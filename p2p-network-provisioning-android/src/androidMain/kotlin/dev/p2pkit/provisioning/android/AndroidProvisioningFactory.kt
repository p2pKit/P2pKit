package dev.p2pkit.provisioning.android

import android.content.Context
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.ProvisioningContext

/**
 * Provisioning factory for Android. Registered via
 * [dev.p2pkit.core.dsl.NetworkProvisioningConfigBuilder.android].
 *
 * Holds only the application context — not an Activity reference — so the
 * library never leaks a UI lifecycle. The host app supplies the runtime
 * permission flow; the library only reports what's missing via
 * [P2pKit.permissions] (the host wires [AndroidP2pPermissionManager]).
 */
public class AndroidProvisioningFactory(
    applicationContext: Context
) : NetworkProvisioningFactory {

    private val appContext: Context = applicationContext.applicationContext

    override fun build(context: ProvisioningContext): NetworkProvisioningManager =
        AndroidNetworkProvisioningManager(
            ctx = context,
            wifi = WifiManagerWrapperImpl(appContext)
        )
}
