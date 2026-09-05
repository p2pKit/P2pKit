# Samples and diagnostic applications

All samples live under `samples/` and are excluded from Maven publication.
Their detailed diagnostics are explicit test functionality, not production
configuration recommendations. Sample admission policies can be deliberately
permissive; the library's default remains fail-closed authenticated v2.

| Project | Role | Main test capabilities |
| --- | --- | --- |
| `:p2p-sample-android` | Android sender and receiver | Discovery/session controls, provisioning, file picker, progress, SHA-256, diagnostic viewer/export |
| `:p2p-sample-desktop` | JVM CLI sender and receiver | REPL commands, manual endpoint, fault-test arguments, JSONL/evidence export |
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

For validation controls, event names, evidence export, and two-peer
correlation, follow the [validation handbook](../validation/README.md) and
[test catalog](../validation/test-catalog.md).
