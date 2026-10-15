@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.rpc.internal

import kotlinx.cinterop.addressOf
import kotlinx.cinterop.convert
import kotlinx.cinterop.usePinned
import platform.Security.SecRandomCopyBytes
import platform.Security.errSecSuccess
import platform.Security.kSecRandomDefault

internal actual fun secureRpcBytes(size: Int): ByteArray {
    require(size in 1..64)
    return ByteArray(size).also { bytes ->
        bytes.usePinned {
            check(SecRandomCopyBytes(kSecRandomDefault, size.convert(), it.addressOf(0)) == errSecSuccess) {
                "RPC secure random source unavailable"
            }
        }
    }
}
