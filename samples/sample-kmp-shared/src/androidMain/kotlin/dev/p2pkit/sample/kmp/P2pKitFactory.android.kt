package dev.p2pkit.sample.kmp

import android.content.Context
import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.android.P2pKitAndroid
import dev.p2pkit.transport.lan.lan

@Volatile
private var applicationContext: Context? = null

/**
 * Must be called once from [android.app.Application.onCreate] (or any other
 * place that runs before the first `createP2pKit`). Pass any [Context]; only
 * `applicationContext` is retained.
 */
public fun initP2pKitAndroid(context: Context) {
    val app = context.applicationContext
    applicationContext = app
    // Required for persistent PeerId on Android: without this the kit falls
    // back to in-memory storage and the device gets a new identity every
    // process launch. The documented KMP setup pattern promised this call but
    // never made it (AUDIT-2026-06 fix).
    P2pKitAndroid.initialize(app)
}

public actual fun createP2pKit(
    appId: String,
    deviceName: String,
    authorization: PeerAuthorizationPolicy
): P2pKit {
    val ctx = applicationContext
        ?: error("Call initP2pKitAndroid(applicationContext) from Application.onCreate() first.")
    return P2pKit.create {
        this.appId = AppId(appId)
        this.deviceName = deviceName
        security {
            mode = SecurityMode.AuthenticatedV2(authorization)
        }
        transports { lan(ctx) }
    }
}
