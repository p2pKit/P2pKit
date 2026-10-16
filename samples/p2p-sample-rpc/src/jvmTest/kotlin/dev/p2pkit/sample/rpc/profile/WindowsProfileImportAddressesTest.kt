package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

/** Inert PE bytes and address comparisons only; no Windows lookup, native memory, JNI or installed evidence. */
class WindowsProfileImportAddressesTest {
    @Test fun everyOriginalSlotMatchesItsOwnResolutionIndependentOfObservationOrder() {
        val image = image()
        assertEquals(2, image.namedImports.size)
        for (base in listOf(BASE, 0x7ff900000000L)) {
            val resolved = resolutions(image)
            WindowsProfileImportAddresses.verify(image, base, image.imageBytes,
                resolved.reversed(), slots(image, resolved, base).reversed())
        }
        assertEquals(WindowsProfileByteManifest.Scope.BYTE_MANIFEST_ONLY, image.scope)
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test fun distinctLogicalImportsMayHaveAnIdenticalForwardedTarget() {
        val image = image()
        val resolved = resolutions(image).map { it.copy(address = TARGET) }
        // No physical DLL name is inferred from kernel32's logical name or from this arbitrary number.
        verify(image, resolved, slots(image, resolved))
    }

    @Test fun identicalFunctionNamesFromDifferentLogicalLibrariesHaveDistinctBindings() {
        val original = image()
        val imports = original.namedImports
        val image = original.copy(namedImports = listOf(imports[0],
            imports[1].copy(library = "advapi32.dll", function = imports[0].function)))
        val resolved = resolutions(image)
        verify(image, resolved, slots(image, resolved))
        assertFailsWith<IllegalArgumentException> {
            verify(image, resolved.map { it.copy(library = "kernel32.dll") }, slots(image, resolved))
        }
    }

    @Test fun missingExtraDuplicateAndUnknownResolutionsRefuse() {
        val image = image()
        val resolved = resolutions(image)
        val variants = listOf(resolved.dropLast(1), resolved + resolved.first(),
            listOf(resolved.first(), resolved.first()),
            listOf(resolved.first().copy(function = "UnknownExport"), resolved.last()),
            listOf(resolved.first().copy(function = "a".repeat(129)), resolved.last()),
            listOf(resolved.first().copy(library = "a".repeat(65)), resolved.last()),
            listOf(resolved.first().copy(library = "kernelbase.dll"), resolved.last()))
        for (candidate in variants) assertFailsWith<IllegalArgumentException> {
            verify(image, candidate, slots(image, resolved))
        }
    }

    @Test fun missingExtraDuplicateAndUnknownSlotAddressesRefuse() {
        val image = image()
        val actual = slots(image)
        val variants = listOf(actual.dropLast(1), actual + actual.first(),
            listOf(actual.first(), actual.first()),
            listOf(actual.first().copy(address = BASE + 0x1000), actual.last()),
            listOf(actual.first().copy(address = image.namedImports.first().addressRva), actual.last()))
        for (candidate in variants) assertFailsWith<IllegalArgumentException> { verify(image, readback = candidate) }
    }

    @Test fun sameModuleWrongFunctionAndSwappedTargetsAreNotAccepted() {
        val image = image()
        val actual = slots(image)
        for (target in listOf(0L, -1L, TARGET + 1, BASE + 0x1000)) {
            assertFailsWith<IllegalArgumentException> {
                verify(image, readback = listOf(actual.first().copy(target = target), actual.last()))
            }
        }
        assertFailsWith<IllegalArgumentException> {
            verify(image, readback = listOf(actual.first().copy(target = actual.last().target),
                actual.last().copy(target = actual.first().target)))
        }
    }

    @Test fun matchingReadbackCannotLegitimizeNullNegativeOrCandidateImageTargets() {
        val image = image()
        for (target in listOf(0L, -1L, Long.MIN_VALUE, BASE, BASE + image.imageBytes - 1)) {
            val resolved = resolutions(image).map { it.copy(address = target) }
            assertFailsWith<IllegalArgumentException> { verify(image, resolved, slots(image, resolved)) }
        }
    }

    @Test fun imageBaseAndCompleteMappedExtentMustBeExactAndNonwrapping() {
        val image = image()
        for (base in listOf(0L, 1L, BASE + 1, -65_536L, Long.MIN_VALUE, Long.MAX_VALUE and -65_536L)) {
            val pinned = if (base == (Long.MAX_VALUE and -65_536L)) image.copy(imageBytes = 128L * 1024 * 1024)
                else image
            assertFailsWith<IllegalArgumentException> {
                WindowsProfileImportAddresses.verify(pinned, base, pinned.imageBytes, resolutions(image), slots(image))
            }
        }
        for (size in listOf(0L, image.dllBytes.toLong(), image.imageBytes - 1, image.imageBytes + 1, Long.MAX_VALUE)) {
            assertFailsWith<IllegalArgumentException> {
                WindowsProfileImportAddresses.verify(image, BASE, size, resolutions(image), slots(image))
            }
        }
    }

    @Test fun pinnedSlotsMustBeUniqueAlignedAndFullyInsideTheImage() {
        val original = image()
        val first = original.namedImports.first()
        val second = original.namedImports.last()
        val variants = listOf(first.copy(lookupRva = 0), first.copy(addressRva = 0),
            first.copy(lookupRva = 1), first.copy(addressRva = 1),
            first.copy(lookupRva = -8), first.copy(addressRva = Long.MAX_VALUE),
            first.copy(lookupRva = original.imageBytes), first.copy(addressRva = original.imageBytes),
            first.copy(lookupRva = second.lookupRva), first.copy(addressRva = second.addressRva),
            first.copy(lookupRva = first.addressRva), first.copy(lookupRva = second.addressRva),
            first.copy(addressRva = second.lookupRva))
        for (variant in variants) {
            val image = original.copy(namedImports = listOf(variant, second))
            assertFailsWith<IllegalArgumentException> { verify(image) }
        }
    }

    @Test fun malformedPinnedLogicalImportsAndDuplicateTuplesRefuse() {
        val original = image()
        val first = original.namedImports.first()
        val second = original.namedImports.last()
        val variants = listOf(first.copy(library = "KERNEL32.dll"), first.copy(library = "kernelbase.dll"),
            first.copy(library = "../kernel32.dll"), first.copy(function = ""),
            first.copy(function = "a".repeat(129)), first.copy(function = "#1"),
            first.copy(function = "CloseHandle\u0000"), first.copy(function = second.function))
        for (variant in variants) assertFailsWith<IllegalArgumentException> {
            verify(original.copy(namedImports = listOf(variant, second)))
        }
    }

    @Test fun boundedInputsAreReadExactlyOnceAndNotRevisitedDuringComparison() {
        val image = image()
        val imports = Once(image.namedImports)
        val resolved = Once(resolutions(image))
        val readback = Once(slots(image))
        verify(image.copy(namedImports = imports), resolved, readback)
        for (reads in listOf(imports.reads, resolved.reads, readback.reads)) {
            assertEquals(listOf(1, 1), reads.toList())
        }
    }

    @Test fun emptyOversizedAndMismatchedCountsRefuseBeforeConsumingAnEntry() {
        val image = image()
        for (count in listOf(0, 4097, Int.MAX_VALUE)) {
            val imports = Unread<WindowsProfilePeImage.NamedImport>(count)
            val resolved = Unread<WindowsProfileImportAddresses.ResolvedImport>(count)
            val readback = Unread<WindowsProfileImportAddresses.IatSlot>(count)
            assertFailsWith<IllegalArgumentException> { verify(image.copy(namedImports = imports), resolved, readback) }
        }
        val imports = Unread<WindowsProfilePeImage.NamedImport>(2)
        for ((resolutionCount, slotCount) in listOf(1 to 2, 2 to 1, 3 to 2, 2 to 3)) {
            assertFailsWith<IllegalArgumentException> {
                verify(image.copy(namedImports = imports), Unread(resolutionCount), Unread(slotCount))
            }
        }
    }

    private fun verify(
        image: WindowsProfileByteManifest.ByteAuthorization,
        resolved: List<WindowsProfileImportAddresses.ResolvedImport> = resolutions(image),
        readback: List<WindowsProfileImportAddresses.IatSlot> = slots(image, resolved),
    ) = WindowsProfileImportAddresses.verify(image, BASE, image.imageBytes, resolved, readback)

    private fun resolutions(image: WindowsProfileByteManifest.ByteAuthorization) =
        image.namedImports.mapIndexed { index, entry ->
            WindowsProfileImportAddresses.ResolvedImport(entry.library, entry.function, TARGET + index * 16)
        }

    private fun slots(
        image: WindowsProfileByteManifest.ByteAuthorization,
        resolved: List<WindowsProfileImportAddresses.ResolvedImport> = resolutions(image),
        base: Long = BASE,
    ) = image.namedImports.mapIndexed { index, entry ->
        WindowsProfileImportAddresses.IatSlot(base + entry.addressRva, resolved[index].address)
    }

    private fun image(): WindowsProfileByteManifest.ByteAuthorization {
        val bytes = WindowsProfilePeFixture.create()
        // Extend the existing real parser fixture with one distinct named import and complete null terminators.
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).apply {
            putInt(0x98 + 116 + 12 * 8, 24)
            putLong(0xe68, 0x28c0)
            putLong(0xe88, 0x28c0)
        }
        "GetCurrentProcess".toByteArray(Charsets.US_ASCII).copyInto(bytes, 0xec2)
        val source = "a".repeat(40)
        val tree = "b".repeat(40)
        val manifest = WindowsProfileByteManifest.produce(source, tree, true, bytes)
        val hash = MessageDigest.getInstance("SHA-256").digest(manifest).joinToString("") { "%02x".format(it) }
        return WindowsProfileByteManifest.authorize(
            manifest, bytes, WindowsProfileByteManifest.Authority(hash, source, tree),
        )
    }

    private class Once<T>(private val original: List<T>) : AbstractList<T>() {
        override val size = original.size
        val reads = IntArray(size)
        override fun get(index: Int): T = original[index].also { check(++reads[index] == 1) }
    }

    private class Unread<T>(override val size: Int) : AbstractList<T>() {
        override fun get(index: Int): T = error("Rejected inventory must not be consumed")
    }

    private companion object {
        const val BASE = 0x180000000L
        const val TARGET = 0x7ffa00001001L
    }
}
