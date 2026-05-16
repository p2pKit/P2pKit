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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
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
                title = { Text("P2pKit Sample") }
            )
        }
    ) { padding ->
        if (!isRunning) {
            SetupScreen(
                paddingValues = padding,
                deviceName = vm.deviceName,
                onDeviceNameChange = vm::updateDeviceName,
                onStart = vm::start
            )
        } else {
            RoomScreen(
                paddingValues = padding,
                vm = vm
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
            text = "P2pKit sample — discover devices on your Wi-Fi and chat with all of them in a room.",
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
private fun RoomScreen(
    paddingValues: PaddingValues,
    vm: P2pKitViewModel
) {
    val peers by vm.peers.collectAsState()
    var draft by remember { mutableStateOf("") }

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
            TextButton(onClick = vm::stop) { Text("Stop") }
        }
        Spacer(Modifier.height(8.dp))

        LazyColumn(
            modifier = Modifier.fillMaxWidth().height(160.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(peers, key = { it.id.value }) { peer ->
                PeerCard(
                    peer = peer,
                    isConnected = vm.connectedSessions.any { it.peer.id.value == peer.id.value },
                    onConnect = { vm.connect(peer) }
                )
            }
        }

        Spacer(Modifier.height(16.dp))

        // Connected peers + target selection ------------------------------------
        val connected = vm.connectedSessions.toList()
        if (connected.isNotEmpty()) {
            Text(
                text = "Room (${connected.size} connected)",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(Modifier.height(8.dp))
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(connected, key = { it.id }) { session ->
                    val pid = session.peer.id.value
                    val selected = vm.targetedPeerIds.contains(pid)
                    FilterChip(
                        selected = selected,
                        onClick = { vm.togglePeerTarget(pid) },
                        label = { Text(session.peer.name) }
                    )
                }
                item {
                    if (vm.targetedPeerIds.isNotEmpty()) {
                        AssistChip(
                            onClick = vm::clearPeerTargets,
                            label = { Text("Broadcast") },
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

        // Room timeline ---------------------------------------------------------
        LazyColumn(
            modifier = Modifier.fillMaxWidth().height(260.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            items(vm.roomMessages.toList(), key = { it.id }) { line ->
                RoomLine(line)
            }
        }

        Spacer(Modifier.height(8.dp))

        // Input + Send ----------------------------------------------------------
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
        maxLines = 4,
        overflow = TextOverflow.Ellipsis
    )
}

@Composable
private fun PeerCard(peer: Peer, isConnected: Boolean, onConnect: () -> Unit) {
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
            if (isConnected) {
                Text(text = "Connected", style = MaterialTheme.typography.labelSmall)
            } else {
                TextButton(onClick = onConnect) { Text("Connect") }
            }
        }
    }
}
