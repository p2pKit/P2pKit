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
`verify-rpc-windows-msi-payload.py` compares the exact DLL, manifest and whole parent-pin JAR after a bounded,
source-bound static WiX `dark` extraction of that same MSI. It checks concrete installed target paths and the
extracted bytes; it does not install the MSI or execute custom actions. The guarded hosted test retains the
three compared component copies and tool/byte receipts, not the complete extracted application/runtime.

These checks preserve explicit `NOT_PERFORMED` installation, native execution, runtime qualification and signing
states. Static equality is useful packaging evidence but not Windows RPC provider or full-application acceptance.
