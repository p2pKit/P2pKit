# RPC application-session authorization

This is an **opt-in contract** for applications where employees share one trusted
phone, tablet or workstation. Device authentication alone does not authenticate
the employee. `register()` and `tryNotify()` remain device-level APIs; registering
a handler that checks an employee only at handler entry does not protect later
retained or queued replies. Private routes should use `registerScoped()` and
`tryNotifyScoped()`.

These APIs are new source functionality, not functionality supplied by the
previously published `0.8.0-rc7`. Consume matching official Core/LAN/RPC versions
that include this contract before deploying it; a source test is not publication
or qualification of a consumer's employee boundary.

## Validate credentials and capture the original login

The application validates credentials in its typed, bounded request. RPC never
accepts a request-body principal/session string as proof of authentication. Keep
one `RpcApplicationSession` instance for one verified login. A later login must
get a **new instance**, even if employee or session identifier strings repeat.
Bind it to `PeerIdentity.fingerprint` from the authenticated encrypted transport,
not to an address or a claimed fingerprint in the request.

Example application code (the credential verifier and permissions are yours):

```kotlin
registerScoped(
    procedure = privateSale,
    authenticate = { peer, request ->
        val login = sessions.verifyCredential(peer, request.credential)
        login?.let { RpcAuthorizationScope(it.rpcSession, request.saleId) }
    },
    authorize = { check ->
        val login = check.scope.session
        sessions.isCurrentVerifiedLogin(check.peer, login) &&
            permissions.isEnabled(login.principal) &&
            permissions.mayPerform(login, check.scope.resource, check.operation)
    },
) { context, request ->
    val original = checkNotNull(context.authorizationScope)
    sales.executeFor(original.session.principal, original.resource, request.operationId)
}
```

`principal`, `sessionId` and `resource` are immutable, bounded metadata (up to
256 characters each, no ASCII controls). They are **not bearer credentials**.
Use opaque nonsecret identifiers; do not put tokens/passwords in them or log the
request/context fields. Session/scope/context `toString()` omit authorization
identifiers, but explicitly reading their properties still reveals application
data. A positive optional session `lifetime` expires monotonically and cannot be
renewed; create a new login instead. No thread/connection/timer is allocated per
application session.

A scoped request captures its exact original login/resource before admission.
Dedup records, result bodies, bodyless running/failure responses, original
asynchronous output and queued tickets retain those facts. Reconnect does not
replace them with the employee currently using the same device. Duplicate
invocations and digest-only status/cancel/receipt controls never reauthenticate
an existing request as a new employee.

## Fresh policy, bounded work, conservative outcomes

The scope-aware callback runs before admission and execution; before
`Duplicate`, `Status`, `Cancel` and `Receipt`; and for `Success`,
`ApplicationError`, `Failure`, `Running` and `Notification` disclosure. The owned
writer checks again immediately before committing queued scoped output. A
control permission is not automatically permission to disclose its outcome.
Default authorization denies everything, including disclosure.

Authentication and policy callbacks must be fast and cancellation-cooperative.
Each has an owned five-second maximum wait; initial authentication/admission and
handler-start checks also honor the shorter remaining request deadline. A
callback exception/timeout never grants access. A noncooperative callback or
handler cannot be forcibly freed or rolled back; its actual owner keeps resources
until it exits. Typed authentication decoding, retained authorization metadata,
result bodies and queued authority are charged to the existing bounded shared
budget. `host128()`, `host256()`, the wire, per-client limits and defaults do not
change.

Revoked/expired scope or policy denial may suppress **all** application output,
including bodyless failures. Missing/expired scoped control records also remain
silent: digest-only controls supply no verified original application authority.
The caller may therefore time out with an uncertain execution outcome. Generic
pre-authentication refusal contains only the caller's request/procedure metadata;
failed application authentication or a prohibited scoped reinvocation flag is
conservatively `AccessRevoked` (`MayHaveExecuted`) because another invocation
may race admission of that ID.
Never infer rollback, nonexecution or successful cancellation from silence.
Malformed protocol input still fails the existing protocol checks; physical
connection-generation fencing remains in force.

## Order employee transitions against commitment

Before switching the device's current employee, disabling/revoking a login, or
publishing an incompatible permissions transition:

1. `await host.revokeApplicationSession(oldLogin)` (in Kotlin, call the suspending
   method and let it return). This irreversibly fences the original session,
   then requests cancellation of that host's matching owned queued/running work.
   It does not revoke the device trust grant or close its shared connection.
2. Clear private presentation, subscriptions and application-held response data.
3. Publish the new employee/policy state and, after genuine credential validation,
   create a new application-session instance.

`oldLogin.revoke()` provides the same irreversible admission/start/output fence
without requesting host cancellation. Use it to fence a shared session across
multiple host instances, then cancel each owner's work as appropriate. Expiry
also prevents new commitments; it is not a background task that promises immediate
cancellation of already-started business effects. Disable/current-resource policy
belongs in the fresh authorizer; use awaited revocation for atomic transitions.
RPC cannot independently detect that the remote employee changed.

A short session mutex orders revocation/expiry against admission, handler-start
commitment and the writer's `SendTicket.begin()` transaction. **No application
callback or network I/O runs under it.** If revocation wins, an uncommitted scoped
ticket cannot start. If commitment wins, that output may finish **after** revocation
returns. Commitment is local ticket start, not actual socket delivery, remote
receipt or presentation. Data already committed/delivered and business effects
already started cannot be retracted. Do not promise an instantaneous deletion of
information from the shared device.

## Private notifications and recovery

```kotlin
host.tryNotifyScoped(
    RpcAuthorizationScope(verifiedLogin.rpcSession, saleId),
    saleChanged,
    update,
) { check -> permissions.mayReceive(check.peer, check.scope) }
```

The original scope is explicit and deny-by-default policy is checked before
encoding and at writer commitment. `Enqueued` means local bounded acceptance,
not later policy approval or receipt. Legacy `tryNotify()` intentionally stays
device-only; do not use it for employee-private updates.

Transport results remain bounded, in-memory and host-incarnation-specific. The
application owns durable operation IDs/transactions and business recovery. A
fresh authenticated lookup after a later login uses a new RPC request and fresh
application policy; while the original record remains retained, reusing its request ID cannot adopt a
new employee. After bounded record expiry, a new invocation with that ID can be
admitted under fresh validated credentials; RPC IDs are not durable business
idempotency keys.
Do not reexecute a potentially committed business operation merely because old
scoped output was suppressed or its result expired.

## Verification scope

Deterministic common tests exercise delayed success/application error, zero-cache
original output, retained/status/duplicate/receipt/cancel isolation, queued
cancellation/deadline failures, reconnect, revocation/expiry/policy changes,
competing admission grants, callback timeout/Error cleanup, notifications and
noncooperative ownership. Actual `SessionRpcLink` writer tests cover suspension
followed by revoke/expiry/generation/disconnect/trust changes, a dequeued ticket's
cleanup and commitment-wins network I/O.

These checks prove the library mechanism under their stated fixtures. They do
not authenticate a real employee, qualify a POS policy, establish physical
mobile capacity, or replace the pending installed-Windows/physical-device tests.
