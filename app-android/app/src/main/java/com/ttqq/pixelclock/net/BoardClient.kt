package com.ttqq.pixelclock.net

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.DataOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.GZIPInputStream

/**
 * 板子 HTTP 客户端。
 *
 * 板子固件（v0.3.23）提供的接口：
 *   GET  /status                  → {ip,rssi,host,push,bright,rot}
 *   GET  /brightness              → {level}
 *   POST /brightness?level=0..255
 *   GET  /rotate                  → 循环切换；POST /rotate?v=0..3
 *   GET  /wifi                    → {ssid}
 *   POST /wifi?ssid=&pass=
 *   GET  /diallist                → {dials:[{n,c,f,o,b,s,m,x,y,x2,sc,fg}]}
 *   GET  /dialpreview?name=       → base64(首帧 8192B)
 *   POST /dialplay?name=
 *   POST /dialdel?name=
 *   POST /dialov?name=&mode=&ox=&oy=&x2=&sc=&fg=&ov=
 *   POST /dialup?name=&off=&plain=&final=1&fps=&overlay=&burst=&ovmode=&ox=&oy=&x2=&sc=&fg=
 *   GET  /faces                   → gzip JSON（内置表盘字典）
 *   GET  /animlist                → 动画状态
 *   POST /animload / /animsave
 *   POST /face?idx=0..3           → 切换固件内置表盘
 */
class BoardClient(private var baseUrl: String) {

    /** 板子地址，形如 http://192.168.1.46 或 http://pixelclock.local */
    var host: String = baseUrl
        private set

    fun setHost(newHost: String) {
        baseUrl = normalize(newHost)
        host = baseUrl
    }

    companion object {
        /** 单帧 RGB565 字节数：64×64×2 */
        const val FRAME_BYTES = 8192

        /** 把用户输入的裸 IP / 主机名规整成完整 base URL */
        fun normalize(input: String): String {
            var h = input.trim()
            if (h.isEmpty()) return h
            if (!h.startsWith("http://") && !h.startsWith("https://")) {
                h = "http://$h"
            }
            return h.trimEnd('/')
        }
    }

    // ---------------- 底层 HTTP ----------------

    private suspend fun request(
        path: String,
        method: String = "GET",
        timeoutMs: Int = 6000,
        body: ByteArray? = null,
        gzipResponse: Boolean = false,
    ): String = withContext(Dispatchers.IO) {
        val url = URL(baseUrl + path)
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = timeoutMs
            readTimeout = timeoutMs
            doInput = true
            setRequestProperty("Accept", "application/json, text/plain, */*")
            setRequestProperty("Connection", "close")
            if (body != null) {
                doOutput = true
                setFixedLengthStreamingMode(body.size)
                setRequestProperty("Content-Type", "application/octet-stream")
            }
        }
        try {
            if (body != null) {
                DataOutputStream(conn.outputStream).use { it.write(body) }
            }
            val code = conn.responseCode
            val raw = (if (code in 200..299) conn.inputStream else conn.errorStream)
            if (raw == null) throw BoardException("HTTP $code 无响应体")
            val stream = BufferedInputStream(raw)
            // 固件 /faces 与 / 返回 Content-Encoding: gzip
            val isGzip = gzipResponse ||
                (conn.getHeaderField("Content-Encoding")?.contains("gzip", true) == true)
            val decoded: java.io.InputStream = if (isGzip) GZIPInputStream(stream) else stream
            val text = decoded.readBytes().toString(Charsets.UTF_8)
            if (code !in 200..299) throw BoardException("HTTP $code: ${text.take(120)}")
            text
        } catch (e: BoardException) {
            throw e
        } catch (e: Exception) {
            throw BoardException("连接失败：${e.message ?: e::class.java.simpleName}")
        } finally {
            conn.disconnect()
        }
    }

    private suspend fun getJson(path: String) = JSONObject(request(path))

    /**
     * 带重试的 GET。弱 WiFi 下板子的 WebServer 偶发拒连接，
     * 重试 2 次（指数退避）能覆盖绝大多数瞬时故障。
     */
    suspend fun statusRetry(): Status {
        var last: Exception? = null
        repeat(3) { attempt ->
            try {
                return status()
            } catch (e: Exception) {
                last = e
                if (attempt < 2) kotlinx.coroutines.delay(400L * (attempt + 1))
            }
        }
        throw last ?: BoardException("状态读取失败")
    }

    /**
     * 能力探测：固件没有 /version 端点，用接口是否存在来推断版本能力。
     * v0.3.22 起有 /rotate 与 /status.rot；v0.3.23 起有 /wifi。
     */
    suspend fun capabilities(): Capabilities {
        // /status.rot 字段存在 → 支持旋转（v0.3.22+）
        val rotate = runCatching { status().rot in 0..3 }.getOrDefault(false)
        // /wifi 返回 JSON → v0.3.23+
        val wifi = runCatching { getJson("/wifi").has("ssid") }.getOrDefault(false)
        // /diallist 返回 dials 数组 → LittleFS 表盘库
        val dialLib = runCatching { getJson("/diallist").has("dials") }.getOrDefault(false)
        return Capabilities(rotate, wifi, dialLib)
    }

    data class Status(
        val ip: String = "",
        val rssi: Int = 0,
        val host: String = "",
        val push: Int = 0,
        val bright: Int = 0,
        val rot: Int = 0,
    ) {
        /** 信号质量百分比（-100..0 dBm 映射到 0..100） */
        val signalPct: Int get() = ((rssi + 100).coerceIn(0, 100))
        val signalBars: Int
            get() = when {
                rssi >= -55 -> 4
                rssi >= -67 -> 3
                rssi >= -75 -> 2
                rssi >= -85 -> 1
                else -> 0
            }
    }

    suspend fun status(): Status = getJson("/status").let {
        Status(
            ip = it.optString("ip"),
            rssi = it.optInt("rssi"),
            host = it.optString("host"),
            push = it.optInt("push"),
            bright = it.optInt("bright"),
            rot = it.optInt("rot"),
        )
    }

    // ---------------- 亮度 / 旋转 ----------------

    suspend fun brightness(): Int = getJson("/brightness").optInt("level")

    suspend fun setBrightness(level: Int) {
        request("/brightness?level=${level.coerceIn(0, 255)}", "POST")
    }

    suspend fun setRotation(v: Int) {
        request("/rotate?v=${v.coerceIn(0, 3)}", "POST")
    }

    // ---------------- WiFi ----------------

    suspend fun wifiSsid(): String = getJson("/wifi").optString("ssid")

    /** 切换 WiFi；板子会保存并重启，失败自动回落配网热点 */
    suspend fun setWifi(ssid: String, pass: String) {
        val q = "ssid=${java.net.URLEncoder.encode(ssid, "UTF-8")}" +
            "&pass=${java.net.URLEncoder.encode(pass, "UTF-8")}"
        request("/wifi?$q", "POST", timeoutMs = 12000)
    }

    /** 改板子主机名（影响 mDNS 与 DHCP 主机名） */
    suspend fun setHostname(name: String) {
        request("/setname?name=${java.net.URLEncoder.encode(name, "UTF-8")}", "POST", timeoutMs = 12000)
    }

    // ---------------- 表盘库 ----------------

    data class Dial(
        val name: String,
        val frames: Int = 1,
        val fps: Int = 6,
        val overlay: Int = 0,
        val burst: Int = 0,
        val size: Long = 0,
        val ovMode: Int = 0,
        val ox: Int = -1,
        val oy: Int = 46,
        val ox2: Int = 34,
        val ovScale: Int = 2,
        val ovFg: Int = 0,
    )

    suspend fun dialList(): List<Dial> {
        val arr = getJson("/diallist").optJSONArray("dials") ?: return emptyList()
        return (0 until arr.length()).mapNotNull { i ->
            val o = arr.optJSONObject(i) ?: return@mapNotNull null
            Dial(
                name = o.optString("n"),
                frames = o.optInt("c", 1),
                fps = o.optInt("f", 6),
                overlay = o.optInt("o"),
                burst = o.optInt("b"),
                size = o.optLong("s"),
                ovMode = o.optInt("m"),
                ox = o.optInt("x", -1),
                oy = o.optInt("y", 46),
                ox2 = o.optInt("x2", 34),
                ovScale = o.optInt("sc", 2),
                ovFg = o.optInt("fg"),
            )
        }.filter { it.name.isNotEmpty() }
    }

    /** 表盘首帧缩略图（base64 → RGB565 像素） */
    suspend fun dialPreview(name: String): DialPreview? {
        val b64 = request("/dialpreview?name=${enc(name)}").trim()
        if (b64.isEmpty()) return null
        return runCatching { DialPreview.decode(b64) }.getOrNull()
    }

    suspend fun dialPlay(name: String) {
        request("/dialplay?name=${enc(name)}", "POST")
    }

    suspend fun dialDelete(name: String) {
        request("/dialdel?name=${enc(name)}", "POST")
    }

    suspend fun dialOverlay(
        name: String,
        mode: Int? = null, ox: Int? = null, oy: Int? = null,
        ox2: Int? = null, scale: Int? = null, fg: Int? = null, overlay: Int? = null,
    ) {
        val q = buildString {
            append("name=").append(enc(name))
            mode?.let { append("&mode=").append(it) }
            ox?.let { append("&ox=").append(it) }
            oy?.let { append("&oy=").append(it) }
            ox2?.let { append("&x2=").append(it) }
            scale?.let { append("&sc=").append(it) }
            fg?.let { append("&fg=").append(it) }
            overlay?.let { append("&ov=").append(it) }
        }
        request("/dialov?$q", "POST")
    }

    /** 切换固件内置表盘（0=TEST 1=CLOCK 2=PLASMA 3=REMOTE） */
    suspend fun selectBuiltinFace(idx: Int) {
        request("/face?idx=$idx", "POST")
    }

    /**
     * 推送单帧表盘到板子 RAM（即时显示，不落 flash）。
     *
     * 协议：POST /pushface?off=&len=&plain=<hex>，body 为 HEX 文本。
     *  - 一次发满 8192 字节（整帧）→ 固件自动 CRC 校验并 commit
     *  - 分块发 → 需要最后再 POST /pushface?commit=1 触发 CRC 校验
     * 成功后固件自动切到 REMOTE 表盘（idx=3）播放。
     */
    suspend fun pushFrame(data: ByteArray, onProgress: (Int, Int) -> Unit = { _, _ -> }) {
        require(data.size <= FRAME_BYTES) { "单帧最多 $FRAME_BYTES 字节，实际 ${data.size}" }
        val chunk = 2048
        var off = 0
        while (off < data.size) {
            val n = minOf(chunk, data.size - off)
            val hex = data.copyOfRange(off, off + n).joinToString("") { "%02x".format(it) }
            request("/pushface?off=$off&len=$n&plain=$hex", "POST", timeoutMs = 12000)
            off += n
            onProgress(off, data.size)
        }
        // 分块路径：显式 commit 触发 CRC 校验
        request("/pushface?commit=1", "POST", timeoutMs = 8000)
    }

    // ---------------- 表盘上传（分片） ----------------

    data class UploadProgress(val sent: Int, val total: Int, val done: Boolean)

    /**
     * 分片推送 .rgb565 表盘到板子 FS。
     * 协议：POST /dialup?name=&off=&plain=<hex>&[final=1&fps=&overlay=&burst=&...]
     * 每片 ≤ CHUNK_MAX（固件侧 8KB），最后一片带 final=1。
     */
    suspend fun uploadDial(
        name: String,
        data: ByteArray,
        fps: Int = 6,
        overlay: Int = 1,
        burst: Int = 0,
        ovMode: Int = 0,
        ox: Int = -1,
        oy: Int = 46,
        ox2: Int = 34,
        ovScale: Int = 2,
        ovFg: Int = 0,
        onProgress: (UploadProgress) -> Unit = {},
    ) {
        val chunk = 2048                      // 2KB 原始数据 → 4KB hex，安全低于固件上限
        var off = 0
        while (off < data.size) {
            val n = minOf(chunk, data.size - off)
            val part = data.copyOfRange(off, off + n)
            val hex = part.joinToString("") { "%02x".format(it) }
            val isFinal = (off + n) >= data.size
            val q = buildString {
                append("name=").append(enc(name))
                append("&off=").append(off)
                append("&plain=").append(hex)
                if (isFinal) {
                    append("&final=1")
                    append("&fps=").append(fps)
                    append("&overlay=").append(overlay)
                    append("&burst=").append(burst)
                    append("&ovmode=").append(ovMode)
                    append("&ox=").append(ox)
                    append("&oy=").append(oy)
                    append("&x2=").append(ox2)
                    append("&sc=").append(ovScale)
                    append("&fg=").append(ovFg)
                }
            }
            request("/dialup?$q", "POST", timeoutMs = 15000)
            off += n
            onProgress(UploadProgress(off, data.size, isFinal))
        }
    }

    // ---------------- 动画 ----------------

    data class AnimStatus(
        val frames: Int = 0,
        val fps: Int = 0,
        val overlay: Boolean = false,
        val burst: Boolean = false,
        val cap: Int = 0,
        val hasFs: Boolean = false,
        val ovMode: Int = 0,
        val ovX: Int = 12,
        val ovY: Int = 11,
        val ovX2: Int = 34,
        val ovScale: Int = 2,
        val ovFg: Int = 0,
    )

    suspend fun animStatus(): AnimStatus = getJson("/animlist").let {
        AnimStatus(
            frames = it.optInt("frames"),
            fps = it.optInt("fps"),
            overlay = it.optInt("overlay") == 1,
            burst = it.optInt("burst") == 1,
            cap = it.optInt("cap"),
            hasFs = it.optInt("fs") == 1,
            ovMode = it.optInt("ovmode"),
            ovX = it.optInt("ovx", 12),
            ovY = it.optInt("ovy", 11),
            ovX2 = it.optInt("ovx2", 34),
            ovScale = it.optInt("ovs", 2),
            ovFg = it.optInt("ovfg"),
        )
    }

    suspend fun animLoad() { request("/animload", "POST") }
    suspend fun animSave() { request("/animsave", "POST") }

    // ---------------- 内置表盘字典（gzip） ----------------

    /**
     * 固件 /faces 返回：gzip 压缩的 JSON **数组**，每项
     *   { "n": "笑脸", "id": "smiley", "d": "<base64 首帧 8192B>" }
     * 注意：是数组不是 {"faces":[...]}。
     */
    data class BuiltinFace(val id: String, val name: String, val previewB64: String?)

    suspend fun builtinFaces(): List<BuiltinFace> {
        val text = request("/faces", gzipResponse = true).trim()
        if (text.isEmpty()) return emptyList()
        val arr = org.json.JSONArray(text)
        return (0 until arr.length()).mapNotNull { i ->
            val o = arr.optJSONObject(i) ?: return@mapNotNull null
            BuiltinFace(
                id = o.optString("id"),
                name = o.optString("n"),
                previewB64 = o.optString("d").takeIf { it.isNotEmpty() },
            )
        }
    }

    private fun enc(s: String) = java.net.URLEncoder.encode(s, "UTF-8")
}

class BoardException(message: String) : Exception(message)

/**
 * 能力探测结果：固件没有 /version 端点，用接口是否存在来推断版本能力。
 *   旋转   → v0.3.22+（/rotate 与 /status.rot）
 *   WiFi   → v0.3.23+（/wifi）
 *   表盘库 → LittleFS 表盘库（/diallist）
 */
data class Capabilities(
    val hasRotate: Boolean = false,
    val hasWifi: Boolean = false,
    val hasDialLib: Boolean = false,
) {
    val summary: String
        get() = listOf(
            if (hasRotate) "旋转" else "无旋转",
            if (hasWifi) "WiFi" else "无WiFi",
            if (hasDialLib) "表盘库" else "无表盘库",
        ).joinToString(" · ")
}
