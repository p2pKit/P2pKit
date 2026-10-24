package dev.p2pkit.transport.lan.internal.jmdns.impl

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportSecurityProfile
import dev.p2pkit.transport.lan.JvmDeterministicDiscoveryTestBackend
import dev.p2pkit.transport.lan.JvmLanDiscoveryTransport
import dev.p2pkit.transport.lan.JvmTestDiscoveryAdvertisement
import dev.p2pkit.transport.lan.JvmTestDiscoveryBackend
import dev.p2pkit.transport.lan.LanConstants
import dev.p2pkit.transport.lan.LanServiceRegistration
import dev.p2pkit.transport.lan.LanTxtRecordFixtures
import dev.p2pkit.transport.lan.internal.jmdns.ServiceEvent
import dev.p2pkit.transport.lan.internal.jmdns.ServiceListener
import dev.p2pkit.transport.lan.lanEndpoints
import java.util.concurrent.CopyOnWriteArrayList
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull

/** Original JmDNS cache/clone/executor path through the actual Kotlin admission and state relay. */
@OptIn(ExperimentalCoroutinesApi::class)
class ServiceInfoTxtReadinessIngressTest {
    @Test
    fun secureCachedResolutionCannotEraseActiveAdmission() =
        resolution(TransportSecurityProfile.AuthenticatedV2, staged = false)

    @Test
    fun legacyCachedResolutionCannotEraseActiveAdmission() =
        resolution(TransportSecurityProfile.LegacyPlaintextV1, staged = false)

    @Test
    fun secureCachedResolutionCannotEraseStagedAdmission() =
        resolution(TransportSecurityProfile.AuthenticatedV2, staged = true)

    @Test
    fun legacyCachedResolutionCannotEraseStagedAdmission() =
        resolution(TransportSecurityProfile.LegacyPlaintextV1, staged = true)

    private fun resolution(profile: TransportSecurityProfile, staged: Boolean) = runTest {
        val txt = LanTxtRecordFixtures.encode(LanTxtRecordFixtures.properties(profile).toList())
        ServiceInfoOrderingFixture(LanConstants.serviceTypeJmdns(profile), "remote", txt, true).use { source ->
            val delivery = JvmDeterministicDiscoveryTestBackend { emptyList() }
            val rawValidTxt = CopyOnWriteArrayList<Boolean>()
            val listener = object : ServiceListener {
                override fun serviceAdded(event: ServiceEvent) = Unit

                override fun serviceRemoved(event: ServiceEvent) {
                    delivery.withdraw(event.name)
                }

                override fun serviceResolved(event: ServiceEvent) {
                    rawValidTxt += event.info.getPropertyString(LanConstants.TXT_APP_ID) == "lan-txt-test"
                    // Forward every real callback, including invalid TXT. No test-side filtering,
                    // fabricated success, direct relay mutation or polling can repair the result.
                    delivery.advertise(
                        JvmTestDiscoveryAdvertisement(event.name, event.info, event.info.inetAddresses.toList())
                    )
                }
            }
            val backend = object : JvmTestDiscoveryBackend by delivery {
                override fun subscribe(
                    localPeerId: PeerId,
                    resolved: (JvmTestDiscoveryAdvertisement) -> Unit,
                    removed: (String) -> Unit
                ) {
                    delivery.subscribe(localPeerId, resolved, removed)
                    // The real lease activates only after subscribe returns. Exercise both
                    // its staged latest-per-instance replay and the active publication path.
                    if (staged) source.replayAgainstIncomingTxt(listener, true)
                }
            }
            val transport = JvmLanDiscoveryTransport(
                LanServiceRegistration(
                    appId = AppId("lan-txt-test"),
                    localPeerId = PeerId("local"),
                    deviceName = "Observer",
                    platform = Platform.JVM_DESKTOP,
                    securityProfile = profile,
                    fingerprint = if (profile == TransportSecurityProfile.AuthenticatedV2) {
                        PeerFingerprint("p2f1-" + "b".repeat(51) + "a")
                    } else {
                        null
                    },
                    tcpPort = 45_000
                ),
                backend
            )
            val events = mutableListOf<PeerEvent>()
            val collector = launch(start = CoroutineStart.UNDISPATCHED) { transport.events.collect(events::add) }
            try {
                transport.startDiscovery()
                if (!staged) source.replayAgainstIncomingTxt(listener, true)
                runCurrent()
                assertEquals(1, events.size, "The final real admission/relay state must retain the resolved peer")
                val found = assertIs<PeerEvent.Found>(events.single())
                assertEquals(PeerId("remote"), found.peer.publicPeer.id)
                assertEquals("Remote", found.peer.publicPeer.name)
                assertEquals(listOf("127.0.0.1"), found.peer.lanEndpoints().map { it.host })
                assertEquals(listOf(45_001), found.peer.lanEndpoints().map { it.port })
                if (profile == TransportSecurityProfile.AuthenticatedV2) {
                    assertNotNull(found.peer.authenticationHint)
                } else {
                    assertNull(found.peer.authenticationHint)
                }
                assertEquals(listOf(true), rawValidTxt.toList())

                source.requestUnchangedResolution()
                runCurrent()
                assertEquals(listOf(true), rawValidTxt.toList(), "Fresh resolvers must retain raw deduplication")
                assertEquals<List<PeerEvent>>(listOf(found), events)

                // Absence of TXT is not an empty TXT record. A received empty record must
                // still reach validation and withdraw the now-invalid application identity.
                source.receiveTxt(byteArrayOf(0))
                runCurrent()
                assertEquals(listOf(true, false), rawValidTxt.toList())
                assertEquals(2, events.size)
                assertEquals(PeerId("remote"), assertIs<PeerEvent.Lost>(events.last()).peerId)

                source.receiveTxt(txt)
                runCurrent()
                assertEquals(listOf(true, false, true), rawValidTxt.toList())
                assertEquals(3, events.size)
                assertEquals(found.peer, assertIs<PeerEvent.Found>(events.last()).peer)
            } finally {
                try {
                    transport.stopDiscovery()
                } finally {
                    collector.cancelAndJoin()
                }
            }
        }
    }
}
