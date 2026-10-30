package com.ttqq.pixelclock.ui

import android.graphics.Bitmap
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ttqq.pixelclock.net.BoardClient
import com.ttqq.pixelclock.net.DialOverlay
import com.ttqq.pixelclock.net.DialPreview

/**
 * 叠加时钟位置调整器。
 *
 * 调的是**推送到板子的表盘上叠加的那个 HH:MM**（固件 face_remote 的 overlay 层），
 * 不是固件内置的那款整屏时钟表盘。
 *
 * 交互：64x64 预览上直接拖动时钟框 → 松手写板子（/dialov 立即生效）。
 * 拖动过程中只更新本地预览，**松手才写**——固件每次 /dialov 都会把 meta 落盘到
 * LittleFS，边拖边写等于拿 flash 当橡皮擦。
 */
@Composable
fun ClockAdjustDialog(
    dial: BoardClient.Dial,
    preview: DialPreview?,
    onDismiss: () -> Unit,
    onApply: (mode: Int, ox: Int, oy: Int, ox2: Int, scale: Int, fg: Int, overlay: Int) -> Unit,
) {
    var mode by remember { mutableIntStateOf(dial.ovMode) }
    var ox by remember { mutableIntStateOf(dial.ox) }
    var oy by remember { mutableIntStateOf(dial.oy) }
    var ox2 by remember { mutableIntStateOf(dial.ox2) }
    var scale by remember { mutableIntStateOf(dial.ovScale) }
    var fg by remember { mutableIntStateOf(dial.ovFg) }
    var overlay by remember { mutableIntStateOf(dial.overlay) }

    /** 拖拽目标：0=文本框，1=小时块，2=分钟块 */
    var dragTarget by remember { mutableIntStateOf(0) }

    // 拖拽起点快照 + 浮点累计偏移（拖动中保持浮点精度，松手才取整）
    var baseOx by remember { mutableIntStateOf(dial.ox) }
    var baseOy by remember { mutableIntStateOf(dial.oy) }
    var baseOx2 by remember { mutableIntStateOf(dial.ox2) }
    var accX by remember { mutableFloatStateOf(0f) }
    var accY by remember { mutableFloatStateOf(0f) }

    /** 当前生效的位置（含拖动中的临时偏移） */
    val curOx = if (dragTarget == 0 && mode == 0 && baseOx < 0)
        DialOverlay.textX(DialOverlay.CENTER, scale)
    else baseOx
    val curOx2 = baseOx2
    val curOy = baseOy

    /** 一次性提交：更新本地状态 + 立即写板子 */
    fun apply(
        m: Int = mode, x: Int = ox, y: Int = oy, x2: Int = ox2,
        s: Int = scale, c: Int = fg, o: Int = overlay,
    ) {
        val cm = DialOverlay.clampMode(m)
        val cs = DialOverlay.clampScale(s)
        val cf = DialOverlay.clampFg(c)
        val cx = DialOverlay.clampOx(cm, x)
        val cy = DialOverlay.clampOy(cm, y)
        val cx2 = DialOverlay.clampOx2(x2)
        mode = cm; ox = cx; oy = cy; ox2 = cx2; scale = cs; fg = cf; overlay = o
        baseOx = cx; baseOy = cy; baseOx2 = cx2
        accX = 0f; accY = 0f
        onApply(cm, cx, cy, cx2, cs, cf, o)
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Column {
                Text("调整叠加时钟", color = TextHi, fontSize = 17.sp)
                Text(
                    dial.name,
                    color = TextLow,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                )
            }
        },
        text = {
            Column {
                // ---------- 预览 + 拖拽 ----------
                BoxWithConstraints(
                    modifier = Modifier.fillMaxWidth(),
                    contentAlignment = Alignment.Center,
                ) {
                    val side = minOf(maxWidth, 264.dp)
                    OverlayPreview(
                        side = side,
                        preview = preview,
                        mode = mode, ox = curOx, oy = curOy, ox2 = curOx2, scale = scale,
                        dragTarget = dragTarget,
                        onDragStart = { px, py ->
                            dragTarget = when (mode) {
                                0 -> 0
                                else -> {
                                    val hit = DialOverlay.hitBlock(px, py, baseOx, baseOx2, baseOy)
                                    if (hit >= 0) hit + 1
                                    else DialOverlay.nearestBlock(px, baseOx, baseOx2) + 1
                                }
                            }
                            baseOx = ox; baseOy = oy; baseOx2 = ox2
                            accX = 0f; accY = 0f
                        },
                        onDrag = { dx, dy ->
                            accX += dx
                            accY += dy
                            when (dragTarget) {
                                0 -> {
                                    val bx = if (mode == 0 && baseOx < 0)
                                        DialOverlay.textX(DialOverlay.CENTER, scale) else baseOx
                                    ox = DialOverlay.clampOx(mode, bx + accX.toInt())
                                    oy = DialOverlay.clampOy(mode, baseOy + accY.toInt())
                                }
                                1 -> {
                                    ox = DialOverlay.clampOx(mode, baseOx + accX.toInt())
                                    oy = DialOverlay.clampOy(mode, baseOy + accY.toInt())
                                }
                                2 -> {
                                    ox2 = DialOverlay.clampOx2(baseOx2 + accX.toInt())
                                    oy = DialOverlay.clampOy(mode, baseOy + accY.toInt())
                                }
                            }
                        },
                        onDragEnd = { apply() },
                    )
                }

                Spacer(Modifier.height(8.dp))
                Text(
                    "在图上直接拖动时钟框 · 位置 x=$ox y=$oy" +
                        if (mode == 1) " · 分钟块 x=$ox2" else "",
                    color = TextLow,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                )

                Spacer(Modifier.height(10.dp))

                // ---------- 参数按钮 ----------
                OptionRow(
                    label = "样式",
                    options = listOf(0 to "经典文本", 1 to "方块数字"),
                    selected = mode,
                    onSelect = { v -> apply(m = v) },
                )
                Spacer(Modifier.height(6.dp))
                OptionRow(
                    label = "字号",
                    options = listOf(1 to "小", 2 to "大"),
                    selected = scale,
                    enabled = mode == 0,
                    onSelect = { v -> apply(s = v) },
                )
                Spacer(Modifier.height(6.dp))
                OptionRow(
                    label = "颜色",
                    options = listOf(0 to "白", 1 to "黑", 2 to "黄"),
                    selected = fg,
                    enabled = mode == 0,
                    onSelect = { v -> apply(c = v) },
                )
                Spacer(Modifier.height(6.dp))
                OptionRow(
                    label = "叠加",
                    options = listOf(1 to "显示", 0 to "隐藏"),
                    selected = overlay,
                    onSelect = { v -> apply(o = v) },
                )
                Spacer(Modifier.height(8.dp))

                Text(
                    "提示：方块数字会盖住底图烘焙的数字；经典文本带描边，浅色背景也看得清。",
                    color = TextLow,
                    fontSize = 10.sp,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { apply(); onDismiss() }) {
                Text("完成", color = Accent)
            }
        },
        dismissButton = {
            Row {
                TextButton(onClick = {
                    apply(
                        m = 0,
                        x = DialOverlay.CENTER,
                        y = DialOverlay.DEF_OY,
                        x2 = DialOverlay.DEF_OX2,
                        s = DialOverlay.DEF_SCALE,
                        c = DialOverlay.DEF_FG,
                        o = 1,
                    )
                }) { Text("恢复默认", color = TextMid) }
                TextButton(onClick = onDismiss) { Text("关闭", color = TextMid) }
            }
        },
        containerColor = Surface,
    )
}

// ---------------- 预览画布 ----------------

@Composable
private fun OverlayPreview(
    side: Dp,
    preview: DialPreview?,
    mode: Int, ox: Int, oy: Int, ox2: Int, scale: Int,
    dragTarget: Int,
    onDragStart: (Int, Int) -> Unit,
    onDrag: (Float, Float) -> Unit,
    onDragEnd: () -> Unit,
) {
    // 底图转 ImageBitmap（remember 缓存，避免拖动时反复创建）
    val bmp = remember(preview) {
        preview?.let {
            Bitmap.createBitmap(it.width, it.height, Bitmap.Config.ARGB_8888).apply {
                setPixels(it.pixels, 0, it.width, 0, 0, it.width, it.height)
            }.asImageBitmap()
        }
    }

    // 回调用 rememberUpdatedState 包住：手势协程不能被重组重启，
    // 所以 pointerInput 的 key 必须固定，否则拖动会中途断掉。
    val curStart by rememberUpdatedState(onDragStart)
    val curDrag by rememberUpdatedState(onDrag)
    val curEnd by rememberUpdatedState(onDragEnd)

    Box(
        modifier = Modifier
            .size(side)
            .clip(RoundedCornerShape(6.dp))
            .background(Color.Black)
            .border(1.dp, Border, RoundedCornerShape(6.dp)),
    ) {
        Canvas(
            modifier = Modifier
                .fillMaxSize()
                .pointerInput(Unit) {
                    detectDragGestures(
                        onDragStart = { pos ->
                            curStart(
                                DialOverlay.pxToPanelX(pos.x, size.width.toFloat()),
                                DialOverlay.pxToPanelY(pos.y, size.height.toFloat()),
                            )
                        },
                        onDrag = { change, delta ->
                            change.consume()
                            // 拖拽增量换算成面板像素（保持浮点，累积后再取整）
                            val dx = delta.x / size.width.toFloat() * DialOverlay.PANEL_W
                            val dy = delta.y / size.height.toFloat() * DialOverlay.PANEL_H
                            curDrag(dx, dy)
                        },
                        onDragEnd = { curEnd() },
                        onDragCancel = { curEnd() },
                    )
                },
        ) {
            val cw = size.width
            val ch = size.height

            // 底图
            bmp?.let {
                drawImage(
                    image = it,
                    dstSize = IntSize(cw.toInt(), ch.toInt()),
                )
            }

            // 64 格参考线（每 8 格一条）
            val grid = Color.White.copy(alpha = 0.10f)
            for (i in 8 until 64 step 8) {
                val gx = DialOverlay.panelToPxX(i, cw)
                drawLine(grid, Offset(gx, 0f), Offset(gx, ch), 1f)
                val gy = DialOverlay.panelToPxY(i, ch)
                drawLine(grid, Offset(0f, gy), Offset(cw, gy), 1f)
            }

            // 时钟框
            val boxColor = Color(0xFFFFB74D)
            val fill = boxColor.copy(alpha = 0.18f)
            val stroke = Stroke(width = 2f)

            if (mode == 0) {
                val w = DialOverlay.textWidth(scale)
                val h = DialOverlay.textHeight(scale)
                val tx = DialOverlay.textX(ox, scale)
                val ty = DialOverlay.textY(oy, scale)
                val px = DialOverlay.panelToPxX(tx, cw)
                val py = DialOverlay.panelToPxY(ty, ch)
                val pw = DialOverlay.panelToPxX(tx + w, cw) - px
                val ph = DialOverlay.panelToPxY(ty + h, ch) - py
                drawRect(fill, Offset(px, py), Size(pw, ph))
                drawRect(boxColor, Offset(px, py), Size(pw, ph), style = stroke)
            } else {
                listOf(ox to 1, ox2 to 2).forEach { (bx, which) ->
                    val px = DialOverlay.panelToPxX(bx, cw)
                    val py = DialOverlay.panelToPxY(oy, ch)
                    val pw = DialOverlay.panelToPxX(bx + DialOverlay.BLOCK, cw) - px
                    val ph = DialOverlay.panelToPxY(oy + DialOverlay.BLOCK, ch) - py
                    val c = if (dragTarget == which) Warn else boxColor
                    drawRect(c.copy(alpha = 0.18f), Offset(px, py), Size(pw, ph))
                    drawRect(c, Offset(px, py), Size(pw, ph), style = stroke)
                }
            }
        }
    }
}

// ---------------- 参数按钮组 ----------------

@Composable
private fun OptionRow(
    label: String,
    options: List<Pair<Int, String>>,
    selected: Int,
    enabled: Boolean = true,
    onSelect: (Int) -> Unit,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(label, color = if (enabled) TextMid else TextLow, fontSize = 12.sp)
        options.forEach { (v, text) ->
            val on = (v == selected)
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .background(if (on) AccentDim else SurfaceHi)
                    .border(1.dp, if (on) Accent else Border, RoundedCornerShape(6.dp))
                    .then(
                        if (enabled) Modifier.clickable { onSelect(v) } else Modifier
                    )
                    .padding(horizontal = 10.dp, vertical = 5.dp),
            ) {
                Text(
                    text,
                    color = if (!enabled) TextLow else if (on) TextHi else TextMid,
                    fontSize = 12.sp,
                    fontWeight = if (on) FontWeight.Bold else FontWeight.Normal,
                )
            }
        }
    }
}
