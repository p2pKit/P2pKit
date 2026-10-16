package dev.p2pkit.sample.rpc.profile

import java.util.Collections

/**
 * Exact headers and complete executable-page comparison against independently pinned file bytes, including AMD64 DIR64
 * relocation and the loader's exact ImageBase update for the required DYNAMIC_BASE image.
 * This is a dormant loader algorithm, NOT a loader, native memory reader or loading authority.
 * A productive caller must separately establish original file/module/ancestor custody, system-call authority,
 * readable mappings and protections, import providers and lifetime before obtaining actual readbacks.
 * Matching caller-supplied arrays establishes none of those prerequisites or Windows provider availability.
 * Supports separate 4KiB section pages only. Header pages require read-only, non-executable protection;
 * executable pages require execute/read protection. These byte comparisons do not observe that OS protection.
 */
internal class WindowsProfileMappedCode private constructor(private val layout: WindowsProfilePeImage.CodeLayout) {
    data class Region(val address: Long, val bytes: Int, val executable: Boolean = true)
    data class Readback(val address: Long, val bytes: ByteArray)

    /** Complete, page-bounded requests: each fits a single supported Windows query region/read call. */
    fun regions(moduleBase: Long, mappedImageBytes: Long): List<Region> {
        checkMapping(moduleBase, mappedImageBytes)
        val ranges = layout.sections.flatMap { section ->
            (0 until section.mappedBytes step PAGE_BYTES).map { offset ->
                Region(moduleBase + section.rva + offset, PAGE_BYTES, section.executable)
            }
        }
        return Collections.unmodifiableList(ranges)
    }

    /**
     * Reassemble a complete unique page inventory before comparing original sections, so a DIR64 crossing
     * pages is still one validated eight-byte update. The private layout bounds total copied bytes to 128MiB
     * and page count to 32,768. Every supplied page is copied once before later caller-owned entries are read.
     * Writable data, IAT/provider identities, non-header metadata and actual protections require separate checks.
     * This neither observes native memory nor establishes simultaneous acquisition/continued immutability.
     */
    fun verify(moduleBase: Long, mappedImageBytes: Long, observed: List<Readback>) {
        checkMapping(moduleBase, mappedImageBytes)
        val count = layout.sections.sumOf { it.mappedBytes / PAGE_BYTES }
        require(observed.size == count) { "Windows profile executable readback inventory differs" }
        val pending = linkedMapOf<Long, Pair<Int, Int>>()
        layout.sections.forEachIndexed { index, section ->
            for (offset in 0 until section.mappedBytes step PAGE_BYTES) {
                pending[moduleBase + section.rva + offset] = index to offset
            }
        }
        val snapshots = layout.sections.map { ByteArray(it.mappedBytes) }
        repeat(count) { index ->
            val readback = observed[index]
            val destination = pending.remove(readback.address)
            require(destination != null && readback.bytes.size == PAGE_BYTES) {
                "Windows profile executable readback range differs"
            }
            readback.bytes.copyInto(snapshots[destination.first], destination.second)
        }
        check(pending.isEmpty()) { "Windows profile executable readback inventory differs" }
        val delta = moduleBase - layout.preferredBase
        layout.sections.forEachIndexed { index, section ->
            val actual = snapshots[index]
            var cursor = 0
            if (!section.executable) {
                // The required DYNAMIC_BASE image's loaded PE header contains the actual base, not its
                // on-disk preferred base. Derive exactly these eight expected bytes from the original
                // module mapping; never mask them, accept an arbitrary value or rewrite the file snapshot.
                // The field offset comes from the verified original PE header, never loaded metadata.
                check(section.rva == 0L && section.relocations.isEmpty())
                val field = layout.headerImageBaseOffset
                compareUnchanged(section.rawBytes, actual, 0, field)
                for (byte in 0..7) require(actual[field + byte] == (moduleBase ushr (byte * 8)).toByte()) {
                    "Windows profile mapped header ImageBase differs"
                }
                cursor = field + 8
            }
            for (relocation in section.relocations) {
                compareUnchanged(section.rawBytes, actual, cursor, relocation)
                var original = 0L
                for (byte in 0..7) {
                    original = original or ((section.rawBytes[relocation + byte].toLong() and 255) shl (byte * 8))
                }
                // DIR64 is unsigned 64-bit addition, including wraparound; it is not signed pointer validation.
                val relocated = original + delta
                for (byte in 0..7) require(actual[relocation + byte] == (relocated ushr (byte * 8)).toByte()) {
                    "Windows profile relocated executable bytes differ"
                }
                cursor = relocation + 8
            }
            compareUnchanged(section.rawBytes, actual, cursor, actual.size)
        }
    }

    private fun compareUnchanged(original: ByteArray, actual: ByteArray, from: Int, until: Int) {
        for (index in from until until) {
            val expected = if (index < original.size) original[index] else 0.toByte()
            require(actual[index] == expected) { "Windows profile executable bytes differ" }
        }
    }

    private fun checkMapping(moduleBase: Long, mappedImageBytes: Long) {
        require(mappedImageBytes == layout.imageBytes && moduleBase > 0 && moduleBase % 65_536 == 0L &&
            moduleBase <= Long.MAX_VALUE - mappedImageBytes) { "Invalid Windows profile executable mapping range" }
    }

    companion object {
        private const val PAGE_BYTES = 4096

        /** Snapshot and reparse the same pinned bytes; no expected bytes are taken from a loaded candidate. */
        fun prepare(library: ByteArray, image: WindowsProfileByteManifest.ByteAuthorization): WindowsProfileMappedCode {
            val layout = WindowsProfilePeImage.codeLayout(library)
            require(layout.sha256 == image.dllSha256 && layout.fileBytes == image.dllBytes &&
                layout.imageBytes == image.imageBytes) { "Windows profile executable plan differs from pinned bytes" }
            return WindowsProfileMappedCode(layout)
        }
    }
}
