package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.PeerId
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse

@OptIn(ExperimentalCoroutinesApi::class)
class FakeDiscoveryTransportTest {

    @Test
    fun syntheticFixtureDoesNotReplayBeforeSubscriptionInEitherMode() = runTest {
        for (strict in listOf(false, true)) {
            val fixture = FakeDiscoveryTransport(strictDelivery = strict)
            fixture.emit(PeerEvent.Lost(PeerId("before-subscription")))

            val received = async(start = CoroutineStart.UNDISPATCHED) {
                fixture.events.first()
            }
            fixture.awaitSubscriber()
            val afterSubscription = PeerEvent.Lost(PeerId("after-subscription"))
            fixture.emit(afterSubscription)

            assertEquals(afterSubscription, received.await(), "strictDelivery=$strict")
        }
    }

    @Test
    fun strictBufferAcceptanceDoesNotAcknowledgeConsumerProcessing() = runTest {
        val fixture = FakeDiscoveryTransport(strictDelivery = true)
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val observed = mutableListOf<PeerEvent>()
        val events: List<PeerEvent> = List(258) { PeerEvent.Lost(PeerId("event-$it")) }
        val collector = backgroundScope.launch(start = CoroutineStart.UNDISPATCHED) {
            fixture.events.collect { event ->
                observed += event
                if (event == events.first()) {
                    entered.complete(Unit)
                    release.await()
                }
            }
        }
        try {
            fixture.awaitSubscriber()
            fixture.emit(events.first())
            runCurrent()
            entered.await()

            // The callback remains blocked: the next emit returns after enqueueing.
            fixture.emit(events[1])
            assertEquals(listOf(events.first()), observed)
            for (index in 2..256) fixture.emit(events[index])
            val saturated = async(start = CoroutineStart.UNDISPATCHED) {
                fixture.emit(events.last())
            }
            assertFalse(saturated.isCompleted, "the full 256-event buffer must suspend a strict emitter")

            release.complete(Unit)
            runCurrent()
            saturated.await()
            assertEquals(events, observed, "strict backlog must drain without loss once the callback resumes")
        } finally {
            release.complete(Unit)
            collector.cancelAndJoin()
        }
    }
}
