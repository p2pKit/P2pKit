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

During #229 review, `IosLanDiscoveryTransport.emitPeer` was observed returning on malformed/invalid TXT or mismatched
service identity without withdrawing previously admitted cache/relay/endpoint ownership. The reconciliation function
keeps same-generation entries. This is **unconfirmed at the cross-component transition boundary**: no bounded actual
caller regression has been run and no new fix/disposition is claimed.

Read/update existing [#332](https://github.com/p2pKit/P2pKit/issues/332) if the same invalid-record-withdrawal cause is
confirmed on Apple; do not duplicate it merely because the current title names JVM/Android. #23 and merged #24/#72/
#101/#102 histories were read: their generation/path/failed-dial corrections are not clear proof of this transition.
Use an owned native endpoint and synthetic TXT, verify Found-to-invalid-to-Lost, late subscribers, retained dial
leases, stale generations, recovery, repeated invalid records and shutdown. Preserve the existing JVM/Android repair.

Separately, the Apple NUL-key alias mechanism was **confirmed and filed as
[#356](https://github.com/p2pKit/P2pKit/issues/356)** using actual macOS Network.framework plus a first-party caller
trace. Its complete six-file correction is independently approved/pushed at `183b6c9`; see the [repair report](repairs/356.md).
That fixes the original-key/native-representation/byte boundary, not this unconfirmed lifecycle mechanism and not an
expansion of #229's value approval. Investigate the transition after #356, using the corrected native decoder.
