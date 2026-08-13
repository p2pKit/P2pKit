# Current API and protocol specification

This document is the maintained high-level contract for the `0.7` release
candidate line. Public ABI files under each library module are the executable
binary-compatibility baselines; `api/android/` protects Android-only bytecode
that Kotlin's built-in JVM/KLIB validator does not inspect. The detailed design
record produced during the 0.7 remediation is preserved in
[`../archive/remediation/2026-07/P2pKit-Spec.md`](../archive/remediation/2026-07/P2pKit-Spec.md).

## Lifecycle

- One `P2pKit` instance owns its transports, sessions, peer registry, and
  provisioning integration.
- `start()` initializes the instance. Advertising and discovery have separate
  observable feature states and may be controlled independently.
- `stop()` is terminal for the kit and is idempotent. Host collectors and
  sessions should be cancelled/closed before final teardown.
- Restartable low-level data transports use `stop()` to return to an idle state;
  permanent cleanup is owned by the enclosing kit lifecycle.
- Provisioning-manager `close()` is suspending, idempotent, and permanent.

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
  Kotlin, Java, and Swift mapping.
- The sender hashes the exact prepared byte snapshot before transfer. The
  negotiated `file-commit-sha256-v1` flow transmits length and SHA-256, streams
  bounded chunks, verifies at the receiver, flushes and atomically commits the
  destination, then sends the durable acknowledgement.
- Duplicate/retry handling is transfer-ID based and must not create multiple
  committed outputs. SHA-256 detects corruption but is not authentication; the
  authenticated-v2 transport supplies authenticity.

## Compatibility

The published `0.7.0-rc3` API and wire protocol are immutable. Later commits
may change repository paths and documentation but must not rewrite the tag,
coordinates, artifacts, ABI, or protocol. See [compatibility](../compatibility.md).
