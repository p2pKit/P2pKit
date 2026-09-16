#!/usr/bin/env python3
"""Offline API/RAW/HTTP models only; no API, socket, TLS, native owner or build.

The HTTP parser runs against byte-stream models. Every connection/context factory
is replaced or forbidden. Synthetic fields are not hosted job-clock evidence.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
from datetime import datetime, timezone
from email.utils import format_datetime
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_full_job_budget as J
import hosted_test_identity as I

SERVICE_EPOCH = 1789516800
RUNNER = "GitHub Actions 1000000001"
TOKEN = "synthetic_read_token_never_real"


def model_admission(event="push"):
    source = {"commit": "a" * 40, "tree": "b" * 40}
    payload = {"repository": {"full_name": I.REPOSITORY, "default_branch": "main"}}
    binding = {"before": "c" * 40}
    ref = "refs/heads/main"
    if event == "pull_request":
        ref = "refs/pull/7/merge"
        payload.update(number=7, pull_request={"number": 7,
            "base": {"sha": "c" * 40, "ref": "main", "repo": {"full_name": I.REPOSITORY}},
            "head": {"sha": "d" * 40, "ref": "topic", "repo": {"full_name": "independent-fork/P2pKit"}}})
        binding = {"number": 7, "base": "c" * 40, "head": "d" * 40, "headRepository": "independent-fork/P2pKit"}
    raw, policy, key = I.encoded(payload), I.encoded({"model": "policy"}), b"SYNTHETIC PUBLIC KEY; NOT CRYPTOGRAPHIC MATERIAL"
    record = {"schema": 1, "scope": "ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY", "source": source,
        "profile": "full", "suites": ["cli", "diagnostics"],
        "github": {"repository": I.REPOSITORY, "workflow": ".github/workflows/ci.yml", "workflowSha": source["commit"],
            "job": "complete-gate", "runId": "123", "runAttempt": "1", "event": event, "ref": ref,
            "eventSha256": J.digest(raw), "eventBinding": binding, "runnerOS": "macOS", "runnerArch": "ARM64"},
        "policy": {"sha256": J.digest(policy), "keySha256": J.digest(key), "fingerprint": "A" * 40,
                   "expiresAt": 2000000000}}
    return I.Admission(I.encoded(record), raw, policy, key, "A" * 40, J.digest(key), 2000000000)


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def header(body, *, date=SERVICE_EPOCH, length=True):
    values = ["HTTP/1.1 200 OK", "Date: " + format_datetime(datetime.fromtimestamp(date, timezone.utc), usegmt=True),
        "Content-Type: application/json; charset=utf-8", "Cache-Control: private, max-age=60, s-maxage=60",
        "X-GitHub-Request-Id: A1B2:C3D4:5678:90AB", "X-GitHub-Api-Version-Selected: 2022-11-28", "Connection: close"]
    if length:
        values.append("Content-Length: " + str(len(body)))
    return ("\r\n".join(values) + "\r\n\r\n").encode("ascii")


def model_responses(admitted, invocation="e" * 32, *, raw_ns=10000 * J.NS, elapsed=120):
    record, head, branch, head_repo = J.admitted_identity(admitted)
    github = record["github"]
    started = SERVICE_EPOCH - elapsed
    prs = []
    if github["event"] == "pull_request":
        binding = github["eventBinding"]
        prs = [{"number": binding["number"],
                "head": {"sha": head, "ref": branch, "repo": {"url": J.ORIGIN + "/repos/" + head_repo}},
                "base": {"sha": binding["base"], "ref": "main", "repo": {"url": J.ORIGIN + "/repos/" + I.REPOSITORY}}}]
    attempt = {"id": int(github["runId"]), "run_attempt": int(github["runAttempt"]), "path": github["workflow"],
        "event": github["event"], "repository": {"full_name": I.REPOSITORY}, "head_repository": {"full_name": head_repo},
        "head_sha": head, "head_branch": branch, "status": "in_progress", "conclusion": None, "pull_requests": prs,
        "created_at": iso(started - 10), "run_started_at": iso(started - 5)}
    job = {"id": 456, "run_id": int(github["runId"]), "run_attempt": int(github["runAttempt"]), "name": "complete-gate",
        "head_sha": head, "head_branch": branch, "status": "in_progress", "completed_at": None, "conclusion": None,
        "started_at": iso(started), "labels": ["macos-latest"], "runner_id": 1000000001, "runner_name": RUNNER,
        "runner_group_id": 0, "runner_group_name": "GitHub Actions",
        "run_url": J.ORIGIN + "/repos/" + I.REPOSITORY + "/actions/runs/" + github["runId"],
        "url": J.ORIGIN + "/repos/" + I.REPOSITORY + "/actions/jobs/456"}
    bodies = {"attempt": attempt, "jobs": {"total_count": 1, "jobs": [job]}}
    paths = J.paths(admitted)
    return {label: response(paths[label], invocation, I.encoded(body), raw_ns=raw_ns) for label, body in bodies.items()}


def response(path, invocation, body, *, raw_ns=10000 * J.NS):
    return J.encoded({"schema": 1, "scope": "PRIVATE_ACTIONS_JOB_TIME_RESPONSE", "origin": J.ORIGIN,
        "method": "GET", "path": path, "invocation": invocation, "clockDomain": J.RAW_CLOCK_DOMAIN,
        "startedRawNs": raw_ns, "finishedRawNs": raw_ns, "status": 200,
        "headersBase64": base64.b64encode(header(body)).decode("ascii"),
        "bodyBase64": base64.b64encode(body).decode("ascii"), "complete": True, "retirement": "KNOWN", "error": None})


def replace_body(raw, change):
    row = J.parse(raw)
    value = I.parse(base64.b64decode(row["bodyBase64"]), J.BODY_LIMIT)
    change(value)
    body = I.encoded(value)
    row["bodyBase64"] = base64.b64encode(body).decode("ascii")
    row["headersBase64"] = base64.b64encode(header(body)).decode("ascii")
    return J.encoded(row)


def replace_header(raw, change):
    row = J.parse(raw)
    row["headersBase64"] = base64.b64encode(change(base64.b64decode(row["headersBase64"]))).decode("ascii")
    return J.encoded(row)


def provenance():
    return {"controllerJob": "f" * 32, "invocation": "e" * 32, "phaseStartSha256": "1" * 64,
            "phaseResultSha256": "2" * 64, "childReturnSha256": "3" * 64, "runnerName": RUNNER}


class PureBudgetModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(J.http.client, "HTTPSConnection", side_effect=AssertionError("NO_HTTP")))
        self.stack.enter_context(patch.object(socket, "socket", side_effect=AssertionError("NO_SOCKET")))
        self.stack.enter_context(patch.object(J.ssl, "create_default_context", side_effect=AssertionError("NO_TLS")))
        self.addCleanup(self.stack.close)
        self.admitted = model_admission()
        self.originals = model_responses(self.admitted)
        self.provenance = provenance()

    def derive(self):
        return J.derive(self.admitted, self.originals, self.provenance)

    def mutate(self, label, change):
        self.originals[label] = replace_body(self.originals[label], change)

    def test_budget_charges_actual_setup_and_all_source_owned_reserves(self):
        budget = self.derive()
        self.assertEqual(J.TAIL_SECONDS, 2070)
        self.assertEqual(J.TAIL_SECONDS + J.SEAL_SECONDS, 2190)
        self.assertEqual(J.RESERVE_SECONDS, 2430)
        self.assertEqual(budget.fence("upload"), (10000 + 3600 - 120 - 66) * J.NS)
        self.assertEqual(budget.fence("productive"), budget.fence("upload") - 2430 * J.NS)
        self.assertEqual(budget.fence("product-return"), budget.fence("productive") + 330 * J.NS)
        self.assertEqual(budget.fence("controller-return"), budget.fence("upload") - 360 * J.NS)
        self.assertEqual(budget.fence("seal"), budget.fence("upload") - 210 * J.NS)
        self.assertEqual(budget.value["originalsSha256"], {k: J.digest(v) for k, v in self.originals.items()})

    def test_exact_simulator_retirement_reserve_is_not_borrowed_from_export_or_seal(self):
        expected = [(label + suffix, seconds) for label in
            ("simulator-retire-before", "simulator-shutdown", "simulator-retire-after")
            for suffix, seconds in (("", 120), ("-final", 45), ("-read", 30))] + [("simulator-retirement", 30)]
        actual = [(label, seconds) for label, seconds in J.CONTROLLER_TAIL if label.startswith("simulator-")]
        self.assertEqual(actual, expected)
        self.assertEqual(sum(seconds for _, seconds in actual), 615)
        budget = self.derive()
        self.assertEqual(budget.fence("simulator-retirement") - budget.fence("uninstall-read"), 615 * J.NS)
        self.assertEqual(budget.fence("export-freeze") - budget.fence("simulator-retirement"), 180 * J.NS)
        self.assertEqual(J.JOB_SECONDS, 3600)
        self.assertEqual((J.SEAL_SECONDS, J.UPLOAD_SECONDS, J.TRANSITION_SECONDS), (120, 180, 30))

    def test_service_pr_head_is_not_synthetic_merge_source_and_base_is_exact(self):
        self.admitted = model_admission("pull_request")
        self.originals = model_responses(self.admitted)
        self.assertEqual(self.derive().value["source"]["commit"], "a" * 40)
        self.mutate("jobs", lambda value: value["jobs"][0].update(head_sha="a" * 40))
        with self.assertRaises(J.BudgetError):
            self.derive()
        self.originals = model_responses(self.admitted)
        self.mutate("attempt", lambda value: value["pull_requests"][0]["base"].update(sha="f" * 40))
        with self.assertRaises(J.BudgetError):
            self.derive()

    def test_attempt_identity_status_and_head_mismatches_fail_closed(self):
        changes = {"id": 124, "run_attempt": 2, "path": ".github/workflows/other.yml", "event": "workflow_dispatch",
                   "head_sha": "f" * 40, "head_branch": "other", "status": "completed", "conclusion": "success",
                   "repository": {"full_name": "other/repo"}, "head_repository": {"full_name": "other/repo"}}
        for key, value in changes.items():
            with self.subTest(key=key):
                self.originals = model_responses(self.admitted)
                self.mutate("attempt", lambda row: row.update({key: value}))
                with self.assertRaises(J.BudgetError):
                    self.derive()

    def test_job_identity_status_and_native_runner_binding_fail_closed(self):
        changes = {"id": True, "run_id": 124, "run_attempt": 2, "name": "other-job", "head_sha": "f" * 40,
            "head_branch": "other", "status": "queued", "conclusion": "success", "completed_at": iso(SERVICE_EPOCH),
            "runner_name": "some-other-actual-runner", "runner_id": 0, "runner_group_id": False,
            "runner_group_name": "self-hosted", "labels": ["macOS", "ARM64"], "url": "https://evil.invalid/job",
            "run_url": "https://api.github.com/repos/other/repo/actions/runs/123"}
        for key, value in changes.items():
            with self.subTest(key=key):
                self.originals = model_responses(self.admitted)
                self.mutate("jobs", lambda row: row["jobs"][0].update({key: value}))
                with self.assertRaises(J.BudgetError):
                    self.derive()

    def test_no_truncated_page_duplicate_name_or_duplicate_id_selection(self):
        for mode in ("truncated", "duplicate-name", "duplicate-id", "empty", "over-100"):
            self.originals = model_responses(self.admitted)
            def change(value):
                if mode == "truncated": value["total_count"] = 2
                elif mode.startswith("duplicate"):
                    second = dict(value["jobs"][0])
                    second.update(id=457) if mode == "duplicate-name" else second.update(name="different")
                    value["jobs"].append(second)
                    value["total_count"] = 2
                elif mode == "empty": value.update(jobs=[], total_count=0)
                else: value["total_count"] = 101
            self.mutate("jobs", change)
            with self.subTest(mode=mode), self.assertRaises(J.BudgetError):
                self.derive()

    def test_missing_null_future_malformed_and_old_start_never_use_local_time(self):
        for value in (None, "", "2026-09-16T00:00:00+00:00", "2026-02-30T00:00:00Z", iso(SERVICE_EPOCH + 1),
                      iso(SERVICE_EPOCH - 3590)):
            self.originals = model_responses(self.admitted)
            self.mutate("jobs", lambda row: row["jobs"][0].update(started_at=value))
            with self.subTest(value=value), patch.object(J.time, "time", side_effect=AssertionError("NO_WALL_CLOCK")), \
                    self.assertRaises(J.BudgetError):
                self.derive()

    def test_spent_setup_cannot_be_restored_by_a_new_controller_epoch(self):
        self.originals = model_responses(self.admitted, elapsed=2000)
        budget = self.derive()
        with patch.object(J, "shared_raw_ns", return_value=10000 * J.NS), \
                patch.object(J.time, "monotonic", return_value=-1000000):
            with self.assertRaises(J.BudgetError):
                budget.deadline("productive", 7200)

    def test_raw_domain_types_overflow_replay_and_out_of_order_responses_refuse(self):
        for key, value in (("clockDomain", "python.monotonic"), ("startedRawNs", True),
                           ("startedRawNs", -1), ("startedRawNs", J.UINT64 + 1),
                           ("finishedRawNs", 9999 * J.NS), ("finishedRawNs", 10016 * J.NS),
                           ("invocation", "0" * 32), ("path", "/arbitrary"), ("origin", "https://evil.invalid")):
            self.originals = model_responses(self.admitted)
            row = J.parse(self.originals["jobs"])
            row[key] = value
            self.originals["jobs"] = J.encoded(row)
            with self.subTest(key=key, value=value), self.assertRaises(J.BudgetError):
                self.derive()

    def test_request_latency_is_charged_from_request_start_not_receipt_now(self):
        row = J.parse(self.originals["jobs"])
        row["finishedRawNs"] += 14 * J.NS
        self.originals["jobs"] = J.encoded(row)
        budget = self.derive()
        self.assertEqual(budget.fence("upload"), (10000 + 3600 - 120 - 66) * J.NS)
        with patch.object(J, "shared_raw_ns", return_value=10014 * J.NS), patch.object(J.time, "monotonic", return_value=50.):
            self.assertEqual(budget.deadline("productive", 7200), 50 + 3600 - 120 - 66 - 2430 - 14)

    def test_actual_clock_unavailable_backwards_noninteger_or_overflow_never_falls_back(self):
        budget = self.derive()
        for raw in (9999 * J.NS, -1, True, 10000., J.UINT64 + 1):
            with self.subTest(raw=raw), patch.object(J, "shared_raw_ns", return_value=raw), self.assertRaises(J.BudgetError):
                budget.check("productive")
        with patch.object(J, "shared_raw_ns", side_effect=RuntimeError("clock unavailable")), self.assertRaises(RuntimeError):
            budget.check("productive")
        clock = J.BudgetClock(budget)
        with patch.object(J, "shared_raw_ns", side_effect=[10001 * J.NS, 10000 * J.NS]):
            clock.check("productive")
            with self.assertRaises(J.BudgetError):
                clock.check("productive")

    def test_phase_reads_do_not_renew_absolute_fences(self):
        budget = self.derive()
        before = budget.record
        raw = budget.fence("controller-return") - 2 * J.NS
        with patch.object(J, "shared_raw_ns", return_value=raw), patch.object(J.time, "monotonic", return_value=100.):
            self.assertEqual(budget.deadline("controller-return", 45), 102.)
            self.assertEqual(budget.deadline("controller-return", 45), 102.)
        with patch.object(J, "shared_raw_ns", return_value=raw + 2 * J.NS), self.assertRaises(J.BudgetError):
            budget.deadline("controller-return", 45)
        self.assertEqual(budget.record, before)

    def test_header_stale_duplicate_redirect_and_missing_freshness_refuse(self):
        changes = [lambda raw: raw.replace(b"200 OK", b"302 Found"),
            lambda raw: raw.replace(b"Date: ", b"Not-Date: "),
            lambda raw: raw.replace(b"Date: ", b"Date: invalid\r\nDate: "),
            lambda raw: raw.replace(b"Connection: close", b"Age: 3\r\nConnection: close"),
            lambda raw: raw.replace(b"max-age=60", b"max-age=61"),
            lambda raw: raw.replace(b"private, max-age=60", b"public, max-age=60"),
            lambda raw: raw.replace(b"Connection: close", b"Cache-Control: no-cache\r\nConnection: close"),
            lambda raw: raw.replace(b"Connection: close", b"Via: proxy\r\nConnection: close"),
            lambda raw: raw.replace(b"Connection: close", b"Warning: stale\r\nConnection: close"),
            lambda raw: raw.replace(b"Connection: close", b"Content-Encoding: gzip\r\nConnection: close"),
            lambda raw: raw.replace(b"Connection: close", b"X-Cache: HIT\r\nConnection: close")]
        for change in changes:
            self.originals = model_responses(self.admitted)
            self.originals["jobs"] = replace_header(self.originals["jobs"], change)
            with self.subTest(change=changes.index(change)), self.assertRaises(J.BudgetError):
                self.derive()

    def test_second_precision_date_must_be_canonical_utc_and_consistent(self):
        for text in ("Wed, 16 Sep 2026 00:00:00 UTC", "Tue, 16 Sep 2026 00:00:00 GMT", "bad", None):
            with self.subTest(text=text), self.assertRaises(J.BudgetError):
                J.http_epoch(text)
        value = J.parse(self.originals["attempt"])
        body = base64.b64decode(value["bodyBase64"])
        value["headersBase64"] = base64.b64encode(header(body, date=SERVICE_EPOCH + 1)).decode("ascii")
        self.originals["attempt"] = J.encoded(value)
        with self.assertRaises(J.BudgetError):
            self.derive()

    def test_absent_content_length_can_be_valid_but_truncated_or_duplicate_json_cannot(self):
        self.originals["jobs"] = replace_header(self.originals["jobs"],
                lambda raw: b"\r\n".join(line for line in raw.split(b"\r\n") if not line.startswith(b"Content-Length:")))
        self.derive()
        for body in (b'{"total_count":1,"total_count":1,"jobs":[]}', b'{"unfinished":', b'[]'):
            self.originals["jobs"] = response(J.paths(self.admitted)["jobs"], "e" * 32, body)
            with self.subTest(body=body), self.assertRaises(I.AdmissionError):
                self.derive()

    def test_oversized_response_or_header_and_bad_encoding_are_bounded(self):
        row = J.parse(self.originals["jobs"])
        for key, value in (("headersBase64", base64.b64encode(b"x" * (J.HEADER_LIMIT + 1)).decode()),
                           ("bodyBase64", base64.b64encode(b"x" * (J.BODY_LIMIT + 1)).decode()),
                           ("bodyBase64", "not base64")):
            modified = dict(row, **{key: value})
            self.originals["jobs"] = J.encoded(modified)
            with self.subTest(key=key), self.assertRaises(J.BudgetError):
                self.derive()

    def test_original_provenance_and_policy_are_part_of_exact_record_hash(self):
        original = self.derive()
        self.provenance["phaseResultSha256"] = "4" * 64
        changed = self.derive()
        self.assertNotEqual(original.sha256, changed.sha256)
        self.assertEqual(original.value["policy"], J.policy())
        self.assertEqual(J.policy()["requests"], 2)
        self.assertEqual(J.policy()["retries"], 0)


class HttpModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(socket, "socket", side_effect=AssertionError("NO_SOCKET")))
        self.stack.enter_context(patch.object(socket, "create_connection", side_effect=AssertionError("NO_SOCKET")))
        self.context = object()
        self.stack.enter_context(patch.object(J.ssl, "create_default_context", return_value=self.context))
        self.now, self.responses, self.connections, self.requests = 10000 * J.NS, [], [], []
        self.failure = self.close_failure = None
        self.stack.enter_context(patch.object(J, "shared_raw_ns", side_effect=lambda: self.now))
        self.stack.enter_context(patch.object(J.http.client, "HTTPSConnection", side_effect=self.connection))
        self.addCleanup(self.stack.close)

    def connection(self, host, *, timeout, context):
        self.assertEqual(host, "api.github.com")
        self.assertEqual(timeout, 5)
        self.assertIs(context, self.context)
        case = self
        class Socket:
            def __init__(self, raw): self.raw, self.timeouts = raw, []
            def makefile(self, mode):
                self.stream = io.BytesIO(self.raw)
                return self.stream
            def settimeout(self, seconds): self.timeouts.append(seconds)
        class Connection:
            def __init__(self):
                self.closed = False
                self.sock = Socket(case.responses.pop(0))
                self.original_sock = self.sock
            def request(self, method, path, *, headers):
                case.requests.append((method, path, dict(headers)))
                if case.failure: raise case.failure
            def getresponse(self):
                result = self.response_class(self.sock, method="GET")
                result.begin()
                # http.client detaches its connection when Connection: close;
                # the original response file/socket must still read correctly.
                if result.will_close: self.sock = None
                return result
            def close(self):
                self.closed = True
                if case.close_failure: raise case.close_failure
        value = Connection()
        self.connections.append(value)
        return value

    def test_exact_two_gets_no_proxy_retry_or_redirect_and_token_only_in_request(self):
        admitted = model_admission()
        modeled = model_responses(admitted)
        for label in ("attempt", "jobs"):
            row = J.parse(modeled[label])
            self.responses.append(base64.b64decode(row["headersBase64"]) + base64.b64decode(row["bodyBase64"]))
        retained = {}
        result = J.acquire(admitted, "e" * 32, TOKEN, lambda label, raw: retained.update({label: raw}))
        self.assertEqual(set(result), {"attempt", "jobs"})
        self.assertEqual(result, retained)
        self.assertEqual([row[:2] for row in self.requests], [("GET", value) for value in J.paths(admitted).values()])
        for _, _, headers in self.requests:
            self.assertEqual(headers["Authorization"], "Bearer " + TOKEN)
            self.assertEqual(headers["Cache-Control"], "no-cache, max-age=0")
            self.assertEqual(headers["Accept-Encoding"], "identity")
        self.assertTrue(all(value.closed for value in self.connections))
        self.assertTrue(all(value.original_sock.stream.closed for value in self.connections))
        self.assertNotIn(TOKEN.encode(), b"".join(retained.values()))

    def test_framed_chunked_and_eof_bodies_without_content_length(self):
        for mode in ("chunked", "eof"):
            body = b'{"synthetic":true}'
            raw = header(body, length=False)
            if mode == "chunked":
                raw = raw.replace(b"Connection: close", b"Transfer-Encoding: chunked\r\nConnection: close")
                raw += hex(len(body))[2:].encode() + b"\r\n" + body + b"\r\n0\r\n\r\n"
            else:
                raw += body
            self.responses.append(raw)
            value, error = J._request(J.paths(model_admission())["attempt"], TOKEN, "e" * 32)
            with self.subTest(mode=mode):
                self.assertIsNone(error)
                self.assertEqual(base64.b64decode(J.parse(value)["bodyBase64"]), body)
                self.assertTrue(J.parse(value)["complete"])

    def test_non_200_response_is_retained_and_never_followed_or_retried(self):
        body = b'{"synthetic":true}'
        self.responses.append(header(body).replace(b"200 OK", b"302 Found") + body)
        retained = {}
        with self.assertRaises(J.BudgetError):
            J.acquire(model_admission(), "e" * 32, TOKEN, lambda label, raw: retained.update({label: raw}))
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(set(retained), {"attempt"})
        self.assertEqual(J.parse(retained["attempt"])["status"], 302)
        self.assertFalse(J.parse(retained["attempt"])["complete"])
        self.assertTrue(self.connections[0].closed)

    def test_connection_failure_and_close_failure_never_advance_to_next_get(self):
        for kind in ("connect", "close"):
            self.responses.append(header(b"{}") + b"{}")
            self.failure = OSError("synthetic network error") if kind == "connect" else None
            self.close_failure = OSError("synthetic close error") if kind == "close" else None
            before = len(self.requests)
            retained = {}
            with self.subTest(kind=kind), self.assertRaises(J.BudgetError):
                J.acquire(model_admission(), "e" * 32, TOKEN, lambda label, raw: retained.update({label: raw}))
            self.assertEqual(len(self.requests), before + 1)
            self.assertEqual(set(retained), {"attempt"})
            self.assertNotIn(TOKEN, retained["attempt"].decode())

    def test_oversized_header_truncated_body_and_excessive_wire_never_complete(self):
        body = b'{"synthetic":true}'
        cases = [header(body)[:-2] + b"X-Big: " + b"x" * 4096 + b"\r\n\r\n" + body,
                 header(body) + body[:-1],
                 header(body).replace(b"Content-Length: " + str(len(body)).encode(), b"Content-Length: 1048577") + body]
        for raw in cases:
            self.responses.append(raw)
            value, error = J._request(J.paths(model_admission())["attempt"], TOKEN, "e" * 32)
            self.assertIsNotNone(error)
            self.assertFalse(J.parse(value)["complete"])
            self.assertTrue(self.connections[-1].closed)

    def test_slow_socket_read_uses_remaining_absolute_deadline_and_fails_after_read(self):
        case = self
        class Slow(io.BytesIO):
            def readline(self, limit):
                raw = super().readline(limit)
                case.now += 16 * J.NS
                return raw
        sock = SimpleNamespace(settimeout=lambda seconds: self.assertLessEqual(seconds, 5))
        stream = J._Reader(Slow(b"HTTP/1.1 200 OK\r\n"), sock, self.now + 15 * J.NS, self.now)
        with self.assertRaises(J.BudgetError):
            stream.readline(65536)
        self.assertEqual(bytes(stream.header), b"HTTP/1.1 200 OK\r\n")
        stream.close()

    def test_raw_clock_failure_after_close_keeps_observed_original_bytes_as_failed(self):
        body = b'{"synthetic":true}'
        self.responses.append(header(body) + body)
        connection = self.connection
        def late(*args, **kwargs):
            value = connection(*args, **kwargs)
            close = value.close
            def finish():
                close()
                self.now -= J.NS  # Invalid RAW, never an alternate clock.
            value.close = finish
            return value
        with patch.object(J.http.client, "HTTPSConnection", side_effect=late):
            raw, error = J._request(J.paths(model_admission())["attempt"], TOKEN, "e" * 32)
        self.assertIsInstance(error, J.BudgetError)
        value = J.parse(raw)
        self.assertEqual(base64.b64decode(value["headersBase64"]), header(body))
        self.assertEqual(base64.b64decode(value["bodyBase64"]), body)
        self.assertFalse(value["complete"])
        self.assertIsNone(value["finishedRawNs"])
        self.assertEqual(value["error"], "JOB_TIME_CLOCK_FAILED")
        self.assertTrue(self.connections[0].closed)

    def test_chunk_framing_and_body_reads_share_original_wire_byte_cap(self):
        socket = SimpleNamespace(settimeout=lambda seconds: self.assertLessEqual(seconds, J.SOCKET_SECONDS))
        stream = J._Reader(io.BytesIO(b"xx"), socket, self.now + 15 * J.NS, self.now)
        stream.in_headers = False
        stream.wire_bytes = 2 * J.BODY_LIMIT + J.HEADER_LIMIT - 1
        with self.assertRaisesRegex(J.BudgetError, "JOB_TIME_HTTP_WIRE_LIMIT"):
            stream.read(2)
        stream.close()

    def test_missing_or_header_injection_token_cannot_allocate_connection(self):
        for token in (None, "", "bad\r\nX: header", "x" * 4097):
            with self.subTest(token_size=None if token is None else len(token)), self.assertRaises(J.BudgetError):
                J.acquire(model_admission(), "e" * 32, token, lambda *args: self.fail("NO_RETENTION"))
        self.assertEqual(self.connections, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
