"""Productive finite K owner. Dormant source; no workflow/runtime acceptance.

One genuine R BEFORE original is consumed once, in this interpreter. No JSON
or externally constructed class can restore it. Its same live seal fence
remains mandatory through native, copy, carrier, pending and output closes.
The distinct flat10 grammar never calls the old P0/fixed30 export entry.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import stat
import time
import uuid

import hosted_initial_recipient_productive_receiver as R
import hosted_initial_recipient_productive_receiver_data as RD
import hosted_initial_recipient_productive_tail_data as TD
import hosted_initial_recipient_productive_custody_data as CD
import hosted_initial_recipient_evidence as E

P, C, N, B, O = R.P, R.P.C, R.P.N, R.P.B, R.P.O
native, Q, continuity = C.native, C.Q, C.C
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
NS = O.NS
CONTEXT_SCOPE, START_SCOPE, CHILD_SCOPE, ACK_SCOPE = TD.CONTEXT_SCOPE, TD.START_SCOPE, TD.CHILD_SCOPE, TD.ACK_SCOPE
CREDENTIAL_NAMES = (N.acquisition.origin.wire.TOKEN_ENV, "GITHUB_TOKEN", "GH_TOKEN",
    "ACTIONS_RUNTIME_TOKEN", "ACTIONS_CACHE_URL", "ACTIONS_RESULTS_URL")
CAP_FIELDS = tuple(zip(TD.CAP_FIELDS, ("--tail-started-ns", "--tail-work-end-ns", "--tail-final-end-ns")))
# All four exist before spawn; the later birth insertion cannot mutate the
# service directory across the child's two unchanged full start-file reads.
PRIVATE_DIRECTORIES = ("control-home", "temporary", "service", "native-birth")
PHASE_PLACEMENT = tuple((name, "native-birth" if name == "native-start.json" else "service") for name in TD.PHASE_NAMES)
DIRECTORIES = ("root", "tail-returned", *PRIVATE_DIRECTORIES,
    "tail-public-crypto", "tail-copied-evidence", "tail-export-output")
INPUT_LIMITS = {"source-index.json": CD.LIMIT, "before-index.json": CD.LIMIT,
    "before-input-close.json": CD.LIMIT, "before-readback-close.json": CD.LIMIT,
    "before-native-close.json": CD.LIMIT, "before-writer-close.json": CD.LIMIT,
    "deadline.json": CD.PUBLIC_LIMIT}
_ATTEMPTS, _PARENTS, _CLOCKS, _FILE_PINS, _NATIVE, _CARRIERS, _OUTPUTS = {}, {}, {}, {}, {}, {}, {}
_OWNER_REGISTRY, _PINS, _CHILDREN, _VIEWS, _NODES, _CHILD_FAILURES = {}, {}, {}, {}, {}, {}
_ENTRY = C.B.EntryLatch(_ATTEMPTS)


def require(value, code):
    TD.require(value, "OWNER_" + code)


def _paths():
    parent = C._paths("worker")[2]
    root = parent / "productive-tail"
    private = root / TD.DIRECTORY
    return {"root": root, "tail-returned": private, **{name: private / name for name in PRIVATE_DIRECTORIES},
        **{name: root / name for name in ("tail-public-crypto", "tail-copied-evidence", "tail-export-output")}}


def _phase_directory(name):
    """One closed physical placement; semantic phase labels are unchanged."""
    _source_current()
    require(type(name) is str and name in TD.PHASE_NAMES, "NATIVE_PHASE_NAME")
    return next(directory for label, directory in PHASE_PLACEMENT if label == name)


def _phase_roster(directory, observed):
    _source_current()
    require(type(directory) is str and directory in ("service", "native-birth") and
        type(observed) is tuple and all(type(name) is str for name in observed) and
        observed == tuple(sorted(name for name, parent in PHASE_PLACEMENT if parent == directory)),
        "NATIVE_PHASE_DISK_ROSTER")
    return observed


def _track(value):
    _source_current()
    require(id(value) not in _PINS and type(value.__dict__) is dict, "ORIGINAL_OBJECT_NEW")
    _PINS[id(value)] = (value, type(value), value.__dict__, tuple(value.__dict__.items()))
    return value


def _pin(value):
    _source_current()
    saved = _PINS.get(id(value))
    require(type(saved) is tuple and saved[0] is value and type(value) is saved[1] and
        value.__dict__ is saved[2] and tuple(value.__dict__) == tuple(name for name, _ in saved[3]) and
        all(value.__dict__[name] is original for name, original in saved[3]), "ORIGINAL_OBJECT_CHANGED")
    return value


def _closed_files(owner):
    require(type(owner) is C._PrimaryOwner, "FILE_OWNER_TYPE")
    owner.structural()
    require(owner.finished and owner.failure is None and owner.owner.closed and not owner.owner.unknown and
        owner.owner.original is None and owner.errors == [] and all(a and c for _r, _l, _v, a, c in owner.rows),
        "FILE_OWNER_CLOSE_UNKNOWN")


@dataclass(frozen=True, repr=False)
class _File:
    owner: object
    directory: object
    name: str
    reader: object
    ordinal: int
    maximum: int
    count: int
    raw: bytes


def _open_file(owner, directory, name, maximum):
    """Separate fixed bounded reader; never put ciphertext in a Snapshot."""
    require(type(owner) is C._PrimaryOwner and type(maximum) is int and 0 < maximum <= TD.MAX_ZIP_BYTES, "READER_BOUND")
    Q._component(name)
    owner.guard()
    require(type(directory) is (native.windows.PrivateDirectory if os.name == "nt" else Q._PosixDirectory) and
        any(label == "directory" and resource is directory and not attempted and not closed
            for _row, label, resource, attempted, closed in owner.rows), "READER_ORIGINAL_OWNED_DIRECTORY")
    end = min(owner.owner.local_end, owner.owner.fence.deadline(900))
    path, directory_pin = directory.path / name, (directory.path, tuple(directory.identity))
    if os.name == "nt":
        reader = owner.acquire("reader", lambda: directory.open_file(name, max_bytes=maximum, deadline=end))
        require(type(reader) is native.windows.NativeFile, "READER_TYPE")
        info = reader.initial_info
    else:
        reader = owner.acquire("reader", lambda: Q._posix_stream(path, os.O_RDONLY | os.O_NOFOLLOW, "rb"))
        require(type(reader) is io.BufferedReader, "READER_TYPE")
        info = Q._file_info(path, reader, maximum)
    raw = O.encoded(info.as_dict())  # Pin the actual metadata return before another callback.
    result = _File(owner, directory, name, reader, len(owner.rows) - 1, maximum, info.size, raw)
    _FILE_PINS[id(result)] = (result, result.__dict__, owner._anchor(), directory_pin, path, info,
        N._history_graph(result.__dict__, path, directory_pin[0]), False)
    _file_current(result)
    owner.guard()
    return result


def _file_current(value, *, closed=False):
    saved = _FILE_PINS.get(id(value))
    require(type(value) is _File and type(saved) is tuple and saved[0] is value and value.__dict__ is saved[1] and
        type(closed) is bool and value.owner._anchor() is saved[2], "FILE_ORIGINAL_HANDLE")
    owner = value.owner
    owner.structural()
    N._check_history(saved[6])
    require(value.directory.path is saved[3][0] and tuple(value.directory.identity) == saved[3][1] and
        value.ordinal < len(owner.rows) and owner.rows[value.ordinal][2] is value.reader and
        owner.rows[value.ordinal][3:] == ((True, True) if closed else (False, False)) and
        O.encoded(saved[5].as_dict()) == value.raw and type(value.count) is int and
        0 <= value.count <= value.maximum <= TD.MAX_ZIP_BYTES, "FILE_ORIGINAL_METADATA_OR_CLOSE")
    TD.metadata(C.canonical(value.raw), owner.owner.first.clock.role, value.count)
    if not closed:
        value.directory.verify()
        current = value.reader.verify() if os.name == "nt" else Q._file_info(saved[4], value.reader, value.maximum)
        require(current == saved[5] and O.encoded(current.as_dict()) == value.raw, "FILE_LIFETIME_CHANGED")
    return saved


def _stream(value, checksum=None, *, writer=None, retain=False, close=False):
    """Exact64KiB, expected bytes/hash/EOF/metadata. Zero files are read too."""
    require(type(retain) is bool and type(close) is bool and (not retain or value.count <= native.LIMIT), "STREAM_RETAIN")
    if checksum is not None:
        C.digest(checksum)
    owner, total, hashed, pieces, written = value.owner, 0, hashlib.sha256(), [], None
    try:
        _file_current(value)
        owner.guard()
        require(value.reader.seek(0) == 0, "STREAM_INITIAL_POSITION")
        while total < value.count:
            owner.guard()
            piece = value.reader.read(min(C.COPY_CHUNK, value.count - total))
            require(type(piece) is bytes and 0 < len(piece) <= min(C.COPY_CHUNK, value.count - total), "STREAM_SHORT_READ")
            total += len(piece)
            hashed.update(piece)
            if retain:
                pieces.append(piece)
            owner.guard()
            if writer is not None:
                amount = writer.write(piece)
                require(type(amount) is int and amount == len(piece), "STREAM_SHORT_WRITE")
                owner.guard()
        owner.guard()
        tail = value.reader.read(1)
        require(type(tail) is bytes and tail == b"" and total == value.count and
            (checksum is None or hashed.hexdigest() == checksum), "STREAM_HASH_SIZE_EOF")
        _file_current(value)
        if writer is not None:
            writer.sync()
            info = writer.verify()
            written = O.encoded(info.as_dict())
            require(type(info.size) is int and info.size == value.count, "STREAM_WRITER_SIZE")
            TD.metadata(C.canonical(written), owner.owner.first.clock.role, value.count)
        owner.guard()
        return b"".join(pieces) if retain else (hashed.hexdigest(), written)
    except BaseException as error:
        raise owner.remember(error)
    finally:
        for resource in (value.reader if close else None, writer):
            if resource is not None and not owner.owner.unknown:
                try:
                    owner.close_one(resource)
                except BaseException as error:
                    owner.remember(error, unknown=True)
        if owner.failure is not None:
            raise owner.failure


def _small(owner, directory, name, maximum, *, checksum=None):
    reader = _open_file(owner, directory, name, maximum)
    return _stream(reader, checksum, retain=True, close=True)


def _write_bytes(owner, directory, name, raw):
    """Actual exclusive writer and separate closed reader, not a JSON receipt."""
    require(type(raw) is bytes and 0 <= len(raw) <= native.LIMIT, "WRITE_BYTES_BOUND")
    Q._component(name)
    writer = None
    try:
        end = owner.guard()
        writer = owner.acquire("writer", lambda: directory.create_file(name, max_bytes=max(1, len(raw)), deadline=end))
        written = writer.write(raw)
        require(type(written) is int and written == len(raw), "WRITE_BYTES_SHORT")
        writer.sync()
        observed = writer.verify()
        before_raw = O.encoded(observed.as_dict())
        require(observed.size == len(raw), "WRITE_BYTES_SIZE")
        owner.guard()
    except BaseException as error:
        raise owner.remember(error)
    finally:
        if writer is not None and not owner.owner.unknown:
            owner.close_one(writer)
        if owner.failure is not None:
            raise owner.failure
    readback = _open_file(owner, directory, name, max(1, len(raw)))
    actual = _stream(readback, O.digest(raw), retain=True, close=True)
    require(actual == raw, "WRITE_BYTES_READBACK")
    policy = TD.write_close_metadata(owner.owner.first.clock.role, C.canonical(before_raw),
        C.canonical(readback.raw), len(raw))
    return {"preCloseWrite": C.canonical(before_raw), "postCloseReadback": C.canonical(readback.raw),
        "metadataPolicy": policy}


def _list_names(owner, directory, maximum):
    require(type(maximum) is int and 0 < maximum <= CD.MAX_NODES, "DIRECTORY_LIST_CAP")
    end = owner.guard()
    directory.verify()
    if os.name == "nt":
        actual = directory.names(max_names=maximum, deadline=end)
    else:
        actual = []
        with os.scandir(directory.path) as entries:
            for entry in entries:
                require(len(actual) < maximum, "DIRECTORY_LIMIT")
                actual.append(Q._component(entry.name))
    require(len(actual) == len(set(name.casefold() for name in actual)), "DIRECTORY_CASE_ALIAS")
    for name in actual:
        Q._component(name)
    directory.verify()
    owner.guard()
    return tuple(sorted(actual))


def _names(owner, directory, expected):
    require(type(expected) is tuple and len(expected) <= CD.MAX_NODES and len(set(expected)) == len(expected),
        "DIRECTORY_EXPECTED")
    require(_list_names(owner, directory, max(1, len(expected))) == tuple(sorted(expected)), "DIRECTORY_EXACT_ROSTER")


@dataclass(eq=False, repr=False)
class _TailOwnerAnchor:
    owner: object
    dictionary: dict
    binding: tuple
    first_graph: tuple
    rows: tuple = ()
    pending: object = None
    failure: object = None
    unknown: bool = False
    closed: bool = False
    frozen: object = None
    phase: object = None
    phase_active: bool = False
    busy: bool = False
    closing: object = None
    error_rows: tuple = ()
    error_graph: tuple = ()


class _TailNativeOwner(native.Owner):
    """Actual custody-only Owner with original return/close observations.

    Shared native Owner file methods and original phase/source callers use these
    fixed acquisition/close seams. Nothing replaces a native resource backend or
    the first Window. A callback cannot create closure by editing ledger flags.
    """
    def __init__(self, local_end, fence=None, *, first=None, cancelled=lambda: None):
        require(type(self) is _TailNativeOwner and id(self) not in _OWNER_REGISTRY and
            type(fence) is _Clock and first is not None,
            "AUTHORITY_OWNER_NEW")
        native.Owner.__init__(self, local_end, fence, first=first, cancelled=cancelled)
        self.initial_sources = {}
        binding = (self.first, self.fence, self.cancelled, self.local_end, self.resources,
            self.errors, self.initial_sources, self.admissions, self.early_last,
            self.entry_original, self.entry_close_attempted, self.entry_close_original, self.entry_close_snapshot)
        _OWNER_REGISTRY[id(self)] = _TailOwnerAnchor(self, self.__dict__, binding,
            N._history_graph(first), error_graph=N._history_graph(self.errors))
        self.check()

    def _anchor(self):
        anchor = _OWNER_REGISTRY.get(id(self))
        require(type(self) is _TailNativeOwner and type(anchor) is _TailOwnerAnchor and anchor.owner is self,
            "AUTHORITY_OWNER_ORIGINAL_HANDLE")
        return anchor

    def error(self, stage, error, *, unknown=False):
        anchor = self._anchor()
        if anchor.failure is None:
            anchor.failure = error  # Only this actual error callback establishes the first failure.
        anchor.unknown |= unknown
        if self.__dict__ is anchor.dictionary:
            try:
                native.Owner.error(self, stage, error, unknown=anchor.unknown)
            except BaseException:
                anchor.unknown = True
            anchor.unknown |= self.unknown
            anchor.dictionary["unknown"] = anchor.unknown
            # These rows were produced by the actual error recorder. The original
            # first exception above is independently retained even if it is falsey.
            anchor.error_rows = tuple(anchor.binding[5])
            anchor.error_graph = N._history_graph(anchor.binding[5])
        else:
            anchor.unknown = True
            anchor.dictionary["unknown"] = True
        if anchor.unknown and not any(owner is self for owner in native.QUARANTINE):
            native.QUARANTINE.append(self)

    def check(self):
        """Passive original binding/ledger checks; never observe or grant time."""
        anchor = self._anchor()
        try:
            _source_current()
            first, fence, cancelled, local, resources, errors, sources, admissions, early, \
                entry, entry_attempted, entry_original, entry_snapshot = anchor.binding
            require(self.__dict__ is anchor.dictionary and self.first is first and self.fence is fence and
                self.cancelled is cancelled and type(self.local_end) is float and self.local_end == local and
                self.resources is resources and self.errors is errors and self.initial_sources is sources and
                self.admissions is admissions and type(self.early_last) is int and self.early_last == early and
                self.entry_original is entry and self.entry_close_attempted is entry_attempted and
                self.entry_close_original is entry_original and self.entry_close_snapshot is entry_snapshot and
                self.original is anchor.failure and self.unknown is anchor.unknown and self.closed is anchor.closed,
                "AUTHORITY_OWNER_BINDING_CHANGED")
            limits = anchor.phase[1:3] if anchor.phase_active else (None, None)
            require(all(type(value) is type(original) and value == original for value, original in
                zip((self.work_limit, self.final_limit), limits)), "AUTHORITY_OWNER_PHASE_LIMITS_CHANGED")
            N._check_history(anchor.first_graph)
            require(type(resources) is list and len(resources) == len(anchor.rows) <= CD.MAX_NODES and
                len({id(row) for row, *_ in anchor.rows}) == len(anchor.rows) ==
                len({id(resource) for _row, _label, resource, _a, _c in anchor.rows}), "AUTHORITY_OWNER_ROSTER_CHANGED")
            for current, (row, label, resource, attempted, closed) in zip(resources, anchor.rows):
                require(current is row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                    type(row["label"]) is str and row["label"] == label and row["owner"] is resource and
                    row["attempted"] is attempted and row["closed"] is closed and (not closed or attempted),
                    "AUTHORITY_OWNER_RESOURCE_CHANGED")
            require(type(errors) is list and len(errors) == len(anchor.error_rows) and
                all(current is original for current, original in zip(errors, anchor.error_rows)), "AUTHORITY_OWNER_ERRORS_CHANGED")
            N._check_history(anchor.error_graph)
            if anchor.frozen is not None:
                require(tuple((row, label, resource) for row, label, resource, _a, _c in anchor.rows) == anchor.frozen,
                    "AUTHORITY_OWNER_FROZEN_CHANGED")
            return anchor
        except BaseException as error:
            self.error("custody-owner-binding", error, unknown=True)
            raise anchor.failure

    def end(self, *, final=False):
        anchor = self.check()
        try:
            result = native.Owner.end(self, final=final)
            self.check()
            require(final or anchor.failure is None, "AUTHORITY_OWNER_CALLBACK_FAILED")
            return result
        except BaseException as error:
            self.error("custody-owner-fence", error)
            try:
                self.check()
            except BaseException:
                pass  # Binding failure retains UNKNOWN and the original error.
            raise anchor.failure

    def acquire(self, label, factory, *, final=False):
        anchor = self.check()
        require(type(label) is str and label in ("directory", "writer", "stdout", "stderr", "native-scope") and
            type(final) is bool, "AUTHORITY_OWNER_RESOURCE_LABEL")
        if anchor.busy:
            self.error("custody-owner-reentry", O.OriginError("INITIAL_CUSTODY_AUTHORITY_OWNER_REENTRY"))
            raise anchor.failure
        require(not anchor.closed and anchor.frozen is None and not anchor.unknown, "AUTHORITY_OWNER_ACQUIRE_CLOSED")
        anchor.busy = True
        try:
            self.end(final=final)
            try:
                value = factory()
            except BaseException as error:
                self.error("custody-" + label + "-allocation", error, unknown=True)
                raise anchor.failure
            anchor.pending = value  # FIRST operation after actual return; before any callback/check.
            self.check()
            require(not any(resource is value for _row, _label, resource, _a, _c in anchor.rows),
                "AUTHORITY_OWNER_DUPLICATE_RESOURCE")
            row = {"label": label, "owner": value, "attempted": False, "closed": False}
            anchor.rows = (*anchor.rows, (row, label, value, False, False))
            anchor.binding[4].append(row)
            anchor.pending = None
            self.end(final=final)
            return value
        except BaseException as error:
            self.error("custody-owner-acquire", error, unknown=anchor.pending is not None)
            try:
                self.check()
            except BaseException:
                pass
            raise anchor.failure
        finally:
            anchor.busy = False

    def close_fence(self):
        anchor = self.check()
        if anchor.unknown:
            return False
        native.Owner.close_fence(self)  # Same retained fence/LOCAL ceiling; never a new allowance.
        self.check()
        return not anchor.unknown

    def close_one(self, value):
        anchor = self.check()
        if anchor.closing is not None:
            self.error("custody-owner-close-reentry", O.OriginError("INITIAL_CUSTODY_AUTHORITY_OWNER_CLOSE_REENTRY"))
            raise anchor.failure
        index = next((index for index, row in enumerate(anchor.rows) if row[2] is value), None)
        require(index is not None, "AUTHORITY_OWNER_FOREIGN_CLOSE")
        row, label, resource, attempted, closed = anchor.rows[index]
        if attempted:
            require(closed, "AUTHORITY_OWNER_CLOSE_RETRY")
            return
        if anchor.unknown or not self.close_fence():
            return
        self.check()
        anchor.closing = resource
        row["attempted"] = True
        anchor.rows = (*anchor.rows[:index], (row, label, resource, True, False), *anchor.rows[index + 1:])
        try:
            resource.close()  # The actual unchanged backend's return is the ONLY close proof.
        except BaseException as error:
            self.error("custody-" + label + "-close", error, unknown=True)
        else:
            row["closed"] = True
            anchor.rows = (*anchor.rows[:index], (row, label, resource, True, True), *anchor.rows[index + 1:])
        finally:
            anchor.closing = None
        self.close_fence()

    def close(self):
        anchor = self.check()
        if anchor.closed:
            return
        anchor.closed = True
        self.closed = True
        self.close_fence()
        for _row, _label, resource, _attempted, _closed in reversed(anchor.rows):
            if anchor.unknown:
                break
            self.close_one(resource)
        self.close_fence()
        if anchor.unknown:
            if not any(owner is self for owner in native.QUARANTINE):
                native.QUARANTINE.append(self)
            raise anchor.failure if anchor.failure is not None else O.OriginError("INITIAL_CUSTODY_AUTHORITY_OWNER_UNKNOWN")

    def freeze(self):
        anchor = self.check()
        require(not anchor.closed and not anchor.unknown and anchor.failure is None and anchor.frozen is None and
            anchor.pending is None and not anchor.busy and anchor.closing is None and not anchor.phase_active,
            "AUTHORITY_OWNER_FREEZE")
        anchor.frozen = tuple((row, label, resource) for row, label, resource, _a, _c in anchor.rows)

    def known(self):
        anchor = self.check()
        require(anchor.frozen is not None and anchor.closed and not anchor.unknown and anchor.failure is None and
            anchor.pending is None and not anchor.busy and anchor.closing is None and not anchor.phase_active and
            all(attempted and closed for _row, _label, _resource, attempted, closed in anchor.rows),
            "AUTHORITY_OWNER_CLOSE_NOT_KNOWN")
        return anchor

@dataclass(eq=False, repr=False)
class _ClockState:
    handle: object
    binding: tuple
    graph: tuple
    last: int
    local_last: float
    failure: object = None
    busy: bool = False


class _Clock:
    """Actual first RAW/LOCAL, fixed shortening; optional SAME live R fence."""
    __slots__ = ("_binding",)

    def __init__(self, first, local, boot, cancelled, deadline, caps, before=None):
        require(type(self) is _Clock and id(self) not in _CLOCKS and callable(cancelled), "CLOCK_NEW")
        O.clocks.validate_reading(first)
        CD.local(local)
        parsed = RD.deadline(TD.encoded(deadline, CD.PUBLIC_LIMIT))
        TD.caps(parsed, caps)
        require(O.clock_value(first.clock) == parsed["clock"] and boot == parsed["originalBootDigest"] and
            caps[0] <= first.nanoseconds < caps[1], "CLOCK_ORIGINAL_FIRST")
        work = O.wire._directed_deadline(local, (caps[1] - first.nanoseconds) / NS, caps[1], first.nanoseconds)
        final = O.wire._directed_deadline(local, (caps[2] - first.nanoseconds) / NS, caps[2], first.nanoseconds)
        if before is not None:
            require(R.checked_productive_before(before) is before, "SAME_BEFORE")
            work, final = min(work, before.fence.local_end), min(final, before.fence.local_end)
        self._binding = (first, local, boot, cancelled, deadline, caps, work, final, before)
        _CLOCKS[id(self)] = _ClockState(self, self._binding, N._history_graph(first, deadline, caps),
            first.nanoseconds, local)
        self.current()

    def _anchor(self):
        saved = _CLOCKS.get(id(self))
        require(type(self) is _Clock and type(saved) is _ClockState and saved.handle is self, "ORIGINAL_CLOCK")
        return saved

    def fail(self, error):
        saved = self._anchor()
        if saved.failure is None:
            saved.failure = error
        return saved.failure

    def current(self):
        saved = self._anchor()
        if saved.failure is not None:
            raise saved.failure
        try:
            _source_current()
            require(self._binding is saved.binding and not any(name in os.environ for name in CREDENTIAL_NAMES) and
                not native.QUARANTINE and not Q.QUARANTINE and not continuity.QUARANTINE and
                not E.windows._QUARANTINE and not native.diagnostics._QUARANTINE, "CLOCK_LINEAGE_OR_QUARANTINE")
            N._check_history(saved.graph)
            before = saved.binding[8]
            if before is not None:
                _pin(before)
                require(R.checked_productive_before(before) is before, "ORIGINAL_BEFORE_RETURN")
            return saved
        except BaseException as error:
            raise self.fail(error)

    reading = property(lambda self: self.current().binding[0])
    clock = property(lambda self: self.reading.clock)
    first = property(lambda self: self.reading.nanoseconds)
    first_local = property(lambda self: self.current().binding[1])
    deadline_data = property(lambda self: self.current().binding[4])
    caps = property(lambda self: self.current().binding[5])
    work = property(lambda self: self.caps[1])
    final = property(lambda self: self.caps[2])
    local_end = property(lambda self: self.current().binding[7])
    cancelled = property(lambda self: self.current().binding[3])
    last = property(lambda self: self.current().last)

    def now(self, *, final=False, minimum=0, limit=None):
        saved = self.current()
        try:
            require(type(final) is bool and not saved.busy, "CLOCK_REENTRY")
            saved.busy = True
            end = saved.binding[5][2 if final else 1]
            if limit is not None:
                end = min(end, CD.integer(limit))
            frontier = max(saved.last, CD.integer(minimum))
            for number in range(2):
                local = CD.local(time.monotonic())
                require(saved.local_last <= local < saved.binding[7 if final else 6], "LOCAL_EXPIRED_OR_BACKWARDS")
                saved.local_last = local
                before = saved.binding[8]
                if before is not None:
                    frontier = max(frontier, before.fence.now(final=final, minimum=frontier, limit=end))
                    self.current()
                now = O.clocks.checked_now(saved.binding[0].clock, minimum_ns=frontier)
                saved.last = frontier = CD.integer(now, frontier, end - 1)
                self.current()
                boot = continuity.boot_digest(saved.binding[0].clock.role)
                self.current()
                require(boot == saved.binding[2], "BOOT_CHANGED")
                if number == 0:
                    saved.binding[3]()
                    self.current()
                    require(saved.busy and saved.last == frontier and saved.local_last == local, "CLOCK_CALLBACK_CHANGED")
            after = CD.local(time.monotonic())
            require(saved.local_last <= after < saved.binding[7 if final else 6], "CLOCK_FINAL_LOCAL")
            saved.local_last = after
            return frontier
        except BaseException as error:
            raise self.fail(error)
        finally:
            saved.busy = False

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 900,
            "MECHANISM_SUBCAP")
        local = CD.local(time.monotonic())
        now = self.now(final=final, limit=limit)
        end = self.final if final else self.work
        if limit is not None:
            end = min(end, CD.integer(limit))
        return min(self.current().binding[7 if final else 6],
            O.wire._directed_deadline(local, maximum, end, now))


class _Parent:
    __slots__ = ("_binding",)

    def __init__(self, before, attempt):
        require(type(self) is _Parent and id(self) not in _PARENTS and
            not any(saved[1][0] is before for saved in _PARENTS.values()), "BEFORE_CONTINUATION_ONCE")
        _track(before)  # Returned object pinned BEFORE the first supplier callback.
        require(R.checked_productive_before(before) is before, "GENUINE_BEFORE_REQUIRED")
        _pin(before)
        deadline = RD.deadline(before.deadline_raw)
        closed = TD.canonical(before.authority_index_raw)["closeWriterReturn"]["closedNs"]
        before.fence.now(minimum=closed)
        local = CD.local(time.monotonic())
        first = O.clocks.observe()
        boot = continuity.boot_digest(first.clock.role)
        start = first.nanoseconds
        work = min(start + 210 * NS, deadline["sealEndNs"] - 45 * NS)
        caps = TD.caps(deadline, (start, work, work + 45 * NS))
        clock = _Clock(first, local, boot, before.fence.cancelled, deadline, caps, before)
        self._binding = (before, attempt, clock, closed)
        _PARENTS[id(self)] = (self, self._binding, {"failure": None, "phase": "BEFORE_RETURNED",
            "native": None, "carrier": None, "pending": None})
        self.current()

    def _anchor(self):
        saved = _PARENTS.get(id(self))
        require(type(self) is _Parent and type(saved) is tuple and saved[0] is self and
            self._binding is saved[1], "PARENT_ORIGINAL")
        return saved

    def fail(self, error):
        saved = self._anchor()
        error = _ENTRY.fail(error)
        error = saved[1][2].fail(error)
        if saved[2]["failure"] is None:
            saved[2]["failure"] = error
        return saved[2]["failure"]

    def current(self):
        saved = self._anchor()
        if saved[2]["failure"] is not None:
            raise saved[2]["failure"]
        try:
            _source_current()
            _ENTRY.check(_ATTEMPTS, saved[1][1])
            _pin(saved[1][0])
            require(R.checked_productive_before(saved[1][0]) is saved[1][0], "SAME_BEFORE_ORIGINAL")
            saved[1][2].current()
            return saved
        except BaseException as error:
            raise self.fail(error)

    clock = property(lambda self: self.current()[1][2])
    before = property(lambda self: self.current()[1][0])

    def now(self, **kwargs):
        self.current()
        result = self.clock.now(**kwargs)
        self.current()
        return result

    def currency(self):
        self.now()
        return self.current()


@dataclass(frozen=True, repr=False)
class TailChild:
    pass


@dataclass(frozen=True, repr=False)
class TailArchiveBinding:
    pass


@dataclass(frozen=True, repr=False)
class TailChildSourceBinding:
    job_id: str
    observed_raw: bytes
    event_sha256: str
    context_sha256: str
    start_sha256: str


@dataclass(frozen=True, repr=False)
class TailValidationCaps:
    clock: object
    first: object
    firstLocal: float
    workEndNs: int
    workEndLocal: float
    operationFinishEndNs: int
    operationFinishEndLocal: float
    finishReserveNs: int
    operationLimitNs: int


@dataclass(frozen=True, repr=False)
class TailArchiveCaps:
    clock: object
    first: object
    firstLocal: float
    workEndNs: int
    workEndLocal: float
    operationFinishEndNs: int
    operationFinishEndLocal: float
    finishReserveNs: int
    operationLimitNs: int


@dataclass(frozen=True, repr=False)
class TailValidationView:
    child: object
    role: str
    work: object
    public_key_raw: bytes
    policy_raw: bytes
    original_match_raw: bytes
    source: object
    caps: object


@dataclass(frozen=True, repr=False)
class TailArchiveView:
    child: object
    archive: object
    recipient: object
    role: str
    payload: object
    output: object
    payload_root: object
    members: tuple
    map: object
    lineage: object
    caps: object
    public_inputs: bytes


@dataclass(frozen=True, repr=False)
class ExpectedNode:
    relative: str
    kind: str
    bytes: object
    sha256: object
    native: tuple
    provenance: object


@dataclass(frozen=True, repr=False)
class _NodeOrigin:
    child: object
    path: object
    raw: object
    owner: object
    label: str


@dataclass(frozen=True, repr=False)
class _Lineage:
    child: object
    context_raw: bytes
    start_raw: bytes
    metadata_close: bytes
    copied_close: bytes
    map_raw: bytes


@dataclass(frozen=True, repr=False)
class _Completion:
    returned: object
    raw: int
    local: float


@dataclass(eq=False, repr=False)
class _State:
    handle: object
    clock: object
    context_raw: bytes
    start_raw: bytes
    raws: tuple
    metadata_close: bytes
    metadata_owner: object
    owner: object
    roots: tuple
    source: object
    validation: object = None
    validation_return: object = None
    validation_completed: object = None
    archive: object = None
    archive_view: object = None
    root: object = None
    members: object = None
    map: object = None
    lineage: object = None
    public_inputs: object = None
    backend_return: object = None
    export_completed: object = None
    closed: object = None
    failure: object = None


def _set(state, **values):
    _pin(state)
    for name, value in values.items():
        require(name in state.__dict__, "KNOWN_STATE_FIELD")
        setattr(state, name, value)
    _PINS[id(state)] = (state, type(state), state.__dict__, tuple(state.__dict__.items()))


def _state(child, *, retired=False):
    state = _CHILDREN.get(id(child))
    require(type(child) is TailChild and type(state) is _State and state.handle is child, "GENUINE_CHILD_REQUIRED")
    if id(state) in _CHILD_FAILURES:
        raise _CHILD_FAILURES[id(state)]
    _pin(child)
    _pin(state)
    if state.failure is not None:
        raise state.failure
    _closed_files(state.metadata_owner)
    _pin(state.source)
    state.clock.current()
    require((state.closed is not None) is retired, "ORIGINAL_CHILD_PHASE")
    if retired:
        _closed_files(state.owner)
    else:
        state.owner.structural()
        require(not state.owner.finished and state.owner.failure is None and not state.owner.owner.unknown,
            "LIVE_OUTER_OWNER_REQUIRED")
    for name, directory, path, identity in state.roots:
        require(directory.path is path and tuple(directory.identity) == identity, "ORIGINAL_BORROWED_ROOT")
        if not retired:
            directory.verify()
    return state


def _fail(state, error):
    # Keep the first error outside the callback-facing state, even if its
    # dictionary or a method has already been replaced. Never adopt a repair.
    failure = _CHILD_FAILURES.setdefault(id(state), error)
    original = _PINS.get(id(state))
    require(type(original) is tuple and original[0] is state, "ORIGINAL_FAILURE_STATE")
    clock = dict(original[3])["clock"]
    return clock.fail(failure)


def _operation_caps(state, kind):
    state.clock.now()
    local = CD.local(time.monotonic())
    first = O.clocks.observe()
    require(first.clock == state.clock.clock and first.nanoseconds >= state.clock.last, "OPERATION_ORIGINAL_CLOCK")
    seconds = 60 if kind is TailValidationCaps else 240
    finish = min(state.clock.work, first.nanoseconds + seconds * NS)
    reserve = 30 * NS if first.clock.role == "windows-x64" else 0
    work = finish - reserve
    require(first.nanoseconds < work <= finish <= state.clock.work, "OPERATION_FITS_OR_REFUSE")
    finish_local = min(state.clock.current().binding[6], O.wire._directed_deadline(local, seconds, finish, first.nanoseconds))
    work_local = min(finish_local - reserve / NS, O.wire._directed_deadline(local, seconds, work, first.nanoseconds))
    require(local < work_local <= finish_local, "OPERATION_LOCAL_INTERVAL")
    return _track(kind(first.clock, first, local, work, work_local, finish, finish_local, reserve, seconds * NS))


def _operation_current(state, caps, completion):
    _pin(caps)
    if completion is None:
        state.clock.now(limit=caps.operationFinishEndNs)
        require(CD.local(time.monotonic()) < caps.operationFinishEndLocal, "OPERATION_LOCAL_EXPIRED")
    else:
        _pin(completion)
        require(caps.first.nanoseconds <= completion.raw < caps.operationFinishEndNs and
            caps.firstLocal <= completion.local < caps.operationFinishEndLocal, "ORIGINAL_OPERATION_COMPLETION")


def checked_child_validation(child):
    state = _state(child)
    try:
        if state.validation is None:
            require(state.archive is None and state.validation_return is None, "VALIDATION_ONCE")
            roots, raws = dict((name, directory) for name, directory, _path, _pin in state.roots), dict(state.raws)
            work = roots["tail-public-crypto"]
            view = _track(TailValidationView(child, state.clock.clock.role, work if os.name == "nt" else work.path,
                raws["returned/recipient-public.asc"], raws["returned/candidate-policy.json"],
                raws["returned/original-match.json"], state.source, _operation_caps(state, TailValidationCaps)))
            _VIEWS[id(view)] = view, child
            _set(state, validation=view)
        return _check_child_validation(state.validation)
    except BaseException as error:
        raise _fail(state, error)


def _check_child_validation(view):
    _pin(view)
    require(type(view) is TailValidationView, "TAIL_VALIDATION_VIEW_ONLY")
    state = _state(view.child)
    binding = _VIEWS.get(id(view))
    require(type(binding) is tuple and binding[0] is view and binding[1] is view.child and
        state.validation is view and view.source is state.source,
        "ORIGINAL_VALIDATION_VIEW")
    _operation_current(state, view.caps, state.validation_completed)
    return view


def _node_current(node, child):
    _pin(node)
    require(type(node) is ExpectedNode and _NODES.get(id(node)) is node, "ORIGINAL_NODE")
    CD.native(node.native, directory=node.kind == "directory")
    _pin(node.provenance)
    require(type(node.provenance) is _NodeOrigin, "ORIGINAL_NODE_PROVENANCE")
    source = node.provenance
    require(source.child is child and source.path == _paths()["tail-copied-evidence"] / node.relative and
        source.label in ("ACTUAL_K_COPY_READBACK", "ACTUAL_SEPARATE_MAP_WRITER_READBACK", "ACTUAL_FINAL_FLAT_ROOT"),
        "ORIGINAL_NODE_SOURCE_BINDING")
    _closed_files(source.owner)
    if node.kind == "file":
        require(type(source.raw) is bytes and node.bytes == len(source.raw) and node.sha256 == TD.sha(source.raw),
            "ORIGINAL_CLOSED_NODE_BYTES")
    else:
        require(node.kind == "directory" and source.raw is None and node.bytes is node.sha256 is None,
            "ORIGINAL_DIRECTORY_NODE")
    return node


def checked_child_archive(child, archive, recipient):
    state = _state(child)
    require(type(archive) is TailArchiveBinding and state.archive is archive and
        state.validation_return is not None and state.validation_completed is not None and
        state.validation_return.recipient is recipient, "ORIGINAL_TAIL_ARCHIVE_RECIPIENT")
    if state.archive_view is None:
        roots = dict((name, directory) for name, directory, _path, _pin in state.roots)
        payload = roots["tail-copied-evidence"]
        output = roots["tail-export-output"] if os.name == "nt" else _paths()["tail-export-output"]
        view = _track(TailArchiveView(child, archive, recipient, state.clock.clock.role,
            payload if os.name == "nt" else payload.path, output, state.root, state.members, state.map,
            state.lineage, _operation_caps(state, TailArchiveCaps), state.public_inputs))
        _VIEWS[id(view)] = view, child
        _set(state, archive_view=view)
    return _check_child_archive(state.archive_view)


def _archive_liveness(view):
    _pin(view)
    require(type(view) is TailArchiveView, "TAIL_ARCHIVE_VIEW_ONLY")
    state = _state(view.child)
    binding = _VIEWS.get(id(view))
    require(type(binding) is tuple and binding[0] is view and binding[1] is view.child and
        state.archive_view is view and state.archive is view.archive and state.members is view.members and
        state.map is view.map and state.root is view.payload_root and state.lineage is view.lineage and
        state.public_inputs is view.public_inputs and state.validation_return.recipient is view.recipient,
        "ORIGINAL_ARCHIVE_VIEW")
    _pin(view.archive)
    _pin(view.lineage)
    _operation_current(state, view.caps, state.export_completed)
    return view.caps


def _flat_nodes(view):
    require(type(view.members) is tuple and 0 < len(view.members) < CD.MAX_NODES, "FLAT_MEMBERS")
    for number, node in enumerate(view.members):
        _node_current(node, view.child)
        require(node.kind == "file" and node.relative == CD.member_name(number), "CONTIGUOUS_FLAT_MEMBERS")
    _node_current(view.payload_root, view.child)
    _node_current(view.map, view.child)
    require(view.payload_root.relative == "" and view.payload_root.kind == "directory" and
        view.map.relative == TD.MAP_NAME and view.map.kind == "file", "FLAT_ROOT_MAP")
    nodes = (view.payload_root, *view.members, view.map)
    require(len({CD.native_key(node.native) for node in nodes}) == len(nodes), "FLAT_NATIVE_ALIAS")
    public = TD.public_inputs(view.public_inputs)
    cut = public["cut"]
    require(cut["memberCount"] == len(view.members) + 1 and cut["totalBytes"] ==
        sum(node.bytes for node in view.members) + view.map.bytes and cut["mapSha256"] == view.map.sha256 and
        cut["mapBytes"] == view.map.bytes, "ACTUAL_FLAT_NODE_ACCOUNTING")


def _check_child_archive(view):
    _archive_liveness(view)
    _flat_nodes(view)
    return view


def checked_retired_child_validation(child):
    state = _state(child, retired=True)
    view = state.validation
    _pin(view)
    require(type(view) is TailValidationView and state.validation_return is not None and
        state.validation_completed.returned is state.validation_return and view.child is child, "RETIRED_VALIDATION")
    _operation_current(state, view.caps, state.validation_completed)
    return view


def check_retired_child_archive(view):
    _pin(view)
    require(type(view) is TailArchiveView, "RETIRED_TAIL_VIEW_ONLY")
    state = _state(view.child, retired=True)
    require(state.archive_view is view and state.backend_return is state.export_completed.returned and
        state.archive is view.archive and state.members is view.members and state.map is view.map and
        state.root is view.payload_root and state.lineage is view.lineage and state.public_inputs is view.public_inputs and
        state.validation_return.recipient is view.recipient, "RETIRED_ARCHIVE")
    _operation_current(state, view.caps, state.export_completed)
    _flat_nodes(view)
    return view


def _native_info(info):
    require(type(info) is native.windows.FileInfo, "WINDOWS_INFO_TYPE")
    return CD.native(("windows", *info.identity, info.is_directory, info.size, info.links, info.attributes,
        info.creation_100ns, info.modified_100ns, info.change_100ns, info.owner_sid, info.protected_dacl),
        directory=info.is_directory)


def _directory_native(directory):
    info = directory.verify()
    stamp = _native_info(info) if os.name == "nt" else CD.native(
        ("posix", *native.posix._stamp(os.stat(directory.path, follow_symlinks=False))), directory=True)
    require(stamp[1:3] == tuple(directory.identity), "DIRECTORY_NATIVE_JOIN")
    return stamp


def _read_path(owner, path, maximum, *, expected=None, stamp=None, directory_stamp=None):
    require(type(path) is type(ROOT) and path.is_absolute() and ".." not in path.parts, "FIXED_READ_PATH")
    directory = C._private(owner, path.parent)
    current_directory = _directory_native(directory)
    require(directory_stamp is None or current_directory == directory_stamp, "ORIGINAL_DIRECTORY_METADATA")
    reader = _open_file(owner, directory, path.name, maximum)
    current = _native_info(reader.reader.initial_info) if os.name == "nt" else CD.native(
        ("posix", *native.posix._stamp(os.fstat(reader.reader.fileno()))), directory=False)
    require(stamp is None or current == stamp, "ORIGINAL_FILE_METADATA")
    raw = _stream(reader, None if expected is None else TD.sha(expected), retain=True)
    after = _native_info(reader.reader.verify()) if os.name == "nt" else CD.native(
        ("posix", *native.posix._stamp(os.fstat(reader.reader.fileno()))), directory=False)
    require(current == after and (expected is None or raw == expected), "ACTUAL_READ_FULL_METADATA_BYTES")
    owner.close_one(reader.reader)
    _file_current(reader, closed=True)
    require(_directory_native(directory) == current_directory, "DIRECTORY_CHANGED_DURING_READ")
    owner.close_one(directory)
    return raw, current, current_directory


def _source_path(name):
    CD.relative(name)
    parent = C._paths("worker")[2]
    if name.startswith("seal/"):
        return parent / "productive-receiver" / name
    if name.startswith("before/"):
        return parent / "productive-receiver" / name
    return parent / "productive-final" / name


def _original_read_expectations(context, transport):
    """Join retained DATA, not owners; keep every historical source row intact.

    R reads context among279 originals, then writes authority-close separately.
    Only that literal root context read uses the genuine later writer-readback
    directory vector. No current-read field comparison is masked or weakened.
    The parent calls this before writing its actual transport, and the child
    calls it before reopening any declared original. Both still need real R/
    native custody; consistent DATA alone establishes neither.
    """
    _source_current()
    require(type(transport) is dict and set(transport) == set(INPUT_LIMITS), "EXACT_TRANSPORT_INPUTS")
    TD.hashes(context["filesSha256"], INPUT_LIMITS)
    TD.hashes(context["predecessors"], TD.PREDECESSOR_FIELDS)
    for name, maximum in INPUT_LIMITS.items():
        require(type(transport[name]) is bytes and 0 < len(transport[name]) <= maximum and
            TD.sha(transport[name]) == context["filesSha256"][name], "TRANSPORT_ORIGINAL_BYTES")
    index = TD.canonical(transport["source-index.json"])
    TD.fields(index, "schema scope files fileCount beforeIndexSha256 beforeAuthoritySha256 deadlineSha256 provenance exportSaveAuthority")
    require(index["schema"] == 1 and type(index["schema"]) is int and index["scope"] ==
        "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_R_ORIGINAL_READ_TRANSPORT_V1" and type(index["files"]) is list and
        type(index["fileCount"]) is int and len(index["files"]) == index["fileCount"] == 585 and index["exportSaveAuthority"] is False and
        index["provenance"] == "ACTUAL_R_RETURN_REFERENCES_NOT_RECONSTRUCTED_OWNERS", "TRANSPORT_SCOPE")
    require(index["beforeIndexSha256"] == TD.sha(transport["before-index.json"]) == context["predecessors"]["beforeIndexSha256"] and
        index["beforeAuthoritySha256"] == context["predecessors"]["beforeAuthoritySha256"] and
        index["deadlineSha256"] == TD.sha(transport["deadline.json"]) == context["predecessors"]["deadlineSha256"],
        "TRANSPORT_ORIGINAL_HASHES")
    deadline = RD.deadline(transport["deadline.json"])
    require(TD.encoded(deadline) == TD.encoded(context["deadline"]), "TRANSPORT_ORIGINAL_DEADLINE")
    before = RD.authority_index(transport["before-index.json"], edge="before")
    # _context already bound this original session to the actual fixed K path.
    # Derive its one BEFORE sibling textually; do not acquire native state here.
    require(type(context["session"]) is str, "BEFORE_FIXED_CONTEXT_PATH")
    private = Path(context["session"])
    require(private.is_absolute() and ".." not in private.parts and private.name == TD.DIRECTORY and
        private.parent.name == "productive-tail", "BEFORE_FIXED_CONTEXT_PATH")
    require(before["root"] == str(private.parent.parent / "productive-receiver" / "before" / "authority") and
        before["clock"] == deadline["clock"] and before["authorityCloseSha256"] == index["beforeAuthoritySha256"],
        "BEFORE_ORIGINAL_ROOT_CLOCK_HASH")
    writer = RD.writer_return(TD.canonical(transport["before-writer-close.json"]))
    require(TD.encoded(writer) == TD.encoded(before["closeWriterReturn"]) and
        RD.known_close(transport["before-readback-close.json"]) == before["originalReadbackClose"] and
        writer["closedNs"] == CD.integer(context["beforeClosedNs"], deadline["sealFirstNs"], deadline["sealEndNs"] - 1) and
        writer["closedNs"] <= CD.integer(context["parentFirstNs"], deadline["sealFirstNs"], deadline["sealEndNs"] - 1),
        "BEFORE_ORIGINAL_WRITER_CLOSE_FLOOR")
    historical = index["files"][305:]
    require(tuple(row["relative"] for row in historical) == tuple("before/authority/" + name for name in
        before["requiredFiles"]), "BEFORE_ORIGINAL280_ORDER")
    directories = {row["relative"]: tuple(row["readbackNative"]) for row in before["directories"]}
    for row, declared in zip(historical, before["files"]):
        TD.fields(row, "relative bytes sha256 maximum native directoryNative provenance")
        projection = {name: declared[name] for name in ("bytes", "sha256", "maximum", "native", "directoryNative", "provenance")}
        projection["relative"] = "before/authority/" + declared["relative"]
        require(TD.encoded(row) == TD.encoded(projection), "BEFORE_VERBATIM_HISTORICAL_ROW")
        parent = declared["relative"].rpartition("/")[0] or "."
        require(CD.native_key(tuple(declared["directoryNative"])) == CD.native_key(directories[parent]),
            "BEFORE_ORIGINAL_DIRECTORY_IDENTITY")
    named = {row["relative"]: row for row in before["files"]}
    require(tuple(name for name in named if "/" not in name) == ("authority-close.json", "context.json") and
        named["context.json"]["sha256"] == before["authorityContextSha256"] and
        TD.encoded(named["authority-close.json"]) == TD.encoded(writer["readback"]), "BEFORE_NAMED_ROOT_ORIGINALS")
    earlier = tuple(named["context.json"]["directoryNative"])
    later = tuple(named["authority-close.json"]["directoryNative"])
    inventory = directories["."]
    # Compare original epochs only. Preserve complete identity/privacy/stable
    # fields; POSIX directory size/mtime/ctime and Windows modified/change are
    # the insertion's evidenced differences, not exceptions on a current read.
    if later[0] == "posix":
        require(earlier[:6] == inventory[:6] == later[:6], "BEFORE_STABLE_ROOT_FIELDS")
    else:
        require(earlier[:8] == inventory[:8] == later[:8] and earlier[10:] == inventory[10:] == later[10:],
            "BEFORE_STABLE_ROOT_FIELDS")
    expected = tuple(later if row["relative"] == "before/authority/context.json" else tuple(row["directoryNative"])
        for row in index["files"])
    _source_current()
    return index, expected


def _input_values(parent):
    before = parent.before
    expected = tuple(name for name, _maximum in RD.FINAL_INPUTS)
    require(type(before.inputs) is tuple and len(before.inputs) == 305 and type(before.authority_files) is tuple and
        len(before.authority_files) == 280 and tuple(row[0] for row in before.inputs[:24]) == expected and
        before.inputs[24][0] == "seal/seal-pending.json", "ORIGINAL_R305_B280")
    rows = []
    for name, raw, maximum, stamp, directory_stamp, provenance in (*before.inputs,
            *(("before/authority/" + row[0], *row[1:]) for row in before.authority_files)):
        require(type(raw) is bytes and len(raw) <= maximum <= CD.LIMIT and
            provenance == "FRESH_RECEIVER_READ_NOT_ORIGINAL_PRODUCER_PIN", "SOURCE_ROW_ORIGIN")
        CD.native(stamp, directory=False)
        CD.native(directory_stamp, directory=True)
        rows.append({"relative": name, "bytes": len(raw), "sha256": TD.sha(raw), "maximum": maximum,
            "native": list(stamp), "directoryNative": list(directory_stamp), "provenance": provenance})
    require(len(rows) == len({row["relative"] for row in rows}) == 585, "SOURCE_INDEX_ROSTER")
    source = TD.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_R_ORIGINAL_READ_TRANSPORT_V1",
        "files": rows, "fileCount": 585, "beforeIndexSha256": TD.sha(before.authority_index_raw),
        "beforeAuthoritySha256": TD.sha(before.authority_raw), "deadlineSha256": TD.sha(before.deadline_raw),
        "provenance": "ACTUAL_R_RETURN_REFERENCES_NOT_RECONSTRUCTED_OWNERS", "exportSaveAuthority": False})
    require(tuple(name for name, raw in before.authority_close_originals) == ("input", "readback", "native", "writer"),
        "FOUR_ORIGINAL_RETURNED_CLOSE_BYTES")
    result = {"source-index.json": source, "before-index.json": before.authority_index_raw,
        **{"before-" + name + "-close.json": raw for name, raw in before.authority_close_originals},
        "deadline.json": before.deadline_raw}
    require(set(result) == set(INPUT_LIMITS), "EXACT_TRANSPORT_INPUTS")
    for name, maximum in INPUT_LIMITS.items():
        require(type(result[name]) is bytes and 0 < len(result[name]) <= maximum, "TRANSPORT_INPUT_BOUND")
    return result


def _command(context_hash, deadline, caps, minimum=None):
    CD.sha(context_hash)
    TD.caps(deadline, caps)
    result = [str(Path(sys.executable).resolve(strict=True)), "-I", "-B", "-S",
        str(SCRIPTS / "run-hosted-initial-recipient-productive-tail.py"), "_tail-child", "--context-sha256", context_hash,
        "--deadline-base64", base64.b64encode(TD.encoded(deadline, CD.PUBLIC_LIMIT)).decode("ascii")]
    if minimum is not None:
        result.extend(("--minimum-ns", str(CD.integer(minimum))))
    for (_name, flag), value in zip(CAP_FIELDS, caps):
        result.extend((flag, str(value)))
    return result


def _context(raw, deadline, caps, clock):
    value = TD.canonical(raw, CD.PUBLIC_LIMIT)
    TD.fields(value, TD.CONTEXT_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == CONTEXT_SCOPE and
        value["kind"] == "worker" and value["root"] == str(ROOT) and value["session"] == str(_paths()["tail-returned"]) and value["deadline"] == deadline and value["caps"] == dict(zip(TD.CAP_FIELDS, caps)) and
        value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False, "CONTEXT")
    CD.job(value["job"])
    TD.caps(deadline, caps)
    require(deadline["clock"] == O.clock_value(clock) and TD.sha(TD.encoded(value["originalProposal"])) ==
        deadline["originalProposalSha256"] and value["beforeClosedNs"] <= value["parentFirstNs"] == caps[0],
        "CONTEXT_ORIGINAL_FLOORS")
    CD.integer(value["beforeClosedNs"], deadline["sealFirstNs"], caps[0])
    CD.local(value["parentFirstLocal"])
    C._collect_service_job(value["originalServiceJob"])
    TD.hashes(value["predecessors"], TD.PREDECESSOR_FIELDS)
    TD.hashes(value["filesSha256"], INPUT_LIMITS)
    require(value["predecessors"]["deadlineSha256"] == TD.sha(TD.encoded(deadline, CD.PUBLIC_LIMIT)) and
        all(value["predecessors"][name] == deadline[name] for name in ("collectCloseSha256", "sealSha256")),
        "CONTEXT_PREDECESSORS")
    TD.fields(value["directories"], DIRECTORIES)
    pins = []
    for name, pin in value["directories"].items():
        if name == "tail-export-output" and clock.role != "windows-x64":
            require(pin is None, "ORIGINAL_ABSENT_POSIX_OUTPUT")
        else:
            pins.append(TD.identity(pin, clock.role))
    require(len(set(pins)) == len(pins), "CONTEXT_DIRECTORY_ALIAS")
    inherited = value["inheritedContext"]
    require(type(inherited) is dict and all(type(name) is str and type(item) is str for name, item in inherited.items()) and
        (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "CONTEXT_INHERITANCE")
    return value


def _start_fields(raw, context_raw, context, role):
    value = TD.canonical(raw)
    TD.fields(value, native.START_FIELDS)
    caps = tuple(context["caps"][name] for name in TD.CAP_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == START_SCOPE and
        value["contextSha256"] == TD.sha(context_raw) and value["argv"] == _command(TD.sha(context_raw), context["deadline"], caps) and
        value["cwd"] == str(ROOT) and value["role"] == role and value["job"] == context["job"] and
        value["state"] == context["session"] and value["home"] == str(Path(context["session"]) / "control-home") and
        value["exitCode"] is None and value["launchAttempted"] is False and value["scopeAttempted"] is False and
        value["retirement"] == "UNKNOWN" and tuple(CD.integer(value[name]) for name in TD.CAP_FIELDS) == caps,
        "START_ORIGINAL_BINDINGS")
    CD.job(value["invocation"])
    expected = native.processes.ownership_environment(context["inheritedContext"], context["job"], value["invocation"],
        value["state"], value["home"], allow_new_context=True)
    require(value["inheritedContext"] == {name: expected[name] for name in Q._CONTEXT}, "START_NATIVE_INHERITANCE")
    return value


def _read_original_inputs(owner, context, transport):
    index, directories = _original_read_expectations(context, transport)
    result, seen = [], set()
    for number, row in enumerate(index["files"]):
        TD.fields(row, "relative bytes sha256 maximum native directoryNative provenance")
        CD.relative(row["relative"])
        CD.sha(row["sha256"])
        require(row["relative"] not in seen and row["provenance"] == "FRESH_RECEIVER_READ_NOT_ORIGINAL_PRODUCER_PIN",
            "ORIGINAL_SOURCE_ROW")
        seen.add(row["relative"])
        if number < 24:
            require((row["relative"], row["maximum"]) == RD.FINAL_INPUTS[number], "FINAL24_ORDER")
        elif number == 24:
            require(row["relative"] == "seal/seal-pending.json", "SEAL_ROW")
        else:
            require(row["relative"].startswith("seal/authority/" if number < 305 else "before/authority/"), "AUTHORITY_ROW")
        maximum = CD.integer(row["maximum"], 1, CD.LIMIT)
        count = CD.integer(row["bytes"], 0, maximum)
        graph = N._history_graph(row)
        raw, stamp, directory = _read_path(owner, _source_path(row["relative"]), maximum,
            stamp=tuple(row["native"]), directory_stamp=directories[number])
        N._check_history(graph)
        require(len(raw) == count and TD.sha(raw) == row["sha256"], "ACTUAL_REOPEN_R_BYTES_HASH")
        result.append((row["relative"], raw, maximum, stamp, directory))
    final_rows = tuple((name, raw, maximum, stamp, directory,
        "FRESH_RECEIVER_READ_NOT_ORIGINAL_PRODUCER_PIN") for name, raw, maximum, stamp, directory in result[:24])
    RD.final_bundle({name: raw for name, raw, *_ in final_rows})
    return tuple(result)


def _new_file_owner(clock):
    return C._PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))


def _expected(state, relative, stamp, raw, owner, label, *, directory=False):
    origin = _track(_NodeOrigin(state.handle, _paths()["tail-copied-evidence"] / relative, raw, owner, label))
    node = _track(ExpectedNode(relative, "directory" if directory else "file", None if directory else len(raw),
        None if directory else TD.sha(raw), stamp, origin))
    _NODES[id(node)] = node
    return node


def _indexed_sources(owner, root, index, *, count):
    files, directories = index["files"], index["directories"]
    require(type(files) is list and len(files) == count and type(directories) is list and len(directories) == 58,
        "INDEXED_AUTHORITY_ROSTER")
    declared_files = tuple(row["relative"] for row in files)
    declared_dirs = tuple("" if row["relative"] == "." else row["relative"] for row in directories)
    require(len(set(declared_files)) == count and len(set(declared_dirs)) == 58 and "" in declared_dirs,
        "INDEXED_PATH_UNION")
    for name in (*declared_files, *declared_dirs):
        CD.relative(name, empty=True)
    for row, name in zip(directories, declared_dirs):
        path = root / name
        directory = C._private(owner, path)
        if row.get("identity") is not None:
            require(tuple(directory.identity) == tuple(row["identity"]), "INDEX_ORIGINAL_LOGICAL_DIRECTORY_PIN")
        prefix = name + "/" if name else ""
        wanted = tuple(sorted(item[len(prefix):] for item in (*declared_files, *declared_dirs)
            if item != name and item.startswith(prefix) and "/" not in item[len(prefix):]))
        _names(owner, directory, wanted)
        owner.close_one(directory)
    records = []
    for row in files:
        path = root / row["relative"]
        raw, stamp, directory = _read_path(owner, path, row["maximum"])
        require(len(raw) == row["bytes"] and TD.sha(raw) == row["sha256"], "INDEXED_ORIGINAL_BYTES")
        records.append((path, raw, stamp, directory, "ACTUAL_K_READ_OF_ORIGINAL_INDEX_DECLARATION"))
    return tuple(records)


def _process_record(raw):
    value = E.I.parse(raw, CD.LIMIT)
    TD.fields(value, "schema waitExitCode retired interruption")
    require(type(value["schema"]) is int and value["schema"] == 1 and type(value["waitExitCode"]) is int and
        value["waitExitCode"] == 0 and value["retired"] is True and value["interruption"] is None and
        (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode("ascii") == raw, "PROCESS_RECORD")


def _encryption_status(raw):
    require(type(raw) is bytes and len(raw) <= E.posix.MAX_DIAGNOSTIC_BYTES, "STATUS_BOUND")
    lines = raw.splitlines()
    require(sum(line.startswith(b"[GNUPG:] BEGIN_ENCRYPTION ") for line in lines) == 1 and
        lines.count(b"[GNUPG:] END_ENCRYPTION") == 1 and not any(line.startswith((b"[GNUPG:] FAILURE", b"[GNUPG:] ERROR"))
        for line in lines), "COMPLETE_ENCRYPTION_STATUS")


def _windows_write_readback(written, stamp, count):
    CD.native(stamp, directory=False)
    require(stamp[0] == "windows", "WINDOWS_DIAGNOSTIC_VECTOR")
    info = dict(zip(("is_directory", "size", "links", "attributes", "creation_100ns", "modified_100ns", "change_100ns",
        "owner_sid", "protected_dacl"), stamp[3:]))
    info["identity"] = list(stamp[1:3])
    TD.write_close_metadata("windows-x64", written, info, count)


def _final_diagnostics(state, owner, map_value, manifest):
    """New K observations only. Never snapshot/copy private scratch plaintext."""
    root = C._paths("worker")[2] / "productive-final" / "public-crypto"
    roots = [row for row in map_value["sourceDirectories"] if row["path"] == str(root)]
    require(len(roots) == 1, "FINAL_VALIDATION_ROOT_ORIGINAL")
    directory = C._private(owner, root)
    require(tuple(directory.identity) == tuple(roots[0]["native"][1:3]), "FINAL_PUBLIC_ROOT_IDENTITY")
    names = _list_names(owner, directory, 32)
    owner.close_one(directory)
    prior = {}
    for row in map_value["members"]:
        if row["sourceKind"] == "native-file":
            path = Path(row["source"])
            if path.is_relative_to(root):
                prior[path.relative_to(root).as_posix()] = row
    require("recipient.asc" in prior and "recipient.gpg" in prior, "FINAL_PUBLIC_KEYS_REQUIRED")
    prior_roots = {name.split("/")[0] for name in prior} | {"gnupg", "tmp"}
    require(prior_roots.issubset(names), "FINAL_STABLE_VALIDATION_ROOTS")
    windows = state.clock.clock.role == "windows-x64"
    extra = set(names) - prior_roots
    operations = tuple(sorted(name for name in extra if re.fullmatch(r"gpg-[0-9a-f]{32}" if windows else r"gpg-[a-z0-9_]+", name)))
    results = tuple(sorted(name for name in extra if re.fullmatch(r"encrypted-export-result-[0-9a-f]{32}\.json", name)))
    scratch = tuple(sorted(name for name in extra if re.fullmatch(r"export-[0-9a-f]{32}", name)))
    require(len(operations) == 2 and len(results) == len(scratch) == (1 if windows else 0) and
        extra == set((*operations, *results, *scratch)), "FINAL_PRODUCTIVE_DIAGNOSTIC_COMPLEMENT")
    for operation in sorted({name.split("/")[0] for name in prior if "/" in name} - {"gnupg", "tmp"}):
        d = C._private(owner, root / operation)
        expected = tuple(name.split("/", 1)[1] for name in prior if name.startswith(operation + "/"))
        require(all("/" not in name for name in expected), "FLAT_ORIGINAL_VALIDATION_OPERATION")
        _names(owner, d, expected)
        owner.close_one(d)
    observed, late, changes = [], [], []
    for name, row in sorted(prior.items()):
        if name.startswith(("gnupg/", "tmp/")):
            continue  # Current public-only complement below records changes/removals explicitly.
        raw, stamp, parent = _read_path(owner, root / name, row["maximum"], stamp=tuple(row["sourceNative"]))
        require(len(raw) == row["bytes"] and TD.sha(raw) == row["sha256"], "FINAL_UNCHANGED_VALIDATION_FILE")
    for home in ("gnupg", "tmp"):
        d = C._private(owner, root / home)
        entries = _list_names(owner, d, 32)
        require((not windows or not entries) and all("secret" not in name.casefold() and
            "private" not in name.casefold() and name.casefold() != "secring.gpg" for name in entries), "PUBLIC_ONLY_HOME")
        owner.close_one(d)
        current = set()
        for leaf in entries:
            name = home + "/" + leaf
            raw, stamp, parent = _read_path(owner, root / name, CD.LIMIT)
            late.append((root / name, raw, stamp, parent, "CURRENT_PUBLIC_HOME_COMPLEMENT_NOT_OLD_UNCHANGED_CLAIM"))
            current.add(name)
            old = prior.get(name)
            changes.append({"relative": name, "state": "ADDED" if old is None else
                "UNCHANGED" if old["sha256"] == TD.sha(raw) and old["sourceNative"] == list(stamp) else "CHANGED",
                "priorSha256": None if old is None else old["sha256"], "currentSha256": TD.sha(raw)})
        for name, row in prior.items():
            if name.startswith(home + "/") and name not in current:
                changes.append({"relative": name, "state": "REMOVED", "priorSha256": row["sha256"], "currentSha256": None})
    listing = encryption = None
    contents, metadata = {}, {}
    for operation in operations:
        d = C._private(owner, root / operation)
        leaves = _list_names(owner, d, 4)
        owner.close_one(d)
        listed = tuple(sorted(("stdout", "stderr") if windows else ("stdout", "stderr", "status", "process.json")))
        encrypted = tuple(sorted(("stderr",) if windows else ("stderr", "status", "process.json")))
        require(leaves in (listed, encrypted), "DIAGNOSTIC_OPERATION_ROSTER")
        if leaves == listed:
            require(listing is None, "ONE_LISTING")
            listing = operation
        else:
            require(encryption is None, "ONE_ENCRYPTION")
            encryption = operation
        for leaf in leaves:
            raw, stamp, parent = _read_path(owner, root / operation / leaf,
                CD.LIMIT if leaf == "process.json" else E.posix.MAX_DIAGNOSTIC_BYTES)
            observed.append((root / operation / leaf, raw, stamp, parent, "ACTUAL_FINAL_PRODUCTIVE_DIAGNOSTIC_READ"))
            contents[operation + "/" + leaf] = raw
            metadata[operation + "/" + leaf] = stamp
            if leaf == "process.json":
                _process_record(raw)
    require(listing is not None and encryption is not None and E.posix._key_identity(contents[listing + "/stdout"],
        manifest["recipient"]["fingerprint"]) == (manifest["recipient"]["encryptionFingerprint"],
        manifest["recipient"]["expiresAt"]), "FINAL_KEY_LISTING")
    _encryption_status(contents[encryption + ("/stderr" if windows else "/status")])
    derived = {"publicHomeChanges": changes, "scratch": "REMOVED_TRANSIENTS_NOT_RECREATED"}
    if windows:
        raw, stamp, parent = _read_path(owner, root / results[0], E.windows.MAX_RECORD_BYTES)
        value = TD.canonical(raw, E.windows.MAX_RECORD_BYTES)
        TD.fields(value, "schema operation scope result outerOwnerClose ownWriterClose ownReadback ordinaryResources "
            "priorResourceAccounting commands priorGuardReturns retirement")
        require(type(value["schema"]) is int and value["schema"] == 1 and value["operation"] == "encrypted-export" and
            value["scope"] == "INITIAL_RECIPIENT_PRODUCTIVE_WINDOWS_PRIOR_FACTS_V1" and value["result"] ==
            "PENDING_RESULT_WRITER_READBACK_AND_FUNCTION_RETURN" and value["outerOwnerClose"] == value["ownWriterClose"] ==
            "PENDING" and value["ownReadback"] == "NOT_STARTED" and value["retirement"] ==
            "PRIOR_OWNED_RESOURCES_KNOWN_NOT_OUTER_CLOSE" and type(value["ordinaryResources"]) is list and
            value["ordinaryResources"] and type(value["commands"]) is list and len(value["commands"]) == 2,
            "PRODUCTIVE_PRIOR_FACTS_NOT_READY_ALIAS")
        for row in value["ordinaryResources"]:
            TD.fields(row, "label coverage normalCloseReturned")
            require(type(row["label"]) is str and 0 < len(row["label"]) <= 256 and
                row["coverage"] in ("DIRECT", "TRANSITIVE_ORIGINAL_AGGREGATE_RETURN") and
                row["normalCloseReturned"] is True, "PRIOR_RESOURCE_CLOSE")
        accounting = TD.fields(value["priorResourceAccounting"], "directOriginalCloseCalls directOriginalOwners "
            "transitivelyClosedOriginalOwners uniqueOriginalPinReferences originalPinReleaseContributions "
            "borrowedRootsNotClosedHere memoryHelpersRetainedWithoutIndependentCloseClaim pinReleaseMeaning timingCapacityQualification")
        for name in ("directOriginalCloseCalls", "directOriginalOwners", "transitivelyClosedOriginalOwners", "uniqueOriginalPinReferences",
                "originalPinReleaseContributions", "borrowedRootsNotClosedHere", "memoryHelpersRetainedWithoutIndependentCloseClaim"):
            CD.integer(accounting[name], 0, 1000000)
        require(accounting["directOriginalCloseCalls"] == len(value["ordinaryResources"]) and
            0 < accounting["directOriginalOwners"] <= accounting["directOriginalCloseCalls"] and
            accounting["uniqueOriginalPinReferences"] <= accounting["originalPinReleaseContributions"] and
            accounting["borrowedRootsNotClosedHere"] == 3 and accounting["pinReleaseMeaning"] ==
            "OWNER_CONTRIBUTION_NOT_EARLY_BORROWED_RAW_HANDLE_CLOSE" and
            accounting["timingCapacityQualification"] == "NOT_PERFORMED", "PRIOR_ACCOUNTING_DATA_NOT_KNOWN_OUTER_CLOSE")
        CD.integer(value["priorGuardReturns"], 1, 1000000000)
        for number, command in enumerate(value["commands"]):
            TD.fields(command, "argv invocation waitExitCode retirement outputs ownership")
            require(type(command["waitExitCode"]) is int and command["waitExitCode"] == 0 and
                command["retirement"] == "KNOWN", "ORIGINAL_COMMAND_COMPLETE")
            CD.job(command["invocation"])
            argv = command["argv"]
            recipient = state.validation_return.recipient
            base = [str(recipient.executable), "--no-options", "--homedir", str(root / "gnupg"), "--batch", "--no-tty",
                "--no-autostart", "--no-auto-key-retrieve", "--no-auto-key-import", "--auto-key-locate", "clear", "--disable-dirmngr",
                "--pinentry-mode", "error", "--no-random-seed-file", "--no-default-keyring", "--keyring", "./recipient.gpg",
                "--lock-never", "--no-auto-check-trustdb", "--trust-model", "always"]
            expected = base + (["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint", "--list-keys"] if number == 0 else
                ["--status-fd", "2", "--cipher-algo", "AES256", "--compress-algo", "none", "--no-encrypt-to", "--recipient",
                    manifest["recipient"]["encryptionFingerprint"] + "!", "--output", "-", "--encrypt", str(root / scratch[0] / "evidence.tar.gz")])
            require(argv == expected, "ORIGINAL_PRODUCTIVE_COMMAND_ARGV")
            TD.fields(command["outputs"], "stdout stderr")
            for label in (("stdout", "stderr") if number == 0 else ("stderr",)):
                info = dict(command["outputs"][label])
                raw_output = contents[(listing if number == 0 else encryption) + "/" + label]
                require(info.pop("sha256", None) == TD.sha(raw_output), "ORIGINAL_COMMAND_OUTPUT_HASH")
                stamp_output = metadata[(listing if number == 0 else encryption) + "/" + label]
                _windows_write_readback(info, stamp_output, len(raw_output))
            launches = command["ownership"].get("launches")
            require(type(launches) is list and len(launches) == 1, "ONE_ORIGINAL_COMMAND_LAUNCH")
            leaders = [row for row in command["ownership"].get("startedIdentities", []) if row.get("pid") == launches[0].get("pid")]
            require(len(leaders) == 1, "ORIGINAL_COMMAND_LEADER")
            native.native_record(command["ownership"], {"role": "windows-x64",
                "job": TD.canonical(dict(state.raws)["returned/context.json"])["job"], "invocation": command["invocation"],
                "cwd": str(root)}, leaders[0], argv)
        d = C._private(owner, root / scratch[0])
        _names(owner, d, ("evidence.tar.gz", "evidence.tar.gz.gpg"))
        plaintext = _open_file(owner, d, "evidence.tar.gz", TD.MAX_ZIP_BYTES)
        _file_current(plaintext)
        owner.close_one(plaintext.reader)  # Metadata-only: never read or call this an EOF/copy/cleanup observation.
        _file_current(plaintext, closed=True)
        cipher = _open_file(owner, d, "evidence.tar.gz.gpg", TD.MAX_ZIP_BYTES)
        require(cipher.count == manifest["artifact"]["size"] and
            _stream(cipher, manifest["artifact"]["sha256"], close=True)[0] == manifest["artifact"]["sha256"],
            "ORIGINAL_PRIVATE_PUBLIC_CIPHERTEXT_JOIN")
        # The command stdout sink is the private scratch ciphertext. It has
        # no fabricated retained plaintext/EOF/hash record of its own.
        TD.write_close_metadata("windows-x64", value["commands"][1]["outputs"]["stdout"],
            TD.canonical(cipher.raw), cipher.count)
        derived["scratch"] = {"observation": "METADATA_ONLY_PLAINTEXT_NOT_EOF_NOT_COPY_NOT_DELETE",
            "plaintextMetadata": TD.canonical(plaintext.raw), "ciphertextMetadata": TD.canonical(cipher.raw),
            "ciphertextSha256": manifest["artifact"]["sha256"]}
        owner.close_one(d)
        observed.append((root / results[0], raw, stamp, parent, "ACTUAL_PRODUCTIVE_PENDING_PRIOR_FACTS_RECORD"))
    require(len(observed) == (4 if windows else 7) and (not late if windows else len(late) <= 64), "EXACT_DIAGNOSTIC_COUNTS")
    return tuple(observed), tuple(late), derived


def _supplier_summary(state):
    recipient = state.validation_return.recipient
    return TD.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_ACTUAL_RECIPIENT_RETURN_V1",
        "contextSha256": TD.sha(state.context_raw), "startSha256": TD.sha(state.start_raw),
        "invocation": TD.canonical(state.start_raw)["invocation"], "clock": O.clock_value(state.clock.clock),
        "validationStartedNs": state.validation.caps.first.nanoseconds, "validationReturnedNs": state.validation_completed.raw,
        "recipient": {"fingerprint": recipient.fingerprint, "encryptionFingerprint": recipient.encryption_fingerprint,
            "keySha256": recipient.key_sha256, "expiresAt": recipient.expires_at},
        "supplierReturned": True, "outerChild": "STILL_LIVE", "exportSaveAuthority": False})


def _freeze_tail(state, originals, transport):
    """Ten ordered actual source groups, one separately closed flat map."""
    owner = _new_file_owner(state.clock)
    copied_owner = _new_file_owner(state.clock)
    map_owner = None
    try:
        context = TD.canonical(state.context_raw, CD.PUBLIC_LIMIT)
        by_name = {name: (raw, maximum, stamp, directory) for name, raw, maximum, stamp, directory in originals}
        final_raw = by_name["export-output/manifest.json"][0]
        final = CD.public_manifest(final_raw)
        groups = {name: [] for name in TD.GROUPS}
        def original(group, name):
            raw, maximum, stamp, directory = by_name[name]
            path = _source_path(name)
            actual, current, parent = _read_path(owner, path, maximum, expected=raw, stamp=stamp, directory_stamp=directory)
            groups[group].append((path, actual, current, parent, "ACTUAL_K_REOPEN_OF_R_READ_NOT_PRODUCER_PIN"))
        for name in (*("returned/crypto-service/" + name for name in TD.PHASE_NAMES if name != "start.json"),
                "returned/crypto-child-result.json", *("returned/" + name for name in CD.LATER_FILES)):
            original(TD.GROUPS[0], name)
        post_raw = by_name["returned/productive-post-authority-index.json"][0]
        post_index = CD.authority_index(post_raw, post=True)
        groups[TD.GROUPS[1]].extend(_indexed_sources(owner, C._paths("worker")[2] /
            "productive-final" / "authority-post-export", post_index, count=279))
        copy_raw = by_name["payload/copy-index.json"][0]
        copy = CD.final_index(copy_raw)
        require(final["copy"]["index"]["sha256"] == TD.sha(copy_raw), "FINAL_COPY_INDEX_HASH")
        map_ref = copy["groups"][29]["map"]
        map_path = C._paths("worker")[2] / "productive-final" / "payload" / "map-recipient-validation.json"
        map_raw, stamp, directory = _read_path(owner, map_path, CD.LIMIT)
        require(len(map_raw) == map_ref["bytes"] and TD.sha(map_raw) == map_ref["sha256"], "ORIGINAL_FINAL_VALIDATION_MAP")
        old_map = CD.map_record(map_raw, 30)
        groups[TD.GROUPS[2]].append((map_path, map_raw, stamp, directory, "EXACT_FINAL_ENCRYPTED_MAP_REFERENCE_COPY"))
        original(TD.GROUPS[2], "payload/copy-index.json")
        diagnostic, late, derived = _final_diagnostics(state, owner, old_map, final)
        groups[TD.GROUPS[3]].extend(diagnostic)
        groups[TD.GROUPS[4]].extend(late)
        for name in by_name:
            if name.startswith("seal/authority/"):
                original(TD.GROUPS[5], name)
            elif name.startswith("before/authority/"):
                original(TD.GROUPS[7], name)
        original(TD.GROUPS[6], "seal/seal-pending.json")
        for name in ("before-index.json", "before-input-close.json", "before-readback-close.json",
                "before-native-close.json", "before-writer-close.json"):
            path = _paths()["tail-returned"] / name
            raw, stamp, directory = _read_path(owner, path, INPUT_LIMITS[name], expected=transport[name])
            groups[TD.GROUPS[8]].append((path, raw, stamp, directory, "ACTUAL_NEW_TRANSPORT_OF_R_RETURNED_BYTES_NOT_OLD_DISK"))
        work = C._private(owner, _paths()["tail-public-crypto"])
        snapshot, inventory = C._recipient_inventory(owner, work, dict(state.raws)["returned/recipient-public.asc"])
        for row in inventory["files"]:
            path = work.path / row["relative"]
            raw, stamp, directory = _read_path(owner, path, row["maximum"])
            require(len(raw) == row["bytes"] and TD.sha(raw) == row["sha256"], "CURRENT_VALIDATION_SOURCE_BYTES")
            groups[TD.GROUPS[9]].append((path, raw, stamp, directory, "ACTUAL_SAME_E_RECIPIENT_VALIDATION_NATIVE_FILE"))
        C._snapshot_current(owner, snapshot, rescan=True)
        for path, raw in ((_paths()["tail-returned"] / "context.json", state.context_raw),
                (_paths()[_phase_directory("start.json")] / "start.json", state.start_raw)):
            actual, stamp, directory = _read_path(owner, path, CD.LIMIT, expected=raw)
            groups[TD.GROUPS[9]].append((path, actual, stamp, directory, "ACTUAL_K_DISK_CONTEXT_OR_NATIVE_START"))
        groups[TD.GROUPS[9]].append((None, _supplier_summary(state), None, None,
            "ACTUAL_E_SUPPLIER_SUMMARY_EMBEDDED_NOT_DISK_ORIGINAL"))
        source_close = owner.finish()
        _closed_files(owner)
        # Separate data writer; same work cap, no copied byte obtains a new allowance.
        destination = C._private(copied_owner, _paths()["tail-copied-evidence"])
        _names(copied_owner, destination, ())
        rows, nodes, native_paths, totals = [], [], {}, {}
        for group in TD.GROUPS:
            totals[group] = {"memberCount": len(groups[group]), "totalBytes": sum(len(row[1]) for row in groups[group])}
            for path, raw, source_native, parent_native, provenance in groups[group]:
                name = CD.member_name(len(rows))
                require(final["copy"]["plaintextBytes"] + sum(row["bytes"] for row in rows) + len(raw) <= CD.MAX_BYTES,
                    "COPY_SHARED_BYTES")
                if source_native is not None:
                    key = CD.native_key(source_native)
                    require(key not in native_paths or native_paths[key] == path, "SOURCE_CROSS_PATH_ALIAS")
                    native_paths[key] = path
                written = _write_bytes(copied_owner, destination, name, raw)
                actual, stamp, _directory = _read_path(copied_owner, destination.path / name, max(1, len(raw)), expected=raw)
                require(CD.native_key(stamp) not in native_paths, "COPY_SOURCE_NATIVE_ALIAS")
                native_paths[CD.native_key(stamp)] = destination.path / name
                node = _expected(state, name, stamp, actual, copied_owner, "ACTUAL_K_COPY_READBACK")
                nodes.append(node)
                rows.append({"ordinal": len(rows), "group": group, "member": name,
                    "source": "actual-recipient-summary" if path is None else str(path),
                    "sourceKind": "embedded-not-disk" if path is None else "native-file",
                    "sourceNative": None if source_native is None else list(source_native),
                    "sourceDirectoryNative": None if parent_native is None else list(parent_native),
                    "bytes": len(raw), "sha256": TD.sha(raw), "destinationNative": list(stamp),
                    "writer": written, "provenance": provenance})
        _names(copied_owner, destination, tuple(node.relative for node in nodes))
        copied_close = copied_owner.finish()
        _closed_files(copied_owner)
        map_raw = TD.encoded({"schema": 1, "scope": TD.MAP_SCOPE, "groups": totals, "members": rows,
            "dataFiles": len(rows), "dataBytes": sum(row["bytes"] for row in rows),
            "contextSha256": TD.sha(state.context_raw), "predecessors": context["predecessors"],
            "sourceOwnerClose": TD.canonical(source_close), "copyOwnerClose": TD.canonical(copied_close),
            "derivedNotDeliveredOriginals": derived, "ownHash": "EXCLUDED_NO_SELF_REFERENCE",
            "writerReturn": CD.PENDING, "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"})
        cut = {"mapName": TD.MAP_NAME, "mapSha256": TD.sha(map_raw), "mapBytes": len(map_raw),
            "memberCount": len(rows) + 1, "totalBytes": sum(row["bytes"] for row in rows) + len(map_raw), "groups": totals}
        TD.cut(cut, TD.final_reference(final_raw), state.clock.clock.role == "windows-x64")
        map_owner = _new_file_owner(state.clock)
        target = C._private(map_owner, _paths()["tail-copied-evidence"])
        _write_bytes(map_owner, target, TD.MAP_NAME, map_raw)
        actual, stamp, _directory = _read_path(map_owner, target.path / TD.MAP_NAME, CD.LIMIT, expected=map_raw)
        mapped = _expected(state, TD.MAP_NAME, stamp, actual, map_owner, "ACTUAL_SEPARATE_MAP_WRITER_READBACK")
        root = _expected(state, "", _directory_native(target), None, map_owner, "ACTUAL_FINAL_FLAT_ROOT", directory=True)
        _names(map_owner, target, tuple([node.relative for node in nodes] + [TD.MAP_NAME]))
        map_owner.finish()
        _closed_files(map_owner)
        lineage = _track(_Lineage(state.handle, state.context_raw, state.start_raw, state.metadata_close, copied_close, map_raw))
        archive = _track(TailArchiveBinding())
        _set(state, root=root, members=tuple(nodes), map=mapped, lineage=lineage, archive=archive,
            public_inputs=TD.manifest_inputs(final_raw, context["predecessors"], cut))
        return archive
    except BaseException as error:
        for actual in (owner, copied_owner, map_owner):
            if actual is not None and not actual.finished:
                actual.remember(error)
                if not actual.owner.unknown:
                    try:
                        actual.finish()
                    except BaseException:
                        pass
        raise _fail(state, error)


@dataclass(frozen=True, repr=False)
class _NativeReturn:
    parent: object
    owner: object
    context: bytes
    child: bytes
    records: tuple
    phase: tuple
    close: bytes
    closed_ns: int  # AFTER child domain, captures AND the actual native parent owner close.


def _native_phase_data(context_raw, records, child_raw, clock):
    """Closed DATA checks, called only for an actual registered K native return."""
    context = _context(context_raw, clock.deadline_data, tuple(TD.canonical(context_raw, 65536)["caps"][name]
        for name, _flag in CAP_FIELDS), clock.clock)
    require(type(records) is tuple and len(records) == len(TD.PHASE_NAMES) and
        {name for name, _raw in records} == set(TD.PHASE_NAMES), "NATIVE_ORIGINAL_PHASE_ROSTER")
    data = dict(records)
    start = _start_fields(data["start.json"], context_raw, context, clock.clock.role)
    terminal, birth = TD.canonical(data["result.json"]), TD.canonical(data["native-start.json"])
    TD.fields(terminal, native.TERMINAL_FIELDS)
    TD.fields(birth, {"ownership", "leader", "preparerIdentity", "observedNs"})
    changed = {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}
    require(O.encoded({name: value for name, value in terminal.items() if name in start and name not in changed}) ==
        O.encoded({name: value for name, value in start.items() if name not in changed}) and
        type(terminal["exitCode"]) is int and terminal["exitCode"] == 0 and terminal["launchAttempted"] is True and
        terminal["scopeAttempted"] is True and terminal["scopeCloseAttempted"] is True and terminal["scopeClosed"] is True and
        terminal["retirement"] == "KNOWN" and terminal["survivors"] == [] and terminal["errors"] == [] and
        data["stderr.log"] == b"" and terminal["baselineSha256"] == O.digest(data["baseline.json"]) and
        terminal["nativeStartSha256"] == O.digest(data["native-start.json"]) and terminal["leader"] == birth["leader"],
        "NATIVE_ACTUAL_TERMINAL")
    minimum = O.integer(terminal["launchMinimumNs"], start["startedNs"])
    command = _command(O.digest(context_raw), context["deadline"], tuple(context["caps"][name] for name, _flag in CAP_FIELDS), minimum)
    require(terminal["launchArgv"] == command, "NATIVE_ACTUAL_COMMAND")
    native.native_record(terminal["ownership"], start, terminal["leader"], command)
    native.native_record(birth["ownership"], start, terminal["leader"], command, terminal=False)
    require(birth["ownership"]["launches"] == terminal["ownership"]["launches"] and
        native.closed_lifetime(birth["preparerIdentity"], clock.clock.role) ==
        native.closed_lifetime(terminal["preparerIdentity"], clock.clock.role) and
        birth["preparerIdentity"]["pid"] != terminal["leader"]["pid"], "NATIVE_ORIGINAL_LIFETIME")
    baseline = native.baseline_record(data["baseline.json"], clock.clock.role)
    if baseline["baseline"] is not None:
        leader = native.lifetime(terminal["leader"], clock.clock.role)
        require(list(leader[:4] if clock.clock.role.startswith("macos-") else leader) not in baseline["baseline"],
            "NATIVE_PREEXISTING_LEADER")
    require(O.encoded(terminal["captureOutcomes"]) == O.encoded({name: {key: True for key in
        ("synced", "verified", "closeAttempted", "closed", "readback")} for name in ("stdout", "stderr")}) and
        O.encoded(terminal["captures"]) == O.encoded({name: {"sha256": O.digest(data[name + ".log"]),
            "bytes": len(data[name + ".log"])} for name in ("stdout", "stderr")}), "NATIVE_CAPTURE_READBACKS")
    child, ack = _child_data(child_raw, context_raw, data["start.json"], minimum, clock.clock), TD.canonical(data["stdout.log"])
    TD.fields(ack, {"schema", "scope", "invocation", "terminalSha256", "clock", "closedNs", "ownerCloseSha256",
        "metadataResourceCount", "operativeResourceCount"})
    require(type(ack["schema"]) is int and ack["schema"] == 1 and ack["scope"] == ACK_SCOPE and
        ack["invocation"] == start["invocation"] and ack["terminalSha256"] == O.digest(child_raw) and
        O.encoded(ack["clock"]) == O.encoded(O.clock_value(clock.clock)) and type(ack["metadataResourceCount"]) is int and
        ack["metadataResourceCount"] == child["metadataResourceCount"] and
        type(ack["operativeResourceCount"]) is int and 0 < ack["operativeResourceCount"] <= CD.MAX_NODES,
        "NATIVE_CHILD_CLOSED_ACK")
    C.digest(ack["ownerCloseSha256"])
    require(minimum <= O.integer(birth["observedNs"]) <= O.integer(terminal["completedNs"]) < start["workEndNs"] and
        minimum <= child["beganNs"] <= child["exportedNs"] <= child["beforeOwnerCloseNs"] <=
        O.integer(ack["closedNs"]) <= terminal["completedNs"] <= O.integer(terminal["finalizedNs"]) < start["finalEndNs"],
        "NATIVE_ORIGINAL_TIME_CHAIN")
    return context, child, data



def _checked_native(parent, result):
    saved = _NATIVE.get(id(result))
    require(type(result) is _NativeReturn and type(saved) is tuple and saved[0] is result, "ORIGINAL_NATIVE_RETURN")
    _pin(result)
    owner, anchor, pins, graphs = saved[1:]
    parent.current()
    require(parent._anchor()[2]["native"] is owner and result.owner is owner and result.parent is parent and
        owner._anchor() is anchor and owner.known() is anchor and owner.fence is parent.clock and
        owner.first is parent.clock.reading, "NATIVE_ORIGINAL_OWNER_CLOSE")
    for directory, path, identity in pins:
        require(directory.path is path and tuple(directory.identity) == identity and
            C._collect_directory_closed(directory, parent.clock.clock.role), "NATIVE_ORIGINAL_CLOSED_ROOT")
    for graph in graphs:
        N._check_history(graph)
    context, child, records = _native_phase_data(result.context, result.records, result.child, parent.clock)
    require(result.phase == tuple(context["caps"][name] for name in TD.CAP_FIELDS) and
        TD.canonical(records["result.json"])["finalizedNs"] <= result.closed_ns < result.phase[2], "NATIVE_RETURN_FLOOR")
    return owner, context, child, records, TD.canonical(result.close)


def _prelaunch_budget(parent, caps):
    local = CD.local(time.monotonic())
    now = parent.now(limit=caps[1])
    # Productive validation's inclusive60 ALREADY contains Windows finish30
    # (_operation_caps). The legacy supplier's additional30 is not used here.
    require(min(parent.clock.current().binding[6] - local, (caps[1] - now) / NS) > 60, "VALIDATION_CANNOT_FIT")


def _native_tail(parent):
    saved = parent.currency()
    require(saved[2]["phase"] == "BEFORE_RETURNED" and saved[2]["native"] is None, "NATIVE_ONCE")
    saved[2]["phase"] = "NATIVE"
    clock, caps, inputs = parent.clock, parent.clock.caps, _input_values(parent)
    _prelaunch_budget(parent, caps)
    owner = scope = out = err = child = None
    failure = None
    native_known = False
    try:
        owner = _TailNativeOwner(clock.deadline(900, final=True, limit=caps[2]), clock,
            first=clock.reading, cancelled=clock.cancelled)
        saved[2]["native"] = owner
        owner_anchor = owner._anchor()
        outer = owner.open(C._paths("worker")[2])
        root = owner.child(outer, "productive-tail", create=True)
        private = owner.child(root, TD.DIRECTORY, create=True)
        directories = {"root": root, "tail-returned": private}
        for name in PRIVATE_DIRECTORIES:
            directories[name] = owner.child(private, name, create=True)
        for name in ("tail-public-crypto", "tail-copied-evidence"):
            directories[name] = owner.child(root, name, create=True)
        if clock.clock.role == "windows-x64":
            directories["tail-export-output"] = owner.child(root, "tail-export-output", create=True)
        pins = tuple((directory, directory.path, tuple(directory.identity)) for directory in (outer, *directories.values()))
        require(len({pin[2] for pin in pins}) == len(pins), "SETUP_DIRECTORY_ALIAS")
        before_raws = {name: raw for name, raw, *_rest in parent.before.inputs[:24]}
        _final_context, final_inputs, manifest, _index, _custody, _transfer, _post, _collect = RD.final_bundle(before_raws)
        context = {"schema": 1, "scope": CONTEXT_SCOPE, "kind": "worker", "root": str(ROOT),
            "session": str(private.path), "job": uuid.uuid4().hex, "observed": final_inputs["observed"],
            "deadline": clock.deadline_data, "originalProposal": final_inputs["originalProposal"],
            "caps": dict(zip(TD.CAP_FIELDS, caps)), "parentFirstNs": clock.first,
            "parentFirstLocal": clock.first_local, "beforeClosedNs": parent._binding[3],
            "originalServiceJob": final_inputs["history"]["serviceJob"],
            "predecessors": {"collectCloseSha256": clock.deadline_data["collectCloseSha256"],
                "sealSha256": clock.deadline_data["sealSha256"], "beforeAuthoritySha256": TD.sha(parent.before.authority_raw),
                "beforeIndexSha256": TD.sha(parent.before.authority_index_raw), "deadlineSha256": TD.sha(parent.before.deadline_raw)},
            "filesSha256": {name: TD.sha(raw) for name, raw in inputs.items()},
            "directories": {name: list(directories[name].identity) if name in directories else None for name in DIRECTORIES},
            "inheritedContext": Q._inherited_context(), "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        context_raw = TD.encoded(context, CD.PUBLIC_LIMIT)
        _context(context_raw, clock.deadline_data, caps, clock.clock)
        _original_read_expectations(context, inputs)
        parent.current()  # Still the SAME registered live R return, before transport writes.
        input_graph = N._history_graph(context, inputs, tuple(pin[1] for pin in pins))
        for name, raw in (*inputs.items(), ("context.json", context_raw)):
            require(owner.write(private, name, raw) == raw, "CONTEXT_ACTUAL_READBACK")
            parent.now(limit=caps[1])
            N._check_history(input_graph)
        capture_end = min(owner.local_end, clock.deadline(900, final=True, limit=caps[2]))
        invocation = uuid.uuid4().hex
        environment = native.processes.ownership_environment(native.recipient_environment(private.path), context["job"],
            invocation, str(private.path), str(private.path / "control-home"), allow_new_context=True)
        require(not any(name in environment for name in CREDENTIAL_NAMES), "NATIVE_CHILD_TOKEN_FREE")
        start = {"schema": 1, "scope": START_SCOPE, "contextSha256": O.digest(context_raw),
            "argv": _command(O.digest(context_raw), clock.deadline_data, caps), "cwd": str(ROOT), "role": clock.clock.role,
            "job": context["job"], "invocation": invocation, "state": str(private.path),
            "home": str(private.path / "control-home"), "inheritedContext": {name: environment[name] for name in Q._CONTEXT},
            **dict(zip((name for name, _flag in CAP_FIELDS), caps)), "exitCode": None,
            "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"}
        start_raw = O.encoded(start)
        _start_fields(start_raw, context_raw, context, clock.clock.role)
        service = directories[_phase_directory("start.json")]
        require(owner.write(service, "start.json", start_raw) == start_raw, "NATIVE_START_READBACK")
        row = dict(start)
        row["captureOutcomes"] = {name: {"synced": False, "verified": False, "closeAttempted": False,
            "closed": False, "readback": False} for name in ("stdout", "stderr")}
        original_inputs = N._history_graph(context, inputs, start, environment)
        resource_start = len(owner_anchor.rows)
        try:
            out = owner.acquire("stdout", lambda: service.create_file("stdout.log", max_bytes=native.ACK_LIMIT, deadline=capture_end))
            err = owner.acquire("stderr", lambda: service.create_file("stderr.log", max_bytes=native.STDERR_LIMIT, deadline=capture_end))
            row["scopeAttempted"] = True
            scope = owner.acquire("native-scope", lambda: native.processes.make_scope(context["job"], invocation,
                str(private.path), str(private.path / "control-home")))
            row["preparerIdentity"] = native.preparer_identity(scope, clock.clock.role)
            baseline_raw = owner.write(service, "baseline.json", {"role": clock.clock.role,
                "baseline": sorted(scope.baseline) if hasattr(scope, "baseline") else None,
                "kernelJob": clock.clock.role == "windows-x64"})
            row["baselineSha256"] = O.digest(baseline_raw)
            _prelaunch_budget(parent, caps)
            N._check_history(original_inputs)
            row["launchMinimumNs"] = parent.now(limit=caps[1])
            command = _command(O.digest(context_raw), clock.deadline_data, caps, row["launchMinimumNs"])
            row["launchArgv"], row["launchAttempted"] = command, True
            child = scope.spawn(command, str(ROOT), environment, stdout=out, stderr=err)
            require(child.stdout is None and child.stderr is None, "NATIVE_ACTUAL_PRIVATE_SINKS")
            birth = scope.description()
            birth_graph = N._history_graph(birth)
            leaders = [value for value in birth.get("startedIdentities", []) if value.get("pid") == child.pid]
            require(len(leaders) == 1, "NATIVE_ACTUAL_BIRTH")
            row["leader"] = dict(leaders[0])
            native.lifetime(row["leader"], clock.clock.role)
            birth_directory = directories[_phase_directory("native-start.json")]
            birth_raw = owner.write(birth_directory, "native-start.json", {"ownership": birth, "leader": row["leader"],
                "preparerIdentity": row["preparerIdentity"], "observedNs": parent.now(limit=caps[1])})
            row["nativeStartSha256"] = O.digest(birth_raw)
            N._check_history(birth_graph)
            while True:
                parent.currency()
                parent.now(limit=caps[1])
                N._check_history(original_inputs)
                owner.check()
                for stream in (out, err):
                    stream.observe_live_output() if clock.clock.role == "windows-x64" else stream.verify()
                code = child.poll()
                if code is not None:
                    row["exitCode"] = code
                observed = parent.now(limit=caps[1])
                if code is not None:
                    row["completedNs"] = observed
                    require(type(code) is int and code == 0 and not scope.discover(), "NATIVE_CHILD_OR_DESCENDANT_FAILED")
                    break
                scope.discover()
                native.time.sleep(.025)
        except BaseException as error:
            owner.error("k-native", error)
        finally:
            # Pin-return even when acquire's later guard failed, never infer a
            # missing local variable means the genuine native scope is retired.
            allocated = owner_anchor.rows[resource_start:]
            scope = scope if scope is not None else next((resource for _r, label, resource, _a, _c in allocated
                if label == "native-scope"), None)
            out = out if out is not None else next((resource for _r, label, resource, _a, _c in allocated if label == "stdout"), None)
            err = err if err is not None else next((resource for _r, label, resource, _a, _c in allocated if label == "stderr"), None)
            if scope is not None:
                try:
                    try:
                        clock.now(final=True, limit=caps[2])
                    except BaseException as error:
                        owner.error("k-native-final-clock", error)
                    remaining = max(0, capture_end - time.monotonic())
                    grace = min(5, remaining)
                    row["survivors"] = scope.drain(grace=grace, kill_wait=min(5, max(0, remaining - grace)), deadline=capture_end)
                    require(row["survivors"] == [], "NATIVE_SURVIVORS")
                    row["ownership"] = scope.description()
                    require(row["ownership"].get("discoveryErrors") == [] and native.preparer_identity(scope, clock.clock.role) ==
                        row["preparerIdentity"], "NATIVE_DRAIN_IDENTITY")
                    native.posix._deadline(capture_end)
                    native_known = True
                except BaseException as error:
                    owner.error("k-native-drain", error, unknown=True)
                owner.close_one(scope)
                original = next(resource for resource, _label, actual, _a, _c in owner_anchor.rows if actual is scope)
                row["scopeCloseAttempted"], row["scopeClosed"] = original["attempted"], original["closed"]
                if original["closed"] is not True:
                    native_known = False
                    owner.error("k-native-scope", O.OriginError("INITIAL_K_NATIVE_SCOPE_UNKNOWN"), unknown=True)
            elif row["scopeAttempted"]:
                owner.error("k-native-allocation", O.OriginError("INITIAL_K_NATIVE_SCOPE_UNKNOWN"), unknown=True)
            else:
                native_known = True
            if native_known and not owner_anchor.unknown:
                for name, stream in (("stdout", out), ("stderr", err)):
                    if stream is None:
                        continue
                    outcome = row["captureOutcomes"][name]
                    try:
                        native.posix._deadline(capture_end)
                        stream.sync()
                        outcome["synced"] = True
                        stream.verify()
                        outcome["verified"] = True
                    except BaseException as error:
                        owner.error("k-native-capture", error)
                    owner.close_one(stream)
                    original = next(resource for resource, _label, actual, _a, _c in owner_anchor.rows if actual is stream)
                    outcome.update(closeAttempted=original["attempted"], closed=original["closed"])
            if row["launchAttempted"] and owner_anchor.failure is not None:
                owner.error("k-native-child-return", owner_anchor.failure, unknown=True)
        if owner_anchor.failure is not None:
            raise owner_anchor.failure
        require(native_known and not owner_anchor.unknown, "NATIVE_CLOSE_NOT_KNOWN")
        row["finalizedNs"] = parent.now(final=True, limit=caps[2])
        captures = {}
        for name, maximum in (("stdout", native.ACK_LIMIT), ("stderr", native.STDERR_LIMIT)):
            captures[name] = owner.read(service, name + ".log", maximum, final=True)
            row["captureOutcomes"][name]["readback"] = True
            parent.now(final=True, limit=caps[2])
        require(captures["stderr"] == b"", "NATIVE_STDERR_NOT_EMPTY")
        row.update(retirement="KNOWN", errors=[], captures={name: {"sha256": O.digest(raw), "bytes": len(raw)}
            for name, raw in captures.items()})
        terminal_raw = owner.write(service, "result.json", row, final=True)
        child_raw = owner.read(private, "tail-child-result.json", final=True)
        records = tuple(sorted({"start.json": start_raw, "baseline.json": baseline_raw, "native-start.json": birth_raw,
            "result.json": terminal_raw, "stdout.log": captures["stdout"], "stderr.log": captures["stderr"]}.items()))
        _native_phase_data(context_raw, records, child_raw, clock)
        N._check_history(input_graph)
        N._check_history(original_inputs)
        parent.currency()
        parent.now(final=True, limit=caps[2])
        _phase_roster("service", native._initializer_names(owner, directories["service"]))
        _phase_roster("native-birth", native._initializer_names(owner, directories["native-birth"]))
        require(native._initializer_names(owner, private) == PRIVATE_INPUT_NAMES and
            native._initializer_names(owner, root) == tuple(sorted((TD.DIRECTORY, "tail-public-crypto",
                "tail-copied-evidence", "tail-export-output"))), "NATIVE_FINAL_ROSTER")
        owner.freeze()
        owner.close()
        closed = owner.known()
        closed_ns = parent.now(final=True, limit=caps[2])
        close_raw = TD.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_PRODUCTIVE_TAIL_NATIVE_KNOWN_CLOSE_V1",
            "resources": [{"ordinal": number, "label": label, "closeAttempted": attempted, "closed": ended}
                for number, (_row, label, _resource, attempted, ended) in enumerate(closed.rows)],
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False})
        result = _track(_NativeReturn(parent, owner, context_raw, child_raw, records, caps, close_raw, closed_ns))
        _NATIVE[id(result)] = result, owner, owner_anchor, pins, (input_graph, original_inputs)
        _checked_native(parent, result)
        saved[2]["phase"] = "NATIVE_CLOSED"
        return result
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("productive-tail-native", error)
            failure = owner._anchor().failure
    finally:
        if owner is not None and not owner.closed:
            try:
                owner.close()
            except BaseException as error:
                if failure is None:
                    failure = error
    raise parent.fail(failure)


def _child_data(raw, context_raw, start_raw, minimum, clock):
    value = TD.canonical(raw)
    TD.fields(value, "schema scope contextSha256 startSha256 invocation clock bootDigest launchMinimumNs beganNs "
        "metadataLastNs metadataCloseSha256 metadataResourceCount validationStartedNs validationReturnedNs exportedNs "
        "beforeOwnerCloseNs recipientReturnSha256 recipient cut outputIdentity manifest retirement finalPrivateOriginals "
        "testAcceptance productiveAuthority cacheAuthority exportSaveAuthority budgetAcceptance")
    context = TD.canonical(context_raw, CD.PUBLIC_LIMIT)
    start = _start_fields(start_raw, context_raw, context, clock.role)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == CHILD_SCOPE and
        value["contextSha256"] == TD.sha(context_raw) and value["startSha256"] == TD.sha(start_raw) and
        value["invocation"] == start["invocation"] and value["clock"] == O.clock_value(clock) and
        value["bootDigest"] == context["deadline"]["originalBootDigest"] and value["launchMinimumNs"] == minimum and
        value["retirement"] == "PENDING_CHILD_CLOSE" and value["finalPrivateOriginals"] == TD.EXCLUDED and
        value["testAcceptance"] == "NOT_PERFORMED" and value["productiveAuthority"] is value["cacheAuthority"] is
        value["exportSaveAuthority"] is False and value["budgetAcceptance"] == "NOT_ADMITTED", "CHILD_PENDING_RECORD")
    TD.fields(value["manifest"], "bytes sha256 base64")
    encoded = value["manifest"]["base64"]
    require(type(encoded) is str and 0 < len(encoded) <= 4 * ((CD.PUBLIC_LIMIT + 2) // 3), "MANIFEST_TRANSPORT_BOUND")
    manifest_raw = base64.b64decode(encoded, validate=True)
    manifest = TD.public_manifest(manifest_raw)
    require(base64.b64encode(manifest_raw).decode("ascii") == encoded and len(manifest_raw) == value["manifest"]["bytes"] and
        TD.sha(manifest_raw) == value["manifest"]["sha256"] and value["cut"] == manifest["cut"] and
        value["recipient"] == manifest["recipient"] and manifest["predecessors"] == context["predecessors"], "ACTUAL_CHILD_MANIFEST")
    CD.sha(value["metadataCloseSha256"])
    CD.sha(value["recipientReturnSha256"])
    CD.integer(value["metadataResourceCount"], 1, CD.MAX_NODES)
    TD.identity(value["outputIdentity"], clock.role)
    previous = CD.integer(minimum)
    for name in ("beganNs", "metadataLastNs", "validationStartedNs", "validationReturnedNs", "exportedNs", "beforeOwnerCloseNs"):
        previous = CD.integer(value[name], previous, context["caps"]["workEndNs"] - 1)
    return value


def _check_receiver_data(context, originals, transport):
    raw_map = {name: raw for name, raw, *_ in originals}
    final_raws = {name: raw_map[name] for name, _maximum in RD.FINAL_INPUTS}
    _context_, final, manifest, _index, _custody, _transfer, _post, _collect = RD.final_bundle(final_raws)
    require(final["observed"] == context["observed"] and final["originalProposal"] == context["originalProposal"] and
        manifest["source"] == context["deadline"]["source"] and TD.sha(final_raws["export-output/manifest.json"]) ==
        context["deadline"]["manifestSha256"], "ACTUAL_FINAL_ORIGINALS_JOIN")
    inputs = tuple((name, raw, maximum, stamp, directory, "FRESH_RECEIVER_READ_NOT_ORIGINAL_PRODUCER_PIN")
        for name, raw, maximum, stamp, directory in originals[:305])
    before_rows = tuple((name.removeprefix("before/authority/"), raw, maximum, stamp, directory,
        "FRESH_RECEIVER_READ_NOT_ORIGINAL_PRODUCER_PIN") for name, raw, maximum, stamp, directory in originals[305:])
    index = RD.authority_index(transport["before-index.json"], edge="before")
    matches = [(name, raw) for name, raw, *_ in before_rows if TD.sha(raw) == context["predecessors"]["beforeAuthoritySha256"]]
    require(len(matches) == 1, "ONE_ACTUAL_BEFORE_AUTHORITY_CLOSE")
    closes = tuple((name, transport["before-" + name + "-close.json"]) for name in ("input", "readback", "native", "writer"))
    RD.authority_bundle(matches[0][1], transport["before-index.json"], before_rows, closes, edge="before", input_rows=inputs)
    seal = RD.seal_record(raw_map["seal/seal-pending.json"], final_raws)
    seal_rows = tuple((name.removeprefix("seal/authority/"), raw, maximum, stamp, directory,
        "FRESH_RECEIVER_READ_NOT_ORIGINAL_PRODUCER_PIN") for name, raw, maximum, stamp, directory in originals[25:305])
    RD.authority_bundle(TD.encoded(seal["authority"]), TD.encoded(seal["authorityIndex"]), seal_rows,
        tuple((name, TD.encoded(seal["authorityCloseOriginals"][name])) for name in ("input", "readback", "native", "writer")),
        edge="seal", input_rows=inputs[:24])
    require(TD.sha(raw_map["seal/seal-pending.json"]) == context["predecessors"]["sealSha256"] and
        index["closeWriterReturn"]["closedNs"] == context["beforeClosedNs"], "ORIGINAL_RECEIVER_PREDECESSORS")


def _e_functions():
    names = ("validate_initial_productive_tail_recipient", "checked_productive_tail_validation_return",
        "export_initial_productive_tail_encrypted", "checked_productive_tail_backend_return",
        "checked_retired_productive_tail_validation_return", "checked_retired_productive_tail_backend_return")
    result = tuple(getattr(E, name) for name in names)
    require(all(callable(value) for value in result), "EXACT_E_TAIL_FACADE_REQUIRED")
    return names, result


def tail_child(context_sha256, minimum_ns, deadline, caps, cancelled):
    """Only fixed native argv can reach the genuine child-local owner graph."""
    metadata = outer = state = clock = None
    try:
        local = CD.local(time.monotonic())
        first = O.clocks.observe()
        boot = continuity.boot_digest(first.clock.role)
        clock = _Clock(first, local, boot, cancelled, deadline, caps)
        require(caps[0] <= CD.integer(minimum_ns) <= first.nanoseconds < caps[1], "CHILD_ORIGINAL_LAUNCH_MINIMUM")
        metadata = _new_file_owner(clock)
        context_raw, _stamp, _dir = _read_path(metadata, _paths()["tail-returned"] / "context.json", CD.PUBLIC_LIMIT)
        require(TD.sha(context_raw) == CD.sha(context_sha256), "NATIVE_CONTEXT_HASH")
        context = _context(context_raw, deadline, caps, first.clock)
        start_raw, _stamp, _dir = _read_path(metadata, _paths()[_phase_directory("start.json")] / "start.json", CD.LIMIT)
        start = _start_fields(start_raw, context_raw, context, first.clock.role)
        inherited = Q._inherited_context()
        require(inherited == start["inheritedContext"] and set(inherited) == set(Q._CONTEXT), "CHILD_ACTUAL_NATIVE_DOMAIN")
        domain = native.processes.ownership_domains(inherited[native.processes.CHAIN_ENV], inherited[native.processes.DOMAINS_ENV])[-1]
        require(domain == {"id": start["invocation"], "job": start["job"], "state": start["state"], "home": start["home"]},
            "CHILD_LAST_NATIVE_DOMAIN")
        transport = {}
        for name, maximum in INPUT_LIMITS.items():
            raw, _stamp, _dir = _read_path(metadata, _paths()["tail-returned"] / name, maximum)
            require(TD.sha(raw) == context["filesSha256"][name], "ACTUAL_TRANSPORT_HASH")
            transport[name] = raw
        require(RD.deadline(transport["deadline.json"]) == deadline, "DEADLINE_ARGV_REJOIN")
        originals = _read_original_inputs(metadata, context, transport)
        _check_receiver_data(context, originals, transport)
        observed, primary, event = N.host_context(context["observed"]["firstUseAt"])
        require(observed == context["observed"] and observed["role"] == first.clock.role and
            primary == C._paths("worker")[0]["P"] and event == dict((name, raw) for name, raw, *_ in originals)["returned/event.json"],
            "CURRENT_REAL_HOST_EVENT")
        metadata_close = metadata.finish()
        _closed_files(metadata)
        metadata_last = clock.now()
        outer = _new_file_owner(clock)
        roots = []
        for name, path in _paths().items():
            if name == "tail-export-output" and os.name != "nt":
                require(not os.path.lexists(path), "NEW_POSIX_OUTPUT_ONLY")
                continue
            directory = C._private(outer, path)
            require(tuple(directory.identity) == tuple(context["directories"][name]), "ACTUAL_CHILD_ROOT_IDENTITY")
            roots.append((name, directory, directory.path, tuple(directory.identity)))
        directories = dict((name, directory) for name, directory, _path, _pin in roots)
        for name in ("tail-public-crypto", "tail-copied-evidence", "control-home", "temporary"):
            _names(outer, directories[name], ())
        child = _track(TailChild())
        source = _track(TailChildSourceBinding(context["job"], TD.encoded(context["observed"]), TD.sha(event),
            TD.sha(context_raw), TD.sha(start_raw)))
        state = _track(_State(child, clock, context_raw, start_raw, tuple((name, raw) for name, raw, *_ in originals),
            metadata_close, metadata, outer, tuple(roots), source))
        _CHILDREN[id(child)] = state
        api_names, apis = _e_functions()
        def suppliers():
            require(all(getattr(E, name) is original for name, original in zip(api_names, apis)) and
                R.P is P and P.C is C and P.N is N and P.B is B and P.O is O, "ORIGINAL_FACADE_SUPPLIERS")
            _pin(state)
        suppliers()
        returned = apis[0](child)
        _track(returned)  # FIRST operation after the real E return.
        _set(state, validation_return=returned)
        suppliers()
        require(apis[1](returned, child) is returned and returned.view is state.validation, "ACTUAL_E_VALIDATION_RETURN")
        completion = _track(_Completion(returned, clock.now(limit=state.validation.caps.operationFinishEndNs),
            CD.local(time.monotonic())))
        _set(state, validation_completed=completion)
        _operation_current(state, state.validation.caps, completion)
        archive = _freeze_tail(state, originals, transport)
        suppliers()
        result = apis[2](child, archive, returned.recipient)
        _track(result)
        _set(state, backend_return=result)
        suppliers()
        require(apis[3](result, state.archive_view) is result and result.view is state.archive_view, "ACTUAL_E_TAIL_BACKEND_RETURN")
        completed = _track(_Completion(result, clock.now(limit=state.archive_view.caps.operationFinishEndNs),
            CD.local(time.monotonic())))
        _set(state, export_completed=completed)
        _operation_current(state, state.archive_view.caps, completed)
        manifest_raw = result.manifest_raw
        final_raw = dict(state.raws)["export-output/manifest.json"]
        _final, manifest = TD.join_manifests(final_raw, manifest_raw)
        if os.name == "nt":
            output = directories["tail-export-output"]
        else:
            output = C._private(outer, _paths()["tail-export-output"])
            roots.append(("tail-export-output", output, output.path, tuple(output.identity)))
            _set(state, roots=tuple(roots))
        _names(outer, output, ("evidence.tar.gz.gpg", "manifest.json"))
        require(_small(outer, output, "manifest.json", CD.PUBLIC_LIMIT) == manifest_raw, "ACTUAL_TAIL_MANIFEST_READBACK")
        cipher = _open_file(outer, output, "evidence.tar.gz.gpg", TD.MAX_ZIP_BYTES)
        require(cipher.count == manifest["artifact"]["size"] and _stream(cipher, manifest["artifact"]["sha256"], close=True)[0] ==
            manifest["artifact"]["sha256"], "ACTUAL_TAIL_CIPHERTEXT_HASH_EOF_CLOSE")
        summary_raw = _supplier_summary(state)
        before_closed = clock.now()
        result_raw = TD.encoded({"schema": 1, "scope": CHILD_SCOPE, "contextSha256": TD.sha(context_raw),
            "startSha256": TD.sha(start_raw), "invocation": start["invocation"], "clock": O.clock_value(clock.clock),
            "bootDigest": boot, "launchMinimumNs": minimum_ns, "beganNs": clock.first, "metadataLastNs": metadata_last,
            "metadataCloseSha256": TD.sha(metadata_close), "metadataResourceCount": len(metadata.rows),
            "validationStartedNs": state.validation.caps.first.nanoseconds, "validationReturnedNs": completion.raw,
            "exportedNs": completed.raw, "beforeOwnerCloseNs": before_closed, "recipientReturnSha256": TD.sha(summary_raw),
            "recipient": manifest["recipient"], "cut": manifest["cut"], "outputIdentity": list(output.identity),
            "manifest": {"bytes": len(manifest_raw), "sha256": TD.sha(manifest_raw),
                "base64": base64.b64encode(manifest_raw).decode("ascii")}, "retirement": "PENDING_CHILD_CLOSE",
            "finalPrivateOriginals": manifest["finalPrivateOriginals"], "testAcceptance": "NOT_PERFORMED",
            "productiveAuthority": False, "cacheAuthority": False, "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"})
        _child_data(result_raw, context_raw, start_raw, minimum_ns, clock.clock)
        _write_bytes(outer, directories["tail-returned"], "tail-child-result.json", result_raw)
        suppliers()
        apis[1](returned, child)
        apis[3](result, state.archive_view)
        closed_raw = outer.finish()
        _set(state, closed=closed_raw)
        _closed_files(outer)
        suppliers()
        require(apis[4](returned, child) is returned and apis[5](result, state.archive_view) is result,
            "ACTUAL_RETIRED_E_RETURNS")
        closed = clock.now(minimum=before_closed, limit=clock.work)
        return {"schema": 1, "scope": ACK_SCOPE, "invocation": start["invocation"],
            "terminalSha256": TD.sha(result_raw), "clock": O.clock_value(clock.clock), "closedNs": closed,
            "ownerCloseSha256": TD.sha(closed_raw), "metadataResourceCount": len(metadata.rows),
            "operativeResourceCount": len(outer.rows)}, clock, clock.work
    except BaseException as error:
        failure = error if state is None else _fail(state, error)
        for owner in (metadata, outer):
            if owner is not None and not owner.finished:
                owner.remember(failure)
                if not owner.owner.unknown:
                    try:
                        owner.finish()
                    except BaseException:
                        pass
        raise failure if clock is None else clock.fail(failure)


@dataclass(frozen=True, repr=False)
class _Carrier:
    parent: object
    native: object
    raw: bytes
    close: bytes


def _root_names(*, upload=False):
    return (TD.DIRECTORY, "tail-public-crypto", "tail-copied-evidence", "tail-export-output",
        *(("upload-output",) if upload else ()))


def _copy_carrier(parent, returned):
    """Four literal copies AFTER actual child/native parent retirement."""
    checked = _checked_native(parent, returned)
    _native_parent, context, child, _records, native_close = checked
    parent.currency()
    clock, owner = parent.clock, None
    failure = None
    try:
        require(parent._anchor()[2]["phase"] == "NATIVE_CLOSED" and parent._anchor()[2]["carrier"] is None,
            "CARRIER_ONCE_AFTER_NATIVE")
        owner = C._PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
        parent._anchor()[2]["carrier"] = owner  # Actual return before the next callback.
        custody = C._private(owner, _paths()["root"])
        p0 = C._private(owner, C._paths("worker")[2] / "productive-final" / "export-output")
        tail = C._private(owner, custody.path / "tail-export-output")
        end = owner.guard()
        target = owner.acquire("directory", lambda: custody.create_directory("upload-output", deadline=end))
        _names(owner, custody, _root_names(upload=True))
        directories = (custody, p0, tail, target)
        pins = tuple((directory, directory.path, tuple(directory.identity)) for directory in directories)
        require(len({pin[2] for pin in pins}) == 4 and tuple(custody.identity) == tuple(context["directories"]["root"]) and
            tuple(tail.identity) == tuple(child["outputIdentity"]), "CARRIER_ORIGINAL_DIRECTORIES")
        final_row = next(row for row in parent.before.inputs if row[0] == "export-output/manifest.json")
        require(_directory_native(p0) == final_row[4], "CARRIER_ORIGINAL_R_OUTPUT_METADATA")
        final_raw = final_row[1]
        tail_manifest_raw = base64.b64decode(child["manifest"]["base64"], validate=True)
        manifest, tail_manifest = TD.join_manifests(final_raw, tail_manifest_raw)
        members = [
            {"name": TD.CARRIER_MEMBERS[0], "bytes": manifest["artifact"]["size"], "sha256": manifest["artifact"]["sha256"]},
            {"name": TD.CARRIER_MEMBERS[1], "bytes": len(final_raw), "sha256": O.digest(final_raw)},
            {"name": TD.CARRIER_MEMBERS[2], "bytes": tail_manifest["artifact"]["size"], "sha256": tail_manifest["artifact"]["sha256"]},
            {"name": TD.CARRIER_MEMBERS[3], "bytes": len(tail_manifest_raw), "sha256": O.digest(tail_manifest_raw)},
        ]
        total, zipped = TD.carrier_bytes(members)  # Includes552 fixed ZIP bytes; refuse BEFORE copying/Create.
        _names(owner, p0, ("evidence.tar.gz.gpg", "manifest.json"))
        _names(owner, tail, ("evidence.tar.gz.gpg", "manifest.json"))
        _names(owner, target, ())
        observations = []
        for number, row in enumerate(members):
            parent.currency()
            source = p0 if number < 2 else tail
            leaf = "manifest.json" if number % 2 else "evidence.tar.gz.gpg"
            reader = _open_file(owner, source, leaf, CD.PUBLIC_LIMIT if number % 2 else TD.MAX_ZIP_BYTES)
            require(reader.count == row["bytes"] and reader.ordinal == 4 + number * 3, "CARRIER_SOURCE_SIZE_OR_ORDINAL")
            end = owner.guard()
            writer = owner.acquire("writer", lambda: target.create_file(row["name"], max_bytes=row["bytes"], deadline=end))
            writer_ordinal = len(owner.rows) - 1
            checksum, write_raw = _stream(reader, row["sha256"], writer=writer, close=True)
            require(checksum == row["sha256"] and owner.rows[writer_ordinal][3:] == (True, True), "CARRIER_WRITER_CLOSE")
            readback = _open_file(owner, target, row["name"], row["bytes"])
            require(_stream(readback, row["sha256"], close=True)[0] == row["sha256"], "CARRIER_READBACK_HASH")
            require(readback.count == row["bytes"], "CARRIER_READBACK_SIZE")
            observations.append({**row, "sourceRelative": TD.SOURCE_NAMES[number], "sourceDirectoryIdentity": list(source.identity),
                "sourceRead": {"metadata": C.canonical(reader.raw), "readerOrdinal": reader.ordinal},
                "write": {"metadata": C.canonical(write_raw), "writerOrdinal": writer_ordinal},
                "readback": {"metadata": C.canonical(readback.raw), "readerOrdinal": readback.ordinal},
                "metadataPolicy": TD.write_close_metadata(clock.clock.role, C.canonical(write_raw),
                    C.canonical(readback.raw), row["bytes"])})
            _file_current(reader, closed=True)
            _file_current(readback, closed=True)
        _names(owner, target, TD.CARRIER_MEMBERS)
        _names(owner, p0, ("evidence.tar.gz.gpg", "manifest.json"))
        _names(owner, tail, ("evidence.tar.gz.gpg", "manifest.json"))
        _names(owner, custody, _root_names(upload=True))
        for directory, path, pin in pins:
            directory.verify()
            require(directory.path is path and tuple(directory.identity) == pin, "CARRIER_PIN_CHANGED")
        graph = N._history_graph(observations, members, pins[0][1], pins[1][1], pins[2][1], pins[3][1])
        parent.currency()
        closed_raw = owner.finish()
        closed_ns = parent.now()
        _closed_files(owner)
        N._check_history(graph)
        _checked_native(parent, returned)
        value = {"schema": 1, "scope": TD.CARRIER_SCOPE, **_identity_data(context), "predecessors": context["predecessors"],
            "manifests": {"finalSha256": members[1]["sha256"], "tailSha256": members[3]["sha256"]},
            "cutMapSha256": child["cut"]["mapSha256"], "carrier": {"relative": "upload-output", "identity": list(pins[3][2])},
            "files": observations, "totalBytes": total, "zipBytes": zipped,
            "nativeClose": {"contextSha256": O.digest(returned.context), "resultSha256": O.digest(returned.child),
                "ackSha256": O.digest(dict(returned.records)["stdout.log"]),
                "phaseSha256": {name: O.digest(raw) for name, raw in returned.records}},
            "ownerCloses": {"native": native_close, "carrier": C._collect_file_close(closed_raw)},
            "times": {"beforeClosedNs": context["beforeClosedNs"], "tailChildClosedNs": returned.closed_ns,
                "carrierClosedNs": closed_ns}, "writerReturn": "PENDING_SEPARATE_RECORD_WRITER_CLOSE",
            **_nonacceptance()}
        raw = TD.encode_close(value)
        result = _track(_Carrier(parent, returned, raw, closed_raw))
        _CARRIERS[id(result)] = (result, result.__dict__, parent, returned, raw, closed_raw, owner, owner._anchor(), pins,
            N._history_graph(result.__dict__, tuple(pin[1] for pin in pins)), graph)
        _checked_carrier(result)
        parent._anchor()[2]["phase"] = "CARRIER_CLOSED"
        return result
    except BaseException as error:
        failure = parent.fail(error if owner is None else owner.remember(error))
    finally:
        if owner is not None and not owner.finished and not owner.owner.unknown:
            try:
                owner.finish()
            except BaseException as error:
                if failure is None:
                    failure = parent.fail(error)
    raise failure


def _nonacceptance():
    return {"originalStepOutcome": "NOT_OBSERVED", "upload": "NOT_PERFORMED", "testAcceptance": "NOT_PERFORMED",
        "productiveAuthority": False, "cacheAuthority": False, "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}


def _identity_data(context):
    step = C._collect_service_job(context["originalServiceJob"])
    observed = context["observed"]
    return {"kind": context["kind"], "selection": observed["inputs"]["selection"], "source": observed["source"],
        "github": {"repository": C.I.REPOSITORY, "runId": observed["github"]["runId"],
            "runAttempt": observed["github"]["runAttempt"], "job": observed["github"]["job"],
            "jobId": step[0], "role": observed["role"]}, "originalProposal": context["originalProposal"], "deadline": context["deadline"]}


def _checked_carrier(result):
    saved = _CARRIERS.get(id(result))
    require(type(result) is _Carrier and type(saved) is tuple and saved[0] is result,
        "CARRIER_ORIGINAL_RETURN")
    try:
        _pin(result)
        require(result.__dict__ is saved[1] and result.parent is saved[2] and result.native is saved[3] and
            result.raw == saved[4] and result.close == saved[5], "CARRIER_RETURN_REPLACED")
        parent, native_result, _raw, _close, owner, anchor, pins, graph, observed_graph = saved[2:]
        parent.current()
        require(owner._anchor() is anchor and parent._anchor()[2]["carrier"] is owner, "CARRIER_ORIGINAL_OWNER")
        _closed_files(owner)
        for directory, path, pin in pins:
            require(directory.path is path and tuple(directory.identity) == pin and
                C._collect_directory_closed(directory, parent.clock.clock.role), "CARRIER_CLOSED_PIN_CHANGED")
        N._check_history(graph)
        N._check_history(observed_graph)
        _checked_native(parent, native_result)
        return parent, TD.parse_close(result.raw)
    except BaseException as error:
        raise saved[2].fail(error)


_PENDING = {}
PRIVATE_INPUT_NAMES = tuple(sorted((*INPUT_LIMITS, "context.json", "tail-child-result.json",
    *PRIVATE_DIRECTORIES)))
PRIVATE_CLOSED_NAMES = tuple(sorted((*PRIVATE_INPUT_NAMES, TD.PRIVATE_CARRIER_CLOSE, TD.FILE)))


@dataclass(frozen=True, repr=False)
class _Pending:
    parent: object
    carrier: object
    raw: bytes
    close: bytes


def _retain_pending(carrier):
    """R file first, then pending; both actual writer/readback owners close."""
    parent, close = _checked_carrier(carrier)
    parent.currency()
    owner = None
    failure = None
    try:
        clock = parent.clock
        require(parent._anchor()[2]["phase"] == "CARRIER_CLOSED" and parent._anchor()[2]["pending"] is None,
            "PENDING_WRITER_ONCE_AFTER_CARRIER")
        owner = C._PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
        parent._anchor()[2]["pending"] = owner
        directory = C._private(owner, _paths()["tail-returned"])
        path, identity = directory.path, tuple(directory.identity)
        native_result = carrier.native
        _native_owner, context, _child, _records, _native_close = _checked_native(parent, native_result)
        require(identity == tuple(context["directories"]["tail-returned"]), "PENDING_ORIGINAL_PRIVATE_DIRECTORY")
        _names(owner, directory, PRIVATE_INPUT_NAMES)
        carrier_write = _write_bytes(owner, directory, TD.PRIVATE_CARRIER_CLOSE, carrier.raw)
        parent.currency()
        prepared = parent.now()
        before = parent.before
        originals = {name: raw for name, raw, *_ in before.inputs}
        value = {"schema": 1, "scope": TD.PENDING_SCOPE, **_identity_data(context),
            "originals": {"eventSha256": O.digest(originals["returned/event.json"]), "policySha256": O.digest(originals["returned/candidate-policy.json"]),
                "matchSha256": O.digest(originals["returned/original-match.json"])}, "predecessors": close["predecessors"],
            "manifests": close["manifests"], "cutMapSha256": close["cutMapSha256"],
            "members": [{name: row[name] for name in ("name", "bytes", "sha256")} for row in close["files"]],
            "totalBytes": close["totalBytes"], "zipBytes": close["zipBytes"],
            "knownCloses": {"beforeIndexSha256": O.digest(before.authority_index_raw),
                "beforeWriterCloseSha256": O.digest(dict(before.authority_close_originals)["writer"]), "tailChildCloseSha256": O.digest(native_result.close),
                "carrierCloseSha256": O.digest(carrier.raw)},
            "times": {**close["times"], "pendingPreparedNs": prepared}, "writerReturn": "PENDING_OWNER_CLOSE",
            **_nonacceptance()}
        raw = TD.encode_pending(value)
        graph = N._history_graph(value, carrier_write, path)
        pending_write = _write_bytes(owner, directory, TD.FILE, raw)
        write_graph = N._history_graph(pending_write)
        require(_small(owner, directory, TD.PRIVATE_CARRIER_CLOSE, TD.LIMIT, checksum=O.digest(carrier.raw)) == carrier.raw and
            _small(owner, directory, TD.FILE, CD.PUBLIC_LIMIT, checksum=O.digest(raw)) == raw, "PENDING_BOTH_RECORDS_READBACK")
        _names(owner, directory, PRIVATE_CLOSED_NAMES)
        parent.currency()
        N._check_history(graph)
        N._check_history(write_graph)
        closed_raw = owner.finish()
        closed_ns = parent.now()
        _closed_files(owner)
        _checked_carrier(carrier)
        result = _track(_Pending(parent, carrier, raw, closed_raw))
        _PENDING[id(result)] = (result, result.__dict__, parent, carrier, raw, closed_raw, owner, owner._anchor(),
            directory, path, identity, closed_ns, N._history_graph(result.__dict__, value, pending_write, carrier_write, path))
        parent._anchor()[2]["phase"] = "PENDING_CLOSED"
        return result
    except BaseException as error:
        failure = error if owner is None else owner.remember(error)
    finally:
        if owner is not None and not owner.finished and not owner.owner.unknown:
            try:
                owner.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
    raise parent.fail(failure)


def _checked_pending(result):
    saved = _PENDING.get(id(result))
    require(type(result) is _Pending and type(saved) is tuple and saved[0] is result, "PENDING_ORIGINAL_RESULT")
    _result, dictionary, parent, carrier, raw, closed, owner, original, directory, path, identity, closed_ns, graph = saved
    try:
        _pin(result)
        require(result.__dict__ is dictionary and result.parent is parent and result.carrier is carrier and
            result.raw == raw and result.close == closed and owner._anchor() is original and
            parent._anchor()[2]["pending"] is owner and parent._anchor()[2]["phase"] == "PENDING_CLOSED",
            "PENDING_RETURN_CHANGED")
        parent.current()
        _ENTRY.returned(_ATTEMPTS, parent._binding[1], result)
        N._check_history(graph)
        _closed_files(owner)
        require(directory.path is path and tuple(directory.identity) == identity and
            C._collect_directory_closed(directory, parent.clock.clock.role), "PENDING_WRITER_DIRECTORY_CLOSE")
        _original_parent, carrier_value = _checked_carrier(carrier)
        value = TD.parse_pending(raw)
        require(value["knownCloses"]["carrierCloseSha256"] == O.digest(carrier.raw) and
            value["knownCloses"]["tailChildCloseSha256"] == O.digest(carrier.native.close) and
            value["manifests"] == carrier_value["manifests"] and value["times"]["pendingPreparedNs"] <= closed_ns <
            parent.clock.final, "PENDING_KNOWN_CLOSE_LINKS")
        return parent, dict(TD.output_values(raw))
    except BaseException as error:
        raise parent.fail(error)


def _append_nine(values, check):
    """Distinct exact9 appender; shared original native close mechanics only."""
    require(type(values) is dict and set(values) == set(TD.OUTPUT_FIELDS), "NINE_OUTPUT_FIELDS")
    CD.sha(values[TD.OUTPUT])
    deadline = TD.decoded_deadline(values["initialProductiveDeadlineBase64"], values["initialProductiveDeadlineSha256"])
    require({name: values[name] for name in TD.SEAL_OUTPUT_FIELDS} == TD.seal_outputs(deadline), "NINE_SAME_SEAL_FIELDS")
    raw = "".join(name + "=" + values[name] + "\n" for name in sorted(values)).encode("ascii")
    require(len(raw) <= 4096 and callable(check) and not continuity.QUARANTINE, "NINE_OUTPUT_BOUND")
    check()
    target = Path(os.environ.get("GITHUB_OUTPUT", ""))
    parent = Path(os.environ.get("RUNNER_TEMP", ""))
    require(target.is_absolute() and parent.is_absolute() and ".." not in target.parts and
        target.parent == parent / "_runner_file_commands" and
        re.fullmatch(r"set_output_[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", target.name),
        "NINE_OUTPUT_FIXED_RUNNER_PATH")
    parents = tuple((path, path.lstat()) for path in target.parents)
    for path, info in parents:
        require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "NINE_OUTPUT_PARENT")
    before = target.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == 0 and
        not getattr(before, "st_file_attributes", 0) & 0x400 and (os.name == "nt" or before.st_uid == os.geteuid()),
        "NINE_OUTPUT_EMPTY_FILE")
    attributes = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_file_attributes")
    identity = tuple(getattr(before, name, None) for name in attributes)

    def same_file(current, count):
        return tuple(getattr(current, name, None) for name in attributes) == identity and current.st_size == count

    check()
    descriptor = os.open(target, os.O_RDWR | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0) |
        getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    failure = None
    try:
        require(same_file(os.fstat(descriptor), 0), "NINE_OUTPUT_OPEN_CHANGED")
        check()
        written = os.write(descriptor, raw)
        require(type(written) is int and written == len(raw), "NINE_OUTPUT_SHORT_WRITE")
        os.fsync(descriptor)
        check()
        require(os.lseek(descriptor, 0, os.SEEK_SET) == 0 and os.read(descriptor, len(raw) + 1) == raw,
            "NINE_OUTPUT_EXACT_READBACK")
        require(same_file(target.lstat(), len(raw)) and same_file(os.fstat(descriptor), len(raw)), "NINE_OUTPUT_REPLACED")
        for path, info in parents:
            after = path.lstat()
            require(os.path.samestat(info, after) and stat.S_ISDIR(after.st_mode) and
                not getattr(after, "st_file_attributes", 0) & 0x400, "NINE_OUTPUT_PARENT_CHANGED")
    except BaseException as error:
        failure = error
    try:
        os.close(descriptor)
    except BaseException as error:
        continuity.QUARANTINE.append(descriptor)
        if failure is not None:
            raise failure from error
        raise O.OriginError("INITIAL_K_OUTPUT_CLOSE_UNKNOWN") from error
    if failure is not None:
        raise failure
    check()


class _OutputFence:
    """Actual pending-writer close, single nine-output append, two late checks."""
    __slots__ = ("_binding",)

    def __init__(self, result):
        parent, values = _checked_pending(result)
        try:
            require(type(self) is _OutputFence and id(self) not in _OUTPUTS and
                not any(saved[1][0] is result for saved in _OUTPUTS.values()), "OUTPUT_ONCE")
            limit = parent.clock.final
            value = {"schema": 1, "scope": "INITIAL_PRODUCTIVE_BEFORE_UPLOAD_PENDING_ORIGINAL_STEP_RETURN_V1", **values,
                "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
            self._binding = (result, parent, values, value, limit, N._history_graph(values, value))
            _OUTPUTS[id(self)] = (self, self._binding, {"phase": "NEW", "checks": 0, "busy": False, "failure": None})
        except BaseException as error:
            raise parent.fail(error)

    def _anchor(self):
        saved = _OUTPUTS.get(id(self))
        require(type(self) is _OutputFence and type(saved) is tuple and saved[0] is self,
            "OUTPUT_ORIGINAL_BINDING")
        return saved

    def _fail(self, saved, error):
        failure = saved[1][1].fail(error)
        if saved[2]["failure"] is None:
            saved[2]["failure"] = failure
        return saved[2]["failure"]

    def _begin(self):
        saved = self._anchor()
        if saved[2]["failure"] is not None:
            raise saved[2]["failure"]
        try:
            require(self._binding is saved[1] and not saved[2]["busy"], "OUTPUT_BINDING_OR_REENTRY")
            saved[2]["busy"] = True
            return saved
        except BaseException as error:
            raise self._fail(saved, error)

    def _current(self, saved):
        require(self._anchor() is saved and self._binding is saved[1] and saved[2]["busy"] and
            saved[2]["failure"] is None, "OUTPUT_CHANGED")
        result, parent, values, _value, limit, graph = saved[1]
        N._check_history(graph)
        original_parent, actual_values = _checked_pending(result)
        require(original_parent is parent and actual_values == values and
            limit == parent.clock.final, "OUTPUT_PENDING_CHANGED")
        return parent, limit

    def _guard(self):
        saved = self._begin()
        try:
            require(saved[2]["phase"] == "APPENDING" and saved[2]["checks"] == 0, "OUTPUT_APPEND_PHASE")
            parent, limit = self._current(saved)
            parent.current()
            parent.now(final=True, limit=limit)
            self._current(saved)
        except BaseException as error:
            raise self._fail(saved, error)
        finally:
            saved[2]["busy"] = False

    def append(self):
        saved = self._begin()
        try:
            require(saved[2]["phase"] == "NEW", "OUTPUT_APPEND_REUSE")
            self._current(saved)
            saved[2]["phase"] = "APPENDING"
        except BaseException as error:
            raise self._fail(saved, error)
        finally:
            saved[2]["busy"] = False
        try:
            _append_nine(saved[1][2], self._guard)
            self._guard()
            saved[2]["phase"] = "OUTPUT"
            return saved[1][3], self, saved[1][4]
        except BaseException as error:
            raise self._fail(saved, error)

    def now(self, *, final=False, minimum=0, limit=None):
        saved = self._begin()
        try:
            require(saved[2]["phase"] == "OUTPUT" and final is True and type(minimum) is int and minimum == 0 and
                type(limit) is int and limit == saved[1][4] and type(saved[2]["checks"]) is int and
                0 <= saved[2]["checks"] < 2, "OUTPUT_EXACT_LATE_CHECK")
            saved[2]["checks"] += 1
            parent, original_limit = self._current(saved)
            parent.current()
            observed = parent.now(final=True, limit=original_limit)
            self._current(saved)
            return observed
        except BaseException as error:
            raise self._fail(saved, error)
        finally:
            saved[2]["busy"] = False


def before_and_tail(cancelled):
    """The sole fixed parent route; B and K are one same-interpreter attempt."""
    original = _ENTRY
    attempt = original.begin(_ATTEMPTS)
    parent = None
    try:
        before = R.productive_before(cancelled)
        original.check(_ATTEMPTS, attempt)
        parent = _Parent(before, attempt)
        returned = _native_tail(parent)
        carrier = _copy_carrier(parent, returned)
        pending = _retain_pending(carrier)
        original.complete(_ATTEMPTS, attempt, pending)
        _checked_pending(pending)
        return _OutputFence(pending).append()
    except BaseException as error:
        raise original.fail(error) if parent is None else parent.fail(error)


def check_child_validation(view):
    return _check_child_validation(view)


def check_child_archive(view):
    return _check_child_archive(view)


def archive_liveness(view):
    return _archive_liveness(view)


_SUPPLIER_BUSY = set()


def _guarded_supplier(function):
    """Source-owned facade wrapper; never callable selection from DATA/argv."""
    def checked(first, *rest):
        binding = _VIEWS.get(id(first))
        child = binding[1] if type(binding) is tuple and binding[0] is first else first
        state = _CHILDREN.get(id(child))
        if state is None:
            return function(first, *rest)  # Original exact-type checker refuses.
        entered = False
        try:
            _source_current()
            require(id(state) not in _SUPPLIER_BUSY, "SUPPLIER_REENTRY")
            _SUPPLIER_BUSY.add(id(state))
            entered = True
            result = function(first, *rest)
            _source_current()
            require(_CHILDREN.get(id(child)) is state and id(state) in _SUPPLIER_BUSY,
                "SUPPLIER_ORIGINAL_STATE_CHANGED")
            if id(state) in _CHILD_FAILURES:
                raise _CHILD_FAILURES[id(state)]
            _pin(state)
            state.clock.current()
            return result
        except BaseException as error:
            raise _fail(state, error)
        finally:
            if entered:
                _SUPPLIER_BUSY.discard(id(state))
    return checked


for _supplier_name in ("checked_child_validation", "check_child_validation", "checked_child_archive", "check_child_archive",
        "archive_liveness", "checked_retired_child_validation", "check_retired_child_archive"):
    globals()[_supplier_name] = _guarded_supplier(globals()[_supplier_name])


def _bind_source_check():
    namespace = globals()
    functions = tuple((name, value) for name, value in tuple(namespace.items())
        if callable(value) and getattr(value, "__module__", None) == __name__)
    classes = tuple((kind, name, value) for kind in (_Clock, _Parent, _TailNativeOwner, _OutputFence, _State,
        _File, _NodeOrigin, _Lineage, _Completion, _NativeReturn, _Carrier, _Pending, TailChild, TailArchiveBinding,
        TailChildSourceBinding, TailValidationView, TailArchiveView, TailValidationCaps, TailArchiveCaps, ExpectedNode)
        for name, value in kind.__dict__.items())
    native_classes = tuple((kind, name, value) for kind in (native.Owner, C._PrimaryOwner)
        for name, value in kind.__dict__.items())
    suppliers = tuple((module, name, getattr(module, name)) for module, names in (
        (R, ("productive_before", "checked_productive_before")),
        (RD, ("final_bundle", "authority_bundle", "seal_record", "deadline", "original_proposal",
            "authority_index", "writer_return", "known_close", "file_observation")),
        (TD, ("public_inputs", "public_manifest", "cut", "manifest_inputs", "join_manifests", "encode_close", "encode_pending", "output_values",
            "decoded_deadline", "deadline_environment", "proposal_deadline", "PHASE_NAMES")),
        (E, _e_functions()[0]), (C, ("_PrimaryOwner", "_private", "_recipient_inventory")),
        (N, ("_history_graph", "_check_history", "host_context")), (C.B, ("EntryLatch",))) for name in names)
    aliases = tuple((name, namespace[name]) for name in ("R", "RD", "P", "C", "N", "B", "O", "TD", "CD", "E", "native", "Q",
        "continuity", "_ENTRY", "_ATTEMPTS", "_PINS", "_CHILDREN", "_VIEWS", "_CLOCKS", "_OWNER_REGISTRY", "_CHILD_FAILURES",
        "_SUPPLIER_BUSY", "_PARENTS", "_NODES", "_FILE_PINS", "_NATIVE", "_CARRIERS", "_PENDING", "_OUTPUTS",
        "PRIVATE_DIRECTORIES", "PHASE_PLACEMENT", "DIRECTORIES", "INPUT_LIMITS", "PRIVATE_INPUT_NAMES", "PRIVATE_CLOSED_NAMES"))
    input_limits = tuple(INPUT_LIMITS.items())
    def check():
        require(namespace.get("_source_current") is check and all(namespace.get(name) is original for name, original in
            (*functions, *aliases)) and all(kind.__dict__.get(name) is original for kind, name, original in (*classes, *native_classes)) and
            all(getattr(module, name) is original for module, name, original in suppliers) and
            tuple(INPUT_LIMITS) == tuple(name for name, _maximum in input_limits) and
            all(INPUT_LIMITS[name] is original for name, original in input_limits) and
            R.P is P and P.C is C and P.N is N and P.B is B and P.O is O, "ORIGINAL_SOURCE_SUPPLIER_CHANGED")
    return check


_source_current = _bind_source_check()
