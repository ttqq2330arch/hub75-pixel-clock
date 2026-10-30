package com.ttqq.pixelclock

import com.ttqq.pixelclock.net.DialOverlay
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 叠加时钟几何逻辑单测。
 *
 * 这些数值必须与固件严格一致：
 *   - 文本宽度：src/font5x7.h 的 textWidth() = 字符数 * 6 * scale - scale
 *   - 方块边长：src/face_remote.cpp 的 kBlockSize = 19
 *   - 钳制范围：src/net.cpp 的 clampOv()
 * 任何一个对不上，APP 里拖出来的位置就和板子上实际显示的不一样。
 */
class DialOverlayTest {

    @Test
    fun `经典文本框尺寸与固件 textWidth 一致`() {
        // "HH:MM" 5 个字符 → 5*6*scale - scale
        assertEquals(58, DialOverlay.textWidth(2))
        assertEquals(29, DialOverlay.textWidth(1))
        assertEquals(14, DialOverlay.textHeight(2))
        assertEquals(7, DialOverlay.textHeight(1))
    }

    @Test
    fun `ox 为 -1 时水平居中`() {
        // (64 - 58) / 2 = 3
        assertEquals(3, DialOverlay.textX(DialOverlay.CENTER, 2))
        // (64 - 29) / 2 = 17
        assertEquals(17, DialOverlay.textX(DialOverlay.CENTER, 1))
    }

    @Test
    fun `指定 ox 时用指定值`() {
        assertEquals(0, DialOverlay.textX(0, 2))
        // x=20 放不下 58px 宽的框（20+58=78 > 64），固件会往回收到 64-58=6
        assertEquals(6, DialOverlay.textX(20, 2))
        // scale1 时 29px 宽，x=20 放得下
        assertEquals(20, DialOverlay.textX(20, 1))
    }

    @Test
    fun `文本框越界时回收进面板`() {
        // x + w > 64 → x = 64 - w
        assertEquals(6, DialOverlay.textX(60, 2))
        // y + 7*scale > 64 → y = 64 - 7*scale
        assertEquals(50, DialOverlay.textY(60, 2))
        assertEquals(57, DialOverlay.textY(60, 1))
        // 负数归零
        assertEquals(0, DialOverlay.textY(-5, 2))
    }

    @Test
    fun `钳制范围与固件 clampOv 一致`() {
        // mode0：ox 允许 -1（居中）到 64
        assertEquals(-1, DialOverlay.clampOx(0, -5))
        assertEquals(64, DialOverlay.clampOx(0, 99))
        assertEquals(30, DialOverlay.clampOx(0, 30))
        // mode1：ox 是块 X，范围 0..45
        assertEquals(0, DialOverlay.clampOx(1, -5))
        assertEquals(45, DialOverlay.clampOx(1, 99))

        // oy：mode0 0..50，mode1 0..45
        assertEquals(0, DialOverlay.clampOy(0, -1))
        assertEquals(50, DialOverlay.clampOy(0, 99))
        assertEquals(45, DialOverlay.clampOy(1, 99))

        // 分钟块 X 0..45
        assertEquals(0, DialOverlay.clampOx2(-3))
        assertEquals(45, DialOverlay.clampOx2(99))

        // 字号 1..2，颜色 0..2
        assertEquals(1, DialOverlay.clampScale(0))
        assertEquals(2, DialOverlay.clampScale(5))
        assertEquals(0, DialOverlay.clampFg(-1))
        assertEquals(2, DialOverlay.clampFg(7))
    }

    @Test
    fun `模式只有经典和方块两种`() {
        assertEquals(0, DialOverlay.clampMode(0))
        assertEquals(1, DialOverlay.clampMode(1))
        assertEquals(1, DialOverlay.clampMode(9))
    }

    @Test
    fun `面板坐标与预览像素坐标互逆`() {
        val canvas = 256f
        for (panel in 0 until 64) {
            val px = DialOverlay.panelToPxX(panel, canvas)
            assertEquals("X 往返 panel=$panel", panel, DialOverlay.pxToPanelX(px, canvas))
            val py = DialOverlay.panelToPxY(panel, canvas)
            assertEquals("Y 往返 panel=$panel", panel, DialOverlay.pxToPanelY(py, canvas))
        }
    }

    @Test
    fun `预览坐标超出画布时被钳制`() {
        assertEquals(0, DialOverlay.pxToPanelX(-50f, 256f))
        assertEquals(63, DialOverlay.pxToPanelX(9999f, 256f))
        assertEquals(0, DialOverlay.pxToPanelY(-50f, 256f))
        assertEquals(63, DialOverlay.pxToPanelY(9999f, 256f))
        // 画布尺寸为 0 时不崩
        assertEquals(0, DialOverlay.pxToPanelX(10f, 0f))
        assertEquals(0f, DialOverlay.panelToPxX(10, 0f))
    }

    @Test
    fun `方块命中检测区分小时块和分钟块`() {
        // ox=10 小时块，ox2=40 分钟块，oy=20，块 19x19
        assertEquals(0, DialOverlay.hitBlock(12, 25, 10, 40, 20))
        assertEquals(1, DialOverlay.hitBlock(42, 25, 10, 40, 20))
        // Y 不在块内
        assertEquals(-1, DialOverlay.hitBlock(12, 5, 10, 40, 20))
        // X 在两个块之间
        assertEquals(-1, DialOverlay.hitBlock(30, 25, 10, 40, 20))
    }

    @Test
    fun `没命中时选最近的块`() {
        // 靠近小时块
        assertEquals(0, DialOverlay.nearestBlock(12, 10, 40))
        // 靠近分钟块
        assertEquals(1, DialOverlay.nearestBlock(42, 10, 40))
        // 正中间偏向哪边取决于距离
        assertTrue(DialOverlay.nearestBlock(25, 10, 40) in 0..1)
    }

    @Test
    fun `默认参数与固件一致`() {
        assertEquals(-1, DialOverlay.CENTER)
        assertEquals(46, DialOverlay.DEF_OY)
        assertEquals(34, DialOverlay.DEF_OX2)
        assertEquals(2, DialOverlay.DEF_SCALE)
        assertEquals(0, DialOverlay.DEF_FG)
        assertEquals(19, DialOverlay.BLOCK)
    }
}
