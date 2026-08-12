# GitHub issues and pull requests audit — 2026-08-11

This audit compares every open issue and pull request, plus recently closed
unmerged pull requests, with post-`0.7.0-rc3` `main`. GitHub remains the live
tracker. “Partial” means useful implementation exists but at least one stated
acceptance criterion or required real-world measurement remains unproved.

## Issue closed by this audit

| Issue | Classification and evidence | Action |
| --- | --- | --- |
| [#45 — PeerRegistry manualPeerIds race](https://github.com/p2pKit/P2pKit/issues/45) | **Completed differently.** Commit `ee2cae5` replaced the split mutable set with one atomically updated `StateFlow<Map<PeerId, TrackedPeer>>` containing manual and per-discovery-source contributions. `PeerRegistryTest` covers repeated manual-peer eviction immunity and mixed ownership. The focused JVM suite passed on the current development lineage on 2026-08-08. | Closed with the implementation/test evidence. PR #46 was closed as superseded. |
| [#42 — JmDNS.create may block indefinitely](https://github.com/p2pKit/P2pKit/issues/42) | **Completed.** Commit `d21d065` adds bounded construction, one outstanding attempt per transport, late-handle cleanup, poisoned recovery after cleanup failure, and deterministic timeout/orphan tests. PR [#70](https://github.com/p2pKit/P2pKit/pull/70) passed the complete gate on its exact tree. | Closed automatically by the protected merge `8bf8aec4eb1901bde17098bdc7bcf82545bb1d64`. Hostile-network timing remains external performance evidence, not an implementation blocker. |
| [#47 — duplicate Android HostSelector lacks test](https://github.com/p2pKit/P2pKit/issues/47) | **Completed.** Commit `d21d065` enables AGP-KMP `androidHostTest`, ports the complete selector contract, and wires its 39 passing tests into `:p2p-transport-lan:check`. | Closed automatically by PR #70 after its exact tree passed the complete gate. |

## Issues remaining open

| Issue | Current implementation | Exact missing work | Priority / blocker / next action |
| --- | --- | --- | --- |
| [#21 — idle discovered peer disappears on Android](https://github.com/p2pKit/P2pKit/issues/21) | Transport-managed discovery lifetime and native TTL ownership prevent the old core-only 15-second eviction path. Commit `699bfd1` replaces every lossy LAN `DROP_OLDEST` event buffer with a state-backed lifecycle relay, replays current peers after collection recovery, clears a failed source before recollection, and tests 1,024-transition saturation plus stop/restart on JVM, Android host, and Apple Simulator. | Execute the long-idle/no-connect and real graceful/abrupt removal cases on representative Android devices. CI cannot prove OEM multicast/JmDNS TTL behavior or the actual UI observation that initiated the issue. | **High, external evidence only.** Execute `LAN-T01` A3 on physical Android hardware and retain both-peer long-idle, Lost/Found, JmDNS, UI, and packet evidence. |
| [#23 — iOS stale Bonjour endpoint after peer restart](https://github.com/p2pKit/P2pKit/issues/23) | Commit `d6efe08` gives cached endpoints immutable browser-generation leases, replaces them on each accepted update, clears them before browser/path ownership changes, and conditionally removes only the failed lease so a concurrent fresh result survives. | Prove peer-restart timing on devices. The first stale attempt can still consume the evidence-dependent 10-second Apple connect ceiling; the fix prevents that failed lease from remaining dialable or deleting a newer endpoint. | **High.** Apple devices/AWDL. Execute `LAN-T07` restart/path cases and retain both-peer endpoint-generation/timing evidence. |
| [#25 — JVM/macOS no-address JmDNS.create trap](https://github.com/p2pKit/P2pKit/issues/25) | Commit `d21d065` removes the no-argument path, selects one deterministic explicit multicast-capable LAN address, excludes loopback/tunnel/virtual/container interfaces, watches the complete eligible topology, and rebinds through the serialized coordinator. | Prove Mac↔Android and Linux↔mobile discovery plus interface rotation on two physical machines; the implementation now fails visibly rather than binding an unsafe platform default when no eligible LAN exists. | **High.** External macOS/Linux/network evidence. Execute `ENV-02` and retain interface/PCAP evidence. |
| [#26 — Android hotspot host may bind cellular](https://github.com/p2pKit/P2pKit/issues/26) | Commit `d21d065` uses an explicit Wi-Fi/Ethernet `Network` when available and otherwise selects a private IPv4 only from known AP/tether Java interfaces. The system-default callback is change detection only and can never become the bind fallback. | Prove AP/tether names, multicast readiness, and route behavior across representative OEM kernels; AP-client isolation remains outside application control. | **High.** OEM/hotspot hardware. Run the Android provisioning/LAN matrix with `dumpsys`, `ip addr`, both-peer logs, and PCAP evidence. |
| [#27 — iOS hotspot rebind/foreground storm](https://github.com/p2pKit/P2pKit/issues/27) | Commit `d6efe08` includes `nw_interface_type_other` in the path fingerprint and coalesces WillEnterForeground/DidBecomeActive into one inactive episode. A successful path rebind while inactive satisfies that episode, preventing a second foreground port rotation. | Personal Hotspot path classification and notification timing still need physical-device proof across iOS versions. | **Medium.** Apple device/Personal Hotspot. Run `LAN-T07` repeated enable/foreground cases and prove at most one completed rebind per inactive episode. |
| [#28 — Android address order may select VPN](https://github.com/p2pKit/P2pKit/issues/28) | Selection uses a Wi-Fi/Ethernet `Network`, `LinkProperties`, routable-address filtering, and shared network state rather than the first process-global address. | Validate VPN plus Wi-Fi/hotspot combinations on real OEM devices and prove both discovery and TCP stay on the chosen LAN. | **High.** Physical VPN/network matrix. Execute `LAN-T01` with PCAP/dumpsys evidence. |
| [#29 — Android rebind cancellation race](https://github.com/p2pKit/P2pKit/issues/29) | `JmdnsLifecycleCoordinator` serializes transitions; owns ambiguous tokens/handles until close; rolls back construction, token, registration, watcher, and partial multicast-lock failures; and coalesces concurrent callbacks. JVM coordinator tests plus Android-host listener-generation tests cover cancellation and stale-cleanup races. | Reproduce rapid callback/close storms on hardware and prove no zombie listener or overlapping JmDNS generation remains. | **Medium. External timing only after source commit `0a50312`.** Run the documented 50-toggle stress and retain generation/resource logs. |
| [#30 — no hotspot bind fallback](https://github.com/p2pKit/P2pKit/issues/30) | Commit `d21d065` adds explicit AP/tether selection, a one-second interface/address-readiness watcher, bounded construction, rollback, and bounded retry/backoff without increasing the 800 ms debounce. | Validate real OEM bind failures and establish whether any safe alternate carrier exists after retries; the code does not guess that a stale or cellular address is a valid fallback. | **Medium.** OEM hotspot evidence. Capture exact readiness/bind errors and implement an alternate only if the hardware evidence proves one is safe. |
| [#31 — JVM path/interface rebind](https://github.com/p2pKit/P2pKit/issues/31) | Commit `d21d065` polls an immutable full-topology bind target and feeds changes into the serialized rebind coordinator. A regression also proves that adding the second feature cannot relabel an old handle and suppress the required rebind. | Two-machine macOS/Linux Wi-Fi flap and interface-switch evidence is missing. | **Medium.** Physical machines/network. Execute `ENV-02`; close only after reproducible recovery evidence. |
| [#32 — Apple browser does not prohibit cellular](https://github.com/p2pKit/P2pKit/issues/32) | Commit `d6efe08` builds browser parameters with cellular prohibited and peer-to-peer enabled, symmetric with listener/outbound policy; an Apple test inspects the actual native parameter object. | Prove the policy neither prevents Personal Hotspot/AWDL discovery nor produces hidden cellular fallback on real devices. | **High.** Apple path evidence. Execute the `LAN-T07` hotspot/AWDL matrix before closure. |
| [#33 — Android outbound socket may use cellular](https://github.com/p2pKit/P2pKit/issues/33) | `AndroidLanDataTransport` creates outbound sockets through the selected `Network.socketFactory`, an equivalent stronger route binding than a later `bindSocket`. | Prove actual route selection under Wi-Fi+cellular+VPN/hotspot on physical devices. | **High.** Hardware/PCAP. Run `LAN-T01`; close if all acceptance criteria are evidenced. |
| [#34 — Apple AWDL browser/listener asymmetry](https://github.com/p2pKit/P2pKit/issues/34) | Browser, listener, and outbound Network.framework parameters all opt into peer-to-peer; commit `d6efe08` also makes cellular prohibition symmetric and tests the native browser/listener parameter objects. | Real AWDL discovery and bidirectional transfer have not been demonstrated. | **Medium.** Apple devices/AWDL. Execute the AWDL handbook and correlate both peers/path evidence. |
| [#35 — Android 800 ms rebind debounce](https://github.com/p2pKit/P2pKit/issues/35) | Serialized generations, rollback/retry, callback signals, and the new one-second AP-interface readiness watcher cover address arrival after an early callback; the debounce intentionally remains 800 ms. | Measure rapid hotspot/Wi-Fi callback bursts across OEMs and determine whether the current readiness/state model covers every sequence. | **Medium.** Hardware measurement. Do not lengthen a timeout without evidence; run the 50-toggle case. |
| [#36 — Android foreground refresh missing](https://github.com/p2pKit/P2pKit/issues/36) | Commit `d21d065` wires the official sample's Activity lifecycle into the approved host-driven contract: switches retain user intent, background policy pauses features, and foreground waits for the stop to settle before restarting only requested features. Deterministic tests cover stop/start ordering and revoked intent. | Long-background, Doze/App-Standby, process-restart, and rapid lifecycle behavior still require real-device proof; the SDK intentionally does not infer host intent or install an implicit process-wide observer. | **Medium.** Physical Android lifecycle evidence. Execute the documented background/foreground matrix and correlate the stable restore events. |
| [#37 — Apple DidBecomeActive not observed](https://github.com/p2pKit/P2pKit/issues/37) | Commit `d6efe08` observes WillResignActive, WillEnterForeground, and DidBecomeActive; a locked episode coordinator covers DidBecomeActive-only recovery and suppresses duplicate notifications. Tests prove lifecycle sequences and registration cleanup across restartable stop/start. | Control Center, system-dialog, call interruption, split-view, and lock/unlock behavior require real-device evidence. | **Medium.** Apple lifecycle hardware. Execute `LAN-T07` B4 and correlate lifecycle/rebind diagnostics. |
| [#38 — iOS endpoint registry survives rebind](https://github.com/p2pKit/P2pKit/issues/38) | Commit `d6efe08` invalidates opaque endpoints before stop, refresh, listener rebind, browser terminal recovery, and every new browser generation. Rebind also cancels pending old-path dials; generation/conditional-removal tests prevent stale ownership and fresh-endpoint deletion. | Prove the native path-change race on devices and confirm reconnect waits for a current browser result. | **High.** Apple path hardware. Execute `LAN-T07` B3/B4 with endpoint-generation and connection-ID evidence. |
| [#39 — JmDNS cache growth during long idle](https://github.com/p2pKit/P2pKit/issues/39) | Rebind closes old instances and diagnostics expose generation/resource behavior. | A 6–12 hour multi-peer idle/appearance churn run with heap/cache/resource measurements has not been performed. | **Medium.** Long-running physical lab. Execute a bounded soak and retain heap/descriptor evidence. |
| [#40 — asymmetric TCP connect timeouts](https://github.com/p2pKit/P2pKit/issues/40) | Platform timeouts are bounded and reconnect budgets are explicit. | JVM/Android remain 5 s and Apple 10 s; no hostile-network measurement justifies convergence or documents intentional asymmetry. | **Medium.** Two-machine/Apple timing. Measure first; change API/values only from evidence. |
| [#41 — iOS write-ready 10 s wedge](https://github.com/p2pKit/P2pKit/issues/41) | Commit `d6efe08` makes write-ready expiry terminal: it latches Closed, cancels the native connection exactly once, and makes the next write fail immediately. A deterministic 25 ms seam proves the terminal transition without changing the production 10-second ceiling. | Device evidence must measure cancellation/path-change wakeup and determine whether the 10-second ceiling is appropriate for AWDL. | **Medium.** Apple path fault injection. Run B3/B4 and the #40 timing campaign before changing the value. |
| [#43 — Android serviceRemoved has null ServiceInfo](https://github.com/p2pKit/P2pKit/issues/43) | Commit `d21d065` owns admitted instance-name→peer mappings by listener generation and tests metadata-free removal, stale/current ownership, and terminal drain. Commit `699bfd1` makes removal delivery convergent under saturation, late collection, stream recovery, stop, and remove/re-add conflation. | Prove the real OEM/JmDNS null-or-stub callback shape and measure eviction timing for graceful stop, force-stop, packet loss, and callback churn. | **Medium, external evidence only.** Execute `LAN-T01` add/remove cases on physical devices and retain callback payload, instance name, peer ID, UI timing, both-peer logs, and PCAP. |
| [#44 — link-local asymmetry](https://github.com/p2pKit/P2pKit/issues/44) | Shared routable-host validation and platform selectors now retain valid IPv4 link-local/scoped IPv6 candidates where appropriate. | Cross-platform link-local-only discovery/connectivity has not been exercised on physical interfaces; zone/scope handling needs evidence. | **Medium.** Two-machine/device link-local topology. Execute `PS-T08` plus PCAP/path logs. |

No partially completed issue was closed. Related external evidence is organized
under [`../validation/`](../validation/README.md), but those handbooks do not
replace issue-specific implementation work.

## JVM/Android LAN remediation workstream evidence

Source commit `d21d06506e64379899287e0d34bd6fffa3ea28b0` is the focused
implementation and regression-test commit. It changes only these files:

- `library/p2p-transport-lan/build.gradle.kts`
- `library/p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/JmdnsLifecycleCoordinator.kt`
- `library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/BoundedBlockingHandleCreator.kt`
- `library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanBinding.kt`
- `library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDiscoveryTransport.kt`
- `library/p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidLanBinding.kt`
- `library/p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidLanDiscoveryTransport.kt`
- `library/p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/BoundedBlockingHandleCreator.kt`
- `library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/BoundedBlockingHandleCreatorTest.kt`
- `library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JmdnsLifecycleCoordinatorTest.kt`
- `library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JvmLanBindSelectorTest.kt`
- the four tests under `library/p2p-transport-lan/src/androidHostTest/`
- `samples/p2p-sample-android/src/main/java/dev/p2pkit/sample/android/ForegroundFeatureRestorer.kt`
- `samples/p2p-sample-android/src/main/java/dev/p2pkit/sample/android/P2pKitViewModel.kt`
- `samples/p2p-sample-android/src/test/java/dev/p2pkit/sample/android/ForegroundFeatureRestorerTest.kt`

Final local exact-tree verification on 2026-08-09:

- `./gradlew :p2p-transport-lan:jvmTest :p2p-transport-lan:testAndroidHostTest :p2p-sample-android:testDebugUnitTest` — **PASS**; the Android host task ran 39 tests with zero failures.
- `./gradlew :p2p-transport-lan:check :p2p-transport-lan:dokkaGeneratePublicationHtml :p2p-sample-android:assembleDebug :p2p-sample-android:lintDebug` — **PASS**; JVM/Android/iOS simulator tests, all declared iOS compilation, ABI, Dokka, APK assembly, and lint completed.
- `scripts/check-publish-artifacts.sh` — **PASS**; all 15 publications had readable artifacts, Dokka, coordinates, module identities, and release metadata.
- `scripts/check-published-consumers.sh` — **PASS**; isolated JVM, Android, KMP, and iOS 14 consumers compiled.
- `./gradlew :p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance` and `scripts/check-xcframework-minimum-os.sh` — **PASS**; provenance matched and all release slices retained the iOS 14 floor.
- `scripts/check-sbom.sh`, OSV lock coverage, Markdown links, repository layout, and `git diff --check` — **PASS**.

PR [#70](https://github.com/p2pKit/P2pKit/pull/70) ran the hosted complete
gate successfully on head `21fc3e2433231d2ab93c8fdbec69b2858d69807f`:
[run 31287800890](https://github.com/p2pKit/P2pKit/actions/runs/31287800890).
The protected normal merge produced
`8bf8aec4eb1901bde17098bdc7bcf82545bb1d64`; its tree
`7aeaff888eb734ea422616fac3950a76b7bef32a` is byte-for-byte identical to
the tested PR tree, so the exact-tree reuse policy correctly avoids a redundant
complete-gate run.

The workstream does not change public ABI, Maven coordinates, secure-v2 or LAN
wire formats, the iOS deployment floor, or any immutable published artifact.
Android OEM multicast/callback behavior, Mac/Linux interface rotation, and
hostile-network timing remain external evidence requirements and are not
claimed as verified here.

## JVM/Android LAN ownership follow-up

Source commit `0a50312` closes additional deterministic resource-ownership
gaps found by the continuation audit:

- cancelled or failed listener binds retain and close every produced
  `ServerSocket`, including cleanup failures crossing a coroutine dispatcher;
- listener generation handoff is atomic, so stale accept-loop cleanup cannot
  clear a replacement listener or its advertised port;
- pending outbound sockets cannot escape a concurrent stop at the final raw-
  connection handoff, and failed candidate cleanup prevents unsafe fallback;
- all failed listener/dial resources remain in retryable retained sets instead
  of a single overwriteable cleanup slot;
- JmDNS construction, token creation, native attachment, watcher start, and
  Android multicast-lock acquisition now form one rollback transaction;
- an interrupted bounded-construction waiter transfers a completed orphan to
  one owned daemon cleanup worker instead of blocking the cancelled caller;
- discovery stop drains transport-owned peer admissions even when native
  listener detach fails, and rejected incoming raw connections receive full
  wrapper cleanup.

Deterministic proof comprises 36 coordinator tests, five JVM and four Android
bounded-construction tests, five JVM and six Android socket-ownership tests,
and two JVM candidate-fallback tests: 58 focused executions, zero failures,
errors, or skips. Complete LAN JVM/Android suites passed with 113 JVM and 46
Android-host tests. `check`, Android compilation/lint/sample checks, all
declared Apple compilation/linkage, 79 arm64-simulator LAN tests (one explicit
external diagnostic ignored), ABI, Dokka, SBOM, all 15 publication shapes,
isolated JVM/Android/KMP/iOS 14 consumers, release-XCFramework provenance,
iOS 14 slice inspection, and the Swift warnings-as-errors build passed on the
same source tree.

The first protected-boundary run for PR
[#82](https://github.com/p2pKit/P2pKit/pull/82),
[CI run 31480335701](https://github.com/p2pKit/P2pKit/actions/runs/31480335701),
correctly failed rather than producing a nondeterministic terminal result. Two
pre-existing core test harnesses failed under the three-core hosted workload,
before any LAN assertion failed: the iOS path-recovery test coupled its wake-up
assertion to completion of a second handshake within 3.5 seconds, and the JVM
PeerId test launched four child JVMs simultaneously but gave all four one
shared 15-second startup window. The follow-up keeps the behavioral assertions
intact: it observes the retry dial itself within one third of the configured
retry delay before separately requiring a successful rearm, and preloads each
of the four child processes in turn before releasing all four into the same
file-lock contention point. Focused concurrent reruns and the complete
589-test JVM plus 559-test iOS Simulator core suites pass with zero failures,
errors, or skips.

The correction was committed as `a88d033801c03b430c5067776d941e099471a541`
(tree `25f6a53342759ec3b9bb134fb759e733f2301b35`). The replacement
[complete gate](https://github.com/p2pKit/P2pKit/actions/runs/31486056226)
passed on that exact head together with OSV, dependency review, and Ubuntu and
Windows Desktop checks. PR #82 merged normally through branch protection as
`e64c833fd9759f529df212122583ec3bd4edba1f`; the merge tree is the identical
`25f6a53342759ec3b9bb134fb759e733f2301b35`, so no duplicate gate was run.

This follow-up changes no public ABI, Maven coordinate, secure-v2 or LAN wire
format, platform floor, or immutable release artifact. Issue #29 still needs
the physical 50-toggle callback storm. The subsequent discovery-relay batch
below completes the repository prerequisite for #21/#43; their physical
campaigns remain pending.

## Reliable LAN discovery relay workstream evidence

Source commit `699bfd1654708dde3d3dfe1f06b55ae013fddfc7` replaces the
platform-specific replay-zero, 256-entry `DROP_OLDEST` buffers with one common
state-backed lifecycle relay. Native and JmDNS callbacks remain non-blocking,
but an already observed peer cannot remain stuck merely because unrelated
churn saturated an event queue. Each collector receives a complete current
snapshot; lifecycle tokens preserve `Lost` then `Found` across a conflated
remove/re-add; in-place changes coalesce only to the latest `Updated` value.

The audit also closes two adjacent ownership gaps required for that guarantee:

- ordinary discovery-flow failure or unexpected completion removes only that
  transport's registry contributions before bounded recollection, after which
  the state-backed transport replays its current peers;
- Apple stop retires browser generation, announce cache, opaque endpoint
  leases, and relay state in one native-lock transaction. A queued result
  either commits before the withdrawal or fails the host-intent/generation
  check, so it cannot resurrect a peer after stop.

The focused regression set covers late subscription, two independent
collectors, 1,024 add/remove transitions while a collector is blocked, latest
update coalescing, remove/re-add lifecycle identity, stable multi-peer clear,
32 concurrent callback writers, JVM callback/stop/restart integration, Apple
stop/restart, and core failure/completion recollection with an unaffected
second transport. No assertion or production timeout was weakened.

The first protected complete-gate run for PR
[#83](https://github.com/p2pKit/P2pKit/pull/83),
[CI run 31492177821](https://github.com/p2pKit/P2pKit/actions/runs/31492177821),
failed only in the pre-existing JVM
`FilePeerIdStorageTest.concurrentChildProcessesCommitOneDurableWinner` harness.
The earlier sequential-preload correction still gave each already-ready child
an unrelated 15-second deadline while the parent loaded the remaining JVMs;
the first child could therefore exit before barrier release on the three-core
hosted runner. The follow-up removes that false deadline: a ready child waits
for the explicit parent release while checking that the owning parent process
is alive, and the parent retains bounded readiness/completion waits plus
unconditional child cleanup. Storage assertions and production behavior are
unchanged. The failed run is not verification evidence. Replacement
[run 31497583675](https://github.com/p2pKit/P2pKit/actions/runs/31497583675)
passed on corrected head `78b0e4249f031fd24af4d98be87a1894b0512c2e`
and tree `3fc254c5aa6f69e243a81df375cfde1048e56345`. PR #83 then merged
normally through branch protection as
`ba418189b7fc3033ac4f3e51932b83f7407bf323`; the merge has the identical
tree, so exact-tree reuse avoided an unnecessary duplicate complete gate.

Exact changed files:

- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/PeerRegistryTest.kt`
- `library/p2p-transport-lan/src/commonMain/kotlin/dev/p2pkit/transport/lan/ReliablePeerEventRelay.kt`
- `library/p2p-transport-lan/src/commonTest/kotlin/dev/p2pkit/transport/lan/ReliablePeerEventRelayTest.kt`
- `library/p2p-transport-lan/src/jvmMain/kotlin/dev/p2pkit/transport/lan/JvmLanDiscoveryTransport.kt`
- `library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JvmDiscoveryRelayIntegrationTest.kt`
- `library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/ReliablePeerEventRelayConcurrencyTest.kt`
- `library/p2p-transport-lan/src/androidMain/kotlin/dev/p2pkit/transport/lan/AndroidLanDiscoveryTransport.kt`
- `library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosLanDiscoveryTransport.kt`
- `library/p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/IosLanLifecycleTest.kt`

Focused and complete affected-module verification passed with 591 core JVM,
561 core arm64 iOS Simulator, 121 LAN JVM, 52 LAN Android-host, and 86 LAN
arm64 iOS Simulator tests: zero failures or errors and no skips except the one
explicitly external `IosLanDiagnosticTest`. The root `check --rerun-tasks`
also passed with all 184 actionable tasks executed. The arm64 host cannot run
the x64 iOS binaries, but their test sources compiled and linked; ABI, strict
Dokka, Android compilation, and all declared iOS target compilation/linkage
passed. Release/consumer checks, the protected PR gate, and merge-tree identity
are proven by the replacement run and merge above. Physical peer
lifetime/removal and real-network callback ordering remain external; none is
claimed as verified by simulator or host checks.

There is no public API/ABI, Maven coordinate, secure-v2 or LAN wire change,
platform-floor change, or change to any immutable release artifact. Issues
#21 and #43 now have no known repository-side relay/removal prerequisite, but
remain open until `LAN-T01` supplies real Android long-idle, null/stub callback,
graceful/abrupt departure, UI-timing, and packet evidence.

## Apple LAN remediation workstream evidence

Source commit `d6efe0899d7aabc3dae891b0dda80bb6adec1a4a` is the focused
implementation and deterministic-regression commit. It changes only:

- `library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/AppleLifecycleRecoveryCoordinator.kt`
- `library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosEndpointRegistry.kt`
- `library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosLanDataTransport.kt`
- `library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosLanDiscoveryTransport.kt`
- `library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosRawConnection.kt`
- `library/p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/AppleLifecycleRecoveryCoordinatorTest.kt`
- `library/p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/IosEndpointRegistryTest.kt`
- `library/p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/IosLanConnectCancellationTest.kt`
- `library/p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/IosLanRecoveryTest.kt`
- `library/p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/IosRawConnectionTest.kt`

The architectural corrections are:

- opaque Bonjour endpoints carry immutable browser-generation ownership;
  every browser/path retirement invalidates old endpoints, and a failed dial
  can remove only the lease it actually used;
- rebind begins by invalidating endpoints and cancelling pending old-path
  dials, preventing connects from escaping through the teardown window;
- browser/listener/outbound parameters are peer-to-peer enabled and prohibit
  cellular symmetrically, while `nw_interface_type_other` participates in the
  path fingerprint;
- WillResignActive, WillEnterForeground, and DidBecomeActive feed a locked
  inactive-episode coordinator that emits at most one recovery and recognizes
  a successful path rebind performed while inactive;
- write-ready timeout is terminal: it closes state and cancels the native
  connection exactly once without changing the evidence-dependent 10-second
  production ceiling.

Focused and complete affected checks on 2026-08-09:

- Apple production/test compilation — **PASS**.
- Focused endpoint, lifecycle, cancellation, recovery, and raw-connection
  tests — **PASS**.
- `:p2p-transport-lan:iosSimulatorArm64Test` — **PASS** after correcting an
  intermediate native test seam that left asynchronous browser work for later
  classes; the final side-effect-free generation seam produced 79 tests,
  zero failures, and one intentionally ignored external diagnostic.
- `:p2p-transport-lan:check` — **PASS** in 1m20s, including JVM, Android host,
  iOS simulator, iosArm64 compilation, iosX64 linkage policy, and ABI.
- strict LAN Dokka, publication shape (15 publications), isolated
  JVM/Android/KMP/iOS 14 consumers, release-XCFramework provenance, iOS 14
  minimum-OS inspection, and SBOM (38 release components) — **PASS**.
- The generated Swift sample compiled for arm64 and x86_64 simulator slices
  with `SWIFT_TREAT_WARNINGS_AS_ERRORS=YES` — **PASS**.

The first protected-boundary run, [CI run 31292879247](https://github.com/p2pKit/P2pKit/actions/runs/31292879247),
stopped in the iOS sample UI entry-point test before any P2pKit start action
was acknowledged. XCTest found a visible, hittable Start button but spent
about 11 seconds checking an interrupting element, reported that it had
synthesized the tap, and left the application at `Status: Not started`. The
exact original test passed locally on a dedicated iPhone 17 simulator, which
isolated the failure to hosted XCTest input delivery rather than Apple LAN
startup.

The corrected test keeps the existing aggregate ten-second acknowledgement
budget. It attempts an alternate center-coordinate input exactly once only
when the semantic tap left the app foregrounded, the status unchanged, and
the Start control present and hittable; it never retries an acknowledged app
action or a P2pKit operation. A debug-only launch argument deterministically
drops the first app action so a second UI test covers that recovery branch.
The normal and injected cases passed together, followed by three no-retry
iterations (six test executions) and a Release warnings-as-errors build. The
test argument was confirmed absent from the Release binary. CI now retains
the failed `.xcresult` for seven days, while `check-sbom.sh` remains the
blocking SBOM presence/content gate and an earlier failure no longer creates
a misleading second missing-artifact failure.

No public ABI, Maven coordinate, secure-v2/LAN wire format, iOS library floor,
or immutable published-artifact changes. Real AWDL, Personal Hotspot,
Control Center/system interruption, device lock/background, peer restart,
path rotation, and timeout histograms remain required external evidence; none
is claimed as verified by simulator or host checks.

## Provisioning lifecycle and native ownership workstream evidence

Implementation commit `fc73837cfa154caa82a6f96172603108b8577842`
(tree `99f3ca08faef2980ad0b44611ee4dc1de487c779`) makes each public
provisioning operation manager-owned rather than caller-owned on Android, JVM,
and Apple. Caller cancellation now cancels and joins the owned operation;
manager-parent cancellation closes the JVM and Apple implementations
terminally. Android serializes initial binding and rebinding, arbitrates the
process-wide bind token across manager instances, retains every native cleanup
resource until cleanup actually succeeds, shares one close attempt and result
among concurrent callers, and permits a later close to retry a failed cleanup.
Generation ownership prevents a stale hotspot callback or old-network
`onLost` callback from releasing a newer acquisition. `onUnavailable` and
network delivery have one terminal winner.

Android request validation now rejects a missing, empty, or non-ASCII WPA2 or
WPA3 passphrase before invoking `WifiNetworkSpecifier`; OPEN requests reject
any password value, including an empty wrapper. Permission requirements use
both the device SDK and the consumer target SDK. Manual provisioning results
include the local identity fingerprint and pairing QR without logging a
credential. JVM address-scanner failures represented by ordinary exceptions
become a retryable `Unknown` state while cancellation and fatal errors retain
their semantics. The unsupported manager's stale version text and affected
KDoc were corrected without renaming its private compatibility constant.

Exact implementation and regression files:

- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/provisioning/UnsupportedNetworkProvisioningManager.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/NetworkProvisioningCloseTest.kt`
- `library/p2p-network-provisioning-android/src/androidHostTest/kotlin/dev/p2pkit/provisioning/android/AndroidNetworkProvisioningManagerTest.kt`
- `library/p2p-network-provisioning-android/src/androidHostTest/kotlin/dev/p2pkit/provisioning/android/RetryableProvisioningCleanupTest.kt`
- `library/p2p-network-provisioning-android/src/androidMain/AndroidManifest.xml`
- `library/p2p-network-provisioning-android/src/androidMain/kotlin/dev/p2pkit/provisioning/android/AndroidDsl.kt`
- `library/p2p-network-provisioning-android/src/androidMain/kotlin/dev/p2pkit/provisioning/android/AndroidNetworkProvisioningManager.kt`
- `library/p2p-network-provisioning-android/src/androidMain/kotlin/dev/p2pkit/provisioning/android/AndroidP2pPermissionManager.kt`
- `library/p2p-network-provisioning-android/src/androidMain/kotlin/dev/p2pkit/provisioning/android/ProvisioningAndroidValidation.kt`
- `library/p2p-network-provisioning-android/src/androidMain/kotlin/dev/p2pkit/provisioning/android/RetryableProvisioningCleanup.kt`
- `library/p2p-network-provisioning-android/src/androidMain/kotlin/dev/p2pkit/provisioning/android/WifiManagerWrapper.kt`
- `library/p2p-network-provisioning-android/src/androidMain/kotlin/dev/p2pkit/provisioning/android/WifiManagerWrapperImpl.kt`
- `library/p2p-network-provisioning-desktop/src/main/kotlin/dev/p2pkit/provisioning/desktop/JvmDsl.kt`
- `library/p2p-network-provisioning-desktop/src/main/kotlin/dev/p2pkit/provisioning/desktop/JvmNetworkProvisioningManager.kt`
- `library/p2p-network-provisioning-desktop/src/test/kotlin/dev/p2pkit/provisioning/desktop/JvmNetworkProvisioningManagerTest.kt`
- `library/p2p-transport-lan/src/appleMain/kotlin/dev/p2pkit/transport/lan/IosManualNetworkProvisioningManager.kt`
- `library/p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/IosManualProvisioningLifecycleTest.kt`

Focused final-tree evidence before the protected boundary:

- Android provisioning host tests — **PASS**, 51 tests, zero failures,
  errors, or skips. This includes concurrent close, failed-cleanup retry,
  stale callback generation, process-binding arbitration, permission policy,
  request validation, and typed error mapping.
- Desktop provisioning tests — **PASS**, 15 tests, zero failures, errors, or
  skips, including caller/parent cancellation and transient scanner recovery.
- Apple lifecycle tests — **PASS** within the full 89-test arm64 simulator
  suite. The suite has zero failures/errors and one intentionally skipped
  external-only `IosLanDiagnosticTest`; the provisioning lifecycle class has
  four executed tests.
- The affected-module boundary passed `p2p-core` JVM tests, Android
  provisioning `check` and host-test lint, Desktop `check`, Apple simulator
  tests, iosArm64/iosX64 compilation, and all four affected ABI checks: 79
  actionable tasks executed in 1m29s. The Android KMP module exposes
  `lintAnalyzeAndroidHostTest` through `lint` but no separate Android-main
  lint task; Android-main production compilation did execute.
- `git diff --check` and the committed-diff whitespace review — **PASS**.

There is no public ABI, Maven coordinate, wire-format, secure-v2,
platform-floor, or published-artifact change. Complete gate
[31514113705](https://github.com/p2pKit/P2pKit/actions/runs/31514113705)
passed exact PR head `dadfc66307353c95d865f2835eca0d2d89d3eb84`.
PR [#84](https://github.com/p2pKit/P2pKit/pull/84) then merged normally as
`fc1f6f92e6eb52573ef6f9034102d9d288d7a2bf`; the head and merge both have
tree `61cc2e6684ea0fce804bf7bedf2b02006fec0b73`, so the exact-tree reuse policy
avoided a redundant gate. Physical `PROV-A12`, `PS-T01`, and `PS-T02`
evidence remains mandatory for real Android framework/OEM callbacks and
process binding. Apple manual-provisioning lifecycle behavior still requires
the device lifecycle legs in `LAN-T07` and `ENV-01`; simulator tests do not
prove suspension, process death, or AWDL.

## Core secure protocol ownership workstream evidence

Implementation commit `c867c90c82a1a7b675fb2d19a055911ee6f8e4cd`
(tree `95b24544a59d15b548aeed5520704fdd773b5a34`) closes four
repository-executable protocol and ownership gaps found by the continuation
audit:

- a successful Noise XX outcome now remains in an explicit lease until the
  connect caller claims it; cancellation after worker settlement closes the
  secure stream and clears handshake metadata instead of stranding cipher
  state;
- HELLO and legacy FILE_OFFER JSON reject duplicate top-level fields,
  including escaped/literal spellings of the same key, before typed decoding;
- application-handshake rejection writes preserve owner cancellation while
  retaining stable local errors for ordinary best-effort write failures; and
- partial-message reassembly expiry is wired to the monotonic clock rather
  than wall time, so clock corrections cannot retain hostile fragments or
  evict a live reassembly prematurely.

Exact implementation and regression files:

- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/Handshake.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/AuthenticatedV2SecurityEngine.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/JsonWireValidation.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/HelloPayload.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/protocol/FileOfferPayload.kt`
- the corresponding four common test classes under
  `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/`.

Final source-tree verification before the protected boundary:

- complete `p2p-core` JVM suite — **PASS**, 598 tests, zero failures,
  errors, or skips;
- complete iOS Simulator Arm64 suite — **PASS**, 568 tests, zero failures,
  errors, or skips;
- Android main compilation/lint checks and iosArm64, iosSimulatorArm64, and
  iosX64 production/test compilation and linkage — **PASS**. `iosX64Test` is
  host-skipped after linkage on Apple Silicon; its production and test code
  compiled and linked, but runtime execution requires an Intel host and is not
  inferred from this run;
- core ABI and warning-failing Dokka — **PASS**;
- all 15 publication shapes and isolated JVM, Java, Android, KMP, and iOS 14
  consumers — **PASS**;
- release XCFramework device/simulator reconstruction and provenance, iOS 14
  minimum-slice inspection, and the generated Swift sample build with
  `SWIFT_TREAT_WARNINGS_AS_ERRORS=YES` — **PASS**; and
- `git diff --check`, staged whitespace review, ignored-test search, and XML
  result inspection — **PASS**. No core test is ignored. Xcode emitted only
  its non-source AppIntents metadata notice because the sample has no
  AppIntents dependency.

The approved secure-v2 and explicit legacy-v1 wire contracts, public ABI,
Maven coordinates, and platform floors are unchanged. Complete gate
[31524495713](https://github.com/p2pKit/P2pKit/actions/runs/31524495713)
passed exact PR head `701612ef2daa222376fc953e6a739da0f4e9ed04`.
PR [#85](https://github.com/p2pKit/P2pKit/pull/85) then merged normally as
`0b267fa97dc09a573d3a7fb1e00416a5d5d16c12`; the head and merge both have
tree `c944e628ac95f703a80277d2038f0daa56981013`, so the exact-tree reuse policy
avoided a redundant gate. These deterministic checks do not satisfy
independent secure-v2 interoperability or professional cryptographic review;
both external campaigns remain pending.

## Core discovery admission and publication workstream evidence

Implementation commit `bef0407647ac3444ffad965a59a7483610df9192`
(tree `5cb0bf265a3c892b6dd059012a4f7b68055e9857`) closes the
repository-executable discovery-boundary gaps found by the continuation audit:

- every public discovery-SPI event is validated before retention, with bounded
  peer identifiers, names, transport hints, hosts, ports, and metadata;
- event-supplied manual provenance and application-trusted pins are normalized
  to discovered provenance and untrusted discovery claims, while an actual
  application-supplied manual pin remains authoritative for a mixed entry;
- discovery retention is capped at 1,024 distinct peer identifiers without
  charging manual-only entries, blocking updates at capacity, or preventing
  capacity reclamation after source loss or staleness;
- invalid and capacity-rejected events cannot reset empty-stream recollection
  backoff, and rejection diagnostics are stable, value-free, and once-only;
  and
- registry mutations carry monotonically increasing generations through
  publication, so a delayed older writer cannot overwrite a newer `Lost`,
  eviction, manual-registration, or terminal-close snapshot. The established
  public peer `StateFlow` still suppresses heartbeat-only list emissions while
  `lastSeen` advances.

Exact implementation and regression files:

- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerRegistry.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/DiscoveryTransport.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/PeerRegistryTest.kt`

Final implementation-tree evidence before the protected boundary:

- `PeerRegistryTest` — **PASS**, 33 JVM and 33 arm64 iOS Simulator tests,
  zero failures, errors, or skips. New deterministic coverage includes stale
  publication ordering, heartbeat de-noising, provenance normalization,
  manual-pin precedence, hostile-field rejection, value-safe diagnostics,
  capacity reclamation and multi-source accounting, 128 concurrent writers,
  and virtual-time invalid-stream backoff;
- complete `p2p-core` check — **PASS**, 607 JVM and 577 arm64 iOS Simulator
  tests, zero failures, errors, or skips, with all 25 requested tasks executed
  under `--rerun-tasks`;
- Android main compilation and every declared iOS production/test compile and
  link — **PASS**. `iosX64Test` is host-skipped on Apple Silicon after its test
  binary links; runtime execution still requires an Intel macOS runner and is
  not inferred from linkage;
- core ABI and warning-failing Dokka — **PASS**; and
- `scripts/run-release-gate.sh` — **PASS** on the identical implementation
  tree, including repository policy/link checks, root checks, SBOM, all 15
  publication shapes, isolated JVM/Java/Android/KMP/iOS 14 consumers, release
  XCFramework provenance and minimum-iOS inspection, and the Swift sample build
  with warnings as errors. `git diff --check` also passed.

There is no public API/ABI, Maven coordinate, wire-format, platform-floor, or
published-artifact change. These automated checks do not prove physical
Android/Apple discovery behavior, real-network callback ordering, or hostile
multi-machine conditions; the corresponding validation campaigns remain
pending and are not upgraded by this workstream.

Complete gate
[31531533715](https://github.com/p2pKit/P2pKit/actions/runs/31531533715)
passed exact PR head `90d50e83ad16419061fd5964f438b1baa09173ec`.
PR [#86](https://github.com/p2pKit/P2pKit/pull/86) then merged normally as
`f8cf629d7209fdb6dc321c180123d26028ae63d7`; head and merge share tree
`d93b3d5598bc13037dd802aeeac7dfdad57231ab`, so exact-tree reuse avoided a
redundant complete gate.

## Core lifecycle and persistent identity workstream evidence

Implementation commit `04df9a0f98d233107f9a27d67e6d889135c7f7be`
(tree `572696ff0b37098cc03f3193968b71f2981e72ca`) closes the
repository-executable lifecycle and local-identity gaps found by the
continuation audit:

- whole-kit and feature startup now treat cancellation as an outer resource
  transaction, including cancellation recorded after a platform callback has
  acquired a resource and returned; successful cleanup restores a retryable
  idle state, while incomplete cleanup latches fail-closed ownership;
- partially attached network-path observers are detached before startup
  degrades, observer cleanup attempts cannot overlap when a broken callback
  ignores cancellation, and ordinary observer failure cannot leave data
  transports bound behind a public `Starting` state;
- AppId and local PeerId values are validated against the HELLO text contract
  before transport construction, persisted UTF-8 records are read with a
  4,096-byte hard bound and strict decoding, and corrupt records regenerate
  rather than reaching wire or diagnostic surfaces; and
- JVM and Android process-lock registries retain an entry only while an
  operation is using or waiting for it, avoiding unbounded process memory
  growth across transient AppIds without weakening same-path serialization.

Exact implementation and regression files:

- `library/p2p-core/src/androidMain/kotlin/dev/p2pkit/core/internal/FilePeerIdStorage.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/NetworkPath.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/dsl/Builders.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/PeerIdStorage.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/permission/NoOpP2pPermissionManager.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/InMemoryPeerIdStorageTest.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/KitLifecycleTest.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/LocalIdentityTest.kt`
- `library/p2p-core/src/iosMain/kotlin/dev/p2pkit/core/internal/NSUserDefaultsPeerIdStorage.kt`
- `library/p2p-core/src/iosTest/kotlin/dev/p2pkit/core/internal/NSUserDefaultsPeerIdStorageTest.kt`
- `library/p2p-core/src/jvmMain/kotlin/dev/p2pkit/core/internal/FilePeerIdStorage.kt`
- `library/p2p-core/src/jvmTest/kotlin/dev/p2pkit/core/internal/FilePeerIdStorageTest.kt`

Final committed-tree verification before the protected boundary:

- complete `p2p-core` JVM suite — **PASS**, 620 tests, zero failures,
  errors, or skips;
- complete iOS Simulator Arm64 suite — **PASS**, 590 tests, zero failures,
  errors, or skips. Deterministic regressions exercise cancellation during
  bind, feature retry cleanup, observer attach/cleanup, and callbacks that
  cancel then return a resource;
- Android main compilation and iosArm64, iosSimulatorArm64, and iosX64
  production/test compilation and linkage — **PASS**. `iosX64Test` is
  host-skipped on Apple Silicon after its test binary links; Intel runtime
  execution is not inferred from linkage;
- Android sample, CLI sample, and Desktop UI checks — **PASS**, respectively
  4, 7, and 14 executed tests with zero failures/errors/skips; Android lint,
  core ABI, and warning-failing Dokka also passed;
- all 15 publication shapes and isolated JVM, Java, Android, KMP, and iOS 14
  consumers — **PASS** under strict dependency verification;
- release XCFramework device/simulator reconstruction and provenance —
  **PASS**, with commit `04df9a0f98d233107f9a27d67e6d889135c7f7be`,
  source state `clean`, and iOS 14.0 minimum slices. The Swift sample build
  passed with `SWIFT_TREAT_WARNINGS_AS_ERRORS=YES`; Xcode emitted only its
  non-source AppIntents notice because the sample has no AppIntents
  dependency; and
- CycloneDX JSON/XML validation — **PASS**, 38 release components and no
  sample/build contamination. Release metadata, repository layout, 91 active
  Markdown links, OSV lock coverage for all 11 lockfiles, CI scope policy,
  release-workflow policy, `git diff --check`, and clean-worktree checks also
  passed.

`NO-SOURCE` resource/Java tasks and Kotlin/Gradle synthetic SwiftPM or plugin
configuration skips correspond to undeclared source kinds or absent external
SwiftPM inputs, not omitted tests. Sample CycloneDX subtasks are intentionally
excluded from the release SBOM and the aggregate SBOM content gate confirms
that exclusion. No test in the executed JVM, arm64 iOS Simulator, or sample
suites was skipped.

There is no public API/ABI, Maven coordinate, secure-v2 or legacy wire-byte,
platform-floor, or publication-layout change. Construction now rejects local
identity text that the existing wire decoder would reject, and legacy corrupt
persistence records regenerate; valid existing identities remain compatible.
Complete gate
[31542848494](https://github.com/p2pKit/P2pKit/actions/runs/31542848494)
passed exact PR head `f699c232075b923faa69b3f5a4f8fb2e95842db1`.
PR [#87](https://github.com/p2pKit/P2pKit/pull/87) then merged normally as
`a99a890c2208e33fe413869a424b60dacadca71f`; head and merge share tree
`0c42da2bbfe80727705a4d69977021df689f28d8`, so exact-tree reuse avoided a
redundant complete gate. Physical Android/Apple lifecycle behavior,
real-network callback ordering, independent secure-v2 interoperability, and
professional cryptographic review remain external campaigns and are not
upgraded by this evidence.

## Public configuration and transport SPI workstream evidence

Implementation commit `c7ff7cdce20e1f71505dd7d2087fa38c63437f0b`
(tree `7142124e8081b60b36dcbebd389643b66afc5828`) closes the
repository-executable public configuration and third-party transport boundary
gaps found by the fresh API audit:

- repeated `networkProvisioning {}` blocks now preserve an existing provider
  registration unless a later block explicitly replaces it, matching the
  accumulation behavior of the other configuration blocks;
- default public advertising and discovery state flows are read-only at
  runtime rather than castable shared `MutableStateFlow` instances;
- third-party transport capability, priority, and type getter failures are
  fail-closed as typed connection or initialization failures, retain their
  cause, and never swallow coroutine cancellation; and
- public lifecycle, session-state, configuration-bound, manual-endpoint,
  transport-SPI, and connection-ownership KDoc now states the behavior enforced
  by production code.

Exact implementation and regression files:

- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/Config.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/P2pKit.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/States.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/dsl/Builders.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/P2pKitImpl.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/TransportManager.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/provisioning/ManualPeerRegistrar.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/provisioning/NetworkProvisioningTypes.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/FileTransferConfig.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/DataTransport.kt`
- `library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transport/RawConnection.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/PublicConfigurationValidationTest.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/PublicModelImmutabilityTest.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/KitLifecycleTest.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/NetworkProvisioningCloseTest.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/PeerRegistryTest.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/TransportCapabilityTest.kt`
- `library/p2p-core/src/commonTest/kotlin/dev/p2pkit/core/internal/TransportManagerTest.kt`

Final committed-tree verification before the protected boundary:

- complete `p2p-core` check under strict dependency verification and
  `--rerun-tasks` — **PASS**: 636 JVM and 606 arm64 iOS Simulator tests, zero
  failures, errors, or skips, with all 25 requested tasks executed;
- focused configuration, immutability, lifecycle, provisioning-close,
  transport-capability, and selection suites — **PASS**, including invalid
  bounds, repeated configuration blocks, runtime state-flow immutability,
  provider getter failure/cancellation, stable priority ties, lazy startup
  failure, and terminal lifecycle behavior;
- Android main, iosArm64, iosSimulatorArm64, and iosX64 production/test
  compilation and linkage, Android sample, CLI, Desktop UI, Android lint, ABI,
  and warning-failing Dokka — **PASS**. `iosX64Test` is host-skipped on Apple
  Silicon after its test binary links; runtime execution remains an Intel-host
  requirement and is not inferred from linkage;
- `scripts/run-release-gate.sh` — **PASS** on the clean implementation commit,
  including repository/link/policy validation, root checks, strict dependency
  verification, 38-component release SBOM, all 15 publication shapes,
  isolated JVM/Java/Android/KMP/iOS 14 consumers, release XCFramework
  reconstruction and provenance, iOS 14 slice inspection, and Swift warnings
  as errors; and
- XCFramework provenance records exact commit
  `c7ff7cdce20e1f71505dd7d2087fa38c63437f0b`, source state `clean`, and input
  digest `4924688d4af7da6bbbe7f11a87acbef55f5ed81d56086768b1d16af5bb69b4ba`.
  `git diff --check` and the clean-worktree check also passed.

The observed `NO-SOURCE` tasks are undeclared Java/resource source kinds, while
synthetic SwiftPM and unsupported non-iOS XCFramework family tasks are expected
plugin branches rather than omitted declared tests. No executed JVM, arm64 iOS
Simulator, or sample test was skipped. There is no public API/ABI, Maven
coordinate, wire-byte, platform-floor, or publication-layout change. Physical
platform behavior and all six external validation campaigns remain pending.

The first protected `complete-gate` attempt for PR
[#88](https://github.com/p2pKit/P2pKit/pull/88), run
[`31600157407`](https://github.com/p2pKit/P2pKit/actions/runs/31600157407),
failed in the signed Central bundle entry-point test after its Gradle
publication and all 15 artifact-shape checks had passed. Under `pipefail`, the
signature-status parser stopped reading as soon as it found `VALIDSIG`, which
could give the upstream `printf` a broken pipe when GPG returned a sufficiently
large trailing status stream. The release-script correction consumes the full
stream while retaining the first fingerprint; its regression supplies 20,000
trailing status records, and the disposable-key integration test passes the
real signed bundle, signatures, checksums, manifest, and secret-safety checks.
The replacement hosted result will be recorded only after it completes.

## Pull request audit

| PR | Classification | Decision |
| --- | --- | --- |
| [#46 — synchronize manualPeerIds](https://github.com/p2pKit/P2pKit/pull/46) | Superseded by the stronger atomic `TrackedPeer` architecture on `main`; focused registry tests pass. | Closed with explanation; authorship/history remains in the PR. |
| [#49 — upload-artifact 7.0.1](https://github.com/p2pKit/P2pKit/pull/49) | Applicable dependency maintenance. Exact-base `complete-gate`, dependency review, and both OSV checks passed. | **Merged** normally through the protected PR path as `7c7f468b7f270f554518b3cf0586889262922378`. |
| [#50 — checkout 7.0.1](https://github.com/p2pKit/P2pKit/pull/50) | Applicable dependency maintenance. Its pinned action update was applied as commit `6e49e39` with Dependabot authorship preserved and passed the combined complete release gate. | Integrated through PR #60; the redundant single-update PR closed with commit-specific evidence and its branch was removed. |
| [#51 — dependency-review-action 5.0.0](https://github.com/p2pKit/P2pKit/pull/51) | Applicable security-workflow maintenance. Its pinned action update was applied as commit `06b2917` with Dependabot authorship preserved and passed the combined complete release gate. | Integrated through PR #60; the redundant single-update PR closed with commit-specific evidence and its branch was removed. |
| [#52 — AndroidX core 1.19.0](https://github.com/p2pKit/P2pKit/pull/52) | The raw branch mixed an AndroidX bump with host-specific lock churn and incomplete verification metadata. Curated replacement [#64](https://github.com/p2pKit/P2pKit/pull/64) normalized locks/metadata and passed Android plus complete-gate verification. | **Closed as superseded.** Replacement merged as `7a2351c1ac29c91690fa574d7c58925241af3f8e`. |
| [#53 — kotlinx-serialization-json 1.11.0](https://github.com/p2pKit/P2pKit/pull/53) | The runtime/KMP update was hardened with canonical vectors, malformed-input/privacy tests, diagnostics redaction, verified artifacts, locks, and isolated consumers in [#68](https://github.com/p2pKit/P2pKit/pull/68). | **Closed as superseded.** Replacement merged as `090f672d1bcb883468c0a231844bf64ce174aa0b`; its exact tree passed the complete gate. |
| [#54 — Android Compose BOM 2026.06.01](https://github.com/p2pKit/P2pKit/pull/54) | Curated replacement [#65](https://github.com/p2pKit/P2pKit/pull/65) coordinated BOM, Activity, Lifecycle, compile/runtime graphs, locks, and verification metadata instead of accepting the raw cross-host churn. | **Closed as superseded.** Replacement merged as `67411fe5aa03fbf09557dda80d3d2acbc4b5a130`. |
| [#55 — JetBrains Compose 1.11.1](https://github.com/p2pKit/P2pKit/pull/55) | Curated replacement [#67](https://github.com/p2pKit/P2pKit/pull/67) verified plugin/Skiko artifacts, cross-host locks, Desktop packaging, and Ubuntu/Windows compatibility. | **Closed as superseded.** Replacement merged as `ded15735b58ff11fc7c726f6e3924edfccc1ec0f`. Manual headful observation remains an external validation campaign, not a dependency-merge claim. |
| [#56 — Kotlin 2.4.10](https://github.com/p2pKit/P2pKit/pull/56) | Curated replacement [#69](https://github.com/p2pKit/P2pKit/pull/69) preserved the iOS 14 floor and published module identities, migrated ABI configuration, verified KLIB/XCFramework minimum OS, normalized locks/metadata, and reran publication consumers. | **Closed as superseded.** Replacement merged as `7bedf1c1032d7787355934517a793c83c754dc77`; complete gate [31283943878](https://github.com/p2pKit/P2pKit/actions/runs/31283943878) passed on the identical tree. |
| [#57 — setup-gradle 6.3.0](https://github.com/p2pKit/P2pKit/pull/57) | Applicable build-action maintenance. Its pinned action update was applied as commit `0b57655` with Dependabot authorship preserved and passed the combined complete release gate. | Integrated through PR #60; the redundant single-update PR closed with commit-specific evidence and its branch was removed. |
| [#58 — setup-java 5.7.0](https://github.com/p2pKit/P2pKit/pull/58) | Applicable build-action maintenance. Its pinned action update was applied as commit `9f7b865` with Dependabot authorship preserved and passed the combined complete release gate. | Integrated through PR #60; the redundant single-update PR closed with commit-specific evidence and its branch was removed. |
| [#59 — public repository reorganization](https://github.com/p2pKit/P2pKit/pull/59) | Production-grade layout, documentation, sample, and release-tooling consolidation; no published API, coordinates, protocol, or tag rewrite. | **Merged** normally through the protected path as `98a210e3572ad59b9256cf2ba3113f7b9a912099`; its temporary branch was deleted. |
| [#60 — final consolidation and validation handbook](https://github.com/p2pKit/P2pKit/pull/60) | Canonical Apache license, July evidence disposition, operational six-area validation handbook, final branch/GitHub audit, and four pinned action updates. All four required checks passed on exact head. | **Merged** normally through the protected path as `0a6c6bac28f9f99bab96d3753992994b867d6dad`; its temporary branch was deleted. |
| [#70 — harden JVM and Android LAN binding and recovery](https://github.com/p2pKit/P2pKit/pull/70) | Deterministic JVM/Android LAN bind selection, bounded JmDNS construction, serialized rebind ownership, metadata-free Android removal, and host-driven sample foreground restoration. Focused platform/publication checks and the complete gate passed on the exact PR tree. | **Merged** normally through the protected path as `8bf8aec4eb1901bde17098bdc7bcf82545bb1d64`; its temporary branch was deleted. Issues #42 and #47 closed, while hardware-dependent LAN issues remain open pending their required evidence. |
| [#71 — LAN merge evidence](https://github.com/p2pKit/P2pKit/pull/71) | Documentation-only exact-tree evidence for PR #70 and its still-external hardware requirements. The CI classifier selected the lightweight path. | **Merged** normally as `e9b372f501705413d80218e950a31c2666f38a65`; its temporary branch was deleted. |
| [#72 — Apple LAN recovery](https://github.com/p2pKit/P2pKit/pull/72) | Browser-generation endpoint ownership, path/lifecycle coalescing, symmetric Network.framework policy, terminal write-ready cleanup, deterministic Apple tests, and an evidence-backed iOS UI input correction. All required security, cross-host, and complete-gate checks passed on exact head `0a8209d0ab9980eaa1eff003a3d83ce92ef51f62`. | **Merged** normally as `35305d251198aebdba436ee77b696ce60ccb8b50`; its tree `02c86aac80cfabcf69da44abee35ae329b44ba49` is identical to the tested PR tree. Physical Apple evidence remains pending. |
| [#79 — harden file transfer terminal ownership](https://github.com/p2pKit/P2pKit/pull/79) | The initial focused ownership corrections were retained with authorship in the larger #80 branch. Its first hosted boundary exposed additional cancellation/error-classification work rather than being accepted as the end of the workstream. | GitHub records it merged because #80 integrated its commits; #80 is the authoritative complete implementation and verification boundary. |
| [#80 — complete file transfer lifecycle hardening](https://github.com/p2pKit/P2pKit/pull/80) | Completed source/destination ownership, bounded callback/control/source/cleanup behavior, durable receiver finalization, cancellation/error classification, sample cleanup, and deterministic cross-platform regressions without changing public ABI or wire bytes. | **Merged** normally as `dcb537f0088653c4c3652aad6b3fbb8c2ed40698`. Complete gate [31429345786](https://github.com/p2pKit/P2pKit/actions/runs/31429345786) passed on head `5c5961538e673026b4dae22b4e4666325d43ca50`; merge and head share tree `9c36cc3b7a41ae6b9aa34a2f213f814a28ec53c8`. |
| [#81 — harden core session lifecycle and diagnostics](https://github.com/p2pKit/P2pKit/pull/81) | Failure-isolated logging, deterministic setup/incoming/terminal/reconnect/feature ownership, bounded refresh/start settlement, post-terminal delivery prevention, collector recovery, peer-error reconnect handling, and deep `MessageId` immutability. | **Merged** normally as `a7d8ebfbdc945b5d1ab3db1c51daed1d4f30cc1f`. Complete gate [31472464571](https://github.com/p2pKit/P2pKit/actions/runs/31472464571) passed on head `145fa607be33c665de88b057f240ca89742922e7`; both share tree `b1cacff7cc4884e5d1c8a0e2f1b2dec2a97ceff8`. |
| [#82 — harden LAN resource ownership](https://github.com/p2pKit/P2pKit/pull/82) | Completed JVM/Android native-handle ownership, bounded JmDNS construction, cancellation/orphan cleanup, selected-network routing, and deterministic callback/resource regressions. | **Merged** normally as `e64c833fd9759f529df212122583ec3bd4edba1f`. Replacement complete gate [31486056226](https://github.com/p2pKit/P2pKit/actions/runs/31486056226) passed on head `a88d033801c03b430c5067776d941e099471a541`; merge and head share tree `25f6a53342759ec3b9bb134fb759e733f2301b35`. |
| [#83 — make LAN discovery delivery convergent](https://github.com/p2pKit/P2pKit/pull/83) | Replaced lossy discovery event buffers with a state-backed relay, made source failure/completion withdrawal deterministic, and retired Apple endpoint/relay generations atomically on stop. | **Merged** normally as `ba418189b7fc3033ac4f3e51932b83f7407bf323`. Replacement complete gate [31497583675](https://github.com/p2pKit/P2pKit/actions/runs/31497583675) passed on head `78b0e4249f031fd24af4d98be87a1894b0512c2e`; merge and head share tree `3fc254c5aa6f69e243a81df375cfde1048e56345`. |
| [#84 — harden provisioning lifecycle and native ownership](https://github.com/p2pKit/P2pKit/pull/84) | Made operations manager-owned across Android, JVM, and Apple; serialized Android binding/rebinding and cleanup ownership; hardened validation, permissions, cancellation, and typed failure handling. | **Merged** normally as `fc1f6f92e6eb52573ef6f9034102d9d288d7a2bf`. Complete gate [31514113705](https://github.com/p2pKit/P2pKit/actions/runs/31514113705) passed on head `dadfc66307353c95d865f2835eca0d2d89d3eb84`; merge and head share tree `61cc2e6684ea0fce804bf7bedf2b02006fec0b73`. |
| [#85 — harden secure protocol ownership and parsing](https://github.com/p2pKit/P2pKit/pull/85) | Closed post-handshake lease ownership, duplicate JSON-field acceptance, cancellation misclassification, and wall-clock reassembly-expiry gaps without changing approved wire bytes. | **Merged** normally as `0b267fa97dc09a573d3a7fb1e00416a5d5d16c12`. Complete gate [31524495713](https://github.com/p2pKit/P2pKit/actions/runs/31524495713) passed on head `701612ef2daa222376fc953e6a739da0f4e9ed04`; merge and head share tree `c944e628ac95f703a80277d2038f0daa56981013`. |
| [#86 — harden core discovery admission and publication](https://github.com/p2pKit/P2pKit/pull/86) | Validated and bounded third-party discovery events, normalized provenance, capped retention, and generation-ordered peer publication with deterministic hostile-input and concurrency coverage. | **Merged** normally as `f8cf629d7209fdb6dc321c180123d26028ae63d7`. Complete gate [31531533715](https://github.com/p2pKit/P2pKit/actions/runs/31531533715) passed on head `90d50e83ad16419061fd5964f438b1baa09173ec`; merge and head share tree `d93b3d5598bc13037dd802aeeac7dfdad57231ab`. |
| [#87 — harden core lifecycle and persistent identity](https://github.com/p2pKit/P2pKit/pull/87) | Made startup and observer acquisition cancellation-safe, bounded and strictly decoded persisted identities, validated wire-bound local identity, and bounded transient process-lock registries. | **Merged** normally as `a99a890c2208e33fe413869a424b60dacadca71f`. Complete gate [31542848494](https://github.com/p2pKit/P2pKit/actions/runs/31542848494) passed on head `f699c232075b923faa69b3f5a4f8fb2e95842db1`; merge and head share tree `0c42da2bbfe80727705a4d69977021df689f28d8`. |

The recently closed, unmerged PRs were #46, whose stronger replacement is
documented above, and #50, #51, #57, and #58, whose exact updates and authorship
were preserved through PR #60. No closed/unmerged PR contained additional
production work requiring recovery. PRs #52–#56 are now closed as superseded
by curated PRs #64, #68, #65, #67, and #69 respectively. Each replacement
resolved its complete dependency graph, locks, and verification metadata
without bypassing fail-closed checks; no raw Dependabot branch remains live.

## Live GitHub configuration audit — 2026-08-09

After PR #72, a fetched/pruned audit found no open pull requests and only
`main` on the canonical remote. The two active rulesets protect `main` from
deletion/non-fast-forward updates and require a pull request plus
`complete-gate`, dependency review, and both OSV contexts; `v*` tags are
protected from deletion and non-fast-forward updates. Those protections were
not bypassed or weakened.

All nine registered workflows remain current: CI, dependency review,
dependency submission, Desktop cross-host, OSV advisory scanning, Maven
Central publication/dry-run/namespace verification, and Dependabot updates.
The sole stale live reference was the CI push trigger for deleted
`remediation/**` branches; the final cleanup removes it and locks that absence
in the workflow regression test. Historical branch names inside the archive
remain provenance, not live instructions.

The only GitHub environment is `maven-central`, restricted to `v*` tags and a
required owner review with administrator bypass disabled at the environment
level. It contains exactly the four publication secret names and two
non-secret rotation/fingerprint variables required by the release workflow;
there are no repository-level secrets or variables. No credential value was
read, changed, or exposed during this audit.
