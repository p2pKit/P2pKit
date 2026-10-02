# October 2: official ARM27 continuation checkpoint

## Latest update: repaired ordinary Swift action passed

The existing authorized **Swift-only** session at
`2e8af8daedb39f0711fd2dd45ca96337d88fb334`, tree
`d7ad647a7cbf31e290c5ddb3c5408f077db534db`, completed at12:42:29 UTC on October2.
The agent independently reviewed the saved evidence without another bootstrap,
test execution or password request. This consumed request must not be repeated.

| Executed lane | Independently verified result |
| --- | --- |
| Fresh native admission | **129 PASS**,169.136s:36 policy,45 modeled Darwin,48 native-class controls. Invocation `1eda863aa1614a72bcb4569051172d61`. Required for this new source/session, not additional RPC scenarios. |
| Toolchain and producers | Official native Mac27/Xcode27.0, JDK17/21, installed XcodeGen package, current-source XCFramework/minimum OS and generated project passed. |
| Cold simulator readiness | **PASS:35.032681s under120s**, invocation `19ea99acb8b0468fa6204e14a3408c4e`. No readiness retry or deadline extension. |
| Ordinary Swift | **88 unit +6 UI PASS**, zero failed/skipped; exact source-method inventory and original assessor passed. Both English/German Port-input cases now succeed with the real keyboard/parser interaction. Invocation `de5dc7447e6e49a2ab31f155867f826a`. |
| Provenance and cleanup | **25 outer +1 nested finalizers PASS**; current-producer binding and1,937-file XCTest manifest verified. Every wrapper stop succeeded, no owned survivors/unclassified lifetimes/discovery errors, exact owned simulator shut down and deleted. |

Evidence: `P2pKit-mac27-ui-recheck-20261002-p5nfg_ka/native-2e8af8da`,
job `45b6134cf01541ae845b3e0b109c4914`. Independent review `16-*` and the7,342-entry
preservation index `19-*` are in its parent. Result SHA-256:
`cb1b2f0fc58c8a183480cb7c7fece5e93ed28dc80216f6ff203ed92c67b78bcc`.
Swift receipt SHA-256:
`8122cc36fb880a4166c490f21459fa3e791bf8c3e8ea2d80c6e8fe29d98694ee`.

The result is **PASS for the selected eight-phase plan**, not full RPC/LAN
qualification. Lifecycle, cancellation, phone, driver and clock phases were
explicitly **not requested**. Their earlier source-bound results below remain
unchanged. The21,209/1,665/2,167-entry native77/e815/f455 indices were reverified;
no historical failure was rewritten as a pass.

The scoped runner/authorization controls also passed **25+12 offline methods**
locally and in CI at this source: run `37003239903`, job `110825501585`, artifact
`11224532036`;594-byte ZIP SHA-256
`ef1e1114ab6b5bf0568d11f943f59d9efc38de4e417301d54856a493187e3c87`, verified before
reading. These are the same37 methods on two hosts, not74 unique tests.

A separate read-only snapshot at12:43:26UTC observed **5.312744GiB available**
of16GiB. It is not the memory level measured throughout the preceding tests or
a125-second health pass. Work that does not require capacity admission can
continue with available RAM; the6GiB capacity requirement was not changed.
Foundation remains **NOT_READY**; the resource, runner and physical boundaries
are listed below. No further Swift authorization is pending.

## Earlier update: lifecycle, cancellation and current iPhone gates passed

The fresh dialog session at `77aed5dcf5a7c96980affb61f5e828dac7973320`, tree
`0a33bf3cf57edde1f22c5443f321b0f289877bff`, completed on the official Mac27/Xcode27
host. It is **consumed**. Its result remains **FAIL** because ordinary Swift UI
and available-memory admission failed; all previous failures below remain intact.

| Lane actually executed | Independently reviewed result |
| --- | --- |
| Native controls | **129 PASS**,153.769s, including both previously failed SIGTERM controls. The actual new dialog environment recorded blocked/ignored SIGTERM before process-local restoration; the old unrecorded mask is not relabeled. Invocation `c8b99497f8fc48bdad67e4b2612d181b`. |
| Toolchain, cold readiness and producers | Native JDK17/21, Mac27/Xcode27, installed resources, fresh simulator readiness, XCFramework/minimum OS and generated project passed. No translated or prebuilt app substitution. |
| Ordinary Swift | Exact inventory executed: **88 unit PASS;4 UI PASS,2 UI FAIL**. English/German Port typing lacked keyboard focus after an unreachable tap. Invocation `a39be98e51d14df8a5dfaa9a61c68203`, product65/stop0/final65. Original assessor rejects it. Xcode's600-second diagnostic-collection timeout is also retained. |
| Owned lifecycle | **28 PASS**, exact original selection, nested provenance and before/after Shutdown verified. Invocation `74ddc5734fdb4c4c80753b3b8138adc1`. These methods overlap the ordinary unit inventory; do not add them into a percentage. |
| Production-adapter cancellation | **1 PASS**, actual diagnostic flow/native Job plus accepted callback retirement within the original2-second window, and a live replacement/no-late-delivery control. Invocation `f0140e5fee4648d18decad4dddc3c6b0`. |
| Current phone application | **13 unit +2 UI PASS**,1 nested framework producer and2 nested provenance checks. Unsigned ARM64 device app built with actual Mach-O minimum iOS15.0; its simulator shut down/deleted. Invocation `e3730d1d541c42779ba223730cad6673`. No signing, install, USB or physical RPC test. |
| Matching JVM driver | **PASS: preparation only**,24 source-bound JARs, invocation `13af03e887414ead8e180b73fd7b2798`. No mobile workload executed. |
| Mac generator preflight | Full125.002254666s/12,500 expirations/126 resource snapshots executed. Maximum gap62.651209ms passes<100ms; minimum available memory4,064,706,560bytes fails6,442,450,944bytes. Original health verdict **FAIL**, invocation `db957f2bbdb34cbe9a21181dba834754`. No capacity pass or blind retry. |
| Cleanup | **45 outer +6 nested finalizers** independently validate; every same-home wrapper stop succeeded, with no owned survivors, unclassified lifetimes or discovery errors. Both exact owned simulators were deleted. Successful cleanup does not erase either product/health failure. |

Evidence: `P2pKit-mac27-dialog-signals-fix-20261002-o9f_cjj4/native-77aed5dc`,
job `61138c7507714903b2bff81040f4dd7d`. Reviews `14-*`, `16-*` through `19-*` and
the21,209-entry preservation index are in its parent. Final result SHA-256:
`48c7aae3c1714c3e53511f24280a47067c92bf930e4a483a45b19ed956e7ba63`.

The exported `p2pkit-rpc-iphone-unsigned.app.zip` contains5 files/4,749,822bytes,
SHA-256 `d7b514d08cccc33117f36e6991d1cc546abeb9e23f672e7cb3d34696b19cfe5e`.
Its `phone-export.json` and matching driver manifest bind **77aed5dc**, not a later
UI/report commit. Driver manifest SHA-256:
`be4e0bce3f0fd2f9c3c2627f447e570d80c517bb8aed5b7c547e8c729522ee78`.
Keep that source binding for signing/device handoff; never silently relabel it.

The signal repair's33 offline methods also passed on Mac and Linux: CI run
`36996596428`, job `110804631529`, artifact `11222016095`,598bytes, ZIP SHA-256
`5439b96c4474014d63cd6099831057defe854d9231d5db091d009e060808f1d0`.
These are the same19+14 methods on two kernels, not66 unique tests.

At that checkpoint, the next action was the [scoped ordinary Swift repair](local-arm27-qualification.md#recheck-only-the-remaining-ordinary-swift-action).
The later2e8af8da result above closes that repair; the original failed run remains failed. The repair
used the existing Done/reveal workflow and required the fresh source-bound88+6
action and admission/finalizers. Do not repeat the passed lifecycle, cancellation
or phone suites. The memory failure requires a quieter/adequately resourced
generator, not weaker limits or permission to close unrelated owner applications.

## Earlier update: dialog authenticated; cancellation signal delivery failed

The owner authenticated the agent-initiated macOS dialog. `native-e8158bbd` at
`e8158bbd7dcb265d894ade23666ad0554a0a51f9`, tree
`e6c46ee2220f96c003d31d0ba673a72bb0b6a936`, is now **consumed**. The unchanged
bootstrap proved a fresh audit session and irreversible return to the normal
account. No password was handled by the launcher or agent.

All129 controls executed in226.205s: **127 passed,1 failed,1 errored**. Real
controller SIGTERM cancellation was absent from its receipt; the product hit
its original20-second deadline. The actual opaque-token signal returned0 but
the target did not exit within the original40-second capture bound. Neither
failure is converted into a pass. Native invocation
`3157f9777d184c06936442c37217c729`, job `766ddb4f915b4ab78df60bc4f35a99b2`,
receipt SHA-256
`05e514751b6051068b79df0d59f6c45be7e3d677a1ba3498de0fd0d289fcad99`.
The outer finalizer independently validates: stop0,386 owned lifetimes,
no survivors, unknown lifetimes or discovery errors. Product/final exit1;
no toolchain, simulator, Swift, phone, driver or clock phase subsequently ran.

Evidence remains in `P2pKit-mac27-tool-resources-fix-20261002-vsx3kxyv/native-e8158bbd`;
the independent review and1665-entry index are in
`P2pKit-mac27-dialog-signals-fix-20261002-o9f_cjj4`. Direct and non-administrator
Standard Additions probes observed empty masks; those do **not** establish the
privileged helper's incoming mask. That old mask was not recorded.

The [fresh-process signal preparation](local-arm27-qualification.md#fresh-process-signal-environment)
records and restores ordinary cancellation delivery after privilege/session
admission and before spawning any child. It preserves the original bootstrap,
native controls/executor/ownership checker and every deadline. A new exact-source
run is required to observe actual dialog inheritance and requalify the failed
boundary; no old session, state or product result may be reused.

The preceding resource/stream repair's43 changed offline controls passed locally
and in CI at `e8158bbd`: run `36992765063`, job `110792551391`, artifact
`11220062438`,788bytes; ZIP SHA-256
`6551ffe683343293ec674f5d0c19688ef8610ad37f22f8a92d12104d7c41691c`,
verified before reading. Those are offline passes, not new Swift/phone results.

## Earlier update: wrapper repaired; tool-resource and stream failures isolated

The owner executed `native-f45584cd` at
`f45584cdd89b3bbbf5492ae2950200f3b491453c`, tree
`f81c6e74af1ce00ee0a28bcaa96bb4b8d61af004`, on macOS27.0/Xcode27.0(27A266a).
That request is **consumed**. The result remains **FAIL**, not a pass or a
completion percentage. Its preceding `8783cc9d` failure below remains unchanged.

| Executed lane | Actual evidence/result |
| --- | --- |
| Native ownership controls | **129 PASS** in109.998s:36policy,45modeled Darwin,48native-class. Invocation `0ab3df7746ee45cc9b67ed50eecd4c8e`; wrapper stop0 and complete native finalization,320 recorded owned lifetimes, no survivors/unknowns/discovery errors. |
| Toolchain and producers | Actual native JDK17/21, Mac27/Xcode27, first-launch/translation checks, installed XcodeGen version, shared XCFramework/minimum OS and current-source mobile-driver preparation passed. No mobile workload ran. |
| Fresh simulator readiness | **PASS**, product28.512314s under120s, invocation `f4139a8190704b62b2fe79108617ced3`. The separate phone simulator reached readiness in26.411s. |
| Ordinary Swift, lifecycle and cancellation | Each `xcodebuild` exited70 before XCTest: generated test-host app could not be resolved. Missing nested provenance was a downstream consequence, not permission to omit it. No88+6,28 or1-method pass is claimed. |
| Current phone application | Its framework producer passed; `phone-unit-ui` exited70 for the same test-host failure. No13+2 methods or unsigned-device app were produced. |
| Mac generator clock | First page-observer command completed, but strict private-file read rejected0644 output. The125-second clock measurement did not execute; no health/capacity pass. |
| Cleanup | All **39 outer command receipts** independently validate with successful same-home wrapper stops and no owned survivors, unknown lifetimes or discovery errors. Both exact app/phone simulators were shut down and deleted. Product failures remain failures despite successful cleanup. |

The preserved run is in
`P2pKit-mac27-wrapper-preparation-fix-20261002-mp3y72bi/native-f45584cd`.
Read-only review and the2167-entry evidence index are in
`P2pKit-mac27-tool-resources-fix-20261002-vsx3kxyv` (`00-*`, `01-*`).
Native-control receipt SHA-256:
`e737865609070f7538848202b35b5efadf26ab334ee5b05ae8bddf51975ba606`.
The conservative `nativeAttempt/PASS_OUTPUT_ONLY` log diagnostic is not the
receipt verdict; the separate source/context/canonical-receipt checks above
prove that particular native leaf passed, not that the whole run passed.

Root cause: the private XcodeGen binary was separated from its31 installed
settings resources. It returned0 while reporting missing presets. The repair
binds/stages the complete package, rather than modifying app/test configuration.
Shared USB/clock command streams now use create-only0600 descriptors, without
changing global umask, strict file admission, ownership or deadlines.
Changed offline suites pass: local controller16, package13, command streams6,
and one-shot authorization8. An actual installed-tool packaging regression
generated a synthetic project with correct product/test-host defaults; only
AppleScript **compilation**, not authentication/bootstrap, was performed at this
repair checkpoint. These are not replacement RPC qualification results.

The [one-shot dialog launcher](local-arm27-qualification.md#agent-initiated-macos-authentication-instead-of-terminal-copypaste)
lets the agent initiate a fresh prepared run and the owner authenticate directly
in macOS, without copying commands. It grants no persistent root access and
never retries a cancelled or consumed request. A new exact-source native session
is necessary to validate the repaired gates; prior passed product counts are not
added to a new qualification percentage.

## Earlier update: first product session failed after the controls

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

The original non-interactive `sudo` refusal remains in
`native-395181e2/authorization-result.json`. It is historical, not the current
boundary: the dialog works and both77aed5dc and2e8af8da sessions above are consumed.
The UI recheck is complete; do not prepare or repeat another Swift request.

| Remaining lane | State / boundary | Concrete next action |
| --- | --- | --- |
| ARM ordinary Swift **88 unit +6 UI** | **CLOSED/PASS at2e8af8da**, exact88+6 inventory, both repaired cases and nested provenance verified. The77aed5dc failure remains intact. | Preserve the reviewed result; no further UI recheck or authorization needed. |
| ARM owned lifecycle **28 methods** | **CLOSED/PASS at77aed5dc**, with exact selection/provenance/retirement. | Do not rerun for the unrelated UI interaction change. |
| ARM production-adapter cancellation **1 method** | **CLOSED/PASS at77aed5dc**, actual adapter/native and callback barriers. | Preserve its receipt; no mock substitution or unrelated rerun. |
| ARM exact native/simulator finalization | **25 outer +1 nested PASS at2e8af8da**, its owned simulator deleted; earlier **45+6 PASS at77aed5dc**, both simulators deleted. | Preserve each source/session separately; do not combine finalizer counts into a qualification percentage. |
| Current iPhone app/resource/control methods **13 unit +2 UI** | **CLOSED/PASS at77aed5dc**, native compilation/XCTest/provenance verified. | Preserve the exact source-bound app result. USB/device compatibility remains the separate row below. |
| Current unsigned iPhone app and matching JVM driver | **Produced and hash-verified at77aed5dc**; unsigned ARM64/iOS15 app and24-JAR driver. | Use that frozen source/artifact pairing for owner signing/device handoff; never relabel it as a later report/UI commit. |
| Intel supported-host completion | Prior failures remain; observed runner lacks an available XcodeGen. No-install policy respected. | Provide an already provisioned native Intel runner with XcodeGen2.45.4, or separately authorize provisioning; agent then closes the remaining native/build/Swift/finalization gates. ARM is not a substitute. |
| ART **API37** | **BLOCKED: legitimate KVM access unavailable**. | Provide an authorized KVM-enabled runner; agent executes maintained API37/runtime/LAN-permission cases. |
| ART **API24** | Same KVM boundary; old supplemental ten-control run is not this suite. | Agent executes the maintained older-API cases and original cleanup. |
| ART **API25** | Same KVM boundary; not executed. | Agent executes the maintained API25 cases and original cleanup. |
| Actual iPhone USB/CoreDevice contract | Candidate implemented/offline-tested; actual selected-device schema, copy semantics and timing **unverified**. | Owner supplies a signed current app, trusted unlocked USB iPhone and local authorization. Agent inspects exact bounded output and fixes adapter incompatibilities; never guesses fields or extends the four-second limit. |
| Actual Android physical USB control | Emulator shell evidence does not satisfy physical four-second observations. | Owner provides the current debug test app/USB device and approves only the new private ADB identity; agent runs the source-bound coordinator. |
| Phone-independent Mac generator preflight | **Executed at77aed5dc: duration/gap PASS, memory FAIL**; minimum3.79GiB versus6GiB. Later instantaneous5.31GiB is not a passing health trace. Not a physical-device boundary. | Owner makes an adequately resourced/quiet generator available without agent termination of unrelated apps. Agent measures fresh health immediately before a real workload; no blind health retry or relaxed threshold. |
| Full-duration iPhone resource series | Actual phone CPU/RSS/thread and retention observations remain unmeasured. | After signed-app/USB/LAN admission, agent captures and reviews the full-duration Mac/iPhone series; mocked telemetry is never substituted. |
| Android mobile large/steady workloads | Neither physical workload is complete. | Controlled owner LAN/phone required; run separate fresh **20 × 1MiB/concurrency2** and **128 × 10Hz × 1800s** attempts, with resources, 65-second retention and Stop/pin/native cleanup. |
| iPhone mobile large/steady workloads | Neither physical workload is complete. | Same separate workloads and cleanup, using the signed current iPhone app and Mac coordinator, without wireless/tunnel substitution. |
| Physical interoperability/security matrix | JVM↔Android, JVM↔iPhone and Android↔iPhone, both host/client directions, remain device/network work. | Owner controls devices/topology; execute pairing, revocation, restart, cancellation, permission/path denial and payload/lifecycle cases with reviewed evidence. |
| Wider external campaigns | Unclosed; this continuation awards none of them. | Follow the six campaign statuses and exact procedures in [validation](../validation/README.md), including hostile-network, headful, independent interoperability and external security audit requirements. |

## Owner handoff

1. **Swift work is complete:** the agent independently verified the2e8af8da
   `state/private/result.json`, exact88+6 results, fresh provenance and complete
   finalizers. No new password/Terminal command is needed for this closed item.
   The passed77aed5dc phone package was not rebuilt or relabeled.
2. Before physical capacity work, make an adequately resourced generator
   available. Its fresh immediately preceding125-second health trace must keep
   available memory at least6GiB and the maximum clock gap below100ms. Ordinary
   engineering can continue below6GiB, but no capacity pass is awarded for it.
3. **Later, at the actual device boundary:** owner signs/installs the matching app, grants
   device trust/local-network permission, supplies selected private network/device
   settings, and uses **Prepare → Load → review pins → approve → Start host**.
   The exact coordinator command and private evidence contract are in
   [mobile capacity](mobile-capacity.md#mac27-generator-and-iphone-host-candidate).
   If USB control fails, press **Stop** on the phone and preserve evidence;
   never erase the container or retry an ambiguous publication.

No owner credentials, device identifiers, private control records or native
execution state belong in Git or uploaded summaries. No system/toolchain or
physical-device installation, reset, clean, stash, branch switch, automatic merge,
signing or old-checkout modification was performed. Source-built XCTest hosts
ran in the specifically owned disposable simulators; those simulators were deleted.
