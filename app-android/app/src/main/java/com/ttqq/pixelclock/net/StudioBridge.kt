package com.ttqq.pixelclock.net

import android.webkit.JavascriptInterface
import org.json.JSONObject

/**
 * WebView 与 APP 原生层之间的桥。
 *
 * 网页（assets/studio.html，即用户做的「HUB75 像素图片生成器」）里的「推送到表盘」按钮
 * 原本自己用 fetch 直连设备，但在 Android WebView 里会撞上明文 HTTP 与 CORS 限制。
 * 这里把“发往设备”那一层换成原生 HttpURLConnection —— 复用 APP 已连接的板子地址
 * （mDNS 自动发现或手动连接），并享受全局 cleartext 放行配置。
 *
 * 网页侧通过 window.PixelClockBridge 调用；本类以 "NativeBridge" 名义注入 WebView。
 * @JavascriptInterface 方法运行在 WebView 的 JavaBridge 后台线程，同步网络 IO 不会卡 UI。
 */
class StudioBridge(
    /** 返回当前 APP 已连接的板子 base URL，例如 http://192.168.1.46 */
    private val getHost: () -> String,
    /** 用户点击“打开设备网页”时，用外部浏览器打开该地址 */
    private val onOpenDevice: (String) -> Unit,
) {

    @JavascriptInterface
    fun getBaseUrl(): String = getHost().trim()

    @JavascriptInterface
    fun post(path: String, body: String): String = wrap { DeviceHttp.post(getBaseUrl(), path, body) }

    @JavascriptInterface
    fun get(path: String): String = wrap { DeviceHttp.get(getBaseUrl(), path) }

    @JavascriptInterface
    fun openDevice() {
        val h = getBaseUrl()
        if (h.isNotEmpty()) onOpenDevice(h)
    }

    /** 统一把结果包成 JSON 字符串，供网页 Promise 解析；任何异常都不向上抛（WebView 看不到堆栈）。 */
    private fun wrap(block: () -> Unit): String {
        val json = JSONObject()
        return try {
            if (getBaseUrl().isEmpty()) {
                json.put("ok", false).put("error", "未连接像素时钟：请先在「控制台」连上板子")
            } else {
                block()
                json.put("ok", true)
            }
            json.toString()
        } catch (e: Exception) {
            json.put("ok", false).put("error", e.message ?: e.javaClass.simpleName)
            json.toString()
        }
    }
}
