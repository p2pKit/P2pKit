package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcReply
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

@OptIn(ExperimentalCoroutinesApi::class)
class RpcCapacityExerciseHostTest {
    @Test
    fun remoteHoldRecordsActualEntryAndRetiresWhenItsOwnedHandlerIsCancelled() = runTest {
        val host = CapacityExerciseHostState()
        val worker = async { host.hold("cancel") }
        testScheduler.runCurrent()
        assertEquals(CapacityExerciseCounters(holdEntered = 1), host.snapshot())
        worker.cancelAndJoin()
        assertEquals(CapacityExerciseCounters(holdEntered = 1, holdRetired = 1), host.snapshot())
        assertFalse(worker.isActive)
        assertFailsWith<IllegalArgumentException> { host.hold("arbitrary-command") }
        assertEquals(CapacityExerciseCounters(holdEntered = 1, holdRetired = 1), host.snapshot())
    }

    @Test
    fun sleepingHandlerIsFiniteAndIndependentRequestsRetainTheirOwnCancellation() = runTest {
        val host = CapacityExerciseHostState()
        val slow = async { host.slow("synthetic") }
        testScheduler.runCurrent()
        assertEquals(CapacityExerciseCounters(slowEntered = 1), host.snapshot())
        assertEquals(RpcReply.Success("synthetic"), slow.await())
        assertEquals(1_000L, testScheduler.currentTime)
        assertEquals(CapacityExerciseCounters(slowEntered = 1, slowRetired = 1), host.snapshot())
        val cancelled = async { host.slow("synthetic") }
        testScheduler.runCurrent()
        cancelled.cancelAndJoin()
        assertEquals(CapacityExerciseCounters(slowEntered = 2, slowRetired = 2), host.snapshot())
    }

    @Test
    fun fixedProcedureBodiesAndErrorsRetainOriginalPerRequestLimits() {
        val procedures = listOf(RpcCapacityExercises.echo, RpcCapacityExercises.reject, RpcCapacityExercises.denied,
            RpcCapacityExercises.hold, RpcCapacityExercises.slow, RpcCapacityExercises.state)
        assertEquals(6, procedures.map { it.name to it.version }.toSet().size)
        for (procedure in procedures) {
            assertEquals(1024, procedure.requestLimitBytes)
            assertEquals(1024, procedure.responseLimitBytes)
            assertEquals(256, procedure.errorLimitBytes)
        }
    }
}
