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

            val found = mutableListOf<Found>()
            val listener = object : NsdManager.DiscoveryListener {
                override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                    if (cont.isActive) cont.resume(found.toList())
                }

                override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                    if (cont.isActive) cont.resume(found.toList())
                }

                override fun onDiscoveryStarted(serviceType: String) {}

                override fun onDiscoveryStopped(serviceType: String) {
                    if (cont.isActive) cont.resume(found.toList())
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

            val done = AtomicBoolean(false)
            try {
                mgr.discoverServices("_http._tcp.", NsdManager.PROTOCOL_DNS_SD, listener)
            } catch (e: Exception) {
                if (cont.isActive) cont.resume(emptyList())
                return@suspendCancellableCoroutine
            }

            // 超时兜底：NsdManager 的 onDiscoveryStopped 在部分机型不触发
            val main = android.os.Handler(android.os.Looper.getMainLooper())
            main.postDelayed({
                if (done.compareAndSet(false, true)) {
                    runCatching { mgr.stopServiceDiscovery(listener) }
                    if (cont.isActive) cont.resume(found.toList())
                }
            }, timeoutMs)

            cont.invokeOnCancellation {
                runCatching { mgr.stopServiceDiscovery(listener) }
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
     * 只探测 /24 网段里有限个候选，避免全网扫描。
     */
    suspend fun probeCandidates(subnet: String = "192.168.1."): List<String> = coroutineScope {
        val candidates = (2..60).map { "$subnet$it" }
        val hits = mutableListOf<String>()
        val sem = Semaphore(24)
        val jobs = candidates.map { ip ->
            async {
                sem.acquire()
                try {
                    val ok = runCatching {
                        val c = BoardClient("http://$ip")
                        c.status().host.isNotEmpty()
                    }.getOrDefault(false)
                    if (ok) hits.add(ip)
                } finally {
                    sem.release()
                }
            }
        }
        jobs.awaitAll()
        hits
    }

    @Suppress("unused")
    private fun multicastLock(): WifiManager.MulticastLock? {
        val wm = context.getSystemService(Context.WIFI_SERVICE) as? WifiManager ?: return null
        return wm.createMulticastLock("pixelclock-mdns").apply {
            setReferenceCounted(true)
            acquire()
        }
    }
}
