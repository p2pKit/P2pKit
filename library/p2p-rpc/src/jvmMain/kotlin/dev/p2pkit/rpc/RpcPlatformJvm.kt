package dev.p2pkit.rpc

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.core.security.JvmSecureIdentityStore
import dev.p2pkit.provisioning.desktop.jvm
import dev.p2pkit.transport.lan.lan

/** JVM 17 host/client with application-supplied protected identity storage; no insecure default. */
public fun RpcPlatform.Companion.jvm(identityStore: JvmSecureIdentityStore): RpcPlatform = RpcPlatform { settings ->
    P2pKit.create {
        settings.configure(this)
        jvmSecureIdentityStore(identityStore)
        transports { lan(settings.lan, settings.role) }
        networkProvisioning { jvm() }
    }
}
