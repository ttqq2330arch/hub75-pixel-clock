package com.ttqq.pixelclock.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ttqq.pixelclock.net.BoardClient

@Composable
fun PixelClockApp(vm: MainViewModel, st: UiState) {
    val snack = remember { SnackbarHostState() }

    LaunchedEffect(st.message) {
        st.message?.let {
            snack.showSnackbar(it)
            vm.clearMessage()
        }
    }

    Scaffold(
        containerColor = Bg,
        snackbarHost = { SnackbarHost(snack) },
        bottomBar = { BottomBar(st.screen) { vm.go(it) } },
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize()) {
            when (st.screen) {
                Screen.HOME -> HomePage(vm, st)
                Screen.DIALS -> DialsPage(vm, st)
                Screen.SETTINGS -> SettingsPage(vm, st)
            }
        }
    }
}

// ==================== 底部导航 ====================

@Composable
private fun BottomBar(current: Screen, onGo: (Screen) -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(Surface)
            .border(1.dp, Border)
    ) {
        Row(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
            NavItem("控制台", Icons.Filled.PlayArrow, current == Screen.HOME, Modifier.weight(1f)) { onGo(Screen.HOME) }
            NavItem("表盘库", Icons.Filled.Add, current == Screen.DIALS, Modifier.weight(1f)) { onGo(Screen.DIALS) }
            NavItem("设置", Icons.Filled.Search, current == Screen.SETTINGS, Modifier.weight(1f)) { onGo(Screen.SETTINGS) }
        }
    }
}

@Composable
private fun NavItem(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    active: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    Column(
        modifier
            .clickable(onClick = onClick)
            .padding(vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            icon,
            contentDescription = label,
            tint = if (active) Accent else TextLow,
            modifier = Modifier.size(20.dp),
        )
        Spacer(Modifier.height(2.dp))
        Text(
            label,
            color = if (active) Accent else TextLow,
            fontSize = 11.sp,
            fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
        )
    }
}

// ==================== 控制台页 ====================

@Composable
private fun HomePage(vm: MainViewModel, st: UiState) {
    var showConnect by remember { mutableStateOf(st.host.isEmpty() || !st.online) }
    var showWifi by remember { mutableStateOf(false) }
    var showBright by remember { mutableStateOf(false) }

    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // ---- 连接状态卡 ----
        item {
            Card(
                title = if (st.online) "设备在线" else "设备未连接",
                subtitle = st.host.ifEmpty { "尚未选择板子" },
                trailing = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (st.status != null) {
                            SignalBars(st.status!!.signalBars)
                            Spacer(Modifier.width(6.dp))
                            Text(
                                "${st.status!!.rssi} dBm",
                                color = TextMid,
                                fontSize = 11.sp,
                            )
                        }
                        IconButton(onClick = { vm.connect(st.host) }) {
                            Icon(Icons.Filled.Refresh, "刷新", tint = Accent, modifier = Modifier.size(18.dp))
                        }
                    }
                },
            ) {
                if (st.status != null) {
                    val s = st.status!!
                    StatusRow("板子 IP", s.ip, Accent, mono = true)
                    StatusRow("主机名", s.host.ifEmpty { "pixelclock" }, mono = true)
                    StatusRow("推送状态", when (s.push) {
                        0 -> "空闲"
                        1 -> "传输中"
                        else -> "完成/错误($s.push)"
                    }, if (s.push == 1) Warn else TextHi)
                } else {
                    Text(
                        "点击右上角刷新重试，或在「设置」里重新选择板子地址",
                        color = TextLow,
                        fontSize = 12.sp,
                    )
                }
                Spacer(Modifier.height(10.dp))
                Button(
                    onClick = { showConnect = true },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = SurfaceHi),
                ) {
                    Text(if (st.online) "切换设备" else "连接设备", color = Accent, fontSize = 13.sp)
                }
            }
        }

        // ---- 亮度 ----
        item {
            Card(
                title = "屏幕亮度",
                subtitle = "当前 ${st.bright}",
                trailing = {
                    TextButton(onClick = { showBright = true }) {
                        Text("预设", color = Accent, fontSize = 12.sp)
                    }
                },
            ) {
                BrightnessSlider(
                    value = st.bright,
                    onChange = { vm.setBrightness(it) },
                    onCommit = { vm.commitBrightness(it) },
                )
            }
        }

        // ---- 旋转 ----
        item {
            Card(
                title = "屏幕旋转",
                subtitle = "当前 ${RotLabels.getOrElse(st.rot) { "0°" }}",
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    RotLabels.forEachIndexed { idx, label ->
                        val active = st.rot == idx
                        Box(
                            Modifier
                                .weight(1f)
                                .height(38.dp)
                                .clip(RoundedCornerShape(9.dp))
                                .background(if (active) AccentDim else SurfaceHi)
                                .clickable { vm.setRotation(idx) },
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                label,
                                color = if (active) Color.Black else TextHi,
                                fontSize = 13.sp,
                                fontWeight = if (active) FontWeight.Bold else FontWeight.Normal,
                            )
                        }
                    }
                }
            }
        }

        // ---- 表盘商店（/faces：6 个单帧表盘，推送即显示）----
        if (st.builtin.isNotEmpty()) {
            item {
                Card(
                    title = "表盘商店",
                    subtitle = "点击即推送到屏幕显示",
                ) {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(st.builtin, key = { it.id }) { f ->
                            val pv = remember(f.id) { decodePreview(f.previewB64) }
                            Column(
                                Modifier
                                    .width(92.dp)
                                    .clip(RoundedCornerShape(10.dp))
                                    .background(SurfaceHi)
                                    .clickable { vm.pushBuiltinFace(f) }
                                    .padding(6.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                            ) {
                                DialThumb(pv, size = 72)
                                Spacer(Modifier.height(4.dp))
                                Text(
                                    f.name,
                                    color = TextMid,
                                    fontSize = 11.sp,
                                    maxLines = 1,
                                )
                            }
                        }
                    }
                }
            }
        }

        // ---- 固件内置表盘（4 个）----
        item {
            Card(
                title = "固件内置表盘",
                subtitle = "切换板子上预置的 4 款表盘",
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("测试" to 0, "时钟" to 1, "等离子" to 2, "远程" to 3).forEach { (label, idx) ->
                        Box(
                            Modifier
                                .weight(1f)
                                .height(40.dp)
                                .clip(RoundedCornerShape(9.dp))
                                .background(SurfaceHi)
                                .clickable { vm.selectBuiltinFace(idx) },
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(label, color = TextHi, fontSize = 12.sp)
                        }
                    }
                }
            }
        }

        // ---- 动画 ----
        item {
            val a = st.anim
            Card(
                title = "远程动画",
                subtitle = a?.let {
                    "${it.frames} 帧 @ ${it.fps}fps${if (it.hasFs) " · 已存 flash" else ""}"
                } ?: "读取中…",
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = { vm.loadAnim() },
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.buttonColors(containerColor = SurfaceHi),
                    ) { Text("载入", color = TextHi, fontSize = 13.sp) }
                    Button(
                        onClick = { vm.saveAnim() },
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.buttonColors(containerColor = SurfaceHi),
                    ) { Text("存到 flash", color = TextHi, fontSize = 13.sp) }
                }
            }
        }

        // ---- WiFi ----
        item {
            Card(
                title = "WiFi 网络",
                subtitle = st.wifiSsid.ifEmpty { "读取中…" },
            ) {
                Button(
                    onClick = { showWifi = true },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = SurfaceHi),
                ) { Text("切换 WiFi", color = Accent, fontSize = 13.sp) }
            }
        }

        item { Spacer(Modifier.height(4.dp)) }
    }

    if (showConnect) {
        ConnectDialog(
            st = st,
            onDismiss = { showConnect = false },
            onConnect = { h ->
                showConnect = false
                vm.connect(h)
            },
            onDiscover = {
                vm.discover()
            },
        )
    }

    if (showWifi) {
        WifiDialog(
            current = st.wifiSsid,
            onDismiss = { showWifi = false },
            onApply = { s, p ->
                showWifi = false
                vm.changeWifi(s, p)
            },
        )
    }

    if (showBright) {
        BrightPresetDialog(
            current = st.bright,
            onDismiss = { showBright = false },
            onPick = {
                showBright = false
                vm.commitBrightness(it)
            },
        )
    }
}

// ==================== 表盘库页 ====================

@Composable
private fun DialsPage(vm: MainViewModel, st: UiState) {
    var showUpload by remember { mutableStateOf(false) }
    var pendingDelete by remember { mutableStateOf<String?>(null) }
    var adjusting by remember { mutableStateOf<String?>(null) }

    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Card(
                title = "板载表盘库",
                subtitle = "共 ${st.dials.size} 个 · 点击缩略图立即播放",
                trailing = {
                    Row {
                        IconButton(onClick = { vm.refreshDials() }) {
                            Icon(Icons.Filled.Refresh, "刷新", tint = Accent, modifier = Modifier.size(18.dp))
                        }
                        IconButton(onClick = { showUpload = true }) {
                            Icon(Icons.Filled.Add, "推送表盘", tint = Accent, modifier = Modifier.size(20.dp))
                        }
                    }
                },
            ) {
                st.uploading?.let { (sent, total) ->
                    UploadProgressBar(sent, total)
                } ?: if (st.dials.isEmpty()) {
                    EmptyState("板子上还没有表盘\n点右上角 + 推送一个 .rgb565 文件")
                } else {
                    Text(
                        "点「调时钟」可拖动表盘上叠加的 HH:MM 位置",
                        color = TextLow,
                        fontSize = 11.sp,
                    )
                }
            }
        }

        items(st.dials, key = { it.name }) { d ->
            Card(
                title = d.name,
                subtitle = "${d.size / 1024} KB · ${d.frames} 帧 · ${d.fps}fps" +
                    if (d.overlay == 1) " · 叠加层" else "",
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    DialThumb(st.previews[d.name], size = 88)
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Button(
                                onClick = { vm.playDial(d.name) },
                                colors = ButtonDefaults.buttonColors(containerColor = AccentDim),
                            ) {
                                Icon(Icons.Filled.PlayArrow, null, tint = androidx.compose.ui.graphics.Color.Black, modifier = Modifier.size(16.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("播放", color = androidx.compose.ui.graphics.Color.Black, fontSize = 12.sp)
                            }
                            Button(
                                onClick = { adjusting = d.name },
                                colors = ButtonDefaults.buttonColors(containerColor = SurfaceHi),
                            ) {
                                Icon(Icons.Filled.Tune, null, tint = Accent, modifier = Modifier.size(16.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("调时钟", color = Accent, fontSize = 12.sp)
                            }
                            IconButton(onClick = { pendingDelete = d.name }) {
                                Icon(Icons.Filled.Delete, "删除", tint = Bad, modifier = Modifier.size(18.dp))
                            }
                        }
                    }
                }
            }
        }

        item { Spacer(Modifier.height(4.dp)) }
    }

    if (showUpload) {
        UploadDialog(
            onDismiss = { showUpload = false },
            onUpload = { name, bytes ->
                showUpload = false
                vm.uploadDial(name, bytes)
            },
        )
    }

    pendingDelete?.let { name ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text("删除表盘？", color = TextHi) },
            text = { Text("将从板子上永久删除 $name", color = TextMid) },
            confirmButton = {
                TextButton(onClick = {
                    vm.deleteDial(name)
                    pendingDelete = null
                }) { Text("删除", color = Bad) }
            },
            dismissButton = {
                TextButton(onClick = { pendingDelete = null }) { Text("取消", color = TextMid) }
            },
            containerColor = Surface,
        )
    }

    // ---------- 叠加时钟位置调整 ----------
    adjusting?.let { name ->
        val d = st.dials.firstOrNull { it.name == name }
        // 表盘被删掉时收起对话框，否则会卡在一个打不开的状态
        LaunchedEffect(d == null) {
            if (d == null) adjusting = null
        }
        if (d != null) {
            ClockAdjustDialog(
                dial = d,
                preview = st.previews[name],
                onDismiss = { adjusting = null },
                onApply = { m, ox, oy, ox2, sc, fg, ov ->
                    vm.setDialOverlay(name, m, ox, oy, ox2, sc, fg, ov)
                },
            )
        }
    }
}

// ==================== 设置页 ====================

@Composable
private fun SettingsPage(vm: MainViewModel, st: UiState) {
    var hostInput by remember(st.host) { mutableStateOf(st.host) }
    var renameInput by remember { mutableStateOf("") }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Card(
            title = "板子地址",
            subtitle = "可填 IP（192.168.1.46）或主机名（pixelclock.local）",
        ) {
            OutlinedTextField(
                value = hostInput,
                onValueChange = { hostInput = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                placeholder = { Text("192.168.1.46", color = TextLow, fontSize = 13.sp) },
                textStyle = androidx.compose.ui.text.TextStyle(color = TextHi, fontSize = 14.sp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Accent,
                    unfocusedBorderColor = Border,
                    cursorColor = Accent,
                ),
            )
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = { vm.connect(hostInput) },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = AccentDim),
                ) { Text("连接", color = androidx.compose.ui.graphics.Color.Black, fontSize = 13.sp) }
                Button(
                    onClick = { vm.discover() },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = SurfaceHi),
                ) { Text("自动发现", color = Accent, fontSize = 13.sp) }
            }
        }

        if (st.discovering) {
            Card(title = "正在搜索…") { LoadingRow("扫描局域网中的板子") }
        }

        if (st.discovered.isNotEmpty()) {
            Card(title = "发现的板子", subtitle = "点击连接") {
                Column {
                    st.discovered.forEach { d ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp))
                                .clickable { vm.connect(d.baseUrl) }
                                .padding(vertical = 10.dp, horizontal = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(d.name, color = TextHi, fontSize = 14.sp, fontWeight = FontWeight.Medium)
                                Text(d.baseUrl, color = TextLow, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                            }
                            Text("连接", color = Accent, fontSize = 12.sp)
                        }
                    }
                }
            }
        }

        Card(
            title = "主机名",
            subtitle = "改 mDNS 名字（多板部署时用，如 pixelclock-01）",
        ) {
            OutlinedTextField(
                value = renameInput,
                onValueChange = { renameInput = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                placeholder = { Text("pixelclock-02", color = TextLow, fontSize = 13.sp) },
                textStyle = androidx.compose.ui.text.TextStyle(color = TextHi, fontSize = 14.sp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Accent,
                    unfocusedBorderColor = Border,
                    cursorColor = Accent,
                ),
            )
            Spacer(Modifier.height(10.dp))
            Button(
                onClick = { vm.renameHost(renameInput) },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = SurfaceHi),
            ) { Text("改名并重启板子", color = Accent, fontSize = 13.sp) }
        }

        Card(title = "关于", subtitle = "像素时钟 · 个人版 v1.0.0") {
            Text(
                "ESP32-S3 + HUB75 64×64 像素时钟的官方手机客户端。\n" +
                    "配套开源固件 v0.3.23：https://github.com/ttqq2330arch/hub75-pixel-clock\n\n" +
                    "本机通过局域网 WiFi 直连板子，不上传任何数据到云端。",
                color = TextMid,
                fontSize = 12.sp,
            )
        }

        Spacer(Modifier.height(8.dp))
    }
}
