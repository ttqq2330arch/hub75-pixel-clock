package com.ttqq.pixelclock.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread

/**
 * DeviceHttp 是 WebView 桥接的传输层：把网页生成的 HEX 帧数据 POST 到板子。
 * 这里用零依赖的 ServerSocket 起一个桩，验证路径、body、Content-Type，以及非 2xx 抛异常。
 *
 * 注：com.sun.net.httpserver 不在本机构建 JRE 的默认模块里，故自写一个最小 HTTP 响应器。
 */
class DeviceHttpTest {

    /** 最小 HTTP 桩：连接关闭后一次性读全请求，解析首行/头/body，按回调返回状态码。 */
    private class TinyServer(
        private val onRequest: (method: String, path: String, query: String, headers: Map<String, String>, body: String) -> Int,
    ) {
        private val server = ServerSocket(0, 0, InetAddress.getByName("127.0.0.1"))
        val port: Int get() = server.localPort
        private var running = true

        init {
            thread(isDaemon = true) {
                while (running) {
                    try { handle(server.accept()) } catch (_: Exception) { /* 忽略单次异常 */ }
                }
            }
        }

        private fun handle(sock: Socket) {
            try {
                val `in` = sock.getInputStream()
                val buf = ByteArray(1024)
                val headOut = ByteArrayOutputStream()
                // 1) 读头直到 \r\n\r\n
                var headerEnd = -1
                while (headerEnd < 0) {
                    val n = `in`.read(buf)
                    if (n < 0) break
                    headOut.write(buf, 0, n)
                    val a = headOut.toByteArray()
                    for (i in 0 until a.size - 3) {
                        if (a[i] == 13.toByte() && a[i + 1] == 10.toByte() && a[i + 2] == 13.toByte() && a[i + 3] == 10.toByte()) {
                            headerEnd = i
                            break
                        }
                    }
                }
                val a = headOut.toByteArray()
                val headerBytes = if (headerEnd >= 0) a.copyOf(headerEnd) else a
                var bodyBytes = if (headerEnd >= 0) a.copyOfRange(headerEnd + 4, a.size) else ByteArray(0)
                val headerText = headerBytes.toString(Charsets.ISO_8859_1)
                val contentLength = headerText.lines()
                    .firstOrNull { it.startsWith("content-length", ignoreCase = true) }
                    ?.substringAfter(":")?.trim()?.toIntOrNull() ?: 0
                // 2) 按 Content-Length 补齐 body（客户端用定长传输，不会因等 EOF 死锁）
                val bodyOut = ByteArrayOutputStream()
                bodyOut.write(bodyBytes)
                while (bodyOut.size() < contentLength) {
                    val n = `in`.read(buf)
                    if (n < 0) break
                    bodyOut.write(buf, 0, n)
                }
                val body = bodyOut.toByteArray().toString(Charsets.ISO_8859_1)
                val firstLine = headerText.substringBefore("\r\n")
                val parts = firstLine.split(" ")
                val method = parts[0]
                val url = parts.getOrElse(1) { "" }
                val (path, query) = if (url.contains("?")) url.substringBefore("?") to url.substringAfter("?") else url to ""
                val headers = headerText.lines().drop(1).filter { it.contains(":") }.associate {
                    val i = it.indexOf(":"); it.substring(0, i).trim().lowercase() to it.substring(i + 1).trim()
                }
                val code = onRequest(method, path, query, headers, body)
                val out = sock.getOutputStream()
                out.write("HTTP/1.1 $code OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray())
                out.flush()
            } catch (_: Exception) {
                // 忽略
            } finally {
                runCatching { sock.close() }
            }
        }

        fun stop() { running = false; runCatching { server.close() } }
    }

    private fun baseUrl(server: TinyServer) = "http://127.0.0.1:${server.port}"

    @Test
    fun `POST 把 HEX body 与路径原样发出`() {
        // 确保本地回环不走代理
        System.setProperty("http.nonProxyHosts", "127.0.0.1|localhost|*.local|192.168.*")
        val lastBody = AtomicReference<String>("")
        val lastCt = AtomicReference<String>("")
        val server = TinyServer { _, path, query, headers, body ->
            lastBody.set(body)
            lastCt.set(headers["content-type"] ?: "")
            assertTrue("path 应为 /dialup，实际 $path", path == "/dialup")
            assertTrue("缺少 name 参数: $query", query.contains("name=test"))
            assertTrue("缺少 off 参数: $query", query.contains("off=0"))
            200
        }
        try {
            val hex = "001f07e0ffff0000" // 4 字节 HEX（2 像素 RGB565）
            DeviceHttp.post(baseUrl(server), "/dialup?name=test&off=0&len=4&final=1", hex)
            assertEquals("body 必须是原始 HEX 文本", hex, lastBody.get())
            assertTrue("Content-Type 应为 text/plain，实际 ${lastCt.get()}", lastCt.get().startsWith("text/plain"))
        } finally {
            server.stop()
        }
    }

    @Test
    fun `GET 成功不抛异常`() {
        System.setProperty("http.nonProxyHosts", "127.0.0.1|localhost|*.local|192.168.*")
        val server = TinyServer { _, _, _, _, _ -> 200 }
        try {
            DeviceHttp.get(baseUrl(server), "/status")
        } finally {
            server.stop()
        }
    }

    @Test
    fun `非 2xx 抛异常`() {
        System.setProperty("http.nonProxyHosts", "127.0.0.1|localhost|*.local|192.168.*")
        val server = TinyServer { _, _, _, _, _ -> 500 }
        try {
            assertThrows(RuntimeException::class.java) {
                DeviceHttp.post(baseUrl(server), "/boom", "deadbeef")
            }
        } finally {
            server.stop()
        }
    }
}
