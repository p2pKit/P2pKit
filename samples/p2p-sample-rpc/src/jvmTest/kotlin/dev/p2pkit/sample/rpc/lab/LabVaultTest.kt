package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.sample.rpc.RpcCapacityContract
import kotlinx.coroutines.test.runTest
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.PosixFilePermissions
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class LabVaultTest {
    private fun <T> fixture(block: (Path) -> T): T {
        val root = Files.createTempDirectory("rpc-lab-vault-", PosixFilePermissions.asFileAttribute(
            PosixFilePermissions.fromString("rwx------"),
        )).toRealPath()
        try { return block(root) } finally {
            Files.walk(root).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach(Files::delete) }
        }
    }

    @Test
    fun opaqueValuesAreEncryptedCopiedAndRecoverableOnlyWithTheSameKey() = fixture { root ->
        val key = LabVault.randomKey()
        val value = "opaque synthetic private material".toByteArray()
        val original = value.copyOf()
        val store = LabVault(root, key)
        val winner = store.putIfAbsent("test", value)
        value.fill(0)
        winner.fill(1)
        assertContentEquals(original, store.read("test"))
        val ciphertext = Files.list(root).use { it.filter { p -> p.toString().endsWith(".aesgcm") }.findFirst().orElseThrow() }
        assertFalse(LabFiles.read(ciphertext).toString(Charsets.UTF_8).contains(String(original)))
        val same = LabVault(root, key)
        assertContentEquals(original, same.read("test"))
        val wrong = LabVault(root)
        assertFails { wrong.read("test") }
        wrong.close()
        same.close()
        store.close()
        assertFails { store.read("test") }
        key.fill(0)
    }

    @Test
    fun atomicAbsentWinnerIsStableAcrossThreadsAndSeparateStoreInstances() = fixture { root ->
        val key = LabVault.randomKey()
        val stores = List(4) { LabVault(root, key) }
        val executor = Executors.newFixedThreadPool(4)
        try {
            val values = (0 until 32).map { index -> executor.submit<ByteArray> {
                stores[index % stores.size].putIfAbsent("race", byteArrayOf(index.toByte()))
            } }.map { it.get(5, TimeUnit.SECONDS) }
            values.forEach { assertContentEquals(values.first(), it) }
            stores.forEach { assertContentEquals(values.first(), it.read("race")) }
        } finally {
            executor.shutdown()
            assertTrue(executor.awaitTermination(5, TimeUnit.SECONDS))
            stores.forEach(LabVault::close)
            key.fill(0)
        }
    }

    @Test
    fun corruptionAndNamespaceSubstitutionFailClosed() = fixture { root ->
        val store = LabVault(root)
        store.putIfAbsent("first", byteArrayOf(42))
        val first = root.resolve(LabFiles.sha256("first".toByteArray()) + ".aesgcm")
        val second = root.resolve(LabFiles.sha256("second".toByteArray()) + ".aesgcm")
        LabFiles.write(second, LabFiles.read(first))
        assertFails { store.read("second") }
        val bytes = LabFiles.read(first)
        bytes[bytes.lastIndex] = (bytes.last().toInt() xor 1).toByte()
        LabFiles.write(first, bytes, replace = true)
        assertFails { store.read("first") }
        store.close()
    }

    @Test
    fun deletionIsIdempotentAndMissingIsNotAnEmptyValue() = fixture { root ->
        val store = LabVault(root)
        assertNull(store.read("empty"))
        assertContentEquals(byteArrayOf(), store.putIfAbsent("empty", byteArrayOf()))
        assertNotNull(store.read("empty"))
        assertTrue(store.delete("empty"))
        assertFalse(store.delete("empty"))
        assertNull(store.read("empty"))
        store.close()
    }

    @Test
    fun unprotectedPathsAndSymlinksAreRejectedWithoutReadingTheirTargets() = fixture { root ->
        val weak = Files.createDirectory(root.resolve("weak"))
        Files.setPosixFilePermissions(weak, PosixFilePermissions.fromString("rwxr-xr-x"))
        assertFails { LabVault(weak) }
        val link = root.resolve("link")
        Files.createSymbolicLink(link, weak)
        assertFails { LabVault(link) }
        val store = LabVault(root)
        val entry = root.resolve(LabFiles.sha256("test".toByteArray()) + ".aesgcm")
        Files.createSymbolicLink(entry, root.resolve("absent-target"))
        assertFails { store.read("test") }
        store.close()
    }

    @Test
    fun trustIsPersistedAndSeparatedByPurposeAndSyntheticAppId() = runTest {
        fixture { root ->
            val vault = LabVault(root)
            val store = LabTrustStore(vault)
            val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
            // The fixture has no suspending implementation; runTest owns the suspend scope.
            kotlinx.coroutines.runBlocking {
                store.replace(RpcCapacityContract.appId, RpcTrustPurpose.HostClients, setOf(pin))
                assertEquals(setOf(pin), LabTrustStore(vault).load(RpcCapacityContract.appId, RpcTrustPurpose.HostClients))
                assertEquals(emptySet(), store.load(RpcCapacityContract.appId, RpcTrustPurpose.SelectedHosts))
                assertFails { store.load(AppId("not.the.synthetic.app"), RpcTrustPurpose.HostClients) }
                store.replace(RpcCapacityContract.appId, RpcTrustPurpose.HostClients, emptySet())
                assertEquals(emptySet(), store.load(RpcCapacityContract.appId, RpcTrustPurpose.HostClients))
            }
            vault.close()
        }
    }

    @Test
    fun controlFilesRejectDuplicatesAndNonAsciiInsteadOfSilentlyNormalizing() {
        assertEquals(mapOf("schema" to "1"), LabFiles.parse("schema=1\n".toByteArray()))
        for (bad in listOf("schema=1\nschema=2\n", "empty=\n", "key=value\r\n", "key=private\u0000value\n")) {
            assertFails { LabFiles.parse(bad.toByteArray()) }
        }
    }
}
