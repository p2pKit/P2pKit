#!/usr/bin/env python3
"""Fixed Stage1 evidence custody; source preparation, not productive admission.

Only the authentic gate/initializer successful Steps may supply the fixed
primary handoff. Historical bytes do not restore a retired owner, Recipient or
HTTP lease. Actual current acquisition, token-free encryption, original native
retirement and separate successful seal/upload Steps remain mandatory.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import hashlib
import importlib.util
import io
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
_spec = importlib.util.spec_from_file_location("_initial_recipient_custody_primary",
    SCRIPTS / "run-hosted-initial-recipient.py")
N = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = N
_spec.loader.exec_module(N)
native, O, I, Q, A, C = N.native, N.O, N.I, N.Q, N.acquisition, N.continuity
import hosted_initial_recipient_evidence as E
import hosted_initial_recipient_before as B
import hosted_initial_recipient_use as U

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
_RETIRED_PRODUCTIVE_WINDOWS = {}


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
    retired: object = None


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
        require(anchor.retired is _RETIRED_PRODUCTIVE_WINDOWS.get(id(self)), "WINDOW_RETIREMENT_CHANGED")
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
            require(anchor.retired is None, "WINDOW_TERMINALLY_RETIRED")
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


# This fixed PRIMARY edge is not a standalone CLI or the final custody caller.
# Current authority, same-child Recipient, three-origin freeze and every later
# export/Step operation remain separate. Nothing here writes a workflow output.
COPY_CHUNK = 64 * 1024
_PRIMARY_ATTEMPTS = {}
_PRIMARY_QUARANTINE = []


def _history_names(kind):
    names = {"P/prelude.json", "P/context.json", "P/initial-result.json",
        "P/acquisition-queries/session-result.json", "P/service/child-result.json"}
    names.update("P/service/" + name for name in native.PHASE_FILES)
    names.update("P/acquisition-queries/" + name + ".bin" for name in N.ORIGINAL_KEYS)
    for group in ("source-before", "source-after"):
        names.update("P/" + group + "/" + name + ".bin" for name in N.SOURCE_KEYS)
        names.update(("P/" + group + "/source-return.json", "P/" + group + "/session-result.json"))
    if kind == "worker":
        names.update(("P/worker-identity.json", "P/worker-service-time.json", "P/worker-allocation-proposal.json",
            "I/receiving-window.json", "I/initializer-context.json", "I/initialization-pending.json",
            "T/step-pending.json", "S/sender-pending.json"))
    return tuple(sorted(names))


def _crypto_names():
    return tuple(sorted({"P/context.json", "P/worker-identity.json", "P/worker-allocation-proposal.json",
        "C/crypto-originals.json", "R/recipient-context.json", "R/recipient-public.asc",
        "R/recipient-pending.json", "R/recipient-validation/child-result.json", "R/source-final/source-return.json",
        "S/recipient-return.json", "S/sender-pending.json", "T/step-pending.json", "I/receiving-window.json",
        "R/crypto/recipient.asc", "R/crypto/recipient.gpg",
        *("R/" + name for name in N.RECIPIENT_FILES),
        *("R/recipient-validation/" + group + "/source-return.json" for group in ("source-before", "source-after")),
        *("R/recipient-validation/" + name for name in native.PHASE_FILES)}))


def _indexed_originals(primary, raw, names):
    """Check supplied bytes against the authentic caller's fixed index, not I/O."""
    require(type(primary) is Primary and type(raw) is dict and set(raw) == set(names), "HISTORY_ROSTER")
    rows = {row[0]: row for row in primary.files}
    for name in names:
        require(name in rows and type(raw[name]) is bytes, "HISTORY_ORIGINAL")
        _, maximum, count, checksum, _ = rows[name]
        require(len(raw[name]) == count <= maximum and O.digest(raw[name]) == checksum, "HISTORY_BYTES")


def _fixed_service_argv(interpreter, context_raw, minimum=None):
    require(type(interpreter) is str and Path(interpreter).is_absolute(), "HISTORY_INTERPRETER")
    value = [interpreter, "-I", "-B", "-S", str(SCRIPTS / "run-hosted-initial-recipient.py"),
             "_service", "--context-sha256", O.digest(context_raw)]
    return value if minimum is None else value + ["--minimum-ns", str(O.integer(minimum))]


def primary_history(primary, raw, observed, event, clock, interpreter):
    """Fixed historical byte predicate; no live owner/authority/LOCAL restoration.

    The original successful Step/hash is a caller obligation. The pure match is
    evaluated at ORIGINAL firstUseAt, never today's wall time or a renewed Date.
    Source/query/native declarations retain their original Step-only provenance.
    """
    _indexed_originals(primary, raw, _history_names(primary.kind))
    roots, handoff = dict(primary.roots), canonical(primary.handoff_raw)
    index = canonical(primary.inventory_raw)
    context = fields(canonical(raw["P/context.json"]), " ".join(N.CONTEXT_FIELDS), "HISTORY_CONTEXT_FIELDS")
    frame = native.history.HistoricalPrelude(raw["P/prelude.json"])
    O.clocks.validate_identity(clock)
    _same(O.clock_value(frame.clock), O.clock_value(clock), "HISTORY_CLOCK")
    _same(context["observed"], observed, "HISTORY_ACTUAL_CONTEXT")
    require(type(observed) is dict and observed["kind"] == primary.kind and observed["role"] == primary.role == clock.role,
        "HISTORY_ACTUAL_ROLE")
    first_use = O.integer(observed["firstUseAt"], 1)
    require(context["schema"] == 1 and type(context["schema"]) is int and
        context["scope"] == native.INITIAL_CONTEXT_SCOPE and context["root"] == str(ROOT) and
        context["session"] == str(roots["P"]) and context["prelude"] == O.parse(frame.raw) and
        type(event) is bytes and context["eventSha256"] == O.digest(event) and
        type(context["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", context["job"]) and
        context["budgetAcceptance"] == "NOT_ADMITTED" and context["exportSaveAuthority"] is False,
        "HISTORY_CONTEXT")
    originals = {name: raw["P/acquisition-queries/" + name + ".bin"] for name in N.ORIGINAL_KEYS}
    require(originals["event"] == event, "HISTORY_EVENT")
    phases = {name: raw["P/service/" + name] for name in native.PHASE_FILES}
    start = fields(canonical(phases["start.json"]), " ".join(native.START_FIELDS), "HISTORY_START_FIELDS")
    require(start["schema"] == 1 and type(start["schema"]) is int and start["scope"] == native.PHASE_SCOPE and
        start["contextSha256"] == O.digest(raw["P/context.json"]) and
        start["argv"] == _fixed_service_argv(interpreter, raw["P/context.json"]) and start["cwd"] == str(ROOT) and
        start["state"] == str(roots["P"]) and start["home"] == str(roots["P"] / "control-home") and
        start["job"] == context["job"] and start["role"] == clock.role and
        type(start["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", start["invocation"]) and
        start["exitCode"] is None and start["launchAttempted"] is False and start["scopeAttempted"] is False and
        start["retirement"] == "UNKNOWN", "HISTORY_START")
    native.history.phase_start(frame, context["sourceReturnedNs"], start)
    require(type(context["inheritedContext"]) is dict and all(type(value) is str for value in context["inheritedContext"].values()) and
        (set(context["inheritedContext"]).issubset({"GRADLE_USER_HOME"}) or set(context["inheritedContext"]) == set(Q._CONTEXT)),
        "HISTORY_CONTEXT_ANCESTORS")
    inherited = native.processes.ownership_environment(context["inheritedContext"], context["job"], start["invocation"],
        str(roots["P"]), str(roots["P"] / "control-home"), allow_new_context=True)
    _same(start["inheritedContext"], {name: inherited[name] for name in Q._CONTEXT}, "HISTORY_NATIVE_ANCESTORS")
    inputs = N._retained_match_inputs(context, originals, start["invocation"], clock,
        start["startedNs"], start["workEndNs"])
    match, service = N._retained_match_at(inputs, now=first_use)
    require(type(match.record) is bytes and match.record == originals["match"], "HISTORY_MATCH")
    row = fields(canonical(phases["result.json"]), " ".join(native.TERMINAL_FIELDS), "HISTORY_PHASE_FIELDS")
    birth = fields(canonical(phases["native-start.json"]), "ownership leader preparerIdentity observedNs",
        "HISTORY_BIRTH_FIELDS")
    changed = {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}
    _same({name: row[name] for name in start if name not in changed},
          {name: start[name] for name in start if name not in changed}, "HISTORY_PHASE_START")
    require(type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is True and
        row["scopeAttempted"] is True and row["scopeCloseAttempted"] is True and row["scopeClosed"] is True and
        row["retirement"] == "KNOWN" and row["survivors"] == [] and row["errors"] == [] and
        phases["stderr.log"] == b"" and row["nativeStartSha256"] == O.digest(phases["native-start.json"]) and
        row["baselineSha256"] == O.digest(phases["baseline.json"]) and row["leader"] == birth["leader"],
        "HISTORY_PHASE_RETIREMENT")
    captures = {name: {key: True for key in ("synced", "verified", "closeAttempted", "closed", "readback")}
        for name in ("stdout", "stderr")}
    _same(row["captureOutcomes"], captures, "HISTORY_CAPTURE_CLOSE")
    _same(row["captures"], {name: {"sha256": O.digest(phases[name + ".log"]),
        "bytes": len(phases[name + ".log"])} for name in ("stdout", "stderr")}, "HISTORY_CAPTURES")
    argv = _fixed_service_argv(interpreter, raw["P/context.json"], row["launchMinimumNs"])
    _same(row["launchArgv"], argv, "HISTORY_LAUNCH")
    native.native_record(row["ownership"], start, row["leader"], argv)
    native.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    _same(birth["ownership"]["launches"], row["ownership"]["launches"], "HISTORY_BIRTH")
    preparer = native.closed_lifetime(row["preparerIdentity"], clock.role)
    require(preparer == native.closed_lifetime(birth["preparerIdentity"], clock.role) and
        preparer["pid"] != row["leader"]["pid"], "HISTORY_PREPARER")
    baseline = native.baseline_record(phases["baseline.json"], clock.role)
    if baseline["baseline"] is not None:
        lifetime = native.lifetime(row["leader"], clock.role)
        require(list(lifetime[:4] if clock.role.startswith("macos-") else lifetime) not in baseline["baseline"],
            "HISTORY_PREEXISTING_LEADER")
    child = fields(canonical(raw["P/service/child-result.json"]), "schema scope contextSha256 startSha256 invocation "
        "clock launchMinimumNs beganNs metadataLastNs acquiredNs queryReturnedNs querySessionSha256 originalsSha256 "
        "matchSha256 completedNs retirement errors", "HISTORY_CHILD_FIELDS")
    ack = fields(canonical(phases["stdout.log"]), "schema scope invocation terminalSha256 clock closedNs", "HISTORY_ACK_FIELDS")
    require(type(child["schema"]) is int and child["schema"] == 1 and child["scope"] == N.CHILD_SCOPE and
        child["contextSha256"] == O.digest(raw["P/context.json"]) and child["startSha256"] == O.digest(phases["start.json"]) and
        child["invocation"] == start["invocation"] and child["clock"] == O.clock_value(clock) and
        child["launchMinimumNs"] == row["launchMinimumNs"] and child["retirement"] == "KNOWN" and child["errors"] == [] and
        type(ack["schema"]) is int and ack["schema"] == 1 and ack["scope"] == native.INITIAL_ACK_SCOPE and
        ack["invocation"] == start["invocation"] and ack["terminalSha256"] == O.digest(raw["P/service/child-result.json"]) and
        ack["clock"] == O.clock_value(clock), "HISTORY_CHILD_ACK")
    minimum = N._service_chain_minimum(frame.first, context["sourceReturnedNs"], start, row, birth, child, service, ack)
    hashes = {name: O.digest(value) for name, value in originals.items()}
    require(child["originalsSha256"] == hashes and child["matchSha256"] == O.digest(match.record) and
        child["querySessionSha256"] == O.digest(raw["P/acquisition-queries/session-result.json"]), "HISTORY_CHILD_ORIGINALS")
    sources = []
    for name in ("source-before", "source-after"):
        path = "P/" + name + "/"
        source = fields(canonical(raw[path + "source-return.json"]),
            "schema scope originalsSha256 sessionSha256 clock returnedNs", "HISTORY_SOURCE_FIELDS")
        require(type(source["schema"]) is int and source["schema"] == 1 and source["scope"] == N.SOURCE_SCOPE and
            source["clock"] == O.clock_value(clock) and source["sessionSha256"] == O.digest(raw[path + "session-result.json"]) and
            source["originalsSha256"] == {key: O.digest(originals[key]) for key in N.SOURCE_KEYS} and
            all(raw[path + key + ".bin"] == originals[key] for key in N.SOURCE_KEYS), "HISTORY_SOURCE")
        sources.append(source)
    require(context["sourceReturnSha256"] == O.digest(raw["P/source-before/source-return.json"]) and
        context["sourceReturnedNs"] == sources[0]["returnedNs"] and
        minimum <= O.integer(sources[1]["returnedNs"]) < frame.work, "HISTORY_SOURCE_ORDER")
    pending = fields(canonical(raw["P/initial-result.json"]), "schema scope contextSha256 sourceBeforeSha256 sourceAfterSha256 "
        "matchSha256 originalChain retainedNs retirement budgetAcceptance workerAdmission workerIdentitySha256 "
        "serviceTimeBasisSha256 allocationProposalSha256 qualificationAcceptance exportSaveAuthority", "HISTORY_PENDING_FIELDS")
    chain = fields(pending["originalChain"], "phaseSha256 childSha256 querySessionSha256 originalsSha256 checkedNs", "HISTORY_CHAIN_FIELDS")
    require(type(pending["schema"]) is int and pending["schema"] == 1 and pending["scope"] == N.RESULT_SCOPE and
        pending["contextSha256"] == O.digest(raw["P/context.json"]) and pending["matchSha256"] == O.digest(match.record) and
        pending["sourceBeforeSha256"] == O.digest(raw["P/source-before/source-return.json"]) and
        pending["sourceAfterSha256"] == O.digest(raw["P/source-after/source-return.json"]) and
        pending["retirement"] == "PENDING_OWNER_CLOSE" and pending["budgetAcceptance"] == "NOT_ADMITTED" and
        pending["workerAdmission"] == "NOT_PERFORMED" and pending["qualificationAcceptance"] == "NOT_ESTABLISHED" and
        pending["exportSaveAuthority"] is False and chain["phaseSha256"] == {key: O.digest(value) for key, value in phases.items()} and
        chain["childSha256"] == O.digest(raw["P/service/child-result.json"]) and chain["querySessionSha256"] == child["querySessionSha256"] and
        chain["originalsSha256"] == hashes and sources[1]["returnedNs"] <= O.integer(chain["checkedNs"]) <=
        O.integer(pending["retainedNs"]) < frame.work,
        "HISTORY_PENDING")
    _same(index["source"], observed["source"], "HISTORY_INDEX_SOURCE")
    _same(index["github"], observed["github"], "HISTORY_INDEX_JOB")
    arithmetic = native.service_time.basis_arithmetic(service["jobsRequestStartedNs"],
        O.wire.utc_epoch(service["jobStartedAt"]), service["originDateEpochSeconds"])
    captured = (raw["P/context.json"], tuple(originals.items()), start["invocation"], start["startedNs"], start["workEndNs"])
    service_job = N._service_job(captured, clock)
    if primary.kind == "gate":
        require(type(match) is A.gate.GateEligibility and O.digest(raw["P/initial-result.json"]) == primary.result_sha256 and
            index["contextSha256"] == O.digest(raw["P/context.json"]) and
            index["gateEligibilitySha256"] == O.digest(match.record) and
            handoff["gateEligibility"] == O.parse(match.record) and index["policy"] == O.parse(match.record)["policy"] and
            all(pending[name] is None for name in ("workerIdentitySha256", "serviceTimeBasisSha256", "allocationProposalSha256")) and
            handoff["clock"] == O.clock_value(clock) and handoff["preludeSha256"] == O.digest(frame.raw), "HISTORY_GATE")
        previous = O.integer(handoff["originalClosedNs"], pending["retainedNs"])
        require(previous < frame.final, "HISTORY_GATE_CLOSE")
        boot, local_scope = digest(handoff["bootDigest"]), "NO_SERIALIZED_LOCAL_ADOPTION"
    else:
        require(type(match) is A.stages.BootstrapMatch, "HISTORY_WORKER_MATCH")
        _same(index["clock"], O.clock_value(clock), "HISTORY_WORKER_INDEX_CLOCK")
        identity = N.initial_identity.bind_worker_match(match, event_raw=event,
            policy_raw=originals["candidate_policy_raw"], now=first_use)
        require(identity.record == raw["P/worker-identity.json"] and
            O.digest(identity.record) == index["workerIdentitySha256"] == pending["workerIdentitySha256"], "HISTORY_WORKER_IDENTITY")
        basis, proposal = N._worker_time_values(identity, service, clock, start["invocation"])
        require((basis, proposal) == (raw["P/worker-service-time.json"], raw["P/worker-allocation-proposal.json"]) and
            pending["serviceTimeBasisSha256"] == O.digest(basis) and pending["allocationProposalSha256"] == O.digest(proposal),
            "HISTORY_WORKER_ORIGINAL_BASIS")
        step, sender = N._step_record(raw["T/step-pending.json"]), canonical(raw["S/sender-pending.json"])
        receiving, _, began, work = N._receiving_frame(raw["I/receiving-window.json"])
        init = fields(canonical(raw["I/initialization-pending.json"]), "schema scope window stepSha256 authoritySha256 "
            "originals retainedNs retainedLocal childReturn ownerReturn originalStepOutcome budgetAcceptance "
            "testAcceptance exportSaveAuthority", "HISTORY_INITIAL_PENDING_FIELDS")
        init_context = fields(canonical(raw["I/initializer-context.json"]), "schema scope job receivingWindowSha256 "
            "authoritySha256 senderSha256 stepSha256 requestSha256 workerIdentitySha256 budgetAcceptance "
            "testAcceptance exportSaveAuthority", "HISTORY_INITIAL_CONTEXT_FIELDS")
        closed = fields(canonical(dict(primary.embedded)["initialization-history.json"]), "schema scope pendingSha256 closedNs "
            "closedLocal resourceCount ownerReturn nextPhaseAuthority budgetAcceptance exportSaveAuthority", "HISTORY_INITIAL_CLOSE_FIELDS")
        authority_raw = dict(primary.embedded)["receiving-authority-return.json"]
        require(O.digest(raw["T/step-pending.json"]) == index["recipientStepSha256"] == init["stepSha256"] == init_context["stepSha256"] and
            O.digest(raw["S/sender-pending.json"]) == index["senderSha256"] == step["senderSha256"] == receiving["senderSha256"] and
            step["directory"] == str(roots["T"]) and step["directoryIdentity"] == list(dict((name, pin) for name, pin, _ in primary.directories)["T"]) and
            step["observed"] == observed and step["serviceJob"] == list(service_job) and step["clock"] == O.clock_value(clock) and
            receiving["clock"] == O.clock_value(clock) and step["workerIdentitySha256"] == receiving["workerIdentitySha256"] == index["workerIdentitySha256"] and
            step["originalProposalSha256"] == receiving["originalProposalSha256"] == O.digest(proposal) and
            receiving["firstUseAt"] == first_use and receiving["previousNs"] == sender["readWindow"]["retainedNs"] and
            sender["readWindow"]["clock"] == step["clock"] and sender["readWindow"]["readEndNs"] == step["readEndNs"] and
            sender["readWindow"]["readLocalCeiling"] == step["readLocalCeiling"] and
            0 <= local_value(sender["readWindow"]["previousLocal"]) <= step["lowerLocal"] and
            receiving["previousNs"] <= step["lowerNs"] <= began, "HISTORY_RECEIVING_BINDINGS")
        require(type(init_context["schema"]) is int and init_context["schema"] == 1 and
            init_context["scope"] == "INITIAL_RECIPIENT_CANONICAL_INITIALIZER_CONTEXT_V1" and
            type(init_context["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", init_context["job"]) and
            init_context["senderSha256"] == index["senderSha256"] and
            init_context["workerIdentitySha256"] == index["workerIdentitySha256"] and
            init_context["budgetAcceptance"] == init["budgetAcceptance"] == "NOT_ADMITTED" and
            init_context["testAcceptance"] == init["testAcceptance"] == "NOT_PERFORMED" and
            init_context["exportSaveAuthority"] is init["exportSaveAuthority"] is False and
            init["childReturn"] == "INITIALIZED_CONTEXT_NOT_PRODUCT_RECEIPT" and
            init["ownerReturn"] == "PENDING_OWNER_CLOSE" and init["originalStepOutcome"] == "NOT_OBSERVED",
            "HISTORY_INITIAL_PENDING")
        file_rows = {row[0]: row for row in primary.files}
        dir_rows = {name: pin for name, pin, _ in primary.directories}
        original_names = ("I/receiving-window.json", "I/initializer-context.json",
            *("I/canonical-init/" + name for name in sorted(native.PHASE_FILES | {"request.json"})),
            "I/state/context.json", "I/state/gradle-home/gradle.properties")
        expected_originals = []
        for name in original_names:
            relative, _, count, checksum, _ = file_rows[name]
            parent, leaf = relative.rsplit("/", 1)
            expected_originals.append({"directory": str(roots["I"].joinpath(*parent.split("/")[1:])),
                "directoryIdentity": list(dir_rows[parent]), "name": leaf, "bytes": count, "sha256": checksum})
        _same(init["originals"], expected_originals, "HISTORY_INITIAL_ORIGINALS")
        require(init_context["requestSha256"] == file_rows["I/canonical-init/request.json"][3], "HISTORY_INITIAL_REQUEST")
        authority = fields(canonical(authority_raw), "schema scope receivingWindowSha256 senderSha256 workerIdentitySha256 "
            "matchSha256 originalProposalSha256 filesSha256 pendingSha256 originalChain preCloseNs closedNs "
            "resourceCount retirement budgetAcceptance exportSaveAuthority", "HISTORY_INITIAL_AUTHORITY_FIELDS")
        authority_names = {name.removeprefix("P/") for name in _history_names("gate")}
        authority_names.difference_update(("prelude.json", "initial-result.json"))
        authority_names.add("authority-window.json")
        _same(authority["filesSha256"], {name: file_rows["I/authority/" + name][3] for name in authority_names},
            "HISTORY_INITIAL_AUTHORITY_ORIGINALS")
        achain = fields(authority["originalChain"], "phaseSha256 childSha256 querySessionSha256 originalsSha256 checkedNs",
            "HISTORY_INITIAL_AUTHORITY_CHAIN_FIELDS")
        require(type(authority["schema"]) is int and authority["schema"] == 1 and
            authority["scope"] == "INITIAL_RECIPIENT_RECEIVING_AUTHORITY_CLOSED_HISTORY_V1" and
            authority["receivingWindowSha256"] == O.digest(raw["I/receiving-window.json"]) and
            authority["senderSha256"] == index["senderSha256"] and
            authority["workerIdentitySha256"] == index["workerIdentitySha256"] and
            authority["matchSha256"] == O.digest(match.record) and authority["originalProposalSha256"] == O.digest(proposal) and
            authority["pendingSha256"] == file_rows["I/authority/authority-pending.json"][3] and
            authority["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and authority["budgetAcceptance"] == "NOT_ADMITTED" and
            authority["exportSaveAuthority"] is False and type(authority["resourceCount"]) is int and
            0 < authority["resourceCount"] <= MAX_MEMBERS and
            achain["phaseSha256"] == {name: file_rows["I/authority/service/" + name][3] for name in native.PHASE_FILES} and
            achain["childSha256"] == file_rows["I/authority/service/child-result.json"][3] and
            achain["querySessionSha256"] == file_rows["I/authority/acquisition-queries/session-result.json"][3] and
            achain["originalsSha256"] == {name: file_rows["I/authority/acquisition-queries/" + name + ".bin"][3]
                for name in N.ORIGINAL_KEYS} and began <= O.integer(achain["checkedNs"]) <=
            O.integer(authority["preCloseNs"]) <= O.integer(authority["closedNs"]) <= O.integer(init["retainedNs"]),
            "HISTORY_INITIAL_AUTHORITY")
        require(type(init["schema"]) is int and init["schema"] == 1 and
            init["scope"] == "INITIAL_RECIPIENT_CANONICAL_INITIALIZATION_PENDING_OWNER_CLOSE_V1" and init["window"] == receiving and
            O.digest(raw["I/initialization-pending.json"]) == primary.result_sha256 == index["initializationSha256"] == closed["pendingSha256"] and
            init["authoritySha256"] == init_context["authoritySha256"] == O.digest(authority_raw) == index["authoritySha256"] and
            init_context["receivingWindowSha256"] == O.digest(raw["I/receiving-window.json"]) and
            type(closed["schema"]) is int and closed["schema"] == 1 and
            closed["scope"] == "INITIAL_RECIPIENT_CLOSED_INITIALIZATION_HISTORY_V1" and
            closed["ownerReturn"] == "KNOWN_RESOURCE_CLOSE_ONLY" and closed["nextPhaseAuthority"] is False and
            closed["budgetAcceptance"] == "NOT_ADMITTED" and closed["exportSaveAuthority"] is False and
            type(closed["resourceCount"]) is int and 0 < closed["resourceCount"] <= MAX_MEMBERS and
            began <= O.integer(init["retainedNs"]) <= O.integer(closed["closedNs"]) < work and
            step["lowerLocal"] <= local_value(init["retainedLocal"]) <= local_value(closed["closedLocal"]), "HISTORY_INITIAL_CLOSE")
        previous, boot = closed["closedNs"], digest(step["bootSha256"])
        local_scope = "ORIGINAL_RECEIVING_FIRST_LOCAL_NOT_INDEPENDENTLY_RECONSTRUCTIBLE"
    return O.encoded({"schema": 1, "scope": "INITIAL_CUSTODY_PRIMARY_HISTORICAL_BINDING_V1", "kind": primary.kind,
        "observed": observed, "clock": O.clock_value(clock), "originalBootDigest": boot, "originalPreviousNs": previous,
        "originalJobBasisNs": arithmetic["jobStartBasisNs"], "serviceArithmetic": arithmetic, "serviceJob": list(service_job),
        "firstUseAt": first_use, "matchSha256": O.digest(match.record), "originalLocalScope": local_scope,
        "primaryStepScope": "ACTUAL_SUCCESS_AND_HASH_REQUIRED_NOT_INDEPENDENT_RUNTIME_QUALIFICATION",
        "currentAuthority": "NOT_ACQUIRED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})


def _crypto_roster(primary, inventory, context, child, public, armor, ring):
    """Retained shallow declarations/public packets only, never a live Recipient."""
    windows = primary.role == "windows-x64"
    directories, rows = inventory["directories"], inventory["files"]
    require(type(directories) is list and len(directories) == (6 if windows else 5), "CRYPTO_DIRECTORIES")
    for directory in directories:
        fields(directory, "relative identity members", "CRYPTO_DIRECTORY_FIELDS")
        require(type(directory["relative"]) is str and type(directory["members"]) is list and
            len(directory["members"]) <= 32 and all(type(name) is str for name in directory["members"]) and
            directory["members"] == sorted(directory["members"]) and
            len({name.casefold() for name in directory["members"]}) == len(directory["members"]), "CRYPTO_DIRECTORY_NAMES")
        native.directory_identity(directory["identity"], primary.role)
        for name in directory["members"]:
            Q._component(name)
    members = directories[0]["members"]
    operations = tuple(name for name in members if re.fullmatch(
        r"gpg-[0-9a-f]{32}" if windows else r"gpg-[a-z0-9_]+", name))
    results = tuple(name for name in members if re.fullmatch(r"recipient-validation-result-[0-9a-f]{32}\.json", name))
    require(len(operations) == (3 if windows else 2) and len(results) == (1 if windows else 0) and
        set(members) == {"recipient.asc", "recipient.gpg", "gnupg", "tmp", *operations, *results} and
        tuple(row["relative"] for row in directories) == ("", "gnupg", "tmp", *operations) and
        len({tuple(row["identity"]) for row in directories}) == len(directories), "CRYPTO_SHALLOW_GRAMMAR")
    pins = {name: (identity, provenance) for name, identity, provenance in primary.directories}
    crypto_pins = {name for name in pins if name == "R/crypto" or name.startswith("R/crypto/")}
    require(crypto_pins == {"R/crypto" + ("/" + row["relative"] if row["relative"] else "") for row in directories},
        "CRYPTO_PIN_ROSTER")
    for row in directories:
        name = "R/crypto" + ("/" + row["relative"] if row["relative"] else "")
        expected = "AUTHENTICATED_ORIGINAL_CRYPTO_NATIVE_PIN" if row["relative"] else "RECEIVER_READBACK_NATIVE_PIN"
        require(pins[name] == (tuple(row["identity"]), expected), "CRYPTO_PIN_CHANGED")
    _same(directories[0]["identity"], context["directories"]["crypto"], "CRYPTO_CONTEXT_PIN")
    _same(directories[0]["identity"], child["recipient"]["work_identity"], "CRYPTO_CHILD_PIN")
    expected = {name: native.posix.MAX_KEY_BYTES for name in ("recipient.asc", "recipient.gpg")}
    expected.update({name: native.diagnostics.MAX_RECORD_BYTES for name in results})
    for directory in directories[1:]:
        name, members = directory["relative"], directory["members"]
        if name in ("gnupg", "tmp"):
            require(not windows or members == [], "CRYPTO_WINDOWS_EMPTY_HOME")
        else:
            require(members == sorted(("stdout", "stderr") if windows else ("stdout", "stderr", "status", "process.json")),
                "CRYPTO_OPERATION_MEMBERS")
        for member in members:
            expected[name + "/" + member] = (native.LIMIT if name in ("gnupg", "tmp") or member == "process.json"
                else native.posix.MAX_DIAGNOSTIC_BYTES)
    require(type(rows) is list and len(rows) == len(expected) and
        (len(rows) == 9 if windows else 10 <= len(rows) <= 74), "CRYPTO_FILE_COUNT")
    declared, total = [], 0
    for row, name in zip(rows, sorted(expected)):
        fields(row, "relative bytes sha256", "CRYPTO_FILE_FIELDS")
        require(row["relative"] == name, "CRYPTO_FILE_ORDER")
        checked = N._worker_file("R/crypto/" + name, expected[name], row["bytes"], row["sha256"],
            "AUTHENTICATED_CRYPTO_DECLARATION")
        declared.append(tuple(checked[key] for key in ("relative", "maximum", "bytes", "sha256", "provenance")))
        total += checked["bytes"]
        require(total <= N.CRYPTO_ORIGINALS_LIMIT, "CRYPTO_BYTE_CAP")
    require(tuple(declared) == tuple(row for row in primary.files if row[0].startswith("R/crypto/")) and
        type(inventory["totalBytes"]) is int and inventory["totalBytes"] == total, "CRYPTO_INDEX_BYTES")
    key_rows = {row[0]: row for row in declared}
    require(type(public) is bytes and type(armor) is bytes and type(ring) is bytes and public == armor and
        0 < len(public) <= native.posix.MAX_KEY_BYTES and 0 < len(ring) <= native.posix.MAX_KEY_BYTES and
        (len(armor), O.digest(armor)) == key_rows["R/crypto/recipient.asc"][2:4] and
        (len(ring), O.digest(ring)) == key_rows["R/crypto/recipient.gpg"][2:4] and
        O.digest(armor) == child["recipient"]["key_sha256"], "CRYPTO_PUBLIC_KEY_BINDING")
    require(native.posix._public_armor(armor) == ring, "CRYPTO_PUBLIC_ONLY_RING")
    return tuple(declared)


def _retained_crypto_tail(value, row, swindow, step, receiving, source, pending, validation):
    """Only serialized caps/chronology; the absent first receiving LOCAL is not an input."""
    clock = O.wire.clock_identity(value["clock"])
    for observed in (swindow["clock"], step["clock"], receiving["clock"], source["clock"]):
        _same(observed, O.clock_value(clock), "CRYPTO_TAIL_CLOCK")
    require(type(value["readEndNs"]) is int and value["readEndNs"] == row["readEndNs"] == swindow["readEndNs"] == step["readEndNs"] and
        type(value["readLocalCeiling"]) is float and math.isfinite(value["readLocalCeiling"]) and
        value["readLocalCeiling"] == swindow["readLocalCeiling"] == step["readLocalCeiling"] and
        0 <= local_value(swindow["previousLocal"]) <= local_value(step["lowerLocal"]) < value["readLocalCeiling"] and
        receiving["previousNs"] == swindow["retainedNs"] and swindow["previousNs"] == validation["closedNs"], "CRYPTO_CAPS")
    chronology = (row["readbackCompletedNs"], value["capturedNs"], source["returnedNs"], pending["retainedNs"],
        validation["preCloseNs"], validation["closedNs"], swindow["previousNs"], swindow["retainedNs"], step["lowerNs"])
    require(all(type(number) is int and 0 <= number < value["readEndNs"] for number in chronology) and
        tuple(sorted(chronology)) == chronology and chronology[-1] <= O.integer(receiving["firstNs"]), "CRYPTO_TAIL_CHRONOLOGY")
    return "NOT_INDEPENDENTLY_RECONSTRUCTIBLE"


def crypto_history(primary, raw, historical_raw, interpreter):
    """Recheck retained crypto links, not the missing original receiving LOCAL.

    This deliberately never calls _worker_crypto_index with an invented reader,
    creates a Recipient, reads the old registry or reruns public-key validation.
    The successful original Step retains its own unchanged live-check scope.
    """
    require(primary.kind == "worker", "CRYPTO_WORKER_ONLY")
    _indexed_originals(primary, raw, _crypto_names())
    history = canonical(historical_raw)
    roots, index = dict(primary.roots), canonical(primary.inventory_raw)
    pins = {name: identity for name, identity, _ in primary.directories}
    files = {row[0]: row for row in primary.files}
    side = fields(canonical(raw["C/crypto-originals.json"]), "schema scope directory directoryIdentity "
        "recipientValidationSha256 recipientSenderSha256 recipientStepSha256 inventory writerReturn "
        "originalStepOutcome budgetAcceptance exportSaveAuthority", "CRYPTO_SIDECAR_FIELDS")
    require(type(side["schema"]) is int and side["schema"] == 1 and side["scope"] == N.CRYPTO_SIDECAR_SCOPE and
        side["directory"] == str(roots["C"]) and side["directoryIdentity"] == list(pins["C"]) and
        side["recipientValidationSha256"] == O.digest(raw["S/recipient-return.json"]) and
        side["recipientSenderSha256"] == O.digest(raw["S/sender-pending.json"]) == index["senderSha256"] and
        side["recipientStepSha256"] == O.digest(raw["T/step-pending.json"]) == index["recipientStepSha256"] and
        O.digest(raw["C/crypto-originals.json"]) == index["recipientCryptoOriginalsSha256"] and
        side["writerReturn"] == "PENDING_OWNER_CLOSE" and side["originalStepOutcome"] == "NOT_OBSERVED" and
        side["budgetAcceptance"] == "NOT_ADMITTED" and side["exportSaveAuthority"] is False, "CRYPTO_SIDECAR")
    value = fields(side["inventory"], "schema scope root contextSha256 childSha256 phaseSha256 clock readEndNs "
        "readLocalCeiling capturedNs directories files totalBytes copyState liveRecipient budgetAcceptance "
        "exportSaveAuthority", "CRYPTO_INVENTORY_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == N.CRYPTO_ORIGINALS_SCOPE and
        value["root"] == str(roots["R"] / "crypto") and value["copyState"] == "ORIGINAL_BYTES_NOT_COPIED" and
        value["liveRecipient"] == "NOT_TRANSFERRED" and value["budgetAcceptance"] == "NOT_ADMITTED" and
        value["exportSaveAuthority"] is False, "CRYPTO_INVENTORY")
    context = fields(canonical(raw["R/recipient-context.json"]), " ".join(N.RECIPIENT_CONTEXT_FIELDS), "CRYPTO_CONTEXT_FIELDS")
    require(type(context["schema"]) is int and context["schema"] == 1 and context["scope"] == N.RECIPIENT_CONTEXT_SCOPE and
        context["session"] == str(roots["R"]) and context["root"] == str(ROOT) and
        context["observed"] == canonical(raw["P/context.json"])["observed"] == history["observed"] and
        context["eventSha256"] == canonical(raw["P/context.json"])["eventSha256"] and
        context["inheritedContext"] == canonical(raw["P/context.json"])["inheritedContext"] and
        context["filesSha256"] == {name: O.digest(raw["R/" + name]) for name in N.RECIPIENT_FILES} and
        context["directories"] == {name: list(pins["R/" + name]) for name in N.RECIPIENT_DIRECTORIES} and
        type(context["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", context["job"]) and
        context["budgetAcceptance"] == "NOT_ADMITTED" and context["exportSaveAuthority"] is False, "CRYPTO_CONTEXT")
    frame, clock, first, ends = N._recipient_frame(raw["R/recipient-window.json"])
    receiving, _, began, _ = N._receiving_frame(raw["I/receiving-window.json"])
    step = N._step_record(raw["T/step-pending.json"])
    sender = fields(canonical(raw["S/sender-pending.json"]), "schema scope directory directoryIdentity records "
        "originalReferences readWindow writerReturn originalStepOutcome completeOriginals liveRecipient "
        "currentRemoteAuthority budgetAcceptance testAcceptance exportSaveAuthority", "CRYPTO_SENDER_FIELDS")
    swindow = fields(sender["readWindow"], "clock previousNs previousLocal readEndNs readLocalCeiling retainedNs", "CRYPTO_SENDER_WINDOW_FIELDS")
    require(type(sender["schema"]) is int and sender["schema"] == 1 and sender["scope"] == N.RECIPIENT_SENDER_SCOPE and
        sender["directory"] == str(roots["S"]) and sender["directoryIdentity"] == list(pins["S"]) and
        sender["writerReturn"] == "PENDING_NOT_OBSERVABLE_BY_THIS_FILE" and sender["originalStepOutcome"] == "NOT_OBSERVED" and
        sender["completeOriginals"] == "NOT_ESTABLISHED_BY_THIS_BUNDLE" and sender["liveRecipient"] == "NOT_TRANSFERRED" and
        sender["currentRemoteAuthority"] == "NOT_GRANTED_BY_HISTORY" and sender["budgetAcceptance"] == "NOT_ADMITTED" and
        sender["testAcceptance"] == "NOT_PERFORMED" and sender["exportSaveAuthority"] is False and
        sender["records"] == {name: {"bytes": files["S/" + name][2], "sha256": files["S/" + name][3]}
            for name in ("readmission-return.json", "recipient-return.json")}, "CRYPTO_SENDER")
    identity = canonical(raw["P/worker-identity.json"])
    proposal = canonical(raw["P/worker-allocation-proposal.json"])
    require(raw["R/worker-identity.json"] == raw["P/worker-identity.json"] and
        raw["R/worker-proposal.json"] == raw["P/worker-allocation-proposal.json"] and
        raw["R/worker-match.json"] == O.encoded(identity["initialRecipient"]) and
        sender["originalReferences"] == {"recipientSession": str(roots["R"]), "readmissionSession": str(roots["E"]),
            "scope": "PINNED_CONTEXT_REFERENCES_NOT_CURRENT_FILESYSTEM_OBSERVATIONS",
            "workerIdentitySha256": O.digest(raw["P/worker-identity.json"]),
            "serviceTimeBasisSha256": files["P/worker-service-time.json"][3],
            "originalProposalSha256": O.digest(raw["P/worker-allocation-proposal.json"])} and
        frame["firstUseAt"] == history["firstUseAt"] and
        frame["originalProposalSha256"] == O.digest(raw["P/worker-allocation-proposal.json"]) and
        frame["originalProposedJobEndNs"] == proposal["proposedJobEndNs"] and
        frame["originalFencesNs"] == {name: proposal["phaseFencesNs"][name] for name in
            ("recipient-validation", "recipient-final", "recipient-read")}, "CRYPTO_WORKER_LINKS")
    validation = fields(canonical(raw["S/recipient-return.json"]), "schema scope window originalReadmissionSha256 "
        "workerIdentitySha256 authoritySha256 pendingSha256 preCloseNs closedNs resourceCount retirement "
        "liveRecipient currentRemoteAuthority budgetAcceptance testAcceptance exportSaveAuthority", "CRYPTO_VALIDATION_FIELDS")
    require(type(validation["schema"]) is int and validation["schema"] == 1 and validation["scope"] == N.RECIPIENT_RETURN_SCOPE and
        validation["window"] == frame and validation["originalReadmissionSha256"] == frame["originalReadmissionSha256"] ==
        files["S/readmission-return.json"][3] and validation["workerIdentitySha256"] == frame["workerIdentitySha256"] ==
        O.digest(raw["P/worker-identity.json"]) and validation["authoritySha256"] == O.digest(raw["R/authority-return.json"]) and
        validation["pendingSha256"] == O.digest(raw["R/recipient-pending.json"]) and
        type(validation["resourceCount"]) is int and 0 < validation["resourceCount"] <= MAX_MEMBERS and
        validation["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and validation["liveRecipient"] == "NOT_TRANSFERRED" and
        validation["currentRemoteAuthority"] == "NOT_GRANTED_BY_HISTORY" and validation["budgetAcceptance"] == "NOT_ADMITTED" and
        validation["testAcceptance"] == "NOT_PERFORMED" and validation["exportSaveAuthority"] is False, "CRYPTO_VALIDATION")
    phase = {name: raw["R/recipient-validation/" + name] for name in native.PHASE_FILES}
    # Use the maintained byte-only native graph predicate. Its command helper
    # resolves the ACTUAL interpreter; compare it to the one pinned by our caller.
    require(str(Path(sys.executable).resolve(strict=True)) == interpreter, "CRYPTO_ACTUAL_INTERPRETER")
    start, row, birth, child, ack = N._initial_graph_native(raw["R/recipient-context.json"], roots["R"], clock,
        first, ends[0], ends[1], phase, raw["R/recipient-validation/child-result.json"], "R")
    require(value["contextSha256"] == O.digest(raw["R/recipient-context.json"]) and
        value["childSha256"] == O.digest(raw["R/recipient-validation/child-result.json"]) and
        value["phaseSha256"] == {name: O.digest(contents) for name, contents in phase.items()} and
        child["identitySha256"] == O.digest(raw["P/worker-identity.json"]) and
        child["authoritySha256"] == O.digest(raw["R/authority-return.json"]), "CRYPTO_PHASE_LINKS")
    supplier = fields(child["recipient"], "fingerprint encryption_fingerprint expires_at key_sha256 work_identity executable" +
        (" executable_sha256 job_id" if primary.role == "windows-x64" else ""), "CRYPTO_SUPPLIER_FIELDS")
    require(supplier["fingerprint"] == identity["policy"]["fingerprint"] and
        supplier["key_sha256"] == identity["policy"]["keySha256"] and
        type(supplier["encryption_fingerprint"]) is str and re.fullmatch(r"[0-9A-F]{40}", supplier["encryption_fingerprint"]) and
        type(supplier["expires_at"]) is int and (supplier["expires_at"] == 0 or supplier["expires_at"] >= identity["policy"]["expiresAt"]) and
        type(supplier["executable"]) is str and Path(supplier["executable"]).is_absolute(), "CRYPTO_SUPPLIER")
    if primary.role == "windows-x64":
        require(supplier["job_id"] == context["job"], "CRYPTO_WINDOWS_JOB")
        digest(supplier["executable_sha256"])
    pending = canonical(raw["R/recipient-pending.json"])
    retained = O.integer(pending["retainedNs"])
    _same(pending, {"schema": 1, "scope": "INITIAL_RECIPIENT_VALIDATION_PENDING_OWNER_CLOSE_V1",
        "windowSha256": O.digest(raw["R/recipient-window.json"]), "contextSha256": value["contextSha256"],
        "authoritySha256": validation["authoritySha256"], "phaseSha256": value["phaseSha256"], "childSha256": value["childSha256"],
        "sourceFinalSha256": O.digest(raw["R/source-final/source-return.json"]), "retainedNs": retained,
        "retirement": "PENDING_OWNER_CLOSE", "liveRecipient": "NOT_TRANSFERRED", "budgetAcceptance": "NOT_ADMITTED",
        "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}, "CRYPTO_PENDING")
    sources = []
    for key, digest_name in (("R/recipient-validation/source-before", "sourceBeforeSha256"),
            ("R/recipient-validation/source-after", "sourceAfterSha256"), ("R/source-final", None)):
        original = fields(canonical(raw[key + "/source-return.json"]), "schema scope originalsSha256 sessionSha256 clock returnedNs",
            "CRYPTO_SOURCE_FIELDS")
        require(type(original["schema"]) is int and original["schema"] == 1 and original["scope"] == N.SOURCE_SCOPE and
            original["clock"] == O.clock_value(clock) and original["sessionSha256"] == files[key + "/session-result.json"][3] and
            original["originalsSha256"] == {name: files["P/acquisition-queries/" + name + ".bin"][3] for name in N.SOURCE_KEYS} and
            all(files[key + "/" + name + ".bin"][2:4] == files["P/acquisition-queries/" + name + ".bin"][2:4]
                for name in N.SOURCE_KEYS) and (digest_name is None or
                child[digest_name] == O.digest(raw[key + "/source-return.json"])), "CRYPTO_SOURCE")
        sources.append(original)
    for observed in (value["clock"], child["clock"], swindow["clock"], step["clock"], receiving["clock"], history["clock"]):
        _same(observed, O.clock_value(clock), "CRYPTO_CLOCK")
    require(primary.role == clock.role, "CRYPTO_NATIVE_ROLE")
    local_scope = _retained_crypto_tail(value, row, swindow, step, receiving, sources[2], pending, validation)
    authority = fields(canonical(raw["R/authority-return.json"]), "schema scope recipientWindowSha256 originalReadmissionSha256 "
        "workerIdentitySha256 matchSha256 serviceTimeBasisSha256 originalProposalSha256 filesSha256 pendingSha256 "
        "originalChain preCloseNs closedNs resourceCount retirement budgetAcceptance exportSaveAuthority", "CRYPTO_AUTHORITY_FIELDS")
    authority_names = {name.removeprefix("P/") for name in _history_names("gate")}
    authority_names.difference_update(("prelude.json", "initial-result.json"))
    authority_names.add("authority-window.json")
    require(type(authority["schema"]) is int and authority["schema"] == 1 and
        authority["scope"] == "INITIAL_RECIPIENT_USE_AUTHORITY_CLOSED_HISTORY_V1" and
        authority["recipientWindowSha256"] == O.digest(raw["R/recipient-window.json"]) and
        authority["originalReadmissionSha256"] == frame["originalReadmissionSha256"] and
        authority["workerIdentitySha256"] == O.digest(raw["P/worker-identity.json"]) and
        authority["matchSha256"] == O.digest(raw["R/worker-match.json"]) and
        authority["serviceTimeBasisSha256"] == files["P/worker-service-time.json"][3] and
        authority["originalProposalSha256"] == frame["originalProposalSha256"] and
        authority["filesSha256"] == {name: files["R/authority/" + name][3] for name in authority_names} and
        authority["pendingSha256"] == files["R/authority/authority-pending.json"][3] and
        first <= O.integer(authority["preCloseNs"]) <= O.integer(authority["closedNs"]) and
        type(authority["resourceCount"]) is int and 0 < authority["resourceCount"] <= MAX_MEMBERS and
        authority["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and authority["budgetAcceptance"] == "NOT_ADMITTED" and
        authority["exportSaveAuthority"] is False, "CRYPTO_AUTHORITY_LINKS")
    chain = fields(authority["originalChain"], "phaseSha256 childSha256 querySessionSha256 originalsSha256 checkedNs", "CRYPTO_AUTHORITY_CHAIN_FIELDS")
    require(chain["phaseSha256"] == {name: files["R/authority/service/" + name][3] for name in native.PHASE_FILES} and
        chain["childSha256"] == files["R/authority/service/child-result.json"][3] and
        chain["querySessionSha256"] == files["R/authority/acquisition-queries/session-result.json"][3] and
        chain["originalsSha256"] == {name: files["R/authority/acquisition-queries/" + name + ".bin"][3] for name in N.ORIGINAL_KEYS} and
        first <= O.integer(chain["checkedNs"]) <= authority["preCloseNs"], "CRYPTO_AUTHORITY_CHAIN")
    times = (first, authority["closedNs"], start["startedNs"], row["launchMinimumNs"], child["beganNs"], child["metadataLastNs"],
        sources[0]["returnedNs"], child["supplierReturnedNs"], sources[1]["returnedNs"], child["completedNs"], ack["closedNs"],
        row["completedNs"], row["finalStartedNs"], row["finalizedNs"], row["readStartedNs"], row["readbackCompletedNs"],
        value["capturedNs"], sources[2]["returnedNs"], retained, validation["preCloseNs"], validation["closedNs"],
        swindow["previousNs"], swindow["retainedNs"], step["lowerNs"])
    require(all(type(number) is int and 0 <= number < value["readEndNs"] for number in times) and
        tuple(sorted(times)) == times and times[-1] <= began and
        child["metadataLastNs"] < child["beganNs"] + 45 * O.NS and ack["closedNs"] < min(child["beganNs"] + 210 * O.NS, ends[0]) and
        row["completedNs"] < ends[0] and row["launchMinimumNs"] <= O.integer(birth["observedNs"]) <= row["completedNs"] and
        type(row["finalEndNs"]) is int and row["finalEndNs"] == min(ends[1], row["finalStartedNs"] + 45 * O.NS) and
        row["readEndNs"] == min(ends[2], row["readStartedNs"] + 30 * O.NS) and
        row["finalizedNs"] <= row["readStartedNs"] < row["finalEndNs"], "CRYPTO_CHRONOLOGY")
    declared = _crypto_roster(primary, value, context, child, raw["R/recipient-public.asc"],
        raw["R/crypto/recipient.asc"], raw["R/crypto/recipient.gpg"])
    return O.encoded({"schema": 1, "scope": "INITIAL_CUSTODY_RETAINED_CRYPTO_LINKS_ONLY_V1",
        "sidecarSha256": O.digest(raw["C/crypto-originals.json"]), "files": len(declared), "bytes": value["totalBytes"],
        "originalReceivingFirstLocal": local_scope,
        "missingOriginalIfRequiredForQualification": "UNAVAILABLE", "liveRecipient": "NOT_RESTORED",
        "currentAuthority": "NOT_ACQUIRED", "exportSaveAuthority": False})


_PRIMARY_OWNERS = {}


@dataclass(eq=False, repr=False)
class _PrimaryOwnerAnchor:
    handle: object
    binding: tuple
    rows: tuple = ()
    returned: tuple = ()
    snapshots: tuple = ()
    pending: object = None
    failure: object = None
    closing: object = None
    finished: bool = False
    busy: bool = False


class _PrimaryOwner:
    """Fixed file-only wrapper; actual returned resources precede every callback.

    Owner.acquire has a post-registration callback before its return. Here the
    maintained factories are called directly and their actual return AND original
    Owner ledger row are pinned first. No old owner/ledger is reconstructed. Only
    unchanged native Owner.close_one/close retire these actual new resources.
    """
    __slots__ = ("_bound",)

    def __init__(self, owner):
        require(type(self) is _PrimaryOwner and id(self) not in _PRIMARY_OWNERS and
            type(owner) is native.Owner and not owner.resources and not owner.errors and
            owner.original is None and owner.closed is False and owner.unknown is False, "COPY_NEW_OWNER")
        limits = (owner.first, owner.fence, owner.cancelled, owner.local_end, owner.work_limit, owner.final_limit)
        # The original native object/dictionary and public lists are independent
        # of this callback-facing handle. Private immutable tuples below retain
        # each actual return/row even if both visible roster lists are erased.
        self._bound = (owner, owner.__dict__, owner.resources, owner.errors, limits,
            N._history_graph(owner.first), [], [], [])
        _PRIMARY_OWNERS[id(self)] = _PrimaryOwnerAnchor(self, self._bound)
        self.structural()

    def _anchor(self):
        anchor = _PRIMARY_OWNERS.get(id(self))
        require(type(self) is _PrimaryOwner and type(anchor) is _PrimaryOwnerAnchor and
            anchor.handle is self, "COPY_ORIGINAL_OWNER_HANDLE")
        return anchor

    owner = property(lambda self: self._anchor().binding[0])
    ledger = property(lambda self: self._anchor().binding[2])
    errors = property(lambda self: self._anchor().binding[3])
    bound = property(lambda self: self._anchor().binding[4])
    graph = property(lambda self: self._anchor().binding[5])
    rows = property(lambda self: self._anchor().binding[6])
    returned = property(lambda self: self._anchor().binding[7])
    snapshots = property(lambda self: self._anchor().binding[8])
    pending = property(lambda self: self._anchor().pending)
    failure = property(lambda self: self._anchor().failure)
    closing = property(lambda self: self._anchor().closing)
    finished = property(lambda self: self._anchor().finished)
    busy = property(lambda self: self._anchor().busy)

    def structural(self):
        anchor = self._anchor()
        owner, dictionary, ledger, errors, bound, graph, rows, returned, snapshots = anchor.binding
        require(self._bound is anchor.binding and owner.__dict__ is dictionary, "COPY_ORIGINAL_OWNER_BINDING")
        N._check_history(graph)
        require(type(owner) is native.Owner and owner.resources is ledger and owner.errors is errors and
            owner.first is bound[0] and owner.fence is bound[1] and owner.cancelled is bound[2] and
            type(owner.local_end) is type(bound[3]) and owner.local_end == bound[3] and
            type(owner.work_limit) is type(bound[4]) and owner.work_limit == bound[4] and
            type(owner.final_limit) is type(bound[5]) and owner.final_limit == bound[5] and
            type(ledger) is list and type(errors) is list and type(rows) is list and type(returned) is list and
            len(ledger) == len(rows) == len(anchor.rows) == len(returned) == len(anchor.returned) <= MAX_MEMBERS and
            all(actual is original for actual, original in zip(rows, anchor.rows)) and
            all(actual is original for actual, original in zip(returned, anchor.returned)) and
            type(owner.closed) is bool and (not owner.closed or anchor.finished), "COPY_OWNER_CHANGED")
        for current, (row, label, resource, attempted, closed), actual in zip(ledger, anchor.rows, anchor.returned):
            require(current is row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                type(row["label"]) is str and row["label"] == label and row["owner"] is resource is actual and
                type(row["attempted"]) is bool and type(row["closed"]) is bool and
                (not row["closed"] or row["attempted"]) and
                ((row["attempted"] is attempted and row["closed"] is closed) or
                    anchor.closing is resource and not attempted and not closed and row["attempted"] is True),
                "COPY_LEDGER_CHANGED")
        require(len({id(row) for row, *_ in anchor.rows}) == len(anchor.rows) ==
            len({id(resource) for _, _, resource, _, _ in anchor.rows}), "COPY_RESOURCE_ALIAS")
        require(type(snapshots) is list and len(snapshots) == len(anchor.snapshots) and
            all(actual is original for actual, (original, _graph) in zip(snapshots, anchor.snapshots)),
            "COPY_SNAPSHOT_ROSTER_CHANGED")
        for snapshot, saved in anchor.snapshots:
            N._check_history(saved)

    def remember(self, error, *, unknown=False):
        anchor = self._anchor()
        owner = anchor.binding[0]  # Never report/close against a replacement callback-facing owner.
        if anchor.failure is None:
            anchor.failure = owner.original if owner.original is not None else error
        try:
            owner.error("custody-primary", error, unknown=unknown)
        except BaseException:
            owner.unknown = True
        if owner.unknown and not any(value is self for value in _PRIMARY_QUARANTINE):
            _PRIMARY_QUARANTINE.append(self)
        return anchor.failure

    def guard(self):
        try:
            self.structural()
            require(not self.finished and self.closing is None and self.failure is None and
                self.owner.original is None and self.owner.unknown is False and self.errors == [], "COPY_OWNER_FAILED")
            result = self.owner.end()
            self.structural()
            require(self.failure is None and self.owner.original is None and not self.owner.unknown and not self.errors,
                "COPY_CALLBACK_FAILED")
            return result
        except BaseException as error:
            try:
                self.structural()
            except BaseException:
                self.remember(error, unknown=True)
            raise self.remember(error)

    def acquire(self, label, factory):
        require(type(label) is str and label in ("directory", "reader", "writer", "snapshot", "embedded-reader"), "COPY_RESOURCE_LABEL")
        anchor = self._anchor()
        if anchor.busy:
            error = O.OriginError("INITIAL_CUSTODY_COPY_ALLOCATION_REENTRY")
            raise self.remember(error)
        anchor.busy = True
        try:
            self.guard()
            try:
                resource = factory()
            except BaseException as error:
                raise self.remember(error, unknown=True)
            anchor.pending = resource  # FIRST action; the original registry keeps this actual return on failure.
            self.structural()
            require(not any(saved is resource for _, _, saved, _, _ in anchor.rows), "COPY_DUPLICATE_RESOURCE")
            anchor.returned = (*anchor.returned, resource)
            self.returned.append(resource)
            row = {"label": label, "owner": resource, "attempted": False, "closed": False}
            self.ledger.append(row)
            anchor.rows = (*anchor.rows, (row, label, resource, False, False))
            self.rows.append(anchor.rows[-1])
            anchor.pending = None  # Both private immutable originals exist before the next callback.
            self.guard()
            return resource
        except BaseException as error:
            # An allocation can have returned before a hostile ledger mutation.
            # Never infer its missing row/handle was closed, or adopt a new row.
            unknown = anchor.pending is not None or len(anchor.returned) != len(anchor.rows)
            try:
                self.structural()
            except BaseException:
                unknown = True
            raise self.remember(error, unknown=unknown)
        finally:
            anchor.busy = False

    def retain_snapshot(self, snapshot):
        anchor = self._anchor()
        self.structural()
        require(type(snapshot) is _PrimarySnapshot and not anchor.finished and
            not any(original is snapshot for original, _graph in anchor.snapshots), "COPY_NEW_SNAPSHOT")
        anchor.snapshots = (*anchor.snapshots, (snapshot, N._history_graph(snapshot.__dict__)))
        self.snapshots.append(snapshot)
        self.structural()

    def close_one(self, resource):
        anchor = self._anchor()
        try:
            self.structural()
            require(anchor.closing is None and not self.owner.unknown and not anchor.finished, "COPY_CLOSE_NOT_KNOWN")
            index = next(number for number, row in enumerate(anchor.rows) if row[2] is resource)
            row, label, actual, attempted, closed = anchor.rows[index]
            require(not attempted and not closed, "COPY_CLOSE_RETRY")
            anchor.closing = resource
            self.owner.close_one(resource)
            self.structural()
            require(row["attempted"] is True and row["closed"] is True and not self.owner.unknown, "COPY_CLOSE_UNKNOWN")
            anchor.rows = (*anchor.rows[:index], (row, label, actual, True, True), *anchor.rows[index + 1:])
            self.rows[index] = anchor.rows[index]
            if self.owner.original is not None:
                self.remember(self.owner.original)
        except BaseException as error:
            raise self.remember(error, unknown=True)
        finally:
            anchor.closing = None

    def finish(self):
        # No repeated close, repaired ledger or successful return after UNKNOWN.
        anchor = self._anchor()
        require(not anchor.finished, "COPY_OWNER_CLOSE_RETRY")
        try:
            self.structural()
            require(not self.owner.unknown and not anchor.busy, "COPY_OWNER_QUARANTINED_OR_BUSY")
            for _row, _label, resource, attempted, closed in reversed(anchor.rows):
                if not attempted:
                    self.close_one(resource)
                else:
                    require(closed, "COPY_OWNER_PARTIAL_CLOSE")
            self.structural()
            anchor.finished = True
            self.owner.close()  # All genuine resources already known closed; none can be skipped by a callback.
            self.structural()
            require(self.owner.closed is True and not self.owner.unknown and
                all(attempted and closed for _, _, _, attempted, closed in anchor.rows), "COPY_OWNER_CLOSE_INCOMPLETE")
            if self.owner.original is not None:
                self.remember(self.owner.original)
        except BaseException as error:
            anchor.finished = True
            unknown = self.owner.unknown
            try:
                self.structural()
            except BaseException:
                unknown = True
            self.remember(error, unknown=unknown)
        if self.failure is not None:
            raise self.failure
        require(not self.errors, "COPY_OWNER_ERRORS")
        return O.encoded({"schema": 1, "scope": "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1",
            "resources": [{"ordinal": number, "label": label, "closeAttempted": attempted, "closed": closed}
                for number, (_, label, _, attempted, closed) in enumerate(anchor.rows)],
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False})


def _private(owner, path, *, create=False, parent=None, name=None):
    end = owner.guard()
    if parent is not None:
        require(create is True and name == "copied-evidence" and path == parent.path / name, "COPY_FIXED_CHILD")
        factory = lambda: parent.create_directory(name, deadline=end)
    elif create:
        factory = lambda: Q._new_private_directory(path)
    else:
        factory = lambda: native.windows.open_private_directory(path) if os.name == "nt" else Q._PosixDirectory(path)
    directory = owner.acquire("directory", factory)
    require(type(directory) is (native.windows.PrivateDirectory if os.name == "nt" else Q._PosixDirectory), "COPY_DIRECTORY_TYPE")
    require(directory.path == path, "COPY_DIRECTORY_PATH")
    identity = tuple(native.directory_identity(list(directory.identity), owner.owner.first.clock.role))
    directory.verify()
    owner.guard()
    require(directory.path == path and tuple(directory.identity) == identity, "COPY_DIRECTORY_CHANGED")
    return directory


def _consume(owner, reader, count, checksum, verify, *, writer=None, retain=False):
    require(type(count) is int and 0 <= count <= MAX_BYTES and type(retain) is bool and
        (not retain or count <= native.LIMIT), "COPY_STREAM_LIMIT")
    if checksum is not None:
        digest(checksum)
    total, hashed, pieces = 0, hashlib.sha256(), []
    try:
        while total < count:
            owner.guard()
            piece = reader.read(min(COPY_CHUNK, count - total))
            require(type(piece) is bytes and 0 < len(piece) <= min(COPY_CHUNK, count - total), "COPY_SHORT_OR_NONBYTE_READ")
            total += len(piece)
            hashed.update(piece)
            if retain:
                pieces.append(piece)
            owner.guard()
            if writer is not None:
                written = writer.write(piece)
                require(type(written) is int and written == len(piece), "COPY_SHORT_WRITE")
                owner.guard()
        owner.guard()
        tail = reader.read(1)
        require(type(tail) is bytes and tail == b"" and total == count and
            (checksum is None or hashed.hexdigest() == checksum), "COPY_SIZE_HASH_EOF")
        verify()
        owner.guard()
        if writer is not None:
            writer.sync()
            info = writer.verify()
            write_metadata = O.encoded(info.as_dict())  # Actual returned value, before any callback or close.
            require(type(info.size) is int and info.size == count, "COPY_WRITER_SIZE")
            owner.guard()
        return b"".join(pieces) if retain else ((hashed.hexdigest(), write_metadata) if writer is not None else hashed.hexdigest())
    except BaseException as error:
        raise owner.remember(error)
    finally:
        for resource in (reader, writer):
            if resource is not None and not owner.owner.unknown:
                try:
                    owner.close_one(resource)
                except BaseException as error:
                    owner.remember(error, unknown=True)
        if owner.failure is not None:
            raise owner.failure


def _read_private(owner, directory, name, maximum):
    """Small preliminary read with a real separately registered reader, even empty."""
    Q._component(name)
    end = owner.guard()
    path = directory.path / name
    if os.name == "nt":
        reader = owner.acquire("reader", lambda: directory.open_file(name, max_bytes=maximum, deadline=end))
        require(type(reader) is native.windows.NativeFile, "COPY_READER_TYPE")
        original = reader.initial_info
        count = original.size
        def verify():
            require(reader.verify() == original, "COPY_METADATA_READER_CHANGED")
    else:
        reader = owner.acquire("reader", lambda: Q._posix_stream(path, os.O_RDONLY | os.O_NOFOLLOW, "rb"))
        require(type(reader) is io.BufferedReader, "COPY_READER_TYPE")
        original = Q._file_info(path, reader, maximum)
        count = original.size
        def verify():
            directory.verify()
            require(Q._file_info(path, reader, maximum) == original, "COPY_METADATA_READER_CHANGED")
    return _consume(owner, reader, count, None, verify, retain=True)


@dataclass(frozen=True, repr=False)
class _PrimarySnapshot:
    group: str
    path: object
    directory: object
    pin: tuple
    native: object
    original: object
    metadata: tuple
    graph: tuple
    windows: bool


def _snapshot_metadata(entries, windows):
    require(type(windows) is bool and hasattr(entries, "items") and 0 < len(entries) <= MAX_MEMBERS, "COPY_SNAPSHOT_FIELDS")
    result = []
    for name, value in sorted(entries.items()):
        require(type(name) is str and (name == "" or not name.startswith("/") and
            all(Q._component(part) == part for part in name.split("/"))), "COPY_SNAPSHOT_NAME")
        if windows:
            require(type(value) is native.windows.FileInfo and type(value.is_directory) is bool and
                type(value.size) is int and value.size >= 0, "COPY_WINDOWS_METADATA")
            identity = tuple(native.directory_identity(list(value.identity), "windows-x64"))
            directory, count, raw = value.is_directory, value.size, O.encoded(value.as_dict())
        else:
            require(type(value) is tuple and len(value) == 8 and all(type(number) is int for number in value) and
                (stat.S_ISDIR(value[2]) or stat.S_ISREG(value[2])) and value[5] >= 0, "COPY_POSIX_METADATA")
            identity, directory, count = value[:2], stat.S_ISDIR(value[2]), value[5]
            raw = O.encoded({"posixStamp": list(value)})
        result.append((name, directory, identity, count, raw))
    require(result[0][0] == "" and result[0][1] is True and
        len({row[0].casefold() for row in result}) == len(result) and
        len({row[2] for row in result}) == len(result), "COPY_SNAPSHOT_ALIASES")
    return tuple(result)


def _snapshot(owner, group, directory):
    end, windows = owner.guard(), os.name == "nt"
    if type(owner.owner.fence) is Window:
        end = owner.owner.fence.deadline(900)  # Whole original work interval; NativeFile's900 cap is unchanged.
    used_bytes, used_members = _aggregate(tuple(owner.snapshots))
    require(used_members < MAX_MEMBERS, "COPY_SNAPSHOT_MEMBER_BUDGET")
    path, pin = directory.path, tuple(directory.identity)
    if windows:
        resource = owner.acquire("snapshot", lambda: directory.snapshot(max_bytes=MAX_BYTES - used_bytes,
            max_members=MAX_MEMBERS - used_members, deadline=end))
        require(type(resource) is native.windows.Snapshot, "COPY_SNAPSHOT_TYPE")
        original = resource.entries
    else:
        resource = None
        try:
            original = native.posix._snapshot(path, MAX_BYTES - used_bytes, MAX_MEMBERS - used_members, end)
        except BaseException as error:
            raise owner.remember(error, unknown=True)  # The unchanged supplier owns its internal descriptor close.
    # Pin every actually returned stamp before the next clock/cancellation call.
    snapshot = _PrimarySnapshot(group, path, directory, pin, resource, original, _snapshot_metadata(original, windows),
        N._history_graph(original, path), windows)
    owner.retain_snapshot(snapshot)
    owner.guard()
    _snapshot_current(owner, snapshot)
    return snapshot


def _snapshot_current(owner, snapshot, *, rescan=False):
    require(type(snapshot) is _PrimarySnapshot and any(item is snapshot for item in owner.snapshots), "COPY_ORIGINAL_SNAPSHOT")
    N._check_history(snapshot.graph)
    require(snapshot.directory.path == snapshot.path and tuple(snapshot.directory.identity) == snapshot.pin and
        _snapshot_metadata(snapshot.original, snapshot.windows) == snapshot.metadata and
        snapshot.metadata[0][2] == snapshot.pin, "COPY_SNAPSHOT_CHANGED")
    snapshot.directory.verify()
    if snapshot.windows:
        require(snapshot.native.entries is snapshot.original, "COPY_WINDOWS_SNAPSHOT_CHANGED")
        if rescan:
            require(_snapshot_metadata(snapshot.native.verify(), True) == snapshot.metadata, "COPY_WINDOWS_SNAPSHOT_CHANGED")
    elif rescan:
        try:
            current = native.posix._snapshot(snapshot.path, MAX_BYTES, MAX_MEMBERS, owner.guard())
        except BaseException as error:
            raise owner.remember(error, unknown=True)
        require(_snapshot_metadata(current, False) == snapshot.metadata, "COPY_SOURCE_OR_DESTINATION_CHANGED")


def _indexed_snapshots(primary, sources, handoff, handoff_name):
    """Exact source file/directory/empty rosters and all recorded original pins."""
    actual = {snapshot.group + ("/" + name if name else ""): (directory, identity, count, metadata)
        for snapshot in sources for name, directory, identity, count, metadata in snapshot.metadata}
    require(tuple(snapshot.group for snapshot in sources) == tuple(name for name, _ in primary.roots) and
        set(actual) == {row[0] for row in primary.directories} | {row[0] for row in primary.files}, "COPY_EXACT_SOURCE_ROSTER")
    for key, pin, _provenance in primary.directories:
        require(actual[key][0] is True and (pin is None or actual[key][1] == pin), "COPY_ORIGINAL_DIRECTORY_PIN")
    for key, maximum, count, checksum, _provenance in primary.files:
        require(actual[key][0] is False and actual[key][2] == count <= maximum, "COPY_DECLARED_FILE_SIZE")
        digest(checksum)
    require(tuple(row[0] for row in handoff.metadata) == ("", handoff_name) and
        handoff.metadata[1][1] is False and handoff.metadata[1][3] == len(primary.handoff_raw), "COPY_HANDOFF_ROSTER")
    combined = [row for snapshot in (*sources, handoff) for row in snapshot.metadata]
    require(len({row[2] for row in combined}) == len(combined), "COPY_SOURCE_IDENTITY_ALIAS")
    return tuple(sorted(actual.items()))


def _aggregate(snapshots, additional_bytes=0, additional_members=0):
    require(type(additional_bytes) is int and additional_bytes >= 0 and
        type(additional_members) is int and additional_members >= 0, "COPY_AGGREGATE_INPUTS")
    total = sum(row[3] for snapshot in snapshots for row in snapshot.metadata if not row[1]) + additional_bytes
    count = sum(len(snapshot.metadata) for snapshot in snapshots) + additional_members
    require(total <= MAX_BYTES and count <= MAX_MEMBERS, "COPY_AGGREGATE_CAP")
    return total, count


def _snapshot_reader(owner, snapshot, name):
    require(type(snapshot) is _PrimarySnapshot and any(item is snapshot for item in owner.snapshots), "COPY_ORIGINAL_SNAPSHOT")
    N._check_history(snapshot.graph)
    require(snapshot.directory.path == snapshot.path and tuple(snapshot.directory.identity) == snapshot.pin and
        (not snapshot.windows or snapshot.native.entries is snapshot.original), "COPY_SOURCE_SNAPSHOT_CHANGED")
    rows = {row[0]: row for row in snapshot.metadata}
    require(name in rows and rows[name][1] is False, "COPY_SOURCE_FILE_REQUIRED")
    if snapshot.windows:
        reader = owner.acquire("reader", lambda: snapshot.native.open_file(name))
        require(type(reader) is native.windows.NativeFile, "COPY_READER_TYPE")
        original = snapshot.original[name]
        def verify():
            require(reader.verify() == original, "COPY_NATIVE_FILE_CHANGED")
    else:
        reader = owner.acquire("reader", lambda: native.posix._open_member(snapshot.path, name, snapshot.original))
        require(type(reader) is io.BufferedReader, "COPY_READER_TYPE")
        original = snapshot.original[name]
        def verify():
            require(native.posix._stamp(os.fstat(reader.fileno())) == original, "COPY_POSIX_FILE_CHANGED")
    return reader, verify


def _member_name(ordinal):
    require(type(ordinal) is int and 0 <= ordinal < MAX_MEMBERS, "COPY_MEMBER_ORDINAL")
    return "member-" + str(ordinal).zfill(5) + ".bin"


def _copy_member(owner, destination, ordinal, count, checksum, *, snapshot=None, name=None, embedded=None):
    require((snapshot is None) is (embedded is not None), "COPY_ONE_ORIGIN")
    target = _member_name(ordinal)
    if embedded is not None:
        require(type(embedded) is bytes and len(embedded) == count and O.digest(embedded) == checksum, "COPY_EMBEDDED_BYTES")
        reader = owner.acquire("embedded-reader", lambda: io.BytesIO(embedded))
        def verify():
            require(type(reader) is io.BytesIO and reader.getvalue() == embedded, "COPY_EMBEDDED_CHANGED")
    else:
        reader, verify = _snapshot_reader(owner, snapshot, name)
    end = owner.guard()
    writer = owner.acquire("writer", lambda: destination.create_file(target, max_bytes=count, deadline=end))
    require(type(writer) is (native.windows.NativeFile if os.name == "nt" else Q._PosixSink), "COPY_WRITER_TYPE")
    returned_hash, write_metadata = _consume(owner, reader, count, checksum, verify, writer=writer)
    require(returned_hash == checksum, "COPY_RETURNED_HASH")
    return target, write_metadata


def _written_matches(raw, node, windows):
    metadata = canonical(raw)
    if windows:
        require(O.encoded(metadata) == node[4], "COPY_WRITER_SNAPSHOT_PIN")
    else:
        stamp = fields(canonical(node[4]), "posixStamp", "COPY_POSIX_STAMP_FIELDS")["posixStamp"]
        require(type(stamp) is list and len(stamp) == 8 and all(type(value) is int for value in stamp),
            "COPY_POSIX_STAMP")
        _same(metadata, {"device": stamp[0], "inode": stamp[1], "size": stamp[5],
            "mtime_ns": stamp[6], "ctime_ns": stamp[7]}, "COPY_WRITER_SNAPSHOT_PIN")


def _copy_indexed(owner, primary, sources, handoff, handoff_name, destination):
    """Fixed low-level PRIMARY copying; supplied models alone cannot mint a return."""
    source_records = _indexed_snapshots(primary, sources, handoff, handoff_name)
    source_bytes = sum(row[2] for row in primary.files) + len(primary.handoff_raw)
    embedded_bytes = sum(len(raw) for _, raw in primary.embedded)
    destination_count = len(primary.files) + 1 + len(primary.embedded)
    _aggregate((*sources, handoff), source_bytes + embedded_bytes, destination_count + 1)
    groups = {snapshot.group: snapshot for snapshot in sources}
    members = []
    for relative, maximum, count, checksum, provenance in primary.files:
        group, name = relative.split("/", 1)
        target, written = _copy_member(owner, destination, len(members), count, checksum, snapshot=groups[group], name=name)
        members.append({"member": target, "bytes": count, "sha256": checksum, "origin": "PRIMARY", "original": relative,
            "originalMaximum": maximum, "provenance": provenance, "carrier": "INDEXED_DISK_ORIGINAL",
            "destinationWriteMetadata": O.parse(written)})
    target, written = _copy_member(owner, destination, len(members), len(primary.handoff_raw), O.digest(primary.handoff_raw),
        snapshot=handoff, name=handoff_name)
    members.append({"member": target, "bytes": len(primary.handoff_raw), "sha256": O.digest(primary.handoff_raw),
        "origin": "PRIMARY", "original": handoff_name, "provenance": "ACTUAL_PRIMARY_HANDOFF_DISK_BYTES", "carrier": "HANDOFF",
        "destinationWriteMetadata": O.parse(written)})
    for name, raw in primary.embedded:
        target, written = _copy_member(owner, destination, len(members), len(raw), O.digest(raw), embedded=raw)
        members.append({"member": target, "bytes": len(raw), "sha256": O.digest(raw), "origin": "PRIMARY", "original": name,
            "provenance": "ORIGINAL_EMBEDDED_BYTES_FROM_EXACT_HANDOFF", "carrier": "EMBEDDED_NOT_DISK_ORIGINAL",
            "destinationWriteMetadata": O.parse(written)})
    readback = _snapshot(owner, "COPIED_PRIMARY", destination)
    require(tuple(row[0] for row in readback.metadata) == ("", *(row["member"] for row in members)) and
        all(not row[1] for row in readback.metadata[1:]), "COPY_DESTINATION_ROSTER")
    _aggregate((*sources, handoff, readback))
    all_metadata = [row for snapshot in (*sources, handoff, readback) for row in snapshot.metadata]
    require(len({row[2] for row in all_metadata}) == len(all_metadata), "COPY_DESTINATION_SOURCE_ALIAS")
    for item, node in zip(members, readback.metadata[1:]):
        _written_matches(O.encoded(item["destinationWriteMetadata"]), node, readback.windows)
        reader, verify = _snapshot_reader(owner, readback, item["member"])
        _consume(owner, reader, item["bytes"], item["sha256"], verify)
    for snapshot in (*sources, handoff, readback):
        owner.guard()
        _snapshot_current(owner, snapshot, rescan=True)
        owner.guard()
    require(_indexed_snapshots(primary, sources, handoff, handoff_name) == source_records, "COPY_FINAL_SOURCE_ROSTER")
    return O.encoded({"schema": 1, "scope": PRIMARY_SCOPE, "origin": "PRIMARY", "members": members,
        "sourceMetadata": [[name, [directory, list(identity), count, O.parse(metadata)]]
            for name, (directory, identity, count, metadata) in source_records],
        "originalDirectories": [{"relative": name, "identity": None if pin is None else list(pin), "provenance": provenance}
            for name, pin, provenance in primary.directories],
        "handoffMetadata": [[name, directory, list(identity), count, O.parse(metadata)]
            for name, directory, identity, count, metadata in handoff.metadata],
        "destination": str(destination.path), "destinationIdentity": list(readback.pin),
        "destinationMetadata": [[name, directory, list(identity), count, O.parse(metadata)]
            for name, directory, identity, count, metadata in readback.metadata],
        "memberCount": len(members), "totalBytes": sum(row["bytes"] for row in members), "nextOrdinal": len(members),
        "freeze": "NOT_FINAL_THREE_ORIGIN_FREEZE", "remainingOrigins": list(ORIGINS[1:]),
        "productiveAuthority": False, "currentAuthority": "NOT_ACQUIRED", "exportSaveAuthority": False})


@dataclass(frozen=True, repr=False)
class PrimaryCopy:
    """Same-process authenticated PRIMARY return, NOT current authority/export."""
    window: object
    primary: Primary
    history: bytes
    crypto_history: object
    copy: bytes
    originals: tuple
    preliminary_close: bytes
    native_close: bytes


_PRIMARY_RETURNS = {}
_CREDENTIAL_NAMES = (O.wire.TOKEN_ENV, "GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN",
    "ACTIONS_CACHE_URL", "ACTIONS_RESULTS_URL")
_ACTUAL_NAMES = (PRIMARY_OUTCOME, PRIMARY_RESULT, PRIMARY_HANDOFF, "RUNNER_TEMP", "GITHUB_WORKSPACE", "GITHUB_EVENT_PATH",
    "GITHUB_JOB", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_REPOSITORY", "GITHUB_EVENT_NAME", "GITHUB_REF",
    "GITHUB_SHA", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME")


def _actual_inputs(expected):
    require(type(expected) is tuple and tuple(os.environ.get(name) for name in _ACTUAL_NAMES) == expected and
        os.environ.get(PRIMARY_OUTCOME) == "success" and not any(name in os.environ for name in _CREDENTIAL_NAMES),
        "ACTUAL_PRIMARY_INPUT_OR_CREDENTIAL_CHANGED")
    digest(os.environ.get(PRIMARY_RESULT))
    digest(os.environ.get(PRIMARY_HANDOFF))


def _begin_primary(kind):
    previous = _PRIMARY_ATTEMPTS.get("fixed")
    if previous is not None:
        error = O.OriginError("INITIAL_CUSTODY_PRIMARY_ATTEMPT_ALREADY_USED")
        if previous["state"] == "STARTED":
            if previous["failure"] is None:
                previous["failure"] = error
            previous["state"] = "FAILED"
            raise previous["failure"]
        raise error
    attempt = {"kind": kind, "state": "STARTED", "owners": [], "return": None, "failure": None}
    _PRIMARY_ATTEMPTS["fixed"] = attempt
    return attempt


_PRELIMINARIES = {}


@dataclass(eq=False, repr=False)
class _PreliminaryAnchor:
    handle: object
    binding: tuple
    graph: tuple
    end: float
    last: int
    local_last: float
    owner: object = None
    owner_anchor: object = None
    closed: bool = False
    close_graph: tuple = ()
    busy: bool = False
    failure: object = None


class _Preliminary:
    """Only actually observed CURRENT custody frontiers under original S+30.

    This unbound Owner seam does not use serialized LOCAL, old receiving state or
    a repaired Window. The original S/LOCAL are later supplied unchanged to Window;
    its first genuine observation must exceed both known-close high-water values.
    """
    __slots__ = ("_bound",)

    def __init__(self, first, local, boot, actual, cancelled):
        require(type(self) is _Preliminary and id(self) not in _PRELIMINARIES, "PRELIMINARY_NOT_NEW")
        graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        local_value(local)
        digest(boot)
        require(type(actual) is tuple and callable(cancelled), "PRELIMINARY_INPUTS")
        self._bound = (first, local, boot, actual, cancelled)
        end = O.wire._directed_deadline(local, 30, O.integer(first.nanoseconds + 30 * O.NS), first.nanoseconds)
        _PRELIMINARIES[id(self)] = _PreliminaryAnchor(self, self._bound, graph, end, first.nanoseconds, local)
        self.structural()

    def _anchor(self):
        anchor = _PRELIMINARIES.get(id(self))
        require(type(self) is _Preliminary and type(anchor) is _PreliminaryAnchor and anchor.handle is self,
            "PRELIMINARY_ORIGINAL_HANDLE")
        return anchor

    bound = property(lambda self: self._anchor().binding)
    graph = property(lambda self: self._anchor().graph)
    end = property(lambda self: self._anchor().end)
    last = property(lambda self: self._anchor().last)
    local_last = property(lambda self: self._anchor().local_last)
    owner = property(lambda self: self._anchor().owner)
    busy = property(lambda self: self._anchor().busy)
    failure = property(lambda self: self._anchor().failure)

    @staticmethod
    def _error(anchor, error):
        if anchor.failure is None:
            anchor.failure = error
        return anchor.failure

    def _current(self, anchor):
        require(_PRELIMINARIES.get(id(self)) is anchor and self._bound is anchor.binding,
            "PRELIMINARY_ORIGINAL_BINDING")
        N._check_history(anchor.graph)
        if anchor.owner is not None:
            require(anchor.owner._anchor() is anchor.owner_anchor, "PRELIMINARY_ORIGINAL_OWNER")
            anchor.owner.structural()
            owner = anchor.owner.owner
            if owner.closed:
                require(anchor.owner.finished and anchor.owner.failure is None and owner.original is None and
                    owner.unknown is False and anchor.owner.errors == [] and
                    all(attempted and closed for _, _, _, attempted, closed in anchor.owner_anchor.rows),
                    "PRELIMINARY_CLOSE_UNKNOWN")
                if not anchor.closed:
                    anchor.close_graph = N._history_graph(owner)
                    anchor.closed = True
            require(not anchor.closed or owner.closed is True, "PRELIMINARY_CLOSE_REVERSED")
            N._check_history(anchor.close_graph)

    def structural(self, expected=None):
        """Passive original binding/known-close guard; no revived metadata IO30."""
        anchor = self._anchor()
        try:
            require(expected is None or anchor is expected, "PRELIMINARY_ORIGINAL_ANCHOR")
            self._current(anchor)
        except BaseException as error:
            raise self._error(anchor, error)

    def _begin(self):
        anchor = self._anchor()
        if anchor.failure is not None:
            raise anchor.failure
        try:
            self._current(anchor)
            require(not anchor.busy, "PRELIMINARY_REENTRY")
            anchor.busy = True
            return anchor
        except BaseException as error:
            raise self._error(anchor, error)

    def bind_owner(self, wrapper):
        anchor = self._begin()
        try:
            first, _local, _boot, _actual, _cancelled = anchor.binding
            require(anchor.owner is None and type(wrapper) is _PrimaryOwner and not wrapper.rows and
                not wrapper.finished and wrapper.owner.first is first and wrapper.owner.fence is None and
                wrapper.owner.local_end == anchor.end and wrapper.owner.work_limit is None and
                wrapper.owner.final_limit is None and wrapper.owner.early_last == first.nanoseconds and
                getattr(wrapper.owner.cancelled, "__self__", None) is self and
                getattr(wrapper.owner.cancelled, "__func__", None) is _Preliminary.observe,
                "PRELIMINARY_NEW_OWNER_BINDING")
            wrapper.structural()
            anchor.owner, anchor.owner_anchor = wrapper, wrapper._anchor()
            self._current(anchor)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def observe(self):
        anchor = self._begin()
        try:
            first, local, boot, actual, cancelled = anchor.binding
            for number in range(2):
                self._current(anchor)
                if anchor.owner is not None:
                    anchor.last = max(anchor.last, O.integer(anchor.owner.owner.early_last))
                before = local_value(time.monotonic())
                require(anchor.local_last <= before < anchor.end, "PRELIMINARY_LOCAL_EXPIRED_OR_BACKWARDS")
                anchor.local_last = before
                self._current(anchor)
                observed = O.clocks.checked_now(first.clock, minimum_ns=anchor.last)
                anchor.last = O.integer(observed, anchor.last)
                self._current(anchor)
                require(anchor.last < first.nanoseconds + 30 * O.NS and anchor.busy and anchor.failure is None,
                    "PRELIMINARY_RAW_EXPIRED_OR_CHANGED")
                _actual_inputs(actual)
                current_boot = C.boot_digest(first.clock.role)
                self._current(anchor)
                require(type(current_boot) is str and current_boot == boot, "PRELIMINARY_BOOT_CHANGED")
                if number == 0:
                    last, latest = anchor.last, anchor.local_last
                    cancelled()
                    self._current(anchor)
                    require(anchor.last == last and anchor.local_last == latest and anchor.busy and anchor.failure is None,
                        "PRELIMINARY_CALLBACK_CHANGED")
            after = local_value(time.monotonic())
            require(anchor.local_last <= after < anchor.end, "PRELIMINARY_FINAL_LOCAL")
            anchor.local_last = after
            self._current(anchor)
            require(anchor.busy and anchor.failure is None, "PRELIMINARY_FINAL_CHANGED")
            return anchor.last
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False


def copy_primary(kind, *, cancelled):
    """One fixed authentic Step-to-PRIMARY copy. No CLI/outputs/freeze/export.

    The caller already removed credentials into its private stack. This operation
    owns preliminary/native files only; the next authority caller MUST consume
    checked_primary's original return and its same Window, not serialized times.
    """
    attempt = _begin_primary(kind)  # Irreversible before time, paths, callbacks or allocation.
    preliminary = active = window = result = None
    failure = None
    try:
        require(kind in ("gate", "worker") and callable(cancelled), "PRIMARY_ENTRY")
        actual = tuple(os.environ.get(name) for name in _ACTUAL_NAMES)
        _actual_inputs(actual)
        require(not _PRIMARY_QUARANTINE and not native.QUARANTINE and not Q.QUARANTINE and
            not native.diagnostics._QUARANTINE and not C.QUARANTINE, "PRIMARY_PRIOR_UNKNOWN")
        local = local_value(time.monotonic())  # The FIRST current LOCAL, never restarted after metadata.
        first = O.clocks.observe()
        first_graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        require(native.processes.host_role() == first.clock.role, "PRIMARY_NATIVE_ROLE")
        boot = digest(C.boot_digest(first.clock.role))
        N._check_history(first_graph)
        preliminary = _Preliminary(first, local, boot, actual, cancelled)
        preliminary.observe()
        original_roots, handoff_path, custody_path = _paths(kind)
        handoff_name = N.GATE_HANDOFF_FILE if kind == "gate" else N.WORKER_HANDOFF_FILE
        pre_owner = native.Owner(preliminary.end, first=first, cancelled=preliminary.observe)
        active = _PrimaryOwner(pre_owner)
        attempt["owners"].append(active)
        preliminary.bind_owner(active)
        handoff_dir = _private(active, handoff_path)
        handoff_binding = (handoff_path, tuple(native.directory_identity(list(handoff_dir.identity), first.clock.role)))
        handoff_graph = N._history_graph(handoff_binding)
        handoff_raw = _read_private(active, handoff_dir, handoff_name, native.LIMIT)
        primary = primary_record(kind, first.clock.role, original_roots, handoff_binding[0], handoff_binding[1], handoff_raw,
            outcome=actual[0], result_sha256=actual[1], handoff_sha256=actual[2])
        primary_graph = N._history_graph(primary.__dict__)
        names = _history_names(kind)
        metadata_dirs, metadata_pins, originals = {}, {}, {}
        primary_pins = {name: pin for name, pin, _ in primary.directories}
        file_rows = {row[0]: row for row in primary.files}
        for name in names:
            parent, leaf = name.rsplit("/", 1)
            group, *parts = parent.split("/")
            if parent not in metadata_dirs:
                path = original_roots[group].joinpath(*parts)
                directory = _private(active, path)
                pin = tuple(directory.identity)
                require(parent in primary_pins and (primary_pins[parent] is None or primary_pins[parent] == pin),
                    "PRELIMINARY_ORIGINAL_DIRECTORY")
                metadata_dirs[parent], metadata_pins[parent] = directory, pin
            require(name in file_rows, "PRELIMINARY_INDEXED_NAME")
            originals[name] = _read_private(active, metadata_dirs[parent], leaf, file_rows[name][1])
        _indexed_originals(primary, originals, names)
        context = canonical(originals["P/context.json"])
        first_use = O.integer(context["observed"]["firstUseAt"], 1)
        observed, path, event = N.host_context(first_use)
        require(path == original_roots["P"], "PRIMARY_ACTUAL_PATH")
        interpreter = str(Path(sys.executable).resolve(strict=True))
        history_raw = primary_history(primary, originals, observed, event, first.clock, interpreter)
        history = canonical(history_raw)
        require(history["originalBootDigest"] == boot and history["originalPreviousNs"] <= first.nanoseconds,
            "PRIMARY_ORIGINAL_BOOT_OR_CHRONOLOGY")
        limits = schedule(kind, history["originalJobBasisNs"], first.nanoseconds)
        N._check_history(primary_graph)
        preliminary.observe()
        preliminary_close = active.finish()
        preliminary.observe()  # Includes actual original metadata Owner's known-close RAW and LOCAL.
        preliminary_anchor = preliminary._anchor()
        require(preliminary_anchor.closed, "PRELIMINARY_CLOSE_NOT_RETAINED")
        carried_ns, carried_local = preliminary.last, preliminary.local_last
        require(carried_ns < limits["workEndNs"], "PRELIMINARY_SPENT_WORK")
        active = None
        originals = tuple(sorted(originals.items()))
        originals_graph = N._history_graph(originals)

        def current():
            require(_PRIMARY_ATTEMPTS.get("fixed") is attempt and attempt["state"] in ("STARTED", "RETURNED") and
                attempt["failure"] is None, "PRIMARY_ATTEMPT_CHANGED")
            _actual_inputs(actual)
            preliminary.structural(preliminary_anchor)
            N._check_history(handoff_graph)
            N._check_history(primary_graph)
            N._check_history(originals_graph)
            require(type(window) is Window and window._anchor().last >= carried_ns and
                window._anchor().local_last >= carried_local, "PRIMARY_PRELIMINARY_HIGH_WATER_LOST")
            if active is not None:
                active.structural()
            cancelled()
            _actual_inputs(actual)
            preliminary.structural(preliminary_anchor)
            N._check_history(handoff_graph)
            N._check_history(primary_graph)
            N._check_history(originals_graph)
            if active is not None:
                active.structural()
            require(_PRIMARY_ATTEMPTS.get("fixed") is attempt and attempt["state"] in ("STARTED", "RETURNED") and
                attempt["failure"] is None, "PRIMARY_CALLBACK_ATTEMPT_CHANGED")

        window = Window(first, local, boot, limits, current)
        # No anchor mutation/reconstruction: a real same-process observation must
        # exceed the genuine preliminary close. S and all six limits stay original.
        window.now(minimum=carried_ns)
        owner = native.Owner(window.deadline(900, final=True), window, first=first, cancelled=current)
        owner.work_limit, owner.final_limit = window.work, window.final
        active = _PrimaryOwner(owner)
        attempt["owners"].append(active)
        sources = tuple(_snapshot(active, name, _private(active, path)) for name, path in primary.roots)
        handoff = _snapshot(active, "HANDOFF", _private(active, handoff_path))
        _indexed_snapshots(primary, sources, handoff, handoff_name)
        require(handoff.path == handoff_binding[0] and handoff.pin == handoff_binding[1] and
            canonical(primary.handoff_raw)["directoryIdentity"] == list(handoff_binding[1]), "PRIMARY_HANDOFF_PIN_CHANGED")
        actual_pins = {snapshot.group + ("/" + name if name else ""): pin
            for snapshot in sources for name, directory, pin, _count, _metadata in snapshot.metadata if directory}
        require(all(actual_pins[name] == pin for name, pin in metadata_pins.items()), "PRIMARY_METADATA_PIN_CHANGED")
        # Every metadata blob is later copied from disk and checked again against
        # the SAME primary index. Early metadata never substitutes for a disk copy.
        crypto_raw = None
        if kind == "worker":
            groups, crypto_originals = {snapshot.group: snapshot for snapshot in sources}, {}
            for name in _crypto_names():
                group, relative = name.split("/", 1)
                _, maximum, count, checksum, _ = file_rows[name]
                reader, verify = _snapshot_reader(active, groups[group], relative)
                crypto_originals[name] = _consume(active, reader, count, checksum, verify, retain=True)
            crypto_raw = crypto_history(primary, crypto_originals, history_raw, interpreter)
        destination_root = _private(active, custody_path, create=True)
        require(native._initializer_names(owner, destination_root) == (), "PRIMARY_NEW_CUSTODY_NOT_EMPTY")
        destination = _private(active, custody_path / "copied-evidence", create=True,
            parent=destination_root, name="copied-evidence")
        require(native._initializer_names(owner, destination) == (), "PRIMARY_NEW_COPY_NOT_EMPTY")
        copy_raw = _copy_indexed(active, primary, sources, handoff, handoff_name, destination)
        canonical(copy_raw)  # Existing2MiB record ceiling; no unbounded metadata map.
        require(native._initializer_names(owner, destination_root) == ("copied-evidence",), "PRIMARY_CUSTODY_ROSTER_CHANGED")
        require(N.host_context(first_use) == (observed, original_roots["P"], event) and
            _paths(kind) == (original_roots, handoff_path, custody_path) and
            str(Path(sys.executable).resolve(strict=True)) == interpreter, "PRIMARY_FINAL_ACTUAL_CONTEXT")
        N._check_history(primary_graph)
        window.now()
        native_close = active.finish()
        window.now()  # A late native close cannot turn consumed work into authority time.
        result = PrimaryCopy(window, primary, history_raw, crypto_raw, copy_raw, originals, preliminary_close, native_close)
        graphs = (N._history_graph(result.__dict__, primary.__dict__, originals),
            *(N._history_graph(wrapper.owner) for wrapper in attempt["owners"]))
        saved = (result, window, primary, history_raw, crypto_raw, copy_raw, originals,
            preliminary_close, native_close, tuple((wrapper, wrapper._anchor()) for wrapper in attempt["owners"]),
            graphs, actual, attempt, preliminary, preliminary_anchor, handoff_binding, handoff_graph)
        require(id(result) not in _PRIMARY_RETURNS, "PRIMARY_RETURN_REUSE")
        _PRIMARY_RETURNS[id(result)] = saved
        attempt["return"], attempt["state"] = result, "RETURNED"
        return result
    except BaseException as error:
        failure = active.remember(error) if active is not None else error
    finally:
        if failure is not None:
            for wrapper in reversed(attempt["owners"]):
                if not wrapper.finished and not wrapper.owner.unknown:
                    try:
                        wrapper.remember(failure)
                        wrapper.finish()
                    except BaseException:
                        pass  # The first error and the actual original ledgers remain retained.
            attempt["failure"], attempt["state"] = failure, "FAILED"
    raise failure


def checked_primary(result):
    """Authenticate this process's known-close return; do NOT observe/acquire time.

    Returns (same Window, original Primary, historical bytes, PRIMARY map bytes,
    immutable original history-file bytes). Later code must explicitly use that
    live Window/current acquisition. Merely parsing/copying these bytes cannot
    mint this return; this function intentionally grants no remote authority.
    """
    saved = _PRIMARY_RETURNS.get(id(result))
    require(type(result) is PrimaryCopy and type(saved) is tuple and saved[0] is result, "PRIMARY_NOT_ORIGINAL_RETURN")
    _, window, primary, history, crypto, copy, originals, preclose, close, owners, graphs, actual, attempt, \
        preliminary, preliminary_anchor, handoff_binding, handoff_graph = saved
    try:
        require(_PRIMARY_ATTEMPTS.get("fixed") is attempt and attempt["return"] is result and attempt["state"] == "RETURNED" and
            result.window is window and result.primary is primary and result.originals is originals and
            result.history == history and result.crypto_history == crypto and result.copy == copy and
            result.preliminary_close == preclose and result.native_close == close, "PRIMARY_RETURN_CHANGED")
        for graph in graphs:
            N._check_history(graph)
        for owner, original_anchor in owners:
            require(owner._anchor() is original_anchor, "PRIMARY_ORIGINAL_OWNER_ANCHOR")
            owner.structural()
            require(owner.finished and owner.failure is None and owner.owner.closed and not owner.owner.unknown and
                owner.owner.original is None and owner.errors == [] and
                all(attempted and closed for _, _, _, attempted, closed in owner.rows), "PRIMARY_CLOSE_CHANGED")
        preliminary.structural(preliminary_anchor)
        require(preliminary_anchor.closed and preliminary.failure is None, "PRIMARY_PRELIMINARY_CLOSE_CHANGED")
        N._check_history(handoff_graph)
        require(canonical(primary.handoff_raw)["directoryIdentity"] == list(handoff_binding[1]), "PRIMARY_HANDOFF_CHANGED")
        _actual_inputs(actual)
        require(window._view().failure is None and window._view().retired is None, "PRIMARY_WINDOW_FAILED_OR_RETIRED")
        return window, primary, history, copy, originals
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


# Confined authority owner; unchanged native file/process backends and Window.
_CUSTODY_OWNERS = {}


@dataclass(eq=False, repr=False)
class _CustodyOwnerAnchor:
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


class _CustodyOwner(native.Owner):
    """Actual custody-only Owner with original return/close observations.

    Shared native Owner file methods and original phase/source callers use these
    fixed acquisition/close seams. Nothing replaces a native resource backend or
    the first Window. A callback cannot create closure by editing ledger flags.
    """
    def __init__(self, local_end, fence=None, *, first=None, cancelled=lambda: None):
        require(type(self) is _CustodyOwner and id(self) not in _CUSTODY_OWNERS and
            type(fence) in (Window, _CustodyChildClock, _CollectClock, _TailClock, _BeforeClock, U.UseWindow) and first is not None,
            "AUTHORITY_OWNER_NEW")
        native.Owner.__init__(self, local_end, fence, first=first, cancelled=cancelled)
        self.initial_sources = {}
        binding = (self.first, self.fence, self.cancelled, self.local_end, self.resources,
            self.errors, self.initial_sources, self.admissions, self.early_last,
            self.entry_original, self.entry_close_attempted, self.entry_close_original, self.entry_close_snapshot)
        _CUSTODY_OWNERS[id(self)] = _CustodyOwnerAnchor(self, self.__dict__, binding,
            N._history_graph(first), error_graph=N._history_graph(self.errors))
        self.check()

    def _anchor(self):
        anchor = _CUSTODY_OWNERS.get(id(self))
        require(type(self) is _CustodyOwner and type(anchor) is _CustodyOwnerAnchor and anchor.owner is self,
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
            require(type(resources) is list and len(resources) == len(anchor.rows) <= MAX_MEMBERS and
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

    def enter_custody_phase(self, started, work_end, final_end):
        anchor = self.check()
        require(type(self.fence) is Window and anchor.phase is None and not anchor.closed and not anchor.unknown and
            anchor.failure is None and not anchor.busy and anchor.frozen is None and
            type(started) is int and type(work_end) is int and type(final_end) is int and
            started == self.fence.last and started < work_end and
            work_end == min(self.fence.work, started + 45 * O.NS) and
            final_end == min(self.fence.final, work_end + 45 * O.NS), "AUTHORITY_OWNER_ORIGINAL_PHASE")
        anchor.phase = (started, work_end, final_end, (self.work_limit, self.final_limit))
        anchor.phase_active = True
        self.work_limit, self.final_limit = work_end, final_end
        self.check()

    def leave_custody_phase(self, started, work_end, final_end, old_limits):
        anchor = self.check()
        require(anchor.phase_active and anchor.phase is not None and
            type(old_limits) is tuple and old_limits == (None, None) and
            (started, work_end, final_end, old_limits) == anchor.phase, "AUTHORITY_OWNER_PHASE_RETURN_CHANGED")
        self.work_limit, self.final_limit = old_limits
        anchor.phase_active = False  # Original phase tuple remains consumed forever.
        self.check()

    def enter_crypto_phase(self, context_raw, started, work_end, final_end):
        """One distinct token-free210 phase; never change authority45."""
        anchor = self.check()
        context = canonical(context_raw, 65536)
        require(context.get("scope") == _CRYPTO_CONTEXT_SCOPE and type(self.fence) is Window and
            anchor.phase is None and not anchor.closed and not anchor.unknown and anchor.failure is None and
            not anchor.busy and anchor.frozen is None and self.work_limit is None and self.final_limit is None and
            type(started) is int and type(work_end) is int and type(final_end) is int and
            started == self.fence.last and started < work_end and
            work_end == min(self.fence.work, started + 210 * O.NS) and
            final_end == min(self.fence.final, work_end + 45 * O.NS), "CRYPTO_OWNER_ORIGINAL_PHASE")
        _same(context["window"], canonical(_custody_authority_window(self.fence)), "CRYPTO_OWNER_WINDOW")
        anchor.phase = (started, work_end, final_end, (None, None))
        anchor.phase_active = True
        self.work_limit, self.final_limit = work_end, final_end
        self.check()

    def leave_crypto_phase(self, started, work_end, final_end):
        anchor = self.check()
        require(anchor.phase_active and anchor.phase == (started, work_end, final_end, (None, None)),
            "CRYPTO_OWNER_PHASE_RETURN_CHANGED")
        self.work_limit = self.final_limit = None
        anchor.phase_active = False
        self.check()

    def enter_collect_phase(self, context_raw, started, work_end, final_end):
        """Only the new post-export native phase, within its original READ end."""
        anchor = self.check()
        require(type(self.fence) is _CollectClock and self.fence.side == "parent" and
            anchor.phase is None and not anchor.closed and not anchor.unknown and anchor.failure is None and
            not anchor.busy and anchor.frozen is None and self.work_limit is None and self.final_limit is None and
            type(started) is int and type(work_end) is int and type(final_end) is int and
            started == self.fence.last and started < work_end and
            work_end == min(self.fence.work, started + 45 * O.NS) and
            final_end == min(self.fence.final, work_end + 45 * O.NS), "COLLECT_OWNER_ORIGINAL_PHASE")
        context = _collect_context(context_raw, self.fence.clock)
        require(context["continuationEndNs"] == self.fence.work == self.fence.final and
            context["originalWindow"] == self.fence.frame, "COLLECT_OWNER_ORIGINAL_WINDOW")
        anchor.phase = (started, work_end, final_end, (None, None))
        anchor.phase_active = True
        self.work_limit, self.final_limit = work_end, final_end
        self.check()

    def leave_collect_phase(self, started, work_end, final_end, old_limits):
        anchor = self.check()
        require(type(self.fence) is _CollectClock and anchor.phase_active and type(old_limits) is tuple and
            old_limits == (None, None) and anchor.phase == (started, work_end, final_end, old_limits),
            "COLLECT_OWNER_PHASE_RETURN_CHANGED")
        self.work_limit = self.final_limit = None
        anchor.phase_active = False
        self.check()


    def enter_tail_phase(self, context_raw, started, work_end, final_end):
        """One new seal-only episode, never an enlarged collect owner/window."""
        anchor = self.check()
        require(type(self.fence) is _TailClock and self.fence.side == "parent" and
            anchor.phase is None and not anchor.closed and not anchor.unknown and anchor.failure is None and
            not anchor.busy and anchor.frozen is None and self.work_limit is None and self.final_limit is None and
            type(started) is int and type(work_end) is int and type(final_end) is int and
            started == self.fence.last and started < work_end and
            work_end == min(self.fence.work, started + 45 * O.NS) and
            final_end == min(self.fence.final, work_end + 45 * O.NS), "TAIL_OWNER_ORIGINAL_PHASE")
        context = _tail_context(context_raw, self.fence.clock)
        require(context["continuationEndNs"] == self.fence.work == self.fence.final and
            context["originalWindow"] == self.fence.frame, "TAIL_OWNER_ORIGINAL_WINDOW")
        anchor.phase = (started, work_end, final_end, (None, None))
        anchor.phase_active = True
        self.work_limit, self.final_limit = work_end, final_end
        self.check()

    def leave_tail_phase(self, started, work_end, final_end, old_limits):
        anchor = self.check()
        require(type(self.fence) is _TailClock and anchor.phase_active and type(old_limits) is tuple and
            old_limits == (None, None) and anchor.phase == (started, work_end, final_end, old_limits),
            "TAIL_OWNER_PHASE_RETURN_CHANGED")
        self.work_limit = self.final_limit = None
        anchor.phase_active = False
        self.check()


    def enter_before_phase(self, context_raw, started, work_end, final_end):
        """Exactly one B-only phase; its seed already capped the FIRST reader."""
        anchor = self.check()
        require(type(self.fence) is _BeforeClock and self.fence.side == "parent" and
            anchor.phase is None and not anchor.closed and not anchor.unknown and anchor.failure is None and
            not anchor.busy and anchor.frozen is None and self.work_limit is None and self.final_limit is None and
            type(started) is int and started == self.fence.last, "BEFORE_OWNER_ORIGINAL_PHASE")
        context = _before_context(context_raw, self.fence.clock)
        B.phase_caps(context["deadline"], (started, work_end, final_end))
        _same(context["deadline"], self.fence.seed, "BEFORE_OWNER_SEED")
        _same(context["originalWindow"], self.fence.frame, "BEFORE_OWNER_WINDOW")
        require(context["continuationEndNs"] == self.fence.work == self.fence.final,
            "BEFORE_OWNER_ORIGINAL_END")
        anchor.phase = (started, work_end, final_end, (None, None))
        anchor.phase_active = True
        self.work_limit, self.final_limit = work_end, final_end
        self.check()

    def leave_before_phase(self, started, work_end, final_end, old_limits):
        anchor = self.check()
        require(type(self.fence) is _BeforeClock and anchor.phase_active and type(old_limits) is tuple and
            old_limits == (None, None) and anchor.phase == (started, work_end, final_end, old_limits),
            "BEFORE_OWNER_PHASE_RETURN_CHANGED")
        self.work_limit = self.final_limit = None
        anchor.phase_active = False
        self.check()

    def enter_productive_phase(self, context_raw, started, work_end, final_end):
        """One fresh per-use HTTP child, never a revived C prep/custody phase."""
        anchor = self.check()
        require(type(self.fence) is U.UseWindow and self.fence.side == "parent" and
            anchor.phase is None and not anchor.closed and not anchor.unknown and anchor.failure is None and
            not anchor.busy and anchor.frozen is None and self.work_limit is None and self.final_limit is None and
            type(started) is int and started == self.fence.last, "PRODUCTIVE_USE_OWNER_ORIGINAL_PHASE")
        context = canonical(context_raw)
        require(context["scope"] == U.site_scope(context["site"]) and
            O.encoded(context["window"]) == self.fence.raw, "PRODUCTIVE_USE_OWNER_CONTEXT")
        _clock, seed = U.checked_frame(context["window"])
        U.phase_caps(seed, (started, work_end, final_end))
        require((work_end, final_end) == (min(self.fence.work, started + 45 * O.NS),
            min(self.fence.final, work_end + 45 * O.NS)), "PRODUCTIVE_USE_OWNER_PHASE_CAPS")
        anchor.phase = (started, work_end, final_end, (None, None))
        anchor.phase_active = True
        self.work_limit, self.final_limit = work_end, final_end
        self.check()

    def leave_productive_phase(self, started, work_end, final_end, old_limits):
        anchor = self.check()
        require(type(self.fence) is U.UseWindow and anchor.phase_active and type(old_limits) is tuple and
            old_limits == (None, None) and anchor.phase == (started, work_end, final_end, old_limits),
            "PRODUCTIVE_USE_OWNER_PHASE_RETURN_CHANGED")
        self.work_limit = self.final_limit = None
        anchor.phase_active = False
        self.check()


def _custody_match_pin(match, kind):
    require(kind in ("gate", "worker") and type(match) is
        (A.gate.GateEligibility if kind == "gate" else A.stages.BootstrapMatch) and type(match.record) is bytes,
        "AUTHORITY_MATCH_TYPE")
    dictionary, raw = match.__dict__, match.record
    require(type(dictionary) is dict and set(dictionary) == {"record"}, "AUTHORITY_MATCH_FIELDS")
    return match, type(match), dictionary, raw, N._history_graph(dictionary)


def _custody_match_check(pin):
    require(type(pin) is tuple and len(pin) == 5, "AUTHORITY_MATCH_PIN")
    match, kind, dictionary, raw, graph = pin
    require(type(match) is kind and match.__dict__ is dictionary and type(match.record) is bytes and match.record == raw,
        "AUTHORITY_MATCH_CHANGED")
    N._check_history(graph)
    return match


# Fixed custody child guard. The maintained helper supplies immutable caps only;
# it never supplies a reconstructed current observation or original parent owner.
_CUSTODY_CHILD_CLOCKS = {}


@dataclass(eq=False, repr=False)
class _CustodyChildAnchor:
    handle: object
    binding: tuple
    first_graph: tuple
    cap: object
    cap_dictionary: dict
    cap_graph: tuple
    last: int
    local_last: float
    phase: str = "METADATA"
    metadata: object = None
    metadata_graph: tuple = ()
    frame: tuple = ()
    frame_graph: tuple = ()
    operative: object = None
    busy: bool = False
    failure: object = None


class _CustodyChildClock:
    """Actual child-first clocks; one metadata cap, one shortening, no renewal.

    _RecipientWindow remains unchanged. Its complete dictionary, including the
    construction-only `last`, is immutable here. Actual checked_now returns go
    straight into our independently retained frontier before any other callback.
    There is no call to the helper's now/deadline or adoption of its mutable last.
    """
    __slots__ = ("_binding",)

    def __init__(self, first, local, boot, cancelled):
        require(type(self) is _CustodyChildClock and id(self) not in _CUSTODY_CHILD_CLOCKS,
            "CHILD_CLOCK_NOT_NEW")
        first_graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        local_value(local)
        digest(boot)
        require(callable(cancelled), "CHILD_CLOCK_CALLBACK")
        cap = native._RecipientWindow(first, first.nanoseconds, local, None, cancelled, metadata=True)
        self._binding = (first, local, boot, cancelled)
        anchor = _CustodyChildAnchor(self, self._binding, first_graph, cap, cap.__dict__,
            N._history_graph(cap.__dict__), first.nanoseconds, local)
        _CUSTODY_CHILD_CLOCKS[id(self)] = anchor
        self._current(anchor)

    def _anchor(self):
        anchor = _CUSTODY_CHILD_CLOCKS.get(id(self))
        require(type(self) is _CustodyChildClock and type(anchor) is _CustodyChildAnchor and
            anchor.handle is self, "CHILD_CLOCK_ORIGINAL_HANDLE")
        return anchor

    @staticmethod
    def _error(anchor, error):
        if anchor.failure is None:
            anchor.failure = error
        return anchor.failure

    def _current(self, anchor):
        require(_CUSTODY_CHILD_CLOCKS.get(id(self)) is anchor and self._binding is anchor.binding and
            anchor.handle is self and type(anchor.cap) is native._RecipientWindow and
            anchor.cap.__dict__ is anchor.cap_dictionary, "CHILD_CLOCK_ORIGINAL_BINDING")
        N._check_history(anchor.first_graph)
        N._check_history(anchor.cap_graph)
        if anchor.metadata is not None:
            anchor.metadata.structural()
        N._check_history(anchor.metadata_graph)
        N._check_history(anchor.frame_graph)
        if anchor.frame:
            require(anchor.frame[4].__dict__ is anchor.frame[5] and
                type(anchor.frame[-3]) is native._RecipientWindow and
                anchor.frame[-3].__dict__ is anchor.frame[-2], "CHILD_CLOCK_RETAINED_FRAME_CHANGED")
        if anchor.operative is not None:
            require(type(anchor.operative) is _CustodyOwner, "CHILD_CLOCK_ORIGINAL_OWNER")
            anchor.operative.check()

    def _view(self):
        anchor = self._anchor()
        try:
            self._current(anchor)
            return anchor
        except BaseException as error:
            raise self._error(anchor, error)

    clock = property(lambda self: self._view().binding[0].clock)
    first = property(lambda self: self._view().binding[0].nanoseconds)
    work = property(lambda self: self._view().cap.work)
    final = property(lambda self: self._view().cap.final)
    local_end = property(lambda self: self._view().cap.local_end)
    last = property(lambda self: self._view().last)

    def _begin(self):
        anchor = self._anchor()
        if anchor.failure is not None:
            raise anchor.failure
        try:
            self._current(anchor)
            require(not anchor.busy, "CHILD_CLOCK_REENTRY")
            anchor.busy = True
            return anchor
        except BaseException as error:
            raise self._error(anchor, error)

    def _local(self, anchor):
        value = local_value(time.monotonic())
        require(value >= anchor.local_last, "CHILD_CLOCK_LOCAL_BACKWARDS")
        anchor.local_last = value
        self._current(anchor)
        require(value < anchor.cap.local_end, "CHILD_CLOCK_LOCAL_EXPIRED")
        return value

    def _observe(self, anchor, *, final, minimum, limit):
        require(type(final) is bool, "CHILD_CLOCK_FINAL_TYPE")
        end = anchor.cap.final if final else anchor.cap.work
        if limit is not None:
            end = min(end, O.integer(limit))
        frontier = max(anchor.last, O.integer(minimum))
        for number in range(2):
            self._current(anchor)  # Pin newly returned native rows BEFORE any clock callback.
            local = self._local(anchor)
            observed = O.clocks.checked_now(anchor.binding[0].clock, minimum_ns=frontier)
            anchor.last = frontier = O.integer(observed, frontier)
            self._current(anchor)
            require(frontier < end and anchor.busy and anchor.failure is None, "CHILD_CLOCK_RAW_EXPIRED_OR_CHANGED")
            # Both sides of cancellation are observed. An unchanged ClockIdentity
            # cannot stand in for the live boot after the callback/second RAW.
            boot = C.boot_digest(anchor.binding[0].clock.role)
            self._current(anchor)
            require(type(boot) is str and boot == anchor.binding[2], "CHILD_CLOCK_BOOT_CHANGED")
            if number == 0:
                anchor.binding[3]()
                self._current(anchor)
                require(anchor.last == frontier and anchor.local_last == local and anchor.busy and
                    anchor.failure is None, "CHILD_CLOCK_CALLBACK_CHANGED")
        self._local(anchor)
        self._current(anchor)
        require(anchor.last == frontier and anchor.busy and anchor.failure is None, "CHILD_CLOCK_FRONTIER_CHANGED")
        return frontier

    def now(self, *, final=False, minimum=0, limit=None):
        anchor = self._begin()
        try:
            return self._observe(anchor, final=final, minimum=minimum, limit=limit)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def deadline(self, maximum, *, final=False, limit=None):
        anchor = self._begin()
        try:
            require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 210,
                "CHILD_CLOCK_OPERATION_MAXIMUM")
            local = self._local(anchor)
            observed = self._observe(anchor, final=final, minimum=0, limit=limit)
            end = anchor.cap.final if final else anchor.cap.work
            if limit is not None:
                end = min(end, O.integer(limit))
            result = min(anchor.cap.local_end, O.wire._directed_deadline(local, maximum, end, observed))
            self._current(anchor)
            require(anchor.busy and anchor.failure is None, "CHILD_CLOCK_DEADLINE_CHANGED")
            return result
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def attach_metadata(self, wrapper):
        anchor = self._begin()
        try:
            require(anchor.phase == "METADATA" and anchor.metadata is None and type(wrapper) is _PrimaryOwner and
                wrapper.owner.first is anchor.binding[0] and wrapper.owner.fence is self and
                not wrapper.finished and not wrapper.rows, "CHILD_METADATA_ORIGINAL_OWNER")
            anchor.metadata = wrapper
            self._current(anchor)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def bind(self, context_raw, context, start_raw, start, expected, event, inherited):
        anchor = self._begin()
        try:
            require(anchor.phase == "METADATA" and anchor.metadata is not None, "CHILD_CLOCK_BIND_ONCE")
            anchor.phase = "BINDING"  # Any failure consumes the one transition.
            metadata = anchor.metadata
            metadata.structural()
            require(metadata.finished and metadata.failure is None and metadata.owner.closed is True and
                metadata.owner.original is None and metadata.owner.unknown is False and metadata.errors == [] and
                all(attempted and closed for _, _, _, attempted, closed in metadata.rows), "CHILD_METADATA_CLOSE_UNKNOWN")
            require(type(context_raw) is bytes and type(start_raw) is bytes and type(event) is bytes and
                canonical(context_raw) == context and canonical(start_raw) == start and
                type(context) is dict and type(start) is dict and type(inherited) is dict,
                "CHILD_FRAME_ORIGINAL_BYTES")
            kind = context["observed"]["kind"]
            require(kind in ("gate", "worker") and type(expected) is
                (A.gate.GateEligibility if kind == "gate" else A.stages.BootstrapMatch) and
                type(expected.record) is bytes and expected.record == O.encoded(context["expectedMatch"]),
                "CHILD_FRAME_EXPECTED_MATCH")
            frame = context["window"]
            require(frame["originalBootDigest"] == anchor.binding[2] and frame["clock"] == O.clock_value(anchor.binding[0].clock) and
                start["startedNs"] <= anchor.binding[0].nanoseconds and
                start["workEndNs"] == min(frame["workEndNs"], O.integer(start["startedNs"]) + 45 * O.NS) and
                anchor.last < O.integer(start["workEndNs"]), "CHILD_FRAME_ORIGINAL_CAP")
            anchor.metadata_graph = N._history_graph(metadata.owner)
            anchor.frame = (context_raw, context, start_raw, start, expected, expected.__dict__, event, inherited,
                anchor.cap, anchor.cap_dictionary, anchor.cap_graph)
            anchor.frame_graph = N._history_graph(anchor.frame)
            # Same ACTUAL first/LOCAL and metadata frontier; no helper observation
            # is restored or reused. The validated parent45 can only shorten it.
            cap = native._RecipientWindow(anchor.binding[0], anchor.last, anchor.binding[1],
                start["workEndNs"], anchor.binding[3])
            anchor.cap, anchor.cap_dictionary = cap, cap.__dict__
            anchor.cap_graph = N._history_graph(cap.__dict__)
            anchor.phase = "OPERATIVE"
            self._current(anchor)
            self._observe(anchor, final=False, minimum=anchor.last, limit=start["workEndNs"])
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def attach_operative(self, owner):
        anchor = self._begin()
        try:
            require(anchor.phase == "OPERATIVE" and anchor.operative is None and type(owner) is _CustodyOwner and
                owner.fence is self and owner.first is anchor.binding[0] and not owner.closed and
                not owner.check().rows and owner._anchor().pending is None,
                "CHILD_OPERATIVE_ORIGINAL_OWNER")
            anchor.operative = owner
            self._current(anchor)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def bind_crypto(self, context_raw, context, start_raw, start, expected, event, inherited):
        """One original metadata-to-crypto transition, not an authority45 knob."""
        anchor = self._begin()
        try:
            require(anchor.phase == "METADATA" and anchor.metadata is not None, "CHILD_CLOCK_BIND_ONCE")
            anchor.phase = "BINDING"
            metadata = anchor.metadata
            metadata.structural()
            require(metadata.finished and metadata.failure is None and metadata.owner.closed is True and
                metadata.owner.original is None and metadata.owner.unknown is False and metadata.errors == [] and
                all(attempted and closed for _, _, _, attempted, closed in metadata.rows), "CHILD_METADATA_CLOSE_UNKNOWN")
            require(type(context_raw) is bytes and type(start_raw) is bytes and type(event) is bytes and
                canonical(context_raw, 65536) == context and canonical(start_raw) == start and
                type(context) is dict and type(start) is dict and type(inherited) is dict,
                "CHILD_FRAME_ORIGINAL_BYTES")
            kind = context["kind"]
            require(type(expected) is (A.gate.GateEligibility if kind == "gate" else A.stages.BootstrapMatch) and
                type(expected.record) is bytes and O.digest(expected.record) == context["filesSha256"]["fresh-match.json"],
                "CRYPTO_CHILD_EXPECTED_MATCH")
            # Retain the original frame BEFORE host/ownership suppliers run.
            # A callback cannot replace an already validated shorter parent end.
            anchor.metadata_graph = N._history_graph(metadata.owner)
            anchor.frame = (context_raw, context, start_raw, start, expected, expected.__dict__, event, inherited,
                anchor.cap, anchor.cap_dictionary, anchor.cap_graph)
            anchor.frame_graph = N._history_graph(anchor.frame)
            _crypto_start(context_raw, context, start, anchor.binding[0], anchor.binding[2], event, inherited)
            self._current(anchor)
            require(anchor.last < start["workEndNs"], "CRYPTO_CHILD_ORIGINAL_CAP")
            cap = native._RecipientWindow(anchor.binding[0], anchor.last, anchor.binding[1],
                start["workEndNs"], anchor.binding[3])
            anchor.cap, anchor.cap_dictionary = cap, cap.__dict__
            anchor.cap_graph = N._history_graph(cap.__dict__)
            anchor.phase = "OPERATIVE"
            self._current(anchor)
            self._observe(anchor, final=False, minimum=anchor.last, limit=start["workEndNs"])
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False


# Fixed authority-1 child, not a standalone acquisition/provider or a new budget.
_AUTHORITY_CHILD_SCOPE = "INITIAL_CUSTODY_AUTHORITY_PENDING_CHILD_CLOSE_V1"
_AUTHORITY_CONTEXT_FIELDS = "schema scope window history observed expectedMatch eventSha256 root session job " \
    "inheritedContext sourceReturnSha256 sourceReturnedNs primaryResultSha256 primaryCopySha256 " \
    "directoryIdentity budgetAcceptance exportSaveAuthority"
_AUTHORITY_HISTORY_FIELDS = "schema scope kind observed clock originalBootDigest originalPreviousNs originalJobBasisNs " \
    "serviceArithmetic serviceJob firstUseAt matchSha256 originalLocalScope primaryStepScope currentAuthority " \
    "budgetAcceptance exportSaveAuthority"


def _custody_authority_frame(value):
    """Closed parent data, never a reconstructed live custody Window."""
    fields(value, "schema scope clock originalBootDigest kind originalJobBasisNs jobEndNs startNs " +
        " ".join(WINDOW_NAMES), "AUTHORITY_WINDOW_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == WINDOW_SCOPE,
        "AUTHORITY_WINDOW_SCOPE")
    clock = O.wire.clock_identity(value["clock"])
    digest(value["originalBootDigest"])
    limits = schedule(value["kind"], value["originalJobBasisNs"], value["startNs"])
    _same({name: value[name] for name in limits}, limits, "AUTHORITY_WINDOW_ARITHMETIC")
    return clock, limits


def _custody_authority_context(raw, path, first, boot):
    """Actual host/event binding inside the genuinely owned fixed HTTP child."""
    context = fields(canonical(raw), _AUTHORITY_CONTEXT_FIELDS, "AUTHORITY_CONTEXT_FIELDS")
    frame_clock, limits = _custody_authority_frame(context["window"])
    history = fields(context["history"], _AUTHORITY_HISTORY_FIELDS, "AUTHORITY_HISTORY_FIELDS")
    require(type(context["schema"]) is int and context["schema"] == 1 and
        context["scope"] == native.INITIAL_CUSTODY_AUTHORITY_CONTEXT_SCOPE and
        context["root"] == str(ROOT) and context["session"] == str(path) and
        context["budgetAcceptance"] == "NOT_ADMITTED" and context["exportSaveAuthority"] is False and
        type(history["schema"]) is int and history["schema"] == 1 and
        history["scope"] == "INITIAL_CUSTODY_PRIMARY_HISTORICAL_BINDING_V1" and
        history["kind"] == limits["kind"] and history["observed"] == context["observed"] and
        history["clock"] == context["window"]["clock"] and frame_clock == first.clock and
        history["originalBootDigest"] == context["window"]["originalBootDigest"] == boot and
        history["originalJobBasisNs"] == limits["originalJobBasisNs"] and
        O.integer(history["originalPreviousNs"]) <= limits["startNs"] <= first.nanoseconds < limits["workEndNs"] and
        history["budgetAcceptance"] == "NOT_ADMITTED" and history["exportSaveAuthority"] is False and
        history["currentAuthority"] == "NOT_ACQUIRED", "AUTHORITY_CONTEXT_BINDINGS")
    first_use = O.integer(history["firstUseAt"], 1)
    kind = history["kind"]
    observed, primary_path, event = N.host_context(first_use)
    roots, _handoff, custody_path = _paths(kind)
    require(primary_path == roots["P"] and path == custody_path / "authority-1" and
        observed == context["observed"] and observed["role"] == first.clock.role and
        observed["kind"] == kind and observed["firstUseAt"] == first_use and
        context["eventSha256"] == O.digest(event), "AUTHORITY_ACTUAL_CONTEXT")
    for name in ("sourceReturnSha256", "primaryResultSha256", "primaryCopySha256"):
        digest(context[name])
    require(type(context["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", context["job"]) and
        limits["startNs"] <= O.integer(context["sourceReturnedNs"]) < limits["workEndNs"],
        "AUTHORITY_SOURCE_TIME")
    inherited = context["inheritedContext"]
    require(type(inherited) is dict and all(type(item) is str for item in inherited.values()) and
        (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)),
        "AUTHORITY_PARENT_DOMAIN")
    native.directory_identity(context["directoryIdentity"], first.clock.role)
    expected_raw = O.encoded(context["expectedMatch"])
    require(O.digest(expected_raw) == digest(history["matchSha256"]) and
        context["expectedMatch"]["firstUseAt"] == first_use, "AUTHORITY_EXPECTED_HISTORY")
    # A supplied historical value is not current authority. The actual acquirer
    # must revalidate this exact expected record against fresh original responses.
    expected = (A.gate.GateEligibility if kind == "gate" else A.stages.BootstrapMatch)(expected_raw)
    return context, expected, event


def _custody_authority_start(raw, context_raw, context, path, first, minimum, inherited):
    start = _custody_authority_start_fields(raw, context_raw, context, path, first.clock)
    require(start["startedNs"] <= O.integer(minimum) <= first.nanoseconds < start["workEndNs"],
        "AUTHORITY_ORIGINAL_PHASE")
    require(type(inherited) is dict and set(inherited) == set(Q._CONTEXT) and
        inherited == start["inheritedContext"],
        "AUTHORITY_NATIVE_INHERITANCE")
    domain = native.processes.ownership_domains(inherited[native.processes.CHAIN_ENV],
        inherited[native.processes.DOMAINS_ENV])[-1]
    require(domain == {"id": start["invocation"], "job": start["job"], "state": start["state"],
        "home": start["home"]}, "AUTHORITY_NATIVE_DOMAIN")
    return start, domain


def _custody_finish_queries(owner, supplier, failure):
    """Exactly one actual finalizer; preserve even a falsey original failure."""
    if supplier is not None:
        try:
            supplier._finalize(failure)
        except BaseException as error:
            if failure is None:
                failure = error
    if (supplier is not None and supplier.unknown) or Q.QUARANTINE or native.diagnostics._QUARANTINE:
        if failure is None:
            failure = O.OriginError("INITIAL_CUSTODY_AUTHORITY_QUERY_UNKNOWN")
        owner.error("custody-authority-query", failure, unknown=True)
    if failure is not None:
        raise failure


def custody_authority_child(context_hash, minimum, cancelled):
    """One real authority-1 child under the parent's already-owned native domain.

    No CLI dispatch is installed by this fragment. Metadata and acquisition use
    two NEW actual Owners, with known metadata close before the sole cap bind.
    The first LOCAL/RAW/boot never restart; the parent phase45 can only shorten.
    """
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    metadata = owner = clock = result_raw = None
    failure = None
    try:
        local = local_value(time.monotonic())  # Before first RAW, including all metadata work.
        first = O.clocks.observe()
        first_graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        require(first.nanoseconds >= O.integer(minimum), "AUTHORITY_CHILD_PRECEDES_LAUNCH")
        boot = digest(C.boot_digest(first.clock.role))
        N._check_history(first_graph)
        digest(context_hash)
        require(callable(cancelled) and type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and
            not any(name in os.environ for name in _CREDENTIAL_NAMES), "AUTHORITY_CHILD_CREDENTIAL_BOUNDARY")
        clock = _CustodyChildClock(first, local, boot, cancelled)
        metadata_owner = native.Owner(clock.local_end, clock, first=first, cancelled=cancelled)
        metadata = _PrimaryOwner(metadata_owner)
        clock.attach_metadata(metadata)
        kind, _primary_path = N.location()
        path = _paths(kind)[2] / "authority-1"
        private = _private(metadata, path)
        private_pin = tuple(private.identity)
        context_raw = _read_private(metadata, private, "context.json", native.LIMIT)
        require(O.digest(context_raw) == context_hash, "AUTHORITY_CHILD_CONTEXT_HASH")
        context, expected, event = _custody_authority_context(context_raw, path, first, boot)
        expected_pin = _custody_match_pin(expected, kind)
        require(tuple(context["directoryIdentity"]) == private_pin, "AUTHORITY_CHILD_PARENT_PIN")
        service = _private(metadata, path / "service")
        service_pin = tuple(service.identity)
        start_raw = _read_private(metadata, service, "start.json", native.LIMIT)
        inherited = Q._inherited_context()
        start, domain = _custody_authority_start(start_raw, context_raw, context, path, first, minimum, inherited)
        metadata_graph = N._history_graph(context, start, expected.__dict__, inherited, first)
        metadata_close = metadata.finish()
        metadata_last = clock.now()
        N._check_history(metadata_graph)
        _custody_match_check(expected_pin)
        clock.bind(context_raw, context, start_raw, start, expected, event, inherited)
        # These directories are reopened by a NEW Owner only after metadata's
        # actual known close. No retired handle or observed LOCAL is restored.
        owner = _CustodyOwner(clock.local_end, clock, first=first, cancelled=cancelled)
        clock.attach_operative(owner)
        private = owner.open(path)
        require(tuple(private.identity) == private_pin and owner.read(private, "context.json") == context_raw,
            "AUTHORITY_CHILD_ORIGINAL_CONTEXT")
        service = owner.child(private, "service")
        require(tuple(service.identity) == service_pin and owner.read(service, "start.json") == start_raw,
            "AUTHORITY_CHILD_ORIGINAL_START")
        supplier = None
        query_failure = None
        try:
            supplier = N.query_owner(owner, clock, path / "acquisition-queries")
            N._initial_service_query_git(supplier)
            supplier.native_host_matches_actions()
            def retain(name, raw, *, failed):
                require(name in N.ORIGINAL_KEYS and type(raw) is bytes and type(failed) is bool,
                    "AUTHORITY_CHILD_ORIGINAL_NAME")
                owner.end(final=failed)
                supplier._write(supplier.private, name + ".bin", raw)
                owner.end(final=failed)
            match, originals = A.acquire_bootstrap(ROOT, kind=kind, query_runner=supplier, invocation=domain["id"],
                token=token, retain=retain, fence=clock, original_work_end=start["workEndNs"],
                first_use_at=context["observed"]["firstUseAt"], expected=expected)
            token = None
            match_pin = _custody_match_pin(match, kind)
            original_graph = N._history_graph(match.__dict__, originals)
            acquired = clock.now(limit=start["workEndNs"])
            _custody_match_check(expected_pin)
            _custody_match_check(match_pin)
            require(type(match) is type(expected) and match.record == expected.record and
                type(originals) is tuple and tuple(name for name, _raw in originals) == N.ORIGINAL_KEYS and
                all(type(raw) is bytes for _name, raw in originals) and dict(originals)["event"] == event,
                "AUTHORITY_CHILD_ORIGINAL_MATCH")
        except BaseException as error:
            query_failure = error
        finally:
            token = None
            _custody_finish_queries(owner, supplier, query_failure)
        # No provisional session or caught finalizer error can cross this edge.
        returned = clock.now(limit=start["workEndNs"])
        N._check_history(original_graph)
        _custody_match_check(match_pin)
        queries = owner.open(path / "acquisition-queries")
        session = N.query_session(owner, queries)
        require(all(owner.read(queries, name + ".bin") == raw for name, raw in originals),
            "AUTHORITY_CHILD_ORIGINAL_READBACK")
        N._check_history(metadata_graph)
        _custody_match_check(expected_pin)
        result_raw = owner.write(service, "child-result.json", {"schema": 1, "scope": _AUTHORITY_CHILD_SCOPE,
            "contextSha256": context_hash, "startSha256": O.digest(start_raw), "invocation": domain["id"],
            "clock": O.clock_value(first.clock), "bootDigest": boot, "launchMinimumNs": minimum,
            "beganNs": first.nanoseconds, "metadataLastNs": metadata_last, "acquiredNs": acquired,
            "queryReturnedNs": returned, "querySessionSha256": O.digest(session),
            "originalsSha256": {name: O.digest(raw) for name, raw in originals}, "matchSha256": O.digest(match.record),
            "directoryIdentities": {".": list(private_pin), "service": list(service_pin)},
            "metadataClose": canonical(metadata_close),
            "completedNs": clock.now(limit=start["workEndNs"]), "retirement": "KNOWN", "errors": []})
        N._check_history(original_graph)
        _custody_match_check(match_pin)
        clock.now()
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("custody-authority-child", error)
            failure = owner._anchor().failure
        elif metadata is not None:
            failure = metadata.remember(error)
    finally:
        token = None
        if metadata is not None and not metadata.finished:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
        if owner is not None:
            if failure is None and owner._anchor().failure is None:
                try:
                    owner.freeze()
                except BaseException as error:
                    owner.error("custody-authority-close-roster", error, unknown=True)
            try:
                owner.close()
            except BaseException as error:
                owner.error("custody-authority-owner-close", error)
            if failure is None and owner._anchor().failure is not None:
                failure = owner._anchor().failure
            if failure is None:
                try:
                    owner.known()
                except BaseException as error:
                    owner.error("custody-authority-close-return", error, unknown=True)
                    failure = owner._anchor().failure
    if failure is not None:
        raise failure
    require(owner is not None and clock is not None and result_raw is not None and not owner.unknown,
        "AUTHORITY_CHILD_NO_ORIGINALS")
    N._check_history(metadata_graph)
    N._check_history(original_graph)
    closed = clock.now(limit=start["workEndNs"])
    _custody_match_check(expected_pin)
    _custody_match_check(match_pin)
    owner.known()
    return {"schema": 1, "scope": native.INITIAL_CUSTODY_AUTHORITY_ACK_SCOPE, "invocation": domain["id"],
        "terminalSha256": O.digest(result_raw), "clock": O.clock_value(first.clock), "closedNs": closed}, \
        clock, start["workEndNs"]


# Fixed pre-export authority-1 parent. Source draft: no CLI/workflow integration.
_AUTHORITY_RETURNS = {}
_AUTHORITY_ATTEMPTS = {}
_AUTHORITY_INDEX_SCOPE = "INITIAL_CUSTODY_AUTHORITY_PRE_EXPORT_INDEX_V1"
_AUTHORITY_PENDING_SCOPE = "INITIAL_CUSTODY_AUTHORITY_PRE_EXPORT_PENDING_CLOSE_V1"
_AUTHORITY_RETURN_SCOPE = "INITIAL_CUSTODY_AUTHORITY_PRE_EXPORT_CLOSED_HISTORY_V1"


def _custody_authority_window(window):
    """Encode the ORIGINAL live Window; these bytes never reconstruct it."""
    require(type(window) is Window, "AUTHORITY_ORIGINAL_WINDOW")
    anchor = window._view()
    require(anchor.failure is None, "AUTHORITY_FAILED_WINDOW")
    first, _local, boot, limits_raw, _ends, _locals, _cancel = anchor.binding
    raw = O.encoded({"schema": 1, "scope": WINDOW_SCOPE, "clock": O.clock_value(first.clock),
        "originalBootDigest": boot, **canonical(limits_raw)})
    _custody_authority_frame(canonical(raw))
    return raw


def _custody_authority_start_fields(raw, context_raw, context, path, clock):
    """Pure original-phase schema; no synthesized Reading or live native owner."""
    start = fields(canonical(raw), " ".join(native.START_FIELDS), "AUTHORITY_START_FIELDS")
    require(type(start["schema"]) is int and start["schema"] == 1 and start["scope"] == native.PHASE_SCOPE and
        start["contextSha256"] == O.digest(context_raw) and start["argv"] == native.phase_command(context_raw) and
        start["cwd"] == str(ROOT) and start["role"] == clock.role and start["job"] == context["job"] and
        start["state"] == str(path) and start["home"] == str(path / "control-home") and
        type(start["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", start["invocation"]) and
        start["exitCode"] is None and start["launchAttempted"] is False and start["scopeAttempted"] is False and
        start["retirement"] == "UNKNOWN", "AUTHORITY_START")
    frame = context["window"]
    began = O.integer(start["startedNs"], O.integer(context["sourceReturnedNs"]))
    require(began < O.integer(start["workEndNs"]) and
        start["workEndNs"] == min(frame["workEndNs"], began + 45 * O.NS) and
        start["finalEndNs"] == min(frame["nativeFinalEndNs"], start["workEndNs"] + 45 * O.NS),
        "AUTHORITY_ORIGINAL_PHASE")
    expected = native.processes.ownership_environment(context["inheritedContext"], context["job"],
        start["invocation"], str(path), str(path / "control-home"), allow_new_context=True)
    require(type(start["inheritedContext"]) is dict and
        start["inheritedContext"] == {name: expected[name] for name in Q._CONTEXT}, "AUTHORITY_START_INHERITANCE")
    return start


def _custody_authority_phase_bytes(context_raw, path, clock, records, child_raw, private_pin, service_pin):
    """Maintain the native phase/ACK/close predicates without old-window adoption."""
    return _initial_authority_phase_bytes(context_raw, path, clock, records, child_raw, private_pin, service_pin,
        native.INITIAL_CUSTODY_AUTHORITY_CONTEXT_SCOPE)


def productive_use_phase_bytes(context_raw, path, clock, records, child_raw, private_pin, service_pin):
    """Distinct per-use route over the SAME native return/close predicates."""
    context = canonical(context_raw)
    scope = U.site_scope(context["site"])
    require(context["scope"] == scope, "PRODUCTIVE_USE_PHASE_SCOPE")
    return _initial_authority_phase_bytes(context_raw, path, clock, records, child_raw, private_pin, service_pin, scope)


def productive_use_start_fields(raw, context_raw, context, path, clock):
    start = fields(canonical(raw), " ".join(native.START_FIELDS), "PRODUCTIVE_USE_START_FIELDS")
    frame_clock, seed = U.checked_frame(context["window"])
    caps = tuple(start[name] for name in U.PHASE_NAMES)
    U.phase_caps(seed, caps)
    require(frame_clock == clock and context["scope"] == U.site_scope(context["site"]) and
        context["site"] == seed["site"] and type(start["schema"]) is int and start["schema"] == 1 and
        start["scope"] == native.PHASE_SCOPE and start["contextSha256"] == O.digest(context_raw) and
        start["argv"] == native.phase_command(context_raw, use_caps=caps) and start["cwd"] == str(ROOT) and
        start["role"] == clock.role and start["job"] == context["job"] and start["state"] == str(path) and
        start["home"] == str(path / "control-home") and type(start["invocation"]) is str and
        re.fullmatch(r"[0-9a-f]{32}", start["invocation"]) and start["exitCode"] is None and
        start["launchAttempted"] is False and start["scopeAttempted"] is False and start["retirement"] == "UNKNOWN" and
        seed["firstNs"] <= O.integer(context["sourceReturnedNs"]) <= caps[0], "PRODUCTIVE_USE_START_BINDING")
    inherited = native.processes.ownership_environment(context["inheritedContext"], context["job"], start["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    _same(start["inheritedContext"], {name: inherited[name] for name in Q._CONTEXT}, "PRODUCTIVE_USE_START_INHERITANCE")
    return start


def _initial_authority_phase_bytes(context_raw, path, clock, records, child_raw, private_pin, service_pin, scope):
    require(scope in (native.INITIAL_CUSTODY_AUTHORITY_CONTEXT_SCOPE, U.PRIVATE_CONTEXT, U.PUBLIC_CONTEXT),
        "AUTHORITY_PHASE_FIXED_SCOPE")
    require(type(records) is dict and set(records) == native.PHASE_FILES and
        all(type(raw) is bytes for raw in records.values()), "AUTHORITY_PHASE_FILES")
    context = canonical(context_raw)
    require(context["scope"] == scope, "AUTHORITY_PHASE_CONTEXT_SCOPE")
    use = scope != native.INITIAL_CUSTODY_AUTHORITY_CONTEXT_SCOPE
    start = (productive_use_start_fields if use else _custody_authority_start_fields)(
        records["start.json"], context_raw, context, path, clock)
    row = fields(canonical(records["result.json"]), " ".join(native.TERMINAL_FIELDS), "AUTHORITY_TERMINAL_FIELDS")
    birth = fields(canonical(records["native-start.json"]), "ownership leader preparerIdentity observedNs",
        "AUTHORITY_BIRTH_FIELDS")
    changed = {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}
    _same({name: row[name] for name in start if name not in changed},
        {name: start[name] for name in start if name not in changed}, "AUTHORITY_TERMINAL_START")
    require(type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is True and
        row["scopeAttempted"] is True and row["scopeCloseAttempted"] is True and row["scopeClosed"] is True and
        row["retirement"] == "KNOWN" and row["survivors"] == [] and row["errors"] == [] and records["stderr.log"] == b"" and
        row["nativeStartSha256"] == O.digest(records["native-start.json"]) and
        row["baselineSha256"] == O.digest(records["baseline.json"]) and row["leader"] == birth["leader"],
        "AUTHORITY_NATIVE_RETURN")
    argv = (native.phase_command(context_raw, O.integer(row["launchMinimumNs"], start["startedNs"]),
        use_caps=tuple(start[name] for name in U.PHASE_NAMES)) if use else
        native.phase_command(context_raw, O.integer(row["launchMinimumNs"], start["startedNs"])))
    _same(row["launchArgv"], argv, "AUTHORITY_EXECUTED_COMMAND")
    native.native_record(row["ownership"], start, row["leader"], argv)
    native.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    _same(birth["ownership"]["launches"], row["ownership"]["launches"], "AUTHORITY_NATIVE_BIRTH")
    preparer = native.closed_lifetime(row["preparerIdentity"], clock.role)
    require(preparer == native.closed_lifetime(birth["preparerIdentity"], clock.role) and
        preparer["pid"] != row["leader"]["pid"], "AUTHORITY_PREPARER")
    baseline = native.baseline_record(records["baseline.json"], clock.role)
    if baseline["baseline"] is not None:
        leader = native.lifetime(row["leader"], clock.role)
        require(list(leader[:4] if clock.role.startswith("macos-") else leader) not in baseline["baseline"],
            "AUTHORITY_PREEXISTING_LEADER")
    _same(row["captureOutcomes"], {name: {key: True for key in
        ("synced", "verified", "closeAttempted", "closed", "readback")} for name in ("stdout", "stderr")},
        "AUTHORITY_CAPTURE_CLOSE")
    _same(row["captures"], {name: {"sha256": O.digest(records[name + ".log"]),
        "bytes": len(records[name + ".log"])} for name in ("stdout", "stderr")}, "AUTHORITY_CAPTURE_BYTES")
    child = fields(canonical(child_raw), "schema scope contextSha256 startSha256 invocation clock bootDigest "
        "launchMinimumNs beganNs metadataLastNs acquiredNs queryReturnedNs querySessionSha256 originalsSha256 "
        "matchSha256 directoryIdentities metadataClose completedNs retirement errors", "AUTHORITY_CHILD_FIELDS")
    ack = fields(canonical(records["stdout.log"]), "schema scope invocation terminalSha256 clock closedNs",
        "AUTHORITY_ACK_FIELDS")
    child_scope = U.PUBLIC_CHILD if scope == U.PUBLIC_CONTEXT else U.PRIVATE_CHILD if use else _AUTHORITY_CHILD_SCOPE
    ack_scope = U.PUBLIC_ACK if scope == U.PUBLIC_CONTEXT else U.PRIVATE_ACK if use else native.INITIAL_CUSTODY_AUTHORITY_ACK_SCOPE
    require(type(child["schema"]) is int and child["schema"] == 1 and child["scope"] == child_scope and
        child["contextSha256"] == O.digest(context_raw) and child["startSha256"] == O.digest(records["start.json"]) and
        child["invocation"] == start["invocation"] and child["clock"] == O.clock_value(clock) and
        child["bootDigest"] == context["window"]["originalBootDigest"] and
        child["launchMinimumNs"] == row["launchMinimumNs"] and child["retirement"] == "KNOWN" and child["errors"] == [] and
        type(ack["schema"]) is int and ack["schema"] == 1 and
        ack["scope"] == ack_scope and ack["invocation"] == start["invocation"] and
        ack["terminalSha256"] == O.digest(child_raw) and ack["clock"] == O.clock_value(clock),
        "AUTHORITY_CHILD_ACK")
    _same(child["directoryIdentities"], {".": list(private_pin), "service": list(service_pin)},
        "AUTHORITY_CHILD_DIRECTORY_PINS")
    closed = fields(child["metadataClose"], "schema scope resources retirement exportSaveAuthority",
        "AUTHORITY_METADATA_CLOSE_FIELDS")
    require(type(closed["schema"]) is int and closed["schema"] == 1 and
        closed["scope"] == "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1" and
        closed["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and closed["exportSaveAuthority"] is False,
        "AUTHORITY_METADATA_CLOSE")
    _same(closed["resources"], [{"ordinal": index, "label": label, "closeAttempted": True, "closed": True}
        for index, label in enumerate(("directory", "reader", "directory", "reader"))],
        "AUTHORITY_METADATA_ORIGINAL_ROSTER")
    return start, row, birth, child, ack


def _custody_read_authority_phase(owner, private, context_raw, source, phase, window, primary_result):
    """Read THIS native return, then recheck current authority from its originals."""
    require(type(owner) is _CustodyOwner and type(phase) is native.OriginalPhase and
        owner.phase_originals is phase and phase.context == context_raw and owner.fence is window and
        any(row["owner"] is private and row["attempted"] is False for row in owner.resources),
        "AUTHORITY_NOT_ORIGINAL_PHASE")
    owner.check()
    source_pin, phase_pin = N._source_pin(source), N._phase_pin(phase)
    graph = N._history_graph(source, phase)
    same_window, primary, history_raw, copy_raw, historical = checked_primary(primary_result)
    require(same_window is window, "AUTHORITY_PRIMARY_WINDOW_CHANGED")
    path, first = private.path, window._view().binding[0]
    boot = window._view().binding[2]
    context, expected, event = _custody_authority_context(context_raw, path, first, boot)
    require(context["history"] == canonical(history_raw) and context["primaryResultSha256"] == primary.result_sha256 and
        context["primaryCopySha256"] == O.digest(copy_raw) and
        context["window"] == canonical(_custody_authority_window(window)) and
        tuple(context["directoryIdentity"]) == tuple(private.identity) and
        owner.read(private, "context.json") == context_raw and
        owner.read(private, "authority-window.json") == _custody_authority_window(window),
        "AUTHORITY_CURRENT_CONTEXT")
    policy = N.source_readback(owner, path / "source-before", source)
    require(context["sourceReturnSha256"] == O.digest(source.raw) and
        context["sourceReturnedNs"] == canonical(source.raw)["returnedNs"], "AUTHORITY_SOURCE_RETURN")
    records = dict(phase.records)
    require(len(phase.records) == len(native.PHASE_FILES) and set(records) == native.PHASE_FILES,
        "AUTHORITY_ORIGINAL_PHASE_ROSTER")
    directory = owner.child(private, "service")
    private_pin, service_pin = tuple(private.identity), tuple(directory.identity)
    require(all(owner.read(directory, name) == raw for name, raw in phase.records), "AUTHORITY_PHASE_READBACK")
    child_raw = owner.read(directory, "child-result.json")
    start, row, birth, child, ack = _custody_authority_phase_bytes(context_raw, path, first.clock,
        records, child_raw, private_pin, service_pin)
    queries = owner.open(path / "acquisition-queries")
    session = N.query_session(owner, queries)
    originals = tuple((name, owner.read(queries, name + ".bin")) for name in N.ORIGINAL_KEYS)
    original = dict(originals)
    require(child["querySessionSha256"] == O.digest(session) and child["originalsSha256"] ==
        {name: O.digest(raw) for name, raw in originals} and child["matchSha256"] == O.digest(original["match"]) and
        original["event"] == event and {name: original[name] for name in N.SOURCE_KEYS} == policy and
        original["match"] == expected.record == dict(historical)["P/acquisition-queries/match.bin"],
        "AUTHORITY_ORIGINAL_BYTES")
    match, service = N.retained_match(context, original, start["invocation"], window.clock,
        start["startedNs"], start["workEndNs"])
    captured = (context_raw, originals, start["invocation"], start["startedNs"], start["workEndNs"])
    match_pin = _custody_match_pin(match, primary.kind)
    return_graph = N._history_graph(match.__dict__, captured)
    require(type(match) is type(expected) and match.record == expected.record and
        list(N._service_job(captured, window.clock)) == canonical(history_raw)["serviceJob"],
        "AUTHORITY_CURRENT_MATCH_OR_JOB")
    minimum = N._service_chain_minimum(first.nanoseconds, context["sourceReturnedNs"], start, row, birth, child, service, ack)
    checked = window.now(minimum=minimum)
    N._check_history(graph)
    N._check_history(return_graph)
    _custody_match_check(match_pin)
    owner.check()
    require(N._source_pin(source)[1:] == source_pin[1:] and N._phase_pin(phase)[1:] == phase_pin[1:] and
        owner.phase_originals is phase, "AUTHORITY_NATIVE_ORIGINAL_CHANGED")
    chain = {"phaseSha256": {name: O.digest(raw) for name, raw in phase.records}, "childSha256": O.digest(child_raw),
        "querySessionSha256": O.digest(session), "originalsSha256": {name: O.digest(raw) for name, raw in originals},
        "checkedNs": checked}
    return match, chain, captured, (child_raw, session)


def _custody_authority_index(owner, path, window, originals, pending, before, after, phase, match, captured):
    """Index all actual new originals, retaining original pins vs declarations."""
    require(type(originals) is tuple and len(originals) == len(dict(originals)) == 37 and
        all(type(name) is str and type(raw) is bytes for name, raw in originals) and
        type(pending) is bytes and owner.phase_originals is phase and
        owner.initial_sources.get(str(path / "source-before")) is before and
        owner.initial_sources.get(str(path / "source-after")) is after, "AUTHORITY_INDEX_ORIGINALS")
    available = dict((*originals, ("authority-pending.json", pending)))
    data = dict(captured[1])
    require(tuple(data) == N.ORIGINAL_KEYS and data["match"] == match.record and
        {name: data[name] for name in N.SOURCE_KEYS} == dict(before.records) == dict(after.records),
        "AUTHORITY_INDEX_MATCH")
    indexed, directories = [], [path, path / "control-home", path / "temporary", path / "service"]
    for name, source, raw, values in (
            ("source-before", before, before.session, dict(before.records)),
            ("acquisition-queries", None, available["acquisition-queries/session-result.json"], data),
            ("source-after", after, after.session, dict(after.records))):
        rows, paths = N._gate_query_index(path / name, raw, values, source=source)
        indexed.extend(rows)
        directories.extend(paths)
    for name in ("authority-window.json", "context.json", "authority-pending.json",
            *("service/" + name for name in sorted(native.PHASE_FILES)), "service/child-result.json"):
        raw = available[name]
        maximum = (native.ACK_LIMIT if name == "service/stdout.log" else
            native.STDERR_LIMIT if name == "service/stderr.log" else native.LIMIT)
        require(len(raw) <= maximum, "AUTHORITY_INDEX_RECORD_LIMIT")
        indexed.append((path / name, maximum, len(raw), O.digest(raw)))
    require(len(indexed) == len({target for target, *_ in indexed}) == 281 and
        len(directories) == len(set(directories)) == 58, "AUTHORITY_INDEX_COMPLETE_ROSTER")
    targets = {".": path, **{name: path / name for name in
        ("control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")}}
    pins = N._worker_pins(owner, window.clock.role, targets)
    identities = {key: identity for key, _row, _dir, _path, identity in pins}
    require(set(identities) == set(targets), "AUTHORITY_INDEX_REQUIRED_PINS")
    files = []
    for target, maximum, count, checksum in sorted(indexed):
        name = target.relative_to(path).as_posix()
        if name in available:
            require(count == len(available[name]) and checksum == O.digest(available[name]), "AUTHORITY_INDEX_RAW_CHANGED")
        files.append({"relative": name, "maximum": maximum, "bytes": count, "sha256": checksum,
            "provenance": "ACTUAL_RETAINED_BYTES" if name in available else "ORIGINAL_QUERY_DECLARATION"})
    require(sum(row["provenance"] == "ACTUAL_RETAINED_BYTES" for row in files) == 38 and
        sum(row["bytes"] for row in files) <= MAX_BYTES, "AUTHORITY_INDEX_AVAILABLE_ROSTER")
    entries = []
    for target in sorted(directories):
        name = "." if target == path else target.relative_to(path).as_posix()
        entries.append({"relative": name, "identity": None if name not in identities else list(identities[name]),
            "provenance": "ORIGINAL_NATIVE_PIN" if name in identities else "ORIGINAL_QUERY_DECLARATION"})
    raw = O.encoded({"schema": 1, "scope": _AUTHORITY_INDEX_SCOPE, "origin": "AUTHORITY_PRE_EXPORT",
        "root": str(path), "clock": O.clock_value(window.clock), "contextSha256": O.digest(phase.context),
        "matchSha256": O.digest(match.record), "pendingSha256": O.digest(pending), "files": files, "directories": entries,
        "fileCount": len(files), "directoryCount": len(entries), "totalBytes": sum(row["bytes"] for row in files),
        "copyState": "ORIGINAL_BYTES_NOT_COPIED", "exportSaveAuthority": False})
    canonical(raw)
    return raw, pins


@dataclass(frozen=True, repr=False)
class CustodyAuthority:
    """Actual authority-1 return, not a live lease, Admission or export capability."""
    primary: object
    raw: bytes
    inventory: bytes
    originals: tuple


def custody_authority(primary_result, token):
    """One original native acquisition under the SAME live custody Window."""
    require("fixed" not in _AUTHORITY_ATTEMPTS, "AUTHORITY_REUSE")
    attempt = {"primary": primary_result, "state": "STARTED", "failure": None, "owner": None, "return": None}
    _AUTHORITY_ATTEMPTS["fixed"] = attempt
    owner = result = None
    match_pins = []
    source_links = ()
    phase_link = None
    pins = ()
    graphs = []
    failure = None
    try:
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and
            not any(name in os.environ for name in _CREDENTIAL_NAMES), "AUTHORITY_TOKEN_BOUNDARY")
        window, primary, history_raw, copy_raw, historical = checked_primary(primary_result)
        history, source_files = canonical(history_raw), dict(historical)
        window_raw = _custody_authority_window(window)
        first = window._view().binding[0]
        observed, actual_root, event = N.host_context(history["firstUseAt"])
        roots, _handoff, custody_path = _paths(primary.kind)
        require(actual_root == roots["P"] and observed == history["observed"] and
            event == source_files["P/acquisition-queries/event.bin"], "AUTHORITY_ACTUAL_PRIMARY_CONTEXT")
        graphs.append(N._history_graph(primary_result, observed, first))
        window.now()
        owner = _CustodyOwner(window.deadline(900, final=True), window, first=first, cancelled=window._view().binding[6])
        attempt["owner"] = owner
        owner_anchor = owner._anchor()
        owner_binding = (owner.__dict__, owner.resources, owner.errors, owner.initial_sources)
        def current():
            require(_AUTHORITY_ATTEMPTS.get("fixed") is attempt and attempt["primary"] is primary_result and
                attempt["owner"] is owner and attempt["state"] in ("STARTED", "RETURNED") and
                attempt["failure"] is None, "AUTHORITY_ATTEMPT_CHANGED")
            require(owner.__dict__ is owner_binding[0] and owner.resources is owner_binding[1] and
                owner.errors is owner_binding[2] and owner.initial_sources is owner_binding[3] and
                owner.original is None and owner.unknown is False and owner.errors == [], "AUTHORITY_OWNER_CHANGED")
            require(checked_primary(primary_result)[0] is window, "AUTHORITY_PRIMARY_RETURN_CHANGED")
            require(owner._anchor() is owner_anchor, "AUTHORITY_ORIGINAL_OWNER_ANCHOR")
            owner.check()
            require(set(owner.initial_sources) == {key for key, _source in source_links} and
                all(owner.initial_sources[key] is source for key, source in source_links) and
                owner.phase_originals is phase_link, "AUTHORITY_ORIGINAL_LINKS_CHANGED")
            for pin in match_pins:
                _custody_match_check(pin)
            for graph in graphs:
                N._check_history(graph)
            if pins:
                N._check_worker_pins(pins, first.clock.role, closed=owner.closed)
        current()
        root = owner.open(custody_path)
        require(native._initializer_names(owner, root) == ("copied-evidence",), "AUTHORITY_CUSTODY_INITIAL_ROSTER")
        path = custody_path / "authority-1"
        private = owner.child(root, "authority-1", create=True)
        private_pin = tuple(private.identity)
        owner.write(private, "authority-window.json", window_raw)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        current()
        before = N.source_queries(owner, window, observed, path / "source-before")
        source_links = ((str(path / "source-before"), before),)
        before_pin = N._source_pin(before)
        graphs.append(N._history_graph(before))
        current()
        require(dict(before.records) == {name: source_files["P/acquisition-queries/" + name + ".bin"]
            for name in N.SOURCE_KEYS}, "AUTHORITY_SOURCE_CHANGED")
        expected_raw = source_files["P/acquisition-queries/match.bin"]
        context_raw = owner.write(private, "context.json", {"schema": 1,
            "scope": native.INITIAL_CUSTODY_AUTHORITY_CONTEXT_SCOPE, "window": canonical(window_raw),
            "history": history, "observed": observed, "expectedMatch": canonical(expected_raw), "eventSha256": O.digest(event),
            "root": str(ROOT), "session": str(path), "job": N.uuid.uuid4().hex, "inheritedContext": Q._inherited_context(),
            "sourceReturnSha256": O.digest(before.raw), "sourceReturnedNs": canonical(before.raw)["returnedNs"],
            "primaryResultSha256": primary.result_sha256, "primaryCopySha256": O.digest(copy_raw),
            "directoryIdentity": list(private_pin), "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _, phase = N._initial_service_phase(owner, private, context_raw, token, window, before)
        phase_link = phase
        token = None
        phase_pin = N._phase_pin(phase)
        graphs.append(N._history_graph(phase))
        current()
        _custody_read_authority_phase(owner, private, context_raw, before, phase, window, primary_result)
        current()
        after = N.source_queries(owner, window, observed, path / "source-after")
        source_links = (*source_links, (str(path / "source-after"), after))
        after_pin = N._source_pin(after)
        graphs.append(N._history_graph(after))
        current()
        require(N.source_readback(owner, path / "source-after", after) == dict(before.records),
            "AUTHORITY_FINAL_SOURCE_CHANGED")
        match, chain, captured, (child_raw, session_raw) = _custody_read_authority_phase(
            owner, private, context_raw, before, phase, window, primary_result)
        match_pin = _custody_match_pin(match, primary.kind)
        match_pins.append(match_pin)
        graphs.append(N._history_graph(match.__dict__, chain, captured))
        current()
        files = [("authority-window.json", window_raw), ("context.json", context_raw),
            ("service/child-result.json", child_raw), ("acquisition-queries/session-result.json", session_raw)]
        files.extend(("service/" + name, raw) for name, raw in phase.records)
        files.extend(("acquisition-queries/" + name + ".bin", raw) for name, raw in captured[1])
        for name, source in (("source-before", before), ("source-after", after)):
            files.extend(((name + "/source-return.json", source.raw), (name + "/session-result.json", source.session)))
            files.extend((name + "/" + label + ".bin", raw) for label, raw in source.records)
        originals = tuple(files)
        pending = owner.write(private, "authority-pending.json", {"schema": 1, "scope": _AUTHORITY_PENDING_SCOPE,
            "windowSha256": O.digest(window_raw), "primaryResultSha256": primary.result_sha256,
            "primaryCopySha256": O.digest(copy_raw), "matchSha256": O.digest(match.record),
            "filesSha256": {name: O.digest(raw) for name, raw in originals}, "originalChain": chain,
            "retainedNs": window.now(), "retirement": "PENDING_OWNER_CLOSE", "exportSaveAuthority": False})
        inventory_raw, pins = _custody_authority_index(owner, path, window, originals, pending,
            before, after, phase, match, captured)
        graphs.append(N._history_graph(originals, tuple(path for _key, _row, _dir, path, _identity in pins),
            tuple(identity for _key, _row, _dir, _path, identity in pins)))
        current()
        require(N._source_pin(before)[1:] == before_pin[1:] and N._source_pin(after)[1:] == after_pin[1:] and
            N._phase_pin(phase)[1:] == phase_pin[1:] and owner.phase_originals is phase and
            owner.initial_sources == {str(path / "source-before"): before, str(path / "source-after"): after} and
            tuple(private.identity) == private_pin and
            native._initializer_names(owner, root) == ("authority-1", "copied-evidence"),
            "AUTHORITY_ORIGINAL_RETURN_CHANGED")
        preclose = window.now()
        current()
        owner.freeze()
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("custody-authority", error)
            failure = owner._anchor().failure
    finally:
        token = None
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                owner.error("custody-authority-close", error)
            if failure is None and owner._anchor().failure is not None:
                failure = owner._anchor().failure
    try:
        if failure is not None:
            raise failure
        require(owner is not None and owner._anchor() is owner_anchor, "AUTHORITY_INCOMPLETE")
        owner.known()
        current()
        closed = window.now(minimum=preclose)  # Original WORK, not a new or native-final allowance.
        current()
        raw = O.encoded({"schema": 1, "scope": _AUTHORITY_RETURN_SCOPE, "windowSha256": O.digest(window_raw),
            "primaryResultSha256": primary.result_sha256, "primaryCopySha256": O.digest(copy_raw),
            "matchSha256": O.digest(match.record), "inventorySha256": O.digest(inventory_raw),
            "pendingSha256": O.digest(pending), "originalChain": chain, "preCloseNs": preclose, "closedNs": closed,
            "resourceCount": len(owner_anchor.frozen), "retirement": "KNOWN_RESOURCE_CLOSE_ONLY",
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        canonical(raw)
        all_originals = (*originals, ("authority-pending.json", pending))
        result = CustodyAuthority(primary_result, raw, inventory_raw, all_originals)
        return_graph = N._history_graph(result.__dict__, all_originals)
        saved = (result, primary_result, raw, inventory_raw, all_originals, window, current,
            owner, owner_anchor, owner.__dict__, return_graph, match_pin, captured, attempt)
        require(id(result) not in _AUTHORITY_RETURNS, "AUTHORITY_RETURN_REUSE")
        _AUTHORITY_RETURNS[id(result)] = saved
        attempt["return"], attempt["state"] = result, "RETURNED"
        checked_custody_authority(result, primary_result)
        return result
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def checked_custody_authority(result, primary_result):
    """Authenticate this same-process return only; do not renew remote authority."""
    saved = _AUTHORITY_RETURNS.get(id(result))
    require(type(result) is CustodyAuthority and type(saved) is tuple and saved[0] is result and
        saved[1] is primary_result and result.primary is primary_result, "AUTHORITY_NOT_ORIGINAL_RETURN")
    _, _primary, raw, inventory, originals, window, current, owner, anchor, dictionary, graph, match_pin, captured, attempt = saved
    try:
        require(attempt["state"] == "RETURNED" and attempt["return"] is result and result.raw == raw and
            result.inventory == inventory and result.originals is originals, "AUTHORITY_RETURN_CHANGED")
        N._check_history(graph)
        current()
        require(owner.__dict__ is dictionary and owner._anchor() is anchor, "AUTHORITY_RETURN_OWNER_CHANGED")
        owner.known()
        match = _custody_match_check(match_pin)
        require(window._view().failure is None, "AUTHORITY_RETURN_FAILED_WINDOW")
        return window, match, captured, raw, inventory, originals
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


# This one-way exit does not make an Admission or extend the original prep.
# The productive driver must create NEW parents and acquire NEW authority at
# each fixed use site. In particular it cannot retain authority-1's current()
# closure as the cancellation/authority callback of a productive owner.
_PRODUCTIVE_PREFIX_ATTEMPTS, _PRODUCTIVE_PREFIX_RETURNS = {}, {}
_PRODUCTIVE_PREFIX_ENTRY = B.EntryLatch(_PRODUCTIVE_PREFIX_ATTEMPTS)
_PRODUCTIVE_INITIALIZER_NAMES = (
    "I/receiving-window.json", "I/initializer-context.json", "I/initialization-pending.json",
    *("I/canonical-init/" + name for name in sorted(native.PHASE_FILES | {"request.json"})),
    "I/state/context.json", "I/state/gradle-home/gradle.properties",
)


@dataclass(frozen=True, repr=False)
class RetiredProductivePrefix:
    """Closed original prefix DATA and same-call provenance, not live authority."""
    raw: bytes
    primary: object
    authority: object
    identity: object
    history: bytes
    proposal: bytes
    originals: tuple
    initializer_originals: tuple
    initializer_directories: tuple
    initializer: object
    first: object
    original_boot: str
    retired_ns: int
    retired_local: float


def retire_primary_for_productive(primary_result, authority_result):
    """Read the real initializer inputs, close, then terminally retire C prep.

    This is called only by the fixed productive driver while it honestly holds
    its API token in the parent stack. Environment/child credential boundaries
    remain unchanged. No crypto/export is entered here and no token is returned.
    The twelve original initializer files are read through a NEW bounded
    file-only owner and compared to the authentic PRIMARY index. They do not
    reexecute the initializer or the accepted complete-reader fixture.
    """
    entry = _PRODUCTIVE_PREFIX_ENTRY
    attempt = entry.begin(_PRODUCTIVE_PREFIX_ATTEMPTS)
    wrapper = window = result = None
    failure = None
    try:
        entry.check(_PRODUCTIVE_PREFIX_ATTEMPTS, attempt)
        window, primary, history_raw, _copy_raw, originals = checked_primary(primary_result)
        same_window, match, captured, authority_raw, inventory_raw, authority_originals = \
            checked_custody_authority(authority_result, primary_result)
        require(primary.kind == "worker" and same_window is window and
            type(match) is A.stages.BootstrapMatch and not any(name in os.environ for name in _CREDENTIAL_NAMES),
            "PRODUCTIVE_PREFIX_ORIGINAL_WORKER")
        primary_saved = _PRIMARY_RETURNS[id(primary_result)]
        authority_saved = _AUTHORITY_RETURNS[id(authority_result)]
        anchor = window._view()
        first, _local, boot, _limits, _ends, _locals, callback = anchor.binding
        history, historical = canonical(history_raw), dict(originals)
        identity = N.initial_identity.bind_worker_match(match,
            event_raw=historical["P/acquisition-queries/event.bin"],
            policy_raw=historical["P/acquisition-queries/candidate_policy_raw.bin"], now=int(time.time()))
        proposal = historical["P/worker-allocation-proposal.json"]
        require(identity.record == historical["P/worker-identity.json"] and
            match.record == historical["P/acquisition-queries/match.bin"] and
            captured[0] == dict(authority_originals)["context.json"] and
            N._service_job(captured, first.clock) == tuple(history["serviceJob"]),
            "PRODUCTIVE_PREFIX_IDENTITY_OR_CONTINUITY")
        roots, _handoff, _custody = _paths("worker")
        initializer = roots["I"]
        directories = tuple((name, pin, provenance) for name, pin, provenance in primary.directories
            if name in INITIALIZER_DIRECTORIES)
        require(len(directories) == 8 and all(pin is not None for _name, pin, _provenance in directories),
            "PRODUCTIVE_PREFIX_INITIALIZER_PINS")
        pins = {name: pin for name, pin, _provenance in directories}
        file_rows = {row[0]: row for row in primary.files}
        window.now()
        owner = native.Owner(window.deadline(900, final=True), window, first=first, cancelled=callback)
        owner.work_limit, owner.final_limit = window.work, window.final
        wrapper = _PrimaryOwner(owner)
        opened, read = {}, {}
        for name in _PRODUCTIVE_INITIALIZER_NAMES:
            entry.check(_PRODUCTIVE_PREFIX_ATTEMPTS, attempt)
            require(checked_primary(primary_result)[0] is window and
                checked_custody_authority(authority_result, primary_result)[0] is window,
                "PRODUCTIVE_PREFIX_ORIGINAL_CHANGED")
            parent, leaf = name.rsplit("/", 1)
            if parent not in opened:
                path = initializer.joinpath(*parent.split("/")[1:])
                opened[parent] = _private(wrapper, path)
                require(tuple(opened[parent].identity) == pins[parent], "PRODUCTIVE_PREFIX_DIRECTORY_CHANGED")
            require(name in file_rows, "PRODUCTIVE_PREFIX_FILE_NOT_INDEXED")
            read[name] = _read_private(wrapper, opened[parent], leaf, file_rows[name][1])
        _indexed_originals(primary, read, _PRODUCTIVE_INITIALIZER_NAMES)
        context = canonical(read["I/initializer-context.json"])
        canonical_context = N.native.initialization.producer.parse(read["I/state/context.json"])
        # The canonical supplier uses its own indented JSON; preserve its exact
        # bytes and run the maintained initial-origin predicate, not a reencode.
        N.native.initialization.initial_recipient_context_record(read["I/state/context.json"],
            worker_raw=identity.record, root=str(ROOT), state=str(initializer / "state"), role=first.clock.role,
            outer_job=context["job"], homes=tuple(canonical_context["javaHomes"]),
            policy_raw=read["I/state/gradle-home/gradle.properties"])
        initializer_originals = tuple((name, read[name]) for name in _PRODUCTIVE_INITIALIZER_NAMES)
        data_graph = N._history_graph(identity.__dict__, initializer_originals, directories, first,
            primary_result.__dict__, authority_result.__dict__)
        close_raw = wrapper.finish()
        entry.check(_PRODUCTIVE_PREFIX_ATTEMPTS, attempt)
        require(checked_primary(primary_result)[0] is window and
            checked_custody_authority(authority_result, primary_result)[0] is window,
            "PRODUCTIVE_PREFIX_CLOSE_CHANGED")
        before = window.now()
        raw = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_PRIMARY_RETIRED_FOR_PRODUCTIVE_V1",
            "clock": O.clock_value(first.clock), "originalBootDigest": boot,
            "primaryResultSha256": primary.result_sha256, "primaryCopySha256": O.digest(primary_result.copy),
            "authoritySha256": O.digest(authority_raw), "authorityInventorySha256": O.digest(inventory_raw),
            "workerIdentitySha256": O.digest(identity.record), "originalProposalSha256": O.digest(proposal),
            "initializer": str(initializer), "initializerFilesSha256":
                {name: O.digest(blob) for name, blob in initializer_originals},
            "inputOwnerClose": canonical(close_raw), "inputsClosedNs": before,
            "originalPrepWorkEndNs": window.work, "prepDisposition": "TERMINALLY_RETIRED",
            "receivingDisposition": "HISTORICAL_NOT_REVIVED", "currentAuthority": "NEW_PER_USE_REQUIRED",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        canonical(raw)
        N._check_history(data_graph)
        retired = window.now(minimum=before)  # Includes serialization and actual original file close.
        entry.check(_PRODUCTIVE_PREFIX_ATTEMPTS, attempt)
        wrapper.structural()
        require(wrapper.finished and wrapper.failure is None and wrapper.owner.closed and
            not wrapper.owner.unknown and wrapper.errors == [] and
            all(attempted and closed for _row, _label, _resource, attempted, closed in wrapper.rows) and
            anchor.retired is None and anchor.failure is None and not anchor.busy,
            "PRODUCTIVE_PREFIX_CLOSE_NOT_KNOWN")
        result = RetiredProductivePrefix(raw, primary_result, authority_result, identity, history_raw,
            proposal, originals, initializer_originals, directories, initializer, first, boot, retired, anchor.local_last)
        result_graph = N._history_graph(result.__dict__, identity.__dict__)
        saved = (result, result_graph, data_graph, primary_saved, authority_saved, window, anchor,
            wrapper, wrapper._anchor(), close_raw, entry, attempt, retired, anchor.local_last)
        require(id(result) not in _PRODUCTIVE_PREFIX_RETURNS and id(window) not in _RETIRED_PRODUCTIVE_WINDOWS,
            "PRODUCTIVE_PREFIX_RETIRE_ONCE")
        _PRODUCTIVE_PREFIX_RETURNS[id(result)] = saved
        _RETIRED_PRODUCTIVE_WINDOWS[id(window)] = result
        anchor.retired = result  # No callback/observation occurs between the two original registry writes.
        entry.complete(_PRODUCTIVE_PREFIX_ATTEMPTS, attempt, result)
        checked_retired_primary(result)
        return result
    except BaseException as error:
        failure = entry.fail(error)
        if window is not None:
            window._error(window._anchor(), failure)
        if wrapper is not None and not wrapper.finished:
            try:
                wrapper.remember(failure)
                wrapper.finish()
            except BaseException:
                pass  # Original first failure and actual owner cleanup/UNKNOWN remain retained.
        raise failure


def checked_retired_primary(result):
    """Passive original-close check ONLY; no old current(), RAW or deadline call."""
    saved = _PRODUCTIVE_PREFIX_RETURNS.get(id(result))
    require(type(result) is RetiredProductivePrefix and type(saved) is tuple and saved[0] is result,
        "PRODUCTIVE_PREFIX_NOT_ORIGINAL_RETURN")
    _, result_graph, data_graph, primary_saved, authority_saved, window, anchor, wrapper, owner_anchor, \
        close_raw, entry, attempt, retired, local = saved
    try:
        entry.returned(_PRODUCTIVE_PREFIX_ATTEMPTS, attempt, result)
        N._check_history(result_graph)
        N._check_history(data_graph)
        require(_PRIMARY_RETURNS.get(id(result.primary)) is primary_saved and
            _AUTHORITY_RETURNS.get(id(result.authority)) is authority_saved and
            _WINDOWS.get(id(window)) is anchor and window._bound is anchor.binding and
            _RETIRED_PRODUCTIVE_WINDOWS.get(id(window)) is result and anchor.retired is result and
            anchor.failure is None and not anchor.busy and anchor.last == retired and anchor.local_last == local and
            result.retired_ns == retired and result.retired_local == local, "PRODUCTIVE_PREFIX_RETIRED_BINDING")
        for original, original_attempt in ((result.primary, primary_saved[12]),
                (result.authority, authority_saved[13])):
            require(original_attempt["state"] == "RETURNED" and original_attempt["return"] is original and
                original_attempt["failure"] is None, "PRODUCTIVE_PREFIX_PREDECESSOR_FAILED")
        for graph in primary_saved[10]:
            N._check_history(graph)
        N._check_history(authority_saved[10])
        require(wrapper._anchor() is owner_anchor and wrapper.finished and wrapper.failure is None and
            wrapper.owner.closed and not wrapper.owner.unknown and wrapper.errors == [] and
            all(attempted and closed for _row, _label, _resource, attempted, closed in wrapper.rows),
            "PRODUCTIVE_PREFIX_INPUT_CLOSE_CHANGED")
        wrapper.structural()
        authority_saved[7].known()
        for owner, original_anchor in primary_saved[9]:
            require(owner._anchor() is original_anchor and owner.finished and owner.failure is None and
                owner.owner.closed and not owner.owner.unknown and owner.errors == [] and
                all(attempted and closed for _row, _label, _resource, attempted, closed in owner.rows),
                "PRODUCTIVE_PREFIX_PRIMARY_CLOSE_CHANGED")
            owner.structural()
        require(canonical(result.raw)["inputOwnerClose"] == canonical(close_raw), "PRODUCTIVE_PREFIX_CLOSE_RECORD")
        entry.returned(_PRODUCTIVE_PREFIX_ATTEMPTS, attempt, result)
        return result
    except BaseException as error:
        raise entry.fail(error)


def _copy_authority(owner, primary_result, authority_result, destination):
    """Append only the original closed authority episode; no freeze or export.

    The fixed outer caller owns this NEW file-only owner and its final close.
    Both prior returns stay historical; they neither restore owners nor renew
    the SAME original Window. PRIMARY's original map is never rewritten.
    """
    require(type(owner) is _PrimaryOwner, "AUTHORITY_COPY_OWNER")
    try:
        owner.guard()
        window, primary, history, primary_raw, historical = checked_primary(primary_result)
        authority_window, match, captured, closed_raw, inventory_raw, originals = \
            checked_custody_authority(authority_result, primary_result)
        require(authority_window is window and type(window) is Window and owner.owner.fence is window and
            owner.owner.first is window._view().binding[0] and not owner.snapshots and
            owner.owner.work_limit == window.work and owner.owner.final_limit == window.final,
            "AUTHORITY_COPY_ORIGINAL_WINDOW")
        require(any(row[2] is destination and row[1] == "directory" and not row[3] and not row[4]
            for row in owner.rows), "AUTHORITY_COPY_OWNED_DESTINATION")
        roots, handoff, custody_path = _paths(primary.kind)
        require(destination.path == custody_path / "copied-evidence" and
            primary.role == window.clock.role, "AUTHORITY_COPY_FIXED_DESTINATION")

        def current():
            owner.guard()
            now = checked_primary(primary_result)
            require(now[0] is window and now[1] is primary and now[2] == history and
                now[3] == primary_raw and now[4] is historical, "AUTHORITY_COPY_PRIMARY_CHANGED")
            now = checked_custody_authority(authority_result, primary_result)
            require(now[0] is window and now[1] is match and now[2] is captured and
                now[3] == closed_raw and now[4] == inventory_raw and now[5] is originals,
                "AUTHORITY_COPY_RETURN_CHANGED")
            require(_paths(primary.kind) == (roots, handoff, custody_path) and
                destination.path == custody_path / "copied-evidence", "AUTHORITY_COPY_PATH_CHANGED")
            owner.structural()  # No callback after the original-return checks.

        def metadata(snapshot):
            return [[name, directory, list(identity), count, O.parse(raw)]
                for name, directory, identity, count, raw in snapshot.metadata]

        old = canonical(primary_raw)
        require(old["scope"] == PRIMARY_SCOPE and old["origin"] == "PRIMARY" and
            old["destination"] == str(destination.path) and old["destinationIdentity"] == list(destination.identity) and
            type(old["members"]) is list and type(old["memberCount"]) is int and
            old["memberCount"] == old["nextOrdinal"] == len(old["members"]) > 0 and
            old["totalBytes"] == sum(row["bytes"] for row in old["members"]) and
            old["remainingOrigins"] == list(ORIGINS[1:]) and old["freeze"] == "NOT_FINAL_THREE_ORIGIN_FREEZE" and
            old["exportSaveAuthority"] is False, "AUTHORITY_COPY_PRIMARY_MAP")
        previous_count = old["memberCount"]
        before = _snapshot(owner, "COPIED_PRIMARY", destination)
        require(metadata(before) == old["destinationMetadata"] and before.pin == tuple(old["destinationIdentity"]) and
            tuple(row[0] for row in before.metadata) == ("", *(_member_name(n) for n in range(previous_count))) and
            all(not row[1] for row in before.metadata[1:]), "AUTHORITY_COPY_PREVIOUS_DESTINATION")
        for number, (item, node) in enumerate(zip(old["members"], before.metadata[1:])):
            require(item["member"] == _member_name(number) and item["origin"] == "PRIMARY" and
                type(item["bytes"]) is int and item["bytes"] == node[3], "AUTHORITY_COPY_PREVIOUS_MEMBER")
            _written_matches(O.encoded(item["destinationWriteMetadata"]), node, before.windows)
            reader, verify = _snapshot_reader(owner, before, item["member"])
            _consume(owner, reader, item["bytes"], item["sha256"], verify)
            current()

        path = custody_path / "authority-1"
        index = fields(canonical(inventory_raw), "schema scope origin root clock contextSha256 matchSha256 "
            "pendingSha256 files directories fileCount directoryCount totalBytes copyState exportSaveAuthority",
            "AUTHORITY_COPY_INDEX_FIELDS")
        require(type(index["schema"]) is int and index["schema"] == 1 and index["scope"] == _AUTHORITY_INDEX_SCOPE and
            index["origin"] == ORIGINS[1] and index["root"] == str(path) and
            index["clock"] == O.clock_value(window.clock) and index["copyState"] == "ORIGINAL_BYTES_NOT_COPIED" and
            index["exportSaveAuthority"] is False and type(index["fileCount"]) is int and index["fileCount"] == 281 and
            type(index["directoryCount"]) is int and index["directoryCount"] == 58 and
            type(index["files"]) is list and len(index["files"]) == 281 and
            type(index["directories"]) is list and len(index["directories"]) == 58, "AUTHORITY_COPY_INDEX")
        require(type(originals) is tuple and len(originals) == 38 and
            all(type(name) is str and type(raw) is bytes for name, raw in originals) and
            len(dict(originals)) == 38, "AUTHORITY_COPY_RETAINED_ORIGINALS")
        available = dict(originals)
        closed = fields(canonical(closed_raw), "schema scope windowSha256 primaryResultSha256 primaryCopySha256 "
            "matchSha256 inventorySha256 pendingSha256 originalChain preCloseNs closedNs resourceCount retirement "
            "budgetAcceptance exportSaveAuthority", "AUTHORITY_COPY_CLOSED_FIELDS")
        require(type(closed["schema"]) is int and closed["schema"] == 1 and closed["scope"] == _AUTHORITY_RETURN_SCOPE and
            closed["windowSha256"] == O.digest(available["authority-window.json"]) and
            closed["primaryResultSha256"] == primary.result_sha256 and closed["primaryCopySha256"] == O.digest(primary_raw) and
            closed["inventorySha256"] == O.digest(inventory_raw) and
            closed["matchSha256"] == index["matchSha256"] == O.digest(match.record) and
            closed["pendingSha256"] == index["pendingSha256"] == O.digest(available["authority-pending.json"]) and
            index["contextSha256"] == O.digest(available["context.json"]) and
            captured[0] == available["context.json"] and dict(captured[1])["match"] == match.record and
            closed["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and closed["budgetAcceptance"] == "NOT_ADMITTED" and
            closed["exportSaveAuthority"] is False, "AUTHORITY_COPY_CLOSED_LINKS")
        current()
        source = _snapshot(owner, ORIGINS[1], _private(owner, path))
        nodes = {row[0]: row for row in source.metadata}
        file_rows, directory_rows = {}, {}
        for row in index["files"]:
            fields(row, "relative maximum bytes sha256 provenance", "AUTHORITY_COPY_FILE_FIELDS")
            name = row["relative"]
            require(type(name) is str and name and all(Q._component(part) == part for part in name.split("/")) and
                name not in file_rows and type(row["maximum"]) is int and type(row["bytes"]) is int and
                0 <= row["bytes"] <= row["maximum"] <= native.LIMIT and row["maximum"] > 0,
                "AUTHORITY_COPY_FILE")
            digest(row["sha256"])
            retained = name in available
            require(row["provenance"] == ("ACTUAL_RETAINED_BYTES" if retained else "ORIGINAL_QUERY_DECLARATION") and
                (not retained or row["bytes"] == len(available[name]) and row["sha256"] == O.digest(available[name])) and
                (row["bytes"] != 0 or row["sha256"] == O.digest(b"")), "AUTHORITY_COPY_FILE_PROVENANCE")
            file_rows[name] = row
        fixed_pins = {"", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries"}
        for row in index["directories"]:
            fields(row, "relative identity provenance", "AUTHORITY_COPY_DIRECTORY_FIELDS")
            relative = row["relative"]
            name = "" if relative == "." else relative
            require(type(name) is str and (relative == "." or name and
                all(Q._component(part) == part for part in name.split("/"))) and name not in directory_rows,
                "AUTHORITY_COPY_DIRECTORY")
            pinned = name in fixed_pins
            require(row["provenance"] == ("ORIGINAL_NATIVE_PIN" if pinned else "ORIGINAL_QUERY_DECLARATION") and
                (row["identity"] is not None) is pinned, "AUTHORITY_COPY_DIRECTORY_PROVENANCE")
            if pinned:
                pin = tuple(native.directory_identity(row["identity"], primary.role))
                require(name in nodes and nodes[name][1] is True and nodes[name][2] == pin,
                    "AUTHORITY_COPY_ORIGINAL_PIN")
            directory_rows[name] = row
        require(tuple(file_rows) == tuple(sorted(file_rows)) and tuple(directory_rows) == tuple(sorted(directory_rows)) and
            set(available) <= set(file_rows) and fixed_pins <= set(directory_rows) and
            len(set(file_rows) | set(directory_rows)) == 339 and set(nodes) == set(file_rows) | set(directory_rows) and
            all(nodes[name][1] is True for name in directory_rows) and
            all(nodes[name][1] is False and nodes[name][3] == row["bytes"] for name, row in file_rows.items()) and
            type(index["totalBytes"]) is int and index["totalBytes"] == sum(row["bytes"] for row in file_rows.values()),
            "AUTHORITY_COPY_EXACT_ROSTER")
        combined = (*before.metadata, *source.metadata)
        require(len({row[2] for row in combined}) == len(combined), "AUTHORITY_COPY_SOURCE_ALIAS")
        # Existing PRIMARY + original authority + the appended destination share
        # ONE unchanged aggregate allowance. Snapshot observations are retained.
        added_bytes = index["totalBytes"] + len(closed_raw)
        _aggregate(tuple(owner.snapshots), old["totalBytes"] + added_bytes, previous_count + 283)
        members = []
        for name, row in file_rows.items():
            current()
            target, written = _copy_member(owner, destination, previous_count + len(members), row["bytes"], row["sha256"],
                snapshot=source, name=name)
            members.append({"member": target, "origin": ORIGINS[1], "original": name,
                "originalMaximum": row["maximum"], "bytes": row["bytes"], "sha256": row["sha256"],
                "provenance": row["provenance"], "carrier": "INDEXED_DISK_ORIGINAL",
                "sourceCopyIdentity": list(nodes[name][2]), "destinationWriteMetadata": O.parse(written)})
            current()
        target, written = _copy_member(owner, destination, previous_count + len(members), len(closed_raw),
            O.digest(closed_raw), embedded=closed_raw)
        members.append({"member": target, "origin": ORIGINS[1], "original": "authority-return.json",
            "originalMaximum": native.LIMIT, "bytes": len(closed_raw), "sha256": O.digest(closed_raw),
            "provenance": "ACTUAL_CLOSED_PARENT_RETURN", "carrier": "EMBEDDED_NOT_DISK_ORIGINAL",
            "sourceCopyIdentity": None, "destinationWriteMetadata": O.parse(written)})
        require(len(members) == 282, "AUTHORITY_COPY_MEMBER_COUNT")
        current()
        after = _snapshot(owner, "COPIED_PRIMARY_AND_AUTHORITY", destination)
        require(after.path == before.path and after.pin == before.pin and
            tuple(row[0] for row in after.metadata) == ("", *(_member_name(n) for n in range(previous_count + 282))) and
            all(not row[1] for row in after.metadata[1:]) and
            after.metadata[1:previous_count + 1] == before.metadata[1:], "AUTHORITY_COPY_APPEND_TRANSITION")
        _aggregate(tuple(owner.snapshots))
        combined = (*source.metadata, *after.metadata)
        require(len({row[2] for row in combined}) == len(combined), "AUTHORITY_COPY_DESTINATION_ALIAS")
        for item, node in zip((*old["members"], *members), after.metadata[1:]):
            current()
            _written_matches(O.encoded(item["destinationWriteMetadata"]), node, after.windows)
            reader, verify = _snapshot_reader(owner, after, item["member"])
            _consume(owner, reader, item["bytes"], item["sha256"], verify)
        for snapshot in (source, after):
            current()
            _snapshot_current(owner, snapshot, rescan=True)
            current()
        raw = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_AUTHORITY_COPY_V1", "origin": ORIGINS[1],
            "primaryResultSha256": primary.result_sha256, "primaryCopySha256": O.digest(primary_raw),
            "authorityReturnSha256": O.digest(closed_raw), "authorityInventorySha256": O.digest(inventory_raw),
            "authorityInventoryBase64": base64.b64encode(inventory_raw).decode("ascii"),
            "members": members, "sourceMetadata": metadata(source), "originalDirectories": index["directories"],
            "destination": str(destination.path), "destinationIdentity": list(after.pin),
            "destinationBeforeMetadataSha256": O.digest(O.encoded({"metadata": metadata(before)})),
            "destinationRootBefore": metadata(before)[0], "destinationMetadata": metadata(after),
            "previousMemberCount": previous_count, "memberCount": len(members), "totalBytes": added_bytes,
            "aggregateMemberCount": previous_count + len(members), "aggregateTotalBytes": old["totalBytes"] + added_bytes,
            "nextOrdinal": previous_count + len(members), "freeze": "NOT_FINAL_THREE_ORIGIN_FREEZE",
            "remainingOrigins": [ORIGINS[2]], "productiveAuthority": False,
            "currentAuthority": "CLOSED_HISTORY_NOT_LIVE_LEASE", "exportSaveAuthority": False})
        canonical(raw)
        current()
        return raw
    except BaseException as error:
        raise owner.remember(error)


# This route owns ONLY validation/export. It grants no custody Step output,
# productive cache authority, seal, upload, or current post-export HTTP lease.
_CRYPTO_CONTEXT_SCOPE = "INITIAL_CUSTODY_CRYPTO_CONTEXT_V1"
_CRYPTO_START_SCOPE = "INITIAL_CUSTODY_CRYPTO_START_V1"
_CRYPTO_CHILD_SCOPE = "INITIAL_CUSTODY_CRYPTO_PENDING_CHILD_CLOSE_V1"
_CRYPTO_ACK_SCOPE = "INITIAL_CUSTODY_CRYPTO_POST_OWNER_CLOSE_ACK_V1"
_CRYPTO_CONTEXT_FIELDS = "schema scope kind root session job observed window primary authority filesSha256 " \
    "directories inheritedContext budgetAcceptance exportSaveAuthority"
_CRYPTO_INPUT_LIMITS = {
    "primary-map.json": native.LIMIT, "authority-map.json": native.LIMIT,
    "authority-return.json": native.LIMIT, "original-match.json": min(A.stages.LIMIT, native.LIMIT),
    "fresh-match.json": min(A.stages.LIMIT, native.LIMIT), "event.json": I.EVENT_LIMIT,
    "candidate-policy.json": I.POLICY_LIMIT, "recipient-public.asc": native.posix.MAX_KEY_BYTES,
}
_CRYPTO_DIRECTORIES = ("custody", "returned", "control-home", "temporary", "crypto-service",
    "copied-evidence", "public-crypto", "export-output")
_CRYPTO_ATTEMPTS, _CRYPTO_RETURNS = {}, {}
_CRYPTO_NATIVE_RETURNS = {}


def _custody_crypto_command(context_hash, minimum=None):
    result = native.initial_custody_authority_command(context_hash, minimum)
    result[5] = "_crypto"
    return result


def _crypto_context(context_raw, first, boot):
    """Closed fixed transport plus actual host; no transported clock is live."""
    context = fields(canonical(context_raw, 65536), _CRYPTO_CONTEXT_FIELDS, "CRYPTO_CONTEXT_FIELDS")
    clock, limits = _custody_authority_frame(context["window"])
    kind = context["kind"]
    require(type(context["schema"]) is int and context["schema"] == 1 and
        context["scope"] == _CRYPTO_CONTEXT_SCOPE and kind in ("gate", "worker") and
        limits["kind"] == kind and clock == first.clock and context["window"]["originalBootDigest"] == boot and
        context["root"] == str(ROOT) and context["budgetAcceptance"] == "NOT_ADMITTED" and
        context["exportSaveAuthority"] is False and not any(name in os.environ for name in _CREDENTIAL_NAMES),
        "CRYPTO_CONTEXT_BINDINGS")
    first_use = O.integer(context["observed"]["firstUseAt"], 1)
    observed, primary_path, event = N.host_context(first_use)
    roots, _handoff, custody = _paths(kind)
    returned = custody / "returned"
    require(observed == context["observed"] and observed["kind"] == kind and
        observed["role"] == first.clock.role and primary_path == roots["P"] and
        context["session"] == str(returned) and limits["startNs"] <= first.nanoseconds < limits["workEndNs"] and
        type(context["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", context["job"]), "CRYPTO_ACTUAL_CONTEXT")
    primary = fields(context["primary"], " ".join(E.PRIMARY_FIELDS), "CRYPTO_PRIMARY_FIELDS")
    require(primary["step"] == ("initial-originals" if kind == "gate" else "canonical-initialization") and
        primary["outcome"] == "success", "CRYPTO_PRIMARY_STEP")
    for name in ("resultSha256", "handoffSha256", "inventorySha256"):
        digest(primary[name])
    authority = fields(context["authority"], "returnSha256 matchSha256 copySha256", "CRYPTO_AUTHORITY_FIELDS")
    for value in authority.values():
        digest(value)
    hashes = fields(context["filesSha256"], " ".join(_CRYPTO_INPUT_LIMITS), "CRYPTO_INPUT_FIELDS")
    for value in hashes.values():
        digest(value)
    require(hashes["original-match.json"] == hashes["fresh-match.json"] == authority["matchSha256"] and
        hashes["authority-return.json"] == authority["returnSha256"] and
        hashes["authority-map.json"] == authority["copySha256"] and hashes["event.json"] == O.digest(event),
        "CRYPTO_ORIGINAL_INPUT_LINKS")
    directories = fields(context["directories"], " ".join(_CRYPTO_DIRECTORIES), "CRYPTO_DIRECTORY_FIELDS")
    identities = []
    for name in _CRYPTO_DIRECTORIES:
        if name == "export-output" and first.clock.role != "windows-x64":
            require(directories[name] is None, "CRYPTO_POSIX_OUTPUT_ABSENT")
        else:
            identities.append(tuple(native.directory_identity(directories[name], first.clock.role)))
    require(len(set(identities)) == len(identities), "CRYPTO_DIRECTORY_ALIAS")
    inherited = context["inheritedContext"]
    require(type(inherited) is dict and all(type(item) is str for item in inherited.values()) and
        (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)),
        "CRYPTO_PARENT_DOMAIN")
    return context, event


def _crypto_start_fields(context_raw, context, start, clock):
    fields(start, " ".join(native.START_FIELDS), "CRYPTO_START_FIELDS")
    path = _paths(context["kind"])[2] / "returned"
    frame = context["window"]
    require(type(start["schema"]) is int and start["schema"] == 1 and start["scope"] == _CRYPTO_START_SCOPE and
        start["contextSha256"] == O.digest(context_raw) and start["argv"] == _custody_crypto_command(O.digest(context_raw)) and
        start["cwd"] == str(ROOT) and start["role"] == clock.role and start["job"] == context["job"] and
        start["state"] == str(path) and start["home"] == str(path / "control-home") and
        type(start["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", start["invocation"]) and
        start["exitCode"] is None and start["launchAttempted"] is False and start["scopeAttempted"] is False and
        start["retirement"] == "UNKNOWN", "CRYPTO_START")
    began = O.integer(start["startedNs"], O.integer(frame["startNs"]))
    require(began < O.integer(start["workEndNs"]) and
        start["workEndNs"] == min(frame["workEndNs"], began + 210 * O.NS) and
        start["finalEndNs"] == min(frame["nativeFinalEndNs"], start["workEndNs"] + 45 * O.NS),
        "CRYPTO_ORIGINAL_PHASE")
    expected = native.processes.ownership_environment(context["inheritedContext"], context["job"],
        start["invocation"], str(path), str(path / "control-home"), allow_new_context=True)
    require(type(start["inheritedContext"]) is dict and
        start["inheritedContext"] == {name: expected[name] for name in Q._CONTEXT}, "CRYPTO_START_INHERITANCE")
    return start


def _crypto_start(context_raw, context, start, first, boot, event, inherited):
    checked, actual_event = _crypto_context(context_raw, first, boot)
    require(checked == context and type(event) is bytes and actual_event == event, "CRYPTO_FRAME_ORIGINALS")
    _crypto_start_fields(context_raw, context, start, first.clock)
    require(start["startedNs"] <= first.nanoseconds < start["workEndNs"] and
        type(inherited) is dict and set(inherited) == set(Q._CONTEXT) and inherited == start["inheritedContext"],
        "CRYPTO_NATIVE_INHERITANCE")
    domain = native.processes.ownership_domains(inherited[native.processes.CHAIN_ENV],
        inherited[native.processes.DOMAINS_ENV])[-1]
    require(domain == {"id": start["invocation"], "job": start["job"], "state": start["state"],
        "home": start["home"]}, "CRYPTO_NATIVE_DOMAIN")
    return start, domain


def _crypto_inputs(context, raws):
    """Fixed original-byte links, not a serialized PRIMARY/authority capability."""
    require(type(raws) is dict and set(raws) == set(_CRYPTO_INPUT_LIMITS), "CRYPTO_INPUT_ROSTER")
    for name, maximum in _CRYPTO_INPUT_LIMITS.items():
        raw = raws[name]
        require(type(raw) is bytes and 0 < len(raw) <= maximum and
            O.digest(raw) == context["filesSha256"][name], "CRYPTO_INPUT_BYTES")
    require(raws["original-match.json"] == raws["fresh-match.json"], "CRYPTO_MATCH_BYTES")
    kind = context["kind"]
    match_type = A.gate.GateEligibility if kind == "gate" else A.stages.BootstrapMatch
    match = canonical(raws["fresh-match.json"], _CRYPTO_INPUT_LIMITS["fresh-match.json"])
    require(match["firstUseAt"] == context["observed"]["firstUseAt"] and
        match["source"] == context["observed"]["source"], "CRYPTO_MATCH_SOURCE")
    primary, authority, closed = (canonical(raws[name]) for name in
        ("primary-map.json", "authority-map.json", "authority-return.json"))
    require(primary["scope"] == PRIMARY_SCOPE and primary["origin"] == ORIGINS[0] and
        authority["scope"] == "INITIAL_RECIPIENT_CUSTODY_AUTHORITY_COPY_V1" and authority["origin"] == ORIGINS[1] and
        closed["scope"] == _AUTHORITY_RETURN_SCOPE and closed["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and
        closed["windowSha256"] == O.digest(O.encoded(context["window"])) and
        closed["primaryResultSha256"] == authority["primaryResultSha256"] == context["primary"]["resultSha256"] and
        closed["primaryCopySha256"] == authority["primaryCopySha256"] == O.digest(raws["primary-map.json"]) and
        authority["authorityReturnSha256"] == O.digest(raws["authority-return.json"]) and
        authority["authorityInventorySha256"] == closed["inventorySha256"] and
        closed["matchSha256"] == context["authority"]["matchSha256"] and
        all(value["exportSaveAuthority"] is False for value in (primary, authority, closed)),
        "CRYPTO_PRIMARY_AUTHORITY_LINKS")
    try:
        inventory_raw = base64.b64decode(authority["authorityInventoryBase64"], validate=True)
    except (ValueError, TypeError):
        raise O.OriginError("INITIAL_CUSTODY_CRYPTO_AUTHORITY_INVENTORY_ENCODING") from None
    inventory = canonical(inventory_raw)
    require(O.digest(inventory_raw) == closed["inventorySha256"] and
        inventory["matchSha256"] == closed["matchSha256"] and inventory["pendingSha256"] == closed["pendingSha256"],
        "CRYPTO_AUTHORITY_INVENTORY_LINKS")
    policy, public = I._policy(raws["candidate-policy.json"], int(time.time()))
    require(public == raws["recipient-public.asc"] and O.digest(raws["candidate-policy.json"]) == A.stages.POLICY_SHA256 and
        policy["recipient"]["sha256"] == O.digest(public), "CRYPTO_RECIPIENT_PUBLIC_POLICY")
    return match_type(raws["original-match.json"]), match_type(raws["fresh-match.json"]), policy


@dataclass(frozen=True, repr=False)
class _CryptoNativeReturn:
    context: bytes
    records: tuple
    child: bytes
    phase: tuple


def _custody_crypto_native(owner, private, context_raw, window, check):
    """One token-free child, captured and retired within the original phase.

    The owner predates setup and keeps its original LOCAL255 ceiling. This
    function neither closes that outer owner nor grants the later READ edge.
    """
    require(type(owner) is _CustodyOwner and type(window) is Window and owner.fence is window and
        owner.first is window._view().binding[0] and callable(check), "CRYPTO_NATIVE_OWNER")
    context = canonical(context_raw, 65536)
    require(context["scope"] == _CRYPTO_CONTEXT_SCOPE and
        private.path == _paths(context["kind"])[2] / "returned" and
        tuple(private.identity) == tuple(context["directories"]["returned"]) and
        not any(name in os.environ for name in _CREDENTIAL_NAMES), "CRYPTO_NATIVE_CONTEXT")
    check()
    started = window.now()
    work_end = min(window.work, started + 210 * O.NS)
    final_end = min(window.final, work_end + 45 * O.NS)
    owner.enter_crypto_phase(context_raw, started, work_end, final_end)
    # Setup has already spent the owner's original ceiling. This only clips it.
    capture_end = min(owner.local_end, window.deadline(255, final=True, limit=final_end))
    invocation = uuid.uuid4().hex
    environment = native.processes.ownership_environment(native.recipient_environment(private.path),
        context["job"], invocation, str(private.path), str(private.path / "control-home"), allow_new_context=True)
    require(not any(name in environment for name in _CREDENTIAL_NAMES), "CRYPTO_NATIVE_TOKEN_FREE")
    start = {"schema": 1, "scope": _CRYPTO_START_SCOPE, "contextSha256": O.digest(context_raw),
        "argv": _custody_crypto_command(O.digest(context_raw)), "cwd": str(ROOT), "role": window.clock.role,
        "job": context["job"], "invocation": invocation, "state": str(private.path),
        "home": str(private.path / "control-home"),
        "inheritedContext": {name: environment[name] for name in Q._CONTEXT}, "startedNs": started,
        "workEndNs": work_end, "finalEndNs": final_end, "exitCode": None,
        "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"}
    _crypto_start_fields(context_raw, context, start, window.clock)
    directory = owner.child(private, "crypto-service")
    require(tuple(directory.identity) == tuple(context["directories"]["crypto-service"]), "CRYPTO_SERVICE_PIN")
    start_raw = owner.write(directory, "start.json", start)
    row = dict(start)
    row["captureOutcomes"] = {name: {"synced": False, "verified": False, "closeAttempted": False,
        "closed": False, "readback": False} for name in ("stdout", "stderr")}
    scope = out = err = child = baseline_raw = birth_raw = None
    native_known = False
    anchor = owner.check()
    resource_start = len(anchor.rows)
    try:
        check()
        out = owner.acquire("stdout", lambda: directory.create_file("stdout.log",
            max_bytes=native.ACK_LIMIT, deadline=capture_end))
        err = owner.acquire("stderr", lambda: directory.create_file("stderr.log",
            max_bytes=native.STDERR_LIMIT, deadline=capture_end))
        row["scopeAttempted"] = True
        scope = owner.acquire("native-scope", lambda: native.processes.make_scope(context["job"], invocation,
            str(private.path), str(private.path / "control-home")))
        row["preparerIdentity"] = native.preparer_identity(scope, window.clock.role)
        baseline_raw = owner.write(directory, "baseline.json", {"role": window.clock.role,
            "baseline": sorted(scope.baseline) if hasattr(scope, "baseline") else None,
            "kernelJob": window.clock.role == "windows-x64"})
        row["baselineSha256"] = O.digest(baseline_raw)
        check()
        row["launchMinimumNs"] = window.now(limit=work_end)
        argv = _custody_crypto_command(O.digest(context_raw), row["launchMinimumNs"])
        row["launchArgv"], row["launchAttempted"] = argv, True
        child = scope.spawn(argv, str(ROOT), environment, stdout=out, stderr=err)
        require(child.stdout is None and child.stderr is None, "CRYPTO_PRIVATE_SINKS")
        birth = scope.description()
        leaders = [value for value in birth.get("startedIdentities", []) if value.get("pid") == child.pid]
        require(len(leaders) == 1, "CRYPTO_NATIVE_BIRTH")
        row["leader"] = dict(leaders[0])
        native.lifetime(row["leader"], window.clock.role)
        birth_raw = owner.write(directory, "native-start.json", {"ownership": birth, "leader": row["leader"],
            "preparerIdentity": row["preparerIdentity"], "observedNs": window.now(limit=work_end)})
        row["nativeStartSha256"] = O.digest(birth_raw)
        while True:
            check()
            window.now(limit=work_end)
            if window.clock.role == "windows-x64":
                out.observe_live_output()
                err.observe_live_output()
            else:
                out.verify()
                err.verify()
            code = child.poll()
            if code is not None:
                row["exitCode"] = code  # Original supplier return before any later observation.
            observed = window.now(limit=work_end)
            if code is not None:
                row["completedNs"] = observed
                require(type(code) is int and code == 0, "CRYPTO_CHILD_FAILED")
                require(not scope.discover(), "CRYPTO_LEFT_DESCENDANTS")
                window.now(limit=work_end)
                break
            scope.discover()
            native.time.sleep(.025)
    except BaseException as error:
        owner.error("custody-crypto-native", error)
    finally:
        # Acquisition may return before a late guard raises. These private rows
        # retain the actual resources; no repeat allocation or inferred birth.
        saved = anchor.rows[resource_start:]
        scope = scope if scope is not None else next((r for _row, label, r, _a, _c in saved if label == "native-scope"), None)
        out = out if out is not None else next((r for _row, label, r, _a, _c in saved if label == "stdout"), None)
        err = err if err is not None else next((r for _row, label, r, _a, _c in saved if label == "stderr"), None)
        if scope is not None:
            try:
                # A failed original clock cannot prevent bounded cleanup, but
                # the retained prelaunch ceiling cannot yield successful use.
                try:
                    window.now(final=True, limit=final_end)
                except BaseException as error:
                    owner.error("crypto-final-clock", error)
                remaining = max(0, capture_end - time.monotonic())
                grace = min(5, remaining)
                row["survivors"] = scope.drain(grace=grace, kill_wait=min(5, max(0, remaining - grace)),
                    deadline=capture_end)
                require(row["survivors"] == [], "CRYPTO_SURVIVORS")
                row["ownership"] = scope.description()
                require(row["ownership"].get("discoveryErrors") == [], "CRYPTO_DRAIN_IDENTITY")
                if "preparerIdentity" in row:
                    require(native.preparer_identity(scope, window.clock.role) == row["preparerIdentity"],
                        "CRYPTO_DRAIN_IDENTITY")
                native.posix._deadline(capture_end)
                native_known = True
            except BaseException as error:
                owner.error("crypto-drain", error, unknown=True)
            owner.close_one(scope)
            original_row = next(r for r, _label, actual, _a, _c in anchor.rows if actual is scope)
            row["scopeCloseAttempted"], row["scopeClosed"] = original_row["attempted"], original_row["closed"]
            if not original_row["closed"]:
                native_known = False
                owner.error("crypto-scope-close", O.OriginError("INITIAL_CUSTODY_CRYPTO_SCOPE_UNKNOWN"), unknown=True)
        elif row["scopeAttempted"]:
            owner.error("crypto-scope-construction", O.OriginError("INITIAL_CUSTODY_CRYPTO_SCOPE_UNKNOWN"), unknown=True)
        else:
            native_known = True
        if native_known and not anchor.unknown:
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
                    native.posix._deadline(capture_end)
                except BaseException as error:
                    owner.error("crypto-capture", error)
                owner.close_one(stream)
                original_row = next(r for r, _label, actual, _a, _c in anchor.rows if actual is stream)
                outcome.update(closeAttempted=original_row["attempted"], closed=original_row["closed"])
        elif not native_known:
            owner.error("crypto-native-close", O.OriginError("INITIAL_CUSTODY_CRYPTO_NATIVE_UNKNOWN"), unknown=True)
        if row["launchAttempted"] and anchor.failure is not None:
            owner.error("crypto-child-return", anchor.failure, unknown=True)
    if anchor.failure is not None:
        raise anchor.failure
    require(native_known and not anchor.unknown and all(outcome[name] is True
        for outcome in row["captureOutcomes"].values() for name in ("synced", "verified", "closeAttempted", "closed")),
        "CRYPTO_NATIVE_NOT_RETIRED")
    row["finalizedNs"] = window.now(final=True, limit=final_end)
    captures = {}
    for name, maximum in (("stdout", native.ACK_LIMIT), ("stderr", native.STDERR_LIMIT)):
        captures[name] = owner.read(directory, name + ".log", maximum, final=True)
        row["captureOutcomes"][name]["readback"] = True
        native.posix._deadline(capture_end)
        window.now(final=True, limit=final_end)
    require(captures["stderr"] == b"", "CRYPTO_STDERR")
    row.update(retirement="KNOWN", errors=[], captures={name: {"sha256": O.digest(raw), "bytes": len(raw)}
        for name, raw in captures.items()})
    row_raw = owner.write(directory, "result.json", row, final=True)
    child_raw = owner.read(private, "crypto-child-result.json", final=True)
    native.posix._deadline(capture_end)
    window.now(final=True, limit=final_end)
    require(owner.phase_originals is None, "CRYPTO_NATIVE_RETURN_REUSE")
    returned = _CryptoNativeReturn(context_raw, tuple(sorted({"start.json": start_raw, "result.json": row_raw,
        "baseline.json": baseline_raw, "native-start.json": birth_raw, "stdout.log": captures["stdout"],
        "stderr.log": captures["stderr"]}.items())), child_raw, (started, work_end, final_end))
    owner.phase_originals = returned
    original = (returned, owner, window, owner.__dict__, anchor, scope, out, err, child, capture_end,
        returned.records, child_raw, returned.phase, returned.__dict__)
    _CRYPTO_NATIVE_RETURNS[id(returned)] = (original, N._history_graph(returned.__dict__, returned.records))
    owner.leave_crypto_phase(started, work_end, final_end)
    return returned


def _crypto_metadata(snapshot):
    return [[name, directory, list(identity), count, O.parse(raw)]
        for name, directory, identity, count, raw in snapshot.metadata]


def _crypto_previous(owner, destination, primary_raw, authority_raw):
    primary, authority = canonical(primary_raw), canonical(authority_raw)
    require(primary["scope"] == PRIMARY_SCOPE and primary["origin"] == ORIGINS[0] and
        authority["scope"] == "INITIAL_RECIPIENT_CUSTODY_AUTHORITY_COPY_V1" and authority["origin"] == ORIGINS[1] and
        authority["primaryCopySha256"] == O.digest(primary_raw) and
        authority["previousMemberCount"] == primary["memberCount"] == primary["nextOrdinal"] and
        authority["aggregateMemberCount"] == authority["nextOrdinal"] == primary["memberCount"] + authority["memberCount"] and
        authority["aggregateTotalBytes"] == primary["totalBytes"] + authority["totalBytes"] and
        authority["remainingOrigins"] == [ORIGINS[2]] and authority["freeze"] == "NOT_FINAL_THREE_ORIGIN_FREEZE" and
        primary["exportSaveAuthority"] is False and authority["exportSaveAuthority"] is False and
        primary["destination"] == authority["destination"] == str(destination.path) and
        primary["destinationIdentity"] == authority["destinationIdentity"] == list(destination.identity),
        "CRYPTO_PREVIOUS_MAPS")
    require(type(primary["members"]) is list and len(primary["members"]) == primary["memberCount"] > 0 and
        type(authority["members"]) is list and len(authority["members"]) == authority["memberCount"] > 0 and
        authority["destinationRootBefore"] == primary["destinationMetadata"][0] and
        authority["destinationBeforeMetadataSha256"] == O.digest(O.encoded({"metadata": primary["destinationMetadata"]})),
        "CRYPTO_PREVIOUS_MAP_LINKS")
    before = _snapshot(owner, "COPIED_PRIMARY_AND_AUTHORITY", destination)
    members = tuple((*primary["members"], *authority["members"]))
    require(_crypto_metadata(before) == authority["destinationMetadata"] and
        before.metadata[1:primary["memberCount"] + 1] == tuple((name, directory, tuple(identity), count, O.encoded(data))
            for name, directory, identity, count, data in primary["destinationMetadata"][1:]) and
        tuple(row[0] for row in before.metadata) == ("", *(_member_name(n) for n in range(len(members)))) and
        all(not row[1] for row in before.metadata[1:]), "CRYPTO_PREVIOUS_DESTINATION")
    for number, (item, node) in enumerate(zip(members, before.metadata[1:])):
        require(item["member"] == _member_name(number) and item["origin"] ==
            (ORIGINS[0] if number < primary["memberCount"] else ORIGINS[1]) and
            type(item["bytes"]) is int and item["bytes"] == node[3], "CRYPTO_PREVIOUS_MEMBER")
        _written_matches(O.encoded(item["destinationWriteMetadata"]), node, before.windows)
        reader, verify = _snapshot_reader(owner, before, item["member"])
        _consume(owner, reader, item["bytes"], item["sha256"], verify)
    require(sum(item["bytes"] for item in members) == authority["aggregateTotalBytes"], "CRYPTO_PREVIOUS_BYTES")
    return before, members


def _recipient_inventory(owner, work, public_raw):
    """Actual completed validation tree, not fabricated old PRIMARY pins."""
    source = _snapshot(owner, ORIGINS[2], work)
    nodes = {row[0]: row for row in source.metadata}
    windows = source.windows
    names = tuple(sorted(name for name in nodes if name and "/" not in name))
    operations = tuple(name for name in names if re.fullmatch(
        r"gpg-[0-9a-f]{32}" if windows else r"gpg-[a-z0-9_]+", name))
    results = tuple(name for name in names if re.fullmatch(r"recipient-validation-result-[0-9a-f]{32}\.json", name))
    require(len(operations) == (3 if windows else 2) and len(results) == (1 if windows else 0) and
        set(names) == {"recipient.asc", "recipient.gpg", "gnupg", "tmp", *operations, *results},
        "RECIPIENT_VALIDATION_ROOT_ROSTER")
    directory_names = ("", "gnupg", "tmp", *operations)
    require({name for name, node in nodes.items() if node[1]} == set(directory_names), "RECIPIENT_VALIDATION_DIRECTORIES")
    directories = []
    expected = {name: native.posix.MAX_KEY_BYTES for name in ("recipient.asc", "recipient.gpg")}
    expected.update({name: native.diagnostics.MAX_RECORD_BYTES for name in results})
    for directory in directory_names:
        prefix = directory + "/" if directory else ""
        members = tuple(sorted(name[len(prefix):] for name in nodes if name != directory and name.startswith(prefix) and
            "/" not in name[len(prefix):]))
        require(len(members) <= 32, "RECIPIENT_VALIDATION_DIRECTORY_CAP")
        if directory in ("gnupg", "tmp"):
            require(not windows or not members, "RECIPIENT_WINDOWS_HOME_NOT_EMPTY")
            require(all("secret" not in name.casefold() and "private" not in name.casefold() and
                name.casefold() != "secring.gpg" for name in members), "RECIPIENT_PRIVATE_MATERIAL_FORBIDDEN")
        elif directory:
            require(members == tuple(sorted(("stdout", "stderr") if windows else
                ("stdout", "stderr", "status", "process.json"))), "RECIPIENT_VALIDATION_OPERATION_ROSTER")
        directories.append({"relative": directory, "identity": list(nodes[directory][2]), "members": list(members)})
        if directory:
            for name in members:
                expected[directory + "/" + name] = (native.LIMIT if directory in ("gnupg", "tmp") or
                    name == "process.json" else native.posix.MAX_DIAGNOSTIC_BYTES)
    files = {name: row for name, row in nodes.items() if not row[1]}
    require(set(files) == set(expected) and (len(files) == 9 if windows else 10 <= len(files) <= 74),
        "RECIPIENT_VALIDATION_FILE_ROSTER")
    records, encodings, total = [], {}, 0
    for name in sorted(expected):
        node, maximum = files[name], expected[name]
        require(node[3] <= maximum, "RECIPIENT_VALIDATION_FILE_CAP")
        reader, verify = _snapshot_reader(owner, source, name)
        retain = name in ("recipient.asc", "recipient.gpg")
        returned = _consume(owner, reader, node[3], None, verify, retain=retain)
        if retain:
            encodings[name] = returned
        checksum = O.digest(returned) if retain else returned
        total += node[3]
        require(total <= N.CRYPTO_ORIGINALS_LIMIT, "RECIPIENT_VALIDATION_TOTAL_CAP")
        records.append({"relative": name, "maximum": maximum, "bytes": node[3], "sha256": checksum,
            "identity": list(node[2]), "provenance": "ACTUAL_SAME_CHILD_VALIDATION_ORIGINAL"})
    require(type(public_raw) is bytes and 0 < len(public_raw) <= native.posix.MAX_KEY_BYTES and
        encodings["recipient.asc"] == public_raw and native.posix._public_armor(public_raw) == encodings["recipient.gpg"],
        "RECIPIENT_PUBLIC_ONLY_ENCODINGS")
    _snapshot_current(owner, source, rescan=True)
    return source, {"schema": 1, "scope": "INITIAL_CUSTODY_SAME_CHILD_VALIDATION_ORIGINALS_V1",
        "root": str(work.path), "directories": directories, "files": records, "fileCount": len(records),
        "directoryCount": len(directories), "totalBytes": total, "outerChild": "STILL_LIVE",
        "exportSaveAuthority": False}


@dataclass(frozen=True, repr=False)
class _RecipientCopy:
    raw: bytes
    source: object
    before: object
    after: object
    members: tuple
    prior: tuple


def _copy_recipient(owner, destination, work, primary_raw, authority_raw, context_raw, start_raw,
        summary_raw, public_raw, check):
    require(type(owner) is _PrimaryOwner and callable(check), "RECIPIENT_COPY_OWNER")
    try:
        check()
        before, prior = _crypto_previous(owner, destination, primary_raw, authority_raw)
        source, inventory = _recipient_inventory(owner, work, public_raw)
        context, start, summary = canonical(context_raw, 65536), canonical(start_raw), canonical(summary_raw)
        require(context["scope"] == _CRYPTO_CONTEXT_SCOPE and start["scope"] == _CRYPTO_START_SCOPE and
            summary["scope"] == "INITIAL_CUSTODY_ACTUAL_RECIPIENT_RETURN_V1" and
            summary["contextSha256"] == O.digest(context_raw) and summary["startSha256"] == O.digest(start_raw) and
            summary["supplierReturned"] is True and summary["outerChild"] == "STILL_LIVE" and
            summary["recipient"]["key_sha256"] == O.digest(public_raw) and
            summary["recipient"]["work_identity"] == list(work.identity) and
            context["directories"]["public-crypto"] == list(work.identity), "RECIPIENT_COPY_ORIGINAL_BINDINGS")
        embedded = (("context.json", context_raw), ("start.json", start_raw), ("recipient-return.json", summary_raw))
        added_bytes = inventory["totalBytes"] + sum(len(raw) for _, raw in embedded)
        _aggregate(tuple(owner.snapshots), sum(row["bytes"] for row in prior) + added_bytes,
            len(prior) + len(inventory["files"]) + len(embedded) + 1)
        require(len({row[2] for row in (*before.metadata, *source.metadata)}) ==
            len(before.metadata) + len(source.metadata), "RECIPIENT_COPY_SOURCE_ALIAS")
        members = []
        for item in inventory["files"]:
            check()
            name, written = _copy_member(owner, destination, len(prior) + len(members), item["bytes"], item["sha256"],
                snapshot=source, name=item["relative"])
            members.append({"member": name, "origin": ORIGINS[2], "original": item["relative"],
                "originalMaximum": item["maximum"], "bytes": item["bytes"], "sha256": item["sha256"],
                "provenance": item["provenance"], "carrier": "INDEXED_DISK_ORIGINAL",
                "sourceCopyIdentity": item["identity"], "destinationWriteMetadata": O.parse(written)})
        for name, raw in embedded:
            check()
            target, written = _copy_member(owner, destination, len(prior) + len(members), len(raw), O.digest(raw), embedded=raw)
            members.append({"member": target, "origin": ORIGINS[2], "original": name,
                "originalMaximum": 65536 if name == "context.json" else native.LIMIT,
                "bytes": len(raw), "sha256": O.digest(raw), "provenance": "ACTUAL_PRE_EXPORT_RETURNED_BYTES",
                "carrier": "EMBEDDED_NOT_DISK_ORIGINAL", "sourceCopyIdentity": None,
                "destinationWriteMetadata": O.parse(written)})
        after = _snapshot(owner, "COPIED_THREE_ORIGIN_DATA", destination)
        require(after.pin == before.pin and after.metadata[1:len(prior) + 1] == before.metadata[1:] and
            tuple(row[0] for row in after.metadata) == ("", *(_member_name(n) for n in range(len(prior) + len(members)))) and
            all(not row[1] for row in after.metadata[1:]), "RECIPIENT_COPY_APPEND_TRANSITION")
        for item, node in zip((*prior, *members), after.metadata[1:]):
            check()
            _written_matches(O.encoded(item["destinationWriteMetadata"]), node, after.windows)
            reader, verify = _snapshot_reader(owner, after, item["member"])
            _consume(owner, reader, item["bytes"], item["sha256"], verify)
        _snapshot_current(owner, source, rescan=True)
        _snapshot_current(owner, after, rescan=True)
        _aggregate(tuple(owner.snapshots))
        raw = O.encoded({"schema": 1, "scope": "INITIAL_CUSTODY_RECIPIENT_COPY_V1", "origin": ORIGINS[2],
            "primaryCopySha256": O.digest(primary_raw), "authorityCopySha256": O.digest(authority_raw),
            "validationInventory": inventory, "recipientReturnSha256": O.digest(summary_raw),
            "members": members, "sourceMetadata": _crypto_metadata(source), "originalDirectories": inventory["directories"],
            "destination": str(destination.path), "destinationIdentity": list(after.pin),
            "destinationBeforeMetadataSha256": O.digest(O.encoded({"metadata": _crypto_metadata(before)})),
            "destinationRootBefore": _crypto_metadata(before)[0], "destinationMetadata": _crypto_metadata(after),
            "previousMemberCount": len(prior), "memberCount": len(members), "totalBytes": added_bytes,
            "aggregateMemberCount": len(prior) + len(members),
            "aggregateTotalBytes": sum(row["bytes"] for row in prior) + added_bytes,
            "nextOrdinal": len(prior) + len(members), "outerChild": "STILL_LIVE",
            "freeze": "NOT_FINAL_THREE_ORIGIN_FREEZE", "exportSaveAuthority": False})
        canonical(raw)
        check()
        return _RecipientCopy(raw, source, before, after, tuple(members), prior)
    except BaseException as error:
        raise owner.remember(error)


def _write_custody_map(owner, destination, name, raw):
    """Only the four fixed non-overwriting manifest members, never an arbitrary path."""
    require(name in ("primary-map.json", "authority-map.json", "recipient-map.json", "copy-map.json"),
        "CRYPTO_FIXED_MAP_NAME")
    canonical(raw, 65536 if name == "copy-map.json" else native.LIMIT)
    reader = owner.acquire("embedded-reader", lambda: io.BytesIO(raw))
    end = owner.guard()
    writer = owner.acquire("writer", lambda: destination.create_file(name, max_bytes=len(raw), deadline=end))
    def verify():
        require(type(reader) is io.BytesIO and reader.getvalue() == raw, "CRYPTO_MAP_ORIGINAL_BYTES")
    checksum, written = _consume(owner, reader, len(raw), O.digest(raw), verify, writer=writer)
    require(checksum == O.digest(raw) and _read_private(owner, destination, name, len(raw)) == raw, "CRYPTO_MAP_READBACK")
    return written


@dataclass(frozen=True, repr=False)
class _CryptoFreeze:
    snapshot: object
    maps: tuple
    copied: bytes
    metadata_sha256: str
    members: tuple


def _freeze_custody_copy(owner, destination, primary_raw, authority_raw, recipient_copy, check):
    require(type(owner) is _PrimaryOwner and type(recipient_copy) is _RecipientCopy and callable(check), "CRYPTO_FREEZE_OWNER")
    try:
        primary, authority, recipient = canonical(primary_raw), canonical(authority_raw), canonical(recipient_copy.raw)
        require(recipient["primaryCopySha256"] == O.digest(primary_raw) and
            recipient["authorityCopySha256"] == O.digest(authority_raw) and
            recipient["destinationMetadata"] == _crypto_metadata(recipient_copy.after), "CRYPTO_FREEZE_ORIGINS")
        members = (*recipient_copy.prior, *recipient_copy.members)
        maps = (("primary-map.json", primary_raw), ("authority-map.json", authority_raw),
            ("recipient-map.json", recipient_copy.raw))
        originals = (primary, authority, recipient)
        require(tuple(value["origin"] for value in originals) == ORIGINS and
            sum(value["memberCount"] for value in originals) == len(members) and
            all(value["memberCount"] == len(value["members"]) for value in originals), "CRYPTO_FREEZE_MEMBER_COUNTS")
        data_bytes = sum(row["bytes"] for row in members)
        require(sum(value["totalBytes"] for value in originals) == data_bytes, "CRYPTO_FREEZE_DATA_BYTES")
        combined = O.encoded({"schema": 1, "scope": "INITIAL_CUSTODY_THREE_ORIGIN_COPY_MAP_V1",
            "origins": {origin: {"mapFile": name, "bytes": len(raw), "sha256": O.digest(raw),
                "memberCount": value["memberCount"], "totalBytes": value["totalBytes"]}
                for origin, (name, raw), value in zip(ORIGINS, maps, originals)},
            "dataMemberCount": len(members), "dataTotalBytes": data_bytes,
            "payloadMembersExcludingThisMap": len(members) + 3,
            "payloadBytesExcludingThisMap": data_bytes + sum(len(raw) for _, raw in maps),
            "destination": str(destination.path), "destinationIdentity": list(destination.identity),
            "contentState": "COMPLETE_PRE_EXPORT_CONTENT_DECLARATION", "exportSaveAuthority": False})
        canonical(combined, 65536)
        maps = (*maps, ("copy-map.json", combined))
        _aggregate(tuple(owner.snapshots), sum(len(raw) for _, raw in maps), 4)
        check()
        _snapshot_current(owner, recipient_copy.after, rescan=True)
        written = {}
        for name, raw in maps:
            written[name] = _write_custody_map(owner, destination, name, raw)
            check()
        _snapshot_current(owner, recipient_copy.source, rescan=True)
        # The completed validation cut is now immutable history. Close every
        # source reader/Snapshot/writer before the ONE completed payload freeze;
        # only the destination directory remains for its new read-only snapshot.
        for _row, _label, resource, attempted, closed in reversed(owner.rows):
            if resource is destination:
                continue
            if not attempted:
                owner.close_one(resource)
            else:
                require(closed, "CRYPTO_PRE_EXPORT_CLOSE_UNKNOWN")
        require(all(resource is destination or attempted and closed
            for _row, _label, resource, attempted, closed in owner.rows), "CRYPTO_VALIDATION_NOT_RETIRED")
        complete = _snapshot(owner, "COMPLETED_THREE_ORIGIN_FREEZE", destination)
        require(complete.pin == recipient_copy.after.pin and
            tuple(row[0] for row in complete.metadata) == tuple(sorted(("", *(row["member"] for row in members),
                *(name for name, _ in maps)))) and all(not row[1] for row in complete.metadata[1:]),
            "CRYPTO_COMPLETE_FREEZE_ROSTER")
        nodes = {row[0]: row for row in complete.metadata}
        for item, original in zip(members, recipient_copy.after.metadata[1:]):
            node = nodes[item["member"]]
            require(node == original, "CRYPTO_FINAL_DATA_CHANGED")
            _written_matches(O.encoded(item["destinationWriteMetadata"]), node, complete.windows)
            reader, verify = _snapshot_reader(owner, complete, item["member"])
            _consume(owner, reader, item["bytes"], item["sha256"], verify)
        for name, raw in maps:
            _written_matches(written[name], nodes[name], complete.windows)
            reader, verify = _snapshot_reader(owner, complete, name)
            require(_consume(owner, reader, len(raw), O.digest(raw), verify, retain=True) == raw, "CRYPTO_FINAL_MAP_CHANGED")
        _aggregate(tuple(owner.snapshots))
        _snapshot_current(owner, complete, rescan=True)
        final_bytes = data_bytes + sum(len(raw) for _, raw in maps)
        require(sum(row[3] for row in complete.metadata if not row[1]) == final_bytes and
            len(complete.metadata) == len(members) + 5, "CRYPTO_FINAL_PAYLOAD_COUNTS")
        copied = O.encoded({"mapSha256": O.digest(combined), "memberCount": len(members) + 4,
            "totalBytes": final_bytes, "origins": {origin: O.digest(raw)
                for origin, (_name, raw) in zip(ORIGINS, maps[:3])}})
        check()
        return _CryptoFreeze(complete, maps, copied, O.digest(O.encoded({"metadata": _crypto_metadata(complete)})), tuple(members))
    except BaseException as error:
        raise owner.remember(error)


def _crypto_directory_paths(kind):
    custody = _paths(kind)[2]
    returned = custody / "returned"
    return {"custody": custody, "returned": returned, "control-home": returned / "control-home",
        "temporary": returned / "temporary", "crypto-service": returned / "crypto-service",
        "copied-evidence": custody / "copied-evidence", "public-crypto": custody / "public-crypto",
        "export-output": custody / "export-output"}


def _crypto_open_directories(owner, context):
    paths, directories = _crypto_directory_paths(context["kind"]), {}
    role = context["observed"]["role"]
    for name in _CRYPTO_DIRECTORIES:
        if name == "export-output" and role != "windows-x64":
            require(not os.path.lexists(paths[name]), "CRYPTO_POSIX_OUTPUT_ALREADY_EXISTS")
            continue
        directory = _private(owner, paths[name]) if type(owner) is _PrimaryOwner else owner.open(paths[name])
        pin = tuple(native.directory_identity(context["directories"][name], role))
        require(tuple(directory.identity) == pin and directory.path == paths[name], "CRYPTO_DIRECTORY_PIN_CHANGED")
        directories[name] = directory
    return directories


def _crypto_fixed_readback(owner, directories, context_raw, start_raw, raws):
    """Read only fixed immutable inputs, never the evolving service directory."""
    def read(directory, name, maximum):
        if type(owner) is _PrimaryOwner:
            return _read_private(owner, directory, name, maximum)
        return owner.read(directory, name, maximum)
    require(read(directories["returned"], "context.json", 65536) == context_raw and
        read(directories["crypto-service"], "start.json", native.LIMIT) == start_raw, "CRYPTO_FRAME_READBACK")
    for name, maximum in _CRYPTO_INPUT_LIMITS.items():
        require(read(directories["returned"], name, maximum) == raws[name], "CRYPTO_INPUT_READBACK")
    context = canonical(context_raw, 65536)
    for name, directory in directories.items():
        directory.verify()
        require(tuple(directory.identity) == tuple(context["directories"][name]) and
            directory.path == _crypto_directory_paths(context["kind"])[name], "CRYPTO_READBACK_DIRECTORY_CHANGED")


def _crypto_recipient_value(pin):
    E._recipient_current(pin)
    recipient = pin[0]
    value = {name: getattr(recipient, name) for name in
        ("fingerprint", "encryption_fingerprint", "expires_at", "key_sha256")}
    value.update(work_identity=list(recipient.work_identity), executable=str(recipient.executable))
    if os.name == "nt":
        value.update(work=str(recipient.work.path), executable_sha256=recipient.executable_sha256, job_id=recipient.job_id)
    else:
        value.update(work_dir=str(recipient.work_dir), home=str(recipient.home))
    return value


def _crypto_recipient_closed(pin):
    """Original immutable fields after real close, not a live-owner assertion."""
    recipient, kind, dictionary, names, values, paths, directories = pin
    require(type(recipient) is kind and recipient.__dict__ is dictionary and set(dictionary) == set(names),
        "CRYPTO_CLOSED_RECIPIENT_CHANGED")
    for name, saved in zip(names, values):
        actual = dictionary[name]
        require(type(actual) is type(saved) and (actual == saved if type(saved) in (str, int) else actual is saved),
            "CRYPTO_CLOSED_RECIPIENT_CHANGED")
    for directory, original, path, identity in directories:
        require(type(directory) is E.windows.files.PrivateDirectory and directory.__dict__ is original and
            directory.path is path and directory.identity is identity and directory._closed is True,
            "CRYPTO_CLOSED_RECIPIENT_DIRECTORY_CHANGED")
    E._paths_current(paths)


def _crypto_export_timeout(clock):
    require(type(clock) is _CustodyChildClock, "CRYPTO_EXPORT_CLOCK")
    local = local_value(time.monotonic())
    now = clock.now()
    remaining = min(clock.local_end - local, (clock.work - now) / O.NS)
    # The Windows backend's separate finish30 is charged to this same end.
    finish = 30 if clock.clock.role == "windows-x64" else 0
    seconds = math.floor(min(240, remaining - finish))
    require(type(seconds) is int and seconds > 0, "CRYPTO_EXPORT_NO_REMAINING_WORK")
    return seconds


def _crypto_child_work(clock, context_raw, start_raw, raws, minimum, metadata_close, metadata_last):
    """Same-child actual Recipient, three-origin copy, one export and real close."""
    context, start = canonical(context_raw, 65536), canonical(start_raw)
    anchor = clock._view()
    require(anchor.phase == "OPERATIVE" and anchor.operative is None, "CRYPTO_CHILD_OPERATIVE_PHASE")
    first, _local, boot, cancelled = anchor.binding
    original, fresh, policy = _crypto_inputs(context, raws)
    frames = N._history_graph(context, start, raws, original.__dict__, fresh.__dict__, policy, first)
    owner = file_owner = pin = recipient_copy_dictionary = recipient_copy_graph = None
    copied_dictionary = copied_graph = None
    failure = result_raw = copied = recipient_copy = manifest_raw = None
    try:
        owner = _CustodyOwner(clock.local_end, clock, first=first, cancelled=cancelled)
        clock.attach_operative(owner)
        directories = _crypto_open_directories(owner, context)
        _crypto_fixed_readback(owner, directories, context_raw, start_raw, raws)
        work, evidence = directories["public-crypto"], directories["copied-evidence"]
        output_path = _crypto_directory_paths(context["kind"])["export-output"]
        output = directories.get("export-output") if os.name == "nt" else output_path
        require(native._initializer_names(owner, work) == (), "CRYPTO_VALIDATION_WORK_NOT_EMPTY")
        validating = clock.now()
        if os.name == "nt":
            recipient = native.diagnostics.validate_recipient(raws["recipient-public.asc"], policy["recipient"]["fingerprint"],
                work, job_id=context["job"])
        else:
            recipient = native.posix.validate_recipient(directories["returned"].path / "recipient-public.asc",
                policy["recipient"]["fingerprint"], work.path)
        # FIRST action after the supplier returns. This live object never comes
        # from a summary file/dictionary, nor from the retired primary child.
        pin = E._recipient_pin(recipient, os.name == "nt", evidence if os.name == "nt" else evidence.path, output)
        returned = clock.now()
        E._recipient_current(pin)
        require(recipient.work_identity == work.identity and recipient.fingerprint == policy["recipient"]["fingerprint"] and
            recipient.key_sha256 == policy["recipient"]["sha256"] and policy["expiresAt"] <= recipient.expires_at and
            ((os.name == "nt" and recipient.work is work and recipient.job_id == context["job"]) or
             (os.name != "nt" and recipient.work_dir == work.path and recipient.home == work.path / "gnupg")),
            "CRYPTO_ACTUAL_RECIPIENT_RETURN")
        summary_raw = O.encoded({"schema": 1, "scope": "INITIAL_CUSTODY_ACTUAL_RECIPIENT_RETURN_V1",
            "contextSha256": O.digest(context_raw), "startSha256": O.digest(start_raw), "invocation": start["invocation"],
            "clock": O.clock_value(first.clock), "bootDigest": boot, "launchMinimumNs": minimum,
            "beganNs": first.nanoseconds, "metadataLastNs": metadata_last, "validationStartedNs": validating,
            "validationReturnedNs": returned, "recipient": _crypto_recipient_value(pin),
            "supplierReturned": True, "outerChild": "STILL_LIVE", "exportSaveAuthority": False})
        canonical(summary_raw)
        raw_owner = native.Owner(clock.local_end, clock, first=first, cancelled=cancelled)
        file_owner = _PrimaryOwner(raw_owner)
        destination = _private(file_owner, evidence.path)
        validation_source = _private(file_owner, work.path)

        def copy_returns_current():
            # Callback-free original-return checks remain valid after the live
            # Recipient/work owners close; no retired owner is reopened here.
            if recipient_copy is not None:
                require(type(recipient_copy) is _RecipientCopy and recipient_copy.__dict__ is recipient_copy_dictionary,
                    "CRYPTO_RECIPIENT_COPY_RETURN_CHANGED")
                N._check_history(recipient_copy_graph)
            if copied is not None:
                require(type(copied) is _CryptoFreeze and copied.__dict__ is copied_dictionary, "CRYPTO_FREEZE_RETURN_CHANGED")
                N._check_history(copied_graph)

        def passive():
            N._check_history(frames)
            clock._view()
            owner.check()
            E._recipient_current(pin)
            require(not any(name in os.environ for name in _CREDENTIAL_NAMES), "CRYPTO_CHILD_CREDENTIAL_CHANGED")
            require(destination.path == evidence.path and destination.identity == evidence.identity and
                recipient.work_identity == work.identity, "CRYPTO_CHILD_ORIGINAL_ROOTS")
            copy_returns_current()

        def before_export():
            passive()
            clock.now()
            _crypto_fixed_readback(owner, directories, context_raw, start_raw, raws)
            passive()

        before_export()
        recipient_copy = _copy_recipient(file_owner, destination, validation_source, raws["primary-map.json"],
            raws["authority-map.json"], context_raw, start_raw, summary_raw, raws["recipient-public.asc"], passive)
        recipient_copy_dictionary = recipient_copy.__dict__
        recipient_copy_graph = N._history_graph(recipient_copy_dictionary)
        copied = _freeze_custody_copy(file_owner, destination, raws["primary-map.json"], raws["authority-map.json"],
            recipient_copy, passive)
        copied_dictionary = copied.__dict__
        copied_graph = N._history_graph(copied.__dict__)
        output_owner = output if os.name == "nt" else None

        def export_check():
            before_export()
            require(type(copied) is _CryptoFreeze and copied.__dict__ is copied_dictionary, "CRYPTO_FREEZE_RETURN_CHANGED")
            N._check_history(copied_graph)
            _snapshot_current(file_owner, copied.snapshot, rescan=True)
            current = int(time.time())
            require(policy["notBefore"] <= context["observed"]["firstUseAt"] <= current < policy["expiresAt"] <=
                recipient.expires_at, "CRYPTO_LOCAL_POLICY_EXPIRED")
            # Validation-only work roster is intentionally NOT reasserted here:
            # export creates additional backend records outside the frozen tree.

        def read_manifest():
            nonlocal output_owner
            if output_owner is None:
                output_owner = owner.open(output_path)
            return owner.read(output_owner, native.posix.MANIFEST, E.MANIFEST_LIMIT)

        timeout_seconds = _crypto_export_timeout(clock)
        manifest_raw = E.export_encrypted(evidence if os.name == "nt" else evidence.path, output, recipient,
            kind=context["kind"], selection=context["observed"]["inputs"]["selection"],
            source_commit=context["observed"]["source"]["commit"], source_tree=context["observed"]["source"]["tree"],
            original_match=original, fresh_match=fresh, event_raw=raws["event.json"], policy_raw=raws["candidate-policy.json"],
            primary=context["primary"], copied=canonical(copied.copied),
            authority={name: context["authority"][name] for name in E.AUTHORITY_FIELDS}, check=export_check,
            read_manifest=read_manifest, timeout_seconds=timeout_seconds, max_bytes=MAX_BYTES, max_members=MAX_MEMBERS)
        # Capture the actual adapter bytes before any callback or file readback.
        require(type(manifest_raw) is bytes and 0 < len(manifest_raw) <= E.MANIFEST_LIMIT, "CRYPTO_EXPORT_BYTE_RETURN")
        manifest = canonical(manifest_raw, E.MANIFEST_LIMIT)
        exported = clock.now()
        export_check()
        require(read_manifest() == manifest_raw and manifest["copy"] == canonical(copied.copied) and
            manifest["primary"] == context["primary"] and manifest["source"] == context["observed"]["source"],
            "CRYPTO_EXPORT_RETURN_CHANGED")
        result_raw = O.encoded({"schema": 1, "scope": _CRYPTO_CHILD_SCOPE,
            "contextSha256": O.digest(context_raw), "startSha256": O.digest(start_raw), "invocation": start["invocation"],
            "clock": O.clock_value(first.clock), "bootDigest": boot, "launchMinimumNs": minimum,
            "beganNs": first.nanoseconds, "metadataLastNs": metadata_last, "metadataCloseSha256": O.digest(metadata_close),
            "validationStartedNs": validating, "validationReturnedNs": returned, "exportedNs": exported,
            "recipientReturnSha256": O.digest(summary_raw), "recipient": manifest["recipient"],
            "copy": canonical(copied.copied), "freezeMetadataSha256": copied.metadata_sha256,
            "sourceMetadataSha256": {origin: O.digest(O.encoded({"metadata": canonical(raw)["sourceMetadata"]}))
                for origin, raw in zip(ORIGINS, (raws["primary-map.json"], raws["authority-map.json"], recipient_copy.raw))},
            "manifest": {"bytes": len(manifest_raw), "sha256": O.digest(manifest_raw),
                "base64": base64.b64encode(manifest_raw).decode("ascii")},
            "retirement": "PENDING_CHILD_CLOSE", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        canonical(result_raw)
        require(owner.write(directories["returned"], "crypto-child-result.json", result_raw) == result_raw,
            "CRYPTO_CHILD_RESULT_WRITE")
        export_check()
        file_close = file_owner.finish()
        passive()
        before_close = clock.now()
        owner.freeze()
    except BaseException as error:
        failure = error
        if file_owner is not None:
            failure = file_owner.remember(error)
        if owner is not None:
            owner.error("crypto-child", failure)
            failure = owner._anchor().failure
    finally:
        if file_owner is not None and not file_owner.finished and not file_owner.owner.unknown:
            try:
                file_owner.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
                if owner is not None:
                    owner.error("crypto-child-files-close", error, unknown=file_owner.owner.unknown)
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                owner.error("crypto-child-owner-close", error)
            if failure is None and owner._anchor().failure is not None:
                failure = owner._anchor().failure
    if failure is not None:
        raise failure
    require(result_raw is not None and pin is not None and file_owner.finished and file_owner.failure is None,
        "CRYPTO_CHILD_INCOMPLETE")
    closed_owner = owner.known()
    file_owner.structural()
    copy_returns_current()
    _crypto_recipient_closed(pin)
    N._check_history(frames)
    closed = clock.now(minimum=before_close)
    _crypto_recipient_closed(pin)
    copy_returns_current()
    require(all(attempted and ended for _row, _label, _resource, attempted, ended in file_owner.rows),
        "CRYPTO_CHILD_FILE_CLOSE_UNKNOWN")
    close_summary = O.encoded({"fileOwner": canonical(file_close), "operativeResources": [
        {"ordinal": number, "label": label, "closeAttempted": attempted, "closed": ended}
        for number, (_row, label, _resource, attempted, ended) in enumerate(closed_owner.rows)]})
    ack = {"schema": 1, "scope": _CRYPTO_ACK_SCOPE, "invocation": start["invocation"],
        "terminalSha256": O.digest(result_raw), "clock": O.clock_value(first.clock), "closedNs": closed,
        "ownerCloseSha256": O.digest(close_summary), "fileResourceCount": len(file_owner.rows),
        "operativeResourceCount": len(closed_owner.rows)}
    copy_returns_current()
    return ack, clock, clock.work


def custody_crypto_child(context_hash, minimum, cancelled):
    """Fixed child entry; metadata closes before the one crypto cap binding."""
    metadata = clock = None
    failure = None
    try:
        local = local_value(time.monotonic())
        first = O.clocks.observe()
        first_graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        require(first.nanoseconds >= O.integer(minimum), "CRYPTO_CHILD_PRECEDES_LAUNCH")
        boot = digest(C.boot_digest(first.clock.role))
        N._check_history(first_graph)
        digest(context_hash)
        require(callable(cancelled) and not any(name in os.environ for name in _CREDENTIAL_NAMES), "CRYPTO_CHILD_TOKEN_FREE")
        clock = _CustodyChildClock(first, local, boot, cancelled)
        metadata = _PrimaryOwner(native.Owner(clock.local_end, clock, first=first, cancelled=cancelled))
        clock.attach_metadata(metadata)
        kind, _primary_path = N.location()
        path = _paths(kind)[2] / "returned"
        private = _private(metadata, path)
        context_raw = _read_private(metadata, private, "context.json", 65536)
        require(O.digest(context_raw) == context_hash, "CRYPTO_CHILD_CONTEXT_HASH")
        context, event = _crypto_context(context_raw, first, boot)
        directories = _crypto_open_directories(metadata, context)
        require(private.identity == directories["returned"].identity, "CRYPTO_METADATA_DIRECTORY_CHANGED")
        start_raw = _read_private(metadata, directories["crypto-service"], "start.json", native.LIMIT)
        start = canonical(start_raw)
        inherited = Q._inherited_context()
        _crypto_start(context_raw, context, start, first, boot, event, inherited)
        require(start["startedNs"] <= minimum <= first.nanoseconds, "CRYPTO_ACTUAL_LAUNCH_MINIMUM")
        raws = {name: _read_private(metadata, private, name, maximum) for name, maximum in _CRYPTO_INPUT_LIMITS.items()}
        original, expected, policy = _crypto_inputs(context, raws)
        frame_graph = N._history_graph(context, start, raws, expected.__dict__, original.__dict__, policy, inherited, first)
        _crypto_fixed_readback(metadata, directories, context_raw, start_raw, raws)
        metadata_close = metadata.finish()
        metadata_last = clock.now()
        N._check_history(frame_graph)
        clock.bind_crypto(context_raw, context, start_raw, start, expected, event, inherited)
        return _crypto_child_work(clock, context_raw, start_raw, raws, minimum, metadata_close, metadata_last)
    except BaseException as error:
        failure = error
    finally:
        if metadata is not None and not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
    if failure is not None:
        raise failure


def _crypto_phase_bytes(context_raw, phase, clock):
    """Fixed byte consistency, used only AFTER a registered actual native return."""
    context = canonical(context_raw, 65536)
    records = dict(phase.records)
    require(type(phase) is _CryptoNativeReturn and phase.context == context_raw and
        len(phase.records) == len(records) and set(records) == native.PHASE_FILES and
        all(type(raw) is bytes for raw in records.values()), "CRYPTO_PHASE_BYTES")
    start = _crypto_start_fields(context_raw, context, canonical(records["start.json"]), clock)
    require(phase.phase == (start["startedNs"], start["workEndNs"], start["finalEndNs"]), "CRYPTO_PHASE_ORIGINAL_CAPS")
    row = fields(canonical(records["result.json"]), " ".join(native.TERMINAL_FIELDS), "CRYPTO_TERMINAL_FIELDS")
    birth = fields(canonical(records["native-start.json"]), "ownership leader preparerIdentity observedNs", "CRYPTO_BIRTH_FIELDS")
    changed = {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}
    _same({name: row[name] for name in start if name not in changed},
        {name: start[name] for name in start if name not in changed}, "CRYPTO_TERMINAL_START")
    require(type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is True and
        row["scopeAttempted"] is True and row["scopeCloseAttempted"] is True and row["scopeClosed"] is True and
        row["retirement"] == "KNOWN" and row["survivors"] == [] and row["errors"] == [] and records["stderr.log"] == b"" and
        row["nativeStartSha256"] == O.digest(records["native-start.json"]) and
        row["baselineSha256"] == O.digest(records["baseline.json"]) and row["leader"] == birth["leader"],
        "CRYPTO_NATIVE_RETURN")
    argv = _custody_crypto_command(O.digest(context_raw), O.integer(row["launchMinimumNs"], start["startedNs"]))
    _same(row["launchArgv"], argv, "CRYPTO_EXECUTED_COMMAND")
    native.native_record(row["ownership"], start, row["leader"], argv)
    native.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    _same(birth["ownership"]["launches"], row["ownership"]["launches"], "CRYPTO_NATIVE_BIRTH")
    preparer = native.closed_lifetime(row["preparerIdentity"], clock.role)
    require(preparer == native.closed_lifetime(birth["preparerIdentity"], clock.role) and
        preparer["pid"] != row["leader"]["pid"], "CRYPTO_PREPARER")
    baseline = native.baseline_record(records["baseline.json"], clock.role)
    if baseline["baseline"] is not None:
        leader = native.lifetime(row["leader"], clock.role)
        require(list(leader[:4] if clock.role.startswith("macos-") else leader) not in baseline["baseline"],
            "CRYPTO_PREEXISTING_LEADER")
    _same(row["captureOutcomes"], {name: {key: True for key in
        ("synced", "verified", "closeAttempted", "closed", "readback")} for name in ("stdout", "stderr")},
        "CRYPTO_CAPTURE_CLOSE")
    _same(row["captures"], {name: {"sha256": O.digest(records[name + ".log"]),
        "bytes": len(records[name + ".log"])} for name in ("stdout", "stderr")}, "CRYPTO_CAPTURE_BYTES")
    child = fields(canonical(phase.child), "schema scope contextSha256 startSha256 invocation clock bootDigest "
        "launchMinimumNs beganNs metadataLastNs metadataCloseSha256 validationStartedNs validationReturnedNs exportedNs "
        "recipientReturnSha256 recipient copy freezeMetadataSha256 sourceMetadataSha256 manifest retirement budgetAcceptance exportSaveAuthority",
        "CRYPTO_CHILD_FIELDS")
    ack = fields(canonical(records["stdout.log"]), "schema scope invocation terminalSha256 clock closedNs "
        "ownerCloseSha256 fileResourceCount operativeResourceCount", "CRYPTO_ACK_FIELDS")
    require(type(child["schema"]) is int and child["schema"] == 1 and child["scope"] == _CRYPTO_CHILD_SCOPE and
        child["contextSha256"] == O.digest(context_raw) and child["startSha256"] == O.digest(records["start.json"]) and
        child["invocation"] == start["invocation"] and child["clock"] == O.clock_value(clock) and
        child["bootDigest"] == context["window"]["originalBootDigest"] and child["launchMinimumNs"] == row["launchMinimumNs"] and
        child["retirement"] == "PENDING_CHILD_CLOSE" and child["budgetAcceptance"] == "NOT_ADMITTED" and
        child["exportSaveAuthority"] is False and type(ack["schema"]) is int and ack["schema"] == 1 and
        ack["scope"] == _CRYPTO_ACK_SCOPE and ack["invocation"] == start["invocation"] and
        ack["terminalSha256"] == O.digest(phase.child) and ack["clock"] == O.clock_value(clock), "CRYPTO_CHILD_ACK")
    for name in ("metadataCloseSha256", "recipientReturnSha256", "freezeMetadataSha256"):
        digest(child[name])
    fields(child["sourceMetadataSha256"], " ".join(ORIGINS), "CRYPTO_SOURCE_METADATA_HASHES")
    for value in child["sourceMetadataSha256"].values():
        digest(value)
    copied = fields(child["copy"], " ".join(E.COPY_FIELDS), "CRYPTO_COPY_FIELDS")
    fields(copied["origins"], " ".join(ORIGINS), "CRYPTO_COPY_ORIGINS")
    digest(copied["mapSha256"])
    for value in copied["origins"].values():
        digest(value)
    require(len(set(copied["origins"].values())) == len(ORIGINS) and
        type(copied["memberCount"]) is int and 0 < copied["memberCount"] < MAX_MEMBERS and
        type(copied["totalBytes"]) is int and 0 < copied["totalBytes"] <= MAX_BYTES,
        "CRYPTO_COPY_BOUNDS")  # The unchanged aggregate also counts the root.
    digest(ack["ownerCloseSha256"])
    require(all(type(ack[name]) is int and 0 < ack[name] <= MAX_MEMBERS
        for name in ("fileResourceCount", "operativeResourceCount")), "CRYPTO_CHILD_CLOSE_COUNTS")
    ordered = [row["launchMinimumNs"], *(child[name] for name in ("beganNs", "metadataLastNs", "validationStartedNs",
        "validationReturnedNs", "exportedNs")), ack["closedNs"], row["completedNs"], row["finalizedNs"]]
    require(all(type(value) is int and O.integer(value) == value for value in ordered) and ordered == sorted(ordered) and
        start["startedNs"] <= ordered[0] and ack["closedNs"] < min(start["workEndNs"], child["beganNs"] + 210 * O.NS) and
        row["completedNs"] < start["workEndNs"] and row["finalizedNs"] < start["finalEndNs"] and
        row["launchMinimumNs"] <= O.integer(birth["observedNs"]) <= row["completedNs"], "CRYPTO_ORIGINAL_CHRONOLOGY")
    exported = fields(child["manifest"], "bytes sha256 base64", "CRYPTO_MANIFEST_FIELDS")
    require(type(exported["bytes"]) is int and 0 < exported["bytes"] <= E.MANIFEST_LIMIT and
        type(exported["base64"]) is str and len(exported["base64"]) <= 4 * ((E.MANIFEST_LIMIT + 2) // 3),
        "CRYPTO_MANIFEST_BOUNDS")
    try:
        manifest_raw = base64.b64decode(exported["base64"], validate=True)
    except (ValueError, TypeError):
        raise O.OriginError("INITIAL_CUSTODY_CRYPTO_MANIFEST_ENCODING") from None
    manifest = canonical(manifest_raw, E.MANIFEST_LIMIT)
    require(base64.b64encode(manifest_raw).decode("ascii") == exported["base64"] and
        len(manifest_raw) == exported["bytes"] and O.digest(manifest_raw) == digest(exported["sha256"]) and
        manifest["schema"] == 4 and manifest["scope"] == E.SCOPE and manifest["kind"] == context["kind"] and
        manifest["source"] == context["observed"]["source"] and manifest["primary"] == context["primary"] and
        manifest["copy"] == child["copy"] and manifest["recipient"] == child["recipient"] and
        manifest["initialRecipient"]["matchSha256"] == context["authority"]["matchSha256"] and
        manifest["initialRecipient"]["freshReturnSha256"] == context["authority"]["returnSha256"] and
        manifest["productiveAuthority"] is False and manifest["cacheAuthority"] is False and
        manifest["exportSaveAuthority"] is False and manifest["budgetAcceptance"] == "NOT_ADMITTED",
        "CRYPTO_ORIGINAL_MANIFEST")
    return start, row, child, ack, manifest_raw


def _checked_crypto_native(phase, owner, window):
    saved = _CRYPTO_NATIVE_RETURNS.get(id(phase))
    require(type(phase) is _CryptoNativeReturn and type(saved) is tuple and len(saved) == 2, "CRYPTO_NOT_ORIGINAL_NATIVE_RETURN")
    original, graph = saved
    require(original[0] is phase and original[1] is owner and original[2] is window and
        owner.__dict__ is original[3] and owner._anchor() is original[4] and owner.phase_originals is phase and
        phase.records is original[10] and phase.child == original[11] and phase.phase is original[12] and
        phase.__dict__ is original[13],
        "CRYPTO_NATIVE_RETURN_CHANGED")
    N._check_history(graph)
    anchor = owner.check()
    require(not anchor.unknown and anchor.failure is None and not anchor.phase_active and
        anchor.phase[:3] == phase.phase and owner.local_end == anchor.binding[3], "CRYPTO_NATIVE_OWNER_CHANGED")
    for resource, label in zip(original[5:8], ("native-scope", "stdout", "stderr")):
        require(any(actual is resource and name == label and attempted and closed
            for _row, name, actual, attempted, closed in anchor.rows), "CRYPTO_NATIVE_RESOURCE_CLOSE_CHANGED")
    return _crypto_phase_bytes(phase.context, phase, window.clock)


@dataclass(frozen=True, repr=False)
class _ClosedCrypto:
    context: bytes
    phase: object
    manifest: bytes
    parent_close: bytes


def custody_crypto(primary_result, authority_result):
    """Actual known-close parent return only; no outward custody Step success."""
    require("fixed" not in _CRYPTO_ATTEMPTS, "CRYPTO_PARENT_REUSE")
    attempt = {"state": "STARTED", "primary": primary_result, "authority": authority_result,
        "failure": None, "return": None, "readClaimed": False, "reader": None}
    _CRYPTO_ATTEMPTS["fixed"] = attempt
    owner = copy_owner = phase = result = None
    failure = None
    try:
        window, primary, history_raw, primary_raw, historical = checked_primary(primary_result)
        authority_window, fresh, captured, authority_raw, inventory_raw, originals = checked_custody_authority(authority_result, primary_result)
        require(authority_window is window and not any(name in os.environ for name in _CREDENTIAL_NAMES), "CRYPTO_PARENT_ORIGINAL_WINDOW")
        first, _local, _boot, _limits, _ends, _locals, cancelled = window._view().binding
        history, source_files = canonical(history_raw), dict(historical)
        frame_raw = _custody_authority_window(window)
        paths = _crypto_directory_paths(primary.kind)
        owner_before = native.Owner(window.deadline(900, final=True), window, first=first, cancelled=cancelled)
        owner_before.work_limit, owner_before.final_limit = window.work, window.final
        copy_owner = _PrimaryOwner(owner_before)
        destination = _private(copy_owner, paths["copied-evidence"])
        authority_copy_raw = _copy_authority(copy_owner, primary_result, authority_result, destination)
        require(type(authority_copy_raw) is bytes, "CRYPTO_AUTHORITY_COPY_BYTE_RETURN")
        copy_close = copy_owner.finish()
        copy_owner.structural()
        require(copy_owner.finished and copy_owner.failure is None and all(a and c for _r, _l, _v, a, c in copy_owner.rows),
            "CRYPTO_AUTHORITY_COPY_NOT_CLOSED")
        # This is the only parent LOCAL255 allocation and precedes ALL new setup.
        owner = _CustodyOwner(window.deadline(255, final=True), window, first=first, cancelled=cancelled)
        anchor = owner._anchor()
        observed, actual_root, event = N.host_context(history["firstUseAt"])
        require(observed == history["observed"] and actual_root == _paths(primary.kind)[0]["P"] and
            event == source_files["P/acquisition-queries/event.bin"], "CRYPTO_PARENT_ACTUAL_CONTEXT")
        original_match = source_files["P/acquisition-queries/match.bin"]
        policy_raw = source_files["P/acquisition-queries/candidate_policy_raw.bin"]
        policy, public = I._policy(policy_raw, int(time.time()))
        require(original_match == fresh.record and O.digest(original_match) == history["matchSha256"], "CRYPTO_PARENT_MATCH")
        raw_inputs = {"primary-map.json": primary_raw, "authority-map.json": authority_copy_raw,
            "authority-return.json": authority_raw, "original-match.json": original_match, "fresh-match.json": fresh.record,
            "event.json": event, "candidate-policy.json": policy_raw, "recipient-public.asc": public}
        graphs = (N._history_graph(observed, raw_inputs, fresh.__dict__, primary.__dict__, captured, originals),)
        directories = {"custody": owner.open(paths["custody"])}
        require(native._initializer_names(owner, directories["custody"]) == ("authority-1", "copied-evidence"),
            "CRYPTO_PARENT_INITIAL_ROSTER")
        directories["returned"] = owner.child(directories["custody"], "returned", create=True)
        for name in ("control-home", "temporary", "crypto-service"):
            directories[name] = owner.child(directories["returned"], name, create=True)
        directories["copied-evidence"] = owner.child(directories["custody"], "copied-evidence")
        directories["public-crypto"] = owner.child(directories["custody"], "public-crypto", create=True)
        if os.name == "nt":
            directories["export-output"] = owner.child(directories["custody"], "export-output", create=True)
        else:
            require(not os.path.lexists(paths["export-output"]), "CRYPTO_PARENT_OUTPUT_MUST_BE_ABSENT")
        identities = {name: list(directories[name].identity) if name in directories else None for name in _CRYPTO_DIRECTORIES}
        for name, maximum in _CRYPTO_INPUT_LIMITS.items():
            require(type(raw_inputs[name]) is bytes and 0 < len(raw_inputs[name]) <= maximum, "CRYPTO_PARENT_INPUT_CAP")
            require(owner.write(directories["returned"], name, raw_inputs[name]) == raw_inputs[name], "CRYPTO_PARENT_INPUT_WRITE")
        context = {"schema": 1, "scope": _CRYPTO_CONTEXT_SCOPE, "kind": primary.kind, "root": str(ROOT),
            "session": str(paths["returned"]), "job": uuid.uuid4().hex, "observed": observed, "window": canonical(frame_raw),
            "primary": {"step": "initial-originals" if primary.kind == "gate" else "canonical-initialization",
                "outcome": "success", "resultSha256": primary.result_sha256, "handoffSha256": O.digest(primary.handoff_raw),
                "inventorySha256": O.digest(primary.inventory_raw)},
            "authority": {"returnSha256": O.digest(authority_raw), "matchSha256": O.digest(fresh.record),
                "copySha256": O.digest(authority_copy_raw)},
            "filesSha256": {name: O.digest(raw) for name, raw in raw_inputs.items()}, "directories": identities,
            "inheritedContext": Q._inherited_context(), "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        context_raw = O.encoded(context)
        _crypto_context(context_raw, first, window._view().binding[2])
        _crypto_inputs(context, raw_inputs)
        require(owner.write(directories["returned"], "context.json", context_raw) == context_raw, "CRYPTO_PARENT_CONTEXT_WRITE")
        context_graph = N._history_graph(context)

        def current():
            require(_CRYPTO_ATTEMPTS.get("fixed") is attempt and attempt["failure"] is None and
                attempt["state"] in ("STARTED", "CLOSED", "RETURNED") and
                attempt["primary"] is primary_result and attempt["authority"] is authority_result,
                "CRYPTO_PARENT_ATTEMPT_CHANGED")
            p = checked_primary(primary_result)
            a = checked_custody_authority(authority_result, primary_result)
            require(p[0] is window and p[1] is primary and p[2] == history_raw and p[3] == primary_raw and p[4] is historical and
                a[0] is window and a[1] is fresh and a[2] is captured and a[3] == authority_raw and
                a[4] == inventory_raw and a[5] is originals, "CRYPTO_PARENT_UPSTREAM_CHANGED")
            for graph in graphs:
                N._check_history(graph)
            N._check_history(context_graph)
            require(owner._anchor() is anchor, "CRYPTO_PARENT_OWNER_CHANGED")
            owner.check()
            copy_owner.structural()
            require(copy_owner.finished and copy_owner.failure is None, "CRYPTO_PARENT_COPY_CLOSE_CHANGED")

        current()
        phase = _custody_crypto_native(owner, directories["returned"], context_raw, window, current)
        start, terminal, child, ack, manifest_raw = _checked_crypto_native(phase, owner, window)
        current()
        window.now(final=True, limit=start["finalEndNs"])
        owner.freeze()
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("crypto-parent", error)
            failure = owner._anchor().failure
    finally:
        if copy_owner is not None and not copy_owner.finished and not copy_owner.owner.unknown:
            try:
                copy_owner.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                owner.error("crypto-parent-close", error)
            if failure is None and owner._anchor().failure is not None:
                failure = owner._anchor().failure
    try:
        if failure is not None:
            raise failure
        anchor = owner.known()
        current()
        _checked_crypto_native(phase, owner, window)
        closed = window.now(final=True, limit=start["finalEndNs"])
        native.posix._deadline(owner.local_end)
        parent_close = O.encoded({"schema": 1, "scope": "INITIAL_CUSTODY_CRYPTO_PARENT_KNOWN_CLOSE_V1",
            "contextSha256": O.digest(context_raw), "childSha256": O.digest(phase.child),
            "authorityCopyCloseSha256": O.digest(copy_close), "phaseSha256": {name: O.digest(raw) for name, raw in phase.records},
            "closedNs": closed, "resources": [{"ordinal": number, "label": label,
                "closeAttempted": attempted, "closed": ended}
                for number, (_row, label, _resource, attempted, ended) in enumerate(anchor.rows)],
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False})
        canonical(parent_close)
        result = _ClosedCrypto(context_raw, phase, manifest_raw, parent_close)
        graph = N._history_graph(result.__dict__, owner.__dict__)
        saved = (result, window, owner, anchor, context_raw, phase, manifest_raw, parent_close, graph, current, attempt,
            copy_close, result.__dict__)
        _CRYPTO_RETURNS[id(result)] = saved
        attempt["return"], attempt["state"] = result, "CLOSED"
        checked_custody_crypto(result)
        return result
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def checked_custody_crypto(result):
    saved = _CRYPTO_RETURNS.get(id(result))
    require(type(result) is _ClosedCrypto and type(saved) is tuple and saved[0] is result, "CRYPTO_NOT_ORIGINAL_PARENT_RETURN")
    _, window, owner, anchor, context_raw, phase, manifest_raw, parent_close, graph, current, attempt, _copy_close, dictionary = saved
    try:
        require(attempt["return"] is result and attempt["state"] in ("CLOSED", "RETURNED") and
            result.context == context_raw and result.phase is phase and result.manifest == manifest_raw and
            result.parent_close == parent_close and result.__dict__ is dictionary, "CRYPTO_PARENT_RETURN_CHANGED")
        N._check_history(graph)
        current()
        require(owner._anchor() is anchor, "CRYPTO_PARENT_CLOSE_CHANGED")
        owner.known()
        _checked_crypto_native(phase, owner, window)
        require(window._view().failure is None, "CRYPTO_PARENT_WINDOW_FAILED")
        return window, context_raw, phase, manifest_raw, parent_close
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


_CRYPTO_READ_FENCES, _CRYPTO_CARRIERS = {}, {}


class _CryptoReadFence:
    """Only the original known-close parent's existing READ end, not a new clock."""
    __slots__ = ("_binding",)

    def __init__(self, result):
        require(type(self) is _CryptoReadFence and id(self) not in _CRYPTO_READ_FENCES, "CRYPTO_READ_NEW_FACADE")
        window, _context, _phase, _manifest, _closed = checked_custody_crypto(result)
        saved = _CRYPTO_RETURNS[id(result)]
        attempt = saved[10]
        require(attempt["readClaimed"] is True and attempt["reader"] is None, "CRYPTO_READ_ORIGINAL_CLAIM")
        self._binding = (result, saved, window, attempt)
        _CRYPTO_READ_FENCES[id(self)] = (self, self._binding)
        attempt["reader"] = self
        self._current()

    def _current(self):
        pin = _CRYPTO_READ_FENCES.get(id(self))
        require(type(self) is _CryptoReadFence and type(pin) is tuple and pin[0] is self and
            self._binding is pin[1], "CRYPTO_READ_ORIGINAL_FACADE")
        result, saved, window, attempt = pin[1]
        require(_CRYPTO_RETURNS.get(id(result)) is saved and saved[10] is attempt and attempt["readClaimed"] is True and
            attempt["reader"] is self and checked_custody_crypto(result)[0] is window, "CRYPTO_READ_PARENT_CHANGED")
        return window

    clock = property(lambda self: self._current().clock)

    def now(self, *, final=False, minimum=0, limit=None):
        require(type(final) is bool, "CRYPTO_READ_FINAL_TYPE")
        return self._current().now(final=final, minimum=minimum, limit=limit, stage="readEndNs")

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(final) is bool, "CRYPTO_READ_FINAL_TYPE")
        return self._current().deadline(maximum, final=final, limit=limit, stage="readEndNs")


@dataclass(frozen=True, repr=False)
class CustodyCryptoCarrier:
    parent: object
    raw: bytes
    metadata_close: bytes


def _custody_crypto_carrier(result):
    """One post-parent-close writer; no actual custody Step/late authority grant."""
    window, context_raw, phase, manifest_raw, parent_close = checked_custody_crypto(result)
    saved = _CRYPTO_RETURNS[id(result)]
    attempt = saved[10]
    require(attempt["readClaimed"] is False, "CRYPTO_READ_WRITER_REUSE")
    attempt["readClaimed"] = True  # Includes failures before allocation/write.
    metadata = None
    failure = None
    try:
        facade = _CryptoReadFence(result)
        first, _local, _boot, _limits, _ends, _locals, cancelled = window._view().binding
        metadata = _PrimaryOwner(native.Owner(facade.deadline(45, final=True), facade, first=first, cancelled=cancelled))
        context, manifest = canonical(context_raw, 65536), canonical(manifest_raw, E.MANIFEST_LIMIT)
        child = canonical(phase.child)
        paths = _crypto_directory_paths(context["kind"])
        output = _private(metadata, paths["export-output"])
        if context["directories"]["export-output"] is not None:
            require(list(output.identity) == context["directories"]["export-output"], "CRYPTO_READ_OUTPUT_PIN")
        require(_read_private(metadata, output, native.posix.MANIFEST, E.MANIFEST_LIMIT) == manifest_raw,
            "CRYPTO_READ_ORIGINAL_MANIFEST")
        returned = _private(metadata, paths["returned"])
        require(list(returned.identity) == context["directories"]["returned"], "CRYPTO_READ_RETURNED_PIN")
        facade.now()
        original_window = canonical(context_raw, 65536)["window"]
        window_value = {name: original_window[name] for name in
            ("clock", "originalBootDigest", "originalJobBasisNs", "jobEndNs", "startNs", *WINDOW_NAMES)}
        view = window._view()
        window_value.update(lastNs=view.last, lastLocal=view.local_last)
        raw = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_CUSTODY_CLOSED_RETURN_V1",
            "kind": context["kind"], "selection": manifest["selection"], "source": manifest["source"],
            "github": manifest["github"], "policy": manifest["policy"], "authority": manifest["initialRecipient"],
            "primary": context["primary"], "window": window_value,
            "copy": {**manifest["copy"], "path": str(paths["copied-evidence"]),
                "directoryIdentity": context["directories"]["copied-evidence"],
                "sourceMetadataSha256": child["sourceMetadataSha256"],
                "destinationMetadataSha256": child["freezeMetadataSha256"]},
            "recipient": manifest["recipient"],
            "exporter": {"manifestBase64": base64.b64encode(manifest_raw).decode("ascii"),
                "manifestBytes": len(manifest_raw), "manifestSha256": O.digest(manifest_raw),
                "childSha256": O.digest(phase.child), "ackSha256": O.digest(dict(phase.records)["stdout.log"]),
                "phaseSha256": {name: O.digest(data) for name, data in phase.records},
                "nativeResources": canonical(parent_close)["resources"]},
            "parentClose": canonical(parent_close), "writerReturn": "PENDING_OWNER_CLOSE",
            "originalStepOutcome": "NOT_OBSERVED", "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False,
            "cacheAuthority": False, "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"})
        canonical(raw)
        reader = metadata.acquire("embedded-reader", lambda: io.BytesIO(raw))
        end = metadata.guard()
        writer = metadata.acquire("writer", lambda: returned.create_file("custody-return.json", max_bytes=len(raw), deadline=end))
        def verify():
            require(type(reader) is io.BytesIO and reader.getvalue() == raw, "CRYPTO_CARRIER_ORIGINAL_BYTES")
        checksum, _written = _consume(metadata, reader, len(raw), O.digest(raw), verify, writer=writer)
        require(checksum == O.digest(raw) and _read_private(metadata, returned, "custody-return.json", native.LIMIT) == raw,
            "CRYPTO_CARRIER_READBACK")
        checked_custody_crypto(result)
        closed = metadata.finish()
        facade.now(final=True)
        checked_custody_crypto(result)
        require(metadata.finished and metadata.failure is None and metadata.owner.closed and not metadata.owner.unknown and
            all(attempted and ended for _row, _label, _resource, attempted, ended in metadata.rows), "CRYPTO_CARRIER_CLOSE_UNKNOWN")
        carrier = CustodyCryptoCarrier(result, raw, closed)
        _CRYPTO_CARRIERS[id(carrier)] = (carrier, result, raw, closed, metadata, metadata._anchor(),
            N._history_graph(carrier.__dict__, metadata.owner.__dict__))
        attempt["state"] = "RETURNED"
        return carrier  # Private data only. Fresh post-export/late-output edges are NOT implemented here.
    except BaseException as error:
        failure = error
        if metadata is not None:
            failure = metadata.remember(error)
    finally:
        if metadata is not None and not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
        if failure is not None:
            if attempt["failure"] is None:
                attempt["failure"] = failure
            attempt["state"] = "FAILED"
    if failure is not None:
        raise attempt["failure"]


# Two distinct trusted Steps. The first never retains its token across crypto;
# the second needs its own real mapping and predecessor SUCCESS. Neither route
# authorizes activation. Post-cut records below are LOCAL guard inputs only.
_COLLECT_OUTCOME = "P2PKIT_INITIAL_CRYPTO_OUTCOME"
_COLLECT_STEP_HASH = "P2PKIT_INITIAL_CRYPTO_STEP_SHA256"
_COLLECT_EXPORT_HASH = "P2PKIT_INITIAL_EXPORTER_RETURN_SHA256"
_COLLECT_NAMES = (*_ACTUAL_NAMES, _COLLECT_OUTCOME, _COLLECT_STEP_HASH, _COLLECT_EXPORT_HASH)
_EXPORT_STEP_SCOPE = "INITIAL_CUSTODY_CRYPTO_STEP_PENDING_GUARDED_OUTPUT_V1"
_EXPORT_STEP_FILE = "crypto-step-pending.json"
_COLLECT_SCOPE = "INITIAL_RECIPIENT_COLLECT_CLOSED_RETURN_V1"
_COLLECT_FILE = "collect-close.json"
_COLLECT_CHILD_SCOPE = "INITIAL_POST_EXPORT_AUTHORITY_PENDING_CHILD_CLOSE_V1"
_COLLECT_ACK_SCOPE = "INITIAL_POST_EXPORT_AUTHORITY_ORIGINAL_POST_CLOSE_ACK_V1"
_COLLECT_STEP_FIELDS = "schema scope kind step primary originalServiceJob directory directoryIdentity cryptoCarrier " \
    "originalWindow originalContextSha256 observed lowerNs lowerLocal sample writerReturn originalStepOutcome " \
    "testAcceptance productiveAuthority cacheAuthority budgetAcceptance exportSaveAuthority"
_COLLECT_CONTEXT_FIELDS = "schema scope edge kind root session job observed originalWindow originalServiceJob " \
    "predecessor expectedMatch eventSha256 sourceReturnSha256 sourceReturnedNs inheritedContext directoryIdentity " \
    "parentFirstNs continuationEndNs budgetAcceptance exportSaveAuthority"
_COLLECT_ATTEMPTS, _EXPORT_STEPS, _COLLECT_INPUTS, _COLLECT_CLOCKS = {}, {}, {}, {}
_COLLECT_AUTHORITY_RETURNS, _COLLECT_RETURNS, _COLLECT_OUTPUTS = {}, {}, {}


def _collect_begin(name):
    """Failure accounting only; this closed list selects no operation or cap."""
    require(name in ("export-transfer", "post-export-authority", "collect-final", "collect-export-entry", "collect-close-entry"),
        "COLLECT_ATTEMPT_NAME")
    previous = _COLLECT_ATTEMPTS.get(name)
    if previous is not None:
        if previous["failure"] is None:
            previous["failure"] = O.OriginError("INITIAL_CUSTODY_COLLECT_ATTEMPT_REUSE")
        previous["state"] = "FAILED"
        raise previous["failure"]
    attempt = {"failure": None, "state": "STARTED", "return": None}
    _COLLECT_ATTEMPTS[name] = attempt
    return attempt


def _collect_pending(value):
    require(value["writerReturn"] == "PENDING_OWNER_CLOSE" and value["originalStepOutcome"] == "NOT_OBSERVED" and
        value["testAcceptance"] == "NOT_PERFORMED" and value["productiveAuthority"] is False and
        value["cacheAuthority"] is False and value["budgetAcceptance"] == "NOT_ADMITTED" and
        value["exportSaveAuthority"] is False, "COLLECT_PENDING_FLAGS")


def _collect_primary(value, kind):
    fields(value, " ".join(E.PRIMARY_FIELDS), "COLLECT_PRIMARY_FIELDS")
    require(kind in ("gate", "worker") and value["outcome"] == "success" and
        value["step"] == ("initial-originals" if kind == "gate" else "canonical-initialization"), "COLLECT_PRIMARY_STEP")
    for name in ("resultSha256", "handoffSha256", "inventorySha256"):
        digest(value[name])


def _collect_service_job(value):
    require(type(value) is list and len(value) == 4 and type(value[0]) is int and value[0] > 0 and
        type(value[3]) is int and value[3] > 0 and type(value[1]) is str and type(value[2]) is str and
        0 < len(value[2]) <= 256 and not any(ord(char) < 32 or ord(char) == 127 for char in value[2]),
        "COLLECT_ORIGINAL_SERVICE_JOB")
    A.stages.joint.timestamp(value[1])
    return value


def _collect_close_rows(value, labels):
    require(type(value) is list and 0 < len(value) <= MAX_MEMBERS, "COLLECT_CLOSE_ROSTER")
    for ordinal, row in enumerate(value):
        fields(row, "ordinal label closeAttempted closed", "COLLECT_CLOSE_ROW")
        require(type(row["ordinal"]) is int and row["ordinal"] == ordinal and
            type(row["label"]) is str and row["label"] in labels and row["closeAttempted"] is True and
            row["closed"] is True, "COLLECT_CLOSE_ROW_VALUE")


def _collect_file_close(raw):
    value = fields(canonical(raw), "schema scope resources retirement exportSaveAuthority", "COLLECT_FILE_CLOSE_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1" and
        value["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and value["exportSaveAuthority"] is False,
        "COLLECT_FILE_CLOSE_SCOPE")
    _collect_close_rows(value["resources"], {"directory", "reader", "writer", "snapshot", "embedded-reader"})
    return value


def _collect_write(owner, directory, name, raw):
    """Only the two new post-cut records; never extend the frozen-map writer."""
    require(type(owner) is _PrimaryOwner and name in (_EXPORT_STEP_FILE, _COLLECT_FILE), "COLLECT_FIXED_RECORD_NAME")
    canonical(raw)
    reader = owner.acquire("embedded-reader", lambda: io.BytesIO(raw))
    end = owner.guard()
    writer = owner.acquire("writer", lambda: directory.create_file(name, max_bytes=len(raw), deadline=end))
    def verify():
        require(type(reader) is io.BytesIO and reader.getvalue() == raw, "COLLECT_WRITER_ORIGINAL_BYTES")
    checksum, _written = _consume(owner, reader, len(raw), O.digest(raw), verify, writer=writer)
    require(checksum == O.digest(raw) and _read_private(owner, directory, name, native.LIMIT) == raw,
        "COLLECT_WRITER_READBACK")


def _collect_directory_closed(directory, role):
    return directory._closed if role == "windows-x64" else directory.closed


def _collect_names(metadata, directory, extra=()):
    """Only the immediate returned directory, not a replay of its old readers."""
    require(type(metadata) is _PrimaryOwner and type(extra) is tuple and
        extra in ((), (_EXPORT_STEP_FILE,), (_EXPORT_STEP_FILE, _COLLECT_FILE)), "COLLECT_ROSTER_STAGE")
    end = metadata.guard()
    directory.verify()
    if metadata.owner.first.clock.role == "windows-x64":
        names = directory.names(max_names=32, deadline=end)
    else:
        names = []
        with os.scandir(directory.path) as entries:
            for entry in entries:
                require(len(names) < 32, "COLLECT_ROSTER_LIMIT")
                names.append(entry.name)
    expected = (*_CRYPTO_INPUT_LIMITS, "context.json", "crypto-child-result.json", "custody-return.json",
        "control-home", "temporary", "crypto-service", *extra)
    require(len(names) == len(set(name.casefold() for name in names)) and tuple(sorted(names)) == tuple(sorted(expected)),
        "COLLECT_RETURNED_ROSTER")
    directory.verify()
    metadata.guard()


def _collect_actual(expected=None):
    actual = tuple(os.environ.get(name) for name in _COLLECT_NAMES)
    require((expected is None or type(expected) is tuple and actual == expected) and
        not any(name in os.environ for name in _CREDENTIAL_NAMES) and
        os.environ.get(_COLLECT_OUTCOME) == "success" and os.environ.get(PRIMARY_OUTCOME) == "success",
        "COLLECT_ACTUAL_STEP_OR_CREDENTIAL_CHANGED")
    for name in (_COLLECT_STEP_HASH, _COLLECT_EXPORT_HASH, PRIMARY_RESULT, PRIMARY_HANDOFF):
        digest(os.environ.get(name))
    return actual


def _checked_crypto_carrier(carrier):
    """Only THIS actual return; bytes or an equal reconstructed carrier cannot mint it."""
    saved = _CRYPTO_CARRIERS.get(id(carrier))
    require(type(carrier) is CustodyCryptoCarrier and type(saved) is tuple and saved[0] is carrier,
        "COLLECT_NOT_ORIGINAL_CRYPTO_CARRIER")
    _, parent, raw, closed, metadata, anchor, graph = saved
    require(carrier.parent is parent and carrier.raw == raw and carrier.metadata_close == closed and
        metadata._anchor() is anchor and any(value is carrier.__dict__ and mode == "mapping"
            for value, _kind, mode, _snapshot in graph), "COLLECT_CRYPTO_CARRIER_CHANGED")
    N._check_history(graph)
    metadata.structural()
    require(metadata.finished and metadata.failure is None and metadata.owner.closed and not metadata.owner.unknown and
        metadata.owner.original is None and metadata.errors == [] and
        all(a and c for _row, _label, _resource, a, c in metadata.rows), "COLLECT_CRYPTO_WRITER_NOT_CLOSED")
    window, context, phase, manifest, parent_close = checked_custody_crypto(parent)
    attempt = _CRYPTO_RETURNS[id(parent)][10]
    facade = attempt["reader"]
    require(attempt["state"] == "RETURNED" and attempt["readClaimed"] is True and type(facade) is _CryptoReadFence and
        facade._current() is window, "COLLECT_NOT_ORIGINAL_READ_FACADE")
    _collect_file_close(closed)
    return window, facade, context, manifest, parent_close


def _collect_crypto_inputs(carrier):
    """Only the original already-checked crypto call's actual two inputs."""
    _checked_crypto_carrier(carrier)
    attempt = _CRYPTO_RETURNS[id(carrier.parent)][10]
    return attempt["primary"], attempt["authority"]


def _collect_export_currency(carrier):
    window, facade, context_raw, manifest_raw, parent_close = _checked_crypto_carrier(carrier)
    primary_result, authority_result = _collect_crypto_inputs(carrier)
    _, _primary, history_raw, _copy, historical = checked_primary(primary_result)
    _, original, captured, _raw, _index, _originals = checked_custody_authority(authority_result, primary_result)
    original_pin = _custody_match_pin(original, _primary.kind)
    graph = N._history_graph(carrier.__dict__, captured, historical)
    dictionary = carrier.__dict__
    context, originals, invocation, began, end = captured
    match, _service = N.retained_match(canonical(context), dict(originals), invocation, window.clock, began, end)
    match_pin = _custody_match_pin(match, _primary.kind)
    require(type(match) is type(original) and match.record == original.record, "COLLECT_EXPORT_GRANT_CHANGED")
    I._policy(dict(historical)["P/acquisition-queries/candidate_policy_raw.bin"], int(time.time()))
    facade.now()
    # No fresh observation follows these passive pins: even the last output
    # cancellation callback must not mutate a previously checked old return.
    N._check_history(graph)
    _custody_match_check(original_pin)
    _custody_match_check(match_pin)
    require(carrier.__dict__ is dictionary and _checked_crypto_carrier(carrier) ==
        (window, facade, context_raw, manifest_raw, parent_close) and checked_primary(primary_result)[0] is window and
        checked_custody_authority(authority_result, primary_result)[0] is window, "COLLECT_EXPORT_POST_CALLBACK_CHANGED")
    current_inputs = _collect_crypto_inputs(carrier)
    require(current_inputs[0] is primary_result and current_inputs[1] is authority_result, "COLLECT_EXPORT_INPUTS_CHANGED")
    return window, facade, context_raw, manifest_raw, parent_close, canonical(history_raw)


@dataclass(frozen=True, repr=False)
class _ExportStep:
    carrier: object
    raw: bytes
    metadata_close: bytes


def _export_pre_crypto(kind, cancelled):
    """The outer caller NEVER receives a token reference to keep across crypto."""
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    try:
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and
            not any(name in os.environ for name in _CREDENTIAL_NAMES), "COLLECT_EXPORT_TOKEN")
        primary = copy_primary(kind, cancelled=cancelled)
        authority = custody_authority(primary, token)
        return primary, authority
    finally:
        token = None


def _retain_crypto_step(carrier):
    attempt = _collect_begin("export-transfer")
    attempt["carrier"] = carrier
    metadata = None
    failure = None
    try:
        window, facade, context_raw, manifest_raw, _closed, history = _collect_export_currency(carrier)
        context = canonical(context_raw, 65536)
        original_carrier = carrier.raw
        original_dictionary = carrier.__dict__
        input_graph = N._history_graph(carrier.__dict__, context, history)
        first, _local, _boot, _limits, _ends, _locals, cancelled = window._view().binding
        lower = facade.now()
        lower_local = window._view().local_last
        metadata = _PrimaryOwner(native.Owner(facade.deadline(30), facade, first=first, cancelled=cancelled))
        paths = _crypto_directory_paths(context["kind"])
        directory = _private(metadata, paths["returned"])
        pin = (directory, directory.path, tuple(directory.identity))
        _collect_names(metadata, directory)
        output = _private(metadata, paths["export-output"])
        pins = (pin, (output, output.path, tuple(output.identity)))
        require((context["directories"]["export-output"] is None or
            list(output.identity) == context["directories"]["export-output"]) and
            _read_private(metadata, output, native.posix.MANIFEST, E.MANIFEST_LIMIT) == manifest_raw,
            "COLLECT_TRANSFER_ORIGINAL_MANIFEST")
        require(list(pin[2]) == context["directories"]["returned"] and
            _read_private(metadata, directory, "custody-return.json", native.LIMIT) == original_carrier and
            _read_private(metadata, directory, "context.json", 65536) == context_raw, "COLLECT_TRANSFER_ORIGINAL_FILES")
        raw = O.encoded({"schema": 1, "scope": _EXPORT_STEP_SCOPE, "kind": context["kind"],
            "step": "initial-custody-export", "primary": context["primary"], "originalServiceJob": history["serviceJob"],
            "directory": str(paths["returned"]), "directoryIdentity": list(pin[2]),
            "cryptoCarrier": {"sha256": O.digest(original_carrier), "bytes": len(original_carrier),
                "exporterReturnSha256": O.digest(manifest_raw), "metadataClose": _collect_file_close(carrier.metadata_close)},
            "originalWindow": context["window"], "originalContextSha256": O.digest(context_raw), "observed": context["observed"],
            "lowerNs": lower, "lowerLocal": lower_local,
            "sample": "AFTER_CRYPTO_CARRIER_FUNCTION_BEFORE_GUARDED_OUTPUT_AND_STEP_RETURN",
            "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED", "testAcceptance": "NOT_PERFORMED",
            "productiveAuthority": False, "cacheAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _collect_step_record(raw)
        _collect_write(metadata, directory, _EXPORT_STEP_FILE, raw)
        _collect_names(metadata, directory, (_EXPORT_STEP_FILE,))
        require(_read_private(metadata, directory, _EXPORT_STEP_FILE, native.LIMIT) == raw and
            _read_private(metadata, directory, "custody-return.json", native.LIMIT) == original_carrier and
            _read_private(metadata, directory, "context.json", 65536) == context_raw and
            _read_private(metadata, output, native.posix.MANIFEST, E.MANIFEST_LIMIT) == manifest_raw,
            "COLLECT_TRANSFER_READBACK")
        N._check_history(input_graph)
        require(carrier.__dict__ is original_dictionary and carrier.raw == original_carrier, "COLLECT_TRANSFER_CARRIER_CHANGED")
        _collect_export_currency(carrier)
        closed = metadata.finish()
        facade.now(final=True)
        result = _ExportStep(carrier, raw, closed)
        saved = (result, result.__dict__, raw, closed, carrier, original_dictionary, original_carrier,
            metadata, metadata._anchor(), pins, window, facade, attempt,
            N._history_graph(result.__dict__, metadata.owner.__dict__, tuple(value[1] for value in pins)), input_graph)
        _EXPORT_STEPS[id(result)] = saved
        attempt["return"], attempt["state"] = result, "RETURNED"
        _checked_export_step(result)
        return result
    except BaseException as error:
        failure = error if metadata is None else metadata.remember(error)
    finally:
        if metadata is not None and not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
        if failure is not None:
            if attempt["failure"] is None:
                attempt["failure"] = failure
            attempt["state"] = "FAILED"
    raise attempt["failure"]


def _checked_export_step(result):
    saved = _EXPORT_STEPS.get(id(result))
    require(type(result) is _ExportStep and type(saved) is tuple and saved[0] is result,
        "COLLECT_NOT_ORIGINAL_EXPORT_STEP")
    _, dictionary, raw, closed, carrier, carrier_dictionary, carrier_raw, metadata, anchor, pins, window, facade, attempt, graph, inputs = saved
    try:
        def current():
            require(type(result) is _ExportStep and type(carrier) is CustodyCryptoCarrier and
                _EXPORT_STEPS.get(id(result)) is saved and _COLLECT_ATTEMPTS.get("export-transfer") is attempt and
                attempt["return"] is result and attempt["state"] == "RETURNED" and attempt["failure"] is None and
                result.__dict__ is dictionary and result.carrier is carrier and result.raw == raw and result.metadata_close == closed and
                carrier.__dict__ is carrier_dictionary and carrier.raw == carrier_raw, "COLLECT_EXPORT_STEP_CHANGED")
            N._check_history(graph)
            N._check_history(inputs)
            require(metadata._anchor() is anchor, "COLLECT_TRANSFER_OWNER_CHANGED")
            metadata.structural()
            require(metadata.finished and metadata.failure is None and metadata.owner.closed and not metadata.owner.unknown and
                metadata.owner.original is None and metadata.errors == [] and all(a and c for _r, _l, _v, a, c in metadata.rows),
                "COLLECT_TRANSFER_CLOSE_UNKNOWN")
            for directory, path, identity in pins:
                require(directory.path is path and tuple(directory.identity) == identity and
                    _collect_directory_closed(directory, window.clock.role) is True, "COLLECT_TRANSFER_PIN_CHANGED")
        current()
        currency = _collect_export_currency(carrier)
        current()
        require(currency[0] is window and currency[1] is facade, "COLLECT_TRANSFER_FACADE_CHANGED")
        _collect_file_close(closed)
        return facade, canonical(currency[2], 65536)["window"]["readEndNs"], {
            "initialCryptoStepSha256": O.digest(raw), "initialExporterReturnSha256": O.digest(currency[3])}
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def _collect_step_record(raw):
    value = fields(canonical(raw), _COLLECT_STEP_FIELDS, "COLLECT_STEP_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == _EXPORT_STEP_SCOPE and
        value["step"] == "initial-custody-export" and value["kind"] in ("gate", "worker") and
        value["sample"] == "AFTER_CRYPTO_CARRIER_FUNCTION_BEFORE_GUARDED_OUTPUT_AND_STEP_RETURN", "COLLECT_STEP_SCOPE")
    _collect_pending(value)
    clock, limits = _custody_authority_frame(value["originalWindow"])
    require(limits["kind"] == value["kind"] and limits["startNs"] <= O.integer(value["lowerNs"]) < limits["readEndNs"],
        "COLLECT_STEP_ORIGINAL_TIME")
    local_value(value["lowerLocal"])
    _collect_primary(value["primary"], value["kind"])
    _collect_service_job(value["originalServiceJob"])
    digest(value["originalContextSha256"])
    native.directory_identity(value["directoryIdentity"], clock.role)
    require(type(value["directory"]) is str and Path(value["directory"]).is_absolute() and
        ".." not in Path(value["directory"]).parts and type(value["observed"]) is dict,
        "COLLECT_STEP_DIRECTORY_OR_HOST")
    carrier = fields(value["cryptoCarrier"], "sha256 bytes exporterReturnSha256 metadataClose", "COLLECT_STEP_CARRIER_FIELDS")
    digest(carrier["sha256"])
    digest(carrier["exporterReturnSha256"])
    require(type(carrier["bytes"]) is int and 0 < carrier["bytes"] <= native.LIMIT, "COLLECT_STEP_CARRIER_LIMIT")
    _collect_file_close(O.encoded(carrier["metadataClose"]))
    return value


_COLLECT_READ_LIMITS = {
    "step": native.LIMIT, "carrier": native.LIMIT, "context": 65536, "manifest": E.MANIFEST_LIMIT,
    "original-match": _CRYPTO_INPUT_LIMITS["original-match.json"], "fresh-match": _CRYPTO_INPUT_LIMITS["fresh-match.json"],
    "event": I.EVENT_LIMIT, "policy": I.POLICY_LIMIT, "public": native.posix.MAX_KEY_BYTES,
}


def _collect_manifest(raw):
    value = fields(canonical(raw, E.MANIFEST_LIMIT), "schema scope kind selection source github policy initialRecipient "
        "primary copy recipient testAcceptance productiveAuthority cacheAuthority exportSaveAuthority budgetAcceptance artifact",
        "COLLECT_MANIFEST_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 4 and value["scope"] == E.SCOPE and
        value["kind"] in ("gate", "worker") and value["testAcceptance"] == "NOT_PERFORMED" and
        value["productiveAuthority"] is False and value["cacheAuthority"] is False and
        value["exportSaveAuthority"] is False and value["budgetAcceptance"] == "NOT_ADMITTED", "COLLECT_MANIFEST_SCOPE")
    A.stages.joint.source(value["source"])
    _collect_primary(value["primary"], value["kind"])
    copied = fields(value["copy"], " ".join(E.COPY_FIELDS), "COLLECT_MANIFEST_COPY")
    fields(copied["origins"], " ".join(ORIGINS), "COLLECT_MANIFEST_ORIGINS")
    for checksum in (copied["mapSha256"], *copied["origins"].values()):
        digest(checksum)
    require(len(set(copied["origins"].values())) == 3 and type(copied["memberCount"]) is int and
        0 < copied["memberCount"] < MAX_MEMBERS and type(copied["totalBytes"]) is int and
        0 < copied["totalBytes"] <= MAX_BYTES, "COLLECT_MANIFEST_COPY_LIMIT")
    recipient = fields(value["recipient"], "fingerprint encryptionFingerprint keySha256 expiresAt", "COLLECT_MANIFEST_RECIPIENT")
    require(all(type(recipient[name]) is str and re.fullmatch(r"[0-9A-F]{40}", recipient[name])
        for name in ("fingerprint", "encryptionFingerprint")), "COLLECT_RECIPIENT_FINGERPRINTS")
    digest(recipient["keySha256"])
    O.integer(recipient["expiresAt"], 1)
    artifact = fields(value["artifact"], "name sha256 size", "COLLECT_MANIFEST_ARTIFACT")
    require(artifact["name"] == native.posix.ARTIFACT and type(artifact["size"]) is int and
        0 < artifact["size"] <= native.posix.MAX_CIPHERTEXT_BYTES, "COLLECT_MANIFEST_ARTIFACT_LIMIT")
    digest(artifact["sha256"])
    return value


def _collect_bundle(raws):
    """Closed prior-Step DATA. Never constructs an old live/native return object."""
    require(type(raws) is dict and set(raws) == set(_COLLECT_READ_LIMITS), "COLLECT_INPUT_ROSTER")
    for name, maximum in _COLLECT_READ_LIMITS.items():
        require(type(raws[name]) is bytes and 0 < len(raws[name]) <= maximum, "COLLECT_INPUT_LIMIT")
    step = _collect_step_record(raws["step"])
    frame = step["originalWindow"]
    clock, _limits = _custody_authority_frame(frame)
    carrier = fields(canonical(raws["carrier"]), "schema scope kind selection source github policy authority primary window copy "
        "recipient exporter parentClose writerReturn originalStepOutcome testAcceptance productiveAuthority cacheAuthority "
        "exportSaveAuthority budgetAcceptance", "COLLECT_CRYPTO_CARRIER_FIELDS")
    require(type(carrier["schema"]) is int and carrier["schema"] == 1 and
        carrier["scope"] == "INITIAL_RECIPIENT_CUSTODY_CLOSED_RETURN_V1" and carrier["kind"] == step["kind"] and
        len(raws["carrier"]) == step["cryptoCarrier"]["bytes"] and
        O.digest(raws["carrier"]) == step["cryptoCarrier"]["sha256"], "COLLECT_CRYPTO_CARRIER_LINK")
    _collect_pending(carrier)
    context = fields(canonical(raws["context"], 65536), _CRYPTO_CONTEXT_FIELDS, "COLLECT_ORIGINAL_CONTEXT_FIELDS")
    require(type(context["schema"]) is int and context["schema"] == 1 and context["scope"] == _CRYPTO_CONTEXT_SCOPE and
        context["kind"] == step["kind"] and context["window"] == frame and context["observed"] == step["observed"] and
        context["primary"] == carrier["primary"] == step["primary"] and context["root"] == str(ROOT) and
        context["session"] == step["directory"] and O.digest(raws["context"]) == step["originalContextSha256"] and
        context["budgetAcceptance"] == "NOT_ADMITTED" and context["exportSaveAuthority"] is False and
        type(context["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", context["job"]), "COLLECT_ORIGINAL_CONTEXT_LINK")
    hashes = fields(context["filesSha256"], " ".join(_CRYPTO_INPUT_LIMITS), "COLLECT_ORIGINAL_INPUT_FIELDS")
    for checksum in hashes.values():
        digest(checksum)
    for name, original in (("original-match", "original-match.json"), ("fresh-match", "fresh-match.json"),
            ("event", "event.json"), ("policy", "candidate-policy.json"), ("public", "recipient-public.asc")):
        require(O.digest(raws[name]) == hashes[original], "COLLECT_ORIGINAL_INPUT_HASH")
    require(raws["original-match"] == raws["fresh-match"], "COLLECT_ORIGINAL_MATCH_CHANGED")
    initial = fields(context["authority"], "returnSha256 matchSha256 copySha256", "COLLECT_INITIAL_AUTHORITY_FIELDS")
    for checksum in initial.values():
        digest(checksum)
    require(initial["matchSha256"] == hashes["original-match.json"] == hashes["fresh-match.json"] and
        initial["returnSha256"] == hashes["authority-return.json"] and initial["copySha256"] == hashes["authority-map.json"],
        "COLLECT_INITIAL_AUTHORITY_LINKS")
    directories = fields(context["directories"], " ".join(_CRYPTO_DIRECTORIES), "COLLECT_ORIGINAL_DIRECTORIES")
    identities = []
    for name, value in directories.items():
        if name == "export-output" and clock.role != "windows-x64":
            require(value is None, "COLLECT_ORIGINAL_POSIX_OUTPUT")
        else:
            identities.append(tuple(native.directory_identity(value, clock.role)))
    require(len(identities) == len(set(identities)) and directories["returned"] == step["directoryIdentity"],
        "COLLECT_ORIGINAL_DIRECTORY_PINS")
    inherited = context["inheritedContext"]
    require(type(inherited) is dict and all(type(item) is str for item in inherited.values()) and
        (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "COLLECT_ORIGINAL_DOMAIN")
    old_window = fields(carrier["window"], "clock originalBootDigest originalJobBasisNs jobEndNs startNs " +
        " ".join(WINDOW_NAMES) + " lastNs lastLocal", "COLLECT_CARRIER_WINDOW_FIELDS")
    require(all(old_window[name] == frame[name] for name in old_window if name not in ("lastNs", "lastLocal")) and
        frame["startNs"] <= O.integer(old_window["lastNs"]) <= step["lowerNs"] and
        local_value(old_window["lastLocal"]) <= step["lowerLocal"], "COLLECT_CARRIER_WINDOW_LINK")
    exported = fields(carrier["exporter"], "manifestBase64 manifestBytes manifestSha256 childSha256 ackSha256 phaseSha256 "
        "nativeResources", "COLLECT_EXPORTER_FIELDS")
    require(type(exported["manifestBase64"]) is str and len(exported["manifestBase64"]) <= 4 * ((E.MANIFEST_LIMIT + 2) // 3),
        "COLLECT_EXPORTER_ENCODING_LIMIT")
    try:
        original_manifest = base64.b64decode(exported["manifestBase64"], validate=True)
    except (ValueError, TypeError):
        raise O.OriginError("INITIAL_CUSTODY_COLLECT_EXPORTER_ENCODING") from None
    require(base64.b64encode(original_manifest).decode("ascii") == exported["manifestBase64"] and
        original_manifest == raws["manifest"] and type(exported["manifestBytes"]) is int and
        len(original_manifest) == exported["manifestBytes"] and
        O.digest(original_manifest) == digest(exported["manifestSha256"]) == step["cryptoCarrier"]["exporterReturnSha256"],
        "COLLECT_ORIGINAL_EXPORTER_BYTES")
    for name in ("childSha256", "ackSha256"):
        digest(exported[name])
    fields(exported["phaseSha256"], " ".join(native.PHASE_FILES), "COLLECT_EXPORTER_PHASE_HASHES")
    for checksum in exported["phaseSha256"].values():
        digest(checksum)
    parent = fields(carrier["parentClose"], "schema scope contextSha256 childSha256 authorityCopyCloseSha256 phaseSha256 "
        "closedNs resources retirement exportSaveAuthority", "COLLECT_CRYPTO_PARENT_CLOSE_FIELDS")
    require(type(parent["schema"]) is int and parent["schema"] == 1 and
        parent["scope"] == "INITIAL_CUSTODY_CRYPTO_PARENT_KNOWN_CLOSE_V1" and
        parent["contextSha256"] == step["originalContextSha256"] and parent["childSha256"] == exported["childSha256"] and
        parent["phaseSha256"] == exported["phaseSha256"] and parent["resources"] == exported["nativeResources"] and
        frame["startNs"] <= O.integer(parent["closedNs"]) <= old_window["lastNs"] and
        parent["closedNs"] < frame["nativeFinalEndNs"] and parent["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and
        parent["exportSaveAuthority"] is False, "COLLECT_CRYPTO_PARENT_CLOSE_LINK")
    digest(parent["authorityCopyCloseSha256"])
    _collect_close_rows(parent["resources"], {"directory", "writer", "native-scope", "stdout", "stderr"})
    manifest = _collect_manifest(original_manifest)
    for name in ("kind", "selection", "source", "github", "policy", "primary", "recipient"):
        require(carrier[name] == manifest[name], "COLLECT_MANIFEST_CARRIER_LINK")
    require(carrier["authority"] == manifest["initialRecipient"] and
        manifest["initialRecipient"]["matchSha256"] == initial["matchSha256"] and
        manifest["initialRecipient"]["freshReturnSha256"] == initial["returnSha256"], "COLLECT_MANIFEST_AUTHORITY_LINK")
    copied = fields(carrier["copy"], " ".join(E.COPY_FIELDS) + " path directoryIdentity sourceMetadataSha256 destinationMetadataSha256",
        "COLLECT_CARRIER_COPY_FIELDS")
    require({name: copied[name] for name in E.COPY_FIELDS} == manifest["copy"] and
        copied["directoryIdentity"] == directories["copied-evidence"], "COLLECT_CARRIER_COPY_LINK")
    fields(copied["sourceMetadataSha256"], " ".join(ORIGINS), "COLLECT_CARRIER_ORIGIN_METADATA")
    for checksum in (*copied["sourceMetadataSha256"].values(), copied["destinationMetadataSha256"]):
        digest(checksum)
    require(type(copied["path"]) is str and Path(copied["path"]).is_absolute(), "COLLECT_CARRIER_COPY_PATH")
    return step, carrier, context, manifest


def _collect_host(raws, parsed, clock):
    step, carrier, context, manifest = parsed
    graph = N._history_graph(parsed, raws)
    first_use = O.integer(step["observed"]["firstUseAt"], 1)
    observed, primary, event = N.host_context(first_use)
    roots, _handoff, custody = _paths(step["kind"])
    require(observed == step["observed"] and observed["role"] == clock.role and primary == roots["P"] and event == raws["event"] and
        step["directory"] == str(custody / "returned") and context["session"] == str(custody / "returned") and
        carrier["copy"]["path"] == str(custody / "copied-evidence"), "COLLECT_ACTUAL_HOST_OR_PATH")
    expected = canonical(raws["original-match"], A.stages.LIMIT)
    fields(expected, " ".join(E.COMMON_MATCH | ({"stage", "selector", "workerAdmission", "qualificationAcceptance"}
        if step["kind"] == "gate" else set())), "COLLECT_EXPECTED_MATCH_FIELDS")
    github = dict(observed["github"])
    if step["kind"] == "worker":
        github.update(profile=A.stages.bootstrap.PROFILE, selection=observed["inputs"]["selection"])
    require(type(expected["schema"]) is int and expected["schema"] == 1 and expected["scope"] ==
        ("NONPRODUCTIVE_ELIGIBILITY" if step["kind"] == "gate" else A.stages.STAGE1 + "_MATCH_ONLY_NOT_ADMISSION") and
        expected["github"] == github and expected["source"] == expected["reviewed"] == observed["source"] and
        expected["originalBase"] == A.stages.BASE and expected["firstUseAt"] == first_use and
        manifest["source"] == observed["source"] and manifest["selection"] == observed["inputs"]["selection"] and
        manifest["github"] == {**github, "repository": I.REPOSITORY, "eventSha256": O.digest(event)}, "COLLECT_EXPECTED_IDENTITY")
    policy, public = I._policy(raws["policy"], int(time.time()))
    require(public == raws["public"] and O.digest(raws["policy"]) == A.stages.POLICY_SHA256 and
        expected["policy"] == {"origin": "reviewed-head", "commit": observed["source"]["commit"],
            "blob": hashlib.sha1(b"blob " + str(len(raws["policy"])).encode("ascii") + b"\0" + raws["policy"]).hexdigest(),
            "path": I.POLICY_PATH, "sha256": A.stages.POLICY_SHA256}, "COLLECT_EXPECTED_POLICY")
    initial = fields(manifest["initialRecipient"], "authority environment originalBase reviewed firstUseAt notBefore expiresAt "
        "matchSha256 freshReturnSha256", "COLLECT_MANIFEST_INITIAL_FIELDS")
    for name in ("authority", "environment", "originalBase", "reviewed", "firstUseAt", "notBefore", "expiresAt"):
        require(initial[name] == expected[name], "COLLECT_MANIFEST_INITIAL_LINK")
    require(manifest["policy"] == {**expected["policy"], "fingerprint": policy["recipient"]["fingerprint"],
        "keySha256": policy["recipient"]["sha256"], "expiresAt": policy["expiresAt"], "retentionDays": 14} and
        manifest["recipient"]["fingerprint"] == policy["recipient"]["fingerprint"] and
        manifest["recipient"]["keySha256"] == O.digest(public) and
        policy["expiresAt"] <= manifest["recipient"]["expiresAt"], "COLLECT_MANIFEST_POLICY_RECIPIENT")
    now = int(time.time())
    require(policy["notBefore"] <= O.integer(expected["notBefore"], 1) <= first_use <= now <
        O.integer(expected["expiresAt"], 1) <= policy["expiresAt"], "COLLECT_ORIGINAL_GRANT_EXPIRED")
    N._check_history(graph)
    match = (A.gate.GateEligibility if step["kind"] == "gate" else A.stages.BootstrapMatch)(raws["original-match"])
    return match


@dataclass(frozen=True, repr=False)
class _CollectInput:
    originals: tuple
    metadata_close: bytes


def _checked_collect_input(value):
    saved = _COLLECT_INPUTS.get(id(value))
    require(type(value) is _CollectInput and type(saved) is tuple and saved[0] is value, "COLLECT_NOT_ORIGINAL_INPUT")
    _, dictionary, originals, close, metadata, anchor, pins, graph, actual = saved
    require(value.__dict__ is dictionary and value.originals is originals and value.metadata_close == close and
        metadata._anchor() is anchor, "COLLECT_INPUT_RETURN_CHANGED")
    N._check_history(graph)
    _collect_actual(actual)
    metadata.structural()
    require(metadata.finished and metadata.failure is None and metadata.owner.closed and not metadata.owner.unknown and
        metadata.owner.original is None and metadata.errors == [] and
        all(a and c for _r, _l, _v, a, c in metadata.rows), "COLLECT_INPUT_CLOSE_UNKNOWN")
    for directory, path, identity in pins:
        require(directory.path is path and tuple(directory.identity) == identity and
            _collect_directory_closed(directory, metadata.owner.first.clock.role) is True, "COLLECT_INPUT_PIN_CHANGED")
    _collect_file_close(close)
    return dict(originals), metadata


def _read_collect_input(clock, kind, actual):
    metadata = _PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
    clock.attach_metadata(metadata)
    failure = None
    try:
        _collect_actual(actual)
        _roots, _handoff, custody = _paths(kind)
        returned = _private(metadata, custody / "returned")
        output = _private(metadata, custody / "export-output")
        _collect_names(metadata, returned, (_EXPORT_STEP_FILE,))
        pins = tuple((directory, directory.path, tuple(directory.identity)) for directory in (returned, output))
        records = (("step", returned, _EXPORT_STEP_FILE), ("carrier", returned, "custody-return.json"),
            ("context", returned, "context.json"), ("manifest", output, native.posix.MANIFEST),
            ("original-match", returned, "original-match.json"), ("fresh-match", returned, "fresh-match.json"),
            ("event", returned, "event.json"), ("policy", returned, "candidate-policy.json"),
            ("public", returned, "recipient-public.asc"))
        originals = tuple((name, _read_private(metadata, directory, leaf, _COLLECT_READ_LIMITS[name]))
            for name, directory, leaf in records)
        graph = N._history_graph(originals, tuple(row[1] for row in pins))
        raws = dict(originals)
        require(O.digest(raws["step"]) == os.environ[_COLLECT_STEP_HASH], "COLLECT_ACTUAL_STEP_HASH")
        parsed = _collect_bundle(raws)
        step, _carrier, context, _manifest = parsed
        require(step["kind"] == kind and step["primary"]["resultSha256"] == os.environ[PRIMARY_RESULT] and
            step["primary"]["handoffSha256"] == os.environ[PRIMARY_HANDOFF] and
            step["cryptoCarrier"]["exporterReturnSha256"] == os.environ[_COLLECT_EXPORT_HASH] and
            step["directoryIdentity"] == list(pins[0][2]) and (context["directories"]["export-output"] is None or
                context["directories"]["export-output"] == list(pins[1][2])), "COLLECT_ACTUAL_PREDECESSOR")
        _collect_host(raws, parsed, clock.clock)
        for name, directory, leaf in records:
            require(_read_private(metadata, directory, leaf, _COLLECT_READ_LIMITS[name]) == raws[name], "COLLECT_INPUT_REREAD")
        _collect_names(metadata, returned, (_EXPORT_STEP_FILE,))
        _collect_actual(actual)
        N._check_history(graph)
        closed = metadata.finish()
        clock.now(final=True)
        result = _CollectInput(originals, closed)
        _COLLECT_INPUTS[id(result)] = (result, result.__dict__, originals, closed, metadata, metadata._anchor(), pins,
            N._history_graph(result.__dict__, metadata.owner.__dict__, tuple(row[1] for row in pins)), actual)
        _checked_collect_input(result)
        return result
    except BaseException as error:
        failure = metadata.remember(error)
    finally:
        if not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
    raise failure


@dataclass(eq=False, repr=False)
class _CollectClockAnchor:
    handle: object
    binding: tuple
    graph: tuple
    last: int
    local_last: float
    metadata: object = None
    metadata_graph: tuple = ()
    frame_binding: object = None
    frame_graph: tuple = ()
    operative: object = None
    phase: str = "METADATA"
    busy: bool = False
    failure: object = None


class _CollectClock:
    """Only the two new POST_EXPORT owners; never restore a historical Window.

    Parent metadata30 and child metadata45 start at their actual FIRST samples.
    Original READ and launch bounds only shorten both ceilings. The frame keeps
    its original work/native-final/read ends unchanged as historical data.
    """
    __slots__ = ("_binding",)

    def __init__(self, first, local, boot, cancelled, *, side):
        require(type(self) is _CollectClock and id(self) not in _COLLECT_CLOCKS and side in ("parent", "child"),
            "COLLECT_CLOCK_NEW")
        graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        local_value(local)
        digest(boot)
        require(callable(cancelled), "COLLECT_CLOCK_CANCEL")
        seconds = 30 if side == "parent" else 45
        end = O.integer(first.nanoseconds + seconds * O.NS)
        local_end = O.wire._directed_deadline(local, seconds, end, first.nanoseconds)
        self._binding = (first, local, boot, cancelled, side, (end, local_end))
        N._check_history(graph)
        _COLLECT_CLOCKS[id(self)] = _CollectClockAnchor(self, self._binding, graph, first.nanoseconds, local)
        self._view()

    def _anchor(self):
        anchor = _COLLECT_CLOCKS.get(id(self))
        require(type(self) is _CollectClock and type(anchor) is _CollectClockAnchor and anchor.handle is self,
            "COLLECT_CLOCK_ORIGINAL_HANDLE")
        return anchor

    @staticmethod
    def _error(anchor, error):
        if anchor.failure is None:
            anchor.failure = error
        return anchor.failure

    def _current(self, anchor):
        require(_COLLECT_CLOCKS.get(id(self)) is anchor and self._binding is anchor.binding and anchor.handle is self,
            "COLLECT_CLOCK_ORIGINAL_BINDING")
        N._check_history(anchor.graph)
        N._check_history(anchor.metadata_graph)
        N._check_history(anchor.frame_graph)
        if anchor.metadata is not None:
            anchor.metadata.structural()
        if anchor.frame_binding is not None and anchor.binding[4] == "parent":
            _checked_collect_input(anchor.frame_binding[0])
        if anchor.frame_binding is not None:
            index = 4 if anchor.binding[4] == "parent" else 6
            require(anchor.frame_binding[index].__dict__ is anchor.frame_binding[index + 1],
                "COLLECT_CLOCK_EXPECTED_DICTIONARY_CHANGED")
        if anchor.operative is not None:
            require(type(anchor.operative) is _CustodyOwner and anchor.operative.fence is self,
                "COLLECT_CLOCK_OPERATIVE_CHANGED")
            anchor.operative.check()

    def _view(self):
        anchor = self._anchor()
        try:
            self._current(anchor)
            return anchor
        except BaseException as error:
            raise self._error(anchor, error)

    @staticmethod
    def _caps(anchor):
        return anchor.binding[5] if anchor.frame_binding is None else anchor.frame_binding[-1]

    reading = property(lambda self: self._view().binding[0])
    clock = property(lambda self: self.reading.clock)
    cancelled = property(lambda self: self._view().binding[3])
    side = property(lambda self: self._view().binding[4])
    first = property(lambda self: self.reading.nanoseconds)
    last = property(lambda self: self._view().last)
    local_end = property(lambda self: self._caps(self._view())[1])
    work = property(lambda self: self._caps(self._view())[0])
    final = property(lambda self: self.work)

    @property
    def frame(self):
        anchor = self._view()
        require(anchor.phase == "OPERATIVE" and anchor.frame_binding is not None, "COLLECT_CLOCK_NOT_BOUND")
        return anchor.frame_binding[1]

    def _begin(self):
        anchor = self._anchor()
        if anchor.failure is not None:
            raise anchor.failure
        try:
            self._current(anchor)
            require(not anchor.busy, "COLLECT_CLOCK_REENTRY")
            anchor.busy = True
            return anchor
        except BaseException as error:
            raise self._error(anchor, error)

    def _local(self, anchor):
        value = local_value(time.monotonic())
        require(value >= anchor.local_last, "COLLECT_LOCAL_BACKWARDS")
        anchor.local_last = value
        self._current(anchor)
        require(value < self._caps(anchor)[1], "COLLECT_LOCAL_EXPIRED")
        return value

    def _observe(self, anchor, minimum, limit):
        end = self._caps(anchor)[0]
        if limit is not None:
            end = min(end, O.integer(limit))
        frontier = max(anchor.last, O.integer(minimum))
        for number in range(2):
            local = self._local(anchor)
            observed = O.clocks.checked_now(anchor.binding[0].clock, minimum_ns=frontier)
            anchor.last = frontier = O.integer(observed, frontier)
            self._current(anchor)
            require(frontier < end and anchor.busy and anchor.failure is None, "COLLECT_RAW_EXPIRED_OR_CHANGED")
            boot = C.boot_digest(anchor.binding[0].clock.role)
            self._current(anchor)
            require(type(boot) is str and boot == anchor.binding[2], "COLLECT_BOOT_CHANGED")
            if number == 0:
                anchor.binding[3]()
                self._current(anchor)
                require(anchor.last == frontier and anchor.local_last == local and anchor.failure is None and anchor.busy,
                    "COLLECT_CALLBACK_CHANGED")
        self._local(anchor)
        self._current(anchor)
        require(anchor.last == frontier and anchor.busy and anchor.failure is None, "COLLECT_FRONTIER_CHANGED")
        return frontier

    def now(self, *, final=False, minimum=0, limit=None):
        anchor = self._begin()
        try:
            require(type(final) is bool, "COLLECT_FINAL_TYPE")
            return self._observe(anchor, minimum, limit)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def deadline(self, maximum, *, final=False, limit=None):
        anchor = self._begin()
        try:
            require(type(final) is bool and type(maximum) in (int, float) and math.isfinite(maximum) and
                0 < maximum <= 900, "COLLECT_MECHANISM_MAXIMUM")
            local = self._local(anchor)
            observed = self._observe(anchor, 0, limit)
            end, local_end = self._caps(anchor)
            if limit is not None:
                end = min(end, O.integer(limit))
            result = min(local_end, O.wire._directed_deadline(local, maximum, end, observed))
            self._current(anchor)
            require(anchor.busy and anchor.failure is None, "COLLECT_DEADLINE_CHANGED")
            return result
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def attach_metadata(self, metadata):
        anchor = self._begin()
        try:
            require(anchor.phase == "METADATA" and anchor.metadata is None and type(metadata) is _PrimaryOwner and
                metadata.owner.fence is self and metadata.owner.first is anchor.binding[0] and
                not metadata.finished and not metadata.rows, "COLLECT_METADATA_ORIGINAL_OWNER")
            anchor.metadata = metadata
            self._current(anchor)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def _bind_begin(self, anchor, side):
        require(anchor.binding[4] == side and anchor.phase == "METADATA" and anchor.frame_binding is None and
            anchor.metadata is not None, "COLLECT_BIND_ONCE")
        anchor.phase = "BINDING"
        metadata = anchor.metadata
        metadata.structural()
        require(metadata.finished and metadata.failure is None and metadata.owner.closed and
            metadata.owner.original is None and not metadata.owner.unknown and metadata.errors == [] and
            all(a and c for _r, _l, _v, a, c in metadata.rows), "COLLECT_BIND_METADATA_NOT_CLOSED")
        anchor.metadata_graph = N._history_graph(metadata.owner.__dict__)
        self._observe(anchor, anchor.last, None)

    def _bind_end(self, anchor, values, frame, end):
        old_end, old_local = self._caps(anchor)
        end = min(old_end, O.integer(end))
        require(anchor.last < end, "COLLECT_BIND_TOO_LATE")
        local_end = min(old_local, O.wire._directed_deadline(anchor.binding[1],
            (end - anchor.binding[0].nanoseconds) / O.NS, end, anchor.binding[0].nanoseconds))
        require(anchor.local_last < local_end, "COLLECT_BIND_LOCAL_EXPIRED")
        anchor.frame_binding = (values[0], frame, *values[1:], (end, local_end))
        anchor.frame_graph = N._history_graph(anchor.frame_binding)
        anchor.phase = "OPERATIVE"
        self._current(anchor)
        self._observe(anchor, anchor.last, end)

    def bind_parent(self, result):
        anchor = self._begin()
        try:
            self._bind_begin(anchor, "parent")
            raws, metadata = _checked_collect_input(result)
            require(metadata is anchor.metadata, "COLLECT_BIND_ORIGINAL_METADATA")
            parsed = _collect_bundle(raws)
            graph = N._history_graph(parsed, raws, result.__dict__)
            step = parsed[0]
            frame = step["originalWindow"]
            require(frame["clock"] == O.clock_value(anchor.binding[0].clock) and frame["originalBootDigest"] == anchor.binding[2] and
                anchor.binding[0].nanoseconds >= step["lowerNs"] and anchor.binding[1] >= step["lowerLocal"],
                "COLLECT_BIND_ORIGINAL_FLOOR")
            expected = _collect_host(raws, parsed, anchor.binding[0].clock)
            pin = _custody_match_pin(expected, step["kind"])
            N._check_history(graph)
            _custody_match_check(pin)
            self._bind_end(anchor, (result, raws, parsed, expected, expected.__dict__), frame, frame["readEndNs"])
            return expected
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def bind_child(self, context_raw, start_raw, event, inherited):
        anchor = self._begin()
        try:
            self._bind_begin(anchor, "child")
            context, start = canonical(context_raw), canonical(start_raw)
            graph = N._history_graph(context, start, inherited)
            _collect_context(context_raw, anchor.binding[0].clock)
            expected = _collect_child_host(context, event, anchor.binding[0], anchor.binding[2])
            pin = _custody_match_pin(expected, context["kind"])
            _collect_start_fields(start_raw, context_raw, context, anchor.binding[0].clock)
            require(type(inherited) is dict and set(inherited) == set(Q._CONTEXT) and inherited == start["inheritedContext"] and
                start["startedNs"] <= anchor.binding[0].nanoseconds < start["workEndNs"], "COLLECT_CHILD_INHERITANCE")
            domain = native.processes.ownership_domains(inherited[native.processes.CHAIN_ENV],
                inherited[native.processes.DOMAINS_ENV])[-1]
            require(domain == {"id": start["invocation"], "job": start["job"], "state": start["state"], "home": start["home"]},
                "COLLECT_CHILD_NATIVE_DOMAIN")
            N._check_history(graph)
            _custody_match_check(pin)
            self._bind_end(anchor, (None, context_raw, context, start_raw, start, expected, expected.__dict__, event, inherited),
                context["originalWindow"], start["workEndNs"])
            return context, start, expected, domain
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def attach_operative(self, owner):
        anchor = self._begin()
        try:
            require(anchor.phase == "OPERATIVE" and anchor.operative is None and type(owner) is _CustodyOwner and
                owner.first is anchor.binding[0] and owner.fence is self and not owner.closed and
                not owner.check().rows and owner._anchor().pending is None, "COLLECT_OPERATIVE_ORIGINAL_OWNER")
            anchor.operative = owner
            self._current(anchor)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False


def _collect_context(raw, clock):
    context = fields(canonical(raw), _COLLECT_CONTEXT_FIELDS, "COLLECT_CONTEXT_FIELDS")
    frame_clock, limits = _custody_authority_frame(context["originalWindow"])
    require(type(context["schema"]) is int and context["schema"] == 1 and
        context["scope"] == native.INITIAL_COLLECT_AUTHORITY_CONTEXT_SCOPE and context["edge"] == "POST_EXPORT" and
        context["kind"] == limits["kind"] and context["root"] == str(ROOT) and frame_clock == clock and
        context["budgetAcceptance"] == "NOT_ADMITTED" and context["exportSaveAuthority"] is False,
        "COLLECT_CONTEXT_SCOPE")
    _collect_service_job(context["originalServiceJob"])
    prior = fields(context["predecessor"], "step outcome stepSha256 cryptoCarrierSha256 exporterReturnSha256", "COLLECT_CONTEXT_PREDECESSOR")
    require(prior["step"] == "initial-custody-export" and prior["outcome"] == "success", "COLLECT_CONTEXT_PREDECESSOR_OUTCOME")
    for name in ("stepSha256", "cryptoCarrierSha256", "exporterReturnSha256"):
        digest(prior[name])
    for name in ("eventSha256", "sourceReturnSha256"):
        digest(context[name])
    began = O.integer(context["parentFirstNs"], limits["startNs"])
    require(context["continuationEndNs"] == min(limits["readEndNs"], began + 30 * O.NS) and
        began <= O.integer(context["sourceReturnedNs"]) < O.integer(context["continuationEndNs"]) and
        type(context["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", context["job"]) and
        type(context["observed"]) is dict and context["observed"]["kind"] == context["kind"] and
        context["observed"]["role"] == clock.role, "COLLECT_CONTEXT_TIME_OR_HOST")
    native.directory_identity(context["directoryIdentity"], clock.role)
    path = _paths(context["kind"])[2] / "authority-2"
    require(context["session"] == str(path), "COLLECT_CONTEXT_FIXED_PATH")
    inherited = context["inheritedContext"]
    require(type(inherited) is dict and all(type(item) is str for item in inherited.values()) and
        (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "COLLECT_CONTEXT_PARENT_DOMAIN")
    expected = context["expectedMatch"]
    fields(expected, " ".join(E.COMMON_MATCH | ({"stage", "selector", "workerAdmission", "qualificationAcceptance"}
        if context["kind"] == "gate" else set())), "COLLECT_CONTEXT_EXPECTED_FIELDS")
    require(expected["firstUseAt"] == context["observed"]["firstUseAt"] and
        expected["source"] == context["observed"]["source"], "COLLECT_CONTEXT_EXPECTED_LINK")
    return context


def _collect_child_host(context, event, first, boot):
    graph = N._history_graph(context, first)
    observed, _primary, actual_event = N.host_context(O.integer(context["observed"]["firstUseAt"], 1))
    require(observed == context["observed"] and type(event) is bytes and event == actual_event and
        O.digest(event) == context["eventSha256"] and context["originalWindow"]["clock"] == O.clock_value(first.clock) and
        context["originalWindow"]["originalBootDigest"] == boot and
        context["parentFirstNs"] <= first.nanoseconds < context["continuationEndNs"], "COLLECT_CHILD_ACTUAL_HOST")
    N._check_history(graph)
    return (A.gate.GateEligibility if context["kind"] == "gate" else A.stages.BootstrapMatch)(O.encoded(context["expectedMatch"]))


def _collect_start_fields(raw, context_raw, context, clock):
    start = fields(canonical(raw), " ".join(native.START_FIELDS), "COLLECT_START_FIELDS")
    graph = N._history_graph(context, start)
    path = _paths(context["kind"])[2] / "authority-2"
    require(type(start["schema"]) is int and start["schema"] == 1 and start["scope"] == native.PHASE_SCOPE and
        start["contextSha256"] == O.digest(context_raw) and start["argv"] == native.phase_command(context_raw) and
        start["cwd"] == str(ROOT) and start["role"] == clock.role and start["job"] == context["job"] and
        start["state"] == str(path) and start["home"] == str(path / "control-home") and
        type(start["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", start["invocation"]) and
        start["exitCode"] is None and start["launchAttempted"] is False and start["scopeAttempted"] is False and
        start["retirement"] == "UNKNOWN", "COLLECT_START")
    began = O.integer(start["startedNs"], context["sourceReturnedNs"])
    require(began < O.integer(start["workEndNs"]) and
        start["workEndNs"] == min(context["continuationEndNs"], began + 45 * O.NS) and
        start["finalEndNs"] == min(context["continuationEndNs"], start["workEndNs"] + 45 * O.NS), "COLLECT_PHASE_CAPS")
    expected = native.processes.ownership_environment(context["inheritedContext"], context["job"], start["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    require(type(start["inheritedContext"]) is dict and
        start["inheritedContext"] == {name: expected[name] for name in Q._CONTEXT}, "COLLECT_START_INHERITANCE")
    N._check_history(graph)
    return start


def _collect_authority_child(context_hash, minimum, cancelled):
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    metadata = owner = clock = result_raw = None
    failure = None
    try:
        local = local_value(time.monotonic())
        first = O.clocks.observe()
        first_graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        require(first.nanoseconds >= O.integer(minimum) and native.processes.host_role() == first.clock.role,
            "COLLECT_CHILD_FIRST_OR_HOST")
        boot = digest(C.boot_digest(first.clock.role))
        N._check_history(first_graph)
        digest(context_hash)
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and
            not any(name in os.environ for name in _CREDENTIAL_NAMES) and callable(cancelled), "COLLECT_CHILD_TOKEN")
        clock = _CollectClock(first, local, boot, cancelled, side="child")
        metadata = _PrimaryOwner(native.Owner(clock.local_end, clock, first=first, cancelled=cancelled))
        clock.attach_metadata(metadata)
        kind, _primary = N.location()
        path = _paths(kind)[2] / "authority-2"
        private = _private(metadata, path)
        service = _private(metadata, path / "service")
        private_pin, service_pin = tuple(private.identity), tuple(service.identity)
        context_raw = _read_private(metadata, private, "context.json", native.LIMIT)
        start_raw = _read_private(metadata, service, "start.json", native.LIMIT)
        require(O.digest(context_raw) == context_hash, "COLLECT_CHILD_CONTEXT_HASH")
        context = _collect_context(context_raw, first.clock)
        require(tuple(context["directoryIdentity"]) == private_pin, "COLLECT_CHILD_CONTEXT_PIN")
        _observed, _root, event = N.host_context(context["observed"]["firstUseAt"])
        inherited = Q._inherited_context()
        metadata_graph = N._history_graph(context, inherited, first)
        metadata_close = metadata.finish()
        metadata_last = clock.now()
        N._check_history(metadata_graph)
        context, start, expected, domain = clock.bind_child(context_raw, start_raw, event, inherited)
        expected_pin = _custody_match_pin(expected, kind)
        require(start["startedNs"] <= minimum <= first.nanoseconds, "COLLECT_CHILD_LAUNCH_MINIMUM")
        owner = _CustodyOwner(clock.local_end, clock, first=first, cancelled=cancelled)
        clock.attach_operative(owner)
        private = owner.open(path)
        service = owner.child(private, "service")
        require(tuple(private.identity) == private_pin and tuple(service.identity) == service_pin and
            owner.read(private, "context.json") == context_raw and owner.read(service, "start.json") == start_raw,
            "COLLECT_CHILD_ORIGINAL_METADATA")
        supplier = None
        query_failure = None
        try:
            supplier = N.query_owner(owner, clock, path / "acquisition-queries")
            N._initial_service_query_git(supplier)
            supplier.native_host_matches_actions()
            def retain(name, raw, *, failed):
                require(name in N.ORIGINAL_KEYS and type(raw) is bytes and type(failed) is bool, "COLLECT_CHILD_ORIGINAL_NAME")
                owner.end(final=failed)
                supplier._write(supplier.private, name + ".bin", raw)
                owner.end(final=failed)
            match, originals = A.acquire_bootstrap(ROOT, kind=kind, query_runner=supplier, invocation=domain["id"],
                token=token, retain=retain, fence=clock, original_work_end=start["workEndNs"],
                first_use_at=context["observed"]["firstUseAt"], expected=expected)
            token = None
            match_pin = _custody_match_pin(match, kind)
            original_graph = N._history_graph(match.__dict__, originals)
            acquired = clock.now(limit=start["workEndNs"])
            _custody_match_check(match_pin)
            _custody_match_check(expected_pin)
            require(type(match) is type(expected) and match.record == expected.record and type(originals) is tuple and
                tuple(name for name, _raw in originals) == N.ORIGINAL_KEYS and all(type(raw) is bytes for _name, raw in originals) and
                dict(originals)["event"] == event, "COLLECT_CHILD_FRESH_MATCH")
        except BaseException as error:
            query_failure = error
        finally:
            token = None
            _custody_finish_queries(owner, supplier, query_failure)
        returned = clock.now(limit=start["workEndNs"])
        N._check_history(original_graph)
        _custody_match_check(match_pin)
        queries = owner.open(path / "acquisition-queries")
        session = N.query_session(owner, queries)
        require(all(owner.read(queries, name + ".bin") == raw for name, raw in originals), "COLLECT_CHILD_ORIGINAL_READBACK")
        _collect_query_index(path / "acquisition-queries", session, dict(originals), context["observed"])
        N._check_history(metadata_graph)
        _custody_match_check(expected_pin)
        result_raw = owner.write(service, "child-result.json", {"schema": 1, "scope": _COLLECT_CHILD_SCOPE,
            "contextSha256": context_hash, "startSha256": O.digest(start_raw), "invocation": domain["id"],
            "clock": O.clock_value(first.clock), "bootDigest": boot, "launchMinimumNs": minimum,
            "beganNs": first.nanoseconds, "metadataLastNs": metadata_last, "acquiredNs": acquired,
            "queryReturnedNs": returned, "querySessionSha256": O.digest(session),
            "originalsSha256": {name: O.digest(raw) for name, raw in originals}, "matchSha256": O.digest(match.record),
            "directoryIdentities": {".": list(private_pin), "service": list(service_pin)},
            "metadataClose": _collect_file_close(metadata_close), "completedNs": clock.now(limit=start["workEndNs"]),
            "retirement": "PENDING_CHILD_CLOSE", "errors": []})
        N._check_history(original_graph)
        _custody_match_check(match_pin)
        clock.now()
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("collect-authority-child", error)
            failure = owner._anchor().failure
        elif metadata is not None:
            failure = metadata.remember(error)
    finally:
        token = None
        if metadata is not None and not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
        if owner is not None:
            if failure is None and owner._anchor().failure is None:
                try:
                    owner.freeze()
                except BaseException as error:
                    owner.error("collect-child-close-roster", error, unknown=True)
            try:
                owner.close()
            except BaseException as error:
                owner.error("collect-child-close", error)
            if failure is None and owner._anchor().failure is not None:
                failure = owner._anchor().failure
    if failure is not None:
        raise failure
    require(owner is not None and clock is not None and result_raw is not None, "COLLECT_CHILD_INCOMPLETE")
    anchor = owner.known()
    N._check_history(metadata_graph)
    N._check_history(original_graph)
    _custody_match_check(expected_pin)
    _custody_match_check(match_pin)
    closed = clock.now(limit=start["workEndNs"])
    owner.known()
    owner_close = {"schema": 1, "scope": "INITIAL_POST_EXPORT_AUTHORITY_CHILD_KNOWN_CLOSE_V1",
        "resources": [{"ordinal": index, "label": label, "closeAttempted": attempted, "closed": ended}
            for index, (_row, label, _resource, attempted, ended) in enumerate(anchor.rows)],
        "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}
    return {"schema": 1, "scope": _COLLECT_ACK_SCOPE, "invocation": domain["id"], "terminalSha256": O.digest(result_raw),
        "clock": O.clock_value(first.clock), "closedNs": closed, "ownerClose": owner_close}, clock, start["workEndNs"]


def _collect_phase_bytes(context_raw, phase, child_raw, clock, private_pin, service_pin):
    """This new phase only; the caller separately proves actual owner-return identity."""
    require(type(phase) is native.OriginalPhase and phase.context == context_raw and type(phase.records) is tuple,
        "COLLECT_PHASE_RETURN_TYPE")
    context = _collect_context(context_raw, clock)
    records = dict(phase.records)
    require(len(phase.records) == len(records) and set(records) == native.PHASE_FILES and
        all(type(raw) is bytes for raw in records.values()), "COLLECT_PHASE_FILES")
    start = _collect_start_fields(records["start.json"], context_raw, context, clock)
    row = fields(canonical(records["result.json"]), " ".join(native.TERMINAL_FIELDS), "COLLECT_TERMINAL_FIELDS")
    birth = fields(canonical(records["native-start.json"]), "ownership leader preparerIdentity observedNs", "COLLECT_BIRTH_FIELDS")
    changed = {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}
    _same({name: row[name] for name in start if name not in changed},
        {name: start[name] for name in start if name not in changed}, "COLLECT_TERMINAL_START")
    require(type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is True and
        row["scopeAttempted"] is True and row["scopeCloseAttempted"] is True and row["scopeClosed"] is True and
        row["retirement"] == "KNOWN" and row["survivors"] == [] and row["errors"] == [] and records["stderr.log"] == b"" and
        row["nativeStartSha256"] == O.digest(records["native-start.json"]) and
        row["baselineSha256"] == O.digest(records["baseline.json"]) and row["leader"] == birth["leader"], "COLLECT_NATIVE_RETURN")
    argv = native.phase_command(context_raw, O.integer(row["launchMinimumNs"], start["startedNs"]))
    _same(row["launchArgv"], argv, "COLLECT_NATIVE_COMMAND")
    native.native_record(row["ownership"], start, row["leader"], argv)
    native.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    _same(birth["ownership"]["launches"], row["ownership"]["launches"], "COLLECT_NATIVE_BIRTH")
    preparer = native.closed_lifetime(row["preparerIdentity"], clock.role)
    require(preparer == native.closed_lifetime(birth["preparerIdentity"], clock.role) and
        preparer["pid"] != row["leader"]["pid"], "COLLECT_NATIVE_PREPARER")
    baseline = native.baseline_record(records["baseline.json"], clock.role)
    if baseline["baseline"] is not None:
        leader = native.lifetime(row["leader"], clock.role)
        require(list(leader[:4] if clock.role.startswith("macos-") else leader) not in baseline["baseline"], "COLLECT_PREEXISTING_LEADER")
    _same(row["captureOutcomes"], {name: {key: True for key in
        ("synced", "verified", "closeAttempted", "closed", "readback")} for name in ("stdout", "stderr")}, "COLLECT_CAPTURE_CLOSE")
    _same(row["captures"], {name: {"sha256": O.digest(records[name + ".log"]), "bytes": len(records[name + ".log"])}
        for name in ("stdout", "stderr")}, "COLLECT_CAPTURE_BYTES")
    child = fields(canonical(child_raw), "schema scope contextSha256 startSha256 invocation clock bootDigest launchMinimumNs "
        "beganNs metadataLastNs acquiredNs queryReturnedNs querySessionSha256 originalsSha256 matchSha256 directoryIdentities "
        "metadataClose completedNs retirement errors", "COLLECT_CHILD_FIELDS")
    ack = fields(canonical(records["stdout.log"]), "schema scope invocation terminalSha256 clock closedNs ownerClose", "COLLECT_ACK_FIELDS")
    require(type(child["schema"]) is int and child["schema"] == 1 and child["scope"] == _COLLECT_CHILD_SCOPE and
        child["contextSha256"] == O.digest(context_raw) and child["startSha256"] == O.digest(records["start.json"]) and
        child["invocation"] == start["invocation"] and child["clock"] == O.clock_value(clock) and
        child["bootDigest"] == context["originalWindow"]["originalBootDigest"] and child["launchMinimumNs"] == row["launchMinimumNs"] and
        child["retirement"] == "PENDING_CHILD_CLOSE" and child["errors"] == [] and
        type(ack["schema"]) is int and ack["schema"] == 1 and ack["scope"] == _COLLECT_ACK_SCOPE and
        ack["invocation"] == start["invocation"] and ack["terminalSha256"] == O.digest(child_raw) and
        ack["clock"] == O.clock_value(clock), "COLLECT_CHILD_ACK")
    _same(child["directoryIdentities"], {".": list(private_pin), "service": list(service_pin)}, "COLLECT_CHILD_PINS")
    metadata = _collect_file_close(O.encoded(child["metadataClose"]))
    _same(metadata["resources"], [{"ordinal": index, "label": label, "closeAttempted": True, "closed": True}
        for index, label in enumerate(("directory", "directory", "reader", "reader"))], "COLLECT_METADATA_ROSTER")
    close = fields(ack["ownerClose"], "schema scope resources retirement exportSaveAuthority", "COLLECT_CHILD_CLOSE_FIELDS")
    require(type(close["schema"]) is int and close["schema"] == 1 and
        close["scope"] == "INITIAL_POST_EXPORT_AUTHORITY_CHILD_KNOWN_CLOSE_V1" and
        close["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and close["exportSaveAuthority"] is False, "COLLECT_CHILD_CLOSE")
    _collect_close_rows(close["resources"], {"directory", "writer"})
    fields(child["originalsSha256"], " ".join(N.ORIGINAL_KEYS), "COLLECT_CHILD_ORIGINAL_HASHES")
    for checksum in (child["querySessionSha256"], child["matchSha256"], *child["originalsSha256"].values()):
        digest(checksum)
    ordered = [row["launchMinimumNs"], *(child[name] for name in
        ("beganNs", "metadataLastNs", "acquiredNs", "queryReturnedNs", "completedNs")), ack["closedNs"], row["completedNs"], row["finalizedNs"]]
    require(all(type(value) is int and O.integer(value) == value for value in ordered) and ordered == sorted(ordered) and
        start["startedNs"] <= ordered[0] and ack["closedNs"] < start["workEndNs"] and row["completedNs"] < start["workEndNs"] and
        row["finalizedNs"] < start["finalEndNs"] and row["launchMinimumNs"] <= O.integer(birth["observedNs"]) <= row["completedNs"],
        "COLLECT_ORIGINAL_PHASE_CHRONOLOGY")
    return start, row, birth, child, ack


def _collect_query_index(path, session_raw, originals, observed, *, source=None):
    """Closed declarations of THIS actual12/24-query return, never old custody."""
    rows, directories = N._gate_query_index(path, session_raw, originals, source=source)
    graph = N._history_graph(originals, observed)
    session = canonical(session_raw, Q.MAX_RECEIPT_BYTES)
    entry = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(I.POLICY_PATH.encode("ascii")) + rb"\x00",
        originals["candidate_policy_entry"])
    require(entry is not None, "COLLECT_QUERY_POLICY_ENTRY")
    blob, commit = entry.group(1).decode("ascii"), observed["source"]["commit"]
    I.sha(commit)
    commands = (("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
        ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--verify", commit + "^{tree}"),
        ("rev-parse", "--is-shallow-repository"), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
        ("rev-parse", "--verify", A.stages.BASE["commit"] + "^{tree}"),
        ("ls-tree", "-z", A.stages.BASE["commit"], "--", I.POLICY_PATH),
        ("merge-base", A.stages.BASE["commit"], commit), ("ls-tree", "-z", commit, "--", I.POLICY_PATH),
        ("cat-file", "-s", blob), ("cat-file", "blob", blob))
    selected = None
    for index, row in enumerate(session["queries"]):
        require(type(row["argv"]) is list and row["argv"] and type(row["argv"][0]) is str, "COLLECT_QUERY_ARGV")
        if selected is None:
            selected = row["argv"][0]
        require(row["argv"] == [selected, "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
            "-C", str(ROOT), *commands[index % 12]], "COLLECT_QUERY_ORIGINAL_COMMAND")
    N._check_history(graph)
    return rows, directories


def _collect_source_pin(source):
    N._source_pin(source)
    return source, source.__dict__, source.records, source.session, source.raw, N._history_graph(source)


def _collect_source_current(pin):
    source, dictionary, records, session, raw, graph = pin
    require(type(source) is N.SourceReturn and source.__dict__ is dictionary and source.records is records and
        source.session == session and source.raw == raw, "COLLECT_SOURCE_RETURN_CHANGED")
    N._check_history(graph)


def _collect_phase_pin(phase):
    N._phase_pin(phase)
    return phase, phase.__dict__, phase.context, phase.records, N._history_graph(phase)


def _collect_phase_current(pin):
    phase, dictionary, context, records, graph = pin
    require(type(phase) is native.OriginalPhase and phase.__dict__ is dictionary and phase.context == context and
        phase.records is records, "COLLECT_PHASE_RETURN_CHANGED")
    N._check_history(graph)


def _collect_predecessor(raws, step):
    return {"step": "initial-custody-export", "outcome": "success", "stepSha256": O.digest(raws["step"]),
        "cryptoCarrierSha256": step["cryptoCarrier"]["sha256"],
        "exporterReturnSha256": step["cryptoCarrier"]["exporterReturnSha256"]}


def _collect_read_authority(owner, private, before, phase, clock, input_result, expected):
    """Actual new phase/source/query readback; original prior SUCCESS is data only."""
    before_pin, phase_pin, expected_pin = _collect_source_pin(before), _collect_phase_pin(phase), \
        _custody_match_pin(expected, clock.frame["kind"])
    raws, _metadata = _checked_collect_input(input_result)
    step, _carrier, old_context, _manifest = _collect_bundle(raws)
    context_raw = phase.context
    context = _collect_context(context_raw, clock.clock)
    graph = N._history_graph(context, raws)
    require(type(owner) is _CustodyOwner and owner.fence is clock and owner.phase_originals is phase and
        context["originalWindow"] == clock.frame == step["originalWindow"] and
        context["originalServiceJob"] == step["originalServiceJob"] and context["observed"] == old_context["observed"] and
        context["predecessor"] == _collect_predecessor(raws, step) and
        O.encoded(context["expectedMatch"]) == expected.record == raws["original-match"] and
        owner.read(private, "context.json") == context_raw and tuple(context["directoryIdentity"]) == tuple(private.identity),
        "COLLECT_CURRENT_CONTEXT")
    policy = N.source_readback(owner, private.path / "source-before", before)
    require(context["sourceReturnSha256"] == O.digest(before.raw) and
        context["sourceReturnedNs"] == canonical(before.raw)["returnedNs"], "COLLECT_CURRENT_SOURCE_RETURN")
    _collect_query_index(private.path / "source-before", before.session, dict(before.records), context["observed"], source=before)
    service = owner.child(private, "service")
    for name, raw in phase.records:
        maximum = native.ACK_LIMIT if name == "stdout.log" else native.STDERR_LIMIT if name == "stderr.log" else native.LIMIT
        require(owner.read(service, name, maximum) == raw, "COLLECT_CURRENT_PHASE_BYTES")
    child_raw = owner.read(service, "child-result.json")
    start, row, birth, child, ack = _collect_phase_bytes(context_raw, phase, child_raw, clock.clock,
        tuple(private.identity), tuple(service.identity))
    queries = owner.open(private.path / "acquisition-queries")
    session = N.query_session(owner, queries)
    originals = tuple((name, owner.read(queries, name + ".bin")) for name in N.ORIGINAL_KEYS)
    original = dict(originals)
    captured = (context_raw, originals, start["invocation"], start["startedNs"], start["workEndNs"])
    captured_graph = N._history_graph(captured)
    require(child["querySessionSha256"] == O.digest(session) and child["originalsSha256"] ==
        {name: O.digest(raw) for name, raw in originals} and child["matchSha256"] == O.digest(original["match"]) and
        original["event"] == raws["event"] and {name: original[name] for name in N.SOURCE_KEYS} == policy and
        original["candidate_policy_raw"] == raws["policy"] and original["match"] == expected.record,
        "COLLECT_CURRENT_ORIGINALS")
    _collect_query_index(private.path / "acquisition-queries", session, original, context["observed"])
    match, service_time = N.retained_match(context, original, start["invocation"], clock.clock,
        start["startedNs"], start["workEndNs"])
    match_pin = _custody_match_pin(match, context["kind"])
    match_graph = N._history_graph(match.__dict__, service_time)
    require(type(match) is type(expected) and match.record == expected.record and
        list(N._service_job(captured, clock.clock)) == step["originalServiceJob"], "COLLECT_CURRENT_MATCH_OR_ORIGINAL_JOB")
    minimum = N._service_chain_minimum(clock.first, context["sourceReturnedNs"], start, row, birth, child, service_time, ack)
    checked = clock.now(minimum=minimum)
    _collect_source_current(before_pin)
    _collect_phase_current(phase_pin)
    _custody_match_check(expected_pin)
    _custody_match_check(match_pin)
    N._check_history(graph)
    N._check_history(captured_graph)
    N._check_history(match_graph)
    owner.check()
    require(owner.phase_originals is phase, "COLLECT_CURRENT_PHASE_OWNER")
    authority = {"contextSha256": O.digest(context_raw), "sourceBeforeSha256": O.digest(before.raw),
        "expectedMatchSha256": O.digest(expected.record), "freshMatchSha256": O.digest(match.record),
        "originalsSha256": {name: O.digest(raw) for name, raw in originals}, "querySessionSha256": O.digest(session),
        "phaseSha256": {name: O.digest(raw) for name, raw in phase.records}, "childSha256": O.digest(child_raw),
        "ackSha256": O.digest(dict(phase.records)["stdout.log"]), "invocation": start["invocation"],
        "startedNs": start["startedNs"], "workEndNs": start["workEndNs"], "finalEndNs": start["finalEndNs"],
        "acquiredNs": child["acquiredNs"], "checkedNs": checked}
    return match, captured, authority, child_raw, session


@dataclass(frozen=True, repr=False)
class _CollectAuthority:
    """This second-Step episode's actual known-close, never exported originals."""
    input: object
    raw: bytes
    originals: tuple


def _collect_authority(input_result, clock, expected, token):
    attempt = _collect_begin("post-export-authority")
    attempt.update(input=input_result, clock=clock, owner=None)
    owner = None
    failure = None
    source_links, source_pins, graphs, match_pins, directory_pins = (), (), (), (), ()
    phase = phase_pin = None
    try:
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and
            not any(name in os.environ for name in _CREDENTIAL_NAMES) and type(clock) is _CollectClock and
            clock.side == "parent", "COLLECT_AUTHORITY_TOKEN_OR_CLOCK")
        raws, _metadata = _checked_collect_input(input_result)
        parsed = _collect_bundle(raws)
        step, _carrier, old_context, _manifest = parsed
        expected_pin = _custody_match_pin(expected, step["kind"])
        match_pins = (expected_pin,)
        graphs = (N._history_graph(raws, parsed),)
        require(expected.record == raws["original-match"] and clock.frame == step["originalWindow"], "COLLECT_AUTHORITY_INPUT")
        owner = _CustodyOwner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled)
        attempt["owner"] = owner
        clock.attach_operative(owner)
        anchor, dictionary = owner._anchor(), owner.__dict__
        def current():
            require(_COLLECT_ATTEMPTS.get("post-export-authority") is attempt and attempt["input"] is input_result and
                attempt["clock"] is clock and attempt["owner"] is owner and attempt["state"] in ("STARTED", "RETURNED") and
                attempt["failure"] is None and owner.__dict__ is dictionary and owner._anchor() is anchor,
                "COLLECT_AUTHORITY_ORIGINAL_ATTEMPT")
            _checked_collect_input(input_result)
            owner.check()
            require(owner.original is None and not owner.unknown and owner.errors == [] and
                set(owner.initial_sources) == {name for name, _source in source_links} and
                all(owner.initial_sources[name] is source for name, source in source_links) and owner.phase_originals is phase,
                "COLLECT_AUTHORITY_ORIGINAL_OWNER")
            for pin in source_pins:
                _collect_source_current(pin)
            if phase_pin is not None:
                _collect_phase_current(phase_pin)
            for pin in match_pins:
                _custody_match_check(pin)
            for graph in graphs:
                N._check_history(graph)
            if directory_pins:
                N._check_worker_pins(directory_pins, clock.reading.clock.role, closed=owner.closed)
        current()
        custody = _paths(step["kind"])[2]
        root = owner.open(custody)
        require(native._initializer_names(owner, root) == ("authority-1", "copied-evidence", "export-output", "public-crypto", "returned"),
            "COLLECT_CUSTODY_INITIAL_ROSTER")
        path = custody / "authority-2"
        private = owner.child(root, "authority-2", create=True)
        private_pin = tuple(private.identity)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        before = N.source_queries(owner, clock, old_context["observed"], path / "source-before")
        source_links = ((str(path / "source-before"), before),)
        source_pins = (_collect_source_pin(before),)
        current()
        policy = N.source_readback(owner, path / "source-before", before)
        require(policy["candidate_policy_raw"] == raws["policy"], "COLLECT_POST_EXPORT_POLICY_CHANGED")
        _collect_query_index(path / "source-before", before.session, policy, old_context["observed"], source=before)
        inherited = Q._inherited_context()
        context = {"schema": 1, "scope": native.INITIAL_COLLECT_AUTHORITY_CONTEXT_SCOPE, "edge": "POST_EXPORT",
            "kind": step["kind"], "root": str(ROOT), "session": str(path), "job": uuid.uuid4().hex,
            "observed": old_context["observed"], "originalWindow": step["originalWindow"],
            "originalServiceJob": step["originalServiceJob"], "predecessor": _collect_predecessor(raws, step),
            "expectedMatch": canonical(expected.record, A.stages.LIMIT), "eventSha256": O.digest(raws["event"]),
            "sourceReturnSha256": O.digest(before.raw), "sourceReturnedNs": canonical(before.raw)["returnedNs"],
            "inheritedContext": inherited, "directoryIdentity": list(private_pin), "parentFirstNs": clock.first,
            "continuationEndNs": clock.work, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        graphs = (*graphs, N._history_graph(context, inherited))
        context_raw = O.encoded(context)
        _collect_context(context_raw, clock.clock)
        current()
        require(owner.write(private, "context.json", context_raw) == context_raw, "COLLECT_CONTEXT_WRITE")
        _directory, returned_phase = N._initial_service_phase(owner, private, context_raw, token, clock, before)
        phase = returned_phase
        phase_pin = _collect_phase_pin(phase)
        token = None
        current()
        first_match, first_captured, _chain, _child, _session = _collect_read_authority(
            owner, private, before, phase, clock, input_result, expected)
        match_pins = (*match_pins, _custody_match_pin(first_match, step["kind"]))
        graphs = (*graphs, N._history_graph(first_captured))
        current()
        after = N.source_queries(owner, clock, old_context["observed"], path / "source-after")
        source_links = (*source_links, (str(path / "source-after"), after))
        source_pins = (*source_pins, _collect_source_pin(after))
        current()
        require(N.source_readback(owner, path / "source-after", after) == policy, "COLLECT_FINAL_SOURCE_CHANGED")
        _collect_query_index(path / "source-after", after.session, dict(after.records), old_context["observed"], source=after)
        match, captured, authority, child_raw, session_raw = _collect_read_authority(
            owner, private, before, phase, clock, input_result, expected)
        match_pin = _custody_match_pin(match, step["kind"])
        match_pins = (*match_pins, match_pin)
        require(captured == first_captured, "COLLECT_FRESH_ORIGINALS_CHANGED")
        authority["sourceAfterSha256"] = O.digest(after.raw)
        files = [("context.json", context_raw), ("service/child-result.json", child_raw),
            ("acquisition-queries/session-result.json", session_raw)]
        files.extend(("service/" + name, raw) for name, raw in phase.records)
        files.extend(("acquisition-queries/" + name + ".bin", raw) for name, raw in captured[1])
        for name, source in (("source-before", before), ("source-after", after)):
            files.extend(((name + "/source-return.json", source.raw), (name + "/session-result.json", source.session)))
            files.extend((name + "/" + key + ".bin", raw) for key, raw in source.records)
        originals = tuple(files)
        graphs = (*graphs, N._history_graph(captured, authority, originals))
        directory_pins = N._worker_pins(owner, clock.clock.role, {".": path, **{name: path / name for name in
            ("control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")}})
        current()
        require(tuple(private.identity) == private_pin and native._initializer_names(owner, root) ==
            ("authority-1", "authority-2", "copied-evidence", "export-output", "public-crypto", "returned"),
            "COLLECT_PARENT_FINAL_ROSTER")
        preclose = clock.now()
        current()
        owner.freeze()
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("collect-authority-parent", error)
            failure = owner._anchor().failure
    finally:
        token = None
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                owner.error("collect-authority-parent-close", error)
            if failure is None and owner._anchor().failure is not None:
                failure = owner._anchor().failure
    try:
        if failure is not None:
            raise failure
        require(owner is not None and owner._anchor() is anchor, "COLLECT_AUTHORITY_INCOMPLETE")
        owner.known()
        current()
        closed = clock.now(minimum=preclose)
        current()
        parent_close = {"schema": 1, "scope": "INITIAL_POST_EXPORT_AUTHORITY_PARENT_KNOWN_CLOSE_V1",
            "resources": [{"ordinal": index, "label": label, "closeAttempted": attempted, "closed": ended}
                for index, (_row, label, _resource, attempted, ended) in enumerate(anchor.rows)],
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}
        final_authority = {**authority, "closedNs": closed}
        raw = O.encoded({"schema": 1, "scope": "INITIAL_POST_EXPORT_AUTHORITY_CLOSED_RETURN_V1", "edge": "POST_EXPORT",
            "authority": final_authority, "parentClose": parent_close, "preCloseNs": preclose, "closedNs": closed,
            "testAcceptance": "NOT_PERFORMED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        canonical(raw)
        result = _CollectAuthority(input_result, raw, originals)
        saved = (result, result.__dict__, input_result, raw, originals, clock, owner, anchor, dictionary, current,
            N._history_graph(result.__dict__, captured, final_authority, parent_close), match_pin, captured, attempt)
        _COLLECT_AUTHORITY_RETURNS[id(result)] = saved
        attempt["return"], attempt["state"] = result, "RETURNED"
        _checked_collect_authority(result)
        return result
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def _checked_collect_authority(result):
    """Passive original new episode graph/known-close, not a new remote query."""
    saved = _COLLECT_AUTHORITY_RETURNS.get(id(result))
    require(type(result) is _CollectAuthority and type(saved) is tuple and saved[0] is result,
        "COLLECT_NOT_ORIGINAL_AUTHORITY_RETURN")
    _, dictionary, inputs, raw, originals, clock, owner, anchor, owner_dictionary, current, graph, match_pin, captured, attempt = saved
    try:
        require(result.__dict__ is dictionary and result.input is inputs and result.raw == raw and result.originals is originals and
            attempt["state"] == "RETURNED" and attempt["return"] is result and attempt["failure"] is None,
            "COLLECT_AUTHORITY_RETURN_CHANGED")
        N._check_history(graph)
        current()
        require(owner.__dict__ is owner_dictionary and owner._anchor() is anchor and clock._view().failure is None,
            "COLLECT_AUTHORITY_OWNER_CHANGED")
        owner.known()
        match = _custody_match_check(match_pin)
        return clock, inputs, raw, originals, match, captured
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def _collect_authority_currency(result):
    clock, inputs, raw, originals, original_match, captured = _checked_collect_authority(result)
    pin = _custody_match_pin(original_match, clock.frame["kind"])
    raws, _metadata = _checked_collect_input(inputs)
    parsed = _collect_bundle(raws)
    graph = N._history_graph(raws, parsed, captured)
    expected = _collect_host(raws, parsed, clock.clock)
    expected_pin = _custody_match_pin(expected, parsed[0]["kind"])
    context_raw, acquisition_raws, invocation, began, end = captured
    match, _service = N.retained_match(canonical(context_raw), dict(acquisition_raws), invocation, clock.clock, began, end)
    fresh_pin = _custody_match_pin(match, parsed[0]["kind"])
    require(type(match) is type(original_match) is type(expected) and match.record == original_match.record == expected.record,
        "COLLECT_LATE_GRANT_CHANGED")
    clock.now()
    _custody_match_check(pin)
    _custody_match_check(expected_pin)
    _custody_match_check(fresh_pin)
    N._check_history(graph)
    _checked_collect_authority(result)
    return clock, inputs, raw, originals


def _collect_pre_metadata(kind, cancelled):
    """The sole second-Step token holder returns no secret/closure to metadata."""
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    try:
        local = local_value(time.monotonic())
        first = O.clocks.observe()
        graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        boot = digest(C.boot_digest(first.clock.role))
        N._check_history(graph)
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and callable(cancelled) and
            not native.QUARANTINE and not Q.QUARANTINE and not C.QUARANTINE and not native.diagnostics._QUARANTINE and
            native.processes.host_role() == first.clock.role, "COLLECT_SECOND_TOKEN_OR_UNKNOWN")
        actual = _collect_actual()
        clock = _CollectClock(first, local, boot, cancelled, side="parent")
        inputs = _read_collect_input(clock, kind, actual)
        expected = clock.bind_parent(inputs)
        return _collect_authority(inputs, clock, expected, token)
    finally:
        token = None


def _collect_authority_record(raw, frame):
    value = fields(canonical(raw), "schema scope edge authority parentClose preCloseNs closedNs testAcceptance "
        "budgetAcceptance exportSaveAuthority", "COLLECT_AUTHORITY_RECORD_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == "INITIAL_POST_EXPORT_AUTHORITY_CLOSED_RETURN_V1" and value["edge"] == "POST_EXPORT" and
        value["testAcceptance"] == "NOT_PERFORMED" and value["budgetAcceptance"] == "NOT_ADMITTED" and
        value["exportSaveAuthority"] is False, "COLLECT_AUTHORITY_RECORD_SCOPE")
    authority = fields(value["authority"], "contextSha256 sourceBeforeSha256 sourceAfterSha256 expectedMatchSha256 freshMatchSha256 "
        "originalsSha256 querySessionSha256 phaseSha256 childSha256 ackSha256 invocation startedNs workEndNs finalEndNs "
        "acquiredNs checkedNs closedNs", "COLLECT_AUTHORITY_BINDING_FIELDS")
    for name in ("contextSha256", "sourceBeforeSha256", "sourceAfterSha256", "expectedMatchSha256", "freshMatchSha256",
            "querySessionSha256", "childSha256", "ackSha256"):
        digest(authority[name])
    fields(authority["originalsSha256"], " ".join(N.ORIGINAL_KEYS), "COLLECT_AUTHORITY_ORIGINAL_HASH_FIELDS")
    fields(authority["phaseSha256"], " ".join(native.PHASE_FILES), "COLLECT_AUTHORITY_PHASE_HASH_FIELDS")
    for checksum in (*authority["originalsSha256"].values(), *authority["phaseSha256"].values()):
        digest(checksum)
    require(authority["freshMatchSha256"] == authority["expectedMatchSha256"] == authority["originalsSha256"]["match"] and
        authority["ackSha256"] == authority["phaseSha256"]["stdout.log"] and type(authority["invocation"]) is str and
        re.fullmatch(r"[0-9a-f]{32}", authority["invocation"]), "COLLECT_AUTHORITY_HASH_LINKS")
    times = [authority[name] for name in ("startedNs", "acquiredNs", "checkedNs")]
    times.extend((value["preCloseNs"], value["closedNs"]))
    require(all(type(item) is int and O.integer(item) == item for item in times) and times == sorted(times) and
        frame["startNs"] <= times[0] and authority["closedNs"] == value["closedNs"] < frame["readEndNs"] and
        times[0] < O.integer(authority["workEndNs"]) <= O.integer(authority["finalEndNs"]) <= frame["readEndNs"] and
        authority["acquiredNs"] < authority["workEndNs"], "COLLECT_AUTHORITY_RECORD_TIME")
    close = fields(value["parentClose"], "schema scope resources retirement exportSaveAuthority", "COLLECT_PARENT_CLOSE_FIELDS")
    require(type(close["schema"]) is int and close["schema"] == 1 and
        close["scope"] == "INITIAL_POST_EXPORT_AUTHORITY_PARENT_KNOWN_CLOSE_V1" and
        close["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and close["exportSaveAuthority"] is False,
        "COLLECT_PARENT_CLOSE_SCOPE")
    _collect_close_rows(close["resources"], {"directory", "writer", "native-scope", "stdout", "stderr"})
    return value


@dataclass(frozen=True, repr=False)
class _CollectClosed:
    authority: object
    raw: bytes
    metadata_close: bytes


def _collect_final_record(raw, inputs, authority_raw):
    value = fields(canonical(raw), "schema scope kind edge predecessor primary originalWindow lastNs lastLocal authority parentClose "
        "writerReturn originalStepOutcome testAcceptance productiveAuthority cacheAuthority budgetAcceptance exportSaveAuthority",
        "COLLECT_FINAL_FIELDS")
    raws, _metadata = _checked_collect_input(inputs)
    step = _collect_step_record(raws["step"])
    authority = _collect_authority_record(authority_raw, step["originalWindow"])
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == _COLLECT_SCOPE and
        value["kind"] == step["kind"] and value["edge"] == "POST_EXPORT" and
        value["predecessor"] == _collect_predecessor(raws, step) and value["primary"] == step["primary"] and
        value["originalWindow"] == step["originalWindow"] and value["authority"] == authority["authority"] and
        value["parentClose"] == authority["parentClose"] and
        authority["closedNs"] <= O.integer(value["lastNs"]) < step["originalWindow"]["readEndNs"] and
        local_value(value["lastLocal"]) >= step["lowerLocal"], "COLLECT_FINAL_ORIGINAL_LINKS")
    _collect_pending(value)
    return value


def _collect_final_readback(metadata, returned, output, raws):
    names = (("step", returned, _EXPORT_STEP_FILE), ("carrier", returned, "custody-return.json"),
        ("context", returned, "context.json"), ("manifest", output, native.posix.MANIFEST),
        ("original-match", returned, "original-match.json"), ("fresh-match", returned, "fresh-match.json"),
        ("event", returned, "event.json"), ("policy", returned, "candidate-policy.json"), ("public", returned, "recipient-public.asc"))
    for name, directory, leaf in names:
        require(_read_private(metadata, directory, leaf, _COLLECT_READ_LIMITS[name]) == raws[name], "COLLECT_FINAL_PRIOR_BYTES_CHANGED")


def _collect_closed(authority_result):
    attempt = _collect_begin("collect-final")
    attempt["authority"] = authority_result
    metadata = None
    failure = None
    try:
        clock, inputs, authority_raw, _originals = _collect_authority_currency(authority_result)
        raws, _prior_metadata = _checked_collect_input(inputs)
        step = _collect_step_record(raws["step"])
        authority = _collect_authority_record(authority_raw, step["originalWindow"])
        graph = N._history_graph(authority_result.__dict__, raws, step, authority)
        authority_dictionary = authority_result.__dict__
        last = clock.now()
        last_local = clock._view().local_last
        metadata = _PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
        paths = _crypto_directory_paths(step["kind"])
        returned, output = _private(metadata, paths["returned"]), _private(metadata, paths["export-output"])
        pins = tuple((directory, directory.path, tuple(directory.identity)) for directory in (returned, output))
        original_pins = _COLLECT_INPUTS[id(inputs)][6]
        require(all(pin[1:] == original[1:] for pin, original in zip(pins, original_pins)), "COLLECT_FINAL_ORIGINAL_DIRECTORY_PINS")
        _collect_names(metadata, returned, (_EXPORT_STEP_FILE,))
        _collect_final_readback(metadata, returned, output, raws)
        raw = O.encoded({"schema": 1, "scope": _COLLECT_SCOPE, "kind": step["kind"], "edge": "POST_EXPORT",
            "predecessor": _collect_predecessor(raws, step), "primary": step["primary"], "originalWindow": step["originalWindow"],
            "lastNs": last, "lastLocal": last_local, "authority": authority["authority"], "parentClose": authority["parentClose"],
            "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED", "testAcceptance": "NOT_PERFORMED",
            "productiveAuthority": False, "cacheAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _collect_final_record(raw, inputs, authority_raw)
        _collect_write(metadata, returned, _COLLECT_FILE, raw)
        _collect_names(metadata, returned, (_EXPORT_STEP_FILE, _COLLECT_FILE))
        _collect_final_readback(metadata, returned, output, raws)
        N._check_history(graph)
        require(authority_result.__dict__ is authority_dictionary, "COLLECT_FINAL_AUTHORITY_CHANGED")
        _collect_authority_currency(authority_result)
        closed = metadata.finish()
        clock.now(final=True)
        result = _CollectClosed(authority_result, raw, closed)
        saved = (result, result.__dict__, authority_result, authority_dictionary, inputs, raw, closed, clock,
            metadata, metadata._anchor(), pins, attempt,
            N._history_graph(result.__dict__, metadata.owner.__dict__, tuple(pin[1] for pin in pins)), graph)
        _COLLECT_RETURNS[id(result)] = saved
        attempt["return"], attempt["state"] = result, "RETURNED"
        _checked_collect_closed(result)
        return result
    except BaseException as error:
        failure = error if metadata is None else metadata.remember(error)
    finally:
        if metadata is not None and not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
        if failure is not None:
            if attempt["failure"] is None:
                attempt["failure"] = failure
            attempt["state"] = "FAILED"
    raise attempt["failure"]


def _checked_collect_closed(result):
    saved = _COLLECT_RETURNS.get(id(result))
    require(type(result) is _CollectClosed and type(saved) is tuple and saved[0] is result,
        "COLLECT_NOT_ORIGINAL_FINAL_RETURN")
    _, dictionary, authority, authority_dictionary, inputs, raw, closed, clock, metadata, anchor, pins, attempt, graph, input_graph = saved
    try:
        def current():
            require(type(result) is _CollectClosed and type(authority) is _CollectAuthority and
                _COLLECT_RETURNS.get(id(result)) is saved and _COLLECT_ATTEMPTS.get("collect-final") is attempt and
                attempt["state"] == "RETURNED" and attempt["return"] is result and attempt["authority"] is authority and
                attempt["failure"] is None and result.__dict__ is dictionary and result.authority is authority and
                result.raw == raw and result.metadata_close == closed and authority.__dict__ is authority_dictionary and
                metadata._anchor() is anchor, "COLLECT_FINAL_RETURN_CHANGED")
            N._check_history(graph)
            N._check_history(input_graph)
            metadata.structural()
            require(metadata.finished and metadata.failure is None and metadata.owner.closed and not metadata.owner.unknown and
                metadata.owner.original is None and metadata.errors == [] and all(a and c for _row, _label, _resource, a, c in metadata.rows),
                "COLLECT_FINAL_WRITER_CLOSE_UNKNOWN")
            for directory, path, identity in pins:
                require(directory.path is path and tuple(directory.identity) == identity and
                    _collect_directory_closed(directory, clock.clock.role) is True, "COLLECT_FINAL_PIN_CHANGED")
        current()
        currency = _collect_authority_currency(authority)
        current()
        require(currency[0] is clock and currency[1] is inputs, "COLLECT_FINAL_CURRENCY_CHANGED")
        _collect_file_close(closed)
        value = _collect_final_record(raw, inputs, currency[2])
        return clock, value["originalWindow"]["readEndNs"], {"initialCustodySha256": O.digest(raw),
            "initialExporterReturnSha256": value["predecessor"]["exporterReturnSha256"]}
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


class _CollectOutputFence:
    """Exactly one registered result, one actual append and two late OUTPUT checks."""
    __slots__ = ("_binding",)

    def __init__(self, result):
        require(type(self) is _CollectOutputFence and id(self) not in _COLLECT_OUTPUTS, "COLLECT_OUTPUT_NEW")
        require(type(result) in (_ExportStep, _CollectClosed), "COLLECT_OUTPUT_ORIGINAL_TYPE")
        registry = _EXPORT_STEPS if type(result) is _ExportStep else _COLLECT_RETURNS
        returned = registry.get(id(result))
        require(type(returned) is tuple and returned[0] is result and
            not any(saved[1][0] is result for saved in _COLLECT_OUTPUTS.values()), "COLLECT_OUTPUT_RETURN_REUSE")
        clock, limit, values = (_checked_export_step(result) if type(result) is _ExportStep else _checked_collect_closed(result))
        value = {"schema": 1, "scope": "INITIAL_CUSTODY_DIGESTS_PENDING_ORIGINAL_STEP_RETURN_V1", **values,
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        self._binding = (result, registry, returned, result.__dict__, clock, limit, values, value, N._history_graph(values, value))
        _COLLECT_OUTPUTS[id(self)] = (self, self._binding, {"phase": "NEW", "checks": 0, "busy": False, "failure": None})

    def _original(self):
        saved = _COLLECT_OUTPUTS.get(id(self))
        require(type(self) is _CollectOutputFence and type(saved) is tuple and saved[0] is self,
            "COLLECT_OUTPUT_ORIGINAL_FACADE")
        return saved

    @staticmethod
    def _fail(saved, error):
        state = saved[2]
        if state["failure"] is None:
            state["failure"] = error
        return state["failure"]

    def _begin(self):
        saved = self._original()
        if saved[2]["failure"] is not None:
            raise saved[2]["failure"]
        try:
            require(self._binding is saved[1] and not saved[2]["busy"], "COLLECT_OUTPUT_REENTRY_OR_BINDING")
            saved[2]["busy"] = True
            return saved
        except BaseException as error:
            raise self._fail(saved, error)

    def _current(self, saved):
        require(self._original() is saved and self._binding is saved[1] and saved[2]["busy"] and
            saved[2]["failure"] is None, "COLLECT_OUTPUT_CHANGED")
        result, registry, returned, dictionary, clock, limit, values, value, graph = saved[1]
        require(registry.get(id(result)) is returned and result.__dict__ is dictionary and not C.QUARANTINE and
            not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE, "COLLECT_OUTPUT_RETURN_CHANGED")
        N._check_history(graph)
        current = _checked_export_step(result) if type(result) is _ExportStep else _checked_collect_closed(result)
        require(current[0] is clock and type(current[1]) is int and current[1] == limit and current[2] == values,
            "COLLECT_OUTPUT_ORIGINAL_DIGESTS")
        N._check_history(graph)
        require(self._original() is saved and self._binding is saved[1] and saved[2]["busy"] and saved[2]["failure"] is None and
            registry.get(id(result)) is returned and result.__dict__ is dictionary, "COLLECT_OUTPUT_CALLBACK_CHANGED")
        return clock, limit, values, value

    def _append_guard(self):
        saved = self._begin()
        try:
            require(saved[2]["phase"] == "APPENDING" and saved[2]["checks"] == 0, "COLLECT_OUTPUT_APPEND_PHASE")
            clock, limit, _values, _value = self._current(saved)
            clock.now(final=True, limit=limit)
            self._current(saved)
        except BaseException as error:
            raise self._fail(saved, error)
        finally:
            saved[2]["busy"] = False

    def append(self):
        saved = self._begin()
        try:
            require(saved[2]["phase"] == "NEW" and saved[2]["checks"] == 0, "COLLECT_OUTPUT_APPEND_ONCE")
            _clock, limit, values, value = self._current(saved)
            saved[2]["phase"] = "APPENDING"
        except BaseException as error:
            raise self._fail(saved, error)
        finally:
            saved[2]["busy"] = False
        try:
            C.append_outputs(values, self._append_guard)
            self._append_guard()
            require(self._original() is saved and saved[2]["phase"] == "APPENDING" and saved[2]["failure"] is None,
                "COLLECT_OUTPUT_APPEND_RETURN_CHANGED")
            saved[2]["phase"] = "OUTPUT"
            return value, self, limit
        except BaseException as error:
            raise self._fail(saved, error)

    def now(self, *, final=False, minimum=0, limit=None):
        saved = self._begin()
        try:
            require(saved[2]["phase"] == "OUTPUT" and type(final) is bool and final is True and
                type(minimum) is int and minimum == 0 and type(limit) is int and limit == saved[1][5] and
                type(saved[2]["checks"]) is int and 0 <= saved[2]["checks"] < 2, "COLLECT_OUTPUT_EXACT_LATE_CHECK")
            saved[2]["checks"] += 1
            clock, original_limit, _values, _value = self._current(saved)
            observed = clock.now(final=True, limit=original_limit)
            self._current(saved)
            return observed
        except BaseException as error:
            raise self._fail(saved, error)
        finally:
            saved[2]["busy"] = False


def collect_export(kind, cancelled):
    attempt = _collect_begin("collect-export-entry")
    try:
        primary, authority = _export_pre_crypto(kind, cancelled)
        # No token ever existed in this frame. Do not merge these calls into a
        # transaction retaining the pre-crypto helper's credential across them.
        result = custody_crypto(primary, authority)
        carrier = _custody_crypto_carrier(result)
        transfer = _retain_crypto_step(carrier)
        output = _CollectOutputFence(transfer).append()
        require(_COLLECT_ATTEMPTS.get("collect-export-entry") is attempt and attempt["state"] == "STARTED" and
            attempt["failure"] is None, "COLLECT_EXPORT_ENTRY_CHANGED")
        attempt["state"] = "RETURNED"
        return output
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def collect_close(kind, cancelled):
    attempt = _collect_begin("collect-close-entry")
    try:
        authority = _collect_pre_metadata(kind, cancelled)
        closed = _collect_closed(authority)
        output = _CollectOutputFence(closed).append()
        require(_COLLECT_ATTEMPTS.get("collect-close-entry") is attempt and attempt["state"] == "STARTED" and
            attempt["failure"] is None, "COLLECT_CLOSE_ENTRY_CHANGED")
        attempt["state"] = "RETURNED"
        return output
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


# Seal is a NEW trusted Step. Its historical input files neither renew READ nor
# restore an old Window/owner/Recipient. The terminal transport self-tail is not
# part of the already frozen encrypted packet. Only SEAL is implemented here.
_TAIL_OUTCOME = "P2PKIT_INITIAL_CUSTODY_OUTCOME"
_TAIL_HASH = "P2PKIT_INITIAL_CUSTODY_SHA256"
_TAIL_EXPORT_HASH = "P2PKIT_INITIAL_CUSTODY_EXPORTER_RETURN_SHA256"
_TAIL_NAMES = (*_COLLECT_NAMES, _TAIL_OUTCOME, _TAIL_HASH, _TAIL_EXPORT_HASH)
_TAIL_LIMITS = {**_COLLECT_READ_LIMITS, "collect": native.LIMIT}
_TAIL_CONTEXT_FIELDS = "schema scope edge kind root session job observed originalWindow originalServiceJob " \
    "predecessor expectedMatch eventSha256 sourceReturnSha256 sourceReturnedNs inheritedContext directoryIdentity " \
    "parentFirstNs continuationEndNs budgetAcceptance exportSaveAuthority"
_TAIL_CHILD_SCOPE = "INITIAL_SEAL_AUTHORITY_PENDING_CHILD_CLOSE_V1"
_TAIL_ACK_SCOPE = "INITIAL_SEAL_AUTHORITY_ORIGINAL_POST_CLOSE_ACK_V1"
_TAIL_SEAL_SCOPE = "INITIAL_RECIPIENT_SEAL_PENDING_ORIGINAL_STEP_RETURN_V1"
_TAIL_ATTEMPTS, _TAIL_INPUTS, _TAIL_CLOCKS = {}, {}, {}
_TAIL_AUTHORITIES, _TAIL_SEALS, _TAIL_OUTPUTS = {}, {}, {}


def _tail_begin(name):
    require(name in ("seal-entry", "seal-authority", "seal-record"), "TAIL_ATTEMPT_NAME")
    previous = _TAIL_ATTEMPTS.get(name)
    if previous is not None:
        if previous["failure"] is None:
            previous["failure"] = O.OriginError("INITIAL_CUSTODY_TAIL_ATTEMPT_REUSE")
        previous["state"] = "FAILED"
        raise previous["failure"]
    result = {"state": "STARTED", "failure": None, "return": None}
    _TAIL_ATTEMPTS[name] = result
    return result


def _tail_actual(expected=None):
    _collect_actual()
    actual = tuple(os.environ.get(name) for name in _TAIL_NAMES)
    require((expected is None or type(expected) is tuple and actual == expected) and
        os.environ.get(_TAIL_OUTCOME) == "success", "TAIL_ACTUAL_COLLECT_SUCCESS")
    digest(os.environ.get(_TAIL_HASH))
    require(digest(os.environ.get(_TAIL_EXPORT_HASH)) == os.environ[_COLLECT_EXPORT_HASH],
        "TAIL_ACTUAL_EXPORTER_HASH")
    return actual


def _tail_roster(stage):
    require(stage in ("INPUT", "AUTHORITY", "SEALED"), "TAIL_ROOT_STAGE")
    names = ("authority-1", "authority-2", "copied-evidence", "export-output", "public-crypto", "returned")
    if stage != "INPUT":
        names += ("authority-seal",)
    if stage == "SEALED":
        names += ("seal",)
    return tuple(sorted(names))


def _tail_directory_names(metadata, directory):
    require(type(metadata) is _PrimaryOwner, "TAIL_FILE_OWNER")
    end = metadata.guard()
    directory.verify()
    if metadata.owner.first.clock.role == "windows-x64":
        names = directory.names(max_names=32, deadline=end)
    else:
        names = []
        with os.scandir(directory.path) as entries:
            for entry in entries:
                require(len(names) < 32, "TAIL_DIRECTORY_LIMIT")
                names.append(entry.name)
    require(len(names) == len(set(names)) == len(set(name.casefold() for name in names)), "TAIL_DIRECTORY_ALIAS")
    directory.verify()
    metadata.guard()
    return tuple(sorted(names))


def _tail_collect_record(raw, raws, step):
    """Historical collect Step DATA, not its unpersisted live authority return."""
    value = fields(canonical(raw), "schema scope kind edge predecessor primary originalWindow lastNs lastLocal authority parentClose "
        "writerReturn originalStepOutcome testAcceptance productiveAuthority cacheAuthority budgetAcceptance exportSaveAuthority",
        "TAIL_COLLECT_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == _COLLECT_SCOPE and
        value["kind"] == step["kind"] and value["edge"] == "POST_EXPORT" and
        value["predecessor"] == _collect_predecessor(raws, step) and value["primary"] == step["primary"] and
        value["originalWindow"] == step["originalWindow"], "TAIL_COLLECT_LINKS")
    _collect_pending(value)
    authority = fields(value["authority"], "contextSha256 sourceBeforeSha256 sourceAfterSha256 expectedMatchSha256 freshMatchSha256 "
        "originalsSha256 querySessionSha256 phaseSha256 childSha256 ackSha256 invocation startedNs workEndNs finalEndNs "
        "acquiredNs checkedNs closedNs", "TAIL_COLLECT_AUTHORITY_FIELDS")
    for name in ("contextSha256", "sourceBeforeSha256", "sourceAfterSha256", "expectedMatchSha256", "freshMatchSha256",
            "querySessionSha256", "childSha256", "ackSha256"):
        digest(authority[name])
    fields(authority["originalsSha256"], " ".join(N.ORIGINAL_KEYS), "TAIL_COLLECT_ORIGINAL_HASHES")
    fields(authority["phaseSha256"], " ".join(native.PHASE_FILES), "TAIL_COLLECT_PHASE_HASHES")
    for checksum in (*authority["originalsSha256"].values(), *authority["phaseSha256"].values()):
        digest(checksum)
    require(authority["freshMatchSha256"] == authority["expectedMatchSha256"] ==
        authority["originalsSha256"]["match"] == O.digest(raws["original-match"]) and
        authority["originalsSha256"]["event"] == O.digest(raws["event"]) and
        authority["originalsSha256"]["candidate_policy_raw"] == O.digest(raws["policy"]) and
        authority["ackSha256"] == authority["phaseSha256"]["stdout.log"] and type(authority["invocation"]) is str and
        re.fullmatch(r"[0-9a-f]{32}", authority["invocation"]), "TAIL_COLLECT_AUTHORITY_LINKS")
    frame = step["originalWindow"]
    times = [authority[name] for name in ("startedNs", "acquiredNs", "checkedNs", "closedNs")]
    times.append(value["lastNs"])
    require(all(type(item) is int and O.integer(item) == item for item in times) and times == sorted(times) and
        step["lowerNs"] <= times[0] and times[-1] < frame["readEndNs"] and
        times[0] < O.integer(authority["workEndNs"]) == O.integer(authority["finalEndNs"]) <= frame["readEndNs"] and
        authority["acquiredNs"] < authority["workEndNs"] and times[-1] < authority["finalEndNs"] and
        local_value(value["lastLocal"]) >= step["lowerLocal"], "TAIL_COLLECT_TIME")
    close = fields(value["parentClose"], "schema scope resources retirement exportSaveAuthority", "TAIL_COLLECT_CLOSE_FIELDS")
    require(type(close["schema"]) is int and close["schema"] == 1 and
        close["scope"] == "INITIAL_POST_EXPORT_AUTHORITY_PARENT_KNOWN_CLOSE_V1" and
        close["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and close["exportSaveAuthority"] is False, "TAIL_COLLECT_CLOSE")
    _collect_close_rows(close["resources"], {"directory", "writer", "native-scope", "stdout", "stderr"})
    return value


def _tail_bundle(raws):
    require(type(raws) is dict and set(raws) == set(_TAIL_LIMITS) and
        all(type(raws[name]) is bytes and 0 < len(raws[name]) <= maximum for name, maximum in _TAIL_LIMITS.items()),
        "TAIL_INPUT_ROSTER_OR_LIMIT")
    prior = {name: raws[name] for name in _COLLECT_READ_LIMITS}
    parsed = _collect_bundle(prior)
    collected = _tail_collect_record(raws["collect"], prior, parsed[0])
    return (*parsed, collected)


def _tail_host(raws, parsed, clock):
    # Includes real bounded event/host and wall-time checks, but NO HTTP query.
    return _collect_host({name: raws[name] for name in _COLLECT_READ_LIMITS}, parsed[:4], clock)


def _tail_predecessor(raws, step):
    return {"step": "initial-custody", "outcome": "success", "collectSha256": O.digest(raws["collect"]),
        "cryptoStepSha256": O.digest(raws["step"]), "cryptoCarrierSha256": O.digest(raws["carrier"]),
        "exporterReturnSha256": step["cryptoCarrier"]["exporterReturnSha256"]}


@dataclass(frozen=True, repr=False)
class _TailInput:
    originals: tuple
    metadata_close: bytes


def _checked_tail_input(value):
    saved = _TAIL_INPUTS.get(id(value))
    require(type(value) is _TailInput and type(saved) is tuple and saved[0] is value, "TAIL_NOT_ORIGINAL_INPUT")
    _, dictionary, originals, close, metadata, anchor, pins, graph, actual = saved
    require(value.__dict__ is dictionary and value.originals is originals and value.metadata_close == close and
        metadata._anchor() is anchor, "TAIL_INPUT_CHANGED")
    N._check_history(graph)
    _tail_actual(actual)
    metadata.structural()
    require(metadata.finished and metadata.failure is None and metadata.owner.closed and not metadata.owner.unknown and
        metadata.owner.original is None and metadata.errors == [] and
        all(a and c for _r, _l, _v, a, c in metadata.rows), "TAIL_INPUT_CLOSE_UNKNOWN")
    for directory, path, identity in pins:
        require(directory.path is path and tuple(directory.identity) == identity and
            _collect_directory_closed(directory, metadata.owner.first.clock.role) is True, "TAIL_INPUT_PIN_CHANGED")
    _collect_file_close(close)
    return dict(originals), metadata


def _tail_records(returned, output):
    return (("step", returned, _EXPORT_STEP_FILE), ("carrier", returned, "custody-return.json"),
        ("context", returned, "context.json"), ("manifest", output, native.posix.MANIFEST),
        ("original-match", returned, "original-match.json"), ("fresh-match", returned, "fresh-match.json"),
        ("event", returned, "event.json"), ("policy", returned, "candidate-policy.json"),
        ("public", returned, "recipient-public.asc"), ("collect", returned, _COLLECT_FILE))


def _tail_readback(metadata, records, raws):
    for name, directory, leaf in records:
        require(_read_private(metadata, directory, leaf, _TAIL_LIMITS[name]) == raws[name], "TAIL_INPUT_REREAD")


def _read_tail_input(clock, kind, actual):
    metadata = _PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
    clock.attach_metadata(metadata)
    failure = None
    try:
        _tail_actual(actual)
        custody = _paths(kind)[2]
        returned = _private(metadata, custody / "returned")
        step_raw = _read_private(metadata, returned, _EXPORT_STEP_FILE, native.LIMIT)
        require(O.digest(step_raw) == os.environ[_COLLECT_STEP_HASH], "TAIL_ACTUAL_CRYPTO_STEP_HASH")
        # The first reader is already KNOWN closed. Narrow both clocks BEFORE
        # all carrier/context/manifest/host reads. This is not operative binding.
        clock.narrow_parent(step_raw)
        root, output = _private(metadata, custody), _private(metadata, custody / "export-output")
        pins = tuple((directory, directory.path, tuple(directory.identity)) for directory in (root, returned, output))
        require(_tail_directory_names(metadata, root) == _tail_roster("INPUT"), "TAIL_INITIAL_ROOT_ROSTER")
        _collect_names(metadata, returned, (_EXPORT_STEP_FILE, _COLLECT_FILE))
        records = _tail_records(returned, output)
        originals = tuple((name, step_raw if name == "step" else _read_private(metadata, directory, leaf, _TAIL_LIMITS[name]))
            for name, directory, leaf in records)
        graph = N._history_graph(originals, tuple(row[1] for row in pins))
        raws = dict(originals)
        parsed = _tail_bundle(raws)
        step, _carrier, context, _manifest, _collected = parsed
        require(step["kind"] == kind and step["primary"]["resultSha256"] == os.environ[PRIMARY_RESULT] and
            step["primary"]["handoffSha256"] == os.environ[PRIMARY_HANDOFF] and
            step["cryptoCarrier"]["exporterReturnSha256"] == os.environ[_TAIL_EXPORT_HASH] and
            O.digest(raws["collect"]) == os.environ[_TAIL_HASH] and
            step["directoryIdentity"] == list(pins[1][2]) and
            (context["directories"]["export-output"] is None or context["directories"]["export-output"] == list(pins[2][2])),
            "TAIL_ACTUAL_PREDECESSOR_OR_HISTORICAL_PIN")
        _tail_host(raws, parsed, clock.clock)
        _tail_readback(metadata, records, raws)
        _collect_names(metadata, returned, (_EXPORT_STEP_FILE, _COLLECT_FILE))
        require(_tail_directory_names(metadata, root) == _tail_roster("INPUT"), "TAIL_FINAL_INPUT_ROOT_ROSTER")
        _tail_actual(actual)
        N._check_history(graph)
        closed = metadata.finish()
        clock.now(final=True)
        result = _TailInput(originals, closed)
        _TAIL_INPUTS[id(result)] = (result, result.__dict__, originals, closed, metadata, metadata._anchor(), pins,
            N._history_graph(result.__dict__, metadata.owner.__dict__, tuple(row[1] for row in pins)), actual)
        _checked_tail_input(result)
        return result
    except BaseException as error:
        failure = metadata.remember(error)
    finally:
        if not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
    raise failure


@dataclass(eq=False, repr=False)
class _TailClockAnchor:
    handle: object
    binding: tuple
    graph: tuple
    last: int
    local_last: float
    metadata: object = None
    metadata_graph: tuple = ()
    narrowed: object = None
    narrow_graph: tuple = ()
    bound: object = None
    bound_graph: tuple = ()
    operative: object = None
    phase: str = "METADATA"
    busy: bool = False
    failure: object = None


class _TailClock:
    """Fresh seal owner, bounded by FIRST observations and old absolute seal end.

    No historical live clock is accepted. Metadata narrowing is one-shot and
    cannot grant operative authority. Native Owner.local_end stays immutable;
    effective RAW/LOCAL caps only shrink, including cleanup and output checks.
    """
    __slots__ = ("_binding",)

    def __init__(self, first, local, boot, cancelled, *, side):
        require(type(self) is _TailClock and id(self) not in _TAIL_CLOCKS and side in ("parent", "child"), "TAIL_CLOCK_NEW")
        graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        local_value(local)
        digest(boot)
        require(callable(cancelled), "TAIL_CLOCK_CANCEL")
        seconds = 30 if side == "parent" else 45
        end = O.integer(first.nanoseconds + seconds * O.NS)
        local_end = O.wire._directed_deadline(local, seconds, end, first.nanoseconds)
        self._binding = (first, local, boot, cancelled, side, (end, local_end))
        N._check_history(graph)
        _TAIL_CLOCKS[id(self)] = _TailClockAnchor(self, self._binding, graph, first.nanoseconds, local)
        self._view()

    def _anchor(self):
        anchor = _TAIL_CLOCKS.get(id(self))
        require(type(self) is _TailClock and type(anchor) is _TailClockAnchor and anchor.handle is self, "TAIL_CLOCK_HANDLE")
        return anchor

    @staticmethod
    def _error(anchor, error):
        if anchor.failure is None:
            anchor.failure = error
        return anchor.failure

    def _current(self, anchor):
        require(_TAIL_CLOCKS.get(id(self)) is anchor and self._binding is anchor.binding and anchor.handle is self,
            "TAIL_CLOCK_BINDING_CHANGED")
        for graph in (anchor.graph, anchor.metadata_graph, anchor.narrow_graph, anchor.bound_graph):
            N._check_history(graph)
        if anchor.metadata is not None:
            anchor.metadata.structural()
        if anchor.bound is not None:
            if anchor.binding[4] == "parent":
                _checked_tail_input(anchor.bound[0])
            _custody_match_check(anchor.bound[-1])
        if anchor.operative is not None:
            require(type(anchor.operative) is _CustodyOwner and anchor.operative.fence is self, "TAIL_OPERATIVE_CHANGED")
            anchor.operative.check()

    def _view(self):
        anchor = self._anchor()
        try:
            self._current(anchor)
            return anchor
        except BaseException as error:
            raise self._error(anchor, error)

    @staticmethod
    def _caps(anchor):
        return anchor.binding[5] if anchor.narrowed is None else anchor.narrowed[-1]

    reading = property(lambda self: self._view().binding[0])
    clock = property(lambda self: self.reading.clock)
    cancelled = property(lambda self: self._view().binding[3])
    side = property(lambda self: self._view().binding[4])
    first = property(lambda self: self.reading.nanoseconds)
    last = property(lambda self: self._view().last)
    local_end = property(lambda self: self._caps(self._view())[1])
    work = property(lambda self: self._caps(self._view())[0])
    final = property(lambda self: self.work)

    @property
    def frame(self):
        anchor = self._view()
        require(anchor.phase == "OPERATIVE" and anchor.bound is not None, "TAIL_CLOCK_NOT_BOUND")
        return anchor.narrowed[2]

    def _begin(self):
        anchor = self._anchor()
        if anchor.failure is not None:
            raise anchor.failure
        try:
            self._current(anchor)
            require(not anchor.busy, "TAIL_CLOCK_REENTRY")
            anchor.busy = True
            return anchor
        except BaseException as error:
            raise self._error(anchor, error)

    def _local(self, anchor):
        value = local_value(time.monotonic())
        require(value >= anchor.local_last, "TAIL_LOCAL_BACKWARDS")
        anchor.local_last = value
        self._current(anchor)
        require(value < self._caps(anchor)[1], "TAIL_LOCAL_EXPIRED")
        return value

    def _observe(self, anchor, minimum, limit):
        end = self._caps(anchor)[0]
        if limit is not None:
            end = min(end, O.integer(limit))
        frontier = max(anchor.last, O.integer(minimum))
        for number in range(2):
            local = self._local(anchor)
            observed = O.clocks.checked_now(anchor.binding[0].clock, minimum_ns=frontier)
            anchor.last = frontier = O.integer(observed, frontier)
            self._current(anchor)
            require(frontier < end and anchor.busy and anchor.failure is None, "TAIL_RAW_EXPIRED_OR_CHANGED")
            boot = C.boot_digest(anchor.binding[0].clock.role)
            self._current(anchor)
            require(type(boot) is str and boot == anchor.binding[2], "TAIL_BOOT_CHANGED")
            if number == 0:
                anchor.binding[3]()
                self._current(anchor)
                require(anchor.last == frontier and anchor.local_last == local and anchor.failure is None and anchor.busy,
                    "TAIL_CALLBACK_CHANGED")
        self._local(anchor)
        self._current(anchor)
        require(anchor.last == frontier and anchor.busy and anchor.failure is None, "TAIL_FRONTIER_CHANGED")
        return frontier

    def now(self, *, final=False, minimum=0, limit=None):
        anchor = self._begin()
        try:
            require(type(final) is bool, "TAIL_FINAL_TYPE")
            return self._observe(anchor, minimum, limit)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def deadline(self, maximum, *, final=False, limit=None):
        anchor = self._begin()
        try:
            require(type(final) is bool and type(maximum) in (int, float) and math.isfinite(maximum) and
                0 < maximum <= 900, "TAIL_MECHANISM_MAXIMUM")
            local = self._local(anchor)
            observed = self._observe(anchor, 0, limit)
            end, local_end = self._caps(anchor)
            if limit is not None:
                end = min(end, O.integer(limit))
            result = min(local_end, O.wire._directed_deadline(local, maximum, end, observed))
            self._current(anchor)
            require(anchor.busy and anchor.failure is None, "TAIL_DEADLINE_CHANGED")
            return result
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def attach_metadata(self, metadata):
        anchor = self._begin()
        try:
            require(anchor.phase == "METADATA" and anchor.metadata is None and type(metadata) is _PrimaryOwner and
                metadata.owner.fence is self and metadata.owner.first is anchor.binding[0] and
                not metadata.finished and not metadata.rows, "TAIL_METADATA_ORIGINAL_OWNER")
            anchor.metadata = metadata
            self._current(anchor)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def _narrow(self, anchor, side, raw, value, frame, end):
        require(anchor.phase == "METADATA" and anchor.narrowed is None and anchor.bound is None and
            anchor.binding[4] == side and anchor.metadata is not None and not anchor.metadata.finished,
            "TAIL_NARROW_ONCE_BEFORE_BINDING")
        # Exactly the first fixed directory and its KNOWN-closed first reader.
        rows = anchor.metadata.rows
        require(len(rows) == 2 and tuple(row[1] for row in rows) == ("directory", "reader") and
            rows[0][3:] == (False, False) and rows[1][3:] == (True, True), "TAIL_FIRST_READER_NOT_CLOSED")
        old_end, old_local = self._caps(anchor)
        end = min(old_end, O.integer(end))
        require(anchor.binding[0].nanoseconds < end and frame["clock"] == O.clock_value(anchor.binding[0].clock) and
            frame["originalBootDigest"] == anchor.binding[2], "TAIL_NARROW_ORIGINAL_CLOCK_OR_END")
        local_end = min(old_local, O.wire._directed_deadline(anchor.binding[1],
            (end - anchor.binding[0].nanoseconds) / O.NS, end, anchor.binding[0].nanoseconds))
        anchor.narrowed = (raw, value, frame, (end, local_end))
        anchor.narrow_graph = N._history_graph(anchor.narrowed)
        anchor.phase = "NARROWED"
        self._current(anchor)
        self._observe(anchor, anchor.last, end)

    def narrow_parent(self, step_raw):
        anchor = self._begin()
        try:
            require(O.digest(step_raw) == os.environ.get(_COLLECT_STEP_HASH), "TAIL_NARROW_ACTUAL_STEP_HASH")
            step = _collect_step_record(step_raw)
            require(anchor.binding[0].nanoseconds >= step["lowerNs"] and anchor.binding[1] >= step["lowerLocal"],
                "TAIL_NARROW_ORIGINAL_FLOOR")
            self._narrow(anchor, "parent", step_raw, step, step["originalWindow"], step["originalWindow"]["sealEndNs"])
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def narrow_child(self, context_raw):
        anchor = self._begin()
        try:
            context = _tail_context(context_raw, anchor.binding[0].clock)
            require(context["parentFirstNs"] <= anchor.binding[0].nanoseconds, "TAIL_CHILD_PARENT_FLOOR")
            self._narrow(anchor, "child", context_raw, context, context["originalWindow"], context["continuationEndNs"])
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def _bind_begin(self, anchor, side):
        require(anchor.binding[4] == side and anchor.phase == "NARROWED" and anchor.bound is None and
            anchor.metadata is not None, "TAIL_BIND_ONCE")
        anchor.phase = "BINDING"
        metadata = anchor.metadata
        metadata.structural()
        require(metadata.finished and metadata.failure is None and metadata.owner.closed and
            metadata.owner.original is None and not metadata.owner.unknown and metadata.errors == [] and
            all(a and c for _r, _l, _v, a, c in metadata.rows), "TAIL_BIND_METADATA_NOT_CLOSED")
        anchor.metadata_graph = N._history_graph(metadata.owner.__dict__)
        self._observe(anchor, anchor.last, None)

    def bind_parent(self, result):
        anchor = self._begin()
        try:
            self._bind_begin(anchor, "parent")
            raws, metadata = _checked_tail_input(result)
            require(metadata is anchor.metadata and raws["step"] == anchor.narrowed[0], "TAIL_BIND_ORIGINAL_METADATA")
            parsed = _tail_bundle(raws)
            require(parsed[0] == anchor.narrowed[1] and anchor.binding[0].nanoseconds >= parsed[4]["lastNs"] and
                anchor.binding[1] >= parsed[4]["lastLocal"], "TAIL_BIND_COLLECT_FLOORS")
            expected = _tail_host(raws, parsed, anchor.binding[0].clock)
            pin = _custody_match_pin(expected, parsed[0]["kind"])
            anchor.bound = (result, raws, parsed, pin)
            anchor.bound_graph = N._history_graph(anchor.bound)
            anchor.phase = "OPERATIVE"
            self._current(anchor)
            self._observe(anchor, anchor.last, None)
            return expected
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def bind_child(self, context_raw, start_raw, event, inherited):
        anchor = self._begin()
        try:
            self._bind_begin(anchor, "child")
            context, start = _tail_context(context_raw, anchor.binding[0].clock), canonical(start_raw)
            require(context_raw == anchor.narrowed[0], "TAIL_CHILD_ORIGINAL_CONTEXT")
            expected = _tail_child_host(context, event, anchor.binding[0], anchor.binding[2])
            _tail_start_fields(start_raw, context_raw, context, anchor.binding[0].clock)
            require(type(inherited) is dict and set(inherited) == set(Q._CONTEXT) and inherited == start["inheritedContext"] and
                start["startedNs"] <= anchor.binding[0].nanoseconds < start["workEndNs"] and
                start["workEndNs"] == anchor.narrowed[-1][0], "TAIL_CHILD_INHERITANCE_OR_CAP")
            domain = native.processes.ownership_domains(inherited[native.processes.CHAIN_ENV],
                inherited[native.processes.DOMAINS_ENV])[-1]
            require(domain == {"id": start["invocation"], "job": start["job"], "state": start["state"], "home": start["home"]},
                "TAIL_CHILD_NATIVE_DOMAIN")
            pin = _custody_match_pin(expected, context["kind"])
            anchor.bound = (None, context_raw, context, start_raw, start, event, inherited, pin)
            anchor.bound_graph = N._history_graph(anchor.bound)
            anchor.phase = "OPERATIVE"
            self._current(anchor)
            self._observe(anchor, anchor.last, None)
            return context, start, expected, domain
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def attach_operative(self, owner):
        anchor = self._begin()
        try:
            require(anchor.phase == "OPERATIVE" and anchor.operative is None and type(owner) is _CustodyOwner and
                owner.first is anchor.binding[0] and owner.fence is self and not owner.closed and
                owner.original is None and not owner.unknown and owner.resources == [], "TAIL_OPERATIVE_ORIGINAL_OWNER")
            anchor.operative = owner
            self._current(anchor)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False


def _tail_context(raw, clock):
    context = fields(canonical(raw), _TAIL_CONTEXT_FIELDS, "TAIL_CONTEXT_FIELDS")
    frame_clock, limits = _custody_authority_frame(context["originalWindow"])
    require(type(context["schema"]) is int and context["schema"] == 1 and
        context["scope"] == native.INITIAL_TAIL_AUTHORITY_CONTEXT_SCOPE and context["edge"] == "SEAL" and
        context["kind"] == limits["kind"] and context["root"] == str(ROOT) and frame_clock == clock and
        context["budgetAcceptance"] == "NOT_ADMITTED" and context["exportSaveAuthority"] is False,
        "TAIL_CONTEXT_SCOPE")
    _collect_service_job(context["originalServiceJob"])
    prior = fields(context["predecessor"], "step outcome collectSha256 cryptoStepSha256 cryptoCarrierSha256 exporterReturnSha256",
        "TAIL_CONTEXT_PREDECESSOR")
    require(prior["step"] == "initial-custody" and prior["outcome"] == "success", "TAIL_CONTEXT_PREDECESSOR_OUTCOME")
    for name in ("collectSha256", "cryptoStepSha256", "cryptoCarrierSha256", "exporterReturnSha256"):
        digest(prior[name])
    for name in ("eventSha256", "sourceReturnSha256"):
        digest(context[name])
    began = O.integer(context["parentFirstNs"], limits["startNs"])
    require(context["continuationEndNs"] == min(limits["sealEndNs"], began + 30 * O.NS) and
        began <= O.integer(context["sourceReturnedNs"]) < O.integer(context["continuationEndNs"]) and
        type(context["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", context["job"]) and
        type(context["observed"]) is dict and context["observed"]["kind"] == context["kind"] and
        context["observed"]["role"] == clock.role, "TAIL_CONTEXT_TIME_OR_HOST")
    native.directory_identity(context["directoryIdentity"], clock.role)
    require(context["session"] == str(_paths(context["kind"])[2] / "authority-seal"), "TAIL_CONTEXT_FIXED_PATH")
    inherited = context["inheritedContext"]
    require(type(inherited) is dict and all(type(item) is str for item in inherited.values()) and
        (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "TAIL_CONTEXT_PARENT_DOMAIN")
    expected = context["expectedMatch"]
    fields(expected, " ".join(E.COMMON_MATCH | ({"stage", "selector", "workerAdmission", "qualificationAcceptance"}
        if context["kind"] == "gate" else set())), "TAIL_CONTEXT_EXPECTED_FIELDS")
    require(expected["firstUseAt"] == context["observed"]["firstUseAt"] and
        expected["source"] == context["observed"]["source"], "TAIL_CONTEXT_EXPECTED_LINK")
    return context


def _tail_child_host(context, event, first, boot):
    graph = N._history_graph(context, first)
    observed, _primary, actual_event = N.host_context(O.integer(context["observed"]["firstUseAt"], 1))
    require(observed == context["observed"] and type(event) is bytes and event == actual_event and
        O.digest(event) == context["eventSha256"] and context["originalWindow"]["clock"] == O.clock_value(first.clock) and
        context["originalWindow"]["originalBootDigest"] == boot and
        context["parentFirstNs"] <= first.nanoseconds < context["continuationEndNs"], "TAIL_CHILD_ACTUAL_HOST")
    N._check_history(graph)
    return (A.gate.GateEligibility if context["kind"] == "gate" else A.stages.BootstrapMatch)(O.encoded(context["expectedMatch"]))


def _tail_start_fields(raw, context_raw, context, clock):
    start = fields(canonical(raw), " ".join(native.START_FIELDS), "TAIL_START_FIELDS")
    graph = N._history_graph(context, start)
    path = _paths(context["kind"])[2] / "authority-seal"
    require(type(start["schema"]) is int and start["schema"] == 1 and start["scope"] == native.PHASE_SCOPE and
        start["contextSha256"] == O.digest(context_raw) and start["argv"] == native.phase_command(context_raw) and
        start["cwd"] == str(ROOT) and start["role"] == clock.role and start["job"] == context["job"] and
        start["state"] == str(path) and start["home"] == str(path / "control-home") and
        type(start["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", start["invocation"]) and
        start["exitCode"] is None and start["launchAttempted"] is False and start["scopeAttempted"] is False and
        start["retirement"] == "UNKNOWN", "TAIL_START")
    began = O.integer(start["startedNs"], context["sourceReturnedNs"])
    require(began < O.integer(start["workEndNs"]) and
        start["workEndNs"] == min(context["continuationEndNs"], began + 45 * O.NS) and
        start["finalEndNs"] == min(context["continuationEndNs"], start["workEndNs"] + 45 * O.NS), "TAIL_PHASE_CAPS")
    expected = native.processes.ownership_environment(context["inheritedContext"], context["job"], start["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    require(type(start["inheritedContext"]) is dict and
        start["inheritedContext"] == {name: expected[name] for name in Q._CONTEXT}, "TAIL_START_INHERITANCE")
    N._check_history(graph)
    return start


def _tail_authority_child(context_hash, minimum, cancelled):
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    metadata = owner = clock = result_raw = None
    failure = None
    try:
        local = local_value(time.monotonic())
        first = O.clocks.observe()
        first_graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        require(first.nanoseconds >= O.integer(minimum) and native.processes.host_role() == first.clock.role,
            "TAIL_CHILD_FIRST_OR_HOST")
        boot = digest(C.boot_digest(first.clock.role))
        N._check_history(first_graph)
        digest(context_hash)
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and
            not any(name in os.environ for name in _CREDENTIAL_NAMES) and callable(cancelled), "TAIL_CHILD_TOKEN")
        clock = _TailClock(first, local, boot, cancelled, side="child")
        metadata = _PrimaryOwner(native.Owner(clock.local_end, clock, first=first, cancelled=cancelled))
        clock.attach_metadata(metadata)
        kind, _primary = N.location()
        path = _paths(kind)[2] / "authority-seal"
        private = _private(metadata, path)
        private_pin = tuple(private.identity)
        context_raw = _read_private(metadata, private, "context.json", native.LIMIT)
        require(O.digest(context_raw) == context_hash, "TAIL_CHILD_CONTEXT_HASH")
        clock.narrow_child(context_raw)
        service = _private(metadata, path / "service")
        service_pin = tuple(service.identity)
        start_raw = _read_private(metadata, service, "start.json", native.LIMIT)
        context = _tail_context(context_raw, first.clock)
        require(tuple(context["directoryIdentity"]) == private_pin, "TAIL_CHILD_CONTEXT_PIN")
        _observed, _root, event = N.host_context(context["observed"]["firstUseAt"])
        inherited = Q._inherited_context()
        metadata_graph = N._history_graph(context, inherited, first)
        metadata_close = metadata.finish()
        metadata_last = clock.now()
        N._check_history(metadata_graph)
        context, start, expected, domain = clock.bind_child(context_raw, start_raw, event, inherited)
        expected_pin = _custody_match_pin(expected, kind)
        require(start["startedNs"] <= minimum <= first.nanoseconds, "TAIL_CHILD_LAUNCH_MINIMUM")
        owner = _CustodyOwner(clock.local_end, clock, first=first, cancelled=cancelled)
        clock.attach_operative(owner)
        private = owner.open(path)
        service = owner.child(private, "service")
        require(tuple(private.identity) == private_pin and tuple(service.identity) == service_pin and
            owner.read(private, "context.json") == context_raw and owner.read(service, "start.json") == start_raw,
            "TAIL_CHILD_ORIGINAL_METADATA")
        supplier = None
        query_failure = None
        try:
            supplier = N.query_owner(owner, clock, path / "acquisition-queries")
            N._initial_service_query_git(supplier)
            supplier.native_host_matches_actions()
            def retain(name, raw, *, failed):
                require(name in N.ORIGINAL_KEYS and type(raw) is bytes and type(failed) is bool, "TAIL_CHILD_ORIGINAL_NAME")
                owner.end(final=failed)
                supplier._write(supplier.private, name + ".bin", raw)
                owner.end(final=failed)
            match, originals = A.acquire_bootstrap(ROOT, kind=kind, query_runner=supplier, invocation=domain["id"],
                token=token, retain=retain, fence=clock, original_work_end=start["workEndNs"],
                first_use_at=context["observed"]["firstUseAt"], expected=expected)
            token = None
            match_pin = _custody_match_pin(match, kind)
            original_graph = N._history_graph(match.__dict__, originals)
            acquired = clock.now(limit=start["workEndNs"])
            _custody_match_check(match_pin)
            _custody_match_check(expected_pin)
            require(type(match) is type(expected) and match.record == expected.record and type(originals) is tuple and
                tuple(name for name, _raw in originals) == N.ORIGINAL_KEYS and all(type(raw) is bytes for _name, raw in originals) and
                dict(originals)["event"] == event, "TAIL_CHILD_FRESH_MATCH")
        except BaseException as error:
            query_failure = error
        finally:
            token = None
            _custody_finish_queries(owner, supplier, query_failure)
        returned = clock.now(limit=start["workEndNs"])
        N._check_history(original_graph)
        _custody_match_check(match_pin)
        queries = owner.open(path / "acquisition-queries")
        session = N.query_session(owner, queries)
        require(all(owner.read(queries, name + ".bin") == raw for name, raw in originals), "TAIL_CHILD_ORIGINAL_READBACK")
        _collect_query_index(path / "acquisition-queries", session, dict(originals), context["observed"])
        N._check_history(metadata_graph)
        _custody_match_check(expected_pin)
        result_raw = owner.write(service, "child-result.json", {"schema": 1, "scope": _TAIL_CHILD_SCOPE,
            "contextSha256": context_hash, "startSha256": O.digest(start_raw), "invocation": domain["id"],
            "clock": O.clock_value(first.clock), "bootDigest": boot, "launchMinimumNs": minimum,
            "beganNs": first.nanoseconds, "metadataLastNs": metadata_last, "acquiredNs": acquired,
            "queryReturnedNs": returned, "querySessionSha256": O.digest(session),
            "originalsSha256": {name: O.digest(raw) for name, raw in originals}, "matchSha256": O.digest(match.record),
            "directoryIdentities": {".": list(private_pin), "service": list(service_pin)},
            "metadataClose": _collect_file_close(metadata_close), "completedNs": clock.now(limit=start["workEndNs"]),
            "retirement": "PENDING_CHILD_CLOSE", "errors": []})
        N._check_history(original_graph)
        _custody_match_check(match_pin)
        clock.now()
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("tail-authority-child", error)
            failure = owner._anchor().failure
        elif metadata is not None:
            failure = metadata.remember(error)
    finally:
        token = None
        if metadata is not None and not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
        if owner is not None:
            if failure is None and owner._anchor().failure is None:
                try:
                    owner.freeze()
                except BaseException as error:
                    owner.error("tail-child-close-roster", error, unknown=True)
            try:
                owner.close()
            except BaseException as error:
                owner.error("tail-child-close", error)
            if failure is None and owner._anchor().failure is not None:
                failure = owner._anchor().failure
    if failure is not None:
        raise failure
    require(owner is not None and clock is not None and result_raw is not None, "TAIL_CHILD_INCOMPLETE")
    anchor = owner.known()
    N._check_history(metadata_graph)
    N._check_history(original_graph)
    _custody_match_check(expected_pin)
    _custody_match_check(match_pin)
    closed = clock.now(limit=start["workEndNs"])
    owner.known()
    owner_close = {"schema": 1, "scope": "INITIAL_SEAL_AUTHORITY_CHILD_KNOWN_CLOSE_V1",
        "resources": [{"ordinal": index, "label": label, "closeAttempted": attempted, "closed": ended}
            for index, (_row, label, _resource, attempted, ended) in enumerate(anchor.rows)],
        "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}
    return {"schema": 1, "scope": _TAIL_ACK_SCOPE, "invocation": domain["id"], "terminalSha256": O.digest(result_raw),
        "clock": O.clock_value(first.clock), "closedNs": closed, "ownerClose": owner_close}, clock, start["workEndNs"]


def _tail_phase_bytes(context_raw, phase, child_raw, clock, private_pin, service_pin):
    """New seal phase DATA only; original live phase/owner identity is separate."""
    require(type(phase) is native.OriginalPhase and phase.context == context_raw and type(phase.records) is tuple,
        "TAIL_PHASE_TYPE")
    context = _tail_context(context_raw, clock)
    records = dict(phase.records)
    require(len(phase.records) == len(records) and set(records) == native.PHASE_FILES and
        all(type(raw) is bytes for raw in records.values()), "TAIL_PHASE_FILES")
    start = _tail_start_fields(records["start.json"], context_raw, context, clock)
    row = fields(canonical(records["result.json"]), " ".join(native.TERMINAL_FIELDS), "TAIL_TERMINAL_FIELDS")
    birth = fields(canonical(records["native-start.json"]), "ownership leader preparerIdentity observedNs", "TAIL_BIRTH_FIELDS")
    changed = {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}
    _same({name: row[name] for name in start if name not in changed},
        {name: start[name] for name in start if name not in changed}, "TAIL_TERMINAL_START")
    require(type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is True and
        row["scopeAttempted"] is True and row["scopeCloseAttempted"] is True and row["scopeClosed"] is True and
        row["retirement"] == "KNOWN" and row["survivors"] == [] and row["errors"] == [] and records["stderr.log"] == b"" and
        row["nativeStartSha256"] == O.digest(records["native-start.json"]) and
        row["baselineSha256"] == O.digest(records["baseline.json"]) and row["leader"] == birth["leader"], "TAIL_NATIVE_RETURN")
    argv = native.phase_command(context_raw, O.integer(row["launchMinimumNs"], start["startedNs"]))
    _same(row["launchArgv"], argv, "TAIL_NATIVE_COMMAND")
    native.native_record(row["ownership"], start, row["leader"], argv)
    native.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    _same(birth["ownership"]["launches"], row["ownership"]["launches"], "TAIL_NATIVE_BIRTH")
    preparer = native.closed_lifetime(row["preparerIdentity"], clock.role)
    require(preparer == native.closed_lifetime(birth["preparerIdentity"], clock.role) and
        preparer["pid"] != row["leader"]["pid"], "TAIL_NATIVE_PREPARER")
    baseline = native.baseline_record(records["baseline.json"], clock.role)
    if baseline["baseline"] is not None:
        leader = native.lifetime(row["leader"], clock.role)
        require(list(leader[:4] if clock.role.startswith("macos-") else leader) not in baseline["baseline"], "TAIL_PREEXISTING_LEADER")
    _same(row["captureOutcomes"], {name: {key: True for key in
        ("synced", "verified", "closeAttempted", "closed", "readback")} for name in ("stdout", "stderr")}, "TAIL_CAPTURE_CLOSE")
    _same(row["captures"], {name: {"sha256": O.digest(records[name + ".log"]), "bytes": len(records[name + ".log"])}
        for name in ("stdout", "stderr")}, "TAIL_CAPTURE_BYTES")
    child = fields(canonical(child_raw), "schema scope contextSha256 startSha256 invocation clock bootDigest launchMinimumNs "
        "beganNs metadataLastNs acquiredNs queryReturnedNs querySessionSha256 originalsSha256 matchSha256 directoryIdentities "
        "metadataClose completedNs retirement errors", "TAIL_CHILD_FIELDS")
    ack = fields(canonical(records["stdout.log"]), "schema scope invocation terminalSha256 clock closedNs ownerClose", "TAIL_ACK_FIELDS")
    require(type(child["schema"]) is int and child["schema"] == 1 and child["scope"] == _TAIL_CHILD_SCOPE and
        child["contextSha256"] == O.digest(context_raw) and child["startSha256"] == O.digest(records["start.json"]) and
        child["invocation"] == start["invocation"] and child["clock"] == O.clock_value(clock) and
        child["bootDigest"] == context["originalWindow"]["originalBootDigest"] and child["launchMinimumNs"] == row["launchMinimumNs"] and
        child["retirement"] == "PENDING_CHILD_CLOSE" and child["errors"] == [] and
        type(ack["schema"]) is int and ack["schema"] == 1 and ack["scope"] == _TAIL_ACK_SCOPE and
        ack["invocation"] == start["invocation"] and ack["terminalSha256"] == O.digest(child_raw) and
        ack["clock"] == O.clock_value(clock), "TAIL_CHILD_ACK")
    _same(child["directoryIdentities"], {".": list(private_pin), "service": list(service_pin)}, "TAIL_CHILD_PINS")
    metadata = _collect_file_close(O.encoded(child["metadataClose"]))
    _same(metadata["resources"], [{"ordinal": index, "label": label, "closeAttempted": True, "closed": True}
        for index, label in enumerate(("directory", "reader", "directory", "reader"))], "TAIL_METADATA_ROSTER")
    close = fields(ack["ownerClose"], "schema scope resources retirement exportSaveAuthority", "TAIL_CHILD_CLOSE_FIELDS")
    require(type(close["schema"]) is int and close["schema"] == 1 and
        close["scope"] == "INITIAL_SEAL_AUTHORITY_CHILD_KNOWN_CLOSE_V1" and
        close["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and close["exportSaveAuthority"] is False, "TAIL_CHILD_CLOSE")
    _collect_close_rows(close["resources"], {"directory", "writer"})
    fields(child["originalsSha256"], " ".join(N.ORIGINAL_KEYS), "TAIL_CHILD_ORIGINAL_HASHES")
    for checksum in (child["querySessionSha256"], child["matchSha256"], *child["originalsSha256"].values()):
        digest(checksum)
    ordered = [row["launchMinimumNs"], *(child[name] for name in
        ("beganNs", "metadataLastNs", "acquiredNs", "queryReturnedNs", "completedNs")), ack["closedNs"], row["completedNs"], row["finalizedNs"]]
    require(all(type(value) is int and O.integer(value) == value for value in ordered) and ordered == sorted(ordered) and
        start["startedNs"] <= ordered[0] and ack["closedNs"] < start["workEndNs"] and row["completedNs"] < start["workEndNs"] and
        row["finalizedNs"] < start["finalEndNs"] and row["launchMinimumNs"] <= O.integer(birth["observedNs"]) <= row["completedNs"],
        "TAIL_ORIGINAL_PHASE_CHRONOLOGY")
    return start, row, birth, child, ack


def _tail_read_authority(owner, private, before, phase, clock, input_result, expected):
    before_pin, phase_pin, expected_pin = _collect_source_pin(before), _collect_phase_pin(phase), \
        _custody_match_pin(expected, clock.frame["kind"])
    raws, _metadata = _checked_tail_input(input_result)
    step, _carrier, old_context, _manifest, _collected = _tail_bundle(raws)
    context_raw = phase.context
    context = _tail_context(context_raw, clock.clock)
    graph = N._history_graph(context, raws)
    require(type(owner) is _CustodyOwner and owner.fence is clock and owner.phase_originals is phase and
        context["originalWindow"] == clock.frame == step["originalWindow"] and
        context["originalServiceJob"] == step["originalServiceJob"] and context["observed"] == old_context["observed"] and
        context["predecessor"] == _tail_predecessor(raws, step) and
        O.encoded(context["expectedMatch"]) == expected.record == raws["original-match"] and
        owner.read(private, "context.json") == context_raw and tuple(context["directoryIdentity"]) == tuple(private.identity),
        "TAIL_CURRENT_CONTEXT")
    policy = N.source_readback(owner, private.path / "source-before", before)
    require(context["sourceReturnSha256"] == O.digest(before.raw) and
        context["sourceReturnedNs"] == canonical(before.raw)["returnedNs"], "TAIL_CURRENT_SOURCE_RETURN")
    _collect_query_index(private.path / "source-before", before.session, dict(before.records), context["observed"], source=before)
    service = owner.child(private, "service")
    for name, raw in phase.records:
        maximum = native.ACK_LIMIT if name == "stdout.log" else native.STDERR_LIMIT if name == "stderr.log" else native.LIMIT
        require(owner.read(service, name, maximum) == raw, "TAIL_CURRENT_PHASE_BYTES")
    child_raw = owner.read(service, "child-result.json")
    start, row, birth, child, ack = _tail_phase_bytes(context_raw, phase, child_raw, clock.clock,
        tuple(private.identity), tuple(service.identity))
    queries = owner.open(private.path / "acquisition-queries")
    session = N.query_session(owner, queries)
    originals = tuple((name, owner.read(queries, name + ".bin")) for name in N.ORIGINAL_KEYS)
    original = dict(originals)
    captured = (context_raw, originals, start["invocation"], start["startedNs"], start["workEndNs"])
    captured_graph = N._history_graph(captured)
    require(child["querySessionSha256"] == O.digest(session) and child["originalsSha256"] ==
        {name: O.digest(raw) for name, raw in originals} and child["matchSha256"] == O.digest(original["match"]) and
        original["event"] == raws["event"] and {name: original[name] for name in N.SOURCE_KEYS} == policy and
        original["candidate_policy_raw"] == raws["policy"] and original["match"] == expected.record,
        "TAIL_CURRENT_ORIGINALS")
    _collect_query_index(private.path / "acquisition-queries", session, original, context["observed"])
    match, service_time = N.retained_match(context, original, start["invocation"], clock.clock,
        start["startedNs"], start["workEndNs"])
    match_pin = _custody_match_pin(match, context["kind"])
    match_graph = N._history_graph(match.__dict__, service_time)
    require(type(match) is type(expected) and match.record == expected.record and
        list(N._service_job(captured, clock.clock)) == step["originalServiceJob"], "TAIL_CURRENT_MATCH_OR_ORIGINAL_JOB")
    minimum = N._service_chain_minimum(clock.first, context["sourceReturnedNs"], start, row, birth, child, service_time, ack)
    checked = clock.now(minimum=minimum)
    _collect_source_current(before_pin)
    _collect_phase_current(phase_pin)
    _custody_match_check(expected_pin)
    _custody_match_check(match_pin)
    N._check_history(graph)
    N._check_history(captured_graph)
    N._check_history(match_graph)
    owner.check()
    require(owner.phase_originals is phase, "TAIL_CURRENT_PHASE_OWNER")
    authority = {"contextSha256": O.digest(context_raw), "sourceBeforeSha256": O.digest(before.raw),
        "expectedMatchSha256": O.digest(expected.record), "freshMatchSha256": O.digest(match.record),
        "originalsSha256": {name: O.digest(raw) for name, raw in originals}, "querySessionSha256": O.digest(session),
        "phaseSha256": {name: O.digest(raw) for name, raw in phase.records}, "childSha256": O.digest(child_raw),
        "ackSha256": O.digest(dict(phase.records)["stdout.log"]), "invocation": start["invocation"],
        "startedNs": start["startedNs"], "workEndNs": start["workEndNs"], "finalEndNs": start["finalEndNs"],
        "acquiredNs": child["acquiredNs"], "checkedNs": checked}
    return match, captured, authority, child_raw, session


@dataclass(frozen=True, repr=False)
class _TailAuthority:
    """THIS seal episode's actual close; never an old serialized capability."""
    input: object
    raw: bytes
    originals: tuple


def _tail_authority(input_result, clock, expected, token):
    attempt = _tail_begin("seal-authority")
    attempt.update(input=input_result, clock=clock, owner=None)
    owner = None
    failure = None
    source_links, source_pins, graphs, match_pins, directory_pins = (), (), (), (), ()
    phase = phase_pin = None
    try:
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and
            not any(name in os.environ for name in _CREDENTIAL_NAMES) and type(clock) is _TailClock and
            clock.side == "parent", "TAIL_AUTHORITY_TOKEN_OR_CLOCK")
        raws, _metadata = _checked_tail_input(input_result)
        parsed = _tail_bundle(raws)
        step, _carrier, old_context, _manifest, _collected = parsed
        expected_pin = _custody_match_pin(expected, step["kind"])
        match_pins = (expected_pin,)
        graphs = (N._history_graph(raws, parsed),)
        require(expected.record == raws["original-match"] and clock.frame == step["originalWindow"], "TAIL_AUTHORITY_INPUT")
        owner = _CustodyOwner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled)
        attempt["owner"] = owner
        clock.attach_operative(owner)
        anchor, dictionary = owner._anchor(), owner.__dict__
        def current():
            require(_TAIL_ATTEMPTS.get("seal-authority") is attempt and attempt["input"] is input_result and
                attempt["clock"] is clock and attempt["owner"] is owner and attempt["state"] in ("STARTED", "RETURNED") and
                attempt["failure"] is None and owner.__dict__ is dictionary and owner._anchor() is anchor,
                "TAIL_AUTHORITY_ORIGINAL_ATTEMPT")
            _checked_tail_input(input_result)
            owner.check()
            require(owner.original is None and not owner.unknown and owner.errors == [] and
                set(owner.initial_sources) == {name for name, _source in source_links} and
                all(owner.initial_sources[name] is source for name, source in source_links) and owner.phase_originals is phase,
                "TAIL_AUTHORITY_ORIGINAL_OWNER")
            for pin in source_pins:
                _collect_source_current(pin)
            if phase_pin is not None:
                _collect_phase_current(phase_pin)
            for pin in match_pins:
                _custody_match_check(pin)
            for graph in graphs:
                N._check_history(graph)
            if directory_pins:
                N._check_worker_pins(directory_pins, clock.clock.role, closed=owner.closed)
        current()
        custody = _paths(step["kind"])[2]
        root = owner.open(custody)
        input_pins = _TAIL_INPUTS[id(input_result)][6]
        require(root.path == input_pins[0][1] and tuple(root.identity) == input_pins[0][2] and
            native._initializer_names(owner, root) == _tail_roster("INPUT"), "TAIL_AUTHORITY_INITIAL_ROOT")
        path = custody / "authority-seal"
        private = owner.child(root, "authority-seal", create=True)
        private_pin = tuple(private.identity)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        before = N.source_queries(owner, clock, old_context["observed"], path / "source-before")
        source_links = ((str(path / "source-before"), before),)
        source_pins = (_collect_source_pin(before),)
        current()
        policy = N.source_readback(owner, path / "source-before", before)
        require(policy["candidate_policy_raw"] == raws["policy"], "TAIL_SEAL_POLICY_CHANGED")
        _collect_query_index(path / "source-before", before.session, policy, old_context["observed"], source=before)
        inherited = Q._inherited_context()
        context = {"schema": 1, "scope": native.INITIAL_TAIL_AUTHORITY_CONTEXT_SCOPE, "edge": "SEAL",
            "kind": step["kind"], "root": str(ROOT), "session": str(path), "job": uuid.uuid4().hex,
            "observed": old_context["observed"], "originalWindow": step["originalWindow"],
            "originalServiceJob": step["originalServiceJob"], "predecessor": _tail_predecessor(raws, step),
            "expectedMatch": canonical(expected.record, A.stages.LIMIT), "eventSha256": O.digest(raws["event"]),
            "sourceReturnSha256": O.digest(before.raw), "sourceReturnedNs": canonical(before.raw)["returnedNs"],
            "inheritedContext": inherited, "directoryIdentity": list(private_pin), "parentFirstNs": clock.first,
            "continuationEndNs": clock.work, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        graphs = (*graphs, N._history_graph(context, inherited))
        context_raw = O.encoded(context)
        _tail_context(context_raw, clock.clock)
        current()
        require(owner.write(private, "context.json", context_raw) == context_raw, "TAIL_CONTEXT_WRITE")
        _directory, returned_phase = N._initial_service_phase(owner, private, context_raw, token, clock, before)
        phase = returned_phase
        phase_pin = _collect_phase_pin(phase)
        token = None
        current()
        first_match, first_captured, _chain, _child, _session = _tail_read_authority(
            owner, private, before, phase, clock, input_result, expected)
        match_pins = (*match_pins, _custody_match_pin(first_match, step["kind"]))
        graphs = (*graphs, N._history_graph(first_captured))
        current()
        after = N.source_queries(owner, clock, old_context["observed"], path / "source-after")
        source_links = (*source_links, (str(path / "source-after"), after))
        source_pins = (*source_pins, _collect_source_pin(after))
        current()
        require(N.source_readback(owner, path / "source-after", after) == policy, "TAIL_FINAL_SOURCE_CHANGED")
        _collect_query_index(path / "source-after", after.session, dict(after.records), old_context["observed"], source=after)
        match, captured, authority, child_raw, session_raw = _tail_read_authority(
            owner, private, before, phase, clock, input_result, expected)
        match_pin = _custody_match_pin(match, step["kind"])
        match_pins = (*match_pins, match_pin)
        require(captured == first_captured, "TAIL_FRESH_ORIGINALS_CHANGED")
        authority["sourceAfterSha256"] = O.digest(after.raw)
        files = [("context.json", context_raw), ("service/child-result.json", child_raw),
            ("acquisition-queries/session-result.json", session_raw)]
        files.extend(("service/" + name, raw) for name, raw in phase.records)
        files.extend(("acquisition-queries/" + name + ".bin", raw) for name, raw in captured[1])
        for name, source in (("source-before", before), ("source-after", after)):
            files.extend(((name + "/source-return.json", source.raw), (name + "/session-result.json", source.session)))
            files.extend((name + "/" + key + ".bin", raw) for key, raw in source.records)
        originals = tuple(files)
        graphs = (*graphs, N._history_graph(captured, authority, originals))
        directory_pins = N._worker_pins(owner, clock.clock.role, {".": path, **{name: path / name for name in
            ("control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")}})
        current()
        require(tuple(private.identity) == private_pin and native._initializer_names(owner, root) == _tail_roster("AUTHORITY"),
            "TAIL_AUTHORITY_FINAL_ROOT")
        preclose = clock.now()
        current()
        owner.freeze()
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("tail-authority-parent", error)
            failure = owner._anchor().failure
    finally:
        token = None
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                owner.error("tail-authority-parent-close", error)
            if failure is None and owner._anchor().failure is not None:
                failure = owner._anchor().failure
    try:
        if failure is not None:
            raise failure
        require(owner is not None and owner._anchor() is anchor, "TAIL_AUTHORITY_INCOMPLETE")
        owner.known()
        current()
        closed = clock.now(minimum=preclose)
        current()
        parent_close = {"schema": 1, "scope": "INITIAL_SEAL_AUTHORITY_PARENT_KNOWN_CLOSE_V1",
            "resources": [{"ordinal": index, "label": label, "closeAttempted": attempted, "closed": ended}
                for index, (_row, label, _resource, attempted, ended) in enumerate(anchor.rows)],
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}
        final_authority = {**authority, "closedNs": closed}
        raw = O.encoded({"schema": 1, "scope": "INITIAL_SEAL_AUTHORITY_CLOSED_RETURN_V1", "edge": "SEAL",
            "authority": final_authority, "parentClose": parent_close, "preCloseNs": preclose, "closedNs": closed,
            "testAcceptance": "NOT_PERFORMED", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        canonical(raw)
        result = _TailAuthority(input_result, raw, originals)
        saved = (result, result.__dict__, input_result, raw, originals, clock, owner, anchor, dictionary, current,
            N._history_graph(result.__dict__, captured, final_authority, parent_close), match_pin, captured, attempt)
        _TAIL_AUTHORITIES[id(result)] = saved
        attempt["return"], attempt["state"] = result, "RETURNED"
        _checked_tail_authority(result)
        return result
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def _checked_tail_authority(result):
    saved = _TAIL_AUTHORITIES.get(id(result))
    require(type(result) is _TailAuthority and type(saved) is tuple and saved[0] is result, "TAIL_NOT_ORIGINAL_AUTHORITY")
    _, dictionary, inputs, raw, originals, clock, owner, anchor, owner_dictionary, current, graph, match_pin, captured, attempt = saved
    try:
        require(result.__dict__ is dictionary and result.input is inputs and result.raw == raw and result.originals is originals and
            attempt["state"] == "RETURNED" and attempt["return"] is result and attempt["failure"] is None,
            "TAIL_AUTHORITY_RETURN_CHANGED")
        N._check_history(graph)
        current()
        require(owner.__dict__ is owner_dictionary and owner._anchor() is anchor and clock._view().failure is None,
            "TAIL_AUTHORITY_OWNER_CHANGED")
        owner.known()
        return clock, inputs, raw, originals, _custody_match_check(match_pin), captured
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def _tail_authority_currency(result):
    clock, inputs, raw, originals, original_match, captured = _checked_tail_authority(result)
    pin = _custody_match_pin(original_match, clock.frame["kind"])
    raws, _metadata = _checked_tail_input(inputs)
    parsed = _tail_bundle(raws)
    graph = N._history_graph(raws, parsed, captured)
    expected = _tail_host(raws, parsed, clock.clock)
    expected_pin = _custody_match_pin(expected, parsed[0]["kind"])
    context_raw, acquisition_raws, invocation, began, end = captured
    match, _service = N.retained_match(canonical(context_raw), dict(acquisition_raws), invocation, clock.clock, began, end)
    fresh_pin = _custody_match_pin(match, parsed[0]["kind"])
    require(type(match) is type(original_match) is type(expected) and match.record == original_match.record == expected.record,
        "TAIL_LATE_GRANT_CHANGED")
    clock.now()
    _custody_match_check(pin)
    _custody_match_check(expected_pin)
    _custody_match_check(fresh_pin)
    N._check_history(graph)
    _checked_tail_authority(result)
    return clock, inputs, raw, originals


def _tail_pre_metadata(kind, cancelled):
    """Own token-bearing helper; no credential/old live capability is returned."""
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    try:
        local = local_value(time.monotonic())
        first = O.clocks.observe()
        graph = N._history_graph(first)
        O.clocks.validate_reading(first)
        boot = digest(C.boot_digest(first.clock.role))
        N._check_history(graph)
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and callable(cancelled) and
            not native.QUARANTINE and not Q.QUARANTINE and not C.QUARANTINE and not native.diagnostics._QUARANTINE and
            native.processes.host_role() == first.clock.role, "TAIL_TOKEN_OR_UNKNOWN")
        actual = _tail_actual()
        clock = _TailClock(first, local, boot, cancelled, side="parent")
        inputs = _read_tail_input(clock, kind, actual)
        expected = clock.bind_parent(inputs)
        return _tail_authority(inputs, clock, expected, token)
    finally:
        token = None


def _tail_ciphertext(metadata, output, artifact):
    """One fixed ciphertext reader; NOT the512MiB packet copier or a Snapshot."""
    fields(artifact, "name size sha256", "TAIL_ARTIFACT_FIELDS")
    require(artifact["name"] == native.posix.ARTIFACT and type(artifact["size"]) is int and
        0 < artifact["size"] <= native.posix.MAX_CIPHERTEXT_BYTES, "TAIL_ARTIFACT_LIMIT")
    digest(artifact["sha256"])
    require(_tail_directory_names(metadata, output) == tuple(sorted((native.posix.ARTIFACT, native.posix.MANIFEST))),
        "TAIL_OUTPUT_ROSTER")
    end, reader = metadata.guard(), None
    expected = O.encoded(artifact)
    output_pin = output.path, tuple(output.identity)
    try:
        path = output.path / native.posix.ARTIFACT
        if os.name == "nt":
            reader = metadata.acquire("reader", lambda: output.open_file(native.posix.ARTIFACT,
                max_bytes=native.posix.MAX_CIPHERTEXT_BYTES, deadline=end))
            require(type(reader) is native.windows.NativeFile, "TAIL_CIPHERTEXT_READER")
            original = reader.initial_info
            def verify():
                require(reader.verify() == original, "TAIL_CIPHERTEXT_METADATA_CHANGED")
        else:
            reader = metadata.acquire("reader", lambda: Q._posix_stream(path, os.O_RDONLY | os.O_NOFOLLOW, "rb"))
            require(type(reader) is io.BufferedReader, "TAIL_CIPHERTEXT_READER")
            original = Q._file_info(path, reader, native.posix.MAX_CIPHERTEXT_BYTES)
            def verify():
                output.verify()
                require(Q._file_info(path, reader, native.posix.MAX_CIPHERTEXT_BYTES) == original,
                    "TAIL_CIPHERTEXT_METADATA_CHANGED")
        original_raw = O.encoded(original.as_dict())
        require(type(original.size) is int and original.size == artifact["size"], "TAIL_CIPHERTEXT_SIZE")
        total, hashed = 0, hashlib.sha256()
        while total < artifact["size"]:
            metadata.guard()
            piece = reader.read(min(COPY_CHUNK, artifact["size"] - total))
            require(type(piece) is bytes and 0 < len(piece) <= min(COPY_CHUNK, artifact["size"] - total),
                "TAIL_CIPHERTEXT_SHORT_READ")
            total += len(piece)
            hashed.update(piece)
            metadata.guard()
        metadata.guard()
        extra = reader.read(1)
        require(type(extra) is bytes and extra == b"" and total == artifact["size"] and
            hashed.hexdigest() == artifact["sha256"], "TAIL_CIPHERTEXT_HASH_OR_EOF")
        verify()
        metadata.guard()
        require(output.path is output_pin[0] and tuple(output.identity) == output_pin[1] and
            O.encoded(artifact) == expected and O.encoded(original.as_dict()) == original_raw, "TAIL_CIPHERTEXT_BINDING_CHANGED")
    except BaseException as error:
        raise metadata.remember(error)
    finally:
        if reader is not None and not metadata.owner.unknown:
            try:
                metadata.close_one(reader)
            except BaseException as error:
                metadata.remember(error, unknown=True)
        if metadata.failure is not None:
            raise metadata.failure
    require(_tail_directory_names(metadata, output) == tuple(sorted((native.posix.ARTIFACT, native.posix.MANIFEST))),
        "TAIL_OUTPUT_ROSTER_CHANGED")
    require(output.path is output_pin[0] and tuple(output.identity) == output_pin[1] and O.encoded(artifact) == expected,
        "TAIL_CIPHERTEXT_FINAL_BINDING")
    return {"scope": "THIS_SEAL_FILE_OBSERVATION_NOT_HISTORICAL_POSIX_OUTPUT_PIN",
        "directoryIdentity": list(output_pin[1]), "fileMetadataSha256": O.digest(original_raw), "artifact": canonical(expected)}


def _tail_authority_record(raw, frame, first_ns, end_ns):
    value = fields(canonical(raw), "schema scope edge authority parentClose preCloseNs closedNs testAcceptance "
        "budgetAcceptance exportSaveAuthority", "TAIL_AUTHORITY_RECORD_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == "INITIAL_SEAL_AUTHORITY_CLOSED_RETURN_V1" and value["edge"] == "SEAL" and
        value["testAcceptance"] == "NOT_PERFORMED" and value["budgetAcceptance"] == "NOT_ADMITTED" and
        value["exportSaveAuthority"] is False, "TAIL_AUTHORITY_RECORD_SCOPE")
    authority = fields(value["authority"], "contextSha256 sourceBeforeSha256 sourceAfterSha256 expectedMatchSha256 freshMatchSha256 "
        "originalsSha256 querySessionSha256 phaseSha256 childSha256 ackSha256 invocation startedNs workEndNs finalEndNs "
        "acquiredNs checkedNs closedNs", "TAIL_AUTHORITY_BINDING_FIELDS")
    for name in ("contextSha256", "sourceBeforeSha256", "sourceAfterSha256", "expectedMatchSha256", "freshMatchSha256",
            "querySessionSha256", "childSha256", "ackSha256"):
        digest(authority[name])
    fields(authority["originalsSha256"], " ".join(N.ORIGINAL_KEYS), "TAIL_AUTHORITY_ORIGINAL_HASH_FIELDS")
    fields(authority["phaseSha256"], " ".join(native.PHASE_FILES), "TAIL_AUTHORITY_PHASE_HASH_FIELDS")
    for checksum in (*authority["originalsSha256"].values(), *authority["phaseSha256"].values()):
        digest(checksum)
    require(authority["freshMatchSha256"] == authority["expectedMatchSha256"] == authority["originalsSha256"]["match"] and
        authority["ackSha256"] == authority["phaseSha256"]["stdout.log"] and type(authority["invocation"]) is str and
        re.fullmatch(r"[0-9a-f]{32}", authority["invocation"]), "TAIL_AUTHORITY_HASH_LINKS")
    times = [authority[name] for name in ("startedNs", "acquiredNs", "checkedNs")]
    times.extend((value["preCloseNs"], value["closedNs"]))
    require(all(type(item) is int and O.integer(item) == item for item in times) and times == sorted(times) and
        frame["startNs"] <= first_ns <= times[0] and authority["closedNs"] == value["closedNs"] < end_ns and
        end_ns == min(first_ns + 30 * O.NS, frame["sealEndNs"]) and
        times[0] < O.integer(authority["workEndNs"]) == O.integer(authority["finalEndNs"]) == end_ns and
        authority["acquiredNs"] < authority["workEndNs"], "TAIL_AUTHORITY_RECORD_TIME")
    close = fields(value["parentClose"], "schema scope resources retirement exportSaveAuthority", "TAIL_PARENT_CLOSE_FIELDS")
    require(type(close["schema"]) is int and close["schema"] == 1 and
        close["scope"] == "INITIAL_SEAL_AUTHORITY_PARENT_KNOWN_CLOSE_V1" and
        close["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and close["exportSaveAuthority"] is False, "TAIL_PARENT_CLOSE_SCOPE")
    _collect_close_rows(close["resources"], {"directory", "writer", "native-scope", "stdout", "stderr"})
    return value


def _tail_seal_record(raw, inputs, authority_raw, first_ns, end_ns):
    value = fields(canonical(raw), "schema scope kind edge predecessor primary source github policy originalWindow "
        "firstNs hardEndNs lastNs lastLocal manifestSha256 output authority inputMetadataClose writerReturn originalStepOutcome "
        "decryption upload testAcceptance productiveAuthority cacheAuthority budgetAcceptance exportSaveAuthority", "TAIL_SEAL_FIELDS")
    raws, _metadata = _checked_tail_input(inputs)
    step, _carrier, _context, manifest, collected = _tail_bundle(raws)
    authority = _tail_authority_record(authority_raw, step["originalWindow"], first_ns, end_ns)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == _TAIL_SEAL_SCOPE and
        value["kind"] == step["kind"] and value["edge"] == "SEAL" and
        value["predecessor"] == _tail_predecessor(raws, step) and value["primary"] == step["primary"] and
        all(value[name] == manifest[name] for name in ("source", "github", "policy")) and
        value["originalWindow"] == step["originalWindow"] and value["authority"] == authority and
        value["inputMetadataClose"] == _collect_file_close(inputs.metadata_close) and
        type(value["firstNs"]) is int and value["firstNs"] == first_ns and
        type(value["hardEndNs"]) is int and value["hardEndNs"] == end_ns and
        authority["closedNs"] <= O.integer(value["lastNs"]) < end_ns and
        local_value(value["lastLocal"]) >= collected["lastLocal"] and
        value["manifestSha256"] == O.digest(raws["manifest"]) and
        value["decryption"] == value["upload"] == "NOT_PERFORMED", "TAIL_SEAL_BINDING")
    _collect_pending(value)
    output = fields(value["output"], "scope directoryIdentity fileMetadataSha256 artifact", "TAIL_OUTPUT_FIELDS")
    require(output["scope"] == "THIS_SEAL_FILE_OBSERVATION_NOT_HISTORICAL_POSIX_OUTPUT_PIN" and
        output["directoryIdentity"] == list(_TAIL_INPUTS[id(inputs)][6][2][2]) and output["artifact"] == manifest["artifact"],
        "TAIL_OUTPUT_OBSERVATION")
    digest(output["fileMetadataSha256"])
    return value


def _historical_seal_record(raw, raws, *, outcome, expected_sha256):
    """Decode supplied prior-Step DATA, never restore a seal/owner capability.

    The caller must authenticate actual Step outcomes/hash custody, read these
    bytes through new owned readers and acquire its own current authority and
    clocks. This pure check neither observes a host nor registers any return.
    Pending self-writer/Step flags remain unchanged even with supplied success.
    """
    value = fields(canonical(raw), "schema scope kind edge predecessor primary source github policy originalWindow "
        "firstNs hardEndNs lastNs lastLocal manifestSha256 output authority inputMetadataClose writerReturn originalStepOutcome "
        "decryption upload testAcceptance productiveAuthority cacheAuthority budgetAcceptance exportSaveAuthority",
        "HISTORICAL_SEAL_FIELDS")
    require(type(outcome) is str and outcome == "success" and O.digest(raw) == digest(expected_sha256),
        "HISTORICAL_SEAL_SUPPLIED_STEP")
    step, _carrier, context, manifest, collected = _tail_bundle(raws)
    frame = step["originalWindow"]
    first, end = O.integer(value["firstNs"]), O.integer(value["hardEndNs"])
    authority = _tail_authority_record(O.encoded(value["authority"]), frame, first, end)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == _TAIL_SEAL_SCOPE and
        value["kind"] == step["kind"] and value["edge"] == "SEAL", "HISTORICAL_SEAL_SCOPE")
    expected = {"predecessor": _tail_predecessor(raws, step), "primary": step["primary"],
        **{name: manifest[name] for name in ("source", "github", "policy")}, "originalWindow": frame,
        "manifestSha256": O.digest(raws["manifest"])}
    # Canonical equality also refuses boolean/integer substitutions in nested
    # supplied history. Equality of Python mappings alone would not do that.
    _same({name: value[name] for name in expected}, expected, "HISTORICAL_SEAL_BINDINGS")
    binding = authority["authority"]
    # The existing parser compares this nested value to a typed outer integer.
    # Refuse numeric equality aliases locally, without changing that parser.
    O.integer(binding["closedNs"])
    require(binding["expectedMatchSha256"] == binding["freshMatchSha256"] == binding["originalsSha256"]["match"] ==
        O.digest(raws["original-match"]) and binding["originalsSha256"]["event"] == O.digest(raws["event"]) and
        binding["originalsSha256"]["candidate_policy_raw"] == O.digest(raws["policy"]),
        "HISTORICAL_SEAL_AUTHORITY_INPUTS")
    require(collected["lastNs"] <= first and authority["closedNs"] <= O.integer(value["lastNs"]) < end and
        local_value(value["lastLocal"]) >= collected["lastLocal"], "HISTORICAL_SEAL_CHRONOLOGY")
    _collect_pending(value)
    require(value["decryption"] == value["upload"] == "NOT_PERFORMED", "HISTORICAL_SEAL_NOT_ACCEPTANCE")
    # This parses historical close DATA; it is not today's metadata owner's
    # close, and is deliberately never installed in _TAIL_INPUTS or any ledger.
    _collect_file_close(O.encoded(value["inputMetadataClose"]))
    output = fields(value["output"], "scope directoryIdentity fileMetadataSha256 artifact", "HISTORICAL_SEAL_OUTPUT_FIELDS")
    clock = O.wire.clock_identity(frame["clock"])
    native.directory_identity(output["directoryIdentity"], clock.role)
    require(output["scope"] == "THIS_SEAL_FILE_OBSERVATION_NOT_HISTORICAL_POSIX_OUTPUT_PIN",
        "HISTORICAL_SEAL_OUTPUT_SCOPE")
    original_pin = context["directories"]["export-output"]
    if original_pin is not None:
        _same(output["directoryIdentity"], original_pin, "HISTORICAL_SEAL_WINDOWS_OUTPUT_PIN")
    _same(output["artifact"], manifest["artifact"], "HISTORICAL_SEAL_ARTIFACT")
    # The seal-observed pin and this hash are declarations only. A later user
    # still needs a NEW owned exact file/metadata read before upload is possible.
    digest(output["fileMetadataSha256"])
    return value


_HISTORICAL_AUTHORITY_LIMITS = {
    "context.json": native.LIMIT, "service/child-result.json": native.LIMIT,
    "acquisition-queries/session-result.json": Q.MAX_RECEIPT_BYTES,
    **{"service/" + name: native.ACK_LIMIT if name == "stdout.log" else
        native.STDERR_LIMIT if name == "stderr.log" else native.LIMIT for name in native.PHASE_FILES},
    **{"acquisition-queries/" + name + ".bin": Q.MAX_RECEIPT_BYTES for name in N.ORIGINAL_KEYS},
    **{side + "/" + name: native.LIMIT if name == "source-return.json" else Q.MAX_RECEIPT_BYTES
        for side in ("source-before", "source-after")
        for name in ("source-return.json", "session-result.json", *(key + ".bin" for key in N.SOURCE_KEYS))},
}


def _historical_query_index(context, side, raws):
    """Expand original query declarations, NOT read files or restore SourceReturn.

    Native ownership/output metadata remains opaque historical DATA. Query
    result and stream hashes are bound, but no native retirement is established.
    Every emitted row still requires a new owned size/hash/EOF/metadata read.
    """
    require(side in ("source-before", "source-after", "acquisition-queries"), "HISTORY_QUERY_SIDE")
    acquisition = side == "acquisition-queries"
    keys = N.ORIGINAL_KEYS if acquisition else N.SOURCE_KEYS
    originals = {name: raws[side + "/" + name + ".bin"] for name in keys}
    session_raw = raws[side + "/session-result.json"]
    session = fields(canonical(session_raw, Q.MAX_RECEIPT_BYTES),
        "schema scope job queries result retirement firstError errors readbacks", "HISTORY_QUERY_SESSION_FIELDS")
    require(type(session["schema"]) is int and session["schema"] == 1 and
        session["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and type(session["job"]) is str and
        re.fullmatch(r"[0-9a-f]{32}", session["job"]) and session["result"] == "READY_FOR_CALLER_SEAL" and
        session["retirement"] == "KNOWN" and session["firstError"] is None and session["errors"] == [] and
        type(session["queries"]) is list and len(session["queries"]) == (24 if acquisition else 12) and
        type(session["readbacks"]) is list, "HISTORY_QUERY_SESSION")
    path = Path(context["session"]) / side  # Path arithmetic only; no filesystem call.
    entry = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(I.POLICY_PATH.encode("ascii")) + rb"\x00",
        originals["candidate_policy_entry"])
    require(entry is not None, "HISTORY_QUERY_POLICY_ENTRY")
    commit, blob = context["observed"]["source"]["commit"], entry.group(1).decode("ascii")
    I.sha(commit)
    commands = (("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
        ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--verify", commit + "^{tree}"),
        ("rev-parse", "--is-shallow-repository"), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
        ("rev-parse", "--verify", A.stages.BASE["commit"] + "^{tree}"),
        ("ls-tree", "-z", A.stages.BASE["commit"], "--", I.POLICY_PATH),
        ("merge-base", A.stages.BASE["commit"], commit), ("ls-tree", "-z", commit, "--", I.POLICY_PATH),
        ("cat-file", "-s", blob), ("cat-file", "blob", blob))
    expected, directories, ids, selected = [(path, "owner.json", None, None)], [side, side + "/query-home"], set(), None
    if acquisition:
        expected.append((path, "event.bin", None, None))
    for index, query in enumerate(session["queries"]):
        fields(query, "schema scope id job state home cwd argv stdoutLimit stderrLimit timeoutSeconds launchAttempted "
            "scopeAttempted waitExitCode retirement result errors outputs ownedSurvivors ownership", "HISTORY_QUERY_FIELDS")
        require(type(query["schema"]) is int and query["schema"] == 1 and
            query["scope"] == "NATIVE_OWNED_ORDINARY_GIT_QUERY" and type(query["id"]) is str and
            re.fullmatch(r"[0-9a-f]{32}", query["id"]) and query["id"] not in ids and
            query["job"] == session["job"] and query["state"] == str(path) and
            query["home"] == str(path / "query-home") and query["cwd"] == context["root"] and
            query["launchAttempted"] is True and query["scopeAttempted"] is True and
            type(query["waitExitCode"]) is int and query["waitExitCode"] == 0 and
            query["retirement"] == "KNOWN" and query["result"] == "READY_FOR_CALLER_SEAL" and
            query["errors"] == query["ownedSurvivors"] == [] and type(query["ownership"]) is dict and
            query["ownership"].get("discoveryErrors") == [], "HISTORY_QUERY_DECLARATION")
        ids.add(query["id"])
        timeout = query["timeoutSeconds"]
        require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 15, "HISTORY_QUERY_TIMEOUT")
        limit = I.EVENT_LIMIT if index % 12 == 1 else I.POLICY_LIMIT if index % 12 == 11 else 4096
        require(type(query["stdoutLimit"]) is int and query["stdoutLimit"] == limit and
            type(query["stderrLimit"]) is int and query["stderrLimit"] == 4096 and type(query["argv"]) is list and
            query["argv"] and type(query["argv"][0]) is str and 0 < len(query["argv"][0]) <= 8192 and
            "\0" not in query["argv"][0], "HISTORY_QUERY_LIMITS")
        if selected is None:
            selected = query["argv"][0]
        require(query["argv"] == [selected, "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
            "-C", context["root"], *commands[index % 12]], "HISTORY_QUERY_COMMAND")
        fields(query["outputs"], "stdout stderr", "HISTORY_QUERY_OUTPUTS")
        target = path / ("query-" + query["id"])
        directories.append(side + "/query-" + query["id"])
        expected.extend((target, name, query[name[:-4] + "Limit"] if name.endswith(".log") else None, query)
            for name in ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"))
        if acquisition and index == 11:
            expected.extend((path, name + ".bin", None, None) for name in (*N.SOURCE_KEYS, *N.HTTP_KEYS))
    expected.extend((path, name + ".bin", None, None)
        for name in (("observation", "match") if acquisition else N.SOURCE_KEYS))
    require(len(session["readbacks"]) == len(expected), "HISTORY_QUERY_READBACK_COUNT")
    rows, total = [], len(session_raw)
    for row, (parent, name, limit, query) in zip(session["readbacks"], expected):
        fields(row, "parent name maximum retirement result bytes sha256", "HISTORY_QUERY_READBACK_FIELDS")
        count, maximum = O.integer(row["bytes"]), O.integer(row["maximum"], 1)
        checksum = digest(row["sha256"])
        require(row["parent"] == str(parent) and row["name"] == name and row["retirement"] == "KNOWN" and
            row["result"] == "RETAINED" and count <= maximum <= Q.MAX_RECEIPT_BYTES and
            maximum == (max(1, count) if limit is None else limit) and
            (count != 0 or checksum == O.digest(b"")), "HISTORY_QUERY_READBACK")
        if parent == path and name.endswith(".bin"):
            original = originals[name[:-4]]
            require(count == len(original) and checksum == O.digest(original), "HISTORY_QUERY_ORIGINAL_BYTES")
        if query is not None and name.endswith(".log"):
            output = query["outputs"][name[:-4]]
            require(type(output) is dict and type(output.get("bytes")) is int and output["bytes"] == count and
                output.get("sha256") == checksum, "HISTORY_QUERY_STREAM_BINDING")
        if query is not None and name == "result.json":
            original = Q.encoded(query)
            require(count == len(original) and checksum == O.digest(original), "HISTORY_QUERY_RESULT_BINDING")
        total += count
        require(total <= Q.MAX_SESSION_BYTES, "HISTORY_QUERY_SESSION_CAP")
        relative = side + "/" + ("" if parent == path else parent.name + "/") + name
        rows.append((relative, maximum, count, checksum))
    rows.append((side + "/session-result.json", Q.MAX_RECEIPT_BYTES, len(session_raw), O.digest(session_raw)))
    if not acquisition:
        raw = raws[side + "/source-return.json"]
        source = fields(canonical(raw), "schema scope originalsSha256 sessionSha256 clock returnedNs", "HISTORY_SOURCE_FIELDS")
        require(type(source["schema"]) is int and source["schema"] == 1 and source["scope"] == N.SOURCE_SCOPE and
            source["sessionSha256"] == O.digest(session_raw), "HISTORY_SOURCE_SESSION")
        _same(source["originalsSha256"], {name: O.digest(value) for name, value in originals.items()}, "HISTORY_SOURCE_ORIGINALS")
        _same(source["clock"], context["originalWindow"]["clock"], "HISTORY_SOURCE_CLOCK")
        O.integer(source["returnedNs"])
        rows.append((side + "/source-return.json", native.LIMIT, len(raw), O.digest(raw)))
    require(len(rows) == (137 if acquisition else 67), "HISTORY_QUERY_FILE_COUNT")
    return tuple(rows), tuple(directories)


def _historical_authority_index(raws, prior_raws, parsed, sealed, side):
    """The existing36 binding inputs DECLARE279 required files, not custody."""
    require(side in ("authority-2", "authority-seal") and type(raws) is dict and
        set(raws) == set(_HISTORICAL_AUTHORITY_LIMITS), "HISTORY_AUTHORITY_INPUT_ROSTER")
    require(all(type(raw) is bytes and len(raw) <= _HISTORICAL_AUTHORITY_LIMITS[name] for name, raw in raws.items()),
        "HISTORY_AUTHORITY_INPUT_LIMIT")
    step, _carrier, old_context, _manifest, collected = parsed
    sealing = side == "authority-seal"
    authority = sealed["authority"]["authority"] if sealing else collected["authority"]
    context_raw = raws["context.json"]
    context = fields(canonical(context_raw), _TAIL_CONTEXT_FIELDS if sealing else _COLLECT_CONTEXT_FIELDS,
        "HISTORY_AUTHORITY_CONTEXT_FIELDS")
    require(type(context["schema"]) is int and context["schema"] == 1 and context["scope"] ==
        (native.INITIAL_TAIL_AUTHORITY_CONTEXT_SCOPE if sealing else native.INITIAL_COLLECT_AUTHORITY_CONTEXT_SCOPE) and
        context["edge"] == ("SEAL" if sealing else "POST_EXPORT") and context["kind"] == step["kind"] and
        context["root"] == old_context["root"] and context["session"] == str(Path(step["directory"]).parent / side) and
        type(context["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", context["job"]) and
        context["budgetAcceptance"] == "NOT_ADMITTED" and context["exportSaveAuthority"] is False and
        O.digest(context_raw) == authority["contextSha256"], "HISTORY_AUTHORITY_CONTEXT")
    expected = {"observed": old_context["observed"], "originalWindow": step["originalWindow"],
        "originalServiceJob": step["originalServiceJob"], "expectedMatch": canonical(prior_raws["original-match"], A.stages.LIMIT),
        "eventSha256": O.digest(prior_raws["event"]), "sourceReturnSha256": authority["sourceBeforeSha256"],
        "predecessor": _tail_predecessor(prior_raws, step) if sealing else _collect_predecessor(prior_raws, step)}
    _same({name: context[name] for name in expected}, expected, "HISTORY_AUTHORITY_CONTEXT_BINDINGS")
    frame = step["originalWindow"]
    clock = O.wire.clock_identity(frame["clock"])
    first, end = O.integer(context["parentFirstNs"], step["lowerNs"]), O.integer(context["continuationEndNs"])
    require(end == min(first + 30 * O.NS, frame["sealEndNs" if sealing else "readEndNs"]) and
        end == authority["workEndNs"] == authority["finalEndNs"] and first <= authority["startedNs"] and
        (not sealing or first == sealed["firstNs"]), "HISTORY_AUTHORITY_CONTEXT_TIME")
    inherited = context["inheritedContext"]
    require(type(inherited) is dict and all(type(item) is str for item in inherited.values()) and
        (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "HISTORY_AUTHORITY_INHERITANCE")
    private_pin = native.directory_identity(context["directoryIdentity"], clock.role)
    for name, expected_hash in (("service/child-result.json", authority["childSha256"]),
            ("source-before/source-return.json", authority["sourceBeforeSha256"]),
            ("source-after/source-return.json", authority["sourceAfterSha256"]),
            ("acquisition-queries/session-result.json", authority["querySessionSha256"]),
            *(("service/" + name, checksum) for name, checksum in authority["phaseSha256"].items()),
            *(("acquisition-queries/" + name + ".bin", checksum) for name, checksum in authority["originalsSha256"].items())):
        require(O.digest(raws[name]) == expected_hash, "HISTORY_AUTHORITY_ORIGINAL_HASH")
    originals = {name: raws["acquisition-queries/" + name + ".bin"] for name in N.ORIGINAL_KEYS}
    require(originals["event"] == prior_raws["event"] and originals["match"] == prior_raws["original-match"] and
        originals["candidate_policy_raw"] == prior_raws["policy"] and all(raws[side_name + "/" + name + ".bin"] == originals[name]
        for side_name in ("source-before", "source-after") for name in N.SOURCE_KEYS), "HISTORY_AUTHORITY_SOURCE_BYTES")
    child = canonical(raws["service/child-result.json"])
    require(child.get("contextSha256") == O.digest(context_raw) and child.get("retirement") == "PENDING_CHILD_CLOSE" and
        child.get("querySessionSha256") == authority["querySessionSha256"], "HISTORY_AUTHORITY_CHILD_BINDINGS")
    _same(child.get("originalsSha256"), authority["originalsSha256"], "HISTORY_AUTHORITY_CHILD_ORIGINALS")
    pins = fields(child.get("directoryIdentities"), ". service", "HISTORY_AUTHORITY_CHILD_PINS")
    _same(pins["."], list(private_pin), "HISTORY_AUTHORITY_ROOT_PIN")
    service_pin = native.directory_identity(pins["service"], clock.role)
    require(private_pin != service_pin, "HISTORY_AUTHORITY_PIN_ALIAS")
    # This helper binds native phase/child byte hashes, not their complete native
    # grammar/outcome. No native object or historical owner is reconstructed.
    rows = [(name, _HISTORICAL_AUTHORITY_LIMITS[name], len(raws[name]), O.digest(raws[name]))
        for name in ("context.json", "service/child-result.json", *("service/" + name for name in sorted(native.PHASE_FILES)))]
    directories = ["", "control-home", "temporary", "service"]
    for side_name in ("source-before", "source-after", "acquisition-queries"):
        query_rows, query_directories = _historical_query_index(context, side_name, raws)
        rows.extend(query_rows)
        directories.extend(query_directories)
    before = canonical(raws["source-before/source-return.json"])["returnedNs"]
    after = canonical(raws["source-after/source-return.json"])["returnedNs"]
    require(type(context["sourceReturnedNs"]) is int and context["sourceReturnedNs"] == before and
        first <= before <= authority["startedNs"] <= authority["acquiredNs"] <= after <= authority["checkedNs"] < end,
        "HISTORY_AUTHORITY_SOURCE_CHRONOLOGY")
    require(len(rows) == 279 and len({row[0].casefold() for row in rows}) == 279 and len(directories) == 58 and
        len({name.casefold() for name in directories}) == 58, "HISTORY_AUTHORITY_EXACT_ROSTER")
    return tuple(sorted(rows)), tuple((name, tuple(private_pin) if not name else tuple(service_pin) if name == "service" else None)
        for name in sorted(directories))


def _historical_tail_authority_indexes(prior_raws, seal_raw, authorities, *, outcome, expected_sha256):
    """558 required file declarations only; no B schema, reads, copy or owner.

    Both original authority episodes must be present. The36 retained binding
    inputs per episode expand to279/58, never substitute for actual custody of
    the original query streams, owners, starts, baselines and result files.
    """
    sealed = _historical_seal_record(seal_raw, prior_raws, outcome=outcome, expected_sha256=expected_sha256)
    parsed = _tail_bundle(prior_raws)
    require(type(authorities) is dict and set(authorities) == {"authority-2", "authority-seal"}, "HISTORY_AUTHORITY_PAIR")
    all_rows, all_directories = [], []
    for side in ("authority-2", "authority-seal"):
        rows, directories = _historical_authority_index(authorities[side], prior_raws, parsed, sealed, side)
        all_rows.extend({"relative": side + "/" + name, "maximum": maximum, "bytes": count, "sha256": checksum}
            for name, maximum, count, checksum in rows)
        all_directories.extend({"relative": side + ("/" + name if name else ""),
            "historicalPin": None if pin is None else list(pin), "provenance":
            "HISTORICAL_CONTEXT_OR_CHILD_PIN" if pin is not None else "HISTORICAL_DECLARED_DIRECTORY_NOT_NATIVE_PIN"}
            for name, pin in directories)
    pins = [tuple(row["historicalPin"]) for row in all_directories if row["historicalPin"] is not None]
    total = sum(row["bytes"] for row in all_rows)
    require(len(pins) == len(set(pins)) == 4 and len(all_rows) == 558 and len(all_directories) == 116 and
        total <= MAX_BYTES, "HISTORY_AUTHORITY_PAIR_LIMIT_OR_ALIAS")
    return O.encoded({"schema": 1, "scope": "INITIAL_CUSTODY_EXISTING_AUTHORITY_REQUIRED_FILES_DATA_V1",
        "sealSha256": O.digest(seal_raw), "files": all_rows, "directories": all_directories,
        "fileCount": 558, "directoryCount": 116, "totalBytes": total,
        "copyState": "NOT_COPIED", "readback": "NOT_PERFORMED", "nativeAcceptance": "NOT_PERFORMED",
        "beforeAuthority": "NOT_IMPLEMENTED", "productiveAuthority": False, "cacheAuthority": False,
        "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"})


def _tail_write(metadata, directory, raw):
    require(type(metadata) is _PrimaryOwner and directory.path.name == "seal", "TAIL_SEAL_FIXED_DIRECTORY")
    canonical(raw)
    reader = metadata.acquire("embedded-reader", lambda: io.BytesIO(raw))
    end = metadata.guard()
    writer = metadata.acquire("writer", lambda: directory.create_file("seal-pending.json", max_bytes=len(raw), deadline=end))
    def verify():
        require(type(reader) is io.BytesIO and reader.getvalue() == raw, "TAIL_SEAL_WRITER_BYTES")
    checksum, _written = _consume(metadata, reader, len(raw), O.digest(raw), verify, writer=writer)
    require(checksum == O.digest(raw) and _read_private(metadata, directory, "seal-pending.json", native.LIMIT) == raw,
        "TAIL_SEAL_WRITER_READBACK")


@dataclass(frozen=True, repr=False)
class _TailSeal:
    authority: object
    raw: bytes
    metadata_close: bytes


def _retain_tail_seal(authority_result):
    attempt = _tail_begin("seal-record")
    attempt["authority"] = authority_result
    metadata = None
    failure = None
    try:
        clock, inputs, authority_raw, _originals = _tail_authority_currency(authority_result)
        raws, _prior_metadata = _checked_tail_input(inputs)
        step, _carrier, _context, manifest, _collected = _tail_bundle(raws)
        authority = _tail_authority_record(authority_raw, step["originalWindow"], clock.first, clock.work)
        graph = N._history_graph(authority_result.__dict__, raws, step, manifest, authority)
        authority_dictionary = authority_result.__dict__
        metadata = _PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
        custody = _paths(step["kind"])[2]
        root, returned, output = (_private(metadata, path) for path in (custody, custody / "returned", custody / "export-output"))
        pins = tuple((directory, directory.path, tuple(directory.identity)) for directory in (root, returned, output))
        original_pins = _TAIL_INPUTS[id(inputs)][6]
        # Original returned pin (+Windows output pin) were checked on input.
        # POSIX output here is THIS tail input→final pin, not a historical pin.
        require(all(pin[1:] == original[1:] for pin, original in zip(pins, original_pins)), "TAIL_SEAL_INPUT_DIRECTORY_PINS")
        require(_tail_directory_names(metadata, root) == _tail_roster("AUTHORITY"), "TAIL_SEAL_INITIAL_ROOT")
        _collect_names(metadata, returned, (_EXPORT_STEP_FILE, _COLLECT_FILE))
        records = _tail_records(returned, output)
        _tail_readback(metadata, records, raws)
        observation = _tail_ciphertext(metadata, output, manifest["artifact"])
        graph = (*graph, *N._history_graph(observation))
        _tail_authority_currency(authority_result)
        directory = _private(metadata, custody / "seal", create=True)
        pins += ((directory, directory.path, tuple(directory.identity)),)
        require(tuple(directory.identity) not in tuple(pin[2] for pin in pins[:-1]) and
            _tail_directory_names(metadata, directory) == (), "TAIL_SEAL_NEW_DIRECTORY")
        last = clock.now()
        last_local = clock._view().local_last
        raw = O.encoded({"schema": 1, "scope": _TAIL_SEAL_SCOPE, "kind": step["kind"], "edge": "SEAL",
            "predecessor": _tail_predecessor(raws, step), "primary": step["primary"],
            **{name: manifest[name] for name in ("source", "github", "policy")}, "originalWindow": step["originalWindow"],
            "firstNs": clock.first, "hardEndNs": clock.work, "lastNs": last, "lastLocal": last_local,
            "manifestSha256": O.digest(raws["manifest"]), "output": observation, "authority": authority,
            "inputMetadataClose": _collect_file_close(inputs.metadata_close), "writerReturn": "PENDING_OWNER_CLOSE",
            "originalStepOutcome": "NOT_OBSERVED", "decryption": "NOT_PERFORMED", "upload": "NOT_PERFORMED",
            "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _tail_seal_record(raw, inputs, authority_raw, clock.first, clock.work)
        _tail_write(metadata, directory, raw)
        require(_tail_directory_names(metadata, directory) == ("seal-pending.json",) and
            _tail_directory_names(metadata, root) == _tail_roster("SEALED"), "TAIL_SEAL_FINAL_ROSTER")
        _collect_names(metadata, returned, (_EXPORT_STEP_FILE, _COLLECT_FILE))
        _tail_readback(metadata, records, raws)
        N._check_history(graph)
        require(authority_result.__dict__ is authority_dictionary, "TAIL_SEAL_AUTHORITY_CHANGED")
        _tail_authority_currency(authority_result)
        closed = metadata.finish()
        clock.now(final=True)
        result = _TailSeal(authority_result, raw, closed)
        saved = (result, result.__dict__, authority_result, authority_dictionary, inputs, raw, closed, clock,
            metadata, metadata._anchor(), pins, attempt,
            N._history_graph(result.__dict__, metadata.owner.__dict__, tuple(pin[1] for pin in pins)), graph)
        _TAIL_SEALS[id(result)] = saved
        attempt["return"], attempt["state"] = result, "RETURNED"
        _checked_tail_seal(result)
        return result
    except BaseException as error:
        failure = error if metadata is None else metadata.remember(error)
    finally:
        if metadata is not None and not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
        if failure is not None:
            if attempt["failure"] is None:
                attempt["failure"] = failure
            attempt["state"] = "FAILED"
    raise attempt["failure"]


def _checked_tail_seal(result):
    saved = _TAIL_SEALS.get(id(result))
    require(type(result) is _TailSeal and type(saved) is tuple and saved[0] is result, "TAIL_NOT_ORIGINAL_SEAL")
    _, dictionary, authority, authority_dictionary, inputs, raw, closed, clock, metadata, anchor, pins, attempt, graph, prior_graph = saved
    try:
        def current():
            require(_TAIL_SEALS.get(id(result)) is saved and result.__dict__ is dictionary and
                result.authority is authority and result.raw == raw and result.metadata_close == closed and
                authority.__dict__ is authority_dictionary and metadata._anchor() is anchor and
                _TAIL_ATTEMPTS.get("seal-record") is attempt and attempt["authority"] is authority and
                attempt["return"] is result and attempt["state"] == "RETURNED" and attempt["failure"] is None,
                "TAIL_SEAL_RETURN_CHANGED")
            N._check_history(graph)
            N._check_history(prior_graph)
            metadata.structural()
            require(metadata.finished and metadata.failure is None and metadata.owner.closed and not metadata.owner.unknown and
                metadata.owner.original is None and metadata.errors == [] and all(a and c for _r, _l, _v, a, c in metadata.rows),
                "TAIL_SEAL_METADATA_CLOSE_UNKNOWN")
            for directory, path, identity in pins:
                require(directory.path is path and tuple(directory.identity) == identity and
                    _collect_directory_closed(directory, clock.clock.role) is True, "TAIL_SEAL_FINAL_PIN_CHANGED")
        current()
        currency = _tail_authority_currency(authority)
        current()
        require(currency[0] is clock and currency[1] is inputs, "TAIL_SEAL_CURRENCY_CHANGED")
        _collect_file_close(closed)
        _tail_seal_record(raw, inputs, currency[2], clock.first, clock.work)
        return clock, clock.work, {"initialSealSha256": O.digest(raw)}
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def _tail_output_values(result, *, for_before):
    """Same original live seal, optionally exposing its old absolute deadline.

    This is not BEFORE entry, a new clock, an owner deserializer or a grant.
    The returned output limit remains the seal's own narrower clock.work.
    """
    require(type(for_before) is bool, "TAIL_OUTPUT_MODE")
    clock, limit, values = _checked_tail_seal(result)
    if for_before:
        frame = canonical(result.raw)["originalWindow"]
        declared, _limits = _custody_authority_frame(frame)
        require(declared == clock.clock, "TAIL_OUTPUT_ORIGINAL_CLOCK")
        _same(frame, clock.frame, "TAIL_OUTPUT_ORIGINAL_WINDOW")
        values = {"initialSealSha256": values["initialSealSha256"],
            "initialSealEndNs": str(frame["sealEndNs"]),
            "initialSealClockRole": declared.role, "initialSealClockDomain": declared.domain,
            "initialSealClockTicksPerSecond": str(declared.ticks_per_second),
            "initialSealBootSha256": frame["originalBootDigest"]}
        C.seal_deadline_data(values)
    return clock, limit, values


class _TailOutputFence:
    """One known-closed seal, one append, exactly the two existing late checks."""
    __slots__ = ("_binding",)

    def __init__(self, result, *, for_before=False):
        require(type(self) is _TailOutputFence and id(self) not in _TAIL_OUTPUTS, "TAIL_OUTPUT_NEW")
        returned = _TAIL_SEALS.get(id(result))
        require(type(result) is _TailSeal and type(returned) is tuple and returned[0] is result and
            not any(saved[1][0] is result for saved in _TAIL_OUTPUTS.values()), "TAIL_OUTPUT_ORIGINAL_OR_REUSE")
        clock, limit, values = _tail_output_values(result, for_before=for_before)
        mode = {"forBefore": for_before}
        scope = ("INITIAL_SEAL_DEADLINE_PENDING_ORIGINAL_STEP_RETURN_V1" if for_before else
            "INITIAL_SEAL_DIGEST_PENDING_ORIGINAL_STEP_RETURN_V1")
        value = {"schema": 1, "scope": scope, **values,
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        # Append the mode pin; all eight legacy binding indices stay unchanged.
        self._binding = (result, returned, result.__dict__, clock, limit, values, value,
            N._history_graph(values, value, mode), mode)
        _TAIL_OUTPUTS[id(self)] = (self, self._binding, {"phase": "NEW", "checks": 0, "busy": False, "failure": None})

    def _original(self):
        saved = _TAIL_OUTPUTS.get(id(self))
        require(type(self) is _TailOutputFence and type(saved) is tuple and saved[0] is self, "TAIL_OUTPUT_ORIGINAL_FACADE")
        return saved

    @staticmethod
    def _fail(saved, error):
        if saved[2]["failure"] is None:
            saved[2]["failure"] = error
        return saved[2]["failure"]

    def _begin(self):
        saved = self._original()
        if saved[2]["failure"] is not None:
            raise saved[2]["failure"]
        try:
            require(self._binding is saved[1] and not saved[2]["busy"], "TAIL_OUTPUT_REENTRY_OR_BINDING")
            saved[2]["busy"] = True
            return saved
        except BaseException as error:
            raise self._fail(saved, error)

    def _current(self, saved):
        require(self._original() is saved and self._binding is saved[1] and saved[2]["busy"] and saved[2]["failure"] is None,
            "TAIL_OUTPUT_CHANGED")
        result, returned, dictionary, clock, limit, values, value, graph, mode = saved[1]
        require(_TAIL_SEALS.get(id(result)) is returned and result.__dict__ is dictionary and not C.QUARANTINE and
            not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE, "TAIL_OUTPUT_RETURN_CHANGED")
        N._check_history(graph)
        current = _tail_output_values(result, for_before=mode["forBefore"])
        require(current[0] is clock and type(current[1]) is int and current[1] == limit and current[2] == values,
            "TAIL_OUTPUT_ORIGINAL_DIGEST")
        N._check_history(graph)
        require(self._original() is saved and self._binding is saved[1] and saved[2]["busy"] and saved[2]["failure"] is None and
            _TAIL_SEALS.get(id(result)) is returned and result.__dict__ is dictionary, "TAIL_OUTPUT_CALLBACK_CHANGED")
        return clock, limit, values, value

    def _append_guard(self):
        saved = self._begin()
        try:
            require(saved[2]["phase"] == "APPENDING" and saved[2]["checks"] == 0, "TAIL_OUTPUT_APPEND_PHASE")
            clock, limit, _values, _value = self._current(saved)
            clock.now(final=True, limit=limit)
            self._current(saved)
        except BaseException as error:
            raise self._fail(saved, error)
        finally:
            saved[2]["busy"] = False

    def append(self):
        saved = self._begin()
        try:
            require(saved[2]["phase"] == "NEW" and saved[2]["checks"] == 0, "TAIL_OUTPUT_APPEND_ONCE")
            _clock, limit, values, value = self._current(saved)
            saved[2]["phase"] = "APPENDING"
        except BaseException as error:
            raise self._fail(saved, error)
        finally:
            saved[2]["busy"] = False
        try:
            C.append_outputs(values, self._append_guard)
            self._append_guard()
            require(self._original() is saved and saved[2]["phase"] == "APPENDING" and saved[2]["failure"] is None,
                "TAIL_OUTPUT_APPEND_RETURN_CHANGED")
            saved[2]["phase"] = "OUTPUT"
            return value, self, limit
        except BaseException as error:
            raise self._fail(saved, error)

    def now(self, *, final=False, minimum=0, limit=None):
        saved = self._begin()
        try:
            require(saved[2]["phase"] == "OUTPUT" and type(final) is bool and final is True and
                type(minimum) is int and minimum == 0 and type(limit) is int and limit == saved[1][4] and
                type(saved[2]["checks"]) is int and 0 <= saved[2]["checks"] < 2, "TAIL_OUTPUT_EXACT_LATE_CHECK")
            saved[2]["checks"] += 1
            clock, original_limit, _values, _value = self._current(saved)
            observed = clock.now(final=True, limit=original_limit)
            self._current(saved)
            return observed
        except BaseException as error:
            raise self._fail(saved, error)
        finally:
            saved[2]["busy"] = False


def _seal(kind, cancelled, *, for_before):
    require(type(for_before) is bool, "TAIL_OUTPUT_MODE")
    attempt = _tail_begin("seal-entry")
    try:
        authority = _tail_pre_metadata(kind, cancelled)
        # This frame never held a token; the new authority owner is CLOSED.
        result = _retain_tail_seal(authority)
        output = _TailOutputFence(result, for_before=for_before).append()
        require(_TAIL_ATTEMPTS.get("seal-entry") is attempt and attempt["state"] == "STARTED" and
            attempt["failure"] is None, "TAIL_SEAL_ENTRY_CHANGED")
        attempt["state"] = "RETURNED"
        return output
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def seal(kind, cancelled):
    return _seal(kind, cancelled, for_before=False)


def seal_for_before(kind, cancelled):
    """Opt-in original seal episode only; no BEFORE acquisition or workflow."""
    return _seal(kind, cancelled, for_before=True)


# BEFORE is a new actual same-process authority episode. Neither the old seal
# JSON nor its already-consumed TailClock registry is an executable capability.
_BEFORE_NAMES = (*_TAIL_NAMES, B.SEAL_OUTCOME_ENV, *(environment for _name, environment, _flag in B.SEED_FIELDS))
_BEFORE_CONTEXT_FIELDS = "schema scope edge kind root session job observed originalWindow originalServiceJob " \
    "predecessor expectedMatch eventSha256 sourceReturnSha256 sourceReturnedNs inheritedContext directoryIdentity " \
    "parentFirstNs parentFirstLocal continuationEndNs deadline selectedInputs inputMetadata budgetAcceptance exportSaveAuthority"
_BEFORE_ATTEMPTS, _BEFORE_INPUTS, _BEFORE_CLOCKS, _BEFORE_AUTHORITIES = {}, {}, {}, {}
_BEFORE_ENTRY = B.EntryLatch(_BEFORE_ATTEMPTS)


def _before_begin(name):
    require(name in ("entry", "authority"), "BEFORE_ATTEMPT_NAME")
    if name == "entry":
        return _BEFORE_ENTRY.begin(_BEFORE_ATTEMPTS)
    previous = _BEFORE_ATTEMPTS.get(name)
    if previous is not None:
        if previous["failure"] is None:
            previous["failure"] = O.OriginError("INITIAL_CUSTODY_BEFORE_ATTEMPT_REUSE")
        previous["state"] = "FAILED"
        raise previous["failure"]
    result = {"state": "STARTED", "failure": None, "return": None}
    _BEFORE_ATTEMPTS[name] = result
    return result


def _before_entry_current(entry):
    """The original parent latch and attempt, never a child/context capability."""
    require(type(entry) is tuple and len(entry) == 2 and type(entry[0]) is B.EntryLatch,
        "BEFORE_ENTRY_BINDING")
    original, attempt = entry
    try:
        require(original is _BEFORE_ENTRY, "BEFORE_ENTRY_LATCH_REPLACED")
        original.check(_BEFORE_ATTEMPTS, attempt)
    except BaseException as error:
        raise original.fail(error)


def _before_actual(expected=None):
    _tail_actual()
    actual = tuple(os.environ.get(name) for name in _BEFORE_NAMES)
    require((expected is None or type(expected) is tuple and actual == expected) and
        os.environ.get(B.SEAL_OUTCOME_ENV) == "success", "BEFORE_ACTUAL_SEAL_SUCCESS")
    seed = {name: os.environ.get(environment) for name, environment, _flag in B.SEED_FIELDS}
    C.seal_deadline_data(seed)
    return actual, seed


def _before_selected(actual):
    """Only the selected nonsecret Step input strings, not the whole environment."""
    require(type(actual) is tuple and len(actual) == len(_BEFORE_NAMES), "BEFORE_SELECTED_INPUTS")
    saved = dict(zip(_BEFORE_NAMES, actual))
    names = (PRIMARY_OUTCOME, PRIMARY_RESULT, PRIMARY_HANDOFF, _COLLECT_OUTCOME, _COLLECT_STEP_HASH,
        _COLLECT_EXPORT_HASH, _TAIL_OUTCOME, _TAIL_HASH, _TAIL_EXPORT_HASH, B.SEAL_OUTCOME_ENV,
        *(environment for _name, environment, _flag in B.SEED_FIELDS))
    return {name: saved[name] for name in names}


def _before_roster(*, created):
    require(type(created) is bool, "BEFORE_ROOT_STAGE")
    return tuple(sorted((*_tail_roster("SEALED"), *(("authority-before",) if created else ()))))


def _before_metadata(value, role, count):
    """Validate retained actual metadata DATA, never open/reconstruct a file."""
    require(type(count) is int and 0 <= count <= native.LIMIT, "BEFORE_METADATA_COUNT")
    if role == "windows-x64":
        fields(value, "identity is_directory size links attributes creation_100ns modified_100ns change_100ns owner_sid protected_dacl",
            "BEFORE_WINDOWS_METADATA_FIELDS")
        identity = tuple(native.directory_identity(value["identity"], role))
        require(value["is_directory"] is False and type(value["links"]) is int and value["links"] == 1 and
            type(value["owner_sid"]) is str and re.fullmatch(r"S-1-[0-9-]{1,180}", value["owner_sid"]) and
            type(value["protected_dacl"]) is bool, "BEFORE_WINDOWS_PRIVATE_METADATA")
        for name in ("attributes", "creation_100ns", "modified_100ns", "change_100ns"):
            O.integer(value[name])
    else:
        require(role in O.clocks.DOMAINS, "BEFORE_METADATA_ROLE")
        fields(value, "device inode size mtime_ns ctime_ns", "BEFORE_POSIX_METADATA_FIELDS")
        identity = tuple(native.directory_identity([value["device"], value["inode"]], role))
        O.integer(value["mtime_ns"])
        O.integer(value["ctime_ns"])
    require(type(value["size"]) is int and value["size"] == count, "BEFORE_METADATA_SIZE")
    return identity


def _before_read(metadata, directory, name, maximum, *, count=None, checksum=None):
    """Actual bounded read, EOF, stable native metadata and real reader close.

    Unlike the unchanged legacy _read_private contract, retain the actual
    reader metadata in canonical bytes before streaming, not only its payload.
    The maintained owner already pins the returned reader before its own
    allocation-return callback. This serves all279 originals, eleven inputs
    and the separate close file; it is not a new native-file backend.
    """
    require(type(metadata) is _PrimaryOwner and type(maximum) is int and 0 < maximum <= native.LIMIT,
        "BEFORE_READER_LIMIT")
    Q._component(name)
    end, path = metadata.guard(), directory.path / name
    if os.name == "nt":
        reader = metadata.acquire("reader", lambda: directory.open_file(name, max_bytes=maximum, deadline=end))
        require(type(reader) is native.windows.NativeFile, "BEFORE_READER_TYPE")
        original = reader.initial_info
        def verify():
            require(reader.verify() == original, "BEFORE_READER_METADATA_CHANGED")
    else:
        reader = metadata.acquire("reader", lambda: Q._posix_stream(path, os.O_RDONLY | os.O_NOFOLLOW, "rb"))
        require(type(reader) is io.BufferedReader, "BEFORE_READER_TYPE")
        original = Q._file_info(path, reader, maximum)
        def verify():
            directory.verify()
            require(Q._file_info(path, reader, maximum) == original, "BEFORE_READER_METADATA_CHANGED")
    original_raw = O.encoded(original.as_dict())
    observed_count, ordinal = original.size, len(metadata.rows) - 1
    require(type(observed_count) is int and 0 <= observed_count <= maximum and
        (count is None or type(count) is int and observed_count == count), "BEFORE_READER_DECLARED_SIZE")
    info = canonical(original_raw)
    _before_metadata(info, metadata.owner.first.clock.role, observed_count)
    raw = _consume(metadata, reader, observed_count, checksum, verify, retain=True)
    require(metadata.rows[ordinal][2] is reader and metadata.rows[ordinal][3:] == (True, True) and
        O.encoded(original.as_dict()) == original_raw, "BEFORE_READER_ORIGINAL_CLOSE")
    return raw, {"bytes": observed_count, "sha256": O.digest(raw), "metadata": info,
        "readerOrdinal": ordinal, "retirement": "KNOWN_READER_CLOSE"}


def _before_same_read(first, second):
    _same({name: first[name] for name in ("bytes", "sha256", "metadata", "retirement")},
        {name: second[name] for name in ("bytes", "sha256", "metadata", "retirement")}, "BEFORE_READBACK_CHANGED")


def _before_originals():
    return (("seal", "seal/seal-pending.json", native.LIMIT),
        *( (name, ("export-output/" if name == "manifest" else "returned/") + leaf, _TAIL_LIMITS[name])
            for name, _directory, leaf in _tail_records(None, None)))


def _before_input_data(value, role):
    """Closed retained-input grammar only; the actual registry is separate."""
    fields(value, "firstNs firstLocal closedNs closedLocal files ownerClose", "BEFORE_INPUT_DATA_FIELDS")
    require(O.integer(value["firstNs"]) <= O.integer(value["closedNs"]) and
        local_value(value["firstLocal"]) <= local_value(value["closedLocal"]), "BEFORE_INPUT_DATA_CHRONOLOGY")
    close = _collect_file_close(O.encoded(value["ownerClose"]))
    require(type(value["files"]) is list and len(value["files"]) == 11, "BEFORE_ELEVEN_INPUTS")
    ordinals, identities = set(), set()
    for row, (key, relative, maximum) in zip(value["files"], _before_originals()):
        fields(row, "key relative maximum first readback", "BEFORE_INPUT_READ_FIELDS")
        require((row["key"], row["relative"]) == (key, relative) and type(row["maximum"]) is int and
            row["maximum"] == maximum, "BEFORE_INPUT_READ_PATH")
        for read in (row["first"], row["readback"]):
            fields(read, "bytes sha256 metadata readerOrdinal retirement", "BEFORE_READ_FIELDS")
            count = O.integer(read["bytes"], 1)
            digest(read["sha256"])
            ordinal = O.integer(read["readerOrdinal"])
            identity = _before_metadata(read["metadata"], role, count)
            require(count <= maximum and ordinal not in ordinals and ordinal < len(close["resources"]) and
                close["resources"][ordinal]["label"] == "reader" and read["retirement"] == "KNOWN_READER_CLOSE",
                "BEFORE_INPUT_READER_CLOSE")
            ordinals.add(ordinal)
        _before_same_read(row["first"], row["readback"])
        require(identity not in identities, "BEFORE_INPUT_FILE_ALIAS")
        identities.add(identity)
    require(len(close["resources"]) == 26 and len(ordinals) == 22 and
        sum(row["label"] == "directory" for row in close["resources"]) == 4, "BEFORE_INPUT_FULL_CLOSE_ROSTER")
    return value


@dataclass(frozen=True, repr=False)
class _BeforeInput:
    originals: tuple
    metadata: bytes


def _checked_before_input(result):
    saved = _BEFORE_INPUTS.get(id(result))
    require(type(result) is _BeforeInput and type(saved) is tuple and saved[0] is result, "BEFORE_ORIGINAL_INPUT")
    _, dictionary, originals, raw, metadata, anchor, pins, graph, actual = saved
    require(result.__dict__ is dictionary and result.originals is originals and result.metadata == raw and
        metadata._anchor() is anchor, "BEFORE_INPUT_CHANGED")
    N._check_history(graph)
    _before_actual(actual)
    metadata.structural()
    require(metadata.finished and metadata.failure is None and metadata.owner.closed and not metadata.owner.unknown and
        metadata.owner.original is None and metadata.errors == [] and all(a and c for _r, _l, _v, a, c in metadata.rows),
        "BEFORE_INPUT_CLOSE_UNKNOWN")
    for _name, directory, path, identity in pins:
        require(directory.path is path and tuple(directory.identity) == identity and
            _collect_directory_closed(directory, metadata.owner.first.clock.role) is True, "BEFORE_INPUT_PIN_CHANGED")
    value = _before_input_data(canonical(raw), metadata.owner.first.clock.role)
    require(tuple((row["key"], row["first"]["sha256"]) for row in value["files"]) ==
        tuple((name, O.digest(data)) for name, data in originals), "BEFORE_INPUT_HASH_CHANGED")
    return dict(originals), value, metadata


@dataclass(eq=False, repr=False)
class _BeforeClockAnchor:
    handle: object
    binding: tuple
    graph: tuple
    last: int
    local_last: float
    metadata: object = None
    frame: object = None
    frame_graph: tuple = ()
    bound: object = None
    bound_graph: tuple = ()
    operative: object = None
    file_owners: tuple = ()
    phase: str = "METADATA"
    busy: bool = False
    failure: object = None


class _BeforeClock:
    """New one-shot B clock, capped BEFORE its first owner/read.

    Parent seed gives the original absolute sealEnd, not a new FIRST+allowance.
    The child additionally inherits native.phase's actual work/final tuple in
    fixed argv. All original caps/LOCAL pairs remain immutable; no old clock,
    Date, JSON owner, read failure or cleanup callback can renew them.
    """
    __slots__ = ("_binding",)

    def __init__(self, first, local, boot, cancelled, seed, *, side, actual=None, inherited=None, entry=None):
        require(type(self) is _BeforeClock and id(self) not in _BEFORE_CLOCKS and side in ("parent", "child") and
            callable(cancelled), "BEFORE_CLOCK_NEW")
        graph = N._history_graph(first, seed, actual, inherited)
        local_value(local)
        work, final = B.first_caps(seed, first, boot, inherited=inherited)
        require((side == "parent" and inherited is None and type(actual) is tuple) or
            (side == "child" and type(inherited) is tuple and actual is None and entry is None), "BEFORE_CLOCK_SIDE")
        if side == "parent":
            _before_entry_current(entry)
        local_work = O.wire._directed_deadline(local, (work - first.nanoseconds) / O.NS, work, first.nanoseconds)
        local_final = O.wire._directed_deadline(local, (final - first.nanoseconds) / O.NS, final, first.nanoseconds)
        self._binding = (first, local, boot, cancelled, side, seed, actual, inherited,
            (work, final, local_work, local_final), entry)
        N._check_history(graph)
        _BEFORE_CLOCKS[id(self)] = _BeforeClockAnchor(self, self._binding, graph, first.nanoseconds, local)
        self._view()

    def _anchor(self):
        anchor = _BEFORE_CLOCKS.get(id(self))
        require(type(self) is _BeforeClock and type(anchor) is _BeforeClockAnchor and anchor.handle is self,
            "BEFORE_CLOCK_HANDLE")
        return anchor

    @staticmethod
    def _error(anchor, error):
        if anchor.binding[4] == "parent":
            error = anchor.binding[9][0].fail(error)
        if anchor.failure is None:
            anchor.failure = error
        return anchor.failure

    def _current(self, anchor):
        require(_BEFORE_CLOCKS.get(id(self)) is anchor and self._binding is anchor.binding and anchor.handle is self,
            "BEFORE_CLOCK_BINDING_CHANGED")
        if anchor.binding[4] == "parent":
            _before_entry_current(anchor.binding[9])
        for graph in (anchor.graph, anchor.frame_graph, anchor.bound_graph):
            N._check_history(graph)
        if anchor.binding[4] == "parent":
            _actual, seed = _before_actual(anchor.binding[6])
            _same(seed, anchor.binding[5], "BEFORE_CLOCK_SEED_CHANGED")
        require(not native.QUARANTINE and not Q.QUARANTINE and not C.QUARANTINE and
            not native.diagnostics._QUARANTINE, "BEFORE_CLOCK_UNKNOWN")
        if anchor.metadata is not None:
            anchor.metadata.structural()
            require(anchor.metadata.failure is None and not anchor.metadata.owner.unknown, "BEFORE_METADATA_FAILED")
        if anchor.bound is not None:
            if anchor.binding[4] == "parent":
                _checked_before_input(anchor.bound[0])
            _custody_match_check(anchor.bound[-1])
        if anchor.operative is not None:
            require(type(anchor.operative) is _CustodyOwner and anchor.operative.fence is self,
                "BEFORE_OPERATIVE_CHANGED")
            anchor.operative.check()
            require(anchor.operative.original is None and not anchor.operative.unknown, "BEFORE_OPERATIVE_FAILED")
        for _name, owner, saved in anchor.file_owners:
            require(owner._anchor() is saved and owner.owner.fence is self, "BEFORE_FILE_OWNER_CHANGED")
            owner.structural()
            require(owner.failure is None and not owner.owner.unknown, "BEFORE_FILE_OWNER_FAILED")

    def _view(self):
        anchor = self._anchor()
        try:
            self._current(anchor)
            return anchor
        except BaseException as error:
            raise self._error(anchor, error)

    reading = property(lambda self: self._view().binding[0])
    clock = property(lambda self: self.reading.clock)
    first = property(lambda self: self.reading.nanoseconds)
    first_local = property(lambda self: self._view().binding[1])
    cancelled = property(lambda self: self._view().binding[3])
    side = property(lambda self: self._view().binding[4])
    seed = property(lambda self: self._view().binding[5])
    inherited = property(lambda self: self._view().binding[7])
    work = property(lambda self: self._view().binding[8][0])
    final = property(lambda self: self._view().binding[8][1])
    local_end = property(lambda self: self._view().binding[8][3])
    last = property(lambda self: self._view().last)

    @property
    def frame(self):
        anchor = self._view()
        require(anchor.frame is not None, "BEFORE_WINDOW_NOT_REBOUND")
        return anchor.frame[2]

    def _begin(self):
        anchor = self._anchor()
        if anchor.failure is not None:
            raise anchor.failure
        try:
            self._current(anchor)
            require(not anchor.busy, "BEFORE_CLOCK_REENTRY")
            anchor.busy = True
            return anchor
        except BaseException as error:
            raise self._error(anchor, error)

    def _local(self, anchor, final):
        value = local_value(time.monotonic())
        require(value >= anchor.local_last, "BEFORE_LOCAL_BACKWARDS")
        anchor.local_last = value
        self._current(anchor)
        require(value < anchor.binding[8][3 if final else 2], "BEFORE_LOCAL_EXPIRED")
        return value

    def _observe(self, anchor, final, minimum, limit):
        end = anchor.binding[8][1 if final else 0]
        if limit is not None:
            end = min(end, O.integer(limit))
        frontier = max(anchor.last, O.integer(minimum))
        for number in range(2):
            local = self._local(anchor, final)
            observed = O.clocks.checked_now(anchor.binding[0].clock, minimum_ns=frontier)
            anchor.last = frontier = O.integer(observed, frontier)
            self._current(anchor)
            require(frontier < end and anchor.busy and anchor.failure is None, "BEFORE_RAW_EXPIRED_OR_CHANGED")
            boot = C.boot_digest(anchor.binding[0].clock.role)
            self._current(anchor)
            require(type(boot) is str and boot == anchor.binding[2], "BEFORE_BOOT_CHANGED")
            if number == 0:
                anchor.binding[3]()
                self._current(anchor)
                require(anchor.last == frontier and anchor.local_last == local and anchor.failure is None and anchor.busy,
                    "BEFORE_CALLBACK_CHANGED")
        self._local(anchor, final)
        self._current(anchor)
        require(anchor.last == frontier and anchor.busy and anchor.failure is None, "BEFORE_FRONTIER_CHANGED")
        return frontier

    def now(self, *, final=False, minimum=0, limit=None):
        anchor = self._begin()
        try:
            require(type(final) is bool, "BEFORE_FINAL_TYPE")
            return self._observe(anchor, final, minimum, limit)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def deadline(self, maximum, *, final=False, limit=None):
        anchor = self._begin()
        try:
            require(type(final) is bool and type(maximum) in (int, float) and math.isfinite(maximum) and
                0 < maximum <= 900, "BEFORE_MECHANISM_MAXIMUM")
            local = self._local(anchor, final)
            observed = self._observe(anchor, final, 0, limit)
            end = anchor.binding[8][1 if final else 0]
            if limit is not None:
                end = min(end, O.integer(limit))
            result = min(anchor.binding[8][3 if final else 2],
                O.wire._directed_deadline(local, maximum, end, observed))
            self._current(anchor)
            require(anchor.busy and anchor.failure is None, "BEFORE_DEADLINE_CHANGED")
            return result
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def attach_metadata(self, metadata):
        anchor = self._begin()
        try:
            require(anchor.phase == "METADATA" and anchor.metadata is None and type(metadata) is _PrimaryOwner and
                metadata.owner.fence is self and metadata.owner.first is anchor.binding[0] and
                not metadata.finished and not metadata.rows, "BEFORE_METADATA_ORIGINAL_OWNER")
            anchor.metadata = metadata
            self._current(anchor)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def _rebind(self, anchor, raw, value, frame):
        require(anchor.phase == "METADATA" and anchor.frame is None and anchor.bound is None and
            anchor.metadata is not None and not anchor.metadata.finished, "BEFORE_WINDOW_REBIND_ONCE")
        rows = anchor.metadata.rows
        require(len(rows) == 2 and tuple(row[1] for row in rows) == ("directory", "reader") and
            rows[0][3:] == (False, False) and rows[1][3:] == (True, True), "BEFORE_FIRST_READER_NOT_CLOSED")
        frame_clock, _limits = _custody_authority_frame(frame)
        _sha, end, seed_clock, boot = C.seal_deadline_data(anchor.binding[5])
        _same(O.clock_value(frame_clock), O.clock_value(seed_clock), "BEFORE_WINDOW_CLOCK")
        require(frame["sealEndNs"] == end and frame["originalBootDigest"] == boot == anchor.binding[2],
            "BEFORE_WINDOW_DEADLINE_CHANGED")
        anchor.frame = (raw, value, frame)
        anchor.frame_graph = N._history_graph(anchor.frame)
        anchor.phase = "WINDOW_BOUND"
        self._current(anchor)
        self._observe(anchor, False, anchor.last, None)

    def rebind_seal(self, raw):
        anchor = self._begin()
        try:
            require(anchor.binding[4] == "parent" and O.digest(raw) == anchor.binding[5]["initialSealSha256"],
                "BEFORE_FIRST_SEAL_HASH")
            value = canonical(raw)
            require(type(value.get("schema")) is int and value["schema"] == 1 and value.get("scope") == _TAIL_SEAL_SCOPE and
                value.get("edge") == "SEAL" and O.integer(value.get("lastNs")) <= anchor.binding[0].nanoseconds and
                local_value(value.get("lastLocal")) <= anchor.binding[1], "BEFORE_FIRST_SEAL_FLOOR")
            self._rebind(anchor, raw, value, value["originalWindow"])
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def rebind_context(self, raw):
        anchor = self._begin()
        try:
            require(anchor.binding[4] == "child", "BEFORE_CHILD_SIDE")
            context = _before_context(raw, anchor.binding[0].clock)
            _same(context["deadline"], anchor.binding[5], "BEFORE_CHILD_SEED_CHANGED")
            require(context["parentFirstNs"] <= anchor.binding[0].nanoseconds and
                context["parentFirstLocal"] <= anchor.binding[1], "BEFORE_CHILD_PARENT_FLOOR")
            self._rebind(anchor, raw, context, context["originalWindow"])
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def _bind_begin(self, anchor, side):
        require(anchor.binding[4] == side and anchor.phase == "WINDOW_BOUND" and anchor.bound is None and
            anchor.metadata is not None, "BEFORE_BIND_ONCE")
        anchor.phase = "BINDING"
        metadata = anchor.metadata
        metadata.structural()
        require(metadata.finished and metadata.failure is None and metadata.owner.closed and
            metadata.owner.original is None and not metadata.owner.unknown and not metadata.errors and
            all(a and c for _r, _l, _v, a, c in metadata.rows), "BEFORE_METADATA_NOT_CLOSED")
        self._observe(anchor, False, anchor.last, None)

    def bind_parent(self, result):
        anchor = self._begin()
        try:
            self._bind_begin(anchor, "parent")
            raws, value, metadata = _checked_before_input(result)
            require(metadata is anchor.metadata and raws["seal"] == anchor.frame[0], "BEFORE_ORIGINAL_METADATA")
            prior = {name: raws[name] for name in _TAIL_LIMITS}
            parsed = _tail_bundle(prior)
            sealed = _historical_seal_record(raws["seal"], prior, outcome="success",
                expected_sha256=anchor.binding[5]["initialSealSha256"])
            _same(sealed, anchor.frame[1], "BEFORE_ORIGINAL_SEAL_CHANGED")
            require(sealed["lastNs"] <= value["firstNs"] <= value["closedNs"] <= anchor.last and
                sealed["lastLocal"] <= value["firstLocal"] <= value["closedLocal"] <= anchor.local_last,
                "BEFORE_METADATA_ORIGINAL_FLOORS")
            expected = _tail_host(prior, parsed, anchor.binding[0].clock)
            anchor.bound = (result, raws, parsed, sealed, _custody_match_pin(expected, parsed[0]["kind"]))
            anchor.bound_graph = N._history_graph(anchor.bound)
            anchor.phase = "AUTHORITY"
            self._current(anchor)
            self._observe(anchor, False, anchor.last, None)
            return expected
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def bind_child(self, context_raw, start_raw, event, inherited, minimum):
        anchor = self._begin()
        try:
            self._bind_begin(anchor, "child")
            context = _before_context(context_raw, anchor.binding[0].clock)
            require(context_raw == anchor.frame[0], "BEFORE_CHILD_ORIGINAL_CONTEXT")
            expected = _before_child_host(context, event, anchor.binding[0], anchor.binding[2])
            start = _before_start_fields(start_raw, context_raw, context, anchor.binding[0].clock)
            caps = tuple(start[name] for name, _flag in B.PHASE_FIELDS)
            require(caps == anchor.binding[7] and type(inherited) is dict and set(inherited) == set(Q._CONTEXT) and
                start["startedNs"] <= O.integer(minimum) <= anchor.binding[0].nanoseconds < start["workEndNs"],
                "BEFORE_CHILD_INHERITED_CAPS")
            _same(inherited, start["inheritedContext"], "BEFORE_CHILD_INHERITED_CONTEXT")
            domain = native.processes.ownership_domains(inherited[native.processes.CHAIN_ENV],
                inherited[native.processes.DOMAINS_ENV])[-1]
            _same(domain, {"id": start["invocation"], "job": start["job"], "state": start["state"], "home": start["home"]},
                "BEFORE_CHILD_NATIVE_DOMAIN")
            anchor.bound = (None, context_raw, context, start_raw, start, event, inherited,
                _custody_match_pin(expected, context["kind"]))
            anchor.bound_graph = N._history_graph(anchor.bound)
            anchor.phase = "AUTHORITY"
            self._current(anchor)
            self._observe(anchor, False, anchor.last, None)
            return context, start, expected, domain
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def attach_operative(self, owner):
        anchor = self._begin()
        try:
            require(anchor.phase == "AUTHORITY" and anchor.operative is None and type(owner) is _CustodyOwner and
                owner.first is anchor.binding[0] and owner.fence is self and not owner.closed and
                owner.original is None and not owner.unknown and not owner.resources, "BEFORE_ORIGINAL_AUTHORITY_OWNER")
            anchor.operative = owner
            self._current(anchor)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False

    def attach_file_owner(self, name, owner):
        anchor = self._begin()
        try:
            expected = ("readback", "writer")
            require(anchor.binding[4] == "parent" and anchor.phase == "AUTHORITY" and anchor.operative is not None and
                len(anchor.file_owners) < 2 and name == expected[len(anchor.file_owners)] and
                type(owner) is _PrimaryOwner and owner.owner.fence is self and owner.owner.first is anchor.binding[0] and
                not owner.finished and not owner.rows, "BEFORE_ORIGINAL_FILE_OWNER")
            if name == "writer":
                anchor.operative.known()
                require(anchor.file_owners[0][1].finished, "BEFORE_READBACK_NOT_CLOSED")
            else:
                require(not anchor.operative.closed, "BEFORE_READBACK_AUTHORITY_CLOSED")
            anchor.file_owners = (*anchor.file_owners, (name, owner, owner._anchor()))
            self._current(anchor)
        except BaseException as error:
            raise self._error(anchor, error)
        finally:
            anchor.busy = False


def _read_before_input(clock, kind, actual):
    metadata = _PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
    failure = None
    try:
        clock.attach_metadata(metadata)
        _before_actual(actual)
        custody = _paths(kind)[2]
        seal_directory = _private(metadata, custody / "seal")
        seal_raw, first_read = _before_read(metadata, seal_directory, "seal-pending.json", native.LIMIT)
        # The seed's original RAW/LOCAL caps preceded the owner/open. This merely
        # rebinds those same already-enforced caps to the FIRST known-close read.
        clock.rebind_seal(seal_raw)
        root = _private(metadata, custody)
        returned = _private(metadata, custody / "returned")
        output = _private(metadata, custody / "export-output")
        pins = tuple((name, directory, directory.path, tuple(directory.identity)) for name, directory in
            (("seal", seal_directory), (".", root), ("returned", returned), ("export-output", output)))
        require(len({pin[3] for pin in pins}) == 4 and _tail_directory_names(metadata, root) == _before_roster(created=False) and
            _tail_directory_names(metadata, seal_directory) == ("seal-pending.json",), "BEFORE_INPUT_SEALED_ROOT")
        _collect_names(metadata, returned, (_EXPORT_STEP_FILE, _COLLECT_FILE))
        records = (("seal", seal_directory, "seal-pending.json"), *_tail_records(returned, output))
        originals, reads = [("seal", seal_raw)], [first_read]
        for name, directory, leaf in records[1:]:
            raw, read = _before_read(metadata, directory, leaf, _TAIL_LIMITS[name])
            originals.append((name, raw))
            reads.append(read)
        originals = tuple(originals)
        raws = dict(originals)
        prior = {name: raws[name] for name in _TAIL_LIMITS}
        parsed = _tail_bundle(prior)
        sealed = _historical_seal_record(seal_raw, prior, outcome="success", expected_sha256=clock.seed["initialSealSha256"])
        step, _carrier, context, _manifest, _collected = parsed
        require(step["kind"] == kind and step["primary"]["resultSha256"] == os.environ[PRIMARY_RESULT] and
            step["primary"]["handoffSha256"] == os.environ[PRIMARY_HANDOFF] and
            step["cryptoCarrier"]["exporterReturnSha256"] == os.environ[_TAIL_EXPORT_HASH] and
            O.digest(raws["step"]) == os.environ[_COLLECT_STEP_HASH] and O.digest(raws["collect"]) == os.environ[_TAIL_HASH],
            "BEFORE_ACTUAL_PREDECESSORS")
        _same(step["directoryIdentity"], list(pins[2][3]), "BEFORE_ORIGINAL_RETURNED_PIN")
        if context["directories"]["export-output"] is not None:
            _same(context["directories"]["export-output"], list(pins[3][3]), "BEFORE_ORIGINAL_WINDOWS_OUTPUT_PIN")
        _same(sealed["output"]["directoryIdentity"], list(pins[3][3]), "BEFORE_SEAL_OBSERVED_OUTPUT_PIN")
        _same(sealed["originalWindow"], clock.frame, "BEFORE_ORIGINAL_SEAL_WINDOW")
        _tail_host(prior, parsed, clock.clock)
        graph = N._history_graph(originals, reads, parsed, sealed, tuple(pin[2] for pin in pins))
        readbacks = []
        for (name, directory, leaf), read in zip(records, reads):
            raw, second = _before_read(metadata, directory, leaf, native.LIMIT if name == "seal" else _TAIL_LIMITS[name],
                count=read["bytes"], checksum=read["sha256"])
            require(raw == raws[name], "BEFORE_ELEVEN_ORIGINAL_READBACK")
            _before_same_read(read, second)
            readbacks.append(second)
        require(_tail_directory_names(metadata, root) == _before_roster(created=False) and
            _tail_directory_names(metadata, seal_directory) == ("seal-pending.json",), "BEFORE_FINAL_SEALED_ROOT")
        _collect_names(metadata, returned, (_EXPORT_STEP_FILE, _COLLECT_FILE))
        _before_actual(actual)
        N._check_history(graph)
        close = metadata.finish()
        closed_ns = clock.now()
        value = {"firstNs": clock.first, "firstLocal": clock.first_local, "closedNs": closed_ns,
            "closedLocal": clock._view().local_last, "files": [{"key": key, "relative": relative, "maximum": maximum,
                "first": first_read, "readback": second} for (key, relative, maximum), first_read, second in
                zip(_before_originals(), reads, readbacks)], "ownerClose": _collect_file_close(close)}
        raw = O.encoded(_before_input_data(value, clock.clock.role))
        result = _BeforeInput(originals, raw)
        _BEFORE_INPUTS[id(result)] = (result, result.__dict__, originals, raw, metadata, metadata._anchor(), pins,
            N._history_graph(result.__dict__, metadata.owner.__dict__, tuple(pin[2] for pin in pins)), actual)
        _checked_before_input(result)
        return result
    except BaseException as error:
        failure = metadata.remember(error)
    finally:
        if not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
    raise failure


def _before_predecessor(raws, step):
    return {"step": "initial-seal", "outcome": "success", "sealSha256": O.digest(raws["seal"]),
        "collectSha256": O.digest(raws["collect"]), "cryptoStepSha256": O.digest(raws["step"]),
        "cryptoCarrierSha256": O.digest(raws["carrier"]),
        "exporterReturnSha256": step["cryptoCarrier"]["exporterReturnSha256"]}


def _before_context(raw, clock):
    value = fields(canonical(raw), _BEFORE_CONTEXT_FIELDS, "BEFORE_CONTEXT_FIELDS")
    frame_clock, limits = _custody_authority_frame(value["originalWindow"])
    seal_sha, end, seed_clock, boot = C.seal_deadline_data(value["deadline"])
    _same(O.clock_value(frame_clock), O.clock_value(clock), "BEFORE_CONTEXT_ACTUAL_CLOCK")
    _same(O.clock_value(frame_clock), O.clock_value(seed_clock), "BEFORE_CONTEXT_SEED_CLOCK")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == B.CONTEXT_SCOPE and
        value["edge"] == "BEFORE" and value["kind"] == limits["kind"] and value["root"] == str(ROOT) and
        value["session"] == str(_paths(value["kind"])[2] / "authority-before") and
        value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False and
        value["originalWindow"]["originalBootDigest"] == boot and type(value["continuationEndNs"]) is int and
        value["continuationEndNs"] == limits["sealEndNs"] == end, "BEFORE_CONTEXT_SCOPE_OR_END")
    _collect_service_job(value["originalServiceJob"])
    predecessor = fields(value["predecessor"], "step outcome sealSha256 collectSha256 cryptoStepSha256 cryptoCarrierSha256 "
        "exporterReturnSha256", "BEFORE_CONTEXT_PREDECESSOR")
    require(predecessor["step"] == "initial-seal" and predecessor["outcome"] == "success" and
        predecessor["sealSha256"] == seal_sha, "BEFORE_CONTEXT_SEAL_OUTCOME")
    for name in ("sealSha256", "collectSha256", "cryptoStepSha256", "cryptoCarrierSha256", "exporterReturnSha256"):
        digest(predecessor[name])
    for name in ("eventSha256", "sourceReturnSha256"):
        digest(value[name])
    began = O.integer(value["parentFirstNs"], limits["startNs"])
    local_value(value["parentFirstLocal"])
    metadata = _before_input_data(value["inputMetadata"], clock.role)
    require(began == metadata["firstNs"] and type(value["parentFirstLocal"]) is type(metadata["firstLocal"]) and
        value["parentFirstLocal"] == metadata["firstLocal"] and
        metadata["closedNs"] <= O.integer(value["sourceReturnedNs"]) < end and
        type(value["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["job"]) and
        type(value["observed"]) is dict and value["observed"]["kind"] == value["kind"] and
        value["observed"]["role"] == clock.role, "BEFORE_CONTEXT_TIME_OR_HOST")
    hashes = {row["key"]: row["first"]["sha256"] for row in metadata["files"]}
    require(all(predecessor[name] == hashes[key] for name, key in (("sealSha256", "seal"), ("collectSha256", "collect"),
        ("cryptoStepSha256", "step"), ("cryptoCarrierSha256", "carrier"))) and value["eventSha256"] == hashes["event"],
        "BEFORE_CONTEXT_INPUT_HASHES")
    native.directory_identity(value["directoryIdentity"], clock.role)
    inherited = value["inheritedContext"]
    require(type(inherited) is dict and all(type(item) is str for item in inherited.values()) and
        (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "BEFORE_CONTEXT_PARENT_DOMAIN")
    expected = value["expectedMatch"]
    fields(expected, " ".join(E.COMMON_MATCH | ({"stage", "selector", "workerAdmission", "qualificationAcceptance"}
        if value["kind"] == "gate" else set())), "BEFORE_CONTEXT_EXPECTED_FIELDS")
    require(type(expected["firstUseAt"]) is int and expected["firstUseAt"] == value["observed"]["firstUseAt"] and
        expected["source"] == value["observed"]["source"] and O.digest(O.encoded(expected)) == hashes["original-match"],
        "BEFORE_CONTEXT_EXPECTED_LINK")
    selected = value["selectedInputs"]
    names = set(_before_selected(tuple(None for _name in _BEFORE_NAMES)))
    require(type(selected) is dict and set(selected) == names and all(type(item) is str for item in selected.values()),
        "BEFORE_CONTEXT_SELECTED_FIELDS")
    require(all(selected[name] == "success" for name in
        (PRIMARY_OUTCOME, _COLLECT_OUTCOME, _TAIL_OUTCOME, B.SEAL_OUTCOME_ENV)) and
        all(selected[environment] == value["deadline"][name] for name, environment, _flag in B.SEED_FIELDS),
        "BEFORE_CONTEXT_SELECTED_SUCCESS_OR_SEED")
    for name in (PRIMARY_RESULT, PRIMARY_HANDOFF, _COLLECT_STEP_HASH, _COLLECT_EXPORT_HASH, _TAIL_HASH, _TAIL_EXPORT_HASH):
        digest(selected[name])
    require(selected[_COLLECT_STEP_HASH] == hashes["step"] and selected[_TAIL_HASH] == hashes["collect"] and
        selected[_COLLECT_EXPORT_HASH] == selected[_TAIL_EXPORT_HASH] == predecessor["exporterReturnSha256"],
        "BEFORE_CONTEXT_SELECTED_HASHES")
    return value


def _before_child_host(context, event, first, boot):
    graph = N._history_graph(context, first)
    observed, _primary, actual_event = N.host_context(O.integer(context["observed"]["firstUseAt"], 1))
    _same(observed, context["observed"], "BEFORE_CHILD_ACTUAL_CONTEXT")
    require(type(event) is bytes and event == actual_event and O.digest(event) == context["eventSha256"] and
        context["originalWindow"]["originalBootDigest"] == boot and
        context["parentFirstNs"] <= first.nanoseconds < context["continuationEndNs"], "BEFORE_CHILD_ACTUAL_HOST")
    _same(context["originalWindow"]["clock"], O.clock_value(first.clock), "BEFORE_CHILD_ACTUAL_CLOCK")
    N._check_history(graph)
    return (A.gate.GateEligibility if context["kind"] == "gate" else A.stages.BootstrapMatch)(O.encoded(context["expectedMatch"]))


def _before_start_fields(raw, context_raw, context, clock):
    start = fields(canonical(raw), " ".join(native.START_FIELDS), "BEFORE_START_FIELDS")
    graph = N._history_graph(context, start)
    caps = B.phase_caps(context["deadline"], tuple(start[name] for name, _flag in B.PHASE_FIELDS))
    path = _paths(context["kind"])[2] / "authority-before"
    require(type(start["schema"]) is int and start["schema"] == 1 and start["scope"] == native.PHASE_SCOPE and
        start["contextSha256"] == O.digest(context_raw) and
        start["argv"] == native.phase_command(context_raw, before_caps=caps) and
        start["cwd"] == str(ROOT) and start["role"] == clock.role and start["job"] == context["job"] and
        start["state"] == str(path) and start["home"] == str(path / "control-home") and
        type(start["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", start["invocation"]) and
        start["exitCode"] is None and start["launchAttempted"] is False and start["scopeAttempted"] is False and
        start["retirement"] == "UNKNOWN" and caps[0] >= context["sourceReturnedNs"], "BEFORE_START")
    inherited = native.processes.ownership_environment(context["inheritedContext"], context["job"], start["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    _same(start["inheritedContext"], {name: inherited[name] for name in Q._CONTEXT}, "BEFORE_START_INHERITANCE")
    N._check_history(graph)
    return start


def _before_service_steps(captured, clock):
    """Read the retained actual response, not a new HTTP request or poll."""
    context_raw, originals, invocation, _began, _end = captured
    context, original = canonical(context_raw), dict(originals)
    github = context["observed"]["github"]
    path = A.API + "/actions/runs/" + github["runId"] + "/attempts/" + github["runAttempt"]
    _, attempt, _ = O.response_bytes(original["attempt"], path, invocation, clock)
    response, jobs, date = O.response_bytes(original["jobs"], path + "/jobs?per_page=100&page=1", invocation, clock)
    job = A._run(context["observed"], I.parse(attempt, O.wire.BODY_LIMIT), I.parse(jobs, O.wire.BODY_LIMIT), date)
    identity = [job["id"], job["started_at"], job["runner_name"], job["runner_id"]]
    _same(identity, context["originalServiceJob"], "BEFORE_FRESH_ORIGINAL_SERVICE_JOB")
    steps = B.step_rows(job, date)
    return {"originalServiceJob": identity, "jobsOriginalSha256": O.digest(original["jobs"]),
        "jobsBodySha256": O.digest(jobs), "serviceDateEpochSeconds": date,
        "jobsRequestStartedNs": O.integer(response["startedNs"]), "jobsRequestFinishedNs": O.integer(response["finishedNs"]),
        "steps": {role: row for role, row in steps}}


def _before_authority_child(context_hash, minimum, cancelled, seed, caps):
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    metadata = owner = clock = result_raw = None
    failure = None
    try:
        # Seed/caps are already decoded before this function. The FIRST pair
        # creates a genuine B child clock; no first+45 metadata bootstrap exists.
        local = local_value(time.monotonic())
        first = O.clocks.observe()
        first_graph = N._history_graph(first, seed, caps)
        O.clocks.validate_reading(first)
        require(first.nanoseconds >= O.integer(minimum) and native.processes.host_role() == first.clock.role,
            "BEFORE_CHILD_FIRST_OR_HOST")
        boot = digest(C.boot_digest(first.clock.role))
        N._check_history(first_graph)
        digest(context_hash)
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and
            not any(name in os.environ for name in _CREDENTIAL_NAMES) and callable(cancelled), "BEFORE_CHILD_TOKEN")
        clock = _BeforeClock(first, local, boot, cancelled, seed, side="child", inherited=caps)
        metadata = _PrimaryOwner(native.Owner(clock.local_end, clock, first=first, cancelled=cancelled))
        clock.attach_metadata(metadata)
        kind, _primary = N.location()
        path = _paths(kind)[2] / "authority-before"
        private = _private(metadata, path)
        private_pin = tuple(private.identity)
        context_raw, context_read = _before_read(metadata, private, "context.json", native.LIMIT)
        require(O.digest(context_raw) == context_hash, "BEFORE_CHILD_CONTEXT_HASH")
        clock.rebind_context(context_raw)
        service = _private(metadata, path / "service")
        service_pin = tuple(service.identity)
        start_raw, start_read = _before_read(metadata, service, "start.json", native.LIMIT)
        context = _before_context(context_raw, first.clock)
        _same(context["directoryIdentity"], list(private_pin), "BEFORE_CHILD_CONTEXT_PIN")
        _observed, _root, event = N.host_context(context["observed"]["firstUseAt"])
        inherited = Q._inherited_context()
        metadata_graph = N._history_graph(context, inherited, first, context_read, start_read)
        metadata_reads = []
        for directory, name, raw, read in ((private, "context.json", context_raw, context_read),
                (service, "start.json", start_raw, start_read)):
            same, reread = _before_read(metadata, directory, name, native.LIMIT, count=read["bytes"], checksum=read["sha256"])
            require(same == raw, "BEFORE_CHILD_METADATA_READBACK")
            _before_same_read(read, reread)
            metadata_reads.append({"name": name, "first": read, "readback": reread})
        metadata_close = metadata.finish()
        metadata_last = clock.now()
        N._check_history(metadata_graph)
        context, start, expected, domain = clock.bind_child(context_raw, start_raw, event, inherited, minimum)
        expected_pin = _custody_match_pin(expected, kind)
        owner = _CustodyOwner(clock.local_end, clock, first=first, cancelled=cancelled)
        clock.attach_operative(owner)
        private = owner.open(path)
        service = owner.child(private, "service")
        require(tuple(private.identity) == private_pin and tuple(service.identity) == service_pin and
            owner.read(private, "context.json") == context_raw and owner.read(service, "start.json") == start_raw,
            "BEFORE_CHILD_ORIGINAL_METADATA")
        supplier = None
        query_failure = None
        try:
            supplier = N.query_owner(owner, clock, path / "acquisition-queries")
            N._initial_service_query_git(supplier)
            supplier.native_host_matches_actions()
            def retain(name, raw, *, failed):
                require(name in N.ORIGINAL_KEYS and type(raw) is bytes and type(failed) is bool, "BEFORE_CHILD_ORIGINAL_NAME")
                owner.end(final=failed)
                supplier._write(supplier.private, name + ".bin", raw)
                owner.end(final=failed)
            match, originals = A.acquire_bootstrap(ROOT, kind=kind, query_runner=supplier, invocation=domain["id"],
                token=token, retain=retain, fence=clock, original_work_end=start["workEndNs"],
                first_use_at=context["observed"]["firstUseAt"], expected=expected)
            token = None
            match_pin = _custody_match_pin(match, kind)
            original_graph = N._history_graph(match.__dict__, originals)
            acquired = clock.now(limit=start["workEndNs"])
            _custody_match_check(match_pin)
            _custody_match_check(expected_pin)
            require(type(match) is type(expected) and match.record == expected.record and type(originals) is tuple and
                tuple(name for name, _raw in originals) == N.ORIGINAL_KEYS and all(type(raw) is bytes for _name, raw in originals) and
                dict(originals)["event"] == event, "BEFORE_CHILD_FRESH_MATCH")
        except BaseException as error:
            query_failure = error
        finally:
            token = None
            _custody_finish_queries(owner, supplier, query_failure)
        returned = clock.now(limit=start["workEndNs"])
        N._check_history(original_graph)
        _custody_match_check(match_pin)
        queries = owner.open(path / "acquisition-queries")
        session = N.query_session(owner, queries)
        require(all(owner.read(queries, name + ".bin") == raw for name, raw in originals), "BEFORE_CHILD_ORIGINAL_READBACK")
        _collect_query_index(path / "acquisition-queries", session, dict(originals), context["observed"])
        captured = (context_raw, originals, domain["id"], start["startedNs"], start["workEndNs"])
        steps = _before_service_steps(captured, first.clock)
        _custody_match_check(expected_pin)
        N._check_history(metadata_graph)
        result_raw = owner.write(service, "child-result.json", {"schema": 1, "scope": B.CHILD_SCOPE,
            "contextSha256": context_hash, "startSha256": O.digest(start_raw), "invocation": domain["id"],
            "clock": O.clock_value(first.clock), "bootDigest": boot, "launchMinimumNs": minimum,
            "phaseCaps": {name: value for (name, _flag), value in zip(B.PHASE_FIELDS, caps)},
            "deadlineSha256": O.digest(O.encoded(seed)), "beganNs": first.nanoseconds, "metadataLastNs": metadata_last,
            "acquiredNs": acquired, "queryReturnedNs": returned, "querySessionSha256": O.digest(session),
            "originalsSha256": {name: O.digest(raw) for name, raw in originals}, "matchSha256": O.digest(match.record),
            "directoryIdentities": {".": list(private_pin), "service": list(service_pin)}, "serviceSteps": steps,
            "metadataReads": metadata_reads, "metadataClose": _collect_file_close(metadata_close),
            "completedNs": clock.now(limit=start["workEndNs"]), "retirement": "PENDING_CHILD_CLOSE", "errors": []})
        N._check_history(original_graph)
        _custody_match_check(match_pin)
        clock.now()
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("before-authority-child", error)
            failure = owner._anchor().failure
        elif metadata is not None:
            failure = metadata.remember(error)
    finally:
        token = None
        if metadata is not None and not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
        if owner is not None:
            if failure is None and owner._anchor().failure is None:
                try:
                    owner.freeze()
                except BaseException as error:
                    owner.error("before-child-close-roster", error, unknown=True)
            try:
                owner.close()
            except BaseException as error:
                owner.error("before-child-close", error)
            if failure is None and owner._anchor().failure is not None:
                failure = owner._anchor().failure
    if failure is not None:
        raise failure
    require(owner is not None and clock is not None and result_raw is not None, "BEFORE_CHILD_INCOMPLETE")
    anchor = owner.known()
    N._check_history(metadata_graph)
    N._check_history(original_graph)
    _custody_match_check(expected_pin)
    _custody_match_check(match_pin)
    closed = clock.now(limit=start["workEndNs"])
    owner.known()
    owner_close = {"schema": 1, "scope": "INITIAL_BEFORE_AUTHORITY_CHILD_KNOWN_CLOSE_V1",
        "resources": [{"ordinal": index, "label": label, "closeAttempted": attempted, "closed": ended}
            for index, (_row, label, _resource, attempted, ended) in enumerate(anchor.rows)],
        "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}
    return {"schema": 1, "scope": B.ACK_SCOPE, "invocation": domain["id"], "terminalSha256": O.digest(result_raw),
        "clock": O.clock_value(first.clock), "closedNs": closed, "ownerClose": owner_close}, clock, start["workEndNs"]


def _before_phase_bytes(context_raw, phase, child_raw, clock, private_pin, service_pin):
    """B-only phase DATA checker. Genuine phase/owner returns are checked too."""
    require(type(phase) is native.OriginalPhase and phase.context == context_raw and type(phase.records) is tuple,
        "BEFORE_PHASE_TYPE")
    context = _before_context(context_raw, clock)
    records = dict(phase.records)
    require(len(phase.records) == len(records) and set(records) == native.PHASE_FILES and
        all(type(raw) is bytes for raw in records.values()), "BEFORE_PHASE_FILES")
    start = _before_start_fields(records["start.json"], context_raw, context, clock)
    caps = tuple(start[name] for name, _flag in B.PHASE_FIELDS)
    row = fields(canonical(records["result.json"]), " ".join(native.TERMINAL_FIELDS), "BEFORE_TERMINAL_FIELDS")
    birth = fields(canonical(records["native-start.json"]), "ownership leader preparerIdentity observedNs", "BEFORE_BIRTH_FIELDS")
    changed = {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}
    _same({name: row[name] for name in start if name not in changed},
        {name: start[name] for name in start if name not in changed}, "BEFORE_TERMINAL_START")
    require(type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is True and
        row["scopeAttempted"] is True and row["scopeCloseAttempted"] is True and row["scopeClosed"] is True and
        row["retirement"] == "KNOWN" and row["survivors"] == [] and row["errors"] == [] and records["stderr.log"] == b"" and
        row["nativeStartSha256"] == O.digest(records["native-start.json"]) and
        row["baselineSha256"] == O.digest(records["baseline.json"]) and row["leader"] == birth["leader"], "BEFORE_NATIVE_RETURN")
    argv = native.phase_command(context_raw, O.integer(row["launchMinimumNs"], start["startedNs"]), before_caps=caps)
    _same(row["launchArgv"], argv, "BEFORE_NATIVE_COMMAND")
    native.native_record(row["ownership"], start, row["leader"], argv)
    native.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    _same(birth["ownership"]["launches"], row["ownership"]["launches"], "BEFORE_NATIVE_BIRTH")
    preparer = native.closed_lifetime(row["preparerIdentity"], clock.role)
    _same(preparer, native.closed_lifetime(birth["preparerIdentity"], clock.role), "BEFORE_NATIVE_PREPARER")
    require(preparer["pid"] != row["leader"]["pid"], "BEFORE_NATIVE_PREPARER_LEADER_ALIAS")
    baseline = native.baseline_record(records["baseline.json"], clock.role)
    if baseline["baseline"] is not None:
        leader = native.lifetime(row["leader"], clock.role)
        require(list(leader[:4] if clock.role.startswith("macos-") else leader) not in baseline["baseline"],
            "BEFORE_PREEXISTING_LEADER")
    _same(row["captureOutcomes"], {name: {key: True for key in
        ("synced", "verified", "closeAttempted", "closed", "readback")} for name in ("stdout", "stderr")}, "BEFORE_CAPTURE_CLOSE")
    _same(row["captures"], {name: {"sha256": O.digest(records[name + ".log"]), "bytes": len(records[name + ".log"])}
        for name in ("stdout", "stderr")}, "BEFORE_CAPTURE_BYTES")
    child = fields(canonical(child_raw), "schema scope contextSha256 startSha256 invocation clock bootDigest launchMinimumNs "
        "phaseCaps deadlineSha256 beganNs metadataLastNs acquiredNs queryReturnedNs querySessionSha256 originalsSha256 "
        "matchSha256 directoryIdentities serviceSteps metadataReads metadataClose completedNs retirement errors", "BEFORE_CHILD_FIELDS")
    ack = fields(canonical(records["stdout.log"]), "schema scope invocation terminalSha256 clock closedNs ownerClose", "BEFORE_ACK_FIELDS")
    require(type(child["schema"]) is int and child["schema"] == 1 and child["scope"] == B.CHILD_SCOPE and
        child["contextSha256"] == O.digest(context_raw) and child["startSha256"] == O.digest(records["start.json"]) and
        child["invocation"] == start["invocation"] and
        child["bootDigest"] == context["originalWindow"]["originalBootDigest"] and
        child["deadlineSha256"] == O.digest(O.encoded(context["deadline"])) and
        type(child["launchMinimumNs"]) is int and child["launchMinimumNs"] == row["launchMinimumNs"] and
        child["retirement"] == "PENDING_CHILD_CLOSE" and child["errors"] == [] and
        type(ack["schema"]) is int and ack["schema"] == 1 and ack["scope"] == B.ACK_SCOPE and
        ack["invocation"] == start["invocation"] and ack["terminalSha256"] == O.digest(child_raw), "BEFORE_CHILD_ACK")
    _same(child["clock"], O.clock_value(clock), "BEFORE_CHILD_CLOCK")
    _same(ack["clock"], O.clock_value(clock), "BEFORE_ACK_CLOCK")
    _same(child["phaseCaps"], {name: value for (name, _flag), value in zip(B.PHASE_FIELDS, caps)}, "BEFORE_CHILD_CAPS")
    _same(child["directoryIdentities"], {".": list(private_pin), "service": list(service_pin)}, "BEFORE_CHILD_PINS")
    metadata = _collect_file_close(O.encoded(child["metadataClose"]))
    _same(metadata["resources"], [{"ordinal": index, "label": label, "closeAttempted": True, "closed": True}
        for index, label in enumerate(("directory", "reader", "directory", "reader", "reader", "reader"))],
        "BEFORE_CHILD_METADATA_ROSTER")
    require(type(child["metadataReads"]) is list and len(child["metadataReads"]) == 2, "BEFORE_CHILD_METADATA_READS")
    for value, name, raw, initial, reread in zip(child["metadataReads"], ("context.json", "start.json"),
            (context_raw, records["start.json"]), (1, 3), (4, 5)):
        fields(value, "name first readback", "BEFORE_CHILD_METADATA_FIELDS")
        require(value["name"] == name, "BEFORE_CHILD_METADATA_NAME")
        for read, ordinal in ((value["first"], initial), (value["readback"], reread)):
            fields(read, "bytes sha256 metadata readerOrdinal retirement", "BEFORE_CHILD_READ_FIELDS")
            require(type(read["bytes"]) is int and read["bytes"] == len(raw) and read["sha256"] == O.digest(raw) and
                type(read["readerOrdinal"]) is int and read["readerOrdinal"] == ordinal and
                read["retirement"] == "KNOWN_READER_CLOSE", "BEFORE_CHILD_METADATA_BINDING")
            _before_metadata(read["metadata"], clock.role, len(raw))
        _before_same_read(value["first"], value["readback"])
    close = fields(ack["ownerClose"], "schema scope resources retirement exportSaveAuthority", "BEFORE_CHILD_CLOSE_FIELDS")
    require(type(close["schema"]) is int and close["schema"] == 1 and
        close["scope"] == "INITIAL_BEFORE_AUTHORITY_CHILD_KNOWN_CLOSE_V1" and
        close["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and close["exportSaveAuthority"] is False, "BEFORE_CHILD_CLOSE")
    _collect_close_rows(close["resources"], {"directory", "writer"})
    fields(child["originalsSha256"], " ".join(N.ORIGINAL_KEYS), "BEFORE_CHILD_ORIGINAL_HASHES")
    for checksum in (child["querySessionSha256"], child["matchSha256"], *child["originalsSha256"].values()):
        digest(checksum)
    ordered = [row["launchMinimumNs"], *(child[name] for name in
        ("beganNs", "metadataLastNs", "acquiredNs", "queryReturnedNs", "completedNs")), ack["closedNs"], row["completedNs"], row["finalizedNs"]]
    require(all(type(value) is int and O.integer(value) == value for value in ordered) and ordered == sorted(ordered) and
        start["startedNs"] <= ordered[0] and ack["closedNs"] < start["workEndNs"] and row["completedNs"] < start["workEndNs"] and
        row["finalizedNs"] < start["finalEndNs"] and row["launchMinimumNs"] <= O.integer(birth["observedNs"]) <= row["completedNs"],
        "BEFORE_ORIGINAL_PHASE_CHRONOLOGY")
    return start, row, birth, child, ack


def _before_read_authority(owner, private, before, phase, clock, inputs, expected):
    before_pin, phase_pin, expected_pin = _collect_source_pin(before), _collect_phase_pin(phase), \
        _custody_match_pin(expected, clock.frame["kind"])
    raws, input_metadata, _metadata = _checked_before_input(inputs)
    prior = {name: raws[name] for name in _TAIL_LIMITS}
    step, _carrier, old_context, _manifest, _collected = _tail_bundle(prior)
    context_raw = phase.context
    context = _before_context(context_raw, clock.clock)
    graph = N._history_graph(context, raws, input_metadata)
    require(type(owner) is _CustodyOwner and owner.fence is clock and owner.phase_originals is phase and
        owner.read(private, "context.json") == context_raw, "BEFORE_CURRENT_OWNER_OR_CONTEXT")
    for name, expected_value in (("originalWindow", clock.frame), ("originalServiceJob", step["originalServiceJob"]),
            ("observed", old_context["observed"]), ("predecessor", _before_predecessor(raws, step)),
            ("inputMetadata", input_metadata), ("deadline", clock.seed),
            ("selectedInputs", _before_selected(_BEFORE_INPUTS[id(inputs)][-1])),
            ("directoryIdentity", list(private.identity))):
        _same(context[name], expected_value, "BEFORE_CURRENT_CONTEXT_BINDING")
    require(O.encoded(context["expectedMatch"]) == expected.record == raws["original-match"], "BEFORE_CURRENT_EXPECTED")
    policy = N.source_readback(owner, private.path / "source-before", before)
    require(context["sourceReturnSha256"] == O.digest(before.raw) and
        context["sourceReturnedNs"] == canonical(before.raw)["returnedNs"], "BEFORE_CURRENT_SOURCE_RETURN")
    _collect_query_index(private.path / "source-before", before.session, dict(before.records), context["observed"], source=before)
    service = owner.child(private, "service")
    for name, raw in phase.records:
        maximum = native.ACK_LIMIT if name == "stdout.log" else native.STDERR_LIMIT if name == "stderr.log" else native.LIMIT
        require(owner.read(service, name, maximum) == raw, "BEFORE_CURRENT_PHASE_BYTES")
    child_raw = owner.read(service, "child-result.json")
    start, row, birth, child, ack = _before_phase_bytes(context_raw, phase, child_raw, clock.clock,
        tuple(private.identity), tuple(service.identity))
    queries = owner.open(private.path / "acquisition-queries")
    session = N.query_session(owner, queries)
    originals = tuple((name, owner.read(queries, name + ".bin")) for name in N.ORIGINAL_KEYS)
    original = dict(originals)
    captured = (context_raw, originals, start["invocation"], start["startedNs"], start["workEndNs"])
    captured_graph = N._history_graph(captured)
    require(child["querySessionSha256"] == O.digest(session) and child["originalsSha256"] ==
        {name: O.digest(raw) for name, raw in originals} and child["matchSha256"] == O.digest(original["match"]) and
        original["event"] == raws["event"] and {name: original[name] for name in N.SOURCE_KEYS} == policy and
        original["candidate_policy_raw"] == raws["policy"] and original["match"] == expected.record,
        "BEFORE_CURRENT_ORIGINALS")
    _collect_query_index(private.path / "acquisition-queries", session, original, context["observed"])
    match, service_time = N.retained_match(context, original, start["invocation"], clock.clock,
        start["startedNs"], start["workEndNs"])
    match_pin = _custody_match_pin(match, context["kind"])
    steps = _before_service_steps(captured, clock.clock)
    _same(child["serviceSteps"], steps, "BEFORE_CHILD_FRESH_SERVICE_STEPS")
    match_graph = N._history_graph(match.__dict__, service_time, steps)
    require(type(match) is type(expected) and match.record == expected.record, "BEFORE_CURRENT_MATCH")
    minimum = N._service_chain_minimum(clock.first, context["sourceReturnedNs"], start, row, birth, child, service_time, ack)
    checked = clock.now(minimum=minimum)
    _collect_source_current(before_pin)
    _collect_phase_current(phase_pin)
    _custody_match_check(expected_pin)
    _custody_match_check(match_pin)
    for saved in (graph, captured_graph, match_graph):
        N._check_history(saved)
    owner.check()
    require(owner.phase_originals is phase, "BEFORE_CURRENT_PHASE_OWNER")
    authority = {"contextSha256": O.digest(context_raw), "sourceBeforeSha256": O.digest(before.raw),
        "expectedMatchSha256": O.digest(expected.record), "freshMatchSha256": O.digest(match.record),
        "originalsSha256": {name: O.digest(raw) for name, raw in originals}, "querySessionSha256": O.digest(session),
        "phaseSha256": {name: O.digest(raw) for name, raw in phase.records}, "childSha256": O.digest(child_raw),
        "ackSha256": O.digest(dict(phase.records)["stdout.log"]), "invocation": start["invocation"],
        "startedNs": start["startedNs"], "workEndNs": start["workEndNs"], "finalEndNs": start["finalEndNs"],
        "acquiredNs": child["acquiredNs"], "checkedNs": checked, "serviceSteps": steps}
    return match, captured, authority, child_raw, session


@dataclass(frozen=True, repr=False)
class _BeforeAcquired:
    """Private still-owned acquisition return. Not closed authority/K input."""
    input: object
    clock: object
    owner: object
    root: object
    private: object
    before: object
    after: object
    phase: object
    captured: tuple
    match: object
    summary: dict


_BEFORE_ACQUIRED = {}


def _before_acquire(inputs, clock, expected, token, entry):
    """Token-bearing acquisition ONLY; exhaustive copy/close runs after return."""
    attempt = owner = None
    failure = None
    source_links, source_pins, graphs, match_pins, directory_bindings = (), (), (), (), ()
    phase = phase_pin = None
    try:
        # Even an already-consumed attempt can raise. Keep that first check
        # inside the token-clearing finally, not in a retained exception frame.
        attempt = _before_begin("authority")
        _before_entry_current(entry)
        attempt.update(input=inputs, clock=clock, owner=None, entry=entry)
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and
            not any(name in os.environ for name in _CREDENTIAL_NAMES) and type(clock) is _BeforeClock and
            clock.side == "parent" and clock._view().binding[9] is entry, "BEFORE_ACQUISITION_TOKEN_OR_CLOCK")
        raws, input_metadata, _metadata = _checked_before_input(inputs)
        parsed = _tail_bundle({name: raws[name] for name in _TAIL_LIMITS})
        step, _carrier, old_context, _manifest, _collected = parsed
        match_pins = (_custody_match_pin(expected, step["kind"]),)
        graphs = (N._history_graph(raws, parsed, input_metadata),)
        require(expected.record == raws["original-match"], "BEFORE_ACQUISITION_EXPECTED")
        _same(clock.frame, step["originalWindow"], "BEFORE_ACQUISITION_WINDOW")
        owner = _CustodyOwner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled)
        attempt["owner"] = owner
        clock.attach_operative(owner)
        anchor, dictionary = owner._anchor(), owner.__dict__
        def current():
            # This closure deliberately never captures token, retain or a
            # credential-bearing acquisition frame. It survives for K custody.
            _before_entry_current(entry)
            require(_BEFORE_ATTEMPTS.get("authority") is attempt and attempt["input"] is inputs and
                attempt["clock"] is clock and attempt["owner"] is owner and attempt["state"] in
                ("STARTED", "ACQUIRED", "CLOSING", "RETURNED") and attempt["failure"] is None and
                attempt["entry"] is entry and owner.__dict__ is dictionary and owner._anchor() is anchor,
                "BEFORE_ORIGINAL_ACQUISITION")
            _checked_before_input(inputs)
            owner.check()
            require(owner.original is None and not owner.unknown and owner.errors == [] and
                set(owner.initial_sources) == {name for name, _source in source_links} and
                all(owner.initial_sources[name] is source for name, source in source_links) and owner.phase_originals is phase,
                "BEFORE_ORIGINAL_AUTHORITY_OWNER")
            for directory, path, identity in directory_bindings:
                require(directory.path is path and tuple(directory.identity) == identity and
                    _collect_directory_closed(directory, clock.clock.role) is owner.closed,
                    "BEFORE_ORIGINAL_DIRECTORY_BINDING")
            for pin in source_pins:
                _collect_source_current(pin)
            if phase_pin is not None:
                _collect_phase_current(phase_pin)
            for pin in match_pins:
                _custody_match_check(pin)
            for graph in graphs:
                N._check_history(graph)
            _before_entry_current(entry)
        current()
        custody = _paths(step["kind"])[2]
        root = owner.open(custody)
        original_root = _BEFORE_INPUTS[id(inputs)][6][1]
        require(root.path == original_root[2] and tuple(root.identity) == original_root[3] and
            native._initializer_names(owner, root) == _before_roster(created=False), "BEFORE_ACQUISITION_SEALED_ROOT")
        path = custody / "authority-before"
        private = owner.child(root, "authority-before", create=True)
        private_pin = tuple(private.identity)
        directory_bindings = tuple((directory, directory.path, tuple(directory.identity)) for directory in (root, private))
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        before = N.source_queries(owner, clock, old_context["observed"], path / "source-before")
        source_links = ((str(path / "source-before"), before),)
        source_pins = (_collect_source_pin(before),)
        current()
        policy = N.source_readback(owner, path / "source-before", before)
        require(policy["candidate_policy_raw"] == raws["policy"], "BEFORE_SOURCE_POLICY_CHANGED")
        _collect_query_index(path / "source-before", before.session, policy, old_context["observed"], source=before)
        inherited = Q._inherited_context()
        context = {"schema": 1, "scope": B.CONTEXT_SCOPE, "edge": "BEFORE", "kind": step["kind"],
            "root": str(ROOT), "session": str(path), "job": uuid.uuid4().hex, "observed": old_context["observed"],
            "originalWindow": step["originalWindow"], "originalServiceJob": step["originalServiceJob"],
            "predecessor": _before_predecessor(raws, step), "expectedMatch": canonical(expected.record, A.stages.LIMIT),
            "eventSha256": O.digest(raws["event"]), "sourceReturnSha256": O.digest(before.raw),
            "sourceReturnedNs": canonical(before.raw)["returnedNs"], "inheritedContext": inherited,
            "directoryIdentity": list(private_pin), "parentFirstNs": clock.first, "parentFirstLocal": clock.first_local,
            "continuationEndNs": clock.work, "deadline": clock.seed,
            "selectedInputs": _before_selected(_BEFORE_INPUTS[id(inputs)][-1]), "inputMetadata": input_metadata,
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        graphs = (*graphs, N._history_graph(context, inherited))
        context_raw = O.encoded(context)
        _before_context(context_raw, clock.clock)
        current()
        require(owner.write(private, "context.json", context_raw) == context_raw, "BEFORE_CONTEXT_WRITE")
        _directory, returned_phase = N._initial_service_phase(owner, private, context_raw, token, clock, before)
        phase = returned_phase
        phase_pin = _collect_phase_pin(phase)
        token = None
        current()
        first_match, first_captured, _chain, _child, _session = _before_read_authority(
            owner, private, before, phase, clock, inputs, expected)
        match_pins = (*match_pins, _custody_match_pin(first_match, step["kind"]))
        graphs = (*graphs, N._history_graph(first_captured))
        current()
        after = N.source_queries(owner, clock, old_context["observed"], path / "source-after")
        source_links = (*source_links, (str(path / "source-after"), after))
        source_pins = (*source_pins, _collect_source_pin(after))
        current()
        require(N.source_readback(owner, path / "source-after", after) == policy, "BEFORE_FINAL_SOURCE_CHANGED")
        _collect_query_index(path / "source-after", after.session, dict(after.records), old_context["observed"], source=after)
        match, captured, authority, child_raw, session_raw = _before_read_authority(
            owner, private, before, phase, clock, inputs, expected)
        match_pins = (*match_pins, _custody_match_pin(match, step["kind"]))
        require(captured == first_captured and tuple(private.identity) == private_pin and
            native._initializer_names(owner, root) == _before_roster(created=True), "BEFORE_ACQUISITION_STABLE")
        authority["sourceAfterSha256"] = O.digest(after.raw)
        graphs = (*graphs, N._history_graph(captured, authority))
        current()
        clock.now()
        result = _BeforeAcquired(inputs, clock, owner, root, private, before, after, phase, captured, match, authority)
        _BEFORE_ACQUIRED[id(result)] = (result, result.__dict__, current,
            N._history_graph(result.__dict__, root.path, private.path), attempt, child_raw, session_raw, context_raw,
            owner, anchor, clock, entry)
        attempt["state"] = "ACQUIRED"
        _checked_before_acquired(result)
        return result
    except BaseException as error:
        failure = error
        if owner is not None:
            owner.error("before-acquisition-parent", error)
            failure = owner._anchor().failure
        failure = entry[0].fail(failure)
        if attempt is not None:
            if attempt["failure"] is None:
                attempt["failure"] = failure
            attempt["state"] = "FAILED"
    finally:
        token = None
        if failure is not None and owner is not None:
            try:
                owner.close()
            except BaseException as error:
                owner.error("before-acquisition-failed-close", error)
    raise failure if attempt is None else attempt["failure"]


def _checked_before_acquired(result):
    saved = _BEFORE_ACQUIRED.get(id(result))
    require(type(result) is _BeforeAcquired and type(saved) is tuple and saved[0] is result,
        "BEFORE_NOT_ORIGINAL_ACQUISITION")
    try:
        _before_entry_current(saved[11])
        require(saved[4]["failure"] is None and result.__dict__ is saved[1] and result.owner is saved[8] and
            result.owner._anchor() is saved[9] and result.clock is saved[10], "BEFORE_ACQUISITION_DICTIONARY_CHANGED")
        N._check_history(saved[3])
        saved[2]()
        clock_anchor = result.clock._view()
        require(clock_anchor.binding[9] is saved[11] and clock_anchor.failure is None and
            not any(name in os.environ for name in _CREDENTIAL_NAMES),
            "BEFORE_ACQUISITION_FAILED_OR_CREDENTIAL")
        _before_entry_current(saved[11])
        return saved
    except BaseException as error:
        error = saved[11][0].fail(error)
        if saved[4]["failure"] is None:
            saved[4]["failure"] = error
        saved[4]["state"] = "FAILED"
        raise saved[4]["failure"]


def _before_currency(result):
    saved = _checked_before_acquired(result)
    try:
        _before_entry_current(saved[11])
        raws, _input_metadata, _metadata = _checked_before_input(result.input)
        prior = {name: raws[name] for name in _TAIL_LIMITS}
        expected = _tail_host(prior, _tail_bundle(prior), result.clock.clock)
        expected_pin = _custody_match_pin(expected, result.clock.frame["kind"])
        context_raw, originals, invocation, began, end = result.captured
        match, _service = N.retained_match(canonical(context_raw), dict(originals), invocation, result.clock.clock, began, end)
        match_pin = _custody_match_pin(match, result.clock.frame["kind"])
        require(type(match) is type(expected) is type(result.match) and match.record == expected.record == result.match.record,
            "BEFORE_CURRENT_GRANT_CHANGED")
        _same(_before_service_steps(result.captured, result.clock.clock), result.summary["serviceSteps"],
            "BEFORE_CURRENT_SERVICE_STEPS_CHANGED")
        result.clock.now()
        _custody_match_check(expected_pin)
        _custody_match_check(match_pin)
        require(_checked_before_acquired(result) is saved, "BEFORE_CURRENT_ACQUISITION_REPLACED")
        return saved
    except BaseException as error:
        raise saved[11][0].fail(error)


def _before_index(result):
    """Compare the actual producer declarations to the independent fixed grammar."""
    saved = _checked_before_acquired(result)
    child_raw, session_raw, context_raw = saved[5:8]
    context, path = _before_context(context_raw, result.clock.clock), result.private.path
    require(N.SOURCE_KEYS == B.SOURCE_KEYS and N.ORIGINAL_KEYS == B.ORIGINAL_KEYS and
        native.PHASE_FILES == set(B.PHASE_FILES), "BEFORE_PRODUCER_GRAMMAR_CHANGED")
    groups = (("source-before", result.before, result.before.session, dict(result.before.records)),
        ("acquisition-queries", None, session_raw, dict(result.captured[1])),
        ("source-after", result.after, result.after.session, dict(result.after.records)))
    rows, directories, identifiers = [], [path, path / "control-home", path / "temporary", path / "service"], []
    for side, source, session, originals in groups:
        new_rows, new_directories = _collect_query_index(path / side, session, originals, context["observed"], source=source)
        rows.extend(new_rows)
        directories.extend(new_directories)
        identifiers.append(tuple(row["id"] for row in canonical(session, Q.MAX_RECEIPT_BYTES)["queries"]))
    required_files, required_directories = B.member_grammar(*identifiers)
    for name, raw in (("context.json", context_raw), ("service/child-result.json", child_raw),
            *(("service/" + name, raw) for name, raw in result.phase.records)):
        maximum = native.ACK_LIMIT if name == "service/stdout.log" else \
            native.STDERR_LIMIT if name == "service/stderr.log" else native.LIMIT
        require(type(raw) is bytes and len(raw) <= maximum, "BEFORE_PHASE_ORIGINAL_LIMIT")
        rows.append((path / name, maximum, len(raw), O.digest(raw)))
    index = tuple(sorted((str(target.relative_to(path)).replace(os.sep, "/"), maximum, count, checksum)
        for target, maximum, count, checksum in rows))
    relative_directories = tuple(sorted(str(target.relative_to(path)).replace(os.sep, "/") for target in directories))
    require(len(index) == 279 and tuple(row[0] for row in index) == tuple(name for name in required_files if name != "authority-close.json") and
        relative_directories == required_directories and all(type(maximum) is int and type(count) is int and
            0 <= count <= maximum <= native.LIMIT for _name, maximum, count, _checksum in index),
        "BEFORE_EXHAUSTIVE_PRODUCER_ROSTER")
    require(sum(row[2] for row in index) <= MAX_BYTES, "BEFORE_ORIGINAL_TOTAL_LIMIT")
    return index, required_files, required_directories


def _before_directory_members(metadata, directory, expected):
    """B-only exact cardinality cap. Old32-entry roster helpers are unchanged."""
    require(type(metadata) is _PrimaryOwner and type(expected) is tuple and len(expected) <= 42 and
        len(set(expected)) == len(expected), "BEFORE_DIRECTORY_EXPECTATION")
    end = metadata.guard()
    directory.verify()
    maximum = max(1, len(expected))
    if metadata.owner.first.clock.role == "windows-x64":
        names = directory.names(max_names=maximum, deadline=end)
    else:
        names = []
        with os.scandir(directory.path) as entries:
            for entry in entries:
                require(len(names) < maximum, "BEFORE_DIRECTORY_LIMIT")
                names.append(entry.name)
    require(len(names) == len(set(names)) == len(set(name.casefold() for name in names)) and
        tuple(sorted(names)) == expected, "BEFORE_DIRECTORY_MEMBERSHIP")
    directory.verify()
    metadata.guard()


def _before_query_files(result, originals):
    """Bind each actual query's five copied originals to its actual session."""
    saved = _checked_before_acquired(result)
    context = canonical(saved[7])
    for side, session_raw in (("source-before", result.before.session), ("source-after", result.after.session),
            ("acquisition-queries", saved[6])):
        session = canonical(session_raw, Q.MAX_RECEIPT_BYTES)
        owner = fields(canonical(originals[side + "/owner.json"]),
            "schema scope job state home root nativeRole git ancestorContext", "BEFORE_QUERY_OWNER_FIELDS")
        path = result.private.path / side
        require(type(owner["schema"]) is int and owner["schema"] == 1 and owner["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
            owner["job"] == session["job"] and owner["state"] == str(path) and owner["home"] == str(path / "query-home") and
            owner["root"] == str(ROOT) and owner["nativeRole"] == result.clock.clock.role and
            owner["git"] == session["queries"][0]["argv"][0], "BEFORE_ORIGINAL_QUERY_OWNER")
        inherited = (canonical(dict(result.phase.records)["start.json"])["inheritedContext"] if side == "acquisition-queries"
            else context["inheritedContext"])
        _same(owner["ancestorContext"], inherited, "BEFORE_QUERY_ORIGINAL_ANCESTORS")
        for query in session["queries"]:
            prefix = side + "/query-" + query["id"] + "/"
            require(originals[prefix + "result.json"] == Q.encoded(query), "BEFORE_QUERY_RESULT_ORIGINAL")
            start = canonical(originals[prefix + "start.json"])
            expected = {name: value for name, value in query.items() if name not in ("ownership", "ownedSurvivors")}
            expected.update(launchAttempted=False, scopeAttempted=False, waitExitCode=None, retirement="UNKNOWN",
                result="HOLD", errors=[], outputs={})
            require(set(start) == set(expected) | {"environment"}, "BEFORE_QUERY_START_FIELDS")
            _same({name: start[name] for name in expected}, expected, "BEFORE_QUERY_START_ORIGINAL")
            require(type(start["environment"]) is dict and all(type(key) is str and type(value) is str
                for key, value in start["environment"].items()) and
                not any(name in start["environment"] for name in _CREDENTIAL_NAMES), "BEFORE_QUERY_START_CREDENTIALS")
            baseline = fields(canonical(originals[prefix + "baseline.json"]), "nativeRole baseline kernelJob",
                "BEFORE_QUERY_BASELINE_FIELDS")
            require(baseline["nativeRole"] == result.clock.clock.role and
                baseline["kernelJob"] is (result.clock.clock.role == "windows-x64") and
                (baseline["baseline"] is None if baseline["kernelJob"] else type(baseline["baseline"]) is list),
                "BEFORE_QUERY_BASELINE")
            for stream in ("stdout", "stderr"):
                raw = originals[prefix + stream + ".log"]
                value = query["outputs"][stream]
                require(type(value["bytes"]) is int and value["bytes"] == len(raw) and value["sha256"] == O.digest(raw),
                    "BEFORE_QUERY_STREAM_ORIGINAL")


def _before_capture(result, index, required, directories, original_pins):
    """Read ALL279 actual files and ALL58 exact directories. Not K capture."""
    clock, path = result.clock, result.private.path
    metadata = _PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
    failure = None
    try:
        clock.attach_file_owner("readback", metadata)
        _before_currency(result)
        native_pins = {key: identity for key, _row, _directory, _path, identity in original_pins}
        require(set(native_pins) == set(B.DIRECTORY_TARGETS), "BEFORE_SEVEN_ORIGINAL_TARGETS")
        members = dict(B.directory_members(required, directories, closed=False))
        handles, pins = {}, []
        for relative in sorted(directories, key=lambda name: (name.count("/"), name != ".", name)):
            target = path if relative == "." else path.joinpath(*relative.split("/"))
            directory = _private(metadata, target)
            pin = tuple(directory.identity)
            require(not any(pin == previous[3] for previous in pins) and
                (relative not in native_pins or pin == native_pins[relative]), "BEFORE_DIRECTORY_ORIGINAL_PIN_OR_ALIAS")
            _before_directory_members(metadata, directory, members[relative])
            handles[relative] = directory
            pins.append((relative, directory, directory.path, pin))
        originals, observed, identities, total = [], [], set(pin[3] for pin in pins), 0
        for relative, maximum, count, checksum in index:
            parent, _, name = relative.rpartition("/")
            raw, observation = _before_read(metadata, handles[parent or "."], name, maximum, count=count, checksum=checksum)
            pin = _before_metadata(observation["metadata"], clock.clock.role, count)
            require(pin not in identities, "BEFORE_FILE_OR_DIRECTORY_ALIAS")
            identities.add(pin)
            total += len(raw)
            require(total <= MAX_BYTES, "BEFORE_ACTUAL_TOTAL_LIMIT")
            originals.append((relative, raw))
            observed.append({"relative": relative, "maximum": maximum, **observation})
        originals = tuple(originals)
        require(len(originals) == 279 and tuple(name for name, _raw in originals) == tuple(row[0] for row in index),
            "BEFORE_ALL279_READ_REQUIRED")
        _before_query_files(result, dict(originals))
        graph = N._history_graph(originals, observed, tuple(pin[2] for pin in pins))
        for relative, directory in handles.items():
            _before_directory_members(metadata, directory, members[relative])
        _before_currency(result)
        N._check_worker_pins(original_pins, clock.clock.role)
        N._check_history(graph)
        close = metadata.finish()
        closed_ns = clock.now()
        data = {"files": observed, "directories": [{"relative": relative, "path": str(target),
            "originalIdentity": list(native_pins[relative]) if relative in native_pins else None,
            "originalProvenance": "ORIGINAL_AUTHORITY_NATIVE_PIN" if relative in native_pins else "UNPINNED_ORIGINAL_DIRECTORY",
            "readbackIdentity": list(identity)} for relative, _directory, target, identity in sorted(pins)],
            "fileCount": 279, "directoryCount": 58, "totalBytes": total, "closedNs": closed_ns,
            "ownerClose": _collect_file_close(close), "captureScope": "BEFORE_ORIGINAL_READBACK_NOT_K_CAPTURE"}
        raw = O.encoded(data)
        canonical(raw)
        return originals, raw, metadata, tuple(pins)
    except BaseException as error:
        failure = metadata.remember(error)
    finally:
        if not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
    raise failure


def _before_file_owner_known(owner, anchor, pins):
    require(type(owner) is _PrimaryOwner and owner._anchor() is anchor, "BEFORE_CLOSED_FILE_OWNER_CHANGED")
    owner.structural()
    require(owner.finished and owner.failure is None and owner.owner.closed is True and owner.owner.unknown is False and
        owner.owner.original is None and owner.errors == [] and all(a and c for _r, _l, _v, a, c in owner.rows),
        "BEFORE_FILE_CLOSE_NOT_KNOWN")
    for _name, directory, path, identity in pins:
        require(directory.path is path and tuple(directory.identity) == identity and
            _collect_directory_closed(directory, owner.owner.first.clock.role) is True, "BEFORE_CLOSED_DIRECTORY_CHANGED")


def _before_pending_close(result, readback_raw, required, parent_close, preclose, closed):
    """No self hash/byte total or enclosing writer/Step success is possible here."""
    _before_currency(result)
    _raws, input_metadata, _metadata = _checked_before_input(result.input)
    clock = result.clock
    readback = canonical(readback_raw)
    require(readback["fileCount"] == 279 and readback["directoryCount"] == 58 and
        tuple(row["relative"] for row in readback["files"]) == tuple(name for name in required if name != "authority-close.json") and
        O.integer(readback["closedNs"]) <= O.integer(preclose) <= O.integer(closed) < clock.frame["sealEndNs"],
        "BEFORE_PENDING_CLOSE_CHRONOLOGY_OR_ROSTER")
    raw = O.encoded({"schema": 1, "scope": B.CLOSE_SCOPE, "edge": "BEFORE", "kind": clock.frame["kind"],
        "originalWindow": clock.frame, "deadline": clock.seed, "inputMetadata": input_metadata,
        "authority": result.summary, "parentClose": parent_close, "preCloseNs": preclose, "closedNs": closed,
        "requiredFiles": list(required), "requiredFileCount": 280, "otherFiles": readback["files"],
        "otherFilesCount": 279, "otherFilesTotalBytes": readback["totalBytes"], "directories": readback["directories"],
        "directoryCount": 58, "originalReadbackClose": readback["ownerClose"],
        "self": {"relative": "authority-close.json", "maximum": native.LIMIT,
            "state": "PENDING_SEPARATE_WRITER_READBACK_AND_CLOSE"},
        "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED", "liveRecipient": "NOT_CREATED",
        "capture": "NOT_K_CAPTURE", "upload": "NOT_PERFORMED", "testAcceptance": "NOT_PERFORMED",
        "productiveAuthority": False, "cacheAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    canonical(raw)
    return raw


def _before_write_close(result, raw, readback_raw, required, directories):
    """Fresh original capped writer AFTER actual authority/query/native closes."""
    clock, path = result.clock, result.private.path
    result.owner.known()
    metadata = _PrimaryOwner(native.Owner(clock.local_end, clock, first=clock.reading, cancelled=clock.cancelled))
    failure = None
    try:
        clock.attach_file_owner("writer", metadata)
        _before_currency(result)
        expected = canonical(readback_raw)
        observed_pins = {row["relative"]: tuple(row["readbackIdentity"]) for row in expected["directories"]}
        initial_members = dict(B.directory_members(required, directories, closed=False))
        final_members = dict(B.directory_members(required, directories, closed=True))
        custody = _private(metadata, path.parent)
        original_root = _BEFORE_INPUTS[id(result.input)][6][1]
        require(custody.path == original_root[2] and tuple(custody.identity) == original_root[3] and
            _tail_directory_names(metadata, custody) == _before_roster(created=True), "BEFORE_WRITER_CUSTODY_ROOT")
        handles, pins = {}, [("custody", custody, custody.path, tuple(custody.identity))]
        for relative in sorted(directories, key=lambda name: (name.count("/"), name != ".", name)):
            target = path if relative == "." else path.joinpath(*relative.split("/"))
            directory = _private(metadata, target)
            identity = tuple(directory.identity)
            require(identity == observed_pins[relative] and not any(identity == old[3] for old in pins),
                "BEFORE_WRITER_READBACK_PIN_CHANGED")
            _before_directory_members(metadata, directory, initial_members[relative])
            handles[relative] = directory
            pins.append((relative, directory, directory.path, identity))
        private = handles["."]
        canonical(raw)
        reader = metadata.acquire("embedded-reader", lambda: io.BytesIO(raw))
        end = metadata.guard()
        writer = metadata.acquire("writer", lambda: private.create_file("authority-close.json", max_bytes=len(raw), deadline=end))
        writer_ordinal = len(metadata.rows) - 1
        def verify():
            require(type(reader) is io.BytesIO and reader.getvalue() == raw, "BEFORE_CLOSE_WRITER_BYTES")
        checksum, written_metadata = _consume(metadata, reader, len(raw), O.digest(raw), verify, writer=writer)
        require(checksum == O.digest(raw) and metadata.rows[writer_ordinal][2] is writer and
            metadata.rows[writer_ordinal][3:] == (True, True), "BEFORE_CLOSE_WRITER_HASH_OR_CLOSE")
        write_observation = {"bytes": len(raw), "sha256": checksum, "metadata": canonical(written_metadata),
            "writerOrdinal": writer_ordinal, "observation": "PRE_CLOSE_WRITE_VERIFY", "retirement": "KNOWN_WRITER_CLOSE"}
        _before_metadata(write_observation["metadata"], clock.clock.role, len(raw))
        reread, observation = _before_read(metadata, private, "authority-close.json", native.LIMIT,
            count=len(raw), checksum=checksum)
        require(reread == raw, "BEFORE_CLOSE_WRITER_READBACK")
        # These are different native lifetimes, not interchangeable stamps.
        # Only Windows modified/change times may finalize across writer close;
        # the real postclose reader above still requires full lifetime equality.
        metadata_policy = B.write_close_metadata(clock.clock.role, write_observation["metadata"],
            observation["metadata"], len(raw))
        for relative, directory in handles.items():
            _before_directory_members(metadata, directory, final_members[relative])
        require(_tail_directory_names(metadata, custody) == _before_roster(created=True), "BEFORE_WRITER_FINAL_ROOT")
        _before_currency(result)
        graph = N._history_graph(write_observation, observation, tuple(pin[2] for pin in pins))
        close = metadata.finish()
        closed = clock.now()
        _before_file_owner_known(metadata, metadata._anchor(), pins)
        N._check_history(graph)
        writer_return = O.encoded({"schema": 1, "scope": "INITIAL_BEFORE_CLOSE_WRITER_KNOWN_RETURN_V1",
            "relative": "authority-close.json", "bytes": len(raw), "sha256": O.digest(raw),
            "preCloseWrite": write_observation, "readback": observation, "metadataPolicy": metadata_policy,
            "ownerClose": _collect_file_close(close), "closedNs": closed,
            "originalStepOutcome": "NOT_OBSERVED", "capture": "NOT_K_CAPTURE", "exportSaveAuthority": False})
        canonical(writer_return)
        return writer_return, metadata, tuple(pins)
    except BaseException as error:
        failure = metadata.remember(error)
    finally:
        if not metadata.finished and not metadata.owner.unknown:
            try:
                metadata.finish()
            except BaseException as error:
                if failure is None:
                    failure = error
    raise failure


@dataclass(frozen=True, repr=False)
class _BeforeAuthority:
    """Genuine same-process280-file return, not a deserializable K capability."""
    acquired: object
    raw: bytes
    originals: tuple
    readback: bytes
    writer_close: bytes
    index: bytes


def _close_before_authority(acquired):
    """Token-free full279 readback, actual authority close, then the280th writer."""
    saved = _BEFORE_ACQUIRED.get(id(acquired))
    require(type(saved) is tuple and saved[0] is acquired, "BEFORE_CLOSE_ORIGINAL_ACQUISITION")
    # Pin the ORIGINAL owner/anchor before the first currency callback; a
    # changed return dictionary must not redirect or skip failed-entry cleanup.
    attempt, owner, owner_anchor, clock, entry = saved[4], saved[8], saved[9], saved[10], saved[11]
    failure = None
    try:
        require(_before_currency(acquired) is saved, "BEFORE_CLOSE_ACQUISITION_CHANGED")
        require(attempt["state"] == "ACQUIRED" and attempt["return"] is None, "BEFORE_CLOSE_ONCE")
        attempt["state"] = "CLOSING"
        index, required, directories = _before_index(acquired)
        targets = {name: acquired.private.path if name == "." else acquired.private.path / name for name in B.DIRECTORY_TARGETS}
        original_pins = N._worker_pins(owner, clock.clock.role, targets)
        require(all(label == "directory" or attempted and closed for _row, label, _resource, attempted, closed in owner.check().rows),
            "BEFORE_ORIGINAL_WRITERS_NOT_CLOSED")
        originals, readback_raw, readback_owner, readback_pins = _before_capture(acquired, index, required, directories, original_pins)
        readback_anchor = readback_owner._anchor()
        _before_file_owner_known(readback_owner, readback_anchor, readback_pins)
        N._check_worker_pins(original_pins, clock.clock.role)
        _before_currency(acquired)
        require(native._initializer_names(owner, acquired.root) == _before_roster(created=True), "BEFORE_PRECLOSE_ROOT")
        preclose = clock.now()
        owner.freeze()
    except BaseException as error:
        error = entry[0].fail(error)
        owner.error("before-authority-capture", error)
        failure = owner_anchor.failure
    finally:
        try:
            owner.close()
        except BaseException as error:
            owner.error("before-authority-close", error)
        if failure is None and owner_anchor.failure is not None:
            failure = owner_anchor.failure
    try:
        if failure is not None:
            raise failure
        anchor = owner.known()
        closed = clock.now(minimum=preclose)
        N._check_worker_pins(original_pins, clock.clock.role, closed=True)
        _before_file_owner_known(readback_owner, readback_anchor, readback_pins)
        _before_currency(acquired)
        parent_close = {"schema": 1, "scope": "INITIAL_BEFORE_AUTHORITY_PARENT_KNOWN_CLOSE_V1",
            "resources": [{"ordinal": number, "label": label, "closeAttempted": attempted, "closed": ended}
                for number, (_row, label, _resource, attempted, ended) in enumerate(anchor.rows)],
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False}
        raw = _before_pending_close(acquired, readback_raw, required, parent_close, preclose, closed)
        writer_close, writer_owner, writer_pins = _before_write_close(acquired, raw, readback_raw, required, directories)
        complete = tuple(sorted((*originals, ("authority-close.json", raw))))
        require(len(complete) == 280 and tuple(name for name, _raw in complete) == required, "BEFORE_REAL280_REQUIRED")
        readback, writer_return = canonical(readback_raw), canonical(writer_close)
        files = sorted((*readback["files"], {"relative": "authority-close.json", "maximum": native.LIMIT,
            **writer_return["readback"]}), key=lambda row: row["relative"])
        total = sum(len(data) for _name, data in complete)
        require(total <= MAX_BYTES, "BEFORE_REAL280_TOTAL_LIMIT")
        index_raw = O.encoded({"schema": 1, "scope": "INITIAL_BEFORE_ACTUAL_ORIGINALS_CLOSED_RETURN_V1",
            "requiredFiles": list(required), "files": files, "fileCount": 280, "totalBytes": total,
            "directories": readback["directories"], "directoryCount": 58,
            "authorityCloseSha256": O.digest(raw), "closeWriterReturn": writer_return,
            "originalReadbackClose": readback["ownerClose"], "capture": "NOT_K_CAPTURE",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False,
            "cacheAuthority": False, "exportSaveAuthority": False})
        canonical(index_raw)
        result = _BeforeAuthority(acquired, raw, complete, readback_raw, writer_close, index_raw)
        binding = (result, result.__dict__, acquired, raw, complete, readback_raw, writer_close, index_raw, clock,
            writer_owner, writer_owner._anchor(), writer_pins, readback_owner, readback_anchor, readback_pins,
            original_pins, N._history_graph(result.__dict__, writer_owner.owner.__dict__, readback_owner.owner.__dict__,
                owner.__dict__, tuple(pin[2] for pin in (*writer_pins, *readback_pins))), attempt, entry)
        require(id(result) not in _BEFORE_AUTHORITIES, "BEFORE_RETURN_REUSE")
        _BEFORE_AUTHORITIES[id(result)] = binding
        attempt["return"], attempt["state"] = result, "RETURNED"
        _checked_before_authority(result)
        clock.now()
        _checked_before_authority(result)
        return result
    except BaseException as error:
        error = entry[0].fail(error)
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def _checked_before_authority(result):
    """Internal closed-owner check; the enclosing entry may still be STARTED."""
    saved = _BEFORE_AUTHORITIES.get(id(result))
    require(type(result) is _BeforeAuthority and type(saved) is tuple and saved[0] is result, "BEFORE_NOT_ORIGINAL_AUTHORITY")
    _, dictionary, acquired, raw, originals, readback, writer_close, index_raw, clock, writer, writer_anchor, writer_pins, \
        reader, reader_anchor, reader_pins, original_pins, graph, attempt, entry = saved
    try:
        _before_entry_current(entry)
        require(result.__dict__ is dictionary and result.acquired is acquired and result.raw == raw and
            result.originals is originals and result.readback == readback and result.writer_close == writer_close and
            result.index == index_raw and attempt["state"] == "RETURNED" and attempt["return"] is result and
            attempt["failure"] is None, "BEFORE_AUTHORITY_RETURN_CHANGED")
        N._check_history(graph)
        require(_checked_before_acquired(acquired)[11] is entry, "BEFORE_AUTHORITY_ORIGINAL_ENTRY")
        acquired.owner.known()
        clock_anchor = clock._view()
        require(acquired.clock is clock and clock_anchor.binding[9] is entry and clock_anchor.failure is None,
            "BEFORE_AUTHORITY_CLOCK_CHANGED")
        _before_file_owner_known(writer, writer_anchor, writer_pins)
        _before_file_owner_known(reader, reader_anchor, reader_pins)
        N._check_worker_pins(original_pins, clock.clock.role, closed=True)
        index = canonical(index_raw)
        require(type(index["fileCount"]) is int and index["fileCount"] == len(originals) == 280 and
            index["requiredFiles"] == [name for name, _raw in originals] and len(index["files"]) == 280 and
            type(index["directoryCount"]) is int and index["directoryCount"] == len(index["directories"]) == 58 and
            type(index["totalBytes"]) is int and index["totalBytes"] == sum(len(data) for _name, data in originals) <= MAX_BYTES and
            index["authorityCloseSha256"] == O.digest(raw), "BEFORE_AUTHORITY_EXHAUSTIVE_ROSTER_CHANGED")
        for (name, data), row in zip(originals, index["files"]):
            require(row["relative"] == name and type(row["bytes"]) is int and row["bytes"] == len(data) and
                row["sha256"] == O.digest(data), "BEFORE_AUTHORITY_ORIGINAL_BYTES_CHANGED")
        require(dict(originals)["authority-close.json"] == raw and
            index["closeWriterReturn"] == canonical(writer_close) and index["capture"] == "NOT_K_CAPTURE",
            "BEFORE_AUTHORITY_CLOSE_WRITER_CHANGED")
        _before_entry_current(entry)
        return clock, acquired.input, originals, index_raw, acquired.match, acquired.captured
    except BaseException as error:
        error = entry[0].fail(error)
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]


def checked_before_authority(result):
    """Passive original-result check, including actual enclosing entry completion.

    A pending internal result is not accepted here. A future one-use K still
    needs this same clock/current authority and freshly read originals; this
    checker itself never copies K, validates a recipient or grants export/upload.
    """
    saved = _BEFORE_AUTHORITIES.get(id(result))
    require(type(result) is _BeforeAuthority and type(saved) is tuple and saved[0] is result,
        "BEFORE_NOT_ORIGINAL_AUTHORITY")
    entry = saved[18]
    try:
        _before_entry_current(entry)
        entry[0].returned(_BEFORE_ATTEMPTS, entry[1], result)
        checked = _checked_before_authority(result)
        _before_entry_current(entry)
        entry[0].returned(_BEFORE_ATTEMPTS, entry[1], result)
        return checked
    except BaseException as error:
        raise entry[0].fail(error)


def _before_pre_metadata(kind, cancelled, entry):
    """The ONLY parent token frame; it returns before exhaustive readback/copy."""
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    try:
        _before_entry_current(entry)
        actual, seed = _before_actual()
        local = local_value(time.monotonic())
        first = O.clocks.observe()
        graph = N._history_graph(first, seed, actual)
        O.clocks.validate_reading(first)
        boot = digest(C.boot_digest(first.clock.role))
        N._check_history(graph)
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and callable(cancelled) and
            native.processes.host_role() == first.clock.role, "BEFORE_TOKEN_OR_HOST")
        clock = _BeforeClock(first, local, boot, cancelled, seed, side="parent", actual=actual, entry=entry)
        inputs = _read_before_input(clock, kind, actual)
        expected = clock.bind_parent(inputs)
        return _before_acquire(inputs, clock, expected, token, entry)
    finally:
        token = None


def before_authority(kind, cancelled):
    """Dormant same-process B entry. No CLI parent output or K/upload success."""
    original = _BEFORE_ENTRY
    attempt = _before_begin("entry")
    entry = (original, attempt)
    try:
        _before_entry_current(entry)
        acquired = _before_pre_metadata(kind, cancelled, entry)
        # All token-bearing frames are gone before the279-file read/copy. Only
        # this actual registered owner can produce the separate280th close row.
        result = _close_before_authority(acquired)
        _before_entry_current(entry)
        require(_BEFORE_AUTHORITIES[id(result)][18] is entry, "BEFORE_RETURN_ENTRY_CHANGED")
        original.complete(_BEFORE_ATTEMPTS, attempt, result)
        original.returned(_BEFORE_ATTEMPTS, attempt, result)
        return result
    except BaseException as error:
        raise original.fail(error)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("collect-export", "collect-close", "seal", "seal-for-before"):
        entry = commands.add_parser(name, allow_abbrev=False)
        entry.add_argument("--kind", required=True, choices=("gate", "worker"))
    for name in ("_authority", "_crypto", "_post-export-authority", "_tail-authority", "_before-authority"):
        child = commands.add_parser(name, allow_abbrev=False)
        child.add_argument("--context-sha256", required=True)
        child.add_argument("--minimum-ns", required=True)
        if name == "_before-authority":
            for field, _environment, flag in B.SEED_FIELDS:
                child.add_argument(flag, required=True, dest=field)
            for field, flag in B.PHASE_FIELDS:
                child.add_argument(flag, required=True, dest=field)
    args = parser.parse_args()
    try:
        require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
            "ISOLATED_INTERPRETER_REQUIRED")
        if args.operation in ("collect-export", "collect-close", "seal", "seal-for-before"):
            operation = {"collect-export": collect_export, "collect-close": collect_close,
                "seal": seal, "seal-for-before": seal_for_before}[args.operation]
            native.guarded(lambda signals: operation(args.kind, lambda: native.cancellation(signals)))
            return 0
        digest(args.context_sha256)
        require(re.fullmatch(r"0|[1-9][0-9]{0,19}", args.minimum_ns), "LAUNCH_MINIMUM")
        minimum = O.integer(int(args.minimum_ns))
        if args.operation == "_before-authority":
            seed = {name: getattr(args, name) for name, _environment, _flag in B.SEED_FIELDS}
            caps = B.decimal_caps(seed, tuple(getattr(args, name) for name, _flag in B.PHASE_FIELDS))
            command = native.initial_before_authority_command(args.context_sha256, seed, caps, minimum)
            require(sys.argv[1:] == command[5:], "BEFORE_EXACT_CHILD_ARGUMENTS")
            native.guarded(lambda signals: _before_authority_child(args.context_sha256, minimum,
                lambda: native.cancellation(signals), seed, caps))
            return 0
        if args.operation == "_authority":
            native.initial_custody_authority_command(args.context_sha256, minimum)
            operation = custody_authority_child
        elif args.operation == "_post-export-authority":
            native.initial_collect_authority_command(args.context_sha256, minimum)
            operation = _collect_authority_child
        elif args.operation == "_tail-authority":
            native.initial_tail_authority_command(args.context_sha256, minimum)
            operation = _tail_authority_child
        else:
            _custody_crypto_command(args.context_sha256, minimum)
            operation = custody_crypto_child
        native.guarded(lambda signals: operation(args.context_sha256, minimum, lambda: native.cancellation(signals)))
        return 0
    except BaseException:
        print("INITIAL_RECIPIENT_CUSTODY_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
