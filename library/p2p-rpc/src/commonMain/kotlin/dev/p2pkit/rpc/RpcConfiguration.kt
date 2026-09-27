package dev.p2pkit.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.rpc.internal.RegisteredProcedure
import dev.p2pkit.rpc.internal.registeredProcedure
import dev.p2pkit.transport.lan.OrganizationLan

/** No raw P2pKit/security/transport customization that could bypass the RPC profile. */
public open class RpcConfiguration internal constructor() {
    public var appId: AppId? = null
    public var lan: OrganizationLan? = null
    public var trustStore: RpcTrustStore? = null
    public var limits: RpcLimits = RpcLimits.host128()
    internal val notifications: MutableMap<String, RpcNotification<*>> = mutableMapOf()

    /** Register before runtime creation. Unknown notifications are not implicitly decoded or subscribed. */
    public fun <T> notification(notification: RpcNotification<T>) {
        require(notification.key !in notifications) { "Duplicate notification descriptor" }
        notifications[notification.key] = notification
    }
}

public class RpcHostConfiguration internal constructor() : RpcConfiguration() {
    /** Disable on mDNS-filtered networks and share the policy-checked numeric endpoint out of band. */
    public var advertise: Boolean = true
    internal val procedures: MutableMap<String, RegisteredProcedure> = mutableMapOf()

    /**
     * Authorization is deny-by-default, rechecked for results, and must be fast/cancellation-cooperative.
     * Exceptions or an owned five-second timeout deny access; first admission also honors the shorter
     * remaining request budget. The host runtime owns handler jobs, not the incoming session.
     */
    public fun <Q, R, E> register(
        procedure: RpcProcedure<Q, R, E>,
        authorize: suspend (PeerIdentity) -> Boolean = { false },
        handler: suspend (RpcCallContext, Q) -> RpcReply<R, E>,
    ) {
        require(procedure.key !in procedures) { "Duplicate procedure descriptor" }
        procedures[procedure.key] = registeredProcedure(procedure, authorize, handler)
    }
}

public class RpcClientConfiguration internal constructor() : RpcConfiguration()
