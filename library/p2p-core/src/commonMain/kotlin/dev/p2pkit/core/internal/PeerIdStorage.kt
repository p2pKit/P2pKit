package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.decodeStrictUtf8
import dev.p2pkit.core.protocol.validateWireText

/**
 * Persists the local device's [PeerId] across process restarts so that other
 * peers recognise the same device after a relaunch.
 *
 * Internal. Apps don't construct or configure this directly — the default
 * platform implementation is selected by [defaultPeerIdStorage]. Tests and
 * advanced internal code can override via [dev.p2pkit.core.dsl.P2pKitBuilder.peerIdStorage].
 */
internal interface PeerIdStorage {

    /**
     * Return the persisted [PeerId] for this storage instance, generating and
     * saving a fresh one on first call. Implementations must return a stable
     * id on repeated calls for the same storage backing.
     */
    fun loadOrGenerate(): PeerId
}

/**
 * Bound the legacy persistence record independently from the tighter HELLO
 * field contract. The small allowance preserves existing whitespace-trimmed
 * records without permitting a corrupted file/defaults value to drive an
 * unbounded read or normalization allocation.
 */
internal const val MAX_PERSISTED_PEER_ID_BYTES: Int = 4_096

/** Decode one already-bounded persistence record without UTF-8 replacement. */
internal fun decodePersistedPeerId(bytes: ByteArray): PeerId {
    require(bytes.size <= MAX_PERSISTED_PEER_ID_BYTES) {
        "persistent PeerId exceeds $MAX_PERSISTED_PEER_ID_BYTES bytes"
    }
    return parsePersistedPeerId(bytes.decodeStrictUtf8("persistent PeerId"))
}

/** Parse the legacy whitespace-tolerant record, then enforce the wire contract. */
internal fun parsePersistedPeerId(raw: String): PeerId {
    require(raw.length <= MAX_PERSISTED_PEER_ID_BYTES) {
        "persistent PeerId exceeds $MAX_PERSISTED_PEER_ID_BYTES characters"
    }
    return validateLocalPeerId(PeerId(raw.trim()))
}

/** Validate any default or injected local identity before transport construction. */
internal fun validateLocalPeerId(peerId: PeerId): PeerId {
    validateWireText(
        peerId.value,
        "local PeerId",
        HelloPayload.MAX_FIELD_LEN,
        HelloPayload.MAX_FIELD_UTF8_BYTES,
        requireNonBlank = true
    )
    return peerId
}

/**
 * Selects the default [PeerIdStorage] for the current platform.
 *
 * - JVM: file under `~/.p2pkit/peer-id-v2/<full-appId-hash>/peer-id`.
 * - Android (after `P2pKitAndroid.initialize(context)`): file under
 *   `<filesDir>/p2pkit/peer-id-v2/<full-appId-hash>/peer-id`.
 * - iOS: a full-AppId-hash entry in a collision-safe NSUserDefaults bucket.
 * - Android (without init): an [InMemoryPeerIdStorage] fallback plus a
 *   `logger.warn` so the behaviour is loud.
 */
internal expect fun defaultPeerIdStorage(appId: AppId, logger: P2pLogger): PeerIdStorage
