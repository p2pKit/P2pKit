package dev.p2pkit.transport.lan

import kotlin.concurrent.Volatile
import platform.Foundation.NSLock

/** One native `nw_path_monitor_t` callback generation. */
internal class ApplePathMonitorOwner internal constructor(
    internal val generation: Long
) {
    @Volatile
    private var active: Boolean = true

    fun isActive(): Boolean = active

    internal fun retire() {
        active = false
    }
}

/** Values derived from one admitted path callback. */
internal data class ApplePathMonitorUpdate(
    val isFirstSatisfied: Boolean,
    val becameSatisfied: Boolean,
    val previousInterfaceFingerprint: Int,
    val interfaceChanged: Boolean,
    val previousAddressFingerprint: ULong,
    val addressChanged: Boolean
) {
    val needsRebind: Boolean
        get() = applePathNeedsRebind(
            becameSatisfied = becameSatisfied,
            isFirstEver = isFirstSatisfied,
            interfaceChanged = interfaceChanged,
            addressChanged = addressChanged
        )
}

/**
 * Serializes ownership and fingerprints for restartable Apple path monitors.
 *
 * `nw_path_monitor_cancel` does not drain an update already queued on the
 * dispatch queue. [detach] retires the owner under the same lock used by
 * [publish], then resets all fingerprints. A delayed callback from that
 * monitor is therefore rejected before it can write over the next monitor's
 * state. Callers must carry [ApplePathMonitorOwner.isActive] into any delayed
 * work scheduled from an admitted update.
 */
internal class ApplePathMonitorCallbackState {
    private val lock = NSLock()
    private var nextGeneration: Long = 0
    private var activeOwner: ApplePathMonitorOwner? = null
    private var lastWasSatisfied: Boolean = false
    private var hasEverObservedSatisfied: Boolean = false
    private var lastInterfaceFingerprint: Int = NO_INTERFACE_FINGERPRINT
    private var lastAddressFingerprint: ULong = NO_ADDRESS_FINGERPRINT

    fun begin(): ApplePathMonitorOwner = withLock {
        check(activeOwner == null) { "an Apple path-monitor generation is already active" }
        resetObservationsLocked()
        ApplePathMonitorOwner(++nextGeneration).also { activeOwner = it }
    }

    fun detach(owner: ApplePathMonitorOwner): Boolean = withLock {
        if (activeOwner !== owner) return@withLock false
        owner.retire()
        activeOwner = null
        resetObservationsLocked()
        true
    }

    fun publish(
        owner: ApplePathMonitorOwner,
        isSatisfied: Boolean,
        interfaceFingerprint: Int,
        addressFingerprint: ULong
    ): ApplePathMonitorUpdate? = withLock {
        if (activeOwner !== owner || !owner.isActive()) return@withLock null

        val previousWasSatisfied = lastWasSatisfied
        val isFirstSatisfied = !hasEverObservedSatisfied
        lastWasSatisfied = isSatisfied
        if (isSatisfied) hasEverObservedSatisfied = true
        val becameSatisfied = isSatisfied && !previousWasSatisfied

        val previousInterfaceFingerprint = lastInterfaceFingerprint
        val isFirstInterfaceFingerprint =
            previousInterfaceFingerprint == NO_INTERFACE_FINGERPRINT
        if (isSatisfied) lastInterfaceFingerprint = interfaceFingerprint
        val interfaceChanged = isSatisfied &&
            !isFirstInterfaceFingerprint &&
            previousInterfaceFingerprint != interfaceFingerprint

        val previousAddressFingerprint = lastAddressFingerprint
        val isFirstAddressFingerprint = previousAddressFingerprint == NO_ADDRESS_FINGERPRINT
        if (isSatisfied) lastAddressFingerprint = addressFingerprint
        val addressChanged = isSatisfied &&
            !isFirstAddressFingerprint &&
            previousAddressFingerprint != addressFingerprint

        ApplePathMonitorUpdate(
            isFirstSatisfied = isFirstSatisfied,
            becameSatisfied = becameSatisfied,
            previousInterfaceFingerprint = previousInterfaceFingerprint,
            interfaceChanged = interfaceChanged,
            previousAddressFingerprint = previousAddressFingerprint,
            addressChanged = addressChanged
        )
    }

    private fun resetObservationsLocked() {
        lastWasSatisfied = false
        hasEverObservedSatisfied = false
        lastInterfaceFingerprint = NO_INTERFACE_FINGERPRINT
        lastAddressFingerprint = NO_ADDRESS_FINGERPRINT
    }

    private inline fun <T> withLock(block: () -> T): T {
        lock.lock()
        return try {
            block()
        } finally {
            lock.unlock()
        }
    }

    internal companion object {
        const val NO_INTERFACE_FINGERPRINT: Int = -1
        val NO_ADDRESS_FINGERPRINT: ULong = ULong.MAX_VALUE
    }
}
