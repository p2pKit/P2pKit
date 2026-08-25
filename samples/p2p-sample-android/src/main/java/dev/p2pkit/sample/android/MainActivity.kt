package dev.p2pkit.sample.android

import android.Manifest
import android.content.Intent
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.viewModels
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
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
import androidx.compose.material3.Icon
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.WifiSecurityType
import dev.p2pkit.core.transfer.FileTransferState
import kotlinx.coroutines.delay
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * AUDIT-2026-06: C-G8-samples-android-07 — shared spacing tokens so card
 * padding, section gaps and line spacing are uniform across the screen
 * instead of ad-hoc 2/4/6/8/10/12dp literals. Shapes come from
 * `MaterialTheme.shapes` rather than hand-rolled corner radii.
 */
private object Dimens {
    /** Outer padding of each screen. */
    val ScreenPadding = 16.dp
    /** Content padding inside every Card. */
    val CardPadding = 12.dp
    /** Vertical gap between major sections. */
    val SectionGap = 12.dp
    /** Gap between sibling items and before buttons. */
    val ItemGap = 8.dp
    /** Gap between closely related lines/controls. */
    val SmallGap = 4.dp
    /** Tight line spacing in dense lists. */
    val LineGap = 2.dp
}

internal const val SECURITY_POSTURE_WARNING: String =
    "DEVELOPMENT MODE: accepting any authenticated peer with this AppId. " +
        "Production apps must pin peer fingerprints with PinnedOnly."

class MainActivity : ComponentActivity() {
    private val sampleViewModel: P2pKitViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    P2pKitSampleApp(sampleViewModel)
                }
            }
        }
    }

    override fun onStart() {
        super.onStart()
        sampleViewModel.notifyForegrounded()
    }

    override fun onStop() {
        sampleViewModel.notifyBackgrounded()
        super.onStop()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun P2pKitSampleApp(vm: P2pKitViewModel) {
    val isRunning by vm.isRunning.collectAsState()
    var showDiagnostics by rememberSaveable { mutableStateOf(false) }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Column {
                        Text("P2pKit Test Harness")
                        // V0.4-PROVENANCE (L2 UI): show the active SDK
                        // build identity in the title bar so the
                        // operator can visually confirm the deployed
                        // version before starting any hardware test.
                        Text(
                            text = dev.p2pkit.core.BuildInfo.describe(),
                            style = MaterialTheme.typography.labelSmall
                        )
                    }
                },
                actions = {
                    TextButton(onClick = { showDiagnostics = !showDiagnostics }) {
                        Text(if (showDiagnostics) "Room" else "Diagnostics")
                    }
                }
            )
        }
    ) { padding ->
        if (showDiagnostics) {
            AndroidDiagnosticsScreen(
                vm = vm,
                onBack = { showDiagnostics = false },
                paddingValues = padding
            )
        } else if (!isRunning) {
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
    val isStarting by vm.isStarting.collectAsState()
    // AUDIT-2026-06: D-G8-samples-android-02 — Start must also wait for the
    // previous kit's async teardown, or two kits overlap (duplicate mDNS
    // advertisements + two TCP listeners).
    val isStopping by vm.isStopping.collectAsState()
    val cleanupPending by vm.cleanupPending.collectAsState()
    val kmpSmokeBusy by vm.kmpSmokeBusy.collectAsState()
    val kmpSmokeResult by vm.kmpSmokeResult.collectAsState()
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
            // AUDIT-2026-06: D-G8-samples-android-14 — scrollable + imePadding so
            // the Start button stays reachable with the keyboard open
            // (adjustResize) and in landscape.
            .verticalScroll(rememberScrollState())
            .imePadding()
            .padding(Dimens.ScreenPadding),
        verticalArrangement = Arrangement.spacedBy(Dimens.SectionGap)
    ) {
        Text(
            text = "Discover devices on your Wi-Fi and chat with all of them in a room.",
            style = MaterialTheme.typography.bodyMedium
        )
        SecurityPostureWarning()
        OutlinedTextField(
            value = vm.deviceName,
            onValueChange = vm::updateDeviceName,
            label = { Text("Device name") },
            singleLine = true,
            enabled = !isStarting,
            modifier = Modifier.fillMaxWidth()
        )
        Text(
            text = "App ID: ${vm.appId}",
            style = MaterialTheme.typography.bodySmall
        )

        Spacer(Modifier.height(Dimens.ItemGap))
        Text(
            text = "Reconnect policy",
            style = MaterialTheme.typography.titleSmall
        )
        ReconnectChoicePicker(vm)

        Spacer(Modifier.height(Dimens.ItemGap))
        Button(
            onClick = vm::start,
            enabled = vm.deviceName.trim().isNotEmpty() && !isStarting && !isStopping,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                when {
                    isStarting -> "Starting…"
                    isStopping -> "Stopping previous run…"
                    cleanupPending -> "Retry cleanup"
                    else -> "Start"
                }
            )
        }

        Button(
            onClick = vm::runKmpConsumerSmoke,
            enabled = !isStarting && !isStopping && !kmpSmokeBusy,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(if (kmpSmokeBusy) "Running KMP consumer smoke…" else "Run KMP consumer smoke")
        }
        if (kmpSmokeResult != null) {
            Text(
                text = kmpSmokeResult.orEmpty(),
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}

@Composable
private fun ReconnectChoicePicker(vm: P2pKitViewModel) {
    // v0.4 sample-only bump: the picker preset is 10 / 1500 instead of the
    // SDK's documented 5 / 1000 defaults. Reason — see README "Known
    // limitations" entry for the v0.4 NsdManager mDNS-cache limitation:
    // when the *remote* peer's network flaps (e.g. iPhone Wi-Fi off/on),
    // Android's NSD daemon serves stale cached SRV records for an
    // extended TTL window. A longer reconnect budget lets the retry loop
    // outlast both the remote peer's cellular-handover gap and the
    // daemon's cache eviction so a fresh resolution can land before
    // attempts exhaust. The SDK's defaults are intentionally NOT
    // changed — apps that don't hit this scenario shouldn't be forced
    // into a longer perceived-failure window.
    //
    // AUDIT-2026-06: C-G8-samples-android-05 — rememberSaveable so the
    // half-edited values survive rotation/theme changes.
    var maxAttemptsText by rememberSaveable {
        mutableStateOf(
            (vm.reconnectChoice as? ReconnectChoice.Enabled)?.maxAttempts?.toString() ?: "10"
        )
    }
    var retryDelayText by rememberSaveable {
        mutableStateOf(
            (vm.reconnectChoice as? ReconnectChoice.Enabled)?.retryDelayMillis?.toString() ?: "1500"
        )
    }
    val choice = vm.reconnectChoice
    // AUDIT-2026-06: A-G8-samples-android-16 — single commit path: blank /
    // mid-edit fields fall back to the same 10 / 1500 preset the radio
    // commits (previously the fields silently committed 1 / 0).
    fun commitEnabled() {
        val attempts = maxAttemptsText.toIntOrNull()?.coerceAtLeast(1) ?: 10
        val delay = retryDelayText.toLongOrNull()?.coerceAtLeast(0L) ?: 1_500L
        vm.updateReconnectChoice(ReconnectChoice.Enabled(attempts, delay))
    }
    Column(verticalArrangement = Arrangement.spacedBy(Dimens.SmallGap)) {
        // AUDIT-2026-06: D-G8-samples-android-11 — the whole row is the
        // selectable element (Role.RadioButton) so the label is announced
        // and tappable; the inner control has onClick = null.
        Row(
            modifier = Modifier.selectable(
                selected = choice is ReconnectChoice.Disabled,
                role = Role.RadioButton,
                onClick = { vm.updateReconnectChoice(ReconnectChoice.Disabled) }
            ),
            verticalAlignment = Alignment.CenterVertically
        ) {
            RadioButton(
                selected = choice is ReconnectChoice.Disabled,
                onClick = null
            )
            Text("Disabled")
        }
        Row(
            modifier = Modifier.selectable(
                selected = choice is ReconnectChoice.Enabled,
                role = Role.RadioButton,
                onClick = { commitEnabled() }
            ),
            verticalAlignment = Alignment.CenterVertically
        ) {
            RadioButton(
                selected = choice is ReconnectChoice.Enabled,
                onClick = null
            )
            Text("Enabled")
        }
        if (choice is ReconnectChoice.Enabled) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(Dimens.ItemGap),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = maxAttemptsText,
                    onValueChange = { txt ->
                        maxAttemptsText = txt.filter { it.isDigit() }.take(4)
                        commitEnabled()
                    },
                    label = { Text("maxAttempts") },
                    singleLine = true,
                    // AUDIT-2026-06: D-G8-samples-android-05 — numeric keyboard
                    // for the digit-only field.
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.weight(1f)
                )
                OutlinedTextField(
                    value = retryDelayText,
                    onValueChange = { txt ->
                        retryDelayText = txt.filter { it.isDigit() }.take(6)
                        commitEnabled()
                    },
                    label = { Text("retryDelayMillis") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
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
    val isStopping by vm.isStopping.collectAsState()
    val networkPathStatus by vm.networkPathStatus.collectAsState()
    // AUDIT-2026-06: C-G8-samples-android-05 — survive configuration changes.
    var draft by rememberSaveable { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(Dimens.ScreenPadding)
    ) {
        SecurityPostureWarning()
        Spacer(Modifier.height(Dimens.ItemGap))
        StatusHeader(
            appId = vm.appId,
            deviceName = vm.deviceName,
            peerId = localPeerId,
            kitState = kitState,
            advertising = advertising,
            discovering = discovering,
            autoMesh = autoMesh,
            isStopping = isStopping,
            networkPathStatus = networkPathStatus,
            onToggleAdvertising = vm::toggleAdvertising,
            onToggleDiscovery = vm::toggleDiscovery,
            onToggleAutoMesh = vm::toggleAutoMesh,
            onStop = vm::stop
        )
        HorizontalDivider(modifier = Modifier.padding(vertical = Dimens.ItemGap))

        Text(
            text = "Discovered peers (${peers.size})",
            style = MaterialTheme.typography.titleMedium
        )
        Spacer(Modifier.height(Dimens.SmallGap))
        LazyColumn(
            modifier = Modifier.fillMaxWidth().height(140.dp),
            verticalArrangement = Arrangement.spacedBy(Dimens.ItemGap)
        ) {
            items(peers, key = { it.id.value }) { peer ->
                PeerCard(
                    peer = peer,
                    // AUDIT-2026-06: A-G8-samples-android-18 — hand the session
                    // over so the card can label from its real state instead of
                    // showing "Connected" for any non-terminal session.
                    session = vm.connectedSessions.firstOrNull { it.peer.id.value == peer.id.value },
                    isConnecting = vm.pendingConnectPeerIds.contains(peer.id.value),
                    onConnect = { vm.connect(peer) }
                )
            }
        }

        Spacer(Modifier.height(Dimens.SectionGap))
        HotspotCard(vm = vm)

        Spacer(Modifier.height(Dimens.ItemGap))
        JoinHotspotCard(vm = vm)

        // AUDIT-2026-06: B-G8-samples-android-04 — read the SnapshotStateList
        // directly; no per-recomposition toList() copies.
        val connected = vm.connectedSessions
        Spacer(Modifier.height(Dimens.SectionGap))

        // File picker shared across all per-chip "Send file…" menu items.
        // AUDIT-2026-06: A-G8-samples-android-15 — rememberSaveable so the
        // target peer survives Activity recreation while the picker is open.
        var pendingSendPeerId by rememberSaveable { mutableStateOf<String?>(null) }
        val pickerLauncher = rememberLauncherForActivityResult(
            ActivityResultContracts.OpenDocument()
        ) { uri ->
            val peerId = pendingSendPeerId
            pendingSendPeerId = null
            when {
                uri != null && peerId != null -> vm.sendFile(peerId, uri)
                uri == null && peerId != null -> vm.notifyFilePickerCancelled(peerId)
                // AUDIT-2026-06: A-G8-samples-android-15 — surface the dropped
                // result instead of silently discarding the picked file.
                uri != null -> vm.notifySendTargetLost()
            }
        }

        if (connected.isNotEmpty()) {
            Text(
                text = "Room (${connected.size} connected)",
                style = MaterialTheme.typography.titleMedium
            )
            Spacer(Modifier.height(Dimens.SmallGap))
            LazyRow(horizontalArrangement = Arrangement.spacedBy(Dimens.ItemGap)) {
                items(connected, key = { it.id }) { session ->
                    ConnectedPeerChip(
                        session = session,
                        isTargeted = vm.targetedPeerIds.contains(session.peer.id.value),
                        onToggleTarget = { vm.togglePeerTarget(session.peer.id.value) },
                        onCloseSession = { vm.closeSession(session.peer.id.value) },
                        onSendFile = {
                            pendingSendPeerId = session.peer.id.value
                            pickerLauncher.launch(arrayOf("*/*"))
                        }
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

        Spacer(Modifier.height(Dimens.SectionGap))

        Text(text = "Timeline", style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(Dimens.SmallGap))
        // AUDIT-2026-06: D-G8-samples-android-06 — autoscroll so the newest
        // timeline entries are visible without manual scrolling. Keyed on
        // size + last id so it also fires once the capacity trim keeps the
        // size constant.
        val timelineState = rememberLazyListState()
        LaunchedEffect(vm.roomMessages.size, vm.roomMessages.lastOrNull()?.id) {
            if (vm.roomMessages.isNotEmpty()) {
                timelineState.animateScrollToItem(vm.roomMessages.size - 1)
            }
        }
        LazyColumn(
            state = timelineState,
            modifier = Modifier.fillMaxWidth().height(200.dp),
            verticalArrangement = Arrangement.spacedBy(Dimens.LineGap)
        ) {
            items(vm.roomMessages, key = { it.id }) { line ->
                RoomLine(line)
            }
        }

        Spacer(Modifier.height(Dimens.ItemGap))

        OutlinedTextField(
            value = draft,
            onValueChange = { draft = it },
            label = { Text("Message") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(Modifier.height(Dimens.ItemGap))
        val targetCount = vm.targetedPeerIds.size
        val sendLabel = when {
            connected.isEmpty() -> "No peers connected"
            targetCount == 0 -> "Broadcast (${connected.size})"
            else -> "Send to $targetCount"
        }
        // AUDIT-2026-06: A-G8-samples-android-19 — single derived flag from the
        // ViewModel instead of collectAsState() inside a short-circuiting any{}.
        val hasConnectedSession by vm.hasConnectedSession.collectAsState()
        Button(
            onClick = {
                val text = draft.trim()
                if (text.isEmpty()) return@Button
                draft = ""
                vm.sendRoomMessage(text)
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = hasConnectedSession && draft.trim().isNotEmpty() && !isStopping
        ) {
            Text(sendLabel)
        }

        Spacer(Modifier.height(Dimens.ItemGap))

        if (vm.pendingFileOffers.isNotEmpty()) {
            Text(
                text = "Incoming file offers (${vm.pendingFileOffers.size})",
                style = MaterialTheme.typography.titleSmall
            )
            Spacer(Modifier.height(Dimens.SmallGap))
            Column(verticalArrangement = Arrangement.spacedBy(Dimens.SmallGap)) {
                vm.pendingFileOffers.toList().forEach { offer ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text("${offer.name} from ${offer.peerName}", maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text("${offer.sizeBytes} bytes — consent required", style = MaterialTheme.typography.labelSmall)
                        }
                        TextButton(onClick = { vm.acceptFileOffer(offer.id) }) { Text("Accept") }
                        TextButton(onClick = { vm.rejectFileOffer(offer.id) }) { Text("Reject") }
                    }
                }
            }
            Spacer(Modifier.height(Dimens.ItemGap))
        }

        if (vm.fileTransfers.isNotEmpty()) {
            Text(
                text = "File transfers (${vm.fileTransfers.size})",
                style = MaterialTheme.typography.titleSmall
            )
            Spacer(Modifier.height(Dimens.SmallGap))
            LazyColumn(
                modifier = Modifier.fillMaxWidth().height(160.dp),
                verticalArrangement = Arrangement.spacedBy(Dimens.SmallGap)
            ) {
                items(vm.fileTransfers, key = { it.id }) { row ->
                    FileTransferRowView(row = row, onCancel = { vm.cancelFileTransfer(row.id) })
                }
            }
            Spacer(Modifier.height(Dimens.ItemGap))
        }

        Text(
            text = "Logs (last ${vm.logTail.size})",
            style = MaterialTheme.typography.labelMedium
        )
        // AUDIT-2026-06: D-G8-samples-android-06 — keep the newest log lines
        // in view as they arrive.
        val logState = rememberLazyListState()
        LaunchedEffect(vm.logTail.size, vm.logTail.lastOrNull()) {
            if (vm.logTail.isNotEmpty()) logState.scrollToItem(vm.logTail.size - 1)
        }
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(100.dp)
                .clip(MaterialTheme.shapes.small)
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .padding(Dimens.ItemGap)
        ) {
            LazyColumn(state = logState) {
                items(vm.logTail) { line ->
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
private fun SecurityPostureWarning() {
    Card(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = SECURITY_POSTURE_WARNING,
            color = MaterialTheme.colorScheme.onErrorContainer,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.errorContainer)
                .padding(Dimens.CardPadding)
        )
    }
}

@Composable
private fun StatusHeader(
    appId: String,
    deviceName: String,
    peerId: String?,
    kitState: P2pState,
    advertising: Boolean,
    discovering: Boolean,
    autoMesh: Boolean,
    isStopping: Boolean,
    networkPathStatus: NetworkPathStatus,
    onToggleAdvertising: () -> Unit,
    onToggleDiscovery: () -> Unit,
    onToggleAutoMesh: () -> Unit,
    onStop: () -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(Dimens.LineGap)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(text = deviceName, style = MaterialTheme.typography.titleMedium)
            OverflowMenu(onStop = onStop, isStopping = isStopping)
        }
        Text(text = "appId: $appId", style = MaterialTheme.typography.bodySmall)
        Text(
            text = "peerId: ${peerId?.take(8) ?: "—"}…",
            style = MaterialTheme.typography.bodySmall
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                text = "state: ${kitState::class.simpleName}",
                style = MaterialTheme.typography.bodySmall
            )
            Spacer(Modifier.width(Dimens.ItemGap))
            NetworkPathChip(networkPathStatus)
        }
        // AUDIT-2026-06: D-G8-samples-android-11 — each label+switch row is one
        // toggleable element (Role.Switch): screen readers announce the label
        // and tapping the label toggles; the inner Switch has no own handler.
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(Dimens.SectionGap),
            verticalAlignment = Alignment.CenterVertically
        ) {
            LabelledSwitch(label = "Advertise", checked = advertising, onToggle = onToggleAdvertising)
            LabelledSwitch(label = "Discover", checked = discovering, onToggle = onToggleDiscovery)
            LabelledSwitch(label = "Auto-mesh", checked = autoMesh, onToggle = onToggleAutoMesh)
        }
    }
}

@Composable
private fun LabelledSwitch(label: String, checked: Boolean, onToggle: () -> Unit) {
    Row(
        modifier = Modifier.toggleable(
            value = checked,
            role = Role.Switch,
            onValueChange = { onToggle() }
        ),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.width(Dimens.SmallGap))
        Switch(checked = checked, onCheckedChange = null)
    }
}

/**
 * Tiny coloured chip showing the current [NetworkPathStatus]. Sized to fit
 * on the same row as the kit-state text so testers can watch path
 * transitions during Wi-Fi toggle tests without scrolling.
 *
 * AUDIT-2026-06: C-G8-samples-android-06 — colors come from the
 * MaterialTheme color scheme (container/on-container roles) instead of
 * hardcoded hex literals, so the chip stays consistent with the theme.
 */
@Composable
private fun NetworkPathChip(status: NetworkPathStatus) {
    val scheme = MaterialTheme.colorScheme
    val (label, bg, fg) = when (status) {
        NetworkPathStatus.Satisfied ->
            Triple("online", scheme.primaryContainer, scheme.onPrimaryContainer)
        NetworkPathStatus.Unsatisfied ->
            Triple("offline", scheme.errorContainer, scheme.onErrorContainer)
        NetworkPathStatus.Unknown ->
            Triple("path: unknown", scheme.surfaceVariant, scheme.onSurfaceVariant)
    }
    Text(
        text = label,
        style = MaterialTheme.typography.labelSmall,
        color = fg,
        modifier = Modifier
            .clip(MaterialTheme.shapes.small)
            .background(bg)
            .padding(horizontal = Dimens.ItemGap, vertical = Dimens.LineGap)
    )
}

@Composable
private fun OverflowMenu(onStop: () -> Unit, isStopping: Boolean) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        IconButton(onClick = { expanded = true }) {
            // AUDIT-2026-06: D-G8-samples-android-10 — real icon with a
            // contentDescription instead of an unlabeled "⋮" glyph.
            Icon(Icons.Default.MoreVert, contentDescription = "Kit options")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                text = { Text(if (isStopping) "Stopping…" else "Stop kit") },
                enabled = !isStopping,
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
    onCloseSession: () -> Unit,
    onSendFile: () -> Unit
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
                    // AUDIT-2026-06: D-G8-samples-android-10 — labeled icon.
                    Icon(
                        Icons.Default.MoreVert,
                        contentDescription = "Session options for ${session.peer.name}"
                    )
                }
            }
        )
        DropdownMenu(expanded = menuExpanded, onDismissRequest = { menuExpanded = false }) {
            DropdownMenuItem(
                text = { Text("Send file…") },
                enabled = state == ConnectionState.Connected,
                onClick = {
                    menuExpanded = false
                    onSendFile()
                }
            )
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
private fun FileTransferRowView(row: FileTransferRow, onCancel: () -> Unit) {
    val state = row.state
    val isActive = state is FileTransferState.Offered ||
        state is FileTransferState.Accepted ||
        state is FileTransferState.Sending
    val arrow = if (row.direction == FileTransferDirection.Outgoing) "↑" else "↓"
    // AUDIT-2026-06: D-G8-samples-android-12 — direction also as text
    // ("to"/"from" the peer), not just the arrow glyph screen readers skip.
    val directionWord = if (row.direction == FileTransferDirection.Outgoing) "to" else "from"
    val sizeKb = row.sizeBytes / 1024
    val sentKb = row.bytesTransferred / 1024
    val pct = if (row.sizeBytes > 0) ((row.bytesTransferred * 100) / row.sizeBytes).toInt() else 0
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(Dimens.CardPadding)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "$arrow ${row.name}",
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f, fill = false)
                )
                Text(
                    text = "$directionWord ${row.peerName} · ${state.label()}",
                    style = MaterialTheme.typography.labelSmall,
                    // AUDIT-2026-06: B-G8-samples-android-07 — bound the line so a
                    // hostile remote reason can't blow up text layout.
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
            }
            Text(
                text = "$sentKb / $sizeKb KiB ($pct%)",
                style = MaterialTheme.typography.labelSmall
            )
            if (row.destinationPath != null) {
                Text(
                    text = "saved to ${row.destinationPath}",
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            if (row.sha256 != null) {
                Text(
                    text = "sha256 ${row.sha256}",
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            if (isActive) {
                Spacer(Modifier.height(Dimens.SmallGap))
                TextButton(onClick = onCancel) { Text("Cancel") }
            }
        }
    }
}

// AUDIT-2026-06: B-G8-samples-android-07 — remote-supplied reject/cancel
// reasons and error messages are truncated before rendering (a hostile peer
// can ship a reason bounded only by the 8 MiB frame limit).
private fun FileTransferState.label(): String = when (this) {
    is FileTransferState.Offered -> "offered"
    is FileTransferState.Accepted -> "accepted"
    is FileTransferState.Sending -> "sending ${"%.0f".format(progress * 100)}%"
    is FileTransferState.Completed -> "completed"
    is FileTransferState.Rejected -> "rejected" + (reason?.let { " — ${it.take(200)}" } ?: "")
    is FileTransferState.Cancelled -> "cancelled" + (reason?.let { " — ${it.take(200)}" } ?: "")
    is FileTransferState.Failed -> "failed — ${(error.message ?: error::class.simpleName.toString()).take(200)}"
}

@Composable
private fun RoomLine(message: RoomMessage) {
    val style = MaterialTheme.typography.bodyMedium
    // AUDIT-2026-06: B-G8-samples-android-08 — render the timestamp instead of
    // carrying it as a write-only field.
    val time = remember(message.timestamp) {
        SimpleDateFormat("HH:mm:ss", Locale.US).format(Date(message.timestamp))
    }
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
        text = "$time  $prefix${message.displayBody}",
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
    val busy by vm.provisioningBusy.collectAsState()
    val context = LocalContext.current

    // Pick the right runtime permission for the device's API level.
    val perm = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        Manifest.permission.NEARBY_WIFI_DEVICES
    } else {
        Manifest.permission.ACCESS_FINE_LOCATION
    }
    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        vm.refreshMissingPermissions()
        if (granted) {
            vm.startHotspot()
        } else {
            // User denied. Either temporarily (will get the prompt next time)
            // or permanently (system silently returned false). Surface a
            // hint either way so the user understands why the retry didn't.
            vm.notifyPermissionDenied("hotspot host")
        }
    }
    // Device-wide Location toggle is settings-only — no permission API can
    // flip it. Some OEMs (Huawei, MIUI, older Samsung) require it ON even
    // when NEARBY_WIFI_DEVICES is granted.
    // AUDIT-2026-06: C-G8-samples-android-04 — polled as snapshot state
    // (produceState) instead of a binder IPC on every recomposition; also
    // refreshes after returning from the Location settings screen.
    val locationOn by produceState(initialValue = true, context) {
        while (true) {
            value = isLocationModeOn(context)
            delay(5_000)
        }
    }
    val locationOff = !locationOn
    val isLocationProblem = (result as? LocalNetworkResult.Failed)
        ?.error is dev.p2pkit.core.NetworkProvisioningError.PermissionMissingForProvisioning &&
        (((result as LocalNetworkResult.Failed).error
            as dev.p2pkit.core.NetworkProvisioningError.PermissionMissingForProvisioning)
            .permissions.contains(dev.p2pkit.core.permission.P2pPermission.Location))

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(Dimens.CardPadding)) {
            Text(
                text = "Hotspot host (LocalOnlyHotspot)",
                style = MaterialTheme.typography.titleSmall
            )
            Spacer(Modifier.height(Dimens.SmallGap))
            val r = result
            when {
                r is LocalNetworkResult.Started -> {
                    val info = r.manualConnectionInfo
                    Text("SSID: ${r.credentials.ssid ?: "—"}", style = MaterialTheme.typography.bodySmall)
                    Text(
                        // Do not put the hotspot credential in clear text on a
                        // shared screen or screenshot. The platform still owns
                        // the credential; this sample only needs to show that
                        // one was provisioned.
                        text = "Pass: ${if (r.credentials.password != null) "••••••" else "—"}",
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
                    Spacer(Modifier.height(Dimens.ItemGap))
                    Button(
                        onClick = vm::stopHotspot,
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(if (busy) "Working…" else "Stop hotspot")
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
                    Spacer(Modifier.height(Dimens.ItemGap))
                    Button(
                        onClick = vm::stopHotspot,
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(if (busy) "Working…" else "Stop hotspot")
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
                        Spacer(Modifier.height(Dimens.ItemGap))
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
                        Spacer(Modifier.height(Dimens.SmallGap))
                        Button(
                            onClick = vm::startHotspot,
                            enabled = !busy,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(if (busy) "Working…" else "Retry")
                        }
                    } else {
                        Text(
                            text = "Failed: ${r.error::class.simpleName} — ${r.error.message ?: ""}",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Spacer(Modifier.height(Dimens.ItemGap))
                        Button(
                            onClick = {
                                if (missing.isNotEmpty()) launcher.launch(perm) else vm.startHotspot()
                            },
                            enabled = !busy,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                when {
                                    busy -> "Working…"
                                    missing.isNotEmpty() -> "Grant permission and retry"
                                    else -> "Retry"
                                }
                            )
                        }
                    }
                }
                r is LocalNetworkResult.Unsupported -> {
                    Text(
                        text = "Unsupported: ${r.reason}",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                // AUDIT-2026-06: A-G8-samples-android-17 — show the instruction
                // the user must follow instead of falling into the idle branch
                // (previously visible only in logcat).
                r is LocalNetworkResult.RequiresUserAction -> {
                    Text(
                        text = r.instruction,
                        style = MaterialTheme.typography.bodySmall
                    )
                    Spacer(Modifier.height(Dimens.ItemGap))
                    Button(
                        onClick = vm::startHotspot,
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(if (busy) "Working…" else "Retry")
                    }
                }
                else -> {
                    Text(
                        text = "Host a LocalOnlyHotspot so a nearby peer can join (no SIM / no router needed). " +
                            "Random SSID + passphrase chosen by Android.",
                        style = MaterialTheme.typography.bodySmall
                    )
                    if (locationOff) {
                        Spacer(Modifier.height(Dimens.SmallGap))
                        Text(
                            text = "Note: this device's system-wide Location toggle is OFF. " +
                                "Many OEMs require it ON for hotspot hosting. If start fails, " +
                                "enable Location in Settings.",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                    Spacer(Modifier.height(Dimens.ItemGap))
                    Button(
                        onClick = {
                            if (missing.isNotEmpty()) launcher.launch(perm) else vm.startHotspot()
                        },
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            when {
                                busy -> "Working…"
                                missing.isNotEmpty() -> "Grant permission and host hotspot"
                                else -> "Host hotspot"
                            }
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun JoinHotspotCard(vm: P2pKitViewModel) {
    val joinResult by vm.joinResult.collectAsState()
    val missing by vm.missingPermissions.collectAsState()
    val busy by vm.provisioningBusy.collectAsState()

    // AUDIT-2026-06: C-G8-samples-android-05 — rememberSaveable so the SSID /
    // passphrase the tester just copied from the host device survive rotation.
    var ssidInput by rememberSaveable { mutableStateOf("") }
    var passInput by rememberSaveable { mutableStateOf("") }
    // AUDIT-2026-06: A-G8-samples-android-11 — WPA2/WPA3 selectable so
    // WPA3-SAE-only hotspots can be joined.
    var useWpa3 by rememberSaveable { mutableStateOf(false) }
    val security = if (useWpa3) WifiSecurityType.WPA3 else WifiSecurityType.WPA2

    // Pick the right runtime permission for the device's API level.
    val perm = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        Manifest.permission.NEARBY_WIFI_DEVICES
    } else {
        Manifest.permission.ACCESS_FINE_LOCATION
    }
    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        vm.refreshMissingPermissions()
        // AUDIT-2026-06: A-G8-samples-android-20 — resume the join after the
        // grant (the host card already did this); previously the user had to
        // tap the button a second time.
        if (granted) vm.joinHotspot(ssidInput, passInput, security)
        else vm.notifyPermissionDenied("hotspot join")
    }

    val isLocationProblem = (joinResult as? JoinNetworkResult.Failed)
        ?.error is dev.p2pkit.core.NetworkProvisioningError.PermissionMissingForProvisioning &&
        ((joinResult as JoinNetworkResult.Failed).error
            as dev.p2pkit.core.NetworkProvisioningError.PermissionMissingForProvisioning)
            .permissions.contains(dev.p2pkit.core.permission.P2pPermission.Location)

    val context = LocalContext.current
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(Dimens.CardPadding)) {
            Text(
                text = "Join hotspot (WifiNetworkSpecifier)",
                style = MaterialTheme.typography.titleSmall
            )
            Spacer(Modifier.height(Dimens.SmallGap))
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
                    // AUDIT-2026-06: D-G8-samples-android-13 — the process stays
                    // bound to the joined network after dismissing; say so and
                    // label the action honestly instead of "Clear status".
                    Spacer(Modifier.height(Dimens.SmallGap))
                    Text(
                        text = "The join stays active until you stop the kit — dismissing only " +
                            "hides this card.",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Spacer(Modifier.height(Dimens.ItemGap))
                    Button(
                        onClick = vm::clearJoinResult,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("Dismiss — still joined")
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
                        Spacer(Modifier.height(Dimens.ItemGap))
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
                    Spacer(Modifier.height(Dimens.ItemGap))
                    JoinInputs(
                        ssid = ssidInput,
                        onSsidChange = { ssidInput = it },
                        pass = passInput,
                        onPassChange = { passInput = it },
                        useWpa3 = useWpa3,
                        onUseWpa3Change = { useWpa3 = it }
                    )
                    Spacer(Modifier.height(Dimens.SmallGap))
                    Button(
                        onClick = {
                            if (missing.isNotEmpty()) permLauncher.launch(perm)
                            else vm.joinHotspot(ssidInput, passInput, security)
                        },
                        enabled = ssidInput.trim().isNotEmpty() && !busy,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            when {
                                busy -> "Working…"
                                missing.isNotEmpty() -> "Grant permission and retry"
                                else -> "Retry join"
                            }
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
                // AUDIT-2026-06: A-G8-samples-android-17 — a Pending join no
                // longer falls into the idle branch showing an active Join
                // button as if nothing were in flight.
                r is JoinNetworkResult.Pending -> {
                    Text(
                        text = "Join request pending — approve the system dialog if it appears.",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Spacer(Modifier.height(Dimens.SmallGap))
                    TextButton(onClick = vm::clearJoinResult) { Text("Dismiss") }
                }
                else -> {
                    Text(
                        text = "Connect this device to a peer's LocalOnlyHotspot. Enter the SSID + " +
                            "passphrase shown on the host phone's Hotspot card. The OS will prompt " +
                            "you to approve the join.",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Spacer(Modifier.height(Dimens.ItemGap))
                    JoinInputs(
                        ssid = ssidInput,
                        onSsidChange = { ssidInput = it },
                        pass = passInput,
                        onPassChange = { passInput = it },
                        useWpa3 = useWpa3,
                        onUseWpa3Change = { useWpa3 = it }
                    )
                    Spacer(Modifier.height(Dimens.SmallGap))
                    Button(
                        onClick = {
                            if (missing.isNotEmpty()) permLauncher.launch(perm)
                            else vm.joinHotspot(ssidInput, passInput, security)
                        },
                        enabled = ssidInput.trim().isNotEmpty() && !busy,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            when {
                                busy -> "Working…"
                                missing.isNotEmpty() -> "Grant permission and join"
                                else -> "Join hotspot"
                            }
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun JoinInputs(
    ssid: String,
    onSsidChange: (String) -> Unit,
    pass: String,
    onPassChange: (String) -> Unit,
    useWpa3: Boolean,
    onUseWpa3Change: (Boolean) -> Unit
) {
    OutlinedTextField(
        value = ssid,
        onValueChange = onSsidChange,
        label = { Text("SSID") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
    )
    Spacer(Modifier.height(Dimens.SmallGap))
    OutlinedTextField(
        value = pass,
        onValueChange = onPassChange,
        label = { Text("Passphrase (blank = open network)") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth()
    )
    // AUDIT-2026-06: A-G8-samples-android-11 — security type selector (only
    // meaningful for protected networks).
    if (pass.isNotEmpty()) {
        Spacer(Modifier.height(Dimens.SmallGap))
        Row(
            horizontalArrangement = Arrangement.spacedBy(Dimens.ItemGap),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("Security", style = MaterialTheme.typography.bodySmall)
            FilterChip(
                selected = !useWpa3,
                onClick = { onUseWpa3Change(false) },
                label = { Text("WPA2") }
            )
            FilterChip(
                selected = useWpa3,
                onClick = { onUseWpa3Change(true) },
                label = { Text("WPA3") }
            )
        }
    }
}

@Composable
private fun PeerCard(
    peer: Peer,
    session: P2pSession?,
    isConnecting: Boolean,
    onConnect: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(Dimens.CardPadding),
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
            // AUDIT-2026-06: A-G8-samples-android-18 — label derives from the
            // session's actual state; a Reconnecting session no longer reads
            // "Connected".
            val sessionState = session?.state?.collectAsState()?.value
            when {
                sessionState == ConnectionState.Connected ->
                    Text(text = "Connected", style = MaterialTheme.typography.labelSmall)
                sessionState != null ->
                    Text(text = sessionState.name, style = MaterialTheme.typography.labelSmall)
                isConnecting ->
                    Text(text = "Connecting…", style = MaterialTheme.typography.labelSmall)
                else -> TextButton(onClick = onConnect) { Text("Connect") }
            }
        }
    }
}
