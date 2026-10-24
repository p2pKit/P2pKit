package dev.p2pkit.core

/**
 * Snapshot of optional, process-local known-route protection for an SDK session. It does not certify
 * network reachability or authorize other advertised endpoints. At most 64 eligible outgoing sessions
 * per kit retain a route independently of the untrusted discovery budget. Existing manual peers keep
 * their separate until-stop registration contract.
 *
 * Protection requires the original full application pin/PinnedOnly approval, or a currently Trusted
 * restricted profile. AcceptAny alone, enrollment and plaintext never earn protected priority.
 * A protected route lives only with its exact registered session and transport generation. Recovery
 * has at most 30 seconds of monotonic grace (or the shorter profile window); final close, replacement,
 * revocation, expiry and kit stop retire it. Live authorization is checked before promotion/use;
 * idle peer-list removal is reconciled by the existing registry eviction poll.
 */
public enum class ProtectedRouteStatus {
    /** Incoming, third-party/unsupported transport, or no usable exact outbound route was supplied. */
    Unsupported,

    /** The original session did not obtain the local authorization needed for scarce-route priority. */
    NotAuthorized,

    /** An eligible exact route is retained outside discovery admission for this live session. */
    Protected,

    /** All 64 route allowances were occupied. The otherwise-valid session is not rejected or closed. */
    CapacityUnavailable,

    /** The session's route was retired; stale capabilities cannot renew themselves. */
    Retired,
}
