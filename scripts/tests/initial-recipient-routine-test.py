#!/usr/bin/env python3
"""Offline routine-operation controls, not GitHub or hosted qualification.

Only current public source/policy and temporary synthetic operation records are
read. API callbacks are fakes; no credentials, process, network, native owner or
private evidence access. Tests exercise actual maintained parser/functions.
"""
from __future__ import annotations

import copy
import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("ROUTINE_OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import initial_recipient_routine as R

I, S = R.identity, R.stages
POLICY = (ROOT / ".github/test-evidence-recipient.json").read_bytes()
START = json.loads(POLICY)["notBefore"]
NOW = START + 3600
INSTRUCTION = "a" * 64
ENVIRONMENT = {"name": "initial-recipient-execution", "id": 101,
    "branchPolicies": [{"id": 102, "name": "work/release-foundation-20260926-1WzHcOIr", "type": "branch"},
                       {"id": 103, "name": "refs/pull/*/merge", "type": "branch"}]}


def request():
    return {"schema": 1, "scope": R.SCOPE, "ownerInstructionSha256": INSTRUCTION,
        "allocationResultSha256": "b" * 64, "source": {"commit": "c" * 40, "tree": "d" * 40},
        "environment": copy.deepcopy(ENVIRONMENT), "bootstrap": [
            {"selection": selection, "runId": str(300 + n), "runAttempt": "1"}
            for n, selection in enumerate(("desktop-windows-x64", "desktop-linux-x64",
                                          "desktop-macos-arm64", "full-macos-arm64"))],
        "handoffDeadlineEpoch": NOW + 86400}


def comment(body, when=NOW):
    stamp = datetime.datetime.fromtimestamp(when, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": 8001, "url": "https://api.github.com/repos/p2pKit/P2pKit/issues/comments/8001",
        "issue_url": "https://api.github.com/repos/p2pKit/P2pKit/issues/437",
        "html_url": "https://github.com/p2pKit/P2pKit/issues/437#issuecomment-8001",
        "user": {"login": S.joint.OWNER_LOGIN, "id": S.joint.OWNER_ID, "type": "User"},
        "performed_via_github_app": None, "created_at": stamp, "updated_at": stamp, "body": body.decode("ascii")}


class PaginationControls(unittest.TestCase):
    def pages(self, total):
        return [I.encoded({"total_count": total, "workflow_runs": [{"id": n + 1}
            for n in range(begin, min(begin + 100, total))]}) for begin in range(0, max(total, 1), 100)]

    def collect(self, pages):
        calls = []
        def get(endpoint):
            calls.append(endpoint)
            self.assertEqual(endpoint, R.WORKFLOW_RUNS + f"?per_page=100&page={len(calls)}")
            return pages[len(calls) - 1]
        return R.collect_bootstrap_runs(get), calls

    def test_empty_and_single_page_boundaries(self):
        for size in (0, 1, 99, 100):
            with self.subTest(size=size):
                result, calls = self.collect(self.pages(size))
                self.assertEqual(len(result.rows), size)
                self.assertEqual(len(calls), 1)

    def test_101_preserves_both_actual_original_pages(self):
        pages = self.pages(101)
        result, calls = self.collect(pages)
        self.assertEqual(len(result.rows), 101)
        self.assertEqual(tuple(page.raw for page in result.originals), tuple(pages))
        self.assertEqual(tuple(page.endpoint for page in result.originals), tuple(calls))
        self.assertEqual(json.loads(result.originals[0].raw)["workflow_runs"], [{"id": n} for n in range(1, 101)])

    def test_exact_existing_20_page_bound(self):
        result, calls = self.collect(self.pages(2000))
        self.assertEqual(len(result.rows), 2000)
        self.assertEqual(len(calls), 20)

    def test_more_than_existing_bound_rejected(self):
        with self.assertRaises(I.AdmissionError):
            self.collect(self.pages(2001))

    def test_total_drift_rejected(self):
        pages = self.pages(101)
        value = json.loads(pages[-1]); value["total_count"] = 102
        pages[-1] = I.encoded(value)
        with self.assertRaises(I.AdmissionError):
            self.collect(pages)

    def test_duplicate_ids_within_and_across_pages_rejected(self):
        for page in (0, 1):
            pages = self.pages(101)
            value = json.loads(pages[page]); value["workflow_runs"][-1]["id"] = 1
            pages[page] = I.encoded(value)
            with self.subTest(page=page), self.assertRaises(I.AdmissionError):
                self.collect(pages)

    def test_short_nonfinal_page_and_extra_rows_rejected(self):
        for value in ({"total_count": 101, "workflow_runs": [{"id": 1}]},
                      {"total_count": 0, "workflow_runs": [{"id": 1}]}):
            with self.subTest(value=value), self.assertRaises(I.AdmissionError):
                self.collect([I.encoded(value)])

    def test_strict_page_shapes_and_duplicate_json_rejected(self):
        values = [b'{"total_count":0,"total_count":0,"workflow_runs":[]}',
                  b'{"total_count":NaN,"workflow_runs":[]}']
        for total, entries in ((True, []), (-1, []), (0, {}), (1, [None]),
                               (1, [{"id": True}]), (1, [{"id": 0}]), (1, [{"id": "1"}])):
            values.append(I.encoded({"total_count": total, "workflow_runs": entries}))
        for value in values:
            with self.subTest(value=value), self.assertRaises(I.AdmissionError):
                self.collect([value])

    def test_transport_failure_has_no_retry(self):
        calls = []
        def failed(endpoint):
            calls.append(endpoint)
            raise RuntimeError("synthetic GET failure")
        with self.assertRaises(RuntimeError):
            R.collect_bootstrap_runs(failed)
        self.assertEqual(len(calls), 1)


class RoutineRegistrationControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-routine-model-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.req = request()
        self.calls = []
        self.reply = None
        self.mutate_post = self.mutate_readback = None
        self.service_skew = 0

    def preflight(self, req, body):
        self.calls.append("preflight")
        self.assertEqual(req, self.req)
        self.reply = comment(body, NOW + self.service_skew)

    def post(self, body):
        self.calls.append("post")
        self.assertTrue((self.directory / R.CONSUMED).is_file())
        self.assertEqual(self.reply["body"], body.decode("ascii"))
        value = copy.deepcopy(self.reply)
        if self.mutate_post:
            self.mutate_post(value)
        return 201, I.encoded(value), self.http_date()

    def readback(self, identifier):
        self.calls.append("readback")
        self.assertEqual(identifier, 8001)
        value = copy.deepcopy(self.reply)
        if self.mutate_readback:
            self.mutate_readback(value)
        return I.encoded(value), self.http_date()

    def http_date(self):
        return datetime.datetime.fromtimestamp(NOW + self.service_skew, datetime.timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S GMT")

    def run_one(self, **overrides):
        args = dict(authorized_instruction_sha256=INSTRUCTION, allocation_directory=self.directory,
                    preflight=self.preflight, post=self.post, read_comment=self.readback, clock=lambda: NOW)
        args.update(overrides)
        return R.register_c1_once(I.encoded(self.req), POLICY, **args)

    def test_success_is_delegated_not_personal_or_environment_approval(self):
        result = self.run_one()
        self.assertEqual(self.calls, ["preflight", "post", "readback"])
        self.assertFalse(result["personalApproval"])
        self.assertFalse(result["environmentApproved"])
        self.assertFalse(result["nativeQualification"])
        self.assertEqual(result["executor"], "OWNER_DELEGATED_ROUTINE")
        self.assertEqual(result["releaseStatus"], "NOT_READY")
        self.assertEqual(json.loads((self.directory / "ROUTINE-C1-RESULT.json").read_bytes()), result)
        self.assertEqual(result["source"], self.req["source"])
        self.assertEqual(result["bootstrap"], self.req["bootstrap"])

    def test_service_skew_not_compared_to_local_operation_time(self):
        for skew in (-30, 30):
            directory = self.directory / str(skew)
            directory.mkdir(mode=0o700)
            original = self.directory
            self.directory, self.service_skew = directory, skew
            try:
                with self.subTest(skew=skew):
                    result = self.run_one()
                    self.assertEqual(result["serviceTimes"]["createdAt"], NOW + skew)
                    self.assertFalse(result["personalApproval"])
            finally:
                self.directory = original

    def test_service_expiry_rejected_even_when_local_clock_is_valid(self):
        self.service_skew = json.loads(POLICY)["expiresAt"] - NOW
        with self.assertRaises(I.AdmissionError):
            self.run_one()
        self.assertTrue((self.directory / R.CONSUMED).exists())
        self.assertFalse((self.directory / "ROUTINE-C1-RESULT.json").exists())

    def test_original_http_dates_required_and_bounded(self):
        for date in (None, "invalid", "Tue, 13 Oct 2026 12:00:00 +0000",
                     "Mon, 13 Oct 2026 12:00:00 GMT"):
            with self.subTest(date=date), self.assertRaises(I.AdmissionError):
                R._service_epoch(date)
        directory = self.directory / "expired-get"
        directory.mkdir(mode=0o700)
        expired = datetime.datetime.fromtimestamp(self.req["handoffDeadlineEpoch"],
            datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        def expired_readback(identifier):
            raw, _ = self.readback(identifier)
            return raw, expired
        with self.assertRaises(I.AdmissionError):
            self.run_one(read_comment=expired_readback)
        self.assertTrue((self.directory / R.CONSUMED).exists())

    def test_canonical_wire_unchanged_and_maintained_parser_accepts(self):
        req, body = R.canonical_c1(I.encoded(self.req), POLICY,
            authorized_instruction_sha256=INSTRUCTION, now=NOW)
        parsed, authority, created = S.statement(S.STAGE1, I.encoded(comment(body)), 8001, R.digest(body))
        self.assertEqual(parsed["reviewed"], req["source"])
        self.assertEqual(parsed["bootstrap"], req["bootstrap"])
        self.assertEqual(set(parsed), set(S.COMMON.split()) | {"bootstrap"})
        self.assertEqual(created, NOW)
        self.assertEqual(authority["bodySha256"], R.digest(body))

    def test_delegation_digest_mismatch_rejected_before_io(self):
        with self.assertRaises(I.AdmissionError):
            self.run_one(authorized_instruction_sha256="e" * 64)
        self.assertEqual(self.calls, [])
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_final_release_kinds_and_extra_fields_rejected(self):
        for scope in ("approve-pr", "APPROVE_APPLICATION_SET", "publish", "stage2"):
            self.req["scope"] = scope
            with self.subTest(scope=scope), self.assertRaises(I.AdmissionError):
                self.run_one()
        self.assertEqual(self.calls, [])
        self.req = request(); self.req["personalApproval"] = True
        with self.assertRaises(I.AdmissionError):
            self.run_one()

    def test_policy_or_expired_handoff_rejected(self):
        for when in (START - 1, self.req["handoffDeadlineEpoch"], json.loads(POLICY)["expiresAt"]):
            with self.subTest(when=when), self.assertRaises(I.AdmissionError):
                self.run_one(clock=lambda: when)
        with self.assertRaises(I.AdmissionError):
            R.canonical_c1(I.encoded(self.req), POLICY + b"\n",
                authorized_instruction_sha256=INSTRUCTION, now=NOW)
        self.assertEqual(self.calls, [])

    def test_malformed_source_roster_and_environment_rejected(self):
        cases = []
        value = request(); value["source"] = dict(S.BASE); cases.append(value)
        value = request(); value["source"]["commit"] = "bad"; cases.append(value)
        value = request(); value["bootstrap"][1]["runId"] = value["bootstrap"][0]["runId"]; cases.append(value)
        value = request(); value["bootstrap"][0]["runAttempt"] = "0"; cases.append(value)
        value = request(); value["environment"]["name"] = "maven-central"; cases.append(value)
        value = request(); value["handoffDeadlineEpoch"] = json.loads(POLICY)["expiresAt"]; cases.append(value)
        for value in cases:
            self.req = value
            with self.subTest(value=value), self.assertRaises(I.AdmissionError):
                self.run_one()
        self.assertEqual(self.calls, [])

    def test_failed_preflight_or_stale_clock_never_posts(self):
        def failed(_request, _body):
            raise RuntimeError("synthetic preflight failure")
        with self.assertRaises(RuntimeError):
            self.run_one(preflight=failed)
        self.assertFalse((self.directory / R.CONSUMED).exists())
        self.assertEqual(self.calls, [])
        for phase in ("preflight", "post", "readback"):
            directory = self.directory / ("mutation-" + phase)
            directory.mkdir(mode=0o700)
            original = self.directory
            self.directory, self.calls = directory, []
            captured = []
            def preflight(req, body):
                self.preflight(req, body)
                captured.append(req)
                if phase == "preflight":
                    req["source"]["commit"] = "e" * 40
            def post(body):
                answer = self.post(body)
                if phase == "post":
                    captured[0]["source"]["commit"] = "e" * 40
                return answer
            def readback(identifier):
                answer = self.readback(identifier)
                captured[0]["source"]["commit"] = "e" * 40
                return answer
            try:
                with self.subTest(phase=phase), self.assertRaises(I.AdmissionError):
                    self.run_one(preflight=preflight, post=post, read_comment=readback)
                self.assertEqual(self.calls, ["preflight", "post", "readback"][:
                    {"preflight": 1, "post": 2, "readback": 3}[phase]])
                self.assertFalse((directory / "ROUTINE-C1-RESULT.json").exists())
            finally:
                self.directory = original

    def test_stale_preflight_never_posts(self):
        ticks = iter((NOW, NOW + 61))
        with self.assertRaises(I.AdmissionError):
            self.run_one(clock=lambda: next(ticks))
        self.assertEqual(self.calls, ["preflight"])
        self.assertFalse((self.directory / R.CONSUMED).exists())

    def test_old_personal_or_delegated_intent_blocks_without_callbacks(self):
        (self.directory / R.CONSUMED).write_bytes(b'{"old-personal-handler":true}')
        with self.assertRaises(I.AdmissionError):
            self.run_one()
        self.assertEqual(self.calls, [])

    def test_successful_operation_cannot_be_replayed(self):
        self.run_one()
        with self.assertRaises(I.AdmissionError):
            self.run_one()
        self.assertEqual(self.calls.count("post"), 1)

    def test_ambiguous_post_is_consumed_and_not_retried(self):
        calls = []
        def failed(_body):
            calls.append("post")
            raise TimeoutError("synthetic ambiguous write")
        with self.assertRaises(TimeoutError):
            self.run_one(post=failed)
        self.assertTrue((self.directory / R.CONSUMED).is_file())
        with self.assertRaises(I.AdmissionError):
            self.run_one(post=failed)
        self.assertEqual(calls, ["post"])

    def test_refused_post_is_consumed(self):
        with self.assertRaises(I.AdmissionError):
            self.run_one(post=lambda _body: (403, b'{}', self.http_date()))
        self.assertTrue((self.directory / R.CONSUMED).is_file())
        self.assertNotIn("readback", self.calls)

    def test_wrong_actual_owner_app_or_edit_never_accepted(self):
        # Each case has a separate genuine synthetic allocation directory; an
        # invalid actual POST cannot be retried in the same one.
        mutations = [lambda value: value["user"].update(login="other"),
                     lambda value: value.update(performed_via_github_app={"id": 1}),
                     lambda value: value.update(updated_at="2000-01-01T00:00:00Z"),
                     lambda value: value.update(body=value["body"] + " ")]
        for number, mutation in enumerate(mutations):
            directory = self.directory / str(number); directory.mkdir(mode=0o700)
            self.mutate_post = mutation
            original = self.directory; self.directory = directory
            try:
                with self.subTest(number=number), self.assertRaises(I.AdmissionError):
                    self.run_one()
                self.assertTrue((directory / R.CONSUMED).is_file())
                self.assertFalse((directory / "ROUTINE-C1-RESULT.json").exists())
            finally:
                self.directory = original

    def test_readback_change_fails_without_repost(self):
        self.mutate_readback = lambda value: value.update(body=value["body"] + " ")
        with self.assertRaises(I.AdmissionError):
            self.run_one()
        self.assertEqual(self.calls, ["preflight", "post", "readback"])
        self.assertTrue((self.directory / R.CONSUMED).is_file())
        with self.assertRaises(I.AdmissionError):
            self.run_one()
        self.assertEqual(self.calls.count("post"), 1)

    def test_plaintext_request_never_claims_human_or_final_authority(self):
        self.run_one()
        intent = json.loads((self.directory / R.CONSUMED).read_bytes())
        self.assertFalse(intent["personalApproval"])
        self.assertFalse(intent["retryAllowed"])
        self.assertTrue(intent["mayHavePostedIfInterrupted"])
        self.assertEqual(intent["ownerInstructionSha256"], INSTRUCTION)
        self.assertEqual(intent["requestSha256"], R.digest(I.encoded(self.req)))


if __name__ == "__main__":
    unittest.main(failfast=True)
