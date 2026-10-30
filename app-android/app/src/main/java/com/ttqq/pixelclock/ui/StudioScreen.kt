package com.ttqq.pixelclock.ui

import android.content.Intent
import android.net.Uri
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import com.ttqq.pixelclock.net.StudioBridge

/**
 * 「像素工坊」页：把用户做的 HUB75 像素图片生成器（assets/studio.html）原样嵌进 APP。
 *
 * 网页负责：图片 → 限色 + Floyd–Steinberg 抖动 → 64×64 RGB565 多帧 → 分块重试推送。
 * APP 桥接负责：把“发往设备”那一层换成原生 HttpURLConnection（复用已连接的板子地址），
 * 既 100% 保留网页的像素算法，又不用在手机上手敲 IP、也不踩 WebView 的明文/CORS 坑。
 */
@Composable
fun StudioScreen(vm: MainViewModel, st: UiState) {
    val context = LocalContext.current

    val fileCallbackState = remember { androidx.compose.runtime.mutableStateOf<ValueCallback<Array<Uri>>?>(null) }
    val pickImage = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        fileCallbackState.value?.onReceiveValue(if (uri != null) arrayOf(uri) else null)
        fileCallbackState.value = null
    }

    val bridge = remember {
        StudioBridge(
            getHost = { vm.state.value.host },
            onOpenDevice = { url ->
                runCatching {
                    context.startActivity(
                        Intent(Intent.ACTION_VIEW, Uri.parse(url))
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                    )
                }
            },
        )
    }

    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { ctx ->
            WebView(ctx).apply {
                settings.apply {
                    javaScriptEnabled = true
                    domStorageEnabled = true
                    allowFileAccess = true
                    allowContentAccess = true
                    cacheMode = WebSettings.LOAD_NO_CACHE
                }
                addJavascriptInterface(bridge, "NativeBridge")

                webViewClient = object : WebViewClient() {
                    // 网页里点「打开设备网页」会尝试跳 http(s)，改到外部浏览器打开，避免在 WebView 内套娃。
                    override fun shouldOverrideUrlLoading(
                        view: WebView?,
                        request: android.webkit.WebResourceRequest,
                    ): Boolean {
                        val url = request.url.toString()
                        if (url.startsWith("http")) {
                            runCatching {
                                context.startActivity(
                                    Intent(Intent.ACTION_VIEW, Uri.parse(url))
                                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                                )
                            }
                            return true
                        }
                        return false
                    }
                }

                webChromeClient = object : WebChromeClient() {
                    override fun onShowFileChooser(
                        view: WebView?,
                        filePathCallback: ValueCallback<Array<Uri>>,
                        params: FileChooserParams?,
                    ): Boolean {
                        fileCallbackState.value?.onReceiveValue(null) // 取消上一次未完成的
                        fileCallbackState.value = filePathCallback
                        pickImage.launch("image/*")
                        return true
                    }
                }

                loadUrl("file:///android_asset/studio.html")
            }
        },
        onRelease = { it.destroy() },
    )

    DisposableEffect(Unit) {
        onDispose {
            fileCallbackState.value?.onReceiveValue(null)
            fileCallbackState.value = null
        }
    }
}
