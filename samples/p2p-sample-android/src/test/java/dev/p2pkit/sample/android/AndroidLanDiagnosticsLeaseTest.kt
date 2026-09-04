package dev.p2pkit.sample.android

import dev.p2pkit.transport.lan.AndroidLanDiag
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class AndroidLanDiagnosticsLeaseTest {
    private var previousEnabled: Boolean = false
    private var previousRetainHistory: Boolean = false
    private var previousTraceFrames: Boolean = false

    @BeforeTest
    fun captureHostSettings() {
        previousEnabled = AndroidLanDiag.enabled
        previousRetainHistory = AndroidLanDiag.retainHistory
        previousTraceFrames = AndroidLanDiag.traceFrames
        AndroidLanDiag.enabled = false
        AndroidLanDiag.traceFrames = false
        AndroidLanDiag.retainHistory = false
    }

    @AfterTest
    fun restoreHostSettings() {
        // Flush test-only history before restoring the host's retention mode.
        AndroidLanDiag.retainHistory = false
        AndroidLanDiag.enabled = previousEnabled
        AndroidLanDiag.traceFrames = previousTraceFrames
        AndroidLanDiag.retainHistory = previousRetainHistory
    }

    @Test
    fun releaseRestoresDisabledDefaultsAndIsIdempotent() {
        val lease = AndroidLanDiagnosticsLease.acquire()
        try {
            assertTrue(AndroidLanDiag.enabled)
            assertTrue(AndroidLanDiag.retainHistory)
        } finally {
            lease.release()
            lease.release()
        }
        assertFalse(AndroidLanDiag.enabled)
        assertFalse(AndroidLanDiag.retainHistory)
    }

    @Test
    fun releaseRestoresPreEnabledHostConfiguration() {
        AndroidLanDiag.enabled = true

        val lease = AndroidLanDiagnosticsLease.acquire()
        try {
            assertTrue(AndroidLanDiag.enabled)
            assertTrue(AndroidLanDiag.retainHistory)
        } finally {
            lease.release()
        }
        assertTrue(AndroidLanDiag.enabled)
        assertFalse(AndroidLanDiag.retainHistory)
    }

    @Test
    fun overlappingOwnersRetainThenClearHistoryAtTheFinalRelease() {
        val first = AndroidLanDiagnosticsLease.acquire()
        val second = AndroidLanDiagnosticsLease.acquire()
        val marker = "overlapping-lease-${System.nanoTime()}"
        emitRetainedDiagnostic(marker)
        try {
            first.release()
            assertTrue(AndroidLanDiag.enabled)
            assertTrue(AndroidLanDiag.retainHistory)
            assertTrue(AndroidLanDiag.events.replayCache.any { marker in it })
        } finally {
            first.release()
            second.release()
        }
        assertFalse(AndroidLanDiag.enabled)
        assertFalse(AndroidLanDiag.retainHistory)
        assertTrue(AndroidLanDiag.events.replayCache.none { marker in it })
    }

    @Test
    fun releasePreservesHistoryWhenTheHostAlreadyRetainedIt() {
        AndroidLanDiag.enabled = true
        AndroidLanDiag.retainHistory = true
        val hostMarker = "host-history-${System.nanoTime()}"
        emitRetainedDiagnostic(hostMarker)

        val lease = AndroidLanDiagnosticsLease.acquire()
        val leaseMarker = "lease-history-${System.nanoTime()}"
        emitRetainedDiagnostic(leaseMarker)
        try {
            assertTrue(AndroidLanDiag.events.replayCache.any { leaseMarker in it })
        } finally {
            lease.release()
        }

        assertTrue(AndroidLanDiag.enabled)
        assertTrue(AndroidLanDiag.retainHistory)
        assertTrue(AndroidLanDiag.events.replayCache.any { hostMarker in it })
        assertTrue(AndroidLanDiag.events.replayCache.any { leaseMarker in it })
    }

    private fun emitRetainedDiagnostic(marker: String) {
        AndroidLanDiag.traceFrames = true
        // Local JVM tests may use throwing android.jar log stubs. The event is
        // emitted before logcat is invoked, which is the behavior under test.
        runCatching { AndroidLanDiag.frame("lease-test", marker) }
        assertTrue(AndroidLanDiag.events.replayCache.any { marker in it })
    }
}
