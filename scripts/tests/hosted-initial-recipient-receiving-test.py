#!/usr/bin/env python3
"""Focused receiving seam models; no complete-reader rerun or initialization.

The accepted full graph reader is replaced by an explicitly supplied immutable
model. No synthetic1066-file fixture is created. The enter-only compatibility
model supplies exact in-memory row/directory shapes, not authenticated history.
Its222 original directory handles plus session/Step handles need more than a
nofile128 launcher; all remain bounded fixture resources, not new production caps.
Only the NEW receiving owner,
fixed acquisition/child/readback/close composition and tiny private POSIX files
execute. Git, HTTP transport, native processes/clocks and predecessor transport
remain models. No canonical initializer/provider/build or hosted result exists.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("receiving_native_models",
    Path(__file__).with_name("hosted-initial-recipient-native-test.py"))
F = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = F
spec.loader.exec_module(F)  # Existing guard is installed BEFORE any project import.
N, S, O, I, Q = F.N, F.S, F.O, F.I, F.Q
SEAM_REQUEST = S.canonical.init_request


class FirstFailure(RuntimeError):
    def __bool__(self):
        return False


class ReceivingControls(unittest.TestCase):
    """Composition, not inheritance: selecting this class runs only its methods."""

    def setUp(self):
        self.fx = F.NativeModels("runTest")
        self.addCleanup(self.fx.doCleanups)
        self.fx.setUp()
        self.addCleanup(self.cleanup_receiving_models)
        self.fx.choose("worker", "desktop-linux-x64")
        self.clock = self.fx.fixture.clock
        self.read_calls, self.continuations, self.child_envs = [], [], []
        self.reader_delay = 25 * O.NS
        self.reader_error = None
        self.make_graph_model()
        self.fx.stack.enter_context(patch.object(N, "_read_initial_recipient_originals", side_effect=self.read_graph_model))
        self.fx.stack.enter_context(patch.object(S.processes, "make_scope", side_effect=self.make_receiving_scope))
        self.fx.stack.enter_context(patch.object(S, "initialize_after_entry",
            side_effect=AssertionError("LEGACY_INITIALIZER_MUST_NOT_RUN")))
        self.fx.stack.enter_context(patch.object(S.canonical, "init_request",
            side_effect=AssertionError("CANONICAL_INITIALIZER_IS_NOT_CONNECTED")))

    def cleanup_receiving_models(self):
        # Only tiny fixture files and fake native domains exist. This is NOT a
        # production recovery path for UNKNOWN ownership or failed retirement.
        for state in (*N._RECEIVING_WINDOWS.values(), *N._AUTHORITY_WINDOWS.values()):
            roster = state.roster
            if roster is not None:
                for row, label, resource, _a, _c in reversed(roster.seen):
                    if label != "native-scope" and not row.get("closed"):
                        resource.close()
                        row["attempted"] = row["closed"] = True
        for registry in (N._RECEIVING_WINDOWS, N._RECEIVING_CONTINUATIONS, N._AUTHORITY_WINDOWS, N._AUTHORITY_RETURNS):
            registry.clear()
        if hasattr(self, "_seam_roots"):
            for registry in (N._WORKER_READER_CAPTURES, N._WORKER_AUTHORITY_CAPTURES, N._WORKER_AUTHORITY_RETURNS):
                registry.clear()  # Only these enter-local fake-domain captures.

    def make_graph_model(self):
        fixture = self.fx.fixture
        began = fixture.ns
        match, originals = fixture.acquire()  # Existing modeled HTTP transport, not a native/reader invocation.
        records = dict(originals)
        context = O.encoded({"observed": fixture.context, "inheritedContext": Q._inherited_context()})
        captured = (context, tuple((name, records[name]) for name in N.ORIGINAL_KEYS), F.F.INVOCATION, began, began + 45 * O.NS)
        identity = N.initial_identity.bind_worker_match(match, event_raw=records["event"],
            policy_raw=records["candidate_policy_raw"], now=F.F.F.FIRST1)
        basis, proposal = N._worker_time_records(identity, captured, self.clock)
        sender = O.encoded({"readWindow": {"retainedNs": fixture.ns, "previousLocal": fixture.ns / O.NS}})
        rows = {"P/context.json": context, "S/sender-pending.json": sender, "P/worker-identity.json": identity.record,
            "P/worker-service-time.json": basis, "P/worker-allocation-proposal.json": proposal,
            "P/service/start.json": O.encoded({"invocation": F.F.INVOCATION,
                "startedNs": began, "workEndNs": began + 45 * O.NS})}
        rows.update(("P/acquisition-queries/" + name + ".bin", raw) for name, raw in records.items())
        # These padding entries are inert supplied data, NOT original files or
        # a replacement for any assertion in the accepted complete reader.
        while len(rows) < 1066:
            rows["MODEL_ONLY_UNUSED/" + str(len(rows))] = b"explicit-supplied-model\n"
        self.graph = tuple(rows.items())
        self.sender_hash = O.digest(sender)
        os.environ[N.RECEIVING_OUTCOME_ENV] = "success"
        os.environ[N.RECEIVING_HASH_ENV] = self.sender_hash
        path = N._recipient_path()
        target = path.with_name(path.name + "-output")
        directory = Q._new_private_directory(target)
        directory.close()
        fixture.requests.clear()
        fixture.retained.clear()

    def read_graph_model(self, owner, directory, *, recipient_outcome, expected_sha256):
        self.assertNotIn(O.wire.TOKEN_ENV, os.environ)
        self.assertEqual((recipient_outcome, expected_sha256), ("success", self.sender_hash))
        self.assertIs(type(owner), S.Owner)
        self.assertIs(type(owner.fence), N._ReceivingWindow)
        self.assertFalse(owner.closed)
        self.assertLessEqual(owner.fence.state().local_start, owner.first.nanoseconds / O.NS)
        self.assertEqual(owner.fence.work, owner.first.nanoseconds + 120 * O.NS)
        self.read_calls.append((owner, owner.fence, owner.first, directory))
        for name in getattr(self, "_seam_directories", ()):
            if name != "S":
                group, *parts = name.split("/")
                owner.open(self._seam_roots[group].joinpath(*parts))
        self.fx.fixture.ns += self.reader_delay
        if self.reader_error is not None:
            raise self.reader_error
        return self.graph

    def make_receiving_scope(self, job, invocation, state, home):
        case, fx = self, self.fx
        self.assertEqual(Path(state), N._receiving_path() / "authority")
        class Scope:
            name, baseline = "linux-proc-pidfd", set()
            def __init__(self):
                self.launches, self.closed, self.close_calls = [], False, 0
            def _identity(self, pid):
                return {"pid": pid, "startTicks": 9012, "live": True}
            def spawn(self, argv, cwd, env, *, stdout, stderr):
                case.assertEqual(argv[4:6], [str(F.ROOT / "scripts/run-hosted-initial-recipient.py"), "_service-receiving-authority"])
                case.assertEqual(env[O.wire.TOKEN_ENV], F.TOKEN)
                case.assertNotIn("GITHUB_TOKEN", env)
                case.assertNotIn(N.RECEIVING_HASH_ENV, env)
                case.child_envs.append(dict(env))
                self.launches = [{"api": "subprocess.Popen", "requestedArgv": argv, "resolvedArgv": argv,
                    "cwd": cwd, "shell": False, "created": True, "executable": argv[0], "pid": 1234,
                    "outputMode": "caller-owned-files"}]
                def write(raw):
                    return os.write(stdout.fileno(), raw)
                output = SimpleNamespace(buffer=SimpleNamespace(write=write, flush=stdout.sync))
                code = 0
                try:
                    with patch.dict(os.environ, env, clear=True), patch.object(S.sys, "stdout", output):
                        S.guarded(lambda cancelled: N.service_child(argv[-3], int(argv[-1]), cancelled,
                            authority=True, receiving=True))
                except BaseException as error:
                    fx.child_errors.append(error)
                    os.write(stderr.fileno(), b"SYNTHETIC_CHILD_FAILURE\n")
                    code = 125
                return SimpleNamespace(pid=1234, stdout=None, stderr=None, poll=lambda: code)
            def description(self):
                return {"backend": self.name, "scope": "controlled-marker-inheriting-descendants", "job": job,
                    "invocation": invocation, "launches": self.launches,
                    "startedIdentities": [{"pid": 1234, "startTicks": 5678, "uid": os.getuid(), "live": False}],
                    "discoveryErrors": [], "discoveryReconciliations": []}
            def discover(self):
                return []
            def drain(self, *, grace, kill_wait, deadline):
                start = json.loads((Path(state) / "service/start.json").read_bytes())
                case.assertLessEqual(deadline, start["finalEndNs"] / O.NS)
                case.assertLessEqual(grace + kill_wait, max(0, deadline - fx.fixture.ns / O.NS))
                fx.drains.append((grace, kill_wait, deadline))
                fx.after_drain()
                return fx.scope_survivors
            def close(self):
                self.closed = True
                self.close_calls += 1
                if fx.scope_close_error is not None:
                    raise fx.scope_close_error
        result = Scope()
        fx.scopes.append(result)
        return result

    def prepare_seam_model(self):
        """Enter-only compatibility DATA, never the accepted reader/generator.

        Keep composed InitializationControls/SenderStepControls setup unchanged.
        This supplies the existing fixed capture grammar and Step/input bytes;
        no capture/continuity/admission checker is patched to accept them.
        """
        if hasattr(self, "_seam_roots"):
            return
        old, rows, directories = dict(self.graph), {}, set()
        recipient = N._recipient_path()
        preparation = recipient.with_name(recipient.name.removesuffix("-recipient"))
        roots = {"P": preparation, "E": preparation.with_name(preparation.name + "-entry"),
            "R": recipient, "S": recipient.with_name(recipient.name + "-output")}
        stamp, clock = self.fx.fixture.ns, self.clock
        context = O.parse(old["P/context.json"])
        context.update(root=str(F.ROOT), session=str(preparation))
        records = {name: old["P/acquisition-queries/" + name + ".bin"] for name in N.ORIGINAL_KEYS}
        identity = N.initial_identity.bind_worker_match(N.acquisition.stages.BootstrapMatch(records["match"]),
            event_raw=records["event"], policy_raw=records["candidate_policy_raw"], now=context["observed"]["firstUseAt"])

        def add(name, raw=None):
            self.assertNotIn(name, rows)
            rows[name] = O.encoded({"suppliedSeamDataNotOriginalEvidence": name}) if raw is None else raw
            directories.add(name.rsplit("/", 1)[0])

        def query(root, acquisition=False):
            directories.add(root + "/query-home")
            add(root + "/owner.json")
            add(root + "/session-result.json")
            for name in N.ORIGINAL_KEYS if acquisition else N.SOURCE_KEYS:
                add(root + "/" + name + ".bin", records[name])
            if not acquisition:
                add(root + "/source-return.json")
            for number in range(1, 25 if acquisition else 13):
                directory = root + "/query-" + f"{number:032x}"
                for name in ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"):
                    add(directory + "/" + name, b"" if name == "stderr.log" else None)

        # Same fixed shapes as the independent WorkerModel fixture, but only
        # in-memory old rows and actual empty directory handles. No old body
        # file, old-byte scan, crypto inventory or canonical initializer runs.
        for group, names in (("P", ("prelude.json", "context.json", "worker-identity.json", "worker-service-time.json",
                "worker-allocation-proposal.json", "initial-result.json")),
                ("E", ("entry-window.json", "context.json", "entry-pending.json")),
                ("R/authority", ("authority-window.json", "context.json", "authority-pending.json"))):
            for name in names:
                add(group + "/" + name)
            for name in (*sorted(S.PHASE_FILES), "child-result.json"):
                add(group + "/service/" + name, b"" if name == "stderr.log" else None)
            directories.update(group + "/" + name for name in ("control-home", "temporary"))
            for name in ("source-before", "acquisition-queries", "source-after"):
                query(group + "/" + name, name == "acquisition-queries")
        for name in (*N.RECIPIENT_FILES, "recipient-context.json", "recipient-pending.json"):
            add("R/" + name)
        for name in (*sorted(S.PHASE_FILES), "child-result.json"):
            add("R/recipient-validation/" + name, b"" if name == "stderr.log" else None)
        for root in ("R/recipient-validation/source-before", "R/recipient-validation/source-after", "R/source-final"):
            query(root)
        for name in ("readmission-return.json", "recipient-return.json", "sender-pending.json"):
            add("S/" + name)
        directories.update("R/" + name for name in ("control-home", "temporary", "crypto"))
        for name in ("worker-identity.json", "worker-service-time.json", "worker-allocation-proposal.json"):
            rows["P/" + name] = old["P/" + name]
        rows["P/context.json"], rows["P/service/start.json"] = O.encoded(context), old["P/service/start.json"]
        rows["R/recipient-context.json"] = O.encoded({"job": "c" * 32, "root": str(F.ROOT), "session": str(recipient)})
        rows["R/recipient-public.asc"] = identity.public_key
        rows["S/sender-pending.json"] = O.encoded({"readWindow": {"retainedNs": stamp, "previousLocal": stamp / O.NS,
            "clock": O.clock_value(clock), "readEndNs": stamp + 30 * O.NS, "readLocalCeiling": stamp / O.NS + 30}})
        self.assertEqual(len(rows), 1066)
        self.assertEqual({group: sum(name.split("/", 1)[0] == group for name in rows) for group in roots},
            {"P": 284, "E": 281, "R": 498, "S": 3})
        self.assertEqual(len(directories), 222)
        for name in sorted(directories, key=lambda value: (value.count("/"), value)):
            group, *parts = name.split("/")
            roots[group].joinpath(*parts).mkdir(parents=True, mode=0o700, exist_ok=True)
        self._seam_roots, self._seam_directories = roots, tuple(sorted(directories))
        self.graph = tuple(sorted(rows.items()))
        self.sender_hash = O.digest(rows["S/sender-pending.json"])
        os.environ[N.RECEIVING_HASH_ENV] = self.sender_hash
        start = O.parse(rows["P/service/start.json"])
        captured = (rows["P/context.json"], tuple(records.items()), start["invocation"], start["startedNs"], start["workEndNs"])
        path = N._step_path()
        directory = Q._new_private_directory(path)
        directory_identity = S.directory_identity(list(directory.identity), clock.role)
        directory.close()
        step = O.encoded({"schema": 1, "scope": N.continuity.STEP_SCOPE, "directory": str(path),
            "directoryIdentity": directory_identity, "senderSha256": self.sender_hash, "observed": context["observed"],
            "serviceJob": list(N._service_job(captured, clock)), "workerIdentitySha256": O.digest(identity.record),
            "originalProposalSha256": O.digest(rows["P/worker-allocation-proposal.json"]), "clock": O.clock_value(clock),
            "bootSha256": self.fx.gate_boot, "lowerNs": stamp, "lowerLocal": stamp / O.NS,
            "readEndNs": stamp + 30 * O.NS, "readLocalCeiling": stamp / O.NS + 30,
            "sample": "AFTER_SENDER_FUNCTION_BEFORE_GUARDED_OUTPUT_AND_STEP_RETURN", "writerReturn": "PENDING_OWNER_CLOSE",
            "originalStepOutcome": "NOT_OBSERVED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        (path / N.continuity.STEP_FILE).write_bytes(step)
        (path / N.continuity.STEP_FILE).chmod(0o600)
        os.environ[N.continuity.STEP_HASH_ENV] = O.digest(step)
        self.fx.complete_worker_queries = True
        self.fx.stack.enter_context(patch.object(S.canonical, "init_request", side_effect=SEAM_REQUEST))
        for name in ("JAVA_HOME", "P2PKIT_AUDIT_JDK21"):
            home = self.fx.base / name
            (home / "bin").mkdir(parents=True, mode=0o700)
            for binary in ("java", "javac"):
                target = home / "bin" / binary
                target.write_bytes(b"NONFUNCTIONAL_SYNTHETIC_JDK_NEVER_EXECUTE\n")
                target.chmod(0o700)
            os.environ[name] = str(home)

    def enter(self):
        self.prepare_seam_model()
        return N._receive_initialization(self.fx.cancelled)

    def assert_receiver_closed(self):
        self.assertTrue(N._RECEIVING_WINDOWS)
        for state in N._RECEIVING_WINDOWS.values():
            self.assertTrue(state.terminal)
            self.assertTrue(state.roster.owner.closed)
            if not state.roster.owner.unknown:
                self.assertTrue(all(row["attempted"] and row["closed"] for row in state.roster.rows))

    def test_live_scope_keeps_original_anchor_and_closes_authority_before_token_free_yield(self):
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_FIXED_INITIALIZER_NOT_CONNECTED"):
            with self.enter() as continuation:
                owner, window = continuation.checked()
                self.continuations.append(continuation)
                self.assertIs(owner, self.read_calls[0][0])
                self.assertIs(window, self.read_calls[0][1])
                self.assertIs(owner.first, self.read_calls[0][2])
                self.assertEqual(window.work, owner.first.nanoseconds + 120 * O.NS)
                self.assertGreater(window.last, owner.first.nanoseconds + self.reader_delay)
                self.assertNotIn(O.wire.TOKEN_ENV, os.environ)
                self.assertTrue(all(state.roster.owner.closed and state.terminal for state in N._AUTHORITY_WINDOWS.values()
                    if state.roster is not None))
                self.assertEqual([len(value.calls) for value in self.fx.queries], [12, 24, 12])
                self.assertTrue(all(value.closed and value.finalizations == 1 for value in self.fx.queries))
                self.assertEqual(len(self.fx.fixture.requests), 8)
                self.assertEqual(len(self.fx.scopes), 1)
                self.assertEqual(self.fx.scopes[0].close_calls, 1)
                self.assertEqual(len(self.read_calls), 1)
                self.assertEqual(len(window.state().originals), 1066)  # Supplied model only.
        self.assert_receiver_closed()
        with self.assertRaises(I.AdmissionError):
            self.continuations[0].checked()

    def test_late_reader_cannot_start_another_init120(self):
        self.reader_delay = 120 * O.NS
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT120_EXPIRED"):
            with self.enter():
                self.fail("late reader must not yield")
        self.assertEqual(self.fx.queries, [])
        self.assertEqual(self.fx.fixture.requests, [])
        self.assert_receiver_closed()

    def test_missing_step_cannot_admit_job_from_supplied_sender_graph(self):
        self.prepare_seam_model()
        del os.environ[N.continuity.STEP_HASH_ENV]
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_CONTINUITY_REQUIRED"):
            with self.enter():
                self.fail("supplied graph alone must not admit a worker job")
        self.assertEqual(self.fx.queries, [])
        self.assertEqual(self.fx.scopes, [])
        self.assertFalse(N._AUTHORITY_RETURNS)
        self.assert_receiver_closed()

    def test_changed_step_bytes_refuse_before_current_source_or_native_acquisition(self):
        self.prepare_seam_model()
        path = N._step_path() / N.continuity.STEP_FILE
        step = O.parse(path.read_bytes())
        step["bootSha256"] = "b" * 64
        path.write_bytes(O.encoded(step))
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_CONTINUITY_BYTES"):
            with self.enter():
                self.fail("changed Step must not admit a worker job")
        self.assertEqual(self.fx.queries, [])
        self.assertEqual(self.fx.scopes, [])
        self.assertFalse(N._AUTHORITY_RETURNS)
        self.assert_receiver_closed()

    def test_acquisition_close_uses_remaining_init_work_not_final_or_new_time(self):
        def late(directory):
            if directory.name == "source-after":
                state = next(iter(N._RECEIVING_WINDOWS.values()))
                self.fx.fixture.ns = state.first + 120 * O.NS
        self.fx.after_query_close = late
        with self.assertRaises((I.AdmissionError, O.OriginError)):
            with self.enter():
                self.fail("late current authority must not yield")
        self.assertFalse(N._RECEIVING_CONTINUATIONS)
        self.assertTrue(self.fx.queries[-1].closed)
        self.assert_receiver_closed()

    def test_current_service_job_must_equal_original_job_and_runner(self):
        job = self.fx.fixture.bodies["jobs"]["jobs"][0]
        job.update(id=1901, url=O.wire.ORIGIN + N.acquisition.API + "/actions/jobs/1901")
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_AUTHORITY_JOB_OR_MATCH_CHANGED"):
            with self.enter():
                self.fail("changed current service job must not yield")
        self.assertFalse(N._RECEIVING_CONTINUATIONS)
        self.assert_receiver_closed()

    def test_dirty_current_source_refuses_before_http(self):
        self.fx.fixture.git.clean_value = False
        with self.assertRaises(I.AdmissionError):
            with self.enter():
                self.fail("changed current source must not yield")
        self.assertEqual(self.fx.fixture.requests, [])
        self.assert_receiver_closed()

    def test_changed_owner_statement_refuses_current_acquisition(self):
        self.fx.fixture.bodies["comment"]["body"] += " "
        with self.assertRaises((I.AdmissionError, O.OriginError)):
            with self.enter():
                self.fail("changed statement must not yield")
        self.assertTrue(self.fx.child_errors)
        self.assertFalse(N._RECEIVING_CONTINUATIONS)
        self.assert_receiver_closed()

    def test_reader_failure_preserves_first_exception_and_closes_receiver(self):
        failure = self.reader_error = FirstFailure("MODEL_FIRST_READER_FAILURE")
        with self.assertRaises(FirstFailure) as caught:
            with self.enter():
                self.fail("failed reader must not yield")
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.fx.queries, [])
        self.assertNotIn(O.wire.TOKEN_ENV, os.environ)
        self.assert_receiver_closed()

    def test_cancellation_does_not_reach_native_acquisition(self):
        self.fx.cancelled.append(signal.SIGTERM)
        with self.assertRaises(KeyboardInterrupt):
            with self.enter():
                self.fail("cancelled receiver must not yield")
        self.assertEqual(self.fx.queries, [])
        self.assertEqual(self.fx.scopes, [])
        self.assert_receiver_closed()

    def test_failed_query_finalizer_cannot_publish_current_authority(self):
        failure = self.fx.query_close_error = RuntimeError("MODEL_QUERY_FINALIZER_FAILURE")
        with self.assertRaises(RuntimeError) as caught:
            with self.enter():
                self.fail("failed query close must not yield")
        self.assertIs(caught.exception, failure)
        self.assertTrue(self.fx.queries[0].closed)
        self.assertEqual(self.fx.fixture.requests, [])
        self.assertFalse(N._RECEIVING_CONTINUATIONS)
        self.assert_receiver_closed()

    def test_failed_native_close_cannot_publish_current_authority(self):
        self.fx.scope_close_error = RuntimeError("MODEL_NATIVE_CLOSE_FAILURE")
        with self.assertRaises((RuntimeError, I.AdmissionError, O.OriginError)):
            with self.enter():
                self.fail("failed native close must not yield")
        self.assertEqual(self.fx.scopes[0].close_calls, 1)
        self.assertFalse(N._RECEIVING_CONTINUATIONS)
        self.assertTrue(any(state.roster.owner.unknown for state in N._AUTHORITY_WINDOWS.values() if state.roster is not None))
        self.assert_receiver_closed()

    def test_copied_or_unregistered_continuation_cannot_borrow_live_owner(self):
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_FIXED_INITIALIZER_NOT_CONNECTED"):
            with self.enter() as continuation:
                for other in (N._ReceivingContinuation(), copy.copy(continuation)):
                    with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_CONTINUATION_NOT_ORIGINAL"):
                        other.checked()
                continuation.checked()
        self.assert_receiver_closed()

    def test_restored_transport_cannot_revive_failed_original_continuation(self):
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_STEP_OR_TOKEN_CHANGED") as stopped:
            with self.enter() as continuation:
                owner, window = continuation.checked()
                os.environ[N.RECEIVING_HASH_ENV] = "f" * 64
                with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_STEP_OR_TOKEN_CHANGED") as first:
                    continuation.checked()
                self.assertIs(owner.original, first.exception)
                self.assertTrue(N._RECEIVING_WINDOWS[id(window)].failed)
                os.environ[N.RECEIVING_HASH_ENV] = self.sender_hash
                with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_OWNER_FAILED"):
                    continuation.checked()
                self.assertIs(owner.original, first.exception)
        self.assertIs(stopped.exception, first.exception)
        self.assert_receiver_closed()

    def test_reintroduced_token_refuses_original_continuation(self):
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_STEP_OR_TOKEN_CHANGED"):
            with self.enter() as continuation:
                os.environ[O.wire.TOKEN_ENV] = F.TOKEN
                continuation.checked()
        self.assert_receiver_closed()

    def test_receiving_window_cannot_enter_old_recipient_authority_route(self):
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_FIXED_INITIALIZER_NOT_CONNECTED"):
            with self.enter() as continuation:
                _owner, window = continuation.checked()
                with self.assertRaisesRegex(I.AdmissionError, "AUTHORITY_EPISODE"):
                    N._RecipientAuthorityWindow.parent(window)
                raw = O.encoded({"scope": S.INITIAL_RECEIVING_CONTEXT_SCOPE})
                self.assertEqual(S.phase_command(raw)[5], "_service-receiving-authority")
                self.assertNotEqual(S.initial_authority_command(O.digest(raw))[5], S.phase_command(raw)[5])
        self.assert_receiver_closed()

    def test_rebound_receiver_owner_fence_refuses_and_retains_original_resources(self):
        rows = None
        with self.assertRaises(I.AdmissionError):
            with self.enter() as continuation:
                owner, window = continuation.checked()
                rows = tuple(window.state().roster.rows)
                owner.fence = object()  # Do not restore an invalid live publication.
                continuation.checked()
        self.assertIsNotNone(rows)
        state = next(iter(N._RECEIVING_WINDOWS.values()))
        self.assertTrue(state.roster.owner.unknown)
        self.assertEqual(tuple(state.roster.rows), rows)
        self.assertTrue(any(owner is state.roster.owner for owner in S.QUARANTINE))


if __name__ == "__main__":
    unittest.main(failfast=True)
