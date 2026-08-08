package dev.p2pkit.sample.kmp

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.provisioning.desktop.jvm
import java.io.File
import java.nio.file.Files
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull

/**
 * Verifies that a KMP-style consumer can wire up P2pKit via the shared
 * [createP2pKit] JVM implementation and exchange a message over real TCP via
 * the deterministic manual-IP fallback.
 *
 * This complements `:p2p-transport-lan:jvmTest` and proves that the KMP
 * consumer wiring, provisioning sidecar, authenticated manual peer, and
 * message path work end-to-end on JVM without multicast timing.
 *
 * The sample's public factory remains unchanged; [createJvmP2pKit] only lets
 * this same-module test add desktop provisioning. Physical-platform tests
 * retain responsibility for real multicast discovery.
 */
@OptIn(ExperimentalP2pApi::class)
class KmpConsumerLoopbackTest {

    private val appId = "kmp-consumer-itest-${System.currentTimeMillis()}"
    private val tempHomes = mutableListOf<File>()

    @AfterTest
    fun cleanup() {
        tempHomes.forEach { runCatching { it.deleteRecursively() } }
        tempHomes.clear()
    }

    private fun createKit(deviceName: String): P2pKit {
        val savedHome = System.getProperty("user.home")
        val tempHome = Files.createTempDirectory("p2pkit-kmp-itest-${deviceName}-").toFile()
        tempHomes.add(tempHome)
        System.setProperty("user.home", tempHome.absolutePath)
        return try {
            createJvmP2pKit(appId, deviceName) { jvm() }
        } finally {
            // clearProperty when originally unset, instead of poisoning
            // user.home to "" (AUDIT-2026-06 fix).
            if (savedHome != null) System.setProperty("user.home", savedHome)
            else System.clearProperty("user.home")
        }
    }

    @Test
    fun sharedFactoryCreatesAKitThatCanGreetAManualPeer() {
        runBlocking {
            val responder = createKit("Bob")
            val greeter = createKit("Alice")

            try {
                val incomingReady = CompletableDeferred<Unit>()
                val incomingSession = async {
                    responder.incomingSessions
                        .onSubscription { incomingReady.complete(Unit) }
                        .first()
                }
                responder.start()
                greeter.start()
                incomingReady.await()

                val responderInfo = assertNotNull(
                    responder.networkProvisioning.getManualConnectionInfo()
                )
                val responderPeer = greeter.networkProvisioning.createManualPeer(
                    host = "127.0.0.1",
                    port = responderInfo.port,
                    expectedFingerprint = assertNotNull(responderInfo.fingerprint)
                )
                val outgoing = withTimeout(10_000) { greeter.connect(responderPeer) }
                assertEquals(ConnectionState.Connected, outgoing.state.value)
                assertEquals(responderInfo.fingerprint, outgoing.peerIdentity.fingerprint)

                withTimeout(10_000) {
                    val incoming = incomingSession.await()
                    val messageReady = CompletableDeferred<Unit>()
                    val firstMessage = async {
                        incoming.incoming
                            .onSubscription { messageReady.complete(Unit) }
                            .first()
                    }

                    // P2pSession.incoming is a replay-0 SharedFlow: sending
                    // before the receiver collector is active legitimately
                    // drops the message. A loaded hosted runner exposed that
                    // race even though the incoming-session collector was
                    // already active. Acknowledge both subscriptions before
                    // exercising the wire path; the existing 10-second bound
                    // still covers session delivery, subscription, send, and
                    // receive as one terminal operation.
                    messageReady.await()
                    outgoing.send(P2pMessage.Text("hello from Alice"))

                    val msg = assertIs<P2pMessage.Text>(firstMessage.await())
                    assertEquals("hello from Alice", msg.value)
                }
            } finally {
                greeter.stop()
                responder.stop()
            }
        }
    }
}
