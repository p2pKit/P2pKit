package dev.p2pkit.sample.desktop

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import java.util.concurrent.ConcurrentHashMap

/**
 * Minimal P2pKit CLI sample with room-style broadcast.
 *
 * Usage:
 * ```
 * gradlew :p2p-sample-desktop:run --args="<deviceName> <appId>"
 * ```
 *
 * Both arguments are optional. Once running, type commands at the `>` prompt:
 *
 * - `peers`               — list currently discovered peers
 * - `connect <id-prefix>` — open a session to a peer whose id starts with `<id-prefix>`
 *                           (8 chars is usually enough); a plain name also works
 * - `send <text>`         — broadcast a text message to **every** active session
 *                           (room semantics — if only one peer is connected, this
 *                            sends to just that one)
 * - `to <id-or-name> <text>` — targeted send to a single peer
 * - `sessions`            — list active sessions
 * - `close <id-prefix>`   — close a session
 * - `help`                — print the command list
 * - `quit` / `exit`       — close everything and exit
 */
fun main(args: Array<String>) {
    val deviceName = args.getOrNull(0) ?: "Desktop-${System.currentTimeMillis() % 10_000}"
    val appId = AppId(args.getOrNull(1) ?: "p2pkit-desktop-sample")

    println("[P2pKit CLI] deviceName=$deviceName  appId=${appId.value}")

    val p2p = P2pKit.create {
        this.appId = appId
        this.deviceName = deviceName
        transports { lan() }
        logger = StdErrLogger
    }

    val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    val sessions = ConcurrentHashMap<String, P2pSession>()

    p2p.peers
        .onEach { peers ->
            // Print only when the set changes; the public flow already deduplicates
            // on `Peer` identity, so any emission is meaningful.
            println("[peers] ${peers.size}: ${peers.joinToString { "${it.name}(${it.id.value.take(8)})" }}")
        }
        .launchIn(scope)

    p2p.incomingSessions
        .onEach { session ->
            println("[incoming] from ${session.peer.name} (${session.peer.id.value.take(8)})")
            sessions[session.peer.id.value] = session
            wireIncoming(session, scope)
        }
        .launchIn(scope)

    runBlocking {
        try {
            p2p.startAdvertising()
            p2p.startDiscovery()
        } catch (e: Throwable) {
            System.err.println("Failed to start: ${e.message}")
            return@runBlocking
        }

        println("Ready. Type 'help' for commands.")
        repl(p2p, scope, sessions)

        println("Stopping…")
        p2p.stop()
        scope.cancel()
    }
}

private suspend fun repl(
    p2p: P2pKit,
    scope: CoroutineScope,
    sessions: ConcurrentHashMap<String, P2pSession>
) {
    val reader = System.`in`.bufferedReader()
    while (true) {
        print("> ")
        System.out.flush()
        val line = reader.readLine()?.trim() ?: break
        if (line.isEmpty()) continue

        val (cmd, arg) = line.split(' ', limit = 2).let {
            it[0] to (it.getOrNull(1)?.trim().orEmpty())
        }

        when (cmd) {
            "help" -> printHelp()

            "peers" -> {
                val peers = p2p.peers.value
                if (peers.isEmpty()) println("(no peers yet)") else peers.forEach(::printPeer)
            }

            "sessions" -> {
                if (sessions.isEmpty()) {
                    println("(no active sessions)")
                } else {
                    sessions.values.forEach {
                        println("  ${it.peer.name} (${it.peer.id.value.take(8)})  state=${it.state.value}")
                    }
                }
            }

            "connect" -> {
                if (arg.isEmpty()) {
                    println("usage: connect <peer-id-prefix-or-name>")
                    continue
                }
                val match = findPeer(p2p, arg)
                if (match == null) {
                    println("no peer matching '$arg'")
                    continue
                }
                scope.launch {
                    try {
                        val session = p2p.connect(match)
                        sessions[session.peer.id.value] = session
                        wireIncoming(session, scope)
                        println("connected to ${session.peer.name} (${session.peer.id.value.take(8)})")
                    } catch (e: Throwable) {
                        System.err.println("connect failed: ${e.message}")
                    }
                }
            }

            "send" -> {
                if (arg.isEmpty()) {
                    println("usage: send <text>  (broadcasts to every active session)")
                    continue
                }
                val snapshot = sessions.values.toList()
                if (snapshot.isEmpty()) {
                    println("no active session; run `connect` first")
                    continue
                }
                val msg = P2pMessage.Text(arg)
                println("[broadcast → ${snapshot.size}] $arg")
                for (session in snapshot) {
                    scope.launch {
                        runCatching { session.send(msg) }.onFailure {
                            System.err.println("send to ${session.peer.name} failed: ${it.message}")
                        }
                    }
                }
            }

            "to" -> {
                val space = arg.indexOf(' ')
                if (space <= 0 || space == arg.length - 1) {
                    println("usage: to <peer-id-prefix-or-name> <text>")
                    continue
                }
                val target = arg.substring(0, space).trim()
                val text = arg.substring(space + 1).trim()
                if (text.isEmpty()) {
                    println("usage: to <peer-id-prefix-or-name> <text>")
                    continue
                }
                val session = sessions.values.firstOrNull { matches(it.peer, target) }
                if (session == null) {
                    println("no active session matching '$target'")
                    continue
                }
                println("[to ${session.peer.name}] $text")
                scope.launch {
                    runCatching { session.send(P2pMessage.Text(text)) }.onFailure {
                        System.err.println("send to ${session.peer.name} failed: ${it.message}")
                    }
                }
            }

            "close" -> {
                if (arg.isEmpty()) {
                    println("usage: close <peer-id-prefix-or-name>")
                    continue
                }
                val session = sessions.values.firstOrNull { matches(it.peer, arg) }
                if (session == null) {
                    println("no active session matching '$arg'")
                    continue
                }
                scope.launch {
                    runCatching { session.close() }
                    sessions.remove(session.peer.id.value)
                    println("closed session with ${session.peer.name}")
                }
            }

            "quit", "exit" -> return

            else -> println("unknown command '$cmd' — type `help`")
        }
    }
}

private fun printHelp() {
    println(
        """
        Commands:
          peers                       — list discovered peers
          connect <id-or-name>        — open a session
          send <text>                 — broadcast to every active session (room)
          to <id-or-name> <text>      — send to one peer
          sessions                    — list active sessions
          close <id-or-name>          — close a session
          help                        — show this list
          quit | exit                 — stop and exit
        """.trimIndent()
    )
}

private fun printPeer(peer: Peer) {
    println("  ${peer.id.value.take(8)}…  ${peer.name}  [${peer.platform}]")
}

private fun findPeer(p2p: P2pKit, query: String): Peer? =
    p2p.peers.value.firstOrNull { matches(it, query) }

private fun matches(peer: Peer, query: String): Boolean =
    peer.id.value.startsWith(query) || peer.name.equals(query, ignoreCase = true)

private fun wireIncoming(session: P2pSession, scope: CoroutineScope) {
    session.incoming
        .onEach { msg ->
            when (msg) {
                is P2pMessage.Text -> println("[${session.peer.name}] ${msg.value}")
                is P2pMessage.Binary -> println("[${session.peer.name}] <binary ${msg.bytes.size}B>")
            }
        }
        .launchIn(scope)
}

private object StdErrLogger : P2pLogger {
    override fun debug(message: String) = Unit
    override fun info(message: String) = System.err.println("[p2pkit] $message")
    override fun warn(message: String, throwable: Throwable?) {
        System.err.println("[p2pkit WARN] $message" + (throwable?.let { " (${it.message})" } ?: ""))
    }
    override fun error(message: String, throwable: Throwable?) {
        System.err.println("[p2pkit ERROR] $message" + (throwable?.let { " (${it.message})" } ?: ""))
    }
}
