package dev.p2pkit.sample.desktop.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import androidx.compose.ui.window.rememberWindowState
import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.launch

fun main() = application {
    Window(
        onCloseRequest = ::exitApplication,
        state = rememberWindowState(width = 820.dp, height = 640.dp),
        title = "P2pKit Sample (Desktop)"
    ) {
        MaterialTheme {
            Surface(modifier = Modifier.fillMaxSize()) {
                P2pKitSampleApp()
            }
        }
    }
}

@Composable
private fun P2pKitSampleApp() {
    // Parent-scoped coroutine scope. Survives RunningScreen leaving the
    // composition, which is critical for running `kit.stop()` to completion
    // when the user clicks Stop — a child scope would be cancelled mid-cleanup
    // and the kit's mDNS/TCP listeners would leak.
    val appScope = rememberCoroutineScope()
    var deviceName by remember { mutableStateOf("Desktop-${(1000..9999).random()}") }
    var appIdInput by remember { mutableStateOf(DEFAULT_APP_ID) }
    var p2p by remember { mutableStateOf<P2pKit?>(null) }

    val kit = p2p
    if (kit == null) {
        SetupScreen(
            deviceName = deviceName,
            onDeviceNameChange = { deviceName = it },
            appId = appIdInput,
            onAppIdChange = { appIdInput = it },
            onStart = {
                p2p = P2pKit.create {
                    appId = AppId(appIdInput.ifBlank { DEFAULT_APP_ID })
                    this.deviceName = deviceName
                    transports { lan() }
                }
            }
        )
    } else {
        RunningScreen(
            kit = kit,
            deviceName = deviceName,
            onStop = {
                val toStop = kit
                p2p = null
                // Run on appScope so the cleanup survives RunningScreen's disposal.
                appScope.launch { runCatching { toStop.stop() } }
            }
        )
    }
}

@Composable
private fun SetupScreen(
    deviceName: String,
    onDeviceNameChange: (String) -> Unit,
    appId: String,
    onAppIdChange: (String) -> Unit,
    onStart: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "P2pKit Sample",
            style = MaterialTheme.typography.headlineSmall
        )
        Text(
            text = "Discover other devices on the local network and exchange text messages.",
            style = MaterialTheme.typography.bodyMedium
        )
        OutlinedTextField(
            value = deviceName,
            onValueChange = onDeviceNameChange,
            label = { Text("Device name") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        OutlinedTextField(
            value = appId,
            onValueChange = onAppIdChange,
            label = { Text("App ID (must match on every device)") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Button(
            onClick = onStart,
            enabled = deviceName.isNotBlank() && appId.isNotBlank(),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Start")
        }
    }
}

@Composable
private fun RunningScreen(
    kit: P2pKit,
    deviceName: String,
    onStop: () -> Unit
) {
    val scope = rememberCoroutineScope()
    val peers by kit.peers.collectAsState()
    val sessions = remember { mutableStateListOf<P2pSession>() }
    val messages = remember { mutableStateListOf<ChatLine>() }
    var draft by remember { mutableStateOf("") }
    var selectedSession by remember { mutableStateOf<P2pSession?>(null) }

    // Start advertising + discovery when this screen enters composition.
    // Cleanup is owned by the parent via [onStop] — do NOT call kit.stop()
    // from this composable's scope (it would be cancelled before stop() can
    // finish).
    LaunchedEffect(kit) {
        runCatching { kit.startAdvertising() }
        runCatching { kit.startDiscovery() }
    }

    LaunchedEffect(kit) {
        kit.incomingSessions.collect { session ->
            sessions.add(session)
            if (selectedSession == null) selectedSession = session
            scope.launch {
                session.incoming.collect { msg ->
                    messages.add(ChatLine(session.peer.name, msg))
                }
            }
        }
    }

    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text("Logged in as $deviceName", fontWeight = FontWeight.SemiBold)
                Text("Peers: ${peers.size}", style = MaterialTheme.typography.bodySmall)
            }
            TextButton(onClick = onStop) { Text("Stop") }
        }
        Spacer(Modifier.height(12.dp))

        Row(modifier = Modifier.fillMaxSize()) {
            // Peers column
            Column(
                modifier = Modifier.width(280.dp).fillMaxHeight()
            ) {
                Text(
                    text = "Discovered peers",
                    style = MaterialTheme.typography.titleSmall
                )
                Spacer(Modifier.height(8.dp))
                if (peers.isEmpty()) {
                    Text(
                        text = "Searching… open the sample on another machine on the same Wi-Fi.",
                        style = MaterialTheme.typography.bodySmall
                    )
                } else {
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(peers, key = { it.id.value }) { peer ->
                            PeerCard(
                                peer = peer,
                                onConnect = {
                                    scope.launch {
                                        val session = runCatching { kit.connect(peer) }.getOrNull()
                                            ?: return@launch
                                        if (sessions.none { it.id == session.id }) sessions.add(session)
                                        selectedSession = session
                                        scope.launch {
                                            session.incoming.collect { msg ->
                                                messages.add(ChatLine(session.peer.name, msg))
                                            }
                                        }
                                    }
                                }
                            )
                        }
                    }
                }
            }

            Spacer(Modifier.width(16.dp))

            // Chat column
            Column(modifier = Modifier.fillMaxSize()) {
                val active = selectedSession
                if (active == null) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("Tap Connect on a peer to start chatting.")
                    }
                } else {
                    val sessionState by active.state.collectAsState()
                    Text(
                        text = "Session with ${active.peer.name} — ${sessionState.name}",
                        style = MaterialTheme.typography.titleSmall
                    )
                    Spacer(Modifier.height(8.dp))
                    LazyColumn(
                        modifier = Modifier.fillMaxWidth().height(380.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        items(messages.toList()) { line ->
                            Text("${line.from}: ${line.formatted}")
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = draft,
                            onValueChange = { draft = it },
                            label = { Text("Message") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth().padding(end = 8.dp)
                                .weight(1f)
                        )
                        Button(
                            onClick = {
                                val text = draft.trim()
                                if (text.isEmpty()) return@Button
                                draft = ""
                                scope.launch {
                                    runCatching { active.send(P2pMessage.Text(text)) }
                                }
                                messages.add(ChatLine("(me)", P2pMessage.Text(text)))
                            },
                            enabled = sessionState == ConnectionState.Connected
                        ) {
                            Text("Send")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PeerCard(peer: Peer, onConnect: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text(text = peer.name, style = MaterialTheme.typography.titleSmall)
                Text(
                    text = "${peer.platform} · ${peer.id.value.take(8)}…",
                    style = MaterialTheme.typography.bodySmall
                )
            }
            TextButton(onClick = onConnect) { Text("Connect") }
        }
    }
}

private data class ChatLine(val from: String, val message: P2pMessage) {
    val formatted: String
        get() = when (message) {
            is P2pMessage.Text -> message.value
            is P2pMessage.Binary -> "<binary ${message.bytes.size}B>"
        }
}

private const val DEFAULT_APP_ID = "p2pkit-desktop-sample"
