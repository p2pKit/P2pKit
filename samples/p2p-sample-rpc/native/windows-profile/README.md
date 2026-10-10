# Windows protected-profile native custody (incomplete)

**Not a production provider. No Windows SDK build or Windows runtime qualification has passed.**
The existing Windows UI/profile gate remains closed. Nothing here loads a DLL automatically.

Implemented source components:

- `profile_policy.c`: bounded component/path/ADS/ACL decoding and positive non-reused native ownership tokens;
  reserve-before-allocation, exact-once close, failed-close quarantine and reverse creation-order cleanup.
- `profile_win32.c`: native x64/effective-token checks; OS KnownFolder LocalAppData root; pinned handle-relative
  ancestor/root/child opens; protected user+SYSTEM DACL **at creation**; native NTFS/identity/ACL/stream readback;
  bounded existing-record reads; existing-file identity/existence observations; a bounded 1,024-member native
  directory walk with independent member custody readback; exclusive existing lock-file custody; disposable encrypted-record staging and owning session retirement.
- `profile_jni.c` and `WindowsProfileCustodyJni`: actual bounded JNI calls to those components, not a Java ACL
  substitute. Errors contain fixed public codes, never paths, SIDs, records or OS exception text.

Custody ABI **3** has exactly thirteen JNI exports (adding `stageRecord` and `discardStage`);
its identity-record wire version remains 1. `WindowsProfilePeImage` rejects the prior eight- and eleven-export ABI images.
This partial custody ABI is distinct from the complete `WindowsProfileNativeApi` adapter ABI 1.
The complete adapter still requires ABI 1 **and** `0x7f`; neither condition is changed to admit this
incomplete custody component. All custody revisions lack required durable-persistence capabilities.

The native component restricts elevated default owners and any thread impersonation rather than guessing
an effective owner. Existing unsafe directories/files fail; they are not repaired, reset, deleted or migrated.
An explicit `openRoot` may create the two private directories; those creations are **not** a claim of durable
record transactions. The context serializes admission without a work queue. Closing joins actual synchronous
OS calls; a hung call still requires the missing terminal watchdog, not an invented coroutine timeout.

`capabilities()` returns `0x43` (root custody, metadata and cleanup only), not the required complete `0x7f`.
There is deliberately no claim for atomic write/replace/delete, namespace durability, recovery or complete
profile-lock creation. The full `WindowsProfileFiles` adapter must not accept this incomplete mask.

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

1. Complete and review atomic record mutation, durable namespace transaction/recovery and lock-file creation.
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

### Intended real Windows compilation (not executed here)

From an existing **x64 MSVC Native Tools** prompt with a real Windows SDK and `JAVA_HOME` pointing at JDK17:

```bat
samples\p2p-sample-rpc\native\windows-profile\build-windows.cmd C:\new-owned-output
```

This create-only recipe compiles the three actual C translation units, uses `/MT` static CRT, and links only
the listed Windows system libraries. It requests x64, C11, warnings-as-errors, stack/SDL/CFG protections,
ASLR/high-entropy VA/NX, and embedded manifest. The PE verifier must independently confirm the real resulting
DLL's headers, actual imports and thirteen exports; compiler flags are not that evidence. Verify Authenticode,
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

JNI copies the bounded input into owned native memory and clears that copy on every exit. The synchronous
C ABI borrows stable caller bytes only for that call. Partial writes must make positive bounded progress;
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
