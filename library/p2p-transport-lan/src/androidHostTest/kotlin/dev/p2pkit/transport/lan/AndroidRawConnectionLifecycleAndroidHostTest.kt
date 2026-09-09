package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout

/** Exercises Android's shipped socket implementation on a host JVM, not ART or a physical device. */
class AndroidRawConnectionLifecycleAndroidHostTest {
    @Test
    fun remoteHalfCloseEndsReadFlowNormallyAndReleasesTheSocket() = runBlocking {
        val loopback = InetAddress.getLoopbackAddress()
        ServerSocket(0, 1, loopback).use { server ->
            Socket().use { local ->
                local.connect(InetSocketAddress(loopback, server.localPort), CONNECT_TIMEOUT_MS)
                server.accept().use { remote ->
                    val connection = AndroidRawConnection(local)
                    val reader = async(start = CoroutineStart.UNDISPATCHED) {
                        connection.read().collect { error("The FIN-only peer must not send payload bytes") }
                    }
                    try {
                        // Send a TCP FIN without closing the peer's read side or its descriptor.
                        remote.shutdownOutput()
                        withTimeout(TIMEOUT_MS) { reader.await() }

                        assertFalse(remote.isClosed, "the fixture must half-close, not close both directions")
                        assertTrue(local.isClosed, "normal EOF must release the descriptor before explicit close()")
                        assertEquals(ConnectionState.Closed, connection.state.value)
                    } finally {
                        connection.close()
                        withTimeout(TIMEOUT_MS) { reader.cancelAndJoin() }
                    }
                }
            }
        }
    }

    private companion object {
        const val CONNECT_TIMEOUT_MS = 5_000
        const val TIMEOUT_MS = 10_000L
    }
}
