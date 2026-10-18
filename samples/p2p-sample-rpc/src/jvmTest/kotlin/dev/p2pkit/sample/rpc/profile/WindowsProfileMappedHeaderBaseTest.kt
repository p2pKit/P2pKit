package dev.p2pkit.sample.rpc.profile

import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertFailsWith

/** Inert ASLR header observations: no native mapping, installed authority or provider qualification. */
class WindowsProfileMappedHeaderBaseTest {
    @Test fun dynamicBaseHeaderMustContainTheExactLoadedBaseAtEitherRelocationSign() {
        val bytes = WindowsProfilePeFixture.create()
        val plan = prepare(bytes)
        for (base in listOf(PREFERRED - 65_536, PREFERRED, PREFERRED + 65_536, 0x7fff00000000L)) {
            plan.verify(base, IMAGE, pages(bytes, base))
        }
    }

    @Test fun originalPreferredBaseIsNotAcceptedAfterRelocation() {
        val bytes = WindowsProfilePeFixture.create()
        val plan = prepare(bytes)
        for (base in listOf(PREFERRED - 65_536, PREFERRED + 65_536)) {
            val observed = pages(bytes, base)
            observed[0].bytes.buffer().putLong(0xb0, PREFERRED)
            assertFailsWith<IllegalArgumentException> { plan.verify(base, IMAGE, observed) }
        }
    }

    @Test fun everyRebasedByteAndBothAdjacentBytesRemainExactNotMasked() {
        val bytes = WindowsProfilePeFixture.create()
        val plan = prepare(bytes)
        val base = PREFERRED + 65_536
        for (offset in 0xaf..0xb8) {
            val observed = pages(bytes, base)
            observed[0].bytes[offset] = (observed[0].bytes[offset].toInt() xor 1).toByte()
            assertFailsWith<IllegalArgumentException> { plan.verify(base, IMAGE, observed) }
        }
    }

    @Test fun imageBaseFieldComesFromTheVerifiedHeaderInsteadOfAFixedCompilerOffset() {
        val bytes = WindowsProfilePeFixture.create().apply {
            copyOfRange(0x80, 0x200).copyInto(this, 0x180)
            buffer().putInt(0x3c, 0x180)
        }
        val plan = prepare(bytes)
        val base = PREFERRED + 65_536
        val observed = pages(bytes, base, 0x1b0)
        plan.verify(base, IMAGE, observed)
        // The old fixed offset now belongs to the opaque DOS-stub bytes; it must stay file-exact.
        observed[0].bytes.buffer().putLong(0xb0, base)
        assertFailsWith<IllegalArgumentException> { plan.verify(base, IMAGE, observed) }
    }

    private fun pages(bytes: ByteArray, base: Long, field: Int = 0xb0) = listOf(
        WindowsProfileMappedCode.Readback(base, bytes.copyOfRange(0, 0x400).copyOf(4096).apply {
            buffer().putLong(field, base)
        }),
        WindowsProfileMappedCode.Readback(base + 4096, bytes.copyOfRange(0x400, 0x600).copyOf(4096)),
    )

    private fun prepare(bytes: ByteArray): WindowsProfileMappedCode {
        val source = "a".repeat(40)
        val tree = "b".repeat(40)
        val manifest = WindowsProfileByteManifest.produce(source, tree, true, bytes)
        val digest = MessageDigest.getInstance("SHA-256").digest(manifest).joinToString("") { "%02x".format(it) }
        return WindowsProfileMappedCode.prepare(bytes, WindowsProfileByteManifest.authorize(manifest, bytes,
            WindowsProfileByteManifest.Authority(digest, source, tree)))
    }

    private fun ByteArray.buffer() = ByteBuffer.wrap(this).order(ByteOrder.LITTLE_ENDIAN)

    companion object {
        private const val PREFERRED = 0x180000000L
        private const val IMAGE = 0x4000L
    }
}
