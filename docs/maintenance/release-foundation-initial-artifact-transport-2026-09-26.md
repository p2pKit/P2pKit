# Initial-recipient artifact transport: source and offline models

## Four-member stored-ZIP byte leaf (later independent increment)

`scripts/hosted_initial_artifact_zip.py` now supplies the deterministic,
demand-driven four-member byte stream required by the future native caller.
It does not open files, authenticate a runner, or establish native retirement.
The complete ZIP, including framing, is bounded by the existing downstream
512 MiB limit; the backend's 576 MiB ciphertext capacity cannot override it.

Exact reviewed source SHA-256:
`8b4d4c31bf0d727f8be0a8f816bb747e484f084bb5efdc3bc48d6a6ba0bc9723`.
The sixteen-control test source SHA-256 is
`0c103032106192d94a171e9289619afdcf1ae0734759d89656398d65f51bdb71`.
Independent source review: `APPROVE_EXACT_STORED_ZIP_SOURCE_AND_16_AUTHORED_CONTROLS_ONLY`,
report SHA-256 `e1f45081771be029180572ccaa61dc67812b714665f38aba281aad5fe899e957`.

On 2026-09-26 at 21:45:39Z, one actual
`python3 -I -B -S scripts/tests/hosted-initial-artifact-zip-test.py -v`
invocation passed **16/16**, exit 0. External execution bounds were CPU60s,
wall120s/kill5s and address space512MiB; the controls used small in-memory
fixtures, not a full-capacity allocation. Whole-command timing was
wall0.093s/user0.080s/system0.012s. Source hashes matched before and after.
Log SHA-256: `e04f5aa7b7dbba948ed9f9adabf5d6199e6d290e8e104d2622e164192b16e971`.
An earlier launch failed at argument parsing (exit2, **zero tests**) because
`-f` duplicated the source's fixed `failfast=True`; only that redundant option
was removed. Its original log is preserved, SHA-256
`d71ef7d48bd4841d031c30a4604b5babb1dcdd467644f90452eb68e6bac32a0c`.

Independent result: `APPROVE_EXACT_16_LOCAL_BYTE_CONTROLS_RESULT_ONLY`, report
SHA-256 `b1b6a9298200f69deefeb886630374ca9c2ee867a86a85152f8b011d455037d6`.
Native K/U/A connection, actual service delivery/retention and hosted
qualification remain outstanding. No accepted transport/reader/preview suite
was rerun for this leaf. All original HOLDs and release gates remain.

## Earlier bounded transport increment

Status: **REVIEWED_SOURCE / OFFLINE_MODELS_PASS / NOT_WORKFLOW_WIRED**.
This is not provider, native-file, custody, retention or hosted qualification.
No initial-recipient authorization, ordinary HOLD or Release gate is lifted.

## Exact implementation

- Source commit: `9c45a6b84ca9db54442f1b9295c6dee1316a5579`.
- Tree: `a4fa2286aaea799a73f4def42844a2f6ce2f1395`.
- Main-based Foundation parent: `b52af2e7cc913b62aa30e980579120f74673d5a2`.

| File | SHA-256 |
| --- | --- |
| `scripts/hosted-initial-artifact-transport.cjs` | `a38f83914680395cf53a6de974a4530432d881ae6d5858103865ab2dbf26ed11` |
| `scripts/tests/hosted-initial-artifact-transport-test.cjs` | `6a2ba78a465db8bc2c79355c1ace73c39fad7f4d54edaaebb396ba2b4ef834ca` |

The bounded module consumes one supplied original byte stream. It creates an
Actions artifact, transfers sequential 8 MiB blocks, commits the exact
Uncommitted block list and finalizes with the observed whole-ZIP hash. It has
no Action, CLI, workflow caller, path/glob acquisition or native owner.

The caller must supply genuine current authority, the owned four-member ZIP,
explicit service credentials and conservatively mapped original absolute
deadlines. The transport retains the original 60-second total cap with the
last five seconds reserved for closure. It does not retry, follow redirects,
overwrite a committed blob, delete an artifact, or infer retirement from EOF.
It requests 14 days of retention; actual service expiry and service digest
remain explicitly unobserved until independently acquired.

The independent source review found a demand/backpressure defect before
execution: a readable listener or positive-size read could prefetch before
Create or during a pending upload. The repair requires an empty HWM0 original
stream, passive initial lifecycle listeners, size-less reads, an on-demand
one-shot readable listener, immediate owned copies and bounded block assembly.
The reviewed synchronous/asynchronous controls observe actual producer reads.

Independent source verdict:
`APPROVE_EXACT_TRANSPORT_SOURCE_AND_OFFLINE_MODEL_EXECUTION_ONLY`.
Review report SHA-256:
`7332122ff9dbc9f2bc9ff2d8f06a1452d69e7fe138aa71741cf4cb821d60f3b2`.

## Executed result

One actual serial model invocation passed **78/78**, exit **0**, on
2026-09-26, 19:19:06Z–19:19:07Z. The runner stops at the first failing assertion.
The complete original log has one guard entry, 78 distinct named PASS rows and
one explicit offline-only aggregate. No earlier reader or other suite was run.

The post-PAM guard verified UID/GID65534 and inherited hard limits before
same-PID Node exec: CPU60s, address space768MiB, file size16MiB, descriptors128,
processes32 and core0. The outer wall90s/kill5s timeout also covered runuser/PAM.
Whole-chain Bash timing was **0.995s wall / 0.693s user / 0.313s system**.
This is not Node-only self CPU or native transport performance.
The guard's PID14979 completed and was independently observed absent.
The frozen inputs and empty restricted HOME/TMP were verified unchanged.

Installed Node executable SHA-256:
`89af8424dd53e560b1933f87ba650d8bf57c83ca5a04600eefb31f416aabbae7`.
There is no Node RETURN/runtime-version observation. Jitless does not establish
that compiled WebAssembly support is disabled. No network-namespace isolation
is claimed; the reviewed closed fake import roster makes these models offline.

| Successful original | SHA-256 |
| --- | --- |
| `controls.log` | `73984372740e32fb75e680c3f47448e2711e240ccc7a60441c1846c81367037c` |
| `controls.time` | `a8b527d0b78d51e978a31a39bb9eb2824f3a61d499af3d03ec17425ab04a5865` |
| `controls.exit` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `results.sha256` | `ec69a2ed178da78f3e2becf641e59b1ad8024d1fa0282172a7f1a571db3d87c0` |

The restricted original packet is
`initial-artifact-models-9c45a6b8-wrapper3-20260926.nI6poX` under the existing
private resume-evidence root. Public records retain identities/hashes, not raw
private originals, service credentials, signed URLs or key material.

Independent actual-result verdict:
`PASS_78_OF_78_LOCAL_OFFLINE_TRANSPORT_MODELS_ONLY`.
Review report SHA-256:
`eab7cc712287fa10ce6b7f537bba1eb387133859d91785d933b9f7fa822e7cea`.
The reviewer inspected originals and source; it did not rerun the models.

## Startup failures retained separately

Two earlier consumed packets failed before any model executed. They are not
hidden, aggregated into the pass, or described as successful model invocations.

1. `initial-artifact-models-9c45a6b8-20260926.TtCqby`: absent `/usr/bin/time`,
   exit127 before Python/Node entry. The timing file is absent and the result
   manifest is partial because the launcher also tried to hash that absent
   file. Log SHA-256:
   `9e445dc4a6d24e53e93127402618a278aa63dcdba82cb67802731aa66d6c4c93`.
2. `initial-artifact-models-9c45a6b8-wrapper2-20260926.RIRV8G`: the guard passed,
   then the installed Node rejected unsupported `--no-expose-wasm`, exit9,
   before model loading. PID14109 was observed absent. Log SHA-256:
   `7998bfe07a288f1f97a943a922914dad6dcf55471548b3f328977386389226c3`.

Inspection of the actual installed tools and existing same-binary option
evidence supported separate frozen wrapper corrections: Bash built-in timing
and removal of that unsupported flag only. Source, models, assertions and all
resource ceilings were unchanged. An additional tool request with a mistyped
working directory was rejected before process creation; it was not a model run.
The independent report preserves the failed packets' exact manifest hashes.

## Remaining acceptance

Real Readables and local hash/buffer/event utilities were exercised. HTTP,
sockets, service/token objects and transport clocks/timers were in-process
models. The result covers wire fields, bounded demand, owned bytes/digests,
negative responses, no retries/overwrites, exact artifact IDs, cancellation,
EOF/close and original deadline fences within that scope only.

Current BEFORE authority, the complete custody-tail capture/freeze/encryption,
owned four-member ZIP acquisition, actual Artifact service transport, AFTER
observations, native retirement and original retention/digest verification are
still required. No workflow is wired here. This does not qualify productive
bootstrap, ordinary FULL/Desktop, provider/cache, publication or recovery.
See the [Foundation runbook](../releasing/release-foundation.md).
