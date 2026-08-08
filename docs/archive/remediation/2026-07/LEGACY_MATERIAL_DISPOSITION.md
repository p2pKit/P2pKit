# Disposition of the previously protected July material

The owner authorized complete review and reorganization of these paths on
2026-08-08. The original content is preserved under this historical archive;
current actionable status lives in [`../../../validation/`](../../../validation/README.md)
and the live GitHub issue tracker.

| Original path | Useful content found | Verified current disposition | Retained location and rationale |
| --- | --- | --- | --- |
| `.review-2026-07/` | Review method/provenance, 18 subsystem reports, implementation notes, flake/stress logs, and unique raw test snapshots. | Its accepted findings were incorporated into the later authoritative review/remediation registers. The provisional findings draft is explicitly rejected. Three historical failing snapshots are not current regressions and may not be represented as a current pass. | [`review-campaign/`](review-campaign/README.md), preserved intact as historical evidence with an authority warning. |
| `DEFERRED_ITEMS_REGISTER_2026-07.md` | Owner decisions, external/platform blockers, publication prerequisites, flake watch list, and repository-hygiene notes at the July baseline. | The nine API/protocol decisions were later approved and implemented; Maven Central `0.7.0-rc2` was published under `io.github.apdelrahman1911`; the old remote/signing/publication blockers are superseded. Physical Android/Apple, hostile-network, CLI/Desktop observation, independent interoperability, and professional audit work remains relevant. | [`DEFERRED_ITEMS_REGISTER_2026-07.md`](DEFERRED_ITEMS_REGISTER_2026-07.md), retained because it explains historical decisions and evidence provenance, but not used as the living backlog. |
| `P2PKIT_FULL_CODE_REVIEW_2026-07-17.md` | The 150-item review source register across core, protocol, transfer, LAN, provisioning, samples, and build/release. | The local remediation tracker records all locally actionable findings/test gaps and exact commits/gates. Code existence and old one-time passes are not promoted to current external verification. The six evidence-dependent areas remain pending. | [`P2PKIT_FULL_CODE_REVIEW_2026-07-17.md`](P2PKIT_FULL_CODE_REVIEW_2026-07-17.md), retained as the immutable source review behind the tracker. |
| `P2PKIT_REMEDIATION_HANDOFF_2026-07-22.md` | Exact July branch/HEAD, completed batches, secure-v2 design, active LAN work, blockers, and continuation procedure. | Its uncommitted LAN batch and later dependency-ready batches were completed; its branch, remote, push, and pre-publication facts are historical. Secure-v2 design remains useful provenance, while current contract is maintained in `docs/architecture/specification.md`. | [`P2PKIT_REMEDIATION_HANDOFF_2026-07-22.md`](P2PKIT_REMEDIATION_HANDOFF_2026-07-22.md), retained as a dated handoff, not an instruction to resume from its old SHA. |

## Current unresolved substance

The historical sources were compared with current code, configuration, tests,
release evidence, and the remediation tracker. The remaining evidence classes
are consolidated into the six handbooks below:

1. [Android physical-device validation](../../../validation/android-physical-device.md)
2. [Apple physical-device and AWDL validation](../../../validation/apple-physical-awdl.md)
3. [Two-machine hostile-network validation](../../../validation/hostile-network.md)
4. [CLI fault injection and headful Desktop validation](../../../validation/cli-desktop-faults.md)
5. [Independent secure-v2 interoperability](../../../validation/secure-v2-interoperability.md)
6. [Professional cryptographic-audit preparation](../../../validation/cryptographic-audit-preparation.md)

Open GitHub issues remain authoritative for specific product defects and
measurement gaps. This archive must not be used to close a partially completed
issue or claim production readiness.
