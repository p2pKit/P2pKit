#!/usr/bin/env python3
"""Fixed-file provider readback controls, not a provider or hosted execution.

The real Owner definition and POSIX private-file reader use tiny owned files.
ACKs, native descriptions, clocks, admissions and provider captures are explicit
models. No original provider/native-process evidence is manufactured or reused.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import hosted_cache_provider_readback as R

L, T, O = R.launch, R.launch.transport, R.outer
spec = importlib.util.spec_from_file_location("readback_plan_fixtures",
    SCRIPTS / "tests/hosted-cache-provider-contract-test.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

# Only the maintained file Owner and its LIMIT constant, not the 13k-line
# controller or held Stage1 receiver, execute. The clock/fence remains modeled.
tree = ast.parse((SCRIPTS / "run-hosted-cache-bootstrap.py").read_text())
selected = [node for node in tree.body if (isinstance(node, ast.ClassDef) and node.name == "Owner") or
            (isinstance(node, ast.Assign) and len(node.targets) == 1 and
             isinstance(node.targets[0], ast.Name) and node.targets[0].id == "LIMIT")]
assert len(selected) == 2
owner_code = compile(ast.Module(body=selected, type_ignores=[]), "selected-Owner", "exec")
owner_globals = {"require": L.require, "math": math, "time": time, "os": os, "query": L.files,
    "posix": L.files.posix_files, "windows": L.files.windows_files, "QUARANTINE": [],
    "origin": NS(clocks=L.clocks, OriginError=L.ProviderLaunchError),
    "diagnostics": NS(_exception_detail=lambda error: {"retirementUnknown": False, "model": type(error).__name__})}
exec(owner_code, owner_globals)
Owner = owner_globals["Owner"]


class Fixture:
    """Small synthetic original graph; no test from the borrowed fixture runs."""
    def __init__(self, case, phase="save"):
        self.case = case
        self.plan_case = C.ProviderContract()
        self.plan_case.setUp()
        case.addCleanup(self.plan_case.doCleanups)
        self.plan = self.plan_case.plan
        self.tmp = tempfile.TemporaryDirectory(prefix="provider-readback-model-")
        case.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.path.chmod(0o700)
        home = self.path / "home"
        home.mkdir(mode=0o700)
        self.local_end = time.monotonic() + 20
        self.raw = 245 * L.clocks.NS
        self.clock = L.clocks.ClockIdentity("linux-x64", L.clocks.DOMAINS["linux-x64"], L.clocks.NS)
        reading = L.clocks.Reading(self.clock, self.raw)
        self.fence = NS(clock=self.clock, deadline=lambda *args, **kw: self.local_end, now=lambda **kw: self.raw)
        self.owner = Owner(self.local_end, self.fence, first=reading)
        case.addCleanup(self.close)
        self.directory = self.owner.open(self.path)
        native = patch.object(L.clocks, "observe", lambda: L.clocks.Reading(self.clock, self.raw))
        native.start()
        case.addCleanup(native.stop)
        info = home.stat()
        self.context = {"schema": "P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1", "role": "linux-x64",
            "frequency": L.clocks.NS, "firstNs": str(105 * L.clocks.NS), "issuedNs": str(100 * L.clocks.NS),
            "hardEndNs": str(280 * L.clocks.NS), "workerCutoffNs": str(250 * L.clocks.NS), "phase": phase,
            "job": "1" * 32, "outerId": "2" * 32, "innerId": "3" * 32,
            "directory": str(self.path), "directoryIdentity": list(self.directory.identity),
            "home": str(home), "homeIdentity": [info.st_dev, info.st_ino],
            "node": "/modeled-tools/node", "toolPath": "/modeled-tools", "plan": self.plan}
        self.request = T._json(self.context)
        self.frame = {key: value for key, value in self.context.items() if key not in ("schema", "firstNs")}
        self.frame.update(schema=1, captureIdentity=[info.st_dev, info.st_ino + 1000], systemRoot=None,
            prefix=[[self.context["outerId"], self.context["job"], str(self.path), str(home)]])
        self.worker_request = T._json(self.frame)
        self.bindings = {name: hashlib.sha256(("MODEL_SOURCE_" + name).encode()).hexdigest()
                         for name in L.worker_source.outer_names("linux-x64")}
        self.python = str(Path(sys.executable))
        self.argv = [self.python, "-I", "-B", "-S", str(SCRIPTS / "hosted_cache_provider_worker.py"),
            L._json({name: self.bindings[name] for name in L.worker_source.names("linux-x64")}),
            self.worker_request.decode("ascii")]
        self.native = {"backend": "linux-proc-pidfd", "job": self.context["job"],
            "invocation": self.context["outerId"], "discoveryErrors": [],
            "launches": [{"api": "subprocess.Popen", "created": True, "pid": 123,
                "cwd": str(SCRIPTS.parent), "outputMode": "caller-owned-files", "shell": False,
                "executable": self.python, "requestedArgv": self.argv[:], "resolvedArgv": self.argv[:]}]}
        self.capture = {"phase": phase, "exit_code": 0, "command": b"", "stdout": b"MODEL_PRIVATE_STDOUT\x00\xff",
            "stderr": b"", "native_retirement": b'{"MODEL":"NOT_NATIVE_EXECUTION"}\n',
            "outputs": (), "observed_ns": 230 * L.clocks.NS,
            "closed_resources": L.lifecycle.ProviderCapture._NAMES}
        if phase == "lookup":
            outputs = {"cache-primary-key": self.plan["key"], "cache-matched-key": self.plan["key"], "cache-hit": "true"}
            self.capture["outputs"] = tuple(sorted(outputs.items()))
            self.capture["command"] = self.command(outputs)
        self.originals = {}
        self.refresh()

    @staticmethod
    def command(outputs):
        delimiter = "ghadelimiter_00000000-0000-4000-8000-000000000000"
        return "".join(name + "<<" + delimiter + "\n" + value + "\n" + delimiter + "\n"
                       for name, value in sorted(outputs.items())).encode("ascii")

    def close(self):
        # Dispose only test-owned tiny resources, never a real native domain.
        self.raw = 245 * L.clocks.NS
        try:
            self.owner.close()
        except L.ProviderLaunchError:
            if not self.owner.unknown:
                raise
        for row in reversed(self.owner.resources):
            if not row["closed"]:
                row["owner"].close()  # Fixture disposal, not candidate UNKNOWN recovery.
        owner_globals["QUARANTINE"].clear()

    def write(self, slot, raw):
        name = {"native": O.NATIVE_NAME, "stdout": "provider-stdout.log", "stderr": "provider-stderr.log",
                "packet": T.PACKET_NAME}[slot]
        path = self.path / name
        path.write_bytes(raw)
        path.chmod(0o600)
        self.originals[slot] = raw
        info = path.stat()
        return O.FileReference(len(raw), hashlib.sha256(raw).hexdigest(), (info.st_dev, info.st_ino))

    def refresh(self):
        packet = T.encode(L.lifecycle.CapturedProvider(**self.capture), self.worker_request)
        packet_ref = self.write("packet", packet)
        self.write("stdout", T.acknowledge(packet, packet_ref.identity, self.worker_request))
        self.write("stderr", b"")
        self.write("native", T._json(self.native) + b"\n")
        self.reack()

    def reack(self):
        self.refs = tuple(self.write(slot, self.originals[slot]) for slot in ("native", "stdout", "stderr", "packet"))
        transcript = NS(failed=False, worker_exit_code=0, provider_return=NS(kind="success"),
            observed_ns=240 * L.clocks.NS,
            closed_resources=("scope", "retirement-writer", "stdout-reader", "stderr-reader", "packet-reader",
                              "stderr", "stdout", "bundle", "capture_directory", "home", "directory"))
        self.ack = O.acknowledge(self.request, self.worker_request, transcript, self.refs)

    def run(self):
        return R.read_success(self.owner, self.directory, self.request, self.ack, 0,
                              python=self.python, bindings=self.bindings)


class ReadbackControls(unittest.TestCase):
    def setUp(self):
        self.model = Fixture(self)

    def test_save_reads_all_actual_fixed_files_but_keeps_enclosing_acceptance_pending(self):
        value = self.model.run()
        self.assertEqual(value.provider.outputs, ())
        self.assertEqual(dict(value.originals), self.model.originals)
        self.assertEqual(value.worker_request, self.model.worker_request)
        self.assertEqual(value.checked_ns, self.model.raw)
        self.assertEqual((value.enclosing_owner_close, value.original_action_outcome, value.provider_acceptance),
                         ("NOT_OBSERVED", "NOT_OBSERVED", "NOT_ESTABLISHED"))
        self.assertNotIn("MODEL_PRIVATE", repr(value))
        self.assertFalse(self.model.owner.closed)
        self.assertTrue(all(row["closed"] for row in self.model.owner.resources[1:]))
        with self.assertRaises(FrozenInstanceError):
            value.checked_ns = 1

    def test_lookup_recovers_checked_exact_fields_without_claiming_contents_or_reuse(self):
        model = Fixture(self, "lookup")
        value = model.run()
        self.assertEqual(dict(value.provider.outputs), {"cache-primary-key": model.plan["key"],
            "cache-matched-key": model.plan["key"], "cache-hit": "true"})
        self.assertEqual(value.provider.provider_acceptance, "NOT_ESTABLISHED")

    def test_failed_incomplete_boolean_or_missing_exit_cannot_start_readback(self):
        model = self.model
        with patch.object(L.files, "_posix_stream") as opened:
            for code in (65, 66, 1, True, None):
                with self.subTest(code=code), self.assertRaises(T.ProviderReturnError):
                    R.read_success(model.owner, model.directory, model.request, model.ack, code,
                                   python=model.python, bindings=model.bindings)
            changed = json.loads(model.ack)
            changed.update(kind="failed", providerKind="failed", workerExitCode=65)
            with self.assertRaisesRegex(L.ProviderLaunchError, "SUCCESS_REQUIRED"):
                R.read_success(model.owner, model.directory, model.request, T._json(changed) + b"\n", 65,
                               python=model.python, bindings=model.bindings)
            opened.assert_not_called()

    def test_same_bytes_on_replacement_inode_do_not_match_original_ack(self):
        path = self.model.path / O.NATIVE_NAME
        displaced = path.with_name("displaced-original.json")
        path.rename(displaced)
        path.write_bytes(displaced.read_bytes())
        path.chmod(0o600)
        with self.assertRaisesRegex(L.ProviderLaunchError, "FILE_REPLACED"):
            self.model.run()

    def test_changed_bytes_on_same_inode_do_not_match_original_ack(self):
        path = self.model.path / O.NATIVE_NAME
        data = path.read_bytes()
        path.write_bytes(data.replace(b'"linux-proc-pidfd"', b'"bogus-proc-pidfd"'))
        with self.assertRaisesRegex(L.ProviderLaunchError, "FILE_CHANGED"):
            self.model.run()

    def test_missing_file_retains_failure_instead_of_returning_a_partial_success(self):
        (self.model.path / O.NATIVE_NAME).unlink()
        with self.assertRaises(FileNotFoundError):
            self.model.run()
        self.assertTrue(self.model.owner.unknown)

    def test_symlink_is_refused_without_following_its_target(self):
        path = self.model.path / O.NATIVE_NAME
        original = path.with_name("original-model.json")
        path.rename(original)
        path.symlink_to(original)
        with self.assertRaises(OSError):
            self.model.run()

    def test_fifo_is_refused_nonblocking(self):
        path = self.model.path / O.NATIVE_NAME
        path.unlink()
        os.mkfifo(path, 0o600)
        with self.assertRaises(L.files.QueryError):
            self.model.run()

    def test_public_mode_file_is_not_private_evidence(self):
        (self.model.path / O.NATIVE_NAME).chmod(0o644)
        with self.assertRaises(L.files.QueryError):
            self.model.run()

    def test_native_launch_fields_must_bind_fixed_worker_and_source(self):
        model = self.model
        for field, bad in (("api", "shell"), ("created", False), ("pid", True), ("cwd", "/elsewhere"),
                           ("outputMode", "pipe"), ("shell", True), ("executable", "/elsewhere/python")):
            value = deepcopy(model.native)
            value["launches"][0][field] = bad
            with self.subTest(field=field), self.assertRaises(L.ProviderLaunchError):
                R._worker_request(T._json(value), model.request, O.read_ack(model.ack, model.request, 0),
                                  model.python, model.bindings)

    def test_changed_resolved_argv_or_source_roster_cannot_reinterpret_native_file(self):
        model = self.model
        original = O.read_ack(model.ack, model.request, 0)
        value = deepcopy(model.native)
        value["launches"][0]["resolvedArgv"][1] = "-c"
        with self.assertRaisesRegex(L.ProviderLaunchError, "NATIVE_LAUNCH"):
            R._worker_request(T._json(value), model.request, original, model.python, model.bindings)
        for bindings in ({}, {**model.bindings, "extra": "a" * 64},
                         {**model.bindings, "audit_processes": "a" * 64}):
            with self.assertRaisesRegex(L.ProviderLaunchError, "SOURCE_"):
                R._worker_request(model.originals["native"], model.request, original, model.python, bindings)

    def test_native_record_role_job_invocation_and_discovery_errors_are_bound(self):
        model = self.model
        ack = O.read_ack(model.ack, model.request, 0)
        for name, value in (("backend", "windows-job-list-suspended"), ("job", "f" * 32),
                            ("invocation", "f" * 32), ("discoveryErrors", ["MODEL_ERROR"]), ("launches", [])):
            with self.subTest(name=name), self.assertRaisesRegex(L.ProviderLaunchError, "NATIVE_RECORD"):
                R._worker_request(T._json({**model.native, name: value}), model.request, ack,
                                  model.python, model.bindings)

    def test_exact_native_request_token_must_match_outer_ack(self):
        model = self.model
        value = deepcopy(model.native)
        changed = T._json({**model.frame, "captureIdentity": [1, 987654321]}).decode("ascii")
        value["launches"][0]["requestedArgv"][-1] = changed
        value["launches"][0]["resolvedArgv"][-1] = changed
        with self.assertRaisesRegex(L.ProviderLaunchError, "WORKER_REQUEST"):
            R._worker_request(T._json(value), model.request, O.read_ack(model.ack, model.request, 0),
                              model.python, model.bindings)

    def test_worker_ack_packet_reference_must_match_outer_native_file_reference(self):
        model = self.model
        value = json.loads(model.originals["stdout"])
        value["packetIdentity"] = [1, 987654321]
        model.originals["stdout"] = T._json(value) + b"\n"
        model.reack()
        with self.assertRaisesRegex(L.ProviderLaunchError, "PACKET_BINDING"):
            model.run()

    def test_invalid_captured_command_cannot_become_checked_outputs(self):
        model = self.model
        value = json.loads(model.originals["packet"])
        value["outputs"] = [["cache-hit", "true"]]
        packet = T._json(value) + b"\n"
        reference = model.write("packet", packet)
        model.originals["stdout"] = T.acknowledge(packet, reference.identity, model.worker_request)
        model.reack()
        with self.assertRaisesRegex(T.ProviderReturnError, "OUTPUTS_CHANGED"):
            model.run()

    def test_provider_observation_cannot_follow_outer_observation(self):
        model = self.model
        model.capture["observed_ns"] = 241 * L.clocks.NS
        model.refresh()
        with self.assertRaisesRegex(L.ProviderLaunchError, "PROVIDER_RETURN"):
            model.run()

    def test_wrong_clock_or_pre_ack_readback_never_opens_files(self):
        model = self.model
        for reading in (L.clocks.Reading(model.clock, 239 * L.clocks.NS),
                        L.clocks.Reading(L.clocks.ClockIdentity("macos-arm64", L.clocks.DOMAINS["macos-arm64"],
                                                             L.clocks.NS), 245 * L.clocks.NS)):
            model.owner.first = reading
            with patch.object(L.files, "_posix_stream") as opened:
                with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_OWNER"):
                    model.run()
                opened.assert_not_called()

    def test_expiry_after_original_file_close_still_refuses(self):
        model = self.model
        original = model.owner.close_one
        def close(value):
            original(value)
            model.raw = 280 * L.clocks.NS
        model.owner.close_one = close
        with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_END"):
            model.run()

    def test_cancelled_or_closed_owner_never_opens_files(self):
        model = self.model
        def cancelled():
            raise KeyboardInterrupt("MODEL_CANCELLATION")
        model.owner.cancelled = cancelled
        with patch.object(L.files, "_posix_stream") as opened:
            with self.assertRaises(KeyboardInterrupt):
                model.run()
            model.owner.cancelled = lambda: None
            model.owner.close()
            with self.assertRaisesRegex(L.ProviderLaunchError, "OWNER_CHANGED"):
                model.run()
            opened.assert_not_called()

    def test_unknown_owner_never_opens_files(self):
        model = self.model
        model.owner.unknown = True
        with patch.object(L.files, "_posix_stream") as opened:
            with self.assertRaisesRegex(L.ProviderLaunchError, "OWNER_CHANGED"):
                model.run()
            opened.assert_not_called()

    def test_cancellation_callback_cannot_replace_owner_fence_before_acquisition(self):
        model = self.model
        model.owner.cancelled = lambda: setattr(model.owner, "fence", NS(deadline=lambda *a, **kw: model.local_end))
        with patch.object(L.files, "_posix_stream") as opened:
            with self.assertRaisesRegex(L.ProviderLaunchError, "OWNER_CHANGED"):
                model.run()
            opened.assert_not_called()
        model.owner.fence = model.fence  # Model fixture disposal only.

    def test_cancellation_callback_cannot_replace_source_bindings_before_acquisition(self):
        model = self.model
        model.owner.cancelled = lambda: model.bindings.update(audit_processes="0" * 64)
        with patch.object(L.files, "_posix_stream") as opened:
            with self.assertRaisesRegex(L.ProviderLaunchError, "INPUT_CHANGED"):
                model.run()
            opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
