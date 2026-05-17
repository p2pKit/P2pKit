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
import platform.Network.nw_browser_state_ready
import platform.Network.nw_browser_state_waiting
import platform.Network.nw_browser_t
import platform.Network.nw_listener_set_advertise_descriptor
import platform.Network.nw_parameters_create
import platform.Network.nw_parameters_set_include_peer_to_peer

/**
 * iOS LAN [DiscoveryTransport].
 *
 * Browsing uses `nw_browser_t`; advertising rides on the listener inside
 * [IosLanDataTransport] via `nw_listener_set_advertise_descriptor`.
 *
 * **Refresh loop:** `PeerRegistry` in :p2p-core evicts a peer 15 s after its
 * last `PeerEvent.Found`/`Updated`. NWBrowser only fires "result_added" once
 * per peer (and "result_removed" when a peer leaves), so without a periodic
 * heartbeat the iOS discovery transport's peers would silently disappear
 * from `kit.peers` after 15 s even while NWBrowser still sees them. The
 * refresh loop here re-emits `PeerEvent.Updated` for every cached peer
 * every 5 s as long as discovery is running.
 *
 * **Diagnostics:** every browser state change, every result-change call,
 * every TXT decode, and every filter outcome is appended to
 * [IosLanDebug.events]. The iOS sample subscribes to that flow for an
 * in-app log; from a release consumer's view it's a 200-entry replayable
 * SharedFlow they can ignore.
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

    @Volatile
    private var browserReady: Boolean = false

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) = lock.withLock {
        if (advertising) return@withLock
        IosLanDebug.log(
            "advertise",
            "starting: peerId=${localPeer.peerId.value.take(8)} app=${localPeer.appId.value} name=${localPeer.deviceName}"
        )
        val descriptor = buildAdvertiseDescriptor(localPeer)
        nw_listener_set_advertise_descriptor(dataTransport.listener, descriptor)
        advertising = true
        IosLanDebug.log("advertise", "started")
    }

    override suspend fun stopAdvertising() = lock.withLock {
        if (!advertising) return@withLock
        IosLanDebug.log("advertise", "stopping")
        nw_listener_set_advertise_descriptor(dataTransport.listener, null)
        advertising = false
    }

    override suspend fun startDiscovery() = lock.withLock {
        if (browser != null) return@withLock
        IosLanDebug.log(
            "browse",
            "startDiscovery: type=${LanConstants.SERVICE_TYPE_BONJOUR} app=${transportContext.appId.value} localPid=${transportContext.localPeerId.value.take(8)}"
        )
        val descriptor = nw_browse_descriptor_create_bonjour_service(
            type = LanConstants.SERVICE_TYPE_BONJOUR,
            domain = null
        )
        nw_browse_descriptor_set_include_txt_record(descriptor, true)

        val browserParams = nw_parameters_create()
        nw_parameters_set_include_peer_to_peer(browserParams, true)

        val b = nw_browser_create(descriptor, browserParams)
            ?: error("nw_browser_create returned null")
        browser = b

        nw_browser_set_queue(b, dataTransport.queue)
        nw_browser_set_state_changed_handler(b) { state, _ ->
            val label = when (state) {
                nw_browser_state_ready -> "ready"
                nw_browser_state_waiting -> "waiting"
                nw_browser_state_failed -> "failed"
                nw_browser_state_cancelled -> "cancelled"
                else -> "raw=$state"
            }
            IosLanDebug.log("browse", "state -> $label")
            when (state) {
                nw_browser_state_ready -> browserReady = true
                nw_browser_state_failed, nw_browser_state_cancelled -> {
                    browserReady = false
                    browser = null
                }
            }
            Unit
        }
        nw_browser_set_browse_results_changed_handler(b) { old, new, batchComplete ->
            handleBrowseResultChange(old, new, batchComplete)
            Unit
        }
        nw_browser_start(b)
        IosLanDebug.log("browse", "nw_browser_start invoked")
    }

    override suspend fun stopDiscovery() = lock.withLock {
        val b = browser ?: return@withLock
        IosLanDebug.log("browse", "stopDiscovery: cancelling browser")
        browser = null
        browserReady = false
        nw_browser_cancel(b)
    }

    private fun buildAdvertiseDescriptor(localPeer: LocalPeerInfo): nw_advertise_descriptor_t {
        val descriptor = nw_advertise_descriptor_create_bonjour_service(
            name = localPeer.peerId.value,
            type = LanConstants.SERVICE_TYPE_BONJOUR,
            domain = null
        ) ?: error("nw_advertise_descriptor_create_bonjour_service returned null")
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

    private fun handleBrowseResultChange(
        old: nw_browse_result_t,
        new: nw_browse_result_t,
        batchComplete: Boolean
    ) {
        val changes = nw_browse_result_get_changes(old, new)
        val added = (changes and nw_browse_result_change_result_added.toULong()) != 0UL
        val removed = (changes and nw_browse_result_change_result_removed.toULong()) != 0UL
        val txtChanged = (changes and nw_browse_result_change_txt_record_changed.toULong()) != 0UL

        IosLanDebug.log(
            "browse",
            "result change: added=$added removed=$removed txtChanged=$txtChanged batchComplete=$batchComplete oldNull=${old == null} newNull=${new == null}"
        )

        if (added && new != null) {
            emitPeer(new, isUpdate = false)
        } else if (removed && old != null) {
            emitLost(old)
        } else if (txtChanged && new != null) {
            emitPeer(new, isUpdate = true)
        }
    }

    private fun emitPeer(result: nw_browse_result_t, isUpdate: Boolean) {
        val endpoint = nw_browse_result_copy_endpoint(result)
        if (endpoint == null) {
            IosLanDebug.log("browse", "emitPeer: copy_endpoint returned null — skip")
            return
        }
        val txt = nw_browse_result_copy_txt_record_object(result)
        val attrs = IosBonjour.txtRecordToMap(txt)
        IosLanDebug.log("browse", "emitPeer: txt=$attrs (isUpdate=$isUpdate)")

        val pid = attrs[LanConstants.TXT_PEER_ID]
        val app = attrs[LanConstants.TXT_APP_ID]
        if (pid == null) {
            IosLanDebug.log("browse", "emitPeer: filter — missing TXT_PEER_ID")
            return
        }
        if (app == null) {
            IosLanDebug.log("browse", "emitPeer: filter — missing TXT_APP_ID")
            return
        }
        if (pid == transportContext.localPeerId.value) {
            IosLanDebug.log("browse", "emitPeer: filter — self (pid matches local)")
            return
        }
        if (app != transportContext.appId.value) {
            IosLanDebug.log(
                "browse",
                "emitPeer: filter — appId mismatch (peer=$app local=${transportContext.appId.value})"
            )
            return
        }

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
            transportHints = listOf(TransportHint(type = TransportKind.LAN))
        )
        val event = if (isUpdate) PeerEvent.Updated(internalPeer) else PeerEvent.Found(internalPeer)
        _events.tryEmit(event)
        IosLanDebug.log("browse", "emitPeer: ACCEPTED ${if (isUpdate) "Updated" else "Found"} $name pid=${pid.take(8)}")
    }

    private fun emitLost(result: nw_browse_result_t) {
        val txt = nw_browse_result_copy_txt_record_object(result)
        val pid = IosBonjour.txtRecordToMap(txt)[LanConstants.TXT_PEER_ID]
        if (pid == null) {
            IosLanDebug.log("browse", "emitLost: TXT had no peer id — skip")
            return
        }
        if (pid == transportContext.localPeerId.value) return
        val peerId = PeerId(pid)
        endpointRegistry.remove(peerId)
        _events.tryEmit(PeerEvent.Lost(peerId))
        IosLanDebug.log("browse", "emitLost: $pid")
    }
}
