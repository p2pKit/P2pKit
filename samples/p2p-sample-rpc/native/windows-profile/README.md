# Windows protected-profile native custody (incomplete)

**Not a production provider. No Windows SDK build or Windows runtime qualification has passed.**
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
  and owning session retirement.
- `profile_jni.c` and `WindowsProfileCustodyJni`: actual bounded JNI calls to those components, not a Java ACL
  substitute. Errors contain fixed public codes, never paths, SIDs, records or OS exception text.

Custody ABI **7** has exactly seventeen JNI exports (adding `createVaultLock` and typed failure propagation);
its identity-record wire version remains 1. `WindowsProfilePeImage` rejects prior custody export inventories,
including the sixteen-export ABI6 image. The older ABI4/ABI5/ABI6 sections below describe their original scopes,
not the current ABI or new Windows runtime results.
This partial custody ABI is distinct from the complete `WindowsProfileNativeApi` adapter ABI 1.
The complete adapter still requires ABI 1 **and** `0x7f`; neither condition is changed to admit this
incomplete custody component. All custody revisions lack required durable-persistence capabilities.

The native component restricts elevated default owners and any thread impersonation rather than guessing
an effective owner. Existing unsafe directories/files fail; they are not repaired, reset, deleted or migrated.
An explicit `openRoot` may create the two private directories; those creations are **not** a claim of durable
record transactions. The context serializes admission without a work queue. Closing joins actual synchronous
OS calls; a hung call still requires the missing terminal watchdog, not an invented coroutine timeout.

`capabilities()` returns `0x43` (root custody, metadata and cleanup only), not the required complete `0x7f`.
There is deliberately no claim for atomic write/replace/delete, namespace durability, recovery or the complete
profile-lock orchestration. The full `WindowsProfileFiles` adapter must not accept this incomplete mask.

## Current role-bound admission and retirement (ABI7 hardening)

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

`lockExisting` now admits only the exact component spelling `profile.lock` at root or `vault.lock` at
canonical identity. Existing and new locks use the same verify–file-flush–verify–publish controller and
must be ordinary zero-length one-link files at the expected scope. They retain their different
`FILE_OPEN` versus collision-refusing `FILE_CREATE` semantics; neither operation rescues the other.
For vault admission, native checks revalidate the actual held profile file, not just a role boolean.
Pre-profile `exists(root, "profile.lock")` and `read(root, "profile.lock", 0)` remain nonmutating
metadata operations, preserving the initialization order in `DesktopRpcProfile.open`.

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

This is unreleased behavioral hardening within custody ABI7: seventeen JNI exports, capability `0x43`
and closed complete-provider availability are unchanged. It adds no durable namespace transactions,
record publication/recovery, native loader or runtime qualification. Live lock files cannot be deleted
by the expected-file deletion primitive. In particular, the existing synthetic `LabVault.destroy`
helper is not a production native destruction recipe; complete-provider cleanup still needs explicit
integration rather than weakening role admission. Real OS tests require a disposable Windows account
or VM because the KnownFolder root is intentionally non-injectable; there is no temporary-path fallback.

## Verification and build boundary

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
3. Implement the terminal native-call watchdog/cancellation policy with retained late-completion ownership.
4. Compile the actual Windows source and JNI, resolve SDK/compiler issues, and add OS adversarial/runtime
   tests for all native branches. Secure production wiring remains deliberately absent until those contracts exist.

Windows x64 runtime/installed-MSI validation is a separate unavailable infrastructure gate. Passing these
portable controls alone must never flip `WindowsProfileAvailability.IMPLEMENTED` or `.QUALIFIED`.

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
DLL's headers, actual imports and seventeen exports; compiler flags are not that evidence. Verify Authenticode,
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
namespace recovery recipe, producer/installed-DLL trust, and terminal-call integration. The disposable
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
abi=7
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


## Explicit new profile-lock prerequisite (not a durable transaction)

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
must satisfy the existing case-insensitive namespace rule. Current ABI7 additionally restricts mutation
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

## Explicit protected child-directory creation (ABI6)

The original ABI6 `createChildDirectory(parent, name)` primitive created one new directory below an
already-held public private directory. Current ABI7 hardening restricts it to `root/identity` under the
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

## Explicit identity-vault lock creation and typed JNI errors (ABI7)

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
claimed. Current ABI7 role hardening now enforces native profile/vault sequencing and grant dependencies;
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

The maintained suite now includes fifteen lock-policy/controller groups and twenty-five actual-JNI
mock-backend groups. Additional controls cover fixed vault scope, unsigned parent/file IDs, post-flush
changes, exact reverse ownership retirement, all fifteen effectful pending-entry boundaries, exact
integer error forwarding, linkage/allocation failure, identity output and local-reference cleanup. JVM tests separately
inspect the actual exception class/constructor and the seventeen-export PE/manifest contract. Synthetic
PE export tables reserve disjoint slots explicitly; negative mutations must actually alter the fixture.
These are portable/JVM controls, **not Windows SDK, NTFS or installed-application qualification**.

Real Windows controls must still establish relative creation access, creation-time ACLs, cross-process
share exclusion and collisions, fresh case/ADS/reparse/hard-link/parent-substitution rejection, native
JVM exception behavior, root-close with a live vault lease and the residual-file behavior after faults.
The existing Desktop/MSI producer must preserve the JNI class names and exception constructor, verify
the real DLL exports/imports and signing/custody, and bind the final bytes to the existing release
provenance. None of that native loading, packaging or production wiring is enabled by this revision.
