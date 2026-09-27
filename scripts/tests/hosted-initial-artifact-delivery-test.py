#!/usr/bin/env python3
"""Small terminal-delivery DATA controls, never live K/U/A or HTTP evidence.

All source, job, runner, Step and clock values below are synthetic. No previous
fixture/suite, native owner, Recipient, artifact or private key is acquired.
"""
from __future__ import annotations

import _strptime  # Complete the standard UTC parser import before the I/O guard.
import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import unittest


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("DELIVERY_DATA_SIDE_EFFECT")


sys.dont_write_bytecode = True
sys.addaudithook(offline)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hosted_initial_artifact_delivery as D


# Only the already-reviewed PUBLIC policy is read, before the DATA I/O guard.
# No packet/key backend or Recipient object is invoked by these controls.
PUBLIC_POLICY_RAW = (Path(__file__).resolve().parents[2] / ".github/test-evidence-recipient.json").read_bytes()
NS = 1_000_000_000
DATE = "Sat, 26 Sep 2026 00:00:30 GMT"
NOW = int(datetime(2026, 9, 26, 0, 0, 30, tzinfo=timezone.utc).timestamp())
NAMES = ("P2pKit initial custody export", "P2pKit initial post-export custody",
    "P2pKit initial custody seal", "P2pKit initial before-upload custody",
    "P2pKit initial custody upload", "P2pKit initial after-upload custody")
MEMBERS = ("evidence.tar.gz.gpg", "manifest.json", "custody-tail.tar.gz.gpg", "custody-tail-manifest.json")


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def checksum(value):
    return hashlib.sha256(wire(value)).hexdigest()


def clone(value):
    return json.loads(wire(value))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validity():
    return {"policy": {"notBefore": NOW - 100, "expiresAt": NOW + 100},
        "match": {"notBefore": NOW - 50, "expiresAt": NOW + 50}}


def seed():
    return {"initialSealSha256": "b" * 64, "initialSealEndNs": str(346 * NS),
        "initialSealClockRole": "linux-x64", "initialSealClockDomain":
        "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)", "initialSealClockTicksPerSecond": str(NS),
        "initialSealBootSha256": "a" * 64}


def pending():
    deadline = seed()
    window = {"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_ABSOLUTE_WINDOW_V1",
        "clock": {"role": "linux-x64", "domain": deadline["initialSealClockDomain"], "ticksPerSecond": NS},
        "originalBootDigest": "a" * 64, "kind": "worker", "originalJobBasisNs": 0,
        "jobEndNs": 5400 * NS, "startNs": NS, "workEndNs": 241 * NS,
        "nativeFinalEndNs": 286 * NS, "readEndNs": 316 * NS,
        "sealEndNs": 346 * NS, "uploadEndNs": 406 * NS, "afterEndNs": 421 * NS}
    members = [{"name": name, "bytes": 1, "sha256": digit * 64} for name, digit in zip(MEMBERS, "cdef")]
    return {"schema": 1, "scope": "INITIAL_RECIPIENT_BEFORE_UPLOAD_PENDING_V1", "kind": "worker",
        "selection": "desktop-linux-x64", "source": {"commit": "1" * 40, "tree": "2" * 40},
        "github": {"repository": "p2pKit/P2pKit", "runId": "9001", "runAttempt": "2",
            "job": "populate", "jobId": 9002, "role": "linux-x64"},
        "originalWindow": window, "deadline": deadline,
        "originals": {"eventSha256": "3" * 64, "policySha256": D.S.POLICY_SHA256, "matchSha256": "4" * 64},
        "predecessors": {"cryptoStepSha256": "5" * 64, "collectSha256": "6" * 64, "sealSha256": "b" * 64,
            "beforeAuthoritySha256": "7" * 64, "originalWindowSha256": checksum(window)},
        "manifests": {"p0Sha256": "d" * 64, "tailSha256": "f" * 64}, "cutMapSha256": "8" * 64,
        "members": members, "totalBytes": 4, "zipBytes": 556,
        "knownCloses": {name: "9" * 64 for name in
            ("beforeReadbackSha256", "beforeCloseWriterSha256", "tailChildCloseSha256", "carrierCloseSha256")},
        "times": {"beforeClosedNs": 2 * NS, "tailChildClosedNs": 3 * NS,
            "carrierClosedNs": 4 * NS, "pendingPreparedNs": 5 * NS},
        "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED", "upload": "NOT_PERFORMED",
        "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}


def service(stage="upload"):
    current = 4 if stage == "upload" else 5
    steps = []
    for index, name in enumerate(NAMES):
        start = "2026-09-26T00:00:" + str(index * 2 + 1).zfill(2) + "Z"
        end = "2026-09-26T00:00:" + str(index * 2 + 2).zfill(2) + "Z"
        steps.append({"name": name, "number": index + 1,
            "status": "completed" if index < current else "in_progress" if index == current else "queued",
            "conclusion": "success" if index < current else None,
            "started_at": start if index <= current else None, "completed_at": end if index < current else None})
    job = {"id": 9002, "run_id": 9001, "run_attempt": 2, "name": "populate", "head_sha": "1" * 40,
        "head_branch": D.S.SOURCE_REF.removeprefix("refs/heads/"),
        "url": "https://api.github.com/repos/p2pKit/P2pKit/actions/jobs/9002",
        "run_url": "https://api.github.com/repos/p2pKit/P2pKit/actions/runs/9001",
        "status": "in_progress", "conclusion": None, "completed_at": None,
        "started_at": "2026-09-26T00:00:00Z", "runner_name": "synthetic-runner", "runner_id": 9003,
        "labels": ["ubuntu-latest"], "runner_group_id": 0, "runner_group_name": "GitHub Actions", "steps": steps}
    context = {"originalServiceJob": [9002, job["started_at"], "synthetic-runner", 9003],
        "observed": {"runnerName": "synthetic-runner"}}
    return job, context


def headers(raw=b"{}"):
    return ["Date", DATE, "Content-Type", "application/json; charset=utf-8",
        "X-GitHub-Api-Version-Selected", "2022-11-28", "X-GitHub-Request-Id", "SYNTHETIC:12345678",
        "Cache-Control", "public, max-age=60, s-maxage=60", "Content-Length", str(len(raw))]


def linked_packet():
    """New synthetic cross-links, not old fixtures or actual K/native evidence."""
    value = pending()
    source, github = value["source"], value["github"]
    policy = json.loads(PUBLIC_POLICY_RAW)
    event = wire({"repository": {"full_name": "p2pKit/P2pKit", "default_branch": "main"},
        "ref": D.S.SOURCE_REF, "inputs": {"selection": value["selection"],
            "expected_sha": source["commit"], "expected_tree": source["tree"]}})
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit",
        "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
        "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": D.S.SOURCE_REF, "GITHUB_SHA": source["commit"], "GITHUB_WORKFLOW_SHA": source["commit"],
        "GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/" + D.S.bootstrap.WORKFLOW + "@" + D.S.SOURCE_REF,
        "GITHUB_JOB": "populate", "GITHUB_RUN_ID": "9001", "GITHUB_RUN_ATTEMPT": "2",
        "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "RUNNER_NAME": "synthetic-runner"}
    observed = {"kind": "worker", "source": clone(source), "inputs": json.loads(event)["inputs"],
        "firstUseAt": NOW - 20, "role": "linux-x64", "runnerName": "synthetic-runner",
        "github": {"event": "workflow_dispatch", "ref": D.S.SOURCE_REF, "workflow": D.S.bootstrap.WORKFLOW,
            "workflowSha": source["commit"], "job": "populate", "runId": "9001", "runAttempt": "2",
            "runnerOS": "Linux", "runnerArch": "X64"}}
    match = {"schema": 1, "scope": D.S.STAGE1 + "_MATCH_ONLY_NOT_ADMISSION",
        "authority": {"id": 9005, "url": "https://github.com/p2pKit/P2pKit/issues/437#issuecomment-9005",
            "bodySha256": "5" * 64, "owner": D.S.joint.OWNER_LOGIN, "ownerId": D.S.joint.OWNER_ID,
            "createdAt": "2026-09-26T00:00:00Z"},
        "originalBase": clone(D.S.BASE), "reviewed": clone(source), "source": clone(source),
        "github": {**clone(observed["github"]), "profile": D.S.bootstrap.PROFILE, "selection": value["selection"]},
        "policy": {"origin": "reviewed-head", "commit": source["commit"], "blob": hashlib.sha1(b"blob " +
            str(len(PUBLIC_POLICY_RAW)).encode("ascii") + b"\0" + PUBLIC_POLICY_RAW).hexdigest(),
            "path": D.I.POLICY_PATH, "sha256": D.S.POLICY_SHA256},
        "environment": {"name": D.S.ENVIRONMENT, "id": 9006, "branchPolicies": [
            {"id": 9007 + number, "name": name, "type": "branch"} for number, name in enumerate(D.S.BRANCHES)]},
        "firstUseAt": NOW - 20, "notBefore": NOW - 25, "expiresAt": NOW + 3600}
    match_raw = wire(match)
    value["originals"] = {"eventSha256": sha(event), "policySha256": sha(PUBLIC_POLICY_RAW),
        "matchSha256": sha(match_raw)}
    recipient = policy["recipient"]
    p0 = {"schema": 4, "scope": "ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_EVIDENCE", "kind": "worker",
        "selection": value["selection"], "source": clone(source),
        "github": {**clone(match["github"]), "repository": "p2pKit/P2pKit", "eventSha256": sha(event)},
        "policy": {**clone(match["policy"]), "fingerprint": recipient["fingerprint"],
            "keySha256": recipient["sha256"], "expiresAt": policy["expiresAt"], "retentionDays": 14},
        "initialRecipient": {**{name: clone(match[name]) for name in
            ("authority", "environment", "originalBase", "reviewed", "firstUseAt", "notBefore", "expiresAt")},
            "matchSha256": sha(match_raw), "freshReturnSha256": "6" * 64},
        "primary": {"step": "canonical-initialization", "outcome": "success", "resultSha256": "7" * 64,
            "handoffSha256": "8" * 64, "inventorySha256": "9" * 64},
        "copy": {"mapSha256": "a" * 64, "memberCount": 20, "totalBytes": 200,
            "origins": {name: digit * 64 for name, digit in zip(
                ("PRIMARY", "AUTHORITY_PRE_EXPORT", "RECIPIENT_PRE_EXPORT"), "bcd")}},
        "recipient": {"fingerprint": recipient["fingerprint"], "encryptionFingerprint": "B" * 40,
            "keySha256": recipient["sha256"], "expiresAt": 1821484800},
        "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED",
        "artifact": {"name": "evidence.tar.gz.gpg", "sha256": "f" * 64, "size": 500}}
    p0_raw = wire(p0)
    counts = {"RETURNED": 13, "CRYPTO_SERVICE": 6, "POST_EXPORT_AUTHORITY": 279,
        "SEAL_AUTHORITY": 279, "SEAL": 1, "P0_EXPORT_DIAGNOSTICS": 7,
        "P0_VALIDATION_MAP_REFERENCE": 1, "BEFORE_AUTHORITY": 280, "NEW_RECIPIENT_VALIDATION": 11}
    cut = {"mapName": "custody-tail-map.json", "mapSha256": value["cutMapSha256"], "mapBytes": 100,
        "memberCount": sum(counts.values()) + 1, "totalBytes": sum(counts.values()) * 2 + 100,
        "groups": {name: {"memberCount": count, "totalBytes": count * 2} for name, count in counts.items()}}
    tail = {"schema": 1, "scope": "ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_CUSTODY_TAIL_V1", "kind": "worker",
        "selection": value["selection"], "source": clone(source), "github": clone(github),
        "policy": {name: p0["policy"][name] for name in ("sha256", "fingerprint", "keySha256", "expiresAt", "retentionDays")},
        "recipient": clone(p0["recipient"]), "p0": {"manifestSha256": sha(p0_raw), "artifact": clone(p0["artifact"]),
            "privateMemberCount": 20, "privateTotalBytes": 200}, "predecessors": clone(value["predecessors"]),
        "cut": cut, "transport": {"artifactMember": "custody-tail.tar.gz.gpg",
            "manifestMember": "custody-tail-manifest.json", "backendArtifact": "evidence.tar.gz.gpg",
            "backendManifest": "manifest.json"},
        "finalPrivateOriginals": {"disposition": "NOT_DELIVERED", "coverage": "EXCLUDED_FROM_K_AND_R",
            "requiredEvidence": "NOT_USED_AS_QUALIFICATION_ORIGINALS"},
        "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED",
        "artifact": {"name": "evidence.tar.gz.gpg", "sha256": "a" * 64, "size": 400}}
    tail_raw = wire(tail)
    value["manifests"] = {"p0Sha256": sha(p0_raw), "tailSha256": sha(tail_raw)}
    value["members"] = [{"name": name, "bytes": count, "sha256": digest} for name, count, digest in zip(
        MEMBERS, (500, len(p0_raw), 400, len(tail_raw)), ("f" * 64, sha(p0_raw), "a" * 64, sha(tail_raw)))]
    value["totalBytes"] = sum(row["bytes"] for row in value["members"])
    value["zipBytes"] = value["totalBytes"] + 552
    raws = {"event.json": event, "candidate-policy.json": PUBLIC_POLICY_RAW,
        "original-match.json": match_raw, "before-match.json": match_raw}
    _job, service_context = service()
    context = {"schema": 1, "scope": "INITIAL_RECIPIENT_K_TAIL_CHILD_CONTEXT_V1", "kind": "worker",
        "root": "/synthetic-only", "session": "/synthetic-only/session", "job": "populate", "observed": observed,
        "originalWindow": clone(value["originalWindow"]), "deadline": clone(value["deadline"]), "caps": {},
        "parentFirstNs": NS, "parentFirstLocal": 1, "beforeClosedNs": 2 * NS,
        "originalServiceJob": service_context["originalServiceJob"], "predecessors": clone(value["predecessors"]),
        "filesSha256": {name: sha(raw) for name, raw in raws.items()}, "directories": {}, "inheritedContext": {},
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    raws["context.json"] = wire(context)
    carrier = {name: clone(value[name]) for name in ("schema", "kind", "selection", "source", "github",
        "originalWindow", "deadline", "predecessors", "manifests", "cutMapSha256", "totalBytes", "zipBytes",
        "originalStepOutcome", "upload", "testAcceptance", "productiveAuthority", "cacheAuthority",
        "exportSaveAuthority", "budgetAcceptance")}
    carrier.update(scope="INITIAL_RECIPIENT_K_CARRIER_KNOWN_CLOSE_V1", carrier={"relative": "upload-output",
        "identity": [1, 12]}, files=[], writerReturn="PENDING_SEPARATE_RECORD_WRITER_CLOSE",
        times={name: value["times"][name] for name in ("beforeClosedNs", "tailChildClosedNs", "carrierClosedNs")},
        nativeClose={"contextSha256": sha(raws["context.json"]), "resultSha256": "8" * 64, "ackSha256": "9" * 64,
            "phaseSha256": {name: "9" * 64 for name in
                ("start.json", "baseline.json", "result.json", "native-start.json", "stdout.log", "stderr.log")}},
        ownerCloses={})
    sources = ("export-output/evidence.tar.gz.gpg", "export-output/manifest.json",
        "tail-export-output/evidence.tar.gz.gpg", "tail-export-output/manifest.json")
    for number, row in enumerate(value["members"]):
        metadata = {"device": 1, "inode": 101 + number * 10, "size": row["bytes"], "mtime_ns": 20, "ctime_ns": 30}
        carrier["files"].append({**clone(row), "sourceRelative": sources[number],
            "sourceDirectoryIdentity": [1, 10 if number < 2 else 11],
            "sourceRead": {"metadata": {**metadata, "inode": 100 + number * 10}, "readerOrdinal": 4 + number * 3},
            "write": {"metadata": clone(metadata), "writerOrdinal": 5 + number * 3},
            "readback": {"metadata": clone(metadata), "readerOrdinal": 6 + number * 3},
            "metadataPolicy": "POSIX_FULL_METADATA_EQUAL"})
    for name, scope, labels in (("native", "INITIAL_K_NATIVE_PARENT_KNOWN_CLOSE_V1", ("directory",)),
            ("carrier", "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1", ("directory",) * 4 + ("reader", "writer", "reader") * 4)):
        carrier["ownerCloses"][name] = {"schema": 1, "scope": scope, "resources": [
            {"ordinal": ordinal, "label": label, "closeAttempted": True, "closed": True}
            for ordinal, label in enumerate(labels)], "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}
    raws[D.H.PRIVATE_CARRIER_CLOSE] = wire(carrier)
    value["knownCloses"]["carrierCloseSha256"] = sha(raws[D.H.PRIVATE_CARRIER_CLOSE])
    raws[D.H.FILE] = wire(value)
    return raws, env, (value, carrier, context, observed, policy, match), (p0_raw, tail_raw)


def rebind_context(raws):
    """Only synthetic parent hashes, for reaching a deeper DATA mismatch."""
    carrier = json.loads(raws[D.H.PRIVATE_CARRIER_CLOSE])
    carrier["nativeClose"]["contextSha256"] = sha(raws["context.json"])
    raws[D.H.PRIVATE_CARRIER_CLOSE] = wire(carrier)
    pending = json.loads(raws[D.H.FILE])
    pending["knownCloses"]["carrierCloseSha256"] = sha(raws[D.H.PRIVATE_CARRIER_CLOSE])
    raws[D.H.FILE] = wire(pending)


class DeliveryDataControls(unittest.TestCase):
    def call(self, operation, *args, **kwargs):
        global GUARDED
        previous, GUARDED = GUARDED, True
        try:
            return operation(*args, **kwargs)
        finally:
            GUARDED = previous

    def reject(self, operation, *args, **kwargs):
        with self.assertRaises((ValueError, RuntimeError)):
            self.call(operation, *args, **kwargs)

    def test_upload_has_one_original_sixty_second_cap_and_close_reserve(self):
        self.assertEqual(self.call(D.upload_caps, seed(), 340 * NS), (346 * NS, 395 * NS, 400 * NS))

    def test_upload_refuses_early_empty_interval_and_exact_seal_boundary(self):
        for first in (0, 291 * NS, 346 * NS, 347 * NS):
            self.reject(D.upload_caps, seed(), first)

    def test_upload_rejects_noninteger_or_changed_seed(self):
        for bad in (True, 340.0, "340", -1, 1 << 64):
            self.reject(D.upload_caps, seed(), bad)
        for name, bad in (("initialSealEndNs", "0346"), ("initialSealBootSha256", "A" * 64),
                ("initialSealClockDomain", "CLOCK_MONOTONIC")):
            self.reject(D.upload_caps, {**seed(), name: bad}, 340 * NS)

    def test_after_is_original_first_plus_fifteen_not_a_new_upload_cap(self):
        self.assertEqual(self.call(D.after_caps, seed(), 400 * NS), (406 * NS, 415 * NS))
        self.assertEqual(self.call(D.after_caps, seed(), 406 * NS - 1), (406 * NS, 421 * NS - 1))

    def test_after_first_at_or_after_upload_end_refuses(self):
        for first in (406 * NS, 407 * NS, True, -1, 1 << 64):
            self.reject(D.after_caps, seed(), first)

    def test_canonical_ascii_and_duplicate_fields(self):
        self.assertEqual(self.call(D.canonical, b'{"a":1}\n'), {"a": 1})
        for raw in (b'{"a":1}', b'{ "a":1}\n', b'{"a":1,"a":1}\n', b'{"a":NaN}\n', b"", bytearray(b"{}\n")):
            self.reject(D.canonical, raw)

    def test_record_bounds_and_exact_scalar_types(self):
        self.reject(D.canonical, b" " * (D.LIMIT + 1))
        for value in (None, True, 1, "A" * 64, "a" * 63, "a" * 65):
            self.reject(D.digest, value)
        self.assertEqual(self.call(D.digest, "a" * 64), "a" * 64)

    def test_decimal_accepts_uint64_without_float_rounding(self):
        self.assertEqual(self.call(D.decimal, "18446744073709551615"), (1 << 64) - 1)
        for value in ("01", "-1", "1.0", "1e3", "18446744073709551616", True, 1):
            self.reject(D.decimal, value)

    def test_artifact_name_binds_original_run_attempt_kind_selection(self):
        self.assertEqual(self.call(D.artifact_name, pending()), "initial-recipient-custody-9001-2-worker-desktop-linux-x64")
        value = pending()
        value["github"]["runAttempt"] = "03"
        self.reject(D.artifact_name, value)

    def test_ready_is_private_pending_data_not_step_or_native_acceptance(self):
        _job, context = service()
        raw = self.call(D.ready, pending(), context, first_raw=340 * NS,
            before_sha256="a" * 64, carrier_sha256="b" * 64, now=NOW, **validity())
        value = self.call(D.canonical, raw)
        self.assertEqual(value["jobOriginal"], context["originalServiceJob"])
        self.assertEqual(value["firstRawNs"], str(340 * NS))
        self.assertEqual(value["nativeFileRetirement"], "PENDING_ORIGINAL_READERS")
        self.assertEqual(value["originalStepOutcome"], "NOT_OBSERVED")
        self.assertEqual(value["qualification"], "NOT_ESTABLISHED")

    def test_ready_refuses_changed_original_window(self):
        _job, context = service()
        value = pending()
        value["originalWindow"]["sealEndNs"] += 1
        self.reject(D.ready, value, context, first_raw=340 * NS,
            before_sha256="a" * 64, carrier_sha256="b" * 64, now=NOW, **validity())

    def test_ready_carries_exact_original_policy_and_authority_utc_bounds(self):
        _job, context = service()
        inputs = validity()
        value = self.call(D.canonical, self.call(D.ready, pending(), context, first_raw=340 * NS,
            before_sha256="a" * 64, carrier_sha256="b" * 64, now=NOW, **inputs))
        self.assertEqual({name: value[name] for name in
            ("policyNotBefore", "policyExpiresAt", "authorityNotBefore", "authorityExpiresAt")},
            {"policyNotBefore": NOW - 100, "policyExpiresAt": NOW + 100,
                "authorityNotBefore": NOW - 50, "authorityExpiresAt": NOW + 50})

    def test_ready_refuses_boolean_float_expired_and_widened_original_validity(self):
        _job, context = service()
        for group, name, bad in (("policy", "notBefore", True), ("policy", "expiresAt", float(NOW + 100)),
                ("match", "notBefore", NOW + 1), ("match", "notBefore", NOW - 101),
                ("match", "expiresAt", NOW), ("match", "expiresAt", NOW + 101)):
            inputs = validity()
            inputs[group][name] = bad
            self.reject(D.ready, pending(), context, first_raw=340 * NS, before_sha256="a" * 64,
                carrier_sha256="b" * 64, now=NOW, **inputs)

    def retained(self, raws, env, *, before_sha256=None, now=NOW):
        return self.call(D.retained_inputs, raws, environment=env, kind="worker", seed=seed(),
            before_sha256=sha(raws[D.H.FILE]) if before_sha256 is None else before_sha256, now=now)

    def test_retained_inputs_connect_all_seven_original_data_files(self):
        raws, env, expected, _manifests = linked_packet()
        self.assertEqual(self.retained(raws, env), expected)
        self.assertEqual(set(raws), {"before-upload-pending.json", "carrier-close.json", "context.json",
            "event.json", "candidate-policy.json", "original-match.json", "before-match.json"})
        self.assertEqual(expected[0]["budgetAcceptance"], "NOT_ADMITTED")

    def test_retained_inputs_refuse_missing_extra_and_oversized_original(self):
        for mode in ("missing", "extra", "oversized"):
            raws, env, _expected, _manifests = linked_packet()
            if mode == "missing":
                del raws["event.json"]
            elif mode == "extra":
                raws["injected.json"] = b"{}\n"
            else:
                raws["context.json"] = b"x" * (D.H.LIMIT + 1)
            with self.assertRaises((ValueError, RuntimeError)):
                self.retained(raws, env)

    def test_retained_inputs_require_actual_before_and_carrier_hash_links(self):
        raws, env, _expected, _manifests = linked_packet()
        with self.assertRaisesRegex(ValueError, "ORIGINAL_BEFORE_HASH"):
            self.retained(raws, env, before_sha256="0" * 64)
        value = json.loads(raws[D.H.FILE])
        value["knownCloses"]["carrierCloseSha256"] = "0" * 64
        raws[D.H.FILE] = wire(value)
        with self.assertRaisesRegex(ValueError, "CARRIER_HASH_KIND_SEED"):
            self.retained(raws, env)

    def test_retained_inputs_refuse_source_and_member_substitution_between_k_records(self):
        for name in ("source", "members"):
            raws, env, _expected, _manifests = linked_packet()
            value = json.loads(raws[D.H.FILE])
            if name == "source":
                value["source"]["commit"] = "7" * 40
            else:
                value["members"][0]["sha256"] = "7" * 64
            raws[D.H.FILE] = wire(value)
            with self.assertRaisesRegex(ValueError, "CARRIER_ORIGINAL_BINDING|CARRIER_MEMBERS_OR_TIMES"):
                self.retained(raws, env)

    def test_retained_inputs_require_exact_k_context_hash_scope_and_original_window(self):
        for field, bad, rehash in (("job", "changed", False), ("scope", "UNKNOWN_CONTEXT", True),
                ("budgetAcceptance", "ADMITTED", True), ("exportSaveAuthority", True, True)):
            raws, env, _expected, _manifests = linked_packet()
            context = json.loads(raws["context.json"])
            context[field] = bad
            raws["context.json"] = wire(context)
            if rehash:
                rebind_context(raws)
            with self.assertRaisesRegex(ValueError, "K_CONTEXT"):
                self.retained(raws, env)

    def test_retained_inputs_refuse_same_shape_but_different_before_match(self):
        raws, env, _expected, _manifests = linked_packet()
        match = json.loads(raws["before-match.json"])
        match["firstUseAt"] += 1
        raws["before-match.json"] = wire(match)
        with self.assertRaisesRegex(ValueError, "BEFORE_MATCH_SUBSTITUTION"):
            self.retained(raws, env)

    def test_retained_inputs_rederive_actual_context_not_just_hashes(self):
        raws, env, _expected, _manifests = linked_packet()
        env["RUNNER_NAME"] = "different-synthetic-runner"
        with self.assertRaisesRegex(ValueError, "ACTUAL_CONTEXT_ORIGINAL_LINK"):
            self.retained(raws, env)

    def test_retained_inputs_require_every_context_input_hash_after_context_rebinding(self):
        for name in ("event.json", "candidate-policy.json", "original-match.json", "before-match.json"):
            raws, env, _expected, _manifests = linked_packet()
            context = json.loads(raws["context.json"])
            context["filesSha256"][name] = "0" * 64
            raws["context.json"] = wire(context)
            rebind_context(raws)
            with self.assertRaisesRegex(ValueError, "K_INPUT_LINKS"):
                self.retained(raws, env)

    def test_retained_inputs_refuse_expired_original_authority_without_refresh(self):
        raws, env, expected, _manifests = linked_packet()
        with self.assertRaisesRegex(ValueError, "MATCH_CURRENT_WINDOW"):
            self.retained(raws, env, now=expected[5]["expiresAt"])

    def test_manifests_bind_exact_p0_tail_and_four_carrier_members(self):
        _raws, _env, expected, manifests = linked_packet()
        p0, tail = self.call(D.manifests, expected[0], *manifests, policy=expected[4], match=expected[5])
        self.assertEqual((wire(p0), wire(tail)), manifests)
        self.assertEqual(tail["p0"]["manifestSha256"], sha(manifests[0]))
        self.assertEqual([row["name"] for row in expected[0]["members"]], list(MEMBERS))

    def test_manifests_refuse_either_changed_original_hash(self):
        for index in (0, 1):
            _raws, _env, expected, manifests = linked_packet()
            changed = list(manifests)
            changed[index] += b"\n"
            self.reject(D.manifests, expected[0], *changed, policy=expected[4], match=expected[5])

    def test_manifests_refuse_p0_source_recipient_or_authority_relabeling_after_rehash(self):
        for path, bad in ((("source", "commit"), "8" * 40), (("recipient", "fingerprint"), "C" * 40),
                (("initialRecipient", "matchSha256"), "8" * 64)):
            _raws, _env, expected, manifests = linked_packet()
            p0 = json.loads(manifests[0])
            p0[path[0]][path[1]] = bad
            p0_raw = wire(p0)
            expected[0]["manifests"]["p0Sha256"] = sha(p0_raw)
            self.reject(D.manifests, expected[0], p0_raw, manifests[1], policy=expected[4], match=expected[5])

    def test_manifests_refuse_changed_tail_predecessor_or_cut_even_after_rehash(self):
        for group, field, error in (("predecessors", "beforeAuthoritySha256", "TAIL_COMPLETE_DECLARATION"),
                ("cut", "mapSha256", "TAIL_MAP")):
            _raws, _env, expected, manifests = linked_packet()
            self.call(D.manifests, expected[0], *manifests, policy=expected[4], match=expected[5])
            tail = json.loads(manifests[1])
            self.assertNotEqual(tail[group][field], "0" * 64, "negative must change the original field")
            tail[group][field] = "0" * 64
            tail_raw = wire(tail)
            self.assertNotEqual(tail_raw, manifests[1], "negative must change the original canonical bytes")
            # Rebind only synthetic hash/size declarations, so rejection must
            # reach the named semantic check, not a shallow member mismatch.
            expected[0]["manifests"]["tailSha256"] = sha(tail_raw)
            expected[0]["members"][3].update(bytes=len(tail_raw), sha256=sha(tail_raw))
            expected[0]["totalBytes"] = sum(row["bytes"] for row in expected[0]["members"])
            expected[0]["zipBytes"] = expected[0]["totalBytes"] + 552
            with self.subTest(group=group), self.assertRaisesRegex(ValueError, error):
                self.call(D.manifests, expected[0], manifests[0], tail_raw, policy=expected[4], match=expected[5])

    def test_manifests_refuse_ciphertext_roster_count_size_hash_or_order_substitution(self):
        for change in ("missing", "size", "hash", "order"):
            _raws, _env, expected, manifests = linked_packet()
            members = expected[0]["members"]
            if change == "missing":
                members.pop()
            elif change == "size":
                members[0]["bytes"] += 1
            elif change == "hash":
                members[2]["sha256"] = "8" * 64
            else:
                members[0], members[2] = members[2], members[0]
            self.reject(D.manifests, expected[0], *manifests, policy=expected[4], match=expected[5])

    def final_inputs(self):
        raws, _env, expected, _manifests = linked_packet()
        ready_raw = self.call(D.ready, expected[0], expected[2], policy=expected[4], match=expected[5],
            first_raw=340 * NS, before_sha256=sha(raws[D.H.FILE]),
            carrier_sha256=sha(raws[D.H.PRIVATE_CARRIER_CLOSE]), now=NOW)
        return {"before_sha256": sha(raws[D.H.FILE]), "ready_raw": ready_raw,
            "zip_result": {"scope": D.Z.SCOPE, "zipBytes": expected[0]["zipBytes"],
                "members": clone(expected[0]["members"]), "zipSha256": "6" * 64},
            "close_raw": b"synthetic-known-close-only\n", "closed_ns": 341 * NS}

    def test_stream_final_binds_original_ready_zip_close_and_stays_nonaccepting(self):
        values = self.final_inputs()
        raw = self.call(D.stream_final, **values)
        record = self.call(D.canonical, raw)
        self.assertEqual(record["readySha256"], sha(values["ready_raw"]))
        self.assertEqual(record["nativeCloseSha256"], sha(values["close_raw"]))
        self.assertEqual(record["zipSha256"], "6" * 64)
        self.assertEqual(record["closedNs"], str(341 * NS))
        self.assertEqual(record["originalReaderOutcome"], "PENDING_ENCLOSING_PROCESS_CLOSE")
        self.assertEqual(record["qualification"], "NOT_ESTABLISHED")

    def test_stream_final_refuses_wrong_ready_before_zip_members_and_hash(self):
        for change in ("before", "ready", "scope", "size", "members", "hash"):
            values = self.final_inputs()
            if change == "before":
                values["before_sha256"] = "0" * 64
            elif change == "ready":
                ready = json.loads(values["ready_raw"])
                ready["scope"] = D.FINAL_SCOPE
                values["ready_raw"] = wire(ready)
            elif change == "scope":
                values["zip_result"]["scope"] = "UNKNOWN"
            elif change == "size":
                values["zip_result"]["zipBytes"] += 1
            elif change == "members":
                values["zip_result"]["members"][0]["sha256"] = "0" * 64
            else:
                values["zip_result"]["zipSha256"] = "not-a-sha256"
            self.reject(D.stream_final, **values)

    def test_stream_final_refuses_missing_close_and_noninteger_or_late_raw_time(self):
        for closed in (True, "341000000000", 340 * NS - 1, 395 * NS):
            values = self.final_inputs()
            values["closed_ns"] = closed
            self.reject(D.stream_final, **values)
        for close in (None, b"", b"x" * (D.H.LIMIT + 1)):
            values = self.final_inputs()
            values["close_raw"] = close
            self.reject(D.stream_final, **values)

    def test_public_header_hash_is_exact_vector_not_wire_bytes(self):
        vector = headers()
        values, epoch, digest = self.call(D.public_headers, vector)
        expected = hashlib.sha256(json.dumps(vector, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        self.assertEqual((values["date"], epoch, digest), (DATE, NOW, expected))

    def test_public_headers_refuse_duplicate_case_and_nontext(self):
        for vector in (headers() + ["date", DATE], headers() + ["Extra"], headers() + ["X-test", 1],
                headers() + ["X test", "bad"], headers() + ["X-test", "bad\r\nvalue"], tuple(headers())):
            self.reject(D.public_headers, vector)

    def test_public_headers_refuse_private_aged_and_intermediary_data(self):
        for vector in (headers() + ["Age", "1"], headers() + ["Via", "proxy"],
                headers() + ["X-Cache", "HIT"], headers() + ["Location", "https://elsewhere.invalid"],
                [part.replace("public,", "private,") for part in headers()]):
            self.reject(D.public_headers, vector)

    def test_public_headers_refuse_invalid_date_encoding_and_bound(self):
        for vector in (headers() + ["Content-Encoding", "gzip"], [part.replace("Sat,", "Fri,") for part in headers()],
                headers() + ["X-padding", "x" * 2049], []):
            self.reject(D.public_headers, vector)

    def test_upload_and_after_require_distinct_current_step_frontiers(self):
        for stage, count in (("upload", 5), ("after", 6)):
            job, _context = service(stage)
            rows = self.call(D.service_steps, job, NOW, stage)
            self.assertEqual(len(rows), count)
            self.assertEqual(rows[stage]["status"], "in_progress")
            self.assertTrue(all(row["conclusion"] == "success" for key, row in rows.items() if key != stage))

    def test_before_still_in_progress_cannot_authorize_create(self):
        job, _context = service()
        job["steps"][3].update(status="in_progress", conclusion=None, completed_at=None)
        self.reject(D.service_steps, job, NOW, "upload")

    def test_upload_refuses_an_intervening_completed_step_after_before(self):
        job, _context = service()
        row = {"name": "Unreviewed intervening writer", "number": 5, "status": "completed",
            "conclusion": "success", "started_at": "2026-09-26T00:00:08Z",
            "completed_at": "2026-09-26T00:00:08Z"}
        for existing in job["steps"][4:]:
            existing["number"] += 1
        job["steps"].insert(4, row)
        self.reject(D.service_steps, job, NOW, "upload")

    def test_after_refuses_an_intervening_completed_step_after_upload(self):
        job, _context = service("after")
        row = {"name": "Unreviewed intervening writer", "number": 6, "status": "completed",
            "conclusion": "success", "started_at": "2026-09-26T00:00:10Z",
            "completed_at": "2026-09-26T00:00:10Z"}
        job["steps"][5]["number"] += 1
        job["steps"].insert(5, row)
        self.reject(D.service_steps, job, NOW, "after")

    def test_a_number_gap_does_not_prove_terminal_adjacency(self):
        for stage, start in (("upload", 4), ("after", 5)):
            job, _context = service(stage)
            for row in job["steps"][start:]:
                row["number"] += 1
            self.reject(D.service_steps, job, NOW, stage)

    def test_after_refuses_upload_not_genuinely_completed_successfully(self):
        for conclusion in ("failure", "cancelled", "skipped", "neutral", "timed_out"):
            job, _context = service("after")
            job["steps"][4]["conclusion"] = conclusion
            self.reject(D.service_steps, job, NOW, "after")

    def test_steps_refuse_missing_duplicate_and_extra_fields(self):
        job, _context = service()
        job["steps"].pop(1)
        self.reject(D.service_steps, job, NOW, "upload")
        job, _context = service()
        job["steps"][1]["name"] = job["steps"][0]["name"]
        self.reject(D.service_steps, job, NOW, "upload")
        job, _context = service()
        job["steps"][0]["inventedSuccess"] = True
        self.reject(D.service_steps, job, NOW, "upload")

    def test_steps_refuse_wrong_number_type_and_order(self):
        for number in (True, 1, "2", 0):
            job, _context = service()
            job["steps"][1]["number"] = number
            self.reject(D.service_steps, job, NOW, "upload")

    def test_steps_refuse_future_time_and_unproven_skipped_required_row(self):
        for changes in ({"started_at": "2026-09-26T00:01:00Z"},
                {"status": "completed", "conclusion": "skipped", "started_at": None, "completed_at": None}):
            job, _context = service()
            job["steps"][1].update(changes)
            self.reject(D.service_steps, job, NOW, "upload")

    def test_steps_refuse_two_current_rows_or_a_queued_prior(self):
        for index in (0, 5):
            job, _context = service()
            job["steps"][index].update(status="in_progress", conclusion=None,
                started_at="2026-09-26T00:00:12Z", completed_at=None)
            self.reject(D.service_steps, job, NOW, "upload")

    def test_job_binds_whole_original_body_and_exact_runner_source(self):
        job, context = service()
        raw = wire(job)
        result = self.call(D.service_job, pending(), context, raw, headers(raw), stage="upload", now=NOW)
        self.assertEqual(result["jobId"], 9002)
        self.assertEqual(result["bodySha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["serviceEpoch"], NOW)
        self.assertNotIn("runnerName", result)

    def test_job_rejects_other_job_run_attempt_commit_ref_or_runner(self):
        for field, bad in (("id", 9004), ("run_id", 9004), ("run_attempt", 3), ("head_sha", "3" * 40),
                ("head_branch", "main"), ("runner_id", 9004), ("runner_name", "substituted-runner"),
                ("name", "other-job"), ("started_at", "2026-09-26T00:00:01Z")):
            job, context = service()
            job[field] = bad
            raw = wire(job)
            self.reject(D.service_job, pending(), context, raw, headers(raw), stage="upload", now=NOW)

    def test_job_rejects_wrong_host_group_completion_and_location(self):
        for field, bad in (("labels", ["self-hosted"]), ("runner_group_id", True), ("runner_group_name", "private"),
                ("status", "completed"), ("conclusion", "success"), ("completed_at", "2026-09-26T00:00:12Z"),
                ("url", "https://elsewhere.invalid/jobs/9002"), ("run_url", "https://elsewhere.invalid/runs/9001")):
            job, context = service()
            job[field] = bad
            raw = wire(job)
            self.reject(D.service_job, pending(), context, raw, headers(raw), stage="upload", now=NOW)

    def test_job_rejects_length_mismatch_and_stale_or_future_service_date(self):
        job, context = service()
        raw = wire(job)
        self.reject(D.service_job, pending(), context, raw, headers(), stage="upload", now=NOW)
        for now in (NOW - 1, NOW + 61):
            self.reject(D.service_job, pending(), context, raw, headers(raw), stage="upload", now=now)
        self.assertEqual(self.call(D.service_job, pending(), context, raw, headers(raw),
            stage="upload", now=NOW + 60)["serviceEpoch"], NOW)


if __name__ == "__main__":
    unittest.main(failfast=True)
