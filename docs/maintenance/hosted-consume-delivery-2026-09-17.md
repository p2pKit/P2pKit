# Held hosted consume/delivery preparation — 2026-09-17

Refs [#437](https://github.com/p2pKit/P2pKit/issues/437) and
[#424](https://github.com/p2pKit/P2pKit/issues/424). This dated record covers
**source preparation and selected offline controls only**, not native execution,
cache qualification, successful required CI, main delivery or issue closure.
The revision starts from `ea8a80050b175ca96e91e5c8f9eccfd4e073bec5`
(tree `ad3feb5992b9020d90aee6fc7ecc22c1c599ed45`). Its owning commit and final
independent verdict are mapped in those issues; later changes require a delta
review rather than treating this record as current-candidate acceptance.

## Connected source, deliberately not activated

Both literal ordinary activation **HOLD / exit 125** steps remain. Behind them:

```text
original admission -> pre-tool native/service timing + exact consume plan
  -> standalone exact restore -> original-outcome guard
  -> fresh controller adopts original timing/restore records
  -> positive allowlisted-byte seed into a fresh canonical Gradle home
  -> original product, custody, same-home stop and native retirement
  -> Desktop packaging -> one evidence freeze/export -> independent seal
  -> bounded evidence upload -> no-writer package verification
  -> Desktop / Linux-only Android uploads -> final original-outcome guard
```

The Actions-read token exists only in timing preparation, not the product or
delivery. Restore is pinned to
`actions/cache/restore@caa296126883cff596d87d8935842f9db880ef25`, admits only
`S/caches/modules-2/files-2.1`, and has no fallback key, cross-OS archive,
whole-home restore, post save or silent cold fallback. A provider's exact-hit
label is not byte admission, resolver reuse or measured download savings.

FULL remains consume-only. Its 3,600-second job, 2,430-second reserve, eight ABI
roles, additive comparison, three Android ABI checks, eleven supplements,
Central final credential screen and post-screen inventory are not replaced.
Desktop retains its 1,800-second job and 600/825-second product/outer ceilings.
Packaging uses 75 seconds work plus 45 finalization **before** the only freeze.
Delivery ends at the earlier of the original job fence or original controller
terminal RAW observation plus 600 seconds; sample uploads share one 180-second
window. These shared ceilings fail on exhaustion, not promise every maximum
fits. The [cache](../testing/hosted-dependency-cache.md) and
[clock](../testing/hosted-job-clock.md) guides define the full contract.

Other corrected boundaries include keeping Windows native volume/file identity
separate from the packager's Python stat identity, nonblocking no-follow POSIX
sample reads (including swapped FIFOs), and narrowly admitting the two original
sample dotfile receipts. This does not broaden dependency filenames or grant
signing, publication or extra execution authority.

## Independent review findings and regression evidence

The nonimplementing connected reviewer found three predecessor-clock gaps:
crypto started from an old response instead of the original parent phase;
job-time could accept a first child read below its parent start if a later read
recovered; and budget conversion discarded a later native phase high-water.
Each unchanged independent desired-state oracle **failed before** and **passed
after** correction. These are synthetic campaign-source reproductions, not
observed native clock incidents or deployed-main failures.

The helper now retains the initial full immutable reading, accepts a validated
minimum and returns both original responses and the final post-retention
high-water. The controller carries these through acquisition, crypto and close,
preserving the first failure. Acquisition remains **45 seconds** (request 15,
socket 5); preparation's 120-second local window is a different bound. The
HTTP parser's final observation also preserves its reader high-water.

The reviewer inspected the complete connected diff, actual callers, #424/#437
conversations and the exact evidence, then explicitly authorized only the
controller composition expectation change to
`eb10c042667499ee489e499ab89bb8657882e556c5c6d8dc74916feff0245499`.
Other supplier expectations remain unchanged. The two dispatcher mutations
now target their real guarded calls; new mutations cover adoption, packaging,
frozen consume and original-clock edges. Agent review is **not formal GitHub
approval**, and the final tripwire/report review remains separately recorded.

Core/test SHA-256 bindings:

| File under `scripts/` | SHA-256 |
| --- | --- |
| `run-hosted-test-custody.py` | `a42e0a72574955a8a2d74d54e306a846ea4ef602ca8c03017d52926b1574c902` |
| `hosted_full_job_budget.py` | `7e34da911bc05b4edd48bf91104900c513553e9d514021691915d1aa4a339a0a` |
| `tests/hosted-consume-delivery-test.py` | `c9360cf2b521fabf266b09ee2c4d76bb9cf38c119b740c3a656a8e86e9cf2fb1` |
| `tests/hosted-desktop-job-budget-test.py` | `875062e41faf18a82668eed4205a7215ac1e7d2f45d9da02a756a681ef023d21` |

## Actually executed; not merely authored

Mac Python 3.9.6 / Ruby 2.6.10, serial lightweight operations, source manifests,
original logs/exit codes and known process-group retirement. These use tiny
synthetic files and modeled native/provider boundaries, not application builds.

| Actual command | Result and evidence scope |
| --- | --- |
| `python3 -B scripts/tests/hosted-consume-delivery-test.py -v` | **54/54 PASS**, including all 25 integrated consume methods, real original/copy-map readers, coherent replacement refusal, clock/cancellation/failure/retirement and package/delivery models. |
| `python3 -I -B -S scripts/tests/hosted-full-job-budget-test.py -v` | **26/26 PASS**, retained on identical helper/controller inputs. |
| `python3 -I -B -S scripts/tests/hosted-desktop-job-budget-test.py -v` | **22/22 PASS**, including the final literal 45-second acquisition boundary. |
| `python3 -I -B -S scripts/tests/check-hosted-test-composition-test.py -v` | **16/16 PASS**, actual parsed supplier programs and mutations; no supplier execution. |
| `python3 -I -B -S scripts/tests/hosted-controller-import-test.py` | **4/4 PASS**, cold actual import graph with absent Unix APIs and native/network/child operations prohibited. |
| Selected `hosted-test-controller-test.py` models below | **13/13 PASS**, unchanged product/fixture inputs. |
| `ruby scripts/tests/check-hosted-test-workflow-policy-test.rb` | **521 controls PASS**, retained unchanged caller-policy inputs. |
| `ruby scripts/tests/check-sample-app-workflow-policy-test.rb` | **133 controls PASS**, retained unchanged sample-policy inputs. |
| `ruby scripts/check-hosted-test-workflow-policy.rb` and `ruby scripts/check-sample-app-workflow-policy.rb` | Both current source policies **PASS**, not workflow executions. |
| `bash scripts/tests/check-markdown-links.sh`, `bash scripts/check-release-metadata.sh`, `git diff --check` | **PASS**: 506 relative links / 109 active files, unchanged snapshot/RC3 metadata, and whitespace respectively. Link checking is local, not remote URL/anchor acceptance. |

The exact selected controller invocation was:

```sh
python3 -I -B -S scripts/tests/hosted-test-controller-test.py \
  FinalizationModels \
  WholeControllerModels.test_desktop_whole_composition_and_post_return_seal_pass_in_model \
  WholeControllerModels.test_seed_full_model_preserves_primary_supplement_abi_simulator_and_clock_contracts \
  WholeControllerModels.test_full_guard_before_and_after_share_exact_frozen_upload_cap \
  WholeControllerModels.test_full_upload_expired_absolute_cap_cannot_be_renewed_by_after_guard \
  WholeControllerModels.test_full_upload_tampered_cap_refuses_even_with_matching_new_hash -v
```

Its 13 cases include eight finalization cases, not 13 whole-controller runs.
The prior 86-case whole-suite attempt timed out and remains an **incomplete
aggregate**, not a pass. Early fixture/helper failures and the independent
before-fail oracles remain retained, not rewritten as first-attempt successes.

Reuse is limited to unchanged relevant source, fixtures and environment. The
compatible 13-case run preceded only an unused Desktop test-method boundary
correction; it did not import or execute that method. The subsequent complete
Desktop and connected suites cover the final test file. The 25 private consume
method ASTs were preserved exactly during integration. No older ABI/native,
preview or lock-writer result is promoted to new-source whole-gate proof.

Private packets: `connected-delivery-resume-1u5biu6z`,
`connected-caller-registration-jEVFG5oi` and
`review-consume-delivery-final-_hsqynkg`. Raw receipts, path-bearing originals
and payloads remain outside Git. Tiny test fixtures retired; no Gradle ran,
so no Gradle stop was applicable. No unrelated process or shared cache was
stopped/deleted.

## Remaining work and closure boundary

- Separate manual `CACHE_BOOTSTRAP_ONLY` producer/save/probe integration and its
  reviewed complete budget remain unfinished. No save tail is added to FULL.
- Native clock/ownership, genuine exact restoration, positive admitted bytes,
  actual resolver reuse, packaging/retirement/seal/delivery and measured fit
  require genuine admitted hosted evidence; models do not satisfy these gates.
- `.github/test-evidence-recipient.json` is absent. A named routine custodian,
  exact public key, finite 14-day policy, legitimate trusted-original-base
  bootstrap and formal different-account approval remain external prerequisites.
  Candidate source cannot authorize its own recipient.
- Required `complete-gate`, `review`, `scan / osv-scan` and `osv-scanner`, formal
  PR approval, normal merge and preservation are not complete. No held CI,
  local build/download, emulator, merge, closure or publication ran here.
- Accepted preview run `35070982169` retains development APK/MSI/ARM64-DMG/DEB
  as Actions artifacts expiring 30 September, **not main Releases**. Do not
  rebuild unchanged preview artifacts merely for this source preparation.

Physical-phone criteria stay deferred. Production/Maven/Store publication is
not authorized. Historical accounting remains **206/234 repair-approved** and
**207/234 historically resolved**; live issue counts are separate. Audit/release
remain **NOT_READY**. `GHSA-r937-wjx7-w2jp` / `CVE-2026-53914` remains
**EXCEPTED_NOT_FIXED**, Kotlin 2.4.10 affected, expiry 2026-10-31; no scan,
upgrade or exception extension is claimed by this increment.
