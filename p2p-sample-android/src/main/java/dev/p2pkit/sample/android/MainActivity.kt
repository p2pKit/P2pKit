package dev.p2pkit.sample.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    val vm: P2pKitViewModel = viewModel()
                    P2pKitSampleApp(vm)
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun P2pKitSampleApp(vm: P2pKitViewModel) {
    val isRunning by vm.isRunning.collectAsState()

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text("P2pKit Test Harness") }
            )
        }
    ) { padding ->
        if (!isRunning) {
            SetupScreen(
                paddingValues = padding,
                vm = vm
            )
        } else {
            RoomScreen(
                paddingValues = padding,
                vm = vm
            )
        }
    }
}

// =====================================================================
// Setup screen
// =====================================================================

@Composable
private fun SetupScreen(
    paddingValues: PaddingValues,
    vm: P2pKitViewModel
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text(
            text = "Discover devices on your Wi-Fi and chat with all of them in a room.",
            style = MaterialTheme.typography.bodyMedium
        )
        OutlinedTextField(
            value = vm.deviceName,
            onValueChange = vm::updateDeviceName,
            label = { Text("Device name") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Text(
            text = "App ID: ${vm.appId}",
            style = MaterialTheme.typography.bodySmall
        )

        Spacer(Modifier.height(8.dp))
        Text(
            text = "Reconnect policy",
            style = MaterialTheme.typography.titleSmall
        )
        ReconnectChoicePicker(vm)

        Spacer(Modifier.height(8.dp))
        Button(
            onClick = vm::start,
            enabled = vm.deviceName.isNotBlank(),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Start")
        }
    }
}

@Composable
private fun ReconnectChoicePicker(vm: P2pKitViewModel) {
    var maxAttemptsText by remember {
        mutableStateOf(
            (vm.reconnectChoice as? ReconnectChoice.Enabled)?.maxAttempts?.toString() ?: "5"
        )
    }
    var retryDelayText by remember {
        mutableStateOf(
            (vm.reconnectChoice as? ReconnectChoice.Enabled)?.retryDelayMillis?.toString() ?: "1000"
        )
    }
    val choice = vm.reconnectChoice
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            RadioButton(
                selected = choice is ReconnectChoice.Disabled,
                onClick = { vm.updateReconnectChoice(ReconnectChoice.Disabled) }
            )
            Text("Disabled")
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            RadioButton(
                selected = choice is ReconnectChoice.Enabled,
                onClick = {
                    val attempts = maxAttemptsText.toIntOrNull()?.coerceAtLeast(1) ?: 5
                    val delay = retryDelayText.toLongOrNull()?.coerceAtLeast(0L) ?: 1_000L
                    vm.updateReconnectChoice(ReconnectChoice.Enabled(attempts, delay))
                }
            )
            Text("Enabled")
        }
        if (choice is ReconnectChoice.Enabled) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = maxAttemptsText,
                    onValueChange = { txt ->
                        maxAttemptsText = txt.filter { it.isDigit() }.take(4)
                        val attempts = maxAttemptsText.toIntOrNull()?.coerceAtLeast(1) ?: 1
                        val delay = retryDelayText.toLongOrNull()?.coerceAtLeast(0L) ?: 0L
                        vm.updateReconnectChoice(ReconnectChoice.Enabled(attempts, delay))
                    },
                    label = { Text("maxAttempts") },
                    singleLine = true,
                    modifier = Modifier.weight(1f)
                )
                OutlinedTextField(
                    value = retryDelayText,
                    onValueChange = { txt ->
                        retryDelayText = txt.filter { it.isDigit() }.take(6)
                        val attempts = maxAttemptsText.toIntOrNull()?.coerceAtLeast(1) ?: 1
                        val delay = retryDelayText.toLongOrNull()?.coerceAtLeast(0L) ?: 0L
                        vm.updateReconnectChoice(ReconnectChoice.Enabled(attempts, delay))
                    },
                    label = { Text("retryDelayMillis") },
                    singleLine = true,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

// =====================================================================
// Room screen (running)
// =====================================================================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RoomScreen(
    paddingValues: PaddingValues,
    vm: P2pKitViewModel
) {
    val peers by vm.peers.collectAsState()
    val kitState by vm.kitState.collectAsState()
    val advertising by vm.advertising.collectAsState()
    val discovering by vm.discovering.collectAsState()
    val localPeerId by vm.localPeerId.collectAsState()
    var draft by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
            .padding(16.dp)
    ) {
        StatusHeader(
            appId = vm.appId,
            deviceName = vm.deviceName,
            peerId = localPeerId,
            kitState = kitState,
            advertising = advertising,
            discovering = discovering,
            onToggleAdvertising = vm::toggleAdvertising,
            onToggleDiscovery = vm::toggleDiscovery,
            onStop = vm::stop
        )
        HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp))

        Text(
            text = "Discovered peers (${peers.size})",
            style = MaterialTheme.typography.titleMedium
        )
        Spacer(Modifier.height(4.dp))
        LazyColumn(
            modifier = Modifier.fillMaxWidth().height(140.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            items(peers, key = { it.id.value }) { peer ->
                PeerCard(
                    peer = peer,
                    isConnected = vm.connectedSessions.any { it.peer.id.value == peer.id.value },
                    onConnect = { vm.connect(peer) }
                )
            }
        }

        val connected = vm.connectedSessions.toList()
        Spacer(Modifier.height(12.dp))
        if (connected.isNotEmpty()) {
            Text(
                text = "Room (${connected.size} connected)",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(Modifier.height(4.dp))
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(connected, key = { it.id }) { session ->
                    ConnectedPeerChip(
                        session = session,
                        isTargeted = vm.targetedPeerIds.contains(session.peer.id.value),
                        onToggleTarget = { vm.togglePeerTarget(session.peer.id.value) },
                        onCloseSession = { vm.closeSession(session.peer.id.value) }
                    )
                }
                item {
                    if (vm.targetedPeerIds.isNotEmpty()) {
                        AssistChip(
                            onClick = vm::clearPeerTargets,
                            label = { Text("Clear targets") },
                            colors = AssistChipDefaults.assistChipColors()
                        )
                    }
                }
            }
        } else {
            Text(
                text = "Tap Connect on a peer to start a room.",
                style = MaterialTheme.typography.bodyMedium
            )
        }

        Spacer(Modifier.height(12.dp))

        Text(text = "Timeline", style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(4.dp))
        LazyColumn(
            modifier = Modifier.fillMaxWidth().height(200.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            items(vm.roomMessages.toList(), key = { it.id }) { line ->
                RoomLine(line)
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
        val targetCount = vm.targetedPeerIds.size
        val sendLabel = when {
            connected.isEmpty() -> "No peers connected"
            targetCount == 0 -> "Broadcast (${connected.size})"
            else -> "Send to $targetCount"
        }
        Button(
            onClick = {
                val text = draft.trim()
                if (text.isEmpty()) return@Button
                draft = ""
                vm.sendRoomMessage(text)
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = connected.isNotEmpty() && draft.isNotBlank()
        ) {
            Text(sendLabel)
        }

        Spacer(Modifier.height(8.dp))

        Text(
            text = "Logs (last ${vm.logTail.size})",
            style = MaterialTheme.typography.labelMedium
        )
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(100.dp)
                .clip(RoundedCornerShape(6.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .padding(6.dp)
        ) {
            LazyColumn {
                items(vm.logTail.toList()) { line ->
                    Text(
                        text = line,
                        style = MaterialTheme.typography.labelSmall,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }
    }
}

// =====================================================================
// Pieces
// =====================================================================

@Composable
private fun StatusHeader(
    appId: String,
    deviceName: String,
    peerId: String?,
    kitState: P2pState,
    advertising: Boolean,
    discovering: Boolean,
    onToggleAdvertising: () -> Unit,
    onToggleDiscovery: () -> Unit,
    onStop: () -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(text = deviceName, style = MaterialTheme.typography.titleMedium)
            OverflowMenu(onStop = onStop)
        }
        Text(text = "appId: $appId", style = MaterialTheme.typography.bodySmall)
        Text(
            text = "peerId: ${peerId?.take(8) ?: "—"}…",
            style = MaterialTheme.typography.bodySmall
        )
        Text(
            text = "state: ${kitState::class.simpleName}",
            style = MaterialTheme.typography.bodySmall
        )
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Advertise", style = MaterialTheme.typography.bodySmall)
                Switch(checked = advertising, onCheckedChange = { onToggleAdvertising() })
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Discover", style = MaterialTheme.typography.bodySmall)
                Switch(checked = discovering, onCheckedChange = { onToggleDiscovery() })
            }
        }
    }
}

@Composable
private fun OverflowMenu(onStop: () -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        IconButton(onClick = { expanded = true }) {
            Text("⋮", style = MaterialTheme.typography.titleLarge)
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                text = { Text("Stop kit") },
                onClick = {
                    expanded = false
                    onStop()
                }
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ConnectedPeerChip(
    session: P2pSession,
    isTargeted: Boolean,
    onToggleTarget: () -> Unit,
    onCloseSession: () -> Unit
) {
    val state by session.state.collectAsState()
    var menuExpanded by remember { mutableStateOf(false) }
    Box {
        FilterChip(
            selected = isTargeted,
            onClick = onToggleTarget,
            label = {
                val stateLabel = state.name.lowercase()
                Text("${session.peer.name} · $stateLabel")
            },
            trailingIcon = {
                IconButton(onClick = { menuExpanded = true }) {
                    Text("⋮")
                }
            }
        )
        DropdownMenu(expanded = menuExpanded, onDismissRequest = { menuExpanded = false }) {
            DropdownMenuItem(
                text = { Text("Close session") },
                enabled = state == ConnectionState.Connected || state == ConnectionState.Reconnecting,
                onClick = {
                    menuExpanded = false
                    onCloseSession()
                }
            )
        }
    }
}

@Composable
private fun RoomLine(message: RoomMessage) {
    val style = MaterialTheme.typography.bodyMedium
    val prefix = when (message.direction) {
        RoomMessage.Direction.Incoming -> "${message.senderName} → "
        RoomMessage.Direction.Outgoing -> {
            val tgt = message.target
            val tag = when (tgt) {
                SendTarget.All -> "broadcast"
                is SendTarget.Specific -> "→ ${tgt.peerIds.size} peer(s)"
            }
            "me [$tag]: "
        }
        RoomMessage.Direction.System -> "[system] "
    }
    Text(
        text = "$prefix${message.displayBody}",
        style = style,
        maxLines = 3,
        overflow = TextOverflow.Ellipsis
    )
}

@Composable
private fun PeerCard(peer: Peer, isConnected: Boolean, onConnect: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(10.dp),
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
            if (isConnected) {
                Text(text = "Connected", style = MaterialTheme.typography.labelSmall)
            } else {
                TextButton(onClick = onConnect) { Text("Connect") }
            }
        }
    }
}
