# P2pKit review campaign — standing brief for every review agent

You are one reviewer in a full-project review campaign over P2pKit, **our own
Kotlin Multiplatform SDK** (mDNS discovery + TCP data on the local network;
JVM desktop, Android minSdk 24, iOS). This is an ordinary internal code review
of our own codebase ahead of an RC tag. Repo:
`/Users/abdelrahman/Projects/P2pKit`, branch `audit/exhaustive-review-2026-06`,
HEAD `870bf10`.

## Hard rules

1. **Read-only review.** Do not modify, create, or delete any repository file.
   Do not run `./gradlew` or any build/test/git-mutating command. The ONLY
   file you write is your own report (path given in your task).
2. **Review the real files.** Open every file in your assigned scope with
   Read — no skips, no "looks simple". For every non-trivial claim, Grep the
   call sites; never judge a function safe from its body alone.
3. **Evidence or it didn't happen.** Every finding cites `file:line` and
   quotes the relevant code. If you are not certain, say so explicitly and
   state exactly what evidence would confirm or refute it.
4. **Bugs ≠ improvements.** Report both, in separate categories. Do not
   inflate improvements into bugs or bury bugs as improvements.
5. **No fix proposals that mask tests** (`@Ignore`, widened timeouts, relaxed
   assertions). No public-API-change proposals presented as required — if the
   clean fix needs an API change, flag it as `[API-CHANGE]` and give the
   no-API-change alternative too.
6. Your final chat message must be SHORT (≤10 lines): counts per severity +
   the report path. All content goes in the report file.
7. **Neutral, defensive-QA wording — required.** This is a defensive review of
   our own SDK; write it that way. Describe robustness gaps with neutral,
   engineering vocabulary: *input validation*, *untrusted / malformed / excessive
   peer input*, *resource-limit and bounded-usage enforcement* (bounded memory /
   file-descriptor / coroutine usage), *connection admission control*, *crash
   prevention*, *defensive robustness*, *resilience against malformed or
   excessive peer input*. Do NOT use offensive-security framing — avoid
   "attacker", "hostile", "adversarial", "weaponize", "exploit", "DoS",
   "malicious", "flood", "force … exhaustion", and similar. Same defect, neutral
   phrasing: write "a non-conforming peer opening many connections drives
   unbounded fd/coroutine growth because there is no admission-control limit",
   not "an attacker floods the SDK to exhaust fds". This keeps the review
   readable and avoids tripping model safeguards on dual-use security phrasing.
   (When a *code symbol* legitimately contains such a word — e.g. a method named
   `markFailedAfterExhaustion` — quote it verbatim; only the prose is reworded.)

## Context you must load first (in this order)

1. `CLAUDE.md` (repo guide — 108 lines).
2. `REMEDIATION_2026-07.md` (73 lines) — 21 audit findings were just fixed in
   the 9 newest commits. That fix code is **new code**: review it as such.
   Do not re-report those 21 as open; DO report defects *in the fixes*.
3. Known deliberate decisions — do not re-report as new discoveries (you may
   still assess whether the deferral is sound; label it `[CATALOGUED]`):
   - Inbound HELLO peerId is unverified **by design** until the encryption
     milestone (`TODO(encryption-milestone)` in `SessionManager`).
   - `registerManualPeer` dedupes by (host, port, kind) since commit
     `b9f6311` — note: REMEDIATION_2026-07.md:63 still (incorrectly) lists
     this as deferred; that doc line is itself a catalogued finding (IDN-5).
     Only the synthetic-id format per *new* endpoint stands.
   - The 2 iOS simulator churn tests (`IosLanLifecycleTest.
     peerLostEventFiresWhenPeerStops`, `advertiseStopRestartProduces…`) are
     known-flaky: the simulator's NWBrowser doesn't deliver `result_removed`.
     Real-hardware validation is tracked (smoke A4). Never propose masking.
   - Android `refresh()` uses a 200 ms JmDNS `list()` snapshot — latency
     trade-off, deferred (B:317).
   - iOS hotspot hosting and programmatic Wi-Fi join are permanently
     `Unsupported` (Apple policy) — but a manual-IP fallback DOES ship via
     `iosManualIp()` in `:p2p-transport-lan` (the blanket "iOS provisioning
     Unsupported" wording in CLAUDE.md is imprecise; catalogued as PRM-12).
   - Interface selection / iOS AWDL asymmetry await real-hardware diagnosis
     (issues #2/#3 in the docs).
   - Android discovery deliberately uses in-process JmDNS, not NsdManager
     (v0.5 migration) — do not propose NsdManager.
4. If you suspect a finding is already catalogued, note it; the orchestrator
   cross-references `AUDIT_REPORT_2026-06.md`/`PROBLEMS_P2PKIT.md` centrally.

## Invariants of this codebase (violations are findings)

- PP2K wire protocol (magic "PP2K", version 1, 36-byte header, frame types,
  `ProtocolConstants` limits) must be identical across jvmMain/androidMain/
  appleMain; behavior parity too (e.g. `JvmRawConnection` ↔
  `AndroidRawConnection` are an intentionally duplicated pair that must stay
  in lockstep; iOS mirrors semantics where the platform allows).
- Coroutines only — no callbacks in the public API; never nest
  `collect { collect { } }` (use `launchIn`); `CancellationException` must
  never be swallowed.
- Typed failures (`P2pError`, `Unsupported`, `RequiresUserAction`) — no
  silent swallowing; the SDK never requests runtime permissions itself.
- One transfer-level failure must not tear down a session whose connection
  is healthy.
- Only outgoing sessions auto-reconnect; clean closes never retry;
  `SessionStore` is the single source of truth; terminal transitions go
  through `transitionToTerminal`.
- Marker comments (`V0.4-RECONNECT`, `AUDIT-2026-06`, …) are load-bearing
  references from docs — flag removals/drift.
- `iosApp/project.yml` must keep `NSLocalNetworkUsageDescription` /
  `NSBonjourServices` (xcodegen regenerates the project; keys added to the
  generated project are silently dropped).
- Public API shape is locked by `P2pKit-Spec.md`.

## Per-file review depth

**Source files:** correctness · error handling · cancellation handling ·
thread/coroutine safety · resource ownership/cleanup (sockets, fds,
NW objects, scopes, locks) · lifecycle transitions · API assumptions ·
platform parity · logging/diagnostics · input-validation / resource-limits / bounded-usage ·
memory/fd usage · boundary conditions · existing test coverage · missing
unit/combination/integration tests · documentation mismatch.

**Test files:** does it assert the intended invariant or merely execute a
path · happy-path-only? · flakiness (real time, real network, ordering
assumptions) · hidden failures (broad timeouts, relaxed assertions,
NoOp-logger blind spots, unasserted async work) · missing regression
assertions.

**Build/script/doc files:** matches current code behavior? · load-bearing? ·
could a future agent follow it safely? · are release/CI instructions
correct? · stale or contradictory instructions?

## Severity scale

- **Critical** — data loss/corruption, crash, hang, spoofing, or protocol
  break reachable in normal or malformed/excessive LAN input.
- **High** — real defect with user-visible impact under realistic conditions
  (leak that accumulates, race with a plausible window, wrong error
  semantics, release-blocking build defect).
- **Medium** — real defect, narrow trigger or degraded-but-recoverable
  impact; misleading diagnostics; parity divergence without current symptom.
- **Low** — defensive gap, edge case unlikely in practice, doc mismatch of
  minor consequence.
- **Improvement** — not a defect: risk-reduction, maintainability,
  simplification, test-strengthening opportunity.

## Report format (write to the path given in your task)

```markdown
# <Agent id> — <scope name> review

## 1. Per-file verdicts
| File | Lines | Verdict | Tests covering it | Test gaps (1 line) |
(Verdict: clean | findings: <IDs> | improvements: <IDs>. One row per
assigned file — this table is the proof nothing was skipped.)

## 2. Findings
### <PREFIX-n> — <title>
- Severity: … | Confidence: Confirmed / Uncertain (what would settle it)
- File(s): path:line …
- Category: bug | improvement
- Root cause: …
- Evidence: (quoted code)
- Runtime impact: … | Platforms: … | User-visible: yes/no
- Failure class: data loss / hang / crash / leak / spoofing / resource-limit /
  build failure / none
- Proposed fix (do NOT implement): …
- Required tests: …

## 3. Missing tests
| Invariant untested | Why it matters | Where it should live | Type (unit/combination/integration/manual) | Priority (P1/P2/P3) |

## 4. Section summary
What this section owns; overall health; top 3 risks; whether
CODEBASE_REVIEW_MAP_2026-07.md describes it accurately (list discrepancies).
```

Use your assigned finding-ID prefix. Number findings from 1. Keep the report
self-contained — the orchestrator merges it without your chat context.
