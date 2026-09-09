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

For validation controls, event names, evidence export, and two-peer
correlation, follow the [validation handbook](../validation/README.md) and
[test catalog](../validation/test-catalog.md).
