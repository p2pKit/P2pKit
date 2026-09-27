package dev.p2pkit.transport.lan

import android.net.Network
import java.net.InetAddress

/** Immutable route snapshot shared by Android discovery and TCP dialing. */
internal data class AndroidLanDialRoute(
    val network: Network?,
    val localAddress: InetAddress,
    val fingerprint: String
)

/**
 * Shared route ownership between Android LAN discovery and TCP dialing.
 * [resolveCurrentTarget] is used only when discovery has not yet published a
 * route, so manual LAN peers do not require advertising/discovery to be on.
 */
internal class AndroidLanNetworkState(
    private val resolveCurrentTarget: (() -> AndroidLanBindTarget?)? = null,
    private val requireFresh: Boolean = false
) {
    @Volatile
    private var selected: AndroidLanDialRoute? = null

    fun selectedRoute(): AndroidLanDialRoute? =
        if (requireFresh) resolveCurrentTarget?.invoke()?.toDialRoute()
        else selected ?: resolveCurrentTarget?.invoke()?.toDialRoute()

    fun selectedNetwork(): Network? = selected?.network

    fun select(target: AndroidLanBindTarget) {
        selected = target.toDialRoute()
    }

    fun clear() {
        selected = null
    }

    private fun AndroidLanBindTarget.toDialRoute(): AndroidLanDialRoute =
        AndroidLanDialRoute(
            network = network,
            localAddress = address,
            fingerprint = fingerprint
        )
}
