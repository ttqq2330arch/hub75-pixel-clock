package com.ttqq.pixelclock.ui

import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import java.io.ByteArrayOutputStream

// ---------------- 连接对话框 ----------------

@Composable
fun ConnectDialog(
    st: UiState,
    onDismiss: () -> Unit,
    onConnect: (String) -> Unit,
    onDiscover: () -> Unit,
) {
    var input by remember { mutableStateOf(st.host) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("连接板子", color = TextHi) },
        text = {
            Column {
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("IP 或主机名", color = TextMid, fontSize = 12.sp) },
                    placeholder = { Text("192.168.1.46", color = TextLow, fontSize = 13.sp) },
                    textStyle = androidx.compose.ui.text.TextStyle(color = TextHi, fontSize = 14.sp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Accent,
                        unfocusedBorderColor = Border,
                        cursorColor = Accent,
                        focusedLabelColor = Accent,
                        unfocusedLabelColor = TextMid,
                    ),
                )
                Spacer(Modifier.height(10.dp))
                Text(
                    "提示：主机名填 pixelclock.local 可跨 IP 段访问（板子改了 IP 也不用重填）",
                    color = TextLow,
                    fontSize = 11.sp,
                )
                if (st.discovered.isNotEmpty()) {
                    Spacer(Modifier.height(10.dp))
                    Text("自动发现的板子：", color = TextMid, fontSize = 12.sp)
                    st.discovered.forEach { d ->
                        Box(
                            Modifier
                                .fillMaxWidth()
                                .padding(top = 6.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .background(SurfaceHi)
                                .clickable {
                                    input = d.baseUrl
                                }
                                .padding(10.dp),
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    Text(d.name, color = TextHi, fontSize = 13.sp)
                                    Text(d.baseUrl, color = TextLow, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                                }
                                Text("选择", color = Accent, fontSize = 11.sp)
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onConnect(input) }) { Text("连接", color = Accent) }
        },
        dismissButton = {
            Row {
                TextButton(onClick = onDiscover) { Text("自动发现", color = TextMid) }
                TextButton(onClick = onDismiss) { Text("取消", color = TextMid) }
            }
        },
        containerColor = Surface,
    )
}

// ---------------- WiFi 对话框 ----------------

@Composable
fun WifiDialog(
    current: String,
    onDismiss: () -> Unit,
    onApply: (String, String) -> Unit,
) {
    var ssid by remember { mutableStateOf(current) }
    var pass by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("切换 WiFi", color = TextHi) },
        text = {
            Column {
                Text(
                    "当前：${current.ifEmpty { "未知" }}\n\n切换后板子会保存配置并重启；若新 WiFi 连不上，会自动回落到配网热点 PixelClock-Setup（密码 12345678）。",
                    color = TextMid,
                    fontSize = 12.sp,
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = ssid,
                    onValueChange = { ssid = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("WiFi 名称", color = TextMid, fontSize = 12.sp) },
                    textStyle = androidx.compose.ui.text.TextStyle(color = TextHi, fontSize = 14.sp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Accent,
                        unfocusedBorderColor = Border,
                        cursorColor = Accent,
                        focusedLabelColor = Accent,
                        unfocusedLabelColor = TextMid,
                    ),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = pass,
                    onValueChange = { pass = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("密码（开放网络可留空）", color = TextMid, fontSize = 12.sp) },
                    textStyle = androidx.compose.ui.text.TextStyle(color = TextHi, fontSize = 14.sp),
                    visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Accent,
                        unfocusedBorderColor = Border,
                        cursorColor = Accent,
                        focusedLabelColor = Accent,
                        unfocusedLabelColor = TextMid,
                    ),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onApply(ssid, pass) }) { Text("应用", color = Accent) }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消", color = TextMid) }
        },
        containerColor = Surface,
    )
}

// ---------------- 亮度预设 ----------------

@Composable
fun BrightPresetDialog(
    current: Int,
    onDismiss: () -> Unit,
    onPick: (Int) -> Unit,
) {
    val presets = listOf(
        0 to "息屏",
        30 to "夜间",
        60 to "微光",
        128 to "50%",
        200 to "80%",
        255 to "全亮",
    )
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("亮度预设", color = TextHi) },
        text = {
            Column {
                presets.forEach { (v, label) ->
                    Box(
                        Modifier
                            .fillMaxWidth()
                            .padding(vertical = 3.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(if (v == current) AccentDim else SurfaceHi)
                            .clickable { onPick(v) }
                            .padding(vertical = 11.dp, horizontal = 12.dp),
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(label, color = TextHi, fontSize = 14.sp, modifier = Modifier.weight(1f))
                            Text("$v", color = TextLow, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("关闭", color = TextMid) }
        },
        containerColor = Surface,
    )
}

// ---------------- 推送表盘对话框 ----------------

@Composable
fun UploadDialog(
    onDismiss: () -> Unit,
    onUpload: (String, ByteArray) -> Unit,
) {
    val ctx = LocalContext.current
    var name by remember { mutableStateOf("") }
    var sizeText by remember { mutableStateOf("") }
    var bytes by remember { mutableStateOf<ByteArray?>(null) }
    var err by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }

    val picker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent(),
    ) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        loading = true
        err = null
        try {
            val data = ctx.contentResolver.openInputStream(uri)?.use { input ->
                val bos = ByteArrayOutputStream()
                input.copyTo(bos)
                bos.toByteArray()
            } ?: throw IllegalStateException("打不开文件")
            bytes = data
            sizeText = "${data.size / 1024} KB"
            if (name.isEmpty()) {
                name = uri.lastPathSegment?.substringAfterLast('/')?.removeSuffix(".rgb565") ?: "dial"
            }
        } catch (e: Exception) {
            err = "读取失败：${e.message}"
        } finally {
            loading = false
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("推送表盘到板子", color = TextHi) },
        text = {
            Column {
                Button(
                    onClick = { picker.launch("*/*") },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = SurfaceHi),
                ) {
                    Text(if (bytes == null) "选择 .rgb565 文件" else "重新选择", color = Accent, fontSize = 13.sp)
                }
                if (loading) {
                    Spacer(Modifier.height(8.dp))
                    LoadingRow("读取文件…")
                }
                if (sizeText.isNotEmpty()) {
                    Spacer(Modifier.height(6.dp))
                    Text("已选：$sizeText", color = Good, fontSize = 12.sp)
                }
                err?.let {
                    Spacer(Modifier.height(6.dp))
                    Text(it, color = Bad, fontSize = 12.sp)
                }
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    label = { Text("表盘名", color = TextMid, fontSize = 12.sp) },
                    textStyle = androidx.compose.ui.text.TextStyle(color = TextHi, fontSize = 14.sp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Accent,
                        unfocusedBorderColor = Border,
                        cursorColor = Accent,
                        focusedLabelColor = Accent,
                        unfocusedLabelColor = TextMid,
                    ),
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    "格式：64×64 RGB565 逐帧拼接（每帧 8192 字节）。文件会被分片推到板子 flash。",
                    color = TextLow,
                    fontSize = 11.sp,
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val b = bytes
                    if (b != null && name.isNotBlank()) {
                        onUpload(name.trim(), b)
                    }
                },
                enabled = bytes != null && name.isNotBlank(),
            ) { Text("推送", color = if (bytes != null) Accent else TextLow) }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消", color = TextMid) }
        },
        containerColor = Surface,
    )
}
