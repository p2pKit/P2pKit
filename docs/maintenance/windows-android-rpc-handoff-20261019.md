# Windows and Android RPC implementation handoff

**NOT_READY for complete Windows qualification.** On 2026-10-19 the owner confirmed
that the Windows/Android functionality they tested now works, after the Android
Host approval repair. Record this as successful manual owner testing. It does not
establish every W01–W11 assertion, typed-error case, revocation scenario or the
required twenty complete installed lifecycle cycles.

This is the current handoff for RPC/Foundation. The
[Windows LAN/native checkpoint](windows-local-network-and-native-20261019.md) and
[earlier installed report](windows-rpc-completion-20261018.md) retain the detailed
preceding controls, source bindings and failures. Historical statements that
discovery or the productive provider was unavailable describe those older sources.

## Source and integration

Qualification branch: `work/windows-rpc-completion-20261018`. The previous remote
checkpoint was `dfdf1f248f816be3d40990dc2f772482db2f6bf6`, tree
`1f3d6becaa9ee87aafcf0a1618f58975513e1bd2`. Twelve subsequent commits implement and
document the Windows LAN/native work and the Android repair. A final report-only
commit contains this handoff; its SHA/tree are recorded in the campaign comment.

| Latest component | Commit | Tree |
| --- | --- | --- |
| Installed Windows app and bounded connection diagnostic | `643988b25109756e06d89cf2fb83b895a3fef16e` | `8ea6cc7514da6420d028ab6c68b21e61ce7f7edf` |
| Installed Android app / native socket repair | `a2d8593f5ffa47f20c84296d71d721531fad3ba1` | `47273f5586682c622b6eb3850ed6fa0e528fb4c0` |
| Final Android device verifier | `d51ab685b5c25c82d84eb264cb94d8ffa53c4b75` | `a5ad03d9557035c3a10840017100041faed16521` |

The other nine commits, including Windows native execution and IP-observer
ownership fixes, are described in the preceding checkpoint. Inspect the complete
implementation and changed-file inventory without resetting an existing checkout:

```bash
git fetch origin work/windows-rpc-completion-20261018
git log --reverse --format='%H %T %s' dfdf1f248f816be3d40990dc2f772482db2f6bf6..d51ab685b5c25c82d84eb264cb94d8ffa53c4b75
git diff --name-status dfdf1f248f816be3d40990dc2f772482db2f6bf6..d51ab685b5c25c82d84eb264cb94d8ffa53c4b75
```

Review these commits in an isolated branch. No independent reviewer approval is
claimed by this handoff. Do not overwrite Foundation/RPC work or infer a release
approval. No main merge, tag, release publication or policy change accompanies it.

## Productive changes

Windows LAN selection now observes original verified `iphlpapi.dll` exports and
`GetIpInterfaceTable` before and after Java enumeration. An interface is omitted
only when both native observations establish no IP binding and Java reports no
addresses/prefixes. Genuine competing LANs, inconsistent observations, unknown
ownership and unsupported flags still refuse. The completed acquisition handoff
retains the original module and callable ownership. There is no JDK17 fallback,
name exemption, environment-selected interface or first-peer substitution.

The native smoke runs through the existing supervisor with original executable
custody and process/job observation. Real cross-process contention now verifies
sharing refusal, later acquisition and unchanged identity. Productive encrypted
creation/reopen and password-refusal controls passed at their recorded sources.
The original thirty-second application budget and ten-second UI control budget
remain unchanged; the Back-stage failure is still a failure.

The Windows connection diagnostic preserves the original exception, cancellation
and cleanup behavior. It emits a bounded fixed-vocabulary cause/stage record,
without addresses, fingerprints, payloads, raw exception messages or retries.
Actual failed Android-Host attempts produced immediate authentication/socket
failure records, which led to the Android compatibility investigation.

The Android 10/API29 phone denied `android.system.Os.fcntlInt`, public only since
API30, while configuring an accepted Host socket. The LAN module now uses a small
NDK JNI helper to call `socket`/`accept4` with `SOCK_NONBLOCK | SOCK_CLOEXEC`
atomically, then verify the actual flags. The existing Network binding,
read/write/poll behavior, descriptor leases, pending-child retention and cleanup
remain in use. Strongly retained `ParcelFileDescriptor` owners close their exact
descriptors through Android ownership checks; native integers are borrowed under
the existing handle lease. No private Java fields, hidden Android APIs, process
route override or permissive storage/network fallback was introduced.

The Android helper exports `open(Z)I`, `accept(I)I`, `verifyFlags(I)I` and
`closeUnowned(I)I` on `dev.p2pkit.transport.lan.AndroidNativeSockets`. Its class
loader retains the library; consumer keep rules preserve JNI names. Android
identity/trust source is unchanged from the previously installed `506d3bda` app.
There is no protocol or persisted-data migration.

## Build compatibility and exact artifacts

Android builds now need **NDK `29.0.14206865`** in the existing SDK:
`sdkmanager "ndk;29.0.14206865"`. Only this missing local package was installed;
the supplied SDK packages were reused. The Android KMP plugin has no
`externalNativeBuild` DSL, so `BuildAndroidLanSocketsTask` registers its output
through AGP's JNI source API. All four Android ABIs target API24, with 16 KiB ELF
alignment, RELRO/NOW and non-executable stacks. The AAR and APK contain the exact
compiler-produced native bytes. See the
[native helper contract](../../library/p2p-transport-lan/src/nativeInterop/androidSockets/README.md).

Foundation must provision the pinned NDK in Android build jobs before consuming
this change. No workflow or release pipeline was changed here. Android API24–28,
API30+, other ABI runtime execution and shrinking-consumer runtime coverage are
not established by this single phone run.

Windows still uses the canonical Desktop module/MainKt, unchanged MSI identity
and sample sections, Java17 ordinary bytecode, pinned Temurin21.0.12.1+1,
`jdk.unsupported`, and narrowly named preview/native access. No module is unloaded
behind cached JNI addresses. The preview packaging option is not an enable switch.

| Bound artifact | SHA-256 |
| --- | --- |
| Windows `643988b2` MSI, 114319360 bytes | `567bd65fa072472d5444444ba56a0126f0459a4d0ffde0aa41d6438c1abc7f53` |
| Windows 224-file installed inventory | `f0f25e8b479f3b649631e381353547fbf87afa2208c1379a18d7edb27d18c8f8` |
| Windows native DLL, 193536 bytes | `3fc801e8ebbbd95aac7154d25bb1e5e0bf328b6b7b43fc1981032bbc86eb79f5` |
| Windows loader adapter JAR | `847a645fcde9a6036d17a8f72d5ab158fc233e95198359b66b7b18aced069d90` |
| Original pinned Temurin archive | `f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e` |
| Android `a2d8593f` APK, 18125404 bytes | `d49ba7a0ad28dcd8c98c7516c005025b8cda43a4fe490d0d9fba32da2e7fd403` |
| Android LAN AAR, 663144 bytes | `da95a43bdb36c7e5437cd259e4871ab14954bdb54faefc9e31cd6b8aa1fb34ce` |
| Android `d51ab685` test APK | `e109df03e6d9bafe7f37f73cea776f6b591407c16d83d0340f9cbf9b6eb680d8` |
| Android arm64 native library, 6896 bytes | `a7a0919d34faf7941307dfc98ddf30e3ae3cb2d5427e63d71068a93dd862b042` |
| Android armv7 native library, 5268 bytes | `6109b0ce554b93d829d22eef15f8b9f8addac8135f280193aba66302ad6b6e71` |
| Android x86 native library, 5264 bytes | `897ea48d7ba61a1a0982cc7c26ed32479e050d914ba5f56b4d65e3c086e13cbb` |
| Android x86_64 native library, 6568 bytes | `fdc50037335e8ffc8ae82d4d3af11684a49793336f492d09191e573940b2af90` |

All 224 installed Windows files and 68 runtime DLLs matched the verified
package/original supplier. The Android installed APK was pulled back and matched
the verified APK. Its version remains 0.8.0-rc3/code320204, with the distinct source
identity embedded in assets. These local packages do not replace published rc3 assets.

## Verification and preserved failures

The checked-in wrapper, declared toolchains and strict dependency verification
were used. Tests, native controls and manual observations are separate evidence:

| Command/control | Result and scope |
| --- | --- |
| `:p2p-rpc:jvmTest`, `:p2p-sample-rpc:jvmTest`, `:p2p-sample-desktop-ui:test` at `643988b2` | PASS: 80 + 611 + 71 = 762 tests; zero failures/errors/skips |
| Loader verification and canonical `:p2p-sample-desktop-ui:packageMsi` at `643988b2` | PASS; no alternate packaging pipeline |
| Fresh account/session/startup checks and maintained supervised installed `admission` at `643988b2` | PASS with observed driver exit0; candidate receipt requires that outer observation |
| `:p2p-transport-lan:testAndroidHostTest` | PASS: 139 tests |
| `:p2p-sample-android:testDebugUnitTest` | PASS: 254 tests |
| `:p2p-sample-rpc:testAndroidHostTest` | PASS: 68 tests |
| Android test compilation and `:p2p-sample-android:lintDebug` | PASS; lint repeated after verifier correction |
| `:p2p-transport-lan:buildAndroidLanSockets`, `:p2p-transport-lan:restoreAndroidMainEmbeddedJmdnsAar` | PASS: all four ABIs and AAR publication layout |
| `:p2p-sample-android:assembleDebug`, `:p2p-sample-android:assembleDebugAndroidTest` | PASS at their distinct source bindings above |
| `apksigner verify --verbose --print-certs`, `zipalign -c -P 16 -v 4` | PASS: matching single certificate and alignment |
| ELF exports/imports/protections and APK/AAR byte comparison | PASS; no runtime inference from byte checks alone |
| Actual Android `am instrument -r -w ...LanSocketRuntimeInstrumentation` | PASS: eight controls, 4.125s, result -1, adb exit0; original instrumentation process subsequently absent |
| Repository layout, OSV coverage, Markdown links, release metadata and whitespace checks | PASS |
| Gradle daemon retirement | PASS |

The Android managed total is 461, with zero failures/errors/skips. Do not add
overlapping earlier checkpoint totals into a purported single full gate. Earlier
Windows native custody/cold-reopen/cross-process receipts and encrypted-profile
results remain in the linked checkpoint. No successful prior test was rebuilt just
for this upload. No new Actions result is asserted; normal push workflows may run.
The earlier Apple ABI failure remains recorded and its baseline is unchanged.

Actual Android runtime controls independently checked listener/accepted flags via
the owned socket's `/proc/self/fdinfo`, empty nonblocking accept/read, a synthetic
byte round trip, write backpressure, EOF and closure. The control had a ten-second
inner budget and thirty-second outer command deadline; traffic was bounded to a
local test socket. This establishes kernel/JNI behavior on Android10/API29 arm64,
not real LAN pairing by itself.

Preserved failures include Android runtime attempt01 at LISTENER_FLAGS and
attempt02 at LISTENER_FLAGS_STAT/ERRNO_13. The verifier had attempted to stat
unrelated inherited framework descriptors. It now selects the exact owned socket
before stat/flag checks; matching-socket access and all flag assertions remain
mandatory. Attempt03 passed. An initial signing-output parser refusal reflected
build-tools37's changed label, not a different certificate; installation waited
for exact certificate equality. Packaging retained unstripped AndroidX/native
libraries and logged that fact; byte correspondence was checked.

At Windows `643988b2`, an initial preflight mistakenly required an absent native
smoke root and correctly refused the existing application profile before payload.
The maintained existing-profile admission then passed. Earlier installation,
loader, fresh-create and UI deadline failures remain intact. Neither manual
success nor later passing controls retroactively change them. Flush success or
process termination is not evidence of power-loss durability.

Selected private evidence hashes, without uploading their contents:

| Evidence | SHA-256 |
| --- | --- |
| Windows `643988b2` installed binding record | `e2c25503a736f127b8ef16c2f56fbbe82f447958fa5fe7cbc6f87fb62b23fb92` |
| Windows `643988b2` admission candidate | `f96f70cc3740a325cd48747eaa1f387e13161f2026f2d50020c79bb6d2ea8614` |
| Windows `643988b2` JVM totals record | `b2987865370ac05d3352d0d0751338f39d7d102d4d408e3a361e46e837bdb4b7` |
| Android runtime attempt01, FAIL | `a148dc025c2fb1127e98e4bf95b9ed6e67a581b86d3d7edd97c57db49672c93b` |
| Android runtime attempt02, FAIL | `6eb28e81df4b29840ad6ce5a8fded4b7dab1b37c5030dbfda4f62984677a3c30` |
| Android runtime attempt03, PASS | `ed732b5c79115192190300144ab098734b31bb9767896846ad86bb402ece9c50` |
| Android replacement-install/readback record | `7e5040917bc23f746ece7eaa3dc0eeeb3caec1deca24111984801fa755a5c4a4` |
| NDK r29 compiler executable | `f2e1b93d9dd27b847773e7de61b00f1b49ae27eb20ba434297cc020f768a1dfb` |
| NDK r29 linker executable | `1260f9d6e0522bd476d040203998fa03406607971c13a9aa74f3f66f1e6d1c5d` |

## Data preservation and manual result

The approved phone was updated with `adb install -r`, retaining its package UID
and signing identity. No uninstall, data clear, identity/trust reset or keystore
export occurred. Recorded `files/` and `shared_prefs/` hashes matched before and
after update and runtime controls. There was no pre-update byte snapshot of
`no_backup/` or Android Keystore in this repair; the hash comparison is not a full
storage/keystore audit. Identity/trust implementation source remained unchanged.

The owner first reported that Android's Review action appeared, then confirmed
that everything they tested now works. The last verified installed pair is the
Windows `643988b2` MSI and Android `a2d8593f` APK above. The agent did not select or
approve a peer, substitute a discovered device or replay requests. No new scripted
RPC result, revocation matrix or twenty-cycle record accompanies the owner's
manual confirmation. Raw profiles, device/account identifiers, fingerprints,
screenshots and logs remain private.

## Remaining W01–W11 work and next agent actions

| Case | Qualification status |
| --- | --- |
| W01 | BLOCKED / partial: actual positive Standard-user admission; full negative-token matrix outstanding |
| W02 | BLOCKED / partial: productive installed load/import admission; complete pre-execution refusal matrix outstanding |
| W03 | BLOCKED / partial: actual productive JNI/profile operations; full bounds/races/lifecycle matrix outstanding |
| W04 | BLOCKED / partial: actual custody and unsafe-DACL controls; full hostile path/ACL/reparse matrix outstanding |
| W05 | BLOCKED / partial: composed operations and cross-process contention; fault/uncertainty matrix outstanding |
| W06 | BLOCKED / partial: fresh encrypted creation, process reopen and wrong-password refusal; tamper/interruption/recovery outstanding |
| W07 | BLOCKED / partial: observed normal retirement; complete cancellation/race/uncertain-cleanup coverage outstanding |
| W08 | BLOCKED / partial: owner reports successful Windows/Android manual use; complete recorded two-device RPC/typed-error matrix outstanding |
| W09 | BLOCKED: complete peer persistence, revocation and safe reconnect qualification outstanding |
| W10 | FAIL remains: Back deadline failed; zero fully accepted automated UI cycles, twenty-cycle/resource/interruption gate outstanding |
| W11 | BLOCKED / partial: exact bindings for named results; complete qualified artifact/platform matrix outstanding |

RPC/Foundation should independently review the whole source delta and native/JNI
ownership changes, provide the pinned NDK to appropriate builders, run the missing
Apple ABI verification on macOS, and run affected complete gates at the chosen
integration source. The previously green CI belongs to its earlier exact source.
Do not empty an ABI baseline, change availability flags, relax policy/deadlines or
replace the canonical application/supervisor to manufacture success.

Remaining actual Windows cases still require an admitted Windows Standard-user
context, exact installed artifacts and original supervision. Another platform can
perform source review and its own build checks but cannot supply those Windows
results. Preserve existing synthetic profiles and retained failures; new destructive
or native-smoke fixtures require their separately admitted disposable context.

Campaign verdict remains **NOT_READY** until required productive integration,
independent review and actual Windows Host/Client qualification are complete.
