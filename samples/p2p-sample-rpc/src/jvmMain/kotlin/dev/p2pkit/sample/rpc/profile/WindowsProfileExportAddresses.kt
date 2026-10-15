package dev.p2pkit.sample.rpc.profile

/**
 * Address comparison for a later loader's JNI handoff, not permission to load or dereference native memory.
 * The loader must independently establish the original module's identity, mapped size, protections, imports
 * and continuous ownership before collecting these observations. Caller-supplied addresses prove none of that.
 * No symbol lookup, native call, module lease, registration or provider availability is supplied here.
 */
internal object WindowsProfileExportAddresses {
    data class ResolvedExport(val name: String, val address: Long)

    /**
     * Require every by-name resolution to equal the pinned original function RVA plus the same observed base.
     * Do not accept merely an address inside the image, sorted-name index arithmetic, or a second module copy.
     * Returning normally proves this bounded comparison only; it never produces a trusted loading context.
     */
    fun verify(
        image: WindowsProfileByteManifest.ByteAuthorization,
        moduleBase: Long,
        mappedImageBytes: Long,
        resolved: List<ResolvedExport>,
    ) {
        require(image.imageBytes in 4096..(128L * 1024 * 1024) && mappedImageBytes == image.imageBytes) {
            "Windows profile mapped image size differs from pinned bytes"
        }
        require(moduleBase > 0 && moduleBase % 65_536 == 0L &&
            moduleBase <= Long.MAX_VALUE - mappedImageBytes) {
            "Invalid Windows profile image base or address range"
        }
        val allowedNames = WindowsProfilePeImage.expectedExports
        val count = allowedNames.size
        require(image.namedExports.size == count && resolved.size == count) {
            "Windows profile export resolution is incomplete"
        }
        val expected = linkedMapOf<String, Long>()
        val ordinals = mutableSetOf<Int>()
        for (index in 0 until count) {
            val export = image.namedExports[index]
            require(export.name in allowedNames && export.ordinal in 1..count &&
                ordinals.add(export.ordinal) && export.functionRva in 1 until mappedImageBytes &&
                expected.put(export.name, moduleBase + export.functionRva) == null) {
                "Invalid Windows profile pinned export binding"
            }
        }
        // Distinct names may legitimately share machine code after linker folding. Identity is name -> RVA,
        // not uniqueness of code addresses. The bounded original ordinal/name inventory must still be exact.
        for (index in 0 until count) {
            val actual = resolved[index]
            require(expected.remove(actual.name) == actual.address) {
                "Windows profile resolved export differs from pinned function address"
            }
        }
        check(expected.isEmpty()) { "Windows profile export resolution is incomplete" }
    }
}
