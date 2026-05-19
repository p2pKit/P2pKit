package dev.p2pkit.core.internal

import android.util.Log

internal actual fun nativeBuildInfoLog(line: String) {
    Log.i("p2pkit", "[buildInfo] $line")
}
