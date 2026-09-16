#!/usr/bin/env python3
"""Modeled native-call controls only; no process, DLL or private-file execution."""
from __future__ import annotations

import ctypes
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("audit_processes", ROOT / "scripts/audit_processes.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


def load_caller(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    result = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"audit_processes": P}):
        spec.loader.exec_module(result)
    return result


A = load_caller("owned_output_audit", "run-audit-command.py")
C = load_caller("owned_output_windows", "run-windows-directory-control.py")
H = load_caller("owned_output_hosted", "run-hosted-lock-candidate.py")


class ModelWindows:
    def __init__(self):
        self.closed, self.calls, self.duplicates, self.attributes = [], [], [], {}
        self.close_attempts, self.close_failures = [], set()
        self.attributes_failure, self.termination_failure = False, False
        self.inheritable = False
        self.member = True
        self.resume_failure = False
        self.fail_duplicate = 0
        self.next_handle = 1000

    def check(self, value, operation):
        if not value:
            raise P.OwnershipError("modeled " + operation)
        return value

    def close(self, handle):
        if handle:
            self.close_attempts.append(handle)
            if handle in self.close_failures:
                raise P.OwnershipError(f"MODELED_CLOSE_FAILURE_{handle}")
            self.closed.append(handle)

    def GetHandleInformation(self, handle, flags):
        self.calls.append(("inspect-original", handle))
        flags._obj.value = 1 if self.inheritable else 0
        return 1

    def DuplicateHandle(self, source_process, original, destination_process, result, access, inherit, flags):
        self.calls.append(("duplicate", original))
        if self.fail_duplicate and len(self.duplicates) + 1 == self.fail_duplicate:
            return 0
        assert source_process.value == destination_process.value == ctypes.c_void_p(-1).value
        assert (access, inherit, flags) == (0, 1, 2)
        result._obj.value = original + 100
        self.duplicates.append((original, result._obj.value))
        return 1

    def CreatePipe(self, read, write, security, size):
        self.calls.append(("pipe",))
        read._obj.value, write._obj.value = self.next_handle, self.next_handle + 1
        self.next_handle += 2
        return 1

    def SetHandleInformation(self, handle, mask, value):
        assert (mask, value) == (1, 0)
        return 1

    def CreateFileW(self, path, *args):
        assert path == "NUL"
        return 200

    def InitializeProcThreadAttributeList(self, attributes, count, flags, size):
        assert (count, flags) == (2, 0)
        size._obj.value = 256
        return int(attributes is not None)

    def UpdateProcThreadAttribute(self, attributes, flags, kind, value, size, previous, returned):
        self.attributes[kind] = tuple(value)
        return 1

    def DeleteProcThreadAttributeList(self, attributes):
        self.calls.append(("delete-attributes",))
        if self.attributes_failure:
            raise P.OwnershipError("MODELED_ATTRIBUTES_FAILURE")

    def CreateProcessW(self, application, command, process_security, thread_security, inherit, flags,
                       environment, cwd, startup, result):
        self.calls.append(("create",))
        assert inherit == 1 and flags == 0x80604
        assert self.attributes[0x0002000D] == (900,)
        self.child_std_handles = (startup._obj.startup.stdin, startup._obj.startup.stdout,
                                 startup._obj.startup.stderr)
        self.child_command = command.value
        result._obj.process, result._obj.thread = 300, 301
        result._obj.pid, result._obj.tid = 400, 401
        return 1

    def IsProcessInJob(self, process, job, result):
        assert (process, job) == (300, 900)
        self.calls.append(("membership",))
        result._obj.value = int(self.member)
        return 1

    def identity(self, process, pid):
        return {"pid": pid, "creationFileTime": 123456}

    def ResumeThread(self, thread):
        assert thread == 301
        self.calls.append(("resume",))
        return 0xFFFFFFFF if self.resume_failure else 1

    def TerminateJobObject(self, job, code):
        self.calls.append(("terminate-job", job, code))
        return 0 if self.termination_failure else 1


class OutputSinkTests(unittest.TestCase):
    def setUp(self):
        self.reset_scope()
        self.stdout = SimpleNamespace(native_handle=10, writable=lambda: True)
        self.stderr = SimpleNamespace(native_handle=11, writable=lambda: True)
        self.fake_crt = SimpleNamespace(open_osfhandle=Mock(side_effect=lambda handle, flags: handle + 5000))
        self.fd_close = Mock()
        self.fileio = Mock(side_effect=lambda fd, mode, closefd: io.BytesIO())
        contexts = [patch.dict(sys.modules, {"msvcrt": self.fake_crt}),
                    patch.object(P.os, "O_BINARY", 0x8000, create=True),
                    patch.object(P.os, "close", self.fd_close), patch.object(io, "FileIO", self.fileio),
                    patch.object(P.os, "fdopen", side_effect=AssertionError("Use the nonowning FileIO boundary")),
                    patch.object(P, "resolve_executable", side_effect=lambda argv, cwd, env: list(argv)),
                    patch.object(subprocess, "Popen", side_effect=AssertionError("no native child in models")),
                    patch.object(ctypes, "CDLL", side_effect=AssertionError("no native library in models")),
                    patch.object(ctypes, "WinDLL", side_effect=AssertionError("no native library in models"), create=True)]
        for context in contexts:
            context.start()
            self.addCleanup(context.stop)

    def reset_scope(self):
        self.api = ModelWindows()
        self.scope = object.__new__(P.WindowsScope)
        self.scope.api, self.scope.job, self.scope.job_id, self.scope.invocation = self.api, 900, "a" * 32, "b" * 32
        self.scope.leaders, self.scope.launches, self.scope.known = [], [], {}
        self.scope.discovery_errors = set()

    def spawn(self, **changes):
        sinks = {"stdout": self.stdout, "stderr": self.stderr}
        sinks.update(changes)
        return self.scope.spawn([r"C:\tools\fixture.exe", "literal argument"], r"C:\work", {"SAFE": "1"}, **sinks)

    def test_windows_duplicates_only_explicit_outputs_and_assigns_before_resume(self):
        child = self.spawn()
        self.assertEqual(self.api.duplicates, [(10, 110), (11, 111)])
        self.assertEqual(self.api.attributes[0x00020002], (200, 110, 111))
        self.assertEqual(self.api.child_std_handles, (200, 110, 111))
        self.assertNotIn(("pipe",), self.api.calls)
        self.assertLess(self.api.calls.index(("membership",)), self.api.calls.index(("resume",)))
        self.assertEqual(sorted(self.api.closed), [110, 111, 200, 301])
        self.assertIsNone(child.stdout)
        self.assertIsNone(child.stderr)
        self.assertEqual(self.scope.launches[0]["outputMode"], "caller-owned-native-files")
        self.assertTrue(self.scope.launches[0]["jobAssignedBeforeResume"])
        self.fake_crt.open_osfhandle.assert_not_called()
        self.fileio.assert_not_called()
        self.fd_close.assert_not_called()
        self.scope.close()
        self.assertIn(300, self.api.closed)
        self.assertIn(900, self.api.closed)
        self.assertNotIn(10, self.api.closed)
        self.assertNotIn(11, self.api.closed)

    def test_default_windows_pipe_contract_is_preserved(self):
        streams = [io.BytesIO(b"stdout"), io.BytesIO(b"stderr")]
        with patch.object(io, "FileIO", side_effect=streams) as wrap:
            child = self.scope.spawn([r"C:\tools\fixture.exe"], r"C:\work", {})
        self.assertEqual([row for row in self.api.calls if row == ("pipe",)], [("pipe",), ("pipe",)])
        self.assertEqual(self.api.duplicates, [])
        self.assertEqual(child.stdout.read(6), b"stdout")
        self.assertEqual(child.stderr.read(6), b"stderr")
        self.assertEqual([child.stdout.fileno(), child.stderr.fileno()], [6000, 6002])
        self.assertEqual([call.args for call in wrap.call_args_list], [(6000, "rb"), (6002, "rb")])
        self.assertTrue(all(call.kwargs == {"closefd": False} for call in wrap.call_args_list))
        self.assertNotIn("outputMode", self.scope.launches[0])
        self.assertEqual(self.api.attributes[0x00020002], (200, 1001, 1003))
        self.assertEqual(sorted(self.api.closed), [200, 301, 1001, 1003])
        self.scope.close()
        self.assertTrue(all(not stream.closed for stream in streams))  # Successful caller ownership survives.
        self.fd_close.assert_not_called()
        for stream in (child.stdout, child.stderr):
            self.assertFalse(stream.closed)
            stream.close()
            stream.close()
            self.assertTrue(stream.closed)
            with self.assertRaises(ValueError):
                stream.read(1)
            with self.assertRaises(ValueError):
                stream.fileno()
        self.assertEqual([call.args[0] for call in self.fd_close.call_args_list], [6000, 6002])

    def test_half_redirect_rejected_before_native_allocation(self):
        with self.assertRaisesRegex(P.OwnershipError, "Both owned output"):
            self.spawn(stderr=None)
        self.assertEqual(self.api.calls, [])
        self.assertEqual(self.scope.launches, [])

    def test_original_inheritable_handle_is_not_admitted(self):
        self.api.inheritable = True
        with self.assertRaisesRegex(P.OwnershipError, "not be inheritable"):
            self.spawn()
        self.assertEqual(self.api.duplicates, [])
        self.assertNotIn(("create",), self.api.calls)

    def test_readonly_invalid_and_duplicate_original_handles_are_rejected(self):
        for sink in (SimpleNamespace(native_handle=0, writable=lambda: True),
                     SimpleNamespace(native_handle=ctypes.c_void_p(-1).value, writable=lambda: True),
                     SimpleNamespace(native_handle=True, writable=lambda: True),
                     SimpleNamespace(native_handle=20, writable=lambda: False), self.stdout):
            with self.subTest(sink=sink):
                with self.assertRaisesRegex(P.OwnershipError, "Distinct open"):
                    self.spawn(stderr=sink)
                self.assertNotIn(("create",), self.api.calls)
        self.assertNotIn(10, self.api.closed)

    def test_second_duplicate_failure_retires_first_duplicate_not_original(self):
        self.api.fail_duplicate = 2
        with self.assertRaisesRegex(P.OwnershipError, "DuplicateHandle"):
            self.spawn()
        self.assertEqual(self.api.closed, [110])
        self.assertNotIn(("create",), self.api.calls)

    def test_membership_failure_never_resumes_and_requests_job_retirement(self):
        self.api.member = False
        with self.assertRaisesRegex(P.OwnershipError, "lacks required job membership"):
            self.spawn()
        self.assertNotIn(("resume",), self.api.calls)
        self.assertIn(("terminate-job", 900, 125), self.api.calls)
        self.assertEqual(sorted(self.api.closed), [110, 111, 200, 300, 301])
        self.assertEqual(self.scope.leaders, [])

    def test_resume_failure_leaves_exact_child_handle_for_outer_owner(self):
        self.api.resume_failure = True
        with self.assertRaisesRegex(P.OwnershipError, "ResumeThread"):
            self.spawn()
        self.assertIn(("terminate-job", 900, 125), self.api.calls)
        self.assertEqual(len(self.scope.leaders), 1)
        self.assertEqual(self.scope.leaders[0].handle, 300)
        self.scope.close()
        self.assertEqual(self.api.closed.count(300), 1)
        self.assertNotIn(10, self.api.closed)

    def test_redirect_cleanup_failure_attempts_every_resource_and_keeps_child_for_outer_drain(self):
        self.api.close_failures = {110}
        with self.assertRaisesRegex(P.OwnershipError, "retirement UNKNOWN") as raised:
            self.spawn()
        self.assertIn("MODELED_CLOSE_FAILURE_110", str(raised.exception))
        self.assertEqual(self.api.close_attempts, [110, 111, 200, 301])
        self.assertTrue(self.scope.launches[0]["resumed"])
        self.assertEqual(self.scope.leaders[0].handle, 300)
        rows = self.scope.launches[0]["resourceCleanup"]
        self.assertEqual(sum(row["status"] == "UNKNOWN" for row in rows), 1)
        self.assertTrue(self.scope.description()["discoveryErrors"])
        self.scope.close()
        self.assertEqual(self.api.close_attempts, [110, 111, 200, 301, 300, 900])
        self.assertNotIn(10, self.api.close_attempts)
        self.assertNotIn(11, self.api.close_attempts)

    def test_primary_failure_survives_multiple_finalizer_failures_and_all_attempts(self):
        self.api.member = False
        self.api.close_failures = {110, 301}
        self.api.attributes_failure = self.api.termination_failure = True
        with self.assertRaisesRegex(P.OwnershipError, "lacks required job membership") as raised:
            self.spawn()
        self.assertNotIn(("resume",), self.api.calls)
        self.assertEqual(self.api.close_attempts, [110, 111, 200, 301, 300])
        rows = self.scope.launches[0]["resourceCleanup"]
        unknown = [row for row in rows if row["status"] == "UNKNOWN"]
        self.assertEqual(len(unknown), 4)
        self.assertEqual({P._retirement_text(row) for row in unknown}, self.scope.discovery_errors)
        self.assertEqual(set(raised.exception.__notes__), self.scope.discovery_errors)
        self.scope.close()
        self.assertEqual(self.api.close_attempts[-1], 900)

    def test_default_pipe_cleanup_also_attempts_every_owned_handle(self):
        streams = [io.BytesIO(), io.BytesIO()]
        self.api.close_failures = {1001}
        with patch.object(io, "FileIO", side_effect=streams), \
                self.assertRaisesRegex(P.OwnershipError, "retirement UNKNOWN"):
            self.scope.spawn([r"C:\tools\fixture.exe"], r"C:\work", {})
        self.assertEqual(self.api.close_attempts, [1001, 1003, 200, 301])
        self.assertTrue(self.scope.leaders[0].stdout.closed)
        self.assertEqual(self.api.duplicates, [])
        self.assertTrue(all(stream.closed for stream in streams))
        self.assertEqual([call.args[0] for call in self.fd_close.call_args_list], [6000, 6002])
        self.scope.close()

    def test_default_pipe_resume_failure_attempts_all_streams_despite_other_cleanup_failures(self):
        stream = Mock()
        stream.close.side_effect = P.OwnershipError("MODELED_STREAM_CLOSE_FAILURE")
        self.api.resume_failure = True
        streams = [stream, io.BytesIO()]
        self.api.close_failures = {1001}
        with patch.object(io, "FileIO", side_effect=streams), \
                self.assertRaisesRegex(P.OwnershipError, "ResumeThread") as raised:
            self.scope.spawn([r"C:\tools\fixture.exe"], r"C:\work", {})
        stream.close.assert_called_once_with()
        self.assertTrue(streams[1].closed)
        self.assertEqual(self.api.close_attempts, [1001, 1003, 200, 301])
        self.assertTrue(any("MODELED_STREAM_CLOSE_FAILURE" in note for note in raised.exception.__notes__))
        self.assertTrue(any("MODELED_CLOSE_FAILURE_1001" in note for note in raised.exception.__notes__))
        self.assertEqual([call.args[0] for call in self.fd_close.call_args_list], [6000, 6002])
        self.scope.close()

    def test_cleanup_cancellation_remains_cancellation_after_other_resources_are_attempted(self):
        interrupted = KeyboardInterrupt("modeled cancellation")
        self.api.DeleteProcThreadAttributeList = Mock(side_effect=interrupted)
        with self.assertRaises(KeyboardInterrupt) as raised:
            self.spawn()
        self.assertIs(raised.exception, interrupted)
        self.assertEqual(self.api.close_attempts, [110, 111, 200, 301])
        self.assertTrue(self.scope.description()["discoveryErrors"])
        self.scope.close()

    def test_outer_close_attempts_all_leaders_and_job_without_raw_handle_retry(self):
        self.scope.leaders = [P.WindowsProcess(self.api, 300, 400, None, None),
                              P.WindowsProcess(self.api, 302, 402, None, None)]
        self.api.close_failures = {300, 900}
        with self.assertRaisesRegex(P.OwnershipError, "retirement UNKNOWN") as raised:
            self.scope.close()
        self.assertEqual(self.api.close_attempts, [300, 302, 900])
        self.assertIn("MODELED_CLOSE_FAILURE_300", str(raised.exception))
        self.assertIn("MODELED_CLOSE_FAILURE_900", str(raised.exception))
        self.assertEqual(len(self.scope.description()["discoveryErrors"]), 2)
        self.scope.close()
        self.assertEqual(self.api.close_attempts, [300, 302, 900])
        self.assertEqual(len(self.scope.description()["discoveryErrors"]), 2)

    def test_failed_job_setup_preserves_primary_when_job_close_also_fails(self):
        self.api.CreateJobObjectW = Mock(return_value=900)
        self.api.SetInformationJobObject = Mock(return_value=0)
        self.api.close_failures = {900}
        with patch.object(P, "WinApi", return_value=self.api), \
                self.assertRaisesRegex(P.OwnershipError, "SetInformationJobObject") as raised:
            P.WindowsScope("a" * 32, "b" * 32, "C:\\state", "C:\\home")
        self.assertEqual(self.api.close_attempts, [900])
        self.assertIn("retirement UNKNOWN", raised.exception.__notes__[0])

    def test_late_finalizer_closes_unreturned_pipes_without_caller_rescue(self):
        streams = [io.BytesIO(), io.BytesIO()]
        self.api.close_failures = {1001}
        with patch.object(P.os, "fdopen", side_effect=streams), \
                patch.object(io, "FileIO", side_effect=streams), patch.object(P.os, "close"), \
                self.assertRaises(P.OwnershipError):
            self.scope.spawn([r"C:\tools\fixture.exe"], r"C:\work", {})
        self.assertTrue(all(stream.closed for stream in streams), "spawn never returned a caller-owned pipe")

    def test_failed_wrapper_after_crt_adoption_retires_descriptor(self):
        original = OSError("MODELED_FILEIO_CONSTRUCTION_FAILURE")
        with patch.object(P.os, "fdopen", side_effect=original), \
                patch.object(io, "FileIO", side_effect=original), patch.object(P.os, "close") as close, \
                self.assertRaises(OSError) as raised:
            self.scope.spawn([r"C:\tools\fixture.exe"], r"C:\work", {})
        self.assertIs(raised.exception, original)
        close.assert_called_once_with(6000)
        self.assertNotIn(1000, self.api.close_attempts)

    def test_every_late_temporary_failure_retires_pending_pipes_once(self):
        for failed in (1001, 1003, 200, 301, "attributes"):
            with self.subTest(failed=failed):
                self.reset_scope()
                self.fd_close.reset_mock()
                if failed == "attributes":
                    self.api.attributes_failure = True
                else:
                    self.api.close_failures = {failed}
                views = [io.BytesIO(), io.BytesIO()]
                with patch.object(io, "FileIO", side_effect=views), self.assertRaises(P.OwnershipError):
                    self.scope.spawn([r"C:\tools\fixture.exe"], r"C:\work", {})
                self.assertTrue(all(view.closed for view in views))
                self.assertEqual([call.args[0] for call in self.fd_close.call_args_list], [6000, 6002])
                self.assertEqual(self.api.close_attempts, [1001, 1003, 200, 301])
                self.assertEqual(self.api.calls.count(("terminate-job", 900, 125)), 1)
                self.assertEqual(self.scope.leaders[0].handle, 300)
                rows = self.scope.launches[0]["resourceCleanup"]
                self.assertEqual([row["phase"] for row in rows], ["launch-temporary"] * 5 + ["failed-return"] * 3)
                self.assertEqual(sum(row["status"] == "UNKNOWN" for row in rows), 1)
                self.scope.close()
                self.assertEqual(self.api.close_attempts[-2:], [300, 900])

    def test_first_and_second_crt_adoption_failure_keep_only_unadopted_raw_handles(self):
        for index in (0, 1):
            with self.subTest(index=index):
                self.reset_scope()
                self.fd_close.reset_mock()
                self.fileio.reset_mock()
                original = OSError("MODELED_CRT_ADOPTION_FAILURE_" + str(index))
                self.fake_crt.open_osfhandle.side_effect = [original] if index == 0 else [6000, original]
                with self.assertRaises(OSError) as raised:
                    self.scope.spawn([r"C:\tools\fixture.exe"], r"C:\work", {})
                self.assertIs(raised.exception, original)
                self.assertEqual([call.args[0] for call in self.fd_close.call_args_list], [] if index == 0 else [6000])
                self.assertEqual(self.fileio.call_count, index)
                self.assertEqual(self.api.close_attempts,
                                 ([1000, 1001, 1002, 1003, 200, 301, 300] if index == 0 else
                                  [1001, 1002, 1003, 200, 301, 300]))
                self.assertNotIn(("resume",), self.api.calls)
                self.assertEqual(self.api.calls.count(("terminate-job", 900, 125)), 1)
                self.scope.close()

    def test_first_and_second_nonowning_wrapper_failure_close_each_adopted_fd_once(self):
        for index in (0, 1):
            with self.subTest(index=index):
                self.reset_scope()
                self.fd_close.reset_mock()
                original = OSError("MODELED_NONOWNING_VIEW_FAILURE_" + str(index))
                view = io.BytesIO()
                with patch.object(io, "FileIO", side_effect=[original] if index == 0 else [view, original]), \
                        self.assertRaises(OSError) as raised:
                    self.scope.spawn([r"C:\tools\fixture.exe"], r"C:\work", {})
                self.assertIs(raised.exception, original)
                self.assertEqual([call.args[0] for call in self.fd_close.call_args_list], [6000] if index == 0 else [6000, 6002])
                self.assertNotIn(1000, self.api.close_attempts)
                if index:
                    self.assertNotIn(1002, self.api.close_attempts)
                    self.assertTrue(view.closed)
                else:
                    self.assertIn(1002, self.api.close_attempts)
                self.assertNotIn(("resume",), self.api.calls)
                self.scope.close()

    def test_reader_allocation_failure_happens_before_that_crt_transfer(self):
        reader_type = P._WindowsPipeReader
        for index in (0, 1):
            with self.subTest(index=index):
                self.reset_scope()
                self.fd_close.reset_mock()
                self.fake_crt.open_osfhandle.reset_mock()
                original = MemoryError("MODELED_READER_ALLOCATION_FAILURE")
                count = [0]

                def create(handle, name):
                    call = count[0]
                    count[0] += 1
                    if call == index:
                        raise original
                    return reader_type(handle, name)

                with patch.object(P, "_WindowsPipeReader", side_effect=create), self.assertRaises(MemoryError) as raised:
                    self.scope.spawn([r"C:\tools\fixture.exe"], r"C:\work", {})
                self.assertIs(raised.exception, original)
                self.assertEqual(self.fake_crt.open_osfhandle.call_count, index)
                self.assertEqual([call.args[0] for call in self.fd_close.call_args_list], [] if index == 0 else [6000])
                self.assertIn(1002 if index else 1000, self.api.close_attempts)
                self.scope.close()

    def test_view_and_descriptor_failures_are_independent_and_never_retried(self):
        for failures in (("view",), ("fd",), ("view", "fd"), ("cancel", "fd")):
            with self.subTest(failures=failures):
                view = Mock(read=Mock(return_value=b"binary\0\xff"))
                cancellation = KeyboardInterrupt("MODELED_VIEW_CANCEL")
                if "view" in failures:
                    view.close.side_effect = OSError("MODELED_VIEW_CLOSE")
                if "cancel" in failures:
                    view.close.side_effect = cancellation
                self.fd_close.reset_mock(side_effect=True)
                if "fd" in failures:
                    self.fd_close.side_effect = OSError("MODELED_FD_CLOSE")
                with patch.object(io, "FileIO", return_value=view):
                    reader = P._WindowsPipeReader(1000, "stdout")
                    reader.adopt()
                expected = KeyboardInterrupt if "cancel" in failures else P.OwnershipError
                with self.assertRaises(expected) as raised:
                    reader.close()
                error = raised.exception
                if "cancel" in failures:
                    self.assertIs(error, cancellation)
                self.assertTrue(reader.closed and reader.descriptor_adopted)
                self.assertIsNone(reader._fd)
                view.close.assert_called_once_with()
                self.fd_close.assert_called_once_with(6000)
                details = P.retirement_details(error)
                self.assertEqual(len(details["resources"]), len(failures))
                self.assertEqual(details["status"], "UNKNOWN")
                with self.assertRaises(expected) as repeated:
                    reader.close()
                self.assertIs(repeated.exception, error)
                self.fd_close.assert_called_once_with(6000)
                self.assertNotIn(1000, self.api.close_attempts)
                with self.assertRaises(P.OwnershipError):
                    reader.adopt()

    def test_failed_return_collects_multiple_pipe_errors_and_cannot_erase_unknown(self):
        self.api.resume_failure = True
        self.api.close_failures = {1001}
        self.fd_close.side_effect = OSError("MODELED_FD_CLOSE")
        views = [Mock(), Mock()]
        views[0].close.side_effect = OSError("MODELED_VIEW_CLOSE")
        with patch.object(io, "FileIO", side_effect=views), self.assertRaisesRegex(P.OwnershipError, "ResumeThread") as raised:
            self.scope.spawn([r"C:\tools\fixture.exe"], r"C:\work", {})
        rows = P.retirement_details(raised.exception)["resources"]
        self.assertTrue(any(row["resource"] == "stdout-crt-descriptor" for row in rows))
        self.assertTrue(any(row["resource"] == "stderr-crt-descriptor" for row in rows))
        self.assertEqual([call.args[0] for call in self.fd_close.call_args_list], [6000, 6002])
        self.assertTrue(all(view.close.call_count == 1 for view in views))
        self.scope.discover = Mock(return_value=[])
        self.assertEqual(self.scope.drain(), [])
        self.assertTrue(self.scope.description()["discoveryErrors"])
        self.scope.close()
        before = list(self.api.close_attempts)
        self.scope.close()
        self.assertEqual(self.api.close_attempts, before)
        self.assertNotIn(1000, before)
        self.assertNotIn(1002, before)

    def test_late_cancellation_preserves_object_cause_and_pending_reader_retirement(self):
        original = SystemExit("MODELED_FINALIZER_CANCEL")
        original.__cause__ = RuntimeError("MODELED_EXISTING_CAUSE")
        cause = original.__cause__
        self.api.DeleteProcThreadAttributeList = Mock(side_effect=original)
        self.api.close_failures = {1001, 301}
        with self.assertRaises(SystemExit) as raised:
            self.scope.spawn([r"C:\tools\fixture.exe"], r"C:\work", {})
        self.assertIs(raised.exception, original)
        self.assertIs(original.__cause__, cause)
        self.assertEqual(original.args, ("MODELED_FINALIZER_CANCEL",))
        self.assertEqual([call.args[0] for call in self.fd_close.call_args_list], [6000, 6002])
        self.assertEqual(self.api.calls.count(("terminate-job", 900, 125)), 1)
        self.assertEqual(len(P.retirement_details(original)["resources"]), 3)
        self.scope.close()

    def test_constructor_formatter_handles_args_independent_str_and_explicit_overflow(self):
        class Primary(OSError):
            def __str__(self):
                return "MODELED_FIXED_PRIMARY"

        primary = Primary(5, "MODELED_ORIGINAL_ARGS")
        args = primary.args
        primary.__cause__ = ValueError("MODELED_EXISTING_CAUSE")
        cause = primary.__cause__
        self.scope._retire([(str(index), Mock(side_effect=OSError("MODELED_CLOSE_" + str(index))))
                            for index in range(P.MAX_RETIREMENT_ERRORS + 2)], original=primary,
                           phase="scope-construction")
        self.assertEqual(primary.args, args)
        self.assertIs(primary.__cause__, cause)
        self.assertEqual(str(primary), "MODELED_FIXED_PRIMARY")
        details = P.retirement_details(primary)
        self.assertEqual(len(details["resources"]), P.MAX_RETIREMENT_ERRORS)
        self.assertEqual(details["omitted"], 2)
        self.assertIn("retirement UNKNOWN", P.format_ownership_error(primary))
        self.assertIn("2 further resource errors", P.format_ownership_error(primary))
        json.dumps(details)  # Structured carrier is serializable, not traceback/native objects.


class CallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="owned-output-model-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        for target, name in ((subprocess, "Popen"), (ctypes, "CDLL"), (ctypes, "WinDLL")):
            guard = patch.object(target, name, side_effect=AssertionError("MODELS MUST NOT EXECUTE NATIVE CALLS"),
                                 create=True)
            guard.start()
            self.addCleanup(guard.stop)

    def execute_model(self, scope_factory, tee_factory=None):
        root, state = self.base / "source", self.base / "state"
        root.mkdir()
        state.mkdir()
        (state / "evidence").mkdir()
        (state / "context.json").write_bytes(b"MODEL_CONTEXT_NOT_AN_ADMISSION")
        home = state / "gradle-home"
        home.mkdir()
        (home / "gradle.properties").write_bytes(b"MODEL_POLICY_NOT_GRADLE_INPUT")
        wrapper = root / ("gradlew.bat" if os.name == "nt" else "gradlew")
        wrapper.write_text("MODEL_NEVER_EXECUTED\n")
        source = {"MODEL_ONLY": True}
        context = {"id": "a" * 32, "root": str(root), "gradleHome": str(home), "source": source,
                   "gradlePropertiesSha256": A.digest((home / "gradle.properties").read_bytes())}
        identifier = "b" * 32
        args = SimpleNamespace(cwd=str(root), wrapper=str(wrapper), id=identifier, purpose="model", kind="command",
                               argv=["MODEL_NEVER_EXECUTED"], receipt=None, timeout=1, stop_timeout=1)
        self.receipt_path = state / "evidence" / identifier / "receipt.json"
        contexts = [patch.dict(os.environ, {P.STATE_ENV: str(state)}, clear=True),
                    patch.object(A, "context_at", return_value=(state, context)),
                    patch.object(A, "host_role", return_value="windows-x64"),
                    patch.object(A, "ownership_environment", return_value={}),
                    patch.object(A, "source_snapshot", return_value=source),
                    patch.object(A, "report_snapshot", return_value={}),
                    patch.object(A, "retain_reports", return_value={}),
                    patch.object(A, "cancellation_requested"),
                    patch.object(A, "cancel_nested_leaves"),
                    patch.object(A, "make_scope", side_effect=scope_factory),
                    patch.object(A, "LeafLock", return_value=Mock(held=True)),
                    patch.object(A, "wait_process", return_value=0),
                    patch.object(A.signal, "getsignal", return_value="MODEL_HANDLER"),
                    patch.object(A.signal, "signal"), patch.object(A.os, "fsync")]
        if tee_factory is not None:
            contexts.append(patch.object(A, "Tee", side_effect=tee_factory))
        for context in contexts:
            context.start()
        try:
            return A.execute(args)
        finally:
            for context in reversed(contexts):
                context.stop()

    def test_failed_scope_constructor_unknown_reaches_actual_executor_receipt(self):
        api = ModelWindows()
        original = OSError("MODELED_JOB_CONFIGURATION_FAILURE")
        api.CreateJobObjectW = Mock(return_value=900)
        api.SetInformationJobObject = Mock(side_effect=original)
        api.close_failures = {900}
        with patch.object(P, "WinApi", return_value=api):
            code = self.execute_model(P.WindowsScope)
        receipt = json.loads(self.receipt_path.read_text())
        self.assertEqual(code, 125)
        self.assertIsNone(receipt["productExitCode"])
        self.assertTrue(any("retirement UNKNOWN" in row and "job" in row for row in receipt["errors"]),
                        receipt["errors"])
        self.assertEqual(original.args, ("MODELED_JOB_CONFIGURATION_FAILURE",))

    def test_executor_constructor_cancellation_is_rethrown_after_failed_receipt(self):
        parent = self.base
        for kind in (KeyboardInterrupt, SystemExit):
            with self.subTest(kind=kind.__name__):
                self.base = parent / kind.__name__
                self.base.mkdir()
                api = ModelWindows()
                original = kind("MODELED_CONSTRUCTOR_CANCELLATION")
                api.CreateJobObjectW = Mock(return_value=900)
                api.SetInformationJobObject = Mock(side_effect=original)
                api.close_failures = {900}
                with patch.object(P, "WinApi", return_value=api), self.assertRaises(kind) as raised:
                    self.execute_model(P.WindowsScope)
                self.assertIs(raised.exception, original)
                receipt = json.loads(self.receipt_path.read_text())
                self.assertEqual(receipt["finalExitCode"], 125)
                self.assertTrue(any("retirement UNKNOWN" in row and "job" in row for row in receipt["errors"]))
                self.assertEqual(original.args, ("MODELED_CONSTRUCTOR_CANCELLATION",))
                self.assertEqual(api.close_attempts, [900])

    @staticmethod
    def model_scope():
        scope = Mock(launches=[])
        scope.discover.return_value = scope.drain.return_value = []
        scope.description.return_value = {"discoveryErrors": []}
        return scope

    @staticmethod
    def model_child(pid):
        child = Mock(pid=pid, stdout=Mock(), stderr=Mock())
        child.poll.return_value = child.wait.return_value = 0
        return child

    @staticmethod
    def model_tee(source, destination, live, errors, start=True):
        return Mock(source=source, finish=Mock(side_effect=source.close))

    def test_executor_partial_product_and_stop_tees_close_only_unclaimed_readers(self):
        parent = self.base
        for failed_index in (0, 1, 2, 3):
            with self.subTest(failed_index=failed_index):
                self.base = parent / str(failed_index)
                self.base.mkdir()
                scope = self.model_scope()
                product, stop = self.model_child(400), self.model_child(500)
                scope.spawn.side_effect = [product, stop]
                acquired, calls = [], []

                def tee(*args):
                    index = len(calls)
                    calls.append(args)
                    if index == failed_index:
                        raise OSError("MODELED_TEE_ALLOCATION_FAILURE")
                    stream = self.model_tee(*args)
                    acquired.append(stream)
                    return stream

                code = self.execute_model(lambda *args: scope, tee)
                receipt = json.loads(self.receipt_path.read_text())
                self.assertEqual(code, 125)
                self.assertTrue(any("MODELED_TEE_ALLOCATION_FAILURE" in row for row in receipt["errors"]))
                self.assertEqual(scope.spawn.call_count, 2)
                scope.close.assert_called_once()
                for child in (product, stop):
                    child.stdout.close.assert_called_once_with()
                    child.stderr.close.assert_called_once_with()
                for stream in acquired:
                    stream.finish.assert_called_once_with()

    def test_executor_successful_model_path_finishes_each_claimed_pipe_once(self):
        scope = self.model_scope()
        product, stop = self.model_child(400), self.model_child(500)
        scope.spawn.side_effect = [product, stop]
        code = self.execute_model(lambda *args: scope, self.model_tee)
        receipt = json.loads(self.receipt_path.read_text())
        self.assertEqual(code, 0)  # Model flow control only: no actual executable or gate ran.
        self.assertEqual(receipt["errors"], [])
        self.assertEqual(scope.spawn.call_count, 2)
        for child in (product, stop):
            child.stdout.close.assert_called_once_with()
            child.stderr.close.assert_called_once_with()
        scope.close.assert_called_once_with()

    def test_executor_unclaimed_pipe_unknown_and_cancellation_survive_other_finalizers(self):
        scope = self.model_scope()
        product, stop = self.model_child(400), self.model_child(500)
        scope.spawn.side_effect = [product, stop]
        original = KeyboardInterrupt("MODELED_UNCLAIMED_CLOSE_CANCELLATION")
        row = {"phase": "pipe-close", "resource": "stderr-crt-descriptor", "status": "UNKNOWN",
               "error": "OSError: MODELED_FD_CLOSE_FAILURE"}
        P._finish_retirement([(row, OSError("MODELED_FD_CLOSE_FAILURE"))], original)
        product.stderr.close.side_effect = original
        count = [0]

        def tee(*args):
            count[0] += 1
            if count[0] == 2:
                raise OSError("MODELED_SECOND_TEE_FAILURE")
            return self.model_tee(*args)

        with self.assertRaises(KeyboardInterrupt) as raised:
            self.execute_model(lambda *args: scope, tee)
        self.assertIs(raised.exception, original)
        receipt = json.loads(self.receipt_path.read_text())
        self.assertEqual(receipt["finalExitCode"], 125)
        self.assertTrue(any("stderr-crt-descriptor" in error for error in receipt["errors"]))
        stop.stdout.close.assert_called_once_with()
        stop.stderr.close.assert_called_once_with()
        scope.close.assert_called_once_with()

    def test_real_tee_finalizer_retains_descriptor_unknown_and_attempts_every_output_action(self):
        reader = P._WindowsPipeReader(1000, "stdout")
        reader._fd, reader._view = 6000, io.BytesIO()
        tee = A.Tee.__new__(A.Tee)
        tee.source, tee.live, tee.errors = reader, None, []
        tee._resources_attempted, tee._complete = False, Mock()
        tee.output = Mock()
        tee.output.fileno.return_value = 42
        tee.output.flush.side_effect = OSError("MODELED_OUTPUT_FLUSH_FAILURE")
        tee.output.close.side_effect = OSError("MODELED_OUTPUT_CLOSE_FAILURE")
        with patch.object(P.os, "close", side_effect=OSError("MODELED_DESCRIPTOR_FAILURE")) as close, \
                patch.object(A.os, "fsync", side_effect=OSError("MODELED_OUTPUT_SYNC_FAILURE")) as sync:
            tee._copy()  # The real callable, synchronous here; never a thread or child process.
        close.assert_called_once_with(6000)
        sync.assert_called_once_with(42)
        tee.output.flush.assert_called_once_with()
        tee.output.close.assert_called_once_with()
        self.assertEqual(len(tee.errors), 4)
        self.assertIn("stdout-crt-descriptor", tee.errors[0])
        self.assertIn("retirement UNKNOWN", tee.errors[0])
        self.assertTrue(reader.closed)

    def test_real_tee_read_and_close_cancellations_do_not_skip_other_finalizers(self):
        for where in ("read", "close"):
            with self.subTest(where=where):
                original = KeyboardInterrupt("MODELED_TEE_" + where)
                source, output = Mock(), Mock()
                source.read.return_value = b""
                getattr(source, where).side_effect = original
                tee = A.Tee.__new__(A.Tee)
                tee.source, tee.output, tee.live, tee.errors = source, output, None, []
                tee._resources_attempted, tee._complete = False, Mock()
                with patch.object(A.os, "fsync") as sync, self.assertRaises(KeyboardInterrupt) as raised:
                    tee._copy()
                self.assertIs(raised.exception, original)
                source.close.assert_called_once_with()
                output.flush.assert_called_once_with()
                output.close.assert_called_once_with()
                sync.assert_called_once_with(output.fileno.return_value)
                self.assertTrue(any("MODELED_TEE_" + where in error for error in tee.errors))

    def test_real_tee_captures_owned_reader_error_instead_of_unhandled_thread_error(self):
        source, output = Mock(), Mock()
        original = P.OwnershipError("MODELED_OWNED_READER_FAILURE")
        source.read.side_effect = original
        tee = A.Tee.__new__(A.Tee)
        tee.source, tee.output, tee.live, tee.errors = source, output, None, []
        tee._resources_attempted, tee._complete = False, Mock()
        with patch.object(A.os, "fsync"):
            tee._copy()
        self.assertTrue(any("MODELED_OWNED_READER_FAILURE" in error for error in tee.errors))
        source.close.assert_called_once_with()
        output.close.assert_called_once_with()

    def controller_model(self):
        controller = C.Controller.__new__(C.Controller)
        controller.base = self.base
        controller.root = self.base / "campaign-source"
        controller.root.mkdir()
        controller.public = self.base / "public"
        for name in ("admission", "current", "preimage"):
            (controller.public / name).mkdir(parents=True)
        controller.raw = self.base / "raw"
        controller.raw.mkdir()
        controller.active_public = controller.public / "admission"
        controller.scope = self.model_scope()
        controller.state = self.base / "controller-state"
        controller.state.mkdir()
        controller.identity = {"sourceSha": "a" * 40, "scope": "MODEL_ONLY_NOT_HOSTED"}
        controller.counter, controller.safe = 0, False
        controller.cancelled, controller.cases, controller.handlers = [], [], {}
        controller.env = {}
        controller.deadline = controller.final_deadline = C.time.monotonic() + 30
        controller.resources = Mock(return_value={})
        return controller

    def test_windows_command_retains_unclaimed_descriptor_close_unknown_in_actual_record(self):
        controller = self.controller_model()
        child = self.model_child(400)
        controller.scope.spawn.return_value = child
        reader = P._WindowsPipeReader(1002, "stderr")
        reader._fd, reader._view = 6002, io.BytesIO()
        child.stderr = reader
        first = self.model_tee(child.stdout, None, None, [])
        with patch.object(C.audit, "Tee", side_effect=[first, OSError("MODELED_SECOND_TEE_FAILURE")]), \
                patch.object(P.os, "close", side_effect=OSError("MODELED_DESCRIPTOR_FAILURE")) as close, \
                self.assertRaises(C.CommandFailure) as raised:
            controller.command(["MODEL_NEVER_EXECUTED"], controller.root, {}, "model")
        record = json.loads((raised.exception.capture / "command.json").read_text())
        self.assertTrue(any("stderr-crt-descriptor" in error for error in record["errors"]))
        self.assertTrue(any("retirement UNKNOWN" in error for error in record["errors"]))
        close.assert_called_once_with(6002)
        first.finish.assert_called_once_with()
        child.stdout.close.assert_called_once_with()

    def test_windows_command_cancellation_retains_record_and_rethrows_same_object(self):
        controller = self.controller_model()
        original = SystemExit("MODELED_WINDOWS_COMMAND_CANCELLATION")
        controller.scope.spawn.side_effect = original
        with self.assertRaises(SystemExit) as raised:
            controller.command(["MODEL_NEVER_EXECUTED"], controller.root, {}, "model")
        self.assertIs(raised.exception, original)
        record = json.loads((controller.raw / "1-model/command.json").read_text())
        self.assertTrue(record["cancelled"])
        self.assertTrue(any("MODELED_WINDOWS_COMMAND_CANCELLATION" in error for error in record["errors"]))
        controller.scope.drain.assert_called_once()

    def test_windows_main_captures_real_constructor_unknown_before_no_controller_is_returned(self):
        api = ModelWindows()
        original = OSError("MODELED_OUTER_JOB_CONFIGURATION_FAILURE")
        api.CreateJobObjectW = Mock(return_value=900)
        api.SetInformationJobObject = Mock(side_effect=original)
        api.close_failures = {900}
        identity = {"sourceSha": "a" * 40, "runId": "MODEL", "runAttempt": "1"}
        stderr = io.StringIO()
        env = {"GITHUB_WORKSPACE": str(ROOT), "GITHUB_EVENT_PATH": str(self.base / "MODELED_EVENT"),
               "RUNNER_TEMP": str(self.base)}
        with patch.dict(os.environ, env, clear=True), \
                patch.object(C.argparse.ArgumentParser, "parse_args", return_value=SimpleNamespace(action="run")), \
                patch.object(C.audit, "source_snapshot", return_value={}), \
                patch.object(C, "read_json", return_value={}), patch.object(C, "dispatch_identity", return_value=identity), \
                patch.object(C, "regular", return_value=b"MODEL_BLOB"), \
                patch.object(C.audit, "git", return_value=b"MODEL_BLOB"), \
                patch.object(P, "host_role", return_value="windows-x64"), \
                patch.object(P, "ownership_environment", return_value={"GRADLE_USER_HOME": str(self.base / "unused")}), \
                patch.object(P, "make_scope", side_effect=P.WindowsScope), patch.object(P, "WinApi", return_value=api), \
                patch.object(sys, "stderr", stderr), patch.object(C.shutil, "rmtree") as dispose:
            code = C.main()
        self.assertEqual(code, 125)
        self.assertIn("MODELED_OUTER_JOB_CONFIGURATION_FAILURE", stderr.getvalue())
        self.assertIn("retirement UNKNOWN (scope-construction/job)", stderr.getvalue())
        self.assertIn("MODELED_CLOSE_FAILURE_900", stderr.getvalue())
        self.assertEqual(api.close_attempts, [900])
        self.assertEqual(original.args, ("MODELED_OUTER_JOB_CONFIGURATION_FAILURE",))
        dispose.assert_not_called()

    def test_windows_case_constructor_failure_reaches_run_record_and_never_disposes_case(self):
        controller = self.controller_model()
        source = {"files": {}, "source": {"MODEL_ONLY": True}}
        controller.admit_tools = Mock()
        controller.materialize = Mock()
        controller.source = Mock(return_value=source)
        controller.git = Mock(return_value=b"MODEL_BLOB")
        controller.seal_results = Mock()
        context = {"id": "c" * 32, "gradleHome": str(self.base / "current/state/gradle-home")}
        state = self.base / "current/state"

        def init(*args, **kwargs):
            for name in ("gradle-home", "evidence", "cancellations"):
                (state / name).mkdir(parents=True, exist_ok=True)
            (state / "context.json").write_bytes(b"MODEL_CONTEXT")
            (state / "gradle-home/gradle.properties").write_bytes(b"MODEL_POLICY")
            return 0, self.base / "MODEL_UNUSED_OUTPUT"

        controller.command = Mock(side_effect=init)
        api = ModelWindows()
        original = OSError("MODELED_CASE_JOB_CONFIGURATION_FAILURE")
        api.CreateJobObjectW = Mock(return_value=900)
        api.SetInformationJobObject = Mock(side_effect=original)
        api.close_failures = {900}
        with patch.object(C, "transform"), patch.object(C, "copy_public"), \
                patch.object(C, "regular", return_value=b"MODEL_BLOB"), patch.object(C, "prepared_context"), \
                patch.object(C.audit, "context_at", return_value=(state, context)), \
                patch.object(P, "ownership_environment", return_value={}), \
                patch.object(P, "make_scope", side_effect=P.WindowsScope), patch.object(P, "WinApi", return_value=api), \
                patch.object(C.signal, "getsignal", return_value="MODEL_HANDLER"), patch.object(C.signal, "signal"), \
                patch.object(C.shutil, "rmtree") as dispose:
            code = controller.run()
        self.assertEqual(code, 125)
        error_log = (controller.public / "admission/controller-error.txt").read_text()
        self.assertIn("MODELED_CASE_JOB_CONFIGURATION_FAILURE", error_log)
        self.assertIn("retirement UNKNOWN (scope-construction/job)", error_log)
        self.assertEqual(len(controller.cases), 1)
        case = controller.cases[0]
        self.assertIsNone(case["scope"])
        self.assertFalse(case["safe"])
        self.assertTrue(case["root"].is_dir())
        retired = json.loads((case["public"] / "retirement.json").read_text())
        self.assertFalse(retired["complete"])
        self.assertEqual(retired["removed"], [])
        dispose.assert_not_called()
        self.assertFalse(controller.safe)

    def test_actual_tee_constructor_failure_retires_its_allocated_output(self):
        scope = self.model_scope()
        product, stop = self.model_child(400), self.model_child(500)
        scope.spawn.side_effect = [product, stop]
        output, real_tee, calls = Mock(), A.Tee, []
        original = OSError("MODELED_THREAD_ALLOCATION_FAILURE")

        def tee(*args):
            calls.append(args)
            if len(calls) == 1:
                with patch.object(A, "new_file", return_value=output), \
                        patch.object(A.threading, "Thread", side_effect=original):
                    return real_tee(*args)
            return self.model_tee(*args)

        self.assertEqual(self.execute_model(lambda *args: scope, tee), 125)
        receipt = json.loads(self.receipt_path.read_text())
        self.assertTrue(any("MODELED_THREAD_ALLOCATION_FAILURE" in row for row in receipt["errors"]))
        output.close.assert_called_once_with()
        product.stdout.close.assert_called_once_with()
        product.stderr.close.assert_called_once_with()

    def test_uncertain_thread_start_keeps_registered_streams_without_racing_close(self):
        scope = self.model_scope()
        product, stop = self.model_child(400), self.model_child(500)
        scope.spawn.side_effect = [product, stop]
        original = KeyboardInterrupt("MODELED_START_MAY_HAVE_ENTERED")
        thread, completion, output = Mock(), Mock(), Mock()
        thread.start.side_effect = original
        thread.is_alive.return_value = True
        completion.wait.return_value = False
        real_tee, calls = A.Tee, []

        def tee(*args):
            calls.append(args)
            if len(calls) == 1:
                with patch.object(A, "new_file", return_value=output), \
                        patch.object(A.threading, "Thread", return_value=thread), \
                        patch.object(A.threading, "Event", return_value=completion):
                    return real_tee(*args)
            return self.model_tee(*args)

        with self.assertRaises(KeyboardInterrupt) as raised:
            self.execute_model(lambda *args: scope, tee)
        self.assertIs(raised.exception, original)
        product.stdout.close.assert_not_called()
        output.close.assert_not_called()
        product.stderr.close.assert_called_once_with()
        scope.close.assert_called_once_with()
        receipt = json.loads(self.receipt_path.read_text())
        self.assertEqual(receipt["finalExitCode"], 125)
        self.assertTrue(any("UNKNOWN" in row and "stream" in row.lower() for row in receipt["errors"]))

    def test_thread_start_cancellation_after_worker_completion_never_double_closes(self):
        scope = self.model_scope()
        product, stop = self.model_child(400), self.model_child(500)
        scope.spawn.side_effect = [product, stop]
        product.stdout.read.return_value = b""
        original = SystemExit("MODELED_START_CANCEL_AFTER_COMPLETION")
        output, real_tee, calls = Mock(), A.Tee, []
        thread = Mock()
        thread.is_alive.return_value = False

        def make_thread(*, target, **kwargs):
            def start():
                target()  # Synchronous model of thread entry/completion; no thread starts.
                raise original
            thread.start.side_effect = start
            return thread

        def tee(*args):
            calls.append(args)
            if len(calls) == 1:
                with patch.object(A, "new_file", return_value=output), \
                        patch.object(A.threading, "Thread", side_effect=make_thread):
                    return real_tee(*args)
            return self.model_tee(*args)

        with self.assertRaises(SystemExit) as raised:
            self.execute_model(lambda *args: scope, tee)
        self.assertIs(raised.exception, original)
        product.stdout.close.assert_called_once_with()
        output.close.assert_called_once_with()
        product.stderr.close.assert_called_once_with()
        self.assertEqual(json.loads(self.receipt_path.read_text())["finalExitCode"], 125)

    def test_actual_case_close_cancellation_still_finalizes_outer_and_records_unknown(self):
        controller = self.controller_model()
        original = KeyboardInterrupt("MODELED_CASE_HANDLE_CLOSE_CANCEL")
        api = ModelWindows()

        def close(handle):
            if handle:
                api.close_attempts.append(handle)
                if handle == 300:
                    raise original
                api.closed.append(handle)

        api.close = close
        scope = object.__new__(P.WindowsScope)
        scope.api, scope.job, scope.job_id, scope.invocation = api, 900, "a" * 32, "b" * 32
        scope.leaders = [P.WindowsProcess(api, 300, 400, None, None)]
        scope.launches, scope.known, scope.discovery_errors = [], {}, set()
        scope.drain = Mock(return_value=[])
        scope.description = Mock(return_value={"discoveryErrors": ["MODELED_ADMISSION_FAILURE"]})
        case = {"retirementAttempted": False, "name": "current", "public": controller.public / "current",
                "state": self.base / "case-state", "scope": scope, "roots": {}, "initialized": False,
                "started": False, "safe": False, "leaves": []}
        controller.cases = [case]
        errors = []
        with self.assertRaises(KeyboardInterrupt) as raised:
            controller.finalize_resources(None, errors)
        self.assertIs(raised.exception, original)
        self.assertEqual(api.close_attempts, [300, 900])
        controller.scope.drain.assert_called_once_with()
        controller.scope.close.assert_called_once_with()
        case_record = json.loads((case["public"] / "retirement.json").read_text())
        outer_record = json.loads((controller.public / "admission/controller-retirement.json").read_text())
        self.assertFalse(case_record["complete"])
        self.assertFalse(outer_record["complete"])
        self.assertTrue(any("retirement UNKNOWN" in row for row in case_record["errors"]))
        self.assertTrue(any("MODELED_CASE_HANDLE_CLOSE_CANCEL" in row for row in errors))

    def test_run_preserves_primary_cancellation_through_failed_retirement_receipt(self):
        controller = self.controller_model()
        original = SystemExit("MODELED_PRIMARY_CANCEL")
        secondary = OSError("MODELED_FINAL_RECEIPT_FAILURE")
        controller.admit_tools = Mock(side_effect=original)
        controller.seal_results = Mock()
        controller.retire_command_copies = Mock(return_value={"MODEL_ONLY": True})
        real_write = C.new_json

        def write(path, value):
            if path.name == "controller-retirement.json":
                raise secondary
            return real_write(path, value)

        with patch.object(C, "new_json", side_effect=write), \
                patch.object(C.signal, "getsignal", return_value="MODEL_HANDLER"), \
                patch.object(C.signal, "signal") as handlers, self.assertRaises(SystemExit) as raised:
            controller.run()
        self.assertIs(raised.exception, original)
        controller.scope.drain.assert_called_once_with()
        controller.scope.close.assert_called_once_with()
        controller.seal_results.assert_called_once()
        errors = controller.seal_results.call_args.args[1]
        self.assertTrue(any("MODELED_FINAL_RECEIPT_FAILURE" in row for row in errors))
        self.assertTrue(all(call.args[1] == "MODEL_HANDLER" for call in handlers.call_args_list[-len(controller.handlers):]))
        self.assertIn("MODELED_PRIMARY_CANCEL", (controller.public / "admission/controller-error.txt").read_text())

    def test_constructor_primary_survives_all_output_finalizer_failures(self):
        primary = SystemExit("MODEL_THREAD_ALLOCATION_CANCEL")
        source, output, errors = Mock(), Mock(), []
        output.flush.side_effect = OSError("MODEL_FLUSH_FAILURE")
        output.close.side_effect = KeyboardInterrupt("MODEL_SECONDARY_CLOSE_CANCEL")
        with patch.object(A, "new_file", return_value=output), \
                patch.object(A.threading, "Thread", side_effect=primary), \
                patch.object(A.os, "fsync", side_effect=OSError("MODEL_SYNC_FAILURE")), \
                self.assertRaises(SystemExit) as raised:
            A.Tee(source, self.base / "model.log", None, errors, False)
        self.assertIs(raised.exception, primary)
        source.close.assert_not_called()  # No returned Tee acquired this borrowed pipe.
        output.flush.assert_called_once_with()
        output.close.assert_called_once_with()
        self.assertEqual(len(errors), 3)
        self.assertTrue(any("UNKNOWN" in row and "SECONDARY_CLOSE_CANCEL" in row for row in errors))

    def test_deferred_unstarted_tee_retires_once_without_starting_a_worker(self):
        source, output, thread, errors = Mock(), Mock(), Mock(), []
        with patch.object(A, "new_file", return_value=output), patch.object(A.threading, "Thread", return_value=thread), \
                patch.object(A.os, "fsync") as sync:
            tee = A.Tee(source, self.base / "model.log", None, errors, False)
            tee.finish()
            tee.finish()
        thread.start.assert_not_called()
        source.close.assert_called_once_with()
        output.close.assert_called_once_with()
        sync.assert_called_once_with(output.fileno.return_value)
        self.assertEqual(errors, [])
        with self.assertRaises(A.AuditError):
            tee.start()

    def test_eager_default_constructor_retains_pending_owner_on_uncertain_start(self):
        source, output, thread, completion, errors = Mock(), Mock(), Mock(), Mock(), []
        original = KeyboardInterrupt("MODEL_EAGER_START_CANCEL")
        thread.start.side_effect = original
        completion.wait.return_value = False
        with patch.object(A, "new_file", return_value=output), patch.object(A.threading, "Thread", return_value=thread), \
                patch.object(A.threading, "Event", return_value=completion), self.assertRaises(KeyboardInterrupt) as raised:
            A.Tee(source, self.base / "model.log", None, errors)
        self.assertIs(raised.exception, original)
        tee = original._p2pkit_pending_tee
        self.assertIs(tee.source, source)
        self.assertIs(tee.thread, thread)
        tee.finish()  # Already attempted; no deadline widening or second close.
        completion.wait.assert_called_once_with(timeout=3)
        source.close.assert_not_called()
        output.close.assert_not_called()
        self.assertTrue(any("retirement UNKNOWN" in row for row in errors))

    def test_eager_default_success_preserves_exact_bytes_with_synchronous_worker_model(self):
        source, live = io.BytesIO(b"prefix\x00\xff\r\n"), io.BytesIO()
        destination, thread, errors = self.base / "model.log", Mock(), []
        thread.is_alive.return_value = False

        def make_thread(*, target, **kwargs):
            thread.start.side_effect = target  # Runs synchronously; no thread/native launch.
            return thread

        with patch.object(A.threading, "Thread", side_effect=make_thread):
            tee = A.Tee(source, destination, live, errors)
            tee.finish()
        self.assertEqual(destination.read_bytes(), b"prefix\x00\xff\r\n")
        self.assertEqual(live.getvalue(), destination.read_bytes())
        self.assertTrue(source.closed and tee.output.closed)
        self.assertEqual(errors, [])

    def test_windows_command_registers_actual_tee_before_uncertain_start(self):
        controller, child = self.controller_model(), self.model_child(400)
        controller.scope.spawn.return_value = child
        original, output, thread, completion = SystemExit("MODEL_WINDOWS_TEE_START"), Mock(), Mock(), Mock()
        thread.start.side_effect = original
        completion.wait.return_value = False
        with patch.object(C.audit, "Tee", A.Tee), patch.object(A, "new_file", return_value=output), \
                patch.object(A.threading, "Thread", return_value=thread), \
                patch.object(A.threading, "Event", return_value=completion), self.assertRaises(SystemExit) as raised:
            controller.command(["MODEL_NEVER_EXECUTED"], controller.root, {}, "model")
        self.assertIs(raised.exception, original)
        child.stdout.close.assert_not_called()
        child.stderr.close.assert_called_once_with()
        output.close.assert_not_called()
        record = json.loads((controller.raw / "1-model/command.json").read_text())
        self.assertTrue(record["cancelled"])
        self.assertTrue(any("retirement UNKNOWN" in row for row in record["errors"]))

    def disposal_case(self, controller, name="current"):
        case = controller.allocate(name)
        state = case["state"]
        state.mkdir()
        for name in ("gradle-home", "fixtures", "konan", "android-user"):
            path = state / name
            path.mkdir()
            info = path.lstat()
            case["roots"][str(path)] = {"device": info.st_dev, "inode": info.st_ino}
        (case["root"] / "sentinel").write_bytes(b"MODEL_OWNED_SOURCE_DO_NOT_DISPOSE_ON_UNKNOWN")
        (state / "context.json").write_bytes(b"MODEL_CONTEXT")
        case.update(initialized=True, context={"expectedCommit": "a" * 40},
                    contextHash=C.digest((state / "context.json").read_bytes()), before={"MODEL_SOURCE": True},
                    scope=self.model_scope())
        controller.source = Mock(return_value=case["before"])
        return case

    def test_actual_case_close_failure_preserves_all_synthetic_disposal_roots(self):
        parent = self.base
        for kind in (OSError, KeyboardInterrupt, SystemExit):
            with self.subTest(kind=kind.__name__):
                self.base = parent / kind.__name__
                self.base.mkdir()
                controller = self.controller_model()
                case = self.disposal_case(controller)
                original = kind("MODEL_CASE_CLOSE_UNKNOWN")
                case["scope"].close.side_effect = original
                with patch.object(C.audit, "LeafLock", return_value=Mock()), \
                        patch.object(C, "retain_before_disposal", return_value={}) as retain, \
                        patch.object(C, "verify_before_disposal"), \
                        patch.object(C.shutil, "rmtree", wraps=C.shutil.rmtree) as remove, \
                        self.assertRaises((C.audit.AuditError, kind)) as raised:
                    controller.retire(case)
                if kind is not OSError:
                    self.assertIs(raised.exception, original)
                remove.assert_not_called()
                retain.assert_not_called()
                case["scope"].close.assert_called_once_with()
                self.assertTrue(all(Path(root).is_dir() for root in case["roots"]))
                self.assertEqual((case["root"] / "sentinel").read_bytes(), b"MODEL_OWNED_SOURCE_DO_NOT_DISPOSE_ON_UNKNOWN")
                record = json.loads((case["public"] / "retirement.json").read_text())
                self.assertFalse(record["complete"])
                self.assertEqual(record["removed"], [])

    def test_successful_actual_case_closes_scope_before_disposing_roots(self):
        controller = self.controller_model()
        case, order = self.disposal_case(controller), []
        case["scope"].close.side_effect = lambda: order.append("close")
        remove = C.shutil.rmtree

        def dispose(path, **kwargs):
            order.append("dispose")
            return remove(path, **kwargs)

        with patch.object(C.audit, "LeafLock", return_value=Mock()), \
                patch.object(C, "retain_before_disposal", return_value={}), patch.object(C, "verify_before_disposal"), \
                patch.object(C.shutil, "rmtree", side_effect=dispose):
            controller.retire(case)
        self.assertEqual(order, ["close", *(["dispose"] * 5)])
        self.assertTrue(case["safe"])
        self.assertTrue(json.loads((case["public"] / "retirement.json").read_text())["complete"])

    def test_case_cancellation_still_attempts_sibling_case_and_outer_receipts(self):
        controller = self.controller_model()
        first = self.disposal_case(controller, "current")
        second = self.disposal_case(controller, "preimage")
        first["scope"].close.side_effect = SystemExit("MODEL_FIRST_CASE_CLOSE_CANCEL")
        second["initialized"] = False  # Partial allocation must remain, not simulate native success.
        errors = []
        with self.assertRaises(SystemExit) as raised:
            controller.finalize_resources(None, errors)
        self.assertIs(raised.exception, first["scope"].close.side_effect)
        for case in (first, second):
            case["scope"].close.assert_called_once_with()
            self.assertFalse(json.loads((case["public"] / "retirement.json").read_text())["complete"])
            self.assertTrue(case["root"].is_dir())
        controller.scope.drain.assert_called_once_with()
        controller.scope.close.assert_called_once_with()
        self.assertFalse(json.loads((controller.public / "admission/controller-retirement.json").read_text())["complete"])

    def test_run_primary_cancellation_wins_over_receipt_handler_and_seal_failures(self):
        parent = self.base
        for kind, other in ((KeyboardInterrupt, SystemExit), (SystemExit, KeyboardInterrupt)):
            with self.subTest(kind=kind.__name__):
                self.base = parent / kind.__name__
                self.base.mkdir()
                controller = self.controller_model()
                primary = kind("MODEL_PRIMARY")
                controller.admit_tools = Mock(side_effect=primary)
                controller.retire_command_copies = Mock(return_value={})
                controller.seal_results = Mock(side_effect=other("MODEL_SEAL_CANCEL"))
                real_write, restores = C.new_json, []

                def write(path, value):
                    if path.name == "controller-retirement.json":
                        raise OSError("MODEL_RECEIPT_ERROR")
                    return real_write(path, value)

                def handler(number, value):
                    if value == "MODEL_ORIGINAL_HANDLER":
                        restores.append(number)
                        if len(restores) == 1:
                            raise other("MODEL_HANDLER_CANCEL")

                with patch.object(C, "new_json", side_effect=write), \
                        patch.object(C.signal, "getsignal", return_value="MODEL_ORIGINAL_HANDLER"), \
                        patch.object(C.signal, "signal", side_effect=handler), self.assertRaises(kind) as raised:
                    controller.run()
                self.assertIs(raised.exception, primary)
                self.assertEqual(set(restores), set(controller.handlers))
                controller.scope.close.assert_called_once_with()
                controller.seal_results.assert_called_once()
                detail = P.format_ownership_error(primary)
                for text in ("MODEL_RECEIPT_ERROR", "MODEL_HANDLER_CANCEL", "MODEL_SEAL_CANCEL"):
                    self.assertIn(text, detail)

    def test_failed_case_seal_still_attempts_other_seals_but_never_announces_ready(self):
        controller = self.controller_model()
        controller.safe = True
        output = self.base / "model-github-output"
        output.write_bytes(b"")
        original, attempts = KeyboardInterrupt("MODEL_SEAL_CANCEL"), []

        def seal(path, identity, name):
            attempts.append(name)
            if name == "current":
                raise original

        outcomes = {name: {"verdict": "NOT_EXECUTED"} for name in ("current", "preimage")}
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}), patch.object(C, "seal_public", side_effect=seal), \
                patch.object(C, "verify_public") as verify, self.assertRaises(KeyboardInterrupt) as raised:
            controller.seal_results(outcomes, [])
        self.assertIs(raised.exception, original)
        self.assertEqual(attempts, ["current", "preimage", "admission"])
        self.assertEqual(verify.call_count, 3)
        self.assertEqual(output.read_bytes(), b"")
        record = json.loads((controller.public / "admission/outcome.json").read_text())
        self.assertEqual(record["verdict"], "NOT_ACCEPTED")
        self.assertTrue(any("MODEL_SEAL_CANCEL" in row for row in record["errors"]))

    def test_receipt_cancellation_does_not_skip_lease_or_sibling_receipt_close(self):
        primary = SystemExit("MODEL_RECEIPT_FLUSH_CANCEL")
        optional, canonical, lock = Mock(), Mock(), Mock()
        optional.flush.side_effect = primary
        lock.close.side_effect = KeyboardInterrupt("MODEL_LEASE_CLOSE_CANCEL")
        receipt = {"finalExitCode": 0, "errors": []}
        with patch.object(A, "new_file", return_value=canonical), \
                patch.object(A.os, "fstat", return_value=SimpleNamespace(st_dev=1, st_ino=2)), \
                patch.object(A.os, "fsync"), self.assertRaises(SystemExit) as raised:
            A.finalize_receipts(receipt, self.base, optional, self.base / "optional.json", lock)
        self.assertIs(raised.exception, primary)
        optional.close.assert_called_once_with()
        canonical.close.assert_called_once_with()
        lock.close.assert_called_once_with()
        self.assertEqual(receipt["finalExitCode"], 125)
        self.assertTrue(any("MODEL_LEASE_CLOSE_CANCEL" in row for row in receipt["errors"]))

    def test_executor_start_cancellation_survives_secondary_terminal_receipt_failure(self):
        scope = self.model_scope()
        product, stop = self.model_child(400), self.model_child(500)
        scope.spawn.side_effect = [product, stop]
        primary, secondary, count = SystemExit("MODEL_START_PRIMARY"), KeyboardInterrupt("MODEL_RECEIPT_SECONDARY"), []

        def tee(*args):
            stream = self.model_tee(*args)
            if not count:
                stream.start.side_effect = primary
            count.append(stream)
            return stream

        with patch.object(A, "finalize_receipts", side_effect=secondary) as final, self.assertRaises(SystemExit) as raised:
            self.execute_model(lambda *args: scope, tee)
        self.assertIs(raised.exception, primary)
        scope.close.assert_called_once_with()
        self.assertFalse(self.receipt_path.exists())  # The modeled receipt writer failed; no retention claim.
        record = final.call_args.args[0]
        self.assertEqual(record["finalExitCode"], 125)
        self.assertTrue(any("MODEL_RECEIPT_SECONDARY" in row for row in record["errors"]))
        for child in (product, stop):
            child.stdout.close.assert_called_once_with()
            child.stderr.close.assert_called_once_with()

    def test_fallback_stop_cancellation_preserves_primary_after_lease_close_and_receipt(self):
        controller = self.controller_model()
        case = self.disposal_case(controller)
        case["env"] = {}
        case["context"].update(gradleHome=str(case["state"] / "gradle-home"), id="a" * 32)
        wrapper = case["root"] / "gradlew.bat"
        wrapper.write_bytes(b"MODEL_WRAPPER_NEVER_EXECUTED")
        case["before"]["files"] = {"gradlew.bat": {"sha256": C.digest(wrapper.read_bytes())}}
        primary, lock = KeyboardInterrupt("MODEL_FALLBACK_CANCEL"), Mock()
        controller.command = Mock(side_effect=primary)
        lock.close.side_effect = SystemExit("MODEL_FALLBACK_LEASE_CLOSE")
        with patch.object(C.audit, "context_at", return_value=(case["state"], case["context"])), \
                patch.object(C.audit, "LeafLock", return_value=lock), self.assertRaises(KeyboardInterrupt) as raised:
            controller.fallback_stop(case)
        self.assertIs(raised.exception, primary)
        lock.close.assert_called_once_with()
        record = json.loads((case["public"] / "fallback-stop.json").read_text())
        self.assertIsNone(record["exitCode"])
        self.assertTrue(any("MODEL_FALLBACK_CANCEL" in row for row in record["errors"]))
        self.assertTrue(any("MODEL_FALLBACK_LEASE_CLOSE" in row for row in record["errors"]))

    def test_case_scope_closes_after_fallback_attempt_and_post_fallback_drain(self):
        controller = self.controller_model()
        case, order = self.disposal_case(controller), []
        case.update(started=True, leaves=[{"valid": False}])
        case["scope"].drain.side_effect = lambda: order.append("drain") or []
        case["scope"].close.side_effect = lambda: order.append("close")
        controller.fallback_stop = Mock(side_effect=lambda unused: order.append("fallback") or {"errors": []})
        with self.assertRaises(C.audit.AuditError):
            controller.retire(case)  # Unfinalized original leaf still prohibits disposal.
        self.assertEqual(order, ["drain", "fallback", "drain", "close"])
        self.assertTrue(all(Path(root).is_dir() for root in case["roots"]))

    def hosted_command_model(self):
        commands = self.base / "commands"
        commands.mkdir()
        runtime = SimpleNamespace(root=self.base, state=self.base / "state", home=self.base / "home", commands=commands,
            job="a" * 32, check=Mock(), env={}, api=SimpleNamespace(Tee=A.Tee), fail=Mock(),
            stream_budget=H.StreamBudget(4096), final_stream_budget=H.StreamBudget(4096))
        command = H.Command(runtime, "model", ["MODEL_NEVER_EXECUTED"], invocation="b" * 32)
        scope, child = self.model_scope(), self.model_child(400)
        scope.name, scope.baseline, scope.leaders = "darwin-libproc-audit-token", set(), [child]
        scope.spawn.return_value = child
        return command, scope, child

    def test_hosted_actual_capture_keeps_uncertain_start_pipe_owned_and_closes_unclaimed_sibling(self):
        command, scope, child = self.hosted_command_model()
        original, output, thread, completion = SystemExit("MODEL_HOSTED_START_CANCEL"), Mock(), Mock(), Mock()
        thread.start.side_effect = original
        completion.wait.return_value = False
        with patch.object(P, "make_scope", return_value=scope), patch.object(P, "ownership_environment", return_value={}), \
                patch.object(A, "new_file", return_value=output), patch.object(A.threading, "Thread", return_value=thread), \
                patch.object(A.threading, "Event", return_value=completion), self.assertRaises(SystemExit) as raised:
            try:
                command.start()
            finally:
                command.drain("model-final")
                command.close()
        self.assertIs(raised.exception, original)
        child.stdout.close.assert_not_called()
        child.stderr.close.assert_called_once_with()
        output.close.assert_not_called()
        scope.close.assert_called_once_with()
        record = json.loads((command.directory / "command.json").read_text())
        self.assertTrue(any("retirement UNKNOWN" in row for row in record["errors"]))

    def test_hosted_spawn_primary_survives_real_tee_constructor_and_native_close_failures(self):
        command, scope, child = self.hosted_command_model()
        original, output = KeyboardInterrupt("MODEL_HOSTED_SPAWN_CANCEL"), Mock()
        scope.spawn.side_effect = original
        scope.close.side_effect = OSError("MODEL_HOSTED_SCOPE_CLOSE")
        with patch.object(P, "make_scope", return_value=scope), patch.object(P, "ownership_environment", return_value={}), \
                patch.object(A, "new_file", return_value=output), \
                patch.object(A.threading, "Thread", side_effect=OSError("MODEL_HOSTED_THREAD_ALLOCATION")), \
                patch.object(A.os, "fsync"), self.assertRaises(KeyboardInterrupt) as raised:
            try:
                command.start()
            finally:
                command.drain("model-final")
                command.close()
        self.assertIs(raised.exception, original)
        output.close.assert_called_once_with()
        child.stdout.close.assert_called_once_with()
        child.stderr.close.assert_called_once_with()
        scope.close.assert_called_once_with()
        record = json.loads((command.directory / "command.json").read_text())
        self.assertTrue(any("MODEL_HOSTED_THREAD_ALLOCATION" in row for row in record["errors"]))
        self.assertTrue(any("MODEL_HOSTED_SCOPE_CLOSE" in row for row in record["errors"]))


class PosixOutputTests(unittest.TestCase):
    def test_existing_pipe_and_owned_file_modes_share_same_native_owner(self):
        for stdout, stderr in ((None, None), (object(), object())):
            with self.subTest(redirected=stdout is not None):
                scope = object.__new__(P.PosixScope)
                scope.launches, scope.leaders = [], []
                scope.discover = Mock(return_value=[])
                child = SimpleNamespace(pid=1234, stdout=None, stderr=None)
                with patch.object(P, "resolve_executable", return_value=["/fixture/python"]), \
                        patch.object(subprocess, "Popen", return_value=child) as spawn:
                    owned = scope.spawn(["/fixture/python"], "/fixture", {"OWNED": "1"},
                                        stdout=stdout, stderr=stderr)
                values = spawn.call_args.kwargs
                self.assertIs(values["stdout"], subprocess.PIPE if stdout is None else stdout)
                self.assertIs(values["stderr"], subprocess.PIPE if stderr is None else stderr)
                self.assertEqual(values["env"], {"OWNED": "1"})
                self.assertTrue(values["start_new_session"] and values["close_fds"])
                self.assertEqual(scope.leaders, [owned])
                scope.discover.assert_called_once_with()
                self.assertEqual("outputMode" in scope.launches[0], stdout is not None)

    def test_posix_half_redirect_never_launches(self):
        with patch.object(subprocess, "Popen") as spawn, \
                self.assertRaisesRegex(P.OwnershipError, "Both owned output"):
            object.__new__(P.PosixScope).spawn(["/fixture/python"], "/fixture", {}, stdout=object())
        spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
