# RPC physical-session provenance and exact closure

This additive API is selected for the **unpublished `0.8.0-rc10` candidate** and
addresses [#531](https://github.com/p2pKit/P2pKit/issues/531).
It is not present in the immutable `0.8.0-rc8` artifacts. It supplements
[application-session authorization](application-session-authorization.md);
it does not replace credential verification or awaited login revocation. #531
is an integration requirement, not a reproduced security vulnerability.

## Capture at authentication

Use `registerScopedWithPhysicalSession()` when an application must associate a
verified login with the exact incoming authenticated connection:

```kotlin
registerScopedWithPhysicalSession(
    procedure = privateSale,
    authenticate = { connection, request ->
        val login = sessions.verifyCredential(connection.peer, request.credential)
        login?.let {
            // Application-owned association: retain this SDK capability, not a claimed ID.
            sessions.bindPhysicalSession(it, connection.physicalSession)
            RpcAuthorizationScope(it.rpcSession, request.saleId)
        }
    },
    authorize = { check ->
        sessions.isCurrentVerifiedLogin(check.peer, check.scope.session) &&
            sessions.mayUsePhysicalSession(
                check.scope.session,
                check.originalPhysicalSession,
                check.physicalSession,
                check.operation,
            ) && permissions.mayPerform(check.scope, check.operation)
    },
) { context, request ->
    val originalConnection = checkNotNull(context.physicalSession)
    sales.execute(checkNotNull(context.authorizationScope), originalConnection, request)
}
```

The example's `sessions`, `permissions` and `sales` are consumer-owned policy,
credential verification and business logic, not additional SDK APIs. Binding a
connection must not implicitly grant a different employee access to old work.

`RpcAuthenticationContext` is constructed from the incoming SDK link before the
authentication callback can suspend. `peer` is transport-authenticated;
`physicalSession` is an opaque `RpcPhysicalSession` capability. Compare capability
instances with `===`. Its immutable `generation` belongs to that session lifetime.
Incoming Host sessions do not reconnect in place: a reconnect is a new capability,
often with generation **1 again**. A peer fingerprint plus generation is therefore
not an exact-session key. Request bodies, discovery labels, request IDs, host
monitoring IDs and `RpcHost.connections` snapshots cannot construct or replace the
capability. There is no borrowed-kit injection or new wire protocol.

Existing `registerScoped()` registrations retain their behavior and now also get
physical provenance in authorization/handler contexts. Legacy device-only
`register()` handlers have a null `physicalSession`.

## Original connection versus operation connection

Both associations are immutable within each callback context:

| Callback / operation | `originalPhysicalSession` | `physicalSession` |
| --- | --- | --- |
| Authentication | Not a property of this context | Incoming connection captured before authentication |
| `Invoke`, `Execute` authorization | Original request connection | Original request connection |
| Handler | Use the handler's `physicalSession` | Original request connection |
| `Duplicate`, `Status`, `Cancel`, `Receipt` | Original retained request connection | Connection making this control/recovery request |
| `Success`, `ApplicationError`, `Failure`, `Running` | Original request connection | Actual selected output connection |
| `tryNotifyScoped()` | Null: independent notification has no inferred request origin | Actual selected destination |
| `tryNotifyScopedFrom(origin, ...)` | Explicit SDK capability supplied by the application | Actual selected destination |

Execution is host-owned and may outlive its original connection. `Execute` does
not imply that a reply will use that same connection. Disclosure authorization
is separate and sees the actual destination. The writer rechecks policy for the
same destination held by its queued ticket, then rechecks transport state,
generation, deadline, trust and the original login's revocation gate. A reconnect
during suspended policy cannot retarget the ticket.

For a notification arising from an earlier request, pass its captured connection
to `host.tryNotifyScopedFrom(origin, scope, notification, value, authorize)`.
The SDK requires the origin's authenticated peer to match the scope's peer. This
is an explicit application-selected association, not proof that a particular
request caused the notification; the application still checks its original login,
resource and physical-session policy. Plain `tryNotifyScoped()` supplies null
origin rather than pretending the current connection originated older work.

`isConnected` is a current observation of this exact lifetime, never a lookup of
the latest peer connection. It is not atomic check-and-act authorization. For
example, a strict policy can reject output unless original and destination are
the same permitted capability; other applications may allow a verified recovery
connection. The application chooses that policy explicitly. An old capability
never changes into the recovery connection.

## Close and await exactly the captured session

On an employee/policy transition that also requires physical retirement:

1. Await `host.revokeApplicationSession(oldLogin)` to fence that original login's
   admission, handler start and uncommitted output, and request cancellation of
   its host-owned work.
2. Await `capturedPhysicalSession.close()` for every application-associated
   lifetime that must be retired. No current-fingerprint lookup is performed.
3. Require confirmed closure before claiming physical cleanup. Clear private
   presentation and publish the new application state according to your policy.

`close()` seals that link and awaits the exact core session's cleanup. It leaves
other clients and a successor connection alone. It is safe to call from an RPC
callback: it does not join the calling RPC worker or host-owned handlers.
`closure` is a `StateFlow<RpcPhysicalSessionClosure>`:

- `Open`: no close transaction through this capability has begun. This alone
  does not prove the transport remains connected; inspect `isConnected`.
- `Closing`: physical teardown is in progress, not confirmed.
- `Closed`: the exact core session's cleanup completed successfully.
- `Incomplete`: teardown threw; the original exception is propagated. A terminal
  transport state by itself never becomes confirmed cleanup.

Concurrent calls serialize. A successful close is idempotent and releases the
capability's reference to its transport owner. An incomplete close retains that
exact owner so later calls reobserve its existing cleanup result/deadline; they
do not create a new timeout budget or promise that retry will succeed. Caller
cancellation cannot abandon owned cleanup. It can be reported when the call
returns, especially when closing from the reader callback itself; inspect
`closure` to distinguish confirmed completion from incomplete teardown.

Physical close alone does **not** revoke application authority, stop all
host-owned handlers, roll back effects, or retract already committed output.
Missing replies still carry conservative unknown execution outcomes. If cleanup
is incomplete, retain the failure and follow application recovery policy rather
than claiming that a replacement login is safe solely because the UI disconnected.

## Bounds and verification

There is one capability per existing SDK link, with no extra socket, worker,
timer or global capability directory. Scoped records retain the original through
the existing bounded retention window and charge an additional fixed allowance;
queued policy captures charge both physical associations. Unchanged record,
per-client, payload and notification limits remain in force. Applications own
and must bound any capabilities they retain outside the SDK.

Common deterministic regressions cover suspended authentication, original versus
recovery connections with colliding generation 1, all scoped control/disclosure
kinds, queued writer reconnection, explicit/absent notification origins, original
login revocation, and old-handle closure without closing another client or its
successor. `SessionRpcLink` regressions cover awaited concurrent closure, terminal
state before cleanup, retained failure/Error/cancellation, caller cancellation,
callback closure and resource drain. Existing scoped authorization and generation
fence tests continue to apply. These fixtures do not claim physical-device
capacity or qualification of a consumer's employee policy.
