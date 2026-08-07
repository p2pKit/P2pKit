package dev.p2pkit.core.internal

import dev.p2pkit.core.NetworkPathStatus

/**
 * Generation-gated state shared by platform network-path callbacks.
 *
 * The owning observer must serialize calls. A generation starts before the
 * native callback is registered so synchronous registration callbacks are
 * accepted. [detach] invalidates that generation and clears its retained
 * networks; callbacks from a cancelled monitor then return `null` and cannot
 * overwrite the next generation's status.
 */
internal class NetworkPathCallbackState<NetworkKey> {
    private var nextGeneration: Long = 0L
    private var activeGeneration: Long? = null
    private val activeNetworks: MutableSet<NetworkKey> = mutableSetOf()

    /** Starts a generation, or returns `null` while an existing one is owned. */
    fun begin(): Long? {
        if (activeGeneration != null) return null
        val generation = ++nextGeneration
        activeGeneration = generation
        activeNetworks.clear()
        return generation
    }

    /** Returns the generation whose native cleanup is still owned. */
    fun currentGeneration(): Long? = activeGeneration

    fun publish(generation: Long, status: NetworkPathStatus): NetworkPathStatus? =
        status.takeIf { activeGeneration == generation }

    fun available(generation: Long, network: NetworkKey): NetworkPathStatus? {
        if (activeGeneration != generation) return null
        activeNetworks += network
        return NetworkPathStatus.Satisfied
    }

    fun lost(generation: Long, network: NetworkKey): NetworkPathStatus? {
        if (activeGeneration != generation) return null
        activeNetworks -= network
        return NetworkPathStatus.Unsatisfied.takeIf { activeNetworks.isEmpty() }
    }

    fun detach(generation: Long): NetworkPathStatus? {
        if (activeGeneration != generation) return null
        activeGeneration = null
        activeNetworks.clear()
        return NetworkPathStatus.Unknown
    }
}
