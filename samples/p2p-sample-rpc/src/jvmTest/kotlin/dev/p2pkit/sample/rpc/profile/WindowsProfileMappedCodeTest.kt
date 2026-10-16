package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

/** Inert byte readbacks only: no native memory, DLL load, installed authority or Windows execution. */
class WindowsProfileMappedCodeTest {
    @Test fun exactOriginalCodeAtPreferredAndOtherBasesPassesWithoutGrantingAvailability() {
        val bytes = fixture()
        val plan = prepare(bytes)
        for (base in listOf(PREFERRED, PREFERRED - 65_536, PREFERRED + 65_536)) {
            assertEquals(listOf(WindowsProfileMappedCode.Region(base, 0x1000, false),
                WindowsProfileMappedCode.Region(base + 0x1000, 0x1000)), plan.regions(base, IMAGE_SIZE))
            plan.verify(base, IMAGE_SIZE, listOf(header(bytes, base), readback(bytes, base)))
        }
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test fun changedCodeFailsEvenWhenAllExportNamesAndAddressesStillMatch() {
        val bytes = fixture()
        val plan = prepare(bytes)
        for (index in listOf(0, 1, 255, 511)) {
            val actual = readback(bytes).also { it.bytes[index] = (it.bytes[index].toInt() xor 1).toByte() }
            assertFailsWith<IllegalArgumentException> { plan.verify(PREFERRED, IMAGE_SIZE, listOf(header(bytes), actual)) }
        }
    }

    @Test fun appliesOnlyValidatedDir64WritesWithBothDeltaSignsAndUnsignedWraparound() {
        for (original in listOf(0L, PREFERRED + 0x1000, Long.MAX_VALUE, Long.MIN_VALUE, -1L)) {
            val bytes = fixture().apply {
                buffer().putInt(0x1000, 0x1000).putShort(0x1008, 0xa081.toShort())
                buffer().putLong(0x481, original)
            }
            val plan = prepare(bytes)
            for (base in listOf(PREFERRED, PREFERRED - 65_536, PREFERRED + 65_536)) {
                val observed = readback(bytes, base)
                ByteBuffer.wrap(observed.bytes).order(ByteOrder.LITTLE_ENDIAN)
                    .putLong(0x81, original + base - PREFERRED)
                plan.verify(base, IMAGE_SIZE, listOf(header(bytes, base), observed))
                observed.bytes[0x82] = (observed.bytes[0x82].toInt() xor 1).toByte()
                assertFailsWith<IllegalArgumentException> {
                    plan.verify(base, IMAGE_SIZE, listOf(header(bytes, base), observed))
                }
            }
        }
    }

    @Test fun adjacentFixupsAreAppliedOnceEachAndAbsolutePaddingNeverWritesCode() {
        val bytes = fixture().apply {
            buffer().putInt(0x1000, 0x1000).putShort(0x1008, 0xa088.toShort()).putShort(0x100a, 0xa080.toShort())
            buffer().putLong(0x480, 101).putLong(0x488, -201)
        }
        val base = PREFERRED + 65_536
        val actual = readback(bytes, base)
        ByteBuffer.wrap(actual.bytes).order(ByteOrder.LITTLE_ENDIAN).putLong(0x80, 101 + 65_536L)
            .putLong(0x88, -201 + 65_536L)
        prepare(bytes).verify(base, IMAGE_SIZE, listOf(header(bytes, base), actual))
        val absolute = fixture().apply {
            buffer().putInt(0x1000, 0x1000).putShort(0x1008, 0x0080).putShort(0x100a, 0x0088)
        }
        prepare(absolute).verify(base, IMAGE_SIZE, listOf(header(absolute, base), readback(absolute, base)))
    }

    @Test fun zeroFillAndFileAndPageAlignmentPaddingAreAllCompared() {
        val smaller = fixture().apply { buffer().putInt(SECTIONS + 8, 0x100) }
        val smallerPlan = prepare(smaller)
        assertEquals(0x1000, smallerPlan.regions(PREFERRED, IMAGE_SIZE).last().bytes)
        smallerPlan.verify(PREFERRED, IMAGE_SIZE, listOf(header(smaller), readback(smaller)))
        assertFailsWith<IllegalArgumentException> {
            smallerPlan.verify(PREFERRED, IMAGE_SIZE, listOf(header(smaller), readback(smaller, size = 0x100)))
        }
        val larger = fixture().apply { buffer().putInt(SECTIONS + 8, 0x300) }
        val largerPlan = prepare(larger)
        val tail = readback(larger)
        largerPlan.verify(PREFERRED, IMAGE_SIZE, listOf(header(larger), tail))
        tail.bytes[0x2ff] = 1
        assertFailsWith<IllegalArgumentException> {
            largerPlan.verify(PREFERRED, IMAGE_SIZE, listOf(header(larger), tail))
        }
    }

    @Test fun everyExecutableSectionIsRequiredAndDuplicateOrExtraObservationsFail() {
        val bytes = fixture().apply { buffer().putInt(SECTIONS + 80 + 36, 0x60000040) }
        val plan = prepare(bytes)
        val first = readback(bytes)
        val second = WindowsProfileMappedCode.Readback(PREFERRED + 0x3000,
            bytes.copyOfRange(0x1000, 0x1200).copyOf(0x1000))
        plan.verify(PREFERRED, IMAGE_SIZE, listOf(second, header(bytes), first))
        for (observed in listOf(emptyList(), listOf(first), listOf(first, first),
            listOf(header(bytes), first, second, second))) {
            assertFailsWith<IllegalArgumentException> { plan.verify(PREFERRED, IMAGE_SIZE, observed) }
        }
    }

    @Test fun wrongBaseSectionAddressLengthAndImageExtentFail() {
        val bytes = fixture()
        val plan = prepare(bytes)
        for (base in listOf(0L, -65_536, PREFERRED + 1, Long.MIN_VALUE)) {
            assertFailsWith<IllegalArgumentException> { plan.regions(base, IMAGE_SIZE) }
            assertFailsWith<IllegalArgumentException> {
                plan.verify(base, IMAGE_SIZE, listOf(header(bytes), readback(bytes)))
            }
        }
        // A high aligned base still admits this small image; use a genuinely overflowing extent for refusal.
        val highBase = Long.MAX_VALUE and -65_536L
        plan.verify(highBase, IMAGE_SIZE, listOf(header(bytes, highBase), readback(bytes, highBase)))
        val bigger = bytes.copyOf().apply {
            buffer().putInt(0x98 + 56, 0x21000).putInt(SECTIONS + 80 + 8, 0x1e000)
        }
        assertFailsWith<IllegalArgumentException> { prepare(bigger).regions(highBase, 0x21000) }
        for (size in listOf(0L, IMAGE_SIZE - 1, IMAGE_SIZE + 1, Long.MAX_VALUE)) {
            assertFailsWith<IllegalArgumentException> { plan.regions(PREFERRED, size) }
        }
        for (actual in listOf(readback(bytes, PREFERRED + 65_536), readback(bytes, size = 0x1ff),
            WindowsProfileMappedCode.Readback(PREFERRED + 0x2000, ByteArray(0x200)))) {
            assertFailsWith<IllegalArgumentException> { plan.verify(PREFERRED, IMAGE_SIZE, listOf(header(bytes), actual)) }
        }
    }

    @Test fun planCannotBePreparedFromDifferentBytesOrAnUnboundImageSize() {
        val original = fixture()
        val image = authorize(original)
        val changed = original.copyOf().apply { this[0x401] = (this[0x401].toInt() xor 1).toByte() }
        assertFailsWith<IllegalArgumentException> { WindowsProfileMappedCode.prepare(changed, image) }
        for (other in listOf(image.copy(imageBytes = IMAGE_SIZE + 4096), image.copy(dllBytes = image.dllBytes - 1))) {
            assertFailsWith<IllegalArgumentException> { WindowsProfileMappedCode.prepare(original, other) }
        }
        assertFailsWith<IllegalArgumentException> { WindowsProfileMappedCode.prepare(ByteArray(1), image) }
    }

    @Test fun mutationOfInputBytesAndReturnedRegionInventoryCannotChangeTheOriginalPlan() {
        val bytes = fixture()
        val actual = readback(bytes)
        val originalHeader = header(bytes)
        val plan = prepare(bytes)
        bytes.fill(0)
        plan.verify(PREFERRED, IMAGE_SIZE, listOf(originalHeader, actual))
        assertFailsWith<UnsupportedOperationException> {
            (plan.regions(PREFERRED, IMAGE_SIZE) as MutableList<WindowsProfileMappedCode.Region>).clear()
        }
        actual.bytes.fill(0)
        assertFailsWith<IllegalArgumentException> { plan.verify(PREFERRED, IMAGE_SIZE, listOf(originalHeader, actual)) }
    }

    @Test fun callerInventoryIsBoundedAndEachEntryIsConsumedOnlyOnce() {
        val bytes = fixture()
        val plan = prepare(bytes)
        var reads = 0
        val once = object : AbstractList<WindowsProfileMappedCode.Readback>() {
            override val size: Int get() = 2
            override fun get(index: Int): WindowsProfileMappedCode.Readback {
                check(index == reads++)
                return if (index == 0) header(bytes) else readback(bytes)
            }
        }
        plan.verify(PREFERRED, IMAGE_SIZE, once)
        assertEquals(2, reads)
        val tooMany = object : AbstractList<WindowsProfileMappedCode.Readback>() {
            override val size: Int get() = Int.MAX_VALUE
            override fun get(index: Int): WindowsProfileMappedCode.Readback = error("Must not read oversized inventory")
        }
        assertFailsWith<IllegalArgumentException> { plan.verify(PREFERRED, IMAGE_SIZE, tooMany) }
    }

    @Test fun discardableExecutableSectionsAreRefusedRatherThanClaimedPermanentlyReadable() {
        val bytes = fixture().apply { buffer().putInt(SECTIONS + 36, 0x62000020) }
        // The byte reader remains structural; this additional supported-mapping limitation is plan-specific.
        val image = authorize(bytes)
        assertFailsWith<IllegalArgumentException> { WindowsProfileMappedCode.prepare(bytes, image) }
    }

    private fun fixture(): ByteArray = WindowsProfilePeFixture.create().apply {
        for (index in 0x400 until 0x600) this[index] = (index * 37 + 11).toByte()
    }

    private fun readback(bytes: ByteArray, base: Long = PREFERRED, size: Int = 0x1000) =
        WindowsProfileMappedCode.Readback(base + 0x1000, bytes.copyOfRange(0x400, 0x600).copyOf(size))

    private fun header(bytes: ByteArray, base: Long = PREFERRED) =
        WindowsProfileMappedCode.Readback(base, bytes.copyOfRange(0, 0x400).copyOf(0x1000))

    private fun prepare(bytes: ByteArray) = WindowsProfileMappedCode.prepare(bytes, authorize(bytes))

    private fun authorize(bytes: ByteArray): WindowsProfileByteManifest.ByteAuthorization {
        val source = "a".repeat(40)
        val tree = "b".repeat(40)
        val manifest = WindowsProfileByteManifest.produce(source, tree, true, bytes)
        val hash = MessageDigest.getInstance("SHA-256").digest(manifest).joinToString("") { "%02x".format(it) }
        return WindowsProfileByteManifest.authorize(manifest, bytes,
            WindowsProfileByteManifest.Authority(hash, source, tree))
    }

    private fun ByteArray.buffer(): ByteBuffer = ByteBuffer.wrap(this).order(ByteOrder.LITTLE_ENDIAN)

    companion object {
        private const val PREFERRED = 0x180000000L
        private const val IMAGE_SIZE = 0x4000L
        private const val SECTIONS = 0x98 + 240
    }
}
