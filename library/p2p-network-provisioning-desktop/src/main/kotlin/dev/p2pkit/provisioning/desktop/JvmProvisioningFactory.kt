package dev.p2pkit.provisioning.desktop

import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.ProvisioningContext

/**
 * Provisioning factory for JVM desktop. Registered via
 * [dev.p2pkit.core.dsl.NetworkProvisioningConfigBuilder.jvm].
 */
public object JvmProvisioningFactory : NetworkProvisioningFactory {
    override fun build(context: ProvisioningContext): NetworkProvisioningManager =
        JvmNetworkProvisioningManager(ctx = context)
}
