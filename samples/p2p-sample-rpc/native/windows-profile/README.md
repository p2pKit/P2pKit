# Windows protected-profile native custody (incomplete)

**Not a production provider. No Windows SDK build or Windows runtime qualification has passed.**
The existing Windows UI/profile gate remains closed. Nothing here loads a DLL automatically.

Implemented source components:

- `profile_policy.c`: bounded component/path/ADS/ACL decoding and positive non-reused native ownership tokens;
  reserve-before-allocation, exact-once close, failed-close quarantine and reverse creation-order cleanup.
- `profile_win32.c`: native x64/effective-token checks; OS KnownFolder LocalAppData root; pinned handle-relative
  ancestor/root/child opens; protected user+SYSTEM DACL **at creation**; native NTFS/identity/ACL/stream readback;
  bounded existing-record reads; exclusive existing lock-file custody and owning session retirement.
- `profile_jni.c` and `WindowsProfileCustodyJni`: actual bounded JNI calls to those components, not a Java ACL
  substitute. Errors contain fixed public codes, never paths, SIDs, records or OS exception text.

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
