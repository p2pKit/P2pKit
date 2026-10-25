package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import kotlinx.coroutines.test.runTest
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.Socket
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

class JvmRawConnectionPathWatchTest {
    private class OwnedSocket : Socket() {
        val bytes = ByteArrayOutputStream()
        var closes = 0
        override fun getOutputStream() = bytes
        override fun getInputStream() = ByteArrayInputStream(byteArrayOf(1))
        override fun close() { closes++; super.close() }
    }

    @Test fun aHealthyBackgroundObservationCannotAuthorizeALaterProhibitedWrite() = runTest {
        val socket = OwnedSocket()
        var removed = 0
        val connection = JvmRawConnection(socket, pathAllowed = { false },
            watchPath = { SocketPathWatch { removed++ } })
        assertFailsWith<IOException> { connection.write(byteArrayOf(1, 2, 3)) }
        assertEquals(0, socket.bytes.size())
        assertEquals(ConnectionState.Closed, connection.state.value)
        connection.close()
        assertEquals(1, removed)
        assertEquals(1, socket.closes)
    }

    @Test fun changedPathAfterAReadCannotDeliverBytesBasedOnAnEarlierHealthyWatchdog() = runTest {
        val socket = OwnedSocket()
        var checks = 0
        val connection = JvmRawConnection(socket, pathAllowed = { ++checks == 1 },
            watchPath = { SocketPathWatch {} })
        var delivered = 0
        assertFailsWith<IOException> { connection.read().collect { delivered += it.size } }
        assertEquals(0, delivered)
        assertEquals(ConnectionState.Closed, connection.state.value)
        connection.close()
        assertEquals(1, socket.closes)
    }

    @Test fun immediateWatchdogRejectionDuringRegistrationStillRetiresItsOriginalWatch() = runTest {
        val socket = OwnedSocket()
        var removed = 0
        val connection = JvmRawConnection(socket, pathAllowed = { true }, watchPath = { reject ->
            reject() // Before the constructor has received the registration.
            SocketPathWatch { removed++ }
        })
        connection.close()
        assertEquals(ConnectionState.Closed, connection.state.value)
        assertEquals(1, removed)
        assertEquals(1, socket.closes)
    }

    @Test fun watchdogStartupFailureCannotAbandonTheOriginalSocket() {
        val socket = OwnedSocket()
        assertFailsWith<IOException> {
            JvmRawConnection(socket, pathAllowed = { true }, watchPath = { throw IOException("synthetic startup") })
        }
        assertEquals(1, socket.closes)
    }

    @Test fun watchdogCleanupFailureStillReleasesTheSocketAndRemainsObservable() = runTest {
        val socket = OwnedSocket()
        val original = IOException("synthetic watch retirement failure")
        val connection = JvmRawConnection(socket, pathAllowed = { true },
            watchPath = { SocketPathWatch { throw original } })
        repeat(2) { assertSame(original, assertFailsWith<IOException> { connection.close() }) }
        assertEquals(1, socket.closes)
    }
}
