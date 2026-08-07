package dev.p2pkit.core.permission

/**
 * Default permission manager used when the host app does not supply one.
 *
 * Reports no required permissions and treats every check as "granted". Apps
 * that need stricter behavior (e.g., Android with `NEARBY_WIFI_DEVICES`)
 * should plug their own implementation in via the builder once that knob
 * exists; for v0.1 this no-op is sufficient because the LAN transport
 * doesn't require runtime permissions on the platforms we ship.
 */
public class NoOpP2pPermissionManager : P2pPermissionManager {
    override suspend fun requiredPermissions(): List<P2pPermission> = emptyList()
    override suspend fun missingPermissions(): List<P2pPermission> = emptyList()
    override suspend fun hasRequiredPermissions(): Boolean = true
}
