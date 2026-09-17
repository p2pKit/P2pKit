#!/usr/bin/env python3
"""Synthetic coordinator controls only: never import/start a peer, Java or a network."""
from copy import deepcopy
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "independent_peer_capture", Path(__file__).resolve().parents[1] / "independent_peer_capture.py",
)
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)


def binding():
    return {"invocationId": "synthetic-invocation", "caseId": "synthetic-case", "pid": os.getpid(),
            "parentPid": os.getppid(), "bridgeSha256": "1" * 64, "helperSha256": "2" * 64,
            "peerManifestSha256": "3" * 64}


def terminal(code=0):
    note = {"stage": "drain-read", "cause": "read-error", "category": "connection-reset",
            "kind": None, "errno": 54}
    endpoint = {"v": 1, "protocol": {"event": "closed", "origin": "local", "kind": None, "stage": "active"},
                "retirementStarted": True, "writeShutdown": "completed", "actualDrainReadEof": True,
                "listenerClose": "not-owned", "streamClose": "closed", "causes": [deepcopy(note)]}
    actor = {"done": True, "exitCode": code, "failureKind": None, "controlOutputFailed": False,
             "constructorCleanupFailed": False, "endpointOutputFailed": False, "socketCleanupFailed": False,
             "retirementErrorKind": None, "resourceFinalization": "returned-clean", "endpoint": endpoint,
             "causes": [deepcopy(note)]}
    return {"v": 1, "state": "returned", "returnCode": code, "lastStage": "stdio-restore-input",
            "raisedStage": None, "actor": actor, "causes": [deepcopy(note)], "finalOutput": "drained",
            "stdioRestore": {"input": "restored", "output": "restored"}}


class Holder:
    def __init__(self, value=None, error=None):
        self.value = terminal() if value is None else value
        self.error = error

    @property
    def snapshot(self):
        if self.error is not None:
            raise self.error
        return deepcopy(self.value)


class Sink:
    def __init__(self, export_error=None, close_error=None):
        self.export_error, self.close_error = export_error, close_error
        self.records, self.close_count = [], 0

    def export(self, record):
        self.records.append(record)
        if self.export_error is not None:
            raise self.export_error

    def close(self):
        self.close_count += 1
        if self.close_error is not None:
            raise self.close_error


class CaptureSchemaTest(unittest.TestCase):
    def decode(self, value, expected=None, observed=0):
        expected = binding() if expected is None else expected
        return capture.decode_capture(capture.encode_capture(value, expected), expected, observed)

    def test_codes_and_separate_actor_exit(self):
        for code in (0, 2, 70):
            with self.subTest(code=code):
                value = terminal(code)
                value["actor"]["exitCode"] = 70
                actual = self.decode(value, observed=code)
                self.assertEqual(code, actual["terminal"]["returnCode"])
                self.assertEqual(70, actual["terminal"]["actor"]["exitCode"])
                self.assertTrue(capture.has_returned_actor_endpoint(actual))
                # Completeness is deliberately not successful natural/process/protocol acceptance.
                self.assertNotIn("PASS", actual)

    def test_incomplete_and_raised_records_do_not_invent_return(self):
        for state in ("unused", "running", "raised"):
            value = terminal()
            value.update(state=state, returnCode=None, actor=None)
            actual = self.decode(value, observed=-9)
            self.assertFalse(capture.has_returned_actor_endpoint(actual))
            value["returnCode"] = 0
            with self.assertRaises(capture.CaptureError):
                self.decode(value)
        for key in ("actor", "endpoint"):
            value = terminal()
            if key == "actor":
                value[key] = None
            else:
                value["actor"][key] = None
            self.assertFalse(capture.has_returned_actor_endpoint(self.decode(value)))

    def test_process_exit_and_each_binding_field_must_match(self):
        raw = capture.encode_capture(terminal(), binding())
        with self.assertRaises(capture.CaptureError):
            capture.decode_capture(raw, binding(), 70)
        for key in capture.BINDING_FIELDS:
            expected = binding()
            expected[key] = expected[key] + 1 if type(expected[key]) is int else (
                "f" * 64 if key.endswith("Sha256") else "different"
            )
            with self.subTest(key=key), self.assertRaises(capture.CaptureError):
                capture.decode_capture(raw, expected, 0)

    def test_missing_and_extra_fields_at_every_object(self):
        base = json.loads(capture.encode_capture(terminal(), binding()))

        def objects(value, path=()):
            if type(value) is dict:
                yield path, value
                for key, item in value.items():
                    yield from objects(item, path + (key,))
            elif type(value) is list:
                for key, item in enumerate(value):
                    yield from objects(item, path + (key,))

        for path, item in objects(base):
            for remove in [None, *item]:
                value = deepcopy(base)
                current = value
                for key in path:
                    current = current[key]
                if remove is None:
                    current["unexpected"] = "not admitted"
                else:
                    del current[remove]
                with self.subTest(path=path, remove=remove), self.assertRaises(capture.CaptureError):
                    capture.decode_capture(json.dumps(value).encode(), binding(), 0)

    def test_exact_types_and_bounded_numbers(self):
        for number in (True, False, 0.0, "0", -1, 1, 71, 2**128):
            value = terminal()
            value["returnCode"] = number
            with self.subTest(number=number), self.assertRaises(capture.CaptureError):
                self.decode(value)
        for number in (-(2**31), 2**31 - 1, None):
            value = terminal()
            value["causes"][0]["errno"] = number
            self.decode(value)
        for number in (True, 1.0, "1", -(2**31) - 1, 2**31):
            value = terminal()
            value["causes"][0]["errno"] = number
            with self.assertRaises(capture.CaptureError):
                self.decode(value)
        value = terminal()
        value["actor"]["endpoint"]["actualDrainReadEof"] = 1
        with self.assertRaises(capture.CaptureError):
            self.decode(value)

    def test_unknown_tokens_and_distinct_cause_stages(self):
        for key in ("stage", "cause", "category", "kind"):
            value = terminal()
            value["causes"][0][key] = "dynamic exception text is forbidden"
            with self.assertRaises(capture.CaptureError):
                self.decode(value)
        for notes in ([terminal()["causes"][0]] * 2, [terminal()["causes"][0]] * 37):
            value = terminal()
            value["causes"] = notes
            with self.assertRaises(capture.CaptureError):
                self.decode(value)

    def test_widest_snapshot_fits_its_separate_cap(self):
        value, expected = terminal(70), binding()
        expected.update(invocationId="i" * 64, caseId="c" * 64, pid=2**63 - 1, parentPid=2**63 - 1)
        notes = [{"stage": stage, "cause": max(capture.CAUSES, key=len), "category": max(capture.CATEGORIES, key=len),
                  "kind": max(capture.KINDS, key=len), "errno": -(2**31)} for stage in sorted(capture.STAGES)]
        value["lastStage"] = value["raisedStage"] = max(capture.STAGES, key=len)
        value["finalOutput"] = "not-nonblocking"
        value["stdioRestore"] = {"input": "not-attempted", "output": "not-attempted"}
        value["actor"]["resourceFinalization"] = "returned-uncertain"
        for key in ("done", "controlOutputFailed", "constructorCleanupFailed", "endpointOutputFailed", "socketCleanupFailed"):
            value["actor"][key] = False
        value["actor"]["failureKind"] = value["actor"]["retirementErrorKind"] = max(capture.KINDS, key=len)
        value["actor"]["endpoint"].update(
            retirementStarted=False, actualDrainReadEof=False, writeShutdown="not-attempted",
            listenerClose="interrupted", streamClose="interrupted",
        )
        value["actor"]["endpoint"]["protocol"].update(
            origin="remote", kind=max(capture.KINDS, key=len), stage=max(capture.PROTOCOL_STAGES, key=len),
        )
        for level in (value, value["actor"], value["actor"]["endpoint"]):
            level["causes"] = deepcopy(notes)
        raw = capture.encode_capture(value, expected)
        self.assertEqual(108, len(notes) * 3)
        self.assertLess(len(raw), capture.MAX_BYTES)
        self.assertEqual(value, capture.decode_capture(raw, expected, 70)["terminal"])

    def test_raw_boundaries_duplicates_numbers_trailing_and_utf8(self):
        raw = capture.encode_capture(terminal(), binding())
        padded = raw + b" " * (capture.MAX_BYTES - len(raw))
        capture.decode_capture(padded, binding(), 0)
        invalid = [padded + b" ", b"", raw + b"{}", b"\xff", b"[" * 2000 + b"]" * 2000,
                   raw.replace(b'"v":1', b'"v":1,"\\u0076":1', 1),
                   raw.replace(b'"returnCode":0', b'"returnCode":-0'),
                   raw.replace(b'"returnCode":0', b'"returnCode":0e0'),
                   raw.replace(b'"returnCode":0', b'"returnCode":NaN')]
        # Removing only the final newline is still valid JSON; all earlier truncated prefixes are invalid.
        invalid.extend(raw[:length] for length in range(len(raw) - 1))
        for index, data in enumerate(invalid):
            with self.subTest(index=index), self.assertRaises(capture.CaptureError):
                capture.decode_capture(data, binding(), 0)

    def test_no_inference_from_eof_close_or_fionread(self):
        value = terminal(70)
        value["actor"]["endpoint"]["actualDrainReadEof"] = False
        actual = self.decode(value, observed=70)
        self.assertFalse(actual["terminal"]["actor"]["endpoint"]["actualDrainReadEof"])
        self.assertEqual("closed", actual["terminal"]["actor"]["endpoint"]["streamClose"])
        value["actor"]["endpoint"]["FIONREAD"] = 0
        with self.assertRaises(capture.CaptureError):
            self.decode(value, observed=70)


class CaptureParityTest(unittest.TestCase):
    def test_exact_return_arguments_and_no_added_output(self):
        for code in (0, 2, 70):
            sink, holder, calls = Sink(), Holder(), []

            def run(*args, **kwargs):
                calls.append((args, kwargs))
                return code

            output, error = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                self.assertEqual(code, capture.invoke_with_capture(run, holder, 41, 42, sink))
            self.assertEqual([((41, 42, 120), {"diagnostics": holder})], calls)
            self.assertEqual(1, len(sink.records))
            self.assertEqual(1, sink.close_count)
            self.assertEqual("", output.getvalue() + error.getvalue())

    def test_exception_identity_survives_all_diagnostic_failures(self):
        for original in (RuntimeError("synthetic-original"), KeyboardInterrupt(), SystemExit(70)):
            for stage in ("none", "snapshot", "export", "close"):
                holder = Holder(error=SystemExit(99) if stage == "snapshot" else None)
                sink = Sink(export_error=KeyboardInterrupt() if stage == "export" else None,
                            close_error=RuntimeError("diagnostic-only") if stage == "close" else None)

                def run(*_args, **_kwargs):
                    raise original

                with self.subTest(stage=stage), self.assertRaises(BaseException) as raised:
                    capture.invoke_with_capture(run, holder, 41, 42, sink)
                self.assertIs(original, raised.exception)
                self.assertEqual(1, sink.close_count)

    def test_diagnostic_failures_cannot_turn_return_into_exception_or_retry(self):
        for error in (RuntimeError(), KeyboardInterrupt(), SystemExit(70)):
            for stage in ("snapshot", "export", "close"):
                holder = Holder(error=error if stage == "snapshot" else None)
                sink = Sink(export_error=error if stage == "export" else None,
                            close_error=error if stage == "close" else None)
                run = mock.Mock(return_value=2)
                self.assertEqual(2, capture.invoke_with_capture(run, holder, 1, 2, sink))
                run.assert_called_once_with(1, 2, 120, diagnostics=holder)
                self.assertEqual(1, sink.close_count)


class CaptureSinkTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p2pkit-capture-test-")
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name).resolve()
        self.expected = binding()
        self.case = self.state / "work" / "core-tcp-interop" / self.expected["invocationId"] / self.expected["caseId"]
        for path in (self.state / "work", self.state / "work" / "core-tcp-interop", self.case.parent, self.case):
            path.mkdir(mode=0o700)
        marker = ("p2pkit-owned-peer-v1\n" + self.expected["invocationId"] + "\n").encode()
        self.marker = self.case.parent / "OWNER"
        self.marker.write_bytes(marker)
        self.marker.chmod(0o600)
        self.marker_hash = hashlib.sha256(marker).hexdigest()

    def sink(self):
        value = capture.OwnedCapture(self.state, self.case, self.expected, self.marker_hash)
        self.addCleanup(value.close)
        return value

    def test_real_create_new_bytes_mode_binding_and_directory_fd_retirement(self):
        sink = self.sink()
        directory_fd = sink._fd
        self.assertEqual(0, capture.invoke_with_capture(lambda *_args, **_kwargs: 0, Holder(), 41, 42, sink))
        path = self.case / capture.RAW_NAME
        self.assertEqual(0o600, path.stat().st_mode & 0o777)
        self.assertEqual(terminal(), capture.decode_capture(path.read_bytes(), self.expected, 0)["terminal"])
        with self.assertRaises(OSError):
            os.fstat(directory_fd)
        with self.assertRaises(capture.CaptureError):
            sink.export(terminal())

    def test_existing_file_or_symlink_is_never_overwritten(self):
        path = self.case / capture.RAW_NAME
        path.write_bytes(b"prior evidence")
        with self.assertRaises(capture.CaptureError):
            self.sink()
        self.assertEqual(b"prior evidence", path.read_bytes())
        path.unlink()
        path.symlink_to(self.marker)
        with self.assertRaises(capture.CaptureError):
            self.sink()
        self.assertEqual(self.marker_hash, hashlib.sha256(self.marker.read_bytes()).hexdigest())

    def test_post_admission_collision_keeps_existing_bytes(self):
        sink = self.sink()
        path = self.case / capture.RAW_NAME
        path.write_bytes(b"late evidence")
        with self.assertRaises(FileExistsError):
            sink.export(terminal())
        self.assertEqual(b"late evidence", path.read_bytes())

    def test_paths_modes_ownership_marker_and_process_bindings_fail_closed(self):
        self.case.chmod(0o755)
        with self.assertRaises(capture.CaptureError):
            self.sink()
        self.case.chmod(0o700)
        with mock.patch.object(capture.os, "geteuid", return_value=os.getuid() + 1):
            with self.assertRaises(capture.CaptureError):
                self.sink()
        for key in ("pid", "parentPid"):
            self.expected[key] += 1
            with self.assertRaises(capture.CaptureError):
                self.sink()
            self.expected[key] -= 1
        self.marker.write_bytes(b"different owner")
        with self.assertRaises(capture.CaptureError):
            self.sink()

    def test_symlink_and_replaced_case_are_refused_without_adoption(self):
        sink = self.sink()
        original = self.case.with_name("original-case")
        self.case.rename(original)
        self.case.symlink_to(original, target_is_directory=True)
        with self.assertRaises(capture.CaptureError):
            sink.export(terminal())
        with self.assertRaises(capture.CaptureError):
            self.sink()
        self.case.unlink()
        self.case.mkdir(mode=0o700)
        self.assertFalse((original / capture.RAW_NAME).exists())
        self.assertFalse((self.case / capture.RAW_NAME).exists())

    def test_directory_replacement_after_admission_is_rejected(self):
        sink = self.sink()
        self.case.rename(self.case.with_name("original-case"))
        self.case.mkdir(mode=0o700)
        with self.assertRaises(capture.CaptureError):
            sink.export(terminal())
        self.assertFalse((self.case / capture.RAW_NAME).exists())

    def test_short_writes_complete_without_overwrite_or_retry_of_failure(self):
        sink, write = self.sink(), os.write
        with mock.patch.object(capture.os, "write", side_effect=lambda fd, data: write(fd, data[:31])):
            sink.export(terminal())
        capture.decode_capture((self.case / capture.RAW_NAME).read_bytes(), self.expected, 0)

    def test_partial_zero_progress_and_enospc_keep_failure_bytes_and_return(self):
        for suffix, failure in (("zero", 0), ("enospc", OSError(28, "synthetic ENOSPC"))):
            self.expected["caseId"] = suffix
            self.case = self.case.with_name(suffix)
            self.case.mkdir(mode=0o700)
            sink, write = self.sink(), os.write
            first = True

            def failing_write(fd, data):
                nonlocal first
                if first:
                    first = False
                    return write(fd, data[:17])
                if isinstance(failure, Exception):
                    raise failure
                return failure

            with mock.patch.object(capture.os, "write", side_effect=failing_write) as writes:
                self.assertEqual(70, capture.invoke_with_capture(lambda *_a, **_k: 70, Holder(terminal(70)), 41, 42, sink))
                self.assertEqual(2, writes.call_count)
            raw = (self.case / capture.RAW_NAME).read_bytes()
            self.assertEqual(17, len(raw))
            with self.assertRaises(capture.CaptureError):
                capture.decode_capture(raw, self.expected, 70)

    def test_close_error_does_not_replace_return_or_claim_close_receipt(self):
        sink, write, close = self.sink(), os.write, os.close
        file_fd = None

        def observe_write(fd, data):
            nonlocal file_fd
            file_fd = fd
            return write(fd, data)

        def close_then_raise(fd):
            close(fd)
            if fd == file_fd:
                raise OSError("synthetic post-close error")

        with mock.patch.object(capture.os, "write", side_effect=observe_write), \
                mock.patch.object(capture.os, "close", side_effect=close_then_raise):
            self.assertEqual(0, capture.invoke_with_capture(lambda *_a, **_k: 0, Holder(), 41, 42, sink))
        # This proves why readable bytes are NOT a close-syscall receipt.
        capture.decode_capture((self.case / capture.RAW_NAME).read_bytes(), self.expected, 0)
        self.assertIsNone(sink._fd)


if __name__ == "__main__":
    unittest.main()
