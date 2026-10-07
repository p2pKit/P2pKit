package dev.p2pkit.sample.android.rpclab

import androidx.compose.ui.graphics.luminance
import kotlin.test.Test
import kotlin.test.assertTrue

class RpcLabThemeTest {
    @Test fun normalTextAndHeroHaveReadableContrastInBothThemes() {
        for (dark in listOf(false, true)) {
            val colors = rpcLabColors(dark)
            for ((ink, paper) in listOf(colors.onSurface to colors.surface,
                colors.onPrimaryContainer to colors.primaryContainer)) {
                val a = ink.luminance(); val b = paper.luminance()
                val contrast = (maxOf(a, b) + 0.05f) / (minOf(a, b) + 0.05f)
                assertTrue(contrast >= 4.5f, "Body text contrast must be at least 4.5:1")
            }
        }
    }
}
