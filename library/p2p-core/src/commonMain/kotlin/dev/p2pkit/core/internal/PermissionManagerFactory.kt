package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.permission.P2pPermissionManager

/**
 * Selects the default [P2pPermissionManager] for the current platform when
 * the host app does not supply its own via
 * [dev.p2pkit.core.dsl.P2pKitBuilder.permissionManager].
 *
 * - **Android LAN:** on device API 37+ with application target SDK 37+, reports
 *   [dev.p2pkit.core.permission.P2pPermission.LocalNetwork] and queries the live
 *   `ACCESS_LOCAL_NETWORK` grant. Other ordinary device/target combinations
 *   require no runtime LAN permission. The four normal LAN permissions still
 *   belong in the manifest, not a runtime prompt. Using the application context
 *   registered by `P2pKitAndroid.initialize(context)`, construction warns about
 *   missing normal declarations. Missing initialization retains the warned
 *   no-op fallback; it is not proof of a grant.
 * - **Android without LAN:** no-op; selected transport descriptors, not the
 *   platform alone, determine whether the default LAN policy applies.
 * - **JVM / iOS:** a no-op manager — plain LAN/mDNS needs no runtime
 *   permission grant on those platforms (iOS Local Network access is gated by
 *   the OS at first use, with no pre-check API to surface here).
 *
 * Query a provisioning sidecar's separate manager immediately before hotspot/
 * join operations; do not use it to over-gate base LAN. A custom LAN transport
 * using an exempt system-mediated picker must supply an explicit manager:
 * transport kind alone cannot describe that exemption.
 */
internal expect fun defaultPlatformPermissionManager(logger: P2pLogger, usesLan: Boolean): P2pPermissionManager
