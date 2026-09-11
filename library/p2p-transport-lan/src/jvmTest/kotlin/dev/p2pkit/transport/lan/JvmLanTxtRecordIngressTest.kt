package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportSecurityProfile
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/** Real JmDNS records through the production callback/relay path, without multicast timing. */
@OptIn(ExperimentalCoroutinesApi::class)
class JvmLanTxtRecordIngressTest {
    @Test
    fun legacyDiscoveryRejectsMalformedUtf8AndKeepsItsListenerAlive() =
        rejectsMalformedUtf8(TransportSecurityProfile.LegacyPlaintextV1)

    @Test
    fun secureDiscoveryRejectsMalformedUtf8AndKeepsItsListenerAlive() =
        rejectsMalformedUtf8(TransportSecurityProfile.AuthenticatedV2)

    private fun rejectsMalformedUtf8(profile: TransportSecurityProfile) = runTest {
        withDiscovery(profile) { fixture ->
            for ((description, bytes) in LanTxtRecordFixtures.malformedUtf8) {
                for (key in LanConstants.DISCOVERY_TXT_KEYS) {
                    // Keeping LAN in the capability list exposes normalization followed by enum filtering.
                    val value = if (key == LanConstants.TXT_CAPABILITIES) "LAN,".encodeToByteArray() + bytes else bytes
                    fixture.publish(mapOf(key to value))
                    runCurrent()
                    assertTrue(fixture.events.isEmpty(), "$profile / $key / $description must not be admitted")
                    fixture.backend.withdraw("remote")
                    runCurrent()
                    assertTrue(fixture.events.isEmpty(), "an unadmitted malformed record cannot emit Lost")
                }
            }
            fixture.publish()
            runCurrent()
            assertEquals("Remote", assertIs<PeerEvent.Found>(fixture.events.single()).peer.publicPeer.name)
        }
    }

    @Test
    fun invalidUtf8ReresolutionWithdrawsExactlyOnceAndValidRecoveryIsFound() = runTest {
        for (profile in TransportSecurityProfile.entries) {
            withDiscovery(profile) { fixture ->
                fixture.publish()
                runCurrent()
                assertIs<PeerEvent.Found>(fixture.events.single())
                fixture.events.clear()

                val invalid = mapOf(LanConstants.TXT_DEVICE_NAME to byteArrayOf(0xC3.toByte()))
                fixture.publish(invalid)
                runCurrent()
                assertEquals(PeerId("remote"), assertIs<PeerEvent.Lost>(fixture.events.single()).peerId)
                fixture.events.clear()
                fixture.publish(invalid)
                runCurrent()
                assertTrue(fixture.events.isEmpty(), "repeated invalid input must not duplicate Lost")

                val lateEvents = mutableListOf<PeerEvent>()
                val lateCollector = launch(start = CoroutineStart.UNDISPATCHED) {
                    fixture.transport.events.collect(lateEvents::add)
                }
                try {
                    runCurrent()
                    assertTrue(lateEvents.isEmpty(), "a late collector must not replay the invalidated route")
                    fixture.publish()
                    runCurrent()
                    assertIs<PeerEvent.Found>(fixture.events.single())
                    assertIs<PeerEvent.Found>(lateEvents.single())
                    fixture.backend.withdraw("remote")
                    runCurrent()
                    assertIs<PeerEvent.Lost>(fixture.events.last())
                    assertEquals(2, fixture.events.size)
                } finally {
                    lateCollector.cancelAndJoin()
                }
            }
        }
    }

    @Test
    fun malformedDuplicateCannotBeHiddenBehindAValidLastValue() = runTest {
        for (profile in TransportSecurityProfile.entries) {
            withDiscovery(profile) { fixture ->
                val entries = LanTxtRecordFixtures.properties(profile).toList() + listOf(
                    LanConstants.TXT_DEVICE_NAME to byteArrayOf(0xC3.toByte()),
                    LanConstants.TXT_DEVICE_NAME to "Last".encodeToByteArray()
                )
                fixture.publishRaw(LanTxtRecordFixtures.encode(entries))
                runCurrent()
                assertTrue(fixture.events.isEmpty(), "all consumed occurrences must decode strictly")
            }
        }
    }

    @Test
    fun emptyBooleanAndNulTerminatedNamesAreNotNormalizedIntoValidNames() = runTest {
        for (profile in TransportSecurityProfile.entries) {
            withDiscovery(profile) { fixture ->
                for (value in listOf(null, byteArrayOf(), "Remote\u0000".encodeToByteArray())) {
                    fixture.publish(mapOf(LanConstants.TXT_DEVICE_NAME to value))
                    runCurrent()
                    assertTrue(fixture.events.isEmpty(), "malformed semantic text must not be normalized")
                }
            }
        }
    }

    @Test
    fun validUnicodeReplacementCharactersAndUnknownBinaryFieldsRemainUsable() = runTest {
        for (profile in TransportSecurityProfile.entries) {
            withDiscovery(profile) { fixture ->
                val peerId = "remote-\uFFFD"
                val name = "📱 αβ \uFFFD = Remote"
                val properties = LanTxtRecordFixtures.properties(profile) + mapOf(
                    LanConstants.TXT_PEER_ID to peerId.encodeToByteArray(),
                    LanConstants.TXT_DEVICE_NAME to name.encodeToByteArray(),
                    "future" to byteArrayOf(0xFF.toByte())
                )
                fixture.publishRaw(LanTxtRecordFixtures.encode(properties.toList()), peerId)
                runCurrent()
                val found = assertIs<PeerEvent.Found>(fixture.events.single()).peer.publicPeer
                assertEquals(peerId, found.id.value)
                assertEquals(name, found.name)
            }
        }
    }

    private suspend fun TestScope.withDiscovery(
        profile: TransportSecurityProfile,
        block: suspend (DiscoveryFixture) -> Unit
    ) {
        val fixture = DiscoveryFixture(profile)
        val collector = launch(start = CoroutineStart.UNDISPATCHED) {
            fixture.transport.events.collect(fixture.events::add)
        }
        try {
            fixture.transport.startDiscovery()
            block(fixture)
        } finally {
            try {
                fixture.transport.stopDiscovery()
            } finally {
                collector.cancelAndJoin()
            }
        }
    }

    private class DiscoveryFixture(val profile: TransportSecurityProfile) {
        val backend = JvmDeterministicDiscoveryTestBackend()
        val events = mutableListOf<PeerEvent>()
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

        fun publish(replacements: Map<String, ByteArray?> = emptyMap()) {
            publishRaw(LanTxtRecordFixtures.encode((LanTxtRecordFixtures.properties(profile) + replacements).toList()))
        }

        fun publishRaw(bytes: ByteArray, instanceName: String = "remote") {
            val info = ServiceInfo.create(
                LanConstants.serviceTypeJmdns(profile), instanceName, 45_001, 0, 0, bytes
            )
            backend.advertise(JvmTestDiscoveryAdvertisement(instanceName, info))
        }
    }
}
