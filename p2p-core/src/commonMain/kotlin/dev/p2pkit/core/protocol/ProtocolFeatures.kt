package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError

internal object ProtocolFeatures {
    const val APP_MESSAGE_ENVELOPE_V1: String = "app-message-envelope-v1"
    const val FILE_COMMIT_SHA256_V1: String = "file-commit-sha256-v1"

    val SECURE_V2: Set<String> = setOf(APP_MESSAGE_ENVELOPE_V1, FILE_COMMIT_SHA256_V1)
}

/** Mutable only during the authenticated HELLO commit; one instance per connection epoch. */
internal class ProtocolSessionState(
    val localPeerId: String,
    val secure: Boolean,
    localFeatures: Set<String> = if (secure) ProtocolFeatures.SECURE_V2 else emptySet()
) {
    val localFeatures: Set<String> = localFeatures.toSet()

    var remotePeerId: String? = null
        private set
    var negotiatedFeatures: Set<String> = emptySet()
        private set

    private var outboundSequence: Long = 0
    private var inboundSequence: Long = 0
    private val inboundMessageIds: MutableSet<MessageId> = mutableSetOf()
    private val inboundMessageIdOrder: ArrayDeque<MessageId> = ArrayDeque()

    fun completeHello(remotePeerId: String, remoteFeatures: Collection<String>) {
        val negotiated = if (secure) localFeatures.intersect(remoteFeatures.toSet()) else emptySet()
        val existingPeerId = this.remotePeerId
        if (existingPeerId != null) {
            check(existingPeerId == remotePeerId && negotiatedFeatures == negotiated) {
                "Protocol HELLO state conflicts with the committed peer or features"
            }
            return
        }
        this.remotePeerId = remotePeerId
        negotiatedFeatures = negotiated
    }

    fun supports(feature: String): Boolean = feature in negotiatedFeatures

    fun nextOutboundSequence(): Long = outboundSequence.also {
        if (it == Long.MAX_VALUE) throw P2pError.ProtocolError("Application message sequence exhausted")
    }

    fun commitOutboundSequence(sequence: Long) {
        check(sequence == outboundSequence) { "Application message sequence commit is out of order" }
        outboundSequence++
    }

    fun commitInboundEnvelope(sequence: Long, messageId: MessageId) {
        if (sequence != inboundSequence) {
            throw P2pError.ProtocolError(
                "Application message sequence mismatch: expected $inboundSequence, got $sequence"
            )
        }
        if (messageId in inboundMessageIds) {
            throw P2pError.ProtocolError("Application messageId was already received in this session")
        }
        if (inboundSequence == Long.MAX_VALUE) {
            throw P2pError.ProtocolError("Application message sequence exhausted")
        }
        inboundSequence++
        inboundMessageIds += messageId
        inboundMessageIdOrder += messageId
        if (inboundMessageIdOrder.size > MAX_RETAINED_MESSAGE_IDS) {
            inboundMessageIds -= inboundMessageIdOrder.removeFirst()
        }
    }

    companion object {
        private const val MAX_RETAINED_MESSAGE_IDS: Int = 256

        fun legacy(localPeerId: String = "legacy-local"): ProtocolSessionState =
            ProtocolSessionState(localPeerId = localPeerId, secure = false).also {
                it.completeHello(remotePeerId = "legacy-remote", remoteFeatures = emptySet())
            }
    }
}
