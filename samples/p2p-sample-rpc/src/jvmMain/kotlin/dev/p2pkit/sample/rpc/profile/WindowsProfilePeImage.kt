package dev.p2pkit.sample.rpc.profile

import java.security.MessageDigest
import java.util.Locale

/** Structural prerequisite only: neither a Windows signature verifier, filesystem admission, nor a DLL loader. */
internal object WindowsProfilePeImage {
    const val ABI = 2
    const val MAXIMUM_BYTES = 32 * 1024 * 1024
    val expectedExports: Set<String> get() = setOf(
        "abi", "capabilities", "openRoot", "child", "identity", "read", "lockExisting", "close",
        "fileIdentity", "exists", "names",
    ).mapTo(linkedSetOf()) { "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_$it" }

    data class Observation(val sha256: String, val imports: Set<String>, val exports: Set<String>,
        val hasCertificateTable: Boolean)

    fun verify(image: ByteArray): Observation {
        require(image.size in 512..MAXIMUM_BYTES) { "Unsupported PE image size" }
        // Bind the observation/hash to one private byte snapshot, not concurrently mutable caller storage.
        return Reader(image.copyOf()).verify()
    }

    private class Reader(private val bytes: ByteArray) {
        private data class Section(val virtual: Long, val size: Long, val raw: Long, val rawSize: Long,
            val mappedSize: Long, val executable: Boolean)
        private val sections = mutableListOf<Section>()
        private val directories = mutableListOf<Pair<Long, Long>>()
        private fun check(value: Boolean) = require(value) { "Unsupported or malformed Windows profile PE image" }
        private fun span(at: Long, count: Long): Int {
            check(at >= 0 && count >= 0 && at <= bytes.size.toLong() && count <= bytes.size.toLong() - at)
            return at.toInt()
        }
        private fun u16(at: Long): Int {
            val i = span(at, 2)
            return (bytes[i].toInt() and 255) or ((bytes[i + 1].toInt() and 255) shl 8)
        }
        private fun u32(at: Long): Long = u16(at).toLong() or (u16(at + 2).toLong() shl 16)
        private fun u64(at: Long): Long = u32(at) or (u32(at + 4) shl 32)
        private fun zero(at: Long, count: Long): Boolean {
            val offset = span(at, count)
            return (offset until offset + count.toInt()).all { bytes[it] == 0.toByte() }
        }
        private fun powerOfTwo(value: Long): Boolean = value > 0 && value and (value - 1) == 0L
        private fun align(value: Long, alignment: Long): Long = (value + alignment - 1) / alignment * alignment
        private fun section(rva: Long, size: Long): Section {
            check(rva in 1..0xffffffffL && size > 0 && size <= 0x100000000L - rva)
            return sections.singleOrNull {
                rva >= it.virtual && rva - it.virtual < minOf(it.size, it.rawSize) &&
                    size <= minOf(it.size, it.rawSize) - (rva - it.virtual)
            }.also { check(it != null) }!!
        }
        private fun mapped(rva: Long, size: Long): Long {
            val s = section(rva, size)
            val offset = s.raw + (rva - s.virtual)
            span(offset, size)
            return offset
        }
        private fun text(rva: Long, maximum: Int): String {
            val output = StringBuilder()
            for (i in 0..maximum) {
                val value = bytes[mapped(rva + i, 1).toInt()].toInt() and 255
                if (value == 0) { check(output.isNotEmpty()); return output.toString() }
                check(value in 33..126 && i < maximum)
                output.append(value.toChar())
            }
            error("Unreachable bounded PE string reader")
        }
        fun verify(): Observation {
            check(u16(0) == 0x5a4d)
            val pe = u32(0x3c)
            check(pe >= 64 && u32(pe) == 0x4550L && u16(pe + 4) == 0x8664)
            val count = u16(pe + 6)
            check(count in 1..32 && u32(pe + 12) == 0L && u32(pe + 16) == 0L)
            check(u16(pe + 20) == 240 && u16(pe + 22) and 0x2003 == 0x2002)
            val optional = pe + 24
            span(optional, 240)
            check(u16(optional) == 0x20b && u64(optional + 24) > 0 && u64(optional + 24) % 65536 == 0L)
            val sectionAlignment = u32(optional + 32)
            val fileAlignment = u32(optional + 36)
            check(powerOfTwo(fileAlignment) && fileAlignment in 512..65536 &&
                powerOfTwo(sectionAlignment) && sectionAlignment in fileAlignment..65536)
            val imageSize = u32(optional + 56)
            val headersSize = u32(optional + 60)
            check(imageSize in 4096..(128L * 1024 * 1024) && imageSize % sectionAlignment == 0L)
            check(headersSize >= optional + 240 + count * 40L && headersSize % fileAlignment == 0L)
            span(0, headersSize)
            check(u16(optional + 68) in setOf(2, 3) && u16(optional + 70) and 0x160 == 0x160)
            check(u32(optional + 104) == 0L && u32(optional + 108) == 16L)
            repeat(16) { i -> directories += u32(optional + 112 + i * 8) to u32(optional + 116 + i * 8) }
            val names = mutableSetOf<String>()
            repeat(count) { i ->
                val at = optional + 240 + i * 40L
                val rawName = bytes.copyOfRange(span(at, 8), (at + 8).toInt())
                val nameEnd = rawName.indexOf(0).let { if (it < 0) 8 else it }
                check(nameEnd > 0 && rawName.drop(nameEnd).all { it == 0.toByte() })
                val name = rawName.take(nameEnd).map { (it.toInt() and 255).toChar() }.joinToString("")
                check(name.matches(Regex("[.A-Za-z0-9_$]+")) && names.add(name))
                val size = u32(at + 8)
                val virtual = u32(at + 12)
                val rawSize = u32(at + 16)
                val raw = u32(at + 20)
                val flags = u32(at + 36)
                val executable = flags and 0x20000000 != 0L
                check(size > 0 && virtual >= align(headersSize, sectionAlignment) &&
                    virtual % sectionAlignment == 0L && rawSize % fileAlignment == 0L)
                check(!executable || flags and 0x40000000 != 0L && flags and 0x80000000 == 0L)
                check(u32(at + 24) == 0L && u32(at + 28) == 0L && u16(at + 32) == 0 && u16(at + 34) == 0)
                if (rawSize == 0L) check(raw == 0L) else {
                    check(raw >= headersSize && raw % fileAlignment == 0L)
                    span(raw, rawSize)
                }
                val mappedSize = align(maxOf(size, rawSize), sectionAlignment)
                check(virtual <= imageSize && mappedSize <= imageSize - virtual)
                sections += Section(virtual, size, raw, rawSize, mappedSize, executable)
            }
            val virtual = sections.sortedBy { it.virtual }
            check(virtual.zipWithNext().all { (a, b) -> a.virtual + a.mappedSize <= b.virtual })
            check(virtual.last().virtual + virtual.last().mappedSize == imageSize)
            val raw = sections.filter { it.rawSize > 0 }.sortedBy { it.raw }
            check(raw.zipWithNext().all { (a, b) -> a.raw + a.rawSize <= b.raw })
            check(raw.isNotEmpty())
            for ((index, directory) in directories.withIndex()) {
                val (rva, size) = directory
                check((rva == 0L) == (size == 0L))
                if (rva != 0L && index != 4) mapped(rva, size)
            }
            // Bound/delay imports and managed CLR images are not part of this native C ABI.
            check(listOf(11, 13, 14, 15).all { directories[it].first == 0L })
            check(directories[5].first != 0L)
            val entryPoint = u32(optional + 16)
            if (entryPoint != 0L) check(section(entryPoint, 1).executable)
            val certificate = certificateTable(raw.last().raw + raw.last().rawSize)
            val imports = imports()
            val exports = exports()
            val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            return Observation(hash, imports, exports, certificate)
        }
        private fun certificateTable(rawEnd: Long): Boolean {
            val (offset, size) = directories[4]
            if (size == 0L) { check(rawEnd == bytes.size.toLong()); return false }
            check(offset % 8 == 0L && offset == align(rawEnd, 8) && offset + size == bytes.size.toLong())
            check(zero(rawEnd, offset - rawEnd))
            span(offset, size)
            var position = offset
            var count = 0
            while (position < offset + size) {
                check(++count <= 8 && offset + size - position >= 8)
                val length = u32(position)
                check(length >= 8 && length <= offset + size - position &&
                    u16(position + 4) == 0x200 && u16(position + 6) == 2)
                val padded = align(length, 8)
                check(padded <= offset + size - position && zero(position + length, padded - length))
                position += padded
            }
            check(position == offset + size)
            return true // Presence only; no Authenticode chain/digest/revocation assertion.
        }
        private fun imports(): Set<String> {
            val (rva, size) = directories[1]
            check(rva != 0L && size in 40..(33L * 20) && size % 20 == 0L)
            val result = linkedSetOf<String>()
            var terminated = false
            var totalFunctions = 0
            val (iat, iatSize) = directories[12]
            check(iat != 0L && iatSize > 0)
            for (i in 0 until (size / 20).toInt()) {
                val at = mapped(rva + i * 20L, 20)
                if (zero(at, 20)) {
                    check(zero(at, size - i * 20L))
                    terminated = true
                    break
                }
                check(i < 32 && u32(at + 4) == 0L && u32(at + 8) == 0L)
                val library = text(u32(at + 12), 64).lowercase(Locale.ROOT)
                check(library in setOf("kernel32.dll", "advapi32.dll", "ntdll.dll", "shell32.dll", "ole32.dll") &&
                    result.add(library))
                val lookup = u32(at)
                val address = u32(at + 16)
                check(lookup != 0L && address >= iat && address - iat < iatSize)
                val functionNames = mutableSetOf<String>()
                var thunkTerminated = false
                for (j in 0..512) {
                    check((j + 1) * 8L <= iatSize - (address - iat))
                    val value = u64(mapped(lookup + j * 8L, 8))
                    check(value == u64(mapped(address + j * 8L, 8)))
                    if (value == 0L) { thunkTerminated = true; break }
                    check(j < 512 && ++totalFunctions <= 4096 && value in 1..0xffffffffL)
                    mapped(value, 2)
                    val name = text(value + 2, 128)
                    check(name.matches(Regex("[A-Za-z_][A-Za-z0-9_]*")) && functionNames.add(name))
                }
                check(thunkTerminated && functionNames.isNotEmpty())
            }
            check(terminated && result.isNotEmpty())
            return result
        }
        private fun exports(): Set<String> {
            val (rva, size) = directories[0]
            check(rva != 0L && size in 40..65536)
            val at = mapped(rva, 40)
            check(u32(at) == 0L && text(u32(at + 12), 64) == "p2pkit-windows-profile.dll" && u32(at + 16) == 1L)
            val count = expectedExports.size
            check(u32(at + 20) == count.toLong() && u32(at + 24) == count.toLong())
            val functions = mapped(u32(at + 28), count * 4L)
            val names = mapped(u32(at + 32), count * 4L)
            val ordinals = mapped(u32(at + 36), count * 2L)
            val output = linkedSetOf<String>()
            val seenOrdinals = mutableSetOf<Int>()
            var previous = ""
            repeat(count) { i ->
                val name = text(u32(names + i * 4L), 192)
                val ordinal = u16(ordinals + i * 2L)
                check(name > previous && output.add(name) && ordinal < count && seenOrdinals.add(ordinal))
                previous = name
                val function = u32(functions + ordinal * 4L)
                check(function !in rva until rva + size && section(function, 1).executable)
            }
            check(output == expectedExports)
            return output
        }
    }
}
