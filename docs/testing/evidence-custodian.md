# CI evidence custody and owner-controlled sample Releases

This procedure covers **ordinary FULL/Desktop CI and development sample
prereleases**, not production/Maven/Store publication. Source implementation is
not Release readiness. Both ordinary activation HOLDs, qualified cache/native/
resolver/custody/scheduling requirements and required security checks remain.
The [dated implementation record](../maintenance/sample-release-owner-policy-2026-09-20.md)
records what actually exists and what remains unexecuted.

## Owner, evidence and access

The responsible owner/custodian is **`Apdelrahman1911`**, GitHub user ID
**`104788132`**. Both were read from the authenticated GitHub account, not
inferred from a display name. The owner approved using the same account for PR
creation, personal authorization, manual merge and subsequent evidence approval.
No email address, second account or external storage service is required.

The custodian protects the private key, retrieves the original evidence before
expiry, verifies/decrypts it privately, records a truthful redacted review and
decides whether to approve publication. Custodianship is a responsibility, not a
new GitHub permission or authority to waive failed gates. The agent implements
and reviews source but must not post either manual approval as the owner.

Ordinary execution generates original admission/event/recipient-policy records,
product and test reports/transcripts, invocation and same-home stop records,
native ownership/retirement observations, dependency preparation/restore/seed
records, clock/budget receipts, and applicable packaging records/hashes. FULL
also retains its required ABI/simulator/supplement evidence. Failures must remain
failures; missing originals, unknown retirement or an invalid seal must not be
replaced by a plausible reconstructed receipt. Not every failure permits export.

After known writer retirement, the maintained exporters produce only:

- **`evidence.tar.gz.gpg`**: the encrypted original packet;
- **`manifest.json`**: public source/tree, run/attempt, policy and ciphertext
  size/hash bindings, not the private transcripts.

The ordinary artifact names are
`ordinary-desktop-evidence-<OS>-<ARCH>-<source>-<run>-<attempt>` and
`ordinary-full-evidence-<OS>-<ARCH>-<source>-<run>-<attempt>`.
The publisher requires three Desktop native-host packets and the FULL packet
from the exact main `complete-gate` run/attempt. Android packaging shares Linux's
Desktop invocation; it is not a fifth ordinary evidence packet.

GitHub Actions artifact downloads require sign-in and repository read access.
This repository is public: the ciphertext and public manifest are **not
owner-only downloads**. The private key controls plaintext access, not GitHub
artifact permissions. No additional private-storage infrastructure is introduced.
APK/MSI/DMG/DEB assets go separately to public repository **Releases**, unencrypted
and downloadable without the evidence key or Actions access.

## What the key does

[`hosted_evidence.py`](../../scripts/hosted_evidence.py) validates a public-only
OpenPGP key, its full 40-hex v4 fingerprint, usable encryption capability and
expiry. It rejects secret-key packets. Its encryption uses AES256 with the
session key encrypted to the exact validated encryption subkey; the archive is
integrity-protected OpenPGP ciphertext (MDC/AEAD shape), not an unprotected old
packet or proof of sender identity.
The native Windows exporter follows its separate private-handle contract.

The key **does not sign commits, APKs, installers, Releases or test verdicts**.
The separate post-return `seal` rechecks original source/custody/export bindings;
it is not a private-key digital signature or evidence of private decryption.
Public hashes provide byte bindings, not a substitute for trusted provenance.
The owner independently confirms the public fingerprint before trusting it.

The real ASCII-armored public key, uppercase primary fingerprint and SHA-256 of
the exact armor bytes belong in **`.github/test-evidence-recipient.json`**.
The [real public-only policy](../../.github/test-evidence-recipient.json) is now
prepared on the integration branch, **not delivered to trusted main or admitted**.
It contains no placeholder key or assumed approval.
Private material belongs only in the dedicated restricted VPS directory and
the owner's secure private copy, never Git, Actions, chat or Telegram.

### Completed setup, with separate evidence scopes — 20 September 2026

The actual public export passed the maintained `validate_recipient` backend at
source **`44ded2041cd077d9f98c880d58c020adb2bf4360`** on
**`2026-09-20T16:29:19Z–16:29:20Z`**. The exact export and backend source hashes
were rechecked unchanged when preparing the policy; that completed validation
was not rerun or promoted to hosted qualification.

| Public property | Validated value |
| --- | --- |
| Primary fingerprint | `0A996D2BC19518FB50071A95D3FDADA57CFB7E1F` |
| Encryption-subkey fingerprint | `4D7CF63A16AFC0BDDC82F3E686D7D3D9A7B44350` |
| UID | `P2pKit CI evidence (Apdelrahman1911)` |
| Algorithm/capability | RSA4096 certification-only primary; usable RSA4096 encryption-only subkey |
| Both expiries | `1821484800` = `2027-09-21T00:00:00Z` |
| Exact public armor | 3,155 bytes; SHA-256 `5dcb108725ffb2a9c99f4e61e35c3473d34776530effca7385282faf62b86aaf` |
| Public packet tags | `6,13,2,14,2`; no secret-key packets |

Public-validation result SHA-256:
`2d0aa5105cc57fb3f034687652d212a1a260172eafb136c982743a8ec9bffafd`.
This binds the retained local validation record, not a hosted custody result.

The owner separately confirmed: **private backup restore/decrypt passed;
fingerprints matched; fresh pinentry succeeded; secure personal backup retained**.
That is **owner-confirmed recovery, not agent-observed execution**. The agent
checked only backup existence/permissions before confirmation and did not run
the recovery helper or read the secret export, revocation contents or passphrase.
Do not repeat the completed setup or publish its private recovery material.

## Private key-generation procedure — reference, not a request to regenerate

The owner explicitly designated this VPS as the trusted generation environment.
The inspected installed tools are GPG **2.4.4** and `pinentry-curses`. No existing
project key-generation helper or trusted routine custodian key was found. Use
a certification-only RSA4096 primary plus RSA4096 encryption subkey, compatible
with the maintained v4 recipient validator. Public label:
**`P2pKit CI evidence (Apdelrahman1911)`**. Both keys expire at
**`2027-09-21T00:00:00Z`** (epoch **`1821484800`**).

Use the owner's **own private SSH terminal with pinentry**, not an agent-captured
PTY, chat input, `script` recording, CI job or logged session. Enter a strong
nonempty passphrase only into pinentry. Never use a passphrase argument,
environment variable, file, loopback input, empty-passphrase fallback or shell
tracing. No private passphrase channel is established in the agent session.

The owner used
**`/root/.local/share/p2pkit/evidence-custodian/2026-09-20/`**. It now exists;
do not overwrite it or rerun these generation commands. The exclusive directory
creation below records the original private-terminal procedure:

```bash
set +x
set -eu
umask 077
export TZ=UTC
export GPG_TTY="$(tty)"
KEY_DIR=/root/.local/share/p2pkit/evidence-custodian/2026-09-20
mkdir -p -m 0700 "$(dirname "$KEY_DIR")"
mkdir -m 0700 "$KEY_DIR"  # exclusive: an existing destination is an error
mkdir -m 0700 "$KEY_DIR/gnupg" "$KEY_DIR/backup"
export GNUPGHOME="$KEY_DIR/gnupg"

gpg --no-options --pinentry-mode ask --quick-generate-key \
  'P2pKit CI evidence (Apdelrahman1911)' rsa4096 cert 20270921T000000
FPR="$(gpg --no-options --with-colons --with-fingerprint --list-keys |
  awk -F: '$1 == "fpr" { print $10; exit }')"
test "${#FPR}" -eq 40
gpg --no-options --pinentry-mode ask --quick-add-key \
  "$FPR" rsa4096 encr 20270921T000000

gpg --no-options --armor --output "$KEY_DIR/public-key.asc" --export "$FPR"
gpg --no-options --with-colons --with-fingerprint --with-subkey-fingerprint \
  --list-keys "$FPR" > "$KEY_DIR/public-metadata.colons"
gpg --no-options --with-subkey-fingerprint --list-keys "$FPR" \
  > "$KEY_DIR/public-metadata.txt"
sha256sum "$KEY_DIR/public-key.asc" > "$KEY_DIR/public-key.sha256"
# --output is mandatory: never emit the secret export on stdout.
gpg --no-options --pinentry-mode ask --armor \
  --output "$KEY_DIR/backup/secret-key.asc" --export-secret-keys "$FPR"
test -s "$KEY_DIR/backup/secret-key.asc"
cp "$GNUPGHOME/openpgp-revocs.d/$FPR.rev" "$KEY_DIR/backup/revocation.asc"
find "$KEY_DIR" -type d -exec chmod 0700 {} +
find "$KEY_DIR" -type f -exec chmod 0600 {} +
```

These are **reference instructions**; the completed public validation and
owner-confirmed recovery are recorded separately above. Installed GnuPG's
`OpenPGP Key Management` documentation supports `YYYYMMDDThhmmss` for
both quick-generation expiry arguments; a date-only value is not used. After
generation, independently check the public listing has exactly the intended
primary/subkey, full fingerprints, UID, RSA4096 capabilities and expiry field
`1821484800` for both. Validate the actual public export with the maintained
recipient backend before admitting it. If any step fails, preserve that private
directory and inspect the failure; do not silently generate another identity.

The GnuPG home contains the protected private key; `backup/secret-key.asc` is its
passphrase-protected export. The revocation certificate is sensitive too. Retain
the whole dedicated directory securely, and use owner-controlled SSH/SFTP to
make the requested personal secure copy outside Git/CI evidence. Verify backup
restoration/decryption privately before relying on it; file existence is not a
recovery test. The agent may report only the directory path, public armor,
fingerprints, UID, algorithm, expiry and public-key hash. Never display/copy the
secret export or passphrase into tool output. Key expiry stops new encryption;
it does not erase the key or automatically destroy old ciphertext.

## Recipient policy and three different clocks

[`hosted_test_identity.py`](../../scripts/hosted_test_identity.py) already
requires the following exact policy fields (no additional assumed approvals):

| Field | Prepared owner-authorized value |
| --- | --- |
| `schema` | `1` |
| `repository` | `p2pKit/P2pKit` |
| `purpose` | `P2PKIT_TEST_TRANSCRIPTS` |
| `retrievalOwner` | `Apdelrahman1911` |
| `retentionDays` | `14` |
| `notBefore` | Inclusive `1789948800` = `2026-09-21T00:00:00Z` |
| `expiresAt` | Exclusive `1791158400` = `2026-10-05T00:00:00Z` |
| `recipient.publicKey` | Exact validated 3,155-byte ASCII public armor, including original newlines |
| `recipient.fingerprint` | `0A996D2BC19518FB50071A95D3FDADA57CFB7E1F` |
| `recipient.sha256` | `5dcb108725ffb2a9c99f4e61e35c3473d34776530effca7385282faf62b86aaf` |

This **prepared, not-yet-active admission window** is separate from the one-year
key lifetime and from each artifact's retention. Preparation on 20 September
does not admit execution: the real clock is still before `notBefore`. Explicit
timestamp boundary tests of the pure parser are offline models, not live admission.
The window must not be backdated or silently
rolled forward if prerequisites miss the window. Reannounce any replacement
before applying it. Admission requires `notBefore <= now < expiresAt`; the
exporter also prevents policy validity from exceeding validated key lifetime.

The policy must be in the **legitimately trusted base** before ordinary PR or
manual candidate admission can use it. PR admission reads the original base
commit, manual/bootstrap admission reads the original fetched main, and main
push admission reads that main source. Candidate policy cannot authorize itself.
Adding this JSON is not Markdown-only CI: the current scope classifier selects
FULL, whose missing-base/custody/cache prerequisites remain. An owner decision
or a public key alone does not resolve that bootstrap path. Do not weaken scope
classification, use a force/admin merge, fabricate a check or remove a HOLD to
put it into main. Record the eventual real policy commit/blob/hash, owner
authorization and successful normal delivery before using it as trusted input.

The prepared JSON is **3,631 bytes**, SHA-256
`2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521`.
Its decoded armor is byte-identical to the validated export. **25/25 focused
author offline controls passed**: exact public input/backend bindings, pure
parser start/end boundaries, closed-schema/hash/field/duplicate/size refusals,
and the expected real-clock refusal before the window. The separate scope
classification returned **`full`**. These controls did not invoke hosted
identity, GPG, encryption/decryption, GitHub Actions or any product build.
The containing commit's #437 record binds the final source review and checks;
it is not personal PR authorization or approval of future evidence.

### What enforces 14-day evidence retention

The ordinary upload steps already contain the following settings in
[CI](../../.github/workflows/ci.yml) (`ordinary-evidence`) and
[Desktop cross-host](../../.github/workflows/desktop-cross-host.yml)
(`ordinary-evidence`):

```yaml
uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
with:
  # The actual workflows list only export/evidence.tar.gz.gpg and export/manifest.json.
  retention-days: 14
  overwrite: false
  if-no-files-found: error
```

GitHub calculates retention for each artifact from its upload/creation time;
the artifact API's **`created_at` and `expires_at` are the actual UTC record**.
No upload has been scheduled here, so there are no actual artifact expiry dates
to invent. For example only, an artifact created `2026-09-21T13:45:00Z` with
14 days has a maximum policy expiry `2026-10-05T13:45:00Z`, not the recipient
policy's midnight boundary. The publisher's `artifact_identity()` requires:

```text
expired == false
created_at <= now < expires_at <= created_at + 1,209,600 seconds
```

This is automatic service retention plus a fail-closed metadata check, not a
new purge service. GitHub expires/deletes artifacts under its retention system;
the implementation does not prove physical erasure at an exact second or
guarantee retention against authorized early deletion. Never reupload old
evidence to renew the window or relabel an expired artifact as available.
Missing/expired packets block pending publication. The workflow cannot delete
copies a reader downloaded: the owner privately disposes of review plaintext
and temporary copies, without adding a long-term evidence backup. Public hash
manifests/redacted reviews and approved public Release assets may remain;
neither contains or recovers private originals. The private key/backup has a
separate security lifecycle and is never subject to evidence-artifact upload.

## The two manual approvals

### Before merge: exact-head PR authorization

GitHub does not allow a PR author to submit native `APPROVED` on their own PR.
The owner explicitly accepted this replacement instead of a second account:

```text
/p2pkit approve-pr <full-final-PR-head-SHA>
```

After all four required PR checks (`complete-gate`, `review`, `scan / osv-scan`,
`osv-scanner`) pass, the owner personally posts that exact line as a **new** PR
comment, then manually performs a preserving merge. Do not edit the comment:
the publisher requires `created_at == updated_at`, after the required check
timestamps and no later than the merge. Wrong head/account, extra command text,
post-merge authorization or an unresolved `CHANGES_REQUESTED` is invalid.
Subsequent head/check changes need a fresh authorization. The actual main merge
message must contain **`[release ci]`**, with that case and spacing.

[`publish-sample-release.py`](../../scripts/publish-sample-release.py) binds the
owner login **and numeric ID**, comment ID/URL/body hash, timestamps, final head,
manual merger and required checks. It validates this before publication; it does
not install a native GitHub comment-required merge rule. Existing branch rules
are not weakened. The comment is the trusted recorded authorization, not this
guide, an agent review, an agent-posted status comment or a claimed native
self-approval. The owner must not use an admin merge to evade required checks.

### After build: evidence review and protected publication

1. After genuine marked-main execution and technical gates pass,
   `prepare-review` downloads/inspects the four public app bundles. It binds the
   four original encrypted evidence artifact identities and produces public
   `receipt.json`, `sample-release.json`, `SHA256SUMS`, `review-request.json` in
   **`sample-release-review-<publisher-run>-<attempt>`**. Metadata binding alone
   is not ciphertext validation, decryption or internal evidence acceptance.
2. The owner retrieves each exact evidence artifact named in that request,
   verifies the original ZIP digest and `manifest.json` ciphertext size/hash,
   and decrypts in a private working directory using the custodian key and
   pinentry. Never decrypt to stdout, a public log or the checkout. Inspect
   archive membership before safe extraction; do not execute evidence contents.
   Verify internal source/tree/run/attempt/policy, original reports, receipts,
   retirement, budgets and issue-specific acceptance against the public request.
   Record failures honestly and withhold approval if anything is missing.
3. The owner opens the pending **`sample-development-release`** environment
   deployment and personally clicks **Approve and deploy**, supplying exactly
   the challenge shown by that `prepare-review` result:

   ```text
   APPROVE_EVIDENCE <publisher-run>/<attempt> <review-request-sha256>
   ```

   This is the owner's evidence-review attestation. The agent must not submit
   it through the owner's API token. Approval history does not itself prove the
   human read/decrypted the packet, so the separate redacted review is important.
4. The isolated publisher checks the real Actions approval history, sole owner,
   exact environment ID, current run/attempt, exact challenge, unexpired unchanged
   review/evidence artifacts, checks and inspected app manifest again before
   any Release mutation. A rerun cannot reuse another attempt's challenge;
   `workflow_dispatch operation=publish` uses this same path. `verify` stays
   read-only and never grants publication permission.
5. The development prerelease uses `samples-<full-source-SHA>`, never a library
   `v*` tag. Only the four app packages plus notices/manifest/checksums become
   public assets. Remote asset digests and anonymous access are checked. This is
   not application installation, signer, LAN, physical-device or whole-audit
   acceptance. Published RC3, versions, compatibility restrictions and the
   production publication prohibition stay unchanged.

Required environment configuration: sole required reviewer `Apdelrahman1911`
(`104788132`), `prevent_self_review: false`, custom deployment branch **`main`**
only, **`can_admins_bypass: false`**. Disabling self-review prevention is intentional
so the owner can approve their own triggered deployment; it does not remove
the required reviewer. The owner disabled administrator bypass; API readback
on **20 September 2026, refreshed at 16:52 UTC**, confirms all these settings,
environment ID **`22338522000`**, and the sole `main` branch policy
**`60503975`**. The environment-configuration blocker is resolved, not the
execution or publication prerequisites. The publisher rechecks the real settings
and refuses any later nonconforming configuration. The original resolution is
[recorded in #437](https://github.com/p2pKit/P2pKit/issues/437#issuecomment-5751072195).

These protections cover the maintained workflow paths, not an impossible
guarantee that a repository administrator cannot later rewrite policy outside
them. Such rewriting/direct publication is not authorized by this procedure.

## Who does what, in order

| Step | Owner | Agent/source | GitHub/CI and independent verification |
| --- | --- | --- | --- |
| Custodian/key | Owner has confirmed private recovery and secure personal backup | Actual public validation recorded; no secret access or repeated recovery | Public backend validation passed; recovery is owner-confirmed, not agent-observed; no CI private key |
| Trusted policy | Public identity/window authorized; eventual exact-head PR authorization still required | Real public JSON prepared, not trusted or admitted; no PR or CI started | Legitimate original-base bootstrap, required checks and normal delivery remain blocked; candidate cannot authorize itself |
| PR | Personally post exact-head authorization after checks; manually merge with `[release ci]` | Never auto-approve/merge; preserve required gates | Check identity/history; comment is validated by publisher, not native self-review |
| Build/evidence | Do not waive HOLDs or qualification | Complete/review remaining bounded provider/custody prerequisites | Once admitted, run actual hosted tasks, retire writers, seal/encrypt and upload for 14 days |
| Review | Retrieve/decrypt/inspect originals before expiry; record redacted decision | Prepare source/run/hash-bound public request, not fake evidence | Independent source/runtime evidence checks and artifact availability remain mandatory |
| Publish | Personally approve exact post-build challenge | Enforce the same fail-closed path on automatic notifications/manual publication/reruns | Only after all gates, copy unchanged public app bytes; verify remote digests/access |

There is no authorized final **production Release** step in this flow. The
destination is a **development sample prerelease**, and current status remains
**NOT_READY** until the actual prerequisites, qualifications and approvals exist.
