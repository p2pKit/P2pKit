"""Closed K-to-U pending DATA; never a clock, B/K return or upload permission.

The genuine one-use custody parent alone may write this fixed pending file and
emit its hash after actual child/native/file closes. This codec performs no
I/O and cannot establish that any supplied hash/close/Step/source is original.
U independently binds actual BEFORE success before Create, owns its original
FIRST cap and four file readers, and observes terminal delivery with A. Neither
current checkout cleanliness nor fresh recipient/source authority follows from
this historical data. Native identities and filesystem paths stay PRIVATE.
"""
from __future__ import annotations

import hashlib

import hosted_initial_recipient_before as B
import hosted_initial_recipient_tail_evidence as T


SCOPE = "INITIAL_RECIPIENT_BEFORE_UPLOAD_PENDING_V1"
FILE = "before-upload-pending.json"
DIRECTORY = "tail-returned"
PRIVATE_CARRIER_CLOSE = "carrier-close.json"
OUTPUT = "initialBeforeSha256"
HASH_ENV = "P2PKIT_INITIAL_BEFORE_SHA256"
OUTCOME_ENV = "P2PKIT_INITIAL_BEFORE_OUTCOME"
LIMIT = T.MANIFEST_LIMIT
# This is the EXISTING downstream complete-ZIP bound, not the backend's inner
# ciphertext capacity. Raising either old cap or omitting framing is forbidden.
MAX_ZIP_BYTES = 512 * 1024 * 1024
ORIGINAL_FIELDS = {"eventSha256", "policySha256", "matchSha256"}
MANIFEST_FIELDS = {"p0Sha256", "tailSha256"}
CLOSE_FIELDS = {"beforeReadbackSha256", "beforeCloseWriterSha256", "tailChildCloseSha256", "carrierCloseSha256"}
TIME_FIELDS = ("beforeClosedNs", "tailChildClosedNs", "carrierClosedNs", "pendingPreparedNs")
WINDOW_ENDS = ("workEndNs", "nativeFinalEndNs", "readEndNs", "sealEndNs", "uploadEndNs", "afterEndNs")
FIELDS = {
    "schema", "scope", "kind", "selection", "source", "github", "originalWindow", "deadline", "originals",
    "predecessors", "manifests", "cutMapSha256", "members", "totalBytes", "zipBytes", "knownCloses", "times",
    "writerReturn", "originalStepOutcome", "upload", "testAcceptance", "productiveAuthority", "cacheAuthority",
    "exportSaveAuthority", "budgetAcceptance",
}


def require(value, code):
    T.require(value, "HANDOFF_" + code)


def _fields(value, names):
    require(type(value) is dict and all(type(name) is str for name in value) and set(value) == set(names), "FIELDS")


def _integer(value, low, high):
    require(type(value) is int and low <= value <= high, "INTEGER")
    return value


def _hashes(value, names):
    _fields(value, names)
    for checksum in value.values():
        T.original._sha(checksum)


def _window(value, kind, role, seed):
    """The maintained finite window algebra as DATA, with no clock supplier."""
    _fields(value, {"schema", "scope", "clock", "originalBootDigest", "kind", "originalJobBasisNs", "jobEndNs",
        "startNs", *WINDOW_ENDS})
    require(type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == "INITIAL_RECIPIENT_CUSTODY_ABSOLUTE_WINDOW_V1" and value["kind"] == kind, "WINDOW_SCOPE")
    clock = B.wire.clock_identity(value["clock"])
    seal_hash, seal_end, declared, boot = B.continuity.seal_deadline_data(seed)
    require(clock == declared and clock.role == role and value["originalBootDigest"] == boot, "WINDOW_CLOCK_OR_BOOT")
    for name in ("originalJobBasisNs", "jobEndNs", "startNs", *WINDOW_ENDS):
        _integer(value[name], 0, B.clocks.UINT64)
    basis, start = value["originalJobBasisNs"], value["startNs"]
    job_end = basis + (360 if kind == "gate" else 1200) * B.wire.NS
    work = min(start + 240 * B.wire.NS, job_end - 180 * B.wire.NS)
    expected = (work, work + 45 * B.wire.NS, work + 75 * B.wire.NS, work + 105 * B.wire.NS,
        work + 165 * B.wire.NS, work + 180 * B.wire.NS)
    require(basis <= start < work and value["jobEndNs"] == job_end and expected[-1] <= job_end and
        tuple(value[name] for name in WINDOW_ENDS) == expected and value["sealEndNs"] == seal_end,
        "WINDOW_ORIGINAL_ARITHMETIC")
    return seal_hash, seal_end


def carrier_bytes(members):
    """Exactly four stored-ZIP members, with signed16-byte data descriptors.

    No ZIP64, extra fields, comments, directory entries or filename overrides.
    U must implement these exact bytes and enforce the same512MiB aggregate
    before Create; neither this formula nor a receipt proves an actual ZIP.
    """
    require(type(members) is list and len(members) == len(T.CARRIER_MEMBERS), "FOUR_MEMBERS")
    total, framing = 0, 22
    for number, (row, name) in enumerate(zip(members, T.CARRIER_MEMBERS)):
        _fields(row, {"name", "bytes", "sha256"})
        require(type(row["name"]) is str and row["name"] == name, "LITERAL_MEMBER_ORDER")
        maximum = T.MANIFEST_LIMIT if number in (1, 3) else T.posix.MAX_CIPHERTEXT_BYTES
        total += _integer(row["bytes"], 1, maximum)
        T.original._sha(row["sha256"])
        framing += 30 + 16 + 46 + 2 * len(name.encode("ascii"))
    require(total <= T.posix.MAX_CIPHERTEXT_BYTES and total + framing <= MAX_ZIP_BYTES, "CARRIER_OR_DOWNSTREAM_ZIP_CAP")
    return total, total + framing


def pending_value(value):
    """Validate exact supplied history; no side effects or live return is made."""
    T.original._graph(value)
    _fields(value, FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE and
        type(value["kind"]) is str and value["kind"] in ("gate", "worker"), "SCOPE")
    kind = value["kind"]
    _cohort, selected_role, _system, _arch = T.S.bootstrap.selection(value["selection"])
    role = "linux-x64" if kind == "gate" else selected_role
    T.S.joint.source(value["source"])
    github = value["github"]
    _fields(github, {"repository", "runId", "runAttempt", "job", "jobId", "role"})
    T.S.joint.run(github)
    _integer(github["jobId"], 1, 10 ** 20 - 1)
    require(github["repository"] == T.I.REPOSITORY and github["role"] == role and
        github["job"] == (T.original.G.JOB if kind == "gate" else T.S.bootstrap.JOB), "JOB")
    seal_hash, seal_end = _window(value["originalWindow"], kind, role, value["deadline"])
    _hashes(value["originals"], ORIGINAL_FIELDS)
    require(value["originals"]["policySha256"] == T.S.POLICY_SHA256, "POLICY_PIN")
    _hashes(value["predecessors"], T.PREDECESSOR_FIELDS)
    require(value["predecessors"]["sealSha256"] == seal_hash and value["predecessors"]["originalWindowSha256"] ==
        hashlib.sha256(T.original._canonical(value["originalWindow"])).hexdigest(), "PREDECESSOR_WINDOW")
    _hashes(value["manifests"], MANIFEST_FIELDS)
    T.original._sha(value["cutMapSha256"])
    total, zipped = carrier_bytes(value["members"])
    require(type(value["totalBytes"]) is int and value["totalBytes"] == total and type(value["zipBytes"]) is int and
        value["zipBytes"] == zipped and value["members"][1]["sha256"] == value["manifests"]["p0Sha256"] and
        value["members"][3]["sha256"] == value["manifests"]["tailSha256"], "CARRIER_DECLARATION")
    _hashes(value["knownCloses"], CLOSE_FIELDS)
    _fields(value["times"], TIME_FIELDS)
    previous = value["originalWindow"]["startNs"]
    for name in TIME_FIELDS:
        previous = _integer(value["times"][name], previous, seal_end - 1)
    require(value["writerReturn"] == "PENDING_OWNER_CLOSE" and value["originalStepOutcome"] == "NOT_OBSERVED" and
        value["upload"] == value["testAcceptance"] == "NOT_PERFORMED" and value["productiveAuthority"] is False and
        value["cacheAuthority"] is False and value["exportSaveAuthority"] is False and
        value["budgetAcceptance"] == "NOT_ADMITTED", "NO_SELF_OR_EXECUTION_ACCEPTANCE")
    return value


def parse_pending(raw):
    require(type(raw) is bytes and 0 < len(raw) <= LIMIT, "BYTES")
    value = T.I.parse(raw, LIMIT)
    require(T.original._canonical(value) == raw, "CANONICAL")
    return pending_value(value)


def encode_pending(value):
    raw = T.original._canonical(pending_value(value))
    require(0 < len(raw) <= LIMIT, "BYTES")
    return raw


def output_values(raw):
    """Seven exact output strings as DATA, never an append or output fence."""
    value = parse_pending(raw)
    return {OUTPUT: hashlib.sha256(raw).hexdigest(), **value["deadline"]}
