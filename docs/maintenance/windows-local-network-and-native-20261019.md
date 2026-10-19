# Windows LAN integration and native execution checkpoint

**NOT_READY. Host startup now works on the tested Windows machine; complete
Windows Host/Client and lifecycle qualification remain unfinished.**

See the later [Windows/Android handoff](windows-android-rpc-handoff-20261019.md)
for installed source `643988b2`, the Android Host repair and the owner's successful
manual testing. The exact-source results and failures below remain preserved.

This continuation was limited by the owner to Windows implementation and local
checks, followed by manual application testing. No GitHub Actions or other-platform
checks were run. Earlier failures and evidence remain preserved.

## Source and implementation

Branch: `work/windows-rpc-completion-20261018`. Starting source was
`dfdf1f248f816be3d40990dc2f772482db2f6bf6`, tree
`1f3d6becaa9ee87aafcf0a1618f58975513e1bd2`, clean. The final installed implementation
is `2d9f3f38df3e0fab2a60650ea8de7b9e4c460da3`, tree
`587732aa220ab2a5a2922db1975ce580b1d7c037`. Later documentation commits do not change
that binary's source. All continuation commits are local pending independent review.

| Commit | Change |
| --- | --- |
| `185bdbd08301e0a1b7c0fb577659588f128d3cd6` | Original Windows IP-interface observation before LAN selection |
| `d280579e65af369693dda541b16ea8b8ddb449a1` | Fixed native selections in the existing canonical supervisor |
| `89b12b26ecdec0f23184a4b5bf972bf6cb632838` | Observer-stage and native-argument regression corrections |
| `59eacd6e2f09cd98aa400a2f15ce3cb34c40fdc1` | Real cross-process native custody controls |
| `64df898c87373f80ac93a3c48e02492c1633003d` | Exact packaged observer-class inventory |
| `e42df0bc844f58c138d364a0a2c5b3b9901190e2` | Bounded original IP-observer failure reporting |
| `58266a97603994f28929c076c0937ff97dfb4451` | Continue retained module ownership after acquisition completes |
| `2d9f3f38df3e0fab2a60650ea8de7b9e4c460da3` | Fixed-vocabulary UI-stage timing diagnostics |

The original LAN refusal counted twelve link-only interfaces as competing IP
interfaces. The named JDK21 loader now retains the originally verified system
`iphlpapi.dll`, verifies resolved callable addresses and providers, and observes
`GetIpInterfaceTable` before and after complete Java interface enumeration. It
omits an interface only when both observations prove no IP binding and Java
reports no addresses or prefixes. Genuine multiple eligible LANs still refuse.
Native errors, inconsistent topology, unknown ownership and unsupported flags
remain failures. There is no environment-selected interface or first-peer fallback.

The IP observer retains process-lifetime callable custody; Stop does not unload
the module. Its completed-owner handoff preserves the sealed acquisition stage,
original bootstrap/requester identity, thread ownership and retained export/ACL
graph. JNI capabilities, qualification flags and protected-storage policies were
not inflated. MainKt, MSI identity/version, sample sections, Java17 bytecode,
the pinned JDK21 supplier, `jdk.unsupported` and named preview/native-access scope
remain intact.

## Actual environment and native controls

Actual assistant/tool tokens and threads were checked before protected execution:
native AMD64 Windows11 Home Single Language 25H2, build 26200.9168; initialized
ordinary local account, matching primary-token owner, normal interactive console
logon, no administrator SID, filtered/elevated token, service identity or thread
impersonation. LocalAppData and workspace are fixed NTFS. Startup overrides,
concurrent application work and unsafe installed metadata were refused.

The owner explicitly authorized archiving synthetic data and reusing the account.
The application profile and each native fixture were moved intact into separate
retained directories, with file identities, contents and ACLs checked unchanged.
Every native invocation began with an absent P2pKit entry. No failed fixture was
deleted, repaired or promoted to an application profile.

The maintained MSVC/SDK recipe compiled the cross-process smoke. The fixed adapter
retained original executable custody, atomic job admission, bounded output,
watchdogs, process/descendant observation and the original 30000ms outer budget.

| Actual native invocation | Source / observed result / receipt SHA-256 |
| --- | --- |
| Custody | `89b12b26`; PASS, 479 assertion lines, 5 process witnesses; `ff8161547e619e567691d53b78955cf3ac2e58c7a754fca17ad89002626db9ab` |
| Cold session reopen | `89b12b26`; PASS, 90 assertion lines, 5 witnesses; `6c95dbdb64f9c0184d64018fbb3102de0312808457935207ac47c1ea8b7f3416` |
| Custody with cross-process contention | `59eacd6e`; PASS, 483 assertion lines, 9 witnesses; `3c17714c290954d5af2944034a09b60610bcd8d80f9651892bd6a6042f374269` |

All three payloads and enclosing drivers exited0; captures and enclosing cleanup
were observed complete. Assertion lines are not distinct test counts. The first
two used EXE SHA-256 `ad57f8c430868f706fb8e532c8636096679311fd2f7f93196ed298e32c450da3`:
its original build was dirty, and every consumed input was independently rebound
unchanged to the named source. The cross-process EXE SHA-256 is
`2ba061488675526ad288823d740ca96b01c4b6fa0bf7950a21b9356ffe8e7a94`.

The cross-process checks observe a genuine sharing violation while custody is
held, successful acquisition after retirement, and unchanged original identities.
Cold reopen is orderly same-process native-session reopen, not encrypted process
restart, interruption recovery or power-loss durability. Receipts remain candidates
requiring the enclosing driver's observed exit; the tool observed exit0. No separate
terminal original-driver-handle receipt or stronger finalization claim was invented.

## Installed results and artifact bindings

The canonical local `:p2p-sample-desktop-ui:packageMsi` task produced each MSI with
the diagnostic preview-adapter packaging option. That option supplies no provider
authority. Normal UAC uninstall/install transitions preserved package identity;
all 224 installed files and 68 runtime DLLs matched their independently verified
package/supplier. No shared-folder permissions or security policies changed.

| Final installed object at `2d9f3f38` | SHA-256 |
| --- | --- |
| MSI, 114298880 bytes | `f252a102183673652a46f2a309cb13dc2b9960ba2c15281b0969fc8f6bb5831a` |
| 224-file installed inventory | `cef0e8b9015076200c34b2ca07b0d9767da19192320f6703405378cdb20d4d20` |
| Native DLL, 193536 bytes | `4597defae59a0a0746363063ea88babc1bd94cd1e6f41d9dae0f750851254092` |
| Loader adapter JAR | `847a645fcde9a6036d17a8f72d5ab158fc233e95198359b66b7b18aced069d90` |
| Reused Temurin21.0.12.1+1 supplier archive | `f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e` |

| Supervised installed operation | Source / result / receipt SHA-256 |
| --- | --- |
| Admission | `58266a97`; PASS; `5318fd147ebd829795d9583194226eddfec509b7a786a5efc9702f23dbdf77f7` |
| Fresh encrypted profile creation | `58266a97`; PASS; `c24360c275358f48a1b4b9007a8b718ecf71ca978c38b9975be884cdae99ca08` |
| Separate-process encrypted reopen | `58266a97`; PASS; `96c68ebc201cce24bce830f6a58f2c6c299e27e1a634408dd8f55cb43b6c6e13` |
| Wrong-password refusal and valid reopen | `58266a97`; PASS; `e2a8137f0284fbe52b4b258cacf16d51137a9b4d25f66e3d893ab0041d68318f` |
| UI cycle, first attempt | `58266a97`; FAIL at Host restart after lost focus; `8151785089af69046101d0a07623ef4b14608e179f50eb3751389905aa11f83a` |
| UI cycle, controlled repeat | `58266a97`; FAIL at Back; `3c04290f71be9f1f872aeaa34a25fdcacce33dbbbf9e012a6fd9ac3c42c22410` |
| Admission | `2d9f3f38`; PASS; `313a3c77ed49e5e026cfb6b750736237bae94446fa25ad555d4f36a706b92e29` |
| Instrumented UI cycle | `2d9f3f38`; FAIL at Back, subordinate deadline; `3c68403982e3bfc824649670f0a62292b0f7849fefacaa6d34d07662d820ff7f` |

The productive controls entered the actual JNI provider and exercised encrypted
record read/replace/delete, close and reopen. Wrong-password authentication failed
without changing encrypted contents. The later UI control also verified the
existing encrypted fixture before opening the canonical application window.

The instrumented UI reached navigation at1638ms, unlock at2046ms, Host startup
at2122ms, Stop at2827ms, second Host at6871ms and Back at7050ms. Both Hosts reached
Ready and retained the same fingerprint. The original ten-second UI deadline
expired at10017ms during Back cleanup. The application then exited0 normally;
the driver correctly returned1. Six process witnesses, captures and enclosing
cleanup were retired. This is not an accepted complete lifecycle cycle, and no
deadline was extended. Further lifecycle engineering/qualification remains required.

## Local verification and preserved failures

The checked-in wrapper, declared toolchains and strict dependency verification
were used with `--continue --rerun-tasks --no-build-cache --no-daemon --max-workers=2`.
Four contribution shell checks passed: layout, OSV lockfile coverage, Markdown
links and release metadata. Gradle was stopped after every completed gate.

- Complete affected Windows JVM suites passed: core875, RPC75, LAN309, sampleRPC611
  and Desktop71 (1941 total, no failures/errors/skips). These are bound to their
  individual implementation checkpoints, not one new cross-platform gate.
- The complete sampleRPC/loader/package gate passed at `58266a97`. The affected
  Desktop suite, loader and canonical MSI build passed at `2d9f3f38`.
- SDK layout compilation checked the actual 168-byte IP row and its field offsets.
  Parser, ownership and bridge regressions passed, including completed-owner refusal
  controls. The exact package-inventory suite passed all50 tests.
- Canonical supervisor controls passed: 28 Python core, 9 driver, 3 native-adapter,
  C#8 valid/54 refusal controls, and all six harmless actual Windows controls.
- All16 prior MSVC memory-only policy programs passed; their consumed source bytes
  were rechecked unchanged. Original dirty-build history remains recorded.

Preserved development failures include the initial SDK offset assertion, loader-stage
regression, native-adapter preparation refusals before payload, missing exact adapter
classes, and MSI logging error1622 before uninstall. Installed `89b12b26` admission
failed without a useful stage; `e42df0bc` then identified `IP_OBSERVER_MODULE`.
The completed-owner fix at `58266a97` passed real admission. None of those failures
was erased or reclassified. Earlier Apple ABI failure/baseline and original CI evidence
are untouched; no new cross-platform or GitHub Actions result is claimed.

## Remaining campaign work

| Case | Current status and remaining scope |
| --- | --- |
| W01 | BLOCKED / partial: actual positive Standard-user admission; full negative token matrix outstanding |
| W02 | BLOCKED / partial: real installed load/import/JNI admission passes; complete pre-execution refusal matrix outstanding |
| W03 | BLOCKED / partial: genuine productive JNI/profile operations; full bounds/races/lifecycle matrix outstanding |
| W04 | BLOCKED / partial: real custody and unsafe-DACL control pass; complete hostile path/ACL/reparse matrix outstanding |
| W05 | BLOCKED / partial: composed operations and actual cross-process contention pass; fault/uncertainty matrix outstanding |
| W06 | BLOCKED / partial: fresh encrypted creation, process reopen and wrong-password refusal pass; tamper/interruption/recovery outstanding |
| W07 | BLOCKED / partial: observed normal retirement; full cancellation/race/uncertain-cleanup qualification outstanding |
| W08 | BLOCKED / partial: original LAN refusal resolved and two real Host starts observed; two-device pairing/RPC/typed errors outstanding |
| W09 | BLOCKED: no qualified peer persistence, revocation or safe reconnect result |
| W10 | FAIL: zero fully accepted UI cycles; Back deadline failure, twenty-cycle and resource/interruption matrix outstanding |
| W11 | BLOCKED / partial: source/build/MSI/runtime bindings complete for named results; no complete qualified matrix |

Manual user testing is not an automated qualification result. Compare fingerprints
explicitly on both approved devices; never auto-select a discovered peer or replay
requests. The existing Android build and its older source binding remain separate.
Keep raw evidence, retained fixtures and device/account identities private. Review
and integrate the isolated commits without merging, tagging, signing or publishing.

See the [preceding Windows report](windows-rpc-completion-20261018.md),
[native supervisor contract](windows-native-smoke-supervision.md) and
[installed UI control](windows-installed-ui-control.md). Windows Host/Client is not
yet qualified; the verdict remains **NOT_READY**.
