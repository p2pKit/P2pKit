# Windows RPC profile integration contract

**Implementation status: NOT_IMPLEMENTED. Runtime qualification: NOT_QUALIFIED.**

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
