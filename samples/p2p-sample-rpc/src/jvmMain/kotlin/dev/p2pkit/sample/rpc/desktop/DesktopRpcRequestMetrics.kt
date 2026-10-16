package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcMetricCard
import java.awt.BorderLayout
import java.awt.Font
import java.awt.GridLayout
import javax.swing.BorderFactory
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.SwingConstants

/** Latest-value-only counters; unknown state is hidden, never presented as measured zeros. */
internal class DesktopRpcRequestMetrics : JPanel(GridLayout(0, 4, 8, 8)) {
    private var rendered: List<RpcMetricCard>? = null

    fun render(metrics: List<RpcMetricCard>?) {
        if (rendered == metrics) return
        rendered = metrics?.toList()
        removeAll()
        metrics.orEmpty().forEach { metric ->
            add(JPanel(BorderLayout()).apply {
                border = BorderFactory.createCompoundBorder(BorderFactory.createEtchedBorder(),
                    BorderFactory.createEmptyBorder(6, 6, 6, 6))
                add(JLabel(metric.label, SwingConstants.CENTER), BorderLayout.NORTH)
                add(JLabel(metric.value.toString(), SwingConstants.CENTER).apply {
                    name = "rpc.metric.${metric.id}"
                    font = font.deriveFont(Font.BOLD, 22f)
                    accessibleContext.accessibleName = "${metric.label}: ${metric.value}"
                }, BorderLayout.CENTER)
            })
        }
        revalidate()
        repaint()
    }
}
