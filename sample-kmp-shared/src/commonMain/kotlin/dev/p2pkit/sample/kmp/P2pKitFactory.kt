package dev.p2pkit.sample.kmp

import dev.p2pkit.core.P2pKit

/**
 * Platform-agnostic factory for [P2pKit].
 *
 * Hides the only platform difference in v0.1: Android's LAN transport needs
 * a `Context`, JVM's does not. Each platform provides its own `actual`
 * implementation.
 *
 * Android consumers must call `initP2pKitAndroid(applicationContext)` from
 * their `Application.onCreate` before the first call to [createP2pKit].
 */
public expect fun createP2pKit(appId: String, deviceName: String): P2pKit
