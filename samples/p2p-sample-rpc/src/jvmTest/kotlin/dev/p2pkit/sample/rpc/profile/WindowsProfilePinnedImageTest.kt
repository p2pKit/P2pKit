package dev.p2pkit.sample.rpc.profile

import java.io.IOException
import java.nio.ByteBuffer
import java.security.MessageDigest
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Inert channel controls, not Windows sharing, native loading or installed-runtime evidence. */
class WindowsProfilePinnedImageTest {
    private class Owner(var bytes: ByteArray = WindowsProfilePeFixture.create()) : WindowsProfilePinnedImage.Owner {
        var closes = 0
        var reads = 0
        var sizes = 0
        var maximumRead = Int.MAX_VALUE
        var reportedSize: Long? = null
        var readOverride: ((ByteBuffer, Long) -> Int)? = null
        var beforeSize: (() -> Unit)? = null
        var closeFailure: Throwable? = null
        val buffers = mutableListOf<ByteArray>()
        override fun size(): Long {
            sizes++
            beforeSize?.invoke()
            return reportedSize ?: bytes.size.toLong()
        }
        override fun read(destination: ByteBuffer, position: Long): Int {
            reads++
            buffers += destination.array()
            readOverride?.let { return it(destination, position) }
            if (position >= bytes.size) return -1
            val count = minOf(destination.remaining(), bytes.size - position.toInt(), maximumRead)
            destination.put(bytes, position.toInt(), count)
            return count
        }
        override fun close() { closes++; closeFailure?.let { throw it } }
    }

    private val original = WindowsProfilePeFixture.create()
    private fun manifest() = WindowsProfileByteManifest.produce("a".repeat(40), "b".repeat(40), true, original)
    private fun authority(bytes: ByteArray) = WindowsProfileByteManifest.Authority(
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) },
        "a".repeat(40), "b".repeat(40),
    )
    private fun open(owner: Owner): WindowsProfilePinnedImage {
        val manifest = manifest()
        return WindowsProfilePinnedImage.openForValidation(manifest, authority(manifest)) { owner }
    }

    @Test fun originalOwnerRemainsHeldThroughReadbackAndExplicitClose() {
        val owner = Owner()
        val pin = open(owner)
        assertEquals(WindowsProfilePinnedImage.Scope.INERT_VALIDATION_ONLY, pin.scope)
        assertEquals(0, owner.closes)
        assertEquals(original.size, pin.verify().dllBytes)
        assertEquals(WindowsProfilePeImage.verify(original).namedImports, pin.verify().namedImports)
        assertTrue(owner.sizes >= 6)
        assertTrue(owner.buffers.all { bytes -> bytes.all { it == 0.toByte() } })
        pin.close()
        pin.close()
        assertEquals(1, owner.closes)
        assertFails { pin.verify() }
    }

    @Test fun callerManifestMutationCannotReplaceOrDestroyThePrivatePin() {
        val owner = Owner()
        val manifest = manifest()
        val pin = WindowsProfilePinnedImage.openForValidation(manifest, authority(manifest)) { owner }
        manifest.fill(0)
        try { assertEquals(original.size, pin.verify().dllBytes) } finally { pin.close() }
    }

    @Test fun malformedManifestBoundsRejectBeforeOwnerAcquisition() {
        for (bytes in listOf(ByteArray(0), ByteArray(WindowsProfileByteManifest.MAXIMUM_MANIFEST_BYTES + 1))) {
            var acquired = false
            assertFails {
                WindowsProfilePinnedImage.openForValidation(bytes, authority(manifest())) {
                    acquired = true
                    Owner()
                }
            }
            assertFalse(acquired)
        }
    }

    @Test fun wrongIndependentManifestAuthorityClosesWithoutReturningAPin() {
        val owner = Owner()
        val manifest = manifest()
        val wrong = WindowsProfileByteManifest.Authority("0".repeat(64), "a".repeat(40), "b".repeat(40))
        assertFails { WindowsProfilePinnedImage.openForValidation(manifest, wrong) { owner } }
        assertEquals(1, owner.closes)
    }

    @Test fun invalidFileSizesRejectBeforeReadAndCloseTheAcquiredOwner() {
        for (size in listOf(-1L, 0, 511, WindowsProfilePeImage.MAXIMUM_BYTES.toLong() + 1, Long.MAX_VALUE)) {
            val owner = Owner().also { it.reportedSize = size }
            assertFails { open(owner) }
            assertEquals(0, owner.reads)
            assertEquals(1, owner.closes)
        }
    }

    @Test fun shortPositiveReadsCompleteWithoutReopeningTheOriginalOwner() {
        val owner = Owner().also { it.maximumRead = 3 }
        open(owner).use { assertEquals(original.size, it.verify().dllBytes) }
        assertTrue(owner.reads > original.size / 3)
        assertEquals(1, owner.closes)
    }

    @Test fun zeroProgressOrPrematureEofFailsInsteadOfSpinning() {
        for (count in listOf(0, -1)) {
            val owner = Owner().also { it.readOverride = { _, _ -> count } }
            assertFails { open(owner) }
            assertEquals(1, owner.reads)
            assertEquals(1, owner.closes)
        }
    }

    @Test fun inconsistentReadCountFailsBeforeAdvancing() {
        val owner = Owner().also { it.readOverride = { _, _ -> 1 } }
        assertFails { open(owner) }
        assertEquals(1, owner.reads)
        assertEquals(1, owner.closes)
    }

    @Test fun trailingByteOrSizeChangeFailsAndRetiresTheOwner() {
        val longer = Owner(original + byteArrayOf(1)).also { it.reportedSize = original.size.toLong() }
        assertFails { open(longer) }
        assertEquals(1, longer.closes)
        val changed = Owner()
        changed.beforeSize = { if (changed.sizes == 2) changed.reportedSize = original.size.toLong() + 1 }
        assertFails { open(changed) }
        assertEquals(1, changed.closes)
    }

    @Test fun changedBytesBetweenAdmissionAndReadbackNeverReturnAPin() {
        val owner = Owner()
        owner.beforeSize = { if (owner.sizes == 3) owner.bytes[0x400] = 1 }
        assertFails { open(owner) }
        assertEquals(1, owner.closes)
    }

    @Test fun laterTamperingSealsReadAdmissionButRetainsTheOriginalCloseOwner() {
        val owner = Owner()
        val pin = open(owner)
        owner.bytes[0x400] = 1
        val failure = assertFails { pin.verify() }
        val reads = owner.reads
        owner.bytes = original.copyOf()
        assertSame(failure, assertFails { pin.verify() })
        assertEquals(reads, owner.reads)
        assertEquals(0, owner.closes)
        pin.close()
        assertEquals(1, owner.closes)
    }

    @Test fun closeFailureIsRetainedAndNeverRetried() {
        val owner = Owner()
        val pin = open(owner)
        val failure = IOException("synthetic close")
        owner.closeFailure = failure
        assertSame(failure, assertFails { pin.close() })
        assertSame(failure, assertFails { pin.close() })
        assertFails { pin.verify() }
        assertEquals(1, owner.closes)
    }

    @Test fun initializationFailurePreservesIndependentCleanupFailure() {
        val owner = Owner().also { it.reportedSize = 0 }
        val cleanup = IOException("synthetic close")
        owner.closeFailure = cleanup
        val failure = assertFails { open(owner) } as WindowsProfilePinnedImage.AcquisitionFailure
        assertTrue(failure.cause is IllegalArgumentException)
        assertSame(cleanup, failure.cleanupFailure)
        assertTrue(failure.suppressed.any { it === cleanup })
        assertFails { failure.retainedPin.verify() }
        assertSame(cleanup, assertFails { failure.retainedPin.close() })
        assertEquals(1, owner.closes)
    }

    @Test fun sameReadAndCloseFailureCannotCauseSelfSuppressionOrRetry() {
        val failure = IOException("synthetic read and close")
        val owner = Owner().also { it.readOverride = { _, _ -> throw failure }; it.closeFailure = failure }
        val retained = assertFails { open(owner) } as WindowsProfilePinnedImage.AcquisitionFailure
        assertSame(failure, retained.cause)
        assertSame(failure, retained.cleanupFailure)
        assertEquals(0, retained.suppressed.size)
        assertSame(failure, assertFails { retained.retainedPin.close() })
        assertEquals(0, failure.suppressed.size)
        assertEquals(1, owner.closes)
    }

    @Test fun readErrorAndCleanupExceptionRetainExactOwnersWithoutDiagnosticSuppression() {
        assertRetainedReportingError(OutOfMemoryError("synthetic image read"), IOException("synthetic close"))
    }

    @Test fun readExceptionAndCleanupErrorRetainExactOwnersWithoutDiagnosticSuppression() {
        assertRetainedReportingError(IOException("synthetic image read"), OutOfMemoryError("synthetic close"))
    }

    @Test fun distinctReadAndCleanupErrorsRetainExactOwnersWithoutDiagnosticSuppression() {
        assertRetainedReportingError(LinkageError("synthetic image read"), OutOfMemoryError("synthetic close"))
    }

    @Test fun sameReadAndCleanupErrorDoesNotCauseSelfSuppressionOrRetry() {
        val failure = OutOfMemoryError("synthetic image read and close")
        assertRetainedReportingError(failure, failure)
    }

    /** Synthetic Errors exercise transfer branches, not heap exhaustion or allocation impossibility. */
    private fun assertRetainedReportingError(original: Throwable, cleanup: Throwable) {
        val owner = Owner().also { it.readOverride = { _, _ -> throw original }; it.closeFailure = cleanup }
        val failure = assertFails { open(owner) } as WindowsProfilePinnedImage.AcquisitionFailure
        assertSame(original, failure.cause)
        assertSame(cleanup, failure.cleanupFailure)
        assertTrue(failure.suppressed.isEmpty())
        assertTrue(original.suppressed.isEmpty())
        assertTrue(cleanup.suppressed.isEmpty())
        assertEquals(WindowsProfilePinnedImage.Scope.INERT_VALIDATION_ONLY, failure.retainedPin.scope)
        val reads = owner.reads
        val sizes = owner.sizes
        assertFails { failure.retainedPin.verify() }
        assertEquals(reads, owner.reads)
        assertEquals(sizes, owner.sizes)
        repeat(2) { assertSame(cleanup, assertFails { failure.retainedPin.close() }) }
        assertEquals(1, owner.closes)
        assertTrue(owner.buffers.isNotEmpty())
        assertTrue(owner.buffers.all { bytes -> bytes.all { it == 0.toByte() } })
    }

    @Test fun readErrorWithSuccessfulClosePropagatesOriginalWithoutAnUncertainOwner() {
        val original = OutOfMemoryError("synthetic image read")
        val owner = Owner().also { it.readOverride = { _, _ -> throw original } }
        assertSame(original, assertFails { open(owner) })
        assertEquals(1, owner.closes)
        assertTrue(original.suppressed.isEmpty())
        assertTrue(owner.buffers.all { bytes -> bytes.all { it == 0.toByte() } })
    }

    @Test fun preOwnerErrorDoesNotManufactureRetainedOwnership() {
        val original = OutOfMemoryError("synthetic owner acquisition")
        val manifest = manifest()
        var attempts = 0
        assertSame(original, assertFails {
            WindowsProfilePinnedImage.openForValidation(manifest, authority(manifest)) {
                attempts++
                throw original
            }
        })
        assertEquals(1, attempts)
        assertTrue(original.suppressed.isEmpty())
    }

    @Test fun acquisitionFailureDoesNotManufactureAnOwner() {
        val failure = IOException("synthetic acquisition")
        val manifest = manifest()
        assertSame(failure, assertFails {
            WindowsProfilePinnedImage.openForValidation(manifest, authority(manifest)) { throw failure }
        })
    }

    @Test fun probeRefusalHelperAcceptsOnlySelectedAcquisitionIoFailure() {
        WindowsProfilePinnedImageWindowsProbe.requireIoAcquisitionRefused { throw IOException("synthetic open") }
        val later = IOException("not the selected acquisition phase")
        assertSame(later, assertFails {
            WindowsProfilePinnedImageWindowsProbe.requireIoAcquisitionRefused({ false }) { throw later }
        })
        val other = IllegalArgumentException("synthetic validation")
        assertSame(other, assertFails {
            WindowsProfilePinnedImageWindowsProbe.requireIoAcquisitionRefused { throw other }
        })
    }

    @Test fun probeRefusalHelperRejectsSuccessfulAcquisitionRegardlessOfCloseOutcome() {
        for (closeFailure in listOf(null, IOException("synthetic close"))) {
            var closes = 0
            val failure = assertFails {
                WindowsProfilePinnedImageWindowsProbe.requireIoAcquisitionRefused {
                    AutoCloseable { closes++; closeFailure?.let { throw it } }
                }
            }
            assertTrue(failure is IllegalStateException)
            assertEquals(1, closes)
            assertEquals(if (closeFailure == null) emptyList() else listOf(closeFailure), failure.suppressed.toList())
        }
    }

    @Test fun closeWaitsForActualReadReturnAndCannotReleaseALiveChannel() {
        val owner = Owner()
        val pin = open(owner)
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val closing = CountDownLatch(1)
        val closed = CountDownLatch(1)
        val failure = AtomicReference<Throwable?>()
        owner.readOverride = { destination, position ->
            entered.countDown()
            check(release.await(5, TimeUnit.SECONDS))
            if (position >= original.size) -1 else {
                val count = minOf(destination.remaining(), original.size - position.toInt())
                destination.put(original, position.toInt(), count)
                count
            }
        }
        val reader = Thread { try { pin.verify() } catch (caught: Throwable) { failure.set(caught) } }
        val closer = Thread {
            closing.countDown()
            try { pin.close() } catch (caught: Throwable) { failure.set(caught) } finally { closed.countDown() }
        }
        try {
            reader.start()
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            closer.start()
            assertTrue(closing.await(5, TimeUnit.SECONDS))
            assertFalse(closed.await(100, TimeUnit.MILLISECONDS))
            assertEquals(0, owner.closes)
        } finally {
            release.countDown()
            reader.join(5_000)
            if (closer.state != Thread.State.NEW) closer.join(5_000) else pin.close()
        }
        assertFalse(reader.isAlive)
        assertFalse(closer.isAlive)
        assertEquals(null, failure.get())
        assertEquals(1, owner.closes)
    }
}
