package dev.p2pkit.sample.rpc.profile

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/** Inert bytes only; import binding is neither performed nor qualified by these controls. */
class WindowsProfilePeImportWriteTest {
    @Test fun rejectsAnImportAddressSlotOverlappingAReferencedExportOrdinal() {
        // The original low word is a valid last ordinal. Import resolution would replace that same word.
        rejected(ordinalBoundary(overlap = true))
    }

    @Test fun acceptsAnImportAddressTableImmediatelyAfterTheExportOrdinals() {
        val result = WindowsProfilePeImage.verify(ordinalBoundary(overlap = false))
        assertEquals(WindowsProfilePeImage.expectedExports, result.exports)
        assertEquals(listOf(WindowsProfilePeImage.NamedImport("kernel32.dll", "CloseHandle", 0x2920, 0x2880)),
            result.namedImports)
    }

    @Test fun rejectsAnImportAddressTableInsideTheDeclaredExportDirectory() {
        rejected(WindowsProfilePeFixture.create().apply { directory(0, 0x2000, 0x890) })
    }

    @Test fun rejectsAnImportAddressDirectoryEnclosingLookupOrImportNameMetadata() {
        rejected(WindowsProfilePeFixture.create().apply { directory(12, 0x2860, 0x30) })
        rejected(WindowsProfilePeFixture.create().apply { directory(12, 0x2880, 0x30) })
    }

    @Test fun rejectsAnImportAddressDirectoryEnclosingTheRelocationProgram() {
        rejected(WindowsProfilePeFixture.create().apply {
            directory(5, 0x28b0, 12)
            copyOfRange(0x1000, 0x100c).copyInto(this, 0xeb0)
            directory(12, 0x2880, 0x40)
        })
    }

    private fun ordinalBoundary(overlap: Boolean): ByteArray {
        val original = WindowsProfilePeFixture.create()
        return original.copyOf(0xf800).apply {
            // Extend raw-backed data so an import-name RVA has the valid final ordinal as its low word.
            fill(0, 0x1000, size)
            put32(SECTIONS + 40 + 8, 0xf000)
            put32(SECTIONS + 40 + 16, 0xf000)
            put32(SECTIONS + 80 + 12, 0x11000)
            put32(SECTIONS + 80 + 20, 0xf600)
            put32(OPTIONAL + 56, 0x12000)
            directory(0, 0x2000, 40) // Referenced ordinals lie outside the declared export directory.
            directory(5, 0x11000, 12)
            original.copyOfRange(0x1000, 0x100c).copyInto(this, 0xf600)
            put16(0xf608, 0xa960)
            put32(0xe00, 0x2920)
            put64(0xf20, 0x10016)
            put64(0xe80, 0x10016)
            "CloseHandle\u0000".toByteArray(Charsets.US_ASCII).copyInto(this, 0xe618)
            val start = if (overlap) 0xe54 else 0xe52
            put32(0x624, (start + 0x1a00).toLong())
            repeat(WindowsProfilePeImage.expectedExports.size) { put16(start + it * 2, it) }
        }
    }

    private fun rejected(bytes: ByteArray) {
        assertFailsWith<IllegalArgumentException> { WindowsProfilePeImage.verify(bytes) }
    }
    private fun ByteArray.put16(at: Int, value: Int) {
        this[at] = value.toByte()
        this[at + 1] = (value ushr 8).toByte()
    }
    private fun ByteArray.put32(at: Int, value: Long) {
        for (i in 0..3) this[at + i] = (value ushr (i * 8)).toByte()
    }
    private fun ByteArray.put64(at: Int, value: Long) {
        for (i in 0..7) this[at + i] = (value ushr (i * 8)).toByte()
    }
    private fun ByteArray.directory(index: Int, rva: Long, size: Long) {
        put32(OPTIONAL + 112 + index * 8, rva)
        put32(OPTIONAL + 116 + index * 8, size)
    }

    companion object {
        private const val OPTIONAL = 0x98
        private const val SECTIONS = OPTIONAL + 240
    }
}
