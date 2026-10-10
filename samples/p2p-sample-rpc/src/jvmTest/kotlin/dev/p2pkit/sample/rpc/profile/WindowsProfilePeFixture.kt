package dev.p2pkit.sample.rpc.profile

/** Synthetic bytes only; never a native artifact or executable qualification result. */
internal object WindowsProfilePeFixture {
    private fun ByteArray.put16(at: Int, value: Int) {
        this[at] = value.toByte(); this[at + 1] = (value ushr 8).toByte()
    }
    private fun ByteArray.put32(at: Int, value: Long) {
        for (i in 0..3) this[at + i] = (value ushr (i * 8)).toByte()
    }
    private fun ByteArray.put64(at: Int, value: Long) {
        for (i in 0..7) this[at + i] = (value ushr (i * 8)).toByte()
    }
    private fun ByteArray.ascii(at: Int, value: String) {
        value.toByteArray(Charsets.US_ASCII).copyInto(this, at); this[at + value.length] = 0
    }
    private fun ByteArray.directory(index: Int, rva: Long, size: Long) {
        put32(OPTIONAL + 112 + index * 8, rva); put32(OPTIONAL + 116 + index * 8, size)
    }
    fun create(): ByteArray = ByteArray(0x1200).apply {
        put16(0, 0x5a4d); put32(0x3c, 0x80); put32(0x80, 0x4550)
        put16(0x84, 0x8664); put16(0x86, 3); put16(0x94, 240); put16(0x96, 0x2022)
        put16(OPTIONAL, 0x20b); put32(OPTIONAL + 16, 0x1000); put64(OPTIONAL + 24, 0x180000000)
        put32(OPTIONAL + 32, 0x1000); put32(OPTIONAL + 36, 0x200)
        put32(OPTIONAL + 56, 0x4000); put32(OPTIONAL + 60, 0x400)
        put16(OPTIONAL + 68, 3); put16(OPTIONAL + 70, 0x160); put32(OPTIONAL + 108, 16)
        directory(0, 0x2000, 0x600); directory(1, 0x2600, 40); directory(5, 0x3000, 8)
        directory(12, 0x2680, 16)
        fun section(index: Int, name: String, va: Long, offset: Long, length: Long, flags: Long) {
            val at = SECTIONS + index * 40
            ascii(at, name); put32(at + 8, length); put32(at + 12, va)
            put32(at + 16, length); put32(at + 20, offset); put32(at + 36, flags)
        }
        section(0, ".text", 0x1000, 0x400, 0x200, 0x60000020)
        section(1, ".rdata", 0x2000, 0x600, 0xa00, 0x40000040)
        section(2, ".reloc", 0x3000, 0x1000, 0x200, 0x42000040)
        put32(0x60c, 0x2030); put32(0x610, 1); put32(0x614, 15); put32(0x618, 15)
        put32(0x61c, 0x2050); put32(0x620, 0x2090); put32(0x624, 0x20d0)
        ascii(0x630, "p2pkit-windows-profile.dll")
        var string = 0x700
        WindowsProfilePeImage.expectedExports.sorted().forEachIndexed { index, value ->
            put32(0x650 + index * 4, 0x1000L + index)
            put32(0x690 + index * 4, 0x2000L + string - 0x600)
            put16(0x6d0 + index * 2, index)
            ascii(string, value); string += value.length + 1
        }
        check(string < 0xc00)
        put32(0xc00, 0x2660); put32(0xc0c, 0x2640); put32(0xc10, 0x2680)
        ascii(0xc40, "KERNEL32.dll"); put64(0xc60, 0x26a0); put64(0xc80, 0x26a0)
        ascii(0xca2, "CloseHandle")
    }

    private const val OPTIONAL = 0x98
    private const val SECTIONS = OPTIONAL + 240
}
