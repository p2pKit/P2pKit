package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.PeerId
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals

class FakeDiscoveryTransportTest {

    @Test
    fun productionShapedFixtureDoesNotReplayBeforeSubscription() = runTest {
        val fixture = FakeDiscoveryTransport(strictDelivery = true)
        fixture.emit(PeerEvent.Lost(PeerId("before-subscription")))

        val received = async(start = CoroutineStart.UNDISPATCHED) {
            fixture.events.first()
        }
        fixture.awaitSubscriber()
        val afterSubscription = PeerEvent.Lost(PeerId("after-subscription"))
        fixture.emit(afterSubscription)

        assertEquals(afterSubscription, received.await())
    }
}
