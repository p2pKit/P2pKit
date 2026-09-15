# Sample build blockers: researched GitHub route — 15 September 2026

**Dated research and execution checkpoint, not a fix, workflow implementation,
successful build or permission to retry.** The owner requested a researched
GitHub-side solution instead of further local writer attempts. No local build,
dependency acquisition, emulator, CI dispatch, merge or release was started for
this research. Private evidence remains outside Git and public Actions artifacts.

**Later continuation:** the owner-approved encrypted
[hosted lock-candidate implementation](hosted-lock-candidate-2026-09-15.md) is
recorded separately. Permission/proposal statements below describe this earlier
research checkpoint, not the later implementation or a successful hosted run.

## Exact source and remaining defects

At the 17:11 UTC fetch, main remained
`3bc76f956f8f47447b51a62474fc878b9c43173c`, tree
`2a1105fde1d1ac299448489501e29d7a0d4a407a`.
The clean integration branch `work/nonphysical-integration-20260915-022112`
was at `614e5344b6161ff4adeb5ec27a2bba267326e815`, tree
`dd1b520bd2501618897177b78b9c82d8c68ea13d`.
This document's containing commit changes documentation only.

- **Windows setup:** [614e534](https://github.com/p2pKit/P2pKit/commit/614e5344b6161ff4adeb5ec27a2bba267326e815)
  replaces Git Bash's failing `mkdir -m700` with native Python directory creation,
  preserving exclusive allocation and existing-path/link rejection. Its scoped
  source/offline review is complete; genuine Windows execution is still missing.
  Do not implement that correction again. [#439](https://github.com/p2pKit/P2pKit/issues/439) stays open.
- **Dependency locks:** the [LAN build](../../library/p2p-transport-lan/build.gradle.kts)
  already uses the patched, locally produced JmDNS JAR, but six project locks
  still require `org.jmdns:jmdns:3.6.3`: LAN, Desktop provisioning, Android sample,
  Desktop UI, Desktop CLI and shared KMP sample. Strict resolution correctly
  rejects that mismatch. This is not evidence of an unavailable Maven download.
  All twelve locks and verification metadata remain unchanged.
- **Sample delivery:** [run 34978847218](https://github.com/p2pKit/P2pKit/actions/runs/34978847218)
  used `1bf4fc81d3e0981278244e959775c6e38eef3163`, not the later Windows fix.
  Linux/macOS hit stale locks, Windows failed setup, and the overall run was
  cancelled with zero artifacts. No corrected matrix was rerun.

## Supported solution, not a workaround

[Gradle's dependency-locking documentation](https://docs.gradle.org/current/userguide/dependency_locking.html)
explains that `--write-locks` updates the configurations actually resolved by the
requested tasks; a root `dependencies` invocation is not a whole multi-project
refresh. It also explains that a failed build does not persist the lock state.
That is consistent with the retained failed writers and unchanged locks here.

Use the complete maintained
[dependency-update procedure](../../scripts/prepare-dependency-update.sh), with
an independently accepted exact base and owned execution/finalization:

```sh
# Future command after the prerequisites below; NOT executed by this research.
scripts/prepare-dependency-update.sh <reviewed-full-source-SHA>
```

Its unchanged operation is `resolveAndLockAll --write-locks
--write-verification-metadata sha256 --no-configure-on-demand`, followed by
metadata validation, strict postchecks and the provenance classifier/curator.
The [root graph](../../build.gradle.kts) includes every applicable subproject
check and Dokka task plus aggregate SBOM generation. Do not edit locks manually,
restore the obsolete dependency, use a partial task graph or weaken verification.
[Gradle's verification documentation](https://docs.gradle.org/current/userguide/dependency_verification.html)
also distinguishes generated checksums from established artifact authenticity.
Successful generation still needs independent complete-candidate review.

## Reachable GitHub path and its real prerequisites

[GitHub documents](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
that a manually dispatched workflow must exist on the default branch; `--ref`
selects another branch revision. Therefore the smallest reachable candidate is
a separately reviewed, isolated `dependency-lock-candidate` operation in the
existing [Desktop workflow](../../.github/workflows/desktop-cross-host.yml).
**That operation and its mutable controller are proposed, not implemented.**
A new standalone workflow cannot simply be dispatched from this unmerged branch.

Do not retarget the retired `audit-lock-refresh.yml`: it uses the retired branch
contract, routes mutation through the now-immutable leaf, omits the complete
current provenance procedure, and has obsolete raw-evidence upload/cleanup rules.

The [official ARM Mac image inventory](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md),
observed image `20260907.0351.1`, lists Xcode 26.5 (`17F42`), SDKs 36 and 37.0,
and an iOS 26.5 iPhone 17 simulator. It defaults to **Xcode 26.6**, so explicit
26.5 selection remains necessary. This inventory is not admission of an actual
runner's native process ownership, capacity, simulator or multicast.

Before a hosted writer can start:

1. **Approve private evidence delivery.** Live metadata showed a public repository,
   zero repository Actions secrets/variables and zero registered self-hosted
   runners. No configured recipient/private retrieval route was found. Narrow
   permission was requested for a one-use owner-retained private key and encrypted
   Actions evidence. It has not been granted in this checkpoint. Do not print or
   upload raw test logs/XML. An absent recipient must stop before downloads/builds.
2. **Review the mutable adapter and credential boundary.** Use the existing native
   ownership implementation and [writer custody contract](../testing/local.md#subprocess-transcript-custody-on-failure),
   including actual reserved product/stop IDs, original results, same-home stop,
   known drains and unconditional custody collection. Do not manufacture an
   immutable receipt for changed locks. The earlier hosted `SSH_AUTH_SOCK`
   rejection remains unresolved; do not unset hooks or call that host admitted.
3. **Preserve workflow isolation and admission.** Add the operation to the closed
   queue/input policies without changing ordinary sample tasks, witness/capacity
   jobs, required checks or publisher authority. Bind exact source/tree/base and
   real run identity; admit the actual pinned tools, resources and simulator
   before the expensive full writer. No speculative dispatch is authorized here.
4. **Accept only a complete result.** Retain all twelve before/after locks,
   metadata, original logs/results, generated ABI/producer/SBOM evidence and
   #424's current CLI 9/diagnostics 23 methods with six original exports. Review
   the actual candidate and provenance before committing generated files. Then
   run applicable scan/submission and current sample/native verification.

The existing [sample delivery route](sample-app-workflows-2026-09-15.md) still
requires genuine builds, required CI, independent formal PR approval and normal
main merge before the main-bound development prerelease publisher can deliver
apps. There is no shortcut from a successful lock write to a release.

## Latest local outcome: no Gradle launch

The later controller attempt ran **16:48:16.588006Z–16:48:34.260238Z**, exit 125.
Its first NORMAL admission passed and it copied **1,740,504,707 bytes locally**
from qualified retained inputs. Its second admission observed WARN and refused
to start the writer. `writer=null`, `stop=null`: no Gradle/product task/test ran
and no Gradle stop was necessary. All six fast samples had the same swap counter;
incremental swapout was zero. No cause of the pressure transition is established.

Independent result review accepted
`ACCEPT_FAILED_PRE_WRITER_RESULT_WITH_SUPPLEMENTAL_NO_PRODUCT_RETIREMENT_FINDING`:
all eighteen recorded helper commands retired, the selected simulator remained
Shutdown, and leases were released. The original custody `HOLD/UNKNOWN` and
`retirementHold=true` remain unchanged; the supplemental no-product finding does
not rewrite them or authorize cleanup. The entire state/dependency homes remain
retained. Review-report SHA-256:
`f61d31a29ced3f56238807ed27f0b92096fba027c69f3f5b683caed01d865d03`.

This is separate from the earlier actual full-writer failure documented on
[#425](https://github.com/p2pKit/P2pKit/issues/425#issuecomment-5684182643).
Do not conflate local input copying with internet downloads or either failure
with a compiler defect. Do not restart another local writer from these records.

Private packet handles: `hosted-lock-route-research-p3zp7eup`,
`hosted-lock-route-issues-7gemxsbs`, and
`writer-quiet-terminal-independent-review-uzsht2es`. The four official documents
totalled **768,106 downloaded bytes**; no SDK or dependency was downloaded by
this research. Complete #424/#425/#437/#439 conversations were refreshed with
pagination. Their issues remain open; no completion or closure credit is added.
Historical accounting remains **206/234 repair approvals**, separately from the
fresh **61 open GitHub issues**. Whole audit/release remains **NOT_READY**.
