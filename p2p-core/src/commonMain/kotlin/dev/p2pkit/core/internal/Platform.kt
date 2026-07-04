package dev.p2pkit.core.internal

import dev.p2pkit.core.Platform

/** Epoch-millis clock. Tests inject fakes; production uses the platform clock. */
internal expect fun systemTimeMillis(): Long

/** Identity of the platform the SDK is running on. */
internal expect fun currentPlatform(): Platform
