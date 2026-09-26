#!/usr/bin/env python3
"""Offline synthetic recovery/provider/approval controls, never real qualification.

No GitHub request, GPG execution, application/library build or download occurs.
The public-certificate fixture is deliberately unusable and every provider/run
and command verdict in this file is explicitly fabricated test input only.
"""

import argparse
import copy
import datetime
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[2]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


R = module("recovery_controls", "scripts/maven_recovery.py")
S = module("sample_fixture_only", "scripts/tests/publish-sample-release-test.py")
B = module("bundle_fixture_only", "scripts/tests/central-bundle-evidence-test.py")
P = S.R
SOURCE, TREE, VERSION = S.SOURCE, S.TREE, S.VERSION
CONTROLLER, CONTROLLER_TREE = "5" * 40, "6" * 40
NOW = S.NOW + 3600


def utc(offset):
    return datetime.datetime.fromtimestamp(S.NOW + offset, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def zipped(files):
    stream = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # Deliberate duplicate test input only.
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in files.items() if type(files) is dict else files:
                archive.writestr(name, raw)
    return stream.getvalue()


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        # Reuse only the source-defined data factory, not its previously passed
        # test methods or any historical runtime verdict.
        self.fixture = S.ReleaseTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)
        self.api, self.base = self.fixture.api, self.fixture.base
        self.frozen_plan = self.fixture.prepared(self.fixture.plan())
        self.frozen_hash = self.frozen_plan["frozenApplicationSet"]["sha256"]
        self.clock = mock.patch.object(R.time, "time", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.api.data["/git/commits/" + SOURCE] = {"sha": SOURCE, "tree": {"sha": TREE}}
        self.api.data["/git/commits/" + CONTROLLER] = {"sha": CONTROLLER, "tree": {"sha": CONTROLLER_TREE}}
        self.api.data["/git/ref/heads/main"] = {"object": {"sha": CONTROLLER}}
        for candidate in (SOURCE, CONTROLLER):
            self.api.data[f"/compare/{candidate}...{CONTROLLER}"] = {
                "status": "identical" if candidate == CONTROLLER else "ahead", "merge_base_commit": {"sha": candidate}}
        self.api.data["/actions/runs/900"]["conclusion"] = "failure"
        self.original_jobs = self.api.collections["/actions/runs/900/attempts/1/jobs"]
        original = self.original_jobs[2]
        original.update(conclusion="failure", started_at=utc(60), completed_at=utc(180), steps=[])
        for index, name in enumerate((*R.REQUIRED_STEPS, R.REMOTE, "Upload publication evidence"), start=1):
            original["steps"].append(self.step(index, name, 60 + (index - 1) * 10, 60 + index * 10,
                                               "failure" if name == R.REMOTE else "success"))
        self.signed_files = self.bundle()
        signed_step = next(x for x in original["steps"] if x["name"] == R.SIGNED_UPLOAD)
        deployment_step = next(x for x in original["steps"] if x["name"] == R.DEPLOYMENT_UPLOAD)
        invocation = self.invocation()
        suffix = f"{invocation['tag']}-900-1"
        self.add_artifact(9002, "maven-central-signed-bundle-" + suffix, self.signed_files,
                          900, SOURCE, invocation["tag"], R.P.timestamp(signed_step["started_at"]) - S.NOW + 1)
        self.deployment_files = self.deployment()
        self.add_artifact(9003, "maven-central-deployment-" + suffix, self.deployment_files,
                          900, SOURCE, invocation["tag"], R.P.timestamp(deployment_step["started_at"]) - S.NOW + 1)
        self.context = {"id": 1000, "attempt": 1, "source": CONTROLLER, "tree": CONTROLLER_TREE,
                        "workflowId": 89, "workflowPath": R.WORKFLOW}
        run = {**S.run(1000, R.WORKFLOW, CONTROLLER, "workflow_dispatch"), "workflow_id": 89, "name": R.NAME,
               "actor": S.OWNER, "triggering_actor": S.OWNER, "status": "in_progress", "conclusion": None}
        self.api.data["/actions/runs/1000"] = copy.deepcopy(run)
        self.api.data["/actions/runs/1000/attempts/1"] = copy.deepcopy(run)
        self.api.data["/actions/workflows/recover-maven-central.yml"] = {"id": 89, "path": R.WORKFLOW}
        self.api.collections["/actions/runs/1000/artifacts"] = []
        self.api.collections["/actions/runs/1000/attempts/1/jobs"] = [
            {"id": 1010, "name": "prepare-recovery", "run_id": 1000, "run_attempt": 1, "head_sha": CONTROLLER,
             "status": "completed", "conclusion": "success", "started_at": utc(300), "completed_at": utc(420),
             "steps": [self.step(1, R.PREPARE, 300, 360), self.step(2, R.REQUEST_UPLOAD, 360, 390)]},
            {"id": 1011, "name": "verify-recovery", "run_id": 1000, "run_attempt": 1, "head_sha": CONTROLLER,
             "status": "completed", "conclusion": "success", "started_at": utc(480), "completed_at": utc(2040),
             "steps": [self.step(1, R.AUTHORIZE, 480, 540), self.step(2, R.VERIFY_ORIGINALS, 600, 900),
                       self.step(3, R.VERIFY_CONSUMERS, 900, 1800), self.step(4, R.RECORD_RESULT, 1860, 1920),
                       self.step(5, R.RESULT_UPLOAD, 1920, 1980)]}]
        self.api.data["/environments/" + R.ENVIRONMENT] = {
            **copy.deepcopy(self.api.data["/environments/" + P.ENVIRONMENT]), "id": 602, "name": R.ENVIRONMENT}
        self.api.collections["/environments/" + R.ENVIRONMENT + "/deployment-branch-policies"] = [{"name": "main", "type": "branch"}]
        self.api.data["/actions/runs/1000/approvals"] = []
        self.request = self.descriptor = self.result = None

    @staticmethod
    def step(number, name, start, end, conclusion="success"):
        return {"number": number, "name": name, "status": "completed", "conclusion": conclusion,
                "started_at": utc(start), "completed_at": utc(end)}

    def invocation(self):
        return R.P.maven_source_identity(self.api, SOURCE, 900, 1, self.api.data["/actions/runs/900"],
                                         self.api.data["/actions/workflows/publish-maven-central.yml"])

    def bundle(self):
        files = {}
        for original in B.BASES:
            name = original.replace(B.VERSION, VERSION)
            data = b"SYNTHETIC NON-ARTIFACT " + name.encode()
            files[name] = data
            files[name + ".asc"] = b"SYNTHETIC DETACHED SIGNATURE, NOT CRYPTOGRAPHIC"
            for algorithm in ("md5", "sha1", "sha256", "sha512"):
                files[name + "." + algorithm] = hashlib.new(algorithm, data).hexdigest().encode() + b"\n"
        stem = "p2pkit-" + VERSION + "-central-bundle"
        binary = zipped(files)
        manifest = "".join(hashlib.sha256(raw).hexdigest() + "  " + name + "\n" for name, raw in sorted(files.items())).encode()
        summary = {"schemaVersion": 2, "group": "io.github.apdelrahman1911", "version": VERSION,
                   "signingKeyFingerprint": B.FINGERPRINT, "bundleFile": stem + ".zip", "bundleSha256": hashlib.sha256(binary).hexdigest(),
                   "bundleSizeBytes": len(binary), "signedFiles": 84, "sourceSha": SOURCE, "sourceTree": TREE,
                   "manifestSha256": hashlib.sha256(manifest).hexdigest(), "publicKeyFile": stem + ".public.asc",
                   "publicKeySha256": hashlib.sha256(B.PUBLIC).hexdigest()}
        return {stem + ".zip": binary, stem + ".manifest.sha256": manifest, stem + ".summary.json": P.encoded(summary),
                stem + ".public.asc": B.PUBLIC}

    def deployment(self):
        stem = "p2pkit-" + VERSION + "-central-bundle"
        summary = self.signed_files[stem + ".summary.json"]
        identifier = "01234567-89ab-cdef-0123-456789abcdef"
        rows = []
        for offset, kind, state, detail in (
                (131, "upload_started", "LOCAL", f"p2pkit-{VERSION}-{SOURCE[:12]}"),
                (132, "upload_accepted", "PENDING", identifier),
                (133, "deployment_state", "PUBLISHED", "poll_1"),
                (133, "publication_completed", "PUBLISHED", identifier)):
            rows.append({"timestamp": utc(offset).replace("Z", ".000Z"), "event": kind, "state": state, "detail": detail})
        files = {"bundle.sha256": (P.parsed(summary)["bundleSha256"] + "\n").encode(),
                 "commit-sha.txt": (SOURCE + "\n").encode(), "deployment-id.txt": (identifier + "\n").encode(),
                 "status.json": P.encoded({"deploymentState": "PUBLISHED", "deploymentId": identifier}),
                 "portal-events.jsonl": b"".join(P.encoded(row).replace(b"\n", b"") + b"\n" for row in rows)}
        files["deployment-receipt.json"] = P.encoded(R.D.receipt({"source": SOURCE, "tag": "v" + VERSION, "id": 900, "attempt": 1},
                                                               TREE, summary, files))
        return files

    def add_artifact(self, identifier, name, files, run, source, branch, created):
        raw = zipped(files)
        artifact = {"id": identifier, "name": name, "expired": False, "created_at": utc(created),
                    "expires_at": utc(created + 14 * 86400), "size_in_bytes": len(raw),
                    "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
                    "workflow_run": {"id": run, "head_sha": source, "head_branch": branch}}
        self.api.data[f"/actions/artifacts/{identifier}"] = artifact
        self.api.collections[f"/actions/runs/{run}/artifacts"].append(artifact)
        self.api.files[identifier] = raw
        return artifact

    def replace_artifact(self, identifier, files):
        raw = zipped(files)
        artifact = self.api.data[f"/actions/artifacts/{identifier}"]
        artifact.update(size_in_bytes=len(raw), digest="sha256:" + hashlib.sha256(raw).hexdigest())
        self.api.files[identifier] = raw

    def original(self, remaining=R.F.MAVEN_HEADROOM):
        with tempfile.TemporaryDirectory(dir=self.base) as temporary:
            return R.original_metadata(self.api, SOURCE, 900, 1, 9001, self.frozen_hash, Path(temporary), remaining_seconds=remaining)

    def make_request(self):
        if self.request is not None:
            return
        with tempfile.TemporaryDirectory(dir=self.base) as temporary, mock.patch.object(R.time, "time", return_value=S.NOW + 330):
            # A real crypto or subprocess call here would violate structural-only preparation.
            with mock.patch.object(R.subprocess, "run", side_effect=AssertionError("Unexpected external execution")):
                self.request = R.prepare(self.api, self.context, SOURCE, 900, 1, 9001, self.frozen_hash, Path(temporary))
        self.request_hash = hashlib.sha256(P.encoded(self.request)).hexdigest()
        self.add_artifact(10001, R.request_name(self.context), {R.REQUEST: P.encoded(self.request)}, 1000, CONTROLLER, "main", 365)
        self.api.data["/actions/runs/1000/approvals"] = [{"state": "approved", "user": S.OWNER, "comment": R.challenge(self.request),
            "environments": [{"id": 602, "name": R.ENVIRONMENT}]}]
        self.load_request()

    def load_request(self):
        with tempfile.TemporaryDirectory(dir=self.base) as temporary:
            request, self.descriptor = R.load_request(self.api, self.context, 10001, self.request_hash, Path(temporary),
                                                      remaining_seconds=R.F.MAVEN_HEADROOM)
        return request

    def command_receipt(self, purpose):
        start, end = (650, 700) if purpose == "remote" else (950, 1700)
        return {"recovery": self.context, "requestSha256": self.request_hash, "source": {"commit": SOURCE, "tree": TREE},
                "purpose": purpose, "command": R.COMMANDS[purpose], "script": {"bytes": 13, "sha256": "7" * 64},
                "startedAt": S.NOW + start, "completedAt": S.NOW + end, "wallSeconds": end - start,
                "exitCode": 0, "log": {"bytes": 50, "sha256": "8" * 64}, "ownedProcessGroupRetired": True}

    def make_result(self):
        if self.result is not None:
            return
        self.make_request()
        provider = self.api.collections["/actions/runs/1000/attempts/1/jobs"][1]
        # Explicitly synthetic provider result; this tests loader policy only.
        verification = {"deployment": self.request["deployment"],
                        "bundle": {**self.request["bundle"], "scope": "VERIFIED_PUBLIC_SIGNATURES", "signaturesVerified": True,
                                   "signerFingerprints": [B.FINGERPRINT]},
                        "remote": self.command_receipt("remote"), "consumers": self.command_receipt("consumers")}
        self.result = {"schema": 1, "scope": R.RESULT_SCOPE, "recovery": self.context, "request": self.descriptor,
                       "ownerApproval": R.approval(self.api, self.request), "original": self.request["original"],
                       "originalConclusion": "failure", "verification": verification,
                       "provider": {"id": 1011, "name": "verify-recovery", "startedAt": provider["started_at"],
                                    "steps": R.verification_steps(provider)},
                       "recordedAt": S.NOW + 1880, "expiresAt": self.request["original"]["expiresAt"]}
        self.result_hash = hashlib.sha256(P.encoded(self.result)).hexdigest()
        self.add_artifact(10002, R.result_name(self.context), {R.RESULT: P.encoded(self.result)}, 1000, CONTROLLER, "main", 1930)
        for path in ("/actions/runs/1000", "/actions/runs/1000/attempts/1"):
            self.api.data[path].update(status="completed", conclusion="success")

    def plan(self, bound=True):
        with tempfile.TemporaryDirectory(dir=self.base) as temporary:
            options = {"artifact_id": 10002, "expected_hash": self.result_hash} if bound else {}
            return R.publication_plan(self.api, 1000, 1, Path(temporary), **options)

    def rewrite_result(self):
        self.result_hash = hashlib.sha256(P.encoded(self.result)).hexdigest()
        self.replace_artifact(10002, {R.RESULT: P.encoded(self.result)})

    def arguments(self, **values):
        args = {"source": SOURCE, "maven_run": "900", "maven_attempt": "1", "frozen_artifact": "9001",
                "frozen_sha256": self.frozen_hash, "authority": "recovery", "recovery_run": "1000", "recovery_attempt": "1",
                "recovery_artifact": "10002", "recovery_sha256": self.result_hash}
        args.update(values)
        return argparse.Namespace(**args)

    def test_original_failed_attempt_is_never_relabelled_success(self):
        value = self.original()
        self.assertEqual("failure", value["originalConclusion"])
        self.assertEqual(8, len(value["qualification"]["artifacts"]) + len(value["qualification"]["evidence"]))
        self.assertEqual(self.frozen_plan["frozenApplicationSet"], value["frozenApplicationSet"])
        self.assertEqual("failure", self.api.data["/actions/runs/900"]["conclusion"])
        with self.assertRaises(ValueError):
            P.maven_publication(self.api, SOURCE, 900, 1)
        self.assertEqual([], self.api.mutations)

    def test_cancellation_success_later_rerun_and_preupload_failure_hold(self):
        original = copy.deepcopy(self.api.data["/actions/runs/900"])
        for change in ({"conclusion": "cancelled"}, {"conclusion": "success"}, {"run_attempt": 2}, {"status": "in_progress"}):
            with self.subTest(change=change):
                self.api.data["/actions/runs/900"] = {**original, **change}
                with self.assertRaises(ValueError):
                    self.original()
        self.api.data["/actions/runs/900"] = original
        for name in R.REQUIRED_STEPS:
            step = next(x for x in self.original_jobs[2]["steps"] if x["name"] == name)
            step["conclusion"] = "failure"
            with self.subTest(step=name), self.assertRaises(ValueError):
                self.original()
            step["conclusion"] = "success"

    def test_remote_tail_must_actually_run_and_be_the_only_failure(self):
        steps = self.original_jobs[2]["steps"]
        original = copy.deepcopy(steps)
        for mutation in (lambda: steps.pop(-2), lambda: steps[-2].update(conclusion="skipped"),
                         lambda: steps[-2].update(conclusion="success"), lambda: steps[0].update(conclusion="cancelled"),
                         lambda: steps[-1].update(name="Unreviewed failing step", conclusion="failure")):
            steps[:] = copy.deepcopy(original)
            mutation()
            with self.assertRaises(ValueError):
                self.original()
        steps[:] = copy.deepcopy(original)
        steps[-2]["conclusion"], steps[-1]["conclusion"] = "success", "failure"
        self.assertEqual("success", self.original()["jobs"]["publish-release"]["verificationTail"]["conclusion"])

    def test_original_artifacts_cannot_be_missing_ambiguous_expired_or_late(self):
        original = copy.deepcopy(self.api.collections["/actions/runs/900/artifacts"])
        for mutate in (lambda rows: rows.pop(), lambda rows: rows.append(copy.deepcopy(rows[-1])),
                       lambda rows: rows[-1].update(expired=True), lambda rows: rows[-1].update(created_at=utc(200))):
            rows = copy.deepcopy(original)
            mutate(rows)
            self.api.collections["/actions/runs/900/artifacts"] = rows
            with self.assertRaises(ValueError):
                self.original()

    def test_original_tree_gates_and_custody_are_live_not_frozen_success_claims(self):
        for change, restore in (
            (lambda: self.api.data["/git/commits/" + SOURCE]["tree"].update(sha=CONTROLLER_TREE),
             lambda: self.api.data["/git/commits/" + SOURCE]["tree"].update(sha=TREE)),
            (lambda: self.api.data["/actions/runs/900/approvals"].clear(),
             lambda: None),
        ):
            change()
            with self.assertRaises(ValueError):
                self.original()
            restore()

    def test_preparation_is_read_only_and_binds_controller_separately_from_source(self):
        self.make_request()
        self.assertEqual(CONTROLLER, self.request["recovery"]["source"])
        self.assertEqual(SOURCE, self.request["original"]["maven"]["source"])
        self.assertNotIn("signaturesVerified", self.request["bundle"])
        self.assertEqual(self.request, self.load_request())
        self.assertEqual([], self.api.mutations)

    def test_preparation_does_not_overwrite_existing_attempt_record(self):
        self.make_request()
        with tempfile.TemporaryDirectory(dir=self.base) as temporary, self.assertRaises(ValueError):
            R.prepare(self.api, self.context, SOURCE, 900, 1, 9001, self.frozen_hash, Path(temporary))

    def test_request_hash_artifact_source_and_prepare_step_must_match(self):
        self.make_request()
        self.request_hash = "0" * 64
        with self.assertRaises(ValueError):
            self.load_request()
        self.request_hash = hashlib.sha256(P.encoded(self.request)).hexdigest()
        artifact = self.api.data["/actions/artifacts/10001"]
        original = copy.deepcopy(artifact)
        for change in ({"created_at": utc(410)}, {"name": "other-attempt"}, {"workflow_run": {"id": 1000, "head_sha": SOURCE, "head_branch": "main"}}):
            artifact.clear()
            artifact.update(original, **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.load_request()

    def test_exact_recovery_environment_and_personal_approval_are_mandatory(self):
        self.make_request()
        value = self.api.data["/environments/" + R.ENVIRONMENT]
        original = copy.deepcopy(value)
        for mutate in (lambda: value.update(can_admins_bypass=True),
                       lambda: value["protection_rules"][1].update(prevent_self_review=True),
                       lambda: value["protection_rules"][1]["reviewers"][0]["reviewer"].update(id=123)):
            value.clear()
            value.update(copy.deepcopy(original))
            mutate()
            with self.assertRaises(ValueError):
                R.approval(self.api, self.request)
        value.clear()
        value.update(original)
        history = self.api.data["/actions/runs/1000/approvals"]
        approval = copy.deepcopy(history[0])
        for change in ({"state": "rejected"}, {"user": {**S.OWNER, "id": 1}}, {"comment": R.challenge(self.request).replace("1000/1", "1000/2")},
                       {"environments": [{"id": 600, "name": P.ENVIRONMENT}]}):
            history[:] = [{**approval, **change}]
            with self.subTest(change=change), self.assertRaises(ValueError):
                R.approval(self.api, self.request)

    def test_public_original_outer_digest_roster_links_and_duplicate_members_reject(self):
        value = self.original()
        artifact = value["artifacts"]["deployment"]
        self.api.files[9003] += b"different"
        with tempfile.TemporaryDirectory(dir=self.base) as temporary, self.assertRaises(ValueError):
            R.unpack(self.api, artifact, {name: R.P.JSON_LIMIT for name in self.deployment_files}, Path(temporary) / "out", total_limit=6 * R.P.JSON_LIMIT)
        for files in ([*self.deployment_files.items(), next(iter(self.deployment_files.items()))],
                      {**self.deployment_files, "../escape": b"synthetic"}):
            self.replace_artifact(9003, files)
            candidate = R.P.artifact_identity(self.api.data["/actions/artifacts/9003"], 900, SOURCE, "v" + VERSION)
            with tempfile.TemporaryDirectory(dir=self.base) as temporary, self.assertRaises(ValueError):
                R.unpack(self.api, candidate, {name: R.P.JSON_LIMIT for name in self.deployment_files}, Path(temporary) / "out", total_limit=6 * R.P.JSON_LIMIT)
        info = zipfile.ZipInfo("status.json")
        info.external_attr = (stat.S_IFLNK | 0o600) << 16
        self.replace_artifact(9003, [(info if key == "status.json" else key, raw) for key, raw in self.deployment_files.items()])
        candidate = R.P.artifact_identity(self.api.data["/actions/artifacts/9003"], 900, SOURCE, "v" + VERSION)
        with tempfile.TemporaryDirectory(dir=self.base) as temporary, self.assertRaises(ValueError):
            R.unpack(self.api, candidate, {name: R.P.JSON_LIMIT for name in self.deployment_files}, Path(temporary) / "out", total_limit=6 * R.P.JSON_LIMIT)

    def test_public_signature_path_uses_all_originals_and_fake_backend_only(self):
        original = self.original()
        calls = []
        def fake_gpg(arguments, **options):
            calls.append(arguments)
            self.assertIn("--no-auto-key-retrieve", arguments)
            if "--import" in arguments:
                output = b""
            elif "--list-keys" in arguments:
                output = B.listing()
            else:
                self.assertIn("--verify", arguments)
                output = B.status()
            return subprocess.CompletedProcess(arguments, 0, output)
        with tempfile.TemporaryDirectory(dir=self.base) as temporary, mock.patch.object(R.subprocess, "run", side_effect=fake_gpg), \
                mock.patch.object(B.E.shutil, "which", return_value="/synthetic-not-gpg"):
            deployment, inspection, bundle = R.inspect_originals(self.api, original, Path(temporary), signatures=True)
            self.assertEqual(84, sum("--verify" in row for row in calls))
            self.assertTrue(bundle.is_file())
            self.assertEqual("PUBLISHED", deployment["deployment"]["state"])
            self.assertTrue(R.signature_receipt(inspection, R.bundle_identity(inspection))["signaturesVerified"])

    def test_successful_recovery_is_separate_delivery_authority_only(self):
        self.make_result()
        plan = self.plan()
        self.assertNotIn("mavenPublication", plan)
        self.assertEqual("failure", plan["mavenRecovery"]["originalConclusion"])
        self.assertEqual(self.frozen_plan["artifacts"], plan["artifacts"])
        self.assertEqual(self.frozen_plan["evidence"], plan["evidence"])
        with mock.patch.object(R.subprocess, "run", side_effect=AssertionError("No rerun allowed")):
            self.assertEqual(plan, self.plan(bound=False))
            P.revalidate_plan(self.api, plan)
        self.assertEqual([], self.api.mutations)

    def test_no_missing_ambiguous_or_wrong_hash_result_selection(self):
        self.make_result()
        self.result_hash = "e" * 64
        with self.assertRaises(ValueError):
            self.plan()
        rows = self.api.collections["/actions/runs/1000/artifacts"]
        result = rows.pop()
        with self.assertRaises(ValueError):
            self.plan(bound=False)
        rows += [result, copy.deepcopy(result)]
        with self.assertRaises(ValueError):
            self.plan(bound=False)

    def test_completed_recovery_provider_failure_cancellation_or_rerun_cannot_authorize(self):
        self.make_result()
        path = "/actions/runs/1000"
        original = copy.deepcopy(self.api.data[path])
        for change in ({"conclusion": "failure"}, {"conclusion": "cancelled"}, {"run_attempt": 2}, {"head_sha": SOURCE}):
            self.api.data[path] = {**original, **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.plan()
        self.api.data[path] = original
        for job in self.api.collections["/actions/runs/1000/attempts/1/jobs"]:
            job["conclusion"] = "failure"
            with self.assertRaises(ValueError):
                self.plan()
            job["conclusion"] = "success"

    def test_required_verification_and_retention_steps_cannot_be_skipped(self):
        self.make_result()
        steps = self.api.collections["/actions/runs/1000/attempts/1/jobs"][1]["steps"]
        for step in steps:
            step["conclusion"] = "skipped"
            with self.subTest(name=step["name"]), self.assertRaises(ValueError):
                self.plan()
            step["conclusion"] = "success"

    def test_recovery_result_cannot_fake_unsigned_or_wrong_source_command_success(self):
        self.make_result()
        original = copy.deepcopy(self.result)
        for mutate in (lambda: self.result["verification"]["bundle"].update(signaturesVerified=False),
                       lambda: self.result["verification"]["bundle"].update(scope="UNVERIFIED_SYNTHETIC_STRUCTURE"),
                       lambda: self.result["verification"]["remote"]["source"].update(commit=CONTROLLER),
                       lambda: self.result["verification"]["consumers"].update(exitCode=1),
                       lambda: self.result["verification"]["consumers"].update(command=[R.CONSUMER_SCRIPT, "--latest-published"]),
                       lambda: self.result["verification"]["remote"].update(ownedProcessGroupRetired=False),
                       lambda: self.result.update(originalConclusion="success")):
            self.result = copy.deepcopy(original)
            mutate()
            self.rewrite_result()
            with self.assertRaises(ValueError):
                self.plan()

    def test_original_failure_tag_and_original_custody_must_remain_unchanged_after_recovery(self):
        self.make_result()
        originals = copy.deepcopy(self.api.data)
        for change in (lambda: self.api.data["/actions/runs/900"].update(conclusion="success"),
                       lambda: self.api.data["/git/ref/tags/v" + VERSION]["object"].update(sha=CONTROLLER),
                       lambda: self.api.data["/actions/artifacts/9001"].update(expired=True),
                       lambda: self.api.data["/actions/runs/900/approvals"].clear(),
                       lambda: self.api.data["/actions/runs/1000/approvals"].clear()):
            self.api.data = copy.deepcopy(originals)
            change()
            with self.assertRaises(ValueError):
                self.plan()

    def test_provider_step_and_result_upload_timing_are_bound(self):
        self.make_result()
        original = copy.deepcopy(self.result)
        for mutate in (lambda: self.result["provider"].update(id=9999),
                       lambda: self.result.update(recordedAt=S.NOW + 1930),
                       lambda: self.result["verification"]["consumers"].update(startedAt=S.NOW + 850)):
            self.result = copy.deepcopy(original)
            mutate()
            self.rewrite_result()
            with self.assertRaises(ValueError):
                self.plan()

    def test_source_checkout_is_exact_and_separate_without_version_overrides(self):
        original = self.base / "original"
        original.mkdir()
        (original / "gradle.properties").write_text("VERSION_NAME=" + VERSION + "\n")
        with mock.patch.object(R.P.PACK, "git", side_effect=[SOURCE.encode(), TREE.encode(), b""]):
            R.verify_checkout(original, SOURCE, TREE, VERSION)
        for values in ([CONTROLLER.encode(), TREE.encode(), b""], [SOURCE.encode(), CONTROLLER_TREE.encode(), b""],
                       [SOURCE.encode(), TREE.encode(), b" M changed"]):
            with mock.patch.object(R.P.PACK, "git", side_effect=values), self.assertRaises(ValueError):
                R.verify_checkout(original, SOURCE, TREE, VERSION)
        (original / "gradle.properties").write_text("VERSION_NAME=0.8.1\n")
        with mock.patch.object(R.P.PACK, "git", side_effect=[SOURCE.encode(), TREE.encode(), b""]), self.assertRaises(ValueError):
            R.verify_checkout(original, SOURCE, TREE, VERSION)

    def test_command_environment_has_no_token_signing_or_test_profile_override(self):
        folder = self.base / "environment"
        folder.mkdir()
        env = {"PATH": "/synthetic-bin", "JAVA_HOME": "/synthetic-java", "ANDROID_HOME": "/synthetic-sdk",
               "GH_TOKEN": "not-a-credential", "MAVEN_SIGNING_PASSWORD": "not-a-secret", "JAVA_TOOL_OPTIONS": "unsafe",
               "P2PKIT_CENTRAL_TEST_MODE": "1", "P2PKIT_CONSUMER_PROFILE": "lan-jvm-android", "HOME": "/borrowed"}
        actual = R.execution_environment(env, folder, "consumers")
        self.assertFalse(set(actual) & {"GH_TOKEN", "MAVEN_SIGNING_PASSWORD", "JAVA_TOOL_OPTIONS", "P2PKIT_CENTRAL_TEST_MODE"})
        self.assertEqual("complete", actual["P2PKIT_CONSUMER_PROFILE"])
        self.assertEqual("https://repo.maven.apache.org/maven2", actual["P2PKIT_CONSUMER_REPOSITORY_URL"])
        self.assertEqual(str(folder / "home"), actual["HOME"])
        self.assertEqual(str(folder / "consumer"), actual["P2PKIT_CONSUMER_WORK_DIR"])

    def test_owned_workspace_never_claims_existing_or_replaced_directories(self):
        path = R.owned_directory(self.base, self.context, create=True)
        self.assertEqual(path, R.owned_directory(self.base, self.context, create=False))
        with self.assertRaises(FileExistsError):
            R.owned_directory(self.base, self.context, create=True)
        (path / ".owner.json").write_bytes(P.encoded({"wrong": "owner"}))
        with self.assertRaises(ValueError):
            R.owned_directory(self.base, self.context, create=False)

    def test_hosted_context_requires_current_main_controller_and_correct_job(self):
        env = {**S.hosted_env(), "GITHUB_WORKFLOW_REF": P.REPO + "/" + R.WORKFLOW + "@refs/heads/main",
               "GITHUB_SHA": CONTROLLER, "GITHUB_WORKFLOW_SHA": CONTROLLER, "GITHUB_RUN_ID": "1000",
               "GITHUB_JOB": "prepare-recovery", "RUNNER_OS": "Linux"}
        with mock.patch.object(R, "verify_checkout") as checkout:
            self.assertEqual(self.context, R.hosted_context(self.api, env, "prepare"))
            checkout.assert_called_once_with(R.ROOT, CONTROLLER, CONTROLLER_TREE)
        for change in ({"GITHUB_ACTIONS": "false"}, {"RUNNER_ENVIRONMENT": "self-hosted"}, {"GITHUB_REF": "refs/heads/other"},
                       {"GITHUB_SHA": SOURCE}, {"GITHUB_JOB": "verify-recovery"}, {"RUNNER_OS": "macOS"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                R.hosted_context(self.api, {**env, **change}, "prepare")

    def test_final_record_joins_current_provider_and_both_exact_original_source_receipts(self):
        self.make_result()
        for path in ("/actions/runs/1000", "/actions/runs/1000/attempts/1"):
            self.api.data[path].update(status="in_progress", conclusion=None)
        provider = self.api.collections["/actions/runs/1000/attempts/1/jobs"][1]
        provider.update(status="in_progress", conclusion=None, completed_at=None)
        directory = self.fixture.output("finishing")
        original = self.result["verification"]
        R.write_record(directory, "verified-originals.json", {key: original[key] for key in ("deployment", "bundle", "remote")})
        R.write_record(directory, "verified-consumers.json", original["consumers"])
        with mock.patch.object(R, "verify_checkout") as checkout, \
                mock.patch.object(R.P.PACK, "file_hash", return_value=original["consumers"]["script"]), \
                mock.patch.object(R.time, "time", return_value=S.NOW + 1880):
            result = R.finish(self.api, self.request, self.descriptor, self.result["ownerApproval"], directory, self.base / "original")
            self.assertEqual(self.result, result)
            checkout.assert_called_once_with(self.base / "original", SOURCE, TREE, VERSION)
            (directory / "verified-consumers.json").unlink()
            with self.assertRaises(OSError):
                R.finish(self.api, self.request, self.descriptor, self.result["ownerApproval"], directory, self.base / "original")

    def test_final_delivery_needs_twenty_minutes_not_a_new_recovery_window_or_new_expiry(self):
        self.make_result()
        expiry = P.timestamp(self.result["expiresAt"])
        with mock.patch.object(R.time, "time", return_value=expiry - 3600):
            with self.assertRaises(ValueError):
                self.original()  # A NEW 110-minute recovery cannot fit here.
            self.assertEqual(self.result["expiresAt"], self.original(R.F.DELIVERY_HEADROOM)["expiresAt"])
            self.assertEqual(self.result["expiresAt"], self.plan()["mavenRecovery"]["expiresAt"])
        with mock.patch.object(R.time, "time", return_value=expiry - R.F.DELIVERY_HEADROOM), self.assertRaises(ValueError):
            self.plan()

    def test_verify_originals_unknown_close_keeps_exact_child_input_outside_metadata_cleanup(self):
        self.make_request()
        provider = self.api.collections["/actions/runs/1000/attempts/1/jobs"][1]
        provider.update(status="in_progress", conclusion=None, completed_at=None)
        output = R.owned_directory(self.base, self.context, create=True)
        R.write_record(output, "authorization.json", {"request": self.descriptor, "approval": R.approval(self.api, self.request)})
        paths = []
        def synthetic_inspection(api, original, directory, *, signatures):
            self.assertTrue(signatures)  # Accepting path must never request structural-only mode.
            names = {name: R.P.ARCHIVE_LIMIT for name in self.signed_files}
            R.unpack(api, original["artifacts"]["signedBundle"], names, directory / "signed", total_limit=R.P.ARCHIVE_LIMIT)
            bundle = directory / "signed" / ("p2pkit-" + VERSION + "-central-bundle.zip")
            paths.append(bundle)
            return self.request["deployment"], {**self.request["bundle"], "signaturesVerified": True,
                "scope": "VERIFIED_PUBLIC_SIGNATURES", "signerFingerprints": [B.FINGERPRINT]}, bundle
        def unknown_close(request, original_root, purpose, work, deadline, bundle):
            self.assertEqual(paths[0], bundle)
            (work / "command.log").write_bytes(b"synthetic unknown-close original; do not print")
            raise R.P.Hold("SYNTHETIC_UNKNOWN_RETIREMENT")
        arguments = ["maven_recovery.py", "verify-originals", "--request-artifact", "10001", "--request-sha256", self.request_hash,
                     "--original-root", str(self.base / "original-source")]
        transcript = io.StringIO()
        with mock.patch.object(R, "ReadOnlyApi", return_value=self.api), mock.patch.object(R, "hosted_context", return_value=self.context), \
                mock.patch.object(R, "inspect_originals", side_effect=synthetic_inspection), mock.patch.object(R, "run_command", side_effect=unknown_close), \
                mock.patch("sys.argv", arguments), mock.patch("sys.stdout", transcript):
            self.assertEqual(1, R.main())
        self.assertEqual(output / "originals" / "signed" / ("p2pkit-" + VERSION + "-central-bundle.zip"), paths[0])
        self.assertTrue(paths[0].is_file())
        self.assertTrue((output / "remote-command" / "command.log").is_file())
        self.assertFalse((output / "verified-originals.json").exists())
        self.assertNotIn("synthetic unknown-close original", transcript.getvalue())

    def test_read_only_api_cannot_upload_sign_or_mutate(self):
        api = R.ReadOnlyApi("synthetic-not-a-credential")
        with mock.patch.object(R.P.Api, "open", side_effect=AssertionError("No network allowed")):
            for method in ("POST", "PATCH", "PUT", "DELETE"):
                with self.subTest(method=method), self.assertRaises(ValueError):
                    api.open(R.P.API + R.P.PREFIX + "/releases", method=method)

    def test_sample_recovery_event_derives_original_source_not_controller_source(self):
        self.make_result()
        event = {"name": R.NAME, "id": 1000, "run_attempt": 1, "head_sha": CONTROLLER, "head_branch": "main", "event": "workflow_dispatch"}
        self.assertEqual(SOURCE, P.trigger_source(self.api, event))
        self.assertEqual(SOURCE, P.select_delivery_plan(self.api, self.arguments(), event)["source"]["commit"])
        for change in ({"head_sha": SOURCE}, {"head_branch": "v" + VERSION}, {"event": "push"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                P.select_delivery_plan(self.api, self.arguments(), {**event, **change})

    def test_manual_recovery_delivery_requires_all_exact_original_and_result_bindings(self):
        self.make_result()
        self.assertEqual(self.plan(), P.select_delivery_plan(self.api, self.arguments()))
        for field in ("source", "maven_run", "maven_attempt", "frozen_artifact", "frozen_sha256", "recovery_run", "recovery_attempt",
                      "recovery_artifact", "recovery_sha256"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                P.select_delivery_plan(self.api, self.arguments(**{field: ""}))
        for change in ({"source": CONTROLLER}, {"maven_run": "901"}, {"maven_attempt": "2"}, {"frozen_artifact": "9002"},
                       {"frozen_sha256": "e" * 64}, {"authority": "maven"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                P.select_delivery_plan(self.api, self.arguments(**change))

    def test_sample_delivery_cannot_have_dual_or_missing_authority(self):
        self.make_result()
        plan = self.plan()
        with self.assertRaises(ValueError):
            P.revalidate_plan(self.api, {**plan, "mavenPublication": self.invocation()})
        with self.assertRaises(ValueError):
            P.delivery_authority({key: value for key, value in plan.items() if key != "mavenRecovery"})

    def test_recovery_does_not_replace_fresh_sample_postbuild_owner_approval(self):
        self.make_result()
        plan = self.plan()
        descriptor = self.fixture.authorization(plan)
        self.api.data["/actions/runs/400/approvals"] = []
        with self.assertRaises(ValueError):
            P.publish(self.api, plan, self.fixture.output("blocked-publication"), True, descriptor)
        self.assertEqual([], self.api.mutations)

    def test_sample_publication_promotes_only_frozen_apps_and_records_original_failure(self):
        self.make_result()
        plan = self.plan()
        descriptor = self.fixture.authorization(plan)
        result = P.publish(self.api, plan, self.fixture.output("recovery-publication"), True, descriptor)
        self.assertEqual("PUBLISHED_DEVELOPMENT_PRERELEASE", result["result"])
        self.assertEqual(7, len(self.api.public_probes))
        self.assertEqual({"apk", "msi", "dmg", "deb"}, {x["file"].rsplit(".", 1)[1] for x in result["assets"] if x.get("artifactId")})
        self.assertIn("remains **FAILED**", self.api.release["body"])
        self.assertIn("/actions/runs/1000", self.api.release["body"])
        self.assertEqual("failure", self.api.data["/actions/runs/900"]["conclusion"])
        self.assertFalse(any("recovery-result" in x["file"] or "evidence" in x["file"] for x in result["assets"]))


class CommandControls(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="p2pkit-recovery-command-control-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.source = self.base / "original"
        (self.source / "scripts").mkdir(parents=True)
        (self.source / R.CONSUMER_SCRIPT).write_bytes(b"synthetic script; not executed\n")
        self.work = self.base / "owned-command"
        self.work.mkdir()
        self.request = {"recovery": {"id": 1, "attempt": 1, "source": CONTROLLER, "tree": CONTROLLER_TREE},
                        "original": {"maven": {"source": SOURCE, "version": VERSION}, "tree": TREE}}
        self.checkout = mock.patch.object(R, "verify_checkout")
        self.checkout.start()
        self.addCleanup(self.checkout.stop)
        self.environment = mock.patch.dict(os.environ, {"PATH": "/synthetic", "JAVA_HOME": "/synthetic-java", "ANDROID_HOME": "/synthetic-sdk"}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def run_fake(self, code=0, *, running=False, retirement_error=False, large_output=False, rollback=False):
        process = mock.Mock(pid=123456789, returncode=None if running else code)
        process.poll.return_value = None if running else code
        process.wait.return_value = code
        def spawn(command, **options):
            self.assertEqual(["bash", str(self.source / R.CONSUMER_SCRIPT)], command)
            self.assertEqual("complete", options["env"]["P2PKIT_CONSUMER_PROFILE"])
            self.assertNotIn("GH_TOKEN", options["env"])
            options["stdout"].write(b"synthetic command output only\n")
            options["stdout"].flush()
            return process
        with mock.patch.object(R.subprocess, "Popen", side_effect=spawn) as popen, \
                mock.patch.object(R, "group_exists", return_value=False), \
                mock.patch.object(R, "retire_group", side_effect=OSError("synthetic retirement failure") if retirement_error else None) as retire, \
                mock.patch.object(R.time, "time", side_effect=[100.0, 20.0] if rollback else None, return_value=100.0), \
                mock.patch.object(R.time, "monotonic", side_effect=[0.0, 61.0] if running else None, return_value=0.0), \
                mock.patch.object(R.time, "sleep"), mock.patch.object(R, "LOG_LIMIT", 1 if large_output else 64 * R.P.MIB):
            try:
                return R.run_command(self.request, self.source, "consumers", self.work, 160.0)
            finally:
                self.assertEqual(1, popen.call_count)
                if running:
                    self.assertEqual(1, retire.call_count)

    def test_success_records_exact_source_and_retains_owned_local_command_original(self):
        receipt = self.run_fake()
        self.assertEqual(SOURCE, receipt["source"]["commit"])
        self.assertEqual(0, receipt["exitCode"])
        self.assertEqual("PASS", R.read_record(self.work, "command-status.json")["result"])
        self.assertTrue((self.work / "command.log").is_file())

    def test_failure_preserves_original_output_and_sanitized_phase_exit(self):
        with self.assertRaisesRegex(ValueError, "Original consumers verification failed"):
            self.run_fake(code=7)
        status = R.read_record(self.work, "command-status.json")
        self.assertEqual(7, status["exitCode"])
        self.assertEqual("exit", status["phase"])
        self.assertEqual("synthetic command output only\n", (self.work / "command.log").read_text())
        self.assertNotIn("synthetic command output", P.encoded(status).decode())

    def test_monotonic_fence_prevents_wall_rollback_from_extending_execution(self):
        with self.assertRaisesRegex(ValueError, "remaining job/output safety budget"):
            self.run_fake(running=True, rollback=True)
        self.assertTrue((self.work / "command.log").is_file())
        self.assertEqual("execution", R.read_record(self.work, "command-status.json")["phase"])

    def test_retirement_failure_does_not_mask_primary_or_remove_originals(self):
        with self.assertRaisesRegex(ValueError, "remaining job/output safety budget"):
            self.run_fake(running=True, retirement_error=True)
        status = R.read_record(self.work, "command-status.json")
        self.assertEqual("OSError", status["retirementErrorType"])
        self.assertEqual("Hold", status["errorType"])
        self.assertTrue((self.work / "command.log").is_file())

    def test_output_bound_failure_is_not_a_success_receipt(self):
        with self.assertRaises(ValueError):
            self.run_fake(large_output=True)
        self.assertEqual("HOLD", R.read_record(self.work, "command-status.json")["result"])
        self.assertTrue((self.work / "command.log").is_file())


if __name__ == "__main__":
    unittest.main(failfast=True)
