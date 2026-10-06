package dev.p2pkit.sample.android.rpclab

import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcHostState
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class RpcLabEventLogTest {
    @Test
    fun boundedHistoryKeepsExactlyTheNewestEightyEventsInOrder() {
        val log = RpcLabEventLog()
        repeat(90) { log.record(RpcLabEventLog.Event.PairRequested) }
        assertEquals(80, log.lines.value.size)
        assertEquals("11 PairRequested", log.lines.value.first())
        assertEquals("90 PairRequested", log.lines.value.last())
    }

    @Test
    fun typedFailureContainsOnlyKindPhaseAndEvidenceNeverExceptionTextOrIdentity() {
        val log = RpcLabEventLog()
        val failure = RpcFailure(RpcFailureKind.DeadlineExceeded, RpcFailurePhase.Negotiation,
            executionEvidence = RpcExecutionEvidence.NotSent)
        assertEquals("DeadlineExceeded/Negotiation/NotSent", log.failure(failure))
        val privateValue = "rpc1|secret p2f1-private 192.168.1.42 message-content"
        assertEquals("LocalOrProtocolFailure", log.failure(IllegalStateException(privateValue)))
        assertFalse(log.lines.value.joinToString().contains(privateValue))
        assertEquals("1 Failure DeadlineExceeded/Negotiation/NotSent", log.lines.value.first())
        assertEquals("2 Failure LocalOrProtocolFailure", log.lines.value.last())
    }

    @Test
    fun refreshAndCleanupKeepThePreviousFailureAndOnlyHostReportsClientCount() {
        val log = RpcLabEventLog()
        log.failure(RpcFailure(RpcFailureKind.Authentication, RpcFailurePhase.Trust))
        val failure = log.lines.value.single()
        val client = log.snapshot(false, "Disconnected", 0, 0, 0, null)
        assertEquals("Client state=Disconnected; completed=0; queued=0", client)
        val host = log.snapshot(true, "Running", 2, 3, 1, 4)
        assertEquals("Host state=Running; connected clients=2; completed=3; queued=1", host)
        log.record(RpcLabEventLog.Event.CleanupCompleted)
        assertEquals(failure, log.lines.value.first())
        assertTrue(log.lines.value.contains("4 PendingRequests count=4"))
        assertEquals("5 CleanupCompleted", log.lines.value.last())
    }

    @Test
    fun runtimeStringsAreWhitelistedPerRoleAndCannotSmuggleNetworkOrInvitationData() {
        val log = RpcLabEventLog()
        RpcHostState.entries.forEach {
            assertTrue(log.snapshot(true, it.name, 0, 0, 0, null).contains("state=${it.name};"))
        }
        RpcConnectionState.entries.forEach {
            assertTrue(log.snapshot(false, it.name, 0, 0, 0, null).contains("state=${it.name};"))
        }
        assertTrue(log.snapshot(false, "Running", 0, 0, 0, null).contains("state=Unknown;"))
        val privateValue = "rpc1|hidden p2f1-private 10.0.0.1"
        assertEquals("Host state=Unknown; connected clients=0; completed=0; queued=0",
            log.snapshot(true, privateValue, -1, -2, -3, -4))
        assertFalse(log.lines.value.joinToString().contains(privateValue))
        assertTrue(log.lines.value.last().endsWith("count=0"))
    }

    @Test
    fun echoFiltersNativeStringMetadataAndNeverInventsAMissingPhaseOrEvidence() {
        val log = RpcLabEventLog()
        RpcFailureKind.entries.forEach {
            assertTrue(log.echo(0, 1, 10, it.name, "NotSent").contains("result=${it.name};"))
        }
        RpcExecutionEvidence.entries.forEach {
            assertTrue(log.echo(0, 1, 10, "Cancelled", it.name).contains("evidence=${it.name};"))
        }
        val privateValue = "rpc1|private 192.168.1.1 payload"
        assertEquals("Echo replies=0/0; elapsedMs=0; result=UnknownFailure; " +
            "evidence=UnknownEvidence; phase=Unavailable", log.echo(-1, -1, -1, privateValue, privateValue))
        assertEquals("Echo replies=1/1; elapsedMs=10; result=Complete; evidence=Unavailable; phase=Unavailable",
            log.echo(1, 1, 10, null, null))
        assertFalse(log.lines.value.joinToString().contains(privateValue))
    }

    @Test
    fun pendingFeedbackDistinguishesCheckingFromLiveZeroAndRequiresIndependentIdentityComparison() {
        assertTrue(RpcLabFeedback.pending(null).contains("checking live host state"))
        assertTrue(RpcLabFeedback.pending(0).contains("Pending requests: 0."))
        assertTrue(RpcLabFeedback.pending(0).contains("other device Start client and Pair"))
        assertTrue(RpcLabFeedback.pending(2).contains("Pending requests: 2."))
        assertTrue(RpcLabFeedback.pending(2).contains("full client fingerprint on both devices"))
        assertTrue(RpcLabFeedback.PAIR_STARTED.contains("connecting and negotiating"))
        assertTrue(RpcLabFeedback.PAIR_STARTED.contains("only after the request reaches the host"))
        assertFalse(RpcLabFeedback.PAIR_STARTED.contains("Waiting for approval"))
    }

    @Test
    fun lastSafeFailureSurvivesRingRolloverRefreshStopAndSuccessfulEcho() {
        val log = RpcLabEventLog()
        val failure = log.failure(RpcFailure(RpcFailureKind.DeadlineExceeded, RpcFailurePhase.Negotiation))
        repeat(100) { log.snapshot(false, "Disconnected", 0, 0, 0, null) }
        log.record(RpcLabEventLog.Event.StopRequested)
        log.record(RpcLabEventLog.Event.CleanupCompleted)
        assertEquals(80, log.lines.value.size)
        assertFalse(log.lines.value.any { it.contains("DeadlineExceeded") })
        assertEquals(failure, log.lastFailure.value)
        val failedEcho = log.echo(0, 1, 10, "NotConnected", "NotSent")
        assertEquals(failedEcho, log.lastFailure.value)
        log.echo(1, 1, 10, null, null)
        assertEquals(failedEcho, log.lastFailure.value)
        log.failure(IllegalStateException("rpc1|private pin and payload"))
        assertEquals("LocalOrProtocolFailure", log.lastFailure.value)
    }

    @Test
    fun activityWiresPairFeedbackBeforeSuspensionAndKeepsRefreshErrorsInTheLog() {
        val source = activitySource()
        val pair = source.substringAfter("private fun pair()").substringBefore("private fun copyDiagnostics()")
        assertTrue(pair.contains("Event.PairRequested"))
        assertTrue(pair.contains("status = RpcLabFeedback.PAIR_STARTED"))
        assertTrue(pair.contains("pairAndConnect(trusted)"))
        assertTrue(pair.contains("Event.PairConnected"))
        assertTrue(pair.indexOf("Event.PairRequested") < pair.indexOf("pairAndConnect(trusted)"))
        assertTrue(pair.indexOf("status = RpcLabFeedback.PAIR_STARTED") < pair.indexOf("pairAndConnect(trusted)"))
        assertTrue(pair.indexOf("Event.PairConnected") > pair.indexOf("pairAndConnect(trusted)"))
        assertTrue(source.contains("Button({ pair() }, enabled = !busy)"))
        assertTrue(source.contains("Text(if (hostRole) \"Active role: Host\" else \"Active role: Client\""))
        val refresh = source.substringAfter("private fun refreshStatus()").substringBefore("private fun pair()")
        assertTrue(refresh.contains("liveStatus.refresh()"))
        assertTrue(refresh.contains("eventLog.snapshot(sample.asHost, sample.state"))
        assertTrue(refresh.contains("catch (failure: Exception) { eventLog.failure(failure) }"))
        assertTrue(source.contains("status = eventLog.failure(error)"))
        assertTrue(source.contains("Text(RpcLabFeedback.pending(rows?.size))"))
        assertTrue(source.contains("checkNotNull(lab).approve(request.requestId)"))
        assertTrue(source.contains("Event.ExactClientApproved"))
    }

    @Test
    fun activityCopiesOnlyTheBoundedSanitizedLogOnAnExplicitForegroundAction() {
        val source = activitySource()
        val copy = source.substringAfter("private fun copyDiagnostics()").substringBefore("@Composable")
        assertTrue(copy.contains("if (!foreground) return"))
        assertTrue(copy.contains("eventLog.lines.value.joinToString"))
        assertFalse(copy.contains("invitationClipboard"))
        assertFalse(copy.contains("invitation,"))
        assertFalse(copy.contains("localPin"))
        assertFalse(copy.contains("localAddress"))
        assertFalse(copy.contains("primaryClip"))
        assertTrue(source.contains("Button({ copyDiagnostics() }, enabled = foreground && logLines.isNotEmpty())"))
        assertTrue(source.contains("val lastFailure by eventLog.lastFailure.collectAsState()"))
        assertTrue(source.contains("SelectionContainer { Text(\"Last failure:"))
        assertTrue(copy.contains("eventLog.lastFailure.value"))
        assertTrue(source.contains("Text(\"Copy diagnostics\")"))
        assertFalse(source.contains("android.util.Log"))
        assertFalse(source.contains("printStackTrace"))
    }

    private fun activitySource(): String {
        val root = generateSequence(File(checkNotNull(System.getProperty("user.dir")))) { it.parentFile }
            .first { File(it, "settings.gradle.kts").isFile }
        return File(root, "samples/p2p-sample-android/src/debug/java/" +
            "dev/p2pkit/sample/android/rpclab/RpcLabActivity.kt").readText()
    }
}
