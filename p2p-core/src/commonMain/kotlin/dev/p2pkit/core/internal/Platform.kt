package dev.p2pkit.core.internal

import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform

/** Epoch-millis clock. Tests inject fakes; production uses the platform clock. */
internal expect fun systemTimeMillis(): Long

/** Identity of the platform the SDK is running on. */
internal expect fun currentPlatform(): Platform

/**
 * Generate a fresh, random [PeerId].
 *
 * v0.1 does not persist this between launches — every process gets a new id.
 * Persistent storage (DataStore on Android, a file on JVM) is planned for v0.2.
 */
@OptIn(kotlin.uuid.ExperimentalUuidApi::class)
internal fun newRandomPeerId(): PeerId = PeerId(kotlin.uuid.Uuid.random().toString())
