package dev.p2pkit.core.permission

/**
 * Permission manager for platforms/configurations with no preflight runtime
 * permission requirement.
 *
 * Reports no required permissions and treats every check as "granted". Apps
 * can provide another implementation through
 * [dev.p2pkit.core.dsl.P2pKitBuilder.permissionManager]. Core LAN uses only
 * install-time Android permissions; provisioning sidecars expose their own
 * runtime-permission managers and should be queried immediately around those
 * provisioning operations rather than used to over-gate core LAN features.
 */
public class NoOpP2pPermissionManager : P2pPermissionManager {
    override suspend fun requiredPermissions(): List<P2pPermission> = emptyList()
    override suspend fun missingPermissions(): List<P2pPermission> = emptyList()
    override suspend fun hasRequiredPermissions(): Boolean = true
}
