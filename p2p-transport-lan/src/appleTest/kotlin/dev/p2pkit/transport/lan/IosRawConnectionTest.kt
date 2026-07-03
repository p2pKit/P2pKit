@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.transport.lan.interop.p2pkit_nw_create_plain_tcp_parameters
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import platform.Network.nw_connection_create
import platform.Network.nw_endpoint_create_host
import platform.darwin.dispatch_queue_create

/**
 * Direct unit tests for [IosRawConnection]'s local close/cancel latch —
 * the pure-logic paths that need no live peer:
 *
 * - [IosRawConnection.close] / [IosRawConnection.cancelNow] flip the state
 *   to [ConnectionState.Closed] synchronously and are idempotent
 *   (cancelOnce is CAS-guarded).
 * - `write()` on a closed connection is refused promptly — it must throw
 *   from the entry `closed` check without ever suspending into the
 *   nw_connection_send await. (The V0.6-WRITE-TIMEOUT send deadline itself
 *   needs a wedged live peer and is covered by manual verification, not
 *   this suite.)
 *
 * The connection dials 127.0.0.1:9 (discard port; nothing listens there in
 * the simulator). The dial's outcome is irrelevant — every assertion
 * targets the local latch, never a successful round-trip, so there is no
 * network-timing flake surface.
 */
class IosRawConnectionTest {

    private fun newStartedConnection(): IosRawConnection {
        val params = p2pkit_nw_create_plain_tcp_parameters()
            ?: error("p2pkit_nw_create_plain_tcp_parameters returned null")
        val endpoint = nw_endpoint_create_host("127.0.0.1", "9")
            ?: error("nw_endpoint_create_host returned null")
        val conn = nw_connection_create(endpoint, params)
            ?: error("nw_connection_create returned null")
        val queue = dispatch_queue_create("dev.p2pkit.test.rawconn", null)
        return IosRawConnection.wrap(conn, queue)
    }

    @Test
    fun writeAfterCloseIsRefusedPromptly() = runBlocking {
        val raw = newStartedConnection()
        raw.close()
        assertEquals(ConnectionState.Closed, raw.state.value)
        // withTimeout bounds "promptly": the refuse path must throw from the
        // entry check, never suspend into the send await.
        val e = withTimeout(2_000) {
            assertFailsWith<IllegalStateException> { raw.write(byteArrayOf(1, 2, 3)) }
        }
        assertEquals("connection closed", e.message)
    }

    @Test
    fun cancelNowLatchesClosedSynchronouslyAndIsIdempotent() = runBlocking {
        val raw = newStartedConnection()
        raw.cancelNow("test: inbound dropped")
        assertEquals(ConnectionState.Closed, raw.state.value)
        // Repeat cancels and a later close() are safe no-ops (CAS-guarded).
        raw.cancelNow("test: again")
        raw.close()
        assertEquals(ConnectionState.Closed, raw.state.value)
        val e = withTimeout(2_000) {
            assertFailsWith<IllegalStateException> { raw.write(byteArrayOf(1)) }
        }
        assertEquals("connection closed", e.message)
    }
}
