package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/** Pinned byte comparisons only, not observed Windows mappings, OS authority or provider qualification. */
class WindowsProfileMappedEnvelopeTest {
    @Test fun includesOriginalHeadersAndCompleteExecutablePages() {
        val bytes = WindowsProfilePeFixture.create()
        val plan = prepare(bytes)
        assertEquals(listOf(BASE to 4096, BASE + 4096 to 4096),
            plan.regions(BASE, IMAGE).map { it.address to it.bytes })
        plan.verify(BASE, IMAGE, observed(plan, bytes))
    }

    @Test fun changedHeaderOrHeaderPageTailIsNeverIgnored() {
        val bytes = WindowsProfilePeFixture.create()
        val plan = prepare(bytes)
        for (offset in listOf(0, 0x3c, 0x80, 0x98 + 24, 0x188, 0x3ff, 0x400, 0xfff)) {
            val actual = observed(plan, bytes)
            actual.singleOrNull { it.address == BASE }?.bytes?.let {
                it[offset] = (it[offset].toInt() xor 1).toByte()
            }
            assertFailsWith<IllegalArgumentException> { plan.verify(BASE, IMAGE, actual) }
        }
    }

    @Test fun changedExecutablePageTailIsNeverIgnored() {
        val bytes = WindowsProfilePeFixture.create()
        val plan = prepare(bytes)
        for (offset in listOf(0x200, 0x3ff, 0xfff)) {
            val actual = observed(plan, bytes)
            val code = actual.single { it.address == BASE + 4096 }.bytes
            if (offset < code.size) code[offset] = 1
            assertFailsWith<IllegalArgumentException> { plan.verify(BASE, IMAGE, actual) }
        }
    }

    @Test fun originalRawAlignmentTailIsRetainedRatherThanInventedAsZero() {
        val bytes = WindowsProfilePeFixture.create().apply {
            buffer().putInt(SECTIONS + 8, 0x100)
            this[0x500] = 11
            this[0x5ff] = 22
        }
        val plan = prepare(bytes)
        val actual = observed(plan, bytes)
        plan.verify(BASE, IMAGE, actual)
        actual.single { it.address == BASE + 4096 }.bytes.let {
            if (it.size > 0x1ff) it[0x1ff] = 0
        }
        assertFailsWith<IllegalArgumentException> { plan.verify(BASE, IMAGE, actual) }
    }

    @Test fun subpageAndLargerSectionAlignmentHaveNoUnprovenMappingPlan() {
        for (alignment in listOf(512, 1024, 2048, 8192)) {
            val bytes = WindowsProfilePeFixture.create().apply {
                buffer().putInt(0x98 + 32, alignment)
                if (alignment < 4096) buffer().putInt(0x98 + 56, 0x3000 + alignment)
            }
            // Larger alignment makes this particular fixture structurally invalid as well.
            if (alignment < 4096) WindowsProfilePeImage.verify(bytes)
            assertFailsWith<IllegalArgumentException> { prepare(bytes) }
        }
    }

    @Test fun missingDuplicateAndShiftedHeaderObservationsAreRefused() {
        val bytes = WindowsProfilePeFixture.create()
        val plan = prepare(bytes)
        val actual = observed(plan, bytes)
        val header = actual.singleOrNull { it.address == BASE }
        assertFailsWith<IllegalArgumentException> {
            plan.verify(BASE, IMAGE, actual.filterNot { it.address == BASE })
        }
        if (header != null) {
            assertFailsWith<IllegalArgumentException> { plan.verify(BASE, IMAGE, listOf(header, header)) }
            assertFailsWith<IllegalArgumentException> {
                plan.verify(BASE, IMAGE, actual.map {
                    if (it === header) it.copy(address = BASE + 1) else it
                })
            }
        }
    }

    @Test fun headersRemainPinnedAtPreferredAndRelocatedModuleBases() {
        val bytes = WindowsProfilePeFixture.create()
        val plan = prepare(bytes)
        for (base in listOf(BASE - 65536, BASE, BASE + 65536)) {
            val actual = observed(plan, bytes, base)
            plan.verify(base, IMAGE, actual)
            actual.singleOrNull { it.address == base }?.bytes?.buffer()?.putLong(0x98 + 24, base + 1)
            assertFailsWith<IllegalArgumentException> { plan.verify(base, IMAGE, actual) }
        }
    }

    private fun observed(plan: WindowsProfileMappedCode, bytes: ByteArray, base: Long = BASE) =
        plan.regions(base, IMAGE).map { region ->
            val contents = ByteArray(region.bytes)
            when (region.address - base) {
                0L -> {
                    bytes.copyInto(contents, 0, 0, minOf(contents.size, 0x400))
                    contents.buffer().putLong(0x98 + 24, base)
                }
                4096L -> bytes.copyInto(contents, 0, 0x400, 0x400 + minOf(contents.size, 0x200))
                else -> error("Unexpected inert fixture region")
            }
            WindowsProfileMappedCode.Readback(region.address, contents)
        }

    private fun prepare(bytes: ByteArray): WindowsProfileMappedCode {
        val source = "a".repeat(40)
        val tree = "b".repeat(40)
        val manifest = WindowsProfileByteManifest.produce(source, tree, true, bytes)
        val digest = MessageDigest.getInstance("SHA-256").digest(manifest).joinToString("") { "%02x".format(it) }
        val image = WindowsProfileByteManifest.authorize(manifest, bytes,
            WindowsProfileByteManifest.Authority(digest, source, tree))
        return WindowsProfileMappedCode.prepare(bytes, image)
    }

    private fun ByteArray.buffer() = ByteBuffer.wrap(this).order(ByteOrder.LITTLE_ENDIAN)

    companion object {
        private const val BASE = 0x180000000L
        private const val IMAGE = 0x4000L
        private const val SECTIONS = 0x188
    }
}
