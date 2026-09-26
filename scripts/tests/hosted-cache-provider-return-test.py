#!/usr/bin/env python3
"""Private transport controls: supplied bytes, Windows models and tiny POSIX files.

No provider, Node, native process, credential, cryptography or workflow executes.
Fixtures from earlier suites are borrowed, not their TestCase methods replayed.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import FrozenInstanceError, replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("return_supervisor_fixtures",
    Path(__file__).with_name("hosted-cache-provider-supervisor-test.py"))
F = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = F
spec.loader.exec_module(F)
L, T, W = F.L, F.L.transport, F.F.W
clocks, files, caught = L.clocks, L.files.windows_files, F.caught


def request(role="linux-x64", phase="save"):
    return T._json({"role": role, "phase": phase, "job": "1" * 32, "outerId": "2" * 32, "innerId": "4" * 32,
                    "issuedNs": str(100 * clocks.NS), "workerCutoffNs": str(250 * clocks.NS)})


def capture(role="linux-x64", *, failed=False, phase="save", **changes):
    names = L.lifecycle.ProviderCapture._NAMES
    fields = dict(phase=phase, exit_code=19 if failed else 0, command=b"", stdout=b"MODEL_PRIVATE\x00\xff",
        stderr=b"MODEL_ERROR\r\n", native_retirement=b'{"model":"NOT_NATIVE_EVIDENCE"}\n',
        observed_ns=100 * clocks.NS, closed_resources=names[:-2] if role == "windows-x64" else names)
    if not failed:
        fields["outputs"] = ()
    fields.update(changes)
    return (L.lifecycle.FailedProviderCapture if failed else L.lifecycle.CapturedProvider)(**fields)


class CodecControls(unittest.TestCase):
    def encoded(self, value, req=None):
        req = request() if req is None else req
        raw = T._json(value) + b"\n" if type(value) is dict else T.encode(value, req)
        role = json.loads(req)["role"]
        identity = (1, "e" * 32) if role == "windows-x64" else (1, 17)
        ack = T.read_ack(T.acknowledge(raw, identity, req), req)
        return raw, ack, req

    def test_four_roles_roundtrip_to_distinct_immutable_nonacceptance_type(self):
        for role in ("linux-x64", "windows-x64", "macos-arm64", "macos-x64"):
            with self.subTest(role=role):
                source = capture(role)
                raw, ack, req = self.encoded(source, request(role))
                result = T.decode(raw, ack, req, 0)
                self.assertIs(type(result), T.TransportedProvider)
                self.assertNotIsInstance(result, L.lifecycle.CapturedProvider)
                self.assertEqual((result.command, result.stdout, result.stderr, result.native_retirement),
                    (source.command, source.stdout, source.stderr, source.native_retirement))
                self.assertEqual((result.provider_acceptance, result.original_step_outcome), ("NOT_ESTABLISHED", "NOT_OBSERVED"))
                self.assertNotIn("MODEL_PRIVATE", repr(result))
                with self.assertRaises(FrozenInstanceError):
                    result.kind = "success"

    def test_maximum_four_raw_fields_fit_without_widening_existing_codecs(self):
        source = capture(failed=True, phase="lookup", command=b"\x00" * 4096, stdout=b"x" * (1024 * 1024),
            stderr=b"y" * (1024 * 1024), native_retirement=b"\xff" * (2 * 1024 * 1024))
        raw, ack, req = self.encoded(source, request(phase="lookup"))
        self.assertLess(len(raw), 6 * 1024 * 1024)
        self.assertEqual(sum(len(json.loads(raw)[name]) for name in T._LIMITS), 5597876)
        with patch.object(L.cache, "provider_command_outputs", side_effect=AssertionError("FAILED_BYTES_MUST_NOT_PARSE")):
            result = T.decode(raw, ack, req, T.FAILED_CAPTURE_EXIT)
        self.assertEqual(result.command, source.command)
        self.assertEqual(len(result.native_retirement), 2 * 1024 * 1024)
        self.assertEqual((L.files.MAX_RECEIPT_BYTES, L.lifecycle.LOG_BYTES), (2 * 1024 * 1024, 1024 * 1024))

    def test_each_sender_field_limit_and_nonbyte_type_refuse(self):
        for name, maximum in T._LIMITS.items():
            field = "native_retirement" if name == "nativeRetirement" else name
            for raw in (b"x" * (maximum + 1), "not bytes"):
                with self.subTest(field=field, kind=type(raw).__name__), self.assertRaises(T.ProviderReturnError):
                    T.encode(capture(failed=True, **{field: raw}), request())

    def test_duplicate_noncanonical_extra_and_partial_ack_refuse(self):
        raw, ack, req = self.encoded(capture())
        original = T.acknowledge(raw, ack.packet_identity, req)
        malformed = [b"", original[:-1], original + original, b" " + original,
            original.replace(b'{', b'{"schema":"P2PKIT_PROVIDER_RETURN_ACK_V1",', 1),
            original[:-2] + b',"unexpected":true}\n']
        for changed in malformed:
            with self.subTest(size=len(changed)), self.assertRaises(T.ProviderReturnError):
                T.read_ack(changed, req)

    def test_packet_schema_duplicate_key_and_json_canonicality_refuse(self):
        raw, ack, req = self.encoded(capture())
        malformed = [raw.replace(b'{', b'{"kind":"success",', 1), b" " + raw,
                     raw[:-2] + b',"extra":true}\n', b"[1,2,3]\n"]
        for changed in malformed:
            selected = T.read_ack(T.acknowledge(changed, ack.packet_identity, req), req)
            with self.subTest(size=len(changed)), self.assertRaises(T.ProviderReturnError):
                T.decode(changed, selected, req, 0)

    def test_noncanonical_base64_decoded_overflow_and_failed_outputs_refuse(self):
        raw, _, req = self.encoded(capture(failed=True))
        source = json.loads(raw)
        variants = [("stdout", "Zh=="), ("stdout", "Zg==\n"), ("command", base64.b64encode(b"x" * 4097).decode()),
                    ("nativeRetirement", ""), ("outputs", [["cache-hit", "true"]])]
        for name, replacement in variants:
            with self.subTest(name=name, length=len(replacement)):
                packet, ack, _ = self.encoded({**source, name: replacement}, req)
                with self.assertRaises(T.ProviderReturnError):
                    T.decode(packet, ack, req, T.FAILED_CAPTURE_EXIT)

    def test_exact_request_hash_and_packet_bytes_are_bound(self):
        raw, ack, req = self.encoded(capture())
        for changed_raw, changed_req in ((raw + b"\n", req), (raw[:-2] + b" \n", req), (raw, request(phase="lookup"))):
            with self.subTest(raw=len(changed_raw), request=changed_req == req), self.assertRaises(T.ProviderReturnError):
                T.decode(changed_raw, ack, changed_req, 0)

    def test_actual_worker_exit_must_match_capture_kind_without_bool_alias(self):
        for failed, invalid in ((False, [True, None, 1, 65, 66]), (True, [True, None, 0, 1, 66])):
            raw, ack, req = self.encoded(capture(failed=failed))
            for code in invalid:
                with self.subTest(failed=failed, code=code), self.assertRaisesRegex(T.ProviderReturnError, "WORKER_OUTCOME"):
                    T.decode(raw, ack, req, code)

    def test_scope_close_time_and_identity_fields_refuse(self):
        raw, _, req = self.encoded(capture())
        source = json.loads(raw)
        for name, value in (("closedResources", []), ("observedNs", str(250 * clocks.NS)), ("observedNs", True),
                            ("exitCode", False), ("kind", "approved"), ("providerAcceptance", "PASS"),
                            ("outerId", "9" * 32), ("outputs", [["cache-hit", "true"]])):
            packet, ack, _ = self.encoded({**source, name: value}, req)
            with self.subTest(name=name), self.assertRaises(T.ProviderReturnError):
                T.decode(packet, ack, req, 0)

    def test_ack_size_identity_and_private_repr_do_not_coerce_types(self):
        raw, ack, req = self.encoded(capture())
        source = json.loads(T.acknowledge(raw, ack.packet_identity, req))
        for name, value in (("packetBytes", True), ("packetBytes", T.PACKET_BYTES + 1), ("packetIdentity", [1, "17"]),
                            ("packetIdentity", [True, 17]), ("packetIdentity", [1, 0])):
            with self.subTest(name=name), self.assertRaises(T.ProviderReturnError):
                T.read_ack(T._json({**source, name: value}) + b"\n", req)


class WorkerTransportModels(unittest.TestCase):
    def setUp(self):
        self.fixture = F.F.LaunchSites()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.parent = self.fixture.parent()

    def tearDown(self):
        self.fixture.tearDown()

    def run_worker(self):
        return self.fixture.worker(self.parent)

    def main_worker(self, *, code=0):
        self.fixture.provider_code = code
        frame = copy.deepcopy(self.parent.frame)
        worker = L._CaptureWorker(frame, L._json(frame).encode("ascii"))
        self.fixture.workers.append(worker)
        with patch.dict(os.environ, self.parent.worker_environment, clear=True), patch.object(W, "bootstrap", return_value=worker):
            result = W.main()
        return result, worker

    def read_packet(self):
        with self.fixture.root.open_file(T.PACKET_NAME, max_bytes=T.PACKET_BYTES, deadline=280.0) as stream:
            return stream.read()

    def test_original_success_packet_and_ack_follow_all_original_worker_closes(self):
        original = self.fixture.acks.append
        def acknowledged(raw):
            worker = self.fixture.workers[-1]
            self.assertEqual(worker.closed, ["packet", "bundle", "home", "directory"])
            self.assertTrue(worker.packet.closed)
            self.assertTrue(worker.directory._closed)
            self.assertIs(worker.capture_return, worker.capture.result)
            original(raw)
        with patch.object(L, "_write_ack", acknowledged):
            code, worker = self.main_worker()
        self.assertEqual(code, 0)
        raw = self.read_packet()
        ack = T.read_ack(self.fixture.acks[0], worker.request)
        result = T.decode(raw, ack, worker.request, code)
        self.assertEqual(result.stdout, worker.capture_return.stdout)
        self.assertEqual(result.closed_resources, worker.capture_return.closed_resources)
        self.assertEqual(len(self.fixture.acks), 1)

    def test_genuine_failed_capture_is_transported_with_original_failure_and_nonzero_exit(self):
        with patch.object(L.cache, "provider_command_outputs", side_effect=AssertionError("FAILED_BYTES_MUST_NOT_PARSE")):
            code, worker = self.main_worker(code=19)
            self.assertEqual(code, T.FAILED_CAPTURE_EXIT)
            self.assertIs(worker.capture_return, worker.capture.failure_capture)
            self.assertIs(worker.original_error, worker.capture._primary)
            result = T.decode(self.read_packet(), T.read_ack(self.fixture.acks[0], worker.request), worker.request, code)
        self.assertEqual((result.kind, result.exit_code, result.outputs), ("failed", 19, None))
        self.assertEqual(result.stdout, b"MODEL_PRIVATE_STDOUT")

    def test_complete_ack_followed_by_cutoff_failure_has_no_completed_exit(self):
        def late(raw):
            self.fixture.acks.append(raw)
            self.fixture.model.raw = 250 * clocks.NS
        with patch.object(L, "_write_ack", late):
            code, worker = self.main_worker()
        self.assertEqual(code, T.INCOMPLETE_EXIT)
        self.assertEqual(len(self.fixture.acks), 1)
        self.assertIsNone(worker._send_receipt)

    def test_complete_ack_then_system_exit65_does_not_impersonate_known_failure(self):
        def failed_write(raw):
            self.fixture.acks.append(raw)
            raise SystemExit(65)
        with patch.object(L, "_write_ack", failed_write):
            code, worker = self.main_worker(code=19)
        self.assertEqual(code, T.INCOMPLETE_EXIT)
        self.assertIs(worker.original_error, worker.capture._primary)
        self.assertIsNone(worker._send_receipt)

    def test_stale_failed_receipt_plus_secondary_failure_refuses_reserved_exit(self):
        self.fixture.provider_code = 19
        caught(self.run_worker)
        worker = self.fixture.workers[-1]
        original, receipt = worker.original_error, worker._send_receipt
        worker._failed("model-secondary", F.Failure("MODEL_SECONDARY"))
        self.assertIs(worker.original_error, original)
        self.assertIs(worker._send_receipt, receipt)
        self.assertIs(caught(lambda: worker.exit_code(None, original)), original)
        self.assertRegex(str(worker._errors[-1][1]), "BOUNDARY_CHANGED")

    def test_failed_final_exit_check_cannot_be_retried_as_success(self):
        worker = self.run_worker()
        failure = F.Cancel("MODEL_FINAL_EXIT_OBSERVATION_FAILED")
        def once():
            self.fixture.model.on_raw = None
            raise failure
        self.fixture.model.on_raw = once
        self.assertIs(caught(lambda: worker.exit_code(worker.capture_return, None)), failure)
        self.assertIs(caught(lambda: worker.exit_code(worker.capture_return, None)), failure)

    def test_unreturned_packet_acquisition_retains_owners_and_never_acks(self):
        original = files.PrivateDirectory.create_file
        failure = F.Cancel("MODEL_ACQUISITION_RETURN_LOST")
        def create(owner, name, **kwargs):
            result = original(owner, name, **kwargs)
            if name == T.PACKET_NAME:
                self.fixture.extra.append(result)
                raise failure
            return result
        with patch.object(files.PrivateDirectory, "create_file", create):
            self.assertIs(caught(self.run_worker), failure)
        worker = self.fixture.workers[-1]
        self.assertIsNone(worker.packet)
        self.assertFalse(worker.directory._closed)
        self.assertEqual((worker.closed, self.fixture.acks), ([], []))

    def test_short_packet_write_never_closes_distinct_roots_or_acks(self):
        original = files.NativeFile.write
        def write(owner, raw):
            count = original(owner, raw)
            return count - 1 if PureWindowsPath(owner.path).name == T.PACKET_NAME else count
        with patch.object(files.NativeFile, "write", write):
            self.assertRegex(str(caught(self.run_worker)), "PACKET_WRITE")
        worker = self.fixture.workers[-1]
        self.assertFalse(worker.packet.closed)
        self.assertFalse(worker.directory._closed)
        self.assertEqual(self.fixture.acks, [])

    def test_packet_close_failure_is_once_only_and_preserves_first_capture_error(self):
        original, calls = files.NativeFile.close, []
        self.fixture.provider_code = 19
        def close(owner):
            if PureWindowsPath(owner.path).name == T.PACKET_NAME:
                calls.append(owner)
                original(owner)
                raise F.Cancel("MODEL_PACKET_CLOSE_UNKNOWN")
            return original(owner)
        with patch.object(files.NativeFile, "close", close):
            error = caught(self.run_worker)
        worker = self.fixture.workers[-1]
        self.assertIs(error, worker.capture._primary)
        self.assertEqual(calls, [worker.packet])
        self.assertEqual((worker.closed, self.fixture.acks), ([], []))
        self.assertFalse(worker.directory._closed)

    def test_replaced_equal_capture_return_after_clock_callback_refuses(self):
        replacements = []
        def change():
            if self.fixture.workers and self.fixture.workers[-1].capture_return is not None and not replacements:
                worker = self.fixture.workers[-1]
                replacements.append(worker.capture_return)
                worker.capture_return = replace(worker.capture_return)
        self.fixture.model.on_raw = change
        self.assertRegex(str(caught(self.run_worker)), "BOUNDARY_CHANGED")
        self.assertEqual(len(replacements), 1)
        self.assertEqual(self.fixture.acks, [])
        self.assertIsNone(self.fixture.workers[-1].packet)

    def test_request_mismatch_refuses_before_any_worker_clock_or_acquisition(self):
        frame = copy.deepcopy(self.parent.frame)
        worker = L._CaptureWorker(frame, L._json(frame).encode("ascii") + b" ")
        with patch.dict(os.environ, self.parent.worker_environment, clear=True):
            self.assertRegex(str(caught(worker.run)), "REQUEST_CHANGED")
        self.assertIsNone(worker.window)
        self.fixture.inner.spawn.assert_not_called()

    def test_preconstruction_system_exit_and_normal_return_without_receipt_are_incomplete(self):
        with patch.object(W, "bootstrap", side_effect=SystemExit(65)):
            self.assertEqual(W.main(), 66)
        worker = L._CaptureWorker({}, b"{}")
        with patch.object(W, "bootstrap", return_value=worker), patch.object(worker, "run", return_value=None):
            self.assertEqual(W.main(), 66)
        with patch.object(W, "bootstrap", return_value=worker), patch.object(worker, "run", side_effect=SystemExit(0)):
            self.assertEqual(W.main(), 66)


class SupervisorTransportModels(unittest.TestCase):
    def setUp(self):
        self.fixture = F.SupervisorModels()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.owner, self.model = self.fixture.owner, self.fixture.model

    def tearDown(self):
        self.fixture.tearDown()

    def packet_node(self):
        return self.model.api.nodes[str(PureWindowsPath(self.fixture.fixture.root.path) / T.PACKET_NAME)]

    def test_failed_original_inner_worker_returns_bytes_but_outer_execution_still_fails(self):
        base, workers = self.fixture, []
        base.packet_from_worker = True
        base.fixture.provider_code, base.fixture.worker_code = 19, 65
        def run_worker():
            if not workers:
                with patch.object(L, "_write_ack", lambda raw: self.model.api.write(self.owner.launch.stdout.native_handle, raw)):
                    error = caught(lambda: base.fixture.worker(self.owner.launch))
                worker = base.fixture.workers[-1]
                self.assertIs(error, worker.original_error)
                self.assertEqual(worker.exit_code(None, error), 65)
                workers.append(worker)
        base.on_wait = run_worker
        with patch.object(L.cache, "provider_command_outputs", side_effect=AssertionError("FAILED_BYTES_MUST_NOT_PARSE")):
            self.assertRegex(str(caught(base.run_owner)), "SUPERVISOR_WORKER_FAILED")
        result = self.owner.transcript
        self.assertTrue(result.failed)
        self.assertEqual(result.provider_return.kind, "failed")
        self.assertEqual(result.provider_return.stdout, workers[0].capture_return.stdout)
        self.assertEqual(result.provider_return.exit_code, 19)

    def test_late_poll_with_complete_packet_does_not_gain_control_return(self):
        def configure():
            def poll():
                self.model.raw = 250 * clocks.NS
                return 0
            self.owner.launch.child.poll.side_effect = poll
        self.fixture.on_wait = configure
        self.assertRegex(str(caught(self.fixture.run_owner)), "WORKER_CUTOFF")
        self.assertEqual(self.owner.transcript.worker_exit_code, 0)
        self.assertIsNone(self.owner._qualified_wait)
        self.assertIsNone(self.owner.transcript.provider_return)
        self.assertIsNone(self.owner._readers["packet-reader"])

    def test_missing_ack_keeps_closed_opaque_failure_without_provider_authority(self):
        self.fixture.model_stdout = b""
        self.assertIsInstance(caught(self.fixture.run_owner), T.ProviderReturnError)
        self.assertTrue(self.owner.transcript.failed)
        self.assertIsNone(self.owner.transcript.provider_return)
        self.assertFalse(self.owner.unknown)
        self.assertTrue(self.owner.launch.directory._closed)

    def test_duplicate_ack_does_not_open_packet_or_accept_worker_zero(self):
        def duplicate():
            self.model.api.write(self.owner.launch.stdout.native_handle, self.fixture.model_stdout)
        self.fixture.on_wait = duplicate
        self.assertIsInstance(caught(self.fixture.run_owner), T.ProviderReturnError)
        self.assertIsNone(self.owner._readers["packet-reader"])
        self.assertIsNone(self.owner.transcript.provider_return)

    def test_same_bytes_new_file_identity_refuses_and_pins_distinct_owners(self):
        self.fixture.on_wait = lambda: setattr(self.packet_node(), "identifier", 777)
        self.assertRegex(str(caught(self.fixture.run_owner)), "PACKET_REPLACED")
        self.fixture.pinned()

    def test_same_size_changed_packet_hash_refuses_and_pins_distinct_owners(self):
        def change():
            node = self.packet_node()
            node.content = node.content.replace(b"MODEL", b"XXXXX", 1) if b"MODEL" in node.content else b"!" + node.content[1:]
        self.fixture.on_wait = change
        self.assertRegex(str(caught(self.fixture.run_owner)), "PACKET_CHANGED")
        self.fixture.pinned()

    def test_reader_registered_before_post_open_clock_failure(self):
        original = files.PrivateDirectory.open_file
        def opened(owner, name, **kwargs):
            result = original(owner, name, **kwargs)
            if name == T.PACKET_NAME:
                self.model.raw = 280 * clocks.NS
            return result
        with patch.object(files.PrivateDirectory, "open_file", opened):
            self.assertRegex(str(caught(self.fixture.run_owner)), "LAUNCH_EXPIRED")
        self.assertIsNotNone(self.owner._readers["packet-reader"])
        self.assertFalse(self.owner._readers["packet-reader"].closed)
        self.fixture.pinned()

    def test_reader_close_unknown_does_not_release_original_roots(self):
        original = files.NativeFile.close
        failure, calls = F.Cancel("MODEL_READER_CLOSE_UNKNOWN"), []
        def close(owner):
            if PureWindowsPath(owner.path).name == T.PACKET_NAME and not owner._writable:
                calls.append(owner)
                original(owner)
                raise failure
            return original(owner)
        with patch.object(files.NativeFile, "close", close):
            self.assertIs(caught(self.fixture.run_owner), failure)
        self.assertEqual(calls, [self.owner._readers["packet-reader"]])
        self.fixture.pinned()

    def test_windows_packet_reader_is_separate_and_preclose_timestamp_is_not_reused(self):
        self.fixture.on_wait = lambda: setattr(self.packet_node(), "version", self.packet_node().version + 1)
        result = self.fixture.run_owner()
        self.assertIsNotNone(result.provider_return)
        self.assertTrue(self.owner._readers["packet-reader"].closed)
        self.assertIn("packet-reader", result.closed_resources)
        self.assertEqual(result.provider_return.provider_acceptance, "NOT_ESTABLISHED")

    def test_nonreserved_worker_exit_with_valid_success_packet_is_opaque_only(self):
        self.fixture.fixture.worker_code = 66
        self.assertRegex(str(caught(self.fixture.run_owner)), "WORKER_FAILED")
        self.assertIsNone(self.owner.transcript.provider_return)
        self.assertEqual(self.owner.transcript.worker_exit_code, 66)


class PosixPacketModels(unittest.TestCase):
    def setUp(self):
        self.fixture = F.PosixTranscriptModels()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def tearDown(self):
        self.fixture.tearDown()

    def test_fixed_packet_symlink_refuses_without_reading_target(self):
        model, owner = self.fixture.model, self.fixture.owner
        target = model.base / "unrelated-packet"
        target.write_bytes(b"MODEL_DO_NOT_READ")
        def swap(path, mode):
            if mode == "rb" and path.name == T.PACKET_NAME:
                path.unlink()
                path.symlink_to(target)
        model.before_open = swap
        caught(self.fixture.run_owner)
        self.assertTrue(owner.unknown)
        self.assertFalse(model.root.closed)
        self.assertNotIn("packet", owner._raw)
        self.assertEqual(target.read_bytes(), b"MODEL_DO_NOT_READ")

    def test_short_packet_read_keeps_original_reader_and_roots_pinned(self):
        model, owner = self.fixture.model, self.fixture.owner
        model.reader_wrap = lambda path, stream: (SimpleNamespace(fileno=stream.fileno, read=lambda _: b"",
            close=stream.close) if path.name == T.PACKET_NAME else stream)
        self.assertRegex(str(caught(self.fixture.run_owner)), "PACKET_CHANGED")
        self.assertTrue(owner.unknown)
        self.assertEqual(owner._raw["packet"], b"")
        self.assertFalse(model.root.closed)

    def test_actual_packet_reader_closed_before_last_directory(self):
        result = self.fixture.run_owner()
        self.assertLess(result.closed_resources.index("packet-reader"), result.closed_resources.index("directory"))
        self.assertTrue(self.fixture.owner._readers["packet-reader"].closed)
        self.assertEqual(result.provider_return.stdout, b"MODEL_INNER_STDOUT")


if __name__ == "__main__":
    unittest.main()
