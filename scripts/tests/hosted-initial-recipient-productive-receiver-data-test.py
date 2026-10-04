#!/usr/bin/env python3
"""New receiver DATA controls only; none is a native/provider/hosted test.

The complete280 packet below consists of small in-memory declarations. It
deliberately does not model valid process/HTTP originals. The live receiver's
native/source readers, policy validator and same-process return are separate
mandatory prerequisites. No old test methods, key files or evidence are read.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import ctypes
from pathlib import Path
import stat
import sys
import unittest
from unittest.mock import patch


GUARDED = False
EFFECTS = []


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in (
            "open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        EFFECTS.append(event)
        raise AssertionError("PRODUCTIVE_RECEIVER_DATA_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive_receiver_data as RD

CD, D, O, B, NS = RD.CD, RD.D, RD.O, RD.B, RD.NS
H, BOOT = "a" * 64, "b" * 64
ERRORS = (ValueError, RuntimeError)


def guarded(function, *args, **kwargs):
    global GUARDED
    prior, count = GUARDED, len(EFFECTS)
    GUARDED = True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = prior
        if len(EFFECTS) != count:
            raise AssertionError("PRODUCTIVE_RECEIVER_DATA_EFFECT")


def clock():
    return {"role": "linux-x64", "domain": O.clocks.DOMAINS["linux-x64"], "ticksPerSecond": NS}


def native(number, size=0, *, directory=False):
    return ("posix", 7, number, stat.S_IFDIR | 0o700 if directory else stat.S_IFREG | 0o600,
        0, 2 if directory else 1, size, 1, 1)


def close(labels, *, native_owner=False):
    return {"schema": 1, "scope": RD.NATIVE_CLOSE_SCOPE if native_owner else "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1",
        "resources": [{"ordinal": number, "label": label, "closeAttempted": True, "closed": True}
            for number, label in enumerate(labels)], "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}


def observation(name, raw, number, directory, ordinal):
    return {"relative": name, "maximum": CD.LIMIT, "bytes": len(raw), "sha256": O.digest(raw),
        "native": list(native(number, len(raw))), "directoryNative": list(directory), "provenance": RD.PROVENANCE,
        "readerOrdinal": ordinal, "retirement": "KNOWN_READER_CLOSE"}


def window(*, edge="seal"):
    first = 5000 * NS
    return {"schema": 1, "scope": RD.WINDOW_SCOPE, "edge": edge, "clock": clock(), "originalBootDigest": BOOT,
        "originalJobBasisNs": 1000 * NS, "originalProposalSha256": H, "sealFirstNs": first,
        "sealEndNs": first + 100 * NS, "authorityFirstNs": first + NS,
        "authorityWorkEndNs": first + 100 * NS, "authorityFinalEndNs": first + 100 * NS,
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}


def outputs():
    return tuple(zip(RD.OUTPUT_FIELDS, (H, str(5100 * NS), clock()["role"], clock()["domain"], str(NS), BOOT)))


def claims(*, before=False):
    value = {name: "success" if name.endswith("OUTCOME") else H for name in (*CD.FINAL_CLAIMS, *RD.COLLECT_CLAIMS)}
    if before:
        value[RD.SEAL_OUTCOME_ENV] = "success"
        value.update((name, output[1]) for name, output in zip(RD.OUTPUT_ENV, outputs()))
    return value


def steps(edge="before"):
    roles = [role for role, _name in RD.STEP_NAMES]
    current = roles.index(edge)
    rows = []
    for number, (_role, literal) in enumerate(RD.STEP_NAMES):
        status = "completed" if number < current else "in_progress" if number == current else "queued"
        rows.append({"name": literal, "number": number + 1, "status": status,
            "conclusion": "success" if number < current else None,
            "started_at": "2026-09-27T00:00:01Z" if number <= current else None,
            "completed_at": "2026-09-27T00:00:01Z" if number < current else None})
    return {"started_at": "2026-09-27T00:00:00Z", "steps": rows}


def authority_packet():
    """Real grammar and hashes; symbolic source/native contents are NOT qualified."""
    ids = tuple(tuple(format(first + n, "032x") for n in range(count))
        for first, count in ((1, 12), (13, 24), (37, 12)))
    required, names = B.member_grammar(*ids)
    basis = 1000 * NS
    arithmetic = D.allocation.fence_arithmetic(basis)
    proposal = {"scope": "INITIAL_RECIPIENT_BOOTSTRAP_ALLOCATION_PROPOSAL_V1",
        "serviceTimeBasis": {"jobStartBasisNs": basis}, "policy": D.allocation.policy(), **arithmetic,
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    end = arithmetic["phaseFencesNs"]["separate-seal"]
    first = end - 100 * NS
    frame = {**window(), "originalProposalSha256": O.digest(O.encoded(proposal)), "sealFirstNs": first, "sealEndNs": end,
        "authorityFirstNs": first + NS, "authorityWorkEndNs": end, "authorityFinalEndNs": end}
    raw = {name: b"" if name.endswith(".log") else b"{}\n" for name in required if name != "authority-close.json"}
    raw["acquisition-queries/match.bin"] = b"{}\n"
    input_close, reader_close, parent_close = close(("reader",)), close(("reader",) * 279), close(("directory",), native_owner=True)
    directory_pins = {name: native(1000 + ordinal, directory=True) for ordinal, name in enumerate(names)}
    root = "/model/productive-receiver/seal/authority"
    directories = [{"relative": name, "path": root + ("" if name == "." else "/" + name),
        "originalIdentity": list(directory_pins[name][1:3]) if name in B.DIRECTORY_TARGETS else None,
        "originalProvenance": "ORIGINAL_AUTHORITY_NATIVE_PIN" if name in B.DIRECTORY_TARGETS else "UNPINNED_ORIGINAL_DIRECTORY",
        "readbackNative": list(directory_pins[name])} for name in names]
    predecessor = {"exportTransferSha256": H, "collectCloseSha256": H, "manifestSha256": H, "sealSha256": None,
        "exportOutcome": "success", "collectOutcome": "success", "sealOutcome": "NOT_OBSERVED"}
    observed = {"kind": "worker", "source": {"commit": "a" * 40, "tree": "b" * 40}}
    history = {"observed": observed, "clock": clock(), "originalJobBasisNs": basis, "originalBootDigest": BOOT,
        "matchSha256": O.digest(b"{}\n"), "currentAuthority": "NOT_ACQUIRED"}
    context = {"schema": 1, "scope": RD.SEAL_CONTEXT_SCOPE, "edge": "seal", "kind": "worker", "root": "/model/source",
        "session": root, "job": "a" * 32, "observed": observed, "history": history, "originalProposal": proposal,
        "expectedMatch": {}, "eventSha256": H, "authorityWindow": frame,
        "sourceReturnSha256": O.digest(raw["source-before/source-return.json"]), "sourceReturnedNs": first + 2 * NS,
        "inheritedContext": {}, "directoryIdentity": list(directory_pins["."][1:3]), "predecessor": predecessor,
        "originalServiceJob": [1, "2026-09-27T00:00:00Z", "synthetic-runner", 1],
        "inputCloseSha256": O.digest(O.encoded(input_close)), "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    raw["context.json"] = O.encoded(context)
    start = {"invocation": "b" * 32, "startedNs": first + 3 * NS, "workEndNs": first + 48 * NS, "finalEndNs": first + 93 * NS}
    raw["service/start.json"] = O.encoded(start)
    raw["service/child-result.json"] = O.encoded({"acquiredNs": first + 6 * NS, "serviceSteps": {"model": "NOT_NATIVE"}})
    summary = {"contextSha256": O.digest(raw["context.json"]), "sourceBeforeSha256": context["sourceReturnSha256"],
        "sourceAfterSha256": O.digest(raw["source-after/source-return.json"]), "freshMatchSha256": O.digest(b"{}\n"),
        "originalsSha256": {name: O.digest(raw["acquisition-queries/" + name + ".bin"]) for name in B.ORIGINAL_KEYS},
        "querySessionSha256": O.digest(raw["acquisition-queries/session-result.json"]),
        "phaseSha256": {name: O.digest(raw["service/" + name]) for name in B.PHASE_FILES},
        "childSha256": O.digest(raw["service/child-result.json"]), "ackSha256": O.digest(raw["service/stdout.log"]),
        **start, "acquiredNs": first + 6 * NS, "checkedNs": first + 10 * NS, "serviceSteps": {"model": "NOT_NATIVE"}}
    observations = [observation(name, raw[name], ordinal + 1, directory_pins[name.rpartition("/")[0] or "."], ordinal)
        for ordinal, name in enumerate(sorted(raw))]
    authority = {"schema": 1, "scope": RD.CLOSE_SCOPE, "edge": "seal", "contextSha256": O.digest(raw["context.json"]),
        "authorityWindow": frame, "predecessor": predecessor, "inputCloseSha256": context["inputCloseSha256"],
        "authority": summary, "parentClose": parent_close, "preCloseNs": first + 11 * NS, "closedNs": first + 12 * NS,
        "requiredFiles": list(required), "requiredFileCount": 280, "otherFiles": observations, "otherFilesCount": 279,
        "otherFilesTotalBytes": sum(len(item) for item in raw.values()), "directories": directories, "directoryCount": 58,
        "originalReadbackClose": reader_close,
        "self": {"relative": "authority-close.json", "maximum": CD.LIMIT, "state": "PENDING_SEPARATE_WRITER_READBACK_AND_CLOSE"},
        "writerReturn": CD.PENDING, "originalStepOutcome": "NOT_OBSERVED", "liveRecipient": "NOT_CREATED", "capture": "NOT_K_CAPTURE",
        "upload": "NOT_PERFORMED", "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    authority_raw = O.encoded(authority)
    raw["authority-close.json"] = authority_raw
    last = observation("authority-close.json", authority_raw, 280, directory_pins["."], 1)
    writer = {"schema": 1, "scope": RD.WRITER_SCOPE, "relative": "authority-close.json", "bytes": len(authority_raw),
        "sha256": O.digest(authority_raw), "preCloseWrite": {"bytes": len(authority_raw), "sha256": O.digest(authority_raw),
            "metadata": {"device": 7, "inode": 280, "size": len(authority_raw), "mtime_ns": 1, "ctime_ns": 1}, "writerOrdinal": 0,
            "observation": "PRE_CLOSE_WRITE_VERIFY", "retirement": "KNOWN_WRITER_CLOSE"},
        "readback": last, "metadataPolicy": "POSIX_FULL_METADATA_EQUAL", "ownerClose": close(("writer", "reader")),
        "closedNs": first + 13 * NS, "originalStepOutcome": "NOT_OBSERVED", "capture": "NOT_K_CAPTURE", "exportSaveAuthority": False}
    observations = sorted((*observations, last), key=lambda row: row["relative"])
    index = {"schema": 1, "scope": RD.INDEX_SCOPE, "edge": "seal", "root": root, "clock": clock(),
        "authorityContextSha256": O.digest(raw["context.json"]), "requiredFiles": list(required), "files": observations,
        "directories": directories, "fileCount": 280, "directoryCount": 58, "totalBytes": sum(len(item) for item in raw.values()),
        "authorityCloseSha256": O.digest(authority_raw), "closeWriterReturn": writer, "originalReadbackClose": reader_close,
        "capture": "NOT_K_CAPTURE", "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False,
        "cacheAuthority": False, "exportSaveAuthority": False}
    rows = tuple((row["relative"], raw[row["relative"]], row["maximum"], tuple(row["native"]), tuple(row["directoryNative"]),
        row["provenance"]) for row in observations)
    originals = tuple((name, O.encoded(value)) for name, value in
        (("input", input_close), ("readback", reader_close), ("native", parent_close), ("writer", writer)))
    return authority_raw, O.encoded(index), rows, originals


def proposal_model(worker=None, *, jobs_start=1000 * NS):
    worker = worker or {"profile": "model-bootstrap", "selection": "model-selection", "cacheCohort": {},
        "source": {"commit": "a" * 40, "tree": "b" * 40}, "github": {}, "initialRecipient": {"firstUseAt": 1}}
    first_use = worker["initialRecipient"]["firstUseAt"]
    service = {"jobsRequestStartedNs": jobs_start, "jobStartedAt": "2026-09-27T00:00:00Z",
        "originDateEpochSeconds": O.wire.utc_epoch("2026-09-27T00:00:02Z")}
    shared = {"schema": 1, "profile": worker["profile"], "selection": worker["selection"], "cacheCohort": worker["cacheCohort"],
        "source": worker["source"], "github": worker["github"], "workerIdentitySha256": O.digest(O.encoded(worker)), "clock": clock(),
        "firstUseAt": first_use, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    basis = {**shared, "scope": "INITIAL_RECIPIENT_BOOTSTRAP_SERVICE_TIME_BASIS_V1", "invocation": "c" * 32,
        "service": service, "policy": D.allocation.service_time.policy(),
        **D.allocation.service_time.basis_arithmetic(service["jobsRequestStartedNs"],
            O.wire.utc_epoch(service["jobStartedAt"]), service["originDateEpochSeconds"])}
    proposal = {**shared, "scope": "INITIAL_RECIPIENT_BOOTSTRAP_ALLOCATION_PROPOSAL_V1", "serviceTimeBasis": basis,
        "serviceTimeBasisSha256": O.digest(O.encoded(basis)), "policy": D.allocation.policy(),
        **D.allocation.fence_arithmetic(basis["jobStartBasisNs"]), "productiveOwner": "NOT_CREATED"}
    history = {name: None for name in D.HISTORY_FIELDS.split()}
    history.update(schema=1, scope="INITIAL_CUSTODY_PRIMARY_HISTORICAL_BINDING_V1", kind="worker", clock=clock(),
        originalBootDigest=BOOT, currentAuthority="NOT_ACQUIRED", firstUseAt=first_use,
        matchSha256=O.digest(O.encoded(worker["initialRecipient"])), observed={"source": worker["source"]},
        originalJobBasisNs=basis["jobStartBasisNs"], budgetAcceptance="NOT_ADMITTED", exportSaveAuthority=False)
    return proposal, history, worker


def final_packet():
    """Symbolic CD parser returns exercise the NEW final24 joins, not CD/native acceptance."""
    raw = {name: b"{}\n" for name, _maximum in RD.FINAL_INPUTS}
    raw["returned/crypto-service/stderr.log"] = b""
    raw["returned/recipient-public.asc"] = b"SYMBOLIC PUBLIC DATA NOT A KEY\n"
    policy = {"recipient": {"fingerprint": "A" * 40, "sha256": O.digest(raw["returned/recipient-public.asc"])},
        "expiresAt": 2000000000}
    raw["returned/candidate-policy.json"] = O.encoded(policy)
    match = {"firstUseAt": 1, "github": {}, "policy": {"sha256": O.digest(raw["returned/candidate-policy.json"])}}
    raw["returned/original-match.json"] = raw["returned/fresh-match.json"] = O.encoded(match)
    worker = {"profile": "model-bootstrap", "selection": "model-selection", "cacheCohort": {},
        "source": {"commit": "a" * 40, "tree": "b" * 40}, "github": {}, "initialRecipient": match}
    proposal, history, worker = proposal_model(worker)
    final_claims = {name: claims()[name] for name in CD.FINAL_CLAIMS}
    predecessor = {name: final_claims[key] for name, key in
        (("producerStepOutcome", "PRODUCER_OUTCOME"), ("producerHandoffSha256", "HANDOFF_SHA256"),
         ("producerReturnSha256", "PRODUCER_RETURN_SHA256"), ("afterSaveStepOutcome", "AFTER_SAVE_OUTCOME"),
         ("afterSaveSha256", "AFTER_SAVE_SHA256"), ("afterProbeStepOutcome", "AFTER_PROBE_OUTCOME"), ("probeSha256", "PROBE_SHA256"))}
    predecessor["prefixRetentionSha256"] = H
    raw["returned/authority-index.json"] = O.encoded({"contextSha256": H})
    proposal_sha = O.digest(O.encoded(proposal))
    pre = {"inventorySha256": O.digest(raw["returned/authority-index.json"]), "contextSha256": H,
        "matchSha256": O.digest(raw["returned/original-match.json"]), "workerIdentitySha256": O.digest(O.encoded(worker)),
        "authorityWindow": {"originalProposalSha256": proposal_sha}, "predecessor": predecessor, "closedNs": 100}
    raw["returned/authority-return.json"] = O.encoded(pre)
    groups = [{"modelOrdinal": ordinal} for ordinal in range(29)]
    prior = {"preExportReturnSha256": O.digest(raw["returned/authority-return.json"]),
        "preExportIndexSha256": O.digest(raw["returned/authority-index.json"]), "prefixRetentionSha256": H, "groups": groups[:28]}
    raw["returned/pre-export-copy-index.json"] = O.encoded(prior)
    final = {"observed": history["observed"], "history": history, "originalProposal": proposal, "workerIdentity": worker,
        "compatibilityInputsSha256": H,
        "claims": final_claims, **{name: prior[name] for name in ("preExportReturnSha256", "preExportIndexSha256", "prefixRetentionSha256")},
        "preExportCopyIndexSha256": O.digest(raw["returned/pre-export-copy-index.json"]),
        "originalMatchSha256": O.digest(raw["returned/original-match.json"]), "freshMatchSha256": O.digest(raw["returned/fresh-match.json"]),
        "sourceRecordsSha256": {"candidate_policy_raw": O.digest(raw["returned/candidate-policy.json"])}}
    raw["returned/final-inputs.json"] = O.encoded(final)
    context = {"observed": final["observed"], "history": history, "originalProposal": proposal, "clock": clock(),
        "originalBootDigest": BOOT, "parent28Sha256": final["preExportCopyIndexSha256"],
        "finalInputsSha256": O.digest(raw["returned/final-inputs.json"]),
        "inputs": {name: {"name": name, "bytes": len(raw["returned/" + name]), "sha256": O.digest(raw["returned/" + name])}
            for name, _maximum in CD.CRYPTO_INPUTS}}
    raw["returned/context.json"] = O.encoded(context)
    index = {"startSha256": O.digest(raw["returned/crypto-service/start.json"]), "contextSha256": O.digest(raw["returned/context.json"]),
        "parent28Sha256": final["preExportCopyIndexSha256"], "groups": groups}
    raw["payload/copy-index.json"] = O.encoded(index)
    manifest = {"source": worker["source"], "selection": worker["selection"],
        "github": {**match["github"], "repository": D.identity.I.REPOSITORY, "eventSha256": O.digest(raw["returned/event.json"])},
        "policy": {**match["policy"], "fingerprint": policy["recipient"]["fingerprint"], "keySha256": policy["recipient"]["sha256"],
            "expiresAt": policy["expiresAt"], "retentionDays": 14}, "recipient": {"keySha256": policy["recipient"]["sha256"]},
        "copy": {"groups": groups, "index": {"name": "copy-index.json", "bytes": len(raw["payload/copy-index.json"]),
            "sha256": O.digest(raw["payload/copy-index.json"])}},
        "initialRecipient": {"preExportReturnSha256": final["preExportReturnSha256"],
            "preExportIndexSha256": final["preExportIndexSha256"], "matchSha256": final["originalMatchSha256"]},
        "productive": {**predecessor, "originalProposalSha256": proposal_sha, "compatibilityInputsSha256": H}}
    raw["export-output/manifest.json"] = O.encoded(manifest)
    hashes = {"contextSha256": O.digest(raw["returned/context.json"]), "manifestSha256": O.digest(raw["export-output/manifest.json"]),
        "copyIndexSha256": O.digest(raw["payload/copy-index.json"]), "preExportReturnSha256": final["preExportReturnSha256"],
        "preExportIndexSha256": final["preExportIndexSha256"], "parent28Sha256": context["parent28Sha256"]}
    custody = {**hashes, "startSha256": index["startSha256"], "childSha256": O.digest(raw["returned/crypto-child-result.json"]),
        "nativeRecordsSha256": {name: O.digest(raw["returned/crypto-service/" + name]) for name in B.PHASE_FILES},
        "claims": final_claims, "authorityClosedNs": 100, "nativePhase": [101], "returnedNs": 102}
    raw["returned/" + CD.LATER_FILES[0]] = O.encoded(custody)
    custody_sha = O.digest(raw["returned/" + CD.LATER_FILES[0]])
    raw["returned/" + CD.LATER_FILES[1]] = O.encoded({**hashes, "custodyReturnSha256": custody_sha, "returnedNs": 103})
    transfer_sha = O.digest(raw["returned/" + CD.LATER_FILES[1]])
    raw["returned/" + CD.LATER_FILES[3]] = O.encoded({"contextSha256": "c" * 64})
    post = {"contextSha256": "c" * 64, "inventorySha256": O.digest(raw["returned/" + CD.LATER_FILES[3]]),
        "matchSha256": final["originalMatchSha256"], "workerIdentitySha256": pre["workerIdentitySha256"],
        "authorityWindow": {"originalProposalSha256": proposal_sha, "authorityFirstNs": 104}, "closedNs": 105,
        "predecessor": {"step": "custody-export", "stepOutcome": "success", "exportTransferSha256": transfer_sha,
            "custodyReturnSha256": custody_sha, **{name: hashes[name] for name in
                ("manifestSha256", "copyIndexSha256", "preExportReturnSha256", "preExportIndexSha256")}}}
    raw["returned/" + CD.LATER_FILES[2]] = O.encoded(post)
    collected = {**{name: value for name, value in hashes.items() if name not in ("contextSha256", "parent28Sha256")},
        "custodyReturnSha256": custody_sha, "exportTransferSha256": transfer_sha,
        "postExportReturnSha256": O.digest(raw["returned/" + CD.LATER_FILES[2]]), "postExportIndexSha256": post["inventorySha256"],
        "returnedNs": 106}
    raw["returned/" + CD.LATER_FILES[4]] = O.encoded(collected)
    values = {**claims(), CD.EXPORT_CLAIMS[1]: transfer_sha, CD.EXPORT_CLAIMS[2]: hashes["manifestSha256"],
        RD.COLLECT_CLAIMS[-1]: O.digest(raw["returned/" + CD.LATER_FILES[4]])}
    return raw, values, worker


class ReceiverDataModels(unittest.TestCase):
    def check(self, function, *args, **kwargs):
        return guarded(function, *args, **kwargs)

    def refuses(self, function, *args, **kwargs):
        with self.assertRaises(ERRORS):
            self.check(function, *args, **kwargs)

    def test_final24_fixed_order_and_no_old_p0_roster(self):
        names = tuple(name for name, _maximum in RD.FINAL_INPUTS)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), 24)
        self.assertEqual(names[:2], ("returned/context.json", "returned/crypto-child-result.json"))
        self.assertEqual(names[-2:], ("export-output/manifest.json", "payload/copy-index.json"))
        self.assertEqual(names[2:11], tuple("returned/" + name for name in (
            "final-inputs.json", "pre-export-copy-index.json", "authority-return.json", "authority-index.json",
            "original-match.json", "fresh-match.json", "event.json", "candidate-policy.json", "recipient-public.asc")))
        for values in ({}, {name: b"{}\n" for name in names[:-1]}, {**{name: b"{}\n" for name in names}, "P0": b"{}\n"}):
            self.refuses(RD.final_bundle, values)

    def test_exact6_output_no_hydration_and_canonical_integers(self):
        value = outputs()
        self.assertIs(self.check(RD.output_values, value), value)
        self.assertEqual(self.check(RD.encode_output_values, value).count(b"\n"), 6)
        for changed in (list(value), value[:-1], tuple(reversed(value)),
                (value[0], (value[1][0], "01"), *value[2:]), (value[0], (value[1][0], "-1"), *value[2:]),
                (*value[:4], (value[4][0], "1"), value[5]), ((value[0][0], H.upper()), *value[1:])):
            self.refuses(RD.output_values, changed)

    def test_seal_and_before_require_separate_original_success_claims(self):
        for before in (False, True):
            value = claims(before=before)
            self.assertIs(self.check(RD.claims, value, before=before), value)
            for name in value:
                if name.endswith("OUTCOME"):
                    self.refuses(RD.claims, {**value, name: "skipped"}, before=before)
            self.refuses(RD.claims, {**value, "initialSealSha256": H}, before=before)

    def test_exact_productive_step_frontier_all_four_receivers(self):
        date = O.wire.utc_epoch("2026-09-27T00:00:02Z")
        for edge in ("seal", "before", "upload", "after"):
            rows = self.check(RD.step_rows, steps(edge), date, edge=edge)
            self.assertEqual(tuple(name for name, _row in rows), tuple(name for name, _literal in RD.STEP_NAMES))

    def test_step_names_legacy_frontier_date_duplicate_or_skipped_refuse(self):
        original, date = steps(), O.wire.utc_epoch("2026-09-27T00:00:02Z")
        changes = ((0, "name", B.STEP_NAMES[0][1]), (0, "conclusion", "skipped"),
            (2, "completed_at", "2026-09-27T00:00:03Z"), (3, "status", "completed"),
            (4, "status", "in_progress"), (1, "name", original["steps"][0]["name"]), (1, "number", True))
        for number, field, value in changes:
            changed = copy.deepcopy(original)
            changed["steps"][number][field] = value
            self.refuses(RD.step_rows, changed, date, edge="before")

    def test_authority_is_same_seal120_not_a_renewed_window(self):
        for edge in ("seal", "before"):
            for basis in (1000 * NS, -1, -66 * NS):
                value = {**window(edge=edge), "originalJobBasisNs": basis}
                self.assertIs(self.check(RD.authority_window, value), value)
                for name, changed in (("sealFirstNs", True), ("sealEndNs", value["sealFirstNs"] + 121 * NS),
                        ("authorityWorkEndNs", value["sealEndNs"] - 1), ("authorityFinalEndNs", value["sealEndNs"] + 1),
                        ("budgetAcceptance", "ADMITTED"), ("exportSaveAuthority", True)):
                    self.refuses(RD.authority_window, {**value, name: changed})
            for invalid in (True, False, 1.0, "-1", None, -O.clocks.UINT64 - 1, O.clocks.UINT64 + 1):
                self.refuses(RD.authority_window, {**window(edge=edge), "originalJobBasisNs": invalid})
            for name in ("sealFirstNs", "sealEndNs", *RD.AUTHORITY_CAP_FIELDS[:3]):
                self.refuses(RD.authority_window, {**window(edge=edge), "originalJobBasisNs": -66 * NS, name: -1})

    def test_exact22_deadline_data_and_bounds_not_an_admission(self):
        value = {name: H for name in RD.DEADLINE_FIELDS.split() if name.endswith("Sha256")}
        value.update(schema=1, scope=RD.DEADLINE_SCOPE, kind="worker", selection="FULL-linux-x64",
            source={"commit": "a" * 40, "tree": "b" * 40}, github={}, originalJobBasisNs=1000 * NS,
            clock=clock(), originalBootDigest=BOOT, sealFirstNs=5000 * NS, sealEndNs=5100 * NS,
            uploadStartByNs=5110 * NS, uploadEndNs=5170 * NS, afterEndNs=5185 * NS, returnEndNs=5230 * NS,
            budgetAcceptance="NOT_ADMITTED", exportSaveAuthority=False)
        for basis in (1000 * NS, -1, -66 * NS):
            signed = {**value, "originalJobBasisNs": basis}
            self.assertEqual(self.check(RD.deadline, O.encoded(signed)), signed)
        for name, changed in (("sealFirstNs", True), ("sealEndNs", 5121 * NS), ("uploadEndNs", 5100 * NS),
                ("scope", "INITIAL_BEFORE_DEADLINE_V1"), ("source", {"commit": "latest-main", "tree": "b" * 40}),
                ("exportSaveAuthority", True), ("extra", None)):
            self.refuses(RD.deadline, O.encoded({**value, name: changed}))
        for invalid in (True, False, 1.0, "-1", None, -O.clocks.UINT64 - 1, O.clocks.UINT64 + 1):
            self.refuses(RD.deadline, O.encoded({**value, "originalJobBasisNs": invalid}))
        for name in ("sealFirstNs", "sealEndNs", "uploadStartByNs", "uploadEndNs", "afterEndNs", "returnEndNs"):
            self.refuses(RD.deadline, O.encoded({**value, "originalJobBasisNs": -66 * NS, name: -1}))

    def test_full_native_row_grammar_does_not_create_a_producer_pin(self):
        row = ("service/stdout.log", b"abc", 16, native(1, 3), native(2, directory=True), RD.PROVENANCE)
        self.assertIs(self.check(RD.file_row, row), row)
        for changed in (list(row), (*row[:5], "ORIGINAL_AUTHORITY_NATIVE_PIN"), (*row[:2], True, *row[3:]),
                (*row[:3], native(1, 4), *row[4:]), ("../private", *row[1:])):
            self.refuses(RD.file_row, changed)

    def test_close_requires_every_real_boolean_not_asserted_success(self):
        value = close(("directory", "reader", "writer"))
        self.assertEqual(self.check(RD.known_close, O.encoded(value)), value)
        for field, item in (("closed", False), ("closeAttempted", 1), ("ordinal", True), ("label", "proof")):
            changed = copy.deepcopy(value)
            changed["resources"][1][field] = item
            self.refuses(RD.known_close, O.encoded(changed))

    def test_complete280_index_and_four_close_bytes_join(self):
        packet = authority_packet()
        parsed = self.check(RD.authority_bundle, *packet, edge="seal")
        self.assertEqual(parsed[1]["fileCount"], 280)
        self.assertEqual(parsed[1]["directoryCount"], 58)
        self.assertEqual(parsed[0]["writerReturn"], CD.PENDING)
        self.assertFalse(parsed[1]["productiveAuthority"])

    def test_missing_extra_reordered_or_aliased_originals_refuse(self):
        authority, index, rows, originals = authority_packet()
        for changed in (rows[:-1], (*rows, rows[-1]), tuple(reversed(rows)),
                (rows[0], (*rows[1][:3], rows[0][3], *rows[1][4:]), *rows[2:])):
            self.refuses(RD.authority_bundle, authority, index, changed, originals, edge="seal")
        self.refuses(RD.authority_bundle, authority, index, rows, tuple(reversed(originals)), edge="seal")

    def test_index_280th_requires_known_writer_and_reader_not_self_row(self):
        _authority, raw, _rows, _closes = authority_packet()
        value = O.parse(raw)
        for mutation in (lambda item: item["closeWriterReturn"]["ownerClose"]["resources"][0].update(closed=False),
                lambda item: item["closeWriterReturn"].update(originalStepOutcome="success"),
                lambda item: item["closeWriterReturn"]["preCloseWrite"].update(writerOrdinal=1),
                lambda item: item.update(fileCount=279)):
            changed = copy.deepcopy(value)
            mutation(changed)
            self.refuses(RD.authority_index, O.encoded(changed), edge="seal")

    def test_280th_writer_metadata_policy_is_rederived_from_full_readback(self):
        _authority, raw, _rows, _closes = authority_packet()
        value = O.parse(raw)["closeWriterReturn"]
        self.assertIs(self.check(RD.writer_return, value), value)
        for mutation in (lambda item: item.update(metadataPolicy="UNVERIFIED"),
                lambda item: item["preCloseWrite"]["metadata"].update(inode=281),
                lambda item: item["preCloseWrite"]["metadata"].update(ctime_ns=2)):
            changed = copy.deepcopy(value)
            mutation(changed)
            self.refuses(RD.writer_return, changed)

    def test_windows_metadata_keeps_both_close_observations_without_false_equality(self):
        _authority, raw, _rows, _closes = authority_packet()
        value = O.parse(raw)["closeWriterReturn"]
        native_value = ("windows", 7, "1" * 32, False, value["bytes"], 1, 0, 1, 4, 5, "S-1-5-100", True)
        value["readback"]["native"] = list(native_value)
        value["readback"]["directoryNative"] = ["windows", 7, "2" * 32, True, 0, 1, 0x10, 1, 1, 1, "S-1-5-100", True]
        value["preCloseWrite"]["metadata"] = {**RD.file_metadata(native_value), "modified_100ns": 2, "change_100ns": 3}
        value["metadataPolicy"] = "WINDOWS_WRITE_CLOSE_MODIFIED_CHANGE_ONLY"
        self.assertIs(self.check(RD.writer_return, value), value)
        value["preCloseWrite"]["metadata"]["creation_100ns"] = 9
        self.refuses(RD.writer_return, value)

    def test_complete_corpus_hash_change_cannot_be_replaced_by_old_index(self):
        authority, index, rows, originals = authority_packet()
        first = rows[0]
        altered = (first[0], b"x" * len(first[1]), *first[2:])
        self.refuses(RD.authority_bundle, authority, index, (altered, *rows[1:]), originals, edge="seal")

    def test_original_directory_pins_not_invented_for_query_targets(self):
        _authority, raw, _rows, _closes = authority_packet()
        value = O.parse(raw)
        row = next(row for row in value["directories"] if row["originalIdentity"] is None)
        row["originalIdentity"] = row["readbackNative"][1:3]
        row["originalProvenance"] = "ORIGINAL_AUTHORITY_NATIVE_PIN"
        self.refuses(RD.authority_index, O.encoded(value), edge="seal")

    def test_no_close_or_summary_hash_can_substitute_for_original_bytes(self):
        authority, index, rows, originals = authority_packet()
        changed = (*originals[:3], ("writer", O.encoded({**O.parse(originals[3][1]), "sha256": H})))
        self.refuses(RD.authority_bundle, authority, index, rows, changed, edge="seal")
        self.refuses(RD.authority_bundle, authority, index, rows, originals, edge="before")


class OriginalProposalModels(unittest.TestCase):
    """Exercise new original arithmetic with only the worker DATA reader stubbed."""
    def test_negative_virtual_basis_original_proposal_is_rederived_not_clamped(self):
        for start in (68 * NS - 1, 2 * NS):
            proposal, history, worker = proposal_model(jobs_start=start)
            basis = proposal["serviceTimeBasis"]
            self.assertEqual(basis["chargedAgeNs"], 68 * NS)
            self.assertEqual(basis["jobStartBasisNs"], start - 68 * NS)
            self.assertLess(basis["jobStartBasisNs"], 0)
            self.assertEqual(proposal["proposedJobEndNs"], basis["jobStartBasisNs"] + 5400 * NS)
            self.assertEqual(proposal["allocationStartBasisNs"], basis["jobStartBasisNs"] + 750 * NS)
            with self.subTest(start=start), patch.object(D.identity, "cache_cohort",
                    lambda raw: {} if raw == O.encoded(worker) else None):
                self.assertIs(guarded(RD.original_proposal, proposal, history, worker), proposal)
                self.assertEqual(guarded(RD._proposal, proposal, history), proposal["phaseFencesNs"])
                self.assertEqual(proposal["budgetAcceptance"], "NOT_ADMITTED")
                self.assertIs(proposal["exportSaveAuthority"], False)
                for changed_basis in (0, basis["jobStartBasisNs"] - 1):
                    changed, changed_history = copy.deepcopy(proposal), copy.deepcopy(history)
                    changed["serviceTimeBasis"]["jobStartBasisNs"] = changed_basis
                    changed["serviceTimeBasisSha256"] = O.digest(O.encoded(changed["serviceTimeBasis"]))
                    changed.update(D.allocation.fence_arithmetic(changed_basis))
                    changed_history["originalJobBasisNs"] = changed_basis
                    with self.assertRaises(ERRORS):
                        guarded(RD.original_proposal, changed, changed_history, worker)
                for invalid in (True, False, 1.0, "-1", None, -O.clocks.UINT64 - 1, O.clocks.UINT64 + 1):
                    changed_history = {**history, "originalJobBasisNs": invalid}
                    with self.assertRaises(ERRORS):
                        guarded(RD.original_proposal, proposal, changed_history, worker)
                    with self.assertRaises(ERRORS):
                        guarded(RD._proposal, proposal, changed_history)
                changed = copy.deepcopy(proposal)
                changed["serviceTimeBasis"]["service"]["jobsRequestStartedNs"] = -1
                with self.assertRaises(ERRORS):
                    guarded(RD.original_proposal, changed, history, worker)
                for name in ("proposedJobEndNs", "allocationStartBasisNs"):
                    changed = {**proposal, name: -1}
                    with self.assertRaises(ERRORS):
                        guarded(RD.original_proposal, changed, history, worker)
                    with self.assertRaises(ERRORS):
                        guarded(RD._proposal, changed, history)

    def test_complete_basis_hash_identity_and_every_end_remain_original(self):
        proposal, history, worker = proposal_model()
        basis = proposal["serviceTimeBasis"]
        with patch.object(D.identity, "cache_cohort", lambda raw: {} if raw == O.encoded(worker) else None):
            self.assertIs(guarded(RD.original_proposal, proposal, history, worker), proposal)
            for change in (lambda value: value.update(workerIdentitySha256=H),
                    lambda value: value.update(serviceTimeBasisSha256=H),
                    lambda value: value["serviceTimeBasis"].update(jobStartBasisNs=basis["jobStartBasisNs"] + 1),
                    lambda value: value["phaseFencesNs"].update({"separate-seal": value["phaseFencesNs"]["separate-seal"] + 1}),
                    lambda value: value.update(exportSaveAuthority=True), lambda value: value.update(extra=None)):
                value = copy.deepcopy(proposal)
                change(value)
                with self.assertRaises(ERRORS):
                    guarded(RD.original_proposal, value, history, worker)


class FinalJoinSupplierModels(unittest.TestCase):
    """Only CD's already-separate parser boundary is symbolic, not any RD join.

    These controls do NOT qualify CD, crypto, policy, clocks, owners or real
    final outputs. The live receiver uses the actual CD and PC validators.
    """
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.raw, self.values, self.worker = final_packet()
        for name in ("crypto_context", "final_inputs", "pre_index", "public_manifest", "final_index", "authority_return",
                "authority_index", "custody_return", "export_transfer", "collect_close"):
            stack.enter_context(patch.object(CD, name, lambda raw, **_kwargs: CD.canonical(raw)))
        stack.enter_context(patch.object(D.identity, "cache_cohort",
            lambda raw: {} if raw == O.encoded(self.worker) else None))

    def test_complete_new_final24_and_external_claim_joins(self):
        result = guarded(RD.bind_claims, self.raw, self.values)
        self.assertEqual(len(self.raw), 24)
        self.assertEqual(result[1]["workerIdentity"], self.worker)
        self.assertEqual(result[-1]["returnedNs"], 106)
        self.assertEqual(result[1]["compatibilityInputsSha256"], result[2]["productive"]["compatibilityInputsSha256"])
        self.assertNotIn("compatibilityInputsSha256", O.parse(self.raw["returned/authority-return.json"])["predecessor"])

    def test_manifest_compatibility_cannot_be_changed_with_consistent_outer_hashes(self):
        # Keep the original final24 fixture coherent; change the CD parser's
        # supplied DATA at its existing symbolic seam, not any RD join.
        original = CD.public_manifest
        def changed(raw):
            value = original(raw)
            value["productive"]["compatibilityInputsSha256"] = "c" * 64
            return value
        with patch.object(CD, "public_manifest", changed), self.assertRaisesRegex(O.OriginError, "FINAL_PRODUCTIVE_MANIFEST"):
            guarded(RD.final_bundle, self.raw)


    def test_each_original24_byte_record_is_bound_not_only_the_manifest(self):
        for name, _maximum in RD.FINAL_INPUTS:
            with self.subTest(original=name):
                changed = dict(self.raw)
                value = self.raw[name]
                changed[name] = O.encoded({**O.parse(value), "newModelOnlyField": True}) if value.startswith(b"{") else value + b"x"
                with self.assertRaises(ERRORS):
                    guarded(RD.bind_claims, changed, self.values)


if __name__ == "__main__":
    unittest.main(failfast=True)
