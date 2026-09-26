"""Fixed original-fd0 cancellation for the dormant outer supervisor only.

The sole wire message is b"C". EOF is failure, not its delimiter. This borrows
stdin and owns only one non-inheritable identity pin; that pin is never a reader.
No launcher, Node identity, hard preemption or provider acceptance is supplied.
The future original Node caller must retain its writer/cancellation latch through
actual child close: the final Python poll is necessarily earlier than that close.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import errno
import io
import os
import stat
import sys
import threading

import hosted_cache_provider_launch as L


QUARANTINE = []
PTR, U32, I32 = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int32


class _WindowsStdin:
    """Fixed system exports, not a caller-selected native backend."""
    def __init__(self):
        L.require(os.name == "nt" and ctypes.sizeof(PTR) == 8, "PROVIDER_CANCEL_WINDOWS_ABI")
        import msvcrt
        self.crt = msvcrt
        self.kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
        self.base = ctypes.WinDLL("Kernelbase.dll", use_last_error=True, winmode=0x800)
        for library, name, arguments, result in (
            (self.kernel, "DuplicateHandle", [PTR, PTR, PTR, ctypes.POINTER(PTR), U32, I32, U32], I32),
            (self.kernel, "CloseHandle", [PTR], I32),
            (self.kernel, "GetHandleInformation", [PTR, ctypes.POINTER(U32)], I32),
            (self.base, "CompareObjectHandles", [PTR, PTR], I32),
        ):
            function = getattr(library, name)
            function.argtypes, function.restype = arguments, result
            setattr(self, name, function)


class OriginalStdinCancel:
    """One-shot same-thread owner; all operations spend the entry's window.

    Construction is inert. start() alone acquires a new identity reference.
    retire() seals even a failed owner and attempts only a still-known pin's
    close, once. It never closes/rebinds/restores blocking mode on borrowed fd0.
    """
    def __init__(self, window):
        self.window = self._window_original = window
        self._thread = threading.get_ident()
        self._started = self._active = self._busy = False
        self._sealed = self._retire_started = self._close_attempted = self._closed = False
        self._primary, self._faults = None, 0
        self._wire_seen = self._wire_original = False
        self._streams = self._streams_original = None
        self._native = self._native_original = None
        self._pin = self._pin_original = None
        self._identity = self._identity_original = self._handle = self._handle_original = None
        self._dup_output = None  # Retained even if a native call fails after its effect.
        self._acquired = False
        self._windows = window.clock.role == "windows-x64"
        self._retired = self._retired_original = None

    def _phase(self):
        return (self._started, self._active, self._sealed, self._retire_started,
                self._close_attempted, self._closed, self._acquired)

    @staticmethod
    def _advanced(boundary, index):
        # Each flag changes only False -> True at one fixed source-owned point.
        # Derive expectations from the saved phase, never callback-mutated fields.
        phase = boundary[2]
        L.require(phase[index] is False, "PROVIDER_CANCEL_PHASE_REPEAT")
        return (*boundary[:2], phase[:index] + (True,) + phase[index + 1:])

    def _failed(self, error):
        if self._primary is None:
            self._primary = error
        self._faults += 1
        if not any(owner is self for owner in QUARANTINE):
            QUARANTINE.append(self)

    @contextmanager
    def _operation(self, *, retiring=False):
        entered = False
        try:
            L.require(not self._busy and threading.get_ident() == self._thread,
                      "PROVIDER_CANCEL_OPERATION_REENTRY")
            if not retiring and self._primary is not None:
                raise self._primary
            self._busy, entered = True, True
            yield self._primary, self._faults, self._phase()
        except BaseException as error:
            self._failed(error)
            raise self._primary
        finally:
            if entered:
                self._busy = False

    def _fence(self, boundary):
        def same():
            L.require(self.window is self._window_original and type(self.window) is L._Window and
                threading.get_ident() == self._thread and self._busy and
                self._primary is boundary[0] and self._faults == boundary[1] and
                self._streams is self._streams_original and self._native is self._native_original and
                self._pin == self._pin_original and self._identity is self._identity_original and
                self._handle == self._handle_original and self._wire_seen is self._wire_original and
                all(actual is expected for actual, expected in zip(self._phase(), boundary[2])) and
                self._windows is (self.window.clock.role == "windows-x64"),
                "PROVIDER_CANCEL_ORIGINALS_CHANGED")
        same()
        self.window.check()  # Never a fresh conversion, clock or cleanup allowance.
        same()

    def _call(self, boundary, function, *arguments):
        # Only internal fixed stdlib/native operations use this fence. Resource
        # acquisition below registers its actual output BEFORE the post-call fence.
        self._fence(boundary)
        value = function(*arguments)
        self._fence(boundary)
        return value

    def _streams_intact(self):
        source, buffer, raw = self._streams
        L.require(sys.stdin is sys.__stdin__ is source and type(source) is io.TextIOWrapper and
            source.buffer is buffer and type(buffer) is io.BufferedReader and
            buffer.raw is raw and type(raw) is io.FileIO and raw.closefd is False and raw.mode == "rb" and
            not source.closed and not buffer.closed and not raw.closed and
            all(type(value) is int and value == 0 for value in (source.fileno(), buffer.fileno(), raw.fileno())),
            "PROVIDER_CANCEL_STDIN_CHANGED")

    @staticmethod
    def _posix_identity(info):
        kind = stat.S_IFMT(info.st_mode)
        L.require(kind in (stat.S_IFIFO, stat.S_IFSOCK) and type(info.st_dev) is int and info.st_dev >= 0 and
                  type(info.st_ino) is int and info.st_ino > 0, "PROVIDER_CANCEL_PIPE_IDENTITY")
        return info.st_dev, info.st_ino, kind

    def _objects(self, boundary):
        self._fence(boundary)
        self._streams_intact()
        self._fence(boundary)
        L.require(self._acquired and self._pin is not None, "PROVIDER_CANCEL_PIN_UNOWNED")
        if self._windows:
            handle = self._call(boundary, self._native.crt.get_osfhandle, 0)
            L.require(type(handle) is int and handle == self._handle, "PROVIDER_CANCEL_HANDLE_CHANGED")
            same = self._call(boundary, self._native.CompareObjectHandles, handle, self._pin)
            L.require(type(same) is int and same != 0, "PROVIDER_CANCEL_OBJECT_CHANGED")
            flags = U32()
            valid = self._call(boundary, self._native.GetHandleInformation, self._pin, ctypes.byref(flags))
            L.require(type(valid) is int and valid != 0 and not flags.value & 1,
                      "PROVIDER_CANCEL_PIN_INHERITANCE")
        else:
            for descriptor in (0, self._pin):
                info = self._call(boundary, os.fstat, descriptor)
                L.require(self._posix_identity(info) == self._identity, "PROVIDER_CANCEL_OBJECT_CHANGED")
            L.require(self._call(boundary, os.get_inheritable, self._pin) is False,
                      "PROVIDER_CANCEL_PIN_INHERITANCE")
        self._streams_intact()
        self._fence(boundary)

    def _modes(self, boundary):
        if self._windows:
            # setmode returns the PREVIOUS mode or raises. Unknown text mode
            # cannot be repaired into acceptance, even if this setter changed it.
            previous = self._call(boundary, self._native.crt.setmode, 0, os.O_BINARY)
            L.require(type(previous) is int and previous == os.O_BINARY, "PROVIDER_CANCEL_BINARY_MODE")
        L.require(self._call(boundary, os.get_blocking, 0) is False, "PROVIDER_CANCEL_BLOCKING_MODE")

    def start(self):
        with self._operation() as boundary:
            L.require(all(value is False for value in boundary[2]), "PROVIDER_CANCEL_START_ONCE")
            self._started = True
            boundary = self._advanced(boundary, 0)
            self._fence(boundary)
            L.require(sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 12) and
                ((os.name == "nt" and self._windows) or (os.name == "posix" and not self._windows)),
                "PROVIDER_CANCEL_RUNTIME")
            source = sys.stdin
            L.require(type(source) is io.TextIOWrapper and source is sys.__stdin__, "PROVIDER_CANCEL_STDIN")
            self._streams = self._streams_original = (source, source.buffer, source.buffer.raw)
            self._streams_intact()
            self._fence(boundary)
            if self._windows:
                self._native = self._native_original = _WindowsStdin()
                self._fence(boundary)
                self._handle = self._handle_original = self._call(boundary, self._native.crt.get_osfhandle, 0)
                L.require(type(self._handle) is int and 0 < self._handle < PTR(-1).value,
                          "PROVIDER_CANCEL_HANDLE")
                info = self._call(boundary, os.fstat, 0)
                L.require(stat.S_ISFIFO(info.st_mode), "PROVIDER_CANCEL_PIPE_TYPE")  # NOT Windows identity.
                output = PTR()
                self._dup_output = output
                self._fence(boundary)
                try:
                    status = self._native.DuplicateHandle(PTR(-1), self._handle, PTR(-1),
                                                         ctypes.byref(output), 0, 0, 2)
                finally:
                    self._pin = self._pin_original = output.value
                # A false/ambiguous call retains its cell but cannot invent a
                # known owned handle, close it speculatively or retry acquisition.
                L.require(type(status) is int and status != 0 and type(self._pin) is int and
                    0 < self._pin < PTR(-1).value and self._pin != self._handle, "PROVIDER_CANCEL_DUPLICATE")
                self._acquired = True
                boundary = self._advanced(boundary, 6)
            else:
                self._identity = self._identity_original = self._posix_identity(self._call(boundary, os.fstat, 0))
                self._fence(boundary)
                self._pin = self._pin_original = os.dup(0)
                L.require(type(self._pin) is int and self._pin > 2, "PROVIDER_CANCEL_DUPLICATE")
                self._acquired = True
                boundary = self._advanced(boundary, 6)
            self._fence(boundary)
            self._objects(boundary)
            L.require(self._call(boundary, os.get_blocking, 0) is True, "PROVIDER_CANCEL_INITIAL_MODE")
            if self._windows:
                previous = self._call(boundary, self._native.crt.setmode, 0, os.O_BINARY)
                L.require(type(previous) is int and previous == os.O_BINARY, "PROVIDER_CANCEL_BINARY_MODE")
            self._objects(boundary)
            self._call(boundary, os.set_blocking, 0, False)
            self._modes(boundary)
            self._objects(boundary)
            self._active = True
            boundary = self._advanced(boundary, 1)
            self._fence(boundary)

    def poll(self):
        with self._operation() as boundary:
            L.require(all(actual is expected for actual, expected in
                zip(boundary[2], (True, True, False, False, False, False, True))),
                "PROVIDER_CANCEL_NOT_ACTIVE")
            self._objects(boundary)
            self._modes(boundary)
            self._objects(boundary)
            self._fence(boundary)
            would_block = False
            try:
                raw = os.read(0, 2)  # One fixed original read, never the pin or a drain loop.
            except BlockingIOError as error:
                if error.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                    raise
                would_block = True
                raw = None
            if not would_block:
                L.require(type(raw) is bytes and raw == b"C" and not self._wire_seen,
                          "PROVIDER_CANCEL_WIRE")  # EOF/duplicate/extra input is terminal.
                self._wire_seen = self._wire_original = True  # Before post-read callbacks; distinct from OS signals.
            self._fence(boundary)
            self._objects(boundary)
            self._modes(boundary)
            self._objects(boundary)
            return self._wire_seen

    def retire(self):
        # Last bounded poll while the identity pin is still live. An earlier
        # protocol failure stops further reads, but not a known pin's safe close.
        if self._active and not self._sealed and self._primary is None:
            try:
                self.poll()
            except BaseException:
                pass  # poll already retained its exact failure; never an acceptance path.
        with self._operation(retiring=True) as boundary:
            L.require(not self._retire_started, "PROVIDER_CANCEL_RETIRE_ONCE")
            self._retire_started = self._sealed = True
            boundary = self._advanced(self._advanced(boundary, 2), 3)
            self._objects(boundary)
            self._fence(boundary)
            self._close_attempted = True  # Never retry even if the native result is ambiguous.
            boundary = self._advanced(boundary, 4)
            if self._windows:
                status = self._native.CloseHandle(self._pin)
                L.require(type(status) is int and status != 0, "PROVIDER_CANCEL_PIN_CLOSE")
            else:
                os.close(self._pin)
            self._closed = True  # Actual close return, before the post-close original fence.
            boundary = self._advanced(boundary, 5)
            self._fence(boundary)
            if self._primary is not None:
                raise self._primary
            # Immutable source-owned terminal bindings. Later checks never query
            # the retired pin, reread its modes or sample a native clock.
            self._retired = self._retired_original = (
                self._window_original, self._streams_original, self._native_original,
                self._pin_original, self._identity_original, self._handle_original,
                self._wire_original, self._dup_output, self._thread, self._windows, boundary[2])
            return self._wire_seen

    def check_retired(self):
        """Direct terminal-state check only: no retired-pin query/read or callback."""
        L.require(self._sealed and self._retire_started and self._close_attempted and self._closed and
            not self._busy and self._primary is None and self._faults == 0,
            "PROVIDER_CANCEL_RETIRE_INCOMPLETE")
        retired = self._retired
        L.require(type(retired) is tuple and len(retired) == 11 and retired is self._retired_original,
                  "PROVIDER_CANCEL_RETIRE_BINDING")
        window, streams, native, pin, identity, handle, wire, output, thread, windows, phase = retired
        L.require(self.window is self._window_original is window and
            self._streams is self._streams_original is streams and
            self._native is self._native_original is native and
            self._pin is self._pin_original is pin and self._identity is self._identity_original is identity and
            self._handle is self._handle_original is handle and self._wire_seen is self._wire_original is wire and
            self._dup_output is output and self._thread is thread and self._windows is windows and
            all(actual is expected for actual, expected in zip(self._phase(), phase)),
            "PROVIDER_CANCEL_RETIRE_BINDING")
