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

Host records join captured engine admission/queue/finalization states with available handler previews.
A host `Succeeded` means the engine finalized a successful reply, not that its client received it.
Client records distinguish business errors, RPC failures, timeout and cancellation. Cancelled calls must not
be read as rolled-back side effects; when the exact wire evidence is unavailable, the UI does not invent it.
Completed client replies expose actual wire IDs. Local pre-admission failures may have no wire ID.

Copy diagnostics excludes payloads, peer pins and request IDs. Copy details is a separate explicit action
including application data and bounded previews. Neither is automatic telemetry. Payloads can be private:
do not send details to an untrusted clipboard manager, cloud service or bug tracker.

## Discovery and approval foundation

The opt-in `RpcPhoneLab.createNearbyApplicationHost/Client` factories share one implementation across
all platforms. Normal Android, iOS and Desktop screens use these factories. Explicit manual/capacity test paths retain their original factories.
`RpcPhoneSettings.automatic` accepts a platform-observed eligible private LAN and uses an ephemeral
listener port. It does not guess the interface, bypass `OrganizationLan`, or authorize a network itself.

`P2pKit.discoveryClaim` and `RpcClient.discoveredHosts` expose advisory snapshots, excluding stale,
unsigned, conflicting and manual-only records. Strict organization advertisements add optional numeric
`ip`/`port` TXT hints beside ordinary Bonjour SRV records. These are public routing hints, not secrets,
trust or DNS resolution. iOS validates them against its private-subnet policy before publishing; the
existing pre-dial, selected-interface, actual-socket and pinned-handshake checks still apply. Old opaque-only
Bonjour records remain undialable under that strict policy; there is no permissive fallback.

`RpcClient.requestApproval` uses the new bodyless wire kind only after informed local first-use confirmation.
The host must opt in to `allowNearbyPairing` and explicitly approve the authenticated fingerprint.
See the [protocol](protocol.md) for slot limits, expiry, cooldown and fresh-session requirements.
`RpcPairingRequest.origin` distinguishes nearby TOFU from invitation-secret enrollment.

The shared `RpcDiscoveryCoordinator` owns one cancellable/joinable worker. It persists **only the explicitly
selected host fingerprint** in a separate `SelectedHostPreference` namespace; that namespace never grants
RPC access. Discovery alone never chooses a host. Reconnect requires current durable `SelectedHosts` trust
and exactly one current discovery match. Missing/duplicate records show Offline/Ambiguous; revocation
requires new explicit approval. Retry waits are 1, 2, 4, 8, 16, then 30 seconds. Nearby clients disable the
separate core transport-reconnect owner. No request is replayed by this coordinator. Rejection/approval
timeout is not retried automatically. Android/iOS platform-protected stores keep the selection. Desktop now
has a persistent passphrase-unlocked profile; local restart/corruption/locking tests cover it, not a physical
reconnection campaign. All three screens show advisory discovery/presence, host Approve/Reject, informed
first-use selection, and exact-pin Revoke/Forget. Dismissing a dialog does not approve anything.

## Remaining parity gates — not implemented or not yet verified

| Gate | Required work |
| --- | --- |
| Automatic networking | Normal role startup selects one current eligible private LAN and an OS-assigned port on all three platforms. Manual settings remain only in explicit test/advanced flows. Native and device validation remains open. |
| Discovery | Shared advisory API and strict numeric TXT hints implemented; frontend lists/status implemented; verify native discovery/interoperability. Opaque-only Bonjour records are not silently resolved or dialed. |
| First-use enrollment | Opt-in shared protocol implemented; equivalent client-confirmation and host approve/reject dialogs implemented; validate actual exchanges. |
| Trusted reconnect | Shared selected-pin persistence/backoff/ownership implemented; frontends wired; validate real loss/restart/revocation behavior. Never choose the first advertised host. |
| Desktop persistence | Persistent encrypted POSIX profile implemented with restart, wrong-password, corruption, exclusive-lock and unsafe-path tests. Actual packaged-app restart validation remains open; Windows storage is not implemented. |
| Trust management | Equivalent presence lists and exact-pin revoke/forget wired on both roles and all platforms; validate actual disconnect and re-approval exchanges. |
| Complete monitoring | Editable typed forms implemented on all three. Bounded host admission/queue/outcome capture and independent host/client lifetime counters implemented; native presentation and interoperability checks remain open. |
| Cross-platform verification | Build/UI tests plus authenticated application exchanges in all nine host/client directions; loss/restart/revocation and approval rejection tests. Shared unit tests alone do not prove this matrix. |

The first-use discovery design must make its assurance explicit: an unauthenticated discovery record cannot
prove the intended host identity. Fingerprints must be compared through an independently trusted channel
or the UI must explicitly obtain informed first-use trust approval; silently treating mDNS as that channel
would weaken the current security model. Already-trusted reconnects must pin the saved cryptographic identity.

Intel, Android ART infrastructure qualification, sustained capacity and controlled physical-network campaigns
remain separate from these application changes. Existing failed runs remain historical evidence, not passes.

## Desktop profile and unlock

The normal Desktop window opens `~/.p2pkit-rpc-desktop` only after a local profile-passphrase prompt.
Use a separate strong 12–128-character passphrase, **not the computer login password**. PBKDF2-HMAC-SHA256
(600,000 iterations, random 16-byte salt) derives a 256-bit key; existing bounded AES-GCM vault records
bind their namespace as authenticated data. Only the salt/version header and encrypted records are persisted.
The profile is owner-only, POSIX-only, rejects symlinks, and holds an exclusive process lock. Unlock failures
never erase/recreate existing identities. Incomplete initialization or corruption fails closed and needs
owner review of the retained files; there is no automatic password recovery or reset.

Stop closes the network role but preserves the unlocked profile for another role. Window close closes the
role before releasing the profile and clearing its in-memory key best effort. Restart requires unlocking
again, but not re-pairing. This is a sample encrypted-file profile, **not an OS-backed desktop keystore**;
Android Keystore and iOS device-only Keychain remain platform-specific implementations. Windows lacks this
POSIX storage implementation and must not be claimed as equivalent or release-ready.

## Editable application requests

Each normal client screen has the same `users.get`, `items.list`, and `message.send` forms, plus presets.
`RpcApplicationInput.parse` bounds input, validates only fields used by the selected procedure, and rejects
malformed/overflowing integer input locally. Validly encoded business-invalid input (for example user ID
`-1`, missing user `999`, or item limit `51`) reaches the same typed host handler and returns a structured
business error. `RpcPhoneLab.beginRequest` uses the existing bounded call/cancellation/history path.
Neither connection selection nor trusted reconnect replays application requests.

The iOS UI rejection tests use a DEBUG-only **unavailable-network** observer. It can deny networking only;
it cannot manufacture a network, discovered device, approval or successful RPC. Those UI results are not
native discovery or physical interoperability evidence.

## Engine outcomes and history

All three dashboards use `RpcMetricCard`: admitted requests, active/queued calls, succeeded, business errors,
RPC failures, cancelled, timed out, refused attempts and omitted metadata captures. Totals are for the current
role runtime, including diagnostic calls; **refused attempts are not additional admitted logical calls**.
Retries/status recovery do not increment admitted calls twice. Client success means a decoded reply was
observed locally, not that a later application consumer necessarily received it before cancellation.

`RpcHostConfiguration.requestHistoryCapacity` is opt-in (default zero, maximum 256); application hosts use 100.
Each retained metadata slot charges a conservative 4096-byte allowance to the existing host payload budget.
At capacity, terminal slots can be replaced but active slots cannot. Missing memory/capture capacity drops
metadata, not RPC work; counts remain independent. No payload is copied into core monitoring or diagnostics.
The bounded recorder does not enumerate the 131072-entry deduplication table. Stop clears engine metadata
and releases its allowances; late non-cooperative handlers retain their existing execution ownership.

The sample joins handler previews to observed engine state using host lifetime, stable capture identity, authenticated fingerprint and
wire request ID. Handler return alone is not recorded as RPC success: encoding, cancellation or finalization
may still fail. Queued/pre-handler failures are visible without inventing decoded payloads. Refused invocation
attempts are distinct from an earlier admitted call with the same ID. History remains bounded across Stop;
if metadata capture is unavailable, handlers do not create permanently active preview rows.
If Stop races the final observation, the retained row explicitly says `HostStoppedOutcomeUnobserved`, not
successful rollback or delivery. Clearing completed history does not reimport unchanged engine snapshots.

`RpcClient.callWithObservation` accepts a caller-owned single-use `RpcCallObservation`. Its conflated flow
exposes the actual wire ID, selected pin, host lifetime, local queue/send/recovery stages, elapsed time and
execution evidence before the final reply. It adds no timer, callback, request replay or background worker.
The sample binds at most eight live observers to exact local history IDs and reads them on its existing
500 ms status tick. Client **In-flight calls** includes the **Local send queue**; do not sum those counters.
Cancelling a queued ticket seals transmission before terminal evidence is published. If sending won that
race, the outcome is conservative (`MayHaveExecuted`), not a promise of rollback. Completed replies and local
preview errors retain known IDs/evidence. Native active-role presentation validation remains open. The current protocol's `Running` response does not distinguish remote queued from executing;
the client must not infer that distinction from a counter or silence.
