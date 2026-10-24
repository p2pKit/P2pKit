package dev.p2pkit.transport.lan

import java.net.Inet6Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket

/** Numeric readback only: unresolved addresses never trigger a name lookup. */
internal fun Socket.connectedLanEndpoint(): LanTcpEndpoint? = observeOptionalLanRoute {
    val remote = remoteSocketAddress as? InetSocketAddress ?: return@observeOptionalLanRoute null
    if (remote.isUnresolved || remote.port !in 1..65_535) return@observeOptionalLanRoute null
    val numeric = remote.address?.lanNumericAddress() ?: return@observeOptionalLanRoute null
    LanTcpEndpoint(numeric, remote.port)
}

internal fun InetAddress.lanNumericAddress(): LanNumericAddress? =
    LanNumericAddress.copyOf(address, (this as? Inet6Address)?.scopeId ?: 0)

internal fun LanNumericAddress.inetAddress(): InetAddress {
    val bytes = copyBytes()
    return if (bytes.size == 16) Inet6Address.getByAddress(null, bytes, scopeId)
    else InetAddress.getByAddress(bytes)
}

internal fun LanTcpEndpoint.socketAddress(): InetSocketAddress = InetSocketAddress(address.inetAddress(), port)
