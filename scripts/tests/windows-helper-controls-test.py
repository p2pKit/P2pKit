#!/usr/bin/env python3
"""Pure/offline Windows helper control models, never native or GPG acceptance.

No child, network, crypto, Gradle, SDK or native API is executed. Production
custody state machines use in-memory owners; native fixture bodies are not run.
The maintained Windows controller test entry loads these methods exactly once.
"""
from __future__ import annotations

import ast
import base64
from contextlib import ExitStack
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


H = module("windows_helper_model_subject", "run-hosted-windows-helper-controls.py")
T = module("windows_file_retention_model_subject", "tests/hosted-windows-files-test.py")
N = module("windows_native_definitions_only", "tests/windows-helper-native-test.py")


def public_armor():
    # Deliberately tiny syntactic public packet, not a working crypto recipient.
    packet = bytes([0xC6, 1, 4])
    return b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n" + base64.b64encode(packet) + b"\n-----END PGP PUBLIC KEY BLOCK-----\n"


def dispatch():
    sha, tree, ref = "a" * 40, "b" * 40, "refs/heads/work/helper-model"
    env = {"P2PKIT_EXPECTED_SHA": sha, "P2PKIT_EXPECTED_TREE": tree, "P2PKIT_OPERATION": H.OPERATION,
           "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": H.REPOSITORY, "GITHUB_EVENT_NAME": "workflow_dispatch",
           "GITHUB_JOB": H.OPERATION, "GITHUB_WORKFLOW": "Desktop cross-host", "GITHUB_SHA": sha,
           "GITHUB_WORKFLOW_SHA": sha, "GITHUB_REF": ref, "GITHUB_REF_TYPE": "branch",
           "GITHUB_WORKFLOW_REF": H.REPOSITORY + "/" + H.WORKFLOW + "@" + ref,
           "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_WORKSPACE": str(H.ROOT),
           "RUNNER_OS": "Windows", "RUNNER_ARCH": "X64", "RUNNER_ENVIRONMENT": "github-hosted",
           "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
           "P2PKIT_REVIEWED_BASE": "", "P2PKIT_EVIDENCE_PUBLIC_KEY": public_armor().decode(),
           "P2PKIT_EVIDENCE_FINGERPRINT": "C" * 40}
    event = {"repository": {"full_name": H.REPOSITORY}, "ref": ref, "inputs": {
        "operation": H.OPERATION, "expected_sha": sha, "expected_tree": tree, "reviewed_base": "",
        "evidence_public_key": env["P2PKIT_EVIDENCE_PUBLIC_KEY"], "evidence_fingerprint": "C" * 40}}
    return env, event


def admitted():
    return H.identity(*dispatch(), H.ROOT)


class Models(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        # These are model-local globals, never a reset of a native held domain.
        self.stack.enter_context(patch.object(H.encrypted, "_QUARANTINE", []))
        self.stack.enter_context(patch.object(H, "_HELD", []))
        self.stack.enter_context(patch.object(H.processes, "make_scope", side_effect=AssertionError("MODEL cannot launch")))
        self.stack.enter_context(patch.object(H.encrypted, "validate_recipient", side_effect=AssertionError("MODEL cannot use GPG")))
        self.stack.enter_context(patch.object(H.encrypted, "export_encrypted", side_effect=AssertionError("MODEL cannot encrypt")))

    def set(self, target, name, **kwargs):
        return self.stack.enter_context(patch.object(target, name, **kwargs))


class IdentityModels(Models):
    def test_actual_identity_dictionary_and_short_event_ref_match(self):
        env, event = dispatch()
        value = H.identity(env, event, H.ROOT)
        self.assertEqual(value["recipientSha256"], H.digest(public_armor()))
        event["ref"] = env["GITHUB_REF"][len("refs/heads/"):]
        self.assertEqual(H.identity(env, event, H.ROOT), value)

    def test_all_fixed_host_workflow_and_source_fields_are_required(self):
        original, event = dispatch()
        for field in original:
            if field.startswith("GITHUB_") or field.startswith("RUNNER_") or field in ("P2PKIT_OPERATION", "P2PKIT_EXPECTED_SHA", "P2PKIT_EXPECTED_TREE"):
                with self.subTest(field=field):
                    env = dict(original); env[field] = "wrong"
                    with self.assertRaises((H.HelperError, H.encrypted.portable.EvidenceError)):
                        H.identity(env, event, H.ROOT)

    def test_event_ref_repository_extra_and_changed_inputs_refuse(self):
        env, event = dispatch()
        mutations = [lambda e: e.update(ref="main"), lambda e: e["repository"].update(full_name="other/repo"),
                     lambda e: e["inputs"].update(command="echo"), lambda e: e["inputs"].update(expected_tree="d" * 40)]
        for mutation in mutations:
            altered = copy.deepcopy(event); mutation(altered)
            with self.assertRaises(H.HelperError):
                H.identity(env, altered, H.ROOT)

    def test_optional_empty_writer_input_may_be_omitted_without_changing_identity(self):
        env, event = dispatch()
        expected = H.identity(env, event, H.ROOT)
        event["inputs"].pop("reviewed_base")
        original = copy.deepcopy(event)
        self.assertEqual(H.identity(env, event, H.ROOT), expected)
        self.assertEqual(event, original)  # Original event representation is not rewritten.

    def test_optional_writer_input_rejects_null_nonstring_nonempty_and_whitespace(self):
        env, event = dispatch()
        for value in (None, False, 0, [], {}, " ", "\n", "a" * 40):
            with self.subTest(value=value):
                altered = copy.deepcopy(event); altered["inputs"]["reviewed_base"] = value
                with self.assertRaises(H.HelperError) as caught:
                    H.identity(env, altered, H.ROOT)
                self.assertEqual(caught.exception.code, "EVENT_WRITER_BASE_NOT_EMPTY")

    def test_every_authority_input_remains_required_exact_and_string_typed(self):
        env, event = dispatch()
        for key in set(event["inputs"]) - {"reviewed_base"}:
            with self.subTest(key=key, mode="absent"):
                altered = copy.deepcopy(event); altered["inputs"].pop(key)
                with self.assertRaises(H.HelperError) as caught:
                    H.identity(env, altered, H.ROOT)
                self.assertEqual(caught.exception.code, "EVENT_INPUT_KEYS_DIFFER")
            for value in (None, False, 0, [], {}, "", event["inputs"][key] + " "):
                with self.subTest(key=key, value=value):
                    altered = copy.deepcopy(event); altered["inputs"][key] = value
                    with self.assertRaises(H.HelperError) as caught:
                        H.identity(env, altered, H.ROOT)
                    self.assertEqual(caught.exception.code, "EVENT_REQUIRED_INPUT_VALUES_DIFFER")

    def test_event_rejections_report_fixed_boundary_codes_without_input_values(self):
        env, event = dispatch()
        cases = [(None, "EVENT_REPOSITORY_DIFFERS"),
                 ({**event, "repository": {}}, "EVENT_REPOSITORY_DIFFERS"),
                 ({**event, "ref": "different-ref"}, "EVENT_REF_DIFFERS"),
                 ({**event, "inputs": None}, "EVENT_INPUT_KEYS_DIFFER"),
                 ({**event, "inputs": {**event["inputs"], "extra": "not-to-print"}}, "EVENT_INPUT_KEYS_DIFFER")]
        for altered, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(H.HelperError) as caught:
                    H.identity(env, altered, H.ROOT)
                self.assertEqual(str(caught.exception), code)

    def test_ordinary_events_and_retired_audit_ref_never_bootstrap_helper(self):
        env, event = dispatch()
        for name in ("push", "pull_request", "schedule", "workflow_run"):
            changed = dict(env, GITHUB_EVENT_NAME=name)
            with self.assertRaises(H.HelperError):
                H.identity(changed, event, H.ROOT)
        env["GITHUB_REF"] = event["ref"] = "refs/heads/audit/complete-2026-09-04"
        env["GITHUB_WORKFLOW_REF"] = H.REPOSITORY + "/" + H.WORKFLOW + "@" + env["GITHUB_REF"]
        with self.assertRaises(H.HelperError):
            H.identity(env, event, H.ROOT)

    def test_public_recipient_and_empty_writer_base_are_mandatory(self):
        original, event = dispatch()
        for field, value in (("P2PKIT_REVIEWED_BASE", "a" * 40), ("P2PKIT_EVIDENCE_FINGERPRINT", ""),
                             ("P2PKIT_EVIDENCE_PUBLIC_KEY", ""), ("P2PKIT_EVIDENCE_PUBLIC_KEY", "secret")):
            with self.subTest(field=field):
                env = dict(original); env[field] = value
                with self.assertRaises((H.HelperError, H.encrypted.portable.EvidenceError)):
                    H.identity(env, event, H.ROOT)

    def test_secret_packet_under_public_armor_refuses(self):
        env, event = dispatch()
        key = public_armor().replace(base64.b64encode(bytes([0xC6, 1, 4])), base64.b64encode(bytes([0xC5, 1, 4])))
        env["P2PKIT_EVIDENCE_PUBLIC_KEY"] = event["inputs"]["evidence_public_key"] = key.decode()
        with self.assertRaises(H.encrypted.portable.EvidenceError):
            H.identity(env, event, H.ROOT)

    def test_ambient_credentials_hooks_options_are_dropped_without_temp_replacement(self):
        e = {"PATH": "native-path", "TEMP": "original-temp", "RUNNER_TEMP": "original-runner-temp",
             "GITHUB_TOKEN": "NOT_A_CREDENTIAL_MODEL", "JAVA_TOOL_OPTIONS": "not-admitted", "GIT_CONFIG_COUNT": "9"}
        domain = H.processes.ownership_environment(e, "1" * 32, "2" * 32, "state", "home", allow_new_context=True)
        value = H.command_environment(domain)
        self.assertEqual(value["TEMP"], "original-temp")
        self.assertEqual(value["RUNNER_TEMP"], "original-runner-temp")
        for key in (H.processes.JOB_ENV, H.processes.CHAIN_ENV, H.processes.DOMAINS_ENV, H.processes.STATE_ENV, "GRADLE_USER_HOME"):
            self.assertEqual(value[key], domain[key])
        self.assertFalse({"GITHUB_TOKEN", "JAVA_TOOL_OPTIONS", "GIT_CONFIG_COUNT"} & value.keys())

    def test_missing_gpg_is_a_precise_blocker_without_installer_fallback(self):
        self.set(H.sys, "executable", new="C:\\native\\python.exe")
        self.set(H.encrypted, "_executable", return_value="d" * 64)
        self.set(H.shutil, "which", side_effect=["C:\\git\\git.exe", None])
        with self.assertRaisesRegex(H.HelperError, "GPG_NOT_INSTALLED_ON_PATH"):
            H.admitted_tools()

    def test_unsafe_or_wrong_architecture_gpg_refuses(self):
        self.set(H.sys, "executable", new="C:\\native\\python.exe")
        self.set(H.encrypted, "_executable", side_effect=["p", "g", ValueError("MODEL PE rejected")])
        self.set(H.shutil, "which", side_effect=["C:\\git.exe", "C:\\gpg.exe"])
        with self.assertRaisesRegex(H.HelperError, "GPG_NOT_NATIVE_AMD64_OR_SAFE_FILE"):
            H.admitted_tools()

    def test_tool_observations_distinguish_each_actual_admission_without_extra_calls(self):
        self.set(H.sys, "executable", new="C:\\native\\python.exe")
        for index, expected in enumerate((H.Stage.PYTHON_TOOL, H.Stage.GIT_TOOL, H.Stage.GPG_TOOL)):
            with self.subTest(tool=expected), ExitStack() as local:
                local.enter_context(patch.object(H.shutil, "which", side_effect=["C:\\git.exe", "C:\\gpg.exe"]))
                checked = local.enter_context(patch.object(H.encrypted, "_executable",
                    side_effect=[*("hash" for _ in range(index)), OSError("MODEL private executable path")]))
                progress = H.Progress()
                with self.assertRaises((OSError, H.HelperError)):
                    H.admitted_tools(observe=progress.mark)
                self.assertEqual(progress.stage, expected)
                self.assertEqual(checked.call_count, index + 1)

    def test_duplicate_nonfinite_and_oversized_private_records_refuse(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[]', b'x' * (H.MAX_RECORD + 1)):
            with self.assertRaises((H.HelperError, ValueError)):
                H.decode(raw)

    def test_exception_attachments_and_original_cancellation_are_retained(self):
        error = KeyboardInterrupt("MODEL cancellation")
        error._p2pkit_windows_evidence = b'{"retirement":"UNKNOWN","commands":[{"original":true}]}'
        detail = H.error_detail(error)
        self.assertTrue(detail["retirementUnknown"])
        self.assertTrue(detail["windowsEvidence"][0]["commands"][0]["original"])

    def test_raising_oversized_and_nonboolean_attachment_accessors_fail_closed(self):
        class Hostile(Exception):
            @property
            def private_record(self):
                raise KeyboardInterrupt("MODEL accessor")
        errors = [Hostile("MODEL"), ValueError("MODEL large"), ValueError("MODEL flag")]
        errors[1].private_record = b"x" * (H.encrypted.MAX_RECORD_BYTES + 1)
        errors[2].retirement_unknown = "False"
        for error in errors:
            detail = H.error_detail(error)
            self.assertTrue(detail["retirementUnknown"])
            self.assertTrue(detail["incomplete"])

    def test_nested_exporter_attachment_is_not_lost_behind_a_late_close_failure(self):
        nested = H.encrypted.WindowsEvidenceError(OSError("MODEL first"), b'{"retirement":"UNKNOWN","commands":[{"raw":"ORIGINAL"}]}', True)
        primary = OSError("MODEL late close"); primary.__context__ = nested
        detail = H.error_detail(primary)
        self.assertTrue(detail["retirementUnknown"])
        self.assertEqual(detail["windowsEvidence"][0]["commands"][0]["raw"], "ORIGINAL")

    def test_attached_graph_cycle_and_overflow_are_bounded(self):
        value = OSError("MODEL cycle"); value.__context__ = value
        value.private_record = b'{"retirement":"KNOWN"}'
        detail = H.error_detail(value)
        self.assertEqual(len(detail["windowsEvidence"]), 1)
        previous = value
        for index in range(10):
            child = OSError("MODEL " + str(index)); previous.__cause__ = child; previous = child
            child.private_record = H.encoded({"retirement": "KNOWN", "index": index})
        self.assertTrue(H.error_detail(value)["retirementUnknown"])


class Memory:
    def __init__(self):
        self.data, self.directories, self.events, self.errors = {}, set(), [], {}

    def root(self, path):
        path = Path(path)
        self.directories.add(str(path))
        return Owner(self, path)

    def fail(self, event):
        self.events.append(event)
        if event in self.errors:
            raise self.errors[event]


class Owner:
    def __init__(self, memory, path):
        self.memory, self.path, self.closed = memory, Path(path), False

    def create_directory(self, name):
        path = self.path / name
        H.require(str(path) not in self.memory.directories, "MODEL_DIRECTORY_REPLAY")
        return self.memory.root(path)

    def open_directory(self, name):
        path = self.path / name
        H.require(str(path) in self.memory.directories, "MODEL_DIRECTORY_ABSENT")
        return Owner(self.memory, path)

    def create_file(self, name, *, max_bytes, deadline=None):
        path = str(self.path / name)
        self.memory.fail("create:" + path)
        H.require(path not in self.memory.data, "MODEL_EXCLUSIVE_CREATE")
        self.memory.data[path] = b""
        return Sink(self.memory, path, max_bytes)

    def read_bytes(self, name, *, max_bytes, deadline=None):
        self.memory.fail("read:" + str(self.path / name))
        raw = self.memory.data[str(self.path / name)]
        H.require(len(raw) <= max_bytes, "MODEL_READ_BOUND")
        return raw

    def snapshot(self, **kwargs):
        owner = self
        class Snapshot:
            def __init__(self):
                self.entries = {"": None}
                for key in owner.memory.data:
                    path = Path(key)
                    if owner.path in path.parents:
                        self.entries[path.relative_to(owner.path).as_posix()] = None
            def __enter__(self): return self
            def __exit__(self, *args): owner.memory.fail("snapshot-close:" + str(owner.path))
            def verify(self): owner.memory.fail("snapshot-verify:" + str(owner.path))
            def open_file(self, name):
                class Reader(io.BytesIO):
                    def verify(self): pass
                return Reader(owner.read_bytes(name, max_bytes=H.MAX_RECORD))
        return Snapshot()

    def close(self):
        self.memory.fail("close:" + str(self.path))
        self.closed = True

    def __enter__(self): return self
    def __exit__(self, *args): self.close()


class Sink:
    def __init__(self, memory, path, maximum):
        self.memory, self.path, self.maximum, self.closed = memory, path, maximum, False

    def write(self, raw):
        self.memory.fail("write:" + self.path)
        self.memory.data[self.path] += bytes(raw)
        return len(raw)

    def sync(self): self.memory.fail("sync:" + self.path)

    def verify(self):
        self.memory.fail("verify:" + self.path)
        size = len(self.memory.data[self.path])
        if size > self.maximum:
            raise ValueError("MODEL native output exceeded its byte bound")
        return SimpleNamespace(size=size, as_dict=lambda: {"size": size, "fixture": "MEMORY_NOT_NATIVE"})

    def close(self):
        self.memory.fail("close:" + self.path)
        self.closed = True

    def __enter__(self): return self
    def __exit__(self, *args): self.close()


class Scope:
    def __init__(self, memory):
        self.memory, self.close_calls, self.drain_calls, self.code = memory, 0, 0, 0
        self.outputs = (b"MODEL-original\x00\xff\r\n", b"MODEL-error\r\n")
        self.errors = {}

    def phase(self, name):
        self.memory.events.append("scope-" + name)
        if name in self.errors: raise self.errors[name]

    def spawn(self, argv, cwd, env, *, stdout, stderr):
        self.phase("spawn")
        for stream, raw in zip((stdout, stderr), self.outputs):
            stream.memory.data[stream.path] = raw  # Models child writes bypassing NativeFile.write's cap.
        return SimpleNamespace(stdout=None, stderr=None, poll=lambda: self.code)

    def discover(self):
        self.phase("discover"); return []

    def drain(self, **kwargs):
        self.drain_calls += 1; self.phase("drain"); return []

    def description(self):
        self.phase("description"); return {"discoveryErrors": [], "launches": [{"created": True}]}

    def close(self):
        self.close_calls += 1; self.phase("close")


class CommandModels(Models):
    def setUp(self):
        super().setUp()
        self.memory = Memory()
        self.scope = Scope(self.memory)
        self.set(H.processes, "make_scope", return_value=self.scope)
        self.command = H.Commands(self.memory.root("/model/evidence"), self.memory.root("/model/state"), "1" * 32,
                                  deadline=time.monotonic() + 30, environment={})

    def run_command(self, **kwargs):
        return self.command.run(["MODEL-NOT-EXECUTED"], "tiny", **kwargs)

    def test_known_command_keeps_original_bytes_and_closes_duplicates_before_writers(self):
        row, directory = self.run_command()
        self.assertEqual(row["waitExitCode"], 0)
        self.assertEqual(row["retirement"], "KNOWN")
        for label, raw in zip(("stdout", "stderr"), self.scope.outputs):
            path = str(directory.path / (label + ".bin"))
            self.assertEqual(H.private_read(directory, label + ".bin"), raw)
            self.assertEqual(row["outputs"][label]["sha256"], H.digest(raw))
            self.assertLess(self.memory.events.index("scope-close"), self.memory.events.index("close:" + path))
        self.assertEqual(self.scope.close_calls, 1)
        self.command.close()

    def test_nonzero_child_exit_is_retained_not_relabelled_as_success(self):
        self.scope.code = 17
        row, _ = self.run_command()
        self.assertEqual(row["waitExitCode"], 17)

    def test_spawn_failure_retains_original_record_and_independent_drain_close(self):
        original = OSError("MODEL spawn failure")
        self.scope.errors["spawn"] = original
        with self.assertRaises(H.encrypted.WindowsEvidenceError) as caught:
            self.run_command()
        self.assertIs(caught.exception.original, original)
        self.assertEqual(self.scope.close_calls, 1)
        self.assertEqual(self.scope.drain_calls, 1)
        self.assertTrue(any("helper-command-result-" in name for name in self.memory.data))

    def test_second_sink_allocation_failure_retires_first_sink_without_a_launch(self):
        self.memory.errors["create:/model/evidence/command-1-tiny/stderr.bin"] = MemoryError("MODEL second sink")
        with self.assertRaises(H.encrypted.WindowsEvidenceError): self.run_command()
        self.assertNotIn("scope-spawn", self.memory.events)
        self.assertIn("close:/model/evidence/command-1-tiny/stdout.bin", self.memory.events)

    def test_known_constructor_failure_retires_the_preallocated_sinks(self):
        self.set(H.processes, "make_scope", side_effect=OSError("MODEL construction"))
        with self.assertRaises(H.encrypted.WindowsEvidenceError) as caught: self.run_command()
        self.assertFalse(caught.exception.retirement_unknown)
        self.assertIn("close:/model/evidence/command-1-tiny/stderr.bin", self.memory.events)

    def test_constructor_unknown_carrier_preserves_actual_borrowed_pin_objects(self):
        original = OSError("MODEL partial native construction")
        original._p2pkit_retirement = {"status": "UNKNOWN", "resources": [], "omitted": 0}
        self.set(H.processes, "make_scope", side_effect=original)
        with self.assertRaises(H.encrypted.WindowsEvidenceError) as caught: self.run_command()
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertTrue(self.command.unknown)
        session = H.encrypted._QUARANTINE[0]
        self.assertTrue(all(row["quarantined"] and not row["owner"].closed for row in session.resources))
        self.assertIn(self.command.evidence, session.borrowed)
        self.assertIn(self.command.state, session.borrowed)

    def test_each_native_finalizer_failure_is_sticky_unknown_and_does_not_close_borrowed_sinks(self):
        for phase in ("drain", "description", "close"):
            with self.subTest(phase=phase):
                # Separate model instance, not a production latch reset/retry.
                memory = Memory(); scope = Scope(memory); scope.errors[phase] = OSError("MODEL " + phase)
                command = H.Commands(memory.root("/case/evidence"), memory.root("/case/state"), "2" * 32,
                                     deadline=time.monotonic() + 30, environment={})
                with patch.object(H.encrypted, "_QUARANTINE", []), patch.object(H.processes, "make_scope", return_value=scope):
                    with self.assertRaises(H.encrypted.WindowsEvidenceError): command.run(["MODEL"], "tiny")
                    self.assertTrue(command.unknown)
                    self.assertEqual(scope.close_calls, 1)
                    self.assertNotIn("close:/case/evidence/command-1-tiny/stdout.bin", memory.events)
                    with self.assertRaisesRegex(H.HelperError, "PRIOR_COMMAND_RETIREMENT_UNKNOWN"):
                        command.run(["MODEL"], "next")

    def test_cancellation_object_survives_command_and_attachment_recording(self):
        original = KeyboardInterrupt("MODEL cancellation")
        self.scope.errors["spawn"] = original
        with self.assertRaises(KeyboardInterrupt) as caught: self.run_command()
        self.assertIs(caught.exception, original)
        self.assertTrue(hasattr(original, "_p2pkit_windows_evidence"))
        self.assertEqual(self.scope.close_calls, 1)

    def test_output_limit_is_observed_even_when_the_child_already_exited(self):
        with self.assertRaises(H.encrypted.WindowsEvidenceError) as caught: self.run_command(output_limit=8)
        self.assertIn("byte bound", json.dumps(H.error_detail(caught.exception)))
        self.assertEqual(self.scope.drain_calls, 1)
        self.assertEqual(self.scope.close_calls, 1)

    def test_one_writer_close_failure_does_not_skip_sibling_close_and_blocks_reuse(self):
        self.memory.errors["close:/model/evidence/command-1-tiny/stdout.bin"] = OSError("MODEL close")
        with self.assertRaises(H.encrypted.WindowsEvidenceError): self.run_command()
        self.assertIn("close:/model/evidence/command-1-tiny/stderr.bin", self.memory.events)
        self.assertTrue(self.command.unknown)
        with self.assertRaises(H.HelperError): self.command.close()

    def test_partial_record_retention_failure_cannot_return_a_successful_command(self):
        self.memory.errors["write:/model/evidence/command-1-tiny/start.json"] = OSError("MODEL journal")
        with self.assertRaises(H.encrypted.WindowsEvidenceError): self.run_command()
        self.assertNotIn("scope-spawn", self.memory.events)

    def test_capture_reopen_failure_preserves_original_retired_command(self):
        self.memory.errors["read:/model/evidence/command-1-tiny/stdout.bin"] = OSError("MODEL reopen")
        with self.assertRaises(OSError): self.run_command()
        self.assertEqual(self.scope.close_calls, 1)
        self.assertIn("/model/evidence/command-1-tiny/stdout.bin", self.memory.data)

    def test_directory_close_unknown_stays_held_and_other_owned_directories_are_attempted(self):
        self.run_command()
        self.memory.errors["close:/model/evidence/command-1-tiny"] = OSError("MODEL root close")
        with self.assertRaises(H.HelperError): self.command.close()
        self.assertIn(self.command, H._HELD)
        with self.assertRaises(H.HelperError): self.command.run(["MODEL"], "next")

    def test_shared_cancellation_blocks_next_child_but_allows_finite_final_source_observation(self):
        cancellation = [15]
        command = H.Commands(self.command.evidence, self.command.state, "2" * 32,
                             deadline=time.monotonic() + 30, environment={}, cancellation=cancellation)
        self.assertIs(command.cancelled, cancellation)
        with self.assertRaises(H.encrypted.WindowsEvidenceError): command.run(["MODEL"], "cancelled")
        self.assertNotIn("scope-spawn", self.memory.events)
        row, _ = command.run(["MODEL"], "final-source", finalizing=True)
        self.assertEqual(row["waitExitCode"], 0)

    def test_bounds_and_existing_quarantine_refuse_before_allocating_or_spawning(self):
        for kwargs in ({"timeout": True}, {"timeout": 301}, {"output_limit": 0}, {"output_limit": H.MAX_OUTPUT + 1}):
            with self.assertRaises(H.HelperError): self.run_command(**kwargs)
        H.encrypted._QUARANTINE.append(object())
        with self.assertRaises(H.HelperError): self.run_command()
        self.assertEqual(self.memory.events, [])

    def test_another_commands_native_root_hold_blocks_every_new_phase(self):
        H._HELD.append(object())
        with self.assertRaisesRegex(H.HelperError, "PRIOR_COMMAND_RETIREMENT_UNKNOWN"):
            self.run_command(finalizing=True)
        self.assertEqual(self.memory.events, [])


class AcceptanceModels(Models):
    def test_inventory_derives_current_inherited_executor109_and_files58(self):
        raw = (SCRIPTS / "tests/run-audit-command-test.py").read_bytes()
        inv = H.method_inventory(raw, ["PurePolicyTests", "DarwinObservationTests", "WindowsNativeTests"])
        self.assertEqual({key: len(value) for key, value in inv.items()},
                         {"PurePolicyTests": 35, "DarwinObservationTests": 32, "WindowsNativeTests": 42})
        raw = (SCRIPTS / "tests/hosted-windows-files-test.py").read_bytes()
        inv = H.method_inventory(raw, ["PurePolicyTests", "NativeCallShapeTests", "ModelCustodyTests",
                                      "NativeFixtureOrchestrationTests", "NativeWindowsTests"])
        self.assertEqual(sum(map(len, inv.values())), 58)
        self.assertEqual(len(inv["NativeWindowsTests"]), 7)

    def test_original_unittest_method_outcomes_accept_both_supported_verbose_shapes(self):
        inventory = {"Case": ["test_one", "test_two"]}
        for shape in ("Case", "Case.{name}"):
            raw = "".join(name + " (__main__." + shape.format(name=name) + ") ... ok\n" for name in inventory["Case"])
            H.assert_unittest((raw + "\nRan 2 tests in 0.010s\n\nOK\n").encode(), inventory)

    def test_missing_duplicate_skipped_expected_failure_and_wrong_counts_refuse(self):
        good = b"test_one (__main__.Case) ... ok\ntest_two (__main__.Case) ... ok\nRan 2 tests in 0.001s\nOK\n"
        for bad in (good.replace(b"test_two", b"test_one"), good.replace(b"Ran 2", b"Ran 1"),
                    good.replace(b"... ok", b"... skipped", 1), good.replace(b"... ok", b"... expected failure", 1),
                    good.replace(b"OK", b"OK (skipped=1)"), good + b"Ran 2 tests in 0.001s\n"):
            with self.assertRaises(H.HelperError): H.assert_unittest(bad, {"Case": ["test_one", "test_two"]})

    def sample(self):
        identity = admitted()
        observation = {"cases": [{"mode": "constructor", "outputRenamedAfterFailure": True, "sourceStillCallerOwned": True},
                                {"mode": "not-started", "completionAcknowledged": True, "workerRetired": True},
                                {"mode": "started-cancel", "completionAcknowledged": True, "workerRetired": True,
                                 "originalCancellation": True}], "finishPolicySeconds": 3}
        raw = H.encoded(observation)
        result = {"schema": 1, "case": "native-tee", "native": True, "passed": True,
                  "source": {"commit": identity["sourceSha"], "tree": identity["sourceTree"]},
                  "run": {"id": identity["runId"], "attempt": identity["runAttempt"]},
                  "observations": [{"path": "actual-tee-paths.json", "sha256": H.digest(raw)}],
                  "privateDecryption": "NOT_RUN", "expectedPinHoldToInterpreterExit": False, "retirement": "KNOWN",
                  "acceptanceAuthority": "PARENT_ZERO_EXIT_AND_NATIVE_JOB_RETIREMENT"}
        return identity, result, raw

    def test_native_case_requires_bound_original_observations_after_outer_retirement(self):
        identity, result, raw = self.sample()
        H.assert_native_result("native-tee", result, identity, lambda _: raw)

    def test_native_success_label_alone_wrong_source_run_and_unobserved_pin_hold_refuse(self):
        identity, result, raw = self.sample()
        for field, value in (("retirement", "UNKNOWN"), ("expectedPinHoldToInterpreterExit", True),
                             ("privateDecryption", "PASS"), ("acceptanceAuthority", "SELF"), ("passed", 1),
                             ("source", {"commit": "c" * 40, "tree": "b" * 40}), ("run", {"id": "124", "attempt": "2"})):
            changed = copy.deepcopy(result); changed[field] = value
            with self.assertRaises(H.HelperError): H.assert_native_result("native-tee", changed, identity, lambda _: raw)

    def test_mutated_missing_and_duplicate_native_observations_refuse(self):
        identity, result, raw = self.sample()
        with self.assertRaises(H.HelperError): H.assert_native_result("native-tee", result, identity, lambda _: raw + b" ")
        for rows in ([], result["observations"] * 2, [{"path": "../other", "sha256": H.digest(raw)}]):
            changed = copy.deepcopy(result); changed["observations"] = rows
            with self.assertRaises(H.HelperError): H.assert_native_result("native-tee", changed, identity, lambda _: raw)

    def test_tee_timeout_relaxation_and_missing_worker_ack_are_not_accepted(self):
        identity, result, raw = self.sample()
        for transform in (lambda v: v.update(finishPolicySeconds=30), lambda v: v["cases"][1].update(workerRetired=False)):
            observation = H.decode(raw); transform(observation)
            altered = H.encoded(observation); result["observations"][0]["sha256"] = H.digest(altered)
            with self.assertRaises(H.HelperError): H.assert_native_result("native-tee", result, identity, lambda _: altered)

    def test_fixed_native_case_inventory_matches_definitions_and_separate_interpreters(self):
        tree = ast.parse((SCRIPTS / "tests/windows-helper-native-test.py").read_bytes())
        case = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Fixture")
        methods = {node.name.replace("_", "-") for node in case.body if isinstance(node, ast.FunctionDef) and node.name.startswith("native_")}
        self.assertEqual(methods - {"native-scope"}, set(H.NATIVE_CASES))
        self.assertEqual(set(H.NATIVE_OBSERVATIONS), set(H.NATIVE_CASES))

    def test_maintained_entrypoint_loads_this_model_suite_exactly_once(self):
        tree = ast.parse((SCRIPTS / "tests/run-windows-directory-control-test.py").read_bytes())
        hooks = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load_tests"]
        self.assertEqual(len(hooks), 1)
        loader = SimpleNamespace(loadTestsFromModule=lambda module: "MODEL_SUITE")
        tests = SimpleNamespace(addTests=lambda value: seen.append(value)); seen = []
        fake = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _: None), name="model_entry_hook")
        context = {"importlib": SimpleNamespace(util=SimpleNamespace(spec_from_file_location=lambda *args: fake,
                      module_from_spec=lambda _: object())), "sys": SimpleNamespace(modules={}), "ROOT": H.ROOT}
        exec(compile(ast.Module(body=hooks, type_ignores=[]), "reviewed-load-tests-hook", "exec"), context)
        self.assertIs(context["load_tests"](loader, tests, None), tests)
        self.assertEqual(seen, ["MODEL_SUITE"])


class RetentionModels(Models):
    def setUp(self):
        super().setUp()
        self.memory = Memory()
        self.retention = T.NativeRetention.__new__(T.NativeRetention)
        self.retention.root = self.memory.root("/retained")
        self.retention.events, self.retention.completed, self.retention.unknown = [], [], False
        self.retention.detail = H.encrypted._exception_detail
        model = T.NativeFixtureOrchestrationTests()
        self.case = model.case()
        self.case.root.verify = lambda: SimpleNamespace(identity=(1, "synthetic"), protected_dacl=True, owner_sid=T.USER,
                                                        as_dict=lambda: {"fixture": "MODEL"})
        self.set(T, "RETENTION", new=self.retention)
        self.removal = self.set(T.shutil, "rmtree")

    def test_original_bytes_are_retained_before_disposal_with_size_and_hash(self):
        raw = b"MODEL-original\x00\xff\r\n"
        self.retention.original(self.case, "native-input", raw)
        self.case.cleanup_fixture()
        self.assertEqual(self.memory.data["/retained/original-0001.bin"], raw)
        rows = self.retention.events
        self.assertEqual([row["phase"] for row in rows], ["original-bytes", "retirement-known-before-disposal", "fixture-disposed"])
        self.assertEqual(rows[0]["sha256"], H.digest(raw))
        self.removal.assert_called_once_with(self.case.parent)
        self.assertEqual(self.retention.completed, [self.case._testMethodName])

    def test_pre_disposal_journal_failure_preserves_the_fixture(self):
        self.memory.errors["write:/retained/event-0001.json"] = OSError("MODEL journal")
        with self.assertRaises(OSError): self.case.cleanup_fixture()
        self.removal.assert_not_called()
        self.assertTrue(self.case.retirement_unknown)
        self.assertTrue(self.retention.unknown)

    def test_original_failure_cause_and_cancellation_survive_secondary_retention_error(self):
        original = KeyboardInterrupt("MODEL primary")
        cause = ValueError("MODEL cause"); original.__cause__ = cause
        self.memory.errors["write:/retained/event-0001.json"] = OSError("MODEL journal")
        with self.assertRaises(KeyboardInterrupt) as caught: self.retention.failure(self.case, "failure", original)
        self.assertIs(caught.exception, original)
        self.assertIs(original.__cause__, cause)
        self.assertTrue(any("retention UNKNOWN" in note for note in original.__notes__))

    def test_unknown_child_retirement_never_becomes_disposal_authority(self):
        self.case.retirement_unknown = True
        self.case.cleanup_fixture()
        self.assertTrue(self.retention.unknown)
        self.removal.assert_not_called()
        self.assertEqual(self.retention.events[-1]["phase"], "preserved-unknown")

    def test_native_root_close_failure_is_retained_before_any_disposal(self):
        original = OSError("MODEL close"); original.__notes__ = ["Native handle retirement UNKNOWN: 1"]
        self.case.root.close_error = original
        with self.assertRaises(OSError) as caught: self.case.cleanup_fixture()
        self.assertIs(caught.exception, original)
        self.removal.assert_not_called()
        self.assertEqual(self.retention.events[0]["phase"], "root-close-failure")

    def test_expected_rejection_records_original_cause_but_does_not_consume_unknown(self):
        original = T.files.FilesystemError("MODEL expected"); original.__notes__ = ["Native handle retirement UNKNOWN: 1"]
        with self.assertRaises(T.files.FilesystemError) as caught:
            with self.case.expected_rejection(T.files.FilesystemError): raise original
        self.assertIs(caught.exception, original)
        self.assertTrue(self.retention.unknown)

    def test_disposal_failure_and_original_bytes_remain_retained(self):
        self.retention.original(self.case, "sentinel", b"MODEL")
        self.removal.side_effect = OSError("MODEL disposal")
        with self.assertRaises(OSError): self.case.cleanup_fixture()
        self.assertIn("/retained/original-0001.bin", self.memory.data)
        self.assertEqual(self.retention.events[-1]["phase"], "fixture-disposal-failure")
        self.assertEqual(self.retention.completed, [])

    def test_native_orchestration_models_cannot_contaminate_hosted_native_journal(self):
        model = T.NativeFixtureOrchestrationTests("test_setup_unknown_retains_fixture_and_does_not_start_a_body")
        result = unittest.TestResult()
        model.run(result)
        self.assertTrue(result.wasSuccessful(), (result.failures, result.errors))
        self.assertIs(T.RETENTION, self.retention)
        self.assertEqual(self.retention.events, [])

    def result(self):
        return SimpleNamespace(wasSuccessful=lambda: True, skipped=[], expectedFailures=[], unexpectedSuccesses=[],
                               testsRun=58, failures=[], errors=[])

    def test_late_journal_close_failure_refuses_provisional_native_summary(self):
        self.retention.completed = ["test_native"]
        self.memory.errors["close:/retained"] = OSError("MODEL journal last close")
        with self.assertRaises(OSError): T.finalize_retention(self.retention, self.result(), ["test_native"])
        self.assertTrue(self.retention.unknown)
        self.assertIn("/retained/summary.json", self.memory.data)

    def test_summary_retention_cancellation_survives_independent_late_close_failure(self):
        original = KeyboardInterrupt("MODEL summary cancellation")
        self.memory.errors["write:/retained/summary.json"] = original
        self.memory.errors["close:/retained"] = OSError("MODEL late close")
        with self.assertRaises(KeyboardInterrupt) as caught:
            T.finalize_retention(self.retention, self.result(), ["test_native"])
        self.assertIs(caught.exception, original)
        self.assertTrue(any("final close UNKNOWN" in note for note in original.__notes__))

    def test_skipped_or_incomplete_native_methods_cannot_be_a_pass(self):
        for skipped, completed in (([], []), (["test_native"], ["test_native"])):
            memory = Memory(); retention = T.NativeRetention.__new__(T.NativeRetention)
            retention.root, retention.detail = memory.root("/own"), H.encrypted._exception_detail
            retention.unknown, retention.completed = False, completed
            result = self.result(); result.skipped = skipped
            with self.assertRaises(T.files.FilesystemError): T.finalize_retention(retention, result, ["test_native"])
            self.assertFalse(H.decode(memory.data["/own/summary.json"])["passed"])

    def test_fixture_parent_must_match_current_state_and_remain_disjoint(self):
        self.stack.enter_context(patch.dict(os.environ, {H.processes.STATE_ENV: "/owned-state"}))
        probe = self.set(T.files, "open_private_directory", side_effect=AssertionError("MODEL wrong path reached native API"))
        for destination, parent in (("/evidence", "/wrong"), ("/owned-state/fixtures/native-tmp/evidence", "/owned-state/fixtures/native-tmp")):
            with self.assertRaises(T.files.FilesystemError): T.NativeRetention(destination, parent)
        probe.assert_not_called()

    def test_empty_exact_owned_fixture_parent_is_admitted_without_changing_temp(self):
        self.stack.enter_context(patch.dict(os.environ, {H.processes.STATE_ENV: "/owned-state", "TEMP": "untouched"}))
        self.set(T.files, "open_private_directory", return_value=self.memory.root("/owned-state/fixtures/native-tmp"))
        self.set(T.files, "create_private_directory", side_effect=self.memory.root)
        retention = T.NativeRetention("/evidence", "/owned-state/fixtures/native-tmp")
        self.assertEqual(retention.root.path, Path("/evidence"))
        self.assertEqual(os.environ["TEMP"], "untouched")


class SealModels(Models):
    def setUp(self):
        super().setUp()
        self.memory, self.identity = Memory(), admitted()
        self.base = self.memory.root("/helper")
        self.output = self.memory.root("/export")
        evidence = self.base.create_directory("evidence")
        self.source = {"commit": self.identity["sourceSha"], "tree": self.identity["sourceTree"], "files": {"MODEL": {}}}
        self.manifest = {"schema": 1, "scope": "ENCRYPTED_PRIVATE_TEST_EVIDENCE",
            "source": {"commit": self.identity["sourceSha"], "tree": self.identity["sourceTree"]},
            "github": {"repository": H.REPOSITORY, "runId": "123", "runAttempt": "2"}}
        raw = b"MODEL_CIPHERTEXT_NOT_ENCRYPTION"
        self.manifest["artifact"] = {"name": H.encrypted.portable.ARTIFACT, "size": len(raw), "sha256": H.digest(raw)}
        H.private_write(self.output, H.encrypted.portable.ARTIFACT, raw)
        H.private_json(self.output, H.encrypted.portable.MANIFEST, self.manifest)
        self.control_result = {"identity": self.identity, "retirement": "KNOWN", "controlsPassed": False}
        H.private_json(evidence, "controls-result.json", self.control_result)
        self.returned = {"schema": 1, "identity": self.identity, "retirement": "KNOWN", "controlsPassed": False,
            "manifest": self.manifest, "manifestSha256": H.digest(H.encoded(self.manifest)),
            "resultSha256": H.digest(H.encoded(self.control_result)), "privateDecryption": "NOT_RUN"}
        H.private_json(self.base, "return.json", self.returned)
        H.private_json(self.base, "source-binding.json", self.source)
        self.set(H, "actual_identity", return_value=self.identity)
        self.set(H, "paths", return_value=(self.base.path, self.output.path))
        self.set(H.files, "open_private_directory", side_effect=lambda path: Owner(self.memory, path))
        self.set(H, "admitted_tools", return_value=(Path("MODEL-python.exe"), Path("MODEL-git.exe"), {}))
        self.set(H, "source_snapshot", return_value=self.source)
        self.set(H.encrypted.portable, "_manifest_identity", return_value={key: value for key, value in self.manifest.items() if key != "artifact"})
        self.env = self.stack.enter_context(patch.dict(os.environ, {"P2PKIT_HELPER_RUN_OUTCOME": "success", "GITHUB_OUTPUT": "/model-output"}))
        self.set(H, "public_file", return_value=b"")
        self.authority = io.StringIO()
        class Output:
            def __enter__(_): return self.authority
            def __exit__(_, *args): return False
        self.writer = self.set(Path, "open", return_value=Output())
        self.set(H.os, "fsync", return_value=None)
        self.authority.fileno = lambda: -999  # Mocked fsync, not a real descriptor.
        self.set(H.sys, "stdout", new=io.StringIO())

    def test_failed_controls_can_retain_ciphertext_but_never_claim_pass(self):
        self.assertEqual(H.validate_public(), 0)
        self.assertEqual(self.authority.getvalue(), "artifacts_ready=true\ncontrols_passed=false\n")
        for path in ("/helper/post-return-validation", "/helper", "/export"):
            self.assertIn("close:" + path, self.memory.events)

    def test_controller_failed_or_cancelled_outcome_blocks_even_existing_ciphertext(self):
        for outcome in ("failure", "cancelled", "skipped", ""):
            os.environ["P2PKIT_HELPER_RUN_OUTCOME"] = outcome
            with self.assertRaisesRegex(H.HelperError, "CONTROLLER_DID_NOT_RETURN_SAFELY"): H.validate_public()
        self.writer.assert_not_called()

    def test_late_native_root_close_failure_cannot_write_upload_authority(self):
        self.memory.errors["close:/export"] = OSError("MODEL last close")
        with self.assertRaises(H.HelperError): H.validate_public()
        self.writer.assert_not_called()
        self.assertTrue(H._HELD)

    def test_post_return_source_and_event_changes_are_not_sealed(self):
        self.set(H, "source_snapshot", return_value={"changed": True})
        with self.assertRaisesRegex(H.HelperError, "POST_RETURN_SOURCE_CHANGED"): H.validate_public()
        self.writer.assert_not_called()

    def test_changed_final_event_blocks_upload(self):
        self.set(H, "actual_identity", side_effect=[self.identity, {"changed": True}])
        with self.assertRaisesRegex(H.HelperError, "POST_RETURN_EVENT_CHANGED"): H.validate_public()
        self.writer.assert_not_called()

    def test_truncated_or_changed_ciphertext_does_not_inherit_manifest_authority(self):
        self.memory.data["/export/" + H.encrypted.portable.ARTIFACT] = b"changed"
        with self.assertRaisesRegex(H.HelperError, "PUBLIC_CIPHERTEXT_DIFFERS"): H.validate_public()
        self.writer.assert_not_called()

    def test_extra_raw_file_prevents_even_ciphertext_only_upload_authority(self):
        self.memory.data["/export/raw-secret.log"] = b"MODEL_ONLY"
        with self.assertRaisesRegex(H.HelperError, "PUBLIC_INVENTORY_DIFFERS"): H.validate_public()
        self.writer.assert_not_called()

    def test_private_result_change_or_failed_result_relabelling_refuses(self):
        changed = dict(self.control_result, controlsPassed=True)
        self.memory.data["/helper/evidence/controls-result.json"] = H.encoded(changed)
        with self.assertRaisesRegex(H.HelperError, "PRIVATE_RESULT_BINDING_DIFFERS"): H.validate_public()
        self.writer.assert_not_called()

    def test_replayed_post_return_validation_cannot_overwrite_prior_seal(self):
        self.base.create_directory("post-return-validation")
        with self.assertRaisesRegex(H.HelperError, "MODEL_DIRECTORY_REPLAY"): H.validate_public()
        self.writer.assert_not_called()

    def test_manifest_tamper_refuses_even_when_ciphertext_is_unchanged(self):
        self.memory.data["/export/manifest.json"] += b" "
        with self.assertRaisesRegex(H.HelperError, "PUBLIC_MANIFEST_DIFFERS"): H.validate_public()
        self.writer.assert_not_called()

    def test_snapshot_close_failure_cannot_become_upload_authority(self):
        self.memory.errors["snapshot-close:/export"] = OSError("MODEL snapshot close")
        with self.assertRaises(OSError): H.validate_public()
        self.writer.assert_not_called()

    def test_original_seal_failure_keeps_secondary_native_close_details(self):
        self.memory.data["/export/raw.log"] = b"MODEL"
        self.memory.errors["close:/export"] = OSError("MODEL secondary close")
        with self.assertRaisesRegex(H.HelperError, "PUBLIC_INVENTORY_DIFFERS") as caught:
            H.validate_public()
        self.assertTrue(any("PRIVATE_ROOT_CLOSE_UNKNOWN" in note for note in caught.exception.__notes__))
        self.writer.assert_not_called()


class NativeFixtureFinalizationModels(Models):
    def fixture(self):
        fixture = N.Fixture.__new__(N.Fixture)
        memory = Memory(); root = memory.root("/native-model")
        child = root.create_directory("child")
        fixture.root, fixture.owners = root, [root, child]
        fixture.name, fixture.unknown, fixture.expected_hold = "native-sinks", False, False
        fixture.result = {"fixture": "MODEL_NOT_NATIVE"}
        fixture.observations = []
        fixture.native_sinks = lambda: None
        self.set(N.H, "_HELD", new=[])
        self.set(N.W, "_QUARANTINE", new=[])
        self.set(N, "_RETAIN_TO_EXIT", new=[])
        return fixture, memory

    def test_late_fixture_root_close_returns_failure_despite_provisional_result(self):
        fixture, memory = self.fixture()
        memory.errors["close:/native-model"] = OSError("MODEL late close")
        self.assertEqual(fixture.execute(), 1)
        result = H.decode(memory.data["/native-model/result.json"])
        self.assertEqual(result["acceptanceAuthority"], "PARENT_ZERO_EXIT_AND_NATIVE_JOB_RETIREMENT")
        self.assertIn(fixture, N._RETAIN_TO_EXIT)

    def test_child_close_failure_is_journalled_before_root_and_preserves_original(self):
        fixture, memory = self.fixture()
        original = KeyboardInterrupt("MODEL body cancellation")
        fixture.native_sinks = lambda: (_ for _ in ()).throw(original)
        memory.errors["close:/native-model/child"] = OSError("MODEL close")
        self.assertEqual(fixture.execute(), 1)
        result = H.decode(memory.data["/native-model/result.json"])
        self.assertEqual(result["failure"]["nodes"][0]["message"], "MODEL body cancellation")
        self.assertEqual(result["retirement"], "UNKNOWN")
        self.assertNotIn("close:/native-model", memory.events)

    def test_expected_pin_hold_is_not_closed_or_relabelled_known_in_child(self):
        fixture, memory = self.fixture(); fixture.expected_hold = True
        self.assertEqual(fixture.execute(), 0)
        result = H.decode(memory.data["/native-model/result.json"])
        self.assertEqual(result["retirement"], "EXPECTED_PIN_HOLD_TO_EXIT")
        self.assertNotIn("close:/native-model", memory.events)
        self.assertNotIn("close:/native-model/child", memory.events)

    def test_unexpected_quarantine_refuses_success_and_preserves_every_owner(self):
        fixture, memory = self.fixture(); N.W._QUARANTINE.append(object())
        self.assertEqual(fixture.execute(), 1)
        self.assertFalse(H.decode(memory.data["/native-model/result.json"])["passed"])
        self.assertNotIn("close:/native-model", memory.events)
        self.assertNotIn("close:/native-model/child", memory.events)

    def test_fixture_journal_failure_never_grants_success_or_cleanup(self):
        fixture, memory = self.fixture()
        memory.errors["write:/native-model/result.json"] = OSError("MODEL result retention")
        self.assertEqual(fixture.execute(), 1)
        self.assertNotIn("close:/native-model", memory.events)
        self.assertIn(fixture, N._RETAIN_TO_EXIT)


class SourceBindingModels(Models):
    def setUp(self):
        super().setUp()
        import hashlib
        self.memory, self.raw, self.queries = Memory(), b"MODEL source\n", []
        self.set(H, "ROOT", new=Path(r"C:\source"))
        blob = hashlib.sha1(b"blob " + str(len(self.raw)).encode() + b"\0" + self.raw).hexdigest()
        self.responses = {("rev-parse", "--show-toplevel"): b"C:\\source\n",
            ("rev-parse", "HEAD"): b"a" * 40 + b"\n", ("rev-parse", "HEAD^{tree}"): b"b" * 40 + b"\n",
            ("rev-parse", "--is-shallow-repository"): b"false\n",
            ("status", "--porcelain=v1", "--untracked-files=all", "--ignored"): b"",
            ("config", "--get", "remote.origin.url"): b"https://github.com/p2pKit/P2pKit.git\n",
            ("ls-tree", "-rlz", "HEAD"): b"100644 blob " + blob.encode() + b" " + str(len(self.raw)).encode() + b"\tfile.txt" + bytes([0])}
        self.set(H, "public_file", return_value=self.raw)
        def query(argv, name, **kwargs):
            key = tuple(argv[argv.index("-C") + 2:]); self.queries.append((argv, kwargs))
            root = self.memory.root("/source-query-" + str(len(self.queries)))
            H.private_write(root, "stdout.bin", self.responses[key])
            return {"waitExitCode": 0}, root
        self.commands = SimpleNamespace(state=SimpleNamespace(path=Path("/model-state")), run=query)

    def test_actual_blob_counterparts_not_worktree_status_alone_bind_every_byte(self):
        result = H.source_snapshot(self.commands, Path("MODEL-git"))
        self.assertEqual(result["files"]["file.txt"]["sha256"], H.digest(self.raw))
        self.assertEqual(len(self.queries), 7)
        self.assertTrue(all("--no-replace-objects" in argv and "credential.helper=" in argv for argv, _ in self.queries))

    def test_clean_status_with_filtered_or_modified_bytes_is_refused(self):
        self.set(H, "public_file", return_value=self.raw.replace(b"\n", b"\r\n"))
        with self.assertRaisesRegex(H.HelperError, "TRACKED_SOURCE_BYTES_DIFFER"):
            H.source_snapshot(self.commands, Path("MODEL-git"))

    def test_shallow_checkouts_are_not_current_source_evidence(self):
        self.responses[("rev-parse", "--is-shallow-repository")] = b"true\n"
        with self.assertRaisesRegex(H.HelperError, "FULL_HISTORY_REQUIRED"):
            H.source_snapshot(self.commands, Path("MODEL-git"))

    def test_final_source_queries_use_only_finite_finalization_authority(self):
        H.source_snapshot(self.commands, Path("MODEL-git"), finalizing=True)
        self.assertTrue(all(options == {"timeout": 60, "finalizing": True} for _, options in self.queries))

    def test_source_observations_are_fixed_and_preserve_query_order_flags_and_bounds(self):
        stages = []
        H.source_snapshot(self.commands, Path("MODEL-git"), observe=stages.append)
        self.assertEqual(stages, [H.Stage.SOURCE_TOPLEVEL, H.Stage.SOURCE_HEAD, H.Stage.SOURCE_TREE,
            H.Stage.SOURCE_SHALLOW, H.Stage.SOURCE_STATUS, H.Stage.SOURCE_ORIGIN,
            H.Stage.SOURCE_ENTRIES, H.Stage.SOURCE_BYTES])
        self.assertEqual(len(self.queries), 7)
        self.assertTrue(all(options == {"timeout": 60, "finalizing": False} for _, options in self.queries))

    def test_failed_source_query_keeps_its_exact_stage_without_runtime_values(self):
        self.responses[("rev-parse", "--is-shallow-repository")] = b"true\n"
        progress = H.Progress()
        with self.assertRaisesRegex(H.HelperError, "FULL_HISTORY_REQUIRED"):
            H.source_snapshot(self.commands, Path("MODEL-git"), observe=progress.mark)
        self.assertEqual(progress.stage, H.Stage.SOURCE_SHALLOW)
        self.assertEqual(len(self.queries), 4)


class PublicFailureModels(Models):
    def display(self, stage, error):
        output = io.StringIO()
        with patch.object(H.sys, "stderr", output):
            value = H.public_observation(stage, H.error_detail(error))
            H.print_public_failure(value)
        self.assertEqual(set(value), set(H._PUBLIC_FIELDS))
        for name, domain in H._PUBLIC_FIELDS.items():
            self.assertIn(value[name], {member.value for member in domain})
        return value, output.getvalue()

    def test_code_shaped_untyped_and_helper_errors_never_become_public_codes(self):
        for error in (OSError("MODEL_PRIVATE_SENTINEL"), H.HelperError("MODEL_PRIVATE_SENTINEL")):
            with self.subTest(kind=type(error).__name__):
                value, text = self.display(H.Stage.PYTHON_TOOL, error)
                self.assertNotIn("MODEL_PRIVATE_SENTINEL", text)
                self.assertEqual(value["stage"], "PYTHON_TOOL")

    def test_forged_code_accessor_and_hostile_exception_diagnostics_cannot_escape(self):
        class Hostile(H.HelperError):
            def __init__(self):
                RuntimeError.__init__(self, "MODEL_PRIVATE_SENTINEL")
            @property
            def code(self):
                raise AssertionError("MODEL PRIVATE ACCESSOR SHOULD NOT RUN")
            def __str__(self):
                raise RuntimeError("MODEL PRIVATE STR")
            @property
            def private_record(self):
                raise RuntimeError("MODEL PRIVATE RECORD")
        value, text = self.display(H.Stage.RECIPIENT, Hostile())
        self.assertEqual(value["retirementObservation"], "UNKNOWN")
        self.assertNotIn("MODEL", text)

    def test_every_public_field_requires_exact_finite_membership(self):
        value = H.public_observation(H.Stage.SOURCE_HEAD, {})
        for name in H._PUBLIC_FIELDS:
            with self.subTest(field=name):
                output = io.StringIO()
                with patch.object(H.sys, "stderr", output):
                    H.print_public_failure({**value, name: "MODEL_PRIVATE_SENTINEL"})
                self.assertNotIn("MODEL_PRIVATE_SENTINEL", output.getvalue())
                self.assertIn("stage=UNOBSERVED", output.getvalue())

    def test_native_error_projection_is_typed_and_finite_not_raw_message_or_number(self):
        for error, operation, status in (
            (H.files.FilesystemError("Windows NtCreateFile failed (error 5)"), "FILE_CREATE", "ACCESS_DENIED"),
            (H.processes.OwnershipError("Windows CreateProcessW (atomic job assignment) failed: error 87"),
             "PROCESS_CREATE", "INVALID_PARAMETER"),
            (H.files.FilesystemError("Windows ReadFile failed (error 1234567890)"), "FILE_READ", "OTHER_NATIVE_ERROR"),
            (OSError("Windows NtCreateFile failed (error 5)"), "UNOBSERVED", "UNOBSERVED"),
            (H.files.FilesystemError("Windows MODEL_PRIVATE_SENTINEL failed (error 5)"), "UNOBSERVED", "UNOBSERVED")):
            with self.subTest(operation=operation, status=status):
                value, text = self.display(H.Stage.SOURCE_HEAD, error)
                self.assertEqual((value["nativeOperation"], value["nativeStatus"]), (operation, status))
                self.assertNotIn("1234567890", text)
                self.assertNotIn("MODEL_PRIVATE_SENTINEL", text)

    def test_recipient_records_expose_only_last_fixed_command_and_exit_category(self):
        common = ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint"]
        for arguments, step in ((["--version"], "VERSION"),
             (common + ["--import-options", "show-only", "--import", "MODEL_PRIVATE_KEY_PATH"], "SHOW_ONLY"),
             (common + ["--list-keys"], "LIST_KEYS"), (["MODEL_PRIVATE_SENTINEL"], "UNRECOGNIZED_COMMAND")):
            for code, outcome in ((None, "NO_EXIT_CODE"), (0, "ZERO"), (2, "NONZERO"), (True, "NO_EXIT_CODE")):
                with self.subTest(step=step, outcome=outcome):
                    record = {"operation": "recipient-validation", "retirement": "KNOWN",
                              "commands": [{"argv": ["MODEL_PRIVATE_GPG_PATH", *arguments], "waitExitCode": code}]}
                    error = H.encrypted.WindowsEvidenceError(OSError("MODEL PRIVATE"), H.encoded(record), False)
                    value, text = self.display(H.Stage.RECIPIENT, error)
                    self.assertEqual((value["lastGpgCommand"], value["lastGpgExit"]), (step, outcome))
                    self.assertNotIn("MODEL", text)

    def test_recipient_native_details_and_earlier_stage_do_not_invent_gpg_execution(self):
        record = {"operation": "recipient-validation", "retirement": "KNOWN", "commands": [],
                  "failures": [{"detail": H.error_detail(H.files.FilesystemError(
                      "Windows GetFileInformationByHandleEx failed (error 50)"))}]}
        error = H.encrypted.WindowsEvidenceError(OSError("MODEL PRIVATE"), H.encoded(record), False)
        value, _ = self.display(H.Stage.RECIPIENT, error)
        self.assertEqual(value["nativeOperation"], "FILE_INFORMATION")
        self.assertEqual(value["lastGpgCommand"], "UNOBSERVED")
        record["commands"] = [{"argv": ["MODEL_PRIVATE_GPG", "--version"], "waitExitCode": 0}]
        error = H.encrypted.WindowsEvidenceError(OSError("MODEL PRIVATE"), H.encoded(record), False)
        value, _ = self.display(H.Stage.SOURCE_HEAD, error)
        self.assertEqual(value["lastGpgCommand"], "UNOBSERVED")

    def test_main_does_not_read_arbitrary_helper_code_accessor(self):
        class Hostile(H.HelperError):
            def __init__(self):
                RuntimeError.__init__(self, "MODEL_PRIVATE_SENTINEL")
            @property
            def code(self):
                raise AssertionError("MODEL PRIVATE ACCESSOR SHOULD NOT RUN")
        output = io.StringIO()
        self.set(H.sys, "argv", new=["helper", "run"])
        self.set(H.sys, "stderr", new=output)
        self.set(H, "run", side_effect=Hostile())
        self.assertEqual(H.main(), 1)
        self.assertNotIn("MODEL", output.getvalue())

class RunFailureModels(Models):
    def setUp(self):
        super().setUp()
        self.memory, self.identity = Memory(), admitted()
        self.source = {"commit": self.identity["sourceSha"], "tree": self.identity["sourceTree"], "files": {"MODEL": {}}}
        self.invocations, self.finalizations = [], []
        memory, invocations, finalizations = self.memory, self.invocations, self.finalizations
        class Runner:
            def __init__(_, evidence, state, job, *, deadline, environment=None, cancellation=None):
                _.evidence, _.state, _.deadline = evidence, state, deadline
                _.environment, _.unknown = {}, False
                _.cancelled = [] if cancellation is None else cancellation
            def run(_, args, label, **kwargs):
                invocations.append((label, args))
                capture = _.evidence.create_directory("original-" + label)
                H.private_write(capture, "stdout.bin", b"MODEL ORIGINAL SUITE OUTPUT")
                H.private_write(capture, "stderr.bin", b"MODEL ASSERTION FAILURE")
                return {"waitExitCode": 17}, capture
            def close(_):
                finalizations.append(str(_.state.path))
                memory.fail("runner-close:" + str(_.state.path))
        self.set(H, "Commands", new=Runner)
        self.set(H, "actual_identity", return_value=self.identity)
        self.set(H, "paths", return_value=(Path("/run-model"), Path("/export-model")))
        self.set(H.files, "create_private_directory", side_effect=self.memory.root)
        self.set(H, "admitted_tools", return_value=(Path("MODEL-python.exe"), Path("MODEL-git.exe"), {"MODEL": True}))
        self.source_call = self.set(H, "source_snapshot", side_effect=[self.source, self.source])
        recipient = SimpleNamespace(fingerprint="C" * 40, encryption_fingerprint="D" * 40, expires_at=0, key_sha256="e" * 64)
        self.set(H.encrypted, "validate_recipient", return_value=recipient)
        def export(evidence, output, recipient, **identity):
            raw = b"MODEL NOT ENCRYPTION"
            manifest = {"artifact": {"name": H.encrypted.portable.ARTIFACT, "size": len(raw), "sha256": H.digest(raw)}}
            H.private_write(output, H.encrypted.portable.ARTIFACT, raw)
            H.private_json(output, H.encrypted.portable.MANIFEST, manifest)
            return manifest
        self.export = self.set(H.encrypted, "export_encrypted", side_effect=export)
        self.stack.enter_context(patch.dict(os.environ, {"P2PKIT_EVIDENCE_PUBLIC_KEY": public_armor().decode()}))
        self.set(H.signal, "getsignal", return_value="MODEL_ORIGINAL_HANDLER")
        self.handlers = self.set(H.signal, "signal")
        self.stdout, self.stderr = io.StringIO(), io.StringIO()
        self.set(H.sys, "stdout", new=self.stdout); self.set(H.sys, "stderr", new=self.stderr)

    def test_failed_native_suite_stops_next_suites_but_preserves_safe_failure_export(self):
        self.assertEqual(H.run(), 0)
        self.assertEqual([label for label, _ in self.invocations], ["executor"])
        self.assertEqual(self.finalizations, ["/run-model/state/executor", "/run-model/state"])
        result = H.decode(self.memory.data["/run-model/evidence/controls-result.json"])
        self.assertFalse(result["controlsPassed"])
        self.assertEqual(result["retirement"], "KNOWN")
        self.assertEqual(self.memory.data["/run-model/evidence/original-executor/stdout.bin"], b"MODEL ORIGINAL SUITE OUTPUT")
        self.assertEqual(self.export.call_count, 1)
        self.assertIn("PRIVATE_DECRYPTION=NOT_RUN", self.stdout.getvalue())
        options = self.source_call.call_args_list[-1].kwargs
        self.assertEqual(set(options), {"finalizing", "observe"})
        self.assertIs(options["finalizing"], True)
        self.assertTrue(callable(options["observe"]))

    def test_final_source_failure_prevents_export_and_still_retires_main_and_suite(self):
        self.source_call.side_effect = [self.source, {"changed": True}]
        self.assertEqual(H.run(), 1)
        self.export.assert_not_called()
        self.assertEqual(len(self.finalizations), 2)
        self.assertNotIn("/run-model/return.json", self.memory.data)

    def test_exporter_attached_failure_is_retained_privately_and_not_printed(self):
        original = OSError("MODEL PRIVATE PATH NEVER PUBLIC")
        error = H.encrypted.WindowsEvidenceError(original, b'{"retirement":"KNOWN","originalBytes":"MODEL"}', False)
        self.export.side_effect = error
        self.assertEqual(H.run(), 1)
        failure = H.decode(self.memory.data["/run-model/not-accepted.json"])
        self.assertIn("MODEL", json.dumps(failure))
        self.assertNotIn("PRIVATE PATH", self.stderr.getvalue() + self.stdout.getvalue())

    def test_late_native_root_close_refuses_provisional_return_record(self):
        self.memory.errors["close:/export-model"] = OSError("MODEL late close")
        self.assertEqual(H.run(), 1)
        self.assertIn("/run-model/return.json", self.memory.data)
        self.assertTrue(H._HELD)
        self.assertNotIn("RETURNED_FOR_SEAL", self.stdout.getvalue())

    def test_unknown_case_close_blocks_encryption_and_preserves_failure(self):
        error = OSError("MODEL suite close"); error.__notes__ = ["Native handle retirement UNKNOWN: 9"]
        self.memory.errors["runner-close:/run-model/state/executor"] = error
        self.assertEqual(H.run(), 1)
        self.export.assert_not_called()
        self.assertIn("/run-model/not-accepted.json", self.memory.data)

    def test_admission_failure_skips_every_fixture_and_restores_handlers(self):
        self.set(H, "admitted_tools", side_effect=H.HelperError("GPG_NOT_INSTALLED_ON_PATH"))
        self.assertEqual(H.run(), 1)
        self.assertEqual(self.invocations, [])
        self.export.assert_not_called()
        self.assertTrue(any(call.args[-1] == "MODEL_ORIGINAL_HANDLER" for call in self.handlers.call_args_list))

    def test_first_stage_survives_export_guard_and_privately_retains_original_error(self):
        self.memory.errors["create:/run-model/started.json"] = OSError("MODEL_PRIVATE_SENTINEL")
        self.assertEqual(H.run(), 1)
        self.assertIn("stage=START_RECORD", self.stderr.getvalue())
        self.assertNotIn("MODEL_PRIVATE_SENTINEL", self.stderr.getvalue())
        self.assertNotIn("RECIPIENT_ADMISSION_INCOMPLETE", self.stderr.getvalue())
        private = H.decode(self.memory.data["/run-model/not-accepted.json"])
        self.assertEqual(private["failures"][0]["detail"]["nodes"][0]["message"], "MODEL_PRIVATE_SENTINEL")
        self.assertEqual(self.invocations, [])
        self.export.assert_not_called()

    def test_later_unknown_finalization_cannot_erase_the_first_stage_or_original(self):
        self.memory.errors["create:/run-model/started.json"] = OSError("MODEL_PRIVATE_SENTINEL")
        self.memory.errors["close:/export-model"] = OSError("MODEL later close")
        self.assertEqual(H.run(), 1)
        self.assertIn("stage=START_RECORD", self.stderr.getvalue())
        self.assertIn("retirementObservation=UNKNOWN", self.stderr.getvalue())
        self.assertNotIn("MODEL", self.stderr.getvalue())
        self.assertTrue(H._HELD)

    def test_recipient_failure_reports_only_existing_last_command_and_original_stage(self):
        record = {"operation": "recipient-validation", "retirement": "KNOWN", "commands": [
            {"argv": ["MODEL_PRIVATE_GPG_PATH", "--version"], "waitExitCode": 2}]}
        error = H.encrypted.WindowsEvidenceError(OSError("MODEL_PRIVATE_SENTINEL"), H.encoded(record), False)
        self.set(H.encrypted, "validate_recipient", side_effect=error)
        self.assertEqual(H.run(), 1)
        self.assertIn("stage=RECIPIENT", self.stderr.getvalue())
        self.assertIn("lastGpgCommand=VERSION", self.stderr.getvalue())
        self.assertIn("lastGpgExit=NONZERO", self.stderr.getvalue())
        self.assertNotIn("MODEL", self.stderr.getvalue())
        private = H.decode(self.memory.data["/run-model/not-accepted.json"])
        self.assertEqual(private["failures"][0]["detail"]["windowsEvidence"][0], record)
        self.assertEqual(self.invocations, [])
        self.export.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
