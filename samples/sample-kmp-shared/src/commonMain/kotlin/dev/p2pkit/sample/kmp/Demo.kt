package dev.p2pkit.sample.kmp

import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Self-contained demo flow exercising the core advertise → discover →
 * connect → send → close → stop path of P2pKit (not the full API surface —
 * no incoming-consumption/file-transfer/provisioning coverage). Useful
 * as a sanity smoke test from any platform: pass in a fresh [P2pKit], a name,
 * and the exact out-of-band fingerprint for the intended peer. The demo will
 * advertise, discover one peer, connect only to that fingerprint, send a
 * greeting, close the session, and stop the kit.
 *
 * Returns a short human-readable summary of what happened — easy to assert
 * against in a host-platform test, or log to the device screen.
 */
public suspend fun runDiscoverAndGreet(
    p2p: P2pKit,
    greetingFrom: String,
    expectedFingerprint: PeerFingerprint,
    discoveryTimeoutMillis: Long = 10_000
): String = runDiscoverAndGreetInternal(
    p2p = p2p,
    greetingFrom = greetingFrom,
    discoveryTimeoutMillis = discoveryTimeoutMillis,
    connect = { peer -> p2p.connect(peer, expectedFingerprint) }
)

/**
 * Deliberately unverified local smoke path. This exists only for a harness
 * that has explicitly opted into [ExplicitSecurityRisk] and selected
 * [PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp] at kit creation.
 * Production consumers must use [runDiscoverAndGreet] with an out-of-band
 * fingerprint instead.
 */
@ExplicitSecurityRisk
public suspend fun runUnverifiedDiscoverAndGreetForLocalTestingOnly(
    p2p: P2pKit,
    greetingFrom: String,
    discoveryTimeoutMillis: Long = 10_000
): String = runDiscoverAndGreetInternal(
    p2p = p2p,
    greetingFrom = greetingFrom,
    discoveryTimeoutMillis = discoveryTimeoutMillis,
    connect = p2p::connect
)

private suspend fun runDiscoverAndGreetInternal(
    p2p: P2pKit,
    greetingFrom: String,
    discoveryTimeoutMillis: Long,
    connect: suspend (Peer) -> P2pSession
): String {
    var session: P2pSession? = null
    try {
        p2p.startAdvertising()
        p2p.startDiscovery()

        val peer = withTimeoutOrNull(discoveryTimeoutMillis) {
            p2p.peers.first { it.isNotEmpty() }.first()
        } ?: return "no peer discovered within ${discoveryTimeoutMillis}ms"

        val connected = connect(peer)
        session = connected
        connected.send(P2pMessage.Text("hello from $greetingFrom"))
        return "sent greeting to ${peer.name} (${peer.id.value.take(8)}…)"
    } finally {
        // The demo owns the temporary advertise/discover lifecycle. Always
        // close a connected session and stop the kit, including timeout and
        // send-failure paths (SAMPLE-21).
        try {
            session?.close()
        } finally {
            p2p.stop()
        }
    }
}
