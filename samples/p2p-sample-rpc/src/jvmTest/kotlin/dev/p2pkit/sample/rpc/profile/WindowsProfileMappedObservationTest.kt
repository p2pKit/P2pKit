package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

/** Inert post-refusal formatting, not native reads, mapping acceptance or installed authority. */
class WindowsProfileMappedObservationTest {
    @Test fun matchingSyntheticPagesRevealOnlyClosedCategoriesWithoutEnablingLoading() {
        val fixture = Fixture()
        assertEquals(line("NONE", 0), fixture.observe())
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test fun headerRawPaddingAndContiguousFilePageAreDistinguishedWithoutRelaxingComparison() {
        val raw = Fixture()
        raw.pages[0][100] = (raw.pages[0][100].toInt() xor 1).toByte()
        assertEquals(line("HEADER_RAW", 100), raw.observe())
        val padding = Fixture()
        padding.pages[0][0x400] = 1
        assertEquals(line("HEADER_PADDING", 0x400), padding.observe())
        val contiguous = Fixture()
        contiguous.pages[0] = contiguous.bytes.copyOfRange(0, 4096)
        assertEquals(line("HEADER_PADDING", 0x400, "MATCH"), contiguous.observe())
        // The diagnostic finding cannot turn the maintained comparator's refusal into a pass.
        val manifest = WindowsProfileByteManifest.produce("a".repeat(40), "b".repeat(40), true, contiguous.bytes)
        val hash = java.security.MessageDigest.getInstance("SHA-256").digest(manifest)
            .joinToString("") { "%02x".format(it) }
        val image = WindowsProfileByteManifest.authorize(manifest, contiguous.bytes,
            WindowsProfileByteManifest.Authority(hash, "a".repeat(40), "b".repeat(40)))
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileMappedCode.prepare(contiguous.bytes, image).verify(BASE, 0x4000, listOf(
                WindowsProfileMappedCode.Readback(BASE, contiguous.pages[0]),
                WindowsProfileMappedCode.Readback(BASE + 4096, contiguous.pages[1]),
            ))
        }
    }

    @Test fun executableRawAndPaddingFailuresRemainDistinctAndLaterMismatchIsNotHidden() {
        val raw = Fixture()
        raw.pages[1][12] = (raw.pages[1][12].toInt() xor 1).toByte()
        assertEquals(line("EXECUTABLE_RAW", 12, executable = "DIFFERENT"), raw.observe())
        val padding = Fixture()
        padding.pages[1][4095] = 1
        assertEquals(line("EXECUTABLE_PADDING", 4095, executable = "DIFFERENT"), padding.observe())
        padding.pages[0][7] = (padding.pages[0][7].toInt() xor 1).toByte()
        assertEquals(line("HEADER_RAW", 7, executable = "DIFFERENT"), padding.observe())
    }

    @Test fun exactDir64ComparisonUsesOriginalBytesAndDoesNotExposeRelocatedAddresses() {
        for (delta in listOf(-65_536L, 0L, 65_536L)) {
            val fixture = Fixture(BASE + delta, relocations = true)
            assertEquals(line("NONE", 0), fixture.observe())
            fixture.pages[1][0x82] = (fixture.pages[1][0x82].toInt() xor 1).toByte()
            assertEquals(line("RELOCATION", 0x82, executable = "DIFFERENT"), fixture.observe())
        }
    }

    @Test fun wrongPageInventoryAndLengthsCannotBeReportedAsAnObservation() {
        val fixture = Fixture()
        val requests = fixture.requests
        for (index in requests.indices) {
            val changed = requests.copyOf().apply { this[index]++ }
            assertFailsWith<IllegalArgumentException> { fixture.observe(changed) }
        }
        assertFailsWith<IllegalArgumentException> { fixture.observe(requests.copyOf(requests.size - 1)) }
        fixture.pages[0] = fixture.pages[0].copyOf(4095)
        assertFailsWith<IllegalArgumentException> { fixture.observe() }
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileLoadedNativeFixture.mappedObservation(ByteArray(1), BASE, longArrayOf(), emptyArray())
        }
    }

    private class Fixture(val base: Long = BASE, relocations: Boolean = false) {
        val bytes = WindowsProfilePeFixture.create().apply {
            for (index in 0x400 until 0x600) this[index] = (index * 37 + 11).toByte()
            if (relocations) ByteBuffer.wrap(this).order(ByteOrder.LITTLE_ENDIAN)
                .putInt(0x1000, 0x1000).putShort(0x1008, 0xa081.toShort()).putLong(0x481, Long.MAX_VALUE)
        }
        val requests = longArrayOf(base, 4096, 0, base + 4096, 4096, 1)
        val pages = arrayOf(bytes.copyOfRange(0, 0x400).copyOf(4096),
            bytes.copyOfRange(0x400, 0x600).copyOf(4096)).apply {
            ByteBuffer.wrap(this[0]).order(ByteOrder.LITTLE_ENDIAN).putLong(0x98 + 24, base)
            if (relocations) ByteBuffer.wrap(this[1]).order(ByteOrder.LITTLE_ENDIAN)
                .putLong(0x81, Long.MAX_VALUE + base - BASE)
        }
        fun observe(requested: LongArray = requests) =
            WindowsProfileLoadedNativeFixture.mappedObservation(bytes, base, requested, pages)
    }

    private fun line(first: String, offset: Int, header: String = "DIFFERENT", executable: String = "MATCH") =
        "WINDOWS_LOADED_MAPPED_OBSERVATION first=$first offset=$offset headerFilePage=$header executable=$executable"

    companion object { private const val BASE = 0x180000000L }
}
