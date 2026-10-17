package dev.p2pkit.sample.rpc.profile

import java.util.Collections

/**
 * Exact import-slot comparison for the later loader, not permission to load or read native memory.
 * The caller must independently retain the original image and system-provider mappings, validate their
 * protections and resolve each original export before collecting the IAT readback under the same ownership.
 * A logical import such as kernel32.dll may forward to another approved system module. This comparison
 * does not identify, approve or pin that physical provider, and caller-supplied addresses confer no authority.
 */
internal object WindowsProfileImportAddresses {
    /** Logical DLL/name from the original import table; address is the independently resolved final target. */
    data class ResolvedImport(val library: String, val function: String, val address: Long)

    /** Actual absolute slot address and its 64-bit value, not a lookup-table value or a list-position claim. */
    data class IatSlot(val address: Long, val target: Long)

    /**
     * Require every original import's own IAT slot to contain its exact resolved target. No native lookup,
     * memory access, executable-byte verification, import terminator/padding check or module lease occurs here.
     * Returning normally proves only this bounded comparison; it never publishes a provider or trusted context.
     */
    fun verify(
        image: WindowsProfileByteManifest.ByteAuthorization,
        moduleBase: Long,
        mappedImageBytes: Long,
        resolved: List<ResolvedImport>,
        readback: List<IatSlot>,
    ) = verifySlots(image.imageBytes, image.namedImports, moduleBase, mappedImageBytes, resolved, readback)

    private fun verifySlots(
        imageBytes: Long,
        namedImports: List<WindowsProfilePeImage.NamedImport>,
        moduleBase: Long,
        mappedImageBytes: Long,
        resolved: List<ResolvedImport>,
        readback: List<IatSlot>,
    ) {
        require(imageBytes in 4096..(128L * 1024 * 1024) && mappedImageBytes == imageBytes) {
            "Windows profile mapped image size differs from pinned bytes"
        }
        require(moduleBase > 0 && moduleBase % 65_536 == 0L &&
            moduleBase <= Long.MAX_VALUE - mappedImageBytes) {
            "Invalid Windows profile image base or address range"
        }
        val count = namedImports.size
        require(count in 1..4096 && resolved.size == count && readback.size == count) {
            "Windows profile import observations are incomplete or exceed their bound"
        }
        // Consume each bounded entry once. Validate and compare the SAME immutable fields, never reread a
        // caller-owned list after verification. No list implementation, mutable array or native view escapes.
        val imports = List(count) { namedImports[it] }
        val resolutions = List(count) { resolved[it] }
        val slots = List(count) { readback[it] }
        val expected = linkedMapOf<Pair<String, String>, Long>()
        val lookupSlots = mutableSetOf<Long>()
        val addressSlots = mutableSetOf<Long>()
        for (entry in imports) {
            require(entry.library.length in 1..64 && entry.library in libraries && entry.function.length in 1..128 &&
                functionName.matches(entry.function) && validSlot(entry.lookupRva, mappedImageBytes) &&
                validSlot(entry.addressRva, mappedImageBytes) && lookupSlots.add(entry.lookupRva) &&
                addressSlots.add(entry.addressRva) &&
                expected.put(entry.library to entry.function, moduleBase + entry.addressRva) == null) {
                "Invalid Windows profile pinned import binding"
            }
        }
        require(lookupSlots.none { it in addressSlots }) { "Windows profile lookup and address slots overlap" }
        val targets = linkedMapOf<Long, Long>()
        val imageEnd = moduleBase + mappedImageBytes
        for (entry in resolutions) {
            require(entry.library.length in 1..64 && entry.function.length in 1..128) {
                "Windows profile original import name exceeds its bound"
            }
            val slot = expected.remove(entry.library to entry.function)
            require(slot != null && entry.address > 0 && entry.address !in moduleBase until imageEnd) {
                "Windows profile original import resolution differs from pinned inventory"
            }
            // Different logical exports can forward/fold to the same original machine-code address.
            // Uniqueness belongs to the import tuple and its slot, not to the resolved target value.
            targets[slot] = entry.address
        }
        for (entry in slots) {
            require(targets.remove(entry.address) == entry.target) {
                "Windows profile import slot differs from its original resolved target"
            }
        }
        check(expected.isEmpty() && targets.isEmpty()) { "Windows profile import comparison is incomplete" }
    }

    /** Immutable range requests; each stays within one 4 KiB page and the complete declared IAT. */
    data class Region(val address: Long, val bytes: Int)
    data class Readback(val address: Long, val bytes: ByteArray)

    /**
     * Bind a full-IAT comparison plan to the same independently pinned original PE snapshot. This adds no
     * authority to the supplied manifest, file, loaded module or system-provider resolutions.
     */
    fun prepare(library: ByteArray, image: WindowsProfileByteManifest.ByteAuthorization): Plan =
        Plan.prepare(library, image)

    /** Original bytes never escape: only declared named slots may differ after Windows import resolution. */
    class Plan private constructor(private val layout: WindowsProfilePeImage.IatLayout) {
        fun regions(moduleBase: Long, mappedImageBytes: Long): List<Region> {
            checkMapping(moduleBase, mappedImageBytes)
            val result = mutableListOf<Region>()
            var offset = 0
            while (offset < layout.bytes.size) {
                val rva = layout.rva + offset
                val count = minOf(4096 - (rva % 4096).toInt(), layout.bytes.size - offset)
                result += Region(moduleBase + rva, count)
                offset += count
            }
            return Collections.unmodifiableList(result)
        }

        /**
         * Compare every declared IAT byte, including each original null terminator and inter-table/trailing
         * padding. Named slots must contain their exact independently resolved target; all other bytes retain
         * their original values. Actual page/query acquisition, atomicity, physical forwarded providers and
         * protection from concurrent mutation remain external obligations, not claims of this byte algorithm.
         */
        fun verify(moduleBase: Long, mappedImageBytes: Long, resolved: List<ResolvedImport>, observed: List<Readback>) {
            val ranges = regions(moduleBase, mappedImageBytes)
            require(observed.size == ranges.size) { "Windows profile complete IAT readback inventory differs" }
            val pending = ranges.associateByTo(linkedMapOf()) { it.address }
            // One private bounded snapshot, at most the original PE file bound. Never revisit caller entries.
            val actual = ByteArray(layout.bytes.size)
            repeat(ranges.size) { index ->
                val readback = observed[index]
                val range = pending.remove(readback.address)
                require(range != null && readback.bytes.size == range.bytes) {
                    "Windows profile complete IAT readback range differs"
                }
                val offset = (readback.address - moduleBase - layout.rva).toInt()
                readback.bytes.copyInto(actual, offset)
            }
            check(pending.isEmpty()) { "Windows profile complete IAT readback inventory differs" }
            val slots = layout.namedImports.map { entry ->
                val offset = (entry.addressRva - layout.rva).toInt()
                var target = 0L
                for (byte in 0..7) target = target or ((actual[offset + byte].toLong() and 255) shl (byte * 8))
                IatSlot(moduleBase + entry.addressRva, target)
            }
            verifySlots(layout.imageBytes, layout.namedImports, moduleBase, mappedImageBytes, resolved, slots)
            var cursor = 0
            for (entry in layout.namedImports.sortedBy { it.addressRva }) {
                val offset = (entry.addressRva - layout.rva).toInt()
                compareOriginal(actual, cursor, offset)
                cursor = offset + 8
            }
            compareOriginal(actual, cursor, actual.size)
        }

        private fun compareOriginal(actual: ByteArray, from: Int, until: Int) {
            for (index in from until until) require(actual[index] == layout.bytes[index]) {
                "Windows profile IAT terminator or padding differs from pinned bytes"
            }
        }

        private fun checkMapping(moduleBase: Long, mappedImageBytes: Long) {
            require(mappedImageBytes == layout.imageBytes && moduleBase > 0 && moduleBase % 65_536 == 0L &&
                moduleBase <= Long.MAX_VALUE - mappedImageBytes) { "Invalid Windows profile IAT mapping range" }
        }

        companion object {
            internal fun prepare(library: ByteArray, image: WindowsProfileByteManifest.ByteAuthorization): Plan {
                val layout = WindowsProfilePeImage.iatLayout(library)
                require(layout.sha256 == image.dllSha256 && layout.fileBytes == image.dllBytes &&
                    layout.imageBytes == image.imageBytes && layout.namedImports == image.namedImports) {
                    "Windows profile complete IAT plan differs from pinned bytes"
                }
                return Plan(layout)
            }
        }
    }

    private fun validSlot(rva: Long, imageBytes: Long): Boolean =
        rva > 0 && rva % 8 == 0L && rva <= imageBytes - 8

    private val libraries = setOf("kernel32.dll", "advapi32.dll", "ntdll.dll", "shell32.dll", "ole32.dll")
    private val functionName = Regex("[A-Za-z_][A-Za-z0-9_]*")
}
