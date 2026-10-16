# Windows RPC prerelease decision and known limitations

**Execution scheduling: deferred post-release by the owner. Qualification: not passed.**
Track the disposable-machine setup, exact procedures, historical failures, owners and
acceptance checklist in [Windows qualification issue #462](https://github.com/p2pKit/P2pKit/issues/462),
assigned to the repository owner under **Post-0.8.0-rc1 Windows RPC qualification**.
No test runs against the owner's daily Windows profile are authorized by this document.

## Owner decision — 2026-10-13

The owner authorizes pursuing **0.8.0-rc1** through the existing canonical merge/release
pipeline, explicitly accepting the risk of deferring real Windows standard-user,
protected-profile, JNI and installed-application qualification until after release.
Preserve the Windows implementation, provider components, packaging, MSI, successful
protections and fail-closed behavior **as implemented**. Do not remove or exclude Windows
RPC, invent a second producer, or use the earlier reduced-capability release proposal.
Do not add optional qualification infrastructure as a prerequisite to this decision.

This records the owner's instruction, not a personally authored GitHub approval, a
passing test, or authorization to bypass repository checks, protected environments,
exact-source approval challenges, signing controls or artifact freezing. Foundation must
carry the accepted testing risk into its existing candidate/approval records. A requirement
enforced by that pipeline is not satisfied by changing its result to PASS or deleting it.
No version, runtime, installer, availability flag or loading path changes in this record.

## Current candidate preparation — 2026-10-16

The owner authorized preparing **0.8.0-rc2** after rc1's Central preflight failure.
This changes release metadata and the supported namespace-query preflight, not
Windows implementation, MSI packaging or any limitation listed below. The dated
October13 decision above remains historical; this preparation note does not
manufacture renewed publication approval or claim deferred tests have passed.
The new exact candidate still needs its required checks, artifact freeze and
separate merge/tag/signing/publication approvals. Windows sample RPC Host/Client
remains technically unavailable, with the existing fail-closed paths preserved.

## Experimental Windows status — implementation is not merely untested

The shared JVM RPC library and the Windows sample's native protected-profile provider are
different components. The existing Windows Desktop application's other features remain;
**its RPC section is present, but Windows RPC Host/Client is technically unavailable**:

- `DesktopRpcProfile.open` / `openAttempt` select only `PosixProfileFiles` and refuse Windows.
- `WindowsProfileAvailability` already has `IMPLEMENTED=false` and `QUALIFIED=false`.
- The JDK21 adapter's `WindowsLoader.openInstalledProvider()` always refuses because trusted
  bootstrap/loading is unimplemented. Its existing optional packaging defaults off.
- The real JNI custody bridge reports ABI **13 / 0x43**, while the managed full-provider
  admission requires **1 / 0x7f**. Reporting invented capabilities is not an implementation.

These are existing technical boundaries, **not functionality disabled by the owner's new
release decision**. Preserve the staged DLL/manifest/parent-pin resources, explicit
`jdk.unsupported`, MainKt, application identities and the single Foundation pipeline.
Do not advertise working Windows protected RPC, promise native execution, or replace its
storage/loading requirements with an insecure fallback. Published Java17 bytecode targets
and the packaged JDK21 family remain unchanged.

The minimum work to make this feature productive is an independently trusted installed
root/runtime/first-OS-call boundary; original-handle ancestor/ACL/reparse verification;
constrained loading with loaded-module/import/JNI lifetime ownership; a genuinely admitted
full-provider adapter and production factory; and profile/UI ownership transfer into that
provider. Foundation owns installer/runtime/bootstrap authority; RPC owns loader/provider
implementation. Composed native writes/deletes, synchronization and managed ownership
already exist and must not be unnecessarily rebuilt. Flipping flags or loading a candidate
DLL to authorize itself cannot fill the gap.

## Accepted testing risk and unchanged canonical gates

The RPC contribution currently changes terminal shutdown for **every Windows application
window**, including non-RPC sample holders and workers. The
[terminal application-exit prerequisite](windows-profile-integration.md#terminal-application-exit-prerequisite)
is therefore affected even without productive protected RPC. Its actual Windows/installed-MSI
lifetime validation is among the owner's deferred, **NOT_EXECUTED / NOT_QUALIFIED** risks;
the earlier prerequisite is not being falsely recorded as satisfied. Foundation must reconcile
this explicit risk acceptance with its maintained release contract. A build-image module probe
or static MSI extraction is not installed-app lifetime acceptance.

Keep the unperformed ordinary MSI install/launch/navigation/shutdown cases in issue #462,
along with protected-profile/JNI/peer-operation cases; none becomes a success through deferral.
Retain included-runtime/byte checks, all Foundation custody/provenance/freeze requirements,
required GitHub checks and the [release checklist](../releasing/checklist.md). The owner has
not requested a Maven-only release, MSI omission or replacement publication workflow.

Do not claim trusted first-load, protected NTFS, JNI/provider, durability/recovery,
authorization/revocation or installed lifetime qualification until the real tests pass.
Testing-risk acceptance cannot enable a known-unsafe path or supply missing executable code.
The owner will provide a disposable Windows session for follow-up; rollback or a superseding
version cannot guarantee erasure of published Maven bytes or reversal of downstream effects.

## JVM test applicability is not a runtime waiver

The normal `:p2p-sample-rpc:jvmTest` task includes:

| Executing host | Mandatory source directories |
| --- | --- |
| Linux / macOS | `src/commonTest`, `src/jvmTest`, `src/posixJvmTest/kotlin` |
| Windows | `src/commonTest`, `src/jvmTest`, `src/windowsJvmTest/kotlin` |

The 24 real POSIX filesystem methods remain required on Linux/macOS, with their assertions
preserved. Eight portable methods from mixed classes stay in `jvmTest`. Two actual-Windows
production refusal tests assert Windows context, rejection before any path access, password
clearing and absence of invented cleanup ownership. They do not impersonate a positive
protected-profile test. Unsupported test hosts fail registration rather than manufacture a pass.

The maintained source inventory and mutation controls live in
`scripts/tests/rpc-jvm-test-host-inventory.json` and
`scripts/tests/check-rpc-module-policy-test.py`, reached by the normal repository-layout gate.
The scoped Windows Actions command runs the **unfiltered applicable** JVM task, not the older
415-test selection. No ignored tests, assumptions, permissive storage or weaker assertions are
introduced. Actual host runs and their inventories must still be checked; source registration
alone is not execution evidence.
