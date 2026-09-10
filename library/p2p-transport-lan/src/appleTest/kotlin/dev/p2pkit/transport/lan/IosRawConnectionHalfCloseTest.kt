@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.transport.lan.interop.p2pkit_nw_connection_receive_default
import dev.p2pkit.transport.lan.interop.p2pkit_nw_create_plain_tcp_parameters
import dev.p2pkit.transport.lan.interop.p2pkit_test_nw_connection_send_fin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import platform.Network.nw_connection_cancel
import platform.Network.nw_connection_create
import platform.Network.nw_connection_set_queue
import platform.Network.nw_connection_set_state_changed_handler
import platform.Network.nw_connection_start
import platform.Network.nw_connection_state_failed
import platform.Network.nw_connection_state_ready
import platform.Network.nw_endpoint_create_host
import platform.darwin.dispatch_queue_create

/** Native loopback only: FIN handling and resource release, without discovery/security/session fixtures. */
class IosRawConnectionHalfCloseTest {
    @Test
    fun remoteHalfCloseEndsReadFlowNormallyAndReleasesTheConnection() = runBlocking {
        val context = TransportContext(
            appId = AppId("ios-read-half-close"),
            localPeerId = PeerId("ios-read-half-close-local"),
            deviceName = "local",
            platform = Platform.IOS
        )
        val transport = IosLanDataTransport(context, IosEndpointRegistry())
        try {
            assertTrue(transport.start().isSuccess)
            val port = requireNotNull(transport.tcpPort.value)
            val incoming = async(start = CoroutineStart.UNDISPATCHED) {
                transport.incomingConnections().first()
            }
            val parameters = requireNotNull(p2pkit_nw_create_plain_tcp_parameters())
            val endpoint = requireNotNull(nw_endpoint_create_host("127.0.0.1", port.toString()))
            val peer = requireNotNull(nw_connection_create(endpoint, parameters))
            try {
                val ready = CompletableDeferred<Unit>()
                nw_connection_set_queue(peer, dispatch_queue_create("dev.p2pkit.test.rawconn.fin", null))
                nw_connection_set_state_changed_handler(peer) { state, _ ->
                    when (state) {
                        nw_connection_state_ready -> ready.complete(Unit)
                        nw_connection_state_failed -> ready.completeExceptionally(
                            IllegalStateException("Native half-close peer failed to connect")
                        )
                    }
                }
                nw_connection_start(peer)
                val inbound = withTimeout(TIMEOUT_MS) {
                    ready.await()
                    incoming.await()
                }
                try {
                    val reader = async(start = CoroutineStart.UNDISPATCHED) {
                        inbound.read().collect { error("The FIN-only peer must not send payload bytes") }
                    }
                    try {
                        val peerTerminated = CompletableDeferred<Boolean>()
                        p2pkit_nw_connection_receive_default(peer, 1u, 1u) { _, _, complete, error ->
                            peerTerminated.complete(complete || error != null)
                        }
                        val finSent = CompletableDeferred<Unit>()
                        p2pkit_test_nw_connection_send_fin(peer) { error ->
                            if (error == null) {
                                finSent.complete(Unit)
                            } else {
                                finSent.completeExceptionally(IllegalStateException("Native FIN send failed"))
                            }
                        }
                        withTimeout(TIMEOUT_MS) {
                            finSent.await()
                            reader.await()
                        }
                        assertEquals(ConnectionState.Closed, inbound.state.value)
                        // A state flag alone cannot prove native release. The peer has only
                        // sent FIN; its receive side must terminate before either explicit close.
                        assertTrue(
                            withTimeout(TIMEOUT_MS) { peerTerminated.await() },
                            "read EOF must terminate the native connection, not only update its state"
                        )
                    } finally {
                        withTimeout(TIMEOUT_MS) { reader.cancelAndJoin() }
                    }
                } finally {
                    inbound.close()
                }
            } finally {
                nw_connection_cancel(peer)
            }
        } finally {
            transport.close()
        }
    }

    private companion object {
        const val TIMEOUT_MS = 10_000L
    }
}
