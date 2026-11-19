package dev.p2pkit.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.security.JvmSecureIdentityStore
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.HasLocalTcpEndpoint
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import dev.p2pkit.provisioning.desktop.JvmProvisioningFactory
import dev.p2pkit.transport.lan.LanRole
import dev.p2pkit.transport.lan.OrganizationLan
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.runInterruptible
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.builtins.serializer
import java.net.InetAddress
import java.net.InetSocketAddress
import java.nio.ByteBuffer
import java.nio.channels.ServerSocketChannel
import java.nio.channels.SocketChannel
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotSame
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Genuine authenticated SDK sessions over local TCP. Store/adapter fixtures own only this test's resources. */
class RpcTrustReloadTcpTest {
    private val app = AppId("rpc.trust.reload.tcp")
    private val lan = OrganizationLan(listOf("10.0.0.0/24"), "trusttest", TEST_ADDRESS)
    private val procedure = RpcProcedure(
        "trust.echo", 1, String.serializer(), String.serializer(), String.serializer(),
    )

    @Test
    fun refreshRetainsUnaffectedSessionsAndFailsClosedOnStoreLoss() = runBlocking<Unit> {
        val hostStore = Store(app, RpcTrustPurpose.HostClients)
        val hostPort = TcpPeer(LanRole.Host)
        val deviceA = TcpPeer(LanRole.DialOnly)
        val deviceB = TcpPeer(LanRole.DialOnly)
        val scopes = MutableStateFlow<Map<PeerFingerprint, RpcAuthorizationScope>>(emptyMap())
        val latest = MutableStateFlow<Map<PeerFingerprint, RpcCallContext>>(emptyMap())
        val aEntered = CompletableDeferred<Unit>()
        val aCancelled = CompletableDeferred<Unit>()
        val host = RpcHost.create(hostPort.platform, this) {
            appId = app
            lan = this@RpcTrustReloadTcpTest.lan
            trustStore = hostStore
            advertise = false
            registerScopedWithPhysicalSession(
                procedure,
                authenticate = { incoming, _ -> scopes.value[incoming.peer.fingerprint] },
                authorize = { context -> scopes.value[context.peer.fingerprint] === context.scope },
            ) { context, request ->
                val pin = checkNotNull(context.peer.fingerprint)
                latest.update { it + (pin to context) }
                if (request == "hold") {
                    aEntered.complete(Unit)
                    try {
                        awaitCancellation()
                    } finally {
                        aCancelled.complete(Unit)
                    }
                }
                RpcReply.Success(request)
            }
        }
        try {
            withTimeout(25_000) {
                assertEquals(RpcFailureKind.Closed, assertFailsWith<RpcFailure> { host.reloadTrustFromStore() }.kind)
                host.start()
                val endpoint = host.endpoint()
                val target = RpcSelectedHost(host.fingerprint, endpoint)
                val a = client(deviceA, target)
                try {
                    val b = client(deviceB, target)
                    try {
                        assertNotEquals(a.fingerprint, b.fingerprint)
                        val pins = setOf(a.fingerprint, b.fingerprint)
                        val scopeA = RpcAuthorizationScope(RpcApplicationSession(a.fingerprint, "a", "login-a"))
                        val scopeB = RpcAuthorizationScope(RpcApplicationSession(b.fingerprint, "b", "login-b"))
                        scopes.value = mapOf(a.fingerprint to scopeA, b.fingerprint to scopeB)
                        hostStore.commit(pins)
                        host.reloadTrustFromStore()
                        a.connect(target)
                        b.connect(target)
                        echo(a, "a before")
                        echo(b, "b before")
                        val originalA = checkNotNull(latest.value.getValue(a.fingerprint).physicalSession)
                        val originalB = latest.value.getValue(b.fingerprint)
                        val physicalB = checkNotNull(originalB.physicalSession)
                        assertSame(scopeB, originalB.authorizationScope)

                        val pending = async { assertFailsWith<RpcFailure> { a.call(procedure, "hold") } }
                        aEntered.await()
                        hostStore.commit(setOf(b.fingerprint))
                        host.reloadTrustFromStore()
                        aCancelled.await()
                        pending.await()
                        assertEquals(RpcPhysicalSessionClosure.Closed, originalA.closure.value)
                        assertFalse(host.trust.isTrusted(a.fingerprint))
                        assertFailsWith<RpcFailure> { a.call(procedure, "withdrawn") }
                        val beforeRejected = deviceA.dials.get()
                        assertFailsWith<RpcFailure> { a.connect(target) }
                        assertEquals(beforeRejected + 1, deviceA.dials.get())
                        assertEquals(RpcReply.Success("b during withdrawal"), b.call(procedure, "b during withdrawal"))
                        assertSame(physicalB, latest.value.getValue(b.fingerprint).physicalSession)
                        assertSame(scopeB, latest.value.getValue(b.fingerprint).authorizationScope)

                        // Device trust readmission still requires application authentication.
                        scopes.value = mapOf(b.fingerprint to scopeB)
                        hostStore.commit(pins)
                        host.reloadTrustFromStore()
                        a.connect(target)
                        assertEquals(
                            RpcFailureKind.Unauthorized,
                            assertFailsWith<RpcFailure> { a.call(procedure, "no application login") }.kind,
                        )
                        val newScopeA = RpcAuthorizationScope(
                            RpcApplicationSession(a.fingerprint, "a", "new-login-a"),
                        )
                        scopes.value += a.fingerprint to newScopeA
                        echo(a, "a after fresh approval")
                        echo(b, "b after")
                        assertNotSame(originalA, latest.value.getValue(a.fingerprint).physicalSession)
                        assertSame(newScopeA, latest.value.getValue(a.fingerprint).authorizationScope)
                        val finalB = latest.value.getValue(b.fingerprint)
                        assertSame(physicalB, finalB.physicalSession)
                        assertSame(scopeB, finalB.authorizationScope)
                        assertEquals(originalB.hostIncarnation, finalB.hostIncarnation)
                        assertEquals(1, deviceB.dials.get())
                        assertEquals(RpcConnectionState.Ready, b.state.value)
                        assertTrue(physicalB.isConnected)
                        assertTrue(scopeB.session.isActive)
                        assertEquals(endpoint.port, host.endpoint().port)
                        assertEquals(pins, host.trust.fingerprints().toSet())
                        assertEquals(RpcHostState.Running, host.state.value)

                        hostStore.failReads()
                        assertEquals(
                            RpcFailureKind.TrustStorage,
                            assertFailsWith<RpcFailure> { host.reloadTrustFromStore() }.kind,
                        )
                        assertEquals(RpcHostState.Closed, host.state.value)
                        assertTrue(host.trust.fingerprints().isEmpty())
                        assertFalse(physicalB.isConnected)
                        assertFailsWith<RpcFailure> { b.call(procedure, "closed") }
                    } finally {
                        b.close()
                    }
                } finally {
                    a.close()
                }
            }
        } finally {
            try {
                host.close()
            } finally {
                hostPort.identity.clear()
                deviceA.identity.clear()
                deviceB.identity.clear()
            }
        }
    }

    private suspend fun CoroutineScope.client(device: TcpPeer, target: RpcSelectedHost): RpcClient =
        RpcClient.create(device.platform, this) {
            appId = app
            lan = this@RpcTrustReloadTcpTest.lan
            transportReconnect = false
            trustStore = Store(app, RpcTrustPurpose.SelectedHosts, setOf(target.fingerprint))
        }

    private suspend fun echo(client: RpcClient, value: String) {
        assertEquals(RpcReply.Success(value), client.call(procedure, value))
    }

    private class Store(
        private val app: AppId,
        private val purpose: RpcTrustPurpose,
        initial: Set<PeerFingerprint> = emptySet(),
    ) : RpcTrustStore {
        private val pins = MutableStateFlow<Set<PeerFingerprint>?>(initial)
        fun commit(value: Set<PeerFingerprint>) { pins.value = value.toSet() }
        fun failReads() { pins.value = null }
        override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> {
            assertEquals(app, appId)
            assertEquals(this.purpose, purpose)
            return checkNotNull(pins.value) { "Test store snapshot unavailable" }
        }
        override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
            error("The test uses application-owned commits only")
        }
    }

    private class TcpPeer(role: LanRole) {
        val identity = IdentityStore()
        val dials = AtomicInteger()
        private val transport = LoopbackTransport(role, dials)
        val platform = RpcPlatform { settings ->
            check(settings.role == role)
            P2pKit.create {
                settings.configure(this)
                jvmSecureIdentityStore(identity)
                transports {
                    register(object : TransportFactory {
                        override val descriptor = TransportDescriptor.dataOnly(TransportKind.LAN)
                        override fun build(context: TransportContext) = TransportPair(data = transport)
                    })
                }
                networkProvisioning {
                    register(object : NetworkProvisioningFactory {
                        @OptIn(ExperimentalP2pApi::class)
                        override fun build(context: ProvisioningContext): NetworkProvisioningManager =
                            object : NetworkProvisioningManager by JvmProvisioningFactory.build(context) {
                                override suspend fun getManualConnectionInfo(): ManualConnectionInfo? {
                                    val port = context.lanTcpPort() ?: return null
                                    return ManualConnectionInfo(
                                        listOf(TEST_ADDRESS), port, context.appId, context.localPeerId,
                                        context.localDeviceName, context.localFingerprint, context.localPairingQr,
                                    )
                                }
                            }
                    })
                }
            }
        }
    }

    // The real RPC policy still validates the synthetic private address. Only this adapter dials
    // the loopback interface, so this test has no Wi-Fi, multicast, routable socket or port race.
    private class LoopbackTransport(private val role: LanRole, private val dials: AtomicInteger) :
        DataTransport, HasLocalTcpEndpoint {
        override val type = TransportKind.LAN
        override val priority = 1
        private val listener = MutableStateFlow<ServerSocketChannel?>(null)
        override val tcpPort = MutableStateFlow<Int?>(null)

        override suspend fun start(): Result<Unit> {
            if (role == LanRole.Host && listener.value == null) {
                val server = ServerSocketChannel.open()
                try {
                    server.bind(InetSocketAddress(LOOPBACK, 0))
                    tcpPort.value = (server.localAddress as InetSocketAddress).port
                    listener.value = server
                } catch (failure: Throwable) {
                    server.close()
                    throw failure
                }
            }
            return Result.success(Unit)
        }

        override suspend fun stop() {
            val server = listener.value
            listener.value = null
            tcpPort.value = null
            server?.close()
        }

        override suspend fun close() = stop()

        override fun canConnect(peer: InternalPeer): Boolean =
            role == LanRole.DialOnly && peer.transportHints.any { it.type == type && it.host == TEST_ADDRESS }

        override suspend fun connect(peer: InternalPeer): RawConnection {
            val hint = peer.transportHints.single { it.type == type && it.host == TEST_ADDRESS }
            val channel = SocketChannel.open()
            try {
                runInterruptible(Dispatchers.IO) {
                    channel.socket().connect(InetSocketAddress(LOOPBACK, checkNotNull(hint.port)), 2_000)
                }
                dials.incrementAndGet()
                return SocketStream(channel)
            } catch (failure: Throwable) {
                channel.close()
                throw failure
            }
        }

        override fun incomingConnections() = if (role == LanRole.DialOnly) emptyFlow() else flow {
            val server = checkNotNull(listener.first { it != null })
            while (server.isOpen) {
                var accepted: SocketChannel? = null
                try {
                    runInterruptible(Dispatchers.IO) { accepted = server.accept() }
                    emit(SocketStream(checkNotNull(accepted)))
                    accepted = null // The core session now owns the connection.
                } finally {
                    accepted?.close()
                }
            }
        }
    }

    private class SocketStream(private val channel: SocketChannel) : RawConnection {
        override val state = MutableStateFlow(ConnectionState.Connected)
        override suspend fun write(bytes: ByteArray) = runInterruptible(Dispatchers.IO) {
            val buffer = ByteBuffer.wrap(bytes)
            while (buffer.hasRemaining()) channel.write(buffer)
        }

        override fun read() = flow {
            val buffer = ByteBuffer.allocate(4096)
            while (channel.isOpen) {
                buffer.clear()
                val size = runInterruptible(Dispatchers.IO) { channel.read(buffer) }
                if (size < 0) break
                if (size > 0) emit(buffer.array().copyOf(size))
            }
        }

        override suspend fun close() {
            channel.close()
            state.value = ConnectionState.Closed
        }
    }

    private class IdentityStore : JvmSecureIdentityStore {
        private val entries = mutableMapOf<String, ByteArray>()
        @Synchronized override fun read(namespace: String): ByteArray? = entries[namespace]?.copyOf()
        @Synchronized override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray =
            entries.getOrPut(namespace) { value.copyOf() }.copyOf()
        @Synchronized override fun delete(namespace: String): Boolean = entries.remove(namespace)?.let {
            it.fill(0)
            true
        } ?: false
        @Synchronized fun clear() {
            entries.values.forEach { it.fill(0) }
            entries.clear()
        }
    }

    private companion object {
        const val TEST_ADDRESS = "10.0.0.1"
        val LOOPBACK: InetAddress = InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1))
    }
}
