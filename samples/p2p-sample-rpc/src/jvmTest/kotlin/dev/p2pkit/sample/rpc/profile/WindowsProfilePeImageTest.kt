package dev.p2pkit.sample.rpc.profile

import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class WindowsProfilePeImageTest {
    @Test fun acceptsExplicitProtectedChildDirectoryCreationExport() {
        val child = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_createChildDirectory"
        val expected = WindowsProfilePeImage.expectedExports + child
        val result = WindowsProfilePeImage.verify(WindowsProfilePeFixture.create(expected))
        assertEquals(expected, result.exports)
        assertEquals(16, result.exports.size)
        assertEquals(6, WindowsProfilePeImage.ABI)
    }

    @Test fun rejectsPriorCustodyExportInventoryWithoutChildCreation() {
        val prior = WindowsProfilePeImage.expectedExports.filterNot { it.endsWith("_createChildDirectory") }.toSet()
        rejected(WindowsProfilePeFixture.create(prior))
    }

    @Test fun acceptsBoundedStructuralFixtureWithoutClaimingNativeOrSignatureQualification() {
        assertEquals(6, WindowsProfilePeImage.ABI)
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
        rejected(fixture().apply { ascii(0xc40, "badcode.dll") })
        rejected(fixture().apply { ascii(0xc40, "../evil.dll") })
        rejected(fixture().apply { ascii(0xc40, "C:evil.dll") })
        rejected(fixture().apply {
            put32(OPTIONAL + 116 + 8, 60)
            copyInto(this, 0xc14, 0xc00, 0xc14)
        })
        rejected(fixture().apply { put32(0xc0c, 0x2fff) })
    }

    @Test fun rejectsDelayBoundManagedAndMalformedImportDirectories() {
        for (index in listOf(11, 13, 14, 15)) rejected(fixture().apply { directory(index, 0x2600, 40) })
        rejected(fixture().apply { directory(1, 0x2600, 39) })
        rejected(fixture().apply { put32(0xc14, 1) })
        rejected(fixture().apply { put32(0xc04, 1) })
        rejected(fixture().apply { put32(0xc00, 0) })
    }

    @Test fun rejectsOrdinalImportsIatSubstitutionMissingTerminationAndBadNames() {
        rejected(fixture().apply { put64(0xc60, Long.MIN_VALUE or 1); put64(0xc80, Long.MIN_VALUE or 1) })
        rejected(fixture().apply { put64(0xc80, 0x26b0) })
        rejected(fixture().apply { put64(0xc68, 0x26a0); put64(0xc88, 0x26a0) })
        rejected(fixture().apply { ascii(0xca2, "Close.Handle") })
        rejected(fixture().apply { directory(12, 0x2680, 8) })
        rejected(fixture().apply { fill('X'.code.toByte(), 0xca2, 0xd30) })
    }

    @Test fun requiresTheExactVersionedJniExportsAndDistinctOrdinals() {
        rejected(fixture().apply { ascii(0x700, "Java_foreign_abi") })
        rejected(fixture().apply { put32(0x600 + 24, 12) })
        rejected(fixture().apply { put32(0x600 + 24, 13) })
        rejected(fixture().apply { put32(0x600 + 24, 14) })
        rejected(fixture().apply { put32(0x600 + 24, 15) })
        rejected(fixture().apply { put32(0x600 + 20, WindowsProfilePeImage.expectedExports.size + 1L) })
        rejected(fixture().apply { put16(0x6d2, 0) })
        rejected(fixture().apply { put16(0x6d0, WindowsProfilePeImage.expectedExports.size) })
        rejected(fixture().apply { put32(0x694, get32(0x690)) })
        rejected(fixture().apply { ascii(0x630, "other-profile.dll") })
    }

    @Test fun rejectsUnboundedStringsArraysAndArithmeticWraparound() {
        rejected(fixture().apply { put32(0x690, 0xffffffff) })
        rejected(fixture().apply { put32(0x600 + 28, 0xfffffff0) })
        rejected(fixture().apply { directory(0, 0xfffffff0, 65536) })
        rejected(fixture().apply { put32(SECTIONS + 12, 0xfffff000) })
        rejected(fixture().apply { fill('Q'.code.toByte(), 0x700, 0x700 + 193) })
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
        assertEquals(16, WindowsProfilePeImage.expectedExports.size)
    }

    private fun rejected(bytes: ByteArray) {
        assertFalse(bytes.contentEquals(fixture()), "A rejection fixture must actually change the admitted image")
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
    private fun fixture(): ByteArray = WindowsProfilePeFixture.create()

    companion object {
        private const val OPTIONAL = 0x98
        private const val SECTIONS = OPTIONAL + 240
    }
}
