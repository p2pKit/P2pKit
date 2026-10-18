package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.PhoneOperationFailureState
import dev.p2pkit.sample.rpc.PhoneOperationTerminalFailure
import dev.p2pkit.sample.rpc.startPhoneOperation
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Real facade callback + Desktop ownership bridge, not a native storage or installed-runtime test. */
@OptIn(ExperimentalCoroutinesApi::class)
class DesktopRpcFatalOperationTest {
    @Test
    fun fatalCallbackAndCancellationRaceCannotStrandStopOrAuthorizeReplacement() = runTest {
        for (cancelBeforeFailure in listOf(false, true)) {
            val failures = PhoneOperationFailureState()
            val original = LinkageError("synthetic native reporting failure")
            var physicalCloses = 0
            val owner = DesktopRpcRunOwner(backgroundScope) { _: Any ->
                failures.retire { physicalCloses++ }
            }
            assertTrue(owner.start("Client", { Any() }) {})
            runCurrent()
            assertTrue(owner.action {
                awaitDesktopRpcCompletion<String> { callback ->
                    val operation = startPhoneOperation(backgroundScope, MutableStateFlow(false),
                        { "cancelled" }, { "sanitized" }, callback, failures) {
                        if (cancelBeforeFailure) {
                            try { awaitCancellation() } finally { throw original }
                        }
                        throw original
                    }
                    val cancel: () -> Unit = { operation.cancel() }
                    cancel
                }
            })
            runCurrent()
            if (cancelBeforeFailure) {
                owner.cancelAction()
                runCurrent()
            }
            assertEquals(DesktopRpcRunOwner.Stage.Ready, owner.snapshot().stage)
            assertSame(original, failures.originalFailure)
            val stopped = owner.stop()
            runCurrent()
            assertTrue(stopped.isCompleted)
            val failure = stopped.await()
            assertTrue(failure is PhoneOperationTerminalFailure)
            assertSame(original, failure.originalFailure)
            assertEquals(1, physicalCloses)
            assertEquals(DesktopRpcRunOwner.Stage.Failed, owner.snapshot().stage)
            assertFalse(owner.start("Host", { Any() }) {})
            assertSame(failure, owner.stop().await())
            assertEquals(1, physicalCloses)
        }
    }
}
