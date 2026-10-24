# Changelog

This file records release-facing behavior. Historical internal milestone tags,
audits, trackers, and implementation evidence remain under `docs/archive/`.

## Unreleased source

- Add optional selected-outbound-route SPI and per-session protection status.
  Retain at most64 exact numeric routes for originally authorized secure
  outgoing sessions, outside the untrusted discovery budgets. Fence original
  transport/session ownership, revocation, stop/restart and bounded recovery;
  permit fallback only after clean probe refusal. This addresses known-peer
  protection, not unknown-peer discovery fairness or guaranteed connectivity.
- Correct the modified private JmDNS producer's TXT-readiness predicate:
  SRV/address-only state no longer publishes a premature resolved clone or
  suppresses the still-needed TXT question. A received empty TXT is still
  DNS-SD data and remains subject to the application's metadata validation.
  The current private producer is `.410.8`; published rc7 retains `.410.7`.
  Deterministic regressions identify a real cause class for #516 without
  claiming the exact interleaving of its archived macOS timeout was observed.

No next release version is selected here. The records and artifact bindings
below remain immutable; these source changes do not retrospectively qualify
the original failed runs or complete physical/installed-application campaigns.

## 0.8.0-rc7 — development release candidate (2026-10-23)

Published and verified on Maven Central from immutable `v0.8.0-rc7`, with
separately approved delivery of the matching frozen APK/MSI/ARM64-DMG/DEB.
Both original publisher attempts succeeded; all seven complete anonymous
public downloads matched the recorded hashes.

Release source is `bc3a28e8e381b49585fb697160cb954bc642ea29`, bound by immutable
`v0.8.0-rc7`. Its main qualification explicitly combines thirteen successful
original-main components with an unchanged-source Intel replacement; the
original failed run is not relabeled. See the
[release record](docs/releases/0.8.0-rc7.md) for qualification, protected
publication, matching frozen applications and verified delivery scope.
Earlier release binaries and their evidence remain unchanged.

### Runtime and data ownership

- Retain application-message payload/backlog ownership across prompt cancellation
  (#488), Android URI sources across hashing cancellation (#487), queued inbound
  sockets/admission leases when collectors cancel (#489), and Android receive
  reservations before wrapper handoff (#492).
- Withdraw the old JmDNS handle's peers during whole-link rebind (#490), and keep
  Android optional SAF descriptor/size lookup off Main (#491).
- Replace filename-only sample cleanup with exclusively leased staging and proven
  abandoned-owner reconciliation (#495). Completed files keep their legitimate
  names; concurrent writers retain their staging. Add backward-compatible JVM
  and Android durable-destination overloads for an app-owned staging directory,
  and bind the Android sample to its Android factory rather than a JVM facade.
- Bound remote service-type/DNS-cache retention in the modified private JmDNS
  producer `.410.7` (#503), retaining source/patch/license/SBOM provenance. This is
  resource bounding, **not** a fix for hostile discovery-budget squatting (#120).
- Move large iOS sample preset generation/hash/readback off MainActor; Stop
  cancels and joins owned preparation before allowing replacement (#497).
- Protect the Android sample's API24–32 window with `FLAG_SECURE` for its full
  lifetime (#479). This intentionally also disables foreground screenshots,
  recording and non-secure displays on those APIs; API33+ keeps its existing
  task-preview-only policy. Synthetic API24 (`13d62b6`) and API32 (`aafce4f6`)
  witnesses have accepted original Recents/lifecycle/capture evidence. This is
  not natural-credential, physical-device or all-OEM acceptance.

### Tests, tooling and release reliability

- Retain native process ownership instead of signalling a potentially recycled
  process-group number during platform cleanup (#494).
- Require actual Running status in the iOS startup UI test (#498); retire Apple
  fixtures after setup/assertion failures (#502), and always join SessionStore
  test readers after mutation failures (#500).
- Bound Central HTTP phases by the original publisher-job deadline without
  retrying ambiguous uploads (#493); admit exact historical published-consumer
  contracts including their original private JmDNS version (#496).
- Align documented local release preflight and RPC controls with the maintained
  modular CI graph (#501), and correct stale current-operation guidance (#499).
- Add an independently selectable API24/API32 task-preview witness. Its genuine
  captures must be reviewed; a green harness is not privacy/OEM acceptance.

### Remaining limitations

High-severity discovery admission issue #120 remains open: untrusted advertised
addresses/fingerprints do not establish a fair or trusted origin. Added tests
retain this limitation and verify the existing explicitly pinned manual route;
they do not claim a hostile-LAN repair. Independent interoperability (#133),
physical/OEM/AWDL/Doze/network campaigns, actual iPhone backup observations (#291),
and remaining installed Windows W01–W11 coverage (#462) remain incomplete. This
candidate is not stable/production READY. No failed test or historical release
attempt is promoted to a pass by these repairs.

## 0.8.0-rc6 — development release candidate (2026-10-21)

Published and verified from immutable `v0.8.0-rc6`, source
`3ef2c6155abd66292011c3775b30fb71d280e9c7`, with matching frozen APK/MSI/DMG/DEB.
The original Maven workflow's final artifact upload failed after Central
publication and remote checks passed; separate protected read-only recovery
passed before application delivery. No Maven republishing or application rebuild
occurred. See the [release record](docs/releases/0.8.0-rc6.md) for original failures,
recovery evidence, approvals and all seven anonymous-download hashes.

- Preserve cancellation and local-close ownership when a session router receives
  a buffered generic close error; do not report normal teardown as a new
  `routeEvents failed` warning.
  Active transport errors, unclean remote EOF and typed authentication/protocol
  failures retain their existing handling. No warning allowlist or timeout change.
- Add deterministic JVM and Android-host cancellation/active-error/EOF/security
  controls, retaining the real secure receive accounting and recovery tests.
- Include the merged, verified dependency maintenance from PR #481: CycloneDX
  3.4.1, kotlinx-io 0.9.1, SLF4J 2.0.19, updated build-tool dependencies and pinned
  Actions, with the complete generated lock/integrity graph.
- Synchronize iOS UI-test keyboard input character by character and target the
  actual sample Done control, retaining exact text and keyboard-dismissal checks.
- Retain all current Windows RPC, installed-lifecycle and physical-device
  qualification limitations. This release does not claim those campaigns passed.

## 0.8.0-rc5 — development release candidate (2026-10-20)

Published and verified on Maven Central from immutable `v0.8.0-rc5`, source
`c8cca6db4d36dff61242c9e02b3bd0f4cb4eb5a9`, with the same-source frozen
Android APK, Windows x64 MSI, macOS ARM64 DMG and Linux x64 DEB. See the
[release record](docs/releases/0.8.0-rc5.md) for exact-source qualification,
separate protected approvals and all seven verified public-download hashes.
This remains a development prerelease, not complete installed, physical-device
or independent-audit qualification. Earlier releases remain immutable.

- Correct Android, CLI and Desktop diagnostics that inferred an optional file
  feature from a secure connection without observing feature negotiation.
- Preserve Android password sensitivity across join-result UI changes and mask
  before submission while retaining failed-retry input. Rendered/lifecycle
  acceptance remains separately tracked; this source repair is not a runtime pass.
- Disable Android sample recents screenshots on API33+ without blocking normal
  foreground screenshots. API24–32 receive no task-preview suppression; retain
  the [legacy preview limitation](docs/security/model.md#android-sample-credential-previews).
- Support verified lock-only dependency refreshes through the documented direct
  preparer, while preserving exact unchanged XML and verification-policy checks.
- Canonicalize the optional RPC multicast diagnostic's Python interpreter before
  allocating work; preserve invalid-input and actual primitive-admission guards.
- Clarify provisioning constructor compatibility, process-wide Android join
  routing, canonical SDK setup and external-validation status references.
- Correct operational-limit source citations and add narrowly scoped drift checks.
- Add bounded Windows Back-cleanup progress diagnostics without changing resource
  ownership, close order, provider behavior or time limits.
- Add a controlled actual authenticated-v2 PING/PONG RTT diagnostic. The recorded
  JVM loopback comparison showed no consistent TCP_NODELAY speedup; the separate
  synthetic TCP probe's benefit is not a measured protocol improvement.
- Prepare focused Android UI and Apple acceptance routes.
  Compilation, model and loopback results are not physical-device,
  actual installed-Windows, independent-peer or complete real-LAN qualification.

## 0.8.0-rc4 — development release candidate (2026-10-20)

Published and verified on Maven Central from immutable `v0.8.0-rc4`, source
`ba27d15eccfdc56756e6a2da4708a11e40bef690`. The same-source frozen Android APK,
Windows x64 MSI, macOS ARM64 DMG and Linux x64 DEB are publicly available.
See the [release record](docs/releases/0.8.0-rc4.md) for exact-source qualification,
separate protected approvals and all seven public-download hashes. Publication
does not complete the installed-Windows or external-device qualification below.

- Connect the productive Windows installed-provider path and retain original
  runtime/module/JNI ownership, protected storage, cleanup and admission checks.
  Windows LAN selection uses verified native IP-interface observations without
  weakening competing-interface or unknown-ownership refusal.
- Repair Android API24–29 accepted-socket setup without hidden APIs: a small
  NDK JNI helper creates/accepts nonblocking, close-on-exec sockets atomically,
  retaining the existing Network binding and descriptor leases. Android AAR/APK
  source builds require NDK `29.0.14206865`; the producer targets API24 and all
  four Android ABIs. Actual kernel/JNI controls cover Android10/API29 arm64 only.
- Preserve JVM17 library bytecode, the Windows sample's pinned JDK21 native
  runtime contract, application/MSI identity, protocol and persisted-data formats.
- The owner reported successful manual Windows/Android use on 2026-10-19 against
  the incoming installed pair. The Back deadline failure and zero fully accepted
  automated UI cycles remain; W01–W11, typed errors, revocation, interruption and
  full installed lifecycle qualification are incomplete. See the
  [exact-source handoff](docs/maintenance/windows-android-rpc-handoff-20261019.md)
  and [current Windows scope](docs/rpc/windows-release-scope.md).
- Remove the mandatory calendar-based Maven Central token-rotation deadline.
  Existing credentials remain usable while valid; compromise, exposure,
  revocation or provider requirements still require action. Authentication,
  namespace access, signing, protected approvals and integrity gates are unchanged.
- Strengthen the Apple post-transfer-cancellation fixture to observe a request
  and reply before teardown, with both subscriptions established before sending
  and both sessions still connected. The existing receive bound is unchanged;
  a completed local send alone is no longer mistaken for remote receipt.
- Make Swift UI Start-input recovery recognize late acknowledgements before
  issuing its one bounded retry; retain the readiness and no-duplicate-start checks.
- Required exact-source CI, Apple ABI/native checks, immutable artifact freezing
  and protected publication controls remain mandatory. No ABI baseline is changed
  to turn the earlier unavailable Apple-toolchain result into a pass.

## 0.8.0-rc3 — development release candidate (2026-10-18)

Published and verified on Maven Central from immutable `v0.8.0-rc3`, source
`db5d6c01e9a5f0c46fdb51ed0d885a5a394bbe5c`. The matching frozen Android APK,
Windows x64 MSI, macOS ARM64 DMG and Linux x64 DEB are publicly available.
See the [release record](docs/releases/0.8.0-rc3.md) for exact-source qualification,
publication and complete anonymous-download verification. This is not productive
Windows RPC or installed-application qualification.

- Retain main's Kotlin 2.4.20/security dependency outputs and macOS execution
  fixes while integrating the newer RPC Windows native/controller work.
- Add bounded installed-admission failure-stage diagnostics. Existing source,
  module, native ownership and cleanup checks remain; failure still exits nonzero.
- Preserve original-process Windows supervision and its six successful control
  results. The actual installed admission failed; the new diagnostic has not yet
  been qualified against a newly installed application.
- Repair the reconnect test's transient-StateFlow observation ordering without
  changing library behavior, deadlines, attempt limits or success assertions.
- Windows public protected-provider integration and sample RPC Host/Client remain
  unavailable. W01–W11 and other real installed/device/network acceptance remain
  open; this development candidate must not be presented as their completion.
  See the [current Windows scope](docs/rpc/windows-release-scope.md).

## 0.8.0-rc2 — release candidate (2026-10-17)

Published to Maven Central from immutable `v0.8.0-rc2`, source
`bd98deeb6ab44b5f5126d88742aa69b57f290c32`. The same-source frozen APK,
Windows x64 MSI, macOS ARM64 DMG and Linux x64 DEB are available in the
[development sample prerelease](https://github.com/p2pKit/P2pKit/releases/tag/samples-v0.8.0-rc2).
See the [release record](docs/releases/0.8.0-rc2.md) for exact approvals,
qualification, signed bundle, Central deployment and public-download hashes.

- Replace the undocumented internal Central namespace preflight with a bounded,
  authenticated request to the documented exact-namespace deployments API.
  This check reports token authentication and accepted namespace-query access,
  not namespace `VERIFIED` state. Actual Central publication and remote
  byte/consumer verification subsequently passed.
- Publish the combined Foundation/RPC changes described under the rc1 history
  below, including the 0.8-only discovery, admission and queue changes. RPC adds
  six coordinates to the existing fifteen. Its section is part of the existing
  samples rather than a separate application-release pipeline.
- Fresh same-source modular qualification, native ARM64/Intel simulator checks,
  and all four app builds passed. Separate protected Maven and post-build sample
  approvals were recorded; all seven public release assets passed complete
  anonymous-download hash verification. No rc1 artifacts were relabeled as rc2.
- Windows sample RPC Host/Client remains technically unavailable; protected
  loader/profile integration and real Windows runtime qualification are not
  completed. Physical-device, hostile-network, independent interoperability and
  professional-audit scopes remain open. Publication is not a production-readiness
  claim; the existing Kotlin advisory exception is not a remediation.

## 0.8.0-rc1 (tagged, not published)

The combined Foundation/RPC changes and subsequent release-admission repairs were
merged into `main`. Immutable `v0.8.0-rc1` points to
`8700583a5ae5aeaf5c77edee2a3ed4f5bd9a2d2c`. Maven
[run38941438027/1](https://github.com/p2pKit/P2pKit/actions/runs/38941438027)
failed the internal namespace API preflight with HTTP401 before signing or upload.
The existing tag, failed run and accepted source-bound qualification are preserved;
rc1 is not described as a published Maven release. The behavior notes below remain
applicable to its rc2 successor, without implying new qualification or approval.

### RPC prerelease target — 0.8.0-rc1

- The owner requests retaining the existing Windows RPC implementation and MSI while
  accepting post-release real Windows runtime qualification as a known prerelease risk.
  This is not a Windows functionality exclusion or a security-check waiver.
- **Windows limitation:** the RPC section and native components are present, but Windows
  sample Host/Client remains unavailable because secure native loading and production
  protected-profile integration are incomplete. Other Windows sample functionality is
  retained. The shared JVM RPC library is distinct from this sample-owned native backend.
- Standard-user protected-profile, actual JNI/provider and installed-application lifecycle
  tests are not passed. See [issue #462](https://github.com/p2pKit/P2pKit/issues/462) and the
  [owner decision and exact limitations](docs/rpc/windows-release-scope.md). Existing
  fail-closed controls remain intact; no unsafe loading/storage fallback is enabled.
- `0.8.0-rc1` is the intended prerelease, **not an already published version**. Required
  combined-source checks, Foundation approvals and canonical artifact freezing still apply.

### Audit-origin Android provisioning address snapshots — reserved for 0.8.0+

- #282: Android manual connection information and hosted-network snapshots now
  share one IO-dispatched all-interface scanner. Usable IPv4 is retained and
  portable non-link-local unicast IPv6 candidates are included, so dual-stack
  consumers can see additional addresses and IPv6-only snapshots need not be
  empty. Sender-local IPv6 zones and deprecated site-local IPv6 are excluded.
  A snapshot is not proof of peer reachability: LAN-only route admission and
  fingerprint-pinned authentication are unchanged. Physical IPv6/OEM
  qualification remains pending.
- This integrated but unreleased behavior expansion is **not approved for a 0.7 release** and
  is not part of published RC3. Honor the 0.8.0+ target or obtain an explicit
  owner release decision; no version/tag/publication authorization is implied.

### Audit-origin discovery tightening — reserved for 0.8.0+

- #229: JVM/Android decode original DNS-SD TXT bytes rather than JmDNS's
  normalized property map. Malformed UTF-8 in a consumed field rejects the
  complete record, including earlier duplicate values; empty/boolean values
  stay empty and trailing NULs reach the existing semantic rejection checks.
  Unknown fields remain ignored, and correctly encoded Unicode (including
  literal U+FFFD) remains valid. Valid peers, security profiles and the wire
  format are unchanged. JVM/Android invalid re-resolutions still withdraw their
  old route.
- #356: Apple reads the original bounded TXT bytes for both native dictionary
  and buffer records. Unknown NUL-containing keys cannot supply or overwrite
  canonical fields, and valid fields after those keys remain readable.
  Failed access, truncated framing and malformed consumed values reject the
  whole record. Absent records and valid Unicode/empty/duplicate-value behavior
  stay compatible. This decoder change does not change discovery cache lifecycle.
- #332 (Apple follow-up): a non-admissible current-browser re-resolution now
  withdraws that native service's prior cache, endpoint and relay ownership.
  Invalid TXT cannot select another peer for removal; retired callbacks cannot
  delete replacement ownership. Repeated rejection is idempotent and valid
  recovery publishes a fresh Found lifecycle. Existing dial/session ownership,
  manual endpoints and independent advertising remain unaffected.
- This integrated audit-origin change is unreleased, **not** part of published RC3 and
  **not approved for a 0.7 release**. The current snapshot version label does
  not override #229's 0.8.0+ requirement. A release must honor that target or
  obtain an explicit owner decision before changing it; no version/tag or
  publication authorization is implied here.

### Audit-origin receive-backlog accounting — reserved for 0.8.0+

- #145: receive admission no longer creates UTF-8 arrays just to measure text
  or metadata. The unchanged 64-message/8 MiB caps now use an approximate
  retention-policy charge: 512 bytes/message, two bytes/text UTF-16 code unit
  (or actual binary payload length), and 256 bytes/metadata pair plus two
  bytes/key and value code unit. Recorded ownership is released on delivery,
  failed-send rollback and terminal drain; defensive binary copies remain.
- This tightens admission, not the wire format or public ABI. A legal 4 MiB
  ASCII message alone exceeds the budget by 512 bytes and fails the receiving
  session. See [operational limits](docs/reference/limits.md). The estimate is
  not an exact platform or whole-session heap bound. This integrated but unreleased change is
  **not approved for a 0.7 release**; honor the 0.8.0+ target or obtain a new
  explicit owner decision. No version/tag/publication is authorized here.

## 0.7.0-rc3 — release candidate (2026-08-09)

This candidate preserves the RC2 public API and secure-v2 wire format while
incorporating the post-RC2 dependency, LAN recovery, sample-diagnostics, and
repository-hardening work. It is intended to be the exact artifact set used
for the remaining real-world and independent validation campaigns.
It was published from immutable tag `v0.7.0-rc3` under the verified
`io.github.apdelrahman1911` Maven Central namespace.

### LAN reliability

- Selects and owns routable JVM/Android LAN bindings deterministically,
  including Android selected-network socket routing, bounded JmDNS creation,
  serialized rebind cleanup, and metadata-free service removal.
- Hardens Apple browser-generation endpoint ownership, listener/browser path
  recovery, foreground coalescing, peer-to-peer/cellular policy symmetry, and
  terminal write-ready cleanup.
- Adds deterministic lifecycle, callback-race, removal, path-rotation,
  cancellation, and recovery regression coverage without treating simulator
  or host checks as physical-device evidence.

### Toolchain and distribution

- Updates to Kotlin 2.4.10 while retaining and inspecting the iOS 14 library
  deployment floor across every XCFramework slice.
- Updates Kotlin serialization, AndroidX/Compose, and Desktop Compose with
  locked dependency graphs, verification metadata, canonical serialization
  vectors, ABI checks, and cross-host Desktop packaging coverage.
- Keeps the verified `io.github.apdelrahman1911` namespace, signed Central
  bundle shape, provenance, SBOM, isolated-consumer, and immutable-tag gates.
- Rebuilds release signatures with daemon and build-cache reuse disabled so a
  prior disposable key or maintainer key rotation cannot contribute stale
  signatures to a Central bundle.

### Validation status

Android and Apple physical-device validation, two-machine hostile-network
testing, CLI fault injection/headful Desktop observation, independent
secure-v2 interoperability, and professional cryptographic audit remain
pending. Publishing this release candidate does not mark any of those areas
complete or claim production readiness.

## 0.7.0-rc2 — release candidate (2026-08-06)

This candidate preserves the `0.7.0-rc1` API, protocol, and implementation and
corrects only its unpublished Maven release identity. All artifacts now use
the owner-verified Central Portal namespace `io.github.apdelrahman1911`. The
`v0.7.0-rc1` tag remains immutable and was not published after Central rejected
the former unowned namespace during validation.

Published to Maven Central under `io.github.apdelrahman1911`. Android and Apple
physical-device validation, two-machine hostile-network testing, CLI
fault injection/headful Desktop observation, independent secure-v2
interoperability, and professional cryptographic audit remain explicitly
pending external evidence.

## 0.7.0-rc1 — release candidate (2026-08-04)

Remote Maven Central publication is not asserted by this source state.

### Security

- Authenticated protocol v2 is the default:
  `Noise_XX_25519_ChaChaPoly_SHA256` with persistent X25519 identities.
- Default authorization is fail-closed
  `PeerAuthorizationPolicy.RejectUnknown`.
- Added typed fingerprints, AppId-bound pairing QR text, exact per-connect
  pins, global pinned authorization, and an explicit-risk same-AppId admission
  policy.
- Authenticated messages and file-transfer control/content are protected by
  the secure record layer. Failed authentication never downgrades to plaintext.
- Secure and deprecated plaintext peers use separate discovery namespaces:
  `_p2pkit2._tcp`/protocol 2 and `_p2pkit._tcp`/protocol 1.
- Android secure identity uses Keystore-wrapped no-backup storage after
  `P2pKitAndroid.initialize`; iOS uses a device-only Keychain item. JVM hosts
  must provide a protected `JvmSecureIdentityStore`.

### Reliability and API behavior

- Retained independent advertising/discovery feature states and explicit
  transport capabilities.
- Hardened startup rollback, cancellation, reconnect, stop, file-transfer
  durability, parsing bounds, queue bounds, and session bookkeeping.
- Authenticated peers negotiate an application-message metadata envelope and
  durable SHA-256 file commit protocol.
- Public collection-valued models now expose immutable snapshots.
- Public API additions preserve the existing entry points; deprecated
  plaintext and legacy file APIs remain for an explicit migration period.

### Distribution

- Versioned as new `0.7.0-rc1` artifacts; existing `0.6.x` artifacts must not be
  overwritten.
- All four library modules produce Central-shaped POMs, sources, Dokka
  documentation, Gradle metadata, ABI baselines, dependency locks, and SBOM
  evidence.
- A credential-gated script builds a signed/checksummed Central Portal bundle
  without performing a remote upload.

See [`docs/guides/migrating-to-0.7.md`](docs/guides/migrating-to-0.7.md) before upgrading.

## 0.6.x

Legacy LAN protocol v1 line. Artifacts from this line are immutable.
