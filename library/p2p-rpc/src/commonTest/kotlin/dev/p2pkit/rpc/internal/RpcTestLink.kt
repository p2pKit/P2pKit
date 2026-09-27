package dev.p2pkit.rpc.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.SessionConnectionInfo
import dev.p2pkit.rpc.RpcFailureKind
import kotlinx.coroutines.flow.MutableStateFlow

// Test-only identity/channel seams. Production factories never expose these or accept arbitrary kits.
internal class RpcTestLink(index: Int = 0, override val admission: PeerAdmission = PeerAdmission.Trusted) : RpcLink {
    override val identity = PeerIdentity(PeerId("rpc-test-$index"), testFingerprint(index))
    override val transportState = MutableStateFlow(ConnectionState.Connected)
    override val generation = MutableStateFlow(SessionConnectionInfo(1))
    override val failure = MutableStateFlow<RpcFailureKind?>(null)
    val sent = mutableListOf<WireMessage>()
    val queued = mutableListOf<SendTicket>()
    var paused = false
    var closeFailure: Exception? = null
    var onSend: suspend (WireMessage) -> Unit = {}

    override suspend fun offer(
        message: WireMessage, expiresAt: Long, notification: Boolean, onStart: () -> Unit,
    ): SendTicket? {
        if (transportState.value != ConnectionState.Connected) return null
        val ticket = SendTicket(
            message.retained(), expiresAt, generation.value.generation, notification, onStart = onStart,
        )
        if (paused) queued += ticket else deliver(ticket)
        return ticket
    }

    suspend fun deliver(ticket: SendTicket) {
        if (!ticket.begin()) return
        try {
            sent += ticket.message.retained()
            onSend(ticket.message)
        } finally { ticket.finish(true) }
    }

    fun clearSent() { sent.forEach { it.release() }; sent.clear() }
    override suspend fun close() {
        transportState.value = ConnectionState.Closed
        queued.forEach { it.cancelQueued() }
        queued.clear()
        closeFailure?.let { throw it }
    }
}

internal fun testFingerprint(index: Int = 0): PeerFingerprint =
    PeerFingerprint("p2f1-" + ('a'.code + index).toChar().toString().repeat(51) + "a")

internal const val TEST_INCARNATION: String = "11111111111111111111111111111111"
internal const val TEST_REQUEST: String = "22222222222222222222222222222222"
internal const val TEST_SECOND: String = "33333333333333333333333333333333"
internal fun testBody(text: String, budget: PayloadBudget): OwnedBytes =
    OwnedBytes.copy(text.encodeToByteArray(), budget)

internal suspend fun RpcHostEngine.negotiate(link: RpcTestLink) {
    attach(link)
    onMessage(link, WireMessage(WireKind.Hello, TEST_REQUEST))
    link.clearSent()
}

internal suspend fun RpcHostEngine.deliver(link: RpcTestLink, message: WireMessage) {
    try { onMessage(link, message) } finally { message.release() }
}
