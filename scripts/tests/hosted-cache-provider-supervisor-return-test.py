#!/usr/bin/env python3
"""Offline outer-return controls: modeled native/service/pipe, tiny POSIX files.

No provider, native process, Node, credential, crypto or workflow executes.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("outer_return_fixtures",
    Path(__file__).with_name("hosted-cache-provider-supervisor-test.py"))
F = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = F
spec.loader.exec_module(F)
S, L, T = F.S, F.L, F.S.outer_return
clocks, files, caught, Failure = F.clocks, F.files, F.caught, F.Failure


class CodecControls(unittest.TestCase):
    """Explicit supplied records only, not original execution authority."""
    def setUp(self):
        self.context = {"schema": "P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1", "role": "windows-x64",
            "frequency": 10 ** 7, "firstNs": str(101 * clocks.NS), "issuedNs": str(100 * clocks.NS),
            "hardEndNs": str(280 * clocks.NS), "workerCutoffNs": str(250 * clocks.NS), "phase": "save",
            "job": "1" * 32, "outerId": "2" * 32, "innerId": "4" * 32,
            "directory": r"C:\model\state", "directoryIdentity": [1, "a" * 32],
            "home": r"C:\model\home", "homeIdentity": [1, "b" * 32],
            "node": r"C:\model\node.exe", "toolPath": r"C:\model", "plan": {"MODEL_NOT_ADMISSION": True}}
        self.request = L.transport._json(self.context)
        self.worker_request = L.transport._json({**self.context, "schema": 1})
        self.references = tuple(T.FileReference(3, hashlib.sha256(b"abc").hexdigest(), (1, str(n) * 32))
                                for n in range(1, 5))
        self.transcript = SimpleNamespace(failed=False, worker_exit_code=0, provider_return=SimpleNamespace(kind="success"),
            observed_ns=102 * clocks.NS, closed_resources=("scope", "retirement-writer", "packet-reader", "stderr", "stdout",
                "bundle", "capture_directory", "home", "directory"))
        self.raw = T.acknowledge(self.request, self.worker_request, self.transcript, self.references)

    def changed(self, **changes):
        return L.transport._json({**json.loads(self.raw), **changes}) + b"\n"

    def refuses(self, raw, code=0, request=None):
        with self.assertRaises(L.transport.ProviderReturnError):
            T.read_ack(raw, self.request if request is None else request, code)

    def test_distinct_invocation_and_worker_hashes_do_not_establish_authority(self):
        ack = T.read_ack(self.raw, self.request, 0)
        self.assertNotEqual(ack.invocation_sha256, ack.worker_request_sha256)
        self.assertEqual(ack.invocation_sha256, hashlib.sha256(self.request).hexdigest())
        self.assertEqual((ack.enclosing_node_return, ack.original_runner_outcome, ack.provider_acceptance),
                         ("NOT_OBSERVED", "NOT_OBSERVED", "NOT_ESTABLISHED"))
        with self.assertRaises(FrozenInstanceError):
            ack.kind = "failed"

    def test_missing_duplicate_truncated_noncanonical_and_oversized_ack_refuse(self):
        for raw in (b"", self.raw + self.raw, self.raw[:-1], self.raw + b" ", b"x" * (T.ACK_BYTES + 1),
                    self.raw.replace(b'{', b'{"kind":"success",', 1)):
            with self.subTest(size=len(raw)):
                self.refuses(raw)

    def test_exact_invocation_and_pending_scope_cannot_change(self):
        for change in ({"invocationSha256": "f" * 64}, {"originalRunnerOutcome": "success"},
                       {"providerAcceptance": "ACCEPTED"}, {"extra": True}):
            self.refuses(self.changed(**change))
        self.refuses(self.raw, request=L.transport._json({**self.context, "outerId": "3" * 32}))

    def test_success_requires_matching_nonboolean_exit_and_worker_result(self):
        for code in (None, True, 65, 66, -9, "0"):
            self.refuses(self.raw, code)
        for change in ({"workerExitCode": True}, {"workerExitCode": 65}, {"providerKind": None},
                       {"providerKind": "failed"}, {"kind": "unknown"}):
            self.refuses(self.changed(**change))

    def test_failed_opaque_record_is_not_success_and_needs_no_packet_reference(self):
        self.transcript.failed, self.transcript.worker_exit_code, self.transcript.provider_return = True, 29, None
        self.transcript.closed_resources = tuple(name for name in self.transcript.closed_resources if name != "packet-reader")
        raw = T.acknowledge(self.request, self.worker_request, self.transcript, (*self.references[:3], None))
        ack = T.read_ack(raw, self.request, 65)
        self.assertEqual((ack.kind, ack.provider_kind, dict(ack.files)["packet"]), ("failed", None, None))
        self.refuses(raw, 0)

    def test_file_caps_hashes_identities_and_fixed_slots_refuse_substitution(self):
        original = json.loads(self.raw)["files"]
        for name, bound in T._LIMITS.items():
            for change in ({"bytes": bound + 1}, {"bytes": True}, {"sha256": "bad"}, {"identity": [True, "1" * 32]}):
                self.refuses(self.changed(files={**original, name: {**original[name], **change}}))
        self.refuses(self.changed(files={**original, "path": "/arbitrary"}))
        self.refuses(self.changed(files={**original, "stderr": original["stdout"]}))
        self.refuses(self.changed(files={**original, "native": None}))
        self.refuses(self.changed(files={**original, "packet": None}))

    def test_close_order_and_original_time_window_are_not_claimed_from_a_preclose_ack(self):
        for closes in ([], list(self.transcript.closed_resources[:-1]), list(reversed(self.transcript.closed_resources)),
                       [*self.transcript.closed_resources, "directory"]):
            self.refuses(self.changed(closedResources=closes))
        for value in ("0", str(280 * clocks.NS), 102 * clocks.NS, True):
            self.refuses(self.changed(observedNs=value))

    def test_posix_file_identity_grammar_is_separate_from_windows(self):
        request = L.transport._json({**self.context, "role": "linux-x64", "frequency": clocks.NS,
                                    "directoryIdentity": [1, 1], "homeIdentity": [1, 2]})
        refs = tuple(replace(value, identity=(1, index + 3)) for index, value in enumerate(self.references))
        self.transcript.closed_resources = ("scope", "retirement-writer", "stdout-reader", "stderr-reader",
                                            *self.transcript.closed_resources[2:])
        worker_request = L.transport._json({**json.loads(request), "schema": 1})
        raw = T.acknowledge(request, worker_request, self.transcript, refs)
        self.assertEqual(dict(T.read_ack(raw, request, 0).files)["native"].identity, (1, 3))


class ModelPipe:
    def __init__(self):
        self.writes, self.events = [], []
        self.on_write = self.on_flush = lambda: None
        self.descriptor = 1

    def fileno(self):
        return self.descriptor

    def write(self, raw):
        self.writes.append(raw)
        self.events.append("write")
        self.on_write()
        return len(raw)

    def flush(self):
        self.events.append("flush")
        self.on_flush()


class SendModels(unittest.TestCase):
    def setUp(self):
        self.base = F.SupervisorModels()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.owner, self.model = self.base.owner, self.base.model
        self.sink = ModelPipe()
        self.stdout = SimpleNamespace(buffer=self.sink)
        binding = patch.object(S, "sys", SimpleNamespace(stdout=self.stdout))
        binding.start()
        self.addCleanup(binding.stop)

    def tearDown(self):
        self.base.tearDown()

    def send(self):
        self.owner.take_directories(self.base.fixture.root, self.base.fixture.home)
        return self.owner.run_and_send(clocks.Reading(self.model.clock, self.model.raw), **self.base.values())

    def entry(self):
        # Explicit surrounding-entry model, not a native process exit or Node.
        result = error = None
        try:
            result = self.send()
        except BaseException as original:
            error = original
        try:
            code = self.owner.exit_code(result, error)
        except BaseException:
            code = T.INCOMPLETE_EXIT
        return code, result, error

    def incomplete(self, *, pinned=False):
        code, result, error = self.entry()
        self.assertEqual(code, 66)
        self.assertIsNone(result)
        self.assertIsNotNone(error)
        self.assertIsNone(self.owner._send_receipt)
        if pinned:
            self.base.pinned()
        return error

    def native_writer(self, owner):
        return PureWindowsPath(owner.path).name == T.NATIVE_NAME

    def test_actual_outer_call_persists_before_roots_close_and_only_then_writes_ack(self):
        def verify_closed():
            self.assertTrue(self.base.fixture.root._closed)
            self.assertTrue(self.owner._retirement_writer.closed)
            self.assertTrue(self.owner._finished)
            self.assertIsNotNone(self.owner._completion)
        self.sink.on_write = verify_closed
        code, result, error = self.entry()
        self.assertEqual((code, error), (0, None))
        self.assertEqual(self.sink.events, ["write", "flush"])
        self.assertEqual(result.closed_resources[:2], ("scope", "retirement-writer"))
        raw = self.model.api.nodes[str(self.owner._retirement_writer.path)].content
        self.assertEqual(raw, result.native_retirement)
        native_request = json.loads(raw)["launches"][0]["requestedArgv"][-1].encode("ascii")
        self.assertEqual(native_request, result.request)
        ack = T.read_ack(self.sink.writes[0], self.owner._invocation.request, code)
        self.assertEqual(ack.worker_request_sha256, hashlib.sha256(result.request).hexdigest())
        self.assertEqual(dict(ack.files)["native"].sha256, hashlib.sha256(raw).hexdigest())
        self.assertLessEqual(len(self.sink.writes[0]), 4096)
        self.assertEqual(ack.provider_acceptance, "NOT_ESTABLISHED")

    def test_known_failed_worker_gets_opaque_failed_ack_but_keeps_first_exception(self):
        self.base.fixture.worker_code = 29
        code, result, error = self.entry()
        self.assertEqual((code, result), (65, None))
        self.assertIs(error, self.owner._completion.error)
        ack = T.read_ack(self.sink.writes[0], self.owner._invocation.request, code)
        self.assertEqual((ack.kind, ack.worker_exit_code, ack.provider_kind), ("failed", 29, None))
        self.model.never_classifier.assert_not_called()

    def test_bad_inner_ack_can_have_closed_opaque_failure_not_success(self):
        self.base.model_stdout = b"MODEL_NOT_AN_ACK"
        code, result, error = self.entry()
        self.assertEqual((code, result), (65, None))
        self.assertIs(error, self.owner._completion.error)
        self.assertIsNone(dict(T.read_ack(self.sink.writes[0], self.owner._invocation.request, 65).files)["packet"])

    def test_lost_native_writer_acquisition_is_unknown_and_never_acknowledged(self):
        original, lost = self.base.fixture.root.create_file, []
        failure = Failure("MODEL_LOST_NATIVE_WRITER")
        def create(name, **values):
            writer = original(name, **values)
            if name == T.NATIVE_NAME:
                lost.append(writer)
                self.base.fixture.extra.append(writer)
                raise failure
            return writer
        with patch.object(self.base.fixture.root, "create_file", create):
            self.assertIs(self.incomplete(pinned=True), failure)
        self.assertEqual(len(lost), 1)
        self.assertIsNone(self.owner._retirement_writer)
        self.assertEqual(self.sink.writes, [])

    def test_short_native_write_keeps_distinct_owners_pinned(self):
        original = files.NativeFile.write
        def write(writer, raw):
            result = original(writer, raw)
            return result - 1 if self.native_writer(writer) else result
        with patch.object(files.NativeFile, "write", write):
            self.assertRegex(str(self.incomplete(pinned=True)), "RETIREMENT_WRITE")

    def test_native_sync_failure_is_unknown(self):
        original, failure = files.NativeFile.sync, Failure("MODEL_NATIVE_SYNC")
        def sync(writer):
            if self.native_writer(writer):
                raise failure
            return original(writer)
        with patch.object(files.NativeFile, "sync", sync):
            self.assertIs(self.incomplete(pinned=True), failure)

    def test_native_identity_change_after_write_is_unknown(self):
        original = files.NativeFile.sync
        def sync(writer):
            original(writer)
            if self.native_writer(writer):
                self.model.api.nodes[str(writer.path)].identifier += 100
        with patch.object(files.NativeFile, "sync", sync):
            self.incomplete(pinned=True)

    def test_native_close_unknown_is_not_retried_or_allowed_to_release_roots(self):
        original, failure, attempts = files.NativeFile.close, Failure("MODEL_NATIVE_CLOSE"), []
        def close(writer):
            if self.native_writer(writer):
                attempts.append(writer)
                original(writer)
                raise failure
            original(writer)
        with patch.object(files.NativeFile, "close", close):
            self.assertIs(self.incomplete(pinned=True), failure)
        self.assertEqual(attempts, [self.owner._retirement_writer])

    def test_expiry_after_native_sync_cannot_release_roots_or_emit_ack(self):
        original = files.NativeFile.sync
        def sync(writer):
            original(writer)
            if self.native_writer(writer):
                self.model.raw = 280 * clocks.NS
        with patch.object(files.NativeFile, "sync", sync):
            self.incomplete(pinned=True)

    def test_native_writer_replacement_during_later_read_refuses_completion(self):
        original = files.NativeFile.read_provider_log
        def read(writer):
            raw = original(writer)
            self.owner._retirement_writer = SimpleNamespace(close=Mock())
            return raw
        with patch.object(files.NativeFile, "read_provider_log", read):
            self.incomplete(pinned=True)

    def test_last_root_close_expiry_cannot_emit_a_preclose_success(self):
        original = files.PrivateDirectory.close
        def close(owner):
            original(owner)
            if owner is self.base.fixture.root:
                self.model.raw = 280 * clocks.NS
        with patch.object(files.PrivateDirectory, "close", close):
            self.incomplete()
        self.assertEqual(self.sink.writes, [])

    def test_requested_argv_replacement_refuses_before_native_file_publication(self):
        self.base.on_wait = lambda: self.base.fixture.outer.launches[0]["requestedArgv"].__setitem__(-1, "{}")
        self.incomplete(pinned=True)
        self.assertIsNone(self.owner._retirement_writer)

    def test_resolved_argv_replacement_is_not_an_alternative_request_source(self):
        self.base.on_wait = lambda: self.base.fixture.outer.launches[0]["resolvedArgv"].__setitem__(-1, "{}")
        self.incomplete(pinned=True)

    def test_joint_resolved_executable_and_windows_framing_change_refuses_before_persistence(self):
        def mutate():
            record = self.base.fixture.outer.launches[0]
            record["resolvedArgv"][0] = record["applicationName"] = r"C:\unrelated\python.exe"
            record["commandLine"] = L.subprocess.list2cmdline(record["resolvedArgv"])
        self.base.on_wait = mutate
        self.assertRegex(str(self.incomplete(pinned=True)), "SUPERVISOR_NATIVE_RESOLVED_ARGV")
        self.assertIsNone(self.owner._retirement_writer)
        self.assertEqual(self.sink.writes, [])

    def test_jointly_changed_launch_description_and_diagnostic_vector_cannot_replace_original(self):
        def mutate():
            record = self.base.fixture.outer.launches[0]
            record["requestedArgv"][-1] = record["resolvedArgv"][-1] = "{}"
            record["commandLine"] = L.subprocess.list2cmdline(record["resolvedArgv"])
            self.owner.launch.worker_argv[-1] = "{}"
        self.base.on_wait = mutate
        self.incomplete(pinned=True)

    def test_wrong_launch_pid_or_unresumed_windows_process_cannot_be_a_completed_return(self):
        self.base.on_wait = lambda: self.base.fixture.outer.launches[0].update(pid=999, resumed=False)
        self.incomplete(pinned=True)

    def test_joint_child_pid_and_description_change_cannot_replace_original_spawn(self):
        def mutate():
            self.owner.launch.child.pid = 999
            self.base.fixture.outer.launches[0]["pid"] = 999
        self.base.on_wait = mutate
        self.incomplete(pinned=True)

    def test_changed_outer_invocation_cannot_be_selected_from_the_later_receipt(self):
        self.base.on_wait = lambda: setattr(self.owner, "_invocation", S._Invocation(b"{}"))
        self.incomplete(pinned=True)

    def test_boolean_stdout_descriptor_refuses_before_launch(self):
        self.sink.descriptor = True
        self.incomplete()
        self.base.fixture.scope_factory.assert_not_called()

    def test_partial_ack_write_is_not_a_completed_send(self):
        with patch.object(self.sink, "write", return_value=1):
            self.incomplete()
        self.assertEqual(self.sink.events, [])

    def test_boolean_ack_count_is_not_a_completed_send(self):
        with patch.object(self.sink, "write", return_value=True):
            self.incomplete()

    def test_broken_pipe_is_not_a_completed_send(self):
        with patch.object(self.sink, "write", side_effect=BrokenPipeError("MODEL_PIPE")):
            self.incomplete()

    def test_flush_failure_does_not_gain_success_from_already_written_ack(self):
        with patch.object(self.sink, "flush", side_effect=Failure("MODEL_FLUSH")):
            self.incomplete()
        self.assertEqual(len(self.sink.writes), 1)

    def test_buffer_replacement_during_write_does_not_flush_a_substitute(self):
        substitute = ModelPipe()
        self.sink.on_write = lambda: setattr(self.stdout, "buffer", substitute)
        self.incomplete()
        self.assertEqual(substitute.events, [])

    def test_expiry_after_ack_flush_is_not_a_completed_send(self):
        self.sink.on_flush = lambda: setattr(self.model, "raw", 280 * clocks.NS)
        self.incomplete()
        self.assertEqual(self.sink.events, ["write", "flush"])

    def test_late_completion_constructor_cannot_publish_a_return(self):
        original = S._Completion
        def late(*args):
            value = original(*args)
            self.model.raw = 280 * clocks.NS
            return value
        with patch.object(S, "_Completion", side_effect=late):
            self.incomplete()
        self.assertEqual(self.sink.writes, [])

    def test_substituted_actual_run_return_is_not_the_original_completion(self):
        original = self.owner.run
        with patch.object(self.owner, "run", side_effect=lambda *args, **values: replace(original(*args, **values))):
            self.incomplete()
        self.assertEqual(self.sink.writes, [])

    def test_replaced_completion_references_cannot_be_selected_after_run_returns(self):
        original = self.owner.run
        def run(*args, **values):
            result = original(*args, **values)
            old = self.owner._completion
            self.owner._completion = replace(old, references=(replace(old.references[0], sha256="f" * 64), *old.references[1:]))
            return result
        with patch.object(self.owner, "run", run):
            self.incomplete()
        self.assertEqual(self.sink.writes, [])

    def test_late_send_receipt_construction_is_not_published(self):
        original = S._Send
        def late(*args):
            value = original(*args)
            self.model.raw = 280 * clocks.NS
            return value
        with patch.object(S, "_Send", side_effect=late):
            self.incomplete()
        self.assertEqual(self.sink.events, ["write", "flush"])

    def test_swallowed_reentry_after_write_is_sticky(self):
        nested = []
        self.sink.on_write = lambda: nested.append(caught(lambda: self.owner.run_and_send(
            clocks.Reading(self.model.clock, self.model.raw), **self.base.values())))
        self.assertIs(self.incomplete(), nested[0])
        self.base.fixture.outer.spawn.assert_called_once()

    def test_failed_capture_keeps_first_error_when_later_ack_flush_fails(self):
        self.base.fixture.worker_code = 29
        with patch.object(self.sink, "flush", side_effect=Failure("MODEL_SECONDARY")):
            error = self.incomplete()
        self.assertIs(error, self.owner._completion.error)

    def test_replaced_error_slot_cannot_replace_the_actual_original_run_exception(self):
        self.base.fixture.worker_code = 29
        self.sink.on_flush = lambda: setattr(self.owner, "_primary", Failure("MODEL_REPLACEMENT_ERROR"))
        error = self.incomplete()
        self.assertIs(error, self.owner._completion.error)

    def test_expired_exit_classification_cannot_be_retried_after_clock_restore(self):
        result = self.send()
        self.model.raw = 280 * clocks.NS
        first = caught(lambda: self.owner.exit_code(result, None))
        self.model.raw = 100 * clocks.NS
        self.assertIs(caught(lambda: self.owner.exit_code(result, None)), first)
        self.assertEqual(len(self.sink.writes), 1)

    def test_no_send_or_supplied_result_cannot_mint_reserved_exit(self):
        result = self.base.run_owner()
        self.assertIsNotNone(caught(lambda: self.owner.exit_code(result, None)))
        self.assertEqual(self.sink.writes, [])


class PosixFileControls(unittest.TestCase):
    """Real tiny original file only; upstream/native/clock remain explicit models."""
    def setUp(self):
        self.base = F.PosixTranscriptModels()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)

    def tearDown(self):
        self.base.tearDown()

    def test_retirement_bytes_and_reference_survive_actual_writer_close(self):
        result = self.base.run_owner()
        writer = self.base.owner._retirement_writer
        self.assertTrue(writer.closed)
        raw = writer.path.read_bytes()  # Test inspection only, not a production late reopen.
        self.assertEqual(raw, result.native_retirement)
        ref = self.base.owner._completion.references[0]
        self.assertEqual((ref.size, ref.sha256), (len(raw), hashlib.sha256(raw).hexdigest()))
        self.assertEqual(writer.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(raw)["launches"][0]["requestedArgv"][-1].encode("ascii"), result.request)

    def test_existing_fixed_native_file_is_not_replaced_or_used_as_a_fallback(self):
        path = self.base.model.root.path / T.NATIVE_NAME
        path.write_bytes(b"MODEL_KEEP_EXISTING")
        self.assertIsNotNone(caught(self.base.run_owner))
        self.assertEqual(path.read_bytes(), b"MODEL_KEEP_EXISTING")
        self.assertTrue(self.base.owner.unknown)
        self.assertFalse(self.base.model.root.closed)
        self.assertIsNone(self.base.owner._completion)

    def test_joint_resolved_executable_and_posix_framing_change_refuses_before_persistence(self):
        original = self.base.start
        def start(*args, **values):
            returned = original(*args, **values)
            record = self.base.model.scope.launches[0]
            record["resolvedArgv"][0] = record["executable"] = "/unrelated/python3"
            return returned
        self.base.model_launch.side_effect = start
        self.assertRegex(str(caught(self.base.run_owner)), "SUPERVISOR_NATIVE_RESOLVED_ARGV")
        self.assertTrue(self.base.owner.unknown)
        self.assertFalse(self.base.model.root.closed)
        self.assertIsNone(self.base.owner._completion)
        self.assertIsNone(self.base.owner._retirement_writer)
        self.assertFalse((self.base.model.root.path / T.NATIVE_NAME).exists())


if __name__ == "__main__":
    unittest.main()
