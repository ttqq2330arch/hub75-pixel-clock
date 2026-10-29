package com.ttqq.pixelclock.net

/**
 * 表盘缩略图解码。
 *
 * 固件 /dialpreview 返回首帧 8192 字节的 base64。
 * rgb565 格式：每像素 2 字节，小端，高 5 位红 / 中 6 位绿 / 低 5 位蓝。
 * 帧按行主序排列，每行 64 像素 → 每帧 128 字节，64 行 = 8192 字节。
 */
data class DialPreview(
    val width: Int,
    val height: Int,
    /** ARGB_8888 像素数组 */
    val pixels: IntArray,
) {
    companion object {
        const val FRAME_W = 64
        const val FRAME_H = 64
        const val FRAME_BYTES = FRAME_W * FRAME_H * 2   // 8192

        fun decode(b64: String): DialPreview {
            // 用 java.util.Base64（API 26+）而非 android.util.Base64，
            // 这样解码逻辑能在 JVM 单元测试里真跑。
            val raw = java.util.Base64.getMimeDecoder().decode(b64.trim())
            val px = IntArray(FRAME_W * FRAME_H)
            val n = minOf(raw.size, FRAME_BYTES)
            for (i in 0 until n step 2) {
                val lo = raw[i].toInt() and 0xFF
                val hi = raw[i + 1].toInt() and 0xFF
                val v = (hi shl 8) or lo
                val r = ((v shr 11) and 0x1F) shl 3
                val g = ((v shr 5) and 0x3F) shl 2
                val b = (v and 0x1F) shl 3
                val idx = i / 2
                if (idx < px.size) px[idx] = (0xFF shl 24) or (r shl 16) or (g shl 8) or b
            }
            return DialPreview(FRAME_W, FRAME_H, px)
        }
    }
}
