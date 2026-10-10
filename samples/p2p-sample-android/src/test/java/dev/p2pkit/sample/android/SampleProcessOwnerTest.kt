package dev.p2pkit.sample.android

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class SampleProcessOwnerTest {
    @Test fun ordinaryReservationBlocksBothLanesUntilExactRelease() {
        val owner = SampleProcessOwner()
        val token = assertNotNull(owner.acquire(SampleProcessOwner.Lane.Ordinary))
        assertNull(owner.acquire(SampleProcessOwner.Lane.Ordinary))
        assertNull(owner.acquire(SampleProcessOwner.Lane.RpcSection))
        assertTrue(owner.release(token))
        assertFalse(owner.release(token))
        assertNotNull(owner.acquire(SampleProcessOwner.Lane.RpcSection))
    }

    @Test fun rpcUiReservationBlocksOrdinaryEvenBeforeAnRpcRuntimeExists() {
        val owner = SampleProcessOwner()
        val token = assertNotNull(owner.acquire(SampleProcessOwner.Lane.RpcSection))
        assertNull(owner.acquire(SampleProcessOwner.Lane.Ordinary) { false })
        assertNull(owner.acquire(SampleProcessOwner.Lane.RpcSection))
        assertTrue(owner.release(token))
    }

    @Test fun orphanRpcRuntimeBlocksOrdinaryButAllowsItsExplicitRecoverySection() {
        val owner = SampleProcessOwner()
        assertNull(owner.acquire(SampleProcessOwner.Lane.Ordinary) { true })
        val recovery = assertNotNull(owner.acquire(SampleProcessOwner.Lane.RpcSection) { true })
        assertTrue(owner.release(recovery))
        val ordinary = assertNotNull(owner.acquire(SampleProcessOwner.Lane.Ordinary) { false })
        assertEquals(SampleProcessOwner.Lane.Ordinary, ordinary.lane)
    }

    @Test fun staleLeaseCannotReleaseOrExecuteUnderReplacementAdmission() {
        val owner = SampleProcessOwner()
        val previous = assertNotNull(owner.acquire(SampleProcessOwner.Lane.RpcSection))
        assertTrue(owner.release(previous))
        val current = assertNotNull(owner.acquire(SampleProcessOwner.Lane.RpcSection))
        assertFalse(owner.release(previous))
        var called = false
        assertFailsWith<IllegalStateException> { owner.withCurrent(previous) { called = true } }
        assertFalse(called)
        assertSame(current, owner.state.value)
        assertTrue(owner.withCurrent(current) { true })
    }

    @Test fun throwingBridgeKeepsItsExactOwnerInsteadOfSilentlyReleasingAdmission() {
        val owner = SampleProcessOwner()
        val token = assertNotNull(owner.acquire(SampleProcessOwner.Lane.RpcSection))
        assertFailsWith<IllegalStateException> { owner.withCurrent(token) { error("synthetic creation failure") } }
        assertSame(token, owner.state.value)
        assertTrue(owner.release(token))
    }
}
