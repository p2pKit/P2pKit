# Release checklist

This checklist applies to each future non-snapshot release. It does not authorize
a tag or Maven Central publication. The latest verified library publication is
[`0.8.0-rc8`](../releases/0.8.0-rc8.md), from exact source
`6c85fdc2977386e572830c243f9aa8bb17d84ec3`. Maven
[41028814149/1](https://github.com/p2pKit/P2pKit/actions/runs/41028814149)
passed, including complete remote consumers and byte comparison of 242 remote
files (121 original artifacts plus their signatures). Separate sample delivery
[41035118810/1](https://github.com/p2pKit/P2pKit/actions/runs/41035118810)
passed and published the [sample prerelease](https://github.com/p2pKit/P2pKit/releases/tag/samples-v0.8.0-rc8)
at the same source. Independent, complete anonymous downloads verified all seven
public assets against the approved original application and supporting-file
hashes, without rebuilding the four applications. This verifies delivery, not
installed execution or physical-device qualification.

The rc8 aggregate
[41028216266/1](https://github.com/p2pKit/P2pKit/actions/runs/41028216266)
passed all fourteen components and 125 commands, retaining all four original
applications unchanged. Original source component
[41023086404/1](https://github.com/p2pKit/P2pKit/actions/runs/41023086404)
failed with `COMMAND/CLEANUP DRAIN_DEADLINE`; its cause is unknown. The aggregate
selects the genuine same-source source-only replacement
[41026343627/1](https://github.com/p2pKit/P2pKit/actions/runs/41026343627), not a
reclassification of that failure. Later source requires its own qualification.

The earlier [rc7 record](../releases/0.8.0-rc7.md) retains its failed original
Intel job, successful same-source replacement and verified immutable public bytes.
The earlier [rc6 record](../releases/0.8.0-rc6.md) retains its original Maven
evidence-upload failure and successful separate recovery as rc6 history;
that recovery is not inferred for rc7 or rc8.
The incoming manual Windows/Android report remains a separate, limited result;
publication does not extend its installed-application coverage.
Retain the [Windows qualification limits](../rpc/windows-release-scope.md),
including the Back deadline failure and incomplete automated lifecycle coverage.

Before selecting a version, review the unreleased behavior notes. The integrated
audit's [#229 discovery-admission tightening](https://github.com/p2pKit/P2pKit/issues/229)
and its related [#356 Apple TXT decoder correction](https://github.com/p2pKit/P2pKit/issues/356)
and [#332 Apple invalid-resolution withdrawal](https://github.com/p2pKit/P2pKit/issues/332),
as well as [#145 receive-backlog admission tightening](https://github.com/p2pKit/P2pKit/issues/145)
and [#158 LAN inbound-queue depth alignment](https://github.com/p2pKit/P2pKit/issues/158),
were reserved for **0.8.0+** and were included in the separately qualified rc2
release. Do not backport them into a 0.7 release without a new explicit owner
decision. Documentation and consolidation of audit history into `main` do not
authorize a subsequent release or replace its qualification.

1. Update `VERSION_NAME` to the exact non-snapshot version and update current
   docs/changelog. Keep `LATEST_PUBLISHED_VERSION` at the previous release until
   remote publication is verified.
2. Confirm a clean worktree and exact ancestry from `origin/main`.
3. Pass the modular `ci.yml` components and exact-source aggregation, plus
   `git diff --check`. Retain genuine `build/reports/platform-tests/` evidence
   from the same-source `macos-shared`, native ARM64 `ios-arm64` and native Intel
   `ios-x64` profiles: all 24 portable test tasks plus non-test `check` dependencies
   remain required across the three components. The arm64 gate cannot verify the published `iosX64` slice;
   no Intel execution may be inferred from cross-compilation. See the
   [platform coverage guide](../testing/local.md#platform-execution-evidence).
4. Require the component results for OSV, ABI, strict Dokka, SBOM, publication shape,
   isolated consumers, Swift warnings-as-errors, and XCFramework provenance.
5. Confirm `scripts/check-release-tag.sh v<VERSION_NAME>` and
   `scripts/check-maven-central-version.sh absent` pass.
6. Require the exact same-source/version four-platform application set and
   original encrypted evidence, then obtain explicit owner authorization for
   the exact tag and commit. Follow the [exact-source foundation procedure](release-foundation.md).
7. Push the immutable tag and allow the protected `maven-central` environment
   to perform signing, bundle validation, publication-build SBOM validation,
   provenance, and publication. The new secret-free `freeze-applications` stage
   must pass first; protected approval must include its exact attempt/set-hash
   challenge. Readiness is checked again immediately before irreversible upload.
8. Verify remote bytes, signatures, checksums, metadata, and isolated consumers.
9. After successful Maven verification, deliver the exact frozen APK/MSI/ARM64-DMG/DEB
   through the separately protected sample evidence-approval stage and verify
   every complete public download against its recorded hash. Do not rebuild or
   reselect applications after Maven.
10. Record the verified publication, update `LATEST_PUBLISHED_VERSION` and current
   documentation through a normal reviewed change. Open a next snapshot line only
   when separately agreed; publication bookkeeping selects no new version. Record the
   actual GitHub prerelease/release entry; do not create a duplicate sample release
   or rebuild published bytes. All earlier sample prereleases retain their own
   immutable bytes. Do not advance latest-published metadata before verification
   or invent the next snapshot version.

Never move or recreate an existing release tag, weaken a gate, put secrets in
the repository, or publish a snapshot.

## Which build each gate covers

`ci.yml` independently executes tests, ABI, Dokka, SBOM, local publication/consumers
and Apple/XCFramework checks. `verify-release` revalidates those exact-source
results and the frozen application set; it does not repeat all component builds.
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
`-L`). Repository advisory filters are disabled; a local
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
| Main JVM and KMP-metadata JARs; nine native `-metadata.jar` archives; Android AARs | Exactly one `META-INF/LICENSE`, byte-identical to repository `LICENSE`. |
| Every publication's `-sources.jar` and Dokka `-javadoc.jar`, including iOS coordinates | The same single canonical embedded license, in addition to the existing source/index checks. |
| Nine Kotlin/Native main `.klib` and three LAN `-cinterop-p2pkit_nw.klib` archives | Explicit **embedded-license-check exemption**: not produced by `Jar`/`BundleAar`, and not rewritten. The gate requires each archive to exist and be readable, plus the sibling POM's Apache-2.0 metadata; the nine main KLIBs also require identity checks. It prints `EXEMPT`, not an embedded-license pass. |
| Source-built `P2pKitShared.xcframework` | Separate Apple output, not an artifact in this Maven publication set. Its provenance/minimum-OS checks do not certify license embedding. A redistributor must separately include the applicable license/notice material. |

The current source configuration, including RPC published in `0.8.0-rc2`,
requires 75 archives on macOS: 63 license-covered JARs/AARs and 12 explicitly
exempt KLIBs, across 21 publication coordinates. The rc2 release record binds its
actual inspected publication. This configured shape alone is not inspection
evidence for a later source or qualification of unfinished RPC runtime behavior.
The immutable historical four-library set remains 54 archives (45 covered, nine exempt) across 15 coordinates;
no RPC coordinate is inferred for those historical 0.7 releases.
Every checked publication produces success, failure or an explicit KLIB
exception; missing, changed or duplicate license entries in a covered JAR/AAR
fail the gate. Non-macOS omission of the nine current-source iOS publication rows is a host
execution limitation, **not** that license exception or a complete release pass.
Retain a macOS inspection of the complete publication set before release.

This describes packaging/check scope, not legal advice or a waiver of Apache-2.0
redistribution obligations. A vendored KLIB without its POM is not promised to
carry license text. Include the repository license and applicable notices when
redistributing; do not infer compliance from `EXEMPT`. Previously published RC
artifacts/tags remain immutable; their embedded contents require their own byte
inspection and are not inferred from today's build rules.
