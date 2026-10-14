package dev.p2pkit.sample.rpc.profile

import java.security.MessageDigest
import java.util.Collections
import java.util.Locale

/** Structural prerequisite only: neither a Windows signature verifier, filesystem admission, nor a DLL loader. */
internal object WindowsProfilePeImage {
    const val ABI = 13
    const val MAXIMUM_BYTES = 32 * 1024 * 1024
    private const val MAXIMUM_RELOCATION_BLOCKS = 32_768
    private const val MAXIMUM_RELOCATION_SLOTS = 65_536
    val expectedExports: Set<String> get() = setOf(
        "abi", "capabilities", "openRoot", "child", "identity", "read", "lockExisting", "createProfileLock", "close",
        "fileIdentity", "exists", "names", "stageRecord", "discardStage", "requestExpectedFileDeletion",
        "createChildDirectory", "createVaultLock", "prepareRecord", "renameCandidate", "syncDirectory", "replaceCandidate",
        "writeRecord", "deleteRecord",
    ).mapTo(linkedSetOf()) { "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_$it" }

    /** Original image RVAs, not resolved addresses or authority over the eventual Windows import providers. */
    data class NamedImport(val library: String, val function: String, val lookupRva: Long, val addressRva: Long)

    data class Observation(val sha256: String, val imports: Set<String>, val namedImports: List<NamedImport>,
        val exports: Set<String>,
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
        private val immutableMetadata = mutableListOf<LongRange>()
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
        private fun metadata(rva: Long, size: Long): Long {
            val offset = mapped(rva, size)
            immutableMetadata += rva until rva + size
            return offset
        }
        private fun text(rva: Long, maximum: Int): String {
            val output = StringBuilder()
            for (i in 0..maximum) {
                val value = bytes[mapped(rva + i, 1).toInt()].toInt() and 255
                if (value == 0) {
                    check(output.isNotEmpty())
                    immutableMetadata += rva..rva + i
                    return output.toString()
                }
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
            val namedImports = imports()
            val exports = exports()
            relocations(imageSize)
            val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            return Observation(hash, Collections.unmodifiableSet(namedImports.mapTo(linkedSetOf()) { it.library }),
                Collections.unmodifiableList(namedImports), Collections.unmodifiableSet(exports), certificate)
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
        private fun imports(): List<NamedImport> {
            val (rva, size) = directories[1]
            check(rva != 0L && size in 40..(33L * 20) && size % 20 == 0L)
            metadata(rva, size)
            val libraries = linkedSetOf<String>()
            val result = mutableListOf<NamedImport>()
            val tables = mutableListOf<LongRange>()
            var terminated = false
            var totalFunctions = 0
            val (iat, iatSize) = directories[12]
            check(iat != 0L && iat % 8 == 0L && iatSize > 0 && iatSize % 8 == 0L)
            metadata(iat, iatSize)
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
                    libraries.add(library))
                val lookup = u32(at)
                val address = u32(at + 16)
                check(lookup != 0L && lookup % 8 == 0L && address % 8 == 0L &&
                    address >= iat && address - iat < iatSize)
                val functionNames = mutableSetOf<String>()
                var thunkTerminated = false
                for (j in 0..512) {
                    check((j + 1) * 8L <= iatSize - (address - iat))
                    val value = u64(metadata(lookup + j * 8L, 8))
                    check(value == u64(mapped(address + j * 8L, 8)))
                    if (value == 0L) { thunkTerminated = true; break }
                    check(j < 512 && ++totalFunctions <= 4096 && value in 1..0xffffffffL)
                    metadata(value, 2)
                    val name = text(value + 2, 128)
                    check(name.matches(Regex("[A-Za-z_][A-Za-z0-9_]*")) && functionNames.add(name))
                    result += NamedImport(library, name, lookup + j * 8L, address + j * 8L)
                }
                check(thunkTerminated && functionNames.isNotEmpty())
                // Include terminators: another descriptor must not overwrite a supposedly final null slot.
                // The maintained MSVC producer uses distinct ILT/IAT tables. Aliased slots make the eventual
                // loaded import identity ambiguous even when both DLL basenames are on the allowlist.
                val tableBytes = (functionNames.size + 1) * 8L
                for (start in listOf(lookup, address)) {
                    val range = start until start + tableBytes
                    check(tables.none { range.first <= it.last && it.first <= range.last })
                    tables += range
                }
            }
            check(terminated && result.isNotEmpty())
            return result
        }
        private fun exports(): Set<String> {
            val (rva, size) = directories[0]
            check(rva != 0L && size in 40..65536)
            metadata(rva, size)
            val at = mapped(rva, 40)
            check(u32(at) == 0L && text(u32(at + 12), 64) == "p2pkit-windows-profile.dll" && u32(at + 16) == 1L)
            val count = expectedExports.size
            check(u32(at + 20) == count.toLong() && u32(at + 24) == count.toLong())
            val functions = metadata(u32(at + 28), count * 4L)
            val names = metadata(u32(at + 32), count * 4L)
            val ordinals = metadata(u32(at + 36), count * 2L)
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

        private fun relocations(imageSize: Long) {
            val (rva, size) = directories[5]
            check(rva % 4 == 0L && size >= 8 && size % 4 == 0L)
            metadata(rva, size)
            // Protect every referenced byte, including out-of-directory tables, hints and terminators.
            // Merge before lookup so adversarial inputs cannot multiply slot count by metadata count.
            val protectedRanges = mutableListOf<LongRange>()
            for (range in immutableMetadata.sortedBy { it.first }) {
                val last = protectedRanges.lastOrNull()
                if (last != null && range.first <= last.last + 1) {
                    protectedRanges[protectedRanges.lastIndex] = last.first..maxOf(last.last, range.last)
                } else protectedRanges += range
            }
            fun overlapsMetadata(target: Long): Boolean {
                var low = 0
                var high = protectedRanges.size
                while (low < high) {
                    val middle = (low + high) ushr 1
                    if (protectedRanges[middle].first <= target + 7) low = middle + 1 else high = middle
                }
                return low > 0 && protectedRanges[low - 1].last >= target
            }
            val writes = mutableListOf<Long>()
            var cursor = 0L
            var blocks = 0
            var slots = 0
            while (cursor < size) {
                check(size - cursor >= 8 && ++blocks <= MAXIMUM_RELOCATION_BLOCKS)
                val at = mapped(rva + cursor, 8)
                val page = u32(at)
                val blockSize = u32(at + 4)
                check(page % 4096 == 0L && page < imageSize &&
                    blockSize >= 8 && blockSize % 4 == 0L && blockSize <= size - cursor)
                val count = (blockSize - 8) / 2
                check(count <= MAXIMUM_RELOCATION_SLOTS - slots)
                slots += count.toInt()
                repeat(count.toInt()) { index ->
                    val entry = u16(at + 8 + index * 2L)
                    when (entry ushr 12) {
                        0 -> Unit // IMAGE_REL_BASED_ABSOLUTE has no write; its offset is ignored by Windows.
                        10 -> { // IMAGE_REL_BASED_DIR64 is the supported AMD64 pointer fixup.
                            val target = page + (entry and 0xfff)
                            mapped(target, 8) // Excludes headers, unmapped gaps, zero-fill and partial spans.
                            check(!overlapsMetadata(target))
                            writes += target
                        }
                        else -> check(false)
                    }
                }
                cursor += blockSize
            }
            check(cursor == size)
            writes.sort()
            for (index in 1 until writes.size) check(writes[index - 1] + 8 <= writes[index])
        }
    }
}
