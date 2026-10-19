# Installed Windows password-refusal control

**NOT_READY. This source is an executable control, not evidence that it passed.**

Use the maintained driver with `--operation password-refusal` only after actual
account/session, startup, installed-byte and original supervisor admission. It
selects exactly `--rpc-windows-disposable-password-refusal` in the canonical
installed MainKt application. The existing 15-second command, 5-second cleanup
and 30000ms outer deadline remain unchanged.

The owner-approved disposable application profile must already contain the
existing synthetic encrypted marker. This operation never creates a fixture,
changes a password, resets identity/trust, injects a provider or enters networking.
It uses the fixed installed provider and three separately retained original
acquisitions: valid unlock, deliberately wrong synthetic password, valid reopen.

Both valid acquisitions verify the existing marker and hash the profile header
and all encrypted records through admitted native directories while holding the
profile lease. Namespace membership and hashes must match after refusal. Locked
lease files are not reopened for hashing; native lease and settled-inventory
checks retain their original semantics. Hashes and plaintext are not printed.

The wrong-password acquisition must produce the actual AEAD authentication-tag
failure, return no usable profile and acknowledge cleanup without a retained
session. Password arrays must be cleared. Any other error, unexpected acceptance,
changed ciphertext or uncertain cleanup fails and retains the original owners.
Failed physical cleanup is never retried. All successful closes require an empty
managed handle ledger, plus the supervisor's separate process/descendant/capture
and cleanup observations; a printed JSON result cannot qualify process retirement.

Record exact source/tree, MSI, runtime, installed inventory and original receipts.
This is a narrow W06 password/reopen control. It does not qualify tamper detection,
interrupted publication, power-loss durability, peer revocation, hostile paths or
the full native lifecycle matrix. Preserve every failure and fixture unchanged.
