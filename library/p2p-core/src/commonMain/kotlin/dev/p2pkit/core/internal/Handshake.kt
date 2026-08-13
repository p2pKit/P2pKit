package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.channels.ReceiveChannel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Performs the HELLO handshake on [connection].
 *
 * Both sides send a HELLO immediately and then wait for the peer's HELLO.
 * If the peer's [HelloPayload.appId] differs from [localAppId], or its
 * [HelloPayload.protocolVersion] is incompatible, the connection is
 * terminated with an ERROR frame and a typed exception is raised.
 *
 * Returns the validated peer hello so callers can construct a [Peer].
 */
internal suspend fun performHandshake(
    protocol: P2pProtocol,
    connection: RawConnection,
    events: ReceiveChannel<ProtocolEvent>,
    localAppId: AppId,
    localPeerId: PeerId,
    localDeviceName: String,
    localPlatform: Platform,
    localTransports: Set<TransportKind>,
    protocolState: dev.p2pkit.core.protocol.ProtocolSessionState? = null,
    protocolVersion: Byte = ProtocolConstants.LEGACY_VERSION,
    handshakeTimeoutMillis: Long = DEFAULT_HANDSHAKE_TIMEOUT_MS,
    logger: P2pLogger = P2pLogger.NoOp
): HelloPayload {

    val localHello = HelloPayload(
        appId = localAppId.value,
        peerId = localPeerId.value,
        deviceName = localDeviceName,
        platform = localPlatform.name,
        supportedTransports = localTransports.map { it.name },
        protocolVersion = protocolVersion.toUByte().toInt(),
        features = protocolState?.localFeatures?.sorted() ?: emptyList()
    )
    protocol.sendHello(connection, localHello)

    val firstEvent = withTimeoutOrNull(handshakeTimeoutMillis) {
        events.receive()
    } ?: run {
        sendErrorBestEffort(protocol, connection, "handshake timeout", logger)
        throw P2pError.HandshakeRejected("Handshake timed out after $handshakeTimeoutMillis ms")
    }

    if (firstEvent !is ProtocolEvent.Hello) {
        sendErrorBestEffort(protocol, connection, "expected HELLO", logger)
        throw P2pError.HandshakeRejected("Expected HELLO, got $firstEvent")
    }

    val peerHello = firstEvent.payload

    if (peerHello.appId != localAppId.value) {
        sendErrorBestEffort(protocol, connection, "appId mismatch", logger)
        throw P2pError.HandshakeRejected(
            "appId mismatch: local=${localAppId.value} remote=${peerHello.appId}"
        )
    }
    if (peerHello.protocolVersion != protocolVersion.toUByte().toInt()) {
        sendErrorBestEffort(protocol, connection, "protocol version mismatch", logger)
        throw P2pError.VersionMismatch(
            localVersion = protocolVersion.toUByte().toInt(),
            remoteVersion = peerHello.protocolVersion
        )
    }
    protocolState?.completeHello(peerHello.peerId, peerHello.features)
    return peerHello
}

/** A rejection diagnostic must never turn owner cancellation into a handshake failure. */
private suspend fun sendErrorBestEffort(
    protocol: P2pProtocol,
    connection: RawConnection,
    reason: String,
    logger: P2pLogger,
) {
    try {
        protocol.sendError(connection, reason)
    } catch (cancelled: CancellationException) {
        currentCoroutineContext().ensureActive()
        logger.debug(
            "Unable to send handshake rejection to peer: " +
                "CancellationException from active protocol callback"
        )
    } catch (_: Exception) {
        // The peer is already being rejected; an ordinary best-effort write
        // failure must not replace the stable local validation error.
    }
}

internal fun HelloPayload.toPeer(): Peer = Peer(
    id = PeerId(peerId),
    name = deviceName,
    platform = parsePlatform(platform),
    supportedTransports = supportedTransports.mapNotNull { runCatching { TransportKind.valueOf(it) }.getOrNull() }.toSet()
)

private fun parsePlatform(name: String): Platform =
    runCatching { Platform.valueOf(name) }.getOrDefault(Platform.UNKNOWN)

internal const val DEFAULT_HANDSHAKE_TIMEOUT_MS: Long = 10_000
