# Ordinary hosted caller preparation — 2026-09-17

Refs [#424](https://github.com/p2pKit/P2pKit/issues/424) and
[#437](https://github.com/p2pKit/P2pKit/issues/437).
This is a dated **source-preparation** record, not a hosted run, cache
qualification, required-check pass, issue closure, or release approval.
The implementation starts from `59b91c738da2801cc4d5008acd54dfd728a2e18d`
(tree `b1926553481692da6f6365fad04e3a5488449e06`).

## Prepared path and intentional activation hold

The ordinary Desktop verification job and CI FULL now express the existing
custody controller's real caller contract:

```text
literal activation HOLD
  -> original-event/source/recipient admission
  -> separate dependency staging
  -> tool prerequisites
  -> controller run --seed-dependencies
  -> separate validate-public
  -> exact encrypted archive + safe public manifest upload
  -> terminal check of actual step outcomes and sealed profile result
```

Both activation steps emit
`ORDINARY_TEST_ACTIVATION=HOLD; QUALIFIED_DEPENDENCY_CACHE_REQUIRED` and exit 125
**before ordinary toolchain/SDK/cache/stage/product acquisition**. The terminal
check remains failure-aware; a missing, skipped, failed or provisional outcome
cannot turn that HOLD into a passing ordinary gate. No cache provider or
population/save mechanism is introduced. Merely adding a recipient policy does
not lift the activation hold. This hold is job-local: the independent JVM
prerequisite jobs remain unchanged. This preparation dispatches no workflow.

FULL keeps the existing primary `check` selector, all eight generated ABI roles,
the aggregate additive Klib comparison, three custom Android ABI comparisons,
and eleven supplements. These remain in the unchanged
[controller](../../scripts/run-hosted-test-custody.py),
[primary ABI supplier](../../scripts/hosted_primary_abi.py), and
[FULL supplement supplier](../../scripts/hosted_full_supplements.py); they are
not replaced by policy greps, copied baselines, or the root-only `:check` task.
Swift results, XCFramework sidecars, SBOM and other private evidence stay inside
that custody path instead of direct raw workflow uploads.

Only FULL grants job-local `contents: read` plus `actions: read`. Its Actions
read token is present only on the controller run step, never admission, seal,
upload guards, or products. FULL calls the existing upload guards before and
after the fixed three-minute artifact upload. Desktop does not call that
FULL-only API. Both upload exactly `evidence.tar.gz.gpg` and `manifest.json`,
with 14-day retention, no hidden files, no overwrite, and missing files treated
as failure. Packaging may inspect successful ordinary Desktop products only
after its complete terminal guard; no additional ordinary Gradle stop or product
writer is appended after sealing.

The explicit `sample-apps` preview retains its build-only task body, owned home,
stop, packaging and product-upload contracts. Its direct build/cache/stop are
now explicitly preview-only. It is not runtime acceptance for ordinary Desktop.
The JVM prerequisite jobs, six dispatch inputs, queue identities, special
Windows/Mac/lock operations, and separate `iphoneos-product` job are preserved.
Intel and standalone release/Maven workflow paths are unchanged.

## Offline verification actually executed

The commands below ran serially on this source preparation using macOS
Ruby 2.6.10 and Python 3.9.6. Each command had a private bounded supervisor,
retained source map/log/exit code, and verified process-group retirement.
No local Gradle, Java, Xcode product, emulator, SDK/dependency download, real GPG
test, hosted dispatch, publication, merge or closure was performed.

| Command | Observed result and boundary |
| --- | --- |
| `ruby scripts/tests/check-hosted-test-workflow-policy-test.rb` | PASS, 209 policy/synthetic-shell controls, including execution of the literal HOLD and actual terminal shell against success/failure/cancelled/skipped/missing outcomes; no GitHub runner execution. |
| `python3 -I -B -S scripts/tests/check-hosted-test-composition-test.py` | PASS, 15 AST-only tests with adverse subcases against actual controller/driver/ABI/supplement/retention edges; no supplier imports or execution. |
| `ruby scripts/tests/check-sample-app-workflow-policy-test.rb` | PASS, 81 source-policy controls, including preserved preview isolation and ordinary packaging guards. |
| `ruby scripts/tests/check-platform-test-policy-test.rb` | PASS, 32 caller-policy controls; preserved Intel/standalone release rules. |
| `bash scripts/check-android-abi-guard.sh --static-only` | PASS, source policy only; no generated ABI or Gradle graph proof. |
| `bash scripts/tests/check-android-abi-guard-policy-test.sh` | PASS, fixture mutations of the real composed Android ABI roster/graph and direct standalone release graph. |
| `ruby scripts/tests/check-heavy-job-queue-policy-test.rb` | PASS, 313 controls. |
| `ruby scripts/tests/check-windows-directory-control-policy-test.rb` | PASS, 113 controls. |
| `ruby scripts/tests/check-hosted-lock-candidate-policy-test.rb` | PASS, 326 controls. |
| `ruby scripts/tests/check-mac-host-admission-policy-test.rb` | PASS, 63 controls; no native admission. |
| `ruby scripts/tests/check-hosted-iphoneos-product-policy-test.rb` | PASS, 81 controls; no product build. |
| `ruby scripts/tests/check-ci-scope-policy-test.rb` | PASS, 21 controls. |
| `ruby scripts/tests/check-jvm-cross-host-policy-test.rb` | PASS, 32 controls; no JVM test execution. |
| `ruby scripts/tests/check-workflow-checkout-policy-test.rb` and `ruby scripts/check-workflow-checkout-policy.rb` | PASS, 19 fixture controls plus all workflow checkout credential checks. |
| `bash scripts/tests/check-kotlin-toolchain-policy-test.sh` | PASS, static consistency and local fixture checks only; not dependency/native qualification. |
| `bash scripts/tests/check-repository-layout.sh` | PASS, ten project mappings and 15 Android setup negative controls. |
| `git diff --check` | PASS. |

`actionlint` 1.7.12 was also executed with shellcheck/pyflakes disabled. It exits
1 on the eight preserved `queue: max` keys in these two workflows; this is **not
an actionlint pass**. The separate queue policy covers the documented queue
schema. No unsupported key was removed to manufacture a pass.

The ordinary caller and AST mutation controls are now required by the existing
CI/release entrypoints. Assertions formerly looking for direct FULL YAML build
or upload strings now check the exact composed caller and parsed supplier
programs. Independent structural expectations are bound to unchanged approved
base source, not derived from the workflow under test. Supplier changes require
their own review and explicit expectation updates. The whole release-workflow
hook and release gate were **not executed** here: they include real native/GPG
fixtures and product work outside this offline slice.

## Remaining acceptance, not waived

- Independently review this final source/diff and all affected caller policies.
- Qualify a supported, bounded restore/save provider and population path, safe
  native staging/extraction, exclusion of affected build-cache state, original
  source/provenance, and real native resolver reuse. Existing isolated seed
  preparation is not a cache hit or demonstrated download saving. This remains
  engineering/qualification work, not an invented owner policy decision.
- Resolve the trusted original-base recipient/bootstrap and routine custodian
  policy through the existing approval process. Do not invent a key or move
  candidate policy into the trust boundary.
- Prove the actual admitted native hosts, successful controller/ABI/supplement
  results, sealed encrypted retention, private evidence inspection, and required
  CI/formal PR review against one exact candidate before any merge or closure.
- Preserve the original Desktop 30-minute and FULL 60-minute job limits. FULL's
  existing 2,430-second reserve leaves at most 1,170 seconds for productive work
  **before setup charges**; no measured fit is claimed and no deadline was
  widened. A fast-failing held source path is not a successful full gate.

The older preview run `35070982169` at `8e4ca838` produced downloadable Actions
artifacts in its own build-only scope. This work neither rebuilds nor converts
those artifacts into current ordinary runtime, merged-main, or Releases evidence.
All existing physical-phone, independent-interoperability, publication, and
other same-issue acceptance holds remain distinct.
