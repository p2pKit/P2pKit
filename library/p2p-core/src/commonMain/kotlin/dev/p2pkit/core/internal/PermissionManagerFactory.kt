package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.permission.P2pPermissionManager

/**
 * Selects the default [P2pPermissionManager] for the current platform when
 * the host app does not supply its own via
 * [dev.p2pkit.core.dsl.P2pKitBuilder.permissionManager].
 *
 * - **Android:** reports no runtime permissions — core LAN needs only
 *   normal install-time permissions (`INTERNET`, `ACCESS_NETWORK_STATE`,
 *   `ACCESS_WIFI_STATE`, `CHANGE_WIFI_MULTICAST_STATE`), which are
 *   auto-granted iff declared in the manifest and cannot be requested at
 *   runtime. Using the application
 *   context registered via `P2pKitAndroid.initialize(context)`, the factory
 *   emits a non-fatal warn at construction if any is missing from the
 *   manifest (a build-time mistake that otherwise shows up as silent
 *   zero-discovery). Falls back to a no-op manager (with a warn) if init was
 *   never called.
 * - **JVM / iOS:** a no-op manager — plain LAN/mDNS needs no runtime
 *   permission grant on those platforms (iOS Local Network access is gated by
 *   the OS at first use, with no pre-check API to surface here).
 *
 * Provisioning sidecars that need the hotspot/join runtime permissions ship
 * their own richer manager (e.g. `AndroidP2pPermissionManager`); apps wire it
 * in through the builder knob.
 */
internal expect fun defaultPlatformPermissionManager(logger: P2pLogger): P2pPermissionManager
