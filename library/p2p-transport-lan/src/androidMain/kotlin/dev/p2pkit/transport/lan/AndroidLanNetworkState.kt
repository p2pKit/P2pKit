package dev.p2pkit.transport.lan

import android.net.Network

/** Shared route ownership between Android LAN discovery and TCP dialing. */
internal class AndroidLanNetworkState {
    @Volatile
    private var selected: Network? = null

    fun selectedNetwork(): Network? = selected

    fun select(network: Network?) {
        selected = network
    }
}
