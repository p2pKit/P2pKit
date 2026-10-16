package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/** Inert file/readback bytes: no Windows query, mapping lifetime or installed-provider qualification. */
class WindowsProfileMappedPagesTest {
    @Test fun completeCodeAndHeaderRequestsFitSingleWindowsPages() {
        val bytes = fixture()
        val plan = prepare(bytes)
        assertEquals(listOf(BASE, BASE + 0x1000, BASE + 0x4000, BASE + 0x5000),
            plan.regions(BASE, IMAGE).map { it.address })
        assertEquals(listOf(4096, 4096, 4096, 4096), plan.regions(BASE, IMAGE).map { it.bytes })
        assertEquals(listOf(false, true, true, true), plan.regions(BASE, IMAGE).map { it.executable })
        // Observation order is irrelevant; actual addresses and all bytes remain bound to the original plan.
        plan.verify(BASE, IMAGE, observed(bytes, plan, BASE).reversed())
    }

    @Test fun originalDir64CrossingTwoPagesIsVerifiedOnceWithEitherDeltaSign() {
        val bytes = fixture()
        val plan = prepare(bytes)
        for (base in listOf(BASE - 65536, BASE, BASE + 65536)) {
            val actual = observed(bytes, plan, base)
            plan.verify(base, IMAGE, actual)
            for (index in 0..7) {
                val rva = 0x4ffc + index
                val page = actual.single { it.address == base + (rva and -4096) }
                val offset = rva and 4095
                page.bytes[offset] = (page.bytes[offset].toInt() xor 1).toByte()
                assertFailsWith<IllegalArgumentException> { plan.verify(base, IMAGE, actual) }
                page.bytes[offset] = (page.bytes[offset].toInt() xor 1).toByte()
            }
        }
    }

    @Test fun everyOriginalPageIsRequiredWithExactAddressSizeAndContent() {
        val bytes = fixture()
        val plan = prepare(bytes)
        val actual = observed(bytes, plan, BASE)
        val bad = listOf(
            actual.dropLast(1),
            actual + actual.last(),
            actual.dropLast(1) + actual.first(),
            actual.dropLast(1) + actual.last().copy(address = BASE + 0x5001),
            actual.dropLast(1) + actual.last().copy(bytes = ByteArray(4095)),
            actual.dropLast(1) + actual.last().copy(bytes = ByteArray(4097)),
            actual.mapIndexed { i, page -> if (i == 2) page.copy(bytes = actual[3].bytes) else page },
        )
        for (wrong in bad) assertFailsWith<IllegalArgumentException> { plan.verify(BASE, IMAGE, wrong) }
        for (offset in listOf(0x100, 0x1ff, 0x200, 0xfff)) {
            val last = actual.last().bytes
            last[offset] = (last[offset].toInt() xor 1).toByte()
            assertFailsWith<IllegalArgumentException> { plan.verify(BASE, IMAGE, actual) }
            last[offset] = (last[offset].toInt() xor 1).toByte()
        }
    }

    @Test fun pageInventoryIsBoundedReadOnceAndPrivatelyCopiedBeforeLaterEntries() {
        val bytes = fixture()
        val plan = prepare(bytes)
        val actual = observed(bytes, plan, BASE)
        var reads = 0
        val once = object : AbstractList<WindowsProfileMappedCode.Readback>() {
            override val size: Int get() = 4
            override fun get(index: Int): WindowsProfileMappedCode.Readback {
                check(index == reads++)
                if (index == 3) actual[2].bytes.fill(0) // Cannot retroactively modify its consumed snapshot.
                return actual[index]
            }
        }
        plan.verify(BASE, IMAGE, once)
        assertEquals(4, reads)
        val oversized = object : AbstractList<WindowsProfileMappedCode.Readback>() {
            override val size: Int get() = Int.MAX_VALUE
            override fun get(index: Int): WindowsProfileMappedCode.Readback = error("Must reject count before reading")
        }
        assertFailsWith<IllegalArgumentException> { plan.verify(BASE, IMAGE, oversized) }
    }

    private fun fixture(): ByteArray = WindowsProfilePeFixture.create().copyOf(0x2400).apply {
        buffer().putShort(0x86, 4).putInt(0x98 + 56, IMAGE.toInt())
        val section = 0x188 + 3 * 40
        ".more".toByteArray(Charsets.US_ASCII).copyInto(this, section)
        buffer().putInt(section + 8, 0x1100).putInt(section + 12, 0x4000)
            .putInt(section + 16, 0x1200).putInt(section + 20, 0x1200).putInt(section + 36, 0x60000020)
        for (offset in 0x1200 until 0x2400) this[offset] = (offset * 37 + 11).toByte()
        buffer().putLong(0x21fc, ORIGINAL)
        buffer().putInt(0x1000, 0x4000).putShort(0x1008, 0xaffc.toShort())
    }

    private fun observed(bytes: ByteArray, plan: WindowsProfileMappedCode, base: Long):
        List<WindowsProfileMappedCode.Readback> {
        val added = bytes.copyOfRange(0x1200, 0x2400).copyOf(0x2000)
        added.buffer().putLong(0xffc, ORIGINAL + base - BASE)
        return plan.regions(base, IMAGE).map { range ->
            val payload = when (range.address - base) {
                0L -> bytes.copyOfRange(0, 0x400).copyOf(range.bytes)
                0x1000L -> bytes.copyOfRange(0x400, 0x600).copyOf(range.bytes)
                0x4000L -> added.copyOfRange(0, range.bytes)
                0x5000L -> added.copyOfRange(0x1000, 0x1000 + range.bytes)
                else -> error("Unexpected inert fixture page")
            }
            WindowsProfileMappedCode.Readback(range.address, payload)
        }
    }

    private fun prepare(bytes: ByteArray): WindowsProfileMappedCode {
        val source = "a".repeat(40)
        val tree = "b".repeat(40)
        val manifest = WindowsProfileByteManifest.produce(source, tree, true, bytes)
        val hash = MessageDigest.getInstance("SHA-256").digest(manifest).joinToString("") { "%02x".format(it) }
        return WindowsProfileMappedCode.prepare(bytes, WindowsProfileByteManifest.authorize(manifest, bytes,
            WindowsProfileByteManifest.Authority(hash, source, tree)))
    }

    private fun ByteArray.buffer() = ByteBuffer.wrap(this).order(ByteOrder.LITTLE_ENDIAN)

    companion object {
        private const val BASE = 0x180000000L
        private const val IMAGE = 0x6000L
        private const val ORIGINAL = Long.MAX_VALUE - 16384
    }
}
