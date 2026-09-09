package dev.p2pkit.sample.desktop.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.snapshots.Snapshot
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.ImageComposeScene
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.style.TextDirection
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.use
import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.sample.diagnostics.LocalPairingInfo
import dev.p2pkit.transport.lan.lan
import java.io.File
import kotlin.test.AfterTest
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

class LocalPairingSectionTest {
    private val diagnostics = KitTestDiagnostics()

    @AfterTest
    fun checkDiagnostics() = runBlocking { diagnostics.finish() }

    @OptIn(ExperimentalComposeUiApi::class)
    @Test
    fun disclosureShowsFullSelectableLtrTokensAndResetsForANewIdentity() = runBlocking {
        val kit = createKit()
        val replacement = createKit()
        val info = assertNotNull(LocalPairingInfo.from(kit))
        val next = assertNotNull(LocalPairingInfo.from(replacement))
        assertNotEquals(info.qr, next.qr, "each JVM sample kit must have its own in-memory identity")
        for (direction in listOf(LayoutDirection.Ltr, LayoutDirection.Rtl)) {
            val current = mutableStateOf(info)
            ImageComposeScene(
                width = 360, height = 1_100, density = Density(1f, 1.5f), layoutDirection = direction,
                content = { MaterialTheme { Surface { LocalPairingSection(current.value) } } }
            ).use { scene ->
                var frame = 0L
                fun render() {
                    // ImageComposeScene.render dispatches snapshot notifications after its
                    // recomposition phase. Flush external/semantic-action writes before the frame.
                    Snapshot.sendApplyNotifications()
                    frame += 16_666_667
                    scene.render(frame).close()
                }
                fun nodes() = scene.semanticsOwners.flatMap { it.unmergedRootSemanticsNode.descendants() }
                render()
                assertFalse(nodes().any { it.text() == info.qr || it.text() == info.fingerprint })
                val show = nodes().single { node ->
                    node.config.getOrNull(SemanticsProperties.Role) == Role.Button &&
                        node.descendants().any { it.text() == "Show local pairing information" }
                }
                assertTrue(assertNotNull(show.config.getOrNull(SemanticsActions.OnClick)?.action).invoke())
                render()
                for (token in listOf(info.qr, info.fingerprint)) {
                    val text = nodes().single { it.text() == token }
                    val layouts = mutableListOf<TextLayoutResult>()
                    assertTrue(
                        assertNotNull(text.config.getOrNull(SemanticsActions.GetTextLayoutResult)?.action)
                            .invoke(layouts)
                    )
                    val layout = layouts.single()
                    assertEquals(TextDirection.Ltr, layout.layoutInput.style.textDirection)
                    assertFalse(layout.hasVisualOverflow)
                    assertTrue(text.boundsInRoot.width > 0 && text.boundsInRoot.bottom <= 1_100)
                }
                scene.render(frame).use { image ->
                    val output = File("build/reports/pairing-ui", "disclosed-$direction.png")
                    check(output.parentFile.isDirectory || output.parentFile.mkdirs())
                    assertNotNull(image.encodeToData()).use { output.writeBytes(it.bytes) }
                }
                // Apply the external test write synchronously; unlike an input event,
                // this manual offscreen scene has no UI loop to dispatch global notifications.
                Snapshot.withMutableSnapshot { current.value = next }
                render()
                val tokens = listOf(info.qr, info.fingerprint, next.qr, next.fingerprint)
                assertFalse(nodes().any { it.text() in tokens })
                assertTrue(nodes().any { it.text() == "Show local pairing information" })
            }
        }
    }

    private fun SemanticsNode.descendants(): List<SemanticsNode> = listOf(this) + children.flatMap { it.descendants() }

    private fun SemanticsNode.text(): String =
        config.getOrNull(SemanticsProperties.Text)?.joinToString("") { it.text }.orEmpty()

    private fun createKit(): P2pKit = diagnostics.create { recording ->
        P2pKit.create {
            logger = recording
            appId = AppId("synthetic.pairing.ui")
            deviceName = "Synthetic pairing UI"
            jvmSecureIdentityStore(DevelopmentOnlyInMemorySecureIdentityStore())
            transports { lan() }
        }
    }
}
