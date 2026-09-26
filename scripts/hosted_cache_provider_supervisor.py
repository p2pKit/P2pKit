"""Dormant original retirement, worker transcripts and private result transport.

No enclosing Node/runner outcome or seal/upload is supplied here. In particular
a transported capture or zero worker exit is NOT provider acceptance. The
original supervisor must survive: losing it is terminal UNKNOWN.
All work spends the launcher's original180/shared final45; no timeout is renewed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
import sys
import threading

import hosted_cache_provider_launch as launch
import hosted_cache_provider_supervisor_return as outer_return


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
    provider_return: launch.transport.TransportedProvider | None = field(default=None, repr=False)
    scope: str = "WORKER_TRANSCRIPT_WITH_OPTIONAL_TRANSPORT_V1"
    provider_control_return: str = "NOT_OBSERVED"
    enclosing_step_outcome: str = "NOT_OBSERVED"
    provider_acceptance: str = "NOT_ESTABLISHED"


@dataclass(frozen=True, repr=False)
class _Invocation:
    request: bytes = field(repr=False)


@dataclass(frozen=True, repr=False)
class _Completion:
    invocation: _Invocation = field(repr=False)
    transcript: WorkerTranscript = field(repr=False)
    references: tuple = field(repr=False)
    error: BaseException | None = field(repr=False)
    check: object = field(repr=False)


@dataclass(frozen=True, repr=False)
class _Send:
    completion: _Completion = field(repr=False)
    acknowledgement: bytes = field(repr=False)
    check: object = field(repr=False)


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
        self._qualified_wait = None
        self._wait_started = False
        self._readers = {"stdout-reader": None, "stderr-reader": None, "packet-reader": None}
        self._attempted = set()
        self._closed = []
        self._raw = {}
        self._retirement_writer = None
        self._retirement_owner = None
        self._retirement_started = False
        self._invocation = self._invocation_binding = self._completion = None
        self._send_started = self._exit_started = False
        self._send_receipt = None
        self._argv = self._cwd = self._pid = None

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

    def take_window(self, window):
        try:
            launch.require(not self._started and self.launch is self._original, "SUPERVISOR_WINDOW_TRANSFER")
            self._original.take_window(window)
        except BaseException as error:
            self._failed("window-transfer", error)
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
            self._invocation is self._invocation_binding and type(self._invocation) is _Invocation and
            self._retirement_writer is self._retirement_owner and
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
                returned.request is self._request and returned.argv is self._argv and returned.cwd is self._cwd and
                type(returned.pid) is int and type(original.child.pid) is int and
                returned.pid == self._pid == original.child.pid,
                "SUPERVISOR_ORIGINAL_LAUNCH_RETURN_CHANGED")

    def _check(self):
        self._bindings()
        value = self._window.check(work=False)
        self._bindings()
        return value

    def _fence(self, boundary):
        primary, errors, prefix, observed_wait, qualified_wait = boundary
        def same():
            launch.require(not self._unknown and self._primary is primary and self._errors is errors and
                len(errors) == len(prefix) and all(actual is prior for actual, prior in zip(errors, prefix)),
                "SUPERVISOR_FAILURE_BOUNDARY_CHANGED")
            request, cutoff, local_end, code = observed_wait
            launch.require(self._wait_return is observed_wait and self._request is request and
                self._cutoff == cutoff and self._worker_local_end == local_end and
                type(self._exit_code) is type(code) and self._exit_code == code and
                self._qualified_wait is qualified_wait and (qualified_wait is None or qualified_wait is observed_wait),
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
        qualified = False
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
                    launch.require(type(observed_code) is int, "SUPERVISOR_WORKER_FAILED")
                    qualified = True  # Only AFTER original post-poll cutoff/binding checks.
                    launch.require(observed_code == 0, "SUPERVISOR_WORKER_FAILED")
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
            self._qualified_wait = self._wait_return if qualified else None

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
            reference = outer_return.reference(raw, before, self._window.clock.role, name)
            self._fence(boundary)
            return raw, reference
        except BaseException as error:
            # In particular, an opener may have acquired an unreturned handle.
            # No note/parser can prove that provisional obligation was retired.
            self._failed(name + "-readback", error, unknown=True)
            raise

    def _read_packet(self, ack, boundary):
        try:
            self._fence(boundary)
            directory = dict(self._owners)["directory"]
            role = self._window.clock.role
            launch.require(self._readers["packet-reader"] is None, "SUPERVISOR_DUPLICATE_READER")
            path = directory.path / launch.transport.PACKET_NAME
            reader = (directory.open_file(launch.transport.PACKET_NAME, max_bytes=launch.transport.PACKET_BYTES,
                deadline=self._window.local_end) if role == "windows-x64" else
                launch.files._posix_stream(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, "rb"))
            self._readers["packet-reader"] = reader  # Actual return, before callbacks.
            self._fence(boundary)
            def info():
                return reader.verify() if role == "windows-x64" else launch.files._file_info(path, reader, launch.transport.PACKET_BYTES)
            before = info()
            self._fence(boundary)
            launch.require(before.size == ack.packet_bytes and
                launch.transport.file_identity(before, role) == ack.packet_identity, "SUPERVISOR_PACKET_REPLACED")
            raw = reader.read(launch.transport.PACKET_BYTES + 1)
            self._raw["packet"] = raw
            self._fence(boundary)
            launch.require(info() == before and type(raw) is bytes and len(raw) == before.size and
                launch.hashlib.sha256(raw).hexdigest() == ack.packet_sha256, "SUPERVISOR_PACKET_CHANGED")
            directory.verify()
            self._fence(boundary)
            self._close("packet-reader", reader)
            self._fence(boundary)
            reference = outer_return.reference(raw, before, role, "packet")
            self._fence(boundary)
            return raw, reference
        except BaseException as error:
            self._failed("packet-readback", error, unknown=True)
            raise

    def _persist_native(self, native, boundary):
        """Persist the actual retained description AFTER known original close.

        No new scope, path-selected writer, packet copy, or later reopen. A lost
        acquisition or any ambiguous finalization leaves distinct roots pinned.
        """
        try:
            self._fence(boundary)
            launch.require(not self._retirement_started and self._retirement_writer is None and
                "scope" in self._closed and type(native) is bytes and 0 < len(native) <= outer_return.NATIVE_BYTES,
                "SUPERVISOR_RETIREMENT_WRITER")
            self._retirement_started = True
            directory = dict(self._owners)["directory"]
            writer = directory.create_file(outer_return.NATIVE_NAME, max_bytes=outer_return.NATIVE_BYTES,
                                           deadline=self._window.local_end)
            self._retirement_writer = writer  # Actual return, before all callbacks.
            self._retirement_owner = writer
            launch.require(writer is not None, "SUPERVISOR_RETIREMENT_WRITER_NOT_RETURNED")
            def checked():
                launch.require(self._retirement_writer is writer and self._retirement_started,
                               "SUPERVISOR_RETIREMENT_WRITER_CHANGED")
                self._fence(boundary)
                launch.require(self._retirement_writer is writer and self._retirement_started,
                               "SUPERVISOR_RETIREMENT_WRITER_CHANGED")
            checked()
            before = writer.verify()
            identity = launch.transport.file_identity(before, self._window.clock.role)
            checked()
            count = writer.write(native)
            checked()
            launch.require(type(count) is int and count == len(native), "SUPERVISOR_RETIREMENT_WRITE")
            writer.sync()
            checked()
            after = writer.verify()
            checked()
            launch.require(before.size == 0 and after.size == len(native) and
                launch.transport.file_identity(after, self._window.clock.role) == identity,
                "SUPERVISOR_RETIREMENT_CHANGED")
            reference = outer_return.reference(native, after, self._window.clock.role, "native")
            checked()
            launch.require(self._close("retirement-writer", writer), "SUPERVISOR_RETIREMENT_CLOSE")
            checked()
            return reference
        except BaseException as error:
            self._failed("retirement-write", error, unknown=True)
            raise

    def _native_request(self, native, child):
        """Bind actual launch-description bytes to the retained pre-spawn vector.

        Later readers can recover the exact request string from this same file;
        no command-line reverse parsing or reconstructed frame is necessary.
        """
        value = launch.transport._parse(native, outer_return.NATIVE_BYTES)
        role = self._window.clock.role
        backend, api, output = ("windows-job-list-suspended", "CreateProcessW", "caller-owned-native-files") if role == "windows-x64" else (
            "linux-proc-pidfd" if role == "linux-x64" else "darwin-libproc-audit-token",
            "subprocess.Popen", "caller-owned-files")
        context, _ = outer_return._context(self._invocation.request)
        launch.require(value.get("backend") == backend and value.get("invocation") == context["outerId"] and
            value.get("job") == context["job"] and type(value.get("launches")) is list and
            len(value["launches"]) == 1, "SUPERVISOR_NATIVE_LAUNCH")
        record, argv = value["launches"][0], self._argv
        launch.require(type(argv) is tuple and len(argv) == 7 and all(type(arg) is str for arg in argv) and
            argv[1:4] == ("-I", "-B", "-S") and
            launch._path(argv[4], role).name == "hosted_cache_provider_worker.py" and
            type(record) is dict and record.get("requestedArgv") == list(argv) and
            record.get("api") == api and record.get("created") is True and
            type(record.get("pid")) is int and record["pid"] == self._pid and child.pid == self._pid and
            record.get("cwd") == self._cwd and record.get("outputMode") == output,
            "SUPERVISOR_NATIVE_LAUNCH")
        resolved = record.get("resolvedArgv")
        launch.require(type(resolved) is list and len(resolved) == 7 and all(type(arg) is str for arg in resolved) and
            resolved == list(argv), "SUPERVISOR_NATIVE_RESOLVED_ARGV")
        launch._path(resolved[0], role)
        if role == "windows-x64":
            launch.require(record.get("resumed") is True and record.get("batch") is False and
                record.get("applicationName") == resolved[0] and
                record.get("commandLine") == launch.subprocess.list2cmdline(resolved),
                "SUPERVISOR_NATIVE_WINDOWS_FRAMING")
        else:
            launch.require(record.get("shell") is False and record.get("executable") == resolved[0],
                           "SUPERVISOR_NATIVE_POSIX_FRAMING")
        raw = record["requestedArgv"][-1].encode("ascii")  # Exact original string, never reserialization.
        launch.require(0 < len(raw) <= 16 * 1024 and raw == self._request,
                       "SUPERVISOR_NATIVE_REQUEST_CHANGED")

    def _finish(self):
        owners = dict(self._owners)
        scope = owners["scope"]
        observed_wait = self._wait_return
        boundary = (self._primary, self._errors, tuple(self._errors), observed_wait, self._qualified_wait)
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
                if self._wait_started:
                    self._native_request(native, owners["child"])
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
        out = err = provider_return = control_error = None
        native_ref = out_ref = err_ref = packet_ref = None
        try:
            if self._wait_started:
                self._fence(boundary)
                native_ref = self._persist_native(native, boundary)
                out, out_ref = self._read("stdout", owners["stdout"], boundary)
                err, err_ref = self._read("stderr", owners["stderr"], boundary)
                try:
                    self._fence(boundary)
                    launch.require(boundary[4] is observed_wait and observed_wait[3] in (0, launch.transport.FAILED_CAPTURE_EXIT),
                                   "SUPERVISOR_RETURN_WAIT_UNQUALIFIED")
                    ack = launch.transport.read_ack(out, observed_wait[0])
                    self._fence(boundary)
                    raw, packet_ref = self._read_packet(ack, boundary)
                    provider_return = launch.transport.decode(raw, ack, observed_wait[0], observed_wait[3])
                    now = self._fence(boundary)
                    launch.require(provider_return.observed_ns <= now, "SUPERVISOR_RETURN_FUTURE_CAPTURE")
                except BaseException as error:
                    provider_return, control_error = None, error
                    # Pure framing/interpretation failures still permit known
                    # original closes and an opaque failed transcript. I/O
                    # ambiguity has already latched UNKNOWN in _read_packet.
        except BaseException as error:
            self._failed("capture", error)
        finally:
            for name in ("packet-reader", "stderr-reader", "stdout-reader", "stderr", "stdout", "bundle", "capture_directory", "home", "directory"):
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
        expected.add("retirement-writer")
        launch.require(set(self._closed) == expected and all(type(raw) is bytes for raw in (out, err, native)) and
            (self._exit_code is None or type(self._exit_code) is int), "SUPERVISOR_CLOSE_INCOMPLETE")
        transcript = WorkerTranscript(observed_wait[3], observed_wait[0], out, err, native, observed,
            tuple(self._closed), boundary[0] is not None or control_error is not None, provider_return,
            provider_control_return="TRANSPORTED_OBSERVATION_ONLY" if provider_return is not None else "NOT_OBSERVED")
        self._fence(boundary)  # Construction and final checks spend the original end.
        self._transcript = transcript
        if control_error is not None:
            self._failed("control-return", control_error)
        return transcript, (native_ref, out_ref, err_ref, packet_ref), boundary[0] if boundary[0] is not None else control_error

    def _complete(self, finished, invocation):
        """Bind the actual _finish return, not a later-selected diagnostic slot."""
        transcript, references, original_error = finished
        launch.require(self._primary is original_error, "SUPERVISOR_RETURN_ERROR_CHANGED")
        boundary = (self._primary, self._errors, tuple(self._errors), self._wait_return, self._qualified_wait)
        readers, reader_owners = self._readers, tuple(self._readers.items())
        writer = self._retirement_writer
        closed, closes = self._closed, tuple(self._closed)
        attempted, attempts = self._attempted, frozenset(self._attempted)
        completion = None
        def same():
            launch.require(self._finished and self._invocation is invocation and self._transcript is transcript and
                self._completion is completion and self._readers is readers and
                tuple(readers) == tuple(name for name, _ in reader_owners) and
                all(readers[name] is owner for name, owner in reader_owners) and
                self._retirement_writer is writer and self._retirement_started and
                self._closed is closed and tuple(closed) == closes and self._attempted is attempted and
                attempted == attempts and transcript.failed == (boundary[0] is not None),
                "SUPERVISOR_RETURN_COMPLETION_CHANGED")
        def checked():
            same()
            observed = self._fence(boundary)
            same()
            return observed
        checked()
        pending = _Completion(invocation, transcript, references, original_error, checked)
        checked()
        completion = pending
        self._completion = completion  # Final publication, with no following callback.

    def run_and_send(self, first, **values):
        """Own the original run return/raise before the fixed stdout handoff.

        Dormant internal entry, not an admitted CLI. The future original Node
        child must also observe asynchronous close and matching exit; ACK alone
        cannot establish timely enclosing return or supervisor survival.
        """
        error = None
        try:
            launch.require(not self._send_started, "SUPERVISOR_RETURN_ONE_SEND")
            self._send_started = True
            stdout, sink = sys.stdout, sys.stdout.buffer
            descriptor = sink.fileno()
            launch.require(type(descriptor) is int and descriptor == 1, "SUPERVISOR_RETURN_STDOUT")
            result = error = None
            try:
                result = self.run(first, **values)
            except BaseException as original:
                error = original
            completion = self._completion
            launch.require(type(completion) is _Completion and
                ((error is None and completion.error is None and result is completion.transcript) or
                 (error is not None and result is None and error is completion.error)),
                "SUPERVISOR_RETURN_ORIGINAL_RETURN")
            receipt = None
            def checked():
                completion.check()
                descriptor = sink.fileno()
                launch.require(self._completion is completion and self._send_receipt is receipt and
                    self._send_started and sys.stdout is stdout and stdout.buffer is sink and
                    type(descriptor) is int and descriptor == 1,
                    "SUPERVISOR_RETURN_STDOUT_CHANGED")
                completion.check()
                launch.require(self._send_receipt is receipt and sys.stdout is stdout and stdout.buffer is sink,
                               "SUPERVISOR_RETURN_STDOUT_CHANGED")
            checked()
            raw = outer_return.acknowledge(completion.invocation.request, completion.transcript.request,
                                           completion.transcript, completion.references)
            checked()
            count = sink.write(raw)
            checked()
            launch.require(type(count) is int and count == len(raw), "SUPERVISOR_RETURN_ACK_WRITE")
            sink.flush()  # Pipe transport: flush Python buffering, never fsync a pipe.
            checked()
            pending = _Send(completion, raw, checked)
            checked()
            receipt = pending
            self._send_receipt = receipt
        except BaseException as secondary:
            self._failed("send", secondary)
            if error is not None:
                raise error
            raise self._primary
        if error is not None:
            raise error  # Intended original failure, not a new finalization error.
        return result

    def exit_code(self, result, error):
        """Once-only classification for the future original enclosing entry."""
        receipt = self._send_receipt
        try:
            launch.require(not self._exit_started, "SUPERVISOR_RETURN_EXIT_ONCE")
            self._exit_started = True
            launch.require(type(receipt) is _Send and
                ((error is None and result is receipt.completion.transcript and receipt.completion.error is None) or
                 (error is not None and result is None and error is receipt.completion.error)),
                "SUPERVISOR_RETURN_INCOMPLETE")
            receipt.check()
            launch.require(self._send_receipt is receipt, "SUPERVISOR_RETURN_RECEIPT_CHANGED")
            return 0 if error is None else outer_return.FAILED_EXIT
        except BaseException as secondary:
            self._failed("exit", secondary)
            if type(receipt) is _Send and receipt.completion.error is not None:
                raise receipt.completion.error
            raise self._primary

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
        finished = invocation_request = None
        try:
            if self._primary is not None:
                raise self._primary
            # Establish the distinct OUTER invocation from original arguments
            # before any launch callback. Never select it from a worker receipt.
            value = {"schema": "P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1", "role": first.clock.role,
                "frequency": first.clock.ticks_per_second, "firstNs": str(first.nanoseconds),
                "issuedNs": str(issued_ns), "hardEndNs": str(hard_end_ns), "workerCutoffNs": str(worker_cutoff_ns),
                "phase": phase, "job": job, "outerId": invocation, "innerId": inner_invocation,
                "directory": str(original.directory.path), "directoryIdentity": list(original.directory.identity),
                "home": str(original.home.path), "homeIdentity": list(original.home.identity),
                "node": node, "toolPath": tool_path, "plan": plan}
            invocation_request = _Invocation(launch._json(value).encode("ascii"))
            detached, _ = outer_return._context(invocation_request.request)
            self._invocation = self._invocation_binding = invocation_request
            self._returned_launch = original.start(first, issued_ns=issued_ns, hard_end_ns=hard_end_ns, worker_cutoff_ns=worker_cutoff_ns,
                phase=phase, job=job, invocation=invocation, inner_invocation=inner_invocation,
                plan=detached["plan"], node=node, tool_path=tool_path, cancelled=cancelled)
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
                self._argv, self._cwd, self._pid = returned.argv, returned.cwd, returned.pid
                worker_frame = launch.worker_source.record(returned.request.decode("ascii"))
                launch.require(self._invocation is invocation_request and all(worker_frame.get(name) == value
                    for name, value in detached.items() if name not in ("schema", "firstNs")),
                    "SUPERVISOR_RETURN_INVOCATION_CHANGED")
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
                finished = self._finish()
            except BaseException as error:
                self._failed("finish", error)
            self._finished = True
            if self._unknown and not any(item is self for item in QUARANTINE):
                QUARANTINE.append(self)
        if finished is not None:
            try:
                self._complete(finished, invocation_request)
            except BaseException as error:
                self._failed("completion", error)
        if self._primary is not None:
            raise self._primary
        return self.transcript
