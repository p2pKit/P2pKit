package dev.p2pkit.core.internal

/**
 * Briefly parks a competing synchronous publisher, not the permit owner.
 * Preserve thread interruption and leave coroutine cancellation untouched.
 * This must not pump an event loop, invoke callbacks or create a worker.
 */
internal expect fun pausePeerPublication()

internal const val PEER_PUBLICATION_PAUSE_NANOS: Long = 1_000_000L
