# Windows RPC implementation and qualification checkpoint

**NOT_READY — Windows Host/Client has not completed actual qualification.**

This report distinguishes source implementation, portable/model controls, actual installed admission,
productive storage failures and unexecuted acceptance work. Installation alone is not acceptance.
Raw profiles, account/device identities, payloads and logs remain private.

## Installed UI attempt at 54e5bf59

Source `54e5bf59bb0b082f5994a41eb79af42e7b629ad5`, tree
`9fb5e6f0e91c6e80d91ed6f3570c2d2aecf51c21`, was built by the canonical scoped Desktop producer
[39185940802/1](https://github.com/p2pKit/P2pKit/actions/runs/39185940802). This is not a complete CI pass.
The MSI SHA-256 is `bf5097c3217170fc6574b60aa1274e4e5c3a23effcc303f8794a885e28864676`;
all 224 installed files matched, inventory `cf45f3fadb56e726f70c7e0b48165f9f58664f4d18482da02c5d4092b35cc7d7`.
All 68 runtime DLLs matched the unchanged pinned Temurin supplier. Actual assistant/tool Standard-user
tokens, interactive session and startup observations passed again; profile contents were preserved.

- Installed admission: PASS, app/driver exit0, 2.047s; receipt
  `84b2d12075342eff8d65fbb8f931d8f32489ac2999460035cd290cd588b14a39`.
- Installed `ui-host-cycle`: FAIL at `HOST_START`, app exit0 after normal terminal close, driver exit1
  because the required UI result was absent. Command elapsed 12.796s, no outer timeout. Receipt
  `2e76c60ccde1ad4df76c9414b0f9203e42d561793126114269a8deb19022ec74`.
  Actual RPC navigation and the passphrase dialog were reached; Host Ready was not established.
  The stage alone does not identify profile, network or UI failure. Zero installed UI cycles are passed.
- Both runs observed six retired/closed process witnesses, closed captures and known enclosing cleanup.
  The existing profile inventory was unchanged after installation and the failed UI attempt.
- Complete local managed gate: 2,946 tests, zero failures/errors/skips; full command exit1 solely for
  Apple ABI unavailable on Windows. Four shell gates, loader controls and byte inspection passed.
  The Apple baseline and earlier failures are preserved. All six harmless supervisor controls also passed.

The follow-up adds bounded rendered-state diagnostics and original test-worker retirement observation.
It does not weaken profile admission, network selection, focus checks, JNI lifetime or any deadline.
Actual installed Host/Client, peer operations, independent review and W01–W11 remain incomplete.

## Latest continuation: productive profile and UI integration

The exact-source installed candidate at `ba40c6cc1a9662ac06ccfa15eb4c9a832a40caca`, tree
`07860a9ef655f16341195d4f8b0a7a31857813ec`, passed installed admission and productive profile reopening.
The raw ABI13/`0x43` bridge and private managed composition remain unchanged. The source adds a distinct
delete-pending inspection: zero links are accepted only after this operation's acknowledged disposition,
with the original file identity and pending state. Ordinary files still require one link.

- All 16 portable native programs passed, including 13 deletion groups. Native DLL/smoke compilation passed.
- The checked-in wrapper's complete `check` invocation ran 2,946 managed tests with zero failures,
  errors or skips. The gate exited1 solely at Apple ABI verification, which requires macOS; the baseline
  remains intact. Four contribution shell gates, loader adapter controls and DLL byte inspection passed.
- Canonical Desktop producer: [39182289177/1](https://github.com/p2pKit/P2pKit/actions/runs/39182289177).
  The initial older-workflow dispatch 39182077105 was cancelled and supplies no evidence.
- MSI SHA-256: `f046b1396f6d213241f0715e6a6f43fa7f5412e5301be759615c15009b76bc00`.
  Package manifest: `87155b7d7844d3ff91ee2048033a1d74ff499b7276122187cc760700d6d77c99`.
  All 224 installed files and 68 runtime DLLs matched the package and original pinned supplier.
- Installed DLL SHA-256: `b33d65d19fc0181d190d6ef96d562782208b04521d3c5887f5a3cffcb68b7c39`.
- `run-windows-installed-admission.py --operation admission`: PASS, app/driver exit0, 2.031s.
  Receipt: `9f98f3a3f8c8017a0656c89ae857466b96e02d47e50a984238856da1ea5f57f6`.
- The same maintained driver with `--operation profile-reopen`: PASS, app/driver exit0, 2.750s.
  Receipt: `d7e8300c0383e9706800b1c5847fdc5a0e50518b33c2c7d67d6d80ddff0c7a5e`.
  It read the existing encrypted marker, exercised scratch create/replace/read/expected-identity delete,
  absence readback and namespace sync, then acknowledged profile close with no remaining managed leases.
  Two sessions reused registration without unloading cached JNI addresses. Both invocations observed
  all six process witnesses exited/closed, bounded captures and known enclosing cleanup within 30000ms.

The owner approved archiving the original failed profile intact and reusing the disposable account.
All eight archived entries retained their original identities, content and ACLs. The later fresh-create
attempt at `64d4a84d` failed at `READ_REPLACE_DELETE / CleanupUnknown`; receipt
`259ef5e69742186caf4306a7a0934ed29e26c5d366ae1595ad66807751b39567` remains FAIL. The zero-link
repair enabled subsequent normal reopening of its complete visible state, not a retrospective create pass.
No successful fresh-create, interrupted-state recovery or power-loss durability is claimed.

The subsequent UI change connects Host/Client to the fixed installed provider through the owned unlock
task. It verifies the original module/runtime before Desktop preparation, and permits a role only when
unlock succeeds without cleanup uncertainty or a retained session. New coroutine regressions exercise
those ownership refusals. This source change still needs its own affected checks, exact-source installer
and actual UI execution; the `ba40c6cc` results above do not qualify it. At
`4106bd6e64fd5b894a39ef2f677cc9bff1a93ad3` (tree `32b9111e07e00c659736dde5f0525ec4c2222b16`),
the subsequent complete local gate ran 2,946 passing managed tests with zero failures/errors/skips;
its sole failing task remained Apple ABI verification. No baseline was changed. The fixed
[installed UI control](windows-installed-ui-control.md) supplies the next actual navigation/Host lifecycle
invocation under the existing supervisor; its implementation alone is not a UI result.

The approved Android endpoint now has the verified debug APK from `506d3bda`, version `0.8.0-rc3`.
Its installed SHA-256 is `6d360be38403f8c2a2e678b86e41dadbd8a083f508d95f716a0c1efd9ee5cf18`.
The owner explicitly approved removal of the previous differently signed test app and its app data.
No pairing, peer approval or device RPC result is inferred from installation.

W01–W11 remain incomplete: admission and productive JNI/storage have positive observations, while
negative contexts, hostile paths/ACLs, cross-process/fault controls, cancellation/races, actual UI/LAN,
revocation/reconnect and 20 installed lifecycle cycles remain outstanding. Independent Foundation review
and actual Apple ABI verification are also pending. The remaining sections preserve earlier checkpoints.

## Source and ownership

- Branch: `work/windows-rpc-completion-20261018`.
- Implementation commit: `64d4a84d84f9fdf62bd859e3a46793f9e6171538`.
- Implementation tree: `435d69051c4ff1aea1f0a14beacb9d15393656e1`.
- Base: `db5d6c01e9a5f0c46fdb51ed0d885a5a394bbe5c`, tree
  `4fccd01ecbac953a9934d5325bd84913e3fc6885`.
- Isolated checkout: `windows-rpc-completion-20261018`. Original checkouts and shared branches were preserved.
- Working tree was clean at implementation commit/push. A later report-only commit does not change
  the source identity of any tested application or installer below.
- [Complete implementation diff and changed-file inventory](https://github.com/p2pKit/P2pKit/compare/db5d6c01e9a5f0c46fdb51ed0d885a5a394bbe5c...64d4a84d84f9fdf62bd859e3a46793f9e6171538).

Foundation transferred the necessary repair ownership in
[the implementation handoff](https://github.com/p2pKit/P2pKit/issues/462#issuecomment-6252427986).
No merge, tag, release signing, publication, account creation or security-policy change was performed.

## Implemented repairs

| Commit | Change and practical effect |
|---|---|
| `523f0bd9` | Retain bounded system-cohort failure diagnostics. |
| `884d9015` | Carry those retained diagnostics through the actual JDK21-to-Kotlin/Desktop boundary. |
| `bce97101` | Preserve valid zero-filled system data exports while refusing their use as callable code. |
| `074c55ca` | Bind Desktop toolkit preparation and the required API-set routes to original runtime/process owners. This addresses the observed missing `ole32.dll` and unsupported route failures. |
| `b82645bc` | Admit the complete expected API-set adapter class inventory in packaging inspection, retaining rejection of unknown/test classes. |
| `91fec158` | Connect the public installed provider to the existing retained installed controller. Successful return requires actual admission; failed attempts retain ownership, and registered owners are reused without unloading cached JNI addresses. |
| `506d3bda` | Add fixed supervised installed encrypted-profile create/reopen controls and bounded failure-stage labels, using existing encryption, custody and lifecycle code. |
| `64d4a84d` | Correct NTFS directory index versus data-stream inspection; add two portable regression groups. |

The last repair changes five paths under `samples/p2p-sample-rpc/native/windows-profile/`:
`profile_policy.c`, `profile_policy.h`, `profile_win32.c`, `tests/profile_policy_test.c`, `README.md`.
Raw custody ABI13/`0x43`, JNI export descriptors, managed composition ABI1/`0x7f`, encrypted record formats,
installer identity and versioning remain unchanged. No plaintext identity, POSIX-on-Windows path or
permissive storage fallback was added. Windows UI readiness declarations remain closed pending evidence.

### Confirmed directory defect

The real installed encrypted-marker write at `506d3bda` failed with native `Policy`. Read-only queries
on original handles subsequently showed that the identity directory had standard EOF 4096 while
`FileStreamInfo` reported `ERROR_HANDLE_EOF`: its NTFS index had grown without adding a data stream.
The old policy incorrectly required every directory's standard EOF to be zero. It therefore refused
both original-parent inspection during writing and later inventory inspection. The exact in-call
transition was not instrumented; the invalid policy condition was reproduced independently.

The repair accepts OS-confirmed no-stream directories independently of their nonnegative index size.
A reported directory stream must still be the single empty unnamed stream. Named, multiple, nonempty,
truncated and invalid-size streams refuse; regular-file stream length must still match file EOF.
ACL/owner, original identity, reparse, case, link, record-size, lease, sync and retirement checks remain.
The new regression failed before the repair and passed afterward. Corrected installed inventory
inspection subsequently advanced beyond the old failure, but successful persistence has not been demonstrated.

## Admitted environment and supervision

The actual assistant and tool processes were checked, not inferred from a switched desktop account:
native AMD64 Windows/processes, ordinary local Standard primary tokens, matching user/default owner,
no elevation or filtered token, no Administrators SID even deny-only, no Service SID, active interactive
local-console session, and no observed thread impersonation/query failure. The disposable account was
initialized by interactive logon. Exact identities and session records are private.

Windows 11 Home Single Language 25H2, build `26200.9168`; local fixed NTFS; OS-resolved LocalAppData and
startup configuration were checked. The application profile entry was absent before first creation.
It now exists and contains a retained failed pending record; that state is not relabeled as fresh.

Existing MSVC 19.44.35229.0/toolset 14.44.35207, Windows SDK 10.0.26100.0 and JDK17 were used locally.
Ordinary bytecode remains Java17. The installed runtime remains the canonical Temurin
21.0.12.1+1-LTS supplier, not the development Oracle JDK21. The named loader module retains narrowly
scoped preview/native access and `jdk.unsupported`.
Installed admission executes the original runtime readback: `NOSHARE_READ`, `NOSHARE_WRITE` and
`NOSHARE_DELETE` must resolve as the actual `ExtendedOpenOption` type from the linked boot module.
That class/module check passed; the complete real sharing/lock behavior matrix remains part of W05.

The canonical outer observer/job/watchdog was extended only with fixed operation selections. The
original 30000ms subject deadline, process/descendant ownership, capture bounds, final exit and cleanup
requirements remain. Six affected harmless supervisor controls passed at `506d3bda`, including their
intentional nonzero/overflow/blocked outcomes. They are not storage or installed Host/Client tests.

## Exact installed candidate and actual execution

The first productive installed attempt used source `506d3bda4ebd084feee41fc89faf962e9ae1aae9`, tree
`ccf53c4d0240af0b098f6d0e4c246fc7f8c07f14`. Canonical Desktop producer:
[39177027760/1](https://github.com/p2pKit/P2pKit/actions/runs/39177027760).
Version remains `0.8.0-rc3`, numeric MSI version `1.8.203`; these candidate bytes are not replacement
published rc3 assets. A normal full MSI uninstall/install was necessary for changed content-derived
components; both installer exits were observed as zero. No manual installation-root deletion occurred.

| Binding | Value |
|---|---|
| MSI | `desktop-installer-windows-x64-506d3bda4ebd.msi`, 114249728 bytes |
| MSI SHA-256 | `2eb673f96c6a077fed4d066f8aa2d7631e7cf6d9729df28e461356219ba1bbf0` |
| Package manifest SHA-256 | `3d98aa84d80863d19d5aa36aaed9c6e3ebb025b3555f52b7a484dbd33e8d0474` |
| Installed inventory | 224 files; digest `e03b3d12c5a2852582c52642dbcbf776fe199ca3e5a72df31c9297776281105b` |
| Installed native DLL SHA-256 | `de89ba19210c8f277637ce2a50f48c180a380f766214f2c2031d519a233c9041` |
| Runtime supplier ZIP SHA-256 | `f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e` |

All 68 installed runtime DLLs matched the pinned supplier. Original artifact digests, run/job/attempt,
embedded source, native manifest/pin, Java17 classes, installed ACL/owner/reparse inventory and all 224
installed file hashes were independently inspected and retained.

Commands used the checked-in `scripts/run-windows-installed-admission.py`, `python -I -B -S`, the exact
`--expected-source` above and a new private owned evidence directory. Fixed `--operation` selections:

| Operation | Actual result |
|---|---|
| `admission` | PASS, app/driver exit0, app command 2.031s; actual JNI `REGISTERED`/`REUSED`, no storage entry. |
| `profile-create` | FAIL, app/driver exit1, 2.344s; `ENCRYPTED_MARKER`, native `Policy`. Public provider, protected root/locks/header and encrypted proof were entered/created; the marker write retained an empty pending file. |
| `profile-reopen` | FAIL, app/driver exit1, 2.125s; `INITIAL_INVENTORY`, native `Policy`. This was the same native directory defect, not proof of the intended managed incomplete-state refusal. |

Each invocation preserved the 30000ms budget, had no timeout, and observed known cleanup, closed captures
and all six original process witnesses retired/closed. Driver exit was observed externally; provisional
JSON alone was not treated as final acceptance. No app/JVM survivors were found after these invocations.
Profile file bytes and identities were unchanged by the second failure. No pending file or identity was
removed, promoted or silently repaired. These observations do not establish power-loss durability.

Receipt SHA-256 values:

- Admission: `3426914fd056bd45fc83a960d0692f895f91af82d433b4024a79cead55690392`.
- Productive create failure: `3d69893d69d86826fc357bc4a0eeb6e1d66f3172d0525db5615abc8a9aa362a9`.
- Reopen failure: `d820456b369c191fab92ddb1ecdb15d140311443030823e8c7e85d50814b0b4d`.

### Repaired candidate now installed: 64d4a84d

The canonical Desktop run [39179217624/1](https://github.com/p2pKit/P2pKit/actions/runs/39179217624)
passed for exact source `64d4a84d84f9fdf62bd859e3a46793f9e6171538`, tree
`435d69051c4ff1aea1f0a14beacb9d15393656e1`. Its original application artifact is ID `12155832368`,
243352439 bytes, digest `28960b800d7cfa4d9564cc5aad44f9c0a68a43697c9a5a279335c4956f57a909`.
The archive, run/attempt/job, embedded identities and package inventory were verified before installation.
Normal MSI uninstall/install both exited0, preserving profile data. The 224 installed files and all
68 runtime DLLs matched the new package and original pinned supplier. Token/session, startup inputs
and retained fixture identity/content were refreshed after installation.

| Binding | Value |
|---|---|
| MSI | `desktop-installer-windows-x64-64d4a84d84f9.msi`, 114245632 bytes |
| MSI SHA-256 | `4095a8a5b23fe03ad22e8144bc697a73a321579c2594491f2874f2c41a090971` |
| Package manifest SHA-256 | `7d6e3391047dfc55d7d2a8459e0f7a350c49834d2df6b0a8e2425078d6bb505f` |
| Installed inventory SHA-256 | `97bedecfb8918b6afdd50f8f0e537cc6fb96ef1ba3b4bc485af7253abe2d720d` |
| Installed DLL | 188416 bytes; SHA-256 `7830722d941c3860fec49657cb80501351964c198208fb7a0e51655fd7ffacf5` |

With `--expected-source 64d4a84d84f9fdf62bd859e3a46793f9e6171538`, the same maintained driver ran:

- `--operation admission`: **PASS**, app/driver exit0, app command 2.125s. Receipt SHA-256
  `3cdafe7d5ae08bbd7cb91ebb50d0796a23f3aa7b81a276be00812133591a5523`.
- `--operation profile-reopen`: **FAIL**, app/driver exit1, 2.266s,
  `stage=PROFILE_OPEN native=NOT_CLASSIFIED`. Initial native inventory now succeeds; the preserved
  failed profile refuses later. This is consistent with conservative pending-record handling, but the
  bounded stage does not uniquely identify which managed check failed. It is not a successful reopen
  or a fully proven pending-recovery case. Receipt SHA-256
  `843474476cab57c79a8a8067387e735c7cc84a04e7f79a5c4308708526aec224`.

Both invocations had no timeout, observed known cleanup/closed captures and all six original process
witnesses retired/closed. No app/JVM survivors remained. The retained profile's five files and two
directories had identical contents/identities before and after; inventory SHA-256 remained
`f03507cc3c563a4e4f6f5ce54f09e2a0c22a85e53d3f8495d1e1fa2b888537c4`.
No fresh creation or native custody-smoke payload was executed in this occupied context.

## Regression and build evidence

At `64d4a84d`, all 16 maintained portable C test programs passed under actual MSVC, using `/W4 /WX`
and `/UNDEBUG`. The policy executable contains 20 groups. The added regression compiled successfully
against old code, then failed its assertion with observed process exit before the repair.
These are memory-only C policy/ownership controls, not Win32 profile execution.

The maintained DLL and smoke recipes compiled successfully. Inputs were hashed during compilation
and rebound unchanged to the clean commit. Compiler/SDK/JNI header hashes and output hashes are private.

- Local DLL: 193536 bytes; SHA-256 `b59ce3a31ab016587a4417b0cd98618b3539304b1a7afc0a91850cb19f327845`.
- Local smoke EXE: 269312 bytes; SHA-256 `7d38fdbac5638ab41ac9939f0d365eedf6f7b38f9bd7fbcb674f23a015f99c40`.
- Neither local output was loaded or executed. The separately produced installed DLL above has its
  own exact-source byte binding and actual execution evidence.

At `506d3bda`, complete adapter controls passed all 542 commands, preserving expected refusal exits.
Affected supervisor checks passed: 28 Python supervisor tests, 8 driver tests, C# receipt controls
(4 valid and 46 refusals), 50 app-image inspection tests, and the six actual harmless Windows controls.
Source [39177030397/1](https://github.com/p2pKit/P2pKit/actions/runs/39177030397) and JVM-Windows
[39177032882/1](https://github.com/p2pKit/P2pKit/actions/runs/39177032882) passed.

The complete local 506 gate used the checked-in wrapper, `check`, `rpcWindowsLoaderJdk21Jar`, Android
`assembleDebug`, `--continue --rerun-tasks --no-build-cache --dependency-verification=strict`,
`--no-daemon --max-workers=2`. It exited1: 2944/2946 XML tests passed, two JmDNS real-resource lifecycle
tests failed, and the Apple ABI task lacked an Apple toolchain. Zero XML errors/skips; Gradle's
unavailable platform tasks are not represented as executed tests. Four repository shell gates passed.
The preserved XML manifest SHA-256 is
`277ec17734217d7bab94e7823711c66dbbc175eff5bb410af30a897ce2b8ea86`.

The JmDNS failures reported inability to map an address to an interface during leave-group cleanup,
and absence of a local up multicast IPv4 interface during another fixture. A new complete gate at
`64d4a84d` uses the fixture's existing explicit physical-interface input, which still verifies its
local/up/multicast properties. Original failures remain failures; no assertion, deadline or baseline
was weakened. Apple ABI baselines must be checked on macOS, never emptied on Windows.

At `64d4a84d`, the full local rerun completed in 9m58s: **2946 tests passed, zero failures/errors/skips**,
274 actionable tasks executed. The overall command still exited1 because
`:p2p-rpc:checkKotlinAbi` could not perform Apple ABI validation on Windows. Apple platform execution
remains unavailable, rather than counted as a passing test. Gradle stopped successfully. The four
repository shell gates passed. The new XML manifest SHA-256 is
`9c674c7339f644c1002c50ba4caf8b605382f934777db47f20f599a68999063a`.
The two earlier LAN lifecycle cases passed with the maintained explicit physical-interface input;
this observation does not retroactively erase the earlier interface failures.

The complete current adapter suite passed **542 commands** with expected refusal exits. Native DLL
byte verification passed with scope `BYTE_MANIFEST_ONLY`; its manifest SHA-256 is
`137a7b61e24daed3b7fa81a0bd4ae4c940365cfd13b6d80fece41bb7f18d018d`. This byte check did not load the DLL.
The current strict wrapper invocation added `:p2p-sample-rpc:verifyRpcWindowsProfileBytes` with explicit
DLL/source/tree/compiler-SHA/new-output pins; the exact arguments and completed receipts are private.
Adapter evidence manifest SHA-256:
`3c5acb847d309c33439ecfb4b64babe6899c9cffeb8c1dca43b12af5a8a85d88`.

Exact-source Source [39179220198/1](https://github.com/p2pKit/P2pKit/actions/runs/39179220198), JVM-Windows
[39179222978/1](https://github.com/p2pKit/P2pKit/actions/runs/39179222978), and Desktop-Windows
[39179217624/1](https://github.com/p2pKit/P2pKit/actions/runs/39179217624) all passed. These are selected
component results; no combined-source or Apple qualification is claimed.

## Android peer preparation

The owner authorized installing the sample on the Android device they will connect. No device has
yet appeared in ADB; OS/CPU admission, existing-app inspection, installation and LAN tests are unrun.
The debug APK was built through `:p2p-sample-android:assembleDebug` from clean `506d3bda` and its embedded
source identity and APK signature were verified. It is `dev.p2pkit.sample.android`, version
`0.8.0-rc3`/320204, 18063731 bytes, SHA-256
`6d360be38403f8c2a2e678b86e41dadbd8a083f508d95f716a0c1efd9ee5cf18`.
It contains arm64-v8a, armeabi-v7a, x86 and x86_64 native libraries. This debug variant includes RPC;
the release variant remains deliberately different. Existing app data must not be cleared to resolve
a signing/version conflict. Peer fingerprint approval and genuine distinct-device traffic remain required.

## W01–W11 acceptance

Statuses refer to each complete required case, not the narrow observations already listed.

| Case | Status | Evidence and outstanding scope |
|---|---|---|
| W01 | BLOCKED | Positive actual Standard interactive context observed; required prohibited-token negative matrix incomplete. |
| W02 | BLOCKED | Actual installed admission passed at b826, 506 and 64d4; full before-candidate unsafe/tampered-input matrix incomplete. |
| W03 | FAIL | Actual JNI registration/reuse passed; productive call failed. Bounds, normal Start/Stop/reopen and full continuity matrix incomplete. |
| W04 | FAIL | Actual protected root/lock/header/proof creation observed; marker write failed. Complete readback and unsafe ACL/reparse/alias negatives incomplete. |
| W05 | FAIL | Write stopped at directory inspection; complete cross-process locks, replace/delete/sync and bounds matrix not demonstrated. |
| W06 | FAIL | Encrypted proof exists and pending state is preserved; repaired reopen gets beyond the old native failure but still refuses. Successful restart, wrong-password/tamper and interruption recovery remain unqualified. |
| W07 | BLOCKED | These failed invocations retired observed processes/resources; complete cancellation/race/uncertain-cleanup matrix not executed. |
| W08 | BLOCKED | Windows UI Host/Client still closed; Android peer absent; real two-device RPC/typed errors unrun. |
| W09 | BLOCKED | Persisted peer selection, revocation and safe reconnect on installed Windows unrun. |
| W10 | BLOCKED | Twenty installed lifecycle cycles and interruption/resource matrix unrun. |
| W11 | BLOCKED | Exact 506 and 64d4 source/MSI/runtime/installed-byte bindings complete for listed invocations; bindings for all final required acceptance results do not yet exist. |

## Required continuation

1. Review `64d4a84d` and the earlier bootstrap/provider/control changes independently. Foundation review
   was requested on [issue #462](https://github.com/p2pKit/P2pKit/issues/462#issuecomment-6256861058);
   no independent approval is claimed.
2. Keep the installed 64d4 package/source bindings and preserved failures. Refresh actual
   token/session/startup facts before further execution; reuse the unchanged canonical supervisor.
3. Narrow the later `PROFILE_OPEN` refusal if further recovery diagnostics are needed. Successful clean creation
   requires a separate fresh disposable profile context or independently restored throwaway snapshot.
   The current account's Standard status is sufficient; its retained failed data is the restriction.
   Do not reset the current profile or reuse native-smoke fixtures as application profiles.
4. Demonstrate productive encrypted write/read/replace/delete, normal restart and recovery, then finish
   supported Desktop UI activation and W01–W11. Do not flip availability constants to replace evidence.
5. Admit and install the authorized Android peer, use synthetic data and explicit fingerprint approval,
   then run genuine LAN Host/Client, revocation/reconnect and lifecycle/resource controls.
6. Foundation must complete Apple ABI and combined-source integration gates on their actual platforms.

Earlier failures remain preserved: historical 87/1314 credentialed-launch failures were not retried;
old `25f704ee` CI results are not credited to new source; bce's missing-system-module failure and the
074 packaging failure remain recorded even though later bounded admission passed. Deferred/unexecuted
tests are not passes. **The verdict remains NOT_READY.**
