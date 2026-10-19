# Real-Windows custody smoke test source

**SCOPED STANDARD-USER NATIVE SMOKE EVIDENCE EXISTS. WINDOWS REMAINS NOT_READY.**

On 2026-10-19, both maintained selections passed under the canonical 30-second
supervisor on the approved native AMD64 Standard-user Windows account. The
supervisor source was `89b12b26ecdec0f23184a4b5bf972bf6cb632838`; all native build
inputs were independently rebound unchanged to that source. The existing smoke
EXE SHA-256 was `ad57f8c430868f706fb8e532c8636096679311fd2f7f93196ed298e32c450da3`.
Its original build used a dirty tree; that history remains recorded. The owner
explicitly authorized archiving synthetic P2pKit data and reusing this account.
The application profile and both smoke fixtures were archived intact separately,
with unchanged file identities, contents and ACLs. Private receipts retain actual
process/descendant retirement and the original source/build bindings.

These results cover the then-maintained custody and orderly cold-session reopen
controls. They do not qualify later source changes, interrupted recovery,
cross-process contention, encrypted profiles, JNI, installed Host/Client or
power-loss durability. Historical build-only and unexecuted statements below
describe their named earlier checkpoints.

The current source additionally tests cross-process contention using two fixed
descendants of the already job-contained smoke. A held-file contender requires
an actual sharing violation and production root refusal; a later contender
requires successful root/profile acquisition after original retirement. The
parent observes the original child handles and checks unchanged root/profile
identity after reacquiring them. No shell, credentialed launch, breakaway, new
job or arbitrary child command is accepted. Five-second child work bounds do
not extend the original outer budget. These added controls passed on the same
approved platform at `59eacd6e2f09cd98aa400a2f15ce3cb34c40fdc1`: 483 assertion lines,
nine retired process witnesses and enclosing driver exit0. The exact EXE SHA-256
is `2ba061488675526ad288823d740ca96b01c4b6fa0bf7950a21b9356ffe8e7a94`;
receipt SHA-256 is `3c17714c290954d5af2944034a09b60610bcd8d80f9651892bd6a6042f374269`.
Its fixture was archived intact separately. This scope does not include JNI,
encrypted recovery, uncertain cleanup or installed Host/Client qualification.
See the [later Windows checkpoint](../../../../../../docs/maintenance/windows-local-network-and-native-20261019.md).

The owner-authorized Windows2022 run
[38243224029](https://github.com/p2pKit/P2pKit/actions/runs/38243224029), at exact source
`1e1800e446afd91298eb1b16a6c5c4ca231d6746`, compiled the actual Win32/JNI DLL and this smoke EXE
with MSVC warnings-as-errors. Its 72 managed-contract tests passed without skips. The retained compiler
receipt binds the source/tree and both output hashes. This is build evidence only: neither DLL nor smoke
was loaded/executed. It does not qualify later changed source, account ownership or runtime behavior.

The optional `verifyRpcWindowsProfileBytes` task inspects compiler-hash-pinned DLL bytes and emits a
create-only `BYTE_MANIFEST_ONLY` record. It never loads the library or grants loader/signature authority.
The hosted account-capability probe only observes three process-token privilege booleans; it does not
create accounts, change privileges, access profiles or authorize smoke execution.

These files are maintained test source. They are not a release producer, a complete
Windows backend, a JNI loader, an installed-MSI test or permission to run against an existing profile.
No source availability/capability setting changes. The actual custody component is ABI13/`0x43`;
full durable profile functionality and `0x7f` remain absent.

## External authorization and environment are mandatory

The fixed adapter is now implemented in the canonical supervisor; see
[native smoke supervision](../../../../../../docs/maintenance/windows-native-smoke-supervision.md).
Its two native operations retain the outer 30-second budget, separately pinned
executable and original-file custody. This source change supersedes statements
below that no adapter exists; it does **not** establish execution approval,
passing native controls, a disposable context or Windows qualification.

Before any future execution, the owner must explicitly authorize this exact source/build in a
**newly disposable Windows standard-user account or disposable VM**, with no concurrent P2pKit app,
profile work or other user data. Do not use the owner's normal Windows account, an elevated account,
SYSTEM, a service identity or a UAC-filtered administrator token. Disposability and lack of concurrent
activity are external prerequisites: the executable cannot prove them.

Execution also requires an **independent, authorized bounded process supervisor through observed exit**.
Before launch, declare a finite monotonic process deadline covering process creation, watchdog startup,
all native operations, watchdog self-retirement, final handle closure, CRT/process exit and bounded output
capture. A console success line or standalone execution cannot qualify this boundary. Timeout, missing
observed exit, supervisor failure or uncertain process/resource cleanup are nonpassing outcomes.

For future qualification, reuse the repository's reviewed owner adapter in `scripts/audit_processes.py`
(real Windows `WindowsScope` job-list/suspended admission), rather than ad-hoc subprocess/PID control or
another release pipeline. The exact supervisor configuration, source binding, process/job ownership and
native Windows behavior require separate preparation, authorization and validation. **That work has not
been completed by this source.** Do not retry or reset a retained fixture after a failed supervised run.

The stock `run-audit-command.py --timeout` is **not** this end-to-end supervisor: its wait budget starts
after process creation, accepts an observed exit before checking that budget, and excludes finalization.
Reusing `WindowsScope` ownership does not by itself close those deadline gaps or authorize this test.

The accepted source selections are `--disposable-custody-smoke` and the separate
`--disposable-custody-restart-smoke` cold-fixture control described below. Each requires exactly one
argument and acknowledges only its test scope; neither is evidence of consent, isolation, account identity
or a disposable environment. The new argument is a proposal for Foundation's exact-source supervisor
review, **not an approved execution path**. Both selections use the same preflight and external admission
requirements. No environment variable, caller-supplied path/SID, timeout override, temporary-root override,
profile repair or migration is accepted.

Read-only preflight checks:

- Actual native AMD64, not an emulated x64 process on ARM64 or a 32-bit process.
- No thread impersonation; unexpected token-query failures refuse execution.
- No elevation, no linked/filtered elevation type, and no Administrators group SID even with deny-only flags.
- No Service group SID regardless of its attributes, including custom ordinary/domain service accounts.
- Actual token user/default owner agree and are not the rejected SYSTEM/service/admin identities.
- The OS-resolved LocalAppData `P2pKit` component is absent. **Any** existing file, directory, reparse object,
  or an inability to establish absence causes refusal before calling the native root API.
- Uncertain preflight handle closure is an explicit non-success; original handles are never retried.

The preflight copies token headers and validates each embedded user, owner and group SID's complete
extent before any SID API reads it. Group SIDs must lie beyond the entire validated group table and
inside the returned 16 KiB query; user/owner queries retain their separate 4 KiB limit. Malformed or
foreign pointers refuse before profile entry. Portable decoder controls and smoke compilation do not
establish real token-context rejection, protected storage or supervised execution.

The absence observation is **not an atomic reservation**. The production `openRoot()` can open an existing
safe tree if another process creates it after this check. Therefore the independently disposable,
exclusive account/VM prerequisite is primary; this preflight does not make a shared account safe.
Production native admission still separately requires fixed local NTFS, private ACLs, pinned ancestors
and supported `FileCaseSensitiveInfo` on every directory. No failed policy is repaired or bypassed.

The initial preflight runs once. A later reopen in the same run is limited to the exact root this run
already admitted; its original native identity is compared in memory. A separate invocation refuses the
retained `P2pKit` tree. For another run, the owner must supply a fresh disposable account/VM or independently
restore its throwaway snapshot; this harness never removes or resets a prior run.

The original `--disposable-custody-smoke` selection additionally closes and reopens this run's still-empty
fixed tree before creating any lock/identity records, requiring a fresh native owner and unchanged original
root identity. Both bootstrap attempts run the actual self → P2pKit → LocalAppData acknowledgment path;
later child/new-lock calls include their
private original-directory acknowledgment. This is **not** crash/power-loss/flush-fault proof. The broader
initial write-capable fixed-directory access may produce a real Windows refusal; no sharing/ACL or
privilege fallback is allowed. Current ABI13 smoke remains **NOT_EXECUTED**.

## Build-only recipe

### Explicit hosted build/JVM selection

The existing `Desktop cross-host` workflow accepts `scope=rpc-windows` and
`rpc_windows_mode=build-only` on its guarded Windows validation branch. This is an explicitly partial
engineering selection, **not Windows native runtime or release qualification**. It retains the actual
MSVC DLL/smoke/probe compilation, strict RPC sample/Desktop/library JVM controls and compiler-hash-pinned
DLL byte inspection. It also compiles/runs the 16 memory-only C policy units described below; the displayed
scope is **BUILD/JVM/POLICY UNITS**, not a promise that no test executable runs. It does not execute either
the token-capability observation or the fresh-account
feasibility probe; account feasibility and native storage are **NOT_PERFORMED**, not passing or waived.
No native DLL/smoke execution, profile loading, privilege grant, signing or publication is enabled.

`rpc_windows_mode` defaults to `full`, preserving both existing account probes and their fatal failure
behavior. Unknown selections are rejected before native compilation. The build-only selector cannot
substitute for a full account-feasibility result or repair the observed `CreateProcessAsUserW` error1314.
Do not repeat that known-prerequisite failure without a changed, reviewed execution environment.

The job name, step summary and source/attempt-specific artifact name identify the selected scope.
`native-build.json` continues to bind exact source/tree and compiler output hashes, with
`WINDOWS_NATIVE_BUILD_ONLY_NOT_RUNTIME_OR_RELEASE` and `nativeExecution=NOT_PERFORMED`. A green build-only
job means only that its selected engineering checks passed. It cannot satisfy the outstanding Windows
native runtime, installed-MSI, durability/recovery, account-supervisor or release gates. Future native
execution still requires the independent authorization and supervision prerequisites above.

### Memory-only policy units on real Windows

`check-hosted-policy-tests.ps1` compiles exactly these portable tests with actual x64 MSVC and executes
them in both hosted modes: `policy`, `stage`, `lock`, `delete`, `child`, `role`, `candidate`, `rename`,
`sync`, `replace`, `write`, `record_delete`, `namespace`, `publication_probe`, `creation_result`, `token_sid`.
Each executable links only `profile_policy.c` and its fixed `tests/profile_<name>_test.c`; Win32/JNI
implementations, profile DLLs, custody smoke, account operations and storage are excluded. `/W4 /WX`
and `/UNDEBUG` remain mandatory. Ambient compiler/linker flags and `ERRORLEVEL` shadowing are cleared.

`policy-units/policy-unit-results.json` uses **WINDOWS_NATIVE_POLICY_UNIT_NOT_STORAGE_OR_RELEASE** and
records exact source/tree/run/attempt, consumed input SHA-256 hashes, separate Git blob IDs/EOL observations,
all 16 executable hashes and each compilation/execution result. Consumed CRLF bytes are not silently
represented as identical to LF Git blobs. Each command retains at most 64 KiB per output stream with
4 KiB read buffers; compile/test waits are 60/10 seconds, respectively, inside a ten-minute hosted step.
Timeout, output overflow, nonzero exit, missing observed exit, changed inputs/EXE or uncertain finalization
fails. Ordinary process-tree termination after failure does not establish arbitrary descendant cleanup
or the atomic job-admission/finalization contract required for the protected profile smoke supervisor.

The companion `scripts/tests/check-rpc-policy-command-test.ps1` extracts only the ordinary process/Git
functions via PowerShell's AST. It tests synthetic dual-pipe output, nonzero exit, both overflow paths,
deadline termination, missing executable and checked Git failures without executing the guarded hosted
script. Neither this test nor a native policy-unit pass qualifies NTFS, tokens, ACLs, JNI, profile loading,
durable recovery, installed-MSI behavior or release readiness. The earlier native-build receipt still
describes only its DLL/smoke/probe outputs; it is not relabeled as policy execution or storage evidence.

From a trusted, existing **x64 MSVC Native Tools** prompt with a real Windows SDK, after separate source
review and approval:

```bat
build-windows-test.cmd C:\exact-source\samples\p2p-sample-rpc\native\windows-profile C:\new-owned-smoke-output
```

This creates only a new output directory and compiles the **actual** `profile_policy.c` and
`profile_win32.c`, plus `profile_win32_smoke_test.c`, into a test EXE. It uses C11, warnings-as-errors,
static CRT, stack/SDL/CFG and ASLR/NX flags consistent with the custody producer, and the same explicit
Windows system imports. It clears ambient compiler/linker response flags. It neither downloads tools
nor executes, installs, signs, loads or publishes anything. No JDK/JNI or mock backend is linked.

Build inputs, toolchain/SDK, source revision/tree and output hashes must be independently collected and
reviewed. A supplied source directory or matching filename is not source provenance. This build recipe
is not a replacement for the existing application signing/freeze/publication pipeline.

Payload executable and argument for that authorized supervisor in the fresh disposable environment:

```bat
C:\new-owned-smoke-output\p2pkit-windows-profile-smoke.exe --disposable-custody-smoke
```

This is **payload only, not a standalone qualifying invocation**. The required supervised execution
configuration is not supplied here. The build recipe was used by the build-only run above. **The payload command has not been run.**
No supervised-process qualification or native execution result is claimed.

## Intended controls, all currently unrun

1. Real root bootstrap and native identity shape, without disclosing paths or IDs.
2. Before the profile lease: missing-file/zero-read behavior; identity creation, vault acquisition and
   staging rejection, no payload callback, and no created identity directory.
3. Fixed existing/create profile/vault scopes, duplicate lease rejection and no open-to-create fallback.
4. Held profile `exists`/`fileIdentity` use actual owned metadata; held `read(0)` is refused without a
   receiver callback, because the API must not unlock the share-none lease to reopen it.
5. After profile release: expected-ID deletion lacks authority and is refused; `read(profile.lock, 0)`
   succeeds with a `NULL`, zero-length callback buffer. Existing lease reacquisition uses a newer token
   while preserving the original file identity.
6. Fixed identity creation, duplicate uppercase identity alias rejection, and alternate/deeper scope refusal.
7. Before the vault lease: identity staging refuses without a payload callback. With a vault lease:
   profile/identity independent close is busy.
8. Disposable identity stages of 0, 1 and 262,144 synthetic bytes; normal stage metadata and reads refuse;
   parent/vault/profile leases cannot independently retire while the stage is owned.
9. Exact stage disposal and immediate idempotent disposal; over-limit input rejects without copying.
   **Different stage names** are used after retirement, without assuming immediate or durable name absence.
   Stage buffers use the wide template's complete size, including its terminator; copy results and the
   shared `pwp_stage_name` policy are checked before native entry. This was corrected during static source
   review and is not compiled or runtime evidence.
10. A root-only stage does not depend on the vault lease, but still prevents independent profile close.
11. Whole-root close with live profile, identity, vault and both stage types; repeated terminal close;
    closed-session refusal; reopen with a newer root token and unchanged root identity, then clean close.
12. Distinct persistent candidates of 0, 1 and 262,144 synthetic bytes, using the actual native-C preparation
    primitive. Pre-profile/pre-vault/bad-name/over-limit rejection makes no payload callback. A callback
    failure creates no candidate; successful preparation verifies original-handle bytes and EOF internally.
13. Live candidates cannot expose ordinary record metadata, reads or inventory; granting leases cannot
    close. Stage disposal refuses a candidate. Normal close retains its bytes; subsequent create collision
    must preserve them. A root candidate needs no vault lease; a candidate survives terminal root close
    and is readable after root/identity reopen. None of these observations establishes durable publication.
14. Native-C create-only rename to root `profile.header` or identity `<64-lowercase-hex>.aesgcm`, using the
    actual native same-directory call and original handle. Wrong-scope/lock targets and disposable stages
    refuse. Renamed owners retain grants and refuse normal metadata/reads/repeated rename until close.
    After close, independent reads verify the synthetic bytes at the target name. A preexisting header
    causes early read-only refusal; both its old nonempty bytes and the empty competing candidate remain.
    This tests neither a race between absence observation and rename nor the native uncertainty path.

15. Original-handle root/identity directory synchronization rejects missing role grants, succeeds under
    the exact held grants, and refuses a closed session. This observes the syscall result, not a crash test.
16. Identity-record first insertion and replacement use the same prepared candidate and retained leases.
    Readback compares synthetic bytes, changed length and new file identity. Held destinations and
    root-header replacement refuse without changing their original bytes. A separate narrow adversarial
    fixture uses create-new Win32 I/O to place one synthetic byte under a fixed record name with default
    inherited security. Original-handle readback checks bounded valid security-descriptor/DACL structure
    and that the DACL is not protected. Replacement must refuse. A reopen compares file identity, bytes
    and the still-unprotected DACL; this does not prove byte-for-byte ACL equality or an adversarial race.
17. The composed record-write entry owns preparation, create-only or replacement publication, original
    directory synchronization and exact candidate retirement in one call. Synthetic readback checks
    inserted/replaced records; invalid scope, missing leases and header replacement remain refused.
    This successful-call observation does not establish interrupted-write recovery or bootstrap durability.
18. One new, declared synthetic ordinary identity record is created through the composed write API and
    removed only through the expected-ID composed deletion API. Invalid token/tuple, wrong ID, missing
    vault grant and attempts to borrow live locks/candidates refuse without changing the record. Successful
    deletion requires original-file intent/readback/actual close, exact post-close absence and parent sync
    inside the native call. Subsequent `exists`/metadata/read observations check immediate absence; both
    repeated composed and low-level deletion preserve the missing-target error. Original directory/lease
    identities and the immutable header are preserved. This is not a power-loss or adversarial race test.

The harness uses the production native custody API except for the explicit test-only unsafe-DACL
fixture above. That fixture is limited to the disposable account, never overwrites an existing object,
and retains its file; it is not a production fallback or a safe-record creation path. The harness does
not promote delete-on-close stages or borrow a lease for deletion. Expected-ID deletion successfully removes
**only the explicitly created synthetic ordinary record in control18**; other deletion calls test refusal
or missing errors. No canonical directory, immutable header, fixed lock, unsafe fixture or retained
pending record is deleted. Disposable-stage cleanup still acts on its exact synthetic delete-on-close handles.

The canonical directories, fixed empty lock files, synthetic persistent candidates and synthetic renamed
header/record files other than the single control18 deletion target are retained. They are not a usable
application profile or real ciphertext payloads.
Pending names are not application records or commit markers; do not promote or reuse these fixtures.
There is no recursive/pathname
cleanup, ACL reset, repair, migration, recovery or attempt to turn a failed run into a reusable profile.
On failure, the current native root receives its actual terminal drain; every original role/stage/candidate owner
is left to that native drain rather than repeated ad-hoc closes. Uncertain cleanup remains a failure.

## Test-only bounded ownership and output

A dedicated watchdog starts **before** preflight or any native operation. The original
`--disposable-custody-smoke` retains its fixed **120,000 ms** budget. The separate
`--disposable-custody-restart-smoke` uses a fixed **30,000 ms** budget through the same watchdog implementation.
These are complete per-mode test budgets, not additional budgets for each native operation or reopen.
Neither changes the application's separate 30,000 ms terminal-exit policy. Each watchdog
uses monotonic elapsed time, including after wake-up, so delayed timer scheduling cannot accept a late
success. Deadline/error exits terminate this test process with code125 (or fail-fast fallback), without
first blocking on stdio. This is **failed test termination with unproven cleanup**, not cancellation of
a Windows call, a cleanup receipt, a profile recovery policy or a production application deadline.
No child processes are launched. Successful native cleanup precedes watchdog disarm/join and independent
thread/event handle retirement. A final monotonic check follows **both** handle-close attempts, so late
return cannot become success. The inner watchdog cannot bound its own startup/self-retirement or subsequent
CRT/process exit; the mandatory external owner above covers that interval. Uncertain watchdog-handle
closure exits nonzero. The external owner must observe the actual process exit and complete its own
bounded cleanup/capture; a printed control result is not an overall passing receipt.

Exit meanings:

| Exit | Meaning |
|---|---|
| 0 | Only these smoke controls and observed cleanup completed within the test boundary |
| 2 | Required exact scope argument absent/invalid |
| 3 | Platform/account/OS preflight refused or unavailable |
| 4 | Pre-existing `P2pKit` component refused |
| 5 | A smoke assertion or expected native result failed |
| 8 | Native, preflight or watchdog resource cleanup is uncertain |
| 125 / fail-fast | Test deadline/wait failure; cleanup is unproven |

Exit0 alone is not a supervised qualification receipt; the outer owner must also complete its exact-source,
deadline and cleanup requirements. This source does not create or claim that receipt.

Diagnostics contain only fixed control IDs, bounded public result codes and synthetic size-case indices.
No paths, user names, SIDs, file IDs, payload bytes, passwords or OS exception messages are printed.
Transient identity comparisons remain in memory and their fixed arrays are cleared after the run.
There is no promise of physical memory erasure. Source/toolchain/EXE hashes, Windows build/architecture,
command, exit and bounded console transcript must be collected separately; the harness neither signs
receipts nor fabricates an independently authorized source/evidence identity.

## Separate cold composite-write and session-reopen control

`--disposable-custody-restart-smoke` selects an additional source-only control in the same executable;
the original mode and all its controls remain available unchanged. **Execution remains NOT_EXECUTED**;
source availability and historical build receipts do not qualify this new control. Exact build results
belong to source-bound receipts. It requires the same
newly disposable standard-user environment, initial `P2pKit` absence, exact-source authorization and
independent bounded supervisor through observed exit and finalization described above. No wrapper,
supervisor or application gate selects or authorizes this new argument.

The separate cold fixture allows a successful first `profile.header` publication through the composed
write API; the original mode already publishes its immutable header through the low-level candidate
controls before reaching its composed-write checks. This new sequence performs:

1. Native root bootstrap, new profile lease and create-only composed publication of a 41-byte synthetic
   header, followed by immediate file identity/readback and exact pending-name absence.
2. New canonical identity directory and vault lease, then create-only composed publication of one
   37-byte synthetic record. Immediate identity/readback, pending-name absence and an exact identity
   inventory require only `vault.lock` and that record. Original vault/identity ownership retires before
   the exact root inventory requires only `profile.lock`, `profile.header` and `identity`.
3. Original profile and root retirement, then an orderly native-session reopen in the **same process**.
   Root, identity, both lock files, header and record must preserve their complete original six-word
   identities; returned public owner tokens must be newer. Empty lock bytes are read before acquiring
   their share-none leases. Existing locks/directories are opened explicitly, with no create fallback.
4. Exact canonical inventories and both absent pending names on reopen, original identity namespace
   synchronization under both original leases and fresh root/identity readback. The inventory vault lease
   retires before header readback; record readback uses a newly acquired vault lease after another empty
   lock read. Unchanged bytes and normal vault/profile/root retirement are required. A failed step transfers
   all remaining ownership to one native root drain; an already-attempted root close is not retried.

Both file bodies contain fixed `0xa5` test bytes. The header is not application metadata and the record
is not encrypted application ciphertext, despite its canonical filename. There is no key derivation,
proof authentication, identity/trust reset, record replacement/deletion, fixture removal or repair in
this mode. All directories, locks and published or incomplete records are retained. Exact inventories
reject extra names; they never remove them. A separate invocation refuses this retained tree.

The word `restart` in the source selection means orderly session retirement/reopen only. This does not
exercise another process, JVM restart, power loss, interruption, lost-acknowledgment recovery, concurrent
writers or the Windows filesystem's crash/durability guarantees. It supplies no JNI, encrypted-profile,
RPC, loader, installed-MSI or full-provider qualification. The fixed inner 30,000 ms watchdog does not
replace the independent outer creation/startup/exit/finalization deadline or Foundation's runtime authority.

## Explicitly not established by this source or a future v1 smoke pass

- Windows SDK compilation is recorded above for its exact source only; actual native smoke execution
  remains **not performed**.
- A supported Windows release/build floor, FileCaseSensitiveInfo applicability on all target systems,
  x86/ARM64 support or behavior outside native Windows x64 on admitted local fixed NTFS.
- Comprehensive adversarial ACL/DACL validation beyond the one unprotected-DACL fixture, creation-time
  security races, extra/null ACLs,
  impersonation changes during an operation, junction/symlink/ADS/hard-link attacks or parent replacement.
- Cross-process share/lock exclusion or process-contender authorization/lifecycle: no subprocess code exists.
- Complete application-record read/write/delete, adversarial collision races,
  full-disk/partial-write/flush/close fault injection, deletion-pending interoperability or close uncertainty.
  The narrow synthetic header collision and single-record deletion checks above are not those broader campaigns.
- Atomic publication/replacement/deletion, namespace durability, crash/interruption recovery or any promotion
  of disposable staging as a full transaction. The narrow create-only rename smoke does not establish
  no-replace races, post-attempt fault handling, crash durability or complete replacement/deletion transactions.
  Root identity persistence within one run is not a durability claim.
- JNI class/exception/export execution, byte-manifest loader authority, Authenticode, installed DLL custody,
  signatures, watchdog/application-exit integration, full encrypted-vault behavior or the complete provider ABI.
- Actual RPC networking/encryption/discovery/trust/reconnect functionality or installed Desktop/MSI behavior.
- Combined Foundation compatibility, release qualification, Maven publication or READY FOR RELEASE status.

Those campaigns remain separate required engineering/infrastructure work. A refused preflight is not a
platform skip counted as pass, and a successful smoke cannot change `0x43`, full-provider availability,
the maintained source's release gates or the protected application publication pipeline.

## Hosted credentialed-launch feasibility probe (not the native smoke)

`profile_account_probe.c` is a separate test-only executable, compiled by `build-account-probe.cmd`.
It links only Windows system libraries, not the profile implementation, JNI bridge or smoke source.
The guarded `check-hosted-account-admission.ps1` accepts only the owner-authorized, exact-source,
GitHub-hosted Windows2022 validation job and compiler-hash-pinned executable.

Before any account operation it tests invalid arguments and refusal of the runner's elevated token.
The controller rejects thread impersonation, creates one unpredictable ordinary local account with an
in-memory random password, and grants only ordinary Builtin Users membership. Existing account/name
collisions refuse; no existing account is adopted, reset or deleted. Passwords and SIDs are not logged.

The positive probe uses `CreateProcessAsUserW` with **no profile load**, a minimal environment,
a 1024-character-bounded command, `STARTUPINFOEX`/`JOB_LIST`, and a suspended primary thread. Original
process-handle job membership and standard-user/token identity are checked before resume. The child
only checks its own token and exits with a fixed code; it performs no P2pKit or filesystem operation.
The controller observes actual exit, empty-job state, independent one-shot handle cleanup and account
disabling. The new disabled account is retained until the disposable runner is destroyed.

A 60-second internal watchdog and two-minute hosted step bound this feasibility experiment. Expiry,
launch refusal or uncertain cleanup is nonpassing. There is no post-create assignment, PID-based
cleanup, elevated payload fallback, privilege-policy changes, ACL repair or reuse of a failed fixture.
`CreateProcessAsUserW` may temporarily enable privileges already held by its caller; this test never
grants a missing right. A missing privilege remains a failed test, not permission to change local policy.
Only fixed control codes, the API selector and booleans are retained in `account-admission.json`.

The earlier [run38247759479](https://github.com/p2pKit/P2pKit/actions/runs/38247759479), at source
`f6b74c27f765612928b098fbf4a8f5e8560272ed`, compiled the probe but failed its positive admission
control: `CreateProcessWithTokenW` returned error87 before process creation. Cleanup was observed; no
credentialed child or native storage code executed. That API accepts extended startup in its published contract, so
this result alone does not prove all extended startup is unsupported or that Actions cannot run the tests.
The current AsUserW path keeps atomic job admission and standard-user checks; it is a separate real-OS
experiment, not a fallback that turns the earlier failure into a pass.

This proves **at most** the exercised credentialed launch/exit path. It does not establish profile loading,
handle-inheritance isolation, stdio capture, adversarial termination/fault controls, the tighter independent
native-smoke supervision boundary, durable storage, MSI behavior or release readiness. The existing
native smoke remains unexecuted until those separate requirements are implemented and verified.

The subsequent [run38248735038](https://github.com/p2pKit/P2pKit/actions/runs/38248735038), at source
`0da85d921068caceba7ad8961d66349503259e42`, compiled the AsUserW probe but returned error1314
(`ERROR_PRIVILEGE_NOT_HELD`) at process creation. Its newly created ordinary account was disabled and
handle cleanup was observed; no credentialed child or P2pKit storage code executed. All 153 managed tests
passed independently. This is a confirmed caller prerequisite for this launcher on that runner, not
native runtime qualification or proof that every possible Actions configuration is incapable.
No missing right was granted and no elevated native-smoke fallback was attempted. A suitable authorized
standard-user runner or separately reviewed runner setup is still needed for native execution.

The later [run38256185596](https://github.com/p2pKit/P2pKit/actions/runs/38256185596), at exact source
`e614e17afd32c90258a7be0555ff19eb09994842`, supplied ABI11 Windows SDK/PE/compiler-hash checks and
185 passing managed tests in22 suites. Overall qualification still failed at the same launcher
error1314; no storage smoke executed. Those results belong to ABI11, not ABI12 deletion or ABI13
namespace/strict-absence source, which require fresh Windows compilation and authorized native execution.

## Explicit pre-existing standard-user admission lane

`profile_account_probe.c` also accepts exactly `--existing-disposable-standard-user-probe`.
This is an **independent, explicitly selected setup control**, not an automatic fallback after error1314.
The prior credentialed lane and its failed observations remain unchanged. The new mode does not create,
delete, enable, disable or log on an account; load a profile; request/enable privileges; invoke native
profile code; or grant execution authority. It must already be running inside the separately authorized
**disposable standard-user session**. A flag or a normal-looking account name cannot establish that prerequisite.

The controller queries its own effective process token and rejects thread impersonation, elevated or
UAC-filtered administrators, Administrators membership (including deny-only), SYSTEM/service identities
and Service group membership. The default token owner must equal the actual user. Admission happens
before child creation. An elevated hosted runner is therefore a **negative control**, not a suitable
positive environment. The already existing `--standard-account-probe-child` remains a token-only child.

The admitted normal session uses `CreateProcessW`, not a credentialed API. Atomic `JOB_LIST` assignment,
no handle inheritance, suspended creation, original-process job membership, exact token-user comparison
and verification before resume remain mandatory. The child queries its own token and exits42; it does
not touch P2pKit storage. The controller observes exit/empty-job state and exact one-shot cleanup with the
same 60-second watchdog. Neither the new mode nor the credentialed mode qualifies the separately required
end-to-end native profile supervisor, protected runtime, installed MSI or release.

The new fixed-shape result explicitly uses:

```text
scope = EXISTING_STANDARD_USER_ADMISSION_NOT_SMOKE_OR_RELEASE
launchApi = CreateProcessW
accountCreated = false
nativeStorageExecuted = false
```

A successful positive result additionally requires process exit0, native result0, stage9, systemCode0,
`created=true`, `resumed=true`, and `cleanupObserved=true`. A separately successful `TokenElevation`
query observing actual elevation produces exit/result3, stage10, systemCode0, with no created/resumed
child or account change. Only that distinct record qualifies the hosted elevated negative control.
Other standard-token rejection is exit/result3 at stage1 and does **not** qualify that control.
Any cleanup uncertainty is exit/result8, not a successful refusal. Other API/precondition errors are failures. Output and independently observed
exit must both be collected; a matching output line alone does not establish success.

Compilation uses the existing `build-account-probe.cmd` and is retained in the existing native-build
receipt; no separate installer or release producer is added. The offline command below tests narrow
source tripwires and mutations only; it is **not C compilation or Windows runtime evidence**:

```bash
python3 -I -B samples/p2p-sample-rpc/native/windows-profile/tests/windows/check-standard-user-source.py -v
```

`check-hosted-standard-user-refusal.ps1` is a separately guarded **negative** hosted control. It verifies
the clean source/tree/run/attempt and successful compiler receipt, checks exact probe bytes, and invokes
only the existing-standard-user flag. It reuses the existing ordinary bounded child helper with a ten-second
budget and at most64 KiB per output stream; it is not the protected-profile process supervisor. Pass requires
the specific stage10 elevated observation, exit3, no child/account/resume/storage action, observed process
exit, completed finalization, and unchanged source/probe bytes. Failed or unavailable token queries,
non-Windows contexts, generic preflight refusal, timeout, uncertain cleanup and malformed observations fail.
`standard-user-refusal/elevated-refusal.json` preserves its distinct non-runtime scope. Its companion
`check-standard-user-refusal-test.ps1 -OutputDirectory <new-absolute-directory>` executes synthetic parser
mutations and an actual invalid-scope child invocation without running any native executable.

**Positive Windows execution has not been performed.** A concrete safe environment is a disposable
native-x64 Windows VM with an ordinary local account logged on normally, on local fixed NTFS, without
any pre-existing `P2pKit` data or concurrent application. Provisioning must retain security policy and
ordinary Users-only membership; never make the user an administrator or grant missing launcher rights.
A standalone standard-user login avoids error1314 rather than trying to confer `SeAssignPrimaryToken`.
Supplying such an environment does not waive independent source/build admission or bounded supervision.

A hosted alternative would require a **separately reviewed setup/supervision design**, not substitution
inside the failed credentialed probe. Task Scheduler may automatically add batch-logon rights, so it
must not be used as a policy-neutral shortcut without proving pre-existing authorization. The stock
GitHub Windows administrative runner is not itself this disposable standard-user runtime environment.
Do not infer native test readiness from its successful compiler or elevated-rejection controls.

## Separate hosted managed lifecycle controls

The dedicated `rpc-windows` job also runs identity-admission, terminal-close, terminal-JVM-process and
Desktop panel-close-owner tests. These use memory models and synthetic JVM children, not a native
profile or installed application. The child probes exercise deadline termination and normal timer
retirement on the executing JVM; their ordinary process-start/wait boundaries are not the independently
qualified end-to-end native smoke supervisor. No native admission failure is skipped, made nonfatal or
converted to a passing platform result by these independent controls.

## Explicit GitHub-hosted logon-environment experiment

`desktop-cross-host.yml` has a separate manually selected `scope=rpc-windows-environment`, guarded to
`work/rpc-windows-validation-20261012`, on Windows2022 and `windows-latest` (admitted only as `win25-vs2026`).
It does not replace `full`, change the original error1314 result or execute protected storage.
No Gradle/dependency download is needed; it uses the installed native compiler.

`profile_logon_environment_probe.c` compiles in the maintained token-only probe and creates one random
Users-only disposable account. `CreateProcessWithLogonW` does not require the missing
`SeAssignPrimaryTokenPrivilege`; interactive-logon permission must already exist. There are no grants,
profile loads, desktop/profile ACL changes, credential logs, scheduled tasks or elevated payload fallbacks.
The only child command is the compiled-in existing standard-user admission probe. Its own child still
uses same-token `CreateProcessW`, atomic `JOB_LIST`, suspended token verification and observed cleanup.
The created account is disabled after ordinary exit and retained until the disposable hosted VM retires.

**This is environmental feasibility, not the protected supervisor.** Unlike the inner probe, the logon
bootstrap uses suspended **post-creation** job assignment. A controller death between creation and assignment
can leave a suspended bootstrap. No profile/JNI/DLL/storage payload is permitted through this recipe.
A successful receipt proves only the scoped standard-token/same-token observations, not initial DLL-load
authority, profile initialization, adversarial lifetime cleanup, native storage, installed-app operation,
or release readiness. Timeout/uncertain cleanup is a failure, not repaired by eventual VM disposal.
Atomic admission and all provider gates remain unchanged; the shared probe also receives the
child-reference cleanup-order repair below.

Each artifact retains exact source/tree/run/attempt/image, consumed input hashes, compiler and bounded
execution logs, executable hash, strict elevated-refusal controls, and the explicit non-qualification flags.
Only named evidence files are uploaded; account profiles and unexpected dumps/temp files are excluded.
Offline tripwires: `python3 -I -S -B scripts/tests/check-rpc-logon-environment-test.py`.

References:
[GitHub runner privileges](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
[AsUser error1314](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessasuserw),
[WithLogon contract](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createprocesswithlogonw).

The first logon experiment at `77fcb279` created, verified and resumed a genuine ordinary-user process on
Windows2022, but correctly failed: the inner probe returned cleanup exit8 and the outer observed uncertain
cleanup. It is not a passing standard-user session. The initial latest-image guard also refused because
GitHub now maps it to `windows-2025-vs2026`; that reviewed image identifier is explicit, not a wildcard.
Diagnostic interposition observes the original job-query/close API results without changing them. A failed
inner run returns a fixed failure-only numeric category; it never becomes success. No profile or JNI test
has been enabled by these diagnostics.

The second experiment (`ab429d86`, run38353066080) reproduced cleanup failure on both real Windows2022
and Windows2025/VS2026: both original job queries succeeded with `ActiveProcesses=1`; no handle-close
errors occurred. The inner failure-only code `0x48000001` preserves result8 and that count.
The [Windows accounting contract](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)
says the active count decrements only after exit **and release of all process references**. Both probes
queried emptiness while still holding their exited child's process/thread handles. The repair observes
exact exit first, retires those original references exactly once, and then checks the still-owned job.
No assertion, zero-member requirement, timeout, privilege, atomic inner admission or cleanup failure is
relaxed. No sleep/retry or handle reacquisition was added. Previous failed runs remain failed evidence.

The reference-order correction alone (`d0f34a65`, run38353592138) was **not sufficient**: both real
images still reported active accounting after our references closed. It remains a failed run, not a
fixed-root-cause claim. Windows' contract covers **all** references, not just ours; kernel/external
observers can retire later. The probe now observes the same original job until exact zero within its
**unchanged 60-second total monotonic budget**. A failed query is immediately terminal. No timeout is
extended/reset, no failed operation is retried, and nonzero/uncertain membership never passes. The
receipt retains first/final counts and observation count. This bounded retirement state is distinct
from the still-unqualified bootstrap pre-assignment interval and protected-profile supervisor.

The next failure-only inner exit encoding retains result (bits24–27), original stage (bits20–23), and
bounded underlying code (bits0–15;65535 also means overflow), marked with bit30. This does not change
normal exit0 or the original probe JSON. It prevents a cleanup failure from hiding an earlier operation
failure; the historical `ab429d86`/`d0f34a65` encoding above remains specific to those old revisions.

### Separate OS-profile and debugger-transfer experiments

The same explicitly scoped environment job also compiles and runs two independent no-storage probes.
They do not replace `audit_processes.py`, authorize a protected payload, or enable the Windows provider.
Each receipt pins its own source/tree/run/image and exact input/binary bytes; uploads are named allowlists,
never profile directories. Failed observations remain failed; there is no alternate launcher fallback.

- `profile_initialization_environment_probe.c` requests the documented `LOGON_WITH_PROFILE` for a fresh
  Users-only account. Before resuming the token-verified child it observes that account's exact hive
  transition from absent to loaded. The fixed child checks `GetUserProfileDirectoryW`, Profile and
  LocalAppData known folders without `KF_FLAG_CREATE`, existing directory/no-final-reparse properties,
  and actual-handle fixed NTFS. No synthetic profile/environment path, ACL repair or privilege grant is
  allowed. After exact process/job retirement it observes exact SID-name absence under the original 60-second
  deadline, without reading registry values; this is not full OS-profile teardown. This proves environment suitability only, not protected
  ancestor/ACL custody. The bootstrap still has its explicitly unqualified pre-job admission interval.
- `profile_debug_environment_probe.c` investigates debugger-owned creation with
  `DEBUG_ONLY_THIS_PROCESS | CREATE_SUSPENDED`, followed by verified job membership and debugger detach
  before resume. A same-token broker is atomically owned by an outer controller's kill-on-close job.
  Positive and three actual broker-death controls observe an exact duplicated child handle: before
  assignment, after assignment and after detach. Default debugger kill-on-exit is never disabled; no
  debug privilege is granted. API support, automatic retirement and failure paths require actual
  Windows execution. Even success is only focused transfer evidence, not the shared full-lifetime
  protected supervisor or installed-app qualification. The child is the existing token-only probe.

Local source tripwires (not runtime evidence):

```bash
python3 -I -S -B scripts/tests/check-rpc-profile-initialization-test.py
python3 -I -S -B scripts/tests/check-rpc-debug-environment-test.py
```

Additional API references:
[known-folder resolution](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath),
[debugger termination contract](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-debugsetprocesskillonexit),
[debugger detach](https://learn.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-debugactiveprocessstop).

The first new hosted experiment (source `867e4c5a`, run38356830139) compiled both probes on both images.
Windows2025/VS2026 passed the OS-profile recipe; Windows2022 passed its child but failed hive retirement.
Both images rejected debugger creation at `CreateProcessWithLogonW` with error87. These failures are
retained, not converted into accepted protected supervision. Source `74427df9`, run38357413193 then
observed exact `RegOpenKeyExW` status1018 (`ERROR_KEY_DELETED`) during automatic hive unload on both
images, while child exit and process/job retirement succeeded. Marked-for-deletion is not absence.

`rpc_windows_environment_case` selects an independent diagnostic experiment (`all` remains the default).
A selected-case success never means the other failed cases or protected tests passed. This avoids
replaying known-unsupported debugger creation during profile-specific diagnosis.

`profile_job_inheritance_environment_probe.c` separately tests whether a suspended WithLogon child
actually inherits the atomically job-bound broker's job. It never assigns that child after creation and
never uses debugger flags. The only job handle remains in the controller; the broker never receives it.
The controller verifies exact child membership before allowing the fixed token-only child to run.
A second case closes the original last job handle after observing exactly two known members, then
observes both original process handles exit. It deliberately does not claim a post-close empty-job query.
Missing membership or uncertain retirement fails. This tests a candidate creation mechanism, not the
shared protected supervisor, standard-child handle-isolation contract, installed app or JNI provider.

The inheritance fixture creates its fresh account **disabled**. Only after the controller validates
and retains the successful account-creation note does it enable that exact account and acknowledge
custody. A single broker waiter consumes this first auto-reset gate signal before group setup, logon
or child creation. The second signal is separate: it can occur only after the controller receives the
child note, pulls its own handle from the original broker, and completes the child checks. The
last-owner-close control never sends that second signal. No passwords are sent through the notes.

These containment rules passed the narrow token-only inheritance experiment on both Windows images
at `e843b2cd`, run38380973132; this is **not profile, JNI, or protected-supervisor qualification**.
In its existing receipt, `accountCreated` means the controller accepted a successful creation note;
`false` does not prove no account was created. A broker dying before that note may leave an untracked
**disabled** fixture account until the approved disposable VM is destroyed. `cleanupObserved` reports
the fixture's owned cleanup checks, including disabling an acknowledged account, not a complete
account inventory or cleanup of that untracked account. No unknown accounts are enumerated, adopted
or deleted. Controller death, in-flight creation, protected-profile/JNI lifetime and full supervision
remain unqualified. Eventual VM disposal does not turn a failed or uncertain run into a passing run.

The historical namespace-observer experiment (retained separately) avoided repeated opens of the SID hive. It owns a real native
`\Registry\User` parent handle, arms one `REG_NOTIFY_CHANGE_NAME` notification, and performs a bounded
parent-only enumeration. A changed scan cannot prove absence; only a complete scan with no intervening
notification can do so. The original end-to-end watchdog is retained. Parent-close must complete its
pending notification before the event closes; all API errors (including1018) remain fatal.
Eighteen inert controls exercise mutation invalidation and error/retirement paths; the exact helper also
compiles inside the Windows environment executable, requiring separate hosted execution evidence.
`hiveUnloadedAfterExit` means **the exact synthetic SID name is absent**, not complete OS-profile teardown,
`SID_Classes` cleanup, hostile-registry supervision or protection against administrative `RegRestoreKey`.
No user hive values, other profile contents, paths or account identifiers are retained in evidence.

### Failure-preserving profile notification-cancellation diagnosis

At source `b66dfd71eecaee0fcccf1b216a81bdcba087dfbc`, selected profile run
[38379043635](https://github.com/p2pKit/P2pKit/actions/runs/38379043635) reached its original
60-second deadline on both Windows images. Both retained a state2/status259 diagnostic scan:
the bounded parent enumeration no longer found the initially observed target, while the pending
notification was never observed complete. This does not establish stable absence, explain the
kernel's behavior, or qualify profile cleanup.

Diagnostic source `e843b2cd7381e8f67a454c24ecb6ab1da8e881f0` explicitly defined
`P2PKIT_HIVE_OBSERVER_DIAGNOSTIC_RETIRE_ON_MISS=1` in the test probe only. Its scope is
**DIAGNOSTIC_CANCELLATION_ONLY_NOT_PROFILE_ACCEPTANCE**. After a state2 diagnostic miss it
leaves `absence_observed` false and enters the existing retirement path: close the original parent
once, observe the pending notification's completion, then close its event once. All work stays
inside the original end-to-end deadline. No query error becomes absence, no notification is rearmed,
no replacement handle is acquired, and failed retirement ownership is not retried.

Even if cancellation and both closes succeed, the observer returns failure and the outer profile
probe returns result8 with `hiveUnloadedAfterExit=false` and `namespaceAbsenceObserved=false`.
`namespaceRetired=true` would establish only this observer's resource retirement. The profile
experiment remains nonpassing; this is not a replacement qualification or a protected-profile/JNI
supervisor. A cancellation error, missing signal, or close error remains nonpassing uncertainty.
The compile-time hook does not affect the normal observer when absent/disabled and does not alter
normal first-scan absence handling. Selected run38381171778 executed this diagnostic on both images:
42 inert controls passed, actual original parent/notification/event retirement completed with status0,
and both native results stayed8 with `namespaceAbsenceObserved=false`. This is completed retirement
observation, not proof that cancellation caused the signal or that profile absence was established.


### Exact relative SID lookup observation

The current profile recipe uses `profile_hive_exact_observer.h` rather than the historical namespace
observer. Actual parent-name notification did not complete when the hive disappeared from enumeration;
Win32 does not promise a parent NAME event for every hive unload. The replacement does not retry a failed
API, extend the deadline, or treat a diagnostic snapshot as acceptance.

It opens one real native `\Registry\User` parent and uses `NtOpenKey` with that handle as `RootDirectory`
and only the canonical SID from the fresh account's verified token as its relative name. Same-run
controls require absence before profile creation and presence before resuming the verified child.
After exact child/job retirement and release of owned process/token handles, only successful presence
may be polled. Each temporary child handle closes exactly once before the next cadence. Only
`STATUS_OBJECT_NAME_NOT_FOUND` (`0xc0000034`) with a NULL output means point-in-time absence.
`STATUS_KEY_DELETED`, access errors, path errors, inconsistent handles and close failures stay fatal;
uncertain ownership remains quarantined and cannot be retried or reported retired. The original
independent process watchdog remains active, including during blocking calls and cleanup.

No notification/event, value reads or namespace enumeration is used by the new observer. It reports a
separate source-bound `EXACT_RELATIVE_SID_LOOKUP_POINT_IN_TIME` family; legacy enumeration/notification
statuses cannot be substituted. Parent retirement, before/loaded/after native statuses, observations
and successful-child-close balance are validated. The 31 inert controls and local receipt/parser checks
are not Windows execution. Separately, selected run38391959505/1 passed on both Windows images
at source `2f27d876d5b97439917b9627ec255ea002f54296`: absence before, presence while loaded,
absence after, and all exact-observer closes passed. That result is scoped to the bound source and run. Even a passing exact lookup does not prove `SID_Classes` retirement, profile-file durability,
all OS-service cleanup, hostile-admin registry stability or protected-profile/JNI supervision.

See [native relative-key opening](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-zwopenkey).


### Controller death at the returned-child audited gate

The third inheritance control, `--disposable-inheritance-controller-death-probe`, keeps a surviving
observer outside the controller's **private** job. Its separate outer containment job remains open
while it observes automatic exits; outer-job termination is failure cleanup only. The controller is
atomically admitted through `PROC_THREAD_ATTRIBUTE_JOB_LIST`. The observer acknowledges the exact
fresh-account creation note before enablement, pulls only original broker/child query+synchronize
handles, and terminates only the original controller (exit126) after its returned suspended child
has passed the existing token, membership and known-three-handle audits. The second gate is never
released. All three process exits, zero outer-job membership, account disable/readback and owner
retirement must complete within the original shared 60-second deadline.

After successful readiness publication, neither controller nor broker may return into ordinary
explicit descendant cleanup: doing so could race observer injection and falsely attribute explicit
termination to last-owner death. Unexpected gate returns terminate only the current process; controller
exit127 and broker exit124, watchdog125 or fast-fail status cannot pass. The wrapper uses the existing
70-second outer command bound, preserves the original two transfer controls, and retains a distinct
`controllerDeathControl` record. Source-bound readback requires this record for new-source PASS;
historical two-control receipts retain their narrower scope without replay or promotion.

This is `CONTROLLER_DEATH_POST_RETURN_GATE_NOT_INFLIGHT_OR_PROTECTED_SUPERVISION`, not an
in-flight Secondary Logon creation test, profile-initialization test, storage payload, JNI provider or
full-lifetime application supervisor. It cannot establish that no delayed/unannounced process emerges
from an interrupted service handoff. Compilation/source checks are not actual Windows execution.

```bash
python3 -I -S -B scripts/tests/check-rpc-job-inheritance-environment-test.py
python3 -I -S -B scripts/tests/check-rpc-windows-environment-evidence-test.py
pwsh -NoProfile -NonInteractive -File scripts/tests/rpc-windows-controller-death-parser-test.ps1
```

### Explicit WithLogon extended-startup API probe

`profile_atomic_logon_environment_probe.c` tests exactly one `CreateProcessWithLogonW` call with
`STARTUPINFOEXW`, `EXTENDED_STARTUPINFO_PRESENT` and an explicit `PROC_THREAD_ATTRIBUTE_JOB_LIST`.
The earlier error87 with **WithTokenW** does not establish **WithLogonW** compatibility. Select
`rpc_windows_environment_case=atomic-logon` in the existing scoped environment workflow. This is a
separate fixed token-only experiment, never an automatic fallback from another failed launch API.

The fixture owns a successfully created disabled ordinary account before enabling it. It requests
suspended creation into a new private job to which the controller is not assigned. Exact child job
membership and standard-token/SID verification must pass before resume. Only the fixed token check
runs; no profile, DLL, JNI or storage payload is permitted. The original 60-second watchdog includes
process/reference retirement, empty-job observation and acknowledged account disable/readback.
The wrapper retains the actual failure before checking acceptance. Error87 or error1314 stays a
failed API experiment even when its owned cleanup succeeds; no privilege, assignment-after-create,
launcher or environment fallback is attempted.

The receipt scope is `ATOMIC_LOGON_JOB_LIST_API_PROBE_NOT_PROTECTED_SUPERVISION`. Requested extended
startup flags and returned-child membership do not by themselves qualify in-flight Secondary Logon
interruption, the complete Foundation supervisor or protected-profile/JNI execution. Synthetic local
parser/source tests are not native Windows execution evidence.
