# Independent secure-v2 interoperability validation

**Status: NOT STARTED.** P2pKit-to-P2pKit tests share implementation code and
therefore do not prove independent interoperability.

## Purpose and independence requirement

Validate `secure-v2` against a separately implemented encoder, decoder, and
state machine. The harness must not link P2pKit artifacts, copy production
Kotlin source, call internal P2pKit codecs through reflection, or derive
expected output at runtime from P2pKit. It may use the public protocol
specification and independent cryptographic libraries. The reviewer must record
the harness repository, commit, language, dependencies, and the people who
implemented/reviewed it.

This is `SECURE-V2-INTEROP-01`. It is not a substitute for the professional
cryptographic audit.

## Normative material and source cross-checks

Freeze a protocol specification for the candidate SHA before testing. Cross-
check it against these implementation entry points without importing them into
the harness:

- `SecureProtocolV2Wire.kt`: 16-byte preface, role/version/suite fields,
  AppId-bound prologue, and length-framed handshake flights.
- `NoiseXXHandshake.kt` and `NoiseTypes.kt`: exact
  `Noise_XX_25519_ChaChaPoly_SHA256` state machine.
- `NoiseRecordCodec.kt` and `NoiseSecureRawConnection.kt`: record length,
  ChaCha20-Poly1305 nonce progression, and terminal failure.
- `Frame.kt`, `FrameCodec.kt`, `ProtocolConstants.kt`, and
  `FrameValidation.kt`: application frame header and packet rules.
- `Handshake.kt`/`HelloPayload.kt`: encrypted HELLO identity and version rules.
- `AppMessageEnvelope.kt`: canonical authenticated metadata, identities,
  sequence/message ID, length, SHA-256, and content.
- `FileTransferWire.kt` and transfer state machines: prepared digest, durable
  commit, result/error, duplicate, and cancellation behavior.
- `SecureIdentityService.kt`, platform cryptography implementations, and public
  authorization policies: fingerprints and key lifecycle.

The maintained high-level contract is
[`../architecture/specification.md`](../architecture/specification.md). If it
and code disagree, stop and file a protocol defect; do not silently teach the
harness the implementation accident.

## Independent harness deliverables

The harness must provide:

1. Pure encode/decode commands for prefaces, prologue, handshake frames, secure
   records, protocol frames, HELLO, message envelopes, and file-transfer
   payloads.
2. Initiator and responder servers capable of completing Noise XX with fixed
   and random keys and then exchanging records.
3. Deterministic RNG/key injection for known-answer tests, plus production-safe
   random mode for end-to-end runs.
4. Mutation commands for every length, magic, version, suite, role, reserved
   byte, packet type/flag, identity, sequence, digest, and ciphertext tag.
5. Transcript export containing public keys, public preface/frames, ciphertext,
   handshake hash, negotiated features, result codes, and timestamps—but never
   private keys from non-test runs.
6. A license and reproducible build. Pin dependency versions and archive an
   SBOM/checksum with results.

Test-only fixed private keys are permitted only as clearly labeled public test
vectors. Never use them as installed identities.

## Known-answer vector suite

Create stable vectors in both directions for:

- 16-byte preface magic `P2KS`, format 1, application version 2.0, suite 1,
  initiator/responder role, and all-zero flags/reserved bytes;
- prologue domain and UTF-8 AppId length/content, including empty, Unicode, and
  maximum-length boundaries;
- Noise XX flights with empty payloads and exact bodies of 32, 96, and 64 bytes;
- X25519 all-zero rejection, HKDF/SHA-256 chaining, handshake hash, split keys,
  ChaCha20-Poly1305 ciphertext/tag, and transport nonces starting at zero;
- secure record framing at zero, normal, maximum, over-maximum, fragmented, and
  coalesced stream boundaries;
- v2 application frames for every packet type and legal flag combination;
- canonical message envelopes with unsorted input metadata producing one
  unsigned-UTF-8-key order, sender/recipient binding, sequence, 16-byte message
  ID, content length, and SHA-256;
- file offer/accept/data/finish/commit/result values for 0, 1, chunk-boundary,
  and maximum supported content sizes.

Generate vector output independently, then run P2pKit tests that consume the
frozen bytes. Separately export P2pKit-produced bytes and verify them with the
harness. A vector is invalid if either side generated its expected value by
calling the other.

## End-to-end compatibility matrix

Run every supported pairing, with each side acting as initiator and responder:

| P2pKit implementation | Independent peer | Required platforms |
| --- | --- | --- |
| JVM LAN | Harness | Linux, macOS, Windows where supported |
| Android LAN | Harness | Two physical Android OS bands |
| Apple LAN | Harness | Physical iOS/iPadOS, infrastructure Wi-Fi and AWDL where harness routing permits |
| P2pKit platform A | Harness proxy/peer | Cross-platform Android↔JVM, Apple↔JVM, and Android↔Apple |

For each cell perform authorized and rejected fingerprints, bidirectional text
and binary messages, canonical metadata, 5 MiB durable transfer, cancellation,
disconnect/reconnect, and clean close. Correlate session, connection, message,
and transfer IDs in both transcripts.

## Negotiation, authentication, and negative matrix

The harness must independently prove:

- version/suite/role/reserved-byte mismatch fails before application data;
- AppId is bound into the transcript and a mismatch cannot complete;
- each side authenticates possession of its static X25519 key and the resulting
  fingerprint is checked by the configured authorization policy;
- initiator/responder reflection and simultaneous role confusion fail;
- no secure-v2 failure falls back to plaintext v1 or `_p2pkit._tcp`;
- tampered Noise flight, ciphertext, tag, frame header, envelope identity,
  metadata, content length/digest, or file digest fails closed;
- record nonce reuse, counter exhaustion boundary, replayed record, replayed
  message sequence/ID, duplicate transfer packet, and out-of-order state
  transition are rejected or handled exactly as specified;
- unknown bounded packet types follow the documented forward-compatibility rule
  while malformed/oversized packets terminate safely;
- truncated/coalesced reads and every byte boundary do not change decoding.

For malformed tests, record the exact mutation offset/value and expected phase
of rejection. The P2pKit sample UI must not show connected/completed when the
protocol transcript failed.

## File-transfer interoperability sequence

Verify this full sequence independently:

1. Sender opens/prepares an immutable source and hashes the exact advertised
   bytes before offering it.
2. Authenticated `FILE_OFFER` binds transfer ID, name, optional MIME, length,
   SHA-256, schema, and durable-completion requirement.
3. Receiver accepts at offset zero or rejects; resume is not claimed.
4. Sender streams bounded `FILE_DATA`, then sends `FILE_FINISH` with byte count,
   chunk count, digest, and offer hash.
5. Receiver verifies ordering/length/digest/offer hash, flushes, and atomically
   commits the destination before `FILE_COMMIT`.
6. Sender reports completion only after a matching authenticated durable commit.
7. Timeout, cancellation, storage failure, source mutation, digest mismatch,
   and duplicate packets produce the specified typed result and no duplicate or
   partial committed output.

SHA-256 alone is not authentication. Acceptance is secure only inside the
authenticated Noise transport and with authorization policy applied.

## Exact execution procedure

1. Pin P2pKit and harness commits; clean-build both and archive dependency/SBOM
   manifests.
2. Run pure known-answer encode/decode tests in both directions.
3. Run the compatibility matrix on isolated networks with synchronized clocks,
   packet capture, harness transcript, and sample evidence export.
4. Run every negative mutation individually from a fresh connection; never
   batch mutations so the failing cause is ambiguous.
5. Repeat each success and expected-failure case three times with new random
   ephemeral keys; run deterministic vectors separately.
6. Have a reviewer who did not implement both sides compare transcripts and
   independently decide pass/fail.

## Pass/fail and evidence

Pass requires byte-identical canonical vectors where specified, equivalent
state/results across all matrix cells, correct authenticated identities,
fail-closed negative cases, no downgrade/replay, and deterministic repeat runs.

Fail on any harness reuse of P2pKit code, unexplained byte difference, accepted
tamper/replay, plaintext fallback, identity mismatch accepted, nonce/counter
divergence, false UI success, corrupt/duplicate durable output, missing matrix
cell, or missing transcript.

Retain protocol spec version, both commits, harness source/build/SBOM, vectors,
public test keys, transcripts, redacted diagnostic exports, PCAP, mutation
manifest, file hashes, platform inventory, exact commands, and reviewer sign-
off. Keep real private/static keys out of evidence.

## Cleanup and completion checklist

Delete ephemeral non-vector keys and test identities, stop harness listeners,
restore networks/firewalls, and hash the evidence archive.

- [ ] Independent implementation and reproducible build reviewed.
- [ ] Bidirectional known-answer vectors passed.
- [ ] Full platform/role compatibility matrix passed.
- [ ] Negotiation/authentication/replay/malformed matrix passed.
- [ ] Durable file sequence and failures passed.
- [ ] Independent reviewer signed the archived result.
