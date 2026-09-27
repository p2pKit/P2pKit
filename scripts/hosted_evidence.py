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

# Only the direct script owns its import path. Importing this helper must not
# widen a caller's isolated, hash-bound module-loading environment.
sys.dont_write_bytecode = True
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_processes


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


def _gpg_environment(recipient: Recipient) -> dict[str, str]:
    """Keep credential isolation without erasing an actual enclosing owner.

    The existing manual/direct caller may have no native context. An owned caller
    must supply its COMPLETE original context: preserve it, never invent a domain
    or accept a partial one. This does not create a native scope, prove retirement
    or authorize a different recipient/source. The outer controller still owns
    its original baseline, complete result, failure custody and post-return seal.
    """
    environment = {"PATH": os.defpath, "HOME": str(recipient.work_dir), "GNUPGHOME": str(recipient.home),
                   "LANG": "C", "LC_ALL": "C", "TMPDIR": str(recipient.work_dir / "tmp")}
    markers = (audit_processes.JOB_ENV, audit_processes.CHAIN_ENV,
               audit_processes.DOMAINS_ENV, audit_processes.STATE_ENV)
    if not any(name in os.environ for name in markers):
        return environment
    try:
        owner = {name: os.environ[name] for name in (*markers, "GRADLE_USER_HOME")}
        # Native POSIX discovery decodes these original bytes as ASCII. Keep
        # escaped Unicode paths valid; never reserialize an unrecognizable domain.
        if not owner[audit_processes.DOMAINS_ENV].isascii():
            _fail("Incomplete or mismatched enclosing evidence owner")
        domains = audit_processes.ownership_domains(owner[audit_processes.CHAIN_ENV],
                                                    owner[audit_processes.DOMAINS_ENV])
        if not domains or owner[audit_processes.JOB_ENV] != domains[-1]["job"] or \
                owner[audit_processes.STATE_ENV] != domains[-1]["state"] or \
                owner["GRADLE_USER_HOME"] != domains[-1]["home"]:
            _fail("Incomplete or mismatched enclosing evidence owner")
    except (KeyError, audit_processes.OwnershipError):
        raise EvidenceError("Incomplete or mismatched enclosing evidence owner") from None
    environment.update(owner)
    return environment


def _gpg(recipient: Recipient, arguments: list[str], end: float, *, output: Path | None = None,
         status: bool = False) -> tuple[bytes, bytes]:
    """Bound the direct child and retain a real enclosing native domain, if any."""
    _deadline(end)
    environment = _gpg_environment(recipient)
    operation = Path(tempfile.mkdtemp(prefix="gpg-", dir=recipient.work_dir))
    stdout_path = output if output is not None else operation / "stdout"
    stderr_path, status_path = operation / "stderr", operation / "status"
    command = _gpg_command(recipient)
    process = None
    code = None
    problem = None
    with _exclusive(stdout_path) as out, _exclusive(stderr_path) as err, _exclusive(status_path) as status_file:
        if status:
            command += ["--status-fd", str(status_file.fileno())]
        try:
            process = _spawn_gpg(command + arguments, recipient, environment, out, err, status_file, status)
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


def _gpg_command(recipient):
    """One maintained, public-only/no-agent/no-network GPG command prefix."""
    return [str(recipient.executable), "--no-options", "--homedir", str(recipient.home),
            "--batch", "--no-tty", "--no-autostart", "--no-auto-key-retrieve",
            "--no-auto-key-import", "--auto-key-locate", "clear", "--disable-dirmngr",
            "--pinentry-mode", "error", "--no-random-seed-file", "--no-default-keyring",
            "--keyring", str(recipient.work_dir / "recipient.gpg")]


def _spawn_gpg(command, recipient, environment, out, err, status_file, status):
    # Return the ACTUAL child immediately. The old wrapper preserves its byte
    # interface; productive custody retains this object before any next callback.
    return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
        cwd=recipient.work_dir, env=environment, close_fds=True,
        pass_fds=(status_file.fileno(),) if status else ())


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
    """POSIX path wrapper; native Windows calls the same pathless parser."""
    size = path.stat().st_size
    with path.open("rb") as handle:
        _ciphertext_stream(handle, size, encryption_fingerprint)


def _ciphertext_stream(handle: BinaryIO, size: int, encryption_fingerprint: str) -> None:
    """Reject incomplete outer packets; only private decryption verifies integrity.

    The caller owns, pins and verifies a bounded immutable reader. This parser
    neither opens a path nor turns a Win32 handle into a CRT descriptor. Maintained
    GPG can select MDC or AEAD; unprotected historical tag-9 remains forbidden.
    """
    if type(size) is not int or not 32 < size <= MAX_CIPHERTEXT_BYTES:
        _fail("Encrypted evidence size is invalid")

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


# Separate productive APIs retain native originals rather than manufacturing a
# receipt around the old dictionary/byte return. Legacy public APIs above keep
# their original argument, scope, timeout, cleanup and return contracts.
_PRODUCTIVE_SESSIONS, _PRODUCTIVE_ATTEMPTS = {}, {}
_PRODUCTIVE_RESOURCES, _PRODUCTIVE_CLOSES, _PRODUCTIVE_FINISHES, _PRODUCTIVE_RESULTS = {}, {}, {}, {}
_PRODUCTIVE_OBSERVATIONS, _PRODUCTIVE_STREAMS, _PRODUCTIVE_RECIPIENTS = {}, {}, {}
_PRODUCTIVE_QUARANTINE = []


@dataclasses.dataclass(frozen=True, repr=False)
class _ProductiveSession:
    binding: object


@dataclasses.dataclass(frozen=True, repr=False)
class _ProductiveResource:
    owner: object
    kind: str
    label: str
    original_type: object
    methods: tuple


@dataclasses.dataclass(frozen=True, repr=False)
class _ProductiveClose:
    session: object
    resource: object
    operation: str
    returned: object
    completion: object


@dataclasses.dataclass(frozen=True, repr=False)
class _ProductiveKnownClose:
    session: object
    resources: tuple
    observations: tuple
    completion: object


@dataclasses.dataclass(frozen=True, repr=False)
class _ProductiveValidationReturn:
    binding: object
    session: object
    recipient: object
    observations: object
    known_close: object


@dataclasses.dataclass(frozen=True, repr=False)
class _ProductiveExportReturn:
    binding: object
    session: object
    manifest_raw: bytes
    artifact: object
    observations: object
    known_close: object


@dataclasses.dataclass(frozen=True, repr=False)
class _ProductiveArtifact:
    name: str
    sha256: str
    size: int
    native: tuple


def _pg_require(condition, code):
    if not condition:
        raise EvidenceError("PRODUCTIVE_POSIX_" + code)


def _pg_pin(value):
    return value, type(value), value.__dict__, tuple(value.__dict__.items())


def _pg_pin_current(pin):
    value, kind, dictionary, items = pin
    _pg_require(type(value) is kind and value.__dict__ is dictionary and set(dictionary) == {key for key, _ in items} and
        all(dictionary[key] is original for key, original in items), "OBJECT_CHANGED")


def _pg_methods(owner, names):
    dictionary = getattr(owner, "__dict__", None)
    _pg_require(dictionary is None or type(dictionary) is dict, "METHOD_INSTANCE_DICTIONARY")
    methods = []
    for name in names:
        bound = getattr(owner, name)
        present = dictionary is not None and name in dictionary
        methods.append((name, getattr(type(owner), name, None), bound, type(owner), type(bound),
            getattr(bound, "__func__", None), getattr(bound, "__name__", None), dictionary, present,
            dictionary[name] if present else None))
    return tuple(methods)


def _pg_methods_current(owner, methods, code):
    for name, descriptor, bound, owner_type, bound_type, function, method_name, dictionary, present, slot in methods:
        current_dictionary = getattr(owner, "__dict__", None)
        _pg_require(type(owner) is owner_type and current_dictionary is dictionary and
            (dictionary is not None and name in dictionary) is present and
            (not present or dictionary[name] is slot), code)
        current = getattr(owner, name)
        # FileIO/scandir/hashlib builtin methods have no __func__. Pin their
        # callable kind/name too; same-owner readall is not the original read.
        # A new instance alias is never adopted, even for the same operation.
        _pg_require(getattr(type(owner), name, None) is descriptor and type(current) is bound_type and
            getattr(current, "__self__", None) is owner and getattr(bound, "__self__", None) is owner and
            getattr(current, "__func__", None) is function and
            type(getattr(current, "__name__", None)) is str and type(method_name) is str and
            current.__name__ == method_name, code)


def _pg_resource_current(resource):
    row = _PRODUCTIVE_RESOURCES.get(id(resource))
    _pg_require(type(row) is dict and row["resource"] is resource, "RESOURCE_NOT_ORIGINAL")
    state = _PRODUCTIVE_SESSIONS.get(id(row["session"]))
    _pg_require(type(state) is dict and state["session"] is row["session"] and
        type(row["index"]) is int and 0 <= row["index"] < len(state["resources"]) and
        state["resources"][row["index"]] is resource, "RESOURCE_LEDGER_CHANGED")
    _pg_pin_current(row["pin"])
    _pg_require(type(resource.owner) is resource.original_type, "RESOURCE_TYPE_CHANGED")
    for owner, name, original in row["links"]:
        current = getattr(owner, name)
        # GzipFile's original close clears fileobj BEFORE its trailer writes.
        # The original sink is separately retained, and may not be replaced.
        cleared_gzip = resource.kind == "gzip" and name == "fileobj" and row["attempted"] and current is None
        _pg_require(current is original or cleared_gzip, "RESOURCE_OWNER_LINK_CHANGED")
    _pg_methods_current(resource.owner, resource.methods, "RESOURCE_METHOD_CHANGED")
    if resource.kind in ("format-writer", "tar-stream") and not row["attempted"]:
        # These two original methods short-circuit on a mutable closed flag.
        # Each separately owned object must remain live until its OWN direct
        # close begins; a parent's close cannot authorize this transition.
        _pg_require(resource.owner.closed is False, "LIVE_FORMAT_ALREADY_CLOSED")
    if row["close"] is not None:
        if resource.kind in ("file", "format-writer", "tar-stream"):
            _pg_require(resource.owner.closed is True, "CLOSED_OWNER_CHANGED")
        elif resource.kind == "gzip":
            _pg_require(resource.owner.fileobj is None, "CLOSED_GZIP_CHANGED")
        elif resource.kind == "process":
            _pg_require(type(resource.owner.returncode) is int and
                resource.owner.returncode is row["close"].returned, "CLOSED_PROCESS_CHANGED")
    return row


def _pg_fail(state, error, *, unknown=False):
    if state["failure"] is None:
        state["failure"] = error
    if unknown:
        state["unknown"] = True
    return state["failure"]


def _pg_state(session):
    state = _PRODUCTIVE_SESSIONS.get(id(session))
    _pg_require(type(session) is _ProductiveSession and type(state) is dict and state["session"] is session and
        _PRODUCTIVE_ATTEMPTS.get(id(session.binding)) is state, "SESSION_NOT_ORIGINAL")
    return state


def _pg_passive(state, *, whole=False):
    session = state["session"]
    _pg_require(_pg_state(session) is state and state["pid"] == os.getpid() and
        state["failure"] is None and not state["unknown"] and not _PRODUCTIVE_QUARANTINE, "FAILED_OR_FOREIGN_SESSION")
    _pg_pin_current(state["session_pin"])
    for pin in state["binding_pins"]:
        _pg_pin_current(pin)
    _pg_require(all(getattr(owner, name, None) is original for owner, name, original in state["functions"]),
        "SUPPLIER_CHANGED")
    _pg_require(state["resources"] is state["resource_list"] and type(state["resources"]) is list and
        len(state["resources"]) == state["resource_count"] and state["observations"] is state["observation_list"] and
        len(state["observations"]) == state["observation_count"], "SESSION_LEDGER_CHANGED")
    _pg_require(not state["pending_owners"], "UNREGISTERED_NATIVE_RETURN")
    for resource in state["formats"]:
        _pg_resource_current(resource)
    # At most two recipients/three commands. Keep these selected suppliers
    # current around every effect without traversing the complete input corpus.
    for recipient, pin, paths in state["recipients"]:
        _pg_pin_current(pin)
        for path, kind, original in paths:
            _pg_require(type(path) is kind and str(path) == original, "RECIPIENT_PATH_CHANGED")
    for environment, items in state["environments"]:
        _pg_require(type(environment) is dict and set(environment) == {name for name, _ in items} and
            all(environment[name] is original for name, original in items), "GPG_ENVIRONMENT_CHANGED")
    for command, arguments, environment, items in state["commands"]:
        _pg_require(type(command) is list and len(command) == len(arguments) and
            all(value is original for value, original in zip(command, arguments)) and
            type(environment) is dict and set(environment) == {name for name, _ in items} and
            all(environment[name] is original for name, original in items), "GPG_COMMAND_CHANGED")
    if whole:
        for entries, dictionary, items in state["snapshots"]:
            _pg_require(entries is dictionary and type(entries) is dict and len(entries) == len(items) and
                all(entries.get(name) is stamp for name, stamp in items), "SNAPSHOT_DATA_CHANGED")
        for index, resource in enumerate(state["resources"]):
            row = _pg_resource_current(resource)
            _pg_require(row["session"] is session and row["index"] == index, "RESOURCE_SESSION_CHANGED")
            if row["close"] is not None:
                close = row["close"]
                original = _PRODUCTIVE_CLOSES.get(id(close))
                _pg_require(type(original) is tuple and original[0] is close and original[1] is row,
                    "CLOSE_NOT_ORIGINAL")
                _pg_pin_current(original[2])
                _pg_require(close.resource is resource and close.session is session and row["attempted"] and
                    close.completion is row["completion"] and close.returned is row["return_fact"][1], "CLOSE_CHANGED")
        for index, observation in enumerate(state["observations"]):
            original = _PRODUCTIVE_OBSERVATIONS.get(id(observation))
            _pg_require(type(original) is tuple and original[0] is observation and original[1] is session and
                original[2] == index, "OBSERVATION_NOT_ORIGINAL")
        for stream in state["streams"]:
            _pg_stream_current(stream)


def _pg_guard(session, *, keyring=None):
    state = _pg_state(session)
    if state["failure"] is not None:
        raise state["failure"]
    try:
        _pg_require(not state["busy"] and state["phase"] == "WORK", "REENTRY_OR_PHASE")
        state["busy"] = True
        _pg_passive(state)
        E = state["E"]
        returned = (E._productive_work_guard(session.binding) if keyring is None else
            E._productive_keyring_guard(session.binding, keyring))
        _pg_require(returned is (state["caps"] if keyring is None else keyring), "ORIGINAL_GUARD_RETURN")
        local = time.monotonic()
        _pg_require(type(local) is float and state["local"] <= local <
            (state["caps"].workEndLocal if keyring is None else keyring.workEndLocal), "WORK_DEADLINE")
        state["local"] = local
        _pg_passive(state)
        return returned, local  # Actual E guard return, NOT a newly invented RAW Reading.
    except BaseException as error:
        raise _pg_fail(state, error)
    finally:
        state["busy"] = False


def _pg_note(session, label, *actual):
    state = _pg_state(session)
    row = (label, *actual)
    _PRODUCTIVE_OBSERVATIONS[id(row)] = (row, session, state["observation_count"])
    state["observations"].append(row)
    state["observation_count"] += 1
    return row


def _pg_new(binding, mode):
    import hosted_initial_recipient_evidence as E
    previous = _PRODUCTIVE_ATTEMPTS.get(id(binding))
    if previous is not None:
        raise _pg_fail(previous, EvidenceError("PRODUCTIVE_POSIX_REENTRY"))
    session = _ProductiveSession(binding)
    resources, observations = [], []
    state = {"session": session, "session_pin": _pg_pin(session), "E": E, "mode": mode, "pid": os.getpid(),
        "busy": False, "phase": "STARTED", "failure": None, "unknown": False, "resources": resources,
        "resource_list": resources, "resource_count": 0, "observations": observations,
        "observation_list": observations, "observation_count": 0, "transients": [], "result": None,
        "finish": None, "finish_attempted": False, "pending_process": None, "pending_owners": [],
        "active_keyring": None, "formats": [], "streams": [], "recipients": [], "snapshots": [], "commands": [],
        "environments": [], "written": {}, "output": None, "private": None, "removal_attempts": set()}
    _PRODUCTIVE_SESSIONS[id(session)], _PRODUCTIVE_ATTEMPTS[id(binding)] = state, state
    try:
        _pg_require(os.name == "posix" and hasattr(os, "O_NOFOLLOW"), "NATIVE_POSIX_REQUIRED")
        _pg_require(mode in ("validation", "export"), "SESSION_MODE")
        state["functions"] = tuple((owner, name, getattr(owner, name)) for owner, names in (
            (E, ("_ProductiveValidationBinding", "_ProductiveExportBinding", "_checked_productive_validation_binding",
                "_checked_productive_export_binding", "_productive_work_guard", "_productive_whole_guard",
                "_productive_node_guard", "_productive_expected_node", "_productive_check_snapshot", "_productive_manifest",
                "_productive_keyring_begin", "_productive_keyring_guard", "_productive_keyring_complete")),
            (os, ("open", "close", "fdopen", "fstat", "scandir", "fsync", "getuid", "getpid", "access", "unlink", "rmdir", "mkdir")),
            (os.path, ("lexists",)),
            (subprocess, ("Popen",)), (subprocess.Popen, ("__init__", "poll", "wait", "terminate", "kill")),
            (time, ("monotonic", "sleep")), (tempfile, ("mkdtemp",)), (dataclasses, ("replace",)),
            (gzip, ("GzipFile",)), (gzip.GzipFile, ("__init__", "close", "write", "flush")),
            (tarfile, ("open", "TarInfo", "TarFile", "_Stream")),
            (tarfile.TarInfo, ("__init__", "tobuf")),
            (tarfile.TarFile, ("__init__", "close", "addfile")),
            (tarfile._Stream, ("__init__", "close", "write")), (hashlib, ("sha256",)),
            (Path, ("lstat", "resolve", "is_file", "mkdir", "rmdir", "unlink")), (shutil, ("which",)),
            (sys.modules[__name__], ("_gpg_command", "_spawn_gpg", "_gpg_environment", "_public_armor", "_key_identity",
                "_stamp", "_path", "_private_directory", "_disjoint", "_pg_require", "_pg_state", "_pg_methods",
                "_pg_methods_current", "_pg_fail",
                "_ciphertext_stream", "Recipient", "_ProductiveSession", "_ProductiveResource", "_ProductiveClose",
                "_ProductiveKnownClose", "_ProductiveValidationReturn", "_ProductiveExportReturn", "_ProductiveArtifact",
                "_ProductiveTarReader", "_ProductiveArchiveWriter", "_ProductiveCipherReader",
                "_pg_guard", "_pg_close", "_pg_passive", "_pg_keep", "_pg_resource_current", "_pg_stream_current",
                "_pg_pin", "_pg_pin_current", "_pg_note", "_pg_closed", "_pg_register_result", "_pg_checked_result",
                "_pg_stream_register", "_pg_stream_begin", "_pg_stream_failed", "_pg_tar_block", "_pg_retain_recipient",
                "_pg_open", "_pg_read", "_pg_write", "_pg_snapshot", "_pg_member", "_pg_archive", "_pg_gpg",
                "_pg_directory", "_pg_ciphertext", "_pg_publish", "_pg_output_roster", "_pg_cleanup", "_pg_abort", "_pg_abort_files",
                "_finish_initial_productive", "_checked_productive_validation_return", "_checked_productive_export_return")),
            (_ProductiveTarReader, ("__init__", "read", "finish")),
            (_ProductiveArchiveWriter, ("__init__", "write", "flush")),
            (_ProductiveCipherReader, ("__init__", "read", "seek", "tell", "_current")),
        ) for name in names)
        view = (E._checked_productive_validation_binding(binding) if mode == "validation" else
            E._checked_productive_export_binding(binding))
        _pg_require(state["failure"] is None and all(getattr(owner, name, None) is original
            for owner, name, original in state["functions"]), "ADMISSION_CALLBACK_CHANGED")
        state["view"], state["caps"], state["local"] = view, view.caps, view.caps.firstLocal
        state["binding_pins"] = tuple(_pg_pin(value) for value in
            (binding, view, view.caps, view.caps.first, view.caps.clock))
        state["phase"] = "WORK"
        _pg_guard(session)
        return session
    except BaseException as error:
        raise _pg_fail(state, error)


def _pg_keep(session, owner, kind, label, methods=()):
    # Called FIRST after a native constructor returns, before another guard.
    state = _pg_state(session)
    state["pending_owners"].append(owner)  # Preserve the native return even if binding fails.
    try:
        resource = _ProductiveResource(owner, kind, label, type(owner), _pg_methods(owner, methods))
        row = {"session": session, "resource": resource, "pin": _pg_pin(resource), "attempted": False,
            "close": None, "transferred": None, "transfer_attempted": False, "parent": None, "children": (), "links": (),
            "index": state["resource_count"], "keyring": state["active_keyring"], "return_fact": None,
            "completion": None}
        _PRODUCTIVE_RESOURCES[id(resource)] = row
        state["resources"].append(resource)
        state["resource_count"] += 1
        _pg_require(state["pending_owners"].pop() is owner, "NATIVE_RETURN_REPLACED")
        return resource
    except BaseException as error:
        _PRODUCTIVE_QUARANTINE.append(owner)
        raise _pg_fail(state, error, unknown=True)


def _pg_closed(session, resource, operation, returned, completion):
    row = _pg_resource_current(resource)
    _pg_require(row["session"] is session and row["attempted"] and row["close"] is None, "CLOSE_ONCE")
    close = _ProductiveClose(session, resource, operation, returned, completion)
    _PRODUCTIVE_CLOSES[id(close)] = (close, row, _pg_pin(close))
    row["close"], row["completion"] = close, completion
    if row["return_fact"] is None:
        row["return_fact"] = (operation, returned)
    _pg_require(row["return_fact"][1] is returned, "ACTUAL_RETURN_CHANGED")
    return close


def _pg_close(session, resource, *, keyring=None):
    state, row = _pg_state(session), _pg_resource_current(resource)
    _pg_require(row["session"] is session and not row["attempted"] and row["transferred"] is None,
        "RESOURCE_CLOSE_ONCE")
    _pg_require(keyring is row["keyring"], "RESOURCE_ORIGINAL_SUBCAP")
    _pg_guard(session, keyring=keyring)
    _pg_resource_current(resource)
    if resource.kind == "file":
        row["last_stat"] = os.fstat(resource.owner.fileno())
        _pg_note(session, "file-before-known-close", resource, row["last_stat"])
        _pg_guard(session, keyring=keyring)
        _pg_resource_current(resource)
    row["attempted"] = True
    try:
        if resource.kind == "descriptor":
            returned = os.close(resource.owner)
        else:
            method = next(item[2] for item in resource.methods if item[0] == "close")
            returned = method()
        # A close flag set before the call is NOT a known close. Retain its
        # original normal return and then the actual in-window observation.
        row["return_fact"] = ("DIRECT_CLOSE_RETURN", returned)
        _pg_note(session, "actual-close-return", resource, returned)
        completion = _pg_guard(session, keyring=keyring)
        close = _pg_closed(session, resource, "DIRECT_CLOSE_RETURN", returned, completion)
        parent = row["parent"]
        if parent is not None:
            parent_row = _pg_resource_current(parent)
            _pg_require(parent_row["transferred"] is resource and not parent_row["attempted"], "DESCRIPTOR_TRANSFER")
            parent_row["attempted"] = True
            _pg_closed(session, parent, "TRANSITIVE_FDOPEN_OWNER_CLOSE", close, completion)
        for child in row["children"]:
            child_row = _pg_resource_current(child)
            _pg_require(child_row["transferred"] is resource and not child_row["attempted"], "NESTED_OWNER_TRANSFER")
            child_row["attempted"] = True
            _pg_closed(session, child, "TRANSITIVE_ORIGINAL_AGGREGATE_RETURN", close, completion)
        return close
    except BaseException as error:
        _PRODUCTIVE_QUARANTINE.append(resource)
        raise _pg_fail(state, error, unknown=True)


def _pg_open(session, path, *, write=False, maximum=MAX_CIPHERTEXT_BYTES, keyring=None):
    _pg_guard(session, keyring=keyring)
    before = None if write else path.lstat()
    if before is not None:
        _pg_note(session, "input-lstat", path, before)
        _pg_require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1 and
            not before.st_mode & 0o022 and 0 <= before.st_size <= maximum, "INPUT_OWNERSHIP_OR_BOUND")
    _pg_guard(session, keyring=keyring)
    flags = os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0) | (os.O_WRONLY | os.O_CREAT | os.O_EXCL if write else os.O_RDONLY)
    fd = os.open(path, flags, 0o600)
    descriptor = _pg_keep(session, fd, "descriptor", "open:" + path.name)
    _pg_guard(session, keyring=keyring)
    _pg_resource_current(descriptor)
    _PRODUCTIVE_RESOURCES[id(descriptor)]["transfer_attempted"] = True
    handle = os.fdopen(fd, "wb" if write else "rb", buffering=0)
    resource = _pg_keep(session, handle, "file", "file:" + path.name,
        ("close", "read", "write", "seek", "tell", "fileno", "flush"))
    _PRODUCTIVE_RESOURCES[id(descriptor)]["transferred"] = resource
    _PRODUCTIVE_RESOURCES[id(resource)]["parent"] = descriptor
    _pg_resource_current(resource)
    actual = os.fstat(fd)
    _pg_note(session, "opened-fstat", resource, actual)
    _pg_require(stat.S_ISREG(actual.st_mode) and actual.st_uid == os.getuid() and actual.st_nlink == 1 and
        not actual.st_mode & 0o022 and (actual.st_size == 0 if write else _stamp(actual) == _stamp(before)),
        "OPENED_INPUT_CHANGED")
    if write:
        state = _pg_state(session)
        _pg_require(str(path) not in state["written"], "EXCLUSIVE_PATH_REUSED")
        state["written"][str(path)] = (path, actual, resource)
    _pg_guard(session, keyring=keyring)
    _pg_resource_current(resource)
    return resource, actual


def _pg_read(session, path, maximum, *, keyring=None):
    resource, before = _pg_open(session, path, maximum=maximum, keyring=keyring)
    result, count = [], 0
    while True:
        _pg_guard(session, keyring=keyring)
        _pg_resource_current(resource)
        block = resource.owner.read(min(1024 * 1024, maximum - count + 1))
        _pg_guard(session, keyring=keyring)
        _pg_resource_current(resource)
        _pg_require(type(block) is bytes, "READ_BYTES")
        count += len(block)
        _pg_require(count <= maximum, "READ_BOUND")
        if not block:
            break
        result.append(block)
    after = os.fstat(resource.owner.fileno())
    _pg_note(session, "readback-fstat", resource, after)
    _pg_require(count == before.st_size and _stamp(after) == _stamp(before) and _stamp(path.lstat()) == _stamp(before),
        "READBACK_CHANGED")
    raw = b"".join(result)
    _pg_note(session, "complete-readback", resource, count, hashlib.sha256(raw).hexdigest())
    _pg_close(session, resource, keyring=keyring)
    return raw, ("posix", *_stamp(after))


def _pg_write(session, path, data, maximum, *, keyring=None):
    _pg_require(type(data) is bytes and len(data) <= maximum, "WRITE_BOUND")
    resource, _before = _pg_open(session, path, write=True, maximum=maximum, keyring=keyring)
    for start in range(0, len(data), 1024 * 1024):
        _pg_guard(session, keyring=keyring)
        _pg_resource_current(resource)
        block = data[start:start + 1024 * 1024]
        _pg_require(resource.owner.write(block) == len(block), "SHORT_WRITE")
        _pg_guard(session, keyring=keyring)
        _pg_resource_current(resource)
    _pg_guard(session, keyring=keyring)
    _pg_resource_current(resource)
    resource.owner.flush()
    _pg_guard(session, keyring=keyring)
    _pg_resource_current(resource)
    os.fsync(resource.owner.fileno())
    _pg_guard(session, keyring=keyring)
    _pg_resource_current(resource)
    written = os.fstat(resource.owner.fileno())
    _pg_resource_current(resource)
    _pg_note(session, "synced-write", resource, written)
    _pg_require(written.st_size == len(data), "WRITE_SIZE")
    _pg_close(session, resource, keyring=keyring)
    return ("posix", *_stamp(written))


def _pg_snapshot(session, root):
    """Own actual snapshot descriptors/iterators; declarations are not handles."""
    entries, total = {}, 0

    def visit(resource, relative, depth):
        nonlocal total
        _pg_guard(session)
        _pg_require(depth <= 64, "SNAPSHOT_DEPTH")
        _pg_resource_current(resource)
        before = os.fstat(resource.owner)
        _pg_note(session, "directory-before", resource, before)
        _pg_resource_current(resource)
        stream = os.scandir(resource.owner)
        iterator = _pg_keep(session, stream, "scandir", "snapshot-directory", ("close", "__next__", "__iter__"))
        while True:
            _pg_guard(session)
            _pg_resource_current(iterator)
            try:
                entry = next(stream)
            except StopIteration:
                break
            _pg_resource_current(iterator)
            _pg_note(session, "scandir-entry", iterator, entry)
            _pg_require(len(entries) < MAX_MEMBERS and "\\" not in entry.name and
                not any(ord(char) < 32 or ord(char) == 127 for char in entry.name), "SNAPSHOT_NAME_OR_COUNT")
            name = relative + "/" + entry.name if relative else entry.name
            _pg_require(len(name.encode("utf-8")) <= 1024, "SNAPSHOT_NAME_BOUND")
            info = entry.stat(follow_symlinks=False)
            _pg_note(session, "entry-stat", entry, info)
            _pg_require(info.st_uid == os.getuid() and not info.st_mode & 0o022 and
                (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)), "SNAPSHOT_OWNERSHIP_OR_KIND")
            if stat.S_ISREG(info.st_mode):
                _pg_require(info.st_nlink == 1, "SNAPSHOT_HARDLINK")
                total += info.st_size
                _pg_require(total <= MAX_BYTES, "SNAPSHOT_BYTES")
            entries[name] = _stamp(info)
            _pg_guard(session)
            if stat.S_ISDIR(info.st_mode):
                _pg_resource_current(resource)
                child_fd = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=resource.owner)
                child = _pg_keep(session, child_fd, "descriptor", "snapshot-child")
                _pg_resource_current(child)
                actual = os.fstat(child_fd)
                _pg_note(session, "child-fstat", child, actual)
                _pg_require(_stamp(actual) == _stamp(info), "SNAPSHOT_DIRECTORY_CHANGED")
                visit(child, name, depth + 1)
                _pg_close(session, child)
        _pg_close(session, iterator)
        _pg_resource_current(resource)
        after = os.fstat(resource.owner)
        _pg_note(session, "directory-after", resource, after)
        _pg_require(_stamp(after) == _stamp(before), "SNAPSHOT_DIRECTORY_CHANGED")
        _pg_guard(session)

    _pg_guard(session)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    opened = _pg_keep(session, fd, "descriptor", "snapshot-root")
    _pg_resource_current(opened)
    original = os.fstat(fd)
    _pg_note(session, "root-fstat", opened, original)
    entries[""] = _stamp(original)
    visit(opened, "", 0)
    _pg_close(session, opened)
    _pg_note(session, "actual-snapshot-return", entries, tuple(entries.items()))
    _pg_state(session)["snapshots"].append((entries, entries, tuple(entries.items())))
    return entries


def _pg_member(session, root, name, snapshot):
    _pg_guard(session)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    parent = _pg_keep(session, fd, "descriptor", "member-root")
    _pg_require(_stamp(os.fstat(fd)) == snapshot[""], "MEMBER_ROOT_CHANGED")
    prefix = ""
    parts = name.split("/")
    for part in parts[:-1]:
        _pg_guard(session)
        _pg_resource_current(parent)
        child_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent.owner)
        child = _pg_keep(session, child_fd, "descriptor", "member-parent")
        _pg_close(session, parent)
        parent = child
        _pg_resource_current(parent)
        prefix = prefix + "/" + part if prefix else part
        _pg_require(_stamp(os.fstat(parent.owner)) == snapshot[prefix], "MEMBER_PARENT_CHANGED")
    _pg_guard(session)
    _pg_resource_current(parent)
    leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent.owner)
    descriptor = _pg_keep(session, leaf, "descriptor", "member-leaf")
    _pg_guard(session)
    _pg_resource_current(descriptor)
    _PRODUCTIVE_RESOURCES[id(descriptor)]["transfer_attempted"] = True
    handle = os.fdopen(leaf, "rb", buffering=0)
    resource = _pg_keep(session, handle, "file", "member-reader", ("close", "read", "fileno", "tell", "seek"))
    _PRODUCTIVE_RESOURCES[id(descriptor)]["transferred"] = resource
    _PRODUCTIVE_RESOURCES[id(resource)]["parent"] = descriptor
    actual = os.fstat(leaf)
    _pg_note(session, "member-fstat", resource, actual)
    _pg_require(_stamp(actual) == snapshot[name], "MEMBER_CHANGED")
    _pg_close(session, parent)
    _pg_resource_current(resource)
    return resource


def _pg_stream_register(stream, static, methods):
    state = _pg_state(stream.session)
    _pg_require(id(stream) not in _PRODUCTIVE_STREAMS, "STREAM_ALREADY_REGISTERED")
    row = {"stream": stream, "kind": type(stream), "dictionary": stream.__dict__,
        "fields": tuple(stream.__dict__), "static": tuple((name, getattr(stream, name)) for name in static),
        "session": stream.session, "resource": stream.resource, "methods": _pg_methods(stream, methods),
        "count": stream.count, "complete": False, "busy": False, "failure": None,
        "digest": getattr(stream, "digest", None), "hex": None}
    if row["digest"] is not None:
        row["digest_methods"] = _pg_methods(row["digest"], ("update", "hexdigest"))
        row["hex"] = row["digest"].hexdigest()
    _PRODUCTIVE_STREAMS[id(stream)] = row
    state["streams"].append(stream)
    _pg_stream_current(stream)


def _pg_stream_current(stream):
    row = _PRODUCTIVE_STREAMS.get(id(stream))
    _pg_require(type(row) is dict and row["stream"] is stream and row["failure"] is None and
        type(stream) is row["kind"] and stream.__dict__ is row["dictionary"] and
        tuple(stream.__dict__) == row["fields"] and all(getattr(stream, name) is original
            for name, original in row["static"]) and type(stream.count) is int and stream.count == row["count"] and
        stream.complete is row["complete"], "STREAM_CHANGED")
    for owner, methods in ((stream, row["methods"]), (row["digest"], row.get("digest_methods", ()))):
        _pg_methods_current(owner, methods, "STREAM_METHOD_CHANGED")
    if row["digest"] is not None:
        _pg_require(row["digest"].hexdigest() == row["hex"], "STREAM_DIGEST_CHANGED")
    _pg_resource_current(row["resource"])
    return row


def _pg_stream_begin(stream):
    row = _PRODUCTIVE_STREAMS.get(id(stream))
    _pg_require(type(row) is dict and row["stream"] is stream, "STREAM_NOT_ORIGINAL")
    state = _pg_state(row["session"])
    try:
        _pg_require(not row["busy"] and not row["complete"], "STREAM_REENTRY_OR_CLOSED")
        row["busy"] = True
        _pg_stream_current(stream)
        _pg_guard(row["session"])
        _pg_stream_current(stream)
        return row
    except BaseException as error:
        row["failure"] = row["failure"] or error
        raise _pg_fail(state, error)


def _pg_stream_failed(row, error):
    row["failure"] = row["failure"] or error
    return _pg_fail(_pg_state(row["session"]), error)


def _pg_tar_block(stream, row, count):
    session, resource, node, stamp = row["session"], row["resource"], stream.node, stream.stamp
    state = _pg_state(session)
    _pg_require(type(count) is int and 0 <= count <= MAX_BYTES, "TAR_READ_REQUEST")
    _pg_require(state["E"]._productive_node_guard(session.binding, node) is node, "TAR_ORIGINAL_NODE")
    _pg_guard(session)
    _pg_stream_current(stream)
    _pg_require(_stamp(os.fstat(resource.owner.fileno())) == stamp, "TAR_METADATA_BEFORE")
    block = resource.owner.read(count)
    _pg_stream_current(stream)
    _pg_require(type(block) is bytes and len(block) <= count and row["count"] + len(block) <= node.bytes,
        "TAR_READ_BYTES")
    row["digest"].update(block)
    row["hex"] = row["digest"].hexdigest()
    row["count"] += len(block)
    stream.count = row["count"]
    _pg_require(_stamp(os.fstat(resource.owner.fileno())) == stamp, "TAR_METADATA_AFTER")
    _pg_require(state["E"]._productive_node_guard(session.binding, node) is node, "TAR_ORIGINAL_NODE")
    _pg_guard(session)
    _pg_stream_current(stream)
    return block


class _ProductiveTarReader:
    """Hash exactly the bytes delivered to tar, including map/index streams."""
    def __init__(self, session, resource, node, stamp):
        self.session, self.resource, self.node, self.stamp = session, resource, node, stamp
        self.count, self.digest, self.complete = 0, hashlib.sha256(), False
        _pg_stream_register(self, ("session", "resource", "node", "stamp", "digest"), ("read", "finish"))

    def read(self, count):
        row = _pg_stream_begin(self)
        try:
            return _pg_tar_block(self, row, count)
        except BaseException as error:
            raise _pg_stream_failed(row, error)
        finally:
            row["busy"] = False

    def finish(self):
        row = _pg_stream_begin(self)
        try:
            _pg_require(_pg_tar_block(self, row, 1) == b"" and row["count"] == self.node.bytes and
                row["hex"] == self.node.sha256, "TAR_ACTUAL_BYTES_OR_EOF")
            _pg_note(row["session"], "tar-input-complete", self, row["resource"], self.node, row["count"], row["hex"])
            _pg_close(row["session"], row["resource"])
            _pg_stream_current(self)
            self.complete = row["complete"] = True
        except BaseException as error:
            raise _pg_stream_failed(row, error)
        finally:
            row["busy"] = False


class _ProductiveArchiveWriter:
    def __init__(self, session, resource):
        self.session, self.resource, self.count, self.complete = session, resource, 0, False
        _pg_stream_register(self, ("session", "resource"), ("write", "flush"))

    def write(self, data):
        row = _pg_stream_begin(self)
        try:
            _pg_require(type(data) is bytes and row["count"] + len(data) <= MAX_ARCHIVE_BYTES, "ARCHIVE_OUTPUT_BOUND")
            returned = row["resource"].owner.write(data)
            _pg_stream_current(self)
            _pg_require(type(returned) is int and returned == len(data), "ARCHIVE_SHORT_WRITE")
            row["count"] += returned
            self.count = row["count"]
            _pg_guard(row["session"])
            _pg_stream_current(self)
            return returned
        except BaseException as error:
            raise _pg_stream_failed(row, error)
        finally:
            row["busy"] = False

    def flush(self):
        row = _pg_stream_begin(self)
        try:
            row["resource"].owner.flush()
            _pg_guard(row["session"])
            _pg_stream_current(self)
        except BaseException as error:
            raise _pg_stream_failed(row, error)
        finally:
            row["busy"] = False


def _pg_archive(session, root, destination, snapshot):
    state = _pg_state(session)
    _pg_require(state["E"]._productive_whole_guard(session.binding) is state["caps"], "ARCHIVE_WHOLE_GUARD")
    raw, _info = _pg_open(session, destination, write=True)
    sink = _ProductiveArchiveWriter(session, raw)
    _pg_stream_current(sink)
    compressed = gzip.GzipFile(fileobj=sink, mode="wb", filename="", mtime=0)
    compressed_owner = _pg_keep(session, compressed, "gzip", "gzip", ("close", "write", "flush"))
    _PRODUCTIVE_RESOURCES[id(compressed_owner)]["links"] = ((compressed, "fileobj", sink), (compressed, "myfileobj", None))
    state["formats"].append(compressed_owner)
    _pg_guard(session)
    _pg_resource_current(compressed_owner)
    archive = tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT)
    # Retain the actual aggregate and nested return BEFORE any fallible
    # adoption/pinning. Keep the public factory's original format/buffering;
    # private _Stream constructor signatures differ between Python versions.
    state["pending_owners"].append(archive)
    native_stream = archive.fileobj
    state["pending_owners"].append(native_stream)
    _pg_require(type(archive) is tarfile.TarFile and type(native_stream) is tarfile._Stream and
        archive.fileobj is native_stream and native_stream.fileobj is compressed and
        archive.mode == native_stream.mode == "w" and native_stream.comptype == "tar" and
        archive.format == tarfile.PAX_FORMAT and archive._extfileobj is False and
        native_stream._extfileobj is True and archive.closed is False and native_stream.closed is False,
        "ORIGINAL_TAR_STREAM_OWNERSHIP")
    original_ownership = (archive._extfileobj, native_stream._extfileobj)
    archive._extfileobj = True  # One source-owned transfer, before any next callback.
    archive_owner = _pg_keep(session, archive, "format-writer", "tar", ("close", "addfile"))
    stream_owner = _pg_keep(session, native_stream, "tar-stream", "tar-stream", ("close", "write"))
    # Both owners now owe distinct original direct closes. In particular,
    # a TarFile.close padding callback cannot credit an early stream flag.
    _PRODUCTIVE_RESOURCES[id(stream_owner)]["links"] = tuple((native_stream, name, getattr(native_stream, name))
        for name in ("fileobj", "mode", "comptype", "bufsize", "_extfileobj"))
    _PRODUCTIVE_RESOURCES[id(archive_owner)]["links"] = tuple((archive, name, getattr(archive, name))
        for name in ("fileobj", "mode", "format", "_extfileobj"))
    state["formats"].extend((archive_owner, stream_owner))
    _pg_require(len(state["pending_owners"]) == 2 and state["pending_owners"][0] is archive and
        state["pending_owners"][1] is native_stream, "ORIGINAL_TAR_RETURNS_CHANGED")
    state["pending_owners"].clear()
    _pg_note(session, "original-tar-stream-direct-ownership-transfer", archive_owner, stream_owner, original_ownership)
    _pg_guard(session)
    for name, stamp in sorted(snapshot.items()):
        node = state["E"]._productive_expected_node(session.binding, name)
        _pg_require(state["E"]._productive_node_guard(session.binding, node) is node, "ARCHIVE_ORIGINAL_NODE")
        info = tarfile.TarInfo("evidence/" + name if name else "evidence")
        info.uid, info.gid, info.uname, info.gname, info.mtime = 0, 0, "", "", 0
        _pg_guard(session)
        _pg_resource_current(archive_owner)
        if stat.S_ISDIR(stamp[2]):
            info.type, info.mode = tarfile.DIRTYPE, 0o700
            archive.addfile(info)
        else:
            info.mode, info.size = 0o600, stamp[5]
            resource = _pg_member(session, root, name, snapshot)
            reader = _ProductiveTarReader(session, resource, node, stamp)
            _pg_note(session, "tar-input-owner", reader, resource, node, info)
            _pg_guard(session)
            _pg_resource_current(archive_owner)
            _pg_stream_current(reader)
            archive.addfile(info, reader)
            _pg_resource_current(archive_owner)
            reader.finish()
        _pg_guard(session)
        _pg_resource_current(archive_owner)
    # Tar padding and gzip trailers are guarded ordinary work, not cleanup
    # borrowing a receipt/finish allowance after the input reads have ended.
    _pg_close(session, archive_owner)
    _pg_close(session, stream_owner)
    _pg_close(session, compressed_owner)
    _pg_guard(session)
    _pg_resource_current(raw)
    raw.owner.flush()
    _pg_guard(session)
    _pg_resource_current(raw)
    os.fsync(raw.owner.fileno())
    _pg_guard(session)
    _pg_resource_current(raw)
    actual = os.fstat(raw.owner.fileno())
    _pg_note(session, "archive-fstat", raw, actual)
    _pg_require(actual.st_size == sink.count, "ARCHIVE_WRITTEN_SIZE")
    _pg_close(session, raw)
    row = _pg_stream_current(sink)
    sink.complete = row["complete"] = True
    _pg_require(state["E"]._productive_whole_guard(session.binding) is state["caps"], "ARCHIVE_RETURN_GUARD")


def _pg_gpg(session, recipient, arguments, *, output=None, status=False, keyring=None):
    """The maintained command/spawn, retaining its actual process before return.

    A direct-child wait is NOT native scope retirement; the enclosing original
    child/parent domain must still prove baseline/quiet/ACK/known-close custody.
    """
    state = _pg_state(session)
    _pg_guard(session, keyring=keyring)
    environment = _gpg_environment(recipient)
    _pg_require(type(environment) is dict and all(type(name) is str and type(value) is str
        for name, value in environment.items()), "GPG_ENVIRONMENT_FIELDS")
    state["environments"].append((environment, tuple(environment.items())))
    _pg_require(environment.get(audit_processes.JOB_ENV) == state["validation_view"].source.job_id,
        "GPG_ENCLOSING_JOB_REQUIRED")
    _pg_guard(session, keyring=keyring)
    operation = Path(tempfile.mkdtemp(prefix="gpg-", dir=recipient.work_dir))
    _pg_note(session, "gpg-operation-created", operation, operation.lstat())
    _pg_directory(session, operation, empty=True, keyring=keyring)
    stdout_path = output if output is not None else operation / "stdout"
    stderr_path, status_path = operation / "stderr", operation / "status"
    out, _ = _pg_open(session, stdout_path, write=True, keyring=keyring)
    err, _ = _pg_open(session, stderr_path, write=True, keyring=keyring)
    status_file, _ = _pg_open(session, status_path, write=True, keyring=keyring)
    command = _gpg_command(recipient)
    if status:
        _pg_resource_current(status_file)
        command += ["--status-fd", str(status_file.owner.fileno())]
        _pg_resource_current(status_file)
    command += arguments
    _pg_require(type(command) is list and all(type(value) is str for value in command) and
        type(environment) is dict and all(type(name) is str and type(value) is str
            for name, value in environment.items()), "GPG_COMMAND_FIELDS")
    state["commands"].append((command, tuple(command), environment, tuple(environment.items())))
    _pg_guard(session, keyring=keyring)
    for item in (out, err, status_file):
        _pg_resource_current(item)
    process = _spawn_gpg(command, recipient, environment, out.owner, err.owner, status_file.owner, status)
    resource = _pg_keep(session, process, "process", "gpg", ("poll", "wait", "terminate", "kill"))
    state["pending_process"] = resource
    _pg_require(process.args is command and type(process.pid) is int and process.pid > 0, "GPG_ACTUAL_PROCESS")
    _PRODUCTIVE_RESOURCES[id(resource)]["links"] = ((process, "args", command), (process, "pid", process.pid))
    _pg_note(session, "actual-spawn-return", resource, command, process.pid)
    while True:
        _pg_guard(session, keyring=keyring)
        _pg_resource_current(resource)
        code = process.poll()
        _pg_note(session, "actual-process-poll", resource, code)
        _pg_require(code is None or type(code) is int, "GPG_POLL_RETURN")
        _pg_resource_current(resource)
        sizes = []
        for item in (out, err, status_file):
            _pg_resource_current(item)
            sizes.append(os.fstat(item.owner.fileno()).st_size)
            _pg_resource_current(item)
        _pg_require(sizes[0] <= (MAX_CIPHERTEXT_BYTES if output is not None else MAX_DIAGNOSTIC_BYTES) and
            sizes[1] <= MAX_DIAGNOSTIC_BYTES and sizes[2] <= MAX_DIAGNOSTIC_BYTES, "GPG_OUTPUT_BOUND")
        _pg_guard(session, keyring=keyring)
        if code is not None:
            break
        time.sleep(0.025)
    row = _pg_resource_current(resource)
    row["attempted"] = True
    returned = process.wait()
    row["return_fact"] = ("DIRECT_CHILD_WAIT_RETURN", returned)
    _pg_note(session, "actual-direct-child-wait-return", resource, returned)
    _pg_require(type(returned) is int and returned == code == 0, "GPG_NATURAL_EXIT")
    completion = _pg_guard(session, keyring=keyring)
    _pg_closed(session, resource, "DIRECT_CHILD_WAIT_ONLY_PARENT_OWNS_DOMAIN", returned, completion)
    state["pending_process"] = None
    for item in (out, err, status_file):
        _pg_guard(session, keyring=keyring)
        _pg_resource_current(item)
        item.owner.flush()
        _pg_guard(session, keyring=keyring)
        _pg_resource_current(item)
        os.fsync(item.owner.fileno())
        _pg_close(session, item, keyring=keyring)
    record = (json.dumps({"schema": 1, "waitExitCode": returned, "retired": True, "interruption": None},
        sort_keys=True) + "\n").encode("ascii")
    _pg_write(session, operation / "process.json", record, MAX_DIAGNOSTIC_BYTES, keyring=keyring)
    readback, _ = _pg_read(session, operation / "process.json", MAX_DIAGNOSTIC_BYTES, keyring=keyring)
    _pg_require(readback == record, "GPG_PROCESS_RECORD_READBACK")
    # The original stderr remains private even on successful completion.
    _pg_read(session, stderr_path, MAX_DIAGNOSTIC_BYTES, keyring=keyring)
    stdout = b"" if output is not None else _pg_read(session, stdout_path, MAX_DIAGNOSTIC_BYTES, keyring=keyring)[0]
    status_raw, _ = _pg_read(session, status_path, MAX_DIAGNOSTIC_BYTES, keyring=keyring)
    _pg_guard(session, keyring=keyring)
    return stdout, status_raw


def _pg_directory(session, path, *, empty=False, identity=None, keyring=None):
    """Own the actual verification descriptor and optional enumeration handle."""
    _pg_guard(session, keyring=keyring)
    checked = _private_directory(path)
    _pg_require(str(checked) == str(path), "DIRECTORY_PATH_CHANGED")
    _pg_guard(session, keyring=keyring)
    before = path.lstat()
    _pg_note(session, "directory-path-stat", path, before)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    resource = _pg_keep(session, fd, "descriptor", "verified-directory")
    actual = os.fstat(fd)
    _pg_note(session, "verified-directory-fstat", resource, actual)
    _pg_require(_stamp(actual) == _stamp(before) and
        (identity is None or (actual.st_dev, actual.st_ino) == identity), "DIRECTORY_IDENTITY_CHANGED")
    _pg_guard(session, keyring=keyring)
    if empty:
        _pg_resource_current(resource)
        iterator = os.scandir(fd)
        enumeration = _pg_keep(session, iterator, "scandir", "new-empty-directory", ("close", "__next__", "__iter__"))
        _pg_resource_current(enumeration)
        try:
            entry = next(iterator)
        except StopIteration:
            entry = None
        _pg_note(session, "new-directory-enumeration", enumeration, entry)
        _pg_require(entry is None, "DIRECTORY_NOT_EMPTY")
        _pg_close(session, enumeration, keyring=keyring)
    _pg_resource_current(resource)
    _pg_require(_stamp(os.fstat(fd)) == _stamp(before) and _stamp(path.lstat()) == _stamp(before),
        "DIRECTORY_VERIFICATION_CHANGED")
    _pg_close(session, resource, keyring=keyring)
    return actual


def _pg_retain_recipient(session, recipient):
    state = _pg_state(session)
    _pg_require(type(recipient) is Recipient, "RECIPIENT_TYPE")
    paths = tuple((path, type(path), str(path)) for path in
        (recipient.work_dir, recipient.home, recipient.executable))
    state["recipients"].append((recipient, _pg_pin(recipient), paths))


def _validate_initial_productive(binding):
    """One registered child validation using the maintained public-only backend."""
    session = _pg_new(binding, "validation")
    state, view = _pg_state(session), binding.view
    state["validation_view"] = view
    try:
        work = view.work  # SAME borrowed concrete PosixPath, not a reconstructed owner.
        identity = _pg_directory(session, work, empty=True)
        _pg_guard(session)
        policy = json.loads(view.policy_raw)  # E has already authenticated these SAME original bytes.
        fingerprint = policy["recipient"]["fingerprint"]
        _pg_require(type(fingerprint) is str and re.fullmatch(r"[0-9A-F]{40}", fingerprint), "POLICY_FINGERPRINT")
        packets = _public_armor(view.public_key_raw)
        _pg_guard(session)
        installed = shutil.which("gpg")
        _pg_require(installed is not None, "INSTALLED_GPG_REQUIRED")
        executable = Path(installed).resolve(strict=True)
        _pg_require(executable.is_file() and os.access(executable, os.X_OK), "INSTALLED_GPG_UNAVAILABLE")
        _pg_guard(session)
        home = work / "gnupg"
        for directory in (home, work / "tmp"):
            _pg_guard(session)
            returned = directory.mkdir(mode=0o700)
            _pg_note(session, "actual-mkdir-return", directory, returned)
            _pg_directory(session, directory, empty=True)
        for name, raw in (("recipient.asc", view.public_key_raw), ("recipient.gpg", packets)):
            native = _pg_write(session, work / name, raw, MAX_KEY_BYTES)
            actual, read_native = _pg_read(session, work / name, MAX_KEY_BYTES)
            _pg_require(actual == raw and read_native == native, "PUBLIC_KEY_COPY_READBACK")
        provisional = Recipient(work, home, executable, fingerprint, "", 0,
            hashlib.sha256(view.public_key_raw).hexdigest(), (identity.st_dev, identity.st_ino))
        _pg_retain_recipient(session, provisional)
        common = ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint"]
        shown, _ = _pg_gpg(session, provisional, common + ["--import-options", "show-only", "--import",
            str(work / "recipient.asc")])
        encryption_fingerprint, expires_at = _key_identity(shown, fingerprint)
        _pg_guard(session)
        selected, _ = _pg_gpg(session, provisional, common + ["--list-keys"])
        _pg_require(_key_identity(selected, fingerprint) == (encryption_fingerprint, expires_at),
            "PUBLIC_KEY_SELECTION_CHANGED")
        recipient = dataclasses.replace(provisional, encryption_fingerprint=encryption_fingerprint, expires_at=expires_at)
        _pg_retain_recipient(session, recipient)
        _pg_directory(session, work, identity=provisional.work_identity)
        known = _finish_initial_productive(session, binding)
        result = _ProductiveValidationReturn(binding, session, recipient, known.observations, known)
        _pg_register_result(session, result)
        _PRODUCTIVE_RECIPIENTS[id(recipient)] = result
        return _checked_productive_validation_return(result, binding)
    except BaseException as error:
        _pg_abort(session, error)
        raise state["failure"]


class _ProductiveCipherReader:
    """The pathless maintained packet parser receives a guarded original stream."""
    def __init__(self, session, resource, stamp):
        self.session, self.resource, self.stamp = session, resource, stamp
        self.size, self.count, self.complete = stamp[5], 0, False
        _pg_stream_register(self, ("session", "resource", "stamp", "size"), ("read", "seek", "tell"))

    def _current(self, row):
        _pg_stream_current(self)
        _pg_require(_stamp(os.fstat(row["resource"].owner.fileno())) == self.stamp and
            row["resource"].owner.tell() == row["count"], "CIPHERTEXT_NATIVE_CHANGED")

    def read(self, count):
        row = _pg_stream_begin(self)
        try:
            _pg_require(type(count) is int and 0 <= count <= MAX_CIPHERTEXT_BYTES, "CIPHERTEXT_READ_BOUND")
            self._current(row)
            raw = row["resource"].owner.read(count)
            _pg_stream_current(self)
            _pg_require(type(raw) is bytes and len(raw) <= count and row["count"] + len(raw) <= self.size,
                "CIPHERTEXT_READ_CHANGED")
            row["count"] += len(raw)
            self.count = row["count"]
            _pg_guard(row["session"])
            self._current(row)
            return raw
        except BaseException as error:
            raise _pg_stream_failed(row, error)
        finally:
            row["busy"] = False

    def seek(self, offset, whence=os.SEEK_SET):
        row = _pg_stream_begin(self)
        try:
            _pg_require(type(offset) is int and type(whence) is int and whence in (os.SEEK_SET, os.SEEK_CUR),
                "CIPHERTEXT_SEEK")
            self._current(row)
            expected = offset if whence == os.SEEK_SET else row["count"] + offset
            _pg_require(0 <= expected <= self.size, "CIPHERTEXT_SEEK_BOUND")
            returned = row["resource"].owner.seek(offset, whence)
            _pg_stream_current(self)
            _pg_require(type(returned) is int and returned == expected, "CIPHERTEXT_SEEK_RETURN")
            self.count = row["count"] = returned
            _pg_guard(row["session"])
            self._current(row)
            return returned
        except BaseException as error:
            raise _pg_stream_failed(row, error)
        finally:
            row["busy"] = False

    def tell(self):
        row = _pg_stream_begin(self)
        try:
            self._current(row)
            _pg_guard(row["session"])
            self._current(row)
            return row["count"]
        except BaseException as error:
            raise _pg_stream_failed(row, error)
        finally:
            row["busy"] = False


def _pg_ciphertext(session, path, recipient, *, expected=None):
    resource, original = _pg_open(session, path)
    native = ("posix", *_stamp(original))
    _pg_require(expected is None or native == expected, "CIPHERTEXT_SOURCE_CHANGED")
    reader = _ProductiveCipherReader(session, resource, _stamp(original))
    _pg_note(session, "ciphertext-reader", reader, resource, original)
    _ciphertext_stream(reader, original.st_size, recipient.encryption_fingerprint)
    reader.seek(0)
    digest, count = hashlib.sha256(), 0
    while True:
        raw = reader.read(1024 * 1024)
        if not raw:
            break
        count += len(raw)
        digest.update(raw)
    _pg_require(count == original.st_size and _stamp(path.lstat()) == _stamp(original), "CIPHERTEXT_COMPLETE_READBACK")
    _pg_note(session, "ciphertext-shape-hash-return", reader, resource, digest.hexdigest(), count, native)
    _pg_close(session, resource)
    row = _pg_stream_current(reader)
    reader.complete = row["complete"] = True
    return digest.hexdigest(), count, native


def _pg_publish(session, ciphertext, recipient, manifest_raw, digest, size, native):
    state, view = _pg_state(session), session.binding.view
    _pg_require(state["E"]._productive_whole_guard(session.binding) is state["caps"], "PUBLICATION_WHOLE_GUARD")
    _pg_guard(session)
    _path(view.output)
    _pg_directory(session, view.output.parent)
    _pg_require(not os.path.lexists(view.output), "EXISTING_OUTPUT")
    _pg_guard(session)
    returned = view.output.mkdir(mode=0o700)
    # Retain the exclusive reservation immediately. A failed later check is
    # NOT permission to delete some other invocation's directory or evidence.
    created = view.output.lstat()
    state["output"] = (view.output, created)
    _pg_note(session, "actual-output-mkdir-return", view.output, returned, created)
    _pg_directory(session, view.output, empty=True, identity=(created.st_dev, created.st_ino))
    source, original = _pg_open(session, ciphertext)
    _pg_require(("posix", *_stamp(original)) == native, "PUBLICATION_PRIVATE_NATIVE_CHANGED")
    target, _ = _pg_open(session, view.output / ARTIFACT, write=True)
    reader = _ProductiveCipherReader(session, source, _stamp(original))
    joined, count = hashlib.sha256(), 0
    while True:
        block = reader.read(1024 * 1024)
        if not block:
            break
        _pg_guard(session)
        _pg_resource_current(target)
        returned = target.owner.write(block)
        _pg_require(type(returned) is int and returned == len(block), "PUBLICATION_SHORT_WRITE")
        _pg_guard(session)
        _pg_resource_current(target)
        joined.update(block)
        count += len(block)
    _pg_require(count == size and joined.hexdigest() == digest, "PUBLICATION_SOURCE_STREAM_CHANGED")
    _pg_note(session, "publication-actual-copy-return", source, target, count, joined.hexdigest())
    _pg_guard(session)
    _pg_resource_current(target)
    target.owner.flush()
    _pg_guard(session)
    _pg_resource_current(target)
    os.fsync(target.owner.fileno())
    _pg_guard(session)
    _pg_close(session, target)
    _pg_close(session, source)
    row = _pg_stream_current(reader)
    reader.complete = row["complete"] = True
    _pg_write(session, view.output / MANIFEST, manifest_raw, 64 * 1024)
    actual_digest, actual_size, actual_native = _pg_ciphertext(session, view.output / ARTIFACT, recipient)
    actual_manifest, manifest_native = _pg_read(session, view.output / MANIFEST, 64 * 1024)
    _pg_require(actual_digest == digest and actual_size == size and actual_manifest == manifest_raw,
        "PUBLICATION_INDEPENDENT_READBACK_CHANGED")
    _pg_output_roster(session, actual_native, manifest_native)
    state["public_native"] = (actual_native, manifest_native)
    _pg_directory(session, view.output, identity=(created.st_dev, created.st_ino))
    return _ProductiveArtifact(ARTIFACT, actual_digest, actual_size, actual_native)


def _pg_output_roster(session, artifact_native, manifest_native):
    # The public ciphertext has its existing576MiB cap, NOT the512MiB
    # plaintext-snapshot cap. This separate EXACT two-file roster does not
    # widen or repurpose the input snapshot or its10,000-member bound.
    state = _pg_state(session)
    output, created = state["output"]
    _pg_guard(session)
    fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directory = _pg_keep(session, fd, "descriptor", "public-roster-root")
    before = os.fstat(fd)
    _pg_require((before.st_dev, before.st_ino) == (created.st_dev, created.st_ino) and
        stat.S_ISDIR(before.st_mode) and before.st_uid == os.getuid() and not before.st_mode & 0o077,
        "PUBLIC_OUTPUT_ROOT_CHANGED")
    _pg_guard(session)
    _pg_resource_current(directory)
    iterator = os.scandir(fd)
    enumeration = _pg_keep(session, iterator, "scandir", "public-roster", ("close", "__next__", "__iter__"))
    found, expected = {}, {ARTIFACT: artifact_native, MANIFEST: manifest_native}
    while True:
        _pg_guard(session)
        _pg_resource_current(enumeration)
        try:
            entry = next(iterator)
        except StopIteration:
            break
        _pg_require(entry.name in expected and entry.name not in found, "PUBLIC_OUTPUT_ROSTER")
        info = entry.stat(follow_symlinks=False)
        native = ("posix", *_stamp(info))
        _pg_note(session, "public-output-entry", entry, info)
        _pg_require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
            not info.st_mode & 0o077 and native == expected[entry.name], "PUBLIC_OUTPUT_NATIVE_CHANGED")
        found[entry.name] = native
    _pg_resource_current(directory)
    _pg_require(set(found) == set(expected) and _stamp(os.fstat(fd)) == _stamp(before) and
        _stamp(output.lstat()) == _stamp(before), "PUBLIC_OUTPUT_FINAL_ROSTER")
    _pg_close(session, enumeration)
    _pg_close(session, directory)
    _pg_note(session, "public-output-roster-return", tuple(found.items()), before)


def _export_initial_productive(binding):
    """Only a genuine E/PC child archive, never paths or an ordinary-CI fallback."""
    session = _pg_new(binding, "export")
    state, view = _pg_state(session), binding.view
    try:
        recipient = view.recipient
        validation = _PRODUCTIVE_RECIPIENTS.get(id(recipient))
        _pg_require(type(validation) is _ProductiveValidationReturn and validation.recipient is recipient and
            validation.binding.view.child is view.child, "ORIGINAL_RECIPIENT_RETURN_REQUIRED")
        _pg_require(_checked_productive_validation_return(validation, validation.binding) is validation,
            "ORIGINAL_RECIPIENT_RETURN_CHANGED")
        state["validation_result"], state["validation_view"] = validation, validation.binding.view
        _pg_retain_recipient(session, recipient)
        _pg_directory(session, view.payload)
        _pg_directory(session, recipient.work_dir, identity=recipient.work_identity)
        _pg_directory(session, recipient.home)
        _disjoint(view.payload, recipient.work_dir, view.output)
        key, _ = _pg_read(session, recipient.work_dir / "recipient.asc", MAX_KEY_BYTES)
        ring, _ = _pg_read(session, recipient.work_dir / "recipient.gpg", MAX_KEY_BYTES)
        _pg_require(hashlib.sha256(key).hexdigest() == recipient.key_sha256 and _public_armor(key) == ring,
            "RECIPIENT_ORIGINAL_BYTES_CHANGED")
        first_resource = state["resource_count"]
        cap = state["E"]._productive_keyring_begin(binding)
        state["active_keyring"] = cap
        listing, _ = _pg_gpg(session, recipient, ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint",
            "--list-keys"], keyring=cap)
        _pg_require(_key_identity(listing, recipient.fingerprint) ==
            (recipient.encryption_fingerprint, recipient.expires_at), "RECIPIENT_KEYRING_CHANGED")
        _pg_guard(session, keyring=cap)
        for resource in state["resources"][first_resource:]:
            row = _pg_resource_current(resource)
            _pg_require(row["keyring"] is cap and row["close"] is not None and
                row["close"].completion[0] is cap, "KEYRING_ORIGINAL_RESOURCE_CLOSE")
        _pg_require(state["E"]._productive_keyring_complete(binding, cap) is cap, "KEYRING_COMPLETION_CHANGED")
        state["active_keyring"] = None
        _pg_guard(session)
        snapshot = _pg_snapshot(session, view.payload)
        state["E"]._productive_check_snapshot(binding, snapshot)
        _pg_guard(session)
        private = Path(tempfile.mkdtemp(prefix="export-", dir=recipient.work_dir))
        created = private.lstat()
        state["private"] = (private, created)
        _pg_note(session, "actual-private-directory", private, created)
        _pg_directory(session, private, empty=True)
        plaintext, ciphertext = private / "evidence.tar.gz", private / ARTIFACT
        _pg_archive(session, view.payload, plaintext, snapshot)
        after = _pg_snapshot(session, view.payload)
        state["E"]._productive_check_snapshot(binding, after)
        _pg_require(after == snapshot, "ARCHIVE_SNAPSHOT_CHANGED")
        _, status = _pg_gpg(session, recipient, ["--cipher-algo", "AES256", "--compress-algo", "none",
            "--trust-model", "always", "--no-encrypt-to", "--recipient", recipient.encryption_fingerprint + "!",
            "--output", "-", "--encrypt", str(plaintext)], output=ciphertext, status=True)
        lines = status.splitlines()
        _pg_require(sum(line.startswith(b"[GNUPG:] BEGIN_ENCRYPTION ") for line in lines) == 1 and
            lines.count(b"[GNUPG:] END_ENCRYPTION") == 1 and not any(line.startswith(
                (b"[GNUPG:] FAILURE", b"[GNUPG:] ERROR")) for line in lines), "GPG_ENCRYPTION_NOT_COMPLETE")
        digest, size, native = _pg_ciphertext(session, ciphertext, recipient)
        manifest_raw = state["E"]._productive_manifest(binding, digest, size)
        _pg_require(type(manifest_raw) is bytes and 0 < len(manifest_raw) <= 64 * 1024, "MANIFEST_BYTES")
        artifact = _pg_publish(session, ciphertext, recipient, manifest_raw, digest, size, native)
        state["artifact_pin"] = _pg_pin(artifact)
        final = _pg_snapshot(session, view.payload)
        state["E"]._productive_check_snapshot(binding, final)
        _pg_require(final == snapshot, "FINAL_SNAPSHOT_CHANGED")
        _pg_require(state["E"]._productive_whole_guard(binding) is state["caps"], "EXPORT_FINAL_WHOLE_GUARD")
        known = _finish_initial_productive(session, binding)
        result = _ProductiveExportReturn(binding, session, manifest_raw, artifact, known.observations, known)
        _pg_register_result(session, result)
        return _checked_productive_export_return(result, binding)
    except BaseException as error:
        _pg_abort(session, error)
        raise state["failure"]


def _pg_cleanup(session):
    state = _pg_state(session)
    _pg_require(state["mode"] == "export" and state["private"] is not None and
        not state.get("cleanup_attempted", False), "TRANSIENT_CLEANUP_ONCE")
    state["cleanup_attempted"] = True
    private, created = state["private"]
    _pg_directory(session, private, identity=(created.st_dev, created.st_ino))
    for name in ("evidence.tar.gz", ARTIFACT):
        written = state["written"].get(str(private / name))
        _pg_require(type(written) is tuple, "TRANSIENT_NOT_OWNED")
        path, _initial, resource = written
        row = _pg_resource_current(resource)
        _pg_require(row["close"] is not None and resource.owner.closed is True and "last_stat" in row,
            "TRANSIENT_WRITER_NOT_CLOSED")
        _pg_guard(session)
        current = path.lstat()
        _pg_note(session, "transient-before-unlink", path, current)
        _pg_require(_stamp(current) == _stamp(row["last_stat"]) and stat.S_ISREG(current.st_mode) and
            current.st_uid == os.getuid() and current.st_nlink == 1, "TRANSIENT_IDENTITY_CHANGED")
        _pg_guard(session)
        _pg_require(str(path) not in state["removal_attempts"], "TRANSIENT_UNLINK_ONCE")
        state["removal_attempts"].add(str(path))
        returned = os.unlink(path)
        _pg_note(session, "actual-transient-unlink-return", path, returned)
        _pg_guard(session)
        _pg_require(not os.path.lexists(path), "TRANSIENT_UNLINK_NOT_OBSERVED")
    _pg_directory(session, private, empty=True, identity=(created.st_dev, created.st_ino))
    _pg_guard(session)
    _pg_require(str(private) not in state["removal_attempts"], "TRANSIENT_RMDIR_ONCE")
    state["removal_attempts"].add(str(private))
    returned = os.rmdir(private)
    observation = _pg_note(session, "actual-transient-rmdir-return", private, returned)
    _pg_guard(session)
    _pg_require(not os.path.lexists(private), "TRANSIENT_RMDIR_NOT_OBSERVED")
    state["cleanup_return"] = observation


def _pg_abort_files(session):
    """Preserve normal exclusive transient/output cleanup after KNOWN closure.

    No cleanup of caller inputs, diagnostics, keys, a replaced inode, an
    attempted removal, or material potentially used by an unretired child.
    This failure-only cleanup cannot register successful custody.
    """
    state = _pg_state(session)
    if state["unknown"] or state["pending_process"] is not None or state["pending_owners"]:
        return
    for saved, names in ((state["output"], (MANIFEST, ARTIFACT)),
            (state["private"], ("evidence.tar.gz", ARTIFACT))):
        if saved is None:
            continue
        directory, created = saved
        if str(directory) in state["removal_attempts"]:
            continue
        _pg_require(time.monotonic() < state["caps"].operationFinishEndLocal, "FAILED_CLEANUP_EXPIRED")
        info = directory.lstat()
        _pg_require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077 and
            (info.st_dev, info.st_ino) == (created.st_dev, created.st_ino), "FAILED_CLEANUP_DIRECTORY_CHANGED")
        for name in names:
            path = directory / name
            if str(path) in state["removal_attempts"]:
                continue
            written = state["written"].get(str(path))
            if written is None:
                continue  # No declaration can authorize unlink of an unowned file.
            _path(path)
            row = _pg_resource_current(written[2])
            _pg_require(row["attempted"] and row["return_fact"] is not None and
                row["resource"].owner.closed is True and "last_stat" in row, "FAILED_CLEANUP_WRITER_NOT_CLOSED")
            current = path.lstat()
            _pg_require(_stamp(current) == _stamp(row["last_stat"]) and stat.S_ISREG(current.st_mode) and
                current.st_uid == os.getuid() and current.st_nlink == 1, "FAILED_CLEANUP_FILE_CHANGED")
            _pg_require(time.monotonic() < state["caps"].operationFinishEndLocal, "FAILED_CLEANUP_EXPIRED")
            state["removal_attempts"].add(str(path))
            returned = os.unlink(path)
            _pg_note(session, "failure-only-unlink-return", path, returned)
        current = directory.lstat()
        _pg_require((current.st_dev, current.st_ino) == (created.st_dev, created.st_ino) and
            stat.S_ISDIR(current.st_mode) and time.monotonic() < state["caps"].operationFinishEndLocal,
            "FAILED_CLEANUP_DIRECTORY_CHANGED")
        state["removal_attempts"].add(str(directory))
        returned = os.rmdir(directory)  # Also refuses extra/unowned members, with no recursive deletion.
        _pg_note(session, "failure-only-rmdir-return", directory, returned)


def _pg_abort(session, original_error):
    """Failure-only owned cleanup: no trailers, new receipt, publication or retry.

    Unknown/attempted closes stay quarantined. The original enclosing native
    owner still owes full process-tree retirement; a Popen wait is not that
    proof. Failure cleanup can never create a successful registered result.
    """
    state = _pg_state(session)
    _pg_fail(state, original_error)
    if state.get("abort_attempted", False):
        return
    state["abort_attempted"], state["phase"] = True, "FAILED"
    if not all(getattr(owner, name, None) is original for owner, name, original in state["functions"]):
        state["unknown"] = True
        _PRODUCTIVE_QUARANTINE.append(session)
        return
    pending = state["pending_process"]
    if pending is not None:
        try:
            row = _pg_resource_current(pending)
            if row["attempted"]:
                # The original wait already ran. Retain its actual return or
                # uncertainty; never call it a second time to manufacture proof.
                if row["return_fact"] is None:
                    state["unknown"] = True
            else:
                process = pending.owner
                methods = {item[0]: item[2] for item in pending.methods}
                code = methods["poll"]()
                _pg_resource_current(pending)
                _pg_note(session, "failure-only-poll-return", pending, code)
                if code is None:
                    methods["terminate"]()
                    _pg_resource_current(pending)
                    methods["kill"]()
                _pg_resource_current(pending)
                # A single cleanup wait, clipped to the ORIGINAL absolute end
                # and the existing direct-child five-second bound. No new cap.
                remaining = max(0.0, min(5.0, state["caps"].operationFinishEndLocal - time.monotonic()))
                row["attempted"] = True
                returned = methods["wait"](timeout=remaining)
                row["return_fact"] = ("FAILED_OPERATION_DIRECT_CHILD_WAIT_RETURN", returned)
                _pg_note(session, "failure-only-direct-wait-return", pending, returned)
        except BaseException:
            state["unknown"] = True
    for resource in reversed(state["resources"]):
        try:
            row = _pg_resource_current(resource)
            if row["attempted"] or row["transferred"] is not None:
                if row["attempted"] and row["return_fact"] is None:
                    state["unknown"] = True
                continue
            if resource.kind not in ("descriptor", "file", "scandir") or row["transfer_attempted"]:
                # Closing tar/gzip after expiry writes padding/trailers. Keep
                # those actual objects alive, close only owned underlying I/O.
                _PRODUCTIVE_QUARANTINE.append(resource)
                if row["transfer_attempted"]:
                    state["unknown"] = True
                continue
            if resource.kind == "file":
                row["last_stat"] = os.fstat(resource.owner.fileno())
            row["attempted"] = True
            if resource.kind == "descriptor":
                returned = os.close(resource.owner)
            else:
                returned = next(item[2] for item in resource.methods if item[0] == "close")()
            row["return_fact"] = ("FAILURE_ONLY_CLOSE_RETURN", returned)
            _pg_note(session, "failure-only-close-return", resource, returned)
        except BaseException:
            state["unknown"] = True
            _PRODUCTIVE_QUARANTINE.append(resource)
    try:
        _pg_abort_files(session)
    except BaseException:
        state["unknown"] = True
    _PRODUCTIVE_QUARANTINE.append(session)


def _finish_initial_productive(session, binding):
    state = _pg_state(session)
    try:
        _pg_require(session.binding is binding and state["phase"] == "WORK" and
            not state["finish_attempted"] and state["finish"] is None, "FINISH_ONCE")
        state["finish_attempted"] = True  # Before callbacks/reentry, not a known close.
        _pg_guard(session)
        if state["mode"] == "export":
            _pg_cleanup(session)
            _pg_output_roster(session, *state["public_native"])
        _pg_passive(state, whole=True)
        _pg_require(state["pending_process"] is None and state["active_keyring"] is None, "UNFINISHED_PROCESS_OR_KEYRING")
        for resource in state["resources"]:
            row = _pg_resource_current(resource)
            _pg_require(row["attempted"] and row["close"] is not None and row["return_fact"] is not None,
                "NATIVE_CLOSE_NOT_KNOWN")
            if resource.kind in ("file", "format-writer", "tar-stream"):
                _pg_require(resource.owner.closed is True, "NATIVE_RESOURCE_NOT_CLOSED")
            if resource.kind == "gzip":
                _pg_require(resource.owner.fileobj is None, "GZIP_NOT_CLOSED")
            if resource.kind == "process":
                _pg_require(type(resource.owner.returncode) is int and resource.owner.returncode == row["close"].returned == 0,
                    "PROCESS_WAIT_CHANGED")
        _pg_require(all(_pg_stream_current(stream)["complete"] for stream in state["streams"]), "STREAM_NOT_COMPLETE")
        completion = _pg_guard(session)
        known = _ProductiveKnownClose(session, tuple(state["resources"]), tuple(state["observations"]), completion)
        rows = tuple((row, tuple(row.items())) for resource in state["resources"]
            for row in (_PRODUCTIVE_RESOURCES[id(resource)],))
        _PRODUCTIVE_FINISHES[id(known)] = (known, state, _pg_pin(known), rows)
        state["finish"], state["phase"] = known, "CLOSED"
        return known
    except BaseException as error:
        raise _pg_fail(state, error)


def _pg_register_result(session, result):
    state = _pg_state(session)
    _pg_require(state["phase"] == "CLOSED" and state["result"] is None and result.session is session and
        result.binding is session.binding and result.known_close is state["finish"] and
        result.observations is state["finish"].observations, "RESULT_ORIGINAL_CLOSE_REQUIRED")
    state["result"] = result
    _PRODUCTIVE_RESULTS[id(result)] = (result, state, _pg_pin(result))


def _pg_checked_result(result, binding, mode):
    """Strictly passive original-return check. No clock, root reopen or E call."""
    registration = _PRODUCTIVE_RESULTS.get(id(result))
    kind = _ProductiveValidationReturn if mode == "validation" else _ProductiveExportReturn
    _pg_require(type(result) is kind and type(registration) is tuple and registration[0] is result,
        "RESULT_NOT_ORIGINAL")
    state = registration[1]
    try:
        _pg_require(state["mode"] == mode and state["result"] is result and result.binding is binding and
            result.session is state["session"] and state["session"].binding is binding and state["phase"] == "CLOSED",
            "RESULT_BINDING_CHANGED")
        _pg_passive(state, whole=True)
        _pg_pin_current(registration[2])
        known = state["finish"]
        original = _PRODUCTIVE_FINISHES.get(id(known))
        _pg_require(type(original) is tuple and original[0] is known and original[1] is state and
            result.known_close is known and known.session is result.session and result.observations is known.observations and
            len(known.resources) == len(state["resources"]) and
            all(left is right for left, right in zip(known.resources, state["resources"])) and
            len(known.observations) == len(state["observations"]) and
            all(left is right for left, right in zip(known.observations, state["observations"])), "KNOWN_CLOSE_CHANGED")
        _pg_pin_current(original[2])
        for row, fields in original[3]:
            _pg_require(set(row) == {name for name, _ in fields} and all(row[name] is value for name, value in fields),
                "ORIGINAL_RESOURCE_CLOSE_CHANGED")
        if mode == "validation":
            _pg_require(any(recipient is result.recipient for recipient, _pin, _paths in state["recipients"]),
                "VALIDATED_RECIPIENT_CHANGED")
        else:
            _pg_pin_current(state["artifact_pin"])
            _pg_require(result.artifact is state["artifact_pin"][0] and state.get("cleanup_return") is not None and
                result.artifact.native is state["public_native"][0], "EXPORTED_ARTIFACT_CHANGED")
        return result
    except BaseException as error:
        raise _pg_fail(state, error)


def _checked_productive_validation_return(result, binding):
    return _pg_checked_result(result, binding, "validation")


def _checked_productive_export_return(result, binding):
    return _pg_checked_result(result, binding, "export")


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
