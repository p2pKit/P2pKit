"""Four literal stored-ZIP byte streams, not file ownership or upload authority.

The genuine caller supplies its fixed, newly owned reader for each index. That
reader must independently enforce its original clocks, exact path/identity,
metadata, EOF and known close; exhaustion of a Python iterable proves none of
those facts. This module performs no I/O, opens no file, and grants no admission.
It verifies every supplied byte against the immutable input declaration and
returns only byte/framing observations. No whole archive is buffered.
"""
from __future__ import annotations

import hashlib
import re
import struct
import zlib


MEMBERS = ("evidence.tar.gz.gpg", "manifest.json", "custody-tail.tar.gz.gpg", "custody-tail-manifest.json")
CHUNK_BYTES = 64 * 1024
MANIFEST_BYTES = 64 * 1024
CIPHERTEXT_BYTES = 576 * 1024 * 1024
# Existing Stage2 packet limit applies to the COMPLETE ZIP, not its contents.
MAX_ZIP_BYTES = 512 * 1024 * 1024
OVERHEAD = 22 + sum(30 + 16 + 46 + 2 * len(name) for name in MEMBERS)
SCOPE = "INITIAL_ARTIFACT_STORED_ZIP_BYTES_ONLY_V1"


class ZipError(ValueError):
    """Only fixed source-owned diagnostics; no supplied content or path."""


def require(value, code):
    if not value:
        raise ZipError("INITIAL_ARTIFACT_ZIP_" + code)


def checked_members(members):
    """Capture closed supplied DATA as immutable scalars, not file metadata."""
    require(type(members) is list and len(members) == len(MEMBERS), "MEMBER_ROSTER")
    captured, total = [], 0
    for index, (row, name) in enumerate(zip(members, MEMBERS)):
        require(type(row) is dict and all(type(key) is str for key in row) and
                set(row) == {"name", "bytes", "sha256"}, "MEMBER_FIELDS")
        require(type(row["name"]) is str and row["name"] == name, "MEMBER_NAME_OR_ORDER")
        maximum = MANIFEST_BYTES if index in (1, 3) else CIPHERTEXT_BYTES
        count, checksum = row["bytes"], row["sha256"]
        require(type(count) is int and 0 < count <= maximum, "MEMBER_SIZE")
        require(type(checksum) is str and re.fullmatch(r"[0-9a-f]{64}", checksum), "MEMBER_DIGEST")
        captured.append((name, count, checksum))
        total += count
    require(total <= CIPHERTEXT_BYTES and total + OVERHEAD <= MAX_ZIP_BYTES, "COMPLETE_ZIP_LIMIT")
    return tuple(captured)


def zip_bytes(members):
    """Exact framing prediction, still not an observed ZIP or provider result."""
    return sum(row[1] for row in checked_members(members)) + OVERHEAD


def stored_zip(members, read_member):
    """Yield at most64KiB per demand and return byte-only observations.

    ``read_member(index)`` is invoked only upon demand for that member's bytes,
    after its local header has been yielded. The fixed native caller owns the
    reader, cancellation, time and close before that iterable returns. This
    callback is not a user-selected filename or a launcher.

    Arguments are captured eagerly, before the returned generator's first
    demand. Source rows may subsequently be changed by their caller but cannot
    alter this immutable declaration; native callers separately pin their
    complete original pending record/graph. No iteration or byte supplier is
    invoked during this preparation.
    """
    captured = checked_members(members)
    require(callable(read_member), "SUPPLIER")
    expected = sum(row[1] for row in captured) + OVERHEAD

    def produce():
        offset, complete, rows, central = 0, hashlib.sha256(), [], []

        def record(raw):
            nonlocal offset
            require(type(raw) is bytes and 0 < len(raw) <= CHUNK_BYTES, "FRAMING_CHUNK")
            require(offset + len(raw) <= expected, "ZIP_OVERRUN")
            complete.update(raw)
            offset += len(raw)
            return raw

        for index, (name, count, checksum) in enumerate(captured):
            filename = name.encode("ascii")
            beginning = offset
            # Classic ZIP2.0, descriptor flag8, STORED, DOS1980-01-01, no extras.
            yield record(struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 8, 0, 0, 33,
                                     0, 0, 0, len(filename), 0) + filename)
            size, crc, content = 0, 0, hashlib.sha256()
            for piece in read_member(index):
                require(type(piece) is bytes and 0 < len(piece) <= CHUNK_BYTES, "INPUT_CHUNK")
                require(size + len(piece) <= count, "MEMBER_OVERRUN")
                size += len(piece)
                crc = zlib.crc32(piece, crc)
                content.update(piece)
                yield record(piece)
            require(size == count and content.hexdigest() == checksum, "MEMBER_SHORT_OR_DIGEST")
            yield record(struct.pack("<IIII", 0x08074B50, crc, size, size))
            central.append(struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 0x0314, 20,
                                       8, 0, 0, 33, crc, size, size, len(filename),
                                       0, 0, 0, 0, 0o100600 << 16, beginning) + filename)
            rows.append({"name": name, "bytes": size, "sha256": checksum, "crc32": crc})
        directory_start = offset
        for row in central:
            yield record(row)
        directory_bytes = offset - directory_start
        yield record(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, len(MEMBERS), len(MEMBERS),
                                 directory_bytes, directory_start, 0))
        require(offset == expected, "COMPLETE_ZIP_SIZE")
        return {"schema": 1, "scope": SCOPE, "members": rows, "zipBytes": offset,
                "zipSha256": complete.hexdigest(), "nativeFileRetirement": "NOT_ESTABLISHED",
                "originalRunnerOutcome": "NOT_OBSERVED", "qualification": "NOT_ESTABLISHED"}

    return produce()
