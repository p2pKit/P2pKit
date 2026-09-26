#!/usr/bin/env python3
"""Dormant fixed BEFORE(B then K) owner; no workflow or execution activation.

This distinct source route does not widen the old P0 exporter, B clock/owner
allowlists, native45 phases, deadlines, output grammar, cache admission or HOLDs.
The only parent entry first obtains genuine B in this SAME interpreter. K's
child has a NEW token-free native domain and same-child PUBLIC Recipient; its
entire finite cut, export, closes and pending output spend the original seal
ceiling. Retained timestamps/hashes/JSON cannot reconstruct either parent.

UNREVIEWED / UNTESTED source preparation. No native/runtime qualification is
asserted. Final encryption/native self-tail remains private and NOT_DELIVERED.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid


sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("_initial_recipient_tail_custody",
    SCRIPTS / "run-hosted-initial-recipient-custody.py")
C = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = C
_spec.loader.exec_module(C)  # Exactly one maintained C/N/native module lineage.
import hosted_initial_recipient_tail_evidence as T
import hosted_initial_recipient_tail_handoff as H
import hosted_initial_recipient_tail_carrier as R

N, native, O, Q, B, continuity = C.N, C.native, C.O, C.Q, C.B, C.C
NS = O.NS
CONTEXT_SCOPE = "INITIAL_RECIPIENT_K_TAIL_CHILD_CONTEXT_V1"
START_SCOPE = "INITIAL_RECIPIENT_K_TAIL_NATIVE_START_V1"
CHILD_SCOPE = "INITIAL_RECIPIENT_K_TAIL_PENDING_CHILD_CLOSE_V1"
ACK_SCOPE = "INITIAL_RECIPIENT_K_TAIL_POST_OWNER_CLOSE_ACK_V1"
MAP_SCOPE = "INITIAL_RECIPIENT_K_PRIVATE_CUT_MAP_V1"
CAP_FIELDS = (("startedNs", "--tail-started-ns"), ("workEndNs", "--tail-work-end-ns"),
    ("finalEndNs", "--tail-final-end-ns"))
INPUT_LIMITS = {
    "before-index.json": native.LIMIT, "before-readback.json": native.LIMIT,
    "before-writer-close.json": native.LIMIT, "before-match.json": min(C.A.stages.LIMIT, native.LIMIT),
    "original-match.json": min(C.A.stages.LIMIT, native.LIMIT), "event.json": C.I.EVENT_LIMIT,
    "candidate-policy.json": C.I.POLICY_LIMIT, "recipient-public.asc": T.posix.MAX_KEY_BYTES,
    "p0-manifest.json": T.MANIFEST_LIMIT, "seal-pending.json": native.LIMIT,
    "crypto-step-pending.json": native.LIMIT, "custody-return.json": native.LIMIT,
    "p0-context.json": 65536, "collect-close.json": native.LIMIT,
}
DIRECTORIES = ("custody", "tail-returned", "control-home", "temporary", "service",
    "tail-public-crypto", "tail-copied-evidence", "tail-export-output")
CONTEXT_FIELDS = {"schema", "scope", "kind", "root", "session", "job", "observed", "originalWindow", "deadline",
    "caps", "parentFirstNs", "parentFirstLocal", "beforeClosedNs", "originalServiceJob", "predecessors",
    "filesSha256", "directories", "inheritedContext", "budgetAcceptance", "exportSaveAuthority"}
_ATTEMPTS, _PARENTS, _CHILD_CLOCKS, _FILE_PINS, _NATIVE, _CARRIERS, _OUTPUTS = {}, {}, {}, {}, {}, {}, {}
_ENTRY = B.EntryLatch(_ATTEMPTS)


def require(value, code):
    C.require(value, "K_" + code)


def _closed_files(owner):
    require(type(owner) is C._PrimaryOwner, "FILE_OWNER_TYPE")
    owner.structural()
    require(owner.finished and owner.failure is None and owner.owner.closed and not owner.owner.unknown and
        owner.owner.original is None and owner.errors == [] and all(a and c for _r, _l, _v, a, c in owner.rows),
        "FILE_OWNER_CLOSE_UNKNOWN")


def _paths(kind):
    root = C._paths(kind)[2]
    private = root / H.DIRECTORY
    return {"custody": root, "tail-returned": private, "control-home": private / "control-home",
        "temporary": private / "temporary", "service": private / "service",
        **{name: root / name for name in ("tail-public-crypto", "tail-copied-evidence", "tail-export-output")}}


def _custody_names(*, tail_output, upload=False):
    """Exact NEW siblings of the unchanged closed B root; no glob/widening."""
    require(type(tail_output) is bool and type(upload) is bool and (not upload or tail_output), "CUSTODY_ROSTER_STAGE")
    return tuple(sorted((*C._before_roster(created=True), "tail-returned", "tail-public-crypto", "tail-copied-evidence",
        *(("tail-export-output",) if tail_output else ()), *(("upload-output",) if upload else ()))))


def _caps(seed, values):
    _sha, seal_end, _clock, _boot = continuity.seal_deadline_data(seed)
    require(type(values) is tuple and len(values) == 3 and
        all(type(value) is int and 0 < value <= O.clocks.UINT64 for value in values), "CAPS")
    started, work, final = values
    # Separate token-free K210 subcap; unchanged45 retirement is reserved
    # INSIDE the inherited sealEnd, never appended to it or to child FIRST.
    require(started < work and work == min(started + 210 * NS, seal_end - 45 * NS) and
        final == work + 45 * NS <= seal_end, "ORIGINAL_NATIVE_CAPS")
    return values


def _command(context_hash, seed, caps, minimum=None):
    C.digest(context_hash)
    _caps(seed, caps)
    result = [str(Path(sys.executable).resolve(strict=True)), "-I", "-B", "-S",
        str(SCRIPTS / "run-hosted-initial-recipient-tail.py"), "_tail-child", "--context-sha256", context_hash]
    if minimum is not None:
        result.extend(("--minimum-ns", str(O.integer(minimum))))
    for name, _environment, flag in B.SEED_FIELDS:
        result.extend((flag, seed[name]))
    for (_name, flag), value in zip(CAP_FIELDS, caps):
        result.extend((flag, str(value)))
    return result


class _Parent:
    """A single consumed real B return, not a loader or restartable facade."""
    __slots__ = ("_binding",)

    def __init__(self, before, attempt, entry):
        require(type(self) is _Parent and id(self) not in _PARENTS and entry is _ENTRY, "PARENT_NEW")
        checked = C.checked_before_authority(before)
        saved = C._BEFORE_AUTHORITIES[id(before)]
        require(not any(anchor[1][0] is before for anchor in _PARENTS.values()), "B_CONTINUATION_REUSE")
        clock, inputs, originals, index_raw, match, captured = checked
        raws = dict(inputs.originals)
        parsed = C._tail_bundle({name: raws[name] for name in C._TAIL_LIMITS})
        self._binding = (before, saved, clock, inputs, originals, index_raw, match, captured, raws, parsed, attempt, entry)
        _PARENTS[id(self)] = (self, self._binding, N._history_graph(raws, parsed),
            {"failure": None, "phase": "B_RETURNED", "native": None, "carrier": None, "writer": None})
        self.current()

    def _anchor(self):
        saved = _PARENTS.get(id(self))
        require(type(self) is _Parent and type(saved) is tuple and saved[0] is self,
            "PARENT_ORIGINAL_BINDING")
        return saved

    def fail(self, error):
        saved = self._anchor()
        original = saved[1][1][18][0].fail(error)  # K failure poisons the original B lineage too.
        original = saved[1][11].fail(original)
        if saved[3]["failure"] is None:
            saved[3]["failure"] = original
        saved[3]["phase"] = "FAILED"
        return saved[3]["failure"]

    def current(self):
        saved = self._anchor()
        if saved[3]["failure"] is not None:
            raise saved[3]["failure"]
        try:
            before, original, clock, inputs, originals, index, match, captured, _raws, _parsed, attempt, entry = saved[1]
            require(self._binding is saved[1] and entry is _ENTRY, "ENTRY_OR_PARENT_REPLACED")
            entry.check(_ATTEMPTS, attempt)
            require(C._BEFORE_AUTHORITIES.get(id(before)) is original, "B_REGISTRY_REPLACED")
            checked = C.checked_before_authority(before)
            require(checked[0] is clock and checked[1] is inputs and checked[2] is originals and checked[3] == index and
                checked[4] is match and checked[5] is captured, "B_RETURN_REPLACED")
            N._check_history(saved[2])
            require(not any(name in os.environ for name in T.CREDENTIAL_NAMES) and not native.QUARANTINE and
                not Q.QUARANTINE and not continuity.QUARANTINE and not T.windows._QUARANTINE, "PARENT_NOT_TOKEN_FREE_OR_KNOWN")
            clock._view()
            return saved
        except BaseException as error:
            raise self.fail(error)

    clock = property(lambda self: self.current()[1][2])

    def now(self, *, final=False, minimum=0, limit=None):
        saved = self.current()
        try:
            result = saved[1][2].now(final=final, minimum=minimum, limit=limit)
            self.current()
            return result
        except BaseException as error:
            raise self.fail(error)

    def currency(self):
        saved = self.current()
        try:
            C._before_currency(saved[1][0].acquired)
            require(self.current() is saved, "CURRENT_B_CHANGED")
            return saved
        except BaseException as error:
            raise self.fail(error)


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
    require(type(owner) is C._PrimaryOwner and type(maximum) is int and 0 < maximum <= H.MAX_ZIP_BYTES, "READER_BOUND")
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
        0 <= value.count <= value.maximum <= H.MAX_ZIP_BYTES, "FILE_ORIGINAL_METADATA_OR_CLOSE")
    R.metadata(C.canonical(value.raw), owner.owner.first.clock.role, value.count)
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
            R.metadata(C.canonical(written), owner.owner.first.clock.role, value.count)
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
    require(type(raw) is bytes and 0 < len(raw) <= native.LIMIT, "WRITE_BYTES_BOUND")
    Q._component(name)
    writer = None
    try:
        end = owner.guard()
        writer = owner.acquire("writer", lambda: directory.create_file(name, max_bytes=len(raw), deadline=end))
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
    policy = R.write_close_metadata(owner.owner.first.clock.role, C.canonical(before_raw),
        C.canonical(readback.raw), len(raw))
    return {"preCloseWrite": C.canonical(before_raw), "postCloseReadback": C.canonical(readback.raw),
        "metadataPolicy": policy}


def _list_names(owner, directory, maximum):
    require(type(maximum) is int and 0 < maximum <= T.posix.MAX_MEMBERS, "DIRECTORY_LIST_CAP")
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
    require(type(expected) is tuple and len(expected) <= T.posix.MAX_MEMBERS and len(set(expected)) == len(expected),
        "DIRECTORY_EXPECTED")
    require(_list_names(owner, directory, max(1, len(expected))) == tuple(sorted(expected)), "DIRECTORY_EXACT_ROSTER")


@dataclass(frozen=True, repr=False)
class _Carrier:
    parent: object
    native: object
    raw: bytes
    close: bytes


def _copy_carrier(parent, returned):
    """Four literal copies AFTER actual child/native parent retirement."""
    checked = _checked_native(parent, returned)
    _native_parent, context, child, _records, native_close = checked
    parent.currency()
    clock, owner = parent.clock, None
    failure = None
    try:
        require(parent._anchor()[3]["phase"] == "NATIVE_CLOSED" and parent._anchor()[3]["carrier"] is None,
            "CARRIER_ONCE_AFTER_NATIVE")
        owner = C._PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
        parent._anchor()[3]["carrier"] = owner  # Actual return before the next callback.
        custody = C._private(owner, _paths(context["kind"])["custody"])
        p0 = C._private(owner, custody.path / "export-output")
        tail = C._private(owner, custody.path / "tail-export-output")
        end = owner.guard()
        target = owner.acquire("directory", lambda: custody.create_directory("upload-output", deadline=end))
        _names(owner, custody, _custody_names(tail_output=True, upload=True))
        directories = (custody, p0, tail, target)
        pins = tuple((directory, directory.path, tuple(directory.identity)) for directory in directories)
        require(len({pin[2] for pin in pins}) == 4 and tuple(custody.identity) == tuple(context["directories"]["custody"]) and
            tuple(tail.identity) == tuple(child["outputIdentity"]), "CARRIER_ORIGINAL_DIRECTORIES")
        input_pins = C._BEFORE_INPUTS[id(parent._binding[3])][6]
        require(tuple(p0.identity) == next(pin[3] for pin in input_pins if pin[0] == "export-output"),
            "CARRIER_ORIGINAL_B_OUTPUT_PIN")
        manifest = T._p0(parent._binding[8]["manifest"])
        tail_manifest_raw = base64.b64decode(child["manifest"]["base64"], validate=True)
        tail_manifest = C.canonical(tail_manifest_raw, T.MANIFEST_LIMIT)
        members = [
            {"name": T.CARRIER_MEMBERS[0], "bytes": manifest["artifact"]["size"], "sha256": manifest["artifact"]["sha256"]},
            {"name": T.CARRIER_MEMBERS[1], "bytes": len(parent._binding[8]["manifest"]), "sha256": O.digest(parent._binding[8]["manifest"])},
            {"name": T.CARRIER_MEMBERS[2], "bytes": tail_manifest["artifact"]["size"], "sha256": tail_manifest["artifact"]["sha256"]},
            {"name": T.CARRIER_MEMBERS[3], "bytes": len(tail_manifest_raw), "sha256": O.digest(tail_manifest_raw)},
        ]
        total, zipped = H.carrier_bytes(members)  # Includes552 fixed ZIP bytes; refuse BEFORE copying/Create.
        _names(owner, p0, (T.posix.ARTIFACT, T.posix.MANIFEST))
        _names(owner, tail, (T.posix.ARTIFACT, T.posix.MANIFEST))
        _names(owner, target, ())
        observations = []
        for number, row in enumerate(members):
            parent.currency()
            source = p0 if number < 2 else tail
            leaf = T.posix.MANIFEST if number % 2 else T.posix.ARTIFACT
            reader = _open_file(owner, source, leaf, T.MANIFEST_LIMIT if number % 2 else H.MAX_ZIP_BYTES)
            require(reader.count == row["bytes"] and reader.ordinal == 4 + number * 3, "CARRIER_SOURCE_SIZE_OR_ORDINAL")
            end = owner.guard()
            writer = owner.acquire("writer", lambda: target.create_file(row["name"], max_bytes=row["bytes"], deadline=end))
            writer_ordinal = len(owner.rows) - 1
            checksum, write_raw = _stream(reader, row["sha256"], writer=writer, close=True)
            require(checksum == row["sha256"] and owner.rows[writer_ordinal][3:] == (True, True), "CARRIER_WRITER_CLOSE")
            readback = _open_file(owner, target, row["name"], row["bytes"])
            require(_stream(readback, row["sha256"], close=True)[0] == row["sha256"], "CARRIER_READBACK_HASH")
            require(readback.count == row["bytes"], "CARRIER_READBACK_SIZE")
            observations.append({**row, "sourceRelative": R.SOURCE_NAMES[number], "sourceDirectoryIdentity": list(source.identity),
                "sourceRead": {"metadata": C.canonical(reader.raw), "readerOrdinal": reader.ordinal},
                "write": {"metadata": C.canonical(write_raw), "writerOrdinal": writer_ordinal},
                "readback": {"metadata": C.canonical(readback.raw), "readerOrdinal": readback.ordinal},
                "metadataPolicy": R.write_close_metadata(clock.clock.role, C.canonical(write_raw),
                    C.canonical(readback.raw), row["bytes"])})
            _file_current(reader, closed=True)
            _file_current(readback, closed=True)
        _names(owner, target, T.CARRIER_MEMBERS)
        _names(owner, p0, (T.posix.ARTIFACT, T.posix.MANIFEST))
        _names(owner, tail, (T.posix.ARTIFACT, T.posix.MANIFEST))
        _names(owner, custody, _custody_names(tail_output=True, upload=True))
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
        value = {"schema": 1, "scope": R.SCOPE, **_identity_data(context), "predecessors": context["predecessors"],
            "manifests": {"p0Sha256": members[1]["sha256"], "tailSha256": members[3]["sha256"]},
            "cutMapSha256": child["cut"]["mapSha256"], "carrier": {"relative": "upload-output", "identity": list(pins[3][2])},
            "files": observations, "totalBytes": total, "zipBytes": zipped,
            "nativeClose": {"contextSha256": O.digest(returned.context), "resultSha256": O.digest(returned.child),
                "ackSha256": O.digest(dict(returned.records)["stdout.log"]),
                "phaseSha256": {name: O.digest(raw) for name, raw in returned.records}},
            "ownerCloses": {"native": native_close, "carrier": C._collect_file_close(closed_raw)},
            "times": {"beforeClosedNs": context["beforeClosedNs"], "tailChildClosedNs": returned.closed_ns,
                "carrierClosedNs": closed_ns}, "writerReturn": "PENDING_SEPARATE_RECORD_WRITER_CLOSE",
            **_nonacceptance()}
        raw = R.encode_close(value)
        result = _Carrier(parent, returned, raw, closed_raw)
        _CARRIERS[id(result)] = (result, result.__dict__, parent, returned, raw, closed_raw, owner, owner._anchor(), pins,
            N._history_graph(result.__dict__, tuple(pin[1] for pin in pins)), graph)
        _checked_carrier(result)
        parent._anchor()[3]["phase"] = "CARRIER_CLOSED"
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
            "jobId": step[0], "role": observed["role"]}, "originalWindow": context["originalWindow"], "deadline": context["deadline"]}


def _checked_carrier(result):
    saved = _CARRIERS.get(id(result))
    require(type(result) is _Carrier and type(saved) is tuple and saved[0] is result,
        "CARRIER_ORIGINAL_RETURN")
    try:
        require(result.__dict__ is saved[1] and result.parent is saved[2] and result.native is saved[3] and
            result.raw == saved[4] and result.close == saved[5], "CARRIER_RETURN_REPLACED")
        parent, native_result, _raw, _close, owner, anchor, pins, graph, observed_graph = saved[2:]
        parent.current()
        require(owner._anchor() is anchor and parent._anchor()[3]["carrier"] is owner, "CARRIER_ORIGINAL_OWNER")
        _closed_files(owner)
        for directory, path, pin in pins:
            require(directory.path is path and tuple(directory.identity) == pin and
                C._collect_directory_closed(directory, parent.clock.clock.role), "CARRIER_CLOSED_PIN_CHANGED")
        N._check_history(graph)
        N._check_history(observed_graph)
        _checked_native(parent, native_result)
        return parent, R.parse_close(result.raw)
    except BaseException as error:
        raise saved[2].fail(error)


@dataclass(eq=False, repr=False)
class _ChildAnchor:
    handle: object
    binding: tuple
    graph: tuple
    last: int
    local_last: float
    context: object = None
    context_graph: tuple = ()
    owners: tuple = ()
    busy: bool = False
    failure: object = None


class _ChildClock:
    """Fresh child FIRST, capped by ORIGINAL argv seed/native tuple before I/O."""
    __slots__ = ("_binding",)

    def __init__(self, first, local, boot, cancelled, seed, caps):
        require(type(self) is _ChildClock and id(self) not in _CHILD_CLOCKS and callable(cancelled), "CHILD_CLOCK_NEW")
        C.local_value(local)
        O.clocks.validate_reading(first)
        _sha, seal_end, declared, original_boot = continuity.seal_deadline_data(seed)
        started, work, final = _caps(seed, caps)
        require(first.clock == declared and type(boot) is str and boot == original_boot and
            started <= first.nanoseconds < work < final <= seal_end, "CHILD_FIRST_CAP_OR_BOOT")
        local_work = O.wire._directed_deadline(local, (work - first.nanoseconds) / NS, work, first.nanoseconds)
        local_final = O.wire._directed_deadline(local, (final - first.nanoseconds) / NS, final, first.nanoseconds)
        self._binding = (first, local, boot, cancelled, seed, caps, local_work, local_final)
        _CHILD_CLOCKS[id(self)] = _ChildAnchor(self, self._binding, N._history_graph(first, seed, caps), first.nanoseconds, local)
        self.current()

    def _anchor(self):
        anchor = _CHILD_CLOCKS.get(id(self))
        require(type(self) is _ChildClock and type(anchor) is _ChildAnchor and anchor.handle is self, "CHILD_CLOCK_HANDLE")
        return anchor

    def fail(self, error):
        anchor = self._anchor()
        if anchor.failure is None:
            anchor.failure = error
        return anchor.failure

    def current(self):
        anchor = self._anchor()
        if anchor.failure is not None:
            raise anchor.failure
        try:
            require(self._binding is anchor.binding and _CHILD_CLOCKS.get(id(self)) is anchor and
                not any(name in os.environ for name in T.CREDENTIAL_NAMES) and not native.QUARANTINE and
                not Q.QUARANTINE and not continuity.QUARANTINE and not T.windows._QUARANTINE and
                not native.diagnostics._QUARANTINE,
                "CHILD_CLOCK_BINDING_OR_QUARANTINE")
            N._check_history(anchor.graph)
            N._check_history(anchor.context_graph)
            for owner, original in anchor.owners:
                require(owner._anchor() is original and owner.owner.fence is self and owner.owner.first is anchor.binding[0],
                    "CHILD_FILE_OWNER_CHANGED")
                owner.structural()
                require(owner.failure is None and not owner.owner.unknown and owner.owner.original is None and owner.errors == [],
                    "CHILD_FILE_OWNER_FAILED")
            return anchor
        except BaseException as error:
            raise self.fail(error)

    reading = property(lambda self: self.current().binding[0])
    clock = property(lambda self: self.reading.clock)
    first = property(lambda self: self.reading.nanoseconds)
    first_local = property(lambda self: self.current().binding[1])
    work = property(lambda self: self.current().binding[5][1])
    final = property(lambda self: self.current().binding[5][2])
    local_end = property(lambda self: self.current().binding[7])
    cancelled = property(lambda self: self.current().binding[3])
    seed = property(lambda self: self.current().binding[4])
    caps = property(lambda self: self.current().binding[5])
    last = property(lambda self: self.current().last)

    def _begin(self):
        anchor = self.current()
        try:
            require(not anchor.busy, "CHILD_CLOCK_REENTRY")
            anchor.busy = True
            return anchor
        except BaseException as error:
            raise self.fail(error)

    def _local(self, anchor, final):
        current = C.local_value(time.monotonic())
        require(current >= anchor.local_last, "CHILD_LOCAL_BACKWARDS")
        anchor.local_last = current
        self.current()
        require(current < anchor.binding[7 if final else 6], "CHILD_LOCAL_EXPIRED")
        return current

    def _observe(self, anchor, final, minimum, limit):
        end = anchor.binding[5][2 if final else 1]
        if limit is not None:
            end = min(end, O.integer(limit))
        frontier = max(anchor.last, O.integer(minimum))
        for number in range(2):
            local = self._local(anchor, final)
            observed = O.clocks.checked_now(anchor.binding[0].clock, minimum_ns=frontier)
            anchor.last = frontier = O.integer(observed, frontier)
            self.current()
            require(anchor.busy and anchor.failure is None and frontier < end, "CHILD_RAW_EXPIRED")
            actual_boot = continuity.boot_digest(anchor.binding[0].clock.role)
            self.current()
            require(type(actual_boot) is str and actual_boot == anchor.binding[2], "CHILD_BOOT_CHANGED")
            if number == 0:
                anchor.binding[3]()
                self.current()
                require(anchor.busy and anchor.failure is None and anchor.last == frontier and anchor.local_last == local,
                    "CHILD_CALLBACK_CHANGED")
        self._local(anchor, final)
        self.current()
        require(anchor.busy and anchor.failure is None and anchor.last == frontier, "CHILD_CLOCK_CHANGED")
        return frontier

    def now(self, *, final=False, minimum=0, limit=None):
        anchor = self._begin()
        try:
            require(type(final) is bool, "CHILD_FINAL_TYPE")
            return self._observe(anchor, final, minimum, limit)
        except BaseException as error:
            raise self.fail(error)
        finally:
            anchor.busy = False

    def deadline(self, maximum, *, final=False, limit=None):
        anchor = self._begin()
        try:
            require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 900 and
                type(final) is bool, "CHILD_MECHANISM_BOUND")
            local = self._local(anchor, final)
            observed = self._observe(anchor, final, 0, limit)
            end = anchor.binding[5][2 if final else 1]
            if limit is not None:
                end = min(end, O.integer(limit))
            result = min(anchor.binding[7 if final else 6], O.wire._directed_deadline(local, maximum, end, observed))
            self.current()
            require(anchor.busy and anchor.failure is None, "CHILD_DEADLINE_CHANGED")
            return result
        except BaseException as error:
            raise self.fail(error)
        finally:
            anchor.busy = False

    def attach(self, owner):
        anchor = self.current()
        require(type(owner) is C._PrimaryOwner and owner.owner.fence is self and owner.owner.first is anchor.binding[0] and
            not owner.finished and not owner.rows and len(anchor.owners) < 2 and
            (not anchor.owners or anchor.owners[0][0].finished), "CHILD_FILE_OWNER_ONCE")
        anchor.owners = (*anchor.owners, (owner, owner._anchor()))
        self.current()

    def bind(self, context_raw, start_raw, raws, inherited):
        anchor = self.current()
        require(anchor.context is None and len(anchor.owners) == 1, "CHILD_CONTEXT_ONCE")
        _closed_files(anchor.owners[0][0])
        anchor.context = (context_raw, start_raw, raws, inherited)
        anchor.context_graph = N._history_graph(raws, inherited)
        self.current()


def _input_values(parent):
    saved = parent.currency()
    before, _original, _clock, _inputs, _originals, index, match, _captured, raws, _parsed, _attempt, _entry = saved[1]
    result = {"before-index.json": index, "before-readback.json": before.readback,
        "before-writer-close.json": before.writer_close, "before-match.json": match.record,
        "original-match.json": raws["original-match"], "event.json": raws["event"], "candidate-policy.json": raws["policy"],
        "recipient-public.asc": raws["public"], "p0-manifest.json": raws["manifest"], "seal-pending.json": raws["seal"],
        "crypto-step-pending.json": raws["step"], "custody-return.json": raws["carrier"],
        "p0-context.json": raws["context"], "collect-close.json": raws["collect"]}
    require(set(result) == set(INPUT_LIMITS) and all(type(raw) is bytes and 0 < len(raw) <= INPUT_LIMITS[name]
        for name, raw in result.items()), "EXACT_CHILD_INPUT_BYTES")
    return result


def _prior(raws):
    return {"step": raws["crypto-step-pending.json"], "carrier": raws["custody-return.json"],
        "context": raws["p0-context.json"], "manifest": raws["p0-manifest.json"], "original-match": raws["original-match.json"],
        "fresh-match": raws["original-match.json"], "event": raws["event.json"], "policy": raws["candidate-policy.json"],
        "public": raws["recipient-public.asc"], "collect": raws["collect-close.json"]}


def _context(raw, seed, caps, clock):
    value = C.canonical(raw, 65536)
    graph = N._history_graph(value, seed, caps, clock)
    H._fields(value, CONTEXT_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == CONTEXT_SCOPE and
        value["kind"] in ("gate", "worker") and value["root"] == str(ROOT) and type(value["job"]) is str and
        re.fullmatch(r"[0-9a-f]{32}", value["job"]) and value["budgetAcceptance"] == "NOT_ADMITTED" and
        value["exportSaveAuthority"] is False, "CONTEXT_SCOPE")
    require(value["deadline"] == seed and value["caps"] == dict(zip((name for name, _flag in CAP_FIELDS), caps)) and
        value["session"] == str(_paths(value["kind"])["tail-returned"]), "CONTEXT_CAPS_PATH")
    H._fields(value["caps"], {name for name, _flag in CAP_FIELDS})
    _caps(seed, tuple(value["caps"][name] for name, _flag in CAP_FIELDS))
    _caps(seed, caps)
    H._window(value["originalWindow"], value["kind"], clock.role, seed)
    require(O.integer(value["parentFirstNs"]) <= O.integer(value["beforeClosedNs"]) <= caps[0] and
        C.local_value(value["parentFirstLocal"]) >= 0, "CONTEXT_PARENT_FLOORS")
    C._collect_service_job(value["originalServiceJob"])
    H._hashes(value["predecessors"], T.PREDECESSOR_FIELDS)
    require(value["predecessors"]["sealSha256"] == seed["initialSealSha256"] and
        value["predecessors"]["originalWindowSha256"] == O.digest(O.encoded(value["originalWindow"])), "CONTEXT_WINDOW_HASH")
    H._hashes(value["filesSha256"], INPUT_LIMITS)
    H._fields(value["directories"], DIRECTORIES)
    pins = []
    for name, pin in value["directories"].items():
        if name == "tail-export-output" and clock.role != "windows-x64":
            require(pin is None, "CONTEXT_POSIX_OUTPUT_ABSENT")
        else:
            pins.append(R.identity(pin, clock.role))
    require(len(set(pins)) == len(pins), "CONTEXT_DIRECTORY_ALIAS")
    inherited = value["inheritedContext"]
    require(type(inherited) is dict and all(type(name) is str and type(item) is str for name, item in inherited.items()) and
        (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "CONTEXT_PARENT_DOMAIN")
    N._check_history(graph)
    return value


def _start_fields(raw, context_raw, context, role):
    value = C.canonical(raw)
    graph = N._history_graph(value, context)
    H._fields(value, native.START_FIELDS)
    caps = tuple(context["caps"][name] for name, _flag in CAP_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == START_SCOPE and
        value["contextSha256"] == O.digest(context_raw) and value["argv"] == _command(O.digest(context_raw), context["deadline"], caps) and
        value["cwd"] == str(ROOT) and value["role"] == role and value["job"] == context["job"] and
        value["state"] == context["session"] and value["home"] == str(Path(context["session"]) / "control-home") and
        type(value["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["invocation"]) and
        value["exitCode"] is None and value["launchAttempted"] is False and value["scopeAttempted"] is False and
        value["retirement"] == "UNKNOWN" and tuple(O.integer(value[name]) for name, _flag in CAP_FIELDS) == caps,
        "START_ORIGINAL_BINDINGS")
    expected = native.processes.ownership_environment(context["inheritedContext"], context["job"], value["invocation"],
        value["state"], value["home"], allow_new_context=True)
    require(value["inheritedContext"] == {name: expected[name] for name in Q._CONTEXT}, "START_NATIVE_INHERITANCE")
    N._check_history(graph)
    return value


def _start(raw, context_raw, context, minimum, first, inherited):
    value = _start_fields(raw, context_raw, context, first.clock.role)
    require(context["caps"]["startedNs"] <= O.integer(minimum) <= first.nanoseconds < context["caps"]["workEndNs"] and
        type(inherited) is dict and set(inherited) == set(Q._CONTEXT) and value["inheritedContext"] == inherited,
        "START_ACTUAL_CHILD_FIRST_AND_CONTEXT")
    domain = native.processes.ownership_domains(inherited[native.processes.CHAIN_ENV], inherited[native.processes.DOMAINS_ENV])[-1]
    require(domain == {"id": value["invocation"], "job": value["job"], "state": value["state"], "home": value["home"]},
        "START_NATIVE_DOMAIN")
    return value


def _child_inputs(context, raws, first):
    require(type(raws) is dict and set(raws) == set(INPUT_LIMITS), "CHILD_INPUT_ROSTER")
    graph = N._history_graph(context, raws, first)
    for name, maximum in INPUT_LIMITS.items():
        require(type(raws[name]) is bytes and 0 < len(raws[name]) <= maximum and
            O.digest(raws[name]) == context["filesSha256"][name], "CHILD_INPUT_HASH")
    prior = _prior(raws)
    parsed = C._tail_bundle(prior)
    step, _carrier, old, manifest, _collected = parsed
    sealed = C._historical_seal_record(raws["seal-pending.json"], prior, outcome="success",
        expected_sha256=context["deadline"]["initialSealSha256"])
    require(step["kind"] == context["kind"] and old["observed"] == context["observed"] and
        step["originalWindow"] == context["originalWindow"] and step["originalServiceJob"] == context["originalServiceJob"] and
        context["predecessors"]["cryptoStepSha256"] == O.digest(prior["step"]) and
        context["predecessors"]["collectSha256"] == O.digest(prior["collect"]) and
        raws["before-match.json"] == raws["original-match.json"], "CHILD_ORIGINAL_BINDINGS")
    prior_graph = N._history_graph(prior, parsed, sealed)
    observed, primary, event = N.host_context(O.integer(context["observed"]["firstUseAt"], 1))
    returned_graph = N._history_graph(observed, primary)
    N._check_history(graph)
    N._check_history(prior_graph)
    require(observed == context["observed"] and observed["role"] == first.clock.role and
        primary == C._paths(context["kind"])[0]["P"] and event == raws["event.json"], "CHILD_CURRENT_HOST_EVENT")
    before = C.canonical(raws["before-index.json"])
    require(before.get("scope") == "INITIAL_BEFORE_ACTUAL_ORIGINALS_CLOSED_RETURN_V1" and
        before.get("authorityCloseSha256") == context["predecessors"]["beforeAuthoritySha256"] and
        type(before.get("fileCount")) is int and before["fileCount"] == 280 and type(before.get("files")) is list and
        len(before["files"]) == 280 and type(before.get("directories")) is list and len(before["directories"]) == 58 and
        before.get("directoryCount") == 58 and before["capture"] == "NOT_K_CAPTURE" and
        before["closeWriterReturn"] == C.canonical(raws["before-writer-close.json"]), "CHILD_ORIGINAL_B_INDEX")
    readback = C.canonical(raws["before-readback.json"])
    writer = C.canonical(raws["before-writer-close.json"])
    require(writer["scope"] == "INITIAL_BEFORE_CLOSE_WRITER_KNOWN_RETURN_V1" and writer["sha256"] ==
        before["authorityCloseSha256"] and type(writer["closedNs"]) is int and writer["closedNs"] == context["beforeClosedNs"] and
        before["originalReadbackClose"] == readback["ownerClose"] and readback["fileCount"] == 279 and
        readback["directoryCount"] == 58 and before["directories"] == readback["directories"], "CHILD_B_CLOSE_LINKS")
    C._collect_file_close(O.encoded(readback["ownerClose"]))
    C._collect_file_close(O.encoded(writer["ownerClose"]))
    require(type(before["requiredFiles"]) is list and before["requiredFiles"] ==
        [row["relative"] for row in before["files"]] and len(set(before["requiredFiles"])) == 280,
        "CHILD_B_REQUIRED_FILES")
    H._window(context["originalWindow"], context["kind"], first.clock.role, context["deadline"])
    N._check_history(graph)
    N._check_history(prior_graph)
    N._check_history(returned_graph)
    return prior, parsed, sealed, before


_CAPTURES, _FREEZES = {}, {}


@dataclass(eq=False, repr=False)
class _CaptureAnchor:
    handle: object
    binding: tuple
    graph: tuple
    directories: tuple = ()
    sources: tuple = ()
    declarations: tuple = ()
    copies: tuple = ()
    pins: tuple = ()
    derived: tuple = ()
    charged_bytes: int = 0
    phase: str = "DECLARING"
    failure: object = None


def _relative(value):
    require(type(value) is str and value and not value.startswith("/") and "\\" not in value and
        all(Q._component(part) == part for part in value.split("/")), "RELATIVE_ORIGINAL")
    return value


class _Capture:
    """Real original readers + one exclusively written finite tail; no loader."""
    __slots__ = ("_binding",)

    def __init__(self, clock, owner, context_raw, start_raw, raws, recipient_pin, work, destination, output):
        require(type(self) is _Capture and id(self) not in _CAPTURES and type(clock) is _ChildClock and
            type(owner) is C._PrimaryOwner and owner.owner.fence is clock and
            type(recipient_pin) is tuple, "CAPTURE_NEW_OWNER")
        T.original._recipient_current(recipient_pin)
        context = _context(context_raw, clock.seed, clock.caps, clock.clock)
        require(clock.current().context is not None and work.path == _paths(context["kind"])["tail-public-crypto"] and
            destination.path == _paths(context["kind"])["tail-copied-evidence"], "CAPTURE_SAME_CHILD")
        self._binding = (clock, owner, context_raw, start_raw, raws, recipient_pin, work, destination, output, context)
        _CAPTURES[id(self)] = _CaptureAnchor(self, self._binding, N._history_graph(raws, context))
        self.current()

    def _anchor(self):
        anchor = _CAPTURES.get(id(self))
        require(type(self) is _Capture and type(anchor) is _CaptureAnchor and anchor.handle is self,
            "CAPTURE_ORIGINAL_BINDING")
        return anchor

    def fail(self, error):
        anchor = self._anchor()
        error = anchor.binding[1].remember(error)
        if anchor.failure is None:
            anchor.failure = error
        anchor.phase = "FAILED"
        return anchor.failure

    def current(self, *, recipient=True):
        anchor = self._anchor()
        if anchor.failure is not None:
            raise anchor.failure
        try:
            require(self._binding is anchor.binding and type(recipient) is bool and
                anchor.phase in ("DECLARING", "COPYING", "FROZEN", "EXPORTING", "EXPORTED", "CLOSED"),
                "CAPTURE_PHASE")
            N._check_history(anchor.graph)
            for graph in anchor.pins:
                N._check_history(graph)
            clock, owner, _context_raw, _start_raw, _raws, pin, work, destination, _output, context = anchor.binding
            clock.current()
            owner.structural()
            require(owner.owner.fence is clock and owner.failure is None and not owner.owner.unknown and owner.errors == [] and
                not any(name in os.environ for name in T.CREDENTIAL_NAMES), "CAPTURE_OWNER_FAILED")
            if recipient:
                T.original._recipient_current(pin)
            else:
                C._crypto_recipient_closed(pin)
            require(work.path == _paths(context["kind"])["tail-public-crypto"] and
                destination.path == _paths(context["kind"])["tail-copied-evidence"] and
                tuple(work.identity) == tuple(context["directories"]["tail-public-crypto"]) and
                tuple(destination.identity) == tuple(context["directories"]["tail-copied-evidence"]), "CAPTURE_ROOTS_CHANGED")
            return anchor
        except BaseException as error:
            raise self.fail(error)

    owner = property(lambda self: self.current().binding[1])
    context = property(lambda self: self.current().binding[9])
    root = property(lambda self: _paths(self.context["kind"])["custody"])

    def pin(self, *values):
        anchor = self.current()
        anchor.pins = (*anchor.pins, N._history_graph(*values))
        self.current()

    def charge(self, count):
        anchor = self.current()
        require(type(count) is int and count >= 0 and anchor.charged_bytes + count <= T.posix.MAX_BYTES,
            "CONSERVATIVE_READER_COPY_BYTES")
        anchor.charged_bytes += count

    def directory(self, relative, expected, *, historical=None, provenance="FIRST_K_OBSERVED_DIRECTORY", mutable=False):
        anchor = self.current()
        require(relative == "" or _relative(relative) == relative, "DIRECTORY_RELATIVE")
        require(type(expected) is tuple and len(set(expected)) == len(expected) and type(mutable) is bool, "DIRECTORY_DECLARATION")
        historical = None if historical is None else tuple(historical)
        old = next((row for row in anchor.directories if row[0] == relative), None)
        if old is not None:
            require(old[3] == tuple(sorted(expected)) and old[4] == historical and old[5:] == (provenance, mutable),
                "DIRECTORY_REDECLARATION")
            return old[1]
        require(anchor.phase == "DECLARING", "DIRECTORY_AFTER_CUT")
        owner = anchor.binding[1]
        path = self.root if not relative else self.root.joinpath(*relative.split("/"))
        directory = C._private(owner, path)
        pin = tuple(directory.identity)
        require(not any(pin == row[2] or relative.casefold() == row[0].casefold() for row in anchor.directories) and
            (historical is None or pin == tuple(historical)), "DIRECTORY_HISTORICAL_PIN_OR_ALIAS")
        _names(owner, directory, expected)
        row = (relative, directory, pin, tuple(sorted(expected)), historical, provenance, mutable)
        anchor.directories = (*anchor.directories, row)
        anchor.pins = (*anchor.pins, N._history_graph(directory.path, row))
        return directory

    def source(self, relative, maximum, *, checksum=None, count=None):
        anchor = self.current()
        _relative(relative)
        parent, _, leaf = relative.rpartition("/")
        directory = next((row[1] for row in anchor.directories if row[0] == parent), None)
        require(directory is not None, "SOURCE_UNDECLARED_DIRECTORY")
        saved = next((row for row in anchor.sources if row[0] == relative), None)
        if saved is None:
            require(anchor.phase == "DECLARING", "NEW_SOURCE_AFTER_CUT")
            reader = _open_file(anchor.binding[1], directory, leaf, maximum)
            self.charge(reader.count)
            pin = R.metadata(C.canonical(reader.raw), anchor.binding[0].clock.role, reader.count)
            require(not any(relative.casefold() == row[0].casefold() or pin == row[3] for row in anchor.sources) and
                not any(pin == row[2] for row in anchor.directories), "SOURCE_IDENTITY_ALIAS")
            returned, _written = _stream(reader, checksum)
            saved = (relative, reader, returned, pin)
            anchor.sources = (*anchor.sources, saved)
        require(type(maximum) is int and 0 <= saved[1].count <= maximum <= H.MAX_ZIP_BYTES and
            (count is None or type(count) is int and saved[1].count == count) and
            (checksum is None or saved[2] == C.digest(checksum)), "SOURCE_DECLARED_BYTES")
        _file_current(saved[1])
        return saved

    def read(self, relative, maximum, *, checksum=None, count=None):
        saved = self.source(relative, maximum, checksum=checksum, count=count)
        require(saved[1].count <= native.LIMIT, "SMALL_SOURCE_BYTES")
        return _stream(saved[1], saved[2], retain=True)

    def declare(self, group, relative, maximum, count, checksum, provenance, *, historical=None):
        anchor = self.current()
        require(anchor.phase == "DECLARING" and group in T.GROUPS and type(provenance) is str and
            not any(row[0] == group and row[1] == relative for row in anchor.declarations), "DECLARATION_ONCE")
        source = self.source(relative, maximum, count=count, checksum=checksum)
        if historical is not None:
            require(type(historical) is dict and O.encoded(historical) == source[1].raw, "ORIGINAL_FILE_METADATA_CHANGED")
        row = (group, relative, maximum, count, checksum, provenance,
            None if historical is None else O.encoded(historical), source)
        anchor.declarations = (*anchor.declarations, row)
        anchor.pins = (*anchor.pins, N._history_graph(row))

    def directories_current(self, *, terminal=False):
        anchor = self.current()
        for _relative_name, directory, pin, names, _historical, _provenance, mutable in anchor.directories:
            directory.verify()
            require(tuple(directory.identity) == pin, "SOURCE_DIRECTORY_IDENTITY_CHANGED")
            if not mutable or anchor.phase in ("DECLARING", "COPYING", "FROZEN"):
                _names(anchor.binding[1], directory, names)
        # Mutable refers ONLY to the owned final crypto work root. Complete
        # allowed additions are checked once after the actual backend return.
        require(type(terminal) is bool, "TERMINAL_TYPE")

    def sources_current(self):
        anchor = self.current()
        for _name, reader, _checksum, _pin in anchor.sources:
            anchor.binding[1].guard()
            _file_current(reader)
        self.directories_current()


def _roster(capture, root, files, directories, pins, provenance):
    """Complete explicit declaration, never recursive enumeration-selected input."""
    require(type(files) is tuple and type(directories) is tuple and "" in directories and
        len(set(directories)) == len(directories) and len(set(files)) == len(files), "ROSTER_DECLARATION")
    all_names = set(files) | set(directories)
    require(len(all_names) == len(files) + len(directories), "ROSTER_FILE_DIRECTORY_ALIAS")
    for relative in sorted(directories, key=lambda value: (value.count("/"), value != "", value)):
        prefix = relative + "/" if relative else ""
        names = tuple(sorted(value[len(prefix):] for value in all_names if value != relative and value.startswith(prefix) and
            "/" not in value[len(prefix):]))
        capture.directory(root + ("/" + relative if relative else ""), names, historical=pins.get(relative), provenance=provenance)


def _existing_declarations(capture, prior, parsed, sealed, before):
    """Actual complete RETURNED19/authority558/B280 inputs, not the old36 subset."""
    capture.pin(prior, parsed, sealed, before)
    _step, carrier, context, manifest, _collected = parsed
    role = capture._binding[0].clock.role
    returned_files = tuple(sorted((*C._CRYPTO_INPUT_LIMITS, "context.json", "crypto-child-result.json", "custody-return.json",
        C._EXPORT_STEP_FILE, C._COLLECT_FILE, *("crypto-service/" + name for name in native.PHASE_FILES))))
    _roster(capture, "returned", returned_files, ("", "control-home", "temporary", "crypto-service"),
        {"": context["directories"]["returned"], "control-home": context["directories"]["control-home"],
            "temporary": context["directories"]["temporary"], "crypto-service": context["directories"]["crypto-service"]},
        "ORIGINAL_P0_CONTEXT_PIN")
    hashes = {**context["filesSha256"], "context.json": O.digest(prior["context"]),
        "crypto-child-result.json": carrier["exporter"]["childSha256"], "custody-return.json": O.digest(prior["carrier"]),
        C._EXPORT_STEP_FILE: O.digest(prior["step"]), C._COLLECT_FILE: O.digest(prior["collect"]),
        **{"crypto-service/" + name: checksum for name, checksum in carrier["exporter"]["phaseSha256"].items()}}
    for name in returned_files:
        limit = (native.ACK_LIMIT if name == "crypto-service/stdout.log" else native.STDERR_LIMIT if name ==
            "crypto-service/stderr.log" else C._CRYPTO_INPUT_LIMITS.get(name, 65536 if name == "context.json" else native.LIMIT))
        source = capture.source("returned/" + name, limit, checksum=hashes[name])
        capture.declare("CRYPTO_SERVICE" if "/" in name else "RETURNED", source[0], limit, source[1].count,
            source[2], "P0_ACTUAL_RETAINED_ORIGINAL")
    _roster(capture, "seal", ("seal-pending.json",), ("",), {}, "SEALED_ORIGINAL_DIRECTORY_CURRENT_PIN")
    capture.declare("SEAL", "seal/seal-pending.json", native.LIMIT, len(capture._binding[4]["seal-pending.json"]),
        O.digest(capture._binding[4]["seal-pending.json"]), "ORIGINAL_SEAL_PENDING_NOT_SELF_SUCCESS")

    authorities = {}
    for side in ("authority-2", "authority-seal"):
        # Preliminary fixed binding inputs use original source-declared paths.
        # No query ID is accepted from an arbitrary filesystem scan.
        path = capture.root / side
        owner = capture.owner
        opened = {}
        for parent in ("", "service", "source-before", "source-after", "acquisition-queries"):
            opened[parent] = C._private(owner, path if not parent else path / parent)
        binding = {}
        for name, maximum in C._HISTORICAL_AUTHORITY_LIMITS.items():
            parent, _, leaf = name.rpartition("/")
            binding[name] = _small(owner, opened[parent], leaf, maximum)
        for directory in reversed(tuple(opened.values())):
            owner.close_one(directory)
        authorities[side] = binding
    index_raw = C._historical_tail_authority_indexes(prior, capture._binding[4]["seal-pending.json"], authorities,
        outcome="success", expected_sha256=capture._binding[0].seed["initialSealSha256"])
    index = C.canonical(index_raw)
    for side, group in (("authority-2", "POST_EXPORT_AUTHORITY"), ("authority-seal", "SEAL_AUTHORITY")):
        rows = tuple(row for row in index["files"] if row["relative"].startswith(side + "/"))
        directories = tuple(row for row in index["directories"] if row["relative"] == side or row["relative"].startswith(side + "/"))
        names = tuple(row["relative"][len(side) + 1:] for row in rows)
        directory_names = tuple("" if row["relative"] == side else row["relative"][len(side) + 1:] for row in directories)
        pins = {"" if row["relative"] == side else row["relative"][len(side) + 1:]: row["historicalPin"]
            for row in directories if row["historicalPin"] is not None}
        _roster(capture, side, names, directory_names, pins, "HISTORICAL_CONTEXT_OR_CHILD_PIN_WHERE_RECORDED")
        for row in rows:
            capture.declare(group, row["relative"], row["maximum"], row["bytes"], row["sha256"],
                "CLOSED_DECLARATION_THEN_ACTUAL_K_READ")

    names = tuple(row["relative"] for row in before["files"])
    dirs = tuple("" if row["relative"] == "." else row["relative"] for row in before["directories"])
    pins = {"" if row["relative"] == "." else row["relative"]: row["readbackIdentity"] for row in before["directories"]}
    _roster(capture, "authority-before", names, dirs, pins, "GENUINE_B_ORIGINAL_READBACK_PIN")
    for row in before["files"]:
        capture.declare("BEFORE_AUTHORITY", "authority-before/" + row["relative"], row["maximum"], row["bytes"],
            row["sha256"], "GENUINE_B_ACTUAL_ORIGINAL", historical=row["metadata"])
    close = capture.read("authority-before/authority-close.json", native.LIMIT,
        checksum=before["authorityCloseSha256"])
    value = C.canonical(close)
    require(value["scope"] == B.CLOSE_SCOPE and value["deadline"] == capture._binding[0].seed and
        value["originalWindow"] == capture.context["originalWindow"] and value["requiredFiles"] == list(names) and
        value["otherFiles"] == C.canonical(capture._binding[4]["before-readback.json"])["files"] and
        value["capture"] == "NOT_K_CAPTURE" and value["originalStepOutcome"] == "NOT_OBSERVED", "B_CLOSED_ORIGINAL_BYTES")
    C._before_input_data(value["inputMetadata"], role)
    query_ids = []
    for side in ("source-before", "acquisition-queries", "source-after"):
        raw = capture.read("authority-before/" + side + "/session-result.json", Q.MAX_RECEIPT_BYTES)
        query_ids.append(tuple(row["id"] for row in C.canonical(raw, Q.MAX_RECEIPT_BYTES)["queries"]))
    required_files, required_dirs = B.member_grammar(*query_ids)
    require(names == required_files and tuple("." if name == "" else name for name in dirs) == required_dirs,
        "B_COMPLETE_FIXED_GRAMMAR")
    capture.sources_current()
    return carrier, manifest


def _budget(clock, *, validation=False):
    """No new time: reserve the unchanged backend finish inside K workEnd."""
    require(type(clock) is _ChildClock and type(validation) is bool, "BUDGET_ORIGINAL_CLOCK")
    local = C.local_value(time.monotonic())
    now = clock.now()
    end = clock.work
    remaining = min(clock.current().binding[6] - local, (end - now) / NS)
    finish = 30 if clock.clock.role == "windows-x64" else 0
    if validation:
        require(remaining > 60 + finish, "VALIDATION_AND_FINISH_NOT_RESERVED")
        return None
    seconds = math.floor(min(240, remaining - finish))
    require(type(seconds) is int and seconds > 0, "EXPORT_AND_FINISH_NOT_RESERVED")
    return seconds


def _process_record(raw):
    """P0 POSIX has this exact spaced spelling, NOT an invented argv ledger."""
    require(type(raw) is bytes and 0 < len(raw) <= native.LIMIT, "PROCESS_BYTES")
    value = T.I.parse(raw, native.LIMIT)
    H._fields(value, {"schema", "waitExitCode", "retired", "interruption"})
    require(type(value["schema"]) is int and value["schema"] == 1 and type(value["waitExitCode"]) is int and
        value["waitExitCode"] == 0 and value["retired"] is True and value["interruption"] is None and
        (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode("ascii") == raw, "PROCESS_ORIGINAL_GRAMMAR")
    return value


def _encryption_status(raw):
    require(type(raw) is bytes and len(raw) <= T.posix.MAX_DIAGNOSTIC_BYTES, "ENCRYPTION_STATUS_BYTES")
    lines = raw.splitlines()
    require(sum(line.startswith(b"[GNUPG:] BEGIN_ENCRYPTION ") for line in lines) == 1 and
        lines.count(b"[GNUPG:] END_ENCRYPTION") == 1 and not any(line.startswith((b"[GNUPG:] FAILURE",
        b"[GNUPG:] ERROR")) for line in lines), "ENCRYPTION_STATUS")


def _read_observed(capture, root, name, maximum, *, group=None, provenance):
    source = capture.source(root + "/" + name, maximum)
    if group is not None:
        capture.declare(group, source[0], maximum, source[1].count, source[2], provenance)
    return source


def _validation_sources(capture, summary_raw):
    """The genuine just-returned NEW validation, including its actual summary."""
    anchor = capture.current()
    _clock, owner, _context_raw, _start_raw, raws, pin, work, _destination, _output, context = anchor.binding
    recipient = pin[0]
    windows = anchor.binding[0].clock.role == "windows-x64"
    root = "tail-public-crypto"
    names = _list_names(owner, work, 32)
    operation_pattern = r"gpg-[0-9a-f]{32}" if windows else r"gpg-[a-z0-9_]+"
    operations = tuple(name for name in names if re.fullmatch(operation_pattern, name))
    results = tuple(name for name in names if re.fullmatch(r"recipient-validation-result-[0-9a-f]{32}\.json", name))
    require(len(operations) == (3 if windows else 2) and len(results) == (1 if windows else 0) and
        set(names) == {"recipient.asc", "recipient.gpg", "recipient-return.json", "gnupg", "tmp", *operations, *results},
        "NEW_VALIDATION_ROOT_ROSTER")
    capture.directory(root, names, historical=context["directories"][root],
        provenance="ACTUAL_SAME_CHILD_VALIDATION_DIRECTORY", mutable=True)
    expected = {"recipient.asc": T.posix.MAX_KEY_BYTES, "recipient.gpg": T.posix.MAX_KEY_BYTES,
        "recipient-return.json": native.LIMIT, **{name: T.windows.MAX_RECORD_BYTES for name in results}}
    for name in ("gnupg", "tmp", *operations):
        temporary = C._private(owner, work.path / name)
        entries = _list_names(owner, temporary, 32)
        identity = tuple(temporary.identity)
        owner.close_one(temporary)
        if name in ("gnupg", "tmp"):
            require((not windows or entries == ()) and all("secret" not in entry.casefold() and
                "private" not in entry.casefold() and entry.casefold() != "secring.gpg" for entry in entries),
                "NEW_VALIDATION_PUBLIC_HOME")
        else:
            require(entries == tuple(sorted(("stdout", "stderr") if windows else
                ("stdout", "stderr", "status", "process.json"))), "NEW_VALIDATION_OPERATION_ROSTER")
        capture.directory(root + "/" + name, entries, historical=identity,
            provenance="ACTUAL_SAME_CHILD_VALIDATION_DIRECTORY")
        for leaf in entries:
            expected[name + "/" + leaf] = native.LIMIT if name in ("gnupg", "tmp") or leaf == "process.json" else \
                T.posix.MAX_DIAGNOSTIC_BYTES
    require(len(expected) == 10 if windows else 11 <= len(expected) <= 75, "NEW_VALIDATION_FILE_COUNT")
    rows = []
    for name, maximum in sorted(expected.items()):
        source = _read_observed(capture, root, name, maximum, group="NEW_RECIPIENT_VALIDATION",
            provenance="ACTUAL_NEW_SAME_CHILD_VALIDATION_ORIGINAL")
        rows.append({"relative": name, "maximum": maximum, "bytes": source[1].count, "sha256": source[2],
            "metadata": C.canonical(source[1].raw)})
    require(capture.read(root + "/recipient-return.json", native.LIMIT) == summary_raw and
        capture.read(root + "/recipient.asc", T.posix.MAX_KEY_BYTES) == raws["recipient-public.asc"] and
        capture.read(root + "/recipient.gpg", T.posix.MAX_KEY_BYTES) == T.posix._public_armor(raws["recipient-public.asc"]),
        "NEW_VALIDATION_ACTUAL_RETURN_AND_PUBLIC_KEY")
    if not windows:
        for name in operations:
            _process_record(capture.read(root + "/" + name + "/process.json", native.LIMIT))
    value = {"root": root, "files": rows, "directories": [{"relative": row[0][len(root):].lstrip("/"),
        "identity": list(row[2]), "members": list(row[3])} for row in capture.current().directories
        if row[0] == root or row[0].startswith(root + "/")], "recipient": C._crypto_recipient_value(pin),
        "totalBytes": sum(row["bytes"] for row in rows)}
    require(value["totalBytes"] <= N.CRYPTO_ORIGINALS_LIMIT, "NEW_VALIDATION_TOTAL_BOUND")
    capture.pin(value)
    return value


def _old_validation(capture, parsed):
    """P0's exact map/opaque summary, not a reconstructed old Recipient."""
    _step, carrier, context, manifest, _collected = parsed
    count = manifest["copy"]["memberCount"] - 4
    require(type(count) is int and 0 < count < T.posix.MAX_MEMBERS - 4, "P0_ORIGINAL_MEMBER_COUNT")
    names = tuple(sorted((*map(C._member_name, range(count)), "primary-map.json", "authority-map.json",
        "recipient-map.json", "copy-map.json")))
    capture.directory("copied-evidence", names, historical=context["directories"]["copied-evidence"],
        provenance="P0_ORIGINAL_COPIED_DIRECTORY")
    raw = capture.read("copied-evidence/recipient-map.json", native.LIMIT,
        checksum=manifest["copy"]["origins"]["RECIPIENT_PRE_EXPORT"])
    value = C.canonical(raw)
    capture.pin(value)
    require(value["scope"] == "INITIAL_CUSTODY_RECIPIENT_COPY_V1" and value["origin"] == "RECIPIENT_PRE_EXPORT" and
        value["primaryCopySha256"] == manifest["copy"]["origins"]["PRIMARY"] and
        value["authorityCopySha256"] == manifest["copy"]["origins"]["AUTHORITY_PRE_EXPORT"] and
        value["destinationIdentity"] == context["directories"]["copied-evidence"] and
        value["destination"] == str(capture.root / "copied-evidence") and
        value["outerChild"] == "STILL_LIVE" and value["exportSaveAuthority"] is False and
        value["freeze"] == "NOT_FINAL_THREE_ORIGIN_FREEZE", "P0_ORIGINAL_VALIDATION_MAP")
    inventory = value["validationInventory"]
    require(inventory["scope"] == "INITIAL_CUSTODY_SAME_CHILD_VALIDATION_ORIGINALS_V1" and
        inventory["root"] == str(capture.root / "public-crypto") and
        inventory["fileCount"] == len(inventory["files"]) and inventory["directoryCount"] == len(inventory["directories"]) and
        type(inventory["fileCount"]) is int and
        (inventory["fileCount"] == 9 if capture._binding[0].clock.role == "windows-x64" else
            10 <= inventory["fileCount"] <= 74), "P0_VALIDATION_INVENTORY")
    require(O.digest(O.encoded({"metadata": value["sourceMetadata"]})) ==
        carrier["copy"]["sourceMetadataSha256"]["RECIPIENT_PRE_EXPORT"], "P0_VALIDATION_METADATA_LINK")
    summaries = [row for row in value["members"] if row["original"] == "recipient-return.json"]
    require(len(summaries) == 1 and summaries[0]["carrier"] == "EMBEDDED_NOT_DISK_ORIGINAL" and
        summaries[0]["sha256"] == value["recipientReturnSha256"] and summaries[0]["member"] in names,
        "P0_ACTUAL_SUMMARY_DECLARATION")
    summary_raw = capture.read("copied-evidence/" + summaries[0]["member"], native.LIMIT,
        checksum=summaries[0]["sha256"], count=summaries[0]["bytes"])
    summary = C.canonical(summary_raw)
    require(summary["scope"] == "INITIAL_CUSTODY_ACTUAL_RECIPIENT_RETURN_V1" and
        summary["contextSha256"] == O.digest(capture._binding[4]["p0-context.json"]) and
        summary["recipient"]["key_sha256"] == manifest["recipient"]["keySha256"] and
        summary["recipient"]["work_identity"] == context["directories"]["public-crypto"] and
        summary["supplierReturned"] is True and summary["outerChild"] == "STILL_LIVE", "P0_ORIGINAL_SUMMARY")
    capture.declare("P0_VALIDATION_MAP_REFERENCE", "copied-evidence/recipient-map.json", native.LIMIT, len(raw),
        O.digest(raw), "EXACT_DUPLICATE_P0_ENCRYPTED_VALIDATION_MAP_REFERENCE")
    capture.pin(summary, inventory)
    return inventory, value["sourceMetadata"], summary["recipient"]


def _old_validation_sources(capture, inventory, metadata, actual_root_names):
    """Retained old validation is checked, not recopied or promoted as new."""
    root, role = "public-crypto", capture._binding[0].clock.role
    nodes = {row[0]: row for row in metadata}
    require(len(nodes) == len(metadata) and all(type(row) is list and len(row) == 5 for row in metadata),
        "P0_VALIDATION_SOURCE_METADATA")
    for row in inventory["directories"]:
        name = row["relative"]
        require(name in nodes and nodes[name][1] is True and nodes[name][2] == row["identity"], "P0_VALIDATION_DIRECTORY")
        capture.directory(root + ("/" + name if name else ""), actual_root_names if name == "" else tuple(row["members"]),
            historical=row["identity"], provenance="ORIGINAL_P0_VALIDATION_DIRECTORY_PIN")
    for row in inventory["files"]:
        name = row["relative"]
        require(name in nodes and nodes[name][1] is False and nodes[name][2] == row["identity"] and
            nodes[name][3] == row["bytes"], "P0_VALIDATION_METADATA_ROSTER")
        source = capture.source(root + "/" + name, row["maximum"], checksum=row["sha256"], count=row["bytes"])
        observed, past = C.canonical(source[1].raw), nodes[name][4]
        if role == "windows-x64":
            require(observed == past, "P0_VALIDATION_WINDOWS_CHANGED")
        else:
            stamp = past["posixStamp"]
            require(type(stamp) is list and len(stamp) == 8 and source[3] == tuple(stamp[:2]) and
                observed == {"device": stamp[0], "inode": stamp[1], "size": stamp[5], "mtime_ns": stamp[6], "ctime_ns": stamp[7]},
                "P0_VALIDATION_POSIX_CHANGED")


def _windows_diagnostic_result(capture, root, result_name, manifest, recipient, listing, encryption, scratch,
        *, group=None):
    """Bind the ACTUAL private result/commands/output metadata, not a receipt."""
    raw = capture.read(root + "/" + result_name, T.windows.MAX_RECORD_BYTES)
    value = C.canonical(raw, T.windows.MAX_RECORD_BYTES)
    capture.pin(value)
    H._fields(value, {"schema", "operation", "result", "retirement", "admittedManifestIdentity", "commands", "failures", "resources"})
    require(type(value["schema"]) is int and value["schema"] == 1 and value["operation"] == "encrypted-export" and
        value["result"] == "READY_FOR_CALLER_SEAL" and value["retirement"] == "KNOWN" and value["failures"] == [] and
        value["admittedManifestIdentity"] == {name: field for name, field in manifest.items() if name != "artifact"} and
        type(value["commands"]) is list and len(value["commands"]) == 2 and type(value["resources"]) is list and
        value["resources"], "WINDOWS_ACTUAL_EXPORT_RESULT")
    for resource in value["resources"]:
        H._fields(resource, {"label", "closed", "quarantined"})
        require(type(resource["label"]) is str and resource["closed"] is True and resource["quarantined"] is False,
            "WINDOWS_EXPORT_RESOURCE_NOT_CLOSED")
    work = capture.root / root
    base = [recipient["executable"], "--no-options", "--homedir", str(work / "gnupg"), "--batch", "--no-tty",
        "--no-autostart", "--no-auto-key-retrieve", "--no-auto-key-import", "--auto-key-locate", "clear", "--disable-dirmngr",
        "--pinentry-mode", "error", "--no-random-seed-file", "--no-default-keyring", "--keyring", "./recipient.gpg",
        "--lock-never", "--no-auto-check-trustdb", "--trust-model", "always"]
    argv = (base + ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint", "--list-keys"],
        base + ["--status-fd", "2", "--cipher-algo", "AES256", "--compress-algo", "none", "--no-encrypt-to", "--recipient",
            recipient["encryption_fingerprint"] + "!", "--output", "-", "--encrypt", str(work / scratch / "evidence.tar.gz")])
    invocations = set()
    for index, (row, command) in enumerate(zip(value["commands"], argv)):
        H._fields(row, {"argv", "invocation", "waitExitCode", "retirement", "outputs", "ownership"})
        require(row["argv"] == command and type(row["invocation"]) is str and
            re.fullmatch(r"[0-9a-f]{32}", row["invocation"]) and row["invocation"] not in invocations and
            type(row["waitExitCode"]) is int and row["waitExitCode"] == 0 and row["retirement"] == "KNOWN",
            "WINDOWS_EXPORT_ORIGINAL_COMMAND")
        invocations.add(row["invocation"])
        ownership = row["ownership"]
        launches = ownership.get("launches")
        require(type(launches) is list and len(launches) == 1, "WINDOWS_EXPORT_ORIGINAL_LAUNCH")
        leaders = [item for item in ownership.get("startedIdentities", []) if item.get("pid") == launches[0].get("pid")]
        require(len(leaders) == 1, "WINDOWS_EXPORT_ORIGINAL_LEADER")
        native.native_record(ownership, {"role": "windows-x64", "job": recipient["job_id"],
            "invocation": row["invocation"], "cwd": str(work)}, leaders[0], command)
        H._fields(row["outputs"], {"stdout", "stderr"})
        for label in ("stdout", "stderr"):
            observation = row["outputs"][label]
            cipher = index == 1 and label == "stdout"
            required = {"identity", "is_directory", "size", "links", "attributes", "creation_100ns", "modified_100ns",
                "change_100ns", "owner_sid", "protected_dacl", *(() if cipher else ("sha256",))}
            H._fields(observation, required)
            maximum = H.MAX_ZIP_BYTES if cipher else T.posix.MAX_DIAGNOSTIC_BYTES
            relative = (scratch + "/" + T.posix.ARTIFACT) if cipher else \
                ((listing if index == 0 else encryption) + "/" + label)
            source = capture.source(root + "/" + relative, maximum,
                checksum=manifest["artifact"]["sha256"] if cipher else observation["sha256"], count=observation["size"])
            if cipher:
                require(source[1].count == manifest["artifact"]["size"], "WINDOWS_EXPORT_ORIGINAL_CIPHERTEXT")
            R.write_close_metadata("windows-x64", {name: field for name, field in observation.items() if name != "sha256"},
                C.canonical(source[1].raw), source[1].count)
    if group is not None:
        source = capture.source(root + "/" + result_name, T.windows.MAX_RECORD_BYTES)
        capture.declare(group, source[0], T.windows.MAX_RECORD_BYTES, source[1].count, source[2],
            "ACTUAL_P0_NATIVE_EXPORT_RESULT_ORIGINAL")
    return O.digest(raw)


def _derived_plaintext(owner, directory):
    """Only real private kind/size/metadata and close, not an original/EOF claim.

    Whole-carrier512MiB is already stricter than the backend568MiB archive
    bound; fixed no-compression encrypted output cannot fit if its input cannot.
    No scratch plaintext is copied, included in the finite cut, or uploaded.
    """
    reader = _open_file(owner, directory, "evidence.tar.gz", H.MAX_ZIP_BYTES)
    require(reader.count > 0, "DERIVED_ARCHIVE_EMPTY")
    _file_current(reader)
    owner.close_one(reader.reader)
    _file_current(reader, closed=True)
    return {"observation": "DERIVED_SCRATCH_KIND_SIZE_ONLY_NOT_ORIGINAL_OR_EOF",
        "metadata": C.canonical(reader.raw), "readerOrdinal": reader.ordinal}


def _export_diagnostics(capture, root, old_names, manifest, recipient, *, p0):
    """Exact terminal complement; first-K pins never become missing producer IDs."""
    anchor = capture.current()
    windows = anchor.binding[0].clock.role == "windows-x64"
    owner = anchor.binding[1]
    observed = C._private(owner, capture.root / root)
    names = _list_names(owner, observed, 64)
    root_pin = tuple(observed.identity)
    owner.close_one(observed)
    old = set(old_names)
    require(old.issubset(names), "EXPORT_REMOVED_VALIDATION_MEMBER")
    additions = set(names) - old
    operations = tuple(sorted(name for name in additions if re.fullmatch(
        r"gpg-[0-9a-f]{32}" if windows else r"gpg-[a-z0-9_]+", name)))
    results = tuple(name for name in additions if re.fullmatch(r"encrypted-export-result-[0-9a-f]{32}\.json", name))
    scratches = tuple(name for name in additions if re.fullmatch(r"export-[0-9a-f]{32}", name)) if windows else ()
    require(len(operations) == 2 and len(results) == (1 if windows else 0) and len(scratches) == (1 if windows else 0) and
        additions == set((*operations, *results, *scratches)), "EXPORT_EXACT_COMPLEMENT")
    if p0:
        capture.directory(root, names, historical=root_pin, provenance="ORIGINAL_P0_VALIDATION_DIRECTORY_PIN")
    else:
        original = next(row for row in anchor.directories if row[0] == root)
        require(root_pin == original[2] and tuple(old_names) == original[3] and original[6] is True,
            "TERMINAL_SAME_CHILD_ROOT")
    listing = encryption = None
    for name in operations:
        probe = C._private(owner, capture.root / root / name)
        members = _list_names(owner, probe, 4)
        pin = tuple(probe.identity)
        owner.close_one(probe)
        if members == tuple(sorted(("stdout", "stderr") if windows else ("stdout", "stderr", "status", "process.json"))):
            require(listing is None, "AMBIGUOUS_EXPORT_LISTING")
            listing = name
        elif members == tuple(sorted(("stderr",) if windows else ("stderr", "status", "process.json"))):
            require(encryption is None, "AMBIGUOUS_EXPORT_ENCRYPTION")
            encryption = name
        else:
            require(False, "EXPORT_OPERATION_ROSTER")
        if p0:
            capture.directory(root + "/" + name, members, historical=pin,
                provenance="FIRST_K_OBSERVED_RETAINED_DIAGNOSTIC")
            for leaf in members:
                _read_observed(capture, root, name + "/" + leaf,
                    native.LIMIT if leaf == "process.json" else T.posix.MAX_DIAGNOSTIC_BYTES,
                    group="P0_EXPORT_DIAGNOSTICS", provenance="FIRST_K_OBSERVED_RETAINED_DIAGNOSTIC")
    require(listing is not None and encryption is not None, "EXPORT_BOTH_OPERATIONS_REQUIRED")
    if not p0:
        # New final self-tail bytes are checked by a distinct post-freeze helper,
        # never registered as new pre-cut sources/declarations or copied to K.
        return names, operations, results, scratches, listing, encryption
    key_listing = capture.read(root + "/" + listing + "/stdout", T.posix.MAX_DIAGNOSTIC_BYTES)
    require(T.posix._key_identity(key_listing, recipient["fingerprint"]) ==
        (recipient["encryption_fingerprint"], recipient["expires_at"]), "P0_EXPORT_KEY_IDENTITY")
    _encryption_status(capture.read(root + "/" + encryption + ("/stderr" if windows else "/status"),
        T.posix.MAX_DIAGNOSTIC_BYTES))
    if windows:
        scratch_directory = capture.directory(root + "/" + scratches[0], (T.posix.ARTIFACT, "evidence.tar.gz"),
            provenance="FIRST_K_OBSERVED_DERIVED_SCRATCH_NOT_ORIGINAL_EVIDENCE")
        shape = _derived_plaintext(owner, scratch_directory)
        anchor.derived = (*anchor.derived, (root + "/" + scratches[0] + "/evidence.tar.gz", shape))
        capture.pin(shape)
        _windows_diagnostic_result(capture, root, results[0], manifest, recipient, listing, encryption, scratches[0],
            group="P0_EXPORT_DIAGNOSTICS")
    else:
        for operation in operations:
            _process_record(capture.read(root + "/" + operation + "/process.json", native.LIMIT))
    return names, operations, results, scratches, listing, encryption


def _p0_diagnostics(capture, parsed):
    inventory, metadata, recipient = _old_validation(capture, parsed)
    roots = [row for row in inventory["directories"] if row["relative"] == ""]
    require(len(roots) == 1 and roots[0]["identity"] == parsed[2]["directories"]["public-crypto"],
        "P0_VALIDATION_ROOT_PIN")
    # Open the recorded P0 root before classifying its literal complement.
    owner = capture.owner
    directory = C._private(owner, capture.root / "public-crypto")
    require(tuple(directory.identity) == tuple(roots[0]["identity"]), "P0_CRYPTO_ORIGINAL_PIN")
    names = _list_names(owner, directory, 64)
    owner.close_one(directory)
    _old_validation_sources(capture, inventory, metadata, names)
    return _export_diagnostics(capture, "public-crypto", tuple(roots[0]["members"]), parsed[3], recipient, p0=True)


@dataclass(frozen=True, repr=False)
class _Freeze:
    capture: object
    snapshot: object
    map_raw: bytes
    cut_raw: bytes
    members: tuple


def _snapshot_file_data(row, role):
    """Compare one supplied Snapshot stamp as DATA, never create a Snapshot."""
    require(type(row) is tuple and len(row) == 5 and type(row[0]) is str and Q._component(row[0]) == row[0] and
        row[1] is False and type(row[2]) is tuple and type(row[3]) is int and
        0 <= row[3] <= H.MAX_ZIP_BYTES and type(row[4]) is bytes, "SNAPSHOT_FILE_ROW")
    value = C.canonical(row[4])
    if role == "windows-x64":
        result = value
    else:
        H._fields(value, {"posixStamp"})
        stamp = value["posixStamp"]
        require(type(stamp) is list and len(stamp) == 8 and all(type(number) is int for number in stamp) and
            stat.S_ISREG(stamp[2]) and not stamp[2] & 0o022 and stamp[3] >= 0 and stamp[4] == 1,
            "SNAPSHOT_POSIX_REGULAR_STAMP")
        result = {"device": stamp[0], "inode": stamp[1], "size": stamp[5], "mtime_ns": stamp[6], "ctime_ns": stamp[7]}
    require(R.metadata(result, role, row[3]) == row[2], "SNAPSHOT_FILE_IDENTITY_SIZE")
    return result


def _destination_snapshot(capture, cut, names):
    """Actual destination-only Snapshot, never the live crypto root/ciphertext."""
    anchor = capture.current()
    clock, owner, destination = anchor.binding[0], anchor.binding[1], anchor.binding[7]
    require(not owner.snapshots and tuple(names) == tuple(sorted(names)), "DESTINATION_ONLY_SNAPSHOT")
    _names(owner, destination, names)
    path, pin = destination.path, tuple(destination.identity)
    end = min(owner.owner.local_end, clock.deadline(900))
    windows = clock.clock.role == "windows-x64"
    if windows:
        resource = owner.acquire("snapshot", lambda: destination.snapshot(max_bytes=cut["totalBytes"],
            max_members=cut["memberCount"] + 1, deadline=end))
        require(type(resource) is native.windows.Snapshot, "DESTINATION_SNAPSHOT_NATIVE_TYPE")
        original = resource.entries
    else:
        resource = None
        try:
            original = native.posix._snapshot(path, cut["totalBytes"], cut["memberCount"] + 1, end)
        except BaseException as error:
            raise owner.remember(error, unknown=True)
    result = C._PrimarySnapshot("INITIAL_K_COMPLETE_TAIL_DESTINATION", path, destination, pin, resource, original,
        C._snapshot_metadata(original, windows), N._history_graph(original, path), windows)
    owner.retain_snapshot(result)
    require(tuple(row[0] for row in result.metadata) == ("", *names) and
        all(not row[1] for row in result.metadata[1:]) and
        sum(row[3] for row in result.metadata[1:]) == cut["totalBytes"], "COMPLETE_DESTINATION_SNAPSHOT")
    C._snapshot_current(owner, result)
    return result


def _freeze_current(result, *, rescan=True):
    saved = _FREEZES.get(id(result))
    require(type(result) is _Freeze and type(saved) is tuple and saved[0] is result,
        "FREEZE_ORIGINAL_HANDLE")
    capture, snapshot, map_raw, cut_raw, members, graph = saved[2:]
    try:
        anchor = capture.current()
        require(result.__dict__ is saved[1] and result.capture is capture and result.snapshot is snapshot and
            result.map_raw == map_raw and result.cut_raw == cut_raw and result.members is members and
            type(rescan) is bool and anchor.phase in ("FROZEN", "EXPORTING", "EXPORTED"), "FREEZE_ORIGINAL_GRAPH")
        N._check_history(graph)
        owner, clock = anchor.binding[1], anchor.binding[0]
        C._snapshot_current(owner, snapshot)
        if rescan:
            owner.guard()
            if snapshot.windows:
                current = snapshot.native.verify()
            else:
                cut = C.canonical(cut_raw)
                current = native.posix._snapshot(snapshot.path, cut["totalBytes"], cut["memberCount"] + 1,
                    min(owner.owner.local_end, clock.deadline(900)))
            require(C._snapshot_metadata(current, snapshot.windows) == snapshot.metadata, "FROZEN_DESTINATION_CHANGED")
            owner.guard()
        capture.sources_current()
        return capture, C.canonical(cut_raw)
    except BaseException as error:
        raise capture.fail(error)


def _freeze_tail(capture, p0, validation):
    """Copy every one of the nine groups; map does not contain/hash itself."""
    anchor = capture.current()
    require(anchor.phase == "DECLARING" and not anchor.copies, "FREEZE_ONCE")
    capture.pin(p0, validation)
    declarations = tuple(sorted(anchor.declarations, key=lambda row: (T.GROUPS.index(row[0]), row[1])))
    require(len({row[1] for row in declarations}) == len(declarations), "TAIL_ORIGINAL_DUPLICATE_GROUP")
    groups = {group: {"memberCount": sum(row[0] == group for row in declarations),
        "totalBytes": sum(row[3] for row in declarations if row[0] == group)} for group in T.GROUPS}
    # Preflight counts/capacity without inventing provisional map bytes/hashes.
    # The actual map is charged exactly once below, before its writer opens.
    windows = anchor.binding[0].clock.role == "windows-x64"
    for name, row in groups.items():
        count = row["memberCount"]
        require(row["totalBytes"] > 0 and (count == T.FIXED_COUNTS[name] if name in T.FIXED_COUNTS else
            count == (4 if windows else 7) if name == "P0_EXPORT_DIAGNOSTICS" else
            count == 10 if windows else 11 <= count <= 75), "PRECOPY_EXACT_GROUP_COUNTS")
    copy_bytes = sum(row[3] for row in declarations)
    require(p0["copy"]["memberCount"] + len(declarations) + 3 <= T.posix.MAX_MEMBERS and
        p0["copy"]["totalBytes"] + copy_bytes + T.MAP_LIMIT <= T.posix.MAX_BYTES and
        anchor.charged_bytes + copy_bytes + T.MAP_LIMIT <= T.posix.MAX_BYTES, "PRECOPY_SHARED_AND_MAP_RESERVATION")
    owner, destination = anchor.binding[1], anchor.binding[7]
    _names(owner, destination, ())
    capture.sources_current()
    capture.pin(declarations)
    anchor.phase = "COPYING"
    for number, declaration in enumerate(declarations):
        group, relative, maximum, count, checksum, provenance, historical_raw, source = declaration
        capture.current()
        capture.charge(count)
        name = C._member_name(number)
        end = min(owner.owner.local_end, anchor.binding[0].deadline(900))
        writer = owner.acquire("writer", lambda: destination.create_file(name, max_bytes=count, deadline=end))
        writer_ordinal = len(owner.rows) - 1
        returned, written = _stream(source[1], checksum, writer=writer)
        require(returned == checksum and owner.rows[writer_ordinal][3:] == (True, True), "TAIL_COPY_WRITER_CLOSE")
        readback = _open_file(owner, destination, name, max(1, count))
        require(readback.count == count and _stream(readback, checksum, close=True)[0] == checksum, "TAIL_COPY_READBACK")
        row = {"member": name, "group": group, "original": relative, "maximum": maximum, "bytes": count,
            "sha256": checksum, "provenance": provenance, "sourceMetadata": C.canonical(source[1].raw),
            "historicalMetadata": None if historical_raw is None else C.canonical(historical_raw),
            "sourceReaderOrdinal": source[1].ordinal, "write": {"metadata": C.canonical(written), "ordinal": writer_ordinal},
            "readback": {"metadata": C.canonical(readback.raw), "ordinal": readback.ordinal},
            "metadataPolicy": R.write_close_metadata(anchor.binding[0].clock.role, C.canonical(written),
                C.canonical(readback.raw), count)}
        require(source[3] != R.metadata(row["readback"]["metadata"], anchor.binding[0].clock.role, count), "TAIL_COPY_ALIAS")
        anchor.copies = (*anchor.copies, row)
        anchor.pins = (*anchor.pins, N._history_graph(row))
        _file_current(readback, closed=True)
    data_bytes = sum(row["bytes"] for row in anchor.copies)
    raw = O.encoded({"schema": 1, "scope": MAP_SCOPE, **_identity_data(anchor.binding[9]),
        "predecessors": anchor.binding[9]["predecessors"], "p0ManifestSha256": O.digest(anchor.binding[4]["p0-manifest.json"]),
        "groups": groups, "members": list(anchor.copies), "payloadMembersExcludingThisMap": len(anchor.copies),
        "payloadBytesExcludingThisMap": data_bytes,
        "directories": [{"relative": row[0], "identity": list(row[2]), "members": list(row[3]),
            "historicalIdentity": None if row[4] is None else list(row[4]), "provenance": row[5],
            "terminalRootMayAddOnlyClosedBackendComplement": row[6]} for row in anchor.directories],
        "derivedNotOriginalOrCopied": [{"relative": relative, **shape} for relative, shape in anchor.derived],
        "originalBReturnedBytes": {name: {"sha256": O.digest(anchor.binding[4][name]),
            "bytes": len(anchor.binding[4][name]), "base64": base64.b64encode(anchor.binding[4][name]).decode("ascii")}
            for name in ("before-index.json", "before-readback.json", "before-writer-close.json")},
        "validationSha256": O.digest(O.encoded(validation)), "mapSelfReference": "EXCLUDED_FROM_OWN_HASH_AND_TOTALS",
        "finalPrivateOriginals": {"disposition": "NOT_DELIVERED", "requiredEvidence": "NOT_USED_AS_QUALIFICATION_ORIGINALS"},
        "productiveAuthority": False, "cacheAuthority": False, "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"})
    require(0 < len(raw) <= T.MAP_LIMIT, "PRIVATE_CUT_MAP_BOUND")
    cut = {"mapSha256": O.digest(raw), "mapBytes": len(raw), "groups": groups,
        "memberCount": len(anchor.copies) + 1, "totalBytes": data_bytes + len(raw)}
    T._cut(cut, p0, anchor.binding[0].clock.role == "windows-x64")
    capture.charge(len(raw))
    map_write = _write_bytes(owner, destination, T.MAP_NAME, raw)
    capture.pin(map_write, cut)
    names = tuple(sorted((T.MAP_NAME, *(row["member"] for row in anchor.copies))))
    complete = _destination_snapshot(capture, cut, names)
    # Independently opened closed readers bind ALL frozen copies, including the
    # map, to the actual post-writer Snapshot, not just their declared hashes.
    expected = {row["member"]: (row["bytes"], row["sha256"], row["readback"]["metadata"]) for row in anchor.copies}
    expected[T.MAP_NAME] = (len(raw), O.digest(raw), map_write["postCloseReadback"])
    snapshotted = {row[0]: _snapshot_file_data(row, anchor.binding[0].clock.role) for row in complete.metadata[1:]}
    readback_graph = N._history_graph(expected, snapshotted)
    for name in names:
        capture.current()
        N._check_history(readback_graph)
        count, checksum, observed = expected[name]
        reader = _open_file(owner, destination, name, max(1, count))
        require(reader.count == count and C.canonical(reader.raw) == observed == snapshotted[name],
            "DESTINATION_POST_CLOSE_AND_SNAPSHOT_METADATA")
        require(_stream(reader, checksum, close=True)[0] == checksum, "DESTINATION_POST_FREEZE_BYTES")
    N._check_history(readback_graph)
    result = _Freeze(capture, complete, raw, O.encoded(cut), anchor.copies)
    _FREEZES[id(result)] = (result, result.__dict__, capture, complete, raw, result.cut_raw, anchor.copies,
        # The genuine owner already pins complete.__dict__ separately. Do not
        # recursively combine that graph with every copy row and exhaust10k.
        N._history_graph(result.__dict__))
    anchor.phase = "FROZEN"
    _freeze_current(result)
    return result


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
    context = _context(context_raw, clock.seed, tuple(C.canonical(context_raw, 65536)["caps"][name]
        for name, _flag in CAP_FIELDS), clock.clock)
    require(type(records) is tuple and len(records) == len(R.PHASE_NAMES) and
        {name for name, _raw in records} == set(R.PHASE_NAMES), "NATIVE_ORIGINAL_PHASE_ROSTER")
    data = dict(records)
    start = _start_fields(data["start.json"], context_raw, context, clock.clock.role)
    terminal, birth = C.canonical(data["result.json"]), C.canonical(data["native-start.json"])
    H._fields(terminal, native.TERMINAL_FIELDS)
    H._fields(birth, {"ownership", "leader", "preparerIdentity", "observedNs"})
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
    child, ack = _child_data(child_raw, context_raw, data["start.json"], minimum, clock.clock), C.canonical(data["stdout.log"])
    H._fields(ack, {"schema", "scope", "invocation", "terminalSha256", "clock", "closedNs", "ownerCloseSha256",
        "metadataResourceCount", "operativeResourceCount"})
    require(type(ack["schema"]) is int and ack["schema"] == 1 and ack["scope"] == ACK_SCOPE and
        ack["invocation"] == start["invocation"] and ack["terminalSha256"] == O.digest(child_raw) and
        O.encoded(ack["clock"]) == O.encoded(O.clock_value(clock.clock)) and type(ack["metadataResourceCount"]) is int and
        ack["metadataResourceCount"] == child["metadataResourceCount"] and
        type(ack["operativeResourceCount"]) is int and 0 < ack["operativeResourceCount"] <= T.posix.MAX_MEMBERS,
        "NATIVE_CHILD_CLOSED_ACK")
    C.digest(ack["ownerCloseSha256"])
    require(minimum <= O.integer(birth["observedNs"]) <= O.integer(terminal["completedNs"]) < start["workEndNs"] and
        minimum <= child["beganNs"] <= child["exportedNs"] <= child["beforeOwnerCloseNs"] <=
        O.integer(ack["closedNs"]) <= terminal["completedNs"] <= O.integer(terminal["finalizedNs"]) < start["finalEndNs"],
        "NATIVE_ORIGINAL_TIME_CHAIN")
    return context, child, data


def _checked_native(parent, result):
    saved = _NATIVE.get(id(result))
    require(type(result) is _NativeReturn and type(saved) is tuple and saved[0] is result,
        "NATIVE_REGISTERED_ORIGINAL")
    owner, owner_dictionary, owner_anchor, original_parent, pins, resources, child_process, graph = saved[2:]
    try:
        parent.current()
        require(result.__dict__ is saved[1] and parent is original_parent and result.parent is parent and result.owner is owner and
            parent._anchor()[3]["native"] is owner and owner.__dict__ is owner_dictionary and owner._anchor() is owner_anchor and
            owner.phase_originals is result and owner.first is parent.clock.reading and owner.fence is parent.clock,
            "NATIVE_PARENT_OWNER_CHANGED")
        owner.known()
        N._check_history(graph)
        require(tuple((row, label, resource) for row, label, resource, _a, _c in owner_anchor.rows) == resources and
            child_process is not None and child_process.returncode == 0, "NATIVE_ACTUAL_RESOURCE_RETURN")
        for directory, path, pin in pins:
            require(directory.path is path and tuple(directory.identity) == pin and
                C._collect_directory_closed(directory, parent.clock.clock.role), "NATIVE_CLOSED_DIRECTORY_PIN")
        context, child, records = _native_phase_data(result.context, result.records, result.child, parent.clock)
        p0_raw = parent._anchor()[1][8]["manifest"]
        p0 = T._p0(p0_raw)
        tail = C.canonical(base64.b64decode(child["manifest"]["base64"], validate=True), T.MANIFEST_LIMIT)
        require(O.encoded(tail["p0"]) == O.encoded({"manifestSha256": O.digest(p0_raw), "artifact": p0["artifact"],
            "privateMemberCount": p0["copy"]["memberCount"], "privateTotalBytes": p0["copy"]["totalBytes"]}) and
            O.encoded(tail["recipient"]) == O.encoded(p0["recipient"]) and
            O.encoded(tail["policy"]) == O.encoded({name: p0["policy"][name] for name in
                ("sha256", "fingerprint", "keySha256", "expiresAt", "retentionDays")}), "NATIVE_TAIL_ORIGINAL_P0_LINK")
        require(result.phase == tuple(context["caps"][name] for name, _flag in CAP_FIELDS) and
            O.integer(result.closed_ns) >= C.canonical(records["result.json"])["finalizedNs"] and
            result.closed_ns < result.phase[2], "NATIVE_PARENT_ORIGINAL_CLOSE_TIME")
        close = C.canonical(result.close)
        H._fields(close, {"schema", "scope", "resources", "retirement", "exportSaveAuthority"})
        require(type(close["schema"]) is int and close["schema"] == 1 and close["scope"] ==
            "INITIAL_K_NATIVE_PARENT_KNOWN_CLOSE_V1" and close["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and
            close["exportSaveAuthority"] is False and close["resources"] == [{"ordinal": number, "label": label,
                "closeAttempted": attempted, "closed": ended} for number, (_row, label, _resource, attempted, ended)
                in enumerate(owner_anchor.rows)], "NATIVE_ACTUAL_PARENT_CLOSE")
        R._resources(close["resources"], carrier=False)
        return owner, context, child, records, close
    except BaseException as error:
        raise original_parent.fail(error)


def _prelaunch_budget(parent, caps):
    parent.currency()
    local = C.local_value(time.monotonic())
    observed = parent.now(limit=caps[1])
    remaining = min(parent.clock.local_end - local, (caps[1] - observed) / NS)
    require(remaining > 60 + (30 if parent.clock.clock.role == "windows-x64" else 0),
        "NATIVE_VALIDATION_FINISH_CANNOT_FIT")


def _native_tail(parent):
    """NEW genuine C native owner; no old clock attachment or phase widening."""
    saved = parent.currency()
    require(saved[3]["phase"] == "B_RETURNED" and saved[3]["native"] is None, "NATIVE_ONCE")
    saved[3]["phase"] = "NATIVE"
    clock = parent.clock
    inputs = _input_values(parent)
    started = parent.now()
    seal_end = continuity.seal_deadline_data(clock.seed)[1]
    caps = _caps(clock.seed, (started, min(started + 210 * NS, seal_end - 45 * NS),
        min(started + 210 * NS, seal_end - 45 * NS) + 45 * NS))
    _prelaunch_budget(parent, caps)
    owner = scope = out = err = child = None
    failure = None
    row = None
    native_known = False
    try:
        owner = C._CustodyOwner(min(clock.local_end, clock.deadline(900, final=True, limit=caps[2])), clock,
            first=clock.reading, cancelled=clock.cancelled)
        saved[3]["native"] = owner  # FIRST returned handle, never a resurrected B owner.
        owner_anchor, dictionary = owner._anchor(), owner.__dict__
        root = owner.open(_paths(saved[1][9][0]["kind"])["custody"])
        # Use the existing explicit-name observer (not the old roster checker,
        # whose allowlist intentionally does not include these NEW siblings).
        require(tuple(native._initializer_names(owner, root)) == C._before_roster(created=True), "NATIVE_PRE_K_ROOT")
        private = owner.child(root, "tail-returned", create=True)
        directories = {"custody": root, "tail-returned": private}
        for name in ("control-home", "temporary", "service"):
            directories[name] = owner.child(private, name, create=True)
        for name in ("tail-public-crypto", "tail-copied-evidence"):
            directories[name] = owner.child(root, name, create=True)
        if clock.clock.role == "windows-x64":
            directories["tail-export-output"] = owner.child(root, "tail-export-output", create=True)
        require(native._initializer_names(owner, root) == _custody_names(tail_output=clock.clock.role == "windows-x64"),
            "NATIVE_EXACT_NEW_ROOT_ROSTER")
        pins = tuple((directory, directory.path, tuple(directory.identity)) for directory in directories.values())
        require(len({pin[2] for pin in pins}) == len(pins), "NATIVE_SETUP_DIRECTORY_ALIAS")
        original_input_pins = C._BEFORE_INPUTS[id(saved[1][3])][6]
        require(tuple(root.identity) == next(pin[3] for pin in original_input_pins if pin[0] == "."),
            "NATIVE_ORIGINAL_CUSTODY_PIN")
        old_step = saved[1][9][0]
        before_close = C.canonical(inputs["before-writer-close.json"])
        context = {"schema": 1, "scope": CONTEXT_SCOPE, "kind": old_step["kind"], "root": str(ROOT),
            "session": str(private.path), "job": uuid.uuid4().hex, "observed": old_step["observed"],
            "originalWindow": old_step["originalWindow"], "deadline": clock.seed,
            "caps": dict(zip((name for name, _flag in CAP_FIELDS), caps)), "parentFirstNs": clock.first,
            "parentFirstLocal": clock.first_local, "beforeClosedNs": before_close["closedNs"],
            "originalServiceJob": old_step["originalServiceJob"],
            "predecessors": {"cryptoStepSha256": O.digest(inputs["crypto-step-pending.json"]),
                "collectSha256": O.digest(inputs["collect-close.json"]), "sealSha256": O.digest(inputs["seal-pending.json"]),
                "beforeAuthoritySha256": C.canonical(inputs["before-index.json"])["authorityCloseSha256"],
                "originalWindowSha256": O.digest(O.encoded(old_step["originalWindow"]))},
            "filesSha256": {name: O.digest(raw) for name, raw in inputs.items()},
            "directories": {name: list(directories[name].identity) if name in directories else None for name in DIRECTORIES},
            "inheritedContext": Q._inherited_context(), "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        context_raw = O.encoded(context)
        _context(context_raw, clock.seed, caps, clock.clock)
        input_graph = N._history_graph(context, inputs, tuple(pin[1] for pin in pins))
        for name, raw in (*inputs.items(), ("context.json", context_raw)):
            require(owner.write(private, name, raw) == raw, "NATIVE_CONTEXT_INPUT_READBACK")
            parent.now(limit=caps[1])
            N._check_history(input_graph)
        capture_end = min(owner.local_end, clock.deadline(900, final=True, limit=caps[2]))
        invocation = uuid.uuid4().hex
        environment = native.processes.ownership_environment(native.recipient_environment(private.path), context["job"],
            invocation, str(private.path), str(private.path / "control-home"), allow_new_context=True)
        require(not any(name in environment for name in T.CREDENTIAL_NAMES), "NATIVE_CHILD_TOKEN_FREE")
        start = {"schema": 1, "scope": START_SCOPE, "contextSha256": O.digest(context_raw),
            "argv": _command(O.digest(context_raw), clock.seed, caps), "cwd": str(ROOT), "role": clock.clock.role,
            "job": context["job"], "invocation": invocation, "state": str(private.path),
            "home": str(private.path / "control-home"), "inheritedContext": {name: environment[name] for name in Q._CONTEXT},
            **dict(zip((name for name, _flag in CAP_FIELDS), caps)), "exitCode": None,
            "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"}
        start_raw = O.encoded(start)
        _start_fields(start_raw, context_raw, context, clock.clock.role)
        service = directories["service"]
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
            command = _command(O.digest(context_raw), clock.seed, caps, row["launchMinimumNs"])
            row["launchArgv"], row["launchAttempted"] = command, True
            child = scope.spawn(command, str(ROOT), environment, stdout=out, stderr=err)
            require(child.stdout is None and child.stderr is None, "NATIVE_ACTUAL_PRIVATE_SINKS")
            birth = scope.description()
            birth_graph = N._history_graph(birth)
            leaders = [value for value in birth.get("startedIdentities", []) if value.get("pid") == child.pid]
            require(len(leaders) == 1, "NATIVE_ACTUAL_BIRTH")
            row["leader"] = dict(leaders[0])
            native.lifetime(row["leader"], clock.clock.role)
            birth_raw = owner.write(service, "native-start.json", {"ownership": birth, "leader": row["leader"],
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
        require(native._initializer_names(owner, private) == tuple(sorted((*INPUT_LIMITS, "context.json",
            "tail-child-result.json", "control-home", "temporary", "service"))) and
            native._initializer_names(owner, service) == tuple(sorted(R.PHASE_NAMES)) and
            native._initializer_names(owner, root) == _custody_names(tail_output=True), "NATIVE_FINAL_PRIVATE_ROSTER")
        resources = tuple((row, label, resource) for row, label, resource, _a, _c in owner_anchor.rows)
        owner.freeze()
        owner.close()
        closed = owner.known()
        closed_ns = parent.now(final=True, limit=caps[2])
        close_raw = O.encoded({"schema": 1, "scope": "INITIAL_K_NATIVE_PARENT_KNOWN_CLOSE_V1",
            "resources": [{"ordinal": number, "label": label, "closeAttempted": attempted, "closed": ended}
                for number, (_row, label, _resource, attempted, ended) in enumerate(closed.rows)],
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False})
        result = _NativeReturn(parent, owner, context_raw, child_raw, records, caps, close_raw, closed_ns)
        owner.phase_originals = result
        _NATIVE[id(result)] = (result, result.__dict__, owner, dictionary, owner_anchor, parent, pins, resources, child,
            N._history_graph(result.__dict__, tuple(pin[1] for pin in pins)))
        _checked_native(parent, result)
        saved[3]["phase"] = "NATIVE_CLOSED"
        return result
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("k-native-parent", error)
            failure = owner._anchor().failure
    finally:
        if owner is not None and not owner.closed:
            try:
                owner.close()
            except BaseException as error:
                if failure is None:
                    failure = error
    raise parent.fail(failure)


_TERMINALS = {}


@dataclass(eq=False, repr=False)
class _TerminalAnchor:
    handle: object
    binding: tuple
    rows: tuple = ()
    graphs: tuple = ()


class _TerminalRead:
    """Actual post-freeze readers; NEVER add terminal bytes to the private cut."""
    __slots__ = ("_binding",)

    def __init__(self, capture, description):
        require(type(self) is _TerminalRead and id(self) not in _TERMINALS, "TERMINAL_NEW_HANDLE")
        directories, allowed, derived = {}, {}, []
        names, operations, results, scratches, listing, encryption = description
        anchor = capture.current()
        require(anchor.phase == "EXPORTED", "TERMINAL_AFTER_ACTUAL_EXPORT_ONLY")
        owner = anchor.binding[1]
        root = "tail-public-crypto"
        directory = C._private(owner, capture.root / root)
        original = next(row for row in anchor.directories if row[0] == root)
        require(tuple(directory.identity) == original[2], "TERMINAL_ORIGINAL_ROOT")
        directories[root] = (directory, directory.path, tuple(directory.identity), tuple(names))
        _names(owner, directory, tuple(names))
        for operation in operations:
            expected = ("stdout", "stderr") if anchor.binding[0].clock.role == "windows-x64" else \
                ("stdout", "stderr", "status", "process.json")
            if operation == encryption:
                expected = tuple(name for name in expected if name != "stdout")
            parent = C._private(owner, capture.root / root / operation)
            _names(owner, parent, expected)
            directories[root + "/" + operation] = (parent, parent.path, tuple(parent.identity), expected)
            allowed.update({root + "/" + operation + "/" + name:
                native.LIMIT if name == "process.json" else T.posix.MAX_DIAGNOSTIC_BYTES for name in expected})
        for result in results:
            allowed[root + "/" + result] = T.windows.MAX_RECORD_BYTES
        for scratch in scratches:
            parent = C._private(owner, capture.root / root / scratch)
            expected = ("evidence.tar.gz", T.posix.ARTIFACT)
            _names(owner, parent, expected)
            directories[root + "/" + scratch] = (parent, parent.path, tuple(parent.identity), expected)
            # Plaintext is a derived, deliberately unexported scratch file.
            # Its shape is checked, never copied or mislabeled an original.
            derived.append(_derived_plaintext(owner, parent))
            allowed[root + "/" + scratch + "/" + T.posix.ARTIFACT] = H.MAX_ZIP_BYTES
        self._binding = (capture, tuple(directories.items()), tuple(allowed.items()), tuple(derived))
        _TERMINALS[id(self)] = _TerminalAnchor(self, self._binding, graphs=(N._history_graph(self._binding),))

    def _anchor(self):
        saved = _TERMINALS.get(id(self))
        require(type(self) is _TerminalRead and type(saved) is _TerminalAnchor and saved.handle is self and
            self._binding is saved.binding, "TERMINAL_ORIGINAL_BINDING")
        for graph in saved.graphs:
            N._check_history(graph)
        saved.binding[0].current()
        return saved

    capture = property(lambda self: self._anchor().binding[0])
    allowed = property(lambda self: dict(self._anchor().binding[2]))

    root = property(lambda self: self.capture.root)

    def pin(self, *values):
        anchor = self._anchor()
        anchor.graphs = (*anchor.graphs, N._history_graph(*values))

    def source(self, relative, maximum, *, checksum=None, count=None):
        anchor = self._anchor()
        allowed = dict(anchor.binding[2])
        require(relative in allowed and maximum == allowed[relative], "TERMINAL_FIXED_READER_ONLY")
        existing = next((value for value in anchor.rows if value[0] == relative), None)
        if existing is None:
            name, _, leaf = relative.rpartition("/")
            directory = dict(anchor.binding[1])[name][0]
            reader = _open_file(self.capture.owner, directory, leaf, maximum)
            digest, _written = _stream(reader, checksum)
            existing = (relative, reader, digest,
                R.metadata(C.canonical(reader.raw), self.capture._binding[0].clock.role, reader.count))
            anchor.rows = (*anchor.rows, existing)
        value = existing
        require((checksum is None or value[2] == C.digest(checksum)) and
            (count is None or type(count) is int and value[1].count == count), "TERMINAL_ORIGINAL_BYTES")
        _file_current(value[1])
        return value

    def read(self, relative, maximum, *, checksum=None, count=None):
        value = self.source(relative, maximum, checksum=checksum, count=count)
        return _stream(value[1], value[2], retain=True)

    def current(self):
        anchor = self._anchor()
        for name, (directory, path, pin, expected) in anchor.binding[1]:
            require(directory.path is path and path == self.root.joinpath(*name.split("/")) and tuple(directory.identity) == pin,
                "TERMINAL_DIRECTORY_CHANGED")
            _names(self.capture.owner, directory, expected)
        for _relative, reader, checksum, _pin in anchor.rows:
            _stream(reader, checksum)


def _terminal_check(capture, validation, manifest):
    """Final backend additions are private self-tail, not new qualifying inputs."""
    rows = [row for row in validation["directories"] if row["relative"] == ""]
    require(len(rows) == 1, "TERMINAL_VALIDATION_ROOT")
    description = _export_diagnostics(capture, "tail-public-crypto", tuple(rows[0]["members"]), manifest,
        validation["recipient"], p0=False)
    terminal = _TerminalRead(capture, description)
    _names_value, operations, results, scratches, listing, encryption = description
    prefix = "tail-public-crypto/"
    listing_raw = terminal.read(prefix + listing + "/stdout", T.posix.MAX_DIAGNOSTIC_BYTES)
    recipient = validation["recipient"]
    require(T.posix._key_identity(listing_raw, recipient["fingerprint"]) ==
        (recipient["encryption_fingerprint"], recipient["expires_at"]), "TERMINAL_KEY_IDENTITY_CHANGED")
    windows = capture._binding[0].clock.role == "windows-x64"
    for name, maximum in terminal.allowed.items():
        terminal.source(name, maximum)
    _encryption_status(terminal.read(prefix + encryption + ("/stderr" if windows else "/status"),
        T.posix.MAX_DIAGNOSTIC_BYTES))
    if windows:
        _windows_diagnostic_result(terminal, "tail-public-crypto", results[0], manifest, recipient,
            listing, encryption, scratches[0])
    else:
        for name in operations:
            _process_record(terminal.read(prefix + name + "/process.json", native.LIMIT))
    terminal.current()
    return terminal


def _child_directories(owner, context):
    result = {}
    for name in DIRECTORIES:
        pin = context["directories"][name]
        if pin is None:
            require(name == "tail-export-output" and owner.owner.first.clock.role != "windows-x64",
                "CHILD_ONLY_ABSENT_POSIX_OUTPUT")
            continue
        result[name] = C._private(owner, _paths(context["kind"])[name])
        require(tuple(result[name].identity) == tuple(pin), "CHILD_ORIGINAL_DIRECTORY_PIN")
    return result


def _child_readback(owner, directories, context_raw, start_raw, raws, *, exported=False):
    private, service = directories["tail-returned"], directories["service"]
    require(type(exported) is bool, "CHILD_READBACK_STAGE")
    _names(owner, directories["custody"], _custody_names(
        tail_output=exported or owner.owner.first.clock.role == "windows-x64"))
    for name, raw in (*raws.items(), ("context.json", context_raw)):
        require(_small(owner, private, name, 65536 if name == "context.json" else INPUT_LIMITS[name],
            checksum=O.digest(raw)) == raw, "CHILD_ORIGINAL_INPUT_READBACK")
    require(_small(owner, service, "start.json", native.LIMIT, checksum=O.digest(start_raw)) == start_raw,
        "CHILD_ORIGINAL_START_READBACK")
    for name, directory in directories.items():
        directory.verify()
        require(tuple(directory.identity) == tuple(C.canonical(context_raw, 65536)["directories"][name]),
            "CHILD_INPUT_DIRECTORY_CHANGED")
    for name in ("control-home", "temporary"):
        _names(owner, directories[name], ())


CHILD_FIELDS = {"schema", "scope", "contextSha256", "startSha256", "invocation", "clock", "bootDigest", "launchMinimumNs",
    "beganNs", "metadataLastNs", "metadataCloseSha256", "metadataResourceCount", "validationStartedNs", "validationReturnedNs",
    "exportedNs", "beforeOwnerCloseNs", "recipientReturnSha256", "recipient", "cut", "freezeMetadataSha256", "outputIdentity",
    "manifest", "retirement", "finalPrivateOriginals", "testAcceptance", "productiveAuthority", "cacheAuthority",
    "exportSaveAuthority", "budgetAcceptance"}
TAIL_MANIFEST_FIELDS = {"schema", "scope", "kind", "selection", "source", "github", "policy", "recipient", "p0",
    "predecessors", "cut", "transport", "finalPrivateOriginals", "testAcceptance", "productiveAuthority", "cacheAuthority",
    "exportSaveAuthority", "budgetAcceptance", "artifact"}


def _child_data(raw, context_raw, start_raw, minimum, clock):
    value = C.canonical(raw)
    context = C.canonical(context_raw, 65536)
    graph = N._history_graph(value, context, clock)
    start = _start_fields(start_raw, context_raw, context, clock.role)
    H._fields(value, CHILD_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == CHILD_SCOPE and
        value["contextSha256"] == O.digest(context_raw) and value["startSha256"] == O.digest(start_raw) and
        value["invocation"] == start["invocation"] and value["clock"] == O.clock_value(clock) and
        value["bootDigest"] == context["originalWindow"]["originalBootDigest"] and
        type(value["launchMinimumNs"]) is int and value["launchMinimumNs"] == minimum and
        type(value["metadataResourceCount"]) is int and 0 < value["metadataResourceCount"] <= T.posix.MAX_MEMBERS,
        "CHILD_RETURN_ORIGINAL_BINDINGS")
    previous = minimum
    for name in ("beganNs", "metadataLastNs", "validationStartedNs", "validationReturnedNs", "exportedNs", "beforeOwnerCloseNs"):
        previous = H._integer(value[name], previous, start["workEndNs"] - 1)
    for name in ("metadataCloseSha256", "recipientReturnSha256", "freezeMetadataSha256"):
        C.digest(value[name])
    R.identity(value["outputIdentity"], clock.role)
    if context["directories"]["tail-export-output"] is not None:
        require(value["outputIdentity"] == context["directories"]["tail-export-output"], "CHILD_WINDOWS_ORIGINAL_OUTPUT")
    H._fields(value["manifest"], {"bytes", "sha256", "base64"})
    try:
        manifest_raw = base64.b64decode(value["manifest"]["base64"], validate=True)
    except (TypeError, ValueError):
        require(False, "CHILD_MANIFEST_ENCODING")
    require(type(value["manifest"]["bytes"]) is int and 0 < len(manifest_raw) == value["manifest"]["bytes"] <= T.MANIFEST_LIMIT and
        base64.b64encode(manifest_raw).decode("ascii") == value["manifest"]["base64"] and
        O.digest(manifest_raw) == value["manifest"]["sha256"], "CHILD_MANIFEST_BYTES")
    manifest = C.canonical(manifest_raw, T.MANIFEST_LIMIT)
    T.original._graph(manifest)
    H._fields(manifest, TAIL_MANIFEST_FIELDS)
    require(type(manifest["schema"]) is int and manifest["schema"] == 1 and manifest["scope"] == T.SCOPE and
        O.encoded({name: manifest[name] for name in ("kind", "selection", "source", "github")}) ==
        O.encoded({name: field for name, field in _identity_data(context).items() if name not in ("originalWindow", "deadline")}) and
        manifest["predecessors"] == context["predecessors"] and
        O.encoded(manifest["cut"]) == O.encoded({"mapName": T.MAP_NAME, **value["cut"]}) and
        O.encoded(manifest["recipient"]) == O.encoded(value["recipient"]) and value["retirement"] == "PENDING_CHILD_CLOSE" and
        value["finalPrivateOriginals"] == manifest["finalPrivateOriginals"] == {"disposition": "NOT_DELIVERED",
            "coverage": "EXCLUDED_FROM_K_AND_R", "requiredEvidence": "NOT_USED_AS_QUALIFICATION_ORIGINALS"}, "CHILD_TAIL_MANIFEST_LINK")
    p0 = manifest["p0"]
    H._fields(p0, {"manifestSha256", "artifact", "privateMemberCount", "privateTotalBytes"})
    require(p0["manifestSha256"] == context["filesSha256"]["p0-manifest.json"], "CHILD_P0_MANIFEST_HASH")
    T._artifact(p0["artifact"])
    H._integer(p0["privateMemberCount"], 1, T.posix.MAX_MEMBERS - 1)
    H._integer(p0["privateTotalBytes"], 1, T.posix.MAX_BYTES)
    T._cut(value["cut"], {"copy": {"memberCount": p0["privateMemberCount"], "totalBytes": p0["privateTotalBytes"]}},
        clock.role == "windows-x64")
    H._fields(manifest["policy"], {"sha256", "fingerprint", "keySha256", "expiresAt", "retentionDays"})
    H._fields(manifest["recipient"], {"fingerprint", "encryptionFingerprint", "keySha256", "expiresAt"})
    policy, recipient = manifest["policy"], manifest["recipient"]
    require(policy["sha256"] == T.S.POLICY_SHA256 and type(policy["retentionDays"]) is int and
        policy["retentionDays"] == 14 and policy["fingerprint"] == recipient["fingerprint"] and
        policy["keySha256"] == recipient["keySha256"] and
        all(type(recipient[name]) is str and re.fullmatch(r"[0-9A-F]{40}", recipient[name]) for name in
            ("fingerprint", "encryptionFingerprint")), "CHILD_EXACT_PUBLIC_RECIPIENT")
    C.digest(recipient["keySha256"])
    H._integer(policy["expiresAt"], 1, O.clocks.UINT64)
    H._integer(recipient["expiresAt"], policy["expiresAt"], O.clocks.UINT64)
    require(manifest["transport"] == {"artifactMember": T.ARTIFACT_MEMBER, "manifestMember": T.MANIFEST_MEMBER,
        "backendArtifact": T.posix.ARTIFACT, "backendManifest": T.posix.MANIFEST}, "CHILD_LITERAL_TRANSPORT")
    for name in ("testAcceptance", "productiveAuthority", "cacheAuthority", "exportSaveAuthority", "budgetAcceptance"):
        expected = _nonacceptance()[name]
        require(type(value[name]) is type(manifest[name]) is type(expected) and value[name] == manifest[name] == expected,
            "CHILD_NO_SELF_ACCEPTANCE")
    T._artifact(manifest["artifact"])
    N._check_history(graph)
    return value


def _child_work(clock, context_raw, start_raw, raws, minimum, metadata_close, metadata_last):
    context = _context(context_raw, clock.seed, clock.caps, clock.clock)
    start = _start_fields(start_raw, context_raw, context, clock.clock.role)
    prior, parsed, sealed, before = _child_inputs(context, raws, clock.reading)
    policy, public = C.I._policy(raws["candidate-policy.json"], int(time.time()))
    require(public == raws["recipient-public.asc"] and O.digest(raws["candidate-policy.json"]) == T.S.POLICY_SHA256 and
        policy["recipient"]["sha256"] == O.digest(public), "CHILD_CURRENT_PUBLIC_POLICY")
    original_type = C.A.gate.GateEligibility if context["kind"] == "gate" else C.A.stages.BootstrapMatch
    original, before_match = original_type(raws["original-match.json"]), original_type(raws["before-match.json"])
    graph = N._history_graph(context, start, raws, prior, parsed, sealed, before, policy, original.__dict__, before_match.__dict__)
    owner = capture = pin = terminal = frozen = None
    failure = None
    try:
        owner = C._PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
        clock.attach(owner)
        directories = _child_directories(owner, context)
        _child_readback(owner, directories, context_raw, start_raw, raws)
        work, destination = directories["tail-public-crypto"], directories["tail-copied-evidence"]
        output_path = _paths(context["kind"])["tail-export-output"]
        output = directories["tail-export-output"] if clock.clock.role == "windows-x64" else output_path
        _names(owner, work, ())
        _names(owner, destination, ())
        _budget(clock, validation=True)
        validating = clock.now()
        if clock.clock.role == "windows-x64":
            recipient = T.windows.validate_recipient(public, policy["recipient"]["fingerprint"], work, job_id=context["job"])
        else:
            recipient = T.posix.validate_recipient(directories["tail-returned"].path / "recipient-public.asc",
                policy["recipient"]["fingerprint"], work.path)
        pin = T.original._recipient_pin(recipient, clock.clock.role == "windows-x64",
            destination if clock.clock.role == "windows-x64" else destination.path, output)
        returned = clock.now()
        require(recipient.work_identity == tuple(context["directories"]["tail-public-crypto"]) and
            recipient.fingerprint == policy["recipient"]["fingerprint"] and recipient.key_sha256 == O.digest(public) and
            policy["expiresAt"] <= recipient.expires_at and (recipient.work is work and recipient.job_id == context["job"]
            if clock.clock.role == "windows-x64" else recipient.work_dir == work.path and recipient.home == work.path / "gnupg"),
            "CHILD_GENUINE_SAME_PROCESS_RECIPIENT")
        summary_raw = O.encoded({"schema": 1, "scope": "INITIAL_K_ACTUAL_NEW_RECIPIENT_RETURN_V1",
            "contextSha256": O.digest(context_raw), "startSha256": O.digest(start_raw), "invocation": start["invocation"],
            "clock": O.clock_value(clock.clock), "bootDigest": clock.current().binding[2], "launchMinimumNs": minimum,
            "beganNs": clock.first, "metadataLastNs": metadata_last, "validationStartedNs": validating,
            "validationReturnedNs": returned, "recipient": C._crypto_recipient_value(pin), "supplierReturned": True,
            "outerChild": "STILL_LIVE", "exportSaveAuthority": False})
        _write_bytes(owner, work, "recipient-return.json", summary_raw)
        capture = _Capture(clock, owner, context_raw, start_raw, raws, pin, work, destination, output)
        capture.pin(context, start, prior, parsed, sealed, before, policy, original.__dict__, before_match.__dict__)
        validation = _validation_sources(capture, summary_raw)
        _existing_declarations(capture, prior, parsed, sealed, before)
        _p0_diagnostics(capture, parsed)
        frozen = _freeze_tail(capture, T._p0(raws["p0-manifest.json"]), validation)
        output_directory = directories.get("tail-export-output")

        def check():
            N._check_history(graph)
            clock.now()
            _freeze_current(frozen)
            T.original._recipient_current(pin)
            current, actual_public = C.I._policy(raws["candidate-policy.json"], int(time.time()))
            require(current == policy and actual_public == public and policy["notBefore"] <=
                context["observed"]["firstUseAt"] <= int(time.time()) < policy["expiresAt"] <= recipient.expires_at,
                "CHILD_POLICY_CHANGED_OR_EXPIRED")
            clock.now()

        def read_manifest():
            nonlocal output_directory
            if output_directory is None:
                output_directory = C._private(owner, output_path)
            _names(owner, output_directory, (T.posix.ARTIFACT, T.posix.MANIFEST))
            return _small(owner, output_directory, T.posix.MANIFEST, T.MANIFEST_LIMIT)

        check()
        export_timeout = _budget(clock)
        capture.current().phase = "EXPORTING"
        manifest_raw = T.export_encrypted(destination if clock.clock.role == "windows-x64" else destination.path,
            output, recipient, p0_manifest_raw=raws["p0-manifest.json"], original_match=original, before_match=before_match,
            event_raw=raws["event.json"], policy_raw=raws["candidate-policy.json"],
            service_job_id=C._collect_service_job(context["originalServiceJob"])[0], predecessors=context["predecessors"],
            cut=C.canonical(frozen.cut_raw), check=check, read_manifest=read_manifest, timeout_seconds=export_timeout)
        require(type(manifest_raw) is bytes, "CHILD_ACTUAL_EXPORT_BYTE_RETURN")
        manifest = C.canonical(manifest_raw, T.MANIFEST_LIMIT)
        manifest_graph = N._history_graph(manifest)
        exported = clock.now()
        capture.current().phase = "EXPORTED"
        check()
        require(read_manifest() == manifest_raw and manifest["cut"] == {"mapName": T.MAP_NAME, **C.canonical(frozen.cut_raw)},
            "CHILD_EXACT_EXPORTED_CUT")
        terminal = _terminal_check(capture, validation, manifest)
        ciphertext = _open_file(owner, output_directory, T.posix.ARTIFACT, H.MAX_ZIP_BYTES)
        require(ciphertext.count == manifest["artifact"]["size"] and
            _stream(ciphertext, manifest["artifact"]["sha256"], close=True)[0] == manifest["artifact"]["sha256"],
            "CHILD_CLOSED_OUTPUT_BYTES")
        _child_readback(owner, directories, context_raw, start_raw, raws, exported=True)
        terminal.current()
        check()
        before_closed = clock.now()
        result_raw = O.encoded({"schema": 1, "scope": CHILD_SCOPE, "contextSha256": O.digest(context_raw),
            "startSha256": O.digest(start_raw), "invocation": start["invocation"], "clock": O.clock_value(clock.clock),
            "bootDigest": clock.current().binding[2], "launchMinimumNs": minimum, "beganNs": clock.first,
            "metadataLastNs": metadata_last, "metadataCloseSha256": O.digest(metadata_close),
            "metadataResourceCount": len(C.canonical(metadata_close)["resources"]), "validationStartedNs": validating,
            "validationReturnedNs": returned, "exportedNs": exported, "beforeOwnerCloseNs": before_closed,
            "recipientReturnSha256": O.digest(summary_raw), "recipient": manifest["recipient"], "cut": C.canonical(frozen.cut_raw),
            "freezeMetadataSha256": O.digest(O.encoded({"metadata": C._crypto_metadata(frozen.snapshot)})),
            "outputIdentity": list(output_directory.identity), "manifest": {"bytes": len(manifest_raw),
                "sha256": O.digest(manifest_raw), "base64": base64.b64encode(manifest_raw).decode("ascii")},
            "retirement": "PENDING_CHILD_CLOSE", "finalPrivateOriginals": manifest["finalPrivateOriginals"],
            **{name: _nonacceptance()[name] for name in ("testAcceptance", "productiveAuthority", "cacheAuthority",
                "exportSaveAuthority", "budgetAcceptance")}})
        _child_data(result_raw, context_raw, start_raw, minimum, clock.clock)
        _write_bytes(owner, directories["tail-returned"], "tail-child-result.json", result_raw)
        terminal.current()
        check()
        N._check_history(manifest_graph)
        closed_raw = owner.finish()
        capture.current(recipient=False).phase = "CLOSED"
        _closed_files(owner)
        N._check_history(graph)
        N._check_history(manifest_graph)
        # FIRST/RAW guard after the actual owner close; ACK is still provisional
        # until this child really exits0 and the parent retires the whole domain.
        closed = clock.now(minimum=before_closed, limit=clock.work)
        require(all(row[3] and row[4] for row in owner.rows), "CHILD_ALL_FILE_CLOSES")
        return {"schema": 1, "scope": ACK_SCOPE, "invocation": start["invocation"],
            "terminalSha256": O.digest(result_raw), "clock": O.clock_value(clock.clock), "closedNs": closed,
            "ownerCloseSha256": O.digest(closed_raw), "metadataResourceCount": len(C.canonical(metadata_close)["resources"]),
            "operativeResourceCount": len(owner.rows)}, clock, clock.work
    except BaseException as error:
        failure = error if owner is None else owner.remember(error)
    finally:
        if owner is not None and not owner.finished and not owner.owner.unknown:
            try:
                owner.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
    raise clock.fail(failure)


def tail_child(context_hash, minimum, cancelled, seed, caps):
    """The fixed native child: FIRST caps precede the FIRST metadata owner/read."""
    owner = clock = None
    failure = None
    try:
        local = C.local_value(time.monotonic())
        first = O.clocks.observe()
        graph = N._history_graph(first, seed, caps)
        O.clocks.validate_reading(first)
        boot = C.digest(continuity.boot_digest(first.clock.role))
        N._check_history(graph)
        require(first.nanoseconds >= O.integer(minimum) and callable(cancelled) and
            not any(name in os.environ for name in T.CREDENTIAL_NAMES), "CHILD_FIRST_OR_TOKEN")
        clock = _ChildClock(first, local, boot, cancelled, seed, caps)
        owner = C._PrimaryOwner(native.Owner(clock.local_end, clock, first=first, cancelled=cancelled))
        clock.attach(owner)
        kind, _primary = N.location()
        private = C._private(owner, _paths(kind)["tail-returned"])
        context_raw = _small(owner, private, "context.json", 65536, checksum=context_hash)
        context = _context(context_raw, seed, caps, first.clock)
        require(context["kind"] == kind, "CHILD_FIXED_KIND")
        directories = _child_directories(owner, context)
        require(tuple(private.identity) == tuple(directories["tail-returned"].identity), "CHILD_FIRST_PIN_CHANGED")
        start_raw = _small(owner, directories["service"], "start.json", native.LIMIT)
        inherited = Q._inherited_context()
        _start(start_raw, context_raw, context, minimum, first, inherited)
        raws = {name: _small(owner, private, name, maximum, checksum=context["filesSha256"][name])
            for name, maximum in INPUT_LIMITS.items()}
        _child_inputs(context, raws, first)
        _child_readback(owner, directories, context_raw, start_raw, raws)
        frame_graph = N._history_graph(context, raws, inherited)
        metadata_close = owner.finish()
        metadata_last = clock.now()
        N._check_history(frame_graph)
        _closed_files(owner)
        clock.bind(context_raw, start_raw, raws, inherited)
        return _child_work(clock, context_raw, start_raw, raws, minimum, metadata_close, metadata_last)
    except BaseException as error:
        failure = error if owner is None else owner.remember(error)
    finally:
        if owner is not None and not owner.finished and not owner.owner.unknown:
            try:
                owner.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
    if clock is not None:
        raise clock.fail(failure)
    raise failure


_PENDING = {}
PRIVATE_INPUT_NAMES = tuple(sorted((*INPUT_LIMITS, "context.json", "tail-child-result.json",
    "control-home", "temporary", "service")))
PRIVATE_CLOSED_NAMES = tuple(sorted((*PRIVATE_INPUT_NAMES, H.PRIVATE_CARRIER_CLOSE, H.FILE)))


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
        require(parent._anchor()[3]["phase"] == "CARRIER_CLOSED" and parent._anchor()[3]["writer"] is None,
            "PENDING_WRITER_ONCE_AFTER_CARRIER")
        owner = C._PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
        parent._anchor()[3]["writer"] = owner
        directory = C._private(owner, _paths(close["kind"])["tail-returned"])
        path, identity = directory.path, tuple(directory.identity)
        native_result = carrier.native
        _native_owner, context, _child, _records, _native_close = _checked_native(parent, native_result)
        require(identity == tuple(context["directories"]["tail-returned"]), "PENDING_ORIGINAL_PRIVATE_DIRECTORY")
        _names(owner, directory, PRIVATE_INPUT_NAMES)
        carrier_write = _write_bytes(owner, directory, H.PRIVATE_CARRIER_CLOSE, carrier.raw)
        parent.currency()
        prepared = parent.now()
        before = parent._binding[0]
        originals = parent._binding[8]
        value = {"schema": 1, "scope": H.SCOPE, **_identity_data(context),
            "originals": {"eventSha256": O.digest(originals["event"]), "policySha256": O.digest(originals["policy"]),
                "matchSha256": O.digest(originals["original-match"])}, "predecessors": close["predecessors"],
            "manifests": close["manifests"], "cutMapSha256": close["cutMapSha256"],
            "members": [{name: row[name] for name in ("name", "bytes", "sha256")} for row in close["files"]],
            "totalBytes": close["totalBytes"], "zipBytes": close["zipBytes"],
            "knownCloses": {"beforeReadbackSha256": O.digest(before.readback),
                "beforeCloseWriterSha256": O.digest(before.writer_close), "tailChildCloseSha256": O.digest(native_result.close),
                "carrierCloseSha256": O.digest(carrier.raw)},
            "times": {**close["times"], "pendingPreparedNs": prepared}, "writerReturn": "PENDING_OWNER_CLOSE",
            **_nonacceptance()}
        raw = H.encode_pending(value)
        graph = N._history_graph(value, carrier_write, path)
        pending_write = _write_bytes(owner, directory, H.FILE, raw)
        write_graph = N._history_graph(pending_write)
        require(_small(owner, directory, H.PRIVATE_CARRIER_CLOSE, H.LIMIT, checksum=O.digest(carrier.raw)) == carrier.raw and
            _small(owner, directory, H.FILE, H.LIMIT, checksum=O.digest(raw)) == raw, "PENDING_BOTH_RECORDS_READBACK")
        _names(owner, directory, PRIVATE_CLOSED_NAMES)
        parent.currency()
        N._check_history(graph)
        N._check_history(write_graph)
        closed_raw = owner.finish()
        closed_ns = parent.now()
        _closed_files(owner)
        _checked_carrier(carrier)
        result = _Pending(parent, carrier, raw, closed_raw)
        _PENDING[id(result)] = (result, result.__dict__, parent, carrier, raw, closed_raw, owner, owner._anchor(),
            directory, path, identity, closed_ns, N._history_graph(result.__dict__, value, pending_write, carrier_write, path))
        parent._anchor()[3]["phase"] = "PENDING_CLOSED"
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
        require(result.__dict__ is dictionary and result.parent is parent and result.carrier is carrier and
            result.raw == raw and result.close == closed and owner._anchor() is original and
            parent._anchor()[3]["writer"] is owner and parent._anchor()[3]["phase"] == "PENDING_CLOSED",
            "PENDING_RETURN_CHANGED")
        parent.current()
        parent._binding[11].returned(_ATTEMPTS, parent._binding[10], result)
        N._check_history(graph)
        _closed_files(owner)
        require(directory.path is path and tuple(directory.identity) == identity and
            C._collect_directory_closed(directory, parent.clock.clock.role), "PENDING_WRITER_DIRECTORY_CLOSE")
        _original_parent, carrier_value = _checked_carrier(carrier)
        value = H.parse_pending(raw)
        require(value["knownCloses"]["carrierCloseSha256"] == O.digest(carrier.raw) and
            value["knownCloses"]["tailChildCloseSha256"] == O.digest(carrier.native.close) and
            value["manifests"] == carrier_value["manifests"] and value["times"]["pendingPreparedNs"] <= closed_ns <
            continuity.seal_deadline_data(parent.clock.seed)[1], "PENDING_KNOWN_CLOSE_LINKS")
        return parent, H.output_values(raw)
    except BaseException as error:
        raise parent.fail(error)


def _append_seven(values, check):
    """Distinct fixed runner-output append; old continuity shapes unchanged."""
    require(type(values) is dict and set(values) == {H.OUTPUT, *(name for name, _environment, _flag in B.SEED_FIELDS)},
        "SEVEN_OUTPUT_FIELDS")
    C.digest(values[H.OUTPUT])
    continuity.seal_deadline_data({name: values[name] for name, _environment, _flag in B.SEED_FIELDS})
    raw = "".join(name + "=" + values[name] + "\n" for name in sorted(values)).encode("ascii")
    require(len(raw) <= 4096 and callable(check) and not continuity.QUARANTINE, "SEVEN_OUTPUT_BOUND")
    check()
    target = Path(os.environ.get("GITHUB_OUTPUT", ""))
    parent = Path(os.environ.get("RUNNER_TEMP", ""))
    require(target.is_absolute() and parent.is_absolute() and ".." not in target.parts and
        target.parent == parent / "_runner_file_commands" and
        re.fullmatch(r"set_output_[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", target.name),
        "SEVEN_OUTPUT_FIXED_RUNNER_PATH")
    parents = tuple((path, path.lstat()) for path in target.parents)
    for path, info in parents:
        require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "SEVEN_OUTPUT_PARENT")
    before = target.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == 0 and
        not getattr(before, "st_file_attributes", 0) & 0x400 and (os.name == "nt" or before.st_uid == os.geteuid()),
        "SEVEN_OUTPUT_EMPTY_FILE")
    attributes = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_file_attributes")
    identity = tuple(getattr(before, name, None) for name in attributes)

    def same_file(current, count):
        return tuple(getattr(current, name, None) for name in attributes) == identity and current.st_size == count

    check()
    descriptor = os.open(target, os.O_RDWR | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0) |
        getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    failure = None
    try:
        require(same_file(os.fstat(descriptor), 0), "SEVEN_OUTPUT_OPEN_CHANGED")
        check()
        written = os.write(descriptor, raw)
        require(type(written) is int and written == len(raw), "SEVEN_OUTPUT_SHORT_WRITE")
        os.fsync(descriptor)
        check()
        require(os.lseek(descriptor, 0, os.SEEK_SET) == 0 and os.read(descriptor, len(raw) + 1) == raw,
            "SEVEN_OUTPUT_EXACT_READBACK")
        require(same_file(target.lstat(), len(raw)) and same_file(os.fstat(descriptor), len(raw)), "SEVEN_OUTPUT_REPLACED")
        for path, info in parents:
            after = path.lstat()
            require(os.path.samestat(info, after) and stat.S_ISDIR(after.st_mode) and
                not getattr(after, "st_file_attributes", 0) & 0x400, "SEVEN_OUTPUT_PARENT_CHANGED")
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
    """Actual pending-writer close, single seven-output append, two late checks."""
    __slots__ = ("_binding",)

    def __init__(self, result):
        parent, values = _checked_pending(result)
        try:
            require(type(self) is _OutputFence and id(self) not in _OUTPUTS and
                not any(saved[1][0] is result for saved in _OUTPUTS.values()), "OUTPUT_ONCE")
            limit = continuity.seal_deadline_data(parent.clock.seed)[1]
            value = {"schema": 1, "scope": "INITIAL_BEFORE_UPLOAD_PENDING_ORIGINAL_STEP_RETURN_V1", **values,
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
            limit == continuity.seal_deadline_data(parent.clock.seed)[1], "OUTPUT_PENDING_CHANGED")
        return parent, limit

    def _guard(self):
        saved = self._begin()
        try:
            require(saved[2]["phase"] == "APPENDING" and saved[2]["checks"] == 0, "OUTPUT_APPEND_PHASE")
            parent, limit = self._current(saved)
            parent.currency()
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
            _append_seven(saved[1][2], self._guard)
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
            parent.currency()
            observed = parent.now(final=True, limit=original_limit)
            self._current(saved)
            return observed
        except BaseException as error:
            raise self._fail(saved, error)
        finally:
            saved[2]["busy"] = False


def before_and_tail(kind, cancelled):
    """The sole fixed parent route; B and K are one same-interpreter attempt."""
    original = _ENTRY
    attempt = original.begin(_ATTEMPTS)
    parent = None
    try:
        before = C.before_authority(kind, cancelled)
        original.check(_ATTEMPTS, attempt)
        parent = _Parent(before, attempt, original)
        returned = _native_tail(parent)
        carrier = _copy_carrier(parent, returned)
        pending = _retain_pending(carrier)
        original.complete(_ATTEMPTS, attempt, pending)
        _checked_pending(pending)
        return _OutputFence(pending).append()
    except BaseException as error:
        raise original.fail(error) if parent is None else parent.fail(error)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="operation", required=True)
    parent = commands.add_parser("before-and-tail", allow_abbrev=False)
    parent.add_argument("--kind", required=True, choices=("gate", "worker"))
    child = commands.add_parser("_tail-child", allow_abbrev=False)
    child.add_argument("--context-sha256", required=True)
    child.add_argument("--minimum-ns", required=True)
    for name, _environment, flag in B.SEED_FIELDS:
        child.add_argument(flag, required=True, dest=name)
    for name, flag in CAP_FIELDS:
        child.add_argument(flag, required=True, dest=name)
    args = parser.parse_args()
    try:
        require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
            "ISOLATED_INTERPRETER_REQUIRED")
        if args.operation == "before-and-tail":
            native.guarded(lambda signals: before_and_tail(args.kind, lambda: native.cancellation(signals)))
        else:
            C.digest(args.context_sha256)
            require(re.fullmatch(r"0|[1-9][0-9]{0,19}", args.minimum_ns), "MINIMUM_DECIMAL")
            minimum = O.integer(int(args.minimum_ns))
            seed = {name: getattr(args, name) for name, _environment, _flag in B.SEED_FIELDS}
            decimals = tuple(getattr(args, name) for name, _flag in CAP_FIELDS)
            require(all(type(value) is str and re.fullmatch(r"[1-9][0-9]{0,19}", value) for value in decimals), "CAP_DECIMALS")
            caps = _caps(seed, tuple(int(value) for value in decimals))
            require(sys.argv[1:] == _command(args.context_sha256, seed, caps, minimum)[5:], "EXACT_FIXED_CHILD_ARGUMENTS")
            native.guarded(lambda signals: tail_child(args.context_sha256, minimum,
                lambda: native.cancellation(signals), seed, caps))
        return 0
    except BaseException:
        print("INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
