#!/usr/bin/env python3
"""Offline fixed-stdin syscall/clock models; never operate on real fd0/handles."""
from __future__ import annotations

import errno
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hosted_cache_provider_cancel as C

L, clocks = C.L, C.L.clocks


class Failure(RuntimeError):
    def __bool__(self):
        return False


def caught(call):
    try:
        call()
    except BaseException as error:
        return error
    raise AssertionError("MODEL_EXPECTED_FAILURE")


class Raw:
    closefd, mode, closed = False, "rb", False

    def fileno(self):
        return 0


class Buffer:
    closed = False

    def __init__(self):
        self.raw = Raw()

    def fileno(self):
        return 0


class Text:
    closed = False

    def __init__(self):
        self.buffer = Buffer()

    def fileno(self):
        return 0


class Syscalls:
    """Only numeric model references. No live descriptor/Windows API underneath."""
    def __init__(self, windows):
        self.windows, self.events = windows, []
        self.stdin, self.pin, self.handle = Text(), 7, 50
        self.identity = (12, 345, stat.S_IFIFO if windows else stat.S_IFSOCK)
        self.refs = {0: self.identity}
        self.blocking, self.binary, self.inheritable = True, 0x8000, False
        self.data, self.reads, self.closes, self.duplicates = [], [], [], []
        self.on_read = self.on_close = self.on_duplicate = lambda: None
        self.compare = 1
        self.dup_status, self.close_status, self.info_status = 1, 1, 1
        self.os = SimpleNamespace(name="nt" if windows else "posix", O_BINARY=0x8000,
            fstat=self.fstat, dup=self.dup, read=self.read, close=self.close,
            get_blocking=self.get_blocking, set_blocking=self.set_blocking,
            get_inheritable=self.get_inheritable)
        self.crt = SimpleNamespace(get_osfhandle=self.get_osfhandle, setmode=self.setmode)
        self.native = SimpleNamespace(crt=self.crt, DuplicateHandle=self.duplicate_handle,
            CompareObjectHandles=self.compare_handles, GetHandleInformation=self.handle_info,
            CloseHandle=self.close_handle)

    def fstat(self, descriptor):
        self.events.append(("fstat", descriptor))
        device, inode, kind = self.refs[descriptor]
        # Windows CPython pipe fstat deliberately has no object identity.
        return SimpleNamespace(st_dev=0 if self.windows else device,
            st_ino=0 if self.windows else inode, st_mode=kind | 0o600)

    def dup(self, descriptor):
        assert descriptor == 0
        self.duplicates.append(("dup", descriptor))
        self.refs[self.pin] = self.refs[0]
        self.on_duplicate()
        return self.pin

    def duplicate_handle(self, source_process, handle, target_process, output, access, inherit, options):
        self.duplicates.append((source_process.value, handle, target_process.value, access, inherit, options))
        assert source_process.value == target_process.value == C.PTR(-1).value
        assert (handle, access, inherit, options) == (50, 0, 0, 2)
        output._obj.value = self.pin
        self.refs[self.pin] = self.refs[0]
        self.on_duplicate()
        return self.dup_status

    def get_osfhandle(self, descriptor):
        assert descriptor == 0
        self.events.append(("get_osfhandle", descriptor))
        return self.handle

    def compare_handles(self, handle, pin):
        self.events.append(("compare", handle, pin))
        assert (handle, pin) == (50, self.pin)
        return self.compare if self.refs.get(0) == self.refs.get(pin) else 0

    def handle_info(self, pin, output):
        self.events.append(("handle_info", pin))
        assert pin == self.pin
        output._obj.value = int(self.inheritable)
        return self.info_status if pin in self.refs else 0

    def get_inheritable(self, descriptor):
        self.events.append(("get_inheritable", descriptor))
        assert descriptor == self.pin
        return self.inheritable

    def setmode(self, descriptor, mode):
        self.events.append(("setmode", descriptor, mode))
        assert descriptor == 0 and mode == 0x8000
        previous, self.binary = self.binary, mode
        return previous

    def get_blocking(self, descriptor):
        self.events.append(("get_blocking", descriptor))
        assert descriptor == 0
        return self.blocking

    def set_blocking(self, descriptor, value):
        self.events.append(("set_blocking", descriptor, value))
        assert descriptor == 0 and value is False
        self.blocking = value

    def read(self, descriptor, count):
        self.reads.append((descriptor, count))
        assert (descriptor, count) == (0, 2)
        self.on_read()
        value = self.data.pop(0) if self.data else BlockingIOError(errno.EAGAIN, "MODEL_EMPTY")
        if isinstance(value, BaseException):
            raise value
        return value

    def close(self, descriptor):
        self.closes.append(("close", descriptor))
        assert descriptor == self.pin and descriptor != 0
        self.refs.pop(descriptor)
        self.on_close()

    def close_handle(self, handle):
        self.closes.append(("CloseHandle", handle))
        assert handle == self.pin and handle != 50
        if self.close_status:
            self.refs.pop(handle)
        self.on_close()
        return self.close_status


class CancelModels(unittest.TestCase):
    def setUp(self):
        self.raw, self.local = 100 * clocks.NS, 100.0
        self.on_raw = lambda: None
        self.patch(L, "time", SimpleNamespace(monotonic=lambda: self.local))
        self.patch(clocks, "checked_now", self.now)

    def tearDown(self):
        C.QUARANTINE.clear()

    def patch(self, target, name, value):
        binding = patch.object(target, name, value)
        result = binding.start()
        self.addCleanup(binding.stop)
        return result

    def now(self, clock, *, minimum_ns):
        self.on_raw()
        return self.raw

    def make(self, windows=False):
        self.model = Syscalls(windows)
        self.patch(C, "os", self.model.os)
        self.patch(C, "sys", SimpleNamespace(stdin=self.model.stdin, __stdin__=self.model.stdin,
            implementation=SimpleNamespace(name="cpython"), version_info=(3, 12, 10)))
        self.patch(C, "io", SimpleNamespace(TextIOWrapper=Text, BufferedReader=Buffer, FileIO=Raw))
        self.factory = self.patch(C, "_WindowsStdin", Mock(return_value=self.model.native))
        role = "windows-x64" if windows else "linux-x64"
        clock = clocks.ClockIdentity(role, clocks.DOMAINS[role], clocks.NS)
        self.window = L._Window(clocks.Reading(clock, self.raw), self.raw, 280 * clocks.NS, 280 * clocks.NS)
        self.owner = C.OriginalStdinCancel(self.window)
        return self.owner

    def start(self, windows=False):
        self.make(windows).start()
        return self.owner

    def refuses_read(self, effect, windows=False):
        self.start(windows)
        effect()
        error = caught(self.owner.poll)
        self.assertEqual(self.model.reads, [])
        self.assertIs(caught(self.owner.poll), error)
        return error

    def test_constructor_is_inert(self):
        self.make(True)
        self.assertEqual(self.model.events, [])
        self.assertEqual(self.model.duplicates, [])
        self.factory.assert_not_called()

    def test_posix_socket_original_and_only_owned_pin_are_retained(self):
        self.start()
        self.assertFalse(self.owner.poll())
        self.assertFalse(self.owner.retire())
        self.owner.check_retired()
        self.assertEqual(self.model.duplicates, [("dup", 0)])
        self.assertEqual(self.model.closes, [("close", 7)])
        self.assertIn(0, self.model.refs)
        self.assertFalse(self.model.blocking)
        self.factory.assert_not_called()

    def test_posix_fifo_is_also_an_admitted_shape_not_node_identity(self):
        self.make()
        self.model.refs[0] = (12, 345, stat.S_IFIFO)
        self.owner.start()
        self.assertFalse(self.owner.retire())

    def test_windows_pin_uses_same_object_not_zeroed_fstat_identity(self):
        self.start(True)
        self.assertFalse(self.owner.poll())
        self.assertFalse(self.owner.retire())
        self.owner.check_retired()
        self.assertEqual(self.model.closes, [("CloseHandle", 7)])
        self.assertEqual(len(self.model.duplicates), 1)
        self.assertTrue(any(event[0] == "compare" for event in self.model.events))
        self.assertFalse(any(event[0] == "fstat" and event[1] == 7 for event in self.model.events))

    def test_fixed_first_byte_latches_across_no_data_and_close(self):
        self.start()
        self.model.data = [b"C"]
        self.assertTrue(self.owner.poll())
        self.assertTrue(self.owner.poll())
        self.assertTrue(self.owner.retire())
        self.owner.check_retired()
        self.assertEqual(self.model.reads, [(0, 2)] * 3)

    def test_eof_other_and_overlength_inputs_are_not_absence(self):
        for value in (b"", b"c", b"C\n", b"CC", b"!", bytearray(b"C"), None):
            with self.subTest(value_type=type(value).__name__, length=0 if value is None else len(value)):
                self.start()
                self.model.data = [value]
                # A real os.read cannot return None; do not let a supplied
                # non-byte result alias the would-block observation either.
                error = caught(self.owner.poll)
                self.assertIs(caught(self.owner.retire), error)
                self.assertEqual(self.model.closes, [("close", 7)])
                self.assertIsNotNone(caught(self.owner.check_retired))

    def test_duplicate_byte_is_not_idempotent_even_on_later_poll(self):
        self.start()
        self.model.data = [b"C", b"C"]
        self.assertTrue(self.owner.poll())
        error = caught(self.owner.poll)
        self.assertIs(caught(self.owner.retire), error)
        self.assertEqual(len(self.model.reads), 2)

    def test_eof_after_cancel_is_incomplete_not_known_failed_return(self):
        self.start(True)
        self.model.data = [b"C", b""]
        self.assertTrue(self.owner.poll())
        error = caught(self.owner.retire)
        self.assertIs(error, self.owner._primary)
        self.assertTrue(self.owner._closed)
        self.assertIsNotNone(caught(self.owner.check_retired))

    def test_wrong_blocking_error_is_not_would_block(self):
        self.start()
        failure = BlockingIOError(errno.EINVAL, "MODEL_NOT_WOULD_BLOCK")
        self.model.data = [failure]
        self.assertIs(caught(self.owner.poll), failure)

    def test_interrupted_and_other_read_errors_are_not_retried(self):
        for failure in (InterruptedError(errno.EINTR, "MODEL_INTERRUPTED"), Failure("MODEL_READ")):
            with self.subTest(kind=type(failure).__name__):
                self.start()
                self.model.data = [failure]
                self.assertIs(caught(self.owner.poll), failure)
                self.assertIs(caught(self.owner.retire), failure)
                self.assertEqual(len(self.model.reads), 1)

    def test_stdin_replacement_refuses_before_any_read(self):
        self.refuses_read(lambda: setattr(C.sys, "stdin", Text()))

    def test_buffer_replacement_refuses_before_any_read(self):
        self.refuses_read(lambda: setattr(self.model.stdin, "buffer", Buffer()))

    def test_raw_replacement_refuses_before_any_read(self):
        self.refuses_read(lambda: setattr(self.model.stdin.buffer, "raw", Raw()))

    def test_original_descriptor_reuse_never_reads_the_pin_as_fallback(self):
        self.refuses_read(lambda: self.model.refs.update({0: (12, 999, stat.S_IFSOCK)}))

    def test_posix_pin_reuse_refuses_before_read(self):
        self.refuses_read(lambda: self.model.refs.update({7: (12, 999, stat.S_IFSOCK)}))

    def test_windows_same_handle_number_different_object_refuses(self):
        self.refuses_read(lambda: setattr(self.model, "compare", 0), True)

    def test_windows_changed_original_handle_refuses(self):
        self.refuses_read(lambda: setattr(self.model, "handle", 51), True)

    def test_inheritable_pin_is_not_repaired(self):
        self.refuses_read(lambda: setattr(self.model, "inheritable", True), True)

    def test_blocking_mode_change_refuses_before_read(self):
        self.refuses_read(lambda: setattr(self.model, "blocking", True))

    def test_windows_text_mode_refuses_despite_setter_normalization(self):
        self.refuses_read(lambda: setattr(self.model, "binary", 0x4000), True)
        self.assertEqual(self.model.binary, 0x8000)

    def test_windows_setmode_error_survives_retirement(self):
        self.start(True)
        failure = Failure("MODEL_SETMODE")
        self.model.crt.setmode = Mock(side_effect=failure)
        self.assertIs(caught(self.owner.poll), failure)
        self.assertIs(caught(self.owner.retire), failure)
        self.assertEqual(self.model.closes, [("CloseHandle", 7)])

    def test_initial_nonblocking_stdin_is_not_silently_normalized(self):
        self.make()
        self.model.blocking = False
        caught(self.owner.start)
        self.assertFalse(any(event[0] == "set_blocking" for event in self.model.events))
        caught(self.owner.retire)
        self.assertEqual(self.model.closes, [("close", 7)])

    def test_initial_nonbinary_windows_stdin_is_refused(self):
        self.make(True)
        self.model.binary = 0x4000
        caught(self.owner.start)
        caught(self.owner.retire)
        self.assertEqual(self.model.closes, [("CloseHandle", 7)])

    def test_unidentifiable_posix_or_regular_file_refuses_before_dup(self):
        for identity in ((0, 0, stat.S_IFSOCK), (12, 345, stat.S_IFREG), (12, 345, stat.S_IFCHR)):
            with self.subTest(identity=identity):
                self.make()
                self.model.refs[0] = identity
                caught(self.owner.start)
                self.assertEqual(self.model.duplicates, [])

    def test_wrong_python_or_host_refuses_before_native_acquisition(self):
        for version, implementation, name in (((3, 11, 0), "cpython", "nt"),
                ((3, 12, 0), "other", "nt"), ((3, 12, 0), "cpython", "posix")):
            with self.subTest(version=version, implementation=implementation, name=name):
                self.make(True)
                C.sys.version_info, C.sys.implementation.name, C.os.name = version, implementation, name
                caught(self.owner.start)
                self.factory.assert_not_called()

    def test_partial_windows_duplicate_failure_retains_cell_without_guessing_ownership(self):
        self.make(True)
        failure = Failure("MODEL_DUP_AFTER_EFFECT")
        self.model.on_duplicate = lambda: (_ for _ in ()).throw(failure)
        self.assertIs(caught(self.owner.start), failure)
        self.assertEqual(self.owner._dup_output.value, 7)
        self.assertEqual(self.owner._pin, 7)
        self.assertFalse(self.owner._acquired)
        self.assertIs(caught(self.owner.retire), failure)
        self.assertEqual(self.model.closes, [])
        self.assertEqual(len(self.model.duplicates), 1)

    def test_false_windows_duplicate_result_is_not_known_ownership(self):
        self.make(True)
        self.model.dup_status = 0
        caught(self.owner.start)
        caught(self.owner.retire)
        self.assertEqual(self.owner._dup_output.value, 7)
        self.assertFalse(self.owner._acquired)
        self.assertEqual(self.model.closes, [])

    def test_late_duplicate_return_is_registered_but_not_qualified_or_retried(self):
        self.make()
        self.model.on_duplicate = lambda: setattr(self, "local", 280.0)
        caught(self.owner.start)
        self.assertEqual(self.owner._pin, 7)
        self.assertTrue(self.owner._acquired)
        caught(self.owner.retire)
        self.assertEqual(self.model.closes, [])
        self.assertEqual(len(self.model.duplicates), 1)

    def test_expired_window_refuses_before_any_native_acquisition(self):
        self.make(True)
        self.raw = 280 * clocks.NS
        caught(self.owner.start)
        self.assertEqual(self.model.events, [])
        self.factory.assert_not_called()

    def test_read_time_uses_same_original_end(self):
        self.start()
        before = self.window.local_end
        self.model.on_read = lambda: setattr(self, "local", 280.0)
        caught(self.owner.poll)
        self.assertEqual(self.window.local_end, before)
        self.assertEqual(len(self.model.reads), 1)

    def test_original_loss_during_would_block_return_refuses(self):
        self.start(True)
        self.model.on_read = lambda: setattr(self.model, "compare", 0)
        caught(self.owner.poll)
        caught(self.owner.retire)
        self.assertEqual(self.model.closes, [])
        self.assertEqual(len(self.model.reads), 1)

    def test_binary_mode_change_during_read_is_not_accepted(self):
        self.start(True)
        self.model.on_read = lambda: setattr(self.model, "binary", 0x4000)
        self.model.data = [b"C"]
        caught(self.owner.poll)
        self.assertTrue(self.owner._wire_seen)
        self.assertIsNotNone(self.owner._primary)

    def test_swallowed_poll_reentry_poison_cannot_be_hidden_by_would_block(self):
        self.start()
        nested = []
        self.model.on_read = lambda: nested.append(caught(self.owner.poll))
        self.assertIs(caught(self.owner.poll), nested[0])
        self.assertEqual(len(self.model.reads), 1)

    def test_native_branch_mutation_refuses_before_wrong_close_api(self):
        self.start(True)
        self.owner._windows = False
        caught(self.owner.retire)
        self.assertEqual(self.model.closes, [])

    def test_last_retirement_poll_can_observe_first_byte(self):
        self.start()
        self.model.data = [b"C"]
        self.assertTrue(self.owner.retire())
        self.owner.check_retired()
        self.assertEqual(len(self.model.reads), 1)

    def test_sealed_owner_never_reads_or_closes_again(self):
        self.start()
        self.owner.retire()
        reads, closes = len(self.model.reads), len(self.model.closes)
        caught(self.owner.poll)
        caught(self.owner.retire)
        self.assertEqual((len(self.model.reads), len(self.model.closes)), (reads, closes))

    def test_ambiguous_close_is_attempted_once_and_remains_incomplete(self):
        self.start(True)
        failure = Failure("MODEL_CLOSE_AFTER_EFFECT")
        self.model.on_close = lambda: (_ for _ in ()).throw(failure)
        self.assertIs(caught(self.owner.retire), failure)
        self.assertIs(caught(self.owner.retire), failure)
        self.assertTrue(self.owner._close_attempted)
        self.assertFalse(self.owner._closed)
        self.assertNotIn(7, self.model.refs)
        self.assertEqual(len(self.model.closes), 1)

    def test_false_close_handle_cannot_be_retried(self):
        self.start(True)
        self.model.close_status = 0
        caught(self.owner.retire)
        caught(self.owner.retire)
        self.assertIn(7, self.model.refs)
        self.assertEqual(len(self.model.closes), 1)

    def test_first_falsey_read_failure_survives_failed_close(self):
        self.start(True)
        failure = Failure("MODEL_FIRST")
        self.model.data = [failure]
        self.assertIs(caught(self.owner.poll), failure)
        self.model.close_status = 0
        self.assertIs(caught(self.owner.retire), failure)
        self.assertEqual(len(self.model.closes), 1)

    def test_post_close_raw_fence_spends_original_window_without_pin_query(self):
        self.start()
        def closed():
            self.raw = 280 * clocks.NS
            self.after_close_events = len(self.model.events)
        self.model.on_close = closed
        caught(self.owner.retire)
        self.assertTrue(self.owner._closed)
        self.assertEqual(len(self.model.events), self.after_close_events)
        self.assertIsNotNone(caught(self.owner.check_retired))

    def test_replaced_equal_window_is_not_a_renewal(self):
        self.start()
        self.owner.window = L._Window(self.window.first, 100 * clocks.NS, 280 * clocks.NS, 280 * clocks.NS)
        caught(self.owner.poll)
        self.assertEqual(self.model.reads, [])


class NativeBindingModels(unittest.TestCase):
    def test_fixed_system_export_and_signature_roster_without_native_loading(self):
        kernel = SimpleNamespace(**{name: Mock() for name in
            ("DuplicateHandle", "CloseHandle", "GetHandleInformation")})
        base = SimpleNamespace(CompareObjectHandles=Mock())
        crt = SimpleNamespace()
        loader = Mock(side_effect=[kernel, base])
        with patch.object(C, "os", SimpleNamespace(name="nt")), patch.dict(sys.modules, msvcrt=crt), \
                patch.object(C.ctypes, "WinDLL", loader, create=True):
            native = C._WindowsStdin()
        self.assertEqual(loader.call_args_list[0].args, ("kernel32.dll",))
        self.assertEqual(loader.call_args_list[1].args, ("Kernelbase.dll",))
        self.assertTrue(all(call.kwargs == {"use_last_error": True, "winmode": 0x800}
                            for call in loader.call_args_list))
        self.assertIs(native.crt, crt)
        self.assertEqual(native.DuplicateHandle.argtypes,
            [C.PTR, C.PTR, C.PTR, C.ctypes.POINTER(C.PTR), C.U32, C.I32, C.U32])
        self.assertEqual(native.CompareObjectHandles.argtypes, [C.PTR, C.PTR])
        self.assertIs(native.CompareObjectHandles.restype, C.I32)
        self.assertEqual(native.CloseHandle.argtypes, [C.PTR])
        self.assertFalse(hasattr(native, "open_osfhandle"))


if __name__ == "__main__":
    unittest.main()
