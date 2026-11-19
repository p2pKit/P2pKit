package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore

/** Fixed diagnostic code only; never expose retained identities or authorize their removal. */
public class RpcPhoneCapacityTrustOccupied internal constructor() :
    Exception("Existing capacity approvals retained; verify earlier cleanup before retrying")

/** Refuse before allocation/import. An unreadable store is not an empty store. */
internal suspend fun requireEmptyMobileCapacityApprovals(trust: RpcTrustStore) {
    if (trust.load(RpcCapacityContract.appId, RpcTrustPurpose.HostClients).isNotEmpty()) {
        throw RpcPhoneCapacityTrustOccupied()
    }
}
