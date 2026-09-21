"""Dormant provider capture/retirement leaf, NOT an authenticated launcher.

The future fixed bridge must establish the original180 frame, safe Node/tools,
complete ownership-marker inheritance and its own remaining resource roster.
This module takes no argv, environment, credential or claimed step outcome.
Native deadlines are acceptance checks, not preemption: an external original-
domain watchdog is still required. No workflow or production caller uses this.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
from pathlib import Path, PureWindowsPath
import re
import threading
import time

import audit_processes as processes
import hosted_dependency_cache as cache
import hosted_job_clock as clocks
import hosted_test_query as files
import hosted_windows_evidence as diagnostics


FINAL_SECONDS = 45  # INSIDE original180, never an additional allowance.
LOG_BYTES = 1024 * 1024
COMMAND_BYTES = 4096
QUARANTINE = []


class ProviderLifecycleError(RuntimeError):
    """Fixed public-safe reason; captures/original exceptions remain private."""


def require(value, reason):
    if not value:
        raise ProviderLifecycleError(reason)


@dataclass(repr=False)
class _Slot:
    owner: object = None
    attempted: bool = False
    close_attempted: bool = False
    closed: bool = False


@dataclass(frozen=True, repr=False)
class CapturedProvider:
    phase: str
    exit_code: int
    command: bytes = field(repr=False)
    stdout: bytes = field(repr=False)
    stderr: bytes = field(repr=False)
    native_retirement: bytes = field(repr=False)
    outputs: tuple
    observed_ns: int
    closed_resources: tuple
    scope: str = "PROVIDER_CAPTURE_ONLY_PENDING_ENCLOSING_RETURN_V1"
    enclosing_owner_retirement: str = "NOT_OBSERVED"
    original_step_outcome: str = "NOT_OBSERVED"
    provider_acceptance: str = "NOT_ESTABLISHED"


class ProviderCapture:
    """One serialized same-call owner; no arbitrary-owner registry or launcher.

    Construction/entry are inert. Inside the active context, take_directory()
    commits transfer of the actual original object, then prepare() may allocate.
    Only the future fixed bridge may use scope/stdout/stderr and command_path to
    launch its authenticated supplier; wait() must receive that original child.
    The bridge must prove successful spawn return, exact sink/command routing
    and marker inheritance; leader membership below cannot establish those.
    Never serialize/reconstruct the LOCAL deadline or treat result as step success.
    """
    _NAMES = ("directory", "stdout", "stderr", "command", "scope",
              "command-reader", "stdout-reader", "stderr-reader")

    def __init__(self, first, *, issued_ns, hard_end_ns, local_end, phase, job, invocation, home, cancelled):
        clocks.validate_reading(first)
        clocks.integer(issued_ns)
        clocks.integer(hard_end_ns)
        require(issued_ns <= first.nanoseconds < hard_end_ns and
                FINAL_SECONDS * clocks.NS < hard_end_ns - issued_ns <= 180 * clocks.NS,
                "PROVIDER_ORIGINAL_WINDOW")
        require(type(local_end) is float and math.isfinite(local_end) and local_end > 0 and callable(cancelled),
                "PROVIDER_LOCAL_WINDOW")
        require(type(phase) is str and phase in ("save", "lookup") and
                all(type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value) for value in (job, invocation)),
                "PROVIDER_FIXED_IDENTITY")
        path_type = PureWindowsPath if first.clock.role == "windows-x64" else Path
        require(type(home) is str and path_type(home).is_absolute() and ".." not in path_type(home).parts and
                not any(ord(char) < 32 or ord(char) == 127 for char in home), "PROVIDER_OWNED_HOME")
        self._clock, self._clock_fields = first.clock, (first.clock.role, first.clock.domain, first.clock.ticks_per_second)
        self._highest, self._raw_end = first.nanoseconds, hard_end_ns
        self._local_end, self._work_local_end = local_end, None
        self._local_highest = 0.0
        self._thread, self._operation = threading.get_ident(), None
        self._phase, self._job, self._invocation, self._home = phase, job, invocation, home
        self._cancelled = cancelled
        self._slots = {name: _Slot() for name in self._NAMES}
        self._entered = self._active = self._finished = self._prepared = self._waited = False
        self._unknown, self._primary, self._errors = False, None, []
        self._child = self._exit_code = self._result = None
        self._native_retirement = None

    @property
    def unknown(self):
        return self._unknown

    @property
    def result(self):
        require(self._finished and self._operation is None and not self._unknown and
                self._primary is None and self._result is not None, "PROVIDER_RESULT_PENDING")
        return self._result

    @property
    def scope(self):
        self._begin("access")
        try:
            require(self._active and self._prepared, "PROVIDER_NOT_PREPARED")
            return self._slots["scope"].owner
        except BaseException as error:
            self._failed("access", error)
            raise
        finally:
            self._operation = None

    @property
    def stdout(self):
        self.scope
        return self._slots["stdout"].owner

    @property
    def stderr(self):
        self.scope
        return self._slots["stderr"].owner

    @property
    def command_path(self):
        self.scope
        return self._slots["command"].owner.path

    def __enter__(self):
        self._begin("enter")
        try:
            require(not self._entered, "PROVIDER_ONE_USE_ONLY")
            self._entered = self._active = True
            return self
        except BaseException as error:
            self._failed("enter", error)
            raise
        finally:
            self._operation = None

    def take_directory(self, directory):
        """Registration-only transfer; no fallible work follows the commit."""
        self._begin("transfer")
        try:
            expected = files.windows_files.PrivateDirectory if self._clock.role == "windows-x64" else files._PosixDirectory
            require(self._active and not self._prepared and self._slots["directory"].owner is None and
                    type(directory) is expected, "PROVIDER_DIRECTORY_TRANSFER")
            require((directory._closed if self._clock.role == "windows-x64" else directory.closed) is False,
                    "PROVIDER_DIRECTORY_CLOSED")
            self._slots["directory"].attempted = True
            self._slots["directory"].owner = directory
        except BaseException as error:
            self._failed("transfer", error)
            raise
        finally:
            self._operation = None

    def _healthy(self):
        if self._primary is not None:
            raise self._primary
        require(not self._unknown, "PROVIDER_RETIREMENT_UNKNOWN")

    def _begin(self, operation, *, cleanup=False):
        # A refused nested operation cannot clear the outer operation's guard
        # or mutate its active/finished/resource state, even if a callback catches it.
        try:
            require(threading.get_ident() == self._thread and self._operation is None, "PROVIDER_OPERATION_REENTRY")
            if not cleanup:
                self._healthy()
        except BaseException as error:
            self._failed(operation + "-entry", error)
            raise
        self._operation = operation

    def _failed(self, stage, error, *, unknown=False):
        if self._primary is None:
            self._primary = error
        self._unknown |= unknown
        try:
            self._unknown |= diagnostics._exception_detail(error)["retirementUnknown"]
        except BaseException:
            # Incomplete diagnostics cannot replace the original or permit more
            # ownership operations. Original error objects remain private below.
            self._unknown = True
        # Fixed operations/finite wait exits, not a per-poll event log.
        if len(self._errors) < 32:
            self._errors.append((stage, error))
        else:
            self._unknown = True

    def _quarantine(self):
        if self._unknown and not any(value is self for value in QUARANTINE):
            QUARANTINE.append(self)

    def _raw(self):
        require((self._clock.role, self._clock.domain, self._clock.ticks_per_second) == self._clock_fields,
                "PROVIDER_CLOCK_CHANGED")
        self._highest = clocks.checked_now(self._clock, minimum_ns=self._highest)
        return self._highest

    def _local(self):
        value = time.monotonic()
        require(type(value) in (int, float) and math.isfinite(value) and value >= self._local_highest,
                "PROVIDER_LOCAL_BACKWARDS_OR_INVALID")
        self._local_highest = value
        return value

    def _check(self, *, final=False, cleanup=False):
        if not cleanup:
            self._healthy()
        # RAW first, LOCAL second: RAW sampling itself spends the saved LOCAL end.
        now = self._raw()
        local = self._local()
        end = self._local_end if final else self._work_local_end
        require(local < end, "PROVIDER_LOCAL_EXPIRED")
        require(now < self._raw_end - (0 if final else FINAL_SECONDS * clocks.NS), "PROVIDER_RAW_EXPIRED")
        if not final:
            self._healthy()
            self._cancelled()
            self._healthy()
            # No new cancellation callback after its own original-end check.
            now = self._raw()
            local = self._local()
            require(local < end, "PROVIDER_LOCAL_EXPIRED")
            require(now < self._raw_end - FINAL_SECONDS * clocks.NS, "PROVIDER_RAW_EXPIRED")
        if not cleanup:
            self._healthy()
        return now

    def _acquire(self, name, factory, *, final=False):
        self._check(final=final)
        slot = self._slots[name]
        require(not slot.attempted, "PROVIDER_DUPLICATE_ALLOCATION")
        slot.attempted = True
        try:
            slot.owner = factory()  # First action on return: commit the original reference.
        except BaseException as error:
            self._failed(name + "-allocation", error, unknown=True)
            raise
        self._check(final=final)
        return slot.owner

    def prepare(self):
        self._begin("prepare")
        try:
            require(self._active and not self._prepared and self._primary is None and
                    self._slots["directory"].owner is not None, "PROVIDER_PREPARATION_STATE")
            # The sole conversion is LOCAL-before-RAW, and can only SHORTEN the
            # caller's original process-local end. It never mints another180.
            local = self._local()
            now = self._raw()
            require(now < self._raw_end, "PROVIDER_RAW_EXPIRED")
            converted = math.nextafter(local + math.nextafter((self._raw_end - now) / clocks.NS, 0.0), -math.inf)
            self._local_end = min(self._local_end, converted)
            self._work_local_end = self._local_end - FINAL_SECONDS
            self._check()
            directory = self._slots["directory"].owner
            directory.verify()
            for name in ("stdout", "stderr"):
                self._acquire(name, lambda name=name: directory.create_file("provider-" + name + ".log",
                    max_bytes=LOG_BYTES, deadline=self._local_end))
            maximum = 0 if self._phase == "save" else COMMAND_BYTES
            if self._clock.role == "windows-x64":
                self._acquire("command", lambda: directory.create_provider_command_file(
                    max_bytes=maximum, deadline=self._local_end))
            else:
                self._acquire("command", lambda: directory.create_file("provider-output.txt",
                    max_bytes=maximum, deadline=self._local_end))
            self._acquire("scope", lambda: processes.make_scope(self._job, self._invocation,
                str(directory.path), self._home))
            expected = (processes.WindowsScope if self._clock.role == "windows-x64" else
                        processes.LinuxScope if self._clock.role == "linux-x64" else processes.DarwinScope)
            require(type(self._slots["scope"].owner) is expected, "PROVIDER_NATIVE_SCOPE_TYPE")
            self._prepared = True
        except BaseException as error:
            self._failed("prepare", error)
            raise
        finally:
            self._operation = None

    def _leader(self, child):
        scope = self._slots["scope"].owner
        expected = processes.WindowsProcess if self._clock.role == "windows-x64" else processes.PosixProcess
        require(type(scope.leaders) is list and len(scope.leaders) == 1 and scope.leaders[0] is child and
                type(scope.launches) is list and len(scope.launches) == 1 and type(child) is expected and
                child.stdout is None and child.stderr is None, "PROVIDER_ORIGINAL_LEADER")
        # In particular this cannot prove POSIX marker inheritance. The fixed
        # bridge must establish that precondition before exposing any credential.

    def wait(self, child):
        self._begin("wait")
        try:
            require(self._active and self._prepared and self._primary is None and self._child is None,
                    "PROVIDER_WAIT_STATE")
            self._leader(child)
            self._child = child
            while True:
                self._check()
                for name in ("stdout", "stderr", "command"):
                    value = self._slots[name].owner
                    if self._clock.role == "windows-x64":
                        value.observe() if name == "command" else value.observe_live_output()
                    else:
                        value.verify()
                    self._check()
                code = child.poll()
                if code is not None:
                    self._exit_code = code  # Before ANY later fallible observation.
                self._check()
                if code is not None:
                    require(type(code) is int and code == 0, "PROVIDER_CHILD_FAILED")
                    self._waited = True
                    return code
                self._slots["scope"].owner.discover()
                self._check()
                remaining = self._work_local_end - self._local()
                require(remaining > 0, "PROVIDER_LOCAL_EXPIRED")
                self._healthy()
                time.sleep(min(.025, remaining))
        except BaseException as error:
            self._failed("wait", error)
            raise
        finally:
            self._operation = None

    def _postcheck(self, stage):
        try:
            self._check(final=True, cleanup=True)
        except BaseException as error:
            self._failed(stage, error)
            return False
        return True

    def _close(self, name):
        slot = self._slots[name]
        if slot.owner is None or slot.close_attempted:
            return False
        before = self._postcheck(name + "-preclose")  # Does not skip independently safe cleanup.
        if name != "scope" and self._unknown:
            return False
        slot.close_attempted = True
        try:
            slot.owner.close()
            slot.closed = True
        except BaseException as error:
            self._failed(name + "-close", error, unknown=True)
        after = self._postcheck(name + "-postclose")
        return before and after and slot.closed and not self._unknown

    def _freeze_command(self):
        """Commit both sides of the fixed native handoff before postchecks."""
        self._check(final=True)
        reader, command = self._slots["command-reader"], self._slots["command"]
        require(not reader.attempted, "PROVIDER_DUPLICATE_ALLOCATION")
        reader.attempted = True
        try:
            reader.owner = command.owner.freeze()
        except BaseException as error:
            self._failed("command-reader-allocation", error, unknown=True)
            raise
        # Successful maintained freeze returns only after its own original close.
        # Register the reader FIRST and record that close before a clock callback.
        command.close_attempted = True
        command.closed = command.owner._closed is True
        if not command.closed:
            error = ProviderLifecycleError("PROVIDER_FREEZE_NOT_CLOSED")
            self._failed("freeze-return", error, unknown=True)
            raise error
        self._check(final=True)
        return reader.owner

    def _capture(self, name, expected, maximum):
        directory = self._slots["directory"].owner
        filename = "provider-output.txt" if name == "command" else "provider-" + name + ".log"
        slot_name = name + "-reader"
        if self._clock.role == "windows-x64":
            reader = self._acquire(slot_name, lambda: directory.open_file(filename,
                max_bytes=maximum, deadline=self._local_end), final=True)
            before = reader.verify()
            self._check(final=True)
            # Windows may defer timestamps until the writer closes. This binds
            # identity/size and the new strict-reader interval, NOT an immutable
            # transcript across the close/reopen gap or same-size overwrite.
            require(before.identity == expected.identity and before.size == expected.size, "PROVIDER_CAPTURE_REPLACED")
            raw = reader.read()
            self._check(final=True)
            require(reader.verify() == before, "PROVIDER_CAPTURE_CHANGED")
        else:
            reader = self._acquire(slot_name, lambda: files._posix_stream(directory.path / filename,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, "rb"), final=True)
            before = files._file_info(directory.path / filename, reader, maximum)
            self._check(final=True)
            require(before == expected, "PROVIDER_CAPTURE_REPLACED")
            raw = reader.read(maximum + 1)
            self._check(final=True)
            require(files._file_info(directory.path / filename, reader, maximum) == before, "PROVIDER_CAPTURE_CHANGED")
        self._check(final=True)
        require(type(raw) is bytes and len(raw) == before.size and len(raw) <= maximum, "PROVIDER_CAPTURE_SIZE")
        directory.verify()
        self._check(final=True)
        return raw

    def __exit__(self, kind, error, traceback):
        self._begin("exit", cleanup=True)
        try:
            return self._finish(error)
        except BaseException as secondary:
            self._failed("exit", secondary)
            self._quarantine()
            raise self._primary
        finally:
            self._operation = None

    def _finish(self, error):
        require(self._active and not self._finished, "PROVIDER_ONE_EXIT_ONLY")
        self._active, self._finished = False, True
        if error is not None:
            self._failed("body", error)
        raw_command = out = err = None
        scope, retired = self._slots["scope"].owner, False
        try:
            if self._primary is None:
                require(self._prepared and self._waited, "PROVIDER_WAIT_REQUIRED")
                self._leader(self._child)  # A second launch after wait is not hidden.
        except BaseException as secondary:
            self._failed("exit-state", secondary)
        if scope is not None:
            try:
                self._check(final=True, cleanup=True)
                remaining = self._local_end - self._local()
                require(remaining > 0, "PROVIDER_LOCAL_EXPIRED")
                survivors = scope.drain(grace=min(5.0, remaining),
                    kill_wait=min(5.0, max(0.0, remaining - 5.0)), deadline=self._local_end)
                require(type(survivors) is list and survivors == [], "PROVIDER_SURVIVORS")
                description = scope.description()
                require(description.get("discoveryErrors") == [] and
                        not getattr(scope, "pending_discoveries", {}), "PROVIDER_DISCOVERY_UNKNOWN")
                self._native_retirement = files.encoded(description)
                self._check(final=True, cleanup=True)
                retired = True
            except BaseException as secondary:
                self._failed("drain", secondary, unknown=True)
            scope_close_qualified = self._close("scope")
            retired = retired and scope_close_qualified
        else:
            # No returned scope is not proof that a failed constructor retired.
            retired = not self._slots["scope"].attempted and not self._unknown
        if retired:
            try:
                if self._primary is None:
                    self._check(final=True)
                    if self._clock.role == "windows-x64":
                        reader = self._freeze_command()
                        before = reader.verify()
                        self._check(final=True)
                        raw_command = reader.read()
                        self._check(final=True)
                        require(reader.verify() == before and type(raw_command) is bytes and
                                len(raw_command) == before.size <= (0 if self._phase == "save" else COMMAND_BYTES),
                                "PROVIDER_CAPTURE_CHANGED")
                        self._check(final=True)
                    for name in ("stdout", "stderr", *(("command",) if self._clock.role != "windows-x64" else ())):
                        stream = self._slots[name].owner
                        self._check(final=True)
                        stream.sync()
                        self._check(final=True)
                        info = stream.verify()
                        self._check(final=True)
                        self._close(name)
                        require(not self._unknown and self._primary is None, "PROVIDER_CAPTURE_CLOSE_FAILED")
                        maximum = (0 if self._phase == "save" else COMMAND_BYTES) if name == "command" else LOG_BYTES
                        raw = self._capture(name, info, maximum)
                        if name == "stdout":
                            out = raw
                        elif name == "stderr":
                            err = raw
                        else:
                            raw_command = raw
            except BaseException as secondary:
                self._failed("capture", secondary)
            finally:
                # Internal supplier cleanup may attempt all its own pins. That
                # does NOT authorize closing distinct outer owners after UNKNOWN.
                for name in ("stderr-reader", "stdout-reader", "command-reader", "command", "stderr", "stdout", "directory"):
                    if self._unknown:
                        break
                    self._close(name)
        else:
            self._unknown = True  # Do not release files beneath an uncertain writer.
        self._postcheck("last-owner-postclose")
        self._quarantine()
        if self._primary is not None:
            raise self._primary
        require(not self._unknown and all(slot.closed for slot in self._slots.values() if slot.owner is not None),
                "PROVIDER_OWNER_CLOSE_INCOMPLETE")
        try:
            self._check(final=True)
            outputs = cache.provider_command_outputs(raw_command, phase=self._phase, role=self._clock.role)
            self._check(final=True)
            self._cancelled()
            observed = self._check(final=True)
            result = CapturedProvider(self._phase, self._exit_code, raw_command, out, err, self._native_retirement,
                tuple(sorted(outputs.items())), observed,
                tuple(name for name, slot in self._slots.items() if slot.owner is not None and slot.closed))
            self._check(final=True)  # Sorting/construction also spends the original end.
            self._result = result
        except BaseException as secondary:
            self._failed("result", secondary)
            raise
        return False
