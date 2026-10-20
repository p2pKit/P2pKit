# API37 LAN permission validation

Issue [#372](https://github.com/p2pKit/P2pKit/issues/372) permits an eligible
**emulator**. It does not inherently require physical hardware. The successful
production repair is preserved; this explicit lane exercises the missing live
revocation boundary rather than rewriting the manager or sample flow.

## Explicit lane and exact source

`.github/workflows/android-permission-validation.yml` supports no-input
`workflow_call` and `workflow_dispatch`. The maintained dispatcher may call it as
`android-permission-diagnostic`; it is not an ordinary CI matrix component or a
release gate. Its separate entry point is
`scripts/run-android-permission-validation.py`. The API35 UI command keeps only
`317`, `324`, and `both`; #372 cannot be selected through that CLI.

The shared source-owned bootstrap builds the exact debug app/test APKs and
maintained JVM CLI distribution, with the checked-in wrapper, strict dependency
locks/checksums, Java17/21 and NDK29.0.14206865. It inspects actual APK manifests,
checks all five explicit runners, hashes both APKs, records source commit/tree,
and creates one fresh API37 Google APIs x86_64 AVD/private adb server. Installed
APK hashes must match. Installed emulator/image revisions and actual runtime
properties are retained. No personal device, existing AVD or prior installation
is adopted. Only the existing public evidence-recipient key is needed; raw
synthetic output is encrypted by the native-owned `ci_evidence.py` exporter.

The newly created, unbooted AVD requests a **2-GiB userdata partition**, following
the maintained RPC Android fixture's bounded allocation pattern. Only its fresh
`config.ini` is changed before first launch; SDK/system images, existing AVDs,
host caches and personal data are never resized or deleted. The generated config
and actual admitted guest `df -k /data /data/local/tmp` observation are retained
privately. This prepares space for APK staging/install and synthetic evidence;
it is not storage qualification, and a successful allocation/install is not
permission acceptance. No boot, instrumentation or retirement bound is extended.

Before either API35 UI or API37 permission instrumentation, the shared bootstrap
requires the boot flag **and** real `input`, `activity`, `package` and `settings`
binder services. The original 180-second boot deadline also bounds identity
checks and the single unlock command; a failed unlock is not retried. A boot
property alone does not establish that Android's system services are usable.
Pre-admission failure retains a fixed, read-only service/process/property and
filtered system-error snapshot privately, within a separate 20-second diagnostic
bound. Before those queries, the same bound covers exact generated-AVD identity
and live original-emulator checks; an unverified/dead guest is `NOT_CAPTURED`.
That retention cannot admit the guest or run any test. Persistent missing
services remain a failed setup, not a permission result or an unavailable-runtime
claim; no APK is installed before this admission completes.

## API37 graphics prerequisite candidate

The API37 lane alone requests the documented positive feature-override syntax
`-feature GLDirectMem,HasSharedSlotsHostMemoryAllocator`. A prior exact-source run reached two SurfaceFlinger/GoldfishMapper aborts
before permission evidence. The public [guest mapper fatal-if condition](https://android.googlesource.com/device/generic/goldfish/+/3ce87694caeb4a330280bb1284d9ad050fe28263/hals/gralloc/mapper.cpp)
requires `hasReadColorBufferDma` to be **present**, not absent. Public
[host extension advertisement](https://android.googlesource.com/platform/hardware/google/gfxstream/+/d047a57228332d995d36600792fa9ccc26cf8ae6/host/RenderControl.cpp)
depends on direct memory and shared-slot allocation. The positive CLI is
[officially documented](https://developer.android.com/studio/releases/emulator#29.0.6).
These public sources justify a prospective graphics prerequisite test; they are
not asserted to identify the exact internal source of hosted emulator37.2.12,
and the candidate is not a proven repair or permission result.

The original single-override diagnostic at9600852c accepted GLDirectMem as
explicitly enabled, yet the same mapper fatal persisted. Its fresh graphics
observation advertised direct memory but neither shared-slot allocation nor
read-color-buffer DMA. This motivates the narrow second positive request: the
supplier recognizes that feature and the public host code requires both. A
supplier default of on is not evidence that the effective renderer enabled it.
This is a prospective fresh-host emulator configuration test, not a declaration
of guest support, a proven repair, or permission-enforcement waiver. The original
failed source/run remains preserved; neither extension strings nor successful
feature overrides can replace the full unchanged permission/traffic campaign.

Before launch, the actual installed binary's bounded `-help-feature` response
and supplier `advancedFeatures.ini` are retained and hashed, together with the
frontend binary hash. Both relevant supplier declarations must be unique and
recognized; their on/off defaults are **not** treated as effective capability
values. Both direct memory and shared-slot allocation are now positively
requested through the same supported emulator feature CLI; no Android permission
or compat flag is changed. The full emulator argv is recorded with source commit/tree, alongside
the existing installed-source properties and actual guest properties. Unknown or
unsupported feature warnings fail closed, even if boot otherwise succeeds. A
bounded private SurfaceFlinger observation precedes real instrumentation; it
cannot prove internal DMA support merely by being nonempty.

There is no renderer fallback, second launch, permission/module flag override,
RAM/image/viewport change, or extended boot/body/cleanup deadline. API35 UI
options are unchanged. Only the original full runtime assertions plus independent
profile review can qualify #372; successful option preflight or graphics-service
observation alone cannot.

## Real campaign, not shell network identity

The existing `LanPermissionRuntimeInstrumentation` gains explicit modes; its
original no-mode caller and `NOT_EXECUTED` revocation terminal remain separate.

1. Fresh target37 app, ordinary target UID, no prior Nearby grant; require actual
   API37/REL/preview0 and the platform's dangerous LAN permission definition.
   Read the mandatory flag through the public `AconfigPackage`, retaining the
   same real object for false-default then true-default reads. Both must return
   true. Retain package/grant, active-module, compat and aconfig shell observations
   separately; absence/errors remain visible, not guessed values.
2. Exercise the real default permission manager and denied feature gate; a raw
   socket to the **already-listening** host control endpoint must be denied.
   `10.0.2.2` is the guest's non-loopback host gateway, not Android loopback or adb
   forwarding. Its eligibility is established by actual denied/granted behavior,
   not assumed from the address alone.
3. Use the sample's actual permission dialog, recreate while the request is
   outstanding, grant through the UI, and require the original manager/VM to
   observe the grant without automatic replay. Complete the raw nonce exchange
   and pinned authenticated bidirectional P2pKit session with the maintained JVM
   peer. The host verifies final, drained CLI output, not an early send snapshot.
4. Persist a source/UID/process/install-bound checkpoint **after duplex traffic**,
   then signal the host. Only then issue the real OS `pm revoke` command. Never
   grant through shell identity or use force-stop as a revocation surrogate.
5. If the original process survives, require that exact manager to report denial,
   reject a previously inactive feature, deny a new raw socket, and preserve
   denial/no replay across actual Activity recreation. If Android kills it,
   missing instrumentation output is **not** success: launch a separate reentry
   mode in the unchanged installation and require the platform's
   `ApplicationExitInfo.REASON_PERMISSION_CHANGE` for the original PID/UID after
   its checkpoint. The new manager, raw socket and explicit sample Start must
   remain denied. This branch never claims a surviving original manager.

The completed-request observer binds an actual outstanding request to the
original retained VM before granting, then requires that VM's request flag to
settle, a live grant and an unchanged successful permission-state snapshot. A
fresh observer-cache read must find the resumed replacement Activity's owned,
focused app window and visible fixed title. The existing production card has two
legal presentations: its available message and enabled Refresh button, or its
intentional removal after a subsequent successful foreground refresh clears the
message. The latter requires absence of the checked status, action and explanation
labels in the same captured tree, not merely a null/missing window or a state-only assertion.
Waiting/grant controls, stale visible labels, disabled buttons and ambiguous
matches cannot pass. The Refresh label resolves to its nearest owned structural
click/activation owner in the bounded ancestry, not a legacy widget class.
Compose can expose the Button role on a fake child while its real click owner
remains a View. A disabled owner can remain clickable but omit ACTION_CLICK;
therefore ownership is resolved before readiness, and the observer never skips
it for an enabled ancestor. The chosen owner must be visible, enabled, clickable
and actually export ACTION_CLICK. A long-click-only or foreign owner fails.
Finite class-category/action-ID/ownership ingredients are recorded privately;
no action is performed by this settlement observer. Fixed predicate ingredients are retained in the original
private instrumentation terminal, including failures. This repairs an overly
narrow observer contract; the earlier timeout alone did not establish whether a
callback or observer/presentation mismatch caused that original failure.

The original 90-second instrumentation body bounds remain; the host campaign is
bounded separately. Failures still trigger every owned retirement attempt. The
host never reads exit trace streams, unrelated app storage or credentials.

If the original, fully drained command stream contains no instrumentation
records, the controller records `NO_INSTRUMENTATION_OUTPUT` and fails. This
classifies output only: it does not prove whether the runner body started or
attribute a platform/service failure. It never authorizes a launch retry or
substitutes for traffic, permission or terminal evidence. Invalid/missing-file
output from optional record retrieval remains a private command capture, not a
misleading `.json` evidence record.

On a live-campaign failure, a source-owned callback revalidates the original live
emulator and exact generated AVD before private diagnostics. The same20-second
diagnostic work budget covers identity and fixed read-only queries: first the
last200 crash-buffer entries (independent of mixed-buffer log turnover), then
at most200 filtered system/ActivityManager/ServiceManager/low-memory/audit entries,
service list, system-server PID, native `cmd activity get-current-user`, and
fixed aggregate memory-pressure/cgroup counters. No root, dynamic PID paths,
app-storage search, memory/image change, or instrumentation replay is used.
The identity check has at most5seconds and each of the six observations at
most2.5seconds, still within the same20-second work budget. Privileged/native
crash stacks remain in the encrypted private capture, never public logs.
Missing observers stay explicit; failed diagnostics preserve the original
failure. Existing exact-owned-leader retirement tails are unchanged, not an
acceptance grace period or a claim of a hard20-second wall-clock cleanup bound.

## Acceptance boundary

A completed result is `HARNESS_PASS_PENDING_PROFILE_REVIEW`, not issue closure or
full-release qualification. Independently review the exact loaded permission
module, mandatory-flag/generated-cache and compat semantics, original route,
no-prior-Nearby installation, traffic, revocation branch and cleanup evidence.
Matching public flag reads alone are **not** generated-cache or enforcement
proof. Conversely a bypassed raw route, unsupported public reader, unrelated
process death, stale installation, partial output or an inconclusive profile
must not become a pass. A suitable runtime is unqualified until this executes;
it is not declared unavailable merely because local KVM is absent.

No physical-phone/OEM behavior, legacy target36, Android16 opt-in or wider test
campaign is claimed. Offline parser tests and compilation do not execute Android:

```sh
python3 -B scripts/tests/run-android-permission-validation-test.py
python3 -B scripts/tests/run-android-ui-validation-test.py
python3 -B scripts/tests/run-android-art-smoke-test.py
```
