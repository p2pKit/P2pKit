package dev.p2pkit.rpc.internal

import java.security.SecureRandom

private val rpcRandom: SecureRandom = SecureRandom()

internal actual fun secureRpcBytes(size: Int): ByteArray {
    require(size in 1..64)
    return ByteArray(size).also(rpcRandom::nextBytes)
}
