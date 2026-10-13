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
        assertEquals(23, result.exports.size)
        assertEquals(13, WindowsProfilePeImage.ABI)
    }

    @Test fun rejectsPriorCustodyExportInventoryWithoutChildCreation() {
        val prior = WindowsProfilePeImage.expectedExports.filterNot { it.endsWith("_createChildDirectory") }.toSet()
        rejected(WindowsProfilePeFixture.create(prior))
    }

    @Test fun requiresExplicitVaultLockExportAndRejectsTheAbiSixInventory() {
        val current = WindowsProfilePeImage.expectedExports
        val vaultLock = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_createVaultLock"
        assertTrue(vaultLock in current)
        assertEquals(current, WindowsProfilePeImage.verify(WindowsProfilePeFixture.create(current)).exports)
        rejected(WindowsProfilePeFixture.create(current - vaultLock))
    }

    @Test fun requiresBothPersistentCandidateExportsAndRejectsTheAbiSevenInventory() {
        val current = WindowsProfilePeImage.expectedExports
        val prepare = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_prepareRecord"
        val rename = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_renameCandidate"
        assertTrue(prepare in current && rename in current)
        rejected(WindowsProfilePeFixture.create(current - prepare))
        rejected(WindowsProfilePeFixture.create(current - rename))
        rejected(WindowsProfilePeFixture.create(current - prepare - rename))
        assertEquals(current, WindowsProfilePeImage.verify(WindowsProfilePeFixture.create(current)).exports)
    }

    @Test fun requiresDirectorySyncExportAndRejectsTheAbiEightInventory() {
        val current = WindowsProfilePeImage.expectedExports
        val sync = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_syncDirectory"
        assertTrue(sync in current)
        rejected(WindowsProfilePeFixture.create(current - sync))
        assertEquals(current, WindowsProfilePeImage.verify(WindowsProfilePeFixture.create(current)).exports)
    }

    @Test fun requiresIdentityReplacementExportAndRejectsTheAbiNineInventory() {
        val current = WindowsProfilePeImage.expectedExports
        val replace = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_replaceCandidate"
        assertTrue(replace in current)
        rejected(WindowsProfilePeFixture.create(current - replace))
        assertEquals(current, WindowsProfilePeImage.verify(WindowsProfilePeFixture.create(current)).exports)
    }

    @Test fun requiresWholeWriteExportAndRejectsTheAbiTenInventory() {
        val current = WindowsProfilePeImage.expectedExports
        val write = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_writeRecord"
        assertTrue(write in current)
        rejected(WindowsProfilePeFixture.create(current - write))
        assertEquals(current, WindowsProfilePeImage.verify(WindowsProfilePeFixture.create(current)).exports)
    }

    @Test fun requiresWholeDeletionExportAndRejectsTheAbiElevenInventory() {
        val current = WindowsProfilePeImage.expectedExports
        val delete = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_deleteRecord"
        assertTrue(delete in current)
        rejected(WindowsProfilePeFixture.create(current - delete))
        assertEquals(current, WindowsProfilePeImage.verify(WindowsProfilePeFixture.create(current)).exports)
    }

    @Test fun syntheticExportTablesAreDisjointAndKeepTheirFinalEntry() {
        val count = WindowsProfilePeImage.expectedExports.size
        assertTrue(WindowsProfilePeFixture.EXPORT_FUNCTIONS + count * 4 <= WindowsProfilePeFixture.EXPORT_NAMES)
        assertTrue(WindowsProfilePeFixture.EXPORT_NAMES + count * 4 <= WindowsProfilePeFixture.EXPORT_ORDINALS)
        assertTrue(WindowsProfilePeFixture.EXPORT_ORDINALS + count * 2 <= WindowsProfilePeFixture.EXPORT_STRINGS)
        val exports = WindowsProfilePeImage.expectedExports
        assertEquals(23, count)
        assertEquals(1665, exports.sumOf { it.length + 1 })
        assertTrue(
            WindowsProfilePeFixture.EXPORT_STRINGS + exports.sumOf { it.length + 1 } <
                WindowsProfilePeFixture.IMPORT_DIRECTORY,
        )
        val bytes = fixture()
        assertEquals(0x1000L + count - 1, bytes.get32(WindowsProfilePeFixture.EXPORT_FUNCTIONS + (count - 1) * 4))
        assertEquals(count, WindowsProfilePeImage.verify(bytes).exports.size)
    }

    @Test fun acceptsBoundedStructuralFixtureWithoutClaimingNativeOrSignatureQualification() {
        assertEquals(13, WindowsProfilePeImage.ABI)
        val fixture = fixture()
        val result = WindowsProfilePeImage.verify(fixture)
        assertEquals(setOf("kernel32.dll"), result.imports)
        assertEquals(listOf(WindowsProfilePeImage.NamedImport("kernel32.dll", "CloseHandle", 0x2860, 0x2880)),
            result.namedImports)
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
        rejected(fixture().apply { put32(0x650, 0x2800) })
        rejected(fixture().apply { put32(0x650, 0x2030) })
        rejected(fixture().apply { put32(OPTIONAL + 16, 0x2800) })
    }

    @Test fun rejectsUnapprovedPathNamedAndDuplicateImports() {
        rejected(fixture().apply { ascii(0xe40, "badcode.dll") })
        rejected(fixture().apply { ascii(0xe40, "../evil.dll") })
        rejected(fixture().apply { ascii(0xe40, "C:evil.dll") })
        rejected(fixture().apply {
            put32(OPTIONAL + 116 + 8, 60)
            copyInto(this, 0xe14, 0xe00, 0xe14)
        })
        rejected(fixture().apply { put32(0xe0c, 0x2fff) })
    }

    @Test fun rejectsDelayBoundManagedAndMalformedImportDirectories() {
        for (index in listOf(11, 13, 14, 15)) rejected(fixture().apply { directory(index, 0x2800, 40) })
        rejected(fixture().apply { directory(1, 0x2800, 39) })
        rejected(fixture().apply { put32(0xe14, 1) })
        rejected(fixture().apply { put32(0xe04, 1) })
        rejected(fixture().apply { put32(0xe00, 0) })
    }

    @Test fun rejectsOrdinalImportsIatSubstitutionMissingTerminationAndBadNames() {
        rejected(fixture().apply { put64(0xe60, Long.MIN_VALUE or 1); put64(0xe80, Long.MIN_VALUE or 1) })
        rejected(fixture().apply { put64(0xe80, 0x28b0) })
        rejected(fixture().apply { put64(0xe68, 0x28a0); put64(0xe88, 0x28a0) })
        rejected(fixture().apply { ascii(0xea2, "Close.Handle") })
        rejected(fixture().apply { directory(12, 0x2880, 8) })
        rejected(fixture().apply { fill('X'.code.toByte(), 0xea2, 0xf30) })
    }

    @Test fun retainsEveryNamedImportAndItsDistinctOriginalThunkSlots() {
        val result = WindowsProfilePeImage.verify(twoImports())
        assertEquals(setOf("kernel32.dll", "ntdll.dll"), result.imports)
        assertEquals(listOf(
            WindowsProfilePeImage.NamedImport("kernel32.dll", "CloseHandle", 0x2860, 0x2880),
            WindowsProfilePeImage.NamedImport("ntdll.dll", "NtClose", 0x2870, 0x2890),
        ), result.namedImports)
        // Byte-table inventory only; RVAs cannot identify the eventual loaded system modules or forwarded exports.
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test fun approvedDllBasenamesCannotShareLookupOrAddressTables() {
        // Without slot ownership checks the Windows loader can bind both approved descriptors into the same IAT.
        rejected(twoImports().apply { put32(0xe14, 0x2860); put32(0xe24, 0x2880) })
        // Distinct IATs do not justify sharing a lookup table across different library descriptors.
        rejected(twoImports().apply { put32(0xe14, 0x2860); put64(0xe90, 0x28a0) })
        // One library's lookup table also cannot alias another library's writable address table.
        rejected(twoImports().apply { put32(0xe14, 0x2880); put64(0xe90, 0x28a0) })
        // Require the producer's separate original lookup/address tables, including within a single descriptor.
        rejected(fixture().apply { put32(0xe00, 0x2880) })
    }

    @Test fun rejectsUnalignedThunkTablesAndIatDirectorySpans() {
        rejected(fixture().apply {
            copyOfRange(0xe60, 0xe70).copyInto(this, 0xe61)
            put32(0xe00, 0x2861)
        })
        rejected(fixture().apply {
            copyOfRange(0xe80, 0xe90).copyInto(this, 0xe81)
            put32(0xe10, 0x2881)
            directory(12, 0x2881, 16)
        })
        rejected(fixture().apply { directory(12, 0x2880, 17) })
    }

    @Test fun returnedImportAndExportInventoriesCannotBeMutatedThroughCollectionCasts() {
        val result = WindowsProfilePeImage.verify(twoImports())
        assertFailsWith<UnsupportedOperationException> { (result.imports as MutableSet<String>).clear() }
        assertFailsWith<UnsupportedOperationException> { (result.exports as MutableSet<String>).clear() }
        assertFailsWith<UnsupportedOperationException> {
            (result.namedImports as MutableList<WindowsProfilePeImage.NamedImport>).clear()
        }
        assertEquals(WindowsProfilePeImage.verify(twoImports()), result)
    }

    @Test fun requiresTheExactVersionedJniExportsAndDistinctOrdinals() {
        rejected(fixture().apply { ascii(WindowsProfilePeFixture.EXPORT_STRINGS, "Java_foreign_abi") })
        rejected(fixture().apply { put32(0x600 + 24, 12) })
        rejected(fixture().apply { put32(0x600 + 24, 13) })
        rejected(fixture().apply { put32(0x600 + 24, 14) })
        rejected(fixture().apply { put32(0x600 + 24, 15) })
        rejected(fixture().apply { put32(0x600 + 24, 16) })
        rejected(fixture().apply { put32(0x600 + 24, 17) })
        rejected(fixture().apply { put32(0x600 + 24, 18) })
        rejected(fixture().apply { put32(0x600 + 24, 19) })
        rejected(fixture().apply { put32(0x600 + 24, 20) })
        rejected(fixture().apply { put32(0x600 + 24, 21) })
        rejected(fixture().apply { put32(0x600 + 24, 22) })
        rejected(fixture().apply { put32(0x600 + 20, WindowsProfilePeImage.expectedExports.size + 1L) })
        rejected(fixture().apply { put16(WindowsProfilePeFixture.EXPORT_ORDINALS + 2, 0) })
        rejected(fixture().apply {
            put16(WindowsProfilePeFixture.EXPORT_ORDINALS, WindowsProfilePeImage.expectedExports.size)
        })
        rejected(fixture().apply {
            put32(WindowsProfilePeFixture.EXPORT_NAMES + 4, get32(WindowsProfilePeFixture.EXPORT_NAMES))
        })
        rejected(fixture().apply { ascii(0x630, "other-profile.dll") })
    }

    @Test fun rejectsUnboundedStringsArraysAndArithmeticWraparound() {
        rejected(fixture().apply { put32(WindowsProfilePeFixture.EXPORT_NAMES, 0xffffffff) })
        rejected(fixture().apply { put32(0x600 + 28, 0xfffffff0) })
        rejected(fixture().apply { directory(0, 0xfffffff0, 65536) })
        rejected(fixture().apply { put32(SECTIONS + 12, 0xfffff000) })
        rejected(fixture().apply {
            val start = WindowsProfilePeFixture.EXPORT_STRINGS
            fill('Q'.code.toByte(), start, start + 193)
        })
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
        assertEquals(23, WindowsProfilePeImage.expectedExports.size)
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
    private fun twoImports(): ByteArray = fixture().apply {
        directory(1, 0x2800, 60)
        directory(12, 0x2880, 32)
        put32(0xe14, 0x2870)
        put32(0xe20, 0x2850)
        put32(0xe24, 0x2890)
        ascii(0xe50, "ntdll.dll")
        put64(0xe70, 0x28c0)
        put64(0xe90, 0x28c0)
        ascii(0xec2, "NtClose")
    }

    companion object {
        private const val OPTIONAL = 0x98
        private const val SECTIONS = OPTIONAL + 240
    }
}
