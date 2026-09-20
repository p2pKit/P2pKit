#!/usr/bin/env python3
"""Native-owned, private, read-only Git queries for ordinary hosted admission.

This is an ACTUAL process-owner binding, not a Git/process mock or a build driver.
It uses audit_processes' native backend and supplied private sinks. It runs no
Gradle/GPG, installs no policy, uploads nothing and grants no build/test acceptance.
NativeGitQueries is one-shot after any failure, single-threaded, and retains all
original captures. UNKNOWN is sticky: pins/sinks remain quarantined and no later
query or successful return is allowed. A surrounding controller still must prove
its own post-return seal before publishing any evidence.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import sys
import threading
import time
import uuid

sys.dont_write_bytecode = True
import audit_processes as processes
import hosted_evidence as posix_files
import hosted_test_identity as identity
import hosted_windows_files as windows_files

MAX_QUERIES = 64
MAX_RECEIPT_BYTES = 2 * 1024 * 1024
MAX_SESSION_BYTES = 64 * 1024 * 1024
FINALIZATION_SECONDS = 45
QUARANTINE = []
_CONTEXT = (processes.JOB_ENV, processes.CHAIN_ENV, processes.DOMAINS_ENV,
            processes.STATE_ENV, "GRADLE_USER_HOME")
_ROLES = {"linux-x64": ("Linux", "X64"), "windows-x64": ("Windows", "X64"),
          "macos-arm64": ("macOS", "ARM64"), "macos-x64": ("macOS", "X64")}


class QueryError(RuntimeError):
    """Fixed public-safe reason; original exceptions/captures stay private."""


def require(value, code):
    if not value:
        raise QueryError(code)


def encoded(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    require(len(raw) <= MAX_RECEIPT_BYTES, "QUERY_RECEIPT_LIMIT")
    return raw


def _component(value):
    require(type(value) is str and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,100}", value), "QUERY_COMPONENT")
    return value


@dataclasses.dataclass(frozen=True)
class _PosixInfo:
    device: int
    inode: int
    size: int
    mtime_ns: int
    ctime_ns: int

    def as_dict(self):
        return dataclasses.asdict(self)


def _file_info(path, stream, maximum):
    before = path.lstat()
    opened = os.fstat(stream.fileno())
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid() and
            not before.st_mode & 0o077 and os.path.samestat(before, opened) and
            0 <= before.st_size == opened.st_size <= maximum, "QUERY_PRIVATE_FILE_CHANGED")
    return _PosixInfo(opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)


def _posix_stream(path, flags, mode):
    """Transfer a new descriptor only after fdopen returns; never leak on failure."""
    descriptor = os.open(path, flags, 0o600)
    try:
        return os.fdopen(descriptor, mode)
    except BaseException as original:
        try:
            os.close(descriptor)
        except BaseException as secondary:
            original.__notes__ = [*getattr(original, "__notes__", ()),
                "POSIX descriptor adoption retirement UNKNOWN: " + processes.format_ownership_error(secondary)]
        raise


class _PosixSink:
    """A regular POSIX sink; never used as a Windows CRT/native-handle adapter."""

    def __init__(self, parent, name, maximum, deadline):
        self.parent, self.path = parent, parent.path / _component(name)
        self.maximum, self.deadline = maximum, deadline
        self.stream = _posix_stream(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, "wb")
        self.closed = False
        try:
            self.original = os.fstat(self.stream.fileno())
        except BaseException as original:
            self.closed = True
            try:
                self.stream.close()
            except BaseException as secondary:
                original.__notes__ = [*getattr(original, "__notes__", ()),
                    "POSIX sink allocation close: " + processes.format_ownership_error(secondary)]
            raise original

    def fileno(self):
        require(not self.closed, "QUERY_SINK_CLOSED")
        return self.stream.fileno()

    def verify(self):
        posix_files._deadline(self.deadline)
        self.parent.verify()
        info = _file_info(self.path, self.stream, self.maximum)
        require((info.device, info.inode) == (self.original.st_dev, self.original.st_ino), "QUERY_SINK_REPLACED")
        return info

    def write(self, raw):
        self.verify()
        require(self.stream.tell() + len(raw) <= self.maximum, "QUERY_SINK_LIMIT")
        return self.stream.write(raw)

    def sync(self):
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def close(self):
        if not self.closed:
            self.closed = True  # Ambiguous close must never be retried.
            self.stream.close()


class _PosixDirectory:
    """Uses the retained POSIX private-path contract; no process ownership logic."""

    def __init__(self, path):
        self.path = posix_files._private_directory(path)
        self.identity = posix_files._identity(self.path)
        self.closed = False

    def verify(self):
        require(not self.closed, "QUERY_DIRECTORY_CLOSED")
        posix_files._private_directory(self.path)
        require(posix_files._identity(self.path) == self.identity, "QUERY_DIRECTORY_REPLACED")

    def create_directory(self, name, *, deadline):
        posix_files._deadline(deadline)
        self.verify()
        path = self.path / _component(name)
        path.mkdir(mode=0o700)
        return _PosixDirectory(path)

    def create_file(self, name, *, max_bytes, deadline):
        self.verify()
        return _PosixSink(self, name, max_bytes, deadline)

    def read_bytes(self, name, *, max_bytes, deadline):
        posix_files._deadline(deadline)
        self.verify()
        path = self.path / _component(name)
        stream = _posix_stream(path, os.O_RDONLY | os.O_NOFOLLOW, "rb")
        original = None
        try:
            before = _file_info(path, stream, max_bytes)
            raw = stream.read(max_bytes + 1)
            require(before == _file_info(path, stream, max_bytes) and len(raw) == before.size,
                    "QUERY_CAPTURE_CHANGED")
        except BaseException as error:
            original = error
        finally:
            # Explicit reader ownership: a read/verify failure never skips close,
            # and a secondary ambiguous close never replaces the original error.
            try:
                stream.close()
            except BaseException as secondary:
                if original is None:
                    original = secondary
                else:
                    original.__notes__ = [*getattr(original, "__notes__", ()),
                        "POSIX reader retirement UNKNOWN: " + processes.format_ownership_error(secondary)]
        if original is not None:
            raise original
        posix_files._deadline(deadline)
        self.verify()
        return raw

    def close(self):
        self.closed = True


def _new_private_directory(path):
    if os.name == "nt":
        return windows_files.create_private_directory(path)
    require(os.name == "posix" and os.geteuid() != 0, "QUERY_ORDINARY_NATIVE_USER")
    path = posix_files._path(path)
    path.mkdir(mode=0o700)
    return _PosixDirectory(path)


def _git_environment():
    value = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C", "GIT_TERMINAL_PROMPT": "0",
             "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
             "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
    if os.name == "nt":
        require(bool(os.environ.get("SYSTEMROOT")), "QUERY_WINDOWS_SYSTEM_ROOT")
        value["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    return value


def _inherited_context():
    value = {name: os.environ[name] for name in _CONTEXT if name in os.environ}
    # An ambient Gradle home alone is not a native ownership claim. A claimed
    # outer domain, however, must remain complete and byte-valid; never erase it.
    if any(name in value for name in _CONTEXT[:-1]):
        require(set(value) == set(_CONTEXT), "QUERY_PARTIAL_ANCESTOR_CONTEXT")
        try:
            value[processes.DOMAINS_ENV].encode("ascii")
        except UnicodeError:
            raise QueryError("QUERY_NONASCII_ANCESTOR_DOMAINS") from None
        domains = processes.ownership_domains(value[processes.CHAIN_ENV], value[processes.DOMAINS_ENV])
        require(domains and value[processes.JOB_ENV] == domains[-1]["job"] and
                value[processes.STATE_ENV] == domains[-1]["state"] and
                value["GRADLE_USER_HOME"] == domains[-1]["home"], "QUERY_ANCESTOR_CONTEXT")
    return value


def _allowed_suffix(arguments):
    if arguments in (("rev-parse", "--show-toplevel"),
                     ("rev-parse", "--is-shallow-repository"),
                     ("status", "--porcelain=v1", "--untracked-files=all")):
        return True
    # Bootstrap identity checks full history and original-main ancestry. Admit
    # only two immutable commits, never arbitrary refs, revision syntax or flags.
    if len(arguments) == 3 and arguments[0] == "merge-base":
        return all(identity.SHA.fullmatch(value) is not None for value in arguments[1:])
    if len(arguments) == 3 and arguments[:2] == ("rev-parse", "--verify"):
        return bool(re.fullmatch(r"(?:HEAD|refs/remotes/origin/main|[0-9a-f]{40})\^\{commit\}|"
                                 r"[0-9a-f]{40}\^\{tree\}", arguments[2]))
    if len(arguments) == 4 and arguments[:3] in (("show", "-s", "--format=%P"), ("show", "-s", "--format=%B")):
        return bool(identity.SHA.fullmatch(arguments[3]))
    if len(arguments) == 5 and arguments[:2] == ("ls-tree", "-z") and arguments[3] == "--" and \
            arguments[4] in (identity.POLICY_PATH, *identity.abi.BASELINES):
        return bool(identity.SHA.fullmatch(arguments[2]))
    if len(arguments) == 3 and arguments[0] == "cat-file" and arguments[1] in ("-s", "blob"):
        return bool(identity.SHA.fullmatch(arguments[2]))
    return False


class NativeGitQueries:
    """Real GitView callback with native-private sinks and native-owned children.

    Use as a context manager. The caller must supply a cancellation check tied to
    its real outer controller; this class does not replace another owner's signal
    handlers. Successful query return requires exit0, complete private capture,
    known native retirement, sink closure and original receipt retention. Class
    receipts say READY_FOR_CALLER_SEAL, never upload/build/crypto acceptance.
    """

    def __init__(self, root, directory, *, check_cancel, owner_deadlines=None):
        require(callable(check_cancel), "QUERY_CANCELLATION_OWNER_REQUIRED")
        # Optional SAME-PROCESS monotonic work/final fences can only shorten the
        # existing per-query15/final45 caps. Keep one immutable pair across all
        # queries, admission retention, failure retention and session close.
        # This is not a service-job budget or a cross-process clock identity.
        if owner_deadlines is not None:
            try:
                require(type(owner_deadlines) is tuple and len(owner_deadlines) == 2 and
                        all(type(value) in (int, float) and math.isfinite(value) for value in owner_deadlines) and
                        time.monotonic() < owner_deadlines[0] <= owner_deadlines[1], "QUERY_OWNER_DEADLINES")
            except (OverflowError, TypeError, ValueError):
                raise QueryError("QUERY_OWNER_DEADLINES") from None
        self._owner_deadlines = owner_deadlines
        self.root, self.path = Path(root), Path(directory)
        self.check_cancel = check_cancel
        self.thread = threading.get_ident()
        self.job, self.records, self.resources, self.errors = uuid.uuid4().hex, [], [], []
        self.readbacks = []
        self.first_error = self.cancellation = None
        self.failed = self.unknown = self.closed = self.active = False
        self.total = 0
        self.io_deadline = self._cap(time.monotonic() + FINALIZATION_SECONDS, final=True)
        self.private = self.home = None
        self.ambient_context = _inherited_context()  # Validate before native allocation.
        self.git_environment = _git_environment()
        self.native_role = processes.host_role()
        require(self.native_role in _ROLES, "QUERY_NATIVE_ROLE")
        require(self.root.is_absolute() and self.root == self.root.resolve(strict=True) and
                self.root.is_dir() and self.path.is_absolute() and ".." not in self.path.parts and
                self.path != self.root and self.path not in self.root.parents and self.root not in self.path.parents,
                "QUERY_ROOTS")
        executable = shutil.which("git")
        require(executable is not None, "QUERY_GIT_UNAVAILABLE")
        self.executable = str(Path(executable).resolve(strict=True))
        self._work_fence()
        try:
            self.private = self._acquire("private-root", lambda: _new_private_directory(self.path))
            self._work_fence()
            self.home = self._acquire("query-home", lambda: self.private.create_directory(
                "query-home", deadline=self.io_deadline))
            self._work_fence()
            self._write(self.private, "owner.json", {"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY",
                "job": self.job, "state": str(self.path), "home": str(self.home.path), "root": str(self.root),
                "nativeRole": self.native_role, "git": self.executable, "ancestorContext": self.ambient_context})
            self._work_fence()
        except BaseException as error:
            self._error(None, "allocation", error, unknown=True)
            self._quarantine()
            self._raise_failure()

    def _cap(self, deadline, *, final):
        return deadline if self._owner_deadlines is None else min(deadline, self._owner_deadlines[int(final)])

    def _work_fence(self):
        if self._owner_deadlines is not None:
            require(time.monotonic() < self._owner_deadlines[0], "QUERY_OWNER_WORK_EXPIRED")

    def _hold(self, label, owner):
        self.resources.append({"label": label, "owner": owner, "closeAttempted": False, "closed": False})
        return owner

    def _acquire(self, label, factory):
        if self._owner_deadlines is not None:
            posix_files._deadline(self._cap(self.io_deadline, final=True))
        try:
            return self._hold(label, factory())
        except BaseException as error:
            # Allocation may fail after a native handle exists. A missing Python
            # return value is not evidence that its constructor retired it.
            self._error(None, label + "-allocation", error, unknown=True)
            raise

    def _error(self, row, phase, error, *, unknown=False):
        self.failed = True
        self.unknown |= unknown or bool(processes.retirement_details(error))
        if self.first_error is None:
            self.first_error = error
        if not isinstance(error, Exception) and self.cancellation is None:
            self.cancellation = error
        detail = {"phase": phase, "detail": processes.format_ownership_error(error),
                  "notes": list(getattr(error, "__notes__", ()))[:64],
                  "retirementUnknown": self.unknown}
        for errors, bound in ((self.errors, 128), *(([(row["errors"], 64)]) if row is not None else [])):
            if len(errors) < bound:
                errors.append(detail)
            else:
                self.unknown = True

    def _quarantine(self):
        self.unknown = True
        if not any(item is self for item in QUARANTINE):
            QUARANTINE.append(self)  # Do not release pins beneath an uncertain native writer.

    def _raise_failure(self):
        if self.cancellation is not None:
            raise self.cancellation
        raise QueryError("NATIVE_GIT_QUERY_HOLD") from None

    def _check(self):
        require(threading.get_ident() == self.thread and not self.closed and not self.failed and not self.unknown,
                "QUERY_OWNER_NOT_LIVE")
        require(_inherited_context() == self.ambient_context and _git_environment() == self.git_environment,
                "QUERY_AMBIENT_CONTEXT_CHANGED")
        self._work_fence()
        self.check_cancel()

    def _close(self, owner, row=None):
        resource = next(item for item in self.resources if item["owner"] is owner)
        if resource["closeAttempted"]:
            return
        resource["closeAttempted"] = True
        try:
            owner.close()
            resource["closed"] = True
        except BaseException as error:
            self._error(row, resource["label"] + "-close", error, unknown=True)

    def _readback(self, parent, name, maximum, deadline, row=None):
        """Own the supplier reader call, including its internal close outcome.

        Both filesystem suppliers close their new reader before a successful
        return. A thrown exception may include an unreturned descriptor or an
        ambiguous native CloseHandle. Do not infer KNOWN from a missing process-
        owner carrier or parse the Windows supplier's human-readable notes.
        Conservatively quarantine original ancestor pins on ANY delegated-reader
        failure, including receipt readback, and retain the original diagnostic.
        """
        deadline = self._cap(deadline, final=True)
        posix_files._deadline(deadline)  # No reader can be allocated after this bound.
        outcome = {"parent": str(parent.path), "name": name, "maximum": maximum,
                   "retirement": "UNKNOWN", "result": "HOLD"}
        self.readbacks.append(outcome)
        try:
            raw = parent.read_bytes(name, max_bytes=maximum, deadline=deadline)
        except BaseException as error:
            outcome["error"] = processes.format_ownership_error(error)
            outcome["notes"] = list(getattr(error, "__notes__", ()))[:64]
            self._error(row, name + "-reader", error, unknown=True)
            raise
        outcome.update(retirement="KNOWN", result="RETAINED", bytes=len(raw))
        posix_files._deadline(deadline)
        return raw

    def _write(self, parent, name, value):
        # Frozen once by the owning phase, NOT a new allowance for every receipt
        # or reader. At most started+timeout+45 in a query, shortened by any
        # original owner final fence, never renewed by a later retention call.
        end = self._cap(self.io_deadline, final=True)
        posix_files._deadline(end)
        raw = value if type(value) is bytes else encoded(value)
        require(len(raw) <= MAX_RECEIPT_BYTES and self.total + len(raw) <= MAX_SESSION_BYTES, "QUERY_SESSION_LIMIT")
        stream = self._acquire(name, lambda: parent.create_file(name, max_bytes=max(1, len(raw)),
                                                              deadline=end))
        original = None
        try:
            posix_files._deadline(end)
            require(stream.write(raw) == len(raw), "QUERY_RECEIPT_SHORT_WRITE")
            stream.sync()
            require(stream.verify().size == len(raw), "QUERY_RECEIPT_SIZE")
            posix_files._deadline(end)
        except BaseException as error:
            original = error
            self._error(None, name + "-write", error)
        self._close(stream)
        if original is not None:
            raise original
        if self.unknown:
            self._raise_failure()
        require(self._readback(parent, name, max(1, len(raw)), end) == raw, "QUERY_RECEIPT_READBACK")
        self.total += len(raw)

    def _final_fence(self, row, deadline=None):
        """Observe late cancellation/time without ever skipping owned cleanup."""
        try:
            self.check_cancel()
        except BaseException as error:
            self._error(row, "final-cancellation", error)
        if self._owner_deadlines is not None:
            deadline = self._owner_deadlines[1] if deadline is None else self._cap(deadline, final=True)
        if deadline is not None:
            try:
                posix_files._deadline(deadline)
            except BaseException as error:
                self._error(row, "final-deadline", error)

    def _query_verdict(self, row):
        row["retirement"] = "UNKNOWN" if self.unknown else "KNOWN"
        row["result"] = "HOLD" if self.failed or self.unknown else "READY_FOR_CALLER_SEAL"

    def native_host_matches_actions(self):
        require(_ROLES[self.native_role] == (os.environ.get("RUNNER_OS"), os.environ.get("RUNNER_ARCH")),
                "QUERY_NATIVE_HOST_DIFFERS_FROM_ACTIONS")

    def __call__(self, *, argv, cwd, environment, stdout_limit, stderr_limit, timeout_seconds):
        try:
            self._check()
            require(not self.active and len(self.records) < MAX_QUERIES, "QUERY_REENTRY_OR_COUNT")
            require(type(argv) is tuple and all(type(item) is str and 0 < len(item) <= 8192 and "\0" not in item
                                               for item in argv), "QUERY_ARGUMENTS")
            prefix = (self.executable, "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                      "-C", str(self.root))
            require(argv[:len(prefix)] == prefix and _allowed_suffix(argv[len(prefix):]) and
                    Path(cwd) == self.root and environment == self.git_environment, "QUERY_NOT_CLOSED_READONLY_GIT")
            require(type(stdout_limit) is int and 0 < stdout_limit <= identity.EVENT_LIMIT and
                    type(stderr_limit) is int and 0 < stderr_limit <= 4096 and
                    type(timeout_seconds) in (int, float) and 0 < timeout_seconds <= 15, "QUERY_BOUNDS")
        except BaseException as error:
            self._error(None, "query-input", error)
            self._raise_failure()
        invocation, started = uuid.uuid4().hex, time.monotonic()
        end = self._cap(started + timeout_seconds, final=False)
        final_end = self._cap(started + timeout_seconds + FINALIZATION_SECONDS, final=True)
        self.io_deadline = final_end
        row = {"schema": 1, "scope": "NATIVE_OWNED_ORDINARY_GIT_QUERY", "id": invocation,
               "job": self.job, "state": str(self.path), "home": str(self.home.path), "cwd": str(self.root),
               "argv": list(argv), "stdoutLimit": stdout_limit, "stderrLimit": stderr_limit,
               "timeoutSeconds": timeout_seconds, "launchAttempted": False, "scopeAttempted": False,
               "waitExitCode": None, "retirement": "UNKNOWN", "result": "HOLD", "errors": [], "outputs": {}}
        self.records.append(row)
        self.active = True
        directory = scope = child = out = err = None
        data = None
        try:
            directory = self._acquire("query-directory", lambda: self.private.create_directory(
                "query-" + invocation, deadline=final_end))
            out = self._acquire("stdout", lambda: directory.create_file("stdout.log", max_bytes=stdout_limit,
                                                                       deadline=final_end))
            err = self._acquire("stderr", lambda: directory.create_file("stderr.log", max_bytes=stderr_limit,
                                                                       deadline=final_end))
            environment = processes.ownership_environment({**environment, **self.ambient_context}, self.job,
                            invocation, str(self.path), str(self.home.path), allow_new_context=True)
            self._write(directory, "start.json", {**row, "environment": environment})
            self._check()
            posix_files._deadline(end)
            row["scopeAttempted"] = True
            scope = self._hold("native-scope", processes.make_scope(self.job, invocation, str(self.path),
                                                                   str(self.home.path)))
            # Keep the ORIGINAL object and POSIX lifetime baseline. This is not
            # a recovery recipe; a fresh post-exit baseline cannot prove retirement.
            self._write(directory, "baseline.json", {"nativeRole": self.native_role,
                "baseline": sorted(scope.baseline) if hasattr(scope, "baseline") else None,
                "kernelJob": self.native_role == "windows-x64"})
            self._check()
            posix_files._deadline(end)
            row["launchAttempted"] = True
            child = scope.spawn(list(argv), str(self.root), environment, stdout=out, stderr=err)
            require(child.stdout is None and child.stderr is None, "QUERY_DID_NOT_BORROW_PRIVATE_SINKS")
            while True:
                self._check()
                posix_files._deadline(end)
                if self.native_role == "windows-x64":
                    out.observe_live_output()
                    err.observe_live_output()
                else:
                    out.verify()
                    err.verify()
                code = child.poll()
                if code is not None:
                    row["waitExitCode"] = code
                    break
                scope.discover()
                time.sleep(0.025)
            require(type(code) is int and code == 0, "QUERY_GIT_NONZERO")
            require(not scope.discover(), "QUERY_GIT_LEFT_DESCENDANTS")
        except BaseException as error:
            self._error(row, "query", error)
        finally:
            native_known = not row["scopeAttempted"]
            if scope is not None:
                try:
                    survivors = scope.drain(grace=0, kill_wait=5)
                    row["ownedSurvivors"] = survivors
                    require(survivors == [], "QUERY_SURVIVORS")
                    native_known = True
                except BaseException as error:
                    self._error(row, "drain", error, unknown=True)
                try:
                    row["ownership"] = scope.description()
                    require(row["ownership"].get("discoveryErrors") == [], "QUERY_DISCOVERY_UNKNOWN")
                except BaseException as error:
                    self._error(row, "ownership-record", error, unknown=True)
                self._close(scope, row)
            elif row["scopeAttempted"]:
                # A failed constructor may have failed native cleanup before it
                # returned. scope=None is not proof of an empty/retired domain.
                self._error(row, "scope-construction", QueryError("QUERY_SCOPE_CONSTRUCTION_UNKNOWN"), unknown=True)
            self._final_fence(row, final_end)
            if not native_known or self.unknown:
                self._quarantine()
            else:
                for label, sink in (("stdout", out), ("stderr", err)):
                    if sink is None:
                        continue
                    try:
                        sink.sync()
                        row["outputs"][label] = sink.verify().as_dict()
                    except BaseException as error:
                        self._error(row, label + "-final", error)
                    self._close(sink, row)
                if not self.unknown and directory is not None and out is not None and err is not None:
                    try:
                        captures = {}
                        for label, limit in (("stdout", stdout_limit), ("stderr", stderr_limit)):
                            raw = self._readback(directory, label + ".log", limit, final_end, row)
                            require(self.total + len(raw) <= MAX_SESSION_BYTES, "QUERY_SESSION_LIMIT")
                            self.total += len(raw)
                            captures[label] = raw
                            row["outputs"].setdefault(label, {}).update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                        data = captures["stdout"]
                    except BaseException as error:
                        self._error(row, "capture-readback", error)
            self._final_fence(row, final_end)
            self._query_verdict(row)
            if directory is not None:
                try:
                    self._write(directory, "result.json", row)
                except BaseException as error:
                    self._error(row, "original-query-receipt", error)
                if not self.unknown:
                    self._close(directory, row)
            # Includes cancellation/deadline during the last receipt's own
            # reader/finalizer or native directory close, not just native drain.
            self._final_fence(row, final_end)
            self._query_verdict(row)
            self.active = False
            if self.unknown:
                self._quarantine()
        if self.failed or data is None:
            self._raise_failure()
        return data

    def retain_admission(self, admission):
        self._check()
        self.io_deadline = self._cap(time.monotonic() + FINALIZATION_SECONDS, final=True)
        require(type(admission) is identity.Admission, "QUERY_ADMISSION_TYPE")
        for name, raw in (("admission.json", admission.record), ("original-event.json", admission.original_event),
                          ("original-policy.json", admission.original_policy), ("recipient-public.asc", admission.public_key)):
            self._write(self.private, name, raw)
        self._write(self.private, "admission-scope.json", {"schema": 1,
            "scope": "IDENTITY_ONLY_NO_CRYPTO_NO_PRODUCTS_NO_UPLOAD", "result": "READY_FOR_CALLER_SEAL"})
        self._check()
        posix_files._deadline(self.io_deadline)

    def record_admission_failure(self, error):
        self._error(None, "admission", error)
        # A distinct failure-retention phase, never a renewal allowing a query
        # to succeed beyond its original absolute finalization deadline.
        self.io_deadline = self._cap(time.monotonic() + FINALIZATION_SECONDS, final=True)
        if self.private is not None:
            try:
                self._write(self.private, "admission-failure.json", {"schema": 1, "result": "HOLD",
                    "error": processes.format_ownership_error(error), "retirement": "UNKNOWN" if self.unknown else "KNOWN"})
            except BaseException as secondary:
                self._error(None, "admission-failure-receipt", secondary)

    def close(self):
        if self.closed:
            if self.failed:
                self._raise_failure()
            return
        self.closed = True
        self.io_deadline = self._cap(time.monotonic() + FINALIZATION_SECONDS, final=True)
        self._final_fence(None)
        if self.active:
            self.unknown = True
        if self.private is not None:
            try:
                self._write(self.private, "session-result.json", {"schema": 1,
                    "scope": "ORDINARY_GIT_QUERIES_ONLY", "job": self.job, "queries": self.records,
                    "result": "HOLD" if self.failed or self.unknown else "READY_FOR_CALLER_SEAL",
                    "retirement": "UNKNOWN" if self.unknown else "KNOWN",
                    "firstError": None if self.first_error is None else processes.format_ownership_error(self.first_error),
                    "errors": self.errors, "readbacks": self.readbacks})
            except BaseException as error:
                self._error(None, "session-receipt", error)
        if not self.unknown:
            for resource in reversed(self.resources):
                if self.unknown:
                    break
                self._close(resource["owner"])
        if self.unknown:
            self._quarantine()
        self._final_fence(None, self.io_deadline)
        if self.failed or self.unknown:
            self._raise_failure()

    def __enter__(self):
        try:
            self._check()
        except BaseException as original:
            # Python never invokes __exit__ after a failed __enter__. The owner
            # already has real private roots/pins; finalize them explicitly.
            self._finalize(original)
            raise
        return self

    def _finalize(self, original):
        if original is not None and not self.closed:
            try:
                self.record_admission_failure(original)
            except BaseException as secondary:
                self._error(None, "admission-failure-finalizer", secondary)
        try:
            self.close()
        except BaseException:
            if original is None:
                raise

    def __exit__(self, kind, original, traceback):
        self._finalize(original)
        return False  # A finalizer never replaces the original cancellation/failure.


def admit_hosted(profile, root, directory, *, expected=None):
    """Actual admission entrypoint: native Git only, with no product/export stage.

    Native ownership calls occur here on the ACTUAL host, never in offline tests.
    No env/GitHub identity substitution, policy bootstrap or lock input fallback.
    A missing authorized policy is a real pre-product HOLD. This standalone
    entrypoint owns signal handlers only for its finite admission interval.
    """
    require(threading.current_thread() is threading.main_thread(), "QUERY_SIGNAL_OWNER_THREAD")
    require(profile in identity.PROFILES, "QUERY_PROFILE")
    cancelled, handlers = [], {}
    cancellation = None

    def check_cancel():
        nonlocal cancellation
        if cancelled:
            if cancellation is None:
                cancellation = KeyboardInterrupt("ORDINARY_HOSTED_QUERY_CANCELLED")
            raise cancellation

    owner = None
    original = None
    result = None
    try:
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handlers[number] = signal.getsignal(number)
            signal.signal(number, lambda signum, _frame: cancelled.append(signum))
        check_cancel()
        owner = NativeGitQueries(root, directory, check_cancel=check_cancel)
        check_cancel()
        owner.native_host_matches_actions()
        result = identity.admit(profile, Path(root), query_runner=owner, expected=expected)
        owner.retain_admission(result)
        check_cancel()
    except BaseException as error:
        original = error
    finally:
        # Own every successfully returned allocation, regardless of whether
        # context entry or the first admission operation ever ran.
        if owner is not None:
            try:
                owner._finalize(original)
            except BaseException as error:
                if original is None:
                    original = error
        for number, handler in handlers.items():
            try:
                signal.signal(number, handler)
            except BaseException as error:
                if owner is not None:
                    owner._error(None, "signal-restoration", error, unknown=True)
                    owner._quarantine()
                if original is None:
                    original = error
        if cancelled and original is None:
            try:
                check_cancel()
            except BaseException as error:
                original = error
    if original is not None:
        raise original
    require(type(result) is identity.Admission, "QUERY_ADMISSION_MISSING")
    return result
