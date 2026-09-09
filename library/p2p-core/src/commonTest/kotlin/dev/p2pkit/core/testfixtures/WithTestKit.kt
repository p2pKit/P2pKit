package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.P2pKit
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext

/**
 * Own one real kit and its diagnostics from construction through completed shutdown.
 * [create] must install its supplied recorder in the existing legacy or secure fixture.
 * Nest scopes for multiple kits; each is stopped even if construction, the body or another stop fails.
 * Additional test-owned collectors, raw resources and stores still need their own finally blocks.
 *
 * This reuses [P2pKit.stop]'s cancellation-safe, independently bounded resource teardown rather than
 * adding a second deadline that could abandon it. A stop failure remains a failure, never permission
 * to call a timed-out resource drained. No worker, dispatcher or test scheduler is created here.
 *
 * By default every WARN/ERROR fails after shutdown, outside the production logger's exception
 * isolation. Deliberate diagnostics need an exact level/message/cause/count assertion in
 * [verifyDiagnostics], not a broad message predicate. DEBUG/INFO do not fail the default net.
 */
internal suspend fun <T> withTestKit(
    create: (RecordingLogger) -> P2pKit,
    verifyDiagnostics: (RecordingLogger) -> Unit = { it.assertNoUnexpectedWarnOrError() },
    test: suspend (P2pKit) -> T
): T {
    val recorder = RecordingLogger()
    var kit: P2pKit? = null
    var bodyFailure: Throwable? = null
    try {
        val created = create(recorder)
        kit = created
        return test(created)
    } catch (failure: Throwable) {
        bodyFailure = failure
        throw failure
    } finally {
        val cleanupFailures = mutableListOf<Throwable>()
        try {
            withContext(NonCancellable) { kit?.stop() }
        } catch (failure: Throwable) {
            cleanupFailures += failure
        }
        // Also runs when creation, the test, cancellation or stop failed. Never assert in warn/error:
        // P2pKit deliberately isolates exceptions thrown from application logger callbacks.
        try {
            verifyDiagnostics(recorder)
        } catch (failure: Throwable) {
            cleanupFailures += failure
        }
        val primary = bodyFailure ?: cleanupFailures.firstOrNull()
        if (primary != null) {
            cleanupFailures.filter { it !== primary }.forEach(primary::addSuppressed)
            if (bodyFailure == null) throw primary
        }
    }
}
