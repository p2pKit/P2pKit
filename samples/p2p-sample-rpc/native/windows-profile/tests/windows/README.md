# Real-Windows custody smoke test source

**NOT_COMPILED. NOT_EXECUTED. NOT RUNTIME EVIDENCE. NO EXECUTION AUTHORIZATION.**

These files are maintained test source. They are not a release producer, a complete
Windows backend, a JNI loader, an installed-MSI test or permission to run against an existing profile.
No source availability/capability setting changes. The actual custody component is ABI8/`0x43`;
full durable profile functionality and `0x7f` remain absent.

## External authorization and environment are mandatory

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

The only accepted execution argument is `--disposable-custody-smoke`. That flag acknowledges test scope;
it is **not** evidence of consent, isolation, account identity or a disposable environment. No environment
variable, caller-supplied path/SID, temporary-root override, profile repair or migration is accepted.

Read-only preflight checks:

- Actual native AMD64, not an emulated x64 process on ARM64 or a 32-bit process.
- No thread impersonation; unexpected token-query failures refuse execution.
- No elevation, no linked/filtered elevation type, and no Administrators group SID even with deny-only flags.
- No Service group SID regardless of its attributes, including custom ordinary/domain service accounts.
- Actual token user/default owner agree and are not the rejected SYSTEM/service/admin identities.
- The OS-resolved LocalAppData `P2pKit` component is absent. **Any** existing file, directory, reparse object,
  or an inability to establish absence causes refusal before calling the native root API.
- Uncertain preflight handle closure is an explicit non-success; original handles are never retried.

The absence observation is **not an atomic reservation**. The production `openRoot()` can open an existing
safe tree if another process creates it after this check. Therefore the independently disposable,
exclusive account/VM prerequisite is primary; this preflight does not make a shared account safe.
Production native admission still separately requires fixed local NTFS, private ACLs, pinned ancestors
and supported `FileCaseSensitiveInfo` on every directory. No failed policy is repaired or bypassed.

The initial preflight runs once. A later reopen in the same run is limited to the exact root this run
already admitted; its original native identity is compared in memory. A separate invocation refuses the
retained `P2pKit` tree. For another run, the owner must supply a fresh disposable account/VM or independently
restore its throwaway snapshot; this harness never removes or resets a prior run.

## Build-only recipe

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
configuration is not supplied here. **Neither build nor payload command has been run.** No Windows
compilation, supervised-process qualification or execution result is claimed.

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

The harness calls only the production native custody API for these controls. It does not create ordinary
records using an unsafe filesystem substitute, promote delete-on-close stages, borrow a lease for
deletion, or delete any profile directory/file. Expected-ID deletion is exercised **only for rejection
without a profile lease**, not successful record deletion. Normal provider-owned stage disposal is the
only deletion behavior exercised; it acts on those exact synthetic delete-on-close handles.

The canonical directories, fixed empty lock files, synthetic persistent candidates and synthetic renamed
header/record files are retained. They are not a usable application profile or real ciphertext payloads.
Pending names are not application records or commit markers; do not promote or reuse these fixtures.
There is no recursive/pathname
cleanup, ACL reset, repair, migration, recovery or attempt to turn a failed run into a reusable profile.
On failure, the current native root receives its actual terminal drain; every original role/stage/candidate owner
is left to that native drain rather than repeated ad-hoc closes. Uncertain cleanup remains a failure.

## Test-only bounded ownership and output

A dedicated watchdog starts **before** preflight or any native operation. Its fixed 120-second budget
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

## Explicitly not established by this source or a future v1 smoke pass

- Any Windows SDK build or actual Windows execution today: **not performed**.
- A supported Windows release/build floor, FileCaseSensitiveInfo applicability on all target systems,
  x86/ARM64 support or behavior outside native Windows x64 on admitted local fixed NTFS.
- Independent adversarial ACL/DACL validation, creation-time security races, inherited/extra/null ACLs,
  impersonation changes during an operation, junction/symlink/ADS/hard-link attacks or parent replacement.
- Cross-process share/lock exclusion or process-contender authorization/lifecycle: no subprocess code exists.
- Complete application-record read/write, successful expected-ID deletion, adversarial collision races,
  full-disk/partial-write/flush/close fault injection, deletion-pending interoperability or close uncertainty.
  The narrow synthetic header collision check above is not those broader campaigns.
- Atomic publication/replacement/deletion, namespace durability, crash/interruption recovery or any promotion
  of disposable staging as a full transaction. The narrow create-only rename smoke does not establish
  no-replace races, post-attempt fault handling, directory durability or replacement/deletion transactions.
  Root identity persistence within one run is not a durability claim.
- JNI class/exception/export execution, byte-manifest loader authority, Authenticode, installed DLL custody,
  signatures, watchdog/application-exit integration, full encrypted-vault behavior or the complete provider ABI.
- Actual RPC networking/encryption/discovery/trust/reconnect functionality or installed Desktop/MSI behavior.
- Combined Foundation compatibility, release qualification, Maven publication or READY FOR RELEASE status.

Those campaigns remain separate required engineering/infrastructure work. A refused preflight is not a
platform skip counted as pass, and a successful smoke cannot change `0x43`, full-provider availability,
the maintained source's release gates or the protected application publication pipeline.
