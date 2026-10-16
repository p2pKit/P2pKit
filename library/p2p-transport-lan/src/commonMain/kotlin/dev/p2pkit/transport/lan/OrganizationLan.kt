package dev.p2pkit.transport.lan

/** Explicit role; DialOnly never binds a TCP listener or advertises a service. */
public enum class LanRole {
    Host,
    DialOnly,
}

/**
 * Fail-closed organization-network profile. Only RFC1918 IPv4 and IPv6 ULA destinations inside
 * [allowedSubnets] are accepted. Both a physical LAN interface and one numeric local address must
 * be selected. No DNS, default-interface, cellular, VPN or peer-to-peer fallback is permitted.
 * Routed private VLANs are supported; administrators must prohibit offsite routing/tunneling.
 * This profile cannot inspect what routers do after packets leave the selected local interface.
 */
public class OrganizationLan(
    allowedSubnets: List<String>,
    public val interfaceName: String,
    public val localAddress: String,
    public val listenPort: Int = 0,
) {
    public val allowedSubnets: List<String> get() = subnets.map { it.text }
    private val subnets = allowedSubnets.map(PrivateSubnet::parse)
    internal val local: NumericAddress = NumericAddress.parse(localAddress)
        ?: throw IllegalArgumentException("A numeric private local address is required")

    init {
        require(subnets.size in 1..64) { "Select 1 to 64 organization-private subnets" }
        require(interfaceName.length in 1..32 && interfaceName.all {
            it in 'a'..'z' || it in 'A'..'Z' || it in '0'..'9' || it in "_.-"
        }) { "An explicit OS LAN interface name is required" }
        require(!isForbiddenLanInterface(interfaceName)) { "Tunnel/peer-to-peer interfaces are forbidden" }
        require(listenPort in 0..65_535)
        require(allows(localAddress)) { "The local address must be in the approved private subnets" }
    }

    /** Numeric-only policy check. Never resolves names or normalizes an ambiguous IPv4 spelling. */
    public fun allows(address: String): Boolean {
        val parsed = NumericAddress.parse(address) ?: return false
        return parsed.isPrivate && subnets.any { it.contains(parsed) }
    }

    internal fun isLocal(address: String): Boolean = NumericAddress.parse(address) == local

    override fun toString(): String = "OrganizationLan(subnets=${subnets.size}, listenPort=$listenPort)"
}

/** Strict ASCII numeric parser: no hostnames, scopes, mapped IPv4, octal, signs, whitespace or brackets. */
internal class NumericAddress private constructor(val bytes: ByteArray) {
    val isPrivate: Boolean get() = when (bytes.size) {
        4 -> byte(0) == 10 || (byte(0) == 172 && byte(1) in 16..31) ||
            (byte(0) == 192 && byte(1) == 168)
        16 -> byte(0) and 0xfe == 0xfc
        else -> false
    }

    private fun byte(index: Int): Int = bytes[index].toInt() and 0xff

    override fun equals(other: Any?): Boolean = other is NumericAddress && bytes.contentEquals(other.bytes)
    override fun hashCode(): Int = bytes.contentHashCode()

    companion object {
        fun parse(text: String): NumericAddress? {
            if (text.isEmpty() || text.length > 39) return null
            if (':' !in text) {
                val parts = text.split('.')
                if (parts.size != 4) return null
                val values = parts.map {
                    if (it.isEmpty() || it.length > 3 || it.any { c -> c !in '0'..'9' } ||
                        (it.length > 1 && it[0] == '0')
                    ) return null
                    (it.toIntOrNull()?.takeIf { n -> n in 0..255 } ?: return null).toByte()
                }
                return NumericAddress(values.toByteArray())
            }
            if (text.any { it !in "0123456789abcdefABCDEF:" }) return null
            val halves = text.split("::")
            if (halves.size > 2) return null
            fun words(part: String): List<Int>? {
                if (part.isEmpty()) return emptyList()
                return part.split(':').map {
                    if (it.length !in 1..4) return null
                    it.toIntOrNull(16) ?: return null
                }
            }
            val left = words(halves[0]) ?: return null
            val right = if (halves.size == 2) words(halves[1]) ?: return null else emptyList()
            val missing = 8 - left.size - right.size
            if ((halves.size == 1 && missing != 0) || (halves.size == 2 && missing < 1)) return null
            val all = left + List(missing) { 0 } + right
            if (all.size != 8) return null
            return NumericAddress(ByteArray(16) { index ->
                (all[index / 2] ushr (if (index % 2 == 0) 8 else 0)).toByte()
            })
        }
    }
}

internal class PrivateSubnet private constructor(
    val text: String,
    private val address: NumericAddress,
    private val prefix: Int,
) {
    fun contains(candidate: NumericAddress): Boolean {
        if (candidate.bytes.size != address.bytes.size) return false
        return address.bytes.indices.all { index ->
            val bits = (prefix - index * 8).coerceIn(0, 8)
            val mask = (0xff shl (8 - bits)) and 0xff
            (address.bytes[index].toInt() and mask) == (candidate.bytes[index].toInt() and mask)
        }
    }

    companion object {
        fun parse(text: String): PrivateSubnet {
            require(text.length <= 43)
            val parts = text.split('/')
            require(parts.size == 2 && parts[1].all { it in '0'..'9' }) { "CIDR notation is required" }
            val address = requireNotNull(NumericAddress.parse(parts[0])) { "Invalid numeric subnet" }
            val prefix = requireNotNull(parts[1].toIntOrNull()) { "Invalid subnet prefix" }
            require(prefix in 0..(address.bytes.size * 8))
            require(address.isPrivate) { "Only RFC1918 and IPv6 ULA subnets are allowed" }
            val minimum = if (address.bytes.size == 16) 7 else when (address.bytes[0].toInt() and 0xff) {
                10 -> 8
                172 -> 12
                else -> 16
            }
            require(prefix >= minimum) { "A subnet may not include non-private addresses" }
            address.bytes.indices.forEach { index ->
                val bits = (prefix - index * 8).coerceIn(0, 8)
                val hostMask = (1 shl (8 - bits)) - 1
                require((address.bytes[index].toInt() and hostMask) == 0) { "CIDR host bits must be zero" }
            }
            return PrivateSubnet(text, address, prefix)
        }
    }
}

internal fun isForbiddenLanInterface(name: String): Boolean = listOf(
    "lo", "utun", "tun", "tap", "wg", "ppp", "ipsec", "vpn", "awdl", "llw", "gif", "stf",
    "veth", "docker", "vbox", "vmnet", "bridge"
).any { name.lowercase().startsWith(it) }
