package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.security.IdentityNamespace
import dev.p2pkit.core.security.IdentityStateMarkerCodec
import java.io.Closeable
import java.io.File
import java.io.FileDescriptor
import java.io.FileOutputStream
import java.io.IOException
import java.io.SyncFailedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.CancellationException

/** Real content streams; only AtomicFile publication and Android syscalls are substituted. */
class AndroidIdentityAtomicWriteAndroidHostTest {
    @Test
    fun blobAndResetMarkerSyncContentBeforePublicationAndDirectoryAfterOwnershipTransfer() {
        val appId = AppId("dev.p2pkit.atomic-write-test")
        val namespace = IdentityNamespace(appId, appId.value.encodeToByteArray(), ByteArray(32) { 7 })
        val blob = AndroidIdentityBlobCodec.encode(namespace, ByteArray(12) { 9 }, ByteArray(120) { 11 })
        AtomicWriteHarness().use { harness ->
            harness.write(blob)
            assertContentEquals(blob, harness.target.readBytes())
            assertEquals(committedEvents, harness.events)
            assertTrue(harness.committed)
            assertTrue(harness.warnings.isEmpty())
        }
        AtomicWriteHarness().use { harness ->
            AndroidIdentityResetMarker.replaceAndVerify(
                namespace = namespace,
                replace = harness::write,
                reread = { harness.target.readBytes() }
            )
            IdentityStateMarkerCodec.decodeResetPending(namespace, harness.target.readBytes())
            assertEquals(committedEvents, harness.events)
            assertTrue(harness.committed)
        }
    }

    @Test
    fun prepublicationFailuresRollBackOnlyOwnedStreamsAndPreserveBothFailures() {
        val stages = listOf("start", "write", "file-sync", "finish")
        stages.forEachIndexed { index, stage ->
            AtomicWriteHarness().use { harness ->
                val primary = IOException("injected $stage failure")
                val cleanup = IOException("injected rollback failure")
                harness.failAt = stage
                harness.failure = primary
                harness.rollbackFailure = cleanup

                val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
                    harness.write(byteArrayOf(1, 2, 3))
                }

                assertEquals(LocalIdentityFailureKind.PERSISTENCE_FAILED, error.kind)
                assertEquals(LocalIdentityRecovery.RETRY, error.recovery)
                assertSame(primary, error.cause)
                val rollback = if (stage == "start") emptyList() else listOf("rollback")
                assertEquals(stages.take(index + 1) + rollback, harness.events)
                assertEquals(if (stage == "start") emptyList() else listOf(cleanup), primary.suppressedExceptions)
                assertFalse(harness.committed)
                assertFalse(harness.target.exists())
                assertTrue(harness.warnings.isEmpty())
            }
        }
    }

    @Test
    fun contentSyncCancellationIsNotWrappedAndStillRollsBack() {
        AtomicWriteHarness().use { harness ->
            val cancellation = CancellationException("cancel content sync")
            val cleanup = IOException("rollback failed")
            harness.failAt = "file-sync"
            harness.failure = cancellation
            harness.rollbackFailure = cleanup

            assertSame(cancellation, assertFailsWith<CancellationException> { harness.write(byteArrayOf(4)) })

            assertEquals(listOf(cleanup), cancellation.suppressedExceptions)
            assertEquals(listOf("start", "write", "file-sync", "rollback"), harness.events)
            assertFalse(harness.committed)
        }
    }

    @Test
    fun defaultCheckedContentBarrierRejectsAClosedDescriptorBeforeFinish() {
        AtomicWriteHarness().use { harness ->
            val events = mutableListOf<String>()
            val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
                writeAndroidIdentityAtomic(
                    bytes = byteArrayOf(4, 5),
                    startWrite = {
                        object : FileOutputStream(File(harness.directory, "closed-descriptor")) {
                            override fun write(bytes: ByteArray) {
                                super.write(bytes)
                                close()
                            }
                        }
                    },
                    finishWrite = { events += "finish" },
                    failWrite = {
                        events += "rollback"
                        it.close()
                    },
                    syncDirectory = { events += "directory" },
                    logger = P2pLogger.NoOp
                )
            }
            assertTrue(error.cause is SyncFailedException)
            assertEquals(listOf("rollback"), events)
        }
    }

    @Test
    fun directoryFailuresWarnWithoutExposingPrivateDetailsOrRollingBackTheWinner() {
        listOf("directory-open", "directory-sync", "directory-close").forEach { stage ->
            AtomicWriteHarness().use { harness ->
                harness.failAt = stage
                harness.failure = IOException("private-appid/private-path/private-alias/$stage")
                val bytes = byteArrayOf(5, 6, 7)

                harness.write(bytes)

                assertTrue(harness.committed)
                assertContentEquals(bytes, harness.target.readBytes())
                assertFalse("rollback" in harness.events)
                assertEquals("ownership", harness.events[4])
                assertEquals("warning", harness.events.last())
                assertEquals(listOf<Pair<String, Throwable?>>(safeWarning to null), harness.warnings)
                val directoryEvents = harness.events.filter { it.startsWith("directory-") }
                assertEquals(
                    if (stage == "directory-open") listOf("directory-open") else directoryBarrierEvents,
                    directoryEvents
                )
            }
        }
    }

    @Test
    fun diagnosticCancellationCannotChangePublishedState() {
        AtomicWriteHarness().use { harness ->
            harness.failAt = "directory-sync"
            harness.failure = IOException("injected directory sync failure")
            harness.warningFailure = CancellationException("host logger failed")
            val bytes = byteArrayOf(8, 9, 10)

            harness.write(bytes)

            assertTrue(harness.committed)
            assertContentEquals(bytes, harness.target.readBytes())
            assertEquals(committedEvents + "warning", harness.events)
            assertEquals(listOf<Pair<String, Throwable?>>(safeWarning to null), harness.warnings)
        }
    }

    @Test
    fun directoryCancellationPropagatesOnlyAfterPublicationOwnershipIsReleased() {
        AtomicWriteHarness().use { harness ->
            val cancellation = CancellationException("cancel directory sync")
            harness.failAt = "directory-sync"
            harness.failure = cancellation
            val bytes = byteArrayOf(11, 12)

            assertSame(cancellation, assertFailsWith<CancellationException> { harness.write(bytes) })

            assertTrue(harness.committed, "first-creation cleanup must no longer own this blob")
            assertContentEquals(bytes, harness.target.readBytes())
            assertEquals(committedEvents, harness.events)
            assertTrue(harness.warnings.isEmpty())
        }
    }

    @Test
    fun directoryBarrierPreservesSyncFailureAndReportsCloseOnlyFailure() {
        listOf(true, false).forEach { failSync ->
            AtomicWriteHarness().use { harness ->
                val syncFailure = IOException("directory sync failed")
                val closeFailure = IOException("directory close failed")
                val events = mutableListOf<String>()
                val descriptor = FileDescriptor()

                val thrown = assertFailsWith<IOException> {
                    syncAndroidIdentityParentDirectory(
                        directory = harness.directory,
                        openDirectory = {
                            events += "open"
                            descriptor
                        },
                        syncDirectory = {
                            assertSame(descriptor, it)
                            events += "sync"
                            if (failSync) throw syncFailure
                        },
                        closeDirectory = {
                            assertSame(descriptor, it)
                            events += "close"
                            throw closeFailure
                        }
                    )
                }

                assertSame(if (failSync) syncFailure else closeFailure, thrown)
                assertEquals(if (failSync) listOf(closeFailure) else emptyList(), thrown.suppressedExceptions)
                assertEquals(listOf("open", "sync", "close"), events)
            }
        }
    }

    private class AtomicWriteHarness : Closeable {
        val directory: File = Files.createTempDirectory("p2pkit-identity-atomic-").toFile()
        private val staging = File(directory, "staging")
        val target = File(directory, "published")
        val events = mutableListOf<String>()
        val warnings = mutableListOf<Pair<String, Throwable?>>()
        var committed = false
        var failAt: String? = null
        var failure: Throwable = IOException("injected failure")
        var rollbackFailure: Throwable? = null
        var warningFailure: Throwable? = null
        private var stream: FileOutputStream? = null
        private val descriptor = FileDescriptor()
        private val logger = object : P2pLogger by P2pLogger.NoOp {
            override fun warn(message: String, throwable: Throwable?) {
                events += "warning"
                warnings += message to throwable
                warningFailure?.let { throw it }
            }
        }

        fun write(bytes: ByteArray) = writeAndroidIdentityAtomic(
            bytes = bytes,
            startWrite = {
                event("start")
                object : FileOutputStream(staging) {
                    override fun write(bytes: ByteArray) {
                        event("write")
                        super.write(bytes)
                    }
                }.also { stream = it }
            },
            syncFile = {
                event("file-sync")
                it.fd.sync()
            },
            finishWrite = {
                event("finish")
                it.close()
                Files.move(staging.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING)
            },
            failWrite = {
                events += "rollback"
                it.close()
                Files.deleteIfExists(staging.toPath())
                rollbackFailure?.let { failure -> throw failure }
            },
            onCommitted = {
                events += "ownership"
                committed = true
            },
            syncDirectory = {
                syncAndroidIdentityParentDirectory(
                    directory = directory,
                    openDirectory = {
                        assertEquals(directory.absolutePath, it)
                        event("directory-open")
                        descriptor
                    },
                    syncDirectory = {
                        assertSame(descriptor, it)
                        event("directory-sync")
                    },
                    closeDirectory = {
                        assertSame(descriptor, it)
                        event("directory-close")
                    }
                )
            },
            logger = logger
        )

        private fun event(name: String) {
            events += name
            if (failAt == name) throw failure
        }

        override fun close() {
            stream?.close()
            check(directory.deleteRecursively()) { "identity test directory cleanup failed" }
        }
    }

    private companion object {
        val directoryBarrierEvents = listOf("directory-open", "directory-sync", "directory-close")
        val committedEvents = listOf("start", "write", "file-sync", "finish", "ownership") + directoryBarrierEvents
        const val safeWarning =
            "Android secure identity state was published, but its directory durability barrier failed; " +
                "crash durability is reduced"
    }
}
