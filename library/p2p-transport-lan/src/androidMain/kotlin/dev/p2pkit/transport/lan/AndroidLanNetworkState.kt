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
 * By default, [resolveCurrentTarget] is used when discovery has not published a
 * route, so manual LAN peers do not require advertising/discovery to be on.
 * The organization profile requires a fresh resolution for every route lookup.
 */
internal class AndroidLanNetworkState(
    private val requireFresh: Boolean = false,
    private val resolveCurrentTarget: (() -> AndroidLanBindTarget?)? = null
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
