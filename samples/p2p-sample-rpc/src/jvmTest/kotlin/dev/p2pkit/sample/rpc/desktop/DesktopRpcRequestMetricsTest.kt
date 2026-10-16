package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcMetricCard
import java.awt.Container
import javax.swing.JLabel
import javax.swing.SwingUtilities
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertSame

class DesktopRpcRequestMetricsTest {
    @Test
    fun metricsHaveAccessibleExactValuesAndUnknownStateDoesNotInventZeros() {
        SwingUtilities.invokeAndWait {
            val panel = DesktopRpcRequestMetrics()
            assertEquals(0, panel.componentCount)
            val rows = listOf(RpcMetricCard("success", "Succeeded", 2), RpcMetricCard("failed", "RPC failures", 3))
            panel.render(rows)
            val first = panel.components[0]
            val value = (first as Container).components.filterIsInstance<JLabel>().single { it.name != null }
            assertEquals("2", value.text)
            assertEquals("Succeeded: 2", value.accessibleContext.accessibleName)
            panel.render(rows)
            assertSame(first, panel.components[0], "An unchanged 500 ms sample cannot rebuild the cards")
            panel.render(null)
            assertEquals(0, panel.componentCount)
        }
    }
}
