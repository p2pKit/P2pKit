package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class AsyncCaptureOwnershipTest {
    @Test
    fun releaseBeforePostedRequestStartsPreventsUseAndRecyclesOnce() {
        var recycled = 0
        val owner = AsyncCaptureOwnership { recycled++ }
        owner.release()
        assertFalse(owner.start())
        owner.release()
        assertTrue(owner.retired())
        assertEquals(1, recycled)
    }

    @Test
    fun timeoutDuringNativeCopyRetainsDestinationUntilActualCallback() {
        var recycled = 0
        val owner = AsyncCaptureOwnership { recycled++ }
        assertTrue(owner.start())
        owner.release()
        assertFalse(owner.retired())
        assertEquals(0, recycled)
        owner.complete()
        assertTrue(owner.retired())
        assertEquals(1, recycled)
    }

    @Test
    fun completedDestinationRemainsReadableUntilConsumerReleases() {
        var recycled = 0
        val owner = AsyncCaptureOwnership { recycled++ }
        assertTrue(owner.start())
        owner.complete()
        assertFalse(owner.retired())
        assertEquals(0, recycled)
        owner.release()
        owner.release()
        assertTrue(owner.retired())
        assertEquals(1, recycled)
    }

    @Test
    fun synchronousRequestFailureRetiresWithoutClaimingSuccessfulCopy() {
        var recycled = 0
        val owner = AsyncCaptureOwnership { recycled++ }
        assertTrue(owner.start())
        owner.complete() // The request threw before accepting the destination.
        owner.release()
        assertTrue(owner.retired())
        assertEquals(1, recycled)
    }

    @Test
    fun missingCallbackNeverBecomesRetirement() {
        val owner = AsyncCaptureOwnership { error("Still in use") }
        assertTrue(owner.start())
        owner.release()
        repeat(10) { assertFalse(owner.retired()) }
    }

    @Test
    fun duplicateCompletionIsRejectedAndCannotDoubleRecycle() {
        var recycled = 0
        val owner = AsyncCaptureOwnership { recycled++ }
        assertTrue(owner.start())
        owner.release()
        owner.complete()
        assertFailsWith<IllegalStateException> { owner.complete() }
        assertEquals(1, recycled)
    }

    @Test
    fun disposalFailureIsNotSuccessfulRetirement() {
        val owner = AsyncCaptureOwnership { error("Recycle failed") }
        assertFailsWith<IllegalStateException> { owner.release() }
        assertFalse(owner.retired())
    }
}
