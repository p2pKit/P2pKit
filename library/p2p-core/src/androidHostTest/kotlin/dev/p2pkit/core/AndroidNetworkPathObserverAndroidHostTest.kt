package dev.p2pkit.core

import dev.p2pkit.core.testfixtures.RecordingLogger
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Host callback/ownership checks using the injected monitor, never Android framework methods. */
class AndroidNetworkPathObserverAndroidHostTest {
    @Test
    fun retainedCallbackRestartWarnsAndSuccessfulCloseRetryRestoresFreshGeneration() = runBlocking {
        val monitor = RetainingNetworkPathMonitor()
        val logger = RecordingLogger()
        val observer = AndroidNetworkPathObserver(monitor, logger)
        try {
            observer.start()
            val first = monitor.registrations.single()
            first.onAvailable("wifi")
            assertEquals(NetworkPathStatus.Satisfied, observer.status.value)

            observer.start()
            assertEquals(1, monitor.registrations.size)
            assertTrue(logger.warnings.isEmpty(), "healthy idempotence is not failed cleanup")

            val unregisterFailure = IllegalStateException("unregister failed")
            monitor.unregisterFailure = unregisterFailure
            observer.close()
            assertEquals(1, logger.warnings.size)
            assertSame(unregisterFailure, logger.entries.last().throwable)
            observer.start()

            assertEquals(1, monitor.registrations.size, "restart must not attach over retained ownership")
            assertSame(first, monitor.active)
            assertEquals(NetworkPathStatus.Satisfied, observer.status.value, "restart must not fabricate path status")
            assertEquals(2, logger.warnings.size, "restart needs a warning distinct from the close failure")
            assertTrue(logger.warnings.last().contains("retry close() to unregister"))
            first.onLost("wifi")
            assertEquals(NetworkPathStatus.Unsatisfied, observer.status.value)
            first.onAvailable("ethernet")
            assertEquals(NetworkPathStatus.Satisfied, observer.status.value, "retained callbacks remain authoritative")

            monitor.unregisterFailure = null
            observer.close()
            assertEquals(listOf(first, first), monitor.unregisterAttempts, "close must retry the retained registration")
            assertNull(monitor.active)
            assertEquals(NetworkPathStatus.Unknown, observer.status.value)
            first.onAvailable("stale")
            assertEquals(NetworkPathStatus.Unknown, observer.status.value)

            observer.start()
            val second = monitor.registrations.last()
            assertEquals(2, monitor.registrations.size)
            first.onLost("ethernet")
            assertEquals(
                NetworkPathStatus.Unknown,
                observer.status.value,
                "old callbacks cannot update the new generation"
            )
            second.onAvailable("wifi-new")
            assertEquals(NetworkPathStatus.Satisfied, observer.status.value)

            observer.start()
            assertEquals(2, monitor.registrations.size)
            assertEquals(2, logger.warnings.size, "successful detachment must clear the failed-unregister diagnostic")
            assertEquals(RecordingLogger.Level.DEBUG, logger.entries.last().level)
        } finally {
            monitor.unregisterFailure = null
            observer.close()
        }
        assertNull(monitor.active)
        assertEquals(NetworkPathStatus.Unknown, observer.status.value)
    }

    @Test
    fun throwingDiagnosticsCannotAlterRetainedCallbackOrCloseRetry() = runBlocking {
        val monitor = RetainingNetworkPathMonitor()
        var diagnosticCalls = 0
        val logger = object : P2pLogger by P2pLogger.NoOp {
            override fun debug(message: String) {
                diagnosticCalls += 1
                throw CancellationException("diagnostic callback cancelled")
            }

            override fun warn(message: String, throwable: Throwable?) {
                diagnosticCalls += 1
                throw IllegalStateException("diagnostic callback failed")
            }
        }
        val observer = AndroidNetworkPathObserver(monitor, logger)
        try {
            observer.start()
            val first = monitor.registrations.single()
            first.onAvailable("wifi")
            observer.start()
            monitor.unregisterFailure = IllegalStateException("unregister failed")
            observer.close()
            observer.start()
            assertEquals(3, diagnosticCalls)
            assertSame(first, monitor.active)
            assertEquals(1, monitor.registrations.size)
            assertEquals(NetworkPathStatus.Satisfied, observer.status.value)

            monitor.unregisterFailure = null
            observer.close()
            assertEquals(listOf(first, first), monitor.unregisterAttempts)
            assertEquals(NetworkPathStatus.Unknown, observer.status.value)
            observer.start()
            assertEquals(2, monitor.registrations.size)
        } finally {
            monitor.unregisterFailure = null
            observer.close()
        }
        assertNull(monitor.active)
    }
}

private class RetainingNetworkPathMonitor : AndroidNetworkPathMonitor {
    val registrations = mutableListOf<AndroidNetworkPathListener>()
    val unregisterAttempts = mutableListOf<AndroidNetworkPathListener>()
    var active: AndroidNetworkPathListener? = null
        private set
    var unregisterFailure: Throwable? = null

    override fun register(listener: AndroidNetworkPathListener) {
        check(active == null) { "a callback is already registered" }
        registrations += listener
        active = listener
    }

    override fun unregister() {
        unregisterAttempts += checkNotNull(active)
        unregisterFailure?.let { throw it }
        active = null
    }
}
