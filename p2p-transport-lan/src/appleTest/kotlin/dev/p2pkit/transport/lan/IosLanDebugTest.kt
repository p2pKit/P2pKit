package dev.p2pkit.transport.lan

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class IosLanDebugTest {

    private var previousConsoleMirror: Boolean = false
    private var previousHistoryRetention: Boolean = false

    @BeforeTest
    fun captureSettings() {
        previousConsoleMirror = IosLanDebug.mirrorToConsole
        previousHistoryRetention = IosLanDebug.retainHistory
        IosLanDebug.mirrorToConsole = false
        IosLanDebug.retainHistory = false
        IosLanDebug.log("test", "clear replay")
    }

    @AfterTest
    fun restoreSettings() {
        IosLanDebug.retainHistory = false
        IosLanDebug.log("test", "clear replay")
        IosLanDebug.mirrorToConsole = previousConsoleMirror
        IosLanDebug.retainHistory = previousHistoryRetention
    }

    @Test
    fun historyIsOptInAndRetainedLinesAreSanitized() {
        IosLanDebug.log("peer", "not retained")
        assertTrue(IosLanDebug.events.replayCache.isEmpty())

        val marker = "retained-diagnostic"
        IosLanDebug.retainHistory = true
        IosLanDebug.log("peer\u001B[31m", "$marker\u202Espoof")

        val line = IosLanDebug.events.replayCache.lastOrNull { marker in it }
        assertNotNull(line)
        assertFalse('\u001B' in line)
        assertFalse('\u202E' in line)
        assertTrue('\uFFFD' in line)
    }

    @Test
    fun disablingReplayDoesNotDropDeliveryToAnActiveSubscriber() = runBlocking {
        val marker = "live-diagnostic"
        val subscribed = CompletableDeferred<Unit>()
        val received = async {
            IosLanDebug.events
                .onSubscription { subscribed.complete(Unit) }
                .first { marker in it }
        }
        subscribed.await()

        IosLanDebug.retainHistory = false
        IosLanDebug.log("peer", marker)

        assertTrue(marker in withTimeout(1_000) { received.await() })
        assertTrue(IosLanDebug.events.replayCache.isEmpty())
    }
}
