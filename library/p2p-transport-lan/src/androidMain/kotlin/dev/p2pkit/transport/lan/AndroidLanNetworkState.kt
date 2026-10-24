package dev.p2pkit.transport.lan

import android.net.Network
import java.net.InetAddress

/** Immutable route snapshot shared by Android discovery and TCP dialing. */
internal data class AndroidLanDialRoute(
    val network: Network?,
    val localAddress: InetAddress,
    val fingerprint: String,
    val revision: Long = 0
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
    private val routeLock = Any()
    @Volatile private var selected: AndroidLanDialRoute? = null
    private var observed: AndroidLanDialRoute? = null
    @Volatile var routeRevision: Long = 0
        private set

    fun selectedRoute(): AndroidLanDialRoute? = synchronized(routeLock) {
        val current = if (requireFresh) resolveCurrentTarget?.invoke()?.toDialRoute()
        else selected ?: resolveCurrentTarget?.invoke()?.toDialRoute()
        if (!sameContext(current, observed)) routeRevision += 1
        observed = current
        current?.copy(revision = routeRevision)
    }

    fun selectedNetwork(): Network? = selected?.network

    fun select(target: AndroidLanBindTarget) = synchronized(routeLock) {
        val current = target.toDialRoute()
        if (!sameContext(current, observed)) routeRevision += 1
        selected = current
        observed = current
    }

    fun clear() = synchronized(routeLock) {
        // Invalidate even if the next fresh lookup rediscovers the same route (network ABA).
        routeRevision += 1
        selected = null
        observed = null
    }

    private fun sameContext(left: AndroidLanDialRoute?, right: AndroidLanDialRoute?): Boolean = when {
        left == null || right == null -> left == right
        else -> left.network == right.network && left.fingerprint == right.fingerprint &&
            left.localAddress.lanNumericAddress() == right.localAddress.lanNumericAddress()
    }

    private fun AndroidLanBindTarget.toDialRoute(): AndroidLanDialRoute =
        AndroidLanDialRoute(
            network = network,
            localAddress = address,
            fingerprint = fingerprint
        )
}
