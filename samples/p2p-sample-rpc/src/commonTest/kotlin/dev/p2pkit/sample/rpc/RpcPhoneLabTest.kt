package dev.p2pkit.sample.rpc

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class RpcPhoneLabTest {
    private fun pins(): List<String> {
        val alphabet = "abcdefghijklmnopqrstuvwxyz234567"
        return List(128) { "p2f1-${alphabet[it / 32]}${alphabet[it % 32]}" + "a".repeat(50) }
    }

    @Test
    fun importRequiresExactly128DistinctWellFormedPins() {
        val pins = pins()
        assertEquals(128, RpcPhoneLab.parseCapacityPins(pins.joinToString("\n")).size)
        assertFailsWith<IllegalArgumentException> { RpcPhoneLab.parseCapacityPins("") }
        assertFailsWith<IllegalArgumentException> { RpcPhoneLab.parseCapacityPins(pins.dropLast(1).joinToString("\n")) }
        assertFailsWith<IllegalArgumentException> {
            RpcPhoneLab.parseCapacityPins((pins.dropLast(1) + pins.first()).joinToString("\n"))
        }
        assertFailsWith<IllegalArgumentException> {
            RpcPhoneLab.parseCapacityPins((pins.dropLast(1) + "not-a-pin").joinToString("\n"))
        }
        assertFailsWith<IllegalArgumentException> { RpcPhoneLab.parseCapacityPins("a".repeat(8193)) }
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
