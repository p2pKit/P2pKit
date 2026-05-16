package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.channels.ReceiveChannel
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
    handshakeTimeoutMillis: Long = DEFAULT_HANDSHAKE_TIMEOUT_MS
): HelloPayload {

    val localHello = HelloPayload(
        appId = localAppId.value,
        peerId = localPeerId.value,
        deviceName = localDeviceName,
        platform = localPlatform.name,
        supportedTransports = localTransports.map { it.name },
        protocolVersion = ProtocolConstants.VERSION.toInt()
    )
    protocol.sendHello(connection, localHello)

    val firstEvent = withTimeoutOrNull(handshakeTimeoutMillis) {
        events.receive()
    } ?: run {
        runCatching { protocol.sendError(connection, "handshake timeout") }
        throw P2pError.HandshakeRejected("Handshake timed out after $handshakeTimeoutMillis ms")
    }

    if (firstEvent !is ProtocolEvent.Hello) {
        runCatching { protocol.sendError(connection, "expected HELLO") }
        throw P2pError.HandshakeRejected("Expected HELLO, got $firstEvent")
    }

    val peerHello = firstEvent.payload

    if (peerHello.appId != localAppId.value) {
        runCatching { protocol.sendError(connection, "appId mismatch") }
        throw P2pError.HandshakeRejected(
            "appId mismatch: local=${localAppId.value} remote=${peerHello.appId}"
        )
    }
    if (peerHello.protocolVersion != ProtocolConstants.VERSION.toInt()) {
        runCatching { protocol.sendError(connection, "protocol version mismatch") }
        throw P2pError.VersionMismatch(
            localVersion = ProtocolConstants.VERSION.toInt(),
            remoteVersion = peerHello.protocolVersion
        )
    }
    return peerHello
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
