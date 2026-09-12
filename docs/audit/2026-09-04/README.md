<!-- audit-current:start -->
# Current audit continuation — September 12

The source of truth is now `main`; use the [Mac handoff](../../testing/mac-handoff.md).
The audit date in this directory name identifies the continuing campaign, not a required branch.

**206/234 approved (88.0%); 207 resolved (88.5%); 27 unresolved (11.5%).**
101 new findings; #287 resolves without repair. **NOT_READY; #133 NOT_STARTED.**
Published source `7d21aef` / tree `36bed6d`; administration does not rerun product gates.

[#417](repairs/417.md) and [#420](repairs/420.md) have scoped independent approvals.
Startup5 still fails readiness and both primitive SENDs; #410 is not approved. The current
ordinary Linux graph fails stale locks despite 1,207 host passes. Four partial ABI comparisons
and the separate dry-run graph guard are not complete retained aggregate ABI qualification.
Current-input OSV passed with the unchanged advisory exception: Kotlin 2.4.10 affected,
2.4.20 available but unqualified, expiry 2026-10-31. No vulnerability-free/release claim.

The [root checkpoint](../../../AUDIT_CHECKPOINT.md) is the concise current handoff;
[issues](issues.md), [follow-ups](followups.md) and [checkpoint.json](checkpoint.json)
(`nativeFollowups.postR23Continuation`) bind counts, dated evidence and limits.
Remaining: #409/#410/#413, 21 external rows and owners #120/#274/#284; ordinary supported
host/lock/runtime and current final gates stay required. Private dormant plans are not required
clone inputs. The affected administrative batch passed at 07:05 UTC; the containing audit commit
binds final result/coverage inspection and independent review. No product gate was rerun.
Earlier repeated narratives are retained in the immutable history linked below.
<!-- audit-current:end -->

## Records

- [Checkpoint metadata](checkpoint.json): exact source/event/result bindings and limitations.
- [Current dispositions](issues.md) and [all 234 issue records](issues.json): decisions, dependencies and outcomes.
- [Coverage ledger](coverage.tsv): dated per-path scopes, not blanket current correctness or fresh execution.
- [Continuation order](followups.md): admission, three native/repair rows, remaining gates and deferred campaigns.
- [Hosted evidence](hosted-validation.md) and [repair reports](repairs/): substantive history retained unchanged.
- [Main consolidation](../../maintenance/repository-consolidation-2026-09.md): branch inventory and Git-backed retirement.

## Historical continuity

Duplicate progress narratives were retired from this working file during main consolidation.
The [complete pre-consolidation file](https://github.com/p2pKit/P2pKit/blob/85c72e530d2881f8a7387c665d8331c553e5d26f/docs/audit/2026-09-04/README.md)
remains reachable in main history at `85c72e530d2881f8a7387c665d8331c553e5d26f`.
Its failures, decisions and review scopes are historical evidence, not new executions.
