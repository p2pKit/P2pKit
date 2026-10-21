package dev.p2pkit.core.internal

import kotlin.test.Test

/** The same deterministic route/cancellation contract against Android-compiled core. */
class SessionRouteCancellationAndroidHostTest {
    @Test
    fun localCancellation() = SessionRouteCancellationTest().locallyCancelledRouteDoesNotReportBufferedCloseFailure()

    @Test
    fun localClosing() = SessionRouteCancellationTest().locallyClosingActiveRouteDoesNotReportBufferedCloseFailure()

    @Test
    fun activeReadFailure() =
        SessionRouteCancellationTest().sameCloseFailureInActiveRouteIsStillReportedAndFailsSession()

    @Test
    fun uncleanRemoteEof() =
        SessionRouteCancellationTest().remoteEofWithoutCloseStillFailsRatherThanBecomingCleanClose()

    @Test
    fun authenticationFailure() =
        SessionRouteCancellationTest().activeAuthenticationFailureRetainsTypedFailureAndDiagnostic()

    @Test
    fun protocolFailure() =
        SessionRouteCancellationTest().activeProtocolFailureRetainsTypedFailureAndDiagnostic()
}
