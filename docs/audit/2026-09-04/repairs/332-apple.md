# #332 Apple follow-up: withdraw invalid re-resolutions

## Disposition and exact source

- Issue [#332](https://github.com/p2pKit/P2pKit/issues/332), Medium discovery correctness/stale-route availability, **OPEN**.
- Complete four-file Apple correction: **`78ef36142fe79b4ff9672656c6f4c97f049678d0`**; approved/pushed, not merged/released.
- Final tree: **`0f8ab1465d257baac8110e3bd1ecf95859abe93c`**, clean at final verification/review.
- Reproduction baseline: `3134789e0ebe072fd7bd96c2cc08ab0e0ad3ecb0`, tree `c9e4c590e43d8f9d8e7a2825d47d6f8e585487e6`.
- Diff base: administrative reopening commit `bfc6c42198eeb32ba81a302c5ee27595bc0a0a06`.
- Prior JVM/Android approval at `ad1d624499cb4b13d3c86957d9bbbcf0b1132b14` remains valid and branch-available.
- [Baseline investigation](https://github.com/p2pKit/P2pKit/issues/332#issuecomment-5575802714) and
  [verified outcome](https://github.com/p2pKit/P2pKit/issues/332#issuecomment-5576324322).

## Root cause and correction

Apple validation returned without revoking previously admitted state after malformed TXT, semantic/app/security
rejection or service/TXT identity mismatch. Current-generation reconciliation intentionally retained it; core TTL
does not repair transport-managed hints. This is the same cause as #332, not a new duplicate or authentication bypass.

`IosLanDiscoveryTransport.kt:857-942` now routes native inputs through a shared boundary and withdraws using only the
**native Bonjour service identity**, never a victim selected from rejected TXT. Admission and withdrawal recheck
host discovery intent, generation and active-browser ownership under the existing cache lock. The shared lost path
(`:1039-1049`) removes cache, endpoint registry and relay state together. Retired callbacks and never-admitted services
cannot evict another/current owner. Rejection is idempotent, frees only its bounded-cache slot, removes predecessors
retained during refresh grace when currently invalid, and permits fresh valid recovery.

Already retained dial leases/sessions keep their operation ownership; old failures cannot erase a replacement lease.
Manual hints and advertising remain independent. No public API/ABI, dependency, wire schema, authentication, nonce,
queue bound or downgrade change. Changelog/checklist reserve this admission change for **0.8.0+**, not the unchanged
snapshot label. Earlier #229/#356 parser corrections and published RC3 history are not rewritten.

## Verification and regression strength

- Baseline: **14 tests, 10 intended retained-admission assertion failures, 4 passing controls**, zero errors/skips.
  The behavior-preserving extraction was independently reconstructed against exact baseline bytes. Failures stop at
  the first assertion; later helper steps/both profile iterations are not claimed as baseline executions.
- Final transition class: **20 passing methods**, each exercising both profiles. Native endpoint/TXT inputs reach
  production validation/cache/registry/relay and browser-generation gates. Coverage includes all rejection categories,
  unrelated/never-admitted peers, valid Unicode/U+FFFD/aliases, late subscriptions, recovery, repeated rejection,
  retired/current generations, rebind gaps, capacity, manual hints, stop/restart and controlled pending-dial ownership.
- Focused LAN check: **480 passes**, zero failures/errors, one unchanged manual skip; 70 XMLs, 52 executed tasks.
  Its complete dirty-worktree patch byte-equals the final committed diff, SHA-256
  `5e34303230031538a53b92edd7a6e7f6cc462a3ecab2de5b622ccc80176cc78e`.
- Eight mutation controls detect missing malformed/schema/mismatch withdrawal, TXT-selected ownership, absent
  generation/browser fences, and omitted endpoint/relay withdrawal. Each produces one intended assertion failure,
  zero errors/skips; exact source is restored. These are expected-red controls, not additional passing Gradle runs.

```bash
./gradlew check :p2p-sample-android:assembleDebug \
  --rerun-tasks --no-build-cache --no-configuration-cache \
  --dependency-verification strict \
  -Pkotlin.compiler.execution.strategy=in-process \
  '-Dorg.gradle.jvmargs=-Xmx2048m -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8' \
  --console=plain --max-workers=2 --no-parallel
```

Final clean result at `78ef361`: **2,387 passes, zero failures/errors, one unchanged manual LAN capture skip;
290 XMLs, 246 executed tasks**. JVM, Android host and Kotlin/Native arm64 simulator tests ran; actual ABI/lint guards
and Android debug assembly pass. Fourteen static/policy gates pass: layout, OSV lock coverage, links, release metadata,
whitespace, scoped source style, dependency verification, toolchain/release policies, wrapper and regressions, actual
Android ABI graph, platform-test policy and runner regressions. Scoped style is not a full ktlint run. This actual
command did not include `--no-configure-on-demand`; earlier #356 commands must not be substituted for its receipt.

## Independent review and cleanup

Fresh `/root/review_332_apple_r1`: **APPROVE**, no actionable findings. Independently inspected complete diff, native
lifetimes, surrounding platform/core callers, lifecycle/security/concurrency/ownership/compatibility and regressions;
verified **1,992 sealed entries, all 370 retained XMLs (290 final), and 28 finalized cleanup receipts**.
Review SHA-256: `2b29c8a6332dd794469c77a39e3b834eb90e462d4176181d9115d4c892c64445`.
Manifest SHA-256: `120d92c9c28d6c7c90b8117483cf06f2cf7ef975abe04a70668373228b6fde8e`.

Every invocation, including failures and mutation controls, finalized wrapper stop, owned-worker retirement, report
preservation and disposable-output removal. The full build removed ten output roots and its remaining owned JDK21
worker. No cleanup failures/final owned survivors. Reviewer ran no builds/workers or tracked edits. Protected guides,
stashes, user sources and shared caches are preserved. Never recursively delete every directory named `build`:
`buildSrc/src/main/java/dev/p2pkit/build` is source. Later administrative checks have separate receipts, not this seal.

## Limits and continuation

Tests inject native endpoint/TXT objects **after browse-result copying**; they do not produce actual NWBrowser results
or prove physical multicast delivery. Dial tests use real **unstarted** native connections with controlled states;
they establish ownership, not TCP establishment or an authenticated end-to-end session. Existing shared concurrency
tests and deterministic interleavings are not hostile-network race evidence.

#23/#43 physical campaigns, #120 capacity/fairness architecture, older OS/Intel runtime, Swift XCTest, ART/OEM,
independent interoperability and professional cryptographic review remain pending. #133 external interoperability
is **NOT_STARTED**; its publication/isolated-consumer evidence remains bound to `7127616`, not rerun here. Final
release/consumer/Swift/XCFramework gates and whole-repository corroboration remain. Overall **NOT READY**.

Raw evidence stays private; hashes are not downloadable-artifact claims. The clone includes source, commands, safe
summaries and public outcomes. This completes the reopened row, restoring **61/171** reviewed repository repairs,
not 62 or an issue closure. Read planned next issue #130 completely before repair. No `main`, tag or release change.
