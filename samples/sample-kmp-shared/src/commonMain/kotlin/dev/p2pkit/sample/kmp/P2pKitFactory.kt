package dev.p2pkit.sample.kmp

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.PeerFingerprint

/**
 * Platform-agnostic factory for [P2pKit].
 *
 * Hides the only platform difference in v0.1: Android's LAN transport needs
 * a `Context`, JVM's does not. Each platform provides its own `actual`
 * implementation.
 *
 * Android consumers must call `initP2pKitAndroid(applicationContext)` from
 * their `Application.onCreate` before the first call to [createP2pKit].
 *
 * [authorization] defaults to fail-closed [PeerAuthorizationPolicy.RejectUnknown].
 * Applications that deliberately choose a weaker policy must pass it at the
 * call site and satisfy that policy's security opt-in themselves.
 */
public expect fun createP2pKit(
    appId: String,
    deviceName: String,
    authorization: PeerAuthorizationPolicy = PeerAuthorizationPolicy.RejectUnknown
): P2pKit

/**
 * Allowlist example: admit only these independently verified complete fingerprints.
 * An empty set denies all unpinned incoming peers. Discovery is not a source of trust.
 * JVM sample storage is in-memory per kit; production must supply durable secure storage.
 */
public fun createPinnedP2pKit(
    appId: String,
    deviceName: String,
    trustedFingerprints: Set<PeerFingerprint>
): P2pKit = createP2pKit(appId, deviceName, PeerAuthorizationPolicy.PinnedOnly(trustedFingerprints))
