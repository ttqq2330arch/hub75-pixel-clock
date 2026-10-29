package com.ttqq.pixelclock.ui

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ttqq.pixelclock.net.DialPreview

// ---------- 通用卡片 ----------

@Composable
fun Card(
    title: String,
    subtitle: String? = null,
    modifier: Modifier = Modifier,
    trailing: @Composable (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Surface),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(title, color = TextHi, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                    if (subtitle != null) {
                        Text(subtitle, color = TextLow, fontSize = 12.sp)
                    }
                }
                trailing?.invoke()
            }
            Spacer(Modifier.height(12.dp))
            content()
        }
    }
}

// ---------- 状态行 ----------

@Composable
fun StatusRow(
    label: String,
    value: String,
    valueColor: Color = TextHi,
    mono: Boolean = false,
) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, color = TextMid, fontSize = 13.sp, modifier = Modifier.width(72.dp))
        Text(
            value,
            color = valueColor,
            fontSize = 13.sp,
            fontWeight = if (mono) FontWeight.Medium else FontWeight.Normal,
            fontFamily = if (mono) androidx.compose.ui.text.font.FontFamily.Monospace else null,
        )
    }
}

// ---------- 信号格 ----------

@Composable
fun SignalBars(bars: Int, modifier: Modifier = Modifier) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(2.dp), verticalAlignment = Alignment.Bottom) {
        for (i in 0 until 4) {
            val h = (5 + i * 4).dp
            Box(
                Modifier
                    .width(4.dp)
                    .height(h)
                    .clip(RoundedCornerShape(1.dp))
                    .background(if (i < bars) Good else Border)
            )
        }
    }
}

// ---------- 亮度滑块 ----------

@Composable
fun BrightnessSlider(
    value: Int,
    onChange: (Int) -> Unit,
    onCommit: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier) {
        Slider(
            value = value.toFloat(),
            onValueChange = { onChange(it.toInt()) },
            onValueChangeFinished = { onCommit(value) },
            valueRange = 0f..255f,
            colors = SliderDefaults.colors(
                thumbColor = Accent,
                activeTrackColor = Accent,
                inactiveTrackColor = Border,
            ),
        )
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            listOf(0, 30, 60, 100, 200, 255).forEach { p ->
                Text(
                    "$p",
                    color = TextLow,
                    fontSize = 11.sp,
                    modifier = Modifier.clickable { onCommit(p) }.padding(horizontal = 2.dp),
                )
            }
        }
    }
}

/** 把固件返回的 base64 缩略图解成可绘制对象 */
@Composable
fun rememberPreview(b64: String?): DialPreview? {
    return remember(b64) {
        if (b64.isNullOrEmpty()) null
        else runCatching {
            DialPreview.decode(b64)
        }.getOrNull()
    }
}

/** 非 Composable 版本，供 ViewModel/回调使用 */
fun decodePreview(b64: String?): DialPreview? {
    if (b64.isNullOrEmpty()) return null
    return runCatching { DialPreview.decode(b64) }.getOrNull()
}

// ---------- 表盘缩略图 ----------

@Composable
fun DialThumb(
    preview: DialPreview?,
    size: Int = 96,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier
            .size(size.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(Color.Black),
        contentAlignment = Alignment.Center,
    ) {
        if (preview == null) {
            Text("…", color = TextLow, fontSize = 12.sp)
        } else {
            val bmp = Bitmap.createBitmap(preview.width, preview.height, Bitmap.Config.ARGB_8888)
            bmp.setPixels(preview.pixels, 0, preview.width, 0, 0, preview.width, preview.height)
            Image(
                bmp.asImageBitmap(),
                contentDescription = null,
                modifier = Modifier.fillMaxSize().padding(2.dp),
            )
        }
    }
}

// ---------- 空态 / 加载 ----------

@Composable
fun EmptyState(text: String, modifier: Modifier = Modifier) {
    Box(
        modifier.fillMaxWidth().padding(vertical = 32.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, color = TextLow, fontSize = 13.sp, textAlign = TextAlign.Center)
    }
}

@Composable
fun LoadingRow(text: String, modifier: Modifier = Modifier) {
    Row(
        modifier.fillMaxWidth().padding(vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        CircularProgressIndicator(
            modifier = Modifier.size(18.dp),
            color = Accent,
            strokeWidth = 2.dp,
        )
        Spacer(Modifier.width(10.dp))
        Text(text, color = TextMid, fontSize = 13.sp)
    }
}

@Composable
fun UploadProgressBar(sent: Long, total: Long, modifier: Modifier = Modifier) {
    val pct = if (total > 0) (sent.toFloat() / total).coerceIn(0f, 1f) else 0f
    Column(modifier) {
        LinearProgressIndicator(
            progress = { pct },
            modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)),
            color = Accent,
            trackColor = Border,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            "推送中 ${(pct * 100).toInt()}%  (${sent / 1024}KB / ${total / 1024}KB)",
            color = TextMid,
            fontSize = 11.sp,
        )
    }
}
