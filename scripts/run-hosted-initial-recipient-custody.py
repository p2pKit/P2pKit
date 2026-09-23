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
        require(window._view().failure is None, "PRIMARY_WINDOW_FAILED")
        return window, primary, history, copy, originals
    except BaseException as error:
        if attempt["failure"] is None:
            attempt["failure"] = error
        attempt["state"] = "FAILED"
        raise attempt["failure"]
