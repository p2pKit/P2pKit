# Actual development-JVM registration component controls

`../../check-jvm-registration.py` compiles the unchanged registrar, JNI translation unit and policy source
into a **test-only development-JVM executable**. Its separate storage backend aborts every `pwp_win_*` entry. It does not
compile `profile_win32.c`, load the Windows profile DLL, authorize a candidate, or alter the production selector.
The default four cases call the registrar directly; optional `--ffm` adds the connected controls below.

On macOS, supply existing trusted absolute `--clang`, `--sdk`, `--jdk` (JDK21), and `--classes` paths, plus a **new** private
`--output` directory outside the checkout. `--classes` must be this checkout's existing
`samples/p2p-sample-rpc/build/classes/kotlin/jvm/main`. No compiler/runtime downloads or Gradle rebuild occurs.
The two real custody classes are copied byte-for-byte into the private test classpath; no same-name Java fixture
or production storage exception class is supplied. Ordinary classes retain Java17, non-preview bytecode.

Four fresh-process cases use a real development JVM with `-Xcheck:jni`:

1. Before registration, the real `abi()` must throw `UnsatisfiedLinkError`. After actual registration of all
   23 original methods, only `abi()` and `capabilities()` execute: exactly 13 and `0x43`. They remain callable
   after a completed `System.gc()` request and duplicate-registration refusal. GC is not class-unloading proof.
2. A pre-existing synthetic Java exception is retained and cleared by the registrar; registration remains absent
   and a corrected retry is refused.
3. A mismatched expected original-symbol address refuses registration; a corrected retry is refused.
4. An empty classpath refuses the missing real application class, retains/clears its exception and refuses retry.

The test driver alone creates/destroys its development VM, retaining its runtime mapping through process exit.
The registrar never creates a VM or attaches a thread. All storage calls remain forbidden. Every process has a
60-second timeout and each output stream has a live 64KiB capture limit; nonzero exits, timeouts, unexpected output and JNI warnings fail the command. Receipts record
exact selected source/class/tool/image hashes and verify those inputs did not change. The existing class/source
observations do not replace the Gradle producer receipt, full compiler provenance or installed authority.

## Optional actual FFM-to-JNI connection

Add `--ffm` to retain all four direct controls and run three additional fresh-process cases. The same selected
existing JDK21 `javac` compiles the **unchanged** original loader `src/main/java` sources and the test-only
`RealRegistrationInvocationTest.java` into a private exploded named module. This adapter lives only here; it is
not added to the production JAR, Gradle source sets, normal gates or the inert model suite. Compilation uses
preview, `-proc:none` and `-Werror`; only the exact two expected preview notes are permitted.

The embedding C driver enables preview and native access **only** for `dev.p2pkit.rpc.windows.loader` in the boot
layer. It supplies its statically linked original registrar address, original 23-entry table observations and
its own already-created VM to the test adapter. Only this test boundary converts those explicitly supplied
process-owned numeric addresses into confined `MemorySegment` views. It does not discover candidate symbols,
interpret addresses as installation authority, or provide a productive loader. The retained test-process roots
keep those original scopes live; the C executable and loaded development runtime remain mapped through VM
shutdown and process exit. Private FFM argument/report frames are separately cleared and retired.

1. `ffm-success`: the real dormant `WindowsJniRegistrationInvocation.prepare` and exact
   `WindowsJniRegistrationOwner.registerOnce` execute the original registrar through an actual FFM downcall.
   The exact immutable success report, permanent owner and private-frame retirement are asserted. Before this
   call `abi()` is unbound; afterwards the actual compiled custody `abi()`/`capabilities()` return 13/`0x43`
   through JNI, including after a completed GC request and native duplicate-registration refusal.
2. `ffm-address`: the original registrar rejects a mismatched table address through FFM. The adapter verifies
   the exact phase-0 address-refusal report and failed owner; the real custody native remains unbound.
3. `ffm-missing-class`: the original registrar encounters the empty application classpath from the real FFM
   context and returns the exact class-refusal/retained-exception report without propagating a pending JNI
   exception across FFM. No substitute application class is supplied; the negative test's retention record
   uses the adapter class because the application class is intentionally absent.

All three cases reject managed re-entry/duplicate ownership, keep original scopes live after frame retirement,
and prove the native one-shot was consumed by a subsequent direct duplicate refusal. Every JVM runs with
`-Xcheck:jni` and must emit only its exact PASS line, with no JNI warnings. The receipt additionally binds original
module sources and compiler inputs, compiled test-module class hashes and their unchanged post-run bytes.
On macOS this exercises the host native linker, not the Windows x64 calling convention.

## Scoped hosted Windows x64 execution

The existing `rpc-windows` job runs these same seven cases after actual JVM-class compilation, including in its
explicit BUILD-ONLY mode. This is additional development-JVM component execution, **not** execution of the profile
DLL or custody smoke. No existing standard-user, account, profile-runtime or release admission changes.

Only the exact authorized hosted job/branch, clean source SHA, setup-selected `RPC_WINDOWS_JDK21` and fixed fresh
output directory are accepted. `--vsdevcmd` supplies the selected existing MSVC installation; it replaces the Mac
`--clang`/`--sdk` options, and `--ffm` is mandatory. The fixed C producer uses JDK21 headers, `/W4 /WX /MT`, x64 and
only the original policy/JNI/registrar plus deny-all backend/test driver. No `profile_win32.c`, `jvm.lib`, candidate
profile DLL, runtime download or alternate application launcher is built or invoked. Windows compilation evidence
must come from the hosted run, never inferred from Mac success.

Before creating its own development VM, the test-only Windows driver refuses an already loaded `jvm.dll`, removes
inherited/current-directory DLL search, sets default search to System32 plus user directories, and adds **only**
the selected JDK `bin` directory. It loads the exact canonical `bin/server/jvm.dll` using `LoadLibraryExW` with
DLL-load-directory/System32/user-directory flags, verifies the returned module's original path, and resolves only
`JNI_CreateJavaVM` from that retained handle. The module and directory cookie remain held through VM/process exit.
The controller hashes selected runtime `bin`/`lib`/headers before and after, and verifies test EXE/module bytes do
not change. These selected development-image observations are not installed-runtime/import authority.

Runtime children receive an explicit isolated environment with System32-only PATH and test-owned temporary/profile
directories, not ambient Java/compiler options. Only the separate compiler child receives selected VS setup and
fixed system-tool directories. Original native Win32 registrar atomics and Windows x64 FFM/JNI calling conventions
are exercised by the seven real JVM cases; all runtime output remains exact PASS lines with no JNI warnings.
Raw CRLF output is retained and normalized only for exact line comparison. Process/capture failures are fatal;
bounded direct-child ownership is not whole-descendant or Foundation supervisor qualification.

**This is real JNI registration and optional connected FFM component evidence, not productive Windows DLL loading,
original Windows module ownership/import verification, protected-profile storage, standard-user admission, an installed
runtime/app test, or complete supervisor qualification.** Global refs do not authorize or pin a Windows DLL.
The native partial ABI/capabilities and production-disabled loader remain unchanged.
