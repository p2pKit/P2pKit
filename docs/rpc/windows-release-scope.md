# Windows RPC prerelease decision and known limitations

**Full installed qualification: not passed. Incoming manual Windows/Android use succeeded.**
Track the disposable-machine setup, exact procedures, historical failures, owners and
acceptance checklist in [Windows qualification issue #462](https://github.com/p2pKit/P2pKit/issues/462),
assigned to the repository owner under **Post-0.8.0-rc1 Windows RPC qualification**.
No test runs against the owner's daily Windows profile are authorized by this document.

## Current integration candidate — 2026-10-19

The owner authorized integrating the incoming Windows/Android work and pursuing
**0.8.0-rc4** through the existing merge/publication pipeline after its required
checks, with operational submissions delegated to the agent. This records the
instruction, not a fabricated personal review, completed CI, tag or publication.
Exact-source approval records, protected-environment challenges, artifact freezing
and all release gates still apply. Published `0.8.0-rc3` bytes remain unchanged.

Productive Windows provider/LAN and Android socket repairs are now implemented
in this candidate. The owner confirmed successful manual use of the functionality
they tested on the installed Windows `643988b2` / Android `a2d8593f` pair. Those
artifacts have distinct identities from published rc3 and the forthcoming rc4
builds. The [handoff](../maintenance/windows-android-rpc-handoff-20261019.md)
records their full source/artifact bindings, Android API29 arm64 runtime controls,
positive installed admission and encrypted-profile controls, and retained failures.

This is **not complete W01–W11 qualification**. The recorded Back-stage deadline
failure remains a failure; there are **zero fully accepted automated UI cycles**,
not the required twenty. Full negative-token/loading/JNI/ACL/lifetime matrices,
typed errors, revocation, interruption, persistence/recovery and recorded
Windows Host/Client integration remain incomplete. Successful manual use must not
be described as completion of those cases or as evidence for older rc3 binaries.

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

## Historical candidate preparation — 2026-10-16

The owner authorized preparing **0.8.0-rc2** after rc1's Central preflight failure.
This changes release metadata and the supported namespace-query preflight, not
Windows implementation, MSI packaging or any limitation listed below. The dated
October13 decision above remains historical; this preparation note does not
manufacture renewed publication approval or claim deferred tests have passed.
The new exact candidate still needs its required checks, artifact freeze and
separate merge/tag/signing/publication approvals. Windows sample RPC Host/Client
remains technically unavailable, with the existing fail-closed paths preserved.

## Historical diagnostic/development candidate — 2026-10-18

The owner authorized preparing and qualifying **0.8.0-rc3**, with
operational submissions delegated to the agent. Final source-bound checks and
protected publication challenges still apply. This is not a claim of completed
Windows protected-provider implementation or installed qualification.

The actual installed diagnostic at `33d524e311c3a67b9447d4617d141e73b3d3ac5d`
failed; its internal failure stage was not observable. The new diagnostic emits
one bounded, closed-vocabulary stage/operation line and preserves the original
failure and nonzero exit. A stage identifies the last entered operation, not a
proven root cause, successful cleanup, or authorization to continue. See the
[original Windows report](../maintenance/windows-supervisor-handoff-20261018/WINDOWS-SUPERVISOR-AND-INSTALLED-REPORT.md).
The six successful supervision controls do not convert that installed failure
into a pass. Standard-user installed admission, productive profile/JNI integration
and W01–W11 remain unqualified; the follow-up must use the new exact release bytes.

## Current implementation and qualification boundaries

The shared JVM RPC library and the Windows sample's native protected-profile provider are
different components. The existing Windows Desktop application's other features remain;
**its RPC section now acquires the installed provider, but Windows Host/Client remains unqualified**:

- The Desktop UI's unlock path checks the original named module/runtime, prepares the actual
  Desktop runtime and acquires the fixed `WindowsProfileFiles` installed provider. Role creation
  requires a successful profile with no retained acquisition cleanup. It cannot authorize native
  loading through an OS-name check or an availability flag. Installed UI execution is still required.
- `WindowsProfileAvailability` already has `IMPLEMENTED=false` and `QUALIFIED=false`.
- The JDK21 adapter's public `WindowsLoader.openInstalledProvider()` now uses the
  original installed controller. Its productive storage and UI integration remain unqualified.
  The original-owner bootstrap/load/JNI controller has passed narrow installed admission. After the
  directory-index and delete-pending link-count repairs, an exact-source installed control reopened
  an encrypted marker and completed protected read/write/replace/delete/sync and acknowledged close.
  Later source-bound controls also exercised fresh encrypted creation, cold reopen, wrong-password
  refusal and cross-process contention. Earlier failures remain failures; the original failed fixture
  was archived intact with explicit owner approval. These controls do not establish fault recovery,
  power-loss durability, complete installed UI behavior or the full qualification matrix.
  See the [latest source/package-bound handoff](../maintenance/windows-android-rpc-handoff-20261019.md)
  and [earlier Windows checkpoint](../maintenance/windows-rpc-completion-20261018.md).
  Optional local adapter
  packaging defaults off; the canonical Windows packaging component explicitly includes it.
- The real JNI custody bridge reports ABI **13 / 0x43**, while the managed full-provider
  admission requires **1 / 0x7f**. Reporting invented capabilities is not an implementation.

These are existing technical boundaries, **not functionality disabled by the owner's new
release decision**. Preserve the staged DLL/manifest/parent-pin resources, explicit
`jdk.unsupported`, MainKt, application identities and the single Foundation pipeline.
Report successful manual use only against its recorded artifacts; do not advertise complete
Windows qualification or replace storage/loading requirements with an insecure fallback.
Published Java17 bytecode targets and the packaged JDK21 family remain unchanged.

The remaining work includes the complete installed root/runtime, first-OS-call, ancestor/ACL/reparse,
constrained-loading and loaded-module/import/JNI negative/lifetime matrices. The original chain is
connected to the public provider; broader persistence/recovery, safe application ownership transfer
and actual UI Host/Client still require qualification. Foundation retains installer/runtime/
bootstrap authority; its October18 handoff delegates the necessary loader/provider/native/UI repairs
to the isolated Windows branch. Composed native writes/deletes, synchronization and managed ownership
already exist and must not be unnecessarily rebuilt. Flipping flags or loading a candidate
DLL to authorize itself cannot fill the gap.

## Accepted testing risk and unchanged canonical gates

The RPC contribution currently changes terminal shutdown for **every Windows application
window**, including non-RPC sample holders and workers. The
[terminal application-exit prerequisite](windows-profile-integration.md#terminal-application-exit-prerequisite)
is therefore affected even without productive protected RPC. Its complete Windows/installed-MSI
lifetime validation remains **NOT_QUALIFIED**: narrow installed controls and manual use do not
satisfy the twenty-cycle gate, and the Back deadline failure is preserved.
The earlier prerequisite is not being falsely recorded as satisfied. Foundation must reconcile
this explicit risk acceptance with its maintained release contract. A build-image module probe
or static MSI extraction is not installed-app lifetime acceptance.

Keep all remaining MSI install/launch/navigation/shutdown cases and their preserved failures
in issue #462, along with protected-profile/JNI/peer-operation cases; none becomes a success
through deferral.
Retain included-runtime/byte checks, all Foundation custody/provenance/freeze requirements,
required GitHub checks and the [release checklist](../releasing/checklist.md). The owner has
not requested a Maven-only release, MSI omission or replacement publication workflow.

Do not claim trusted first-load, protected NTFS, JNI/provider, durability/recovery,
authorization/revocation or installed lifetime qualification until the real tests pass.
Testing-risk acceptance cannot enable a known-unsafe path or supply missing executable code.
Further execution still requires the admitted disposable Windows context and exact artifacts;
rollback or a superseding version cannot guarantee erasure of published Maven bytes or reversal
of downstream effects.

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
