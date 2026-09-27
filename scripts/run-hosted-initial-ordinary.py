#!/usr/bin/env python3
"""Distinct native Stage2 source/qualification acquisition, NOT worker execution.

Only acquire_initial_ordinary/refresh_initial_ordinary create original current
handles. Supplied JSON, a Stage1 SourceReturn, a reference-only identity and a
successful gate cannot do so. This module runs no products, key operation or
cache restore and cannot remove either ordinary HOLD. The standalone 120/75
window is an UNMEASURED source cap, never an admitted job allocation.

The fixed child owns authenticated metadata/archive reads and its native Git
queries. The actual parent owns launch/captures/native retirement, complete
independent packet/readback checks and the original final close. Signed archive
locations and original failure objects stay private. Nothing is decrypted.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import http.client
import math
import os
from pathlib import Path
import re
import shutil
import signal
import ssl
import stat
import sys
import threading
import time
from urllib.parse import parse_qsl, urlsplit
import uuid

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import audit_processes as processes
import hosted_cache_bootstrap_origin as origin
import hosted_cache_compatibility as compatibility
import hosted_dependency_seed_files as files
import hosted_initial_ordinary_identity as identity
import hosted_initial_ordinary_originals as acquisition
import hosted_initial_ordinary_productive_qualification as qualification
import hosted_initial_recipient_continuity as continuity
import hosted_test_query as queries

S, I, NS = acquisition.stages, acquisition.I, origin.NS
WINDOW_SCOPE = "INITIAL_ORDINARY_NATIVE_SOURCE_WINDOW_V1"
CONTEXT_SCOPE = "INITIAL_ORDINARY_NATIVE_ACQUISITION_CONTEXT_V1"
START_SCOPE = "INITIAL_ORDINARY_NATIVE_ACQUISITION_START_V1"
CHILD_SCOPE = "INITIAL_ORDINARY_ACQUIRED_PENDING_NATIVE_PARENT_CLOSE_V1"
ACK_SCOPE = "INITIAL_ORDINARY_CHILD_ORIGINAL_OWNER_RETURN_V1"
RETURN_SCOPE = "INITIAL_ORDINARY_ORIGINAL_CURRENT_SOURCE_V1"
HISTORY_SCOPE = "INITIAL_ORDINARY_RETAINED_PACKET_HISTORY_DATA_V1"
SOURCE_SECONDS, FINAL_SECONDS = 75, 120
SMALL_LIMIT, CONTROL_LIMIT, FILE_COUNT = 4 * 1024 * 1024, 64 * 1024 * 1024, 1024
QUERY_KEYS = ("event", "source_binding", "base_policy_entry", "ancestry_raw", "candidate_policy_entry",
              "candidate_policy_raw", "prior_ancestry_raw", "observation", "match")
HTTP_KEYS = ("attempt", "jobs", "approvals", "comment", "environment", "branches", "main", "reviewed_ref", "pull_request")
CURRENT_KEYS = (*QUERY_KEYS, *HTTP_KEYS)
IDENTITY_ENV = (
    "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_REF", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
    "GITHUB_EVENT_NAME", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKSPACE", "GITHUB_EVENT_PATH",
    "GITHUB_SERVER_URL", "GITHUB_API_URL", "GITHUB_JOB", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME",
    "RUNNER_ENVIRONMENT", "RUNNER_TEMP", "ImageOS", "ImageVersion",
)
FORBIDDEN_SECRETS = ("GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN", "ACTIONS_CACHE_URL", "ACTIONS_RESULTS_URL",
                     "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL")
PURPOSES = ("gate", "worker", "seed", "provider", "custody", "evidence")
_OWNERS, _CLOSES, _RETURNS, _ATTEMPTS = {}, {}, {}, {}
_NATIVE_RETURNS = {}
_QUARANTINE = []
_OWNER_KEY = object()


def require(value, code):
    I.require(value, "INITIAL_ORDINARY_NATIVE_" + code)


def digest(raw):
    require(type(raw) is bytes, "DIGEST_BYTES")
    return hashlib.sha256(raw).hexdigest()


def _scalar(value):
    return origin.integer(value)


def _component(value):
    require(type(value) is str and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,100}", value), "FIXED_COMPONENT")
    return value


def _window(first, work_end, final_end):
    origin.clocks.validate_reading(first)
    work, final = _scalar(work_end), _scalar(final_end)
    require(first.nanoseconds < work <= final and work <= first.nanoseconds + SOURCE_SECONDS * NS and
        final <= first.nanoseconds + FINAL_SECONDS * NS, "SOURCE_WINDOW_BOUNDS")
    return {"schema": 1, "scope": WINDOW_SCOPE, "clock": origin.clock_value(first.clock),
        "firstNs": first.nanoseconds, "workEndNs": work, "finalEndNs": final,
        "budgetAcceptance": "NOT_ADMITTED", "ordinaryAcceptance": "NOT_PERFORMED"}


def _checked_window(value):
    S.fields(value, "schema scope clock firstNs workEndNs finalEndNs budgetAcceptance ordinaryAcceptance", "WINDOW_FIELDS")
    clock = origin.wire.clock_identity(value["clock"])
    expected = _window(origin.clocks.Reading(clock, _scalar(value["firstNs"])), value["workEndNs"], value["finalEndNs"])
    require(I.encoded(value) == I.encoded(expected), "WINDOW_CHANGED")
    return clock


class _Fence:
    """Native RAW high-water plus original inward-rounded LOCAL ends."""

    def __init__(self, value, first, first_local, cancelled):
        self.clock = _checked_window(value)
        require(origin.clocks.validate_reading(first).clock == self.clock and
            value["firstNs"] <= first.nanoseconds < value["workEndNs"] and callable(cancelled), "ACTUAL_WINDOW_CLOCK")
        require(type(first_local) is float and math.isfinite(first_local) and first_local >= 0, "ACTUAL_LOCAL_CLOCK")
        self.raw, self.work, self.final = I.encoded(value), value["workEndNs"], value["finalEndNs"]
        self.last, self.cancelled = first.nanoseconds, cancelled
        self.work_local = origin.wire._directed_deadline(first_local, SOURCE_SECONDS, self.work, self.last)
        self.final_local = origin.wire._directed_deadline(first_local, FINAL_SECONDS, self.final, self.last)

    def now(self, *, final=False, minimum=0, limit=None):
        self.last = origin.clocks.checked_now(self.clock, minimum_ns=max(self.last, _scalar(minimum)))
        end = self.final if final else self.work
        if limit is not None:
            end = min(end, _scalar(limit))
        require(self.last < end and time.monotonic() < (self.final_local if final else self.work_local),
                "ORIGINAL_WINDOW_EXPIRED")
        if not final:
            self.cancelled()
        return self.last

    def deadline(self, maximum, *, final=False, limit=None):
        local = time.monotonic()
        now = self.now(final=final, limit=limit)
        end = self.final if final else self.work
        if limit is not None:
            end = min(end, _scalar(limit))
        return min(self.final_local if final else self.work_local,
                   origin.wire._directed_deadline(local, maximum, end, now))


@dataclass(frozen=True, eq=False, repr=False)
class _ClosedOwner:
    raw: bytes = field(repr=False)


class _Owner:
    """One Stage2-only file ledger; no Stage1/private-return hydration."""

    def __init__(self, key, fence):
        require(key is _OWNER_KEY and type(fence) is _Fence, "OWNER_FACTORY")
        self.fence, self.thread, self.pid = fence, threading.get_ident(), os.getpid()
        self.resources, self.reads, self.writes, self.errors = [], [], [], []
        self.original = self.cancel = self.returned = None
        self.unknown = self.closed = False
        self.control_bytes = 0
        _OWNERS[id(self)] = self

    def guard(self, *, final=False):
        require(_OWNERS.get(id(self)) is self and threading.get_ident() == self.thread and os.getpid() == self.pid and
            not self.closed and (final or self.original is None) and not self.unknown, "OWNER_NOT_CURRENT")
        self.fence.now(final=final)
        return self.fence.final_local if final else self.fence.work_local

    def error(self, phase, error, *, unknown=False):
        require(type(phase) is str and isinstance(error, BaseException), "ORIGINAL_ERROR")
        if self.original is None:
            self.original = error
        if not isinstance(error, Exception) and self.cancel is None:
            self.cancel = error
        self.unknown |= unknown or bool(processes.retirement_details(error))
        # Exception objects/causes stay in this private graph. Serialized reasons
        # must not reveal a signed URL, credential, private path or raw response.
        self.errors.append((phase, error))
        if len(self.errors) > 64:
            self.unknown = True
        if self.unknown and not any(item is self for item in _QUARANTINE):
            _QUARANTINE.append(self)

    def acquire(self, name, factory, *, final=False):
        self.guard(final=final)
        require(type(name) is str and len(self.resources) < FILE_COUNT, "OWNER_RESOURCE_BOUND")
        try:
            resource = factory()
        except BaseException as error:
            self.error(name + "-allocation", error, unknown=True)
            raise
        self.resources.append([name, resource, False, False])
        if name == "dependency-seed-input":
            try:
                require(type(resource) in (files.PosixFile, files.windows.NativeFile), "ORIGINAL_SOURCE_FILE")
                before = resource.initial_info
                require(before.is_directory is False and type(before.size) is int and
                    0 <= before.size <= files.authority.MAX_XML_BYTES and resource.verify() == before,
                    "ORIGINAL_SOURCE_SIZE")
                require(self.control_bytes + before.size <= CONTROL_LIMIT, "CONTROL_BYTES")
                # Charge every real acquisition, including repeated source passes,
                # before F._small_read consumes it. No map-supplied size or refund.
                self.control_bytes += before.size
                self.guard(final=final)
            except BaseException as error:
                self.error(name + "-adopted-source", error)
                raise
        return resource

    def close_one(self, resource):
        rows = [row for row in self.resources if row[1] is resource]
        require(len(rows) == 1, "ORIGINAL_CLOSE_RESOURCE")
        row = rows[0]
        if row[2]:
            require(row[3], "PREVIOUS_CLOSE_UNKNOWN")
            return
        row[2] = True
        try:
            resource.close()
            row[3] = True
        except BaseException as error:
            self.error(row[0] + "-close", error, unknown=True)
            raise

    def directory(self, path, *, create=False, final=False):
        return self.acquire("directory", lambda: files.private_root(path, create=create), final=final)

    def read(self, directory, name, maximum=SMALL_LIMIT, *, final=False):
        end = self.guard(final=final)
        reader = self.acquire("reader", lambda: directory.open_file(_component(name), max_bytes=maximum,
                              deadline=end), final=final)
        raw, first = bytearray(), None
        try:
            before = reader.initial_info
            while len(raw) < before.size:
                self.guard(final=final)
                part = reader.read(min(65536, before.size - len(raw)))
                require(type(part) is bytes and 0 < len(part) <= before.size - len(raw), "READ_TRUNCATED")
                raw.extend(part)
            require(reader.read(1) == b"" and reader.verify() == before, "READ_EOF_OR_METADATA")
        except BaseException as error:
            first = error
            self.error("reader", error)
        try:
            self.close_one(reader)
        except BaseException as error:
            if first is None:
                first = error
        if first is not None:
            raise first
        self.guard(final=final)
        result = bytes(raw)
        require(len(self.reads) < FILE_COUNT, "READ_COUNT")
        self.reads.append((str(directory.path), name, result, I.encoded(before.as_dict()), reader))
        return result

    def write(self, directory, name, value, *, final=False):
        end = self.guard(final=final)
        raw = value if type(value) is bytes else I.encoded(value)
        require(len(raw) <= SMALL_LIMIT and self.control_bytes + len(raw) <= CONTROL_LIMIT, "CONTROL_BYTES")
        sink = self.acquire("writer", lambda: directory.create_file(_component(name), max_bytes=max(1, len(raw)),
                            deadline=end), final=final)
        first, offset = None, 0
        try:
            while offset < len(raw):
                self.guard(final=final)
                part = raw[offset:offset + 65536]
                count = sink.write(part)
                require(type(count) is int and 0 < count <= len(part), "WRITE_NO_PROGRESS")
                offset += count
            sink.sync()
            require(sink.verify().size == len(raw), "WRITE_SIZE")
        except BaseException as error:
            first = error
            self.error("writer", error)
        try:
            self.close_one(sink)
        except BaseException as error:
            if first is None:
                first = error
        if first is not None:
            raise first
        require(self.read(directory, name, max(1, len(raw)), final=final) == raw, "ORIGINAL_WRITE_READBACK")
        self.control_bytes += len(raw)
        self.writes.append((str(directory.path), name, raw, sink))
        return raw

    def close(self):
        require(not self.closed, "OWNER_CLOSE_ONCE")
        if not self.unknown:
            for _name, resource, _attempted, _closed in reversed(self.resources):
                if self.unknown:
                    break
                try:
                    self.close_one(resource)
                except BaseException:
                    break
        self.closed = True
        try:
            returned_ns = self.fence.now(final=True)
        except BaseException as error:
            self.error("owner-final-fence", error)
            returned_ns = None
        if self.original is not None or self.unknown or not all(row[3] for row in self.resources):
            raise self.cancel or self.original or I.AdmissionError("INITIAL_ORDINARY_NATIVE_OWNER_CLOSE_UNKNOWN")
        raw = I.encoded({"schema": 1, "scope": "INITIAL_ORDINARY_ACTUAL_OWNER_CLOSE_V1",
            "resources": len(self.resources), "readers": len(self.reads), "writers": len(self.writes),
            "closedNs": returned_ns, "retirement": "KNOWN", "errors": []})
        result = _ClosedOwner(raw)
        self.returned = result
        _CLOSES[id(result)] = (result, self, tuple(tuple(row) for row in self.resources),
            tuple(self.reads), tuple(self.writes), self.thread, self.pid, raw)
        return result


def _checked_close(result):
    saved = _CLOSES.get(id(result))
    require(type(result) is _ClosedOwner and saved is not None and saved[0] is result, "ORIGINAL_CLOSE_RETURN")
    _, owner, resources, reads, writes, thread, pid, raw = saved
    require(_OWNERS.get(id(owner)) is owner and owner.returned is result and owner.closed and not owner.unknown and
        owner.original is None and owner.cancel is None and not owner.errors and
        thread == threading.get_ident() and pid == os.getpid() and len(resources) == len(owner.resources) and
        all(len(actual) == 4 and actual[0] == expected[0] and actual[1] is expected[1] and
            actual[2] is actual[3] is True for actual, expected in zip(owner.resources, resources)) and
        tuple(owner.reads) == reads and tuple(owner.writes) == writes, "CLOSED_OWNER_CHANGED")
    require(result.raw is raw, "CLOSE_BYTES_CHANGED")
    return owner


def _location(kind, invocation):
    require(kind in ("gate", "worker") and type(invocation) is str and re.fullmatch(r"[0-9a-f]{32}", invocation),
            "LOCATION_IDENTITY")
    run, attempt = os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_RUN_ATTEMPT")
    S.joint.run({"runId": run, "runAttempt": attempt})
    parent = Path(os.environ.get("RUNNER_TEMP", ""))
    require(parent.is_absolute() and parent == parent.resolve(strict=True) and parent.is_dir() and
        parent != ROOT and ROOT not in parent.parents and parent not in ROOT.parents, "PRIVATE_PARENT")
    for path in (parent, *parent.parents):
        info = path.lstat()
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and
            not getattr(info, "st_file_attributes", 0) & 0x400, "PRIVATE_PARENT_ALIAS")
    return parent / ("p2pkit-initial-ordinary-" + run + "-" + attempt + "-" + kind + "-" + invocation)


def _actual_context(kind, first_use_at):
    env = dict(os.environ)
    require(env.get("GITHUB_WORKSPACE") == str(ROOT) and ROOT == ROOT.resolve(strict=True), "SOURCE_ROOT")
    raw = I.read_regular(Path(env.get("GITHUB_EVENT_PATH", "")), I.EVENT_LIMIT)
    return acquisition._context(env, raw, kind, first_use_at), raw


def _installed_git():
    """Select the existing host tool once; never install or inherit a search path."""
    value = shutil.which("git")
    require(type(value) is str, "INSTALLED_GIT_MISSING")
    executable = Path(value).resolve(strict=True)
    require(executable.is_absolute() and executable.is_file() and
        executable.name == ("git.exe" if os.name == "nt" else "git") and
        executable != ROOT and ROOT not in executable.parents and
        os.pathsep not in str(executable.parent) and
        not any(ord(char) < 32 or ord(char) == 127 for char in str(executable)), "INSTALLED_GIT_LOCATION")
    return str(executable)


def _child_environment(path, job, invocation, token, installed_git):
    require(origin.wire.TOKEN_ENV not in os.environ and not any(name in os.environ for name in FORBIDDEN_SECRETS),
            "PARENT_TOKEN_ISOLATION")
    require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "READ_TOKEN")
    blocked = {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT", "BASH_ENV", "ENV", "ZDOTDIR"}
    require(not any(value and (name in blocked or name.startswith(("LD_", "DYLD_", "BASH_FUNC_")))
        for name, value in os.environ.items()), "EXECUTION_OVERRIDE")
    allowed = {*IDENTITY_ENV, "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL"}
    env = {name: value for name, value in os.environ.items() if name in allowed}
    env.update(queries._inherited_context())
    require(installed_git == _installed_git(), "ORIGINAL_INSTALLED_GIT_CHANGED")
    env.update(PATH=str(Path(installed_git).parent), HOME=str(path / "control-home"), USERPROFILE=str(path / "control-home"),
        TMPDIR=str(path / "temporary"), TMP=str(path / "temporary"), TEMP=str(path / "temporary"),
        PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", GIT_TERMINAL_PROMPT="0")
    if os.name == "nt":
        env.update(PATHEXT=".EXE", NoDefaultCurrentDirectoryInExePath="1")
    env = processes.ownership_environment(env, job, invocation, str(path), str(path / "control-home"),
                                           allow_new_context=True)
    env[origin.wire.TOKEN_ENV] = token
    return env


def _command(kind, invocation, context_sha256, minimum_ns, window, boot):
    require(kind in ("gate", "worker") and re.fullmatch(r"[0-9a-f]{32}", invocation) and
        re.fullmatch(r"[0-9a-f]{64}", context_sha256), "FIXED_CHILD_ARGUMENTS")
    _checked_window(window)
    S.digest(boot)
    return [str(Path(sys.executable).resolve(strict=True)), "-I", "-B", "-S", str(SCRIPTS / Path(__file__).name),
        "_acquire-child", kind, invocation, context_sha256, str(_scalar(minimum_ns)),
        str(window["firstNs"]), str(window["workEndNs"]), str(window["finalEndNs"]),
        window["clock"]["role"], window["clock"]["domain"], str(window["clock"]["ticksPerSecond"]), boot]


def _source_inputs(owner):
    """Actual fresh public source opens/EOF/metadata/known closes; no checkout."""
    end = owner.guard()
    return qualification.checked_inputs(compatibility.read_inputs(owner, ROOT, end, owner.guard))


def _page_links(headers, number, total, path):
    """Only complete finite same-endpoint pagination; links never choose a GET."""
    require(type(headers) is dict and type(number) is int and type(total) is int and
        0 <= total <= 1000 and 1 <= number <= max(1, (total + 99) // 100) and callable(path), "PAGE_LINK_INPUT")
    last = max(1, (total + 99) // 100)
    link = headers.get("link")
    if link is None:
        require(number == last, "PAGE_NEXT_LINK_MISSING")
        return
    require(type(link) is str and 0 < len(link) <= origin.wire.HEADER_LINE_LIMIT, "PAGE_LINK_LENGTH")
    expected = {"first": 1, "prev": number - 1, "next": number + 1, "last": last}
    found = set()
    for item in link.split(","):
        match = re.fullmatch(r'\s*<([^<>\s]+)>;\s*rel="(first|prev|next|last)"\s*', item)
        require(match is not None and match[2] not in found, "PAGE_LINK_SHAPE")
        relation, target = match[2], expected[match[2]]
        require(1 <= target <= last, "PAGE_LINK_RANGE")
        try:
            actual, wanted = urlsplit(match[1]), urlsplit(origin.wire.ORIGIN + path(target))
            query = parse_qsl(actual.query, keep_blank_values=True, strict_parsing=True)
            wanted_query = parse_qsl(wanted.query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            raise I.AdmissionError("INITIAL_ORDINARY_NATIVE_PAGE_LINK_SHAPE") from None
        require(actual.scheme == wanted.scheme and actual.netloc == wanted.netloc and actual.path == wanted.path and
            not actual.fragment and actual.username is None and actual.password is None, "PAGE_LINK_ORIGIN")
        require(len(query) == len({key for key, _value in query}) and
            sorted(query) == sorted(wanted_query), "PAGE_LINK_SELECTOR")
        found.add(relation)
    require(("next" in found) == (number < last), "PAGE_LINK_COMPLETENESS")


def _metadata_get(owner, directory, name, path, token, invocation, *, end, pagination=None):
    owner.fence.now(limit=end)
    raw, error = origin._request(path, token, invocation, owner.fence, end)
    try:
        owner.write(directory, name + ".json", raw, final=error is not None)
    except BaseException as secondary:
        if error is None:
            raise
        owner.error("failed-http-original-retention", secondary)
        raise error from secondary
    if error is not None:
        owner.error("original-http", error)
        raise error
    response, body, date = origin.response_bytes(raw, path, invocation, owner.fence.clock)
    _status, headers = origin.wire.headers(base64.b64decode(response["headersBase64"], validate=True))
    if pagination is None:
        require("link" not in headers, "INCOMPLETE_METADATA_RESPONSE")
    else:
        number, paths = pagination
        _page_links(headers, number, I.parse(body, qualification.references.PAGE_LIMIT).get("total_count"), paths)
    owner.fence.now(minimum=response["finishedNs"], limit=end)
    return body, date


def _pages(owner, directory, name, token, invocation, *, end, path, key):
    result, total = [], None
    for number in range(1, qualification.references.PAGE_COUNT + 1):
        requested = path(number)
        raw, _date = _metadata_get(owner, directory, name + "-" + str(number), requested, token, invocation,
                                  end=end, pagination=(number, path))
        value = I.parse(raw, qualification.references.PAGE_LIMIT)
        require(type(value.get("total_count")) is int and 0 <= value["total_count"] <= 1000 and
            type(value.get(key)) is list and len(value[key]) <= 100, "PAGED_COLLECTION")
        if total is None:
            total = value["total_count"]
        require(total == value["total_count"], "PAGED_TOTAL_CHANGED")
        result.append((requested, raw))
        if number == max(1, (total + 99) // 100):
            return tuple(result)
    raise I.AdmissionError("INITIAL_ORDINARY_NATIVE_PAGINATION_BOUND")


def _storage_location(location):
    """Only the original GitHub 302 may select a credential-free blob host."""
    require(type(location) is str and 0 < len(location) <= 8192 and
        all(32 < ord(char) < 127 for char in location), "STORAGE_LOCATION")
    try:
        parsed = urlsplit(location)
        host, port = parsed.hostname, parsed.port
    except ValueError:
        raise I.AdmissionError("INITIAL_ORDINARY_NATIVE_STORAGE_LOCATION") from None
    require(parsed.scheme == "https" and parsed.username is None and parsed.password is None and
        port in (None, 443) and type(host) is str and host == host.lower() and
        re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", host) and
        ".." not in host and (host.endswith(".blob.core.windows.net") or
        host.endswith(".actions.githubusercontent.com")) and parsed.path.startswith("/") and
        not parsed.fragment and "\\" not in location, "STORAGE_ORIGIN")
    return host, parsed.path + ("?" + parsed.query if parsed.query else "")


class _ArchiveReader:
    """Content-Length-only binary parser; metadata's small reader stays intact."""

    def __init__(self, stream, sock, fence, end, maximum):
        self.stream, self.sock, self.fence, self.end, self.maximum = stream, sock, fence, end, maximum
        self.header, self.in_headers, self.wire_bytes = bytearray(), True, 0
        self.close_attempted, self.close_error = False, None

    def _read(self, method, count):
        now = self.fence.now(limit=self.end)
        self.sock.settimeout(min(origin.wire.SOCKET_SECONDS, (self.end - now) / NS))
        raw = getattr(self.stream, method)(count)
        require(type(raw) is bytes and len(raw) <= count, "BINARY_READ_TYPE")
        self.wire_bytes += len(raw)
        require(self.wire_bytes <= self.maximum + origin.wire.HEADER_LIMIT + 1, "BINARY_WIRE_BOUND")
        if self.in_headers:
            self.header.extend(raw)
            require(len(self.header) <= origin.wire.HEADER_LIMIT, "BINARY_HEADER_BOUND")
        self.fence.now(limit=self.end)
        return raw

    def read(self, count=-1):
        require(type(count) is int and 0 <= count <= 65536, "BINARY_READ_BOUND")
        return self._read("read", count)

    def readinto(self, target):
        raw = self.read(len(target))
        target[:len(raw)] = raw
        return len(raw)

    def readline(self, count=-1):
        maximum = min(origin.wire.HEADER_LINE_LIMIT + 1, count) if count >= 0 else origin.wire.HEADER_LINE_LIMIT + 1
        raw = self._read("readline", maximum)
        require(len(raw) <= origin.wire.HEADER_LINE_LIMIT and (not raw or raw.endswith(b"\r\n")), "BINARY_HEADER_LINE")
        return raw

    def close(self):
        if self.close_attempted:
            if self.close_error is not None:
                raise self.close_error
            return
        self.close_attempted = True
        try:
            self.stream.close()
        except BaseException as error:
            self.close_error = error
            raise


def _archive_headers(raw, status, count):
    """The live download and later original-byte reader use ONE exact grammar."""
    require(type(status) is int and status in (200, 302) and type(count) is int and
        (count == 0 if status == 302 else 0 < count <= qualification.ZIP.MAX_ZIP_BYTES), "ARCHIVE_HEADER_INPUT")
    actual, fields = origin.wire.headers(raw)
    require(actual == status, "ARCHIVE_HTTP_STATUS")
    require(fields.get("content-encoding", "identity").lower() == "identity" and
        "transfer-encoding" not in fields and "content-range" not in fields and
        fields.get("content-length") == str(count), "ARCHIVE_EXACT_CONTENT_LENGTH")
    date = origin.wire.http_epoch(fields.get("date"))
    if status == 302:
        require(fields.get("age") in (None, "0") and not any(key in fields for key in
            ("warning", "via", "retry-after")) and fields.get("x-cache", "MISS").upper() in ("MISS", "BYPASS") and
            fields.get("x-github-api-version-selected") == "2022-11-28" and
            type(fields.get("x-github-request-id")) is str and
            re.fullmatch(r"[A-Za-z0-9:-]{8,128}", fields["x-github-request-id"]), "ARCHIVE_ORIGINAL_REDIRECT")
        _storage_location(fields.get("location"))
    else:
        require("location" not in fields, "ARCHIVE_SECOND_REDIRECT_FORBIDDEN")
    return fields, date


def _archive_http(owner, directory, name, host, path, *, token, invocation, end, count, sink=None):
    """One original request; no redirects/retries/proxy/netrc/caller TLS policy.

    Parent native ownership is the external whole-call safety bound. Each read
    keeps the unextended request15/socket5 and the original acquisition45 end.
    Original signed redirect headers are retained privately, never as logs.
    """
    first = owner.fence.now(limit=end)
    request_end = min(end, first + origin.wire.REQUEST_SECONDS * NS)
    connection = response = reader = None
    header, length, content, location, failure = b"", 0, hashlib.sha256(), None, None
    close_errors, complete, status = [], False, None
    require((token is not None and host == origin.wire.HOST and count == 0 and sink is None) or
        (token is None and sink is not None and 0 < count <= qualification.ZIP.MAX_ZIP_BYTES and
            _storage_location("https://" + host + path) == (host, path)), "ARCHIVE_REQUEST_KIND")
    try:
        connection = http.client.HTTPSConnection(host, timeout=min(origin.wire.SOCKET_SECONDS,
            (request_end - first) / NS), context=ssl.create_default_context())

        class Response(http.client.HTTPResponse):
            def __init__(self, sock, **kwargs):
                nonlocal reader
                super().__init__(sock, **kwargs)
                reader = _ArchiveReader(self.fp, sock, owner.fence, request_end, count)
                self.fp = reader

        connection.response_class = Response
        headers = {"Accept": "application/octet-stream", "Accept-Encoding": "identity", "Connection": "close",
            "Cache-Control": "no-cache, max-age=0", "Pragma": "no-cache", "User-Agent": "P2pKit-initial-ordinary"}
        if token is not None:
            require(re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "ARCHIVE_READ_TOKEN")
            headers.update(Authorization="Bearer " + token, **{"X-GitHub-Api-Version": "2022-11-28"})
        owner.fence.now(limit=request_end)
        connection.request("GET", path, headers=headers)
        owner.fence.now(limit=request_end)
        response = connection.getresponse()
        header = bytes(reader.header)
        reader.in_headers = False
        status = response.status
        require(status == (302 if token is not None else 200), "ARCHIVE_HTTP_STATUS")
        fields, _date = _archive_headers(header, status, count)
        location = fields.get("location")
        while length < count:
            owner.fence.now(limit=request_end)
            raw = response.read(min(65536, count - length))
            require(type(raw) is bytes and 0 < len(raw) <= count - length, "ARCHIVE_BODY_TRUNCATED")
            content.update(raw)
            length += len(raw)
            offset = 0
            while offset < len(raw):
                owner.fence.now(limit=request_end)
                written = sink.write(raw[offset:])
                require(type(written) is int and 0 < written <= len(raw) - offset, "ARCHIVE_WRITE_NO_PROGRESS")
                offset += written
        require(response.read(1) == b"", "ARCHIVE_BODY_EOF")
        owner.fence.now(limit=request_end)
        complete = True
    except BaseException as error:
        failure = error
    finally:
        if reader is not None:
            header = bytes(reader.header)
        for label, resource in (("response", response if response is not None else reader), ("connection", connection)):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    close_errors.append((label, error))
                    if failure is None:
                        failure = error
        if reader is not None and reader.close_error is not None and not close_errors:
            close_errors.append(("response-reader", reader.close_error))
    try:
        finished = owner.fence.now(limit=request_end)
    except BaseException as error:
        finished, failure = None, failure or error
    raw = I.encoded({"schema": 1, "scope": "PRIVATE_INITIAL_ORDINARY_ARCHIVE_RESPONSE_V1", "host": host,
        "path": path, "invocation": invocation, "clock": origin.clock_value(owner.fence.clock),
        "startedNs": first, "finishedNs": finished, "status": status,
        "headersBase64": base64.b64encode(header[:origin.wire.HEADER_LIMIT]).decode("ascii"),
        "bodyBytes": length, "bodySha256": content.hexdigest(), "complete": complete and failure is None,
        "retirement": "UNKNOWN" if close_errors else "KNOWN", "error": None if failure is None else "ARCHIVE_FAILED"})
    try:
        owner.write(directory, name + ".json", raw, final=failure is not None)
    except BaseException as error:
        if failure is None:
            failure = error
        else:
            owner.error("archive-original-retention", error)
    for label, error in close_errors:
        owner.error("archive-" + label + "-close", error, unknown=True)
    if failure is not None:
        owner.error("archive-http", failure)
        raise failure
    return location, content.hexdigest()


def _download(owner, directory, packet, token, invocation, end):
    path = qualification.API + "/actions/artifacts/" + str(S.positive(packet["artifactId"])) + "/zip"
    location, _empty_sha = _archive_http(owner, directory, "archive-redirect", origin.wire.HOST, path,
        token=token, invocation=invocation, end=end, count=0)
    host, target = _storage_location(location)
    sink = owner.acquire("archive-writer", lambda: directory.create_file("packet.zip", max_bytes=packet["bytes"],
        deadline=owner.fence.work_local))
    failure = None
    try:
        _location_unused, checksum = _archive_http(owner, directory, "archive-download", host, target,
            token=None, invocation=invocation, end=end, count=packet["bytes"], sink=sink)
        require(checksum == packet["sha256"], "ARCHIVE_DOWNLOAD_DIGEST")
        owner.guard()
        sink.sync()
        require(sink.verify().size == packet["bytes"], "ARCHIVE_DOWNLOAD_SIZE")
    except BaseException as error:
        failure = error
        owner.error("archive-download", error)
    if not owner.unknown:
        try:
            owner.close_one(sink)
        except BaseException as error:
            if failure is None:
                failure = error
    if failure is not None:
        raise failure


def _packet_read(owner, directory, members, packet, *, final=False):
    end = owner.guard(final=final)
    reader = owner.acquire("packet-reader", lambda: directory.open_file("packet.zip", max_bytes=packet["bytes"],
        deadline=end), final=final)
    failure, result = None, None
    try:
        original = reader.initial_info
        require(original.size == packet["bytes"], "PACKET_ORIGINAL_SIZE")
        result = qualification.read_stored_zip(reader, members, packet, lambda: owner.guard(final=final))
        require(reader.verify() == original, "PACKET_ORIGINAL_METADATA_CHANGED")
    except BaseException as error:
        failure = error
        owner.error("packet-reader", error)
    try:
        owner.close_one(reader)
    except BaseException as error:
        if failure is None:
            failure = error
    if failure is not None:
        raise failure
    owner.guard(final=final)
    observed = {"name": "packet.zip", "bytes": packet["bytes"], "sha256": packet["sha256"],
        "native": original.as_dict(), "retirement": "KNOWN", "readAtNs": owner.fence.last}
    # A new complete read observation, never a fabricated old original record.
    return result, observed


def _query_pass(owner, private, context, token, invocation, *, first, histories=(), expected=None):
    name = "current-first" if first else "current-last"
    path = Path(private.path) / name
    supplier, failure, returned = None, None, None
    try:
        owner.guard()
        supplier = queries.NativeGitQueries(ROOT, path, check_cancel=owner.guard,
            owner_deadlines=(owner.fence.work_local, owner.fence.final_local))
        supplier.native_host_matches_actions()
        require(type(supplier.executable) is str and supplier.executable == _installed_git() and
            os.environ.get("PATH") == str(Path(supplier.executable).parent) and (os.name != "nt" or
                os.environ.get("PATHEXT") == ".EXE" and os.environ.get("NoDefaultCurrentDirectoryInExePath") == "1"),
            "ORIGINAL_CHILD_GIT_SELECTION")

        def retain(label, raw, *, failed):
            require(label in CURRENT_KEYS, "FIXED_CURRENT_ORIGINAL")
            owner.guard(final=failed)
            supplier._write(supplier.private, label + ".bin", raw)
            owner.guard(final=failed)

        arguments = {"kind": context["kind"], "query_runner": supplier, "invocation": invocation,
            "token": token, "retain": retain, "fence": owner.fence, "original_work_end": owner.fence.work,
            "first_use_at": context["firstUseAt"]}
        if first:
            returned = acquisition.acquire_current_references(ROOT, **arguments)
        else:
            returned = acquisition.acquire_ordinary(ROOT, **arguments, histories=histories, expected=expected)
    except BaseException as error:
        failure = error
    finally:
        if supplier is not None:
            try:
                supplier._finalize(failure)
            except BaseException as error:
                failure = failure or error
            if supplier.failed or supplier.unknown or not supplier.closed:
                failure = failure or I.AdmissionError("INITIAL_ORDINARY_NATIVE_QUERY_FINALIZER")
                owner.error("query-finalizer", failure, unknown=supplier.unknown)
        if queries.QUARANTINE:
            failure = failure or I.AdmissionError("INITIAL_ORDINARY_NATIVE_QUERY_QUARANTINE")
            owner.error("query-quarantine", failure, unknown=True)
    if failure is not None:
        owner.error("native-queries", failure)
        raise failure
    owner.guard()
    directory = owner.directory(path)
    session_raw = owner.read(directory, "session-result.json")
    session = I.parse(session_raw, SMALL_LIMIT)
    require(session.get("result") == "READY_FOR_CALLER_SEAL" and session.get("retirement") == "KNOWN" and
        session.get("firstError") is None and session.get("errors") == [], "QUERY_ORIGINAL_SESSION")
    result, originals = returned
    require(type(originals) is tuple and len(originals) == len(CURRENT_KEYS) and
        set(dict(originals)) == set(CURRENT_KEYS) and all(owner.read(directory, label + ".bin") == raw
            for label, raw in originals), "QUERY_ORIGINAL_READBACK")
    owner.close_one(directory)
    return result, originals, digest(session_raw)


def _acquire_packet(owner, private, number, entry, declaration, authority_at, current_inputs, token, invocation,
                    previous=None):
    started = owner.fence.now()
    end = min(owner.fence.work, started + origin.wire.ACQUIRE_SECONDS * NS)
    directory = owner.acquire("packet-directory", lambda: private.create_directory("packet-" + str(number),
        deadline=owner.fence.work_local))
    originals = {}
    for name in ("inventory", "compatibility", "review"):
        originals[name], _date = _metadata_get(owner, directory, name, qualification.references.metadata_path(entry[name]),
            token, invocation, end=end)
    inventory, compatible, _review, _bodies = qualification.public_metadata(originals, entry, declaration, authority_at)
    base = qualification.API + "/actions/runs/" + entry["runId"] + "/attempts/" + entry["runAttempt"]
    attempt_raw, _date = _metadata_get(owner, directory, "attempt", base, token, invocation, end=end)
    jobs_raw, _date = _metadata_get(owner, directory, "jobs", base + "/jobs?per_page=100&page=1", token,
        invocation, end=end)
    selected = qualification.completed_job(attempt_raw, jobs_raw, entry, declaration["stage1"]["reviewed"])
    job_raw, job_date = _metadata_get(owner, directory, "job", qualification.API + "/actions/jobs/" + str(selected["id"]),
        token, invocation, end=end)
    artifact_raw, _date = _metadata_get(owner, directory, "artifact", qualification.API + "/actions/artifacts/" +
        str(entry["packet"]["artifactId"]), token, invocation, end=end)
    pages = _pages(owner, directory, "artifacts", token, invocation, end=end,
        path=lambda page: qualification.references.inventory_path(entry["runId"], page), key="artifacts")
    cache_pages = _pages(owner, directory, "caches", token, invocation, end=end,
        path=lambda page: qualification.cache_inventory_path(compatible["provider"], page), key="actions_caches")
    if previous is None:
        _download(owner, directory, entry["packet"], token, invocation, end)
        packet_directory = directory
    else:
        # The original native parent's retained packet path is hash/context-bound
        # input, never an arbitrary cache path or an alternate download fallback.
        require(type(previous) is dict and set(previous) == {"path", "packet", "members"} and
            I.encoded(previous["packet"]) == I.encoded(entry["packet"]) and
            I.encoded(previous["members"]) == I.encoded(inventory["members"]), "PREVIOUS_PACKET_BINDING")
        packet_directory = owner.directory(Path(previous["path"]))
    manifests, read = _packet_read(owner, packet_directory, inventory["members"], entry["packet"])
    owner.fence.now(limit=end)
    result = qualification.qualify(originals=originals, entry=entry, declaration=declaration,
        authority_created_at=authority_at, attempt_raw=attempt_raw, jobs_raw=jobs_raw, job_raw=job_raw, job_date=job_date,
        artifact_raw=artifact_raw, inventory_pages=pages, cache_pages=cache_pages, manifests=manifests,
        current_inputs=current_inputs, now=int(time.time()))
    owner.write(directory, "qualification.json", result.record)
    owner.write(directory, "packet-read.json", read)
    owner.write(directory, "packet-acquisition.json", {"schema": 1,
        "scope": "INITIAL_ORDINARY_ORIGINAL_PACKET_ACQUISITION_V1", "invocation": invocation,
        "clock": origin.clock_value(owner.fence.clock), "firstNs": started, "workEndNs": end,
        "completedNs": owner.fence.now(limit=end), "packet": entry["packet"],
        "source": declaration["stage1"]["reviewed"], "selection": entry["selection"],
        "archive": "ORIGINAL_DOWNLOAD" if previous is None else "ORIGINAL_RETAINED_BYTES"})
    retained = {"path": str(packet_directory.path), "packet": entry["packet"], "members": inventory["members"]}
    if packet_directory is not directory:
        owner.close_one(packet_directory)
    owner.close_one(directory)
    owner.fence.now(limit=end)
    return result, retained


def _previous_paths(previous, kind):
    if previous is None:
        return (None,) * 4
    require(type(previous) is list and len(previous) == 4, "PREVIOUS_PACKET_ROSTER")
    temp = Path(os.environ.get("RUNNER_TEMP", ""))
    prefix = "p2pkit-initial-ordinary-" + os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"] + "-" + kind + "-"
    parent = None
    for number, item in enumerate(previous, 1):
        require(type(item) is dict and set(item) == {"path", "packet", "members"}, "PREVIOUS_PACKET_FIELDS")
        path = Path(item["path"])
        require(path.is_absolute() and str(path) == item["path"] and path.name == "packet-" + str(number) and
            path.parent.parent == temp and path.parent.name.startswith(prefix) and
            re.fullmatch(r"[0-9a-f]{32}", path.parent.name[len(prefix):]), "PREVIOUS_FIXED_PACKET_PATH")
        if parent is None:
            parent = path.parent
        require(path.parent == parent, "PREVIOUS_SAME_PACKET_SET")
        qualification.ZIP.checked_members(item["members"])
    return tuple(previous)


def _context_bytes(raw, kind, invocation, window, boot):
    value = S.fields(qualification.canonical(raw, SMALL_LIMIT), "schema scope root session job invocation observed "
        "eventSha256 window bootDigest inheritedContext git previous expectedMatch", "NATIVE_CONTEXT_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == CONTEXT_SCOPE and
        value["root"] == str(ROOT) and value["session"] == str(_location(kind, invocation)) and
        value["invocation"] == invocation and re.fullmatch(r"[0-9a-f]{32}", value["job"]) and
        I.encoded(value["window"]) == I.encoded(window) and value["bootDigest"] == boot and
        value["git"] == _installed_git(), "ACTUAL_CONTEXT_BINDING")
    context, event = _actual_context(kind, value["observed"]["firstUseAt"])
    require(I.encoded(context) == I.encoded(value["observed"]) and digest(event) == value["eventSha256"],
            "ACTUAL_CONTEXT_CHANGED")
    _previous_paths(value["previous"], kind)
    if value["expectedMatch"] is not None:
        require(type(value["expectedMatch"]) is dict and value["previous"] is not None, "EXPECTED_ORIGINAL_MATCH")
    require(type(value["inheritedContext"]) is dict, "PARENT_NATIVE_CONTEXT")
    return value, event


def _child(kind, invocation, context_sha256, minimum_ns, window, boot, cancelled):
    """Fixed private child; its stdout ACK exists only after actual owner close."""
    token = os.environ.pop(origin.wire.TOKEN_ENV, None)
    first_local, first = time.monotonic(), origin.clocks.observe()
    require(first.nanoseconds >= minimum_ns and first.clock == _checked_window(window) and
        continuity.boot_digest(first.clock.role) == boot and not any(name in os.environ for name in FORBIDDEN_SECRETS),
        "CHILD_NATIVE_CLOCK_OR_CREDENTIALS")
    fence = _Fence(window, first, first_local, cancelled)
    owner = _Owner(_OWNER_KEY, fence)
    result_raw = None
    try:
        path = _location(kind, invocation)
        private = owner.directory(path)
        context_raw = owner.read(private, "context.json")
        require(digest(context_raw) == context_sha256, "CHILD_ORIGINAL_CONTEXT")
        context, event = _context_bytes(context_raw, kind, invocation, window, boot)
        service = owner.directory(path / "service")
        start_raw = owner.read(service, "start.json")
        start = S.fields(qualification.canonical(start_raw, SMALL_LIMIT), "schema scope contextSha256 argv invocation job "
            "session home clock bootDigest startedNs workEndNs finalEndNs inheritedContext launchAttempted "
            "scopeAttempted exitCode retirement", "NATIVE_START_FIELDS")
        inherited = queries._inherited_context()
        require(start["schema"] == 1 and type(start["schema"]) is int and start["scope"] == START_SCOPE and
            start["contextSha256"] == context_sha256 and start["invocation"] == invocation and
            start["job"] == context["job"] and start["session"] == str(path) and
            start["home"] == str(path / "control-home") and start["clock"] == window["clock"] and
            start["bootDigest"] == boot and start["startedNs"] == minimum_ns and
            (start["workEndNs"], start["finalEndNs"]) == (fence.work, fence.final) and
            start["argv"] == _command(kind, invocation, context_sha256, minimum_ns, window, boot) and
            start["inheritedContext"] == inherited and start["launchAttempted"] is start["scopeAttempted"] is False and
            start["exitCode"] is None and start["retirement"] == "UNKNOWN", "ORIGINAL_CHILD_LAUNCH")
        expected_context = processes.ownership_environment(context["inheritedContext"], context["job"], invocation,
            str(path), str(path / "control-home"), allow_new_context=True)
        require(inherited == {name: expected_context[name] for name in queries._CONTEXT}, "CHILD_ORIGINAL_NATIVE_DOMAIN")
        require(fence.now() < first.nanoseconds + origin.wire.ACQUIRE_SECONDS * NS, "CHILD_INITIAL_METADATA45")
        current_inputs = _source_inputs(owner)
        owner.write(private, "source-inputs.json", current_inputs)
        reference, first_raws, first_session = _query_pass(owner, private, context["observed"], token, invocation, first=True)
        require(type(reference) is acquisition.CurrentReferences and dict(first_raws)["event"] == event,
                "CHILD_FIRST_REFERENCES_ONLY")
        reference_value = I.parse(reference.record, SMALL_LIMIT)
        declaration = reference_value["declaration"]
        # The selected exact original comment comes from its transport body,
        # not a guessed authority locator or reserialized statement.
        selection_response = I.parse(dict(first_raws)["approvals"], SMALL_LIMIT)
        approval_raw = base64.b64decode(selection_response["bodyBase64"], validate=True)
        selector = acquisition.gate.select(stage="stage2", run_id=context["observed"]["github"]["runId"],
            attempt=context["observed"]["github"]["runAttempt"], approvals_raw=approval_raw)
        selected = I.parse(selector.record, SMALL_LIMIT)
        _response, comment_raw, _date = origin.response_bytes(dict(first_raws)["comment"], qualification.API +
            "/issues/comments/" + str(selected["commentId"]), invocation, fence.clock)
        _same_decl, _authority, authority_at = S.statement(S.STAGE2, comment_raw, selected["commentId"], selected["bodySha256"])
        require(_same_decl == declaration, "ORIGINAL_DECLARATION")
        entries = declaration["qualifications"]
        require(type(entries) is list and len(entries) == 4, "ALL_FOUR_QUALIFICATIONS")
        previous = _previous_paths(context["previous"], kind)
        qualifications, packets = [], []
        for number, (entry, old) in enumerate(zip(entries, previous), 1):
            qualified, retained = _acquire_packet(owner, private, number, entry, declaration, authority_at,
                current_inputs, token, invocation, old)
            qualifications.append(qualified)
            packets.append(retained)
        require(I.encoded(_source_inputs(owner)) == I.encoded(current_inputs), "INPUTS_CHANGED_DURING_ACQUISITION")
        histories = tuple(item.history for item in qualifications)
        expected = None if context["expectedMatch"] is None else (
            acquisition.gate.GateEligibility if kind == "gate" else S.OrdinaryMatch)(I.encoded(context["expectedMatch"]))
        match, last_raws, last_session = _query_pass(owner, private, context["observed"], token, invocation,
            first=False, histories=histories, expected=expected)
        token = None
        require(dict(last_raws)["event"] == event and
            dict(first_raws)["candidate_policy_raw"] == dict(last_raws)["candidate_policy_raw"], "CURRENT_EVENT_OR_POLICY_CHANGED")
        result_raw = owner.write(service, "child-result.json", {"schema": 1, "scope": CHILD_SCOPE,
            "contextSha256": context_sha256, "startSha256": digest(start_raw), "invocation": invocation,
            "clock": window["clock"], "bootDigest": boot, "startedNs": first.nanoseconds,
            "completedNs": fence.now(), "firstSessionSha256": first_session, "lastSessionSha256": last_session,
            "sourceInputsSha256": digest(I.encoded(current_inputs)), "matchSha256": digest(match.record),
            "qualifications": [digest(item.record) for item in qualifications], "packets": packets,
            "retirement": "PENDING_CHILD_OWNER_CLOSE", "ordinaryAcceptance": "NOT_PERFORMED",
            "h2ProviderAcceptance": "NOT_PERFORMED", "cryptoAcceptance": "NOT_PERFORMED"})
    except BaseException as error:
        owner.error("child-acquisition", error)
    finally:
        token = None
    closed = owner.close()
    _checked_close(closed)
    require(result_raw is not None, "CHILD_MISSING_ORIGINAL_RESULT")
    closed_ns = fence.now()
    return I.encoded({"schema": 1, "scope": ACK_SCOPE, "contextSha256": context_sha256,
        "invocation": invocation, "terminalSha256": digest(result_raw), "ownerCloseSha256": digest(closed.raw),
        "ownerCloseBase64": base64.b64encode(closed.raw).decode("ascii"),
        "closedNs": closed_ns, "clock": window["clock"], "bootDigest": boot, "retirement": "KNOWN"})


@dataclass(frozen=True, eq=False, repr=False)
class _NativeReturn:
    scope: object = field(repr=False)
    child: object = field(repr=False)
    start_raw: bytes = field(repr=False)
    baseline_raw: bytes = field(repr=False)
    result_raw: bytes = field(repr=False)
    stdout_raw: bytes = field(repr=False)
    stderr_raw: bytes = field(repr=False)


def _launch(owner, private, context_raw, token):
    context = I.parse(context_raw, SMALL_LIMIT)
    invocation, job, kind = context["invocation"], context["job"], context["observed"]["kind"]
    path, window, boot = Path(context["session"]), context["window"], context["bootDigest"]
    service = owner.acquire("service-directory", lambda: private.create_directory("service", deadline=owner.guard()))
    output_parent = service
    if os.name != "nt":
        output_parent = owner.acquire("stdio-directory", lambda: queries._PosixDirectory(Path(service.path)))
    out = owner.acquire("native-stdout", lambda: output_parent.create_file("stdout.log", max_bytes=16384,
        deadline=owner.fence.final_local))
    err = owner.acquire("native-stderr", lambda: output_parent.create_file("stderr.log", max_bytes=65536,
        deadline=owner.fence.final_local))
    environment = _child_environment(path, job, invocation, token, context["git"])
    started = owner.fence.now()
    command = _command(kind, invocation, digest(context_raw), started, window, boot)
    start_raw = owner.write(service, "start.json", {"schema": 1, "scope": START_SCOPE,
        "contextSha256": digest(context_raw), "argv": command, "invocation": invocation, "job": job,
        "session": str(path), "home": str(path / "control-home"), "clock": window["clock"], "bootDigest": boot,
        "startedNs": started, "workEndNs": owner.fence.work, "finalEndNs": owner.fence.final,
        "inheritedContext": {name: environment[name] for name in queries._CONTEXT}, "launchAttempted": False,
        "scopeAttempted": False, "exitCode": None, "retirement": "UNKNOWN"})
    scope = child = baseline_raw = None
    status = {"schema": 1, "scope": "INITIAL_ORDINARY_NATIVE_CHILD_RETURN_PENDING_OWNER_CLOSE_V1",
        "startSha256": digest(start_raw), "invocation": invocation, "launchAttempted": False,
        "scopeAttempted": False, "exitCode": None, "retirement": "UNKNOWN", "completedNs": None,
        "ownedSurvivors": None, "ownership": None, "errors": [], "captures": {}}
    failure = None
    try:
        owner.guard()
        status["scopeAttempted"] = True
        scope = owner.acquire("native-scope", lambda: processes.make_scope(job, invocation, str(path),
            str(path / "control-home")))
        baseline_raw = owner.write(service, "baseline.json", {"nativeRole": owner.fence.clock.role,
            "baseline": sorted(scope.baseline) if hasattr(scope, "baseline") else None,
            "kernelJob": owner.fence.clock.role == "windows-x64"})
        owner.guard()
        status["launchAttempted"] = True
        child = scope.spawn(command, str(ROOT), environment, stdout=out, stderr=err)
        environment.pop(origin.wire.TOKEN_ENV, None)
        token = None
        require(child.stdout is None and child.stderr is None, "OWNED_NATIVE_STDIO")
        while True:
            owner.guard()
            if os.name == "nt":
                out.observe_live_output()
                err.observe_live_output()
            else:
                out.verify()
                err.verify()
            code = child.poll()
            if code is not None:
                status["exitCode"] = code
                break
            scope.discover()
            time.sleep(0.025)
        require(type(code) is int and code == 0 and not scope.discover(), "CHILD_EXIT_OR_DESCENDANTS")
        status["completedNs"] = owner.fence.now()
    except BaseException as error:
        failure = error
        owner.error("native-child", error)
    finally:
        environment.pop(origin.wire.TOKEN_ENV, None)
        token = None
        native_known = scope is not None
        if scope is not None:
            try:
                status["ownedSurvivors"] = scope.drain(grace=0, kill_wait=5, deadline=owner.fence.final_local)
                owner.fence.now(final=True)
                require(status["ownedSurvivors"] == [], "NATIVE_SURVIVORS")
            except BaseException as error:
                native_known = False
                owner.error("native-drain", error, unknown=True)
                failure = failure or error
            try:
                status["ownership"] = scope.description()
                require(status["ownership"].get("discoveryErrors") == [], "NATIVE_DISCOVERY_UNKNOWN")
            except BaseException as error:
                native_known = False
                owner.error("native-description", error, unknown=True)
                failure = failure or error
            try:
                owner.close_one(scope)
            except BaseException as error:
                native_known = False
                failure = failure or error
        elif status["scopeAttempted"]:
            owner.error("native-constructor", failure or I.AdmissionError("INITIAL_ORDINARY_NATIVE_CONSTRUCTOR_UNKNOWN"),
                        unknown=True)
        if native_known and not owner.unknown:
            for name, sink in (("stdout", out), ("stderr", err)):
                try:
                    owner.fence.now(final=True)
                    sink.sync()
                    status["captures"][name] = sink.verify().as_dict()
                    owner.close_one(sink)
                except BaseException as error:
                    owner.error("native-" + name + "-final", error)
                    failure = failure or error
    if owner.unknown:
        raise failure or I.AdmissionError("INITIAL_ORDINARY_NATIVE_RETIREMENT_UNKNOWN")
    out_raw = owner.read(service, "stdout.log", 16384, final=failure is not None)
    err_raw = owner.read(service, "stderr.log", 65536, final=failure is not None)
    for name, raw in (("stdout", out_raw), ("stderr", err_raw)):
        status["captures"][name].update(bytes=len(raw), sha256=digest(raw))
    status.update(retirement="KNOWN", errors=[] if failure is None else ["NATIVE_CHILD_FAILED"])
    result_raw = owner.write(service, "result.json", status, final=failure is not None)
    if failure is not None:
        raise failure
    kind = (processes.WindowsScope if owner.fence.clock.role == "windows-x64" else processes.LinuxScope
        if owner.fence.clock.role == "linux-x64" else processes.DarwinScope)
    require(err_raw == b"" and type(scope) is kind, "NATIVE_RETURN_KIND")
    result = _NativeReturn(scope, child, start_raw, baseline_raw, result_raw, out_raw, err_raw)
    _NATIVE_RETURNS[id(result)] = (result, owner, tuple(getattr(result, name) for name in result.__dataclass_fields__))
    owner.guard()
    return result


def _checked_native(result, owner):
    saved = _NATIVE_RETURNS.get(id(result))
    require(type(result) is _NativeReturn and saved is not None and saved[0] is result and saved[1] is owner and
        all(getattr(result, name) is original for name, original in zip(result.__dataclass_fields__, saved[2])),
        "ORIGINAL_NATIVE_RETURN")
    require(any(row[1] is result.scope and row[2] is row[3] is True for row in owner.resources), "NATIVE_CLOSE_NOT_RETURNED")
    return result


def _query_source_sequence(rows, outputs, originals, context, declaration):
    """Parse the fixed original32-query graph. No GitView/replay/admission."""
    source = S.fields(qualification.canonical(originals["source_binding"], SMALL_LIMIT),
        "source reviewed mergeParents", "ORIGINAL_SOURCE_FIELDS")
    head, merge, prior = context["reviewedCommit"], context["sourceCommit"], declaration["stage1"]["reviewed"]
    require(source == {"source": declaration["firstPullRequest"]["merge"], "reviewed": declaration["reviewed"],
        "mergeParents": [S.BASE["commit"], head]} and source["source"]["commit"] == merge and
        source["reviewed"]["commit"] == head, "ORIGINAL_QUERY_SOURCE_BINDING")
    entry, policy = originals["candidate_policy_entry"], originals["candidate_policy_raw"]
    blob = hashlib.sha1(b"blob " + str(len(policy)).encode("ascii") + b"\0" + policy).hexdigest()
    require(0 < len(policy) <= I.POLICY_LIMIT and digest(policy) == S.POLICY_SHA256 and entry ==
        b"100644 blob " + blob.encode("ascii") + b"\t" + I.POLICY_PATH.encode("ascii") + b"\x00" and
        originals["base_policy_entry"] == b"", "ORIGINAL_QUERY_POLICY")
    acquisition._line(originals["ancestry_raw"], S.BASE["commit"], "ORIGINAL_QUERY_BASE_ANCESTRY")
    acquisition._line(originals["prior_ancestry_raw"], prior["commit"], "ORIGINAL_QUERY_H1_ANCESTRY")
    commands = (
        ("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
        ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--is-shallow-repository"),
        ("rev-parse", "--verify", merge + "^{tree}"), ("rev-parse", "--verify", head + "^{tree}"),
        ("show", "-s", "--format=%P", merge), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
        ("rev-parse", "--verify", S.BASE["commit"] + "^{tree}"),
        ("ls-tree", "-z", S.BASE["commit"], "--", I.POLICY_PATH),
        ("merge-base", S.BASE["commit"], head), ("ls-tree", "-z", head, "--", I.POLICY_PATH),
        ("cat-file", "-s", blob), ("cat-file", "blob", blob),
        ("rev-parse", "--verify", prior["commit"] + "^{tree}"), ("merge-base", prior["commit"], head),
    )
    require(type(rows) is list and type(outputs) is list and len(rows) == len(outputs) == 2 * len(commands),
            "ORIGINAL_QUERY_COMPLETE_SEQUENCE")
    for index, (row, raw) in enumerate(zip(rows, outputs)):
        position = index % len(commands)
        limit = I.EVENT_LIMIT if position == 1 else I.POLICY_LIMIT if position == 13 else 4096
        require(tuple(row["argv"][7:]) == commands[position] and row["stdoutLimit"] == limit and
            type(raw) is bytes and len(raw) <= limit, "ORIGINAL_QUERY_COMMAND_SEQUENCE")
        if position == 0:
            require(Path(os.fsdecode(raw.rstrip(b"\r\n"))) == ROOT, "ORIGINAL_QUERY_ROOT")
        elif position in (2, 4, 5, 7, 8, 14):
            expected = {2: merge, 4: source["source"]["tree"], 5: source["reviewed"]["tree"],
                7: S.BASE["commit"], 8: S.BASE["tree"], 14: prior["tree"]}[position]
            acquisition._line(raw, expected, "ORIGINAL_QUERY_SOURCE")
        elif position == 3:
            require(raw in (b"false\n", b"false\r\n"), "ORIGINAL_QUERY_FULL_HISTORY")
        elif position == 6:
            expected = (S.BASE["commit"] + " " + head).encode("ascii")
            require(raw in (expected + b"\n", expected + b"\r\n"), "ORIGINAL_QUERY_MERGE_PARENTS")
        elif position == 12:
            require(re.fullmatch(rb"[1-9][0-9]{0,5}\r?\n", raw) and int(raw) == len(policy), "ORIGINAL_QUERY_POLICY_SIZE")
        else:
            expected = {1: b"", 9: b"", 10: originals["ancestry_raw"], 11: entry, 13: policy,
                15: originals["prior_ancestry_raw"]}[position]
            require(raw == expected, "ORIGINAL_QUERY_OUTPUT")
    observation = I.parse(originals["observation"], SMALL_LIMIT)
    require(all(observation.get(name) == source[name] for name in source), "ORIGINAL_QUERY_OBSERVATION")


def _query_native_record(row, start_raw, baseline_raw, query_owner, inherited):
    """Strict supplied original native-query grammar, not an owner factory."""
    fields = "schema scope id job state home cwd argv stdoutLimit stderrLimit timeoutSeconds launchAttempted " \
        "scopeAttempted waitExitCode retirement result errors outputs"
    S.fields(row, fields + " ownedSurvivors ownership", "QUERY_RESULT_FIELDS")
    require(type(row["schema"]) is int and row["schema"] == 1 and row["scope"] == "NATIVE_OWNED_ORDINARY_GIT_QUERY" and
        all(row[name] == query_owner[name] for name in ("job", "state", "home")) and row["cwd"] == str(ROOT) and
        row["launchAttempted"] is row["scopeAttempted"] is True and type(row["waitExitCode"]) is int and
        row["waitExitCode"] == 0 and row["retirement"] == "KNOWN" and row["result"] == "READY_FOR_CALLER_SEAL" and
        row["errors"] == row["ownedSurvivors"] == [], "QUERY_NATIVE_IDENTITY")
    argv = row["argv"]
    require(type(argv) is list and all(type(arg) is str and 0 < len(arg) <= 8192 and "\0" not in arg for arg in argv) and
        argv[:7] == [query_owner["git"], "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false", "-C", str(ROOT)] and
        queries._allowed_suffix(tuple(argv[7:])) and type(row["stdoutLimit"]) is int and
        0 < row["stdoutLimit"] <= I.EVENT_LIMIT and type(row["stderrLimit"]) is int and row["stderrLimit"] == 4096 and
        type(row["timeoutSeconds"]) is int and row["timeoutSeconds"] == 15, "QUERY_NATIVE_COMMAND")
    start = S.fields(qualification.canonical(start_raw, SMALL_LIMIT), fields + " environment", "QUERY_START_FIELDS")
    changing = {"launchAttempted", "scopeAttempted", "waitExitCode", "retirement", "result", "outputs"}
    require(all(I.encoded({name: start[name]}) == I.encoded({name: row[name]}) for name in fields.split()
        if name not in changing) and start["launchAttempted"] is start["scopeAttempted"] is False and
        start["waitExitCode"] is None and start["retirement"] == "UNKNOWN" and start["result"] == "HOLD" and
        start["outputs"] == {}, "QUERY_ORIGINAL_START_CHANGED")
    expected = processes.ownership_environment({**queries._git_environment(), **inherited}, row["job"], row["id"],
        row["state"], row["home"], allow_new_context=True)
    require(start["environment"] == expected, "QUERY_CREDENTIAL_OR_DOMAIN_SUBSTITUTION")
    role = query_owner["nativeRole"]
    baseline = S.fields(qualification.canonical(baseline_raw, SMALL_LIMIT), "nativeRole baseline kernelJob", "QUERY_BASELINE_FIELDS")
    require(baseline["nativeRole"] == role and baseline["kernelJob"] is (role == "windows-x64"), "QUERY_BASELINE_ROLE")
    if role == "windows-x64":
        require(baseline["baseline"] is None, "QUERY_KERNEL_BASELINE")
    else:
        prior = baseline["baseline"]
        width = 4 if role.startswith("macos-") else 2
        require(type(prior) is list and all(type(item) is list and len(item) == width and
            all(type(part) is int and 0 <= part <= origin.clocks.UINT64 for part in item) and item[0] > 0
            for item in prior) and prior == sorted(prior) and len({tuple(item) for item in prior}) == len(prior) and
            (width != 4 or all(item[3] < 1_000_000 for item in prior)), "QUERY_POSIX_BASELINE")
    native = row["ownership"]
    kind = processes.WindowsScope if role == "windows-x64" else processes.LinuxScope if role == "linux-x64" else processes.DarwinScope
    require(type(native) is dict and native.get("backend") == kind.name and native.get("job") == row["job"] and
        native.get("invocation") == row["id"] and native.get("discoveryErrors") == [] and native.get("scope") ==
        ("kernel-job-no-breakaway-kill-on-close" if role == "windows-x64" else "controlled-marker-inheriting-descendants"),
        "QUERY_NATIVE_DOMAIN")
    launches, identities = native.get("launches"), native.get("startedIdentities")
    require(type(launches) is list and len(launches) == 1 and type(launches[0]) is dict and
        type(identities) is list and all(type(item) is dict for item in identities), "QUERY_NATIVE_LAUNCH")
    launch = launches[0]
    require(type(launch.get("pid")) is int and launch["pid"] > 0 and launch.get("created") is True and
        launch.get("requestedArgv") == launch.get("resolvedArgv") == argv and launch.get("cwd") == str(ROOT), "QUERY_NATIVE_ARGV")
    leaders = [item for item in identities if item.get("pid") == launch["pid"]]
    if role == "windows-x64":
        # Windows captures the actual creationFileTime before it resumes the
        # assigned job member. Its original identity is mandatory, not optional.
        require(len(leaders) == 1, "QUERY_NATIVE_LEADER")
        leader = leaders[0]
        require(launch.get("api") == "CreateProcessW" and launch.get("batch") is False and
            launch.get("applicationName") == argv[0] and launch.get("commandLine") == processes.subprocess.list2cmdline(argv) and
            launch.get("resumed") is launch.get("jobAssignedBeforeResume") is leader.get("jobAssignedBeforeResume") is True and
            type(leader.get("creationFileTime")) is int and leader["creationFileTime"] > 0 and
            launch.get("outputMode") == "caller-owned-native-files", "QUERY_NATIVE_WINDOWS")
        cleanup = launch.get("resourceCleanup")
        names = {"startup-attributes", "launch-handle-0", "launch-handle-1", "launch-handle-2", "primary-thread"}
        require(type(cleanup) is list and len(cleanup) == len(names) and all(type(item) is dict and
            set(item) == {"phase", "resource", "status"} and item["phase"] == "launch-temporary" and
            item["status"] == "RETIRED" and type(item["resource"]) is str for item in cleanup) and
            {item["resource"] for item in cleanup} == names, "QUERY_NATIVE_WINDOWS_TEMPORARIES")
    else:
        require(launch.get("api") == "subprocess.Popen" and launch.get("shell") is False and
            launch.get("executable") == argv[0] and launch.get("outputMode") == "caller-owned-files" and
            type(native.get("discoveryReconciliations")) is list, "QUERY_NATIVE_POSIX")
        # The maintained PosixScope explicitly permits a naturally short Git
        # leader to exit before its first lifetime census. That is NOT an
        # observed identity. Exact original spawn/Popen wait0, clean descendant
        # discovery, bounded scope retirement, query/session and enclosing
        # child-close originals remain mandatory. Do not invent a lifetime or
        # require the already-exited leader to be live for parser acceptance.
        require(len(leaders) <= 1, "QUERY_NATIVE_LEADER")
        fields = ("pid", "uniqueId", "startSeconds", "startMicroseconds") if role.startswith("macos-") else ("pid", "startTicks")
        lifetimes = []
        for observed in identities:
            lifetime = [_scalar(observed.get(name)) for name in fields]
            require(all(number > 0 for number in lifetime[:3 if len(fields) == 4 else 2]) and
                lifetime not in baseline["baseline"] and lifetime not in lifetimes and
                (len(fields) != 4 or lifetime[-1] < 1_000_000), "QUERY_NATIVE_LIFETIME")
            lifetimes.append(lifetime)
            if role.startswith("macos-"):
                _scalar(observed.get("pidVersion"))
        if role.startswith("macos-"):
            drains = native.get("drainReconciliations")
            require(all(type(item) is dict and item.get("outcome") in
                ("lifetime-ended", "nonrunning", "replaced", "unmarked", "owned") for item in native["discoveryReconciliations"]) and
                type(native.get("observationReconciliations")) is list and type(drains) is list and drains and
                all(type(item) is dict and item.get("outcome") == "retired" and "error" not in item and
                    type(item.get("signalReconciliations")) is list and all(type(part) is dict and part.get("outcome") in
                        ("absent", "nonrunning", "replaced", "signal-succeeded") for part in item["signalReconciliations"])
                    for item in drains), "QUERY_NATIVE_DARWIN_DRAIN")


def _read_query_pass(owner, private, name, expected_session, context):
    """Independent parent reads of the child's fixed native query captures."""
    directory = owner.directory(Path(private.path) / name)
    raw = owner.read(directory, "session-result.json")
    require(digest(raw) == expected_session, "ORIGINAL_QUERY_SESSION_HASH")
    session = S.fields(I.parse(raw, SMALL_LIMIT), "schema scope job queries result retirement firstError errors readbacks",
                       "QUERY_SESSION_FIELDS")
    require(session["schema"] == 1 and type(session["schema"]) is int and session["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
        session["result"] == "READY_FOR_CALLER_SEAL" and session["retirement"] == "KNOWN" and
        session["firstError"] is None and session["errors"] == [] and type(session["queries"]) is list and
        0 < len(session["queries"]) <= queries.MAX_QUERIES and re.fullmatch(r"[0-9a-f]{32}", session["job"]),
        "ORIGINAL_NATIVE_QUERY_SESSION")
    owner_raw = owner.read(directory, "owner.json")
    query_owner = S.fields(qualification.canonical(owner_raw, SMALL_LIMIT),
        "schema scope job state home root nativeRole git ancestorContext", "QUERY_OWNER_FIELDS")
    expected = processes.ownership_environment(context["inheritedContext"], context["job"], context["invocation"],
        context["session"], str(Path(context["session"]) / "control-home"), allow_new_context=True)
    inherited = {key: expected[key] for key in queries._CONTEXT}
    require(type(query_owner["schema"]) is int and query_owner["schema"] == 1 and
        query_owner["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and query_owner["job"] == session["job"] and
        query_owner["state"] == str(directory.path) and query_owner["home"] == str(Path(directory.path) / "query-home") and
        query_owner["root"] == str(ROOT) and query_owner["nativeRole"] == owner.fence.clock.role and
        query_owner["git"] == context["git"] and query_owner["ancestorContext"] == inherited, "ORIGINAL_QUERY_OWNER")
    invocations, outputs = set(), []
    for row in session["queries"]:
        require(type(row) is dict and row.get("scope") == "NATIVE_OWNED_ORDINARY_GIT_QUERY" and
            row.get("job") == session["job"] and row.get("result") == "READY_FOR_CALLER_SEAL" and
            row.get("retirement") == "KNOWN" and row.get("waitExitCode") == 0 and
            type(row.get("waitExitCode")) is int and row.get("launchAttempted") is row.get("scopeAttempted") is True and
            row.get("errors") == [] and row.get("ownedSurvivors") == [] and
            type(row.get("ownership")) is dict and row["ownership"].get("discoveryErrors") == [], "ORIGINAL_NATIVE_QUERY")
        identifier = row.get("id")
        require(type(identifier) is str and re.fullmatch(r"[0-9a-f]{32}", identifier) and identifier not in invocations,
                "QUERY_UNIQUE_INVOCATION")
        invocations.add(identifier)
        query = owner.acquire("query-readback-directory", lambda: directory.open_directory("query-" + identifier,
            deadline=owner.guard()))
        require(owner.read(query, "result.json") == I.encoded(row), "QUERY_ORIGINAL_RESULT_CHANGED")
        _query_native_record(row, owner.read(query, "start.json"), owner.read(query, "baseline.json"), query_owner, inherited)
        require(type(row["outputs"]) is dict and set(row["outputs"]) == {"stdout", "stderr"}, "QUERY_ORIGINAL_CAPTURES")
        for label in ("stdout", "stderr"):
            output = owner.read(query, label + ".log", row[label + "Limit"])
            actual = I.parse(owner.reads[-1][3], SMALL_LIMIT)
            expected = actual if owner.fence.clock.role == "windows-x64" else {
                "device": actual["identity"][0], "inode": actual["identity"][1], "size": actual["size"],
                "mtime_ns": actual["mtime_ns"], "ctime_ns": actual["ctime_ns"]}
            require(row["outputs"][label] == {**expected, "bytes": len(output), "sha256": digest(output)} and
                (label != "stderr" or output == b""), "QUERY_ORIGINAL_CAPTURE")
            if label == "stdout":
                outputs.append(output)
        owner.close_one(query)
    originals = {name: owner.read(directory, name + ".bin") for name in CURRENT_KEYS}
    owner.close_one(directory)
    return originals, session["queries"], outputs, raw


def _current_bodies(originals, context, invocation, fence):
    github = context["github"]
    base = qualification.API + "/actions/runs/" + github["runId"]
    attempt = base + "/attempts/" + github["runAttempt"]
    environment = qualification.API + "/environments/" + S.ENVIRONMENT
    paths = {"attempt": attempt, "jobs": attempt + "/jobs?per_page=100&page=1", "approvals": base + "/approvals",
        "environment": environment, "branches": environment + "/deployment-branch-policies?per_page=100&page=1",
        "main": qualification.API + "/git/ref/heads/main", "reviewed_ref": qualification.API +
        "/git/ref/heads/" + S.SOURCE_REF.removeprefix("refs/heads/"), "pull_request": qualification.API +
        "/pulls/" + str(context["pullRequestNumber"])}
    result, dates = {}, {}
    first_start = previous_end = first_date = previous_date = None
    for name in HTTP_KEYS:
        if name == "comment":
            selected = acquisition.gate.select(stage="stage2", run_id=github["runId"], attempt=github["runAttempt"],
                approvals_raw=result["approvals"])
            selection = I.parse(selected.record, SMALL_LIMIT)
            paths[name] = qualification.API + "/issues/comments/" + str(selection["commentId"])
        response, body, date = origin.response_bytes(originals[name], paths[name], invocation, fence.clock)
        require(response["finishedNs"] < fence.work and I.parse(fence.raw, SMALL_LIMIT)["firstNs"] <= response["startedNs"],
                "CURRENT_ORIGINAL_INTERVAL")
        _status, headers = origin.wire.headers(qualification.original_bytes(response["headersBase64"], origin.wire.HEADER_LIMIT))
        require("link" not in headers, "CURRENT_INCOMPLETE_METADATA_RESPONSE")
        if first_start is None:
            first_start, first_date = response["startedNs"], date
        require((previous_end is None or previous_end <= response["startedNs"]) and
            response["finishedNs"] < first_start + origin.wire.ACQUIRE_SECONDS * NS and
            (previous_date is None or previous_date <= date) and
            0 <= date - first_date <= math.ceil((response["finishedNs"] - first_start) / NS) +
                origin.wire.CACHE_SECONDS + 1, "CURRENT_ORIGINAL_CHRONOLOGY")
        previous_end, previous_date = response["finishedNs"], date
        result[name], dates[name] = body, date
    acquisition._run(context, I.parse(result["attempt"], SMALL_LIMIT), I.parse(result["jobs"], SMALL_LIMIT), dates["jobs"])
    selection = I.parse(acquisition.gate.select(stage="stage2", run_id=github["runId"], attempt=github["runAttempt"],
        approvals_raw=result["approvals"]).record, SMALL_LIMIT)
    declaration, authority, authority_at = S.statement(S.STAGE2, result["comment"], selection["commentId"], selection["bodySha256"])
    acquisition.gate.check_environment(declaration["environment"], result["environment"], result["branches"])
    for label, branch, commit in (("main", "main", S.BASE["commit"]),
        ("reviewed_ref", S.SOURCE_REF.removeprefix("refs/heads/"), context["reviewedCommit"])):
        acquisition._ref(I.parse(result[label], SMALL_LIMIT), branch, commit)
    S.joint._current_pr(I.parse(result["pull_request"], SMALL_LIMIT), declaration, declaration["firstPullRequest"])
    return result, declaration, authority, authority_at


def _packet_interval(raw, packet, invocation, window):
    """Original whole-packet45 interval, not a newly granted parent deadline."""
    _checked_window(window)
    value = S.fields(qualification.canonical(raw, SMALL_LIMIT), "schema scope invocation clock firstNs workEndNs "
        "completedNs packet source selection archive", "PACKET_ACQUISITION_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] ==
        "INITIAL_ORDINARY_ORIGINAL_PACKET_ACQUISITION_V1" and value["invocation"] == invocation and
        value["clock"] == window["clock"] and I.encoded(value["packet"]) == I.encoded(packet) and
        value["archive"] in ("ORIGINAL_DOWNLOAD", "ORIGINAL_RETAINED_BYTES"), "PACKET_ACQUISITION_ORIGINAL")
    first, completed, end = (_scalar(value[name]) for name in ("firstNs", "completedNs", "workEndNs"))
    require(window["firstNs"] <= first <= completed < end == min(window["workEndNs"],
        first + origin.wire.ACQUIRE_SECONDS * NS), "PACKET_ACQUISITION_INTERVAL")
    S.joint.source(value["source"])
    S.bootstrap.selection(value["selection"])
    return value


class _PacketAudit:
    """Compare retained ORIGINAL responses in their actual request order."""

    def __init__(self, interval):
        self.interval, self.last_end, self.first_date, self.last_date = interval, None, None, None

    def accept(self, response, date):
        begin, end = _scalar(response["startedNs"]), _scalar(response["finishedNs"])
        require(type(date) is int and self.interval["firstNs"] <= begin <= end <= self.interval["completedNs"] and
            (self.last_end is None or self.last_end <= begin), "PACKET_ORIGINAL_HTTP_CHRONOLOGY")
        if self.first_date is None:
            self.first_date = date
        require((self.last_date is None or self.last_date <= date) and
            0 <= date - self.first_date <= math.ceil((end - self.interval["firstNs"]) / NS) +
                origin.wire.CACHE_SECONDS + 1, "PACKET_ORIGINAL_SERVICE_DATE_DRIFT")
        self.last_end, self.last_date = end, date


def _retained_page(owner, directory, name, path, invocation, fence, *, pagination=None, packet_audit=None):
    raw = owner.read(directory, name + ".json")
    response, body, date = origin.response_bytes(raw, path, invocation, fence.clock)
    require(I.parse(fence.raw, SMALL_LIMIT)["firstNs"] <= response["startedNs"] <= response["finishedNs"] < fence.work,
            "RETAINED_CURRENT_HTTP_INTERVAL")
    _status, headers = origin.wire.headers(qualification.original_bytes(response["headersBase64"], origin.wire.HEADER_LIMIT))
    if pagination is None:
        require("link" not in headers, "RETAINED_INCOMPLETE_METADATA_RESPONSE")
    else:
        number, paths = pagination
        _page_links(headers, number, I.parse(body, qualification.references.PAGE_LIMIT).get("total_count"), paths)
    if packet_audit is not None:
        packet_audit.accept(response, date)
    return body, date


def _retained_pages(owner, directory, name, path, key, invocation, fence, *, packet_audit):
    first, _date = _retained_page(owner, directory, name + "-1", path(1), invocation, fence,
        pagination=(1, path), packet_audit=packet_audit)
    value = I.parse(first, SMALL_LIMIT)
    total = value.get("total_count")
    require(type(total) is int and 0 <= total <= 1000 and type(value.get(key)) is list, "RETAINED_PAGE_TOTAL")
    result = [(path(1), first)]
    for number in range(2, max(1, (total + 99) // 100) + 1):
        raw, _date = _retained_page(owner, directory, name + "-" + str(number), path(number), invocation, fence,
                                   pagination=(number, path), packet_audit=packet_audit)
        result.append((path(number), raw))
    return tuple(result)


def _read_packet(owner, private, number, entry, declaration, authority_at, current_inputs, invocation, retained,
                 archive_origin):
    directory = owner.directory(Path(private.path) / ("packet-" + str(number)))
    acquisition_raw = owner.read(directory, "packet-acquisition.json")
    interval = _packet_interval(acquisition_raw, entry["packet"], invocation, I.parse(owner.fence.raw, SMALL_LIMIT))
    require(interval["source"] == declaration["stage1"]["reviewed"] and interval["selection"] == entry["selection"] and
        (interval["archive"] == "ORIGINAL_DOWNLOAD") == (archive_origin[0] == invocation), "PACKET_ORIGINAL_SOURCE")
    audit = _PacketAudit(interval)

    def page(name, path):
        return _retained_page(owner, directory, name, path, invocation, owner.fence, packet_audit=audit)

    originals = {name: page(name, qualification.references.metadata_path(entry[name]))[0]
        for name in ("inventory", "compatibility", "review")}
    inventory, compatible, _review, _bodies = qualification.public_metadata(originals, entry, declaration, authority_at)
    require(I.encoded(retained["packet"]) == I.encoded(entry["packet"]) and
        I.encoded(retained["members"]) == I.encoded(inventory["members"]), "PARENT_PACKET_REFERENCE")
    base = qualification.API + "/actions/runs/" + entry["runId"] + "/attempts/" + entry["runAttempt"]
    attempt, _date = page("attempt", base)
    jobs, _date = page("jobs", base + "/jobs?per_page=100&page=1")
    selected = qualification.completed_job(attempt, jobs, entry, declaration["stage1"]["reviewed"])
    job_raw, job_date = page("job", qualification.API + "/actions/jobs/" + str(selected["id"]))
    artifact, _date = page("artifact", qualification.API + "/actions/artifacts/" + str(entry["packet"]["artifactId"]))
    pages = _retained_pages(owner, directory, "artifacts", lambda page:
        qualification.references.inventory_path(entry["runId"], page), "artifacts", invocation, owner.fence, packet_audit=audit)
    cache_pages = _retained_pages(owner, directory, "caches", lambda page:
        qualification.cache_inventory_path(compatible["provider"], page), "actions_caches", invocation, owner.fence,
        packet_audit=audit)
    packet_directory = directory if str(directory.path) == retained["path"] else owner.directory(Path(retained["path"]))
    manifests, read = _packet_read(owner, packet_directory, inventory["members"], entry["packet"])
    result = qualification.qualify(originals=originals, entry=entry, declaration=declaration, authority_created_at=authority_at,
        attempt_raw=attempt, jobs_raw=jobs, job_raw=job_raw, job_date=job_date, artifact_raw=artifact, inventory_pages=pages,
        cache_pages=cache_pages, manifests=manifests, current_inputs=current_inputs, now=int(time.time()))
    require(owner.read(directory, "qualification.json") == result.record, "ORIGINAL_QUALIFICATION_CHANGED")
    child_read = S.fields(qualification.canonical(owner.read(directory, "packet-read.json"), SMALL_LIMIT),
        "name bytes sha256 native retirement readAtNs", "ORIGINAL_PACKET_READ_FIELDS")
    require(child_read["name"] == read["name"] and child_read["bytes"] == read["bytes"] and
        child_read["sha256"] == read["sha256"] and child_read["native"] == read["native"] and
        child_read["retirement"] == "KNOWN" and interval["firstNs"] <= _scalar(child_read["readAtNs"]) <=
        interval["completedNs"] < read["readAtNs"], "ORIGINAL_PACKET_READ_CHANGED")
    archives = _retained_archive(owner, packet_directory, entry["packet"], *archive_origin,
        packet_audit=audit if archive_origin[0] == invocation else None)
    if packet_directory is not directory:
        owner.close_one(packet_directory)
    owner.close_one(directory)
    return result, archives


def _retained_archive(owner, directory, packet, invocation, window_raw, *, packet_audit=None):
    """Retain the real earlier download, never relabel a reused file as a GET."""
    window = qualification.canonical(window_raw, SMALL_LIMIT)
    _checked_window(window)
    acquisition_raw = owner.read(directory, "packet-acquisition.json")
    interval = _packet_interval(acquisition_raw, packet, invocation, window)
    require(interval["archive"] == "ORIGINAL_DOWNLOAD", "ARCHIVE_NOT_ORIGINAL_DOWNLOAD")
    if packet_audit is None:
        packet_audit = _PacketAudit(interval)
    else:
        require(packet_audit.interval == interval, "ORIGINAL_ARCHIVE_PACKET_INTERVAL")
    original_path = qualification.API + "/actions/artifacts/" + str(packet["artifactId"]) + "/zip"
    result, previous_end, location = [acquisition_raw], None, None
    for name, status, count, checksum in (("archive-redirect", 302, 0, digest(b"")),
            ("archive-download", 200, packet["bytes"], packet["sha256"])):
        raw = owner.read(directory, name + ".json")
        value = S.fields(qualification.canonical(raw, SMALL_LIMIT), "schema scope host path invocation clock startedNs "
            "finishedNs status headersBase64 bodyBytes bodySha256 complete retirement error", "ARCHIVE_RETURN_FIELDS")
        require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] ==
            "PRIVATE_INITIAL_ORDINARY_ARCHIVE_RESPONSE_V1" and value["invocation"] == invocation and
            value["clock"] == window["clock"] and type(value["status"]) is int and value["status"] == status and
            value["complete"] is True and value["retirement"] == "KNOWN" and value["error"] is None and
            type(value["bodyBytes"]) is int and value["bodyBytes"] == count and value["bodySha256"] == checksum,
            "ARCHIVE_ORIGINAL_RETURN")
        begin, end = _scalar(value["startedNs"]), _scalar(value["finishedNs"])
        require(window["firstNs"] <= begin <= end < min(window["workEndNs"], begin + origin.wire.REQUEST_SECONDS * NS) and
            (previous_end is None or previous_end <= begin), "ARCHIVE_ORIGINAL_TIMING")
        previous_end = end
        header = qualification.original_bytes(value["headersBase64"], origin.wire.HEADER_LIMIT)
        fields, date = _archive_headers(header, status, count)
        packet_audit.accept(value, date)
        if status == 302:
            require(value["host"] == origin.wire.HOST and value["path"] == original_path, "ORIGINAL_ARCHIVE_SELECTOR")
            location = fields.get("location")
            _storage_location(location)
        else:
            require((value["host"], value["path"]) == _storage_location(location) and "location" not in fields,
                    "ORIGINAL_STORAGE_WITHOUT_REDIRECT")
        result.append(raw)
    return tuple(result)


@dataclass(frozen=True, eq=False, repr=False)
class InitialOrdinaryCurrent:
    """Opaque original parent return. Direct construction grants nothing."""


@dataclass(frozen=True, eq=False, repr=False)
class _CurrentState:
    handle: InitialOrdinaryCurrent = field(repr=False)
    owner: _Owner = field(repr=False)
    closed: _ClosedOwner = field(repr=False)
    native: _NativeReturn = field(repr=False)
    context_raw: bytes = field(repr=False)
    record_raw: bytes = field(repr=False)
    match: object = field(repr=False)
    identity: object = field(repr=False)
    qualifications: tuple = field(repr=False)
    packets_raw: bytes = field(repr=False)
    archive_origins: tuple = field(repr=False)
    archive_raws: tuple = field(repr=False)
    first_originals: tuple = field(repr=False)
    first_session_raw: bytes = field(repr=False)
    child_raw: bytes = field(repr=False)
    token: str = field(repr=False)
    previous: object = field(repr=False)
    lineage: object = field(repr=False)


@dataclass(frozen=True, repr=False)
class CurrentBudgetOriginals:
    """Retained DATA from one checked current, not a transferable capability."""
    current_raw: bytes
    context_raw: bytes
    identity_raw: bytes
    attempt_raw: bytes
    jobs_raw: bytes
    first_session_raw: bytes
    child_raw: bytes
    child_ack_raw: bytes
    native_start_raw: bytes
    native_return_raw: bytes
    owner_close_raw: bytes


def _history(current):
    saved = _RETURNS.get(id(current))
    require(type(current) is InitialOrdinaryCurrent and saved is not None and saved[0].handle is current,
            "ORIGINAL_CURRENT_RETURN_REQUIRED")
    state, frozen = saved
    require(type(state) is _CurrentState and all(getattr(state, name) is value for name, value in
        zip(state.__dataclass_fields__, frozen)), "ORIGINAL_CURRENT_STATE_CHANGED")
    require(state.lineage.get("failed") is False, "ORIGINAL_LINEAGE_FAILED")
    require(_checked_close(state.closed) is state.owner and _checked_native(state.native, state.owner) is state.native,
            "CURRENT_ORIGINAL_CLOSE_CHANGED")
    value, context = I.parse(state.record_raw, SMALL_LIMIT), I.parse(state.context_raw, SMALL_LIMIT)
    require(value["scope"] == RETURN_SCOPE and value["matchSha256"] == digest(state.match.record) and
        value["contextSha256"] == digest(state.context_raw) and
        value["ownerCloseSha256"] == digest(state.closed.raw) and
        value["nativeReturnSha256"] == digest(state.native.result_raw) and
        value["qualifications"] == [digest(item.record) for item in state.qualifications] and
        len(state.qualifications) == 4 and all(type(item) is qualification.ProductiveQualification for item in
            state.qualifications) and type(state.packets_raw) is bytes and type(state.first_originals) is tuple and
        tuple(name for name, _raw in state.first_originals) == CURRENT_KEYS and
        all(type(raw) is bytes for _name, raw in state.first_originals) and
        type(state.first_session_raw) is bytes and type(state.child_raw) is bytes and
        I.parse(state.child_raw, SMALL_LIMIT)["firstSessionSha256"] == digest(state.first_session_raw) and
        I.parse(state.native.stdout_raw, 16384)["terminalSha256"] == digest(state.child_raw), "CURRENT_BOUND_ORIGINALS")
    require(type(state.match) is (acquisition.gate.GateEligibility if context["observed"]["kind"] == "gate" else
            S.OrdinaryMatch), "CURRENT_MATCH_TYPE")
    if context["observed"]["kind"] == "worker":
        require(type(state.identity) is identity.InitialOrdinaryIdentity and
            digest(state.identity.record) == value["identitySha256"] and
            identity.cache_cohort(state.identity.record) ==
                (context["observed"]["profile"], context["observed"]["role"]), "CURRENT_IDENTITY_ONLY")
    else:
        require(state.identity is None and value["identitySha256"] is None, "GATE_HAS_NO_WORKER_IDENTITY")
    if state.previous is not None:
        older = _history(state.previous)
        require(older.lineage is state.lineage and state.archive_origins is older.archive_origins and
            state.archive_raws == older.archive_raws and state.packets_raw == older.packets_raw,
            "ORIGINAL_PACKET_LINEAGE_CHANGED")
    return state


def checked_initial_ordinary(current):
    """Active current-source check only; no provider/crypto/worker admission."""
    state = _history(current)
    try:
        require(state.lineage.get("latest") is current, "CURRENT_RETURN_REPLACED")
        context = I.parse(state.context_raw, SMALL_LIMIT)
        observed, event = _actual_context(context["observed"]["kind"], context["observed"]["firstUseAt"])
        require(I.encoded(observed) == I.encoded(context["observed"]) and digest(event) == context["eventSha256"] and
            origin.wire.TOKEN_ENV not in os.environ and _installed_git() == context["git"], "CURRENT_HOST_CONTEXT_CHANGED")
        state.owner.fence.now()
        require(int(time.time()) < I.parse(state.match.record, SMALL_LIMIT)["expiresAt"] and
            all(int(time.time()) < I.parse(item.record, SMALL_LIMIT)["expiresAt"] for item in state.qualifications),
            "CURRENT_POLICY_OR_PACKET_EXPIRED")
        return current
    except BaseException as error:
        state.lineage.update(failed=True, original=error)
        raise


def initial_ordinary_identity(current):
    state = _history(checked_initial_ordinary(current))
    require(state.identity is not None, "WORKER_IDENTITY_REQUIRED")
    return state.identity


def initial_ordinary_eligibility(current):
    state = _history(checked_initial_ordinary(current))
    require(type(state.match) is acquisition.gate.GateEligibility, "GATE_ELIGIBILITY_REQUIRED")
    return state.match


def initial_ordinary_qualification_records(current):
    state = _history(checked_initial_ordinary(current))
    return tuple(item.record for item in state.qualifications)


def initial_ordinary_record(current):
    return _history(checked_initial_ordinary(current)).record_raw


def initial_ordinary_budget_originals(current):
    """Use actual retained bytes, without reading through an already closed owner.

    Budget origin is the FIRST pre-tool source acquisition only. A refreshed or
    cross-step current cannot renew the original service time by this accessor.
    DATA access precedes the single provider claim; it is not another claim.
    """
    state = _history(checked_initial_ordinary(current))
    context = I.parse(state.context_raw, SMALL_LIMIT)
    require(state.identity is not None and state.previous is None and context["previous"] is None and
            id(current) not in state.lineage["claims"], "BUDGET_FIRST_CURRENT_ONLY")
    originals = dict(state.first_originals)
    return CurrentBudgetOriginals(state.record_raw, state.context_raw, state.identity.record,
        originals["attempt"], originals["jobs"], state.first_session_raw, state.child_raw, state.native.stdout_raw, state.native.start_raw,
        state.native.result_raw, state.closed.raw)


def initial_ordinary_retained_data(current):
    """Fixed DATA set for a later real process; no token or native owner export.

    The session writer owns the copy/readback/known close. These bytes alone
    cannot satisfy a current check. Reacquisition always uses a fresh native
    owner, authenticated metadata and complete rereads of all four original ZIPs.
    """
    state = _history(checked_initial_ordinary(current))
    require(state.identity is not None, "RETAINED_WORKER_ONLY")
    context = I.parse(state.context_raw, SMALL_LIMIT)
    value = I.parse(state.identity.record, SMALL_LIMIT)
    data = {
        "current.json": state.record_raw, "context.json": state.context_raw,
        "match.json": state.match.record, "identity.json": state.identity.record,
        "original-event.json": state.identity.original_event, "original-policy.json": state.identity.original_policy,
        "recipient-public.asc": state.identity.public_key, "owner-close.json": state.closed.raw,
        "native-start.json": state.native.start_raw, "native-return.json": state.native.result_raw,
        "first-session.json": state.first_session_raw,
        "child-result.json": state.child_raw, "child-ack.bin": state.native.stdout_raw,
        "attempt.bin": dict(state.first_originals)["attempt"], "jobs.bin": dict(state.first_originals)["jobs"],
    }
    history = {"schema": 1, "scope": HISTORY_SCOPE, "source": value["source"], "github": value["github"],
        "firstUseAt": context["observed"]["firstUseAt"], "bootDigest": context["bootDigest"],
        "identitySha256": digest(state.identity.record), "matchSha256": digest(state.match.record),
        "policySha256": digest(state.identity.original_policy), "packets": I.parse(state.packets_raw, SMALL_LIMIT)["packets"],
        "archiveOrigins": [{"invocation": invocation, "window": I.parse(raw, SMALL_LIMIT)}
                           for invocation, raw in state.archive_origins],
        "originalCurrentSha256": digest(state.record_raw), "originalContextSha256": digest(state.context_raw),
        "originalCloseSha256": digest(state.closed.raw), "originalNativeReturnSha256": digest(state.native.result_raw)}
    data["initial-current-history.json"] = I.encoded(history)
    for number, (qualified, archive) in enumerate(zip(state.qualifications, state.archive_raws), 1):
        data["qualification-" + str(number) + ".json"] = qualified.record
        for label, raw in zip(("acquisition", "redirect", "download"), archive):
            data["archive-" + str(number) + "-" + label + ".json"] = raw
    require(all(type(raw) is bytes and len(raw) <= SMALL_LIMIT for raw in data.values()) and
            sum(map(len, data.values())) <= CONTROL_LIMIT, "RETAINED_DATA_BOUNDS")
    return tuple(data.items())


def _retained_packet_data(data, expected_sha256):
    """Strict historical DATA checks only; never register any saved live object."""
    fixed = {"initial-current-history.json", "current.json", "context.json", "match.json", "identity.json",
        "original-event.json", "original-policy.json", "recipient-public.asc", "owner-close.json",
        "native-start.json", "native-return.json", "first-session.json", "attempt.bin", "jobs.bin",
        "child-result.json", "child-ack.bin"}
    fixed.update("qualification-" + str(n) + ".json" for n in range(1, 5))
    fixed.update("archive-" + str(n) + "-" + name + ".json" for n in range(1, 5)
                 for name in ("acquisition", "redirect", "download"))
    require(type(data) is dict and set(data) == fixed and all(type(raw) is bytes and len(raw) <= SMALL_LIMIT
            for raw in data.values()) and sum(map(len, data.values())) <= CONTROL_LIMIT, "RETAINED_FIXED_DATA")
    S.digest(expected_sha256)
    require(digest(data["initial-current-history.json"]) == expected_sha256, "RETAINED_HISTORY_OUTPUT_HASH")
    history = S.fields(qualification.canonical(data["initial-current-history.json"], SMALL_LIMIT),
        "schema scope source github firstUseAt bootDigest identitySha256 matchSha256 policySha256 packets archiveOrigins "
        "originalCurrentSha256 originalContextSha256 originalCloseSha256 originalNativeReturnSha256", "RETAINED_HISTORY_FIELDS")
    require(type(history["schema"]) is int and history["schema"] == 1 and history["scope"] == HISTORY_SCOPE,
            "RETAINED_HISTORY_SCOPE")
    for name, filename in (("identitySha256", "identity.json"), ("matchSha256", "match.json"),
            ("policySha256", "original-policy.json"), ("originalCurrentSha256", "current.json"),
            ("originalContextSha256", "context.json"), ("originalCloseSha256", "owner-close.json"),
            ("originalNativeReturnSha256", "native-return.json")):
        require(history[name] == digest(data[filename]), "RETAINED_ORIGINAL_HASH")
    bound = identity.retained_identity(data["identity.json"], data["original-event.json"],
        data["original-policy.json"], data["recipient-public.asc"], now=int(time.time()))
    value, match = I.parse(bound.record, SMALL_LIMIT), qualification.canonical(data["match.json"], SMALL_LIMIT)
    context = qualification.canonical(data["context.json"], SMALL_LIMIT)
    require(match == value["initialRecipient"] and history["source"] == value["source"] and
            history["github"] == value["github"] and type(history["firstUseAt"]) is int and
            history["firstUseAt"] == match["firstUseAt"] == context["observed"]["firstUseAt"] and
            context["observed"]["kind"] == "worker" and history["bootDigest"] == context["bootDigest"] and
            context["eventSha256"] == digest(bound.original_event), "RETAINED_IDENTITY")
    _context_bytes(data["context.json"], "worker", context["invocation"], context["window"], history["bootDigest"])
    packets = _previous_paths(history["packets"], "worker")
    require(type(history["archiveOrigins"]) is list and len(history["archiveOrigins"]) == 4,
            "RETAINED_ARCHIVE_ORIGINS")
    origins, archives = [], []
    for number, (entry, packet, origin_data) in enumerate(zip(match["qualifications"], packets,
            history["archiveOrigins"]), 1):
        S.fields(origin_data, "invocation window", "RETAINED_ARCHIVE_ORIGIN_FIELDS")
        invocation, window = origin_data["invocation"], origin_data["window"]
        require(type(invocation) is str and re.fullmatch(r"[0-9a-f]{32}", invocation) and
                _checked_window(window).role == context["observed"]["role"] and
                packet["packet"] == entry["packet"] and Path(packet["path"]).parent == _location("worker", invocation),
                "RETAINED_ARCHIVE_ORIGIN")
        origins.append((invocation, I.encoded(window)))
        archives.append(tuple(data["archive-" + str(number) + "-" + name + ".json"]
                              for name in ("acquisition", "redirect", "download")))
    current = identity.retained_current(data["current.json"], bound, context["observed"]["role"])
    require(type(current["schema"]) is int and current["schema"] == 1 and current["scope"] == RETURN_SCOPE and
            current["contextSha256"] == history["originalContextSha256"] and current["source"] == value["source"] and
            current["reviewed"] == match["reviewed"] and current["kind"] == "worker" and
            current["profile"] == value["profile"] and current["role"] == context["observed"]["role"] and
            current["matchSha256"] == history["matchSha256"] and current["identitySha256"] == history["identitySha256"] and
            current["ownerCloseSha256"] == history["originalCloseSha256"] and
            current["nativeReturnSha256"] == history["originalNativeReturnSha256"] and current["qualifications"] ==
            [digest(data["qualification-" + str(n) + ".json"]) for n in range(1, 5)] and
            all(current[name] == "NOT_PERFORMED" for name in ("ordinaryAcceptance", "h2ProviderAcceptance", "cryptoAcceptance")) and
            current["budgetAcceptance"] == "NOT_ADMITTED" and current["publicationAuthority"] is False,
            "RETAINED_CURRENT_BINDING")
    closed = S.fields(qualification.canonical(data["owner-close.json"], SMALL_LIMIT),
        "schema scope resources readers writers closedNs retirement errors", "RETAINED_CLOSE_FIELDS")
    native = qualification.canonical(data["native-return.json"], SMALL_LIMIT)
    start = qualification.canonical(data["native-start.json"], SMALL_LIMIT)
    child = qualification.canonical(data["child-result.json"], SMALL_LIMIT)
    ack = qualification.canonical(data["child-ack.bin"], 16384)
    require(type(closed["schema"]) is int and closed["schema"] == 1 and closed["scope"] ==
        "INITIAL_ORDINARY_ACTUAL_OWNER_CLOSE_V1" and closed["retirement"] == "KNOWN" and closed["errors"] == [] and
        all(type(closed[name]) is int and 0 < closed[name] <= FILE_COUNT for name in ("resources", "readers", "writers")) and
        native["scope"] == "INITIAL_ORDINARY_NATIVE_CHILD_RETURN_PENDING_OWNER_CLOSE_V1" and
        native["startSha256"] == digest(data["native-start.json"]) and native["invocation"] == context["invocation"] and
        native["launchAttempted"] is native["scopeAttempted"] is True and type(native["exitCode"]) is int and
        native["exitCode"] == 0 and native["retirement"] == "KNOWN" and native["errors"] == [] and
        native["ownedSurvivors"] == [] and start["contextSha256"] == history["originalContextSha256"] and
        native["captures"]["stdout"]["sha256"] == digest(data["child-ack.bin"]) and
        ack["scope"] == ACK_SCOPE and ack["terminalSha256"] == digest(data["child-result.json"]) and
        child["scope"] == CHILD_SCOPE and child["contextSha256"] == history["originalContextSha256"] and
        child["firstSessionSha256"] == digest(data["first-session.json"]) and
        context["window"]["firstNs"] <= _scalar(start["startedNs"]) <= _scalar(native["completedNs"]) <=
        _scalar(closed["closedNs"]) < context["window"]["finalEndNs"], "RETAINED_CLOSED_DATA")
    return history, context, bound, tuple(origins), tuple(archives)


def claim_initial_ordinary(current, purpose):
    """One current source use, not a product/provider/publication permission."""
    state = _history(checked_initial_ordinary(current))
    try:
        require(type(purpose) is str and purpose in PURPOSES and id(current) not in state.lineage["claims"],
                "CURRENT_USE_ONCE")
        kind = I.parse(state.context_raw, SMALL_LIMIT)["observed"]["kind"]
        require((purpose == "gate") == (kind == "gate"), "GATE_CANNOT_CLAIM_WORKER_USE")
        state.lineage["claims"][id(current)] = purpose
        return current
    except BaseException as error:
        state.lineage.update(failed=True, original=error)
        raise


def _new_current(kind, cancelled, original_work_end_ns, original_final_end_ns, *, prior=None,
                 retained=None, retained_sha256=None):
    """Actual current owner. The optional prior is a registered SAME-process return."""
    require(callable(cancelled) and kind in ("gate", "worker") and not _QUARANTINE and not queries.QUARANTINE and
        not continuity.QUARANTINE, "ACTUAL_ENTRY_ARGUMENTS_OR_QUARANTINE")
    first_local, first = time.monotonic(), origin.clocks.observe()
    work, final = min(_scalar(original_work_end_ns), first.nanoseconds + SOURCE_SECONDS * NS), min(
        _scalar(original_final_end_ns), first.nanoseconds + FINAL_SECONDS * NS)
    window = _window(first, work, final)
    fence = _Fence(window, first, first_local, cancelled)
    require(prior is None or retained is None, "ONE_PRIOR_OR_RETAINED_SOURCE")
    require((retained is None) == (retained_sha256 is None), "RETAINED_HASH_REQUIRED")
    older = None if prior is None else _history(prior)
    retained_history = retained_context = retained_identity = retained_origins = retained_archives = None
    if older is None:
        token = os.environ.pop(origin.wire.TOKEN_ENV, None)
        if retained is not None:
            require(kind == "worker", "RETAINED_WORKER_ONLY")
            retained_history, retained_context, retained_identity, retained_origins, retained_archives = (
                _retained_packet_data(retained, retained_sha256))
        observed, event = _actual_context(kind, int(time.time()) if retained_history is None else retained_history["firstUseAt"])
        require(retained_context is None or observed == retained_context["observed"] and
                event == retained_identity.original_event, "RETAINED_HOST_CONTEXT_CHANGED")
        key = (observed["github"]["runId"], observed["github"]["runAttempt"], observed["github"]["job"], observed["role"])
        require(key not in _ATTEMPTS, "ORIGINAL_ENTRY_ALREADY_ATTEMPTED")
        lineage = {"failed": False, "original": None, "latest": None, "claims": {}}
        _ATTEMPTS[key] = lineage
    else:
        lineage, token = older.lineage, older.token
        require(lineage.get("latest") is prior and id(prior) in lineage["claims"] and
            origin.wire.TOKEN_ENV not in os.environ, "REFRESH_ORIGINAL_CLAIM")
        previous_context = I.parse(older.context_raw, SMALL_LIMIT)
        observed, event = _actual_context(kind, previous_context["observed"]["firstUseAt"])
        require(observed == previous_context["observed"] and digest(event) == previous_context["eventSha256"],
                "REFRESH_IDENTITY_CHANGED")
    owner = None
    try:
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "ORIGINAL_READ_TOKEN")
        require(first.clock.role == observed["role"], "ACTUAL_NATIVE_ROLE")
        boot = continuity.boot_digest(first.clock.role)
        if older is not None:
            require(boot == I.parse(older.context_raw, SMALL_LIMIT)["bootDigest"], "ORIGINAL_BOOT_CHANGED")
        elif retained_history is not None:
            require(boot == retained_history["bootDigest"], "RETAINED_BOOT_CHANGED")
        invocation, job = uuid.uuid4().hex, uuid.uuid4().hex
        path = _location(kind, invocation)
        owner = _Owner(_OWNER_KEY, fence)
        private = owner.directory(path, create=True)
        for name in ("control-home", "temporary"):
            owner.acquire("control-directory", lambda: private.create_directory(name, deadline=owner.guard()))
        context_raw = owner.write(private, "context.json", {"schema": 1, "scope": CONTEXT_SCOPE,
            "root": str(ROOT), "session": str(path), "job": job, "invocation": invocation, "observed": observed,
            "eventSha256": digest(event), "window": window, "bootDigest": boot,
            "inheritedContext": queries._inherited_context(), "git": _installed_git(),
            "previous": (retained_history["packets"] if retained_history is not None else
                         None if older is None else I.parse(older.packets_raw, SMALL_LIMIT)["packets"]),
            "expectedMatch": (I.parse(retained["match.json"], SMALL_LIMIT) if retained is not None else
                              None if older is None else I.parse(older.match.record, SMALL_LIMIT))})
        native = _launch(owner, private, context_raw, token)
        _checked_native(native, owner)
        service = owner.directory(path / "service")
        child_raw = owner.read(service, "child-result.json")
        child = S.fields(qualification.canonical(child_raw, SMALL_LIMIT), "schema scope contextSha256 startSha256 invocation "
            "clock bootDigest startedNs completedNs firstSessionSha256 lastSessionSha256 sourceInputsSha256 "
            "matchSha256 qualifications packets retirement ordinaryAcceptance h2ProviderAcceptance cryptoAcceptance",
            "CHILD_RESULT_FIELDS")
        ack = S.fields(qualification.canonical(native.stdout_raw, 16384), "schema scope contextSha256 invocation "
            "terminalSha256 ownerCloseSha256 ownerCloseBase64 closedNs clock bootDigest retirement", "CHILD_ACK_FIELDS")
        start = I.parse(native.start_raw, SMALL_LIMIT)
        require(type(child["schema"]) is int and child["schema"] == 1 and child["scope"] == CHILD_SCOPE and
            child["contextSha256"] == digest(context_raw) and child["startSha256"] == digest(native.start_raw) and
            child["invocation"] == invocation and child["clock"] == window["clock"] and child["bootDigest"] == boot and
            start["startedNs"] <= child["startedNs"] <= child["completedNs"] <= ack["closedNs"] <=
            I.parse(native.result_raw, SMALL_LIMIT)["completedNs"] < fence.work and child["retirement"] ==
            "PENDING_CHILD_OWNER_CLOSE" and all(child[name] == "NOT_PERFORMED" for name in
                ("ordinaryAcceptance", "h2ProviderAcceptance", "cryptoAcceptance")), "ORIGINAL_CHILD_RESULT")
        require(type(ack["schema"]) is int and ack["schema"] == 1 and ack["scope"] == ACK_SCOPE and
            ack["contextSha256"] == digest(context_raw) and ack["invocation"] == invocation and
            ack["terminalSha256"] == digest(child_raw) and ack["clock"] == window["clock"] and
            ack["bootDigest"] == boot and ack["retirement"] == "KNOWN", "ORIGINAL_CHILD_CLOSED_ACK")
        S.digest(ack["ownerCloseSha256"])
        actual_close = qualification.original_bytes(ack["ownerCloseBase64"], 16384)
        require(digest(actual_close) == ack["ownerCloseSha256"], "CHILD_ORIGINAL_CLOSE_BYTES")
        close_value = S.fields(qualification.canonical(actual_close, 16384),
            "schema scope resources readers writers closedNs retirement errors", "CHILD_ORIGINAL_CLOSE_FIELDS")
        require(type(close_value["schema"]) is int and close_value["schema"] == 1 and close_value["scope"] ==
            "INITIAL_ORDINARY_ACTUAL_OWNER_CLOSE_V1" and close_value["retirement"] == "KNOWN" and
            close_value["errors"] == [] and all(type(close_value[name]) is int and 0 < close_value[name] <= FILE_COUNT
                for name in ("resources", "readers", "writers")) and
            child["completedNs"] <= _scalar(close_value["closedNs"]) <= ack["closedNs"], "CHILD_ORIGINAL_CLOSE")
        native_context = I.parse(context_raw, SMALL_LIMIT)
        first_raws, first_queries, first_outputs, first_session_raw = _read_query_pass(owner, private, "current-first",
            child["firstSessionSha256"], native_context)
        last_raws, last_queries, last_outputs, _last_session_raw = _read_query_pass(owner, private, "current-last",
            child["lastSessionSha256"], native_context)
        first_bodies, first_decl, _first_authority, _first_at = _current_bodies(first_raws, observed, invocation, fence)
        bodies, declaration, _authority, authority_at = _current_bodies(last_raws, observed, invocation, fence)
        _query_source_sequence(first_queries, first_outputs, first_raws, observed, first_decl)
        _query_source_sequence(last_queries, last_outputs, last_raws, observed, declaration)
        require(first_decl == declaration and first_raws["event"] == last_raws["event"] == event and
            first_raws["candidate_policy_raw"] == last_raws["candidate_policy_raw"], "ORIGINAL_CURRENT_CHANGED")
        current_inputs = _source_inputs(owner)
        require(owner.read(private, "source-inputs.json") == I.encoded(current_inputs) and
            digest(I.encoded(current_inputs)) == child["sourceInputsSha256"], "ORIGINAL_CURRENT_INPUTS")
        packets = _previous_paths(child["packets"], kind)
        require(older is not None or retained_history is not None or all(Path(item["path"]).parent == path for item in packets),
                "NEW_PACKET_ROOT")
        if older is not None:
            require(I.encoded({"packets": list(packets)}) == older.packets_raw, "ORIGINAL_REUSE_SELECTION_CHANGED")
        elif retained_history is not None:
            require(I.encoded(list(packets)) == I.encoded(retained_history["packets"]), "RETAINED_SELECTION_CHANGED")
        archive_origins = (retained_origins if retained_origins is not None else
                          tuple((invocation, I.encoded(window)) for _ in packets) if older is None else older.archive_origins)
        results, archives = [], []
        for number, (entry, packet, archive_origin) in enumerate(zip(declaration["qualifications"], packets, archive_origins), 1):
            result, archive = _read_packet(owner, private, number, entry, declaration, authority_at, current_inputs,
                                          invocation, packet, archive_origin)
            results.append(result)
            archives.append(archive)
        require(retained_archives is None or tuple(archives) == retained_archives, "RETAINED_ARCHIVE_ORIGINALS_CHANGED")
        require(len(results) == 4 and [digest(item.record) for item in results] == child["qualifications"],
                "ALL_FOUR_ORIGINAL_QUALIFICATIONS")
        args = {"comment_raw": bodies["comment"], "observation_raw": last_raws["observation"],
            "now": int(time.time()), "histories": tuple(item.history for item in results),
            "prior_ancestry_raw": last_raws["prior_ancestry_raw"],
            "expected": (S.OrdinaryMatch(retained["match.json"]) if retained is not None else
                         None if older is None else older.match),
            **{name: last_raws[name] for name in ("base_policy_entry", "ancestry_raw", "candidate_policy_entry", "candidate_policy_raw")}}
        if kind == "gate":
            match = acquisition.gate.eligible(stage="stage2", approvals_raw=bodies["approvals"],
                environment_raw=bodies["environment"], branches_raw=bodies["branches"], **args)
            bound = None
        else:
            selection = I.parse(acquisition.gate.select(stage="stage2", run_id=observed["github"]["runId"],
                attempt=observed["github"]["runAttempt"], approvals_raw=bodies["approvals"]).record, SMALL_LIMIT)
            match = S.match_ordinary(comment_id=selection["commentId"], body_sha256=selection["bodySha256"], **args)
            bound = identity.bind_worker_match(match, comment_raw=bodies["comment"], event_raw=event,
                policy_raw=last_raws["candidate_policy_raw"], now=int(time.time()))
        require(match.record == last_raws["match"] and digest(match.record) == child["matchSha256"], "ORIGINAL_CURRENT_MATCH")
        require(retained_identity is None or bound.record == retained_identity.record, "RETAINED_CURRENT_IDENTITY_CHANGED")
        require(_source_inputs(owner) == current_inputs and continuity.boot_digest(first.clock.role) == boot,
                "FINAL_SOURCE_OR_BOOT_CHANGED")
        pending = owner.write(private, "parent-return-pending.json", {"schema": 1,
            "scope": "INITIAL_ORDINARY_NATIVE_PARENT_PENDING_OWN_CLOSE_V1", "contextSha256": digest(context_raw),
            "nativeReturnSha256": digest(native.result_raw), "matchSha256": digest(match.record),
            "qualifications": [digest(item.record) for item in results], "ordinaryAcceptance": "NOT_PERFORMED"})
        closed = owner.close()
        _checked_close(closed)
        fence.now()
        handle = InitialOrdinaryCurrent()
        record = I.encoded({"schema": 1, "scope": RETURN_SCOPE, "contextSha256": digest(context_raw),
            "source": declaration["firstPullRequest"]["merge"], "reviewed": declaration["reviewed"],
            "kind": kind, "profile": observed["profile"], "role": observed["role"],
            "matchSha256": digest(match.record), "identitySha256": None if bound is None else digest(bound.record),
            "qualifications": [digest(item.record) for item in results], "ownerCloseSha256": digest(closed.raw),
            "nativeReturnSha256": digest(native.result_raw), "pendingSha256": digest(pending),
            "ordinaryAcceptance": "NOT_PERFORMED", "h2ProviderAcceptance": "NOT_PERFORMED",
            "cryptoAcceptance": "NOT_PERFORMED", "budgetAcceptance": "NOT_ADMITTED", "publicationAuthority": False})
        state = _CurrentState(handle, owner, closed, native, context_raw, record, match, bound, tuple(results),
            I.encoded({"packets": list(packets)}), archive_origins, tuple(archives),
            tuple((name, first_raws[name]) for name in CURRENT_KEYS), first_session_raw, child_raw, token, prior, lineage)
        _RETURNS[id(handle)] = (state, tuple(getattr(state, name) for name in state.__dataclass_fields__))
        lineage["latest"] = handle
        checked_initial_ordinary(handle)
        return handle
    except BaseException as error:
        lineage.update(failed=True, original=error)
        if owner is not None:
            owner.error("initial-current-return", error)
            if not owner.closed:
                try:
                    owner.close()
                except BaseException as secondary:
                    if secondary is not error:
                        owner.error("initial-current-error-close", secondary)
        raise


def acquire_initial_ordinary(*, kind, cancelled, original_work_end_ns, original_final_end_ns):
    """New actual hosted gate/worker source acquisition; no implicit allocation.

    Caller supplies its already-retained original absolute ends. This function
    may shorten but cannot admit or renew them. Token must enter by the existing
    P2PKIT_ACTIONS_READ_TOKEN channel; only the fixed metadata child receives it.
    """
    return _new_current(kind, cancelled, original_work_end_ns, original_final_end_ns)


def refresh_initial_ordinary(current, *, cancelled, original_work_end_ns, original_final_end_ns):
    """Fresh source/service/packet read, retaining the original four ZIP bytes.

    No second archive download, key regeneration, old test execution or current
    authority reconstructed from a JSON receipt. A failed lineage is one-shot.
    Source caps are clipped inside the caller's original controller/job ends.
    """
    state = _history(current)
    try:
        return _new_current(I.parse(state.context_raw, SMALL_LIMIT)["observed"]["kind"], cancelled,
            original_work_end_ns, original_final_end_ns, prior=current)
    except BaseException as error:
        state.lineage.update(failed=True, original=error)
        raise


def reacquire_initial_ordinary(retained_data, expected_sha256, *, cancelled,
                              original_work_end_ns, original_final_end_ns):
    """Fresh real current from fixed retained packet DATA after actual step success.

    This process needs its own legitimate read token, same boot and actual host.
    The caller owns fixed-file readback and verifies the preceding Action step
    before entry. No saved owner/registry is loaded, no archive is downloaded,
    and no original first-use, policy expiry or service-job budget is renewed.
    """
    return _new_current("worker", cancelled, original_work_end_ns, original_final_end_ns,
                        retained=retained_data, retained_sha256=expected_sha256)


def _main():
    require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode and
        len(sys.argv) == 13 and sys.argv[1] == "_acquire-child", "FIXED_PRIVATE_CHILD_ONLY")
    kind, invocation, context_hash = sys.argv[2:5]
    require(kind in ("gate", "worker") and re.fullmatch(r"[0-9a-f]{32}", invocation) and
        re.fullmatch(r"[0-9a-f]{64}", context_hash) and all(re.fullmatch(r"[1-9][0-9]{0,19}", sys.argv[index])
            for index in (5, 6, 7, 8, 11)), "FIXED_PRIVATE_CHILD_ARGUMENTS")
    clock = origin.clocks.ClockIdentity(sys.argv[9], sys.argv[10], int(sys.argv[11]))
    window = _window(origin.clocks.Reading(clock, int(sys.argv[6])), int(sys.argv[7]), int(sys.argv[8]))
    minimum, boot = int(sys.argv[5]), S.digest(sys.argv[12])
    cancelled, handlers = [], {}

    def signal_received(number, _frame):
        cancelled.append(number)

    def check_cancel():
        if cancelled:
            raise KeyboardInterrupt("INITIAL_ORDINARY_NATIVE_CANCELLED")

    try:
        for number in (signal.SIGINT, signal.SIGTERM):
            handlers[number] = signal.getsignal(number)
            signal.signal(number, signal_received)
        raw = _child(kind, invocation, context_hash, minimum, window, boot, check_cancel)
        check_cancel()
        require(len(raw) <= 16384 and os.write(1, raw) == len(raw), "CHILD_ACK_SHORT_WRITE")
    finally:
        for number, handler in handlers.items():
            signal.signal(number, handler)


if __name__ == "__main__":
    try:
        _main()
    except BaseException:
        # Never print exception/args/cause or a traceback: signed URLs and raw
        # native diagnostics are private originals, not Actions log material.
        os.write(2, b"INITIAL_ORDINARY_NATIVE_HOLD\n")
        raise SystemExit(1) from None
