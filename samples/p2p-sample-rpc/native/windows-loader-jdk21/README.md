# Isolated JDK21 preview Windows loader boundary

**PUBLIC PROVIDER DISABLED.** This named module contains JDK21 preview FFM
mechanics and the closed original installed-admission chain. Only the separately
explicit installed-admission diagnostic may invoke that native load/JNI chain;
ordinary readback and the public provider entry do not. Implementation and model
results are not installed Windows/provider qualification. The documented trusted
OS/JVM/application/startup premise is still required before its first OS call.

It does not replace the existing Desktop application, installer, version encoding,
Foundation custody or publication pipeline. The ordinary Java17 compilation and
other platforms must not acquire a global JDK21 preview requirement from it.

## Module and public entry points

Module: `dev.p2pkit.rpc.windows.loader`.

- `Probe.main(String[])`: accepts no arguments; prints one bounded diagnostic JSON
  object on success. Runtime-policy refusal exits 2 with a fixed stderr code.
- `Probe.readback()`: the same diagnostic, callable by the existing application's
  explicitly configured modular-preview diagnostic route. Throws on refusal.
- `Probe.installedAdmissionReadback()`: explicit zero-argument native admission
  diagnostic for the installed application, followed by same-owner reuse. It does
  not enter profile storage/network or enable the public provider; failure keeps
  the exact original retained carrier. See the installed diagnostic scope below.
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
the public provider still has no productive caller. The explicit installed admission diagnostic
uses `RegisterNatives` against original verified function addresses, after
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
There is no productive public provider caller. The explicit installed diagnostic alone can
reach the fixed original DLL verification/registration composition below.

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
thread, one immutable report read after normal return, and no frame retirement during native use. The primitive
result is retained before report readback. An unconfirmed native return quarantines the complete input/report
frame unchanged under its failed permanent owner, without report acceptance, retry or replacement. Java unwinding
does not establish native retirement. For confirmed-unused frames, cleanup independently clears each buffer
and closes only the invocation arena, retaining separate preallocated failure
slots and never retrying an uncertain retirement. It never closes the entry/VM scopes or unloads a module.

The diagnostic command exercises **15 fresh-process FFM invocation controls** using a JDK-generated upcall stub
and an inert allocation in place of a VM pointer. The real downcall/upcall checks argument order, exact counts,
bounded pointer layouts, source-array isolation, initial zero output, report readback, owner/thread/one-shot
constraints and frame retirement. The callback never invokes JNI or storage and never lets a Java exception
escape its native boundary. A test-only reflective read-only-buffer fault verifies retained retirement failure;
no production fault-injection hook is added. Pre-call and post-native-return throws verify retained unchanged
frames and the original failed owner; they do not prove actual asynchronous native work. These are host-ABI
FFM mechanics, **not Windows ABI/JNI registration,
DLL loading, protected NTFS, installed application or production authority qualification**.

## Original JVM acquisition and constrained-load call mechanics

`WindowsJvmAcquisitionInvocation` implements the fixed post-admission
`JNI_GetCreatedJavaVMs(JavaVM** vmBuf, jsize bufLen, jsize* nVMs)` call. It supplies one zero-initialized,
disjoint eight-byte VM output and four-byte count output, requires status zero and exactly one positive,
aligned VM pointer, and rejects pointers into its own output buffers. Its result retains the original runtime
owner, arena and entry; retiring private buffers neither invalidates the original VM view nor closes its owner.
The primitive JNI status is retained before output or scope readback. An unconfirmed native return quarantines
the entire original VM/count frame unchanged, including across repeated retirement requests; it cannot publish
a VM or authorize retry. Known pre-call failures and known-return validation/readback failures still retire
their unused private frames. Inert pre-call and post-native-return failures test this distinction, not pending
native work or original-JVM identity.
There is no lookup, `JNI_CreateJavaVM`, attach/detach fallback or production numeric-address construction.
A future caller must transfer the whole result's ownership to the permanent JNI registration owner, not pass
only a borrowed address. Count/address validation alone is not proof of the original JVM's identity.

`WindowsLibraryLoadInvocation` implements the fixed post-admission `LoadLibraryExW` call with a bounded
canonical absolute DLL path, NULL reserved file argument and `LOAD_LIBRARY_SEARCH_SYSTEM32` only.
Its preparation now requires the exact bootstrap and its original JVM; the old caller-supplied callable
entry/arena overload is absent. Before loading, the process-owned attempt calls that bootstrap's fixed
`GetModuleHandleExW(PIN)` for `p2pkit-windows-profile.dll`. Only a confirmed false return, NULL output and
`ERROR_MOD_NOT_FOUND` (126) proceed. An existing module, contradictory output or incomplete return refuses
before `LoadLibraryExW`; any acquired PIN remains retained. Probe buffers are quarantined if native return
or output readback is uncertain. No retry, unpin, basename substitution or search fallback is allowed.
The absence observation is not an atomic exclusion of arbitrary concurrent loading, nor startup/installer
authority; the reviewed process/startup boundary remains required. Real
preparation checks the original boot `java.base` Windows-x64 linker, not mutable OS/architecture hints. It
captures `GetLastError` in the same downcall and captures the Windows-x64 HMODULE return register as a
primitive `long` before any allocating segment wrapper, error readback or scope recheck. Only after those
checks does it create the original-arena view. A late readback/scope failure retains the raw return; a
downcall that does not complete normally retains the permanent owner and the complete private path/error
frame without clearing or closing it, inventing a returned handle, or treating Java unwinding as native
retirement. Repeated retirement requests remain no-ops while return is unconfirmed. Known pre-invocation
refusals and known native returns followed by readback failures still retire their unused private frames.
It does not require zero error state on a successful call. No search-path mutation or `FreeLibrary` API exists.
One permanent process owner is reserved before invocation and retains the original installation, runtime,
file and call owners on success or failure; uncertain outcomes cannot authorize retry or unload.

These package-private mechanisms remain dormant. Their owner references, scopes and path grammar **do not
establish authority**. The productive loader still refuses because independently trusted bootstrap,
installation/runtime custody, actual mapping/protection/import checks and full-provider activation are missing.
The fixed-call components must never be substituted for those prerequisites.

Controls use JDK-generated inert upcalls, not an actual DLL load or original-JVM discovery. Cross-host load
controls reflectively exercise only private call-frame mechanics; no validation bypass is exposed in production.
Windows additionally exercises real Windows-linker/captured-error preparation against the inert upcall.
The load fixture independently returns an ADDRESS while the downcall captures the primitive return register;
late scope closure and interrupted MethodHandle return controls distinguish an observed handle from an
uncertain call. Tests never execute the candidate DLL, open protected storage or claim installed application
qualification.

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

## Once-owned loaded-image comparison

`WindowsLibraryLoadInvocation.Result` attaches one
`WindowsLoadedProfileImageVerification` before any export lookup or image read.
The attachment derives its module, arena, original JVM and fixed OS entries from
that exact load and bootstrap. It retains every export/read invocation and partial
result, then uses the real Java17 PE verifier to compare all planned header/code
pages and IAT slots. JNI ordering selects the original scoped export views; it
never turns a returned numeric comparison result into a new callable pointer.

Owned file comparisons must retain the same original DLL file/path and prebound
system cohort. The separate conditional development comparison requires the
original bootstrap's exact kernel32 resolver and exact unowned byte plan. Neither
route falls back to the other after failure. Failure consumes the attachment and
retains the complete original chain; no retry, unload or provider publication is
introduced. After full comparison, the zero-argument `registerOriginalJni()` reserves
one attempt and obtains only the same original JVM acquisition, declaring class,
23 verified views and registrar. It retains the exact VM result, registration frame,
roots and successful/failed native owner. Preparation/controller failures also seal
the attachment without speculative frame retirement or retry. No supplied numeric
address array, alternate VM or native registration callback enters this composition.
The actual deny-storage DLL fixture uses this same comparison and registration
sequence; its original bad-address registrar control remains separate.

This is post-load composition, **not** the independently trusted first-load or
existing-mapping/backing-file authority. The public loader remains unavailable;
original installation/runtime authority and productive activation are still
required. Component tests do not qualify installed protected storage.

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

### Original retained-handle byte identity observation

`WindowsOriginalJvmFileCandidate.inspectBytes()` attaches one original
`WindowsOriginalJvmBytesCandidate` before any read. It uses the already-held
synchronous `CreateFileW` handle, not a second pathname open. This private handle
starts at offset zero; the other existing metadata/security/ancestor observations
do not move its file pointer. There is no seek, reopen or retry. Fixed `ReadFile`
is resolved and physically pinned with the other original system entries.

The original identity, allocation/EOF length, link count, attributes, reparse and
delete/directory state are checked before and after reading. At most 512 MiB are
read in exact 64-KiB chunks, followed by a one-byte EOF probe: at most 8,193 read
calls with a reused bounded frame. A short body or extra EOF byte refuses the
observation rather than retrying. SHA-256 consumes only each actual bounded
chunk through the boot SUN provider; the final 32-byte result is privately owned
and callers receive a defensive copy. Neither provider naming nor the observed
digest independently establishes the runtime's provenance or approved identity.

Before each native read the candidate marks completion unconfirmed. Only a TRUE
result with a bounded returned DWORD count permits reuse or retirement of its
private buffers. A thrown call, FALSE (including pending), or contradictory count
retains the entire frame and original owners without further calls from this
candidate, clearing or closure. Short/EOF semantic refusal after confirmed native
completion can retire its private frame. Original handles and arenas never close
here. Byte/call bounds are not a wall-clock cancellation guarantee; the outer
execution deadline remains separate. This candidate does not globally seal other
independent original-file metadata attachments after its failure.

Eleven fresh-process inert upcall controls cover count/return bounds, confirmed
retirement, uncertain-frame preservation, thread/call limits and no retry. On
Windows they use actual Windows argument/error-capture mechanics, not actual
filesystem I/O. The separate Windows `bytes` control executes real `ReadFile`
against the original development-JVM file and compares its digest/length with a
separate bounded JDK read of the selected development runtime fixture. That test
path is not a production input or Foundation's independent expected runtime pin.
No bytes, pathname or digest is printed by the fixed test result.

Held-file hashing is **not** loaded-image identity, protection from pre-existing
writable mappings, first-call authority, installed package approval or productive
provider activation. Windows loading and original JNI/provider assembly still
require the independently established startup/package/runtime boundary.

## Fixed packaged byte-verifier connection

`WindowsPackagedVerifier` connects this named module to the existing Java17
`WindowsProfilePackagedVerifier` in the maintained application's system
classloader. It uses only fixed public method signatures and fixed class names;
there is no caller-selected classloader, accessibility override, module-read
change or classpath fallback for the adapter. The original compiled JNI
declaring class is retained without initializing it or calling any native method.

The Java17 helper reuses the maintained PE, manifest, mapped-header/code,
full-IAT and JNI-plan verifiers rather than copying their parsers. It snapshots
bounded inputs before multiple comparisons. Plans expose defensive copies of
original image/export bounds, import/export inventories and page-bounded read
requests. Complete readback comparison returns the 23 JNI addresses in their
fixed registration order plus the separate registrar address. The named-module
side independently bounds returned arrays, ranges, names and address relations.

These are **data comparisons, not native-call authority**. Input pins must later
come from an independently approved package; supplied addresses and page arrays
must later come from the loader's original retained owners and constrained reads.
Matching data, a system classloader relationship or a returned declaring class
does not establish installation, loaded mappings, import-provider identity or
permission to register JNI. No library is loaded by this bridge, and the public
productive loader continues to refuse. Test fixtures remain outside both
production artifacts; connected development-JVM tests are not installed-runtime
or protected-profile qualification.

## Actual loaded development DLL connection

On Windows, the maintained adapter checker additionally builds a **separate
test-only DLL** from the original policy, JNI and registrar sources plus the
existing aborting `deny_storage.c` backend. It never compiles `profile_win32.c`,
stages this DLL to application resources, installs it or changes production
availability. All storage methods abort; only ABI/capability JNI calls execute.
Other hosts compile the Java fixture but explicitly report native execution as
`UNSUPPORTED_HOST_NOT_EXECUTED`.

The fixed MSVC recipe records clean source/tree, selected direct source/header
and tool hashes, compiler arguments and original DLL length/hash **before** any
execution. This is bounded test provenance, not an independent installed package
identity or a complete transitive SDK provenance claim. Actual fixture execution
requires a clean checkout. Raw records remain within the existing component's
private reports and supervisor; no replacement process supervisor is introduced.

Three fresh JDK21 processes run with `-Xcheck:jni`, the dedicated module's native
access and explicit `jdk.unsupported`. They check pre-load wrong-pin refusal,
successful registration/lifetime and native rejection of one wrong JNI address.
The test retains the original file without write/delete sharing. It uses the
unchanged conditional bootstrap, original JVM acquisition, constrained DLL load,
exact export lookup, mapped headers/code/full-IAT readback and packaged byte
comparison before calling the original registrar. Expected imports come from
separate fixed kernel32 resolution and physical SystemDirectory module pins,
never from the candidate's IAT. No parser/import allowlist is relaxed for the
fixture. Successful calls return the actual partial ABI13/capabilities `0x43`,
not the full provider's different contract. Original owners remain retained
after private frame retirement, failed registration and a GC request. No unload
is introduced behind registered JNI addresses.

These tests connect genuine development DLL, Windows FFM and JNI mechanics;
they do **not** establish a trusted first OS call, installed ancestor/ACL
authority, production provider assembly, protected NTFS storage, ordinary-user
admission or installed Host/Client qualification. The public productive factory
must still refuse in every case. Test classes and the deny-storage DLL are
excluded from the production adapter and canonical MSI inputs.

The compiler has a distinct cumulative 150-second budget, including source/tool
observations and hashing. Each tool/Git call keeps its existing 15/60-second
phase cap, shortened to the remaining total. Only its outer wrapper permits
180 seconds so terminal receipts/retirement do not compete with the compiler's
work budget. All existing JVM controls and actual DLL/JNI children retain their
60-second bounds; canonical whole-component supervision is unchanged. Portable
inert-clock regressions verify this composition and failure reporting,
not real compiler timing. A timeout records an uncompleted command instead of
losing it or inventing an exit; original diagnostics stay private and public
failure labels contain only the fixed phase/timeout category. Neither an inner
timeout nor a receipt alone proves descendant retirement.

The test compiler selects the installed x64 MSVC toolchain through fixed
`vswhere` metadata and its bounded default-version file. It reads only the fixed
Windows Kits installation-root registry value in the two registry views,
requiring agreement when both exist, and selects an explicitly complete installed
SDK. It constructs child-only `PATH`, `INCLUDE` and `LIB` from those selected
directories and invokes the absolute compiler directly, without a command shell,
`VsDevCmd`, optional setup extensions or an inherited compiler response flag.
Selected inputs and toolchain selection are checked before and after compilation.
This is development-tool binding, not installed-runtime authority. No machine
environment, registry, installed tool, compiler security flag, execution policy
or native-test deadline is changed. Earlier setup timeouts remain failures;
their exact internal Visual Studio setup cause has not been established.

The loaded-registration test emits a bounded closed failure projection containing
only its fixed stage/category/source-site identifiers and a bounded source line.
It never emits argument values, paths, exception messages, native addresses or
payload bytes in that projection. The original failure still fails the process
and its full traceback stays in private evidence. An inert formatting control
runs without native access on every supported development host. The projection
helps locate a failed connection boundary; it does not turn an attempted load,
registration or cleanup into a pass or establish productive installation authority.

After a mapped comparison refuses, the same test may additionally classify its
already-copied synthetic readbacks: header/code, original/padding/relocation,
within-page offset, whether the complete header page equals the same pinned file
prefix, and whether all executable bytes match their original/DIR64 expectation.
This closed test-only projection performs no additional native call and never
changes the strict comparison or its original failure. It exposes no readback
bytes, process address, path or arbitrary message; it cannot authorize loading.

### Fixed application-to-provider connection

The Java17 application now has a zero-argument installed-provider entry. It
resolves only the exact original boot-layer loader module and invokes its fixed
zero-argument API. There is no supplied path, backend, classloader, owner token
or permission flag. The current loader **still always refuses**. Its private-
constructor typed `Unavailable` result denotes refusal before installed/native
acquisition; generic loader exceptions remain uncertain, not retryable success.
Windows profile selection occurs before any POSIX home-directory resolution.

Only a future successful production-loader return may construct the private
managed composition. Its distinct adapter contract is ABI1/`0x7f`; the underlying
native ABI remains **13/`0x43`**, checked before every storage operation. Existing
composed writes/deletes, namespace synchronization and ownership are reused.
Normal loader return must first establish the independently authorized production
artifact, runtime and original JNI owner, retained for process lifetime. The
development deny-storage DLL deliberately has the same raw ABI and is **not**
sufficient. Profile Stop cannot unload that owner. Availability/UI gates remain
unchanged until productive admission exists; neither these model tests nor the
actual cross-module typed-refusal test qualifies installed Windows operation.

### Exact ASLR header comparison

For the supported `DYNAMIC_BASE` image mapping, the byte comparator requires the
loaded PE header's eight-byte `ImageBase` to equal the original module mapping
base. Its field offset comes from the independently pinned and structurally
verified PE header, not a compiler-specific constant or loaded metadata. This
is one exact derived expectation, **not** a mask or acceptance of both original
and arbitrary rebased values. Every neighboring header byte, header-page tail,
executable byte and validated DIR64 update remains checked. Unsupported mapping
modes that do not satisfy this exact relationship still refuse. This comparison
provides no initial loading authority or ownership by itself.

### Conditional system-import resolution

The named module now owns the kernel32-only import resolver previously confined
to the development fixture. It takes the original byte-verifier plan through an
exclusive typed attachment to the original bootstrap. It refuses unsupported
logical libraries, malformed names, ordinals, duplicates and oversized inventories
before any resolver native effect. Original module PINs, raw entry addresses and
scopes remain retained on success and failure; an uncertain native return
quarantines its private frame instead of clearing or freeing it. There is no
unload, generic owner token, fallback search path or caller-selected system DLL.

The actual development test resolves these independent targets **before** loading
the test DLL, then compares the complete loaded IAT to those targets. It does not
derive expected addresses from the IAT. This is still conditional mechanics:
`GetProcAddress` may load a forwarded provider before its later physical-path
observation. A trusted startup and forwarder policy must precede productive use.
The production native DLL also imports advapi32, ntdll, shell32 and ole32; those
logical libraries are explicitly refused by this bounded component pending the
full provider-policy integration. No full-provider or installed-runtime claim
follows from the kernel32-only development test, and productive loading remains
unavailable.

### Original file-lease composition

The original JVM file facade now delegates its unchanged native acquisition,
metadata and retained-handle mechanics to one concrete `WindowsOriginalFileLease`.
This isolates the existing algorithm for later independent DLL custody without
copying it or substituting a DLL path into the JVM observation. The core accepts
only its exact original JVM facade or the independently attached, final profile-
DLL facade. These are two concrete owner types, not a caller-supplied authority,
native-entry callback or interchangeable `Object`. The private original path is
copied, and the core/facade and preallocated failure carrier remain rooted before
native effects.

Security, ancestor and byte observations still attach to that original facade
and use the same original file handle. Their existing implementations and policy
decisions are unchanged. A Windows-only combined observation exercises all three
children together, checks original ownership after retirement and reports leaf
and ancestor policy acceptance separately. A completed diagnostic with refused
ACL policies is **not** an admitted file. Neither the combined development-JVM
observation nor inert owner/frame controls qualifies a production DLL or an
installed protected profile. No handle/module unloading or productive activation
is introduced.

### Independent original DLL file attachment

The original bootstrap can now attach one independent profile-DLL file candidate.
It does not obtain, relabel or replace a JVM-file observation. Its pathname is only
an untrusted locator: the exact fixed DLL basename and canonical local-drive
subset are shared with the existing load invocation. Path refusal occurs before
file effects; the caller cannot supply native entry addresses, a file handle,
metadata, a byte buffer or an installation-authority flag. Fixed metadata bounds
are 512 bytes through 32 MiB for this DLL role; the JVM streaming limit is unchanged.

The same native file algorithm retains the original read-only/no-write-or-delete-
sharing handle, repeated metadata, final-path correspondence and permanent scopes.
The DLL attachment is one-shot; failure retains its original graph and precludes
continuation. Portable controls cover locator/owner substitution and failure
latching. A separate Windows development-fixture case actually acquires the
compiled deny-storage DLL through this new path, without loading it or creating
an original-JVM-file attachment. Separate fresh processes verify a genuinely
absent file's retained native refusal and a malformed locator's refusal before
file acquisition. This scope is distinct from the existing later constrained
test-DLL mapping and JNI cases, which are preserved unchanged.

The shared file algorithm now quarantines its private frame if an FFM invocation
does not provide an observed normal primitive return. A normal failed Win32
result is still a completed call followed by semantic refusal, not pending I/O.
These fixed Win32 APIs are synchronous; this conservative return-provenance rule
is not evidence that they perform asynchronous buffer writes. Known-return and
pre-invocation failures retain their existing private-frame retirement, and
original handle scopes are never closed.

**This is not yet a complete DLL custody or productive loading pipeline.** The
independent DLL still needs independently approved package/runtime identity and
reviewed startup/import/load assembly. Its original-handle security, ancestor
and bounded snapshot components are described below; existing JVM observations
are not promoted into DLL evidence. No productive-loader return, Windows UI
availability, profile operation, installer identity or publication pipeline is
changed by this component.

### Shared original-handle OWNER/DACL query

The original JVM and independent DLL security attachments now use one concrete
native query engine. Their exact original file and handle owners remain distinct;
a DLL cannot select a JVM facade, supply a replacement handle or choose a native
export. Original facade/core/failure roots precede every native effect. Existing
JVM ancestor inspection still follows its own original typed chain and retains
its unchanged policy and native algorithm.

The DLL query uses its original read-only handle's READ_CONTROL access for the
fixed bounded OWNER|DACL request. It grants no privilege and requests no SACL.
Module PINs, raw resolved entry, original handle and scopes remain retained. An
unobserved normal native return quarantines private buffers; normal failed native
results remain failures. `GetProcAddress` is captured as a primitive before any
address wrapper is allocated. These conditional mechanics do not authorize the
first system call or possible forwarder execution.

Completion of a diagnostic query is separate from descriptor-policy acceptance.
A native/retirement failure permanently latches the DLL file and security owner.
An ordinary policy refusal remains readable as a completed diagnostic, but seals
the DLL file's native-input accessors, including direct typed-bootstrap access.
Neither an accepted leaf policy nor an inert descriptor test establishes ancestor
custody, initial OS/runtime trust, package identity, mapped-image correspondence
or absence of pre-existing writable mappings/security handles. Productive loading
and provider activation remain unavailable until the entire boundary is complete.

### Independent DLL ancestor ownership

A concrete shared ancestor engine retains the existing JVM walk while adding a
separate original DLL security → ancestor attachment. Every factory preserves
the original file handle, pathname snapshot, metadata and system/module scopes;
no caller chooses a handle or substitutes a JVM file as DLL authority. Root and
handle-relative directory leases remain retained, and the final leaf probe must
match the independently held file. Existing descriptor, reparse, case, volume,
filesystem and metadata requirements are unchanged.

The DLL's refused leaf policy prevents ancestor attachment before native effects.
A fully completed ancestor observation may itself report refused policies: its
Java diagnostics remain readable, but subsequent native-input factories are
sealed. Native/retirement failure instead permanently latches the original DLL
file/security chain with its retained failure owner. Unknown native returns keep
private frames quarantined; the separate stricter NT completion/IOSB checks are
preserved. No normal Stop can unload or close these owners.

The maintained actual Windows diagnostic reports
`NOT_EXECUTED_LEAF_POLICY_REFUSED` if the development DLL's real leaf policy
refuses. That is an exercised refusal, **not** successful DLL ancestor traversal.
An accepted leaf permits the real bounded walk and reports its actual policy
result. No ACL, privilege or classification is changed to manufacture acceptance.
The unchanged real JVM walk exercises the shared mechanics separately; neither
scope is productive installation, complete byte custody or first-load authority.

### Copied system-export data and bounded forwarders

`WindowsSystemExportPlan` parses immutable copied AMD64 PE export data without
performing any native call, lookup or library load. It is intentionally separate
from the profile PE parser: the latter still requires its exact native exports
and refuses forwarders. This new data component handles unequal name/function
counts, ordinal bases, aliases, holes and named/ordinal forwarders. It resolves
only an explicitly supplied finite module inventory to a terminal module/RVA;
it does not use candidate IAT addresses or infer API-set mappings.

Inputs are bounded to sixteen files, 32 MiB each and 128 MiB in aggregate. Parsing
has an 8-million-unit work budget; resolution permits at most sixteen visited
export nodes, including the terminal node. Names and strings are bounded and
copied; rounded virtual/raw section overlaps and ambiguous metadata are refused.
A terminal target must occupy original raw-backed readable executable,
non-writable bytes outside inspected export metadata. Cycles, absent providers,
unknown API-set contracts and incomplete/malformed graphs refuse.

These are **data checks, not system-library identity or load authority**. The
productive resolver still needs the actual supported-system forwarder closure,
independently trusted original module/file leases, verified byte-to-mapping
correspondence and bootstrap authority before consuming any resulting RVA.
Merely expanding the existing kernel32-only `GetProcAddress` allowlist would not
solve its potential implicit forwarding effects. The new reader does not enable
that path, change productive loading or claim real-system graph qualification.

### Same-original-handle DLL byte snapshot

The independent DLL file may attach its byte reader only after its own leaf and
completed ancestor policies accept. The concrete shared engine retains the
existing JVM hash-only path and adds a bounded DLL snapshot from the **same
original synchronous file handle**, not the relative ancestor leaf probe. There
is no pathname reopen, second channel, seek, selectable native export or caller-
supplied byte limit. A DLL is 512 bytes through 32 MiB; existing JVM hashing retains
its separate 512 MiB bound.

The full operation checks original metadata before and after its reads, reads
64 KiB chunks with an exact final EOF check (at most 513 calls for the DLL), and
hashes the same ranges copied into the private snapshot. Whole-stream success
and snapshot/digest getters are published only after successful frame retirement.
Short, excess, false/pending, contradictory or throwing reads, changed metadata
and retirement failure cannot expose a completed partial snapshot. Unknown
native completion retains private frames and all original owners. Failure latches
the DLL file; Stop does not unload or close original module/JNI ownership.

Maintained inert full-stream controls execute the actual shared stream logic
with explicitly test-injected Java method handles; they are not native file-I/O
proof. The existing real Windows JVM ReadFile checks remain separate. The actual
DLL diagnostic reports its original leaf/ancestor refusal as `NOT_EXECUTED_*`,
without attaching or running the byte stage. Only admitted prerequisites permit
its real read and `COMPLETED` snapshot observation. Neither result grants package
identity, byte-to-mapping correspondence, initial OS authority or productive
provider admission.

### Original byte owner to the fixed packaged verifier

The original DLL byte facade now attaches the existing `WindowsPackagedVerifier`
exactly once, before snapshot or helper initialization. It supplies only its own
completed snapshot and digest; the digest of that exact private clone must match
before the unchanged Java17 PE, manifest, mapped-code and IAT algorithms run.
There is no caller DLL array, reopened pathname, native entry or callback in this
connection. Every owned result getter and comparison requires the original byte
attachment and retained file chain; an operation failure seals that file through
its original failure carriers. Ordinary wrong-thread or duplicate refusal before
effects does not poison a good completed owner.

The supplied manifest/source/tree pins remain **comparison data**, not evidence
that Foundation admitted their origin. The unchanged unowned verifier still
supports inert comparisons and cannot turn into an owned verifier. Twelve
maintained cases use explicitly fabricated inert owners and the real compiled
Java17 helper; they do not establish native custody, installed class provenance,
maximum-size end-to-end heap sufficiency or productive loading. Original helper
and JNI declaration hashes are checked separately by this test connection.
The loader still requires independent package/runtime authority, complete system
provider custody and mapped-image/import verification before activation.

### Bootstrap and JVM call-return quarantine

The original bootstrap and JVM continuations retain their private call frames
when any fixed downcall fails to return normally. No clearing, closing, retry or
success publication follows uncertain completion. Normal-return primitives,
including the Windows-x64 `GetProcAddress` result, are retained before allocating
pointer views. Retirement requires the original thread and cannot close module
or JVM lifetime scopes. Eighteen inert fixed-call/retirement controls cover these
paths; two wrong-thread regressions also fail against the prior implementation.
These are conservative failure/lifetime controls, not a demonstrated asynchronous
Windows exploit or approval of the first-OS bootstrap. Actual Windows calling
conventions remain covered by the separate original-JVM runtime checks.

The fixed named-export invocation likewise captures the Windows-x64 `FARPROC`
return bits before allocating a Java segment view. Exact original nonforwarded
RVA comparison still precedes publication. An unobserved downcall return retains
the complete private ASCII frame; repeated retirement cannot clear or close it.
Failures before native entry still retire normally. Its 22 inert controls use an
independent pointer-returning upcall descriptor, including post-return readback
failure and an unknown Java return. This neither admits the caller's bootstrap
nor turns an unverified system export into productive loading authority.

Original-image queries and reads likewise retain their private frames when a
`VirtualQuery` or `ReadProcessMemory` downcall has no confirmed Java return.
Each primitive result is recorded before captured-error/metadata readback. Known
return followed by a readback failure permits ordinary frame retirement; unknown
return never permits clearing, closing, retry or result publication. Six focused
inert controls distinguish those paths, alongside the existing image/protection
controls. These are lifetime-policy regressions, not evidence of asynchronous
Win32 behavior or of original mapped-file identity.

### Explicit protected development read fixture

`verifyRpcWindowsLoaderJdk21` accepts the default-false property
`-Pp2pkit.rpc.windows.protectedDevelopmentFixture=true`. Only the canonical
Windows JVM component selects it automatically; ordinary developer controls
do not require administrator rights. Unsupported hosts or insufficient existing
rights fail the requested test, without elevation, account creation, privilege
changes, ancestor ACL repairs or fallback storage. The existing temporary-DLL
refusal cases and separate deny-storage DLL/JNI controls remain unchanged.

The test-only helper resolves Program Files through the OS, checks and retains
its original fixed-NTFS, no-reparse, case-insensitive, policy-accepted ancestors,
then exclusively creates one nonce-named directory and compiler-pinned DLL copy.
Initial protected security grants mutation only to SYSTEM/Administrators and
ordinary Users read/execute. Existing objects and application profiles are never
modified. Original metadata-only handles remain held; the writer is closed before
the Java child. The actual reader must complete accepted file/ancestor policies,
same-original-HANDLE bytes and the fixed Java17 PE comparison with independent
compiler pins. No candidate DLL is loaded or used to authorize itself.

After the fixed reader's known successful exit and closed captures, a one-shot
nonce handshake permits deletion through identity-verified original-object handles.
The file uses `ReOpenFile`. On the observed NTFS test host, directory `ReOpenFile`
failed with error5; an independently verified `OpenFileById` directory handle then
failed `FileDispositionInfo` with error87. These are retained runtime failures,
not a universal API prohibition or the historical credentialed-launch error87.

Directory cleanup now uses one primary `CreateFileW(OPEN_EXISTING)` reopen through
the original held directory's volume-GUID path, bound to the original held volume
root and immutable fixture suffix. There is no caller/DOS-alias path, alternate
lookup or retry. All retained ancestor identities and owner/ACL/reparse policies
are rechecked before any deletion and again before directory disposition. The
returned handle must match the complete original 128-bit ID, volume, GUID path
and exact protected security descriptor; the original directory handle remains
held and is rechecked too. Only then may the same verified handle mark the empty
directory for deletion. This changes lookup mechanics, not identity authority:
no `RemoveDirectory` or other path-based deletion is used. Failure, EOF, timeout or uncertain
completion preserves the fixture, fails the gate and leaves the existing outer
supervisor responsible for uncertain descendants. No recursive path cleanup or
retry is performed. The reader's 60-second limit and 128MiB heap are unchanged.

Thirty-six portable controls cover closed receipts, handshake ownership,
bounded installed-SDK header selection and privacy-safe terminal diagnostics.
On cleanup failure, only a fully retired helper with two original-bound receipts
may export a fixed stage and bounded Win32 code. Otherwise the diagnostic is
`UNKNOWN/0`; unfinished captures are never read. The create-only diagnostic
contains no nonce, object IDs or paths and cannot replace the original failure. The positive Windows test is separate:
`NOT_REQUESTED` is not a pass, and a requested policy refusal is not a skip.
This is administrator **development-file/PE coverage**, not standard-user
protected-profile storage, MSI installation, productive JNI/Host–Client testing,
approved bootstrap authority or W01–W11 qualification. No helper/test input enters
production resources, the adapter JAR, MSI or publication artifact inventory.

Directory diagnostics distinguish GUID-path query, primary open, returned-identity
verification and disposition. Historical ID-query/open and `DELETE_DIRECTORY`
stages remain admitted for their original records, not relabeled. Ten additional
native-helper self-test predicates cover GUID/suffix validation; their inert
success is not evidence that actual cleanup passed. The corrected live sequence
still requires a fresh successful reader and complete fixture-cleanup receipt.

### Original system-module disk observations

The dormant bootstrap can attach one fixed eight-slot observation cohort:
`kernel32.dll`, `advapi32.dll`, `ntdll.dll`, `shell32.dll`, `ole32.dll`,
`kernelbase.dll`, `sechost.dll` and `combase.dll`. Each module must already be
loaded; the collector only pins it. There is no load fallback, caller-supplied
module list, path, symbol provider, API-set routing or authority token. All eight
original module/failure owners exist before the first native effect. Unknown
PIN/path return retains the complete original argument frame and seals the attempt.

The same concrete file, security, ancestor and byte engines now have a third
closed owner role. System files admit a positive unsigned-32-bit link count as
observed metadata, compared at each original metadata revalidation boundary; they
do not enumerate hard links or claim count-based custody. Existing JVM/profile
files still require exactly one link. Each fixed system file must pass original
HANDLE security and ancestor policy before bounded original-HANDLE snapshots
reach the existing copied export parser. The original pinned ntdll query provider
must match its fixed cohort slot. No graph is published from a partial cohort.

The read-only Windows observation reports `MODULE_ABSENT`, `LEAF_POLICY_REFUSED`,
`ANCESTOR_POLICY_REFUSED` or `COMPLETE`, with bounded stage counts. A refusal is
an honest diagnostic, not successful graph resolution or loading qualification.
Only `COMPLETE` can resolve the fixed export queries. The parser's existing
128MiB aggregate-input cap is not a 128MiB heap guarantee: original snapshots
and defensive input copies coexist. Allocation failure retains owners and fails;
the test heap and deadlines are unchanged.

These disk observations still do **not** establish the original mapped
section/file-ID association, full transitive OS load closure, independent
first-OS/bootstrap authority or installed-runtime provenance. The resulting
export targets are copied data, never callable capabilities. Production loading,
JNI activation and provider availability remain unchanged and fail closed. The
four added production owner/failure classes are explicitly included in the static
75-class adapter inventory; both new test classes stay outside production JARs
and application resources.

### Original five-library import comparison

The owned packaged verifier can now bind its verified import tuples to the
complete eight-module cohort already attached to its original byte/file/bootstrap
owners. It accepts no replacement cohort, module names or expected addresses.
The copied export graph follows bounded fixed-library forwarders, retaining each
original terminal provider and RVA. Its predicted addresses remain **data**, not
callable authority or proof that disk bytes match a loaded section.

Once bound, mapped-page comparison requires the exact ordered original targets;
caller-supplied pages and targets cannot agree on a substituted import. Original
owner, thread, scope and graph checks continue on every operation. Failure seals
the original file/byte roots and retains the cohort and partial comparison data;
no partial result, retry, GPA fallback or native load follows.

Twenty-two inert-owner controls exercise all five import libraries, forwarders,
IAT substitution, missing/failed cohorts, partial resolution and owner/lifetime
changes through the real compiled Java17 PE helper. They do not establish native
custody, mapped-module identity or installed authority. The unchanged 75-class
production inventory excludes these tests; productive loading remains unavailable.

### Original launcher/ancestor custody candidate

`WindowsSystemBootstrapCandidate.inspectOriginalInstallation()` is a dormant,
read-only attachment under the documented trusted OS/JVM startup assumption. Its
own bounded `GetModuleFileNameW(NULL)` frame observes the original process launcher
before profile-file effects; the concrete installation owner then retains the
existing file, leaf-security and handle-relative ancestor leases. It neither
borrows a JVM/system owner nor relaxes the non-system single-link or ACL policy.
Negative policy results remain diagnostics and cannot permit later native input.

The recognized `P2pKit Sample.exe` layout and retained directory chain are **not**
Program Files, independently qualified MSI, mapped backing identity, pre-JVM
integrity, installed-byte or standard-user acceptance. This increment does not
read installed bytes, load a profile DLL, expose a raw handle/callback, or connect
the candidate to the productive provider. `WindowsLoader.openInstalledProvider()`
remains unavailable. Inert owner/frame tests do not establish real Windows custody.

### Closed installed pre-load preparation (not provider activation)

The original installation owner now owns a one-shot, zero-argument preparation
of the fixed profile path. It requires the OS-resolved x64 Program Files root,
queried with fixed `SHGetFolderPathW` arguments through actual original
shell32/export/provider bindings, and joins the original JVM/profile ancestor
identities to the retained launcher root. The existing file/policy/byte and
system-import checks remain mandatory. A unique application parent-pin resource
must originate in the fixed original `app` directory; the sidecar is only bounded
comparison data. This is not whole-package self-attestation or proof of earlier
mapped backing/pre-JVM state; trusted startup and independent installed package
qualification remain explicit premises.

Only the concrete completed input child can enter installed load preparation;
the caller-path mechanics remain explicitly development-only. Preparation does
not invoke LoadLibrary, register JNI, publish a provider or change the permanent
public refusal. Owners stay confined to their original platform thread, with
failed/uncertain effects retained and no reset or retry. Inert tests and static
package checks do not qualify actual ordinary-user installation or native use.

The same prepared child has a separate package-private, zero-argument
`registerOriginalProfile()` continuation: its retained load result enters the
existing original mapped-image/import/export verification and then the existing
original JNI registrar. Each stage retains its exact original owner before
effects; failure seals the child without retry, unload or conversion to the
before-effects `Unavailable`. This continuation has no productive public caller.
Its new local controls exercise refusal/ownership/lifetime guards only, not the
successful installed load/verification/JNI path. The public loader still always
refuses; actual standard-user installation and native/provider qualification are
required before connecting it. Future profile opens must reuse the same completed
registration, never transfer or re-enter confined FFM owners from another thread.

The closed, package-private `WindowsLoader.completeOriginalInstalledProvider()`
now composes original bootstrap → installation → preparation → registration under
one process attempt. Only the initial claiming platform thread accesses confined
owners; subsequent completed reuse reads the safely published registration state
without exposing or revisiting those owners. In-progress calls refuse, admitted
failure remains sealed, and no attempt resets. The public entry still always
returns its original `Unavailable` failure; inert controller models do not execute
this first native composition or qualify an installed provider.

### Explicit installed admission diagnostic (not provider availability)

The single exact Desktop argument `--rpc-windows-installed-admission` selects
`MainKt` → fixed original boot-module `Probe.installedAdmissionReadback()` → the
closed original controller twice. It performs installation/runtime/profile-DLL
inspection, DLL load/image verification and JNI registration, then same-owner
reuse; it does not open profile storage, enter network/UI logic or enable the
public provider. No path, manifest, trust Boolean or module override is accepted.
Run it only as an explicitly selected native diagnostic of the independently
checked installed application under the documented trusted-startup model.

Success emits only clean source metadata and the fixed bounded admission/reuse
result. Failure emits one fixed nonqualified stderr code and exits nonzero;
original partial owners/failure remain process-rooted until exit. No relaunch,
unload, unregister or retry is attempted. Local seeded-state/connection controls
are not an installed positive: genuine standard-user installed execution and
later public-provider qualification/connection remain pending. Supervise that
future installed executable with the existing bounded Windows Job Object runner;
this diagnostic does not widen the GHA build-image readback wrapper or replace
its two no-native-load probes.

The failure line includes bounded `stage` and `operation` labels. For system-module
inspection, the operation distinguishes confirmed absence, descriptor-policy
refusal, the last entered file/export step, unknown native return and frame
retirement failure. `SLOT_ZERO` through `SLOT_SEVEN` refer, in order, to kernel32,
advapi32, ntdll, shell32, ole32, kernelbase, sechost and combase. `NO_SLOT` identifies
a collection-wide step. Labels are read only from retained Java state, including
failures thrown before the profile receives its collection reference; they do not
query failed native owners or disclose exception text, paths, SIDs or addresses.
A last-entered step is not proof of the underlying cause. A missing already-loaded
module still refuses admission; these diagnostics add no loading fallback.
