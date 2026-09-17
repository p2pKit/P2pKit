#!/usr/bin/env python3
"""Coordinator-only terminal capture, not protocol code or an interoperability oracle.

Importing this module performs no I/O and imports no peer. The opt-in caller and
its parent must be separately source-bound/admitted. A readable record proves
retained bytes, not successful close/fsync, orderly TCP EOF, or a successful run.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat


SCHEMA = "p2pkit-independent-peer-terminal/1"
RAW_NAME = "peer-terminal.raw.json"
MAX_BYTES = 64 * 1024
LIFETIME_SECONDS = 120
STAGES = frozenset((
    "other", "constructor", "listener-close", "retirement-entry", "retirement-deadline", "write-shutdown",
    "drain-read", "drain-close", "forced-retirement", "preclose-observation", "owned-close", "command-failure",
    "admission", "run-boundary", "endpoint-abort", "output-initialize", "actor-initialize", "stdio-setup",
    "actor-clock", "output-watchdog", "endpoint-tick", "control-command", "control-input", "actor-select",
    "endpoint-read", "endpoint-write", "output-write", "control-read", "resource-finalization", "lifecycle-output",
    "final-output-drain", "final-output-clock", "final-output-select", "final-output-write",
    "stdio-restore-input", "stdio-restore-output",
))
CAUSES = frozenset((
    "other", "exception", "exception-escaped", "abort-after-close", "output-failed", "owner-deadline-elapsed",
    "deadline-elapsed", "shutdown-error", "shutdown-interrupted", "read-error", "read-interrupted",
    "closed-without-eof", "observation-interrupted", "close-error", "close-interrupted", "command-failed",
    "non-posix-or-shared-stdio", "invalid-lifetime", "non-pipe-stdio", "stdio-stat-error",
    "output-not-nonblocking", "not-drained", "restore-error",
))
KINDS = frozenset((
    "other", "PeerError", "ProtocolError", "VersionMismatch", "AuthenticationFailed", "AuthenticatedIdentityMismatch",
    "AuthorizationRejected", "HandshakeRejected", "InvalidLocalState", "TerminalState", "CounterExhausted",
    "LocalSequenceExhausted", "NoiseTransportEofException", "UnsupportedFeature", "ConnectionLost", "WriteTimeout",
    "PongTimeout", "LocalResourceLimit", "ControlOutputFailed", "DialFailed", "AcceptTimeout", "ConnectTimeout",
    "OwnedSocketCleanupFailed", "ControlInputClosed", "ControlInputInvalid", "LifetimeExpired", "CoordinatorAbort",
    "SanitizedLocalFailure",
))
PROTOCOL_STAGES = frozenset((
    "other", "starting", "listening", "connecting", "session", "draining", "terminal", "control",
    "preface-read", "preface-send", "flight1-read", "flight1-send", "flight2-read", "flight2-send",
    "flight3-read", "flight3-send", "hello", "active",
))
CATEGORIES = frozenset((
    "none", "peer-error", "os-error", "connection-reset", "interrupted-io", "would-block",
    "keyboard-interrupt", "system-exit", "exception", "base-exception",
))
BINDING_FIELDS = frozenset((
    "invocationId", "caseId", "pid", "parentPid", "bridgeSha256", "helperSha256", "peerManifestSha256",
))
_LABEL = re.compile(r"[a-zA-Z0-9_.-]{1,64}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class CaptureError(ValueError):
    """Fixed diagnostic codes only; never incorporate private input or exception text."""


def _require(condition, code):
    if not condition:
        raise CaptureError(code)


def _object(value, fields):
    _require(type(value) is dict, "object-required")
    _require(len(value) == len(fields) and all(type(k) is str for k in value), "object-fields")
    _require(value.keys() == fields, "object-fields")


def _token(value, allowed, nullable=False):
    _require(nullable and value is None or type(value) is str and value in allowed, "invalid-token")


def _integer(value, minimum, maximum):
    _require(type(value) is int and minimum <= value <= maximum, "invalid-integer")


def _boolean(value):
    _require(type(value) is bool, "boolean-required")


def _notes(value):
    _require(type(value) is list and len(value) <= len(STAGES), "cause-count")
    seen = set()
    for note in value:
        _object(note, {"stage", "cause", "category", "kind", "errno"})
        _token(note["stage"], STAGES)
        _require(note["stage"] not in seen, "repeated-cause-stage")
        seen.add(note["stage"])
        _token(note["cause"], CAUSES)
        _token(note["category"], CATEGORIES)
        _token(note["kind"], KINDS, nullable=True)
        if note["errno"] is not None:
            _integer(note["errno"], -(2**31), 2**31 - 1)


def validate_terminal(value):
    """Validate the pinned diagnostic vocabulary, including valid failed/incomplete observations."""
    _object(value, {"v", "state", "returnCode", "lastStage", "raisedStage", "actor", "causes",
                    "finalOutput", "stdioRestore"})
    _integer(value["v"], 1, 1)
    _token(value["state"], {"unused", "running", "returned", "raised"})
    if value["state"] == "returned":
        _integer(value["returnCode"], 0, 70)
        _require(value["returnCode"] in (0, 2, 70), "unsupported-return-code")
    else:
        _require(value["returnCode"] is None, "invented-return-code")
    _token(value["lastStage"], STAGES)
    _token(value["raisedStage"], STAGES, nullable=True)
    _token(value["finalOutput"], {"not-attempted", "drained", "deadline", "failed", "raised", "not-nonblocking"})
    _object(value["stdioRestore"], {"input", "output"})
    for entry in value["stdioRestore"].values():
        _token(entry, {"not-attempted", "attempted", "restored", "failed", "interrupted"})
    _notes(value["causes"])
    actor = value["actor"]
    if actor is None:
        return
    _object(actor, {"done", "exitCode", "failureKind", "controlOutputFailed", "constructorCleanupFailed",
                    "endpointOutputFailed", "socketCleanupFailed", "retirementErrorKind", "resourceFinalization",
                    "endpoint", "causes"})
    for key in ("done", "controlOutputFailed", "constructorCleanupFailed", "endpointOutputFailed", "socketCleanupFailed"):
        _boolean(actor[key])
    _integer(actor["exitCode"], 0, 70)
    _require(actor["exitCode"] in (0, 2, 70), "unsupported-actor-code")
    # Actor exitCode and callable returnCode intentionally are NOT compared.
    for key in ("failureKind", "retirementErrorKind"):
        _token(actor[key], KINDS, nullable=True)
    _token(actor["resourceFinalization"], {
        "not-attempted", "attempted", "returned-clean", "returned-uncertain", "raised",
    })
    _notes(actor["causes"])
    endpoint = actor["endpoint"]
    if endpoint is None:
        return
    _object(endpoint, {"v", "protocol", "retirementStarted", "writeShutdown", "actualDrainReadEof",
                       "listenerClose", "streamClose", "causes"})
    _integer(endpoint["v"], 1, 1)
    _boolean(endpoint["retirementStarted"])
    _boolean(endpoint["actualDrainReadEof"])
    _token(endpoint["writeShutdown"], {"not-attempted", "attempted", "completed", "failed", "interrupted"})
    for key in ("listenerClose", "streamClose"):
        _token(endpoint[key], {"not-owned", "owned", "attempted", "closed", "failed", "interrupted"})
    protocol = endpoint["protocol"]
    _object(protocol, {"event", "origin", "kind", "stage"})
    _token(protocol["event"], {"closed", "failed", "other"}, nullable=True)
    _token(protocol["origin"], {"local", "remote"}, nullable=True)
    _token(protocol["kind"], KINDS, nullable=True)
    _token(protocol["stage"], PROTOCOL_STAGES, nullable=True)
    _notes(endpoint["causes"])


def validate_binding(binding):
    _object(binding, BINDING_FIELDS)
    for key in ("invocationId", "caseId"):
        value = binding[key]
        _require(type(value) is str and _LABEL.fullmatch(value) is not None and value not in (".", ".."),
                 "invalid-owner-label")
    for key in ("pid", "parentPid"):
        _integer(binding[key], 1, 2**63 - 1)
    for key in ("bridgeSha256", "helperSha256", "peerManifestSha256"):
        _require(type(binding[key]) is str and _HASH.fullmatch(binding[key]) is not None, "invalid-binding-hash")


def encode_capture(terminal, binding):
    validate_binding(binding)
    validate_terminal(terminal)
    record = {"schema": SCHEMA, **binding, "terminal": terminal}
    raw = (json.dumps(record, ensure_ascii=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")
    _require(len(raw) <= MAX_BYTES, "capture-byte-bound")
    return raw


def _pairs(items):
    value = {}
    for key, item in items:
        _require(key not in value, "duplicate-json-field")
        value[key] = item
    return value


def _json_integer(value):
    _require(len(value) <= 20 and re.fullmatch(r"0|-?[1-9][0-9]*", value) is not None, "json-integer-bound")
    return int(value)


def _non_integer(_value):
    raise CaptureError("non-integer-json-number")


def decode_capture(raw, expected_binding, observed_exit):
    """Pure content/identity consistency; returned dict is NOT a runtime PASS.

    The parent supplies independently observed process PID/parent/exit and retains
    original bytes/hash before decoding. Raised or incomplete records may be
    retained, but cannot qualify natural success. No process code is invented.
    """
    validate_binding(expected_binding)
    _integer(observed_exit, -(2**31), 2**31 - 1)
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "capture-byte-bound")
    try:
        record = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_pairs, parse_int=_json_integer,
                            parse_float=_non_integer, parse_constant=_non_integer)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise CaptureError("invalid-capture-json") from error
    _object(record, BINDING_FIELDS | {"schema", "terminal"})
    _require(record["schema"] == SCHEMA, "capture-schema")
    actual = {key: record[key] for key in BINDING_FIELDS}
    validate_binding(actual)
    _require(actual == expected_binding, "capture-binding-mismatch")
    validate_terminal(record["terminal"])
    terminal = record["terminal"]
    if terminal["state"] == "returned":
        _require(terminal["returnCode"] == observed_exit, "capture-process-exit-disagreement")
    return record


def has_returned_actor_endpoint(record):
    """Necessary capture completeness only; never admits exit70 or any protocol outcome."""
    terminal = record["terminal"]
    return terminal["state"] == "returned" and terminal["actor"] is not None and terminal["actor"]["endpoint"] is not None


def _identity(info):
    return info.st_dev, info.st_ino


def _directory(path):
    _require(path.is_absolute() and str(path) == os.path.normpath(str(path)), "noncanonical-case-path")
    for component in (path, *path.parents):
        info = component.lstat()
        _require(stat.S_ISDIR(info.st_mode), "symlink-or-nondirectory-component")
    info = path.lstat()
    _require(stat.S_IMODE(info.st_mode) == 0o700 and info.st_uid == os.geteuid(), "private-owned-directory-required")
    return _identity(info)


def _marker(path, invocation_id, digest):
    expected = ("p2pkit-owned-peer-v1\n" + invocation_id + "\n").encode("ascii")
    before = path.lstat()
    _require(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode) == 0o600
             and before.st_uid == os.geteuid() and before.st_nlink == 1, "private-owner-marker-required")
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        _require(_identity(os.fstat(fd)) == _identity(before), "owner-marker-replaced")
        raw = os.read(fd, 257)
        after = path.lstat()
        _require(_identity(after) == _identity(before) and after.st_size == before.st_size == len(raw),
                 "owner-marker-changed")
        _require(raw == expected and hashlib.sha256(raw).hexdigest() == digest, "owner-marker-binding")
    finally:
        os.close(fd)


class OwnedCapture:
    """One create-new side record in an already admitted, private case directory.

    The wrapper pins state_directory; it is not an arbitrary output destination.
    Path/inode checks detect replacement, not malicious same-UID isolation. The
    borrowed run descriptors are never inspected/closed/redirected here.
    """

    def __init__(self, state_directory, case_directory, binding, owner_marker_sha256):
        _require(os.name == "posix" and os.getuid() == os.geteuid() != 0, "ordinary-posix-owner-required")
        validate_binding(binding)
        _require(binding["pid"] == os.getpid() and binding["parentPid"] == os.getppid(), "actual-process-binding")
        _require(type(owner_marker_sha256) is str and _HASH.fullmatch(owner_marker_sha256) is not None,
                 "invalid-marker-hash")
        state = Path(state_directory)
        root = state / "work" / "core-tcp-interop" / binding["invocationId"]
        case = Path(case_directory)
        _require(case == root / binding["caseId"], "case-outside-owned-root")
        self._directories = {p: _directory(p) for p in (state, state / "work", root.parent, root, case)}
        self._case, self._root = case, root
        self._binding, self._marker_hash = dict(binding), owner_marker_sha256
        self._fd, self._attempted = None, False
        _marker(root / "OWNER", binding["invocationId"], owner_marker_sha256)
        try:
            (case / RAW_NAME).lstat()
        except FileNotFoundError:
            pass
        else:
            raise CaptureError("capture-already-exists")
        fd = os.open(str(case), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            _require(_identity(os.fstat(fd)) == self._directories[case], "case-directory-replaced")
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd

    def export(self, terminal):
        _require(not self._attempted and self._fd is not None, "capture-single-use")
        self._attempted = True
        raw = encode_capture(terminal, self._binding)
        for path, identity in self._directories.items():
            _require(_directory(path) == identity, "case-ancestor-replaced")
        _marker(self._root / "OWNER", self._binding["invocationId"], self._marker_hash)
        _require(_identity(os.fstat(self._fd)) == self._directories[self._case], "case-directory-replaced")
        fd = os.open(RAW_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self._fd)
        try:
            info = os.fstat(fd)
            _require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
                     and info.st_uid == os.geteuid() and info.st_nlink == 1, "private-capture-required")
            offset = 0
            while offset < len(raw):
                count = os.write(fd, raw[offset:])
                _require(type(count) is int and 0 < count <= len(raw) - offset, "capture-write-no-progress")
                offset += count
            _require(_directory(self._case) == self._directories[self._case], "case-directory-replaced")
        finally:
            # No retry/overwrite/unlink or claim that a readable file proves this close succeeded.
            os.close(fd)

    def close(self):
        fd, self._fd = self._fd, None
        if fd is not None:
            os.close(fd)


def invoke_with_capture(run, holder, input_fd, output_fd, sink):
    """Call the existing peer once. Diagnostic-only errors never replace its return/exception."""
    try:
        return run(input_fd, output_fd, LIFETIME_SECONDS, diagnostics=holder)
    finally:
        try:
            sink.export(holder.snapshot)
        except BaseException:
            pass  # Only NEW diagnostic work. The parent must reject absent/invalid capture.
        finally:
            try:
                sink.close()
            except BaseException:
                pass  # Close only this helper's directory FD; never the borrowed run descriptors.
