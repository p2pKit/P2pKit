package dev.p2pkit.sample.rpc

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.test.assertSame
import kotlin.test.assertNull

@OptIn(ExperimentalCoroutinesApi::class)
class RpcPhoneLabTest {
    private class ReportingError(message: String) : Error(message) { val retainedOwner = Any() }

    private fun pins(count: Int = 128): List<String> {
        val alphabet = "abcdefghijklmnopqrstuvwxyz234567"
        return List(count) { "p2f1-${alphabet[it / 32]}${alphabet[it % 32]}" + "a".repeat(50) }
    }

    @Test
    fun importRequiresExactly128Or256DistinctWellFormedPins() {
        val pins = pins()
        assertEquals(128, RpcPhoneLab.parseCapacityPins(pins.joinToString("\n")).size)
        assertEquals(256, RpcPhoneLab.parseCapacityPins(pins(256).joinToString("\n")).size)
        assertEquals(14847, pins(256).joinToString("\n").encodeToByteArray().size)
        for (count in listOf(129, 255, 257)) {
            assertFailsWith<IllegalArgumentException> { RpcPhoneLab.parseCapacityPins(pins(count).joinToString("\n")) }
        }
        assertFailsWith<IllegalArgumentException> { RpcPhoneLab.parseCapacityPins("") }
        assertFailsWith<IllegalArgumentException> { RpcPhoneLab.parseCapacityPins(pins.dropLast(1).joinToString("\n")) }
        assertFailsWith<IllegalArgumentException> {
            RpcPhoneLab.parseCapacityPins((pins.dropLast(1) + pins.first()).joinToString("\n"))
        }
        assertFailsWith<IllegalArgumentException> {
            RpcPhoneLab.parseCapacityPins((pins.dropLast(1) + "not-a-pin").joinToString("\n"))
        }
        assertFailsWith<IllegalArgumentException> { RpcPhoneLab.parseCapacityPins("a".repeat(16385)) }
    }

    @Test
    fun roleChangesOnlyTheListenPortAndNeverRelaxThePolicy() {
        val settings = RpcPhoneSettings("192.168.14.0/24", "wlan0", "192.168.14.2", 48123)
        assertEquals(48123, settings.policy(host = true).listenPort)
        assertEquals(0, settings.policy(host = false).listenPort)
        assertTrue(settings.policy(host = false).allows("192.168.14.3"))
        assertFalse(settings.policy(host = false).allows("8.8.8.8"))
        assertFailsWith<IllegalArgumentException> { RpcPhoneSettings("192.168.14.0/24", "wlan0", "192.168.14.2", 22) }
        assertFailsWith<IllegalArgumentException> {
            RpcPhoneSettings("0.0.0.0/0", "wlan0", "192.168.14.2", 48123).policy(host = true)
        }
        assertFailsWith<IllegalArgumentException> {
            RpcPhoneSettings("192.168.14.0/24", "utun0", "192.168.14.2", 48123).policy(host = false)
        }
    }

    @Test
    fun nativeOperationHandleCancelsTheOwnedKotlinJob() {
        val job = Job()
        val operation = RpcPhoneOperation(job)
        assertTrue(operation.active)
        operation.cancel()
        operation.cancel()
        assertTrue(job.isCancelled)
        assertFalse(operation.active)
    }

    @Test
    fun cancellingBeforeFirstDispatchCompletesExactlyOnceAndReleasesAdmission() = runTest {
        val busy = MutableStateFlow(false)
        val replies = mutableListOf<String>()
        var actions = 0
        val operation = startPhoneOperation(backgroundScope, busy, { "cancelled" }, { "failed" }, replies::add) {
            actions++
            "success"
        }
        operation.cancel()
        operation.cancel()
        runCurrent()
        assertEquals(0, actions)
        assertEquals(listOf("cancelled"), replies)
        assertFalse(busy.value)
        assertFalse(operation.active)
    }

    @Test
    fun runningCancellationAndParallelAdmissionHaveOneTerminalCallback() = runTest {
        val busy = MutableStateFlow(false)
        val replies = mutableListOf<String>()
        val operation = startPhoneOperation(backgroundScope, busy, { "cancelled" }, { "failed" }, replies::add) {
            awaitCancellation()
        }
        runCurrent()
        assertFailsWith<IllegalStateException> {
            startPhoneOperation(backgroundScope, busy, { "cancelled" }, { "failed" }, replies::add) { "duplicate" }
        }
        operation.cancel()
        runCurrent()
        assertEquals(listOf("cancelled"), replies)
        assertFalse(busy.value)
        assertFalse(operation.active)
    }

    @Test
    fun fatalOperationNotifiesItsCallbackInsteadOfStrandingTheForegroundOwner() = runTest {
        val busy = MutableStateFlow(false)
        val replies = mutableListOf<String>()
        val escaped = mutableListOf<Throwable>()
        val failure = ReportingError("synthetic private native reporting error")
        val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler) +
            CoroutineExceptionHandler { _, cause -> escaped += cause })
        try {
            val operation = startPhoneOperation(scope, busy, { "cancelled" }, { "sanitized" }, replies::add) {
                throw failure
            }
            runCurrent()
            assertFalse(operation.active)
            assertEquals(listOf("sanitized"), replies)
            assertTrue(escaped.isEmpty(), "An owned native failure must not escape to a global log handler")
        } finally { scope.cancel() }
    }

    @Test
    fun fatalOperationSealsBothSlotsBeforeCallbackWithoutLosingTheOriginalError() = runTest {
        val failures = PhoneOperationFailureState()
        val busy = MutableStateFlow(false)
        val siblingBusy = MutableStateFlow(false)
        val failure = ReportingError("synthetic private native reporting error")
        val replies = mutableListOf<String>()
        val operation = startPhoneOperation(backgroundScope, busy, { "cancelled" }, { problem ->
            assertSame(failures.terminal, problem)
            assertNull(problem.cause)
            assertFalse(problem.toString().contains("synthetic private"))
            "sanitized"
        }, { result ->
            assertSame(failure, failures.originalFailure)
            for (slot in listOf(busy, siblingBusy)) {
                assertSame(failures.terminal, assertFailsWith<PhoneOperationTerminalFailure> {
                    startPhoneOperation(backgroundScope, slot, { "cancelled" }, { "failed" }, {}, failures) {
                        error("No effect may run after fatal admission was sealed")
                    }
                })
            }
            replies += result
        }, failures) { throw failure }
        runCurrent()
        assertEquals(listOf("sanitized"), replies)
        assertFalse(operation.active)
        assertFalse(busy.value)
        assertFalse(siblingBusy.value)
        assertSame(failure, failures.terminal.originalFailure)
    }

    @Test
    fun cancellationRacingWithFatalCleanupStillNotifiesOnceAndRetainsFailure() = runTest {
        val failures = PhoneOperationFailureState()
        val busy = MutableStateFlow(false)
        val replies = mutableListOf<String>()
        val failure = ReportingError("synthetic cancellation cleanup failure")
        val operation = startPhoneOperation(backgroundScope, busy, { "cancelled" }, { "sanitized" },
            replies::add, failures) {
            try { awaitCancellation() } finally { throw failure }
        }
        runCurrent()
        operation.cancel()
        operation.cancel()
        runCurrent()
        assertEquals(listOf("cancelled"), replies) // Existing cancellation-first terminal contract is unchanged.
        assertSame(failure, failures.originalFailure)
        assertFalse(operation.active)
        assertFalse(busy.value)
    }

    @Test
    fun previouslyAdmittedSiblingRetiresAndAQueuedSiblingCannotEnterAfterFatalFailure() = runTest {
        val failures = PhoneOperationFailureState()
        val callBusy = MutableStateFlow(false)
        val controlBusy = MutableStateFlow(false)
        val replies = mutableListOf<String>()
        var retired = false
        val sibling = startPhoneOperation(backgroundScope, callBusy, { "cancelled" }, { "sanitized" },
            replies::add, failures) {
            try { awaitCancellation() } finally { withContext(NonCancellable) { retired = true } }
        }
        runCurrent()
        startPhoneOperation(backgroundScope, controlBusy, { "cancelled" }, { "sanitized" },
            replies::add, failures) { throw ReportingError("synthetic fatal control operation") }
        runCurrent()
        sibling.cancel()
        runCurrent()
        assertTrue(retired)
        assertEquals(listOf("sanitized", "cancelled"), replies)
        assertFalse(callBusy.value)
        assertFalse(controlBusy.value)

        val queuedFailures = PhoneOperationFailureState()
        var effects = 0
        val queuedReplies = mutableListOf<String>()
        startPhoneOperation(backgroundScope, MutableStateFlow(false), { "cancelled" }, { "sanitized" },
            queuedReplies::add, queuedFailures) { throw ReportingError("synthetic earlier dispatched error") }
        startPhoneOperation(backgroundScope, MutableStateFlow(false), { "cancelled" }, { "sanitized" },
            queuedReplies::add, queuedFailures) { effects++; "incorrect success" }
        runCurrent()
        assertEquals(0, effects)
        assertEquals(listOf("sanitized", "sanitized"), queuedReplies)
    }

    @Test
    fun failedOperationStillRunsPhysicalRetirementAndKeepsBothOriginalFailures() = runTest {
        for (cleanupFails in listOf(false, true)) {
            val failures = PhoneOperationFailureState()
            val original = ReportingError("synthetic operation failure")
            val cleanup = ReportingError("synthetic cleanup failure")
            failures.retain(original)
            failures.retain(ReportingError("synthetic later sibling failure"))
            var physicalCloses = 0
            val observed = assertFailsWith<PhoneOperationTerminalFailure> {
                failures.retire {
                    assertSame(original, failures.originalFailure)
                    physicalCloses++
                    if (cleanupFails) throw cleanup
                }
            }
            assertSame(failures.terminal, observed)
            assertSame(original, observed.originalFailure)
            assertSame(if (cleanupFails) cleanup else null, observed.retirementFailure)
            assertEquals(1, physicalCloses)
            assertTrue(original.suppressedExceptions.isEmpty())
            assertNull(observed.cause)
        }
    }

    @Test
    fun directEffectsRetainFatalOwnershipAndSealCallbackEntryWithoutRunningAnotherEffect() = runTest {
        val failures = PhoneOperationFailureState()
        val original = ReportingError("synthetic direct native operation error")
        var effects = 0
        val observed = assertFailsWith<PhoneOperationTerminalFailure> {
            failures.effect { effects++; throw original }
        }
        assertSame(failures.terminal, observed)
        assertSame(original, observed.originalFailure)
        assertNull(observed.cause)
        assertSame(observed, assertFailsWith<PhoneOperationTerminalFailure> {
            failures.effect { effects++ }
        })
        assertSame(observed, assertFailsWith<PhoneOperationTerminalFailure> {
            startPhoneOperation(backgroundScope, MutableStateFlow(false), { "cancelled" }, { "failed" },
                {}, failures) { effects++; "incorrect success" }
        })
        runCurrent()
        assertEquals(1, effects)
    }

    @Test
    fun directOrdinaryFailureAndCancellationPreserveTheirOriginalContractWithoutFatalPoisoning() = runTest {
        for (original in listOf(IllegalStateException("synthetic ordinary failure"),
                CancellationException("synthetic cancellation"))) {
            val failures = PhoneOperationFailureState()
            val observed = assertFailsWith<Exception> { failures.effect { throw original } }
            assertSame(original, observed)
            assertNull(failures.originalFailure)
            assertEquals("still available", failures.effect { "still available" })
            var closed = 0
            failures.retire { closed++ }
            assertEquals(1, closed)
        }
    }

    @Test
    fun completedAndFailedCallbacksReleaseAdmissionWithoutLeakingExceptionText() = runTest {
        val busy = MutableStateFlow(false)
        val replies = mutableListOf<String>()
        val first = startPhoneOperation(backgroundScope, busy, { "cancelled" }, { "sanitized" }, replies::add) { "ok" }
        runCurrent()
        first.cancel()
        val second = startPhoneOperation(backgroundScope, busy, { "cancelled" }, { "sanitized" }, replies::add) {
            error("untrusted synthetic details")
        }
        runCurrent()
        assertEquals(listOf("ok", "sanitized"), replies)
        assertFalse(busy.value)
        assertFalse(second.active)
    }
}
