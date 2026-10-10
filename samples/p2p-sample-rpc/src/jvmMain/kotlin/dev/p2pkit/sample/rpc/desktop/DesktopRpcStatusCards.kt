package dev.p2pkit.sample.rpc.desktop

import java.awt.BorderLayout
import java.awt.Color
import java.awt.Font
import java.awt.GridLayout
import javax.swing.BorderFactory
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.SwingConstants

/** Four bounded, latest-value-only cards. An unavailable observation is not a measured zero. */
internal class DesktopRpcStatusCards : JPanel(GridLayout(1, 4, 8, 0)) {
    private val labels = DesktopRpcRole.Host.cardLabels
    private val titles = labels.map { JLabel(it, SwingConstants.CENTER) }
    private val values = labels.map { title ->
        JLabel("—", SwingConstants.CENTER).apply {
            name = "rpc${title}Count"
            font = font.deriveFont(Font.BOLD, 26f)
            accessibleContext.accessibleName = "$title: unavailable"
        }
    }

    init {
        val accents = listOf(Color(0x205EA6), Color(0x8A5200), Color(0x267347), Color(0x7148A8))
        val backgrounds = listOf(Color(0xEAF3FF), Color(0xFFF3D7), Color(0xE8F6ED), Color(0xF2ECFF))
        labels.indices.forEach { index ->
            add(JPanel(BorderLayout(0, 4)).apply {
                background = backgrounds[index]
                border = BorderFactory.createCompoundBorder(
                    BorderFactory.createLineBorder(accents[index], 2),
                    BorderFactory.createEmptyBorder(8, 8, 8, 8),
                )
                add(titles[index].apply {
                    foreground = accents[index]
                    font = font.deriveFont(Font.BOLD)
                }, BorderLayout.NORTH)
                values[index].foreground = accents[index]
                add(values[index], BorderLayout.CENTER)
            })
        }
    }

    fun render(status: DesktopRpcStatus?, role: DesktopRpcRole? = status?.role) {
        val labels = (role ?: DesktopRpcRole.Host).cardLabels
        val counts = status?.counts ?: List(labels.size) { "—" }
        values.forEachIndexed { index, value ->
            if (titles[index].text != labels[index]) {
                titles[index].text = labels[index]
                value.font = value.font.deriveFont(if (index == 1 && role == DesktopRpcRole.Client) 14f else 26f)
            }
            if (value.text != counts[index]) {
                value.text = counts[index]
            }
            val description = "${labels[index]}: " + if (status == null) "unavailable" else counts[index]
            if (value.accessibleContext.accessibleName != description) {
                value.accessibleContext.accessibleName = description
            }
        }
    }
}
