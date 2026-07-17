package dev.p2pkit.core.provisioning

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.TransportKind

/**
 * Internal-but-public hook that lets a [NetworkProvisioningManager]
 * inject a synthetic peer into the kit's discovery registry.
 *
 * The provisioning manager calls [registerManualPeer] from inside its
 * [NetworkProvisioningManager.createManualPeer] implementation. The returned
 * [Peer] is registered with the kit's `PeerRegistry` along with a transport
 * hint carrying [host] / [port], so a subsequent `kit.connect(peer)` call
 * resolves to the right [TransportKind] and reaches the right address.
 *
 * Marked [ExperimentalP2pApi]: the surface lives in `:p2p-core` because
 * separate Gradle modules (`:p2p-network-provisioning-{desktop,android}`)
 * need to consume it, but app code should generally not implement or even
 * touch this interface directly — call
 * [NetworkProvisioningManager.createManualPeer] instead.
 */
@ExperimentalP2pApi
public interface ManualPeerRegistrar {

    /**
     * Synthesize a [Peer] reachable at [host]:[port] via [kind] and register
     * it with the kit's discovery state so `kit.connect(peer)` resolves to
     * the right transport hint.
     *
     * **Lifetime (decision #6b, 2026-07-04):** a manual peer lives until the
     * kit stops — it is exempt from staleness eviction and there is no
     * unregister path in v1 (`kit.stop()` forgets it, along with the rest of
     * the in-memory registry). A removal API (`unregisterManualPeer`) is
     * deferred to the next deliberate spec revision.
     *
     * **Dedupe and name refresh (AUDIT-2026-07 (IDN-7)):** repeat
     * registrations of the same ([host], [port], [kind]) endpoint return the
     * same peer (same synthetic id, one registry entry). A re-registration
     * that supplies a different non-blank [deviceName] refreshes the stored
     * display name; a null/blank [deviceName] keeps the existing name.
     *
     * @param host  IP or hostname the transport can dial.
     * @param port  TCP/UDP port (TCP for [TransportKind.LAN]).
     * @param kind  Transport kind that should accept this hint. Defaults to LAN.
     * @param deviceName  Optional display name. If null, a placeholder
     *                    derived from `host:port` is used.
     */
    public fun registerManualPeer(
        host: String,
        port: Int,
        kind: TransportKind = TransportKind.LAN,
        deviceName: String? = null,
        expectedFingerprint: PeerFingerprint? = null
    ): Peer
}
