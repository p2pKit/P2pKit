package dev.p2pkit.sample.android.rpclab

import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import dev.p2pkit.sample.rpc.RpcTestArchivePage

@Composable
internal fun RpcTestArchivePanel(page: RpcTestArchivePage?, enabled: Boolean,
    browse: (Long, String) -> Unit, export: (String?) -> Unit) {
    RpcLabSectionHeading("Saved test archive", "Original output per test; loading does not replay a test")
    Button({ browse(Long.MAX_VALUE, "") }, enabled = enabled) { Text("Load newest saved results") }
    if (page != null) {
        page.reports.forEach { report ->
            RpcLabDisclosure(report.title) {
                Text(report.detail)
                Button({ export(report.runId) }, enabled = enabled) { Text("Share this output") }
            }
        }
        if (page.reports.isEmpty()) Text("No saved outputs.")
        if (page.olderAvailable) Button({ browse(page.beforeMillis, page.beforeRunId) }, enabled = enabled) {
            Text("Older results")
        }
    }
    Button({ export(null) }, enabled = enabled) { Text("Share all saved outputs") }
}
