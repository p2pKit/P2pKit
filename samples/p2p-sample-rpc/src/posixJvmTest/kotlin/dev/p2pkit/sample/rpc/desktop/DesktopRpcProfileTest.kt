package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.sample.rpc.RpcCapacityContract
import dev.p2pkit.sample.rpc.lab.LabFiles
import kotlinx.coroutines.test.runTest
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.PosixFilePermissions
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertTrue

class DesktopRpcProfileTest {
    private fun password() = "synthetic-test-only-passphrase".toCharArray()
    private fun directory() = Files.createTempDirectory("rpc-profile-test-").toRealPath()
    private fun remove(root: Path) {
        Files.walk(root).use { it.sorted(Comparator.reverseOrder()).forEach(Files::delete) }
    }

    @Test
    fun identityTrustAndSelectionSurviveClosureWithoutPersistingPlaintextAndRevocationSurvivesRestart() = runTest {
        val root = directory()
        val path = root.resolve("profile")
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        val secret = ByteArray(64) { 42 }
        try {
            val password = password()
            val first = DesktopRpcProfile.open(path, password)
            assertTrue(password.all { it == '\u0000' })
            assertContentEquals(secret, first.vault.putIfAbsent("synthetic-identity", secret))
            for (purpose in RpcTrustPurpose.entries) first.trust.replace(RpcCapacityContract.appId, purpose, setOf(pin))
            first.close()
            first.close()
            val records = Files.walk(path).use { it.filter(Files::isRegularFile).toList() }
            records.forEach {
                val bytes = LabFiles.read(it)
                assertTrue(!bytes.toString(Charsets.UTF_8).contains(pin.value))
                assertTrue(!bytes.toString(Charsets.UTF_8).contains(String(password())))
            }
            val second = DesktopRpcProfile.open(path, password())
            assertContentEquals(secret, second.vault.read("synthetic-identity"))
            for (purpose in RpcTrustPurpose.entries) {
                assertEquals(setOf(pin), second.trust.load(RpcCapacityContract.appId, purpose))
                second.trust.replace(RpcCapacityContract.appId, purpose, emptySet())
            }
            second.close()
            val third = DesktopRpcProfile.open(path, password())
            for (purpose in RpcTrustPurpose.entries) {
                assertTrue(third.trust.load(RpcCapacityContract.appId, purpose).isEmpty())
            }
            assertContentEquals(secret, third.vault.read("synthetic-identity"))
            third.close()
        } finally { remove(root) }
    }

    @Test
    fun wrongPasswordConcurrentOpenAndCorruptionFailWithoutIdentityReset() {
        val root = directory()
        val path = root.resolve("profile")
        try {
            val first = DesktopRpcProfile.open(path, password())
            assertFails { DesktopRpcProfile.open(path, password()) }
            first.close()
            val records = Files.walk(path).use { it.filter(Files::isRegularFile).toList() }
                .associateWith(Files::readAllBytes)
            val wrong = "wrong-synthetic-passphrase".toCharArray()
            assertFails { DesktopRpcProfile.open(path, wrong) }
            assertTrue(wrong.all { it == '\u0000' })
            records.forEach { (file, bytes) -> assertContentEquals(bytes, Files.readAllBytes(file)) }
            val retry = DesktopRpcProfile.open(path, password())
            retry.close()
            val header = path.resolve("profile.header")
            LabFiles.write(header, byteArrayOf(1), replace = true)
            assertFails { DesktopRpcProfile.open(path, password()) }
            assertContentEquals(byteArrayOf(1), Files.readAllBytes(header))
        } finally { remove(root) }
    }

    @Test
    fun missingMetadataForeignFilesSymlinksAndLoosePermissionsAreNotRepairedOrDeleted() {
        val root = directory()
        try {
            val path = root.resolve("profile")
            val first = DesktopRpcProfile.open(path, password())
            first.close()
            Files.delete(path.resolve("profile.header"))
            assertFails { DesktopRpcProfile.open(path, password()) }
            assertTrue(Files.isDirectory(path.resolve("identity")))
            val link = root.resolve("linked")
            Files.createSymbolicLink(link, path)
            assertFails { DesktopRpcProfile.open(link, password()) }
            Files.delete(link)
            Files.setPosixFilePermissions(path, PosixFilePermissions.fromString("rwxr-xr-x"))
            assertFails { DesktopRpcProfile.open(path, password()) }
            Files.setPosixFilePermissions(path, PosixFilePermissions.fromString("rwx------"))
            val foreign = root.resolve("foreign")
            Files.createDirectory(foreign,
                PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")))
            LabFiles.write(foreign.resolve("keep.txt"), byteArrayOf(42))
            assertFails { DesktopRpcProfile.open(foreign, password()) }
            assertContentEquals(byteArrayOf(42), Files.readAllBytes(foreign.resolve("keep.txt")))
        } finally { remove(root) }
    }
}
