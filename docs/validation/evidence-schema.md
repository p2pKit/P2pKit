# Validation evidence schema

This is the canonical schema for real-world, interoperability, and audit
results. The repository stores only redacted summaries and hash manifests.
Large or sensitive originals remain in owner-controlled private immutable
storage with versioning and retention enabled, except for the explicitly scoped
ordinary hosted-CI policy below.

## Ordinary hosted-CI retention exception

The owner/custodian `Apdelrahman1911` authorized **14-day GitHub Actions-only
retention** for ordinary FULL/Desktop CI evidence and its development-sample
qualification. See the [custodian procedure](../testing/evidence-custodian.md)
for exact source/configuration, key handling, access model and approvals.

For this scope only, the original packet is retained as `evidence.tar.gz.gpg`
plus its public `manifest.json`, under an immutable Actions artifact identity
with `retention-days: 14` and `overwrite: false`. Record repository, run/attempt,
artifact ID, service `created_at`/`expires_at`, ZIP digest, ciphertext digest and
review decision instead of promising a permanent private immutable URI. The
owner must retrieve/decrypt/inspect the originals while available. Public hashes
and redacted review records outlive the artifact; they cannot recreate it or
substitute for an inspection that never occurred.

GitHub access to ciphertext is **not owner-only** in this public repository.
Only the owner-held decryption key provides the intended plaintext confidentiality.
There is no separate long-term evidence backup or guarantee against authorized
early artifact deletion. Expiry is service-managed, not proof of exact-second
physical erasure or deletion of copies already downloaded. Local review copies
need the owner's private handling and disposal; the workflow cannot delete them.

This exception does **not** waive original-byte integrity, failure preservation,
native custody/retirement, required checks or either execution HOLD. It does not
change physical, hostile-network, independent-interoperability or other external
evidence requirements. The private custodian key/backup is not CI evidence and
must never be put in an Actions artifact. Public development app assets are a
separate, unencrypted distribution channel, not evidence-retention backups.

## Directory and identity

Private evidence uses:

```text
p2pkit/<candidate-sha>/<area>/<scenario-id>/<run-id>/
```

Repository summaries use:

```text
docs/validation/results/<version>-<commit-short>/<area>/<scenario-id>-<run-id>.md
```

A rerun always receives a new run and session ID. Failed evidence is never
overwritten by a later success.

## Required fields

Every result records:

- schema version;
- candidate commit and tree SHA;
- version and exact artifact coordinates or filenames;
- SHA-256 for every installed/tested artifact;
- test ID, scenario ID, run ID, shared session ID, and applicable connection,
  message, and transfer IDs;
- tester and independent reviewer;
- start/end UTC timestamps;
- platform, safely shareable device identifier, model, architecture, OS/build,
  application version/build, and peer role;
- network topology, interfaces safely exposed by the OS, router/AP identity,
  and exact impairment configuration/seed where applicable;
- configuration, protocol version, packet limits, timeouts, retries, and
  approved fault injection;
- expected and observed UI state;
- expected and observed stable diagnostic events;
- source/destination filename class, byte length, and SHA-256 without private
  contents;
- outcome: `PASS`, `FAIL`, `BLOCKED`, or `PENDING`;
- warnings, anomalies, cleanup result, raw-evidence location, per-file hashes,
  and reviewer decision.

## Status rules

- `PASS`: every mandatory assertion and evidence requirement for the run is
  satisfied and independently reviewable.
- `FAIL`: the case executed and any required behavior or evidence failed.
- `BLOCKED`: the case cannot execute because a named external resource,
  credential, environment, or owner authorization is unavailable.
- `PENDING`: it has not yet executed or its evidence review is incomplete.

An area becomes `COMPLETED` only after every mandatory matrix cell passes the
required repetitions. A UI success without matching internal and external
evidence is a failure, not a partial pass.

## Privacy and integrity

Never publish device serials/UDIDs, private keys, tokens, signing profiles,
credentials, private payloads, personal filenames, or raw user data. Use the
samples' anonymized identifiers and synthetic fixtures. Retain an unedited
private original when an OS log requires redaction for sharing.

Create a SHA-256 manifest over every raw evidence file. The committed summary
records the private immutable URI (or the scoped Actions identity above), manifest
hash, and review timestamp without embedding access credentials. Any hash
mismatch invalidates the run.
