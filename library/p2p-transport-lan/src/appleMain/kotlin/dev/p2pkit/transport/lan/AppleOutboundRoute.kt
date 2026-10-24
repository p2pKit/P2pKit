@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.transport.lan.interop.p2pkit_lan_copy_tcp_endpoint
import dev.p2pkit.transport.lan.interop.p2pkit_lan_create_tcp_endpoint
import dev.p2pkit.transport.lan.interop.p2pkit_lan_tcp_endpoint_t
import dev.p2pkit.transport.lan.interop.p2pkit_nw_copy_connected_tcp_endpoint
import dev.p2pkit.transport.lan.interop.p2pkit_nw_create_route_connection
import kotlinx.cinterop.alloc
import kotlinx.cinterop.get
import kotlinx.cinterop.memScoped
import kotlinx.cinterop.ptr
import kotlinx.cinterop.set
import platform.Network.nw_connection_t
import platform.Network.nw_endpoint_t
import platform.Network.nw_parameters_t

/** Copies only numeric bytes/port/scope. All copied NWPath/endpoint leases die inside the C helper. */
internal fun appleConnectedEndpoint(connection: nw_connection_t): LanTcpEndpoint? = memScoped {
    val endpoint = alloc<p2pkit_lan_tcp_endpoint_t>()
    if (!p2pkit_nw_copy_connected_tcp_endpoint(connection, endpoint.ptr)) return@memScoped null
    endpoint.copiedValue()
}

internal fun appleNumericEndpoint(endpoint: nw_endpoint_t): LanTcpEndpoint? = memScoped {
    val copied = alloc<p2pkit_lan_tcp_endpoint_t>()
    if (!p2pkit_lan_copy_tcp_endpoint(endpoint, copied.ptr)) return@memScoped null
    copied.copiedValue()
}

private fun p2pkit_lan_tcp_endpoint_t.copiedValue(): LanTcpEndpoint? {
    if (address_length != 4u && address_length != 16u || scope_id > Int.MAX_VALUE.toUInt()) return null
    val bytes = ByteArray(address_length.toInt()) { address[it].toByte() }
    val numeric = LanNumericAddress.copyOf(bytes, scope_id.toInt()) ?: return null
    if (port.toInt() !in 1..65_535) return null
    return LanTcpEndpoint(numeric, port.toInt())
}

/** Used by endpoint round-trip controls only; production keeps the reconstructed endpoint inside C. */
internal fun LanTcpEndpoint.appleEndpoint(): nw_endpoint_t = memScoped {
    val copied = alloc<p2pkit_lan_tcp_endpoint_t>()
    copyTo(copied)
    p2pkit_lan_create_tcp_endpoint(copied.ptr)
}

internal fun LanTcpEndpoint.appleConnection(parameters: nw_parameters_t): nw_connection_t = memScoped {
    val copied = alloc<p2pkit_lan_tcp_endpoint_t>()
    copyTo(copied)
    p2pkit_nw_create_route_connection(copied.ptr, parameters)
}

private fun LanTcpEndpoint.copyTo(copied: p2pkit_lan_tcp_endpoint_t) {
    val bytes = address.copyBytes()
    copied.address_length = bytes.size.toUInt()
    copied.scope_id = address.scopeId.toUInt()
    copied.port = port.toUShort()
    repeat(16) { copied.address[it] = if (it < bytes.size) bytes[it].toUByte() else 0u }
}
