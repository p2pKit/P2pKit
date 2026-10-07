package dev.p2pkit.sample.rpc.desktop

import java.awt.Color
import java.awt.Font
import javax.swing.BorderFactory
import javax.swing.JLabel
import javax.swing.JPanel

/** Appearance-only components; no timer, peer selection, payload capture or network ownership. */
internal object DesktopRpcAppearance {
    val background = Color(0xF3F6FA)
    val surface = Color.WHITE
    val ink = Color(0x172B40)
    val accent = Color(0x205EA6)

    fun hero(): JPanel = DesktopRpcColumn().apply {
        background = Color(0xEAF3FF)
        border = BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(Color(0xCADBF0)), BorderFactory.createEmptyBorder(18, 18, 18, 18))
        add(JLabel("LOCAL API WORKSPACE").apply { foreground = accent })
        add(JLabel("P2pKit RPC").apply { font = font.deriveFont(Font.BOLD, 30f); foreground = ink })
        add(DesktopRpcWrappedLabel("Discover a host, approve its identity, and explore your local API.")
            .apply { foreground = ink })
    }

    fun heading(title: String): JLabel = JLabel(title).apply {
        font = font.deriveFont(Font.BOLD, 20f)
        foreground = ink
        border = BorderFactory.createEmptyBorder(20, 0, 10, 0)
    }
}
