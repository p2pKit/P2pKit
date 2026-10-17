package dev.p2pkit.sample.rpc

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Exact owned retirement policy only; no platform factory or native profile simulation is credited. */
class PhoneFactoryOwnerTest {
    private class ReportingError(message: String) : Error(message) { val originalOwner = Any() }

    @Test
    fun ordinaryFailureAndCancellationRemainOriginalOnlyAfterSuccessfulPhysicalRetirement() = runTest {
        for (original in listOf(IllegalStateException("synthetic ordinary failure"),
                CancellationException("synthetic cancelled factory"))) {
            val resource = Any()
            var closes = 0
            val owner = PhoneFactoryOwner<Any> { assertSame(resource, it); closes++ }
            owner.resource = resource
            val observed = assertFailsWith<Exception> { owner.failed(original) }
            assertSame(original, observed)
            assertEquals(1, closes)
            assertTrue(checkNotNull(owner.scope.coroutineContext[Job]).isCompleted)
            assertNull(owner.resourceCloseFailure)
        }
    }

    @Test
    fun nativeCloseErrorDoesNotSkipOwnedScopeDrainOrLoseOriginalResourceAndFailure() = runTest {
        for (original in listOf(IllegalStateException("synthetic acquisition failure"),
                ReportingError("synthetic acquisition error"))) {
            val cleanup = ReportingError("synthetic close error")
            val resource = Any()
            var closes = 0
            val owner = PhoneFactoryOwner<Any> { assertSame(resource, it); closes++; throw cleanup }
            owner.resource = resource
            val observed = assertFailsWith<PhoneFactoryOwnershipError> { owner.failed(original) }
            assertSame(owner.failure, observed)
            assertSame(original, observed.initialFailure)
            assertSame(cleanup, observed.resourceCloseFailure)
            assertSame(resource, observed.retainedResource)
            assertTrue(checkNotNull(observed.retainedScope.coroutineContext[Job]).isCompleted)
            assertNull(observed.scopeCloseFailure)
            assertNull(observed.cause)
            assertTrue(original.suppressedExceptions.isEmpty())
            assertTrue(cleanup.suppressedExceptions.isEmpty())
            assertFalse(observed.toString().contains("synthetic"))
            assertEquals(1, closes)
        }
    }

    @Test
    fun failingOwnedScopeCompletionCannotBecomeAProvenOrdinaryFactoryFailure() = runTest {
        val original = IllegalStateException("synthetic initialization failure")
        val cleanup = ReportingError("synthetic owned scope completion failure")
        val resource = Any()
        var closes = 0
        val owner = PhoneFactoryOwner<Any> { assertSame(resource, it); closes++ }
        owner.resource = resource
        val job = checkNotNull(owner.scope.coroutineContext[Job])
        job.invokeOnCompletion { throw cleanup }
        val observed = assertFailsWith<PhoneFactoryOwnershipError> { owner.failed(original) }
        assertSame(original, observed.initialFailure)
        assertSame(resource, observed.retainedResource)
        assertSame(cleanup, observed.scopeCloseFailure?.cause)
        assertNull(observed.resourceCloseFailure)
        assertNull(observed.cause)
        assertEquals(1, closes)
        assertTrue(job.isCompleted)
    }

    @Test
    fun nestedTerminalOperationFailureCannotBecomeAnOrdinaryRetryableFactoryException() = runTest {
        val operations = PhoneOperationFailureState()
        val original = ReportingError("synthetic retained native owner")
        operations.retain(original)
        val owner = PhoneFactoryOwner<Any> { error("No returned resource") }
        val observed = assertFailsWith<PhoneFactoryOwnershipError> { owner.failed(operations.terminal) }
        assertSame(operations.terminal, observed.initialFailure)
        assertSame(original, operations.terminal.originalFailure)
        assertNull(observed.retainedResource)
        assertTrue(checkNotNull(observed.retainedScope.coroutineContext[Job]).isCompleted)
    }
}
