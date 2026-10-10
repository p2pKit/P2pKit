package dev.p2pkit.sample.rpc.profile

import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class WindowsProfilePeImageTest {
    @Test fun acceptsBoundedStructuralFixtureWithoutClaimingNativeOrSignatureQualification() {
        val fixture = fixture()
        val result = WindowsProfilePeImage.verify(fixture)
        assertEquals(setOf("kernel32.dll"), result.imports)
        assertEquals(WindowsProfilePeImage.expectedExports, result.exports)
        assertEquals(MessageDigest.getInstance("SHA-256").digest(fixture).hex(), result.sha256)
        assertFalse(result.hasCertificateTable)
    }

    @Test fun rejectsTruncationOversizedImagesAndUntrustedHeaderOffsets() {
        val original = fixture()
        for (size in listOf(0, 63, 511, 512, 1024, original.size - 1)) rejected(original.copyOf(size))
        rejected(ByteArray(WindowsProfilePeImage.MAXIMUM_BYTES + 1))
        for (offset in listOf(0L, 63L, 0xffffffffL)) rejected(fixture().apply { put32(0x3c, offset) })
    }

    @Test fun rejectsWrongArchitecturePeKindExecutableAndMissingMitigations() {
        rejected(fixture().apply { put16(0x84, 0x14c) })
        rejected(fixture().apply { put16(OPTIONAL, 0x10b) })
        rejected(fixture().apply { put16(0x96, 0x22) })
        rejected(fixture().apply { put16(0x96, 0x2023) })
        for (flags in listOf(0, 0x40, 0x120, 0x140)) rejected(fixture().apply { put16(OPTIONAL + 70, flags) })
        rejected(fixture().apply { put32(OPTIONAL + 108, 17) })
    }

    @Test fun rejectsOverlappingSectionsAndVirtualBytesWithoutRawBacking() {
        rejected(fixture().apply { put32(SECTIONS + 40 + 20, 0x400) })
        rejected(fixture().apply { put32(SECTIONS + 40 + 12, 0x1000) })
        rejected(fixture().apply { put32(SECTIONS + 40 + 8, 0x1000); put32(OPTIONAL + 112, 0x2f00) })
        rejected(fixture().apply { put32(SECTIONS + 20, 0x200) })
        rejected(fixture().apply { put32(SECTIONS + 16, 0xffffffff) })
        rejected(fixture().apply { put32(OPTIONAL + 36, 513) })
    }

    @Test fun rejectsWritableExecutableSectionsAndNonExecutableOrForwardedExports() {
        rejected(fixture().apply { put32(SECTIONS + 36, 0xe0000020) })
        rejected(fixture().apply { put32(0x650, 0x2600) })
        rejected(fixture().apply { put32(0x650, 0x2030) })
        rejected(fixture().apply { put32(OPTIONAL + 16, 0x2600) })
    }

    @Test fun rejectsUnapprovedPathNamedAndDuplicateImports() {
        rejected(fixture().apply { ascii(0xa40, "badcode.dll") })
        rejected(fixture().apply { ascii(0xa40, "../evil.dll") })
        rejected(fixture().apply { ascii(0xa40, "C:evil.dll") })
        rejected(fixture().apply {
            put32(OPTIONAL + 116 + 8, 60)
            copyInto(this, 0xa14, 0xa00, 0xa14)
        })
        rejected(fixture().apply { put32(0xa0c, 0x2fff) })
    }

    @Test fun rejectsDelayBoundManagedAndMalformedImportDirectories() {
        for (index in listOf(11, 13, 14, 15)) rejected(fixture().apply { directory(index, 0x2400, 40) })
        rejected(fixture().apply { directory(1, 0x2400, 39) })
        rejected(fixture().apply { put32(0xa14, 1) })
        rejected(fixture().apply { put32(0xa04, 1) })
        rejected(fixture().apply { put32(0xa00, 0) })
    }

    @Test fun rejectsOrdinalImportsIatSubstitutionMissingTerminationAndBadNames() {
        rejected(fixture().apply { put64(0xa60, Long.MIN_VALUE or 1); put64(0xa80, Long.MIN_VALUE or 1) })
        rejected(fixture().apply { put64(0xa80, 0x24b0) })
        rejected(fixture().apply { put64(0xa68, 0x24a0); put64(0xa88, 0x24a0) })
        rejected(fixture().apply { ascii(0xaa2, "Close.Handle") })
        rejected(fixture().apply { directory(12, 0x2480, 8) })
        rejected(fixture().apply { fill('X'.code.toByte(), 0xaa2, 0xb30) })
    }

    @Test fun requiresTheExactVersionedJniExportsAndDistinctOrdinals() {
        rejected(fixture().apply { ascii(0x6a0, "Java_foreign_abi") })
        rejected(fixture().apply { put32(0x600 + 24, 7) })
        rejected(fixture().apply { put32(0x600 + 20, 9) })
        rejected(fixture().apply { put16(0x692, 0) })
        rejected(fixture().apply { put16(0x690, 8) })
        rejected(fixture().apply { put32(0x674, get32(0x670)) })
        rejected(fixture().apply { ascii(0x630, "other-profile.dll") })
    }

    @Test fun rejectsUnboundedStringsArraysAndArithmeticWraparound() {
        rejected(fixture().apply { put32(0x670, 0xffffffff) })
        rejected(fixture().apply { put32(0x600 + 28, 0xfffffff0) })
        rejected(fixture().apply { directory(0, 0xfffffff0, 65536) })
        rejected(fixture().apply { put32(SECTIONS + 12, 0xfffff000) })
        rejected(fixture().apply { fill('Q'.code.toByte(), 0x6a0, 0x6a0 + 193) })
    }

    @Test fun certificatePresenceIsNotSignatureValidationAndOverlaysAreRejected() {
        val unsigned = fixture()
        rejected(unsigned.copyOf(unsigned.size + 8))
        val certificate = unsigned.copyOf(unsigned.size + 16).apply {
            directory(4, unsigned.size.toLong(), 16)
            put32(unsigned.size, 16)
            put16(unsigned.size + 4, 0x200)
            put16(unsigned.size + 6, 2)
        }
        // Deliberately synthetic certificate bytes: only table framing, never Authenticode validity.
        assertTrue(WindowsProfilePeImage.verify(certificate).hasCertificateTable)
        rejected(certificate.copyOf().apply { put32(unsigned.size, 17) })
        rejected(certificate.copyOf().apply { put16(unsigned.size + 6, 1) })
        rejected(certificate.copyOf().apply { directory(4, 0x1000, 16) })
        rejected(certificate.copyOf().apply { put32(unsigned.size, 9); this[unsigned.size + 10] = 1 })
    }

    @Test fun callerMutationDoesNotAlterReturnedObservationOrExportPolicy() {
        val bytes = fixture()
        val first = WindowsProfilePeImage.verify(bytes)
        bytes.fill(0)
        assertEquals(WindowsProfilePeImage.verify(fixture()), first)
        (WindowsProfilePeImage.expectedExports as MutableSet<String>).clear()
        assertEquals(8, WindowsProfilePeImage.expectedExports.size)
    }

    private fun rejected(bytes: ByteArray) {
        assertFailsWith<IllegalArgumentException> { WindowsProfilePeImage.verify(bytes) }
    }
    private fun ByteArray.hex(): String = joinToString("") { "%02x".format(it) }
    private fun ByteArray.put16(at: Int, value: Int) {
        this[at] = value.toByte(); this[at + 1] = (value ushr 8).toByte()
    }
    private fun ByteArray.put32(at: Int, value: Long) {
        for (i in 0..3) this[at + i] = (value ushr (i * 8)).toByte()
    }
    private fun ByteArray.put64(at: Int, value: Long) {
        for (i in 0..7) this[at + i] = (value ushr (i * 8)).toByte()
    }
    private fun ByteArray.get32(at: Int): Long = (0..3).fold(0L) { value, i ->
        value or ((this[at + i].toLong() and 255) shl (i * 8))
    }
    private fun ByteArray.ascii(at: Int, value: String) {
        value.toByteArray(Charsets.US_ASCII).copyInto(this, at); this[at + value.length] = 0
    }
    private fun ByteArray.directory(index: Int, rva: Long, size: Long) {
        put32(OPTIONAL + 112 + index * 8, rva); put32(OPTIONAL + 116 + index * 8, size)
    }
    private fun fixture(): ByteArray = ByteArray(0x1200).apply {
        put16(0, 0x5a4d); put32(0x3c, 0x80); put32(0x80, 0x4550)
        put16(0x84, 0x8664); put16(0x86, 3); put16(0x94, 240); put16(0x96, 0x2022)
        put16(OPTIONAL, 0x20b); put32(OPTIONAL + 16, 0x1000); put64(OPTIONAL + 24, 0x180000000)
        put32(OPTIONAL + 32, 0x1000); put32(OPTIONAL + 36, 0x200)
        put32(OPTIONAL + 56, 0x4000); put32(OPTIONAL + 60, 0x400)
        put16(OPTIONAL + 68, 3); put16(OPTIONAL + 70, 0x160); put32(OPTIONAL + 108, 16)
        directory(0, 0x2000, 0x400); directory(1, 0x2400, 40); directory(5, 0x3000, 8)
        directory(12, 0x2480, 16)
        fun section(index: Int, name: String, va: Long, offset: Long, length: Long, flags: Long) {
            val at = SECTIONS + index * 40
            ascii(at, name); put32(at + 8, length); put32(at + 12, va)
            put32(at + 16, length); put32(at + 20, offset); put32(at + 36, flags)
        }
        section(0, ".text", 0x1000, 0x400, 0x200, 0x60000020)
        section(1, ".rdata", 0x2000, 0x600, 0xa00, 0x40000040)
        section(2, ".reloc", 0x3000, 0x1000, 0x200, 0x42000040)
        put32(0x60c, 0x2030); put32(0x610, 1); put32(0x614, 8); put32(0x618, 8)
        put32(0x61c, 0x2050); put32(0x620, 0x2070); put32(0x624, 0x2090)
        ascii(0x630, "p2pkit-windows-profile.dll")
        var string = 0x6a0
        WindowsProfilePeImage.expectedExports.sorted().forEachIndexed { index, value ->
            put32(0x650 + index * 4, 0x1000L + index)
            put32(0x670 + index * 4, 0x2000L + string - 0x600)
            put16(0x690 + index * 2, index)
            ascii(string, value); string += value.length + 1
        }
        check(string < 0xa00)
        put32(0xa00, 0x2460); put32(0xa0c, 0x2440); put32(0xa10, 0x2480)
        ascii(0xa40, "KERNEL32.dll"); put64(0xa60, 0x24a0); put64(0xa80, 0x24a0)
        ascii(0xaa2, "CloseHandle")
    }

    companion object {
        private const val OPTIONAL = 0x98
        private const val SECTIONS = OPTIONAL + 240
    }
}
