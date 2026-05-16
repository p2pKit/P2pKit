package dev.p2pkit.sample.kmp

import dev.p2pkit.core.P2pMessage
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.CompletableDeferred
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
 */
class KmpConsumerLoopbackTest {

    private val appId = "kmp-consumer-itest-${System.currentTimeMillis()}"

    @Test
    fun sharedFactoryCreatesAKitThatCanGreetAPeer() {
        runBlocking {
            // The "responder" — accepts whatever message arrives.
            val responder = createP2pKit(appId, "Bob")
            // The "greeter" — discovers and sends.
            val greeter = createP2pKit(appId, "Alice")

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
