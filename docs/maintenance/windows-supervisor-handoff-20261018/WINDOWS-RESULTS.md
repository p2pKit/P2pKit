# Windows supervisor and first installed admission results

18 October 2026. **NOT_READY. Windows Host/Client remains incomplete.**
The supervisor is implemented and its six harmless Windows controls passed.
The first actual installed admission attempt failed. This is not profile,
provider, durability or release qualification.

## Source and installation

- Branch: `work/rpc470-windows-installed-20261018-004011`.
- Reviewed implementation: `724bafed37e2b6d2c55f65a54a01b420115e612a`.
- Implementation tree: `0da9630366d752d12fd707daa76473c696c59e34`.
- Installed application: `33d524e311c3a67b9447d4617d141e73b3d3ac5d`,
  tree `04ad542a1963f82c2f8a8396d93907c3f13416b7`.
- Existing package run: `39083768201/1`. No reinstall or download was needed.
- MSI SHA-256: `1ca2db89c33cefb908ec8a99ee7d81a40e369aeae3f4a4795e3300b9a8d1f089`.
- All 224 installed files matched before and after execution. Inventory SHA-256:
  `344cc88c3031ecd233d0232d05548bdde49dc68f7770c0a1b67a79ae9fbb661d`.

The implementation consumes Foundation's delivered draft and composes unchanged
`audit_processes.WindowsScope` and `ci_evidence.run_command`. It adds retained
original-handle observers, strict bounded receipts and captures, a watchdog armed
through process exit, and explicit installed/harmless entry points. It preserves
the 30000 ms application budget and actual jpackage relaunch. The shared witness
module only observes original job-admitted process handles; it cannot launch or
signal a process. See the [maintained invocation guide](../../rpc/windows-profile-packaging.md#fixed-windows-supervisor).

No provider flag, ABI/capability, native account/storage policy, launcher identity,
ordinary Java target, packaged runtime pin or release pipeline changed.

## Verification

The 26 Python supervisor/witness methods, seven installed-driver methods and
41 receipt-parser cases passed. Repository layout, OSV lockfile coverage,
Markdown links, release metadata and whitespace checks passed. Existing full
Gradle and Apple ABI failures remain unresolved; they were not relabelled or
repeated for coordination. No new Actions dispatch was requested.

| Actual harmless control | Control result | Observer result | Observer elapsed |
| --- | --- | --- | --- |
| Normal nested descendants | PASS | PASS, wrapper exit0 | 2826.64 ms |
| Nonzero fixture | PASS | FAIL, wrapper exit125; inner exit7 retained | 2754.59 ms |
| Inner output overflow | PASS | FAIL, wrapper exit125; `OUTPUT_LIMIT` retained | 2805.09 ms |
| Blocked worker | PASS | FAIL, wrapper exit125 | 26159.44 ms |
| Blocked outer observation | PASS | FAIL, wrapper exit125 | 29047.29 ms |
| Observer output overflow | PASS | FAIL, wrapper exit125 | 2210.79 ms |

All required Python executable identities and every retained process object
were observed exited before enclosing cleanup. The latest actual wrapper exit
was 29096.29 ms, before its original deadline. Capture/handle retirement passed.
The earlier narrower Normal run and failed first overflow-readback control are
preserved. The overflow repair reads only fixed synthetic E log bytes after
retirement under a retained parent; it does not relax the strict private-file
adapter to accept Python's different command-directory ACL.

## First installed attempt

Fresh observations admitted the actual tool/assistant ordinary local user and
normal interactive console session on native AMD64 Windows 11 25H2, build
26200.9168. No administrator SID/elevation, observed thread impersonation,
startup override or conflicting application/profile process was present.
The initial profile entry was absent. Existing profile/ancestor ACLs were
preserved; these observations are not a replacement for native handle policy.

The fixed installed driver invoked `--rpc-windows-installed-admission` once.
Result: **FAIL**, with:

```text
WINDOWS_INSTALLED_ADMISSION_REFUSED_OR_FAILED_NOT_QUALIFIED
```

The launcher and its real relaunch child both exited1. Canonical E retained
`COMMAND_FAILED`, elapsed0.641 s, no timeout, known cleanup, closed captures,
empty cleanup reasons and no native error. All six witnessed process objects
exited and their handles closed. No application process or profile entry
remained. The failing internal stage and successful DLL/JNI admission are
**not established** by this result. No blind retry was performed.

Private installed-attempt receipt SHA-256:
`fec5d001ec62de6913cf0fd9036cf0a2e0b957bda704bcd17d76574bc11a4851`.
Private control-summary SHA-256:
`d1da5469ec9660082a3e55ee158a22435f712e6b02788d6b78ec810146141d16`.
Raw evidence remains private; this document contains only scoped findings.

## Required continuation

The owner confirmed that **RPC will provide the failure-stage diagnostic**.
Loader/application ownership remains with RPC. The current MainKt catch hides
the throwable; the original controller retains the operation privately without
an exposed cause. Source review found no proven early-condition defect.

Provide a bounded source-owned checkpoint/category readback, including Kotlin
pre-loader phases and the retained original controller/candidate state. It must
perform no new native work, avoid completed-owner guards on failed objects,
preserve original owners and nonzero exit, and omit messages, paths, SIDs and
addresses. Bind the resulting source/build/package/installed bytes before the
next Windows attempt. Coordination: [PR #470](https://github.com/p2pKit/P2pKit/pull/470#issuecomment-6245505641).

W01 negative contexts remain incomplete. W02 has a genuine failed installed
attempt; W03 registration/reuse remains unconfirmed. W04–W09 protected storage,
persistence/recovery, cancellation, LAN RPC and revocation are unexecuted.
W10 still requires installed lifecycle/interruption coverage, including at least
20 normal cycles. W11 binds the current failure but not an unexecuted campaign.
Public provider completion remains engineering work, and the full Windows
qualification requires returning to an admitted Windows device.
