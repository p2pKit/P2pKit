# Separate macOS 14 writer-prerequisite profile

Refs [#425](https://github.com/p2pKit/P2pKit/issues/425),
[#437](https://github.com/p2pKit/P2pKit/issues/437),
[#410](https://github.com/p2pKit/P2pKit/issues/410). The owner requests GitHub-only
sample builds. No local build, SDK/dependency download or device run is authorized
by this change. Earlier [ARM/Intel failures](hosted-lock-continuation-2026-09-16.md)
remain failures; no unchanged retry or privacy workaround is proposed.

## Why this is a different prerequisite, not a substituted pass

The separately named `dependency-lock-candidate-macos14` operation requires real
ARM64 `macos-14`, macOS 14, Xcode **16.2 / 16C5032a** at its explicit application
path, native JDK 17/21, literal Android SDK 36/37.0 and an available originally
Shutdown **iPhone 16 / iOS 18.2** simulator. Both existing profiles retain their
OS/Xcode/runtime/iPhone 17 selections. Operation remains bound through original
dispatch inputs, source commit/tree, context, sealing and recovery.

The [official image inventory](https://github.com/actions/runner-images/blob/dff7cf5f1d89bdac4336cd261875e553582fe769/images/macos/macos-14-arm64-Readme.md)
lists these installed tools; its default Xcode is not the selected 16.2.
[Kotlin 2.4.10 source](https://github.com/JetBrains/kotlin/blob/5687445832cd835b4509b9fbc264cdf1a8201093/kotlin-native/konan/konan.properties)
sets the hard minimum Xcode to 12.5; the documented/tested 26.4 pairing is **not**
proof that 16.2 is qualified. macOS 14 is deprecated and scheduled for retirement
on November 2, 2026. This route is a bounded temporary prerequisite investigation,
not a durable replacement for current-native qualification.

The precise compatibility uncertainty is the existing CryptoKit 0.6.0 cinterop
Klibs' Swift 6.2-produced static archives. A Swift package's source-tools version
alone neither proves nor refutes installed-Xcode binary link compatibility.
No dependency, Kotlin pin, source ABI, SDK override or support-library copy changes.

## Fail-closed order and retained scope

1. Existing exact-source, native ownership, resource, toolchain and real simulator
   inventory admission.
2. Existing unchanged natural JmDNS startup control. A failure prevents both the
   Apple-link probe and full writer; Python kernel acceptance cannot rescue it.
3. [Bounded Apple-link admission](../../scripts/hosted_apple_link.py): fetch only
   three exact committed-checksum cinterop Klibs, at most 128 KiB each / 384 KiB
   total. Use the installed SDK/compiler/linker and actual repository Network
   bridge to force-load/link all three required Apple architectures/platforms.
   Reject malformed archives, wrong hashes, required diagnostics, unresolved
   symbols and incorrect output architectures/platforms. No archive rebuild,
   foreign support-library download or weak-symbol/unresolved-symbol override.
4. Only after successful admission, the **unchanged complete**
   `scripts/prepare-dependency-update.sh <exact-reviewed-SHA>`: supported
   `resolveAndLockAll` writer, all registered subproject check/Dokka dependencies,
   aggregate JSON/XML SBOM, strict postchecks and provenance classifier/curator.

Every probe command uses the same owned controller callback and private bounded
transcripts. Original failures, link inputs/outputs, source hashes and results
remain under encrypted evidence. Finalization, same-home stop after an attempted
writer, selected-simulator retirement, exact full-source checkout, non-cancelling
shared heavy queue and finite deadlines are unchanged. The ordinary sample jobs
and publisher are unchanged and cannot run during a writer operation.

`ADMITTED_LINK_ONLY` means installed-toolchain linking only, not cryptographic
behavior, native runtime qualification or accepted dependency locks. A writer
success still needs independent review of **all twelve locks/metadata**, actual
generated task/ABI/BOM/producer evidence, original #424 transcript custody and
current applicable scan/submission. Root `:check` is not itself a writer
dependency: this is not the complete final `./gradlew check` or release gate.
Current Apple/#409/iPhone 17, genuine Intel, Android parity and sample consumer
requirements remain separate. Physical-phone work stays deferred.

## Verification and resumption boundary

Research packet SHA-256:
`09175aeada9aa57f2d73d785d60ecb92bfd0e1ce8557b6d582f1fd181f5113c9`.
Independent plan review:
`e34d6bea2020fd60abd4c3a75e7f635d96d693b257dbd8d4c4e52ef34382eb3d`,
**APPROVE_BOUNDED_MACOS14_PREREQUISITE_PLAN_WITH_REQUIRED_CONTROLS**.
This is not final-source review or a successful hosted execution.

Executed locally using installed Python 3.9.6 and Ruby 2.6.10, with no network,
compiler or native children: `python3 -I -B -S
scripts/tests/run-hosted-lock-candidate-test.py` — **124 PASS**. Two new profile
tests first failed with the intended `unknown hosted native profile` on the
unchanged controller. The full postimage suite covers exact dispatch/credential
isolation, profile/runtime/device rejection, multicast-before-link ordering,
failed-link refusal, selected-device retirement and cross-profile seal/recovery.
These are synthetic admission/control tests, not execution of those native tools.

`ruby scripts/tests/check-{hosted-lock-candidate,heavy-job-queue,mac-host-admission,windows-directory-control,sample-app-workflow}-policy-test.rb`
(one invocation per file) passed **326 / 261 / 63 / 70 / 76** offline controls.
The hosted policy includes the added Apple-link controls in CI, release and
workflow-test entrypoints without relaxing their unconditional failure behavior.
`git diff --check` passed. Private packet handles are
`macos14-profile-preimage-2EnaWL3l`, `macos14-controller-controls-TkjmAt7f` and
`macos14-workflow-controls-lgCE96Ve`; originals stay outside Git.

The separate helper suite, `python3 -I -B -S
scripts/tests/hosted-apple-link-test.py`, passed **62 offline controls**; the
nonimplementing reviewer independently reran all 62. Independent byte-only
inspection also matched all three retained Klibs/inner archives and each pinned
Maven module's exact URL, size and hash. Historical bytes were not copied as
fresh build inputs, and no native compiler/linker was executed locally.

Independent final source verdicts, with no actionable findings:

- **APPROVE_ROOT_PROFILE_SOURCE_AND_INTEGRATION_BOUNDARY**, report SHA-256
  `708ced9a19d5581247b240347e1b060e4da85b158dfa4192a60e07ba12d7e08b`.
- **APPROVE_APPLE_LINK_HELPER_SOURCE_AND_OFFLINE_CONTROLS**, report SHA-256
  `44ed2d98ed973c18e6630012ff97edda4eb09c24fb34d6ead6263c1e510e773d`.

Both reviews bind exact file hashes at base `27218de13d2c9aa3ac7a4fe2660d3f642245f485`;
the containing commit preserves those reviewed code bytes. Neither verdict is
formal GitHub PR approval or admission of a real host/link/writer. The actual
hosted result must be recorded separately, not inferred from these controls.

The [existing dispatch/custody contract](hosted-lock-candidate-2026-09-15.md#encrypted-artifact-and-safe-resumption)
applies with `operation=dependency-lock-candidate-macos14`. Independently approve
the final implementation and bind both SHA inputs and the tree to that exact
revision before one real invocation. No handwritten/partial locks, bypassed
required checks, production publication, automatic issue closure or local build
is authorized. Sample delivery still needs its real successful matrix and the
normal reviewed-main merge. The whole audit/release remains **NOT_READY**.
