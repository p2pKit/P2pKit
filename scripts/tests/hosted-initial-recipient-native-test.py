#!/usr/bin/env python3
"""Guarded offline parent/child composition, NOT hosted/native qualification.

Actual tiny private POSIX files require an ordinary UID. All Git child, HTTP,
native clock/scope, cancellation and service observations are explicit models.
The real controller, acquisition, parsers, GitView and retained readers compose;
no provider, crypto, application or external process is executed by these tests.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import ctypes  # Only stdlib Python-API initialization precedes the audit guard.
import dataclasses
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


N = load("initial_native_test_subject", ROOT / "scripts/run-hosted-initial-recipient.py")
F = load("initial_native_acquisition_fixtures", Path(__file__).with_name("hosted-initial-recipient-originals-test.py"))
S, O, I, Q = N.native, N.O, N.I, N.Q
TOKEN = F.TOKEN


class NativeModels(unittest.TestCase):
    def setUp(self):
        self.assertNotEqual(os.geteuid(), 0, "tiny POSIX file controls require an actual ordinary UID")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fixture = F.OriginalModels("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.temp = tempfile.TemporaryDirectory(prefix="initial-native-model-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.event = self.base / "event.json"
        self.queries, self.scopes, self.child_errors, self.child_envs, self.drains = [], [], [], [], []
        self.query_close_error = self.scope_close_error = self.child_exit = self.ack_transform = None
        self.before_child = self.after_child = self.after_drain = lambda: None
        self.before_query = lambda path: None
        self.after_query_close = lambda path: None
        self.scope_survivors = []
        self.cancelled = []
        self.stack.enter_context(patch.object(Q, "NativeGitQueries", side_effect=self.make_queries))
        self.stack.enter_context(patch.object(S.processes, "make_scope", side_effect=self.make_scope))
        self.stack.enter_context(patch.object(N.time, "time", return_value=F.F.FIRST1))
        self.stack.enter_context(patch.object(S.time, "sleep", side_effect=lambda seconds: None))
        self.stack.enter_context(patch.object(S.signal, "getsignal", return_value=None))
        self.stack.enter_context(patch.object(S.signal, "signal", return_value=None))
        self.stack.enter_context(patch.dict(os.environ, {}, clear=True))
        self.choose("gate", "full-macos-arm64")
        self.addCleanup(self.reset_models)

    def reset_models(self):
        # The uncertainty here belongs exclusively to fake native domains.
        # Close their real tiny fixture streams before releasing model owners;
        # never treat this test teardown as a recovery path for native UNKNOWN.
        for owner in S.QUARANTINE:
            for row in reversed(owner.resources):
                if row["label"] != "native-scope" and not row["attempted"]:
                    row["owner"].close()
        S.QUARANTINE.clear()
        Q.QUARANTINE.clear()
        S.diagnostics._QUARANTINE.clear()
        N._PREPARED_RETURNS.clear()
        N._WORKER_USES.clear()
        N._WORKER_CLAIMS.clear()
        N._ENTRY_WINDOWS.clear()
        N._READMISSION_RETURNS.clear()
        N._READMISSION_ATTEMPTS.clear()

    def choose(self, kind, selection):
        self.fixture.choose(kind, selection)
        self.event.write_bytes(I.encoded(self.fixture.event))
        env = dict(self.fixture.env, GITHUB_WORKSPACE=str(ROOT), GITHUB_EVENT_PATH=str(self.event), RUNNER_TEMP=str(self.base),
                   GITHUB_TOKEN="UNRELATED_SYNTHETIC_TOKEN")
        env[O.wire.TOKEN_ENV] = TOKEN
        os.environ.clear()
        os.environ.update(env)
        self.path = N.location()[1]

    def make_queries(self, root, path, *, check_cancel, owner_deadlines):
        case = self
        self.before_query(path)
        class Queries:
            def __init__(self):
                self.path, self.unknown, self.closed, self.finalizations = path, False, False, 0
                self.deadlines, self.calls, self.host_checked = owner_deadlines, [], False
                self.private = Q._new_private_directory(path)
                case.queries.append(self)
            def native_host_matches_actions(self):
                self.host_checked = True
                case.assertNotIn(O.wire.TOKEN_ENV, os.environ)
            def __call__(self, **kwargs):
                check_cancel()
                case.assertTrue(self.host_checked)
                case.assertNotIn(O.wire.TOKEN_ENV, kwargs["environment"])
                case.assertNotIn("GITHUB_TOKEN", kwargs["environment"])
                case.assertNotIn(TOKEN, repr(kwargs))
                case.assertEqual(kwargs["cwd"], root)
                suffix = kwargs["argv"][7:]
                case.assertTrue(Q._allowed_suffix(suffix))
                self.calls.append(suffix)
                git = case.fixture.git
                if suffix == ("rev-parse", "--show-toplevel"):
                    return (str(root) + "\n").encode() if git.root_value else b"/wrong\n"
                if suffix == ("status", "--porcelain=v1", "--untracked-files=all"):
                    return b"" if git.clean_value else b" M changed\n"
                if suffix[:2] == ("rev-parse", "--verify"):
                    ref = suffix[2]
                    value = (git.head if ref == "HEAD^{commit}" else git.main if ref == "refs/remotes/origin/main^{commit}" else
                             git.main_tree if ref == N.acquisition.stages.BASE["commit"] + "^{tree}" else git.tree_value)
                    return value.encode() + b"\n"
                return git.query(*suffix, limit=kwargs["stdout_limit"])
            def _write(self, directory, name, raw):
                if type(raw) is not bytes:
                    raw = O.encoded(raw)
                stream = directory.create_file(name, max_bytes=max(1, len(raw)), deadline=self.deadlines[1])
                try:
                    case.assertEqual(stream.write(raw), len(raw))
                    stream.sync()
                finally:
                    stream.close()
            def _finalize(self, failure):
                self.finalizations += 1
                case.assertEqual(self.finalizations, 1)
                self._write(self.private, "session-result.json", {"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY",
                    "job": "a" * 32, "queries": [list(x) for x in self.calls], "readbacks": [],
                    "result": "READY_FOR_CALLER_SEAL" if failure is None else "HOLD", "retirement": "KNOWN",
                    "firstError": None if failure is None else "SYNTHETIC_QUERY_FAILURE", "errors": [] if failure is None else ["SYNTHETIC"]})
                self.private.close()
                self.closed = True
                case.after_query_close(path)
                if case.query_close_error is not None:
                    raise case.query_close_error
        return Queries()

    def make_scope(self, job, invocation, state, home):
        case = self
        class Scope:
            name, baseline = "linux-proc-pidfd", set()
            def __init__(self): self.launches, self.closed, self.close_calls = [], False, 0
            def _identity(self, pid): return {"pid": pid, "startTicks": 9012, "live": True}
            def spawn(self, argv, cwd, env, *, stdout, stderr):
                case.before_child()
                case.child_envs.append(dict(env))
                case.assertEqual(env[O.wire.TOKEN_ENV], TOKEN)
                case.assertNotIn("GITHUB_TOKEN", env)
                case.assertEqual(argv[4], str(ROOT / "scripts/run-hosted-initial-recipient.py"))
                self.launches = [{"api": "subprocess.Popen", "requestedArgv": argv, "resolvedArgv": argv,
                    "cwd": cwd, "shell": False, "created": True, "executable": argv[0], "pid": 1234, "outputMode": "caller-owned-files"}]
                def write(raw):
                    captured = case.ack_transform(raw) if case.ack_transform else raw
                    case.assertEqual(os.write(stdout.fileno(), captured), len(captured))
                    return len(raw)
                output = SimpleNamespace(buffer=SimpleNamespace(write=write, flush=stdout.sync))
                code = 0
                try:
                    with patch.dict(os.environ, env, clear=True), patch.object(S.sys, "stdout", output):
                        case.assertIn(argv[5], ("_service", "_service-entry"))
                        S.guarded(lambda cancelled: N.service_child(argv[-3], int(argv[-1]), cancelled,
                            entry=argv[5] == "_service-entry"))
                except BaseException as error:
                    case.child_errors.append(error)
                    os.write(stderr.fileno(), b"SYNTHETIC_CHILD_FAILURE\n")
                    code = 125
                case.after_child()
                return SimpleNamespace(pid=1234, stdout=None, stderr=None, poll=lambda: code if case.child_exit is None else case.child_exit)
            def description(self):
                return {"backend": self.name, "scope": "controlled-marker-inheriting-descendants", "job": job, "invocation": invocation,
                    "launches": self.launches, "startedIdentities": [{"pid": 1234, "startTicks": 5678, "uid": os.getuid(), "live": False}],
                    "discoveryErrors": [], "discoveryReconciliations": []}
            def discover(self): return []
            def drain(self, *, grace, kill_wait, deadline):
                start = json.loads((Path(state) / "service/start.json").read_bytes())
                case.assertLessEqual(deadline, start["finalEndNs"] / O.NS)
                case.assertLessEqual(grace + kill_wait, max(0, deadline - case.fixture.ns / O.NS))
                case.drains.append((grace, kill_wait, deadline))
                case.after_drain()
                return case.scope_survivors
            def close(self):
                self.closed = True
                self.close_calls += 1
                if case.scope_close_error is not None:
                    raise case.scope_close_error
        value = Scope()
        self.scopes.append(value)
        return value

    def prepare(self):
        return N.prepare_originals(self.cancelled)

    def changed_json(self, path, change):
        raw = json.loads(path.read_bytes())
        change(raw)
        path.write_bytes(O.encoded(raw))

    def late_return_change(self, boundary, change, check):
        """Mutate data at an actual final modeled boundary, not its registry."""
        calls = []
        if boundary == "raw":
            def observe():
                reading = self.fixture.observe()
                calls.append("raw")
                change()
                return reading
            replacement = patch.object(O.clocks, "observe", side_effect=observe)
        elif boundary == "local":
            deadline = S.posix._deadline
            def local(end):
                deadline(end)
                calls.append("local")
                change()
            replacement = patch.object(S.posix, "_deadline", side_effect=local)
        else:
            self.assertEqual(boundary, "cancel")
            cancellation = S.cancellation
            def cancel(value):
                cancellation(value)
                calls.append("cancel")
                if len(calls) == 2:
                    change()  # The final call, not the initial cancellation check.
            replacement = patch.object(S, "cancellation", side_effect=cancel)
        with replacement, self.assertRaises(I.AdmissionError):
            check()
        self.assertEqual(len(calls), 2 if boundary == "cancel" else 1)

    def final_record_change(self, boundary, *, identity):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        binding = N._PREPARED_RETURNS[id(original)]
        if identity:
            change = lambda: object.__setattr__(original.identity, "record", b"SYNTHETIC_CHANGED_IDENTITY\n")
            check = lambda: N.original_worker_identity(original)
        else:
            def change():
                object.__setattr__(original, "service_time_raw", b"SYNTHETIC_CHANGED_BASIS\n")
                object.__setattr__(original, "proposal_raw", b"SYNTHETIC_CHANGED_PROPOSAL\n")
            check = lambda: N.original_worker_time_records(original)
        self.late_return_change(boundary, change, check)
        self.assertEqual(N._PREPARED_RETURNS[id(original)].identity_fields, binding.identity_fields)
        self.assertEqual(N._PREPARED_RETURNS[id(original)].service_time_raw, binding.service_time_raw)
        self.assertEqual(N._PREPARED_RETURNS[id(original)].proposal_raw, binding.proposal_raw)
        self.assertEqual(len(self.fixture.requests), 8)

    def test_complete_gate_composes_real_controller_acquisition_queries_and_retained_readers(self):
        value, fence, end = self.prepare()
        self.assertEqual(value["scope"], N.OUTPUT_SCOPE)
        self.assertEqual(end, fence.final)
        self.assertFalse(value["exportSaveAuthority"])
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual([len(x.calls) for x in self.queries], [12, 24, 12])
        self.assertTrue(all(x.closed and x.finalizations == 1 for x in self.queries))
        self.assertEqual(len(self.fixture.requests), 8)
        self.assertEqual(len(self.scopes), 1)
        self.assertEqual(self.scopes[0].close_calls, 1)
        self.assertEqual(len(self.drains), 1)
        match = json.loads((self.path / "acquisition-queries/match.bin").read_bytes())
        self.assertEqual(match["scope"], "NONPRODUCTIVE_ELIGIBILITY")
        self.assertEqual(match["github"]["job"], "initial-recipient-gate")
        self.assertEqual(match["workerAdmission"], "NOT_PERFORMED")
        self.assertEqual((self.path / "acquisition-queries/base_policy_entry.bin").read_bytes(), b"")
        self.assertTrue(all(TOKEN.encode() not in p.read_bytes() for p in self.path.rglob("*") if p.is_file()))

    def test_worker_keeps_its_actual_populate_identity_and_still_has_no_admission(self):
        self.choose("worker", "desktop-linux-x64")
        self.prepare()
        match = json.loads((self.path / "acquisition-queries/match.bin").read_bytes())
        self.assertEqual(match["github"]["job"], "populate")
        self.assertEqual(match["github"]["selection"], "desktop-linux-x64")
        self.assertIn("MATCH_ONLY_NOT_ADMISSION", match["scope"])

    def test_original_worker_return_binds_explicit_head_policy_identity_not_admission(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        value = N.original_worker_identity(original)
        self.assertIs(type(value), N.initial_identity.InitialBootstrapIdentity)
        self.assertIsNot(type(value), I.Admission)
        record = I.parse(value.record, I.EVENT_LIMIT)
        self.assertEqual(record["policy"]["origin"], "reviewed-head")
        self.assertEqual(record["policy"]["commit"], F.F.H1)
        self.assertEqual(record["initialRecipient"], I.parse(original._match.record, I.EVENT_LIMIT))
        self.assertEqual(record["github"]["eventBinding"]["originalMain"], N.acquisition.stages.BASE["commit"])
        self.assertNotIn("policyMain", record["github"]["eventBinding"])
        self.assertEqual((self.path / "worker-identity.json").read_bytes(), value.record)
        pending = I.parse(original.raw, I.EVENT_LIMIT)
        self.assertEqual(pending["workerIdentitySha256"], O.digest(value.record))
        self.assertEqual(pending["workerAdmission"], "NOT_PERFORMED")
        self.assertEqual(value.original_policy, F.F.POLICY)
        self.assertEqual(len(self.fixture.requests), 8)

    def test_original_gate_return_cannot_mint_worker_identity(self):
        original = N._prepare_originals(self.cancelled)
        self.assertIsNone(original.identity)
        self.assertFalse((self.path / "worker-identity.json").exists())
        self.assertIsNone(I.parse(original.raw, I.EVENT_LIMIT)["workerIdentitySha256"])
        with self.assertRaisesRegex(I.AdmissionError, "WORKER_IDENTITY_ONLY"):
            N.original_worker_identity(original)

    def test_worker_retains_jobs_start_basis_and_fixed_proposal_not_admission(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        pending = I.parse(original.raw, I.EVENT_LIMIT)
        self.assertIn("serviceTimeBasisSha256", pending)
        basis_raw, proposal_raw = N.original_worker_time_records(original)
        basis, proposal = O.parse(basis_raw), O.parse(proposal_raw)
        job = O.parse((self.path / "acquisition-queries/jobs.bin").read_bytes())
        last = O.parse((self.path / "acquisition-queries/reviewed_ref.bin").read_bytes())
        self.assertEqual((self.path / "worker-service-time.json").read_bytes(), basis_raw)
        self.assertEqual((self.path / "worker-allocation-proposal.json").read_bytes(), proposal_raw)
        self.assertEqual(pending["serviceTimeBasisSha256"], O.digest(basis_raw))
        self.assertEqual(pending["allocationProposalSha256"], O.digest(proposal_raw))
        self.assertEqual(basis["scope"], N.TIME_SCOPE)
        self.assertEqual(proposal["scope"], N.ALLOCATION_SCOPE)
        self.assertEqual(basis["jobsRequestStartedNs"], job["startedNs"])
        self.assertEqual(basis["jobStartedEpochSeconds"], F.F.START)
        self.assertEqual(basis["serviceAgeSeconds"], 10)
        self.assertEqual(basis["chargedAgeNs"], 76 * O.NS)
        self.assertEqual(basis["jobStartBasisNs"], job["startedNs"] - 76 * O.NS)
        self.assertEqual(basis["service"]["lastNs"], last["finishedNs"])
        self.assertEqual(set(basis["service"]["originalsSha256"]), set(N.HTTP_KEYS))
        self.assertEqual(proposal["proposedJobEndNs"], basis["jobStartBasisNs"] + 5400 * O.NS)
        self.assertEqual(proposal["allocationStartBasisNs"], proposal["proposedJobEndNs"] - 4650 * O.NS)
        self.assertEqual(len(proposal["phaseFencesNs"]), 48)
        self.assertEqual(proposal["serviceTimeBasis"], basis)
        self.assertEqual(proposal["serviceTimeBasisSha256"], O.digest(basis_raw))
        identity = I.parse(original.identity.record, I.EVENT_LIMIT)
        for value in (basis, proposal):
            self.assertEqual(value["workerIdentitySha256"], O.digest(original.identity.record))
            self.assertEqual(value["firstUseAt"], F.F.FIRST1)
            self.assertEqual(value["source"], identity["source"])
            self.assertEqual(value["github"], identity["github"])
            self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
            self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
            self.assertIs(value["exportSaveAuthority"], False)
            self.assertNotIn("admissionSha256", value)
        self.assertEqual(proposal["productiveOwner"], "NOT_CREATED")
        self.assertEqual(len(self.fixture.requests), 8)

    def test_gate_never_produces_a_worker_service_basis_or_proposal(self):
        original = N._prepare_originals(self.cancelled)
        pending = I.parse(original.raw, I.EVENT_LIMIT)
        self.assertIsNone(pending["serviceTimeBasisSha256"])
        self.assertIsNone(pending["allocationProposalSha256"])
        self.assertIsNone(original.service_time_raw)
        self.assertIsNone(original.proposal_raw)
        self.assertFalse((self.path / "worker-service-time.json").exists())
        self.assertFalse((self.path / "worker-allocation-proposal.json").exists())
        with self.assertRaisesRegex(I.AdmissionError, "WORKER_IDENTITY_ONLY"):
            N.original_worker_time_records(original)

    def test_jobs_finish_and_later_response_date_never_replace_original_jobs_anchor(self):
        self.choose("worker", "desktop-linux-x64")
        self.fixture.after_close = lambda: setattr(self.fixture, "ns", self.fixture.ns + O.NS)
        def later_date():
            if len(self.fixture.requests) > 2:
                self.fixture.service_date = F.F.FIRST1 + 10
        self.fixture.before_request = later_date
        original = N._prepare_originals(self.cancelled)
        basis = O.parse(N.original_worker_time_records(original)[0])
        job = O.parse((self.path / "acquisition-queries/jobs.bin").read_bytes())
        last = O.parse((self.path / "acquisition-queries/reviewed_ref.bin").read_bytes())
        self.assertGreaterEqual(job["finishedNs"] - job["startedNs"], O.NS)
        self.assertGreater(last["finishedNs"], job["finishedNs"])
        self.assertEqual(basis["service"]["lastNs"], last["finishedNs"])
        self.assertEqual(basis["service"]["originDateEpochSeconds"], F.F.FIRST1)
        self.assertEqual(basis["jobStartBasisNs"], job["startedNs"] - 76 * O.NS)
        self.assertNotEqual(basis["jobStartBasisNs"], job["finishedNs"] - 76 * O.NS)

    def test_coherently_rehashed_worker_proposal_cannot_replace_original_return(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        basis_raw, proposal_raw = N.original_worker_time_records(original)
        basis, proposal = O.parse(basis_raw), O.parse(proposal_raw)
        basis["jobStartBasisNs"] += O.NS
        changed_basis = O.encoded(basis)
        proposal.update(serviceTimeBasis=basis, serviceTimeBasisSha256=O.digest(changed_basis),
                        **S.allocation.fence_arithmetic(basis["jobStartBasisNs"]))
        changed_proposal = O.encoded(proposal)
        pending = O.parse(original.raw)
        pending.update(serviceTimeBasisSha256=O.digest(changed_basis), allocationProposalSha256=O.digest(changed_proposal))
        object.__setattr__(original, "service_time_raw", changed_basis)
        object.__setattr__(original, "proposal_raw", changed_proposal)
        object.__setattr__(original, "raw", O.encoded(pending))
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_BINDING_CHANGED"):
            N.original_worker_time_records(original)
        bound = N._PREPARED_RETURNS[id(original)]
        self.assertEqual((bound.service_time_raw, bound.proposal_raw), (basis_raw, proposal_raw))

    def test_changed_proposal_or_equality_overriding_bytes_refuse_original_accessor(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        class EqualBytes(bytes):
            def __eq__(self, other): return True
        for name in ("service_time_raw", "proposal_raw"):
            before = getattr(original, name)
            for value in (before + b"\n", bytearray(before), memoryview(before), EqualBytes(before)):
                with self.subTest(field=name, kind=type(value).__name__):
                    object.__setattr__(original, name, value)
                    with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_TIME_BINDING_CHANGED"):
                        N.original_worker_time_records(original)
            object.__setattr__(original, name, before)
        self.assertEqual(N.original_worker_time_records(original), (original.service_time_raw, original.proposal_raw))

    def test_worker_time_originals_are_immutable_complete_and_distinct_from_summary(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        captured = N._PREPARED_RETURNS[id(original)].worker_originals
        self.assertIs(type(captured), tuple)
        self.assertEqual(tuple(name for name, _ in captured[1]), N.ORIGINAL_KEYS)
        for rows in (captured[1][:-1], tuple(reversed(captured[1])), list(captured[1]),
                     tuple((name, bytearray(raw)) for name, raw in captured[1])):
            with self.subTest(kind=type(rows).__name__), self.assertRaisesRegex(I.AdmissionError, "WORKER_TIME_ORIGINALS"):
                N._worker_time_records(original.identity, (captured[0], rows, *captured[2:]), original._fence.clock)
        self.assertEqual(N.original_worker_time_records(original), (original.service_time_raw, original.proposal_raw))

    def test_original_http_failure_clock_invocation_and_order_cannot_supply_basis(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        captured = N._PREPARED_RETURNS[id(original)].worker_originals
        for name, mutate in (("jobs", lambda x: x.update(retirement="UNKNOWN")),
                             ("jobs", lambda x: x.update(complete=False)),
                             ("jobs", lambda x: x.update(invocation="f" * 32)),
                             ("jobs", lambda x: x["clock"].update(role="windows-x64")),
                             ("reviewed_ref", lambda x: x.update(startedNs=1))):
            rows = dict(captured[1]); value = O.parse(rows[name]); mutate(value); rows[name] = O.encoded(value)
            changed = (captured[0], tuple((key, rows[key]) for key in N.ORIGINAL_KEYS), *captured[2:])
            with self.subTest(name=name), self.assertRaises((I.AdmissionError, O.OriginError, O.wire.BudgetError,
                                                          O.clocks.ClockError)):
                N._worker_time_records(original.identity, changed, original._fence.clock)

    def test_original_worker_proposal_accessor_does_not_reacquire_or_renew_time(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        expected = N.original_worker_time_records(original)
        self.fixture.ns += 10 * O.NS
        self.assertEqual(N.original_worker_time_records(original), expected)
        self.assertEqual(len(self.fixture.requests), 8)
        self.fixture.ns = 1120 * O.NS
        with self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"):
            N.original_worker_time_records(original)
        self.assertEqual(len(self.fixture.requests), 8)

    def test_worker_proposal_failure_is_primary_and_registers_no_original_return(self):
        self.choose("worker", "desktop-linux-x64")
        failure = RuntimeError("SYNTHETIC_TIME_BASIS_FAILURE")
        with patch.object(S.service_time, "basis_arithmetic", side_effect=failure), self.assertRaises(RuntimeError) as raised:
            N._prepare_originals(self.cancelled)
        self.assertIs(raised.exception, failure)
        self.assertEqual(N._PREPARED_RETURNS, {})
        self.assertFalse((self.path / "initial-result.json").exists())
        self.assertTrue((self.path / "initial-failure.json").exists())

    def test_worker_proposals_do_not_survive_late_original_owner_close(self):
        self.choose("worker", "desktop-linux-x64")
        close = S.Owner.close
        def late(owner):
            close(owner)
            if hasattr(owner, "initial_sources"):
                self.fixture.ns = 1120 * O.NS
        with patch.object(S.Owner, "close", late), self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"):
            N._prepare_originals(self.cancelled)
        self.assertTrue((self.path / "worker-allocation-proposal.json").exists())
        self.assertEqual(N._PREPARED_RETURNS, {})

    def test_worker_unknown_owner_close_keeps_pending_proposal_non_authorizing(self):
        self.choose("worker", "desktop-linux-x64")
        close = S.Owner.close
        failure = O.OriginError("SYNTHETIC_UNKNOWN_OWNER_CLOSE")
        def unknown(owner):
            close(owner)
            if hasattr(owner, "initial_sources"):
                owner.error("synthetic-close", failure, unknown=True)
                raise failure
        with patch.object(S.Owner, "close", unknown), self.assertRaises(O.OriginError) as raised:
            N._prepare_originals(self.cancelled)
        self.assertIs(raised.exception, failure)
        self.assertTrue((self.path / "worker-allocation-proposal.json").exists())
        self.assertEqual(N._PREPARED_RETURNS, {})

    def test_stage1_service_records_cannot_enter_legacy_admission_wrappers(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        captured = N._PREPARED_RETURNS[id(original)].worker_originals
        rows = dict(captured[1]); pair = {name: rows[name] for name in ("attempt", "jobs")}
        for operation in (S.service_time.derive, S.allocation.derive):
            with self.subTest(operation=operation.__name__), self.assertRaisesRegex(O.OriginError, "ORIGINAL_ADMISSION"):
                operation(original.identity, pair, captured[2], original._fence.clock, self.fixture.env["RUNNER_NAME"])
        with self.assertRaises(O.wire.BudgetError):
            O.wire.Budget(original.proposal_raw).value

    def test_final_raw_observation_cannot_return_changed_time_records(self):
        self.final_record_change("raw", identity=False)

    def test_final_local_check_cannot_return_changed_time_records(self):
        self.final_record_change("local", identity=False)

    def test_final_cancellation_check_cannot_return_changed_time_records(self):
        self.final_record_change("cancel", identity=False)

    def test_final_raw_observation_cannot_return_changed_identity(self):
        self.final_record_change("raw", identity=True)

    def test_final_local_check_cannot_return_changed_identity(self):
        self.final_record_change("local", identity=True)

    def test_final_cancellation_check_cannot_return_changed_identity(self):
        self.final_record_change("cancel", identity=True)

    def test_final_local_boundary_cannot_replace_the_original_owner(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        self.late_return_change("local", lambda: object.__setattr__(original, "_owner", copy.copy(original._owner)),
                                lambda: N.original_worker_identity(original))

    def test_final_local_boundary_cannot_extend_the_original_local_end(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        self.late_return_change("local", lambda: setattr(original._owner, "local_end", original._owner.local_end + 1),
                                lambda: N.original_worker_identity(original))

    def test_final_cancellation_boundary_cannot_replace_original_cancellation(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        self.late_return_change("cancel", lambda: object.__setattr__(original, "_cancelled", []),
                                lambda: N.original_worker_identity(original))

    def test_final_local_boundary_cannot_replace_validated_raw_highwater(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        self.late_return_change("local", lambda: setattr(original._fence, "last", original._fence.last + 1),
                                lambda: N.original_worker_identity(original))

    def test_time_accessor_returns_saved_tuple_not_reloaded_return_fields(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        binding = N._PREPARED_RETURNS[id(original)]
        expected = binding.service_time_raw, binding.proposal_raw
        identity = N.original_worker_identity
        def completed_check(value):
            result = identity(value)
            # A caller-boundary model: the genuine check has completed, but a
            # later data-field change must not select different returned bytes.
            object.__setattr__(original, "service_time_raw", b"SYNTHETIC_LATE_BASIS\n")
            object.__setattr__(original, "proposal_raw", b"SYNTHETIC_LATE_PROPOSAL\n")
            return result
        with patch.object(N, "original_worker_identity", side_effect=completed_check):
            self.assertEqual(N.original_worker_time_records(original), expected)
        self.assertEqual(len(self.fixture.requests), 8)

    def test_copied_preparation_with_same_closed_owner_does_not_register_return(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_PREPARATION_RETURN"):
            N.original_worker_identity(dataclasses.replace(original))
        self.assertIs(N.original_worker_identity(original), original.identity)

    def test_worker_match_cannot_be_replaced_with_gate_return_before_identity_binding(self):
        self.choose("worker", "desktop-linux-x64")
        read = N.read_phase
        def replace(*args):
            result, chain, captured = read(*args)
            return N.acquisition.gate.GateEligibility(result.record), chain, captured
        with patch.object(N, "read_phase", replace), self.assertRaisesRegex(I.AdmissionError, "WORKER_MATCH_ONLY"):
            N._prepare_originals(self.cancelled)
        self.assertFalse((self.path / "worker-identity.json").exists())
        self.assertEqual(N._PREPARED_RETURNS, {})

    def test_worker_identity_expiring_during_actual_owner_close_is_not_registered(self):
        self.choose("worker", "desktop-linux-x64")
        close = S.Owner.close
        def expire(owner):
            close(owner)
            if hasattr(owner, "initial_sources"):
                self.stack.enter_context(patch.object(N.time, "time", return_value=self.fixture.declaration["expiresAt"]))
        with patch.object(S.Owner, "close", expire), self.assertRaisesRegex(I.AdmissionError, "CURRENT_WINDOW"):
            N._prepare_originals(self.cancelled)
        self.assertTrue((self.path / "worker-identity.json").exists())
        self.assertEqual(N._PREPARED_RETURNS, {})

    def test_worker_identity_accessor_does_not_renew_exception_or_query_authority(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        with patch.object(N.time, "time", return_value=self.fixture.declaration["expiresAt"]), \
                self.assertRaisesRegex(I.AdmissionError, "CURRENT_WINDOW"):
            N.original_worker_identity(original)
        self.assertEqual(len(self.fixture.requests), 8)
        self.assertEqual(len(self.queries), 3)

    def test_worker_identity_accessor_cannot_start_a_new_prelude(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        self.fixture.ns = original._fence.final
        with self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"):
            N.original_worker_identity(original)
        self.assertEqual(len(self.fixture.requests), 8)

    def test_cancelled_original_return_cannot_be_used_as_worker_identity(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        self.cancelled.append(True)
        with self.assertRaises(KeyboardInterrupt): N.original_worker_identity(original)

    def test_mutated_identity_equality_object_cannot_override_original_binding(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        class EqualBytes(bytes):
            def __eq__(self, other): return True
        object.__setattr__(original.identity, "record", EqualBytes(b"invented"))
        with self.assertRaisesRegex(I.AdmissionError, "WORKER_IDENTITY_TYPES"):
            N.original_worker_identity(original)

    def test_coherent_worker_authority_and_identity_change_cannot_replace_originals(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        pending = I.parse(original.raw, I.EVENT_LIMIT)
        value = I.parse(original._match.record, I.EVENT_LIMIT)
        value["authority"]["bodySha256"] = "d" * 64
        changed_match = N.acquisition.stages.BootstrapMatch(I.encoded(value))
        changed_identity = N.initial_identity.bind_worker_match(changed_match,
            event_raw=original.identity.original_event, policy_raw=original.identity.original_policy,
            now=F.F.FIRST1)
        self.assertNotEqual(pending["matchSha256"], O.digest(changed_match.record))
        self.assertNotEqual(pending["workerIdentitySha256"], O.digest(changed_identity.record))
        object.__setattr__(original, "_match", changed_match)
        object.__setattr__(original, "identity", changed_identity)
        with self.assertRaises(I.AdmissionError): N.original_worker_identity(original)

    def test_worker_return_keeps_original_prelude_and_local_ceiling(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        old_final = original._fence.final
        original._fence.final += 120 * O.NS
        original._owner.local_end += 120
        self.fixture.ns = old_final + O.NS
        self.assertEqual(O.parse(original._fence.raw)["finalEndNs"], old_final)
        with self.assertRaises((I.AdmissionError, O.OriginError)):
            N.original_worker_identity(original)

    def test_replaced_cancellation_reference_cannot_hide_original_cancel(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        self.cancelled.append(15)
        object.__setattr__(original, "_cancelled", [])
        with self.assertRaises((I.AdmissionError, KeyboardInterrupt)):
            N.original_worker_identity(original)

    def test_coherent_in_place_match_identity_and_pending_edits_do_not_change_registration(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        value = I.parse(original._match.record, I.EVENT_LIMIT)
        value["authority"]["bodySha256"] = "d" * 64
        object.__setattr__(original._match, "record", I.encoded(value))
        changed = N.initial_identity.bind_worker_match(original._match,
            event_raw=original.identity.original_event, policy_raw=original.identity.original_policy, now=F.F.FIRST1)
        for field in dataclasses.fields(changed):
            object.__setattr__(original.identity, field.name, getattr(changed, field.name))
        pending = I.parse(original.raw, I.EVENT_LIMIT)
        pending.update(matchSha256=O.digest(original._match.record), workerIdentitySha256=O.digest(original.identity.record))
        object.__setattr__(original, "raw", I.encoded(pending))
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_BINDING_CHANGED"):
            N.original_worker_identity(original)

    def test_equal_copied_worker_identity_or_match_does_not_replace_original_reference(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        for name in ("identity", "_match"):
            kept = getattr(original, name)
            object.__setattr__(original, name, dataclasses.replace(kept))
            with self.subTest(field=name), self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_BINDING_CHANGED"):
                N.original_worker_identity(original)
            object.__setattr__(original, name, kept)
        self.assertIs(N.original_worker_identity(original), original.identity)

    def test_coherently_copied_closed_owner_and_fence_do_not_rebind_original_return(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        owner, fence = copy.copy(original._owner), copy.copy(original._fence)
        owner.fence = fence
        object.__setattr__(original, "_owner", owner)
        object.__setattr__(original, "_fence", fence)
        with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_PREPARATION_RETURN"):
            N.original_worker_identity(original)

    def test_coherent_prelude_raw_and_fields_cannot_reissue_original_time(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        fence = original._fence
        shifted = O.prelude(O.clocks.Reading(fence.clock, fence.first + 120 * O.NS))
        fence.raw = O.encoded(shifted)
        fence.first, fence.work, fence.final = (shifted[name] for name in ("firstNs", "workEndNs", "finalEndNs"))
        fence.last = fence.first
        original._owner.local_end += 120
        self.fixture.ns = fence.first + O.NS
        # Internally coherent current fields are insufficient without the saved original raw frame.
        S.history.snapshot(fence)
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_FENCE_CHANGED"):
            N.original_worker_identity(original)

    def test_local_ceiling_extension_refuses_even_before_original_expiry(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        original._owner.local_end += 1
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_FENCE_CHANGED"):
            N.original_worker_identity(original)

    def test_replaced_fence_cancellation_callback_is_not_original_binding(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        original._fence.cancelled = lambda: None
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_FENCE_CHANGED"):
            N.original_worker_identity(original)

    def test_successful_accessor_highwater_cannot_be_erased_by_fence_field_mutation(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        first = original._fence.last
        self.fixture.ns += O.NS
        self.assertIs(N.original_worker_identity(original), original.identity)
        original._fence.last = first
        self.fixture.ns = first
        with self.assertRaisesRegex(O.OriginError, "ORIGIN_INTEGER"):
            N.original_worker_identity(original)

    def test_expired_accessor_highwater_cannot_be_erased_by_fence_field_mutation(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        first = original._fence.last
        self.fixture.ns = original._fence.final
        with self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"):
            N.original_worker_identity(original)
        original._fence.last = first
        self.fixture.ns = first
        with self.assertRaisesRegex(O.OriginError, "ORIGIN_INTEGER"):
            N.original_worker_identity(original)

    def test_original_limits_are_pinned_before_actual_owner_close_not_at_registration(self):
        self.choose("worker", "desktop-linux-x64")
        close = S.Owner.close
        def extend(owner):
            close(owner)
            if hasattr(owner, "initial_sources"):
                owner.local_end += 1
        with patch.object(S.Owner, "close", extend), self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_FENCE_CHANGED"):
            N._prepare_originals(self.cancelled)
        self.assertEqual(N._PREPARED_RETURNS, {})

    def test_same_episode_cannot_retry_or_renew_acquisition(self):
        self.prepare()
        with self.assertRaises(Exception): self.prepare()
        self.assertEqual(len(self.scopes), 1)
        self.assertEqual(len(self.fixture.requests), 8)

    def test_non_hosted_context_refuses_before_private_allocation(self):
        os.environ["GITHUB_ACTIONS"] = "false"
        with self.assertRaisesRegex(I.AdmissionError, "HOSTED_CONTEXT"): self.prepare()
        self.assertFalse(self.path.exists())
        self.assertEqual(self.queries, [])

    def test_ambient_loader_override_refuses_before_queries(self):
        os.environ["LD_PRELOAD"] = "SYNTHETIC_INVALID_OVERRIDE"
        with self.assertRaisesRegex(O.OriginError, "AMBIENT_EXECUTION_OVERRIDE"): self.prepare()
        self.assertFalse(self.path.exists())

    def test_wrong_native_clock_role_refuses_even_with_plausible_actions_labels(self):
        self.fixture.clock = O.clocks.ClockIdentity("macos-arm64", O.clocks.DOMAINS["macos-arm64"], O.NS)
        with self.assertRaisesRegex(I.AdmissionError, "ACTUAL_NATIVE_ROLE"): self.prepare()
        self.assertFalse(self.path.exists())

    def test_source_failure_finalizes_query_once_without_starting_http_child(self):
        self.fixture.git.clean_value = False
        with self.assertRaisesRegex(I.AdmissionError, "SOURCE"): self.prepare()
        self.assertEqual(len(self.queries), 1)
        self.assertEqual(self.queries[0].finalizations, 1)
        self.assertEqual(self.scopes, [])
        self.assertEqual(self.fixture.requests, [])

    def test_query_success_receipt_cannot_replace_failed_actual_close(self):
        failure = RuntimeError("SYNTHETIC_QUERY_CLOSE")
        self.query_close_error = failure
        with self.assertRaises(RuntimeError) as caught: self.prepare()
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.scopes, [])
        self.assertEqual(self.queries[0].finalizations, 1)

    def test_primary_query_cancellation_survives_secondary_finalizer_error(self):
        primary = KeyboardInterrupt("SYNTHETIC_QUERY_CANCEL")
        self.fixture.git.failure = primary
        self.query_close_error = RuntimeError("SYNTHETIC_SECONDARY_CLOSE")
        with self.assertRaises(KeyboardInterrupt) as caught: self.prepare()
        self.assertIs(caught.exception, primary)
        self.assertEqual(self.queries[0].finalizations, 1)

    def test_child_nonzero_refuses_even_with_complete_original_success_ack(self):
        self.child_exit = 125
        with self.assertRaisesRegex(O.OriginError, "SERVICE_CHILD_FAILED"): self.prepare()
        self.assertTrue(self.scopes[0].closed)
        self.assertEqual(len(self.queries), 2)

    def test_child_current_gate_predecessor_failure_prevents_worker_return(self):
        self.choose("worker", "desktop-linux-x64")
        self.fixture.bodies["jobs"]["jobs"][1]["conclusion"] = "failure"
        with self.assertRaisesRegex(O.OriginError, "SERVICE_CHILD_FAILED"): self.prepare()
        self.assertIn("GATE_PREDECESSOR", str(self.child_errors[0]))
        self.assertEqual(len(self.fixture.requests), 2)

    def test_http_failure_preserves_original_bytes_in_private_query_custody(self):
        self.fixture.request_error = KeyboardInterrupt("SYNTHETIC_HTTP_CANCEL")
        with self.assertRaisesRegex(O.OriginError, "SERVICE_CHILD_FAILED"): self.prepare()
        self.assertIs(self.child_errors[0], self.fixture.request_error)
        response = json.loads((self.path / "acquisition-queries/attempt.bin").read_bytes())
        self.assertFalse(response["complete"])
        self.assertEqual(len(self.fixture.requests), 1)

    def test_complete_returned_http_response_is_retained_at_pre_retainer_cancellation(self):
        original = N.acquisition.origin._request
        def request(*args):
            result = original(*args)
            args[3].cancelled = lambda: (_ for _ in ()).throw(KeyboardInterrupt("SYNTHETIC_AFTER_HTTP"))
            return result
        with patch.object(N.acquisition.origin, "_request", request), self.assertRaises(O.OriginError): self.prepare()
        response = json.loads((self.path / "acquisition-queries/attempt.bin").read_bytes())
        self.assertTrue(response["complete"])
        self.assertEqual(response["retirement"], "KNOWN")
        self.assertEqual(len(self.fixture.requests), 1)

    def test_failed_child_query_finalizer_cannot_emit_success_ack(self):
        def inject(path):
            if path.name == "acquisition-queries": self.query_close_error = RuntimeError("SYNTHETIC_CHILD_QUERY_CLOSE")
        self.before_query = inject
        with self.assertRaisesRegex(O.OriginError, "SERVICE_CHILD_FAILED"): self.prepare()
        self.assertIn("SYNTHETIC_CHILD_QUERY_CLOSE", str(self.child_errors[0]))
        self.assertFalse((self.path / "service/child-result.json").exists())

    def test_unknown_scope_close_prevents_capture_adoption(self):
        self.scope_close_error = RuntimeError("SYNTHETIC_SCOPE_CLOSE")
        with self.assertRaises(Exception): self.prepare()
        self.assertEqual(self.scopes[0].close_calls, 1)
        self.assertEqual(len(self.queries), 2)
        self.assertTrue(S.QUARANTINE)

    def test_surviving_native_domain_refuses_and_never_constructs_source_after(self):
        self.scope_survivors = ["SYNTHETIC_SURVIVOR"]
        with self.assertRaisesRegex(O.OriginError, "SERVICE_SURVIVORS"): self.prepare()
        self.assertEqual(len(self.queries), 2)
        self.assertEqual(self.scopes[0].close_calls, 1)

    def test_late_native_return_fails_without_new_drain_budget(self):
        self.after_child = lambda: setattr(self.fixture, "ns", 1080 * O.NS)
        with self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"): self.prepare()
        self.assertEqual(self.scopes[0].close_calls, 1)
        self.assertEqual(len(self.queries), 2)

    def test_post_drain_expiry_cannot_accept_retirement(self):
        self.after_drain = lambda: setattr(self.fixture, "ns", 1121 * O.NS)
        with self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"): self.prepare()
        self.assertTrue(S.QUARANTINE)

    def test_cancelled_parent_keeps_original_cancellation_after_successful_child(self):
        self.after_child = lambda: self.cancelled.append(15)
        with self.assertRaises(KeyboardInterrupt): self.prepare()
        self.assertEqual(self.scopes[0].close_calls, 1)
        self.assertEqual(len(self.queries), 2)

    def test_original_ack_scope_cannot_be_substituted_by_old_bootstrap_ack(self):
        def change(raw):
            value = json.loads(raw); value["scope"] = S.ACK_SCOPE
            return O.encoded(value)
        self.ack_transform = change
        with self.assertRaisesRegex(I.AdmissionError, "CHILD_ACK"): self.prepare()

    def test_ack_duplicate_member_or_trailing_json_cannot_be_normalized(self):
        self.ack_transform = lambda raw: raw.rstrip() + b'\n{}\n'
        with self.assertRaises(Exception): self.prepare()
        self.assertEqual(len(self.queries), 2)

    def test_child_success_record_replacement_does_not_match_original_ack(self):
        self.after_child = lambda: self.changed_json(self.path / "service/child-result.json", lambda x: x.update(matchSha256="0" * 64))
        with self.assertRaisesRegex(I.AdmissionError, "CHILD_ACK"): self.prepare()

    def test_retained_http_original_replacement_refuses_even_with_genuine_child_exit(self):
        self.after_child = lambda: (self.path / "acquisition-queries/comment.bin").write_bytes(b"{}")
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_BYTES_CHANGED"): self.prepare()

    def test_source_after_child_is_actual_fresh_query_not_an_old_success_label(self):
        def change(path):
            if path.name == "source-after": self.fixture.git.clean_value = False
        self.before_query = change
        with self.assertRaisesRegex(I.AdmissionError, "SOURCE"): self.prepare()
        self.assertEqual(len(self.queries), 3)
        self.assertEqual(self.queries[-1].finalizations, 1)

    def test_source_return_replacement_refuses_before_adopting_child_data(self):
        self.after_child = lambda: (self.path / "source-before/source-return.json").write_bytes(b"{}")
        with self.assertRaisesRegex(I.AdmissionError, "SOURCE_RETURN_CHANGED"): self.prepare()

    def test_final_query_return_cannot_cross_original_prelude_work_cutoff(self):
        def advance(path):
            if path.name == "source-after": self.fixture.ns = 1075 * O.NS
        self.after_query_close = advance
        with self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"): self.prepare()
        self.assertFalse((self.path / "initial-result.json").exists())

    def test_context_change_at_final_recheck_is_not_hidden_by_unchanged_match(self):
        def change(path):
            if path.name == "source-after": os.environ["GITHUB_SHA"] = F.F.H2
        self.after_query_close = change
        with self.assertRaisesRegex(I.AdmissionError, "WORKFLOW|EXPECTED_SOURCE"): self.prepare()

    def test_copied_phase_cannot_register_actual_native_return(self):
        original = S.phase
        def copied(*args):
            directory, phase = original(*args)
            return directory, S.OriginalPhase(phase.context, phase.records)
        with patch.object(S, "phase", copied), self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_PHASE_RETURN"):
            self.prepare()

    def test_copied_source_return_cannot_register_native_query_completion(self):
        original = N.source_queries
        def copied(*args):
            value = original(*args)
            return N.SourceReturn(value.records, value.session, value.raw)
        with patch.object(N, "source_queries", copied), self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_SOURCE_RETURN"):
            self.prepare()

    def test_closed_phase_route_preserves_old_command_and_rejects_arbitrary_scope(self):
        for scope, command in ((S.CONTEXT_SCOPE, S.command), (S.INITIAL_CONTEXT_SCOPE, S.initial_command)):
            raw = O.encoded({"scope": scope})
            self.assertEqual(S.phase_command(raw, 1), command(O.digest(raw), 1))
        with self.assertRaisesRegex(O.OriginError, "SERVICE_CONTEXT_SCOPE"):
            S.phase_command(O.encoded({"scope": "SYNTHETIC_OTHER", "argv": ["forbidden"]}))

    def test_final_parent_owner_close_is_postchecked_against_original_end(self):
        original = S.Owner.close
        def late(owner):
            original(owner)
            if hasattr(owner, "initial_sources"):
                self.fixture.ns = 1120 * O.NS
        with patch.object(S.Owner, "close", late), self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"):
            self.prepare()
        self.assertTrue((self.path / "initial-result.json").exists())

    def test_initial_ack_gets_final_guarded_highwater_not_child_provisional_time(self):
        value, _, _ = self.prepare()
        row = json.loads((self.path / "service/child-result.json").read_bytes())
        ack = json.loads((self.path / "service/stdout.log").read_bytes())
        self.assertGreater(ack["closedNs"], row["completedNs"])
        self.assertEqual(ack["scope"], S.INITIAL_ACK_SCOPE)
        self.assertEqual(value["scope"], N.OUTPUT_SCOPE)

    def test_context_extra_field_is_not_an_open_command_descriptor(self):
        self.before_child = lambda: self.changed_json(self.path / "context.json", lambda x: x.update(argv=["not-allowed"]))
        with self.assertRaisesRegex(O.OriginError, "SERVICE_CHILD_FAILED"): self.prepare()
        self.assertIn("CHILD_CONTEXT_CHANGED", str(self.child_errors[0]))
        self.assertEqual(len(self.fixture.requests), 0)

    def test_changed_real_event_is_not_replaced_by_saved_context(self):
        self.before_child = lambda: self.event.write_bytes(b"{}")
        with self.assertRaisesRegex(O.OriginError, "SERVICE_CHILD_FAILED"): self.prepare()
        self.assertEqual(len(self.fixture.requests), 0)

    def test_replaced_candidate_policy_remains_rejected_before_http(self):
        self.fixture.git.policy_raw += b"\n"
        with self.assertRaisesRegex(I.AdmissionError, "POLICY_BLOB"): self.prepare()
        self.assertEqual(self.fixture.requests, [])

    def test_retained_match_recheck_still_validates_live_policy_window(self):
        self.after_child = lambda: self.stack.enter_context(patch.object(N.time, "time", return_value=F.F.END))
        with self.assertRaises(I.AdmissionError): self.prepare()
        self.assertEqual(len(self.fixture.requests), 8)

    def test_required_read_token_never_falls_back_to_ambient_github_token(self):
        os.environ.pop(O.wire.TOKEN_ENV)
        with self.assertRaisesRegex(O.OriginError, "ACTIONS_READ_TOKEN"): self.prepare()
        self.assertEqual(len(self.fixture.requests), 0)


if __name__ == "__main__":
    unittest.main()
