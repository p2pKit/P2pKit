package dev.p2pkit.rpc

import dev.p2pkit.core.P2pKit
import dev.p2pkit.transport.lan.iosManualIp
import dev.p2pkit.transport.lan.lan

/** iOS host/client with device-only Keychain identity. Hosting is foreground-first, not an OS background service. */
public fun RpcPlatform.Companion.ios(): RpcPlatform = RpcPlatform { settings ->
    P2pKit.create {
        settings.configure(this)
        transports { lan(settings.lan, settings.role) }
        networkProvisioning { iosManualIp() }
    }
}
