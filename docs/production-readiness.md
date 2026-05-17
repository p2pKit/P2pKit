# P2pKit Production Readiness — Design Doc (v0.3.0+)

Status: **proposal, awaiting review**. Targets the milestone after sample-app
edge-case hardening. Builds on existing `ReconnectPolicy`, `BackgroundPolicy`,
and `SessionManager`; no API breakage in v0.3, only new opt-in behaviour.

## 1. Goals & non-goals

**Goals.** Survive realistic LAN events without user intervention: transient
Wi-Fi drops, network handover (Wi-Fi → Wi-Fi, Wi-Fi → hotspot), OS-suspended
apps, screen-off Doze on Android. Keep sessions through ≤ 30 s outages.

**Non-goals (v0.3).** Process-death state restoration, NAT traversal,
TLS/pairing, cross-LAN reachability. `AppKilledPolicy` stays
`NoPersistenceForMvp`. New peers go through full discovery + handshake.

## 2. Reconnect strategy

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

**Today.** `SessionManager` owns sessions; transports own `DataTransport` +
`DiscoveryTransport`; `IosLanDataTransport.init` binds the listener
synchronously; `nw_listener_create` failure throws and crashes the kit
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

**Today.** Neither platform reacts to path changes for active sessions.
A Wi-Fi reconnect can rotate the local IP without us noticing until a
keep-alive PING times out (≈ 30 s).

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
| User `session.close()` | → `Closing` → `Closed` | none | — |
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
