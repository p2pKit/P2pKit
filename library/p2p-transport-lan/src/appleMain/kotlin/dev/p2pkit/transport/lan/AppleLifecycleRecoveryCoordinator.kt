package dev.p2pkit.transport.lan

import platform.Foundation.NSLock

/** UIKit lifecycle signals relevant to native LAN resource recovery. */
internal enum class AppleLifecycleSignal {
    WillResignActive,
    WillEnterForeground,
    DidBecomeActive
}

/**
 * Coalesces UIKit's overlapping foreground/active notifications into one
 * recovery request per inactive episode.
 *
 * `WillEnterForeground` followed by `DidBecomeActive` is the normal
 * background return sequence. Control Center and system-dialog dismissal can
 * instead deliver only `WillResignActive` followed by `DidBecomeActive`.
 * Treating every notification as an independent listener rebind rotates the
 * advertised port twice and leaves peers dialing the first stale port. This
 * coordinator preserves both recovery paths while emitting at most one
 * request for the episode. A successful path-driven rebind while inactive
 * also satisfies that episode, so the later foreground signal cannot rotate
 * the listener again.
 */
internal class AppleLifecycleRecoveryCoordinator {
    private val lock = NSLock()
    private var active: Boolean = true
    private var episode: Long = 0
    private var requestedEpisode: Long = NO_EPISODE
    private var recoveredEpisode: Long = 0

    fun onSignal(signal: AppleLifecycleSignal): Boolean = withLock {
        when (signal) {
            AppleLifecycleSignal.WillResignActive -> {
                if (active) {
                    active = false
                    episode += 1
                    requestedEpisode = NO_EPISODE
                }
                false
            }

            AppleLifecycleSignal.WillEnterForeground -> requestRecoveryLocked()

            AppleLifecycleSignal.DidBecomeActive -> {
                val shouldRecover = requestRecoveryLocked()
                active = true
                shouldRecover
            }
        }
    }

    /** Mark the current lifecycle episode fresh after any successful rebind. */
    fun onSuccessfulRebind() = withLock {
        recoveredEpisode = episode
    }

    private fun requestRecoveryLocked(): Boolean {
        if (recoveredEpisode == episode || requestedEpisode == episode) return false
        requestedEpisode = episode
        return true
    }

    private inline fun <T> withLock(block: () -> T): T {
        lock.lock()
        return try {
            block()
        } finally {
            lock.unlock()
        }
    }

    private companion object {
        const val NO_EPISODE: Long = -1
    }
}
