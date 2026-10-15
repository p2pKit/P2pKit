package dev.p2pkit.sample.android

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SampleRpcOpenRequestTest {
    @Test fun onlyTheExactFixedActionCanRequestNavigation() {
        val request = SampleRpcOpenRequest()
        for (input in listOf(null, "", "rpc", "$SAMPLE_OPEN_RPC_ACTION?host=true", " $SAMPLE_OPEN_RPC_ACTION")) {
            request.offer(input)
            assertFalse(request.consume(true) { error("Unknown action must not navigate") })
        }
        request.offer(SAMPLE_OPEN_RPC_ACTION)
        assertTrue(request.consume(true) {})
    }

    @Test fun backgroundRequestWaitsForResumeAndIsConsumedExactlyOnce() {
        val request = SampleRpcOpenRequest()
        var opens = 0
        request.offer(SAMPLE_OPEN_RPC_ACTION)
        assertFalse(request.consume(false) { opens++ })
        assertEquals(0, opens)
        assertTrue(request.consume(true) { opens++ })
        assertFalse(request.consume(true) { opens++ })
        assertEquals(1, opens)
    }

    @Test fun burstInputsAreBoundedAndNeverQueueAnAdmissionRetry() {
        val request = SampleRpcOpenRequest()
        repeat(10_000) { request.offer(SAMPLE_OPEN_RPC_ACTION) }
        var attempts = 0
        assertTrue(request.consume(true) { attempts++ /* Synthetic admission refusal: no deferred replay. */ })
        repeat(10_000) { assertFalse(request.consume(true) { attempts++ }) }
        assertEquals(1, attempts)
    }

    @Test fun throwingNavigationStillConsumesItsRequestBeforeDispatch() {
        val request = SampleRpcOpenRequest()
        request.offer(SAMPLE_OPEN_RPC_ACTION)
        assertFailsWith<IllegalStateException> { request.consume(true) { error("synthetic failure") } }
        assertFalse(request.consume(true) { error("No automatic retry") })
    }
}
