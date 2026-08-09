@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportHint
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue
import platform.Network.nw_connection_cancel
import platform.Network.nw_connection_t
import platform.Network.nw_endpoint_create_host

class IosLanConnectCancellationTest {

    private class ControlledConnection(
        private val nativeConnection: nw_connection_t
    ) : IosConnectionHandle {
        private val mutableState = MutableStateFlow(ConnectionState.Connecting)
        override val state: StateFlow<ConnectionState> = mutableState
        var cancelled: Boolean = false
            private set

        override suspend fun write(bytes: ByteArray) = error("not used")
        override fun read(): Flow<ByteArray> = emptyFlow()
        override suspend fun close() = cancelNow("close")

        override fun cancelNow(reason: String) {
            if (cancelled) return
            cancelled = true
            mutableState.value = ConnectionState.Closed
            nw_connection_cancel(nativeConnection)
        }

        fun fail() {
            mutableState.value = ConnectionState.Closed
        }
    }

    @Test
    fun parentCancellationClosesUncommittedNetworkConnection() = runBlocking {
        val created = CompletableDeferred<ControlledConnection>()
        val context = TransportContext(
            appId = AppId("ios-connect-cancel"),
            localPeerId = PeerId("ios-local-connect-cancel"),
            deviceName = "local",
            platform = Platform.IOS
        )
        val transport = IosLanDataTransport(context, IosEndpointRegistry()) { connection, _ ->
            ControlledConnection(connection).also { created.complete(it) }
        }
        val peer = InternalPeer(
            publicPeer = Peer(
                id = PeerId("ios-remote-connect-cancel"),
                name = "remote",
                platform = Platform.IOS,
                supportedTransports = setOf(TransportKind.LAN)
            ),
            transportHints = listOf(
                TransportHint(TransportKind.LAN, host = "127.0.0.1", port = 9)
            )
        )

        val connectJob = launch { transport.connect(peer) }
        val connection = withTimeout(TEST_TIMEOUT_MILLIS) { created.await() }
        connectJob.cancel()
        withTimeout(TEST_TIMEOUT_MILLIS) { connectJob.cancelAndJoin() }

        assertTrue(connection.cancelled, "cancelled connect must cancel its NWConnection")
        transport.close()
    }

    @Test
    fun transportStopCancelsPendingDialAndPreventsLateSuccess() = runBlocking<Unit> {
        val created = CompletableDeferred<ControlledConnection>()
        val transport = IosLanDataTransport(
            TransportContext(
                appId = AppId("ios-connect-stop"),
                localPeerId = PeerId("ios-local-connect-stop"),
                deviceName = "local",
                platform = Platform.IOS
            ),
            IosEndpointRegistry()
        ) { connection, _ ->
            ControlledConnection(connection).also { created.complete(it) }
        }
        val result = async { runCatching { transport.connect(testPeer("ios-remote-connect-stop")) } }

        val connection = withTimeout(TEST_TIMEOUT_MILLIS) { created.await() }
        transport.stop()

        assertTrue(connection.cancelled, "restartable stop must cancel pending NWConnection ownership")
        assertIs<P2pError.ConnectionFailed>(
            withTimeout(TEST_TIMEOUT_MILLIS) { result.await() }.exceptionOrNull()
        )
        transport.close()
    }

    @Test
    fun failedOldDialCannotRemoveConcurrentFreshBrowseEndpoint() = runBlocking {
        val registry = IosEndpointRegistry()
        val peer = testPeer("ios-remote-fresh-endpoint")
        val oldLease = registry.put(
            peer.publicPeer.id,
            assertNotNull(nw_endpoint_create_host("127.0.0.1", "44001")),
            browserGeneration = 1
        )
        var freshLease: IosEndpointRegistry.Lease? = null
        val transport = IosLanDataTransport(
            TransportContext(
                appId = AppId("ios-connect-fresh-endpoint"),
                localPeerId = PeerId("ios-local-fresh-endpoint"),
                deviceName = "local",
                platform = Platform.IOS
            ),
            registry
        ) { connection, _ ->
            freshLease = registry.put(
                peer.publicPeer.id,
                assertNotNull(nw_endpoint_create_host("127.0.0.1", "44002")),
                browserGeneration = oldLease.browserGeneration + 1
            )
            ControlledConnection(connection).also(ControlledConnection::fail)
        }

        try {
            assertIs<P2pError.ConnectionFailed>(
                runCatching { transport.connect(peer) }.exceptionOrNull()
            )
            assertSame(freshLease, registry.lease(peer.publicPeer.id))
        } finally {
            transport.close()
        }
    }

    private fun testPeer(id: String) = InternalPeer(
        publicPeer = Peer(
            id = PeerId(id),
            name = "remote",
            platform = Platform.IOS,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = listOf(
            TransportHint(TransportKind.LAN, host = "127.0.0.1", port = 9)
        )
    )

    private companion object {
        const val TEST_TIMEOUT_MILLIS: Long = 5_000
    }
}
