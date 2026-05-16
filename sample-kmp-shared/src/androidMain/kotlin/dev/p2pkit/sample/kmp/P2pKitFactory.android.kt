package dev.p2pkit.sample.kmp

import android.content.Context
import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.transport.lan.lan

@Volatile
private var applicationContext: Context? = null

/**
 * Must be called once from [android.app.Application.onCreate] (or any other
 * place that runs before the first `createP2pKit`). Pass any [Context]; only
 * `applicationContext` is retained.
 */
public fun initP2pKitAndroid(context: Context) {
    applicationContext = context.applicationContext
}

public actual fun createP2pKit(appId: String, deviceName: String): P2pKit {
    val ctx = applicationContext
        ?: error("Call initP2pKitAndroid(applicationContext) from Application.onCreate() first.")
    return P2pKit.create {
        this.appId = AppId(appId)
        this.deviceName = deviceName
        transports { lan(ctx) }
    }
}
