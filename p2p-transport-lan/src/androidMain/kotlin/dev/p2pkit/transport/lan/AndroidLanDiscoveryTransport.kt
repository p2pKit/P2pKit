package dev.p2pkit.transport.lan

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportHint
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * [DiscoveryTransport] backed by Android's [NsdManager].
 *
 * NsdManager's API is callback-based; this class wraps it in coroutine-friendly
 * primitives. Resolution of discovered services is sequential because some
 * Android API levels reject concurrent `resolveService` calls.
 *
 * Wi-Fi multicast lock: incoming mDNS multicast packets (224.0.0.251:5353) are
 * dropped by Android's Wi-Fi power-save firmware unless an app explicitly holds
 * a [WifiManager.MulticastLock]. The `CHANGE_WIFI_MULTICAST_STATE` permission
 * only **allows** acquiring the lock; the lock itself must also be held. Without
 * it, this transport can advertise (outgoing multicast works) but cannot
 * **receive** other peers' advertisements. The lock is acquired on first
 * start (advertise or discover, whichever comes first) and released when both
 * have stopped.
 */
internal class AndroidLanDiscoveryTransport(
    private val context: Context,
    private val registration: LanServiceRegistration
) : DiscoveryTransport {

    override val type: TransportKind = TransportKind.LAN

    private val _events = MutableSharedFlow<PeerEvent>(
        replay = 0,
        extraBufferCapacity = 256,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    override val events: Flow<PeerEvent> = _events.asSharedFlow()

    private val lock = Mutex()
    private val nsd: NsdManager =
        context.applicationContext.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val wifi: WifiManager? =
        context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager

    private var registrationListener: NsdManager.RegistrationListener? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var multicastLock: WifiManager.MulticastLock? = null

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) = lock.withLock {
        if (registrationListener != null) return@withLock

        acquireMulticastLockIfNeeded()

        val info = NsdServiceInfo().apply {
            serviceName = registration.localPeerId.value
            serviceType = LanConstants.SERVICE_TYPE_NSD
            port = registration.tcpPort
            setAttribute(LanConstants.TXT_PEER_ID, registration.localPeerId.value)
            setAttribute(LanConstants.TXT_APP_ID, registration.appId.value)
            setAttribute(LanConstants.TXT_DEVICE_NAME, localPeer.deviceName)
            setAttribute(LanConstants.TXT_PLATFORM, localPeer.platform.name)
            setAttribute(
                LanConstants.TXT_CAPABILITIES,
                localPeer.supportedTransports.joinToString(",") { it.name }
            )
            setAttribute(LanConstants.TXT_PROTOCOL_VERSION, LanConstants.PROTOCOL_VERSION.toString())
        }

        val registered = CompletableDeferred<Unit>()
        val listener = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(serviceInfo: NsdServiceInfo) {
                registered.complete(Unit)
            }

            override fun onRegistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                registered.completeExceptionally(
                    IllegalStateException("NsdManager registration failed: errorCode=$errorCode")
                )
            }

            override fun onServiceUnregistered(serviceInfo: NsdServiceInfo) = Unit
            override fun onUnregistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) = Unit
        }
        nsd.registerService(info, NsdManager.PROTOCOL_DNS_SD, listener)
        registrationListener = listener
        // Wait for confirmation so callers know we're really advertising.
        registered.await()
    }

    override suspend fun stopAdvertising() = lock.withLock {
        val listener = registrationListener ?: return@withLock
        runCatching { nsd.unregisterService(listener) }
        registrationListener = null
        releaseMulticastLockIfIdle()
    }

    override suspend fun startDiscovery() = lock.withLock {
        if (discoveryListener != null) return@withLock

        acquireMulticastLockIfNeeded()

        val listener = object : NsdManager.DiscoveryListener {
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) = Unit
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) = Unit
            override fun onDiscoveryStarted(serviceType: String) = Unit
            override fun onDiscoveryStopped(serviceType: String) = Unit

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                // Skip self by name before paying for resolution.
                if (serviceInfo.serviceName == registration.localPeerId.value) return
                resolve(serviceInfo)
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                // We don't get TXT records on lost; the service name is our PeerId.
                val pid = serviceInfo.serviceName ?: return
                if (pid == registration.localPeerId.value) return
                _events.tryEmit(PeerEvent.Lost(PeerId(pid)))
            }
        }
        nsd.discoverServices(
            LanConstants.SERVICE_TYPE_NSD,
            NsdManager.PROTOCOL_DNS_SD,
            listener
        )
        discoveryListener = listener
    }

    override suspend fun stopDiscovery() = lock.withLock {
        val listener = discoveryListener ?: return@withLock
        runCatching { nsd.stopServiceDiscovery(listener) }
        discoveryListener = null
        releaseMulticastLockIfIdle()
    }

    private fun acquireMulticastLockIfNeeded() {
        if (multicastLock != null) return
        val wm = wifi ?: return
        val lock = wm.createMulticastLock("p2pkit-mdns").apply {
            setReferenceCounted(false)
            acquire()
        }
        multicastLock = lock
    }

    private fun releaseMulticastLockIfIdle() {
        if (registrationListener != null || discoveryListener != null) return
        val held = multicastLock ?: return
        multicastLock = null
        runCatching { if (held.isHeld) held.release() }
    }

    @Suppress("DEPRECATION") // Newer resolveService(Executor, ResolveListener) is API 34+; keep this until minSdk rises.
    private fun resolve(serviceInfo: NsdServiceInfo) {
        nsd.resolveService(serviceInfo, object : NsdManager.ResolveListener {
            override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) {
                // Silent: NsdManager.FAILURE_ALREADY_ACTIVE etc. happens under load.
            }

            override fun onServiceResolved(info: NsdServiceInfo) {
                val attrs = info.attributes ?: emptyMap()
                val pid = attrs[LanConstants.TXT_PEER_ID]?.decodeToString() ?: return
                val app = attrs[LanConstants.TXT_APP_ID]?.decodeToString() ?: return
                if (pid == registration.localPeerId.value) return
                if (app != registration.appId.value) return

                val name = attrs[LanConstants.TXT_DEVICE_NAME]?.decodeToString() ?: pid
                val plat = attrs[LanConstants.TXT_PLATFORM]?.decodeToString()
                val caps = attrs[LanConstants.TXT_CAPABILITIES]?.decodeToString()
                @Suppress("DEPRECATION") // info.host is the supported way on API < 34.
                val host = info.host?.hostAddress ?: return
                val port = info.port

                val supportedTransports = caps
                    ?.split(",")
                    ?.mapNotNull { tag ->
                        runCatching { TransportKind.valueOf(tag.trim()) }.getOrNull()
                    }
                    ?.toSet()
                    ?: setOf(TransportKind.LAN)
                val platform = plat?.let {
                    runCatching { Platform.valueOf(it) }.getOrNull()
                } ?: Platform.UNKNOWN

                val internalPeer = InternalPeer(
                    publicPeer = Peer(
                        id = PeerId(pid),
                        name = name,
                        platform = platform,
                        supportedTransports = supportedTransports
                    ),
                    transportHints = listOf(
                        TransportHint(type = TransportKind.LAN, host = host, port = port)
                    )
                )
                _events.tryEmit(PeerEvent.Found(internalPeer))
            }
        })
    }
}
