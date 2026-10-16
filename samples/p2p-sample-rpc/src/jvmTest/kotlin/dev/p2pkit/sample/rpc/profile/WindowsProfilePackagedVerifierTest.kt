package dev.p2pkit.sample.rpc.profile

import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame

/** Inert byte fixtures only. No DLL load, JNI registration, native readback or installed authority. */
class WindowsProfilePackagedVerifierTest {
    @Test fun exactSourceSnapshotExposesOnlyCompletePageAndImportData() {
        val fixture = fixture()
        val plan = fixture.plan()
        assertSame(WindowsProfileCustodyJni::class.java, plan.declaringClass())
        assertContentEquals(longArrayOf(0x4000, 0x2000, 0x800), plan.imageLayout())
        assertContentEquals(WindowsProfilePeImage.expectedExports.sorted().toTypedArray(), plan.exportNames())
        assertContentEquals(LongArray(24) { 0x1000L + it }, plan.exportRvas())
        assertContentEquals(arrayOf("kernel32.dll", "CloseHandle"), plan.importNames())
        assertContentEquals(longArrayOf(BASE, 4096, 0, BASE + 0x1000, 4096, 1, BASE + 0x2880, 16, 2),
            plan.regions(BASE))
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test fun successfulComparisonPreservesTheRealApplicationClassLoaderRequirement() {
        val fixture = fixture()
        val plan = fixture.plan()
        assertOriginalLoaderBoundary(plan, fixture.pages(), fixture.exportTargets())
    }

    @Test fun originalInputAndEveryEscapedInventoryRemainIndependentCopies() {
        val fixture = fixture()
        val plan = fixture.plan()
        val originalPages = fixture.pages()
        val originalExports = fixture.exportTargets()
        fixture.library.fill(0)
        fixture.manifest.fill(0)
        plan.imageLayout().fill(0)
        plan.exportNames().fill("wrong")
        plan.exportRvas().fill(0)
        plan.importNames().fill("wrong")
        plan.regions(BASE).fill(0)
        assertContentEquals(longArrayOf(0x4000, 0x2000, 0x800), plan.imageLayout())
        assertContentEquals(LongArray(24) { 0x1000L + it }, plan.exportRvas())
        assertOriginalLoaderBoundary(plan, originalPages, originalExports)
    }

    @Test fun hashSourceTreeAndDifferentBytesNeverCreateAPlan() {
        val fixture = fixture()
        assertFailsWith<IllegalArgumentException> {
            WindowsProfilePackagedVerifier.create(fixture.manifest, fixture.library, "0".repeat(64), SOURCE, TREE)
        }
        assertFailsWith<IllegalArgumentException> {
            WindowsProfilePackagedVerifier.create(fixture.manifest, fixture.library, fixture.hash, TREE, TREE)
        }
        assertFailsWith<IllegalArgumentException> {
            WindowsProfilePackagedVerifier.create(fixture.manifest, fixture.library, fixture.hash, SOURCE, SOURCE)
        }
        assertFailsWith<IllegalArgumentException> {
            WindowsProfilePackagedVerifier.create(fixture.manifest, fixture.library.copyOf().apply { this[0x400] = 1 },
                fixture.hash, SOURCE, TREE)
        }
    }

    @Test fun oversizedOrEmptyFactoryInputsRefuseBeforeParsing() {
        val fixture = fixture()
        for (manifest in listOf(ByteArray(0), ByteArray(4097))) {
            assertFailsWith<IllegalArgumentException> {
                WindowsProfilePackagedVerifier.create(manifest, fixture.library, fixture.hash, SOURCE, TREE)
            }
        }
        for (library in listOf(ByteArray(0), ByteArray(511), ByteArray(WindowsProfilePeImage.MAXIMUM_BYTES + 1))) {
            assertFailsWith<IllegalArgumentException> {
                WindowsProfilePackagedVerifier.create(fixture.manifest, library, fixture.hash, SOURCE, TREE)
            }
        }
    }

    @Test fun headerExecutablePaddingAndIatTerminatorChangesRefuseIndependently() {
        val fixture = fixture()
        val plan = fixture.plan()
        for ((page, offset) in listOf(0 to 0, 0 to 4095, 1 to 0, 1 to 4095, 2 to 8)) {
            val pages = fixture.pages()
            pages[page][offset] = (pages[page][offset].toInt() xor 1).toByte()
            assertFailsWith<IllegalArgumentException> {
                plan.verify(BASE, fixture.exportTargets(), longArrayOf(IMPORT_TARGET), pages)
            }
        }
    }

    @Test fun originalImportValueAndResolvedTargetMustAgreeExactly() {
        val fixture = fixture()
        val plan = fixture.plan()
        for (target in listOf(0L, -1L, BASE, IMPORT_TARGET + 1)) {
            assertFailsWith<IllegalArgumentException> {
                plan.verify(BASE, fixture.exportTargets(), longArrayOf(target), fixture.pages())
            }
        }
        val wrongSlot = fixture.pages().apply { this[2][0] = (this[2][0].toInt() xor 1).toByte() }
        assertFailsWith<IllegalArgumentException> {
            plan.verify(BASE, fixture.exportTargets(), longArrayOf(IMPORT_TARGET), wrongSlot)
        }
    }

    @Test fun everyExportIncludingRegistrarMustKeepItsOriginalRvaBinding() {
        val fixture = fixture()
        val plan = fixture.plan()
        repeat(24) { index ->
            val targets = fixture.exportTargets().apply { this[index]++ }
            assertFailsWith<IllegalArgumentException> {
                plan.verify(BASE, targets, longArrayOf(IMPORT_TARGET), fixture.pages())
            }
        }
    }

    @Test fun incompleteExtraAndWrongSizedReadbacksNeverReachJniPlanPublication() {
        val fixture = fixture()
        val plan = fixture.plan()
        val pages = fixture.pages()
        val variants = listOf(pages.copyOfRange(0, 2), pages + ByteArray(1),
            pages.copyOf().apply { this[0] = ByteArray(4095) },
            pages.copyOf().apply { this[2] = ByteArray(17) })
        for (candidate in variants) assertFailsWith<IllegalArgumentException> {
            plan.verify(BASE, fixture.exportTargets(), longArrayOf(IMPORT_TARGET), candidate)
        }
        for (targets in listOf(LongArray(0), LongArray(23), LongArray(25))) {
            assertFailsWith<IllegalArgumentException> { plan.verify(BASE, targets, longArrayOf(IMPORT_TARGET), pages) }
        }
        for (targets in listOf(LongArray(0), LongArray(2))) {
            assertFailsWith<IllegalArgumentException> { plan.verify(BASE, fixture.exportTargets(), targets, pages) }
        }
    }

    @Test fun baseChecksRejectUnalignedOverflowAndAbsentMappings() {
        val plan = fixture().plan()
        for (base in listOf(0L, -1L, BASE + 1, Long.MAX_VALUE - 0xfff)) {
            assertFailsWith<IllegalArgumentException> { plan.regions(base) }
        }
        val other = 0x7ff900000000L
        assertContentEquals(longArrayOf(other, 4096, 0, other + 0x1000, 4096, 1, other + 0x2880, 16, 2),
            plan.regions(other))
    }

    @Test fun exportDirectoryEscapesOnlyAsBoundedOriginalImmutableMetadata() {
        val library = WindowsProfilePeFixture.create()
        val expected = WindowsProfilePeImage.verify(library)
        val layout = WindowsProfilePeImage.exportLayout(library)
        library.fill(0)
        assertEquals(expected.sha256, layout.sha256)
        assertEquals(0x1200, layout.fileBytes)
        assertEquals(0x4000L, layout.imageBytes)
        assertEquals(0x2000L, layout.directoryRva)
        assertEquals(0x800L, layout.directoryBytes)
        assertEquals(expected.namedExports, layout.namedExports)
        assertFailsWith<UnsupportedOperationException> { (layout.namedExports as MutableList).clear() }
    }

    private fun assertOriginalLoaderBoundary(
        plan: WindowsProfilePackagedVerifier,
        pages: Array<ByteArray>,
        targets: LongArray,
    ) {
        if (plan.declaringClass().classLoader === ClassLoader.getSystemClassLoader()) {
            val result = plan.verify(BASE, targets, longArrayOf(IMPORT_TARGET), pages)
            assertContentEquals(expectedMethods.map { name ->
                val export = if (name == "pwp_jni_register_once") name else PREFIX + name
                targets[plan.exportNames().indexOf(export)]
            }.toLongArray(), result)
            result.fill(0)
            assertEquals(24, plan.verify(BASE, targets, longArrayOf(IMPORT_TARGET), pages).size)
        } else {
            // Gradle's isolated test loader is not the installed application's system classloader.
            // A separate fresh named-module/system-classpath JVM supplies the real connection positive.
            val failure = assertFailsWith<IllegalStateException> {
                plan.verify(BASE, targets, longArrayOf(IMPORT_TARGET), pages)
            }
            assertEquals("Windows JNI declaring class is not the maintained application class", failure.message)
        }
    }

    private class Fixture(val library: ByteArray, val manifest: ByteArray, val hash: String) {
        fun plan() = WindowsProfilePackagedVerifier.create(manifest, library, hash, SOURCE, TREE)
        fun exportTargets(): LongArray = LongArray(24) { BASE + 0x1000 + it }
        fun pages(): Array<ByteArray> = arrayOf(
            ByteArray(4096).also { library.copyInto(it, 0, 0, 0x400) },
            ByteArray(4096).also { library.copyInto(it, 0, 0x400, 0x600) },
            library.copyOfRange(0xe80, 0xe90).also { bytes ->
                for (index in 0..7) bytes[index] = (IMPORT_TARGET ushr (8 * index)).toByte()
            },
        )
    }

    private fun fixture(): Fixture {
        val library = WindowsProfilePeFixture.create()
        val manifest = WindowsProfileByteManifest.produce(SOURCE, TREE, true, library)
        val hash = MessageDigest.getInstance("SHA-256").digest(manifest).joinToString("") { "%02x".format(it) }
        return Fixture(library, manifest, hash)
    }

    companion object {
        private const val BASE = 0x180000000L
        private const val IMPORT_TARGET = 0x70000000L
        private const val SOURCE = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        private const val TREE = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        private const val PREFIX = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_"
        private val expectedMethods = listOf("abi", "capabilities", "openRoot", "child", "createChildDirectory",
            "identity", "fileIdentity", "exists", "names", "read", "lockExisting", "createProfileLock",
            "createVaultLock", "stageRecord", "prepareRecord", "writeRecord", "renameCandidate", "replaceCandidate",
            "syncDirectory", "discardStage", "requestExpectedFileDeletion", "deleteRecord", "close",
            "pwp_jni_register_once")
    }
}
