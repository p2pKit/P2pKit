# CLI fault injection and headful Desktop validation

[Current campaign status](README.md#cli-desktop). Automated parser,
diagnostics, transfer and build coverage is separate from the controlled
process/network failures and real-display observation in `PS-T05` and `PS-T06`.
Those procedures require their own complete evidence-bearing campaign; do not
infer it from the table's partial automated-coverage status.

## Purpose and separation

This plan verifies the packaged JVM CLI and Compose Desktop sample under
operator error, process failure, transport interruption, bounded resource
pressure, and prolonged headful use. Production protocol/security settings
must remain unchanged. Faults are introduced by the OS, network lab, synthetic
files, or a separately reviewed test wrapper—not by hidden production toggles.

## Required environment

- Two JVM 17 processes with separate identity profiles, preferably on two
  machines; one machine is acceptable for process-only cases.
- macOS, Linux, and Windows coverage for the Desktop UI before the area is
  complete; at minimum one real graphical display per OS, not headless Xvfb.
- A terminal recorder (`script` or `asciinema`), screen recorder, process and
  resource monitors, synthetic files, and an isolated test network.
- An approved UI automation tool appropriate to the OS. Store scripts with the
  result evidence; do not add platform-specific credentials to the repository.

## Build and immutable setup

```bash
export EVIDENCE=<absolute-evidence-directory>
export SESSION=ps-t05-<unique-safe-id>
test -z "$(git status --short)"
./gradlew --no-daemon \
  :p2p-sample-diagnostics:test \
  :p2p-sample-desktop:test \
  :p2p-sample-desktop:installDist \
  :p2p-sample-desktop-ui:test \
  :p2p-sample-desktop-ui:compileKotlin
```

Create distinct temporary `user.home`/identity-profile locations for Alice and
Bob and record their permissions. Start the CLI instances with bounded JSONL:

```bash
script -q "$EVIDENCE/cli-alice.typescript" \
  ./gradlew :p2p-sample-desktop:run \
  -Pp2pkit.sample.identityProfile=alice \
  --args="Alice p2pkit-desktop-sample reconnect=5,1000 trace=frames test=PS-T05 session=$SESSION role=sender evidence=$EVIDENCE log=$EVIDENCE/alice.jsonl"

script -q "$EVIDENCE/cli-bob.typescript" \
  ./gradlew :p2p-sample-desktop:run \
  -Pp2pkit.sample.identityProfile=bob \
  --args="Bob p2pkit-desktop-sample reconnect=5,1000 trace=frames test=PS-T05 session=$SESSION role=receiver evidence=$EVIDENCE log=$EVIDENCE/bob.jsonl"
```

Run `diag`, record both peer IDs, and confirm the session IDs match. At the end
of every case use `diag complete <outcome>` and `diag export` before process
cleanup. See the `PS-T05` event sequence in
[`test-catalog.md`](test-catalog.md).

Immediately before each externally applied fault, run
`diag fault <type> <expected-effect>`. This command only timestamps and records
the operator action; it does not alter the SDK, authentication, transport, or
production defaults. Use the same short `<type>` in the wrapper transcript.

## Automated and controlled CLI cases

### D1 — command and option contract

At the prompt run `info`, `peers`, `sessions`, `adv off/on`, `disc off/on`,
`mesh off/on`, `connect`, `manual`, `send`, `to`, `sendfile`, `offers`,
`accept`, `reject`, `close`, every `diag` form (including `diag fault`), and
`quit`. Exercise:

- `--help`, unknown options, duplicate named options, blank values, malformed
  `reconnect`, invalid `trace`, invalid role/test/session, and overly long input;
- ambiguous peer prefixes/names and a peer disappearing after selection;
- EOF on stdin and a terminal closed without `quit`.

Each invalid command must produce sanitized help/error text and leave the
process usable. It must not reinterpret an invalid option as a device name,
print control characters, or change security defaults.

### D2 — peer crash, signals, and abrupt stream termination

During handshake, idle connection, and 49 MiB transfer separately:

1. Send `SIGSTOP` to Bob for longer than keepalive/timeout, then `SIGCONT`.
2. Send `SIGTERM`; repeat with `SIGKILL` as the crash case.
3. Close Bob's stdin; close the terminal emulator; kill Alice while receiving.
4. Restart the peer with the same profile, then with a new profile.

Record `diag fault` immediately before steps 1–3 with the exact signal/action.

Use `ps`, `jcmd`, or the OS equivalent to retain PID/process-tree evidence.
Graceful termination must execute teardown once. Record crashes explicitly;
never infer transfer completion from a crash or locally submitted bytes. Apply
D3's acknowledgment and reconciliation rules to in-flight transfers and
previously committed receiver files. Reconnect is bounded by five attempts at
the configured delay and identity reset follows the authorization policy.

### D3 — socket and network failures

Use the [hostile-network handbook](hostile-network.md) for approved firewall and
interface controls. Inject connection reset, silent drop, blocked discovery,
blocked data port, interface down/up, and repeated reconnect. Correlate every
OS action with a timestamped `network.path.changed`, timeout/retry, and terminal
event where observable. For authenticated-v2 file transfers, distinguish:

- **Incomplete or integrity-invalid data:** the receiver must not commit it;
  uncommitted staging files must be cleaned up.
- **Acknowledgment lost after receiver commit:** the receiver commits before
  sending `FILE_COMMIT`. If that acknowledgment never reaches the sender, the
  sender must time out/fail rather than report completion, but a complete
  committed receiver target may remain. Missing acknowledgment is not proof
  that no receiver output exists.

Use transfer-unique destinations. Correlate both peers' session/transfer IDs,
terminal states, fixture hashes, and the receiver's filesystem evidence before
retrying. Preserve a published target for reconciliation; never delete it merely
because the sender failed or acknowledge before commit to satisfy this campaign.
Do not assume retries across sessions automatically reconcile existing files.
Apply the [destination contract](../../library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/transfer/FileTransferResources.kt#L45)
and [platform durability limits](../architecture/specification.md#file-transfer),
including possible late publication after a commit timeout and Windows' lack
of a directory-entry power-loss guarantee.

### D4 — malformed and corrupted input

Do not feed raw bytes by modifying the production sample. Use the separately
reviewed independent secure-v2 harness to send truncated prefaces, invalid
frame lengths/types, malformed envelopes, duplicate/replayed records, corrupted
ciphertext, invalid file metadata, and incomplete transfer chunks.

The CLI must remain alive where policy permits, reject the connection/transfer
with a typed sanitized error, and never print/decrypt sensitive payload data.
Cryptographic invalid-input cases also belong to the
[interoperability plan](secure-v2-interoperability.md).

### D5 — safe resource pressure

Set explicit host safety limits before execution. Use a small temporary quota or
dedicated filesystem for receiver storage, lower file-descriptor/process limits
only for the child process, and select the specific
[admission/backlog bound](../reference/limits.md#admission-and-application-receive-backlog)
under test. Distinguish per-source LAN admission, core concurrent handshakes,
and net-new inbound session registration; a single source is limited before
it can occupy all core handshake slots. Use only authorized synthetic peers,
and send legal messages/transfers within a preapproved byte budget. Never fill
the system disk or induce host-wide memory pressure.

Expect the limit-specific outcome in that reference, not a universal typed
admission error: an inbound refusal is logged and the connection is closed;
application-backlog overload fails the session. Storage/transfer operations
report their structured failures. Require bounded logs/history and cleanup of
uncommitted `.part`/reservation files, then release test pressure and verify a
subsequent valid operation (using a new session if necessary). Record heap,
CPU, descriptors, threads, disk usage, the tested limit and the safety cutoff.

## Headful Desktop UI campaign

Launch two isolated instances or one UI plus the CLI:

```bash
./gradlew :p2p-sample-desktop-ui:run -Ddev.p2pkit.lan.trace=true -Ddev.p2pkit.lan.traceFrames=true
```

On **Setup**, enter a unique **Device name**, the same **App ID**, and reconnect
settings `maxAttempts=5` and `retryDelayMillis=1000`; then select **Start**.
Open the top-right **Diagnostics** action, start `PS-T06` with the shared
session ID, and keep screen recording active.

### Manual observation checklist

1. Toggle **Advertise**, **Discover**, and **Auto-mesh** and compare each visible
   feature state with diagnostics. Stopped discovery must not retain stale peers
   beyond the documented lifecycle.
2. Connect two peers. Verify peer identity, connection ID, secure-v2 version,
   session state, and error banners remain internally consistent.
3. Use the native file chooser. Accept, reject, cancel, interrupt, retry, and
   complete transfers; compare progress and hashes to exported events.
4. Rapidly toggle features and **Stop**/**Start** while starting, connected,
   offered, and transferring. Close the window in each phase and verify one
   clean JVM exit with no orphan process.
5. Apply D2-D5 faults. The window must remain responsive and enable a valid
   recovery path; an error must not be replaced by a stale success state.
6. Run the approved soak: at least 1,000 bounded terminal operations or the
   approved byte/time budget. Active rows must never be evicted; completed
   history, JSONL, and memory must stay within documented bounds.
7. Pause/filter/search diagnostics and choose **Export Test Evidence**. Verify
   the ZIP opens and its session/transfer IDs match the UI.

Observe responsiveness, repaint/input latency, CPU, resident/heap memory,
thread count, open descriptors, inbox/temporary files, and shutdown duration at
baseline, midpoint, and end.

## Pass/fail and evidence

Pass requires the documented outcomes (including logged inbound refusals in
D5), matching UI and structured events on each peer where exposed, correct hashes for
success, no partial/corrupt committed output, cleanup of uncommitted staging,
bounded retries and resources, one teardown, no orphan process, and three
repeat runs of each mandatory fault on every target OS. In D3's lost-ack case,
sender failure and a complete receiver target are compatible: record each
side's outcome separately and retain the target for reconciliation. A logged
refusal is not evidence that a typed admission API exists.

Fail on crash outside an intentional kill, freeze, false success, contradictory
local terminal states, mixed transfer IDs, unsanitized control text, secret/payload
logging, unbounded growth, leaked process/resource, lost consent, stale active
row, corrupt/partial commit, or missing/crossed evidence.

Retain both JSONL/ZIP exports, terminal transcripts and exit codes, screen
video/screenshots, automation log, exact fault commands/timestamps, process
tree, heap/resource samples, filesystem listing, fixture hashes, OS/JVM/build
versions, and the completed catalog result record.

## Cleanup

Terminate all child processes, verify no sample JVM remains, restore firewall,
interfaces, quotas and `ulimit`, remove only temporary identity profiles and
synthetic inboxes after hashing evidence, and confirm normal network/disk state.

## Completion checklist

- [ ] CLI option/command and EOF/shutdown matrix passed.
- [ ] Crash, signal, socket, malformed-input, and safe-resource cases passed.
- [ ] Headful macOS, Linux, and Windows observation passed.
- [ ] Soak remained bounded and responsive.
- [ ] UI, terminal, peer exports, hashes, and OS evidence correlate.
