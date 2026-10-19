package dev.p2pkit.transport.lan

/** Android NDK socket/accept4 only; no private FileDescriptor fields or hidden Android APIs. */
internal object AndroidNativeSockets {
    init { System.loadLibrary("p2pkit_lan_sockets") }

    // Nonnegative descriptor or negative errno. Both creation calls set flags atomically.
    external fun open(ipv6: Boolean): Int
    external fun accept(listener: Int): Int
    external fun verifyFlags(descriptor: Int): Int
    external fun closeUnowned(descriptor: Int): Int
}
