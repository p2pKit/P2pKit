# RPC implementation checkpoint — 2026-09-27

## Scope and baseline

Source implementation of the approved [Optional LAN RPC plan](../../RPC_MODULE_PLAN.md)
is present. **It has not been compiled, runtime-tested, security-qualified or
capacity-qualified.** This is a workstream checkpoint, not release evidence or
approval to merge. The plan is preserved as the original planning snapshot.

- Isolated clone: `/root/projects/p2pkit-feature-prep-20260927-yiDjCB`.
- Feature branch: `work/rpc-lan-20260927-054728-8b1b11da`.
- Exact base and freshly fetched `origin/main`:
  `3bc76f956f8f47447b51a62474fc878b9c43173c` (no advancement).
- `AGENTS.md` and `CLAUDE.md` were read completely and remain unchanged.
- No Foundation/campaign source, keys, worktrees or private evidence were used.
  Release Foundation remains **NOT_READY**; existing HOLDs and external gates
  remain intact. Future integration must come from main normally.

## Source delivered

1. Additive core/LAN prerequisites: opt-in authenticated admission/quarantine,
   shared payload leases, binary-only restrictions, retained session failure
   and generation observations, generation-bound sending, bounded reconnect,
   explicit organization-private endpoint/interface policy, dial-only clients
   and separate restricted JVM/Android I/O dispatch views. Null-profile P2P
   defaults are retained in source; compatibility still requires execution.
2. Optional `p2p-rpc`: explicit typed procedures, bounded JSON/wire protocol,
   HELLO/READY, host-owned concurrent execution, deadlines, cancellation,
   correlation, stable-ID recovery, deduplication/tombstones and retained
   outcomes. Ambiguous unsafe calls are not silently re-executed.
3. Pairing/trust and notifications: short-lived single-use invitations,
   administrator approval, application-local durable trust, fresh authorized
   connections, live revocation, bounded best-effort updates and sanitized
   connection/diagnostic observations.
4. Deterministic regression source, an inventory example/shared mobile façade,
   an explicitly invoked JVM capacity driver, developer documentation and
   applicable repository/ABI/dependency/platform/publication inventories.
   No permissive transport, identity store or lab provider is bundled.

The [qualification guide](qualification.md) maps the added test suites and the
required platform/security experiments. The [sample](../../samples/p2p-sample-rpc/README.md)
describes the local integration still needed to run the driver. Capacity
requirements remain **128 authenticated clients, 1,280 calls/second, 1 KiB
request/reply bodies, 30 minutes on each actual JVM/Android/iOS host**, plus
physical interoperability and the separate 1 MiB experiment. None has run.

## Offline checks actually run

These commands inspect source or execute synthetic Python/Ruby/shell fixtures,
not Kotlin, Java, Gradle, Xcode or an application. Results include the preceding
continuation of this same isolated workstream.

| Command/check | Observed result |
| --- | --- |
| `git fetch --no-tags origin +refs/heads/main:refs/remotes/origin/main` and ancestry inspection | Main unchanged at the exact base above. |
| `git diff --check` | Passed. |
| Added Kotlin-line scan | Passed 120-column and no-wildcard checks; not compilation or ktlint. |
| Syntax-only inspection of changed scripts/configuration | Six Python ASTs, six `bash -n`, three `ruby -c`, changed TOML and five workflow YAML files passed. |
| `python3 scripts/tests/check-rpc-module-policy-test.py` | Passed, including seven negative controls. |
| `bash scripts/tests/check-repository-layout.sh` | Passed for 12 projects, including 15 Android-setup negative controls and RPC inventory checks. |
| `bash scripts/tests/check-markdown-links.sh` | Passed active-document relative-link checks. |
| `bash scripts/check-release-metadata.sh` | Passed; snapshot/published versions unchanged. |
| `python3 scripts/tests/check-release-metadata-test.py` | 11 tests passed. |
| `ruby scripts/tests/check-jvm-cross-host-policy-test.rb` | 34 checks passed. |
| `ruby scripts/tests/check-platform-test-policy-test.rb` | 31 checks passed. |
| `ruby scripts/tests/check-publication-sbom-policy-test.rb` | Current policy, 27 negative mutations and seven fake-wrapper/real-validator cases passed. |
| `python3 scripts/tests/check-sbom-test.py` | 23 tests passed, including omission of RPC from both synthetic graphs. |
| `python3 scripts/tests/check-publish-license-test.py` | 11 license and 67 embedded-JmDNS archive/metadata fixtures passed; no real publication/build. |

### Failures and intentionally missing inputs

- `python3 scripts/tests/run-platform-tests-test.py`: **21/23 passed**.
  `test_surviving_group_is_drained_even_when_leader_already_exited` and
  `test_term_resistant_worker_is_killed_after_leader_exits_on_term` failed.
  Inspection of only these owned fixture processes found dead, unreaped orphan
  zombies under PID 1, not running workers. AST comparison found both the
  runner's `terminate_process` and the entire `OwnedProcessGroupTest` unchanged
  from main. Main was not separately executed to establish a runtime baseline;
  no assertions/timeouts were relaxed and no unrelated process was touched.
- `bash scripts/check-android-abi-guard.sh --static-only`: failed on missing
  genuine `library/p2p-rpc/api/android/p2p-rpc.api`.
- `bash scripts/tests/check-osv-lockfile-coverage.sh`: failed because the
  expanded workflow has 12 lock arguments but only 10 existing nonempty lock
  inputs. Genuine RPC/sample locks are pending, not excluded from the gate.
- New Kotlin/Android ABI dumps, dependency locks and streaming-JSON verification
  checksums have **not** been fabricated or copied. Their generation requires
  separately authorized toolchain/dependency execution.

Fresh source inspection still finds stale `org.jmdns:jmdns:3.6.3` entries in
main's existing lockfiles. This is the previously reported **separate baseline
issue**, not an RPC regression or a new CI finding. No lock repair was generated
or imported from unfinished Foundation work.

## Authorization still required

No local Java/Gradle/Xcode/application build, SDK/dependency download, hosted
execution, physical-device experiment or capacity run has been started. No
merge, publication, release tag or repository/environment change is authorized.

The next validation needs explicit permission for genuine dependency/ABI input
generation and JVM/Android compilation, tests and compatibility checks in this
isolated workspace. Apple Cinterop/platform execution needs an authorized Apple
host; actual-host capacity, network-path and physical interoperability evidence
need separately coordinated lab runs. See the exact checks and evidence rules
in [qualification](qualification.md). A failed security/capacity contract is a
stop-and-review decision, never permission to weaken it.
