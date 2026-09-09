package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.provisioning.ManualPeerRegistrar
import dev.p2pkit.core.provisioning.NetworkProvisioningConfig
import dev.p2pkit.core.provisioning.ProvisioningContext
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

@OptIn(ExperimentalP2pApi::class)
class IosManualProvisioningPrivacyTest {
    @Test
    @Suppress("DEPRECATION")
    fun manualRegistrationRedactsBothLoggerAndNativeDiagnosticStream() = runBlocking<Unit> {
        val logger = RecordingProvisioningLogger()
        val pin = PeerFingerprint("p2f1-${"a".repeat(52)}")
        val manager = IosManualNetworkProvisioningManager(
            ProvisioningContext(
                appId = AppId("ios-provisioning-privacy"),
                localPeerId = PeerId("local"),
                localDeviceName = "synthetic",
                config = NetworkProvisioningConfig(),
                logger = logger,
                lanTcpPort = { 47_561 },
                manualPeerRegistrar = object : ManualPeerRegistrar {
                    override fun registerManualPeer(
                        host: String,
                        port: Int,
                        kind: TransportKind,
                        deviceName: String?,
                        expectedFingerprint: PeerFingerprint?
                    ): Peer = Peer(PeerId("manual"), "synthetic", Platform.UNKNOWN, setOf(kind))
                }
            )
        )
        // Subscribe before either call without changing process-global logging
        // configuration or discarding another test/consumer's retained history.
        val existing = IosLanDebug.events.replayCache.size
        val native = async(start = CoroutineStart.UNDISPATCHED) {
            IosLanDebug.events.drop(existing).filter { "[provision] createManualPeer" in it }.take(2).toList()
        }
        try {
            manager.createManualPeer("203.0.113.77", 47_561)
            manager.createManualPeer("203.0.113.77", 47_561, pin)
            val nativeMessages = withTimeout(2_000) { native.await() }
            assertEquals(
                listOf("provisioning: createManualPeer", "provisioning: createManualPeer with authenticated pin"),
                logger.messages
            )
            assertTrue(nativeMessages.all { "[provision] createManualPeer" in it })
            // Timestamp digits are metadata, not a disclosed TCP port.
            val nativePayloads = nativeMessages.map { it.substringAfter("] ") }
            for (privateValue in listOf("203.0.113.77", "47561", pin.value)) {
                assertTrue((logger.messages + nativePayloads).none { privateValue in it })
            }
        } finally {
            native.cancelAndJoin()
            manager.close()
        }
    }
}

private class RecordingProvisioningLogger : P2pLogger {
    val messages = mutableListOf<String>()
    override fun debug(message: String) { messages += message }
    override fun info(message: String) { messages += message }
    override fun warn(message: String, throwable: Throwable?) { messages += message }
    override fun error(message: String, throwable: Throwable?) { messages += message }
}
