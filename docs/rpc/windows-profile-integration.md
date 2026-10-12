# Windows RPC profile integration contract

**Implementation status: NOT_IMPLEMENTED. Runtime qualification: NOT_QUALIFIED.**

The complete Windows backend remains unimplemented. The managed filesystem seam,
validation-only adapter, and partial C/JNI custody implementation now exist. They
do not supply a qualified Windows DLL, secure loader, durable NTFS transactions,
or Windows runtime evidence. The production Windows profile gate remains closed.
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

Attach architecture-specific DLL builds, resource staging and verification to the
existing Compose Desktop application/distributions and corresponding CI jobs.
Do not introduce another installer, executable application or release pipeline.
Load only a reviewed app-owned absolute library with source/hash/ABI/architecture
and path-integrity checks; reject mismatches before execution. Native imports must
resolve to approved Windows system libraries, not the current working directory.
Use the existing distribution's signing/provenance process; developer artifacts
are not signed-release or installed-runtime qualification.

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
implementation to complete transaction/durability and interruption recovery;
a noncircular loader that can
verify its app-owned DLL before executing it; architecture/signature/source-bound
existing-MSI packaging; and the terminal watchdog for blocked OS calls. No DLL,
Windows SDK, Windows execution or installed-runtime result is supplied by this
checkpoint. An Apple compiler or a passing memory model cannot close those gates.

### Partial native custody checkpoint

The sample-owned [native custody component](../../samples/p2p-sample-rpc/native/windows-profile/README.md)
has real Win32 implementation source and bounded JNI entry points, not a Java ACL
substitute. Its separate custody ABI is **7**, with **17** exports and capability
mask **`0x43`**. The complete adapter still requires ABI **1** and **`0x7f`**;
the partial component must never be passed off as that full contract.

The implemented primitives include pinned root/child custody, explicit private
child and fixed lock-file creation, existing-record observations, disposable
encrypted-record staging, expected-ID deletion intent, and exact original-handle
retirement. A successful file flush is not a durable namespace transaction, and
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

The C-only `pwp_win_prepare_record` now creates a distinct persistent, uncommitted candidate;
it does not expose another JNI method or satisfy the complete adapter's `write` contract.
Unlike disposable staging, it uses no delete-on-close flag. Under the same native role grants,
it privately creates, writes and file-flushes at most 262,144 bytes, then rewinds and verifies
every byte plus EOF through the original handle with 4-KiB scratch. The opaque owner keeps
its granting leases alive; normal metadata/reads/inventory refuse a live candidate. Close,
including failure cleanup or root drain, retires only the original handle and retains the
candidate file. Partial candidates are never implicitly promoted, retried or deleted.
This advances header/vault write preparation, not atomic publication, namespace durability
or recovery. ABI7, seventeen JNI exports, capability `0x43` and the closed provider gate
remain unchanged. See the native component's persistent-candidate section for its exact scope.

The maintained [real-Windows custody smoke source](../../samples/p2p-sample-rpc/native/windows-profile/tests/windows/README.md)
is **NOT_COMPILED/NOT_EXECUTED**. It requires a separately authorized disposable standard-user environment
and bounded external process owner. It does not complete the provider, authorize execution or qualify an MSI.

## Terminal application-exit prerequisite

`WindowsProfileTerminalClose` implements a validation-only JVM terminal boundary, not ordinary Stop/Back
and not a production Windows selector. It arms a dedicated non-daemon deadline before concealment, claims
exactly one cleanup worker, and retains the actual owner through native return. The deadline also covers the
completion callback. Independent monotonic elapsed-time checks reject late completion even when scheduled
expiry delivery is delayed; an unavailable clock fails closed. Late returns after expiry cannot report successful retirement or restart admission.
The concrete deadline calls `Runtime.halt(125)` without waiting for shutdown hooks: that is a failed terminal
exit with unproven cleanup, **not** successful native cancellation or a cleanup receipt. No implicit deadline
is chosen for production. A caller must provide complete application-owner retirement, not just one profile.

Managed controls cover duplicate delivery, close races, failed scheduling/concealment/completion and retained
late native-model ownership. Forked JVM controls exercise blocked ownership, concealment and completion, plus
normal retirement of the non-daemon timer. They validate the executing JVM host only. Returning from the
completion callback does not prove that the application process exited. The actual Windows cancellation
mechanism, application-close wiring, installed-MSI behavior and selected production deadline remain open.
No process exit hook, native loader or production application setting is changed by this prerequisite.
