# RPC in the maintained sample applications

**Status: integration in progress; not a release-readiness or installed-runtime pass.**

## Application ownership

RPC belongs inside the existing sample applications, not a second installer or
release pipeline:

- Android: `:p2p-sample-android:assembleDebug`, existing `MainActivity` → **RPC**.
  Debug-only RPC dependencies and controls remain excluded from release builds.
- Desktop: `:p2p-sample-desktop-ui:run` and that module's existing native
  distributions. The embedded RPC workspace shares the maintained application
  window; it does not start the legacy preview's separate JFrame/process.

Room's permissive development authorization is not RPC authorization. A Room or
KMP owner, startup, or unfinished cleanup blocks RPC entry. Returning to Room or
closing the application must await the exact RPC owner and protected-profile
cleanup. Stale callbacks must not release a replacement entry. Keep saved trust;
never use navigation as a profile reset or a substitute for successful cleanup.

Legacy RPC preview entry points and their historical evidence remain available
for reference, not the canonical artifact producer or evidence of this integration.
The existing iOS application is unchanged by this Android/Desktop integration.

## Native and storage boundaries

The Mac ARM64 Gradle `run` path may stage the existing source-bound private
TCP/Bonjour adapter. This is a local-development path, not installed-app admission.
Library presence or interface discovery never proves permission, multicast,
per-socket scope, or peer connectivity. Intel and other hosts keep their existing
portable restrictions; a Mac ARM64 result does not qualify them.

**Installed Mac runtime qualification remains open.** A separate opt-in
[development-bundle policy](installed-macos-native-policy.md) admits the actual
packaged launcher, same-bundle classpath authority, exact native bytes and valid
ad-hoc signatures. Private staging keeps its original owner-private rules.
The existing `createDistributable` output feeds an owned-copy finalizer, then
the existing `packageDmg` task. Inner native bytes are signed before their
manifest; the outer application is signed last. No temporary extraction,
permission relaxation, second installer or replacement release pipeline is used.
This is not Developer ID, notarization, or an installed-app/peer pass. Exact
packaged-process loading and Foundation's application identity/freeze checks
remain required.

Windows protected RPC storage is **NATIVE_NOT_IMPLEMENTED / NOT_QUALIFIED**.
Its managed filesystem seam and bounded native-contract adapter have synthetic
regression coverage; there is still no production JNI provider or secure DLL
loader. Host/Client must remain unavailable without a qualified secure backend. See the
[Windows profile contract](windows-profile-integration.md) and
[owner-accepted prerelease testing risk and implementation limitations](windows-release-scope.md). UI rendering or a
Mac-hosted policy test is not Windows filesystem or RPC evidence.

## Dependency transaction

This RPC preparation tree tracks **14 Gradle lockfiles**, including the RPC library and
sample. The foundation's joint writer accounts for 12; it cannot be treated as a
complete writer for this tree without adapting and testing its full inventory.
The maintained writer has regenerated and reviewed this preparation graph,
including the Desktop → RPC runtime's `kotlinx-serialization-json-io` and
`kotlinx-serialization-json-io-jvm` `1.11.0`. Jackson's floor is `2.22.3` and
FreeMarker's is `2.3.35`. All 14 locks were reviewed (seven changed); the complete
11-project check, five-library Dokka and aggregate SBOM graph executed. Fifteen
new artifact entries were independently authenticated; existing pins were retained.
The isolated clone's local SCM URL initially failed SBOM contamination validation.
Correcting that clone's canonical origin and regenerating only the SBOM produced
a validated JSON/XML pair; the original failure remains preserved.

This does not qualify Foundation's future combined source. Use the maintained
writer again for that combined graph; do not transplant the Foundation's 12 locks,
hand-edit generated files, reuse partial candidates or disable verification.

## Qualification ledger

| Lane | Required evidence / current boundary |
| --- | --- |
| Android integration | Focused owner/Back/lifecycle tests, debug build/lint, release exclusion, and real navigation checks; no pass inferred from source review. |
| Desktop integration | Reservation/async-close/dialog tests, maintained-app build and launch, exact final source/artifact binding; no legacy preview pass carried over automatically. |
| Mac native adapter | Current-source private staging/loading and separate development-bundle checks; actual packaged runtime remains a distinct open gate. |
| Dependency transaction | Preparation graph's complete writer, artifact review and SBOM validation passed; final Foundation combined graph must be regenerated and qualified. |
| Windows RPC | Backend engineering and native Windows runtime qualification remain separate open items. |
| Intel / Android ART / physical campaigns | Existing deferred or infrastructure-dependent gates remain deferred/open, never relabelled as passes. |

Record actual commands, source/tree hashes, artifact hashes, results, preserved
failures, cleanup evidence and remaining gates in the final run receipts. This
document deliberately supplies no overlapping-test-count completion percentage.
