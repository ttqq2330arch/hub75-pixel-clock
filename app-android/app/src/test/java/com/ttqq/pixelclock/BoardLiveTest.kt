package com.ttqq.pixelclock

import com.ttqq.pixelclock.net.BoardClient
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.util.Base64

/**
 * 真机联调测试（需要板子在线）。
 * 板子不在时自动跳过（assumeTrue），不会让 CI 失败。
 */
class BoardLiveTest {

    private val host = System.getProperty("board.host") ?: "192.168.1.46"

    private suspend fun online(): Boolean =
        runCatching {
            val c = BoardClient("http://$host")
            c.status().host.isNotEmpty()
        }.getOrDefault(false)

    @Test
    fun `读取板子状态`() = runBlocking {
        assumeTrue("板子不在线，跳过", online())
        val c = BoardClient("http://$host")
        val s = c.status()
        println("状态: ip=${s.ip} rssi=${s.rssi} host=${s.host} bright=${s.bright} rot=${s.rot}")
        assertTrue("IP 不应为空", s.ip.isNotEmpty())
        assertTrue("主机名不应为空", s.host.isNotEmpty())
        assertTrue("亮度应在 0..255", s.bright in 0..255)
        assertTrue("旋转角应在 0..3", s.rot in 0..3)
    }

    @Test
    fun `读取表盘库与缩略图`() = runBlocking {
        assumeTrue("板子不在线，跳过", online())
        val c = BoardClient("http://$host")
        val dials = c.dialList()
        println("表盘数: ${dials.size}")
        assertTrue("应至少有 1 个表盘", dials.isNotEmpty())
        val first = dials.first()
        val pv = c.dialPreview(first.name)
        assertTrue("缩略图应可解码", pv != null)
        println("表盘 '${first.name}' 缩略图 ${pv!!.width}x${pv!!.height}")
    }

    @Test
    fun `读取表盘商店 gzip 字典`() = runBlocking {
        assumeTrue("板子不在线，跳过", online())
        val c = BoardClient("http://$host")
        val faces = c.builtinFaces()
        println("商店表盘: ${faces.map { it.name }}")
        assertTrue("商店应有表盘", faces.isNotEmpty())
        // 预览应为 8192 字节的 base64（10924 字符）
        val b64 = faces.first().previewB64
        assertTrue("应带预览数据", !b64.isNullOrEmpty())
        val raw = Base64.getDecoder().decode(b64)
        assertEquals("预览应为 8192 字节", 8192, raw.size)
    }

    @Test
    fun `能力探测`() = runBlocking {
        assumeTrue("板子不在线，跳过", online())
        val c = BoardClient("http://$host")
        val cap = c.capabilities()
        println("能力: ${cap.summary}")
        assertTrue("v0.3.22+ 应支持旋转", cap.hasRotate)
    }
}
