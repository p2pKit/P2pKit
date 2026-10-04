package dev.p2pkit.sample.rpc.desktop

import kotlinx.coroutines.test.runTest
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.PosixFilePermissions
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class DesktopRpcRuntimeTest {
    @Test
    fun runtimeOwnershipPrecedesEveryFileAllocation() = runTest {
        val parent = directory()
        try {
            val runtime = DesktopRpcRuntime.create(parent)
            assertTrue(Files.list(parent).use { it.findAny().isEmpty })
            runtime.close()
            assertTrue(Files.list(parent).use { it.findAny().isEmpty })
        } finally { removeFixture(parent) }
    }

    @Test
    fun unusedRuntimeOwnsAPrivateVaultAndRetiresOnlyItsNewDirectory() = runTest {
        val parent = directory()
        try {
            val runtime = DesktopRpcRuntime.create(parent)
            runtime.prepareStore()
            val owned = Files.list(parent).use { it.toList().single() }
            assertEquals(PosixFilePermissions.fromString("rwx------"), Files.getPosixFilePermissions(owned))
            assertTrue(Files.isDirectory(owned.resolve("identity")))
            runtime.close()
            assertFalse(Files.exists(owned))
        } finally { removeFixture(parent) }
    }

    @Test
    fun unexpectedForeignContentIsPreservedAndCloseCannotClaimSuccess() = runTest {
        val parent = directory()
        try {
            val runtime = DesktopRpcRuntime.create(parent)
            runtime.prepareStore()
            val owned = Files.list(parent).use { it.toList().single() }
            val foreign = owned.resolve("unowned.txt")
            Files.writeString(foreign, "synthetic foreign content")
            assertFailsWith<java.nio.file.DirectoryNotEmptyException> { runtime.close() }
            assertEquals("synthetic foreign content", Files.readString(foreign))
        } finally { removeFixture(parent) }
    }

    @Test
    fun replacedIdentityDirectoryIsNotDestroyed() = runTest {
        val parent = directory()
        try {
            val runtime = DesktopRpcRuntime.create(parent)
            runtime.prepareStore()
            val owned = Files.list(parent).use { it.toList().single() }
            val original = owned.resolve("identity-original")
            Files.move(owned.resolve("identity"), original)
            Files.createDirectory(owned.resolve("identity"),
                PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")))
            assertFailsWith<IllegalStateException> { runtime.close() }
            assertTrue(Files.isDirectory(original))
            assertTrue(Files.isDirectory(owned.resolve("identity")))
        } finally { removeFixture(parent) }
    }

    @Test
    fun replacedRootDirectoryIsNotDestroyed() = runTest {
        val parent = directory()
        try {
            val runtime = DesktopRpcRuntime.create(parent)
            runtime.prepareStore()
            val owned = Files.list(parent).use { it.toList().single() }
            val original = parent.resolve("original")
            Files.move(owned, original)
            Files.createDirectory(owned,
                PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")))
            assertFailsWith<IllegalStateException> { runtime.close() }
            assertTrue(Files.isDirectory(original.resolve("identity")))
            assertTrue(Files.isDirectory(owned))
        } finally { removeFixture(parent) }
    }

    private fun directory(): Path = Files.createTempDirectory("rpc-desktop-store-test-",
        PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------"))).toRealPath()

    private fun removeFixture(parent: Path) {
        // Only the freshly allocated test directory and the synthetic files introduced in this test.
        Files.walk(parent).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach(Files::delete) }
    }
}
