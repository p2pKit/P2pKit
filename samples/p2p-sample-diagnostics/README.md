# Shared sample diagnostics and incoming-file ownership

The CLI, Desktop UI and Android sample use `reservedFileDestination` after
atomically claiming an unused final filename. iOS uses the equivalent native
`AtomicFileTransferDestination` and `SampleTransferStaging` owner.

Incoming payload staging lives in a separately claimed UUID directory below an
app-controlled inbox namespace, never in the final-filename namespace. A transfer
holds an exclusive OS file lock until its writer and staging cleanup finish.
Reconciliation requires the exact ownership record, a successfully acquired
nonblocking lock and only recognized regular staging entries. A process-local
registry additionally prevents reopening a locally held lock inode. Unknown files,
directories and symlinks do not grant deletion authority. The parent inbox must
remain application-controlled; this is not a sandbox against hostile same-user
filesystem mutation.

The supplied trusted inbox is canonicalized as before (including Android's OS
storage aliases). Every discovered owned-namespace, UUID, record, lease and part
is then checked without following links, including its original path prefixes,
before record/lease/payload access or deletion. Canonical-path equality alone is not a
Windows no-link check. JVM uses NIO `NOFOLLOW_LINKS` attributes and rejects
symbolic/special entries; Android explicitly supplies `Os.lstat` (API21+) and
does not invoke the JVM NIO adapter on API24. These are snapshot checks, not a
race-proof sandbox against a privileged actor replacing paths after validation.

**No filename-only migration cleanup is safe.** Legacy sibling `.p2pkit-*.part`
and `*.p2pkit-part` files are left untouched: they can be valid completed payloads
or another version/process's live transfer. Incomplete claims lacking their
ownership record are also left untouched. Operators must independently establish
ownership before removing such leftovers. No payload filename is newly forbidden;
an existing file colliding with a staging namespace name is preserved and a
bounded alternate namespace is claimed. Empty namespace roots may remain after
successful cleanup.

The SDK's existing durable destination overloads still stage beside the target.
The additive three-argument overload accepts an exclusively owned staging
directory, checks the actual filesystem, and keeps atomic publication without a
copy fallback. POSIX commit syncs both changed directories. The existing Windows
limitation remains: the public JDK provides file sync and atomic publication, but
not a directory-entry power-loss guarantee. This change does not expand that
guarantee or change quota, consent, verification, final-name claims or abort's
protection of possibly published data.

Tests include real separate-JVM live-owner, abrupt-exit and fresh-lifecycle
reconciliation controls. Android host tests explicitly substitute Android syscall
boundaries; Swift tests require the native `DiagnosticsTests` scheme. Neither host
test models nor source review establish a physical-device or cross-platform
network-transfer qualification.
