# Follow-ups not yet established as new defects

These are inherited hypotheses, not fresh findings or issue-completion claims. Reproduce at the current tree and read
complete related issue histories before tracking a new defect. Record negative results as well as confirmations.

## Desktop large-text/RTL sidebar applicability

A synthetic 780x600, RTL, fontScale1.5 render during #135 review showed the pre-existing fixed-width StatusHeader row
extending beyond its sidebar. The English-only sample does not expose a text-scale/RTL setting; actual supported-host
propagation and baseline reachability were not established. Determine applicability and perform a baseline comparison
before calling this a functional/accessibility defect. The separate warning-induced send-button collapse was corrected
within #135 and is not this hypothesis. Old render screenshots are private evidence, not included in Git.

## Swift startup/stop and exported coroutine cancellation

During #202 review, `ContentView.swift` published `kit` before asynchronous startup finished while Stop remained
available. Trace rapid Start/Stop, late collector/probe installation and old stop/start finalizers against a replacement
kit. `isStarting` alone is not proof against cross-kit overlap when stop completion and resumption interleave.

Separately verify whether cancelling a Swift Task cancels the exported Kotlin suspend Flow collector at the actual
bridge boundary. Existing #260 describes long-lived incoming flows, not necessarily that mechanism. Synthetic lease
unit tests do not establish native callback cancellation. Require a bounded reproduction and duplicate check; do not
infer native or physical-device behavior from these suspicions.

## Previously promoted suspicions — do not refile

- Stale out-of-lock JmDNS samples were reproduced, filed as [#340](https://github.com/p2pKit/P2pKit/issues/340) and
  corrected/reviewed in the audit branch.
- Plugin parser allocation before size rejection was reproduced, filed as
  [#345](https://github.com/p2pKit/P2pKit/issues/345) and corrected/reviewed.
- Dependency-submission checksum verification disabling was independently traced/reproduced, filed as
  [#348](https://github.com/p2pKit/P2pKit/issues/348) and corrected/reviewed.

Historical notes predating these dispositions must not be mistaken for still-unfiled new findings. See the issue ledger
and GitHub outcomes for scope and remaining hosted/platform validation.

## Future provisioning producers returning Pending

The Android manager currently never returns `JoinNetworkResult.Pending`. #337's presenter tests include synthetic
Pending behavior, but generic failure events have no operation/resource identifier. Before reusing that presenter
with a different Pending-producing adapter, specify failure attribution during concurrent hotspot work and test the
actual producer. This is a future-adapter applicability concern from independent #337 review, **not a verified current
Android defect**, a lossless/replay guarantee, or a new issue claim.

## File destination authentication-error casts

The #137 reviewer observation was **confirmed, filed as [#358](https://github.com/p2pKit/P2pKit/issues/358), and
independently repaired/pushed** through `d424a23` on 8 September. Original JVM production plus regressions produces
two intended cast failures/three controls; Android original-production control produces three failures/five controls.
The public custom open callback and synthetic internal preflight reproduce `ClassCastException` before retirement,
abort and Failed/result publication. No current application-authentication callback during install was demonstrated.

Both destination catches now require a statically typed file failure; the general classifier still preserves genuine
channel authentication. See [the repair report](repairs/358.md) and
[verified outcome](https://github.com/p2pKit/P2pKit/issues/358#issuecomment-5578319370). Do not refile this cast root or
rewrite historical #137 evidence as if its then-unverified observation had already been reproduced. This remains
local integration/lifecycle correctness, not an authentication bypass or demonstrated data loss.

## File destination cleanup cancellation

During #358 review at `d424a23`, the unchanged generic setup-error cleanup in
`library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/FileTransferDispatcher.kt:655-681,706-732` was noted
to retire the active offer before awaiting `abortUnownedDestination`, then publish `session.markFailed` afterward.
Investigate whether cancellation of the accepting caller while abort is awaited propagates structural cancellation
through `captureCleanupIssue` before the public session becomes terminal or the first terminal response is attempted.
An ordinary IOException open failure may reach the same path; this is not the #358 classifier/cast root.

This is **unverified**. The reviewer ran no reproducer, and #358's open-result cancellation test does not exercise
cancellation during abort. Search full issue/closed-fix histories, then use a bounded deterministic caller-cancel/abort
interleaving to check final state, retired entry/byte budget, replay, repeated operations and cancellation propagation.
Do not infer a confirmed leak, lost data, permanent remote failure or repair from this source hypothesis. Track a
distinct issue only if reproduced and not already covered; preserve #358's independently approved classification.

## XcodeGen version-probe status and failed-install cleanup

During #225 source/evidence review, the unchanged `scripts/install-xcodegen.sh` version probe was noted as unquoted
and used in command-substitution/conditional contexts. Reproduce whether a fake binary printing the expected version
but exiting nonzero is accepted, whether failed probes leave temporary unpack/download directories, and whether an
executable path containing spaces is supported. Use synthetic archives, not a live installer or personal files.

This is **unverified**, not a new issue or a #225 approval claim. Check complete issue histories before tracking an
independent defect. The caller still verifies a reviewed archive checksum; do not infer checksum bypass or attacker
control over that archive. #225 intentionally changed fixture inputs/policies, not the real installer.

## Dependency curator ambient GPG packet and key inspection

During #226 review, unchanged `gpg --list-packets` and `gpg --show-keys` invocations in
`scripts/review-dependency-verification.sh` were noted to omit the explicit temporary-home selection used by its
list/import/verify calls. Reproduce with a synthetic HOME/GNUPGHOME and controlled configuration whether those read-side
operations create ambient files/workers or allow unrelated local configuration to disrupt curation. Never probe a
personal keyring or infer disclosure from source alone.

This is **unconfirmed**, independently trackable if verified, and not folded into #226's workspace/socket correction.
Read complete related issue/closed-fix histories before filing anything new. #226's regression suite deliberately isolates
ambient operations in a synthetic home; its passing result is not proof that every production GPG call selects that home.

## Apple same-generation invalid re-resolution

This inherited hypothesis was **confirmed within existing [#332](https://github.com/p2pKit/P2pKit/issues/332)** on
8 September (local date), after #356. The actual first-party native-input regression at `3134789` produced ten intended
cache-retention assertion failures and four passing controls, zero errors/skips. The original decode/validation block
was unchanged apart from extraction; actual native endpoints/TXT, generation gates and admission/relay/registry were used.
This is not live native browse-result/multicast delivery or physical-device evidence. See the
[verified investigation](https://github.com/p2pKit/P2pKit/issues/332#issuecomment-5575802714).

The complete four-file Apple follow-up is now independently approved/pushed at `78ef361`, preserving the prior
JVM/Android approval; no duplicate was filed. See [the repair report](repairs/332-apple.md) and
[verified outcome](https://github.com/p2pKit/P2pKit/issues/332#issuecomment-5576324322). Twenty native-input methods/both
profiles cover Found-to-invalid-to-Lost, late subscribers, controlled pending-dial ownership, stale/current generations,
capacity, recovery, repeated rejection and stop/restart. Full check/Android assembly passes 2,387/zero failures/errors/
one unchanged manual skip; eight controls and 14 static gates pass. This is not live multicast or a real TCP handshake.
Read #23 and merged #24/#72/#101/#102 for separate startup/path/generation/correlation decisions; their external
campaigns and #120 architecture remain pending. The #332 row returns to approved repository scope, not issue closure.

Separately, the Apple NUL-key alias mechanism was **confirmed and filed as
[#356](https://github.com/p2pKit/P2pKit/issues/356)** using actual macOS Network.framework plus a first-party caller
trace. Its complete six-file correction is independently approved/pushed at `183b6c9`; see the [repair report](repairs/356.md).
That fixes the original-key/native-representation/byte boundary; the separately approved #332 correction handles the
lifecycle transition. Neither expands #229's original value approval. Earlier reports' unconfirmed/pending wording
is historical and superseded here, not rewritten. The 0.8.0+ admission-change restriction remains.
