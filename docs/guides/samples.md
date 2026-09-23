# Samples and diagnostic applications

All samples live under `samples/` and are excluded from Maven publication.
Their detailed diagnostics are explicit test functionality, not production
configuration recommendations. Sample admission policies can be deliberately
permissive; the library's default remains fail-closed authenticated v2.

| Project | Role | Main test capabilities |
| --- | --- | --- |
| `:p2p-sample-android` | Android sender and receiver | Discovery/session controls, provisioning, file picker, progress, SHA-256, diagnostic viewer/export |
| `:p2p-sample-desktop` | JVM CLI sender and receiver | REPL commands, pinned manual endpoint (full out-of-band fingerprint required), fault-test arguments, JSONL/evidence export |
| `:p2p-sample-desktop-ui` | Compose Desktop sender and receiver | Peer/session/file controls, diagnostic viewer, export, headful observation |
| `:sample-kmp-shared` | KMP consumer smoke | Common call-site and Android/JVM runtime consumer coverage |
| `:iosApp` | Swift iOS sender and receiver | Peer/session/file controls, deterministic files, lifecycle, diagnostics/share export |
| `:p2p-sample-diagnostics` | Shared JVM diagnostics model | Structured event schema, redaction, rotation, and evidence package support |

## Pairing with a verified fingerprint

The CLI's `pairing` (also `info`) displays the **complete** local fingerprint
and AppId-bound QR text. Android, Desktop UI and iOS have **Show local pairing
information** in the running screen; reveal and select/copy the full text.
This is a text payload, not a camera/scanner feature. Exchange it through a
trusted channel, not a discovery record, chat with an unknown peer, or a
diagnostic export. Names, aliases and AppId are not trust signals.

To exercise the README's discovered-peer pinning flow using two CLI instances:

1. Run both with the same explicit AppId on a controlled LAN, for example
   `./gradlew :p2p-sample-desktop:run --args="Alice com.example.pairing"`
   and the same command with `Bob`. The CLI is a permissive development harness
   with auto-mesh on; enter `mesh off` in both, then `close <peer-alias>` for
   any existing connection. Turning off mesh does not reject incoming peers.
2. On Bob, enter `pairing`; deliver the full `p2pkit:v2:…` value to Alice
   out of band. On Alice, `peers` lists opaque selectors.
3. Enter `connect-pinned <bob-alias> <bob-full-pairing-QR>` on Alice.
   The command validates the exact AppId and calls `connect(peer, fingerprint)`;
   malformed/other-AppId QR input is refused, and a different proved key fails
   with `AuthenticatedIdentityMismatch`, including for an existing session.
4. `to <bob-alias> hello` sends a greeting. A successful send is a local write,
   not evidence that Bob's application processed it. To test a negative pin,
   supply a different same-AppId instance's QR for Bob; no new session is admitted
   by that command. An earlier session, if any, is not disconnected by a failed pin.

This pins **that outgoing connection**, not the whole harness's incoming
admission. All four interactive apps still use the warned development policy;
unknown same-AppId peers may connect. The KMP sample's `createPinnedP2pKit`
demonstrates `PinnedOnly(trustedFingerprints)` for incoming allowlisting, while
`createP2pKit` defaults to `RejectUnknown`. Its `runDiscoverAndGreet` requires an
out-of-band fingerprint and a `displayLocalPairingQr` callback for the host's
pairing UI, then pins the discovered peer. It never silently logs that QR.

JVM sample keys are in-memory per kit: re-exchange the QR after restart or
Desktop Stop/Start. Android/Apple use their platform secure identity stores;
storage reset or app removal can also require re-pairing. Manual CLI/Desktop
dialing consumes the displayed full `p2f1-…` fingerprint; iOS manual dialing
consumes the whole QR. `info` supplies CLI endpoints. These flows do not provide
internet signaling, NAT traversal, or automatic fallback to plaintext.

### Pinned manual CLI connection

The CLI command is `manual <host>:<port> <full-p2f1-fingerprint>`. The full
fingerprint is mandatory; missing or malformed pins are rejected before dialing.
Unlike `connect-pinned`, this command takes the bare fingerprint, not the QR.

1. Start Alice and Bob with the same explicit AppId as above. Enter `mesh off`
   on both and close any existing connections before testing the manual path.
   Keep Bob running; `disc off` may disable discovery without stopping its
   listener, since manual dialing does not need mDNS.
2. On Bob, enter `info`. Exchange a reachable address from `manual host(s)`,
   `manual port`, and the complete `fingerprint` value with Alice through a
   trusted out-of-band channel. `pairing` also displays the full fingerprint.
3. On Alice, replace the placeholders and enter
   `manual <bob-host>:<bob-port> <bob-full-p2f1-fingerprint>`. For an IPv6
   address, use `[<bob-ipv6-address>]:<bob-port>`. Wait for
   `connected manual peer <alias>`, then use `sessions` to inspect the session.
4. Enter `to <bob-alias> hello` on Alice and check Bob's receive observation;
   Alice's send result alone does not prove receipt. A wrong but well-formed
   pin must fail authentication rather than fall back to an unpinned dial.

Re-exchange pairing information after a JVM kit restart. This outgoing pin does
not change the harness's permissive incoming admission policy described above.

## Android provisioning lifetime

The Android sample subscribes before allowing provisioning calls. Its hotspot and
join cards follow separate resource lifetimes, not just the acquisition result or
the manager's last-owner snapshots. System stop/release removes the corresponding
live claim and credentials/endpoints without erasing the other live resource.
Stopping the hotspot does **not** leave a joined network; stop the kit to release
that binding. Dismissing an established join only hides that binding's card, not a
later successful join (even to the same SSID). A later genuine release is shown as
a failure; a refused repeat join does not release the binding.

A failed or cancelled hotspot stop keeps **Retry hotspot stop** available without
requesting acquisition permissions. Retry does not restart hosting; a successful
stop call clears that intent and leaves an independent join intact. Kit retirement
clears its presentation without acknowledging native cleanup. Permission requests
also check current intent, so a stale acquisition button cannot prompt after Stop
was admitted. Startup failures still retry startup. A startup `CleanupFailed` may describe
different native owners: the card also offers explicit hotspot stop, with whole-kit
Stop as the fallback for all retained cleanup. Untagged cleanup events are not
treated as proof that a live hotspot ended or that its cleanup succeeded.

The presenter records the Android manager's hot-flow events without waiting for
the UI thread, then applies the latest two-resource snapshot on the main thread.
Keep that recorder non-suspending: do not put UI, logging or native work in it.
Manager close or kit replacement retires its subscriptions and pending UI work;
the kit/manager, not the presenter, owns native cleanup. Events are not cleanup
acknowledgements. This sample wiring is not a general replay/history guarantee for
late subscribers to the library's event flow.

API calls are serialized. An asynchronous `Pending` join keeps the join control
disabled even after dismissal, while allowing hotspot controls once the API call
returns. Android's current manager instead awaits its bounded OS callback before
returning. A genuine join success clears ephemeral input even when immediate
release or dismissal prevents a `Joined` card from being rendered. Passphrases
remain non-saveable, obscured by default, and cleared on stop/disposal; a permission
grant never silently resubmits a cleared credential.

## Android diagnostic viewer

The diagnostic viewer observes the recorder's revision as a real Compose snapshot
dependency: new events refresh the list and summary without touching a control.
Its cached list is keyed by revision, filter and source. A successful session clear
also advances the revision even though clearing emits no diagnostic event; a failed
clear preserves the in-memory display and reports the storage failure.

**Pause live logs** freezes the displayed list, not recording. Filter/session changes
and new events continue to update the live snapshot, which is shown on resume.
Leaving the composition cancels its revision collector; reopening reads current
history. These are bounded diagnostic snapshots, not an event-delivery guarantee
or a measured frame-performance claim.

## Desktop UI security posture

The Desktop UI is a development harness, not a trusted room. Its persistent
warning discloses `AcceptAnyAuthenticatedSameApp`: any authenticated same-AppId
peer may connect. AppId is a public scope identifier, not an authorization secret.
Auto-mesh defaults **off**; enabling it explicitly starts unpinned outgoing
connections. Turning it off does **not** block incoming same-AppId connections.
Manual Connect to a discovered peer is also unpinned; the manual-endpoint flow
requires a full fingerprint.

Each new kit uses a new in-memory identity store, so identity changes on kit
recreation, including Stop/Start. Diagnostic exports record
`securityPolicy=authenticated-same-app-test-only` and
`identityStorage=in-memory-per-kit`. Production integrations must use a durable
OS-backed `JvmSecureIdentityStore` and `PeerAuthorizationPolicy.PinnedOnly` with
independently verified fingerprints; see the [security model](../security/model.md).
Encryption does not by itself establish the peer identity you intended to trust.

## Console privacy

Sample-owned console/logcat lines report message type and UTF-8 byte count,
opaque `anon-…` peer/transfer aliases, fixed states, and error types/codes—not
chat bodies, device names, SSIDs, file paths, or exception descriptions. SDK
logger delegates omit free-form details rather than trusting regex redaction.
Hashes support correlation; they do not make observations unlinkable. A local
send result never establishes remote application processing.

File preparation read failures stop that send with a type-only console error.
An optional diagnostic hash reread can fail after a successful receive commit;
that warning does not undo `Completed`, delete published bytes, or replace the
protocol's integrity and durability checks. Preparation cancellation is not
reported as an ordinary read failure.

Chat, file selection, and error UI still show the operator their data. The CLI
uses the displayed peer aliases in `connect`, `to`, `close`, and `sendfile`;
legacy ID prefixes and exact names also work. Use `offers` for filenames and
opaque `accept`/`reject` selectors. Explicit `info` output reveals local manual
endpoints; `info`/`pairing` also deliberately reveal local public pairing identity,
and `diag export` prints its output path. Do not share those outputs
unreviewed. Terminal control stripping prevents injection, **not** disclosure.

This policy does not sanitize library-owned LAN/frame traces or guarantee that
every field in a diagnostic export is private. Those are separate test-only
channels: use synthetic data, synthetic test/session labels and review evidence
before sharing it. Never copy tracing defaults into a production integration.

The iOS sample enables LAN console mirroring only in **Debug**. Its scoped lease
retains up to 200 in-app diagnostic lines in both configurations so the startup
permission probe can see early events. Stop (including failed teardown) and
create/start failures release that opt-in; the last overlapping owner restores
the host's previous settings and clears replay if retention was previously off.
Release builds never change the host's console-mirror setting. The on-screen
log and structured diagnostic recorder remain available; they are not erased by
releasing the library's replay buffer.

Both JVM samples leave raw LAN/frame tracing **off by default**. The CLI accepts
`trace=on` for LAN events and decoded frame metadata, or `trace=frames` to add
socket byte-chunk counts; `trace=off` (the default) adds no sample opt-in. CLI LAN
leases restore previous switches on exit/failure, combine active requests and
preserve the host flags captured when the first lease starts. Frame sinks have
single-current-owner semantics: release never detaches a newer sink, but does
not restore an older sink. Previously recorded diagnostics are not erased.
No trace contains file/message bytes, but topology, names and
traffic metadata still require private handling.

For the Desktop UI, opt in at process startup (no UI toggle is required):

```bash
./gradlew :p2p-sample-desktop:run --args="Desk trace=on"
./gradlew :p2p-sample-desktop-ui:run -Ddev.p2pkit.lan.trace=true
# Optional additional socket byte-chunk counts:
./gradlew :p2p-sample-desktop-ui:run -Ddev.p2pkit.lan.trace=true -Ddev.p2pkit.lan.traceFrames=true
```

The UI run task forwards these properties to the child JVM. A packaged UI can
use `JAVA_TOOL_OPTIONS='-Ddev.p2pkit.lan.trace=true'` when launching instead.
The UI does not overwrite LAN switches; those explicit properties belong to
the host process. Structured application diagnostics remain available without
enabling raw tracing. Never share trace output without reviewing it.

## iOS sample backup policy

The iOS sample keeps received files in app-private `Documents/P2pKitInbox` and
exported packages in `Documents/P2pKitEvidence`; it does not enable Files-app
sharing. It explicitly excludes both managed directory hierarchies from future
OS backups without moving or deleting existing contents. First appearance
prepares both roots independently, and every receive/export reapplies exclusion
before reservation or ZIP staging, including after directory recreation.

A failed setup shows a fixed warning with **Retry storage setup**. Existing
contents may remain backup-eligible after failure; a new receive/export for the
affected root is refused, not silently allowed. An independent root's failure
does not block a successfully prepared inbox or evidence root. General recording,
networking and the checked current-session clear remain independent.

Default iOS file protection (`CompleteUntilFirstUserAuthentication`) is deliberately
unchanged; stronger locked-device protection would alter transfer behavior.
This is **not** blanket diagnostics exclusion or Android `allowBackup=false`
parity: the rotated JSONL files under
`Library/Application Support/P2pKitTestDiagnostics` remain backup-eligible.
Setting a root flag neither erases earlier backups nor controls copies made by a
user's share target. Simulator resource-key and synthetic-transfer tests are not
physical backup observations; inspect a newly created, owner-controlled physical
device backup with synthetic data before claiming that external validation.

## Running samples

Common build commands:

```bash
./gradlew :p2p-sample-android:assembleDebug
./gradlew :p2p-sample-desktop:installDist
./gradlew :p2p-sample-desktop-ui:run
./gradlew :iosApp:runIosSimulator
```

Android APK output is under
`samples/p2p-sample-android/build/outputs/apk/debug/`. The installed JVM CLI is
under `samples/p2p-sample-desktop/build/install/`. The iOS project is generated
from `samples/iosApp/project.yml`; do not hand-edit the ignored `.xcodeproj`.
For XcodeGen, signing prerequisites, and the generated provenance phase, see the
[iOS sample scripts guide](../../samples/iosApp/scripts/README.md).

### Download development apps from Releases

The separate [Development sample Releases workflow](../../.github/workflows/sample-development-releases.yml)
promotes successful, reviewed **main** builds to the repository's
[Releases page](https://github.com/p2pKit/P2pKit/releases). Its introduction is
source work, not evidence that a sample prerelease has already been published.
The current strict-lock, custody, build and review prerequisites still apply.
The [owner/custodian procedure](../testing/evidence-custodian.md) defines the
two manual approvals and the separate encrypted-evidence channel. Release apps
are **public, unencrypted assets**; downloading them needs neither an evidence
private key nor access to an Actions artifact.

Development prereleases use **`samples-<full-source-SHA>`**, never `v*` library
tags. They do not change the snapshot version, published RC history or Maven/Store
publication. They are not marked as the latest stable release. Only complete
Android, Windows, macOS and Linux sets may be published:

| Release asset | Contents |
| --- | --- |
| `P2pKit-samples-android-<sha12>.apk` | Android debug sample; download the APK directly. |
| `P2pKit-samples-windows-<arch>-<sha12>.msi` | Windows Desktop UI installer, including its Java runtime. |
| `P2pKit-samples-macos-<arch>-<sha12>.dmg` | macOS Desktop UI disk image, including its Java runtime. |
| `P2pKit-samples-linux-<arch>-<sha12>.deb` | Desktop UI package for compatible Debian/Ubuntu systems, including its Java runtime. |
| `sample-notices.zip` | Source-bound P2pKit/JmDNS license and notice files. |
| `sample-release.json`, `SHA256SUMS` | Exact source/tree, producer run/attempt/artifact IDs, formal PR/check identities and SHA-256/size bindings. |

Choose your platform's package from **Releases → Assets**, verify `SHA256SUMS`,
then open it using the operating system's normal installation process. Keep the
notices when redistributing. These are **unchanged files from the inspected Actions
bundles**, not recompilations or re-signed copies. Use the recorded architecture;
this is not an all-architecture or genuine-Intel qualification claim. Complete
UI images and separate CLI distributions remain in Actions; the CLI requires Java 17+.
Development packages are not production-signed/notarized and may be rejected by
OS trust policy. Do not disable security controls; trusted production distribution
requires a separate authorized signing/notarization process.

The publisher executes no artifact contents, compiler, Gradle, signing or app
launch. Its read-only admission requires the normal merged PR's preserved final
head, the owner's exact-head authorization, all applicable PR checks, and genuine
main CI/OSV plus one complete three-host producer attempt. All four protected PR checks,
including `review` and Code Scanning's `osv-scanner` result, are required on that
reviewed PR head. Main separately requires its exact-source `complete-gate` and
`scan / osv-scan` workflow checks, not a second copy of PR-only results.
Missing/failed/ambiguous checks
or expired artifacts leave **HOLD**, not a partial release. Squash/rebase merges
need separately reviewed equivalence support; this lane currently admits the
normal history-preserving merge only. The required owner sequence is:

1. `Apdelrahman1911` creates the PR. After its final head's required checks pass,
   the owner personally posts a **new, unedited** PR comment containing exactly
   `/p2pkit approve-pr <full-final-head-SHA>`. A changed head or later required
   check needs a fresh authorization. This is the owner-approved replacement for
   GitHub's unavailable self-`Approve` review, not a fabricated native review.
2. The owner manually makes a normal preserving merge whose **actual main merge
   commit message** contains the exact case-sensitive marker **`[release ci]`**.
   A marker in a PR description or an earlier branch commit does not count.
3. Qualified main CI, OSV and the three-host producer complete, with original
   encrypted FULL/Desktop evidence available. Neither approval lifts execution
   HOLDs or supplies missing qualification.
4. `prepare-review` inspects the app bundles and retains
   `sample-release-review-<publisher-run>-<attempt>`. The owner retrieves and
   privately decrypts/reviews the four evidence artifacts identified in its
   `review-request.json`, then approves the protected
   `sample-development-release` environment using the **exact generated**
   `APPROVE_EVIDENCE <publisher-run>/<attempt> <review-request-sha256>` comment.
5. Only then may the publisher recheck all bindings and publish the development
   prerelease. No automatic PR approval or merge is implemented. Missing, edited,
   stale or wrong-head PR authorization and missing/wrong-attempt evidence
   approval refuse publication. Manual publication and reruns use the same gate.

The PR comment is a mandatory **publisher admission** check; it is not a new
GitHub native merge-protection rule. Existing required checks and thread-resolution
rules are unchanged. The agent must never post either owner approval on the
owner's behalf. Environment administrator bypass must be disabled; the publisher
refuses a configuration that still allows it.

Main Desktop push and CI/OSV push, scheduled or manual completions re-evaluate
readiness without occupying the build queue or dispatching another build. A newer
failed check is never hidden by an older success. A failed readiness run can precede the remaining
checks; later completion or exact manual resumption rechecks them. No old result
is relabeled as proof for a changed source. Ordinary main pushes still request
normal required CI, but **only an admitted marked main merge requests Release
APK/installer packaging and ordinary sample uploads**. Unmarked Desktop runs keep
all six normal verification tasks and encrypted-evidence custody. A readiness
workflow may be notified of an unmarked completion; it refuses Release admission
without starting another build.
For a **no-publication** rehearsal, after the workflow is merged and prerequisites
are satisfied:

```bash
gh workflow run sample-development-releases.yml --repo p2pKit/P2pKit --ref main \
  -f operation=verify -f source_sha=FULL_SOURCE_SHA \
  -f producer_run=EXACT_RUN_ID -f producer_attempt=EXACT_ATTEMPT
```

`verify` has no repository-write permission and cannot approve publication. The
separately isolated `publish` operation, also used by eligible marked-main
completions **after the protected evidence approval**, copies only the four explicitly
validated package members (never a general archive extraction), verifies their
original hashes, and uploads those existing bytes plus notices/provenance to a draft
prerelease. It checks the complete remote asset digests before
publication/read-back, followed by credential-free one-byte download probes of
every public asset. These probes check anonymous access, not a second full-file
hash verification. A same-source tag freezes its first accepted producer and
manifest. Matching partial drafts can resume missing assets; wrong hashes,
unknown assets, collisions and incomplete published releases fail closed. No
overwrite, deletion or tag movement is performed. Do not use reruns to replace
expired output with a rebuilt artifact under an existing release identity.

Read-only implementation tests are not a real no-publication rehearsal or
publication result. The [source milestone](../maintenance/sample-app-workflows-2026-09-15.md)
and [#437](https://github.com/p2pKit/P2pKit/issues/437) retain execution/review holds.
Raw test transcripts never enter app bundles, publisher review artifacts or
Releases. Only the separate recipient-admitted ordinary evidence artifacts retain
encrypted originals; app distribution does not authorize raw evidence upload.

#### After Maven Central publication

Once this wiring is merged into `main`, each successful **Publish Maven Central**
tag-push completion automatically starts the sample publisher. Failed publications,
ordinary commits and publication outside that maintained workflow do not trigger
this Maven hand-off. It verifies the original publisher run/attempt, both successful
verification/publication jobs, immutable `v<VERSION_NAME>` tag and the exact
tagged `gradle.properties` version before selecting the matching main sample build.

The resulting public development prerelease is **`samples-v<VERSION_NAME>`**,
with the Maven version/run recorded in `sample-release.json`. It contains the
same APK, Windows x64 MSI, macOS ARM64 DMG and Linux x64 DEB plus notices/checksums described
above. It neither modifies the library's `v*` tag/release nor replaces the
separate `samples-<SHA>` or existing preview releases.

This is a delivery hand-off, **not another build system**: the marked main merge
already requests the source-matched four-platform build. Its inspected installer
bytes are reused without recompilation. All current HOLDs, marked-merge/PR/main
checks, original encrypted evidence and fresh post-build owner approval remain
mandatory; a successful Maven publication cannot substitute for them. Missing or
expired matching apps/evidence cause HOLD, never reuse of an unrelated preview.
If gates finish later, rerun the sample publisher with its original Maven event,
not the immutable Maven publication. Reruns still require fresh exact-attempt
evidence approval and may not overwrite tags/assets. No new Maven publication or
qualified-main readiness is authorized by this automation.

### Download development apps from Actions

The **Desktop cross-host** workflow requests verification on **every push to
`main`** and relevant sample/library/build pull-request changes; the current
activation HOLD still prevents ordinary execution. Its ordinary manual operation
remains `desktop`. The native Ubuntu, Windows and macOS jobs run serially. On an
admitted main merge containing `[release ci]`, packaging tasks are added to the
same six-task verification batch; Ubuntu also assembles the Android APK. Without
that marker, ordinary verification retains `installDist`/`createDistributable`
checks but does not request Release installers/APK or upload sample bundles.
Required library/full CI gates remain separate and are not replaced by apps.

For an explicit build-only preview, select the manual **`sample-apps`** operation.
It compiles/packages the same Android and Desktop outputs but does not run the
CLI/UI test suites. Ordinary `desktop`, PR and main verification retain their
existing tests. A preview is not a required-check or runtime pass, and a work-branch
preview is retained in Actions rather than published as a main development Release.

After a **successful marked-main producer or explicit preview**, its Actions
page provides these 14-day artifacts. Actions downloads require GitHub sign-in
and repository read access; the eventual public Release assets above do not:

| Artifact name prefix | Contents |
| --- | --- |
| `sample-android-` | Android debug APK, manifest, checksums and notices. No emulator is needed to build it. |
| `sample-desktop-Linux-` | Desktop UI runtime image and JVM CLI distribution, each as `.tar.gz`. |
| `sample-desktop-Windows-` | Desktop UI runtime image and JVM CLI distribution, each as `.zip`. |
| `sample-desktop-macOS-` | Desktop `.app` runtime image and JVM CLI distribution, each as `.tar.gz`. |

Names include the full source SHA, run ID and attempt, plus the observed runner
architecture for Desktop. A `macos-15` runner label alone is **not** Intel evidence.
Use the architecture in `manifest.json`; the workflow does not build every possible
CPU architecture. Downloads contain the complete application/runtime, not only a
launcher. The CLI distribution separately requires Java 17 or newer.

To find a main run without starting another build:

```bash
gh run list --repo p2pKit/P2pKit --workflow desktop-cross-host.yml --branch main --status success --limit 5
gh run view RUN_ID --repo p2pKit/P2pKit
gh run download RUN_ID --repo p2pKit/P2pKit --name EXACT_ARTIFACT_NAME --dir NEW_DOWNLOAD_DIRECTORY
```

Replace the uppercase placeholders with the inspected run/artifact values. Check
the manifest's repository, commit/tree, event/ref and run/attempt against that run;
do not mistake a PR-merge or manual candidate artifact for accepted main output.
Inside the downloaded directory, verify `checksums.sha256` with `sha256sum -c`
(Linux or Git Bash) or `shasum -a 256 -c` (macOS), then extract the inner archive.
Keep the full extracted directory together. Unix tar archives preserve executable
permissions and internal links that a raw Actions directory upload would lose.

These are **development test harnesses**, not a production release. Each native
packaging host builds one existing installer format in the same Gradle batch: Linux DEB,
Windows MSI or macOS DMG. UI runtime images and CLI archives are retained too.
Android uses the debug build task, not a Store signing key.
Desktop has no production signing/notarization step; OS trust checks may reject
it. Do not disable OS security controls to make an unqualified download appear
trusted. This build stage uses no signing credentials, tags, releases or Store
uploads; the separate development-prerelease promotion above consumes its bytes.

The packager checks source/run consistency, native launcher/VM architectures,
application/CLI layout and archive bytes/modes/links. Installer inspection covers
the expected container header and exact byte hashes, **not installation or signer
qualification**. Android inspection checks
AGP output metadata and APK ZIP structure/CRC, **not** the binary manifest or
signer identity. None of these checks launches an app or proves LAN, UI, phone,
independent-interoperability or release acceptance. The existing sample warnings
and permission/consent requirements still apply.

The explicit preview uses the pinned Gradle setup action's dependency/wrapper
caches, excluding the affected Kotlin build cache. Ordinary Desktop instead
requires the [qualified consume-only dependency path](../testing/hosted-dependency-cache.md):
exact admitted dependency bytes, no whole-home restore or silent cold fallback.
Each host uses its own job-owned home, two workers, no parallel Gradle and strict
verification. Both Java 17 and 21 are installed explicitly. Cache hits can reduce
downloads; they do not prove resolver reuse, guarantee zero transfer or excuse
stale dependency locks. Failed builds/stops/packaging do not
publish application artifacts. The existing CLI test execution additionally needs
the [subprocess custody prerequisites](../testing/local.md#subprocess-transcript-custody-on-failure);
app artifact retention is not a replacement for that private test-evidence contract.

For validation controls, event names, evidence export, and two-peer
correlation, follow the [validation handbook](../validation/README.md) and
[test catalog](../validation/test-catalog.md).
