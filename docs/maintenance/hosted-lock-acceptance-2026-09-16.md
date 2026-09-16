# Accepted hosted lock candidate — 16 September 2026

This is a **dated source/evidence handoff**, not a mutable status ledger. Continue
on `work/nonphysical-integration-20260915-022112`; refresh GitHub before executing.
It supplements the [previous hosted continuation](hosted-lock-continuation-2026-09-16.md)
and [sample workflow record](sample-app-workflows-2026-09-15.md). Previous failures
remain failures. No issue closure, main merge or development Release is asserted.

## Exact successful producer and imported result

[GitHub run 35066719641, attempt 1](https://github.com/p2pKit/P2pKit/actions/runs/35066719641)
completed **SUCCESS** using `dependency-lock-candidate-macos14`:

- Source `ef8c42b0eea20152870c6c0e1966c6601ce60f03`, tree
  `3bfc27baf6ac4d910add7b28c4b2142f12708433`.
- Native ARM64 macOS **14.8.9**, Xcode **16.2 / 16C5032a**, iOS **18.2 Simulator**;
  native JDK **17.0.20.1** and **21.0.12.1**. This is the
  [reviewed narrow prerequisite profile](hosted-lock-macos14-2026-09-16.md),
  not canonical Xcode 26.5, genuine Intel, Windows or physical-device qualification.
- Independent result verdict **APPROVE_GENERATED_LOCK_CANDIDATE**; report SHA-256
  `321ac22d9a20914d10b61a6ec54f1fec2c9d63091f7c8bcf15cc2878dd245a95`.
- Original encrypted artifact ID **10435625724**, ZIP **6,272,423 bytes**, SHA-256
  `920c6348c2b06e9e3d7cfb4a108e672031c668437a77ecb536322395f02827ea`.
  Authenticated decryption, exact extracted membership and original hashes were
  inspected privately; no plaintext transcripts, keys or identifiers are published.

The complete maintained operation actually executed:

```text
scripts/prepare-dependency-update.sh ef8c42b0eea20152870c6c0e1966c6601ce60f03
```

Its writer and subsequent strict checks were:

```text
./gradlew resolveAndLockAll --write-locks --write-verification-metadata sha256 \
  --no-configure-on-demand --no-daemon --console=plain
scripts/check-dependency-verification.sh
./gradlew verifyBuildPluginSecurityFloors help --dependency-verification=strict \
  --no-daemon --console=plain
```

The writer succeeded in **21m 2s** (254 actionable tasks, all executed); metadata
validation passed; security-floor/help succeeded in **41s**. The real preparer
completed, including provenance classification and whitespace checks. This was
not a handwritten resolution subset or accepted partial writer output.

All **12 before/after lockfiles and both verification XML copies** were retained.
Only six generated lockfiles differ; each removes the obsolete upstream
`org.jmdns:jmdns:3.6.3` entry. LAN additionally records the existing SLF4J 2.0.7
artifact's `embeddedJmdnsCompileClasspath` membership. No version was upgraded;
the other six locks and verification XML are byte-identical.

| Exact generated postimage | SHA-256 |
| --- | --- |
| `library/p2p-network-provisioning-desktop/gradle.lockfile` | `7a8794ce0d775c5146fb1f280ae406a692c918ecbb9e8e94f0580911ec489c98` |
| `library/p2p-transport-lan/gradle.lockfile` | `ed0b7adfa1f03034d79965437741782c95a1210312189a898503b3afa052eefa` |
| `samples/p2p-sample-android/gradle.lockfile` | `ed56ac6d804833a72bc0f1b9d71fdf8dafee1b5e60b4adf6ddd2c4820ac25f07` |
| `samples/p2p-sample-desktop-ui/gradle.lockfile` | `9de5448362d196780739fe80c639dc261e7b58a1497d93c972c32bc087994eed` |
| `samples/p2p-sample-desktop/gradle.lockfile` | `d30572df734efab101f6ceaf5966df02e6b09e02b4c05150fbf738c545293ef8` |
| `samples/sample-kmp-shared/gradle.lockfile` | `855a1cd7a334742530d2b759da38cfd09bebb2341274d82cbd6b39e0db46a196` |

These **exact original postimages** were imported and pushed in
[`8e4ca8383f5f54a03f7b64f3c8f92225c00deb5b`](https://github.com/p2pKit/P2pKit/commit/8e4ca8383f5f54a03f7b64f3c8f92225c00deb5b),
tree `7978ccd6ae89b478a2ff45ab89349adc6764c932`. The intervening `b8db761d` changes
only two documentation fragments. The successful writer remains bound to its
original producer, not relabeled as an execution at the import commit.

The classifier recorded **REUSE**, 2,991 metadata artifacts and **zero new artifact
tuples**, with 1,313 exact non-project-lock inputs and 17 pinned input hashes
verified. This is reuse of accepted unchanged provenance, **not fresh remote
artifact curation**. Local static-only import checks
`bash scripts/check-dependency-verification.sh`,
`bash scripts/tests/check-osv-lockfile-coverage.sh` and whitespace passed.
Coverage is not a current advisory scan or dependency submission.

## Actual acceptance evidence and remaining boundaries

Original JUnit results: **349 suites, 2,795 cases, zero failures/errors, one
unchanged manual interoperability skip**. All eight generated ABI counterparts
were retained and matched, including the three custom Android comparisons. This
does not mean eight baselines plus three additional baselines, or an Android
`NO_SUPPORTED_DUMP` pass. The actual private JmDNS producer and matching aggregate
JSON/XML SBOM were also retained; this is not protected publication-build evidence.

| Issue | Actual reviewed result | Not established by this run |
| --- | --- | --- |
| [#425](https://github.com/p2pKit/P2pKit/issues/425) | The complete supported preparer now succeeds through unchanged-metadata provenance **REUSE**; all original phase and lock bindings inspected. | Fresh remote curation, current OSV/submission, formal PR approval or merged acceptance. |
| [#445](https://github.com/p2pKit/P2pKit/issues/445) | Reviewed fix `9e2f698bfb76118c3fdd1244af724cb491f793ef` actually compiled; Android-host ownership **20/20**, JVM ownership **12/12** pass, including both new cancellation/active-error methods on each platform. | Android ART/device qualification; no claim that the new methods executed against the preimage. |
| [#410](https://github.com/p2pKit/P2pKit/issues/410) | Fresh compiled fixture/private producer: all **eight** lifecycle modes pass with natural child exit within the original 45s limit, no rescue. Real resource/recovery/goodbye assertions run. | TTL0 send observation is not independently received peer delivery. Isolated publication consumers and other required integrated gates remain separate. |
| [#413](https://github.com/p2pKit/P2pKit/issues/413), [#429](https://github.com/p2pKit/P2pKit/issues/429) | All three LAN native producers and real `:p2p-transport-lan:checkKotlinAbi` pass. Actual additive aggregate and all eight dump mappings/hashes retained; native helper **4/4** passes. | ARM-produced x64 Klib is not native Intel execution; no new Swift app/framework or transfer result. |
| [#424](https://github.com/p2pKit/P2pKit/issues/424) | Actual Gradle API **30/30**, CLI **9/9**, diagnostics **23/23** pass; all six original transcript exports inspected; dedicated writer custody **RETAINED/KNOWN**, product/stop **0/0**. | API-only controls do not execute stock Test actions/workers. Ordinary CI/Desktop controller integration and Windows native exporter acceptance remain outstanding. |
| [#390](https://github.com/p2pKit/P2pKit/issues/390) | Actual executor **106** methods pass: 35 policy, 32 Darwin models, **39 native Darwin fixtures**. Current original writer pre-stop/product-final drains are KNOWN. | Current signal-reconciliation lists are empty: no native reproduction of the former Mach5 signal failure is claimed. |

The eight JmDNS modes were `control`, `failed_recovery`, `shared_close`,
`close_wins`, `recovery_wins`, `responder_close`, `callback_executor`, and
`cleanup_retry`. Passing JUnit required each child's natural exit, not merely a
printed PASS marker. The aggregate LAN dump is **6,176 bytes**, SHA-256
`b65028bae83c1046bc4a145000ed1b0dae6aa9dd5d9a615ea03b60e5963579a0`:
the complete immutable RC3 text plus exactly the existing additive
`createIosOwnedFlowCollection` declaration/comment line in canonical order.

Earlier independently reviewed Swift28 + cancellation1 and native4 results retain
their **original source/environment** scope. The final component/ABI-content
review (`b7037b54bc5e750478ef29283a86ca0a600b09ad23b500d51a6e2576ab7ed261`)
and current input-delta review
(`197a141cea1ad8f837bd6965250f8405fcff9c69ecc1072f9cad669683cb2acf`) are reused
explicitly, not rerun or treated as current Swift/Xcode 16.2 acceptance.

All **60 original command retirements** were KNOWN. Same-home Gradle stop and
resource observer exited 0; the selected simulator was verified Shutdown. The
later seal does not replace missing original observations. Historical
**35059903479/1 remains failed with its original pre-stop UNKNOWN**; earlier
multicast/Intel failures also remain unchanged.

## Other preserved source-only progress

- **#214:** `b8db761d1aa10080b4899d165c72992353733964` updates only the two listener
  source-line fragments changed by #445. All **90 excerpts / 74 values** were
  checked; **479 Markdown links / 100 files** and protected-file/whitespace checks
  passed. Independent **APPROVE_EXACT_DOC_PATCH**, report SHA-256
  `f1f88444181011f20bc5045533d2c357b43814261a8199a64b306633def6bec5`.
  No product rebuild was needed for this exact documentation delta.
- **#424 Windows export:** `f8788dc5aea37b9dba1c6b1ff114bfe8ae420098` integrates the
  reviewed four-file native pinned exporter. Final review **APPROVE_SOURCE_ONLY**,
  SHA-256 `c5b8a51ba179539ee20c2284658682fcdaa7319894c82daaf50fad478a94dd2c`.
  V1's plaintext-pin lifetime finding was reproduced by **four failing / one
  passing** model controls; v2's **65 exporter + 9 shared models** and **10
  independent boundary models** passed. The exact integrated source reran the
  65+9 models successfully. These are **offline models**, not real Windows/GPG
  execution, an ordinary workflow caller or complete #424 acceptance.

## Successful four-platform preview

The existing **build-only preview**
[35070982169/1](https://github.com/p2pKit/P2pKit/actions/runs/35070982169), operation
`sample-apps`, source **`8e4ca8383f5f54a03f7b64f3c8f92225c00deb5b`**, completed
**SUCCESS**, read back at **08:12:25 UTC**. No duplicate run was dispatched.
This is not execution of the later Windows exporter/controller source.

| Actual host job | Build result | Uploaded development artifact |
| --- | --- | --- |
| Ubuntu 24.04 x64, `104712172948` | SUCCESS, **5m 9s**; Android `assembleDebug` and Desktop `packageDeb` | [Android APK, artifact 10435977781](https://github.com/p2pKit/P2pKit/actions/runs/35070982169/artifacts/10435977781); [Linux DEB/UI/CLI, artifact 10436202245](https://github.com/p2pKit/P2pKit/actions/runs/35070982169/artifacts/10436202245) |
| Windows Server 2025 x64, `104713810937` | SUCCESS, **5m 6s**; Desktop `packageMsi` | [Windows MSI/UI/CLI, artifact 10435803838](https://github.com/p2pKit/P2pKit/actions/runs/35070982169/artifacts/10435803838) |
| macOS 15 ARM64, `104715496702` | SUCCESS, **4m 1s**; Desktop `packageDmg` | [macOS DMG/UI/CLI, artifact 10436538265](https://github.com/p2pKit/P2pKit/actions/runs/35070982169/artifacts/10436538265) |

All three original logs show `P2PKIT_SAMPLE_ONLY: true`, strict verification,
successful same-home Gradle stop, successful packager inspection, and successful
uploads. The common actual tasks were `:p2p-sample-desktop:installDist`,
`:p2p-sample-desktop-ui:checkRuntime`, `:p2p-sample-desktop-ui:hotRunArgfile`, and
`:p2p-sample-desktop-ui:createDistributable`, plus the table's native package task
and Linux-only APK task. **CLI/UI test selectors were intentionally not run in
this explicit preview operation.** Ordinary PR/main selectors remain unwaived.
The Windows native prepare step also succeeded after the separately reviewed
`614e5344` correction for [#439](https://github.com/p2pKit/P2pKit/issues/439).

All four artifact manifests/checksum files and ZIP member inventories were read
back with **186,726 bytes of bounded HTTP range reads**, not full application
downloads. Source/tree/workflow/run/attempt identities and manifest checksum
bindings match. The three small complete job logs were retained separately.
Full uploaded ZIP digests were obtained from GitHub, **not independently
recomputed locally**; application payload bytes were not downloaded or launched.
Hosted packager checks cover archive/CRC/layout/container/hash scope, not
installation or production signer identity. The APK is a debug build; Desktop
installers have no production-signing/notarization acceptance.

Artifacts expire **30 September 2026** under the 14-day policy. For now download
them from the run's **Artifacts** section, then extract the APK/DEB/MSI/DMG.
They are **not GitHub Releases on main**, genuine Intel macOS artifacts,
launch/network acceptance, or required ordinary test results. No whole-issue
#437/#439 closure is claimed from the preview alone.

## Delivery and resume boundary

Remaining: ordinary private-custody integration/native Windows qualification,
fresh applicable OSV/dependency submission, required CI and remaining
consumer/native/Swift scope, independent final integration/formal PR review,
normal merge and preservation. `.github/test-evidence-recipient.json` is absent;
candidate policy must not authorize its own trusted base/main bootstrap. Formal
exact-head PR review and legitimate recipient/key-responsibility admission are
external prerequisites, not grounds to bypass protected checks.

No literal standalone `./gradlew check --console=plain`, release monolith,
current #409 Swift/JVM transfer, genuine Intel runtime, emulator rendering,
physical-phone or independent-peer campaign is claimed. Keep affected issues
**OPEN** until their complete acceptance and delivery conditions are met.

Kotlin 2.4.10 advisory **GHSA-r937-wjx7-w2jp / CVE-2026-53914** remains
**EXCEPTED_NOT_FIXED**, exception expiry **2026-10-31**. No new scan/remediation
is implied. Historical repair accounting remains **206/234 (88.0%)**, separate
from the **68 open GitHub issues** refreshed on 16 September. Whole audit/release
remains **NOT_READY**; physical-phone criteria remain deferred.

Private retained packet handles (beneath the campaign evidence root):
`hosted-lock-run-35066719641-ny5b9kti`, `review-run35066719641-5qqf9qwr`,
`locks-generated-import-gcoebdw4`, `214-current-fragments-9hgy_uv6`,
`review-214-fragments-final-pdm_eh53`, `review-windows-evidence-v2-1asml8ht`,
`windows-export-v2-integration-hdvrhfsk`,
`samples-accepted-locks-dispatch-84vv7p5k`, and
`sample-run35070982169-results-lgca0z12`. Retrieve selected originals only
through the owner's private channel. No local Mac Java/Gradle/Xcode build,
SDK/dependency acquisition, emulator or simulator was run for this handoff.
