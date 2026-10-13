# Windows RPC deferral and release scope

**Execution scheduling: deferred post-release by the owner. Qualification: not passed.**
Track the disposable-machine setup, exact procedures, historical failures, owners and
acceptance checklist in [Windows qualification issue #462](https://github.com/p2pKit/P2pKit/issues/462),
assigned to the repository owner under **Post-0.8.0-rc1 Windows RPC qualification**.
No test runs against the owner's daily Windows profile are authorized by this document.

## Proposed shortest safe release scope

Subject to explicit owner/Foundation agreement on the changed capability matrix:

- Keep the optional JVM RPC library and other qualified platforms in scope. The library's
  JVM publication is not the sample-owned Windows native protected-profile provider.
- Leave Windows sample RPC Host/Client unavailable, without plaintext, in-memory identity,
  unsafe filesystem or loader fallback. Keep `IMPLEMENTED=false`, `QUALIFIED=false`, and
  the production loader refusing. Keep the unpublished JDK21-preview adapter opt-in **off**
  for a reduced-scope release; do not change published Java17 bytecode targets.
- Preserve the existing Windows application's identity, other sample sections, MainKt,
  canonical versioning and Foundation's single packaging/freeze/publication pipeline.
- Document Windows protected-profile RPC as unavailable, not experimental-but-qualified.
  The native custody implementation exists, but complete provider/secure-loader integration
  and actual runtime acceptance remain incomplete.
- Verify all included executable/native resources and their nonexecuting boundary. Default
  packaging still stages custody DLL/pin resources; disabling preview does not remove those
  inputs. Any removal belongs to a jointly reviewed package change, not a silent exclusion.

This is a **scope proposal**, not a waiver, readiness verdict, new release producer, or
permission to merge/tag/publish. Issue scheduling alone cannot change the agreed application
parity contract. Foundation must confirm the final supported capability and test matrix.

## Mandatory checks that deferral does not remove

The RPC contribution currently changes terminal shutdown for **every Windows application
window**, including non-RPC sample holders and workers. The
[terminal application-exit prerequisite](windows-profile-integration.md#terminal-application-exit-prerequisite)
therefore still requires actual Windows/installed-MSI lifetime validation even when protected
RPC is disabled. A build-image module probe or static MSI extraction is not that acceptance.

Retain ordinary MSI install/launch/navigation, existing functionality and complete shutdown
checks, included-runtime/byte inspection, all Foundation custody/provenance/freeze requirements,
and the general [release checklist](../releasing/checklist.md). If these applicable gates cannot
pass, the four-application release remains **NOT_READY**. A Maven-only release or omitting the
MSI needs a separately reviewed owner/Foundation release-contract decision; neither is done here.

The deferred feature must pass trusted first-load, protected NTFS, actual JNI/provider,
durability/recovery, authorization/revocation and installed RPC lifetime tests before a later
release enables it. An issue is not evidence of cleanup, cryptographic or storage correctness.

## JVM test applicability is not a runtime waiver

The normal `:p2p-sample-rpc:jvmTest` task includes:

| Executing host | Mandatory source directories |
| --- | --- |
| Linux / macOS | `src/commonTest`, `src/jvmTest`, `src/posixJvmTest/kotlin` |
| Windows | `src/commonTest`, `src/jvmTest`, `src/windowsJvmTest/kotlin` |

The 24 real POSIX filesystem methods remain required on Linux/macOS, with their assertions
preserved. Eight portable methods from mixed classes stay in `jvmTest`. Two actual-Windows
production refusal tests assert Windows context, rejection before any path access, password
clearing and absence of invented cleanup ownership. They do not impersonate a positive
protected-profile test. Unsupported test hosts fail registration rather than manufacture a pass.

The maintained source inventory and mutation controls live in
`scripts/tests/rpc-jvm-test-host-inventory.json` and
`scripts/tests/check-rpc-module-policy-test.py`, reached by the normal repository-layout gate.
The scoped Windows Actions command runs the **unfiltered applicable** JVM task, not the older
415-test selection. No ignored tests, assumptions, permissive storage or weaker assertions are
introduced. Actual host runs and their inventories must still be checked; source registration
alone is not execution evidence.
