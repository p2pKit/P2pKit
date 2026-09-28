"""Bounded, intentionally public failure hints; never closure or acceptance.

Only a fixed code crosses this channel, not private streams or terminal receipts.
Matching the original invocation and phase rejects stale data, not a spoofing
descendant: every hint remains untrusted, including after an actual execute return.
All I/O is best effort and cannot replace the caller's existing failure.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
import sys

BASENAME = "public-failure-hint.txt"
MAX_BYTES = 128
DISCLAIMER = "HINT_NOT_CLOSURE_OR_ACCEPTANCE"
UNAVAILABLE = "UNAVAILABLE"
GENERIC = "PRIVATE_FAILURE"
PHASES = ("PREREQUISITES", "TARGET", "OBSERVER", "GENERATOR")
PURPOSE_PHASES = {
    "dependency-maintenance-prerequisites": "PREREQUISITES",
    "dependency-maintenance-jmdns-target": "TARGET",
    "dependency-maintenance-jmdns-observer": "OBSERVER",
    "dependency-maintenance-generator": "GENERATOR",
}
CHILD_ARGUMENTS = {
    "PREREQUISITES": "_prerequisites",
    "TARGET": "_diagnostic-target",
    "OBSERVER": "_diagnostic-observer",
}
# Only fixed prerequisite/controller-helper errors reachable from these children.
# New error text is private until its literal code is deliberately reviewed here.
UPDATE_CODES = frozenset({
    "PREREQUISITE_OWNER", "MISSING_INSTALLED_TOOL", "XCODE_SELECTION", "TOOL_QUERY_FAILED",
    "JAVA_SELECTION", "XCODE_VERSION", "SDK_MANAGER_MISSING", "SDK_INSTALL_FAILED", "SDK_METADATA",
    "ABSOLUTE_PATH", "PATH_SYMLINK", "FILE_TYPE_OR_BOUND", "FILE_CHANGED", "WRITE_BYTES",
    "WRITE_SHORT", "WRITE_READBACK", "JSON_BOUND", "JSON_DUPLICATE", "JSON_NONFINITE", "JSON_FORMAT",
    "CLEAN_SOURCE", "SOURCE_ORIGIN", "PERSISTED_CREDENTIALS", "REQUEST_FIELDS", "MANUAL_IDENTITY",
    "CONTROLLER_REF", "CONTROLLER_IDENTITY", "RUN_IDENTITY", "ORIGINAL_COMMAND_FAILED",
})
DRIVER_CODES = frozenset({
    "JMDNS_COMMAND_NOT_KNOWN_ORDINARY", "JMDNS_REQUEST", "JMDNS_FIXED_BUDGET", "JMDNS_TARGET_BINDING",
    "JMDNS_TARGET_CLOCKS", "JMDNS_ACTION_CLOCK", "JMDNS_FIXED_CHILD", "JMDNS_RESOURCE_POLICY",
    "JMDNS_ORIGINAL_OWNER", "JMDNS_CONTROLLER_SOURCE", "JMDNS_CHILD_ENVIRONMENT", "JMDNS_REQUEST_SOURCE",
    "JMDNS_WRAPPER_OR_RESOURCE_CHANGED", "JMDNS_ORIGINAL_START", "JMDNS_TOTAL_DEADLINE",
    "JMDNS_JAVA_CODE_BOUND", "JMDNS_HASH_TIMEOUT", "JMDNS_JAVA_CODE_CHANGED", "JMDNS_OBSERVER_TIMEOUT",
    "JMDNS_OBSERVER_STREAM_OR_TIMEOUT", "JMDNS_TEST_NOT_ADMITTED", "JMDNS_TEST_TIMEOUT",
    "JMDNS_ORIGINAL_RETURN", "JMDNS_TARGET_RECORD_CHANGED", "JMDNS_TARGET_IDENTITY",
    "JMDNS_TARGET_RECEIPT_CHANGED", "JMDNS_REPORT_BINDING", "JMDNS_REPORT_MANIFEST",
    "JMDNS_ORIGINAL_CONTROL_REPORT", "JMDNS_CONTROL_REPORT_CHANGED", "JMDNS_ORIGINAL_JAVA_METADATA",
})
CODES = UPDATE_CODES | DRIVER_CODES | frozenset({GENERIC})
IDENTIFIER = re.compile(r"[0-9a-f]{32}\Z")
START_LIMIT = 65536


def phase_for_purpose(purpose):
    return PURPOSE_PHASES.get(purpose) if type(purpose) is str else None


def failure_code(error, *, update_error_type=None, driver_error_type=None):
    """Project only exact caller-supplied, already-loaded error types; never str()."""
    try:
        if type(error) is update_error_type:
            allowed = UPDATE_CODES
        elif type(error) is driver_error_type:
            allowed = DRIVER_CODES
        else:
            return GENERIC
        arguments = error.args
        if type(arguments) is tuple and len(arguments) == 1 and type(arguments[0]) is str and arguments[0] in allowed:
            return arguments[0]
    except BaseException:
        pass
    return GENERIC


def _require(condition):
    if not condition:
        raise ValueError("Unavailable public failure hint")


def _canonical(invocation, phase, code):
    _require(type(invocation) is str and IDENTIFIER.fullmatch(invocation) and
             type(phase) is str and phase in PHASES and type(code) is str and code in CODES)
    raw = ("UNTRUSTED_V1 " + invocation + " " + phase + " " + code + "\n").encode("ascii")
    _require(len(raw) <= MAX_BYTES)
    return raw


def _path(value):
    _require(isinstance(value, (str, Path)))
    path = Path(value)
    raw = os.fspath(value)
    _require(type(raw) is str and 0 < len(raw) <= 8192 and "\0" not in raw and
             path.anchor == "/" and str(path) == raw and ".." not in path.parts and
             1 < len(path.parts) <= 128)
    return path


def _directory_identity(info):
    # Ancestor timestamps/nlink change when unrelated temporary entries appear.
    return info.st_dev, info.st_ino, info.st_mode, info.st_uid


def _file_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _regular(info, limit):
    _require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
             not info.st_mode & 0o077 and 0 <= info.st_size <= limit)


def _check_links(links):
    for parent, name, descriptor, before in links:
        current = os.fstat(descriptor)
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
        _require(_directory_identity(before) == _directory_identity(current) == _directory_identity(named))


@contextmanager
def _invocation_directory(state, invocation):
    """Open each ancestor without following links; create no directories."""
    _require(os.name == "posix" and type(invocation) is str and IDENTIFIER.fullmatch(invocation))
    state = _path(state)
    parts = (*state.parts[1:], "evidence", invocation)
    descriptors, links = [], []
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        descriptor = os.open("/", flags)
        descriptors.append(descriptor)
        before = os.fstat(descriptor)
        _require(stat.S_ISDIR(before.st_mode))
        links.append((None, "/", descriptor, before))
        for index, name in enumerate(parts):
            parent = descriptor
            descriptor = os.open(name, flags, dir_fd=parent)
            descriptors.append(descriptor)  # Retire even when fstat/validation fails.
            before = os.fstat(descriptor)
            _require(stat.S_ISDIR(before.st_mode))
            if index >= len(state.parts) - 2:
                _require(before.st_uid == os.getuid() and stat.S_IMODE(before.st_mode) == 0o700)
            links.append((parent, name, descriptor, before))
        _check_links(links)
        yield descriptor
        _check_links(links)
    finally:
        failed = False
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except BaseException:
                failed = True
        _require(not failed)


def _read_regular(directory, name, limit):
    # O_NONBLOCK precedes fstat: a raced FIFO must not stall the failure path.
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        before = os.fstat(descriptor)
        _regular(before, limit)
        raw = os.read(descriptor, limit + 1)
        after = os.fstat(descriptor)
        named = os.stat(name, dir_fd=directory, follow_symlinks=False)
        _require(len(raw) == before.st_size and _file_identity(before) == _file_identity(after) ==
                 _file_identity(named))
        return raw
    finally:
        os.close(descriptor)


def _unique(pairs):
    value = {}
    for name, item in pairs:
        _require(name not in value)
        value[name] = item
    return value


def _json(raw):
    _require(type(raw) in (str, bytes) and 0 < len(raw) <= START_LIMIT)
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=lambda _: _require(False))


def publish_child(root, env, phase, code):
    """Best-effort fixed-child hint at its existing original start location only."""
    try:
        _require(type(phase) is str and phase in CHILD_ARGUMENTS)
        root = _path(root)
        state = _path(env.get("P2PKIT_AUDIT_STATE_DIR", ""))
        invocation, job = env.get("P2PKIT_AUDIT_OWNERSHIP_CHAIN"), env.get("P2PKIT_AUDIT_JOB_ID")
        raw = _canonical(invocation, phase, code)
        _require(type(job) is str and IDENTIFIER.fullmatch(job))
        home = str(state / "gradle-home")
        domains = _json(env.get("P2PKIT_AUDIT_OWNERSHIP_DOMAINS", ""))
        _require(type(domains) is list and domains == [
            {"id": invocation, "job": job, "state": str(state), "home": home}] and
            env.get("GRADLE_USER_HOME") == home)
        argv = [str(Path(sys.executable).resolve()), "-I", "-B", "-S",
                str(root / "scripts/run-hosted-dependency-update.py"), CHILD_ARGUMENTS[phase]]
        with _invocation_directory(state, invocation) as directory:
            start = _json(_read_regular(directory, "start.json", START_LIMIT))
            _require(type(start) is dict and type(start.get("schema")) is int and start["schema"] == 1 and
                     start.get("id") == invocation and start.get("jobId") == job and
                     start.get("kind") == "command" and phase_for_purpose(start.get("purpose")) == phase and
                     start.get("requestedArgv") == argv and start.get("cwd") == str(root) and
                     start.get("wrapper") == str(root / "gradlew") and start.get("gradleHome") == home and
                     start.get("ancestorInvocationIds") == [] and type(start.get("controllerPid")) is int and
                     start["controllerPid"] == os.getppid())
            try:
                os.stat("receipt.json", dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                return False  # Never read a terminal receipt, optimistic or otherwise.
            descriptor = os.open(BASENAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 0o600, dir_fd=directory)
            try:
                before = os.fstat(descriptor)
                _regular(before, 0)
                _require(os.write(descriptor, raw) == len(raw))
                os.fsync(descriptor)
                after = os.fstat(descriptor)
                _regular(after, MAX_BYTES)
                _require(after.st_size == len(raw) and _file_identity(before)[:5] == _file_identity(after)[:5] and
                         _file_identity(after) == _file_identity(os.stat(BASENAME, dir_fd=directory,
                                                                        follow_symlinks=False)))
            finally:
                os.close(descriptor)
        return True
    except BaseException:
        return False  # No deletion/rewrite/retry; partial bytes can only be unavailable.


def read_hint(state, invocation, phase):
    """Return finite UNTRUSTED data only; never inspect private originals as fallback."""
    try:
        _canonical(invocation, phase, GENERIC)
        with _invocation_directory(state, invocation) as directory:
            raw = _read_regular(directory, BASENAME, MAX_BYTES)
            fields = raw.decode("ascii").split(" ")
            _require(len(fields) == 4 and fields[3].endswith("\n"))
            code = fields[3][:-1]
            _require(raw == _canonical(invocation, phase, code))
        return code
    except BaseException:
        return UNAVAILABLE
