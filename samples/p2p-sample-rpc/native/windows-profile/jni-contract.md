# Windows native/JNI integration contract

This is the native-side proposal for RPC integration, starting at
`e69e8607c6b27e2db2568783c65ef73b8ad1ee85`. Agreement is tracked in
[Foundation coordination #437](https://github.com/p2pKit/P2pKit/issues/437#issuecomment-6180956706).
**NOT_READY: source semantics are not Windows execution or installed-application qualification.**
See the [native implementation](README.md) and [execution prerequisites](tests/windows/README.md).

## ABI, exports and capability boundary

The custody DLL reports **ABI13 / capabilities 0x43** (root custody, metadata, cleanup).
The complete managed adapter requires **ABI1 / 0x7f** and must continue refusing this partial contract.
Implemented composition functions do not independently authorize capability promotion. Promotion needs
reviewed complete semantics, a productive adapter, trusted loading and source-bound execution evidence.

Every symbol is `Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_` followed by the method below.
These are instance native methods; JNI supplies `JNIEnv *` and `jobject` before their descriptor arguments.
The existing compiled `WindowsProfileCustodyJniContractTest` checks all 23 descriptors. PE export presence
does not prove signatures, numeric ABI, trusted loading or native registration continuity.

| Method suffix | JVM descriptor | Native entry / result |
| --- | --- | --- |
| `abi` | `()I` | `PWP_CUSTODY_ABI` = 13 |
| `capabilities` | `()J` | `0x43` |
| `openRoot` | `()J` | `pwp_win_open_root` |
| `child` | `(JLjava/lang/String;)J` | `pwp_win_child` |
| `createChildDirectory` | `(JLjava/lang/String;)J` | `pwp_win_create_child` |
| `identity` | `(J)[J` | `pwp_win_identity` |
| `fileIdentity` | `(JLjava/lang/String;)[J` | `pwp_win_file_identity` |
| `exists` | `(JLjava/lang/String;)Z` | `pwp_win_exists` |
| `names` | `(J)[Ljava/lang/String;` | `pwp_win_names` |
| `read` | `(JLjava/lang/String;I)[B` | `pwp_win_read` |
| `lockExisting` | `(JLjava/lang/String;)J` | `pwp_win_lock` |
| `createProfileLock` | `(J)J` | `pwp_win_create_profile_lock` |
| `createVaultLock` | `(J)J` | `pwp_win_create_vault_lock` |
| `stageRecord` | `(JLjava/lang/String;[B)J` | `pwp_win_stage` |
| `prepareRecord` | `(JLjava/lang/String;[B)J` | `pwp_win_prepare_record` |
| `writeRecord` | `(JLjava/lang/String;Ljava/lang/String;[BZ)V` | `pwp_win_write_record` |
| `renameCandidate` | `(JLjava/lang/String;)V` | `pwp_win_rename_candidate` |
| `replaceCandidate` | `(JLjava/lang/String;)V` | `pwp_win_replace_candidate` |
| `syncDirectory` | `(J)V` | `pwp_win_sync_directory` |
| `discardStage` | `(J)V` | `pwp_win_discard_stage` |
| `requestExpectedFileDeletion` | `(JLjava/lang/String;[J)V` | `pwp_win_request_delete` |
| `deleteRecord` | `(JLjava/lang/String;[J)V` | `pwp_win_delete_record` |
| `close` | `(J)V` | `pwp_win_close` |

## Production mapping and ownership

Use the existing 17-call bridge subset. Map `directoryIdentity` to `identity`; select exactly one child
open/create operation; select a fixed-role lock open/create only after strict existence observation.
Map managed write, delete and sync to `writeRecord`, `deleteRecord` and `syncDirectory` respectively.
The six low-level staging, candidate and delete-intent methods remain diagnostic primitives. Do not
assemble a competing managed transaction or use them to bypass the composed boundary.

`deleteIfEmpty` and `LabVault.destroy` remain unsupported fixture operations. Production Stop releases
ownership and preserves profiles; it neither deletes lock files/directories nor resets identity/trust.
No directory-deletion export is required for that lifecycle.

Native admission has one active operation and no queue. Original root/profile/vault grants remain held
through publication, synchronization and actual close. Positive opaque tokens are never raw OS handles
and are never reused. There are 128 owner slots and at most 32 published handles. A rejected concurrent
operation does not cancel the active native owner. `close(root)` joins it and drains original owners.
Uncertain physical close is never retried, even if root cleanup is requested afterward.

Loader ownership must span JNI registration, every call, late returns and cleanup. Profile Stop must
not unload the DLL behind cached JNI addresses. A failed acquisition can retain unpublished native
resources; preserve the exact provider/session carrier even when no positive handle reached Java.

## Storage and restart semantics

- Root bootstrap acknowledges original handles in RpcProfile → P2pKit → LocalAppData order. New identity
  acknowledges itself → root; new profile/vault locks acknowledge their own file → parent before publication.
- Writes preserve the pending owner through prepare → same-directory publish → original-parent sync →
  close. `profile.header` is create-only. Identity records use 64 lowercase hex characters plus `.aesgcm`;
  replacement is cooperative under both leases, not an atomic compare-and-swap against a hostile writer.
- Deletion verifies the expected file identity on its deletion handle, confirms intent and actual close,
  then establishes strict final-name absence and synchronizes the original parent. Pre-intent missing is
  an error. After intent, failed absence/sync or uncertain cleanup seals admission.
- Restart inspects under the profile lease. Existing identity requires an existing empty `vault.lock`;
  read it before acquiring its share-none lease. Inspect/sync identity under both leases before consuming
  header/KDF material. Preserve and refuse unknown names, pending files and incomplete initialization.
  No candidate promotion, silent repair or identity reset is provided.

Components are bounded to 96 UTF-16 units, records to 262,144 bytes, names to 1,024 members. Identity arrays
contain exactly six raw 64-bit words: wire version 1, volume, two file-ID words, directory `0x1ff` or file
`0x2ff` policy flags, and sentinel 1. Preserve unsigned bit patterns; only opaque handles must be positive.
The managed layer owns encryption/authentication, passwords, peer trust and revocation. A synthetic native
byte round trip proves none of those application properties. Flush/termination is not power-loss evidence.

## Errors and outstanding engineering

Native result codes are 0 OK, 1 Argument, 2 Policy, 3 OS, 4 Busy, 5 Closed, 6 Limit, 7 NotFound,
8 CleanupUnknown and 9 Unimplemented. JNI throws `WindowsProfileCustodyException(int)` for failures and
preserves an existing JVM exception. Reporting failures must remain errors, never successful zero/false.
Unknown codes, CleanupUnknown and reporting Errors cannot establish retirement. Never translate code7
from composed deletion into harmless absence, or retry mutation based on a generic OS failure.

Foundation must supply independently trusted installed-root/runtime/bootstrap authority and the reviewed
same-user outer supervisor. RPC owns the productive loader, complete managed adapter/platform selector,
JNI continuity and application ownership transfer. Native owns storage primitives/compositions and their
Windows controls. No self-pinned candidate, sidecar or nominal trusted-context object supplies authority.
Actual admission, NTFS faults/recovery, JNI, exact runtime/MSI bindings, two-device operations and installed
lifecycle retirement remain W01–W11 requirements. Track results separately in
[campaign #462](https://github.com/p2pKit/P2pKit/issues/462); missing engineering is not a deferred test.

## Post-admission registration core

[`profile_jni_registration.h`](profile_jni_registration.h) and
[`profile_jni_registration.c`](profile_jni_registration.c) implement a **dormant, non-exported**
single-invocation registrar. The existing MSVC producer compiles it; no productive caller or exported
shim is added. The original 23 JNI exports, ABI13/0x43 and provider availability remain unchanged.
This component must never execute to authorize its own initial load.

Before entry, RPC/Foundation must independently admit the installed runtime, exact single live JVM,
original custody module, mappings/protections/import providers and original compiled declaring class.
The loader must already have permanently reserved module/runtime/ancestor ownership and restricted
execution to its dedicated attached platform thread. Caller pointers, class relationships, matching
function addresses and a successful report cannot establish that authority.

`pwp_jni_register_once` takes the independently obtained `JavaVM *`, exactly 23 expected original
function addresses in the table order above, and a distinct live 32-byte report plus its exact size.
There are no caller-selected classes, descriptors, functions or paths. The original compiled symbol
table lives in `profile_jni.c`; expectations are read once before Java calls. Actual registration uses
only the immutable original table, even if class initialization changes caller-owned expectations.

The report is eight consecutive 32-bit fields: size, version (1), phase, signed result, class-retained,
exception-observed, primary-exception-retained and retention-uncertain. Phases distinguish not attempted
(0), attempted/uncertain (1) and completed without a pending exception (2). Fixed result codes in the
header distinguish arguments, duplicate calls, address mismatch, unavailable thread environment,
runtime mismatch, class/method lookup, Java exception, registration failure and uncertain retention.
No object address, path, throwable text or profile data is emitted.

- Invalid pointer/count/size arguments are refused without JNI entry. Valid pointer *memory and
  lifetime* remain a required loader precondition, not something a C null check establishes.
- The first valid invocation atomically consumes the opportunity in the original module; later, concurrent
  or reentrant calls refuse without touching JNI or earlier owners. Even pre-registration failure after
  this reservation is terminal. There is no reset or retry API. The external process-lifetime owner
  must prohibit loading another copy or unloading/reloading this mapping; a per-module latch cannot
  independently establish that process-wide guarantee.
- `GetEnv(JNI_VERSION_21)`, exact reported JNI version and `GetJavaVM` identity must agree. No attach,
  detach, new VM, filesystem, symbol search or OS privilege operation occurs.
- Only bootstrap `java.lang.ClassLoader` and `java.lang.Class` use `FindClass`. The fixed application
  name resolves through `Class.forName(name, false, actualSystemLoader)`, and its defining loader must
  be that exact system loader. The maintained managed plan separately verifies the compiled class,
  declared instance-native modifiers and full descriptors. These are not runtime provenance checks.
- Each fixed descriptor resolves before registration. A strong global class reference is reserved
  before `RegisterNatives`; that operation can partially bind methods before returning failure.
  Original class and external native-module owners remain held through process exit in every outcome.
- Pending exceptions are retained as original global references and cleared within this invocation,
  before the local frame returns. A separate cleanup exception cannot replace the first throwable.
  Failed exception retention remains explicit terminal uncertainty; there is no claim that an
  unretainable original survived. After acquiring JNIEnv, no exception or local reference may escape
  through the FFM return. Earlier argument/duplicate refusals neither inspect nor change JNI state.
  A JVM that cannot clear a pending exception is terminated rather than treated as successful.
- Global references intentionally have no release API. Profile Stop closes storage, never the class,
  cached native code or module. A report does not authorize publication of a complete provider.

The maintained portable command includes 114 fresh-process registrar controls using a **mocked JNI
vtable and inert method table**, plus an original-symbol/descriptor table check in the existing real
JNI translation-unit suite. It covers all 23 address mismatches, all 32 lookup positions with/without
pending exceptions, thread/runtime/class mismatch, allocation and retention faults, partial binding,
cleanup failure, reentry, changed caller observations and duplicate refusal. ASan/UBSan evidence is
source/controller evidence, **not actual JVM registration, Win32 atomics, NTFS or installed runtime**.

Still required: review and expose the final post-admission entry with exact PE inventory/build pins,
connect the dormant managed process-lifetime owner to real exclusive original leases and FFM invocation,
establish independent initial loading
authority, then execute actual JNI and installed Host/Client qualification. No Windows capability or
qualification claim is promoted by compiling or testing this dormant component.

The named JDK21 adapter now contains a dormant fixed-signature FFM invocation implementation. It owns
its disjoint bounded input/report frame, requires the exact reserved registration owner and platform
thread, and retains uncertainty without retiring original module/runtime scopes. Its fresh-process
downcall/upcall controls use only a JDK-generated inert stub: no original DLL, JNI or profile execution.
This supplies call mechanics, not address authority, an exported registrar or productive integration.

The separate [development-JVM controls](tests/jvm/README.md) now exercise this actual registrar and
original JNI translation unit with the real compiled custody classes in a development JDK21. The test-only
Mac executable links an abort-on-entry storage backend, not `profile_win32.c`. Real registration, pure
ABI/capability calls, continuity after a GC request, duplicate refusal and three pre-registration negative
cases are checked under `-Xcheck:jni`. This removes the mocked-vtable limitation for those exact operations,
not the missing productive Windows DLL/FFM/storage/installed-runtime qualification.
