@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.P2pError
import dev.p2pkit.transport.lan.interop.p2pkit_nw_lan_path_is_allowed
import dev.p2pkit.transport.lan.interop.p2pkit_nw_restrict_lan_parameters
import kotlinx.cinterop.toKString
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import platform.Network.nw_connection_t
import platform.Network.nw_parameters_t
import platform.Network.nw_path_monitor_cancel
import platform.Network.nw_path_monitor_create
import platform.Network.nw_path_monitor_set_queue
import platform.Network.nw_path_monitor_set_update_handler
import platform.Network.nw_path_monitor_start
import platform.darwin.dispatch_queue_t
import kotlin.coroutines.resume

/** A bounded native path snapshot supplies the actual interface object required by Network.framework. */
internal suspend fun restrictAppleLanParameters(
    parameters: nw_parameters_t,
    policy: OrganizationLan,
    queue: dispatch_queue_t,
    port: Int? = null,
): nw_parameters_t {
    if (parameters == null) throw P2pError.ConnectionFailed("Organization LAN parameters are unavailable")
    val allowed = withTimeoutOrNull(3_000) {
        suspendCancellableCoroutine<Boolean> { continuation ->
            val monitor = nw_path_monitor_create()
            if (monitor == null) {
                continuation.resume(false)
                return@suspendCancellableCoroutine
            }
            val settled = kotlin.concurrent.AtomicInt(0)
            fun stop() {
                nw_path_monitor_set_update_handler(monitor, null)
                nw_path_monitor_cancel(monitor)
            }
            continuation.invokeOnCancellation {
                settled.compareAndSet(0, 1)
                stop()
            }
            nw_path_monitor_set_queue(monitor, queue)
            nw_path_monitor_set_update_handler(monitor) { path ->
                if (settled.compareAndSet(0, 1)) {
                    val result = p2pkit_nw_restrict_lan_parameters(
                        parameters, path, policy.interfaceName, policy.localAddress, port?.toString()
                    )
                    stop()
                    if (continuation.isActive) continuation.resume(result)
                }
            }
            if (settled.value == 0) nw_path_monitor_start(monitor) else stop()
        }
    }
    if (allowed != true) throw P2pError.ConnectionFailed("Selected organization LAN path cannot be verified")
    return parameters
}

internal fun OrganizationLan.allowsAppleConnection(connection: nw_connection_t): Boolean =
    p2pkit_nw_lan_path_is_allowed(connection, interfaceName, localAddress) { address ->
        address?.toKString()?.let(::allows) == true
    }
