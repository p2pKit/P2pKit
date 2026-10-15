# Actual development-JVM registration component controls

`../../check-jvm-registration.py` compiles the unchanged registrar, JNI translation unit and policy source
into a **test-only Mac executable**. Its separate storage backend aborts every `pwp_win_*` entry. It does not
compile `profile_win32.c`, load a Windows DLL, authorize a candidate, alter the production selector, or use FFM.

Supply existing trusted absolute `--clang`, `--sdk`, `--jdk` (JDK21), and `--classes` paths, plus a **new** private
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
60-second timeout; nonzero exits, timeouts, unexpected output and JNI warnings fail the command. Receipts record
exact selected source/class/tool/image hashes and verify those inputs did not change. The existing class/source
observations do not replace the Gradle producer receipt, full compiler provenance or installed authority.

**This is real JNI registration component evidence, not productive Windows DLL loading, original Windows module
ownership/import verification, protected-profile storage, FFM invocation, standard-user admission, an installed
runtime/app test, or complete supervisor qualification.** Global refs do not authorize or pin a Windows DLL.
The native partial ABI/capabilities and production-disabled loader remain unchanged.
