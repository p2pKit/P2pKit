package dev.p2pkit.sample.desktop.ui

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import java.nio.file.Files
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class ManualConnectionPollingTest {
    @Test
    fun reportsOncePerFailureStreakAndRecoversOnBothNullAndRotatedInfo() = withState { state, _ ->
        val first = manualInfo(9000)
        val rotated = manualInfo(9001)
        val privateDetail = "synthetic private host 192.0.2.8 /private/path"
        val results = ArrayDeque(
            listOf(
                Result.success(first),
                Result.failure(IllegalStateException(privateDetail)),
                Result.failure(IllegalArgumentException(privateDetail)),
                Result.success(null),
                Result.failure(IllegalStateException(privateDetail)),
                Result.success(rotated),
                Result.failure(IllegalStateException(privateDetail))
            )
        )
        val observations = mutableListOf<ManualConnectionInfo?>()
        val messageCounts = mutableListOf<Int>()
        val intervals = mutableListOf<Long>()
        val finished = CancellationException("finite poll script completed")
        val cancellation = assertFailsWith<CancellationException> {
            state.pollManualConnectionInfo(
                getInfo = { results.removeFirst().getOrThrow() },
                awaitNextPoll = { interval ->
                    intervals += interval
                    observations += state.manualConnectionInfo.value
                    messageCounts += state.roomMessages.size
                    if (results.isEmpty()) throw finished
                }
            )
        }
        assertSame(finished, cancellation)
        assertEquals(listOf(first, null, null, null, null, rotated, null), observations)
        assertEquals(listOf(0, 1, 1, 1, 2, 2, 3), messageCounts)
        assertEquals(List(7) { 5_000L }, intervals)
        assertEquals(
            List(3) { "Manual connection info unavailable: IllegalStateException" },
            state.roomMessages.map { it.body }
        )
        assertFalse(state.roomMessages.any { privateDetail in it.body })

        // A new run owns a new debounce streak even if the previous run ended failing.
        assertFailsWith<CancellationException> {
            state.pollManualConnectionInfo(
                getInfo = { throw IllegalStateException(privateDetail) },
                awaitNextPoll = { throw finished }
            )
        }
        assertEquals(4, state.roomMessages.size)
    }

    @Test
    fun fetchCancellationIsRethrownWithoutReportingOrSchedulingAnotherPoll() = withState { state, _ ->
        val cancelled = CancellationException("synthetic cancellation")
        var waits = 0
        assertSame(
            cancelled,
            assertFailsWith<CancellationException> {
                state.pollManualConnectionInfo(
                    getInfo = { throw cancelled },
                    awaitNextPoll = { waits++; error("cancelled fetch must not schedule another poll") }
                )
            }
        )
        assertEquals(0, waits)
        assertTrue(state.roomMessages.isEmpty())
    }

    @Test
    fun cancellingTheRunOwnerStopsTheDefaultDelayWithoutAnotherRead() = withState { state, scope ->
        val runOwner = SupervisorJob(scope.coroutineContext[Job])
        val runScope = CoroutineScope(scope.coroutineContext + runOwner)
        var reads = 0
        val poll = runScope.launch {
            state.pollManualConnectionInfo(getInfo = { reads++; null })
        }
        try {
            assertEquals(1, reads)
            runOwner.cancelAndJoin()
            assertTrue(poll.isCompleted)
            assertTrue(poll.isCancelled)
            assertEquals(1, reads)
            assertTrue(state.roomMessages.isEmpty())
        } finally {
            runOwner.cancelAndJoin()
        }
    }

    @Test
    fun cancellingTheRunOwnerInterruptsTheSuspendedFetchWithoutAFalseFailure() = withState { state, scope ->
        val runOwner = SupervisorJob(scope.coroutineContext[Job])
        val runScope = CoroutineScope(scope.coroutineContext + runOwner)
        var entered = false
        var waits = 0
        val poll = runScope.launch {
            state.pollManualConnectionInfo(
                getInfo = { entered = true; awaitCancellation() },
                awaitNextPoll = { waits++ }
            )
        }
        try {
            assertTrue(entered)
            runOwner.cancelAndJoin()
            assertTrue(poll.isCompleted)
            assertTrue(poll.isCancelled)
            assertEquals(0, waits)
            assertTrue(state.roomMessages.isEmpty())
        } finally {
            runOwner.cancelAndJoin()
        }
    }

    private fun manualInfo(port: Int) = ManualConnectionInfo(
        hostAddresses = listOf("192.0.2.1"),
        port = port,
        appId = AppId("synthetic-app"),
        peerId = PeerId("synthetic-peer"),
        deviceName = "Synthetic Desktop"
    )

    private fun withState(block: suspend (DesktopP2pState, CoroutineScope) -> Unit) = runBlocking {
        val home = Files.createTempDirectory("p2pkit-manual-poll-test").toFile()
        val owner = SupervisorJob()
        val scope = CoroutineScope(Dispatchers.Unconfined + owner)
        val state = DesktopP2pState(scope, home)
        try {
            block(state, scope)
        } finally {
            owner.cancelAndJoin()
            state.shutdownIfRunning()
            assertTrue(home.deleteRecursively(), "remove disposable diagnostic home")
        }
    }
}
