package dev.p2pkit.sample.rpc.desktop

import java.awt.Dimension
import java.awt.GraphicsEnvironment
import java.awt.event.WindowAdapter
import java.awt.event.WindowEvent
import javax.swing.JFrame
import javax.swing.SwingUtilities
import javax.swing.WindowConstants

/** Legacy local preview entry point. The maintained application embeds [RpcDesktopPanel] instead. */
fun main() {
    check(!GraphicsEnvironment.isHeadless()) { "The RPC Desktop sample requires a graphical desktop." }
    SwingUtilities.invokeLater { RpcDesktopWindow().isVisible = true }
}

private class RpcDesktopWindow : JFrame("RPC Desktop sample — developer preview") {
    private val panel = RpcDesktopPanel(onBackRequested = ::closePreview)

    init {
        defaultCloseOperation = WindowConstants.DO_NOTHING_ON_CLOSE
        contentPane = panel
        minimumSize = Dimension(760, 640)
        pack()
        val screen = GraphicsEnvironment.getLocalGraphicsEnvironment().maximumWindowBounds
        setSize(minOf(width, screen.width), minOf(height, screen.height))
        setLocationByPlatform(true)
        addWindowListener(object : WindowAdapter() {
            override fun windowClosing(event: WindowEvent) = closePreview()
        })
        addWindowFocusListener(object : WindowAdapter() {
            override fun windowGainedFocus(event: WindowEvent) = panel.onWindowFocusChanged(true)
            override fun windowLostFocus(event: WindowEvent) = panel.onWindowFocusChanged(false)
        })
    }

    private fun closePreview() {
        panel.requestClose { if (it == DesktopRpcCloseResult.Closed) dispose() }
    }
}
