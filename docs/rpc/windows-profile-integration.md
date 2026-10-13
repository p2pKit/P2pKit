# Windows RPC profile integration contract

**Implementation status: NOT_IMPLEMENTED. Runtime qualification: NOT_QUALIFIED.**

The complete Windows backend remains incomplete. The managed filesystem seam,
validation-only adapter, and partial C/JNI custody implementation now exist, including
composed record writes/deletes, bootstrap synchronization and conservative interrupted-state
admission. These implementations do not supply a qualified Windows DLL, secure loader,
qualified durable NTFS transactions, or installed-runtime evidence. The production Windows profile gate remains closed.
See the implementation checkpoints below.

This document records the missing protected-storage work; it does not enable a
Windows backend. Integrating the RPC section into the existing Desktop sample
must not make its Windows Host/Client buttons usable through an unprotected,
plaintext or in-memory identity fallback. Other supported sample sections may
remain available. A rendered Windows UI is not evidence of RPC readiness.

## Current implementation and reusable reference

`DesktopRpcProfile` derives a 256-bit key from the application passphrase using
PBKDF2-HMAC-SHA256 (600,000 iterations, random 16-byte salt). `LabVault` encrypts
bounded, namespace-authenticated records with AES-GCM. The profile lock remains
held while roles can use its identity/trust. Stop preserves saved identity and
trust; wrong passwords, corrupt records and missing metadata do not reset them.

The filesystem implementation is POSIX-only: exact `0700`/`0600` modes, owner and
symlink checks, filesystem identity readback, `FileChannel` locks, synced temporary
files, exclusive publication and atomic replacement, and directory synchronization.
Windows cannot be enabled by bypassing unsupported permission or directory-sync
calls. The existing general-purpose file-transfer destination explicitly has a
weaker Windows durability contract and is not a protected-profile substitute.

Reviewed source at foundation commit
`b69202ab900f7129bf5c043853dd28489c599195`,
`scripts/hosted_windows_files.py`, contains useful **Python/ctypes evidence-custody
primitives**: token-derived ownership, atomically protected DACLs, pinned
handle-relative creation, native identity/security readback and bounded I/O.
It is not a JVM storage provider. In particular, its ordinary custody API is
create/read-only and does not supply the profile's replacement/deletion
transactions, encrypted-store integration or profile lock lifecycle. Historical
model tests and any unrelated receipts must not be relabelled as profile tests.
Do not bundle or invoke that Python program as an application-storage shortcut.

## Proposed implementation boundary

A sample-owned Windows JNI provider can reuse the existing JVM cryptography
without introducing JNA or another Maven dependency. Its versioned, bounded ABI
must own opaque generation-tagged handles, not expose native pointers/descriptors
to callers. Keep POSIX behavior unchanged and select Windows explicitly; a missing
or invalid native backend fails closed, never falls back.

The provider must implement and independently read back:

- Actual effective-token user/default-owner SIDs; no caller-supplied SID or
  display-name authorization. Define impersonation/elevation handling explicitly.
- Private creation with a protected DACL **at creation time**, admitting only the
  approved user and SYSTEM policy. Reject null, broad, unknown or unexpectedly
  inherited ACLs. Creating with defaults and applying an ACL afterward is unsafe.
- Initially, only explicitly supported local fixed NTFS storage. Reject UNC,
  device/drive-relative paths, aliases, unsafe/reserved components, alternate data
  streams, reparse points/junctions, unexpected hard links and delete-pending files.
- Pinned ancestor handles and handle-relative opens/creates, volume/file IDs,
  exact final-path and ACL checks. A pathname check followed by an unrelated
  pathname open is not equivalent custody. Public JDK ACL views alone do not
  establish the complete protected-DACL/handle-relative/native-metadata contract.
- An exclusive process/profile lock, serialized namespace mutations, bounded
  reads/writes and flushes, atomic create-if-absent and replacement, and
  identity-checked deletion. Preserve the current 262,144-byte record bound.
- Close/operation race protection, noninheritable handles, bounded admission,
  retained failed cleanup, and no reuse of an uncertain released native handle.
  Conceal private UI immediately, but keep the profile owner until roles and
  operations actually retire; navigation must not manufacture a successful close.

The application passphrase is not the Windows login password. Preserve current
key/character-array cleanup and provider-copy limitations; do not promise secure
physical memory erasure or add DPAPI/password recovery implicitly. SYSTEM,
privileged administrators and compromised same-user application code are outside
the user-private-file isolation boundary.

## Decisions required before implementation

1. Supported Windows versions, native architectures, filesystems and profile root
   location, including whether roaming, synchronized or removable storage is refused.
2. Exact token/DACL inheritance policy, including elevated default owners and
   impersonation. Reusing the reference policy requires an explicit decision.
3. The crash-consistency contract: publication, directory-entry durability,
   interrupted replacement and recovery ordering. `FlushFileBuffers`, a Java
   atomic move, or skipping directory fsync must not be asserted equivalent
   without a demonstrated Windows contract. Uncertain/incomplete state is retained,
   not silently reset or overwritten.
4. Whether the existing record format can remain byte-compatible or needs a
   versioned Windows transaction envelope. Any migration must preserve identity,
   trust and wrong-password behavior; a platform switch must not reset trust.
5. Native operation deadlines, cancellation/late-completion ownership, recovery
   after unknown close, and any terminal application-exit policy. Blocking native
   filesystem calls are not made cancellable merely by cancelling a coroutine.

## Existing application packaging only

The existing Desktop tasks now include Windows-x64 native compilation, bounded PE/manifest inspection,
component resources and a packaged parent-pin JAR. See [the implemented packaging wiring](windows-profile-packaging.md).
This does not implement the trusted first-load bootstrap or enable provider admission. The current native ABI13
already implements composed record writes/deletes; the remaining closed gate must not be described as though
those primitives were absent. Protected-profile runtime and installed-MSI qualification are still outstanding.

Attach architecture-specific DLL builds, resource staging and verification to the
existing Compose Desktop application/distributions and corresponding CI jobs.
Do not introduce another installer, executable application or release pipeline.
Load only a reviewed app-owned absolute library with source/hash/ABI/architecture
and path-integrity checks; reject mismatches before execution. Native imports must
resolve to approved Windows system libraries, not the current working directory.
Use the existing distribution's signing/provenance process; developer artifacts
are not signed-release or installed-runtime qualification.

### Final-file sharing pin prerequisite

`WindowsProfilePinnedImage` retains a real Windows JDK 17 `FileChannel` opened with
`READ`, `NOFOLLOW_LINKS`, `NOSHARE_WRITE` and `NOSHARE_DELETE`. It bounds the image
before allocation, reads through the original channel, checks the externally pinned
manifest/PE/digest, and performs a second held-channel readback before returning.
Verification failure seals later reads without discarding the cleanup owner; close
attempts that owner once and retains any close failure. No new Maven dependency is used.

This is **final-file byte/share validation only**, not permission to load the image.
It supplies no installed-ancestor custody, ACL or Authenticode verdict, protection
against preexisting writable mappings, or identity of a loaded module. It exposes
neither an executable pathname nor `System.load`. The Foundation/RPC integration
must still establish independent installed-launcher/ancestor authority before any
native execution. A candidate sidecar cannot establish that authority.

Portable inert-owner tests are distinct from `verifyRpcWindowsPinnedImage`, an
explicit Windows-only probe using ordinary synthetic files. That task refuses a
non-Windows host instead of reporting a skipped platform test as a pass. Its checks
cover final-file sharing and byte tampering only; they do not touch the protected
profile, launch network roles, load a DLL, or qualify the installed MSI. The normal
JVM suite and release packagers do not automatically run this opt-in probe.

## Required verification, separately reported

**Agent-owned engineering:** define/review the ABI and transaction model; implement
JNI, storage/locking integration and existing-app packaging; add failure-first
policy/parser/ownership tests; review all combined source and dependency inputs.
None of that is classified as the user's physical-device testing.

**Native Windows execution:** build and execute each claimed architecture, then test
real token/DACL creation/readback; broad/null/inherited ACL rejection; junction,
symlink, ADS, hard-link and path-alias attacks; parent replacement races; exclusive
locks across processes; partial/full-disk/flush/rename failures; interruption and
restart recovery; wrong password and ciphertext tampering; source/ABI/architecture
and DLL tampering; bounded I/O; close races and exact native-handle retirement.
Finally exercise persistence, RPC Host/Client and shutdown in the existing packaged
sample, with unchanged exact-peer approval and network-admission policies.

Mac-hosted models can test policy and orchestration but cannot prove Windows
security descriptors, NTFS transactions, locking, DLL loading or installed behavior.
No native Windows profile checks were executed for this design document. Missing
Windows execution infrastructure remains a separate qualification blocker; it does
not make the unfinished engineering complete. Until both implementation and required
native evidence exist, Windows protected RPC profiles remain unavailable.

## Managed implementation checkpoint

`profile/ProtectedProfileFiles.kt` separates an owning profile session, relative
directory operations, and lock leases. `PosixProfileFiles` delegates to the existing
POSIX modes, publication, locks and directory sync. `LabVault` retains the same
record format, cryptography, namespaces and path-based mutex identity. A session
owns its directory handles; `vault.close()` retires key use, not that session.
Fixture destruction can therefore verify/delete owned records after vault close.
`DesktopRpcProfile` closes the session after vault and lock cleanup, retains the
first close failure, and does not retry an uncertain physical close.

`WindowsProfileFiles.openForValidation` accepts a supplied native-contract model,
not an application setting or production fallback. It enforces one active native
operation, a 32-live-handle bound, no queued acquisitions, registered late results,
seal-before-close, exact terminal close outcomes and failed-handle retention.
Interruption never abandons the actual cleanup owner. Close records both thrown
`InterruptedException` and a restored interrupt flag (including a normal condition
wake-up), then restores the caller's interrupt after retirement. The first
interruption diagnostic is retained without unbounded accumulation; native close
failures remain primary when they occur first. The terminal outcome is cached at
its final interrupt observation. Interruption is non-success, not proof of native
cancellation, even when all handles were released.

Writes allocate their private copy only after single-operation admission, current
directory verification and component validation. Busy, closing, closed or poisoned
callers cannot allocate a payload copy outside that owner. The admitted copy is
cleared on success and failure before ownership is released. Components, read sizes, directory inventory,
metadata shape and expected file identity are checked. Its model tests exercise
the actual profile/vault callers as well as adversarial adapter behavior. These
tests cannot establish the native assertions represented by metadata flags.

The managed decoder rejects zero volume and all-zero file IDs while preserving
unsigned native ID bits carried in signed JVM values. Child/file observations must
match their pinned parent's volume before publication, caching or deletion; a
caller-supplied typed deletion identity is revalidated through the same decoder.
Rejected allocated child handles remain owned for session cleanup, not cached as
usable directories. These checks do not enable the incomplete Windows provider.

### Complete provider ABI still to implement and qualify

`WindowsProfileNativeApi` is a contract only, not JNI code. ABI version 1 proposes
positive opaque handles and six-word identity observations:
`[version, volumeId, fileIdHigh, fileIdLow, policyFlags, linkCount]`. Required low
flag bits 0–7 represent native x64, fixed local NTFS, actual token-user ownership,
exact protected user+SYSTEM DACL, no reparse point, no delete-pending state,
canonical pinned custody, and noninheritable handle respectively. Bit 8 is a
directory; bit 9 is a regular file; unknown flags or a link count other than one
are rejected. The native implementation must derive these from independent OS
readback on the actual handle, not caller assertions.

Capability bits 0–6 require root admission, handle metadata/custody, exclusive
locking, atomic create, atomic replacement, approved durable directory-entry
transactions, and exact ownership/cleanup. The adapter requires all seven;
claiming bits is not a qualification mechanism. A native allocation that fails
before returning its handle remains the native provider's cleanup responsibility.
All byte/string/result bounds must also be enforced before native allocation.

The root policy is native Windows x64 and local fixed NTFS under the OS-resolved
LocalAppData `P2pKit/RpcProfile`, created with the actual token user and SYSTEM
protected DACL. Do not use environment/user-supplied identity as authority.
Remaining engineering includes connecting the partial handle-relative JNI custody
implementation to complete transaction/durability and the retained/refused interrupted-state policy below;
a noncircular loader that can
verify its app-owned DLL before executing it; architecture/signature/source-bound
existing-MSI packaging; and actual Windows qualification of the terminal watchdog for blocked OS calls. No DLL,
Windows SDK, Windows execution or installed-runtime result is supplied by this
checkpoint. An Apple compiler or a passing memory model cannot close those gates.

### Partial native custody checkpoint

The sample-owned [native custody component](../../samples/p2p-sample-rpc/native/windows-profile/README.md)
has real Win32 implementation source and bounded JNI entry points, not a Java ACL
substitute. Its separate custody ABI is **13**, with **23** exports and capability
mask **`0x43`**. The complete adapter still requires ABI **1** and **`0x7f`**;
the partial component must never be passed off as that full contract.

The implemented primitives include pinned root/child custody, explicit private
child and fixed lock-file creation, existing-record observations, disposable
encrypted-record staging, expected-ID deletion intent, composed record publication/deletion,
and exact original-handle retirement. A successful file flush is not a durable namespace transaction, and
deletion intent is not a promise of durable absence. Unsafe existing objects are
not repaired, replaced, or used as a fallback after failed creation.

Native roles bind the original root, its canonical direct `identity` child, and
the fixed empty `profile.lock`/`vault.lock` leases to non-reused owner tokens.
Creating `identity` or acquiring its vault lease requires a live, freshly verified
profile lease. Root staging/deletion requires that profile lease; identity
staging/deletion requires both leases. Other mutation scopes are refused. Ordinary
pre-profile metadata observations remain available and grant no mutation authority.
Normal lease retirement refuses dependent live roles; whole-root shutdown still
attempts every original owner independently in reverse creation order. Uncertain
cleanup retains its role and poisons admission rather than pretending the lease
was released. Synthetic fixture destruction does not relax these production rules.

`WindowsProfileCustodyException` preserves explicit native failure codes without
paths, identities, payloads, or raw OS messages. JNI does not start work with a
pending Java exception; failures retire unreturned Java references and preserve
the original exception. Unknown codes do not grant retry or recovery authority.
The PE and component-manifest checks validate bounded bytes and independent pins,
not Authenticode, installed-path custody, native loading, or runtime behavior.

The maintained portable C/JNI controls and JVM contract tests exercise these
source-level boundaries only. They do not compile the Win32 translation unit or
prove NTFS/DACL/sharing/crash behavior. Actual Windows SDK compilation, complete
provider and application wiring, and installed-MSI qualification remain required.
The exact supported Windows release/build floor must also be selected and tested:
the current source requires `FileCaseSensitiveInfo` on every pinned directory.
The compile-time `_WIN32_WINNT=0x0A00` setting alone does not establish support for
every Windows 10 build, or for newer rename flags that a transaction may require.

`pwp_win_prepare_record` creates a distinct persistent, uncommitted candidate, exposed as
`WindowsProfileCustodyJni.prepareRecord`; it does not satisfy the complete adapter's `write` contract.
Unlike disposable staging, it uses no delete-on-close flag. Under the same native role grants,
it privately creates, writes and file-flushes at most 262,144 bytes, then rewinds and verifies
every byte plus EOF through the original handle with 4-KiB scratch. The opaque owner keeps
its granting leases alive; normal metadata/reads/inventory refuse a live candidate. Close,
including failure cleanup or root drain, retires only the original handle and retains the
candidate file. Partial candidates are never implicitly promoted, retried or deleted.
This advances header/vault write preparation, not atomic publication, namespace durability
or recovery. Custody ABI13 has twenty-three JNI exports, including the composed record-write and
expected-ID deletion operations described below; capability `0x43` and the closed provider gate remain unchanged.
See the native component's persistent-candidate section for its exact scope.

`pwp_win_rename_candidate`, exposed as `WindowsProfileCustodyJni.renameCandidate`, supplies same-directory
create-only name publication,
not durable commit. It uses the original DELETE-capable handle and the classic native simple-name/NULL-root
rename contract, never replacement or a parent-sharing workaround. Destination scope is exactly root
`profile.header` or identity `<64-lowercase-hex>.aesgcm`. Original ID/ACL/path and prepared size receive
pre/post/file-flush verification; the same owner/grant stays held after success. Post-attempt uncertainty
seals the session and remains quarantined even if its one physical close succeeds. It cannot promote a
disposable stage, satisfy the complete write capability, or prove namespace durability/recovery. Its
native smoke assertions require source-matched Windows compilation and execution;
the shared portable controller is not an NTFS substitute.

The maintained [real-Windows custody smoke source](../../samples/p2p-sample-rpc/native/windows-profile/tests/windows/README.md)
records historical source-bound MSVC build evidence, but remains **NOT_EXECUTED**. Changed source needs
fresh Windows build evidence. Execution requires a separately authorized disposable standard-user environment
and bounded external process owner. It does not complete the provider, authorize execution or qualify an MSI.

## Terminal application-exit prerequisite

`WindowsProfileTerminalClose` implements the final Windows application-exit boundary, not ordinary Stop/Back
and not a native-provider selector. `DesktopRpcTerminalExit` exposes the actual application policy with an explicit
**30,000 ms** budget. It arms a dedicated non-daemon deadline before concealment, claims
exactly one cleanup worker, and retains the actual owner through native return. The deadline also covers the
completion callback. Independent monotonic elapsed-time checks reject late completion even when scheduled
expiry delivery is delayed; an unavailable clock fails closed. Late returns after expiry cannot report successful retirement or restart admission.
The concrete deadline calls `Runtime.halt(125)` without waiting for shutdown hooks: that is a failed terminal
exit with unproven cleanup, **not** successful native cancellation or a cleanup receipt. Successful whole-app
retirement calls `System.exit(0)` while the watchdog is still armed, including through shutdown hooks; returning
from an asynchronous Compose exit request cannot disarm it. A caller must supply complete application-owner
retirement, not just one profile. Construction, ordinary Stop and section Back do not arm the policy.

The RPC panel has a separate `requestTerminalClose`: it conceals private UI immediately and one terminal waiter
subscribes to any existing Back-close attempt. Busy is not the first terminal waiter's final outcome. Unlock
retirement joins the actual task and retains the exact returned profile even when EDT delivery fails; no late
result starts a role after terminal intent. Explicit failed-cleanup observations preserve identical cached
exceptions without relying on self-suppression. A clean wrong-password rejection remains retryable. Profile
retirement occurs only after the runtime retires, and final notification waits for the actual panel job tree,
the detached runtime-cleanup job tree, and the return of the cancellation request. Failed cleanup is not retried.

Managed controls cover duplicate delivery, close races, failed scheduling/concealment/completion and retained
late native-model ownership. Forked JVM controls exercise blocked ownership, concealment and completion, plus
normal retirement, actual application exit and the bounded shutdown-hook case. They validate the executing JVM
host only; test source is not a passing run receipt. The canonical Desktop application selects this policy on
Windows and retires RPC, the existing sample holder, frame registrations and application workers. Actual
Windows/installed-MSI qualification remains required. No native loader or full-provider availability gate is enabled.

## Original-directory NTFS synchronization (custody ABI9)

`pwp_win_sync_directory` / `WindowsProfileCustodyJni.syncDirectory` adds a narrow directory flush under
verified profile/vault leases. The original root and canonical identity directory handles request and
independently read back the exact sync-capable access mask at first admission. The primitive uses
`NtFlushBuffersFileEx` with flags zero, revalidates custody and role generations before and after the
call, and retains uncertain completion across physical handle cleanup. No path is reopened for sync.

This uses the NTFS directory-structure persistence contract in Microsoft MS-FSA section2.1.5.7; it does
not infer that every filesystem implements that guarantee. The existing fixed-local-NTFS admission
remains mandatory. A sync call alone is not a full record transaction: ABI11–13 compose record operations
and fixed bootstrap acknowledgment separately. Interrupted-state recovery, native runtime tests, secure
loading and full adapter qualification remain required. Capability `0x43` and the closed provider gate remain.

The maintained write API requests atomic lease-serialized replacement, not an expected-target-ID CAS.
Its separate delete API does require expected-file identity on the actual deletion handle. This matches
the POSIX sample's validation plus atomic replace under its profile/vault leases; compromised same-user
code remains outside the documented private-file isolation boundary. Do not weaken deletion's stronger
identity contract or infer namespace durability solely from rename/file-flush success.

## Lease-serialized identity-record replacement (custody ABI10)

`pwp_win_replace_candidate` / `WindowsProfileCustodyJni.replaceCandidate` targets only canonical
`identity/<64-lowercase-hex>.aesgcm` names, never the immutable root `profile.header` or lock files.
The prepared candidate and original profile/vault grants remain owned. An existing destination must
pass private-file validation through a fresh unpublished handle, whose exact-once retirement precedes
classic same-directory replacement. An absent destination uses collision-refusing first insertion;
this is not a retry of a failed replacement. Unsafe objects and already-owned targets are rejected.

This primitive intentionally does not supply the full adapter's `write` success boundary. Directory
synchronization, candidate retirement and recovery must be composed and tested before enabling durable
profile writes. Namespace uncertainty seals admission and retains original cleanup ownership. No
alternate directory, relaxed sharing, live-lock release, expected-ID deletion weakening, or capability
promotion is introduced. ABI10's exact JNI export set rejects earlier images; production availability
remains disabled until complete implementation and native/runtime/packaged qualification.

## Single-admission record publication (custody ABI11)

`WindowsProfileCustodyJni.writeRecord` / `pwp_win_write_record` composes persistent preparation,
create-only publication or identity-record replacement, original-directory NTFS synchronization, and
exact candidate retirement under one native admission. A fresh `pwp-pending-` name carries 128 random
bits encoded as 32 lowercase hex digits. It is never a commit marker or authority to overwrite a file.
The native ledger, not the caller's directory token or chosen target name, establishes role authority.
Headers remain create-only; identity AES-GCM records support first insertion and replacement.

The JNI entry checks bounded payload length, both component strings and the boolean before native
entry. Payload copying occurs only inside the admitted native owner. Both strings are released on all
paths, including failure while acquiring the second. Native outcomes cross as fixed typed error codes;
JNI adds no retry, cleanup, directory reopen, stage promotion or fallback. No native candidate handle
escapes the composed operation. Incomplete preparation can leave private pending files for explicit
review; it never overwrites a header or promotes an incomplete identity after failure.

Success requires publication, directory synchronization and actual original-handle retirement. After
name publication, even a directory-sync admission refusal is an uncertain whole-write outcome, not a
harmless precondition failure. The original candidate is still physically closed once, while session
and ownership uncertainty remain sealed. This source composition does not by itself establish crash
behavior, durable creation of all bootstrap ancestors, restart recovery, secure
DLL loading or the complete provider. Those implementation and native-runtime gates remain separate;
neither full-provider availability flag nor the `0x43` capability mask is promoted by this addition.


## Single-admission expected-ID deletion (custody ABI12)

`WindowsProfileCustodyJni.deleteRecord` / `pwp_win_delete_record` composes expected-file-ID
verification, original-handle deletion intent/pending readback/actual close, strict post-close absence,
and original-parent NTFS synchronization under one retained native admission and original role grants.
Only a final raw `STATUS_OBJECT_NAME_NOT_FOUND` plus a NULL probe handle establishes the required
absence. A missing path, DOS-error aggregation, pending status, denied access/sharing, malformed handle
or any returned object does not. Any valid unexpected probe handle is retired exactly once; invalid
sentinels are not closed. Parent/grant checks run after probe retirement and around the original sync.

An initially missing target remains a typed `NotFound` error. The old `requestExpectedFileDeletion`
entry retains its separate intent-only semantics. Any uncertainty after the successful intent/close
boundary seals the whole operation as `CleanupUnknown`, never harmless missing/false. A memory-only
seal cannot inspect or reclose the already-retired source; probe verification may reuse its owner slot.
JNI preserves raw six-word IDs, clears bounded native copies, releases input strings and propagates
fixed errors without retry, cleanup or reinterpretation. ABI13 retains the ABI12/23-export inventory;
PE checks refuse earlier ABI11 images, while numeric ABI/manifest and pinned source/hash checks must
distinguish ABI12 from ABI13. The complete provider remains ABI1/`0x7f`, not this component.

Portable controller and actual-JNI/mock-backend tests are not Windows OS execution. The source-matched
Windows smoke adds a single declared synthetic ordinary-record deletion, plus wrong-ID/missing-grant
refusal, retained leases and immediate absence observations; it remains **NOT_EXECUTED**. Fixed bootstrap
acknowledgment is implemented separately below. Complete lock orchestration, interrupted-state handling, secure
DLL loading, full provider/installed-application wiring and native qualification remain required.

## Fixed namespace bootstrap and new-owner finalization (custody ABI13)

The actual native creation APIs now retain all original owners through ordered acknowledgment:

- `openRoot`: capture only OS-derived LocalAppData/P2pKit/RpcProfile and flush **RpcProfile → P2pKit →
  LocalAppData** before root publication. Always perform all three, including already-existing empty paths.
- `createChildDirectory`: under the original profile lease, flush **new identity itself → original root**.
- `createProfileLock` / `createVaultLock`: flush **original new file → original containing directory** before
  returning the exclusive lease. Vault creation keeps the exact original root/profile grant; it cannot
  use a replacement grant or claim public identity mutation authority before its vault lease is bound.

Only the fixed bootstrap owners and canonical identity obtain the exact sync-capable rights on their first
open. Actual rights and original token/raw handle/identity/parent/role/public state are checked around
every acknowledgment. No close/reopen upgrade, arbitrary public pre-lease sync, volume flush, write/delete
sharing relaxation, DACL repair or privilege fallback exists. The LocalAppData nonprivate inspection is
confined to the captured unpublished KnownFolder context, never exposed as public authority.

A bootstrap open can select create only after exact final `STATUS_OBJECT_NAME_NOT_FOUND` plus NULL,
missing-probe retirement and fresh original-parent verification. `exists` now applies the same strict
absence requirement before returning false. Path-missing, access/sharing errors, pending and late handles
are errors, not invitations to create or interpret records as absent. Once a create syscall is entered,
only exact final `STATUS_OBJECT_NAME_COLLISION` plus NULL proves no creation effect. All other failures
remain `CleanupUnknown`, including no returned handle and later failure after earlier P2pKit creation.
Actual original handles are still closed exactly once; ambiguity remains sticky even if close succeeds.
There is no automatic retry, namespace rollback, leftover adoption, unverified public lease or reset.

The private bounded namespace controller verifies between every sync and before publication/binding.
`pwp_child_finish` / `pwp_lock_finish` remain existing-open custody/file-only helpers; new APIs use the
composed path. Public `syncDirectory` still requires the ordinary original profile/vault grants.
The numeric ABI changes to13 with the same23 exports and `0x43` mask. Symbol inventory alone cannot
detect an ABI12 DLL; byte/source pins and later authorized real runtime ABI checks remain necessary.

Portable shared-controller and actual-JNI/mock-backend coverage is not Windows execution. The native
smoke now also reopens its own still-empty tree without resetting a fixture. Actual Windows storage,
crash/recovery, installed-loader/application and complete bridge qualification remain unexecuted/open.
The full provider's ABI1/`0x7f` admission and `IMPLEMENTED=false`, `QUALIFIED=false` stay unchanged.

## Conservative Windows startup inventory admission

The validation-only Windows filesystem adapter requires a bounded startup inventory under the
original profile lease, before passphrase/key derivation or header consumption. Root entries must
match the fixed profile whitelist and required file/directory types. An existing `identity` directory
must already contain its empty `vault.lock`; its inventory and member types are checked while the
original vault lease is held. Only `vault.lock` and exactly 64 lowercase hex digits plus `.aesgcm`
are admitted there. Pending/stage names, unexpected files, directories and invalid types are refused
intact—not deleted, promoted, reset, repaired or silently adopted.

This inventory operation does not alter records. It does **not** make the whole startup sequence
read-only: existing profile-lock acquisition may create a missing empty `profile.lock` before this
inventory begins. POSIX startup behavior is unchanged. Refusal is a conservative guard, not a full
crash-recovery protocol: the lack of a pending file after a rename still cannot prove a prior operation's
outcome. This validation-only source policy neither enables the native provider nor supplies Windows
runtime evidence. Actual interrupted-operation/durability and native integration qualification remain open.

### Supported interrupted-state contract

Automatic repair of every interrupted or damaged profile is **not** a required capability of this provider.
The supported policy is to acknowledge and authenticate a complete current canonical state, or retain and
refuse an incomplete, unknown or unauthenticated state. Refusal is not a successful rollback, recovery of
an earlier operation's outcome, or permission to reset identity or trust. The seven capability bits above
still require the real custody, locking, atomic mutation, durability and cleanup implementations; a policy
statement or passing memory model does not supply them or authorize a capability-mask change.

| Observed state | Required handling |
|---|---|
| Empty profile, or only its empty profile lock | Normal first initialization under the owned profile lease |
| Complete canonical inventory, successful original namespace sync and valid passphrase/proof | Admit the current profile; make no claim about an earlier unacknowledged mutation |
| Header without identity, missing identity lock, or missing/invalid proof | Refuse; do not recreate the missing application metadata or encrypted records |
| Pending/stage/unknown names or wrong object types | Retain and refuse; do not promote, remove or infer a destination for those entries |
| Uncertain native operation or cleanup | Preserve uncertainty and actual ownership; do not retry an uncertain close or report successful admission |

An already-used profile that loses its proof is not a fresh profile. Existing header, identity and trust
records must remain intact; authenticating a different proof value also cannot authorize initialization.
There is no new initialization/completion marker or transaction envelope. In particular, absence of an
independent completion marker would not prove that a profile had never completed initialization.

Wrong passwords and failed proof checks do not rewrite or repair application records. As described above,
ordinary profile-lock acquisition can create a missing empty `profile.lock` before inventory inspection;
the whole startup operation is therefore not promised to be read-only. This limited lock operation is not
authority to create a missing identity directory, identity lock, header or proof on an established profile.

`WindowsProfileRecoveryAdmissionTest` exercises the real `DesktopRpcProfile`/AES-GCM vault orchestration
over the existing inert Windows model. In addition to interruption and pending-name cases, it checks an
already-used profile with retained identity/trust and a missing proof, and an authenticated but incorrect
proof. Those refusals assert no attempted record/directory/lock creation or deletion, unchanged retained
bytes and identities, passphrase clearing and exact owner retirement. They do not prove Windows NTFS
crash consistency, storage persistence, native syscall behavior or installed-application readiness.

## Explicit Windows vault lease policy

The transferred `WindowsProfileFiles` path in `DesktopRpcProfile` explicitly constructs `LabVault`
with `nonBlockingLeases=true`. This covers proof admission, identity reads/writes, both trust purposes,
revocation and deletion, not just the initial profile lock and startup inventory. The existing native
lease boundary makes one exclusive-open attempt; the managed caller must not request waiting and then
silently have that request ignored. A failed lease does not trigger retries, a queue, weaker sharing or
another provider. "Nonblocking" describes lease acquisition policy, not a guarantee that Windows
filesystem calls cannot hang; actual ownership/terminal shutdown remains a separate requirement.

Every existing default, Path, POSIX and copier-validation vault constructor retains its previous
blocking policy. The per-vault mutex, key/copy lifetime and native-handle ownership are unchanged.
Inert call-routing regressions exercise trust/identity preservation across reopen and confirm the
non-Windows default remains unchanged. They do not qualify native Windows sharing or enable its provider.

## Partial managed JNI mapping

`WindowsProfileCustodyBridge` now maps the actual JNI subset through `WindowsProfileCustodyCalls`.
Before storage entry it checks the numeric custody ABI13 and `0x43` mask, including a second check
between strict existence and the selected lock operation. Writes generate one 128-bit pending name
and invoke the composed write once; deletion returns true only after native completion. Original errors
are propagated without absent-file reinterpretation, retries or fallback. A failed ABI check seals new
storage admission but cannot prevent an already-admitted owner's original cleanup call.

The bridge reports the real partial ABI/mask, so the complete `WindowsProfileFiles` admission still
rejects it. Construction never loads a DLL. Fixture-directory destruction remains unsupported; no
loader, production selector, complete recovery contract or installed-MSI qualification is supplied by
this mapping. Its deterministic mock-call tests are not native Windows execution evidence.

## Strict absence before first record publication

The create-only rename and replacement's first-insertion probe now select publication only after raw final
`STATUS_OBJECT_NAME_NOT_FOUND` plus an exactly NULL handle and successful original-probe retirement.
Previously those two probes used the ordinary reader's DOS-error aggregation, which also classified a
missing path as `NotFound`. That is not absent-target authority. Missing paths, pending results, malformed
success, access/sharing failures and late handles remain errors; valid late handles are retired once.
Failed retirement remains `CleanupUnknown`. Existing read/open error semantics do not change.

Both probes keep their original read-only access and sharing modes. The original candidate and profile/vault
grants remain held and are checked again before any rename; no failed probe authorizes replacement, retry,
fallback or parent reopen. The shared strict-open result classifier and candidate/ownership controllers have
deterministic raw-observation controls; their source is not Windows runtime, crash or installed-loader proof.
Custody ABI13/`0x43` and both closed full-provider gates remain unchanged.

## Current-state identity namespace acknowledgment at startup

After the existing Windows startup inventory admits only canonical names and validates their object types,
the managed validation adapter synchronizes the **original identity directory** while both the original
profile and inventory vault leases remain held. It then verifies both original directories again before
releasing the inventory lease. Header consumption, PBKDF2/key derivation, ciphertext authentication and
profile publication follow only after actual sync return and successful verification/lease retirement.
The existing native `syncDirectory` enforces its original-owner/grant checks; no root-only substitute,
reopened directory, new lease grant, additional writer or provider fallback is introduced.

This is necessary even when no pending name survives: a previous rename or deletion may have become visible
before its acknowledgment failed. The new boundary acknowledges only the currently admitted canonical
namespace. It does **not** establish that a previous write, deletion, RPC call or response succeeded, settle
historical execution evidence, authenticate record contents, or promote an interrupted candidate. Unknown
names and invalid object types still refuse before sync; subsequent header/proof checks still authenticate
the profile. Sync, verification or lease-retirement failure aborts admission, clears the transferred
passphrase and preserves original cleanup failures without retrying an uncertain owner. Records are not
rewritten, deleted, reset or automatically repaired. Fresh identity creation keeps its distinct native
bootstrap acknowledgment; POSIX behavior is unchanged.

`WindowsProfileStartupSyncTest` exercises the real shared profile/AES-GCM vault over the existing inert
model, including lost modeled proof/trust replacement/deletion acknowledgments with no pending name,
original-lease call ordering, blocked/error returns, post-sync verification, retained cleanup uncertainty,
unchanged record bytes/identities and subsequent authentication. The model keeps visible effects in memory;
it does not model NTFS persistence or prove power-loss recovery. These controls are not Windows execution
or installed-application evidence and do not enable the partial custody bridge or either full-provider gate.

## Exact create-result admission before bootstrap, stage or candidate use

All three native `NtCreateFile(FILE_CREATE)` sites now use the same three-way observation boundary before
any stage/candidate phase or bootstrap finalization can be admitted. Creation requires exact final raw
success, successful `IO_STATUS_BLOCK.Status`, `FILE_CREATED` information and a valid original non-NULL
handle. Only raw final `STATUS_OBJECT_NAME_COLLISION` with exactly NULL proves a failed call had no new
namespace effect. Failure I/O status/information are not used to infer absence or successful cleanup.

Previously the stage/candidate sites could return ordinary OS failure after an ambiguous create with no
returned handle, and an initialized candidate could turn a late handle's successful close into apparently
clean cleanup. They also accepted raw success/`FILE_CREATED` without checking the I/O status. Ambiguous
results now seal namespace/session uncertainty before exact original-owner retirement. Valid returned
handles are attached first and physically closed once; NULL and invalid sentinels are never closed.
Stage/candidate phases remain empty until creation is proven, so cleanup cannot mark a presumed stage for
deletion or let candidate close semantics erase the namespace seal. The original stage's delete-on-close
open flag is unchanged; retiring its handle is still required, not a guarantee that no name changed.
Even a clean collision remains a
failed operation, never absence, retry or adoption authority; independent cleanup uncertainty still wins.

After a proven creation, the existing bounded fill/readback/flush and pending-record behavior is unchanged.
A later candidate payload failure can leave an uncommitted pending name for explicit review; it is not a
published record, and successful handle retirement does not promise namespace cleanup or durability.
Access rights, sharing, original lease grants, custody ABI13/`0x43`, JNI exports and provider gates are unchanged.
`profile_creation_result_test.c` exercises the actual shared classifier, ownership ledger and existing
controllers with inert raw observations. It does not execute `NtCreateFile`, prove NTFS crash behavior or
supply installed-loader/full-provider qualification.
