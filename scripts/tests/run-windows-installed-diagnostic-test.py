#!/usr/bin/env python3
"""Offline models by default; --native is an explicit harmless Windows controller.

Native controls use fixed Python fixtures, never the installed launcher. A separate
PowerShell observer must provide QPC start/frequency and observe final process exit.
Their receipts have a distinct NOT_INSTALLED scope; timeout may have no receipt.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("installed_supervisor", ROOT / "scripts/run-windows-installed-diagnostic.py")
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)
SOURCE = "0" * 40
WORKER_CASES = ("normal", "nonzero", "output-overflow", "blocked-worker", "blocked-outer")
NATIVE_CASES = (*WORKER_CASES, "observer-output-overflow")
FIXTURE_SOURCE = "tests/run-windows-installed-diagnostic-test.py"
NORMAL_OUTPUT = b"HARMLESS_NESTED_CHILD_PASS\n"
OBSERVER_OVERFLOW_BYTES = 65537


def witness_model(clock):
    spec = importlib.util.spec_from_file_location("native_witness_model", ROOT / "scripts/tests/run-windows-installed-observer-native.py")
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    class Api:
        def __init__(self):
            self.live, self.duplicates, self.closes, self.exit_queries = {}, [], [], []
            self.image_queries = []
            self.image_path = r"C:\admitted\python.exe"
            self.image_length = None
            self.image_ok = True
        def _bind(self, name, arguments, result):
            if name != "QueryFullProcessImageNameW":
                raise AssertionError("unexpected witness native binding")
        def identity(self, handle, pid):
            return {"pid": pid, "creationFileTime": pid * 100}
        def WaitForSingleObject(self, handle, milliseconds):
            return 258 if self.live.get(handle, True) else 0
        def DuplicateHandle(self, source, handle, target, output, access, inherit, flags):
            if access != 0x101000 or inherit != 0 or flags != 0:
                raise AssertionError("unexpected duplicate authority")
            output._obj.value = handle + 1000
            self.duplicates.append((handle, output._obj.value))
            return 1
        def IsProcessInJob(self, handle, job, output):
            output._obj.value = 1
            return 1
        def GetHandleInformation(self, handle, output):
            output._obj.value = 0
            return 1
        def GetExitCodeProcess(self, handle, output):
            self.exit_queries.append(handle)
            output._obj.value = 259
            return 1
        def QueryFullProcessImageNameW(self, handle, flags, buffer, length):
            self.image_queries.append((handle, flags, length._obj.value))
            buffer.value = self.image_path
            length._obj.value = (len(self.image_path.encode("utf-16-le")) // 2 if self.image_length is None
                                 else self.image_length)
            return int(self.image_ok)
        def check(self, value, operation):
            if not value:
                raise ValueError("MODEL_NATIVE_FAILURE")
        def close(self, handle):
            self.closes.append(handle)
    api = Api()
    scope = types.SimpleNamespace(api=api, job=999)
    return native, api, scope, native.Witnesses(scope, native.HarnessDeadline(clock))


class Clock:
    frequency = 1000
    def __init__(self, now=1000):
        self.value = now
    def now(self):
        return self.value


def outcome(**changes):
    value = dict(code="PASS", exitCode=0, timedOut=False, cleanupKnown=True,
                 capturesClosed=True, cleanupReasons=[], stage="COMMAND", nativeError=None,
                 pendingContext=None, elapsedSeconds=0.01)
    return {**value, **changes}


class FinishedThread:
    ident = 1
    def start(self):
        pass
    def join(self, timeout=None):
        pass
    def is_alive(self):
        return False


class Fixture:
    def __init__(self, root, clock):
        self.root, self.clock, self.operations = root, clock, []
        self.args = types.SimpleNamespace(private_parent=str(root), expected_source=SOURCE, operation="admission",
            start_counter=1000, counter_frequency=1000, worker=False)
        self.value = {"schema": 1, "appSource": SOURCE, "operation": "admission", "outcome": outcome(), "admissionMatched": True}
        self.child = types.SimpleNamespace(stdout=io.BytesIO(), stderr=io.BytesIO(),
            poll=lambda: 0, wait=lambda timeout: 0)
        fixture = self
        self.owners = []
        class Receipt:
            def __init__(self, owner, name):
                self.owner, self.closed = owner, False
                self.stream = (owner.path / name).open("xb")
                fixture.receipt = self
            def write(self, raw):
                if any(owner.closed for owner in fixture.owners):
                    raise AssertionError("receipt lost original ancestor custody")
                fixture.operations.append("receipt-write")
                return self.stream.write(raw)
            def close(self):
                fixture.operations.append("receipt-close")
                self.stream.close()
                self.closed = True
        class Owner:
            def __init__(self, path):
                self.path, self.closed = path, False
                fixture.owners.append(self)
            def create_directory(self, name, deadline):
                (self.path / name).mkdir()
                return Owner(self.path / name)
            def create_file(self, name, max_bytes, deadline):
                if self.closed:
                    raise AssertionError("receipt creation used a retired directory")
                fixture.operations.append("receipt-create")
                return Receipt(self, name)
            def verify(self):
                fixture.operations.append("verify")
            def close(self):
                fixture.operations.append("owner-close")
                self.closed = True
        class Scope:
            discovery_errors = set()
            def __init__(self, *args):
                self.leaders = []
                fixture.scope = self
            def spawn(self, argv, cwd, env):
                fixture.argv = argv
                fixture.operations.append("spawn")
                self.leaders.append(fixture.child)
                (root / "run/worker.json").write_text(json.dumps(fixture.value))
                return fixture.child
            def discover(self):
                fixture.operations.append("discover")
                return []
            def drain(self, **kwargs):
                fixture.operations.append("drain")
                fixture.drain_options = kwargs
                return []
            def close(self):
                fixture.operations.append("scope-close")
        class Capture:
            def __init__(self, pipe, path, limit):
                self.pipe, self.thread = pipe, FinishedThread()
                self.eof, self.closed, self.error = True, True, None
                path.write_bytes(b"")
        self.A = types.SimpleNamespace(WindowsScope=Scope, ownership_environment=lambda env, *a, **kw: env)
        self.E = types.SimpleNamespace(Capture=Capture, encoded=lambda v: (json.dumps(v)+"\n").encode(),
                                      write_private=lambda p, raw: p.write_bytes(raw))
        self.F = types.SimpleNamespace(open_private_directory=lambda path: Owner(Path(path)))
        self.Receipt, self.Owner = Receipt, Owner

    def run(self):
        with patch.object(H, "source_identity", return_value={"fixture": "a" * 64}):
            result = H.supervise(self.args, H.Deadline(self.clock, 1000, 1000), self.A, self.E, self.F)
        return result, json.loads((self.root / "run/supervisor.json").read_text())


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
    def tearDown(self):
        self.temp.cleanup()

    def test_qpc_admission_refuses_epoch_frequency_future_and_expired_values(self):
        for start, frequency, now in ((-1,1000,1000),(1001,1000,1000),(1000,999,1000),
                                      (1000,1000,31000),(True,1000,1000),(1000,True,1000)):
            with self.subTest(start=start, frequency=frequency, now=now), self.assertRaises(ValueError):
                H.Deadline(Clock(now), start, frequency)
        d = H.Deadline(Clock(), 1000, 1000)
        self.assertEqual(d.end, 31000)
        self.assertEqual(d.check(), 30)

    def test_worker_budgets_never_reset_outer_end(self):
        clock = Clock(); d = H.Deadline(clock, 1000, 1000)
        self.assertEqual(d.worker_budgets(), (15, 5))
        clock.value = 21000
        work, cleanup = d.worker_budgets()
        self.assertLessEqual(work + cleanup, 5)
        self.assertEqual(d.end, 31000)
        clock.value = 26000
        with self.assertRaises(ValueError): d.worker_budgets()

    def test_fixed_worker_has_no_caller_command_or_timeout(self):
        args = H.arguments(["--start-counter","1000","--counter-frequency","1000",
                            "--expected-source",SOURCE,"--private-parent",str(self.root)])
        argv = H.worker_argv(args, self.root / "run")
        self.assertEqual(argv[:4], [sys.executable,"-I","-B","-S"])
        self.assertIn("--worker", argv)
        self.assertNotIn("--timeout", argv)
        for extra in (["--command", "PRIVATE"], ["--start-c", "4"], ["--help"]):
            with self.assertRaises(ValueError):
                H.arguments(argv[5:] + extra)

    def test_exact_admission_and_duplicate_or_excess_json_refused(self):
        value = H.expected_admission(SOURCE)
        self.assertEqual(value["admission"]["publicProvider"], "NOT_ENTERED")
        self.assertEqual(H.decode(json.dumps(value).encode(), H.LOG_LIMIT), value)
        for raw in (b'{"a":1,"a":2}', b'x' * (H.LOG_LIMIT + 1), b'', b'{"a":NaN}',
                    b'{"a":Infinity}', b'{"a":-Infinity}', b'{"a":1e400}'):
            with self.assertRaises(ValueError): H.decode(raw, H.LOG_LIMIT)
        line=json.dumps(value,separators=(",",":")).encode()
        self.assertTrue(H.admission_matches(line+b"\n",SOURCE))
        self.assertTrue(H.admission_matches(line+b"\r\n",SOURCE))
        for raw in (line, line+b"\nPRIVATE", line.replace(b'"schema":1',b'"schema":true')+b"\n",
                    line.replace(b'"schema":1',b'"schema":1.0')+b"\n",
                    line.replace(b'"publicProvider":"NOT_ENTERED"', b'"publicProvider":"DISABLED"')+b"\n"):
            self.assertFalse(H.admission_matches(raw,SOURCE))

    def test_outcome_and_worker_record_require_all_original_success_fields(self):
        self.assertTrue(H.command_pass(outcome()))
        for key, bad in (("exitCode",True),("exitCode",1),("timedOut",True),
                          ("cleanupKnown",False),("capturesClosed",False),("cleanupReasons",["UNKNOWN"]),
                         ("code","CLEANUP"),("stage","OTHER"),("elapsedSeconds",True),
                         ("elapsedSeconds",float("inf")),("elapsedSeconds",float("nan")),
                         ("elapsedSeconds",-0.1)):
            self.assertFalse(H.command_pass({**outcome(),key:bad}))
        for missing in outcome():
            partial = outcome()
            del partial[missing]
            self.assertFalse(H.command_pass(partial))
        self.assertFalse(H.command_pass({**outcome(), "unexpected": True}))
        value = {"schema":1,"appSource":SOURCE,"operation":"admission","outcome":outcome(),"admissionMatched":True}
        self.assertTrue(H.validate_worker(value, SOURCE))
        for key, bad in (("schema",True),("appSource","a"*40),("admissionMatched",1)):
            with self.assertRaises(ValueError): H.validate_worker({**value,key:bad},SOURCE)

    def test_outer_success_retains_exact_counter_scope_and_source_distinction(self):
        f = Fixture(self.root, Clock()); code, record = f.run()
        self.assertEqual(code, 0)
        self.assertEqual(record["status"], "PASS")
        self.assertEqual(record["deadlineCounter"], 31000)
        self.assertEqual(record["watchdogCounter"], 30000)
        self.assertEqual(record["appSource"], SOURCE)
        self.assertEqual(record["supervisorSource"], {"fixture":"a"*64})
        self.assertLess(f.operations.index("drain"), f.operations.index("scope-close"))
        self.assertLess(f.operations.index("scope-close"), f.operations.index("owner-close"))
        self.assertLess(f.operations.index("receipt-write"), f.operations.index("receipt-close"))
        self.assertLess(f.operations.index("receipt-close"), f.operations.index("owner-close"))
        self.assertTrue(f.receipt.closed and all(owner.closed for owner in f.owners))

    def test_outer_refuses_failed_worker_but_preserves_actual_outcome(self):
        f = Fixture(self.root, Clock()); f.child.poll = lambda: 1
        f.value.update(admissionMatched=False, outcome={**outcome(),"code":"COMMAND_FAILED","exitCode":1})
        code, record = f.run()
        self.assertEqual(code, 1)
        self.assertEqual(record["workerOutcome"], f.value)
        self.assertEqual(record["status"], "FAIL")

    def test_outer_refuses_live_scope_or_uncertain_close_without_raw_errors(self):
        for operation in ("drain", "close"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                f = Fixture(Path(tmp), Clock())
                if operation == "drain":
                    f.A.WindowsScope.drain = lambda self, **kw: [{"pid":1}]
                else:
                    def bad(self): raise OSError("PRIVATE_PATH_PRIVATE_CREDENTIAL")
                    f.A.WindowsScope.close = bad
                code, record = f.run()
                self.assertEqual(code, 1)
                self.assertFalse(record["outerCleanupKnown"])
                self.assertNotIn("PRIVATE", json.dumps(record))

    def test_late_native_returns_cannot_become_pass(self):
        for operation in ("spawn", "discover", "drain", "close"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                clock = Clock(); f = Fixture(Path(tmp), clock)
                original = getattr(f.A.WindowsScope, operation)
                def late(instance, *args, _original=original, **kwargs):
                    result = _original(instance, *args, **kwargs)
                    clock.value = 31500
                    return result
                setattr(f.A.WindowsScope, operation, late)
                with self.assertRaises(ValueError): f.run()
                self.assertFalse((Path(tmp)/"run/supervisor.json").exists())

    def test_watchdog_is_armed_before_owned_scope_and_never_disarmed(self):
        events = []
        args = types.SimpleNamespace(worker=False,start_counter=1000,counter_frequency=1000)
        with patch.object(H,"arguments",return_value=args), patch.object(H,"Counter",return_value=Clock()), \
             patch.object(H,"arm_watchdog",side_effect=lambda d:events.append("armed")), \
             patch.object(H,"modules",side_effect=lambda:(events.append("imports") or (None,None,None))), \
             patch.object(H,"supervise",side_effect=lambda *a:(events.append("scope") or 0)), \
             patch.object(H.sys,"stdout",io.StringIO()), patch.object(H.os,"_exit",side_effect=lambda c:events.append(("exit",c))):
            H.main([])
        self.assertEqual(events,["armed","imports","scope",("exit",0)])

    def test_watchdog_fires_at_original_29_seconds_without_a_new_allowance(self):
        clock = Clock()
        terminated = []
        class Terminated(Exception):
            pass
        def terminate():
            terminated.append(clock.value)
            raise Terminated()
        clock.terminate = terminate
        class InlineThread:
            def __init__(self, target, name, daemon):
                self.target = target
                self.assertions = (name, daemon)
            def start(self):
                self.target()
        def advance(seconds):
            self.assertGreater(seconds, 0)
            self.assertLessEqual(seconds, 0.02)
            clock.value += max(1, round(seconds * clock.frequency))
        with patch.object(H.threading, "Thread", InlineThread), patch.object(H.time, "sleep", advance):
            with self.assertRaises(Terminated):
                H.arm_watchdog(H.Deadline(clock, 1000, 1000))
        self.assertEqual(terminated, [30000])

    def test_worker_fixed_launcher_and_clipped_original_e_budgets(self):
        directory = self.root / "run"; directory.mkdir()
        args = types.SimpleNamespace(private_parent=str(self.root),expected_source=SOURCE,operation="admission")
        calls = []
        def command(argv, **kw):
            calls.append((argv,kw)); kw["private"].mkdir()
            (kw["private"]/"stdout.log").write_bytes(json.dumps(H.expected_admission(SOURCE),separators=(",",":")).encode()+b"\n")
            (kw["private"]/"stderr.log").write_bytes(b"")
            return outcome()
        E = types.SimpleNamespace(run_command=command,encoded=lambda x:json.dumps(x).encode(),
                                  write_private=lambda p,b:p.write_bytes(b))
        with patch.object(H,"installed_launcher",return_value=Path("/ProgramFiles/P2pKit Sample/P2pKit Sample.exe")):
            self.assertEqual(H.worker(args,H.Deadline(Clock(),1000,1000),E),0)
        self.assertEqual(calls[0][0][1:],["--rpc-windows-installed-admission"])
        self.assertEqual((calls[0][1]["timeout"],calls[0][1]["cleanup_seconds"]),(15,5))
        self.assertEqual(calls[0][1]["log_limit"],4096)

    def test_bounded_reader_refuses_oversized_result(self):
        path=self.root/"large";path.write_bytes(b'x'*(H.RECORD_LIMIT+1))
        with self.assertRaises(ValueError):H.read_bounded(path,H.RECORD_LIMIT)

    def test_operation_is_bound_to_worker_command_output_and_every_receipt(self):
        for operation, flag in H.OPERATIONS.items():
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                args = H.arguments(["--start-counter", "1000", "--counter-frequency", "1000",
                    "--expected-source", SOURCE, "--private-parent", str(root), "--operation", operation])
                argv = H.worker_argv(args, root / "run")
                self.assertEqual(argv[argv.index("--operation") + 1], operation)
                (root / "run").mkdir()
                calls = []
                def command(argv, **options):
                    calls.append(argv)
                    options["private"].mkdir()
                    raw = json.dumps(H.expected_result(SOURCE, operation), separators=(",", ":")).encode() + b"\n"
                    (options["private"] / "stdout.log").write_bytes(raw)
                    (options["private"] / "stderr.log").write_bytes(b"")
                    return outcome()
                E = types.SimpleNamespace(run_command=command, encoded=lambda value: json.dumps(value).encode(),
                                          write_private=lambda path, raw: path.write_bytes(raw))
                with patch.object(H, "installed_launcher", return_value=Path("/ProgramFiles/P2pKit Sample.exe")):
                    self.assertEqual(H.worker(args, H.Deadline(Clock(), 1000, 1000), E), 0)
                self.assertEqual(calls[0][1:], [flag])
                receipt = json.loads((root / "run/worker.json").read_bytes())
                self.assertTrue(H.validate_worker(receipt, SOURCE, operation))
                for other in H.OPERATIONS.keys() - {operation}:
                    with self.assertRaises(ValueError): H.validate_worker(receipt, SOURCE, other)
                    raw = json.dumps(H.expected_result(SOURCE, other), separators=(",", ":")).encode() + b"\n"
                    self.assertFalse(H.admission_matches(raw, SOURCE, operation))
            with tempfile.TemporaryDirectory() as tmp:
                fixture = Fixture(Path(tmp), Clock())
                fixture.args.operation = operation
                fixture.value["operation"] = operation
                code, receipt = fixture.run()
                self.assertEqual(code, 0)
                self.assertEqual(receipt["operation"], operation)

    def test_unrecognized_operation_is_not_a_command_or_profile_override(self):
        for operation in ("", "Profile-create", "profile-create ", "profile-reset", "--help", "admission;exit"):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                H.arguments(["--start-counter", "1000", "--counter-frequency", "1000",
                    "--expected-source", SOURCE, "--private-parent", str(self.root), "--operation", operation])

    def test_failed_final_record_or_late_capture_never_returns_success(self):
        f=Fixture(self.root,Clock())
        def blocked_write(owner,raw): raise OSError("PRIVATE")
        f.Receipt.write=blocked_write
        with self.assertRaises(OSError): f.run()
        self.assertEqual((self.root/"run/supervisor.json").read_bytes(), b"")
        self.assertTrue(f.receipt.closed and all(owner.closed for owner in f.owners))
        with tempfile.TemporaryDirectory() as tmp:
            f=Fixture(Path(tmp),Clock())
            with patch.object(FinishedThread,"is_alive",return_value=True):
                code,record=f.run()
            self.assertEqual(code,1)
            self.assertFalse(record["capturesClosed"])

    def test_final_receipt_or_directory_close_failure_refuses_pass_and_retires_all_owners(self):
        for kind in ("receipt", "directory"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                f = Fixture(Path(tmp), Clock())
                owner_type = f.Receipt if kind == "receipt" else f.Owner
                original = owner_type.close
                def fail(owner):
                    original(owner)
                    raise OSError("PRIVATE_CLOSE_ERROR")
                owner_type.close = fail
                code, record = f.run()
                self.assertEqual(code, 1)
                # The receipt cannot certify the later retirement of its writer.
                # Only an actual timely exit0 may make this candidate acceptable.
                self.assertEqual(record["status"], "PASS")
                self.assertTrue(f.receipt.closed and all(owner.closed for owner in f.owners))
                self.assertNotIn("PRIVATE", json.dumps(record))

    def test_late_receipt_write_or_close_cannot_reset_deadline(self):
        for operation in ("write", "close"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                clock = Clock()
                f = Fixture(Path(tmp), clock)
                original = getattr(f.Receipt, operation)
                def late(owner, *args):
                    result = original(owner, *args)
                    clock.value = 31500
                    return result
                setattr(f.Receipt, operation, late)
                with self.assertRaises(ValueError): f.run()
                self.assertTrue(f.receipt.closed and all(owner.closed for owner in f.owners))

    def test_late_public_flush_cannot_exit_success(self):
        clock = Clock()
        args = types.SimpleNamespace(worker=False, start_counter=1000, counter_frequency=1000)
        class LateOutput(io.StringIO):
            def flush(self):
                clock.value = 31500
        output = LateOutput()
        with patch.object(H, "arguments", return_value=args), patch.object(H, "Counter", return_value=clock), \
             patch.object(H, "arm_watchdog"), patch.object(H, "modules", return_value=(None, None, None)), \
             patch.object(H, "supervise", return_value=0), patch.object(H.sys, "stdout", output), \
             patch.object(H.os, "_exit") as final_exit:
            H.main([])
        self.assertEqual(output.getvalue(), "WINDOWS_INSTALLED_SUPERVISOR PASS\n")
        final_exit.assert_called_once_with(1)

    def test_native_source_binding_covers_the_actual_fixture_controller(self):
        with patch.object(H, "SOURCE_FILES", H.SOURCE_FILES), patch.object(H, "SCOPE", H.SCOPE), \
             patch.object(H, "modules", H.modules), patch.object(H, "worker_argv", H.worker_argv), \
             patch.object(H, "main") as main:
            native_controller(["--native", "normal", "--start-counter", "1000",
                               "--counter-frequency", "1000", "--private-parent", str(self.root)])
            identity = H.source_identity()
            self.assertIn(FIXTURE_SOURCE, identity)
            self.assertEqual(identity[FIXTURE_SOURCE], hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
            self.assertEqual(H.SCOPE, "SUPERVISOR_NATIVE_CONTROL_NOT_INSTALLED")
            main.assert_called_once()

    def test_fixed_native_outcomes_and_output_refusal_without_launching_processes(self):
        for case, actual, stdout, stderr, expected in (
                ("normal", outcome(), NORMAL_OUTPUT, b"", 0),
                ("normal", outcome(), b"WRONG\n", b"", 1),
                ("normal", outcome(), NORMAL_OUTPUT, b"UNEXPECTED\n", 1),
                ("nonzero", outcome(code="COMMAND_FAILED", exitCode=7), b"", b"", 1),
                ("output-overflow", outcome(code="OUTPUT_LIMIT", capturesClosed=False), b"x" * H.LOG_LIMIT, b"", 1)):
            with self.subTest(case=case, stdout=stdout[:16]), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                calls = []
                def command(argv, **options):
                    calls.append((argv, options))
                    options["private"].mkdir()
                    (options["private"] / "stdout.log").write_bytes(stdout)
                    (options["private"] / "stderr.log").write_bytes(stderr)
                    return actual
                E = types.SimpleNamespace(run_command=command, encoded=lambda value: json.dumps(value).encode(),
                                          write_private=lambda path, raw: path.write_bytes(raw))
                with patch.object(H, "modules", return_value=(None, E, None)):
                    self.assertEqual(native_worker(case, directory), expected)
                value = json.loads((directory / "worker.json").read_bytes())
                self.assertEqual(value["outcome"], actual)
                self.assertEqual(value["admissionMatched"], expected == 0)
                self.assertEqual(calls[0][0][:5], [sys.executable, "-I", "-B", "-S", "-c"])
                self.assertEqual(calls[0][1]["timeout"], 5)

    def test_observer_overflow_arms_original_watchdog_before_fixed_output_and_does_not_spawn(self):
        events = []
        clock = Clock()
        class Stopped(Exception):
            pass
        class Output:
            def write(self, raw):
                events.append(("write", len(raw)))
                self.raw = raw
                return len(raw)
            def flush(self):
                events.append("flush")
        output = Output()
        def stopped(seconds):
            if seconds == 2:
                clock.value += 2000
                return
            raise Stopped()
        args = ["--native", "observer-output-overflow", "--start-counter", "1000",
                "--counter-frequency", "1000", "--private-parent", str(self.root)]
        with patch.object(H, "Counter", return_value=clock), \
             patch.object(H, "arm_watchdog", side_effect=lambda deadline: events.append(("armed", deadline.end))), \
             patch.object(H, "modules") as modules, patch.object(H, "main") as main, \
             patch.object(sys, "stdout", types.SimpleNamespace(buffer=output)), patch.object(time, "sleep", stopped):
            with self.assertRaises(Stopped): native_controller(args)
            self.assertEqual(events, [("armed", 31000), ("write", 65537), "flush"])
            self.assertEqual(output.raw, b"x" * OBSERVER_OVERFLOW_BYTES)
            modules.assert_not_called()
            main.assert_not_called()
            events.clear()
            clock.value = 31000
            with self.assertRaises(ValueError): native_controller(args)
            self.assertEqual(events, [])

    def test_death_witness_retains_original_duplicate_and_waits_before_exit_code(self):
        clock = Clock()
        native, api, scope, witnesses = witness_model(clock)
        scope.api.identity(10, 1)
        scope.api.identity(10, 1)
        self.assertEqual(api.duplicates, [(10, 1010)])
        self.assertEqual(api.image_queries, [(1010, 0, 32768)])
        self.assertEqual(witnesses.evidence()[0]["imagePath"], r"C:\admitted\python.exe")
        witnesses.poll()
        self.assertFalse(witnesses.all_exited())
        self.assertEqual(api.exit_queries, [])
        api.live[1010] = False
        clock.value = 2000
        witnesses.poll()
        self.assertTrue(witnesses.all_exited())
        self.assertEqual(witnesses.evidence()[0]["exitCode"], 259)
        self.assertEqual(witnesses.evidence()[0]["exitObservedCounter"], 2000)
        witnesses.freeze()
        scope.api.identity(20, 2)
        self.assertEqual(len(witnesses.rows), 1)
        witnesses.close()
        witnesses.close()
        self.assertEqual(api.closes, [1010])
        self.assertTrue(witnesses.evidence()[0]["closed"])

    def test_death_witness_bound_and_failed_close_never_reopen_or_retry_original(self):
        native, api, scope, witnesses = witness_model(Clock())
        with patch.object(native.W, "MAX_WITNESSES", 1):
            scope.api.identity(10, 1)
            with self.assertRaises(ValueError): scope.api.identity(20, 2)
        self.assertEqual(api.duplicates, [(10, 1010)])
        def fail(handle):
            api.closes.append(handle)
            raise OSError("MODEL_CLOSE_FAILURE")
        api.close = fail
        with self.assertRaises(ValueError): witnesses.close()
        witnesses.close()
        self.assertEqual(api.closes, [1010])
        self.assertFalse(witnesses.evidence()[0]["closed"])

    def test_image_query_failure_or_invalid_length_retains_duplicate_for_close(self):
        for field, bad in (("image_ok", False), ("image_path", "python.exe"), ("image_path", ""),
                           ("image_length", 32768), ("image_length", 1)):
            with self.subTest(field=field, bad=bad):
                native, api, scope, witnesses = witness_model(Clock())
                setattr(api, field, bad)
                with self.assertRaises(ValueError): scope.api.identity(10, 1)
                self.assertEqual(api.image_queries, [(1010, 0, 32768)])
                self.assertEqual(len(witnesses.rows), 1)
                witnesses.freeze()
                witnesses.close()
                self.assertEqual(api.closes, [1010])

    def test_expected_python_images_cannot_be_replaced_by_console_helpers_or_same_basename(self):
        native, api, scope, witnesses = witness_model(Clock())
        python, powershell = r"C:\admitted\python.exe", r"C:\Program Files\PowerShell\7\pwsh.exe"
        for case, minimum in (("Normal", 4), ("Nonzero", 3), ("OutputOverflow", 3),
                              ("BlockedWorker", 2), ("BlockedOuter", 3), ("ObserverOutputOverflow", 1)):
            with self.subTest(case=case):
                root = {"pid": 1, "imagePath": powershell}
                children = [{"pid": index + 2, "imagePath": python} for index in range(minimum)]
                helper = {"pid": 100, "imagePath": r"C:\Windows\System32\conhost.exe"}
                self.assertEqual(len(native.validate_images([root, *children, helper], case, python, 1, powershell)), minimum)
                with self.assertRaises(ValueError):
                    native.validate_images([root, *children[:-1], helper], case, python, 1, powershell)
                impostor = {"pid": 101, "imagePath": r"C:\elsewhere\python.exe"}
                with self.assertRaises(ValueError):
                    native.validate_images([root, *children[:-1], impostor], case, python, 1, powershell)
                with self.assertRaises(ValueError):
                    native.validate_images([{**root, "imagePath": python}, *children], case, python, 1, powershell)

    def test_synthetic_e_overflow_reader_keeps_original_run_and_exact_byte_assertion(self):
        native, api, scope, witnesses = witness_model(Clock())
        for raw, failure in ((b"x" * 4096, False), (b"x" * 4095, True),
                             (b"y" * 4096, True), (b"x" * 4097, True)):
            with self.subTest(size=len(raw), first=raw[:1]), tempfile.TemporaryDirectory() as tmp:
                command = Path(tmp) / "run" / "command"
                command.mkdir(parents=True)
                (command / "stdout.log").write_bytes(raw)
                operations = []
                class Owner:
                    path = command.parent
                    closed = False
                    def __enter__(self):
                        operations.append("enter-run")
                        return self
                    def verify(self):
                        self.assert_open()
                        operations.append("verify-run")
                    def assert_open(self):
                        if self.closed:
                            raise AssertionError("original run closed during read")
                    def __exit__(self, kind, error, trace):
                        self.closed = True
                        operations.append("close-run")
                owner = Owner()
                def open_run(name, deadline):
                    self.assertEqual(name, "run")
                    return owner
                subject = types.SimpleNamespace(open_directory=open_run)
                original_read = native.H.read_bounded
                def bounded_read(path, maximum):
                    owner.assert_open()
                    self.assertEqual(path, command / "stdout.log")
                    self.assertEqual(maximum, 4096)
                    operations.append("read-synthetic")
                    return original_read(path, maximum)
                with patch.object(native.H, "read_bounded", bounded_read):
                    if failure:
                        with self.assertRaises(ValueError):
                            native.verify_e_overflow_evidence(subject, native.HarnessDeadline(Clock()))
                    else:
                        native.verify_e_overflow_evidence(subject, native.HarnessDeadline(Clock()))
                self.assertTrue(owner.closed)
                self.assertEqual(operations[0], "enter-run")
                self.assertEqual(operations[-1], "close-run")

    def test_synthetic_e_overflow_reader_rejects_late_read_or_original_close(self):
        native, api, scope, witnesses = witness_model(Clock())
        for late in ("read", "close"):
            with self.subTest(late=late):
                clock = Clock()
                class Owner:
                    path = self.root
                    closed = False
                    def __enter__(self): return self
                    def verify(self): pass
                    def __exit__(self, kind, error, trace):
                        self.closed = True
                        if late == "close": clock.value = 61000
                owner = Owner()
                subject = types.SimpleNamespace(open_directory=lambda *args, **kwargs: owner)
                def read(path, maximum):
                    if late == "read": clock.value = 61000
                    return b"x" * 4096
                with patch.object(native.H, "read_bounded", read), self.assertRaises(ValueError):
                    native.verify_e_overflow_evidence(subject, native.HarnessDeadline(clock))
                self.assertTrue(owner.closed)


def native_worker(case, directory):
    """Fixed harmless fixture only; no installed file, provider or app invocation."""
    A,E,F=H.modules()
    if case == "blocked-worker":
        # A synchronous call that never returns before the outer owner's cutoff.
        time.sleep(120)
        return 1
    code = {
        "normal": "import subprocess,sys; p=subprocess.Popen([sys.executable,'-I','-B','-S','-c','import time; time.sleep(2)']); result=p.wait(); sys.exit(result) if result else print('HARMLESS_NESTED_CHILD_PASS')",
        "nonzero": "import time,sys; time.sleep(2); sys.exit(7)",
        "output-overflow": "import time,sys; time.sleep(2); sys.stdout.write('x'*4097); sys.stdout.flush()",
        "blocked-outer": "import time; time.sleep(120)",
    }[case]
    # The inner E Job + outer controller Job exercise actual nested inheritance.
    actual=E.run_command([sys.executable,"-I","-B","-S","-c",code],cwd=ROOT,
        environment=dict(os.environ),private=directory/"command",timeout=120 if case=="blocked-outer" else 5,
        cleanup_seconds=2,log_limit=H.LOG_LIMIT)
    accepted = False
    if H.command_pass(actual):
        stdout = H.read_bounded(directory / "command/stdout.log", H.LOG_LIMIT)
        stderr = H.read_bounded(directory / "command/stderr.log", H.LOG_LIMIT)
        accepted = case == "normal" and not stderr and stdout in (NORMAL_OUTPUT, NORMAL_OUTPUT.replace(b"\n", b"\r\n"))
    H.write_new(E,directory/"worker.json",{"schema":1,"appSource":SOURCE,"operation":"admission",
        "outcome":actual,"admissionMatched":accepted})
    return 0 if accepted else 1


def native_controller(argv):
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--native",choices=NATIVE_CASES,required=True)
    parser.add_argument("--start-counter",required=True)
    parser.add_argument("--counter-frequency",required=True)
    parser.add_argument("--private-parent",required=True)
    args=parser.parse_args(argv)
    if args.native == "observer-output-overflow":
        options = H.arguments(["--start-counter", args.start_counter, "--counter-frequency", args.counter_frequency,
                               "--expected-source", SOURCE, "--private-parent", args.private_parent])
        deadline = H.Deadline(H.Counter(), options.start_counter, options.counter_frequency)
        H.arm_watchdog(deadline)
        # The witness harness must observe this original while it is alive.
        time.sleep(min(2.0, deadline.check()))
        deadline.check()
        # Fixed test-only outer-pipe overflow: no E worker, installed app or
        # child creation. The external original-handle observer must refuse it.
        sys.stdout.buffer.write(b"x" * OBSERVER_OVERFLOW_BYTES)
        sys.stdout.buffer.flush()
        while True:
            time.sleep(min(0.05, deadline.check()))
    H.SCOPE="SUPERVISOR_NATIVE_CONTROL_NOT_INSTALLED"
    H.SOURCE_FILES = (*H.SOURCE_FILES, FIXTURE_SOURCE)
    original_modules=H.modules
    def native_modules():
        A,E,F=original_modules()
        if args.native=="blocked-outer":
            original=A.WindowsScope.discover
            def blocked(self):
                original(self)
                time.sleep(120)
                return []
            A.WindowsScope.discover=blocked
        return A,E,F
    H.modules=native_modules
    H.worker_argv=lambda options,directory:[sys.executable,"-I","-B","-S",str(Path(__file__).resolve()),
        "--fixture-worker",args.native,str(directory)]
    H.main(["--start-counter",args.start_counter,"--counter-frequency",args.counter_frequency,
            "--expected-source",SOURCE,"--private-parent",args.private_parent])


if __name__ == "__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--fixture-worker":
        require = H.require
        require(len(sys.argv)==4 and sys.argv[2] in WORKER_CASES)
        os._exit(native_worker(sys.argv[2],Path(sys.argv[3])))
    elif "--native" in sys.argv:
        native_controller(sys.argv[1:])
    else:
        unittest.main(failfast=True)
