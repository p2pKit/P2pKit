package dev.p2pkit.sample.desktop.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.p2pkit.sample.diagnostics.DiagnosticEvent
import dev.p2pkit.sample.diagnostics.DiagnosticFilter
import dev.p2pkit.sample.diagnostics.DiagnosticOutcome
import dev.p2pkit.sample.diagnostics.DiagnosticSeverity
import dev.p2pkit.sample.diagnostics.diagnosticJson
import java.awt.Desktop
import java.awt.Toolkit
import java.awt.datatransfer.StringSelection

@Composable
internal fun DesktopDiagnosticsScreen(
    diagnostics: DesktopDiagnosticHarness,
    revision: Long,
    onBack: () -> Unit
) {
    var testId by remember { mutableStateOf(diagnostics.recorder.activeTestId) }
    var role by remember { mutableStateOf(diagnostics.recorder.activeRole) }
    var requestedSession by remember { mutableStateOf(diagnostics.recorder.activeSessionId) }
    var sessionFilter by remember { mutableStateOf("") }
    var transferFilter by remember { mutableStateOf("") }
    var search by remember { mutableStateOf("") }
    var severity by remember { mutableStateOf<DiagnosticSeverity?>(null) }
    var paused by remember { mutableStateOf(false) }
    var pausedEvents by remember { mutableStateOf<List<DiagnosticEvent>>(emptyList()) }
    var showClearConfirmation by remember { mutableStateOf(false) }
    var exportStatus by remember { mutableStateOf<String?>(null) }
    val selected = remember { mutableStateListOf<Long>() }

    val filter = DiagnosticFilter(
        testId = diagnostics.recorder.activeTestId,
        sessionId = sessionFilter.trim().takeIf(String::isNotEmpty),
        transferId = transferFilter.trim().takeIf(String::isNotEmpty),
        minimumSeverity = severity,
        search = search.trim().takeIf(String::isNotEmpty)
    )
    val liveEvents = remember(revision, filter) { diagnostics.recorder.snapshot(filter) }
    val events = if (paused) pausedEvents else liveEvents
    val summary = diagnostics.summary()

    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = onBack) { Text("Back") }
            Text("Test diagnostics", style = MaterialTheme.typography.headlineSmall)
        }
        Text(
            "test=${summary.testId}  session=${summary.testSessionId}  role=${summary.role}",
            style = MaterialTheme.typography.bodySmall
        )
        Text(
            "connection=${summary.connectionIds.lastOrNull() ?: "—"}  " +
                "transfer=${summary.transferIds.lastOrNull() ?: "—"}  " +
                "protocol=${summary.protocolVersion}  final=${summary.finalOutcome ?: "pending"}",
            style = MaterialTheme.typography.bodySmall
        )
        Text(
            "senderSHA=${summary.senderSha256?.take(12) ?: "—"}  " +
                "receiverSHA=${summary.receiverSha256?.take(12) ?: "—"}  " +
                "integrity=${summary.integrityMatch ?: "—"}",
            style = MaterialTheme.typography.bodySmall
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = testId,
                onValueChange = {
                    testId = it.filter { c -> c.isLetterOrDigit() || c == '-' || c == '_' }
                        .uppercase().take(64)
                },
                label = { Text("Test ID") },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
            OutlinedTextField(
                value = role,
                onValueChange = {
                    role = it.filter { c -> c.isLetterOrDigit() || c == '-' || c == '_' }
                        .lowercase().take(24)
                },
                label = { Text("Role") },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
        }
        OutlinedTextField(
            value = requestedSession,
            onValueChange = {
                requestedSession = it.filter { c ->
                    c.isLetterOrDigit() || c == '-' || c == '_' || c == '.'
                }.take(80)
            },
            label = { Text("Shared session ID (blank = generate)") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                runCatching {
                    requestedSession = diagnostics.startSession(
                        testId,
                        role,
                        requestedSession.ifBlank { null }
                    )
                }.onFailure { exportStatus = "Could not start session: ${it.message}" }
            }) { Text("Begin test session") }
            Button(onClick = {
                if (!paused) pausedEvents = liveEvents
                paused = !paused
            }) { Text(if (paused) "Resume live logs" else "Pause live logs") }
            TextButton(onClick = { diagnostics.complete(DiagnosticOutcome.SUCCESS) }) {
                Text("Complete success")
            }
            TextButton(onClick = { diagnostics.complete(DiagnosticOutcome.FAILURE) }) {
                Text("Complete failure")
            }
            TextButton(onClick = { diagnostics.complete(DiagnosticOutcome.CANCELLATION) }) {
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
            listOf(null, DiagnosticSeverity.WARNING, DiagnosticSeverity.ERROR).forEach { candidate ->
                FilterChip(
                    selected = severity == candidate,
                    onClick = { severity = candidate },
                    label = { Text(candidate?.name ?: "All") }
                )
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                copyText(diagnostics.recorder.jsonLines())
                exportStatus = "Current session copied"
            }) { Text("Copy current session") }
            Button(
                enabled = selected.isNotEmpty(),
                onClick = {
                    copyText(
                        events.filter { it.index in selected }
                            .joinToString("\n", postfix = "\n", transform = ::diagnosticJson)
                    )
                    exportStatus = "${selected.size} selected event(s) copied"
                }
            ) { Text("Copy selected") }
            Button(onClick = {
                runCatching { diagnostics.export() }
                    .onSuccess { file ->
                        exportStatus = "Exported ${file.absolutePath}"
                        runCatching {
                            if (Desktop.isDesktopSupported()) Desktop.getDesktop().open(file.parentFile)
                        }
                    }
                    .onFailure { exportStatus = "Export failed: ${it.message}" }
            }) { Text("Export Test Evidence") }
            TextButton(onClick = { showClearConfirmation = true }) { Text("Clear session") }
        }
        exportStatus?.let { Text(it, style = MaterialTheme.typography.bodySmall) }

        Text(
            "${events.size} event(s)${if (paused) " — display paused" else ""}; tap rows to select",
            style = MaterialTheme.typography.labelMedium
        )
        LazyColumn(
            modifier = Modifier.fillMaxWidth().height(420.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            items(events, key = { it.index }) { event ->
                DesktopDiagnosticEvent(
                    event,
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
            text = { Text("Only ${summary.testSessionId} will be removed.") },
            confirmButton = {
                TextButton(onClick = {
                    diagnostics.clearCurrent()
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
private fun DesktopDiagnosticEvent(
    event: DiagnosticEvent,
    selected: Boolean,
    onToggle: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth().clickable(onClick = onToggle)) {
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

private fun copyText(value: String) {
    Toolkit.getDefaultToolkit().systemClipboard.setContents(StringSelection(value), null)
}
