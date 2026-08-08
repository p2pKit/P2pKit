# Real-world and independent validation handbook

This directory is the authoritative execution handbook for validation that
cannot be completed honestly by a single local checkout. The published release
is `0.7.0-rc2`; the development line is `0.7.0-rc3-SNAPSHOT`. No status below
is upgraded without retained evidence from the exact tested commit.

## Current status

| Area | Status | Handbook | Principal tracker coverage |
| --- | --- | --- | --- |
| Android physical devices | **NOT STARTED** | [Android physical-device validation](android-physical-device.md) | `PROV-A12`, `PT-T20`, `LAN-T01`, `PS-T01`, `PS-T02`, `PS-T04`, Android portions of `ENV-01`, `PS-T08`, `PS-T09` |
| Apple devices and AWDL | **NOT STARTED** | [Apple physical-device and AWDL validation](apple-physical-awdl.md) | `LAN-T07`, `ENV-01`, `ENV-04`, `PS-T07`, `PS-T08`, `PS-T09` |
| Two-machine hostile networks | **NOT STARTED** | [Hostile-network validation](hostile-network.md) | `LAN-T08`, `ENV-02` |
| CLI fault injection and headful Desktop | **PARTIALLY VALIDATED** | [CLI/Desktop validation](cli-desktop-faults.md) | `PS-T05`, `PS-T06` |
| Independent secure-v2 interoperability | **NOT STARTED** | [Secure-v2 interoperability](secure-v2-interoperability.md) | `SECURE-V2-INTEROP-01` |
| Professional cryptographic review | **EXTERNAL AUDIT REQUIRED** | [Cryptographic-audit preparation](cryptographic-audit-preparation.md) | `CRYPTO-AUDIT-01` |

`PARTIALLY VALIDATED` for CLI/Desktop means local builds and automated tests
exist. It does not mean the fault-injection and headful observation procedures
have been executed. P2pKit has **not** received an independent professional
cryptographic audit.

## Shared execution contract

The [test catalog](test-catalog.md) is the canonical source for test IDs,
cross-platform preparation, exact sample builds, structured diagnostic events,
the sample capability matrix, and the result-record template. The six area
handbooks add equipment-specific procedures, environmental manipulation,
failure criteria, and cleanup steps. Read both the relevant handbook and the
catalog entry before execution.

Every accepted result must include:

1. The exact commit SHA, a clean checkout, application/build versions, UTC
   clock state, tester, device model, OS version, and network topology.
2. One unique test ID and session ID. Two-peer tests use the same session ID on
   both peers and preserve their connection/transfer IDs.
3. UI observations plus `Export Test Evidence` from each graphical sample, or
   `diag export` and bounded JSONL from the CLI.
4. The commands and configuration actually used, screenshots or video for UI
   claims, OS logs, and packet captures when required by the handbook.
5. Start/end timestamps, file names/sizes and independent SHA-256 values for
   transfers, a pass/fail decision, and a link to immutable evidence storage.

A green UI alone is never sufficient. A test passes only when the visible
state, both peers' correlated structured events, protocol outcome, and required
external evidence agree.

## Evidence handling

- Synchronize clocks before two-peer tests and retain original, unedited files.
- Name the evidence directory `<test-id>/<UTC timestamp>-<commit-short>/`.
- Hash every retained artifact (`shasum -a 256` on macOS or `sha256sum` on
  Linux) and keep a manifest beside it.
- Never collect private keys, tokens, credentials, signing material, private
  payload contents, or personally identifying device data. Use only synthetic
  test files and the samples' redacted exports.
- A rerun receives a new session ID. Never overwrite failed evidence with a
  later successful run.

## Completion rule

An area becomes `COMPLETED` only when every mandatory case in its handbook has
passed on the required matrix and an independent reviewer can reproduce the
decision from retained evidence. Any skipped mandatory case, missing peer log,
uncorrelated session, or unexplained warning leaves the area pending.
