package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair

/** Process-local discovery callback delivery; compiled only into JVM tests. */
internal class JvmDeterministicDiscoveryTestBackend : JvmTestDiscoveryBackend {
    private data class Subscriber(
        val resolved: (JvmTestDiscoveryAdvertisement) -> Unit,
        val removed: (String) -> Unit
    )

    private val lock = Any()
    private val advertisements = linkedMapOf<String, JvmTestDiscoveryAdvertisement>()
    private val subscribers = linkedMapOf<PeerId, Subscriber>()

    override fun advertise(advertisement: JvmTestDiscoveryAdvertisement) {
        val listeners = synchronized(lock) {
            advertisements[advertisement.instanceName] = advertisement
            subscribers.values.toList()
        }
        listeners.forEach { it.resolved(advertisement) }
    }

    override fun withdraw(instanceName: String) {
        val listeners = synchronized(lock) {
            if (advertisements.remove(instanceName) == null) return
            subscribers.values.toList()
        }
        listeners.forEach { it.removed(instanceName) }
    }

    override fun subscribe(
        localPeerId: PeerId,
        resolved: (JvmTestDiscoveryAdvertisement) -> Unit,
        removed: (String) -> Unit
    ) {
        val existing = synchronized(lock) {
            subscribers[localPeerId] = Subscriber(resolved, removed)
            advertisements.values.toList()
        }
        existing.forEach(resolved)
    }

    override fun unsubscribe(localPeerId: PeerId) {
        synchronized(lock) { subscribers.remove(localPeerId) }
    }

    override fun refresh(localPeerId: PeerId) {
        val snapshot = synchronized(lock) {
            val subscriber = subscribers[localPeerId] ?: return
            subscriber to advertisements.values.toList()
        }
        snapshot.second.forEach(snapshot.first.resolved)
    }
}

/** Real JVM LAN data transport plus deterministic test-only discovery. */
internal class JvmDeterministicLanTestFactory(
    private val discoveryBackend: JvmTestDiscoveryBackend
) : TransportFactory {
    override val descriptor: TransportDescriptor =
        TransportDescriptor.dataAndDiscovery(TransportKind.LAN)

    override fun build(context: TransportContext): TransportPair {
        val registration = LanServiceRegistration(
            appId = context.appId,
            localPeerId = context.localPeerId,
            deviceName = context.deviceName,
            platform = context.platform,
            securityProfile = context.securityProfile,
            fingerprint = context.localFingerprint
        )
        return TransportPair(
            data = JvmLanDataTransport(registration),
            discovery = JvmLanDiscoveryTransport(registration, discoveryBackend)
        )
    }
}
