package dev.p2pkit.sample.kmp

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.transport.lan.lan

public actual fun createP2pKit(appId: String, deviceName: String): P2pKit =
    P2pKit.create {
        this.appId = AppId(appId)
        this.deviceName = deviceName
        transports { lan() }
    }
