package dev.p2pkit.sample.rpc

import kotlinx.coroutines.Job
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

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
}
