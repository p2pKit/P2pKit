#!/usr/bin/env python3
"""New receiving initializer controls, AUTHORED until separately authorized.

Composition, not inheritance/selection of any accepted tests. The old1066 reader
is an explicit supplied graph model. Canonical initialize writes tiny real files;
its Git/host, native process/boot, clocks and upstream HTTP are MODELS. No argv,
JDK, network, GPG, provider, build or actual native observation is executed.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Installs the existing process/network/native audit prohibition before project imports.
R = load("receiving_initializer_models", Path(__file__).with_name("hosted-initial-recipient-receiving-test.py"))
N, S, O, I, Q = R.N, R.S, R.O, R.I, R.Q
C = N.continuity
ROOT = Path(__file__).resolve().parents[2]
A = load("receiving_canonical_file_model", ROOT / "scripts/run-audit-command.py")
REQUEST = S.canonical.init_request
BOOT = "b" * 64


class InitializationControls(unittest.TestCase):
    def setUp(self):
        self.rx = R.ReceivingControls("runTest")
        self.addCleanup(self.rx.doCleanups)
        self.rx.setUp()
        self.fx, self.stack = self.rx.fx, self.rx.fx.stack
        self.addCleanup(self.reset_new_models)
        self.init_scopes, self.init_events, self.init_errors, self.request_calls = [], [], [], []
        self.request_changed = False
        self.before_init = self.after_init = self.init_drain = self.init_close = self.init_constructed = lambda: None
        self.packet = None
        self.make_step_model()
        self.stack.enter_context(patch.object(C, "boot_digest", return_value=BOOT))
        self.stack.enter_context(patch.object(S.canonical, "init_request", side_effect=self.request))
        self.stack.enter_context(patch.object(S.processes, "make_scope", side_effect=self.scope))
        for name in ("JAVA_HOME", "P2PKIT_AUDIT_JDK21"):
            home = self.fx.base / name
            (home / "bin").mkdir(parents=True, mode=0o700)
            for binary in ("java", "javac"):
                path = home / "bin" / binary
                path.write_bytes(b"NONFUNCTIONAL_SYNTHETIC_JDK_NEVER_EXECUTE\n")
                path.chmod(0o700)
            os.environ[name] = str(home)
        self.output = self.fx.base / "_runner_file_commands" / ("set_output_" + "1" * 8 + "-" + "2" * 4 +
            "-" + "3" * 4 + "-" + "4" * 4 + "-" + "5" * 12)
        # NativeModels may already own this private runner-command directory
        # for its distinct gate fixture output. Never replace either file.
        self.output.parent.mkdir(mode=0o700, exist_ok=True)
        self.output.touch(mode=0o600)
        os.environ["GITHUB_OUTPUT"] = str(self.output)

    def reset_new_models(self):
        for registry in (N._RECEIVING_INIT_ATTEMPTS, N._RECEIVING_INIT_RETURNS, N._RECEIVING_CLOSED_RETURNS):
            registry.clear()
        C.QUARANTINE.clear()  # Only explicit fake failures; never native recovery.

    def put(self, path, raw):
        path.write_bytes(raw)
        path.chmod(0o600)

    def make_step_model(self):
        rows = dict(self.rx.graph)
        ns, clock = self.fx.fixture.ns, self.rx.clock
        sender = O.encoded({"readWindow": {"retainedNs": ns, "previousLocal": ns / O.NS,
            "clock": O.clock_value(clock), "readEndNs": ns + 30 * O.NS, "readLocalCeiling": ns / O.NS + 30}})
        rows["S/sender-pending.json"] = sender
        del rows[next(name for name in rows if name.startswith("MODEL_ONLY_UNUSED/"))]
        rows["R/recipient-context.json"] = O.encoded({"job": "c" * 32})
        self.rx.graph = tuple(rows.items())
        self.rx.sender_hash = O.digest(sender)
        os.environ[N.RECEIVING_HASH_ENV] = self.rx.sender_hash
        start = O.parse(rows["P/service/start.json"])
        captured = (rows["P/context.json"], tuple((name, rows["P/acquisition-queries/" + name + ".bin"])
            for name in N.ORIGINAL_KEYS), start["invocation"], start["startedNs"], start["workEndNs"])
        path = N._step_path()
        directory = Q._new_private_directory(path)
        identity = S.directory_identity(list(directory.identity), clock.role)
        directory.close()
        raw = O.encoded({"schema": 1, "scope": C.STEP_SCOPE, "directory": str(path), "directoryIdentity": identity,
            "senderSha256": self.rx.sender_hash, "observed": O.parse(rows["P/context.json"])["observed"],
            "serviceJob": list(N._service_job(captured, clock)), "workerIdentitySha256": O.digest(rows["P/worker-identity.json"]),
            "originalProposalSha256": O.digest(rows["P/worker-allocation-proposal.json"]), "clock": O.clock_value(clock),
            "bootSha256": BOOT, "lowerNs": ns, "lowerLocal": ns / O.NS, "readEndNs": ns + 30 * O.NS,
            "readLocalCeiling": ns / O.NS + 30,
            "sample": "AFTER_SENDER_FUNCTION_BEFORE_GUARDED_OUTPUT_AND_STEP_RETURN", "writerReturn": "PENDING_OWNER_CLOSE",
            "originalStepOutcome": "NOT_OBSERVED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        self.put(path / C.STEP_FILE, raw)
        os.environ[C.STEP_HASH_ENV] = O.digest(raw)

    def request(self, **kwargs):
        self.request_calls.append((kwargs, len(self.fx.queries)))
        raw = REQUEST(**kwargs)
        return raw + b" " if self.request_changed else raw

    def window(self):
        return next(iter(N._RECEIVING_WINDOWS.values())).window

    def scope(self, job, invocation, state, home):
        if Path(state) == N._receiving_path() / "authority":
            self.assertTrue(self.request_calls, "canonical source bytes must be captured BEFORE current source authority")
            return self.rx.make_receiving_scope(job, invocation, state, home)
        case, path = self, N._receiving_path()
        self.assertEqual((Path(state), Path(home)), (path, path / "control-home"))
        self.init_events.append("construct")
        class Scope:
            name, baseline = "linux-proc-pidfd", set()
            def __init__(self):
                self.launches, self.closed, self.close_calls = [], False, 0
            def _identity(self, pid):
                return {"pid": pid, "startTicks": 9012, "live": True}
            def spawn(self, argv, cwd, env, *, stdout, stderr):
                case.init_events.append("spawn")
                current = case.window().state()
                inputs = current.inputs[0]
                case.assertEqual(argv, O.parse(inputs.request_raw)["argv"])
                case.assertEqual(cwd, str(ROOT))
                case.assertNotIn("--minimum-ns", argv)
                for name in (O.wire.TOKEN_ENV, "GITHUB_TOKEN", N.RECEIVING_HASH_ENV, C.STEP_HASH_ENV, "GITHUB_OUTPUT"):
                    case.assertNotIn(name, env)
                case.assertTrue(all(scope.closed for scope in case.fx.scopes))
                case.assertTrue(all(query.closed for query in case.fx.queries))
                case.assertEqual(len(case.rx.read_calls), 1)  # SUPPLIED MODEL, never the real1066 reader.
                case.assertFalse((path / "state").exists())
                self.launches = [{"api": "subprocess.Popen", "requestedArgv": argv, "resolvedArgv": argv,
                    "cwd": cwd, "shell": False, "created": True, "executable": argv[0], "pid": 54322,
                    "outputMode": "caller-owned-files"}]
                case.before_init()
                source = {**O.parse(current.identity_fields[0])["source"], "status": "", "diffSha256": O.digest(b"")}
                output, code = io.StringIO(), 0
                try:
                    with patch.dict(os.environ, env, clear=True), redirect_stdout(output), \
                            patch.object(A, "source_snapshot", return_value=source), \
                            patch.object(A, "host_role", return_value="linux-x64"), \
                            patch.object(A, "git", side_effect=AssertionError("NO_REAL_CANONICAL_GIT")):
                        code = A.initialize(SimpleNamespace(root=str(ROOT), state=str(path / "state"),
                            expected_commit=source["commit"], host="linux-x64"))
                    os.write(stdout.fileno(), output.getvalue().encode("ascii"))
                except BaseException as error:
                    case.init_errors.append(error)
                    os.write(stderr.fileno(), b"SYNTHETIC_INITIALIZER_FAILURE\n")
                    code = 125
                case.after_init()
                return SimpleNamespace(pid=54322, stdout=None, stderr=None, poll=lambda: code)
            def description(self):
                return {"backend": self.name, "scope": "controlled-marker-inheriting-descendants", "job": job,
                    "invocation": invocation, "launches": self.launches, "startedIdentities":
                    ([{"pid": 54322, "startTicks": 6789, "uid": os.getuid(), "live": False}] if self.launches else []),
                    "discoveryErrors": [], "discoveryReconciliations": []}
            def discover(self):
                return []
            def drain(self, *, grace, kill_wait, deadline):
                current = case.window().state(cleanup=True)
                case.assertEqual(current.phase, "WORK")
                case.assertLessEqual(deadline, current.locals[0])
                case.assertLessEqual(deadline, current.work / O.NS)
                case.assertLessEqual(grace + kill_wait, max(0, deadline - case.fx.fixture.ns / O.NS))
                case.init_events.append("drain")
                case.init_drain()
                return []
            def close(self):
                self.closed = True
                self.close_calls += 1
                case.init_events.append("close")
                case.init_close()
        result = Scope()
        self.init_scopes.append(result)
        self.init_constructed()
        return result

    def run_step(self):
        outputs = []
        output = SimpleNamespace(buffer=SimpleNamespace(write=lambda raw: (outputs.append(raw), len(raw))[1], flush=lambda: None))
        def fixed(cancelled):
            self.packet = N._initialize_step(cancelled)
            return self.packet
        with patch.object(S.sys, "stdout", output):
            S.guarded(fixed)
        return outputs

    def assert_no_result(self):
        self.assertIsNone(self.packet)
        self.assertEqual(N._RECEIVING_INIT_RETURNS, {})
        self.assertEqual(self.output.read_bytes(), b"")

    def test_fixed_initializer_shares_original120_and_closes_before_digest_only_output(self):
        original_now, reads = N._ReceivingWindow.now, []
        original_read = S.Owner.read
        def now(window, **kwargs):
            self.assertFalse(window.state(cleanup=True).terminal, "terminal receiver must never be re-observed")
            return original_now(window, **kwargs)
        def read(owner, directory, name, *args, **kwargs):
            if directory.path == N._receiving_path() / "state" or directory.path == N._receiving_path() / "canonical-init" and name in ("stdout.log", "stderr.log"):
                self.assertEqual(self.init_events[-1], "close")
                self.assertTrue(self.init_scopes[0].closed)
                reads.append(name)
            return original_read(owner, directory, name, *args, **kwargs)
        with patch.object(N._ReceivingWindow, "now", now), patch.object(S.Owner, "read", read):
            outputs = self.run_step()
        state = self.window().state(cleanup=True)
        self.assertEqual(state.work, state.first + 120 * O.NS)
        self.assertIs(state.first_reading, self.rx.read_calls[0][2])
        self.assertEqual(self.request_calls[0][1], 0)
        self.assertEqual([len(query.calls) for query in self.fx.queries], [12, 24, 12])
        self.assertEqual(self.init_events, ["construct", "spawn", "drain", "close"])
        self.assertTrue(state.terminal and state.roster.owner.closed)
        self.assertTrue(all(row["closed"] and row["attempted"] for row in state.roster.rows))
        self.assertEqual(self.init_scopes[0].close_calls, 1)
        self.assertTrue({"context.json", "stdout.log", "stderr.log"}.issubset(reads))
        self.assertEqual(self.init_errors, [])
        self.assertEqual(len(outputs), 1)
        value = O.parse(outputs[0])
        self.assertEqual(set(value), {"scope", "initializationSha256", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"})
        self.assertEqual(self.output.read_text(), "initializationSha256=" + value["initializationSha256"] + "\n")
        self.assertEqual(O.parse(state.initialization.pending)["ownerReturn"], "PENDING_OWNER_CLOSE")
        self.assertEqual(len(N._RECEIVING_CLOSED_RETURNS), 1)

    def test_source_change_after_authority_cannot_be_recaptured_as_admitted_request(self):
        self.fx.after_query_close = lambda path: setattr(self, "request_changed", True) if path.name == "source-after" else None
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT_REQUEST_CHANGED"):
            self.run_step()
        self.assertEqual(self.init_scopes, [])
        self.assert_no_result()
        self.assertEqual(len(N._RECEIVING_INIT_ATTEMPTS), 1)

    def test_canonical_return_at_original_work120_has_no_final165_or_read195(self):
        self.after_init = lambda: setattr(self.fx.fixture, "ns", self.window().work)
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT120_EXPIRED"):
            self.run_step()
        self.assert_no_result()
        self.assertEqual(self.window().state(cleanup=True).phase, "CLOSING")

    def test_local_scope_close_at_original120_refuses_even_with_earlier_raw(self):
        self.init_close = lambda: self.stack.enter_context(patch.object(N.time, "monotonic", return_value=self.window().local_end))
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT120_EXPIRED"):
            self.run_step()
        self.assert_no_result()
        self.assertTrue(self.init_scopes[0].closed)

    def test_failed_scope_close_preserves_falsey_first_error_and_unknown_custody(self):
        first = R.FirstFailure("SYNTHETIC_INIT_CLOSE")
        def fail():
            raise first
        self.init_close = fail
        with self.assertRaises(R.FirstFailure) as caught:
            self.run_step()
        self.assertIs(caught.exception, first)
        self.assert_no_result()
        self.assertTrue(self.window().state(cleanup=True).roster.owner.unknown)

    def test_postallocation_failure_recovers_original_scope_without_retry(self):
        first, fired, original = R.FirstFailure("SYNTHETIC_SCOPE_POSTRETURN"), [], S.Owner.end
        def end(owner, **kwargs):
            if self.init_scopes and not fired and any(row["owner"] is self.init_scopes[0] for row in owner.resources):
                fired.append(True)
                raise first
            return original(owner, **kwargs)
        with patch.object(S.Owner, "end", end), self.assertRaises(R.FirstFailure) as caught:
            self.run_step()
        self.assertIs(caught.exception, first)
        self.assertEqual(self.init_events, ["construct", "drain", "close"])
        self.assertEqual(self.init_scopes[0].close_calls, 1)
        self.assert_no_result()

    def test_extra_canonical_evidence_is_not_empty_initialized_state(self):
        self.after_init = lambda: self.put(N._receiving_path() / "state/evidence/unexpected.json", b"{}\n")
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT_STATE_ROSTER"):
            self.run_step()
        self.assert_no_result()

    def test_canonical_job_must_differ_from_original_recipient_job(self):
        def change():
            path = N._receiving_path() / "state/context.json"
            value = O.parse(path.read_bytes())
            value["id"] = "c" * 32
            self.put(path, O.encoded(value))
        self.after_init = change
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT_CONTEXT_JOB"):
            self.run_step()
        self.assert_no_result()

    def test_token_reintroduced_at_initializer_construction_prevents_launch(self):
        self.init_constructed = lambda: os.environ.__setitem__(O.wire.TOKEN_ENV, R.F.TOKEN)
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_STEP_OR_TOKEN_CHANGED"):
            self.run_step()
        self.assertNotIn("spawn", self.init_events)
        self.assert_no_result()

    def test_initializer_claim_cannot_launch_twice_or_reconstruct_old_parent(self):
        with N._receive_initialization(self.fx.cancelled) as continuation:
            result = N._initialize_receiving(continuation)
            calls = len(self.request_calls)
            with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_FIXED_INITIALIZER_NOT_CONNECTED_OR_REUSED"):
                N._initialize_receiving(continuation)
            self.assertEqual(len(self.request_calls), calls)
            self.assertEqual(self.init_events.count("spawn"), 1)
        self.assertIs(N._receiving_initialization_return(continuation, closed=True), result)

    def test_boot_change_after_canonical_return_refuses_successful_step(self):
        self.after_init = lambda: self.stack.enter_context(patch.object(C, "boot_digest", return_value="d" * 64))
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_BOOT_CHANGED"):
            self.run_step()
        self.assert_no_result()

    def test_boot_change_after_owner_close_cannot_restore_same_final_output(self):
        returned = N._initialize_step(self.fx.cancelled)
        state = self.window().state(cleanup=True)
        self.assertTrue(state.terminal and state.roster.owner.closed)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in state.roster.rows))
        outputs = []
        output = SimpleNamespace(buffer=SimpleNamespace(write=lambda raw: (outputs.append(raw), len(raw))[1], flush=lambda: None))
        with patch.object(S.sys, "stdout", output), patch.object(C, "boot_digest", return_value="d" * 64), \
                self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT_OUTPUT_BOOT_CHANGED"):
            S.guarded(lambda _cancelled: returned)
        # Restoring BOOT cannot revive the same failed closed-output adapter.
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_INIT_OUTPUT_CHANGED"):
            returned[1].now(final=True, limit=returned[2])
        self.assertEqual(outputs, [])
        self.assertEqual(self.output.read_text(), "initializationSha256=" + returned[0]["initializationSha256"] + "\n")
        self.assertEqual(len(N._RECEIVING_CLOSED_RETURNS), 1)  # Provisional digest/closed history is NOT step success.

    def test_failed_file_command_after_known_close_cannot_return_success(self):
        first = R.FirstFailure("SYNTHETIC_OUTPUT_FAILURE")
        with patch.object(C, "append_outputs", side_effect=first), self.assertRaises(R.FirstFailure) as caught:
            self.run_step()
        self.assertIs(caught.exception, first)
        self.assertIsNone(self.packet)
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertTrue(self.window().state(cleanup=True).roster.owner.closed)
        self.assertEqual(len(N._RECEIVING_CLOSED_RETURNS), 1)  # Closed history is NOT actual successful step evidence.

    def test_failed_predecessor_step_cannot_start_a_receiving_clock(self):
        os.environ[N.RECEIVING_OUTCOME_ENV] = "failure"
        with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_CLOCK_BEFORE_SUCCESS")), \
                self.assertRaisesRegex(I.AdmissionError, "RECEIVING_STEP_INPUTS"):
            self.run_step()
        self.assertEqual(self.rx.read_calls, [])
        self.assert_no_result()

    def test_future_sidecar_lower_bound_cannot_claim_post_step_order(self):
        path = N._step_path() / C.STEP_FILE
        value = O.parse(path.read_bytes())
        value["lowerNs"] += O.NS
        value["lowerLocal"] += 1
        raw = O.encoded(value)
        self.put(path, raw)
        os.environ[C.STEP_HASH_ENV] = O.digest(raw)
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_STEP_ORDER"):
            self.run_step()
        self.assertEqual(self.rx.read_calls, [])
        self.assert_no_result()

    def test_same_boot_sidecar_must_match_original_job_source_and_runner(self):
        path = N._step_path() / C.STEP_FILE
        value = O.parse(path.read_bytes())
        value["serviceJob"][0] += 1
        raw = O.encoded(value)
        self.put(path, raw)
        os.environ[C.STEP_HASH_ENV] = O.digest(raw)
        with self.assertRaisesRegex(I.AdmissionError, "RECEIVING_CONTINUITY_ORIGINALS"):
            self.run_step()
        self.assertEqual(len(self.rx.read_calls), 1)  # The supplied model only; no complete-reader test.
        self.assertEqual(self.fx.queries, [])
        self.assert_no_result()


if __name__ == "__main__":
    unittest.main(failfast=True)
