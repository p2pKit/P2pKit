# Windows profile component in the existing Desktop application

This is **packaging wiring, not Windows RPC runtime or release qualification**. The partial custody ABI remains 13,
with capability bits `0x43`; the Windows Host/Client availability gate remains disabled until independent first-load
admission, full provider capability integration and protected-profile runtime tests pass.

## Producer

On a Windows x64 builder with installed Visual Studio x64 C++ tools, Windows SDK and the repository's JDK 17 toolchain:

```powershell
.\gradlew.bat :p2p-sample-desktop-ui:stageRpcWindowsProfileNative
.\gradlew.bat :p2p-sample-desktop-ui:createDistributable
.\gradlew.bat :p2p-sample-desktop-ui:packageMsi
```

Use the existing dependency cache and strict dependency verification. These are existing-application build tasks,
not permission to install, run protected-profile probes, sign, publish or replace a previously frozen application.
No separate RPC installer, application identity, version encoding or publication workflow is introduced.

The Windows-only task graph is:

1. `verifyRpcWindowsPackagingSource` always observes an exact clean HEAD, including unrelated/untracked source changes.
   This admission is never an up-to-date result.
2. `buildRpcWindowsProfileNative` locates the installed x64 MSVC environment with Microsoft's `vswhere`, clears ambient
   compiler/include/library flags, and executes the existing `native/windows-profile/build-windows.cmd` with JDK 17
   JNI headers. It verifies source before and after compilation and records SHA-256 over bounded DLL bytes.
3. `stageRpcWindowsProfileNative` runs production byte-inspection code, verifies the canonical PE structure and all 23
   JNI exports, and produces the canonical component manifest. It never executes or loads the DLL.
4. `rpcWindowsParentPinJar` includes a separate parent-component pin resource. Existing Compose packaging includes this
   JAR and the platform resource directory. Compose's package-task `appResourcesDir` is `@Internal`: binding
   a provider alone neither schedules the resource producer nor tracks resource input changes. Each Windows
   package task explicitly depends on `rpcWindowsApplicationResources`, tracks its directory as a relative-path
   input, and verifies the resource binding before packaging. Ordinary `test`, `run`, compilation and source editing do not invoke the
   native producer; they do not require a clean checkout or MSVC because of this packaging integration.
   Compose 1.11.1 marks `AbstractJPackageTask.appResourcesDir` as `@Internal`; its provider alone does not schedule
   the resource producer. Every packaging task therefore declares both the package-only Sync dependency and a
   relative-path-sensitive resource input. The installed-image inspector must still verify actual inclusion.

Native resources are staged under:

```text
build/rpc-windows-profile/<source>/resources/windows/rpc-profile/windows-x64/
  p2pkit-windows-profile.dll
  component.manifest
```

Compose places the platform-relative `rpc-profile/windows-x64` directory beneath its installed application resource
root (`compose.application.resources.dir`). Packaging inspection must check the actual produced image and extracted MSI,
not infer successful inclusion from a task definition.

The separate `p2pkit-windows-profile-parent-pin.jar` contains:

```text
META-INF/p2pkit/windows-profile-parent.properties
```

Its canonical ASCII record binds source, tree, DLL digest and component-manifest digest, with explicit scope
`PACKAGED_COMPONENT_PIN_NOT_LOAD_AUTHORITY`. It is not accepted from the candidate DLL's adjacent sidecar. The packaged
runtime explicitly includes `jdk.unsupported` for `com.sun.nio.file.ExtendedOpenOption`; there is no dependency on an
ambient full JDK at installation time.

## Installer default

The existing MSI explicitly uses machine-wide installation with no directory
chooser. Its default is the platform's Program Files location; the application
name, MainKt entry, canonical version and MSI pipeline are unchanged. This
installer setting does not prove actual owner/ACL or ancestor safety, prevent an
administrator's command-line destination override, or admit the productive
provider. The actual installed root and ordinary-user behavior still require
runtime validation.

The MSI payload inspector verifies the actual decompiled package's x64
`ALLUSERS=1` default, `ProgramFiles64Folder` directory chain and absence of the
directory chooser. Its `installationDefaults` receipt is static package
validation only, not an installed-root or ACL admission.

## Failure and security boundaries

- Staging accepts an empty destination or an exact complete prior two-file byte stage. Partial, unknown, modified,
  wrong-architecture and wrong-export inputs fail rather than being repaired or loaded.
- Generated compiler outputs and failed partial stages are retained for inspection. A deliberately rebuilt DLL can
  differ from a prior build of the same commit (MSVC reproducibility is not assumed); an existing differing stage
  fails. Use a new isolated build directory for a new candidate rather than substituting bytes in a frozen image.
- The external component pin does not independently admit the parent application, filesystem ancestors, publisher
  signature, loaded-module identity, pre-existing writable mappings or native dependency loader behavior. These are
  still mandatory first-load and runtime policy requirements.
- Compilation and byte inspection are not Authenticode validation, installed-MSI execution, protected standard-user
  profile testing, power-loss evidence or release readiness.
- If signing changes DLL bytes, regenerate pins only inside the reviewed existing final-artifact producer after
  signature verification. Never re-sign or rebuild a frozen post-publication application set.

See [Windows provider integration](windows-profile-integration.md) and
[maintained application integration](maintained-app-integration.md) for the remaining runtime and release boundaries.

## Builder-only payload inspection

`verify-rpc-windows-app-image.py` checks the actual existing app image against its compiler record and
component/parent pins. It checks the bundled runtime's module declaration, not class resolution or startup.
Compose can mangle the packaged JAR filename using its content-based naming rule; inspection verifies that rule
without treating its MD5-derived suffix as a security digest. Whole-JAR SHA-256 and the canonical embedded pin
remain the byte bindings.
`verify-rpc-windows-msi-payload.py` compares the exact DLL, manifest, whole parent-pin JAR and, when selected,
the preview-adapter JAR after a bounded,
source-bound static WiX `dark` extraction of that same MSI. It checks concrete installed target paths and the
extracted bytes; it does not install the MSI or execute custom actions.
It also requires the entire MSI application File-table payload to match the
completed image: launcher, configuration, runtime and application files. Only
`app/.jpackage.xml`, which the pinned JDK producer deliberately does not install,
is excluded; its observed hash is recorded separately. The receipt records the
complete inventory digest, file count and byte count. This does not cover MSI
custom-action resources, an actual installation or pre-JVM startup integrity.

The modular `desktop-windows` component invokes `scripts/inspect-rpc-windows-package.py` after its existing
Gradle installer task. This wrapper runs the two maintained inspectors and the installed WiX tool through
the shared `ci_evidence.run_command` supervisor. The four-component comparison is mandatory when the
preview adapter is packaged. Source/run identity, bounded decompiled MSI metadata and tool/comparison
receipts are retained under `build/reports/rpc-windows-package/` through the normal encrypted CI evidence
collection. The complete extracted payload stays outside reports in ephemeral `RUNNER_TEMP`.

These checks preserve explicit `NOT_PERFORMED` installation, native execution, runtime qualification and signing
states. Static equality is useful packaging evidence but not Windows RPC provider or full-application acceptance.

## Existing launcher runtime-module probe

The maintained `MainKt` entry accepts exactly `--rpc-windows-runtime-readback`. Before creating the UI it
resolves the real boot-layer `jdk.unsupported` module, its `jrt:` location and package export, and the actual
`ExtendedOpenOption` constants `NOSHARE_READ`, `NOSHARE_WRITE` and `NOSHARE_DELETE`. Missing or wrong modules
fail without profile access or P2pKit native loading. The fixed public JSON includes clean source identity
and the observed Java version; it never prints profile data or host paths.

The code compiles against JDK 17. The probe accepts reviewed runtime features 17 and 21 and reports the one
actually executing; it does not change the existing producer's runtime. Compose strips native JDK commands,
so a bundled `bin/java.exe` is not assumed and no second launcher is added. The hosted builder invokes the
existing app executable with bounded output/time, pins its launcher/config/runtime/application bytes, checks
the returned module result against the image metadata, and records ordinary process exit. This is build-image
module resolution only, **not** installation, standard-user protected-storage tests or Foundation's required
whole-lifetime installed-app supervision. Those remain separate integration gates.

In modular CI, `scripts/check-rpc-windows-image-runtime.py` follows the static package check. It runs both
existing `--rpc-windows-runtime-readback` and `--rpc-windows-loader-readback` routes, verifies their exact
responses against the source-bound image receipt, and checks the bound image files before and after
execution. The shared supervisor must report normal exit, closed captures and known cleanup. Receipts
and bounded private captures are collected from `build/reports/rpc-windows-runtime-readback/`; this does
not run the productive provider or change the installed-Windows acceptance requirements.

Both steps are required component tasks, not optional diagnostics. A focused `desktop-windows` dispatch
of `ci.yml` or `desktop-cross-host.yml` executes them without rerunning other platforms. Final aggregation
still requires every mandatory component on the exact same source; a focused pass alone is not release
qualification. The old branch-specific PowerShell hosted wrappers are not the active modular entry points.


### Exact Windows JDK producer input

Windows Desktop packaging with `-Pp2pkit.rpc.windows.previewAdapter=true` now
requires the source-pinned Temurin archive in
`native/windows-loader-jdk21/runtime-supplier.properties` under the RPC sample.
The maintained CI setup downloads that archive, checks SHA-256, and sets
`P2PKIT_RPC_WINDOWS_JDK21_ARCHIVE` to its local path. For an equivalent local
Windows build, download the same official archive, set that environment variable,
and set `JAVA_HOME_21_X64` to its extracted JDK root. CI uses setup-java's explicit
`JAVA_HOME_21_X64` installation, not Gradle's major-only toolchain search. The
path is only a candidate: do not change the pin to match an arbitrary installed JDK.

`verifyRpcWindowsJdk21` compares the selected JDK's complete ordinary-file
inventory against the verified archive before jlink, runtime checks and
jpackage. Each task consumes the verification result and checks its actual
selected tool directory. The receipt is retained through the existing encrypted
`build/reports/rpc-windows-runtime/supplier.json` report collection. A cache hit
or `java -version` alone is not supplier verification. This is a build-time byte check, not an immutable directory
lease, supplier signature verification or installed-runtime qualification.

The supported startup model trusts the original OS, installed launcher/JVM
and launching user's configuration/environment. The upstream jpackage
launcher can prefer a per-user configuration; the JVM also accepts ambient
VM options. Post-start Java checks cannot prove those inputs were ignored.
Protected installed-root admission, original module continuity and real
ordinary-user installed tests remain separate requirements. This producer
check does not activate Windows RPC, relax its refusal checks, replace MainKt
or create another MSI/release pipeline.

## Explicit installed-admission diagnostic

The exact installed Desktop argument `--rpc-windows-installed-admission` invokes
only the original boot-module admission chain and same-owner reuse, then exits
without UI, profile-storage or network entry. Unlike the two build-image
readbacks, this explicitly performs DLL load/image verification/JNI registration;
operator selection of this native diagnostic does not enable the public provider.
Its bounded result and retained failures are described in the
[adapter contract](../../samples/p2p-sample-rpc/native/windows-loader-jdk21/README.md#explicit-installed-admission-diagnostic-not-provider-availability).
Actual standard-user installed execution of the independently checked exact
package/runtime remains required; source/model controls are not that evidence.
