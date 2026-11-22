package dev.p2pkit.sample.android

import android.net.Uri
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import java.io.File
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.io.RawSource
import kotlinx.io.buffered
import kotlinx.io.readByteArray
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Real ViewModel and Android URI adapter with an inert recording session. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class RoomFilePickerTest {
    @Test
    fun delayedSelectionsReuseOriginalSessionAndSendExactBytesOnce() = runTest {
        withSampleViewModel {
            val session = PickerSession("original")
            vm.start()
            room.sessions.value = listOf(session)
            runCurrent()
            repeat(10) { index ->
                val delay = listOf(0L, 5_000L, 15_000L, 30_000L, 60_000L)[index % 5]
                val expected = ByteArray(256) { (it * 31 + index).toByte() }
                withFile(expected) { uri ->
                    vm.openFilePicker(session) { vm.notifyBackgrounded() }
                    advanceTimeBy(delay)
                    assertEquals(0, room.backgrounds)
                    // ActivityResultRegistry may deliver at ON_START before our foreground callback.
                    vm.onFilePickerResult(uri)
                    vm.notifyForegrounded()
                    val (size, bytes) = session.sent.receive()
                    assertEquals(256L, size)
                    assertContentEquals(expected, bytes)
                    assertContentEquals(sha256(expected), sha256(bytes))
                    assertTrue(session.sent.tryReceive().isFailure)
                    assertEquals(index + 1, pickerReleases)
                    assertEquals(0, room.connectCalls)
                }
            }
            vm.notifyBackgrounded()
            assertEquals(1, room.backgrounds)
        }
    }

    @Test
    fun cancellationAndLaunchFailuresRetireExecutionAndKeepSession() = runTest {
        withSampleViewModel {
            val session = PickerSession("original")
            vm.start()
            room.sessions.value = listOf(session)
            runCurrent()
            pickerAllowed = false
            vm.openFilePicker(session) { error("A refused lease must never launch the picker") }
            pickerAllowed = true
            vm.openFilePicker(session) { throw IllegalStateException("launch rejected") }
            assertEquals(1, pickerReleases)
            vm.openFilePicker(session) { vm.notifyBackgrounded() }
            vm.onFilePickerResult(null)
            vm.notifyForegrounded()
            assertNull(pickerLost)
            assertEquals(2, pickerReleases)
            assertEquals(0, room.backgrounds)
            assertTrue(session.sent.tryReceive().isFailure)
        }
    }

    @Test
    fun disconnectRefusesStaleResultsEvenWhenTheSamePeerReconnects() = runTest {
        withSampleViewModel {
            val old = PickerSession("original")
            val replacement = PickerSession("replacement")
            vm.start()
            room.sessions.value = listOf(old)
            runCurrent()
            vm.openFilePicker(old) { vm.notifyBackgrounded() }
            old.close()
            runCurrent()
            assertNull(pickerLost)
            assertEquals(1, room.backgrounds)
            room.sessions.value = listOf(replacement)
            vm.notifyForegrounded()
            runCurrent()
            var opened = false
            vm.openFilePicker(replacement) { opened = true }
            assertFalse(opened, "The previous Activity Result has not been drained")
            withFile(byteArrayOf(2, 3)) { uri ->
                vm.onFilePickerResult(uri)
                assertTrue(vm.roomMessages.last().body.contains("File not sent"))
                assertTrue(old.sent.tryReceive().isFailure)
                assertTrue(replacement.sent.tryReceive().isFailure)
                vm.openFilePicker(replacement) { opened = true }
                assertTrue(opened)
                vm.onFilePickerResult(uri)
                assertContentEquals(byteArrayOf(2, 3), replacement.sent.receive().second)
            }
        }
    }

    @Test
    fun expiryAndStopDoNotRetainAFilePickerExecution() = runTest {
        withSampleViewModel {
            val session = PickerSession("original")
            vm.start()
            room.sessions.value = listOf(session)
            runCurrent()
            vm.openFilePicker(session) { vm.notifyBackgrounded() }
            advanceTimeBy(120_001)
            assertNull(pickerLost)
            assertEquals(1, room.backgrounds)
            vm.notifyForegrounded()
            vm.onFilePickerResult(null)
            vm.openFilePicker(session) {}
            vm.stop()
            runCurrent()
            assertNull(pickerLost)
            assertEquals(2, pickerReleases)
            assertEquals(1, room.stopCalls)
        }
    }

    private suspend fun withFile(bytes: ByteArray, use: suspend (Uri) -> Unit) {
        val file = File.createTempFile("picker", ".bin")
        try {
            file.writeBytes(bytes)
            use(Uri.fromFile(file))
        } finally {
            assertTrue(file.delete())
        }
    }

    private fun sha256(bytes: ByteArray): ByteArray = MessageDigest.getInstance("SHA-256").digest(bytes)

    @Suppress("OVERRIDE_DEPRECATION")
    private class PickerSession(override val id: String) : P2pSession {
        override val peer = Peer(PeerId("picker-peer"), "iPhone", Platform.UNKNOWN, setOf(TransportKind.LAN))
        override val state = MutableStateFlow<ConnectionState>(ConnectionState.Connected)
        override val incoming = MutableSharedFlow<P2pMessage>()
        override val incomingFiles = MutableSharedFlow<P2pFileOffer>()
        val sent = Channel<Pair<Long, ByteArray>>(Channel.UNLIMITED)
        private var sequence = 0

        override suspend fun send(message: P2pMessage) = error("Unexpected message")

        override suspend fun sendFile(name: String, sizeBytes: Long, mimeType: String?, source: RawSource): P2pFileTransfer {
            val data = source.buffered().use { it.readByteArray() }
            sent.send(sizeBytes to data)
            val transferId = (++sequence).toString(16).padStart(32, '0')
            return object : P2pFileTransfer {
                override val id = transferId
                override val peer = this@PickerSession.peer
                override val name = name
                override val sizeBytes = sizeBytes
                override val mimeType = mimeType
                override val state = MutableStateFlow<FileTransferState>(FileTransferState.Completed)
                override val bytesTransferred = MutableStateFlow(sizeBytes)
                override suspend fun cancel(reason: String?) = Unit
            }
        }

        override suspend fun close() { state.value = ConnectionState.Closed }
    }
}
