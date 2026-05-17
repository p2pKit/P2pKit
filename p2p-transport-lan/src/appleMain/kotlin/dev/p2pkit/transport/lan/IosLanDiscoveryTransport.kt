@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportHint
import kotlin.concurrent.Volatile
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import platform.Network.nw_advertise_descriptor_create_bonjour_service
import platform.Network.nw_advertise_descriptor_set_no_auto_rename
import platform.Network.nw_advertise_descriptor_set_txt_record_object
import platform.Network.nw_advertise_descriptor_t
import platform.Network.nw_browse_descriptor_create_bonjour_service
import platform.Network.nw_browse_descriptor_set_include_txt_record
import platform.Network.nw_browse_result_change_result_added
import platform.Network.nw_browse_result_change_result_removed
import platform.Network.nw_browse_result_change_txt_record_changed
import platform.Network.nw_browse_result_copy_endpoint
import platform.Network.nw_browse_result_copy_txt_record_object
import platform.Network.nw_browse_result_get_changes
import platform.Network.nw_browse_result_t
import platform.Network.nw_browser_cancel
import platform.Network.nw_browser_create
import platform.Network.nw_browser_set_browse_results_changed_handler
import platform.Network.nw_browser_set_queue
import platform.Network.nw_browser_set_state_changed_handler
import platform.Network.nw_browser_start
import platform.Network.nw_browser_state_cancelled
import platform.Network.nw_browser_state_failed
import platform.Network.nw_browser_t
import platform.Network.nw_listener_set_advertise_descriptor

/**
 * iOS LAN [DiscoveryTransport].
 *
 * - **Advertise** rides on the existing `nw_listener_t` owned by
 *   [IosLanDataTransport]: we build an `nw_advertise_descriptor_t` with
 *   service name = local peer id, service type = [LanConstants.SERVICE_TYPE_BONJOUR],
 *   and a TXT record containing the same keys JmDNS / NSD use. Bonjour
 *   then broadcasts the service on every available interface.
 * - **Browse** uses `nw_browser_t` on the same service type. Every
 *   `nw_browse_result_t` carries an `nw_endpoint_t` (the resolved Bonjour
 *   service) plus the remote TXT record. We stash the endpoint in
 *   [IosEndpointRegistry] keyed by the remote peer id so
 *   [IosLanDataTransport.connect] can dial it via `nw_connection_create`.
 *
 * Same queue as the data transport — serial, so handler invocations from the
 * listener and browser never race each other.
 */
internal class IosLanDiscoveryTransport(
    private val transportContext: TransportContext,
    private val endpointRegistry: IosEndpointRegistry,
    private val dataTransport: IosLanDataTransport
) : DiscoveryTransport {

    override val type: TransportKind = TransportKind.LAN

    private val _events = MutableSharedFlow<PeerEvent>(
        replay = 0,
        extraBufferCapacity = 256,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    override val events: Flow<PeerEvent> = _events.asSharedFlow()

    private val lock = Mutex()

    @Volatile
    private var advertising: Boolean = false

    @Volatile
    private var browser: nw_browser_t = null

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) = lock.withLock {
        if (advertising) return@withLock
        val descriptor = buildAdvertiseDescriptor(localPeer)
        nw_listener_set_advertise_descriptor(dataTransport.listener, descriptor)
        advertising = true
    }

    override suspend fun stopAdvertising() = lock.withLock {
        if (!advertising) return@withLock
        // Passing null clears the advertised service from the listener.
        nw_listener_set_advertise_descriptor(dataTransport.listener, null)
        advertising = false
    }

    override suspend fun startDiscovery() = lock.withLock {
        if (browser != null) return@withLock
        val descriptor = nw_browse_descriptor_create_bonjour_service(
            type = LanConstants.SERVICE_TYPE_BONJOUR,
            domain = null
        )
        nw_browse_descriptor_set_include_txt_record(descriptor, true)

        val b = nw_browser_create(descriptor, null)
            ?: error("nw_browser_create returned null")
        browser = b

        nw_browser_set_queue(b, dataTransport.queue)
        nw_browser_set_state_changed_handler(b) { state, _ ->
            when (state) {
                nw_browser_state_failed,
                nw_browser_state_cancelled -> browser = null
            }
        }
        nw_browser_set_browse_results_changed_handler(b) { old, new, _ ->
            handleBrowseResultChange(old, new)
        }
        nw_browser_start(b)
    }

    override suspend fun stopDiscovery() = lock.withLock {
        val b = browser ?: return@withLock
        browser = null
        nw_browser_cancel(b)
    }

    private fun buildAdvertiseDescriptor(localPeer: LocalPeerInfo): nw_advertise_descriptor_t {
        val descriptor = nw_advertise_descriptor_create_bonjour_service(
            name = localPeer.peerId.value,
            type = LanConstants.SERVICE_TYPE_BONJOUR,
            domain = null
        ) ?: error("nw_advertise_descriptor_create_bonjour_service returned null")
        // Collisions on the network must surface as a failure, not a renamed
        // service — peer-id-as-service-name is supposed to be unique.
        nw_advertise_descriptor_set_no_auto_rename(descriptor, true)

        val txt = IosBonjour.mapToTxtRecord(
            mapOf(
                LanConstants.TXT_PEER_ID to localPeer.peerId.value,
                LanConstants.TXT_APP_ID to localPeer.appId.value,
                LanConstants.TXT_DEVICE_NAME to localPeer.deviceName,
                LanConstants.TXT_PLATFORM to localPeer.platform.name,
                LanConstants.TXT_CAPABILITIES to localPeer.supportedTransports.joinToString(",") { it.name },
                LanConstants.TXT_PROTOCOL_VERSION to LanConstants.PROTOCOL_VERSION.toString()
            )
        )
        nw_advertise_descriptor_set_txt_record_object(descriptor, txt)
        return descriptor
    }

    private fun handleBrowseResultChange(old: nw_browse_result_t, new: nw_browse_result_t) {
        val changes = nw_browse_result_get_changes(old, new)
        val added = (changes and nw_browse_result_change_result_added.toULong()) != 0UL
        val removed = (changes and nw_browse_result_change_result_removed.toULong()) != 0UL
        val txtChanged = (changes and nw_browse_result_change_txt_record_changed.toULong()) != 0UL

        if (added && new != null) {
            emitPeer(new, isUpdate = false)
        } else if (removed && old != null) {
            emitLost(old)
        } else if (txtChanged && new != null) {
            emitPeer(new, isUpdate = true)
        }
    }

    private fun emitPeer(result: nw_browse_result_t, isUpdate: Boolean) {
        val endpoint = nw_browse_result_copy_endpoint(result) ?: return
        val txt = nw_browse_result_copy_txt_record_object(result)
        val attrs = IosBonjour.txtRecordToMap(txt)

        val pid = attrs[LanConstants.TXT_PEER_ID] ?: return
        val app = attrs[LanConstants.TXT_APP_ID] ?: return
        if (pid == transportContext.localPeerId.value) return
        if (app != transportContext.appId.value) return

        val name = attrs[LanConstants.TXT_DEVICE_NAME] ?: pid
        val platform = attrs[LanConstants.TXT_PLATFORM]
            ?.let { runCatching { Platform.valueOf(it) }.getOrNull() }
            ?: Platform.UNKNOWN
        val capabilities = attrs[LanConstants.TXT_CAPABILITIES]
            ?.split(",")
            ?.mapNotNull { tag -> runCatching { TransportKind.valueOf(tag.trim()) }.getOrNull() }
            ?.toSet()
            ?: setOf(TransportKind.LAN)

        val peerId = PeerId(pid)
        endpointRegistry.put(peerId, endpoint)

        val internalPeer = InternalPeer(
            publicPeer = Peer(
                id = peerId,
                name = name,
                platform = platform,
                supportedTransports = capabilities
            ),
            // host/port are unknown on iOS — the connection is built from the
            // opaque endpoint stashed in the registry. We still surface a LAN
            // TransportHint so TransportManager picks us.
            transportHints = listOf(TransportHint(type = TransportKind.LAN))
        )
        val event = if (isUpdate) PeerEvent.Updated(internalPeer) else PeerEvent.Found(internalPeer)
        _events.tryEmit(event)
    }

    private fun emitLost(result: nw_browse_result_t) {
        val txt = nw_browse_result_copy_txt_record_object(result)
        val pid = IosBonjour.txtRecordToMap(txt)[LanConstants.TXT_PEER_ID] ?: return
        if (pid == transportContext.localPeerId.value) return
        val peerId = PeerId(pid)
        endpointRegistry.remove(peerId)
        _events.tryEmit(PeerEvent.Lost(peerId))
    }
}
