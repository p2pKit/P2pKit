#!/usr/bin/env python3
"""Owned-stdin seam controls: tiny POSIX files and modeled Win32 calls only.

Run on a POSIX host. Popen, discovery, executable selection and Windows APIs are
explicit suppliers; no child, native loader, credential, provider or CI executes.
Passing these controls is not native process/custody/retirement qualification.
"""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack
import ctypes
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


def offline_only(event, _arguments):
    if event.startswith(("subprocess.", "socket.", "os.exec", "os.spawn")) or event in {
            "os.system", "os.fork", "os.forkpty", "os.posix_spawn", "ctypes.dlopen", "ctypes.dlsym"}:
        raise AssertionError("OWNED_STDIN_OFFLINE_ONLY: " + event)


sys.addaudithook(offline_only)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_processes as processes
import hosted_windows_files as files


FRAME = b'{"scope":"MODEL_OPERATIONAL_DATA_NOT_A_CREDENTIAL"}\n'
ARGV = ["model-node", "fixed-provider.cjs"]
ENV = {"MODEL_ENVIRONMENT": "NO_SERVICE_CREDENTIALS"}


class OfflineCase(unittest.TestCase):
    def setUp(self):
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)

    def patch(self, target, name, value):
        return self.patches.enter_context(patch.object(target, name, value))


class PosixOwnedStdinControls(OfflineCase):
    def setUp(self):
        super().setUp()
        if os.name != "posix":
            self.fail("These descriptor controls require a POSIX host; no silent platform skip")
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-owned-stdin-model-")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "frame"
        writer = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            self.assertEqual(os.write(writer, FRAME), len(FRAME))
        finally:
            os.close(writer)
        self.descriptors = []
        self.addCleanup(self.close_descriptors)
        self.scope = processes.PosixScope.__new__(processes.PosixScope)
        self.scope._closed, self.scope._retirement_error = False, None
        self.scope.handles, self.scope.leaders, self.scope.launches = {}, [], []
        self.scope.discover = Mock(return_value=[])
        self.backend = SimpleNamespace(pid=4242, stdout=object(), stderr=object(), poll=Mock(return_value=0))
        self.popen = self.patch(processes.subprocess, "Popen", Mock(return_value=self.backend))
        self.resolve = self.patch(processes, "resolve_executable", Mock(return_value=["/model/node", ARGV[1]]))

    def close_descriptors(self):
        for descriptor in reversed(self.descriptors):
            os.close(descriptor)

    def descriptor(self, flags=os.O_RDONLY, path=None):
        descriptor = os.open(self.path if path is None else path, flags)
        self.descriptors.append(descriptor)
        return descriptor

    def spawn(self, **options):
        return self.scope.spawn(ARGV, "/model", ENV, **options)

    def assert_original_open(self, descriptor):
        self.assertEqual(os.fstat(descriptor).st_ino, self.path.stat().st_ino)
        self.assertFalse(os.get_inheritable(descriptor))
        self.assertEqual(self.path.read_bytes(), FRAME)

    def test_default_omitted_and_none_keep_devnull_pipe_contract_and_record(self):
        records = []
        for options in ({}, {"stdin": None}):
            with self.subTest(options=options):
                self.spawn(**options)
                self.assertEqual(self.popen.call_args.args, (["/model/node", ARGV[1]],))
                self.assertEqual(self.popen.call_args.kwargs, dict(cwd="/model", env=ENV,
                    stdin=processes.subprocess.DEVNULL, stdout=processes.subprocess.PIPE,
                    stderr=processes.subprocess.PIPE, start_new_session=True, close_fds=True, bufsize=0))
                records.append(dict(self.scope.launches[-1]))
        self.assertEqual(records[0], records[1])
        self.assertEqual(records[0], {"api": "subprocess.Popen", "requestedArgv": ARGV, "cwd": "/model",
            "shell": False, "created": True, "resolvedArgv": ["/model/node", ARGV[1]],
            "executable": "/model/node", "pid": 4242})

    def test_integer_or_once_captured_fileno_reaches_popen_as_the_exact_integer(self):
        for wrapped in (False, True):
            descriptor = self.descriptor()
            lookup = Mock(side_effect=[descriptor, AssertionError("SECOND_FILENO_LOOKUP")])
            source = SimpleNamespace(fileno=lookup) if wrapped else descriptor
            with self.subTest(wrapped=wrapped):
                self.spawn(stdin=source)
                actual = self.popen.call_args.kwargs["stdin"]
                self.assertIs(type(actual), int)
                self.assertEqual(actual, descriptor)
                self.assertEqual(self.scope.launches[-1]["inputMode"], "caller-owned-file")
                self.assertNotIn(str(self.path), repr(self.scope.launches[-1]))
                self.assert_original_open(descriptor)
                if wrapped:
                    lookup.assert_called_once_with()
                else:
                    lookup.assert_not_called()

    def test_modeled_child_reads_actual_eof_without_rewriting_or_closing_the_borrowed_file(self):
        descriptor = self.descriptor()
        observations = []

        def consume(*_args, **options):
            self.assertEqual(options["stdin"], descriptor)
            observations.extend((os.read(descriptor, len(FRAME) + 1), os.read(descriptor, 1)))
            return self.backend

        self.popen.side_effect = consume
        self.spawn(stdin=descriptor)
        self.assertEqual(observations, [FRAME, b""])
        self.assertEqual(os.lseek(descriptor, 0, os.SEEK_CUR), len(FRAME))
        self.scope.close()  # Only modeled leaders are polled; caller fd is not this scope's resource.
        self.assert_original_open(descriptor)

    def test_malformed_descriptor_and_fileno_results_refuse_before_popen_or_discovery(self):
        invalid = [True, False, -1, 1.0, "1", object(), SimpleNamespace(fileno=1)]
        invalid += [SimpleNamespace(fileno=Mock(return_value=value)) for value in (True, -1, 1.0, None)]
        for source in invalid:
            with self.subTest(source_type=type(source).__name__), self.assertRaises(processes.OwnershipError):
                self.spawn(stdin=source)
        self.popen.assert_not_called()
        self.resolve.assert_not_called()
        self.scope.discover.assert_not_called()
        self.assertEqual(self.scope.launches, [])

    def test_closed_fd_and_original_fileno_failure_remain_failures_without_launch(self):
        descriptor = self.descriptor()
        os.close(descriptor)
        self.descriptors.remove(descriptor)
        with self.assertRaises(OSError):
            self.spawn(stdin=descriptor)
        original = OSError("MODEL_ORIGINAL_FILENO_FAILURE")
        with self.assertRaises(OSError) as raised:
            self.spawn(stdin=SimpleNamespace(fileno=Mock(side_effect=original)))
        self.assertIs(raised.exception, original)
        self.popen.assert_not_called()
        self.scope.discover.assert_not_called()

    def test_nonregular_and_writable_descriptors_cannot_be_owned_stdin(self):
        read, write = os.pipe()
        self.descriptors.extend((read, write))
        cases = {"directory": self.descriptor(path=self.temporary.name), "pipe": read,
                 "character-device": self.descriptor(path=os.devnull),
                 "write-only": self.descriptor(os.O_WRONLY), "read-write": self.descriptor(os.O_RDWR)}
        for name, descriptor in cases.items():
            with self.subTest(kind=name), self.assertRaises(processes.OwnershipError):
                self.spawn(stdin=descriptor)
            os.fstat(descriptor)  # Refusal does not transfer or close caller ownership.
        self.popen.assert_not_called()
        self.scope.discover.assert_not_called()
        self.assertEqual(self.path.read_bytes(), FRAME)

    def test_inheritable_or_nonzero_position_refuses_without_changing_the_original(self):
        for reason in ("inheritable", "position"):
            descriptor = self.descriptor()
            if reason == "inheritable":
                os.set_inheritable(descriptor, True)
            else:
                os.lseek(descriptor, 1, os.SEEK_SET)
            with self.subTest(reason=reason), self.assertRaises(processes.OwnershipError):
                self.spawn(stdin=descriptor)
            self.assertEqual(os.get_inheritable(descriptor), reason == "inheritable")
            self.assertEqual(os.lseek(descriptor, 0, os.SEEK_CUR), 0 if reason == "inheritable" else 1)
            os.fstat(descriptor)
        self.popen.assert_not_called()
        self.scope.discover.assert_not_called()

    def test_spawn_or_postspawn_discovery_failure_never_closes_borrowed_input(self):
        descriptor = self.descriptor()
        for stage in ("spawn", "discovery"):
            original = RuntimeError("MODEL_" + stage.upper() + "_FAILURE")
            self.popen.side_effect = original if stage == "spawn" else None
            self.scope.discover.side_effect = original if stage == "discovery" else None
            with self.subTest(stage=stage), self.assertRaises(RuntimeError) as raised:
                self.spawn(stdin=descriptor)
            self.assertIs(raised.exception, original)
            self.assert_original_open(descriptor)
            self.assertEqual(self.scope.launches[-1]["created"], stage == "discovery")
        self.assertEqual(len(self.scope.leaders), 1)

    def test_optional_input_keeps_paired_output_sinks_and_keyword_only_contract(self):
        descriptor = self.descriptor()
        stdout, stderr = object(), object()
        self.spawn(stdin=descriptor, stdout=stdout, stderr=stderr)
        self.assertIs(self.popen.call_args.kwargs["stdout"], stdout)
        self.assertIs(self.popen.call_args.kwargs["stderr"], stderr)
        self.assertEqual(self.scope.launches[-1]["outputMode"], "caller-owned-files")
        self.popen.reset_mock()
        with self.assertRaises(processes.OwnershipError):
            self.spawn(stdin=descriptor, stdout=stdout)
        with self.assertRaises(TypeError):
            self.scope.spawn(ARGV, "/model", ENV, descriptor)
        self.popen.assert_not_called()
        self.assert_original_open(descriptor)


class NativePinModel:
    def __init__(self, api, handle, content):
        self.api, self.handle = api, handle
        self.path = rf"C:\model\private-{handle}.dat"
        self.info = files.FileInfo((1, f"{handle:032x}"), False, len(content), 1, 0, 1, 1, 1)
        self.release_count = 0

    def observe(self):
        return self.info

    def release(self):
        self.release_count += 1
        if self.release_count != 1:
            raise AssertionError("MODEL_ORIGINAL_PIN_RELEASED_TWICE")
        self.api.close(self.handle)


class WindowsApiModel:
    """Explicit in-memory handle/API model, never ctypes WinDLL or CRT adoption."""
    def __init__(self):
        self.events, self.duplicates, self.pipe_ends = [], [], []
        self.closed = Counter()
        self.handles, self.content = {90: False}, {}
        self.next_handle, self.input_original = 1000, 10
        self.input_failure = None
        self.failure = RuntimeError("MODEL_INPUT_DUPLICATE_FAILURE")
        self.input_info_failure = None
        self.input_close_failure = None
        self.member, self.consume_input = True, False
        self.handle_list, self.job_list, self.standard_handles = (), (), ()
        self.consumed = None

    def fresh(self, inheritable):
        self.next_handle += 1
        self.handles[self.next_handle] = inheritable
        return self.next_handle

    def check(self, result, operation):
        self.events.append(("check", operation))
        if not result:
            if operation == "DuplicateHandle owned input":
                raise self.failure
            raise processes.OwnershipError("MODEL_CHECK_FAILURE: " + operation)
        return result

    def GetHandleInformation(self, handle, output):
        self.events.append(("get-flags", handle))
        if handle == self.input_original and self.input_info_failure is not None:
            raise self.input_info_failure
        output._obj.value = int(self.handles[handle])
        return 1

    def DuplicateHandle(self, source_process, handle, target_process, output, access, inherit, options):
        self.events.append(("duplicate", handle, source_process.value, target_process.value, access, inherit, options))
        if handle == self.input_original and self.input_failure == "before":
            raise self.failure
        duplicate = self.fresh(bool(inherit))
        output._obj.value = duplicate
        self.duplicates.append((handle, duplicate))
        if handle in self.content:
            self.content[duplicate] = self.content[handle]  # DuplicateHandle shares the file position.
        if handle == self.input_original and self.input_failure == "after":
            raise self.failure
        return 0 if handle == self.input_original and self.input_failure == "false" else 1

    def CreatePipe(self, read, write, _security, size):
        if size != 0:
            raise AssertionError("MODEL_PIPE_DEFAULT_CHANGED")
        read._obj.value, write._obj.value = self.fresh(True), self.fresh(True)
        self.pipe_ends.append((read._obj.value, write._obj.value))
        self.events.append(("pipe", *self.pipe_ends[-1]))
        return 1

    def SetHandleInformation(self, handle, mask, flags):
        if (mask, flags) != (1, 0):
            raise AssertionError("MODEL_READ_PIPE_INHERITANCE_CHANGED")
        self.handles[handle.value] = False
        return 1

    def CreateFileW(self, path, access, sharing, security, disposition, attributes, template):
        if (path, access, sharing, disposition, attributes, template) != ("NUL", 0x80000000, 3, 3, 0x80, None):
            raise AssertionError("MODEL_NUL_DEFAULT_CHANGED")
        if security._obj.inherit != 1:
            raise AssertionError("MODEL_NUL_NOT_INHERITABLE")
        handle = self.fresh(True)
        self.content[handle] = {"bytes": b"", "position": 0}
        self.events.append(("nul", handle))
        return handle

    def InitializeProcThreadAttributeList(self, attributes, count, flags, size):
        if (count, flags) != (2, 0):
            raise AssertionError("MODEL_ATTRIBUTE_COUNT_CHANGED")
        size._obj.value = 256
        return 0 if attributes is None else 1

    def UpdateProcThreadAttribute(self, _attributes, flags, key, values, size, old, returned):
        if flags != 0 or old is not None or returned is not None or size != ctypes.sizeof(values):
            raise AssertionError("MODEL_ATTRIBUTE_CALL_CHANGED")
        if key == 0x00020002:
            self.handle_list = tuple(values)
            if len(self.handle_list) != 3 or len(set(self.handle_list)) != 3:
                raise AssertionError("MODEL_EXACT_HANDLE_LIST_REQUIRED")
            if not all(self.handles[value] for value in self.handle_list):
                raise AssertionError("MODEL_INHERITED_HANDLE_NOT_INHERITABLE")
        elif key == 0x0002000D:
            self.job_list = tuple(values)
        else:
            raise AssertionError("MODEL_UNEXPECTED_ATTRIBUTE")
        self.events.append(("attribute", key, tuple(values)))
        return 1

    def DeleteProcThreadAttributeList(self, _attributes):
        self.events.append(("delete-attributes",))

    def CreateProcessW(self, executable, command, process_security, thread_security, inherit, flags,
                       _environment, cwd, startup, information):
        if (executable, cwd, inherit, flags, process_security, thread_security) != (
                r"C:\model\node.exe", r"C:\model", 1, 0x80604, None, None):
            raise AssertionError("MODEL_PROCESS_FLAGS_OR_COMMAND_CHANGED")
        self.standard_handles = (startup._obj.startup.stdin, startup._obj.startup.stdout, startup._obj.startup.stderr)
        if self.standard_handles != self.handle_list or self.job_list != (90,):
            raise AssertionError("MODEL_STARTUP_LISTS_NOT_BOUND")
        if startup._obj.startup.flags != 0x100 or not command.value:
            raise AssertionError("MODEL_STARTUP_FLAGS_CHANGED")
        information._obj.process, information._obj.thread = self.fresh(False), self.fresh(False)
        information._obj.pid, information._obj.tid = 4242, 4243
        self.events.append(("create", information._obj.process, information._obj.thread))
        return 1

    def IsProcessInJob(self, handle, job, member):
        if job != 90:
            raise AssertionError("MODEL_WRONG_JOB")
        member._obj.value = int(self.member)
        self.events.append(("member", handle, self.member))
        return 1

    def identity(self, handle, pid):
        self.events.append(("identity", handle))
        return {"pid": pid, "creationFileTime": 7}

    def ResumeThread(self, handle):
        self.events.append(("resume", handle))
        if self.consume_input:
            data = self.content[self.standard_handles[0]]
            self.consumed = data["bytes"][data["position"]:]
            data["position"] = len(data["bytes"])
        return 1

    def TerminateJobObject(self, job, status):
        self.events.append(("terminate-job", job, status))
        if (job, status) != (90, 125):
            raise AssertionError("MODEL_WRONG_JOB_TERMINATION")
        return 1

    def close(self, handle):
        self.closed[handle] += 1
        if self.closed[handle] != 1 or handle not in self.handles:
            raise AssertionError("MODEL_RAW_HANDLE_CLOSED_TWICE_OR_NOT_OWNED")
        self.events.append(("close", handle))
        del self.handles[handle]
        if any(source == self.input_original and duplicate == handle for source, duplicate in self.duplicates) \
                and self.input_close_failure is not None:
            raise self.input_close_failure  # Models close-then-error: NEVER retry this raw value.

    def seek(self, handle, position, whence):
        data = self.content[handle]
        if whence == 0:
            data["position"] = position
        elif (position, whence) != (0, 1):
            raise AssertionError("MODEL_UNEXPECTED_FILE_SEEK")
        return data["position"]

    def flush(self, handle):
        if handle not in self.handles:
            raise AssertionError("MODEL_FLUSH_CLOSED_ORIGINAL")


class WindowsOwnedStdinControls(OfflineCase):
    def setUp(self):
        super().setUp()
        self.models = []
        self.patch(processes, "resolve_executable", Mock(return_value=[r"C:\model\node.exe", ARGV[1]]))
        self.patch(files, "time", SimpleNamespace(monotonic=lambda: 100.0))
        self.patch(files.NativeFile, "fileno", Mock(side_effect=AssertionError("WIN32_IS_NOT_A_CRT_FD")))
        self.addCleanup(self.dispose_models)

    def model(self):
        api = WindowsApiModel()
        scope = processes.WindowsScope.__new__(processes.WindowsScope)
        scope.api, scope.job = api, 90
        scope.launches, scope.leaders, scope.known, scope.discovery_errors = [], [], {}, set()
        model = SimpleNamespace(api=api, scope=scope, originals=[], streams=[])
        self.models.append(model)
        model.stdin = self.native(model, 10, False, FRAME)
        model.stdout = self.native(model, 20, True, b"")
        model.stderr = self.native(model, 21, True, b"")
        return model

    def native(self, model, handle, writable, content, kind=files.NativeFile):
        model.api.handles[handle] = False
        model.api.content[handle] = {"bytes": content, "position": 0}
        pin = NativePinModel(model.api, handle, content)
        owner = kind(model.api, [pin], max_bytes=4096, writable=writable, deadline=200.0)
        model.originals.append(owner)
        return owner

    def dispose_models(self):
        # Fixture disposal only after all assertions. UNKNOWN duplicates are not
        # retried; this neither performs nor claims any production retirement.
        for model in reversed(self.models):
            for stream in model.streams:
                stream.close()
            model.scope.close()
            for owner in reversed(model.originals):
                owner.close()

    def spawn(self, model, *, pipes=False, supplied=True, source=None):
        options = {} if pipes else {"stdout": model.stdout, "stderr": model.stderr}
        if supplied:
            options["stdin"] = model.stdin if source is None else source
        return model.scope.spawn(ARGV, r"C:\model", ENV, **options)

    def assert_originals_retained(self, model):
        for owner, handle in ((model.stdin, 10), (model.stdout, 20), (model.stderr, 21)):
            self.assertFalse(owner.closed)
            self.assertEqual(owner.native_handle, handle)
            self.assertEqual(model.api.closed[handle], 0)
            self.assertFalse(model.api.handles[handle])
            self.assertEqual(owner._pins[-1].release_count, 0)
        self.assertEqual(model.api.content[10]["bytes"], FRAME)

    def install_pipe_model(self, model):
        class PipeModel:
            def __init__(self, handle, name):
                self.native_handle, self.name = handle, name
                self.descriptor_adopted, self.closed = False, False
                model.streams.append(self)

            def adopt(self):
                self.descriptor_adopted = True  # Explicit model, NOT CRT adoption.

            def close(self):
                if not self.closed:
                    self.closed = True
                    model.api.close(self.native_handle)

        return patch.object(processes, "_WindowsPipeReader", PipeModel)

    def test_default_omitted_or_none_keep_nul_output_duplicates_and_cleanup_order(self):
        records = []
        for explicit in (False, True):
            model = self.model()
            options = {"stdout": model.stdout, "stderr": model.stderr}
            if explicit:
                options["stdin"] = None
            model.scope.spawn(ARGV, r"C:\model", ENV, **options)
            records.append(model.scope.launches[-1])
            outputs = [duplicate for source, duplicate in model.api.duplicates if source in (20, 21)]
            nul = next(row[1] for row in model.api.events if row[0] == "nul")
            self.assertEqual(model.api.handle_list, (nul, *outputs))
            self.assertEqual([row[1] for row in model.api.events if row[0] == "close"][:3], outputs + [nul])
            self.assertNotIn("inputMode", records[-1])
            self.assertEqual(records[-1]["outputMode"], "caller-owned-native-files")
            self.assert_originals_retained(model)
        self.assertEqual(records[0], records[1])

    def test_actual_native_reader_uses_only_fresh_duplicates_and_job_membership_before_resume(self):
        model = self.model()
        model.api.consume_input = True
        self.spawn(model)
        duplicates = dict(model.api.duplicates)
        self.assertEqual(set(duplicates), {10, 20, 21})
        self.assertEqual(model.api.handle_list, (duplicates[10], duplicates[20], duplicates[21]))
        for row in (row for row in model.api.events if row[0] == "duplicate"):
            self.assertEqual(row[2:], (ctypes.c_void_p(-1).value, ctypes.c_void_p(-1).value, 0, 1, 2))
        self.assertFalse(any(row[0] == "nul" for row in model.api.events))
        names = [row[0] for row in model.api.events]
        self.assertLess(names.index("create"), names.index("member"))
        self.assertLess(names.index("member"), names.index("identity"))
        self.assertLess(names.index("identity"), names.index("resume"))
        self.assertEqual(model.api.consumed, FRAME)
        self.assertEqual(model.stdin.tell(), len(FRAME))  # Shared position advances; Scope must not rewind it.
        self.assertEqual(model.scope.launches[-1]["inputMode"], "caller-owned-native-file")
        self.assertTrue(model.scope.launches[-1]["jobAssignedBeforeResume"])
        self.assertNotIn(str(model.stdin.path), repr(model.scope.launches[-1]))
        for duplicate in duplicates.values():
            self.assertEqual(model.api.closed[duplicate], 1)
        self.assert_originals_retained(model)

    def test_default_pipe_outputs_use_only_the_existing_write_ends_with_optional_or_nul_input(self):
        for optional in (False, True):
            model = self.model()
            with self.subTest(optional=optional), self.install_pipe_model(model):
                child = self.spawn(model, pipes=True, supplied=optional)
            writes = [write for _, write in model.api.pipe_ends]
            reads = [read for read, _ in model.api.pipe_ends]
            self.assertEqual(list(model.api.handle_list[1:]), writes)
            self.assertTrue(set(reads).isdisjoint(model.api.handle_list))
            self.assertEqual([child.stdout.native_handle, child.stderr.native_handle], reads)
            for read in reads:
                self.assertEqual(model.api.closed[read], 0)
                self.assertFalse(model.api.handles[read])
            for write in writes:
                self.assertEqual(model.api.closed[write], 1)
            self.assertEqual("inputMode" in model.scope.launches[-1], optional)
            self.assert_originals_retained(model)

    def test_raw_handles_lookalikes_and_nativefile_subclasses_refuse_before_native_acquisition(self):
        class DerivedNativeFile(files.NativeFile):
            pass

        model = self.model()
        derived = self.native(model, 30, False, FRAME, kind=DerivedNativeFile)
        lookalike = SimpleNamespace(native_handle=10, readable=Mock(return_value=True),
                                   writable=Mock(return_value=False), tell=Mock(return_value=0))
        for source in (10, True, object(), lookalike, derived):
            with self.subTest(kind=type(source).__name__), self.assertRaises(processes.OwnershipError):
                self.spawn(model, source=source)
        self.assertEqual(model.api.events, [])
        self.assertEqual(model.scope.launches, [])
        lookalike.readable.assert_not_called()
        lookalike.writable.assert_not_called()
        lookalike.tell.assert_not_called()
        self.assert_originals_retained(model)

    def test_invalid_native_handle_writable_or_closed_reader_never_launches_or_closes_originals(self):
        for bad in (0, -1, True, ctypes.c_void_p(-1).value, 1.0):
            model = self.model()
            pin = model.stdin._pins[-1]
            pin.handle = bad
            try:
                with self.subTest(handle=bad), self.assertRaises(processes.OwnershipError):
                    self.spawn(model)
            finally:
                pin.handle = 10
            self.assertFalse(any(row[0] == "create" for row in model.api.events))
            self.assert_originals_retained(model)
        model = self.model()
        model.stdin._writable = True
        try:
            with self.assertRaises(processes.OwnershipError):
                self.spawn(model)
        finally:
            model.stdin._writable = False
        self.assert_originals_retained(model)
        model = self.model()
        model.stdin.close()
        with self.assertRaises(files.FilesystemError):
            self.spawn(model)
        self.assertEqual(model.api.closed[10], 1)
        self.assertFalse(any(row[0] == "create" for row in model.api.events))

    def test_input_offset_inheritance_or_output_handle_alias_refuses_without_input_duplication(self):
        for reason in ("position", "boolean-position", "inheritable", "output-alias"):
            model = self.model()
            pin = model.stdin._pins[-1]
            if reason in ("position", "boolean-position"):
                model.api.content[10]["position"] = 1 if reason == "position" else True
            elif reason == "inheritable":
                model.api.handles[10] = True
            else:
                pin.handle = 20
            try:
                with self.subTest(reason=reason), self.assertRaises(processes.OwnershipError):
                    self.spawn(model)
                self.assertFalse(any(row[0] == "create" for row in model.api.events))
                self.assertFalse(any(source == 10 for source, _ in model.api.duplicates))
                self.assertEqual(model.api.closed[10], 0)
            finally:
                pin.handle, model.api.handles[10] = 10, False
                model.api.content[10]["position"] = 0
            self.assert_originals_retained(model)

    def test_original_input_handle_information_failure_is_preserved_and_outputs_retire_once(self):
        model = self.model()
        failure = OSError("MODEL_INPUT_HANDLE_INFO_DENIED")
        model.api.input_info_failure = failure
        with self.assertRaises(OSError) as raised:
            self.spawn(model)
        self.assertIs(raised.exception, failure)
        self.assertEqual([source for source, _ in model.api.duplicates], [20, 21])
        for _, duplicate in model.api.duplicates:
            self.assertEqual(model.api.closed[duplicate], 1)
        self.assertFalse(any(row[0] in ("create", "terminate-job") for row in model.api.events))
        self.assert_originals_retained(model)

    def test_duplicate_before_or_after_population_and_false_result_have_exact_once_only_cleanup(self):
        for stage in ("before", "after", "false"):
            model = self.model()
            model.api.input_failure = stage
            with self.subTest(stage=stage), self.assertRaises(RuntimeError) as raised:
                self.spawn(model)
            self.assertIs(raised.exception, model.api.failure)
            self.assertEqual([source for source, _ in model.api.duplicates], [20, 21] + ([] if stage == "before" else [10]))
            for _, duplicate in model.api.duplicates:
                self.assertEqual(model.api.closed[duplicate], 1)
            self.assertFalse(any(row[0] in ("create", "terminate-job") for row in model.api.events))
            self.assertEqual(processes.retirement_details(raised.exception), {})
            self.assert_originals_retained(model)

    def test_late_input_duplicate_close_failure_is_unknown_and_kills_only_owned_job_without_retry(self):
        model = self.model()
        model.api.input_close_failure = OSError("MODEL_INPUT_CLOSE_THEN_ERROR")
        with self.assertRaises(processes.OwnershipError) as raised:
            self.spawn(model)
        detail = processes.retirement_details(raised.exception)
        self.assertEqual(detail["status"], "UNKNOWN")
        self.assertEqual(len(detail["resources"]), 1)
        self.assertEqual(detail["resources"][0]["phase"], "launch-temporary")
        self.assertIn("MODEL_INPUT_CLOSE_THEN_ERROR", detail["resources"][0]["error"])
        self.assertTrue(model.scope.launches[-1]["resumed"])
        self.assertEqual([row for row in model.api.events if row[0] == "terminate-job"], [("terminate-job", 90, 125)])
        self.assertEqual(len(model.scope.leaders), 1)
        model.scope.close()
        model.scope.close()
        for _, duplicate in model.api.duplicates:
            self.assertEqual(model.api.closed[duplicate], 1)
        self.assert_originals_retained(model)

    def test_partial_input_acquisition_keeps_primary_error_and_secondary_unknown_cleanup(self):
        model = self.model()
        model.api.input_failure = "after"
        model.api.input_close_failure = OSError("MODEL_SECONDARY_INPUT_CLOSE_FAILURE")
        with self.assertRaises(RuntimeError) as raised:
            self.spawn(model)
        self.assertIs(raised.exception, model.api.failure)
        self.assertEqual(processes.retirement_details(raised.exception)["status"], "UNKNOWN")
        for _, duplicate in model.api.duplicates:
            self.assertEqual(model.api.closed[duplicate], 1)
        self.assertFalse(any(row[0] in ("create", "terminate-job") for row in model.api.events))
        self.assert_originals_retained(model)

    def test_optional_input_never_bypasses_required_job_membership_before_resume(self):
        model = self.model()
        model.api.member = False
        with self.assertRaisesRegex(processes.OwnershipError, "job membership"):
            self.spawn(model)
        self.assertFalse(any(row[0] == "resume" for row in model.api.events))
        self.assertFalse(model.scope.launches[-1]["resumed"])
        self.assertEqual([row for row in model.api.events if row[0] == "terminate-job"], [("terminate-job", 90, 125)])
        for _, duplicate in model.api.duplicates:
            self.assertEqual(model.api.closed[duplicate], 1)
        self.assert_originals_retained(model)


if __name__ == "__main__":
    result = unittest.main(verbosity=2, failfast=True, exit=False).result
    print("OWNED_STDIN_NATIVE_PROCESS_PROVIDER_CUSTODY_QUALIFICATION=NOT_RUN")
    raise SystemExit(0 if result.wasSuccessful() else 1)
