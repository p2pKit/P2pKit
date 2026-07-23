package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlin.random.Random

/**
 * Default [P2pProtocol] implementation that wires together the building
 * blocks from Step 3: [Chunker] for outbound, [FrameReader] +
 * [Reassembler] for inbound, [FrameCodec] for the wire byte format.
 */
internal class DefaultP2pProtocol(
    private val chunker: Chunker = Chunker(),
    private val clock: () -> Long,
    private val random: Random = Random.Default,
    private val logger: P2pLogger = P2pLogger.NoOp,
    private val version: Byte = ProtocolConstants.LEGACY_VERSION
) : P2pProtocol {

    override suspend fun sendMessage(
        connection: RawConnection,
        message: P2pMessage,
        sessionState: ProtocolSessionState
    ) {
        var envelopeSequence: Long? = null
        val frames = if (sessionState.supports(ProtocolFeatures.APP_MESSAGE_ENVELOPE_V1)) {
            val remotePeerId = sessionState.remotePeerId
                ?: throw P2pError.ProtocolError("Cannot send application envelope before HELLO completes")
            val messageId = MessageId.random(random)
            val sequence = sessionState.nextOutboundSequence()
            val envelope = AppMessageEnvelope.encode(
                message = message,
                messageId = messageId,
                sequence = sequence,
                senderPeerId = sessionState.localPeerId,
                recipientPeerId = remotePeerId
            )
            envelopeSequence = sequence
            chunker.chunkEnvelope(envelope, messageId)
        } else {
            val hasMetadata = when (message) {
                is P2pMessage.Text -> message.metadata.isNotEmpty()
                is P2pMessage.Binary -> message.metadata.isNotEmpty()
            }
            if (hasMetadata && sessionState.secure) {
                throw P2pError.UnsupportedFeature(ProtocolFeatures.APP_MESSAGE_ENVELOPE_V1)
            }
            chunker.chunk(message)
        }
        for (frame in frames) {
            writeFrame(connection, frame)
        }
        envelopeSequence?.let(sessionState::commitOutboundSequence)
    }

    override suspend fun sendHello(connection: RawConnection, hello: HelloPayload) {
        writeFrame(connection, controlFrame(PacketType.HELLO, HelloPayload.encode(hello)))
    }

    override suspend fun sendPing(connection: RawConnection) {
        writeFrame(connection, controlFrame(PacketType.PING))
    }

    override suspend fun sendPong(connection: RawConnection) {
        writeFrame(connection, controlFrame(PacketType.PONG))
    }

    override suspend fun sendClose(connection: RawConnection) {
        writeFrame(connection, controlFrame(PacketType.CLOSE))
    }

    override suspend fun sendError(connection: RawConnection, reason: String) {
        writeFrame(connection, controlFrame(PacketType.ERROR, encodeReason(reason, "ERROR reason")))
    }

    override suspend fun sendFileOffer(
        connection: RawConnection,
        transferId: MessageId,
        offer: FileOfferPayload
    ) {
        writeFrame(
            connection,
            controlFrame(
                type = PacketType.FILE_OFFER,
                messageId = transferId,
                payload = FileOfferPayload.encode(offer)
            )
        )
    }

    override suspend fun sendSecureFileOffer(connection: RawConnection, offer: SecureFileOffer) {
        writeFrame(
            connection,
            controlFrame(PacketType.FILE_OFFER, offer.encode(), offer.transferId)
        )
    }

    override suspend fun sendFileAccept(connection: RawConnection, transferId: MessageId) {
        writeFrame(connection, controlFrame(PacketType.FILE_ACCEPT, messageId = transferId))
    }

    override suspend fun sendSecureFileAccept(connection: RawConnection, transferId: MessageId) {
        writeFrame(
            connection,
            controlFrame(PacketType.FILE_ACCEPT, SecureFileAccept.encode(transferId), transferId)
        )
    }

    override suspend fun sendFileReject(
        connection: RawConnection,
        transferId: MessageId,
        reason: String?
    ) {
        val payload = reason?.let { encodeReason(it, "FILE_REJECT reason") } ?: EMPTY
        writeFrame(connection, controlFrame(PacketType.FILE_REJECT, messageId = transferId, payload = payload))
    }

    override suspend fun sendFileDataFrame(connection: RawConnection, frame: Frame) {
        require(frame.type == PacketType.FILE_DATA) {
            "sendFileDataFrame expects FILE_DATA, got ${frame.type}"
        }
        writeFrame(connection, frame)
    }

    override suspend fun sendFileDone(connection: RawConnection, transferId: MessageId) {
        writeFrame(connection, controlFrame(PacketType.FILE_DONE, messageId = transferId))
    }

    override suspend fun sendFileFinish(connection: RawConnection, finish: SecureFileFinish) {
        writeFrame(connection, controlFrame(PacketType.FILE_FINISH, finish.encode(), finish.transferId))
    }

    override suspend fun sendFileCommit(connection: RawConnection, commit: SecureFileCommit) {
        writeFrame(connection, controlFrame(PacketType.FILE_COMMIT, commit.encode(), commit.transferId))
    }

    override suspend fun sendFileResult(connection: RawConnection, result: SecureFileResult) {
        writeFrame(connection, controlFrame(PacketType.FILE_RESULT, result.encode(), result.transferId))
    }

    override suspend fun sendFileCancel(
        connection: RawConnection,
        transferId: MessageId,
        reason: String?
    ) {
        val payload = reason?.let { encodeReason(it, "FILE_CANCEL reason") } ?: EMPTY
        writeFrame(connection, controlFrame(PacketType.FILE_CANCEL, messageId = transferId, payload = payload))
    }

    /**
     * Single outbound choke point: trace the frame (type + size) then write its
     * encoded bytes. Every send method routes through here so [FrameTrace] sees
     * exactly one TX line per frame, matching the RX line in [events].
     */
    private suspend fun writeFrame(connection: RawConnection, frame: Frame) {
        val versioned = frame.withVersion(version)
        FrameTrace.emit { "TX ${frameDesc(versioned)}" }
        connection.write(FrameCodec.encode(versioned))
    }

    private fun frameDesc(frame: Frame): String {
        val base = "type=${frame.type} len=${frame.payload.size}B"
        return when (frame.type) {
            PacketType.DATA, PacketType.FILE_DATA ->
                "$base chunk=${frame.chunkIndex}/${frame.totalChunks} " +
                    "id=${frame.messageId.toString().take(8)}" +
                    (if (frame.isLastChunk) " LAST" else "")
            PacketType.FILE_OFFER, PacketType.FILE_ACCEPT, PacketType.FILE_REJECT,
            PacketType.FILE_DONE, PacketType.FILE_CANCEL, PacketType.FILE_FINISH,
            PacketType.FILE_COMMIT, PacketType.FILE_RESULT ->
                "$base xfer=${frame.messageId.toString().take(8)}"
            else -> base
        }
    }

    override fun events(
        connection: RawConnection,
        sessionState: ProtocolSessionState
    ): Flow<ProtocolEvent> = flow {
        val reader = FrameReader(logger, expectedVersion = version)
        val reassembler = Reassembler(clock = clock, sessionState = sessionState)
        val warnings = PeerWarningLimiter(logger)
        connection.read().collect { bytes ->
            // Reclaim partial multi-chunk messages that went idle: eviction is
            // by inactivity (no new chunk within the reassembly timeout), not
            // by age since the first chunk, so a slow-but-live transfer is
            // never dropped mid-message (AUDIT-2026-06 fix). evictStale() is
            // otherwise never driven (it has no timer), so without this call a
            // stalled transfer would pin its chunks for the life of the
            // connection. Cheap: no-op while `pending` is empty.
            reassembler.evictStale()
            val frames = reader.feed(bytes)
            for (frame in frames) {
                FrameTrace.emit { "RX ${frameDesc(frame)}" }
                val event = decodeEvent(frame, reassembler, warnings, sessionState)
                if (event != null) emit(event)
            }
        }
    }

    private fun decodeEvent(
        frame: Frame,
        reassembler: Reassembler,
        warnings: PeerWarningLimiter,
        sessionState: ProtocolSessionState
    ): ProtocolEvent? {
        if (sessionState.secure && frame.type.isFileTransfer() &&
            !sessionState.supports(ProtocolFeatures.FILE_COMMIT_SHA256_V1)
        ) {
            throw P2pError.ProtocolError(
                "Secure file transfer frame received without negotiated ${ProtocolFeatures.FILE_COMMIT_SHA256_V1}"
            )
        }
        return when (frame.type) {
            PacketType.DATA -> {
                if (sessionState.supports(ProtocolFeatures.APP_MESSAGE_ENVELOPE_V1) && !frame.isEnvelope) {
                    throw P2pError.ProtocolError(
                        "Negotiated application messages must use the authenticated envelope"
                    )
                }
                val message = reassembler.accept(frame) ?: return null
                ProtocolEvent.Message(message)
            }
            PacketType.HELLO -> {
                // A malformed HELLO body must not throw a SerializationException
                // out of the events flow (which would tear the session down as
                // an unhandled error). Skip + warn, mirroring the unknown-packet
                // policy; during the handshake a missing HELLO simply times out
                // and surfaces as a clean HandshakeRejected.
                val payload = try {
                    HelloPayload.decode(frame.payload)
                } catch (failure: Exception) {
                    if (failure is CancellationException) throw failure
                    warnings.warn(
                        key = "HELLO",
                        message = "Skipping malformed HELLO frame: ${failure.safeDiagnosticDetail()}"
                    )
                    return null
                }
                if (sessionState.secure && sessionState.remotePeerId == null) {
                    sessionState.completeHello(payload.peerId, payload.features)
                }
                ProtocolEvent.Hello(payload)
            }
            PacketType.PING -> ProtocolEvent.Ping
            PacketType.PONG -> ProtocolEvent.Pong
            PacketType.CLOSE -> ProtocolEvent.Close
            PacketType.ERROR -> {
                val reason = frame.payload.decodeReason("ERROR reason")
                ProtocolEvent.PeerError(reason)
            }
            PacketType.ACK -> ProtocolEvent.Ack(frame.messageId, frame.chunkIndex)
            PacketType.FILE_OFFER -> {
                // Skip + warn on a malformed offer body instead of letting the
                // SerializationException escape into routeEvents. A hostile peer
                // could otherwise resend a bad FILE_OFFER after every reconnect
                // to drive a reconnect loop.
                val (payload, secureOffer) = try {
                    if (sessionState.supports(ProtocolFeatures.FILE_COMMIT_SHA256_V1)) {
                        val secure = SecureFileOffer.decode(frame.messageId, frame.payload)
                        FileOfferPayload(secure.name, secure.sizeBytes, secure.mimeType) to secure
                    } else {
                        FileOfferPayload.decode(frame.payload) to null
                    }
                } catch (failure: Exception) {
                    if (failure is CancellationException) throw failure
                    if (sessionState.supports(ProtocolFeatures.FILE_COMMIT_SHA256_V1)) {
                        throw if (failure is P2pError.ProtocolError) {
                            failure
                        } else {
                            P2pError.ProtocolError(
                                "Malformed authenticated FILE_OFFER: ${failure.safeDiagnosticDetail()}"
                            )
                        }
                    }
                    warnings.warn(
                        key = "FILE_OFFER",
                        message = "Skipping malformed FILE_OFFER frame: ${failure.safeDiagnosticDetail()}"
                    )
                    return null
                }
                ProtocolEvent.FileOffer(frame.messageId, payload, secureOffer)
            }
            PacketType.FILE_ACCEPT -> {
                if (sessionState.supports(ProtocolFeatures.FILE_COMMIT_SHA256_V1)) {
                    SecureFileAccept.decode(frame.messageId, frame.payload)
                } else if (frame.payload.isNotEmpty()) {
                    throw P2pError.ProtocolError("Secure FILE_ACCEPT was not negotiated")
                }
                ProtocolEvent.FileAccept(frame.messageId)
            }
            PacketType.FILE_REJECT -> {
                val reason = if (frame.payload.isEmpty()) null else frame.payload.decodeReason("FILE_REJECT reason")
                ProtocolEvent.FileReject(frame.messageId, reason)
            }
            PacketType.FILE_DATA -> ProtocolEvent.FileData(frame)
            PacketType.FILE_DONE -> ProtocolEvent.FileDone(frame.messageId)
            PacketType.FILE_FINISH -> {
                requireFileCommitFeature(sessionState)
                ProtocolEvent.FileFinish(SecureFileFinish.decode(frame.messageId, frame.payload))
            }
            PacketType.FILE_COMMIT -> {
                requireFileCommitFeature(sessionState)
                ProtocolEvent.FileCommit(SecureFileCommit.decode(frame.messageId, frame.payload))
            }
            PacketType.FILE_RESULT -> {
                requireFileCommitFeature(sessionState)
                ProtocolEvent.FileResult(SecureFileResult.decode(frame.messageId, frame.payload))
            }
            PacketType.FILE_CANCEL -> {
                val reason = if (frame.payload.isEmpty()) null else frame.payload.decodeReason("FILE_CANCEL reason")
                ProtocolEvent.FileCancel(frame.messageId, reason)
            }
        }
    }

    private fun requireFileCommitFeature(sessionState: ProtocolSessionState) {
        if (!sessionState.secure || !sessionState.supports(ProtocolFeatures.FILE_COMMIT_SHA256_V1)) {
            throw P2pError.ProtocolError("Authenticated file commit feature was not negotiated")
        }
    }

    private fun PacketType.isFileTransfer(): Boolean = when (this) {
        PacketType.FILE_OFFER, PacketType.FILE_ACCEPT, PacketType.FILE_REJECT,
        PacketType.FILE_DATA, PacketType.FILE_DONE, PacketType.FILE_CANCEL,
        PacketType.FILE_FINISH, PacketType.FILE_COMMIT, PacketType.FILE_RESULT -> true
        else -> false
    }

    private fun controlFrame(
        type: PacketType,
        payload: ByteArray = EMPTY,
        messageId: MessageId = MessageId.random(random)
    ): Frame = Frame(
        type = type,
        flags = FrameFlags.LAST_CHUNK.toByte(),
        messageId = messageId,
        chunkIndex = 0,
        totalChunks = 1,
        payload = payload
    )

    private companion object {
        val EMPTY = ByteArray(0)
    }
}

private fun encodeReason(value: String, field: String): ByteArray {
    validateWireText(
        value = value,
        field = field,
        maxChars = ProtocolConstants.MAX_REASON_PAYLOAD_BYTES,
        maxUtf8Bytes = ProtocolConstants.MAX_REASON_PAYLOAD_BYTES,
        requireNonBlank = true
    )
    return value.encodeToByteArray()
}

private fun ByteArray.decodeReason(field: String): String {
    if (size > ProtocolConstants.MAX_REASON_PAYLOAD_BYTES) {
        throw P2pError.ProtocolError(
            "$field exceeds ${ProtocolConstants.MAX_REASON_PAYLOAD_BYTES} bytes"
        )
    }
    return try {
        decodeStrictUtf8(field).also {
            validateWireText(
                value = it,
                field = field,
                maxChars = ProtocolConstants.MAX_REASON_PAYLOAD_BYTES,
                maxUtf8Bytes = ProtocolConstants.MAX_REASON_PAYLOAD_BYTES,
                requireNonBlank = true
            )
        }
    } catch (failure: IllegalArgumentException) {
        throw P2pError.ProtocolError(failure.message ?: "$field is invalid")
    }
}

/** Fixed-category limiter: attacker-controlled invalid bodies can produce at most five logs/category. */
private class PeerWarningLimiter(private val logger: P2pLogger) {
    private val counts: MutableMap<String, Int> = mutableMapOf()

    fun warn(key: String, message: String) {
        val count = (counts[key] ?: 0) + 1
        counts[key] = count
        val emitted = when {
            count <= WARNING_BURST -> message
            count == WARNING_BURST + 1 -> "Further malformed $key warnings suppressed for this connection"
            else -> return
        }
        try {
            logger.warn(emitted)
        } catch (failure: Exception) {
            if (failure is CancellationException) throw failure
            // A diagnostic sink does not own protocol or connection failure.
        }
    }

    private companion object {
        const val WARNING_BURST: Int = 4
    }
}
