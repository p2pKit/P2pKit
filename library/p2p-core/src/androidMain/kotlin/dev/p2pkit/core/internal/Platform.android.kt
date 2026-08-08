package dev.p2pkit.core.internal

import dev.p2pkit.core.Platform

internal actual fun systemTimeMillis(): Long = System.currentTimeMillis()

internal actual fun monotonicTimeMillis(): Long = System.nanoTime() / 1_000_000L

internal actual fun currentPlatform(): Platform = Platform.ANDROID
