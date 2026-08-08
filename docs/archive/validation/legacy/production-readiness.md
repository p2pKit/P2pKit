# P2pKit Production Readiness — Design Doc (v0.3.0+)

Status: **partially implemented** *(updated 2026-06)*. §3 (transport lifecycle)
and §4 (path-change recovery) shipped in v0.4 — `suspend fun start(): Result<Unit>`
on the transports, `NetworkPathObserver` with Android/iOS impls, iOS path monitor +
listener rebind. §2 (backoff + jitter), §5 (`IosBackgroundTaskGuard`), and §6
(foreground-service sample) remain unimplemented proposals. Builds on existing
`ReconnectPolicy`, `BackgroundPolicy`, and `SessionManager`; no API breakage,
only new opt-in behaviour. "Today" snapshots below are kept as written at
proposal time, with per-section status notes.

## 1. Goals & non-goals

**Goals.** Survive realistic LAN events without user intervention: transient
Wi-Fi drops, network handover (Wi-Fi → Wi-Fi, Wi-Fi → hotspot), OS-suspended
apps, screen-off Doze on Android. Keep sessions through ≤ 30 s outages.

**Non-goals.** Process-death session restoration, NAT traversal, relay, and
cross-LAN reachability. `AppKilledPolicy` stays `NoPersistenceForMvp`. New
peers go through full discovery plus the authenticated-v2 handshake and
authorization policy.

## 2. Reconnect strategy

*Status: still proposed — `ReconnectPolicy.Enabled` remains fixed-delay as of
v0.7. Note one part of the "Today" snapshot has since improved: `V0.4-RECONNECT`
replaced the captured-`InternalPeer` reuse with per-attempt endpoint
re-resolution from fresh discovery data.*

**Today.** `ReconnectPolicy.Enabled(maxAttempts, retryDelayMillis)` — fixed
delay, outgoing-only, reuses the captured `InternalPeer`. Exhaustion → `Failed`.

**Change.** Replace fixed delay with **exponential backoff + jitter**:

```
delay(n) = min(baseDelay × 2^n, maxDelay) + uniform(0, baseDelay)
```

with `baseDelay = 500 ms`, `maxDelay = 8 s`, `maxAttempts = 8` defaults
(≈ 30–60 s budget end-to-end). Field stays binary-compatible: rename
`retryDelayMillis` → `baseDelayMillis` semantically; add optional `maxDelayMillis`,
`backoffMultiplier`, `jitterFraction`. **Incoming sessions** become eligible
for reconnect when the policy is `Enabled` AND the local side initiates a
"reconnect probe" (see §4) — otherwise still rely on remote redial.

## 3. Transport / session lifecycle ownership

*Status: **implemented in v0.4.** `IosLanDataTransport` now exposes
`override suspend fun start(): Result<Unit>`; listener bind failures surface
as typed errors instead of crashing the kit factory.*

**Today (at proposal time).** `SessionManager` owns sessions; transports own
`DataTransport` + `DiscoveryTransport`; `IosLanDataTransport.init` binds the
listener synchronously; `nw_listener_create` failure throws and crashes the kit
factory (no `@Throws` bridge to ObjC).

**Change.** Three rules:

1. **Transports never crash the kit.** Move blocking I/O out of `init`
   into a `suspend fun start()` returning `Result<Unit>`. The kit factory
   either returns a started transport or surfaces a typed
   `P2pError.TransportStartFailed`. Sample apps already display this.
2. **Session lifetime owned exclusively by `SessionManager`.** Transports
   emit raw connection events; SessionManager decides Connected /
   Reconnecting / Failed. Transports do NOT re-emit "session closed."
3. **One reconnect loop per session.** Lives in `SessionManager`, not in
   `IosRawConnection` / `JvmRawConnection`. Backoff state is per-session,
   cancelled on `session.close()` and on `kit.stop()`.

## 4. NWPathMonitor / ConnectivityManager recovery

*Status: **implemented in v0.4.** `NetworkPathObserver` exists with Android
(`ConnectivityManager.NetworkCallback`) and iOS (`nw_path_monitor`) impls;
`SessionManager` reacts via `pathSatisfiedSignal`, and the iOS transport rebinds
its listener on path/interface changes (`startPathMonitor`).*

**Today (at proposal time).** Neither platform reacts to path changes for
active sessions. A Wi-Fi reconnect can rotate the local IP without us noticing
until a keep-alive PING times out (≈ 30 s).

**Change.** Add a new internal interface `NetworkPathObserver` with two
impls:

- **iOS** (`appleMain`): `nw_path_monitor_create` on `dispatch_queue_create`
  emits `PathChanged(status: satisfied|unsatisfied, isExpensive, …)`.
- **Android** (`androidMain`): `ConnectivityManager.NetworkCallback` on
  the system's default network with `NetworkRequest.Builder().addCapability(INTERNET)`.
- **JVM desktop**: no-op; relies on keep-alive only.

`SessionManager` subscribes once. On `status = unsatisfied`, mark all
connected sessions `Reconnecting` immediately (don't wait for PING).
On `status = satisfied` (post-handover), trigger one immediate retry per
reconnecting session, then resume backoff. Local listener rebinds when
the path's interface set changes.

## 5. iOS background-task handling

*Status: still proposed — `IosBackgroundTaskGuard` does not exist in the tree.*

**Today.** `notifyAppBackgrounded` applies `BackgroundPolicy`. With
`KeepRunning`, NWConnection survives ≤ a few seconds before iOS suspends
the process; sessions die silently. With `CloseActiveSessions`, the user
loses room state on every screen lock.

**Change.** Only relevant when `BackgroundPolicy.KeepRunning`. Sample app
(not SDK) calls `UIApplication.shared.beginBackgroundTask(...)` on
`scenePhase → .background` and ends it on `.active`. **SDK provides a
helper** `IosBackgroundTaskGuard(kit:)` so consumers don't have to
re-implement it. Expected behaviour: ~30 s grace period from iOS; after
that the OS suspends and sessions tear down. **Document the limit** —
this is not a workaround for true background networking, which iOS
doesn't allow third-party apps without a VoIP/Audio entitlement.

## 6. Android foreground-service behaviour

*Status: still proposed — no `P2pKitForegroundService` ships in the sample yet.*

**Today.** Android sample is a single Activity. When backgrounded with
`KeepRunning`, the OS can kill the process at any time; Doze freezes
CPU on the screen-off path.

**Change.** Provide a sample-level (not SDK) **`P2pKitForegroundService`**
in `p2p-sample-android`. Documents the production pattern:
`startForegroundService` with a `Notification` of type
`FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE` (API 34+). SDK contribution:
a `P2pKit.ongoingSessionsNotificationContent: StateFlow<NotificationContent>`
the service can observe to keep the notification text accurate ("Connected
to 3 peers"). Manifest must declare `FOREGROUND_SERVICE_CONNECTED_DEVICE`
permission and the matching service type.

## 7. Retry / backoff expectations (summary)

| Trigger | Initial reaction | Retry pattern | Cap |
|---|---|---|---|
| PING timeout (30 s default) | → `Reconnecting` | exp backoff + jitter | `maxAttempts` |
| Path `unsatisfied` (§4) | → `Reconnecting` immediately | wait for `satisfied`, then 1 attempt, then backoff | `maxAttempts` |
| User `session.close()` | → `Closed` (`Closing` is reserved in `ConnectionState` but never entered) | none | — |
| Remote `CLOSE` frame | → `Closed` | none | — |
| Transport start failure (§3) | kit factory returns failure | none — caller decides | — |

## 8. State restoration expectations

**v0.3.** No persistence. After process death, peers re-discover, sessions
reopen. Sample apps already accept this (`AppKilledPolicy.NoPersistenceForMvp`).

**v0.4 (not in this milestone).** Optional persistent `localPeerId` in
`SharedPreferences` / `NSUserDefaults` so peers don't show "new device" on
every relaunch. Out of scope here.

## 9. Open questions for review

1. **Backoff defaults** — is the `500 ms → 8 s, max 8 attempts` budget right
   for LAN? Alternatives: tighter (3 attempts, max 2 s) for snappier "give
   up"; looser (12 attempts, max 30 s) for tolerating long Wi-Fi handovers.
2. **Incoming-session reconnect** — should the SDK initiate from both sides
   when both have `ReconnectPolicy.Enabled`, or keep the v0.2 "outgoing
   only" rule and let the remote redial? Pro/con: bidirectional is more
   resilient but doubles the simultaneous-open arbitration burden.
3. **Background guard scope** — keep the iOS background task / Android
   foreground service in the **sample apps only** as documented patterns,
   or ship them as **opt-in SDK modules** (`p2p-lifecycle-ios`,
   `p2p-lifecycle-android`)?
4. **`KeepAliveConfig` defaults** — 10 s ping / 30 s timeout. NWPathMonitor
   would let us cut timeout to ~10 s without false positives. Worth changing?
5. **Test coverage** — should §4 (path-change recovery) ship with a Kotlin
   test that fakes the `NetworkPathObserver`, or wait for end-to-end manual
   testing on two devices?

## 10. Suggested implementation order

1. §3 transport lifecycle refactor (smallest blast radius, unblocks the rest).
2. §2 reconnect backoff + jitter (no new platform code).
3. §4 path observer (Android + iOS, in parallel).
4. §5/§6 background lifecycle (sample apps + optional SDK helper).
5. §7 documentation pass + a single Markdown matrix the README points to.

Each step lands in its own PR with its own test coverage; total estimate
5–7 commits across 1–2 weeks of focused work.

## 11. Recorded backlog (2026-07)

1. **Async/suspending kit construction** (decision #5a, 2026-07-04; 2026-07
   review ARCH-10, catalogued B:201). `P2pKit.create { }` performs a one-time
   small-file identity read/write (`peerIdStorage.loadOrGenerate()`) on the
   calling thread; on Android, constructing on the main thread risks a brief
   first-launch stall. Disposition for the v0.6 RC line: documented deferral —
   the `P2pKit.create` KDoc says "construct off the main thread on Android".
   Backlog work: move the identity load behind a suspend point (lazy/async
   load or construction inside the first `start()`), weighed against the
   builder-surface lock in `P2pKit-Spec.md`.
