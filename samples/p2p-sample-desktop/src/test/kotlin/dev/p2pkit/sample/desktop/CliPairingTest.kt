package dev.p2pkit.sample.desktop

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.dsl.jvmSecureIdentityStore
import dev.p2pkit.provisioning.desktop.jvm
import dev.p2pkit.sample.diagnostics.LocalPairingInfo
import dev.p2pkit.transport.lan.lan
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class CliPairingTest {
    @Test
    fun explicitDisplayContainsTheWholeAppBoundQrWithoutObjectLogDisclosure() = runBlocking {
        val kit = createKit()
        try {
            val info = assertNotNull(LocalPairingInfo.from(kit))
            val lines = mutableListOf<String>()
            printPairingInfo(kit, lines::add)
            assertTrue(lines.contains("fingerprint      ${info.fingerprint}"))
            assertTrue(lines.contains("pairing QR       ${info.qr}"))
            assertEquals(kit.localFingerprint, kit.parsePeerPairingQr(info.qr))
            assertFalse(info.toString().contains(info.fingerprint))
            assertFalse(info.toString().contains(info.qr))
        } finally {
            kit.stop()
        }
    }

    @Test
    fun parserRequiresOneSelectorAndACompleteQrForTheExactAppId() = runBlocking {
        val kit = createKit()
        val otherApp = createKit(appId = "synthetic.pairing.other-app")
        try {
            val qr = assertNotNull(kit.localPairingQr)
            val request = assertNotNull(parsePinnedConnect(kit, "  anon-selector  $qr  "))
            assertEquals("anon-selector", request.selector)
            assertEquals(kit.localFingerprint, request.fingerprint)
            for (input in listOf(
                "", "anon-selector", "anon-selector ${kit.localFingerprint?.value}",
                "anon-selector ${qr.dropLast(1)}", "anon-selector $qr extra",
                "anon-selector ${otherApp.localPairingQr}", "anon-selector p2pkit:v1:legacy"
            )) {
                assertNull(parsePinnedConnect(kit, input))
            }
        } finally {
            try {
                otherApp.stop()
            } finally {
                kit.stop()
            }
        }
    }

    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun commandPinsRealTcpAndRechecksAnExistingSessionInsteadOfBypassingThePin() = runBlocking {
        val caller = createKit()
        val rejected = CompletableDeferred<Throwable>()
        val receiver = createKit(
            authorization = PeerAuthorizationPolicy.PinnedOnly(setOf(assertNotNull(caller.localFingerprint))),
            logger = object : P2pLogger by P2pLogger.NoOp {
                override fun warn(message: String, throwable: Throwable?) {
                    if (throwable is P2pError.AuthorizationRejected) rejected.complete(throwable)
                }
            }
        )
        val otherIdentity = createKit()
        try {
            val subscribed = CompletableDeferred<Unit>()
            val incoming = async {
                withTimeout(10_000) {
                    receiver.incomingSessions.onSubscription { subscribed.complete(Unit) }.first()
                }
            }
            receiver.start() // Real TCP, not multicast or a simulated security engine.
            subscribed.await()
            val info = assertNotNull(receiver.networkProvisioning.getManualConnectionInfo())
            val peer = caller.networkProvisioning.createManualPeer(
                "127.0.0.1", info.port, assertNotNull(receiver.localFingerprint)
            )
            val request = assertNotNull(parsePinnedConnect(caller, "receiver ${receiver.localPairingQr}"))
            val session = withTimeout(10_000) { connectPinnedPeer(caller, peer, request) }
            assertEquals(receiver.localFingerprint, session.peerIdentity.fingerprint)
            assertEquals(caller.localFingerprint, incoming.await().peerIdentity.fingerprint)
            assertSame(session, connectPinnedPeer(caller, peer, request))

            val wrong = assertNotNull(parsePinnedConnect(caller, "receiver ${otherIdentity.localPairingQr}"))
            assertFailsWith<P2pError.AuthenticatedIdentityMismatch> { connectPinnedPeer(caller, peer, wrong) }
            assertEquals(listOf(session), caller.sessions.value)

            // Knowing the responder's QR does not authorize a third key to enter its allowlist.
            val thirdPeer = otherIdentity.networkProvisioning.createManualPeer(
                "127.0.0.1", info.port, assertNotNull(receiver.localFingerprint)
            )
            val thirdRequest = assertNotNull(
                parsePinnedConnect(otherIdentity, "receiver ${receiver.localPairingQr}")
            )
            assertFailsWith<P2pError> {
                withTimeout(10_000) { connectPinnedPeer(otherIdentity, thirdPeer, thirdRequest) }
            }
            assertIs<P2pError.AuthorizationRejected>(withTimeout(10_000) { rejected.await() })
            assertTrue(otherIdentity.sessions.value.isEmpty())
            assertEquals(1, receiver.sessions.value.size)
        } finally {
            try {
                otherIdentity.stop()
            } finally {
                try {
                    caller.stop()
                } finally {
                    receiver.stop()
                }
            }
        }
    }

    private fun createKit(
        appId: String = "synthetic.pairing.cli",
        authorization: PeerAuthorizationPolicy = PeerAuthorizationPolicy.RejectUnknown,
        logger: P2pLogger = P2pLogger.NoOp
    ): P2pKit = P2pKit.create {
        this.appId = AppId(appId)
        deviceName = "Synthetic pairing fixture"
        jvmSecureIdentityStore(DevelopmentOnlyInMemorySecureIdentityStore())
        security { mode = SecurityMode.AuthenticatedV2(authorization) }
        transports { lan() }
        networkProvisioning { jvm() }
        this.logger = logger
    }
}
