package dev.p2pkit.transport.lan

import java.net.NetworkInterface
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/** Opt-in real JNI bounds/ABI checks only. Invalid inputs stop BEFORE any DNSService operation. */
class MacBonjourNativeIntegrationTest {
    @Test fun verifiedLibraryRejectsMalformedJniInputsWithoutOpeningBonjour() {
        assertNotNull(MacLanNativeLoader.configuredBinding(OrganizationLan(listOf("10.0.0.0/8"), "en0", "10.1.2.3")))
        assertEquals(1, MacBonjourNative.abi())
        val index = NetworkInterface.getByName("lo0").index
        val out = LongArray(1)
        for ((operation, profile, name) in listOf(
            Triple(0, 2, byteArrayOf()), Triple(1, 0, byteArrayOf()), Triple(1, 2, byteArrayOf(1)),
            Triple(3, 2, byteArrayOf(0)), Triple(3, 2, ByteArray(64) { 65 }),
        )) {
            assertTrue(MacBonjourNative.open(index, operation, profile, name, 0, byteArrayOf(), out) != 0)
            assertEquals(0L, out[0])
        }
        assertTrue(MacBonjourNative.open(0, 1, 2, byteArrayOf(), 0, byteArrayOf(), out) != 0)
        assertTrue(MacBonjourNative.open(index, 1, 2, byteArrayOf(), 0, ByteArray(1301), out) != 0)
        assertTrue(MacBonjourNative.open(index, 1, 2, byteArrayOf(), 0, byteArrayOf(), LongArray(2)) != 0)
        assertTrue(MacBonjourNative.poll(0, 0, ByteArray(2048)) < 0)
        assertTrue(MacBonjourNative.poll(0, 0, ByteArray(2047)) < 0)
        assertTrue(MacBonjourNative.poll(0, 101, ByteArray(2048)) < 0)
        assertTrue(MacBonjourNative.close(0) != 0)
    }
}
