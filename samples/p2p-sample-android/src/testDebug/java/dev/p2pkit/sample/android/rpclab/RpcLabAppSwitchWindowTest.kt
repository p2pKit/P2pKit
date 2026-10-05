package dev.p2pkit.sample.android.rpclab

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class RpcLabAppSwitchWindowTest {
    private class Execution : RpcLabAppSwitchWindow.Execution {
        var admitted = true
        var synchronousFailure = false
        var beforeReturn: () -> Unit = {}
        var starts = 0
        var stops = 0
        val callbacks = mutableListOf<() -> Unit>()
        override fun begin(expired: () -> Unit): Boolean {
            starts++
            callbacks += expired
            if (synchronousFailure) expired()
            beforeReturn()
            return admitted
        }
        override fun end() { stops++ }
    }

    private class Fixture {
        var now = 1_000L
        val tasks = mutableListOf<() -> Unit>()
        val delays = mutableListOf<Long>()
        val expired = mutableListOf<Any>()
        var cancelled = 0
        val execution = Execution()
        val window = RpcLabAppSwitchWindow({ now }, { delay, block ->
            delays += delay
            tasks += block
            val cancel: () -> Unit = { cancelled++ }
            cancel
        }, execution) { expired += it }
    }

    @Test
    fun onlyAlreadyCreatedIdleOrdinaryRolesAreEligible() {
        assertTrue(RpcLabAppSwitchWindow.eligible(true, true, false, false, false, false, false))
        for (index in 0..6) {
            val values = mutableListOf(true, true, false, false, false, false, false)
            values[index] = !values[index]
            assertFalse(RpcLabAppSwitchWindow.eligible(values[0], values[1], values[2], values[3],
                values[4], values[5], values[6]), "Unsafe input $index cannot get an app-switch lease")
        }
    }

    @Test
    fun sameOwnerReturnsBeforeOriginalDeadlineOnlyAfterSynchronousNetworkValidation() {
        val f = Fixture()
        val owner = Any()
        assertTrue(f.window.begin(owner))
        assertEquals(listOf(25_000L), f.delays)
        f.now += 24_999
        var validations = 0
        assertTrue(f.window.resume(owner) { validations++; true })
        assertEquals(1, validations)
        assertEquals(1, f.execution.starts)
        assertEquals(1, f.execution.stops)
        assertEquals(1, f.cancelled)
        assertFalse(f.window.active)
        assertTrue(f.expired.isEmpty())
    }

    @Test
    fun returningAtTheDeadlineExpiresWithoutRevalidatingOrRestarting() {
        val f = Fixture()
        val owner = Any()
        assertTrue(f.window.begin(owner))
        f.now += 25_000
        var validations = 0
        assertFalse(f.window.resume(owner) { validations++; true })
        assertEquals(0, validations)
        assertSame(owner, f.expired.single())
        assertFalse(f.window.active)
        assertEquals(1, f.execution.starts)
    }

    @Test
    fun repeatedPauseCannotExtendTheWindowAndStaleCallbacksCannotExpireItsReplacement() {
        val f = Fixture()
        val owner = Any()
        assertTrue(f.window.begin(owner))
        f.now += 10_000
        assertFalse(f.window.begin(owner))
        assertEquals(listOf(25_000L), f.delays)
        val timer = f.tasks.single()
        val service = f.execution.callbacks.single()
        assertTrue(f.window.resume(owner) { true })
        val next = Any()
        assertTrue(f.window.begin(next))
        timer()
        service()
        assertTrue(f.window.active)
        assertTrue(f.expired.isEmpty())
        f.tasks.last()()
        assertSame(next, f.expired.single())
        assertFalse(f.window.active)
    }

    @Test
    fun deniedExecutionOrSynchronousServiceFailureCannotRetainAnUnbackedRole() {
        val denied = Fixture()
        denied.execution.admitted = false
        assertFalse(denied.window.begin(Any()))
        assertFalse(denied.window.active)
        assertEquals(1, denied.execution.stops)
        assertEquals(1, denied.cancelled)
        val failed = Fixture()
        failed.execution.synchronousFailure = true
        val owner = Any()
        assertFalse(failed.window.begin(owner))
        assertFalse(failed.window.active)
        assertSame(owner, failed.expired.single())
        assertEquals(1, failed.execution.stops)
    }

    @Test
    fun serviceLossOrTaskRemovalExpiresOnlyItsExactOwnerOnce() {
        val f = Fixture()
        val owner = Any()
        assertTrue(f.window.begin(owner))
        f.execution.callbacks.single()()
        f.execution.callbacks.single()()
        f.tasks.single()()
        assertSame(owner, f.expired.single())
        assertFalse(f.window.active)
        assertEquals(1, f.execution.stops)
    }

    @Test
    fun stopOrDestructionCancelsTheLeaseWithoutTouchingALaterOwner() {
        val f = Fixture()
        assertTrue(f.window.begin(Any()))
        f.window.close()
        f.window.close()
        f.tasks.single()()
        f.execution.callbacks.single()()
        assertFalse(f.window.active)
        assertTrue(f.expired.isEmpty())
        assertEquals(1, f.execution.stops)
        assertEquals(1, f.cancelled)
    }

    @Test
    fun wrongOwnerAndFailedNetworkCheckCannotResume() {
        for (sameOwner in listOf(false, true)) {
            val f = Fixture()
            val owner = Any()
            assertTrue(f.window.begin(owner))
            var checks = 0
            assertFalse(f.window.resume(if (sameOwner) owner else Any()) { checks++; false })
            assertEquals(if (sameOwner) 1 else 0, checks)
            assertSame(owner, f.expired.single())
        }
    }

    @Test
    fun synchronousTimerExpiryCannotStartExecutionOrLeakItsCancellation() {
        val execution = Execution()
        var cancelled = 0
        var expired = 0
        val window = RpcLabAppSwitchWindow({ 0L }, { _, callback ->
            callback()
            val cancel: () -> Unit = { cancelled++ }
            cancel
        }, execution) { expired++ }
        assertFalse(window.begin(Any()))
        assertFalse(window.active)
        assertEquals(0, execution.starts)
        assertEquals(1, cancelled)
        assertEquals(1, expired)
    }

    @Test
    fun executionAdmissionCannotReturnAnAlreadyExpiredWindow() {
        val f = Fixture()
        val owner = Any()
        f.execution.beforeReturn = { f.now += 25_000 }
        assertFalse(f.window.begin(owner))
        assertFalse(f.window.active)
        assertEquals(1, f.execution.stops)
        assertSame(owner, f.expired.single())
    }

    @Test
    fun synchronousNetworkRevocationDuringReturnCannotResurrectTheLease() {
        val f = Fixture()
        val owner = Any()
        assertTrue(f.window.begin(owner))
        assertFalse(f.window.resume(owner) { f.window.close(); true })
        assertFalse(f.window.active)
        assertEquals(1, f.execution.stops)
    }
}
