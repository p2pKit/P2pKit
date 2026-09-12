# July 2026 review-campaign archive

This directory preserves the historical snapshot of the formerly user-owned
`.review-2026-07/` workspace. It was reviewed and archived during the final
2026-08 consolidation; it is not current guidance or a current test result.
The sole working-tree retirement on 2026-09-12 is the rejected provisional draft
linked below; accepted findings, method notes and original test evidence remain.

## Contents and authority

- `BRIEF.md`, `RESUME.md`, and `IMPLEMENTATION_NOTES.md` preserve the campaign
  method, continuation history, and implementation/test notes.
- `reports/` contains the 18 subsystem review reports A01–A16 (including the
  split A13 and A14 reports).
- `impl-logs/` contains original generated logs and test-result snapshots. They
  are retained because they are unique historical evidence, not because build
  outputs normally belong in documentation.
- [The rejected provisional draft](https://github.com/p2pKit/P2pKit/blob/85c72e530d2881f8a7387c665d8331c553e5d26f/docs/archive/remediation/2026-07/review-campaign/CODEBASE_FINDINGS_2026-07.OPUS-PROVISIONAL.md)
  is retained in reachable Git history, not this working tree. The campaign explicitly records that it is non-authoritative and that
  its content was not reused in the accepted findings register. Do not cite it
  as a project finding or decision.

The authoritative historical remediation result is the adjacent
[`P2PKIT_REMEDIATION_TRACKER_2026-07.md`](../P2PKIT_REMEDIATION_TRACKER_2026-07.md).
Current validation status is in
[`../../../../validation/README.md`](../../../../validation/README.md).

## Historical test evidence caveat

The retained XML corpus contains 233 suites and 1,507 test executions. Three
recorded runs contain historical failures: a file-transfer cancellation race,
a session close-classification mismatch, and an iOS reconnect-rotation timeout.
The campaign notes and subsequent remediation history record reruns/stress
coverage and later fixes. These files must never be summarized as a green test
run for current `main`; current commits require their own exact-commit gates.

Paths and branch/commit descriptions inside the snapshot refer to the original
July workspace. They were intentionally not rewritten to pretend that the
campaign happened at the archive path. One accidental NUL byte in
`reports/A08-filetransfer.md` was removed so the otherwise unchanged Markdown
remains renderable.
