@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.transport.lan.interop.p2pkit_lan_enumerate_interface_addresses
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.pointed
import kotlinx.cinterop.readBytes
import kotlinx.cinterop.toKString

/** Owned Kotlin copy of one borrowed `getifaddrs` entry. */
internal data class AppleInterfaceAddressCandidate(
    val addressBytes: ByteArray,
    val ipVersion: Int,
    val interfaceName: String,
    val interfaceIndex: UInt,
    val addressScopeId: UInt,
    val interfaceIsUp: Boolean,
    val interfaceIsRunning: Boolean,
    val interfaceIsLoopback: Boolean,
    val interfaceIsPointToPoint: Boolean,
    val interfaceSupportsMulticast: Boolean,
    val addressIsInterfaceBroadcast: Boolean
)

internal data class AppleInterfaceAddressSnapshot(
    val candidates: List<AppleInterfaceAddressCandidate>,
    val enumerationErrorCode: Int? = null
)

internal fun interface AppleInterfaceAddressScanner {
    fun scan(): AppleInterfaceAddressSnapshot
}

/**
 * Copy one synchronous `getifaddrs` snapshot into Kotlin-owned values.
 * Callback failures are retained and rethrown only after the C helper has
 * released the native list, so no Kotlin exception crosses the C boundary.
 */
internal fun collectAppleInterfaceAddressSnapshot(): AppleInterfaceAddressSnapshot {
    val candidates = mutableListOf<AppleInterfaceAddressCandidate>()
    var callbackFailure: Throwable? = null
    val status = p2pkit_lan_enumerate_interface_addresses { borrowed ->
        if (borrowed != null && callbackFailure == null) {
            try {
                val candidate = borrowed.pointed
                val length = candidate.address_length.toInt()
                val bytes = candidate.address_bytes?.readBytes(length)
                val interfaceName = candidate.interface_name?.toKString()
                if (bytes != null && interfaceName != null) {
                    candidates += AppleInterfaceAddressCandidate(
                        addressBytes = bytes,
                        ipVersion = candidate.ip_version.toInt(),
                        interfaceName = interfaceName,
                        interfaceIndex = candidate.interface_index,
                        addressScopeId = candidate.address_scope_id,
                        interfaceIsUp = candidate.interface_is_up,
                        interfaceIsRunning = candidate.interface_is_running,
                        interfaceIsLoopback = candidate.interface_is_loopback,
                        interfaceIsPointToPoint = candidate.interface_is_point_to_point,
                        interfaceSupportsMulticast = candidate.interface_supports_multicast,
                        addressIsInterfaceBroadcast = candidate.address_is_interface_broadcast
                    )
                }
            } catch (failure: Throwable) {
                callbackFailure = failure
            }
        }
    }
    callbackFailure?.let { throw it }
    return AppleInterfaceAddressSnapshot(
        candidates = candidates,
        enumerationErrorCode = status.takeUnless { it == 0 }
    )
}

/**
 * Select a stable list of addresses that matches the Apple LAN transport's
 * interface policy: active multicast-capable LAN/AWDL carriers only, never
 * loopback, cellular/VPN-style point-to-point interfaces, wildcard,
 * multicast, or broadcast addresses.
 *
 * IPv4 link-local addresses remain useful for direct segments. IPv6
 * link-local addresses are admitted only when the kernel scope agrees with
 * the enumerated interface; the interface name is appended as the required
 * zone. Global/unique-local IPv6 addresses are emitted without a zone.
 */
internal fun selectAppleHostAddresses(
    candidates: List<AppleInterfaceAddressCandidate>
): List<String> = candidates.asSequence()
    .mapNotNull(::selectAppleHostAddress)
    .distinctBy(SelectedAppleHostAddress::host)
    .sortedWith(compareBy(SelectedAppleHostAddress::rank, SelectedAppleHostAddress::host))
    .map(SelectedAppleHostAddress::host)
    .toList()

private data class SelectedAppleHostAddress(val host: String, val rank: Int)

private fun selectAppleHostAddress(
    candidate: AppleInterfaceAddressCandidate
): SelectedAppleHostAddress? {
    if (!candidate.interfaceIsUp ||
        !candidate.interfaceIsRunning ||
        candidate.interfaceIsLoopback ||
        candidate.interfaceIsPointToPoint ||
        !candidate.interfaceSupportsMulticast
    ) {
        return null
    }

    return when (candidate.ipVersion) {
        4 -> selectIpv4HostAddress(candidate)
        6 -> selectIpv6HostAddress(candidate)
        else -> null
    }
}

private fun selectIpv4HostAddress(
    candidate: AppleInterfaceAddressCandidate
): SelectedAppleHostAddress? {
    val bytes = candidate.addressBytes
    if (bytes.size != IPV4_BYTE_COUNT) return null
    val first = bytes.unsigned(0)
    val unsafe = first == 0 ||
        first == 127 ||
        first in 224..239 ||
        first >= 240 ||
        candidate.addressIsInterfaceBroadcast
    if (unsafe) return null

    val host = bytes.joinToString(".") { (it.toInt() and 0xFF).toString() }
    val rank = if (first == 169 && bytes.unsigned(1) == 254) 1 else 0
    return SelectedAppleHostAddress(host = host, rank = rank)
}

private fun selectIpv6HostAddress(
    candidate: AppleInterfaceAddressCandidate
): SelectedAppleHostAddress? {
    val bytes = candidate.addressBytes
    if (bytes.size != IPV6_BYTE_COUNT ||
        bytes.all { it == 0.toByte() } ||
        bytes.isIpv6Loopback() ||
        bytes.unsigned(0) == 0xFF ||
        bytes.isDeprecatedIpv6SiteLocal() ||
        bytes.isIpv4EmbeddedIpv6()
    ) {
        return null
    }

    val interfaceIndex = candidate.interfaceIndex
    if (candidate.addressScopeId != 0u &&
        interfaceIndex != 0u &&
        candidate.addressScopeId != interfaceIndex
    ) {
        return null
    }

    val numericAddress = formatIpv6Address(bytes)
    val isLinkLocal = bytes.unsigned(0) == 0xFE && (bytes.unsigned(1) and 0xC0) == 0x80
    if (!isLinkLocal) return SelectedAppleHostAddress(host = numericAddress, rank = 2)
    if (interfaceIndex == 0u || !candidate.interfaceName.isSafeInterfaceScope()) return null

    return SelectedAppleHostAddress(
        host = "$numericAddress%${candidate.interfaceName}",
        rank = 3
    )
}

private fun ByteArray.isIpv6Loopback(): Boolean =
    take(IPV6_BYTE_COUNT - 1).all { it == 0.toByte() } && last().unsignedValue() == 1

private fun ByteArray.isIpv4EmbeddedIpv6(): Boolean {
    val compatible = take(12).all { it == 0.toByte() }
    val mapped = take(10).all { it == 0.toByte() } &&
        unsigned(10) == 0xFF &&
        unsigned(11) == 0xFF
    return compatible || mapped
}

private fun ByteArray.isDeprecatedIpv6SiteLocal(): Boolean =
    unsigned(0) == 0xFE && (unsigned(1) and 0xC0) == 0xC0

private fun formatIpv6Address(bytes: ByteArray): String {
    val groups = IntArray(8) { index ->
        (bytes.unsigned(index * 2) shl 8) or bytes.unsigned(index * 2 + 1)
    }
    var longestStart = -1
    var longestLength = 0
    var index = 0
    while (index < groups.size) {
        if (groups[index] != 0) {
            index++
            continue
        }
        val start = index
        while (index < groups.size && groups[index] == 0) index++
        val length = index - start
        if (length >= 2 && length > longestLength) {
            longestStart = start
            longestLength = length
        }
    }
    if (longestStart == -1) return groups.joinToString(":") { it.toString(16) }

    val left = groups.take(longestStart).joinToString(":") { it.toString(16) }
    val right = groups.drop(longestStart + longestLength).joinToString(":") { it.toString(16) }
    return when {
        left.isEmpty() && right.isEmpty() -> "::"
        left.isEmpty() -> "::$right"
        right.isEmpty() -> "$left::"
        else -> "$left::$right"
    }
}

private fun String.isSafeInterfaceScope(): Boolean = length in 1..MAX_INTERFACE_NAME_LENGTH && all { character ->
    character in 'a'..'z' ||
        character in 'A'..'Z' ||
        character in '0'..'9' ||
        character == '_' ||
        character == '-' ||
        character == '.'
}

private fun ByteArray.unsigned(index: Int): Int = this[index].toInt() and 0xFF
private fun Byte.unsignedValue(): Int = toInt() and 0xFF

private const val IPV4_BYTE_COUNT: Int = 4
private const val IPV6_BYTE_COUNT: Int = 16
private const val MAX_INTERFACE_NAME_LENGTH: Int = 15
