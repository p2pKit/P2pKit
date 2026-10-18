# Windows qualification detailed report: supervisor and installed admission

18 October 2026. **NOT_READY. Windows sample Host/Client is not functional or qualified.**

Foundation's delivered supervisor has been completed, independently reviewed,
tested on the actual Standard-user Windows session, and pushed. All six harmless
supervisor controls passed. The first genuine installed admission invocation
then failed with the application's fixed nonqualified error. The original
failure, complete process observations and private evidence are preserved.
The owner confirmed that RPC will provide the missing failure-stage diagnostic.
No further installed retry is authorized by a successful supervisor test alone.

This report supersedes the earlier *current-status* statement that no installed
diagnostic had run. It does not change the historical evidence or earlier failures.

This is the public, sanitized edition of the sealed local report. It records
qualification performed through commit `5a55aebe2ba35522f893d2d341d2ac1bdf1affca`;
source and clean-working-tree statements below describe that checkpoint.
Publishing this Markdown report does not rerun or extend that evidence.
Local paths, account identifiers and private evidence links have been removed;
raw logs, receipts and payload evidence remain private. See the shorter
[results handoff](WINDOWS-RESULTS.md) for a quick reading.

## Source and ownership at the reported checkpoint

| Item | Exact identity |
| --- | --- |
| Branch | `work/rpc470-windows-installed-20261018-004011` |
| Initial clean commit this continuation | `2a0ed93001672404016123c33a53878be12437db` |
| Initial tree | `757e77c3326049be645e37d526a528c66a0b16d5` |
| Foundation additive handoff consumed by fast-forward | `9edece7dd782825c724ee3a52370b69e5e875377` |
| Handoff tree | `fc4ff525f6ee904140318c9633e9434fa4061e09` |
| Reviewed implementation commit | `724bafed37e2b6d2c55f65a54a01b420115e612a` |
| Implementation tree | `0da9630366d752d12fd707daa76473c696c59e34` |
| Reported checkpoint, including sanitized result handoff | `5a55aebe2ba35522f893d2d341d2ac1bdf1affca` |
| Reported checkpoint tree | `a7abf59ce4b3078a8e3cae1cb86984d2ecc2faa2` |
| Local/remote state at that checkpoint | Matching commit, clean working tree, ordinary non-force push |
| Installed application source | `33d524e311c3a67b9447d4617d141e73b3d3ac5d` |
| Installed application tree | `04ad542a1963f82c2f8a8396d93907c3f13416b7` |

Only the qualification branch was pushed. Main, the original RPC branch,
Foundation's checkout, tags, signing, publishing and repository protections were
not modified. Existing AGENTS.md instructions were read and preserved.
Command-scoped safe.directory and the existing qualification-agent author identity
were used; no global wildcard trust or account identity change was made.

Implementation commit changes 11 files: the packaging guide; fixed installed
admission driver; Python supervisor and PowerShell entry; C# external observer;
shared original-process witness module; and five focused test/control files.
The second commit adds only the sanitized `WINDOWS-RESULTS.md` handoff under
`docs/maintenance/windows-supervisor-handoff-20261018/`.

## What was implemented and reviewed

The PowerShell entry compiles the fixed C# observer. It retains Process.Start's
original handle, bounds both output streams, validates exact JSON shapes/types,
binds consumed source hashes, and observes exit and original-handle closure.
One QPC deadline starts before Python creation; the application allowance stays
30000 ms. The Python watchdog remains armed through exit and fires at 29 seconds.
Late exit, lost observation, unfinished capture or uncertain cleanup cannot pass.
Failure retirement is not an extension of acceptance.

The Python supervisor composes the unchanged canonical `audit_processes.WindowsScope`
and `ci_evidence.run_command`. In this report, E denotes the canonical command
runner and F denotes the strict private-file adapter used for evidence custody.
Workers enter jobs atomically before resume;
real launcher/relaunch descendants remain contained. The final supervisor receipt
is created and written through retained original directory owners. Receipt or
ancestor close failure prevents exit 0 even if a provisional PASS was written.

The shared witness module does not launch or signal processes. It duplicates only
already job-admitted original handles, with query/synchronize access and no
inheritance. It records a bounded image path from that same original object,
waits for actual signaled exit, and closes each duplicate once. Test success is
decided before enclosing cleanup can help terminate a broken subject.

The installed driver selects only the existing installed admission path. Harmless
fixture entry points cannot select an application. The driver's final receipt is
also provisional until final writer/parent closure and actual driver exit; it
postchecks the original subject deadline through final output.

Independent review covered observer ownership, source/type binding, deadline and
finalization semantics; the primary Windows agent reviewed Python ownership and the
witnesses. A second review checked the actual six control receipts. Trusted
normal OS, CLR and CPython scheduling remains an explicit assumption; arbitrary
kernel/scheduler stalls are not a hard-real-time guarantee.

No production loader/provider gate, ABI13/0x43 capability, native profile policy,
encrypted storage implementation, Java 17 ordinary target, JDK 21 supplier pin,
MainKt/application identity, MSI resources or release pipeline changed. Native
composed writes, expected-identity deletion, synchronization and ownership remain
intact. Productive provider integration remains unfinished engineering.

## Actual account, startup and filesystem observations

Fresh actual tool and assistant token observations showed the reserved enabled
ordinary local user, primary unelevated native AMD64 tokens, matching user/owner,
no Administrators SID (including deny-only membership), no service/SYSTEM context,
and the Interactive SID. LSA type 2 and WTS observations confirmed normal local
interactive console logon. All enumerated tool/assistant threads had no
impersonation token and no query errors. These are point-in-time observations,
not qualification of every future token or the W01 negative matrix.

Platform: Windows 11 Home Single Language 25H2, build 26200.9168; local fixed NTFS.
OS-resolved LocalAppData and its ancestry were inspected without copying personal
data or changing ACLs. Existing extra campaign-account ancestor permissions were
preserved. Original native ancestor policy still decides productive admission.

Process/user/machine JAVA_TOOL_OPTIONS, _JAVA_OPTIONS, JDK_JAVA_OPTIONS and
JPACKAGE_DEBUG were absent. The exact per-user launcher configuration locations
were absent, and LOCALAPPDATA/APPDATA matched OS Known Folders. PATH was preserved;
the real jpackage relaunch was observed, not avoided by environment changes.

The final pre-invocation checks were recorded at approximately 04:01:37–04:01:40 UTC.
All 224 installed files matched. Read-only inspection of 249 installed objects
found zero reparse points, nonprivileged owners or potential nonprivileged write
ACEs. No application/profile payload was concurrently running. The initial
LocalAppData/P2pKit entry was absent. After the failed invocation it was still
absent, no P2pKit/Java/profile-smoke process remained, and all 224 installed files
still matched. Nothing was deleted or reset to obtain admission.

New evidence directories were created with canonical protected user/SYSTEM
custody, verified and closed. The existing installation, SDKs and tools were
reused. No account, privilege, firewall, UAC or machine-tool policy was changed.

## Tool, package and installed-byte bindings

| Object | Binding |
| --- | --- |
| Python | AMD64 3.12.10, `-I -B -S`; executable SHA256 `4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a` |
| PowerShell | 7.6.5; executable file 7.6.5.500, SHA256 `362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139` |
| Observer compiler/runtime | .NET 10.0.11; Roslyn 5.0.25.56712; file hashes in observer-compiler-runtime-binding.json |
| Existing native tools | MSVC 19.44.35229.0; Windows SDK 10.0.26100.0; no repeat native build this increment |
| Existing package producer | Run 39083768201, attempt 1; exact installed 33d source |
| MSI SHA256 | `1ca2db89c33cefb908ec8a99ee7d81a40e369aeae3f4a4795e3300b9a8d1f089` |
| Installed 224-file inventory SHA256 | `344cc88c3031ecd233d0232d05548bdde49dc68f7770c0a1b67a79ae9fbb661d` |
| Installed profile DLL | 188416 bytes; SHA256 `d0fc25a4ad8867e89432e710389d1d31f7b36dfd4d2446f9195de058ff6ebaf8` |
| Pinned packaged supplier | Temurin 21.0.12.1+1; archive SHA256 `f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e` |
| Runtime lib/modules SHA256 | `79f200d79769f7289a9d99b35bd6f80857f5f848245ea73254c813580c80bad6` |
| Installed driver source SHA256 | `1dbe338c9ed3742e13255102160028a924198bb580459207632074f6dd529cb5` |
| Python supervisor source SHA256 | `059892af82230eafd5b07209ef9c56e51c10f442157c51aea3319f2bd62d927e` |
| C# observer source SHA256 | `45ca1887217f19d620f4367af641bfed26e0af81ec57be1e267471d5306db7b3` |
| Shared witness source SHA256 | `29a2ea7b2d7fb5eb0e0aec13db97ee44b4dd16bc387ad357241c899368cb8328` |

The code checkpoint and installed application deliberately have different source
identities. The supervisor change did not rebuild or alter the installed 33d MSI.
This failed diagnostic did not establish successful runtime/bootstrap/DLL import
provider admission or the three sharing-option behaviors in productive use.

## Command-by-command verification

All repository commands used the isolated checkout. Complete arguments and source
hashes are retained in private receipts. The commands below replace only local
absolute paths with descriptive variables; these variables are not an admission
mechanism or permission to execute against an arbitrary account or directory.
No native control below is a protected-profile smoke or productive JNI test.

| Command / operation | Result |
| --- | --- |
| Fetch qualification branch; verify additive handoff checksums; fast-forward | PASS; original work/history preserved |
| Python `-I -B -S scripts/tests/run-windows-installed-diagnostic-test.py` | Original 13 passed; final expanded 26 methods passed |
| PowerShell `scripts/tests/windows-installed-observer-test.ps1` | Final 41 cases passed: 2 valid, 39 refusals |
| Python `-I -B -S scripts/tests/run-windows-installed-admission-test.py` | Seven methods passed; no installed execution |
| Native witness `--case Normal`, first run | PASS, narrower count-only witness evidence retained |
| Native witness `--case Normal`, second run | PASS with exact Python-image witness requirement |
| Native witness `--case Nonzero` | PASS control; actual COMMAND_FAILED/exit 7 and wrapper exit 125 retained |
| Native witness `--case OutputOverflow`, first run | FAIL during synthetic evidence readback; preserved |
| Native witness `--case OutputOverflow`, corrected reader | PASS; exact 4096 x bytes and OUTPUT_LIMIT retained |
| Native witness `--case BlockedWorker` | PASS control; nonzero failure and known retirement |
| Native witness `--case BlockedOuter` | PASS control; watchdog retirement observed before original 30 s deadline |
| Native witness `--case ObserverOutputOverflow` | PASS control; exact 65536 retained bytes, overflow refusal and task/handle retirement |
| Four local repository gates at implementation checkpoint | PASS: layout, OSV coverage, Markdown links, release metadata |
| Final handoff Markdown check | PASS: 867 links across 149 tracked active Markdown files |
| Staged/final whitespace and source checks | PASS; final remote/local match, working tree clean |
| Fixed installed admission command below | **FAIL exit 1**, preserved real installed attempt |
| Post-attempt process/profile and 224-file readback | No residual application process/profile entry; installed bytes still match |
| Push implementation and sanitized handoff | PASS; only qualification branch, no force |

The maintained native-control command is shown with local paths omitted. Use
only the fixed cases in the result table and the reviewed
[invocation and admission requirements](../../rpc/windows-profile-packaging.md#fixed-windows-supervisor):

```powershell
& $admittedPython -I -B -S scripts/tests/run-windows-installed-observer-native.py --case <fixed-case> --private-parent $ownedNativeEvidenceParent --python $admittedPython
```

Each invocation exclusively created its own retained capsule. The actual installed
command was:

```powershell
& $admittedPython -I -B -S scripts/run-windows-installed-admission.py --expected-source 33d524e311c3a67b9447d4617d141e73b3d3ac5d --private-parent $ownedInstalledEvidenceParent --python $admittedPython
```

## Actual native supervision and installed results

| Current control | Exact Python witnesses | Total witnesses | Observer elapsed |
| --- | --- | --- | --- |
| Normal02 | 4 | 6 | 2826.6409 ms |
| Nonzero01 | 3 | 5 | 2754.5877 ms |
| OutputOverflow02 | 3 | 5 | 2805.0942 ms |
| BlockedWorker01 | 2 | 4 | 26159.4371 ms |
| BlockedOuter01 | 3 | 5 | 29047.2877 ms |
| ObserverOutputOverflow01 | 1 | 3 | 2210.7945 ms |

Every required witness exited before enclosing cleanup; every duplicate closed.
The latest actual PowerShell wrapper exit was 29096.2855 ms. Negative controls
retain wrapper exit 125 and observer FAIL. Their *control* PASS means the expected
failure and retirement occurred; it does not relabel the subject as successful.
Normal02/Nonzero01 remain bound to their exact earlier files: later differences
only add the reviewed synthetic-overflow reader and offline tests. Unaffected
evidence was reused with those differences explicit.

The installed invocation emitted:

```text
WINDOWS_INSTALLED_ADMISSION_REFUSED_OR_FAILED_NOT_QUALIFIED
```

Both real installed launcher objects, including jpackage's relaunch child,
exited 1. E recorded COMMAND_FAILED, elapsed 0.641 s, timedOut=false,
cleanupKnown=true, capturesClosed=true, empty cleanupReasons, nativeError=null
and pendingContext=null. The external observer elapsed 1091.0284 ms; the fixed
wrapper exited 125 and the top driver exited 1. All six retained originals exited
and their handles closed. The driver correctly refused its success predicate.

No successful JNI registration/reuse was reported. The blanket error does not
identify whether failure preceded DLL loading or happened later; candidate load,
mapping/import verification and registration must remain unconfirmed. Protected
storage, persistent identity, pairing, RPC, revocation and UI were not entered
by the fixed diagnostic. There was no blind retry and no profile reset.

## Preserved failures and unchanged earlier evidence

- Initial offline receipt-test failure came from a PowerShell array-expression
  test fixture that accidentally included a valid receipt among negative cases.
  The original failure log remains; corrected grouping yielded 41 passing cases.
- The first native overflow control failed because the strict F adapter correctly
  rejected E's protected three-ACE OWNER_RIGHTS/SYSTEM/Administrators directory.
  Exact 4096 synthetic bytes remained. The repair retained the original two-ACE
  parent and used the existing bounded E-log read contract; E/F/profile policies
  and the failed capsule remain unchanged.
- The real installed refusal remains FAIL. No future diagnostic may erase it or
  count it as successful first load/JNI registration.
- The earlier complete Gradle contribution gate at 2a0 remains FAIL: 2938 tests,
  2937 passing, one ReconnectPolicyTest failure, zero errors/skips. Apple ABI
  checking also failed on Windows with an empty generated result versus the
  maintained 64976-byte baseline. The baseline was not emptied or relaxed.
- Prior 16 memory-only native unit executables, native DLL/smoke builds and byte
  verification remain their original evidence. The built protected smoke/DLL
  were not rerun in this increment. The 490 earlier development JDK 21 adapter
  commands include narrow test-native/JNI controls, not installed qualification.
- Original CI 38547764329/1 and Desktop 38547764042/1 retain their 25f704ee source
  scope. No fresh GREEN claim is made for the new commits. No new Actions
  dispatch or unrelated build was requested here.
- Administrative errors were corrected without source/security changes: missing
  Git author identity used the prior agent identity for one command; a read-only
  PowerShell hash-summary syntax error was retried; an accidentally posted
  placeholder coordination body was replaced on the same comment with the
  intended sanitized report and its remote body verified. These are not tests.

## W01–W11 qualification matrix

| Case | Status | Exact remaining work |
| --- | --- | --- |
| W01 | BLOCKED overall | Actual ordinary-user observations pass; full native account admission/negative token contexts remain incomplete |
| W02 | FAIL | Real installed admission refused; no successful first DLL load/import-provider verification established |
| W03 | BLOCKED | Genuine registration/reuse and productive JNI calls, bounds, Start/Stop/reopen remain unconfirmed |
| W04 | BLOCKED | Protected creation/readback and unsafe-path/ACL controls not executed |
| W05 | BLOCKED | Real cross-process locks, record bounds, replace/delete/sync not executed |
| W06 | BLOCKED | Encrypted restart persistence, wrong-password/tamper and fault recovery not executed |
| W07 | BLOCKED | Productive cancellation/races/retained ownership and uncertain-cleanup cases not executed |
| W08 | BLOCKED | Installed navigation and approved two-device Host/Client RPC/typed errors unavailable |
| W09 | BLOCKED | Persisted peer selection, revocation and safe reconnect not executed |
| W10 | BLOCKED overall | Supervisor controls and failed diagnostic retirement verified; 20 installed lifecycle cycles/interruption/resource matrix still required |
| W11 | BLOCKED overall | Exact source/package/runtime/installed-byte/receipt bindings for this failed attempt exist; unexecuted campaign results cannot be bound as passes |

No power-loss durability claim follows from process termination, flush success
or these supervision results. Native retained smoke fixtures and actual profiles
still require separate approved disposable contexts. The approved second endpoint
was previously described as iPhone 17/iOS 27.0.1 with the latest RPC app; its live
exact source/build still requires binding before LAN qualification. No same-host
substitute, automatic peer selection, fingerprint bypass or request replay occurred.

## RPC handoff and next Windows work

The owner explicitly chose **RPC will provide the diagnostic**. Keep RPC's
loader/Kotlin/Desktop ownership; Foundation's supervisor transfer has been
consumed. This is no longer a missing-Foundation-supervisor blocker.

Independent read-only review found no proven impossible early source condition.
Installed JVM options/version/module metadata and launcher path are compatible
with the checked source, but this does not prove runtime checks passed. MainKt
catches and discards every throwable, while the original installed failure stores
its operation privately without an exposed cause. The failing stage is unknown.

RPC should provide a zero-argument retained-state readback (for example
Probe.installedAdmissionFailureReadback) plus Kotlin-side pre-loader checkpoints.
Use a bounded fixed NOT_QUALIFIED record containing source, outer phase, attempt
state, fixed original checkpoint, bounded export/module slot where applicable,
fixed exception category, and native status only with its API/status domain.
Explicit UNKNOWN must survive incomplete observations. The readback must perform
no new native work, avoid completed-owner guards on failed objects, retain every
original owner and nonzero exit, and omit raw messages/stacks/paths/SIDs/addresses.

After RPC supplies reviewed source, prepare the canonical exact-source artifact,
verify its source/runtime/package/installed bindings, and obtain any necessary
owner installation action for the changed MSI. Then return to this admitted
Windows account, refresh prerequisites and execute the diagnostic under this
supervisor. Resolve the demonstrated cause before productive provider connection.
Complete the real encrypted profile/JNI/application and W01–W11 work afterward.
The public provider cannot be enabled by flags or capability substitution.

No test/application process remains from this increment. The device can be shut
down between handoffs, but Windows will be needed again; this is not completion
of all Windows-specific work.

## Evidence integrity and shared handoff

Raw evidence remains in the sealed local collection. This public report contains
scoped findings and hashes, not the underlying logs, account observations or
payload evidence. The original private report was not modified for publication.
The earlier sealed continuation and setup archives are also preserved.

| Retained object | SHA-256 |
| --- | --- |
| Original full private report | `515b62ecbd314c4e70da894960ddc527baac1148fc5bb7c83ef4a83165f8d526` |
| Sealed evidence manifest, 185 inventoried files | `78267f461c480648d21862839afea04f5230593a639d0451d89c70c2c8cbad39` |
| Current control summary | `d1da5469ec9660082a3e55ee158a22435f712e6b02788d6b78ec810146141d16` |
| Installed-attempt receipt | `fec5d001ec62de6913cf0fd9036cf0a2e0b957bda704bcd17d76574bc11a4851` |
| Installed terminal log | `fc3e27fc06ec11aef7f5f27ad7b8b66b9bcfb8f62945dd66a620319b590906ff` |
| Preflight installed inventory receipt | `b35d8d08703472755fcc0bd5ee6308ef90fc056c6b8c4641b21e6da98c2adef3` |

All 185 inventoried files were rehashed successfully against the sealed manifest
at the end of the reported work. These hashes identify retained evidence; they
do not turn a failure or an unexecuted test into a passing result.

- [Supervisor implementation and installed refusal coordination](https://github.com/p2pKit/P2pKit/pull/470#issuecomment-6245505641).
- [Confirmed RPC diagnostic ownership and checkpoint](https://github.com/p2pKit/P2pKit/pull/470#issuecomment-6245628224).
- [Foundation's original transfer](HANDOFF.md); its unfinished-draft status remains historical.
- [Current concise result handoff](WINDOWS-RESULTS.md).

**Final verdict: NOT_READY. WINDOWS_FUNCTIONAL_AND_QUALIFIED has not been achieved.**
