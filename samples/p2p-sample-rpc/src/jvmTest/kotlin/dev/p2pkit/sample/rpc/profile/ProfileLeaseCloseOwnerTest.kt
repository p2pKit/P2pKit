package dev.p2pkit.sample.rpc.profile

import java.io.IOException
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Callback injection exercises deterministic release/channel failures without pretending to be a native test. */
class ProfileLeaseCloseOwnerTest {
    @Test fun successfulLeaseReleasesLockThenChannelExactlyOnce() {
        val events = mutableListOf<String>()
        val lease = ProfileLeaseCloseOwner({ events += "lock" }, { events += "channel" })
        lease.close()
        lease.close()
        assertEquals(listOf("lock", "channel"), events)
    }

    @Test fun bothFailuresRetainOriginalWithDistinctSuppressedCleanupAndNoRetry() {
        val primary = IOException("synthetic release failure")
        val cleanup = IOException("synthetic channel failure")
        val events = mutableListOf<String>()
        val lease = ProfileLeaseCloseOwner({ events += "lock"; throw primary },
            { events += "channel"; throw cleanup })
        assertSame(primary, assertFailsWith<IOException> { lease.close() })
        assertContentEquals(arrayOf(cleanup), primary.suppressed)
        assertSame(primary, assertFailsWith<IOException> { lease.close() })
        assertEquals(listOf("lock", "channel"), events)
        assertContentEquals(arrayOf(cleanup), primary.suppressed)
    }

    @Test fun releaseFailureStillClosesChannelAndIdenticalFailureCannotSuppressItself() {
        val primary = IOException("synthetic shared failure")
        for (repeatFailure in listOf(false, true)) {
            var channels = 0
            val lease = ProfileLeaseCloseOwner({ throw primary }, {
                channels++
                if (repeatFailure) throw primary
            })
            assertSame(primary, assertFailsWith<IOException> { lease.close() })
            assertSame(primary, assertFailsWith<IOException> { lease.close() })
            assertEquals(1, channels)
            assertTrue(primary.suppressed.isEmpty())
        }
    }

    @Test fun channelOnlyFailureIsTheRetainedTerminalResult() {
        val primary = IOException("synthetic channel failure")
        var releases = 0
        var channels = 0
        val lease = ProfileLeaseCloseOwner({ releases++ }, { channels++; throw primary })
        assertSame(primary, assertFailsWith<IOException> { lease.close() })
        assertSame(primary, assertFailsWith<IOException> { lease.close() })
        assertEquals(1, releases)
        assertEquals(1, channels)
        assertTrue(primary.suppressed.isEmpty())
    }

    @Test fun acquisitionCleanupNeverReplacesPrimaryOrAddsSelfSuppression() {
        val primary = IOException("synthetic acquisition failure")
        val cleanup = IOException("synthetic channel close failure")
        var calls = 0
        closeAfterProfileFailure(primary) { calls++ }
        closeAfterProfileFailure(primary) { calls++; throw primary }
        closeAfterProfileFailure(primary) { calls++; throw cleanup }
        assertEquals(3, calls)
        assertContentEquals(arrayOf(cleanup), primary.suppressed)
    }
}
