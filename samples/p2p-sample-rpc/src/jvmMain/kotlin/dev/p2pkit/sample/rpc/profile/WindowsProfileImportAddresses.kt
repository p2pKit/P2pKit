package dev.p2pkit.sample.rpc.profile

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
    ) {
        require(image.imageBytes in 4096..(128L * 1024 * 1024) && mappedImageBytes == image.imageBytes) {
            "Windows profile mapped image size differs from pinned bytes"
        }
        require(moduleBase > 0 && moduleBase % 65_536 == 0L &&
            moduleBase <= Long.MAX_VALUE - mappedImageBytes) {
            "Invalid Windows profile image base or address range"
        }
        val count = image.namedImports.size
        require(count in 1..4096 && resolved.size == count && readback.size == count) {
            "Windows profile import observations are incomplete or exceed their bound"
        }
        // Consume each bounded entry once. Validate and compare the SAME immutable fields, never reread a
        // caller-owned list after verification. No list implementation, mutable array or native view escapes.
        val imports = List(count) { image.namedImports[it] }
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

    private fun validSlot(rva: Long, imageBytes: Long): Boolean =
        rva > 0 && rva % 8 == 0L && rva <= imageBytes - 8

    private val libraries = setOf("kernel32.dll", "advapi32.dll", "ntdll.dll", "shell32.dll", "ole32.dll")
    private val functionName = Regex("[A-Za-z_][A-Za-z0-9_]*")
}
