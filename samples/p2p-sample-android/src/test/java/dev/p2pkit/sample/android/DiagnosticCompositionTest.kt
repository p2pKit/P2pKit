package dev.p2pkit.sample.android

import android.content.Context
import androidx.compose.runtime.AbstractApplier
import androidx.compose.runtime.BroadcastFrameClock
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Composition
import androidx.compose.runtime.Recomposer
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.Snapshot
import dev.p2pkit.sample.diagnostics.DiagnosticEnvironment
import dev.p2pkit.sample.diagnostics.DiagnosticEvent
import dev.p2pkit.sample.diagnostics.DiagnosticFilter
import dev.p2pkit.sample.diagnostics.DiagnosticOutcome
import dev.p2pkit.sample.diagnostics.DiagnosticRecord
import dev.p2pkit.sample.diagnostics.DiagnosticRecorder
import java.io.File
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

/** Real Compose invalidation/collection on a host SDK; no rendered UI or frame-performance claim. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class DiagnosticCompositionTest {
    @Test
    fun recordedEventsAloneInvalidateBothSnapshotAndSurroundingSummary() = runTest {
        val source = Source()
        var displayed = emptyList<DiagnosticEvent>()
        var finalState: String? = null
        withComposition { fixture ->
            fixture.content {
                val events = rememberDiagnosticEvents(source.revision, DiagnosticFilter(), source.recorder::snapshot)
                val summary = source.recorder.summary()
                SideEffect {
                    displayed = events
                    finalState = summary.finalState
                }
            }
            assertEquals(1, source.revision.subscriptionCount.value)
            assertTrue(displayed.isEmpty())

            source.record("event_only")
            assertEquals(listOf("event_only"), source.recorder.snapshot().map { it.eventName })
            fixture.advance()
            assertEquals(listOf("event_only"), displayed.map { it.eventName })

            source.recorder.completeSession(DiagnosticOutcome.SUCCESS, "synthetic completion", "finished")
            fixture.advance()
            assertEquals("finished", finalState)
            assertEquals(source.recorder.snapshot(), displayed)
        }
        assertEquals(0, source.revision.subscriptionCount.value)
    }

    @Test
    fun sessionAndFilterChangesKeepPauseAsADisplaySnapshot() = runTest {
        val source = Source()
        source.recorder.startSession("PS-T01", "both", "first")
        source.record("match_first")
        var search by mutableStateOf<String?>(null)
        var paused by mutableStateOf(false)
        var frozen by mutableStateOf(emptyList<DiagnosticEvent>())
        var live = emptyList<DiagnosticEvent>()
        var displayed = emptyList<DiagnosticEvent>()
        withComposition { fixture ->
            fixture.content {
                // Matches the screen: active context is plain recorder state, not Compose state.
                val filter = DiagnosticFilter(testId = source.recorder.activeTestId, search = search)
                val events = rememberDiagnosticEvents(source.revision, filter, source.recorder::snapshot)
                val selected = if (paused) frozen else events
                SideEffect {
                    live = events
                    displayed = selected
                }
            }
            val first = displayed
            frozen = first
            paused = true
            fixture.advance()
            source.recorder.startSession("PS-T02", "both", "second")
            source.record("match_second")
            source.record("other_second")
            search = "MATCH"
            fixture.advance()
            assertEquals(first, displayed)
            assertEquals(listOf("match_second"), live.map { it.eventName })

            paused = false
            fixture.advance()
            assertEquals(live, displayed)
            search = "OTHER"
            fixture.advance()
            assertEquals(listOf("other_second"), displayed.map { it.eventName })
        }
        assertEquals(0, source.revision.subscriptionCount.value)
    }

    @Test
    fun sessionChangesAloneRefreshTheCallersPlainRecorderContextFilter() = runTest {
        val source = Source()
        source.recorder.startSession("PS-T01", "both", "first")
        source.record("first")
        var displayed = emptyList<DiagnosticEvent>()
        withComposition { fixture ->
            fixture.content {
                val filter = DiagnosticFilter(testId = source.recorder.activeTestId)
                val events = rememberDiagnosticEvents(source.revision, filter, source.recorder::snapshot)
                SideEffect { displayed = events }
            }
            assertTrue(displayed.any { it.eventName == "first" })
            source.recorder.startSession("PS-T02", "receiver", "second")
            source.record("second")
            fixture.advance()
            assertTrue(displayed.any { it.eventName == "second" })
            assertTrue(displayed.all { it.testId == "PS-T02" })
            assertTrue(source.recorder.snapshot().any { it.testId == "PS-T01" })
        }
        assertEquals(0, source.revision.subscriptionCount.value)
    }

    @Test
    fun successfulHarnessClearInvalidatesCachedHistoryWithoutAnotherEvent() = runTest {
        val root = Files.createTempDirectory("p2pkit-diagnostic-composition").toFile()
        val revision = MutableStateFlow(0L)
        try {
            val preferences = RuntimeEnvironment.getApplication()
                .getSharedPreferences("synthetic-composition", Context.MODE_PRIVATE)
            val harness = AndroidDiagnosticHarness(
                preferences, File(root, "logs"), File(root, "evidence"), environment()
            ) { revision.update { it + 1 } }
            harness.beginSession("PS-T01", "both", "other")
            harness.beginSession("PS-T01", "both", "selected")
            var displayed = emptyList<DiagnosticEvent>()
            withComposition { fixture ->
                fixture.content {
                    val events = rememberDiagnosticEvents(revision, DiagnosticFilter(), harness.recorder::snapshot)
                    SideEffect { displayed = events }
                }
                val other = displayed.filter { it.testSessionId != "selected" }
                assertTrue(other.isNotEmpty())
                assertTrue(displayed.any { it.testSessionId == "selected" })
                val beforeRevision = revision.value

                harness.clearCurrentSession()
                fixture.advance()

                assertEquals(beforeRevision + 1, revision.value)
                assertEquals(other, displayed)
                assertEquals(harness.recorder.snapshot(), displayed)
                assertTrue(preferences.all.isEmpty())
            }
            assertEquals(0, revision.subscriptionCount.value)
        } finally {
            assertTrue(root.deleteRecursively())
        }
    }

    @Test
    fun sourceReplacementAndDisposalCancelOnlyTheirOwnCollector() = runTest {
        val first = Source().apply { record("first") }
        val second = Source().apply { record("second") }
        assertEquals(first.revision.value, second.revision.value)
        var current by mutableStateOf(first)
        var visible by mutableStateOf(true)
        var displayed = emptyList<DiagnosticEvent>()
        var compositions = 0
        withComposition { fixture ->
            fixture.content {
                if (visible) {
                    val source = current
                    val events = rememberDiagnosticEvents(
                        source.revision, DiagnosticFilter(), source.recorder::snapshot
                    )
                    SideEffect {
                        displayed = events
                        compositions++
                    }
                }
            }
            assertEquals(listOf("first"), displayed.map { it.eventName })
            current = second
            fixture.advance()
            assertEquals(0, first.revision.subscriptionCount.value)
            assertEquals(1, second.revision.subscriptionCount.value)
            assertEquals(listOf("second"), displayed.map { it.eventName })
            val afterReplacement = compositions
            first.record("retired")
            fixture.advance()
            assertEquals(afterReplacement, compositions)
            second.record("current")
            fixture.advance()
            assertEquals(listOf("second", "current"), displayed.map { it.eventName })

            visible = false
            fixture.advance()
            assertEquals(0, second.revision.subscriptionCount.value)
            val afterDisposal = compositions
            second.record("while_hidden")
            fixture.advance()
            assertEquals(afterDisposal, compositions)
            visible = true
            fixture.advance()
            assertEquals(1, second.revision.subscriptionCount.value)
            assertEquals(second.recorder.snapshot(), displayed)
        }
        assertEquals(0, first.revision.subscriptionCount.value)
        assertEquals(0, second.revision.subscriptionCount.value)
    }

    @Test
    fun eventBurstIsConflatedIntoOneSnapshotRefreshWithOneCollector() = runTest {
        val source = Source(maxEvents = 128)
        var displayed = emptyList<DiagnosticEvent>()
        var compositions = 0
        withComposition { fixture ->
            fixture.content {
                val events = rememberDiagnosticEvents(source.revision, DiagnosticFilter(), source.recorder::snapshot)
                SideEffect {
                    displayed = events
                    compositions++
                }
            }
            val before = compositions
            repeat(20_000) { source.record("burst_$it") }
            fixture.advance()
            assertEquals(20_000L, source.revision.value)
            assertEquals(before + 1, compositions)
            assertEquals(1, source.revision.subscriptionCount.value)
            assertEquals(128, displayed.size)
            assertEquals("burst_19999", displayed.last().eventName)
            assertEquals(source.recorder.snapshot(), displayed)
        }
        assertEquals(0, source.revision.subscriptionCount.value)
    }

    @Test
    fun actualScreenUsesTheTestedBridgeAndKeepsConfirmedClearAndPauseWiring() {
        val source = File("src/main/java/dev/p2pkit/sample/android/AndroidDiagnosticsScreen.kt").readText()
        assertTrue(source.contains("rememberDiagnosticEvents(vm.diagnosticRevision, filter, vm::diagnosticEvents)"))
        assertTrue(source.contains("val events = if (paused) pausedEvents else liveEvents"))
        assertTrue(source.contains("if (!paused) pausedEvents = liveEvents"))
        assertTrue(source.contains("onCleared = {\n                            selected.clear()\n" +
            "                            pausedEvents = emptyList()"))
        assertFalse(source.contains("@Suppress(\"UNUSED_VARIABLE\")"))
    }

    private class Source(maxEvents: Int = 5_000) {
        val revision = MutableStateFlow(0L)
        val recorder = DiagnosticRecorder(
            environment = environment(), maxEvents = maxEvents,
            eventSink = { revision.update { it + 1 } }
        )

        fun record(name: String) = recorder.record(DiagnosticRecord(category = "test", eventName = name))
    }

    private suspend fun TestScope.withComposition(action: (Fixture) -> Unit) {
        val fixture = Fixture(this)
        try {
            action(fixture)
        } finally {
            fixture.close()
        }
    }

    private class Fixture(private val scope: TestScope) {
        private val clock = BroadcastFrameClock()
        private val recomposer = Recomposer(scope.coroutineContext + clock)
        private val composition = Composition(NoUiApplier(), recomposer)
        private val runner = scope.launch(clock) { recomposer.runRecomposeAndApplyChanges() }
        private var frame = 0L

        fun content(content: @Composable () -> Unit) {
            composition.setContent(content)
            advance()
        }

        fun advance() {
            // Explicit virtual frames, not sleeps or a long polling timeout.
            repeat(8) {
                scope.runCurrent()
                Snapshot.sendApplyNotifications()
                scope.runCurrent()
                if (!clock.hasAwaiters) {
                    assertFalse(recomposer.hasPendingWork)
                    return
                }
                frame += 16_666_667L
                clock.sendFrame(frame)
            }
            error("Composition did not settle within eight virtual frames")
        }

        suspend fun close() {
            composition.dispose()
            recomposer.cancel()
            runner.cancelAndJoin()
            recomposer.join()
        }
    }

    private class NoUiApplier : AbstractApplier<Unit>(Unit) {
        override fun insertTopDown(index: Int, instance: Unit) = error("No UI nodes expected")
        override fun insertBottomUp(index: Int, instance: Unit) = error("No UI nodes expected")
        override fun remove(index: Int, count: Int) = error("No UI nodes expected")
        override fun move(from: Int, to: Int, count: Int) = error("No UI nodes expected")
        override fun onClear() = Unit
    }

    private companion object {
        fun environment() = DiagnosticEnvironment("android", "synthetic-host", "test", "test", "test", "synthetic")
    }
}
