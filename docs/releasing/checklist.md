# Release checklist

This checklist applies to a future non-snapshot release. It does not authorize
a tag or Maven Central publication.

Before selecting a version, review the unreleased behavior notes. The audit
branch's [#229 discovery-admission tightening](https://github.com/p2pKit/P2pKit/issues/229)
and its related [#356 Apple TXT decoder correction](https://github.com/p2pKit/P2pKit/issues/356)
and [#332 Apple invalid-resolution withdrawal](https://github.com/p2pKit/P2pKit/issues/332),
as well as [#145 receive-backlog admission tightening](https://github.com/p2pKit/P2pKit/issues/145)
and [#158 LAN inbound-queue depth alignment](https://github.com/p2pKit/P2pKit/issues/158),
are reserved for **0.8.0+**, despite the current snapshot label. Do not include
them in a 0.7 release without a new explicit owner decision. This checkpoint
neither changes the release version nor authorizes a merge/publication.

1. Update `VERSION_NAME` to the exact non-snapshot version and update current
   docs/changelog. Keep `LATEST_PUBLISHED_VERSION` at the previous release until
   remote publication is verified.
2. Confirm a clean worktree and exact ancestry from `origin/main`.
3. Run all script tests, `git diff --check`, and `scripts/run-release-gate.sh`.
   Retain its source-bound `build/reports/platform-tests/` execution report and
   a same-source native Intel `ios-x64` profile result (local or the manual/weekly
   Intel workflow). The arm64 gate cannot verify the published `iosX64` slice;
   no Intel execution may be inferred from cross-compilation. See the
   [platform coverage guide](../testing/local.md#platform-execution-evidence).
4. Run OSV, dependency submission, ABI, strict Dokka, SBOM, publication shape,
   isolated consumers, Swift warnings-as-errors, and XCFramework provenance.
5. Confirm `scripts/check-release-tag.sh v<VERSION_NAME>` and
   `scripts/check-maven-central-version.sh absent` pass.
6. Obtain explicit owner authorization for the exact tag and commit.
7. Push the immutable tag and allow the protected `maven-central` environment
   to perform signing, bundle validation, publication-build SBOM validation,
   provenance, and publication.
8. Verify remote bytes, signatures, checksums, metadata, and isolated consumers.
9. Create a release record, set `LATEST_PUBLISHED_VERSION`, open the next
   snapshot line, and create a GitHub prerelease/release entry.

Never move or recreate an existing release tag, weaken a gate, put secrets in
the repository, or publish a snapshot.

## Which build each gate covers

`verify-release` runs the secret-free complete gate on a verification build:
tests, ABI, Dokka, SBOM, local publication/consumers, and Apple/XCFramework checks.
The approved `publish-release` job separately rebuilds the exact source with
caches disabled; this signing isolation prevents stale key-specific signatures
from entering the bundle. The two builds are not claimed to be byte-identical.

The bundle builder checks the actual staged publication contents, signatures,
and checksums. Before upload, the publisher then regenerates its aggregate
CycloneDX SBOM without cached/up-to-date task outputs and validates both JSON
and XML. A generation or content failure blocks upload. Both files are retained
in `maven-central-publication-<tag>`, separately from verification-job evidence.
This SBOM describes the resolved library graph plus the explicitly identified
modified embedded JmDNS producer; it is neither an embedded Maven artifact nor
a scan of the ZIP's binary contents. Its private-producer JAR hash is not the
upstream JmDNS hash or an outer-publication hash; staged archive inspection
separately verifies the actual embedded members.

`scripts/check-sbom.sh` requires Python 3. It checks matching release identity,
component coordinates/hashes and dependency edges in the flat aggregate JSON
and CycloneDX 1.6 XML, including duplicate/unresolved references and contamination.
Inputs are limited to 16 MiB each before parsing; XML DTD/entity declarations
are rejected. Both formats must also match the reviewed vendor manifest,
actual source/resource/patch bytes, the owned producer JAR, upstream pedigree,
and LAN-to-embedded-to-SLF4J edges. Source/notice normalization is recorded in
the manifest; upstream archive hashes describe the original inputs. This is
not a full CycloneDX-schema or vulnerability scan.

OSV scans every populated Gradle lock plus the explicitly admitted
`library/p2p-transport-lan/vendor/jmdns/upstream.cdx.json`. That small inventory
is bound to the verified vendor manifest and retains real upstream Maven
advisory identity; it is not the modified component's runtime SBOM. The pinned
scanner supports the explicit `--sbom` input (deprecated upstream in favor of
`-L`). Existing advisory exceptions and their expiry remain unchanged; a local
lifecycle patch does not establish remediation of upstream advisories.

Remote byte comparison and isolated consumers run **after** publication; they
cannot roll back an immutable Central release. XCFramework checks cover a
separate source-built Apple output, not the Maven bundle. A secret-free dry run
does not execute the protected publisher; record that job's exact SHA and
evidence on the next authorized release rather than inferring it from CI.

## Archive license policy

For future candidate builds, the root `Jar`/`BundleAar` rules copy the repository
`LICENSE` rather than maintaining per-module legal text. The existing
`scripts/check-publish-artifacts.sh [existing-repo-dir]` gate enforces:

| Artifact class | Required content / inspection |
| --- | --- |
| Main JVM and KMP-metadata JARs; six native `-metadata.jar` archives; Android AARs | Exactly one `META-INF/LICENSE`, byte-identical to repository `LICENSE`. |
| Every publication's `-sources.jar` and Dokka `-javadoc.jar`, including iOS coordinates | The same single canonical embedded license, in addition to the existing source/index checks. |
| Six Kotlin/Native main `.klib` and three LAN `-cinterop-p2pkit_nw.klib` archives | Explicit **embedded-license-check exemption**: not produced by `Jar`/`BundleAar`, and not rewritten. The gate requires each archive to exist and be readable, plus the sibling POM's Apache-2.0 metadata; the six main KLIBs also retain their existing identity checks. It prints `EXEMPT`, not an embedded-license pass. |
| Source-built `P2pKitShared.xcframework` | Separate Apple output, not an artifact in this Maven publication set. Its provenance/minimum-OS checks do not certify license embedding. A redistributor must separately include the applicable license/notice material. |

The complete macOS set has 54 archives: 45 license-covered JARs/AARs and nine
explicitly exempt KLIBs, across 15 publication coordinates.
Every checked publication produces success, failure or an explicit KLIB
exception; missing, changed or duplicate license entries in a covered JAR/AAR
fail the gate. Non-macOS omission of the six iOS publication rows is a host
execution limitation, **not** that license exception or a complete release pass.
Retain a macOS inspection of the complete publication set before release.

This describes packaging/check scope, not legal advice or a waiver of Apache-2.0
redistribution obligations. A vendored KLIB without its POM is not promised to
carry license text. Include the repository license and applicable notices when
redistributing; do not infer compliance from `EXEMPT`. Previously published RC
artifacts/tags remain immutable; their embedded contents require their own byte
inspection and are not inferred from today's build rules.
