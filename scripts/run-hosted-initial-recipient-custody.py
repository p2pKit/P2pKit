#!/usr/bin/env python3
"""Fixed Stage1 evidence custody; source preparation, not productive admission.

Only the authentic gate/initializer successful Steps may supply the fixed
primary handoff. Historical bytes do not restore a retired owner, Recipient or
HTTP lease. Actual current acquisition, token-free encryption, original native
retirement and separate successful seal/upload Steps remain mandatory.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import importlib.util
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("_initial_recipient_custody_primary",
    SCRIPTS / "run-hosted-initial-recipient.py")
N = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = N
_spec.loader.exec_module(N)
native, O, I, Q, A, C = N.native, N.O, N.I, N.Q, N.acquisition, N.continuity

PRIMARY_OUTCOME = "P2PKIT_INITIAL_PRIMARY_OUTCOME"
PRIMARY_RESULT = "P2PKIT_INITIAL_PRIMARY_RESULT_SHA256"
PRIMARY_HANDOFF = "P2PKIT_INITIAL_PRIMARY_HANDOFF_SHA256"
MAX_BYTES, MAX_MEMBERS = native.posix.MAX_BYTES, native.posix.MAX_MEMBERS
PRIMARY_SCOPE = "INITIAL_RECIPIENT_CUSTODY_PRIMARY_COPY_V1"
ORIGINS = ("PRIMARY", "AUTHORITY_PRE_EXPORT", "RECIPIENT_PRE_EXPORT")
WINDOW_SCOPE = "INITIAL_RECIPIENT_CUSTODY_ABSOLUTE_WINDOW_V1"
WINDOW_NAMES = ("workEndNs", "nativeFinalEndNs", "readEndNs", "sealEndNs", "uploadEndNs", "afterEndNs")
AUTHORITY_PINS = ("I/authority", *("I/authority/" + name for name in
    ("control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")))
INITIALIZER_DIRECTORIES = ("I", "I/canonical-init", "I/control-home", "I/temporary", "I/state",
    "I/state/gradle-home", "I/state/evidence", "I/state/cancellations")
_WINDOWS = {}


def require(value, code):
    I.require(value, "INITIAL_CUSTODY_" + code)


def fields(value, names, code):
    require(type(value) is dict and set(value) == set(names.split()), code)
    return value


def digest(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "DIGEST")
    return value


def local_value(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "LOCAL_CLOCK")
    return value


def canonical(raw, maximum=native.LIMIT):
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "RECORD_LIMIT")
    value = O.parse(raw)
    require(type(value) is dict and O.encoded(value) == raw, "CANONICAL_RECORD")
    return value


def _paths(kind):
    actual, primary = N.location()
    require(kind == actual and kind in ("gate", "worker"), "ACTUAL_JOB_KIND")
    roots = {"P": primary}
    if kind == "worker":
        recipient = N._recipient_path()
        roots.update(E=primary.with_name(primary.name + "-entry"), R=recipient,
            S=recipient.with_name(recipient.name + "-output"), I=N._receiving_path(),
            T=N._step_path(), C=N._crypto_originals_path())
    base = roots["P"] if kind == "gate" else roots["I"]
    return roots, base.with_name(base.name + "-handoff"), primary.with_name(primary.name + "-custody")


def _same(actual, expected, code):
    require(O.encoded(actual) == O.encoded(expected), code)


@dataclass(frozen=True, repr=False)
class Primary:
    """Authenticated Step bytes/metadata only, never a live primary owner."""
    kind: str
    role: str
    handoff_raw: bytes
    inventory_raw: bytes
    roots: tuple
    directories: tuple
    files: tuple
    embedded: tuple
    result_sha256: str


def _worker_directory_provenance(key, role):
    if key in AUTHORITY_PINS:
        return "ORIGINAL_AUTHORITY_NATIVE_PIN"
    if re.fullmatch(r"I/authority/(source-before|source-after|acquisition-queries)/(query-home|query-[0-9a-f]{32})", key):
        return "ORIGINAL_AUTHORITY_DECLARED_DIRECTORY"
    if key in INITIALIZER_DIRECTORIES:
        return "ORIGINAL_INITIALIZER_NATIVE_PIN"
    if key == "T":
        return "SENDER_STEP_RECEIVER_READBACK_NATIVE_PIN"
    if key == "C":
        return "CRYPTO_SIDECAR_RECEIVER_READBACK_NATIVE_PIN"
    if key.startswith("R/crypto/"):
        tail = key.removeprefix("R/crypto/")
        require(tail in ("gnupg", "tmp") or re.fullmatch(
            r"gpg-[0-9a-f]{32}" if role == "windows-x64" else r"gpg-[a-z0-9_]+", tail), "WORKER_CRYPTO_DIRECTORY")
        return "AUTHENTICATED_ORIGINAL_CRYPTO_NATIVE_PIN"
    require(key.split("/", 1)[0] in ("P", "E", "R", "S"), "WORKER_DIRECTORY_PRODUCER")
    return "RECEIVER_READBACK_NATIVE_PIN"


def _worker_file_provenance(key):
    if key.startswith("R/crypto/"):
        return "AUTHENTICATED_CRYPTO_DECLARATION"
    if re.fullmatch(r"I/authority/(source-before|source-after|acquisition-queries)/(owner\.json|"
            r"query-[0-9a-f]{32}/(start\.json|baseline\.json|stdout\.log|stderr\.log|result\.json))", key):
        return "ORIGINAL_AUTHORITY_QUERY_DECLARATION"
    return "ACTUAL_RETAINED_BYTES"


def _worker_inventory(index, roots, role, expected_result):
    fields(index, "schema scope roots source github clock senderSha256 recipientStepSha256 "
        "recipientCryptoOriginalsSha256 initializationSha256 authoritySha256 workerIdentitySha256 files "
        "fileCount fileCounts directories directoryCount directoryCounts totalBytes copyState liveRecipient "
        "budgetAcceptance testAcceptance exportSaveAuthority", "WORKER_INDEX_FIELDS")
    require(type(index["schema"]) is int and index["schema"] == 1 and index["scope"] == N.WORKER_INVENTORY_SCOPE,
        "WORKER_INDEX_SCOPE")
    _same(index["roots"], [{"group": key, "path": str(path)} for key, path in roots.items()], "WORKER_ROOTS")
    require(index["initializationSha256"] == expected_result and index["copyState"] == "ORIGINAL_BYTES_NOT_COPIED" and
        index["liveRecipient"] == "NOT_TRANSFERRED" and index["budgetAcceptance"] == "NOT_ADMITTED" and
        index["testAcceptance"] == "NOT_PERFORMED" and index["exportSaveAuthority"] is False,
        "WORKER_INDEX_AUTHORITY")
    for name in ("senderSha256", "recipientStepSha256", "recipientCryptoOriginalsSha256", "initializationSha256",
            "authoritySha256", "workerIdentitySha256"):
        digest(index[name])
    require(type(index["files"]) is list and type(index["directories"]) is list, "WORKER_INDEX_ROSTERS")
    files, directories = [], []
    for row in index["files"]:
        fields(row, "relative parent maximum bytes sha256 provenance", "WORKER_FILE_FIELDS")
        expected = N._worker_file(row["relative"], row["maximum"], row["bytes"], row["sha256"], row["provenance"])
        _same(row, expected, "WORKER_FILE")
        require(row["provenance"] == _worker_file_provenance(row["relative"]), "WORKER_FILE_PROVENANCE")
        files.append((row["relative"], row["maximum"], row["bytes"], row["sha256"], row["provenance"]))
    for row in index["directories"]:
        fields(row, "relative parent path identity provenance", "WORKER_DIRECTORY_FIELDS")
        key = N._worker_relative(row["relative"])
        target = roots[key.split("/", 1)[0]].joinpath(*key.split("/")[1:])
        require(row["parent"] == (key.rsplit("/", 1)[0] if "/" in key else None) and
            row["path"] == str(target) and row["provenance"] == _worker_directory_provenance(key, role) and
            (row["identity"] is None) == (row["provenance"] == "ORIGINAL_AUTHORITY_DECLARED_DIRECTORY"),
            "WORKER_DIRECTORY_PROVENANCE")
        identity = None if row["identity"] is None else tuple(native.directory_identity(row["identity"], role))
        directories.append((key, identity, row["provenance"]))
    windows = role == "windows-x64"
    declared_names = {row[0] for row in directories}
    require(set(AUTHORITY_PINS + INITIALIZER_DIRECTORIES).issubset(declared_names), "WORKER_REQUIRED_PIN_PATHS")
    crypto_directories = {key for key in declared_names if key.startswith("R/crypto/")}
    require({"R/crypto/gnupg", "R/crypto/tmp"}.issubset(crypto_directories) and
        len(crypto_directories) == (5 if windows else 4), "WORKER_CRYPTO_DIRECTORY_COUNT")
    crypto_count = sum(row[4] == "AUTHENTICATED_CRYPTO_DECLARATION" for row in files)
    require(crypto_count == 9 if windows else 10 <= crypto_count <= 74, "WORKER_CRYPTO_COUNT")
    counts = {key: sum(row[0].split("/", 1)[0] == key for row in files) for key in roots}
    dir_counts = {key: sum(row[0].split("/", 1)[0] == key for row in directories) for key in roots}
    _same(counts, {"P": 284, "E": 281, "R": 498 + crypto_count, "S": 3, "I": 293, "T": 1, "C": 1},
        "WORKER_FILE_COUNTS")
    _same(dir_counts, {"P": 58, "E": 58, "R": 110 if windows else 109, "S": 1, "I": 66, "T": 1, "C": 1},
        "WORKER_DIRECTORY_COUNTS")
    _same(index["fileCounts"], counts, "WORKER_FILE_COUNTS")
    _same(index["directoryCounts"], dir_counts, "WORKER_DIRECTORY_COUNTS")
    require(type(index["fileCount"]) is int and index["fileCount"] == len(files) == 1361 + crypto_count and
        type(index["directoryCount"]) is int and index["directoryCount"] == len(directories) == (295 if windows else 294) and
        sum(row[1] is None for row in directories) == 51, "WORKER_COMPLETE_ROSTERS")
    total = sum(row[2] for row in files)
    require(type(index["totalBytes"]) is int and index["totalBytes"] == total <= MAX_BYTES, "WORKER_TOTAL_BYTES")
    return tuple(directories), tuple(files)


def _gate_inventory(index, roots, pins, expected_result):
    fields(index, "schema scope root contextSha256 initialOriginalsSha256 gateEligibilitySha256 source github policy "
        "directories files copyState nestedNativePins exportSaveAuthority", "GATE_INDEX_FIELDS")
    require(type(index["schema"]) is int and index["schema"] == 1 and index["scope"] == N.GATE_INVENTORY_SCOPE and
        index["root"] == str(roots["P"]) and index["initialOriginalsSha256"] == expected_result and
        index["copyState"] == "ORIGINAL_BYTES_NOT_COPIED" and index["nestedNativePins"] == "NOT_CAPTURED" and
        index["exportSaveAuthority"] is False, "GATE_INDEX_SCOPE")
    for name in ("contextSha256", "initialOriginalsSha256", "gateEligibilitySha256"):
        digest(index[name])
    require(type(index["files"]) is list and len(index["files"]) == 281 and
        type(index["directories"]) is list and len(index["directories"]) == 58 and type(pins) is list and len(pins) == 7,
        "GATE_COMPLETE_ROSTERS")
    original_pins = {}
    for row in pins:
        fields(row, "path identity", "GATE_NATIVE_PIN_FIELDS")
        require(type(row["path"]) is str and row["path"] not in original_pins, "GATE_DUPLICATE_NATIVE_PIN")
        original_pins[row["path"]] = tuple(native.directory_identity(row["identity"], "linux-x64"))
    require(set(original_pins) == {str(roots["P"] / name) for name in
        ("", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")},
        "GATE_NATIVE_PIN_ROSTER")
    directories, files = [], []
    for relative in index["directories"]:
        require(type(relative) is str, "GATE_DIRECTORY_NAME")
        key = "P" if relative == "." else "P/" + relative
        N._worker_relative(key)
        identity = original_pins.get(str(roots["P"].joinpath(*key.split("/")[1:])))
        directories.append((key, identity, "ORIGINAL_NATIVE_PIN" if identity is not None else "ORIGINAL_DECLARED_DIRECTORY"))
    represented = {str(roots["P"].joinpath(*key.split("/")[1:])) for key, identity, _ in directories if identity is not None}
    require(represented == set(original_pins) and sum(identity is not None for _, identity, _ in directories) == 7,
        "GATE_ALL_ORIGINAL_PINS_REQUIRED")
    for row in index["files"]:
        fields(row, "relative maximum bytes sha256", "GATE_FILE_FIELDS")
        key = N._worker_relative("P/" + row["relative"])
        require(type(row["maximum"]) is int and type(row["bytes"]) is int and
            0 <= row["bytes"] <= row["maximum"] <= native.LIMIT and row["maximum"] > 0,
            "GATE_FILE_LIMIT")
        digest(row["sha256"])
        require(row["bytes"] != 0 or row["sha256"] == O.digest(b""), "GATE_EMPTY_HASH")
        files.append((key, row["maximum"], row["bytes"], row["sha256"], "ORIGINAL_PRIMARY_DECLARATION"))
    require(sum(row[2] for row in files) <= MAX_BYTES, "GATE_TOTAL_BYTES")
    return tuple(directories), tuple(files)


def primary_record(kind, role, roots, path, identity, raw, *, outcome, result_sha256, handoff_sha256):
    """Closed Step-carrier grammar, not filesystem or current-authority proof."""
    require(kind in ("gate", "worker") and role in O.clocks.DOMAINS and
        (kind != "gate" or role == "linux-x64") and outcome == "success", "PRIMARY_SUCCESS_REQUIRED")
    digest(result_sha256)
    require(O.digest(raw) == digest(handoff_sha256), "PRIMARY_HANDOFF_HASH")
    value = canonical(raw)
    common = "schema scope directory directoryIdentity inventory originalClose writerReturn originalStepOutcome budgetAcceptance exportSaveAuthority"
    fields(value, common + (" gateEligibility originalClosedNs clock bootDigest preludeSha256 originalNativeDirectories"
        if kind == "gate" else " embeddedOriginals"), "PRIMARY_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == (N.GATE_HANDOFF_SCOPE if kind == "gate" else N.WORKER_HANDOFF_SCOPE) and
        value["directory"] == str(path) and value["writerReturn"] == "PENDING_OWNER_CLOSE" and
        value["originalStepOutcome"] == "NOT_OBSERVED" and value["budgetAcceptance"] == "NOT_ADMITTED" and
        value["exportSaveAuthority"] is False, "PRIMARY_PENDING_RECORD")
    _same(value["directoryIdentity"], list(native.directory_identity(list(identity), role)), "PRIMARY_DIRECTORY_CHANGED")
    index, embedded = value["inventory"], ()
    if kind == "gate":
        directories, files = _gate_inventory(index, roots, value["originalNativeDirectories"], result_sha256)
        digest(value["bootDigest"])
        digest(value["preludeSha256"])
        O.integer(value["originalClosedNs"])
        fields(value["originalClose"], "retirement resources", "GATE_ORIGINAL_CLOSE")
        labels = value["originalClose"]["resources"]
        require(value["originalClose"]["retirement"] == "KNOWN" and type(labels) is list and 0 < len(labels) <= 10000 and
            all(type(label) is str and label in ("directory", "writer", "stdout", "stderr", "native-scope") for label in labels),
            "GATE_ORIGINAL_CLOSE")
        require(O.digest(O.encoded(value["gateEligibility"])) == index["gateEligibilitySha256"], "GATE_MATCH_BINDING")
    else:
        directories, files = _worker_inventory(index, roots, role, result_sha256)
        _same(value["originalClose"], {"authority": "KNOWN_RESOURCE_CLOSE_ONLY", "receiving": "KNOWN_RESOURCE_CLOSE_ONLY"},
            "WORKER_ORIGINAL_CLOSE")
        require(type(value["embeddedOriginals"]) is list and len(value["embeddedOriginals"]) == 2, "WORKER_EMBEDDED_ROSTER")
        saved = []
        for row, name in zip(value["embeddedOriginals"], ("receiving-authority-return.json", "initialization-history.json")):
            fields(row, "name bytes sha256 rawBase64", "WORKER_EMBEDDED_FIELDS")
            require(row["name"] == name and type(row["rawBase64"]) is str, "WORKER_EMBEDDED_NAME")
            try:
                blob = base64.b64decode(row["rawBase64"], validate=True)
            except (ValueError, TypeError):
                require(False, "WORKER_EMBEDDED_ENCODING")
            require(type(row["bytes"]) is int and 0 < len(blob) == row["bytes"] <= native.LIMIT and
                base64.b64encode(blob).decode("ascii") == row["rawBase64"] and O.digest(blob) == digest(row["sha256"]),
                "WORKER_EMBEDDED_CHANGED")
            saved.append((name, blob))
        embedded = tuple(saved)
        require(O.digest(embedded[0][1]) == index["authoritySha256"], "WORKER_AUTHORITY_RETURN_BINDING")
        require(N._worker_handoff_record(path, identity, O.encoded(index), *(blob for _, blob in embedded)) == raw,
            "WORKER_ORIGINAL_HANDOFF")
    names = tuple(row[0] for row in directories) + tuple(row[0] for row in files)
    dir_names = {row[0] for row in directories}
    require(len(names) == len(set(names)) == len({name.casefold() for name in names}) and
        tuple(row[0] for row in directories) == tuple(sorted(dir_names)) and
        tuple(row[0] for row in files) == tuple(sorted(row[0] for row in files)) and
        all(key in dir_names for key in roots) and
        all(key.rsplit("/", 1)[0] in dir_names for key in names if "/" in key), "PRIMARY_NAMES")
    pins = [row[1] for row in directories if row[1] is not None]
    require(len(pins) == len(set(pins)), "PRIMARY_DIRECTORY_ALIAS")
    return Primary(kind, role, raw, O.encoded(index), tuple(roots.items()), directories, files, embedded, result_sha256)


def schedule(kind, original_job_basis, start):
    """Unchanged finite arithmetic; supplied integers do not admit job timing."""
    require(kind in ("gate", "worker"), "WINDOW_KIND")
    basis, start = O.integer(original_job_basis), O.integer(start)
    job_end = O.integer(basis + (360 if kind == "gate" else 1200) * O.NS)
    require(start >= basis and job_end >= 180 * O.NS, "WINDOW_JOB_START")
    work = min(O.integer(start + 240 * O.NS), job_end - 180 * O.NS)
    ends = (work, work + 45 * O.NS, work + 75 * O.NS, work + 105 * O.NS,
        work + 165 * O.NS, work + 180 * O.NS)
    require(start < work and ends[-1] <= job_end and all(O.integer(value) == value for value in ends), "WINDOW_NO_WORK")
    return {"kind": kind, "originalJobBasisNs": basis, "jobEndNs": job_end, "startNs": start,
        **dict(zip(WINDOW_NAMES, ends))}


@dataclass(eq=False, repr=False)
class _WindowAnchor:
    window: object
    binding: tuple
    graph: tuple
    last: int
    local_last: float
    busy: bool = False
    failure: object = None


class Window:
    """One original RAW/LOCAL/boot interval; all nested caps only shorten it.

    The registry retains the original tuple/Reading graph and frontiers outside
    the handle presented to callbacks. This is a fixed cooperating-call contract,
    not a sandbox against code that replaces the private registry itself.
    """
    __slots__ = ("_bound",)

    def __init__(self, first, local, original_boot, limits, cancelled):
        require(type(self) is Window and id(self) not in _WINDOWS, "WINDOW_NOT_NEW")
        graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        local_value(local)
        digest(original_boot)
        require(callable(cancelled) and type(limits) is dict, "WINDOW_INPUTS")
        _same(limits, schedule(limits["kind"], limits["originalJobBasisNs"], limits["startNs"]), "WINDOW_ARITHMETIC")
        require(first.nanoseconds == limits["startNs"], "WINDOW_ORIGINAL_START")
        raw = O.encoded(limits)
        ends = tuple(limits[name] for name in WINDOW_NAMES)
        locals_ = tuple(O.wire._directed_deadline(local, (end - first.nanoseconds) / O.NS,
            end, first.nanoseconds) for end in ends)
        N._check_history(graph)
        self._bound = (first, local, original_boot, raw, ends, locals_, cancelled)
        _WINDOWS[id(self)] = _WindowAnchor(self, self._bound, graph, first.nanoseconds, local)

    def _anchor(self):
        anchor = _WINDOWS.get(id(self))
        require(type(self) is Window and type(anchor) is _WindowAnchor and anchor.window is self,
            "WINDOW_ORIGINAL_HANDLE")
        return anchor

    def _current(self, anchor):
        require(_WINDOWS.get(id(self)) is anchor and anchor.window is self and self._bound is anchor.binding,
            "WINDOW_ORIGINAL_BINDING")
        N._check_history(anchor.graph)

    @staticmethod
    def _error(anchor, error):
        if anchor.failure is None:
            anchor.failure = error
        return anchor.failure

    def _view(self):
        # Original metadata remains available for bounded cleanup after failure;
        # this does not permit another observation, deadline or successful use.
        anchor = self._anchor()
        try:
            self._current(anchor)
            return anchor
        except BaseException as error:
            raise self._error(anchor, error)

    clock = property(lambda self: self._view().binding[0].clock)
    work = property(lambda self: self._view().binding[4][0])
    final = property(lambda self: self._view().binding[4][1])
    last = property(lambda self: self._view().last)

    def _begin(self):
        anchor = self._anchor()
        if anchor.failure is not None:
            raise anchor.failure
        try:
            self._current(anchor)
            require(not anchor.busy, "WINDOW_REENTRY")
            anchor.busy = True
            return anchor
        except BaseException as error:
            raise self._error(anchor, error)

    @staticmethod
    def _stage(anchor, final, limit, stage):
        require(type(final) is bool and (stage is None or type(stage) is str and stage in WINDOW_NAMES), "WINDOW_STAGE")
        index = WINDOW_NAMES.index(stage) if stage is not None else int(final)
        end, local_end = anchor.binding[4][index], anchor.binding[5][index]
        return (min(end, O.integer(limit)) if limit is not None else end), local_end

    def _observe(self, anchor, end, local_end, minimum):
        binding = anchor.binding
        last, local_last = max(anchor.last, O.integer(minimum)), anchor.local_last
        for number in range(2):
            local = local_value(time.monotonic())
            require(local >= local_last and local < local_end, "WINDOW_LOCAL_EXPIRED_OR_BACKWARDS")
            anchor.local_last = local_last = local
            self._current(anchor)
            value = O.clocks.checked_now(binding[0].clock, minimum_ns=last)
            # Preserve the validated observation before any later guard can fail.
            anchor.last = last = O.integer(value, last)
            self._current(anchor)
            require(last < end and anchor.failure is None and anchor.busy,
                "WINDOW_RAW_EXPIRED_OR_BINDING_CHANGED")
            if number == 0:
                boot = C.boot_digest(binding[0].clock.role)
                self._current(anchor)
                require(type(boot) is str and boot == binding[2], "WINDOW_BOOT_CHANGED")
                binding[6]()
                self._current(anchor)
                require(anchor.last == last and anchor.local_last == local_last and
                    anchor.failure is None and anchor.busy, "WINDOW_CALLBACK_CHANGED")
        after = local_value(time.monotonic())
        require(after >= local_last and after < local_end, "WINDOW_FINAL_LOCAL")
        anchor.local_last = after
        self._current(anchor)
        require(anchor.last == last and anchor.failure is None and anchor.busy, "WINDOW_HIGH_WATER_CHANGED")
        return last

    def now(self, *, final=False, minimum=0, limit=None, stage=None):
        anchor = self._begin()
        try:
            end, local_end = self._stage(anchor, final, limit, stage)
            return self._observe(anchor, end, local_end, minimum)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def deadline(self, maximum, *, final=False, limit=None, stage=None):
        anchor = self._begin()
        try:
            require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 900,
                "WINDOW_OPERATION_MAXIMUM")
            end, local_end = self._stage(anchor, final, limit, stage)
            local = local_value(time.monotonic())
            require(local >= anchor.local_last and local < local_end, "WINDOW_DEADLINE_LOCAL")
            anchor.local_last = local  # This first conversion sample is also a high-water observation.
            self._current(anchor)
            observed = self._observe(anchor, end, local_end, 0)
            result = min(local_end, O.wire._directed_deadline(local, maximum, end, observed))
            self._current(anchor)
            require(anchor.failure is None and anchor.busy, "WINDOW_DEADLINE_CHANGED")
            return result
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False


# The actual native copy/current-authority/export/Step entries are added only
# with their independently reviewed original ownership and returned-value flow.
# This source checkpoint has no dispatchable/standalone custody entry.
