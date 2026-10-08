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

If an authenticated host returns enrollment-only access to a previously trusted client, reconnect stops at
`RequiresApproval`. This does not identify why the host denied normal access. All three clients offer
**Request approval again** for that exact pin; only fresh local confirmation sends one enrollment attempt.
Our saved host identity is not erased or replaced, and authentication/storage failures never silently fall
back to first-use trust. A rejected or expired renewal is not retried automatically. Successful durable approval
restores the selected-host preference before normal pinned reconnect.

## Remaining parity gates — not implemented or not yet verified

| Gate | Required work |
| --- | --- |
| Automatic networking | Normal role startup selects one current eligible private LAN and an OS-assigned port on all three platforms. Manual settings remain only in explicit test/advanced flows. Native and device validation remains open. |
| Discovery | Shared advisory API and strict numeric TXT hints implemented; frontend lists/status implemented; verify native discovery/interoperability. Opaque-only Bonjour records are not silently resolved or dialed. |
| First-use enrollment | Opt-in shared protocol implemented; equivalent client-confirmation and host approve/reject dialogs implemented; validate actual exchanges. |
| Trusted reconnect | Shared selected-pin persistence/backoff/ownership implemented; frontends wired; validate real loss/restart/revocation behavior. Never choose the first advertised host. |
| Desktop persistence | Persistent encrypted POSIX profile implemented. Packaged normal-runtime Host → Client → Host and a second JVM process retained the same identity; profile locks and network owners closed. The actual Swing window also passed local Host/Client lifecycle and close checks. Trusted-peer reconnect remains open. Windows storage is not implemented. |
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

## Scoped Desktop Bonjour and local probe scope

The explicit source-pinned macOS ARM64 build now provides separate native TCP and Bonjour implementations.
System `DNSServiceRegister`, `DNSServiceBrowse` and `DNSServiceResolve` receive the selected positive
interface index and fixed `local.` domain. Browse/resolve callbacks must report that same index; registration
acknowledgement does not report one and is not misrepresented as packet egress. Secure-v2 numeric TXT hints
must match identity, SRV port and `OrganizationLan`; no hostname/default-route fallback is used. Ordinary
Java and unconfigured builds retain their original strict JmDNS topology checks. A configured native path
permits a startup attempt only; exact source/hash/architecture/ABI admission still applies.

At `232e7e99fce82ba33fb79bb3f1fa5ac4452b17c8` on Mac27/Xcode27, the real packaged Host started and
registered through Bonjour, then stopped with independently verified process/socket/store cleanup. A separate
local native-API check observed its own registration, browse add, exact SRV/TXT resolution and browse removal,
then closed all owned references. That API-only record was deliberately not an RPC-compatible host; it was
**not** rescue discovery or evidence for the application pairing gate. Neither local observation proves a
multicast packet crossed the Wi-Fi access point or reached another device.

The normal packaged runtime also completed Host → Client → Host twice in separate JVM processes using
one newly generated encrypted test profile. The same cryptographic identity survived role and process
restart, all role owners closed, and the profile lock released. No existing user profile, seeded trust,
remote approval or trusted reconnect was involved. Those remote behaviors remain separate device gates.

At `ee5ffa77e0fd88dfd70908a71ab5f511b0a1b016`, the source-pinned Desktop package passed 69 focused
Desktop tests and an actual Swing Host → Stop → Client → window-close check. Local status and role controls
were checked; 760- and 1000-pixel windows kept wrapped controls and dashboard cards inside their viewport.
Owned-window screenshots were inspected, and process/socket cleanup was independently verified. These were
fresh synthetic profiles, zero remote clients and no RPC calls: this is not a populated request-history,
first-use approval, trusted reconnect or cross-device presentation pass. The earlier clipped layout and
failed development/test-harness runs remain historical failures.

Deterministic native controls cover explicit scope, callback/frame bounds, policy rejection, overflow,
opaque-handle ownership and concurrent poll/close in strict and address/undefined-sanitizer builds.
The JNI contract suite uses the real source-pinned library. Browser state is bounded to 256 records/eight
pending resolves, validates fresh records, withdraws invalid/stale/predecessor admissions, and backs off
repeated callback failures. Close failure retains ownership rather than reporting successful cleanup.
None of these results explain or replace historical Java/Python `EHOSTUNREACH` failures.

The attempted `RpcDesktopApplicationReadinessMainKt --approved-local-application` probe at
`a8fae2af607dc1b89d0bd497d6da9d3eb3453649` failed at Host startup, before discovery, enrollment or calls.
A subsequent source-bound exception trace proved the TCP listener bound and JmDNS target selection rejected
before `JmDNS.create`. No multicast packet-delivery conclusion follows from that failure.
Separately, source review found that the planned same-Mac pairing/call stages could never qualify under
`OrganizationLan`'s deliberate self-address rejection. That invalid probe has been retired, not made to pass
by relaxing transport policy or relabeling its failed stages.

The replacement **different-scope** entrypoint is
`dev.p2pkit.sample.rpc.desktop.RpcDesktopAdvertisingReadinessMainKt`, accepting only
`--approved-local-advertising /absolute/empty/private-parent` and a verified source-matched native/classpath
package. It observes the eligible LAN, starts one fresh ephemeral Host through the real transport, checks
Running/Active, observes for five seconds, then closes and verifies its owned empty parent. It creates no
Client, approves nobody and opens no existing profile. A separate process/socket cleanup readback is required.
This covers **only local Host advertising lifecycle**, not successful multicast sends/announcements, peer
visibility, typed RPC, durable-profile restart or cross-platform interoperability. Failure remains failure.
It is never part of `check`; the older `--approved-local-host` entrypoint remains non-advertising.

Full application exchanges still require distinct permitted network endpoints. Shared deterministic tests,
Android host-JVM tests, Swift simulator checks and APK/framework/package verification cannot substitute
for that gate. All nine platform pairings, trusted reconnect/revocation and native active-role monitoring
remain explicitly open until observed on the respective endpoints.

## Next physical application test

Use two distinct permitted devices on the same eligible private LAN; USB/developer-control reachability
alone is not proof of LAN or multicast support. Install source-identified artifacts without uninstalling
the existing apps or clearing their protected identity/trust stores. Do not replace the LAN policy or force
a different interface to obtain a pass. Repeat this checklist for every claimed Host/Client platform pair.

1. Start **Host** on one device and **Client** on the other. Record each compiled-source ID. Confirm live
   advertising/discovery status and that the Host appears in the Client's nearby list without a pasted code.
2. Select that exact Host. Compare full fingerprints through an independently trusted channel and confirm
   first-use trust. Check the Host's pending popup; **Reject** must deny access. A new explicit attempt and
   **Approve** must reach **Ready** with matching saved identities on both devices.
3. Send `users.get` with ID `123`: expect `Demo user`. Send `items.list` with offset `0`, limit `20`:
   expect Notebook, Pen and Folder with total `3`. Send a short message to `123`: expect a receipt and
   accepted-character count, not a claim of durable message delivery.
4. Send user `999`: expect `UserNotFound`; send user `-1` or item limit `51`: expect `InvalidArgument`.
   Non-integer form input must be rejected locally. Inspect both request histories for procedure/version,
   known wire IDs, previews, elapsed time and distinct success/business/RPC failure states. Counters and
   open details must update without pressing Refresh. Copy diagnostics must omit application payloads.
5. Stop/restart each role and restart the applications without clearing their stores. The explicitly
   selected trusted Host must reconnect by fingerprint, never by first-discovered name/IP. Observe Host
   disappearance, offline status and bounded retries; a lost reply must not replay a message automatically.
6. Revoke/forget the peer. Normal RPC access must end; reconnect must require fresh explicit approval.
   Exercise cancellation while a call is active; if completion wins, record that race rather than claim a
   cancellation. Preserve ambiguous execution evidence. Stop/close both apps and verify owned cleanup.

Keep payload-bearing request details private and separate from sanitized diagnostics. Device runs must
retain their actual results and artifact identifiers; this checklist is not itself execution evidence.


### Simple workspace and approval presentation

All three apps keep role selection, nearby hosts and the three application examples prominent.
**Custom request**, **Error examples & echo**, **Activity & statistics**, **Trusted devices**,
**Request history (application data)** and **Diagnostics** expand on demand. **Device identity**
shows the full local fingerprint for comparison; folding a section does not stop a role, clear
saved trust or history, or approve a peer. Network failures remain visible without expanding details.
The samples remain English-only developer applications; translation and assistive-technology
qualification are not claimed by this layout change.

iOS presents identity decisions from the stable screen root, outside the virtualized Form rows.
Live updates cannot replace an open decision. Swipe dismissal is disabled; **Close** never approves
or rejects. If the exact request expires, disconnects or loses its owning role, the sheet stays open
with an explanation and disabled decision buttons. A busy host also disables decisions. Every actual
approval still rechecks the current runtime, request ID and fingerprint. No pairing deadline is
extended, and expiry does not trigger another approval attempt automatically. Use a new explicit
client request if necessary. The synthetic presentation regression does not establish the cause
of every physical-device lag or count as network qualification.
