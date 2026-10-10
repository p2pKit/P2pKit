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

**Installed Mac packaging remains open.** The loader currently requires native
files owned by the current user with no group/world permission bits, one hard
link, and nonsymlink root/current-user-owned ancestors that are not group/world
writable. Root-owned `0644` bundle resources fail those private-file rules;
group-writable installation ancestors may also fail. Re-signing a staged dylib
changes its bytes and invalidates the source/classpath-pinned manifest hash.
Adding a packaging task cannot resolve these security-contract differences.
Do not relax the private loader, copy native code to temporary storage, or alter
system permissions as a workaround. A separately reviewed installed-bundle
admission and signature/provenance design is required, followed by installed tests.

Windows protected RPC storage is **NOT_IMPLEMENTED / NOT_QUALIFIED**. Host/Client
must remain unavailable without a secure backend. See the
[Windows profile contract](windows-profile-integration.md). UI rendering or a
Mac-hosted policy test is not Windows filesystem or RPC evidence.

## Dependency transaction

This combined tree tracks **14 Gradle lockfiles**, including the RPC library and
sample. The foundation's joint writer accounts for 12; it cannot be treated as a
complete writer for this tree without adapting and testing its full inventory.
The new maintained Desktop → RPC dependency adds
`kotlinx-serialization-json-io` and `kotlinx-serialization-json-io-jvm` `1.11.0`
to the runtime graph. Strict compilation succeeds with the existing compile
locks; the strict test task rejects these two unlocked runtime coordinates
before executing tests. This is not a compiler failure or permission to bypass
locking. Use the maintained combined
writer, independently review newly resolved artifacts, and verify all 14 locks
and required tasks. Do not hand-edit locks, reuse partial candidates, or disable
verification to make the integrated build succeed. This is agent-owned work,
not a physical-device qualification item.

## Qualification ledger

| Lane | Required evidence / current boundary |
| --- | --- |
| Android integration | Focused owner/Back/lifecycle tests, debug build/lint, release exclusion, and real navigation checks; no pass inferred from source review. |
| Desktop integration | Reservation/async-close/dialog tests, maintained-app build and launch, exact final source/artifact binding; no legacy preview pass carried over automatically. |
| Mac private adapter | Current-source staging/loading and affected native checks; installed bundle remains a distinct open gate. |
| Dependency transaction | Complete 14-lock writer and independent artifact verification before required check/Dokka/SBOM closeout. |
| Windows RPC | Backend engineering and native Windows runtime qualification remain separate open items. |
| Intel / Android ART / physical campaigns | Existing deferred or infrastructure-dependent gates remain deferred/open, never relabelled as passes. |

Record actual commands, source/tree hashes, artifact hashes, results, preserved
failures, cleanup evidence and remaining gates in the final run receipts. This
document deliberately supplies no overlapping-test-count completion percentage.
