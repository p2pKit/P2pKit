package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs

class RpcMixedCapacityTest {
    private val alphabet = "abcdefghijklmnopqrstuvwxyz234567"
    private fun pin(index: Int) =
        PeerFingerprint.parse("p2f1-${alphabet[index / 32]}${alphabet[index % 32]}" + "a".repeat(50))

    @Test
    fun all255OriginalGeneratorSessionsAndTheAuthenticatedPhoneAreRequired() = runTest {
        val roster = (0..255).associate { pin(it) to it.toLong() }
        val nonce = "1".repeat(64)
        val artifact = "2".repeat(64)
        var live = roster - pin(255)
        val host = MixedCapacityHost(roster.keys, pin(255), pin(0), nonce, artifact)
        suspend fun control(index: Int, action: String) = host.control(pin(index), "$nonce/$action") { live }

        assertIs<RpcReply.ApplicationError<String>>(control(0, "join/$artifact"))
        assertIs<RpcReply.ApplicationError<String>>(control(255, "join/${"3".repeat(64)}"))
        assertEquals(RpcReply.Success("joined"), control(255, "join/$artifact"))
        assertIs<RpcReply.ApplicationError<String>>(control(0, "open"))
        live = roster
        assertIs<RpcReply.ApplicationError<String>>(control(1, "open"))
        assertEquals(RpcReply.Success("open"), control(0, "open"))
        assertIs<RpcReply.ApplicationError<String>>(control(0, "release"))

        live = roster + (pin(255) to 900L)
        assertIs<RpcReply.ApplicationError<String>>(host.probe(pin(255), "$nonce/phone/0") { live })
        live = roster
        assertIs<RpcReply.ApplicationError<String>>(host.probe(pin(255), "$nonce/generator") { live })
        repeat(255) { index ->
            val body = "$nonce/generator"
            assertEquals(RpcReply.Success(body), host.probe(pin(index), body) { live })
        }
        assertIs<RpcReply.ApplicationError<String>>(host.probe(pin(0), "$nonce/generator") { live })
        assertIs<RpcReply.ApplicationError<String>>(control(255, "confirmed"))
        repeat(20) { index ->
            val body = "$nonce/phone/$index"
            assertEquals(RpcReply.Success(body), host.probe(pin(255), body) { live })
        }
        assertIs<RpcReply.ApplicationError<String>>(control(0, "release"))
        assertEquals(RpcReply.Success("confirmed"), control(255, "confirmed"))
        assertEquals(RpcReply.Success("255,20,true"), control(0, "release"))
        assertEquals(RpcReply.Success("released"), control(255, "status"))
        assertIs<RpcReply.ApplicationError<String>>(host.probe(pin(0), "$nonce/generator") { live })
    }

    @Test
    fun theTemporaryDurableApprovalCannotReadOrEraseOrdinaryClientTrust() = runTest {
        val app = RpcCapacityContract.appId
        val purpose = RpcTrustPurpose.SelectedHosts
        class SinglePurposeStore(initial: Set<PeerFingerprint>) : RpcTrustStore {
            private var entries = initial
            override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> {
                check(appId == app && purpose == RpcTrustPurpose.SelectedHosts)
                return entries
            }
            override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
                check(appId == app && purpose == RpcTrustPurpose.SelectedHosts)
                entries = fingerprints.toSet()
            }
        }
        val ordinary = SinglePurposeStore(setOf(pin(3)))
        val isolated = SinglePurposeStore(emptySet())
        val temporary = MixedClientTrust(isolated, pin(2))
        assertFailsWith<IllegalArgumentException> { temporary.load(app, RpcTrustPurpose.HostClients) }
        assertEquals(emptySet(), temporary.load(app, purpose))
        assertFailsWith<IllegalArgumentException> { temporary.replace(app, purpose, setOf(pin(3))) }
        temporary.replace(app, purpose, setOf(pin(2)))
        assertEquals(setOf(pin(2)), temporary.load(app, purpose))
        temporary.retire()
        assertEquals(emptySet(), temporary.load(app, purpose))
        assertEquals(setOf(pin(3)), ordinary.load(app, purpose))
    }
}
