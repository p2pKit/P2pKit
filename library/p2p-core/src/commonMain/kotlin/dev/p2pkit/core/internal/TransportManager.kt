package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import kotlinx.coroutines.CancellationException

/**
 * Picks the best registered [DataTransport] for a peer.
 *
 * Selection rule: filter to transports whose [DataTransport.canConnect] returns
 * true for the peer, then pick the one with the highest [DataTransport.priority].
 * Throws [P2pError.NoTransportAvailable] if none match. A provider failure
 * while evaluating reachability or selection metadata is contained as
 * [P2pError.ConnectionFailed]; selection fails closed instead of silently
 * falling back to a provider set that could no longer be ranked reliably.
 *
 * LAN is the only shipped transport today, so this is trivial in practice;
 * the abstraction matters once additional transports (BLE / Wi-Fi Direct /
 * Multipeer / Relay) are added.
 */
internal class TransportManager(
    private val transports: List<DataTransport>
) {

    fun selectBestTransport(peer: InternalPeer): DataTransport {
        var best: Candidate? = null
        transports.forEachIndexed { index, transport ->
            val candidate = try {
                if (!transport.canConnect(peer)) return@forEachIndexed
                Candidate(
                    transport = transport,
                    priority = transport.priority,
                    typeOrdinal = transport.type.ordinal,
                    registrationIndex = index
                )
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Throwable) {
                throw selectionFailure(index, failure)
            }

            val current = best
            if (current == null || candidate.precedes(current)) {
                best = candidate
            }
        }
        return best?.transport ?: throw P2pError.NoTransportAvailable(peer.publicPeer)
    }

    private fun selectionFailure(index: Int, failure: Throwable): P2pError.ConnectionFailed =
        P2pError.ConnectionFailed(
            "Transport selection failed for registration #$index: " +
                (failure.message ?: failure::class.simpleName ?: "provider failure")
        ).also { it.underlying = failure }

    private data class Candidate(
        val transport: DataTransport,
        val priority: Int,
        val typeOrdinal: Int,
        val registrationIndex: Int
    ) {
        fun precedes(other: Candidate): Boolean = when {
            priority != other.priority -> priority > other.priority
            typeOrdinal != other.typeOrdinal -> typeOrdinal < other.typeOrdinal
            else -> registrationIndex < other.registrationIndex
        }
    }
}
