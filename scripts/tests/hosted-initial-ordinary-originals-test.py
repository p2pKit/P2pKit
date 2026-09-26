#!/usr/bin/env python3
"""Offline Stage2 composition models, NOT genuine original acquisition.

Supplied Git/HTTP/clock data exercise the dormant seam and real record parsers.
No actual environment entry, native owner, network, child, key or CI is used.
Only committed public policy and synthetic fixture builders are read; earlier
test methods/suites are not executed or treated as current qualification.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
import copy
import ctypes  # Stdlib initialization before the native-loading audit guard.
from datetime import datetime, timezone
from email.utils import format_datetime
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_ordinary_originals as A

spec = importlib.util.spec_from_file_location("ordinary_originals_gate_fixture",
    Path(__file__).with_name("hosted-initial-recipient-gate-test.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
F, S, I, O = G.F, A.stages, A.I, A.origin
TOKEN, INVOCATION = "SYNTHETIC_READ_TOKEN_NOT_A_CREDENTIAL", "e" * 32


class ModelGit:
    def __init__(self):
        self.head, self.source_tree, self.reviewed_tree, self.historical_tree = F.MERGE, F.T2, F.T2, F.T1
        self.main, self.main_tree = S.BASE["commit"], S.BASE["tree"]
        self.parents_value = [self.main, F.H2]
        self.base_entry, self.entry, self.policy_raw = b"", F.ENTRY, F.POLICY
        self.ancestry, self.prior, self.shallow = self.main.encode() + b"\n", F.H1.encode() + b"\n", b"false\n"
        self.root_value, self.clean_value, self.failure = True, True, None
        self.calls, self.after_query = [], lambda: None

    def root_matches(self): return self.root_value
    def clean(self): return self.clean_value
    def commit(self, ref):
        assert ref in ("HEAD", "refs/remotes/origin/main")
        return self.head if ref == "HEAD" else self.main
    def parents(self, commit):
        assert commit == F.MERGE
        return list(self.parents_value)
    def tree(self, commit):
        return {F.MERGE: self.source_tree, F.H2: self.reviewed_tree,
                F.H1: self.historical_tree, S.BASE["commit"]: self.main_tree}[commit]

    def query(self, *args, limit=4096):
        self.calls.append(args)
        if self.failure is not None:
            raise self.failure
        if args == ("rev-parse", "--is-shallow-repository"):
            raw = self.shallow
        elif args == ("merge-base", S.BASE["commit"], F.H2):
            raw = self.ancestry
        elif args == ("merge-base", F.H1, F.H2):
            raw = self.prior
        elif args == ("ls-tree", "-z", S.BASE["commit"], "--", I.POLICY_PATH):
            raw = self.base_entry
        elif args == ("ls-tree", "-z", F.H2, "--", I.POLICY_PATH):
            raw = self.entry
        elif args == ("cat-file", "-s", F.BLOB):
            raw = str(len(self.policy_raw)).encode("ascii") + b"\n"
        elif args == ("cat-file", "blob", F.BLOB):
            assert limit == I.POLICY_LIMIT
            raw = self.policy_raw
        else:
            raise AssertionError("UNEXPECTED_MODEL_GIT_QUERY")
        self.after_query()
        return raw


class OriginalModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.declaration, self.histories = F.stage2(F.stage1())
        self.comment = F.comment(self.declaration, 8002, F.START + 200)
        self.choose()
        self.stack.enter_context(patch.object(O.clocks, "observe", side_effect=self.observe))
        self.stack.enter_context(patch.object(O, "_request", side_effect=self.request))
        self.stack.enter_context(patch.object(A, "acquire_ordinary",
            side_effect=AssertionError("ACTUAL_ENVIRONMENT_ENTRY_FORBIDDEN")))

    def observe(self):
        self.ns += 1000
        return O.clocks.Reading(self.clock, self.ns)

    def choose(self, kind="gate", profile="desktop", role="linux-x64"):
        self.ns, self.git, self.requests, self.retained, self.retain_calls = 1000 * O.NS, ModelGit(), [], {}, []
        self.service_date, self.error, self.link = F.NOW, None, None
        self.after_response, self.envelope_change = lambda _label: None, lambda _value: None
        observed = F.observation2(self.declaration, profile, role)
        self.event = {"action": "synchronize", "number": 999,
            "repository": {"full_name": I.REPOSITORY, "default_branch": "main"},
            "pull_request": copy.deepcopy(observed["pullRequest"])}
        system, arch = ("Linux", "X64") if kind == "gate" else S.joint.ROLES[role]
        actual_role = "linux-x64" if kind == "gate" else role
        self.clock = O.clocks.ClockIdentity(actual_role, O.clocks.DOMAINS[actual_role],
                                           10_000_000 if actual_role == "windows-x64" else O.NS)
        self.fence = O.Fence(O.prelude(O.clocks.Reading(self.clock, self.ns)), minimum=self.ns, cancelled=lambda: None)
        workflow, worker, _ = I.PROFILES[profile]
        run = "401" if profile == "desktop" else "402"
        ref, branch = "refs/pull/999/merge", S.SOURCE_REF.removeprefix("refs/heads/")
        self.env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": I.REPOSITORY,
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
            "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": system, "RUNNER_ARCH": arch,
            "RUNNER_NAME": "SYNTHETIC runner", "GITHUB_JOB": A.gate.JOB if kind == "gate" else worker,
            "GITHUB_EVENT_NAME": "pull_request", "GITHUB_SHA": F.MERGE, "GITHUB_REF": ref,
            "GITHUB_WORKFLOW_SHA": F.MERGE, "GITHUB_WORKFLOW_REF": I.REPOSITORY + "/" + workflow + "@" + ref,
            "GITHUB_RUN_ID": run, "GITHUB_RUN_ATTEMPT": "1"}
        self.context = A._context(self.env, I.encoded(self.event), kind, F.FIRST2)
        base = A.API + "/actions/runs/" + run
        self.paths = {"attempt": base + "/attempts/1", "jobs": base + "/attempts/1/jobs?per_page=100&page=1",
            "approvals": base + "/approvals", "comment": A.API + "/issues/comments/8002",
            "environment": A.API + "/environments/initial-recipient-execution",
            "branches": A.API + "/environments/initial-recipient-execution/deployment-branch-policies?per_page=100&page=1",
            "main": A.API + "/git/ref/heads/main", "reviewed_ref": A.API + "/git/ref/heads/" + branch,
            "pull_request": A.API + "/pulls/999"}
        selector = A.GATE_SELECTOR if kind == "gate" else "macos-latest" if profile == "full" else O.wire.DESKTOP_HOSTS[(system, arch)][1]
        name = A.gate.JOB if kind == "gate" else "complete-gate" if profile == "full" else selector
        job = {"id": 901, "run_id": int(run), "run_attempt": 1, "name": name, "head_sha": F.H2,
            "head_branch": branch, "status": "in_progress", "conclusion": None, "completed_at": None,
            "started_at": F.utc(F.START + 210), "runner_id": 902, "runner_name": self.env["RUNNER_NAME"],
            "runner_group_id": 0, "runner_group_name": "GitHub Actions", "labels": [selector],
            "url": O.wire.ORIGIN + A.API + "/actions/jobs/901", "run_url": O.wire.ORIGIN + base}
        attempt_pr = {"number": 999,
            "base": {"sha": S.BASE["commit"], "ref": "main", "repo": {"url": O.wire.ORIGIN + A.API}},
            "head": {"sha": F.H2, "ref": branch, "repo": {"url": O.wire.ORIGIN + A.API}}}
        self.bodies = {"attempt": {"id": int(run), "run_attempt": 1, "repository": {"full_name": I.REPOSITORY},
                "head_repository": {"full_name": I.REPOSITORY}, "path": workflow, "event": "pull_request",
                "head_sha": F.H2, "head_branch": branch, "status": "in_progress", "conclusion": None,
                "pull_requests": [attempt_pr], "created_at": F.utc(F.START + 201), "run_started_at": F.utc(F.START + 202)},
            "jobs": {"total_count": 1, "jobs": [job]}, "comment": copy.deepcopy(self.comment),
            "approvals": [{"state": "approved", "user": dict(F.OWNER),
                "environments": [{"id": 101, "name": S.ENVIRONMENT}],
                "comment": f"AUTHORIZE_INITIAL_RECIPIENT stage2 {run}/1 8002 {F.body_hash(self.comment)}"}],
            "environment": G.environment(),
            "branches": {"total_count": 2, "branch_policies": copy.deepcopy(F.ENVIRONMENT["branchPolicies"])},
            "pull_request": copy.deepcopy(self.event["pull_request"])}
        if kind == "worker":
            self.bodies["jobs"] = {"total_count": 2, "jobs": [job, {**job, "id": 903, "name": A.gate.JOB,
                "url": O.wire.ORIGIN + A.API + "/actions/jobs/903", "labels": [A.GATE_SELECTOR],
                "status": "completed", "conclusion": "success", "started_at": F.utc(F.START + 204),
                "completed_at": F.utc(F.START + 209)}]}
        for label, branch_name, commit in (("main", "main", S.BASE["commit"]), ("reviewed_ref", branch, F.H2)):
            self.bodies[label] = {"ref": "refs/heads/" + branch_name,
                "url": O.wire.ORIGIN + A.API + "/git/refs/heads/" + branch_name,
                "object": {"type": "commit", "sha": commit, "url": O.wire.ORIGIN + A.API + "/git/commits/" + commit}}

    def request(self, path, token, invocation, fence, end):
        self.assertEqual((token, invocation), (TOKEN, INVOCATION))
        self.assertIs(fence, self.fence)
        label = next(label for label, expected in self.paths.items() if expected == path)
        self.requests.append((path, end))
        start = fence.now(limit=end)
        body = self.bodies[label]
        raw = body if type(body) is bytes else I.encoded(body)
        headers = ["HTTP/1.1 200 OK", "Date: " + format_datetime(datetime.fromtimestamp(self.service_date, timezone.utc), usegmt=True),
            "Content-Type: application/json", "Cache-Control: private, max-age=60, s-maxage=60",
            "X-GitHub-Request-Id: A1B2:C3D4:5678:90AB", "X-GitHub-Api-Version-Selected: 2022-11-28",
            "Connection: close", "Content-Length: " + str(len(raw))]
        if self.link is not None:
            headers.append("Link: " + self.link)
        value = {"schema": 1, "scope": O.RESPONSE_SCOPE, "origin": O.wire.ORIGIN, "method": "GET", "path": path,
            "invocation": invocation, "clock": O.clock_value(self.clock), "startedNs": start,
            "finishedNs": fence.now(limit=end), "status": 200,
            "headersBase64": base64.b64encode(("\r\n".join(headers) + "\r\n\r\n").encode("ascii")).decode("ascii"),
            "bodyBase64": base64.b64encode(raw).decode("ascii"), "complete": self.error is None,
            "retirement": "KNOWN", "error": None if self.error is None else "BOOTSTRAP_SERVICE_FAILED"}
        self.envelope_change(value)
        packet = O.encoded(value)
        self.after_response(label)
        return packet, self.error

    def retain(self, label, raw, *, failed):
        self.retain_calls.append((label, raw, failed))
        self.assertNotIn(label, self.retained)
        self.retained[label] = (raw, failed)

    def acquire(self, **options):
        args = dict(context=self.context, event_raw=I.encoded(self.event), git=self.git, invocation=INVOCATION,
            token=TOKEN, retain=self.retain, fence=self.fence, original_work_end=1045 * O.NS,
            now=lambda: F.NOW, histories=self.histories, expected=None)
        args.update(options)
        return A._acquire_ordinary(**args)

    def refuse(self, code=".+", **options):
        with self.assertRaisesRegex((I.AdmissionError, O.OriginError, O.wire.BudgetError), code):
            self.acquire(**options)

    def test_both_workflow_gates_use_nine_fixed_requests_and_remain_nonproductive(self):
        for profile, role in (("desktop", "linux-x64"), ("full", "macos-arm64")):
            with self.subTest(profile=profile):
                self.choose("gate", profile, role)
                result, originals = self.acquire()
                self.assertIs(type(result), A.gate.GateEligibility)
                value = json.loads(result.record)
                self.assertEqual(value["workerAdmission"], "NOT_PERFORMED")
                self.assertEqual(value["qualificationAcceptance"], "NOT_ESTABLISHED_BY_GATE")
                self.assertEqual(value["source"], {"commit": F.MERGE, "tree": F.T2})
                self.assertEqual(value["policy"]["commit"], F.H2)
                self.assertEqual([path for path, _ in self.requests], list(self.paths.values()))
                self.assertEqual(dict(originals), {label: raw for label, (raw, _) in self.retained.items()})
                self.assertEqual(self.retained["base_policy_entry"], (b"", False))
                self.assertEqual(self.retained["prior_ancestry_raw"], (F.H1.encode() + b"\n", False))
                self.assertTrue(all(TOKEN.encode() not in raw for raw, _ in self.retained.values()))

    def test_four_workers_keep_h2_service_and_merge_source_without_native_admission(self):
        for profile, role in (("desktop", "linux-x64"), ("desktop", "windows-x64"),
                              ("desktop", "macos-arm64"), ("full", "macos-arm64")):
            with self.subTest(profile=profile, role=role):
                self.choose("worker", profile, role)
                result, _ = self.acquire()
                self.assertIs(type(result), S.OrdinaryMatch)
                self.assertNotIsInstance(result, I.Admission)
                value = json.loads(result.record)
                self.assertEqual(value["source"]["commit"], F.MERGE)
                self.assertEqual(value["reviewed"]["commit"], F.H2)
                self.assertEqual(value["stage1"]["reviewed"]["commit"], F.H1)
                self.assertEqual(value["qualificationAcceptance"], "NOT_ESTABLISHED_BY_REFERENCE_MATCH")

    def test_context_rejects_source_workflow_host_or_event_substitution(self):
        for key, bad in (("GITHUB_SHA", F.H2), ("GITHUB_WORKFLOW_SHA", F.H2), ("GITHUB_REF", S.SOURCE_REF),
                ("GITHUB_EVENT_NAME", "push"), ("RUNNER_ENVIRONMENT", "self-hosted"), ("GITHUB_API_URL", "https://example.invalid"),
                ("GITHUB_JOB", "populate"), ("RUNNER_OS", "Windows"), ("GITHUB_RUN_ATTEMPT", "01")):
            with self.subTest(key=key), self.assertRaises(I.AdmissionError):
                A._context({**self.env, key: bad}, I.encoded(self.event), "gate", F.FIRST2)
        for kind, first in (("bootstrap", F.FIRST2), ("worker", True)):
            with self.assertRaises(I.AdmissionError):
                A._context(self.env, I.encoded(self.event), kind, first)

    def test_native_source_data_requires_full_history_ordered_parents_and_equal_merge_tree(self):
        for field, bad in (("head", F.H2), ("source_tree", F.T1), ("reviewed_tree", F.T1),
                ("main", F.H2), ("main_tree", F.T1), ("root_value", False), ("clean_value", False),
                ("shallow", b"true\n"), ("parents_value", [F.H2, S.BASE["commit"]])):
            with self.subTest(field=field):
                self.choose()
                setattr(self.git, field, bad)
                self.refuse()
                self.assertEqual(self.requests, [])

    def test_actual_empty_base_and_exact_h2_policy_are_required_not_missing_policy_fallback(self):
        for field, bad in (("base_entry", None), ("base_entry", b"\n"), ("base_entry", F.ENTRY),
                ("entry", F.ENTRY.replace(b"100644", b"120000")), ("policy_raw", F.POLICY + b"\n"),
                ("ancestry", F.H2.encode() + b"\n")):
            with self.subTest(field=field):
                self.choose()
                setattr(self.git, field, bad)
                self.refuse()
                self.assertEqual(self.requests, [])
        self.choose()
        self.git.failure = I.AdmissionError("MISSING_TRUSTED_RECIPIENT_POLICY")
        with self.assertRaises(I.AdmissionError) as caught:
            self.acquire()
        self.assertIs(caught.exception, self.git.failure)
        self.assertEqual(self.requests, [])

    def test_historical_h1_tree_and_ancestry_are_not_substituted_with_h2(self):
        for field, bad in (("historical_tree", F.T2), ("prior", F.H2.encode() + b"\n"), ("prior", b"")):
            with self.subTest(field=field):
                self.choose()
                setattr(self.git, field, bad)
                self.refuse("HISTORICAL")
                self.assertEqual(len(self.requests), 4)

    def test_service_attempt_and_job_require_h2_not_merge_or_historical_h1(self):
        for label in ("attempt", "job"):
            for wrong in (F.MERGE, F.H1):
                with self.subTest(label=label, wrong=wrong):
                    self.choose()
                    value = self.bodies["attempt"] if label == "attempt" else self.bodies["jobs"]["jobs"][0]
                    value["head_sha"] = wrong
                    self.refuse()
                    self.assertEqual(len(self.requests), 2)

    def test_worker_requires_exact_successful_predecessor_before_its_original_start(self):
        for field, bad in (("status", "in_progress"), ("conclusion", "failure"), ("run_attempt", 2),
                ("head_sha", F.MERGE), ("labels", ["self-hosted"]), ("completed_at", F.utc(F.START + 211))):
            with self.subTest(field=field):
                self.choose("worker")
                self.bodies["jobs"]["jobs"][1][field] = bad
                self.refuse("GATE_PREDECESSOR")
                self.assertEqual(len(self.requests), 2)

    def test_jobs_and_attempt_pr_are_complete_exact_original_records(self):
        for mutate in (lambda: self.bodies["jobs"].update(total_count=2),
                lambda: self.bodies["attempt"].update(pull_requests=[]),
                lambda: self.bodies["jobs"]["jobs"][0].update(runner_name="other"),
                lambda: self.bodies["jobs"]["jobs"][0].update(run_id=True)):
            self.choose()
            mutate()
            self.refuse()
            self.assertEqual(len(self.requests), 2)

    def test_missing_personal_challenge_environment_or_current_main_ref_never_becomes_a_match(self):
        for label, field, bad in (("approvals", "state", "rejected"),
                ("environment", "can_admins_bypass", True), ("main", "object", {"type": "commit", "sha": F.H2})):
            with self.subTest(label=label):
                self.choose()
                value = self.bodies[label][0] if label == "approvals" else self.bodies[label]
                value[field] = bad
                self.refuse()
                self.assertNotIn("match", self.retained)

    def test_current_pr_and_source_are_rechecked_after_all_nine_requests(self):
        for change in (lambda: self.bodies["pull_request"].update(state="closed"),
                       lambda: setattr(self.git, "source_tree", F.T1)):
            self.choose()
            self.after_response = lambda label: change() if label == "reviewed_ref" else None
            self.refuse()
            self.assertEqual(len(self.requests), 9)
            self.assertNotIn("match", self.retained)

    def test_original_absolute_fence_is_not_renewed_by_each_request(self):
        end = 1005 * O.NS
        self.acquire(original_work_end=end)
        self.assertEqual([limit for _, limit in self.requests], [end] * 9)
        self.assertLess(self.fence.last, end)
        self.choose()
        self.git.after_query = lambda: setattr(self, "ns", 1045 * O.NS)
        self.refuse("FENCE_EXPIRED")
        self.assertEqual(self.requests, [])

    def test_http_envelope_path_incomplete_close_and_link_are_not_supplied_success(self):
        for change in (lambda v: v.update(path="/repos/other/repo/actions/runs/401"),
                lambda v: v.update(retirement="UNKNOWN"), lambda v: v.update(complete=False),
                lambda v: v.update(startedNs=999 * O.NS)):
            self.choose()
            self.envelope_change = change
            self.refuse()
            self.assertEqual(len(self.requests), 1)
        self.choose()
        self.link = '<https://example.invalid/next>; rel="next"'
        self.refuse("INCOMPLETE_RESPONSE")
        self.assertEqual(len(self.requests), 1)

    def test_failed_transport_original_is_retained_once_and_never_retried(self):
        self.error = O.OriginError("MODEL_HTTP_FAILURE")
        with self.assertRaises(O.OriginError) as caught:
            self.acquire()
        self.assertIs(caught.exception, self.error)
        raw, failed = self.retained["attempt"]
        self.assertTrue(failed)
        self.assertFalse(json.loads(raw)["complete"])
        self.assertEqual(len([x for x in self.retain_calls if x[0] == "attempt"]), 1)
        self.assertEqual(len(self.requests), 1)

    def test_post_transport_work_expiry_offers_unchanged_original_once_to_final_retainer(self):
        self.after_response = lambda _label: setattr(self, "ns", 1045 * O.NS)
        def retain(label, raw, *, failed):
            if failed:
                self.fence.now(final=True)
            self.retain(label, raw, failed=failed)
        self.refuse("FENCE_EXPIRED", retain=retain)
        raw, failed = self.retained["attempt"]
        self.assertTrue(failed)
        self.assertTrue(json.loads(raw)["complete"])
        self.assertIsNone(json.loads(raw)["error"])
        self.assertEqual(len([x for x in self.retain_calls if x[0] == "attempt"]), 1)
        self.assertEqual(len(self.requests), 1)

    def test_primary_transport_failure_survives_one_failing_retention_attempt(self):
        self.error = KeyboardInterrupt("MODEL_PRIMARY_FAILURE")
        secondary, attempts = ValueError("MODEL_RETAINER_FAILURE"), []
        def retain(label, raw, *, failed):
            if label == "attempt":
                attempts.append((raw, failed))
                raise secondary
            self.retain(label, raw, failed=failed)
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.acquire(retain=retain)
        self.assertIs(caught.exception, self.error)
        self.assertIs(caught.exception.__cause__, secondary)
        self.assertEqual(len(attempts), 1)
        self.assertTrue(attempts[0][1])
        self.assertEqual(len(self.requests), 1)


if __name__ == "__main__":
    unittest.main(failfast=True)
