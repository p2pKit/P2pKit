package dev.p2pkit.sample.android.runtime

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

/** Pure request-boundary controls, not actual Android Home, Recents or privacy evidence. */
class LegacyNavigationTest {
    @Test
    fun closedActionsMapToPublicHomeAndRecentsOnly() {
        assertEquals(listOf("HOME", "RECENTS"), LegacyNavigationAction.entries.map { it.name })
        assertEquals(listOf(2, 3), LegacyNavigationAction.entries.map { it.platformAction })
    }

    @Test
    fun acceptedRequestIsPerformedOnceAndActualReturnIsReported() {
        val calls = mutableListOf<Int>()
        val results = mutableListOf<Boolean>()
        requestLegacyNavigation(LegacyNavigationAction.HOME, { calls.add(it); true }, results::add)
        assertEquals(listOf(2), calls)
        assertEquals(listOf(true), results)
    }

    @Test
    fun rejectedRequestIsReportedBeforeFixedFailureWithoutRetry() {
        val events = mutableListOf<String>()
        val failure = assertFailsWith<LegacyCaptureFailure> {
            requestLegacyNavigation(LegacyNavigationAction.RECENTS, {
                events.add("perform:$it")
                false
            }) { events.add("returned:$it") }
        }
        assertEquals(LegacyCaptureFailureCode.NAVIGATION_ACTION_REJECTED, failure.code)
        assertEquals(listOf("perform:3", "returned:false"), events)
    }

    @Test
    fun thrownRequestPreservesOriginalAndDoesNotInventReturnOrRetry() {
        val original = IllegalStateException("synthetic connection failure")
        var calls = 0
        val results = mutableListOf<Boolean>()
        val failure = assertFailsWith<IllegalStateException> {
            requestLegacyNavigation(LegacyNavigationAction.HOME, { calls++; throw original }, results::add)
        }
        assertSame(original, failure)
        assertEquals(1, calls)
        assertEquals(emptyList(), results)
    }

    @Test
    fun eachRequestedActionReturnsBeforeTheNextRequest() {
        val events = mutableListOf<String>()
        LegacyNavigationAction.entries.forEach { action ->
            requestLegacyNavigation(action, { events.add("perform:$it"); true }) {
                events.add("returned:${action.name}:$it")
            }
        }
        assertEquals(listOf("perform:2", "returned:HOME:true", "perform:3", "returned:RECENTS:true"), events)
    }
}
