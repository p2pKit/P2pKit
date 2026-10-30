package dev.p2pkit.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.rpc.internal.RegisteredProcedure
import dev.p2pkit.rpc.internal.registeredProcedure
import dev.p2pkit.rpc.internal.registeredScopedProcedure
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

    /**
     * Explicit opt-in to invitationless first-use approval. Unknown authenticated peers get only
     * EnrollmentOnly admission, never RPC access. The local administrator must check the fingerprint
     * and approve. A discovery name is not a verified real-world identity. Defaults to invitation-only.
     */
    public var allowNearbyPairing: Boolean = false

    /** Opt-in local metadata inspection, 0 (disabled) to 256 entries. Charged to the existing payload budget. */
    public var requestHistoryCapacity: Int = 0
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

    /**
     * Opt-in application-session isolation without changing the RPC wire or existing registrations.
     * Authenticate validates the typed request's application credentials and returns immutable facts;
     * RPC itself never treats a request-body employee/session claim as authenticated. Return the same
     * RpcApplicationSession instance for one verified login, with a bounded per-request resource.
     *
     * Authorize is deny-by-default and freshly checks the ORIGINAL scope before execution, duplicate/
     * status/cancel/receipt handling, and success/error/bodyless output, including at writer commitment.
     * Both callbacks must be fast and cancellation-cooperative; the owned five-second bound and shorter
     * request allowance still apply. Revoke and await the original session before switching employees.
     * Already committed output/business effects need application presentation cleanup and recovery.
     */
    public fun <Q, R, E> registerScoped(
        procedure: RpcProcedure<Q, R, E>,
        authenticate: suspend (PeerIdentity, Q) -> RpcAuthorizationScope?,
        authorize: suspend (RpcAuthorizationContext) -> Boolean = { false },
        handler: suspend (RpcCallContext, Q) -> RpcReply<R, E>,
    ) {
        require(procedure.key !in procedures) { "Duplicate procedure descriptor" }
        procedures[procedure.key] = registeredScopedProcedure(procedure, authenticate, authorize, handler)
    }
}

public class RpcClientConfiguration internal constructor() : RpcConfiguration() {
    /** Disable when an application owns fresh-discovery reconnect; never run two reconnect owners. */
    public var transportReconnect: Boolean = true
}
