# Professional cryptographic-audit preparation

**Status: EXTERNAL AUDIT REQUIRED.** P2pKit is **not professionally
cryptographically audited**. This document prepares a review package; it is not
an audit report, certification, or security endorsement.

## Purpose and auditor qualification

Commission an independent firm or named specialist with demonstrated protocol,
Noise, X25519, ChaCha20-Poly1305, Kotlin Multiplatform, Android Keystore, Apple
Keychain, and JVM cryptography experience. Require conflict-of-interest
disclosure, a written scope, secure disclosure channel, evidence retention,
severity rubric, remediation review, and signed final report.

## Proposed audit scope

Include, at minimum:

- secure-v2 negotiation, Noise XX handshake and transcript binding;
- platform cryptographic-provider equivalence;
- static/ephemeral key generation, storage, loading, reset, and failure paths;
- fingerprint derivation, authorization policies, manual pins, and identity
  changes;
- secure record framing, nonces/counters, replay and terminal-failure behavior;
- encrypted HELLO, authenticated application metadata, version/downgrade rules;
- durable file-transfer integrity, acknowledgment, cancellation, duplicates,
  and failure mapping;
- discovery claims as untrusted routing hints and their relationship to
  authenticated identity;
- secrets in memory, persistence, logs, diagnostics, crash reports, samples,
  publication artifacts, CI, and dependencies;
- denial-of-service bounds at preface, handshake, record, frame, metadata,
  session, pending offer, transfer, and logging layers.

Out-of-scope items must be explicit. Internet signaling/NAT traversal, user
accounts, human identity, authorization by application business logic, endpoint
OS compromise, and malicious already-authorized peers are not silently assumed
to be solved.

## Threat model package

Prepare a versioned threat model describing assets, actors, trust boundaries,
and attack surfaces. It must cover:

- passive LAN observer; active MITM; malicious discovery advertiser; replay and
  downgrade attacker; unauthorized but same-AppId peer; compromised authorized
  peer; resource-exhaustion peer; local unprivileged process; rooted/jailbroken
  device; malicious test/export consumer; and supply-chain attacker;
- confidentiality/integrity/authenticity of messages and files, persistent
  identity keys, authorization pins, application metadata, availability, and
  privacy of diagnostic output;
- assumptions about trusted out-of-band fingerprint exchange, platform RNG,
  Keystore/Keychain/provider correctness, filesystem permissions, transport
  ordering, OS lifecycle, and application validation of decrypted input;
- residual risks and explicit non-goals from
  [`../security/model.md`](../security/model.md).

For every claimed property, identify the enforcement code and a negative test.

## Protocol specification package

Freeze a byte-level secure-v2 specification for the audited commit, including:

1. Discovery namespaces and fields; which values are only routing claims.
2. 16-byte preface and fail-closed format/application version, suite, role,
   flags, and reserved bytes.
3. AppId-bound Noise prologue and exact
   `Noise_XX_25519_ChaChaPoly_SHA256` token/state sequence.
4. Static and ephemeral X25519 public-key encoding, invalid/all-zero handling,
   HKDF/SHA-256, handshake hash, split keys, and key direction.
5. ChaCha20-Poly1305 record length, associated data, nonce construction,
   increment/exhaustion, fragmentation/coalescing, and terminal authentication
   failure.
6. HELLO/version/features, duplicate-field ambiguity rejection, and
   authorization timing.
7. Application frame header, packet types/flags, maximum sizes, unknown-type
   policy, message envelope canonicalization, sequence/message-ID replay state,
   identities, metadata bounds, length, digest, and content.
8. File offer/data/finish/commit/result state machine, digest scope, prepared
   source, durable persistence semantics, timeouts, cancellation, duplicates,
   crash behavior, and lack of resume at nonzero offset.
9. Close/reconnect and simultaneous-open state transitions.

The independent [interoperability handbook](secure-v2-interoperability.md)
defines the external vector/matrix evidence the auditor should receive.

## Key lifecycle and platform assumptions

Document separately for Android, Apple, and JVM:

- entropy/RNG source and provider selection;
- persistent record format/version and integrity checks;
- Android Keystore wrapping/no-backup storage and failure/reset behavior;
- Apple device-only Keychain accessibility and failure/reset behavior;
- the JVM requirement for caller-supplied confidential, integrity-protected,
  cross-process-safe storage;
- copy boundaries, defensive snapshots, temporary key material, best-effort
  zeroization, garbage-collected memory limitations, and crash/core-dump risk;
- identity reset semantics, pin invalidation/reapproval, backup/restore,
  migration, concurrent process access, and rollback resistance assumptions.

Do not claim guaranteed zeroization on managed/native runtimes unless the
auditor confirms the exact platform behavior.

## Source-code entry points

Provide an indexed source bundle and call graph for:

- `library/p2p-core/.../internal/security/noise/`;
- `SecureIdentityService.kt`, `SecureIdentityStorage*`, and each platform secure
  identity implementation/maintenance API;
- `SecurityManager.kt`, `SessionManager.kt`, `Handshake.kt`, and `HelloPayload`;
- `protocol/Frame*`, `ProtocolConstants`, `AppMessageEnvelope`,
  `FileTransferWire`, sender/receiver/reassembler code;
- public `SecurityConfig`, authorization policies, identity/fingerprint types,
  errors, lifecycle, transport capabilities, and provisioning/manual pin APIs;
- LAN discovery/data transports and selected-network/AWDL route controls;
- diagnostic redaction/export and sample trust-policy configuration;
- Gradle dependency catalogs, lockfiles, SBOM/provenance/signing workflows, ABI
  dumps, release configuration, and published source artifacts.

Use permanent links to the exact audited commit, not moving `main` URLs.

## Test and evidence package

Supply the auditor with:

- all unit/property/integration/fuzz tests and exact gate commands;
- known-answer vectors for X25519, SHA-256, Noise handshake/transport, envelope,
  frame, and file-transfer formats;
- independent interoperability results when available, clearly marked pending
  otherwise;
- hostile-network/device results when available, clearly marked pending
  otherwise;
- ABI/API documentation, threat model, protocol diagrams/state tables,
  dependency inventory/SBOM, OSV results, provenance attestations, and release
  reproduction instructions;
- historical review/remediation archive, including previously found security
  issues and how code/tests addressed them;
- a list of accepted risks, owner decisions, open GitHub security-relevant
  issues, and any test flakes with disposition.

Test vectors must contain only public, deliberately synthetic keys and data.

## Questions requiring explicit expert review

Ask the auditor to answer at least:

- Is the Noise XX implementation byte/state compatible and resistant to state
  confusion, reflection, invalid keys, transcript mismatch, nonce reuse, and
  authentication-oracle behavior?
- Does the preface/AppId/version/suite binding prevent downgrade and cross-AppId
  channel confusion without unsafe fallback?
- Are static-key fingerprints and all authorization modes described and
  enforced accurately, including manual pins and identity reset?
- Are platform RNG, key encoding/storage, provider APIs, failure paths, copies,
  and best-effort wiping adequate and equivalent?
- Does record/frame/envelope parsing enforce bounds before allocation and fail
  safely under truncation, coalescing, malformed lengths, unknown types,
  replays, and concurrency?
- Is metadata fully authenticated/canonical, and are message/file identity,
  length, digest, sequence, and transfer state bound correctly?
- Does durable commit occur before sender success under filesystem, crash,
  cancellation, retry, duplicate, and source-mutation scenarios?
- Can diagnostics, errors, samples, storage, CI, or published artifacts leak
  secrets or materially weaken production defaults?
- Are timing, denial-of-service, dependency, and side-channel risks acceptable
  for the stated threat model?

## Dependency and build review

Archive the exact resolved dependency graph, lockfiles, Gradle/JDK/Kotlin/
Android/Xcode versions, source and binary SBOMs, OSV/dependency-review results,
Maven Central signatures/checksums/POMs, provenance, and reproducible build
instructions. Ask the auditor to identify cryptographic code supplied by each
platform/library and evaluate provider/version assumptions.

## Deliverables and severity rubric

Require:

- kickoff scope/threat-model confirmation;
- private draft findings with file/line/commit, exploit scenario, preconditions,
  impact, reproducible evidence, and remediation guidance;
- severity using a declared rubric (for example Critical/High/Medium/Low/
  Informational) with likelihood and impact separately explained;
- protocol/implementation review, platform-storage review, dependency/build
  review, and test-coverage gap analysis;
- a signed final report identifying the exact commit and unresolved findings;
- a retest letter/report for every fixed Critical/High and agreed Medium item;
- a public summary only after coordinated disclosure and owner approval.

An absence of findings is not equivalent to formal verification. Any scope
limitation must appear prominently in the final report.

## Remediation and retest workflow

1. Triage privately; assign IDs, severity, owner, affected versions, disclosure
   deadline, and whether release use must pause.
2. Reproduce without weakening tests/security. Add deterministic regression
   tests and implement the architectural fix on a protected branch/PR.
3. Run the full repository/release/security gate and independent
   interoperability/device cases affected by the change.
4. Send exact commits and evidence to the original auditor for retest.
5. Record fixed, mitigated, accepted, disputed, and outstanding findings. An
   owner may accept risk but must not label it “verified.”
6. Coordinate advisories/CVEs and downstream notice when published versions are
   affected.

## Preparation checklist

- [ ] Auditor selected and conflict/scope/NDA/disclosure terms signed.
- [ ] Exact commit and immutable source/dependency/build bundle prepared.
- [ ] Threat model, byte-level protocol, state machines, and key lifecycle complete.
- [ ] Entry-point map, tests, vectors, prior findings, and open risks supplied.
- [ ] Independent interoperability and device/network evidence supplied or explicitly pending.
- [ ] Secure communication and vulnerability-triage process exercised.
- [ ] Draft review, remediation, retest, and final signed deliverables completed.

Until every applicable step is completed by a qualified external auditor, the
status remains **EXTERNAL AUDIT REQUIRED**.
