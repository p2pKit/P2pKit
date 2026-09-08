# Follow-ups not yet established as new defects

This file distinguishes unverified hypotheses from separately promoted/repaired findings. Reproduce suspicions at
the current tree and read complete related issue histories before tracking a new defect. Record negative results
as well as confirmations. Promoted findings below are not unfiled concerns or repair-completion claims unless
an exact independent approval is stated. The transfer stop is superseded; #223/#367/#368 have scoped source
approvals below. Active work is private, unapproved/unexecuted hosted-facility preparation; #268 is only planned
after any freshly reproduced prerequisites and sequential independent reviews. Continue feasible work.

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

The #358 review observation was **confirmed, filed as [#359](https://github.com/p2pKit/P2pKit/issues/359), and
independently repaired/pushed** at `de88284` on 8 September. Original production plus three regressions produces
two intended failures/one control: actual accepting-Job cancellation during abort leaves the retained transfer
Offered despite successful ledger/budget retirement. Abort runs, replay works and a full-budget replacement succeeds.
The skipped initial result can leave the sender waiting for its watchdog; no demonstrated file leak/loss, budget leak,
authentication bypass or permanent remote retention was established. Callback-only cancellation remains distinct.

Both generic setup catches now complete bounded settlement in NonCancellable context, then explicitly restore caller
cancellation. Original typed causes, entry identity/epoch fencing and best-effort notification remain; shared bounded
helpers, platform destinations, API/ABI, wire and durability guarantees are unchanged. The install sibling is aligned,
not a separately demonstrated throwing application callback. See [the repair report](repairs/359.md) and
[verified outcome](https://github.com/p2pKit/P2pKit/issues/359#issuecomment-5579078847). Final full check/Android assembly/strict core Dokka passes
2,459/zero failures/errors/one unchanged manual skip; focused33passes,three mutation controls,14static gates.
Do not refile this mechanism or rewrite historical #358 evidence as if its then-unverified observation was already
confirmed. The later [#358 investigation comment](https://github.com/p2pKit/P2pKit/issues/358#issuecomment-5578711750)
records reproduction/filing; #359 has its own approval at `de882840e1e24aa04339b2285e8cd753af265b40`.
Host/arm64 simulator and synthetic pinned in-memory wires are not physical or independent interoperability.

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

## All-tree archive whitespace policy

The failed actual-YAML replay during #144 was **confirmed as distinct [#360](https://github.com/p2pKit/P2pKit/issues/360)
and independently repaired/pushed** at `6995130`. Both pre-#144 manual all-tree gates exited 2 on six formatting
diagnostics in three unchanged historical files; an ordinary-range control passed. Exact-path/category exceptions,
byte-stable checkout attributes and mandatory head/index/worktree hashes now preserve those archives without
unchecked replacement. No archive contents were modified; #301/#303's retention decision is intact.

See [the repair report](repairs/360.md) and [verified outcome](https://github.com/p2pKit/P2pKit/issues/360#issuecomment-5580382007). #360 was independently approved before
#144's final review; both final actual gate entry points pass. #223's wrapper LF defect was then separate and
pending; its later independent correction is recorded below without rewriting the original #360 report.
The initial failed replay and later verifier failures remain original failures, not relabeled evidence.
Do not refile this root cause or claim every archived file now has an integrity pin. Plain Git honors attributes
but does not enforce the three pins; use the actual repository gate. No hosted CI or Windows execution is claimed.

## Wrapper checkout line-ending policy — existing #223 approved

The separate pre-existing [#223](https://github.com/p2pKit/P2pKit/issues/223) was freshly reproduced with actual
isolated Linux Git checkouts: `autocrlf=true` converts the unpinned POSIX launcher to 248 CR bytes, and the real
unchanged checker rejects its checksum; false/input and the batch launcher remain LF. This was a Low checkout/
developer-experience defect, not demonstrated tampering, a production defect or a newly filed audit finding.

The exact two-file correction is independently approved/pushed at `8dd65ce3f4e8f0274c24d09a667b11c653d9eb4b`;
see [the safe report](repairs/223.md) and
[verified outcome](https://github.com/p2pKit/P2pKit/issues/223#issuecomment-5585231528). Explicit `gradlew text eol=lf`
and real checkout regressions preserve wrappers/pins, batch/ABI/archive rules and all four old tamper controls.
Thirteen final static/policy/range gates pass; original-attributes rejection and two attribute mutations remain
meaningful negative evidence. No product Gradle check or native Windows/macOS acceptance follows from this cycle.
Do not refile this cause, blanket-renormalize existing clones, or reinterpret the unchanged #360 report's historical
pending note as current. Active hosted-facility preparation remains private/unapproved/unexecuted here, with #268
only planned after any freshly reproduced prerequisites; no checkpoint stop or whole-audit readiness is implied.

## Resumed corroboration: confirmed and filed #361–#368

These current findings were independently checked against source/callers and the full issue corpus before filing.
#361–#366 are **pending repairs**; #367/#368 have bounded source approvals below. Neither
investigation nor those approvals establish device/external acceptance. See full GitHub bodies and
[issue records](issues.json); do not duplicate them as still-unfiled suspicions.

- [#361](https://github.com/p2pKit/P2pKit/issues/361): Android hotspot error-reason decoder assumes 0–3 while real
  SDK constants are 1–4. Forwarded codes, typed failure and lifecycle remain; fresh manager/message regressions are pending.
- [#362](https://github.com/p2pKit/P2pKit/issues/362): initializer KDoc incorrectly promises an in-memory legacy
  fallback under authenticated defaults. Runtime correctly fails closed; fix prose, not security behavior.
- [#363](https://github.com/p2pKit/P2pKit/issues/363): iOS consent section is hidden for a pending first offer with
  no transfer history. Preserve explicit consent; actual rendered/simulator verification has not been performed.
- [#364](https://github.com/p2pKit/P2pKit/issues/364): interoperability catalog confuses explicit whole-kit security
  profile selection with later optional feature intersection. Source/caller confirmation is not the #133 campaign.
- [#365](https://github.com/p2pKit/P2pKit/issues/365): iOS catalog requests a bare fingerprint where the current
  sample requires a full trusted same-AppId pairing QR. Preserve parser/pins and scoped-IPv6 acceptance coverage.
- [#366](https://github.com/p2pKit/P2pKit/issues/366): Android URI KDoc recommends a JVM-only `sendFile(File)`
  overload absent from that artifact. Source-set/API contradiction, not an executed compilation/device failure.
- [#367](https://github.com/p2pKit/P2pKit/issues/367): the five missing Native/AAPT2 supported-host records
  were confirmed from #145's strict Linux failures, then independently curated and source-repaired at
  `0d88be3`; see [the approved report](repairs/367.md). Independent host-policy regressions and the actual
  851-test/sample/Dokka affected command pass. Its original full checks fail on distinct #368; old #145
  failures remain. Windows/Intel acceptance is NOT_EXECUTED, not discharged by source approval.
- [#368](https://github.com/p2pKit/P2pKit/issues/368): the API24 export-failure fixture blocks lowercase raw
  `test_…zip`, but the recorder/exporter uses normalized `TEST_…zip`. Original Linux checks fail; message-only
  instrumentation proves the exporter succeeded at the other path, then was restored. This is not an
  exporter `IllegalStateException`, security defect or assumed flake. Filed/refetched 10:50:42 UTC after
  duplicate checks; now independently APPROVED/pushed at `c221d54`, with [report](repairs/368.md) and
  [verified outcome](https://github.com/p2pKit/P2pKit/issues/368#issuecomment-5584672507). Summary-derived
  obstacle/exact-string guard preserve and strengthen assertions without production/skip/timeout changes.
  Focused10PASS; combined and separate whole checks eachPASS1607/199XML (234/194tasks), including
  diagnostics110. Original full/diagnostic failures, first368uppercase-oracle FAIL9+1 and intended
  exact-name mutation failure/restoration remain preserved. Host evidence is not ART/device/foreign-host acceptance.

The original private #364/#365 drafts retain their discovery-time NOT_FILED status; the verified publication above
supersedes that historical state without rewriting it. Their source inspection does not complete any physical or
independent interoperability requirement. GitHub Actions may now supply supported Mac/Windows/Apple gates under
serialized root ownership, but no such new gate results are established by these notes.

## #145 stronger original claims and current approval boundary

[#145](repairs/145.md) is independently approved/pushed at `0423e96e15c894c26a7d45a5dfb2a012e0c1ba8e`;
[verified outcome](https://github.com/p2pKit/P2pKit/issues/145#issuecomment-5582924265). Do not refile the fixed
measurement-copy/policy-unit cause. The estimator is a bounded retention-policy estimate, not measured universal
Native heap bounds, literal zero allocation or constant-time metadata processing. Both original caps bounded growth;
Binary under-reporting was already refuted. Preserve deliberate ownership copies and 0.8.0+ admission restrictions.
The JVM allocation probe establishes removal of payload-size scaling in the estimator only. Future measured Native
heap/allocation claims require their own target-specific evidence; this limitation is not a new confirmed defect.
The original #145 failed strict commands remain historical failures. #367 later passes its affected
851-test/sample/Dokka slice, while its original full checks fail on #368. Later #368 Linux passes are
separately recorded, not a relabeling of those failures or whole-audit/foreign-host/external readiness.
The original #145/#367 reports remain unchanged.

## Validation evidence-recipe suspicions — unconfirmed

- **Checksum-manifest self-inclusion:** the catalog's `find "$EVIDENCE" ... > "$EVIDENCE/sha256sums.txt"` recipe
  may enumerate the manifest created/truncated by its own redirection. The root owns a bounded synthetic reproduction;
  none was executed by the documentation investigator. If confirmed, duplicate-check the underlying cause and retain
  hashing of all other evidence, using manifest exclusion or outside-tree staging rather than dropping verification.
- **Apple log source:** plain macOS `log stream` in the Apple handbook/catalog may collect host rather than physical
  device logs. Verify actual forwarding/Console behavior on a supported host before alleging a defect; no Mac run here.
- **Private/shareable identity fields:** serial/UDID result lines may be intended for private raw evidence, whereas
  the evidence schema forbids publishing those values. Establish the intended boundary before claiming a leak.
- **SecurityConfig wording:** cryptographic preparation may use a shorthand for the DSL builder rather than a literal
  public type. Trace the current entry point before filing an API/documentation finding.

These suspicions are not included in the 182-row denominator or counted as repairs. Preserve historical/private raw
artifacts, full external acceptance criteria and protected files while investigating; do not manufacture device,
network, independent-implementation or professional-cryptography results from source inspection.

## Administrative dependency-token correction, not a product defect

#240's curated dependency list previously contained `0`. Its full historical issue body says
`transport #0` twice, referring to the zero-indexed first transport, not a GitHub issue. Only
that extraction error is corrected. Original source/body, all real dependencies, severity, pending
status and repair denominator are otherwise unchanged; no new GitHub defect or #240 fix is claimed.
