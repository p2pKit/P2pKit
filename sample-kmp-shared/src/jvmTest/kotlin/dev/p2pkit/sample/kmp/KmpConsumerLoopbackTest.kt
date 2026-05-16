package dev.p2pkit.sample.kmp

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.CompletableDeferred
import java.io.File
import java.nio.file.Files
import kotlin.test.AfterTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * Verifies that a KMP-style consumer can wire up P2pKit via the shared
 * [createP2pKit] factory and exchange a message over real mDNS + TCP.
 *
 * This is the same level of proof as `:p2p-transport-lan:jvmTest`, but
 * driven through [createP2pKit] from `sample-kmp-shared` — proving the
 * KMP consumer integration pattern works end-to-end on JVM.
 *
 * Because v0.2 persists `PeerId` to `<user.home>/.p2pkit/<appId>/peer-id`, two
 * kits in the same JVM with the same `appId` would otherwise share an id and
 * each filter the other out as "self" in mDNS. The helper below points
 * `user.home` at a fresh temp dir per kit so each one gets its own peer-id
 * file.
 */
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
            createP2pKit(appId, deviceName)
        } finally {
            System.setProperty("user.home", savedHome ?: "")
        }
    }

    @Test
    fun sharedFactoryCreatesAKitThatCanGreetAPeer() {
        runBlocking {
            val responder = createKit("Bob")
            val greeter = createKit("Alice")

            try {
                val incomingReady = CompletableDeferred<Unit>()
                val firstMessage = async {
                    responder.incomingSessions
                        .onSubscription { incomingReady.complete(Unit) }
                        .first()
                        .let { session ->
                            session.incoming
                                .onSubscription { /* eager subscribe */ }
                                .first()
                        }
                }
                responder.startAdvertising()
                responder.startDiscovery()
                incomingReady.await()

                val summary = withTimeout(30_000) {
                    runDiscoverAndGreet(greeter, greetingFrom = "Alice")
                }
                assertTrue(
                    summary.startsWith("sent greeting to Bob"),
                    "Expected greeting summary, got: $summary"
                )

                val msg = assertIs<P2pMessage.Text>(withTimeout(10_000) { firstMessage.await() })
                assertEquals("hello from Alice", msg.value)
            } finally {
                greeter.stop()
                responder.stop()
            }
        }
    }
}
