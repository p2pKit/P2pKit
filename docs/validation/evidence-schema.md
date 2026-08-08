# Validation evidence schema

This is the canonical schema for real-world, interoperability, and audit
results. The repository stores only redacted summaries and hash manifests.
Large or sensitive originals remain in owner-controlled private immutable
storage with versioning and retention enabled.

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
records the private immutable URI, manifest hash, and review timestamp without
embedding access credentials. Any hash mismatch invalidates the run.
