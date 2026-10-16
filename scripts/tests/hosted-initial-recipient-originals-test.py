#!/usr/bin/env python3
"""Offline original-acquisition controls: real parser/composition, modeled I/O.

No actual hosted identities, TLS/network, child/native owner or crypto execution.
Only the committed PUBLIC policy is read; all service records/IDs are synthetic.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
import copy
import ctypes  # Standard-library Python-API initialization precedes the guard.
from datetime import datetime, timezone
from email.utils import format_datetime
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


# No project import has occurred. Block all subsequent native-library loading,
# process and network operations; clock/native services are modeled below.
sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_originals as A

spec = importlib.util.spec_from_file_location("originals_gate_models", Path(__file__).with_name("hosted-initial-recipient-gate-test.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
F, I, S, O = G.F, A.identity, A.stages, A.origin
TOKEN = "SYNTHETIC_READ_TOKEN_NOT_A_CREDENTIAL"
INVOCATION = "e" * 32


class ModelGit:
    def __init__(self):
        self.calls = []
        self.head, self.tree_value = F.H1, F.T1
        self.main, self.main_tree = S.BASE["commit"], S.BASE["tree"]
        self.base_entry, self.entry, self.policy_raw = b"", F.ENTRY, F.POLICY
        self.ancestry, self.shallow = self.main.encode() + b"\n", b"false\n"
        self.clean_value, self.root_value = True, True
        self.failure = None

    def root_matches(self): return self.root_value
    def clean(self): return self.clean_value
    def commit(self, value): return self.head if value == "HEAD" else self.main
    def tree(self, value): return self.main_tree if value == S.BASE["commit"] else self.tree_value
    def policy(self, value):
        assert value == F.H1
        return F.BLOB, self.policy_raw

    def query(self, *args, limit=4096):
        self.calls.append(args)
        if self.failure is not None:
            raise self.failure
        if args == ("rev-parse", "--is-shallow-repository"):
            return self.shallow
        if args == ("merge-base", self.main, F.H1):
            return self.ancestry
        if args == ("ls-tree", "-z", self.main, "--", I.POLICY_PATH):
            return self.base_entry
        if args == ("ls-tree", "-z", F.H1, "--", I.POLICY_PATH):
            return self.entry
        if args == ("cat-file", "-s", F.BLOB):
            return str(len(self.policy_raw)).encode("ascii") + b"\n"
        if args == ("cat-file", "blob", F.BLOB):
            assert limit == I.POLICY_LIMIT
            return self.policy_raw
        raise AssertionError("Unexpected modeled Git query")


class OriginalModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.declaration = F.stage1()
        self.comment = F.comment(self.declaration, 8001, F.START - 60)
        self.git, self.retained, self.requests = ModelGit(), {}, []
        self.ns = 1000 * O.NS
        self.service_date = F.FIRST1
        self.link, self.request_error, self.before_request, self.after_close = None, None, lambda: None, lambda: None
        self.choose("gate", "full-macos-arm64")
        self.stack.enter_context(patch.object(O.clocks, "observe", side_effect=self.observe))
        self.stack.enter_context(patch.object(O.time, "monotonic", side_effect=lambda: self.ns / O.NS))
        self.stack.enter_context(patch.object(O.ssl, "create_default_context", return_value=object()))
        self.stack.enter_context(patch.object(O.http.client, "HTTPSConnection", side_effect=self.connection))

    def observe(self):
        self.ns += 1000
        return O.clocks.Reading(self.clock, self.ns)

    def choose(self, kind, selection):
        slot = next(x for x in self.declaration["bootstrap"] if x["selection"] == selection)
        _, role, system, arch = S.bootstrap.selection(selection)
        if kind == "gate":
            role, system, arch = "linux-x64", "Linux", "X64"
        self.clock = O.clocks.ClockIdentity(role, O.clocks.DOMAINS[role], 10_000_000 if role == "windows-x64" else O.NS)
        self.fence = O.Fence(O.prelude(O.clocks.Reading(self.clock, self.ns)), minimum=self.ns, cancelled=lambda: None)
        self.env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": I.REPOSITORY, "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_API_URL": "https://api.github.com", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": system,
            "RUNNER_ARCH": arch, "GITHUB_JOB": A.gate.JOB if kind == "gate" else "populate", "RUNNER_NAME": "SYNTHETIC runner",
            "GITHUB_RUN_ID": slot["runId"], "GITHUB_RUN_ATTEMPT": slot["runAttempt"], "GITHUB_SHA": F.H1,
            "GITHUB_WORKFLOW_SHA": F.H1, "GITHUB_REF": S.SOURCE_REF, "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_WORKFLOW_REF": I.REPOSITORY + "/" + S.bootstrap.WORKFLOW + "@" + S.SOURCE_REF}
        self.event = {"repository": {"full_name": I.REPOSITORY, "default_branch": "main"}, "ref": S.SOURCE_REF,
            "inputs": {"selection": selection, "expected_sha": F.H1, "expected_tree": F.T1}}
        self.context = A._context(self.env, I.encoded(self.event), kind, F.FIRST1)
        self.base = A.API + "/actions/runs/" + slot["runId"]
        self.paths = {"attempt": self.base + "/attempts/1", "jobs": self.base + "/attempts/1/jobs?per_page=100&page=1",
            "approvals": self.base + "/approvals", "comment": A.API + "/issues/comments/8001",
            "environment": A.API + "/environments/initial-recipient-execution",
            "branches": A.API + "/environments/initial-recipient-execution/deployment-branch-policies?per_page=100&page=1",
            "main": A.API + "/git/ref/heads/main", "reviewed_ref": A.API + "/git/ref/heads/" + S.SOURCE_REF[11:]}
        attempt = {"id": int(slot["runId"]), "run_attempt": 1, "repository": {"full_name": I.REPOSITORY},
            "head_repository": {"full_name": I.REPOSITORY}, "path": S.bootstrap.WORKFLOW, "event": "workflow_dispatch",
            "head_sha": F.H1, "head_branch": S.SOURCE_REF[11:], "status": "in_progress", "conclusion": None,
            "pull_requests": [], "created_at": F.utc(F.START - 30), "run_started_at": F.utc(F.START - 20)}
        job = {"id": 901, "run_id": int(slot["runId"]), "run_attempt": 1, "name": self.env["GITHUB_JOB"],
            "head_sha": F.H1, "head_branch": S.SOURCE_REF[11:], "status": "in_progress", "conclusion": None,
            "completed_at": None, "started_at": F.utc(F.START), "runner_id": 902, "runner_group_id": 0,
            "runner_group_name": "GitHub Actions", "runner_name": self.env["RUNNER_NAME"],
            "labels": [A.GATE_SELECTOR if kind == "gate" else O.SERVICE_SELECTORS[role]],
            "url": O.wire.ORIGIN + A.API + "/actions/jobs/901", "run_url": O.wire.ORIGIN + self.base}
        self.bodies = {"attempt": attempt, "jobs": {"total_count": 1, "jobs": [job]}, "comment": copy.deepcopy(self.comment),
            "approvals": [{"state": "approved", "user": dict(F.OWNER), "environments": [{"id": 101, "name": S.ENVIRONMENT}],
                "comment": f"AUTHORIZE_INITIAL_RECIPIENT stage1 {slot['runId']}/1 8001 {F.body_hash(self.comment)}"}],
            "environment": G.environment(), "branches": {"total_count": 2, "branch_policies": copy.deepcopy(F.ENVIRONMENT["branchPolicies"])}}
        if kind == "worker":
            self.bodies["jobs"] = {"total_count": 2, "jobs": [job, {**job, "id": 903, "name": A.gate.JOB,
                "url": O.wire.ORIGIN + A.API + "/actions/jobs/903", "labels": [A.GATE_SELECTOR],
                "status": "completed", "conclusion": "success", "started_at": F.utc(F.START - 5),
                "completed_at": F.utc(F.START)}]}
        for name, ref, commit in (("main", "main", S.BASE["commit"]), ("reviewed_ref", S.SOURCE_REF[11:], F.H1)):
            self.bodies[name] = {"ref": "refs/heads/" + ref, "url": O.wire.ORIGIN + A.API + "/git/refs/heads/" + ref,
                "object": {"type": "commit", "sha": commit, "url": O.wire.ORIGIN + A.API + "/git/commits/" + commit}}

    def connection(self, host, *, timeout, context):
        self.assertEqual(host, "api.github.com")
        self.assertTrue(0 < timeout <= 5)
        case = self
        class Socket:
            raw = b""
            def makefile(self, mode): return io.BytesIO(self.raw)
            def settimeout(self, value): case.assertTrue(0 < value <= 5)
        class Connection:
            def __init__(self): self.sock = Socket()
            def request(self, method, path, *, headers):
                case.requests.append((method, path, headers))
                case.before_request()
                if case.request_error is not None:
                    raise case.request_error
                label = next(k for k, value in case.paths.items() if value == path)
                body = case.bodies[label]
                raw = body if type(body) is bytes else I.encoded(body)
                fields = ["HTTP/1.1 200 OK", "Date: " + format_datetime(datetime.fromtimestamp(case.service_date, timezone.utc), usegmt=True),
                    "Content-Type: application/json; charset=utf-8", "Cache-Control: private, max-age=60, s-maxage=60",
                    "X-GitHub-Request-Id: A1B2:C3D4:5678:90AB", "X-GitHub-Api-Version-Selected: 2022-11-28",
                    "Connection: close", "Content-Length: " + str(len(raw))]
                if case.link is not None:
                    fields.append("Link: " + case.link)
                self.sock.raw = ("\r\n".join(fields) + "\r\n\r\n").encode("ascii") + raw
            def getresponse(self):
                value = self.response_class(self.sock, method="GET")
                value.begin()
                return value
            def close(self): case.after_close()
        return Connection()

    def retain(self, label, raw, *, failed):
        self.assertNotIn(label, self.retained)
        self.retained[label] = (raw, failed)

    def acquire(self, **changes):
        args = dict(context=self.context, event_raw=I.encoded(self.event), git=self.git, invocation=INVOCATION,
            token=TOKEN, retain=self.retain, fence=self.fence, original_work_end=1045 * O.NS,
            now=lambda: F.DONE1, expected=None)
        args.update(changes)
        return A._acquire_bootstrap(**args)

    def refuse(self, code=".+", **changes):
        with self.assertRaisesRegex((I.AdmissionError, O.OriginError, O.wire.BudgetError), code):
            self.acquire(**changes)

    def test_gate_composes_eight_original_gets_selects_only_named_comment_and_returns_no_admission(self):
        result, originals = self.acquire()
        self.assertIs(type(result), A.gate.GateEligibility)
        self.assertEqual(json.loads(result.record)["github"]["job"], A.gate.JOB)
        self.assertEqual(json.loads(result.record)["workerAdmission"], "NOT_PERFORMED")
        self.assertEqual([x[1] for x in self.requests], list(self.paths.values()))
        self.assertEqual(dict(originals), {k: v[0] for k, v in self.retained.items()})
        self.assertTrue(all(not failed for _, failed in self.retained.values()))
        self.assertTrue(all(TOKEN.encode() not in raw for raw, _ in self.retained.values()))
        self.assertTrue(all(method == "GET" and h["Authorization"] == "Bearer " + TOKEN for method, _, h in self.requests))
        self.assertEqual(self.retained["base_policy_entry"][0], b"")
        self.assertNotIsInstance(result, I.Admission)

    def test_all_six_worker_selections_keep_actual_native_role_and_do_not_return_admission(self):
        for selection in F.SELECTIONS:
            with self.subTest(selection=selection):
                self.ns, self.retained, self.requests = 1000 * O.NS, {}, []
                self.choose("worker", selection)
                result, _ = self.acquire()
                self.assertIs(type(result), S.BootstrapMatch)
                self.assertEqual(json.loads(result.record)["github"]["selection"], selection)
                self.assertEqual(json.loads(result.record)["policy"]["origin"], "reviewed-head")
                self.assertNotIsInstance(result, I.Admission)

    def test_unknown_context_kind_first_use_and_unhosted_labels_refuse(self):
        for kind, first in (("stage2", F.FIRST1), ("gate", True), ("gate", 0)):
            with self.assertRaises(I.AdmissionError): A._context(self.env, I.encoded(self.event), kind, first)
        for key, value in (("GITHUB_ACTIONS", "false"), ("RUNNER_ENVIRONMENT", "self-hosted"),
                           ("GITHUB_API_URL", "https://example.invalid"), ("GITHUB_RUN_ATTEMPT", "01")):
            with self.assertRaises(I.AdmissionError):
                A._context({**self.env, key: value}, I.encoded(self.event), "gate", F.FIRST1)

    def test_context_refuses_cross_job_host_source_workflow_and_unexpected_inputs(self):
        for key, value in (("GITHUB_JOB", "populate"), ("RUNNER_OS", "macOS"), ("GITHUB_SHA", F.H2),
                           ("GITHUB_WORKFLOW_SHA", F.H2), ("GITHUB_WORKFLOW_REF", "other"),
                           ("GITHUB_REF", "refs/heads/main"), ("GITHUB_EVENT_NAME", "pull_request")):
            with self.assertRaises(I.AdmissionError):
                A._context({**self.env, key: value}, I.encoded(self.event), "gate", F.FIRST1)
        self.event["inputs"]["commentId"] = 8001
        with self.assertRaises(I.AdmissionError): A._context(self.env, I.encoded(self.event), "gate", F.FIRST1)

    def test_context_checks_original_event_repo_ref_and_runner_name(self):
        for field, value in (("full_name", "other/repository"), ("default_branch", "other")):
            event = copy.deepcopy(self.event); event["repository"][field] = value
            with self.assertRaises(I.AdmissionError): A._context(self.env, I.encoded(event), "gate", F.FIRST1)
        for runner in (None, "", "bad\nrunner"):
            with self.assertRaises(I.AdmissionError):
                A._context({**self.env, "RUNNER_NAME": runner}, I.encoded(self.event), "gate", F.FIRST1)

    def test_dirty_wrong_tree_head_root_shallow_or_local_main_refuses_before_http(self):
        for name, bad in (("head", F.H2), ("tree_value", F.T2), ("main", F.H2), ("main_tree", F.T2),
                          ("clean_value", False), ("root_value", False), ("shallow", b"true\n")):
            self.git = ModelGit(); setattr(self.git, name, bad); self.retained = {}
            self.refuse(); self.assertEqual(self.requests, [])

    def test_base_policy_absence_requires_exact_success_not_caught_missing_policy_error(self):
        for raw in (b"error", F.ENTRY, b"120000 blob " + F.BLOB.encode() + b"\t" + I.POLICY_PATH.encode() + b"\0"):
            self.git.base_entry, self.retained = raw, {}
            self.refuse("BASE_POLICY_NOT_ABSENT")
        self.git = ModelGit(); self.retained = {}
        failure = I.AdmissionError("MISSING_TRUSTED_RECIPIENT_POLICY")
        self.git.failure = failure
        with self.assertRaises(I.AdmissionError) as caught: self.acquire()
        self.assertIs(caught.exception, failure); self.assertEqual(self.requests, [])

    def test_candidate_entry_and_policy_hash_cannot_change(self):
        self.git.entry = F.ENTRY.replace(b"100644", b"100755")
        self.refuse("POLICY_ENTRY_CHANGED")
        self.git, self.retained = ModelGit(), {}
        self.git.policy_raw += b"\n"
        self.refuse("POLICY_BLOB")

    def test_each_source_query_checks_the_same_original_end(self):
        original = self.git.query
        def late(*args, **kwargs):
            raw = original(*args, **kwargs)
            self.ns = 1045 * O.NS
            return raw
        self.git.query = late
        self.refuse("FENCE_EXPIRED")
        self.assertEqual(len(self.git.calls), 1)
        self.assertEqual(self.requests, [])

    def test_worker_requires_successful_same_attempt_gate_before_its_start(self):
        self.choose("worker", "desktop-linux-x64")
        original = copy.deepcopy(self.bodies["jobs"])
        self.bodies["jobs"]["jobs"].pop(); self.bodies["jobs"]["total_count"] = 1
        self.refuse("GATE_PREDECESSOR")
        for field, bad in (("status", "in_progress"), ("conclusion", "failure"), ("run_attempt", 2),
                           ("head_sha", F.H2), ("completed_at", F.utc(F.START + 1))):
            self.retained = {}; self.bodies["jobs"] = copy.deepcopy(original)
            self.bodies["jobs"]["jobs"][1][field] = bad
            self.refuse("GATE_PREDECESSOR")

    def test_source_is_queried_again_after_service_acquisition(self):
        def change():
            if len(self.requests) == 8: self.git.tree_value = F.T2
        self.before_request = change
        self.refuse("SOURCE"); self.assertNotIn("match", self.retained)

    def test_remote_main_or_reviewed_branch_advance_is_not_hidden_by_local_refs(self):
        for label in ("main", "reviewed_ref"):
            original = copy.deepcopy(self.bodies[label]); self.bodies[label]["object"]["sha"] = F.H2
            self.retained = {}; self.refuse("REF_COMMIT"); self.bodies[label] = original

    def test_remote_ref_location_type_and_object_url_are_exact(self):
        self.bodies["main"]["url"] += "/other"
        self.refuse("REF_LOCATION")
        self.retained = {}; self.bodies["main"]["url"] = O.wire.ORIGIN + A.API + "/git/refs/heads/main"
        self.bodies["main"]["object"]["type"] = "tag"
        self.refuse("REF_COMMIT")

    def test_current_attempt_is_bound_before_selector_acquisition(self):
        for field, bad in (("id", True), ("run_attempt", 2), ("head_sha", F.H2), ("status", "completed"),
                           ("event", "push"), ("path", ".github/workflows/ci.yml"), ("pull_requests", [{}])):
            old = self.bodies["attempt"][field]; self.bodies["attempt"][field] = bad; self.retained, self.requests = {}, []
            self.refuse("CURRENT_ATTEMPT"); self.assertEqual(len(self.requests), 2); self.bodies["attempt"][field] = old

    def test_jobs_require_complete_page_unique_id_actual_job_and_in_progress_state(self):
        self.bodies["jobs"]["total_count"] = 2
        self.refuse("COMPLETE_JOBS")
        self.retained = {}; self.bodies["jobs"]["jobs"] *= 2
        self.refuse("DUPLICATE_JOB")
        self.retained = {}; self.bodies["jobs"]["jobs"] = self.bodies["jobs"]["jobs"][:1]
        self.bodies["jobs"]["total_count"] = 1; self.bodies["jobs"]["jobs"][0]["name"] = "populate"
        self.refuse("EXACT_JOB")

    def test_actual_service_job_binds_runner_not_just_github_labels(self):
        job = self.bodies["jobs"]["jobs"][0]
        for field, bad in (("run_attempt", 2), ("run_id", True), ("head_sha", F.H2), ("completed_at", F.utc(F.START)),
                           ("runner_name", "other"), ("runner_id", 0), ("runner_group_id", True), ("labels", ["self-hosted"])):
            old = job[field]; job[field] = bad; self.retained = {}; self.refuse(); job[field] = old

    def test_unapproved_or_duplicate_challenges_never_fetch_a_comment(self):
        self.bodies["approvals"][0]["state"] = "rejected"
        self.refuse("OWNER_APPROVAL"); self.assertEqual(len(self.requests), 3)
        self.retained, self.requests = {}, []; self.bodies["approvals"][0]["state"] = "approved"
        self.bodies["approvals"] *= 2
        self.refuse("MISSING_OR_AMBIGUOUS_CHALLENGE"); self.assertEqual(len(self.requests), 3)

    def test_malformed_original_approval_json_is_not_saved_by_parser_wrapper(self):
        self.bodies["approvals"] = I.encoded(self.bodies["approvals"]).rstrip(b"\n") + b',"injected":true'
        self.refuse("HISTORY_SHAPE"); self.assertEqual(len(self.requests), 3)

    def test_selected_comment_location_digest_and_edited_state_are_rechecked(self):
        self.bodies["comment"]["body"] += " "
        self.refuse("COMMENT_DIGEST")
        self.retained = {}; self.bodies["comment"] = copy.deepcopy(self.comment)
        self.bodies["comment"]["updated_at"] = F.utc(F.START)
        self.refuse("COMMENT_EDITED")

    def test_missing_protection_or_changed_environment_identity_refuses(self):
        self.bodies["approvals"][0]["environments"][0]["id"] = 202
        self.refuse("APPROVED_ENVIRONMENT_CHANGED")
        self.retained = {}; self.bodies["approvals"][0]["environments"][0]["id"] = 101
        self.bodies["environment"]["can_admins_bypass"] = True
        self.refuse("ENVIRONMENT_CONFIGURATION")

    def test_incomplete_branch_policies_and_pagination_link_refuse(self):
        self.bodies["branches"]["total_count"] = 3
        self.refuse("COMPLETE_BRANCH_POLICIES")
        self.retained = {}; self.link = '<https://example.invalid/next>; rel="next"'
        self.refuse("INCOMPLETE_RESPONSE")

    def test_http_failure_original_is_retained_once_and_never_retried(self):
        self.request_error = O.OriginError("SYNTHETIC_HTTP_FAILURE")
        with self.assertRaises(O.OriginError) as caught: self.acquire()
        self.assertIs(caught.exception, self.request_error)
        self.assertTrue(self.retained["attempt"][1]); self.assertEqual(len(self.requests), 1)
        self.assertFalse(json.loads(self.retained["attempt"][0])["complete"])

    def test_retention_failure_preserves_original_http_cancellation(self):
        failure = KeyboardInterrupt("SYNTHETIC_CANCELLATION"); self.request_error = failure
        def retain(label, raw, *, failed):
            if label == "attempt": raise ValueError("SYNTHETIC_RETENTION_FAILURE")
            self.retain(label, raw, failed=failed)
        with self.assertRaises(KeyboardInterrupt) as caught: self.acquire(retain=retain)
        self.assertIs(caught.exception, failure); self.assertEqual(len(self.requests), 1)

    def after_successful_transport(self, effect):
        request, returned = O._request, []
        def boundary(*args, **kwargs):
            raw, error = request(*args, **kwargs)
            self.assertIsNone(error)
            self.assertTrue(json.loads(raw)["complete"])
            returned.append(raw)
            effect()
            return raw, error
        self.stack.enter_context(patch.object(O, "_request", side_effect=boundary))
        return returned

    def test_work_expiry_before_retainer_keeps_the_complete_original_once_under_final_fence(self):
        returned = self.after_successful_transport(lambda: setattr(self, "ns", 1045 * O.NS))
        attempts = []
        def retain(label, raw, *, failed):
            if label == "attempt":
                attempts.append((raw, failed))
                self.fence.now(final=True)
            self.retain(label, raw, failed=failed)
        self.refuse("FENCE_EXPIRED", retain=retain)
        self.assertIn("attempt", self.retained)
        self.assertEqual(attempts, [(returned[0], True)])
        self.assertEqual(self.retained["attempt"], (returned[0], True))
        self.assertEqual(json.loads(returned[0])["retirement"], "KNOWN")
        self.assertIsNone(json.loads(returned[0])["error"])
        self.assertEqual(len(self.requests), 1)
        self.assertNotIn("match", self.retained)

    def test_cancellation_before_retainer_keeps_original_without_rewriting_transport(self):
        failure = KeyboardInterrupt("SYNTHETIC_POST_TRANSPORT_CANCELLATION")
        def cancel(): raise failure
        returned = self.after_successful_transport(lambda: setattr(self.fence, "cancelled", cancel))
        attempts = []
        def retain(label, raw, *, failed):
            if label == "attempt":
                attempts.append((raw, failed))
                self.fence.now(final=True)
            self.retain(label, raw, failed=failed)
        with self.assertRaises(KeyboardInterrupt) as caught: self.acquire(retain=retain)
        self.assertIs(caught.exception, failure)
        self.assertIn("attempt", self.retained)
        self.assertEqual(attempts, [(returned[0], True)])
        self.assertEqual(self.retained["attempt"], (returned[0], True))
        self.assertTrue(json.loads(returned[0])["complete"])
        self.assertIsNone(json.loads(returned[0])["error"])
        self.assertEqual(len(self.requests), 1)

    def test_pre_retainer_cancellation_remains_primary_when_final_retainer_fails(self):
        failure = KeyboardInterrupt("SYNTHETIC_POST_TRANSPORT_CANCELLATION")
        secondary = ValueError("SYNTHETIC_FINAL_RETENTION_FAILURE")
        def cancel(): raise failure
        returned = self.after_successful_transport(lambda: setattr(self.fence, "cancelled", cancel))
        attempts = []
        def retain(label, raw, *, failed):
            if label == "attempt":
                attempts.append((raw, failed))
                self.fence.now(final=True)
                raise secondary
            self.retain(label, raw, failed=failed)
        with self.assertRaises(KeyboardInterrupt) as caught: self.acquire(retain=retain)
        self.assertIs(caught.exception, failure)
        self.assertEqual(attempts, [(returned[0], True)])
        self.assertIs(caught.exception.__cause__, secondary)
        self.assertEqual(len(self.requests), 1)
        self.assertNotIn("attempt", self.retained)

    def test_expired_final_retention_preserves_boundary_failure_and_is_not_retried(self):
        failure = KeyboardInterrupt("SYNTHETIC_POST_TRANSPORT_CANCELLATION")
        def cancel(): raise failure
        def expired():
            self.ns = self.fence.final
            self.fence.cancelled = cancel
        returned = self.after_successful_transport(expired)
        attempts = []
        def retain(label, raw, *, failed):
            if label == "attempt":
                attempts.append((raw, failed))
                self.fence.now(final=True)
            self.retain(label, raw, failed=failed)
        with self.assertRaises(O.OriginError) as caught: self.acquire(retain=retain)
        self.assertIn("FENCE_EXPIRED", str(caught.exception))
        self.assertEqual(attempts, [(returned[0], True)])
        self.assertIsInstance(caught.exception.__cause__, O.OriginError)
        self.assertEqual(len(self.requests), 1)
        self.assertNotIn("attempt", self.retained)

    def test_entered_retainer_failure_is_not_retried_under_finalization(self):
        failure, attempts = ValueError("SYNTHETIC_ENTERED_RETENTION_FAILURE"), []
        def retain(label, raw, *, failed):
            if label == "attempt":
                attempts.append((raw, failed))
                raise failure
            self.retain(label, raw, failed=failed)
        with self.assertRaises(ValueError) as caught: self.acquire(retain=retain)
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(attempts), 1)
        self.assertFalse(attempts[0][1])
        self.assertTrue(json.loads(attempts[0][0])["complete"])
        self.assertEqual(len(self.requests), 1)

    def test_post_retainer_cancellation_is_not_retried_under_finalization(self):
        failure, attempts = KeyboardInterrupt("SYNTHETIC_POST_RETENTION_CANCELLATION"), []
        def cancel(): raise failure
        def retain(label, raw, *, failed):
            self.retain(label, raw, failed=failed)
            if label == "attempt":
                attempts.append((raw, failed))
                self.fence.cancelled = cancel
        with self.assertRaises(KeyboardInterrupt) as caught: self.acquire(retain=retain)
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(attempts), 1)
        self.assertFalse(attempts[0][1])
        self.assertEqual(self.retained["attempt"], attempts[0])
        self.assertEqual(len(self.requests), 1)

    def test_deadline_in_retention_stops_before_the_next_get(self):
        def retain(label, raw, *, failed):
            self.retain(label, raw, failed=failed)
            if label == "attempt": self.ns = 1045 * O.NS
        self.refuse("FENCE_EXPIRED", retain=retain); self.assertEqual(len(self.requests), 1)

    def test_deadline_in_source_retention_forbids_the_next_record(self):
        def retain(label, raw, *, failed):
            self.retain(label, raw, failed=failed)
            if label == "base_policy_entry": self.ns = 1045 * O.NS
        self.refuse("FENCE_EXPIRED", retain=retain)
        self.assertEqual(set(self.retained), {"event", "base_policy_entry"})
        self.assertEqual(self.requests, [])

    def test_late_transport_close_cannot_produce_success(self):
        self.after_close = lambda: setattr(self, "ns", 1045 * O.NS)
        self.refuse("FENCE_EXPIRED"); self.assertEqual(len(self.requests), 1)
        self.assertTrue(self.retained["attempt"][1])

    def test_original_parent_end_cannot_be_renewed(self):
        self.ns = 1045 * O.NS
        self.refuse("FENCE_EXPIRED"); self.assertEqual(self.requests, [])

    def test_policy_expiry_and_changed_original_first_use_refuse_rechecks(self):
        result, _ = self.acquire()
        self.retained = {}; self.refuse("VALIDITY", now=lambda: self.declaration["expiresAt"])
        self.retained = {}; self.context["firstUseAt"] += 1
        self.refuse("CHANGED_BEFORE_RECHECK", expected=result)

    def test_invalid_token_or_foreign_native_clock_refuses_before_http(self):
        for token in (None, "short", "token\n" + TOKEN): self.refuse("READ_TOKEN", token=token)
        self.context["role"] = "windows-x64"
        self.refuse("NATIVE_CLOCK_ROLE"); self.assertEqual(self.requests, [])

    def test_original_response_bytes_preserve_list_without_rewriting_legacy_object_contract(self):
        self.acquire()
        raw = self.retained["approvals"][0]
        _, body, _ = O.response_bytes(raw, self.paths["approvals"], INVOCATION, self.clock)
        self.assertEqual(body, I.encoded(self.bodies["approvals"]))
        with self.assertRaises(I.AdmissionError): O.observation(raw, self.paths["approvals"], INVOCATION, self.clock)
        _, value, _ = O.observation(self.retained["attempt"][0], self.paths["attempt"], INVOCATION, self.clock)
        self.assertEqual(value, self.bodies["attempt"])

    def test_response_bytes_still_reject_path_clock_incomplete_and_unknown_retirement(self):
        self.acquire(); original = json.loads(self.retained["attempt"][0])
        for name, bad in (("path", "/other"), ("complete", False), ("retirement", "UNKNOWN"), ("status", 201)):
            row = {**original, name: bad}
            with self.assertRaises(O.OriginError): O.response_bytes(I.encoded(row), self.paths["attempt"], INVOCATION, self.clock)

    def test_overall_service_date_drift_cannot_accumulate_per_request_allowances(self):
        self.before_request = lambda: setattr(self, "service_date", F.FIRST1 + 30 * (len(self.requests) - 1))
        self.refuse("SERVICE_DATE_DRIFT"); self.assertLess(len(self.requests), 8)


if __name__ == "__main__":
    unittest.main()
