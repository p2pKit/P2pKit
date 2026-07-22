package dev.p2pkit.core.internal

import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.NetworkPathStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame

class NetworkPathCallbackStateTest {

    @Test
    fun closeClearsRetainedNetworksAndInvalidatesStaleCallbacks() {
        val state = NetworkPathCallbackState<String>()
        val first = assertNotNull(state.begin())

        assertEquals(NetworkPathStatus.Satisfied, state.available(first, "wifi"))
        assertEquals(NetworkPathStatus.Unknown, state.detach(first))
        assertNull(state.lost(first, "wifi"), "a callback after close must be ignored")
        assertNull(
            state.publish(first, NetworkPathStatus.Satisfied),
            "a cancelled native monitor must not restore stale status"
        )

        val second = assertNotNull(state.begin())
        assertNotEquals(first, second, "restart must have a distinct callback generation")
        assertNull(state.available(first, "stale"), "the prior generation must stay invalid")
        assertEquals(NetworkPathStatus.Satisfied, state.available(second, "ethernet"))
    }

    @Test
    fun losingOneOfSeveralNetworksDoesNotPublishUnsatisfied() {
        val state = NetworkPathCallbackState<String>()
        val generation = assertNotNull(state.begin())

        assertEquals(NetworkPathStatus.Satisfied, state.available(generation, "wifi"))
        assertEquals(NetworkPathStatus.Satisfied, state.available(generation, "ethernet"))
        assertNull(state.lost(generation, "wifi"))
        assertEquals(NetworkPathStatus.Unsatisfied, state.lost(generation, "ethernet"))
    }

    @Test
    fun failedUnregisterRetainsOwnershipUntilSuccessfulCleanup() {
        val state = NetworkPathCallbackState<String>()
        val generation = assertNotNull(state.begin())
        assertEquals(NetworkPathStatus.Satisfied, state.available(generation, "wifi"))

        // Native unregister failed: the observer deliberately does not call
        // detach, so ownership and callback authority must remain intact.
        assertNull(state.begin(), "restart must not attach over retained ownership")
        assertEquals(NetworkPathStatus.Unsatisfied, state.lost(generation, "wifi"))

        assertEquals(NetworkPathStatus.Unknown, state.detach(generation))
        val restarted = assertNotNull(state.begin())
        assertNotEquals(generation, restarted)
        assertNull(state.available(generation, "stale"))
        assertEquals(NetworkPathStatus.Satisfied, state.available(restarted, "ethernet"))
    }

    @Test
    fun androidDefaultSelectionUsesRegisteredContextAndPreservesFallback() {
        val fallback = MarkerNetworkPathObserver()
        val wired = MarkerNetworkPathObserver()

        assertSame(
            fallback,
            selectAndroidDefaultPathObserver<String>(null, fallback) { wired }
        )
        assertSame(
            wired,
            selectAndroidDefaultPathObserver("registered", fallback) { context ->
                assertEquals("registered", context)
                wired
            }
        )
    }
}

private class MarkerNetworkPathObserver : NetworkPathObserver {
    override val status: StateFlow<NetworkPathStatus> = MutableStateFlow(NetworkPathStatus.Unknown)
    override suspend fun start() = Unit
    override suspend fun close() = Unit
}
