package dev.p2pkit.core.internal

import dev.p2pkit.core.Platform

internal actual fun systemTimeMillis(): Long = System.currentTimeMillis()

internal actual fun currentPlatform(): Platform = Platform.ANDROID
