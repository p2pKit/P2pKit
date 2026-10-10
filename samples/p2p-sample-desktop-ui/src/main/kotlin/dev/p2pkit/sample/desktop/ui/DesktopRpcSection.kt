package dev.p2pkit.sample.desktop.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.awt.SwingPanel
import androidx.compose.ui.unit.dp
import dev.p2pkit.sample.rpc.desktop.RpcDesktopPanel
import java.awt.Window
import java.awt.event.WindowAdapter
import java.awt.event.WindowEvent
import javax.swing.SwingUtilities

/** Reuses the RPC workspace inside the maintained window; no preview process or second JFrame. */
@Composable
internal fun DesktopRpcSection(panel: RpcDesktopPanel, window: Window, leaving: Boolean, cleanupFailed: Boolean) {
    DisposableEffect(panel, window) {
        val listener = object : WindowAdapter() {
            override fun windowGainedFocus(event: WindowEvent) = panel.onWindowFocusChanged(true)
            override fun windowLostFocus(event: WindowEvent) = panel.onWindowFocusChanged(false)
        }
        window.addWindowFocusListener(listener)
        SwingUtilities.invokeLater { panel.onWindowFocusChanged(window.isActive) }
        onDispose { window.removeWindowFocusListener(listener) }
    }
    Column(Modifier.fillMaxSize()) {
        Surface(color = MaterialTheme.colorScheme.secondaryContainer, modifier = Modifier.fillMaxWidth()) {
            Text(
                "RPC sample · Persistent trust and explicit first-time approval. " +
                    "Separate from the room sample's permissive development policy.",
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.bodySmall,
            )
        }
        if (leaving || cleanupFailed) {
            Text(
                if (cleanupFailed) "RPC is busy or cleanup is unverified. Finish unlocking or review the retained error."
                else "Closing the RPC section and its protected profile…",
                modifier = Modifier.padding(12.dp),
            )
        }
        SwingPanel(factory = { panel }, modifier = Modifier.weight(1f).fillMaxWidth())
    }
}
