"""Private K carrier-close DATA, not original native/Step or upload authority.

The fixed K parent emits this only after its actual new child/native and four
file copy/readback owners have KNOWN closes. The record cannot describe its
own later writer close. A genuine successful enclosing BEFORE Step and the
hash in the separately closed pending record remain necessary. U owns fresh
readers and compares their full metadata to these post-close observations.

This separate large-file grammar does NOT widen B's small-record comparator,
the old plaintext Snapshot, Windows900s, or either existing ciphertext/ZIP
cap. Private metadata and paths never belong in the public pending manifest.
"""
from __future__ import annotations

import hashlib
import re

import hosted_initial_recipient_tail_handoff as H


SCOPE = "INITIAL_RECIPIENT_K_CARRIER_KNOWN_CLOSE_V1"
LIMIT = H.LIMIT
PHASE_NAMES = ("start.json", "baseline.json", "result.json", "native-start.json", "stdout.log", "stderr.log")
SOURCE_NAMES = ("export-output/evidence.tar.gz.gpg", "export-output/manifest.json",
    "tail-export-output/evidence.tar.gz.gpg", "tail-export-output/manifest.json")
FILE_FIELDS = {"name", "bytes", "sha256", "sourceRelative", "sourceDirectoryIdentity", "sourceRead", "write",
    "readback", "metadataPolicy"}
FIELDS = {"schema", "scope", "kind", "selection", "source", "github", "originalWindow", "deadline",
    "predecessors", "manifests", "cutMapSha256", "carrier", "files", "totalBytes", "zipBytes", "nativeClose",
    "ownerCloses", "times", "writerReturn", "originalStepOutcome", "upload", "testAcceptance",
    "productiveAuthority", "cacheAuthority", "exportSaveAuthority", "budgetAcceptance"}


def require(value, code):
    H.require(value, "CARRIER_" + code)


def identity(value, role):
    require(type(value) is list and len(value) == 2, "IDENTITY")
    H._integer(value[0], 0, H.B.clocks.UINT64)
    if role == "windows-x64":
        require(type(value[1]) is str and re.fullmatch(r"[0-9a-f]{32}", value[1]) is not None, "WINDOWS_IDENTITY")
    else:
        require(role in H.B.clocks.DOMAINS, "ROLE")
        H._integer(value[1], 1, H.B.clocks.UINT64)
    return tuple(value)


def metadata(value, role, count):
    """Actual supplied observation grammar, never an open/verify/close action."""
    H._integer(count, 0, H.MAX_ZIP_BYTES)
    windows = role == "windows-x64"
    fields = {"identity", "is_directory", "size", "links", "attributes", "creation_100ns", "modified_100ns",
        "change_100ns", "owner_sid", "protected_dacl"} if windows else {"device", "inode", "size", "mtime_ns", "ctime_ns"}
    H._fields(value, fields)
    require(type(value["size"]) is int and value["size"] == count, "METADATA_SIZE")
    if windows:
        pin = identity(value["identity"], role)
        H._integer(value["attributes"], 0, H.B.clocks.UINT64)
        require(value["is_directory"] is False and type(value["links"]) is int and value["links"] == 1 and
            type(value["owner_sid"]) is str and re.fullmatch(r"S-1-[0-9-]{1,180}", value["owner_sid"]) is not None and
            value["protected_dacl"] is True and not value["attributes"] & (0x400 | 0x10), "WINDOWS_PRIVATE_FILE")
        integers = ("attributes", "creation_100ns", "modified_100ns", "change_100ns")
    else:
        pin = identity([value["device"], value["inode"]], role)
        integers = ("mtime_ns", "ctime_ns")
    for name in integers:
        H._integer(value[name], 0, H.B.clocks.UINT64)
    return pin


def write_close_metadata(role, before, after, count):
    """Same strict per-reader lifetime, only the known write-close seam differs."""
    require(metadata(before, role, count) == metadata(after, role, count), "WRITE_CLOSE_IDENTITY")
    allowed = {"modified_100ns", "change_100ns"} if role == "windows-x64" else set()
    require(H.T.original._canonical({name: value for name, value in before.items() if name not in allowed}) ==
        H.T.original._canonical({name: value for name, value in after.items() if name not in allowed}),
        "WRITE_CLOSE_METADATA_CHANGED")
    return "WINDOWS_WRITE_CLOSE_MODIFIED_CHANGE_ONLY" if allowed else "POSIX_FULL_METADATA_EQUAL"


def _resources(value, *, carrier):
    require(type(value) is list and 0 < len(value) <= H.T.posix.MAX_MEMBERS, "RESOURCE_ROWS")
    labels = ("directory",) * 4 + ("reader", "writer", "reader") * 4 if carrier else None
    require(not carrier or len(value) == len(labels), "CARRIER_RESOURCE_COUNT")
    for ordinal, row in enumerate(value):
        H._fields(row, {"ordinal", "label", "closeAttempted", "closed"})
        require(type(row["ordinal"]) is int and row["ordinal"] == ordinal and type(row["label"]) is str and
            row["label"] in ("directory", "writer", "native-scope", "stdout", "stderr", "reader") and
            row["closeAttempted"] is True and row["closed"] is True and
            (not carrier or row["label"] == labels[ordinal]), "KNOWN_RESOURCE_CLOSE")


def close_value(value):
    H.T.original._graph(value)
    H._fields(value, FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE and
        value["kind"] in ("gate", "worker"), "SCOPE")
    _cohort, selected_role, _system, _arch = H.T.S.bootstrap.selection(value["selection"])
    role = "linux-x64" if value["kind"] == "gate" else selected_role
    H.T.S.joint.source(value["source"])
    github = value["github"]
    H._fields(github, {"repository", "runId", "runAttempt", "job", "jobId", "role"})
    H.T.S.joint.run(github)
    H._integer(github["jobId"], 1, 10 ** 20 - 1)
    require(github["repository"] == H.T.I.REPOSITORY and github["role"] == role and github["job"] ==
        (H.T.original.G.JOB if value["kind"] == "gate" else H.T.S.bootstrap.JOB), "JOB")
    seal_hash, seal_end = H._window(value["originalWindow"], value["kind"], role, value["deadline"])
    H._hashes(value["predecessors"], H.T.PREDECESSOR_FIELDS)
    require(value["predecessors"]["sealSha256"] == seal_hash and value["predecessors"]["originalWindowSha256"] ==
        hashlib.sha256(H.T.original._canonical(value["originalWindow"])).hexdigest(), "WINDOW_HASH")
    H._hashes(value["manifests"], H.MANIFEST_FIELDS)
    H.T.original._sha(value["cutMapSha256"])
    H._fields(value["carrier"], {"relative", "identity"})
    require(value["carrier"]["relative"] == "upload-output", "FIXED_CARRIER")
    carrier_pin = identity(value["carrier"]["identity"], role)
    require(type(value["files"]) is list and len(value["files"]) == 4, "FOUR_FILES")
    file_pins, source_dirs, members = {carrier_pin}, [], []
    for number, row in enumerate(value["files"]):
        H._fields(row, FILE_FIELDS)
        members.append({name: row[name] for name in ("name", "bytes", "sha256")})
        require(row["sourceRelative"] == SOURCE_NAMES[number], "FIXED_SOURCE")
        source_dir = identity(row["sourceDirectoryIdentity"], role)
        source_dirs.append(source_dir)
        observations = []
        for name, label, ordinal in (("sourceRead", "reader", 4 + number * 3),
                ("write", "writer", 5 + number * 3), ("readback", "reader", 6 + number * 3)):
            observation = row[name]
            H._fields(observation, {"metadata", label + "Ordinal"})
            require(type(observation[label + "Ordinal"]) is int and observation[label + "Ordinal"] == ordinal,
                "EXACT_FILE_RESOURCE_ORDINAL")
            observations.append(metadata(observation["metadata"], role, row["bytes"]))
        require(observations[0] != observations[1] == observations[2] and
            observations[0] not in file_pins and observations[1] not in file_pins, "FILE_ALIAS")
        file_pins.update((observations[0], observations[1]))
        require(write_close_metadata(role, row["write"]["metadata"], row["readback"]["metadata"], row["bytes"]) ==
            row["metadataPolicy"], "WRITE_CLOSE_POLICY")
    require(source_dirs[0] == source_dirs[1] and source_dirs[2] == source_dirs[3] and
        source_dirs[0] != source_dirs[2] and not set(source_dirs).intersection(file_pins), "SOURCE_DIRECTORY_ALIAS")
    total, zipped = H.carrier_bytes(members)
    require(type(value["totalBytes"]) is int and value["totalBytes"] == total and type(value["zipBytes"]) is int and
        value["zipBytes"] == zipped and members[1]["sha256"] == value["manifests"]["p0Sha256"] and
        members[3]["sha256"] == value["manifests"]["tailSha256"], "CARRIER_EQUATIONS")
    close = value["nativeClose"]
    H._fields(close, {"contextSha256", "resultSha256", "ackSha256", "phaseSha256"})
    for name in ("contextSha256", "resultSha256", "ackSha256"):
        H.T.original._sha(close[name])
    H._hashes(close["phaseSha256"], PHASE_NAMES)
    require(close["ackSha256"] == close["phaseSha256"]["stdout.log"], "ACK_LINK")
    H._fields(value["ownerCloses"], {"native", "carrier"})
    for name, scope in (("native", "INITIAL_K_NATIVE_PARENT_KNOWN_CLOSE_V1"),
            ("carrier", "INITIAL_CUSTODY_PRIMARY_NATIVE_CLOSE_V1")):
        observed = value["ownerCloses"][name]
        H._fields(observed, {"schema", "scope", "resources", "retirement", "exportSaveAuthority"})
        require(type(observed["schema"]) is int and observed["schema"] == 1 and observed["scope"] == scope and
            observed["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and observed["exportSaveAuthority"] is False,
            "OWNER_CLOSE_SCOPE")
        _resources(observed["resources"], carrier=name == "carrier")
    H._fields(value["times"], H.TIME_FIELDS[:-1])
    previous = value["originalWindow"]["startNs"]
    for name in H.TIME_FIELDS[:-1]:
        previous = H._integer(value["times"][name], previous, seal_end - 1)
    require(value["writerReturn"] == "PENDING_SEPARATE_RECORD_WRITER_CLOSE" and
        value["originalStepOutcome"] == "NOT_OBSERVED" and value["upload"] == value["testAcceptance"] == "NOT_PERFORMED" and
        value["productiveAuthority"] is False and value["cacheAuthority"] is False and
        value["exportSaveAuthority"] is False and value["budgetAcceptance"] == "NOT_ADMITTED", "NO_SELF_ACCEPTANCE")
    return value


def parse_close(raw):
    require(type(raw) is bytes and 0 < len(raw) <= LIMIT, "BYTES")
    value = H.T.I.parse(raw, LIMIT)
    require(H.T.original._canonical(value) == raw, "CANONICAL")
    return close_value(value)


def encode_close(value):
    raw = H.T.original._canonical(close_value(value))
    require(0 < len(raw) <= LIMIT, "BYTES")
    return raw
