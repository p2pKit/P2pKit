package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.TransportSecurityProfile

/**
 * Identity advertised over mDNS plus the bound TCP port, shared between each
 * platform's data and discovery transports (created once per kit by the
 * platform's [dev.p2pkit.core.transport.TransportFactory]).
 *
 * The port is mutable since the v0.3 transport-lifecycle refactor: the data
 * transport binds its server socket lazily in `start()`, then writes the
 * chosen port back into this struct before the discovery transport begins
 * advertising. A zero value means "not bound yet" — discovery transports
 * should not call this with [tcpPort] == 0.
 *
 * The platform `@Volatile` annotations differ between JVM and Kotlin/Native,
 * so we just rely on the SPI call ordering guaranteed by core's start path
 * (it holds a mutex and runs `DataTransport.start()` strictly before
 * `DiscoveryTransport.startAdvertising()`). No cross-thread reads of
 * [tcpPort] happen outside that ordering.
 */
internal class LanServiceRegistration(
    val appId: AppId,
    val localPeerId: PeerId,
    val deviceName: String,
    val platform: Platform,
    val securityProfile: TransportSecurityProfile = TransportSecurityProfile.LegacyPlaintextV1,
    val fingerprint: PeerFingerprint? = null,
    var tcpPort: Int = 0
) {
    init {
        require(
            (securityProfile == TransportSecurityProfile.AuthenticatedV2) == (fingerprint != null)
        ) {
            "Authenticated v2 LAN registration requires a fingerprint; legacy plaintext must not advertise one"
        }
    }

    val serviceTypeJmdns: String get() = LanConstants.serviceTypeJmdns(securityProfile)
    val protocolVersion: Int get() = LanConstants.protocolVersion(securityProfile)
}

/** Validated security portion of a LAN TXT record. */
internal data class LanDiscoverySecurityMetadata(
    val authenticationHint: PeerAuthenticationHint?
)

/**
 * Require a TXT record to match the whole-kit wire profile before publishing
 * it. The v2 fingerprint is discovery input only: authentication still has to
 * prove possession of the corresponding private key, and authorization is
 * evaluated after that proof.
 */
internal fun validateLanDiscoverySecurityMetadata(
    profile: TransportSecurityProfile,
    protocolVersion: String?,
    fingerprint: String?
): LanDiscoverySecurityMetadata? {
    if (protocolVersion != LanConstants.protocolVersion(profile).toString()) return null
    return when (profile) {
        TransportSecurityProfile.AuthenticatedV2 -> {
            val parsed = fingerprint?.let(PeerFingerprint::parseOrNull) ?: return null
            LanDiscoverySecurityMetadata(PeerAuthenticationHint.UntrustedDiscoveryClaim(parsed))
        }
        TransportSecurityProfile.LegacyPlaintextV1 -> {
            if (fingerprint != null) return null
            LanDiscoverySecurityMetadata(authenticationHint = null)
        }
    }
}

/** Wire-level constants shared by the JVM and Android implementations. */
internal object LanConstants {
    /** JmDNS-style service type. Used by [JvmLanDiscoveryTransport]. */
    const val LEGACY_SERVICE_TYPE_JMDNS: String = "_p2pkit._tcp.local."
    const val SECURE_SERVICE_TYPE_JMDNS: String = "_p2pkit2._tcp.local."

    /**
     * Bonjour service type for iOS `nw_advertise_descriptor` and
     * `nw_browse_descriptor`. No trailing dot — Apple's API expects the
     * canonical form. Wire-identical to the JmDNS string above.
     */
    const val LEGACY_SERVICE_TYPE_BONJOUR: String = "_p2pkit._tcp"
    const val SECURE_SERVICE_TYPE_BONJOUR: String = "_p2pkit2._tcp"

    // TXT record keys. Both platforms must use the same keys.
    const val TXT_PEER_ID: String = "pid"
    const val TXT_APP_ID: String = "app"
    const val TXT_DEVICE_NAME: String = "name"
    const val TXT_PLATFORM: String = "plat"
    const val TXT_CAPABILITIES: String = "caps"
    const val TXT_PROTOCOL_VERSION: String = "pv"
    const val TXT_FINGERPRINT: String = "fp"

    val DISCOVERY_TXT_KEYS: Set<String> = setOf(
        TXT_PEER_ID,
        TXT_APP_ID,
        TXT_DEVICE_NAME,
        TXT_PLATFORM,
        TXT_CAPABILITIES,
        TXT_PROTOCOL_VERSION,
        TXT_FINGERPRINT
    )

    /** Wire protocol version. Must match `ProtocolConstants.VERSION` in :p2p-core. */
    const val LEGACY_PROTOCOL_VERSION: Int = 1
    const val SECURE_PROTOCOL_VERSION: Int = 2

    fun serviceTypeJmdns(profile: TransportSecurityProfile): String = when (profile) {
        TransportSecurityProfile.AuthenticatedV2 -> SECURE_SERVICE_TYPE_JMDNS
        TransportSecurityProfile.LegacyPlaintextV1 -> LEGACY_SERVICE_TYPE_JMDNS
    }

    fun serviceTypeBonjour(profile: TransportSecurityProfile): String = when (profile) {
        TransportSecurityProfile.AuthenticatedV2 -> SECURE_SERVICE_TYPE_BONJOUR
        TransportSecurityProfile.LegacyPlaintextV1 -> LEGACY_SERVICE_TYPE_BONJOUR
    }

    fun protocolVersion(profile: TransportSecurityProfile): Int = when (profile) {
        TransportSecurityProfile.AuthenticatedV2 -> SECURE_PROTOCOL_VERSION
        TransportSecurityProfile.LegacyPlaintextV1 -> LEGACY_PROTOCOL_VERSION
    }

    /**
     * Per-attempt TCP connect timeout used by the JVM and Android data
     * transports when dialing a discovered peer. v0.5 real-device traces
     * showed the kernel's default `Socket(host, port)` blocking ~17 s
     * before ECONNREFUSED on a stale port — that whole window is wasted
     * dead time during reconnect because the next attempt would have
     * picked up the fresh port from the JmDNS cache. 5 s comfortably
     * exceeds typical LAN RTT plus TCP SYN retries while still keeping
     * three full retries inside the sample's
     * `ReconnectPolicy.Enabled(maxAttempts=10, retryDelayMillis=1500)`
     * budget. iOS-side `NWConnection` already times out on a shorter
     * horizon via `Network.framework`, so no equivalent knob is needed
     * on the appleMain path.
     */
    const val TCP_CONNECT_TIMEOUT_MS: Int = 5_000

    /**
     * AUDIT-2026-07 (DSC-1): cadence of the JVM/Android discovery heartbeat —
     * while discovery is active, both transports re-emit
     * [dev.p2pkit.core.transport.PeerEvent.Updated] for every appId-matching
     * service already resolved in the in-process JmDNS cache, so
     * `PeerRegistry.lastSeen` keeps refreshing and healthy idle peers survive
     * the registry's 15 s staleness eviction (previously only iOS had this
     * loop, so `kit.peers` silently emptied on JVM/Android in steady state).
     * Reads the local cache only — no forced network re-query, no added
     * multicast. Must stay comfortably below PeerRegistry's 15 s eviction
     * horizon; matches the iOS `PEER_REANNOUNCE_INTERVAL_MS`
     * (IosLanDiscoveryTransport), which stays platform-local by design.
     */
    const val PEER_REANNOUNCE_INTERVAL_MS: Long = 5_000
}

internal val TransportContext.lanServiceTypeBonjour: String
    get() = LanConstants.serviceTypeBonjour(securityProfile)

internal val TransportContext.lanProtocolVersion: Int
    get() = LanConstants.protocolVersion(securityProfile)

/**
 * AUDIT-2026-07 (RBS-1): input validation for the `pid` value of a discovery
 * TXT record, shared by the found and lost paths of the JVM, Android, and
 * iOS discovery transports (the three must stay behavior-identical).
 *
 * [dev.p2pkit.core.PeerId] rejects blank values with an exception, and every
 * discovery callback constructs a [dev.p2pkit.core.PeerId] from this TXT
 * value — so a malformed record from a non-conforming same-service-type
 * advertiser must be dropped inside the platform callback, never thrown
 * across it (on iOS a throw would cross the `nw_browser` callback boundary;
 * on JVM/Android it would surface untyped on a JmDNS listener thread).
 *
 * Returns [rawPid] unchanged when it is usable (present, non-blank, bounded,
 * and free of protocol/log controls), or `null` when the record must be
 * skipped. Values are deliberately NOT trimmed or otherwise normalized —
 * identity handling for conforming peers is unchanged.
 */
internal fun validDiscoveryPeerIdOrNull(rawPid: String?): String? =
    validLanTxtValueOrNull(LanConstants.TXT_PEER_ID, rawPid)
        ?.takeUnless(String::isBlank)

internal fun validLanTxtValueOrNull(key: String, raw: String?): String? =
    raw?.takeIf { lanTxtEntryFits(key, it) && it.isWellFormedLanText() }

/** Fully bounded/validated semantic content of one LAN discovery record. */
internal data class ValidatedLanDiscoveryRecord(
    val peerId: PeerId,
    val deviceName: String,
    val platform: Platform,
    val supportedTransports: Set<TransportKind>,
    val security: LanDiscoverySecurityMetadata
) {
    fun toInternalPeer(hint: TransportHint): InternalPeer = InternalPeer(
        publicPeer = Peer(
            id = peerId,
            name = deviceName,
            platform = platform,
            supportedTransports = supportedTransports
        ),
        transportHints = listOf(hint),
        authenticationHint = security.authenticationHint
    )
}

/**
 * Parse only a bounded record matching this app/security profile. Unknown
 * fields are ignored for forward compatibility; every consumed field must
 * fit one DNS-SD TXT character-string and contain no terminal/log controls.
 */
internal fun validateLanDiscoveryRecord(
    properties: Map<String, String?>,
    expectedAppId: AppId,
    localPeerId: PeerId,
    securityProfile: TransportSecurityProfile
): ValidatedLanDiscoveryRecord? {
    fun value(key: String): String? = validLanTxtValueOrNull(key, properties[key])

    val pidText = value(LanConstants.TXT_PEER_ID)
        ?.let(::validDiscoveryPeerIdOrNull)
        ?: return null
    val app = value(LanConstants.TXT_APP_ID) ?: return null
    if (app != expectedAppId.value || pidText == localPeerId.value) return null

    val protocolVersion = value(LanConstants.TXT_PROTOCOL_VERSION) ?: return null
    val fingerprint = properties[LanConstants.TXT_FINGERPRINT]?.let {
        value(LanConstants.TXT_FINGERPRINT) ?: return null
    }
    val security = validateLanDiscoverySecurityMetadata(
        profile = securityProfile,
        protocolVersion = protocolVersion,
        fingerprint = fingerprint
    ) ?: return null

    val name = properties[LanConstants.TXT_DEVICE_NAME]
        ?.let { value(LanConstants.TXT_DEVICE_NAME) ?: return null }
        ?: pidText
    if (name.isBlank()) return null

    val platformText = properties[LanConstants.TXT_PLATFORM]
        ?.let { value(LanConstants.TXT_PLATFORM) ?: return null }
    val platform = platformText
        ?.let { runCatching { Platform.valueOf(it) }.getOrNull() }
        ?: Platform.UNKNOWN

    val capabilitiesText = properties[LanConstants.TXT_CAPABILITIES]
        ?.let { value(LanConstants.TXT_CAPABILITIES) ?: return null }
    val supported = if (capabilitiesText == null) {
        setOf(TransportKind.LAN)
    } else {
        val tags = capabilitiesText.split(',')
        if (tags.size > MAX_LAN_CAPABILITY_TAGS) return null
        tags.mapNotNull { tag ->
            runCatching { TransportKind.valueOf(tag.trim()) }.getOrNull()
        }.toSet().takeIf { TransportKind.LAN in it } ?: return null
    }

    return ValidatedLanDiscoveryRecord(
        peerId = PeerId(pidText),
        deviceName = name,
        platform = platform,
        supportedTransports = supported,
        security = security
    )
}

/** Build one portable TXT map, failing before native/JmDNS registration. */
internal fun buildLanTxtProperties(
    peerId: PeerId,
    appId: AppId,
    deviceName: String,
    platform: Platform,
    supportedTransports: Set<TransportKind>,
    protocolVersion: Int,
    fingerprint: PeerFingerprint?
): Map<String, String> {
    fun requireField(key: String, value: String) {
        require(value.isNotBlank()) { "LAN TXT '$key' must not be blank" }
        require(value.isWellFormedLanText()) {
            "LAN TXT '$key' contains forbidden control characters or malformed Unicode"
        }
        require(lanTxtEntryFits(key, value)) {
            "LAN TXT '$key' exceeds the $MAX_DNS_SD_TXT_ENTRY_BYTES-byte entry limit"
        }
    }

    requireField(LanConstants.TXT_PEER_ID, peerId.value)
    requireField(LanConstants.TXT_APP_ID, appId.value)
    require(TransportKind.LAN in supportedTransports) {
        "A LAN advertisement must include the LAN transport capability"
    }
    require(deviceName.isWellFormedLanText()) {
        "LAN TXT '${LanConstants.TXT_DEVICE_NAME}' contains forbidden control characters or malformed Unicode"
    }
    val boundedName = truncateLanTxtValue(LanConstants.TXT_DEVICE_NAME, deviceName)
    requireField(LanConstants.TXT_DEVICE_NAME, boundedName)
    val capabilities = supportedTransports.joinToString(",") { it.name }
    requireField(LanConstants.TXT_CAPABILITIES, capabilities)

    return buildMap {
        put(LanConstants.TXT_PEER_ID, peerId.value)
        put(LanConstants.TXT_APP_ID, appId.value)
        put(LanConstants.TXT_DEVICE_NAME, boundedName)
        put(LanConstants.TXT_PLATFORM, platform.name)
        put(LanConstants.TXT_CAPABILITIES, capabilities)
        put(LanConstants.TXT_PROTOCOL_VERSION, protocolVersion.toString())
        fingerprint?.let { put(LanConstants.TXT_FINGERPRINT, it.value) }
    }.also { properties ->
        properties.forEach { (key, value) -> requireField(key, value) }
    }
}

internal fun lanTxtEntryFits(key: String, value: String): Boolean =
    key.encodeToByteArray().size + 1 + value.encodeToByteArray().size <=
        MAX_DNS_SD_TXT_ENTRY_BYTES

internal fun sanitizeLanDiagnostic(raw: String): String = buildString(
    minOf(raw.length, MAX_LAN_DIAGNOSTIC_CHARS)
) {
    var index = 0
    while (index < raw.length && length < MAX_LAN_DIAGNOSTIC_CHARS) {
        val character = raw[index]
        if (
            character.isHighSurrogate() &&
            index + 1 < raw.length &&
            raw[index + 1].isLowSurrogate()
        ) {
            if (length + 2 > MAX_LAN_DIAGNOSTIC_CHARS) break
            append(character)
            append(raw[index + 1])
            index += 2
        } else {
            append(
                if (character.isForbiddenLanControl() || character.isSurrogateCodeUnit()) {
                    '\uFFFD'
                } else {
                    character
                }
            )
            index++
        }
    }
}

private fun truncateLanTxtValue(key: String, value: String): String {
    val maximum = MAX_DNS_SD_TXT_ENTRY_BYTES - key.encodeToByteArray().size - 1
    if (value.encodeToByteArray().size <= maximum) return value
    var end = value.length
    while (end > 0) {
        if (end < value.length && value[end - 1].isHighSurrogate()) end--
        val candidate = value.substring(0, end)
        if (candidate.encodeToByteArray().size <= maximum) return candidate
        end--
    }
    return ""
}

private fun Char.isForbiddenLanControl(): Boolean {
    val value = code
    return value in 0x00..0x1F || value in 0x7F..0x9F ||
        value == 0x061C || value == 0x200E || value == 0x200F ||
        value in 0x202A..0x202E || value in 0x2066..0x2069
}

private fun String.isWellFormedLanText(): Boolean {
    var index = 0
    while (index < length) {
        val character = this[index]
        if (character.isForbiddenLanControl()) return false
        when {
            character.isHighSurrogate() -> {
                if (index + 1 >= length || !this[index + 1].isLowSurrogate()) return false
                index += 2
            }
            character.isLowSurrogate() -> return false
            else -> index++
        }
    }
    return true
}

private fun Char.isSurrogateCodeUnit(): Boolean = code in 0xD800..0xDFFF

internal const val MAX_DNS_SD_TXT_ENTRY_BYTES: Int = 255
private const val MAX_LAN_CAPABILITY_TAGS: Int = 32
private const val MAX_LAN_DIAGNOSTIC_CHARS: Int = 160
