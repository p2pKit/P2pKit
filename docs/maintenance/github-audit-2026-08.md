# GitHub issues and pull requests audit — 2026-08-08

This audit compares every open issue and pull request, plus recently closed
unmerged pull requests, with `main` after `0.7.0-rc2`. GitHub remains the live
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
| [#21 — idle discovered peer disappears on Android](https://github.com/p2pKit/P2pKit/issues/21) | Transport-managed discovery lifetime, heartbeat/reconciliation, rebind coordination, and structured discovery diagnostics now prevent the old core-only 15-second eviction path. | Reproduce a long idle Android session on multiple real devices and prove JmDNS/service cache and UI retention/removal behavior from logs. | **Medium.** Physical Android hardware. Execute `LAN-T01`/Android long-idle matrix; fix only if evidence identifies a remaining layer. |
| [#23 — iOS stale Bonjour endpoint after peer restart](https://github.com/p2pKit/P2pKit/issues/23) | Commit `d6efe08` gives cached endpoints immutable browser-generation leases, replaces them on each accepted update, clears them before browser/path ownership changes, and conditionally removes only the failed lease so a concurrent fresh result survives. | Prove peer-restart timing on devices. The first stale attempt can still consume the evidence-dependent 10-second Apple connect ceiling; the fix prevents that failed lease from remaining dialable or deleting a newer endpoint. | **High.** Apple devices/AWDL. Execute `LAN-T07` restart/path cases and retain both-peer endpoint-generation/timing evidence. |
| [#25 — JVM/macOS no-address JmDNS.create trap](https://github.com/p2pKit/P2pKit/issues/25) | Commit `d21d065` removes the no-argument path, selects one deterministic explicit multicast-capable LAN address, excludes loopback/tunnel/virtual/container interfaces, watches the complete eligible topology, and rebinds through the serialized coordinator. | Prove Mac↔Android and Linux↔mobile discovery plus interface rotation on two physical machines; the implementation now fails visibly rather than binding an unsafe platform default when no eligible LAN exists. | **High.** External macOS/Linux/network evidence. Execute `ENV-02` and retain interface/PCAP evidence. |
| [#26 — Android hotspot host may bind cellular](https://github.com/p2pKit/P2pKit/issues/26) | Commit `d21d065` uses an explicit Wi-Fi/Ethernet `Network` when available and otherwise selects a private IPv4 only from known AP/tether Java interfaces. The system-default callback is change detection only and can never become the bind fallback. | Prove AP/tether names, multicast readiness, and route behavior across representative OEM kernels; AP-client isolation remains outside application control. | **High.** OEM/hotspot hardware. Run the Android provisioning/LAN matrix with `dumpsys`, `ip addr`, both-peer logs, and PCAP evidence. |
| [#27 — iOS hotspot rebind/foreground storm](https://github.com/p2pKit/P2pKit/issues/27) | Commit `d6efe08` includes `nw_interface_type_other` in the path fingerprint and coalesces WillEnterForeground/DidBecomeActive into one inactive episode. A successful path rebind while inactive satisfies that episode, preventing a second foreground port rotation. | Personal Hotspot path classification and notification timing still need physical-device proof across iOS versions. | **Medium.** Apple device/Personal Hotspot. Run `LAN-T07` repeated enable/foreground cases and prove at most one completed rebind per inactive episode. |
| [#28 — Android address order may select VPN](https://github.com/p2pKit/P2pKit/issues/28) | Selection uses a Wi-Fi/Ethernet `Network`, `LinkProperties`, routable-address filtering, and shared network state rather than the first process-global address. | Validate VPN plus Wi-Fi/hotspot combinations on real OEM devices and prove both discovery and TCP stay on the chosen LAN. | **High.** Physical VPN/network matrix. Execute `LAN-T01` with PCAP/dumpsys evidence. |
| [#29 — Android rebind cancellation race](https://github.com/p2pKit/P2pKit/issues/29) | `JmdnsLifecycleCoordinator` serializes transitions and performs non-cancellable rollback/close before recreate. | Reproduce rapid callback/close storms on hardware and prove no zombie listener or overlapping JmDNS generation remains. | **Medium.** Hardware timing. Add any missing Android-host concurrency seam, then run 50-toggle stress. |
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
| [#43 — Android serviceRemoved has null ServiceInfo](https://github.com/p2pKit/P2pKit/issues/43) | Commit `d21d065` owns admitted instance-name→peer mappings by listener generation and adds deterministic Android host tests for metadata-free removal, stale/current generation ownership, and terminal drain. | Prove the real null/stub-info callback shape and eviction timing under graceful stop, force-stop, and packet loss on physical devices. | **Medium.** Hardware confirmation. Run `LAN-T01` add/remove churn and retain both-peer logs. |
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
wire formats, the iOS deployment floor, or published `0.7.0-rc2` artifacts.
Android OEM multicast/callback behavior, Mac/Linux interface rotation, and
hostile-network timing remain external evidence requirements and are not
claimed as verified here.

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

No public ABI, Maven coordinate, secure-v2/LAN wire format, iOS library floor,
or published `0.7.0-rc2` artifact changes. Real AWDL, Personal Hotspot,
Control Center/system interruption, device lock/background, peer restart,
path rotation, and timeout histograms remain required external evidence; none
is claimed as verified by simulator or host checks.

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

The recently closed, unmerged PRs were #46, whose stronger replacement is
documented above, and #50, #51, #57, and #58, whose exact updates and authorship
were preserved through PR #60. No closed/unmerged PR contained additional
production work requiring recovery. PRs #52–#56 are now closed as superseded
by curated PRs #64, #68, #65, #67, and #69 respectively. Each replacement
resolved its complete dependency graph, locks, and verification metadata
without bypassing fail-closed checks; no raw Dependabot branch remains live.
