package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.profile.WindowsProfileTerminalClose

/**
 * Final Windows application-exit policy, not RPC Stop/Back or permission to load a native profile provider.
 * [conceal] must synchronously hide private UI. [retireAllOwners] runs on one worker and must join all actual
 * application owners. Success exits with code 0; failure or a 30-second deadline halts with code 125.
 * The watchdog remains armed through JVM shutdown hooks. Construction does not schedule work or exit.
 */
public class DesktopRpcTerminalExit(conceal: () -> Unit, retireAllOwners: () -> Unit) {
    private val owner = WindowsProfileTerminalClose.forApplication(conceal, retireAllOwners)

    /** One application-exit admission; duplicate requests do not create workers, retries or timers. */
    public fun requestApplicationExit(): Boolean = owner.requestApplicationExit()
}
