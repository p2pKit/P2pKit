package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class WindowsProfileByteManifestTest {
    @Test fun producerAndAuthorizerAgreeWithoutNativeCustodyOrSignatureClaims() {
        val dll = WindowsProfilePeFixture.create()
        val manifest = produce(dll)
        val result = WindowsProfileByteManifest.authorize(manifest, dll, authority(manifest))
        assertEquals(SOURCE, result.source)
        assertEquals(TREE, result.tree)
        assertEquals(hash(manifest), result.manifestSha256)
        assertEquals(hash(dll), result.dllSha256)
        assertEquals(dll.size, result.dllBytes)
        assertEquals(WindowsProfilePeImage.verify(dll).namedImports, result.namedImports)
        assertFailsWith<UnsupportedOperationException> {
            (result.namedImports as MutableList<WindowsProfilePeImage.NamedImport>).clear()
        }
        assertFalse(result.hasCertificateTable)
        assertEquals(WindowsProfileByteManifest.Scope.BYTE_MANIFEST_ONLY, result.scope)
        assertEquals("p2pkit-windows-profile.dll", result.file)
    }

    @Test fun producerIsDeterministicAndDoesNotMutateCallerBytes() {
        val dll = WindowsProfilePeFixture.create()
        val original = dll.copyOf()
        val first = produce(dll)
        assertTrue(first.contentEquals(produce(dll)))
        assertTrue(dll.contentEquals(original))
        first.fill(0)
        assertTrue(produce(dll).isNotEmpty())
    }

    @Test fun producerRejectsDirtyInvalidSourceAndInvalidPe() {
        val dll = WindowsProfilePeFixture.create()
        assertFailsWith<IllegalArgumentException> { WindowsProfileByteManifest.produce(SOURCE, TREE, false, dll) }
        for (bad in listOf("", "A".repeat(40), "a".repeat(39), "a".repeat(41), "../source")) {
            assertFailsWith<IllegalArgumentException> { WindowsProfileByteManifest.produce(bad, TREE, true, dll) }
            assertFailsWith<IllegalArgumentException> { WindowsProfileByteManifest.produce(SOURCE, bad, true, dll) }
        }
        assertFailsWith<IllegalArgumentException> { produce(ByteArray(512)) }
    }

    @Test fun authorityRejectsAbsentMalformedAndIncorrectExternalPins() {
        val dll = WindowsProfilePeFixture.create()
        val manifest = produce(dll)
        for (bad in listOf("", "a".repeat(63), "A".repeat(64), "a".repeat(65))) {
            assertFailsWith<IllegalArgumentException> { WindowsProfileByteManifest.Authority(bad, SOURCE, TREE) }
        }
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileByteManifest.authorize(
                manifest, dll, WindowsProfileByteManifest.Authority("0".repeat(64), SOURCE, TREE),
            )
        }
        assertFailsWith<IllegalArgumentException> { WindowsProfileByteManifest.Authority(hash(manifest), "HEAD", TREE) }
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileByteManifest.Authority(hash(manifest), SOURCE, "HEAD")
        }
    }

    @Test fun independentlyPinnedSourceAndTreeMustMatchEvenWhenManifestHashMatches() {
        val dll = WindowsProfilePeFixture.create()
        val manifest = produce(dll)
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileByteManifest.authorize(manifest, dll, authority(manifest, "c".repeat(40), TREE))
        }
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileByteManifest.authorize(manifest, dll, authority(manifest, SOURCE, "d".repeat(40)))
        }
        rejectsRePinned(manifest.replace("clean=true", "clean=false"), dll)
    }

    @Test fun jointlyReplacingDllAndManifestCannotRedefineExistingParentAuthority() {
        val dll = WindowsProfilePeFixture.create()
        val manifest = produce(dll)
        val pinned = authority(manifest)
        val changed = dll.copyOf().apply { this[0x400] = 1 }
        val changedManifest = produce(changed) // Structurally valid synthetic PE, different executable bytes.
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileByteManifest.authorize(changedManifest, changed, pinned)
        }
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileByteManifest.authorize(manifest, changed, pinned)
        }
    }

    @Test fun declaredLengthAndDigestMustMatchTheExactDllSnapshot() {
        val dll = WindowsProfilePeFixture.create()
        val manifest = produce(dll)
        rejectsRePinned(manifest.replace("bytes=${dll.size}", "bytes=${dll.size + 1}"), dll)
        rejectsRePinned(manifest.replace("sha256=${hash(dll)}", "sha256=${"0".repeat(64)}"), dll)
        rejectsRePinned(manifest.replace("sha256=${hash(dll)}", "sha256=${hash(dll).uppercase()}"), dll)
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileByteManifest.authorize(manifest, dll.copyOf(dll.size - 1), authority(manifest))
        }
    }

    @Test fun manifestBoundsAreCheckedBeforeParsing() {
        val dll = WindowsProfilePeFixture.create()
        for (manifest in listOf(ByteArray(0), ByteArray(4097) { 'x'.code.toByte() })) rejectsRePinned(manifest, dll)
        val manifest = produce(dll)
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileByteManifest.authorize(
                manifest, ByteArray(WindowsProfilePeImage.MAXIMUM_BYTES + 1), authority(manifest),
            )
        }
    }

    @Test fun canonicalEncodingRejectsBomNullNonAsciiCrLfMissingOrExtraFinalNewlines() {
        val dll = WindowsProfilePeFixture.create()
        val manifest = produce(dll)
        val variants = listOf(
            byteArrayOf(0xef.toByte(), 0xbb.toByte(), 0xbf.toByte()) + manifest,
            manifest.copyOf().apply { this[0] = 0 },
            manifest.copyOf().apply { this[0] = 0x80.toByte() },
            manifest.replace("\n", "\r\n"), manifest.dropLast(1).toByteArray(), manifest + byteArrayOf(10),
        )
        variants.forEach { rejectsRePinned(it, dll) }
    }

    @Test fun duplicateUnknownReorderedWhitespaceAndMissingFieldsAreRejected() {
        val dll = WindowsProfilePeFixture.create()
        val manifest = produce(dll)
        val text = manifest.toString(Charsets.US_ASCII)
        val lines = text.trimEnd('\n').split('\n')
        val abi = "abi=${WindowsProfilePeImage.ABI}"
        val variants = listOf(
            text + "$abi\n", text + "unknown=true\n", text.replace(abi, " $abi"),
            lines.reversed().joinToString("\n", postfix = "\n"),
            lines.drop(1).joinToString("\n", postfix = "\n"), text.replace("clean=true", "clean=true "),
        )
        variants.forEach { rejectsRePinned(it.toByteArray(Charsets.US_ASCII), dll) }
    }

    @Test fun schemaComponentAbiPlatformArchitectureAndCapabilitiesAreExact() {
        val dll = WindowsProfilePeFixture.create()
        val manifest = produce(dll)
        val abi = "abi=${WindowsProfilePeImage.ABI}"
        for ((old, new) in listOf(
            "schema=1" to "schema=2", "component=windows-profile-custody" to "component=profile",
            abi to "abi=1", abi to "abi=2", abi to "abi=3", abi to "abi=4", abi to "abi=5", abi to "abi=6",
            abi to "abi=7", abi to "abi=8", abi to "abi=9", abi to "abi=10", abi to "abi=11", abi to "abi=12",
            "platform=windows" to "platform=linux",
            "arch=x86_64" to "arch=arm64", "capabilities=0x43" to "capabilities=0x7f",
        )) rejectsRePinned(manifest.replace(old, new), dll)
    }

    @Test fun numericAbiStillRejectsTwelveWithTheSeparateRegistrarExport() {
        val dll = WindowsProfilePeFixture.create()
        assertEquals(24, WindowsProfilePeImage.verify(dll).exports.size)
        assertEquals(13, WindowsProfilePeImage.ABI)
        // Adding a registrar changes no custody semantics; numeric ABI13 remains an independent prerequisite.
        rejectsRePinned(produce(dll).replace("abi=13", "abi=12"), dll)
    }

    @Test fun fileNameCannotBecomeAnAbsoluteRelativeOrAlternateStreamLoadPath() {
        val dll = WindowsProfilePeFixture.create()
        val manifest = produce(dll)
        for (name in listOf("../evil.dll", "C:\\evil.dll", "\\\\host\\evil.dll", "x.dll:stream", "evil.dll", "")) {
            rejectsRePinned(manifest.replace("file=p2pkit-windows-profile.dll", "file=$name"), dll)
        }
    }

    @Test fun decimalLengthCannotOverflowOrUseSignsWhitespaceOrAlternateSpellings() {
        val dll = WindowsProfilePeFixture.create()
        val manifest = produce(dll)
        for (value in listOf("0", "511", "-1", "+${dll.size}", "0${dll.size}", "1.0", " 1", "9".repeat(100))) {
            rejectsRePinned(manifest.replace("bytes=${dll.size}", "bytes=$value"), dll)
        }
    }

    @Test fun digestCorrectButMalformedNativeImageStillFailsPeAdmission() {
        val dll = WindowsProfilePeFixture.create()
        val malformed = dll.copyOf().apply { this[0] = 0 }
        val manifest = produce(dll).replace("sha256=${hash(dll)}", "sha256=${hash(malformed)}")
        rejectsRePinned(manifest, malformed)
    }

    @Test fun certificateFramingPresenceIsNotAuthenticodeOrFileCustodyEvidence() {
        val original = WindowsProfilePeFixture.create()
        val dll = original.copyOf(original.size + 16)
        ByteBuffer.wrap(dll).order(ByteOrder.LITTLE_ENDIAN).apply {
            putInt(0x98 + 112 + 4 * 8, original.size); putInt(0x98 + 116 + 4 * 8, 16)
            putInt(original.size, 16); putShort(original.size + 4, 0x200); putShort(original.size + 6, 2)
        }
        val manifest = produce(dll)
        val observation = WindowsProfileByteManifest.authorize(manifest, dll, authority(manifest))
        assertTrue(observation.hasCertificateTable)
        assertEquals(WindowsProfileByteManifest.Scope.BYTE_MANIFEST_ONLY, observation.scope)
    }

    @Test fun subsequentCallerMutationCannotChangeReturnedByteAuthorization() {
        val dll = WindowsProfilePeFixture.create()
        val manifest = produce(dll)
        val expected = WindowsProfileByteManifest.authorize(manifest, dll, authority(manifest))
        dll.fill(0); manifest.fill(0)
        val pristine = WindowsProfilePeFixture.create()
        val secondManifest = produce(pristine)
        assertEquals(
            expected, WindowsProfileByteManifest.authorize(secondManifest, pristine, authority(secondManifest)),
        )
    }

    private fun produce(dll: ByteArray) = WindowsProfileByteManifest.produce(SOURCE, TREE, true, dll)
    private fun hash(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }
    private fun ByteArray.replace(old: String, new: String): ByteArray {
        val text = toString(Charsets.US_ASCII)
        assertTrue(old in text)
        return text.replace(old, new).toByteArray(Charsets.US_ASCII)
    }
    private fun authority(manifest: ByteArray, source: String = SOURCE, tree: String = TREE) =
        WindowsProfileByteManifest.Authority(hash(manifest), source, tree)
    private fun rejectsRePinned(manifest: ByteArray, dll: ByteArray) {
        // A well-formed parent pin cannot override this component's schema/PE policy.
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileByteManifest.authorize(manifest, dll, authority(manifest))
        }
    }
    companion object {
        private const val SOURCE = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        private const val TREE = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    }
}
