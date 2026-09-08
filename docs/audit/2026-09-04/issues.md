# Issue disposition index

Checkpoint inventory: **182 issues; 71 reviewed repository repairs (39.0%), 111 remaining rows (61.0%)**.

This dated ledger is not GitHub live state, effort or production readiness. Issues remain open at their recorded
list/individual observations; none was closed by these fixes. #223 is independently APPROVED/pushed at
`8dd65ce3f4e8`; [its Linux checkout/policy report](repairs/223.md) preserves exact source/evidence bindings.
Thirteen final static/policy/range gates pass; no new product Gradle check is inferred. #368 remains approved
at `c221d54b549d`; [its source-bound product passes and prior failures](repairs/368.md) stay source-bound.
#367 remains approved at `0d88be3e3769`; [its original full-check failures](repairs/367.md) remain historical
and Windows/Intel acceptance unexecuted. #145/#144/#360 and earlier approvals are unchanged. Active facility
source731/tree6b259 is independently **APPROVED**, locally committed, not established as pushed/hosted-executed
here. [Its report](hosted-validation.md) separately binds the fresh precommitLinux1607-case check/sample/Dokka
result at6a32+stageda95 and laterclean731rootcheck/CLI/Desktop1607/199XML/205tasks, independently
corroborated; scopes are not interchangeable. Planned #268 is **NOT_STARTED**, after any actually reproduced
prerequisites and their sequential independent reviews. The unnumbered facility adds no approved issue row.
Pending repairs: **88 Low and one informational (#333)**. There are **49 new-audit findings**.

The earlier **12:28:25 UTC** all-state list observes289issues/182open/79PRs(7open), not fresh full histories.
The exhaustive 10:24–10:30 capture remains 288 issues/181 open/79 PRs: all 367 issue-style histories and
79 PR metadata sets freshly fetched, 1,519 GETs, no reused current histories. #368's individual 10:50:42 addition
and #367/#368 outcomes remain historical; #223's 12:36:30 outcome is also individual, not a post-write full refresh.
Latest fresh local capture **16:02:38–16:08:26UTC**:289issues/182open/79PRs(7open), all368 local histories/
79PR collections fresh; zero reuse. All182open IDs reconcile.117first-hop upstream PRs were captured;109count-
complete, eight still lack7reported inline/3conversation records.2927GETall200,402local/33upstream patch
fields omitted. The16:33:33Actions/ref idle point is not an execution lease; refresh before any trigger.
Later18:28freshlists remain identical;all368histories/79PRsetsREUSED16:02–16:08, not new18hcomments/
timelines.18:28:51idle/refpoint is not prepushidleproof/lease. Initialcollectorerror retained;correctedcapture
succeeds,all28HTTP200. Earlier captures/row states unchanged. See [checkpoint metadata](checkpoint.json)
and [the facility report](hosted-validation.md) for exact bindings/limitations.
#133 independent interoperability stays NOT_STARTED; external acceptance on approved rows is not counted complete.
#325's protected-AGENTS exception remains. #240 dependency `0` was a parser mistake (`transport #0` in the body),
not a GitHub issue; its removal is not a product repair, new finding or count change. Likewise, the old368
checkpoint pointer now names `previousAffectedGateAttempt368`; original text/history are retained. This narrow
administrative correction does not modify a product outcome, the original223 assessment or a repair count.

Read [full records](issues.json), [root handoff](../../../AUDIT_CHECKPOINT.md) and
[unverified follow-ups](followups.md). Historical assessments retain original scope; the old #360 assessment's
then-pending #223 note is superseded by the current #223 record, not rewritten. Overall **NOT_READY**.
GitHub Actions authorization is not an executed hosted/external gate. Severity `SEE_FULL_ISSUE` is an inherited
gap, not a new severity assignment. A blank revision means no completed repair/review cycle was recorded.

## Repairs with recorded independent approval (71)

| Issue | Severity at checkpoint | Origin | Last recorded fix/revision |
| --- | --- | --- | --- |
| [#130: [WSE-02] Both provisioning test registrars discard expectedFingerprint — pin propagation is untested](https://github.com/p2pKit/P2pKit/issues/130) | low | Existing | `1847ed330e3a` |
| [#133: [WSG-02] No cross-implementation or cross-version interop test exists anywhere](https://github.com/p2pKit/P2pKit/issues/133) | medium | Existing | `71276169a7d0` |
| [#135: [WSF-04] Desktop UI sample uses the risky policy and auto-mesh with zero warning anywhere](https://github.com/p2pKit/P2pKit/issues/135) | medium | Existing | `2386057d5721` |
| [#137: [WSD-02] Four P2pError variants expose a mutable non-volatile `underlying` slot behind `cause`](https://github.com/p2pKit/P2pKit/issues/137) | low | Existing | `a5d3145d9cfb` |
| [#138: [WSG-01] Kit/session integration tests do not exercise fragmented raw reads](https://github.com/p2pKit/P2pKit/issues/138) | medium | Existing | `02acee835200` |
| [#141: [WSG-12] CI runs full `check` on macOS only; Windows/Linux defect class is invisible](https://github.com/p2pKit/P2pKit/issues/141) | high | Existing | `d859e20252d2` |
| [#142: [BUILD-26] resolveAndLockAll write-locks guard is bypassable via task-name matching](https://github.com/p2pKit/P2pKit/issues/142) | low | Existing | `639167cc1432` |
| [#143: [BUILD-13] Four workflows persist GITHUB_TOKEN in .git/config (persist-credentials missing)](https://github.com/p2pKit/P2pKit/issues/143) | medium | Existing | `d18500c939bf` |
| [#144: [BUILD-18] Docs-only CI shortcut reuses main-merge results from graph shape, not check evidence](https://github.com/p2pKit/P2pKit/issues/144) | low | Existing | `6995130bcdb2` |
| [#145: [WSA1-05] Receive-backlog byte cap allocates a full payload copy to measure and under-counts heap](https://github.com/p2pKit/P2pKit/issues/145) | low | Existing | `0423e96e15c8` |
| [#146: [WSG-04] Shared createTestKit fixture leaves most kit-level tests on the legacy plaintext path](https://github.com/p2pKit/P2pKit/issues/146) | medium | Existing | `ee75358d1a74` |
| [#151: [BUILD-53] SBOM content gate never runs against the bytes uploaded to Maven Central](https://github.com/p2pKit/P2pKit/issues/151) | medium | Existing | `79ec60f50419` |
| [#152: [BUILD-64] Android-ABI task-graph dry-run has one unasserted caller; removable with a green CI](https://github.com/p2pKit/P2pKit/issues/152) | low | Existing | `27fec6a2268a` |
| [#157: [BUILD-65] iosX64Test and Android instrumented tests never execute; the skip is silent](https://github.com/p2pKit/P2pKit/issues/157) | medium | Existing | `3889e44c1152` |
| [#160: [F-15] LAN advertisement can publish SRV port 0 when read mid listener-detach](https://github.com/p2pKit/P2pKit/issues/160) | medium | Existing | `6d92bde87b5a` |
| [#161: [F-16] stopNetworkWatcherNow() throws out of idle teardown, stranding the Wi-Fi multicast lock](https://github.com/p2pKit/P2pKit/issues/161) | medium | Existing | `11a44c6bb70c` |
| [#171: [WSA2-07] startFeature is a 262-line inline transaction whose cancellation flag misses a settlement window](https://github.com/p2pKit/P2pKit/issues/171) | medium | Existing | `2ea1060b1b9a` |
| [#175: [WSB-08] JVM sendFile(File) reopens by path with no file-identity binding (detected post-transmission)](https://github.com/p2pKit/P2pKit/issues/175) | medium | Existing | `a0d074c32206` |
| [#186: [WSD-03] Handshake interpolates a whole ProtocolEvent, leaking unfiltered peer payload into error messages](https://github.com/p2pKit/P2pKit/issues/186) | medium | Existing | `ceaf028263c0` |
| [#187: [WSD-06] NOT_IN_V01 leaks into Kotlin/Native ABI without cross-target baseline parity](https://github.com/p2pKit/P2pKit/issues/187) | medium | Existing | `bf3932eece77` |
| [#190: [WSD-12] Value-class mangling makes the identity surface (and the builder's appId) unreachable from Java](https://github.com/p2pKit/P2pKit/issues/190) | medium | Existing | `d9b900171bcf` |
| [#194: [WSE-08] Android LOHS support predicate omits FEATURE_WIFI](https://github.com/p2pKit/P2pKit/issues/194) | medium | Existing | `e39153eec3f1` |
| [#196: [WSE-14] WifiManagerWrapperImpl adapter untested; no Robolectric/instrumented tier exists to test it](https://github.com/p2pKit/P2pKit/issues/196) | medium | Existing | `5ac78f9d55e1` |
| [#197: [WSF-09] Sample console/logcat paths print chat message bodies, peer names and full peer ids unredacted](https://github.com/p2pKit/P2pKit/issues/197) | medium | Existing | `3f596b1de5ab` |
| [#198: [WSE-12] Stale hotspot-stop callback can overwrite a newer successful join](https://github.com/p2pKit/P2pKit/issues/198) | medium | Existing | `20a6dcdd19db` |
| [#199: [WSF-10] Samples do not demonstrate pinning discovered peers or displaying local pairing QR](https://github.com/p2pKit/P2pKit/issues/199) | medium | Existing | `62dedfaad288` |
| [#202: [WSF-08] iOS sample turns on console mirroring of every transport event with no DEBUG gate or reset](https://github.com/p2pKit/P2pKit/issues/202) | medium | Existing | `ec248178eb62` |
| [#203: [WSF-07] JVM samples flip the library's off-by-default LAN/frame traces on (CLI has an opt-out, Desktop UI has none)](https://github.com/p2pKit/P2pKit/issues/203) | medium | Existing | `fc3c14b2c367` |
| [#208: [WSH-06] local.md fast-gate list omits check-markdown-links.sh and git diff --check (CI runs both)](https://github.com/p2pKit/P2pKit/issues/208) | low | Existing | `3a96a775c379` |
| [#214: [WSH-10] Operational limits documented only in internal source; one of ~40 reaches docs/](https://github.com/p2pKit/P2pKit/issues/214) | medium | Existing | `68170b99a2e7` |
| [#223: [BUILD-25] .gitattributes pins gradlew.bat line endings but leaves gradlew to core.autocrlf](https://github.com/p2pKit/P2pKit/issues/223) | low | Existing | `8dd65ce3f4e8` |
| [#225: [BUILD-33] Version pins duplicated as literals in 4 policy scripts; 10 of 12 sites are deliberate tripwires](https://github.com/p2pKit/P2pKit/issues/225) | low | Existing | `46ed124ded59` |
| [#226: [BUILD-43] review-dependency-verification.sh hardcodes /tmp, ignoring TMPDIR (mktemp+trap intact)](https://github.com/p2pKit/P2pKit/issues/226) | low | Existing | `f085dc8a59f6` |
| [#228: [BUILD-44] iOS launcher lock leaks on EVERY run (trap reads main's local under set -u); mkdir IS atomic](https://github.com/p2pKit/P2pKit/issues/228) | medium | Existing | `d4be234161a5` |
| [#229: [F-03] Lossy JmDNS UTF-8 decode makes isWellFormedLanText vacuous; iOS decodes strictly](https://github.com/p2pKit/P2pKit/issues/229) | low | Existing | `6d9cd3c74724` |
| [#289: [WSF-17] Filename-collision claim duplicated 4x in samples; iOS copy overwrites instead of suffixing](https://github.com/p2pKit/P2pKit/issues/289) | medium | Existing | `7f5f2d844e21` |
| [#313: [WSF-23] DiagnosticRedactor passes details["line"] through the weaker text path; instance= ids survive](https://github.com/p2pKit/P2pKit/issues/313) | low | Existing | `0bfa94481a3a` |
| [#317: [WSF-25] Android diagnostics recomposition-trigger read is inert: unread `by` delegate never subscribes](https://github.com/p2pKit/P2pKit/issues/317) | low | Existing | `f273b1b98e95` |
| [#320: [AUDIT] Sample receivers can delete files after post-publication commit failure](https://github.com/p2pKit/P2pKit/issues/320) | medium | New audit | `33dbe3844d6e` |
| [#321: [AUDIT] Android sample leaks process-global LAN diagnostics enablement](https://github.com/p2pKit/P2pKit/issues/321) | medium | New audit | `61484e1f0f53` |
| [#323: [AUDIT] Rolling JSONL rotation ignores failures and can exceed its disk bound](https://github.com/p2pKit/P2pKit/issues/323) | low | New audit | `e5ee1bfb71b0` |
| [#324: [AUDIT] Android sample persists and exposes hotspot passphrases](https://github.com/p2pKit/P2pKit/issues/324) | medium | New audit | `e392c13cfe83` |
| [#325: [AUDIT] Setup prerequisites omit Android Platform 37 required by the sample](https://github.com/p2pKit/P2pKit/issues/325) | medium | New audit | `6ebfb9f81de4` |
| [#328: [AUDIT] Samples key session-scoped transfer IDs as process-global IDs](https://github.com/p2pKit/P2pKit/issues/328) | medium | New audit | `852a088e3f70` |
| [#332: [AUDIT] LAN discovery retains stale peers after invalid re-resolution (JVM, Android, Apple)](https://github.com/p2pKit/P2pKit/issues/332) | medium | New audit | `78ef36142fe7` |
| [#334: [AUDIT] Dependency verifier cannot approve Gradle plugin marker updates](https://github.com/p2pKit/P2pKit/issues/334) | medium | New audit | `d1a93d025485` |
| [#335: [AUDIT] Dependency verifier rejects valid issuer-key-ID-only OpenPGP signatures](https://github.com/p2pKit/P2pKit/issues/335) | medium | New audit | `d6d8585e39a2` |
| [#336: [AUDIT] Late terminal diagnostic callbacks retire replacement SDK sessions](https://github.com/p2pKit/P2pKit/issues/336) | medium | New audit | `df4c042f3e90` |
| [#337: [AUDIT] Android provisioning cards retain success after system stop or network release](https://github.com/p2pKit/P2pKit/issues/337) | medium | New audit | `170cc86b652d` |
| [#338: [AUDIT] Cancelling a queued provisioning operation clears another acquisition’s state](https://github.com/p2pKit/P2pKit/issues/338) | medium | New audit | `5ac5f1ef7350` |
| [#339: [AUDIT] Initial Wi-Fi binding and cancellation close acquire native monitors in opposite order](https://github.com/p2pKit/P2pKit/issues/339) | high | New audit | `9a694307a6a9` |
| [#340: [AUDIT] Canceled JmDNS network samples can replace newer or restarted bindings](https://github.com/p2pKit/P2pKit/issues/340) | medium | New audit | `ffea091775ce` |
| [#343: [AUDIT] Dependency provenance review rejects valid signatures under a UTF-8 locale](https://github.com/p2pKit/P2pKit/issues/343) | medium | New audit | `0e8ea772cf5c` |
| [#344: [AUDIT] Dependency curator cannot locate signed Gradle sibling-version variant artifacts](https://github.com/p2pKit/P2pKit/issues/344) | medium | New audit | `7e3e02480bf1` |
| [#345: [AUDIT] Plugin metadata size guards allocate the whole file before rejecting oversized input](https://github.com/p2pKit/P2pKit/issues/345) | low | New audit | `7aa225e2d99a` |
| [#346: [AUDIT] iOS app launcher selects a scheme absent from the generated Xcode project](https://github.com/p2pKit/P2pKit/issues/346) | medium | New audit | `c5ad9da3aa4b` |
| [#348: [AUDIT] Dependency-submission action disables checksum verification for the Gradle build](https://github.com/p2pKit/P2pKit/issues/348) | medium | New audit | `c99d89cf95fa` |
| [#349: [AUDIT] SBOM XML gate accepts missing components and mismatched release metadata](https://github.com/p2pKit/P2pKit/issues/349) | low | New audit | `f7a0cdad8c5a` |
| [#350: [AUDIT] D3 fault campaign wrongly forbids receiver commit after acknowledgement loss](https://github.com/p2pKit/P2pKit/issues/350) | medium | New audit | `94b5ae04dcc0` |
| [#351: [AUDIT] File-transfer KDoc promises remote terminal outcomes without delivery guarantees](https://github.com/p2pKit/P2pKit/issues/351) | low | New audit | `ecdee2384c28` |
| [#352: [AUDIT] Selective diagnostic clearing can lose other-session history and misreport storage failures](https://github.com/p2pKit/P2pKit/issues/352) | low | New audit | `32dc5c036581` |
| [#353: [AUDIT] Android API24/25 diagnostics use API26 java.time and NIO without core-library desugaring](https://github.com/p2pKit/P2pKit/issues/353) | low | New audit | `44fdfeeb66a6` |
| [#354: [AUDIT] Android hotspot Retry restarts instead of retrying failed cleanup](https://github.com/p2pKit/P2pKit/issues/354) | low | New audit | `b6af5b8b78bd` |
| [#355: [AUDIT][Low] Terminal kit shutdown misreports inbound completion and retries closed acceptance](https://github.com/p2pKit/P2pKit/issues/355) | low | New audit | `182063131438` |
| [#356: [AUDIT][Low] Apple Bonjour aliases NUL-containing TXT keys into canonical fields](https://github.com/p2pKit/P2pKit/issues/356) | low | New audit | `183b6c917faf` |
| [#357: [AUDIT][Low] LAN watcher test races a real executor against a virtual timeout](https://github.com/p2pKit/P2pKit/issues/357) | low | New audit | `6d9cd3c74724` |
| [#358: [AUDIT][Low] Destination AuthenticationFailed escapes as ClassCastException and skips acceptance cleanup](https://github.com/p2pKit/P2pKit/issues/358) | low | New audit | `d424a23b00fb` |
| [#359: [AUDIT][Low] Caller cancellation during failed destination abort skips terminal settlement](https://github.com/p2pKit/P2pKit/issues/359) | low | New audit | `de882840e1e2` |
| [#360: [AUDIT][Low] All-tree CI whitespace gates reject immutable historical archives](https://github.com/p2pKit/P2pKit/issues/360) | low | New audit | `6995130bcdb2` |
| [#367: [AUDIT][Medium] Host-toolchain checksums omit Linux/Windows and Intel Native archives](https://github.com/p2pKit/P2pKit/issues/367) | medium | New audit | `0d88be3e3769` |
| [#368: [AUDIT][Low] API24 export-failure fixture targets an unnormalized filename on case-sensitive filesystems](https://github.com/p2pKit/P2pKit/issues/368) | low | New audit | `c221d54b549d` |

## Pending remediation (89)

| Issue | Severity at checkpoint | Origin | Last recorded fix/revision |
| --- | --- | --- | --- |
| [#156: [F-07] TCP_NODELAY is unset and transport liveness relies on core deadlines](https://github.com/p2pKit/P2pKit/issues/156) | low | Existing | — |
| [#158: [F-11] Inbound buffer depth diverges: 64 on JVM/Android (framework default) vs 16 on iOS](https://github.com/p2pKit/P2pKit/issues/158) | low | Existing | — |
| [#167: [WSA2-03] Discovery claim overwrites a pinned manual peer's display name (UI spoof, not auth bypass)](https://github.com/p2pKit/P2pKit/issues/167) | low | Existing | — |
| [#168: [WSA1-11] close() burns its full CLOSE-frame budget behind the rearm send gate](https://github.com/p2pKit/P2pKit/issues/168) | low | Existing | — |
| [#169: [WSA2-04] Discovery-rejection warning latches once per kit lifetime, hiding sustained attacks](https://github.com/p2pKit/P2pKit/issues/169) | low | Existing | — |
| [#172: [WSB-05] Staging .part file is created in the destination constructor, orphaned on reject/crash](https://github.com/p2pKit/P2pKit/issues/172) | low | Existing | — |
| [#173: [WSA2-05] PeerListStateFlow defeats StateFlow operator fusion](https://github.com/p2pKit/P2pKit/issues/173) | low | Existing | — |
| [#176: [WSB-06] Unverified partial file stages in the user-visible destination directory during transfer](https://github.com/p2pKit/P2pKit/issues/176) | low | Existing | — |
| [#184: [WSD-04] PeerAuthorizationPolicy sealed hierarchy has no documented evolution contract](https://github.com/p2pKit/P2pKit/issues/184) | low | Existing | — |
| [#188: [WSD-07] Recommended sendFile(PreparedFileSource) overload has an undocumented throwing interface default](https://github.com/p2pKit/P2pKit/issues/188) | low | Existing | — |
| [#191: [WSD-14] Swift receives P2pError through string-based NSError details](https://github.com/p2pKit/P2pKit/issues/191) | low | Existing | — |
| [#195: [WSE-07] Post-start Android permission loss is reported as a platform failure](https://github.com/p2pKit/P2pKit/issues/195) | low | Existing | — |
| [#205: [WSG-09] Reconnect tests disprove a 1000 ms retry with a 150 ms wall-clock delay](https://github.com/p2pKit/P2pKit/issues/205) | low | Existing | — |
| [#206: [WSG-13] Test port binding is ephemeral and already serialized; residue is one unguarded user.home site + a mirrored constant](https://github.com/p2pKit/P2pKit/issues/206) | low | Existing | — |
| [#207: [WSG-10] Warn/error teardown net armed in 1 of 34 kit-constructing suites; convention undocumented](https://github.com/p2pKit/P2pKit/issues/207) | low | Existing | — |
| [#209: [WSG-16] Fixture hangUp closes both directions; production collapses half-close, so the real gap is a transport test](https://github.com/p2pKit/P2pKit/issues/209) | low | Existing | — |
| [#211: [WSH-07] gradle.properties and build.gradle.kts point at a release doc that moved into docs/archive/](https://github.com/p2pKit/P2pKit/issues/211) | low | Existing | — |
| [#212: [WSH-08] Maintained specification.md delegates its design record into docs/archive/, which has a broken link](https://github.com/p2pKit/P2pKit/issues/212) | low | Existing | — |
| [#213: [WSH-11] Error taxonomy is Dokka-published but undocumented; only FileTransferFailed carries retryability](https://github.com/p2pKit/P2pKit/issues/213) | low | Existing | — |
| [#215: [WSH-09] Threat model lacks actor, asset, and trust-boundary structure](https://github.com/p2pKit/P2pKit/issues/215) | low | Existing | — |
| [#216: [WSH-13] Validation status restated by hand in 8 places; only the CLI/Desktop row actually diverges](https://github.com/p2pKit/P2pKit/issues/216) | low | Existing | — |
| [#217: [WSG-15] Admission-control test swallows a socket timeout into a sentinel that is never asserted](https://github.com/p2pKit/P2pKit/issues/217) | low | Existing | — |
| [#218: [WSG-07] runCatching{}.isFailure immutability assertions accept any throwable, not just rejection](https://github.com/p2pKit/P2pKit/issues/218) | low | Existing | — |
| [#219: [WSH-12] Public transport SPI lacks an integration and security contract](https://github.com/p2pKit/P2pKit/issues/219) | low | Existing | — |
| [#220: [WSG-17] Relay concurrency test collects after awaitAll; only the non-diff branch runs](https://github.com/p2pKit/P2pKit/issues/220) | low | Existing | — |
| [#230: [BUILD-54] Release metadata gate matches whole prose sentences via grep -F; two guards fail open](https://github.com/p2pKit/P2pKit/issues/230) | low | Existing | — |
| [#232: [F-09] DataTransport.start() documents "transports do not throw" but suspend cancellation must escape](https://github.com/p2pKit/P2pKit/issues/232) | low | Existing | — |
| [#235: [F-17] Post-cancellation socket read discards its result and rethrows into the platform default handler](https://github.com/p2pKit/P2pKit/issues/235) | low | Existing | — |
| [#236: [BUILD-73] "Every distributable archive carries the exact repository license" is broader than the gate](https://github.com/p2pKit/P2pKit/issues/236) | low | Existing | — |
| [#237: [BUILD-74] README gate list omits the CI test-target and local-artifact scope](https://github.com/p2pKit/P2pKit/issues/237) | low | Existing | — |
| [#239: [WSA2-11] FailureIsolatingP2pLogger isolates throws but not blocking; a slow logger can hang stop()](https://github.com/p2pKit/P2pKit/issues/239) | low | Existing | — |
| [#240: [WSA2-08] Observer-startup rollback error is stamped with transportFactories.first(), blaming an unrelated transport](https://github.com/p2pKit/P2pKit/issues/240) | low | Existing | — |
| [#241: [WSA2-09] NetworkPathCallbackState.begin() returns null unlogged; a declined path-observer restart is undiagnosable](https://github.com/p2pKit/P2pKit/issues/241) | low | Existing | — |
| [#243: [WSA1-13] markCleanlyClosed check-then-act outside the lock; KDoc contradicts rearmWith](https://github.com/p2pKit/P2pKit/issues/243) | low | Existing | — |
| [#245: [WSA1-14] Reconnect flaps accumulate uncancelled 30-second diagnostic watchdogs](https://github.com/p2pKit/P2pKit/issues/245) | low | Existing | — |
| [#247: [WSA1-17] Session close can compose seven 2-second waits without an aggregate deadline](https://github.com/p2pKit/P2pKit/issues/247) | low | Existing | — |
| [#248: [WSC-09] Android identity commit lacks an explicit directory-durability guarantee](https://github.com/p2pKit/P2pKit/issues/248) | low | Existing | — |
| [#249: [WSB-10] acceptData publishes then retracts bytesTransferred, breaking documented monotonic progress](https://github.com/p2pKit/P2pKit/issues/249) | low | Existing | — |
| [#250: [WSC-10/11] Identity storage serializes all namespaces through one process-global lock](https://github.com/p2pKit/P2pKit/issues/250) | low | Existing | — |
| [#252: [WSB-11] Outgoing progress counts submitted (not delivered) bytes; locking asymmetry undocumented](https://github.com/p2pKit/P2pKit/issues/252) | low | Existing | — |
| [#255: [WSA2-13] notifyAppBackgrounded fire-and-forget: no failure channel for consumers; cancellation skips discovery stop](https://github.com/p2pKit/P2pKit/issues/255) | low | Existing | — |
| [#256: [WSB-12] Android syncParentDirectory: throwing Os.close replaces the fsync failure (JVM uses use{})](https://github.com/p2pKit/P2pKit/issues/256) | low | Existing | — |
| [#260: [WSD-10] incoming collectors never complete on terminal transition; KDoc stops short of the consequence](https://github.com/p2pKit/P2pKit/issues/260) | low | Existing | — |
| [#261: [WSC-18] Lossy AppId sanitizer duplicated byte-identically in 3 source sets; collisions defused by hashed namespace](https://github.com/p2pKit/P2pKit/issues/261) | low | Existing | — |
| [#267: [WSD-05] Sealed-placement comment incorrectly calls the Kotlin 2.4.10 rule temporary](https://github.com/p2pKit/P2pKit/issues/267) | low | Existing | — |
| [#268: [WSD-19] P2pMessage.Binary.bytes copies the payload on every read; no public size accessor](https://github.com/p2pKit/P2pKit/issues/268) | low | Existing | — |
| [#271: [WSD-15] Config validation messages omit the offending value at 7 of 12 value-bearing sites](https://github.com/p2pKit/P2pKit/issues/271) | low | Existing | — |
| [#272: [WSD-18] Twelve hand-written public value types lack value-semantics regression tests](https://github.com/p2pKit/P2pKit/issues/272) | low | Existing | — |
| [#273: [WSD-20] PeerPairingQr never appears on the public API: both pairing ends are bare String](https://github.com/p2pKit/P2pKit/issues/273) | low | Existing | — |
| [#274: [WSD-21] ProvisioningContext: 10-arg constructor with 3 defaults freezes the factory SPI's ABI](https://github.com/p2pKit/P2pKit/issues/274) | low | Existing | — |
| [#275: [WSE-05] createManualPeer logs the manual host:port at INFO on all three platforms (default logger is NoOp)](https://github.com/p2pKit/P2pKit/issues/275) | low | Existing | — |
| [#276: [WSD-24] Post-close stopLocalNetwork() is a uniform no-op in all 4 managers; contract is undocumented](https://github.com/p2pKit/P2pKit/issues/276) | low | Existing | — |
| [#277: [WSE-09] Provisioning config: 3 of 4 fields never read; preferredSsidPrefix read but log-only](https://github.com/p2pKit/P2pKit/issues/277) | low | Existing | — |
| [#278: [WSE-11] Desktop poll loop swallows every Exception into NetworkState.Unknown with no escalation](https://github.com/p2pKit/P2pKit/issues/278) | low | Existing | — |
| [#279: [WSE-10] Desktop/iOS parent cancellation skips Closing and close has no deadline](https://github.com/p2pKit/P2pKit/issues/279) | low | Existing | — |
| [#281: [WSE-13] ProcessBindingArbiter global has no reset seam; one host test mutates it unguarded](https://github.com/p2pKit/P2pKit/issues/281) | low | Existing | — |
| [#282: [WSE-16] Android manual-address scanning is IPv4-only and duplicated from LAN selection](https://github.com/p2pKit/P2pKit/issues/282) | low | Existing | — |
| [#284: [WSE-18] joinLocalNetwork has no leave path: a joined network is unreleasable until close()](https://github.com/p2pKit/P2pKit/issues/284) | low | Existing | — |
| [#285: [WSF-11] samples.md and the CLI's own help omit the mandatory p2f1 fingerprint for `manual`](https://github.com/p2pKit/P2pKit/issues/285) | low | Existing | — |
| [#287: [WSE-19] requiredPermissions() omits three install-time Android permissions](https://github.com/p2pKit/P2pKit/issues/287) | low | Existing | — |
| [#288: [WSF-13] Android sample saves peer files to app-scoped external storage but logs "app-private"](https://github.com/p2pKit/P2pKit/issues/288) | low | Existing | — |
| [#290: [WSF-15] Desktop UI provisioning poll failures are silently discarded](https://github.com/p2pKit/P2pKit/issues/290) | low | Existing | — |
| [#291: [WSF-14] iOS sample inbox contents are backed up without an explicit policy](https://github.com/p2pKit/P2pKit/issues/291) | low | Existing | — |
| [#292: [WSG-14] 47 error-message substring assertions in 21 files; 32 are redundant, ~15 load-bearing](https://github.com/p2pKit/P2pKit/issues/292) | low | Existing | — |
| [#296: [WSH-14] validation-status.md files verified-but-non-evidentiary CI provenance under "Completed"](https://github.com/p2pKit/P2pKit/issues/296) | low | Existing | — |
| [#302: [WSA2-14] TrackedPeer.isManual has zero readers; its KDoc claims a derivation and an exemption it does not implement](https://github.com/p2pKit/P2pKit/issues/302) | low | Existing | — |
| [#306: [WSB-16] prepareFinish() error text says FILE_DONE on the authenticated FILE_FINISH path](https://github.com/p2pKit/P2pKit/issues/306) | low | Existing | — |
| [#307: [WSB-17] File-transfer resource-limit constants lack rationale documentation](https://github.com/p2pKit/P2pKit/issues/307) | low | Existing | — |
| [#309: [WSD-22] Eight public KDoc links target internal symbols](https://github.com/p2pKit/P2pKit/issues/309) | low | Existing | — |
| [#311: [WSD-23] create()'s @throws list omits duplicate transport registration (type is listed, cause is not)](https://github.com/p2pKit/P2pKit/issues/311) | low | Existing | — |
| [#312: [WSF-18] Desktop diagnostics report a keep-alive value the samples never configure](https://github.com/p2pKit/P2pKit/issues/312) | low | Existing | — |
| [#314: [WSF-19] iosApp scripts README teaches a manual Xcode phase setup that project.yml automates](https://github.com/p2pKit/P2pKit/issues/314) | low | Existing | — |
| [#316: [WSF-24] Diagnostics recorder exposes three unused pause APIs](https://github.com/p2pKit/P2pKit/issues/316) | low | Existing | — |
| [#322: [AUDIT] Per-session evidence reports recorder-lifetime dropped-event totals](https://github.com/p2pKit/P2pKit/issues/322) | low | New audit | — |
| [#326: [AUDIT] Validation catalog hard-codes a maintainer checkout path](https://github.com/p2pKit/P2pKit/issues/326) | low | New audit | — |
| [#327: [AUDIT] iOS install recipe uses a DerivedData path the build never selects](https://github.com/p2pKit/P2pKit/issues/327) | low | New audit | — |
| [#329: [AUDIT] CLI auto-mesh does not redial after stable-peer session loss](https://github.com/p2pKit/P2pKit/issues/329) | low | New audit | — |
| [#330: [AUDIT] iOS history cap can evict an active transfer row](https://github.com/p2pKit/P2pKit/issues/330) | low | New audit | — |
| [#331: [AUDIT] Android base-LAN KDoc requires provisioning-only runtime permissions](https://github.com/p2pKit/P2pKit/issues/331) | low | New audit | — |
| [#333: [AUDIT] Maintenance index gives the GitHub audit the wrong date](https://github.com/p2pKit/P2pKit/issues/333) | informational | New audit | — |
| [#341: iOS sample groups the local TCP port, breaking copy/paste into manual dialing](https://github.com/p2pKit/P2pKit/issues/341) | low | New audit | — |
| [#342: [Low] Discovery test fixture falsely claims current LAN delivery and acknowledgement semantics](https://github.com/p2pKit/P2pKit/issues/342) | low | New audit | — |
| [#347: [AUDIT] CLI identityProfile comment promises persistence that the in-memory store does not provide](https://github.com/p2pKit/P2pKit/issues/347) | low | New audit | — |
| [#361: [AUDIT][Low] Android hotspot failure labels are shifted from the SDK reason constants](https://github.com/p2pKit/P2pKit/issues/361) | low | New audit | — |
| [#362: [AUDIT][Low] Android initializer KDoc promises a legacy fallback under authenticated defaults](https://github.com/p2pKit/P2pKit/issues/362) | low | New audit | — |
| [#363: [AUDIT][Low] First iOS incoming file offer has no visible Accept/Reject controls](https://github.com/p2pKit/P2pKit/issues/363) | low | New audit | — |
| [#364: [AUDIT][Low] Interoperability catalog conflates security profile selection with optional features](https://github.com/p2pKit/P2pKit/issues/364) | low | New audit | — |
| [#365: [AUDIT][Low] iOS validation recipe requests a bare fingerprint in a full pairing-QR field](https://github.com/p2pKit/P2pKit/issues/365) | low | New audit | — |
| [#366: [AUDIT][Low] Android unknown-size URI KDoc recommends a JVM-only overload](https://github.com/p2pKit/P2pKit/issues/366) | low | New audit | — |

## External/platform validation pending (21)

| Issue | Severity at checkpoint | Origin | Last recorded fix/revision |
| --- | --- | --- | --- |
| [#21: [VALIDATION] Android long-idle discovery retention and removal](https://github.com/p2pKit/P2pKit/issues/21) | SEE_FULL_ISSUE | Existing | — |
| [#23: [VALIDATION] iOS peer-restart endpoint refresh timing](https://github.com/p2pKit/P2pKit/issues/23) | SEE_FULL_ISSUE | Existing | — |
| [#25: [VALIDATION] JVM/macOS explicit JmDNS binding interoperability](https://github.com/p2pKit/P2pKit/issues/25) | SEE_FULL_ISSUE | Existing | — |
| [#26: [VALIDATION] Android hotspot-host LAN binding and routing](https://github.com/p2pKit/P2pKit/issues/26) | SEE_FULL_ISSUE | Existing | — |
| [#27: [VALIDATION] iOS Personal Hotspot rebind coalescing](https://github.com/p2pKit/P2pKit/issues/27) | SEE_FULL_ISSUE | Existing | — |
| [#28: [VALIDATION] Android Wi-Fi/VPN bind-address selection](https://github.com/p2pKit/P2pKit/issues/28) | SEE_FULL_ISSUE | Existing | — |
| [#29: [VALIDATION] Android rapid-rebind listener ownership](https://github.com/p2pKit/P2pKit/issues/29) | SEE_FULL_ISSUE | Existing | — |
| [#30: [VALIDATION] Android hotspot bind readiness and retry](https://github.com/p2pKit/P2pKit/issues/30) | SEE_FULL_ISSUE | Existing | — |
| [#31: [VALIDATION] JVM interface-change rebind recovery](https://github.com/p2pKit/P2pKit/issues/31) | SEE_FULL_ISSUE | Existing | — |
| [#32: [VALIDATION] iOS cellular-prohibited Bonjour discovery on hotspot/AWDL](https://github.com/p2pKit/P2pKit/issues/32) | SEE_FULL_ISSUE | Existing | — |
| [#33: [VALIDATION] Android selected-network outbound routing](https://github.com/p2pKit/P2pKit/issues/33) | SEE_FULL_ISSUE | Existing | — |
| [#34: [VALIDATION] iOS AWDL discovery and bidirectional transfer](https://github.com/p2pKit/P2pKit/issues/34) | SEE_FULL_ISSUE | Existing | — |
| [#35: [VALIDATION] Android hotspot/Wi-Fi rebind debounce under callback bursts](https://github.com/p2pKit/P2pKit/issues/35) | SEE_FULL_ISSUE | Existing | — |
| [#36: [VALIDATION] Android long-background discovery restoration](https://github.com/p2pKit/P2pKit/issues/36) | SEE_FULL_ISSUE | Existing | — |
| [#37: [VALIDATION] iOS activation/interruption discovery recovery](https://github.com/p2pKit/P2pKit/issues/37) | SEE_FULL_ISSUE | Existing | — |
| [#38: [VALIDATION] iOS endpoint generation after path changes](https://github.com/p2pKit/P2pKit/issues/38) | SEE_FULL_ISSUE | Existing | — |
| [#39: [VALIDATION] Long-idle JmDNS cache and resource stability](https://github.com/p2pKit/P2pKit/issues/39) | SEE_FULL_ISSUE | Existing | — |
| [#40: [VALIDATION] Cross-platform TCP connect-timeout measurements](https://github.com/p2pKit/P2pKit/issues/40) | SEE_FULL_ISSUE | Existing | — |
| [#41: [VALIDATION] iOS write-ready timeout and path-interruption recovery](https://github.com/p2pKit/P2pKit/issues/41) | SEE_FULL_ISSUE | Existing | — |
| [#43: [VALIDATION] Android metadata-free JmDNS removal callbacks](https://github.com/p2pKit/P2pKit/issues/43) | SEE_FULL_ISSUE | Existing | — |
| [#44: [VALIDATION] Cross-platform link-local discovery and connectivity](https://github.com/p2pKit/P2pKit/issues/44) | SEE_FULL_ISSUE | Existing | — |

## Architecture/product decision pending (1)

| Issue | Severity at checkpoint | Origin | Last recorded fix/revision |
| --- | --- | --- | --- |
| [#120: [WSA2-01] Hostile LAN host can exhaust the discovery budget and lock out all real peers](https://github.com/p2pKit/P2pKit/issues/120) | high | Existing | — |
