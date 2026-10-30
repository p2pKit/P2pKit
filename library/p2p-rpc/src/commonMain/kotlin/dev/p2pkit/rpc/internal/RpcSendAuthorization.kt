package dev.p2pkit.rpc.internal

import dev.p2pkit.rpc.RpcApplicationSession

/** Original authority survives queueing; revocation and ticket-start share the session's short gate. */
internal class RpcSendAuthorization(
    private val session: RpcApplicationSession,
    private val stillAllowed: () -> Boolean = { true },
    private val authorize: suspend () -> Boolean,
) {
    // Bounded authority/context retained by a queued ticket, charged separately from its payload.
    val allowanceBytes: Long = 2_048

    suspend fun begin(ticket: SendTicket, transportReady: () -> Boolean): Boolean {
        if (!transportReady() || !session.isActive || !stillAllowed() || !authorize()) return false
        return session.commit { stillAllowed() && transportReady() && ticket.begin() }
    }
}
