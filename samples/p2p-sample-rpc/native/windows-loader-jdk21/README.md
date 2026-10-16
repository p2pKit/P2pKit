# Isolated JDK21 preview Windows loader boundary

**PRODUCTION DISABLED.** This named module contains actual JDK21 preview FFM
memory preparation and runtime-policy checks. It does not contain a trusted OS
bootstrap, installed-directory admission, productive DLL load/JNI
registration, protected profile provider or Windows runtime qualification. Dormant
post-admission registration ownership, FFM call mechanics and a conditional system-only
bootstrap investigation are described below. The latter does not supply initial authority.

It does not replace the existing Desktop application, installer, version encoding,
Foundation custody or publication pipeline. The ordinary Java17 compilation and
other platforms must not acquire a global JDK21 preview requirement from it.

## Module and public entry points

Module: `dev.p2pkit.rpc.windows.loader`.

- `Probe.main(String[])`: accepts no arguments; prints one bounded diagnostic JSON
  object on success. Runtime-policy refusal exits 2 with a fixed stderr code.
- `Probe.readback()`: the same diagnostic, callable by the existing application's
  explicitly configured modular-preview diagnostic route. Throws on refusal.
- `WindowsLoaderRuntime.requireDiagnosticRuntime()`: checks the real JDK feature,
  module/layer and preview native-access arrangement. It does not authorize loading.
- `WindowsLoader.openInstalledProvider()`: **always refuses** with
  `WINDOWS_LOADER_DISABLED_TRUSTED_BOOTSTRAP_NOT_IMPLEMENTED` after runtime checks.
  There is no caller-supplied path, context, trusted Boolean, environment bypass or
  fallback provider.

The module exports only `dev.p2pkit.rpc.windows.loader`; it has no external module
or native-library dependencies. Data preparation classes are package-private.

## Exact runtime policy

- Java feature **21**, with `--enable-preview`.
- The explicit, non-automatic module above, resolved in the boot layer.
- `--enable-native-access=dev.p2pkit.rpc.windows.loader`.
- `ALL-UNNAMED` native access is refused, even if our named module is also enabled.
- FFM `Arena`, `MemorySegment` and `ValueLayout` must resolve from the boot
  `java.base` module at `jrt:/java.base`.

`Probe` directly invokes the preview `Module.isNativeAccessEnabled()` API, so its
class-file contract requires Java21 preview, not merely Java21 bytecode. Java17,
missing preview, missing/wrong native-access module, classpath execution and
broad unnamed native access are negative controls. Missing preview/module/runtime
may fail in the JVM before `main`; absence of a JSON record is not a PASS.

No restricted operation is attempted as a way to discover permission. The runtime
policy check performs no `Linker.nativeLinker`, symbol/default/library lookup,
`System.load`, `System.loadLibrary`, address reinterpretation or Windows OS call.
The separate dormant invocation component uses `Linker.nativeLinker` only after
that policy check; this does not supply first-load or address authority.
The preview native-access flag is a narrowly checked prerequisite, not DLL trust
or an OS-account privilege grant.

## Diagnostic contract

Successful JSON fields:

```text
schema=1
scope=JDK21_PREVIEW_MODULE_DIAGNOSTIC_NOT_DLL_OR_PROFILE
javaFeature=21
javaVersion=<Runtime.version(), bounded ASCII>
module=dev.p2pkit.rpc.windows.loader
javaVendor=<actual bounded/escaped java.vendor>
javaRuntimeVersion=<actual bounded/escaped java.runtime.version>
javaVmVersion=<actual bounded/escaped java.vm.version>
previewEnabled=true
namedNativeAccess=true
unnamedNativeAccess=false
ffmFromJavaBase=true
windowsX64Hint=<diagnostic OS/architecture properties only>
productionAvailable=false
nativeLoad=NOT_PERFORMED
profileAccess=NOT_PERFORMED
```

Runtime metadata is limited to 128 printable ASCII characters per value, with
quotes/backslashes escaped. It contains no profile, credential, username or
installation path. Supplier/version properties are diagnostic self-report, **not
independent package/runtime provenance**. The platform hint is not native OS,
token, filesystem or architecture qualification; changing a property never enables
`openInstalledProvider`.

Fixed refusal stderr codes are `JDK21_LOADER_PROBE_REFUSED_ARGUMENTS` and
`JDK21_LOADER_PROBE_REFUSED_RUNTIME_POLICY`. No exception details or input values
are printed by the diagnostic main.

## Actual bounded data preparation

`WindowsX64Frame` owns a confined FFM arena and these original allocations:

- An ASCII single package component encoded as UTF-16LE, bounded to 255 UTF-16
  code units (512 bytes including its zero terminator).
- The 16-byte Windows-x64 `UNICODE_STRING`, with a pointer at offset 8.
- A zero-initialized 16-byte Windows-x64 `IO_STATUS_BLOCK` output buffer.

The fixed package-component policy permits interior spaces, rejects separators,
ADS/colon, NUL, control/non-ASCII characters, trailing dot/space and reserved DOS
names. It is not a general user-path parser or installed-root authority.

Layouts specify little-endian fixed-width fields and require 8-byte addresses.
Preparing these layouts on another supported 64-bit JDK21 host is portable FFM
memory evidence, not Windows ABI execution evidence. No caller-provided OS handle
or raw address enters the frame. Its descriptor points only to its own bounded
allocation, and tests never dereference that descriptor as an unbounded pointer.

The wrapper and failure carrier exist before any native arena acquisition.
Partial acquisition attempts cleanup; uncertain cleanup retains the original
frame and exact cause/cleanup throwable. This is not a guarantee of recovery from
arbitrary VM exhaustion. Access/close require the original Java thread. Successful
close clears allocated data and invalidates every borrowed view; close is
idempotent, and a recorded failed close is not retried. Wrong-thread close cannot
retire the owning thread's frame. A preallocated close carrier retains distinct
clear/arena-close throwable slots without suppression allocation. Input component
and descriptor views are read-only; the output status buffer remains writable.

## Tests and integration

The maintained sample owns these explicit tasks (no new Gradle project or Maven publication):

```text
:p2p-sample-rpc:compileRpcWindowsLoaderJdk21
:p2p-sample-rpc:rpcWindowsLoaderJdk21Jar
```

The existing Windows app-image/MSI tasks include this module only with
`-Pp2pkit.rpc.windows.previewAdapter=true`. That is an investigation packaging
option, **not** an enable-provider flag. Normal builds default to false. In that
mode the linker, runtime check and packager use a Java21 toolchain, while published
libraries and Kotlin sample sources retain their Java17 bytecode targets. The
Java21 supplier/full-build pin still belongs to Foundation and remains unqualified.

The modular JAR is staged under `app/resources/rpc-loader-jdk21/` after the existing
image task generates its launcher, before that task completes and its installer
consumes the image. It must not enter Compose's `appResources` input: JDK21
jpackage recursively includes input JARs in `app.classpath`, even beneath resource
directories. The image task declares the adapter JAR as an explicit build input;
installer tasks retain the completed image dependency. No generated launcher
configuration is rewritten. Static image/MSI and real launcher checks must still
verify the module-only placement. The maintained `MainKt` diagnostic argument
`--rpc-windows-loader-readback` resolves only the exact boot-layer module and invokes
`Probe.readback()` without a classpath fallback. Explicit launcher options are:

```text
--enable-preview
--module-path=$APPDIR/resources/rpc-loader-jdk21
--add-modules=dev.p2pkit.rpc.windows.loader
--enable-native-access=dev.p2pkit.rpc.windows.loader
```

The module JAR retains the repository license injected by the existing Gradle
build. Static image/MSI checks verify these inputs but cannot authorize execution
of an installed DLL. No launcher identity, application identity, version mapping,
installer target or publication pipeline is replaced.

`src/test/java/.../ModelTests.java` is a dependency-free test entry point compiled
into a **separate test output**, patched into the named module only for tests.
Never package it in the production modular JAR. It does not enable assertions by
convention: failed checks throw explicitly, independent of `-ea`.

Expected successful output:

```text
WINDOWS_LOADER_JDK21_MODELS_PASS tests=14 scope=PORTABLE_FFM_DATA_NOT_WINDOWS_NATIVE_OR_PROFILE
```

Tests cover actual runtime policy, bounded metadata escaping, permanent provider
refusal, component rejection/bounds, layout/pointers, little-endian encoding,
zero-initialized output, explicit clearing, retained-view invalidation,
wrong-thread rejection, independent owners, bounded access failures, read-only input
views and exact retained cleanup outcomes. A package-private test seam reports
synthetic precreated errors only after actual arena cleanup, so these uncertainty
controls do not leak test arenas or create native authority. The
separate subprocess campaign must exercise missing/incorrect preview/module/access
flags and Java17 refusal. Local portable tests must not be reported as Windows
protected-profile, JNI or installed-lifetime tests.

Foundation still owns runtime/installer integration and the independently trusted
initial OS/installation boundary. RPC must later implement the original-handle
verifier, constrained loading, actual import providers, continuous identical JNI
registration, complete provider transfer and cleanup. Nothing in this isolated
module changes custody ABI13/0x43, provider availability or release gates.

## Managed JNI registration data

The Java17 sample's
[`WindowsProfileJniPlan`](../../src/jvmMain/kotlin/dev/p2pkit/sample/rpc/profile/WindowsProfileJniPlan.kt)
prepares the fixed 23-method registration inventory plus a separate registrar-v1 binding. It verifies the actual
declaring class, exact compiled instance-native descriptors/modifiers and all 24 original
export-address observations. Bounded private snapshots prevent a verified list
from being reread as different registration inputs. The result is immutable data,
not permission to call an address, a registration attempt or native ownership.

Its separate application-classloader check requires the actual system-loader
class identity. A Gradle test loader, matching binary name in another loader or
incidental FFM `FindClass` context is not a substitute. This relationship check
does not establish Foundation's installed runtime provenance. No native method is
invoked by preparing the plan or inspecting the declaring class.

The native [post-admission registration core](../windows-profile/jni-contract.md#post-admission-registration-core)
now exports the single-invocation operation, but remains unreachable
from production. The managed lifetime and fixed FFM invocation components below are implemented separately;
they have no productive caller and loading remains unimplemented. The design direction is
explicit `RegisterNatives` against original verified function addresses, after
independent loading authority. Preload plus `System.load` does not pin each Java
method to that module. JNI references and pending exceptions need the reviewed
single-native-invocation bridge; its exported interface still requires exact current-source
MSVC/build pins and a qualified integrated caller. `RegisterNatives` can partially
succeed: reserve process-lifetime module/class ownership before the attempt, and
retain it on failure without retry, unregister or unload. Profile Stop must not
retire cached JNI code. None of these lifetime or runtime guarantees follows from
the inert plan, and no productive registration caller is enabled here.

## Registration lifetime component

`WindowsJniRegistrationOwner` is a package-private, dormant post-admission mechanism.
It reserves one boot-module process slot before entering its synchronous invocation,
strongly retaining the original installation/runtime/module owners, declaring class,
immutable registration plan and invocation frame. These references are **not** installed
authority or OS handle pins. A future reviewed loader must first establish real authority
and transfer exclusive originals, not borrowed objects with independent close paths.
There is no productive caller. The fixed dormant invocation implementation below is not wired to a DLL.

Every admitted attempt consumes the slot, even a phase-0 refusal, thrown invocation,
partial registration or malformed report. Success requires coherent result-0/phase-2
readback and successful invocation-buffer retirement. Immutable readback prevents a
caller-writable array from changing the validated result. Separate preallocated failure
slots preserve invocation, readback, controller and retirement errors without suppression
allocation. Failure enum initialization precedes native effects. Profile Stop cannot
reset, unregister or unload through this component: no such API exists. Returning a
registration owner does not publish a complete profile provider.

The existing diagnostic command also runs **46 fresh-process lifetime controls** with
inert invocations. They cover terminal errors, all report words, native refusal codes,
concurrent/reentrant/later attempts, virtual-thread rejection and a child-loaded owner
copy. The owner class must itself belong to the original boot module; delegating the
runtime check to that module cannot admit another singleton. These controls are separate
from the 14 FFM data models and do not execute native registration or establish physical
module retention. Test-only classes never enter the packaged adapter JAR.

## Fixed registration FFM invocation

`WindowsJniRegistrationInvocation` implements the internal invocation interface with the exact C signature
`int32_t(JavaVM*, uintptr_t[23], uint32_t, report32*, uint32_t)`. It accepts already-admitted original entry/VM
segments and a one-time copied address list. **Those parameters do not grant native execution authority.**
Before any productive use, the reviewed loader must independently establish the original runtime, entry,
module/imports and installed custody and transfer exclusive original owners. No such loader caller exists.
The native registration core has one explicit registrar-v1 export, separate from its unchanged 23 JNI
methods. The managed byte/address plan requires all 24 exports, but neither creates a callable scoped
segment nor supplies authority. The production loading refusal is unchanged.

The mechanism requires its original named boot module and one platform thread, native non-global live scoped
addresses, 64-bit little-endian layouts, positive user-mode addresses and an aligned VM pointer. It performs no
symbol search, library loading, numeric-pointer construction or global reinterpretation. Its fixed descriptor
and private confined arena contain disjoint aligned 184-byte input and 32-byte output allocations. Original
address observations are copied once; the Java input view is read-only. These checks establish data mechanics,
not Windows system-library/bootstrap trust or correspondence of a pointer to an admitted VM.

Only the exact process owner's reserved invocation can enter. There is one attempt, on its original platform
thread, one immutable report read after normal return, and no frame retirement during native use. Cleanup
independently clears each buffer and closes only the invocation arena, retaining separate preallocated failure
slots and never retrying an uncertain retirement. It never closes the entry/VM scopes or unloads a module.

The diagnostic command exercises **13 fresh-process FFM invocation controls** using a JDK-generated upcall stub
and an inert allocation in place of a VM pointer. The real downcall/upcall checks argument order, exact counts,
bounded pointer layouts, source-array isolation, initial zero output, report readback, owner/thread/one-shot
constraints and frame retirement. The callback never invokes JNI or storage and never lets a Java exception
escape its native boundary. A test-only reflective read-only-buffer fault verifies retained retirement failure;
no production fault-injection hook is added. These are host-ABI FFM mechanics, **not Windows ABI/JNI registration,
DLL loading, protected NTFS, installed application or production authority qualification**.

## Original JVM acquisition and constrained-load call mechanics

`WindowsJvmAcquisitionInvocation` implements the fixed post-admission
`JNI_GetCreatedJavaVMs(JavaVM** vmBuf, jsize bufLen, jsize* nVMs)` call. It supplies one zero-initialized,
disjoint eight-byte VM output and four-byte count output, requires status zero and exactly one positive,
aligned VM pointer, and rejects pointers into its own output buffers. Its result retains the original runtime
owner, arena and entry; retiring private buffers neither invalidates the original VM view nor closes its owner.
There is no lookup, `JNI_CreateJavaVM`, attach/detach fallback or production numeric-address construction.
A future caller must transfer the whole result's ownership to the permanent JNI registration owner, not pass
only a borrowed address. Count/address validation alone is not proof of the original JVM's identity.

`WindowsLibraryLoadInvocation` implements the fixed post-admission `LoadLibraryExW` call with a bounded
canonical absolute DLL path, NULL reserved file argument and `LOAD_LIBRARY_SEARCH_SYSTEM32` only. Real
preparation checks the original boot `java.base` Windows-x64 linker, not mutable OS/architecture hints. It
captures `GetLastError` in the same downcall, retains the returned HMODULE before later validation, and does
not require zero error state on a successful call. No search-path mutation or `FreeLibrary` API exists.
One permanent process owner is reserved before invocation and retains the original installation, runtime,
file and call owners on success or failure; uncertain outcomes cannot authorize retry or unload.

These package-private mechanisms remain dormant. Their owner references, scopes and path grammar **do not
establish authority**. The productive loader still refuses because independently trusted bootstrap,
installation/runtime custody, actual mapping/protection/import checks and full-provider activation are missing.
The fixed-call components must never be substituted for those prerequisites.

Controls use JDK-generated inert upcalls, not an actual DLL load or original-JVM discovery. Cross-host load
controls reflectively exercise only private call-frame mechanics; no validation bypass is exposed in production.
Windows additionally exercises real Windows-linker/captured-error preparation against the inert upcall. Tests
never execute the candidate DLL, open protected storage or claim installed application qualification.

Run the maintained task explicitly with the development JDK17 and JDK21 toolchains available:

```bash
./gradlew :p2p-sample-rpc:verifyRpcWindowsLoaderJdk21 --no-build-cache --dependency-verification=strict
```

Ordinary Windows `jvmTest` now requires this task, so the modular Windows component cannot omit the adapter
controls after retirement of the old dedicated dispatch lane. Other-host ordinary JVM tests retain their
JDK17-only requirement. Each execution preserves a new report directory under
`build/reports/rpc-windows-loader-jdk21/`; existing canonical CI captures these reports without a new workflow,
packaging identity, release route, scope relaxation or qualification claim. Preview classes remain confined to
the dedicated, unpublished adapter; test classes are excluded by the exact packaged-class inventory.

## Exact nonforwarded export-call mechanics

`WindowsExportLookupInvocation` is the dormant package-private `GetProcAddress(HMODULE, LPCSTR)` mechanism
for an already admitted native module or original JVM. It retains separate original bootstrap and module
owners/arenas plus the original export plan, copies a bounded C/JNI ASCII name, and never supplies an ordinal.
Preparation rejects function RVAs inside the complete PE export-directory span (forwarder entries), invalid
image/directory bounds, and address overflow. The future reviewed caller must derive every copied field from
**the same independently pinned original PE observation** before calling: an object reference, numeric span,
or expected address is not proof of that binding or permission to execute an OS export.

Native return must equal the original module base plus the exact pinned function RVA, not merely fall inside
the image. The returned zero-length view belongs to the original module arena, while the result retains both
complete original owners. Private ASCII storage is cleared/retired only after synchronous return. One attempt,
thread/scope checks, independently retained failures and no original-owner cleanup prevent retry or unloading
through this component. Production preparation requires the actual boot Windows-x64 linker. There is no
lookup of `GetProcAddress` itself, `defaultLookup`, `libraryLookup`, system-forwarder resolution or loader
activation. A forwarded system export can involve another module load; this component must never bootstrap
that authority by observing a provider only after it has executed.

Twenty fresh-process controls use JDK-generated inert upcalls. On Windows they exercise real Windows-linker
argument mechanics; elsewhere only private frame mechanics are invoked reflectively after verifying the
production host refusal. They check exact HMODULE/name/terminator, maximum name size, PE forwarder/range and
overflow refusals, null/wrong returns, partial private-buffer overlap and ordinal-pointer rejection, original
scope retirement, thread/reentry, retained errors and independent cleanup. No real export lookup, Windows
DLL execution, protected profile or installed application is qualified by these controls.

## Bounded original-image query and read mechanics

`WindowsImageReadInvocation` provides dormant `VirtualQuery` / `ReadProcessMemory` mechanics for one
original-image-relative range of 1–65,536 bytes. It requires the actual Windows-x64 boot linker, retains
separate original bootstrap and module owners/arenas plus the original PE plan, and uses only the fixed
current-process pseudo-handle. No OS export is discovered here. No arbitrary native memory is dereferenced
in Java: the supplied OS read entry copies into a private, bounded output buffer.

Both queries must return the exact 48-byte AMD64 `MEMORY_BASIC_INFORMATION`; the complete requested range
must fit one committed `MEM_IMAGE` region within the original image and allocation base. Code permits only
current `PAGE_EXECUTE_READ`; the separate header `READ_ONLY` policy accepts exactly current
`PAGE_READONLY`, refusing writable, copy-on-write and executable protection. Data/IAT still permits only
`PAGE_READONLY`, `PAGE_READWRITE` or `PAGE_WRITECOPY`, never executable, guard or no-access pages.
Initial `AllocationProtect` is compared, not confused with current protection. Successful reads require a nonzero `BOOL` and the exact full 64-bit byte count.
All semantic query fields must match before and after the read; unspecified padding is excluded.

Result/failure owners, both query frames, byte-count storage and bounded output/result arrays are reserved
before native calls. Actual Windows `GetLastError` is captured after each call without requiring zero on
success. Independent private-buffer retirement failures retain original owners; failed reads expose no
result, and successful results return defensive copies. One-shot, thread/scope, overflow and complete
source/output-disjointness checks remain enforced. Neither original module nor bootstrap arena is closed.

This is **not** proof of first-load authority, mapped-file identity, atomic mapping stability or IAT
immutability. Matching queries cannot exclude an intervening change or image copy-on-write. A later reviewed
caller must supply and retain actual original custody, select ranges/policies from the independently pinned
PE plan, perform the existing byte/export/import comparisons, and establish the actual system providers.
Ranges crossing region boundaries are refused, not silently shortened or retried. Production remains unavailable.

Thirty-nine fresh-process controls exercise JDK-generated inert query/read upcalls, never the real OS APIs.
Windows uses actual Windows argument/error-capture mechanics; non-Windows tests verify production refusal
before reflectively exercising private frame mechanics only. They cover complete and partial results,
high-32-bit count mismatch, exact read-only header policy, region/protection changes, padding, alias/overflow
refusal, independent owner scopes, synchronous return and retained cleanup failures. Writable, copy-on-write
and executable header refusals complete one query and no read, retaining their original ownership and cleanup
checks. No installed-runtime or native-storage credit follows.

## Conditional first-system-call candidate (not production authority)

`WindowsSystemBootstrapCandidate` investigates a concrete JDK21 route, rather than
introducing a caller-supplied trust object. Its only initial library lookup is the
fixed **String** `kernel32.dll`. The JDK21 raw-library String route passes the name
through its native loader to Windows `LoadLibrary`; it does not use the distinct
`Path` canonicalization or `defaultLookup` CRT/environment fallback. This is not a
`LOAD_LIBRARY_SEARCH_SYSTEM32` or get-existing-only operation.

**That distinction does not establish initial trust.** Windows redirection and
activation-context handling precede loaded-module/KnownDLL lookup. Foundation must
independently bind the actual installed launcher/runtime, original OS imports and
absence of attacker-controlled initial redirection/injection before this route may
become production authority. The exact supplier/full JDK build and startup context
are not replaced by runtime properties, a filename, an adjacent manifest or the
candidate's own later observations. A compromised JVM cannot validate itself back
into trust. The public `WindowsLoader.openInstalledProvider()` remains unchanged
and refuses; no application route calls this candidate.

The candidate has no caller inputs. It requires the actual boot-module Windows x64
linker, preview/native-access policy and an ordinary platform thread before lookup.
A single original owner retains the lookup and physical provider pins for process
lifetime, including failure. Fixed exported addresses are observed with
`GetModuleHandleExW(FROM_ADDRESS|PIN)` and `GetModuleFileNameW`; provider paths must
match kernel32/kernelbase in the OS-returned system directory. The current process
identifier must agree with the existing JDK process API. These are bounded
post-call observations, **not** first-call authority, ancestor/file custody,
physical code integrity, import closure or a complete Windows provider.

The maintained checker adds runtime/thread refusals on every host and an actual
system-only invocation on Windows (unsupported-host refusal elsewhere). It uses
its development JDK and original hosted process. No protected profile, RPC DLL,
JNI registrar, installer, account launcher, privilege grant or security-policy
change is involved. Its result explicitly distinguishes these system calls from
the existing inert controls and from unperformed installed-runtime qualification.
The test class stays outside the packaged adapter. No `ALL-UNNAMED`, internal-JDK
opening, alternate launcher or new native producer is introduced.

### Existing JVM acquisition connection

The dormant system candidate also owns a single `WindowsOriginalJvmCandidate`
attachment. It selects an **already-loaded** `jvm.dll` with
`GetModuleHandleExW(PIN)`, retains that original module and bounded path observation,
resolves only `JNI_GetCreatedJavaVMs`, and pins the resolved address's physical
provider. That provider must equal the selected original module, not a forwarded
function in another module. It then invokes the existing
`WindowsJvmAcquisitionInvocation` and requires exactly one non-null VM. This
attachment makes no explicit library-load, VM-creation, attach/detach, native
registration or storage call. `GetProcAddress` may implicitly load a forwarded
provider before the later same-module check; only prior expected-runtime/export
authority can exclude that effect. Its original module, export, invocation and VM scope remain
retained after independent temporary-frame retirement and after failure.

The fixed module name, observed path and returned VM do **not** independently prove
that this is Foundation's expected installed runtime, eliminate loaded-name
ambiguity, or establish pre-bootstrap authority. Those comparisons remain required
before productive assembly. No `java.home`, environment path or supplied reference
becomes a trusted runtime pin. The development-only Windows test exercises this
actual call chain in a fresh JVM, with duplicate/thread refusals and unchanged
productive-loader refusal. Non-Windows hosts compile it but explicitly report this
Windows-only execution as unperformed.

### Original runtime file lease and installed-object security policy

The original JVM attachment now has a one-shot, zero-input `inspectFile()` operation.
It opens only its own observed module path with `CreateFileW(GENERIC_READ |
READ_CONTROL, FILE_SHARE_READ, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT)`. The
actual Windows x64 HANDLE return bits are retained before allocating their scoped
view. That original handle remains process-owned on success and failure; there is
no Stop-time close or module unload. Six fixed handle-information queries surround
one bounded normalized final-path query. The two semantic observations must agree
on volume/file identity, size, link count and attributes. Reparse, directory,
offline, delete-pending, zero-identity, multiple-link and oversized files refuse.
Temporary native buffers retire independently; padding is not treated as identity.

This is a **final-file development-runtime lease**, not approved installed custody.
The case-folded path comparison does not establish ancestor case policy, absence of
reparse ancestors, NTFS admission, owner/ACL authority, expected packaged identity,
loaded mapping equivalence or absence of pre-existing writable mappings. The actual
Windows-only fresh-process test checks the native calls, one-shot/thread ownership,
retention after a GC request, and unchanged public-loader refusal. Hosted toolcache
runtime bytes are never relabeled as a protected Program Files installation.

`WindowsInstallationSecurity` independently provides a bounded, private-snapshot
SELF_RELATIVE owner/DACL parser for future original-handle security observations.
It accepts only binary SYSTEM, Administrators or TrustedInstaller ownership; null
DACLs, malformed spans, unknown ACE types/flags/masks, and untrusted effective
mutation grants refuse. A DENY does not rescue an unsafe ALLOW. Inheritance-only
entries do not grant the current object rights; inherited effective entries remain
checked. Secure inherited DACLs need not carry `DACL_PROTECTED`. The specific root
file/subdirectory creation exception requires **independently proved volume-root
identity**; it must never be selected merely from a string prefix. All non-root
objects disallow those untrusted creation/write grants.

The parser does not emulate AccessCheck or infer token-group membership, SACL/MIC
policy, or filesystem custody. Its bounded OWNER|DACL input still must come from an
actual admitted OS query on the retained original handle. No such native security
query or installed-ancestor assembly is supplied by these inert descriptor tests.
The production factory and availability flags remain unchanged, not enabled by a
passing parser or a development-runtime observation.

### Actual original-handle security readback (conditional development scope)

`WindowsOriginalJvmFileCandidate.inspectSecurity()` connects its original retained
HANDLE to a single bounded native OWNER|DACL query, not to a supplied descriptor or
pathname. The conditional bootstrap pins the already-loaded fixed `ntdll.dll`,
checks its observed path against the original OS system directory, resolves only
`NtQuerySecurityObject`, and pins that export's physical provider. Its original
module/provider must agree. This introduces no explicit library load, candidate
helper, account operation, privilege grant, or ACL change. As with the existing JVM
export lookup, a later same-provider check does not exclude earlier implicit
forwarder effects or establish pre-bootstrap/runtime authority.

The query requests exactly OWNER|DACL (`5`) into a preallocated 64 KiB buffer with
one DWORD return length. Exact `STATUS_SUCCESS` and a bounded returned length are
required; there is no resizing, probe/retry or `GetLastError` interpretation of the
NTSTATUS result. The original file/module/entry owners remain retained while
private call buffers retire independently. Only successfully returned bounded
bytes reach the descriptor policy; query completion and policy acceptance are
separate observations. A parser refusal is not a native-query failure or permission
to modify the object's ACL. Unexpected errors remain retained failures.

The Windows development test reports the **actual** descriptor decision, ACCEPTED
or REFUSED, without printing owner SIDs, paths or descriptor bytes. Neither result
qualifies the toolcache runtime as an installed application. Duplicate/wrong-thread
queries refuse, retained file/VM ownership survives a GC request, and the public
productive factory must still refuse. macOS compiles these sources and runs the
inert parser controls, but does not receive Windows native-security-query credit.
Actual ancestor custody, expected packaged/runtime identity, first-call authority,
loaded mapping/import verification and complete provider assembly remain required.

### Original handle-relative ancestor observation

The conditional security attachment also owns a one-shot `inspectAncestors()`.
Its only path comes from the already-observed JVM module; its comparison identity
comes from the original held file. A root directory lease permits read/write
sharing but **not delete sharing**. The actual root must resolve to a bare volume
GUID root, and the already-held original file must resolve through that same GUID
and the exact original path suffix. This prevents treating a substituted directory
as the volume root or relying solely on potentially colliding volume serials.
Actual handle-based filesystem queries require fixed NTFS with persistent ACLs;
no volume label is requested. None of this chooses Foundation's expected Program
Files installation or its runtime pin.

Each subsequent existing component is opened with `NtCreateFile` relative to its
original held parent: bounded single-component names, `OBJ_DONT_REPARSE`,
`FILE_OPEN_REPARSE_POINT`, synchronous options and no delete sharing. Actual
handle metadata rejects reparse, offline, delete-pending and case-sensitive
directories, requires the same volume and retains the complete chain. The final
relative read-only file lease must match the original file identity/metadata.
Directory metadata is re-observed after traversal; directory allocation/size is
not namespace identity. The 64-handle limit includes root, directories and leaf.

Root/directory owner-DACL snapshots use the same bounded native query and binary
policy. The root's specific create-right exception is selected only after the
actual bare-root identity check, not from a supplied enum or path prefix. A failed
policy result is preserved separately from native observation completion. These
snapshots do **not** prove continuous ACL immutability, absence of pre-existing
security/delete handles or writable mappings, loaded image identity, original
startup/export authority or complete installed-app admission.

Synchronous creation options alone do not authorize frame retirement. Before every
`NtCreateFile`, all input/output frames and parent leases have a permanent owner.
Only exact returned success, IO_STATUS_BLOCK success, FILE_OPENED and a retained
valid handle permit frame reuse. A thrown, pending, failed or contradictory
completion retains the entire frame and all owners for process lifetime: no
retry, clearing, closure or further candidate native call. Portable test-only
reflection fixtures verify that the actual retirement gate preserves bytes and
arenas under uncertainty and clears/retires only the non-uncertain frame. They use
allocated inert memory and do not simulate a completed real pending Windows I/O.
The fixture classes cannot enter the packaged adapter.

The fresh-process Windows ancestry control executes the actual calls and records
the actual ancestor policy decision, while retaining duplicate/thread/public
factory refusal checks. Neither ACCEPTED nor REFUSED is installed authority.
Productive DLL/provider activation and real installed qualification remain open.
