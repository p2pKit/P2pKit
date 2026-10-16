package dev.p2pkit.sample.rpc.profile

/**
 * Fixed Java-17 byte-verification bridge for the separately packaged Java-21 named module.
 * Every input is comparison data, never loading authority, a native pointer view or an admitted owner.
 * The later loader must independently establish expected pins, actual readback origins/protections,
 * packaged class/runtime identity and continuous custody. This class loads or registers no native code.
 */
internal class WindowsProfilePackagedVerifier private constructor(
    private val image: WindowsProfileByteManifest.ByteAuthorization,
    private val exports: WindowsProfilePeImage.ExportLayout,
    private val code: WindowsProfileMappedCode,
    private val iat: WindowsProfileImportAddresses.Plan,
) {
    /** Actual compiled declaration, without initialization; not source/classpath provenance by itself. */
    fun declaringClass(): Class<*> = WindowsProfileCustodyJni::class.java

    fun imageLayout(): LongArray = longArrayOf(image.imageBytes, exports.directoryRva, exports.directoryBytes)
    fun exportNames(): Array<String> = image.namedExports.map { it.name }.toTypedArray()
    fun exportRvas(): LongArray = image.namedExports.map { it.functionRva }.toLongArray()
    fun importNames(): Array<String> = image.namedImports.flatMap { listOf(it.library, it.function) }.toTypedArray()

    /** Ordered triples: absolute address, byte count, kind (0 read-only header, 1 executable, 2 IAT data). */
    fun regions(moduleBase: Long): LongArray {
        val codeRegions = code.regions(moduleBase, image.imageBytes)
        val iatRegions = iat.regions(moduleBase, image.imageBytes)
        return LongArray((codeRegions.size + iatRegions.size) * 3).also { result ->
            codeRegions.forEachIndexed { index, region ->
                result[index * 3] = region.address
                result[index * 3 + 1] = region.bytes.toLong()
                result[index * 3 + 2] = if (region.executable) 1 else 0
            }
            iatRegions.forEachIndexed { index, region ->
                val offset = (codeRegions.size + index) * 3
                result[offset] = region.address
                result[offset + 1] = region.bytes.toLong()
                result[offset + 2] = 2
            }
        }
    }

    /**
     * Targets correspond to the exact exported/imported names above; pages correspond to regions(base).
     * Outputs are the 23 original JNI-table addresses followed by the separate registrar address. They
     * remain inert comparison results, not callable views, module leases or permission to register JNI.
     */
    fun verify(
        moduleBase: Long,
        exportTargets: LongArray,
        importTargets: LongArray,
        pages: Array<ByteArray>,
    ): LongArray {
        val requested = regions(moduleBase)
        require(exportTargets.size == image.namedExports.size && importTargets.size == image.namedImports.size &&
            pages.size == requested.size / 3) { "Packaged Windows verifier observations are incomplete" }
        val actualExports = exportTargets.copyOf()
        val actualImports = importTargets.copyOf()
        // Capture each outer reference once, then copy every bounded page before running either verifier.
        // No later parser may reread caller storage or obtain a different cross-parser byte snapshot.
        val references = pages.copyOf()
        val snapshots = Array(references.size) { index ->
            require(references[index].size.toLong() == requested[index * 3 + 1]) {
                "Packaged Windows verifier readback length differs"
            }
            references[index].copyOf()
        }
        val codeReadbacks = mutableListOf<WindowsProfileMappedCode.Readback>()
        val iatReadbacks = mutableListOf<WindowsProfileImportAddresses.Readback>()
        snapshots.forEachIndexed { index, bytes ->
            val address = requested[index * 3]
            if (requested[index * 3 + 2] == 2L) {
                iatReadbacks += WindowsProfileImportAddresses.Readback(address, bytes)
            } else {
                codeReadbacks += WindowsProfileMappedCode.Readback(address, bytes)
            }
        }
        val resolutions = image.namedImports.mapIndexed { index, entry ->
            WindowsProfileImportAddresses.ResolvedImport(entry.library, entry.function, actualImports[index])
        }
        code.verify(moduleBase, image.imageBytes, codeReadbacks)
        iat.verify(moduleBase, image.imageBytes, resolutions, iatReadbacks)
        val resolvedExports = image.namedExports.mapIndexed { index, entry ->
            WindowsProfileExportAddresses.ResolvedExport(entry.name, actualExports[index])
        }
        val plan = WindowsProfileJniPlan.prepare(declaringClass(), image, moduleBase, image.imageBytes, resolvedExports)
        plan.requireApplicationClassLoader()
        return LongArray(24) { index -> if (index == 23) plan.registrar.address else plan.methods[index].address }
    }

    companion object {
        /**
         * Fixed public JVM static signature for named-module reflection. Syntactically supplied pins do
         * not establish their origin; this is exactly the existing byte-manifest comparison, not authority.
         */
        @JvmStatic
        fun create(
            manifest: ByteArray,
            library: ByteArray,
            manifestSha256: String,
            source: String,
            tree: String,
        ): WindowsProfilePackagedVerifier {
            require(manifest.size in 1..WindowsProfileByteManifest.MAXIMUM_MANIFEST_BYTES &&
                library.size in 512..WindowsProfilePeImage.MAXIMUM_BYTES) { "Unbounded packaged verifier input" }
            val manifestSnapshot = manifest.copyOf()
            val librarySnapshot = library.copyOf()
            val pins = WindowsProfileByteManifest.Authority(manifestSha256, source, tree)
            val image = WindowsProfileByteManifest.authorize(manifestSnapshot, librarySnapshot, pins)
            val exports = WindowsProfilePeImage.exportLayout(librarySnapshot)
            require(exports.sha256 == image.dllSha256 && exports.fileBytes == image.dllBytes &&
                exports.imageBytes == image.imageBytes && exports.namedExports == image.namedExports) {
                "Packaged Windows export plan differs from the same pinned byte snapshot"
            }
            return WindowsProfilePackagedVerifier(image, exports,
                WindowsProfileMappedCode.prepare(librarySnapshot, image),
                WindowsProfileImportAddresses.prepare(librarySnapshot, image))
        }
    }
}
