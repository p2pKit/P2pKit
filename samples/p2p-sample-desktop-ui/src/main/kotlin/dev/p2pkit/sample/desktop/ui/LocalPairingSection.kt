package dev.p2pkit.sample.desktop.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextDirection
import dev.p2pkit.sample.diagnostics.LocalPairingInfo

/** Full selectable identity, only after explicit disclosure; never append it to a log. */
@Composable
internal fun LocalPairingSection(info: LocalPairingInfo) {
    var revealed by remember(info.qr) { mutableStateOf(false) }
    Column(modifier = Modifier.fillMaxWidth()) {
        TextButton(onClick = { revealed = !revealed }) {
            Text(if (revealed) "Hide local pairing information" else "Show local pairing information")
        }
        if (revealed) {
            Text(
                "Share with the intended peer through a trusted channel. Do not include in diagnostic exports.",
                style = MaterialTheme.typography.bodySmall
            )
            SelectionContainer {
                Column {
                    Text("Local fingerprint", style = MaterialTheme.typography.labelSmall)
                    Text(
                        info.fingerprint,
                        style = MaterialTheme.typography.bodySmall.copy(textDirection = TextDirection.Ltr)
                    )
                    Text("Local pairing QR text", style = MaterialTheme.typography.labelSmall)
                    Text(
                        info.qr,
                        style = MaterialTheme.typography.bodySmall.copy(textDirection = TextDirection.Ltr)
                    )
                }
            }
            Text(
                "Identity changes after Stop/Start. Incoming same-AppId peers are still accepted.",
                style = MaterialTheme.typography.bodySmall
            )
        }
    }
}
