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

Chat, file selection, and error UI still show the operator their data. The CLI
uses the displayed peer aliases in `connect`, `to`, `close`, and `sendfile`;
legacy ID prefixes and exact names also work. Use `offers` for filenames and
opaque `accept`/`reject` selectors. Explicit `info` output reveals local manual
endpoints, and `diag export` prints its output path. Do not share those outputs
unreviewed. Terminal control stripping prevents injection, **not** disclosure.

This policy does not sanitize library-owned LAN/frame traces or guarantee that
every field in a diagnostic export is private. Those are separate test-only
channels: use synthetic data, synthetic test/session labels and review evidence
before sharing it. Never copy tracing defaults into a production integration.

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
