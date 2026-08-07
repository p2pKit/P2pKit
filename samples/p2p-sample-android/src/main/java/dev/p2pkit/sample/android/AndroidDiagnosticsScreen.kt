package dev.p2pkit.sample.android

import android.content.ClipData
import android.content.Intent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import dev.p2pkit.sample.diagnostics.DiagnosticEvent
import dev.p2pkit.sample.diagnostics.DiagnosticFilter
import dev.p2pkit.sample.diagnostics.DiagnosticOutcome
import dev.p2pkit.sample.diagnostics.DiagnosticSeverity
import dev.p2pkit.sample.diagnostics.diagnosticJson

/**
 * Test-only, in-application evidence viewer. It reads the same bounded
 * recorder that receives SDK, frame, transport, UI, and transfer events.
 */
@Composable
internal fun AndroidDiagnosticsScreen(
    vm: P2pKitViewModel,
    onBack: () -> Unit,
    paddingValues: PaddingValues = PaddingValues()
) {
    @Suppress("UNUSED_VARIABLE")
    val revision by vm.diagnosticRevision.collectAsState()
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    var requestedSession by rememberSaveable { mutableStateOf("") }
    var transferFilter by rememberSaveable { mutableStateOf("") }
    var sessionFilter by rememberSaveable { mutableStateOf("") }
    var search by rememberSaveable { mutableStateOf("") }
    var severity by rememberSaveable { mutableStateOf<DiagnosticSeverity?>(null) }
    var paused by rememberSaveable { mutableStateOf(false) }
    var pausedEvents by remember { mutableStateOf<List<DiagnosticEvent>>(emptyList()) }
    var showClearConfirmation by remember { mutableStateOf(false) }
    val selected = remember { mutableStateListOf<Long>() }

    val filter = DiagnosticFilter(
        testId = vm.diagnosticRecorder.activeTestId.takeUnless { it == "UNASSIGNED" },
        sessionId = sessionFilter.trim().takeIf { it.isNotEmpty() },
        transferId = transferFilter.trim().takeIf { it.isNotEmpty() },
        minimumSeverity = severity,
        search = search.trim().takeIf { it.isNotEmpty() }
    )
    val liveEvents = vm.diagnosticEvents(filter)
    val events = if (paused) pausedEvents else liveEvents
    val summary = vm.diagnosticSummary()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(paddingValues)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = onBack) { Text("Back") }
            Text("Test diagnostics", style = MaterialTheme.typography.titleLarge)
        }
        Text(
            "test=${summary.testId}  session=${summary.testSessionId}  role=${summary.role}",
            style = MaterialTheme.typography.bodySmall
        )
        Text(
            "connection=${summary.connectionIds.lastOrNull() ?: "—"}  " +
                "transfer=${summary.transferIds.lastOrNull() ?: "—"}  " +
                "protocol=${summary.protocolVersion}",
            style = MaterialTheme.typography.bodySmall
        )
        Text(
            "state=${summary.finalState ?: "active"}  outcome=${summary.finalOutcome ?: "pending"}  " +
                "senderSHA=${summary.senderSha256?.take(12) ?: "—"}  " +
                "receiverSHA=${summary.receiverSha256?.take(12) ?: "—"}  " +
                "match=${summary.integrityMatch ?: "—"}",
            style = MaterialTheme.typography.bodySmall
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = vm.diagnosticTestId,
                onValueChange = vm::updateDiagnosticTestId,
                label = { Text("Test ID") },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
            OutlinedTextField(
                value = vm.diagnosticRole,
                onValueChange = vm::updateDiagnosticRole,
                label = { Text("Role") },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
        }
        OutlinedTextField(
            value = requestedSession,
            onValueChange = {
                requestedSession = it.filter { char ->
                    char.isLetterOrDigit() || char == '-' || char == '_' || char == '.'
                }.take(80)
            },
            label = { Text("Shared session ID (blank = generate)") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = {
                    vm.beginDiagnosticSession(requestedSession.ifBlank { null })
                    requestedSession = vm.diagnosticRecorder.activeSessionId
                }
            ) { Text("Begin test session") }
            Button(onClick = {
                if (!paused) pausedEvents = liveEvents
                paused = !paused
            }) { Text(if (paused) "Resume live logs" else "Pause live logs") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = { vm.completeDiagnostic(DiagnosticOutcome.SUCCESS) }) {
                Text("Complete success")
            }
            TextButton(onClick = { vm.completeDiagnostic(DiagnosticOutcome.FAILURE) }) {
                Text("Complete failure")
            }
            TextButton(onClick = { vm.completeDiagnostic(DiagnosticOutcome.CANCELLATION) }) {
                Text("Complete cancelled")
            }
        }

        OutlinedTextField(
            value = search,
            onValueChange = { search = it.take(96) },
            label = { Text("Search event, error, peer, packet") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = sessionFilter,
                onValueChange = { sessionFilter = it.take(80) },
                label = { Text("Session filter") },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
            OutlinedTextField(
                value = transferFilter,
                onValueChange = { transferFilter = it.take(80) },
                label = { Text("Transfer filter") },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf(null, DiagnosticSeverity.WARNING, DiagnosticSeverity.ERROR).forEach { candidate ->
                FilterChip(
                    selected = severity == candidate,
                    onClick = { severity = candidate },
                    label = { Text(candidate?.name ?: "All levels") }
                )
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                clipboard.setText(AnnotatedString(vm.diagnosticRecorder.jsonLines()))
            }) { Text("Copy current session") }
            Button(
                enabled = selected.isNotEmpty(),
                onClick = {
                    val text = events.filter { it.index in selected }
                        .joinToString("\n", postfix = "\n", transform = ::diagnosticJson)
                    clipboard.setText(AnnotatedString(text))
                }
            ) { Text("Copy selected") }
            Button(onClick = {
                val file = vm.exportDiagnosticEvidence() ?: return@Button
                val uri = FileProvider.getUriForFile(
                    context,
                    "${context.packageName}.test-evidence",
                    file
                )
                val share = Intent(Intent.ACTION_SEND).apply {
                    type = "application/zip"
                    putExtra(Intent.EXTRA_STREAM, uri)
                    clipData = ClipData.newRawUri(file.name, uri)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                context.startActivity(Intent.createChooser(share, "Share Test Evidence"))
            }) { Text("Export Test Evidence") }
            TextButton(onClick = { showClearConfirmation = true }) { Text("Clear session") }
        }

        Text(
            "${events.size} event(s)${if (paused) " — display paused" else ""}; " +
                "tap rows to select",
            style = MaterialTheme.typography.labelMedium
        )
        LazyColumn(
            modifier = Modifier.fillMaxWidth().height(360.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            items(events, key = { it.index }) { event ->
                DiagnosticEventCard(
                    event = event,
                    selected = event.index in selected,
                    onToggle = {
                        if (event.index in selected) selected.remove(event.index)
                        else selected.add(event.index)
                    }
                )
            }
        }
    }

    if (showClearConfirmation) {
        AlertDialog(
            onDismissRequest = { showClearConfirmation = false },
            title = { Text("Clear current test session?") },
            text = { Text("Only ${summary.testSessionId} will be removed. Other sessions remain.") },
            confirmButton = {
                TextButton(onClick = {
                    vm.clearCurrentDiagnosticSession()
                    selected.clear()
                    pausedEvents = emptyList()
                    showClearConfirmation = false
                }) { Text("Clear current session") }
            },
            dismissButton = {
                TextButton(onClick = { showClearConfirmation = false }) { Text("Cancel") }
            }
        )
    }
}

@Composable
private fun DiagnosticEventCard(
    event: DiagnosticEvent,
    selected: Boolean,
    onToggle: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onToggle)
    ) {
        Column(modifier = Modifier.padding(8.dp)) {
            Text(
                "${event.timestamp} ${event.severity} ${event.eventName}",
                style = MaterialTheme.typography.labelMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Text(
                buildString {
                    append(if (selected) "selected · " else "")
                    append(event.direction)
                    event.connectionId?.let { append(" conn=").append(it) }
                    event.transferId?.let { append(" xfer=").append(it) }
                    event.packetType?.let { append(" packet=").append(it) }
                    event.currentState?.let { append(" state=").append(it) }
                    event.errorCode?.let { append(" error=").append(it) }
                },
                style = MaterialTheme.typography.bodySmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}
