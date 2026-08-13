# Real-world and independent validation handbook

This directory is the authoritative execution handbook for validation that
cannot be completed honestly by a single local checkout. The latest published
release, `0.7.0-rc3`, is immutable historical release evidence. Current `main`
is a later `0.7.0-SNAPSHOT` development line containing post-RC3 corrections,
so tests of either tree do not certify the other.

Before any campaign starts, freeze one explicitly approved commit and artifact
set, then record its commit SHA, tree SHA, version, and artifact checksums in
every result. No post-audit campaign candidate has been designated by this
document, and no status below is upgraded without retained evidence from the
exact tested tree and artifacts.

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

Repository-side lifecycle/resource prerequisites for Android and Apple manual
provisioning were strengthened and host/simulator-tested in implementation
commit `fc73837cfa154caa82a6f96172603108b8577842`; the exact automated boundary
is recorded in the [GitHub audit](../maintenance/github-audit-2026-08.md).
That evidence does not change either physical campaign's status.

Apple LAN native listener/browser/dial ownership, rebind restoration, delayed
Bonjour work, and caller-versus-library timeout classification were further
strengthened and simulator-tested in implementation commit
`7af3a4bb85d6a9b6f688bfe7245fc5f28028c889`; the exact automated boundary is
recorded in the [GitHub audit](../maintenance/github-audit-2026-08.md). Real
AWDL, Personal Hotspot, path rotation, lifecycle, and timeout measurements
remain `NOT STARTED` and are not inferred from host or simulator evidence.

Repository-side secure-handshake result ownership, duplicate HELLO/legacy
FILE_OFFER field rejection, cancellation-preserving rejection diagnostics, and
monotonic reassembly expiry were strengthened in implementation commit
`c867c90c82a1a7b675fb2d19a055911ee6f8e4cd`; exact automated evidence is
recorded in the [GitHub audit](../maintenance/github-audit-2026-08.md). This
does not change the `NOT STARTED` independent-interoperability status or the
`EXTERNAL AUDIT REQUIRED` professional-review status.

## Shared execution contract

The [test catalog](test-catalog.md) is the canonical source for test IDs,
cross-platform preparation, exact sample builds, structured diagnostic events,
the sample capability matrix, and the result-record template. The six area
handbooks add equipment-specific procedures, environmental manipulation,
failure criteria, and cleanup steps. Read both the relevant handbook and the
catalog entry before execution.

The [evidence schema](evidence-schema.md) defines the permanent redacted record
format and the relationship between repository summaries and private immutable
raw evidence. Use the [result template](templates/result-record.md) for every
run; do not invent a second status format.

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
