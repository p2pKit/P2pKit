package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.sample.rpc.profile.ProtectedProfileDirectory
import dev.p2pkit.sample.rpc.profile.ProtectedProfileLease
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Black-box tests also compile against the earlier vault; no validation-only copy hook is needed. */
class LabVaultInputValidationTest {
    @Test
    fun invalidNamespacesAreRejectedBeforeStorageForEveryOperation() {
        for (namespace in listOf("", "n".repeat(4097))) {
            for (operation in 0..3) {
                val directory = LabVaultTestDirectory()
                val vault = LabVault(directory, ByteArray(32) { 7 })
                val input = byteArrayOf(2, 3)
                try {
                    directory.events.clear()
                    assertFailsWith<IllegalArgumentException> {
                        when (operation) {
                            0 -> vault.read(namespace)
                            1 -> vault.putIfAbsent(namespace, input)
                            2 -> vault.replace(namespace, input)
                            else -> vault.delete(namespace)
                        }
                    }
                    assertTrue(directory.events.isEmpty(), "Invalid namespace reached storage")
                    assertTrue(directory.records.isEmpty())
                    assertContentEquals(byteArrayOf(2, 3), input)
                } finally { vault.close() }
            }
        }
    }

    @Test
    fun oversizedValuesAreRejectedBeforeStorageForAbsentAndExistingNamespaces() {
        for (existing in listOf(false, true)) {
            for (replace in listOf(false, true)) {
                val directory = LabVaultTestDirectory()
                val vault = LabVault(directory, ByteArray(32) { 7 })
                val input = ByteArray(262_101) { 4 }
                try {
                    if (existing) vault.putIfAbsent("synthetic", byteArrayOf(9))
                    val before = directory.records.mapValues { it.value.bytes.copyOf() }
                    directory.events.clear()
                    assertFailsWith<IllegalArgumentException> {
                        if (replace) vault.replace("synthetic", input) else vault.putIfAbsent("synthetic", input)
                    }
                    assertTrue(directory.events.isEmpty(), "Oversized value reached storage")
                    assertEquals(before.keys, directory.records.keys)
                    before.forEach { (name, bytes) ->
                        assertContentEquals(bytes, directory.records.getValue(name).bytes)
                    }
                    assertTrue(input.all { it == 4.toByte() })
                } finally { vault.close() }
            }
        }
    }

    @Test
    fun exactNamespaceAndValueBoundsRoundTripWithoutChangingCallerBytes() {
        val directory = LabVaultTestDirectory()
        val vault = LabVault(directory, ByteArray(32) { 7 })
        val namespace = "n".repeat(4096)
        val input = ByteArray(262_100) { (it % 251).toByte() }
        val original = input.copyOf()
        try {
            assertNull(vault.read(namespace))
            val winner = vault.putIfAbsent(namespace, input)
            assertContentEquals(original, winner)
            winner.fill(0)
            assertContentEquals(original, vault.read(namespace))
            vault.replace(namespace, byteArrayOf())
            assertContentEquals(byteArrayOf(), vault.read(namespace))
            assertContentEquals(original, input)
            assertTrue(vault.delete(namespace))
            assertNull(vault.read(namespace))
        } finally { vault.close() }
    }

    @Test
    fun malformedKeysAreRejectedBeforeAcquiringDirectoryIdentity() {
        for (size in listOf(0, 31, 33, 262_144)) {
            val directory = LabVaultTestDirectory()
            val key = ByteArray(size) { 7 }
            assertFailsWith<IllegalArgumentException> { LabVault(directory, key) }
            assertTrue(directory.events.isEmpty())
            assertTrue(key.all { it == 7.toByte() })
        }
    }
}

/** Inert storage observations only; this fixture cannot establish filesystem or native behavior. */
internal class LabVaultTestDirectory : ProtectedProfileDirectory {
    data class Record(val bytes: ByteArray, val identity: Long)
    val records = linkedMapOf<String, Record>()
    val events = mutableListOf<String>()
    var mutexFailure: Throwable? = null
    var writeFailure: Throwable? = null
    var closeFailure: Throwable? = null
    var beforeLeaseClose: () -> Unit = {}
    private val identity = Any()
    private var next = 1L

    override val mutexIdentity: Any get() {
        events += "mutex"
        mutexFailure?.let { throw it }
        return identity
    }
    override fun verifyIdentity(): Any { events += "verify"; return identity }
    override fun fileIdentity(name: String): Any { events += "fileIdentity"; return records.getValue(name).identity }
    override fun exists(name: String): Boolean { events += "exists"; return name in records }
    override fun names(): Set<String> { events += "names"; return records.keys.toSet() }
    override fun child(name: String, create: Boolean): ProtectedProfileDirectory = error("No child fixture")
    override fun read(name: String, maximum: Int): ByteArray {
        events += "read"
        val bytes = records.getValue(name).bytes
        require(bytes.size <= maximum)
        return bytes.copyOf()
    }
    override fun write(name: String, bytes: ByteArray, replace: Boolean) {
        events += "write"
        writeFailure?.let { throw it }
        check(replace || name !in records)
        records[name] = Record(bytes.copyOf(), next++)
    }
    override fun lock(name: String, nonBlocking: Boolean): ProtectedProfileLease {
        events += "lock"
        records.getOrPut(name) { Record(byteArrayOf(), next++) }
        return object : ProtectedProfileLease {
            override fun close() {
                events += "close"
                beforeLeaseClose()
                closeFailure?.let { throw it }
            }
        }
    }
    override fun delete(name: String, expectedIdentity: Any?): Boolean {
        events += "delete"
        val record = records[name] ?: return false
        check(expectedIdentity == null || expectedIdentity == record.identity)
        return records.remove(name) != null
    }
    override fun sync() { events += "sync" }
    override fun deleteIfEmpty() { events += "deleteIfEmpty"; check(records.isEmpty()) }
}
