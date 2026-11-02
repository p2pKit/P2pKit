# Test Center implementation

The Android, iPhone and JVM lab applications now expose a Test Center containing
the cases in [the physical checklist](../validation/physical-test-checklist.md)
and [#538](https://github.com/p2pKit/P2pKit/issues/538). This source is under
development; it has not been installed or physically qualified by this change.

Built-in RPC entries use the existing connected-device workload controls and
approval policy. Other entries show equipment, steps, duration and evidence.
Starting a guided observation starts a local observation timer, not an external
runner, radio fault, backup, socket slow reader or capacity cohort.

Started/checkpoint/final observations receive distinct immutable record IDs and
one shared group ID. They use the existing protected per-run archives. A process
restart never resumes a workload or turns an unfinished observation into a pass.
Marked steps and evidence references are operator-supplied; even complete
observations remain `NeedsReview` / `AwaitingReview`. Measured RPC responses,
client counts and success cannot be supplied through an observation record.

The recent-evidence export streams at most 100 bounded records to JSON Lines.
Its header states `recentOnly=true`; the footer contains `exportComplete=true`
and the record count. Require the footer when analyzing an export. Exported notes
are private, and the user's chosen destination may retain a partial file on
failure. Existing archives are retained. This export does not enumerate older
archives or export keys, protected identity stores or credentials.

The Test Center initially follows the existing English-only experimental RPC
operator UI. Case IDs, protocol names, status codes and filenames are stable
technical identifiers. The new controls use visible text for accessible names,
native checkbox state and platform text direction. Localized production UI and
physical assistive-technology checks are not claimed by this source change.

Remaining engineering: direct Mac cohort launch/control with source-matched
preparation; mixed physical-phone plus 255 Mac-client coordination; genuine
socket-read backpressure; coordinated long faults; reviewed unplugged recorder;
controlled native callback/storage/packet fixtures; authoritative independent
peer inputs; full archive browsing/export. Hardware/OS/backup/Windows matrix
execution and independent review remain required. The catalog does not supply
these prerequisites or close their issues.

Saved archive controls load newest-first pages of 20 original records, including
records older than the recent window. Export one selected output or the complete
archive to JSON Lines; archive exports declare `recentOnly=false`. Reading never
replays a test or changes its original source/direction. Tombstoned outputs are
omitted. The complete export is bounded to 256 MiB; if it exceeds that limit,
export individual outputs. Original archives remain untouched on error.

Full on-device archive enumeration needs Android 8/API 26 or later; Android 7
retains recent sharing and requires the computer collector for older files.
iPhone sharing and Mac export run away from the UI thread. Stop workloads before
archive operations. Private exports are plaintext evidence; share them only with
the intended reviewer. They contain no profile secrets, but notes may contain
private operator information.
