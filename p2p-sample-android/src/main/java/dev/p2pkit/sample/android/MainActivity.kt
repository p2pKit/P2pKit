package dev.p2pkit.sample.android

import android.Manifest
import android.content.Intent
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.ui.platform.LocalContext
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
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkResult

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
    val autoMesh by vm.autoMesh.collectAsState()
    val localPeerId by vm.localPeerId.collectAsState()
    var draft by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {
        StatusHeader(
            appId = vm.appId,
            deviceName = vm.deviceName,
            peerId = localPeerId,
            kitState = kitState,
            advertising = advertising,
            discovering = discovering,
            autoMesh = autoMesh,
            onToggleAdvertising = vm::toggleAdvertising,
            onToggleDiscovery = vm::toggleDiscovery,
            onToggleAutoMesh = vm::toggleAutoMesh,
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

        Spacer(Modifier.height(12.dp))
        HotspotCard(vm = vm)

        Spacer(Modifier.height(8.dp))
        JoinHotspotCard(vm = vm)

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
    autoMesh: Boolean,
    onToggleAdvertising: () -> Unit,
    onToggleDiscovery: () -> Unit,
    onToggleAutoMesh: () -> Unit,
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
            horizontalArrangement = Arrangement.spacedBy(12.dp),
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
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Auto-mesh", style = MaterialTheme.typography.bodySmall)
                Switch(checked = autoMesh, onCheckedChange = { onToggleAutoMesh() })
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

/**
 * Returns true when the device-wide Location toggle is ON. This is a
 * settings-only toggle, not a runtime permission — apps can read it
 * but cannot flip it. Required (on most OEMs) for
 * `WifiManager.startLocalOnlyHotspot()` to succeed.
 */
private fun isLocationModeOn(context: android.content.Context): Boolean {
    val lm = context.getSystemService(android.content.Context.LOCATION_SERVICE) as? LocationManager
        ?: return true  // unknown → assume OK; avoid false-negative warning
    return runCatching {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) lm.isLocationEnabled
        else lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER) ||
            lm.isProviderEnabled(LocationManager.GPS_PROVIDER)
    }.getOrDefault(true)
}

@Composable
private fun HotspotCard(vm: P2pKitViewModel) {
    val result by vm.hotspotResult.collectAsState()
    val missing by vm.missingPermissions.collectAsState()
    val context = LocalContext.current

    // Pick the right runtime permission for the device's API level.
    val perm = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        Manifest.permission.NEARBY_WIFI_DEVICES
    } else {
        Manifest.permission.ACCESS_FINE_LOCATION
    }
    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { _ ->
        vm.refreshMissingPermissions()
        // Try starting again — user may have just granted the perm.
        vm.startHotspot()
    }
    // Device-wide Location toggle is settings-only — no permission API can
    // flip it. Some OEMs (Huawei, MIUI, older Samsung) require it ON even
    // when NEARBY_WIFI_DEVICES is granted.
    val locationOff = !isLocationModeOn(context)
    val isLocationProblem = (result as? LocalNetworkResult.Failed)
        ?.error is dev.p2pkit.core.NetworkProvisioningError.PermissionMissingForProvisioning &&
        (((result as LocalNetworkResult.Failed).error
            as dev.p2pkit.core.NetworkProvisioningError.PermissionMissingForProvisioning)
            .permissions.contains(dev.p2pkit.core.permission.P2pPermission.Location))

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                text = "Hotspot host (LocalOnlyHotspot)",
                style = MaterialTheme.typography.titleSmall
            )
            Spacer(Modifier.height(4.dp))
            val r = result
            when {
                r is LocalNetworkResult.Started -> {
                    val info = r.manualConnectionInfo
                    Text("SSID: ${r.credentials.ssid ?: "—"}", style = MaterialTheme.typography.bodySmall)
                    Text(
                        text = "Pass: ${r.credentials.password?.reveal() ?: "—"}",
                        style = MaterialTheme.typography.bodySmall
                    )
                    if (info != null) {
                        Text(
                            text = "host(s): ${info.hostAddresses.joinToString(", ")}",
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis
                        )
                        Text("port: ${info.port}", style = MaterialTheme.typography.bodySmall)
                    }
                    Spacer(Modifier.height(6.dp))
                    Button(onClick = vm::stopHotspot, modifier = Modifier.fillMaxWidth()) {
                        Text("Stop hotspot")
                    }
                }
                r is LocalNetworkResult.StartedWithoutCredentials -> {
                    val info = r.manualConnectionInfo
                    Text(
                        text = "Hotspot up, but SSID/passphrase redacted by the OS. " +
                            "Share host:port directly.",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Text(
                        text = "host(s): ${info.hostAddresses.joinToString(", ")}",
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text("port: ${info.port}", style = MaterialTheme.typography.bodySmall)
                    Spacer(Modifier.height(6.dp))
                    Button(onClick = vm::stopHotspot, modifier = Modifier.fillMaxWidth()) {
                        Text("Stop hotspot")
                    }
                }
                r is LocalNetworkResult.Failed -> {
                    if (isLocationProblem) {
                        Text(
                            text = "This device requires system-wide Location services to be ON " +
                                "for Wi-Fi hotspot hosting, even when NEARBY_WIFI_DEVICES is " +
                                "granted (Huawei / MIUI / older Samsung behavior). Turn on Location " +
                                "in system Settings, then Retry.",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Spacer(Modifier.height(6.dp))
                        Button(
                            onClick = {
                                context.startActivity(
                                    Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
                                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                )
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Open Location settings")
                        }
                        Spacer(Modifier.height(4.dp))
                        Button(
                            onClick = vm::startHotspot,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Retry")
                        }
                    } else {
                        Text(
                            text = "Failed: ${r.error::class.simpleName} — ${r.error.message ?: ""}",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Spacer(Modifier.height(6.dp))
                        Button(
                            onClick = {
                                if (missing.isNotEmpty()) launcher.launch(perm) else vm.startHotspot()
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(if (missing.isNotEmpty()) "Grant permission and retry" else "Retry")
                        }
                    }
                }
                r is LocalNetworkResult.Unsupported -> {
                    Text(
                        text = "Unsupported: ${r.reason}",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                else -> {
                    Text(
                        text = "Host a LocalOnlyHotspot so a nearby peer can join (no SIM / no router needed). " +
                            "Random SSID + passphrase chosen by Android.",
                        style = MaterialTheme.typography.bodySmall
                    )
                    if (locationOff) {
                        Spacer(Modifier.height(4.dp))
                        Text(
                            text = "Note: this device's system-wide Location toggle is OFF. " +
                                "Many OEMs require it ON for hotspot hosting. If start fails, " +
                                "enable Location in Settings.",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                    Spacer(Modifier.height(6.dp))
                    Button(
                        onClick = {
                            if (missing.isNotEmpty()) launcher.launch(perm) else vm.startHotspot()
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            if (missing.isNotEmpty()) "Grant permission and host hotspot"
                            else "Host hotspot"
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun JoinHotspotCard(vm: P2pKitViewModel) {
    val joinResult by vm.joinResult.collectAsState()
    val missing by vm.missingPermissions.collectAsState()
    val context = LocalContext.current

    // Pick the right runtime permission for the device's API level.
    val perm = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        Manifest.permission.NEARBY_WIFI_DEVICES
    } else {
        Manifest.permission.ACCESS_FINE_LOCATION
    }
    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { vm.refreshMissingPermissions() }

    var ssidInput by remember { mutableStateOf("") }
    var passInput by remember { mutableStateOf("") }

    val isLocationProblem = (joinResult as? JoinNetworkResult.Failed)
        ?.error is dev.p2pkit.core.NetworkProvisioningError.PermissionMissingForProvisioning &&
        ((joinResult as JoinNetworkResult.Failed).error
            as dev.p2pkit.core.NetworkProvisioningError.PermissionMissingForProvisioning)
            .permissions.contains(dev.p2pkit.core.permission.P2pPermission.Location)

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                text = "Join hotspot (WifiNetworkSpecifier)",
                style = MaterialTheme.typography.titleSmall
            )
            Spacer(Modifier.height(4.dp))
            val r = joinResult
            when {
                r is JoinNetworkResult.Joined -> {
                    Text(
                        text = "Joined. Routing this app's traffic through the joined network. " +
                            "Internet may be unavailable while joined.",
                        style = MaterialTheme.typography.bodySmall
                    )
                    val state = r.networkState
                    if (state is dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi) {
                        Text(
                            text = "ip(s): ${state.localIpAddresses.joinToString(", ")}",
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    Spacer(Modifier.height(6.dp))
                    Button(
                        onClick = vm::clearJoinResult,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("Clear status")
                    }
                }
                r is JoinNetworkResult.Failed -> {
                    if (isLocationProblem) {
                        Text(
                            text = "This device requires system-wide Location services to be ON " +
                                "for joining a peer's Wi-Fi network, even when NEARBY_WIFI_DEVICES " +
                                "is granted (Huawei / MIUI / older Samsung behavior).",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Spacer(Modifier.height(6.dp))
                        Button(
                            onClick = {
                                context.startActivity(
                                    Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
                                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                )
                            },
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Open Location settings")
                        }
                    } else {
                        Text(
                            text = "Failed: ${r.error::class.simpleName} — ${r.error.message ?: ""}",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                    Spacer(Modifier.height(6.dp))
                    JoinInputs(
                        ssid = ssidInput,
                        onSsidChange = { ssidInput = it },
                        pass = passInput,
                        onPassChange = { passInput = it }
                    )
                    Spacer(Modifier.height(4.dp))
                    Button(
                        onClick = {
                            if (missing.isNotEmpty()) permLauncher.launch(perm)
                            else vm.joinHotspot(ssidInput, passInput)
                        },
                        enabled = ssidInput.isNotBlank(),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            if (missing.isNotEmpty()) "Grant permission and retry"
                            else "Retry join"
                        )
                    }
                }
                r is JoinNetworkResult.Unsupported -> {
                    Text(
                        text = "Unsupported: ${r.reason}",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                r is JoinNetworkResult.RequiresUserAction -> {
                    Text(
                        text = r.instruction,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                else -> {
                    Text(
                        text = "Connect this device to a peer's LocalOnlyHotspot. Enter the SSID + " +
                            "passphrase shown on the host phone's Hotspot card. The OS will prompt " +
                            "you to approve the join.",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Spacer(Modifier.height(6.dp))
                    JoinInputs(
                        ssid = ssidInput,
                        onSsidChange = { ssidInput = it },
                        pass = passInput,
                        onPassChange = { passInput = it }
                    )
                    Spacer(Modifier.height(4.dp))
                    Button(
                        onClick = {
                            if (missing.isNotEmpty()) permLauncher.launch(perm)
                            else vm.joinHotspot(ssidInput, passInput)
                        },
                        enabled = ssidInput.isNotBlank(),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            if (missing.isNotEmpty()) "Grant permission and join"
                            else "Join hotspot"
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun JoinInputs(
    ssid: String,
    onSsidChange: (String) -> Unit,
    pass: String,
    onPassChange: (String) -> Unit
) {
    OutlinedTextField(
        value = ssid,
        onValueChange = onSsidChange,
        label = { Text("SSID") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
    )
    Spacer(Modifier.height(4.dp))
    OutlinedTextField(
        value = pass,
        onValueChange = onPassChange,
        label = { Text("Passphrase (blank = open network)") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
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
