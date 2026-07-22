package dev.p2pkit.sample.kmp

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Self-contained demo flow exercising the core advertise → discover →
 * connect → send → close → stop path of P2pKit (not the full API surface —
 * no incoming-consumption/file-transfer/provisioning coverage). Useful
 * as a sanity smoke test from any platform: pass in a fresh [P2pKit] and a
 * name and the demo will advertise, discover one peer, connect, send a
 * greeting, close the session, and stop the kit.
 *
 * Returns a short human-readable summary of what happened — easy to assert
 * against in a host-platform test, or log to the device screen.
 */
public suspend fun runDiscoverAndGreet(
    p2p: P2pKit,
    greetingFrom: String,
    discoveryTimeoutMillis: Long = 10_000
): String {
    var session: P2pSession? = null
    try {
        p2p.startAdvertising()
        p2p.startDiscovery()

        val peer = withTimeoutOrNull(discoveryTimeoutMillis) {
            p2p.peers.first { it.isNotEmpty() }.first()
        } ?: return "no peer discovered within ${discoveryTimeoutMillis}ms"

        val connected = p2p.connect(peer)
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
