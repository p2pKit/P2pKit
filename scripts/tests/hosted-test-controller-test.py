#!/usr/bin/env python3
"""Offline composition models. NO real Git/native owner/GPG/Gradle/CI execution.

Only synthetic private POSIX fixture files are created. Orchestration children
and native methods are modeled. Fresh isolated Python import probes block the
canonical main, all native APIs and further process execution; those small child
interpreters do not execute products or claim genuine host/crypto proof.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
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
        case.events.append("scope")
        if case.constructor_error:
            raise case.constructor_error

    def spawn(self, argv, cwd, environment, *, stdout, stderr):
        self.case.events.append("spawn")
        self.case.calls.append({"argv": argv, "cwd": cwd, "environment": dict(environment),
                                "stdout": stdout, "stderr": stderr})
        if self.case.spawn_error:
            raise self.case.spawn_error
        os.write(stdout.fileno(), self.case.stdout)
        os.write(stderr.fileno(), self.case.stderr)
        self.launches.append({"argv": argv, "cwd": cwd, "created": True, "outputMode": "OFFLINE_SUPPLIED_FILES"})
        if self.case.after_launch:
            self.case.after_launch()
        if getattr(self.case, "model_child", None):
            self.case.model_child(argv, environment)
        return SimpleNamespace(stdout=None, stderr=None, poll=self.poll)

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
                "startedIdentities": [{"pid": 1}], "discoveryErrors": self.case.discovery_errors}

    def close(self):
        self.case.events.append("scope-close")
        if self.case.close_error:
            raise self.case.close_error


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
        self.public_key = b"SYNTHETIC PUBLIC KEY; NOT CRYPTOGRAPHIC MATERIAL"
        event, policy = C.encoded({"model": "event"}), C.encoded({"model": "policy"})
        record = {"source": self.source, "profile": self.profile, "suites": ["cli"],
                  "github": {"eventSha256": C.digest(event), "runId": "123", "runAttempt": "1"},
                  "policy": {"sha256": C.digest(policy), "keySha256": C.digest(self.public_key),
                             "fingerprint": "A" * 40, "expiresAt": 2000000000}}
        self.admitted = C.identity.Admission(C.encoded(record), event, policy, self.public_key,
                                            "A" * 40, C.digest(self.public_key), 2000000000)
        self.stack.enter_context(patch.object(C, "admission", side_effect=self.model_admission))
        self.stack.enter_context(patch.object(C.query, "NativeGitQueries", side_effect=lambda *a, **k:
             SimpleNamespace(unknown=False, native_host_matches_actions=lambda: None, _finalize=lambda error: None)))
        self.stack.enter_context(patch.object(C.posix, "validate_recipient", side_effect=self.model_recipient))
        self.stack.enter_context(patch.object(C.ordinary, "export_encrypted", side_effect=self.model_export))
        self.stack.enter_context(patch.object(C.audit, "output_roots", return_value=[self.root / "build"]))
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

    def model_child(self, argv, environment):
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
        def slow_scope(*args):
            scope = Scope(self, *args)
            self.clock.set_raw(controller.budget.fence("productive"))
            return scope
        with patch.object(C.processes, "make_scope", side_effect=slow_scope), \
                patch.object(C.audit, "request_cancellation", side_effect=self.model_cancellation), \
                self.assertRaises(C.ControllerError):
            controller.product_run()
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
        self.poll_function = delayed_poll
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
        self.poll_function = poll
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
        self.poll_function = fail if boundary == "poll" else lambda: None
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
        self.job_elapsed = 1600
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
                result = super().description()
                result.update(backend="windows-job-list-suspended", scope="kernel-job-no-breakaway-kill-on-close")
                return result
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
