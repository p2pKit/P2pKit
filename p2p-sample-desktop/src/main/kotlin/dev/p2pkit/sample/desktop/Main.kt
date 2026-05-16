package dev.p2pkit.sample.desktop

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import java.util.concurrent.ConcurrentHashMap

/**
 * P2pKit JVM Desktop CLI — the official desktop test harness for v0.2.
 *
 * Usage:
 * ```
 * gradlew :p2p-sample-desktop:run --args="<deviceName> [<appId>] [reconnect=<n>,<delayMs>]"
 * ```
 *
 * All args are optional; `appId` defaults to `p2pkit-desktop-sample` so the
 * sample interops with the Android sample by default. `reconnect=` configures
 * [ReconnectPolicy.Enabled] (locked at kit-construction time per spec §9);
 * without it, reconnect is `Disabled`.
 *
 * Commands at the `>` prompt:
 *
 * - `peers`                       — list currently discovered peers
 * - `sessions`                    — list active sessions with their state
 * - `info` / `state`              — local identity + kit/advertise/discover state + counts
 * - `adv on | adv off`            — toggle advertising
 * - `disc on | disc off`          — toggle discovery
 * - `connect <id-or-name>`        — open a session
 * - `send <text>`                 — broadcast to every active session
 * - `to <id-or-name> <text>`      — targeted send to one peer
 * - `close <id-or-name>`          — close one session
 * - `help`                        — print this list
 * - `quit` / `exit`               — stop the kit and exit
 */
fun main(args: Array<String>) {
    val deviceName = args.getOrNull(0) ?: "Desktop-${System.currentTimeMillis() % 10_000}"
    val rawAppId = args.getOrNull(1)?.takeUnless { it.startsWith("reconnect=") } ?: "p2pkit-desktop-sample"
    val appId = AppId(rawAppId)
    val reconnectArg = args.firstOrNull { it.startsWith("reconnect=") }
    val reconnect = parseReconnect(reconnectArg)

    println("[P2pKit CLI] deviceName=$deviceName  appId=${appId.value}  reconnect=${reconnect.describe()}")

    val p2p = P2pKit.create {
        this.appId = appId
        this.deviceName = deviceName
        transports { lan() }
        lifecycle { reconnectPolicy = reconnect }
        logger = StdErrLogger
    }
    val advertising = StateLatch()
    val discovering = StateLatch()

    val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    val sessions = ConcurrentHashMap<String, P2pSession>()

    p2p.peers
        .onEach { peers ->
            println("[peers] ${peers.size}: ${peers.joinToString { "${it.name}(${it.id.value.take(8)})" }}")
        }
        .launchIn(scope)

    p2p.incomingSessions
        .onEach { session ->
            println("[incoming] from ${session.peer.name} (${session.peer.id.value.take(8)})")
            sessions[session.peer.id.value] = session
            wireIncoming(session, scope)
            scope.launch {
                session.state.collect { st -> println("[state] ${session.peer.name} → $st") }
            }
        }
        .launchIn(scope)

    runBlocking {
        try {
            p2p.startAdvertising(); advertising.set(true)
            p2p.startDiscovery();   discovering.set(true)
        } catch (e: Throwable) {
            System.err.println("Failed to start: ${e.message}")
            return@runBlocking
        }

        println("Ready. Type 'help' for commands.")
        repl(p2p, scope, sessions, advertising, discovering)

        println("Stopping…")
        p2p.stop()
        scope.cancel()
    }
}

private fun parseReconnect(arg: String?): ReconnectPolicy {
    if (arg == null) return ReconnectPolicy.Disabled
    val payload = arg.removePrefix("reconnect=")
    val parts = payload.split(',')
    if (parts.size != 2) {
        System.err.println("[p2pkit WARN] ignoring malformed reconnect arg '$arg' (expected reconnect=<n>,<delayMs>)")
        return ReconnectPolicy.Disabled
    }
    val attempts = parts[0].toIntOrNull()?.takeIf { it >= 1 }
    val delay = parts[1].toLongOrNull()?.takeIf { it >= 0L }
    if (attempts == null || delay == null) {
        System.err.println("[p2pkit WARN] ignoring malformed reconnect arg '$arg' (n must be a positive int, delayMs a non-negative long)")
        return ReconnectPolicy.Disabled
    }
    return ReconnectPolicy.Enabled(maxAttempts = attempts, retryDelayMillis = delay)
}

private fun ReconnectPolicy.describe(): String = when (this) {
    is ReconnectPolicy.Disabled -> "Disabled"
    is ReconnectPolicy.Enabled -> "Enabled(maxAttempts=$maxAttempts, retryDelayMillis=$retryDelayMillis)"
}

private suspend fun repl(
    p2p: P2pKit,
    scope: CoroutineScope,
    sessions: ConcurrentHashMap<String, P2pSession>,
    advertising: StateLatch,
    discovering: StateLatch
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

            "info", "state" -> printInfo(p2p, sessions, advertising, discovering)

            "adv" -> {
                when (arg) {
                    "on"  -> scope.launch {
                        runCatching { p2p.startAdvertising() }
                            .onSuccess { advertising.set(true); println("advertising on") }
                            .onFailure { System.err.println("startAdvertising failed: ${it.message}") }
                    }
                    "off" -> scope.launch {
                        runCatching { p2p.stopAdvertising() }
                            .onSuccess { advertising.set(false); println("advertising off") }
                            .onFailure { System.err.println("stopAdvertising failed: ${it.message}") }
                    }
                    else  -> println("usage: adv on|off")
                }
            }

            "disc" -> {
                when (arg) {
                    "on"  -> scope.launch {
                        runCatching { p2p.startDiscovery() }
                            .onSuccess { discovering.set(true); println("discovery on") }
                            .onFailure { System.err.println("startDiscovery failed: ${it.message}") }
                    }
                    "off" -> scope.launch {
                        runCatching { p2p.stopDiscovery() }
                            .onSuccess { discovering.set(false); println("discovery off") }
                            .onFailure { System.err.println("stopDiscovery failed: ${it.message}") }
                    }
                    else  -> println("usage: disc on|off")
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
                        scope.launch {
                            session.state.collect { st -> println("[state] ${session.peer.name} → $st") }
                        }
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

private fun printInfo(
    p2p: P2pKit,
    sessions: ConcurrentHashMap<String, P2pSession>,
    advertising: StateLatch,
    discovering: StateLatch
) {
    println("---")
    println("appId            ${p2p.appId.value}")
    println("deviceName       ${p2p.localDeviceName}")
    println("localPeerId      ${p2p.localPeerId.value}")
    println("kit state        ${p2p.state.value::class.simpleName}")
    println("advertising      ${advertising.value()}")
    println("discovering      ${discovering.value()}")
    println("peers known      ${p2p.peers.value.size}")
    println("active sessions  ${sessions.size}")
    println("---")
}

private fun printHelp() {
    println(
        """
        Commands:
          peers                       — list discovered peers
          sessions                    — list active sessions
          info | state                — local identity + kit/adv/disc state + counts
          adv on | adv off            — toggle advertising
          disc on | disc off          — toggle discovery
          connect <id-or-name>        — open a session
          send <text>                 — broadcast to every active session (room)
          to <id-or-name> <text>      — send to one peer
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

/**
 * Simple atomic flag used to mirror the user's start/stop intent for
 * advertising and discovery, since the SDK doesn't expose those flags
 * directly (start/stop are commands, not observable state).
 */
private class StateLatch {
    @Volatile private var on = false
    fun set(value: Boolean) { on = value }
    fun value(): Boolean = on
}
