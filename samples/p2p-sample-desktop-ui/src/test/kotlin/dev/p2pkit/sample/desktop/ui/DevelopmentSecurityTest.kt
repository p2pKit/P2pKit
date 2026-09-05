package dev.p2pkit.sample.desktop.ui

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.ImageComposeScene
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.use
import java.io.File
import java.nio.file.Files
import java.util.zip.ZipFile
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class DevelopmentSecurityTest {
    @Test
    fun autoMeshRequiresAnExplicitOperatorToggle() = withState { state ->
        // Same-AppId authentication is not pinning; never auto-initiate on a fresh sample.
        assertFalse(state.autoMesh.value)
        state.toggleAutoMesh()
        assertTrue(state.autoMesh.value)
        state.toggleAutoMesh()
        assertFalse(state.autoMesh.value)
    }

    @Test
    fun diagnosticExportDisclosesTheTestAuthorizationAndIdentityLifetime() = withState { state ->
        val expected = mapOf(
            "securityPolicy" to "authenticated-same-app-test-only",
            "identityStorage" to "in-memory-per-kit"
        )
        expected.forEach { (key, value) ->
            assertEquals(value, state.diagnostics.recorder.configuration.values[key], key)
        }
        ZipFile(state.diagnostics.export()).use { zip ->
            val entry = assertNotNull(zip.getEntry("summary.json"))
            val summary = zip.getInputStream(entry).bufferedReader().use { it.readText() }
            expected.forEach { (key, value) ->
                assertTrue(Regex("\"$key\"\\s*:\\s*\"$value\"").containsMatchIn(summary), key)
            }
        }
    }

    @OptIn(ExperimentalComposeUiApi::class)
    @Test
    fun bothScreensKeepTheCompleteWarningVisibleWithoutOverlappingDiagnostics() = withState { state ->
        state.deviceName = "Synthetic Desktop"
        for (running in listOf(false, true)) {
            for (direction in listOf(LayoutDirection.Ltr, LayoutDirection.Rtl)) {
                for ((width, height, fontScale) in listOf(Triple(980, 760, 1f), Triple(780, 600, 1.5f))) {
                    ImageComposeScene(
                        width = width,
                        height = height,
                        density = Density(1f, fontScale),
                        layoutDirection = direction,
                        content = {
                            MaterialTheme {
                                Surface(modifier = Modifier.fillMaxSize()) {
                                    DesktopSampleScreen(state, running) {}
                                }
                            }
                        }
                    ).use { scene ->
                        scene.render().use { image ->
                            val nodes = scene.semanticsOwners.flatMap { it.unmergedRootSemanticsNode.descendants() }
                            val warning = nodes.single { it.text().startsWith("DEVELOPMENT MODE:") }
                            val text = warning.text()
                            assertTrue(text.contains("even with Auto-mesh off"))
                            assertTrue(text.contains("AppId is not a secret"))
                            assertTrue(text.contains("Identity resets when the kit is recreated"))
                            assertTrue(text.contains("Production apps must verify and pin peer fingerprints"))
                            assertNull(warning.config.getOrNull(SemanticsActions.OnClick))
                            val bounds = warning.boundsInRoot
                            assertTrue(bounds.width > 0 && bounds.height > 0)
                            assertTrue(bounds.left >= 0 && bounds.top >= 0)
                            assertTrue(bounds.right <= width && bounds.bottom <= height)
                            val layout = mutableListOf<TextLayoutResult>()
                            val getLayout = assertNotNull(
                                warning.config.getOrNull(SemanticsActions.GetTextLayoutResult)
                            )
                            assertTrue(assertNotNull(getLayout.action).invoke(layout))
                            assertFalse(layout.single().hasVisualOverflow)
                            val diagnostics = nodes.single { it.text() == "Diagnostics" }
                            assertFalse(bounds.overlaps(diagnostics.boundsInRoot))
                            assertTrue(nodes.any {
                                if (running) it.text() == "Discovered peers (0)" else it.text() == "P2pKit Test Harness"
                            })
                            // Synthetic offscreen evidence only; no desktop capture or running network kit.
                            val name = "${if (running) "room" else "setup"}-$direction-$width.png"
                            val output = File("build/reports/security-warning", name)
                            check(output.parentFile.isDirectory || output.parentFile.mkdirs())
                            assertNotNull(image.encodeToData()).use { output.writeBytes(it.bytes) }
                        }
                    }
                }
            }
        }
    }

    @OptIn(ExperimentalComposeUiApi::class)
    @Test
    fun compactRoomKeepsSendControlsReachableBelowTheWarning() = withState { state ->
        state.deviceName = "Synthetic Desktop"
        ImageComposeScene(
            width = 980,
            height = 600,
            content = {
                MaterialTheme {
                    Surface(modifier = Modifier.fillMaxSize()) { DesktopSampleScreen(state, true) {} }
                }
            }
        ).use { scene ->
            var frameNanos = 0L
            fun nodes() = scene.semanticsOwners.flatMap { it.unmergedRootSemanticsNode.descendants() }
            fun sendButton() = nodes().single { node ->
                node.config.getOrNull(SemanticsProperties.Role) == Role.Button &&
                    node.descendants().any { it.text() == "No peers connected" }
            }
            fun isVisible(node: SemanticsNode): Boolean = with(node.boundsInRoot) {
                width > 0 && height > 0 && height >= node.size.height && top >= 0 && bottom <= 600
            }
            fun capture(name: String) {
                scene.render(frameNanos).use { image ->
                    val output = File("build/reports/security-warning", "$name.png")
                    check(output.parentFile.isDirectory || output.parentFile.mkdirs())
                    assertNotNull(image.encodeToData()).use { output.writeBytes(it.bytes) }
                }
            }
            capture("compact-room-before-scroll")
            val warningBounds = nodes().single { it.text().startsWith("DEVELOPMENT MODE:") }.boundsInRoot
            val button = sendButton()
            println("Initial send control: bounds=${button.boundsInRoot}, size=${button.size}")
            if (!isVisible(button)) {
                val scrollOwner = assertNotNull(nodes().firstOrNull { node ->
                    node.config.getOrNull(SemanticsActions.ScrollBy) != null &&
                        node.descendants().any { it.id == button.id }
                }, "The warning must not make the send controls unreachable")
                val action = assertNotNull(scrollOwner.config.getOrNull(SemanticsActions.ScrollBy)?.action)
                val range = assertNotNull(scrollOwner.config.getOrNull(SemanticsProperties.VerticalScrollAxisRange))
                assertTrue(action.invoke(0f, 600f))
                // ScrollBy is animated. Advance only the scene's virtual frame clock,
                // bounded to 120 frames; no wall-clock sleeps or polling timeouts.
                var frames = 0
                while (range.value() < range.maxValue() && frames++ < 120) {
                    frameNanos += 16_666_667
                    scene.render(frameNanos).close()
                }
                assertEquals(range.maxValue(), range.value(), "Scroll action must reach the bottom")
                capture("compact-room-after-scroll")
            }
            assertTrue(isVisible(sendButton()), "Full send control must be visible initially or after scrolling")
            assertEquals(
                warningBounds,
                nodes().single { it.text().startsWith("DEVELOPMENT MODE:") }.boundsInRoot,
                "The warning must stay visible while room content scrolls"
            )
        }
    }

    private fun SemanticsNode.descendants(): List<SemanticsNode> = listOf(this) + children.flatMap { it.descendants() }

    private fun SemanticsNode.text(): String =
        config.getOrNull(SemanticsProperties.Text)?.joinToString("") { it.text }.orEmpty()

    private fun withState(block: (DesktopP2pState) -> Unit) = runBlocking {
        val home = Files.createTempDirectory("p2pkit-desktop-security-test").toFile()
        val job = SupervisorJob()
        try {
            val state = DesktopP2pState(CoroutineScope(job + Dispatchers.Unconfined), home)
            try {
                block(state)
            } finally {
                state.shutdownIfRunning()
            }
        } finally {
            job.cancelAndJoin()
            assertTrue(home.deleteRecursively(), "remove disposable diagnostic home")
        }
    }
}
