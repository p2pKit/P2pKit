package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.BuildInfo
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.core.protocol.FrameTrace
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.TransportPair
import java.io.File
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.Collections
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

/**
 * Explicit diagnostic entry point, not a normal CI test or an independent peer.
 * Runs unchanged real kits, secure-v2 and JVM LAN socket code. Only socket-option
 * assignment is controlled through existing test factories; no split writes.
 */
@Suppress("DEPRECATION")
internal object ProtocolPingLatency {
    @JvmStatic
    fun main(args: Array<String>) {
        require(args.size == 3)
        val (outputPath, expectedCommit, declaredTree) = args
        require(expectedCommit.matches(Regex("[0-9a-f]{40}")) && declaredTree.matches(Regex("[0-9a-f]{40}")))
        check(BuildInfo.COMMIT == expectedCommit && !BuildInfo.DIRTY)
        verifySource(expectedCommit, declaredTree)
        val output = File(outputPath)
        require(output.isAbsolute && output.canonicalFile == output && output.parentFile.isDirectory)
        check(output.createNewFile()) { "Never overwrite a prior measurement" }
        output.setReadable(false, false)
        output.setWritable(false, false)
        check(output.setReadable(true, true) && output.setWritable(true, true))
        output.appendText("{\"kind\":\"identity\",\"sourceCommit\":\"$expectedCommit\"," +
            "\"declaredSourceTree\":\"$declaredTree\",\"protocol\":\"authenticated-v2\"," +
            "\"topology\":\"same-process-two-kits-ipv4-loopback\",\"warmup\":8,\"retained\":32," +
            "\"javaVersion\":\"${safe(System.getProperty("java.version"))}\"," +
            "\"osName\":\"${safe(System.getProperty("os.name"))}\"," +
            "\"osArch\":\"${safe(System.getProperty("os.arch"))}\"}\n")
        try {
            runBlocking {
                withTimeout(90_000) {
                    listOf(false, true, true, false).forEachIndexed { block, noDelay ->
                        measure(block, noDelay, output)
                    }
                }
            }
            verifySource(expectedCommit, declaredTree)
            output.appendText("{\"kind\":\"terminal\",\"outcome\":\"PASS\",\"blocks\":4}\n")
        } catch (failure: Throwable) {
            output.appendText("{\"kind\":\"terminal\",\"outcome\":\"FAIL\"," +
                "\"errorType\":\"${safe(failure.javaClass.name)}\"}\n")
            throw failure
        }
    }

    private fun verifySource(commit: String, tree: String) {
        fun git(vararg arguments: String): String {
            val process = ProcessBuilder(listOf("git", "--no-optional-locks", "-c", "core.fsmonitor=false") + arguments)
                .redirectError(ProcessBuilder.Redirect.DISCARD).start()
            try {
                check(process.waitFor(5, TimeUnit.SECONDS)) { "Source readback deadline" }
                check(process.exitValue() == 0)
                val bytes = process.inputStream.readNBytes(4097)
                check(bytes.size <= 4096)
                return bytes.toString(Charsets.UTF_8).trim()
            } finally {
                if (process.isAlive) {
                    process.destroyForcibly()
                    check(process.waitFor(5, TimeUnit.SECONDS)) { "Source observer retirement" }
                }
                process.inputStream.close()
                process.errorStream.close()
                process.outputStream.close()
            }
        }
        check(git("status", "--porcelain", "--untracked-files=normal").isEmpty()) { "Full worktree is dirty" }
        check(git("rev-parse", "HEAD") == commit && git("rev-parse", "HEAD^{tree}") == tree)
    }

    private fun safe(value: String): String = value.also {
        require(it.length <= 160 && it.all { char -> char.code in 32..126 && char != '"' && char != '\\' })
    }

    private suspend fun measure(block: Int, noDelay: Boolean, output: File) = coroutineScope {
        val app = AppId("protocol-latency-$block")
        val sockets = Collections.synchronizedList(mutableListOf<OptionSocket>())
        val listeners = Collections.synchronizedList(mutableListOf<ServerSocket>())
        val problems = AtomicInteger()
        val logger = object : P2pLogger {
            override fun debug(message: String) {}
            override fun info(message: String) {}
            override fun warn(message: String, throwable: Throwable?) { problems.incrementAndGet() }
            override fun error(message: String, throwable: Throwable?) { problems.incrementAndGet() }
        }
        fun socket(): OptionSocket = OptionSocket(noDelay).also { sockets.add(it) }
        fun transport(name: String) = JvmLanDataTransport(
            LanServiceRegistration(app, PeerId("$name-registration"), name, Platform.JVM_DESKTOP),
            socketFactory = ::socket,
            serverSocketFactory = {
                object : ServerSocket() {
                    override fun accept(): Socket = socket().also { candidate ->
                        try { implAccept(candidate) } catch (failure: Throwable) { candidate.close(); throw failure }
                    }
                }.also { listeners.add(it) }
            },
            selectedLanAddress = { InetAddress.getByName("127.0.0.1") }
        )
        val discovery = EndpointDiscovery()
        val aliceTransport = transport("initiator")
        val bobTransport = transport("responder")
        val kits = mutableListOf<P2pKit>()
        val collector = PingTraceCollector(40)
        var lease: dev.p2pkit.core.protocol.FrameTraceLease? = null
        var retired: Boolean
        var primary: Throwable? = null
        try {
            fun kit(name: String, data: JvmLanDataTransport, policy: PeerAuthorizationPolicy, pingMillis: Long) =
                P2pKit.create {
                    appId = app
                    deviceName = name
                    jvmSecureIdentityStore(InMemoryTestJvmSecureIdentityStore())
                    security { mode = SecurityMode.AuthenticatedV2(policy) }
                    this.logger = logger
                    keepAlive { pingIntervalMillis = pingMillis; timeoutMillis = 120_000 }
                    transports { register(LatencyFactory(data, if (name == "initiator") discovery else null)) }
                }.also { kits.add(it) }
            val alice = kit("initiator", aliceTransport, PeerAuthorizationPolicy.RejectUnknown, 100)
            val alicePin = checkNotNull(alice.localFingerprint)
            val bob = kit("responder", bobTransport, PeerAuthorizationPolicy.PinnedOnly(setOf(alicePin)), 60_000)
            val bobPin = checkNotNull(bob.localFingerprint)
            bob.start()
            alice.startDiscovery()
            discovery.subscribed()
            val peer = Peer(bob.localPeerId, "responder", Platform.JVM_DESKTOP, setOf(TransportKind.LAN))
            discovery.announce(InternalPeer(peer, listOf(TransportHint(
                TransportKind.LAN, "127.0.0.1", checkNotNull(bobTransport.tcpPort.value)
            ))))
            withTimeout(10_000) { alice.peers.first { list -> list.any { it.id == peer.id } } }
            val waiting = CompletableDeferred<Unit>()
            val incoming = async { bob.incomingSessions.onSubscription { waiting.complete(Unit) }.first() }
            waiting.await()
            val outgoing = withTimeout(10_000) { alice.connect(peer, bobPin) }
            val accepted = withTimeout(10_000) { incoming.await() }
            check(outgoing.peerIdentity.fingerprint == bobPin && accepted.peerIdentity.fingerprint == alicePin)
            check(outgoing.state.value == ConnectionState.Connected &&
                accepted.state.value == ConnectionState.Connected)
            val connectedSockets = synchronized(sockets) { sockets.filter { it.isConnected && !it.isClosed } }
            check(connectedSockets.size == 2)
            connectedSockets.forEach { check(it.requests.get() == 1 && it.tcpNoDelay == noDelay) }
            output.appendText("{\"kind\":\"block\",\"block\":$block,\"tcpNoDelay\":$noDelay," +
                "\"dialReadback\":$noDelay,\"acceptReadback\":$noDelay,\"mutualPinsVerified\":true}\n")
            lease = FrameTrace.installSink(true) { collector.observe(it, System.nanoTime()) }
            withTimeout(15_000) { collector.finished.await() }
            lease.release()
            lease = null
            check(outgoing.state.value == ConnectionState.Connected &&
                accepted.state.value == ConnectionState.Connected)
            connectedSockets.forEach { check(it.requests.get() == 1 && it.tcpNoDelay == noDelay) }
            collector.samples().forEachIndexed { sample, times ->
                output.appendText("{\"kind\":\"sample\",\"block\":$block,\"sample\":$sample," +
                    "\"warmup\":${sample < 8},\"timesNanos\":[${times.joinToString(",") }]," +
                    "\"rttNanos\":${times.last() - times.first()}}\n")
            }
        } catch (failure: Throwable) {
            primary = failure
            throw failure
        } finally {
            lease?.release()
            val failures = mutableListOf<Throwable>()
            withContext(NonCancellable) {
                kits.forEach { kit ->
                    try { withTimeout(15_000) { kit.stop() } } catch (failure: Throwable) { failures.add(failure) }
                }
            }
            retired = failures.isEmpty() && synchronized(sockets) { sockets.all { it.isClosed } } &&
                synchronized(listeners) { listeners.all { it.isClosed } }
            output.appendText("{\"kind\":\"retirement\",\"block\":$block,\"closed\":$retired," +
                "\"warningsOrErrors\":${problems.get()}}\n")
            if (!retired) {
                val cleanup = IllegalStateException("Every exact owned socket/listener/kit must retire")
                failures.forEach(cleanup::addSuppressed)
                val first = primary
                if (first != null) first.addSuppressed(cleanup) else throw cleanup
            }
        }
        check(retired && problems.get() == 0) { "Unexpected SDK diagnostic" }
    }

    private class OptionSocket(private val selected: Boolean) : Socket() {
        val requests = AtomicInteger()
        override fun setTcpNoDelay(on: Boolean) {
            check(on) { "Production transport must request TCP_NODELAY" }
            requests.incrementAndGet()
            super.setTcpNoDelay(selected)
        }
    }

    private class EndpointDiscovery : DiscoveryTransport {
        override val type = TransportKind.LAN
        private val source = MutableSharedFlow<PeerEvent>()
        override val events: Flow<PeerEvent> = source
        suspend fun subscribed() { source.subscriptionCount.first { it > 0 } }
        suspend fun announce(peer: InternalPeer) { source.emit(PeerEvent.Found(peer)) }
        override suspend fun startAdvertising(localPeer: LocalPeerInfo) {}
        override suspend fun stopAdvertising() {}
        override suspend fun startDiscovery() {}
        override suspend fun stopDiscovery() {}
    }

    private class LatencyFactory(private val data: JvmLanDataTransport, private val discovery: DiscoveryTransport?) :
        TransportFactory {
        override val descriptor = if (discovery == null) TransportDescriptor.dataOnly(TransportKind.LAN)
            else TransportDescriptor.dataAndDiscovery(TransportKind.LAN)
        override fun build(context: TransportContext) = TransportPair(data, discovery)
    }
}

/** Single outstanding production PING; responder's own timer is outside the bounded observation window. */
internal class PingTraceCollector(private val count: Int) {
    val finished = CompletableDeferred<Unit>()
    private val expected = listOf(
        "TX type=PING len=0B", "RX type=PING len=0B", "TX type=PONG len=0B", "RX type=PONG len=0B"
    )
    private val result = mutableListOf<List<Long>>()
    private val pending = mutableListOf<Long>()
    private var started = false

    @Synchronized
    fun observe(line: String, nanos: Long) {
        if (finished.isCompleted) return
        try {
            // Installing the observer may intersect an already-started warmup.
            // Never call that partial exchange a sample; start at the next TX.
            if (!started) {
                check(line in expected) { "Unexpected frame before observation boundary" }
                if (line != expected.first()) return
                started = true
            }
            check(line == expected[pending.size]) { "Ambiguous or unexpected protocol trace sequence" }
            check(pending.isEmpty() || nanos >= pending.last())
            pending.add(nanos)
            if (pending.size == 4) {
                check(pending.last() > pending.first())
                result.add(pending.toList())
                pending.clear()
                if (result.size == count) finished.complete(Unit)
            }
        } catch (failure: Throwable) {
            finished.completeExceptionally(failure)
        }
    }

    @Synchronized
    fun samples(): List<List<Long>> {
        check(finished.isCompleted && !finished.isCancelled && pending.isEmpty() && result.size == count)
        return result.toList()
    }
}
