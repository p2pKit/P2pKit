# RPC application samples: parity work

This is an **in-progress application layer**, not a completed discovery product or a new qualification pass.
Android, iOS and JVM use the same Kotlin contracts and request-history owner. The existing invitation,
organization-LAN policy, trust admission, deadlines and capacity harness remain intact during this migration.

## Shared application API

The interactive hosts register `users.get/v1`, `items.list/v1` and `message.send/v1` using
`RpcApplicationSession`. Clients on all three platforms offer the same five exercises: fetch a user,
list items, send a message, unknown-user business error, and invalid-user-ID validation error.
All records are synthetic. `message.send` acknowledges processing; it does **not** claim durable inbox
storage or delivery to another person. Echo remains available under diagnostics.

```kotlin
val app = RpcApplicationSession() // Keep for the window/model lifetime, independently of each role.
// Inside RpcHost.create's configuration, after supplying platform, AppId, LAN and protected trust store:
app.register(this, authorize = { peer -> peer.fingerprint != null })
// RPC itself additionally requires current durable trust; enrollment sessions cannot invoke procedures.

// On an already connected client:
val result = client.callWithDetails(RpcApplicationContract.getUser, UserQuery(123))
when (val reply = result.reply) {
    is RpcReply.Success -> showUser(reply.value)
    is RpcReply.ApplicationError -> showBusinessProblem(reply.error)
}
// result.requestId is the actual wire ID, also seen in the host's RpcCallContext.
// Catch RpcFailure separately; inspect kind, phase, requestId and executionEvidence.
```

The concrete shared API is in `samples/p2p-sample-rpc/src/commonMain/kotlin/dev/p2pkit/sample/rpc/`.
Android and JVM call Kotlin directly. Swift uses `RpcPhoneIos.createApplicationHost/Client` and the
owned `RpcPhoneLab.beginExample` cancellation bridge. Swift task cancellation alone is not Kotlin cancellation.
The public descriptors can also be used with application-defined typed request forms instead of the presets.
Read operations are idempotent; messages never opt into automatic reinvocation after ambiguous execution.

## Request data versus diagnostics

`RpcRequestHistory` retains at most 100 entries by default (configurable only up to 256), with two
1024-byte, Unicode-safe previews per entry. Active records are not evicted; when every slot is active,
additional history capture is declined and counted visibly, not the RPC. This is not the protocol's result-recovery cache.
History survives Stop while its app/window owner remains alive; it is deliberately not persisted to disk.
Clear completed history is an explicit privacy action. Starting another role does not recycle history IDs.
Open request details follow the same request as it completes. If its history entry is cleared or evicted,
the viewers drop the old data. All three platforms re-read by local history ID before copying and refuse stale
Copy actions; they never select a replacement row.

Host records currently cover entered example handlers, not pre-handler rejection or transport queue events.
A host `Succeeded` means the handler returned successfully, not that its client received the reply.
Client records distinguish business errors, RPC failures, timeout and cancellation. Cancelled calls must not
be read as rolled-back side effects; when the exact wire evidence is unavailable, the UI does not invent it.
Completed client replies expose actual wire IDs. Local pre-admission failures may have no wire ID.

Copy diagnostics excludes payloads, peer pins and request IDs. Copy details is a separate explicit action
including application data and bounded previews. Neither is automatic telemetry. Payloads can be private:
do not send details to an untrusted clipboard manager, cloud service or bug tracker.

## Remaining parity gates — not implemented or not yet verified

| Gate | Required work |
| --- | --- |
| Automatic networking | Select one eligible observed private LAN; retain policy and actual-socket/interface checks. Remove manual UI only once all adapters support the replacement. |
| Discovery | Expose fresh advisory Bonjour/mDNS records and policy-checked endpoints; support strict iOS opaque-endpoint resolution and Mac discovery. Never treat a device name/TXT record as authenticated identity. |
| First-use enrollment | A new explicitly enabled, bounded invitationless enrollment flow, host approve/reject and identity comparison. Do not broadcast an invitation secret or silently replace OOB authentication with TOFU. |
| Trusted reconnect | Persist the explicitly selected cryptographic host identity; TTL expiry, one reconnect owner, bounded backoff, cancellation and stale-generation rejection. Never choose the first advertised host. |
| Desktop persistence | Replace the deliberately ephemeral preview vault with protected durable identity/trust storage, including restart and failure tests. No plaintext vault key beside encrypted files. |
| Trust management | Equivalent online/offline lists and exact-pin revoke/forget behavior on both roles and all platforms. |
| Complete monitoring | Per-call queue/admission/cancellation events, lifetime outcome counters and custom editable request forms. |
| Cross-platform verification | Build/UI tests plus authenticated application exchanges in all nine host/client directions; loss/restart/revocation and approval rejection tests. Shared unit tests alone do not prove this matrix. |

The first-use discovery design must make its assurance explicit: an unauthenticated discovery record cannot
prove the intended host identity. Fingerprints must be compared through an independently trusted channel
or the UI must explicitly obtain informed first-use trust approval; silently treating mDNS as that channel
would weaken the current security model. Already-trusted reconnects must pin the saved cryptographic identity.

Intel, Android ART infrastructure qualification, sustained capacity and controlled physical-network campaigns
remain separate from these application changes. Existing failed runs remain historical evidence, not passes.
