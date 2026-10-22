package dev.p2pkit.sample.android

import android.system.ErrnoException
import android.system.OsConstants
import dev.p2pkit.sample.diagnostics.cleanupStaleTransferPartsOnce
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlinx.coroutines.runBlocking
import kotlinx.io.Buffer
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.Implementation
import org.robolectric.annotation.Implements
import org.robolectric.shadows.ShadowLinux

/** Actual default factory and file IO with API35 framework shadows, not ART durability evidence. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE, shadows = [AndroidIncomingDestinationTest.FileMovingLinux::class])
class AndroidIncomingDestinationTest {
    @Test
    fun defaultFactoryUsesAndroidFacadeAndAbortRetiresOnlyItsOwnedStaging() = runBlocking {
        withDirectory { directory ->
            val existing = File(directory, ".p2pkit-completed.part").also { it.writeText("keep") }
            val prepared = prepareIncomingDestination {
                IncomingFileLocation(uniqueDestination(directory, "incoming.bin"), "test-private")
            }
            try {
                assertAndroidDelegate(prepared)
                val sink = prepared.destination.openSink()
                val buffer = Buffer().apply { write(byteArrayOf(1, 2, 3)) }
                sink.write(buffer, 3)
                sink.flush()
                val parts = directory.walkTopDown().filter { it.isFile && it.name.endsWith(".part") }.toList()
                assertEquals(2, parts.size)
                assertTrue(parts.any { it != existing && it.parentFile != directory })
                cleanupStaleTransferPartsOnce(directory)
                assertTrue(parts.all { it.exists() }, "live leased staging must survive cleanup")
                prepared.destination.abort(null)
                assertFalse(prepared.location.file.exists())
                assertEquals(listOf(existing), directory.walkTopDown().filter { it.isFile }.toList())
                assertEquals("keep", existing.readText())
            } finally { prepared.destination.abort(null) }
        }
    }

    @Test
    fun defaultFactoryRetainsPublishedBytesWhenHostDirectorySyncIsUnavailable() = runBlocking {
        withDirectory { directory ->
            val prepared = prepareIncomingDestination {
                IncomingFileLocation(uniqueDestination(directory, ".p2pkit-completed.part"), "test-private")
            }
            try {
                assertAndroidDelegate(prepared)
                val bytes = ByteArray(257) { it.toByte() }
                val buffer = Buffer().apply { write(bytes) }
                prepared.destination.openSink().write(buffer, bytes.size.toLong())
                // ShadowLinux cannot open a directory. The real Android destination must report
                // that missing durability barrier, not claim a successful commit. Rename already
                // happened: abort must preserve the published bytes despite this terminal error.
                val failure = assertFailsWith<ErrnoException> { prepared.destination.commit() }
                assertEquals(OsConstants.EIO, failure.errno)
                assertTrue(failure.message.orEmpty().startsWith("open failed"))
                assertContentEquals(bytes, prepared.location.file.readBytes())
                prepared.destination.abort(null)
                cleanupStaleTransferPartsOnce(directory)
                assertContentEquals(bytes, prepared.location.file.readBytes())
                assertEquals(listOf(prepared.location.file), directory.walkTopDown().filter { it.isFile }.toList())
            } finally { prepared.destination.abort(null) }
        }
    }

    private fun assertAndroidDelegate(prepared: PreparedIncomingDestination) {
        // The wrapper is real: no injected destination or stand-in platform factory.
        val field = prepared.destination.javaClass.getDeclaredField("delegate")
        field.isAccessible = true
        assertEquals("dev.p2pkit.core.transfer.AndroidDurableFileDestination",
            field.get(prepared.destination).javaClass.name)
    }

    private suspend fun withDirectory(block: suspend (File) -> Unit) {
        val directory = Files.createTempDirectory("android-real-destination-").toFile().canonicalFile
        try { block(directory) } finally { check(directory.deleteRecursively()) }
    }

    /** API35's instrumented Linux.rename is a no-op. Model only that syscall with host atomic IO. */
    @Implements(className = "libcore.io.Linux", isInAndroidSdk = false)
    class FileMovingLinux : ShadowLinux() {
        @Implementation
        protected fun rename(oldPath: String, newPath: String) {
            Files.move(File(oldPath).toPath(), File(newPath).toPath(),
                StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
        }
    }
}
