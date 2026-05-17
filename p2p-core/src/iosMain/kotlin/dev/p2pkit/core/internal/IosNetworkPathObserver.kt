@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.core.internal

import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pLogger
import kotlin.concurrent.Volatile
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import platform.Network.nw_path_get_status
import platform.Network.nw_path_monitor_cancel
import platform.Network.nw_path_monitor_create
import platform.Network.nw_path_monitor_set_queue
import platform.Network.nw_path_monitor_set_update_handler
import platform.Network.nw_path_monitor_start
import platform.Network.nw_path_monitor_t
import platform.Network.nw_path_status_satisfied
import platform.Network.nw_path_status_unsatisfied
import platform.darwin.dispatch_queue_create

/**
 * iOS / macOS network-path observer backed by Apple's `nw_path_monitor_t`.
 *
 * The monitor runs on a dedicated serial dispatch queue and fires its
 * update handler whenever the system's default path changes (Wi-Fi off,
 * carrier handover, VPN attach/detach, …). Each event is mapped to one
 * of three [NetworkPathStatus] values and pushed into [status].
 *
 * **What about `satisfiable` / `invalid`?** Apple defines four states
 * total: `satisfied`, `unsatisfied`, `satisfiable` (path is unavailable
 * but might come back), and `invalid` (the monitor is shutting down). We
 * only care about `satisfied` and `unsatisfied` for kit decisions; the
 * other two map to [NetworkPathStatus.Unknown] so the SDK does nothing.
 *
 * **Lambda return-type hazard:** the update handler block must return
 * void. Kotlin/Native infers the lambda's ObjC return type from its last
 * expression; if that's the return value of `_status.value =`
 * (incidentally `Unit` here, but not guaranteed by the language), we still
 * append an explicit `Unit` to match what we had to do in the LAN
 * transport's handlers — without it Kotlin/Native has historically tried
 * to box the result and crash libdispatch.
 */
internal class IosNetworkPathObserver(
    private val logger: P2pLogger
) : NetworkPathObserver {

    private val _status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()

    private val queue = dispatch_queue_create("dev.p2pkit.nwpath", null)
    private val startMutex = Mutex()

    @Volatile
    private var monitor: nw_path_monitor_t = null

    override suspend fun start() = startMutex.withLock {
        if (monitor != null) return@withLock
        val m = nw_path_monitor_create() ?: run {
            logger.warn("nw_path_monitor_create returned null; path observer will report Unknown")
            return@withLock
        }
        nw_path_monitor_set_queue(m, queue)
        nw_path_monitor_set_update_handler(m) { path ->
            val s = nw_path_get_status(path)
            val mapped: NetworkPathStatus = when (s) {
                nw_path_status_satisfied -> NetworkPathStatus.Satisfied
                nw_path_status_unsatisfied -> NetworkPathStatus.Unsatisfied
                else -> NetworkPathStatus.Unknown
            }
            _status.value = mapped
            Unit
        }
        nw_path_monitor_start(m)
        monitor = m
    }

    override suspend fun close() = startMutex.withLock {
        val m = monitor ?: return@withLock
        nw_path_monitor_cancel(m)
        monitor = null
    }
}
