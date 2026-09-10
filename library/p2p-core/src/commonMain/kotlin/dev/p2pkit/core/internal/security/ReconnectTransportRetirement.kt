package dev.p2pkit.core.internal.security

/**
 * Stops the underlying transport without discarding buffered authenticated input.
 * The session must let its existing reader/router finish classification before
 * retrying. This is not full secure-stream disposal or remote EOF acknowledgement.
 */
internal interface ReconnectTransportRetirement {
    suspend fun retireTransportForReconnect()
}
