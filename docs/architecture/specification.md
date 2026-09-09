# Current high-level API and protocol contract

This document is the maintained high-level contract for the `0.7` release
candidate line. Public ABI files under each library module are the executable
binary-compatibility baselines; `api/android/` protects Android-only bytecode
that Kotlin's built-in JVM/KLIB validator does not inspect.

The [July design record](../archive/remediation/2026-07/P2pKit-Spec.md) is frozen
historical rationale, **not a current normative specification**. Its dated
status and milestone language do not describe this checkout. Use the maintained
[migration guide](../guides/migrating-to-0.7.md) for current migration instructions.

A complete, candidate-bound byte-level secure-v2 specification is still required
for [independent interoperability](../validation/secure-v2-interoperability.md)
and [cryptographic review](../validation/cryptographic-audit-preparation.md).
Neither this high-level page nor the archive fills that gap. For current
implementation behavior, inspect the exact candidate's source and ABI baselines;
if they disagree with a maintained contract, report and resolve the discrepancy
before using it as an independent test oracle.

## Lifecycle

- One `P2pKit` instance owns its transports, sessions, peer registry, and
  provisioning integration.
- `start()` initializes the instance. Advertising and discovery have separate
  observable feature states and may be controlled independently.
- A failed feature start settles its bounded rollback once. Cancellation during
  failure settlement cannot discard the original failure or its retained-cleanup
  marker; the caller's cancellation carries that failure as suppressed evidence.
- `stop()` is terminal for the kit and is idempotent. Host collectors and
  sessions should be cancelled/closed before final teardown.
- Feature-stop cleanup is not infallible: the kit reports incomplete cleanup
  as `ConnectionFailed` and retains failed ownership for retry. JVM/Android
  LAN idle teardown attempts watcher retirement and cancels queued rebind work
  even if native handle cleanup fails. Multicast release is attempted after
  the JmDNS handle closes, independently of watcher unregistration success.
- JVM/Android rebind probes and lock acquisition remain cancellable; canceled
  pre-transaction work cannot replace a newer binding. Native close/recreate is
  protected from cancellation only after lifecycle ownership is acquired.
- Restartable low-level data transports use `stop()` to return to an idle state;
  permanent cleanup is owned by the enclosing kit lifecycle.
- JVM/Android LAN advertisements require a bound TCP port. Starting advertising
  while the listener is detached fails with `TransportStartFailed` without
  clearing independent discovery intent. A detached listener during a JmDNS
  rebind rejects the new record and retains both feature intents for bounded
  recovery (five retries, delayed 2/4/6/8/10 seconds). Availability is not
  guaranteed while detached or after retry exhaustion; a new network target
  or explicitly stopping and restarting a feature can trigger another binding
  attempt.
- Provisioning-manager `close()` is suspending, idempotent, and permanent.
- Android hotspot hosting and Wi-Fi joining can coexist. `state` describes
  the latest operation/resource publication; `networkState` describes the
  latest successfully published network resource, not a combined inventory.
  An OS stop/release invalidates only snapshots owned by that resource and
  emits a failure event without waiting for another OS acquisition to finish.
  The event does not acknowledge native cleanup: serialized cleanup may emit
  a subsequent `CleanupFailed`, and failed cleanup remains owned for retry.
  `stopLocalNetwork()` releases hotspots only and preserves a joined network's
  snapshots; joined bindings are released by system loss or manager/kit close.

## Peer and session contract

- Public models expose deep snapshot values; callers do not receive mutable
  internal collections.
- Transport factories declare capabilities before creation. Unsupported
  features are not represented by ambiguous `null` success values.
- Incoming sessions and messages are hot streams. Subscribe before exposing a
  peer and attach collectors promptly.
- Only the outgoing owner reconnects. Clean close is terminal; interruption may
  enter bounded reconnect according to policy.

## Authenticated protocol v2

- Default handshake: `Noise_XX_25519_ChaChaPoly_SHA256`.
- Persistent X25519 identity is AppId-bound; discovered names and TXT values
  are never identity proof.
- The authenticated message envelope binds protocol version, message type,
  sender/recipient identity context, message identifier, sequence/replay data,
  content length, and digest using a canonical encoding inside the secure
  record layer.
- Authentication, envelope validation, replay checks, and version negotiation
  fail closed. There is no automatic downgrade to plaintext protocol v1.
- `_p2pkit2._tcp` is the secure-v2 discovery namespace. Deprecated plaintext
  v1 uses `_p2pkit._tcp` and is isolated.

## File transfer

- Incoming offers remain in `pendingFileOffers` until accepted, rejected,
  cancelled, expired, or cleaned up by lifecycle limits.
- Transfer failures use structured `FileTransferFailed` categories suitable for
  Kotlin, Java, and Swift mapping. On Java, `getKind()`, `getPhase()`,
  `getRetryability()` and `getTransferId()` are ordinary callable getters;
  this narrow mapping contract does not promise a complete Java SDK. See
  [consumer-language and Java interop limits](../compatibility.md#consumer-languages-and-java-interop).
- The sender hashes the exact prepared byte snapshot before transfer. The
  negotiated `file-commit-sha256-v1` flow transmits length and SHA-256, streams
  bounded chunks, verifies at the receiver, flushes and atomically commits the
  destination, then sends the commit acknowledgement. JVM destinations fsync
  file content and atomically rename it. POSIX JVM hosts additionally fsync the
  parent directory; the public JDK exposes no equivalent directory barrier on
  Windows, so that platform cannot guarantee the rename survives sudden power
  loss.
- Built-in JVM/Android destinations create no staging file until `openSink`.
  During receipt, unverified content is stored in a randomly named
  `.p2pkit-*.part` **sibling** of the target to preserve same-filesystem atomic
  publication. JVM POSIX staging is created with `0600` permissions; other
  filesystems use JDK temporary-file defaults and the parent's access policy.
  Android requests `0600` before opening the payload stream and fails if that
  permission operation fails. Choose a trusted, application-controlled directory
  with effective access restrictions; Android internal app storage is preferred
  when external storage does not enforce the required permissions. Same-user
  indexers, backup agents and cloud-sync clients can still read partial content:
  a hidden name or owner-only mode is **not** a backup/sync exclusion. Avoid
  watched/synced destinations when premature consumption is unacceptable.
  Crashes after opening may leave staging files; reconcile only files the
  application can establish it owns, not arbitrary prefix matches.
- For authenticated SDK sessions, JVM `sendFile(File)` retains no descriptor
  while its offer is pending. After acceptance it rechecks the reopened
  descriptor's length and SHA-256 before sending any payload, then rewinds that
  same descriptor for streaming. This adds a full read within the source-open
  `offerTimeoutMillis` budget. It is not an immutable snapshot: in-place edits
  after verification can be transmitted
  before the streaming digest check rejects them. Keep sources immutable when
  disclosure of concurrent edits is unacceptable.
- Duplicate/retry handling is transfer-ID based and must not create multiple
  committed outputs. SHA-256 detects corruption but is not authentication; the
  authenticated-v2 transport supplies authenticity.

## Operational limits

The [operational limits reference](../reference/limits.md) records current
values, source locations, scope and observable consequences for admission,
message/framing/reassembly, receive backlog, discovery and lifecycle deadlines.
It also distinguishes public configuration from internal policy. These bounds
do not promise a supported mesh size, total heap ceiling, aggregate shutdown
deadline or acknowledgement of remote application processing.

## Compatibility

The published `0.7.0-rc3` API and wire protocol are immutable. Later commits
may change repository paths and documentation but must not rewrite the tag,
coordinates, artifacts, ABI, or protocol. See [compatibility](../compatibility.md).
