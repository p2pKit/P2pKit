package dev.p2pkit.provisioning.android

import java.net.Inet4Address
import java.net.Inet6Address
import java.net.InetAddress
import java.net.NetworkInterface
import kotlinx.coroutines.CancellationException

/** The module's only NetworkInterface enumerator; the manager owns its IO hop. */
internal fun collectProvisioningInterfaceAddresses(): List<String> = collectProvisioningInterfaceAddresses(
    interfaces = { NetworkInterface.getNetworkInterfaces()?.asSequence().orEmpty() },
    addresses = { network ->
        if (!network.isUp || network.isLoopback) emptyList()
        else network.inetAddresses.asSequence().toList()
    }
)

/** A disappearing/unreadable NIC must not discard usable sibling interfaces. */
internal fun <T> collectProvisioningInterfaceAddresses(
    interfaces: () -> Sequence<T>,
    addresses: (T) -> List<InetAddress>
): List<String> {
    val current = try {
        interfaces()
    } catch (failure: CancellationException) {
        throw failure
    } catch (_: Exception) {
        return emptyList()
    }
    val candidates = mutableListOf<InetAddress>()
    for (network in current) {
        val snapshot = try {
            addresses(network)
        } catch (failure: CancellationException) {
            throw failure
        } catch (_: Exception) {
            continue
        }
        candidates += snapshot
    }
    return selectProvisioningInterfaceAddresses(candidates)
}

/**
 * Preserve usable IPv4 (including directly connected link-local IPv4) and add
 * portable non-link-local IPv6 unicast. Link-local IPv6 needs the receiver's
 * own interface scope, not a sender-local index/name. Deprecated IPv6 site-local
 * addresses likewise have no portable site scope. Global/ULA candidates are
 * emitted without a zone. This is not a route selector: the LAN transport still
 * enforces its existing LAN-only carrier and destination policy when dialing.
 */
internal fun selectProvisioningInterfaceAddresses(addresses: List<InetAddress>): List<String> =
    addresses.mapNotNull { address ->
        if (address.isLoopbackAddress || address.isAnyLocalAddress || address.isMulticastAddress) {
            return@mapNotNull null
        }
        val host = address.hostAddress ?: return@mapNotNull null
        when (address) {
            is Inet4Address -> host
            is Inet6Address -> host.substringBefore('%').takeUnless {
                address.isLinkLocalAddress || address.isSiteLocalAddress
            }
            else -> null
        }
    }.distinct()
