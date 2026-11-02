package dev.p2pkit.sample.android.rpclab

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.p2pkit.sample.rpc.RpcDeviceTestPhase
import dev.p2pkit.sample.rpc.RpcDeviceTestSession
import dev.p2pkit.sample.rpc.RpcPhoneLab
import dev.p2pkit.sample.rpc.RpcPhysicalTestCatalog
import kotlinx.coroutines.delay

@Composable
internal fun RpcPhysicalTestPanel(tests: RpcDeviceTestSession, enabled: Boolean,
    run: (RpcDeviceTestPhase) -> Unit, changed: () -> Unit) {
    val center = tests.physicalTests
    val active by center.changes.collectAsState()
    var selected by remember { mutableStateOf(RpcPhysicalTestCatalog.cases.first().id) }
    var reference by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    var seconds by remember { mutableStateOf(0L) }
    val test = RpcPhysicalTestCatalog.find(active?.caseId ?: selected)
    LaunchedEffect(active?.sessionId) {
        while (active != null) { seconds = center.elapsedMillis / 1_000; delay(1_000) }
    }
    fun action(block: () -> Unit) {
        if (!enabled) return
        try { block(); changed(); message = "Recorded locally; inspect saved results and storage status." }
        catch (_: Exception) { message = "Action refused. Check steps, duration, evidence reference and storage status." }
    }
    Column {
        Text("Test Center", style = MaterialTheme.typography.headlineSmall)
        Text("Run built-in tests or follow a physical procedure. External tools and hardware remain required where shown.")
        RpcLabDisclosure("Choose a physical test") {
            RpcPhysicalTestCatalog.cases.forEach { item ->
                TextButton({ selected = item.id; reference = ""; notes = "" }, enabled = active == null) {
                    Text(item.summary)
                }
            }
        }
        Text(test.title, style = MaterialTheme.typography.titleMedium)
        Text(test.equipment)
        Text("Method: ${test.tool}")
        test.steps.forEachIndexed { index, step ->
            Row(Modifier.padding(vertical = 4.dp)) {
                Checkbox(index in active?.observedSteps.orEmpty(), { checked ->
                    action { center.observeStep(index, checked) }
                }, enabled = enabled && active != null)
                Text("${index + 1}. $step")
            }
        }
        Text("Evidence to save: ${test.evidence}")
        Text("Minimum observation ${test.minimumSeconds}s · elapsed ${if (active != null) seconds else 0}s")
        val phase = test.phase
        if (phase != null) {
            Button({ run(phase) }, enabled = enabled && active == null) { Text("Open RPC test controls") }
        } else {
            Button({ action { center.start(test.id, RpcPhoneLab.compiledSource, "Android") } },
                enabled = enabled && active == null) { Text("Start guided observation") }
        }
        OutlinedTextField(reference, { if (it.encodeToByteArray().size <= 1_024) reference = it },
            label = { Text("Private evidence reference or saved run IDs") }, enabled = enabled && active != null)
        OutlinedTextField(notes, { if (it.encodeToByteArray().size <= 4_096) notes = it },
            label = { Text("What happened / missing setup") }, enabled = enabled && active != null)
        if (active != null) {
            TextButton({ action { center.checkpoint(reference, notes) } }, enabled = enabled) { Text("Save checkpoint") }
            listOf("AwaitingReview" to "Save for review", "Failed" to "Record failure",
                "Blocked" to "Record missing setup", "Interrupted" to "End observation").forEach { (code, title) ->
                TextButton({ action { center.finish(code, reference, notes) } }, enabled = enabled) { Text(title) }
            }
        }
        Text(message)
        Text("Marked steps are operator observations. Only reviewed evidence establishes qualification.",
            style = MaterialTheme.typography.bodySmall)
    }
}
