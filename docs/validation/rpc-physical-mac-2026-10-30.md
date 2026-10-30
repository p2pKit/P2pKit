# Physical Mac RPC campaign: preparation checkpoint, 2026-10-30

**No physical RPC qualification criterion has passed at this checkpoint.**
Measured steady workload is **0 seconds**. This report records preparation
failures and fixes for [#525](https://github.com/p2pKit/P2pKit/issues/525), using
the [maintained campaign](../rpc/mac-mobile-continuation.md). The issue remains
open. Device identifiers, signing information, keys, addresses, products and
original logs are retained privately on the owner's Mac.

## Source binding

The original checkout was pulled to verified main:

- Commit: `eb6ba5da6c06a440de852477cf485264b2ab3dd3`.
- Tree: `a11d94517d0a28e1045c880eeb3fbf21d34de81b`.
- Separate campaign branch: `codex/rpc-physical-qualification-20261030`.
- Fix PR: [#532](https://github.com/p2pKit/P2pKit/pull/532).

The corrected preparation candidate is
`ae3a76e95987618eace43e8ed3ee1a8273ba14c6`, tree
`d83022b2a737d9c9a538cda0371d3f8e6d32299b`. Its fixes are:

- `5af1d503b60d11210441125e2666872bb01427d1`: bootstrap the Gradle
  distribution under a separate preparation deadline before ordinary tool
  checks, preserving the 120-second Stop deadline.
- `1d51ae6aab3c56286fc7e371f3ec6b3b0d06e67e`: accept the observed nested CoreDevice file metadata while
  retaining exact size/type, filename, directory and symbolic-link checks.
- `ae3a76e95987618eace43e8ed3ee1a8273ba14c6`: use the sample's exported
  `RpcApplicationSession_` Swift name, disambiguating it from the library's
  authorization-session class. The Swift consumer fixture covers construction.

Report-only commits after this candidate are not tested product source. There
is no final preparation manifest or qualified signed iPhone installation yet.
New preparation must bind every product to one exact source/tree before any
physical workload; the partial products below are not admitted for that use.

## Observed environment and prerequisites

The Mac is native Apple Silicon (`Mac16,1`), with 16 GiB RAM, macOS 27.0
(`26A428`), and Xcode 27.0 (`27A266a`). Xcode first-launch setup passed.
Native JDK 17.0.17 and 21.0.11, Python 3.14.6, XcodeGen 2.45.4, Android
platforms 36/37.0, platform-tools and NDK 29.0.14206865 were verified locally.
Existing development signing and a profile covering the selected iPhone were
found; the signed application build still needs to complete.

Selected physical devices are a Huawei AQM-LX1 (Android 10/API 29) and an
iPhone 17 (iOS 27.0.1). Android USB debugging is authorized to the existing
server; approval of the campaign's separate private ADB key remains pending.
The iPhone is paired over USB with Developer Mode enabled. Installation and
Local Network permissions for the corrected products have not been exercised.
Mac/Android private Wi-Fi interface/subnet observations are retained privately.
The iPhone Wi-Fi address/interface still need an actual observation; its
CoreDevice-advertised hostnames did not resolve to an IPv4 address.

Available RAM was most recently 7.18 GiB using the maintained conservative
free + inactive + speculative page calculation. That exceeds the instantaneous
6 GiB prerequisite, but the actual 125-second generator preflight has not run.
Available disk space was approximately 22 GiB after the first product build.

Android battery observations progressed from 25% to 72% while USB charging.
Reported battery temperature was 35 degrees Celsius. These are charging-state
observations, not battery-discharge or CPU-temperature evidence. No iPhone
battery/thermal workload series or calibrated energy measurement is available.

## Retained preparation attempts and cleanup

| Attempt/source | Original outcome | Cleanup evidence |
| --- | --- | --- |
| Initial verified main | First JDK check triggered a wrapper Stop that downloaded Gradle and timed out; final exit 125, Stop exit 143 | Zero owned survivors recorded; failure retained |
| `5af1d503`, shared desktop session | Distribution bootstrap and Stop returned zero, but three newly observed background processes had unobserved parentage; final exit 125 | Ownership remained UNKNOWN; zero owned survivors is not cleanup certification |
| `5af1d503`, isolated session | Eight tool/key checks and the Gradle product build passed; Xcode app build failed with exit 65 because Swift selected the authorization-session class | Each completed supervised command recorded Stop exit zero, unchanged source and zero owned survivors; no phone deployment occurred |

The reviewed `scripts/with-darwin-audit-session.py` bootstrap preserved audit
policy and permanently restored the invoking ordinary account before tools or
products ran. The first isolated worker retired after the failed preparation.
The corrected candidate's new worker is waiting on an expired macOS
administrator authorization. No workload can proceed past that prompt.

## Partial artifact hashes from the failed preparation

These outputs belong exclusively to commit
`5af1d503b60d11210441125e2666872bb01427d1`, tree
`de2dc3e726f55e46825561e3f5a5440cceb1bf01`. The Gradle build passed in
17 minutes 52 seconds; the subsequent signed-app build failed. Hashes identify
retained partial outputs and do not constitute a complete prepared campaign.

| Product | SHA-256 |
| --- | --- |
| Android debug APK | `6e20c1f4bb54395dbadaef0a15d93a6e691838c3a44409d34670781530074781` |
| Mac driver manifest | `19c6370324b5dbe6844726eefbad9e8647f4ee359dbc5aae1244fc2d55000c20` |
| Mac capacity driver JAR | `d78ec943f18a43ec598b0f03b93ced2489dba8af3c1c777698cf100a727bc994` |
| Mac scoped-TCP native library | `e2dc2485cba83bf62d63d0e527a4ba38ed3774fb0b3d86dfddd5a4447ad8c79e` |
| Mac scoped-TCP manifest JAR | `7dde76da6c669b395451a0e4810c53c79e4f9246b16ec855643424f3e425a1ee` |
| iPhone ARM64 framework executable | `4d4f6e5157ff84775d6b29648cec546f06c3309865601ddff784bd79042d2cde` |
| Universal simulator framework executable | `dad8def8a251141e04cb7abc491bdbedd689aa93fb70afdaf2e620662f37f764` |
| Signed iPhone application/executable | Unavailable: compilation failed before a complete signed product |

## Physical results and remaining scope

| Phone host | Clients | Large/correctness/churn | Separate measured steady | Throughput, latency, schedules and resources |
| --- | --- | --- | --- | --- |
| Android | 128 | Not run | 0/1,800 seconds | Unavailable |
| Android | 256 | Not run | 0/1,800 seconds | Unavailable |
| iPhone | 128 | Not run | 0/1,800 seconds | Unavailable |
| iPhone | 256 | Not run | 0/1,800 seconds | Unavailable |

Connection success, response correctness, p95/p99 latency, missed schedules,
CPU, memory, native threads, connected-idle overhead, post-Stop phone drain and
separate Mac generator utilization therefore have no physical workload result.
Disconnect/reconnect, sent cancellation/deadline, authorization/revocation,
fairness, deterministic cleanup and the actual application role matrix are
also pending physical execution.

The current harness still needs reviewed extensions for the simultaneous
255-Mac-plus-one-physical-phone client roster, a genuine socket slow consumer,
long mixed-fault workloads and unplugged recording. A separate phone smoke
test and a delayed handler cannot satisfy those requirements. Actual discharge
will require an identified physical unplug/reconnect action or a supported
charging-control method; simulated battery state is insufficient. Serious or
critical thermal observations must stop the attempt with cleanup retained.

Immediate blockers are the renewed Terminal administrator prompt, completion
and verification of all corrected source-matched products, iPhone network
observation, campaign-key consent and first-install/Local Network admission.
No acceptance checkbox in #525 was changed. No publication, tag, 512-client
claim, cancelled full audit or deferred #520 investigation was performed.

## Fix validation and hosted checks

- `TMPDIR=/private/tmp /opt/homebrew/bin/python3 scripts/tests/rpc-ios-usb-test.py`:
  26 passed.
- `TMPDIR=/private/tmp /opt/homebrew/bin/python3 scripts/tests/run-rpc-mac-campaign-test.py`:
  26 passed.
- `TMPDIR=/private/tmp /opt/homebrew/bin/python3 scripts/tests/rpc-mobile-mac-control-test.py`:
  37 passed. An earlier invocation retained nine errors because its temporary
  paths traversed macOS's `/var` symlink; the canonical private temporary root
  resolved the fixture-environment problem without weakening path checks.
- Swift consumer fixture: ARM64 iPhone SDK typecheck with warnings as errors
  passed against the built framework, including the corrected sample owner.
- `scripts/tests/check-markdown-links.sh`: 1,012 links across 175 active
  Markdown files passed with this report staged; embedded checks passed.
- `git diff --check`: passed for the functional fixes and this report.

The first hosted run
[41092885339](https://github.com/p2pKit/P2pKit/actions/runs/41092885339)
retained an Apple ARM64 failure in `:p2p-core:iosSimulatorArm64Test`
(888 passed, one failed), with known cleanup. The sanitized artifact identified
that task; encrypted original failure evidence was preserved. Other completed
components passed, while the run was not yet wholly complete at this checkpoint.
The corrected candidate's required modular run
[41098167553](https://github.com/p2pKit/P2pKit/actions/runs/41098167553)
is pending. Dependency review and advisory scans passed for that candidate.
Neither a pending gate nor a physical phase that has not run is a qualification
pass.
