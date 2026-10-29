package com.ttqq.pixelclock.net

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Semaphore
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.coroutines.resume

/**
 * mDNS 自动发现板子。
 *
 * 固件 net.cpp 在连上 WiFi 后注册：
 *     MDNS.begin(gHostname)          → http://pixelclock.local/
 *     MDNS.addService("http","tcp",80)
 * 主机名可通过 /setname 改名（多板部署时 pixelclock-01 / -02 ...）。
 *
 * Android 侧用 NsdManager 浏览 _http._tcp.，拿到主机名后即可直连。
 *
 * ⚠️ 必须在浏览期间持有 WifiManager.MulticastLock。
 *    Android 会把未持有 multicast lock 的进程的组播包直接丢弃，
 *    导致 NsdManager 收不到任何 onServiceFound —— 这是「自动发现永远扫不到」
 *    的头号原因，光申请 CHANGE_WIFI_MULTICAST_STATE 权限是不够的。
 */
class BoardDiscovery(private val context: Context) {

    data class Found(
        val name: String,
        val host: String,
        val address: String,
        val port: Int,
    ) {
        /** 规范化为可直接请求的 base URL */
        val baseUrl: String get() = "http://$address:$port"
    }

    private val nsdManager: NsdManager? =
        context.getSystemService(Context.NSD_SERVICE) as? NsdManager

    /** 浏览 _http._tcp. 域内的所有服务 */
    suspend fun browse(timeoutMs: Long = 6000): List<Found> =
        suspendCancellableCoroutine { cont ->
            val mgr = nsdManager
            if (mgr == null) {
                cont.resume(emptyList())
                return@suspendCancellableCoroutine
            }

            val lock = acquireMulticastLock()
            val found = mutableListOf<Found>()
            val done = AtomicBoolean(false)

            // listener 与 finish 互相调用：listener 先声明为 lateinit，
            // finish 才能前向引用它（Kotlin 局部变量不支持前向引用）
            lateinit var listener: NsdManager.DiscoveryListener

            fun finish(result: List<Found>) {
                if (done.compareAndSet(false, true)) {
                    runCatching { mgr.stopServiceDiscovery(listener) }
                    runCatching { lock?.release() }
                    if (cont.isActive) cont.resume(result)
                }
            }

            listener = object : NsdManager.DiscoveryListener {
                override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                    finish(emptyList())
                }

                override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                    finish(emptyList())
                }

                override fun onDiscoveryStarted(serviceType: String) {}

                override fun onDiscoveryStopped(serviceType: String) {
                    finish(found.toList())
                }

                override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                    if (!serviceInfo.serviceType.contains("_http._tcp")) return
                    resolve(mgr, serviceInfo) { f ->
                        if (found.none { it.name == f.name }) {
                            found.add(f)
                        }
                    }
                }

                override fun onServiceLost(serviceInfo: NsdServiceInfo) {}
            }

            try {
                mgr.discoverServices("_http._tcp.", NsdManager.PROTOCOL_DNS_SD, listener)
            } catch (e: Exception) {
                finish(emptyList())
                return@suspendCancellableCoroutine
            }

            // 超时兜底：NsdManager 的 onDiscoveryStopped 在部分机型不触发
            val main = android.os.Handler(android.os.Looper.getMainLooper())
            main.postDelayed({ finish(found.toList()) }, timeoutMs)

            cont.invokeOnCancellation {
                runCatching { mgr.stopServiceDiscovery(listener) }
                runCatching { lock?.release() }
            }
        }

    private fun resolve(
        mgr: NsdManager,
        info: NsdServiceInfo,
        onFound: (Found) -> Unit,
    ) {
        @Suppress("DEPRECATION")
        mgr.resolveService(info, object : NsdManager.ResolveListener {
            override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) {}
            override fun onServiceResolved(info: NsdServiceInfo) {
                val host = info.host?.hostName ?: return
                // Android 12+ 拿不到 Inet4Address 时退回 hostName
                val addr = info.host?.hostAddress ?: host
                val name = info.serviceName?.substringBefore('.') ?: host
                onFound(Found(name = name, host = host, address = addr, port = info.port))
            }
        })
    }

    /**
     * 常见板子 IP 的并发探测（mDNS 在部分 Android 机型/路由器上被过滤时的兜底）。
     * 网段默认取【本机 WiFi 所在 /24】，而不是写死 192.168.1.——
     * 写死的话，用户家里网段是 192.168.0.x 或 10.x 时就永远扫不到。
     */
    suspend fun probeCandidates(subnet: String? = null): List<String> {
        val net = subnet ?: LocalNet.subnetOf(context) ?: "192.168.1."
        return coroutineScope {
            val candidates = (2..120).map { "$net$it" }
            val hits = mutableListOf<String>()
            val sem = Semaphore(32)
            val jobs = candidates.map { ip ->
                async {
                    sem.acquire()
                    try {
                        if (probeHost(ip)) hits.add(ip)
                    } finally {
                        sem.release()
                    }
                }
            }
            jobs.awaitAll()
            hits.sortedBy { it.substringAfterLast('.').toIntOrNull() ?: 0 }
        }
    }

    /**
     * 轻量探活：只发一个 GET /status，1.2s 超时就放弃。
     * 扫描 120 个地址时，超时必须短，否则整轮要等好几分钟。
     */
    private fun probeHost(ip: String): Boolean = runCatching {
        val conn = URL("http://$ip/status").openConnection() as HttpURLConnection
        conn.connectTimeout = 1200
        conn.readTimeout = 1200
        conn.requestMethod = "GET"
        conn.setRequestProperty("Connection", "close")
        val code = conn.responseCode
        val ok = code in 200..299
        conn.disconnect()
        ok
    }.getOrDefault(false)

    /**
     * 获取并持有组播锁。Android 系统会丢弃未持锁进程的组播包，
     * 没有这个锁，NsdManager 收不到任何 mDNS 响应。
     */
    private fun acquireMulticastLock(): WifiManager.MulticastLock? {
        val wm = context.getSystemService(Context.WIFI_SERVICE) as? WifiManager ?: return null
        return runCatching {
            wm.createMulticastLock("pixelclock-mdns").apply {
                setReferenceCounted(true)
                acquire()
            }
        }.getOrNull()
    }
}
