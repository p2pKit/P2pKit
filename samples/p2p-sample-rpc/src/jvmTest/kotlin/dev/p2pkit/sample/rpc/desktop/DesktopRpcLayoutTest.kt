package dev.p2pkit.sample.rpc.desktop

import java.awt.Dimension
import java.awt.GridLayout
import javax.swing.JButton
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.JScrollPane
import javax.swing.SwingUtilities
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class DesktopRpcLayoutTest {
    @Test fun dashboardTracksViewportAndKeepsAllCardsAndLabelsLeadingAligned() {
        SwingUtilities.invokeAndWait {
            for (width in listOf(760, 1000, 1400)) {
                val column = DesktopRpcColumn()
                val label = JLabel("Compiled source: " + "a".repeat(40))
                val cards = JPanel(GridLayout(1, 4)).apply {
                    repeat(4) { add(JLabel("Card $it").apply { preferredSize = Dimension(320, 60) }) }
                }
                column.add(label); column.add(cards)
                val scroll = JScrollPane(column)
                scroll.setSize(width, 640)
                scroll.doLayout(); scroll.viewport.doLayout(); column.doLayout(); cards.doLayout()
                assertEquals(scroll.viewport.extentSize.width, column.width)
                for (child in column.components) {
                    assertEquals(0, child.x)
                    assertTrue(child.width <= column.width)
                }
                assertEquals(4, cards.componentCount)
                for (card in cards.components) assertTrue(card.x + card.width <= column.width)
            }
        }
    }

    @Test fun controlsWrappingOntoAnotherRowReceiveEnoughHeight() {
        SwingUtilities.invokeAndWait {
            val row = JPanel(DesktopRpcWrapLayout())
            repeat(6) { row.add(JButton("Action $it").apply { preferredSize = Dimension(150, 30) }) }
            row.setSize(760, 200)
            val wrapped = row.preferredSize.height
            assertTrue(wrapped >= 70)
            row.setSize(1400, 200)
            assertTrue(row.preferredSize.height < wrapped)
            row.setSize(760, wrapped); row.doLayout()
            row.components.forEach { assertTrue(it.y + it.height <= row.height) }
        }
    }

    @Test fun wrappedStatusEscapesMarkupAndPreservesPlainAccessibleName() {
        SwingUtilities.invokeAndWait {
            val raw = "Connection <img src='https://invalid.example/image'> & offline"
            val label = DesktopRpcWrappedLabel(raw)
            assertTrue(label.text.contains("&lt;img"))
            assertTrue(label.text.contains("&amp;"))
            assertEquals(raw, label.accessibleContext.accessibleName)
            var changes = 0
            label.addPropertyChangeListener("text") { changes++ }
            label.show(raw)
            assertEquals(0, changes)
            label.show("Ready")
            assertEquals(1, changes)
        }
    }

    @Test fun resizingColumnRemeasuresWrappedControlsAndMultilineLabels() {
        SwingUtilities.invokeAndWait {
            val column = DesktopRpcColumn()
            val row = JPanel(DesktopRpcWrapLayout()).apply {
                repeat(6) { add(JButton("Action $it").apply { preferredSize = Dimension(150, 30) }) }
            }
            val label = DesktopRpcWrappedLabel("A long status with spaces ".repeat(20))
            column.add(row); column.add(label)
            column.setSize(1400, 1000); column.doLayout(); row.doLayout()
            val wideHeight = column.preferredSize.height
            for (width in listOf(760, 1000, 760)) {
                column.setSize(width, 1000); column.doLayout(); row.doLayout()
                assertEquals(width, row.width)
                row.components.forEach { assertTrue(it.y + it.height <= row.height) }
                assertEquals(row.height, label.y)
                assertTrue(label.height > label.getFontMetrics(label.font).height)
                assertTrue(column.preferredSize.height > wideHeight)
            }
        }
    }

    @Test fun brandedHeaderRemainsBoundedAndAddsNoRoleActions() {
        SwingUtilities.invokeAndWait {
            val hero = DesktopRpcAppearance.hero()
            for (width in listOf(700, 960)) {
                hero.setSize(width, 200); hero.doLayout()
                assertTrue(hero.preferredSize.height > 0)
                hero.components.forEach {
                    assertTrue(it.x >= 0 && it.x + it.width <= width)
                    assertTrue(it is JLabel)
                }
            }
            assertEquals("Overview", DesktopRpcAppearance.heading("Overview").text)
        }
    }

}
