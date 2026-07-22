package dev.p2pkit.sample.desktop

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.ExplicitSecurityRisk
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.sendFile
import dev.p2pkit.core.protocol.FrameTrace
import dev.p2pkit.provisioning.desktop.jvm
import dev.p2pkit.transport.lan.JvmLanDiag
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.io.asSink
import java.io.File
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
 * - `info` / `state`              — local identity + kit/advertise/discover/mesh state + counts
 * - `adv on | adv off`            — toggle advertising
 * - `disc on | disc off`          — toggle discovery
 * - `mesh on | mesh off`          — toggle auto-mesh (auto-connect to all discovered peers,
 *                                   using a lexicographic tie-break so two peers never race
 *                                   into duplicate sessions)
 * - `connect <id-or-name>`        — open a session
 * - `send <text>`                 — broadcast to every active session
 * - `to <id-or-name> <text>`      — targeted send to one peer
 * - `close <id-or-name>`          — close one session
 * - `manual <host>:<port> <fingerprint>` — connect by IP without mDNS;
 *                                   uses the JVM provisioning module to register
 *                                   a synthetic peer and then dials it
 * - `sendfile <id-or-name> <path>` — stream a file from disk to one peer
 * - `offers`                      — list incoming file offers awaiting consent
 * - `accept <offer-id-prefix>`    — accept an offer if it meets local storage limits
 * - `reject <offer-id-prefix>`    — reject an incoming offer
 * - `help`                        — print this list
 * - `quit` / `exit`               — stop the kit and exit
 *
 * Incoming file offers remain pending until the operator explicitly accepts
 * or rejects them. Accepted files are subject to a 50 MiB per-file limit and
 * a 1 MiB free-space reserve, and are saved under
 * `<user.home>/.p2pkit/incoming/<sender-name>/<filename>`. If the destination
 * name is already taken the file lands in `<name> (n).<ext>` instead of
 * overwriting. State transitions print as `[file …]` lines.
 */
@OptIn(ExplicitSecurityRisk::class)
fun main(args: Array<String>) {
    // Filter the optional `reconnect=` token from the positional args before
    // assigning device name, mirroring the appId guard below — otherwise
    // `--args="reconnect=10,1500"` advertised a device literally named
    // "reconnect=10,1500" (AUDIT-2026-06 fix).
    val rawName = args.getOrNull(0)?.trim()?.takeUnless { it.startsWith("reconnect=") }.orEmpty()
    val deviceName = rawName.ifEmpty { "Desktop-${System.currentTimeMillis() % 10_000}" }
    val rawAppId = args.getOrNull(1)?.trim()?.takeUnless { it.startsWith("reconnect=") || it.isEmpty() }
        ?: "p2pkit-desktop-sample"
    val appId = AppId(rawAppId)
    val reconnectArg = args.firstOrNull { it.startsWith("reconnect=") }
    val reconnect = parseReconnect(reconnectArg)

    // LAN forensic trace (Issue #2). ON by default in this harness — every
    // P2pKitLAN line goes to stdout (greppable). Pass `trace=off` to silence,
    // or `trace=frames` to additionally log every byte chunk on the data socket.
    when (args.firstOrNull { it.startsWith("trace=") }?.substringAfter("=")) {
        "off" -> { JvmLanDiag.enabled = false; FrameTrace.enabled = false }
        "frames" -> {
            JvmLanDiag.enabled = true; JvmLanDiag.traceFrames = true; FrameTrace.enabled = true
        }
        else -> { JvmLanDiag.enabled = true; FrameTrace.enabled = true }
    }

    println("[P2pKit CLI] deviceName=$deviceName  appId=${appId.value}  reconnect=${reconnect.describe()}")
    println(
        "[P2pKit CLI] trace: lan(interfaces/conn)=${JvmLanDiag.enabled} " +
            "frameTypes=${FrameTrace.enabled} bytes=${JvmLanDiag.traceFrames} " +
            "(grep 'P2pKitLAN' + 'P2pKitFRAME'; pass trace=off / trace=frames to change)"
    )
    System.err.println(
        "[P2pKit CLI] DEVELOPMENT SECURITY: accepting any authenticated same-AppId peer; " +
            "identity storage is process-local and must be replaced in production."
    )

    val p2p = P2pKit.create {
        this.appId = appId
        this.deviceName = deviceName
        jvmSecureIdentityStore(DevelopmentOnlyInMemorySecureIdentityStore())
        security {
            mode = SecurityMode.AuthenticatedV2(
                PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp
            )
        }
        transports { lan() }
        lifecycle { reconnectPolicy = reconnect }
        networkProvisioning { jvm() }
        logger = StdErrLogger
    }
    val advertising = StateLatch()
    val discovering = StateLatch()
    val autoMesh = MutableStateFlow(true)

    val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    val sessions = ConcurrentHashMap<String, P2pSession>()
    // Peers with an in-flight `kit.connect` initiated by either auto-mesh
    // or the user-typed `connect <name>` command. Both paths consult this
    // set before launching their own coroutine, so a manual tap during
    // auto-mesh's in-flight window doesn't kick off a second concurrent
    // connect attempt for the same peer. The SDK still dedupes either way,
    // but the local guard keeps the CLI output one-clean per session.
    val pendingConnects: MutableSet<String> = java.util.concurrent.ConcurrentHashMap.newKeySet()
    val pendingFileOffers = ConcurrentHashMap<String, P2pFileOffer>()
    // AUDIT-2026-06 (B-G9-samples-desktop-ios-10): session ids whose collectors
    // are already wired. p2p.connect() is idempotent and can return the SAME
    // P2pSession instance (e.g. `connect` typed while that session is still
    // Connecting/Reconnecting); without this guard the CLI wired a second set
    // of incoming/state collectors onto the instance and every message and
    // state change printed twice for the rest of the run. See registerSession.
    val wiredSessionIds: MutableSet<String> = java.util.concurrent.ConcurrentHashMap.newKeySet()

    p2p.peers
        .onEach { peers ->
            println("[peers] ${peers.size}: ${peers.joinToString { "${it.name.sanitizedForTerminal()}(${it.id.value.take(8)})" }}")
        }
        .launchIn(scope)

    p2p.incomingSessions
        .onEach { session ->
            println("[incoming] from ${session.peer.name.sanitizedForTerminal()} (${session.peer.id.value.take(8)})")
            registerSession(session, scope, sessions, wiredSessionIds, pendingFileOffers)
        }
        .launchIn(scope)

    // Auto-mesh: when on, initiate connect to every newly-discovered peer
    // when our local PeerId is lexicographically less than theirs. The
    // tie-break guarantees exactly one side per pair initiates, avoiding the
    // simultaneous-open race.
    scope.launch {
        combine(autoMesh, p2p.peers) { enabled, peers -> enabled to peers }
            .collect { (enabled, peers) ->
                if (!enabled) return@collect
                val myId = p2p.localPeerId.value
                for (peer in peers) {
                    if (sessions.containsKey(peer.id.value)) continue
                    if (myId >= peer.id.value) continue
                    if (!pendingConnects.add(peer.id.value)) continue
                    System.err.println("[p2pkit] auto-mesh: initiating connect to ${peer.name.sanitizedForTerminal()}")
                    scope.launch {
                        try {
                            runCatching {
                                val s = p2p.connect(peer)
                                registerSession(s, scope, sessions, wiredSessionIds, pendingFileOffers)
                            }.onFailure {
                                System.err.println("[p2pkit WARN] auto-mesh connect to ${peer.name.sanitizedForTerminal()} failed: ${it.message}")
                            }
                        } finally {
                            pendingConnects.remove(peer.id.value)
                        }
                    }
                }
            }
    }

    runBlocking {
        try {
            p2p.startAdvertising(); advertising.set(true)
            p2p.startDiscovery();   discovering.set(true)
        } catch (e: Throwable) {
            System.err.println("Failed to start: ${e.message}")
            runCatching { p2p.stop() }
            scope.cancel()
            return@runBlocking
        }

        println("Ready. Type 'help' for commands.")
        repl(
            p2p,
            scope,
            sessions,
            pendingConnects,
            wiredSessionIds,
            pendingFileOffers,
            advertising,
            discovering,
            autoMesh
        )

        println("Stopping…")
        rejectPendingOffers(pendingFileOffers, "receiver stopped")
        runCatching { p2p.stop() }.onFailure {
            System.err.println("kit.stop() failed: ${it.message}")
        }
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
    // Shared with the auto-mesh loop in main() so both paths consult the
    // same in-flight-connect set. The SDK dedupes either way, but routing
    // both through the same gate keeps the CLI output clean.
    pendingConnects: MutableSet<String>,
    // AUDIT-2026-06 (B-G9-samples-desktop-ios-10): shared wired-collector set,
    // see registerSession.
    wiredSessionIds: MutableSet<String>,
    pendingFileOffers: ConcurrentHashMap<String, P2pFileOffer>,
    advertising: StateLatch,
    discovering: StateLatch,
    autoMesh: MutableStateFlow<Boolean>
) {
    val reader = System.`in`.bufferedReader()
    while (true) {
        print("> ")
        System.out.flush()
        val rawLine = reader.readLine()
        if (rawLine == null) {
            // EOF — Ctrl+D, pipe closed, or stdin redirected from a finished
            // file. Treat as graceful exit so the kit teardown still runs.
            println()
            println("(stdin closed — exiting)")
            return
        }
        val line = rawLine.trim()
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
                        println("  ${it.peer.name.sanitizedForTerminal()} (${it.peer.id.value.take(8)})  state=${it.state.value}")
                    }
                }
            }

            "info", "state" -> printInfo(p2p, sessions, advertising, discovering, autoMesh)

            "manual" -> {
                val manualParts = arg.trim().split(Regex("\\s+"), limit = 2)
                val endpoint = manualParts.getOrNull(0).orEmpty()
                val fingerprintText = manualParts.getOrNull(1).orEmpty()
                val expectedFingerprint = PeerFingerprint.parseOrNull(fingerprintText)
                if (expectedFingerprint == null) {
                    println("usage: manual <host>:<port> <full-p2f1-fingerprint>")
                    continue
                }
                // AUDIT-2026-06 (A-G9-samples-desktop-ios-18): the input used to
                // be split at the FIRST colon, which truncated IPv6 literals
                // (e.g. `fe80::1:9000`) at their first colon even though the
                // host check below claims IPv6 support. Split at the LAST colon
                // instead, and accept the unambiguous `[v6-literal]:port`
                // bracket form too.
                val sep = endpoint.lastIndexOf(':')
                val host = (if (sep >= 0) endpoint.substring(0, sep) else endpoint)
                    .trim()
                    .removeSurrounding("[", "]")
                val portToken = if (sep >= 0) endpoint.substring(sep + 1).trim() else null
                val port = portToken?.toIntOrNull()
                if (host.isEmpty()) {
                    println("usage: manual <host>:<port>  (host is empty)")
                    continue
                }
                if (port == null || port !in 1..65_535) {
                    println("usage: manual <host>:<port>  (port must be 1..65535, got '$portToken')")
                    continue
                }
                // Light host-form sanity check — reject obvious garbage so the
                // user sees a useful message instead of waiting on a connect
                // timeout. Allows IPv4/IPv6 numerics and DNS hostnames.
                if (!host.all { it.isLetterOrDigit() || it in ".:_-" }) {
                    println("manual: host contains invalid characters: '$host'")
                    continue
                }
                scope.launch {
                    @OptIn(ExperimentalP2pApi::class)
                    val synthetic = runCatching {
                        p2p.networkProvisioning.createManualPeer(
                            host,
                            port,
                            expectedFingerprint
                        )
                    }
                        .getOrElse {
                            System.err.println("manual createManualPeer failed: ${it.message}")
                            return@launch
                        }
                    runCatching {
                        val session = p2p.connect(synthetic)
                        registerSession(session, scope, sessions, wiredSessionIds, pendingFileOffers)
                        println("connected manual peer ${session.peer.name.sanitizedForTerminal()}")
                    }.onFailure {
                        System.err.println("manual connect failed: ${it.message}")
                    }
                }
            }

            "mesh" -> {
                when (arg) {
                    "on" -> {
                        autoMesh.value = true
                        println("auto-mesh on")
                    }
                    "off" -> {
                        autoMesh.value = false
                        println("auto-mesh off")
                    }
                    else -> println("usage: mesh on|off  (current: ${if (autoMesh.value) "on" else "off"})")
                }
            }

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
                val peerId = match.id.value
                val existing = sessions[peerId]
                if (existing != null && existing.state.value == ConnectionState.Connected) {
                    println("already connected to ${match.name.sanitizedForTerminal()}")
                    continue
                }
                if (!pendingConnects.add(peerId)) {
                    println("already connecting to ${match.name.sanitizedForTerminal()}")
                    continue
                }
                scope.launch {
                    try {
                        val session = p2p.connect(match)
                        // AUDIT-2026-06 (B-G9-samples-desktop-ios-10): for a peer in
                        // Connecting/Handshaking/Reconnecting, connect() dedupes
                        // onto the SAME session instance; registerSession skips
                        // re-wiring collectors on an already-wired id so output
                        // doesn't start printing twice.
                        registerSession(session, scope, sessions, wiredSessionIds, pendingFileOffers)
                        println("connected to ${session.peer.name.sanitizedForTerminal()} (${session.peer.id.value.take(8)})")
                    } catch (e: Throwable) {
                        System.err.println("connect failed: ${e.message}")
                    } finally {
                        pendingConnects.remove(peerId)
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
                val live = snapshot.filter { it.state.value == ConnectionState.Connected }
                if (live.isEmpty()) {
                    println("no Connected sessions (have ${snapshot.size} session(s) in " +
                        "non-Connected states: ${snapshot.joinToString { "${it.peer.name.sanitizedForTerminal()}=${it.state.value}" }})")
                    continue
                }
                val skipped = snapshot - live.toSet()
                if (skipped.isNotEmpty()) {
                    println("skipping non-Connected: ${skipped.joinToString { "${it.peer.name.sanitizedForTerminal()}(${it.state.value})" }}")
                }
                val msg = P2pMessage.Text(arg)
                println("[broadcast → ${live.size}] $arg")
                for (session in live) {
                    scope.launch {
                        runCatching { session.send(msg) }.onFailure {
                            System.err.println("send to ${session.peer.name.sanitizedForTerminal()} failed: ${it.message}")
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
                if (session.state.value != ConnectionState.Connected) {
                    println("session with ${session.peer.name.sanitizedForTerminal()} is not Connected (state=${session.state.value}) — send skipped")
                    continue
                }
                println("[to ${session.peer.name.sanitizedForTerminal()}] $text")
                scope.launch {
                    runCatching { session.send(P2pMessage.Text(text)) }.onFailure {
                        System.err.println("send to ${session.peer.name.sanitizedForTerminal()} failed: ${it.message}")
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
                    runCatching { session.close() }.onFailure {
                        System.err.println("close ${session.peer.name.sanitizedForTerminal()} failed: ${it.message}")
                    }
                    sessions.remove(session.peer.id.value)
                    println("closed session with ${session.peer.name.sanitizedForTerminal()}")
                }
            }

            "sendfile" -> {
                val space = arg.indexOf(' ')
                if (space <= 0 || space == arg.length - 1) {
                    println("usage: sendfile <peer-id-prefix-or-name> <path>")
                    continue
                }
                val target = arg.substring(0, space).trim()
                val rawPath = arg.substring(space + 1).trim().trim('"')
                if (rawPath.isEmpty()) {
                    println("usage: sendfile <peer-id-prefix-or-name> <path>")
                    continue
                }
                val file = File(rawPath)
                if (!file.exists() || !file.isFile) {
                    println("file not found or not a regular file: ${file.absolutePath}")
                    continue
                }
                if (!file.canRead()) {
                    println("file is not readable (check permissions): ${file.absolutePath}")
                    continue
                }
                if (file.length() == 0L) {
                    println("file is empty (0 bytes), nothing to send: ${file.absolutePath}")
                    continue
                }
                val session = sessions.values.firstOrNull { matches(it.peer, target) }
                if (session == null) {
                    println("no active session matching '$target'")
                    continue
                }
                if (session.state.value != ConnectionState.Connected) {
                    println("session with ${session.peer.name.sanitizedForTerminal()} is not Connected (state=${session.state.value}) — sendfile skipped")
                    continue
                }
                println("[file → ${session.peer.name.sanitizedForTerminal()}] sending ${file.name} (${file.length()}B)")
                scope.launch {
                    runCatching { session.sendFile(file) }
                        .onSuccess { transfer ->
                            scope.launch {
                                transfer.state.collect { st ->
                                    // AUDIT-2026-06 (B-G9-samples-desktop-ios-11): a Failed
                                    // state can embed the remote peer's reject
                                    // reason — sanitize before printing.
                                    println("[file → ${session.peer.name.sanitizedForTerminal()} ${file.name}] ${st.toString().sanitizedForTerminal()}")
                                }
                            }
                        }
                        .onFailure { System.err.println("sendfile failed: ${it.message}") }
                }
            }

            "offers" -> {
                val offers = pendingFileOffers.values.sortedBy { it.id }
                if (offers.isEmpty()) {
                    println("(no pending file offers)")
                } else {
                    offers.forEach { offer ->
                        println(
                            "  ${offer.id.take(8)}…  ${offer.name.sanitizedForTerminal()} " +
                                "(${offer.sizeBytes}B) from ${offer.peer.name.sanitizedForTerminal()}"
                        )
                    }
                }
            }

            "accept", "reject" -> {
                if (arg.isEmpty()) {
                    println("usage: $cmd <offer-id-prefix>")
                    continue
                }
                val matches = pendingFileOffers.values
                    .filter { it.id == arg || it.id.startsWith(arg) }
                    .sortedBy { it.id }
                if (matches.isEmpty()) {
                    println("no pending file offer matching '$arg'")
                    continue
                }
                if (matches.size > 1) {
                    println("ambiguous offer id '$arg': ${matches.joinToString { it.id.take(8) }}")
                    continue
                }
                val offer = matches.single()
                if (!pendingFileOffers.remove(offer.id, offer)) {
                    println("offer ${offer.id.take(8)} is no longer pending")
                    continue
                }
                scope.launch {
                    if (cmd == "accept") {
                        acceptIncomingFile(offer)
                    } else {
                        runCatching { offer.reject("rejected by receiver") }
                            .onSuccess {
                                println(
                                    "[file ← ${offer.peer.name.sanitizedForTerminal()}] " +
                                        "rejected ${offer.name.sanitizedForTerminal()}"
                                )
                            }
                            .onFailure {
                                System.err.println(
                                    "[file ← ${offer.peer.name.sanitizedForTerminal()}] " +
                                        "reject failed: ${it.message}"
                                )
                            }
                    }
                }
            }

            "quit", "exit" -> return

            else -> println("unknown command '$cmd' — type `help`")
        }
    }
}

private suspend fun printInfo(
    p2p: P2pKit,
    sessions: ConcurrentHashMap<String, P2pSession>,
    advertising: StateLatch,
    discovering: StateLatch,
    autoMesh: MutableStateFlow<Boolean>
) {
    println("---")
    println("appId            ${p2p.appId.value}")
    println("deviceName       ${p2p.localDeviceName}")
    println("localPeerId      ${p2p.localPeerId.value}")
    println("kit state        ${p2p.state.value::class.simpleName}")
    println("advertising      ${advertising.value()}")
    println("discovering      ${discovering.value()}")
    println("auto-mesh        ${autoMesh.value}")
    println("peers known      ${p2p.peers.value.size}")
    println("active sessions  ${sessions.size}")
    // printInfo is suspend and called from the suspend repl(); calling the
    // suspend API directly avoids a runBlocking nested inside the REPL's
    // outer runBlocking (AUDIT-2026-06 fix).
    val info = p2p.networkProvisioning.getManualConnectionInfo()
    if (info != null) {
        println("manual host(s)   ${info.hostAddresses.joinToString(", ")}")
        println("manual port      ${info.port}")
    } else {
        println("manual info      (none — provisioning not configured or no LAN port)")
    }
    println("---")
}

private fun printHelp() {
    println(
        """
        Commands:
          peers                              — list discovered peers
          sessions                           — list active sessions
          info | state                       — local identity + kit/adv/disc/mesh state + counts
          adv on | adv off                   — toggle advertising
          disc on | disc off                 — toggle discovery
          mesh on | mesh off                 — toggle auto-mesh (auto-connect to discovered peers)
          connect <id-or-name>               — open a session
          send <text>                        — broadcast to every active session (room)
          to <id-or-name> <text>             — send to one peer
          manual <host>:<port>               — connect by IP, no mDNS needed
          sendfile <id-or-name> <path>       — stream a file from disk to one peer
          offers                              — list incoming file offers awaiting consent
          accept <offer-id-prefix>            — accept an offer within local storage limits
          reject <offer-id-prefix>            — reject an incoming offer
          close <id-or-name>                 — close a session
          help                               — show this list
          quit | exit                        — stop and exit

        Incoming file offers require an explicit accept or reject command.
        Accepted files are limited to 50 MiB, preserve 1 MiB of free space,
        and are saved below ~/.p2pkit/incoming/<sender-name>/.
        A " (n)" suffix is appended when the name is already taken.
        """.trimIndent()
    )
}

private fun printPeer(peer: Peer) {
    println("  ${peer.id.value.take(8)}…  ${peer.name.sanitizedForTerminal()}  [${peer.platform}]")
}

private fun findPeer(p2p: P2pKit, query: String): Peer? =
    p2p.peers.value.firstOrNull { matches(it, query) }

private fun matches(peer: Peer, query: String): Boolean =
    peer.id.value.startsWith(query) || peer.name.equals(query, ignoreCase = true)

/**
 * Single registration path for every session the CLI obtains (incoming,
 * auto-mesh, `connect`, `manual`): stores it in the local map, wires the
 * message/file collectors once, and watches state until terminal.
 *
 * AUDIT-2026-06 (B-G9-samples-desktop-ios-10): `p2p.connect()` is idempotent
 * and returns the SAME session instance while one is already in flight
 * (Connecting/Handshaking/Reconnecting). Wiring collectors a second time on
 * that instance made every subsequent message and state change print twice
 * for the rest of the run; [wiredSessionIds] makes wiring once-per-session-id
 * (ids are unique per session instance, so a replacement session for the same
 * peer still gets wired).
 *
 * AUDIT-2026-06 (A-G9-samples-desktop-ios-14): entries used to leave the
 * sessions map only via the user `close` command, so a session that reached
 * Closed/Failed (peer restart, network drop, reconnect exhausted) stayed in
 * the map forever — auto-mesh's containsKey guard then skipped the peer for
 * good and `sessions`/`send` kept reporting the dead session. The state
 * watcher below prunes the entry on terminal state. The two-arg remove is
 * identity-checked so a newer session already stored for the same peer is
 * never evicted, and the watcher cancels itself afterwards since a terminal
 * StateFlow never changes again.
 */
private fun registerSession(
    session: P2pSession,
    scope: CoroutineScope,
    sessions: ConcurrentHashMap<String, P2pSession>,
    wiredSessionIds: MutableSet<String>,
    pendingFileOffers: ConcurrentHashMap<String, P2pFileOffer>,
) {
    sessions[session.peer.id.value] = session
    if (!wiredSessionIds.add(session.id)) return // collectors already wired on this instance
    wireIncoming(session, scope, pendingFileOffers)
    scope.launch {
        session.state.collect { st ->
            println("[state] ${session.peer.name.sanitizedForTerminal()} → $st")
            if (st == ConnectionState.Closed || st == ConnectionState.Failed) {
                sessions.remove(session.peer.id.value, session)
                wiredSessionIds.remove(session.id)
                cancel()
            }
        }
    }
}

private fun wireIncoming(
    session: P2pSession,
    scope: CoroutineScope,
    pendingFileOffers: ConcurrentHashMap<String, P2pFileOffer>,
) {
    session.incoming
        .onEach { msg ->
            when (msg) {
                is P2pMessage.Text -> println("[${session.peer.name.sanitizedForTerminal()}] ${msg.value.sanitizedForTerminal()}")
                is P2pMessage.Binary -> println("[${session.peer.name.sanitizedForTerminal()}] <binary ${msg.bytes.size}B>")
            }
        }
        .launchIn(scope)
    session.incomingFiles
        .onEach { offer ->
            pendingFileOffers[offer.id] = offer
            println(
                "[file ← ${session.peer.name.sanitizedForTerminal()}] offered " +
                    "${offer.name.sanitizedForTerminal()} (${offer.sizeBytes}B), " +
                    "id=${offer.id.take(8)}…; use `accept ${offer.id.take(8)}` or `reject ${offer.id.take(8)}`"
            )
        }
        .launchIn(scope)
}

private const val MAX_INCOMING_FILE_BYTES: Long = 50L * 1024L * 1024L
private const val REQUIRED_FREE_SPACE_RESERVE_BYTES: Long = 1024L * 1024L

private suspend fun acceptIncomingFile(offer: P2pFileOffer) {
    val peerName = offer.peer.name.sanitizedForTerminal()
    val fileName = offer.name.sanitizedForTerminal()
    if (offer.sizeBytes < 0L || offer.sizeBytes > MAX_INCOMING_FILE_BYTES) {
        runCatching { offer.reject("file exceeds receiver limit") }
        System.err.println(
            "[file ← $peerName] rejected $fileName: size ${offer.sizeBytes}B is outside " +
                "the 0..$MAX_INCOMING_FILE_BYTES byte limit"
        )
        return
    }

    val homeDir = File(System.getProperty("user.home") ?: ".")
    val requiredBytes = offer.sizeBytes + REQUIRED_FREE_SPACE_RESERVE_BYTES
    if (homeDir.usableSpace < requiredBytes) {
        runCatching { offer.reject("insufficient receiver storage") }
        System.err.println(
            "[file ← $peerName] rejected $fileName: ${homeDir.usableSpace}B usable, " +
                "$requiredBytes B required"
        )
        return
    }

    val saveDir = File(File(homeDir, ".p2pkit"), "incoming/${sanitizeName(offer.peer.name)}")
    if (!saveDir.isDirectory && !saveDir.mkdirs()) {
        runCatching { offer.reject("cannot create destination directory") }
        System.err.println("[file ← $peerName] cannot create ${saveDir.absolutePath}")
        return
    }

    // AUDIT-2026-06 (A-G9-samples-desktop-ios-19): atomically claim a unique
    // destination only after the operator consents and storage checks pass.
    val saveFile = uniqueSaveFile(saveDir, sanitizeName(offer.name))
    val out = runCatching { saveFile.outputStream() }.getOrElse { error ->
        runCatching { saveFile.delete() }
        runCatching { offer.reject("cannot open destination: ${error.message}") }
        System.err.println("[file ← $peerName] open failed: ${error.message}")
        return
    }
    val transfer = runCatching { offer.accept(out.asSink()) }.getOrElse { error ->
        runCatching { out.close() }
        runCatching { saveFile.delete() }
        runCatching { offer.reject("accept failed: ${error.message}") }
        System.err.println("[file ← $peerName] accept failed: ${error.message}")
        return
    }
    println("[file ← $peerName] accepting $fileName (${offer.sizeBytes}B) → ${saveFile.absolutePath}")
    transfer.state.first { state ->
        println("[file ← $peerName $fileName] ${state.toString().sanitizedForTerminal()}")
        when (state) {
            is FileTransferState.Completed -> {
                runCatching { out.close() }
                true
            }
            is FileTransferState.Failed,
            is FileTransferState.Cancelled,
            is FileTransferState.Rejected -> {
                runCatching { out.close() }
                runCatching { saveFile.delete() }
                true
            }
            else -> false
        }
    }
}

private suspend fun rejectPendingOffers(
    pendingFileOffers: ConcurrentHashMap<String, P2pFileOffer>,
    reason: String,
) {
    pendingFileOffers.values.toList().forEach { offer ->
        if (pendingFileOffers.remove(offer.id, offer)) {
            runCatching { offer.reject(reason) }
        }
    }
}

private fun sanitizeName(raw: String): String {
    // Strip path separators and the few characters that are illegal on
    // Windows; everything else (spaces, unicode, dots) is fine for the sample.
    // AUDIT-2026-06 (B-G9-samples-desktop-ios-11): also drop ISO control
    // characters so a remote-supplied name can't smuggle terminal escape
    // sequences into the saved filename (and into the printed save path).
    val cleaned = raw.filterNot { it.isISOControl() }
        .replace(Regex("""[\\/:*?"<>|]"""), "_")
        .trim()
    return cleaned.ifEmpty { "untitled" }
}

// AUDIT-2026-06 (B-G9-samples-desktop-ios-11): peer names (from mDNS TXT /
// HELLO, unvalidated by the SDK) and message bodies are remote-controlled.
// Printing them verbatim let a hostile LAN peer embed ANSI/OSC escape
// sequences that rewrite, hide, or spoof lines on the operator's terminal
// (e.g. a fake "[file …] Completed" line). Strip ISO control characters
// before any remote-controlled string reaches stdout/stderr.
private fun String.sanitizedForTerminal(): String = filterNot { it.isISOControl() }

// AUDIT-2026-06 (A-G9-samples-desktop-ios-19): pick a destination no other
// transfer is writing to. createNewFile() atomically claims the name, so a
// repeated offer with the same name lands in "<base> (n)<ext>" instead of
// truncating the previous copy, and two concurrent same-named offers can
// never open two streams onto the same path.
private fun uniqueSaveFile(dir: File, sanitizedName: String): File {
    val dot = sanitizedName.lastIndexOf('.')
    val base = if (dot > 0) sanitizedName.substring(0, dot) else sanitizedName
    val ext = if (dot > 0) sanitizedName.substring(dot) else ""
    var n = 0
    while (true) {
        val candidate = if (n == 0) File(dir, sanitizedName) else File(dir, "$base ($n)$ext")
        val claimed = try {
            candidate.createNewFile() // atomic: false when the name is already taken
        } catch (_: Exception) {
            // Unopenable name or unwritable dir — return the candidate and let
            // the accept path's open-failure guard reject the offer with the
            // real error instead of looping here.
            return candidate
        }
        if (claimed) return candidate
        n++
    }
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
