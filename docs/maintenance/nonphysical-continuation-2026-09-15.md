# Nonphysical campaign preservation — 15 September 2026

**Dated snapshot, not a release approval or another mutable status ledger.**
The owner requested portable source/review/issue handoff and branch consolidation,
without restarting held builds, downloads or CI. GitHub issue conversations own
subsequent acceptance decisions; the [six-area table](../validation/README.md#current-status)
remains their sole mutable campaign-status summary. Historical failures below stay failures.

## Source to resume

Use **`work/nonphysical-integration-20260915-022112`**, not one of its older topic tips.
This branch contains the campaign source and reviewed preparations; **it is not merged**.

| Identity | Exact value |
| --- | --- |
| Main, remotely observed 2026-09-15 07:51:33 UTC | `3bc76f956f8f47447b51a62474fc878b9c43173c` |
| Main tree | `2a1105fde1d1ac299448489501e29d7a0d4a407a` |
| Published integration before this documentation snapshot | `c46da8a739e4e27f124d951bb669126b6ba47974` |
| Integration tree | `061184c6de66824b597e996e2cfe589ff2d2cf9b` |
| Complete executable/source review freeze | `56bbb488f5148097573aeb82dc27c25e2d974f6f`, tree `207c3d8fc3bc2bb4e967823bdee162ddbb811af3` |
| History-preserving integration of that freeze | `163ff79565cd93d2e6ca57f4853cd3bab7f9e025`, same tree |

The later `c46da8a` change is 29 reviewed Mac-handoff documentation lines, not a
cache implementation or bandwidth cap. This snapshot's containing commit changes
documentation only; it does not create new product execution evidence.

The live open-item census was read at **07:51:35 UTC**: **58 issues, six dependency
PRs, no campaign PR**. Complete changed conversations for 15 issues were refreshed
through 07:53:24; 43 unchanged complete conversations and the six complete PR/review
packets were hash-checked and reused. Unchanged refers to body/update/comment
metadata; reused timeline snapshots remain dated, not a fresh all-event or linked-PR
census. This is not a claim that all history was newly downloaded. Later issue-pointer
comments do not change the census denominator.

Historical audit accounting remains **206/234 repair-approved (88.0%), 207/234
historically resolved (88.5%), 27/234 historically unresolved**. The repair-approval
complement is 28, including the no-repair resolution. New issues #421–#436 are
outside that 234-row denominator. These are neither effort percentages nor release
readiness. **This campaign has zero COMPLETE_ACCEPTED closures. Audit/release: NOT_READY.**

## Consolidated branches and safe retirement

All **15 local campaign tips**, including every existing same-name remote tip,
are ancestors of `c46da8a`. All **13 campaign worktrees** were clean at inventory.
No unique campaign commit needs another merge into the integration branch.

<!-- branch-inventory:start -->
| Campaign branch | Preserved tip | Same-name remote |
| --- | --- | --- |
| `work/mac-nonphysical-20260912-124718` | `8cef6af78e8c172736b12aa9fe67a34148e9cace` | No; source reachable through integration |
| `work/nonphysical-317-20260913-235735` | `f64cd4f31eb4ba80b1d34b3cdde4a657857b4570` | Present, exact match |
| `work/nonphysical-424-retention-20260915-060317` | `56bbb488f5148097573aeb82dc27c25e2d974f6f` | No; source reachable through integration |
| `work/nonphysical-android-adapter-20260915-042047` | `0512398ee078a5b7740fea3620a1b6c377e1b135` | No; source reachable through integration |
| `work/nonphysical-fixture-parent-20260914-050148` | `b5f6381669311fd746486f26aa8da81e461eaecb` | Present, exact match |
| `work/nonphysical-integration-20260915-022112` | `c46da8a739e4e27f124d951bb669126b6ba47974` | Present, exact match |
| `work/nonphysical-locks-20260913-090809` | `ff0cc1111ec1a8a5b820de1c40d52dfa2178b22c` | Present, exact match |
| `work/nonphysical-locks-r6-20260915-045855` | `ff0cc1111ec1a8a5b820de1c40d52dfa2178b22c` | No; source reachable through integration |
| `work/nonphysical-mac-capacity-20260914-075958` | `45512398d7570d71b053f88a80a635ee11db25c9` | Present, exact match |
| `work/nonphysical-mac-credential-family-20260914-145919` | `29cf30581181d23fb719491099bc3f60237deffd` | Present, exact match |
| `work/nonphysical-native-temp-20260914-023912` | `9b789062bd8fb1d932018f69e9f81fe551ee6fea` | Present, exact match |
| `work/nonphysical-windows-20260913-052918` | `0ef79ad30831bfc8b33520f1e9ac2e998fadd149` | Present, exact match |
| `work/nonphysical-windows-argfile-20260914-161538` | `ac2a3a7452df605182bb9f10b24d26ce1e8614f6` | Present, exact match |
| `work/nonphysical-windows-filekey-20260914-142800` | `993d325e442b5407113b3b069d8e5406d4f9a9ad` | Present, exact match |
| `work/nonphysical-windows-junit-20260914-155452` | `1273c08be32a7d59324ac7c5b69ac1bad17480c7` | Present, exact match |
<!-- branch-inventory:end -->

**No campaign branch is deletion-eligible yet.** None of those tips is preserved
in main. Keep them until applicable checks, formal review, normal PR merge and
main-preservation proof complete. Inclusion in an unmerged integration branch
alone does not meet the owner's deletion rule. Re-read remote tips immediately
before any future deletion; an advanced tip requires renewed inspection.

Keep unrelated `agent/*`, old audit/dependency/fix branches and worktrees unchanged.
Keep dependency proposals **#95, #97, #106, #107, #108 and #319** separate and unqualified;
their [retention decision](repository-consolidation-2026-09.md#branch-dispositions)
is not superseded. No reset, stash, force-push, tag change or repository-setting
change is part of this handoff.

## How to read acceptance

- **Source-reviewed:** an independent reviewer inspected the exact change and its
  callers/failure paths. Authored tests may still be uncompiled or unexecuted.
- **Scoped repair/runtime approval:** identified real checks passed on their named
  source/platform; unrelated failed aggregates and missing acceptance remain.
- **COMPLETE_ACCEPTED / closure:** all same-issue criteria, applicable checks,
  independent final review, formal PR review, normal merge and preservation are done.
  No row below has reached this boundary in this campaign.

The complete 80-file source cohort and final documentation delta received
**APPROVE_SOURCE_INTEGRATION_AND_LOW_BANDWIDTH_HANDOFF_ONLY** (review R-INTEGRATION).
It expressly **withholds runtime/full-gate acceptance, merge readiness and closure**.
It is not a formal GitHub PR approval. Retained required contexts include
`complete-gate`, `review`, `scan / osv-scan`, and `osv-scanner`; refresh effective
rules before the eventual PR. Automated dependency `review` is not formal human/PR
approval. No check/reviewer bypass is allowed.

## Issue work map

Every issue below remains **OPEN**. `A` means **ACTIONABLE_NONPHYSICAL**, including
work currently held for a real execution/input prerequisite. `B` means
**BLOCKED_EXTERNAL_OR_OWNER**. `D` means **DEFERRED_PHYSICAL_PHONE**. The inventory
contains **29 A / 11 B / 18 D**; these labels do not say 29 builds are authorized.
Every A row additionally requires the common delivery boundary above.

### Actionable nonphysical scope

| Issue | Already preserved; do not redo | Exact remaining delta |
| --- | --- | --- |
| <a id="issue-133"></a>[#133](https://github.com/p2pKit/P2pKit/issues/133) | Main already includes `71276169a7d0da6ecb8f01eb330d942b419fbc6c` and its approved repository goldens/mixed-profile coverage. Independent-peer attempts and four negative methods have separate scoped evidence below. | Resolve the peer-owned natural-exit70 failure with source-isolated observability, then the real two-process/role/file/negative/platform matrix. Current source/artifacts, custody and capture prerequisites still apply; phone cells stay deferred. |
| <a id="issue-141"></a>[#141](https://github.com/p2pKit/P2pKit/issues/141) | Main repair `d859e20252d2ed56fb9eeed20695456f2661e324`; Windows R13 now supplies the missing pre-#110 directory-fsync witness. | Full **Linux and Windows** core/LAN/Desktop-provisioning suites and diagnosable per-OS reports, applicable required full gate and delivery. The one Windows selected test is not either full suite. |
| <a id="issue-143"></a>[#143](https://github.com/p2pKit/P2pKit/issues/143) | Main credential-isolation repair `d18500c939bf3f7cc33f6c980085b1ba7eefebaa`; repository structural guard remains. | Genuine full-path CI, dependency-review, dependency-submission and Desktop three-host acceptance. Resolve the hosted credential boundary below without removing protections. |
| <a id="issue-144"></a>[#144](https://github.com/p2pKit/P2pKit/issues/144) | Main scheduling/full-tree repair `f10c590e4bf72075d2bb2e3ed223d179c38ba633`; prerequisite `6995130bcdb2594257c42bed006f7d23f5bc4d6a`. | Actual hosted scheduled/manual full-path acceptance, not another static implementation or local replay. |
| <a id="issue-214"></a>[#214](https://github.com/p2pKit/P2pKit/issues/214) | `51c577f080f2dd24430be2d3d012863e0a820a75`; R214 approves all 74 values and 90 exact citations (75 table + 15 supplemental). | Preserve/rebind the document and all 31 cited source-file blobs; current documentation/checks and normal delivery. No native rebuild solely for unchanged line citations. |
| <a id="issue-317"></a>[#317](https://github.com/p2pKit/P2pKit/issues/317) | Existing subscription correction retained; `dcd9bf51e4a1ad09b35e7973fecf643d5545ce28` adds source-reviewed hands-off instrumentation. | Fresh APK/test compilation and actual untouched rendered update, timing/full-resolution visual evidence and inert-bridge mutant. Android controller/model passes are not that runtime. |
| <a id="issue-324"></a>[#324](https://github.com/p2pKit/P2pKit/issues/324) | `9673a21112122962cc4734875cd6846d8eb9a3e3`; Compose/Activity/Parcel harness and read-only production-card seam, **source only**. | Real save-before-clear registry/Parcel restore, retained SSID/no secret, mask/reveal/15-second expiry, disposal/ON_STOP/reentry/join/permission-result coverage, nine mutants and screenshots. No whole-process-death or OS-grant proof from callback models. |
| <a id="issue-327"></a>[#327](https://github.com/p2pKit/P2pKit/issues/327) | Corrected recipe already on main. | Build and inspect the fresh unsigned generic `iphoneos` product using admitted Xcode/strict inputs. No connected phone, deployment or publication is needed or authorized. |
| <a id="issue-367"></a>[#367](https://github.com/p2pKit/P2pKit/issues/367) | Main toolchain repair `0d88be3e3769b5133a985e4fe2fca782ba0ef2a6`; retain Intel core780 and Windows strict 115-task scoped positives. | Genuine Intel LAN and applicable hosted/native full-gate reconciliation. Preserve Intel175 passes/nine timeouts/one manual skip and failed aggregates; do not recurate identical publisher bytes. |
| <a id="issue-372"></a>[#372](https://github.com/p2pKit/P2pKit/issues/372) | Existing permission source fix; compat model `f916991efdbc160fca0c7bc43404f31da5fa9739`, 28 host model passes. | Actual API37/target37 runtime, loaded-module/mandatory-flag/compat state and fresh no-Nearby install: deny → grant → authenticated duplex controlled LAN → revoke/lifecycle reentry. The native UI adapter excludes #372. |
| <a id="issue-409"></a>[#409](https://github.com/p2pKit/P2pKit/issues/409) | Prior source corrections and scoped Swift/native positives retained. | Current fresh producer/four sidecars/provenance; **204800 bytes each direction**, pre-Dial activity/RAW timing, consent/pins/hashes, Swift Stop and natural CLI quit. Keep 120/360/900/30-second limits and original xcresult. |
| <a id="issue-410"></a>[#410](https://github.com/p2pKit/P2pKit/issues/410) | All eight real direct-source lifecycle modes accepted by R410 on this ordinary ARM Mac. | Supported full writer, strict packaged private JmDNS/JUnit and consumer paths, JVM/Android parity, final result/provenance review. Standalone javac evidence is not packaging/full-check acceptance. |
| <a id="issue-413"></a>[#413](https://github.com/p2pKit/P2pKit/issues/413) | All eight genuine R4 ABI counterparts retained; R-ABI already approves native components and additive-content reuse at `ff0cc111`. | Actual corrected LAN aggregate/three native producers in the complete supported writer and final candidate/provenance reconciliation. **Do not redo the completed component review**; Intel runtime is separate. |
| <a id="issue-421"></a>[#421](https://github.com/p2pKit/P2pKit/issues/421) | `974d51a0ce638b397e6779a0ddaf5b4da8a8bffd`; real native Python3.9 controls91/91, 39 new fixture removals and 39 original-root recoveries independently approved. | Preserve #431's later compatible fixture-parent change; final input/check/formal-review/merge reconciliation. Original 39 teardown failures remain recorded. |
| <a id="issue-422"></a>[#422](https://github.com/p2pKit/P2pKit/issues/422) | `8cef6af78e8c172736b12aa9fe67a34148e9cace` plus `125aea6afe10fdebeedd618e5a7c14fb360a9011`; **R4 actually passed Android/CLI/DesktopUI/shared producer regressions**. | Broader final build/caller/input and delivery gates. All 11 repair paths match R4→`c46da8a`; do not repeat the obsolete Android-unexecuted claim or impose #133's peer matrix on this recorder repair. |
| <a id="issue-423"></a>[#423](https://github.com/p2pKit/P2pKit/issues/423) | `d33a48677488cda7b7273f8e4156013225a2ac20`; local CRLF normalization preserves originals. R13 real JDK17/21 admission accepted. | Common integration/delivery boundary, not another unchanged Java-parser repair. |
| <a id="issue-424"></a>[#424](https://github.com/p2pKit/P2pKit/issues/424) | CLI `368c310933c37406f77b67c3327347eb815d16be` and diagnostics `03ce11144c9baff76d13010c2dc5475ee3f2ec1c` have scoped runtime passes. Retention follow-up `56bbb488f5148097573aeb82dc27c25e2d974f6f` has source-only approval. | **11 new methods uncompiled/unexecuted**; compile/run both final classes (9 + 23 source methods), independently review originals, and admit the outer owned Java-temp custody envelope. Earlier 4 + 17 passes do not prove the new paths. |
| <a id="issue-425"></a>[#425](https://github.com/p2pKit/P2pKit/issues/425) | `3082ed3d594466db7294201baaeed8efe502d08f`; strict provenance REUSE classifier/caller and 65 hermetic methods approved. | Genuine complete supported writer, all 12 before/after locks and metadata, strict/provenance review and applicable current scan/submission. Stubbed Gradle caller phases are not a successful writer. |
| <a id="issue-426"></a>[#426](https://github.com/p2pKit/P2pKit/issues/426) | `bc9eac3a9bbab0727842966b06be799f6bff39c2`; invocation-local archive conversion correction. R13 both 1,263-blob materializations accepted. | Common integration/delivery boundary; retain complete source bytes, not Windows text conversion. |
| <a id="issue-427"></a>[#427](https://github.com/p2pKit/P2pKit/issues/427) | `52517f4ed8dfd9d47bbbd6c487953824b14e4caf`; owned clone long-path configuration/readback. R13 current172/preimage176 paths ≥260 characters accepted. | Common integration/delivery boundary; no path exclusion or global Git setting change. |
| <a id="issue-428"></a>[#428](https://github.com/p2pKit/P2pKit/issues/428) | `0ef79ad30831bfc8b33520f1e9ac2e998fadd149`; SDK batch parentheses admitted without losing injection guards. R13 actual SDK36/37.0 and native controls accepted. | Common integration/delivery boundary; do not rename unsupported SDKs or rerun the repaired adapter for ceremony. |
| <a id="issue-429"></a>[#429](https://github.com/p2pKit/P2pKit/issues/429) | `ff0cc1111ec1a8a5b820de1c40d52dfa2178b22c`; exact generated canonical LAN ABI reference order, R429 source-approved. | Real corrected `checkKotlinAbi`, three native producers and complete supported writer. R4's failing comparison stays failed; no hand-normalized comparison or RC3 change. |
| <a id="issue-430"></a>[#430](https://github.com/p2pKit/P2pKit/issues/430) | `9b789062bd8fb1d932018f69e9f81fe551ee6fea`; real R7 nonempty failure-path/R8 empty success-path temp diagnostics accepted. | Final input/delivery reconciliation. Historical residue creator/content/deletion safety remain unproved, not a reason to delete it. |
| <a id="issue-431"></a>[#431](https://github.com/p2pKit/P2pKit/issues/431) | `b5f6381669311fd746486f26aa8da81e461eaecb`; eight fixture temp sites separated from process temp. Local37 and R8 native96/empty roots/known retirement accepted. | Final issue-specific input/delivery reconciliation; retain the missing three standalone sentinel traces. Known-handle retirement is not a complete raw native census. |
| <a id="issue-432"></a>[#432](https://github.com/p2pKit/P2pKit/issues/432) | `410e5764261d78e099def0fcb5ae2446148e318d` → `0d919aecbaacd46b00675b13ca08c73f8c2e0bbc`; root/direct-buildSrc request authority, reviewed Map.isEmpty correction, R13 witness. | Common integration/delivery boundary; do not restore the rejected Groovy map predicate. |
| <a id="issue-433"></a>[#433](https://github.com/p2pKit/P2pKit/issues/433) | `30145b7dec0bf3f6a8f31b43af42f7df4e095c18` → `45512398d7570d71b053f88a80a635ee11db25c9`; exact task triple and real StartParameter controls, R13 witness. | Common integration/delivery boundary; constructed adverse controls are not hostile CLI-parser execution. |
| <a id="issue-434"></a>[#434](https://github.com/p2pKit/P2pKit/issues/434) | `993d325e442b5407113b3b069d8e5406d4f9a9ad`; native directory identity with genuinely nullable Java fileKey, R13 witness. | Common integration/delivery boundary; quiescent snapshots do not prove atomic hostile-replacement safety. |
| <a id="issue-435"></a>[#435](https://github.com/p2pKit/P2pKit/issues/435) | `1273c08be32a7d59324ac7c5b69ac1bad17480c7`; Kotlin JVM XML display-name qualification, R13 witness. | Common integration/delivery boundary; preserve source/task/test identity requirements. |
| <a id="issue-436"></a>[#436](https://github.com/p2pKit/P2pKit/issues/436) | `f722d9d88d726c9492022f704d8260c938e3c0c3` → `ac2a3a7452df605182bb9f10b24d26ce1e8614f6`; original worker argfiles and correct Gradle user-home service, R13 witness. | Common integration/delivery boundary. Do not reconstruct missing R10 argfile bytes or weaken caller-argfile/critical-option rejection. |

### External or owner holds

These are **B**, not phone excuses for avoiding feasible Mac work. No option is selected.

| Issue | Exact remaining prerequisite/decision |
| --- | --- |
| <a id="issue-25"></a>[#25](https://github.com/p2pKit/P2pKit/issues/25) | Consenting second on-link computer/interfaces/capture permission for real address/interface replacement; phone matrix cells deferred. |
| <a id="issue-31"></a>[#31](https://github.com/p2pKit/P2pKit/issues/31) | Two on-link macOS/Linux computers and controllable interface/AP flap topology. |
| <a id="issue-40"></a>[#40](https://github.com/p2pKit/P2pKit/issues/40) | Second computer, controlled impairment and packet capture for ENV-02; Apple/AWDL/hotspot phone cells deferred. |
| <a id="issue-44"></a>[#44](https://github.com/p2pKit/P2pKit/issues/44) | Second Mac/Linux host, dedicated adapters/direct cable/no DHCP and capture consent for three real link-local runs; mobile cells deferred. |
| <a id="issue-120"></a>[#120](https://github.com/p2pKit/P2pKit/issues/120) | Explicitly accept the documented High availability residual risk for a named scope, **or** authorize a protected-admission design with specified trust/budgets/expiry/compatibility. Raising caps or trusting advertised fingerprints is not a fix. |
| <a id="issue-151"></a>[#151](https://github.com/p2pKit/P2pKit/issues/151) | Protected non-SNAPSHOT publisher and exact publication-build JSON/XML SBOM need new publication authority. Safe preparation is not actual publisher acceptance; no tag/release authorized. |
| <a id="issue-156"></a>[#156](https://github.com/p2pKit/P2pKit/issues/156) | Consenting second on-link computer and controlled before/after PING/PONG RTT/capture. Existing TCP_NODELAY repair does not supply measured latency. |
| <a id="issue-216"></a>[#216](https://github.com/p2pKit/P2pKit/issues/216) | Editable single-source correction `1d0f2a832ae263619e1b25468a0ce87b396ce312` approved by R216. Protected CLAUDE.md blanket status clause still needs narrow permission or explicit scope exception. |
| <a id="issue-274"></a>[#274](https://github.com/p2pKit/P2pKit/issues/274) | Choose frozen present SPI, additive builder/factory preserving old descriptors, or explicitly breaking future-version SPI. A defaulted extra constructor parameter is not automatically binary-compatible. |
| <a id="issue-284"></a>[#284](https://github.com/p2pKit/P2pKit/issues/284) | Retain caller-controlled terminal close, or authorize a distinct optional nonterminal leave capability with cleanup/cancellation/ABI contract. OS-loss cleanup already exists; do not silently change hotspot stop. |
| <a id="issue-325"></a>[#325](https://github.com/p2pKit/P2pKit/issues/325) | Narrow permission to align protected AGENTS.md SDK guidance with literal library36/sample37.0, or explicit exception. AGENTS.md/CLAUDE.md remain unchanged. |

### Physical-phone deferrals

These **18 D rows** stay open. Do not start them, ask for a phone, or rename their
criteria as emulator qualification. Their old implementation proposals are not a repair queue.

| Issue | Deferred criterion |
| --- | --- |
| <a id="issue-21"></a>[#21](https://github.com/p2pKit/P2pKit/issues/21) | Real Android long-idle discovery retention/removal. |
| <a id="issue-23"></a>[#23](https://github.com/p2pKit/P2pKit/issues/23) | Physical Apple restart, stale-endpoint removal within10s and AWDL. |
| <a id="issue-26"></a>[#26](https://github.com/p2pKit/P2pKit/issues/26) | OEM physical-hotspot routing, discovery and authenticated traffic. |
| <a id="issue-27"></a>[#27](https://github.com/p2pKit/P2pKit/issues/27) | Real Personal Hotspot rebind ordering/port coalescing. |
| <a id="issue-28"></a>[#28](https://github.com/p2pKit/P2pKit/issues/28) | Physical Android VPN/Wi-Fi selection matrix. |
| <a id="issue-29"></a>[#29](https://github.com/p2pKit/P2pKit/issues/29) | OEM physical-device50-toggle listener-ownership campaign. |
| <a id="issue-30"></a>[#30](https://github.com/p2pKit/P2pKit/issues/30) | OEM phone-hotspot multicast-ready/bind-retry acceptance. |
| <a id="issue-32"></a>[#32](https://github.com/p2pKit/P2pKit/issues/32) | iPhone Personal Hotspot/AWDL without cellular fallback. |
| <a id="issue-33"></a>[#33](https://github.com/p2pKit/P2pKit/issues/33) | Physical selected Android Network/AP TCP egress/SYN excluding VPN/cellular. |
| <a id="issue-34"></a>[#34](https://github.com/p2pKit/P2pKit/issues/34) | Physical iPhone AWDL secure discovery and two-way transfer. |
| <a id="issue-35"></a>[#35](https://github.com/p2pKit/P2pKit/issues/35) | Physical OEM 50-toggle debounce/readiness, original 800ms bound. |
| <a id="issue-36"></a>[#36](https://github.com/p2pKit/P2pKit/issues/36) | Real Android Doze/standby, long background and process restart. |
| <a id="issue-37"></a>[#37](https://github.com/p2pKit/P2pKit/issues/37) | Physical Apple interruption/lock/activation timing. |
| <a id="issue-38"></a>[#38](https://github.com/p2pKit/P2pKit/issues/38) | Physical Apple path-rotation race and current browser endpoints. |
| <a id="issue-39"></a>[#39](https://github.com/p2pKit/P2pKit/issues/39) | 6–12-hour soak with **two physical Androids plus JVM/Desktop**. |
| <a id="issue-41"></a>[#41](https://github.com/p2pKit/P2pKit/issues/41) | Physical Apple write-ready cancellation/path interruption. |
| <a id="issue-43"></a>[#43](https://github.com/p2pKit/P2pKit/issues/43) | Physical OEM null/stub serviceRemoved and loss/stop churn. |
| <a id="issue-291"></a>[#291](https://github.com/p2pKit/P2pKit/issues/291) | Physical-device iCloud Backup-set absence; simulator filesystem flags do not close it. |

## Shared execution evidence — count each run once

### Windows R13

The witness source is `d683a8ccff60f669e8873afceaf0e4b185da42f2`; participating
heavy-job serialization is `cfbe38bdf0775c627d033fdf69ac795522ae4927`. Both are
integrated, reviewed prerequisites, not a replacement for host/lease admission.
Within #436, intermediate `481fd89e2255add253b66099ef61df233e1470eb` corrected
the three-line Groovy charsetProperties fixture collision; its actual compiled78
controls passed0/0/0 before the final provider correction and R13. The
[original intermediate outcome](https://github.com/p2pKit/P2pKit/issues/436#issuecomment-5669011242)
retains that separate source/result review rather than hiding it behind the final tip.

[Run 34894432851/attempt1](https://github.com/p2pKit/P2pKit/actions/runs/34894432851/attempts/1),
job104144779181, genuinely succeeded on Windows Server2025 AMD64, Python3.12.10,
JDK17.0.20.1/21.0.12.1, Gradle9.7.0, literal SDK36/37.0. Source
`ac2a3a7452df605182bb9f10b24d26ce1e8614f6`, tree
`72fd1d887262d511061811cb4b8ef7b8cadc2737`.

Actual hosted entry: `python -B scripts/run-windows-directory-control.py run`.
The selected task was:

```text
:p2p-core:jvmTest --tests dev.p2pkit.core.transfer.FileTransferJvmTest.durableDestinationPublishesOnlyAfterCommitAndCommitIsIdempotent
```

This is a task excerpt, not the complete private-path-bound argv. Current
product/stop/final **0/0/0**, one pass; one-method historical derivative
`cd169cb252c024c777cf29e5addc16bd3102c099` / tree
`be8826f26bbdb4a4a00333329658187456914b1f`: **1/0/1**, expected directory
`AccessDeniedException` in pre-#110 `syncParentDirectory`. Only that method came
from `ba208af23b9ce8e8f6efe1e3f63b0b81b38a4c7a`; the old/current selected test
block is unchanged. #110 was not reimplemented. The private derivative was not pushed.

Native96 comprises **35 pure + 19 modeled Darwin + 42 actual Windows fixture
methods**. Schema5/80 comprises **78 constructed/modeled + two real Gradle-service
controls**. Six actual leaves have same-home stop0. Both original worker argument
files were retained/qualified. Review R-WINDOWS approves the **narrow witness and
known retirement with trace limits**, not full library/Desktop/macOS/Intel gates.
Mac/ordinary matrix jobs were skipped, not passed. R10/R11/R12 failures remain.

Three standalone sentinel launch traces remain missing. R5/R6/R7 historical disk
allocations remain **UNPROVED_DO_NOT_REUSE_OR_DELETE**. Source-cohort R-WINDOWS-SOURCE
and passive exact-input comparison support narrow reuse at `c46da8a`; they do not
claim current full-gate binaries.

### JmDNS and ABI

At `974d51a0ce638b397e6779a0ddaf5b4da8a8bffd`, native arm64 macOS26.2/Xcode26.5,
JDK17.0.17, direct javac/Java admission genuinely passed **control,
failed_recovery, shared_close, close_wins, recovery_wins, responder_close,
callback_executor and cleanup_retry**, each naturally within unchanged45s bounds.
All 11 producer/mode receipts were0/0/0. Actual timer/socket/executor ownership,
recovery and TTL-zero native send returns were observed. This is **R410
DIRECT_SOURCE_JAVA_LIFECYCLE_ADMISSION_ONLY**, not receiving-peer delivery,
strict packaged JmDNS, Android parity or Intel acceptance.

Actual full writer R4:

```sh
scripts/prepare-dependency-update.sh 3082ed3d594466db7294201baaeed8efe502d08f
```

It generated **five built-in JVM/Klib plus three custom Android counterparts =
eight ABI baselines**. All three native LAN main targets and aggregate actually
ran; LAN `checkKotlinAbi` failed only on the canonical declaration order tracked
by #429. Other successful task groups remain scoped positives. Android built-in
`NO_SUPPORTED_DUMP` is not one of the accepted comparisons. The generated LAN
aggregate SHA256 is `b65028bae83c1046bc4a145000ed1b0dae6aa9dd5d9a615ea03b60e5963579a0`;
the complete RC3/pre-#413 baseline is
`4d849ded7bfa892236706c499b0692d8fde6f243e91469f4745b840d2692c77c`.
It differs by exactly the existing additive factory signature/comment line.

R-ABI already joins the real R21 Swift28 + isolated cancellation1, R22 ARM4,
R4 ARM4 and all eight generated counterparts at corrected `ff0cc111`.
**APPROVE_NATIVE_COMPONENT_EVIDENCE_AND_ABI_CONTENT_REUSE_AT_FF0** is complete;
the real corrected aggregate/full writer is not. Main still has the old
reference order; this integration branch contains #429's correction.

### #421, #422, #424 and #425

- **#421:** actual native Xcode Python3.9.6 invocation
  `python3 scripts/tests/run-audit-command-test.py --expected-host macos-arm64 --evidence-dir <owned-evidence>`
  ran unchanged91 methods:0 failures/skips,0/0/0. R421 separately accepts original
  39-root recovery with intact authentic archives. This is not a new run here.
- **#422:** initial119 shared diagnostics cases + nine checker models passed.
  The above **R4** subsequently compiled/executed four exact original XML suites:
  Android1, CLI4, DesktopUI4, shared1, **10 passes/no failures/errors/skips**,
  including Connected/reconnect/snapshot/export assertions. R4's full writer
  still failed LAN ABI (writer1/stop0/controller125). The September13
  [pending Android note](https://github.com/p2pKit/P2pKit/issues/422#issuecomment-5654120305)
  is historical, not the current execution delta. No Android ART result is claimed.
- **#424 CLI:** `scripts/prepare-dependency-update.sh 368c310933c37406f77b67c3327347eb815d16be`
  genuinely passed four CLI methods/two real-child transcripts. A separate focused
  CLI invocation was **not** run; the independently reviewed equivalent was the
  required writer. Whole R3:2240/2241 passing, **failed**, not a lock candidate.
- **#424 diagnostics:** actual strict/fresh
  `./gradlew :p2p-sample-diagnostics:test --tests dev.p2pkit.sample.diagnostics.RollingJsonlFileSinkTest --no-configure-on-demand --console=plain --init-script <retained-owned-test-temp-initializer>`
  at `03ce111` passed17 methods/four lossless BUSY/ACQUIRED child transcripts,
  product/stop/final/controller0/0/0/0. Native macOS26.2/JDK17.0.17 tests/JDK21.0.11
  daemon. Its new retention follow-up has **11 authored but unexecuted methods**;
  see [the already posted source-only review](https://github.com/p2pKit/P2pKit/issues/424#issuecomment-5676195391)
  and [outer custody contract](../testing/local.md#subprocess-transcript-custody-on-failure).
- **#425:** real-caller parent negative failed as expected (caller31/unittest1).
  Actual `P2PKIT_PYTHON3=<native-python> bash scripts/tests/check-dependency-update-policy-test.sh`
  passed65 methods (20 caller,16 workspace/GPG,22 variant/locator,7 validator)
  plus shell controls;44 candidate caller invocations retain phase traces.
  Expensive caller Gradle/remote phases are declared stubs. R425 approves this
  exact source/hermetic scope, **not a real complete-writer result**.

### Android preparations, not rendered acceptance

Shared source already integrated:

| Commit | Original executed host-model command/result |
| --- | --- |
| `2babc04e5867c2bcd0725335b896b6ba688c42c6` | `scripts/tests/run-android-art-smoke-test.py`:23 pass; manifest contracts. |
| `f916991efdbc160fca0c7bc43404f31da5fa9739` | `scripts/tests/android-compat-model-test.py`:28 pass. |
| `14123fa58ce5fcc04389726b1eac2ff67c42cf5d` | `scripts/tests/verify-android-acceptance-artifacts-test.py`:10 pass; actual AGP producer unexecuted. |
| `a8e6bb2e1aaf69d482a8cbd039a24d38a5335ff5` | UI verifier24 prior passes reused + three new focused passes, **not 27 newly run together**. |
| `3c1446eddbde2ee950db35e7448efd475ed07d5b` | `scripts/tests/android-ui-controller-test.py`:29 pass. |
| `f64cd4f31eb4ba80b1d34b3cdde4a657857b4570` | `scripts/tests/android-archive-admission-test.py`:48 pass, unchanged modeled execution reused. |
| `0512398ee078a5b7740fea3620a1b6c377e1b135` | `scripts/tests/run-android-ui-tests-test.py`:43 pass; native adapter excludes #372. |

These used isolated native Python3.9 (`-I -B -S`, named test script, `-v`); complete
original variants remain private. They are **pure/fake-I/O models**, not actual
guest/process/HTTP/ART outcomes. R-ANDROID independently reviewed all14 assigned
source files; no runtime approval follows. The source-vocabulary/APEX/aconfig
investigation for #372 does not prove loaded runtime or compat-cache semantics.

The planned two pinned archive inputs total **2,600,577,758 bytes**. Their acquisition
and admission remain **PRELAUNCH_HOLD**, not already downloaded or compared. The
small process-name guard's eight models and no-download repository checks do not
authorize that acquisition. No emulator was started for this snapshot.

### Independent peer #133

The independent peer is **source-isolated coordinated AI authorship**, not an
independent human organization or professional cryptographic auditor. Preserve
that author boundary: peer diagnosis uses its own code/spec, not primary expected
bytes, counterpart source or primary failure payloads supplied to its author.

Actual public-core/test-owned-loopback attempt at `ff0cc111` selected schema5 plus
`PublicCoreIndependentTcpJvmTest.coreResponderDuplexAndRemoteClose`: schema5 passed,
live repetitions **PASS/PASS/FAIL** with `Connection reset`; aggregate1/0/1. Later
five-method C2 run on the same P2pKit source (15 September03:33:55–03:38:49 UTC):

```text
coreInitiatorRejectsWrongPin      3/3 PASS
coreResponderRejectsUnlistedPin  3/3 PASS
peerResponderRejectsWrongPin     3/3 PASS
peerInitiatorRejectsWrongPin     3/3 PASS
coreInitiatorDuplexAndLocalClose PASS/PASS/FAIL
```

Actual maintained1800s leaf selected `:p2p-core:jvmTest` with those five methods,
strict/fresh/two-worker flags and reviewed private attachments. Eleven actionable
tasks ran; JUnit **four passing/one failing methods**. The third positive peer
**naturally exited70**, not killed to manufacture an exit. Protocol CLOSE,
successful close calls and FIONREAD0 do not explain70 or prove orderly EOF.
[Accepted scoped result and failed aggregate](https://github.com/p2pKit/P2pKit/issues/133#issuecomment-5674529394).

Later peer-owned diagnostic work actually passed **104 modeled/fake-I/O unit
methods**, no failures/errors/skips (R-PEER104). That is not a rerun of TCP, native
FIONREAD, storage53 or interoperability. No primary SDK defect/root cause is
established. Shipped LAN, durable file, remaining negative/opposite-role/platform
matrices and external evidence remain incomplete. Never add overlapping suite
counts or present the prior164/focused93 history as164 current diagnostic passes.

### Hosted Mac credential boundary

Reviewed diagnostic commits `23276577f64729bf25a6e2474fc03e18c9e764aa`,
`18de7bae1c62076026db811921281377a5342d0d`,
`29cf30581181d23fb719491099bc3f60237deffd` include actual focused Python42/Ruby63
passes for the last revision. They do not admit the host.

[Run34892883261/attempt1](https://github.com/p2pKit/P2pKit/actions/runs/34892883261)
at `29cf305` failed both collector `run`/`validate-public` with exit2,
`MAC_HOST_CAPACITY_ERROR:ENVIRONMENT_CREDENTIAL_SSH_AGENT`; final guard1,
upload skipped/zero artifacts. This establishes presence of `SSH_AUTH_SOCK`, not
its value, producer, usability, contents or sole-conflict status. Rejection preceded
source/host/capacity collection. Runner-advertised OS is not native/Xcode admission.

R-MAC accepts recording **FAILED with known-invocation retirement**, not a capacity
pass. Resolve a reviewed credential-free boundary or narrow owner permission; do
not unset hooks, inspect the socket, stop an ambient agent or retry ARM/Intel
unchanged. Earlier generic environment failures keep their unresolved attribution.

## Latest writer failure, reuse and bandwidth

**R7 is FAILED_UNPROMOTED**, controller125/writer143/same-home stop0. The guard
observed cumulative **system-wide** swapouts1,075,314,688 bytes, crossing its1GiB
allowance. This is not a proven OOM, disk failure, per-writer attribution or proof
that a16GiB Mac can never qualify. Original R4/R5/R6/R7 outcomes are not replaced
by later source approval. All 12 before/after lockfiles and metadata remain
unchanged; **six stale upstream JmDNS lock memberships remain**.

R7's780 passing core ARM cases and ten SBOM artifacts bind `ff0cc111`, not a
current integrated whole gate. Its reviewed owned Gradle/Konan/tmp inputs were
cleaned; **those homes are unavailable for reuse**. No admitted zero-download
Gradle/cross-state cache-adoption path or enforced wire-byte cap exists here.

For future compatible batches (up to five issues), review each fix separately,
freeze the combined reviewed candidate, then share one **necessary** full gate
and focused affected checks. A five-issue batch is not five forced full builds,
nor permission to omit a distinct platform/failure criterion.

- Keep still-needed, verified dependency inputs **within their owned admitted
  state** while dependent checks remain; stop that state's daemons after each
  invocation. Never delete required dependencies merely to recreate them next run.
- Source/dependency/toolchain/environment/behavior must be matched before reusing
  **results**. Artifact reuse needs producer hashes and the maintained contract;
  old binaries or copied baselines are not fresh execution evidence.
- Source-changing writers require a new immutable execution state. An old state's
  source binding cannot be reassigned. Assess only meaningful input deltas; exact
  content equality can preserve scoped evidence but cannot manufacture a task pass.
- Do not restart a cold writer to discover download cost. Resolve a reviewed
  resource/acquisition plan first. Capture/file-size limits are **not network caps**;
  a precomputed archive/pack size is not measured wire traffic.

Current integrated `./gradlew check --console=plain`, complete writer/strict locks,
remaining ABI comparison, samples/consumers, Dokka/publication shape/SBOM,
Swift transfer/iphoneos and required genuine hosted/Intel scopes are **not all
accepted**. No release monolith ran for this documentation upload. Use the
[Mac executor/retention contract](../testing/mac-handoff.md), not dormant private
plans as unconditional commands. A failure stops dependent work, not unrelated safe work.

## Review provenance index

The following SHA256s identify **retained review text** (or the explicitly labeled
XML metadata record), not signed attestations,
public hosting of raw evidence or formal GitHub PR approvals. Packet basenames
permit owner-channel retrieval without publishing machine paths or private inputs.
Source-only, modeled, actual-runtime and failed-aggregate scopes are distinguished
above and in the linked issue conversations. Final source cohort review did not
turn intermediate CHANGES_REQUESTED or failed executions into passes.

<!-- review-index:start -->
| Key / issue scope | Retained report or labeled evidence record | SHA256 |
| --- | --- | --- |
| R214 — 214: Exact citation-only source approval | `review-214/REPORT.md` | `d26becba183f19f51ff4fe5f02396947235e096dcc85d06b4e7cf1b2f78e2a62` |
| R216 — 216: Editable scope only; protected-file hold | `review-216/REVIEW.md` | `35c75f768baa0278b4d9e9a383baa49d60605bc9ab91af9a6db9acd52dd94f7c` |
| R421 — 421: Native91 and original-fixture recovery | `review-421/FINAL-REVIEW.md` | `5b49a9a2f51dde8df92ba5bc13ef8b097f7c696a9722fecceaae3f223757c223` |
| R410 — 410: Eight direct-source modes only | `jmdns-runtime-independent-review.md` | `78380dd49ab4f7f785c5cb25c3470acd80913a7389d3b182e4db9e860f119bc9` |
| R425 — 425: Source/hermetic65; not full writer | `dependency-reuse-425-review-lI8ET5Rg/REPORT.md` | `b687c30f4d60d2c98dd8669b3b413f0a8b0ac569f20cf8f9f8de11cb3b7e95d9` |
| R429 — 429,413: Canonical-reference source only | `lan-abi-429-source-review-TpZgZKih/REPORT.md` | `ad24f0cf8e2634048d0c09ec1e88d859fe39272a38cbd14298be809eccf66ffe` |
| R-ABI — 413,429: Native components/ABI-content reuse at ff0 | `abi-final-scope-review-bz676ps9/REPORT.md` | `b7037b54bc5e750478ef29283a86ca0a600b09ad23b500d51a6e2576ab7ed261` |
| R-ABI-DELTA — 413,429: Passive input/reuse delta; no new test | `abi-current-continuation-tee95vi7/REPORT.md` | `b3458c255b7fa1b7325752214733e91ad36ff1a4ddeee861f791b1b3f9fe2ae8` |
| R424-RETENTION — 424: Final follow-up SOURCE_ONLY, 11 unexecuted | `retention424-final-source-review-bt__53_f/REPORT.md` | `b8c557e3d35c94b519875f5d2e2c979ddc7d09daca27bc99eb767555d250832f` |
| R-PEER104 — 133: Actual104 modeled/fake-I/O only | `peer-terminal-focused104-result-review-c2j03td4/REVIEW.md` | `a36ad7ee6008dab150b0823ae7c7e3311425d8862008deeabe070d27f4132ee9` |
| R-INTEGRATION — all campaign source: Final source/handoff only; runtime/merge WITHHELD | `source-handoff-final-review-i_7f4tkx/REPORT.md` | `7dba818c59822062992425ed25b9a829f6a79744f4d7fad11daaf9f7f4390b9a` |
| R-REMAINING-SOURCE — 56-file source cohort: Source-only cohort; no full gate | `integration-remaining-full-diff-review-gpxif2pi/REPORT.md` | `f91355da30053f8818673d48cbb4b48470331ff685ee8c1fbe23158df7de91d9` |
| R-WRITER-R7 — 425,410,413,429: Failed/unpromoted result and owned retirement | `writer-r7-terminal-independent-review-timhmjry/REPORT.md` | `d18b1eadf65d8329378d0525c9f5bc0d8f866a11f6372bb454e94d8948796224` |
| R-QUEUE-SOURCE — 141,143,367: Source only | `heavy-job-queue-review-om9gpizu/REPORT.md` | `fcf6847ff53136e9f648a1721f4c526eef012cb04cc117737f4d5dac9d4df89c` |
| R-WITNESS-SOURCE-SOURCE — 141: Source only | `windows-directory-final-source-review.8uikxcnk/REPORT.md` | `08dd571ec77cf009b7467039cc8a1b5f0796ee6e2b9fe0214f79454137039a5b` |
| R424-CLI-SOURCE — 424: Source only | `cli-startup-note-424-independent-review-d4xpjj_j/REPORT.md` | `e4d21210fd546da5c9d67cbe40cb7dac7a0992bcb5a240e08f5292db2140f53e` |
| R424-CLI-RESULT — 424: Actual scoped runtime; aggregate limits retained | `full-writer-r3-result-review-v65gee5f/REPORT.md` | `90768b8dcb914f8dbf8727f1af36235a19ee520b73d18026a6a0752cea6e319c` |
| R424-DIAGNOSTICS-SOURCE — 424: Source only | `diagnostics-startup-note-424-source-review-j30cbcc8/final/REPORT.md` | `4e6104d0a6af7a3adefb8a71acb7d3d7549bfa5d87e66a8473e6b40b27923289` |
| R424-DIAGNOSTICS-RESULT — 424: Actual scoped runtime; aggregate limits retained | `diagnostics-note-424-runtime-review-2exwln_9/REPORT.md` | `c5eeb4051dc0e640a96b966964097eacf6c781bbbbbc02dc11fc45e84a37f5d5` |
| R317 — 317: Harness SOURCE_ONLY | `android-317-root-review-zysiw7p5/REPORT.md` | `88f77206ffbbcbd3b88f0b8b9583a3d26bc030027a54679b1f5192e03759309f` |
| R324 — 324: Harness NOT_COMPILED/NOT_EXECUTED | `android-324-independent-source-review-5rabj_m_/REPORT.md` | `17d6cb11cb64c6e8aae550ab876b31cd0c846530fc85ecc81fbf424340ade3e9` |
| R422 — 422: Source/shared diagnostics119/checker9 | `review-422/FINAL-REVIEW.md` | `c1359b2bde9fc7c522a3b2bbbd58e75b2d90ecd8f0b2a0d7ace31f69b92a913b` |
| R422-ENUM — 422: Enum source correction; later R4 execution separate | `review-422-enum-followup.e7_19ntu/REPORT.md` | `5e705303cf7532de609933b48e8c72abaff22fa59eee5d08172b68c09f549a64` |
| E422-XML — 422: Passive original-XML metadata record, NOT review report | `closure-ready-current-kumd65zm/422-PRODUCER-XML.json` | `d9f4ad39aa53d22f345a98e2638096829323411a05bbe98d71cda1cf2906ec93` |
| R-WRITER-R4 — 422,410,413,425,429: Failed aggregate, scoped positives and retirement | `full-writer-r4-result-independent-review-0AE0XV86/REPORT.md` | `b483233e35fcd3a4e99d23223510aaa51aa84c7f8ec0d0e92d8174da233ed5ac` |
| R-ANDROID-MANIFEST — 317,324,372: Source plus modeled controls | `android-manifest-independent-review-r2-q7go6bl5/REPORT.md` | `5d77631e362b92d7c6c40a60bfe65c66461472c2cee621981b81700ff3c7a3a1` |
| R-ANDROID-COMPAT — 372: Source/pure28, runtime unproved | `android372-model-independent-review-dd1ct2hk/REPORT.md` | `f2d77ecbdc7afb5384adbcffade46df900cfbdab373436734de4d181a0dbf171` |
| R-ANDROID-ARTIFACT — 317,324,372: Source/pure10, actual AGP unexecuted | `android-artifact-independent-review-49igovi_/REPORT.md` | `74b34f1be04719be2ee7830e776848e4cb1be586607ec7130e0b0351337e81bd` |
| R-ANDROID-UI — 317,324: Source/focused pure evidence; no rendered UI | `android-ui-verifier-final-review-ppm28cgu/REPORT.md` | `226c12a470be4d499869c927b5cd8f2086aa0c7939aa7593d7a75a5af2c5178a` |
| R-ANDROID-CONTROLLER — 317,324: Source/modeled29 | `android-ui-controller-core-review-eyiy6qhm/REPORT.md` | `482900f0a24744ccfcff7f9988ee531ef3200f6b3d3148b038c6af9086a4c8fb` |
| R-ANDROID-ARCHIVE — 317,324,372: Archive-source only | `android-archive-source-final-review.9kqrTthE/REPORT.md` | `d14ff42dab9e3c0b4aeb34497b81d9c7cff4b8cfd3561b06a2a970f535a32f4a` |
| R-ANDROID-ARCHIVE-MODELS — 317,324,372: Actual modeled48; acquisition held | `android-archive-models-actual-review.LiOtxzFY/REPORT.md` | `0f26ebbc0d002079fe93ea13828f3ac7bbb6a4605058be925b8798f885fda35e` |
| R-ANDROID-ADAPTER — 317,324: Source/modeled43; native guest unexecuted | `android-native-adapter-model43-review.1Am9Dkut/REPORT.md` | `7863a944f4e92aa52c42a7a44f9482fa22df25b9eac41e4cd49f430dcb6469d2` |
| R-ANDROID — 14-file Android source cohort: SOURCE_ONLY coverage | `integration-android-full-diff-review-csic_8ze/REPORT.md` | `c9b98f64ce2cb3921f4e98f50391b1a050a2881ca205fa9557e906cd97c81f4e` |
| R-GUARD — 317,324,372: Small guard/models/static checks; no acquisition | `no-download-guard-independent-review-046k0qbr/REPORT.md` | `7ab3f36a87a2c905603b3f4a8996adf1132aa7fb20bd87f4d3f10f331ef65294` |
| R372-VOCABULARY — 372: Source qualification, compat state unproved | `android372-readback-vocabulary-1fa02gdd/REPORT.md` | `593cfd18b325f3299f70f4dd3a32ddc776e48f176907faddeb236b92c46a3a40` |
| R372-SUPPLEMENT — 372: Source qualification, not runtime equivalence | `android372-vocabulary-supplement-bmi9k7z6/REPORT.md` | `5c45daa21b195c76bfd2578dd42b5c417294357840c5401b1a4ca76ff985caef` |
| R423 — 423: Scoped source/control review; actual/full-path limits above | `windows-crlf-423-independent-review-45mwkr2y/REPORT.md` | `fc3d8a1d246c94e7888baa4839569e6149f971c14e4342a950a1eb86d9225fc1` |
| R426 — 426: Scoped source/control review; actual/full-path limits above | `windows-archive-426-review-rv5_p2hk/REPORT.md` | `e1c746e9d43de5ddd8f53ef20c6e048df21ae1527c0898df4844f8e0273d19e4` |
| R427 — 427: Scoped source/control review; actual/full-path limits above | `windows-longpath-427-independent-review-w2cn3f6t/REPORT.md` | `438c5c17ab47e026de746dd49b01e64b8bdb94361ea02caa32ddac92162f9265` |
| R428 — 428: Scoped source/control review; actual/full-path limits above | `windows-sdk-428-root-review-chhwbghz/REPORT.md` | `afbfbf1707b2f756cf8920074d309782e04f9ac315c722a5b7fdaf909a4e0344` |
| R430 — 430: Scoped source/control review; actual/full-path limits above | `windows-430-source-independent-review-a0b8x7e3/REPORT.md` | `0d2a96d18d03b29de2b794731745f78ffa2c534fc5d719c5f99b3d78b6e0b679` |
| R430-RESULT — 430: Scoped source/control review; actual/full-path limits above | `windows-r7-result-independent-review-0sealpjm/REPORT.md` | `82d89aa37b9071cc901245100d9a4ca75beef175705e6ad018dba95f527988a5` |
| R431 — 431: Scoped source/control review; actual/full-path limits above | `windows-431-source-independent-review-7j6b1gae/REPORT.md` | `22ef22d58abf0f93135ee63b3777ab058adfd2b15bf35c74fb419b05a66bc631` |
| R431-PURE — 431: Scoped source/control review; actual/full-path limits above | `windows-431-pure-independent-review-r_46n98w/REPORT.md` | `41e088fac89be436535c5a2c63520685e2258a4027bb8e61373f582d12f543e6` |
| R432 — 432: Scoped source/control review; actual/full-path limits above | `windows-432-independent-review-y963anft/REPORT.md` | `0afa4de9e9d0f4506c8dec43b4652435e72ae780d000d001a9d079af745e9fb7` |
| R433 — 433: Scoped source/control review; actual/full-path limits above | `windows-433-independent-review-bqnv8s9c/REPORT.md` | `588c22605977632ac5fbb412570666dd2dba1181363ee7c654d192495454763c` |
| R434 — 434: Scoped source/control review; actual/full-path limits above | `windows-434-independent-final-review-m6ptb_xa/REPORT.md` | `577b7a7178e63ca37572f4c29687a56a68239e05d60b9a63715bb2b7891b605d` |
| R435 — 435: Scoped source/control review; actual/full-path limits above | `issue-435-independent-review-ffg1bk9r/REPORT.md` | `ab348ec68f56338436987d57fd9f6d22266e76621ba28a67631ffb1171fadcc8` |
| R436 — 436: Scoped source/control review; actual/full-path limits above | `issue-436-final-independent-review-3tkb2n27/REPORT.md` | `c7cf66ccfda9b4fd5610a2293a9c4c854969bc348e30d70f0edcf8b31bb466c9` |
| R436-PROVIDER — 436: Scoped source/control review; actual/full-path limits above | `issue-436-worker-provider-independent-review-2uub8kh6/REPORT.md` | `f01c8ece71ce14b5b67d830fc96a5dcfc0efc45ddc8678f12810fca8d1b0f329` |
| R-MAC-CAPACITY — 143,367: Scoped source/control review; actual/full-path limits above | `mac-capacity-independent-source-review-t2ch76gt/REPORT.md` | `26eed4469c443fdbe6c6b7c12fe69d5770756c5161c551b0761f0c96f1805b9d` |
| R-MAC-ENV — 143,367: Scoped source/control review; actual/full-path limits above | `mac-environment-independent-source-review-oe3_to_2/REPORT.md` | `0f4a304497d0aff36594c3c5b5ea8fd99e8d606d4fa82455d1920b19df592fda` |
| R-MAC-CREDENTIAL — 143,367: Scoped source/control review; actual/full-path limits above | `mac-credential-family-independent-review-mriurnvc/REPORT.md` | `edd7fb83f91b4b617761f87aaae09f747f4ecea4aad181225fcd8d2683070e83` |
| R-WINDOWS — 141,423,426,427,428,432–436: Actual current/preimage witness; known retirement/trace limits | `windows-r13-actual-independent-review-_vc7b6nt/REPORT.md` | `b27aeb65540668e1ad0247f99f1d61c4303d219b63aa2541929500e2566b25e4` |
| R-WINDOWS-SOURCE — 8-file Windows source cohort: SOURCE_ONLY | `integration-windows-full-diff-review-bv9n_t9j/REPORT.md` | `3637236eb050b7fca1b06981cd3b08d68db9d772f70f8ab6a34bad706b6b30cc` |
| R-MAC — 143,367: FAILED result/known retirement; no native capacity admission | `arm-capacity-actual-result-review-amz_rmzh/REPORT.md` | `454ddf2f6dec4fa1d2e997dc675573d420abbeb0dcf89500bd8540d9803638a0` |
<!-- review-index:end -->

## Portable continuation and delivery

Read the exact linked issue comments and this snapshot before implementing anything.
For an **existing clean full-history clone**, after confirming origin and preserving
any local work, this fetch retrieves source only—not dependencies or build outputs:

```bash
git status --short --branch
git remote -v
git fetch --no-tags origin work/nonphysical-integration-20260915-022112
# Inspect FETCH_HEAD and any local divergence; do not reset an existing branch.
git rev-parse FETCH_HEAD 'FETCH_HEAD^{tree}'
git log --oneline c46da8a739e4e27f124d951bb669126b6ba47974..FETCH_HEAD
git merge-base --is-ancestor c46da8a739e4e27f124d951bb669126b6ba47974 FETCH_HEAD
git worktree add -b work/nonphysical-resume-UNIQUE /absolute/unused/path FETCH_HEAD
```

Choose unused names/paths. A new machine without a clone needs a **full-history**
clone when its source-download budget is acceptable; do not copy caches or identity
stores from this Mac. Refresh current main/PRs/issues before proceeding. Subsequent
remote advancement must be reconciled, not overwritten.

Retain original logs/XML/ABI dumps/xcresult/provenance/receipts outside Git. Public
summaries and review hashes are portable navigation, **not the missing raw bytes**.
Select only necessary private originals via the owner's private channel and verify
recorded hashes before accepting reuse; never upload credentials, signing material,
payloads, personal identifiers, peer raw inputs or old binaries to this repository.
Missing originals must be recorded precisely, not silently replaced with a blind build.

Before resuming held execution: agree on dependency/guest input budget and meaningful
resource admission; finish #424's outer custody envelope; resolve hosted credential
admission; provide computer-only topology where needed. Protected-file permissions,
#120/#274/#284 choices and #151 publication authority remain separate owner decisions.
No phone action is requested, now or after nonphone work.

After acceptance, open a normal PR to current main, retain exact gate/review/source
bindings, obtain required checks and formal approval, and prefer a normal merge.
Then fetch main, prove the reviewed tip is its ancestor and has no branch-only
commits, re-read remote tips, and only then remove this campaign's obsolete branches.
Close only fully accepted issues with source/merge/command/reviewer links and read
back each final comment/state. Mixed-scope or runtime-held issues stay open.

OSV remains **EXCEPTED_NOT_FIXED**: GHSA-r937-wjx7-w2jp / CVE-2026-53914,
affected Kotlin2.4.10, exception expiry **2026-10-31**;2.4.20 is unqualified.
No fresh advisory scan/remediation/exception extension was performed for this
snapshot. Refresh policy before qualification; changed locks need applicable scan
and submission. Zero unignored findings is not vulnerability-free. Published RC3,
`0.7.0-SNAPSHOT` and documented0.8.0+ restrictions remain unchanged.
