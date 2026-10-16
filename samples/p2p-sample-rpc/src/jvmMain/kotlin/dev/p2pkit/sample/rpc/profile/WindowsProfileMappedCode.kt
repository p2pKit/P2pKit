package dev.p2pkit.sample.rpc.profile

import java.util.Collections

/**
 * Exact headers and complete executable-page comparison against independently pinned file bytes, including AMD64 DIR64
 * relocation. This is a dormant loader algorithm, NOT a loader, native memory reader or loading authority.
 * A productive caller must separately establish original file/module/ancestor custody, system-call authority,
 * readable mappings and protections, import providers and lifetime before obtaining actual readbacks.
 * Matching caller-supplied arrays establishes none of those prerequisites or Windows provider availability.
 * Supports separate 4KiB section pages only. Header pages require read-only, non-executable protection;
 * executable pages require execute/read protection. These byte comparisons do not observe that OS protection.
 */
internal class WindowsProfileMappedCode private constructor(private val layout: WindowsProfilePeImage.CodeLayout) {
    data class Region(val address: Long, val bytes: Int, val executable: Boolean = true)
    data class Readback(val address: Long, val bytes: ByteArray)

    /** Headers first, then complete executable sections. The caller must read each range under original custody. */
    fun regions(moduleBase: Long, mappedImageBytes: Long): List<Region> {
        checkMapping(moduleBase, mappedImageBytes)
        return Collections.unmodifiableList(layout.sections.map {
            Region(moduleBase + it.rva, it.mappedBytes, it.executable)
        })
    }

    /**
     * Check a complete, unique inventory without using a callback to dereference arbitrary native addresses.
     * Readback bytes are bounded and privately copied before comparison. Concurrent mutation cannot change the
     * retained plan, but atomic native acquisition/continued immutability still belongs to the actual loader.
     * Writable data, IAT/provider identities, non-header metadata and page protections require separate checks.
     */
    fun verify(moduleBase: Long, mappedImageBytes: Long, observed: List<Readback>) {
        checkMapping(moduleBase, mappedImageBytes)
        val count = layout.sections.size
        require(observed.size == count) { "Windows profile executable readback inventory differs" }
        val pending = layout.sections.associateByTo(linkedMapOf()) { moduleBase + it.rva }
        // Consume each supplied entry once and retain its bounded private byte snapshot before comparison.
        val snapshots = List(count) { index ->
            val readback = observed[index]
            val section = pending.remove(readback.address)
            require(section != null && readback.bytes.size == section.mappedBytes) {
                "Windows profile executable readback range differs"
            }
            section to readback.bytes.copyOf()
        }
        check(pending.isEmpty()) { "Windows profile executable readback inventory differs" }
        val delta = moduleBase - layout.preferredBase
        for ((section, actual) in snapshots) {
            var cursor = 0
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
        /** Snapshot and reparse the same pinned bytes; no expected bytes are taken from a loaded candidate. */
        fun prepare(library: ByteArray, image: WindowsProfileByteManifest.ByteAuthorization): WindowsProfileMappedCode {
            val layout = WindowsProfilePeImage.codeLayout(library)
            require(layout.sha256 == image.dllSha256 && layout.fileBytes == image.dllBytes &&
                layout.imageBytes == image.imageBytes) { "Windows profile executable plan differs from pinned bytes" }
            return WindowsProfileMappedCode(layout)
        }
    }
}
