# Isolated JDK21 preview Windows loader boundary

**PRODUCTION DISABLED.** This named module contains actual JDK21 preview FFM
memory preparation and runtime-policy checks. It does not contain a trusted OS
bootstrap, installed-directory admission, native lookup, DLL load, productive JNI
registration, protected profile provider or Windows runtime qualification. Dormant
post-admission registration ownership and FFM call mechanics are described below.

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
current `PAGE_EXECUTE_READ`; data/IAT permits only `PAGE_READONLY`, `PAGE_READWRITE` or `PAGE_WRITECOPY`,
never writable executable, guard or no-access pages. Initial `AllocationProtect` is compared, not confused
with current protection. Successful reads require a nonzero `BOOL` and the exact full 64-bit byte count.
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

Thirty-five fresh-process controls exercise JDK-generated inert query/read upcalls, never the real OS APIs.
Windows uses actual Windows argument/error-capture mechanics; non-Windows tests verify production refusal
before reflectively exercising private frame mechanics only. They cover complete and partial results,
high-32-bit count mismatch, region/protection changes, padding, alias/overflow refusal, independent owner
scopes, synchronous return and retained cleanup failures. No installed-runtime or native-storage credit follows.
