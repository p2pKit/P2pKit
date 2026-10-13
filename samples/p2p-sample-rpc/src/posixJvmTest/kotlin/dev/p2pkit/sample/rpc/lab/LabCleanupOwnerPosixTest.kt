package dev.p2pkit.sample.rpc.lab

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.PosixFilePermissions
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertSame

class LabCleanupOwnerPosixTest {
    @Test
    fun failedVaultRetainsItsFailureAndForeignFileButDoesNotStrandIndependentVaults() = fixture { root ->
        val directories = listOf("first", "failed", "last").map { LabFiles.newDirectory(root, it) }
        val vaults = directories.map { LabVault(it) }
        vaults.forEach { it.putIfAbsent("key", byteArrayOf(1)) }
        val replaced = directories[1].resolve(LabFiles.sha256("key".toByteArray()) + ".aesgcm")
        LabFiles.write(replaced, byteArrayOf(2), replace = true)
        val receipt = root.resolve("clients-closed.txt")
        val owner = LabCleanupOwner(vaults, LabVault::destroy) {
            LabFiles.write(receipt, "closed=true\nfixturesRemoved=true\n".toByteArray())
        }
        val failure = assertFails { owner.close() }
        assertFalse(Files.exists(directories[0]))
        assertFalse(Files.exists(directories[2]))
        assertContentEquals(byteArrayOf(2), LabFiles.read(replaced))
        assertFalse(Files.exists(receipt))
        assertSame(failure, assertFails { owner.close() })
        assertContentEquals(byteArrayOf(2), LabFiles.read(replaced))
        assertFalse(Files.exists(receipt))
    }

    private fun fixture(block: (Path) -> Unit) {
        val root = Files.createTempDirectory("rpc-lab-cleanup-", PosixFilePermissions.asFileAttribute(
            PosixFilePermissions.fromString("rwx------"),
        )).toRealPath()
        try {
            block(root)
        } finally {
            Files.walk(root).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach(Files::delete) }
        }
    }
}
