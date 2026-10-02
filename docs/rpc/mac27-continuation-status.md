# October 2: official ARM27 continuation checkpoint

## Latest update: first product session failed after the controls

The owner executed the prepared `native-8783cc9d` request. That request is now
**consumed**, not pending or reusable. Mac27/Xcode27 remains the accepted host.
The previous checkpoint sections below retain their historical observations;
their instruction to run that old request is superseded by this update.

At source `8783cc9d5a027b69689cbf27ae6ac7bcde44ba2b`, invocation
`7a94b97b65cb40fc92c3587302edcc92`:

- All **129 controls passed** in121.478s (36policy,45modeled Darwin,48native-class).
- The mandatory `gradlew --stop` then attempted a cold distribution download.
  It timed out after120.107s: product exit0, stop exit143, final exit125.
- All411 recorded owned lifetimes were drained; no owned survivors,
  unclassified lifetimes or discovery errors were recorded. Nevertheless, the
  failed wrapper finalizer correctly makes the phase **FAIL/OWNERSHIP_UNPROVEN**.
  Successful test output is not a valid admission receipt.
- No later toolchain, simulator, Swift, phone application or capacity phase ran.
  The original receipt checker still refuses this saved failed receipt.

Receipt SHA-256:
`bb2f8f08ea86d170653c9d88c98a9a0d7eb2f8224aa8ff10bdcb4b1b17eca73c`.
Original evidence remains under the earlier evidence parent's
`native-8783cc9d/state/`; the independent failure review and1280-entry integrity
index are in `P2pKit-mac27-wrapper-preparation-fix-20261002-mp3y72bi`.

The [local controller repair](local-arm27-qualification.md#wrapper-dependency-preparation-is-not-finalization)
adds verified **distribution data preparation**, not an increased deadline or
skipped finalizer. A fresh150,308,896-byte official Gradle ZIP was downloaded
without extraction/execution in159.656s and matched the existing source pin
`84fbba45c7f4c64abc77460e1c00f541e9f960e3c7ed2538f1ede19eacd873ae`.
Old partial downloads, native state and failures remain untouched.

The changed Mac offline controls pass: **15** local controller/request-order
tests and **16** distribution pin/copy/identity/empty-home controls. These are
not a replacement native run. A fresh exact-source request is required after
the repaired candidate is frozen; do not repeat any consumed request. Actual
native finalization and all subsequent ARM/app gates remain open.

Repair commit: `70c864c52aa064bb830bbdbbfdfda96d016be9f9`, tree
`2331d188e48da8d37ac4a4c89f40c4d155352367`. Only the two changed suites were run
on Linux in [run36986650033](https://github.com/p2pKit/P2pKit/actions/runs/36986650033):
**15+16 passed**, job `110773107653`, artifact `11217816889`.
The591-byte artifact ZIP was hash-verified before reading:
`b73851f353f1cd8bf48271d30585b2c0fa3391a5b8b3ee18bacc6d2be6e8e90a`.
Layout, workflow YAML/credential policy and whitespace checks passed;745 relative
links resolve in113 active documents. The original native executor/owner,
receipt checker,129-control source, bootstrap, Gradle wrapper/pin, library and
sample application source are unchanged by this repair. No bootstrap or native
suite was rerun by the agent during the repair. The next prepared request is
bound to the final clean documentation checkpoint, not relabeled as this CI run.

## Scope and source

The owner accepted **native macOS27/Xcode27**, from baseline
`e1ae3f37b27780cc4d9efaa16228fcb75c8e159b`. Mac26/Xcode26.5 is **not a prerequisite**.
Foundation remains **NOT_READY**. There is no overall completion percentage:
offline methods, native ownership controls, product tests and physical campaigns
overlap and do not share a qualification denominator.

Source changes, on the existing RPC feature branch only:

| Commit | Change |
| --- | --- |
| `395181e2795e0a8a481f07e199f0bb1d72f48b2c` | Official local ARM27 controller using the existing native executor, original tests, provenance and finalizers; read-only Ubuntu24 KVM observation. |
| `ecb614f901fa91fd426a065dc2f11fe231fa7df0` | Portable offline Android stat fixtures using actual host inode metadata; production Android shell unchanged. |
| `3a99bf6f88e368c520f02e6dbd7d53f13539eee8` | Sealed iPhone inputs, signed-executable binding, Mac/iPhone coordinator, real Darwin clock/resource prerequisites, cleanup-failure retention, current-source driver preparation and targeted offline CI. |
| `ede47d4333c6905020c496bb6cd988204f8a2057` | No-install Intel toolchain availability observation; no native/product execution. |
| `2b1715be22f99dc241fead28f13ab2072038850e` | Adds the phone-independent full native Mac clock preflight to the authorized ARM plan. |
| `cb3c3430d733f5e52b443f3abeed5cb5003eda20` | Refuses setuid/setgid, writable or foreign developer tools and nonregular/unbounded CoreDevice metadata. |

The primary implementation freeze is tree `591d78ebe8675daf6bba6c200a1f67bc96c57e13`
at `3a99bf6f`. The two later functional changes above have separately scoped
controls; later workflow/documentation changes do not relabel earlier tests.
No production `library/` source, dependency versions, old checkout, signing
configuration or release state was changed.

## Executed validation

Private evidence is retained under
`$HOME/Projects/P2pKit-mac27-qualification-20261002-t321maf7`.

| Executed step | Observed result | Evidence |
| --- | --- | --- |
| Changed local ARM orchestration, iOS USB, Darwin preflight and mobile coordinator controls | **11, 22, 12 and 23 PASS**, respectively; offline only. | `offline/20-*.log` through `23-*.log`; exact frozen source/hashes in `frozen-3a99bf6f.json`. |
| Portable Android file/control fixtures | **32 and 13 PASS** on Mac; unchanged five-second fixture limit, real inode/FD metadata. | `offline/18-android-controller-native-stat.log`, `19-mobile-records-native-stat.log`. |
| First read-only native Mac kernel controls | **2 PASS**: actual hardware sysctl observations; actual kqueue timer expirations and exact owned FD closure (`EBADF`). **Not** the 125-second preflight, native-executor admission or RPC execution. | `offline/24-darwin-readonly-native.log`, source `3a99bf6f`. |
| Linux portability and affected contracts | All eight suites pass: local ARM **11**, iOS USB **22**, Darwin model **12**, mobile records **32**, mobile coordinator **23**, Android controller **13**, phone controller **23**, handoff **29**. No device/native claim. | [Run 36980957819](https://github.com/p2pKit/P2pKit/actions/runs/36980957819), job `110755126702`, artifact `11215462043`, source `3a99bf6f`. |
| Maintained qualification compatibility | **105 offline PASS** after the narrowly scoped controller allowlist extension. | `offline/04-maintained-qualification.log`, source `395181e2`. |
| Final phone-independent clock plan and developer-tool guard | **12 and 23 offline PASS** on Mac, respectively, after the two later changes. The earlier 11/22 inventories remain earlier evidence, not extra unique coverage. | `offline/25-local-arm-clock-plan.log` at `2b1715be`; `26-ios-developer-tool-policy.log` at `cb3c3430`. |
| Focused Linux follow-up for those two changes | **12 and 23 offline PASS**, in separate jobs selecting only the changed suite; the other seven suites were not repeated. | [ARM-plan run 36982301880](https://github.com/p2pKit/P2pKit/actions/runs/36982301880), job `110759312179`, artifact `11216560067`, source `2a32713013876634988e0976796491b7303dcffe`; [iOS-policy run 36982670935](https://github.com/p2pKit/P2pKit/actions/runs/36982670935), job `110760511746`, artifact `11215972955`, source `26e4a0f49731defa425c5448dfee3c28b4e5b441`. |
| Repository/source checks | Layout, OSV lockfile/upstream inventory coverage, **739 links / 112 documents**, release metadata, committed diff whitespace, workflow YAML/checkout policy, and **7 offline KVM-policy controls PASS** at the implementation checkpoint. Coverage is not a fresh vulnerability scan. | `source-gates/final-3a99bf6f-results.json`. Later report-only links are checked separately. |
| Current Ubuntu24 KVM availability | Observation completed; `/dev/kvm` mode `0660`, neither readable nor writable by the runner. **No device open or emulator execution**. No self-hosted runner was registered. | [Run 36976927461](https://github.com/p2pKit/P2pKit/actions/runs/36976927461), job `110742651438`, artifact `11213946511`, source `395181e2`. |
| Current Intel installed tools | macOS **15.7.9**, Xcode **26.3**, JDK17/21 and Android36/37 compile platforms observed; **no XcodeGen available on the runner PATH**. No installer, bootstrap, simulator query or product command ran. | [Run 36981272232](https://github.com/p2pKit/P2pKit/actions/runs/36981272232), job `110756116401`, artifact `11215209140`, source `ede47d43`. |

All five downloaded CI ZIPs were SHA-256 verified **before** bounded member reads:

- Offline: `29f1cb47f520b0bf310a2b7675e41519ddd33ceecd7dd8b4d6311780c2852f71`.
- KVM: `b07808d68c7bc36ddfc5efdca44af636f18f760ae4f5665e4b84d9c8193313df`.
- Intel: `179f81efefdbc74de9b73ee2777a3cdd66a99de711ce95c44955d050907642ac`.
- ARM-plan follow-up: `f7e23995309b5bac9803a41b7c4f92132b9234a1748807fa2029951f27b63561`.
- iOS-policy follow-up: `f78a04f2b4ff5f4345e8c4c2769b58671f3a64669af5164caf426908794f28f3`.

### Failures and earlier evidence remain intact

The initial Mac Android fixture run had ten failures because its old GNU-stat
wrapper was not BSD-compatible. Intermediate corrections also exposed an
unsupported format/FD-path case and five-second fixture timeouts. Logs `11`,
`16`, `17` are retained; none is overwritten by the final passes. The repair uses
native BSD/GNU format translation and isolated Python FD inspection, **not longer
timeouts, relaxed assertions, fake metadata or changed Android production code**.
Missing-module development red tests are also retained separately.

Earlier **61 offline passes** (phone23, boot diagnostics6, handoff29, Apple context3)
and their repository gates remain in `P2pKit-rpc-readiness-20261002-047uoh2p`.
They were not rerun wholesale or added to the newer counts as unique coverage.

The successful earlier local readiness at source
`57df23248be2c1872e5bbe18a8f44fcf1f32b177` remains in
`P2pKit-rpc-readiness-fix-20261002-yp51bvm5/12-native-independent-review.json`:

- **129 controls**: 36 pure policy/parser controls, 45 modeled Darwin controls,
  and 48 native-class fixture controls, including modeled failure branches.
  They cover ownership/admission, cancellation/deadlines, hostile lifecycle
  changes and retirement; they are **not 129 RPC/LAN product scenarios**.
  Actual native fixtures include detached/reparented and TERM-resistant workers,
  cancellation/timeout drains, surviving unrelated sentinels, exact argv/source/
  private-home binding, report/provenance preservation and checked output cleanup.
- The real runtime-root Mach-O ARM64/IOSSIMULATOR probe passed; the observed
  manager UID matched but was **not used as ownership authority**.
- One new simulator's cold readiness passed in **29.290629750s / 120s**.
- Both independent native finalizers passed: the controls scope (**278 owned
  lifetimes**) and simulator scope (**18**), with no unclassified lifetimes,
  discovery errors or survivors. Exact simulator Shutdown and deletion also passed.

Those old results retain their **pure-command supplemental receipt scope**;
accepting Mac27 now does not retroactively convert them into product receipts.
The earlier failed local attempt, ARM readiness `120.039s`, Intel inventory
`120.163s`, and later phone readiness `120.291s` remain failures in their original
evidence. Previously accepted JVM/Bonjour/Android results remain bounded to their
[recorded configurations](qualification.md); they were not repeated here.

## Remaining gates and responsible next action

The one non-interactive authorization attempt for a **new** ARM product session
stopped at `sudo: a password is required` (exit1). The bootstrap itself did not
execute: no admission file, native state, Gradle, simulator or application was
started. `native-395181e2/authorization-result.json` retains that attempt; its
request is superseded by the final-source request, not reused.

| Remaining lane | State / boundary | Concrete next action |
| --- | --- | --- |
| ARM ordinary Swift **88 unit + 6 UI** | **BLOCKED: fresh session authentication**, not physical testing. | Owner runs the newly prepared one-shot Terminal command; agent executes and assesses the original inventories. |
| ARM owned lifecycle **28 methods** | Same authorization boundary; no current execution. | Agent runs the existing real lifecycle gate in that session. |
| ARM production-adapter cancellation **1 method** | Same boundary; mocks do not close it. | Agent runs the dedicated actual-adapter cancellation case. |
| ARM exact native/simulator finalization | Still required for every new invocation and owned simulator. | Agent verifies receipts, canonical copies, original ownership, Shutdown/deletion and no survivors, including failure paths. |
| Current iPhone app/resource/control methods **13 unit + 2 UI** | Source implemented; **native compile/tests not yet executed**. | Agent runs current framework/project/XCTest/provenance gates; fixes any actual failures. Not owner physical testing. |
| Current unsigned iPhone app and matching JVM driver | **Not produced yet** for this new source. | Same authorized ARM plan builds/hash-binds both; it neither signs/installs an app nor runs capacity. |
| Intel supported-host completion | Prior failures remain; observed runner lacks an available XcodeGen. No-install policy respected. | Provide an already provisioned native Intel runner with XcodeGen2.45.4, or separately authorize provisioning; agent then closes the remaining native/build/Swift/finalization gates. ARM is not a substitute. |
| ART **API37** | **BLOCKED: legitimate KVM access unavailable**. | Provide an authorized KVM-enabled runner; agent executes maintained API37/runtime/LAN-permission cases. |
| ART **API24** | Same KVM boundary; old supplemental ten-control run is not this suite. | Agent executes the maintained older-API cases and original cleanup. |
| ART **API25** | Same KVM boundary; not executed. | Agent executes the maintained API25 cases and original cleanup. |
| Actual iPhone USB/CoreDevice contract | Candidate implemented/offline-tested; actual selected-device schema, copy semantics and timing **unverified**. | Owner supplies a signed current app, trusted unlocked USB iPhone and local authorization. Agent inspects exact bounded output and fixes adapter incompatibilities; never guesses fields or extends the four-second limit. |
| Actual Android physical USB control | Emulator shell evidence does not satisfy physical four-second observations. | Owner provides the current debug test app/USB device and approves only the new private ADB identity; agent runs the source-bound coordinator. |
| Phone-independent Mac generator preflight | Two kernel controls do **not** close the real 125-second preflight. **Authorization blocked, not physical-device blocked**. | The fresh ARM plan executes it without a phone; every later workload repeats its immediately preceding health observation because resource state is time-specific. |
| Full-duration iPhone resource series | Actual phone CPU/RSS/thread and retention observations remain unmeasured. | After signed-app/USB/LAN admission, agent captures and reviews the full-duration Mac/iPhone series; mocked telemetry is never substituted. |
| Android mobile large/steady workloads | Neither physical workload is complete. | Controlled owner LAN/phone required; run separate fresh **20 × 1MiB/concurrency2** and **128 × 10Hz × 1800s** attempts, with resources, 65-second retention and Stop/pin/native cleanup. |
| iPhone mobile large/steady workloads | Neither physical workload is complete. | Same separate workloads and cleanup, using the signed current iPhone app and Mac coordinator, without wireless/tunnel substitution. |
| Physical interoperability/security matrix | JVM↔Android, JVM↔iPhone and Android↔iPhone, both host/client directions, remain device/network work. | Owner controls devices/topology; execute pairing, revocation, restart, cancellation, permission/path denial and payload/lifecycle cases with reviewed evidence. |
| Wider external campaigns | Unclosed; this continuation awards none of them. | Follow the six campaign statuses and exact procedures in [validation](../validation/README.md), including hostile-network, headful, independent interoperability and external security audit requirements. |

## Owner handoff

1. **Now:** run only the final-source private session command supplied with this
   checkpoint. Never rerun either used readiness bootstrap or the superseded
   `native-395181e2` request. Expected output is
   `state/private/result.json`, per-phase receipts/XCTest evidence, and, **only
   after successful app/provenance/cleanup checks**, `phone-export.json` plus the
   unsigned app ZIP and current-source prepared driver manifest.
2. The agent must review those results and finish any native engineering before
   calling the ARM/app lane complete. A Terminal exit0 alone is not sufficient.
3. **Later, after that review:** owner signs/installs the matching app, grants
   device trust/local-network permission, supplies selected private network/device
   settings, and uses **Prepare → Load → review pins → approve → Start host**.
   The exact coordinator command and private evidence contract are in
   [mobile capacity](mobile-capacity.md#mac27-generator-and-iphone-host-candidate).
   If USB control fails, press **Stop** on the phone and preserve evidence;
   never erase the container or retry an ambiguous publication.

No owner credentials, device identifiers, private control records or native
execution state belong in Git or uploaded summaries. No install, reset, clean,
stash, branch switch, automatic merge, signing or old-checkout modification was
performed in this continuation.
