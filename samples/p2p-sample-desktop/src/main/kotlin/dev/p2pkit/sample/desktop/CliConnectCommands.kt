package dev.p2pkit.sample.desktop

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.sample.diagnostics.SampleConsole
import dev.p2pkit.sample.diagnostics.consoleId
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/** The REPL's discovery-connect route, including its local duplicate-attempt guards. */
internal class CliConnectCommands(
    private val kit: P2pKit,
    private val scope: CoroutineScope,
    private val sessions: Map<String, P2pSession>,
    private val pendingConnects: CliPendingConnects,
    private val onAttempt: (Peer) -> Unit,
    private val onConnected: (P2pSession) -> Unit,
    private val output: (String) -> Unit = ::println,
    private val error: (String) -> Unit = { System.err.println(it) }
) {
    fun execute(command: String, input: String): Job? {
        require(command == "connect" || command == "connect-pinned")
        val pin = if (command == "connect-pinned") parsePinnedConnect(kit, input) else null
        if (command == "connect-pinned" && pin == null) {
            output(PINNED_CONNECT_USAGE)
            output("QR must be canonical and for this AppId; obtain it from the intended peer, not discovery.")
            return null
        }
        if (input.isEmpty()) {
            output("usage: connect <peer-id-prefix-or-name>")
            return null
        }
        val peerMatches = kit.peers.value.filter { matches(it, pin?.selector ?: input) }
        if (peerMatches.isEmpty()) {
            output("no peer matching <input omitted>")
            return null
        }
        if (peerMatches.size > 1) {
            output("ambiguous peer <input omitted>: ${peerMatches.joinToString { it.consoleId }}")
            return null
        }
        val peer = peerMatches.single()
        val peerId = peer.id.value
        val existing = sessions[peerId]
        if (pin == null && existing != null && existing.state.value == ConnectionState.Connected) {
            output("already connected to ${peer.consoleId}")
            return null
        }
        val ownsPendingMarker = pendingConnects.add(peerId)
        if (pin == null && !ownsPendingMarker) {
            output("already connecting to ${peer.consoleId}")
            return null
        }
        // An explicit pin must reach the SDK even when an unpinned auto-mesh/user
        // attempt is pending. The SDK joins that attempt and checks this caller's
        // pin (or retries a differently-authorized failure); a UI guard cannot.
        var admittedSession: P2pSession? = null
        return scope.launch {
            try {
                onAttempt(peer)
                val session = if (pin != null) connectPinnedPeer(kit, peer, pin) else kit.connect(peer)
                admittedSession = session
                // The caller registers collectors once per SDK session, including
                // when both a pending owner and a pinned waiter obtain that session.
                onConnected(session)
                output("connected to ${session.peer.consoleId}")
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Throwable) {
                error("connect failed: ${SampleConsole.failure(failure)}")
            }
        }.also { job ->
            // A waiter must not remove another attempt's marker. A completion
            // handler also releases our own marker if the scope was already
            // cancelled and the coroutine body never got a chance to start.
            job.invokeOnCompletion {
                pendingConnects.complete(peerId, ownsPendingMarker, admittedSession)
            }
        }
    }
}
