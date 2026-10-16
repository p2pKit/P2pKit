package dev.p2pkit.sample.rpc.profile

import java.security.MessageDigest

/** Test-only actual declaration/manifest bridge. Never a native loader or storage entry point. */
internal object WindowsProfileLoadedNativeFixture {
    @JvmStatic
    fun manifest(library: ByteArray, source: String, tree: String): Array<Any> {
        val bytes = WindowsProfileByteManifest.produce(source, tree, true, library)
        val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        return arrayOf(bytes, hash)
    }

    /**
     * Post-refusal test-only projection of already copied synthetic DLL pages. This neither reads native
     * memory nor admits a mapping. Keep the original verifier failure; never use this output for acceptance.
     * Only fixed categories and a within-page offset leave this helper, never bytes or process addresses.
     */
    @JvmStatic
    fun mappedObservation(library: ByteArray, moduleBase: Long, requests: LongArray, pages: Array<ByteArray>): String {
        require(library.size in 512..4 * 1024 * 1024)
        val originalBytes = library.copyOf()
        val layout = WindowsProfilePeImage.codeLayout(originalBytes)
        require(layout.imageBytes <= 16L * 1024 * 1024 && moduleBase > 0 && moduleBase % 65_536 == 0L &&
            moduleBase <= Long.MAX_VALUE - layout.imageBytes)
        require(requests.size % 3 == 0 && pages.size == requests.size / 3 && pages.size <= 8192)
        val codePages = layout.sections.sumOf { it.mappedBytes / 4096 }
        require(pages.size >= codePages)
        var pageIndex = 0
        var first = "NONE"
        var firstOffset = 0
        var executableMatches = true
        var headerFileMatches = false
        for (section in layout.sections) {
            val actual = ByteArray(section.mappedBytes)
            for (offset in 0 until section.mappedBytes step 4096) {
                val index = pageIndex++
                require(requests[index * 3] == moduleBase + section.rva + offset &&
                    requests[index * 3 + 1] == 4096L &&
                    requests[index * 3 + 2] == if (section.executable) 1L else 0L)
                val page = pages[index]
                require(page.size == 4096)
                page.copyInto(actual, offset)
            }
            val expected = section.rawBytes.copyOf(section.mappedBytes)
            val relocated = BooleanArray(section.mappedBytes)
            for (offset in section.relocations) {
                var original = 0L
                for (byte in 0..7) original = original or
                    ((section.rawBytes[offset + byte].toLong() and 255) shl (byte * 8))
                val value = original + moduleBase - layout.preferredBase
                for (byte in 0..7) {
                    expected[offset + byte] = (value ushr (byte * 8)).toByte()
                    relocated[offset + byte] = true
                }
            }
            if (!section.executable) {
                require(section.rva == 0L)
                headerFileMatches = originalBytes.size >= actual.size &&
                    actual.indices.all { actual[it] == originalBytes[it] }
            }
            for (offset in actual.indices) {
                if (actual[offset] == expected[offset]) continue
                if (section.executable) executableMatches = false
                if (first != "NONE") continue
                first = when {
                    relocated[offset] -> "RELOCATION"
                    section.executable && offset < section.rawBytes.size -> "EXECUTABLE_RAW"
                    section.executable -> "EXECUTABLE_PADDING"
                    offset < section.rawBytes.size -> "HEADER_RAW"
                    else -> "HEADER_PADDING"
                }
                firstOffset = offset % 4096
            }
        }
        require(pageIndex == codePages)
        return "WINDOWS_LOADED_MAPPED_OBSERVATION first=$first offset=$firstOffset " +
            "headerFilePage=${if (headerFileMatches) "MATCH" else "DIFFERENT"} " +
            "executable=${if (executableMatches) "MATCH" else "DIFFERENT"}"
    }

    @JvmStatic
    fun abi(): Int = WindowsProfileCustodyJni.abi()

    @JvmStatic
    fun capabilities(): Long = WindowsProfileCustodyJni.capabilities()
}
