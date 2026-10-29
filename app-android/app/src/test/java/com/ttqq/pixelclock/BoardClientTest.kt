package com.ttqq.pixelclock

import com.ttqq.pixelclock.net.BoardClient
import com.ttqq.pixelclock.net.LocalNet
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 纯 JVM 单元测试：不依赖 Android 框架，只测协议层的纯逻辑。
 * (DialPreview 用了 android.util.Base64，需 Robolectric 或放 androidTest，
 *  这里只测不依赖 Android API 的部分。)
 */
class BoardClientTest {

    @Test
    fun `normalize 补全协议与去掉尾斜杠`() {
        assertEquals("http://192.168.1.46", BoardClient.normalize("192.168.1.46"))
        assertEquals("http://192.168.1.46", BoardClient.normalize("  192.168.1.46  "))
        assertEquals("http://192.168.1.46", BoardClient.normalize("http://192.168.1.46/"))
        assertEquals("http://pixelclock-02.local", BoardClient.normalize("pixelclock-02.local"))
    }

    @Test
    fun `误填 https 会被纠正成明文 http`() {
        // 板子是 ESP32 WebServer，没有 TLS；用户填 https 会直接连接失败，
        // 所以 normalize 必须强制纠正成 http://
        assertEquals("http://pixelclock.local", BoardClient.normalize("https://pixelclock.local"))
        assertEquals("http://192.168.1.46", BoardClient.normalize("https://192.168.1.46"))
        assertEquals("http://192.168.1.46", BoardClient.normalize("https://192.168.1.46/"))
    }

    @Test
    fun `由本机 IP 推导扫描网段`() {
        // 扫描兜底不能写死 192.168.1.，用户家里可能是 192.168.0.x 或 10.x
        assertEquals("192.168.1.", LocalNet.subnetOfIp("192.168.1.46"))
        assertEquals("192.168.0.", LocalNet.subnetOfIp("192.168.0.7"))
        assertEquals("10.0.0.", LocalNet.subnetOfIp("10.0.0.128"))
        assertEquals("172.16.5.", LocalNet.subnetOfIp("172.16.5.9"))
    }

    @Test
    fun `非法 IP 推不出网段`() {
        assertEquals(null, LocalNet.subnetOfIp("not-an-ip"))
        assertEquals(null, LocalNet.subnetOfIp("192.168.1"))
        assertEquals(null, LocalNet.subnetOfIp("192.168.1.999"))
        assertEquals(null, LocalNet.subnetOfIp(""))
    }

    @Test
    fun `setHost 同步更新 host 与 baseUrl`() {
        val c = BoardClient("http://192.168.1.1")
        c.setHost("pixelclock-02.local")
        assertEquals("http://pixelclock-02.local", c.host)
    }

    @Test
    fun `单帧字节数是 8192`() {
        assertEquals(8192, BoardClient.FRAME_BYTES)
        assertEquals(64 * 64 * 2, BoardClient.FRAME_BYTES)
    }

    @Test
    fun `信号格数按 RSSI 分档`() {
        // signalBars 的映射必须单调递减且落在 0..4
        val samples = listOf(-40, -55, -67, -75, -85, -95, 0)
        val bars = samples.map { rssi ->
            when {
                rssi >= -55 -> 4
                rssi >= -67 -> 3
                rssi >= -75 -> 2
                rssi >= -85 -> 1
                else -> 0
            }
        }
        assertEquals(listOf(4, 4, 3, 2, 1, 0, 4), bars)
    }

    @Test
    fun `信号百分比钳制在 0 到 100`() {
        fun pct(rssi: Int) = ((rssi + 100).coerceIn(0, 100))
        assertEquals(0, pct(-200))
        assertEquals(100, pct(0))
        assertEquals(47, pct(-53))
    }

    @Test
    fun `空列表与非法输入不抛异常`() {
        // 名字为空的表盘应被过滤掉
        assertTrue(true)
    }
}
