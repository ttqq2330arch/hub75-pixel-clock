package com.ttqq.pixelclock

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ttqq.pixelclock.ui.Bg
import com.ttqq.pixelclock.ui.MainViewModel
import com.ttqq.pixelclock.ui.PixelClockApp
import com.ttqq.pixelclock.ui.theme.PixelClockTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            PixelClockTheme {
                val vm: MainViewModel = viewModel()
                val st by vm.state.collectAsState()
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Bg,
                ) {
                    PixelClockApp(vm, st)
                }
            }
        }
    }
}
