package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerId

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
 * Selects the default [PeerIdStorage] for the current platform.
 *
 * - JVM: file under `~/.p2pkit/<sanitized-appId>/peer-id`.
 * - Android (after `P2pKitAndroid.initialize(context)`): file under
 *   `<filesDir>/p2pkit/<sanitized-appId>/peer-id`.
 * - Android (without init): an [InMemoryPeerIdStorage] fallback plus a
 *   `logger.warn` so the behaviour is loud.
 */
internal expect fun defaultPeerIdStorage(appId: AppId, logger: P2pLogger): PeerIdStorage
