package dev.p2pkit.rpc

import android.content.Context
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.android.P2pKitAndroid
import dev.p2pkit.provisioning.android.android
import dev.p2pkit.transport.lan.lan

/** Android API 24+; Keystore-backed identity and explicit selected LAN Network. No hotspot orchestration. */
public fun RpcPlatform.Companion.android(context: Context): RpcPlatform {
    val application = context.applicationContext
    P2pKitAndroid.initialize(application)
    return RpcPlatform { settings ->
        P2pKit.create {
            settings.configure(this)
            transports { lan(application, settings.lan, settings.role) }
            networkProvisioning { android(application) }
        }
    }
}
