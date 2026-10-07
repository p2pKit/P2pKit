package dev.p2pkit.sample.android.rpclab

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.p2pkit.sample.rpc.RpcNearbyHost

/** Local identity UI only. Dismiss/Back never approves, selects or revokes anything. */
@Composable
internal fun RpcLabDiscoveryPanel(
    snapshot: RpcLabLiveSnapshot?, enabled: Boolean,
    select: (RpcNearbyHost) -> Unit,
    decide: (RpcLabPendingRequest, Boolean) -> Unit,
    forget: (String) -> Unit,
) {
    var chosen by remember { mutableStateOf<RpcNearbyHost?>(null) }
    var approval by remember { mutableStateOf<RpcLabPendingRequest?>(null) }
    var dismissed by remember { mutableStateOf<String?>(null) }
    var revocation by remember { mutableStateOf<String?>(null) }
    val pending = snapshot?.pending.orEmpty()
    LaunchedEffect(pending) {
        if (approval != null && approval !in pending) approval = null
        if (dismissed != null && pending.none { it.requestId == dismissed }) dismissed = null
        if (approval == null && chosen == null && revocation == null) {
            approval = pending.firstOrNull { it.requestId != dismissed }
        }
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("${if (snapshot?.asHost == true) "Advertising" else "Discovery"}: " +
            (snapshot?.networkActivity ?: "Not observed"))
        snapshot?.connection?.let {
            Text("Connection: ${it.state.name}; retry delay: ${it.nextRetryMillis} ms")
            it.failure?.let { code -> Text("Connection issue: $code") }
            it.approvalGuidance?.let { guidance -> Text(guidance) }
            it.selectedFingerprint?.let { pin -> SelectionContainer { Text("Selected host: $pin") } }
        }
        if (snapshot?.asHost == false) {
            Text("Nearby hosts — names and discovery presence are unverified")
            if (snapshot.nearby.isEmpty()) Text("No current host records. Discovery alone does not prove reachability.")
            snapshot.nearby.forEach { host ->
                Card {
                    Column(Modifier.padding(12.dp)) {
                        Text("${host.name} · ${host.platform} · " +
                            if (host.trusted) "Trusted identity" else "Untrusted")
                        SelectionContainer { Text(host.fingerprint) }
                        TextButton({ chosen = host }, enabled = enabled && approval == null) {
                            Text(host.selectionLabel(snapshot.connection))
                        }
                    }
                }
            }
        }
        if (snapshot?.asHost == true) {
            Text("Pending approvals: ${pending.size}")
            pending.forEach { request ->
                TextButton({ approval = request }, enabled = enabled) { Text("Review ${request.fingerprint}") }
            }
        }
        Text("Trusted devices")
        if (snapshot?.trusted.isNullOrEmpty()) Text("No saved approvals for this role.")
        snapshot?.trusted.orEmpty().forEach { device ->
            Card {
                Column(Modifier.padding(12.dp)) {
                    Text("${device.name} · ${device.presence}")
                    SelectionContainer { Text(device.fingerprint) }
                    TextButton({ revocation = device.fingerprint }, enabled = enabled && approval == null) {
                        Text("Revoke / Forget device")
                    }
                }
            }
        }
    }
    chosen?.let { host ->
        val current = snapshot?.nearby?.singleOrNull { it.fingerprint == host.fingerprint }
        AlertDialog(onDismissRequest = { chosen = null }, title = { Text("Select this host identity?") },
            text = { Text("${host.name}\n${host.platform}\n${host.fingerprint}\n" +
                "Discovery names can be spoofed. Compare the full fingerprint on the other device. " +
                "Without comparison this is trust on first use. The host must separately approve your identity.") },
            confirmButton = { TextButton({ chosen = null; select(host) }, enabled = enabled && current != null) {
                Text(host.selectionLabel(snapshot?.connection))
            } }, dismissButton = { TextButton({ chosen = null }) { Text("Cancel") } })
    }
    approval?.let { request ->
        AlertDialog(onDismissRequest = { dismissed = request.requestId; approval = null },
            title = { Text("Client requests approval") }, text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    Text("Authenticated client fingerprint:\n${request.fingerprint}\nOrigin: ${request.origin}\n" +
                        "Compare this with the client display. Approval saves this identity, not its name or address.")
                }
            }, confirmButton = { TextButton({ approval = null; decide(request, true) },
                enabled = enabled && request in pending) { Text("Approve exact identity") } },
            dismissButton = { TextButton({ approval = null; decide(request, false) },
                enabled = enabled && request in pending) { Text("Reject") } })
    }
    revocation?.let { pin ->
        AlertDialog(onDismissRequest = { revocation = null }, title = { Text("Forget this identity?") },
            text = { Text("$pin\nDisconnect and revoke trust. A future connection requires new approval.") },
            confirmButton = { TextButton({ revocation = null; forget(pin) },
                enabled = enabled && snapshot?.trusted?.any { it.fingerprint == pin } == true) { Text("Revoke") } },
            dismissButton = { TextButton({ revocation = null }) { Text("Cancel") } })
    }
}
