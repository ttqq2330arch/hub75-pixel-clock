package com.ttqq.pixelclock.net

/**
 * 叠加时钟的几何与坐标逻辑（纯函数，无 Android 依赖，可 JVM 单测）。
 *
 * 对应固件 `src/face_remote.cpp` 的绘制逻辑 + `src/net.cpp` 的 `clampOv()`。
 * **任何改动都必须与固件保持一致**，否则 APP 里看着对、板子上不是那个位置。
 *
 * ── 两种模式 ──
 *  - mode 0「经典」：5x7 点阵字体画 "HH:MM"，整体一个文本框
 *      宽度 = 字符数 * 6 * scale - scale = 5*6*scale - scale
 *             scale2 → 58，scale1 → 29
 *      高度 = 7 * scale            scale2 → 14，scale1 → 7
 *      ox = -1 表示水平居中（实际 x = (64 - w) / 2）
 *      绘制时带 1px 反色描边（x-1 起，w+2 宽），任何背景下都可读
 *  - mode 1「方块」：两��� 19x19 的数字块（小时块 ox，分钟块 ox2，共用 y = oy）
 *      块内是 7x7 马里奥字体，会盖住底图烘焙的数字并填块体色
 *
 * ── 固件钳制范围（clampOv）──
 *  mode0: ox ∈ [-1, 64]，oy ∈ [0, 50]
 *  mode1: ox ∈ [0, 45]，ox2 ∈ [0, 45]，oy ∈ [0, 45]
 *  scale ∈ [1, 2]，fg ∈ [0, 2]
 */
object DialOverlay {

    const val PANEL_W = 64
    const val PANEL_H = 64

    /** mode0 文本框宽度（固件 Pix::textWidth，5 个字符 "HH:MM"） */
    const val TEXT_W_SCALE1 = 29
    const val TEXT_W_SCALE2 = 58
    const val TEXT_H_SCALE1 = 7
    const val TEXT_H_SCALE2 = 14

    /** mode1 数字块边长 */
    const val BLOCK = 19

    /** mode0 居中标志：ox = -1 */
    const val CENTER = -1

    /** 默认值（固件 setOvDefaults / DialMeta 初始值） */
    const val DEF_OY = 46
    const val DEF_OX2 = 34
    const val DEF_SCALE = 2
    const val DEF_FG = 0

    // ---------------- 尺寸 ----------------

    /** mode0 文本框宽（不含描边） */
    fun textWidth(scale: Int): Int =
        if (scale >= 2) TEXT_W_SCALE2 else TEXT_W_SCALE1

    /** mode0 文本框高（不含描边） */
    fun textHeight(scale: Int): Int =
        if (scale >= 2) TEXT_H_SCALE2 else TEXT_H_SCALE1

    // ---------------- 位置换算 ----------------

    /**
     * mode0 文本框左上角实际 X。
     * ox = -1 → 居中；否则用 ox。再按固件逻辑做越界回收。
     */
    fun textX(ox: Int, scale: Int): Int {
        val w = textWidth(scale)
        var x = if (ox >= 0) ox else (PANEL_W - w) / 2
        if (x < 0) x = 0
        if (x + w > PANEL_W) x = PANEL_W - w
        return x
    }

    /** mode0 文本框实际 Y（越界往上收） */
    fun textY(oy: Int, scale: Int): Int {
        var y = oy
        if (y < 0) y = 0
        if (y + 7 * scale > PANEL_H) y = PANEL_H - 7 * scale
        return y
    }

    // ---------------- 钳制（对齐固件 clampOv） ----------------

    fun clampMode(mode: Int): Int = if (mode == 0) 0 else 1

    /** 钳制 X（mode0 允许 -1 居中；mode1 是块 X） */
    fun clampOx(mode: Int, ox: Int): Int = when (mode) {
        0 -> ox.coerceIn(CENTER, 64)
        else -> ox.coerceIn(0, 45)
    }

    /** 钳制 Y */
    fun clampOy(mode: Int, oy: Int): Int = when (mode) {
        0 -> oy.coerceIn(0, 50)
        else -> oy.coerceIn(0, 45)
    }

    /** 钳制分钟块 X（仅 mode1 用） */
    fun clampOx2(ox2: Int): Int = ox2.coerceIn(0, 45)

    /** 钳制字号 */
    fun clampScale(scale: Int): Int = scale.coerceIn(1, 2)

    /** 钳制前景色 0=白 1=黑 2=黄 */
    fun clampFg(fg: Int): Int = fg.coerceIn(0, 2)

    // ---------------- 缩略图 ↔ 面板坐标 ----------------

    /**
     * 预览画布上的像素坐标 → 64 面板坐标。
     * @param px 预览画布内的像素 X
     * @param canvasWidthPx 预览画布宽度（像素）
     */
    fun pxToPanelX(px: Float, canvasWidthPx: Float): Int {
        if (canvasWidthPx <= 0f) return 0
        val v = (px / canvasWidthPx * PANEL_W).toInt()
        return v.coerceIn(0, PANEL_W - 1)
    }

    /** 预览画布上的像素 Y → 64 面板坐标 */
    fun pxToPanelY(py: Float, canvasHeightPx: Float): Int {
        if (canvasHeightPx <= 0f) return 0
        val v = (py / canvasHeightPx * PANEL_H).toInt()
        return v.coerceIn(0, PANEL_H - 1)
    }

    /** 64 面板坐标 → 预览画布像素 X */
    fun panelToPxX(panelX: Int, canvasWidthPx: Float): Float =
        if (canvasWidthPx <= 0f) 0f else panelX.toFloat() / PANEL_W * canvasWidthPx

    /** 64 面板坐标 → 预览画布像素 Y */
    fun panelToPxY(panelY: Int, canvasHeightPx: Float): Float =
        if (canvasHeightPx <= 0f) 0f else panelY.toFloat() / PANEL_H * canvasHeightPx

    // ---------------- 命中检测 ----------------

    /**
     * mode1 双块：拖拽起点落在哪个块上？
     * @return 0 = 小时块，1 = 分钟块，-1 = 都没命中（交给调用方选最近的）
     */
    fun hitBlock(
        panelX: Int, panelY: Int,
        ox: Int, ox2: Int, oy: Int,
    ): Int {
        if (panelY < oy || panelY >= oy + BLOCK) return -1
        if (panelX >= ox && panelX < ox + BLOCK) return 0
        if (panelX >= ox2 && panelX < ox2 + BLOCK) return 1
        return -1
    }

    /** mode1 两个块都没命中时，选离拖拽点更近的那个 */
    fun nearestBlock(panelX: Int, ox: Int, ox2: Int): Int {
        val d1 = kotlin.math.abs(panelX - (ox + BLOCK / 2))
        val d2 = kotlin.math.abs(panelX - (ox2 + BLOCK / 2))
        return if (d1 <= d2) 0 else 1
    }

    // ---------------- 预设 ----------------

    /** 名称 → 中文说明，给 UI 用 */
    fun modeName(mode: Int): String = if (mode == 0) "经典文本" else "方块数字"

    /** 颜色索引 → 中文 */
    fun fgName(fg: Int): String = when (fg) {
        1 -> "黑"
        2 -> "黄"
        else -> "白"
    }
}
