#!/usr/bin/env python3
"""Authored OFFLINE productive DATA controls; no execution result is implied.

Every byte/clock/job below is SYNTHETIC. No key, owner, provider, native child,
original service acquisition, approval or enclosing Step is reconstructed. The
fixture exercises the ACTUAL pure codecs without replacing their predicates.
Other authored controls may import qualification_fixture; this file does not
execute a test suite on import.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hosted_initial_artifact_productive_delivery as D

TD, CD, RD, S, O, NS = D.TD, D.CD, D.RD, D.S, D.O, D.NS
MODEL_EPOCH = 1790000000
DOMAINS = {
    "linux-x64": "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "windows-x64": "windows.QueryPerformanceCounter/QueryPerformanceFrequency.floor_ns",
    "macos-arm64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-x64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
}


def model_hash(label):
    return hashlib.sha256(("SYNTHETIC_NOT_AN_ORIGINAL:" + label).encode("ascii")).hexdigest()


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def raw(value):
    return O.encoded(value)


def qualification_fixture(role="linux-x64", *, profile="desktop", jobs_request_started_ns=1000 * NS):
    """Self-contained real-codec fixture DATA, never a producer/owner factory.

    API keys needed by Stage2: final_manifest_raw, tail_manifest_raw, members,
    upload_raw, after_raw, job_raw, service_date. Returned component dictionaries
    are mutable test DATA so negative controls can change ONE field and rehash.
    All construction is pure, bounded and has no I/O, native or GPG side effect.
    """
    selection = profile + "-" + role
    cohort, checked_role, system, arch = S.bootstrap.selection(selection)
    assert checked_role == role
    source = {"commit": "a" * 40, "tree": "b" * 40}
    clock = {"role": role, "domain": DOMAINS[role], "ticksPerSecond": NS if role != "windows-x64" else 10000000}
    event_hash, match_hash = model_hash("event"), model_hash("match")
    github = {"repository": S.identity.REPOSITORY, "eventSha256": event_hash, "event": "workflow_dispatch",
        "runId": "123456", "runAttempt": "2", "workflow": S.bootstrap.WORKFLOW, "workflowSha": source["commit"],
        "job": S.bootstrap.JOB, "ref": S.SOURCE_REF, "profile": S.bootstrap.PROFILE, "selection": selection,
        "runnerOS": system, "runnerArch": arch}
    worker_github = {name: item for name, item in github.items() if name not in ("profile", "selection")}
    worker_github["eventBinding"] = {"originalMain": S.BASE["commit"], "policyHead": source["commit"],
        "selection": selection, "expectedCommit": source["commit"], "expectedTree": source["tree"]}
    common = {"schema": 1, "profile": S.bootstrap.PROFILE, "selection": selection,
        "cacheCohort": {"profile": cohort, "role": role}, "source": source, "github": worker_github,
        "workerIdentitySha256": model_hash("worker"), "clock": clock, "firstUseAt": MODEL_EPOCH + 100,
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    service = {"firstNs": jobs_request_started_ns - NS, "lastNs": jobs_request_started_ns + NS, "numericJobId": 789,
        "runnerName": "SYNTHETIC-RUNNER-NOT-ACTUAL", "selector": O.SERVICE_SELECTORS[role],
        "jobStartedAt": utc(MODEL_EPOCH), "originDateEpochSeconds": MODEL_EPOCH + 100,
        "jobsRequestStartedNs": jobs_request_started_ns,
        "originalsSha256": {name: model_hash(name) for name in
            ("attempt", "jobs", "approvals", "comment", "environment", "branches", "main", "reviewed_ref")},
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    allocation = CD.D.allocation
    arithmetic = allocation.service_time.basis_arithmetic(service["jobsRequestStartedNs"], MODEL_EPOCH,
        service["originDateEpochSeconds"])
    basis = {**common, "scope": "INITIAL_RECIPIENT_BOOTSTRAP_SERVICE_TIME_BASIS_V1", "invocation": "c" * 32,
        "service": service, "policy": allocation.service_time.policy(), **arithmetic}
    proposal = {**common, "scope": "INITIAL_RECIPIENT_BOOTSTRAP_ALLOCATION_PROPOSAL_V1", "serviceTimeBasis": basis,
        "serviceTimeBasisSha256": D.sha(raw(basis)), "policy": allocation.policy(),
        **allocation.fence_arithmetic(arithmetic["jobStartBasisNs"]), "productiveOwner": "NOT_CREATED"}
    proposal_hash = D.sha(raw(proposal))
    policy_end = MODEL_EPOCH + 14 * 86400
    policy = {"origin": "reviewed-head", "commit": source["commit"], "blob": "d" * 40,
        "path": S.identity.POLICY_PATH, "sha256": S.POLICY_SHA256, "fingerprint": "A" * 40,
        "keySha256": model_hash("PUBLIC_KEY_NOT_PRESENT"), "expiresAt": policy_end, "retentionDays": 14}
    authority = {"id": 123, "url": "https://github.com/" + S.identity.REPOSITORY + "/issues/437#issuecomment-123",
        "bodySha256": model_hash("AUTHORITY_NOT_APPROVAL"), "owner": S.joint.OWNER_LOGIN,
        "ownerId": S.joint.OWNER_ID, "createdAt": utc(MODEL_EPOCH)}
    initial = {"authority": authority, "environment": {"name": S.ENVIRONMENT, "id": 123,
        "branchPolicies": [{"id": index + 1, "name": name, "type": "branch"} for index, name in enumerate(S.BRANCHES)]},
        "originalBase": dict(S.BASE), "reviewed": source, "firstUseAt": MODEL_EPOCH + 100,
        "notBefore": MODEL_EPOCH, "expiresAt": policy_end, "matchSha256": match_hash,
        "preExportReturnSha256": model_hash("pre-export"), "preExportIndexSha256": model_hash("pre-index")}
    productive = {name: "success" if name.endswith("StepOutcome") else model_hash(name) for name in
        ("originalProposalSha256", "producerHandoffSha256", "producerReturnSha256", "producerStepOutcome",
            "afterSaveSha256", "afterSaveStepOutcome", "probeSha256", "afterProbeStepOutcome", "prefixRetentionSha256", "compatibilityInputsSha256")}
    productive["originalProposalSha256"] = proposal_hash
    fixed = {22: 1373, 23: 6, 25: 122, 26: 3, 27: 7, 29: 9, 30: 12 if role == "windows-x64" else 13}
    groups = [{"ordinal": index, "group": name,
        "map": {"name": "map-" + name + ".json", "bytes": 1, "sha256": model_hash(name)},
        "dataFiles": fixed.get(index, 281), "dataBytes": fixed.get(index, 281)}
        for index, name in enumerate(CD.GROUPS, 1)]
    count = sum(item["dataFiles"] for item in groups)
    copy = {"scope": "INITIAL_RECIPIENT_PRODUCTIVE_FIXED30_ARCHIVE_BINDING_V1", "groups": groups,
        "index": {"name": "copy-index.json", "bytes": 1, "sha256": model_hash("copy-index")},
        "dataFiles": count, "mapFiles": 30, "indexFiles": 1, "archiveFiles": count + 31,
        "archiveNativeNodes": count + 62, "plaintextBytes": count + 31}
    recipient = {"fingerprint": policy["fingerprint"], "encryptionFingerprint": "B" * 40,
        "keySha256": policy["keySha256"], "expiresAt": policy_end}
    final = {"schema": 1, "scope": "ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_PRODUCTIVE_EVIDENCE_V1", "kind": "worker",
        "selection": selection, "source": source, "github": github, "policy": policy, "initialRecipient": initial,
        "productive": productive, "copy": copy, "recipient": recipient,
        "artifact": {"name": "evidence.tar.gz.gpg", "size": 33, "sha256": model_hash("final-ciphertext-not-present")},
        "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    final_raw = raw(final)
    ends = proposal["phaseFencesNs"]
    deadline = {"schema": 1, "scope": "INITIAL_RECIPIENT_PRODUCTIVE_RECEIVER_DEADLINES_V1", "kind": "worker",
        "selection": selection, "source": source, "github": github, "policySha256": S.POLICY_SHA256,
        "originalProposalSha256": proposal_hash, "originalJobBasisNs": arithmetic["jobStartBasisNs"], "clock": clock,
        "originalBootDigest": model_hash("boot"), "sealFirstNs": ends["separate-seal"] - 120 * NS,
        "sealEndNs": ends["separate-seal"], "uploadStartByNs": ends["upload-transition"],
        "uploadEndNs": ends["evidence-upload"], "afterEndNs": ends["upload-after-guard"],
        "returnEndNs": ends["delivery-return"], "collectCloseSha256": model_hash("collect-close"),
        "manifestSha256": D.sha(final_raw), "sealSha256": model_hash("seal-not-original"),
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    predecessors = {"collectCloseSha256": deadline["collectCloseSha256"], "sealSha256": deadline["sealSha256"],
        "beforeAuthoritySha256": model_hash("before-authority"), "beforeIndexSha256": model_hash("before-index"),
        "deadlineSha256": D.sha(raw(deadline))}
    totals = {}
    for name in TD.GROUPS:
        number = TD.FIXED_COUNTS.get(name)
        if number is None:
            number = (4 if role == "windows-x64" else 7) if name == TD.GROUPS[3] else 0 if name == TD.GROUPS[4] else \
                12 if role == "windows-x64" else 13
        totals[name] = {"memberCount": number, "totalBytes": number}
    cut = {"mapName": TD.MAP_NAME, "mapSha256": model_hash("tail-map-not-present"), "mapBytes": 1,
        "memberCount": sum(item["memberCount"] for item in totals.values()) + 1,
        "totalBytes": sum(item["totalBytes"] for item in totals.values()) + 1, "groups": totals}
    tail = TD.public_inputs(TD.manifest_inputs(final_raw, predecessors, cut))
    tail.update(scope=TD.SCOPE, recipient=recipient,
        artifact={"name": "evidence.tar.gz.gpg", "size": 33, "sha256": model_hash("tail-ciphertext-not-present")},
        testAcceptance="NOT_PERFORMED", productiveAuthority=False, cacheAuthority=False,
        budgetAcceptance="NOT_ADMITTED", exportSaveAuthority=False)
    tail_raw = raw(tail)
    members = [{"name": D.Z.MEMBERS[0], "bytes": 33, "sha256": final["artifact"]["sha256"]},
        {"name": D.Z.MEMBERS[1], "bytes": len(final_raw), "sha256": D.sha(final_raw)},
        {"name": D.Z.MEMBERS[2], "bytes": 33, "sha256": tail["artifact"]["sha256"]},
        {"name": D.Z.MEMBERS[3], "bytes": len(tail_raw), "sha256": D.sha(tail_raw)}]
    total, zipped = TD.carrier_bytes(members)
    pending = {"schema": 1, "scope": TD.PENDING_SCOPE, "kind": "worker", "selection": selection, "source": source,
        "github": {name: github[name] for name in ("repository", "runId", "runAttempt", "job")},
        "originalProposal": proposal, "deadline": deadline,
        "originals": {"eventSha256": event_hash, "policySha256": S.POLICY_SHA256, "matchSha256": match_hash},
        "predecessors": predecessors, "manifests": {"finalSha256": D.sha(final_raw), "tailSha256": D.sha(tail_raw)},
        "cutMapSha256": cut["mapSha256"], "members": members, "totalBytes": total, "zipBytes": zipped,
        "knownCloses": {"beforeIndexSha256": predecessors["beforeIndexSha256"],
            "beforeWriterCloseSha256": model_hash("before-writer-not-owner"),
            "tailChildCloseSha256": model_hash("tail-close-not-owner"), "carrierCloseSha256": model_hash("carrier-not-owner")},
        "times": dict(zip(TD.TIME_FIELDS, (deadline["sealFirstNs"] + index * NS for index in (1, 2, 3, 4)))),
        "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED", "upload": "NOT_PERFORMED",
        "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    pending["github"].update(jobId=service["numericJobId"], role=role)
    pending_raw = TD.encode_pending(pending)
    first = deadline["sealEndNs"] + NS
    _start, work, close = D.upload_caps(deadline, first)
    validity = {"policyNotBefore": MODEL_EPOCH, "policyExpiresAt": policy_end,
        "authorityNotBefore": MODEL_EPOCH, "authorityExpiresAt": policy_end}
    base = {name: D.E._copy(pending[name]) for name in
        ("kind", "selection", "source", "github", "originalProposal", "deadline", "originals", "members")}
    base.update(schema=1, beforeSha256=D.sha(pending_raw), **validity, writerReturn="PENDING_OWNER_CLOSE",
        originalHelperOutcome="PENDING_ENCLOSING_PROCESS_CLOSE", originalStepOutcome="NOT_OBSERVED",
        qualification="NOT_ESTABLISHED", privateOriginals="TERMINAL_SELF_TAIL_NOT_DELIVERED")
    artifact = {"id": "4567", "name": D.artifact_name(pending), "zipBytes": zipped,
        "zipSha256": model_hash("zip-not-present"), "createInvokedAt": utc(MODEL_EPOCH + 5101).replace("Z", ".000Z"),
        "requestedExpiresAt": utc(MODEL_EPOCH + 5101 + 14 * 86400).replace("Z", ".000Z"), "requestedRetentionDays": 14}
    pre = 5000 * NS
    upload = {**deepcopy(base), "scope": D.UPLOAD_SCOPE, "readySha256": model_hash("stream-ready"),
        "carrierCloseSha256": pending["knownCloses"]["carrierCloseSha256"], "observedAt": MODEL_EPOCH + 5110,
        "artifact": artifact, "times": {"firstRawNs": str(first), "streamClosedNs": str(first + 2 * NS),
            "finishFirstRawNs": str(first + 3 * NS), "pendingPreparedNs": str(first + 4 * NS),
            "workEndNs": str(work), "closeEndNs": str(close), "readerPreSpawnLocalNs": str(pre),
            "readerReturnedLocalNs": str(pre + 4 * NS), "beforeEnteredLocalNs": str(pre + NS),
            "beforeReturnedLocalNs": str(pre + 2 * NS), "transportEnteredLocalNs": str(pre + 3 * NS),
            "transportReturnedLocalNs": str(pre + 5 * NS)},
        "observations": {**{name: model_hash(name) for name in D.UPLOAD_HASHES},
            "beforeServiceEpoch": MODEL_EPOCH + 5105, "beforeStepNumber": 4, "uploadStepNumber": 5,
            "transportRequestCount": 3 + (zipped + 8 * 1024 * 1024 - 1) // (8 * 1024 * 1024)}}
    upload_raw = D.encoded(D.pending_value(upload, "finish"), D.PENDING_LIMIT)
    a_first = first + 5 * NS
    _u, a_end = D.after_caps(deadline, a_first)
    after = {**deepcopy(base), "scope": D.AFTER_SCOPE, "readySha256": model_hash("after-ready"),
        "uploadSha256": D.sha(upload_raw), "uploadCarrier": {name: model_hash(name) for name in D.CARRIER_FIELDS},
        "observedAt": MODEL_EPOCH + 5125,
        "artifact": {**artifact, "createdAt": utc(MODEL_EPOCH + 5101),
            "expiresAt": utc(MODEL_EPOCH + 5101 + 14 * 86400), "serviceDigest": "sha256:" + artifact["zipSha256"]},
        "times": {"firstRawNs": str(a_first), "endNs": str(a_end), "pendingPreparedNs": str(a_first + NS),
            "observerEnteredLocalNs": str(pre + 6 * NS), "observerReturnedLocalNs": str(pre + 8 * NS)},
        "observations": {**{name: model_hash(name) for name in D.AFTER_HASHES}, "jobServiceEpoch": MODEL_EPOCH + 5122,
            "artifactServiceEpoch": MODEL_EPOCH + 5123, "beforeStepNumber": 4, "uploadStepNumber": 5,
            "afterStepNumber": 6, "observerRequestCount": 2}}
    after_raw = D.encoded(D.pending_value(after, "after"), D.PENDING_LIMIT)
    periods = ((1, 2), (2, 3), (3, 4), (4, 5100), (5100, 5120), (5120, 5130))
    steps = [{"name": name, "number": number, "status": "completed", "conclusion": "success",
        "started_at": utc(MODEL_EPOCH + period[0]), "completed_at": utc(MODEL_EPOCH + period[1])}
        for number, ((_label, name), period) in enumerate(zip(D.STEPS, periods), 1)]
    job = {"id": service["numericJobId"], "run_id": int(github["runId"]), "run_attempt": int(github["runAttempt"]),
        "name": github["job"], "head_sha": source["commit"], "head_branch": S.SOURCE_REF.removeprefix("refs/heads/"),
        "url": D.B.wire.ORIGIN + "/repos/" + S.identity.REPOSITORY + "/actions/jobs/" + str(service["numericJobId"]),
        "run_url": D.B.wire.ORIGIN + "/repos/" + S.identity.REPOSITORY + "/actions/runs/" + github["runId"],
        "status": "completed", "conclusion": "success", "labels": [O.SERVICE_SELECTORS[role]],
        "runner_id": 246, "runner_name": service["runnerName"], "runner_group_id": 0, "runner_group_name": "GitHub Actions",
        "started_at": service["jobStartedAt"], "completed_at": utc(MODEL_EPOCH + 5131), "steps": steps}
    return {"final_manifest_raw": final_raw, "tail_manifest_raw": tail_raw, "members": members,
        "upload_raw": upload_raw, "after_raw": after_raw, "job_raw": json.dumps(job).encode("ascii"),
        "service_date": MODEL_EPOCH + 5140, "final": final, "tail": tail, "upload": upload, "after": after,
        "job": job, "deadline": deadline, "proposal": proposal, "pending": pending, "pending_raw": pending_raw,
        "policy": {"notBefore": MODEL_EPOCH, "expiresAt": policy_end, "recipient": {
            "fingerprint": policy["fingerprint"], "sha256": policy["keySha256"]}},
        "match": {**initial, "policy": {name: policy[name] for name in ("origin", "commit", "blob", "path", "sha256")}},
        "context": {"originalServiceJob": [job["id"], job["started_at"], job["runner_name"], job["runner_id"]]}}


def qualify(f):
    return D.qualification_inputs(*(f[name] for name in ("final_manifest_raw", "tail_manifest_raw", "members",
        "upload_raw", "after_raw", "job_raw", "service_date")))


class ProductiveDeliveryDataControls(unittest.TestCase):
    def setUp(self):
        self.f = qualification_fixture()
        # Every negative starts from a complete positive that reaches the real
        # predicate, not an unrelated missing scope or byte-decoding failure.
        self.assertEqual(len(qualify(self.f)), 5)

    def changed(self, component, path, replacement, expected):
        f = deepcopy(self.f)
        value = f[component]
        for key in path[:-1]:
            value = value[key]
        value[path[-1]] = replacement
        output = {"upload": "upload_raw", "after": "after_raw", "final": "final_manifest_raw",
            "tail": "tail_manifest_raw", "job": "job_raw"}[component]
        f[output] = raw(f[component])
        if component == "upload":
            f["after"]["uploadSha256"] = D.sha(f[output])
            f["after_raw"] = raw(f["after"])
        with self.assertRaisesRegex(Exception, expected):
            qualify(f)

    def test_actual_pure_join_all_four_roles(self):
        for role in DOMAINS:
            with self.subTest(role=role):
                f = qualification_fixture(role)
                result = qualify(f)
                self.assertEqual(result[0]["source"], f["final"]["source"])
                self.assertFalse(result[1]["productiveAuthority"])
                self.assertLessEqual(len(f["upload_raw"]), D.PENDING_LIMIT)
                self.assertLessEqual(len(f["after_raw"]), D.PENDING_LIMIT)

    def test_decoded_record_bound_not_base64_environment_allowance(self):
        self.assertEqual(D.PENDING_LIMIT, 16384)
        value = {"synthetic": ""}
        value["synthetic"] = "x" * (D.PENDING_LIMIT - len(raw(value)))
        exact = D.encoded(value, D.PENDING_LIMIT)
        self.assertEqual(len(exact), 16384)
        self.assertEqual(D.canonical(exact), value)
        encoded = base64.b64encode(exact).decode("ascii")
        self.assertEqual(len(encoded), 21848)
        self.assertEqual(D._base64(encoded, D.PENDING_LIMIT), exact)
        with self.assertRaisesRegex(D.DeliveryError, "RECORD_BOUND"):
            D.encoded({"synthetic": value["synthetic"] + "x"}, D.PENDING_LIMIT)
        # The separate environment decoder is NOT widened to21848.
        with self.assertRaisesRegex(Exception, "DEADLINE_ENV_BOUND"):
            TD.decoded_deadline(encoded, D.sha(exact))

    def test_exact_original_pending_bytes_not_reencoded_f_wrapper(self):
        f = deepcopy(self.f)
        f["upload_raw"] = raw({"pending": f["upload"]})
        with self.assertRaisesRegex(D.DeliveryError, "FIELDS"):
            qualify(f)

    def test_incomplete_job_is_not_qualification(self):
        self.changed("job", ("status",), "in_progress", "QUALIFICATION_COMPLETED_HOSTED_JOB")

    def test_different_numeric_job_rejected(self):
        self.changed("job", ("id",), 790, "QUALIFICATION_JOB_IDENTITY")

    def test_runner_replacement_rejected_after_identity(self):
        self.changed("job", ("runner_name",), "OTHER-MODELED-RUNNER", "QUALIFICATION_ORIGINAL_SERVICE_JOB")

    def test_same_job_changed_start_rejected(self):
        self.changed("job", ("started_at",), utc(MODEL_EPOCH + 1), "QUALIFICATION_ORIGINAL_SERVICE_JOB")

    def test_required_step_failed_not_accepted(self):
        self.changed("job", ("steps", 4, "conclusion"), "failure", "STEP_REQUIRED_SUCCESS_OR_CURRENT")

    def test_required_after_step_missing(self):
        self.changed("job", ("steps",), self.f["job"]["steps"][:-1], "STEP_MISSING")

    def test_required_step_current_not_completed(self):
        f = deepcopy(self.f)
        f["job"]["steps"][-1].update(status="in_progress", conclusion=None, completed_at=None)
        f["job_raw"] = raw(f["job"])
        with self.assertRaisesRegex(D.DeliveryError, "STEP_REQUIRED_SUCCESS_OR_CURRENT"):
            qualify(f)

    def test_inserted_intermediate_step_breaks_terminal_adjacency(self):
        f = deepcopy(self.f)
        for step in f["job"]["steps"][4:]:
            step["number"] += 1
        f["job_raw"] = raw(f["job"])
        with self.assertRaisesRegex(D.DeliveryError, "STEP_TERMINAL_ADJACENCY"):
            qualify(f)

    def test_declared_original_upload_step_does_not_replace_service_step(self):
        self.changed("upload", ("observations", "beforeServiceEpoch"), MODEL_EPOCH + 5099,
            "QUALIFICATION_REAL_STEP_SUCCESS")

    def test_artifact_id_rebound_to_another_after_record(self):
        self.changed("after", ("artifact", "id"), "4568", "QUALIFICATION_COMPLETE_MANIFEST_U_A")

    def test_after_hash_must_bind_exact_original_upload_bytes(self):
        self.changed("after", ("uploadSha256",), model_hash("different-upload"), "QUALIFICATION_COMPLETE_MANIFEST_U_A")

    def test_service_expiry_cannot_extend_fourteen_days(self):
        self.changed("after", ("artifact", "expiresAt"), utc(MODEL_EPOCH + 5102 + 14 * 86400),
            "ARTIFACT_ORIGINAL_SERVICE_EXPIRY_OR_DIGEST")

    def test_changed_service_digest_rejected(self):
        self.changed("after", ("artifact", "serviceDigest"), "sha256:" + model_hash("other"),
            "ARTIFACT_ORIGINAL_SERVICE_EXPIRY_OR_DIGEST")

    def test_manifest_or_member_substitution_not_equal_input(self):
        f = deepcopy(self.f)
        f["members"][0]["sha256"] = model_hash("other-cipher")
        with self.assertRaisesRegex(D.DeliveryError, "QUALIFICATION_EXACT4_MEMBERS"):
            qualify(f)

    def test_partial_or_reordered_member_list_rejected(self):
        for members in (self.f["members"][:-1], list(reversed(self.f["members"]))):
            f = deepcopy(self.f)
            f["members"] = members
            with self.assertRaisesRegex(D.DeliveryError, "QUALIFICATION_EXACT4_MEMBERS"):
                qualify(f)

    def test_duplicate_original_job_key_rejected(self):
        f = deepcopy(self.f)
        f["job_raw"] = f["job_raw"][:-1] + b',"id":789}'
        with self.assertRaises(Exception):
            qualify(f)

    def test_date_is_original_integer_not_bool(self):
        f = deepcopy(self.f)
        f["service_date"] = True
        with self.assertRaisesRegex(D.DeliveryError, "INTEGER"):
            qualify(f)

    def test_later_date_cannot_precede_completed_job(self):
        f = deepcopy(self.f)
        f["service_date"] = MODEL_EPOCH + 5130
        with self.assertRaisesRegex(D.DeliveryError, "QUALIFICATION_SERVICE_CHRONOLOGY"):
            qualify(f)

    def test_phase_fence_edit_rehashed_still_fails_original_arithmetic(self):
        f = deepcopy(self.f)
        proposal = f["upload"]["originalProposal"]
        proposal["phaseFencesNs"]["evidence-upload"] += 1
        f["upload"]["deadline"]["originalProposalSha256"] = D.sha(raw(proposal))
        f["upload_raw"] = raw(f["upload"])
        with self.assertRaisesRegex(Exception, "ORIGINAL_PHASE_ARITHMETIC"):
            qualify(f)

    def test_cache_cohort_edit_rehashed_still_not_initial_worker(self):
        f = deepcopy(self.f)
        proposal = f["upload"]["originalProposal"]
        proposal["cacheCohort"]["profile"] = "full"
        proposal["serviceTimeBasis"]["cacheCohort"]["profile"] = "full"
        proposal["serviceTimeBasisSha256"] = D.sha(raw(proposal["serviceTimeBasis"]))
        f["upload"]["deadline"]["originalProposalSha256"] = D.sha(raw(proposal))
        f["upload_raw"] = raw(f["upload"])
        with self.assertRaisesRegex(Exception, "ORIGINAL_CACHE_COHORT"):
            qualify(f)

    def test_terminal_different_scope_cannot_claim_legacy(self):
        self.changed("upload", ("scope",), "INITIAL_ARTIFACT_UPLOAD_PENDING_ORIGINAL_STEP_RETURN_V1", "PENDING_SCOPE")

    def test_pending_bytes_remain_nonaccepting(self):
        self.changed("after", ("originalStepOutcome",), "success", "PENDING_NOT_SELF_ACCEPTANCE")

    def test_upload_sixty_and_five_original_bounds(self):
        seed = self.f["deadline"]
        first = seed["sealEndNs"] + NS
        start, work, close = D.upload_caps(seed, first)
        self.assertEqual((close - first, close - work), (60 * NS, 5 * NS))
        self.assertEqual(start, seed["uploadStartByNs"])
        for bad in (seed["uploadStartByNs"], True, -1, O.clocks.UINT64):
            with self.subTest(first=bad), self.assertRaises(Exception):
                D.upload_caps(seed, bad)

    def test_after_fifteen_clipped_to_original_end_without_new_credit(self):
        seed = self.f["deadline"]
        first = seed["uploadEndNs"] - NS
        self.assertEqual(D.after_caps(seed, first), (seed["uploadEndNs"], first + 15 * NS))
        for bad in (seed["uploadEndNs"], True, -1):
            with self.subTest(first=bad), self.assertRaises(Exception):
                D.after_caps(seed, bad)

    def test_noncanonical_pending_transport_rejected(self):
        f = deepcopy(self.f)
        f["upload_raw"] = b" " + f["upload_raw"]
        with self.assertRaisesRegex(D.DeliveryError, "CANONICAL"):
            qualify(f)

    def test_ready_reuses_same_deadline_and_original_job_tuple(self):
        f = self.f
        ready_raw = D.ready(f["pending"], f["context"], policy=f["policy"], match=f["match"],
            first_raw=D.decimal(f["upload"]["times"]["firstRawNs"]), before_sha256=D.sha(f["pending_raw"]),
            carrier_sha256=f["pending"]["knownCloses"]["carrierCloseSha256"], now=MODEL_EPOCH + 5105)
        ready = D.stream_ready(ready_raw)
        self.assertEqual(ready["deadline"], f["deadline"])
        self.assertEqual(ready["jobOriginal"], f["context"]["originalServiceJob"])
        self.assertEqual(ready["nativeFileRetirement"], "PENDING_ORIGINAL_READERS")

    def test_negative_virtual_basis_survives_ready_finish_after_and_qualification(self):
        for basis in (-1, -66 * NS):
            with self.subTest(basis=basis):
                # Original service age100 plus the unchanged66-second charge.
                request = 166 * NS + basis
                f = qualification_fixture(jobs_request_started_ns=request)
                original_basis = f["proposal"]["serviceTimeBasis"]
                self.assertEqual(original_basis["service"]["jobsRequestStartedNs"], request)
                self.assertEqual(original_basis["chargedAgeNs"], 166 * NS)
                self.assertEqual(original_basis["jobStartBasisNs"], basis)
                self.assertEqual(f["proposal"]["proposedJobEndNs"], basis + 5400 * NS)
                self.assertEqual(f["proposal"]["serviceTimeBasisSha256"], D.sha(raw(original_basis)))
                self.assertEqual(f["deadline"]["originalJobBasisNs"], basis)
                self.assertEqual(f["deadline"]["originalProposalSha256"], D.sha(raw(f["proposal"])))
                self.assertEqual(f["final"]["productive"]["originalProposalSha256"], D.sha(raw(f["proposal"])))
                ready_raw = D.ready(f["pending"], f["context"], policy=f["policy"], match=f["match"],
                    first_raw=D.decimal(f["upload"]["times"]["firstRawNs"]), before_sha256=D.sha(f["pending_raw"]),
                    carrier_sha256=f["pending"]["knownCloses"]["carrierCloseSha256"], now=MODEL_EPOCH + 5105)
                ready = D.stream_ready(ready_raw)
                self.assertEqual(ready["originalProposal"], f["proposal"])
                self.assertEqual(ready["deadline"], f["deadline"])
                self.assertEqual(ready["jobOriginal"], f["context"]["originalServiceJob"])
                self.assertEqual(ready["qualification"], "NOT_ESTABLISHED")
                for component, mode in (("upload", "finish"), ("after", "after")):
                    value = deepcopy(f[component])
                    self.assertIs(D.pending_value(value, mode), value)
                    self.assertEqual(D.parse_delivery(f[component + "_raw"], mode), value)
                    self.assertEqual(value["originalProposal"], f["proposal"])
                    self.assertEqual(value["deadline"], f["deadline"])
                    self.assertEqual(value["beforeSha256"], D.sha(f["pending_raw"]))
                    self.assertEqual(value["originalStepOutcome"], "NOT_OBSERVED")
                    self.assertEqual(value["qualification"], "NOT_ESTABLISHED")
                    self.assertEqual(value["privateOriginals"], "TERMINAL_SELF_TAIL_NOT_DELIVERED")
                self.assertEqual(f["after"]["uploadSha256"], D.sha(f["upload_raw"]))
                self.assertEqual(qualify(f)[2:4], (f["upload"], f["after"]))
                self.assertEqual(f["pending"]["budgetAcceptance"], "NOT_ADMITTED")
                self.assertIs(f["pending"]["exportSaveAuthority"], False)

    def test_signed_productive_delivery_graph_does_not_relax_other_fields(self):
        f = qualification_fixture(jobs_request_started_ns=100 * NS)  # Derived V=-66NS.
        maximum = (1 << 64) - 1
        basis_paths = (("deadline", "originalJobBasisNs"),
            ("originalProposal", "serviceTimeBasis", "jobStartBasisNs"))

        def parent(value, path):
            for name in path[:-1]:
                value = value[name]
            return value

        for component, mode in (("upload", "finish"), ("after", "after")):
            for path in basis_paths:
                for bad in (True, False, 0.0, "-1", None, -maximum - 1, maximum + 1):
                    value = deepcopy(f[component])
                    parent(value, path)[path[-1]] = bad
                    with self.assertRaisesRegex(D.E.posix.EvidenceError, "GRAPH_JOB_BASIS_INTEGER"):
                        D.pending_value(value, mode)
                value = deepcopy(f[component])
                del parent(value, path)[path[-1]]
                with self.assertRaisesRegex(D.E.posix.EvidenceError, "GRAPH_JOB_BASIS_PATH"):
                    D.pending_value(value, mode)
            paths = [("deadline", name) for name in ("sealFirstNs", "sealEndNs", "uploadStartByNs",
                "uploadEndNs", "afterEndNs", "returnEndNs")]
            paths += [("originalProposal", name) for name in ("allocationStartBasisNs", "proposedJobEndNs")]
            paths += [("originalProposal", "phaseFencesNs", name) for name in f["proposal"]["phaseFencesNs"]]
            paths += [("originalProposal", "serviceTimeBasis", "service", name) for name in
                ("firstNs", "lastNs", "jobsRequestStartedNs", "numericJobId")]
            paths += [("originalProposal", "serviceTimeBasis", "jobsRequestStartedNs"), ("github", "jobId")]
            for path in paths:
                value = deepcopy(f[component])
                parent(value, path)[path[-1]] = -1
                with self.subTest(mode=mode, path=path), self.assertRaisesRegex(D.E.posix.EvidenceError,
                        "^INITIAL_EVIDENCE_GRAPH_INTEGER$"):
                    D.parse_delivery(raw(value), mode)
            for name in f[component]["times"]:
                value = deepcopy(f[component])
                value["times"][name] = "-1"
                with self.subTest(mode=mode, time=name), self.assertRaisesRegex(D.DeliveryError, "_DECIMAL$"):
                    D.parse_delivery(raw(value), mode)
            value = deepcopy(f[component])
            value["originalProposal"]["serviceTimeBasis"]["service"]["jobStartBasisNs"] = -1
            with self.assertRaisesRegex(D.E.posix.EvidenceError, "^INITIAL_EVIDENCE_GRAPH_INTEGER$"):
                D.pending_value(value, mode)
            value = deepcopy(f[component])
            value["originalProposal"]["serviceTimeBasis"]["source"] = value["originalProposal"]["source"]
            with self.assertRaisesRegex(D.E.posix.EvidenceError, "^INITIAL_EVIDENCE_GRAPH_ALIAS_OR_SIZE$"):
                D.pending_value(value, mode)
            value = deepcopy(f[component])
            proposal = value["originalProposal"]
            proposal["serviceTimeBasis"]["jobStartBasisNs"] = value["deadline"]["originalJobBasisNs"] = 0
            proposal["serviceTimeBasisSha256"] = D.sha(raw(proposal["serviceTimeBasis"]))
            value["deadline"]["originalProposalSha256"] = D.sha(raw(proposal))
            with self.assertRaisesRegex((ValueError, RuntimeError), "TAIL_ORIGINAL_SERVICE_ARITHMETIC$"):
                D.pending_value(value, mode)
        context = deepcopy(f["context"])
        context["originalServiceJob"][3] = -1
        with self.assertRaisesRegex(D.E.posix.EvidenceError, "^INITIAL_EVIDENCE_GRAPH_INTEGER$"):
            D.ready(f["pending"], context, policy=f["policy"], match=f["match"],
                first_raw=D.decimal(f["upload"]["times"]["firstRawNs"]), before_sha256=D.sha(f["pending_raw"]),
                carrier_sha256=f["pending"]["knownCloses"]["carrierCloseSha256"], now=MODEL_EPOCH + 5105)


if __name__ == "__main__":
    unittest.main()
