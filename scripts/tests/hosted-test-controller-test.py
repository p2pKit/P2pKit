#!/usr/bin/env python3
"""Offline composition models. NO real Git/native owner/GPG/Gradle/CI execution.

Only synthetic private POSIX fixture files are created. Orchestration children
and native methods are modeled. Fresh isolated Python import probes block the
canonical main, all native APIs and further process execution; those small child
interpreters do not execute products or claim genuine host/crypto proof.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("ordinary_controller_models", ROOT / "scripts/run-hosted-test-custody.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)
JOB_SPEC = importlib.util.spec_from_file_location("ordinary_job_time_model_fixtures",
    ROOT / "scripts/tests/hosted-full-job-budget-test.py")
JOB_MODELS = importlib.util.module_from_spec(JOB_SPEC)
JOB_SPEC.loader.exec_module(JOB_MODELS)


class Clock:
    def __init__(self):
        self.now = 100.
        self.raw_offset = 0

    def monotonic(self):
        return self.now

    def sleep(self, value):
        self.now += value

    def raw(self):
        return int((10000 + self.now) * C.job_time.NS) + self.raw_offset

    def set_raw(self, value):
        self.raw_offset = value - int((10000 + self.now) * C.job_time.NS)


class Scope:
    """Native owner substitute; no child or OS process API is ever called."""
    def __init__(self, case, job, invocation, state, home):
        self.case, self.job, self.invocation = case, job, invocation
        self.state, self.home, self.baseline = state, home, {(10, 20)}
        self.launches = []
        self.event_start = len(case.events)
        case.events.append("scope")
        if case.constructor_error:
            raise case.constructor_error

    def spawn(self, argv, cwd, environment, *, stdout, stderr):
        self.case.events.append("spawn")
        self.pid = 1000 + len(self.case.calls)
        self.case.calls.append({"argv": argv, "cwd": cwd, "environment": dict(environment),
                                "stdout": stdout, "stderr": stderr, "pid": self.pid})
        if self.case.spawn_error:
            raise self.case.spawn_error
        out, err = (self.case.model_output(argv, stdout.path.parent.name) if hasattr(self.case, "model_output")
                    else (self.case.stdout, self.case.stderr))
        os.write(stdout.fileno(), out)
        os.write(stderr.fileno(), err)
        self.launches.append({"argv": argv, "requestedArgv": argv, "api": "subprocess.Popen", "shell": False,
                              "cwd": cwd, "created": True, "pid": self.pid, "outputMode": "OFFLINE_SUPPLIED_FILES"})
        if self.case.after_launch:
            self.case.after_launch()
        if getattr(self.case, "model_child", None):
            self.case.model_child(argv, environment)
        return SimpleNamespace(pid=self.pid, stdout=None, stderr=None, poll=self.poll)

    def poll(self):
        self.case.events.append("poll")
        if self.case.poll_error:
            raise self.case.poll_error
        return self.case.poll_function() if self.case.poll_function else self.case.exit_code

    def discover(self):
        self.case.events.append("discover")
        if self.case.discovery_error:
            raise self.case.discovery_error
        return []

    def drain(self, *, grace, kill_wait):
        self.case.events.append("drain")
        if self.case.drain_error:
            raise self.case.drain_error
        return self.case.survivors

    def description(self):
        return {"backend": "darwin-libproc-audit-token", "scope": "controlled-marker-inheriting-descendants",
                "job": self.job, "invocation": self.invocation, "launches": self.launches,
                "startedIdentities": [model_identity(row["pid"]) for row in self.launches],
                "discoveryErrors": self.case.discovery_errors}

    def close(self):
        self.case.events.append("scope-close")
        if self.case.close_error:
            raise self.case.close_error


def model_identity(pid):
    return {"pid": pid, "uniqueId": pid + 10000, "startSeconds": 100, "startMicroseconds": 0, "pidVersion": 1}


def model_canonical_start(binding, ancestors, pid):
    return {"schema": 1, "id": binding["productInvocation"], "purpose": "ordinary-full", "kind": "command",
        "requestedArgv": ["python3", "scripts/run-platform-tests.py", "full"], "cwd": binding["root"],
        "wrapper": binding["root"] + "/gradlew", "host": binding["role"], "jobId": binding["job"],
        "gradleHome": binding["home"], "startedUtc": "2026-09-16T00:00:00Z", "controllerPid": pid,
        "ancestorInvocationIds": ancestors, "sourceBefore": None, "sourceAfter": None, "productExitCode": None,
        "stopExitCode": None, "finalExitCode": 125, "sourceUnchanged": False, "ownedSurvivors": [], "errors": [],
        "evidenceDirectory": binding["state"] + "/evidence/" + binding["productInvocation"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="controller-model-", dir=ROOT.parent)
        self.path = Path(self.temp.name)
        self.root = self.path / "source"
        self.root.mkdir(mode=0o700)
        (self.root / "scripts").mkdir(mode=0o700)
        for name in ("audit_processes.py", "run-audit-command.py"):
            (self.root / "scripts" / name).write_bytes((ROOT / "scripts" / name).read_bytes())
        self.runner_temp = self.path / "runner-temp"
        self.runner_temp.mkdir(mode=0o700)
        self.clock = Clock()
        self.events, self.calls, self.owners = [], [], []
        self.exit_code, self.stdout, self.stderr = 0, b"synthetic-private-stdout\x00\xff\n", b"synthetic-private-stderr\n"
        self.constructor_error = self.spawn_error = self.poll_error = self.discovery_error = None
        self.drain_error = self.close_error = self.poll_function = self.after_launch = None
        self.survivors, self.discovery_errors = [], []
        self.stack = ExitStack()
        self.stack.enter_context(patch.dict(os.environ, {"RUNNER_TEMP": str(self.runner_temp), "GITHUB_RUN_ID": "123",
             "GITHUB_RUN_ATTEMPT": "1", "JAVA_HOME": "/synthetic/jdk17", "P2PKIT_AUDIT_JDK21": "/synthetic/jdk21",
             "PATH": "/synthetic/bin", "RUNNER_NAME": JOB_MODELS.RUNNER}, clear=True))
        self.stack.enter_context(patch.object(C, "ROOT", self.root))
        self.stack.enter_context(patch.object(C, "SCRIPTS", self.root / "scripts"))
        self.stack.enter_context(patch.object(C.processes, "host_role", return_value="macos-arm64"))
        self.stack.enter_context(patch.object(C.processes, "make_scope", side_effect=lambda *a: Scope(self, *a)))
        self.stack.enter_context(patch.object(C.processes.subprocess, "Popen", side_effect=AssertionError("NO_REAL_PROCESS")))
        self.stack.enter_context(patch.object(C.processes.ctypes, "CDLL", side_effect=AssertionError("NO_NATIVE_API")))
        self.stack.enter_context(patch.object(C.time, "monotonic", side_effect=self.clock.monotonic))
        self.stack.enter_context(patch.object(C.time, "sleep", side_effect=self.clock.sleep))
        self.stack.enter_context(patch.object(C.job_time, "shared_raw_ns", side_effect=self.clock.raw))
        self.stack.enter_context(patch.object(C.job_time.http.client, "HTTPSConnection", side_effect=AssertionError("NO_HTTP")))
        self.stack.enter_context(patch.object(C.job_time.ssl, "create_default_context", side_effect=AssertionError("NO_TLS")))
        self.stack.enter_context(patch.object(socket, "socket", side_effect=AssertionError("NO_SOCKET")))
        self.stack.enter_context(patch.object(socket, "create_connection", side_effect=AssertionError("NO_SOCKET")))
        self.stack.enter_context(patch.object(C.signal, "getsignal", return_value="MODEL_PREVIOUS_HANDLER"))
        self.stack.enter_context(patch.object(C.signal, "signal", return_value="MODEL_PREVIOUS_HANDLER"))
        self.stack.enter_context(patch.object(C.query, "NativeGitQueries", side_effect=AssertionError("NO_UNMODELED_QUERY")))
        self.stack.enter_context(patch.object(C.posix, "validate_recipient", side_effect=AssertionError("NO_GPG")))
        self.stack.enter_context(patch.object(C.windows, "validate_recipient", side_effect=AssertionError("NO_GPG")))
        self.stack.enter_context(patch.object(C.ordinary, "export_encrypted", side_effect=AssertionError("NO_GPG")))
        self.stack.enter_context(patch.object(C.windows, "export_test_encrypted", side_effect=AssertionError("NO_GPG")))
        self.quarantines = [(value, list(value)) for value in (C.QUARANTINE, C.query.QUARANTINE, C.windows._QUARANTINE)]

    def tearDown(self):
        # Only model-native workers existed. Disposing synthetic fixture streams
        # after UNKNOWN assertions is NOT a production quarantine recovery API.
        for owner in [*self.owners, *getattr(self, "crypto_owners", [])]:
            for row in reversed(owner.resources):
                resource = row["owner"]
                if isinstance(resource, (C.query._PosixDirectory, C.query._PosixSink)):
                    try:
                        resource.close()
                    except BaseException:
                        pass
        for target, before in self.quarantines:
            target[:] = before
        self.stack.close()
        self.temp.cleanup()

    def controller(self, profile="desktop"):
        value = C.Controller(profile)
        self.owners.append(value)
        value.allocate()
        return value

    def owner(self):
        value = C.PrivateOwner()
        self.owners.append(value)
        return value

    def private(self, owner, name):
        return owner.new(self.path / name)

    def set_file(self, directory, name, value):
        path = directory.path / name
        raw = value if type(value) is bytes else C.encoded(value)
        with path.open("xb") as stream:
            stream.write(raw)
        path.chmod(0o600)
        return raw


class ContractModels(Base):
    def test_closed_commands_keep_all_six_tasks_and_host_installer(self):
        for role, installer in C.INSTALLERS.items():
            kind, command = C.profile_command("desktop", role)
            self.assertEqual(kind, "gradle")
            self.assertEqual(command[:6], list(C.DESKTOP_TASKS))
            self.assertEqual(command[-2:], [installer, "--console=plain"])
            self.assertEqual(":p2p-sample-android:assembleDebug" in command, role == "linux-x64")
        self.assertEqual(C.profile_command("full", "macos-arm64"),
                         ("command", ["python3", "scripts/run-platform-tests.py", "full"]))
        for profile, role in (("arbitrary", "macos-arm64"), ("full", "linux-x64"), ("desktop", "linux-arm64")):
            with self.assertRaises(C.ControllerError):
                C.profile_command(profile, role)

    def test_windows_original_capture_envelope_stays_below_900_without_renewal(self):
        self.assertEqual(C.PRODUCT_SECONDS["desktop"], 600)
        self.assertEqual(C.OUTER_SECONDS["desktop"], 825)
        self.assertLess(C.OUTER_SECONDS["desktop"] + C.FINAL_SECONDS, C.files.MAX_SECONDS)
        self.assertEqual(C.files.MAX_SECONDS, 900)

    def test_credential_environment_not_inherited_and_overrides_fail(self):
        base = dict(os.environ, GITHUB_TOKEN="synthetic-token", AWS_SECRET_ACCESS_KEY="synthetic-secret")
        result = C.child_environment(base, self.path, self.path / "state")
        self.assertNotIn("GITHUB_TOKEN", result)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", result)
        for name in ("JAVA_OPTS", "LD_PRELOAD", "ORG_GRADLE_PROJECT_secret", "GIT_CONFIG_COUNT"):
            with self.subTest(name=name), self.assertRaises(C.ControllerError):
                C.child_environment(dict(base, **{name: "synthetic-override"}), self.path, self.path / "state")

    def test_genuine_inherited_context_is_preserved_not_replaced(self):
        env = C.processes.ownership_environment(dict(os.environ), "a" * 32, "b" * 32,
                                               "/synthetic/parent", "/synthetic/parent/home")
        with patch.dict(os.environ, env, clear=True):
            result = C.child_environment(env, self.path, self.path / "state")
        for name in C.query._CONTEXT:
            self.assertEqual(result[name], env[name])

    def test_query_constructor_unknown_propagates_without_returned_owner(self):
        owner = self.owner()
        def fail(*args, **kwargs):
            C.query.QUARANTINE.append(object())
            raise C.query.QueryError("ALLOCATION_HOLD")
        with patch.object(C.query, "NativeGitQueries", side_effect=fail), self.assertRaises(C.query.QueryError):
            C.admission(owner, "desktop", self.path / "query", lambda: None)
        self.assertTrue(owner.unknown)
        with self.assertRaises(C.ControllerError):
            owner.close()
        self.assertIn(owner, C.QUARANTINE)

    def test_allocated_query_is_finalized_when_pre_entry_cancelled(self):
        supplier = SimpleNamespace(unknown=False)
        calls = []
        supplier._finalize = lambda original: calls.append(original)
        with patch.object(C.query, "NativeGitQueries", return_value=supplier), self.assertRaises(KeyboardInterrupt):
            C.admission(self.owner(), "desktop", self.path / "query", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(calls[0], KeyboardInterrupt)

    def test_full_rejects_path_python_other_than_admitted_native_interpreter(self):
        controller = self.controller("full")
        with patch.object(controller, "allocate"), patch.object(C, "admission", return_value=SimpleNamespace()), \
                patch.object(C.shutil, "which", return_value="/no/such/python3"), \
                self.assertRaises((C.ControllerError, FileNotFoundError)):
            controller.setup()
        self.assertEqual(self.calls, [])

    def test_abi_query_constructor_unknown_blocks_without_a_returned_owner(self):
        owner = self.owner()
        def failed(*args, **kwargs):
            C.query.QUARANTINE.append(object())
            raise C.query.QueryError("ABI_ALLOCATION_UNKNOWN")
        with patch.object(C.query, "NativeGitQueries", side_effect=failed), self.assertRaises(C.query.QueryError):
            C.abi_references(owner, "a" * 40, self.path / "query", 200., lambda: None)
        self.assertTrue(owner.unknown)
        self.assertEqual(self.calls, [])

    def test_abi_query_returned_allocation_is_finalized_before_entry_cancellation(self):
        owner, calls = self.owner(), []
        error = KeyboardInterrupt("ABI_PREENTRY_CANCEL")
        supplier = SimpleNamespace(unknown=False, _finalize=lambda original: calls.append(original))
        def cancelled():
            raise error
        with patch.object(C.query, "NativeGitQueries", return_value=supplier), self.assertRaises(KeyboardInterrupt) as seen:
            C.abi_references(owner, "a" * 40, self.path / "query", 200., cancelled)
        self.assertIs(seen.exception, error)
        self.assertEqual(calls, [error])
        self.assertFalse(owner.unknown)

    def test_abi_query_late_finalizer_failure_preserves_original_before_return(self):
        owner, calls = self.owner(), []
        original = KeyboardInterrupt("ORIGINAL_ABI_CANCEL")
        def finalize(error):
            calls.append(error)
            raise OSError("SECONDARY_ABI_FINALIZER")
        supplier = SimpleNamespace(unknown=True, _finalize=finalize)
        with patch.object(C.query, "NativeGitQueries", return_value=supplier), self.assertRaises(KeyboardInterrupt) as seen:
            C.abi_references(owner, "a" * 40, self.path / "query", 200., lambda: (_ for _ in ()).throw(original))
        self.assertIs(seen.exception, original)
        self.assertEqual(calls, [original])
        self.assertTrue(owner.unknown)


class PhaseModels(Base):
    def test_success_privately_captures_both_streams_then_drains_closes_and_receipts(self):
        controller = self.controller()
        row = controller.phase("audit-init", ["synthetic-python", "synthetic-init"], 120)
        self.assertEqual(row["exitCode"], 0)
        self.assertEqual(row["retirement"], "KNOWN")
        self.assertLess(self.events.index("drain"), self.events.index("scope-close"))
        target = controller.commands.path / "audit-init"
        self.assertEqual((target / "stdout.log").read_bytes(), self.stdout)
        self.assertEqual((target / "stderr.log").read_bytes(), self.stderr)
        raw = (target / "result.json").read_bytes()
        self.assertEqual(C.parse(raw), row)
        self.assertEqual(controller.phase_hashes["audit-init"], C.digest(raw))
        env = self.calls[0]["environment"]
        domain = C.processes.ownership_domains(env[C.processes.CHAIN_ENV], env[C.processes.DOMAINS_ENV])[-1]
        self.assertEqual(domain["job"], controller.job)
        self.assertEqual(domain["state"], str(controller.path))
        controller.close()
        self.assertTrue(all(row["closed"] for row in controller.resources))

    def test_nonzero_exit_is_retained_known_not_implicitly_passed(self):
        self.exit_code = 23
        controller = self.controller()
        row = controller.phase("product", ["model-product"], 120)
        self.assertEqual(row["exitCode"], 23)
        self.assertEqual(row["retirement"], "KNOWN")
        self.assertEqual(controller.errors, [])

    def test_constructor_failure_is_sticky_unknown_and_sinks_stay_pinned(self):
        self.constructor_error = RuntimeError("model constructor")
        controller = self.controller()
        with self.assertRaisesRegex(RuntimeError, "constructor"):
            controller.phase("product", ["model-product"], 120)
        self.assertTrue(controller.unknown)
        sinks = [row for row in controller.resources if row["label"].startswith("phase-")]
        self.assertEqual(len(sinks), 2)
        self.assertTrue(all(not row["attempted"] for row in sinks))
        with self.assertRaises(C.ControllerError):
            controller.phase("export", ["must-not-launch"], 120, finalizing=True)
        self.assertNotIn("spawn", self.events)

    def test_sink_allocation_failure_never_launches(self):
        controller = self.controller()
        create = C.query._PosixDirectory.create_file
        def fail(directory, name, **kwargs):
            if name == "stderr.log":
                raise RuntimeError("model sink construction")
            return create(directory, name, **kwargs)
        with patch.object(C.query._PosixDirectory, "create_file", fail), self.assertRaises(RuntimeError):
            controller.phase("product", ["must-not-launch"], 120)
        self.assertEqual(self.calls, [])
        self.assertTrue(controller.unknown)

    def test_partial_spawn_failure_preserves_original_and_drains(self):
        self.spawn_error = ValueError("model spawn original")
        controller = self.controller()
        with self.assertRaisesRegex(ValueError, "spawn original"):
            controller.phase("product", ["model"], 120)
        self.assertIn("drain", self.events)
        self.assertIn("scope-close", self.events)
        self.assertFalse(controller.unknown)
        self.assertIs(controller.original, self.spawn_error)

    def test_late_receipt_failure_blocks_successful_return(self):
        controller = self.controller()
        write = controller.write
        def fail(directory, name, value, end):
            if name == "result.json":
                raise OSError("model terminal receipt failed")
            return write(directory, name, value, end)
        with patch.object(controller, "write", side_effect=fail), self.assertRaises(C.ControllerError):
            controller.phase("audit-init", ["model"], 120)
        self.assertNotIn("audit-init", controller.phase_hashes)
        self.assertEqual(controller.errors[-1]["stage"], "audit-init-receipt")

    def test_terminal_readback_failure_cannot_advance_or_claim_known(self):
        controller = self.controller()
        read = C.query._PosixDirectory.read_bytes
        def fail(directory, name, **kwargs):
            if name == "result.json":
                raise OSError("model late readback close")
            return read(directory, name, **kwargs)
        with patch.object(C.query._PosixDirectory, "read_bytes", fail), self.assertRaises(C.ControllerError):
            controller.phase("audit-init", ["model"], 120)
        self.assertTrue(controller.unknown)
        self.assertNotIn("audit-init", controller.phase_hashes)

    def test_drain_failure_is_unknown_and_preserves_primary_error(self):
        self.poll_error = ValueError("primary poll")
        self.drain_error = OSError("secondary drain")
        controller = self.controller()
        with self.assertRaisesRegex(ValueError, "primary poll"):
            controller.phase("product", ["model"], 120)
        self.assertTrue(controller.unknown)
        self.assertIs(controller.original, self.poll_error)
        self.assertTrue(any(row["stage"] == "product-drain" for row in controller.errors))

    def test_scope_close_failure_cannot_return_success(self):
        self.close_error = OSError("model close")
        controller = self.controller()
        with self.assertRaises(C.ControllerError):
            controller.phase("product", ["model"], 120)
        self.assertTrue(controller.unknown)

    def test_live_output_overflow_fails_and_drains_without_upload(self):
        controller = self.controller()
        with patch.object(C, "OUTPUT_LIMIT", 4), self.assertRaises(C.query.QueryError):
            controller.phase("product", ["model"], 120)
        self.assertIn("drain", self.events)
        self.assertTrue(controller.errors)
        self.assertFalse(controller.encrypted)

    def test_cancel_before_launch_never_spawns(self):
        controller = self.controller()
        controller.cancelled.append(signal.SIGTERM)
        with self.assertRaises(KeyboardInterrupt):
            controller.phase("product", ["model"], 120)
        self.assertEqual(self.events, [])

    def test_cancel_during_nonproduct_stops_then_drains(self):
        controller = self.controller()
        self.after_launch = lambda: controller.cancelled.append(signal.SIGTERM)
        self.poll_function = lambda: None
        with self.assertRaises(KeyboardInterrupt):
            controller.phase("audit-init", ["model"], 120)
        self.assertEqual(self.events.count("spawn"), 1)
        self.assertIn("drain", self.events)

    def test_product_cancel_uses_exact_reserved_cooperative_cancellation(self):
        controller = self.controller()
        controller.context = {"id": "a" * 32}
        controller.request = {"owner": {"productInvocation": "b" * 32}}
        self.after_launch = lambda: controller.cancelled.append(signal.SIGTERM)
        codes = iter([None, 125])
        self.poll_function = lambda: next(codes)
        with patch.object(C.audit, "request_cancellation") as cancellation, self.assertRaises(KeyboardInterrupt):
            controller.phase("product", ["model"], 120, product=True)
        cancellation.assert_called_once_with(controller.state_path, "a" * 32, "b" * 32)
        self.assertTrue(controller.product_attempted)
        self.assertIn("drain", self.events)

    def test_absolute_timeout_not_renewed_on_poll(self):
        controller = self.controller()
        self.poll_function = lambda: None
        with self.assertRaises(C.posix.EvidenceError):
            controller.phase("product", ["model"], 1)
        self.assertLess(self.clock.now, 102)
        self.assertIn("drain", self.events)

    def test_result_snapshots_do_not_alias_mutable_errors_or_phases(self):
        controller = self.controller()
        original = controller.result()
        controller.errors.append({"stage": "later"})
        controller.records.append({"phase": "later"})
        self.assertEqual(original["errors"], [])
        self.assertEqual(original["phases"], [])


class CopyAndSealModels(Base):
    def test_arbitrary_admitted_uppercase_and_long_names_are_retained_reversibly(self):
        owner = self.owner()
        source = self.private(owner, "original")
        child = source.path / "buildSrc"
        child.mkdir(mode=0o700)
        payload = b"synthetic-xml\x00\xff" * 100
        original = child / ("TEST-" + "A" * 140 + ".xml")
        original.write_bytes(payload)
        original.chmod(0o600)
        empty = source.path / "Empty.LOG"
        empty.touch(mode=0o600)
        copied = C.copy_tree(owner, source, self.path / "copied", 200.)
        mapping = C.parse((copied.path / "original-path-map.json").read_bytes())
        self.assertIn("buildSrc", mapping["directories"])
        self.assertEqual(len(mapping["files"]), 2)
        for row in mapping["files"]:
            self.assertEqual((copied.path / row["member"]).read_bytes(), (source.path / row["original"]).read_bytes())
            self.assertEqual(row["sha256"], C.digest((source.path / row["original"]).read_bytes()))
        self.assertEqual(original.read_bytes(), payload)
        owner.close()

    def test_copy_rejects_symlink_and_preserves_original(self):
        owner = self.owner()
        source = self.private(owner, "original")
        (source.path / "link").symlink_to(self.root)
        with self.assertRaises(C.posix.EvidenceError):
            C.copy_tree(owner, source, self.path / "copy", 200.)
        self.assertTrue((source.path / "link").is_symlink())

    def test_copy_detects_same_size_corrupt_destination_bytes(self):
        owner = self.owner()
        source = self.private(owner, "original")
        self.set_file(source, "TEST.xml", b"original")
        write = C.query._PosixSink.write
        def corrupt(stream, raw):
            if stream.path.name.startswith("member-"):
                raw = b"X" * len(raw)
            return write(stream, raw)
        with patch.object(C.query._PosixSink, "write", corrupt), self.assertRaisesRegex(C.ControllerError, "COPY_READBACK"):
            C.copy_tree(owner, source, self.path / "copy", 200.)

    def test_copy_preserves_primary_write_and_secondary_reader_close_errors(self):
        owner = self.owner()
        source = self.private(owner, "original")
        self.set_file(source, "TEST.xml", b"test")
        class Reader(io.BytesIO):
            def close(self):
                super().close()
                raise OSError("secondary reader close")
        reader = Reader(b"test")
        write = C.query._PosixSink.write
        def fail(stream, raw):
            if stream.path.name.startswith("member-"):
                raise ValueError("primary copy write")
            return write(stream, raw)
        with patch.object(C.posix, "_open_member", return_value=reader), \
                patch.object(C.query._PosixSink, "write", fail), \
                self.assertRaisesRegex(ValueError, "primary copy write"):
            C.copy_tree(owner, source, self.path / "copy", 200.)
        self.assertTrue(owner.unknown)
        self.assertTrue(any(row["stage"] == "copy-reader-close" for row in owner.errors))

    def test_snapshot_exception_without_returned_object_is_conservative_unknown(self):
        owner = self.owner()
        source = self.private(owner, "original")
        with patch.object(C.posix, "_snapshot", side_effect=OSError("model snapshot close ambiguity")), \
                self.assertRaises(OSError):
            C.copy_tree(owner, source, self.path / "copy", 200.)
        self.assertTrue(owner.unknown)

    def export(self):
        owner = self.owner()
        output = self.private(owner, "export")
        raw = b"SYNTHETIC_NOT_GPG" * 20
        self.set_file(output, C.posix.ARTIFACT, raw)
        manifest = {"schema": 2, "artifact": {"name": C.posix.ARTIFACT, "size": len(raw), "sha256": C.digest(raw)}}
        manifest_raw = self.set_file(output, C.posix.MANIFEST, manifest)
        returned = {"manifest": manifest, "manifestSha256": C.digest(manifest_raw), "returned": True,
                    "retirement": "KNOWN", "errors": []}
        original = {"result": returned, "sha256": C.digest(C.encoded(returned))}
        return owner, output, original

    def test_original_export_hash_binding_is_required(self):
        owner, output, original = self.export()
        self.assertEqual(C.verify_export_binding(owner, output, original, 200.),
                         (output.path / C.posix.MANIFEST).read_bytes())
        original["result"]["manifest"]["artifact"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(C.ControllerError, "EXPORT_RETURN_CHANGED"):
            C.verify_export_binding(owner, output, original, 200.)

    def test_coordinated_ciphertext_manifest_replacement_cannot_self_agree(self):
        owner, output, original = self.export()
        replacement = b"another-synthetic-not-ciphertext" * 20
        (output.path / C.posix.ARTIFACT).write_bytes(replacement)
        replacement_manifest = {"schema": 2, "artifact": {"name": C.posix.ARTIFACT, "size": len(replacement),
                                                         "sha256": C.digest(replacement)}}
        (output.path / C.posix.MANIFEST).write_bytes(C.encoded(replacement_manifest))
        with self.assertRaisesRegex(C.ControllerError, "EXPORTED_ARTIFACT_CHANGED"):
            C.verify_export_binding(owner, output, original, 200.)

    def test_ciphertext_only_change_and_extra_member_are_rejected(self):
        owner, output, original = self.export()
        path = output.path / C.posix.ARTIFACT
        path.write_bytes(b"x" * path.stat().st_size)
        with self.assertRaises(C.ControllerError):
            C.verify_export_binding(owner, output, original, 200.)
        self.set_file(output, "raw.log", b"must-not-upload")
        with self.assertRaisesRegex((C.ControllerError, C.posix.EvidenceError), "SEALED_OUTPUT_MEMBERS|member count"):
            C.artifact_metadata(owner, output, 200.)

    def test_crypto_nonzero_never_upgrades_child_unknown_from_outer_retirement(self):
        controller = self.controller()
        with self.assertRaises(C.ControllerError):
            controller.crypto_return("export", {"exitCode": 125, "retirement": "KNOWN"})
        self.assertTrue(controller.unknown)
        self.assertEqual(self.calls, [])

    def test_missing_crypto_terminal_receipt_is_unknown(self):
        controller = self.controller()
        with self.assertRaises(FileNotFoundError):
            controller.crypto_return("export", {"exitCode": 0})
        self.assertTrue(controller.unknown)

    def test_successful_crypto_return_requires_exact_context(self):
        controller = self.controller()
        controller.context_hash = "a" * 64
        self.set_file(controller.runtime, "export-result.json", {"schema": 1, "operation": "export", "profile": "desktop",
             "contextSha256": "b" * 64, "retirement": "KNOWN", "returned": True, "errors": []})
        with self.assertRaises(C.ControllerError):
            controller.crypto_return("export", {"exitCode": 0})
        self.assertTrue(controller.unknown)

    def test_seal_requires_real_previous_step_success(self):
        with self.assertRaisesRegex(C.ControllerError, "ORIGINAL_CONTROLLER_DID_NOT_SUCCEED"):
            C.validate_public("desktop")
        self.assertEqual(self.calls, [])


class FinalizationModels(Base):
    def fake_controller(self):
        events = self.events
        state = SimpleNamespace(unknown=False, errors=[], private=object(), deadline=200., encrypted=True,
                                cancelled=[], receipt_error=False, close_error=False)
        def check(**kwargs):
            events.append("check")
        def setup():
            events.append("setup")
        def product():
            events.append("product")
        def collect():
            events.append("collect")
        def export():
            events.append("export")
        def result():
            return {"readyForPostReturnSeal": state.encrypted and not state.unknown,
                    "errors": json.loads(json.dumps(state.errors))}
        def error(stage, value, unknown=False):
            state.errors.append({"stage": stage, "detail": str(value)})
            state.unknown |= unknown
        def write(*args):
            events.append("write")
            if state.receipt_error:
                raise OSError("model terminal")
        def close():
            events.append("close")
            if state.close_error:
                raise OSError("model late close")
        for name, value in locals().copy().items():
            if name in {"check", "setup", "product", "collect", "export", "result", "error", "write", "close"}:
                setattr(state, "product_run" if name == "product" else name, value)
        state.retire_simulator = lambda: None  # The real Desktop implementation is an unchanged no-op.
        state.retain_primary_abi = lambda: None
        return state

    def invoke(self, state):
        with patch.object(C, "Controller", return_value=state), redirect_stdout(io.StringIO()) as output:
            code = C.run("desktop")
        self.assertNotIn("model terminal", output.getvalue())
        return code

    def test_actual_run_always_collects_after_product_failure_before_export(self):
        state = self.fake_controller()
        def fail():
            self.events.append("product")
            raise ValueError("synthetic product failure")
        state.product_run = fail
        self.assertEqual(self.invoke(state), 0)  # Safe failure retention is not a passing profile.
        self.assertEqual(self.events, ["check", "setup", "product", "collect", "export", "write", "close"])
        self.assertEqual(state.errors[0]["stage"], "run")

    def test_terminal_write_failure_cannot_return_success(self):
        state = self.fake_controller()
        state.receipt_error = True
        self.assertEqual(self.invoke(state), 125)
        self.assertIn("close", self.events)

    def test_late_close_failure_cannot_return_success(self):
        state = self.fake_controller()
        state.close_error = True
        self.assertEqual(self.invoke(state), 125)

    def test_late_mutation_after_frozen_receipt_cannot_return_success(self):
        state = self.fake_controller()
        def close():
            state.error("late", OSError("late mutation"))
        state.close = close
        self.assertEqual(self.invoke(state), 125)

    def test_signal_restoration_failure_cannot_return_success(self):
        state = self.fake_controller()
        def failure(number, handler):
            if handler == "MODEL_PREVIOUS_HANDLER":
                raise OSError("synthetic restoration failure")
        with patch.object(C.signal, "signal", side_effect=failure):
            self.assertEqual(self.invoke(state), 125)
        self.assertTrue(state.unknown)

    def test_controller_constructor_failure_still_restores_original_handlers(self):
        values = []
        with patch.object(C, "Controller", side_effect=ValueError("model before allocation")), \
                patch.object(C.signal, "signal", side_effect=lambda number, handler: values.append((number, handler))), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(C.run("desktop"), 125)
        signals = (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else []))
        self.assertEqual(values[-len(signals):], [(number, "MODEL_PREVIOUS_HANDLER") for number in signals])

    def test_custody_unknown_blocks_uninstall(self):
        controller = self.controller()
        controller.request = {"owner": {"productInvocation": "a" * 32}}
        directory = controller.child(controller.evidence, "custody", 200., create=True)
        self.set_file(directory, "result.json", {"retirement": "UNKNOWN", "result": "HOLD"})
        calls = []
        with patch.object(controller, "phase", side_effect=lambda *args, **kwargs:
                         calls.append(args[0]) or {"exitCode": 125}), self.assertRaises(C.ControllerError):
            controller.collect()
        self.assertEqual(calls, ["custody-collect"])
        self.assertTrue(controller.unknown)

    def test_known_failed_custody_allows_only_exact_loader_uninstall(self):
        controller = self.controller()
        controller.request = {"owner": {"productInvocation": "a" * 32}}
        directory = controller.child(controller.evidence, "custody", 200., create=True)
        self.set_file(directory, "result.json", {"retirement": "KNOWN", "result": "HOLD"})
        self.set_file(directory, "uninstalled.json", {"absent": True, "originalsDeleted": False})
        calls = []
        with patch.object(controller, "phase", side_effect=lambda *args, **kwargs:
                         calls.append(args) or {"exitCode": 125 if args[0] == "custody-collect" else 0}):
            controller.collect()
        self.assertEqual([row[0] for row in calls], ["custody-collect", "custody-uninstall"])
        self.assertEqual(calls[1][1][-2:], ["--directory", str(directory.path)])
        self.assertFalse(controller.unknown)


class WholeControllerModels(Base):
    """Actual controller orchestration; every child, identity and GPG result modeled.

    Synthetic success is NOT test execution, cryptographic output, hosted identity
    or Windows admission. It checks only composition against frozen interfaces.
    """
    def setUp(self):
        super().setUp()
        self.source = {"commit": "a" * 40, "tree": "b" * 40}
        self.clean_source = {**self.source, "status": "", "diffSha256": C.digest(b"")}
        self.profile = "desktop"
        self.job, self.reserved = "c" * 32, "d" * 32
        self.product_code = 0
        self.simulator_uuid = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
        self.simulator_runtime = "com.apple.CoreSimulator.SimRuntime.iOS-26-5"
        self.simulator_runtimes = {"runtimes": [{"identifier": self.simulator_runtime, "version": "26.5", "isAvailable": True}]}
        self.simulator_devices = {"devices": {self.simulator_runtime: [{"name": "iPhone 17", "udid": self.simulator_uuid,
            "state": "Shutdown", "isAvailable": True, "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-17"}]}}
        self.simulator_outputs, self.simulator_codes, self.simulator_calls = {}, {}, []
        self.product_boots_simulator = True
        self.produce_primary_abi = True
        # Checked-in public bytes are only MODEL INPUTS, not generated evidence.
        # The modeled child separately creates files; real acquisition/retention
        # reads them independently of the modeled immutable Git callback.
        self.abi_references = {index: (ROOT / path).read_bytes() for index, path in enumerate(C.abi.BASELINES)}
        self.abi_query_sessions = []
        self.fail_uninstall = False
        self.job_elapsed, self.job_time_calls, self.job_time_child_errors = 120, [], []
        self.crypto_owners, self.crypto_child_errors, self.crypto_child_quarantines = [], [], []
        self.active_crypto_operation = None
        hold = C.PrivateOwner.hold
        def remember(owner, label, resource):
            if type(owner) is C.PrivateOwner and not any(value is owner for value in self.crypto_owners):
                self.crypto_owners.append(owner)
            return hold(owner, label, resource)
        self.stack.enter_context(patch.object(C.PrivateOwner, "hold", remember))
        (self.root / "buildSrc").mkdir(mode=0o700)
        (self.root / "library").mkdir(mode=0o700)
        for module in dict.fromkeys(route[0] for route in C.abi.ROUTES):
            (self.root / "library" / module).mkdir(mode=0o755)
        self.public_key = b"SYNTHETIC PUBLIC KEY; NOT CRYPTOGRAPHIC MATERIAL"
        event, policy = C.encoded({"model": "event"}), C.encoded({"model": "policy"})
        record = {"source": self.source, "profile": self.profile, "suites": ["cli"],
                  "github": {"eventSha256": C.digest(event), "runId": "123", "runAttempt": "1"},
                  "policy": {"sha256": C.digest(policy), "keySha256": C.digest(self.public_key),
                             "fingerprint": "A" * 40, "expiresAt": 2000000000}}
        self.admitted = C.identity.Admission(C.encoded(record), event, policy, self.public_key,
                                            "A" * 40, C.digest(self.public_key), 2000000000)
        self.stack.enter_context(patch.object(C, "admission", side_effect=self.model_admission))
        self.stack.enter_context(patch.object(C.identity.shutil, "which", return_value=sys.executable))
        self.stack.enter_context(patch.object(C.query, "NativeGitQueries", side_effect=self.model_git_queries))
        self.stack.enter_context(patch.object(C.posix, "validate_recipient", side_effect=self.model_recipient))
        self.stack.enter_context(patch.object(C.ordinary, "export_encrypted", side_effect=self.model_export))
        self.stack.enter_context(patch.object(C.audit, "output_roots", return_value=[self.root / "build", *[
            self.root / "library" / module / "build" for module in dict.fromkeys(route[0] for route in C.abi.ROUTES)]]))
        self.stack.enter_context(patch.object(C.job_time, "_request", side_effect=self.model_job_time_response))

    def use_full(self):
        self.profile = "full"
        self.admitted = JOB_MODELS.model_admission()
        os.environ[C.job_time.TOKEN_ENV] = JOB_MODELS.TOKEN

    def full_controller(self):
        self.use_full()
        controller = C.Controller("full")
        self.owners.append(controller)
        with patch.object(C.shutil, "which", return_value=sys.executable):
            controller.setup()
        return controller

    def execute_full(self):
        self.use_full()
        with patch.object(C.shutil, "which", return_value=sys.executable):
            return self.execute()

    def inject_product_poll(self, function):
        # Keep the original cancellation-before-drain assertions scoped to the
        # actual product, not the newly preceding prelaunch query's own drain.
        spawn = Scope.spawn
        def product(scope, argv, cwd, environment, **sinks):
            if "--cwd" in argv:
                del self.events[:scope.event_start]
                self.poll_function = function
            return spawn(scope, argv, cwd, environment, **sinks)
        self.stack.enter_context(patch.object(Scope, "spawn", product))

    def assert_full_stopped_before_crypto(self):
        with patch.object(C.shutil, "which", return_value=sys.executable), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        self.assertFalse(any("_crypto" in row["argv"] or "init" in row["argv"] or "--cwd" in row["argv"]
                             for row in self.calls))
        self.assertNotIn(C.job_time.TOKEN_ENV, os.environ)
        self.assertIsNone(self.owners[-1].actions_token)
        return self.owners[-1]

    def model_cancellation(self, state, job, invocation):
        self.events.append("cooperative-cancellation")
        self.assertEqual((state, job, invocation),
                         (C.session_path("full", "macos-arm64") / "state", self.job, self.reserved))
        self.save(state / "cancellations" / (invocation + ".json"),
                  {"schema": 1, "id": invocation, "jobId": job, "requestedUtc": "2026-09-16T00:00:00Z"})

    def model_job_time_response(self, path, token, invocation):
        self.assertEqual(token, JOB_MODELS.TOKEN)
        self.assertNotIn(C.job_time.TOKEN_ENV, os.environ)
        self.job_time_calls.append(path)
        paths = C.job_time.paths(self.admitted)
        label = next(label for label, value in paths.items() if value == path)
        return JOB_MODELS.model_responses(self.admitted, invocation, raw_ns=self.clock.raw(),
                                         elapsed=self.job_elapsed)[label], None

    def save(self, path, value):
        raw = value if type(value) is bytes else C.encoded(value)
        path.write_bytes(raw)
        path.chmod(0o600)
        return raw

    def model_admission(self, owner, profile, destination, check_cancel, expected=None):
        check_cancel()
        self.assertEqual(profile, self.profile)
        if expected is not None:
            self.assertEqual(expected, self.admitted)
        destination.mkdir(mode=0o700)
        for name, raw in (("admission.json", self.admitted.record), ("original-event.json", self.admitted.original_event),
                          ("original-policy.json", self.admitted.original_policy), ("recipient-public.asc", self.public_key)):
            self.save(destination / name, raw)
        return self.admitted

    def model_git_queries(self, root, destination, *, check_cancel):
        case = self
        class GitModel:
            def __init__(self):
                self.unknown, self.closed, self.rows = False, False, []
                self.path = Path(destination)
                self.path.mkdir(mode=0o700)
                case.abi_query_sessions.append(self)

            def native_host_matches_actions(self):
                check_cancel()

            def __call__(self, **request):
                check_cancel()
                argv = request["argv"]
                suffix = argv[7:]
                case.assertTrue(C.query._allowed_suffix(suffix))
                case.assertEqual(root, case.root)
                if suffix[:2] == ("ls-tree", "-z"):
                    case.assertEqual(suffix[2], case.source["commit"])
                    index = C.abi.BASELINES.index(suffix[4])
                    raw = ("100644 blob " + C.abi.blob(case.abi_references[index]) + "\t" + suffix[4] + "\0").encode()
                else:
                    data = next(raw for raw in case.abi_references.values() if C.abi.blob(raw) == suffix[2])
                    raw = str(len(data)).encode() if suffix[1] == "-s" else data
                case.assertLessEqual(len(raw), request["stdout_limit"])
                self.rows.append({"argv": list(argv), "cwd": str(root), "waitExitCode": 0,
                    "result": "READY_FOR_CALLER_SEAL", "retirement": "KNOWN", "errors": []})
                check_cancel()
                return raw

            def _finalize(self, original):
                self.closed = True
                case.save(self.path / "session-result.json", {"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY",
                    "result": "READY_FOR_CALLER_SEAL" if original is None else "HOLD", "retirement": "KNOWN",
                    "firstError": None if original is None else type(original).__name__, "errors": [], "queries": self.rows})
        return GitModel()

    def model_recipient(self, key, fingerprint, work):
        self.assertEqual(key.read_bytes(), self.public_key)
        self.assertEqual(fingerprint, "A" * 40)
        (work / "gnupg").mkdir(mode=0o700)
        (work / "tmp").mkdir(mode=0o700)
        return C.posix.Recipient(work, work / "gnupg", Path("/synthetic/gpg"), "A" * 40, "B" * 40,
                                2000000000, C.digest(self.public_key), C.posix._identity(work))

    def model_export(self, evidence, output, recipient, **kwargs):
        self.assertEqual(kwargs["admission"], self.admitted)
        mapping = C.parse((evidence / "original-path-map.json").read_bytes())
        self.assertEqual(mapping["scope"], "REVERSIBLE_PRIVATE_BYTE_COPY")
        output.mkdir(mode=0o700)
        ciphertext = b"SYNTHETIC_NONCRYPTOGRAPHIC_MODEL" * 32
        self.save(output / C.posix.ARTIFACT, ciphertext)
        record = C.parse(self.admitted.record)
        manifest = {"schema": 2, "scope": "ENCRYPTED_PRIVATE_TEST_EVIDENCE", "source": record["source"],
           "github": record["github"], "policy": record["policy"],
           "custody": {"profile": record["profile"], "suites": record["suites"]},
           "artifact": {"name": C.posix.ARTIFACT, "size": len(ciphertext), "sha256": C.digest(ciphertext)}}
        self.save(output / C.posix.MANIFEST, manifest)
        return manifest

    def model_output(self, argv, label):
        if label in (*C.simulator.PREPARE, C.simulator.PRELAUNCH, *C.simulator.RETIRE):
            output = {"simulator-macos-version": b"26.0\n",
                      "simulator-xcode-version": b"Xcode 26.5\nBuild version 17F42\n",
                      "simulator-first-launch": b"", "simulator-runtimes": C.encoded(self.simulator_runtimes),
                      "simulator-devices": C.encoded(self.simulator_devices),
                      C.simulator.PRELAUNCH: C.encoded(self.simulator_devices),
                      C.simulator.BEFORE: C.encoded(self.simulator_devices), C.simulator.SHUTDOWN: b"",
                      C.simulator.AFTER: C.encoded(self.simulator_devices)}[label]
            return self.simulator_outputs.get(label, output), b""
        return self.stdout, self.stderr

    def simulator_state(self, state):
        for rows in self.simulator_devices["devices"].values():
            for row in rows:
                if row["udid"] == self.simulator_uuid:
                    row["state"] = state

    def model_platform_reports(self, folder, environment):
        """Synthetic configured-Property/outcome records, never KGP execution."""
        binding_raw = Path(environment[C.simulator.PATH_ENV]).read_bytes()
        self.assertEqual(C.digest(binding_raw), environment[C.simulator.HASH_ENV])
        start_raw = (folder / "start.json").read_bytes()
        prelaunch_raw = (Path(environment[C.simulator.PATH_ENV]).parent / "prelaunch.json").read_bytes()
        bound = C.simulator.coverage_identity(binding_raw, start_raw, prelaunch_raw)
        policy = C.parse((ROOT / "gradle/platform-test-policy.json").read_bytes())
        tasks = [name for entry in policy["model"].values() for name in entry["tests"]]
        token = "e" * 32
        command = [str(self.root / "gradlew"), "check", "--no-daemon", "--no-build-cache", "--no-configuration-cache",
                   "--rerun-tasks", "--dependency-verification", "strict", "--max-workers=2", "--no-parallel", "--console=plain",
                   "--init-script", str(self.root / "gradle/platform-test-coverage.init.gradle"),
                   "-Pp2pkit.testCoverageRoot=" + str(self.root), "-Pp2pkit.testCoverageToken=" + token,
                   "-Pp2pkit.ordinarySimulatorBinding=" + environment[C.simulator.PATH_ENV],
                   "-Pp2pkit.ordinarySimulatorSha256=" + C.digest(binding_raw),
                   "-Pp2pkit.ordinarySimulatorStartSha256=" + C.digest(start_raw),
                   "-Pp2pkit.ordinarySimulatorPrelaunchSha256=" + C.digest(prelaunch_raw)]
        source = {**self.clean_source, "profile": "full", "token": token, "command": command, "ordinarySimulator": bound}
        selected = {path: {"device": bound["device"], "type": C.simulator.TYPE} for path in C.simulator.TASKS}
        execution = {"schema": 1, "token": token, "buildFailed": bool(self.product_code), "dryRun": False,
            "host": {"os": "Mac OS X", "arch": "aarch64"}, "model": policy["model"],
            "tests": {name: {"outcome": "SKIPPED" if name.endswith(":iosX64Test") else "EXECUTED",
                             "enabled": not name.endswith(":iosX64Test"), "inGraph": True,
                             "passed": 0 if name.endswith(":iosX64Test") else 1, "failed": 0, "skipped": 0} for name in tasks},
            "ordinarySimulator": {**bound, "configured": selected, "inGraph": copy.deepcopy(selected), "unchanged": True}}
        summary = {**source, "sourceAfter": self.clean_source, "result": "FAIL" if self.product_code else "PASS",
                   "errors": ["MODEL_PRODUCT_FAILED"] if self.product_code else [], "gradleExitCode": self.product_code,
                   "stopExitCode": 0}
        directory = folder
        for name in ("reports", "build", "reports", "platform-tests", token):
            directory = directory / name
            directory.mkdir(mode=0o700)
        records = []
        for name, value in (("invocation", source), ("execution", execution), ("summary", summary)):
            raw = self.save(directory / (name + ".json"), value)
            relative = "build/reports/platform-tests/" + token + "/" + name + ".json"
            records.append({"source": relative, "retained": "reports/" + relative, "sha256": C.digest(raw), "bytes": len(raw),
                            "classification": "changed-since-admission"})
        self.save(folder / "report-manifest.json", {"schema": 1, "records": records})
        return records

    def model_child(self, argv, environment):
        if argv[0] in ("/usr/bin/sw_vers", "/usr/bin/xcodebuild", "/usr/bin/xcrun"):
            label = self.calls[-1]["stdout"].path.parent.name
            self.simulator_calls.append((label, list(argv)))
            self.exit_code = self.simulator_codes.get(label, 0)
            if label == C.simulator.SHUTDOWN and self.exit_code == 0:
                self.simulator_state("Shutdown")
            return
        if argv[4] == "-c":
            self.assertEqual(argv[5], C.CANONICAL_BOOTSTRAP)
            self.assertEqual(argv[6], str(self.root / "scripts"))
            self.assertEqual(C.parse(argv[7].encode("ascii")), C.canonical_bindings())
            args = argv[8:]
        else:
            args = argv[5:]
        session = C.session_path(self.profile, "macos-arm64")
        state, custody = session / "state", session / "evidence/custody"
        if args[0] == "_job-time":
            try:
                with patch.dict(os.environ, environment, clear=True):
                    C.job_time_phase(self.profile, args[-1])
                self.exit_code = 0
            except BaseException as error:
                self.job_time_child_errors.append(error)
                self.exit_code = 125
        elif args[0] == "_crypto":
            child_quarantines = ([], [], [])
            previous = self.active_crypto_operation
            self.active_crypto_operation = args[1]
            # These are different interpreter globals in production. A child
            # quarantine must not accidentally update the parent's model state
            # and conceal a missing explicit return fence.
            with patch.object(C, "QUARANTINE", child_quarantines[0]), \
                    patch.object(C.query, "QUARANTINE", child_quarantines[1]), \
                    patch.object(C.windows, "_QUARANTINE", child_quarantines[2]):
                try:
                    with patch.dict(os.environ, environment, clear=True):
                        C.crypto_phase(args[1], self.profile, args[-1])
                    self.exit_code = 0
                except BaseException as error:
                    # A separate child's nonzero exit, not a spawn exception.
                    self.crypto_child_errors.append((args[1], error))
                    self.exit_code = 125
                finally:
                    self.crypto_child_quarantines.append((args[1], [list(rows) for rows in child_quarantines]))
                    self.active_crypto_operation = previous
        elif args[0] == "init":
            self.assertFalse(state.exists())
            state.mkdir(mode=0o700)
            for name in ("gradle-home", "evidence", "cancellations"):
                (state / name).mkdir(mode=0o700)
            self.save(state / "context.json", {"schema": 1, "id": self.job, "root": str(self.root), "host": "macos-arm64",
                 "gradleHome": str(state / "gradle-home"), "source": self.clean_source, "preexistingOutputPaths": []})
        elif args[0] == "prepare":
            self.assertTrue((self.root / "build").is_dir(), "Outputs must be private before any product writer")
            self.assertEqual((self.root / "build").stat().st_mode & 0o777, 0o700)
            custody.mkdir(mode=0o700)
            (custody / "retained").mkdir(mode=0o700)
            command = args[args.index("--") + 1:]
            self.request = {"ownerKind": "audit", "owner": {"job": self.job, "productInvocation": self.reserved,
                "stopInvocation": None}, "command": command, "ownerState": str(state), "home": str(state / "gradle-home"),
                "root": str(self.root), "source": self.clean_source}
            self.request_raw = self.save(custody / "request.json", self.request)
            (state / "gradle-home/init.d").mkdir(mode=0o700)
            self.save(state / "gradle-home/init.d/model-loader", b"synthetic owned loader")
        elif args[0] == "--cwd":
            self.assertEqual(args[args.index("--id") + 1], self.reserved)
            self.assertEqual(environment[C.processes.STATE_ENV], str(state))
            self.assertEqual(environment["GRADLE_USER_HOME"], str(state / "gradle-home"))
            self.assertEqual(environment[C.processes.JOB_ENV], self.job)
            command = args[args.index("--") + 1:]
            self.assertEqual(command, self.request["command"])
            folder = state / "evidence" / self.reserved
            folder.mkdir(mode=0o700)
            canonical = {"schema": 1, "id": self.reserved, "jobId": self.job, "cwd": str(self.root),
                 "kind": args[args.index("--kind") + 1], "host": "macos-arm64", "gradleHome": str(state / "gradle-home"),
                 "requestedArgv": command, "sourceBefore": self.clean_source, "sourceAfter": self.clean_source,
                 "sourceUnchanged": True, "productExitCode": self.product_code, "stopExitCode": 0,
                 "finalExitCode": self.product_code, "errors": [], "ownedSurvivors": [],
                 "ownership": {"discoveryErrors": []}}
            if self.profile == "full":
                binding = C.parse(Path(environment[C.simulator.PATH_ENV]).read_bytes())
                start = model_canonical_start(binding, environment[C.processes.CHAIN_ENV].split(":"), self.calls[-1]["pid"])
                self.save(folder / "start.json", start)
                pid = self.calls[-1]["pid"] + 100000
                canonical = {**start, **canonical, "executedArgv": command, "productPid": pid, "productLaunchIndex": 0,
                    "ownership": {"backend": "darwin-libproc-audit-token", "scope": "controlled-marker-inheriting-descendants",
                        "job": self.job, "invocation": self.reserved, "discoveryErrors": [],
                        "launches": [{"api": "subprocess.Popen", "requestedArgv": command, "cwd": str(self.root),
                                      "shell": False, "created": True, "pid": pid}], "startedIdentities": [model_identity(pid)]}}
                if self.product_boots_simulator:
                    self.simulator_state("Booted")
                canonical["reports"] = self.model_platform_reports(folder, environment)
                self.save(folder / "product.stdout.log", b"MODEL NOT A BUILD\n" + b"".join(
                    b"> Task " + task.encode() + b"\n" for task in C.abi.FRESH_TASKS))
                if self.produce_primary_abi:
                    for index, path in enumerate(C.abi.GENERATED):
                        output = self.root / path
                        output.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                        self.save(output, self.abi_references[index])
            self.save(folder / "receipt.json", canonical)
            self.exit_code = self.product_code
        elif args[0] == "collect":
            canonical = state / "evidence" / self.reserved / "receipt.json"
            self.save(custody / "retained/owner-result.json", canonical.read_bytes())
            self.save(custody / "result.json", {"schema": 1, "requestSha256": C.digest(self.request_raw),
                "result": "RETAINED" if self.product_code == 0 else "HOLD", "retirement": "KNOWN",
                "source": self.clean_source, "sourceAfter": self.clean_source, "productExitCode": self.product_code,
                "stopExitCode": 0, "ownerFinalExitCode": self.product_code,
                "errors": [] if not self.product_code else ["MODEL_PRODUCT_FAILED"]})
            self.exit_code = 0 if self.product_code == 0 else 125
        elif args[0] == "uninstall":
            if self.fail_uninstall:
                self.exit_code = 125
                return
            (state / "gradle-home/init.d/model-loader").unlink()
            self.save(custody / "uninstalled.json", {"requestSha256": C.digest(self.request_raw), "absent": True,
                                                     "originalsDeleted": False})
            self.exit_code = 0
        else:
            raise AssertionError("UNMODELED_CHILD " + repr(args))

    def call_run(self):
        actual = C.Controller
        def construct(profile):
            value = actual(profile)
            self.owners.append(value)
            return value
        with patch.object(C, "Controller", side_effect=construct):
            return C.run(self.profile)

    def execute(self):
        self.exit_code = 0
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(self.call_run(), 0)
        self.assertIn("RETURNED_FOR_SEAL", stdout.getvalue())
        session = C.session_path(self.profile, "macos-arm64")
        result = C.parse((session / "controller-result.json").read_bytes())
        self.assertEqual(result["retirement"], "KNOWN")
        self.assertTrue(result["encrypted"])
        return session, result

    def seal(self):
        output = self.path / "public-step-output"
        output.touch(mode=0o600)
        with patch.dict(os.environ, {"P2PKIT_HOSTED_TEST_RUN_OUTCOME": "success", "GITHUB_OUTPUT": str(output)}), \
                patch.object(C.os, "getpid", return_value=9999999), redirect_stdout(io.StringIO()):
            C.validate_public(self.profile)
        return output.read_text()

    def upload(self, phase, *, before_hash=None):
        output = self.path / ("upload-" + phase + "-output")
        output.touch(mode=0o600)
        environment = {"P2PKIT_HOSTED_TEST_RUN_OUTCOME": "success", "P2PKIT_HOSTED_TEST_SEAL_OUTCOME": "success",
                       "GITHUB_OUTPUT": str(output)}
        if phase == "after":
            original = C.session_path("full", "macos-arm64") / "upload-before.json"
            environment.update(P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME="success",
                P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256=before_hash or C.digest(original.read_bytes()))
        with patch.dict(os.environ, environment), redirect_stdout(io.StringIO()):
            C.upload_guard(phase)
        return output.read_text()

    def test_desktop_whole_composition_and_post_return_seal_pass_in_model(self):
        session, result = self.execute()
        self.assertTrue(result["profilePassed"])
        self.assertEqual([row["phase"] for row in result["phases"]], ["recipient-validation", "audit-init", "custody-prepare",
                         "product", "custody-collect", "custody-uninstall", "export"])
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=true\n")
        self.assertTrue((session / "post-return-validation/seal.json").is_file())
        self.assertFalse((session / "state/gradle-home/init.d/model-loader").exists())

    def test_full_profile_keeps_literal_command_and_both_custody_suites_in_model(self):
        self.use_full()
        with patch.object(C.shutil, "which", return_value=sys.executable):
            session, result = self.execute()
        self.assertTrue(result["profilePassed"])
        context = C.parse((session / "run-context.json").read_bytes())
        self.assertEqual(context["command"], ["python3", "scripts/run-platform-tests.py", "full"])
        prepare = next(row for row in self.calls if "prepare" in row["argv"])
        self.assertEqual(prepare["argv"][prepare["argv"].index("--scope") + 1], "both")
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=true\n")

    def test_full_without_original_shutdown_simulator_cannot_be_green(self):
        # The actual controller must inspect this modeled inventory, not infer
        # simulator ownership from an otherwise successful aggregate check.
        self.simulator_devices = {"devices": {"com.apple.CoreSimulator.SimRuntime.iOS-26-5": []}}
        _session, result = self.execute_full()
        self.assertFalse(result["profilePassed"], "No originally Shutdown iPhone 17 was admitted")
        self.assertFalse(any("prepare" in row["argv"] or "--cwd" in row["argv"] for row in self.calls))
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=false\n")

    def test_full_missing_generated_primary_abi_cannot_be_green(self):
        # Actual controller over synthetic admitted children. No ABI producer
        # bytes exist; a passing modeled aggregate must not imply retention.
        self.produce_primary_abi = False
        _session, result = self.execute_full()
        self.assertFalse(result["profilePassed"])

    def test_full_retains_all_eight_before_export_and_reassesses_original_bytes(self):
        opened = []
        actual = C.posix._open_member
        def observe(root, name, snapshot):
            if "/build/kotlin/" in str(root):
                opened.append(str(root / name))
            return actual(root, name, snapshot)
        with patch.object(C.posix, "_open_member", observe):
            session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        self.assertEqual(opened, [str(self.root / path) for path in C.abi.GENERATED])
        manifest_raw = (session / "evidence/primary-abi/manifest.json").read_bytes()
        manifest = C.parse(manifest_raw)
        self.assertEqual(result["primaryAbi"], C.abi_disposition(manifest_raw))
        self.assertEqual(manifest["assessment"]["additive"]["preimageSha256"], C.abi.PREIMAGE_SHA256)
        self.assertEqual(manifest["primary"]["productInvocation"], self.reserved)
        self.assertEqual(len(manifest["acquisition"]["roots"]), 6)
        self.assertEqual(len(manifest["assessment"]["routes"]), 8)
        queries = next(row for row in self.abi_query_sessions if row.path.name == "primary-abi-queries")
        self.assertTrue(queries.closed)
        self.assertEqual(len(queries.rows), 24)
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=true\n")
        returned = C.parse((session / "runtime/export-result.json").read_bytes())
        self.assertEqual(returned["primaryAbiFrozen"]["manifestSha256"], C.digest(manifest_raw))
        for index in range(8):
            for role in ("generated", "baseline"):
                self.assertEqual((session / "evidence/primary-abi" / C.abi.member(index, role)).read_bytes(),
                                 self.abi_references[index])

    def test_full_all_missing_originals_retains_references_without_substitution(self):
        self.produce_primary_abi = False
        session, result = self.execute_full()
        manifest = C.parse((session / "evidence/primary-abi/manifest.json").read_bytes())
        self.assertFalse(result["profilePassed"])
        self.assertEqual(result["primaryAbi"]["generatedCount"], 0)
        self.assertTrue(all(row["generated"] is None for row in manifest["assessment"]["routes"]))
        self.assertEqual(len(list((session / "evidence/primary-abi").glob("baseline-*.bin"))), 8)
        self.assertEqual(list((session / "evidence/primary-abi").glob("generated-*.bin")), [])
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=false\n")

    def abi_failure_subcase(self, mutation, *, unknown=False):
        """Fresh synthetic state per adversarial case; never reuse an old product."""
        case = WholeControllerModels("runTest")
        case.setUp()
        try:
            retain = C.Controller.retain_primary_abi
            def changed(controller):
                mutation(case, controller)
                return retain(controller)
            case.use_full()
            with patch.object(C.Controller, "retain_primary_abi", changed), redirect_stdout(io.StringIO()):
                code = case.call_run()
            controller = case.owners[-1]
            self.assertFalse(controller.result()["profilePassed"])
            if unknown:
                self.assertEqual(code, 125)
                self.assertTrue(controller.unknown)
                self.assertFalse((controller.path / "export").exists())
            else:
                self.assertEqual(code, 0)
                self.assertEqual(case.seal(), "artifacts_ready=true\nprofile_passed=false\n")
        finally:
            case.tearDown()

    def test_each_missing_generated_file_cannot_be_replaced_by_the_reference(self):
        for index in range(8):
            with self.subTest(index=index):
                self.abi_failure_subcase(lambda case, _controller: (case.root / C.abi.GENERATED[index]).unlink())

    def test_each_generated_byte_mutation_is_a_retained_failed_comparison(self):
        for index in range(8):
            def change(case, _controller):
                path = case.root / C.abi.GENERATED[index]
                case.save(path, b"!" + path.read_bytes()[1:])
            with self.subTest(index=index):
                self.abi_failure_subcase(change)

    def test_original_log_stale_failed_duplicate_or_android_only_events_do_not_pass(self):
        def change(case, controller, mode):
            path = controller.state_path / "evidence" / case.reserved / "product.stdout.log"
            raw = path.read_bytes()
            marker = b"> Task :p2p-core:checkKotlinAbi\n"
            if mode == "duplicate":
                raw += marker
            elif mode == "android-only":
                raw = b"\n".join(b"> Task " + task.encode() for task in C.abi.FRESH_TASKS[-2:]) + b"\n"
            else:
                raw = raw.replace(marker, marker[:-1] + b" " + mode.encode() + b"\n")
            case.save(path, raw)
        for mode in ("FROM-CACHE", "UP-TO-DATE", "SKIPPED", "FAILED", "duplicate", "android-only"):
            with self.subTest(mode=mode):
                self.abi_failure_subcase(lambda case, controller: change(case, controller, mode))

    def test_failed_full_aggregate_never_becomes_green_from_eight_matching_files(self):
        self.product_code = 7
        session, result = self.execute_full()
        self.assertFalse(result["profilePassed"])
        self.assertEqual(result["primaryAbi"]["status"], "HOLD")
        self.assertEqual(len(list((session / "evidence/primary-abi").glob("generated-*.bin"))), 8)
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=false\n")

    def test_known_partial_failure_still_rechecks_original_snapshot_after_final_read(self):
        self.product_code = 7
        session, result = self.execute_full()
        primary = session / "evidence/primary-abi"
        self.assertIsNone(result["primaryAbi"]["manifestSha256"])
        self.assertFalse((primary / "manifest.json").exists())
        count, read = 0, C.PrivateOwner.read
        def changed(owner, directory, name, *args, **kwargs):
            nonlocal count
            raw = read(owner, directory, name, *args, **kwargs)
            if directory.path == primary:
                count += 1
                if count == 16:
                    self.save(directory.path / name, b"!" + raw[1:])
            return raw
        with patch.object(C.PrivateOwner, "read", changed), \
                self.assertRaisesRegex(C.ControllerError, "ABI_POST_RETURN_PACKET_CHANGED"):
            self.seal()
        self.assertEqual(count, 16)

    def test_primary_generated_live_outputs_may_change_after_retention_not_frozen_evidence(self):
        export = C.Controller.export
        def supplement_boundary(controller):
            self.assertEqual(controller.primary_abi["status"], "PASS")
            self.assertTrue((controller.evidence.path / "primary-abi/manifest.json").is_file())
            for path in C.abi.GENERATED:
                self.save(self.root / path, b"SYNTHETIC LATER OUTPUT; NOT AN ABI SUPPLEMENT RUN\n")
            return export(controller)
        with patch.object(C.Controller, "export", supplement_boundary):
            _session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=true\n")

    def test_full_original_log_mutation_is_detected_post_return(self):
        session, _result = self.execute_full()
        path = session / "state/evidence" / self.reserved / "product.stdout.log"
        self.save(path, path.read_bytes() + b"changed after primary return\n")
        # The copied-original fence now detects the changed log size before
        # the later semantic reassessment, with the same no-public-output rule.
        with self.assertRaisesRegex(C.ControllerError, "ABI_FROZEN_CANONICAL_ROSTER_DIFFERS"):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_full_retained_original_mutation_cannot_be_relabelled_by_result(self):
        session, result = self.execute_full()
        path = session / "evidence/primary-abi/generated-00.bin"
        self.save(path, b"!" + path.read_bytes()[1:])
        result["profilePassed"] = True
        self.save(session / "controller-result.json", result)
        with self.assertRaisesRegex(C.ControllerError, "ABI_FROZEN_ORIGINAL_DIFFERS"):
            self.seal()

    def test_coordinated_result_manifest_and_frozen_map_mutation_cannot_replace_export_return(self):
        session, result = self.execute_full()
        path = session / "evidence/primary-abi/manifest.json"
        manifest = C.parse(path.read_bytes())
        manifest["assessment"]["additive"]["preimageSha256"] = "f" * 64
        raw = self.save(path, manifest)
        result["primaryAbi"] = C.abi_disposition(raw)
        self.save(session / "controller-result.json", result)
        frozen = session / "frozen-evidence"
        mapping = C.parse((frozen / "original-path-map.json").read_bytes())
        for row in mapping["files"]:
            if row["original"] == "primary-abi/manifest.json":
                self.save(frozen / row["member"], raw)
                row.update(size=len(raw), sha256=C.digest(raw))
            elif row["original"] == "profile-result-before-export.json":
                before = C.parse((frozen / row["member"]).read_bytes())
                before["primaryAbi"] = result["primaryAbi"]
                before_raw = self.save(frozen / row["member"], before)
                row.update(size=len(before_raw), sha256=C.digest(before_raw))
        self.save(frozen / "original-path-map.json", mapping)
        # The forged copied profile already differs from its retained original;
        # reject before comparing the complete packet to the export return.
        with self.assertRaisesRegex(C.ControllerError, "ABI_FROZEN_ORIGINAL_PROVENANCE_DIFFERS"):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_coordinated_controller_and_export_return_mutation_still_requires_original_frozen_packet(self):
        session, result = self.execute_full()
        returned = C.parse((session / "runtime/export-result.json").read_bytes())
        returned["primaryAbiFrozen"]["manifestSha256"] = "f" * 64
        raw = self.save(session / "runtime/export-result.json", returned)
        result["exportReturn"] = {"result": returned, "sha256": C.digest(raw)}
        self.save(session / "controller-result.json", result)
        with self.assertRaisesRegex(C.ControllerError, "ABI_ORIGINAL_EXPORT_BINDING_CHANGED"):
            self.seal()

    def test_frozen_generated_copy_mutation_is_not_accepted_from_matching_live_output(self):
        session, _result = self.execute_full()
        frozen = session / "frozen-evidence"
        mapping = C.parse((frozen / "original-path-map.json").read_bytes())
        row = next(row for row in mapping["files"] if row["original"] == "primary-abi/generated-07.bin")
        path = frozen / row["member"]
        self.save(path, b"!" + path.read_bytes()[1:])
        with self.assertRaisesRegex(C.ControllerError, "ABI_FROZEN_PACKET_CHANGED"):
            self.seal()

    def test_original_reference_query_return_is_part_of_primary_binding(self):
        session, _result = self.execute_full()
        path = session / "evidence/primary-abi-queries/session-result.json"
        self.save(path, path.read_bytes() + b" ")
        # Exact original/copy equality precedes the manifest's reference hash.
        with self.assertRaisesRegex(C.ControllerError, "ABI_FROZEN_ORIGINAL_PROVENANCE_DIFFERS"):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_primary_retention_and_export_share_one_local_window_without_renewal(self):
        self.use_full()
        write = C.PrivateOwner.write
        original_end = []
        def late(owner, target, name, value, end):
            returned = write(owner, target, name, value, end)
            if name == "manifest.json" and target.path.name == "primary-abi":
                original_end.append(end)
                self.clock.now = end + 1
            return returned
        with patch.object(C.PrivateOwner, "write", late), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        controller = self.owners[-1]
        self.assertEqual(controller.export_freeze_end, original_end[0])
        self.assertEqual(controller.primary_abi["status"], "HOLD")
        self.assertFalse((controller.path / "export").exists())

    def test_primary_abi_raw_fence_expiry_after_query_close_blocks_export(self):
        self.use_full()
        factory = self.model_git_queries
        def late(*args, **kwargs):
            supplier = factory(*args, **kwargs)
            finalize = supplier._finalize
            def closed(error):
                finalize(error)
                if supplier.path.name == "primary-abi-queries":
                    self.clock.set_raw(self.owners[-1].budget.fence("export-freeze"))
            supplier._finalize = closed
            return supplier
        with patch.object(C.query, "NativeGitQueries", side_effect=late), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        controller = self.owners[-1]
        self.assertEqual(controller.primary_abi["status"], "HOLD")
        self.assertTrue(next(row for row in self.abi_query_sessions if row.path.name == "primary-abi-queries").closed)
        self.assertFalse((controller.path / "export").exists())

    def test_primary_retention_is_one_shot_and_not_authority_for_supplement_work(self):
        controller = self.full_controller()
        controller.product_run()
        controller.collect()
        controller.retire_simulator()
        controller.retain_primary_abi()
        first = controller.primary_abi.copy()
        with self.assertRaisesRegex(C.ControllerError, "ABI_PRIMARY_RETENTION_IS_ONE_SHOT"):
            controller.retain_primary_abi()
        self.assertEqual(controller.primary_abi, first)
        self.assertEqual(C.job_time.RESERVE_SECONDS, 2430)
        self.assertEqual(C.job_time.JOB_SECONDS, 3600)

    def test_generated_snapshot_rejects_links_hardlinks_writable_extras_and_empty_files(self):
        def change(case, _controller, mode):
            path = case.root / C.abi.GENERATED[0]
            if mode == "file-link":
                saved = case.path / "original-api"
                path.rename(saved)
                path.symlink_to(saved)
            elif mode == "hardlink":
                os.link(path, case.path / "extra-hardlink")
            elif mode == "writable":
                path.chmod(0o666)
            elif mode == "extra":
                case.save(path.parent / "unexpected.api", b"extra")
            else:
                case.save(path, b"")
        for mode in ("file-link", "hardlink", "writable", "extra", "empty"):
            with self.subTest(mode=mode):
                self.abi_failure_subcase(lambda case, controller: change(case, controller, mode), unknown=mode != "empty")

    def test_generated_ancestors_cannot_be_links_or_a_newly_adopted_build_owner(self):
        def change(case, _controller, mode):
            path = case.root / C.abi.GENERATED[0]
            selected = path.parent if mode == "subtree" else path.parent.parent if mode == "kotlin" else path.parents[2]
            saved = case.path / "moved-generated-parent"
            selected.rename(saved)
            if mode == "build":
                selected.mkdir(mode=0o700)
            else:
                selected.symlink_to(saved, target_is_directory=True)
        for mode in ("subtree", "kotlin", "build"):
            with self.subTest(mode=mode):
                self.abi_failure_subcase(lambda case, controller: change(case, controller, mode))

    def test_generated_growth_truncation_same_size_mutation_and_snapshot_drift_fail(self):
        def install(case, _controller, mode):
            opened = C.posix._open_member
            original_path = case.root / C.abi.GENERATED[0]
            class ChangedReader:
                def __init__(self, raw):
                    self.raw, self.first = raw, True
                def fileno(self):
                    return self.raw.fileno()
                def read(self, size):
                    result = self.raw.read(size)
                    if self.first and mode != "snapshot":
                        self.first = False
                        before = original_path.read_bytes()
                        case.save(original_path, before + b"x" if mode == "grow" else
                                  before[:-1] if mode == "truncate" else b"!" + before[1:])
                    return result
                def close(self):
                    self.raw.close()
                    if mode == "snapshot":
                        case.save(original_path, b"!" + original_path.read_bytes()[1:])
            def reader(root, name, snapshot):
                actual = opened(root, name, snapshot)
                return ChangedReader(actual) if root / name == original_path else actual
            case.stack.enter_context(patch.object(C.posix, "_open_member", reader))
        for mode in ("grow", "truncate", "same-size", "snapshot"):
            with self.subTest(mode=mode):
                self.abi_failure_subcase(lambda case, controller: install(case, controller, mode))

    def test_generated_reader_close_ambiguity_keeps_unknown_and_no_export(self):
        def install(case, _controller):
            opened = C.posix._open_member
            original_path = case.root / C.abi.GENERATED[0]
            def reader(root, name, snapshot):
                actual = opened(root, name, snapshot)
                if root / name != original_path:
                    return actual
                def close():
                    actual.close()
                    raise OSError("SYNTHETIC ABI READER CLOSE UNKNOWN")
                return SimpleNamespace(read=actual.read, fileno=actual.fileno, close=close)
            case.stack.enter_context(patch.object(C.posix, "_open_member", reader))
        self.abi_failure_subcase(install, unknown=True)

    def test_generated_copy_short_write_or_corrupt_readback_cannot_pass(self):
        def install(case, _controller, mode):
            if mode == "short":
                write = C.query._PosixSink.write
                def short(stream, raw):
                    return write(stream, raw[:-1] if stream.path.name == "generated-00.bin" else raw)
                case.stack.enter_context(patch.object(C.query._PosixSink, "write", short))
            else:
                read = C.query._PosixDirectory.read_bytes
                first = True
                def corrupt(directory, name, **kwargs):
                    nonlocal first
                    raw = read(directory, name, **kwargs)
                    if first and directory.path.name == "primary-abi" and name == "generated-00.bin":
                        first = False
                        return b"!" + raw[1:]
                    return raw
                case.stack.enter_context(patch.object(C.query._PosixDirectory, "read_bytes", corrupt))
        for mode in ("short", "readback"):
            with self.subTest(mode=mode):
                self.abi_failure_subcase(lambda case, controller: install(case, controller, mode))

    def test_strict_full_flags_are_required_in_actual_primary_platform_report(self):
        original = self.model_platform_reports
        def reports(folder, environment):
            rows = original(folder, environment)
            for row in rows:
                if row["source"].endswith(("/invocation.json", "/summary.json")):
                    path = folder / row["retained"]
                    value = C.parse(path.read_bytes())
                    value["command"].remove("--no-build-cache")
                    raw = self.save(path, value)
                    row.update(sha256=C.digest(raw), bytes=len(raw))
            self.save(folder / "report-manifest.json", {"schema": 1, "records": rows})
            return rows
        with patch.object(self, "model_platform_reports", side_effect=reports):
            session, result = self.execute_full()
        self.assertEqual(result["simulator"]["terminal"]["status"], "KNOWN_SHUTDOWN")
        self.assertFalse(result["profilePassed"])
        self.assertIn("ABI_PLATFORM_FULL_SELECTOR_OR_HOST_CHANGED", json.dumps(result["errors"]))
        self.assertEqual(len(list((session / "evidence/primary-abi").glob("generated-*.bin"))), 8)
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=false\n")

    def test_export_child_binds_same_abi_bytes_before_and_after_real_export_call(self):
        self.use_full()
        actual = self.model_export
        def changed(evidence, *args, **kwargs):
            result = actual(evidence, *args, **kwargs)
            mapping = C.parse((evidence / "original-path-map.json").read_bytes())
            row = next(row for row in mapping["files"] if row["original"] == "primary-abi/manifest.json")
            path = evidence / row["member"]
            self.save(path, path.read_bytes() + b" ")
            return result
        with patch.object(C.ordinary, "export_encrypted", side_effect=changed), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        self.assertTrue(self.owners[-1].unknown)
        self.assertFalse(self.owners[-1].result()["profilePassed"])
        self.assertTrue(self.crypto_child_errors)

    def copied_provenance_failure(self, layer, original_name, *, failed=False, map_change=None, reason=None):
        """Corrupt the actual copy seam, not the original or a mocked validation result."""
        case = WholeControllerModels("runTest")
        case.setUp()
        try:
            case.use_full()
            case.product_code = 7 if failed else 0
            actual_copy, observations = C.copy_tree, []
            def changed(owner, source, destination, end):
                copied = actual_copy(owner, source, destination, end)
                if copied.path.name != layer:
                    return copied
                path = copied.path / "original-path-map.json"
                mapping = C.parse(path.read_bytes())
                row = next(row for row in mapping["files"] if row["original"] == original_name)
                original = source.path / row["original"]
                before = original.read_bytes()
                self.assertEqual((copied.path / row["member"]).read_bytes(), before)
                observations.append((original, before))
                if map_change is None:
                    replacement = b"!" + before[1:]
                    case.save(copied.path / row["member"], replacement)
                    row.update(size=len(replacement), sha256=C.digest(replacement))
                else:
                    map_change(mapping, row)
                case.save(path, mapping)
                return copied
            with patch.object(C, "copy_tree", changed), redirect_stdout(io.StringIO()):
                self.assertEqual(case.call_run(), 125)
            self.assertEqual(len(observations), 1, "The intended copy corruption must actually execute")
            for original, before in observations:
                self.assertEqual(original.read_bytes(), before)
            controller = case.owners[-1]
            self.assertFalse(controller.encrypted)
            self.assertFalse(controller.result()["profilePassed"])
            self.assertFalse(controller.result()["readyForPostReturnSeal"])
            self.assertFalse((controller.path / "export").exists(), "Reject before invoking even the modeled exporter")
            self.assertEqual(len(case.crypto_child_errors), 1)
            operation, error = case.crypto_child_errors[0]
            self.assertEqual(operation, "export")
            self.assertIsInstance(error, C.ControllerError)
            self.assertEqual(str(error), reason or "ABI_FROZEN_ORIGINAL_PROVENANCE_DIFFERS")
            case.assert_refused_run_cannot_seal()
        finally:
            case.tearDown()

    def assert_refused_run_cannot_seal(self):
        # The explicit child refusal above made the controller nonzero/UNKNOWN;
        # its final check intentionally wrote no sealable controller receipt.
        # Check the REAL failed-step precondition, not an invented success label.
        self.assertFalse((self.owners[-1].path / "controller-result.json").exists())
        output = self.path / "public-step-output"
        output.touch(mode=0o600)
        with patch.dict(os.environ, {"P2PKIT_HOSTED_TEST_RUN_OUTCOME": "failure", "GITHUB_OUTPUT": str(output)}), \
                self.assertRaisesRegex(C.ControllerError, "ORIGINAL_CONTROLLER_DID_NOT_SUCCEED"):
            C.validate_public(self.profile)
        self.assertEqual(output.read_bytes(), b"")

    def test_each_copied_canonical_authority_must_equal_its_independent_original(self):
        names = ["receipt.json", "start.json", "report-manifest.json", "product.stdout.log"] + [
            "reports/build/reports/platform-tests/" + "e" * 32 + "/" + name + ".json"
            for name in ("invocation", "execution", "summary")]
        for name in names:
            with self.subTest(original=name):
                self.copied_provenance_failure("canonical-audit", self.reserved + "/" + name)

    def test_each_copied_direct_and_simulator_authority_must_equal_its_original(self):
        # Kept independent of the implementation's role list. Empty original
        # stderr/first-launch output is still evidence, not permission to omit it.
        names = ["canonical-context.json", "custody/request.json", "custody/result.json", "custody/uninstalled.json",
                 "custody/retained/owner-result.json", "primary-abi-queries/session-result.json",
                 "commands/product/start.json", "commands/product/result.json", "profile-result-before-export.json",
                 "primary-abi/manifest.json"]
        names += ["simulator/" + name + ".json" for name in
                  ("admission", "binding", "prelaunch", "canonical-start", "canonical-product", "launch", "retirement")]
        names += ["commands/" + label + "/" + name for label in
                  ("simulator-macos-version", "simulator-xcode-version", "simulator-first-launch", "simulator-runtimes",
                   "simulator-devices", "simulator-prelaunch", "simulator-retire-before", "simulator-shutdown",
                   "simulator-retire-after") for name in ("start.json", "result.json", "stdout.log", "stderr.log")]
        for name in names:
            with self.subTest(original=name):
                self.copied_provenance_failure("frozen-evidence", name)

    def test_failed_partial_retention_still_refuses_corrupted_copied_authority(self):
        for layer, name in (("canonical-audit", self.reserved + "/receipt.json"),
                            ("canonical-audit", self.reserved + "/product.stdout.log"),
                            ("frozen-evidence", "custody/result.json"),
                            ("frozen-evidence", "simulator/retirement.json")):
            with self.subTest(layer=layer, original=name):
                self.copied_provenance_failure(layer, name, failed=True)

    def test_both_copy_maps_require_exact_schema_roots_unique_roles_sizes_and_hashes(self):
        changes = {
            "root": (lambda mapping, _row: mapping.update(originalRoot=str(self.path)), "ABI_FROZEN_MAP_CHANGED"),
            "schema": (lambda mapping, _row: mapping.update(schema=True), "ABI_FROZEN_MAP_CHANGED"),
            "scope": (lambda mapping, _row: mapping.update(scope="UNTRUSTED_COPY"), "ABI_FROZEN_MAP_CHANGED"),
            "extra": (lambda mapping, _row: mapping.update(other=True), "ABI_FROZEN_MAP_CHANGED"),
            "alias": (lambda mapping, row: row.update(member=mapping["files"][0]["member"]), "ABI_FROZEN_MAP_ROSTER"),
            "role-alias": (lambda mapping, row: row.update(original=mapping["files"][0]["original"]),
                           "ABI_FROZEN_MAP_ROSTER"),
            "traversal": (lambda _mapping, row: row.update(original="../escape"), "ABI_FROZEN_MAP_ROSTER"),
            "member-path": (lambda _mapping, row: row.update(member="../escape"), "ABI_FROZEN_MAP_ROSTER"),
            "directory": (lambda mapping, _row: mapping["directories"].remove(""), "ABI_FROZEN_MAP_ROSTER"),
            "bool-size": (lambda _mapping, row: row.update(size=True), "ABI_FROZEN_MAP_ROSTER"),
            "negative-size": (lambda _mapping, row: row.update(size=-1), "ABI_FROZEN_MAP_ROSTER"),
            "invalid-hash": (lambda _mapping, row: row.update(sha256="X" * 64), "ABI_FROZEN_MAP_ROSTER"),
        }
        for layer, name in (("canonical-audit", self.reserved + "/start.json"),
                            ("frozen-evidence", "simulator/retirement.json")):
            for label, (change, reason) in changes.items():
                with self.subTest(layer=layer, change=label):
                    self.copied_provenance_failure(layer, name, map_change=change, reason=reason)
            for label, change in (("omitted", lambda mapping, row: mapping["files"].remove(row)),
                                  ("size", lambda _mapping, row: row.update(size=row["size"] + 1)),
                                  ("hash", lambda _mapping, row: row.update(sha256="0" * 64))):
                reason = ("ABI_FROZEN_CANONICAL_ROSTER_DIFFERS" if label != "hash" else
                          "ABI_FROZEN_CANONICAL_MAP_DIFFERS") if layer == "canonical-audit" else (
                          "ABI_FROZEN_MAP_MEMBERS_CHANGED" if label == "omitted" else
                          "ABI_FROZEN_PROVENANCE_BYTES_CHANGED")
                with self.subTest(layer=layer, change=label):
                    self.copied_provenance_failure(layer, name, map_change=change, reason=reason)

    def replace_frozen_provenance(self, session, name, *, canonical=False):
        """Self-consistent replacement through both maps after the original return."""
        frozen = session / "frozen-evidence"
        mapping_path = frozen / "original-path-map.json"
        outer = C.parse(mapping_path.read_bytes())
        nested_row = inner = inner_row = None
        if canonical:
            nested_row = next(row for row in outer["files"] if row["original"] == "canonical-audit/original-path-map.json")
            inner = C.parse((frozen / nested_row["member"]).read_bytes())
            inner_row = next(row for row in inner["files"] if row["original"] == self.reserved + "/" + name)
            name = "canonical-audit/" + inner_row["member"]
        row = next(row for row in outer["files"] if row["original"] == name)
        raw = (frozen / row["member"]).read_bytes()
        replacement = b"!" + raw[1:]
        self.save(frozen / row["member"], replacement)
        row.update(size=len(replacement), sha256=C.digest(replacement))
        if canonical:
            inner_row.update(size=len(replacement), sha256=C.digest(replacement))
            raw = self.save(frozen / nested_row["member"], inner)
            nested_row.update(size=len(raw), sha256=C.digest(raw))
        self.save(mapping_path, outer)

    def test_separate_seal_rechecks_both_layers_against_original_provenance(self):
        for canonical, name in ((True, "product.stdout.log"), (True, "receipt.json"),
                                 (False, "custody/result.json"), (False, "simulator/admission.json")):
            with self.subTest(canonical=canonical, original=name):
                case = WholeControllerModels("runTest")
                case.setUp()
                try:
                    session, result = case.execute_full()
                    self.assertTrue(result["profilePassed"])
                    case.replace_frozen_provenance(session, name, canonical=canonical)
                    with self.assertRaisesRegex(C.ControllerError, "ABI_FROZEN_ORIGINAL_PROVENANCE_DIFFERS"):
                        case.seal()
                    self.assertEqual((case.path / "public-step-output").read_bytes(), b"")
                finally:
                    case.tearDown()

    def test_export_child_rechecks_copied_provenance_after_the_exporter_returns(self):
        self.use_full()
        actual = self.model_export
        def changed(evidence, *args, **kwargs):
            result = actual(evidence, *args, **kwargs)
            self.replace_frozen_provenance(evidence.parent, "receipt.json", canonical=True)
            return result
        with patch.object(C.ordinary, "export_encrypted", side_effect=changed), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        self.assertEqual(str(self.crypto_child_errors[0][1]), "ABI_FROZEN_ORIGINAL_PROVENANCE_DIFFERS")
        self.assertFalse(self.owners[-1].encrypted)
        self.assertFalse(self.owners[-1].result()["profilePassed"])
        self.assert_refused_run_cannot_seal()

    def test_bound_provenance_includes_original_canonical_log_tasks_and_all_simulator_phases(self):
        session, result = self.execute_full()
        proof = result["exportReturn"]["result"]["primaryAbiFrozen"]["provenance"]
        self.assertEqual(proof["contextSha256"], result["contextSha256"])
        self.assertEqual(proof["canonicalMapSha256"],
                         C.digest((session / "evidence/canonical-audit/original-path-map.json").read_bytes()))
        names = [row["original"] for row in proof["originals"]]
        self.assertEqual(len(names), len(set(names)))
        log = next(row for row in proof["originals"] if row["original"].endswith("/product.stdout.log"))
        self.assertEqual(log["original"], "state/evidence/" + self.reserved + "/product.stdout.log")
        self.assertEqual(log["log"], C.parse((session / "evidence/primary-abi/manifest.json").read_bytes())["assessment"]["log"])
        self.assertEqual(len(log["log"]["tasks"]), 32)
        self.assertTrue(all(row["present"] for row in proof["originals"]))
        self.assertEqual(len(names), 60)  # 53 direct/context +7 original canonical roles.
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=true\n")

    def test_original_and_frozen_provenance_cannot_change_after_their_bounded_read(self):
        for change_original in (True, False):
            with self.subTest(original=change_original):
                case = WholeControllerModels("runTest")
                case.setUp()
                try:
                    session, _result = case.execute_full()
                    owner = case.owner()
                    private = owner.open(session)
                    mapping = C.parse((session / "frozen-evidence/original-path-map.json").read_bytes())
                    row = next(row for row in mapping["files"] if row["original"] == "custody/result.json")
                    target = (session / "evidence/custody/result.json" if change_original else
                              session / "frozen-evidence" / row["member"])
                    read, changed = C.PrivateOwner.read, []
                    def mutation(reader, parent, name, *args, **kwargs):
                        raw = read(reader, parent, name, *args, **kwargs)
                        if parent.path / name == target and not changed:
                            changed.append(True)
                            case.save(target, b"!" + raw[1:])
                        return raw
                    reason = "ABI_ORIGINAL_PROVENANCE_CHANGED" if change_original else "ABI_FROZEN_MAP_CHANGED"
                    with patch.object(C.PrivateOwner, "read", mutation), self.assertRaisesRegex(C.ControllerError, reason):
                        C.frozen_abi_packet(owner, private, case.clock.now + 45)
                    self.assertEqual(changed, [True])
                    self.assertFalse(owner.unknown)
                    owner.close()
                finally:
                    case.tearDown()

    def test_frozen_provenance_reader_failure_preserves_original_and_unknown(self):
        session, _result = self.execute_full()
        owner = self.owner()
        private = owner.open(session)
        mapping = C.parse((session / "frozen-evidence/original-path-map.json").read_bytes())
        row = next(row for row in mapping["files"] if row["original"] == "custody/result.json")
        actual, reached = C.query._PosixDirectory.read_bytes, []
        failure = OSError("SYNTHETIC_COPIED_AUTHORITY_OPAQUE_READER_FAILURE")
        def failed(parent, name, **kwargs):
            if parent.path == session / "frozen-evidence" and name == row["member"]:
                reached.append(True)
                raise failure
            return actual(parent, name, **kwargs)
        with patch.object(C.query._PosixDirectory, "read_bytes", failed), self.assertRaises(OSError) as caught:
            C.frozen_abi_packet(owner, private, self.clock.now + 45)
        self.assertIs(caught.exception, failure)
        self.assertEqual(reached, [True])
        self.assertTrue(owner.unknown)
        self.assertIs(owner.original, failure)
        with self.assertRaisesRegex(C.ControllerError, "CONTROLLER_RESOURCE_RETIREMENT_UNKNOWN"):
            owner.close()

    def test_frozen_large_log_uses_streaming_and_preserves_original_task_observations(self):
        child = self.model_child
        def large(argv, environment):
            child(argv, environment)
            if "--cwd" in argv:
                path = C.session_path("full", "macos-arm64") / "state/evidence" / self.reserved / "product.stdout.log"
                self.save(path, path.read_bytes() + (b"n" * 1023 + b"\n") * 5120)
        log, opened, active = C.primary_abi_log, C.posix._open_member, []
        reads, closed = [], []
        def observe(owner, directory, end, **kwargs):
            active.append(directory.path.name == "frozen-evidence")
            try:
                return log(owner, directory, end, **kwargs)
            finally:
                active.pop()
        def stream(root, name, snapshot):
            original = opened(root, name, snapshot)
            if not active:
                return original
            copied = active[-1]
            class Reader:
                def read(_self, size):
                    self.assertLessEqual(size, 64 * 1024)
                    reads.append((copied, size))
                    return original.read(size)
                def fileno(_self):
                    return original.fileno()
                def close(_self):
                    original.close()
                    closed.append(copied)
            return Reader()
        with patch.object(self, "model_child", side_effect=large), patch.object(C, "primary_abi_log", observe), \
                patch.object(C.posix, "_open_member", stream):
            session, result = self.execute_full()
            self.assertTrue(result["profilePassed"])
            self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=true\n")
        evidence = C.parse((session / "evidence/primary-abi/manifest.json").read_bytes())["assessment"]["log"]
        self.assertGreater(evidence["bytes"], C.RECORD_LIMIT)
        self.assertEqual(len(evidence["tasks"]), 32)
        self.assertGreater(sum(copied for copied, _size in reads), 80)
        self.assertGreater(closed.count(True), 0)
        self.assertGreater(closed.count(False), 0)

    def test_copied_log_read_error_and_secondary_close_ambiguity_never_return_a_packet(self):
        session, _result = self.execute_full()
        owner = self.owner()
        private = owner.open(session)
        opened, reached, closed = C.posix._open_member, [], []
        failure = ValueError("SYNTHETIC_COPIED_LOG_READ_FAILURE")
        def broken(root, name, snapshot):
            original = opened(root, name, snapshot)
            if root != session / "frozen-evidence":
                return original
            reached.append(name)
            class Reader:
                def read(_self, _size):
                    raise failure
                def fileno(_self):
                    return original.fileno()
                def close(_self):
                    original.close()
                    closed.append(name)
                    raise OSError("SYNTHETIC_COPIED_LOG_CLOSE_UNKNOWN")
            return Reader()
        # Only the log reader uses this low-level seam here; small records use
        # the unchanged private read_bytes supplier, not a replacement backend.
        with patch.object(C.posix, "_open_member", broken), self.assertRaises(ValueError) as caught:
            C.frozen_abi_packet(owner, private, self.clock.now + 45)
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(reached), 1)
        self.assertEqual(closed, reached)
        self.assertTrue(owner.unknown)
        self.assertIs(owner.original, failure)
        self.assertIn("SYNTHETIC_COPIED_LOG_CLOSE_UNKNOWN", json.dumps(owner.errors))
        with self.assertRaisesRegex(C.ControllerError, "CONTROLLER_RESOURCE_RETIREMENT_UNKNOWN"):
            owner.close()

    def test_provenance_reads_keep_original_deadline_and_check_after_copied_log_close(self):
        session, _result = self.execute_full()
        owner = self.owner()
        private = owner.open(session)
        end = self.clock.now + 45
        opened, reached = C.posix._open_member, []
        def delayed(root, name, snapshot):
            original = opened(root, name, snapshot)
            if root != session / "frozen-evidence":
                return original
            class Reader:
                def read(_self, size):
                    return original.read(size)
                def fileno(_self):
                    return original.fileno()
                def close(_self):
                    original.close()
                    reached.append(name)
                    self.clock.now = end
            return Reader()
        read, deadlines = C.PrivateOwner.read, []
        def observe(reader, parent, name, deadline, *args, **kwargs):
            deadlines.append(deadline)
            return read(reader, parent, name, deadline, *args, **kwargs)
        with patch.object(C.posix, "_open_member", delayed), patch.object(C.PrivateOwner, "read", observe), \
                self.assertRaisesRegex(C.posix.EvidenceError, "exceeded its deadline"):
            C.frozen_abi_packet(owner, private, end)
        self.assertEqual(len(reached), 1)
        self.assertEqual(set(deadlines), {end})
        self.assertFalse(owner.unknown)
        owner.close()

    def test_copied_log_close_ambiguity_alone_never_returns_a_packet(self):
        session, _result = self.execute_full()
        owner = self.owner()
        private = owner.open(session)
        opened, closed = C.posix._open_member, []
        failure = OSError("SYNTHETIC_COPIED_LOG_CLOSE_ONLY_UNKNOWN")
        def ambiguous(root, name, snapshot):
            original = opened(root, name, snapshot)
            if root != session / "frozen-evidence":
                return original
            class Reader:
                def read(_self, size):
                    return original.read(size)
                def fileno(_self):
                    return original.fileno()
                def close(_self):
                    original.close()
                    closed.append(name)
                    raise failure
            return Reader()
        with patch.object(C.posix, "_open_member", ambiguous), \
                self.assertRaisesRegex(C.ControllerError, "ABI_ORIGINAL_LOG_CHANGED_OR_UNCLOSED"):
            C.frozen_abi_packet(owner, private, self.clock.now + 45)
        self.assertEqual(len(closed), 1)
        self.assertIs(owner.original, failure)
        self.assertTrue(owner.unknown)
        with self.assertRaisesRegex(C.ControllerError, "CONTROLLER_RESOURCE_RETIREMENT_UNKNOWN"):
            owner.close()

    def test_known_absent_provenance_cannot_appear_during_packet_verification(self):
        self.product_boots_simulator = False
        session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        owner = self.owner()
        private = owner.open(session)
        added = session / "evidence/commands/simulator-shutdown"
        self.assertFalse(added.exists())
        read, reached = C.PrivateOwner.read, []
        def appeared(reader, parent, name, *args, **kwargs):
            raw = read(reader, parent, name, *args, **kwargs)
            if parent.path == session / "evidence/commands/simulator-retire-after" and name == "result.json":
                reached.append(True)
                added.mkdir(mode=0o700)
                self.save(added / "result.json", b"SYNTHETIC_LATE_UNBOUND_ORIGINAL")
            return raw
        with patch.object(C.PrivateOwner, "read", appeared), \
                self.assertRaisesRegex(C.ControllerError, "ABI_ORIGINAL_PROVENANCE_APPEARED"):
            C.frozen_abi_packet(owner, private, self.clock.now + 45)
        self.assertEqual(reached, [True])
        self.assertFalse(owner.unknown)
        owner.close()

    def test_full_admits_before_loader_and_binds_then_retires_only_exact_uuid(self):
        session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        labels = [row["phase"] for row in result["phases"]]
        self.assertEqual(labels, ["job-time", "recipient-validation", "audit-init", *C.simulator.PREPARE,
            "custody-prepare", C.simulator.PRELAUNCH, "product", "custody-collect", "custody-uninstall", *C.simulator.RETIRE, "export"])
        shutdown = [argv for label, argv in self.simulator_calls if label == C.simulator.SHUTDOWN]
        self.assertEqual(shutdown, [["/usr/bin/xcrun", "simctl", "shutdown", self.simulator_uuid]])
        terminal = result["simulator"]["terminal"]
        self.assertEqual(terminal["before"]["state"], "Booted")
        self.assertEqual(terminal["after"]["state"], "Shutdown")
        self.assertEqual(terminal["coverage"]["productInvocation"], self.reserved)
        raw = (session / C.simulator.RELATIVE).read_bytes()
        binding = C.parse(raw)
        self.assertEqual(binding["source"], self.clean_source)
        self.assertEqual(binding["productInvocation"], self.reserved)
        self.assertEqual(binding["job"], self.job)
        self.assertEqual(binding["selected"]["device"]["state"], "Shutdown")
        product = next(row for row in self.calls if "--cwd" in row["argv"])
        self.assertEqual(product["environment"][C.simulator.PATH_ENV], str(session / C.simulator.RELATIVE))
        self.assertEqual(product["environment"][C.simulator.HASH_ENV], C.digest(raw))
        for row in self.calls:
            if "--cwd" not in row["argv"]:
                self.assertNotIn(C.simulator.PATH_ENV, row["environment"])
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=true\n")
        mapping = C.parse((session / "frozen-evidence/original-path-map.json").read_bytes())["files"]
        names = {row["original"] for row in mapping}
        self.assertTrue({"simulator/admission.json", "simulator/binding.json", "simulator/prelaunch.json",
                         "simulator/canonical-start.json", "simulator/canonical-product.json", "simulator/launch.json",
                         "simulator/retirement.json"} <= names)
        self.assertTrue(all("commands/" + label + "/stdout.log" in names
                            for label in (*C.simulator.PREPARE, C.simulator.PRELAUNCH, *C.simulator.RETIRE)))
        retained = {row["original"]: row for row in mapping}
        for name in ("canonical-start.json", "canonical-product.json", "launch.json", "prelaunch.json"):
            with self.subTest(original=name):
                row = retained["simulator/" + name]
                copied = (session / "frozen-evidence" / row["member"]).read_bytes()
                self.assertEqual(copied, (session / "evidence/simulator" / name).read_bytes())
                self.assertEqual((len(copied), C.digest(copied)), (row["size"], row["sha256"]))

    def test_full_originally_booted_device_is_not_adopted(self):
        self.simulator_state("Booted")
        _session, result = self.execute_full()
        self.assertFalse(result["profilePassed"])
        self.assertFalse(result["productAttempted"])
        self.assertFalse(any(label in C.simulator.RETIRE for label, _argv in self.simulator_calls))
        self.assertFalse(any("prepare" in row["argv"] for row in self.calls))
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=false\n")

    def test_full_old_writer_xcode_is_not_ordinary_admission(self):
        self.simulator_outputs["simulator-xcode-version"] = b"Xcode 16.2\nBuild version 16C5032a\n"
        _session, result = self.execute_full()
        self.assertFalse(result["profilePassed"])
        self.assertFalse(result["productAttempted"])
        self.assertEqual([label for label, _argv in self.simulator_calls],
                         ["simulator-macos-version", "simulator-xcode-version"])
        self.assertFalse(any("prepare" in row["argv"] for row in self.calls))

    def test_full_first_launch_nonzero_cannot_be_ignored(self):
        self.simulator_codes["simulator-first-launch"] = 76
        session, result = self.execute_full()
        self.assertFalse(result["profilePassed"])
        self.assertFalse(result["productAttempted"])
        row = C.parse((session / "evidence/commands/simulator-first-launch/result.json").read_bytes())
        self.assertEqual(row["exitCode"], 76)
        self.assertEqual(row["retirement"], "KNOWN")
        self.assertFalse(any(label == "simulator-runtimes" for label, _argv in self.simulator_calls))

    def test_full_wrong_runtime_refuses_before_device_inventory_or_loader(self):
        self.simulator_runtimes["runtimes"][0]["version"] = "26.2"
        _session, result = self.execute_full()
        self.assertFalse(result["profilePassed"])
        self.assertFalse(any("prepare" in row["argv"] or "--cwd" in row["argv"] for row in self.calls))
        self.assertNotIn("simulator-devices", [label for label, _argv in self.simulator_calls])

    def test_full_no_boot_still_requires_both_retirement_inventories(self):
        self.product_boots_simulator = False
        _session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        self.assertEqual([label for label, _argv in self.simulator_calls if label in C.simulator.RETIRE],
                         [C.simulator.BEFORE, C.simulator.AFTER])
        self.assertFalse(result["simulator"]["terminal"]["shutdownAttempted"])
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=true\n")

    def test_full_failed_product_still_retires_owned_uuid_and_stays_failed(self):
        self.product_code = 23
        _session, result = self.execute_full()
        self.assertFalse(result["profilePassed"])
        self.assertEqual(result["simulator"]["terminal"]["status"], "KNOWN_SHUTDOWN")
        self.assertTrue(result["simulator"]["terminal"]["shutdownAttempted"])
        self.assertIsNone(result["simulator"]["terminal"]["coverage"])
        self.assertFalse(any("model-loader" in str(row["argv"]) for row in self.calls))
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=false\n")

    def test_full_failed_profile_cannot_seal_reordered_original_simulator_phases(self):
        self.product_code = 23
        session, result = self.execute_full()
        self.assertFalse(result["profilePassed"])
        phases = result["phases"]
        first = next(index for index, row in enumerate(phases) if row["phase"] == C.simulator.BEFORE)
        phases[first], phases[first + 1] = phases[first + 1], phases[first]
        self.save(session / "controller-result.json", result)
        with self.assertRaisesRegex(C.ControllerError, "PHASE_SEQUENCE_CHANGED"):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_full_failed_profile_cannot_seal_overlapping_raw_phase_intervals(self):
        self.product_code = 23
        session, result = self.execute_full()
        row = next(row for row in result["phases"] if row["phase"] == C.simulator.BEFORE)
        row["startedRawNs"] -= 1  # Still internally ordered, but precedes the previous finalized phase.
        directory = session / "evidence/commands" / C.simulator.BEFORE
        start = C.parse((directory / "start.json").read_bytes())
        start["startedRawNs"] = row["startedRawNs"]
        self.save(directory / "start.json", start)
        raw = self.save(directory / "result.json", row)
        result["phaseSha256"][C.simulator.BEFORE] = C.digest(raw)
        terminal = result["simulator"]["terminal"]
        terminal["phases"][C.simulator.BEFORE]["phaseSha256"] = C.digest(raw)
        self.save(session / "evidence/simulator/retirement.json", terminal)
        self.save(session / "controller-result.json", result)
        with self.assertRaisesRegex(C.ControllerError, "PHASE_RAW_SEQUENCE_CHANGED"):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_full_no_launch_external_change_never_authorizes_shutdown(self):
        controller = self.full_controller()
        self.simulator_state("Booted")
        with self.assertRaisesRegex(C.ControllerError, "SIMULATOR_UNLAUNCHED_EXTERNAL_STATE_CHANGE"):
            controller.retire_simulator()
        self.assertFalse(controller.product_attempted)
        self.assertTrue(controller.unknown)
        self.assertFalse(any(label == C.simulator.SHUTDOWN for label, _argv in self.simulator_calls))
        self.assertEqual([label for label, _argv in self.simulator_calls if label in C.simulator.RETIRE],
                         [C.simulator.BEFORE, C.simulator.AFTER])
        self.assertEqual(controller.simulator_terminal["after"]["state"], "Booted")

    def test_full_no_launch_unchanged_device_can_be_proven_shutdown_without_mutation(self):
        controller = self.full_controller()
        controller.retire_simulator()
        self.assertFalse(controller.product_attempted)
        self.assertEqual(controller.simulator_terminal["status"], "KNOWN_SHUTDOWN")
        self.assertFalse(controller.simulator_terminal["shutdownAttempted"])
        self.assertFalse(controller.result()["profilePassed"])
        controller.close()

    def test_full_external_boot_during_custody_prepare_is_never_adopted(self):
        self.use_full()
        self.product_boots_simulator = False
        model = self.model_child
        def external(argv, environment):
            model(argv, environment)
            if "prepare" in argv:
                self.simulator_state("Booted")
        with patch.object(self, "model_child", side_effect=external), \
                patch.object(C.shutil, "which", return_value=sys.executable), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        controller = self.owners[-1]
        self.assertFalse(controller.product_attempted)
        self.assertFalse(controller.result()["profilePassed"])
        self.assertFalse(any(label == C.simulator.SHUTDOWN for label, _argv in self.simulator_calls))
        self.assertFalse((controller.path / "export").exists())

    def test_full_outer_spawn_attempt_without_a_created_child_never_authorizes_shutdown(self):
        controller = self.full_controller()
        spawn = Scope.spawn
        failure = OSError("SYNTHETIC_SPAWN_FAILED_BEFORE_CHILD_CREATION")
        def failed(scope, argv, cwd, environment, **sinks):
            if "--cwd" in argv:
                self.simulator_state("Booted")  # External transition after the prelaunch observation.
                raise failure
            return spawn(scope, argv, cwd, environment, **sinks)
        with patch.object(Scope, "spawn", failed), self.assertRaises(OSError) as caught:
            controller.product_run()
        self.assertIs(caught.exception, failure)
        product = next(row for row in controller.records if row["phase"] == "product")
        self.assertTrue(product["launchAttempted"])
        self.assertEqual(product["ownership"]["launches"], [])
        self.assertIsNone(controller.simulator_authority)
        with self.assertRaisesRegex(C.ControllerError, "SIMULATOR_UNLAUNCHED_EXTERNAL_STATE_CHANGE"):
            controller.retire_simulator()
        self.assertIs(controller.original, failure)
        self.assertFalse(any(label == C.simulator.SHUTDOWN for label, _argv in self.simulator_calls))

    def test_full_created_outer_bootstrap_without_actual_start_never_authorizes_shutdown(self):
        controller = self.full_controller()
        model = self.model_child
        def bootstrap_failure(argv, environment):
            if "--cwd" in argv:
                self.simulator_state("Booted")
                self.exit_code = 2
            else:
                model(argv, environment)
        with patch.object(self, "model_child", side_effect=bootstrap_failure), self.assertRaises(FileNotFoundError):
            controller.product_run()
        product = next(row for row in controller.records if row["phase"] == "product")
        self.assertTrue(product["ownership"]["launches"][0]["created"])
        self.assertIsNone(controller.simulator_authority)
        self.assertTrue(controller.unknown)  # Existing opaque-reader failure policy is not weakened for cleanup.
        with self.assertRaisesRegex(C.ControllerError, "PRIOR_NATIVE_RETIREMENT_UNKNOWN"):
            controller.retire_simulator()
        self.assertFalse(any(label in C.simulator.RETIRE for label, _argv in self.simulator_calls))

    def test_full_allocated_start_without_created_canonical_product_grants_no_authority(self):
        controller = self.full_controller()
        model = self.model_child
        def failed_product_start(argv, environment):
            model(argv, environment)
            if "--cwd" in argv:
                path = controller.state_path / "evidence" / self.reserved / "receipt.json"
                value = C.parse(path.read_bytes())
                value["ownership"]["launches"] = []
                self.save(path, value)
        with patch.object(self, "model_child", side_effect=failed_product_start), \
                self.assertRaisesRegex(ValueError, "SIMULATOR_NATIVE_LAUNCH_REQUIRED"):
            controller.product_run()
        self.assertIsNone(controller.simulator_authority)
        with self.assertRaisesRegex(C.ControllerError, "SIMULATOR_UNLAUNCHED_EXTERNAL_STATE_CHANGE"):
            controller.retire_simulator()
        self.assertFalse(any(label == C.simulator.SHUTDOWN for label, _argv in self.simulator_calls))

    def damaged_owned_receipt(self, relative):
        controller = self.full_controller()
        controller.product_run()
        controller.collect()
        authority = controller.simulator_authority
        self.assertIsNotNone(authority)
        path = controller.path / relative
        self.save(path, path.read_bytes() + b" ")
        with self.assertRaises(C.ControllerError):
            controller.retire_simulator()
        self.assertEqual(controller.simulator_authority, authority)
        self.assertEqual(controller.simulator_terminal["after"]["state"], "Shutdown")
        self.assertEqual(controller.simulator_terminal["cleanupStatus"], "KNOWN_SHUTDOWN")
        self.assertEqual(controller.simulator_terminal["status"], "HOLD")
        self.assertTrue(controller.unknown)
        self.assertFalse(controller.result()["profilePassed"])
        self.assertEqual([argv for label, argv in self.simulator_calls if label == C.simulator.SHUTDOWN],
                         [["/usr/bin/xcrun", "simctl", "shutdown", self.simulator_uuid]])
        self.assertFalse((controller.path / "export").exists())

    def test_full_postproduct_admission_damage_keeps_hold_but_retires_owned_uuid(self):
        self.damaged_owned_receipt("evidence/simulator/admission.json")

    def test_full_postproduct_actual_start_damage_keeps_hold_but_retires_owned_uuid(self):
        self.damaged_owned_receipt("state/evidence/" + self.reserved + "/start.json")

    def test_full_mutated_reservation_refuses_before_product_scope(self):
        controller = self.full_controller()
        path = controller.path / C.simulator.RELATIVE
        value = C.parse(path.read_bytes())
        value["productInvocation"] = "f" * 32
        self.save(path, value)
        self.events.clear()
        with self.assertRaisesRegex(C.ControllerError, "SIMULATOR_PRIMARY_BINDING_CHANGED"):
            controller.product_run()
        self.assertNotIn("scope", self.events)
        self.assertFalse(controller.product_attempted)

    def test_full_shutdown_failure_captures_terminal_inventory_but_never_exports(self):
        self.use_full()
        self.simulator_codes[C.simulator.SHUTDOWN] = 23
        with patch.object(C.shutil, "which", return_value=sys.executable), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        controller = self.owners[-1]
        self.assertTrue(controller.unknown)
        self.assertEqual(controller.simulator_terminal["retirement"], "UNKNOWN")
        self.assertTrue(any(label == C.simulator.AFTER for label, _argv in self.simulator_calls))
        self.assertTrue((controller.path / "evidence/commands/simulator-shutdown/result.json").is_file())
        self.assertFalse((controller.path / "export").exists())

    def test_full_unknown_simulator_native_close_never_allows_next_phase_or_export(self):
        self.use_full()
        close = Scope.close
        def unknown(scope):
            close(scope)
            if self.calls[-1]["stdout"].path.parent.name == C.simulator.BEFORE:
                raise OSError("synthetic simulator-query close unknown")
        with patch.object(Scope, "close", unknown), patch.object(C.shutil, "which", return_value=sys.executable), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        controller = self.owners[-1]
        self.assertTrue(controller.unknown)
        self.assertFalse(any(label in (C.simulator.SHUTDOWN, C.simulator.AFTER) for label, _argv in self.simulator_calls))
        self.assertFalse((controller.path / "export").exists())

    def test_full_late_terminal_query_zero_cannot_authorize_export(self):
        self.use_full()
        model = self.model_child
        def late(argv, environment):
            model(argv, environment)
            if self.calls[-1]["stdout"].path.parent.name == C.simulator.AFTER:
                self.clock.set_raw(self.owners[-1].budget.fence(C.simulator.AFTER))
        with patch.object(self, "model_child", side_effect=late), patch.object(C.shutil, "which", return_value=sys.executable), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        self.assertTrue(self.owners[-1].unknown)
        self.assertFalse(self.owners[-1].result()["profilePassed"])
        self.assertFalse((self.owners[-1].path / "export").exists())

    def test_full_late_retirement_record_keeps_provisional_receipt_but_actual_hold(self):
        self.use_full()
        write = C.PrivateOwner.write
        def late(owner, directory, name, value, end):
            result = write(owner, directory, name, value, end)
            if name == "retirement.json":
                self.clock.set_raw(self.owners[-1].budget.fence("simulator-retirement"))
            return result
        with patch.object(C.PrivateOwner, "write", late), patch.object(C.shutil, "which", return_value=sys.executable), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        controller = self.owners[-1]
        provisional = C.parse((controller.path / "evidence/simulator/retirement.json").read_bytes())
        self.assertEqual(provisional["status"], "KNOWN_SHUTDOWN")
        self.assertEqual(controller.simulator_terminal["status"], "HOLD")
        self.assertTrue(controller.unknown)
        self.assertFalse((controller.path / "export").exists())

    def test_full_terminal_original_mutation_cannot_seal_even_with_green_boolean(self):
        session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        path = session / "evidence/commands" / C.simulator.AFTER / "stdout.log"
        terminal = C.parse(path.read_bytes())
        terminal["devices"][self.simulator_runtime][0]["state"] = "Booted"
        self.save(path, terminal)
        with self.assertRaises(C.ControllerError):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_full_post_return_actual_start_mutation_cannot_seal(self):
        session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        path = session / "state/evidence" / self.reserved / "start.json"
        self.save(path, path.read_bytes() + b" ")
        with self.assertRaisesRegex(C.ControllerError, "SIMULATOR_LAUNCH_ORIGINALS_CHANGED"):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_full_post_return_launch_authority_copy_mutation_cannot_seal(self):
        session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        path = session / "evidence/simulator/launch.json"
        self.save(path, path.read_bytes() + b" ")
        with self.assertRaisesRegex(C.ControllerError, "SIMULATOR_LAUNCH_ORIGINALS_CHANGED"):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_full_post_return_prelaunch_inventory_mutation_cannot_seal(self):
        session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        path = session / "evidence/commands" / C.simulator.PRELAUNCH / "stdout.log"
        value = C.parse(path.read_bytes())
        value["devices"][self.simulator_runtime][0]["state"] = "Booted"
        self.save(path, value)
        with self.assertRaisesRegex(ValueError, "SIMULATOR_PRELAUNCH_EXTERNAL_STATE_CHANGE"):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_full_post_return_shutdown_cannot_drop_its_actual_launch_authority(self):
        session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        result["simulator"]["terminal"]["launchAuthoritySha256"] = None
        self.save(session / "controller-result.json", result)
        self.save(session / "evidence/simulator/retirement.json", result["simulator"]["terminal"])
        with self.assertRaisesRegex(C.ControllerError, "SEALED_SIMULATOR_SHUTDOWN_WITHOUT_LAUNCH"):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_full_missing_retirement_receipt_is_not_reconstructed_from_result_boolean(self):
        session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        (session / "evidence/simulator/retirement.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_full_original_admission_cannot_be_rebound_to_another_device(self):
        session, _result = self.execute_full()
        path = session / "evidence/simulator/admission.json"
        value = C.parse(path.read_bytes())
        value["selected"]["device"]["udid"] = "BBBBBBBB-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
        self.save(path, value)
        with self.assertRaisesRegex(C.ControllerError, "SIMULATOR_ADMISSION_ORIGINALS_CHANGED"):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")

    def test_full_missing_generated_property_evidence_blocks_export_not_just_label(self):
        self.use_full()
        model = self.model_platform_reports
        def missing(folder, environment):
            model(folder, environment)
            return []
        with patch.object(self, "model_platform_reports", side_effect=missing), \
                patch.object(C.shutil, "which", return_value=sys.executable), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        self.assertFalse(self.owners[-1].result()["profilePassed"])
        self.assertFalse((self.owners[-1].path / "export").exists())

    def test_full_without_service_job_time_refuses_before_crypto_or_init(self):
        self.profile = "full"
        record = C.parse(self.admitted.record)
        record.update(profile="full", suites=["cli", "diagnostics"])
        self.admitted = C.identity.Admission(C.encoded(record), self.admitted.original_event,
            self.admitted.original_policy, self.public_key, "A" * 40, C.digest(self.public_key), 2000000000)
        os.environ.pop("P2PKIT_ACTIONS_READ_TOKEN", None)
        with patch.object(C.shutil, "which", return_value=sys.executable), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        self.assertFalse(any("_crypto" in row["argv"] or "init" in row["argv"] or "--cwd" in row["argv"]
                             for row in self.calls))

    def test_full_raw_cutoff_before_product_spawn_never_launches_product(self):
        controller = self.full_controller()
        self.events.clear()
        self.calls.clear()
        reached = []
        def slow_scope(*args):
            if args[0] != self.job:
                return Scope(self, *args)
            # New prelaunch query is independently drained before this same
            # original product-scope cutoff. Keep assertions on its own trace.
            self.events.clear()
            self.calls.clear()
            reached.append("product")
            scope = Scope(self, *args)
            self.clock.set_raw(controller.budget.fence("productive"))
            return scope
        with patch.object(C.processes, "make_scope", side_effect=slow_scope), \
                patch.object(C.audit, "request_cancellation", side_effect=self.model_cancellation), \
                self.assertRaises(C.ControllerError):
            controller.product_run()
        self.assertEqual(reached, ["product"])
        self.assertNotIn("spawn", self.events)
        self.assertFalse(any("--cwd" in row["argv"] for row in self.calls))
        self.assertTrue(controller.budget_exhausted)

    def test_full_delayed_cutoff_retains_exact_request_before_drain_in_final_window(self):
        controller = self.full_controller()
        self.events.clear()
        polls = []
        def delayed_poll():
            polls.append(self.clock.raw())
            self.clock.set_raw(controller.budget.fence("product-return") + C.job_time.NS)
            return 0
        self.inject_product_poll(delayed_poll)
        with patch.object(C.audit, "request_cancellation", side_effect=self.model_cancellation) as cancellation, \
                self.assertRaises(C.ControllerError):
            controller.product_run()
        cancellation.assert_called_once_with(controller.state_path, self.job, self.reserved)
        self.assertLess(self.events.index("cooperative-cancellation"), self.events.index("drain"))
        original = (controller.state_path / "cancellations" / (self.reserved + ".json")).read_bytes()
        retained = controller.path / "evidence/job-time/product-cancellation.json"
        self.assertEqual(retained.read_bytes(), original)
        self.assertEqual(controller.budget_cancellation["requestSha256"], C.digest(original))
        self.assertTrue(controller.budget_exhausted)
        self.assertFalse(controller.result()["profilePassed"])
        self.assertEqual(len(polls), 1)

    def test_full_finalizing_phase_rechecks_raw_work_fence_before_accepting_exit_zero(self):
        controller = self.full_controller()
        controller.product_run()
        model = self.model_child
        def late_collect(argv, environment):
            model(argv, environment)
            if "collect" in argv:
                self.clock.set_raw(controller.budget.fence("collect"))
        with patch.object(self, "model_child", side_effect=late_collect), self.assertRaises(C.ControllerError):
            controller.collect()
        self.assertFalse(any("uninstall" in row["argv"] for row in self.calls))
        self.assertFalse(controller.result()["profilePassed"])

    def test_full_raw_phase_receipt_close_overrun_cannot_become_complete(self):
        controller = self.full_controller()
        write = C.PrivateOwner.write
        def late_write(owner, directory, name, value, end):
            result = write(owner, directory, name, value, end)
            if owner is controller and directory.path == controller.commands.path / "product" and name == "result.json":
                self.clock.set_raw(controller.budget.fence("product-final"))
            return result
        with patch.object(C.PrivateOwner, "write", late_write), self.assertRaises(C.ControllerError):
            controller.product_run()
        self.assertNotIn("product", controller.phase_hashes)
        self.assertTrue((controller.path / "evidence/commands/product/result.json").is_file())
        self.assertFalse(controller.result()["profilePassed"])

    def test_full_actual_job_spent_3590_seconds_refuses_without_crypto_or_init(self):
        self.use_full()
        self.job_elapsed = 3590
        controller = self.assert_full_stopped_before_crypto()
        self.assertEqual(len(self.job_time_calls), 2)
        self.assertIsNone(controller.budget)
        self.assertTrue((controller.path / "evidence/job-time/jobs.json").is_file())

    def test_full_spent_finalization_reserve_refuses_without_renewing_job(self):
        self.use_full()
        self.job_elapsed = 2000
        controller = self.assert_full_stopped_before_crypto()
        self.assertTrue(controller.budget_exhausted)
        self.assertLess(controller.budget.fence("productive"), self.clock.raw())
        self.assertGreater(controller.budget.fence("controller-return"), self.clock.raw())

    def test_full_repeated_controller_reads_cannot_renew_absolute_return_fence(self):
        controller = self.full_controller()
        original = controller.budget.record
        self.clock.set_raw(controller.budget.fence("controller-return") - 2 * C.job_time.NS)
        first = controller.window("controller-return", 45)
        self.clock.now += 1
        self.assertEqual(controller.window("controller-return", 45), first)
        self.assertEqual(controller.budget.record, original)
        self.clock.now += 1
        with self.assertRaisesRegex(C.ControllerError, "FULL_JOB_STAGE_EXPIRED"):
            controller.window("controller-return", 45)

    def test_full_service_run_attempt_replay_refuses_before_crypto(self):
        self.use_full()
        modeled = self.model_job_time_response
        def replay(path, token, invocation):
            raw, error = modeled(path, token, invocation)
            if path.endswith("/jobs?per_page=100&page=1"):
                raw = JOB_MODELS.replace_body(raw, lambda row: row["jobs"][0].update(run_attempt=2))
            return raw, error
        with patch.object(C.job_time, "_request", side_effect=replay):
            controller = self.assert_full_stopped_before_crypto()
        self.assertIsNone(controller.budget)
        self.assertEqual(str(controller.original), "JOB_TIME_JOB_IDENTITY")

    def test_full_api_failure_preserves_original_and_never_calls_second_get(self):
        self.use_full()
        modeled = self.model_job_time_response
        def fail(path, token, invocation):
            raw, _ = modeled(path, token, invocation)
            value = C.job_time.parse(raw)
            value.update(complete=False, error="JOB_TIME_HTTP_FAILED")
            return C.job_time.encoded(value), C.job_time.BudgetError("JOB_TIME_HTTP_FAILED")
        with patch.object(C.job_time, "_request", side_effect=fail):
            controller = self.assert_full_stopped_before_crypto()
        self.assertEqual(len(self.job_time_calls), 1)
        original = C.parse((controller.path / "evidence/job-time/attempt.json").read_bytes())
        self.assertFalse(original["complete"])
        self.assertFalse((controller.path / "evidence/job-time/jobs.json").exists())
        returned = C.parse((controller.path / "runtime/job-time-result.json").read_bytes())
        self.assertFalse(returned["returned"])

    def test_full_original_job_time_child_return_mismatch_refuses_before_crypto(self):
        self.use_full()
        modeled = self.model_child
        def wrong_return(argv, environment):
            modeled(argv, environment)
            if "_job-time" in argv:
                path = C.session_path("full", "macos-arm64") / "runtime/job-time-result.json"
                returned = C.parse(path.read_bytes())
                returned["originalsSha256"]["jobs"] = "0" * 64
                self.save(path, returned)
        with patch.object(self, "model_child", side_effect=wrong_return):
            controller = self.assert_full_stopped_before_crypto()
        self.assertIsNone(controller.budget)
        self.assertEqual(str(controller.original), "JOB_TIME_ORIGINAL_RESPONSES_CHANGED")

    def test_full_raw_job_time_close_overrun_cannot_use_provisional_success(self):
        self.use_full()
        close = C.PrivateOwner.close
        def late(owner):
            close(owner)
            if type(owner) is C.PrivateOwner:
                self.clock.set_raw(self.clock.raw() + 46 * C.job_time.NS)
        with patch.object(C.PrivateOwner, "close", late):
            controller = self.assert_full_stopped_before_crypto()
        returned = C.parse((controller.path / "runtime/job-time-result.json").read_bytes())
        self.assertTrue(returned["returned"], "The original provisional receipt remains, not an invented failure")
        self.assertIsNone(controller.budget)
        self.assertTrue(self.job_time_child_errors)

    def test_full_token_is_acquisition_only_and_original_budget_inputs_are_frozen(self):
        session, result = self.execute_full()
        self.assertTrue(result["profilePassed"])
        acquisitions = [row for row in self.calls if "_job-time" in row["argv"]]
        self.assertEqual(len(acquisitions), 1)
        self.assertEqual(acquisitions[0]["environment"][C.job_time.TOKEN_ENV], JOB_MODELS.TOKEN)
        for row in self.calls:
            if "_job-time" not in row["argv"]:
                self.assertNotIn(C.job_time.TOKEN_ENV, row["environment"])
        self.assertNotIn(C.job_time.TOKEN_ENV, os.environ)
        frozen = session / "frozen-evidence"
        inventory = C.parse((frozen / "original-path-map.json").read_bytes())
        mapping = {row["original"]: row for row in inventory["files"]}
        originals = {"job-time/" + name + ".json": session / "evidence/job-time" / (name + ".json")
                     for name in ("attempt", "jobs", "budget")}
        originals["job-time/child-return.json"] = session / "runtime/job-time-result.json"
        originals.update({"commands/job-time/" + name + ".json": session / "evidence/commands/job-time" / (name + ".json")
                          for name in ("start", "result")})
        for name, path in originals.items():
            with self.subTest(original=name):
                self.assertIn(name, mapping)
                raw = (frozen / mapping[name]["member"]).read_bytes()
                self.assertEqual(raw, path.read_bytes())
                self.assertEqual((len(raw), C.digest(raw)), (mapping[name]["size"], mapping[name]["sha256"]))
                self.assertNotIn(JOB_MODELS.TOKEN.encode(), raw)

    def test_full_exact_cutoff_requests_once_and_late_zero_is_sealed_as_failed(self):
        self.use_full()
        modeled = self.model_child
        product_polls = []
        def poll():
            product_polls.append(self.clock.raw())
            if len(product_polls) == 1:
                self.clock.set_raw(self.owners[-1].budget.fence("productive"))
                return None
            return 0
        def child(argv, environment):
            modeled(argv, environment)
            self.poll_function = poll if "--cwd" in argv else None
        with patch.object(self, "model_child", side_effect=child), \
                patch.object(C.audit, "request_cancellation", side_effect=self.model_cancellation) as cancellation, \
                patch.object(C.shutil, "which", return_value=sys.executable):
            session, result = self.execute()
        cancellation.assert_called_once_with(session / "state", self.job, self.reserved)
        self.assertEqual(len(product_polls), 2)
        product = next(row for row in result["phases"] if row["phase"] == "product")
        self.assertEqual(product["exitCode"], 0, "Late product zero cannot erase the observed cutoff")
        self.assertTrue(result["jobBudget"]["exhausted"])
        self.assertFalse(result["profilePassed"])
        self.assertEqual(result["jobBudget"]["cooperativeCancellation"]["reason"], "job-budget")
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=false\n")
        rows = C.parse((session / "frozen-evidence/original-path-map.json").read_bytes())["files"]
        self.assertTrue(any(row["original"] == "job-time/product-cancellation.json" for row in rows))

    def test_full_signal_then_cutoff_never_duplicates_canonical_cancellation(self):
        self.use_full()
        modeled = self.model_child
        product_polls = []
        def poll():
            product_polls.append(self.clock.raw())
            controller = self.owners[-1]
            if len(product_polls) == 1:
                self.clock.set_raw(controller.budget.fence("productive") - C.job_time.NS)
                controller.cancelled.append(signal.SIGTERM)
                return None
            self.clock.set_raw(controller.budget.fence("productive"))
            return 0
        def child(argv, environment):
            modeled(argv, environment)
            self.poll_function = poll if "--cwd" in argv else None
        with patch.object(self, "model_child", side_effect=child), \
                patch.object(C.audit, "request_cancellation", side_effect=self.model_cancellation) as cancellation, \
                patch.object(C.shutil, "which", return_value=sys.executable):
            session, result = self.execute()
        cancellation.assert_called_once_with(session / "state", self.job, self.reserved)
        self.assertEqual(result["jobBudget"]["cooperativeCancellation"]["reason"], "signal")
        self.assertTrue(result["jobBudget"]["exhausted"])
        self.assertFalse(result["profilePassed"])
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=false\n")

    def test_full_cancellation_failure_retains_single_attempt_before_native_drain(self):
        controller = self.full_controller()
        self.events.clear()
        failure = OSError("synthetic request write failed")
        def poll():
            self.clock.set_raw(controller.budget.fence("productive"))
            return 0
        def fail_request(*args):
            self.events.append("cooperative-attempt")
            raise failure
        self.inject_product_poll(poll)
        with patch.object(C.audit, "request_cancellation", side_effect=fail_request) as cancellation, \
                self.assertRaises(OSError) as raised:
            controller.product_run()
        self.assertIs(raised.exception, failure)
        cancellation.assert_called_once_with(controller.state_path, self.job, self.reserved)
        self.assertLess(self.events.index("cooperative-attempt"), self.events.index("drain"))
        self.assertFalse(controller.budget_cancellation["requested"])
        self.assertIsNone(controller.budget_cancellation["requestSha256"])
        self.assertTrue(controller.budget_exhausted)
        self.assertFalse(controller.result()["profilePassed"])

    def exceptional_product_cutoff(self, boundary, *, secondary_request_failure=False):
        controller = self.full_controller()
        self.events.clear()
        failure = RuntimeError("synthetic original " + boundary + " monitor failure")
        secondary = OSError("synthetic cancellation write failure")
        reached = []
        def fail():
            reached.append(boundary)
            self.clock.set_raw(controller.budget.fence("productive"))
            raise failure
        def request(*args):
            if secondary_request_failure:
                self.events.append("cooperative-cancellation")
                raise secondary
            self.model_cancellation(*args)
        discover, verify = Scope.discover, C.query._PosixSink.verify
        def fail_discover(scope):
            discover(scope)
            return fail()
        def fail_verify(stream):
            if stream.path == controller.commands.path / "product/stdout.log" and "spawn" in self.events and not reached:
                return fail()
            return verify(stream)
        self.inject_product_poll(fail if boundary == "poll" else lambda: None)
        with ExitStack() as changes:
            if boundary == "discovery":
                changes.enter_context(patch.object(Scope, "discover", fail_discover))
            if boundary == "capture":
                changes.enter_context(patch.object(C.query._PosixSink, "verify", fail_verify))
            cancellation = changes.enter_context(patch.object(C.audit, "request_cancellation", side_effect=request))
            with self.assertRaises(RuntimeError) as raised:
                controller.product_run()
        self.assertIs(raised.exception, failure)
        self.assertIs(controller.original, failure)
        cancellation.assert_called_once_with(controller.state_path, self.job, self.reserved)
        self.assertEqual(reached, [boundary])
        self.assertLess(self.events.index("cooperative-cancellation"), self.events.index("drain"))
        self.assertTrue(controller.budget_exhausted)
        self.assertFalse(controller.result()["profilePassed"])
        self.assertEqual(controller.budget_cancellation["requested"], not secondary_request_failure)
        if secondary_request_failure:
            self.assertTrue(any(row["stage"] == "product-cutoff-finalizer" for row in controller.errors))
        # These are FAILED-monitor cleanup paths. Request-before-drain is not
        # evidence of a completed cooperative grace or canonical stop.

    def test_full_poll_exception_at_cutoff_preserves_original_and_requests_before_drain(self):
        self.exceptional_product_cutoff("poll")

    def test_full_discovery_exception_at_cutoff_preserves_original_and_requests_before_drain(self):
        self.exceptional_product_cutoff("discovery")

    def test_full_capture_exception_at_cutoff_preserves_original_and_requests_before_drain(self):
        self.exceptional_product_cutoff("capture")

    def test_full_exceptional_cutoff_keeps_original_when_exact_request_also_fails(self):
        self.exceptional_product_cutoff("poll", secondary_request_failure=True)

    def test_full_cutoff_during_init_prevents_all_later_productive_phases(self):
        self.use_full()
        # Reach the job cutoff within audit-init's unchanged 120+45s envelope,
        # not by leaping beyond an already-expired independent operation cap.
        # Preserve the same near-cutoff scenario after the NEW required 615s
        # simulator retirement reserve; this is not a relaxed timeout.
        self.job_elapsed = C.job_time.JOB_SECONDS - C.job_time.RESERVE_SECONDS - 66 - 119
        modeled = self.model_child
        def late_init(argv, environment):
            modeled(argv, environment)
            if "init" in argv:
                self.clock.set_raw(self.owners[-1].budget.fence("productive"))
        with patch.object(self, "model_child", side_effect=late_init), \
                patch.object(C.shutil, "which", return_value=sys.executable):
            _session, result = self.execute()
        self.assertTrue(result["jobBudget"]["exhausted"])
        self.assertEqual(result["jobBudget"]["cutoffObservation"]["phase"], "audit-init")
        self.assertFalse(any("prepare" in row["argv"] or "--cwd" in row["argv"] for row in self.calls))
        self.assertFalse(result["profilePassed"])
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=false\n")

    def test_full_raw_controller_close_expiry_refuses_provisional_green_result(self):
        self.use_full()
        controller_type = C.Controller
        close = C.PrivateOwner.close
        def late(owner):
            close(owner)
            if isinstance(owner, controller_type):
                self.clock.set_raw(owner.budget.fence("controller-return"))
        with patch.object(C.PrivateOwner, "close", late), patch.object(C.shutil, "which", return_value=sys.executable), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        session = C.session_path("full", "macos-arm64")
        result = C.parse((session / "controller-result.json").read_bytes())
        self.assertTrue(result["profilePassed"], "The retained provisional result is not the actual step outcome")
        self.assertEqual(self.clock.raw(), self.owners[-1].budget.fence("controller-return"))
        self.assertFalse((session / "post-return-validation").exists())

    def test_full_raw_crypto_close_expiry_blocks_init_and_keeps_parent_hold(self):
        self.use_full()
        close = C.PrivateOwner.close
        def late(owner):
            close(owner)
            if type(owner) is C.PrivateOwner and self.active_crypto_operation == "validate":
                self.clock.set_raw(self.owners[-1].budget.fence("productive"))
        with patch.object(C.PrivateOwner, "close", late), patch.object(C.shutil, "which", return_value=sys.executable), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        self.assertTrue(self.owners[-1].unknown)
        self.assertFalse(any("init" in row["argv"] or "--cwd" in row["argv"] for row in self.calls))
        self.assertTrue(self.crypto_child_errors)

    def test_full_raw_seal_close_expiry_emits_no_upload_authority(self):
        session, _result = self.execute_full()
        budget = C.job_time.Budget((session / "evidence/job-time/budget.json").read_bytes())
        close = C.PrivateOwner.close
        def late(owner):
            close(owner)
            self.clock.set_raw(budget.fence("seal"))
        with patch.object(C.PrivateOwner, "close", late), self.assertRaises(C.job_time.BudgetError):
            self.seal()
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")
        self.assertTrue((session / "post-return-validation/seal.json").is_file())

    def test_full_raw_seal_output_close_expiry_refuses_after_provisional_append(self):
        session, _result = self.execute_full()
        budget = C.job_time.Budget((session / "evidence/job-time/budget.json").read_bytes())
        target, clock = self.path / "public-step-output", self.clock
        original_open = Path.open
        class LateOutput:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self.stream
            def __exit__(self, *args):
                self.stream.close()
                clock.set_raw(budget.fence("seal"))
        def late(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            return LateOutput(stream) if path == target and args and args[0] == "a" else stream
        with patch.object(Path, "open", late), self.assertRaises(C.job_time.BudgetError):
            self.seal()
        self.assertEqual(target.read_text(), "artifacts_ready=true\nprofile_passed=true\n")

    def test_full_budget_originals_and_phase_substitutions_cannot_seal(self):
        session, _result = self.execute_full()
        changes = [("evidence/job-time/budget.json", lambda row: row["policy"].update(jobSeconds=3601)),
                   ("evidence/job-time/budget.json", lambda row: row["fencesRawNs"].update(productive=99999999999999)),
                   ("evidence/job-time/jobs.json", lambda row: row.update(invocation="f" * 32)),
                   ("evidence/job-time/child-return.json", lambda row: row.update(returned=False)),
                   ("runtime/job-time-result.json", lambda row: row.update(invocation="f" * 32)),
                   ("evidence/commands/job-time/start.json", lambda row: row.update(job="f" * 32)),
                   ("evidence/commands/job-time/result.json", lambda row: row.update(exitCode=True)),
                   ("run-context.json", lambda row: row.update(jobBudgetSha256="f" * 64))]
        for name, change in changes:
            path = session / name
            raw = path.read_bytes()
            value = C.parse(raw)
            change(value)
            try:
                self.save(path, value)
                with self.subTest(original=name), self.assertRaises((C.ControllerError, C.job_time.BudgetError)):
                    self.seal()
                self.assertFalse((session / "post-return-validation").exists())
            finally:
                self.save(path, raw)
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=true\n")

    def test_full_guard_before_and_after_share_exact_frozen_upload_cap(self):
        session, result = self.execute_full()
        self.seal()
        before_output = self.upload("before")
        before_raw = (session / "upload-before.json").read_bytes()
        before = C.parse(before_raw)
        self.assertEqual(before_output, "upload_ready=true\nupload_timeout_minutes=3\nupload_guard_sha256=" +
                         C.digest(before_raw) + "\n")
        self.assertEqual(before["jobBudgetSha256"], result["jobBudget"]["sha256"])
        self.assertEqual(before["endRawNs"] - before["beganRawNs"], 180 * C.job_time.NS)
        self.clock.set_raw(self.clock.raw() + C.job_time.NS)
        self.assertEqual(self.upload("after"), "upload_complete=true\n")
        after = C.parse((session / "upload-after.json").read_bytes())
        self.assertEqual(after["beforeSha256"], C.digest(before_raw))
        self.assertEqual(after["stepOutcome"], "success")
        self.assertLess(after["observedRawNs"], before["endRawNs"])

    def test_full_upload_expired_absolute_cap_cannot_be_renewed_by_after_guard(self):
        session, _result = self.execute_full()
        self.seal()
        self.upload("before")
        before = C.parse((session / "upload-before.json").read_bytes())
        self.clock.set_raw(before["endRawNs"])
        with self.assertRaisesRegex(C.ControllerError, "UPLOAD_ORIGINAL_FENCE_CHANGED_OR_EXPIRED"):
            self.upload("after")
        self.assertFalse((session / "upload-after.json").exists())

    def test_full_upload_tampered_cap_refuses_even_with_matching_new_hash(self):
        session, _result = self.execute_full()
        self.seal()
        self.upload("before")
        path = session / "upload-before.json"
        before = C.parse(path.read_bytes())
        before["maximumSeconds"] = 181
        raw = self.save(path, before)
        with self.assertRaisesRegex(C.ControllerError, "UPLOAD_ORIGINAL_FENCE_CHANGED_OR_EXPIRED"):
            self.upload("after", before_hash=C.digest(raw))
        self.assertFalse((session / "upload-after.json").exists())

    def test_full_upload_requires_both_real_preceding_step_outcomes(self):
        for phase, environment in (("before", {}), ("before", {"P2PKIT_HOSTED_TEST_RUN_OUTCOME": "success"}),
                ("before", {"P2PKIT_HOSTED_TEST_RUN_OUTCOME": "failure", "P2PKIT_HOSTED_TEST_SEAL_OUTCOME": "success"}),
                ("after", {"P2PKIT_HOSTED_TEST_RUN_OUTCOME": "success", "P2PKIT_HOSTED_TEST_SEAL_OUTCOME": "success"})):
            with self.subTest(phase=phase, environment=environment), patch.dict(os.environ, environment), \
                    self.assertRaises(C.ControllerError):
                C.upload_guard(phase)
        self.assertEqual(self.owners, [])

    def test_full_upload_rechecks_sealed_artifact_bytes_before_granting_upload(self):
        session, _result = self.execute_full()
        self.seal()
        path = session / "export" / C.posix.ARTIFACT
        original = path.read_bytes()
        self.save(path, b"X" + original[1:])
        with self.assertRaisesRegex(C.ControllerError, "UPLOAD_SEALED_MANIFEST_CHANGED"):
            self.upload("before")
        self.assertFalse((session / "upload-before.json").exists())

    def test_full_raw_upload_guard_close_expiry_cannot_grant_upload(self):
        session, _result = self.execute_full()
        self.seal()
        budget = C.job_time.Budget((session / "evidence/job-time/budget.json").read_bytes())
        close = C.PrivateOwner.close
        def late(owner):
            close(owner)
            self.clock.set_raw(budget.fence("upload-start"))
        with patch.object(C.PrivateOwner, "close", late), self.assertRaises(C.job_time.BudgetError):
            self.upload("before")
        self.assertEqual((self.path / "upload-before-output").read_bytes(), b"")
        self.assertTrue((session / "upload-before.json").is_file())

    def test_full_raw_upload_after_output_close_expiry_refuses_provisional_output(self):
        session, _result = self.execute_full()
        self.seal()
        self.upload("before")
        upload_end = C.parse((session / "upload-before.json").read_bytes())["endRawNs"]
        target, clock = self.path / "upload-after-output", self.clock
        original_open = Path.open
        class LateOutput:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self.stream
            def __exit__(self, *args):
                self.stream.close()
                clock.set_raw(upload_end)
        def late(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            return LateOutput(stream) if path == target and args and args[0] == "a" else stream
        with patch.object(Path, "open", late), self.assertRaisesRegex(C.ControllerError, "UPLOAD_GUARD_EXPIRED"):
            self.upload("after")
        self.assertEqual(target.read_text(), "upload_complete=true\n")

    def test_crypto_failure_blocks_expensive_init_and_keeps_unknown(self):
        with patch.object(C.posix, "validate_recipient", side_effect=ValueError("synthetic GPG failure")), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        self.assertFalse(any("init" in row["argv"] for row in self.calls))
        self.assertTrue(self.owners[-1].unknown)
        self.assertTrue(C.QUARANTINE)

    def test_crypto_rejects_an_internally_valid_but_wrong_outer_native_domain(self):
        model = self.model_child
        def wrong(argv, environment):
            if "_crypto" in argv:
                environment = C.processes.ownership_environment(environment, "e" * 32, "f" * 32,
                                           "/synthetic/wrong-owner", "/synthetic/wrong-home", allow_new_context=True)
            model(argv, environment)
        with patch.object(self, "model_child", side_effect=wrong), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        self.assertFalse(any("init" in row["argv"] for row in self.calls))
        self.assertTrue(self.owners[-1].unknown)

    def test_crypto_late_close_failure_is_not_upgraded_from_a_provisional_receipt(self):
        close = C.PrivateOwner.close
        def late(owner):
            close(owner)
            if type(owner) is C.PrivateOwner:
                raise OSError("model crypto close failure")
        with patch.object(C.PrivateOwner, "close", late), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        self.assertTrue(self.owners[-1].unknown)
        self.assertFalse(any("init" in row["argv"] for row in self.calls))

    def test_failed_product_is_encrypted_retained_and_sealed_as_failed_not_passed(self):
        self.product_code = 23
        _session, result = self.execute()
        self.assertFalse(result["profilePassed"])
        self.assertEqual(self.seal(), "artifacts_ready=true\nprofile_passed=false\n")

    def test_failed_profile_relabeling_is_rejected_by_original_records(self):
        self.product_code = 23
        session, result = self.execute()
        result["profilePassed"] = True
        self.save(session / "controller-result.json", result)
        with self.assertRaisesRegex(C.ControllerError, "FAILED_PROFILE_RELABELLED"):
            self.seal()

    def test_stale_source_export_result_is_rejected(self):
        session, result = self.execute()
        context_path = session / "run-context.json"
        context = C.parse(context_path.read_bytes())
        context["source"]["tree"] = "f" * 40
        self.save(context_path, context)
        with self.assertRaises(C.ControllerError):
            self.seal()

    def test_coordinated_public_tamper_does_not_invent_successful_original_export(self):
        session, result = self.execute()
        output = session / "export"
        forged = b"TAMPERED MODEL CIPHERTEXT"
        self.save(output / C.posix.ARTIFACT, forged)
        manifest = C.parse((output / C.posix.MANIFEST).read_bytes())
        manifest["artifact"].update(size=len(forged), sha256=C.digest(forged))
        self.save(output / C.posix.MANIFEST, manifest)
        with self.assertRaisesRegex(C.ControllerError, "EXPORTED_ARTIFACT_CHANGED"):
            self.seal()

    def test_exact_command_or_original_receipt_mutation_prevents_pass(self):
        session, result = self.execute()
        product = session / "evidence/commands/product/result.json"
        row = C.parse(product.read_bytes())
        row["argv"] = ["skip-tests"]
        self.save(product, row)
        with self.assertRaisesRegex(C.ControllerError, "ORIGINAL_PHASE_CHANGED"):
            self.seal()

    def test_same_run_attempt_post_return_seal_replay_is_rejected(self):
        self.execute()
        self.seal()
        with self.assertRaises(FileExistsError):
            self.seal()

    def crypto_interruption(self, operation, boundary, *, secondary_receipt=False):
        """Actual run/phase/finalization; only child/native/time answers modeled."""
        model = self.model_child
        label = "recipient-validation" if operation == "validate" else "export"
        original_poll = ValueError("synthetic original crypto poll")
        original_receipt = OSError("synthetic outer crypto receipt")
        controller_type = C.Controller
        write = C.PrivateOwner.write
        def fail_receipt(owner, directory, name, value, end):
            if isinstance(owner, controller_type) and directory.path == owner.commands.path / label and \
                    name == "result.json" and (boundary == "receipt" or secondary_receipt):
                raise original_receipt
            return write(owner, directory, name, value, end)
        def child(argv, environment):
            if "_crypto" in argv and argv[argv.index("_crypto") + 1] == operation:
                if boundary == "timeout":
                    self.poll_function = lambda: None
                    return  # Separate child has no terminal receipt at all.
                if boundary == "poll":
                    self.poll_error = original_poll
                    return
            model(argv, environment)
        def advance(value):
            self.clock.now += 60.
        with patch.object(self, "model_child", side_effect=child), \
                patch.object(C.PrivateOwner, "write", fail_receipt), \
                patch.object(C.time, "sleep", side_effect=advance), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        controller = self.owners[-1]
        result = C.parse((controller.path / "controller-result.json").read_bytes())
        row = next(row for row in result["phases"] if row["phase"] == label)
        self.assertTrue(row["launchAttempted"])
        self.assertIn("drain", self.events)
        self.assertTrue(controller.unknown)
        self.assertEqual(result["retirement"], "UNKNOWN")
        self.assertFalse(result["readyForPostReturnSeal"])
        self.assertIn(controller, C.QUARANTINE)
        roots = [row for row in controller.resources if row["label"] in ("private-directory", "private-child")]
        self.assertTrue(roots)
        self.assertTrue(all(not row["attempted"] and not row["closed"] for row in roots))
        self.assertTrue(any(row["stage"] == "crypto-" + operation + "-return" for row in controller.errors))
        terminal = controller.path / "runtime" / (operation + "-result.json")
        if boundary == "receipt":
            self.assertTrue(C.parse(terminal.read_bytes())["returned"])
            self.assertIs(controller.original, original_receipt)
            self.assertNotIn(label, controller.phase_hashes)
        else:
            self.assertFalse(terminal.exists())
        if boundary == "poll":
            self.assertIs(controller.original, original_poll)
        if secondary_receipt:
            self.assertTrue(any(row["stage"] == label + "-receipt" for row in controller.errors))
        self.assertEqual(C.query.QUARANTINE, [])
        self.assertEqual(C.windows._QUARANTINE, [])

    def test_validation_timeout_without_child_return_keeps_parent_pins_unknown(self):
        self.crypto_interruption("validate", "timeout")

    def test_export_timeout_without_child_return_keeps_parent_pins_unknown(self):
        self.crypto_interruption("export", "timeout")

    def test_validation_poll_failure_without_child_return_keeps_parent_pins_unknown(self):
        self.crypto_interruption("validate", "poll")

    def test_export_poll_failure_without_child_return_keeps_parent_pins_unknown(self):
        self.crypto_interruption("export", "poll")

    def test_validation_outer_receipt_failure_does_not_consume_provisional_child_return(self):
        self.crypto_interruption("validate", "receipt")

    def test_export_outer_receipt_failure_does_not_consume_provisional_child_return(self):
        self.crypto_interruption("export", "receipt")

    def test_validation_keeps_original_poll_error_and_secondary_receipt_failure(self):
        self.crypto_interruption("validate", "poll", secondary_receipt=True)

    def test_export_keeps_original_poll_error_and_secondary_receipt_failure(self):
        self.crypto_interruption("export", "poll", secondary_receipt=True)

    def test_child_quarantine_is_separate_and_nonzero_explicitly_holds_parent(self):
        marker = object()
        def fail(*args, **kwargs):
            C.windows._QUARANTINE.append(marker)
            raise ValueError("synthetic child-only UNKNOWN")
        with patch.object(C.posix, "validate_recipient", side_effect=fail), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        self.assertTrue(self.owners[-1].unknown)
        self.assertIn(self.owners[-1], C.QUARANTINE)
        self.assertEqual(C.windows._QUARANTINE, [])
        self.assertEqual(self.crypto_child_quarantines[0][1][2], [marker])

    def crypto_close_overrun(self, operation):
        original_close = C.PrivateOwner.close
        def slow_close(owner):
            original_close(owner)
            if type(owner) is C.PrivateOwner and self.active_crypto_operation == operation:
                self.clock.now += 211.
        with patch.object(C.PrivateOwner, "close", slow_close), redirect_stdout(io.StringIO()):
            self.assertEqual(self.call_run(), 125)
        controller = self.owners[-1]
        self.assertTrue(controller.unknown)
        self.assertEqual(self.crypto_child_errors[-1][0], operation)
        self.assertIsInstance(self.crypto_child_errors[-1][1], C.posix.EvidenceError)
        terminal = C.parse((controller.path / "runtime" / (operation + "-result.json")).read_bytes())
        self.assertTrue(terminal["returned"], "Provisional receipt cannot overrule the nonzero child return")
        self.assertTrue(any(row["stage"] == "crypto-final-deadline"
                            for owner in self.crypto_owners for row in owner.errors))
        self.assertFalse(any(row["attempted"] for row in controller.resources if row["label"] == "private-directory"))

    def test_private_validation_close_cannot_cross_original_absolute_deadline(self):
        self.crypto_close_overrun("validate")

    def test_private_export_close_cannot_cross_original_absolute_deadline(self):
        self.crypto_close_overrun("export")

    def test_public_seal_close_overrun_does_not_emit_success_outputs(self):
        session, _result = self.execute()
        began = self.clock.now
        original_close = C.PrivateOwner.close
        def slow_close(owner):
            original_close(owner)
            if type(owner) is C.PrivateOwner:
                self.clock.now += 121.
        with patch.object(C.PrivateOwner, "close", slow_close), self.assertRaises(C.posix.EvidenceError):
            self.seal()
        self.assertGreater(self.clock.now, began + 120.)
        self.assertEqual((self.path / "public-step-output").read_bytes(), b"")
        self.assertTrue((session / "post-return-validation/seal.json").is_file())

    def test_public_output_close_overrun_blocks_step_success_after_provisional_append(self):
        self.execute()
        target = self.path / "public-step-output"
        original_open = Path.open
        clock = self.clock
        class SlowOutput:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self.stream
            def __exit__(self, kind, value, trace):
                self.stream.close()
                clock.now += 121.
        def late(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            return SlowOutput(stream) if path == target and args and args[0] == "a" else stream
        with patch.object(Path, "open", late), self.assertRaises(C.posix.EvidenceError):
            self.seal()
        self.assertEqual(target.read_text(), "artifacts_ready=true\nprofile_passed=true\n")
        # Those provisional outputs are not authority: the seal step failed.

    def test_seal_rejects_canonical_supplier_hash_rebinding(self):
        session, _result = self.execute()
        path = self.root / "scripts" / "audit_processes.py"
        path.write_bytes(path.read_bytes() + b"\n# synthetic changed source\n")
        with self.assertRaisesRegex(C.ControllerError, "SEALED_CONTEXT_CHANGED"):
            self.seal()
        self.assertFalse((session / "post-return-validation").exists())


FRESH_CANONICAL_PROBE = '''import ctypes, hashlib, json, os, runpy, subprocess, sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
assert sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode
actual, expected = json.loads(sys.argv[1]), json.loads(sys.argv[2])
source = Path(expected[0])
assert str(source.parent) not in sys.path and "audit_processes" not in sys.modules
original_path = list(sys.path)
observed = {}
class MainReachedWithoutExecution(BaseException):
    pass
def trace(frame, event, value):
    if event == "call" and frame.f_code.co_filename == str(source):
        if frame.f_code.co_name in ("initialize", "execute"):
            raise AssertionError("CANONICAL_PRODUCT_FORBIDDEN")
        if frame.f_code.co_name == "main":
            assert sys.argv == expected and sys.path == original_path
            module = sys.modules["audit_processes"]
            assert module.__file__ == str(source.with_name("audit_processes.py"))
            observed.update(main="REACHED_NOT_EXECUTED", argv=list(sys.argv),
                            isolated=sys.flags.isolated, no_site=sys.flags.no_site,
                            no_bytecode=sys.dont_write_bytecode, unchanged_sys_path=True)
            raise MainReachedWithoutExecution()
    return trace
with ExitStack() as guards:
    for module, name in ((subprocess, "Popen"), (ctypes, "CDLL"), (os, "system")):
        guards.enter_context(patch.object(module, name, side_effect=AssertionError("NATIVE_OR_PRODUCT_FORBIDDEN")))
    if hasattr(ctypes, "WinDLL"):
        guards.enter_context(patch.object(ctypes, "WinDLL", side_effect=AssertionError("NATIVE_API_FORBIDDEN")))
    sys.settrace(trace)
    try:
        if actual[0] == "-c":
            sys.argv = ["-c", *actual[2:]]
            exec(compile(actual[1], "<closed-canonical-bootstrap>", "exec"), {"__name__": "__main__"})
        else:
            sys.argv = list(actual)
            runpy.run_path(actual[0], run_name="__main__")
    except MainReachedWithoutExecution:
        pass
    finally:
        sys.settrace(None)
assert observed.get("main") == "REACHED_NOT_EXECUTED"
print(json.dumps(observed, sort_keys=True))
'''


class FreshCanonicalImportModels(unittest.TestCase):
    """Fresh installed Python only; actual canonical/native/product mains blocked."""
    def invocation(self, args):
        controller = object.__new__(C.Controller)  # No host/native constructor.
        controller.canonical_sources = {name: C.digest((ROOT / "scripts" / name).read_bytes())
                                        for name in ("audit_processes.py", "run-audit-command.py")}
        return controller.python(ROOT / "scripts/run-audit-command.py", *args)

    def probe(self, argv, args):
        expected = [str(ROOT / "scripts/run-audit-command.py"), *args]
        command = [str(Path(sys.executable).resolve(strict=True)), "-I", "-B", "-S", "-c", FRESH_CANONICAL_PROBE,
                   json.dumps(argv[4:]), json.dumps(expected)]
        return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)

    def test_fresh_isolated_canonical_init_imports_exact_sibling_without_executing_main(self):
        args = ["init", "--root", str(ROOT), "--state", "/synthetic/never-created-state",
                "--expected-commit", "a" * 40, "--host", "macos-arm64"]
        result = self.probe(self.invocation(args), args)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        value = json.loads(result.stdout)
        self.assertEqual(value["main"], "REACHED_NOT_EXECUTED")
        self.assertTrue(value["unchanged_sys_path"])

    def test_fresh_isolated_canonical_product_preserves_exact_argv_without_executing_main(self):
        args = ["--cwd", str(ROOT), "--wrapper", str(ROOT / "gradlew"), "--kind", "command", "--purpose",
                "ordinary-full", "--id", "d" * 32, "--timeout", "7200", "--stop-timeout", "120", "--",
                "python3", "scripts/run-platform-tests.py", "full"]
        result = self.probe(self.invocation(args), args)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        self.assertEqual(json.loads(result.stdout)["argv"], [str(ROOT / "scripts/run-audit-command.py"), *args])

    def test_canonical_or_sibling_hash_mismatch_refuses_before_main(self):
        args = ["init"]
        for name in ("run-audit-command.py", "audit_processes.py"):
            with self.subTest(supplier=name):
                argv = self.invocation(args)
                bindings = json.loads(argv[7])
                bindings[name] = "0" * 64
                argv[7] = json.dumps(bindings)
                result = self.probe(argv, args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"CANONICAL_BOOTSTRAP_REFUSED", result.stderr)
                self.assertNotIn(b"REACHED_NOT_EXECUTED", result.stdout)

    def test_canonical_bootstrap_rejects_extra_supplier_binding(self):
        args = ["init"]
        argv = self.invocation(args)
        bindings = json.loads(argv[7])
        bindings["untrusted.py"] = "a" * 64
        argv[7] = json.dumps(bindings)
        result = self.probe(argv, args)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"CANONICAL_BOOTSTRAP_REFUSED", result.stderr)


class WindowsFileModels(Base):
    """ACTUAL NativeFile/PrivateDirectory objects over an IN-MEMORY WinAPI model."""
    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location("ordinary_controller_win_file_model",
                    ROOT / "scripts/tests/hosted-windows-files-test.py")
        self.model = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.model
        spec.loader.exec_module(self.model)
        self.api = self.model.ModelApi()
        self.native_roots = []
        self.stack.enter_context(patch.object(C, "os", SimpleNamespace(name="nt", environ=os.environ,
                                                                     getpid=os.getpid, path=os.path)))
        self.stack.enter_context(patch.object(C.query, "_new_private_directory", side_effect=self.new_root))
        self.stack.enter_context(patch.object(C.processes, "host_role", return_value="windows-x64"))
        self.stack.enter_context(patch.object(C.processes, "make_scope", side_effect=self.native_scope))
        self.stack.enter_context(patch.object(C.files.NativeFile, "fileno", side_effect=AssertionError("NO_CRT_CONVERSION")))

    def new_root(self, path):
        root = C.files._root("C:\\work\\" + Path(path).name, self.api, create=True)
        self.native_roots.append(root)
        return root

    def native_scope(self, job, invocation, state, home):
        case = self
        class WindowsScopeModel(Scope):
            def spawn(self, argv, cwd, environment, *, stdout, stderr):
                case.assertIsInstance(stdout, C.files.NativeFile)
                case.assertIsInstance(stderr, C.files.NativeFile)
                case.events.append("spawn")
                case.calls.append({"argv": argv, "environment": environment, "stdout": stdout, "stderr": stderr})
                case.api.write(stdout.native_handle, case.stdout)
                case.api.write(stderr.native_handle, case.stderr)
                self.launches.append({"argv": argv, "cwd": cwd, "created": True})
                return SimpleNamespace(stdout=None, stderr=None, poll=lambda: case.exit_code)
            def description(self):
                # This existing in-memory Windows handle model is not the new
                # Darwin simulator model and must not invent Darwin birth IDs.
                return {"backend": "windows-job-list-suspended", "scope": "kernel-job-no-breakaway-kill-on-close",
                        "job": self.job, "invocation": self.invocation, "launches": self.launches,
                        "discoveryErrors": case.discovery_errors}
        return WindowsScopeModel(case, job, invocation, state, home)

    def tearDown(self):
        for owner in self.owners:
            for row in reversed(owner.resources):
                obj = row["owner"]
                if isinstance(obj, (C.files.PrivateDirectory, C.files.NativeFile)):
                    try:
                        obj.close()
                    except BaseException:
                        pass
        for root in reversed(self.native_roots):
            root.close()
        self.assertEqual(self.api.handles, {}, "Unaccounted in-memory model handles")
        super().tearDown()


    def actual_stream_query_phase(self, *, post_drain_growth=False):
        queries = self.model.StreamQueryModel(self.api)
        original_factory = self.native_scope
        def factory(*args):
            scope = original_factory(*args)
            original_spawn, original_close = scope.spawn, scope.close
            def spawn(argv, cwd, env, *, stdout, stderr):
                child = original_spawn(argv, cwd, env, stdout=stdout, stderr=stderr)
                queries.append_after_standard(stdout.native_handle, b"+stdout")
                queries.append_after_standard(stderr.native_handle, b"+stderr")
                return child
            def close():
                original_close()
                if post_drain_growth:
                    queries.append_after_standard(self.calls[0]["stdout"].native_handle, b"late")
            scope.spawn, scope.close = spawn, close
            return scope
        self.stack.enter_context(patch.object(C.processes, "make_scope", side_effect=factory))
        return self.controller(), queries

    def test_real_inspector_live_growth_is_captured_by_actual_controller_phase(self):
        controller, queries = self.actual_stream_query_phase()
        row = controller.phase("product", ["synthetic-model"], 825)
        self.assertEqual(row["exitCode"], 0)
        self.assertEqual(row["retirement"], "KNOWN")
        self.assertEqual(row["errors"], [])
        self.assertEqual(sum(maximum is not None for _, maximum in queries.observations), 2)
        for name in ("stdout", "stderr"):
            stream = self.calls[0][name]
            node = self.api.nodes[str(stream.path)]
            self.assertEqual(node.content, getattr(self, name) + (b"+stdout" if name == "stdout" else b"+stderr"))
            self.assertTrue(stream.closed)
            self.assertEqual(stream._deadline, 970.)
        controller.close()

    def test_actual_controller_post_drain_verification_does_not_allow_live_growth(self):
        controller, queries = self.actual_stream_query_phase(post_drain_growth=True)
        with self.assertRaises(C.ControllerError):
            controller.phase("product", ["synthetic-model"], 825)
        row = controller.records[0]
        self.assertEqual(row["exitCode"], 0)
        self.assertIn("Alternate data streams are not admitted", json.dumps(row["errors"]))
        self.assertEqual(sum(maximum is not None for _, maximum in queries.observations), 2)
        self.assertTrue(all(self.calls[0][name].closed for name in ("stdout", "stderr")))
        controller.close()  # Known native retirement may close resources; the failed phase stays failed.
        self.assertTrue(row["errors"])

    def test_native_sinks_are_borrowed_without_fileno_and_original_deadlines_stay_fixed(self):
        controller = self.controller()
        row = controller.phase("product", ["synthetic-model"], 825)
        self.assertEqual(row["exitCode"], 0)
        self.assertEqual(row["retirement"], "KNOWN")
        self.assertEqual(self.calls[0]["stdout"]._deadline, 970.)
        self.assertEqual(self.calls[0]["stderr"]._deadline, 970.)
        self.assertTrue(self.calls[0]["stdout"].closed)
        controller.close()

    def test_actual_nativefile_bounded_readback_and_flat_copy_admit_uppercase_xml(self):
        owner = self.owner()
        source = self.private(owner, "original")
        stream = owner.acquire("input", lambda: source.create_file("TEST-Upper.XML", max_bytes=4, deadline=200.))
        stream.write(b"test")
        owner.close_one(stream)
        copied = C.copy_tree(owner, source, self.path / "copy", 200.)
        raw = copied.read_bytes("original-path-map.json", max_bytes=C.RECORD_LIMIT, deadline=200.)
        mapping = C.parse(raw)
        self.assertEqual(mapping["files"][0]["original"], "TEST-Upper.XML")
        self.assertEqual(copied.read_bytes(mapping["files"][0]["member"], max_bytes=4, deadline=200.), b"test")
        owner.close()

    def test_seal_inventory_uses_supported_aggregate_native_bound(self):
        owner = self.owner()
        output = self.private(owner, "export")
        owner.write(output, C.posix.ARTIFACT, b"synthetic-not-crypto", 200.)
        owner.write(output, C.posix.MANIFEST, {"model": True}, 200.)
        result = C.artifact_metadata(owner, output, 200.)
        self.assertEqual(result["sha256"], C.digest(b"synthetic-not-crypto"))
        owner.close()


def passing_result():
    phases = []
    for index, label in enumerate(("recipient-validation", "audit-init", "custody-prepare", "product",
                                   "custody-collect", "custody-uninstall", "export")):
        phases.append({"phase": label, "exitCode": 0, "launchAttempted": True, "scopeAttempted": True,
                       "retirement": "KNOWN", "errors": [], "survivors": [], "ownership": {"discoveryErrors": []}})
    return {"phases": phases, "productAttempted": True, "cancelled": False, "retirement": "KNOWN", "errors": [],
            "encrypted": True, "custody": {"result": "RETAINED", "retirement": "KNOWN", "errors": [],
                        "productExitCode": 0, "stopExitCode": 0, "ownerFinalExitCode": 0}}


class PassModels(unittest.TestCase):
    def test_pass_requires_original_complete_outcomes_not_boolean_label(self):
        value = passing_result()
        self.assertTrue(C.profile_passed(value))
        for kind in ("exit", "missing", "order", "cancel", "error", "survivor", "custody-error", "stop", "bool-exit"):
            value = passing_result()
            if kind == "exit": value["phases"][3]["exitCode"] = 1
            elif kind == "missing": value["phases"].pop(3)
            elif kind == "order": value["phases"].reverse()
            elif kind == "cancel": value["cancelled"] = True
            elif kind == "error": value["errors"].append("fail")
            elif kind == "survivor": value["phases"][3]["survivors"] = [1]
            elif kind == "custody-error": value["custody"]["errors"].append("fail")
            elif kind == "stop": value["custody"]["stopExitCode"] = 125
            elif kind == "bool-exit": value["phases"][3]["exitCode"] = False
            value["profilePassed"] = True
            with self.subTest(kind=kind):
                self.assertFalse(C.profile_passed(value))


if __name__ == "__main__":
    unittest.main(verbosity=2)
