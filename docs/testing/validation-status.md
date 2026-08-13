# Validation status

## Completed locally or through publication infrastructure

- Complete committed module/platform gate, ABI baselines, strict Dokka,
  publication shape, isolated consumers, SBOM, signing, provenance,
  Swift warnings-as-errors, and XCFramework provenance have passed for the
  published `0.7.0-rc3` release commit.
- `BUILD-02` and `ENV-07` remote publication/consumer evidence are recorded in
  the [`0.7.0-rc3` release record](../releases/0.7.0-rc3.md).

Those are immutable historical RC3 results. Current `main` is a post-RC3
`0.7.0-SNAPSHOT` development line. Automated results for current `main` do not
retroactively validate RC3, and RC3 results do not validate later fixes. The
six campaigns below must use one separately frozen commit and artifact set.

The final post-RC3 executable audit tree
`588421f59efd1bcb4cc7d3b7e1205b1ab28b4f85` (PR #103 head
`056708dfcda85d6b4aa9073c156ba386e17803b4`) passed complete gate
[31715657369](https://github.com/p2pKit/P2pKit/actions/runs/31715657369),
dependency review, both OSV contexts, and macOS/Linux/Windows Desktop checks.
It merged as `fbba43328df19cf72956df7417886361b335a570` with an identical tree.
This proves the repository's automated boundary; it is neither a published
release nor substitute evidence for the campaigns below.

## Pending external validation

The following remain pending and must not be described as verified:

1. Android instrumentation and physical-device validation.
2. Apple physical-device, AWDL, path-rotation, background, and process-restart validation.
3. Two-machine hostile-network validation.
4. CLI fault injection and headful Desktop observation.
5. Independent secure-v2 interoperability validation.
6. Professional cryptographic audit.

The exact equipment, steps, UI observations, logs, evidence exports, pass/fail
criteria, and result templates are in the
[real-world validation handbook](../validation/README.md). The cross-platform
tracker-ID procedures and logging matrix are in its
[test catalog](../validation/test-catalog.md).
