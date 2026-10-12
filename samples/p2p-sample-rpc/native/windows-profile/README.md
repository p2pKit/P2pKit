# Windows protected-profile native custody (incomplete)

**Not a production provider. Windows runtime qualification has not passed.** Source-bound Windows SDK
build-only results exist; see the [Windows harness scope](tests/windows/README.md). They do not qualify
later source changes, native execution, protected-profile persistence, or the installed application.
The existing Windows UI/profile gate remains closed. Nothing here loads a DLL automatically.

Implemented source components:

- `profile_policy.c`: bounded component/path/ADS/ACL decoding and positive non-reused native ownership tokens;
  reserve-before-allocation, fixed-scope profile/vault role grants, exact-once close, dependency-aware retirement,
  failed-close quarantine and reverse creation-order cleanup.
- `profile_win32.c`: native x64/effective-token checks; OS KnownFolder LocalAppData root; pinned handle-relative
  ancestor/root/child opens and explicit collision-refusing `root/identity` creation under the profile lease;
  protected user+SYSTEM DACL
  **at creation**; native NTFS/identity/ACL/stream readback;
  bounded existing-record reads; existing-file identity/existence observations; a bounded 1,024-member native
  directory walk with independent member custody readback; exclusive fixed-role existing lock custody; explicit new
  root and identity-vault lock-file creation; disposable encrypted-record staging
  and distinct persistent, uncommitted encrypted-record preparation with original-handle byte readback;
  same-directory create-only candidate rename and cooperative identity-record replacement (not durable commit);
  exact-role original-directory NTFS metadata synchronization (not a complete record transaction);
  single-admission record-write and expected-ID delete compositions, retaining original grants through
  directory sync and actual file retirement; fixed bootstrap/new-child/new-lock namespace acknowledgment
  before public ownership (not a complete managed provider or recovery implementation);
  owning session retirement.
- `profile_jni.c` and `WindowsProfileCustodyJni`: actual bounded JNI calls to those components, not a Java ACL
  substitute. Errors contain fixed public codes, never paths, SIDs, records or OS exception text.
- `WindowsProfileCustodyCalls` and `WindowsProfileCustodyBridge`: the actual seventeen-call managed/JNI
  mapping described below, retaining partial ABI/capability reporting and no loader or production selection.

Custody ABI **13** retains ABI12's exact twenty-three JNI exports and strengthens creation/absence semantics;
its identity-record wire version remains 1. `WindowsProfilePeImage` rejects earlier export inventories,
including the twenty-two-export ABI11 image, but **symbols cannot distinguish ABI12 from ABI13**.
Numeric manifest/ABI checks and externally pinned source/byte hashes must do that; an ABI12 manifest is refused.
The secure loader must eventually verify the real native numeric ABI after establishing load authority.
Older ABI4–ABI12 sections describe their original scopes,
not the current ABI or new Windows runtime results.
This partial custody ABI is distinct from the complete `WindowsProfileNativeApi` adapter ABI 1.
The complete adapter still requires ABI 1 **and** `0x7f`; neither condition is changed to admit this
incomplete custody component. All custody revisions lack required durable-persistence capabilities.

The native component restricts elevated default owners and any thread impersonation rather than guessing
an effective owner. Existing unsafe directories/files fail; they are not repaired, reset, deleted or migrated.
An explicit `openRoot` may create the two private directories and now acknowledges their fixed original
namespace chain; this source contract is **not** executed crash/power-loss evidence or a complete profile transaction.
The context serializes admission without a work queue. Closing joins actual synchronous
OS calls; a hung call is bounded only by the explicit application-exit watchdog, not a coroutine timeout.
The canonical Windows Desktop exit uses a 30-second whole-application deadline; actual installed/native
qualification remains required and no ordinary Stop/Back operation acquires that deadline.

`capabilities()` returns `0x43` (root custody, metadata and cleanup only), not the required complete `0x7f`.
There is deliberately no claim for complete atomic write/replace/delete transactions, durable namespace transactions,
recovery or the complete
profile-lock orchestration. The full `WindowsProfileFiles` adapter must not accept this incomplete mask.

## Managed custody mapping (still not a complete provider)

`WindowsProfileCustodyBridge` implements the shape of `WindowsProfileNativeApi` using the actual JNI object
through the narrow `WindowsProfileCustodyCalls` interface. The JNI object retains the exact twenty-three
native methods, descriptors and exported names; seventeen participate in this mapping. The additional
low-level stage/candidate/delete-intent primitives are not substitutes for composed record operations.
Neither constructing this bridge nor its default JNI object loads a library or selects Windows production
storage. The future secure loader must establish independent executable-file authority first.

The bridge reports the real native ABI and capabilities, never substitutes complete-provider `1 / 0x7f`.
Before **each storage entry** it requires exact custody `13 / 0x43`; unchanged PE exports are not enough.
An initial wrong or unavailable numeric contract enters no storage call. Any failed pin seals subsequent
storage admission, even if later observations appear compatible again. Cleanup is different: after at
least one compatible admission, `close` forwards to the same original calls object without rechecking a
possibly failed numeric query. A never-admitted bridge cannot invoke native close. Actual token ownership,
admission/retirement ordering, late return handling and no-retry close remain the filesystem session's and
native ledger's responsibilities; the bridge does not maintain a competing handle registry.

| Managed operation | Mapping and refusal policy |
|---|---|
| Root, metadata, names and bounded read | Exact corresponding JNI call; `directoryIdentity` uses `identity` |
| `child(..., create)` | Exactly `child` or `createChildDirectory`; no probe or failed-create fallback |
| `lock(..., nonBlocking)` | Requires explicit `true` and exactly `profile.lock` or `vault.lock`; strict `exists`, then one matching existing/open or fixed create call |
| `write` | Validate the 262,144-byte bound and header/record target; generate 16 secure-random bytes once, encode `pwp-pending-` plus 32 lowercase hex, call `writeRecord` once |
| `delete` | Forward the exact expected identity to `deleteRecord`; return true only on composed completion; initial missing and all native failures remain errors |
| `sync` | Exact `syncDirectory` call, preserving native role requirements |
| `deleteIfEmpty` | Explicitly unsupported; fixture destruction is not a production native cleanup recipe |

Write mode is preserved: `profile.header` is create-only; identity-record names accept the native create
or replace operation. Role/directory authorization still comes from native original owners, not the name
alone. Entropy storage is cleared on success and every failure, with no collision retry, payload copy,
leftover deletion or alternate destination. Caller ciphertext ownership is unchanged. No native error
is reinterpreted as an invitation to create, retry, repair a profile or reset an identity.

Compiled JNI descriptor checks and deterministic managed-call tests cover the real mapping, exact inputs,
partial/full admission refusal, changed pins, cleanup after failed introspection, random-name and size
bounds, single-attempt lock/write/deletion, and error-object propagation. They use inert calls, not a fake
complete provider claiming `1 / 0x7f`, and are **not DLL loading, Windows storage or installed-MSI evidence**.
The production gates remain false. Secure loading/packaging, terminal-runtime qualification, full recovery
and source-matched Windows/installed-runtime qualification remain unfinished. Historical checkpoint
statements and evidence below retain their original scopes; this mapping does not relabel them.

## Fixed namespace admission and creation acknowledgment (ABI13)

The actual native public creation paths now use the shared `pwp_namespace_commit_apply` controller under
their existing single nonqueued admission. It does **not** add a public pre-lease synchronization API.

| Public call | Original owners and ordered acknowledgments before publication |
|---|---|
| `openRoot()` | Fixed OS-derived LocalAppData → P2pKit → RpcProfile acquisition; flush **RpcProfile → P2pKit → LocalAppData** |
| `createChildDirectory(root, "identity")` | Retain the original root/profile lease; flush **new identity itself → original root** |
| `createProfileLock(root)` | Hold the new unpublished exclusive file; **file flush → original root directory flush** |
| `createVaultLock(identity)` | Retain the original root/profile grant and identity; **file flush → original identity directory flush** |

Root bootstrap performs all three acknowledgments even when both private directories already exist.
An existing empty tree might be a leftover of an earlier unacknowledged bootstrap. Only the final
KnownFolder component, fixed P2pKit/RpcProfile, and canonical identity acquire the exact sync-capable
directory mask `0x001200a3` on their **first** open. Other ancestors retain their earlier read-only mask.
Sharing remains `FILE_SHARE_READ`, without write/delete sharing. No close/reopen upgrade, alternative
root, environment override, generic access, privileged fallback, arbitrary ancestor or volume sync exists.
The broader initial rights can legitimately fail Windows access/sharing checks; that remains a refusal,
not grounds to relax the contract. Real target evidence is still required.

Every boundary verifies the captured owner token, raw handle, parent, identity, public state and relevant
original profile/vault generation. Actual granted access is re-read around directory sync. LocalAppData
uses nonprivate inspection **only inside its fixed OS-derived unpublished bootstrap scope**; P2pKit,
RpcProfile and identity still require the complete private DACL/NTFS/case/path policy. Existing public
`syncDirectory` retains its profile/vault lease requirements. A new vault's private admission retains
the original profile grant rooted at RpcProfile; it does not invent a public vault grant before binding it.

Opening a fixed bootstrap name may reach `FILE_CREATE` only after raw final
`STATUS_OBJECT_NAME_NOT_FOUND` plus exactly NULL, retirement of that missing probe, and a fresh check
of the same original parent. `exists` likewise returns false only for that exact final-name absence
with clean probe retirement and original-parent verification; `PATH_NOT_FOUND`, access/sharing/pending
errors, success-without-handle and late returned objects cannot become harmless absence.
Existing ordinary read/open error typing is not silently redefined.

Before syscall entry, a rejected create has no claimed namespace side effect. After `FILE_CREATE` starts,
**only final `STATUS_OBJECT_NAME_COLLISION` plus exactly NULL** proves no creation effect. Every other
failure is uncertain, even with no returned handle; a valid late handle is still ledger-owned and actually
closed once. Earlier P2pKit creation stays sticky if later RpcProfile acquisition fails. Creation, any
sync entry, publication or binding failure after mutation seals `CleanupUnknown` before original-owner
retirement. A successful physical close cannot erase that ambiguity. Memory-only sealing never substitutes
for close, revisits a retired slot, removes a pathname, repairs a DACL, retries or publishes a partial result.

The low-level `pwp_child_finish` and `pwp_lock_finish` remain custody/file-only controllers for existing
admission; they are not the new creation finalizer. New locks keep the same share-none lease and file rights.
The namespace controller accepts only bounded ordered counts and verifies between each acknowledgment,
then publishes/binds only after all succeed. Invalid controller arguments retain caller ownership;
native callers still account for any earlier creation before unwinding.

Twenty-two new portable groups exercise the actual shared namespace/sync/owner/role controllers and raw
classification predicates. Six actual-JNI/mock-backend groups cover creation forwarding, fixed errors,
no fallback/retry/cleanup in JNI, and absent-versus-failed existence. These are not Win32/NTFS execution.
The smoke source additionally reopens its own still-empty bootstrap tree and compares its original identity;
it never resets a prior fixture. Current ABI13 native smoke is **NOT_EXECUTED**. Full adapter/loader,
terminal-runtime qualification, interruption/recovery and source-matched native/installed qualification remain open.
Capabilities stay `0x43`; `IMPLEMENTED` and `QUALIFIED` remain false.

## Current role-bound admission and retirement

Profile and vault authority is recorded in the bounded native `pwp_roles` ledger, using the exact
positive, non-reused owner tokens. A filename, public directory token, arbitrary public file or reused
numeric OS handle is **not** lease authority. The native caller binds a role only after independent
original-handle scope/identity/security checks and successful owner publication. The profile role belongs
to the session root; the vault role belongs to the one canonical direct `root/identity` token and the
exact granting profile-lease generation. Duplicate canonical identity opens, including insensitive
spelling aliases, cannot create another mutation authority.

| Operation | Required native role |
|---|---|
| Root/file metadata and bounded existing reads | Admitted metadata custody; no profile lease required |
| Open an existing child directory | Metadata custody; does not itself authorize mutation |
| Create `root/identity` | Live, freshly reverified profile lease; no alternate/sibling/deeper creation |
| Open/create `root/profile.lock` | Exact root; no existing profile role or dependent stages/vault |
| Open/create `root/identity/vault.lock` | Canonical identity token and live, freshly reverified profile lease |
| Stage or request expected-ID deletion under root | Live, freshly reverified profile lease |
| Stage or request expected-ID deletion under identity | Both live, freshly reverified profile and vault leases |
| Replace an identity AES record candidate | Original candidate and both freshly reverified leases; fresh target only |
| Synchronize private root directory metadata | Original write-capable root handle and reverified profile lease |
| Synchronize canonical identity directory metadata | Original write-capable identity and reverified profile+vault leases |
| Compose root header write | Original root and profile lease; immutable header/create-only |
| Compose identity AES record write | Original identity and profile+vault leases; create-only or cooperative replacement |

`lockExisting` now admits only the exact component spelling `profile.lock` at root or `vault.lock` at
canonical identity. Existing locks retain verify–file-flush–verify–publish; new locks now additionally
acknowledge the original containing directory before publication as specified in ABI13 above. Both
must be ordinary zero-length one-link files at the expected scope. They retain their different
`FILE_OPEN` versus collision-refusing `FILE_CREATE` semantics; neither operation rescues the other.
For vault admission, native checks revalidate the actual held profile file, not just a role boolean.
Pre-profile `exists(root, "profile.lock")` and `read(root, "profile.lock", 0)` remain nonmutating
metadata operations, preserving the initialization order in `DesktopRpcProfile.open`.

All post-admission exits from `identity`, `fileIdentity` and `exists` now use the same cleanup-aware
result finalizer as the other custody operations. A newly failed security-descriptor or token-handle
release reports `CleanupUnknown`, not an ordinary policy error or successful observation. The shared
portable result-precedence matrix covers every custody result with clean, failed and poisoned flags;
it is not Windows fault-injection evidence. A later call still receives the unchanged sealed-session
`Closed` admission result. No native ownership, ABI, capability or provider-availability rule changes.

A stage captures its root, directory, profile and (for identity) vault grant **before** bulk payload
allocation/copy. These exact generations are checked again around creation/fill/readback and bound to
the successfully published stage token. Deletion similarly captures and revalidates authority around
the original-handle deletion-intent and pending-readback callbacks. No callback reacquires the native
gate or infers authority by reopening a path. A later lease with the same filename or reused OS handle
cannot validate an older grant.

Independent close refuses a profile while a vault or any of its stages remains; vault/identity close
refuses dependent stages or the live vault as applicable. Successful close clears only that exact role
after the original resource really retires. Failed/quarantined close keeps the association and prohibits
reuse. Uncertain cleanup of a failed **unpublished** stage/vault admission also poisons ownership and
prevents ordinary granting-parent retirement, even though no public role was returned.

Whole-root close instead invokes the actual reverse owner drain, deliberately bypassing those ordinary
dependency guards. It independently attempts every original close even after a vault/stage failure,
retains quarantine/uncertainty, and never physically retries a quarantined value. Stage cleanup still
uses its saved original delete-on-close handle; it does not require a live-token lookup for an owner
already marked retiring. Global poison prevents new metadata/security allocations in that cleanup path.
Only a completely clean drain clears the role ledger. Reopening a root first proves every prior owner
is empty/retired and then binds a fresh token above the new session's monotonic token floor; it never
resets the owner counter or adopts a quarantined slot.

The twenty portable role-controller groups cover native owner publication, fixed selectors, pre-profile
metadata custody, wrong roles/directories, duplicate and stale tokens, lost live/public/resource state,
exact grant generations, stage dependencies, bounded public capacity, unpublished failure retention,
terminal reentry rejection, independent reverse cleanup and fresh-root admission. These are synthetic
resource controls of the **actual shared controller**, not Windows SDK/NTFS/DACL/share or installed-MSI
evidence. `check-portable.py` registers them with the existing ASan/UBSan suites.

The role hardening originally landed within custody ABI8's nineteen exports; current ABI13 retains the
separate primitives described below. Capability `0x43` and closed complete-provider availability are unchanged.
The role ledger itself adds no durable namespace transactions,
record publication/recovery, native loader or runtime qualification. Live lock files cannot be deleted
by the expected-file deletion primitive. In particular, the existing synthetic `LabVault.destroy`
helper is not a production native destruction recipe; complete-provider cleanup still needs explicit
integration rather than weakening role admission. Real OS tests require a disposable Windows account
or VM because the KnownFolder root is intentionally non-injectable; there is no temporary-path fallback.

## Verification and build boundary

The current [real-Windows custody smoke source](tests/windows/README.md) is **NOT_EXECUTED**.
Earlier source revisions have Windows SDK build evidence; that does not qualify the new composed-delete source.
It requires a separately authorized disposable standard-user environment and bounded external process owner;
it neither enables the complete provider nor supplies Windows runtime or release qualification.

The maintained create-only command runs portable C controls with ASan/UBSan and checks the actual JNI C
translation unit against existing JDK17 headers. It writes source hashes, exact commands and separate logs:

```sh
python3 -B samples/p2p-sample-rpc/native/windows-profile/check-portable.py \
  --output /absolute/new-private-check-directory \
  --clang /usr/bin/clang --jdk /absolute/existing/jdk17/home
```

For a direct equivalent C policy invocation from this directory:

```sh
clang -std=c11 -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined \
  profile_policy.c tests/profile_policy_test.c -o /absolute/owned/output/profile-policy-test
/absolute/owned/output/profile-policy-test
```

This exercises the same portable policy and ownership code used by the Windows implementation. It does
**not** emulate Windows APIs or establish NTFS/ACL/locking results. The Win32 translation unit refuses
non-Windows/non-x64 compilation. Compile it only against an actual Windows SDK, JDK JNI headers and an
x64 C11 compiler; link the explicit Windows system imports named in that source. No SDK, DLL, installer,
private key, generated build output or globally installed tool is included here.

## Still agent-owned engineering (not “physical testing”)

1. Complete and review atomic record mutation, durable namespace transaction/recovery and full lock orchestration.
2. Implement the noncircular app-owned DLL loader and source/hash/PE/import/signature validation, then attach
   staging to the existing Desktop application/MSI—not a separate application or release pipeline.
3. Qualify the implemented 30-second whole-application exit policy on actual Windows/installed bytes, including
   retained late unlock/native ownership and a hung JVM shutdown hook. It does not cancel native I/O or prove cleanup.
4. Compile each changed Windows source/JNI revision, resolve SDK/compiler issues, and add OS adversarial/runtime
   tests for all native branches. Secure production wiring remains deliberately absent until those contracts exist.

Windows x64 runtime/installed-MSI validation is a separate unavailable infrastructure gate. Passing these
portable controls alone must never flip `WindowsProfileAvailability.IMPLEMENTED` or `.QUALIFIED`.

## Single-admission record write (ABI11, not a complete profile provider)

`writeRecord` invokes `pwp_win_write_record` with a directory token, caller-supplied canonical pending
name, target name, bounded bytes and an exact boolean replacement selector. A root operation permits
only `profile.header` with replacement disabled. The identity directory permits only
`<64-lowercase-hex>.aesgcm`, with create-only or cooperative replacement. Pending names remain
`pwp-pending-` plus 32 lowercase hexadecimal characters. The future managed adapter must generate
those names from its cryptographic random source; the native API does not derive them from payloads,
introduce a weaker RNG, or retry a name collision. Syntax, bounds, actual scope and original lease
generations are validated before allocating or copying the payload.

One native admission retains the exact root/identity, profile/vault and prepared candidate originals
through this sequence:

```text
prepare persistent candidate + file flush + exact byte/EOF readback
→ create-only publication or cooperative replacement + file flush/readback
→ original candidate/grant verification
→ original parent NTFS metadata/storage synchronization
→ original candidate/grant verification
→ exact original candidate retirement
```

No internal step reacquires the native gate. Existing public preparation, rename, replacement and
directory-sync wrappers retain their original argument/admission/result behavior; private held-gate
helpers accept the single captured grant rather than substituting newer lease generations. The
candidate token never escapes this composite JNI call. An immediate subsequent `fileIdentity` or
`read` therefore observes an ordinary released record after success, rather than colliding with a
still-held candidate. Only successful publication, synchronization, final verification **and actual
candidate close** can report successful record write.

The shared controller adopts every valid nonzero preparation result, including a late owned token
returned with an error. Ordinary preparation failures returning zero already performed their own
cleanup and are not closed again. A successful preparation without a valid owner, an invalid result
code, or an invalid nonzero token instead seals the session; no raw handle is guessed or reconstructed.
Pre-publication safe refusal preserves the original error and closes only the prepared owner, leaving
any pending file. There is no pathname cleanup, rollback or automatic promotion.

Once publication succeeds, **every** later failure is `CleanupUnknown`, including a directory-sync
admission/preverification refusal that never entered the OS flush. The memory-only uncertainty
callback marks the still-live candidate `UNCERTAIN` and seals the session **before** its actual close.
The original close still runs once even when ownership is poisoned; uncertainty keeps that owner
quarantined even if Windows closes it successfully. A close failure similarly outranks a prior safe
error or an otherwise successful write. Neither path reads a retired entry, retries a numeric handle,
releases a granting lease early or prevents independent reverse terminal cleanup.

Twenty-eight portable groups execute the actual record, rename, sync and owner controllers, including
late preparation owners, missing/invalid owners, result and phase matrices, reentry, exact grant
generations, pre/post-sync failures, cleanup precedence and retained independent quarantine. The
real Windows smoke source adds empty/one-byte/maximum identity insertion and replacement, distinct
file IDs, immediate readback, immutable-header collision preservation, unsafe-target refusal,
same-admission reentry and absence of leaked candidate dependencies. It preserves the earlier
low-level successful header publication; testing a **successful composite first header insertion**
requires a separate fresh-account fixture, not deleting or resetting that immutable header.

Those native controls remain unexecuted, and crash/durability behavior has not been qualified.
This write operation does not itself perform bootstrap or deletion; ABI12 separately composes
expected-ID deletion below and ABI13 adds fixed namespace creation acknowledgment above.
Pending-record recovery policy, full lock orchestration, secure DLL loading,
actual Windows terminal-watchdog qualification, installed application wiring and the complete
`WindowsProfileNativeApi` adapter remain required. Capability `0x43`
and both closed full-provider availability flags remain unchanged.

## Single-admission expected-ID deletion (ABI12, not a complete profile provider)

`deleteRecord(directory, name, expected)` calls `pwp_win_delete_record` and returns void only on
successful completion of the entire boundary. One native admission retains the original directory
handle, directory identity and exact profile/vault grant generations. A bounded six-word expected
file-identity snapshot is validated before mutation and cleared on every admitted return. It is not
an IP/name-based identity, expected-ID comparison on a different handle, or a best-effort pathname delete.

1. Open a fresh exclusive unpublished original file under the held parent. Reverify its exact expected
   ID, private security, one link and normal state, mark deletion intent, read back pending state on the
   same handle, and physically close it once. Live leases/candidates are never borrowed or unlocked.
2. After successful original retirement, reserve a separate probe and issue a read-only relative
   `NtCreateFile(FILE_OPEN)` under the same original parent. **Only final
   `STATUS_OBJECT_NAME_NOT_FOUND` (`0xc0000034`) plus an exactly NULL returned handle** can establish
   the absence required here. `STATUS_OBJECT_PATH_NOT_FOUND`, DOS-error aggregates, access/sharing
   denial, pending, success-without-handle and non-NULL invalid sentinels are not absence.
3. Retire the probe reservation, including exactly one actual close for any valid unexpected returned
   handle—even when its status is an error. Invalid sentinels are never attached/closed. Freshly verify
   the original parent/grants after probe retirement; its owner slot may already have been reused.
4. Synchronize the retained original NTFS directory with `NtFlushBuffersFileEx`, including existing
   access/custody/grant checks before and after flush. Reverify the captured parent before returning.

For nonpending `NtCreateFile` completion, the returned NTSTATUS is authoritative; this does not impose
an undocumented equality requirement on failure `IO_STATUS_BLOCK.Status`. See Microsoft's
[NtCreateFile contract](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntcreatefile)
and [IO_STATUS_BLOCK return-status guidance](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/ns-wdm-_io_status_block).
The original handle is synchronously opened, and no alertable callback or native-gate reentry is introduced.
Portable `STATUS_PENDING` cases prove refusal classification, not asynchronous-I/O cancellation or
late-completion cleanup. Changing the synchronous local-NTFS contract would require separate owned completion.

A safe pre-intent missing target still returns `NotFound` **as an error**, never success or `false`.
The existing `requestExpectedFileDeletion` primitive remains intent/readback/retirement only, with its
old missing-error contract intact. Once intent/close succeeds, every non-absence or sync failure is
`CleanupUnknown`, including a later `NotFound`/policy failure from a different step. The memory-only
seal changes session/owner authority; it never reads or recloses the retired source or a reused slot.
Independent original owners still receive their normal reverse terminal drain. There is no retry,
path cleanup, recovery, grant substitution or assumption that failed deletion was rolled back.

Twenty-eight portable groups use the actual shared delete-intent, strict-absence, directory-sync,
role and owner controllers with synthetic syscall callbacks. They cover wrong IDs, every transition,
raw status/handle classification, slot reuse, post-intent failure precedence, reentry and independent
exact-once cleanup. Twelve new groups in the actual-JNI/mock-backend harness cover the exact six-word
copy, unsigned high bits, code7/code8 propagation, old/new entry separation, bad input, pending VM
exceptions and error-reference cleanup. The test-only wipe observer calls the real wipe and checks
its bytes while the fixed stack copy is still live—not a captured pointer after JNI returns.

The native smoke source creates one explicitly declared synthetic ordinary identity record, checks
wrong-ID and missing-authority refusal, deletes only that record through this boundary, then checks
immediate absence, missing-error repetition and original parent/lease preservation. It does not delete
or reset the immutable header, fixed locks, canonical directories or other retained candidates.
**Current ABI13 Windows smoke is NOT_EXECUTED.** These source/controller results are not an NTFS
power-loss test, complete lock/bootstrap durability, full adapter, secure loader, pending-state recovery
or installed-MSI qualification. Capability `0x43` and both complete-provider availability flags stay closed.

## Original-directory NTFS metadata synchronization (ABI9)

`syncDirectory` calls `pwp_win_sync_directory(uint64_t)` on the original registered directory handle.
Only the canonical private profile root and its canonical `identity` child are admitted. Root requires
the current native profile lease; identity requires that profile lease and the current native vault lease.
It is not a public pre-lease bootstrap operation. ABI13 creation paths use a separate private fixed-scope
finalizer above; no caller may borrow that provisional authority for an arbitrary synchronization.

The root and canonical identity are opened once with their existing read/control/traverse/synchronize
rights plus `FILE_ADD_FILE` (the directory-specific bit corresponding to `FILE_WRITE_DATA`). Their
sharing remains `FILE_SHARE_READ`, with no write/delete sharing. ABI13 also acquires these rights initially
for its fixed original LocalAppData/P2pKit bootstrap owners. Other ancestors, noncanonical child
directories, files and read-only probes keep their previous masks. This stricter original-handle access
can reject another opener earlier than the profile-file lock; it does not grant a second profile owner.
There is no access upgrade through close/reopen, `ReOpenFile`, generic access, impersonation or privilege.
`NtQueryInformationFile(FileAccessInformation)` reads back the exact granted mask on that original handle
at admission and around every synchronization. Missing, additional or unqueryable rights fail closed.

Each call captures exact role generations, verifies pinned NTFS identity, owner/protected DACL, streams,
case-insensitive directory policy, canonical path, noninheritability and access rights, then issues
`NtFlushBuffersFileEx(handle, 0, NULL, 0, &io)`. It accepts only synchronous success and re-verifies custody
and grants afterward. Zero flags are intentional: data-only/no-sync flags, volume handles, elevated
fallbacks and a successful flush of some other file are not equivalent. No payload is allocated or copied.

The documented basis is [MS-FSA section 2.1.5.7](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fsa/0de7dc40-9627-437e-a4df-c4696cdc3d02):
a `DirectoryFile` flush persists its metadata and the directory structure to stable storage, then flushes
the underlying storage. [Product note 80](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fsa/4e3695bd-7574-4f24-a223-b4679c065b63#Appendix_A_80)
limits the directory-structure implementation to **NTFS**; other filesystems can report success without
that action. [NtFlushBuffersFileEx](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntflushbuffersfileex)
documents zero-flag metadata/storage synchronization and rejects handles without write/append access.
These contracts justify this primitive, not claims about an unexecuted Windows target or device's behavior.

The portable controller performs verify → one flush → verify. A preverification failure issues no flush.
Once the flush was entered, either flush failure or postverification failure becomes `CleanupUnknown`
and seals the session. The directory remains a **live original owner** until physical close actually runs.
Its uncertain synchronization state stays quarantined even if that one OS close succeeds; no later close
retries the numeric handle. Other independently owned resources are still drained in reverse order.
An ordinary success permits a separate later synchronization; an uncertain operation is never retried.

Fifteen portable controller/access/ownership groups exercise argument and granted-mask rejection,
ordering, stale grants/identities, reentry, all uncertainty boundaries and exact-once independent cleanup.
The real Windows smoke source additionally asserts role-denied cases, root/identity success, repeated
independent synchronization, post-rename synchronization and closed-session refusal. These assertions
still require authorized native execution; portable tests do not prove Windows access, NTFS sharing,
storage behavior, interrupted transactions or recovery.

The primitive does not change candidate states into committed records, perform replacement/deletion,
sync all bootstrap ancestors, introduce recovery, or implement `WindowsProfileNativeApi.write`.
The partial capability mask remains **`0x43`** and both full-provider availability flags remain false.
ABI9 introduced this primitive with twenty JNI exports. The current ABI is 13/23 exports;
neither ABI checks nor a directory flush
substitute for the remaining full transaction, secure loader, packaging and runtime qualification work.

## Cooperative identity-record replacement (ABI10, not a complete write)

`replaceCandidate` invokes `pwp_win_replace_candidate` for a verified persistent candidate under the
canonical identity directory. Only `<64-lowercase-hex>.aesgcm` targets are admitted. `profile.header`
remains create-only; lock files, stage/pending names, other directories and borrowed/public owners are
never replacement targets. The exact original candidate, pinned parent and granting profile/vault
leases remain held throughout. This implements cooperative serialized replacement, consistent with
`WindowsProfileNativeApi.write(..., replace = true)`; it is **not** an expected-ID compare-and-swap
against compromised same-user code. Expected-ID deletion remains a separate unchanged operation.

For an existing target, the implementation opens one fresh, unpublished, read-only, **share-none**
handle relative to the pinned identity directory. It requests no write, DELETE or lock-file rights.
The actual file must pass NTFS, regular-type, one-link, no-reparse/ADS, bounded-size, original-ID/path,
noninheritability and protected user+SYSTEM owner/DACL checks. Its file ID must differ from the
candidate's. Unsafe targets fail without repair, truncation or rename. The exclusive validation probe
is the **only** handle retired before the namespace operation; no candidate or lease is released.

The portable controller's ownership-transfer point is explicit. Before transfer, malformed inputs
leave probe cleanup to the native caller. After transfer, every path closes that exact probe once,
including source/target verification refusal. Uncertain close poisons ownership and prevents rename.
After a successful probe close, fresh verification checks the original candidate and exact granting
roles again. It does not read the probe's retired entry or reuse its OS handle; that registry slot may
already have been reused by source verification. Native admission remains serialized throughout.

An exact missing-file result selects the existing create-only mode (`ReplaceIfExists = FALSE`), so
first insertion through `replace = true` works without a separate mandatory pre-existing record.
An admitted existing target selects classic `FileRenameInformation` with `ReplaceIfExists = TRUE`.
Both use the original candidate handle, NULL `RootDirectory` and a simple basename for its own
directory. Neither path retries another mode after failure, relaxes sharing, uses POSIX rename flags,
reopens the source, or falls back to a pathname API. Cooperative locks, not an atomic destination-ID
comparison at rename, are the concurrency boundary.

After rename, original-candidate identity/security/size readback, file flush and another readback must
all pass. Only then is its observed path updated; it remains `RENAMED`, not an ordinary committed
record. Any failure after namespace-attempt entry becomes sticky uncertainty and retains original
ownership until actual close. Pre-attempt controller failures are terminal `FAILED` with no rename.
Owner quarantine and independent reverse cleanup remain unchanged. ABI11 composes this primitive
with directory synchronization and exact candidate retirement; recovery and the full managed `write`
adapter remain separate work. Capability and production-availability gates are not enabled here.

Twenty-four portable controller/ownership groups exercise name/scope rejection, transfer boundaries,
published/stale/borrowed probes, empty/maximum payload sizes, exact sequencing, create-only absence,
failed target verification/close, stale grants, probe-slot reuse, reentry, all post-attempt failures and
retained candidate/lease ownership. They execute no Windows syscalls. Real smoke controls additionally
assert first insertion, different-size replacement/new file ID, held-owner collision refusal, unchanged
header behavior, synthetic unsafe target identity/byte preservation, exact-handle readback that its DACL
remains unprotected, and original-handle cleanup. The test-only fixture uses create-new Win32 I/O in the
declared disposable account, not a production metadata/mutation fallback; it is never deleted or repaired.
Those new controls still require source-matched MSVC compilation and authorized Windows runtime;
no native execution, crash, installed-MSI or full RPC qualification is implied.

## Create-only candidate rename (not durable commit)

`pwp_win_rename_candidate` advances a **verified persistent candidate** to a new name within its same
directory. It rejects disposable stages and every alternate scope. Only root `profile.header` and
identity `<64-lowercase-hex>.aesgcm` destinations are admitted. The exact native owner, pinned parent,
prepared byte count, file ID and original profile/vault grant remain bound across the operation.
The handle and grant remain owned after success so later transaction work can retain that custody;
this operation does not itself supply such a transaction or enable the complete `write` API.

An already observed destination causes an early read-only refusal, leaving the prepared candidate
unchanged. That observation is **not** an absence reservation: the actual classic native
`NtSetInformationFile(FileRenameInformation)` call uses `ReplaceIfExists = FALSE`, a NULL
`RootDirectory`, and a strictly simple filename. Under the native API this means the source file's
own directory, not process-CWD/Win32 pathname normalization. No alternate parent, replacement,
extended/POSIX rename flags, temporary unlock, parent reopen or sharing/access relaxation is used.
The source already owns DELETE access; the fixed native structure is completely zeroed, its AMD64
offsets are asserted, and its advertised buffer covers the documented structure-plus-name bound.

Authoritative contracts: [native rename information](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information),
[native set-information operation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntsetinformationfile)
and [I/O request target-parent semantics](https://learn.microsoft.com/en-us/windows-hardware/drivers/ifs/irp-mj-set-information).
These document the simple-name/same-directory route. They do not establish this source's Windows
SDK compilation, NTFS/filter/share behavior, supported Windows build floor or crash durability.
Native errors remain failures; there is no fallback to a different API, sharing mode or target path.

Before rename, the original handle is verified against its old path, identity, ACL and prepared size.
After the syscall, that **same handle** is verified against the proposed target path, file-flushed and
verified again. Only then is the stored observed path updated and the phase changed to `RENAMED`.
That phase still refuses normal-record metadata, reads and inventory while the owner is live; repeated
rename is refused. Only ordinary owner retirement subsequently allows independent read-only observation.
A successful file flush is not a durable directory-entry acknowledgment or a completed profile write.

Invalid target arguments and early destination refusal do not consume a verified candidate. An admitted
source-verification failure changes it to `FAILED` without a syscall or retry. Any syscall, postcheck or
post-rename flush uncertainty instead becomes sticky `UNCERTAIN`, seals the session and retains its
original role dependencies. Explicit or terminal close still calls `CloseHandle` **once** on that original
resource, but reports failure/quarantines the owner even if the physical close succeeded. This prevents
an ambiguous publication from turning into a clean close or losing its grant evidence; repeated close
never retries the potentially reused raw Windows value. Root drain still attempts independent owners.
No pathname deletion, rollback, retry, record replacement or recovery is performed.

Portable controls execute the shared phase/target/close-result controller and actual ownership ledger
with synthetic resources. The real Windows smoke source adds successful header/encrypted-record-name
publication, strict scopes, stage rejection, read-only collision preservation, blocked live metadata and
grant retention. It remains **NOT_EXECUTED**, not Windows execution evidence. Crash recovery,
durable replacement/deletion, complete adapter/loader/application integration and native qualification
remain required. This primitive originally landed in custody ABI8; current ABI13 retains capability `0x43`
and the closed complete-provider gate.

## Persistent candidate preparation (not a transaction)

`pwp_win_prepare_record` is the first persistent-record preparation primitive. Custody ABI8 exposes it
as `prepareRecord` and exposes `pwp_win_rename_candidate` as `renameCandidate`; neither is connected to
`WindowsProfileNativeApi.write` or advertises an additional capability. The eventual header create and
encrypted-vault replacement can prepare a candidate with it, but still need a separately implemented
commit/recovery boundary.

Before allocating/copying input it admits the exact root/profile or identity/profile+vault role grant,
fresh directory custody, bounded handle capacity, a `pwp-pending-` plus 32 lowercase-hex component and
at most 262,144 bytes. Random candidate names must come from the caller's secure random generator;
the name validator proves syntax, not randomness. Handle-relative `FILE_CREATE` with a protected
user+SYSTEM DACL and zero sharing refuses any collision; it never opens, truncates or adopts the old
object. The original opaque handle has read/write/delete access for future same-handle publication,
but this operation never sets deletion disposition or invokes rename.

Unlike `pwp-stage-*`, this file has **no `FILE_DELETE_ON_CLOSE`**. It is a persistent pending object,
not a durable or committed record. The shared controller verifies the initial empty file, writes with
bounded positive progress, flushes the file, reverifies custody/size, rewinds the original handle and
reads back every byte against the still-owned input. A final read must prove EOF and a final independent
custody/size check must pass. Readback uses one 4-KiB scratch buffer, cleared after every chunk and exit;
writes are at most 64 KiB. The input copy remains inside the existing admitted bounded-buffer owner.
Zero-length input still requires flush, rewind, EOF and metadata verification. No I/O callback, including
flush or close, acquires a pretend coroutine deadline or becomes native-cancellable through this code.

The returned candidate retains the exact granting profile/vault generations using the existing pending
owner dependency ledger; that ledger controls retirement, not deletion. Ordinary record metadata, reads
and directory-list publication refuse a live candidate. Independent profile/vault/directory close is busy
while a dependent candidate is owned. Explicit candidate close or terminal root drain closes only its
original handle, once, and **leaves the file**. A failed prepare can also leave a partial/new candidate.
Cleanup uncertainty still seals/quarantines ownership; successful handle closure is not rollback or
namespace durability. No pathname deletion, automatic retry, stage promotion or implicit recovery exists.
After close, read-only custody may observe a retained pending file; its name/content is not a commit
marker, permission to reuse it, or an application profile record.

The maintained portable candidate controls exercise the actual shared fill controller, not Win32.
The real-Windows smoke source now includes candidate boundaries, role rejection, copy-failure-before-create,
live-record refusal, collision preservation and retained bytes after ordinary/terminal close. That source
is still **NOT_EXECUTED**. No NTFS persistence, Windows runtime, power-loss recovery, installed
DLL loading or RPC behavior has been established by these changes. Atomic publication/replacement,
namespace durability and expected-ID deletion now have separate composed source boundaries below/above;
ABI13 separately acknowledges fixed bootstrap/creation. Full recovery, adapter integration and native
qualification remain unfinished engineering.

## PE structural admission prerequisite

`WindowsProfilePeImage` checks a private, at-most-32-MiB snapshot: AMD64/PE32+ DLL headers, ASLR/NX,
nonoverlapping raw and mapped sections, file-backed RVA bounds, exact versioned JNI exports, bounded named
imports from the explicit Windows-system allowlist, and certificate-table framing. It rejects CLR, delay/bound
imports, forwarders, executable+writable sections, unbounded strings, unknown overlays and ordinal imports.
The returned SHA-256 identifies that exact snapshot. Certificate-table presence does **not** validate
Authenticode, an installed path, filesystem ownership, DLL dependency resolution or Windows execution.
Synthetic parser fixtures never become native artifacts or runtime qualification receipts.

Run the focused JVM tests through the repository's existing offline/strict Gradle environment:
`:p2p-sample-rpc:jvmTest --tests dev.p2pkit.sample.rpc.profile.WindowsProfilePeImageTest`.

The directory decoder consumes `FILE_ID_BOTH_DIR_INFO` chains using byte reads, strict 104-byte header/UTF-16
name bounds, aligned forward offsets, the 96-character profile component policy, and ASCII-case duplicate
rejection across all batches. It ignores short aliases and skips only exact validated `.`/`..` entries.
Buffers are zeroed before every Windows query. A final zero next-offset permits at most seven alignment
padding bytes; all remaining bytes must remain zero. This is a conservative accepted-buffer policy, not a
claim that Windows reports a bytes-used value. Failure clears the whole aggregate. Actual SDK field offsets
are compile-time asserted, but Windows compilation and runtime behavior remain unverified on this Mac.

Enumeration is a bounded set of checked names, **not** an atomic namespace snapshot or retained member-handle
authority. Later operations must re-open and verify custody. Metadata for an existing share-none lease uses
that exact already-owned file handle after fresh identity/security readback; it never unlocks/reopens the lease.

Every admitted directory, including pinned KnownFolder ancestors, must return a successful
`FileCaseSensitiveInfo` query with **Flags == 0** on its exact held handle. Fresh directory verification
repeats this check. Case-sensitive directories, unknown flags and unavailable/failed queries are rejected;
no directory setting is changed and no fallback assumes case insensitivity. This precondition is necessary
before ASCII-folded path/owned-file matching: an owned `alpha` must not satisfy a distinct `ALPHA` in a
case-sensitive directory. Enumeration duplicate detection alone cannot protect direct metadata operations.
Two portable control groups check the shared flag policy and this folded-alias admission model; they do not
execute NTFS lookups. Real Windows SDK/runtime checks must prove supported-query behavior for ancestors and
private directories, refusal of case-sensitive/case-alias fixtures, and fresh rejection after a mode change.
The DLL ABI, imports, capability mask and closed complete-provider gates are unchanged.

### Intended real Windows compilation (not executed here)

From an existing **x64 MSVC Native Tools** prompt with a real Windows SDK and `JAVA_HOME` pointing at JDK17:

```bat
samples\p2p-sample-rpc\native\windows-profile\build-windows.cmd C:\new-owned-output
```

This create-only recipe compiles the three actual C translation units, uses `/MT` static CRT, and links only
the listed Windows system libraries. It requests x64, C11, warnings-as-errors, stack/SDL/CFG protections,
ASLR/high-entropy VA/NX, and embedded manifest. The PE verifier must independently confirm the real resulting
DLL's headers, actual imports and current twenty-three exports; compiler flags are not that evidence. Verify Authenticode,
source/ABI/hash provenance, secure installed placement and runtime behavior separately. The recipe is not
attached to distributions and does not replace the still-missing existing-MSI signing/staging integration.

Required Windows runtime controls include metadata/existence/enumeration while the same session owns a
share-none profile lock: prove the exact original lease remains held, no temporary unlock occurs, failed
member/lease cleanup is retained, and no returned directory list is mistaken for a namespace snapshot.

## Disposable staging prerequisite (not a transaction)

`stageRecord(directory, name, ciphertext)` accepts only `pwp-stage-` plus exactly 32 lowercase hexadecimal
characters and at most 262,144 encrypted-record bytes. The caller must supply an independently generated
name; its shape alone is not entropy evidence. Native `FILE_CREATE` refuses collisions instead of opening,
truncating or replacing an existing record. The original handle is reserved before allocation and opened
relative to the pinned parent with the protected user+SYSTEM DACL, no sharing, and `FILE_DELETE_ON_CLOSE`.
No JNI/managed entry point can rename this disposable stage or remove its delete-on-close intent.

JNI copies the bounded input only through the admitted native source callback described below.
The C controller clears and frees its owned copy before releasing native admission on every exit. Partial writes must make positive bounded progress;
zero/oversized progress, write/flush errors and original-ID/security/size readback failures prevent token
publication. `FlushFileBuffers` proves neither a durable parent entry nor a recoverable commit graph.
The stage token represents **uncommitted, disposable** bytes, never a successful profile write.

`discardStage`, normal `close(stage)`, and session/root close all retire the same original handle. Checked
file-disposition marking and delete-pending readback precede `CloseHandle`; no cleanup performs path-based
delete or reopens an existing target. Before metadata validation succeeds, only the exact handle returned
by successful `FILE_CREATE`/`FILE_CREATED` is eligible for disposition. Delete-on-close is set at allocation
also for unpublished/failed stages. If marking or closing is uncertain, the token remains quarantined and
admission stays poisoned; independent close is attempted once, not retried or converted into success.
Successful session retirement discards stages before their parent handles. This is handle-release and
delete-disposition intent—not a claim of physical secure erasure or crash/power-loss namespace durability.

The maintained portable runner also executes nine staging contract groups with ASan/UBSan: strict names,
partial/empty/full writes, pre-call bounds, failed progress/write/flush/post-readback, in-flight/repeated
retirement, independent delete/close failures, integration with the same token quarantine registry, and rejection of every stage phase from ordinary metadata.
These callbacks test shared control logic only. Actual Windows controls still must exercise `FILE_CREATE`
collision behavior, delete-on-close visibility and disposition, same-handle identity/ACL readback, full disk,
process/power interruption, cancelled/failed I/O and root retirement with live/unpublished stages. The actual
Win32 translation unit has not been compiled or run on this Mac; no Windows success is inferred.

A complete durable provider still needs a reviewed conditional-replacement/expected-ID transaction and
namespace recovery recipe, producer/installed-DLL trust, and actual terminal-call qualification. The disposable
stage is intentionally not connected to `WindowsProfileNativeApi.write`, and the capability mask, complete
adapter ABI and production availability gates remain unchanged.

Disposable stages are not normal records: their internal identity tuple carries **zero** normal-policy flags,
and neither `identity(stage)` nor ordinary `fileIdentity`/`exists`/`names` may publish stage metadata. A live
owned stage name makes these ordinary observations fail closed, rather than hiding the stage or temporarily
reopening its share-none handle. Ordinary `read` and `lockExisting` also reject a matching owned stage before
opening it. Only stage fill/discard uses its separate original-handle checks; no standard `0x2ff` identity is
fabricated for an object permitted to be delete-pending.

## Byte-manifest authorization prerequisite (not native loading)

`WindowsProfileByteManifest` supplies a private **component** manifest encoder and bounded byte authorizer;
it does not replace the existing Desktop/MSI release manifest, installer or publishing pipeline. A future
existing-app producer may pin this component's manifest digest inside its independently admitted parent
application/provenance metadata. No producer task, resource extraction or runtime loading is enabled here.

The encoder accepts externally established clean source/commit/tree values and a bounded DLL snapshot,
requires the existing PE structural policy, then emits canonical ASCII/LF fields in one exact order:

```text
schema=1
component=windows-profile-custody
abi=9
platform=windows
arch=x86_64
source=<40 lowercase hexadecimal characters>
tree=<40 lowercase hexadecimal characters>
clean=true
file=p2pkit-windows-profile.dll
bytes=<canonical decimal length>
sha256=<64 lowercase hexadecimal characters>
capabilities=0x43
```

`authorize` requires an independently supplied parent-authority triple: exact manifest SHA-256, source
commit and tree. It rejects manifests larger than 4,096 bytes; duplicate, reordered, extra or missing fields;
non-ASCII/CRLF/alternate spellings; different schema/ABI/platform/architecture/capability or filename;
and source, DLL length/hash or structural-PE mismatches. Jointly changing the DLL and adjacent manifest
cannot redefine an existing parent pin. No API derives that external authority from the candidate sidecar.

The returned immutable `BYTE_MANIFEST_ONLY` observation contains no load path or executable bytes. Certificate
framing is explicitly not Authenticode verification. The encoder does not inspect Git, establish clean
filesystem custody, sign a file, prove the compiled native `abi()` result or supply Windows runtime evidence.
Its `clean` input must originate from the existing reviewed build process, not a user-provided assertion.
For a signed distribution, independently verify final DLL signing **before** producing/pinning its final
manifest; do not repair/update a mismatched manifest during loading.

A future secure loader still must establish installed app-owned path/ancestor/handle custody without a
circular dependency on this untrusted DLL; verify publisher/chain/timestamp and safe dependency resolution;
keep exact file identity through loading; and validate real native ABI/source/capability behavior before
publishing any provider. No signature/custody check is skipped and no global search path is introduced by
this byte-only prerequisite. All complete-provider admission flags remain unchanged and closed.

Sixteen deterministic producer/parser controls use the shared synthetic PE fixture (never executed).
Run them with `:p2p-sample-rpc:jvmTest --tests dev.p2pkit.sample.rpc.profile.WindowsProfileByteManifestTest`.


## Historical new profile-lock custody prerequisite (ABI4)

This section records the original ABI4 file-only predecessor. Current creation follows the additional
ABI13 file/parent acknowledgment above; `pwp_lock_finish` itself remains file-only for existing leases.

`createProfileLock(root)` accepts only the already-admitted session root and the fixed component
`profile.lock`. It uses handle-relative `FILE_CREATE` with the private user+SYSTEM DACL at creation,
`READ_DATA | WRITE_DATA` access and **zero sharing**. A collision fails: this operation never opens,
truncates, deletes, repairs or falls back to an existing record. No caller-provided filename is accepted.
The original handle is reserved before allocation and remains owned throughout validation/publication.

The returned opaque token represents the still-held **exclusive handle lease**, not merely an existing
empty file. No other process can acquire a conflicting read/write/delete open while this share-none
handle remains held. This matches the existing `lockExisting` custody contract; no byte-range lock or
complete durable profile-lock capability is claimed. The complete adapter remains unavailable.

Publication requires fresh root and file identity/security/custody readbacks, a zero-length ordinary
file, successful `FlushFileBuffers` on that same handle, and another complete readback. The shared
portable controller publishes only after all checks. Normal/session close releases the original handle
exactly once; failed close is quarantined and poisons further admission. Any failed unpublished operation
retires only its original owned handle. A newly created empty file **may remain after failure**, intentionally:
there is no pathname deletion, unsafe retry, automatic repair or claim of a rolled-back namespace mutation.
Explicit later `lockExisting` remains separately authorized/admitted, never an implicit failure rescue.

The file flush is not proof of durable parent entries, crash recovery or conditional expected-ID replacement.
ABI revision 4 changes the partial custody/export inventory, not the `0x43` capability mask or the complete
provider's ABI/qualification gates. It does not add a loader or connect this operation to production storage.

Eight portable callback-control groups cover exact verify/flush/verify/publish ordering and held ownership;
pre-admission argument checks; first/final readback and flush failures; cached uncertain close/quarantine;
republication/stale tokens; handle limits; and poisoned admission. They exercise the controller called by
actual Win32 source, but do **not** simulate `NtCreateFile`, sharing, NTFS, ACLs or file durability.
The maintained `check-portable.py` includes these ASan/UBSan controls plus the existing policy/stage suites.

The real Windows x64 SDK/runtime gate must prove cross-process share exclusion until lease close;
FILE_CREATE collision preserving pre-existing bytes/security/identity; no inherited handle; exact protected
DACL/readback; alias, hard-link and reparse/root substitution rejection; full-disk/flush failures;
retained close uncertainty; and the documented stranded-empty-file behavior. Those Windows checks have
not run on this Mac. Existing SDK/build/signing/installed-MSI and durable transaction boundaries remain open.

## Expected-ID deletion intent prerequisite (not a durable delete transaction)

`requestExpectedFileDeletion(directory, name, expected)` accepts exactly the normal six-word FILE tuple:
wire version1, nonzero **unsigned/raw 64-bit** volume, nonzero 128-bit file ID, flags `0x2ff`, link count1.
The selected parent is freshly verified, must be a public protected directory on that same volume, and
must satisfy the existing case-insensitive namespace rule. Current ABI8 additionally restricts mutation
to the role-admitted root/identity scopes above. Owned lock/stage leases cannot be borrowed.
Missing targets fail with `NOT_FOUND`; they are not treated as successful deletion.

The implementation reserves ownership before a relative `FILE_OPEN` with `DELETE` access and share0.
It neither creates/truncates a target nor releases another lease. Under the existing serialized gate,
the shared controller marks this **unpublished original handle** retiring before running any callback.
Fresh normal ID/ACL/path/link/parent checks must match the expected tuple before `FileDispositionInfo`
sets deletion intent. The same handle then receives full pending-mode ID/ACL/path/link/parent readback
plus explicit `DeletePending`. Pending metadata has internal flags0, never the normal `0x2ff` claim.
The exact original handle is then closed once; there is no pathname delete, scan or repair fallback.

A pre-mutation mismatch closes only that handle and never marks deletion. After a mark attempt,
uncertain mark/readback/close poisons the context and quarantines the original ownership record, even
if `CloseHandle` reports success. Root close retains that uncertainty and never physically retries the
quarantined value. If close succeeded, the retained numeric resource is diagnostic custody, not a claim
that an OS handle remains live. Success means **checked deletion intent and handle retirement only**: it does not
assert name absence, directory durability, crash recovery or an atomic durable profile transaction.
No call is wired into full `WindowsProfileNativeApi.delete`; capability `0x43` and production gates stay closed.

Eleven portable groups exercise the shared controller: exact order/ownership; malformed tuples and high-bit
volume/IDs; invalid callbacks/tokens; borrowed published leases; preverify rejection; uncertain mark,
pending-readback and close; poison before/after mutation; stale-token/no-retry behavior; and rejected reentry from every callback. These are
**not Windows executions**. Actual x64 SDK/runtime tests must additionally prove missing/wrong/hardlinked,
reparse/case-sensitive/cross-volume/owned-stage/lock/directory rejection without mutation, same-handle
postmark metadata availability, share0 exclusion, and retained errors on every OS boundary. If Windows
cannot support the required readback, this primitive must fail closed—not weaken its assertions.
ABI5 adds the entry point without enabling the incomplete provider or claiming namespace durability.

## JNI bulk-buffer admission and retirement

`stageRecord`, `read` and `names` no longer allocate their bulk native buffers in JNI before attempting
native admission. Their private C calls take synchronous source/receiver callbacks instead. The existing
Win32 `begin()` gate and fresh protected-directory/component checks precede bulk allocation; staging also
checks its public-handle limit before copying. Busy, closed and poisoned admission never invokes a callback
or allocates these bulk buffers. Later native reservation or OS failures can occur after allocation, but
remain inside that single admitted owner; no new global lock, queued work or admission bypass is introduced.

The shared `pwp_buffer_apply` controller allocates one zero-initialized buffer of at most 262,144 bytes,
invokes the synchronous operation, and clears/frees that buffer before the Win32 gate is released. Empty
record operations need no native allocation. Directory inventories fit the same bound. Staging's source
callback copies the Java ciphertext before attempting file creation; source-copy failure therefore cannot
create a stage. Read and inventory receivers create/copy their Java results while the native owner is still
held, after actual file/member custody cleanup. Partial Java result/local references are retired on receiver
failure before releasing that owner. JNI pending exceptions remain primary and do not skip C buffer cleanup.
Successful returned Java arrays belong to the caller; Java heap physical erasure or prompt GC is not claimed.

Callbacks cannot retain native buffers, re-enter the provider or unwind across C. The JNI callbacks check
exceptions and return an error normally. Existing bounded component-string views and fixed diagnostic Java
objects may still be created outside native admission: the guarantee concerns **bulk payload/inventory
buffers**, not every allocation. Custody ABI5, its fifteen JNI exports, capability `0x43`, and the complete
provider/qualification gates are unchanged. No DLL is loaded or production storage enabled.

The portable command adds four real shared-buffer lifecycle groups and nine groups linking the actual JNI
translation unit against a fake JNI vtable/backend. They cover pre-admission rejection without copies,
success/empty operations, allocator failure, native-operation failure, source/receiver bounds, nested busy
attempts and seven pending-JNI-exception boundaries. Test-only libc hooks observe that all native buffer
bytes are zero and the modeled owner is still admitted at free; failed Java local references are retired
before the modeled gate ends. These tests exercise real C controller/JNI code, **not a JVM, Win32 SRWLOCK,
Windows SDK build, NTFS operation, or installed runtime**. Actual Win32 gate placement is source-reviewed
here and must still be compiled and verified with the required Windows runtime controls.

## Historical protected child-directory custody creation (ABI6)

This section records the ABI6 predecessor. Current new identity creation uses ABI13's child-self/root
acknowledgment and sticky postcreation uncertainty. The old custody-only controller remains for existing opens.

The original ABI6 `createChildDirectory(parent, name)` primitive created one new directory below an
already-held public private directory. Current role hardening restricts it to `root/identity` under the
native profile lease as specified above. Existing `child(parent, name)` continues to **open only**; neither method rescues the other's
failure. Input/token, component, parent-identity and handle-capacity checks run before creation, under the
same nonqueued native gate. The relative `NtCreateFile` call installs the protected user+SYSTEM DACL at
`FILE_CREATE` and requires `FILE_CREATED`. Existing files, directories and aliases are never adopted,
truncated, replaced or repaired on collision.

Before publication, the original parent and new child handles receive fresh identity/security/path/case
readbacks. Both must be private one-link directories on the same nonzero volume, with distinct nonzero
file IDs; high-bit volume/file IDs are compared as raw unsigned bits. Successful publication returns only
the original opaque child handle. Failed verification/publication closes only that handle. Cleanup errors,
including a failed security-descriptor release, remain `CLEANUP_UNKNOWN`; failed closes are quarantined
without retry. Session retirement retains the existing child-before-parent ordering.

A newly created directory **may remain after failure**. No rollback, emptiness, safe reuse or durable
namespace creation is established. There is no directory flush, pathname deletion, automatic reopen or
complete-provider wiring. Custody capabilities remain `0x43`, and both full-provider availability gates
remain closed. Complete durable persistence still requires its own implementation and Windows evidence.

Ten portable child-controller/identity groups cover exact lease publication, malformed parent/child
tuples, bad arguments, verification failure, close quarantine, poison, public capacity, publication
failure, stale tokens and reverse session retirement. Five additional actual-JNI/mock-backend groups
cover bounded forwarding, balanced string release, failure without open fallback, pending exceptions and
the ABI6/partial-capability boundary. PE and byte-manifest tests require the new exact export inventory
and reject prior ABI5. None of these controls executes Windows SDK, DACL, NTFS or installed-MSI behavior.

Real Windows checks must additionally prove collision preservation, DACL-at-create, alias/reparse and
case-policy rejection, same-parent/volume readbacks, every OS error/close boundary, and the documented
residual-directory behavior after interrupted creation.

## Historical identity-vault lock creation and retained typed JNI errors (ABI7)

The creation/flush description below records ABI7. ABI13 now acknowledges the original containing
directory before returning new profile/vault leases. The typed error and JNI contracts remain in effect.

`createVaultLock(identityDirectory)` creates only the fixed `vault.lock` within the admitted direct
`root/identity` directory. It accepts no filename, root substitute, sibling or deeper descendant. Both
before allocation and before/after file flush, the original root and identity handles must pass fresh
security, path and identity readback; their IDs must be distinct and on the same nonzero volume.
The fixed-scope predicates are the same portable functions exercised by the lock controls, not a
separate filesystem model substituted for native behavior.

Both `createProfileLock(root)` and `createVaultLock(identityDirectory)` use the shared
verify–file-flush–verify–publish controller. Creation remains handle-relative `FILE_CREATE`/`FILE_CREATED`
with the private user+SYSTEM DACL, read/write access and zero sharing. The unpublished file must remain
the original ordinary zero-length one-link file on its pinned parent's volume. Existing names fail;
neither wrapper invokes `lockExisting`, truncates, repairs or deletes a conflicting object. The native
root wrapper remains limited to `root/profile.lock`. New code preserves cleanup uncertainty on every
post-admission exit, including a failed security-descriptor release before creation.

The returned lease stays held until its exact handle closes. A failed operation retires that original
handle once; an uncertain close stays quarantined without retry. A new empty file **may remain after
failure**. No durable parent namespace, crash recovery, rollback or successful full profile write is
claimed. Current role hardening now enforces native profile/vault sequencing and grant dependencies;
the eventual complete adapter must preserve that order and supply the missing durable transactions.
A named public handle is not proof of the correct lease role. Capabilities remain `0x43`, not
`0x7f`, and the full provider remains unavailable.

Native errors now construct `WindowsProfileCustodyException` through its exact primitive-int
`<init>(I)V` constructor using `NewObjectA`, then `Throw`. The Kotlin exception remains an `IOException`,
but its explicit enum mapping and raw integer code remove any need to parse diagnostic text. Codes
1–9 map to the declared custody results; unknown values, including a manually supplied zero, remain
`Unknown`. Messages contain only fixed text and the bounded integer, never OS exception text, a path,
SID, handle, identity or record. No error implies retry, automatic creation, recovery or relaxed custody.
An on-disk create collision is still `OperatingSystem`; an already-owned conflicting lease is `Busy`.

Every effectful JNI entry refuses to enter native work when an exception is already pending. String
and array acquisition failures also stop before native entry. This does **not** skip cleanup after a
callback fails within an admitted operation: existing native owners still clear buffers and retire
their original resources before JNI propagates the pending exception. Class lookup, constructor and
allocation exceptions remain primary; all acquired error local references are released. A broken
JNI reporting result with no pending exception produces a fixed `LinkageError`, never a zero/false
success; inability to report even that fails terminally through `FatalError`. Directory/file identity
array creation similarly preserves pending allocation/copy failures and retires any unreturned local
array. The encoder copies raw unsigned native identity words without changing their high bits.

The initial lock slice included fifteen lock-policy/controller groups and twenty-five actual-JNI
mock-backend groups; the maintained actual-JNI suite now has seventy-three groups. Additional controls cover fixed vault scope, unsigned parent/file IDs, post-flush
changes, exact reverse ownership retirement, all twenty-one effectful pending-entry boundaries, exact
integer error forwarding, linkage/allocation failure, identity output and local-reference cleanup. JVM tests separately
inspect the actual exception class/constructor and the current twenty-three-export PE/manifest contract. Synthetic
PE export tables reserve disjoint slots explicitly; negative mutations must actually alter the fixture.
These are portable/JVM controls, **not Windows SDK, NTFS or installed-application qualification**.

Real Windows controls must still establish relative creation access, creation-time ACLs, cross-process
share exclusion and collisions, fresh case/ADS/reparse/hard-link/parent-substitution rejection, native
JVM exception behavior, root-close with a live vault lease and the residual-file behavior after faults.
The existing Desktop/MSI producer must preserve the JNI class names and exception constructor, verify
the real DLL exports/imports and signing/custody, and bind the final bytes to the existing release
provenance. None of that native loading, packaging or production wiring is enabled by this revision.

## Persistent-candidate JNI boundary (ABI8)

The two new methods preserve the existing native admission and ownership contract. `prepareRecord`
validates the positive directory token, bounded array length and exact pending-name grammar before the
native call. Only the admitted native owner allocates and requests the bounded JNI array copy; the same
buffer controller clears that copy on every return. The caller still owns its Java array and must clear
it when appropriate. A failed native preparation retires any unreturned handle but may retain a partial
pending file; JNI never claims rollback or chooses a new candidate name automatically.

`renameCandidate` accepts only a positive candidate token and bounded component. Root-versus-identity
scope and exact permitted target spelling are independently enforced by the native role owner, not by
an extra caller-supplied authority flag. Failure codes, including `PWP_CLEANUP_UNKNOWN`, cross the same
typed fixed-code exception boundary. A pending Java exception prevents either operation from entering
native work. No string/byte pointer escapes its synchronous JNI call; no private data enters diagnostics.

The component ABI/export policy changes together to **8 / 19 exports**, rejecting older images and
manifests. The expanded synthetic PE fixture keeps export strings and imports disjoint within the
unchanged bounded image. Compiled JVM descriptor tests and real-JNI/mock-backend controls are not Windows
SDK, DLL-load or NTFS runtime evidence. The complete ABI1/`0x7f` provider and availability gates stay closed.
