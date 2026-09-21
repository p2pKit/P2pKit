"""Dormant original outer retirement and opaque worker transcripts, NOT admission.

No control-return parser, provider result, enclosing Node/runner outcome or
seal/upload is supplied here. In particular a zero worker exit is NOT provider
acceptance. The original supervisor must survive: losing it is terminal UNKNOWN.
All work spends the launcher's original180/shared final45; no timeout is renewed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
import threading

import hosted_cache_provider_launch as launch


QUARANTINE = []
_NAMES = ("directory", "home", "capture_directory", "bundle", "stdout", "stderr", "scope", "child")


@dataclass(frozen=True, repr=False)
class WorkerTranscript:
    worker_exit_code: int | None
    request: bytes = field(repr=False)
    stdout: bytes = field(repr=False)
    stderr: bytes = field(repr=False)
    native_retirement: bytes = field(repr=False)
    observed_ns: int
    closed_resources: tuple
    failed: bool
    scope: str = "OPAQUE_WORKER_TRANSCRIPT_ONLY_V1"
    provider_control_return: str = "NOT_OBSERVED"
    enclosing_step_outcome: str = "NOT_OBSERVED"
    provider_acceptance: str = "NOT_ESTABLISHED"


class ProviderSupervisor:
    """One fixed launch and its actual original owners; no supplied child/result.

    Transfer the two actual directory owners before run(). A completed transcript
    on a failure is accessible separately; run() still raises its first exception.
    Partial bytes remain private staging, never a completed transcript. An
    ambiguous acquisition/drain/read/close retains distinct enclosing owners.
    """
    def __init__(self):
        self.launch = launch.SupervisorLaunch()
        self._original = self.launch
        self._roster = self.launch._owners
        self._thread = threading.get_ident()
        self._started = self._finished = self._unknown = False
        self._primary = None
        self._errors = []
        self._owners = self._window = self._launch_error = None
        self._acquisitions = self._launch_attempts = None
        self._unreturned_acquisition = None
        self._returned_launch = self._launch_receipt = None
        self._request = self._cutoff = self._worker_local_end = None
        self._exit_code = self._transcript = None
        self._wait_return = None
        self._wait_started = False
        self._readers = {"stdout-reader": None, "stderr-reader": None}
        self._attempted = set()
        self._closed = []
        self._raw = {}

    @property
    def unknown(self):
        return self._unknown

    @property
    def transcript(self):
        launch.require(self._finished and not self._unknown and self._transcript is not None,
                       "SUPERVISOR_TRANSCRIPT_PENDING")
        return self._transcript

    def take_directories(self, directory, home):
        try:
            launch.require(not self._started and self.launch is self._original, "SUPERVISOR_ROOT_TRANSFER")
            self._original.take_directories(directory, home)
        except BaseException as error:
            self._failed("transfer", error)
            raise self._primary

    def _failed(self, stage, error, *, unknown=False):
        if self._primary is None:
            self._primary = error
        self._errors.append((stage, error))
        self._unknown |= unknown
        if not any(item is self for item in QUARANTINE):
            QUARANTINE.append(self)

    def _bindings(self):
        original = self._original
        launch.require(threading.get_ident() == self._thread and self.launch is original and
            original._owners is self._roster and tuple(self._roster) == _NAMES and
            all(self._roster[name] is owner and getattr(original, name) is owner for name, owner in self._owners) and
            original.window is self._window and original.original_error is self._launch_error and
            original.attempted is self._acquisitions and type(self._acquisitions) is set and
            self._acquisitions == self._launch_attempts and original._launch_return is self._launch_receipt and
            original._unreturned_acquisition is self._unreturned_acquisition,
            "SUPERVISOR_ORIGINAL_OWNERS_CHANGED")
        returned = self._returned_launch
        # A successful start cannot become a failed/no-return episode by
        # clearing the optional carrier slot that is being validated.
        if self._launch_error is None:
            launch.require(type(returned) is launch.WorkerLaunch and returned is self._launch_receipt and
                returned.child is original.child and type(returned.request) is bytes and
                returned.request is self._request, "SUPERVISOR_ORIGINAL_LAUNCH_RETURN_CHANGED")

    def _check(self):
        self._bindings()
        value = self._window.check(work=False)
        self._bindings()
        return value

    def _fence(self, boundary):
        primary, errors, prefix, observed_wait = boundary
        def same():
            launch.require(not self._unknown and self._primary is primary and self._errors is errors and
                len(errors) == len(prefix) and all(actual is prior for actual, prior in zip(errors, prefix)),
                "SUPERVISOR_FAILURE_BOUNDARY_CHANGED")
            request, cutoff, local_end, code = observed_wait
            launch.require(self._wait_return is observed_wait and self._request is request and
                self._cutoff == cutoff and self._worker_local_end == local_end and
                type(self._exit_code) is type(code) and self._exit_code == code,
                "SUPERVISOR_OBSERVATION_CHANGED")
        same()
        observed = self._check()
        same()
        return observed

    def _postcheck(self, stage):
        try:
            self._check()
            return True
        except BaseException as error:
            self._failed(stage, error)
            return False

    def _close(self, name, owner):
        if owner is None or name in self._attempted:
            return False
        before = self._postcheck(name + "-preclose")
        # Closing the original scope is a safety backstop even after UNKNOWN or
        # expiry, not a qualified retirement. Distinct file owners stay pinned.
        if name != "scope" and (not before or self._unknown):
            return False
        self._attempted.add(name)
        try:
            owner.close()
            self._closed.append(name)
        except BaseException as error:
            self._failed(name + "-close", error, unknown=True)
        after = self._postcheck(name + "-postclose")
        return before and after and name in self._closed and not self._unknown

    def _wait(self, child, cancelled):
        original = self._original
        role = self._window.clock.role
        launch._leader(original.scope, child, role)
        self._wait_started = True
        request, cutoff, local_end = self._request, self._cutoff, self._worker_local_end
        observed_code = None
        def checked():
            if self._primary is not None:
                raise self._primary
            def same():
                launch.require(self._cutoff == cutoff and self._worker_local_end == local_end,
                               "SUPERVISOR_ORIGINAL_WAIT_CHANGED")
                launch.require(self._request is request and type(self._exit_code) is type(observed_code) and
                    self._exit_code == observed_code, "SUPERVISOR_OBSERVATION_CHANGED")
            same()
            now = self._check()
            same()
            launch.require(now < cutoff and self._window.local_highest < local_end,
                           "SUPERVISOR_WORKER_CUTOFF")
            if self._primary is not None:
                raise self._primary
        try:
            while True:
                checked()
                cancelled()
                checked()
                for name in ("stdout", "stderr"):
                    owner = dict(self._owners)[name]
                    owner.observe_live_output() if role == "windows-x64" else owner.verify()
                    checked()
                observed_code = child.poll()  # Actual local return, before callbacks.
                self._exit_code = observed_code
                checked()
                if observed_code is not None:
                    launch.require(type(observed_code) is int and observed_code == 0, "SUPERVISOR_WORKER_FAILED")
                    return
                original.scope.discover()
                checked()
                remaining = local_end - self._window.local_highest
                launch.require(remaining > 0, "SUPERVISOR_WORKER_CUTOFF")
                launch.time.sleep(min(.025, remaining))
        finally:
            # No callback follows this write: later retirement receives actual
            # local observations, not mutable diagnostic slots or a supplied code.
            self._wait_return = (request, cutoff, local_end, observed_code)

    def _read(self, name, writer, boundary):
        try:
            self._fence(boundary)
            writer.sync()
            self._fence(boundary)
            before = writer.verify()
            self._fence(boundary)
            if self._window.clock.role == "windows-x64":
                raw = writer.read_provider_log()
                self._raw[name] = raw
            else:
                reader_name = name + "-reader"
                launch.require(self._readers[reader_name] is None, "SUPERVISOR_DUPLICATE_READER")
                reader = launch.files._posix_stream(writer.path,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, "rb")
                self._readers[reader_name] = reader  # Before any post-return check.
                self._fence(boundary)
                launch.require(launch.files._file_info(writer.path, reader, launch.lifecycle.LOG_BYTES) == before,
                               "SUPERVISOR_TRANSCRIPT_REPLACED")
                raw = reader.read(launch.lifecycle.LOG_BYTES + 1)
                self._raw[name] = raw
                self._fence(boundary)
                launch.require(launch.files._file_info(writer.path, reader, launch.lifecycle.LOG_BYTES) == before,
                               "SUPERVISOR_TRANSCRIPT_CHANGED")
                self._close(reader_name, reader)
            self._fence(boundary)
            launch.require(writer.verify() == before and type(raw) is bytes and
                len(raw) == before.size <= launch.lifecycle.LOG_BYTES, "SUPERVISOR_TRANSCRIPT_CHANGED")
            self._fence(boundary)
            return raw
        except BaseException as error:
            # In particular, an opener may have acquired an unreturned handle.
            # No note/parser can prove that provisional obligation was retired.
            self._failed(name + "-readback", error, unknown=True)
            raise

    def _finish(self):
        owners = dict(self._owners)
        scope = owners["scope"]
        observed_wait = self._wait_return
        boundary = (self._primary, self._errors, tuple(self._errors), observed_wait)
        retired, native = False, None
        if scope is not None:
            try:
                self._check()
                if self._wait_started:
                    launch._leader(scope, owners["child"], self._window.clock.role)
                remaining = self._window.local_end - self._window.local_highest
                launch.require(remaining > 0, "SUPERVISOR_ORIGINAL_END")
                survivors = scope.drain(grace=min(5.0, remaining),
                    kill_wait=min(5.0, max(0.0, remaining - 5.0)), deadline=self._window.local_end)
                launch.require(type(survivors) is list and survivors == [], "SUPERVISOR_SURVIVORS")
                description = scope.description()
                launch.require(description.get("discoveryErrors") == [] and
                    not getattr(scope, "pending_discoveries", {}), "SUPERVISOR_DISCOVERY_UNKNOWN")
                native = launch.files.encoded(description)
                self._raw["native"] = native
                self._check()
                retired = True
            except BaseException as error:
                self._failed("drain", error, unknown=True)
            closed = self._close("scope", scope)
            retired = retired and closed
        else:
            retired = "scope" not in self._original.attempted and not self._unknown
        if not retired:
            self._unknown = True
            return
        out = err = None
        try:
            if self._wait_started:
                self._fence(boundary)
                out = self._read("stdout", owners["stdout"], boundary)
                err = self._read("stderr", owners["stderr"], boundary)
        except BaseException as error:
            self._failed("capture", error)
        finally:
            for name in ("stderr-reader", "stdout-reader", "stderr", "stdout", "bundle", "capture_directory", "home", "directory"):
                if self._unknown:
                    break
                owner = self._readers[name] if name in self._readers else owners[name]
                if name not in self._attempted:
                    self._close(name, owner)
        # A launch failure before original wait still gets safe retirement, but
        # cannot supply a worker transcript. Child handles belong to scope.close.
        if not self._wait_started:
            return
        observed = self._fence(boundary)
        expected = {name for name, owner in self._owners if owner is not None and name != "child"}
        expected.update(name for name, owner in self._readers.items() if owner is not None)
        launch.require(set(self._closed) == expected and all(type(raw) is bytes for raw in (out, err, native)) and
            (self._exit_code is None or type(self._exit_code) is int), "SUPERVISOR_CLOSE_INCOMPLETE")
        transcript = WorkerTranscript(observed_wait[3], observed_wait[0], out, err, native, observed,
                                      tuple(self._closed), boundary[0] is not None)
        self._fence(boundary)  # Construction and final checks spend the original end.
        self._transcript = transcript

    def run(self, first, *, issued_ns, hard_end_ns, worker_cutoff_ns, phase, job, invocation, inner_invocation,
            plan, node, tool_path, cancelled):
        try:
            launch.require(not self._started and threading.get_ident() == self._thread and self.launch is self._original,
                           "SUPERVISOR_ONE_USE")
        except BaseException as error:
            self._failed("entry", error)
            raise self._primary
        self._started = True
        original = self._original
        try:
            if self._primary is not None:
                raise self._primary
            self._returned_launch = original.start(first, issued_ns=issued_ns, hard_end_ns=hard_end_ns, worker_cutoff_ns=worker_cutoff_ns,
                phase=phase, job=job, invocation=invocation, inner_invocation=inner_invocation,
                plan=plan, node=node, tool_path=tool_path, cancelled=cancelled)
        except BaseException as error:
            self._failed("launch", error)
        # Fixed original references, never a recreated native scope or a supplied
        # success record. A failed factory with no return remains UNKNOWN.
        self._owners = tuple((name, self._roster.get(name)) for name in _NAMES)
        self._window, self._launch_error = original.window, original.original_error
        self._acquisitions, self._launch_attempts = original.attempted, frozenset(original.attempted)
        self._unreturned_acquisition = original._unreturned_acquisition
        self._launch_receipt = original._launch_return
        try:
            if (self._unreturned_acquisition is not None or
                    any(name != "child" and self._roster.get(name) is None for name in self._launch_attempts)):
                self._failed("launch-acquisition", launch.ProviderLaunchError("SUPERVISOR_UNRETURNED_ACQUISITION"),
                             unknown=True)
            if self._primary is None:
                returned = self._returned_launch
                launch.require(type(returned) is launch.WorkerLaunch and returned is self._launch_receipt and
                    returned.child is self._roster["child"] and type(returned.request) is bytes,
                    "SUPERVISOR_ORIGINAL_LAUNCH_RETURN_CHANGED")
                # Retain the actual same-call return before the first callback-
                # bearing observation; worker_argv is only a diagnostic view.
                self._request = returned.request
            self._check()
            if self._primary is None:
                self._cutoff = worker_cutoff_ns
                launch.require(launch._ns(original.frame["workerCutoffNs"]) == self._cutoff,
                               "SUPERVISOR_ORIGINAL_CUTOFF_CHANGED")
                self._worker_local_end = math.nextafter(self._window.local_end -
                    (self._window.end - self._cutoff) / launch.clocks.NS, -math.inf)
                self._wait(returned.child, cancelled)
        except BaseException as error:
            self._failed("wait", error)
        finally:
            try:
                self._finish()
            except BaseException as error:
                self._failed("finish", error)
            self._finished = True
            if self._unknown and not any(item is self for item in QUARANTINE):
                QUARANTINE.append(self)
        if self._primary is not None:
            raise self._primary
        return self.transcript
