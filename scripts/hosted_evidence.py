#!/usr/bin/env python3
"""Bounded, encrypted-only export; this is custody, never acceptance or publication.

The caller must have stopped evidence writers and own all three disjoint directories.
Public-key operations cannot start an agent or use a keyserver. No private campaign
key is accepted here. Upload only the two files returned by a SUCCESSFUL export.
Raw GPG diagnostics stay in ``owned_work_dir``; exception messages are public-safe.
The manifest binds bytes/source/run labels, not independent evidence of execution.
"""
from __future__ import annotations

import argparse
import base64
import dataclasses
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import BinaryIO


MAX_KEY_BYTES = 64 * 1024
MAX_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 10_000
MAX_CIPHERTEXT_BYTES = 576 * 1024 * 1024
MAX_ARCHIVE_BYTES = MAX_CIPHERTEXT_BYTES - 8 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 900
MAX_DIAGNOSTIC_BYTES = 1024 * 1024
ARTIFACT = "evidence.tar.gz.gpg"
MANIFEST = "manifest.json"
REPOSITORY = "p2pKit/P2pKit"


class EvidenceError(RuntimeError):
    """A public-safe failure; do not print raw exceptions or private GPG output."""


@dataclasses.dataclass(frozen=True)
class Recipient:
    work_dir: Path
    home: Path
    executable: Path
    fingerprint: str
    encryption_fingerprint: str
    expires_at: int
    key_sha256: str
    work_identity: tuple[int, int]


def _fail(message: str) -> None:
    raise EvidenceError(message)


def _deadline(end: float) -> None:
    if time.monotonic() >= end:
        _fail("Encrypted evidence operation exceeded its deadline")


def _path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        _fail("Evidence paths must be absolute and normalized")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if current != path:
                _fail("Evidence path parent is absent")
            break
        if stat.S_ISLNK(info.st_mode):
            _fail("Evidence paths cannot contain symbolic links")
    return path


def _private_directory(value: str | Path, *, empty: bool = False) -> Path:
    path = _path(value)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        _fail("Evidence directories must be exclusively owned mode-0700 directories")
    if empty and any(path.iterdir()):
        _fail("Evidence work directory must be new and empty")
    return path


def _identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    return info.st_dev, info.st_ino


def _disjoint(*paths: Path) -> None:
    for index, left in enumerate(paths):
        for right in paths[index + 1:]:
            if left == right or left in right.parents or right in left.parents:
                _fail("Evidence, encryption work, and upload directories must be disjoint")


def _exclusive(path: Path) -> BinaryIO:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    return os.fdopen(fd, "wb")


def _read_regular(path: Path, maximum: int) -> bytes:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or \
            info.st_mode & 0o022 or not 0 < info.st_size <= maximum:
        _fail("Evidence input must be a bounded, owned, unlinked regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        if _stamp(os.fstat(handle.fileno())) != _stamp(info):
            _fail("Evidence input changed while opening")
        data = handle.read(maximum + 1)
        if len(data) != info.st_size or _stamp(os.fstat(handle.fileno())) != _stamp(info):
            _fail("Evidence input changed while reading")
        return data


def _packet_length(data: bytes, index: int, old_type: int | None) -> tuple[int, int]:
    if index >= len(data):
        _fail("Malformed public-key packet")
    if old_type is not None:
        if old_type == 3:
            _fail("Indeterminate public-key packets are not admitted")
        size = (1, 2, 4)[old_type]
        if index + size > len(data):
            _fail("Truncated public-key packet length")
        return int.from_bytes(data[index:index + size], "big"), index + size
    first = data[index]
    index += 1
    if first < 192:
        return first, index
    if first < 224:
        if index >= len(data):
            _fail("Truncated public-key packet length")
        return ((first - 192) << 8) + data[index] + 192, index + 1
    if first == 255 and index + 4 <= len(data):
        return int.from_bytes(data[index:index + 4], "big"), index + 4
    _fail("Partial or truncated public-key packets are not admitted")


def _public_armor(data: bytes) -> bytes:
    """Reject secret/compressed/multiple-key packets before invoking GPG at all."""
    try:
        lines = data.decode("ascii").replace("\r\n", "\n").rstrip("\n").split("\n")
        if len(lines) < 4 or lines[0] != "-----BEGIN PGP PUBLIC KEY BLOCK-----" or \
                lines[-1] != "-----END PGP PUBLIC KEY BLOCK-----" or any("\r" in line for line in lines):
            _fail("Exactly one armored public key is required")
        position = 1
        while lines[position]:
            if position > 10 or len(lines[position]) > 1024 or \
                    not re.fullmatch(r"(?:Version|Comment|Charset): [\x20-\x7e]*", lines[position]):
                _fail("Unsupported public-key armor header")
            position += 1
        payload = lines[position + 1:-1]
        checksum = payload.pop() if payload and payload[-1].startswith("=") else None
        if not payload or any(not re.fullmatch(r"[A-Za-z0-9+/=]{1,76}", line) for line in payload):
            _fail("Malformed public-key armor")
        packets = base64.b64decode("".join(payload), validate=True)
        if checksum is not None:
            expected = base64.b64decode(checksum[1:], validate=True)
            crc = 0xB704CE
            for byte in packets:
                crc ^= byte << 16
                for _ in range(8):
                    crc <<= 1
                    if crc & 0x1000000:
                        crc ^= 0x1864CFB
            if len(expected) != 3 or expected != (crc & 0xFFFFFF).to_bytes(3, "big"):
                _fail("Invalid public-key armor checksum")
        index, primary, count = 0, 0, 0
        while index < len(packets):
            header = packets[index]
            index += 1
            if not header & 0x80:
                _fail("Malformed public-key packet header")
            tag = header & 0x3F if header & 0x40 else (header >> 2) & 0x0F
            if tag not in {2, 6, 13, 14, 17}:
                _fail("Secret or unsupported public-key packets are not admitted")
            if count == 0 and tag != 6:
                _fail("A public primary key must be the first packet")
            primary += tag == 6
            count += 1
            length, index = _packet_length(packets, index, None if header & 0x40 else header & 3)
            if length == 0 or index + length > len(packets) or count > 256:
                _fail("Truncated or excessive public-key packets")
            index += length
        if primary != 1:
            _fail("Exactly one public primary key is required")
        return packets
    except (ValueError, IndexError, UnicodeError):
        _fail("Malformed public-key armor")


def _gpg(recipient: Recipient, arguments: list[str], end: float, *, output: Path | None = None,
         status: bool = False) -> tuple[bytes, bytes]:
    """GPG has no agent/network authority; only this direct child is terminated."""
    _deadline(end)
    operation = Path(tempfile.mkdtemp(prefix="gpg-", dir=recipient.work_dir))
    stdout_path = output if output is not None else operation / "stdout"
    stderr_path, status_path = operation / "stderr", operation / "status"
    command = [str(recipient.executable), "--no-options", "--homedir", str(recipient.home),
               "--batch", "--no-tty", "--no-autostart", "--no-auto-key-retrieve",
               "--no-auto-key-import", "--auto-key-locate", "clear", "--disable-dirmngr",
               "--pinentry-mode", "error", "--no-random-seed-file", "--no-default-keyring",
               "--keyring", str(recipient.work_dir / "recipient.gpg")]
    environment = {"PATH": os.defpath, "HOME": str(recipient.work_dir), "GNUPGHOME": str(recipient.home),
                   "LANG": "C", "LC_ALL": "C", "TMPDIR": str(recipient.work_dir / "tmp")}
    process = None
    code = None
    problem = None
    with _exclusive(stdout_path) as out, _exclusive(stderr_path) as err, _exclusive(status_path) as status_file:
        if status:
            command += ["--status-fd", str(status_file.fileno())]
        try:
            process = subprocess.Popen(command + arguments, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                       cwd=recipient.work_dir, env=environment, close_fds=True,
                                       pass_fds=(status_file.fileno(),) if status else ())
            while process.poll() is None:
                _deadline(end)
                if stderr_path.stat().st_size > MAX_DIAGNOSTIC_BYTES or \
                        status_path.stat().st_size > MAX_DIAGNOSTIC_BYTES or \
                        stdout_path.stat().st_size > (MAX_CIPHERTEXT_BYTES if output else MAX_DIAGNOSTIC_BYTES):
                    _fail("GPG exceeded the evidence output bound")
                time.sleep(0.025)
            code = process.wait()
        except BaseException:
            problem = "operation-interrupted"
            raise
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                code = process.returncode
            for handle in (out, err, status_file):
                handle.flush()
                os.fsync(handle.fileno())
            with _exclusive(operation / "process.json") as record:
                record.write(json.dumps({"schema": 1, "waitExitCode": code,
                                         "retired": process is None or process.poll() is not None,
                                         "interruption": problem}, sort_keys=True).encode("ascii") + b"\n")
    if code != 0:
        _fail("GPG failed; private diagnostics were retained")
    if stderr_path.stat().st_size > MAX_DIAGNOSTIC_BYTES or \
            status_path.stat().st_size > MAX_DIAGNOSTIC_BYTES or \
            stdout_path.stat().st_size > (MAX_CIPHERTEXT_BYTES if output else MAX_DIAGNOSTIC_BYTES):
        _fail("GPG exceeded the evidence output bound")
    return (b"" if output is not None else stdout_path.read_bytes(), status_path.read_bytes())


def _key_identity(listing: bytes, expected: str) -> tuple[str, int]:
    try:
        records = [line.split(":") for line in listing.decode("ascii").splitlines() if line]
        if any(row[0] in {"sec", "ssb"} for row in records) or sum(row[0] == "pub" for row in records) != 1:
            _fail("Only one public primary key is admitted")
        keys: list[tuple[list[str], str]] = []
        pending = None
        for row in records:
            if row[0] in {"pub", "sub"}:
                if len(row) < 12 or pending is not None:
                    _fail("Malformed public-key listing")
                pending = row
            elif row[0] == "fpr":
                if pending is None or len(row) < 10 or not re.fullmatch(r"[A-F0-9]{40}", row[9]):
                    _fail("Malformed public-key fingerprint listing")
                keys.append((pending, row[9]))
                pending = None
        if pending is not None or not keys or keys[0][0][0] != "pub" or keys[0][1] != expected:
            _fail("Public-key fingerprint mismatch")
        now = int(time.time())

        def expiry(row: list[str]) -> int:
            if row[6] and not row[6].isdigit():
                _fail("Malformed key expiry")
            return int(row[6] or "0")

        def usable(row: list[str]) -> bool:
            return row[1] not in {"r", "e", "d", "i"} and "D" not in row[11] and \
                (expiry(row) == 0 or expiry(row) > now)

        primary = keys[0][0]
        if not usable(primary):
            _fail("Public primary key is expired, revoked, disabled, or invalid")
        choices = [(row, fingerprint) for row, fingerprint in keys if "e" in row[11] and usable(row)]
        if not choices:
            _fail("No currently usable encryption key is present")
        chosen, fingerprint = choices[-1]
        expirations = [value for value in (expiry(primary), expiry(chosen)) if value]
        return fingerprint, min(expirations) if expirations else 0
    except (ValueError, UnicodeError, IndexError):
        _fail("Malformed GPG public-key listing")


def validate_recipient(key_path: str | Path, expected_full_fingerprint: str,
                       owned_work_dir: str | Path) -> Recipient:
    """Before acquisition/builds, validate one v4 public encryption key.

    ``owned_work_dir`` must already exist, be empty, exclusively owned and mode0700.
    It remains private; retain its operation records on failure. This creates no
    private key, starts no agent, and does not authenticate the owner's fingerprint.
    The caller must independently obtain that full fingerprint from the owner.
    """
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        _fail("Encrypted evidence export requires native POSIX file ownership")
    if not isinstance(expected_full_fingerprint, str) or \
            not re.fullmatch(r"[0-9a-fA-F]{40}", expected_full_fingerprint):
        _fail("Expected fingerprint must be exactly 40 hexadecimal digits")
    work = _private_directory(owned_work_dir, empty=True)
    key = _path(key_path)
    if key == work or work in key.parents:
        _fail("Recipient key must be supplied outside the empty work directory")
    data = _read_regular(key, MAX_KEY_BYTES)
    packets = _public_armor(data)
    gpg = shutil.which("gpg")
    if gpg is None:
        _fail("Installed GPG is required; automatic installation is not permitted")
    executable = Path(gpg).resolve(strict=True)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        _fail("Installed GPG executable is unavailable")
    home = work / "gnupg"
    home.mkdir(mode=0o700)
    (work / "tmp").mkdir(mode=0o700)
    with _exclusive(work / "recipient.asc") as copied:
        copied.write(data)
    # GPG --import can contact an agent even for a public key. A dearmored,
    # explicitly selected public-only legacy ring requires no agent/import.
    with _exclusive(work / "recipient.gpg") as copied:
        copied.write(packets)
    fingerprint = expected_full_fingerprint.upper()
    recipient = Recipient(work, home, executable, fingerprint, "", 0,
                          hashlib.sha256(data).hexdigest(), _identity(work))
    end = time.monotonic() + 60
    common = ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint"]
    shown, _ = _gpg(recipient, common + ["--import-options", "show-only", "--import",
                                        str(work / "recipient.asc")], end)
    encryption_fingerprint, expires_at = _key_identity(shown, fingerprint)
    selected, _ = _gpg(recipient, common + ["--list-keys"], end)
    if _key_identity(selected, fingerprint) != (encryption_fingerprint, expires_at):
        _fail("Selected recipient differs from the validated public key")
    return dataclasses.replace(recipient, encryption_fingerprint=encryption_fingerprint, expires_at=expires_at)


def _stamp(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _snapshot(root: Path, max_bytes: int, max_members: int, end: float) -> dict[str, tuple[int, ...]]:
    entries: dict[str, tuple[int, ...]] = {}
    total = 0

    def visit(fd: int, relative: str, depth: int) -> None:
        nonlocal total
        _deadline(end)
        if depth > 64:
            _fail("Evidence directory nesting exceeds the bound")
        directory_before = _stamp(os.fstat(fd))
        with os.scandir(fd) as stream:
            for entry in stream:
                _deadline(end)
                if len(entries) >= max_members:
                    _fail("Evidence member count exceeds the bound")
                if "\\" in entry.name or any(ord(character) < 32 or ord(character) == 127 for character in entry.name):
                    _fail("Evidence archive member name is unsafe")
                name = relative + "/" + entry.name if relative else entry.name
                if len(name.encode("utf-8")) > 1024:
                    _fail("Evidence archive member name exceeds the bound")
                info = entry.stat(follow_symlinks=False)
                if info.st_uid != os.getuid() or info.st_mode & 0o022:
                    _fail("Evidence members must be owned and not externally writable")
                if not stat.S_ISREG(info.st_mode) and not stat.S_ISDIR(info.st_mode):
                    _fail("Evidence may contain only regular files and directories, never links or special files")
                if stat.S_ISREG(info.st_mode):
                    if info.st_nlink != 1:
                        _fail("Evidence hard links are not admitted")
                    total += info.st_size
                    if total > max_bytes:
                        _fail("Evidence byte count exceeds the bound")
                entries[name] = _stamp(info)
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        if _stamp(os.fstat(child)) != _stamp(info):
                            _fail("Evidence directory changed while opening")
                        visit(child, name, depth + 1)
                    finally:
                        os.close(child)
        if _stamp(os.fstat(fd)) != directory_before:
            _fail("Evidence directory changed while enumerating")

    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        entries[""] = _stamp(os.fstat(fd))
        visit(fd, "", 0)
    finally:
        os.close(fd)
    return entries


def _open_member(root: Path, name: str, snapshot: dict[str, tuple[int, ...]]) -> BinaryIO:
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    prefix = ""
    try:
        if _stamp(os.fstat(fd)) != snapshot[""]:
            _fail("Evidence root changed after inventory")
        parts = name.split("/")
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            prefix = prefix + "/" + part if prefix else part
            if _stamp(os.fstat(fd)) != snapshot[prefix]:
                _fail("Evidence parent changed after inventory")
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        handle = os.fdopen(leaf, "rb")
        if _stamp(os.fstat(handle.fileno())) != snapshot[name]:
            handle.close()
            _fail("Evidence member changed after inventory")
        return handle
    finally:
        os.close(fd)


class _TimedReader:
    def __init__(self, handle: BinaryIO, end: float):
        self.handle, self.end = handle, end

    def read(self, count: int) -> bytes:
        _deadline(self.end)
        return self.handle.read(count)


class _BoundedWriter:
    def __init__(self, handle: BinaryIO, end: float):
        self.handle, self.end, self.count = handle, end, 0

    def write(self, data: bytes) -> int:
        _deadline(self.end)
        self.count += len(data)
        if self.count > MAX_ARCHIVE_BYTES:
            _fail("Compressed evidence exceeds the archive bound")
        return self.handle.write(data)


def _archive(root: Path, destination: Path, snapshot: dict[str, tuple[int, ...]], end: float) -> None:
    with _exclusive(destination) as raw:
        with gzip.GzipFile(fileobj=_BoundedWriter(raw, end), mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                for name, stamp in sorted(snapshot.items()):
                    _deadline(end)
                    info = tarfile.TarInfo("evidence/" + name if name else "evidence")
                    info.uid, info.gid, info.uname, info.gname, info.mtime = 0, 0, "", "", 0
                    if stat.S_ISDIR(stamp[2]):
                        info.type, info.mode = tarfile.DIRTYPE, 0o700
                        archive.addfile(info)
                    else:
                        info.mode, info.size = 0o600, stamp[5]
                        with _open_member(root, name, snapshot) as handle:
                            archive.addfile(info, _TimedReader(handle, end))
                            if handle.read(1) or _stamp(os.fstat(handle.fileno())) != stamp:
                                _fail("Evidence member changed while archiving")
        raw.flush()
        os.fsync(raw.fileno())


def _ciphertext_shape(path: Path, encryption_fingerprint: str) -> None:
    """Reject incomplete outer packets; only private decryption verifies integrity.

    Depending on public-key preferences, maintained GPG versions select MDC or
    AEAD. Obsolete --force-mdc/--rfc4880 switches do not force MDC in GPG 2.5.
    Never admit the unprotected historical tag-9 encrypted packet.
    """
    size = path.stat().st_size
    if not 32 < size <= MAX_CIPHERTEXT_BYTES:
        _fail("Encrypted evidence size is invalid")
    with path.open("rb") as handle:
        def exact(count: int) -> bytes:
            data = handle.read(count)
            if len(data) != count:
                _fail("Encrypted evidence is truncated")
            return data

        def length(old: int | None) -> tuple[int, bool]:
            if old is not None:
                if old == 3:
                    _fail("Indeterminate ciphertext packet is not admitted")
                return int.from_bytes(exact((1, 2, 4)[old]), "big"), False
            first = exact(1)[0]
            if first < 192:
                return first, False
            if first < 224:
                return ((first - 192) << 8) + exact(1)[0] + 192, False
            if first == 255:
                return int.from_bytes(exact(4), "big"), False
            return 1 << (first & 0x1F), True

        def header() -> tuple[int, int | None]:
            byte = exact(1)[0]
            if not byte & 0x80:
                _fail("Invalid ciphertext packet header")
            return (byte & 0x3F, None) if byte & 0x40 else ((byte >> 2) & 0x0F, byte & 3)

        tag, old = header()
        count, partial = length(old)
        if tag != 1 or partial or not 10 < count <= 8192:
            _fail("Encrypted evidence must have exactly one public-key recipient")
        recipient = exact(count)
        if recipient[0] != 3 or recipient[1:9].hex().upper() != encryption_fingerprint[-16:]:
            _fail("Encrypted evidence recipient differs from the validated key")
        tag, old = header()
        if tag not in {18, 20} or old is not None:
            _fail("Encrypted evidence lacks an integrity-protected data packet")
        integrity_tag = tag
        total, first = 0, True
        while True:
            count, partial = length(None)
            total += count
            if handle.tell() + count > size:
                _fail("Encrypted evidence is truncated")
            if first:
                if count < 1:
                    _fail("Unsupported encrypted-evidence integrity format")
                version = exact(1)[0]
                count -= 1
                if integrity_tag == 18 and version == 1:
                    pass  # RFC4880 integrity-protected encryption (MDC).
                elif (integrity_tag == 18 and version == 2) or (integrity_tag == 20 and version == 1):
                    if count < 3:
                        _fail("Truncated AEAD header")
                    cipher, aead, chunk = exact(3)
                    count -= 3
                    if cipher != 9 or aead not in {1, 2, 3} or chunk > 56:
                        _fail("Unsupported encrypted-evidence AEAD parameters")
                else:
                    _fail("Unsupported encrypted-evidence integrity format")
                first = False
            handle.seek(count, os.SEEK_CUR)
            if not partial:
                break
        if total < 32 or handle.tell() != size:
            _fail("Encrypted evidence has missing integrity data or extra packets")


def _manifest_identity(source_commit: str, source_tree: str, run_id: str, run_attempt: str) -> dict:
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value)
           for value in (source_commit, source_tree)) or \
            any(not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", value)
                for value in (run_id, run_attempt)):
        _fail("Full source identities and positive bounded run identifiers are required")
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or \
            os.environ.get("GITHUB_SHA") != source_commit or os.environ.get("GITHUB_RUN_ID") != run_id or \
            os.environ.get("GITHUB_RUN_ATTEMPT") != run_attempt or \
            os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        _fail("Evidence identity does not match the actual manual GitHub run environment")
    return {"schema": 1, "scope": "ENCRYPTED_PRIVATE_TEST_EVIDENCE",
            "source": {"commit": source_commit, "tree": source_tree},
            "github": {"repository": REPOSITORY, "runId": run_id, "runAttempt": run_attempt}}


def export_encrypted(evidence_dir: str | Path, output_dir: str | Path, recipient: Recipient, *,
                     source_commit: str, source_tree: str, run_id: str, run_attempt: str,
                     max_bytes: int = MAX_BYTES, max_members: int = MAX_MEMBERS,
                     timeout_seconds: int = MAX_TIMEOUT_SECONDS) -> dict:
    """Produce ciphertext + minimal manifest; authorize upload only after return.

    All evidence must be quiescent. Input/archive limits may be reduced, never
    increased. The caller must condition upload on this function's successful
    return and must not upload its private work directory (even on failure).
    Private cleanup can fail after ciphertext/manifest creation. Their presence
    alone is not success: a separate post-return seal is required by the caller.
    This is not secure erasure of underlying storage or integrity verification;
    the owner must decrypt/inspect the archive privately before accepting results.
    """
    if any(isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum
           for value, maximum in ((max_bytes, MAX_BYTES), (max_members, MAX_MEMBERS),
                                  (timeout_seconds, MAX_TIMEOUT_SECONDS))):
        _fail("Evidence bounds must be positive and no greater than the fixed limits")
    manifest = _manifest_identity(source_commit, source_tree, run_id, run_attempt)
    return _export_bound_manifest(evidence_dir, output_dir, recipient, manifest=manifest,
                                  max_bytes=max_bytes, max_members=max_members, timeout_seconds=timeout_seconds)


def _export_bound_manifest(evidence_dir: str | Path, output_dir: str | Path, recipient: Recipient, *,
                           manifest: dict, max_bytes: int, max_members: int, timeout_seconds: int) -> dict:
    """Shared POSIX mechanism, private to closed admitted entry points.

    Ordinary CI has its own event/policy admission. The existing public manual
    API above still performs the same bounds and actual-manual-identity checks;
    neither entry point accepts an arbitrary caller-supplied public manifest.
    """
    if any(isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum
           for value, maximum in ((max_bytes, MAX_BYTES), (max_members, MAX_MEMBERS),
                                  (timeout_seconds, MAX_TIMEOUT_SECONDS))):
        _fail("Evidence bounds must be positive and no greater than the fixed limits")
    root = _private_directory(evidence_dir)
    work = _private_directory(recipient.work_dir)
    if _identity(work) != recipient.work_identity:
        _fail("Recipient work ownership changed")
    output = _path(output_dir)
    _private_directory(output.parent)
    _disjoint(root, work, output)
    if os.path.lexists(output):
        _fail("An existing evidence output cannot be overwritten")
    _private_directory(recipient.home)
    key_data = _read_regular(work / "recipient.asc", MAX_KEY_BYTES)
    if hashlib.sha256(key_data).hexdigest() != recipient.key_sha256 or \
            _public_armor(key_data) != _read_regular(work / "recipient.gpg", MAX_KEY_BYTES):
        _fail("Validated recipient changed")
    if recipient.expires_at and recipient.expires_at <= int(time.time()):
        _fail("Validated recipient expired before evidence export")
    end = time.monotonic() + timeout_seconds
    listing, _ = _gpg(recipient, ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint",
                                "--list-keys"], min(end, time.monotonic() + 30))
    if _key_identity(listing, recipient.fingerprint) != (recipient.encryption_fingerprint, recipient.expires_at):
        _fail("Recipient keyring changed before evidence export")
    snapshot = _snapshot(root, max_bytes, max_members, end)
    private = Path(tempfile.mkdtemp(prefix="export-", dir=work))
    plaintext, ciphertext = private / "evidence.tar.gz", private / ARTIFACT
    output_identity = None
    try:
        _archive(root, plaintext, snapshot, end)
        if _snapshot(root, max_bytes, max_members, end) != snapshot:
            _fail("Evidence changed during archive creation")
        _, status = _gpg(recipient, ["--cipher-algo", "AES256", "--compress-algo", "none",
                                     "--trust-model", "always", "--no-encrypt-to",
                                     "--recipient", recipient.encryption_fingerprint + "!", "--output", "-",
                                     "--encrypt", str(plaintext)], end, output=ciphertext, status=True)
        status_lines = status.splitlines()
        if sum(line.startswith(b"[GNUPG:] BEGIN_ENCRYPTION ") for line in status_lines) != 1 or \
                status_lines.count(b"[GNUPG:] END_ENCRYPTION") != 1 or \
                any(line.startswith((b"[GNUPG:] FAILURE", b"[GNUPG:] ERROR")) for line in status_lines):
            _fail("GPG did not confirm complete evidence encryption")
        _ciphertext_shape(ciphertext, recipient.encryption_fingerprint)
        digest = hashlib.sha256()
        with ciphertext.open("rb") as encrypted:
            for block in iter(lambda: encrypted.read(1024 * 1024), b""):
                _deadline(end)
                digest.update(block)
        manifest["artifact"] = {"name": ARTIFACT, "sha256": digest.hexdigest(), "size": ciphertext.stat().st_size}
        encoded = (json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")
        _deadline(end)
        # Exclusive reservation never overwrites another invocation. The upload
        # step may run only after successful return; a manifest is written last.
        output.mkdir(mode=0o700)
        output_identity = _identity(output)
        with _exclusive(output / ARTIFACT) as published, ciphertext.open("rb") as encrypted:
            while True:
                _deadline(end)
                block = encrypted.read(1024 * 1024)
                if not block:
                    break
                published.write(block)
            published.flush()
            os.fsync(published.fileno())
        with _exclusive(output / MANIFEST) as published:
            published.write(encoded)
            published.flush()
            os.fsync(published.fileno())
        return manifest
    except BaseException:
        if output_identity is not None and _identity(output) == output_identity:
            for name in (MANIFEST, ARTIFACT):
                path = output / name
                if path.is_file() and not path.is_symlink():
                    path.unlink()
            output.rmdir()
        raise
    finally:
        # Only paths created exclusively by this invocation; original evidence,
        # raw diagnostics, public key, and caller-owned directories are retained.
        for path in (plaintext, ciphertext):
            if path.is_file() and not path.is_symlink():
                path.unlink()
        private.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--fingerprint", required=True)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    arguments = parser.parse_args()
    try:
        recipient = validate_recipient(arguments.key, arguments.fingerprint, arguments.work_dir)
        manifest = export_encrypted(arguments.evidence_dir, arguments.output_dir, recipient,
                                    source_commit=arguments.source_commit, source_tree=arguments.source_tree,
                                    run_id=arguments.run_id, run_attempt=arguments.run_attempt)
    except EvidenceError as error:
        print(str(error), file=sys.stderr)
        return 125
    except Exception:
        print("Encrypted evidence failed; private diagnostics must remain private", file=sys.stderr)
        return 125
    print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
