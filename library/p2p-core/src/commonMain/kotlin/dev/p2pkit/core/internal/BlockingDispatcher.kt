package dev.p2pkit.core.internal

import kotlinx.coroutines.CoroutineDispatcher

/** Platform dispatcher intended for independently bounded application resource work. */
internal expect fun blockingIoDispatcher(): CoroutineDispatcher

/** Platform dispatcher for SDK/native lifecycle cleanup. */
internal expect fun blockingCleanupDispatcher(): CoroutineDispatcher

/** Platform dispatcher isolated for caller-supplied close/abort callbacks. */
internal expect fun blockingApplicationCleanupDispatcher(): CoroutineDispatcher

/** Platform dispatcher isolated from cleanup for caller-owned file reads. */
internal expect fun blockingFileReadDispatcher(): CoroutineDispatcher

/** Platform dispatcher isolated from application callbacks for protocol control writes. */
internal expect fun blockingProtocolDispatcher(): CoroutineDispatcher
