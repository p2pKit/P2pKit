package dev.p2pkit.sample.rpc.profile

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

/** Inert PE bytes only: these controls never load an image or qualify Windows relocation execution. */
class WindowsProfilePeRelocationTest {
    @Test fun acceptsDir64DataFixupsAndIgnoresAbsolutePaddingOffsets() {
        val bytes = fixture().apply { put16(RELOCATIONS + 10, 0x0800) }
        assertEquals(WindowsProfilePeImage.expectedExports, WindowsProfilePeImage.verify(bytes).exports)
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test fun acceptsAdjacentAndUnalignedFixupsOutsideVerifiedMetadata() {
        for (targets in listOf(listOf(0x2908, 0x2900), listOf(0x2901, 0x2909))) {
            val bytes = fixture().apply {
                put16(RELOCATIONS + 8, 0xa000 or (targets[0] and 0xfff))
                put16(RELOCATIONS + 10, 0xa000 or (targets[1] and 0xfff))
            }
            assertEquals(WindowsProfilePeImage.expectedExports, WindowsProfilePeImage.verify(bytes).exports)
        }
    }

    @Test fun rejectsMalformedBlockSizesAndDirectoryRemainders() {
        for (size in listOf(0L, 7, 8, 9, 10, 11, 14, 16, 0xfffffffc)) {
            rejected(fixture().apply { put32(RELOCATIONS + 4, size) })
        }
        rejected(fixture().apply { directory(5, 0x3000, 13) })
        rejected(fixture().apply { directory(5, 0x3001, 12) })
        rejected(fixture().apply { directory(5, 0x3000, 16) })
    }

    @Test fun rejectsNonPageAlignedAndOutOfImageBlockBases() {
        for (page in listOf(0x2001L, 0x4000, 0xfffff000, 0xffffffff)) {
            rejected(fixture().apply { put32(RELOCATIONS, page) })
        }
    }

    @Test fun rejectsEveryUnsupportedAmd64RelocationType() {
        for (type in (1..15).filterNot { it == 10 }) {
            rejected(fixture().apply { put16(RELOCATIONS + 8, (type shl 12) or 0x900) })
        }
    }

    @Test fun requiresAllEightWrittenBytesToHaveUnambiguousRawBacking() {
        for (target in listOf(0x80, 0x3ff, 0xfff, 0x11f9, 0x1200, 0x29f9, 0x2a00, 0x31f9, 0x4000)) {
            rejected(withTarget(target))
        }
        // Mapped zero-fill tail still cannot supply independently inspected original pointer bytes.
        rejected(withTarget(0x2a00).apply { put32(SECTIONS + 40 + 8, 0xb00) })
    }

    @Test fun rejectsWritesIntoImportDescriptorsAndTheirNullTerminator() {
        for (target in listOf(0x27f9, 0x2800, 0x2804, 0x2814, 0x2827)) rejected(withTarget(target))
    }

    @Test fun rejectsWritesIntoImportNamesHintsAndStringTerminators() {
        for (target in listOf(0x2839, 0x2840, 0x284c, 0x2899, 0x28a0, 0x28a2, 0x28ad)) {
            rejected(withTarget(target))
        }
    }

    @Test fun rejectsWritesIntoLookupAndAddressSlotsIncludingTerminatingSlots() {
        for (target in listOf(0x2859, 0x2860, 0x2868, 0x286f, 0x2879, 0x2880, 0x2888, 0x288f)) {
            rejected(withTarget(target))
        }
    }

    @Test fun protectsReferencedExportMetadataOutsideItsDeclaredDirectorySpan() {
        // PE references need not reside inside the export-directory range itself.
        val base = fixture().apply { directory(0, 0x2000, 40) }
        assertEquals(WindowsProfilePeImage.expectedExports, WindowsProfilePeImage.verify(base).exports)
        for (target in listOf(0x2000, 0x2029, 0x2030, 0x2048, 0x2050, 0x20a8, 0x20b0, 0x2110, 0x2150)) {
            rejected(withTarget(target, base.copyOf()))
        }
        val movedName = base.copyOf().apply {
            put32(0x60c, 0x2900)
            "p2pkit-windows-profile.dll\u0000".toByteArray(Charsets.US_ASCII).copyInto(this, 0xf00)
        }
        rejected(movedName)
    }

    @Test fun rejectsWritesIntoTheRelocationProgramItself() {
        for (target in listOf(0x3000, 0x3004, 0x3007, 0x3008, 0x300b)) rejected(withTarget(target))
    }

    @Test fun rejectsDuplicateAndPartiallyOverlappingWritesRegardlessOfEntryOrder() {
        for (offset in listOf(0x8f9, 0x8ff, 0x900, 0x901, 0x907)) {
            rejected(fixture().apply { put16(RELOCATIONS + 10, 0xa000 or offset) })
        }
        rejected(fixture().apply {
            directory(5, 0x3000, 24)
            put32(RELOCATIONS + 12, 0x2000)
            put32(RELOCATIONS + 16, 12)
            put16(RELOCATIONS + 20, 0xa907)
        })
    }

    @Test fun boundsTotalRelocationSlotsIncludingNoOpEntries() {
        fun image(slots: Int): ByteArray {
            val directorySize = 8 + slots * 2
            val bytes = expandedRelocations(directorySize)
            bytes.put32(RELOCATIONS, 0x2000)
            bytes.put32(RELOCATIONS + 4, directorySize.toLong())
            bytes.put16(RELOCATIONS + 8, 0xa900)
            return bytes
        }
        assertEquals(WindowsProfilePeImage.expectedExports, WindowsProfilePeImage.verify(image(65536)).exports)
        rejected(image(65538))
    }

    @Test fun boundsEmptyBlocksIndependentlyOfTheSlotCount() {
        fun image(blocks: Int): ByteArray = expandedRelocations(blocks * 8).apply {
            for (index in 0 until blocks) {
                put32(RELOCATIONS + index * 8, 0x2000)
                put32(RELOCATIONS + index * 8 + 4, 8)
            }
        }
        assertEquals(WindowsProfilePeImage.expectedExports, WindowsProfilePeImage.verify(image(32768)).exports)
        rejected(image(32769))
    }

    private fun expandedRelocations(directorySize: Int): ByteArray {
        val rawSize = (directorySize + 511) / 512 * 512
        return fixture().copyOf(RELOCATIONS + rawSize).apply {
            fill(0, RELOCATIONS, size)
            directory(5, 0x3000, directorySize.toLong())
            put32(SECTIONS + 80 + 8, rawSize.toLong())
            put32(SECTIONS + 80 + 16, rawSize.toLong())
            put32(OPTIONAL + 56, 0x3000L + (rawSize + 4095) / 4096 * 4096)
        }
    }

    private fun withTarget(target: Int, bytes: ByteArray = fixture()): ByteArray = bytes.apply {
        put32(RELOCATIONS, (target and -4096).toLong())
        put16(RELOCATIONS + 8, 0xa000 or (target and 0xfff))
    }

    private fun rejected(bytes: ByteArray) {
        assertFailsWith<IllegalArgumentException> { WindowsProfilePeImage.verify(bytes) }
    }

    private fun fixture(): ByteArray = WindowsProfilePeFixture.create()
    private fun ByteArray.put16(at: Int, value: Int) {
        this[at] = value.toByte()
        this[at + 1] = (value ushr 8).toByte()
    }
    private fun ByteArray.put32(at: Int, value: Long) {
        for (i in 0..3) this[at + i] = (value ushr (i * 8)).toByte()
    }
    private fun ByteArray.directory(index: Int, rva: Long, size: Long) {
        put32(OPTIONAL + 112 + index * 8, rva)
        put32(OPTIONAL + 116 + index * 8, size)
    }

    companion object {
        private const val OPTIONAL = 0x98
        private const val SECTIONS = OPTIONAL + 240
        private const val RELOCATIONS = 0x1000
    }
}
