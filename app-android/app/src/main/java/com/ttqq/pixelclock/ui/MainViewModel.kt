package com.ttqq.pixelclock.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.ttqq.pixelclock.data.Prefs
import com.ttqq.pixelclock.net.BoardClient
import com.ttqq.pixelclock.net.BoardDiscovery
import com.ttqq.pixelclock.net.DialPreview
import com.ttqq.pixelclock.net.LocalNet
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.Dispatchers

enum class Screen { HOME, DIALS, SETTINGS }

data class UiState(
    val screen: Screen = Screen.HOME,
    val host: String = "",
    val online: Boolean = false,
    val status: BoardClient.Status? = null,
    val bright: Int = 128,
    val rot: Int = 0,
    val wifiSsid: String = "",
    val busy: Boolean = false,
    val discovering: Boolean = false,
    val discovered: List<BoardDiscovery.Found> = emptyList(),
    val dials: List<BoardClient.Dial> = emptyList(),
    val previews: Map<String, DialPreview> = emptyMap(),
    val builtin: List<BoardClient.BuiltinFace> = emptyList(),
    val anim: BoardClient.AnimStatus? = null,
    val uploading: Pair<Long, Long>? = null,
    val message: String? = null,
    val messageIsError: Boolean = false,
)

class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = Prefs(app)
    private val discovery = BoardDiscovery(app)
    private val client = BoardClient(if (prefs.lastHost.isNotEmpty()) BoardClient.normalize(prefs.lastHost) else "http://pixelclock.local")

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    private var pollJob: Job? = null

    init {
        _state.update {
            it.copy(host = prefs.lastHost, bright = prefs.lastBright, rot = prefs.rotation)
        }
        if (prefs.lastHost.isNotEmpty()) {
            connect(prefs.lastHost, auto = true)
        }
    }

    // ---------------- 连接 ----------------

    fun connect(rawHost: String, auto: Boolean = false) {
        val h = BoardClient.normalize(rawHost)
        if (h.isEmpty()) return
        client.setHost(h)
        prefs.lastHost = h
        _state.update { it.copy(host = h, busy = true, message = null) }

        viewModelScope.launch {
            val result = runCatching { client.statusRetry() }
            val ok = result.getOrNull()
            if (ok == null) {
                _state.update {
                    it.copy(
                        online = false,
                        busy = false,
                        status = null,
                        message = diagnose(h, result.exceptionOrNull()),
                        messageIsError = true,
                    )
                }
                stopPolling()
                return@launch
            }
            prefs.lastBright = ok.bright
            prefs.rotation = ok.rot
            _state.update {
                it.copy(
                    online = true,
                    busy = false,
                    status = ok,
                    bright = ok.bright,
                    rot = ok.rot,
                    message = null,
                )
            }
            refreshAll()
            startPolling()
        }
    }

    fun disconnect() {
        stopPolling()
        _state.update { it.copy(online = false, status = null, message = "已断开") }
    }

    /**
     * 连接失败时给出【可执行的】排查提示，而不是干巴巴一句"连不上"。
     * 用户 90% 的情况是：手机没连 WiFi / 手机和板子不在同一网段 / 路由器开了 AP 隔离。
     */
    private fun diagnose(host: String, err: Throwable?): String {
        val raw = err?.message.orEmpty()
        val base = when {
            raw.contains("Cleartext", ignoreCase = true) ->
                "系统拒绝了明文 HTTP（network security config 问题）"
            raw.contains("Unable to resolve host", ignoreCase = true) ||
                raw.contains("Name or service not known", ignoreCase = true) ->
                "找不到主机名"
            raw.contains("Connection refused", ignoreCase = true) ->
                "对方拒绝连接"
            raw.contains("timed out", ignoreCase = true) ||
                raw.contains("timeout", ignoreCase = true) ->
                "连接超时"
            raw.contains("Network is unreachable", ignoreCase = true) ->
                "网络不可达"
            else -> raw.ifBlank { "未知错误" }
        }
        return buildString {
            append("连接失败：$host\n")
            append("原因：$base\n")
            append(LocalNet.hint(getApplication()))
        }
    }

    /** 周期刷新状态 */
    private fun startPolling() {
        stopPolling()
        pollJob = viewModelScope.launch {
            while (true) {
                delay(5000)
                val s = runCatching { client.status() }.getOrNull()
                if (s == null) {
                    _state.update { it.copy(online = false) }
                } else {
                    _state.update { it.copy(online = true, status = s) }
                }
            }
        }
    }

    private fun stopPolling() {
        pollJob?.cancel()
        pollJob = null
    }

    // ---------------- 自动发现 ----------------

    fun discover() {
        _state.update { it.copy(discovering = true, discovered = emptyList()) }
        viewModelScope.launch {
            val found = runCatching { discovery.browse(5000) }.getOrDefault(emptyList())
            if (found.isEmpty()) {
                // mDNS 被路由器/机型过滤时的兜底：扫本机 WiFi 所在网段
                val hits = runCatching { discovery.probeCandidates() }.getOrDefault(emptyList())
                val mapped = hits.map {
                    BoardDiscovery.Found(name = it, host = it, address = it, port = 80)
                }
                _state.update {
                    it.copy(
                        discovering = false,
                        discovered = mapped,
                        message = if (mapped.isEmpty()) {
                            "没找到板子。${LocalNet.hint(getApplication())}"
                        } else "扫描到 ${mapped.size} 个板子",
                        messageIsError = mapped.isEmpty(),
                    )
                }
            } else {
                _state.update { it.copy(discovering = false, discovered = found) }
            }
        }
    }

    // ---------------- 动作 ----------------

    fun setBrightness(level: Int) {
        _state.update { it.copy(bright = level) }
    }

    fun commitBrightness(level: Int) {
        _state.update { it.copy(bright = level) }
        prefs.lastBright = level
        viewModelScope.launch {
            runCatching { client.setBrightness(level) }
                .onFailure { e -> toast(e.message ?: "设置亮度失败", true) }
        }
    }

    fun setRotation(v: Int) {
        _state.update { it.copy(rot = v) }
        prefs.rotation = v
        viewModelScope.launch {
            runCatching { client.setRotation(v) }
                .onFailure { e -> toast(e.message ?: "旋转失败", true) }
        }
    }

    fun selectBuiltinFace(idx: Int) {
        viewModelScope.launch {
            runCatching { client.selectBuiltinFace(idx) }
                .onSuccess { toast("已切换内置表盘 #$idx") }
                .onFailure { e -> toast(e.message ?: "切换失败", true) }
        }
    }

    /** 把商店表盘（单帧 8192B）推到板子 RAM 即时显示 */
    fun pushBuiltinFace(face: BoardClient.BuiltinFace) {
        val b64 = face.previewB64
        if (b64.isNullOrEmpty()) {
            toast("该表盘没有预览数据", true)
            return
        }
        viewModelScope.launch {
            val bytes = runCatching {
                java.util.Base64.getMimeDecoder().decode(b64)
            }.getOrNull()
            if (bytes == null || bytes.size != BoardClient.FRAME_BYTES) {
                toast("表盘数据不完整（${bytes?.size ?: 0}B）", true)
                return@launch
            }
            _state.update { it.copy(uploading = 0L to bytes.size.toLong()) }
            runCatching {
                client.pushFrame(bytes) { sent, total ->
                    _state.update { it.copy(uploading = sent.toLong() to total.toLong()) }
                }
            }.onSuccess {
                _state.update { it.copy(uploading = null) }
                toast("已推送「${face.name}」")
            }.onFailure { e ->
                _state.update { it.copy(uploading = null) }
                toast(e.message ?: "推送失败", true)
            }
        }
    }

    fun playDial(name: String) {
        viewModelScope.launch {
            runCatching { client.dialPlay(name) }
                .onSuccess { toast("正在播放 $name") }
                .onFailure { e -> toast(e.message ?: "播放失败", true) }
        }
    }

    fun deleteDial(name: String) {
        viewModelScope.launch {
            runCatching { client.dialDelete(name) }
                .onSuccess {
                    toast("已删除 $name")
                    refreshDials()
                }
                .onFailure { e -> toast(e.message ?: "删除失败", true) }
        }
    }

    fun uploadDial(name: String, bytes: ByteArray, fps: Int = 6, overlay: Int = 1) {
        viewModelScope.launch {
            _state.update { it.copy(uploading = 0L to bytes.size.toLong()) }
            runCatching {
                client.uploadDial(name, bytes, fps = fps, overlay = overlay) { p ->
                    _state.update { it.copy(uploading = p.sent.toLong() to p.total.toLong()) }
                }
            }.onSuccess {
                _state.update { it.copy(uploading = null) }
                toast("已推送 $name")
                refreshDials()
            }.onFailure { e ->
                _state.update { it.copy(uploading = null) }
                toast(e.message ?: "推送失败", true)
            }
        }
    }

    fun loadAnim() {
        viewModelScope.launch {
            runCatching { client.animLoad() }
                .onSuccess { toast("动画已载入"); refreshAll() }
                .onFailure { e -> toast(e.message ?: "载入失败", true) }
        }
    }

    fun saveAnim() {
        viewModelScope.launch {
            runCatching { client.animSave() }
                .onSuccess { toast("已保存到 flash") }
                .onFailure { e -> toast(e.message ?: "保存失败", true) }
        }
    }

    fun changeWifi(ssid: String, pass: String) {
        viewModelScope.launch {
            runCatching { client.setWifi(ssid, pass) }
                .onSuccess {
                    toast("已下发新 WiFi，板子正在重启…")
                    _state.update { it.copy(wifiSsid = ssid) }
                }
                .onFailure { e -> toast(e.message ?: "切换失败", true) }
        }
    }

    fun renameHost(name: String) {
        viewModelScope.launch {
            runCatching { client.setHostname(name) }
                .onSuccess { toast("主机名已设为 $name，板子重启中…") }
                .onFailure { e -> toast(e.message ?: "改名失败", true) }
        }
    }

    // ---------------- 刷新 ----------------

    fun refreshAll() {
        viewModelScope.launch {
            runCatching { client.status() }.getOrNull()?.let { s ->
                _state.update { it.copy(status = s, bright = s.bright, rot = s.rot, online = true) }
            }
            runCatching { client.wifiSsid() }.getOrNull()?.let { ss ->
                _state.update { it.copy(wifiSsid = ss) }
                prefs.wifiSsid = ss
            }
            refreshDials()
            runCatching { client.builtinFaces() }.getOrNull()?.let { faces ->
                _state.update { it.copy(builtin = faces) }
            }
            runCatching { client.animStatus() }.getOrNull()?.let { a ->
                _state.update { it.copy(anim = a) }
            }
        }
    }

    fun refreshDials() {
        viewModelScope.launch {
            val list = runCatching { client.dialList() }.getOrDefault(emptyList())
            _state.update { it.copy(dials = list) }
            // 拉缩略图（串行，避免压垮板子的 HTTP 服务）
            for (d in list) {
                if (_state.value.previews.containsKey(d.name)) continue
                val p = runCatching { client.dialPreview(d.name) }.getOrNull()
                if (p != null) {
                    _state.update { it.copy(previews = it.previews + (d.name to p)) }
                }
            }
        }
    }

    // ---------------- 叠加时钟位置 ----------------

    /**
     * 调整某个表盘上叠加的 HH:MM 时钟（位置 / 样式 / 字号 / 颜色 / 开关）。
     *
     * 固件 /dialov 写完 meta 立即生效——如果该表盘正在播放，屏幕上马上变。
     * 写完必须刷新列表，否则界面上还是旧的坐标。
     */
    fun setDialOverlay(
        name: String,
        mode: Int, ox: Int, oy: Int, ox2: Int,
        scale: Int, fg: Int, overlay: Int,
    ) {
        viewModelScope.launch {
            runCatching {
                client.dialOverlay(
                    name = name,
                    mode = mode, ox = ox, oy = oy, ox2 = ox2,
                    scale = scale, fg = fg, overlay = overlay,
                )
            }.onSuccess {
                // 只刷新列表，不重拉全部缩略图（省 HTTP 请求，板子扛不住并发）
                val list = runCatching { client.dialList() }.getOrDefault(emptyList())
                _state.update { it.copy(dials = list) }
            }.onFailure { e ->
                toast("调整失败：${e.message ?: e::class.java.simpleName}", true)
            }
        }
    }

    // ---------------- 杂项 ----------------

    fun go(screen: Screen) {
        _state.update { it.copy(screen = screen) }
        if (screen == Screen.DIALS) refreshDials()
    }

    fun toast(msg: String, isError: Boolean = false) {
        _state.update { it.copy(message = msg, messageIsError = isError) }
    }

    fun clearMessage() {
        _state.update { it.copy(message = null) }
    }
}
