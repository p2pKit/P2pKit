package dev.p2pkit.sample.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LocalLifecycleOwner
import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    P2pKitSampleApp()
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun P2pKitSampleApp() {
    // Parent-scoped coroutine scope. Survives RunningScreen leaving the
    // composition, which is critical for running `kit.stop()` to completion
    // when the user clicks Stop — a child scope would be cancelled mid-cleanup
    // and the kit's mDNS/TCP listeners would leak.
    val appScope = rememberCoroutineScope()
    var deviceName by remember { mutableStateOf("Android-${(0..9999).random()}") }
    var p2p by remember { mutableStateOf<P2pKit?>(null) }
    val appContext = LocalContext.current.applicationContext

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text("P2pKit Sample") }
            )
        }
    ) { padding ->
        if (p2p == null) {
            SetupScreen(
                paddingValues = padding,
                deviceName = deviceName,
                onDeviceNameChange = { deviceName = it },
                onStart = {
                    p2p = P2pKit.create {
                        appId = AppId(APP_ID)
                        this.deviceName = deviceName
                        transports { lan(appContext) }
                    }
                }
            )
        } else {
            val kit = p2p!!
            RunningScreen(
                paddingValues = padding,
                kit = kit,
                onStop = {
                    val toStop = kit
                    p2p = null
                    // Run on appScope so the cleanup survives RunningScreen's disposal.
                    appScope.launch { runCatching { toStop.stop() } }
                }
            )
        }
    }
}

@Composable
private fun SetupScreen(
    paddingValues: PaddingValues,
    deviceName: String,
    onDeviceNameChange: (String) -> Unit,
    onStart: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text(
            text = "P2pKit v0.1 sample — discover other devices on the local network and exchange messages.",
            style = MaterialTheme.typography.bodyMedium
        )
        OutlinedTextField(
            value = deviceName,
            onValueChange = onDeviceNameChange,
            label = { Text("Device name") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Button(
            onClick = onStart,
            enabled = deviceName.isNotBlank(),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Start")
        }
    }
}

@Composable
private fun RunningScreen(
    paddingValues: PaddingValues,
    kit: P2pKit,
    onStop: () -> Unit
) {
    val scope = rememberCoroutineScope()
    val lifecycleOwner = LocalLifecycleOwner.current

    val peers by kit.peers.collectAsState()
    val sessions = remember { mutableStateListOf<P2pSession>() }
    val messages = remember { mutableStateListOf<ChatLine>() }
    var draft by remember { mutableStateOf("") }
    var selectedSession by remember { mutableStateOf<P2pSession?>(null) }

    // Start advertising + discovery when entering this screen. Cleanup is
    // owned by the parent via [onStop] — do NOT call kit.stop() from this
    // composable's scope (it would be cancelled before stop() can finish).
    LaunchedEffect(kit) {
        runCatching { kit.startAdvertising() }
        runCatching { kit.startDiscovery() }
    }

    // Bridge Android lifecycle to P2pKit's notifyApp* hooks.
    DisposableEffect(lifecycleOwner, kit) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_PAUSE -> kit.notifyAppBackgrounded()
                Lifecycle.Event.ON_RESUME -> kit.notifyAppForegrounded()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    // Wire up incoming sessions.
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
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = "Discovered peers (${peers.size})",
                style = MaterialTheme.typography.titleMedium
            )
            TextButton(onClick = onStop) { Text("Stop") }
        }
        Spacer(Modifier.height(8.dp))

        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(peers, key = { it.id.value }) { peer ->
                PeerCard(
                    peer = peer,
                    onConnect = {
                        scope.launch {
                            val session = runCatching { kit.connect(peer) }.getOrNull() ?: return@launch
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

        Spacer(Modifier.height(16.dp))

        val active = selectedSession
        if (active != null) {
            val sessionState by active.state.collectAsState()
            Text(
                text = "Session with ${active.peer.name} — ${sessionState.name}",
                style = MaterialTheme.typography.titleSmall
            )
            Spacer(Modifier.height(8.dp))
            LazyColumn(
                modifier = Modifier.fillMaxWidth().height(220.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                items(messages.toList()) { line ->
                    Text(
                        text = "${line.from}: ${line.formatted}",
                        maxLines = 4,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                label = { Text("Message") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(8.dp))
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
                modifier = Modifier.fillMaxWidth(),
                enabled = sessionState == ConnectionState.Connected
            ) {
                Text("Send")
            }
        } else {
            Text(
                text = "Tap a peer to connect.",
                style = MaterialTheme.typography.bodyMedium
            )
        }
    }
}

@Composable
private fun PeerCard(peer: Peer, onConnect: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
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

private const val APP_ID = "dev.p2pkit.sample.android"
