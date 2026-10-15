@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import platform.darwin.kDNSServiceFlagsIncludeP2P
import platform.darwin.kDNSServiceFlagsLongLivedQuery
import platform.darwin.kDNSServiceInterfaceIndexAny

/** Query scope, not authority inferred from a DNS answer's cache/RR interface label. */
internal class IosLanTxtQueryScope private constructor(
    val interfaceIndex: UInt,
    val flags: UInt,
    private val stillCurrent: () -> Boolean
) {
    fun isCurrent(): Boolean = try { stillCurrent() } catch (_: Throwable) { false }

    companion object {
        val ordinary = IosLanTxtQueryScope(
            kDNSServiceInterfaceIndexAny.toUInt(),
            kDNSServiceFlagsIncludeP2P or kDNSServiceFlagsLongLivedQuery,
            { true }
        )

        /** Production supplies the original, already restricted NWParameters readback. */
        fun organization(verifiedIndex: () -> UInt): IosLanTxtQueryScope {
            val index = verifiedIndex()
            check(index in 1u..Int.MAX_VALUE.toUInt()) { "Organization TXT interface cannot be verified" }
            return IosLanTxtQueryScope(index, kDNSServiceFlagsLongLivedQuery) { verifiedIndex() == index }
        }
    }
}
