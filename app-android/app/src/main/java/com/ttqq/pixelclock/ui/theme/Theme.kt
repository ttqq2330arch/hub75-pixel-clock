package com.ttqq.pixelclock.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import com.ttqq.pixelclock.ui.Accent
import com.ttqq.pixelclock.ui.Bg
import com.ttqq.pixelclock.ui.Border
import com.ttqq.pixelclock.ui.Surface
import com.ttqq.pixelclock.ui.TextHi
import com.ttqq.pixelclock.ui.TextLow
import com.ttqq.pixelclock.ui.TextMid

private val DarkScheme = darkColorScheme(
    primary = Accent,
    onPrimary = Color.Black,
    secondary = Accent,
    background = Bg,
    onBackground = TextHi,
    surface = Surface,
    onSurface = TextHi,
    surfaceVariant = Surface,
    onSurfaceVariant = TextMid,
    outline = Border,
    error = Color(0xFFEF5350),
)

@Composable
fun PixelClockTheme(content: @Composable () -> Unit) {
    // 强制深色：这是放在桌面的像素风设备，浅色主题不搭
    @Suppress("UNUSED_EXPRESSION")
    isSystemInDarkTheme()
    MaterialTheme(colorScheme = DarkScheme, content = content)
}
