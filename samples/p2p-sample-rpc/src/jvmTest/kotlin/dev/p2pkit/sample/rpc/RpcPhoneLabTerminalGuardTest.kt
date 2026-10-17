package dev.p2pkit.sample.rpc

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Reflection only transfers an inert ledger into the real facade; no provider, network or storage is created. */
class RpcPhoneLabTerminalGuardTest {
    @Test
    fun everyEffectfulFacadeEntryUsesTheSameRetainedTerminalOwnerBeforeAnyRuntimeAccess() = runTest {
        val job = SupervisorJob()
        val constructor = RpcPhoneLab::class.java.declaredConstructors.single { it.parameterCount == 4 }
        constructor.isAccessible = true
        val lab = constructor.newInstance(CoroutineScope(coroutineContext.minusKey(Job) + job), null, null, null)
            as RpcPhoneLab
        val field = RpcPhoneLab::class.java.getDeclaredField("operationFailures")
        field.isAccessible = true
        val failures = field.get(lab) as PhoneOperationFailureState
        val original = LinkageError("synthetic private original native error")
        failures.retain(original)
        var callbacks = 0
        val actions: List<suspend () -> Unit> = listOf(
            { lab.invitation() },
            { lab.approve("unused") },
            { lab.reject("unused") },
            { lab.revoke("unused") },
            { lab.pairAndConnect("unused") },
            { lab.connect("unused", "unused", 0) },
            { lab.mobileReadyRecord("unused") },
            { lab.mobileClosedRecord(controlHealthy = true) },
            { lab.beginSelectNearby("unused", true) { callbacks++ } },
            { lab.beginPairAndConnect("unused") { callbacks++ } },
            { lab.beginConnect("unused", "unused", 0) { callbacks++ } },
            { lab.beginExample(RpcApplicationExample.GetUser) { callbacks++ } },
            { lab.beginRequest(RpcApplicationInput.parse(RpcApplicationProcedure.GetUser, "1", "0", "1", "")) {
                callbacks++
            } },
            { lab.echo(false) { callbacks++ } },
        )
        for (action in actions) {
            val failure = assertFailsWith<PhoneOperationTerminalFailure> { action() }
            assertSame(failures.terminal, failure)
            assertSame(original, failure.originalFailure)
        }
        assertEquals(0, callbacks)
        // The actual facade close still cancels/joins its owned scope, then returns non-success.
        val closed = assertFailsWith<PhoneOperationTerminalFailure> { lab.close() }
        assertTrue(job.isCompleted)
        assertSame(failures.terminal, closed)
        assertSame(original, closed.originalFailure)
        assertSame(closed, assertFailsWith<PhoneOperationTerminalFailure> {
            lab.mobileClosedRecord(controlHealthy = true)
        })
    }
}
