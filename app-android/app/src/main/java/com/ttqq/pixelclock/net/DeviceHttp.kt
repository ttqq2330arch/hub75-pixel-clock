package com.ttqq.pixelclock.net

import java.io.DataOutputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * 阻塞式 HTTP 工具，专供 WebView 桥接线程调用。
 *
 * 背景：@JavascriptInterface 标注的方法运行在 WebView 独立的 JavaBridge 线程上，
 * 可以在这里直接做同步网络 IO，不会卡 Android 主线程。
 *
 * 推送契约（与固件 /dialup 对齐）：body 是 HEX 文本（无 \0，规避 ESP32 WebServer
 * 二进制截断），Content-Type 用 text/plain。设备读 `arg("plain")` 解码写入文件。
 */
object DeviceHttp {

    /** POST 文本（HEX）到 baseUrl+path，非 2xx 抛异常。 */
    fun post(baseUrl: String, path: String, body: String) {
        val bodyBytes = body.toByteArray(Charsets.UTF_8)
        val url = URL(baseUrl.trimEnd('/') + path)
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 8000
            readTimeout = 15000
            doInput = true
            doOutput = true
            setFixedLengthStreamingMode(bodyBytes.size) // 显式定长：避免 chunked（ESP32 WebServer 不友好）
            setRequestProperty("Content-Type", "text/plain; charset=utf-8")
            setRequestProperty("Connection", "close")
        }
        try {
            DataOutputStream(conn.outputStream).use { it.write(bodyBytes) }
            val code = conn.responseCode
            if (code !in 200..299) {
                val err = runCatching {
                    conn.errorStream?.bufferedReader()?.readText()?.take(120)
                }.getOrNull().orEmpty()
                throw RuntimeException("HTTP $code: $err")
            }
        } finally {
            conn.disconnect()
        }
    }

    /** GET baseUrl+path，非 2xx 抛异常。 */
    fun get(baseUrl: String, path: String) {
        val url = URL(baseUrl.trimEnd('/') + path)
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 8000
            readTimeout = 8000
            doInput = true
            setRequestProperty("Connection", "close")
        }
        try {
            val code = conn.responseCode
            if (code !in 200..299) {
                val err = runCatching {
                    conn.errorStream?.bufferedReader()?.readText()?.take(120)
                }.getOrNull().orEmpty()
                throw RuntimeException("HTTP $code: $err")
            }
        } finally {
            conn.disconnect()
        }
    }
}
