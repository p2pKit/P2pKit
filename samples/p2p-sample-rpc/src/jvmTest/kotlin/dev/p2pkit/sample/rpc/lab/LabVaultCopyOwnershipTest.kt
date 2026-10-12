package dev.p2pkit.sample.rpc.lab

import java.io.IOException
import java.lang.reflect.Proxy
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotSame
import kotlin.test.assertSame
import kotlin.test.assertTrue

class LabVaultCopyOwnershipTest {
    private class Copies {
        val values = mutableListOf<ByteArray>()
        fun copy(input: ByteArray): ByteArray = input.copyOf().also { values += it }
    }

    @Test
    fun malformedKeysNeverInvokeTheCopyOrStorageBoundary() {
        for (size in listOf(0, 31, 33, 262_144)) {
            val directory = LabVaultTestDirectory()
            val copies = Copies()
            val key = ByteArray(size) { 7 }
            assertFailsWith<IllegalArgumentException> { LabVault.forCopyValidation(directory, key, copies::copy) }
            assertTrue(copies.values.isEmpty())
            assertTrue(directory.events.isEmpty())
            assertTrue(key.all { it == 7.toByte() })
        }
    }

    @Test
    fun pathConstructorRejectsMalformedKeyBeforeInspectingThePath() {
        var inspections = 0
        val path = Proxy.newProxyInstance(Path::class.java.classLoader, arrayOf(Path::class.java)) { _, _, _ ->
            inspections++
            error("Invalid key reached Path inspection")
        } as Path
        val key = ByteArray(31) { 7 }
        assertFailsWith<IllegalArgumentException> { LabVault(path, key) }
        assertEquals(0, inspections)
        assertTrue(key.all { it == 7.toByte() })
    }

    @Test
    fun bothPathConstructorsPreserveDirectoryAdmissionFailureAndCallerBytes() {
        for (explicit in listOf(false, true)) {
            val failure = IllegalStateException("synthetic Path admission failure")
            var inspections = 0
            val path = Proxy.newProxyInstance(Path::class.java.classLoader, arrayOf(Path::class.java)) { _, _, _ ->
                inspections++
                throw failure
            } as Path
            val key = ByteArray(32) { 7 }
            assertSame(failure, assertFailsWith<IllegalStateException> {
                if (explicit) LabVault(path, key) else LabVault(path)
            })
            assertEquals(1, inspections)
            assertTrue(key.all { it == 7.toByte() })
        }
    }

    @Test
    fun ordinaryConstructorCopiesTheCallerKeyButNeverOwnsOrClearsIt() {
        val directory = LabVaultTestDirectory()
        val key = ByteArray(32) { 7 }
        val vault = LabVault(directory, key)
        try {
            assertTrue(key.all { it == 7.toByte() })
            key.fill(9)
            vault.putIfAbsent("synthetic", byteArrayOf(1, 2, 3)).fill(0)
            val reopened = LabVault(directory, ByteArray(32) { 7 })
            try {
                val read = checkNotNull(reopened.read("synthetic"))
                try { assertContentEquals(byteArrayOf(1, 2, 3), read) } finally { read.fill(0) }
            } finally { reopened.close() }
        } finally { vault.close() }
        assertTrue(key.all { it == 9.toByte() })
    }

    @Test
    fun invalidOperationInputsNeverInvokeTheCopyOrStorageBoundary() {
        val directory = LabVaultTestDirectory()
        val copies = Copies()
        val vault = LabVault.forCopyValidation(directory, ByteArray(32) { 7 }, copies::copy)
        try {
            directory.events.clear()
            for (namespace in listOf("", "n".repeat(4097))) {
                assertFailsWith<IllegalArgumentException> { vault.read(namespace) }
                assertFailsWith<IllegalArgumentException> { vault.putIfAbsent(namespace, byteArrayOf(4)) }
                assertFailsWith<IllegalArgumentException> { vault.replace(namespace, byteArrayOf(4)) }
                assertFailsWith<IllegalArgumentException> { vault.delete(namespace) }
            }
            val oversized = ByteArray(262_101) { 4 }
            assertFailsWith<IllegalArgumentException> { vault.putIfAbsent("synthetic", oversized) }
            assertFailsWith<IllegalArgumentException> { vault.replace("synthetic", oversized) }
            assertEquals(1, copies.values.size, "Only the already-admitted key was copied")
            assertTrue(directory.events.isEmpty())
            assertTrue(oversized.all { it == 4.toByte() })
        } finally { vault.close() }
        assertTrue(copies.values.single().all { it == 0.toByte() })
    }

    @Test
    fun admittedKeyCopyIsClearedIfMutexInitializationFails() {
        val failure = IOException("synthetic mutex identity failure")
        val directory = LabVaultTestDirectory().also { it.mutexFailure = failure }
        val copies = Copies()
        val key = ByteArray(32) { 7 }
        assertSame(failure, assertFailsWith<IOException> { LabVault.forCopyValidation(directory, key, copies::copy) })
        assertEquals(listOf("mutex"), directory.events)
        assertTrue(copies.values.single().all { it == 0.toByte() })
        assertTrue(key.all { it == 7.toByte() })
    }

    @Test
    fun keyCopierRejectsAliasesChangedLengthAndChangedContentBeforeStorage() {
        for (kind in 0..2) {
            val directory = LabVaultTestDirectory()
            val key = ByteArray(32) { 7 }
            val candidate = when (kind) {
                0 -> key
                1 -> ByteArray(33) { 7 }
                else -> ByteArray(32) { 8 }
            }
            assertFailsWith<IllegalStateException> { LabVault.forCopyValidation(directory, key) { candidate } }
            assertTrue(directory.events.isEmpty())
            assertTrue(key.all { it == 7.toByte() })
            if (candidate !== key) assertTrue(candidate.all { it == 0.toByte() })
        }
    }

    @Test
    fun invalidValueCopiesCannotWriteOrClearCallerInputOrTheLiveKey() {
        for (kind in 0..3) {
            for (replace in listOf(false, true)) {
                val directory = LabVaultTestDirectory()
                val key = ByteArray(32) { 7 }
                val input = key.copyOf()
                var keyCopy: ByteArray? = null
                var rejected: ByteArray? = null
                val vault = LabVault.forCopyValidation(directory, key) { value ->
                    if (keyCopy == null) value.copyOf().also { keyCopy = it } else {
                        when (kind) {
                            0 -> value
                            1 -> ByteArray(33) { 7 }
                            2 -> ByteArray(32) { 8 }
                            else -> checkNotNull(keyCopy)
                        }.also { rejected = it }
                    }
                }
                try {
                    assertFailsWith<IllegalStateException> {
                        if (replace) vault.replace("synthetic", input) else vault.putIfAbsent("synthetic", input)
                    }
                    assertFalse("write" in directory.events)
                    assertTrue(input.all { it == 7.toByte() })
                    assertTrue(key.all { it == 7.toByte() })
                    assertTrue(checkNotNull(keyCopy).all { it == 7.toByte() })
                    if (kind in 1..2) assertTrue(checkNotNull(rejected).all { it == 0.toByte() })
                } finally { vault.close() }
                assertTrue(checkNotNull(keyCopy).all { it == 0.toByte() })
            }
        }
    }

    @Test
    fun replacementCopyClearsBeforeLeaseRetirementOnSuccessAndEveryFailure() {
        for (writeFails in listOf(false, true)) {
            for (closeFails in listOf(false, true)) {
                val directory = LabVaultTestDirectory()
                val copies = Copies()
                val vault = LabVault.forCopyValidation(directory, ByteArray(32) { 7 }, copies::copy)
                val input = byteArrayOf(1, 2, 3)
                val writeFailure = IOException("synthetic write failure")
                val closeFailure = IOException("synthetic lease retirement failure")
                if (writeFails) directory.writeFailure = writeFailure
                if (closeFails) directory.closeFailure = closeFailure
                directory.beforeLeaseClose = {
                    assertEquals(2, copies.values.size)
                    assertTrue(copies.values[1].all { it == 0.toByte() })
                }
                try {
                    if (writeFails || closeFails) {
                        val failure = assertFailsWith<IOException> { vault.replace("synthetic", input) }
                        assertSame(if (writeFails) writeFailure else closeFailure, failure)
                        if (writeFails && closeFails) assertSame(closeFailure, failure.suppressed.single())
                    } else vault.replace("synthetic", input)
                    assertEquals(2, copies.values.size)
                    assertTrue(copies.values[1].all { it == 0.toByte() })
                    assertContentEquals(byteArrayOf(1, 2, 3), input)
                    assertTrue(copies.values[0].all { it == 7.toByte() })
                } finally { vault.close() }
                assertTrue(copies.values[0].all { it == 0.toByte() })
            }
        }
    }

    @Test
    fun unreturnedNewWinnerClearsOnWriteFailureAndLeaseCloseFailure() {
        for ((writeFails, closeFails) in listOf(true to false, false to true, true to true)) {
            val directory = LabVaultTestDirectory()
            val copies = Copies()
            val vault = LabVault.forCopyValidation(directory, ByteArray(32) { 7 }, copies::copy)
            val input = byteArrayOf(1, 2, 3)
            val writeFailure = IOException("synthetic write failure")
            val closeFailure = IOException("synthetic lease retirement failure")
            if (writeFails) directory.writeFailure = writeFailure
            if (closeFails) directory.closeFailure = closeFailure
            directory.beforeLeaseClose = {
                assertEquals(2, copies.values.size)
                if (writeFails) assertTrue(copies.values[1].all { it == 0.toByte() })
                else assertContentEquals(input, copies.values[1]) // Result still owned until actual close returns.
            }
            try {
                val failure = assertFailsWith<IOException> { vault.putIfAbsent("synthetic", input) }
                assertSame(if (writeFails) writeFailure else closeFailure, failure)
                if (writeFails && closeFails) assertSame(closeFailure, failure.suppressed.single())
                assertEquals(2, copies.values.size)
                assertTrue(copies.values[1].all { it == 0.toByte() })
                assertContentEquals(byteArrayOf(1, 2, 3), input)
            } finally { vault.close() }
        }
    }

    @Test
    fun successfulNewWinnerTransfersItsSinglePrivateCopyOnlyAfterLeaseClose() {
        val directory = LabVaultTestDirectory()
        val copies = Copies()
        val vault = LabVault.forCopyValidation(directory, ByteArray(32) { 7 }, copies::copy)
        val input = byteArrayOf(1, 2, 3)
        var retired = false
        directory.beforeLeaseClose = {
            assertContentEquals(input, copies.values[1])
            retired = true
        }
        val winner = try {
            vault.putIfAbsent("synthetic", input).also {
                assertTrue(retired)
                assertEquals(2, copies.values.size)
                assertSame(copies.values[1], it)
                assertNotSame(input, it)
            }
        } finally { vault.close() }
        assertTrue(copies.values[0].all { it == 0.toByte() })
        assertContentEquals(input, winner) // Closed vault must not clear a caller-owned winner.
        input.fill(0)
        assertContentEquals(byteArrayOf(1, 2, 3), winner)
        winner.fill(0)
    }

    @Test
    fun leaseCloseFailureNeverPublishesExistingWinnerOrReadResult() {
        for (read in listOf(false, true)) {
            val directory = LabVaultTestDirectory()
            val vault = LabVault(directory, ByteArray(32) { 7 })
            try {
                vault.putIfAbsent("synthetic", byteArrayOf(1, 2, 3)).fill(0)
                val before = directory.records.mapValues { it.value.bytes.copyOf() }
                val failure = IOException("synthetic lease retirement failure")
                directory.closeFailure = failure
                assertSame(failure, assertFailsWith<IOException> {
                    if (read) vault.read("synthetic") else vault.putIfAbsent("synthetic", byteArrayOf(9))
                })
                before.forEach { (name, bytes) -> assertContentEquals(bytes, directory.records.getValue(name).bytes) }
            } finally { vault.close() }
        }
    }
}
