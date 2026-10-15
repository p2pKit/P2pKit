package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals

/** Inert PE bytes and address arithmetic only. No Windows load, JNI execution or installed-runtime evidence. */
class WindowsProfileExportAddressesTest {
    @Test fun exportBindingsFollowOrdinalTableRatherThanSortedNamePosition() {
        val bytes = WindowsProfilePeFixture.create()
        val names = WindowsProfilePeImage.expectedExports.sorted()
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        names.indices.forEach { index ->
            buffer.putShort(WindowsProfilePeFixture.EXPORT_ORDINALS + index * 2, (names.lastIndex - index).toShort())
        }
        val image = WindowsProfilePeImage.verify(bytes)
        assertEquals(0x4000L, image.imageBytes)
        assertEquals(names.mapIndexed { index, name ->
            WindowsProfilePeImage.NamedExport(name, names.size - index, 0x1000L + names.lastIndex - index)
        }, image.namedExports)
    }

    @Test fun exactBindingUsesActualBaseRatherThanPreferredImageBase() {
        val image = authorize()
        for (base in listOf(0x180000000L, 0x7ff900000000L)) {
            WindowsProfileExportAddresses.verify(image, base, image.imageBytes, resolve(image, base).reversed())
        }
        assertNotEquals(resolve(image, 0x180000000L), resolve(image, 0x7ff900000000L))
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test fun linkerFoldedFunctionsRemainValidWhenBothOriginalBindingsMatch() {
        val bytes = WindowsProfilePeFixture.create()
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
            .putInt(WindowsProfilePeFixture.EXPORT_FUNCTIONS + 4, 0x1000)
        val image = authorize(bytes)
        assertEquals(image.namedExports[0].functionRva, image.namedExports[1].functionRva)
        assertNotEquals(image.namedExports[0].ordinal, image.namedExports[1].ordinal)
        WindowsProfileExportAddresses.verify(image, BASE, image.imageBytes, resolve(image))
    }

    @Test fun byteAuthorizationRetainsImmutableExportBindingsFromTheSameSnapshot() {
        val bytes = WindowsProfilePeFixture.create()
        val observed = WindowsProfilePeImage.verify(bytes)
        val image = authorize(bytes)
        assertEquals(observed.namedExports, image.namedExports)
        assertEquals(observed.imageBytes, image.imageBytes)
        for (bindings in listOf(observed.namedExports, image.namedExports)) {
            assertFailsWith<UnsupportedOperationException> {
                (bindings as MutableList<WindowsProfilePeImage.NamedExport>).clear()
            }
        }
        bytes.fill(0)
        assertEquals(authorize(), image)
        assertEquals(WindowsProfileByteManifest.Scope.BYTE_MANIFEST_ONLY, image.scope)
    }

    @Test fun nullMisalignedNegativeAndWrappingImageBasesAreRejected() {
        val image = authorize()
        for (base in listOf(0L, 1L, BASE + 1, -65_536L, Long.MIN_VALUE)) {
            assertFailsWith<IllegalArgumentException> {
                WindowsProfileExportAddresses.verify(image, base, image.imageBytes, resolve(image))
            }
        }
        // A large aligned positive base must not wrap even when individual low export RVAs still fit.
        val large = image.copy(imageBytes = 128L * 1024 * 1024)
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileExportAddresses.verify(large, Long.MAX_VALUE and -65_536L, large.imageBytes, resolve(image))
        }
    }

    @Test fun observedMappingSizeMustEqualPinnedSizeOfImage() {
        val image = authorize()
        for (size in listOf(0L, image.dllBytes.toLong(), image.imageBytes - 1, image.imageBytes + 1, Long.MAX_VALUE)) {
            assertFailsWith<IllegalArgumentException> {
                WindowsProfileExportAddresses.verify(image, BASE, size, resolve(image))
            }
        }
    }

    @Test fun missingExtraDuplicateAndUnrecognizedResolutionsFail() {
        val image = authorize()
        val actual = resolve(image)
        val variants = listOf(
            actual.dropLast(1), actual + actual.first(),
            actual.toMutableList().apply { this[1] = first() },
            actual.toMutableList().apply { this[0] = first().copy(name = "Java_unknown") },
        )
        for (resolved in variants) assertFailsWith<IllegalArgumentException> {
            WindowsProfileExportAddresses.verify(image, BASE, image.imageBytes, resolved)
        }
    }

    @Test fun insideImageWrongFunctionAndOtherModuleAddressesAreRejected() {
        val image = authorize()
        val original = resolve(image)
        for (address in listOf(0L, BASE, BASE + 0x1001, BASE + image.imageBytes, BASE + 65_536 + 0x1000)) {
            val changed = original.toMutableList().apply { this[0] = first().copy(address = address) }
            assertFailsWith<IllegalArgumentException> {
                WindowsProfileExportAddresses.verify(image, BASE, image.imageBytes, changed)
            }
        }
    }

    @Test fun reorderingExportOrdinalsCannotBeAuthorizedByAnUnchangedParentPin() {
        val bytes = WindowsProfilePeFixture.create()
        val manifest = WindowsProfileByteManifest.produce(SOURCE, TREE, true, bytes)
        val authority = WindowsProfileByteManifest.Authority(hash(manifest), SOURCE, TREE)
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).apply {
            putShort(WindowsProfilePeFixture.EXPORT_ORDINALS, 1)
            putShort(WindowsProfilePeFixture.EXPORT_ORDINALS + 2, 0)
        }
        // Still structurally valid and same export names; altered bindings nevertheless change pinned bytes.
        assertEquals(WindowsProfilePeImage.expectedExports, WindowsProfilePeImage.verify(bytes).exports)
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileByteManifest.authorize(manifest, bytes, authority)
        }
        val replacement = WindowsProfileByteManifest.produce(SOURCE, TREE, true, bytes)
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileByteManifest.authorize(replacement, bytes, authority)
        }
    }

    @Test fun malformedOrPartialByteObservationsAreRejected() {
        val image = authorize()
        val first = image.namedExports.first()
        val invalid = listOf(
            image.copy(namedExports = image.namedExports.dropLast(1)),
            image.copy(namedExports = listOf(first) + image.namedExports.drop(1).map { it.copy(ordinal = 1) }),
            image.copy(namedExports = listOf(first.copy(functionRva = image.imageBytes)) + image.namedExports.drop(1)),
            image.copy(namedExports = listOf(first.copy(name = "Java_unknown")) + image.namedExports.drop(1)),
            image.copy(imageBytes = 0),
        )
        for (candidate in invalid) assertFailsWith<IllegalArgumentException> {
            WindowsProfileExportAddresses.verify(candidate, BASE, candidate.imageBytes, resolve(image))
        }
    }

    private fun authorize(bytes: ByteArray = WindowsProfilePeFixture.create()):
        WindowsProfileByteManifest.ByteAuthorization {
        val manifest = WindowsProfileByteManifest.produce(SOURCE, TREE, true, bytes)
        return WindowsProfileByteManifest.authorize(
            manifest, bytes, WindowsProfileByteManifest.Authority(hash(manifest), SOURCE, TREE),
        )
    }

    private fun resolve(image: WindowsProfileByteManifest.ByteAuthorization, base: Long = BASE) =
        image.namedExports.map { WindowsProfileExportAddresses.ResolvedExport(it.name, base + it.functionRva) }

    private fun hash(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }

    private companion object {
        const val SOURCE = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        const val TREE = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        const val BASE = 0x180000000L
    }
}
