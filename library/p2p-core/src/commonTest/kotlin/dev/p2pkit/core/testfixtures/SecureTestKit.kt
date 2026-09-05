package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.dsl.P2pKitBuilder
import dev.p2pkit.core.internal.DEFAULT_HANDSHAKE_TIMEOUT_MS
import dev.p2pkit.core.internal.SecureIdentityStorage
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair

/**
 * Authenticated-v2 kit fixture using the production builder and real platform cryptography.
 * [authorization] is required: tests must choose admission rather than silently accepting peers.
 * The synthetic [store] is in-memory, not evidence of platform secure persistence.
 *
 * Store invariants remain strict even after [block]; use [P2pKit.create] explicitly when testing
 * production warn-only behavior. Reconnect stays disabled unless requested. Long keepalive
 * intervals isolate lifecycle tests from incidental timer traffic, not from setup deadlines.
 *
 * Wrap fake endpoints in [CopyingRawConnection]: production consumes writes before returning,
 * whereas the default fake queues arrays by reference and secure writers wipe temporary buffers.
 * The caller owns kit.stop() and any supplied store/raw resources on every exit.
 */
internal fun createSecureTestKit(
    appId: AppId,
    name: String,
    store: SecureIdentityStorage = MemorySecureIdentityStorage(),
    transport: DataTransport,
    authorization: PeerAuthorizationPolicy,
    reconnect: ReconnectPolicy = ReconnectPolicy.Disabled,
    setupTimeoutMillis: Long = DEFAULT_HANDSHAKE_TIMEOUT_MS,
    block: P2pKitBuilder.() -> Unit = {}
): P2pKit = P2pKit.create {
    this.appId = appId
    deviceName = name
    secureIdentityStorage = store
    strictSessionInvariants = true
    sessionSetupTimeoutMillis = setupTimeoutMillis
    security { mode = SecurityMode.AuthenticatedV2(authorization) }
    lifecycle { reconnectPolicy = reconnect }
    keepAlive {
        pingIntervalMillis = 60_000
        timeoutMillis = 120_000
    }
    transports { register(SecureTestTransportFactory(transport)) }
    block()
    require(securityMode is SecurityMode.AuthenticatedV2) { "Secure fixture must remain authenticated v2" }
    require(strictSessionInvariants) { "Secure fixture must retain strict session invariants" }
}

/** Synthetic selected peer: no trusted discovery hint grants authorization. */
internal fun peerForSecureKit(kit: P2pKit): Peer = Peer(
    id = kit.localPeerId,
    name = kit.localDeviceName,
    platform = Platform.JVM_DESKTOP,
    supportedTransports = setOf(TransportKind.LAN)
)

/** Preserve the raw transport's write-ownership contract without replacing its read/lifecycle behavior. */
internal class CopyingRawConnection(private val delegate: RawConnection) : RawConnection by delegate {
    override suspend fun write(bytes: ByteArray) = delegate.write(bytes.copyOf())
}

private class SecureTestTransportFactory(private val transport: DataTransport) : TransportFactory {
    override val descriptor = TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair = TransportPair(transport)
}
