package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

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

    @Test fun fullIatPlanRequiresEveryPageBoundedByteAtEitherImageBase() {
        val bytes = fullLibrary()
        val image = image(bytes)
        val plan = WindowsProfileImportAddresses.prepare(bytes, image)
        for (base in listOf(BASE, BASE + 65_536)) {
            assertEquals(listOf(WindowsProfileImportAddresses.Region(base + FULL_IAT_RVA, 16),
                WindowsProfileImportAddresses.Region(base + FULL_IAT_RVA + 16, 24)),
                plan.regions(base, image.imageBytes))
            val resolved = resolutions(image).map { it.copy(address = TARGET) }
            plan.verify(base, image.imageBytes, resolved.reversed(),
                fullReadback(bytes, image, resolved, base).reversed())
        }
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test fun completeIatTerminatorAndNonzeroPaddingChangesRefuseWhileNamedOnlyComparisonCannotSeeThem() {
        val bytes = fullLibrary()
        val image = image(bytes)
        val plan = WindowsProfileImportAddresses.prepare(bytes, image)
        // Original leading/trailing bytes are deliberately nonzero; only the two declared slots may change.
        assertTrue(bytes[FULL_IAT_FILE] != 0.toByte())
        assertTrue(bytes[FULL_IAT_FILE + 39] != 0.toByte())
        for (offset in (0 until 8) + (24 until 40)) {
            val actual = fullReadback(bytes, image)
            val region = if (offset < 16) actual.first() else actual.last()
            val local = if (offset < 16) offset else offset - 16
            region.bytes[local] = (region.bytes[local].toInt() xor 1).toByte()
            // Existing slot verification remains intentionally narrower; this unchanged inventory still passes.
            verify(image)
            assertFailsWith<IllegalArgumentException> {
                plan.verify(BASE, image.imageBytes, resolutions(image), actual)
            }
        }
    }

    @Test fun completeIatUsesExactResolvedNamedSlotsAndRejectsPartialOrDuplicateInventory() {
        val bytes = fullLibrary()
        val image = image(bytes)
        val plan = WindowsProfileImportAddresses.prepare(bytes, image)
        val actual = fullReadback(bytes, image)
        val badLists = listOf(emptyList(), actual.dropLast(1), actual + actual.first(),
            listOf(actual.first(), actual.first()),
            listOf(actual.first().copy(address = actual.first().address + 8), actual.last()),
            listOf(actual.first().copy(bytes = actual.first().bytes.copyOf(8)), actual.last()),
            listOf(actual.first(), actual.last().copy(bytes = actual.last().bytes.copyOf(32))))
        for (candidate in badLists) assertFailsWith<IllegalArgumentException> {
            plan.verify(BASE, image.imageBytes, resolutions(image), candidate)
        }
        for (offset in 8 until 24) {
            val changed = fullReadback(bytes, image)
            val region = if (offset < 16) changed.first() else changed.last()
            val local = if (offset < 16) offset else offset - 16
            region.bytes[local] = (region.bytes[local].toInt() xor 1).toByte()
            assertFailsWith<IllegalArgumentException> {
                plan.verify(BASE, image.imageBytes, resolutions(image), changed)
            }
        }
    }

    @Test fun completeIatPlanCannotBeReboundByChangedBytesImportTuplesOrSize() {
        val bytes = fullLibrary()
        val image = image(bytes)
        val changed = bytes.copyOf().apply { this[FULL_IAT_FILE] = 0 }
        assertFailsWith<IllegalArgumentException> { WindowsProfileImportAddresses.prepare(changed, image) }
        val changedImports = image.namedImports.toMutableList().apply { this[0] = this[0].copy(function = "Other") }
        for (bad in listOf(image.copy(dllBytes = image.dllBytes - 1), image.copy(imageBytes = image.imageBytes + 4096),
            image.copy(namedImports = changedImports), image.copy(namedImports = image.namedImports.reversed()))) {
            assertFailsWith<IllegalArgumentException> { WindowsProfileImportAddresses.prepare(bytes, bad) }
        }
        assertFailsWith<IllegalArgumentException> { WindowsProfileImportAddresses.prepare(ByteArray(511), image) }
    }

    @Test fun completeIatSnapshotAndInventoryCannotBeChangedByLaterCallerMutation() {
        val bytes = fullLibrary()
        val image = image(bytes)
        val imports = image.namedImports.toMutableList()
        val plan = WindowsProfileImportAddresses.prepare(bytes, image.copy(namedImports = imports))
        val actual = fullReadback(bytes, image)
        bytes.fill(0)
        imports.clear()
        plan.verify(BASE, image.imageBytes, resolutions(image), actual)
        assertFailsWith<UnsupportedOperationException> {
            (plan.regions(BASE, image.imageBytes) as MutableList<WindowsProfileImportAddresses.Region>).clear()
        }
        // Resolution collection happens after the readback's private snapshot; mutate a consumed caller array.
        val resolved = resolutions(image)
        val mutation = object : AbstractList<WindowsProfileImportAddresses.ResolvedImport>() {
            override val size = resolved.size
            override fun get(index: Int): WindowsProfileImportAddresses.ResolvedImport {
                actual.forEach { it.bytes.fill(0) }
                return resolved[index]
            }
        }
        plan.verify(BASE, image.imageBytes, mutation, actual)
        assertFailsWith<IllegalArgumentException> { plan.verify(BASE, image.imageBytes, resolved, actual) }
    }

    @Test fun completeIatBoundsInventoryBeforeReadingAndConsumesEachEntryOnce() {
        val bytes = fullLibrary()
        val image = image(bytes)
        val plan = WindowsProfileImportAddresses.prepare(bytes, image)
        val actual = Once(fullReadback(bytes, image))
        val resolved = Once(resolutions(image))
        plan.verify(BASE, image.imageBytes, resolved, actual)
        assertEquals(listOf(1, 1), actual.reads.toList())
        assertEquals(listOf(1, 1), resolved.reads.toList())
        for (count in listOf(0, 1, 3, Int.MAX_VALUE)) assertFailsWith<IllegalArgumentException> {
            plan.verify(BASE, image.imageBytes, resolutions(image), Unread(count))
        }
        for (base in listOf(0L, BASE + 1, -65_536L)) assertFailsWith<IllegalArgumentException> {
            plan.regions(base, image.imageBytes)
        }
        for (size in listOf(0L, image.imageBytes - 1, image.imageBytes + 1, Long.MAX_VALUE)) {
            assertFailsWith<IllegalArgumentException> { plan.regions(BASE, size) }
            assertFailsWith<IllegalArgumentException> { plan.verify(BASE, size, resolutions(image), Unread(2)) }
        }
    }

    private fun fullReadback(
        bytes: ByteArray,
        image: WindowsProfileByteManifest.ByteAuthorization,
        resolved: List<WindowsProfileImportAddresses.ResolvedImport> = resolutions(image),
        base: Long = BASE,
    ): List<WindowsProfileImportAddresses.Readback> {
        val actual = bytes.copyOfRange(FULL_IAT_FILE, FULL_IAT_FILE + 40)
        val buffer = ByteBuffer.wrap(actual).order(ByteOrder.LITTLE_ENDIAN)
        image.namedImports.forEachIndexed { index, entry ->
            buffer.putLong((entry.addressRva - FULL_IAT_RVA).toInt(), resolved[index].address)
        }
        return listOf(WindowsProfileImportAddresses.Readback(base + FULL_IAT_RVA, actual.copyOfRange(0, 16)),
            WindowsProfileImportAddresses.Readback(base + FULL_IAT_RVA + 16, actual.copyOfRange(16, 40)))
    }

    private fun fullLibrary(): ByteArray = library().copyOf(0x3200).apply {
        val bytes = this
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).apply {
            putShort(0x86, 4)
            putInt(0x98 + 56, 0x6000)
            val section = 0x98 + 240 + 120
            ".idata".toByteArray(Charsets.US_ASCII).copyInto(bytes, section)
            putInt(section + 8, 0x2000)
            putInt(section + 12, 0x4000)
            putInt(section + 16, 0x2000)
            putInt(section + 20, 0x1200)
            putInt(section + 36, 0x40000040)
            putInt(0x98 + 112 + 12 * 8, FULL_IAT_RVA.toInt())
            putInt(0x98 + 116 + 12 * 8, 40)
            putInt(0xe10, FULL_IAT_RVA.toInt() + 8)
            putLong(FULL_IAT_FILE + 8, 0x28a0)
            putLong(FULL_IAT_FILE + 16, 0x28c0)
        }
        for (index in (0 until 8) + (32 until 40)) this[FULL_IAT_FILE + index] = (index + 1).toByte()
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

    private fun library(): ByteArray {
        val bytes = WindowsProfilePeFixture.create()
        // Extend the existing real parser fixture with one distinct named import and complete null terminators.
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).apply {
            putInt(0x98 + 116 + 12 * 8, 24)
            putLong(0xe68, 0x28c0)
            putLong(0xe88, 0x28c0)
        }
        "GetCurrentProcess".toByteArray(Charsets.US_ASCII).copyInto(bytes, 0xec2)
        return bytes
    }

    private fun image(bytes: ByteArray = library()): WindowsProfileByteManifest.ByteAuthorization {
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
        const val FULL_IAT_RVA = 0x4ff0L
        const val FULL_IAT_FILE = 0x21f0
        const val BASE = 0x180000000L
        const val TARGET = 0x7ffa00001001L
    }
}
