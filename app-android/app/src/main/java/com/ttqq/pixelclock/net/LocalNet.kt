package com.ttqq.pixelclock.net

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import java.net.Inet4Address
import java.net.NetworkInterface

/**
 * 本机网络信息工具。
 *
 * 用户「连不上」的最常见原因不是 APP 有 bug，而是：
 *   1. 手机没连 WiFi，或连的是访客网络 / 路由器开了 AP 隔离
 *   2. 板子和手机不在同一网段（板子 IP 变了）
 *   3. 手机用的是移动数据
 *
 * 所以连接对话框必须告诉用户「你的手机现在在哪个网段」，
 * 否则用户只能盲猜板子 IP。
 */
object LocalNet {

    /** 本机当前 WiFi IPv4 地址；没连 WiFi 时返回 null */
    fun wifiIp(context: Context): String? {
        val viaCm = wifiIpFromConnectivityManager(context)
        if (viaCm != null) return viaCm
        return wifiIpFromInterfaces()
    }

    private fun wifiIpFromConnectivityManager(context: Context): String? {
        return try {
            val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            val network = cm?.activeNetwork ?: return null
            val caps = cm.getNetworkCapabilities(network) ?: return null
            if (!caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) return null
            val lp = cm.getLinkProperties(network) ?: return null
            lp.linkAddresses
                .firstOrNull { la -> la.address is Inet4Address }
                ?.address
                ?.hostAddress
        } catch (e: Exception) {
            null
        }
    }

    private fun wifiIpFromInterfaces(): String? {
        return try {
            val ifaces = NetworkInterface.getNetworkInterfaces()?.toList() ?: return null
            val wifi = ifaces.firstOrNull { n ->
                val nm = n.name.lowercase()
                (nm.contains("wlan") || nm.contains("wifi")) && n.isUp
            }
            val target = wifi ?: ifaces.firstOrNull { n ->
                n.isUp && !n.isLoopback && !n.isVirtual &&
                    n.inetAddresses.toList()
                        .any { a -> a is Inet4Address && !a.isLinkLocalAddress }
            }
            target?.inetAddresses?.toList()
                ?.firstOrNull { addr -> addr is Inet4Address && !addr.isLinkLocalAddress }
                ?.hostAddress
        } catch (e: Exception) {
            null
        }
    }

    /** 本机 WiFi 的 /24 网段前缀，例如 "192.168.1."；取不到返回 null */
    fun subnetOf(context: Context): String? =
        wifiIp(context)?.let { subnetOfIp(it) }

    /** 由 IPv4 推导 /24 前缀，例如 "192.168.1.46" → "192.168.1." */
    fun subnetOfIp(ip: String): String? {
        val parts = ip.trim().split('.')
        if (parts.size != 4) return null
        val nums = parts.map { p -> p.toIntOrNull() ?: return null }
        if (nums.any { n -> n !in 0..255 }) return null
        return parts.take(3).joinToString(".") + "."
    }

    /** 设备是否连上了 WiFi（能拿到本机 WiFi IP） */
    fun hasWifi(context: Context): Boolean = !wifiIp(context).isNullOrBlank()

    /** 供 UI 显示：板子 IP 应该填什么范围 */
    fun hint(context: Context): String {
        val ip = wifiIp(context)
        val subnet = subnetOf(context)
        return when {
            ip == null -> "本机未连接 WiFi —— 请先连上和板子同一个 WiFi"
            subnet == null -> "本机 IP：$ip"
            else -> "本机 $ip（板子应在 ${subnet}x 网段）"
        }
    }
}
