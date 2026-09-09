# Continued September9 cohort — exact approvals, not audit completion

145/193 independently approved repository-repair rows (75.1%); 48 remaining (24.9%): 26 repair-category rows, 21 external-validation rows and architecture decision #120; 60 new audit findings. Counts are not effort, GitHub closures, platform acceptance or release readiness. **Whole audit NOT_READY.**

## Eighteen final approvals

Independent reviewer `/root/review_cohort_0910_execution` approved all18 exact final revisions. Base `0770ec9950830983acb605a4bedd7384b8f6c3b9` / tree `e77a11cd5612bac242a132bb7210903db9f912f4`; composed diff SHA-256 `d2e7fc9823b9458c5d15236aa51b55095ea1cb324bc9a9c54f48150878b201d4` (113 exact hunks/28files). Final report SHA-256 `a9d865fb88a82cb1f596328e28273dec79a826112fe8ab4a840158e9a1e7ee89`. The14 focused commits below reproduce that approved composition; later working-tree changes are not included.

| Issues | Commit | Correction / limit |
| --- | --- | --- |
| [#288](https://github.com/p2pKit/P2pKit/issues/288) | `9bfe039e02e33ade22433c0bcfa6444b59a031d7` | Label the chosen app-scoped external/internal inbox domain truthfully; accepted keep-external alternative, no migration. |
| [#312](https://github.com/p2pKit/P2pKit/issues/312) | `e5ab733fbd14b245924ca460856f7430cbfe58c6` | Export the actual default 30000 ms keep-alive timeout in both Desktop diagnostic builders. |
| [#316](https://github.com/p2pKit/P2pKit/issues/316) | `feb6292d0316884ef67a648dd33abafdf01485f3` | Remove only unused Kotlin pause state; preserve live Compose/Swift controls and diagnostics schema. |
| [#239](https://github.com/p2pKit/P2pKit/issues/239), [#273](https://github.com/p2pKit/P2pKit/issues/273), [#276](https://github.com/p2pKit/P2pKit/issues/276), [#277](https://github.com/p2pKit/P2pKit/issues/277), [#243](https://github.com/p2pKit/P2pKit/issues/243) | `2d7d40718e40f5284ae9b3640d6f361e90d6e232` | Document synchronous, concurrent logger calls and nonblocking obligations; no latency isolation guarantee. Document all String QR carriers, syntax validation, trusted pinning and handshake-proof boundaries. Document tolerant post-close provisioning stop without inventing runtime cleanup or cancellation guarantees. Document capability flags as advisory, not enforced authorization or security controls. Correct connection-lock/epoch-adoption documentation; no invented additional race repair. |
| [#205](https://github.com/p2pKit/P2pKit/issues/205) | `d313b1b1baaff6e8e245567f57670a3363af43e4` | Await real reconnect-owner completion instead of a 150 ms absence oracle; retain dial/state assertions. |
| [#206](https://github.com/p2pKit/P2pKit/issues/206) | `4e24d9c9daf45b89e6482eec046cf64b95197c1d` | Use secure in-memory fixture identities and the canonical admission limit; remove process-wide home mutation. |
| [#217](https://github.com/p2pKit/P2pKit/issues/217) | `7b24ad8cfb805cd6a4276f358810d255298fea88` | Make socket accept timeout fail immediately with ordinal/deadline and the original exception cause. |
| [#281](https://github.com/p2pKit/P2pKit/issues/281) | `77fe88a4e9a4057a3820ca34e81b2e6dcb29a135` | Release only the test-owned provisioning token in finally; no global reset or production arbiter change. |
| [#167](https://github.com/p2pKit/P2pKit/issues/167) | `58d1d741296896cb92f01c0ccc7737609c782373` | Preserve manual display metadata precedence while retaining trusted pins and additive routing. |
| [#169](https://github.com/p2pKit/P2pKit/issues/169) | `fd223850ce386192079b3d6e2b0ae69f84595d17` | Use bounded monotonic rejection windows, exact concurrent counts and a true NoOp short-circuit. |
| [#240](https://github.com/p2pKit/P2pKit/issues/240) | `49e6b10765cdd0f3582ba89933d5ac8c440b209e` | Attribute observer-only failures as ConnectionFailed; preserve real data-start taxonomy and cancellation. |
| [#241](https://github.com/p2pKit/P2pKit/issues/241) | `9876c9e4b9ba7bc9c1b2f7fac1bd3b597a05c440` | Warn on restart after retained failed observer unregister; distinguish ordinary idempotent start. |
| [#255](https://github.com/p2pKit/P2pKit/issues/255) | `a13745a2c77441025f74e165cab2844029cade67` | Truthful KDoc plus characterization of existing NonCancellable cleanup; no new fanout/cancellation production fix. |
| [#245](https://github.com/p2pKit/P2pKit/issues/245) | `f58e13b4d0a11b545b5ab569127327e76b27782f` | Fence reconnect watchdog episodes, register before eager handlers and retire detached timers outside the lock. |

## Next37 source revisions:27 counted,10 affected-validation pending

Coordinator `/root/review_cohort_0910_execution` approves32 exact source revisions and24 focused completed scopes; report SHA-256 `0771537ffbb288dbde7b9166ce99b98c187353cf47ce65dd1080a15a23817180`. Independent sidecar reviewer `/root/review_sidecars_next` approves3 host repairs and leaves2 Apple rows pending; report SHA-256 `990e7568c58c064e13a82f1c8140650217a5e1d941959ff1cb38c3986c588a8f`. Together27 gain repair-row credit, not37. Existing source-review scopes plus exact final-delta binding are reused, not a fresh whole-file sweep.

| Issues and count status | Commit | Focused correction |
| --- | --- | --- |
| #172 pending, #176 pending, #256 approved | `348cf179194a72afdc7abbd097898884fc25e7df` | fix(transfer): Acquire private staging lazily and preserve directory failures |
| #249 approved, #252 approved | `1e886dcd099806e11c8656c38daf97ff27f51c0a` | fix(transfer): Keep progress monotonic and document submission accounting |
| #218 approved, #342 approved, #272 approved, #292 approved, #220 approved | `4f9da4f98c500988975c274d1d3709572e7f954e` | test: Strengthen value and asynchronous fixture contracts |
| #156 pending, #158 pending | `9ab46d7bdd52a551e4be525dd7b839b32928b6ac` | fix(lan): Set TCP options and align bounded inbound capacity |
| #378 pending | `ac49fee0f81bf0bd34ec01d200f9b04bc13885e5` | fix(audit): Retire owned readonly outputs without mutating shared files |
| #236 pending | `2c1a9ba54a895b8317df69e7dd9b20b12b513d5f` | build: Enforce canonical licenses across covered publication archives |
| #212 approved, #230 approved | `7bc68b6718bdb1a3f3e61dbf2a9fd5c1defd6596` | fix(docs): Align maintained contract and fail-closed release metadata |
| #219 approved, #213 approved, #215 approved | `e9b8be24672fac0421326dfa8e87718180df72d5` | docs: Define transport integration, error recovery and threat boundaries |
| #237 approved, #216 approved | `bb1ad32db4ffb592d75724a9600409ba8d29a91d` | docs: Centralize validation dispositions and describe gate scope |
| #307 approved, #309 approved | `60aadb560ade72250ec575a312a2b81b2dfd2aba` | docs(core): Explain transfer limits and keep public KDoc links public |
| #248 approved | `248f8177c317e79c8de680ceb8ad0b239dd3a71e` | fix(android): Make identity content and directory durability explicit |
| #250 pending | `d4ce3598a1d139721e0a2744a3779f2f38bfc7de` | fix(identity): Serialize secure storage per namespace |
| #261 pending | `e0e52cb9598e9ba367420fa7f5d1c012832223c6` | refactor(identity): Share legacy AppId namespace sanitization |
| #168 approved | `417aab2b62e0f9016a428fa8d6a974b2245b7896` | fix(core): Retire terminal sessions without waiting behind the send gate |
| #195 approved | `b4239a58989eec5ed1fe5f356e224adb1a5d2357` | fix(android): Classify post-start permission loss using current grants |
| #275 pending | `67deecddbb74478e89d03551add8316c8bd420f2` | fix(provisioning): Avoid logging manual endpoint details |
| #278 approved | `bb513c25f1983b91be2d60ab2a96dca846d1157c` | fix(desktop): Report interface polling failures once per episode |
| #279 pending | `a90a3ae12ba8047099ac036bb28b2144af0c5d19` | docs(provisioning): Clarify cancellation and close semantics |
| #282 approved | `63e1ae71d4f87d87ae67486b565f4bf41d2ad2a8` | fix(android): Share dual-stack manual address scanning |
| #173 approved | `7a57e7274a692b78bc913248b3a5359765c25280` | fix(core): Preserve public StateFlow operator fusion for peer lists |
| #232 approved, #260 approved | `1235d293090a489b54defc719870043b63c4033e` | docs(core): Clarify cancellation and hot-stream collector ownership |
| #271 approved | `75ee783185d4760394749e41253eca299db6c97b` | fix(core): Include safe offending values in configuration errors |
| #302 approved | `ffd92738009638d4a4832c575530d03c2b930e54` | refactor(core): Remove unused manual-peer projection |

Pending means independently source-approved but **not counted**: Windows #172/#176/#378; Apple #156/#158/#250/#261/#275/#279; publication-artifact lane #236. All exact source reviews, hashes and per-row executed scope/remaining validation are in `issues.json continuedCohort`.

## Verification retained, not rerun by this documentation task

- `cohort-0910-original-r1` (09:31–09:33UTC):22 fresh cases,16 intended failures/6 passing controls; exits1/0/1. Controlled production restoration, not untouched baseline.
- `cohort-0910-focused-r1` (09:39–09:40UTC):compiler rejected unsupported #173 suppression under Werror; zero fresh product cases. Its22 XML cases were stale. Exits1/0/1; invalid patch withdrawn, not approved here.
- `cohort-0910-focused-r2` (09:52–09:55UTC):160 fresh passes/18suites/no failures/errors/skips;151 tasks(63executed). Exits0/0/0. Core JVM128, core Android observer2, provisioning1, LAN5, KMP1, Android sample12, CLI7, UI4. ABI unchanged; strict core Dokka and15 rendered pages inspected; Android debug assembly passed. Linux iOS KLIB compilation is not Apple linking/runtime.

The0910 focused run passed160 fresh cases. For0911, original focused-r1 remains FAIL(325fresh/324pass/1obsolete-oracle failure); r2 remains FAIL(243fresh/241pass/2sidecar oracle failures; core Android compilation blocked). Narrow corrected r3 passed48fresh/8suites,38core Android+10sidecar, exits0/0/0. Final distinct accepted sidecar scope is179cases, not a sum of copied XML. Static-r1/r2 failures are preserved; static-r3 metadata11fixtures, actual metadata,472links/79active Markdown and whitespace checks passed. Last successful full check remains old clean-d152, not this source. Exact later run source hashes, receipts, exit codes and stop/ownership state are in `checkpoint.json continuedCohort.verificationReceipts`; archived aggregate XML is not automatically fresh execution. Earlier0911 original/focused/static failures remain FAIL. No test was rerun for this administrative packet.

All recorded invocations stopped their task-isolated Gradle daemons with no owned survivors. Outputs were deferred where dependent verification still needed them; that is not an output-deletion claim. The parent owns subsequent safe cleanup/publication. Reuse unchanged successful scopes; no full-build repetition merely for reassurance.

## Remaining boundaries and continuation

10 source-prepared candidates are **not counted** here: #156, #158, #172, #176, #236, #250, #261, #275, #279, #378. Complete their explicitly required affected validation and obtain scoped final acceptance before count advancement. #330/#341/#363 remain pending first affected Apple execution.

#378 is the newly filed read-only Windows launcher cleanup defect: the focused native run passed63 executor controls,15 selected transfer cases and packaging, then cleanup failed. This is not a product failure or complete Windows qualification. The older unexplained cleanup failure remains historical. #379 is the fresh actual PeerRegistry onSubscription correctness defect, separate from #173 fusion; no complete repair is claimed here.

#255 is an approved documentation/characterization correction, not a new cancellation/fanout fix. Preserve its obsolete historical premise as history and reconcile GitHub wording. #274/#284 require owner API-evolution decisions; #287's current-contract defect claim is refuted by its later public correction. All three remain denominator members, not newly approved implementations. #133's repository row approval never means independent interoperability: that campaign remains NOT_STARTED. Physical devices, hostile networks, independent implementations, professional cryptographic review and owner/release prerequisites remain separate.

Continue the next source-prepared cohort without counting unapplied/unapproved work. Complete focused Windows172/176/378, Apple156/158/250/261/275/279 plus prior330/341/363, and candidate publication-artifact/license236 validation. These hosted tasks are pending, not inherently unavailable hardware. Keep274/284 owner decisions and287 current-contract refutation in the denominator, and379 separate from approved173. Finish current whole-repository corroboration, ./gradlew check --console=plain, applicable sample/consumer and release gates. Prefer smallest meaningful scopes and shared cycles; serialize local/hosted resource-heavy runs and preserve every earlier failure and external limit.

GitHub 12:04:11–12:04:20 UTC: 300 issues/193 open,79 PRs/7 open; 379 issue/PR bodies and495 conversation comments freshly captured. Detailed PR reviews/files/commits and timelines retain earlier captures; not a fresh complete-history/remote-execution lease. Earlier detailed full capture and visibility limits remain in the existing ledgers. No issue closure is inferred by this packet. At the final independent local capture,37 focused commits were ahead of origin and not yet pushed. Later source/working edits or publication require a separate binding.
