package dev.p2pkit.transport.lan

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.TimeUnit
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class MacLanVerificationCommandTest {
    @Test fun successfulOutputRetiresEveryOwnedStream() {
        val process = FakeProcess()
        assertEquals("fixture", MacLanVerificationCommand.collect(process))
        assertTrue(process.stdoutClosed && process.stderrClosed && process.stdinClosed)
        assertFalse(process.alive)
    }

    @Test fun stdinAndOutputObservationFailuresStillRetireProcess() {
        for (stdinFails in listOf(true, false)) {
            val failure = IllegalStateException("startup")
            val process = FakeProcess().apply {
                if (stdinFails) closeFailure = failure else observationFailure = failure
            }
            val actual = assertFailsWith<IllegalStateException> {
                MacLanVerificationCommand.collect(process)
            }
            assertSame(failure, actual)
            assertTrue(process.destroyed && process.stdoutClosed && process.stderrClosed)
            assertFalse(process.alive)
        }
    }

    @Test fun primaryRejectionSurvivesCleanupFailure() {
        val process = FakeProcess().apply { exit = 7; errorCloseFailure = IllegalStateException("cleanup") }
        val failure = assertFailsWith<IllegalStateException> { MacLanVerificationCommand.collect(process) }
        assertEquals("Installed native verification failed", failure.message)
        assertTrue(failure.suppressed.any { it.message == "cleanup" })
        assertTrue(process.stdoutClosed && process.stdinClosed)
    }

    @Test fun interruptedExecutionAndCleanupStillRetireAndRestoreInterrupt() {
        val process = FakeProcess().apply { interruptedWaits = 2 }
        try {
            assertFailsWith<InterruptedException> { MacLanVerificationCommand.collect(process) }
            assertTrue(Thread.currentThread().isInterrupted)
            assertTrue(process.destroyed && process.stdoutClosed && process.stderrClosed)
            assertFalse(process.alive)
        } finally {
            Thread.interrupted()
        }
    }

    @Test fun excessiveOutputIsRejected() {
        val process = FakeProcess(ByteArray(65_537))
        assertFailsWith<IllegalStateException> { MacLanVerificationCommand.collect(process) }
        assertTrue(process.stdoutClosed && process.stderrClosed)
    }

    @Test fun failedExitedLeaderWithHeldWriterDoesNotBlockReadOrClaimSuccess() {
        val process = FakeProcess().apply { writerHeld = true; exit = 7; alive = false }
        assertFailsWith<IllegalStateException> { MacLanVerificationCommand.collect(process) }
        assertTrue(process.stdoutClosed && process.stderrClosed)
        assertFalse(process.destroyed) // No signal to the exited leader or an unowned descendant.
    }

    private class FakeProcess(bytes: ByteArray = "fixture".toByteArray()) : Process() {
        var alive = true
        var destroyed = false
        var stdinClosed = false
        var stdoutClosed = false
        var stderrClosed = false
        var exit = 0
        var interruptedWaits = 0
        var closeFailure: RuntimeException? = null
        var errorCloseFailure: RuntimeException? = null
        var observationFailure: RuntimeException? = null
        var writerHeld = false
        private val stdin = object : ByteArrayOutputStream() {
            override fun close() { stdinClosed = true; closeFailure?.let { throw it } }
        }
        private val stdout = object : ByteArrayInputStream(bytes) {
            override fun available(): Int {
                observationFailure?.let { throw it }
                return if (writerHeld) 0 else super.available()
            }
            override fun read(b: ByteArray, off: Int, len: Int): Int {
                check(!writerHeld) { "Must not block on an inherited writer" }
                return super.read(b, off, len)
            }
            override fun close() { stdoutClosed = true; super.close() }
        }
        private val stderr = object : ByteArrayInputStream(byteArrayOf()) {
            override fun close() { stderrClosed = true; errorCloseFailure?.let { throw it }; super.close() }
        }
        override fun getOutputStream(): OutputStream = stdin
        override fun getInputStream(): InputStream = stdout
        override fun getErrorStream(): InputStream = stderr
        override fun waitFor(): Int { alive = false; return exit }
        override fun waitFor(timeout: Long, unit: TimeUnit): Boolean {
            if (interruptedWaits > 0) { interruptedWaits--; throw InterruptedException("fixture") }
            alive = false
            return true
        }
        override fun exitValue(): Int = exit
        override fun destroy() { destroyed = true; alive = false }
        override fun destroyForcibly(): Process = apply { destroy() }
        override fun isAlive(): Boolean = alive
    }
}
