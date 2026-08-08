# Validation status

## Completed locally or through publication infrastructure

- Complete committed module/platform gate, ABI baselines, strict Dokka,
  publication shape, isolated consumers, SBOM, signing, provenance,
  Swift warnings-as-errors, and XCFramework provenance have passed for the
  published `0.7.0-rc2` release commit.
- `BUILD-02` and `ENV-07` remote publication/consumer evidence are recorded in
  the [`0.7.0-rc2` release record](../releases/0.7.0-rc2.md).

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
