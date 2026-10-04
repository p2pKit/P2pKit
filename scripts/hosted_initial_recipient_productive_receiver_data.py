"""Closed productive seal/BEFORE records, not source, owner or cache authority.

This module does not import a native controller or sample a clock.  In
particular, a parsed seal or a declared closed-file index cannot restore the
seal process, its recipient, an HTTP lease or a BEFORE result in another
process.  The receiver independently obtains all of those observations.
"""
from __future__ import annotations

import re

import hosted_initial_recipient_before as B
import hosted_initial_recipient_productive_custody_data as CD


O, D = CD.O, CD.D
NS, LIMIT, PUBLIC_LIMIT = CD.NS, CD.LIMIT, CD.PUBLIC_LIMIT
PROVENANCE = "FRESH_RECEIVER_READ_NOT_ORIGINAL_PRODUCER_PIN"
SEAL_CONTEXT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_SEAL_AUTHORITY_CONTEXT_V1"
BEFORE_CONTEXT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_BEFORE_AUTHORITY_CONTEXT_V1"
SEAL_CHILD_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_SEAL_AUTHORITY_PENDING_CHILD_CLOSE_V1"
BEFORE_CHILD_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_BEFORE_AUTHORITY_PENDING_CHILD_CLOSE_V1"
SEAL_ACK_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_SEAL_AUTHORITY_POST_CLOSE_ACK_V1"
BEFORE_ACK_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_BEFORE_AUTHORITY_POST_CLOSE_ACK_V1"
WINDOW_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_RECEIVER_AUTHORITY_WINDOW_V1"
DEADLINE_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_RECEIVER_DEADLINES_V1"
CLOSE_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_RECEIVER_PENDING_CLOSE_WRITER_V1"
INDEX_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_RECEIVER_ACTUAL280_CLOSED_RETURN_V1"
NATIVE_CLOSE_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_RECEIVER_NATIVE_OWNER_CLOSE_V1"
WRITER_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_RECEIVER_CLOSE_WRITER_KNOWN_RETURN_V1"
SEAL_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_SEAL_PENDING_ORIGINAL_STEP_RETURN_V1"
SEAL_OUTPUT_SCOPE = "INITIAL_RECIPIENT_PRODUCTIVE_SEAL_PENDING_ORIGINAL_STEP_RETURN_OUTPUT_V1"
AUTHORITY_CAP_FIELDS = CD.FINAL_AUTHORITY_CAP_FIELDS
AUTHORITY_CAP_FLAGS = CD.FINAL_AUTHORITY_CAP_FLAGS
OUTPUT_FIELDS = (
    "initialProductiveSealSha256", "initialProductiveSealEndNs", "initialProductiveSealClockRole",
    "initialProductiveSealClockDomain", "initialProductiveSealClockTicksPerSecond", "initialProductiveSealBootSha256",
)
OUTPUT_ENV = (
    "P2PKIT_INITIAL_PRODUCTIVE_SEAL_SHA256", "P2PKIT_INITIAL_PRODUCTIVE_SEAL_END_NS",
    "P2PKIT_INITIAL_PRODUCTIVE_SEAL_CLOCK_ROLE", "P2PKIT_INITIAL_PRODUCTIVE_SEAL_CLOCK_DOMAIN",
    "P2PKIT_INITIAL_PRODUCTIVE_SEAL_CLOCK_TICKS_PER_SECOND", "P2PKIT_INITIAL_PRODUCTIVE_SEAL_BOOT_SHA256",
)
COLLECT_CLAIMS = (
    *CD.EXPORT_CLAIMS, "P2PKIT_INITIAL_PRODUCTIVE_COLLECT_OUTCOME", "P2PKIT_INITIAL_PRODUCTIVE_COLLECT_CLOSE_SHA256",
)
SEAL_OUTCOME_ENV = "P2PKIT_INITIAL_PRODUCTIVE_SEAL_OUTCOME"
STEP_NAMES = (
    ("export", "P2pKit initial productive custody export"),
    ("collect", "P2pKit initial productive post-export custody"),
    ("seal", "P2pKit initial productive custody seal"),
    ("before", "P2pKit initial productive before-upload custody"),
    ("upload", "P2pKit initial productive custody upload"),
    ("after", "P2pKit initial productive after-upload custody"),
)
FINAL_INPUTS = (
    ("returned/context.json", PUBLIC_LIMIT), ("returned/crypto-child-result.json", LIMIT),
    *(("returned/" + name, maximum) for name, maximum in CD.CRYPTO_INPUTS),
    *(("returned/" + name, LIMIT) for name in CD.LATER_FILES),
    *(("returned/crypto-service/" + name,
       16384 if name == "stdout.log" else 65536 if name == "stderr.log" else LIMIT) for name in B.PHASE_FILES),
    ("export-output/manifest.json", PUBLIC_LIMIT), ("payload/copy-index.json", LIMIT),
)
DEADLINE_FIELDS = (
    "schema scope kind selection source github policySha256 originalProposalSha256 originalJobBasisNs clock "
    "originalBootDigest sealFirstNs sealEndNs uploadStartByNs uploadEndNs afterEndNs returnEndNs collectCloseSha256 "
    "manifestSha256 sealSha256 budgetAcceptance exportSaveAuthority"
)
WINDOW_FIELDS = (
    "schema scope edge clock originalBootDigest originalJobBasisNs originalProposalSha256 sealFirstNs sealEndNs "
    "authorityFirstNs authorityWorkEndNs authorityFinalEndNs budgetAcceptance exportSaveAuthority"
)
CONTEXT_FIELDS = (
    "schema scope edge kind root session job observed history originalProposal expectedMatch eventSha256 "
    "authorityWindow sourceReturnSha256 sourceReturnedNs inheritedContext directoryIdentity predecessor "
    "originalServiceJob inputCloseSha256 budgetAcceptance exportSaveAuthority"
)
PREDECESSOR_FIELDS = "exportTransferSha256 collectCloseSha256 manifestSha256 sealSha256 exportOutcome collectOutcome sealOutcome"
INDEX_FIELDS = (
    "schema scope edge root clock authorityContextSha256 requiredFiles files directories fileCount directoryCount "
    "totalBytes authorityCloseSha256 closeWriterReturn originalReadbackClose capture budgetAcceptance testAcceptance "
    "productiveAuthority cacheAuthority exportSaveAuthority"
)
CLOSE_FIELDS = (
    "schema scope edge contextSha256 authorityWindow predecessor inputCloseSha256 authority parentClose preCloseNs "
    "closedNs requiredFiles requiredFileCount otherFiles otherFilesCount otherFilesTotalBytes directories directoryCount "
    "originalReadbackClose self writerReturn originalStepOutcome liveRecipient capture upload testAcceptance "
    "productiveAuthority cacheAuthority budgetAcceptance exportSaveAuthority"
)
SEAL_FIELDS = (
    "schema scope edge kind selection source github policySha256 originalProposalSha256 originalJobBasisNs clock "
    "originalBootDigest sealFirstNs sealEndNs inputs inputClose authority authorityIndex authorityCloseOriginals "
    "ciphertext closedNs writerReturn originalStepOutcome testAcceptance productiveAuthority cacheAuthority "
    "budgetAcceptance exportSaveAuthority"
)


def require(value, reason):
    O.require(value, "INITIAL_PRODUCTIVE_RECEIVER_DATA_" + reason)


def _record(raw, fields, scope, maximum=LIMIT):
    value = CD.fields(CD.canonical(raw, maximum), fields)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == scope, "RECORD_SCOPE")
    CD.nonacceptance(value)
    return value


def _same(left, right, reason):
    require(O.encoded(left) == O.encoded(right), reason)


def _source(value):
    CD.fields(value, "commit tree")
    require(all(type(item) is str and re.fullmatch(r"[0-9a-f]{40}", item) for item in value.values()), "SOURCE")


def claims(value, *, before=False):
    require(type(before) is bool, "CLAIMS_EDGE")
    names = (*CD.FINAL_CLAIMS, *COLLECT_CLAIMS, *((SEAL_OUTCOME_ENV, *OUTPUT_ENV) if before else ()))
    CD.fields(value, names)
    for name in (*CD.FINAL_CLAIMS, *COLLECT_CLAIMS):
        if name.endswith("OUTCOME"):
            require(type(value[name]) is str and value[name] == "success", "ORIGINAL_STEP_REQUIRED")
        else:
            CD.sha(value[name])
    if before:
        require(value[SEAL_OUTCOME_ENV] == "success", "ORIGINAL_SEAL_STEP_REQUIRED")
        output_values(tuple((name, value[environment]) for name, environment in zip(OUTPUT_FIELDS, OUTPUT_ENV)))
    return value


def output_values(values):
    require(type(values) is tuple and len(values) == 6, "OUTPUT_TUPLE")
    for row, name in zip(values, OUTPUT_FIELDS):
        require(type(row) is tuple and len(row) == 2 and type(row[0]) is str and row[0] == name and
            type(row[1]) is str, "OUTPUT_SLOT")
    data = dict(values)
    CD.sha(data[OUTPUT_FIELDS[0]])
    CD.sha(data[OUTPUT_FIELDS[5]])
    for name in (OUTPUT_FIELDS[1], OUTPUT_FIELDS[4]):
        require(re.fullmatch(r"0|[1-9][0-9]{0,19}", data[name]), "OUTPUT_CANONICAL_INTEGER")
        CD.integer(int(data[name]), 1)
    O.clocks.validate_identity(O.clocks.ClockIdentity(data[OUTPUT_FIELDS[2]], data[OUTPUT_FIELDS[3]],
        int(data[OUTPUT_FIELDS[4]])))
    return values


def encode_output_values(values):
    return b"".join((name + "=" + item + "\n").encode("ascii") for name, item in output_values(values))


def step_rows(job, service_date, *, edge):
    """Same strict six-field/frontier rules as B, with a separate literal roster."""
    require(type(edge) is str and edge in ("seal", "before", "upload", "after") and
        type(job) is dict and type(service_date) is int and 0 < service_date <= 253402300799, "STEP_INPUT")
    began = O.wire.utc_epoch(job.get("started_at"))
    require(began <= service_date, "STEP_JOB_START")
    rows = job.get("steps")
    require(type(rows) is list and 0 < len(rows) <= 256, "STEP_COMPLETE_ARRAY")
    previous, seen, selected = 0, set(), {}
    for row in rows:
        CD.fields(row, B.STEP_FIELDS)
        name, number, status, conclusion = (row[key] for key in ("name", "number", "status", "conclusion"))
        require(type(name) is str and 0 < len(name) <= 256 and name not in seen and
            not any(ord(char) < 32 or ord(char) == 127 for char in name) and
            type(number) is int and previous < number <= 2147483647 and type(status) is str and
            status in ("queued", "in_progress", "completed"), "STEP_NAME_NUMBER_STATUS")
        previous = number
        seen.add(name)
        started, completed = row["started_at"], row["completed_at"]
        if status == "queued":
            require(conclusion is None and started is None and completed is None, "STEP_QUEUED")
        elif status == "in_progress":
            require(conclusion is None and completed is None and began <= O.wire.utc_epoch(started) <= service_date,
                "STEP_CURRENT")
        else:
            require(type(conclusion) is str and conclusion in B.CONCLUSIONS, "STEP_CONCLUSION")
            if started is None or completed is None:
                require(conclusion == "skipped" and started is None and completed is None, "STEP_MISSING_TIMES")
            else:
                require(began <= O.wire.utc_epoch(started) <= O.wire.utc_epoch(completed) <= service_date, "STEP_TIMES")
        for role, literal in STEP_NAMES:
            if name == literal:
                selected[role] = row
    require(set(selected) == {role for role, _name in STEP_NAMES}, "STEP_LITERAL_ROSTER")
    current_index = [role for role, _name in STEP_NAMES].index(edge)
    ordered = [selected[role] for role, _name in STEP_NAMES]
    require(all(row["status"] == "completed" and row["conclusion"] == "success" and
        type(row["started_at"]) is type(row["completed_at"]) is str for row in ordered[:current_index]) and
        ordered[current_index]["status"] == "in_progress" and
        all(row["status"] == "queued" for row in ordered[current_index + 1:]), "STEP_REQUIRED_FRONTIER")
    require([row["number"] for row in ordered] == sorted(row["number"] for row in ordered) and
        all(O.wire.utc_epoch(left["completed_at"]) <= O.wire.utc_epoch(right["started_at"])
            for left, right in zip(ordered[:current_index], ordered[1:current_index + 1])), "STEP_PREDECESSOR_ORDER")
    current = ordered[current_index]["number"]
    require(all(row["status"] == ("completed" if row["number"] < current else "queued") for row in rows
        if row["number"] != current), "STEP_UNIQUE_CURRENT")
    return tuple((role, dict(selected[role])) for role, _name in STEP_NAMES)


def final_bundle(raws):
    """Pure final24 joins.  The active caller separately checks current policy/native phase."""
    CD.fields(raws, tuple(name for name, _maximum in FINAL_INPUTS))
    require(len(FINAL_INPUTS) == 24, "FINAL24_LITERAL")
    for name, maximum in FINAL_INPUTS:
        require(type(raws[name]) is bytes and len(raws[name]) <= maximum and
            (raws[name] or name == "returned/crypto-service/stderr.log"), "FINAL_ORIGINAL_BOUND")
    context = CD.crypto_context(raws["returned/context.json"])
    aux = {name: raws["returned/" + name] for name, _maximum in CD.CRYPTO_INPUTS}
    for name, raw in aux.items():
        _same(context["inputs"][name], {"name": name, "bytes": len(raw), "sha256": O.digest(raw)}, "FINAL_INPUT_HASH")
    final, prior = CD.final_inputs(aux["final-inputs.json"]), CD.pre_index(aux["pre-export-copy-index.json"])
    manifest, index = CD.public_manifest(raws["export-output/manifest.json"]), CD.final_index(raws["payload/copy-index.json"])
    pre, pre_index = CD.authority_return(aux["authority-return.json"], post=False), CD.authority_index(aux["authority-index.json"], post=False)
    custody, transfer, post, post_index, collected = (
        CD.custody_return(raws["returned/" + CD.LATER_FILES[0]]),
        CD.export_transfer(raws["returned/" + CD.LATER_FILES[1]]),
        CD.authority_return(raws["returned/" + CD.LATER_FILES[2]], post=True),
        CD.authority_index(raws["returned/" + CD.LATER_FILES[3]], post=True),
        CD.collect_close(raws["returned/" + CD.LATER_FILES[4]]),
    )
    require(final["observed"] == context["observed"] and final["history"] == context["history"] and
        final["originalProposal"] == context["originalProposal"] and aux["original-match.json"] == aux["fresh-match.json"] and
        final["originalMatchSha256"] == final["freshMatchSha256"] == O.digest(aux["original-match.json"]) and
        manifest["source"] == final["observed"]["source"] and manifest["source"] == final["workerIdentity"]["source"] and
        manifest["selection"] == final["workerIdentity"]["selection"], "FINAL_SOURCE_IDENTITY")
    match = CD.canonical(aux["original-match.json"], PUBLIC_LIMIT)
    policy = CD.canonical(aux["candidate-policy.json"], 96 * 1024)
    _same(manifest["github"], {**match["github"], "repository": D.identity.I.REPOSITORY,
        "eventSha256": O.digest(aux["event.json"])}, "FINAL_PUBLIC_GITHUB")
    _same(manifest["policy"], {**match["policy"], "fingerprint": policy["recipient"]["fingerprint"],
        "keySha256": policy["recipient"]["sha256"], "expiresAt": policy["expiresAt"], "retentionDays": 14}, "FINAL_PUBLIC_POLICY")
    require(manifest["recipient"]["keySha256"] == O.digest(aux["recipient-public.asc"]) and
        final["sourceRecordsSha256"]["candidate_policy_raw"] == O.digest(aux["candidate-policy.json"]), "FINAL_PUBLIC_KEY_POLICY")
    require(final["preExportCopyIndexSha256"] == context["parent28Sha256"] == O.digest(aux["pre-export-copy-index.json"]) and
        context["finalInputsSha256"] == O.digest(aux["final-inputs.json"]) and
        final["preExportReturnSha256"] == prior["preExportReturnSha256"] == O.digest(aux["authority-return.json"]) and
        final["preExportIndexSha256"] == prior["preExportIndexSha256"] == O.digest(aux["authority-index.json"]) and
        final["prefixRetentionSha256"] == prior["prefixRetentionSha256"], "FINAL_PREDECESSOR_HASHES")
    require(pre["inventorySha256"] == O.digest(aux["authority-index.json"]) and
        pre["contextSha256"] == pre_index["contextSha256"] and pre["matchSha256"] == final["originalMatchSha256"] and
        pre["workerIdentitySha256"] == post["workerIdentitySha256"] == O.digest(O.encoded(final["workerIdentity"])) and
        pre["authorityWindow"]["originalProposalSha256"] == post["authorityWindow"]["originalProposalSha256"] ==
        manifest["productive"]["originalProposalSha256"] == O.digest(O.encoded(final["originalProposal"])), "FINAL_PRE_AUTHORITY")
    hashes = {"contextSha256": O.digest(raws["returned/context.json"]), "manifestSha256": O.digest(raws["export-output/manifest.json"]),
        "copyIndexSha256": O.digest(raws["payload/copy-index.json"]), "preExportReturnSha256": O.digest(aux["authority-return.json"]),
        "preExportIndexSha256": O.digest(aux["authority-index.json"]), "parent28Sha256": O.digest(aux["pre-export-copy-index.json"])}
    require(all(custody[name] == transfer[name] == checksum for name, checksum in hashes.items()) and
        all(collected[name] == checksum for name, checksum in hashes.items() if name not in ("contextSha256", "parent28Sha256")) and
        collected["custodyReturnSha256"] == transfer["custodyReturnSha256"] == O.digest(raws["returned/" + CD.LATER_FILES[0]]) and
        collected["exportTransferSha256"] == O.digest(raws["returned/" + CD.LATER_FILES[1]]) and
        collected["postExportReturnSha256"] == O.digest(raws["returned/" + CD.LATER_FILES[2]]) and
        collected["postExportIndexSha256"] == post["inventorySha256"] == O.digest(raws["returned/" + CD.LATER_FILES[3]]) and
        post["contextSha256"] == post_index["contextSha256"] and post["matchSha256"] == final["originalMatchSha256"], "FINAL_LATE5_HASHES")
    require(custody["startSha256"] == index["startSha256"] == O.digest(raws["returned/crypto-service/start.json"]) and
        custody["childSha256"] == O.digest(raws["returned/crypto-child-result.json"]) and
        custody["nativeRecordsSha256"] == {name: O.digest(raws["returned/crypto-service/" + name]) for name in B.PHASE_FILES} and
        index["contextSha256"] == hashes["contextSha256"] and index["parent28Sha256"] == hashes["parent28Sha256"] and
        custody["claims"] == final["claims"], "FINAL_NATIVE_ORIGINAL_HASHES")
    require(manifest["copy"]["groups"] == index["groups"] and
        manifest["copy"]["index"] == {"name": "copy-index.json", "bytes": len(raws["payload/copy-index.json"]),
            "sha256": hashes["copyIndexSha256"]} and manifest["copy"]["groups"][:28] == prior["groups"] and
        manifest["initialRecipient"]["preExportReturnSha256"] == hashes["preExportReturnSha256"] and
        manifest["initialRecipient"]["preExportIndexSha256"] == hashes["preExportIndexSha256"] and
        manifest["initialRecipient"]["matchSha256"] == final["originalMatchSha256"], "FINAL_INDEX_MANIFEST_JOIN")
    expected_pre = {name: final["claims"][key] for name, key in
        (("producerStepOutcome", "PRODUCER_OUTCOME"), ("producerHandoffSha256", "HANDOFF_SHA256"),
         ("producerReturnSha256", "PRODUCER_RETURN_SHA256"), ("afterSaveStepOutcome", "AFTER_SAVE_OUTCOME"),
         ("afterSaveSha256", "AFTER_SAVE_SHA256"), ("afterProbeStepOutcome", "AFTER_PROBE_OUTCOME"), ("probeSha256", "PROBE_SHA256"))}
    expected_pre["prefixRetentionSha256"] = final["prefixRetentionSha256"]
    _same(pre["predecessor"], expected_pre, "FINAL_ORIGINAL_PRODUCTIVE_STEPS")
    _same(manifest["productive"], {**expected_pre, "originalProposalSha256": O.digest(O.encoded(final["originalProposal"])),
        "compatibilityInputsSha256": final["compatibilityInputsSha256"]},
        "FINAL_PRODUCTIVE_MANIFEST")
    _same(post["predecessor"], {"step": "custody-export", "stepOutcome": "success",
        "exportTransferSha256": collected["exportTransferSha256"], "custodyReturnSha256": collected["custodyReturnSha256"],
        **{name: hashes[name] for name in ("manifestSha256", "copyIndexSha256", "preExportReturnSha256", "preExportIndexSha256")}},
        "FINAL_POST_AUTHORITY_PREDECESSOR")
    require(pre["closedNs"] == custody["authorityClosedNs"] <= custody["nativePhase"][0] < custody["returnedNs"] <=
        transfer["returnedNs"] <= post["authorityWindow"]["authorityFirstNs"] <= post["closedNs"] <= collected["returnedNs"],
        "FINAL_ORIGINAL_CHRONOLOGY")
    original_proposal(final["originalProposal"], final["history"], final["workerIdentity"])
    return context, final, manifest, index, custody, transfer, post, collected


def bind_claims(raws, values, *, before=False):
    values = claims(values, before=before)
    result = final_bundle(raws)
    require({name: values[name] for name in CD.FINAL_CLAIMS} == result[1]["claims"] and
        values[CD.EXPORT_CLAIMS[1]] == O.digest(raws["returned/" + CD.LATER_FILES[1]]) and
        values[CD.EXPORT_CLAIMS[2]] == O.digest(raws["export-output/manifest.json"]) and
        values[COLLECT_CLAIMS[-1]] == O.digest(raws["returned/" + CD.LATER_FILES[4]]), "ORIGINAL_EXTERNAL_STEP_HASHES")
    return result


def _proposal(proposal, history):
    """Check immutable allocation arithmetic, not a new service-time estimate."""
    require(type(proposal) is dict and type(history) is dict and
        proposal.get("scope") == "INITIAL_RECIPIENT_BOOTSTRAP_ALLOCATION_PROPOSAL_V1" and
        proposal.get("budgetAcceptance") == "NOT_ADMITTED" and proposal.get("exportSaveAuthority") is False,
        "ORIGINAL_PROPOSAL_SCOPE")
    basis = CD.integer(history["originalJobBasisNs"], minimum=-O.clocks.UINT64)
    expected = D.allocation.fence_arithmetic(basis)
    require(proposal["serviceTimeBasis"]["jobStartBasisNs"] == basis and
        proposal["proposedJobEndNs"] == D.allocation.service_time.job_end_arithmetic(basis) and
        proposal["policy"] == D.allocation.policy() and all(proposal[key] == item for key, item in expected.items()),
        "ORIGINAL_PROPOSAL_ARITHMETIC")
    return expected["phaseFencesNs"]


def original_proposal(proposal, history, worker):
    """Full original allocation DATA, without constructing a worker capability.

    This is the byte-level equivalent of D.original_proposal's retained
    arithmetic. The live controller still proves its genuine current worker,
    original service responses, source, original job basis and native clock.
    """
    require(type(proposal) is type(history) is type(worker) is dict, "PROPOSAL_DATA_TYPES")
    worker_raw = O.encoded(worker)
    require(D.identity.cache_cohort(worker_raw) is not None, "PROPOSAL_WORKER_RECORD")
    CD.fields(history, D.HISTORY_FIELDS)
    require(type(history["schema"]) is int and history["schema"] == 1 and
        history["scope"] == "INITIAL_CUSTODY_PRIMARY_HISTORICAL_BINDING_V1" and history["kind"] == "worker" and
        history["currentAuthority"] == "NOT_ACQUIRED", "PROPOSAL_HISTORY_SCOPE")
    CD.nonacceptance(history)
    clock = O.wire.clock_identity(history["clock"])
    CD.sha(history["originalBootDigest"])
    first_use = worker["initialRecipient"]["firstUseAt"]
    require(type(history["firstUseAt"]) is int and history["firstUseAt"] == first_use and
        history["matchSha256"] == O.digest(O.encoded(worker["initialRecipient"])) and
        history["observed"]["source"] == worker["source"], "PROPOSAL_HISTORY_IDENTITY")
    basis = proposal.get("serviceTimeBasis")
    require(type(basis) is dict and type(basis.get("service")) is dict, "PROPOSAL_ORIGINAL_SERVICE")
    CD.job(basis.get("invocation"))
    service = basis["service"]
    shared = {"schema": 1, "profile": worker["profile"], "selection": worker["selection"],
        "cacheCohort": worker["cacheCohort"], "source": worker["source"], "github": worker["github"],
        "workerIdentitySha256": O.digest(worker_raw), "clock": O.clock_value(clock), "firstUseAt": first_use,
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    expected_basis = {**shared, "scope": "INITIAL_RECIPIENT_BOOTSTRAP_SERVICE_TIME_BASIS_V1",
        "invocation": basis["invocation"], "service": service, "policy": D.allocation.service_time.policy(),
        **D.allocation.service_time.basis_arithmetic(service["jobsRequestStartedNs"],
            O.wire.utc_epoch(service["jobStartedAt"]), service["originDateEpochSeconds"])}
    expected = {**shared, "scope": "INITIAL_RECIPIENT_BOOTSTRAP_ALLOCATION_PROPOSAL_V1",
        "serviceTimeBasis": expected_basis, "serviceTimeBasisSha256": O.digest(O.encoded(expected_basis)),
        "policy": D.allocation.policy(), **D.allocation.fence_arithmetic(expected_basis["jobStartBasisNs"]),
        "productiveOwner": "NOT_CREATED"}
    require(O.encoded(proposal) == O.encoded(expected) and
        expected_basis["jobStartBasisNs"] == CD.integer(history["originalJobBasisNs"], minimum=-O.clocks.UINT64),
        "PROPOSAL_EXACT_ORIGINAL_ARITHMETIC")
    return proposal


def authority_window(value):
    CD.fields(value, WINDOW_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == WINDOW_SCOPE and
        value["edge"] in ("seal", "before"), "AUTHORITY_WINDOW_SCOPE")
    CD.nonacceptance(value)
    O.wire.clock_identity(value["clock"])
    for name in ("originalBootDigest", "originalProposalSha256"):
        CD.sha(value[name])
    CD.integer(value["originalJobBasisNs"], minimum=-O.clocks.UINT64)
    for name in ("sealFirstNs", "sealEndNs", *AUTHORITY_CAP_FIELDS[:3]):
        CD.integer(value[name])
    require(value["originalJobBasisNs"] <= value["sealFirstNs"] <= value["authorityFirstNs"] <
        value["authorityWorkEndNs"] == value["authorityFinalEndNs"] == value["sealEndNs"] <= value["sealFirstNs"] + 120 * NS,
        "AUTHORITY_SAME_SEAL120")
    return value


def authority_context(raw, *, edge):
    require(edge in ("seal", "before"), "CONTEXT_EDGE")
    value = _record(raw, CONTEXT_FIELDS, SEAL_CONTEXT_SCOPE if edge == "seal" else BEFORE_CONTEXT_SCOPE)
    require(value["edge"] == edge and value["kind"] == "worker", "CONTEXT_KIND")
    window = authority_window(value["authorityWindow"])
    CD.job(value["job"])
    require(window["edge"] == edge and type(value["root"]) is type(value["session"]) is str and
        value["history"]["observed"] == value["observed"] and value["history"]["clock"] == window["clock"] and
        value["history"]["originalJobBasisNs"] == window["originalJobBasisNs"] and
        value["history"]["originalBootDigest"] == window["originalBootDigest"] and
        value["history"]["matchSha256"] == O.digest(O.encoded(value["expectedMatch"])) and
        value["history"]["currentAuthority"] == "NOT_ACQUIRED", "CONTEXT_ORIGINAL_HISTORY")
    ends = _proposal(value["originalProposal"], value["history"])
    require(O.digest(O.encoded(value["originalProposal"])) == window["originalProposalSha256"] and
        window["sealEndNs"] <= ends["separate-seal"] and
        window["authorityFirstNs"] <= CD.integer(value["sourceReturnedNs"]) < window["authorityWorkEndNs"],
        "CONTEXT_ORIGINAL_PHASE")
    for name in ("eventSha256", "sourceReturnSha256", "inputCloseSha256"):
        CD.sha(value[name])
    predecessor = CD.fields(value["predecessor"], PREDECESSOR_FIELDS)
    for name in ("exportTransferSha256", "collectCloseSha256", "manifestSha256"):
        CD.sha(predecessor[name])
    require(predecessor["exportOutcome"] == predecessor["collectOutcome"] == "success", "CONTEXT_PRIOR_STEPS")
    if edge == "before":
        CD.sha(predecessor["sealSha256"])
        require(predecessor["sealOutcome"] == "success", "CONTEXT_PRIOR_SEAL")
    else:
        require(predecessor["sealSha256"] is None and predecessor["sealOutcome"] == "NOT_OBSERVED", "CONTEXT_CURRENT_SEAL")
    D.native_identity(value["directoryIdentity"], O.wire.clock_identity(window["clock"]).role)
    require(type(value["inheritedContext"]) is dict and all(type(key) is type(item) is str for key, item in
        value["inheritedContext"].items()) and type(value["originalServiceJob"]) is list and
        len(value["originalServiceJob"]) == 4, "CONTEXT_NATIVE_ORIGINALS")
    return value


def deadline(raw, *, final=None, seal_raw=None):
    value = _record(raw, DEADLINE_FIELDS, DEADLINE_SCOPE, PUBLIC_LIMIT)
    require(value["kind"] == "worker" and type(value["selection"]) is str and type(value["github"]) is dict, "DEADLINE_IDENTITY")
    _source(value["source"])
    O.wire.clock_identity(value["clock"])
    for name in ("policySha256", "originalProposalSha256", "originalBootDigest", "collectCloseSha256", "manifestSha256", "sealSha256"):
        CD.sha(value[name])
    names = ("sealFirstNs", "sealEndNs", "uploadStartByNs", "uploadEndNs", "afterEndNs", "returnEndNs")
    numbers = (CD.integer(value["originalJobBasisNs"], minimum=-O.clocks.UINT64),
        *(CD.integer(value[name]) for name in names))
    require(numbers == tuple(sorted(numbers)) and value["sealFirstNs"] < value["sealEndNs"] <= value["sealFirstNs"] + 120 * NS,
        "DEADLINE_ORIGINAL_ORDER")
    require((final is None) is (seal_raw is None), "DEADLINE_JOIN_PAIR")
    if final is not None:
        require(type(final) is dict and type(seal_raw) is bytes, "DEADLINE_JOIN_TYPES")
        context, inputs, manifest, *_rest = final_bundle(final)
        seal = seal_record(seal_raw, final)
        ends = _proposal(inputs["originalProposal"], inputs["history"])
        expected = {name: seal[name] for name in ("selection", "source", "github", "policySha256", "originalProposalSha256",
            "originalJobBasisNs", "clock", "originalBootDigest", "sealFirstNs", "sealEndNs")}
        expected.update(uploadStartByNs=ends["upload-transition"], uploadEndNs=ends["evidence-upload"],
            afterEndNs=ends["upload-after-guard"], returnEndNs=ends["delivery-return"],
            collectCloseSha256=O.digest(final["returned/" + CD.LATER_FILES[4]]),
            manifestSha256=O.digest(final["export-output/manifest.json"]), sealSha256=O.digest(seal_raw))
        require(all(value[name] == item for name, item in expected.items()) and manifest["source"] == value["source"] and
            context["clock"] == value["clock"], "DEADLINE_ORIGINAL_JOIN")
    return value


def file_row(row):
    require(type(row) is tuple and len(row) == 6, "FILE_ROW")
    relative, raw, maximum, native, directory, provenance = row
    CD.relative(relative)
    require(type(raw) is bytes and 0 <= len(raw) <= CD.integer(maximum, 1, LIMIT) and provenance == PROVENANCE, "FILE_BYTES")
    CD.native(native, directory=False)
    CD.native(directory, directory=True)
    require(native[0] == directory[0] and native[6 if native[0] == "posix" else 4] == len(raw) and
        CD.native_key(native) != CD.native_key(directory), "FILE_NATIVE")
    return row


def file_observation(value):
    CD.fields(value, "relative maximum bytes sha256 native directoryNative provenance readerOrdinal retirement")
    CD.relative(value["relative"])
    maximum = CD.integer(value["maximum"], 1, LIMIT)
    size = CD.integer(value["bytes"], 0, maximum)
    CD.sha(value["sha256"])
    require(size or value["bytes"] == 0 and value["sha256"] == O.digest(b""), "FILE_EMPTY_HASH")
    CD.integer(value["readerOrdinal"])
    require(type(value["native"]) is type(value["directoryNative"]) is list and
        value["provenance"] == PROVENANCE and value["retirement"] == "KNOWN_READER_CLOSE", "FILE_OBSERVATION")
    native, directory = CD.native(tuple(value["native"]), directory=False), CD.native(tuple(value["directoryNative"]), directory=True)
    require(native[0] == directory[0] and native[6 if native[0] == "posix" else 4] == size and
        CD.native_key(native) != CD.native_key(directory), "FILE_OBSERVATION_NATIVE")
    return value


def file_metadata(native):
    """Projection of retained full native DATA, never a new file observation."""
    CD.native(native, directory=False)
    if native[0] == "posix":
        return {"device": native[1], "inode": native[2], "size": native[6], "mtime_ns": native[7], "ctime_ns": native[8]}
    return {"identity": list(native[1:3]), "is_directory": native[3], "size": native[4], "links": native[5],
        "attributes": native[6], "creation_100ns": native[7], "modified_100ns": native[8], "change_100ns": native[9],
        "owner_sid": native[10], "protected_dacl": native[11]}


def known_close(raw, *, native=False):
    require(type(native) is bool, "CLOSE_KIND")
    value = CD.fields(CD.canonical(raw), "schema scope resources retirement exportSaveAuthority")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] ==
        (NATIVE_CLOSE_SCOPE if native else "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1") and
        value["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and value["exportSaveAuthority"] is False and
        type(value["resources"]) is list and 0 < len(value["resources"]) <= CD.MAX_NODES, "KNOWN_CLOSE")
    for ordinal, row in enumerate(value["resources"]):
        CD.fields(row, "ordinal label closeAttempted closed")
        require(type(row["ordinal"]) is int and row["ordinal"] == ordinal and type(row["label"]) is str and
            row["label"] in ("directory", "reader", "writer", "embedded-reader", "stdout", "stderr", "native-scope") and
            row["closeAttempted"] is row["closed"] is True, "KNOWN_CLOSE_ROW")
    return value


def writer_return(value):
    CD.fields(value, "schema scope relative bytes sha256 preCloseWrite readback metadataPolicy ownerClose closedNs originalStepOutcome capture exportSaveAuthority")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == WRITER_SCOPE and
        value["relative"] == "authority-close.json" and value["originalStepOutcome"] == "NOT_OBSERVED" and
        value["capture"] == "NOT_K_CAPTURE" and value["exportSaveAuthority"] is False, "CLOSE_WRITER_SCOPE")
    CD.integer(value["closedNs"])
    CD.integer(value["bytes"], 1, LIMIT)
    CD.sha(value["sha256"])
    file_observation(value["readback"])
    require(value["readback"]["relative"] == value["relative"] and value["readback"]["bytes"] == value["bytes"] and
        value["readback"]["sha256"] == value["sha256"], "CLOSE_WRITER_READBACK")
    CD.fields(value["preCloseWrite"], "bytes sha256 metadata writerOrdinal observation retirement")
    written = value["preCloseWrite"]
    require(written["bytes"] == value["bytes"] and type(written["bytes"]) is int and written["sha256"] == value["sha256"] and
        written["observation"] == "PRE_CLOSE_WRITE_VERIFY" and written["retirement"] == "KNOWN_WRITER_CLOSE", "CLOSE_WRITER_ORIGINAL")
    close = known_close(O.encoded(value["ownerClose"]))
    writer, reader = CD.integer(written["writerOrdinal"]), value["readback"]["readerOrdinal"]
    require(writer != reader and writer < len(close["resources"]) and reader < len(close["resources"]) and
        close["resources"][writer]["label"] == "writer" and close["resources"][reader]["label"] == "reader", "CLOSE_WRITER_LEDGER")
    native = tuple(value["readback"]["native"])
    # The maintained comparison is identical for both POSIX roles. Choosing its
    # POSIX grammar here does not assert which platform observed these bytes.
    role = "windows-x64" if native[0] == "windows" else "linux-x64"
    require(value["metadataPolicy"] == B.write_close_metadata(role, written["metadata"], file_metadata(native), value["bytes"]),
        "CLOSE_WRITER_METADATA_POLICY")
    return value


def authority_index(raw, *, edge):
    value = _record(raw, INDEX_FIELDS, INDEX_SCOPE)
    require(value["edge"] == edge and edge in ("seal", "before") and type(value["root"]) is str and
        value["capture"] == "NOT_K_CAPTURE" and value["testAcceptance"] == "NOT_PERFORMED" and
        value["productiveAuthority"] is value["cacheAuthority"] is False, "INDEX_NONACCEPTANCE")
    clock = O.wire.clock_identity(value["clock"])
    CD.sha(value["authorityContextSha256"])
    CD.sha(value["authorityCloseSha256"])
    require(type(value["files"]) is type(value["directories"]) is type(value["requiredFiles"]) is list and
        type(value["fileCount"]) is int and value["fileCount"] == len(value["files"]) == len(value["requiredFiles"]) == 280 and
        type(value["directoryCount"]) is int and value["directoryCount"] == len(value["directories"]) == 58, "INDEX_COMPLETE_COUNTS")
    rows = [file_observation(row) for row in value["files"]]
    names = tuple(row["relative"] for row in rows)
    require(names == tuple(sorted(names)) == tuple(value["requiredFiles"]) and len(set(names)) == 280 and
        len({CD.native_key(tuple(row["native"])) for row in rows}) == 280, "INDEX_FILE_ORDER_ALIAS")
    ids = []
    for side, number in (("source-before", 12), ("acquisition-queries", 24), ("source-after", 12)):
        selected = tuple(sorted({name.split("/")[1][6:] for name in names if name.startswith(side + "/query-")}))
        require(len(selected) == number, "INDEX_QUERY_ROSTER")
        ids.append(selected)
    required, directories = B.member_grammar(*ids)
    require(names == required, "INDEX_REQUIRED280")
    seen, native_keys = [], []
    for row in value["directories"]:
        CD.fields(row, "relative path originalIdentity originalProvenance readbackNative")
        name = row["relative"]
        require(name == "." or CD.relative(name) == name, "INDEX_DIRECTORY")
        require(type(row["path"]) is str and row["path"].replace("\\", "/") ==
            value["root"].replace("\\", "/") + ("" if name == "." else "/" + name),
            "INDEX_FIXED_PATH")
        require(type(row["readbackNative"]) is list, "INDEX_DIRECTORY_VECTOR")
        pin = CD.native(tuple(row["readbackNative"]), directory=True)
        require(pin[0] == ("windows" if clock.role == "windows-x64" else "posix"), "INDEX_DIRECTORY_ROLE")
        if name in B.DIRECTORY_TARGETS:
            require(D.native_identity(row["originalIdentity"], clock.role) == pin[1:3] and
                row["originalProvenance"] == "ORIGINAL_AUTHORITY_NATIVE_PIN", "INDEX_ORIGINAL_PIN")
        else:
            require(row["originalIdentity"] is None and row["originalProvenance"] == "UNPINNED_ORIGINAL_DIRECTORY", "INDEX_NO_INVENTED_PIN")
        seen.append(name)
        native_keys.append(CD.native_key(pin))
    require(tuple(seen) == directories and len(set(native_keys)) == 58 and
        not set(native_keys).intersection(CD.native_key(tuple(row["native"])) for row in rows), "INDEX_DIRECTORY_ORDER_ALIAS")
    require(type(value["totalBytes"]) is int and value["totalBytes"] == sum(row["bytes"] for row in rows) <= CD.MAX_BYTES,
        "INDEX_TOTAL_BYTES")
    returned = writer_return(value["closeWriterReturn"])
    require(returned["sha256"] == value["authorityCloseSha256"] and returned["readback"] ==
        next(row for row in rows if row["relative"] == "authority-close.json"), "INDEX_REAL280TH")
    close = known_close(O.encoded(value["originalReadbackClose"]))
    reader_ordinals = [row["readerOrdinal"] for row in rows if row["relative"] != "authority-close.json"]
    require(len(set(reader_ordinals)) == 279 and all(number < len(close["resources"]) and
        close["resources"][number]["label"] == "reader" for number in reader_ordinals), "INDEX_ALL279_READER_CLOSES")
    return value


def authority_close(raw, *, edge):
    value = _record(raw, CLOSE_FIELDS, CLOSE_SCOPE)
    require(value["edge"] == edge and value["writerReturn"] == CD.PENDING and value["originalStepOutcome"] == "NOT_OBSERVED" and
        value["liveRecipient"] == "NOT_CREATED" and value["capture"] == "NOT_K_CAPTURE" and value["upload"] == "NOT_PERFORMED" and
        value["testAcceptance"] == "NOT_PERFORMED" and value["productiveAuthority"] is value["cacheAuthority"] is False,
        "CLOSE_PENDING_NOT_SELF_PROOF")
    window = authority_window(value["authorityWindow"])
    require(window["edge"] == edge, "CLOSE_EDGE")
    for name in ("contextSha256", "inputCloseSha256"):
        CD.sha(value[name])
    require(window["authorityFirstNs"] <= CD.integer(value["preCloseNs"]) <= CD.integer(value["closedNs"]) < window["sealEndNs"],
        "CLOSE_ORIGINAL_WINDOW")
    known_close(O.encoded(value["parentClose"]), native=True)
    known_close(O.encoded(value["originalReadbackClose"]))
    require(type(value["requiredFileCount"]) is int and value["requiredFileCount"] == 280 and
        type(value["otherFilesCount"]) is int and value["otherFilesCount"] == 279 and
        type(value["directoryCount"]) is int and value["directoryCount"] == 58 and
        type(value["requiredFiles"]) is type(value["otherFiles"]) is type(value["directories"]) is list and
        len(value["requiredFiles"]) == 280 and len(value["otherFiles"]) == 279 and len(value["directories"]) == 58,
        "CLOSE_ROSTER")
    for row in value["otherFiles"]:
        file_observation(row)
    require([row["relative"] for row in value["otherFiles"]] == [name for name in value["requiredFiles"] if name != "authority-close.json"] and
        type(value["otherFilesTotalBytes"]) is int and value["otherFilesTotalBytes"] == sum(row["bytes"] for row in value["otherFiles"]) <= CD.MAX_BYTES,
        "CLOSE_OTHER279")
    _same(value["self"], {"relative": "authority-close.json", "maximum": LIMIT, "state": "PENDING_SEPARATE_WRITER_READBACK_AND_CLOSE"},
        "CLOSE_SELF_PENDING")
    return value


def authority_bundle(authority_raw, index_raw, rows, close_originals, *, edge, input_rows=None):
    """Join actual retained bytes; no process, close handle or recipient is restored.

    Directory vectors on individual fresh reads may differ from the earlier
    pre-close inventory (the separate 280th writer changes the root directory).
    Their native directory identity must still be the original indexed one.
    """
    authority, index = authority_close(authority_raw, edge=edge), authority_index(index_raw, edge=edge)
    require(type(rows) is tuple and len(rows) == 280 and type(close_originals) is tuple and len(close_originals) == 4,
        "BUNDLE_COMPLETE_ORIGINALS")
    for row in rows:
        file_row(row)
    require(tuple(row[0] for row in rows) == tuple(index["requiredFiles"]), "BUNDLE_FILE_ORDER")
    originals = {row[0]: row[1] for row in rows}
    directory_ids = {row["relative"]: CD.native_key(tuple(row["readbackNative"])) for row in index["directories"]}
    for actual, declared in zip(rows, index["files"]):
        relative, raw, maximum, native, directory, provenance = actual
        parent = relative.rpartition("/")[0] or "."
        require((maximum, len(raw), O.digest(raw), native, provenance) == (declared["maximum"], declared["bytes"],
            declared["sha256"], tuple(declared["native"]), declared["provenance"]) and
            CD.native_key(directory) == CD.native_key(tuple(declared["directoryNative"])) == directory_ids[parent],
            "BUNDLE_ACTUAL_FILE_HASH_NATIVE")
    require(originals["authority-close.json"] == authority_raw and index["authorityCloseSha256"] == O.digest(authority_raw) and
        index["authorityContextSha256"] == authority["contextSha256"] == O.digest(originals["context.json"]) and
        index["originalReadbackClose"] == authority["originalReadbackClose"] and index["directories"] == authority["directories"] and
        index["requiredFiles"] == authority["requiredFiles"] and
        [row for row in index["files"] if row["relative"] != "authority-close.json"] == authority["otherFiles"],
        "BUNDLE_AUTHORITY_INDEX_JOIN")
    for pair, name in zip(close_originals, ("input", "readback", "native", "writer")):
        require(type(pair) is tuple and len(pair) == 2 and type(pair[0]) is str and pair[0] == name and type(pair[1]) is bytes,
            "BUNDLE_CLOSE_ORIGINAL_ORDER")
    closes = dict(close_originals)
    input_close = known_close(closes["input"])
    require(known_close(closes["readback"]) == index["originalReadbackClose"] and
        known_close(closes["native"], native=True) == authority["parentClose"] and
        writer_return(CD.canonical(closes["writer"])) == index["closeWriterReturn"] and
        O.digest(closes["input"]) == authority["inputCloseSha256"], "BUNDLE_ACTUAL_CLOSE_BYTES")
    context = authority_context(originals["context.json"], edge=edge)
    require(context["session"] == index["root"] and context["authorityWindow"] == authority["authorityWindow"] and
        context["authorityWindow"]["clock"] == index["clock"] and context["predecessor"] == authority["predecessor"] and
        context["inputCloseSha256"] == authority["inputCloseSha256"] and
        authority["closedNs"] <= index["closeWriterReturn"]["closedNs"] < context["authorityWindow"]["sealEndNs"],
        "BUNDLE_CONTEXT_AND_CLOSE_ORDER")
    summary = CD.fields(authority["authority"], "contextSha256 sourceBeforeSha256 freshMatchSha256 originalsSha256 "
        "querySessionSha256 phaseSha256 childSha256 ackSha256 invocation startedNs workEndNs finalEndNs acquiredNs "
        "checkedNs serviceSteps sourceAfterSha256")
    require(summary["contextSha256"] == authority["contextSha256"] and summary["sourceBeforeSha256"] ==
        context["sourceReturnSha256"] == O.digest(originals["source-before/source-return.json"]) and
        summary["sourceAfterSha256"] == O.digest(originals["source-after/source-return.json"]) and
        summary["freshMatchSha256"] == O.digest(originals["acquisition-queries/match.bin"]) ==
        O.digest(O.encoded(context["expectedMatch"])) and summary["querySessionSha256"] ==
        O.digest(originals["acquisition-queries/session-result.json"]) and summary["childSha256"] ==
        O.digest(originals["service/child-result.json"]) and summary["ackSha256"] == O.digest(originals["service/stdout.log"]) and
        summary["phaseSha256"] == {name: O.digest(originals["service/" + name]) for name in B.PHASE_FILES} and
        summary["originalsSha256"] == {name: O.digest(originals["acquisition-queries/" + name + ".bin"]) for name in B.ORIGINAL_KEYS},
        "BUNDLE_SUMMARY_ORIGINAL_HASHES")
    CD.job(summary["invocation"])
    start = CD.canonical(originals["service/start.json"])
    child = CD.canonical(originals["service/child-result.json"])
    require(tuple(summary[name] for name in ("invocation", "startedNs", "workEndNs", "finalEndNs")) ==
        tuple(start[name] for name in ("invocation", "startedNs", "workEndNs", "finalEndNs")) and
        summary["acquiredNs"] == child["acquiredNs"] and summary["serviceSteps"] == child["serviceSteps"] and
        CD.integer(summary["acquiredNs"]) <= CD.integer(summary["checkedNs"]) <= authority["preCloseNs"],
        "BUNDLE_SUMMARY_NATIVE_JOIN")
    if input_rows is not None:
        require(type(input_rows) is tuple and len(input_rows) == (24 if edge == "seal" else 305), "BUNDLE_INPUT_COUNT")
        for row in input_rows:
            file_row(row)
        require(tuple((row[0], row[2]) for row in input_rows[:24]) == FINAL_INPUTS and
            len({row[0] for row in input_rows}) == len(input_rows), "BUNDLE_INPUT_ORDER")
        raws = {row[0]: row[1] for row in input_rows[:24]}
        _crypto, final, _manifest, *_rest = final_bundle(raws)
        require(context["observed"] == final["observed"] and context["history"] == final["history"] and
            context["originalProposal"] == final["originalProposal"] and O.encoded(context["expectedMatch"]) ==
            raws["returned/original-match.json"] and context["eventSha256"] == O.digest(raws["returned/event.json"]),
            "BUNDLE_INPUT_SOURCE_HISTORY")
        predecessor = {"exportTransferSha256": O.digest(raws["returned/" + CD.LATER_FILES[1]]),
            "collectCloseSha256": O.digest(raws["returned/" + CD.LATER_FILES[4]]),
            "manifestSha256": O.digest(raws["export-output/manifest.json"]), "sealSha256": None,
            "exportOutcome": "success", "collectOutcome": "success", "sealOutcome": "NOT_OBSERVED"}
        if edge == "before":
            require(input_rows[24][0] == "seal/seal-pending.json", "BUNDLE_REAL_SEAL_SLOT")
            seal = seal_record(input_rows[24][1], raws)
            predecessor.update(sealSha256=O.digest(input_rows[24][1]), sealOutcome="success")
            require(tuple(row[0] for row in input_rows[25:]) == tuple("seal/authority/" + name for name in
                seal["authorityIndex"]["requiredFiles"]) and all(context["authorityWindow"][name] == seal[name]
                for name in ("sealFirstNs", "sealEndNs")), "BUNDLE_PRIOR_SEAL280")
        _same(context["predecessor"], predecessor, "BUNDLE_INPUT_PREDECESSOR")
        require(sum(row["label"] == "reader" for row in input_close["resources"]) >= len(input_rows),
            "BUNDLE_INPUT_CLOSE_ROSTER")
    return authority, index


def seal_record(raw, final_raws, expected_values=None):
    value = _record(raw, SEAL_FIELDS, SEAL_SCOPE)
    require(value["edge"] == "SEAL" and value["kind"] == "worker" and value["writerReturn"] == CD.PENDING and
        value["originalStepOutcome"] == "NOT_OBSERVED" and value["testAcceptance"] == "NOT_PERFORMED" and
        value["productiveAuthority"] is value["cacheAuthority"] is False, "SEAL_PENDING_NOT_OWN_STEP")
    context, final, manifest, _index, _custody, transfer, _post, collected = final_bundle(final_raws)
    ends = _proposal(final["originalProposal"], final["history"])
    expected = {"kind": "worker", "selection": manifest["selection"], "source": manifest["source"], "github": manifest["github"],
        "policySha256": O.digest(final_raws["returned/candidate-policy.json"]),
        "originalProposalSha256": O.digest(O.encoded(final["originalProposal"])), "originalJobBasisNs": final["history"]["originalJobBasisNs"],
        "clock": context["clock"], "originalBootDigest": context["originalBootDigest"]}
    require(all(value[name] == item for name, item in expected.items()), "SEAL_FINAL_IDENTITY")
    require(collected["returnedNs"] <= CD.integer(value["sealFirstNs"]) < CD.integer(value["sealEndNs"]) <=
        min(ends["separate-seal"], value["sealFirstNs"] + 120 * NS) and
        value["sealFirstNs"] <= CD.integer(value["closedNs"]) < value["sealEndNs"], "SEAL_ORIGINAL120")
    require(type(value["inputs"]) is list and len(value["inputs"]) == 24, "SEAL_FINAL24")
    for row, (name, maximum) in zip(value["inputs"], FINAL_INPUTS):
        file_observation(row)
        require(row["relative"] == name and row["maximum"] == maximum and row["bytes"] == len(final_raws[name]) and
            row["sha256"] == O.digest(final_raws[name]), "SEAL_ORIGINAL_INPUT_HASH")
    close = known_close(O.encoded(value["inputClose"]))
    require(all(row["readerOrdinal"] < len(close["resources"]) and close["resources"][row["readerOrdinal"]]["label"] == "reader"
        for row in value["inputs"]) and len({row["readerOrdinal"] for row in value["inputs"]}) == 24, "SEAL_ALL_INPUT_CLOSES")
    authority = authority_close(O.encoded(value["authority"]), edge="seal")
    index = authority_index(O.encoded(value["authorityIndex"]), edge="seal")
    require(index["authorityCloseSha256"] == O.digest(O.encoded(authority)) and index["authorityContextSha256"] == authority["contextSha256"] and
        index["originalReadbackClose"] == authority["originalReadbackClose"] and index["directories"] == authority["directories"] and
        index["requiredFiles"] == authority["requiredFiles"] and
        [row for row in index["files"] if row["relative"] != "authority-close.json"] == authority["otherFiles"] and
        authority["authorityWindow"]["sealFirstNs"] == value["sealFirstNs"] and
        authority["authorityWindow"]["sealEndNs"] == value["sealEndNs"] and
        authority["inputCloseSha256"] == O.digest(O.encoded(value["inputClose"])) and
        authority["closedNs"] <= index["closeWriterReturn"]["closedNs"] <= value["closedNs"], "SEAL_AUTHORITY_JOIN")
    original_closes = CD.fields(value["authorityCloseOriginals"], "input readback native writer")
    _same(original_closes, {"input": value["inputClose"], "readback": index["originalReadbackClose"],
        "native": authority["parentClose"], "writer": index["closeWriterReturn"]}, "SEAL_RETURNED_CLOSE_BYTES")
    CD.fields(value["ciphertext"], "artifact native directoryNative eof retirement ownerClose closedNs")
    ciphertext = value["ciphertext"]
    require(ciphertext["artifact"] == manifest["artifact"] and ciphertext["eof"] is True and
        ciphertext["retirement"] == "KNOWN_READER_CLOSE" and type(ciphertext["native"]) is type(ciphertext["directoryNative"]) is list,
        "SEAL_CIPHERTEXT_ORIGINAL")
    native = CD.native(tuple(ciphertext["native"]), directory=False)
    CD.native(tuple(ciphertext["directoryNative"]), directory=True)
    require(native[6 if native[0] == "posix" else 4] == manifest["artifact"]["size"] and
        index["closeWriterReturn"]["closedNs"] <= CD.integer(ciphertext["closedNs"]) <= value["closedNs"], "SEAL_CIPHERTEXT_SIZE_TIME")
    known_close(O.encoded(ciphertext["ownerClose"]))
    if expected_values is not None:
        output_values(expected_values)
        clock = O.wire.clock_identity(value["clock"])
        require(expected_values == tuple(zip(OUTPUT_FIELDS, (O.digest(raw), str(value["sealEndNs"]), clock.role, clock.domain,
            str(clock.ticks_per_second), value["originalBootDigest"]))), "SEAL_EXTERNAL_OUTPUT_BINDING")
    return value
