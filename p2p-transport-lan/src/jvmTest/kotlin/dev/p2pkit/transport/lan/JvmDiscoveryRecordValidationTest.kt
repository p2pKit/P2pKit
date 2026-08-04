package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transport.PeerEvent
import javax.jmdns.ServiceInfo
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertTrue

/**
 * AUDIT-2026-07 (RBS-1) / P1-25 integration leg: crafted-advertiser loopback
 * test for discovery-record input validation in [JvmLanDiscoveryTransport].
 *
 * A deterministic callback crafter supplies real [ServiceInfo] values with
 * non-conforming TXT records — a
 * whitespace-only `pid` value, a record for a different appId, and a
 * service-instance/TXT identity mismatch — alongside conforming ones. The
 * transport under test must:
 *
 *  - never emit a `PeerEvent` for the malformed (blank-pid) record, on the
 *    found or the removed path;
 *  - never emit a `PeerEvent` for the other-app or mismatched-identity record;
 *  - keep delivering conforming records after malformed discovery input and
 *    advertiser withdrawal/re-registration, so the listener worker remains
 *    live. This settles the register's JVM/Android listener-thread-disposition
 *    residual without assigning a deterministic deadline to UDP goodbye.
 *
 * JmDNS goodbye delivery is multicast/TTL-timed and cannot provide a stable
 * unit-test clock. [JvmServiceAdmissionsTest] proves exact TXT-less removal
 * ownership; this test deterministically exercises the production
 * [ServiceInfo] parsing and listener-survival path.
 *
 * Like [JvmLanLoopbackTest], this uses the explicitly gated in-process test
 * discovery path so hosted network topology cannot skip or randomize the
 * callback sequence. Production discovery remains JmDNS-only.
 */
class JvmDiscoveryRecordValidationTest {

    private val unique = "p2pkit-rbs1-${System.currentTimeMillis()}"
    private val discoveryBackend = JvmDeterministicDiscoveryTestBackend()

    @Test
    fun malformedAndOtherAppRecordsAreSkippedWhileConformingRecordsStillFlow() {
        runBlocking {
            val conformingPid = "conforming-$unique"
            val postRemovalPid = "post-removal-$unique"
            val otherAppPid = "other-app-$unique"
            val mismatchedPid = "mismatched-pid-$unique"

            val registration = LanServiceRegistration(
                appId = AppId(unique),
                localPeerId = PeerId("observer-$unique"),
                deviceName = "Observer",
                platform = Platform.JVM_DESKTOP,
                tcpPort = 45000
            )
            val transport = JvmLanDiscoveryTransport(registration, discoveryBackend)
            val seen = mutableListOf<PeerEvent>()
            val subscribed = CompletableDeferred<Unit>()
            val collector = launch {
                transport.events
                    // onStart (not onSubscription — `events` is typed Flow):
                    // on runBlocking's single-threaded event loop the
                    // collector registers its subscription before the awaiting
                    // parent resumes, so no event can be missed.
                    .onStart { subscribed.complete(Unit) }
                    .collect { event -> synchronized(seen) { seen.add(event) } }
            }
            subscribed.await()
            transport.startDiscovery()

            val advertisedInstances = mutableListOf<String>()
            try {
                val blankPidService = craftedService(
                    instanceName = "blank-pid-$unique",
                    port = 45001,
                    pid = " ", // whitespace-only: passes a null check, rejected by PeerId()
                    app = unique,
                    deviceName = "BlankPid"
                )
                val otherAppService = craftedService(
                    instanceName = "other-app-$unique",
                    port = 45002,
                    pid = otherAppPid,
                    app = "$unique-other",
                    deviceName = "OtherApp"
                )
                val conformingService = craftedService(
                    instanceName = "conforming-$unique",
                    port = 45003,
                    pid = conformingPid,
                    app = unique,
                    deviceName = "Conforming"
                )
                val mismatchedService = craftedService(
                    instanceName = "different-instance-$unique",
                    port = 45005,
                    pid = mismatchedPid,
                    app = unique,
                    deviceName = "Mismatched"
                )
                // Non-conforming records first, so the listener processes
                // them before the conforming one. Its arrival proves the
                // callback survived malformed input.
                advertise(blankPidService, advertisedInstances)
                advertise(otherAppService, advertisedInstances)
                advertise(mismatchedService, advertisedInstances)
                advertise(conformingService, advertisedInstances)

                // Found path: the conforming record still resolves and emits
                // even though the blank-pid record went through the same
                // serviceResolved callback.
                awaitCondition {
                    synchronized(seen) {
                        seen.any { it is PeerEvent.Found && pidOf(it) == conformingPid }
                    }
                }

                // Exercise real removal callbacks for every record, then
                // prove the same listener still accepts a fresh conforming
                // record. Exact removal ownership is deterministic in
                // JvmServiceAdmissionsTest rather than coupled to UDP timing.
                advertisedInstances.toList().forEach(discoveryBackend::withdraw)
                advertisedInstances.clear()

                // Listener survival after advertiser withdrawal: a fresh
                // conforming record must still be discovered.
                val postRemovalService = craftedService(
                    instanceName = "post-removal-$unique",
                    port = 45004,
                    pid = postRemovalPid,
                    app = unique,
                    deviceName = "PostRemoval"
                )
                advertise(postRemovalService, advertisedInstances)
                awaitCondition {
                    synchronized(seen) {
                        seen.any { it is PeerEvent.Found && pidOf(it) == postRemovalPid }
                    }
                }

                val snapshot = synchronized(seen) { seen.toList() }
                assertTrue(
                    snapshot.none { pidOf(it).isBlank() },
                    "no event may carry a blank peer id: $snapshot"
                )
                assertTrue(
                    snapshot.none { pidOf(it) == otherAppPid },
                    "a record advertising another appId must not emit Found or Lost: $snapshot"
                )
                assertTrue(
                    snapshot.none { pidOf(it) == mismatchedPid },
                    "service-instance/TXT identity mismatch must not emit any event: $snapshot"
                )
            } finally {
                advertisedInstances.forEach(discoveryBackend::withdraw)
                runCatching { transport.stopDiscovery() }
                collector.cancel()
            }
        }
    }

    private fun craftedService(
        instanceName: String,
        port: Int,
        pid: String,
        app: String,
        deviceName: String
    ): ServiceInfo = ServiceInfo.create(
        LanConstants.LEGACY_SERVICE_TYPE_JMDNS,
        instanceName,
        port,
        /* weight = */ 0,
        /* priority = */ 0,
        mapOf(
            LanConstants.TXT_PEER_ID to pid,
            LanConstants.TXT_APP_ID to app,
            LanConstants.TXT_DEVICE_NAME to deviceName,
            LanConstants.TXT_PLATFORM to Platform.JVM_DESKTOP.name,
            LanConstants.TXT_CAPABILITIES to "LAN",
            LanConstants.TXT_PROTOCOL_VERSION to LanConstants.LEGACY_PROTOCOL_VERSION.toString()
        )
    )

    private fun advertise(service: ServiceInfo, advertisedInstances: MutableList<String>) {
        advertisedInstances += service.name
        discoveryBackend.advertise(
            JvmTestDiscoveryAdvertisement(
                instanceName = service.name,
                info = service
            )
        )
    }

    private suspend fun awaitCondition(condition: () -> Boolean) {
        withTimeout(DISCOVERY_TIMEOUT_MS) {
            while (!condition()) {
                delay(100)
            }
        }
    }

    private fun pidOf(event: PeerEvent): String = when (event) {
        is PeerEvent.Found -> event.peer.publicPeer.id.value
        is PeerEvent.Updated -> event.peer.publicPeer.id.value
        is PeerEvent.Lost -> event.peerId.value
    }

    private companion object {
        const val DISCOVERY_TIMEOUT_MS: Long = 30_000
    }
}
