package com.ttqq.pixelclock.data

import android.content.Context
import androidx.core.content.edit

/** 本地偏好：上次连接的板子地址等 */
class Prefs(context: Context) {

    private val sp = context.getSharedPreferences("pixelclock", Context.MODE_PRIVATE)

    var lastHost: String
        get() = sp.getString(KEY_HOST, "") ?: ""
        set(v) = sp.edit { putString(KEY_HOST, v) }

    var lastBright: Int
        get() = sp.getInt(KEY_BRIGHT, 128)
        set(v) = sp.edit { putInt(KEY_BRIGHT, v) }

    var rotation: Int
        get() = sp.getInt(KEY_ROT, 0)
        set(v) = sp.edit { putInt(KEY_ROT, v) }

    var wifiSsid: String
        get() = sp.getString(KEY_SSID, "") ?: ""
        set(v) = sp.edit { putString(KEY_SSID, v) }

    /** 是否已看过首次引导 */
    var onboarded: Boolean
        get() = sp.getBoolean(KEY_ONBOARDED, false)
        set(v) = sp.edit { putBoolean(KEY_ONBOARDED, v) }

    private companion object {
        const val KEY_HOST = "host"
        const val KEY_BRIGHT = "bright"
        const val KEY_ROT = "rot"
        const val KEY_SSID = "ssid"
        const val KEY_ONBOARDED = "onboarded"
    }
}
