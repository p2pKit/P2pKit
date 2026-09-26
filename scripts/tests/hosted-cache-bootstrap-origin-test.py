#!/usr/bin/env python3
"""Offline bootstrap acquisition composition controls, NOT hosted evidence.

All Actions, clocks, native owners, TLS and HTTP sockets are explicit models.
Only tiny synthetic POSIX private files are real; run under an ordinary UID.
No Git/native child, key operation, provider, Java, Gradle or dependency request.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
import copy
import importlib.util
import io
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_cache_bootstrap_origin as O


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


S = load("bootstrap_origin_controller", ROOT / "scripts/run-hosted-cache-bootstrap.py")
M = load("bootstrap_origin_identity_models", Path(__file__).with_name("hosted-cache-bootstrap-identity-test.py"))
F = load("bootstrap_origin_http_fixtures", Path(__file__).with_name("hosted-full-job-budget-test.py"))
TOKEN = "SYNTHETIC_ACTIONS_READ_TOKEN_NOT_A_CREDENTIAL"
RUNNER = "SYNTHETIC GitHub Actions runner"
SELECTORS = {"linux-x64": "ubuntu-latest", "windows-x64": "windows-latest",
             "macos-arm64": "macos-26", "macos-x64": "macos-15-intel"}


def model_admission(selection="desktop-linux-x64"):
    _, role, system, arch = O.bootstrap.selection(selection)
    event = {"repository": {"full_name": "p2pKit/P2pKit", "default_branch": "main"}, "ref": "work/fixture",
             "inputs": {"selection": selection, "expected_sha": M.SOURCE, "expected_tree": M.TREE}}
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_SERVER_URL": "https://github.com",
           "GITHUB_API_URL": "https://api.github.com", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": system,
           "RUNNER_ARCH": arch, "GITHUB_JOB": "populate", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
           "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/work/fixture", "GITHUB_SHA": M.SOURCE,
           "GITHUB_WORKFLOW_SHA": M.SOURCE, "GITHUB_WORKFLOW_REF":
           "p2pKit/P2pKit/.github/workflows/dependency-cache-bootstrap.yml@refs/heads/work/fixture", "RUNNER_NAME": RUNNER}
    admitted = O.bootstrap._admit(env, S.I.encoded(event), M.ModelGit(), M.NOW)
    clock = O.clocks.ClockIdentity(role, O.clocks.DOMAINS[role], 10_000_000 if role == "windows-x64" else O.NS)
    return admitted, clock, env


def service_bodies(admitted, clock):
    value = O.parse(admitted.record)
    github = value["github"]
    attempt = {"id": 123, "run_attempt": 1, "repository": {"full_name": "p2pKit/P2pKit"},
        "head_repository": {"full_name": "p2pKit/P2pKit"}, "path": ".github/workflows/dependency-cache-bootstrap.yml",
        "event": "workflow_dispatch", "head_sha": value["source"]["commit"], "head_branch": "work/fixture",
        "status": "in_progress", "conclusion": None, "pull_requests": [],
        "created_at": F.iso(F.SERVICE_EPOCH - 30), "run_started_at": F.iso(F.SERVICE_EPOCH - 20)}
    job = {"id": 456, "run_id": 123, "run_attempt": 1, "name": "populate", "head_sha": value["source"]["commit"],
        "head_branch": "work/fixture", "status": "in_progress", "conclusion": None, "completed_at": None,
        "run_url": "https://api.github.com/repos/p2pKit/P2pKit/actions/runs/" + github["runId"],
        "url": "https://api.github.com/repos/p2pKit/P2pKit/actions/jobs/456", "runner_id": 789,
        "runner_name": RUNNER, "runner_group_id": 0, "runner_group_name": "GitHub Actions",
        "labels": [SELECTORS[clock.role]], "started_at": F.iso(F.SERVICE_EPOCH - 10)}
    return {"attempt": attempt, "jobs": {"total_count": 1, "jobs": [job]}}


def response(admitted, clock, label, body, *, start=1001 * O.NS):
    raw = S.I.encoded(body)
    return O.encoded({"schema": 1, "scope": "PRIVATE_BOOTSTRAP_SERVICE_RESPONSE_V1", "origin": "https://api.github.com",
        "method": "GET", "path": O.paths(admitted)[label], "invocation": "e" * 32, "clock": O.clock_value(clock),
        "startedNs": start, "finishedNs": start + 1, "status": 200,
        "headersBase64": base64.b64encode(F.header(raw)).decode(), "bodyBase64": base64.b64encode(raw).decode(),
        "complete": True, "retirement": "KNOWN", "error": None})


class OfflineCase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target, name in ((subprocess, "Popen"), (subprocess, "run"), (os, "system"),
                             (socket, "socket"), (socket, "create_connection"), (S.processes, "host_role"),
                             (S.processes, "make_scope"), (S.query, "NativeGitQueries"),
                             (O.http.client, "HTTPSConnection"), (O.ssl, "create_default_context")):
            self.stack.enter_context(patch.object(target, name, side_effect=AssertionError("NO_NATIVE_OR_NETWORK")))
        self.admitted, self.clock, self.env = model_admission()
        self.nanoseconds = 1000 * O.NS
        self.stack.enter_context(patch.object(O.clocks, "observe", side_effect=self.observe))
        self.stack.enter_context(patch.object(O.time, "monotonic", side_effect=lambda: self.nanoseconds / O.NS))
        self.stack.enter_context(patch.object(S.time, "sleep", side_effect=lambda seconds: None))
        self.fence = O.Fence(O.prelude(O.clocks.Reading(self.clock, self.nanoseconds)),
            minimum=self.nanoseconds, cancelled=lambda: None)

    def observe(self):
        self.nanoseconds += 1000
        return O.clocks.Reading(self.clock, self.nanoseconds)


class IdentityAndFenceTests(OfflineCase):
    def originals(self, admitted=None, clock=None):
        admitted, clock = admitted or self.admitted, clock or self.clock
        return {name: response(admitted, clock, name, body, start=(1001 + index) * O.NS)
                for index, (name, body) in enumerate(service_bodies(admitted, clock).items())}

    def test_all_six_selections_bind_distinct_native_service_not_ordinary_budget(self):
        for selected in ("desktop-linux-x64", "desktop-windows-x64", "desktop-macos-arm64", "desktop-macos-x64",
                         "full-macos-arm64", "full-macos-x64"):
            admitted, clock, _ = model_admission(selected)
            with self.subTest(selection=selected):
                result = O.service_identity(admitted, self.originals(admitted, clock), "e" * 32, clock, RUNNER)
                self.assertEqual(result["selector"], SELECTORS[clock.role])
                self.assertEqual(result["budgetAcceptance"], "NOT_ADMITTED")
                self.assertIs(result["exportSaveAuthority"], False)
                self.assertNotIn("fencesRawNs", result)
                self.assertNotIn("jobSeconds", result)

    def test_coherent_service_identity_drift_or_ambiguous_page_is_rejected(self):
        cases = [lambda b: b["attempt"].update(path=".github/workflows/desktop-cross-host.yml"),
            lambda b: b["attempt"].update(event="push"), lambda b: b["attempt"].update(run_attempt=2),
            lambda b: b["attempt"].update(head_sha="f" * 40), lambda b: b["attempt"].update(status="completed"),
            lambda b: b["jobs"].update(total_count=101),
            lambda b: b["jobs"].update(total_count=2, jobs=[b["jobs"]["jobs"][0]] * 2),
            lambda b: b["jobs"]["jobs"][0].update(name="ubuntu-latest"),
            lambda b: b["jobs"]["jobs"][0].update(labels=["self-hosted"]),
            lambda b: b["jobs"]["jobs"][0].update(runner_name="different runner"),
            lambda b: b["jobs"]["jobs"][0].update(runner_group_id=True),
            lambda b: b["jobs"]["jobs"][0].update(run_id=True),
            lambda b: b["jobs"]["jobs"][0].update(conclusion="success"),
            lambda b: b["jobs"]["jobs"][0].update(started_at=F.iso(F.SERVICE_EPOCH + 1))]
        for index, change in enumerate(cases):
            bodies = service_bodies(self.admitted, self.clock)
            change(bodies)
            raws = {name: response(self.admitted, self.clock, name, body, start=(1001 + i) * O.NS)
                    for i, (name, body) in enumerate(bodies.items())}
            with self.subTest(index=index), self.assertRaises((O.OriginError, O.wire.BudgetError)):
                O.service_identity(self.admitted, raws, "e" * 32, self.clock, RUNNER)

    def test_original_response_order_types_clock_and_http_freshness_are_required(self):
        cases = {"finishedNs": True, "startedNs": 1004 * O.NS, "scope": "PRIVATE_ACTIONS_JOB_TIME_RESPONSE",
                 "complete": 1, "retirement": "UNKNOWN", "error": "failed", "status": True,
                 "clock": O.clock_value(model_admission("desktop-windows-x64")[1])}
        for key, value in cases.items():
            raws = self.originals()
            row = O.parse(raws["jobs"])
            row[key] = value
            raws["jobs"] = O.encoded(row)
            with self.subTest(field=key), self.assertRaises((O.OriginError, O.wire.BudgetError)):
                O.service_identity(self.admitted, raws, "e" * 32, self.clock, RUNNER)
        for header_change in (lambda x: x.replace(b"200 OK", b"302 Found"),
                lambda x: x.replace(b"Connection: close", b"Age: 1\r\nConnection: close"),
                lambda x: x.replace(b"Connection: close", b"Via: proxy\r\nConnection: close"),
                lambda x: x.replace(b"max-age=60", b"max-age=61")):
            raws = self.originals(); row = O.parse(raws["jobs"])
            row["headersBase64"] = base64.b64encode(header_change(base64.b64decode(row["headersBase64"]))).decode()
            raws["jobs"] = O.encoded(row)
            with self.assertRaises((O.OriginError, O.wire.BudgetError)):
                O.service_identity(self.admitted, raws, "e" * 32, self.clock, RUNNER)

    def test_original_120_75_and_clock_identity_cannot_be_relabelled_job_authority(self):
        raw = self.fence.raw
        self.assertEqual((self.fence.work, self.fence.final), (1075 * O.NS, 1120 * O.NS))
        for key, value in (("workEndNs", 1076 * O.NS), ("finalEndNs", 6400 * O.NS),
                           ("exportSaveAuthority", True), ("jobSeconds", 5400), ("firstNs", True)):
            declared = O.parse(raw); declared[key] = value
            with self.subTest(field=key), self.assertRaises((O.OriginError, O.wire.BudgetError, O.clocks.ClockError)):
                O.Fence(declared, minimum=1000 * O.NS, cancelled=lambda: None)
        self.assertEqual(self.fence.raw, raw)

    def test_retention_highwater_and_local_conversion_never_reset_to_response_time(self):
        self.nanoseconds = 1070 * O.NS
        end = self.fence.deadline(45)
        self.assertLessEqual(end, 1075.)
        last = self.fence.last
        self.nanoseconds = last - 2000
        with self.assertRaises(O.clocks.ClockError):
            self.fence.now(minimum=1000 * O.NS)
        self.nanoseconds = 1075 * O.NS
        with self.assertRaises(O.OriginError):
            self.fence.now()
        self.fence.now(final=True)
        self.nanoseconds = 1120 * O.NS
        with self.assertRaises(O.OriginError):
            self.fence.deadline(45, final=True)

    def test_qpc_frequency_changes_cannot_hide_behind_same_role_and_epoch(self):
        self.clock = O.clocks.ClockIdentity("windows-x64", O.clocks.WINDOWS_DOMAIN, 10_000_000)
        bound = O.Fence(O.prelude(O.clocks.Reading(self.clock, self.nanoseconds)), minimum=self.nanoseconds, cancelled=lambda: None)
        self.clock = O.clocks.ClockIdentity("windows-x64", O.clocks.WINDOWS_DOMAIN, 10_000_001)
        with self.assertRaises(O.clocks.ClockError):
            bound.now()

    def test_operation_maximum_rejects_boolean_nonfinite_and_non_numeric_values(self):
        for value in (True, False, None, "45", [], {}, 0, -1, float("inf"), float("nan"), 10 ** 400):
            with self.subTest(value=repr(value)), self.assertRaises(O.OriginError):
                self.fence.deadline(value)


class OwnerFenceTests(OfflineCase):
    def owner(self):
        value = S.Owner(1120., self.fence)
        self.addCleanup(value.close)
        return value

    def test_work_expiry_prevents_new_positive_allocation_before_final_fence(self):
        owner = self.owner()
        made = []
        self.nanoseconds = 1076 * O.NS
        def factory():
            made.append(True)
            return SimpleNamespace(close=lambda: None)
        with self.assertRaises(O.OriginError):
            owner.acquire("synthetic", factory)
        self.assertEqual(made, [])

    def test_returned_allocation_crossing_work_is_not_success_or_unknown_retirement(self):
        owner = self.owner()
        closed = []
        value = SimpleNamespace(close=lambda: closed.append(True))
        def delayed():
            self.nanoseconds = 1076 * O.NS
            return value
        with self.assertRaises(O.OriginError):
            owner.acquire("synthetic", delayed)
        self.assertFalse(owner.unknown)
        owner.close()
        self.assertEqual(closed, [True])

    def test_expired_original_final_fence_still_closes_known_resources_once(self):
        owner = self.owner()
        closed = []
        for number in range(3):
            owner.acquire("synthetic", lambda n=number: SimpleNamespace(close=lambda: closed.append(n)))
        self.nanoseconds = 1120 * O.NS
        owner.close()
        self.assertEqual(closed, [2, 1, 0])
        self.assertIsNotNone(owner.original)
        self.assertFalse(owner.unknown)
        owner.close()
        self.assertEqual(closed, [2, 1, 0])

    def test_local_owner_fence_rejects_nonfinite_boolean_and_invalid_input(self):
        for value in (True, False, None, "1120", [], 0, -1, 1000., math.inf, math.nan, 10 ** 400):
            with self.subTest(value=repr(value)), self.assertRaises(O.OriginError):
                S.Owner(value, self.fence)

    def test_initial_metadata_highwater_survives_loading_the_original_frame(self):
        first = O.clocks.Reading(self.clock, self.nanoseconds)
        owner = S.Owner(1045., first=first)
        self.nanoseconds = 1002 * O.NS
        owner.end()
        self.nanoseconds = 1001 * O.NS
        with self.assertRaises(O.clocks.ClockError):
            owner.bind(self.fence, work_limit=1040 * O.NS, final_limit=1060 * O.NS)
        self.assertEqual(owner.early_last, 1002 * O.NS + 1000)
        self.nanoseconds = 1003 * O.NS
        owner.bind(self.fence, work_limit=1040 * O.NS, final_limit=1060 * O.NS)
        self.assertLessEqual(owner.local_end, 1045.)
        owner.close()

    def test_preframe_cancellation_is_original_and_prevents_file_acquisition(self):
        original = KeyboardInterrupt("SYNTHETIC_EARLY_CANCEL")
        def cancelled(): raise original
        owner = S.Owner(1045., first=O.clocks.Reading(self.clock, self.nanoseconds), cancelled=cancelled)
        allocations = []
        with self.assertRaises(KeyboardInterrupt) as caught:
            owner.acquire("never", lambda: allocations.append(True))
        self.assertIs(caught.exception, original)
        self.assertEqual(allocations, [])
        owner.close()

    def test_short_write_preserves_failure_and_closes_known_writer_once(self):
        owner = self.owner()
        closed = []
        stream = SimpleNamespace(write=lambda raw: len(raw) - 1, close=lambda: closed.append(True))
        parent = SimpleNamespace(create_file=lambda *_args, **_kwargs: stream)
        with self.assertRaisesRegex(O.OriginError, "SHORT_WRITE") as caught:
            owner.write(parent, "synthetic.json", b"abc")
        self.assertIs(owner.original, caught.exception)
        self.assertFalse(owner.unknown)
        owner.close()
        self.assertEqual(closed, [True])

    def test_sync_failure_is_not_replaced_by_secondary_unknown_close(self):
        owner = self.owner()
        original = OSError("SYNTHETIC_SYNC")
        def sync(): raise original
        def close(): raise OSError("SYNTHETIC_CLOSE")
        stream = SimpleNamespace(write=lambda raw: len(raw), sync=sync, close=close)
        parent = SimpleNamespace(create_file=lambda *_args, **_kwargs: stream)
        with self.assertRaises(OSError) as caught:
            owner.write(parent, "synthetic.json", b"abc")
        self.assertIs(caught.exception, original)
        self.assertTrue(owner.unknown)
        with self.assertRaisesRegex(O.OriginError, "RETIREMENT_UNKNOWN"):
            owner.close()
        self.assertIn(owner, S.QUARANTINE)
        S.QUARANTINE.remove(owner)  # Synthetic owner, no native pins exist.

    def test_reader_failure_pins_owner_and_forbids_further_allocation(self):
        owner = self.owner()
        original = OSError("SYNTHETIC_READER_CLOSE")
        def read(*_args, **_kwargs): raise original
        with self.assertRaises(OSError) as caught:
            owner.read(SimpleNamespace(read_bytes=read), "synthetic.json")
        self.assertIs(caught.exception, original)
        allocations = []
        with self.assertRaises(O.OriginError):
            owner.acquire("forbidden", lambda: allocations.append(True), final=True)
        self.assertEqual(allocations, [])
        with self.assertRaises(O.OriginError):
            owner.close()
        S.QUARANTINE.remove(owner)

    def test_late_returned_close_records_expiry_without_repeating_cleanup(self):
        owner = self.owner()
        closed = []
        def close():
            closed.append(True)
            self.nanoseconds = 1120 * O.NS
        resource = owner.acquire("synthetic", lambda: SimpleNamespace(close=close))
        owner.close_one(resource)
        self.assertIsInstance(owner.original, O.OriginError)
        self.assertFalse(owner.unknown)
        owner.close()
        self.assertEqual(closed, [True])


class NativeRecordTests(OfflineCase):
    def native(self, role):
        argv = ["/SYNTHETIC/python", "-I", "-B", "-S", "_service", "--minimum-ns", "1234"]
        start = {"role": role, "job": "b" * 32, "invocation": "e" * 32, "cwd": "/SYNTHETIC/source"}
        leader = {"pid": 1234}
        launch = {"created": True, "requestedArgv": argv, "resolvedArgv": argv, "cwd": start["cwd"], "pid": 1234}
        value = {"backend": S.BACKENDS[role], "job": start["job"], "invocation": start["invocation"],
                 "launches": [launch], "startedIdentities": [leader], "discoveryErrors": []}
        if role == "windows-x64":
            leader.update(creationFileTime=123456789, jobAssignedBeforeResume=True)
            value["scope"] = "kernel-job-no-breakaway-kill-on-close"
            launch.update(api="CreateProcessW", batch=False, applicationName=argv[0],
                commandLine=subprocess.list2cmdline(argv), resumed=True, jobAssignedBeforeResume=True,
                outputMode="caller-owned-native-files", resourceCleanup=[{"phase": "launch-temporary", "resource": name,
                    "status": "RETIRED"} for name in ("startup-attributes", "launch-handle-0", "launch-handle-1",
                                                      "launch-handle-2", "primary-thread")])
        else:
            value.update(scope="controlled-marker-inheriting-descendants", discoveryReconciliations=[])
            launch.update(api="subprocess.Popen", shell=False, executable=argv[0], outputMode="caller-owned-files")
            if role.startswith("macos-"):
                leader.update(uniqueId=4567, startSeconds=5678, startMicroseconds=0, pidVersion=0)
                value.update(observationReconciliations=[], drainReconciliations=[{"outcome": "retired",
                    "signalReconciliations": [{"outcome": "signal-succeeded"}]}])
            else:
                leader["startTicks"] = 5678
        return value, start, leader, argv

    def test_closed_native_variants_include_zero_darwin_pid_version(self):
        for role in SELECTORS:
            with self.subTest(role=role):
                S.native_record(*self.native(role))

    def test_darwin_original_birth_can_precede_resolved_terminal_histories(self):
        for role in ("macos-arm64", "macos-x64"):
            value, start, leader, argv = self.native(role)
            value.update(discoveryErrors=["SYNTHETIC_INITIAL_UNRESOLVED"],
                discoveryReconciliations=[{"outcome": "unresolved", "originalError": "SYNTHETIC"}],
                drainReconciliations=[])
            S.native_record(value, start, leader, argv, terminal=False)
            with self.subTest(role=role), self.assertRaises(O.OriginError):
                S.native_record(value, start, leader, argv)
            value.update(discoveryErrors=[], discoveryReconciliations=[{"outcome": "nonrunning", "originalError": "SYNTHETIC"}],
                drainReconciliations=[{"outcome": "retired", "signalReconciliations": [{"outcome": "absent"}]}])
            S.native_record(value, start, leader, argv)

    def test_native_birth_still_requires_actual_role_scope_job_and_lifetime(self):
        changes = [lambda v: v.update(backend="foreign"), lambda v: v.update(scope="unowned"),
            lambda v: v.update(job="a" * 32), lambda v: v.update(invocation="c" * 32),
            lambda v: v["launches"][0].update(pid=2),
            lambda v: v["launches"][0].update(resolvedArgv=["help"]), lambda v: v.update(startedIdentities=[])]
        for role in SELECTORS:
            for number, change in enumerate(changes):
                value, start, leader, argv = self.native(role)
                change(value)
                with self.subTest(role=role, change=number), self.assertRaises(O.OriginError):
                    S.native_record(value, start, leader, argv, terminal=False)

    def test_windows_launch_and_temporary_retirement_cannot_be_assumed_from_exit(self):
        for key, field in (("resumed", False), ("batch", True), ("jobAssignedBeforeResume", False),
                           ("commandLine", "help"), ("outputMode", "pipe"), ("resourceCleanup", [])):
            value, start, leader, argv = self.native("windows-x64")
            value["launches"][0][key] = field
            with self.subTest(field=key), self.assertRaises(O.OriginError):
                S.native_record(value, start, leader, argv)

    def test_baseline_roster_role_and_original_native_keys_are_closed(self):
        for role in SELECTORS:
            baseline = None if role == "windows-x64" else [[1234, 5678, 9000, 0]] if role.startswith("macos-") else [[1234, 0]]
            value = {"role": role, "baseline": baseline, "kernelJob": role == "windows-x64"}
            self.assertEqual(S.baseline_record(O.encoded(value), role), value)
            for key, changed in (("role", "foreign"), ("kernelJob", not value["kernelJob"]), ("extra", True),
                                 ("baseline", [baseline, baseline])):
                modified = {**value, key: changed}
                with self.subTest(role=role, field=key), self.assertRaises(O.OriginError):
                    S.baseline_record(O.encoded(modified), role)


class AdmissionWrapperTests(OfflineCase):
    """Actual caller, modeled query supplier; never a native/Git admission run."""
    def setUp(self):
        super().setUp()
        self.owner = S.Owner(1120., self.fence)
        self.addCleanup(self.owner.close)
        self.calls, self.files = [], {}
        self.path = Path("/SYNTHETIC/admission")
        self.native_error = self.admit_error = self.finalize_error = self.constructor_error = None
        self.finalize_time = None
        self.supplier = SimpleNamespace(unknown=False, native_host_matches_actions=self.native,
            retain_admission=self.retain, _finalize=self.finalize)
        self.stack.enter_context(patch.object(S.query, "NativeGitQueries", side_effect=self.construct))
        self.stack.enter_context(patch.object(S.bootstrap, "admit", side_effect=self.identity))
        self.stack.enter_context(patch.object(self.owner, "open", side_effect=self.open))

    def construct(self, root, directory, *, check_cancel, owner_deadlines):
        self.calls.append(("construct", root, directory, owner_deadlines))
        self.assertEqual(root, ROOT)
        self.assertEqual(directory, self.path)
        self.assertEqual(check_cancel, self.fence.now)
        self.assertTrue(1000 < owner_deadlines[0] <= 1075)
        self.assertTrue(owner_deadlines[0] <= owner_deadlines[1] <= 1120)
        if self.constructor_error:
            raise self.constructor_error
        return self.supplier

    def native(self):
        self.calls.append(("native",))
        if self.native_error:
            raise self.native_error

    def identity(self, root, *, query_runner, expected):
        self.calls.append(("identity", expected))
        self.assertIs(query_runner, self.supplier)
        self.assertEqual(root, ROOT)
        if self.admit_error:
            raise self.admit_error
        return self.admitted

    def retain(self, admitted):
        self.calls.append(("retain",))
        self.assertIs(admitted, self.admitted)
        self.files.update({"admission.json": admitted.record, "original-event.json": admitted.original_event,
            "original-policy.json": admitted.original_policy, "recipient-public.asc": admitted.public_key})

    def finalize(self, original):
        self.calls.append(("finalize", original))
        self.files["session-result.json"] = O.encoded({"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY",
            "job": "a" * 32, "queries": [], "result": "READY_FOR_CALLER_SEAL", "retirement": "KNOWN",
            "firstError": None, "errors": [], "readbacks": []})
        if self.finalize_time is not None:
            self.nanoseconds = self.finalize_time
        if self.finalize_error:
            raise self.finalize_error

    def open(self, path, **kwargs):
        self.calls.append(("open", path))
        return SimpleNamespace(read_bytes=lambda name, **_kwargs: self.files[name])

    def test_wrapper_supplies_original_optional_fences_and_compares_native_before_identity(self):
        admitted, returned = S.admit(self.owner, self.fence, self.path, expected=self.admitted)
        self.assertIs(admitted, self.admitted)
        self.assertEqual([item[0] for item in self.calls], ["construct", "native", "identity", "retain", "finalize", "open"])
        self.assertIs(self.calls[2][1], self.admitted)
        self.assertIsNone(self.calls[4][1])
        self.assertEqual(returned["sessionSha256"], O.digest(self.files["session-result.json"]))
        self.assertEqual(self.owner.admissions[str(self.path)],
            (admitted, self.files["session-result.json"], O.encoded(returned)))

    def test_native_rejection_finalizes_once_without_identity_or_original_registration(self):
        self.native_error = O.OriginError("SYNTHETIC_NATIVE_MISMATCH")
        with self.assertRaises(O.OriginError) as caught:
            S.admit(self.owner, self.fence, self.path)
        self.assertIs(caught.exception, self.native_error)
        self.assertEqual([item[0] for item in self.calls], ["construct", "native", "finalize"])
        self.assertIs(self.calls[-1][1], self.native_error)
        self.assertEqual(self.owner.admissions, {})

    def test_original_admission_cancellation_survives_secondary_finalizer_failure(self):
        self.admit_error = KeyboardInterrupt("SYNTHETIC_ADMISSION_CANCEL")
        self.finalize_error = OSError("SYNTHETIC_FINALIZE")
        with self.assertRaises(KeyboardInterrupt) as caught:
            S.admit(self.owner, self.fence, self.path)
        self.assertIs(caught.exception, self.admit_error)
        self.assertIs(self.calls[-1][1], self.admit_error)
        self.assertEqual(self.owner.admissions, {})

    def test_provisional_ready_session_does_not_replace_actual_failed_close(self):
        self.finalize_error = OSError("SYNTHETIC_FINAL_CLOSE")
        with self.assertRaises(OSError) as caught:
            S.admit(self.owner, self.fence, self.path)
        self.assertIs(caught.exception, self.finalize_error)
        self.assertEqual(O.parse(self.files["session-result.json"])["result"], "READY_FOR_CALLER_SEAL")
        self.assertNotIn("open", [item[0] for item in self.calls])
        self.assertEqual(self.owner.admissions, {})

    def test_returned_query_session_cannot_cross_original_work_cutoff(self):
        self.finalize_time = 1075 * O.NS
        with self.assertRaises(O.OriginError):
            S.admit(self.owner, self.fence, self.path)
        self.assertNotIn("open", [item[0] for item in self.calls])
        self.assertEqual(self.owner.admissions, {})

    def test_unknown_query_finalization_quarantines_instead_of_registering_return(self):
        self.supplier.unknown = True
        with self.assertRaises(O.OriginError):
            S.admit(self.owner, self.fence, self.path)
        self.assertTrue(self.owner.unknown)
        self.assertEqual(self.owner.admissions, {})
        with self.assertRaises(O.OriginError):
            self.owner.close()
        S.QUARANTINE.remove(self.owner)

    def test_failed_query_constructor_is_not_retired_as_a_returned_supplier(self):
        self.constructor_error = OSError("SYNTHETIC_CONSTRUCTOR")
        with self.assertRaises(OSError) as caught:
            S.admit(self.owner, self.fence, self.path)
        self.assertIs(caught.exception, self.constructor_error)
        self.assertEqual([item[0] for item in self.calls], ["construct"])
        self.assertEqual(self.owner.admissions, {})


class HttpFixtures:
    def setUp(self):
        super().setUp()
        self.requests, self.connections, self.responses = [], [], []
        self.http_failure = self.close_failure = self.reader_close_failure = None
        self.reader_closes = 0
        self.before_request = self.after_close = lambda: None
        self.before_construct_return = self.before_response_stream = lambda: None
        self.tls = object()
        self.stack.enter_context(patch.object(O.ssl, "create_default_context", return_value=self.tls))
        self.stack.enter_context(patch.object(O.http.client, "HTTPSConnection", side_effect=self.connection))
        self.fill_responses()

    def fill_responses(self):
        self.responses = []
        for body in service_bodies(self.admitted, self.clock).values():
            raw = S.I.encoded(body)
            self.responses.append(F.header(raw) + raw)

    def connection(self, host, *, timeout, context):
        self.assertEqual(host, "api.github.com")
        self.assertTrue(0 < timeout <= 5)
        self.assertIs(context, self.tls)
        case = self
        class Stream(io.BytesIO):
            def close(self):
                case.reader_closes += 1
                if case.reader_close_failure:
                    raise case.reader_close_failure
                super().close()
        class Socket:
            def makefile(self, mode):
                self.stream = Stream(case.responses.pop(0))
                case.before_response_stream()
                return self.stream
            def settimeout(self, seconds):
                case.assertTrue(0 < seconds <= 5)
        class Connection:
            def __init__(self): self.sock, self.closed = Socket(), False
            def request(self, method, path, *, headers):
                case.requests.append((method, path, headers))
                case.before_request()
                if case.http_failure:
                    raise case.http_failure
            def getresponse(self):
                result = self.response_class(self.sock, method="GET")
                result.begin()
                return result
            def close(self):
                self.closed = True
                case.after_close()
                if case.close_failure:
                    raise case.close_failure
        value = Connection(); self.connections.append(value)
        self.before_construct_return()
        return value

    def acquire(self, retain=None, end=None):
        self.retained, self.retained_failed = {}, {}
        def record(name, raw, *, failed):
            self.retained[name], self.retained_failed[name] = raw, failed
        return O.acquire(self.admitted, "e" * 32, TOKEN, retain or record,
                         self.fence, original_work_end=end or 1045 * O.NS)


class HttpTests(HttpFixtures, OfflineCase):
    def test_actual_closed_http_parser_keeps_exact_two_original_gets_and_no_token_in_records(self):
        raw, completed = self.acquire()
        self.assertEqual(raw, self.retained)
        self.assertEqual([row[1] for row in self.requests], [
            "/repos/p2pKit/P2pKit/actions/runs/123/attempts/1",
            "/repos/p2pKit/P2pKit/actions/runs/123/attempts/1/jobs?per_page=100&page=1"])
        self.assertTrue(all(row[0] == "GET" and row[2]["Authorization"] == "Bearer " + TOKEN for row in self.requests))
        self.assertTrue(all(connection.closed for connection in self.connections))
        self.assertGreaterEqual(completed, max(O.parse(value)["finishedNs"] for value in raw.values()))
        self.assertNotIn(TOKEN.encode(), b"".join(raw.values()))
        self.assertEqual(self.retained_failed, {"attempt": False, "jobs": False})
        self.assertIs(O.service_identity(self.admitted, raw, "e" * 32, self.clock, RUNNER)["exportSaveAuthority"], False)

    def test_request_failure_retains_original_before_error_and_never_retries(self):
        self.http_failure = O.OriginError("SYNTHETIC_HTTP_FAILURE")
        with self.assertRaisesRegex(O.OriginError, "SYNTHETIC_HTTP_FAILURE"):
            self.acquire()
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(set(self.retained), {"attempt"})
        self.assertIs(O.parse(self.retained["attempt"])["complete"], False)
        self.assertTrue(self.connections[0].closed)
        self.assertEqual(self.retained_failed, {"attempt": True})

    def test_original_parent_end_includes_retention_and_forbids_second_get(self):
        retained = {}
        def delayed(name, raw, *, failed):
            retained[name] = raw
            self.nanoseconds = 1045 * O.NS
        with self.assertRaises(O.OriginError):
            self.acquire(delayed)
        self.assertEqual(set(retained), {"attempt"})
        self.assertEqual(len(self.requests), 1)

    def test_child_start_does_not_renew_45_seconds_or_extend_short_remaining_request(self):
        self.nanoseconds = 1044 * O.NS
        def delay(): self.nanoseconds = 1045 * O.NS
        self.before_request = delay
        with self.assertRaises((O.OriginError, O.wire.BudgetError)):
            self.acquire()
        self.assertEqual(len(self.requests), 1)
        self.assertIs(O.parse(self.retained["attempt"])["complete"], False)

    def test_http_close_unknown_and_post_close_clock_failure_cannot_return_success(self):
        self.close_failure = OSError("synthetic close uncertainty")
        with self.assertRaises(O.OriginError):
            self.acquire()
        self.assertEqual(O.parse(self.retained["attempt"])["retirement"], "UNKNOWN")
        self.fill_responses(); self.requests.clear(); self.close_failure = None
        def backwards(): self.nanoseconds = 999 * O.NS
        self.after_close = backwards
        with self.assertRaises(O.clocks.ClockError):
            self.acquire()
        self.assertIsNone(O.parse(self.retained["attempt"])["finishedNs"])
        self.assertEqual(len(self.requests), 1)

    def test_failed_original_is_primary_when_its_retention_also_fails(self):
        first = O.OriginError("ORIGINAL_SYNTHETIC_ERROR")
        self.http_failure = first
        def fail(*_args, **_kwargs): raise OSError("secondary retention failure")
        with self.assertRaises(O.OriginError) as caught:
            self.acquire(fail)
        self.assertIs(caught.exception, first)

    def test_request_return_cannot_hide_an_intermediate_backward_clock(self):
        self.before_construct_return = lambda: setattr(self, "nanoseconds", 1002 * O.NS) if len(self.connections) == 1 else None
        self.before_request = lambda: setattr(self, "nanoseconds", 1001 * O.NS) if len(self.requests) == 1 else None
        self.after_close = lambda: setattr(self, "nanoseconds", 1003 * O.NS) if len(self.connections) == 1 else None
        with self.assertRaises(O.clocks.ClockError):
            self.acquire()
        self.assertEqual(len(self.requests), 1)
        self.assertIs(O.parse(self.retained["attempt"])["complete"], False)

    def test_parser_uses_latest_parent_highwater_not_request_start(self):
        self.before_construct_return = lambda: setattr(self, "nanoseconds", 1002 * O.NS) if len(self.connections) == 1 else None
        self.before_response_stream = lambda: setattr(self, "nanoseconds", 1001 * O.NS) if len(self.connections) == 1 else None
        self.after_close = lambda: setattr(self, "nanoseconds", 1003 * O.NS) if len(self.connections) == 1 else None
        with self.assertRaises(O.clocks.ClockError):
            self.acquire()
        self.assertEqual(len(self.requests), 1)
        self.assertIs(O.parse(self.retained["attempt"])["complete"], False)

    def test_unknown_http_close_carries_retirement_to_the_receiving_owner(self):
        self.close_failure = OSError("SYNTHETIC_CLOSE")
        with self.assertRaises(O.OriginError) as caught:
            self.acquire()
        detail = S.diagnostics._exception_detail(caught.exception)
        self.assertTrue(detail["retirementUnknown"])
        self.assertFalse(detail["incomplete"])
        self.assertIs(caught.exception.__cause__, self.close_failure)
        self.assertEqual(self.retained_failed, {"attempt": True})

    def test_close_cancellation_remains_the_original_exception(self):
        self.close_failure = KeyboardInterrupt("SYNTHETIC_CLOSE_CANCEL")
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.acquire()
        self.assertIs(caught.exception, self.close_failure)
        self.assertTrue(S.diagnostics._exception_detail(caught.exception)["retirementUnknown"])
        self.assertEqual(self.retained_failed, {"attempt": True})

    def test_eof_reader_close_unknown_survives_http_response_detach(self):
        self.reader_close_failure = OSError("SYNTHETIC_AUTOMATIC_EOF_CLOSE")
        with self.assertRaises(O.OriginError) as caught:
            self.acquire()
        self.assertEqual(self.reader_closes, 1)
        self.assertEqual(O.parse(self.retained["attempt"])["retirement"], "UNKNOWN")
        self.assertTrue(S.diagnostics._exception_detail(caught.exception)["retirementUnknown"])

    def test_eof_reader_close_cancellation_remains_original_and_unknown(self):
        self.reader_close_failure = KeyboardInterrupt("SYNTHETIC_AUTOMATIC_CLOSE_CANCEL")
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.acquire()
        self.assertIs(caught.exception, self.reader_close_failure)
        self.assertEqual(self.reader_closes, 1)
        self.assertEqual(O.parse(self.retained["attempt"])["retirement"], "UNKNOWN")
        self.assertTrue(S.diagnostics._exception_detail(caught.exception)["retirementUnknown"])

    def test_request_cancellation_is_not_replaced_by_later_unknown_close(self):
        self.http_failure = KeyboardInterrupt("SYNTHETIC_REQUEST_CANCEL")
        self.close_failure = OSError("SYNTHETIC_CLOSE")
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.acquire()
        self.assertIs(caught.exception, self.http_failure)
        self.assertTrue(S.diagnostics._exception_detail(caught.exception)["retirementUnknown"])
        self.assertEqual(len(self.requests), 1)

    def test_token_and_original_request_end_refuse_before_network(self):
        for token in (None, "short", "x" * 4097, "x" * 16 + "\n"):
            with self.subTest(token_type=type(token).__name__), self.assertRaises(O.OriginError):
                O.acquire(self.admitted, "e" * 32, token, lambda *_args, **_kwargs: None, self.fence,
                    original_work_end=1045 * O.NS)
        with self.assertRaises(O.OriginError):
            self.acquire(end=999 * O.NS)
        self.assertFalse(self.connections)

    def test_malformed_http_original_is_retained_without_second_request(self):
        self.responses[0] = self.responses[0].replace(b"200 OK", b"302 Found")
        with self.assertRaises(O.OriginError):
            self.acquire()
        self.assertEqual(len(self.requests), 1)
        value = O.parse(self.retained["attempt"])
        self.assertFalse(value["complete"])
        self.assertIn(b"302 Found", base64.b64decode(value["headersBase64"]))
        self.assertTrue(self.connections[0].closed)


class ControllerTests(HttpFixtures, OfflineCase):
    def setUp(self):
        super().setUp()
        require_uid = getattr(os, "geteuid", lambda: 0)()
        self.assertNotEqual(require_uid, 0, "tiny POSIX fixtures require an actual ordinary UID")
        self.temporary = tempfile.TemporaryDirectory(prefix="bootstrap-origin-model-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.event_path = self.base / "event.json"
        self.event_path.write_bytes(self.admitted.original_event)
        self.env.update(GITHUB_WORKSPACE=str(ROOT), GITHUB_EVENT_PATH=str(self.event_path), RUNNER_TEMP=str(self.base),
                        GITHUB_TOKEN="UNRELATED_SYNTHETIC_TOKEN_MUST_NOT_REACH_CHILD")
        self.env[O.wire.TOKEN_ENV] = TOKEN
        self.stack.enter_context(patch.dict(os.environ, self.env, clear=True))
        self.stack.enter_context(patch.object(S, "admit", side_effect=self.fake_admit))
        self.stack.enter_context(patch.object(S.processes, "make_scope", side_effect=self.make_scope))
        self.stack.enter_context(patch.object(S.signal, "getsignal", return_value=None))
        self.stack.enter_context(patch.object(S.signal, "signal", return_value=None))
        self.scopes, self.admissions, self.child_errors, self.child_envs, self.drains = [], [], [], [], []
        self.deadline_conversions = []
        directed = O.wire._directed_deadline
        def converted(local, seconds, fence, now):
            end = directed(local, seconds, fence, now)
            self.deadline_conversions.append((local, seconds, fence, now, end))
            return end
        self.stack.enter_context(patch.object(O.wire, "_directed_deadline", converted))
        self.close_scope_error = self.child_exit = self.ack_transform = None
        self.birth_transform = self.terminal_transform = None
        self.before_child = lambda argv: None
        self.child_write_return = lambda raw: len(raw)
        self.child_flush = lambda: None
        self.child_cancellation = None
        self.after_child = lambda: None
        self.after_drain = lambda: None
        self.cancelled = []
        self.addCleanup(self.reset_models)

    def reset_models(self):
        # Model-only uncertainty, not a recovery recipe for actual native UNKNOWN.
        for owner in S.QUARANTINE:
            for row in reversed(owner.resources):
                if row["label"] != "native-scope" and not row["attempted"]:
                    row["owner"].close()
        S.QUARANTINE.clear()

    def fake_admit(self, owner, fence, path, *, expected=None):
        self.assertNotIn(O.wire.TOKEN_ENV, os.environ)
        fence.now()
        self.admissions.append(path)
        directory = owner.new(path)
        for name, raw in (("admission.json", self.admitted.record), ("original-event.json", self.admitted.original_event),
                          ("original-policy.json", self.admitted.original_policy), ("recipient-public.asc", self.admitted.public_key)):
            owner.write(directory, name, raw)
        if expected is not None:
            self.assertEqual(expected, self.admitted)
        session = owner.write(directory, "session-result.json", {"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY",
            "job": "a" * 32, "queries": [], "result": "READY_FOR_CALLER_SEAL", "retirement": "KNOWN",
            "firstError": None, "errors": [], "readbacks": []})
        returned = {"admissionSha256": O.digest(self.admitted.record), "sessionSha256": O.digest(session),
            "clock": O.clock_value(fence.clock), "returnedNs": fence.now()}
        owner.admissions[str(path)] = (self.admitted, session, O.encoded(returned))
        return self.admitted, returned

    def make_scope(self, job, invocation, state, home):
        case = self
        class Scope:
            name = "linux-proc-pidfd"
            baseline = set()
            def __init__(self): self.launches, self.closed, self.descriptions = [], False, 0
            def _identity(self, pid):
                return {"pid": pid, "startTicks": 9012, "live": True}
            def spawn(self, argv, cwd, env, *, stdout, stderr):
                case.child_envs.append(dict(env))
                case.assertEqual(env[O.wire.TOKEN_ENV], TOKEN)
                case.assertNotIn("GITHUB_TOKEN", env)
                self.launches = [{"api": "subprocess.Popen", "requestedArgv": argv, "resolvedArgv": argv,
                    "cwd": cwd, "shell": False, "created": True, "executable": argv[0], "pid": 1234,
                    "outputMode": "caller-owned-files"}]
                case.before_child(argv)
                def write(raw):
                    # Explicit modeled capture corruption AFTER guarded() has
                    # serialized its final high-water. Child still observes a
                    # full write; the real parent must reject the original sink.
                    captured = case.ack_transform(raw) if case.ack_transform else raw
                    # Native child output goes through its inherited regular
                    # file descriptor, not through the parent's Python owner.
                    case.assertEqual(os.write(stdout.fileno(), captured), len(captured))
                    return case.child_write_return(raw)
                def flush():
                    stdout.sync()
                    case.child_flush()
                output = SimpleNamespace(buffer=SimpleNamespace(write=write, flush=flush))
                def operation(cancelled):
                    case.child_cancellation = cancelled
                    return S.service_child(argv[-3], int(argv[-1]), cancelled)
                code = 0
                try:
                    with patch.dict(os.environ, env, clear=True), patch.object(S.sys, "stdout", output):
                        S.guarded(operation)
                except BaseException as error:
                    case.child_errors.append(error)
                    os.write(stderr.fileno(), b"SYNTHETIC_CHILD_FAILURE\n")
                    code = 125
                case.after_child()
                return SimpleNamespace(pid=1234, stdout=None, stderr=None,
                    poll=lambda: code if case.child_exit is None else case.child_exit)
            def description(self):
                value = {"backend": "linux-proc-pidfd", "scope": "controlled-marker-inheriting-descendants",
                    "job": job, "invocation": invocation, "launches": self.launches,
                    "startedIdentities": [{"pid": 1234, "startTicks": 5678, "uid": os.getuid(), "live": False}],
                    "discoveryErrors": [], "discoveryReconciliations": []}
                transform = case.birth_transform if self.descriptions == 0 else case.terminal_transform
                self.descriptions += 1
                if transform:
                    transform(value)
                return value
            def discover(self): return []
            def drain(self, *, grace, kill_wait, deadline):
                final = O.parse((Path(state) / "service/start.json").read_bytes())["finalEndNs"]
                # The actual conversion samples LOCAL before RAW. Later RAW
                # observations cannot be used to reconstruct that saved end.
                local, maximum, ceiling, observed, expected = case.deadline_conversions[-1]
                case.assertEqual((maximum, ceiling), (45, final))
                case.assertLess(local, observed / O.NS)
                case.assertEqual(deadline, expected)
                remaining = max(0, deadline - case.nanoseconds / O.NS)
                case.assertEqual((grace, kill_wait), (min(5, remaining), min(5, max(0, remaining - grace))))
                case.drains.append({"grace": grace, "kill_wait": kill_wait, "deadline": deadline})
                case.after_drain()
                return []
            def close(self):
                self.closed = True
                if case.close_scope_error:
                    raise case.close_scope_error
        scope = Scope(); self.scopes.append(scope)
        return scope

    def test_complete_actual_source_composition_retains_originals_without_product_authority(self):
        result, fence, end = S.prepare_originals(self.cancelled)
        self.assertFalse(self.child_errors, self.child_errors)
        self.assertEqual(result["scope"], "BOOTSTRAP_PREPARE_HANDOFF_PENDING_STEP_RETURN_V1")
        self.assertEqual(result["budgetAcceptance"], "NOT_ADMITTED")
        self.assertIs(result["exportSaveAuthority"], False)
        self.assertEqual(end, fence.first + 120 * O.NS)
        self.assertEqual(len(self.scopes), 1)
        self.assertTrue(self.scopes[0].closed)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(len(self.admissions), 2)
        path = self.admissions[0].parent
        handoff_raw = (path / "prepare-handoff.json").read_bytes()
        self.assertEqual(O.digest(handoff_raw), result["handoffSha256"])
        self.assertEqual(O.parse(handoff_raw)["originSha256"], O.digest((path / "origin-result.json").read_bytes()))
        self.assertNotIn(TOKEN.encode(), b"".join(p.read_bytes() for p in path.rglob("*") if p.is_file()))
        self.assertFalse((path / "state").exists())
        self.assertNotIn(O.wire.TOKEN_ENV, os.environ)

    def test_same_episode_cannot_retry_acquisition_or_renew_original_clock(self):
        S.prepare_originals([])
        before = len(self.requests)
        os.environ[O.wire.TOKEN_ENV] = TOKEN
        with self.assertRaises(Exception):
            S.prepare_originals([])
        self.assertEqual(len(self.requests), before)

    def test_nonzero_exit_rejects_even_with_complete_original_success_ack(self):
        self.child_exit = 125
        with self.assertRaises(O.OriginError):
            S.prepare_originals([])
        self.assertFalse(self.child_errors)
        self.assertEqual(len(self.admissions), 1)
        self.assertTrue(self.scopes[0].closed)

    def test_unknown_outer_close_cannot_be_replaced_by_child_file_retirement(self):
        self.close_scope_error = OSError("synthetic native close uncertainty")
        with self.assertRaises(Exception):
            S.prepare_originals([])
        self.assertTrue(S.QUARANTINE)
        self.assertFalse(self.child_errors)

    def reject_ack(self, change):
        def transform(raw):
            value = O.parse(raw)
            change(value)
            return O.encoded(value)
        self.ack_transform = transform
        with self.assertRaises(O.OriginError):
            S.prepare_originals([])
        self.assertFalse(self.child_errors, self.child_errors)
        self.assertEqual(len(self.admissions), 1)

    def test_child_ack_terminal_digest_is_required_after_actual_child_return(self):
        self.reject_ack(lambda ack: ack.update(terminalSha256="a" * 64))

    def test_child_ack_scope_is_required_after_actual_child_return(self):
        self.reject_ack(lambda ack: ack.update(scope="SUCCESS"))

    def test_child_ack_original_post_close_highwater_is_required(self):
        self.reject_ack(lambda ack: ack.update(closedNs=999 * O.NS))

    def test_original_birth_backend_is_required_not_only_launch_equality(self):
        self.birth_transform = lambda value: value.update(backend="invented")
        with self.assertRaises(O.OriginError):
            S.prepare_originals([])
        self.assertFalse(self.child_errors, self.child_errors)

    def test_original_birth_job_and_domain_are_required(self):
        self.birth_transform = lambda value: value.update(job="b" * 32, scope="unowned")
        with self.assertRaises(O.OriginError):
            S.prepare_originals([])
        self.assertFalse(self.child_errors, self.child_errors)

    def test_late_native_return_fails_and_known_resources_still_close(self):
        def late(): self.nanoseconds = 1120 * O.NS
        self.after_child = late
        with self.assertRaises(Exception):
            S.prepare_originals([])
        self.assertTrue(self.scopes[0].closed)
        self.assertFalse(self.child_errors)
        self.assertEqual(len(self.admissions), 1)
        self.assertEqual(self.drains, [])

    def test_raw_expiry_after_drain_cannot_accept_native_retirement(self):
        def late():
            local = self.nanoseconds / O.NS
            self.nanoseconds = 1120 * O.NS
            self.stack.enter_context(patch.object(S.time, "monotonic", return_value=local))
        self.after_drain = late
        with self.assertRaises(O.OriginError):
            S.prepare_originals([])
        self.assertEqual(len(self.drains), 1)
        self.assertTrue(self.scopes[0].closed)
        self.assertFalse(self.child_errors)

    def test_bound_failure_skips_drain_and_preserves_original_error_and_close(self):
        first = O.OriginError("MODELED_DRAIN_BOUND_FAILURE")
        original, armed = O.Fence.deadline, [False]
        self.after_child = lambda: armed.__setitem__(0, True)
        def deadline(fence, maximum, **kwargs):
            if maximum == 45 and kwargs.get("limit") is not None and kwargs.get("final") and armed[0]:
                raise first
            return original(fence, maximum, **kwargs)
        with patch.object(O.Fence, "deadline", deadline), self.assertRaises(O.OriginError) as caught:
            S.prepare_originals([])
        self.assertIs(caught.exception, first)
        self.assertEqual(self.drains, [])
        self.assertTrue(self.scopes[0].closed)

    def test_postclose_raw_observation_cannot_cross_the_saved_local_drain_end(self):
        close, observe = S.Owner.close_one, O.clocks.observe
        state = {"armed": False, "crossed": False}
        def closed(owner, resource):
            result = close(owner, resource)
            if resource in self.scopes and self.drains and not state["crossed"]:
                state["armed"] = True
            return result
        def later():
            if state["armed"]:
                state.update(armed=False, crossed=True)
                self.nanoseconds = math.ceil(self.drains[-1]["deadline"] * O.NS)
                self.assertLess(self.nanoseconds, 1090 * O.NS)
            return observe()
        with patch.object(S.Owner, "close_one", closed), \
                patch.object(O.clocks, "observe", side_effect=later), self.assertRaises(S.posix.EvidenceError):
            S.prepare_originals([])
        self.assertTrue(state["crossed"])
        self.assertTrue(self.scopes[0].closed)
        self.assertTrue(S.QUARANTINE)
        owner = S.QUARANTINE[-1]
        self.assertTrue(owner.unknown)
        captures = [row for row in owner.resources if row["label"] in ("stdout", "stderr")]
        self.assertEqual(len(captures), 2)
        self.assertTrue(all(not row["attempted"] and not row["closed"] for row in captures))

    def test_near_work_return_keeps_original_capture_lifetime_through_known_drain(self):
        def approach_work():
            path = self.admissions[0].parent
            self.nanoseconds = O.parse((path / "service/start.json").read_bytes())["workEndNs"] - 2 * O.NS
        self.after_child = approach_work
        self.after_drain = lambda: setattr(self, "nanoseconds", self.nanoseconds + 3 * O.NS)
        S.prepare_originals([])
        path = self.admissions[0].parent
        phase = O.parse((path / "service/result.json").read_bytes())
        self.assertLess(phase["completedNs"], phase["workEndNs"])
        self.assertGreater(phase["finalizedNs"], phase["workEndNs"])
        self.assertLess(phase["finalizedNs"], phase["finalEndNs"])
        self.assertEqual(phase["errors"], [])
        self.assertEqual(phase["retirement"], "KNOWN")
        self.assertEqual(len(self.requests), 2)

    def test_credential_and_execution_overrides_fail_before_private_allocation(self):
        os.environ["PYTHONPATH"] = "/SYNTHETIC/override"
        with self.assertRaisesRegex(O.OriginError, "AMBIENT_EXECUTION_OVERRIDE"):
            S.prepare_originals([])
        self.assertFalse(self.scopes)
        self.assertFalse(list(self.base.glob("p2pkit-cache-originals-*")))

    def reject_original_mutation(self, relative, mutate):
        original = S.revalidate
        def changed(owner, private, *args):
            target = private.path / relative
            self.assertTrue(target.is_file())
            mutate(target)
            return original(owner, private, *args)
        with patch.object(S, "revalidate", side_effect=changed), self.assertRaises((O.OriginError, OSError)):
            S.prepare_originals([])
        self.assertEqual(len(self.admissions), 1)
        self.assertEqual(len(self.requests), 2)
        self.assertFalse(self.child_errors, self.child_errors)
        self.assertFalse((self.admissions[0].parent / "origin-result.json").exists())

    def test_missing_original_baseline_is_not_recreated_after_retirement(self):
        self.reject_original_mutation("service/baseline.json", lambda path: path.unlink())

    def test_replaced_original_baseline_is_not_accepted_from_matching_service_exit(self):
        self.reject_original_mutation("service/baseline.json", lambda path: path.write_bytes(
            O.encoded({"role": "linux-x64", "baseline": [[9999, 1]], "kernelJob": False})))

    def test_original_admission_return_bytes_are_not_replaced_by_their_labels(self):
        self.reject_original_mutation("admission-return.json", lambda path: path.write_bytes(b" " + path.read_bytes()))

    def test_original_native_query_session_is_hash_bound_and_reread(self):
        self.reject_original_mutation("admission/session-result.json", lambda path: path.write_bytes(b" " + path.read_bytes()))

    def test_original_prelude_bytes_cannot_be_rebuilt_from_context(self):
        self.reject_original_mutation("prelude.json", lambda path: path.write_bytes(b" " + path.read_bytes()))

    def test_revalidation_is_repeatable_read_only_inside_the_same_owning_call(self):
        original, observed = S.revalidate, []
        def repeated(owner, private, *args):
            before = {str(path): path.read_bytes() for path in private.path.rglob("*") if path.is_file()}
            first = original(owner, private, *args)
            second = original(owner, private, *args)
            self.assertEqual(first["phaseSha256"], second["phaseSha256"])
            self.assertEqual(first["admissionOriginals"], second["admissionOriginals"])
            self.assertLessEqual(first["revalidatedNs"], second["revalidatedNs"])
            self.assertEqual(before, {str(path): path.read_bytes() for path in private.path.rglob("*") if path.is_file()})
            observed.append(second)
            return second
        with patch.object(S, "revalidate", side_effect=repeated):
            S.prepare_originals([])
        self.assertEqual(len(observed), 2)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(len(self.admissions), 2)

    def test_copied_phase_admission_or_foreign_owner_cannot_supply_current_provenance(self):
        original = S.revalidate
        def probe(owner, private, context, admitted, phase, fence):
            foreign = S.Owner(owner.local_end, fence)
            cloned = copy.copy(phase)
            self.assertIsNot(cloned, phase)
            for other_owner, other_admitted, other_phase in ((foreign, admitted, phase),
                    (owner, admitted, cloned), (owner, copy.copy(admitted), phase), (owner, admitted, dict(phase.records))):
                with self.subTest(owner=other_owner is owner, phase=type(other_phase).__name__), self.assertRaises(O.OriginError):
                    original(other_owner, private, context, other_admitted, other_phase, fence)
            self.assertEqual(foreign.resources, [])
            foreign.close()
            return original(owner, private, context, admitted, phase, fence)
        with patch.object(S, "revalidate", side_effect=probe):
            S.prepare_originals([])
        self.assertEqual(len(self.requests), 2)

    def test_closed_context_schema_refuses_extra_fields_override_or_false_authority(self):
        _, fence, _ = S.prepare_originals([])
        path = self.admissions[0].parent
        context = O.parse((path / "context.json").read_bytes())
        for key, value in (("extra", True), ("root", "/SYNTHETIC/foreign"), ("job", "not-an-id"),
                ("budgetAcceptance", "ADMITTED"), ("exportSaveAuthority", True), ("admissionReturnedNs", True),
                ("runnerName", "runner\n"), ("inheritedContext", {S.processes.JOB_ENV: "f" * 32})):
            with self.subTest(field=key), self.assertRaises(O.OriginError):
                S.context_record(O.encoded({**context, key: value}), self.admitted, path, fence)

    def test_closed_prelaunch_schema_refuses_ordinary_or_renewed_execution(self):
        _, fence, _ = S.prepare_originals([])
        path = self.admissions[0].parent
        context_raw = (path / "context.json").read_bytes()
        context, start = O.parse(context_raw), O.parse((path / "service/start.json").read_bytes())
        for key, value in (("extra", True), ("cwd", "/SYNTHETIC/foreign"), ("job", "c" * 32),
                ("retirement", "KNOWN"), ("exitCode", 0), ("argv", ["help"]), ("invocation", "bad"),
                ("workEndNs", fence.first + 5400 * O.NS), ("finalEndNs", fence.first + 5400 * O.NS)):
            with self.subTest(field=key), self.assertRaises(O.OriginError):
                S.start_record(O.encoded({**start, key: value}), context_raw, context, path, fence)

    def test_first_child_read_must_follow_latest_pre_spawn_floor_not_only_phase_start(self):
        self.before_child = lambda argv: setattr(self, "nanoseconds", int(argv[-1]) - 2000)
        self.after_child = lambda: setattr(self, "nanoseconds", 1002 * O.NS)
        with self.assertRaises(O.OriginError):
            S.prepare_originals([])
        self.assertEqual(len(self.child_errors), 1)
        self.assertEqual(str(self.child_errors[0]), "BOOTSTRAP_CHILD_PRECEDES_LAUNCH")
        self.assertFalse(self.requests)

    def test_child_metadata_clock_regression_cannot_recover_before_frame_binding(self):
        original = S.Owner.read
        def read(owner, directory, name, *args, **kwargs):
            raw = original(owner, directory, name, *args, **kwargs)
            if owner.first is not None and name == "context.json":
                self.nanoseconds = owner.early_last - 2000
            return raw
        self.after_child = lambda: setattr(self, "nanoseconds", 1002 * O.NS)
        with patch.object(S.Owner, "read", read), self.assertRaises(O.OriginError):
            S.prepare_originals([])
        self.assertIsInstance(self.child_errors[0], O.clocks.ClockError)
        self.assertFalse(self.requests)

    def test_work_expired_http_failure_uses_only_remaining_original_final_custody(self):
        self.before_child = lambda argv: setattr(self, "nanoseconds", self.nanoseconds + 3 * O.NS)
        def expire():
            path = self.admissions[0].parent
            self.nanoseconds = O.parse((path / "service/start.json").read_bytes())["workEndNs"]
        self.before_request = expire
        with self.assertRaises(O.OriginError):
            S.prepare_originals([])
        path = self.admissions[0].parent
        record = O.parse((path / "service/attempt.json").read_bytes())
        self.assertFalse(record["complete"])
        self.assertEqual(record["retirement"], "KNOWN")
        self.assertTrue((path / "service/child-failure.json").is_file())
        self.assertFalse((path / "service/jobs.json").exists())
        self.assertFalse((path / "origin-result.json").exists())
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(len(self.admissions), 1)
        self.assertFalse(S.QUARANTINE)
        self.assertTrue(self.scopes[0].closed)
        phase = O.parse((path / "service/result.json").read_bytes())
        self.assertEqual(phase["captureOutcomes"], {name: {"synced": True, "verified": True,
            "closeAttempted": True, "closed": True, "readback": True} for name in ("stdout", "stderr")})

    def test_http_unknown_reaches_actual_child_owner_and_cannot_emit_success_ack(self):
        self.reader_close_failure = OSError("SYNTHETIC_EOF_UNCERTAINTY")
        with self.assertRaises(O.OriginError):
            S.prepare_originals([])
        path = self.admissions[0].parent
        self.assertEqual(O.parse((path / "service/attempt.json").read_bytes())["retirement"], "UNKNOWN")
        self.assertEqual((path / "service/stdout.log").read_bytes(), b"")
        self.assertTrue(any(owner.first is not None and owner.unknown for owner in S.QUARANTINE))
        self.assertTrue(S.diagnostics._exception_detail(self.child_errors[0])["retirementUnknown"])
        self.assertEqual(len(self.requests), 1)

    def test_child_cancellation_keeps_failed_original_and_forbids_second_get(self):
        self.before_request = lambda: self.child_cancellation.append(S.signal.SIGTERM)
        with self.assertRaises(O.OriginError):
            S.prepare_originals([])
        self.assertIsInstance(self.child_errors[0], KeyboardInterrupt)
        path = self.admissions[0].parent
        self.assertFalse(O.parse((path / "service/attempt.json").read_bytes())["complete"])
        self.assertTrue((path / "service/child-failure.json").is_file())
        self.assertEqual(len(self.requests), 1)

    def reject_raw_ack(self, transform):
        self.ack_transform = transform
        with self.assertRaises((ValueError, O.OriginError)):
            S.prepare_originals([])
        self.assertFalse(self.child_errors, self.child_errors)
        self.assertEqual(len(self.admissions), 1)

    def test_duplicate_ack_cannot_be_promoted_from_successful_native_exit(self):
        self.reject_raw_ack(lambda raw: raw + raw)

    def test_trailing_ack_bytes_cannot_be_reencoded_as_original(self):
        self.reject_raw_ack(lambda raw: raw + b" ")

    def test_short_ack_write_fails_even_if_provisional_bytes_escaped(self):
        self.child_write_return = lambda raw: len(raw) - 1
        with self.assertRaises(O.OriginError):
            S.prepare_originals([])
        self.assertEqual(str(self.child_errors[0]), "BOOTSTRAP_ACK_WRITE")
        self.assertTrue((self.admissions[0].parent / "service/stdout.log").read_bytes())
        self.assertEqual(len(self.admissions), 1)

    def test_late_ack_flush_fails_despite_complete_provisional_output(self):
        def expire():
            path = self.admissions[0].parent
            self.nanoseconds = O.parse((path / "service/start.json").read_bytes())["workEndNs"]
        self.child_flush = expire
        with self.assertRaises(O.OriginError):
            S.prepare_originals([])
        self.assertIsInstance(self.child_errors[0], O.OriginError)
        self.assertTrue((self.admissions[0].parent / "service/stdout.log").read_bytes())
        self.assertEqual(len(self.admissions), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
