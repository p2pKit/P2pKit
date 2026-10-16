#!/usr/bin/env python3
"""Pinned Windows encrypted custody, not a workflow, test owner, or uploader.

All three roots are already-owned, protected ``PrivateDirectory`` objects. The
caller keeps them open, without concurrent close/writers, through this operation
AND its post-return seal. No ordinary mode-bit directory is accepted. Work and
partial output stay private on every failure. Only the two sealed output files
may later be uploaded, and only after successful return and caller finalization.

Installed native GPG is the only child; it has no agent/network/import authority.
Raw diagnostics, native identities and exception graphs are private. This module
never deletes plaintext: the outer owner must retain required evidence and dispose
of only proved-owned temporaries after all pins and domains have KNOWN retirement.
This is not secure erasure, a same-user sandbox, or authenticated decryption proof.

The quarantine is an IN-PROCESS pin hold, never a cross-invocation reset contract.
The outer owner must durably retain UNKNOWN and prohibit cleanup/cache save/upload
or a next phase across interpreter exit while it retires the actual owning domain.
This module supplies no executor/controller or replacement for that outer owner.
"""
from __future__ import annotations

import dataclasses
from contextlib import contextmanager
import copyreg
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import tarfile
import time
import uuid

import audit_processes as processes
import hosted_evidence as portable
import hosted_evidence_primitives as primitives
import hosted_test_evidence as ordinary
import hosted_windows_files as files


MAX_RECORD_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_EXECUTABLE_BYTES = 64 * 1024 * 1024
_QUARANTINE = []  # Deliberate pins, not retryable raw handles. No release/reset API.


class WindowsEvidenceError(portable.EvidenceError):
    """Fixed public message. The attached original/record are PRIVATE, not logs."""

    def __init__(self, original, record, unknown):
        super().__init__("WINDOWS_EVIDENCE_FAILED; private custody must remain private")
        self.original = original
        self.private_record = record
        self.retirement_unknown = unknown


def _require(value, message):
    if not value:
        raise portable.EvidenceError(message)


_exception_detail = primitives._exception_detail


class _Session:
    """One finite export/validation attempt; never turns cleanup errors into PASS."""

    def __init__(self, work, label):
        self.work, self.label = work, label
        self.borrowed = [work]
        self.resources, self.commands, self.errors = [], [], []
        self.identity = None
        self._owners = {}
        self.original = None
        self.unknown = False
        self._seen = set()

    def hold(self, label, owner):
        row = {"label": label, "owner": owner, "closed": False, "quarantined": False}
        self.resources.append(row)
        self._owners[id(owner)] = row
        return owner

    def capture(self, phase, error, *, unknown=False):
        detail = _exception_detail(error)
        self.unknown |= unknown or detail["retirementUnknown"]
        if self.original is None:
            self.original = error
        if id(error) not in self._seen:
            self._seen.add(id(error))
            if len(self.errors) < 64:
                self.errors.append({"phase": phase, "detail": detail})
            else:
                self.unknown = True

    def close(self, owner):
        row = self._owners[id(owner)]
        if row["closed"] or row["quarantined"]:
            return
        row["closed"] = True  # Never retry a close, including an ambiguous native close.
        try:
            owner.close()
        except BaseException as error:
            self.capture(row["label"] + "-close", error, unknown=True)

    def check(self):
        if self.original is not None:
            raise self.original

    def quarantine(self, owners):
        self.unknown = True
        for row in self.resources:
            if any(row["owner"] is owner for owner in owners) and not row["closed"]:
                row["quarantined"] = True

    def encoded(self):
        value = {"schema": 1, "operation": self.label,
                 "result": "FAILED" if self.original is not None else "READY_FOR_CALLER_SEAL",
                 "retirement": "UNKNOWN" if self.unknown else "KNOWN",
                 "admittedManifestIdentity": self.identity,
                 "commands": self.commands, "failures": self.errors,
                 "resources": [{key: row[key] for key in ("label", "closed", "quarantined")}
                               for row in self.resources]}
        raw = (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                          allow_nan=False) + "\n").encode("ascii")
        _require(len(raw) <= MAX_RECORD_BYTES, "Private Windows evidence record exceeds its bound")
        return raw

    def finish(self):
        for row in reversed(self.resources):
            self.close(row["owner"])
        receipt = None
        try:
            raw = self.encoded()
            receipt = self.work.create_file(self.label + "-result-" + uuid.uuid4().hex + ".json",
                                             max_bytes=MAX_RECORD_BYTES, deadline=time.monotonic() + 30)
            receipt.write(raw)
            receipt.sync()
            _require(receipt.verify().size == len(raw), "Private Windows evidence record differs")
        except BaseException as error:
            self.capture("private-result", error)
        finally:
            if receipt is not None:
                try:
                    receipt.close()
                except BaseException as error:
                    self.capture("private-result-close", error, unknown=True)
        if self.unknown:
            # Keep roots and unresolved borrowed sinks alive. Merely unwinding a
            # Python stack must not release pins beneath an unretired child.
            _QUARANTINE.append(self)
        if self.original is not None:
            try:
                raw = self.encoded()
            except BaseException:
                self.unknown = True
                if not any(item is self for item in _QUARANTINE):
                    _QUARANTINE.append(self)
                raw = b'{"result":"FAILED","retirement":"UNKNOWN","privateRecord":"UNAVAILABLE"}\n'
            if not isinstance(self.original, Exception):
                # Cancellation retains its exact object/type; data is private.
                try:
                    self.original._p2pkit_windows_evidence = raw
                except BaseException:
                    self.unknown = True
                    _QUARANTINE.append(self)
                raise self.original
            raise WindowsEvidenceError(self.original, raw, self.unknown) from None


@dataclasses.dataclass(frozen=True)
class Recipient:
    work: files.PrivateDirectory
    executable: Path
    executable_sha256: str
    work_identity: tuple[int, str]
    fingerprint: str
    encryption_fingerprint: str
    expires_at: int
    key_sha256: str
    job_id: str


def _native():
    _require(not _QUARANTINE, "Prior Windows evidence retirement is UNKNOWN; no next invocation")
    _require(os.name == "nt" and processes.host_role() == "windows-x64",
             "Windows encrypted evidence requires genuine native AMD64 Windows")


def _root(value):
    _require(isinstance(value, files.PrivateDirectory), "Pass an already-pinned private native root")
    value.verify()
    files.absolute_parts(str(value.path))
    return value


def _disjoint(*roots):
    paths = []
    for root in roots:
        drive, parts = files.absolute_parts(str(root.path))
        paths.append(tuple(piece.casefold() for piece in (drive, *parts)))
    for i, left in enumerate(paths):
        for j in range(i + 1, len(paths)):
            right = paths[j]
            _require(roots[i].identity != roots[j].identity and
                     left[:len(right)] != right and right[:len(left)] != left,
                     "Evidence, encryption work, and output roots must be disjoint")


def _empty(root, session, end):
    snapshot = _session_create(session, "empty-root-snapshot", root, "snapshot",
                               max_bytes=0, max_members=1, deadline=end)
    _require(set(snapshot.entries) == {""}, "Encryption work/output must be new and empty")
    _session_close(session, snapshot)
    _session_check(session)


def _executable(path, end):
    return _executable_owned(path, end, None)


def _executable_owned(path, end, session):
    """Public installed executable only; private evidence never uses Path.open."""
    path = Path(path)
    portable._deadline(end)
    files.absolute_parts(str(path))
    _require(path.suffix.lower() == ".exe", "Installed GPG must be a native executable")
    for parent in (path, *path.parents):
        info = (parent.lstat() if session is None else
                session.effect("executable-path-lstat", type(parent).lstat, parent))
        _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                 "Installed GPG path cannot contain a reparse point")
    before = path.lstat() if session is None else session.effect("executable-before-lstat", type(path).lstat, path)
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             64 <= before.st_size <= MAX_EXECUTABLE_BYTES, "Installed GPG executable is not bounded regular input")
    digest = hashlib.sha256()
    with _executable_reader(path, end, session) as stream:
        descriptor = _session_call(session, stream, "fileno")
        # Public PE file, NOT a NativeFile or private stream.
        opened = os.fstat(descriptor) if session is None else session.effect("executable-open-fstat", os.fstat, descriptor)
        _require(os.path.samestat(before, opened), "Installed GPG changed during admission")
        header = _session_call(session, stream, "read", 64)
        _require(header[:2] == b"MZ", "Installed GPG lacks a native PE header")
        offset = struct.unpack_from("<I", header, 60)[0]
        _require(64 <= offset <= before.st_size - 26, "Installed GPG PE header offset is invalid")
        _session_call(session, stream, "seek", offset)
        pe = _session_call(session, stream, "read", 26)
        _require(pe[:4] == b"PE\0\0" and struct.unpack_from("<H", pe, 4)[0] == 0x8664 and
                 struct.unpack_from("<H", pe, 24)[0] == 0x20B, "Installed GPG is not native AMD64 PE32+")
        _session_call(session, stream, "seek", 0)
        for chunk in iter(lambda: _session_call(session, stream, "read", files.CHUNK), b""):
            portable._deadline(end)
            if session is not None:
                _session_guard(session)
            digest.update(chunk)
        descriptor = _session_call(session, stream, "fileno")
        after = os.fstat(descriptor) if session is None else session.effect("executable-after-fstat", os.fstat, descriptor)
    current = path.lstat() if session is None else session.effect("executable-final-lstat", type(path).lstat, path)
    _require(os.path.samestat(before, after) and os.path.samestat(before, current) and
             before.st_size == after.st_size == current.st_size and
             before.st_mtime_ns == after.st_mtime_ns == current.st_mtime_ns,
             "Installed GPG changed during admission")
    return digest.hexdigest()


@contextmanager
def _executable_reader(path, end, session):
    if session is None:
        with path.open("rb") as stream:
            yield stream
        return
    stream = session.open_executable(path, end)
    try:
        _session_guard(session)
        yield stream
    except BaseException as error:
        _session_capture(session, "public-installed-executable", error)
        raise
    finally:
        _session_close(session, stream)
        _session_check(session)


def _environment(recipient, invocation, home, temporary):
    system = os.environ.get("SYSTEMROOT", "")
    files.absolute_parts(system)
    environment = {"SYSTEMROOT": system, "WINDIR": system,
                   "PATH": str(recipient.executable.parent) + ";" + system + "\\System32",
                   "HOME": str(recipient.work.path), "APPDATA": str(home.path), "LOCALAPPDATA": str(home.path),
                   "GNUPGHOME": str(home.path), "TEMP": str(temporary.path), "TMP": str(temporary.path),
                   "LANG": "C", "LC_ALL": "C"}
    # Do not inherit credentials/hooks/default agent access. Do preserve the
    # complete REAL ownership chain before appending this distinct GPG domain.
    for name in (processes.JOB_ENV, processes.CHAIN_ENV, processes.DOMAINS_ENV,
                 processes.STATE_ENV, "GRADLE_USER_HOME"):
        if name in os.environ:
            environment[name] = os.environ[name]
    return processes.ownership_environment(environment, recipient.job_id, invocation,
                                           str(recipient.work.path), str(home.path), allow_new_context=True)


def _read(session, root, name, maximum, end):
    if type(session) is _ProductiveSession:
        return session.read_bytes(root, name, maximum, end)
    stream = session.hold(name + "-reader", root.open_file(name, max_bytes=maximum, deadline=end))
    raw = stream.read(maximum + 1)
    _require(len(raw) <= maximum and stream.read(1) == b"", "Private input exceeds its byte bound")
    stream.verify()
    _session_close(session, stream)
    _session_check(session)
    return raw


def _write(session, root, name, data, maximum, end):
    if type(session) is _ProductiveSession:
        return session.write_bytes(root, name, data, maximum, end)
    _require(type(data) is bytes and len(data) <= maximum, "Private bytes exceed their fixed bound")
    stream = session.hold(name + "-writer", root.create_file(name, max_bytes=maximum, deadline=end))
    stream.write(data)
    stream.sync()
    _require(stream.verify().size == len(data), "Private byte write differs")
    _session_close(session, stream)
    _session_check(session)


def _gpg(session, recipient, arguments, end, *, output=None, output_name="stdout", encryption=False,
         borrowed_owners=()):
    if type(session) is _ProductiveSession:
        borrowed_owners = tuple(borrowed_owners)
        session.begin_command(recipient, arguments, end, output, output_name, encryption, borrowed_owners)
    portable._deadline(end)
    _require(_session_executable(session, recipient.executable, end) == recipient.executable_sha256,
             "Installed GPG changed")
    work = recipient.work
    _require(_session_call(session, work, "verify").identity == recipient.work_identity,
             "Recipient work ownership changed")
    # Inputs created by the caller precede this command's resource slice. Keep
    # their native input/ancestor owners, not only the paths handed to GPG.
    # Success leaves them caller-owned; UNKNOWN must prevent finish() closing them.
    if type(session) is not _ProductiveSession:
        borrowed_owners = tuple(borrowed_owners)
    for owner in borrowed_owners:
        held = session._owners.get(id(owner))
        _require(held is not None and held["owner"] is owner and not held["closed"] and not held["quarantined"],
                 "GPG borrowed custody must already be a live session-owned resource")
        _session_call(session, owner, "verify")
    start = len(session.resources)
    operation = _session_create(session, "gpg-operation", work, "create_directory",
                                "gpg-" + uuid.uuid4().hex, deadline=end)
    home = _session_create(session, "gpg-home", work, "open_directory", "gnupg", deadline=end)
    temporary = _session_create(session, "gpg-temp", work, "open_directory", "tmp", deadline=end)
    armor = _session_create(session, "recipient-armor-pin", work, "open_file", "recipient.asc",
                            max_bytes=portable.MAX_KEY_BYTES, deadline=end)
    ring = _session_create(session, "recipient-ring-pin", work, "open_file", "recipient.gpg",
                           max_bytes=portable.MAX_KEY_BYTES, deadline=end)
    armor_raw = _session_call(session, armor, "read", portable.MAX_KEY_BYTES)
    ring_raw = _session_call(session, ring, "read", portable.MAX_KEY_BYTES)
    _require(hashlib.sha256(armor_raw).hexdigest() == recipient.key_sha256 and
             portable._public_armor(armor_raw) == ring_raw, "Validated recipient bytes changed")
    destination = operation if output is None else output
    maximum = portable.MAX_DIAGNOSTIC_BYTES if output is None else portable.MAX_CIPHERTEXT_BYTES
    out = _session_create(session, "gpg-stdout", destination, "create_file", output_name,
                           max_bytes=maximum, deadline=end)
    err = _session_create(session, "gpg-stderr-status", operation, "create_file", "stderr",
                           max_bytes=portable.MAX_DIAGNOSTIC_BYTES, deadline=end)
    # POSIX/MSYS GPG treats a drive colon as a resource URL. Explicit ./ selects
    # this pinned work cwd's ring rather than a bare name relative to GNUPGHOME.
    command = [str(recipient.executable), "--no-options", "--homedir", str(home.path),
               "--batch", "--no-tty", "--no-autostart", "--no-auto-key-retrieve", "--no-auto-key-import",
               "--auto-key-locate", "clear", "--disable-dirmngr", "--pinentry-mode", "error",
               "--no-random-seed-file", "--no-default-keyring", "--keyring", "./recipient.gpg",
               "--lock-never", "--no-auto-check-trustdb", "--trust-model", "always"]
    if encryption:
        command += ["--status-fd", "2"]
    command += arguments
    invocation = uuid.uuid4().hex
    environment = _environment(recipient, invocation, home, temporary)
    scope = process = None
    row = {"argv": command, "invocation": invocation, "waitExitCode": None,
           "retirement": "UNSTARTED", "outputs": {}}
    if type(session) is _ProductiveSession:
        session.start_command(row, command, environment)
    else:
        session.commands.append(row)
    domain_known = False
    try:
        if type(session) is _ProductiveSession:
            scope = session.construct("gpg-native-scope", processes.WindowsScope, recipient.job_id, invocation,
                                      str(work.path), str(home.path))
        else:
            scope = processes.WindowsScope(recipient.job_id, invocation, str(work.path), str(home.path))
        process = _session_call(session, scope, "spawn", command, str(work.path), environment,
                                stdout=out, stderr=err)
        _require(process.stdout is None and process.stderr is None, "Native GPG did not borrow private sinks")
        while True:
            portable._deadline(end)
            _session_call(session, out, "observe_live_output")
            _session_call(session, err, "observe_live_output")
            code = _session_call(session, process, "poll")
            if code is not None:
                _command_update(session, row, "waitExitCode", code)
                break
            if type(session) is _ProductiveSession:
                session.effect("gpg-poll-sleep", time.sleep, 0.025)
            else:
                time.sleep(0.025)
        _require(code == 0, "GPG failed; original private diagnostics retained")
        _require(not _session_call(session, scope, "discover"),
                 "GPG left a live descendant; forced cleanup is not successful encryption")
    except BaseException as error:
        _session_capture(session, "gpg-command", error)
    finally:
        if type(session) is _ProductiveSession:
            # A scope may have ACTUALLY returned and been retained before a
            # post-construction guard failed, leaving this frame's local None.
            # Recover only that original owner for necessary close, never a
            # fresh scope or reconstructed job handle.
            scope = _session_returned_scope(session, row, scope)
        if scope is not None:
            try:
                # Never grant a failed/over-limit child a further graceful write
                # interval. The fixed five seconds are retirement, not acceptance.
                remaining = (_session_call(session, scope, "drain", grace=0, kill_wait=5, deadline=end)
                             if type(session) is _ProductiveSession else scope.drain(grace=0, kill_wait=5))
                _require(not remaining, "Native GPG domain retirement is UNKNOWN")
                domain_known = True
            except BaseException as error:
                _session_capture(session, "gpg-drain", error, unknown=True)
            try:
                _command_update(session, row, "ownership", _session_call(session, scope, "description"))
                _require(not row["ownership"].get("discoveryErrors"), "GPG ownership discovery is UNKNOWN")
            except BaseException as error:
                _session_capture(session, "gpg-description", error, unknown=True)
            try:
                if type(session) is _ProductiveSession:
                    _session_close(session, scope)
                    _session_check(session)
                else:
                    scope.close()
            except BaseException as error:
                _session_capture(session, "gpg-scope-close", error, unknown=True)
        elif session.original is not None:
            # Constructor cleanup details, including notes, are already captured;
            # a missing Python scope variable is not itself a retirement proof.
            domain_known = not session.unknown
        if not domain_known or session.unknown:
            session.quarantine([*borrowed_owners, *(item["owner"] for item in session.resources[start:])])
            _command_update(session, row, "retirement", "UNKNOWN")
        else:
            _command_update(session, row, "retirement", "KNOWN")
            for label, sink in (("stdout", out), ("stderr", err)):
                try:
                    info = _session_call(session, sink, "verify")
                    _session_call(session, sink, "sync")
                    _command_update(session, row, "outputs", info.as_dict(), output=label)
                except BaseException as error:
                    _session_capture(session, "gpg-" + label + "-final", error)
                _session_close(session, sink)
    _session_check(session)
    # Writable NativeFiles cannot be read. Reopen by the still-pinned directory,
    # only AFTER native scope/duplicate retirement and writer verify/sync/close.
    stderr = _read(session, operation, "stderr", portable.MAX_DIAGNOSTIC_BYTES, end)
    stdout = b"" if output is not None else _read(session, operation, "stdout", portable.MAX_DIAGNOSTIC_BYTES, end)
    for label, value in (("stdout", stdout), ("stderr", stderr)):
        if label != "stdout" or output is None:
            observed = {**row["outputs"][label], "sha256": hashlib.sha256(value).hexdigest()}
            _command_update(session, row, "outputs", observed, output=label)
    _session_call(session, armor, "verify")
    _session_call(session, ring, "verify")
    _empty(home, session, end)
    _empty(temporary, session, end)
    _require(_session_executable(session, recipient.executable, end) == recipient.executable_sha256,
             "Installed GPG changed during execution")
    # A 30-second key refresh must not leave its deadline-bound readers alive
    # until a potentially 900-second archive/export finishes.
    for item in reversed(session.resources[start:]):
        _session_close(session, item["owner"])
    _session_check(session)
    if type(session) is _ProductiveSession:
        session.complete_command(row, stdout, stderr)
    return stdout, stderr


def validate_recipient(public_key: bytes, expected_full_fingerprint: str, owned_work: files.PrivateDirectory, *,
                       job_id: str) -> Recipient:
    """Validate public policy bytes before tests, with no private key/import/agent.

    ``owned_work`` is empty and remains caller-owned/pinned until export and
    retirement finish. Fingerprint authentication and trusted policy bootstrap are
    caller prerequisites. This function does not establish hosted identity.
    """
    _native()
    _require(isinstance(owned_work, files.PrivateDirectory), "Pass an already-pinned private native root")
    work = owned_work
    session = _Session(work, "recipient-validation")
    result = None
    try:
        end = time.monotonic() + 60
        _root(work)
        _empty(work, session, end)
        _require(type(public_key) is bytes and 0 < len(public_key) <= portable.MAX_KEY_BYTES,
                 "A bounded public key is required")
        _require(type(expected_full_fingerprint) is str and re.fullmatch(r"[0-9a-fA-F]{40}", expected_full_fingerprint),
                 "Expected fingerprint must be exactly 40 hexadecimal digits")
        _require(type(job_id) is str and re.fullmatch(r"[0-9a-f]{32}", job_id), "A genuine owner job identity is required")
        packets = portable._public_armor(public_key)
        installed = shutil.which("gpg.exe")
        _require(installed is not None, "Installed native GPG is required; no download fallback")
        executable = Path(installed)
        executable_sha256 = _executable(executable, end)
        session.hold("gpg-home-created", work.create_directory("gnupg", deadline=end))
        session.hold("gpg-temp-created", work.create_directory("tmp", deadline=end))
        _write(session, work, "recipient.asc", public_key, portable.MAX_KEY_BYTES, end)
        _write(session, work, "recipient.gpg", packets, portable.MAX_KEY_BYTES, end)
        recipient = Recipient(work, executable, executable_sha256, work.identity, expected_full_fingerprint.upper(),
                              "", 0, hashlib.sha256(public_key).hexdigest(), job_id)
        version, _ = _gpg(session, recipient, ["--version"], end)
        _require(re.match(rb"gpg \(GnuPG\) 2\.[0-9]+\.[0-9]+(?:[ \r\n]|$)", version),
                 "Installed executable did not identify as GnuPG 2")
        common = ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint"]
        shown, _ = _gpg(session, recipient, common + ["--import-options", "show-only", "--import",
                                                    str(work.path / "recipient.asc")], end)
        fingerprint, expiry = portable._key_identity(shown, recipient.fingerprint)
        selected, _ = _gpg(session, recipient, common + ["--list-keys"], end)
        _require(portable._key_identity(selected, recipient.fingerprint) == (fingerprint, expiry),
                 "Selected recipient differs from the validated public key")
        result = dataclasses.replace(recipient, encryption_fingerprint=fingerprint, expires_at=expiry)
    except BaseException as error:
        _session_capture(session, "recipient-validation", error)
    finally:
        session.finish()
    return result


def _archive(session, snapshot, destination, end):
    raw = session.hold("plaintext-archive", destination.create_file("evidence.tar.gz",
                        max_bytes=portable.MAX_ARCHIVE_BYTES, deadline=end))
    with gzip.GzipFile(fileobj=portable._BoundedWriter(raw, end), mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
            for name, stamp in sorted(snapshot.entries.items()):
                portable._deadline(end)
                _require(len(name.encode("utf-8")) <= 1024, "Evidence member name exceeds the archive bound")
                info = tarfile.TarInfo("evidence/" + name if name else "evidence")
                info.uid, info.gid, info.uname, info.gname, info.mtime = 0, 0, "", "", 0
                if stamp.is_directory:
                    info.type, info.mode = tarfile.DIRTYPE, 0o700
                    archive.addfile(info)
                else:
                    info.mode, info.size = 0o600, stamp.size
                    stream = session.hold("archive-member", snapshot.open_file(name))
                    archive.addfile(info, portable._TimedReader(stream, end))
                    _require(stream.read(1) == b"" and stream.verify() == stamp,
                             "Evidence member changed while archiving")
                    _session_close(session, stream)
                    _session_check(session)
    raw.sync()
    raw.verify()
    _session_close(session, raw)
    snapshot.verify()
    _session_check(session)


def _hash(stream, end):
    digest = hashlib.sha256()
    count = 0
    for block in iter(lambda: stream.read(files.CHUNK), b""):
        portable._deadline(end)
        count += len(block)
        digest.update(block)
    _require(stream.verify().size == count, "Ciphertext size changed while hashing")
    return digest.hexdigest(), count


def _seal(session, output, manifest, end):
    snapshot = session.hold("sealed-output-snapshot", output.snapshot(
        max_bytes=files.MAX_FILE_BYTES, max_members=3, deadline=end))
    _require(set(snapshot.entries) == {"", portable.ARTIFACT, portable.MANIFEST},
             "Upload root must contain exactly ciphertext and manifest")
    reader = session.hold("sealed-ciphertext-reader", snapshot.open_file(portable.ARTIFACT))
    digest, size = _hash(reader, end)
    _require((digest, size) == (manifest["artifact"]["sha256"], manifest["artifact"]["size"]),
             "Sealed output ciphertext differs")
    _session_close(session, reader)
    encoded = _read(session, output, portable.MANIFEST, MAX_MANIFEST_BYTES, end)
    _require(encoded == _manifest_bytes(manifest), "Sealed output manifest differs")
    snapshot.verify()
    _session_close(session, snapshot)
    _session_check(session)


def _manifest_bytes(manifest):
    raw = (json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    _require(len(raw) <= MAX_MANIFEST_BYTES, "Admitted public manifest exceeds its bound")
    return raw


def _export(evidence, output, recipient, manifest_factory, *, max_bytes, max_members, timeout_seconds):
    _native()
    _require(isinstance(recipient, Recipient) and isinstance(recipient.work, files.PrivateDirectory),
             "A validated native Windows recipient owner is required")
    work = recipient.work
    session = _Session(work, "encrypted-export")
    session.borrowed += [evidence, output]
    result = None
    try:
        for value in (work, evidence, output):
            _root(value)
        for value, maximum in ((max_bytes, portable.MAX_BYTES), (max_members, portable.MAX_MEMBERS),
                               (timeout_seconds, portable.MAX_TIMEOUT_SECONDS)):
            _require(type(value) is int and 0 < value <= maximum, "Evidence bounds cannot be disabled or expanded")
        end = time.monotonic() + timeout_seconds
        manifest = manifest_factory()
        session.identity = json.loads(_manifest_bytes(manifest))
        _manifest_bytes(manifest)
        _disjoint(evidence, work, output)
        _empty(output, session, end)
        _require(not recipient.expires_at or recipient.expires_at > int(time.time()),
                 "Validated recipient expired before export")
        listing, _ = _gpg(session, recipient, ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint",
                                              "--list-keys"], min(end, time.monotonic() + 30))
        _require(portable._key_identity(listing, recipient.fingerprint) ==
                 (recipient.encryption_fingerprint, recipient.expires_at), "Recipient keyring changed before export")
        snapshot = session.hold("original-evidence-snapshot", evidence.snapshot(
            max_bytes=max_bytes, max_members=max_members, deadline=end))
        private = session.hold("export-work", work.create_directory("export-" + uuid.uuid4().hex, deadline=end))
        _archive(session, snapshot, private, end)
        plaintext = session.hold("plaintext-input-pin", private.open_file("evidence.tar.gz",
                                max_bytes=portable.MAX_ARCHIVE_BYTES, deadline=end))
        _, status = _gpg(session, recipient, ["--cipher-algo", "AES256", "--compress-algo", "none",
                          "--no-encrypt-to", "--recipient", recipient.encryption_fingerprint + "!",
                          "--output", "-", "--encrypt", str(plaintext.path)], end,
                        output=private, output_name=portable.ARTIFACT, encryption=True,
                        borrowed_owners=(private, plaintext))
        plaintext.verify()
        lines = status.splitlines()
        _require(sum(line.startswith(b"[GNUPG:] BEGIN_ENCRYPTION ") for line in lines) == 1 and
                 lines.count(b"[GNUPG:] END_ENCRYPTION") == 1 and
                 not any(line.startswith((b"[GNUPG:] FAILURE", b"[GNUPG:] ERROR")) for line in lines),
                 "GPG did not confirm complete evidence encryption")
        encrypted = session.hold("private-ciphertext-reader", private.open_file(portable.ARTIFACT,
                                 max_bytes=portable.MAX_CIPHERTEXT_BYTES, deadline=end))
        portable._ciphertext_stream(encrypted, encrypted.initial_info.size, recipient.encryption_fingerprint)
        encrypted.verify()
        encrypted.seek(0)
        digest, size = _hash(encrypted, end)
        portable._deadline(end)
        _require(manifest_factory() == manifest, "Admitted source/event/policy changed during export")
        _require(not recipient.expires_at or recipient.expires_at > int(time.time()),
                 "Validated recipient expired during export")
        manifest["artifact"] = {"name": portable.ARTIFACT, "sha256": digest, "size": size}
        manifest_raw = _manifest_bytes(manifest)
        published = session.hold("public-ciphertext-writer", output.create_file(portable.ARTIFACT,
                                  max_bytes=size, deadline=end))
        encrypted.seek(0)
        for block in iter(lambda: encrypted.read(files.CHUNK), b""):
            portable._deadline(end)
            published.write(block)
        published.sync()
        _require(published.verify().size == size, "Published ciphertext copy differs")
        _session_close(session, published)
        _session_check(session)
        _write(session, output, portable.MANIFEST, manifest_raw, MAX_MANIFEST_BYTES, end)
        snapshot.verify()
        _seal(session, output, manifest, end)
        result = manifest
    except BaseException as error:
        _session_capture(session, "encrypted-export", error)
    finally:
        session.finish()
    return result


def export_encrypted(evidence, output, recipient: Recipient, *, source_commit: str, source_tree: str,
                     run_id: str, run_attempt: str, max_bytes=portable.MAX_BYTES,
                     max_members=portable.MAX_MEMBERS, timeout_seconds=portable.MAX_TIMEOUT_SECONDS):
    """Manual schema-1 entry only; keeps the actual manual GitHub identity check."""
    return _export(evidence, output, recipient,
                   lambda: portable._manifest_identity(source_commit, source_tree, run_id, run_attempt),
                   max_bytes=max_bytes, max_members=max_members, timeout_seconds=timeout_seconds)


def export_test_encrypted(evidence, output, recipient: Recipient, *, profile, root, admission, query_runner,
                          max_bytes=portable.MAX_BYTES, max_members=portable.MAX_MEMBERS,
                          timeout_seconds=portable.MAX_TIMEOUT_SECONDS):
    """Ordinary schema-2 entry; NEVER accepts an arbitrary public manifest.

    Uses the same original immutable Admission, current real event/source and
    trusted-recipient re-admission as POSIX. The native query_runner remains the
    outer owner's private, bounded, fully retired callback, not a subprocess
    fallback supplied here. There is no trusted-recipient bootstrap in this API.
    """
    return _export(evidence, output, recipient,
                   lambda: ordinary._bound_manifest(recipient, profile=profile, root=root,
                                                     admission=admission, query_runner=query_runner),
                   max_bytes=max_bytes, max_members=max_members, timeout_seconds=timeout_seconds)


def export_bootstrap_encrypted(evidence, output, recipient: Recipient, *, root, admission, query_runner,
                               timeout_seconds, max_bytes=portable.MAX_BYTES, max_members=portable.MAX_MEMBERS):
    """Dormant schema-3 bootstrap entry; no ordinary/manual identity fallback.

    Borrowed NEW native owners, original absolute fences, known writer retirement
    and actual enclosing return/seal remain caller obligations. The unchanged
    native backend rechecks this closed identity before ciphertext publication;
    it cannot turn a dependency Snapshot or UNKNOWN custody into evidence.
    """
    ordinary._bootstrap_bounds(max_bytes, max_members, timeout_seconds)
    return _export(evidence, output, recipient,
                   lambda: ordinary._bound_bootstrap_manifest(recipient, root=root, admission=admission,
                                                               query_runner=query_runner),
                   max_bytes=max_bytes, max_members=max_members, timeout_seconds=timeout_seconds)


def export_initial_ordinary_encrypted(evidence, output, recipient: Recipient, *, root, request,
                                      query_runner, check, timeout_seconds,
                                      max_bytes=portable.MAX_BYTES, max_members=portable.MAX_MEMBERS):
    """Distinct closed schema5 entry; actual parent current before/after required.

    Preserve the maintained NativeFile/Snapshot/GPG native domain and both local
    manifest checks. A candidate DATA identity is never ordinary Admission or a
    caller-selected manifest, and cannot extend the original native lifetimes.
    """
    ordinary._bootstrap_bounds(max_bytes, max_members, timeout_seconds)
    return _export(evidence, output, recipient,
        lambda: ordinary._bound_initial_ordinary_manifest(recipient, root=root, request=request,
                                                          query_runner=query_runner, check=check),
        max_bytes=max_bytes, max_members=max_members, timeout_seconds=timeout_seconds)


# Productive-only in-process currency. None of these registries is persisted,
# reset, or populated by decoded DATA. Legacy _Session/entry policy stays strict.
_PRODUCTIVE_SESSIONS = {}
_PRODUCTIVE_RESULTS = {}
_PRODUCTIVE_ARTIFACTS = {}
_PRODUCTIVE_CLOSES = {}
_PRODUCTIVE_PINS = {}
_PRODUCTIVE_APIS = {}
_PRODUCTIVE_SESSION_PINS = {}
_PRODUCTIVE_ROWS = {}
_PRODUCTIVE_ADAPTERS = {}
_PRODUCTIVE_COMMANDS = {}
_PRODUCTIVE_COMMAND_PINS = {}


@dataclasses.dataclass(frozen=True)
class _ProductiveValidationReturn:
    binding: object
    session: object
    recipient: object
    observations: object
    known_close: object


@dataclasses.dataclass(frozen=True)
class _ProductiveExportReturn:
    binding: object
    session: object
    manifest_raw: bytes
    artifact: object
    observations: object
    known_close: object


@dataclasses.dataclass(frozen=True)
class _ProductiveArtifact:
    name: str
    sha256: str
    size: int
    native: tuple


@dataclasses.dataclass(frozen=True)
class _ProductiveKnownClose:
    session: object
    resources: tuple
    receipt: object
    observations: tuple


def _productive_e():
    # SAME ordinary canonical import, never a spec loader or alternate PC graph.
    import hosted_initial_recipient_evidence
    return hosted_initial_recipient_evidence


def _native_vector(info):
    _require(type(info) is files.FileInfo, "Productive native metadata type differs")
    identity = info.identity
    _require(type(identity) is tuple and len(identity) == 2 and type(identity[0]) is int and
             0 < identity[0] < 2 ** 64 and type(identity[1]) is str and
             re.fullmatch(r"[0-9a-f]{32}", identity[1]), "Productive native identity differs")
    integers = (info.size, info.links, info.attributes, info.creation_100ns,
                info.modified_100ns, info.change_100ns)
    _require(all(type(value) is int and 0 <= value < 2 ** 64 for value in integers) and
             type(info.is_directory) is bool and
             (info.owner_sid is None or type(info.owner_sid) is str) and
             (info.protected_dacl is None or type(info.protected_dacl) is bool),
             "Productive native metadata scalar differs")
    return ("windows", *identity, info.is_directory, *integers, info.owner_sid, info.protected_dacl)


def _same_scalar(actual, original):
    return type(actual) is type(original) and (actual == original if type(original) in
            (str, int, float, bool, bytes, type(None)) else actual is original)


def _data_pin(value, remaining=None, depth=0):
    """Bounded retained builtin DATA, never registration or native authority."""
    if remaining is None:
        remaining = [65536]
    remaining[0] -= 1
    _require(remaining[0] >= 0 and depth <= 32, "Productive retained DATA exceeds its bound")
    kind = type(value)
    if kind in (str, bytes, int, bool, float, type(None)):
        if kind in (str, bytes):
            _require(len(value) <= MAX_RECORD_BYTES, "Productive retained scalar exceeds bound")
        if kind is float:
            _require(math.isfinite(value), "Productive retained observation is not finite")
        return value, kind, None
    if kind in (list, tuple, dict):
        children = (tuple((_data_pin(key, remaining, depth + 1),
                           _data_pin(item, remaining, depth + 1)) for key, item in value.items())
                    if kind is dict else tuple(_data_pin(item, remaining, depth + 1) for item in value))
        return value, kind, children
    if kind is files.FileInfo:
        return value, kind, (_frozen_fields(value), _native_vector(value))
    if kind is os.stat_result:
        return value, kind, (tuple(value), value.st_size, value.st_mtime_ns, value.st_ctime_ns,
                             getattr(value, "st_file_attributes", None))
    raise portable.EvidenceError("Productive retained DATA type differs")


def _data_current(pin):
    value, kind, saved = pin
    _require(type(value) is kind, "Productive original DATA type changed")
    if kind in (str, bytes, int, bool, float, type(None)):
        return
    if kind in (list, tuple):
        _require(len(value) == len(saved) and all(_same_scalar(item, child[0])
                 for item, child in zip(value, saved)), "Productive original DATA slots changed")
        for child in saved:
            _data_current(child)
    elif kind is dict:
        current = tuple(value.items())
        _require(len(current) == len(saved) and all(_same_scalar(key, left[0]) and
                 _same_scalar(item, right[0]) for (key, item), (left, right) in zip(current, saved)),
                 "Productive original DATA mapping changed")
        for left, right in saved:
            _data_current(left)
            _data_current(right)
    elif kind is files.FileInfo:
        _fields_current(value, saved[0])
        _require(_native_vector(value) == saved[1], "Productive original FileInfo changed")
    elif kind is os.stat_result:
        _require((tuple(value), value.st_size, value.st_mtime_ns, value.st_ctime_ns,
                  getattr(value, "st_file_attributes", None)) == saved,
                 "Productive original public stat changed")


def _changed_field(value, pin, name, replacement):
    # Called only for a named source-owned transition, NEVER a whole-object
    # rebase after a callback. Other original slots must remain unchanged.
    _fields_current(value, pin)
    dictionary, fields = pin
    _require(name in dictionary, "Productive transition field differs")
    setattr(value, name, replacement)
    return dictionary, tuple((key, replacement if key == name else item) for key, item in fields)


def _api_pin(api):
    saved = _PRODUCTIVE_APIS.get(id(api))
    if saved is None:
        kind, dictionary = type(api), api.__dict__
        methods = tuple((name, getattr(kind, name)) for name in dir(kind)
                        if not name.startswith("__") and callable(getattr(kind, name)))
        native = tuple((name, value) for name, value in dictionary.items() if callable(value))
        policy = getattr(api, "policy", None)
        policy_pin = _frozen_fields(policy) if policy is not None else None
        saved = (api, kind, dictionary, methods, native, policy, policy_pin)
        _PRODUCTIVE_APIS[id(api)] = saved
    _api_current(saved)
    return saved


def _api_current(saved):
    api, kind, dictionary, methods, native, policy, policy_pin = saved
    _require(_PRODUCTIVE_APIS.get(id(api)) is saved and type(api) is kind and api.__dict__ is dictionary,
             "Productive original native API replaced")
    for name, function in methods:
        _require(getattr(kind, name) is function and name not in dictionary,
                 "Productive original native API method changed")
    for name, function in native:
        _require(dictionary.get(name) is function, "Productive original Win32 function slot changed")
    if policy_pin is not None:
        _require(api.policy is policy, "Productive original native ACL policy replaced")
        _fields_current(policy, policy_pin)


def _reference_pin(owner, names, fields=()):
    """Pure in-memory helper reference; deliberately NOT an observed close."""
    kind, dictionary = type(owner), getattr(owner, "__dict__", None)
    return (owner, kind, dictionary, tuple((name, getattr(kind, name)) for name in names),
            tuple((name, getattr(owner, name)) for name in fields))


def _reference_current(pin):
    owner, kind, dictionary, methods, fields = pin
    _require(type(owner) is kind and getattr(owner, "__dict__", None) is dictionary,
             "Productive original helper reference changed")
    for name, function in methods:
        _require(getattr(kind, name) is function and (dictionary is None or name not in dictionary),
                 "Productive original helper method changed")
    for name, value in fields:
        _require(_same_scalar(getattr(owner, name), value), "Productive original helper field changed")


def _class_pin(kind):
    # Raw namespace descriptors, NOT newly bound classmethods from getattr.
    # Includes original constructors/inherited descriptors before the first E
    # callback, so a same-class method replacement cannot become a new baseline
    # when its first actual owner is constructed later in the operation.
    return kind, kind.__mro__, tuple((base, tuple(base.__dict__.items())) for base in kind.__mro__)


def _class_current(pin):
    kind, bases, namespaces = pin
    _require(kind.__mro__ is bases, "Productive original supplier inheritance changed")
    for base, slots in namespaces:
        current = base.__dict__
        _require(len(current) == len(slots) and all(name in current and _same_scalar(current[name], value)
                 for name, value in slots), "Productive original supplier descriptor/constructor changed")


def _tarinfo_copy_cache():
    """Prepare ONLY the stdlib's named lazy cache before any E callback.

    TarFile.addfile copies TarInfo, whose object reduction can populate this
    cache. Admit that single cold initialization, not arbitrary later class
    mutations. A malformed warm cache is never repaired into a new baseline.
    """
    module, initializer = copyreg, copyreg._slotnames
    tar_module, kind = tarfile, tarfile.TarInfo
    _require(type(kind) is type and kind.__mro__ == (kind, object),
             "Productive TarInfo copy inheritance differs")
    original = _class_pin(kind)
    declaration = kind.__dict__.get("__slots__")
    _require(type(declaration) in (dict, tuple, list), "Productive TarInfo slot declaration differs")
    declaration_pin = _data_pin(declaration)
    expected = tuple(declaration)
    _require(expected and all(type(name) is str and name and not name.startswith("__")
             and name in kind.__dict__ for name in expected) and len(set(expected)) == len(expected),
             "Productive TarInfo slot names differ")
    if "__slotnames__" in kind.__dict__:
        cache = kind.__dict__["__slotnames__"]
        prepared = original
    else:
        cache = initializer(kind)
        # Extend the PRE-call namespaces by this ONE entry. Never snapshot
        # post-call descriptors to bless an unrelated initializer mutation.
        prepared = (kind, original[1], tuple((base, slots + (("__slotnames__", cache),))
                    if base is kind else (base, slots) for base, slots in original[2]))
    _require(copyreg is module and module._slotnames is initializer and tarfile is tar_module and
             tar_module.TarInfo is kind, "Productive TarInfo copy initializer changed")
    _require(type(cache) is list and len(cache) == len(expected) and
             all(type(actual) is str and actual == name for actual, name in zip(cache, expected)) and
             kind.__dict__.get("__slotnames__") is cache, "Productive TarInfo copy cache differs")
    _data_current(declaration_pin)
    _class_current(prepared)
    return module, initializer, _data_pin((declaration, cache))


class _ObjectPin:
    """Original references, not authority; borrowed pin releases stay historical.

    Snapshot/scope nested closure is TRANSITIVE_ORIGINAL_AGGREGATE_RETURN.
    We retain pre-close pins because the real native close clears owner._pins.
    A normal aggregate return, not _closed/_retired flags, supplies that fact.
    """

    def __init__(self, owner):
        self.owner, self.kind = owner, type(owner)
        self.dictionary = getattr(owner, "__dict__", None)
        self.children, self.containers, self.cells, self.stable = [], [], [], []
        self.references = []
        self.pin_list = self.pin_slots = self.entries = self.job = self.process_handle = None
        self.leaders = ()
        self.fileobj = None
        self.retired_fields = None
        self.scope_data = self.scope_errors = self.returncode = None
        self.closed = False
        if self.kind is files.Snapshot:
            self.category = "snapshot"
            names = ("open_file", "verify", "close")
            attrs = ("_operation_lock", "_deadline", "_root", "entries", "total_bytes")
            for name in ("_files", "_directories", "_names"):
                container = getattr(owner, name)
                _require(type(container) is dict, "Productive snapshot container differs")
                items = tuple(container.items())
                self.containers.append((name, container, items))
                if name != "_names":
                    self.children.extend(_ObjectPin(child) for _, child in items)
            self.entries = tuple((name, info, _native_vector(info)) for name, info in owner.entries.items())
        elif self.kind is files.PrivateDirectory:
            self.category = "directory"
            names = ("verify", "names", "snapshot", "open_file", "create_file", "open_directory",
                     "create_directory", "_clone", "_live", "_child", "_walk_parent", "_relative", "_file", "close")
            attrs = ("_operation_lock", "_api", "path", "identity")
        elif self.kind is files.NativeFile:
            self.category = "native-file"
            names = ("read", "write", "verify", "sync", "flush", "close", "tell", "seek", "readable",
                     "writable", "observe_live_output")
            attrs = ("_operation_lock", "_api", "path", "identity", "max_bytes", "_deadline", "_writable",
                     "initial_info")
        elif self.kind is processes.WindowsScope:
            self.category = "scope"
            names = ("spawn", "discover", "drain", "description", "close", "_retire", "_member_pids", "signal_all")
            attrs = ("api", "job_id", "invocation", "leaders", "launches", "known", "discovery_errors")
            self.job = owner.job
            self.scope_data = _data_pin((owner.launches, owner.known))
            self.scope_errors = tuple(sorted(owner.discovery_errors))
        elif self.kind is processes.WindowsProcess:
            self.category = "process"
            names = ("poll", "wait", "close")
            attrs = ("api", "pid", "stdout", "stderr")
            self.process_handle = owner.handle
            self.returncode = owner.returncode
        elif self.kind in (io.BufferedReader, io.FileIO):
            self.category = "public-file"
            names = ("read", "seek", "fileno", "close")
            attrs = ("name", "mode")
            if self.kind is io.BufferedReader:
                attrs += ("raw",)
                self.children.append(_ObjectPin(owner.raw))
        elif self.kind is gzip.GzipFile:
            self.category = "gzip"
            names = ("write", "flush", "close", "_check_not_closed")
            if hasattr(self.kind, "_write_raw"):
                names += ("_write_raw",)
            attrs = ("compress", "mode", "name", "myfileobj", "_write_mtime")
            self.fileobj = owner.fileobj  # Real close alone may clear this field.
            self.references.append(_reference_pin(owner.compress, ("compress", "flush", "copy")))
            if hasattr(owner, "_buffer"):
                attrs += ("_buffer",)
                buffer = owner._buffer
                self.references.append(_reference_pin(buffer, ("write", "flush", "close"), ("raw",)))
                self.references.append(_reference_pin(buffer.raw, ("write", "writable", "close"), ("gzip_file",)))
                _require(buffer.raw.gzip_file is owner, "Productive gzip buffer belongs to another owner")
            # Gzip's write buffer/compressor are retained memory helpers, not
            # native handles and NOT fictitiously described as closed by gzip.
        elif self.kind is tarfile.TarFile:
            self.category = "tar"
            names = ("addfile", "close")
            attrs = ("fileobj", "mode", "format", "encoding", "errors", "_extfileobj", "copybufsize")
            _require(type(owner.fileobj) is tarfile._Stream and owner._extfileobj is True,
                     "Productive tar stream must have its own direct close owner")
        elif self.kind is tarfile._Stream:
            self.category = "tar-stream"
            names = ("write", "close", "tell", "_Stream__write")
            attrs = ("fileobj", "mode", "comptype", "bufsize", "_extfileobj")
            _require(owner.mode == "w" and owner.comptype == "tar" and owner._extfileobj is True,
                     "Productive tar stream mode differs")
        else:
            raise portable.EvidenceError("Productive original owner type differs")
        self.methods = tuple((name, getattr(self.kind, name)) for name in names)
        for name in attrs:
            self.stable.append((name, getattr(owner, name)))
        if self.kind in (files.PrivateDirectory, files.NativeFile):
            self.pin_list, self.pin_slots = owner._pins, tuple(owner._pins)
            _require(type(self.pin_list) is list and self.pin_slots, "Productive native pins are absent")
            for cell in self.pin_slots:
                _require(type(cell) is files._Pin, "Productive original native pin type differs")
                stable = tuple((name, getattr(cell, name)) for name in
                               ("api", "path", "info", "private", "inherited_allowed", "writable",
                                "strict_streams", "immutable", "lock"))
                methods = tuple((name, getattr(type(cell), name)) for name in
                                ("acquire", "release", "observe", "names"))
                self.cells.append((cell, cell.__dict__, stable, methods, cell.handle, _native_vector(cell.info)))
        apis = []
        for name in ("_api", "api"):
            api = getattr(owner, name, None)
            if api is not None and not any(saved[0] is api for saved in apis):
                apis.append(_api_pin(api))
        self.apis = tuple(apis)
        self.children, self.containers = tuple(self.children), tuple(self.containers)
        self.cells, self.stable, self.references = tuple(self.cells), tuple(self.stable), tuple(self.references)
        _PRODUCTIVE_PINS[id(self)] = (self, type(self), self.__dict__, _frozen_fields(self))
        _ObjectPin.check(self)

    def currency(self):
        saved = _PRODUCTIVE_PINS.get(id(self))
        _require(saved is not None and saved[0] is self and type(self) is saved[1] and
                 self.__dict__ is saved[2], "Productive original pin currency replaced")
        _fields_current(self, saved[3])
        return saved

    def transition(self, name, value):
        saved = _ObjectPin.currency(self)
        _require(name in ("children", "leaders", "closed", "retired_fields", "scope_data", "scope_errors",
                         "returncode"), "Productive pin transition differs")
        pin = _changed_field(self, saved[3], name, value)
        _PRODUCTIVE_PINS[id(self)] = (*saved[:3], pin)

    def adopt_process(self, process):
        _ObjectPin.currency(self)
        _require(self.category == "scope" and not self.leaders and
                 type(self.owner.leaders) is list and len(self.owner.leaders) == 1 and
                 self.owner.leaders[0] is process and type(process) is processes.WindowsProcess,
                 "Productive original scope/process return differs")
        child = _ObjectPin(process)
        self.transition("leaders", (process,))
        self.transition("children", (child,))

    def failed_spawn(self):
        _ObjectPin.currency(self)
        _require(self.category == "scope" and not self.leaders and
                 type(self.owner.leaders) is list and len(self.owner.leaders) <= 1,
                 "Productive failed launch leader shape differs")
        children = tuple(_ObjectPin(child) for child in self.owner.leaders)
        self.transition("leaders", tuple(self.owner.leaders))
        self.transition("children", children)
        # Failure-only retention of original supplier mutations. The original
        # exception remains sticky; this does not create a spawn observation.
        self.transition("scope_data", _data_pin((self.owner.launches, self.owner.known)))
        self.transition("scope_errors", tuple(sorted(self.owner.discovery_errors)))

    def returned_call(self, name, value):
        # Only the original supplier's actual mutating method return may change
        # these slots. Never refresh them after an E callback or guard.
        _ObjectPin.currency(self)
        if self.category == "scope" and name in ("spawn", "discover", "drain"):
            _ObjectPin.check(self, changed_scope=True, changed_process=name == "drain")
            self.transition("scope_data", _data_pin((self.owner.launches, self.owner.known)))
            self.transition("scope_errors", tuple(sorted(self.owner.discovery_errors)))
            if name == "drain":
                for child in self.children:
                    child.transition("returncode", child.owner.returncode)
        elif self.category == "process" and name in ("poll", "wait"):
            _ObjectPin.check(self, changed_process=True)
            _require((value is None or type(value) is int) and _same_scalar(self.owner.returncode, value),
                     "Productive actual process returncode differs")
            self.transition("returncode", value)
        _ObjectPin.check(self)

    def check(self, *, passive=False, borrowed=False, closing=False, changed_scope=False, changed_process=False):
        _ObjectPin.currency(self)
        for api in self.apis:
            _api_current(api)
        owner = self.owner
        _require(type(owner) is self.kind and getattr(owner, "__dict__", None) is self.dictionary,
                 "Productive original owner changed")
        for name, function in self.methods:
            _require(getattr(self.kind, name) is function and
                     (self.dictionary is None or name not in self.dictionary),
                     "Productive original method slot changed")
        for name, value in self.stable:
            _require(_same_scalar(getattr(owner, name), value), "Productive original owner field changed")
        if self.retired_fields is not None:
            _fields_current(owner, self.retired_fields)
        for reference in self.references:
            _reference_current(reference)
        if self.category in ("directory", "native-file"):
            if passive and borrowed or closing:
                pass  # Only PC's genuine outer return may authenticate that later retirement.
            elif not self.closed:
                _require(owner._pins is self.pin_list and len(owner._pins) == len(self.pin_slots) and
                         all(left is right for left, right in zip(owner._pins, self.pin_slots)),
                         "Productive original native pin slots changed")
            else:
                _require(type(owner._pins) is list and not owner._pins,
                         "Productive closed native owner acquired replacement pins")
            for cell, dictionary, stable, methods, handle, vector in self.cells:
                _require(type(cell) is files._Pin and cell.__dict__ is dictionary,
                         "Productive original nested pin changed")
                for name, value in stable:
                    _require(_same_scalar(getattr(cell, name), value), "Productive original nested pin field changed")
                for name, function in methods:
                    _require(getattr(type(cell), name) is function and name not in dictionary,
                             "Productive original nested pin method changed")
                _require(_native_vector(cell.info) == vector, "Productive original pin metadata changed")
                # A borrowed ancestor may legitimately retire after this result.
                # Passive checks never infer that event from references/handle.
                if not passive and not self.closed:
                    _require(type(cell.references) is int and cell.references > 0 and cell.handle == handle,
                             "Productive live native pin changed")
        if self.category == "snapshot":
            _require(len(owner.entries) == len(self.entries) and
                     all(owner.entries.get(name) is info and _native_vector(info) == vector
                         for name, info, vector in self.entries),
                     "Productive original snapshot entries changed")
            for name, container, items in self.containers:
                current = getattr(owner, name)
                _require(current is container and len(current) == len(items) and
                         all(key in current and current[key] is value for key, value in items),
                         "Productive original snapshot nested slots changed")
        if self.category == "scope":
            if not changed_scope:
                _data_current(self.scope_data)
                _require(tuple(sorted(owner.discovery_errors)) == self.scope_errors,
                         "Productive original scope retirement data changed")
            _require(len(owner.leaders) == len(self.leaders) and
                     all(left is right for left, right in zip(owner.leaders, self.leaders)),
                     "Productive original leader slots changed")
            if not self.closed and not passive and not closing:
                _require(owner.job == self.job, "Productive original job handle changed")
        if self.category == "process" and not self.closed and not passive and not closing:
            _require(owner.handle == self.process_handle, "Productive original process handle changed")
        if self.category == "process" and not changed_process:
            _require(_same_scalar(owner.returncode, self.returncode), "Productive natural process exit changed")
        if self.category == "gzip":
            _require(owner.fileobj is (None if self.closed or closing else self.fileobj),
                     "Productive original gzip output changed")
            _adapter_current(self.fileobj)
        if self.category in ("tar", "tar-stream"):
            # Both original close methods short-circuit on their public flag.
            # Require LIVE flags before the call and after each prior callback;
            # closing=True belongs only to THIS original in-progress/returned
            # close, never to the separately owned stream's ancestor close.
            _require(owner.closed is (self.closed or closing),
                     "Productive original tar close state changed")
        for child in self.children:
            _ObjectPin.check(child, passive=passive, closing=closing, changed_process=changed_process)

    def returned_close(self):
        # Check immutable originals BEFORE the one legitimate lifecycle update.
        # In particular do not rebase a replaced _pins/entries/leaders/method.
        _ObjectPin.check(self, passive=True, closing=True)
        self.transition("closed", True)
        for child in self.children:
            child.returned_close()
        # This check is secondary integrity. The caller separately retains the
        # successful actual aggregate call; these flags NEVER produce a receipt.
        if self.category in ("directory", "snapshot"):
            _require(self.owner._closed is True, "Productive original close did not retire its owner")
        elif self.category == "native-file":
            _require(self.owner.closed and self.owner._retired is True,
                     "Productive original close did not retire its stream")
        elif self.category == "scope":
            _require(self.owner.job is None, "Productive original scope close did not retire job handle")
        elif self.category == "process":
            _require(self.owner.handle is None, "Productive original process close did not retire handle")
        elif self.category in ("public-file", "gzip", "tar", "tar-stream"):
            _require(self.owner.closed is True, "Productive original stream close did not return closed")
        if type(self.dictionary) is dict:
            self.transition("retired_fields", _frozen_fields(self.owner))
        _ObjectPin.check(self, passive=True)


def _frozen_fields(value):
    _require(type(value.__dict__) is dict, "Productive frozen object dictionary differs")
    return value.__dict__, tuple(value.__dict__.items())


def _fields_current(value, pin):
    dictionary, items = pin
    _require(value.__dict__ is dictionary and len(dictionary) == len(items) and
             all(name in dictionary and _same_scalar(dictionary[name], saved) for name, saved in items),
             "Productive frozen original fields changed")


def _session_pin(session):
    saved = _PRODUCTIVE_SESSION_PINS.get(id(session))
    _require(saved is not None and saved["session"] is session and type(session) is saved["kind"] and
             session.__dict__ is saved["dictionary"], "Productive original session replaced")
    return saved


def _session_fields(session):
    saved = _session_pin(session)
    _fields_current(session, saved["fields"])
    return saved


def _session_set(session, name, value):
    saved = _session_fields(session)
    saved["fields"] = _changed_field(session, saved["fields"], name, value)


def _session_capture(session, phase, error, *, unknown=False):
    # The original failure method is retained before callbacks. Calling a
    # callback-shadowed instance method in an exception path could otherwise
    # swallow the very integrity failure that detected its replacement.
    saved = _PRODUCTIVE_SESSION_PINS.get(id(session))
    if saved is not None and saved["session"] is session:
        return saved["capture"](session, phase, error, unknown=unknown)
    return session.capture(phase, error, unknown=unknown)


def _session_check(session):
    saved = _PRODUCTIVE_SESSION_PINS.get(id(session))
    if saved is not None and saved["session"] is session:
        return saved["check"](session)
    return session.check()


def _session_guard(session, *, whole=False):
    saved = _PRODUCTIVE_SESSION_PINS.get(id(session))
    _require(saved is not None and saved["session"] is session, "Productive original guard registry differs")
    try:
        return saved["guard"](session, whole=whole)
    except BaseException as error:
        _session_capture(session, "productive-original-guard", error)
        raise


def _session_close(session, owner):
    saved = _PRODUCTIVE_SESSION_PINS.get(id(session))
    if saved is not None and saved["session"] is session:
        return saved["close"](session, owner)
    return session.close(owner)


def _session_fail(session, phase, error):
    saved = _PRODUCTIVE_SESSION_PINS.get(id(session))
    _require(saved is not None and saved["session"] is session, "Productive failure session was never registered")
    return saved["fail"](session, phase, error)


def _session_returned_scope(session, row, local_scope):
    saved = _PRODUCTIVE_SESSION_PINS.get(id(session))
    _require(saved is not None and saved["session"] is session, "Productive original scope registry differs")
    originals = tuple(owner for command_row, owner in saved["scope_returns"] if command_row is row)
    _require(len(originals) <= 1, "Productive native scope returned more than once")
    if originals:
        _require(local_scope is None or local_scope is originals[0], "Productive native scope local changed")
        return originals[0]
    _require(local_scope is None, "Productive native scope was never retained")
    return None


def _row_current(row, *, full=False):
    saved = _PRODUCTIVE_ROWS.get(id(row))
    _require(saved is not None and saved["row"] is row and type(row) is dict,
             "Productive original resource row replaced")
    fields = saved["fields"]
    _require(len(row) == len(fields) and all(key in row and _same_scalar(row[key], value)
             for key, value in fields), "Productive original resource row field changed")
    operations, original = row["operations"], saved["operations"]
    _require(len(operations) == len(original) and (not original or operations[-1] is original[-1][0]),
             "Productive original operation log changed")
    if full:
        for actual, (record, pin) in zip(operations, original):
            _require(actual is record, "Productive original operation slot changed")
            if pin is not None:
                _data_current(pin)
    if row["closed"]:
        actual = saved["actual_close"]
        _require(actual is not None and actual[0] is row["owner"] and
                 actual[1] is dict(row["pin"].methods)["close"] and actual[2] is row["close_return"] and
                 row["attempted"] and row["observed_return"], "Productive close lacks its actual original call")
        if row["final_info"] is not None:
            _require(row["owner"].final_info is row["final_info"] and
                     _native_vector(row["final_info"]) == row["final_vector"],
                     "Productive original post-close native metadata changed")
    return saved


def _row_set(row, name, value):
    saved = _row_current(row)
    _require(name in row, "Productive resource transition field differs")
    row[name] = value
    saved["fields"] = tuple((key, value if key == name else item) for key, item in saved["fields"])


def _returned_value(owner, name, value):
    # Capture immediately after the ACTUAL call, before its next E callback.
    # Original immutable FileInfos/returned DATA stay retained. Large payload
    # bytes do not become a second plaintext copy in this in-memory journal.
    if type(value) is bytes:
        observed = ("bytes", len(value), hashlib.sha256(value).hexdigest())
        return observed, _data_pin(observed)
    if type(value) is files.FileInfo:
        return ("native", value, _native_vector(value)), _data_pin(value)
    if name == "spawn":
        _require(type(value) is processes.WindowsProcess, "Productive actual process return differs")
        return ("original-process", value), None
    if type(owner) is files.Snapshot and name == "verify":
        _require(value is owner.entries, "Productive actual snapshot return differs")
        return ("original-entries", value), None
    return ("return", value), _data_pin(value)


def _row_observe(row, name, observation, pin, local, caps):
    saved = _row_current(row)
    _require(len(saved["operations"]) < files.MAX_MEMBERS * 4, "Productive original observation limit")
    if pin is not None:
        _data_current(pin)
    record = (name, observation, local, caps)
    row["operations"].append(record)
    saved["operations"].append((record, pin))


def _command_current(saved):
    pin = _PRODUCTIVE_COMMAND_PINS.get(id(saved))
    _require(pin is not None and pin[0] is saved and type(saved) is dict and len(saved) == len(pin[1]) and
             all(key in saved and _same_scalar(saved[key], value) for key, value in pin[1]),
             "Productive original command state changed")
    _data_current(saved["arguments"])
    if saved["row"] is not None:
        _data_current(saved["row_pin"])
        _data_current(saved["environment"])
        _require(saved["row"]["argv"] is saved["argv"], "Productive original argv replaced")
    _fields_current(saved["recipient"], saved["recipient_pin"])


def _command_set(saved, name, value):
    _command_current(saved)
    _require(name in ("row", "row_pin", "argv", "environment", "completed"),
             "Productive command transition differs")
    # A transition is followed immediately by its companion row state changes,
    # before any callback; other fields cannot be silently rebased.
    pin = _PRODUCTIVE_COMMAND_PINS[id(saved)]
    saved[name] = value
    _PRODUCTIVE_COMMAND_PINS[id(saved)] = (saved, tuple((key, value if key == name else item)
                                                      for key, item in pin[1]))


def _command_update(session, row, key, value, *, output=None):
    if type(session) is not _ProductiveSession:
        if output is None:
            row[key] = value
        else:
            row["outputs"][output] = value
        return
    saved = _PRODUCTIVE_COMMANDS.get(id(row))
    _require(saved is not None and saved is session.command and saved["row"] is row,
             "Productive original command row differs")
    _command_current(saved)
    if output is None:
        _require(key in ("waitExitCode", "retirement", "ownership"), "Productive command transition differs")
        row[key] = value
    else:
        _require(output in ("stdout", "stderr"), "Productive command sink differs")
        row["outputs"][output] = value
    pin = _PRODUCTIVE_COMMAND_PINS[id(saved)]
    replacement = _data_pin(row)
    saved["row_pin"] = replacement
    _PRODUCTIVE_COMMAND_PINS[id(saved)] = (saved, tuple((name, replacement if name == "row_pin" else item)
                                                      for name, item in pin[1]))


def _productive_frame(function):
    # Entire owned operation, including its entry/pin checks, is a once-only
    # failure frame. A caller catching a pre-effect refusal cannot restore
    # fields and quietly resume the same original attempt.
    def owned(session, *args, **kwargs):
        try:
            return function(session, *args, **kwargs)
        except BaseException as error:
            _session_capture(session, "productive-" + function.__name__, error)
            raise
    return owned


class _ProductiveSession:
    """One E-registered operation, actual direct/transitive returns, no reset."""

    def __init__(self, binding, validation):
        # Poison the original duplicate before even the new cache preflight.
        prior = _PRODUCTIVE_SESSIONS.get(id(binding))
        if prior is not None:
            error = portable.EvidenceError("Productive Windows operation cannot begin twice")
            _session_capture(prior, "reentry", error)
            raise error
        self.binding, self.validation, self.pid = binding, validation, os.getpid()
        self.e, self.e_methods = None, ()
        self.resources, self.commands, self.errors, self.observations = [], [], [], []
        self._resource_list, self._command_list = self.resources, self.commands
        self._observation_list, self._error_list = self.observations, self.errors
        self._slots, self._owners, self._borrowed, self._seen = [], {}, [], set()
        self._slot_list, self._owner_map = self._slots, self._owners
        self.original, self.unknown, self.busy, self.finished = None, False, False, False
        self.receipt, self.known_close, self.result = None, None, None
        self.keyring_cap, self.keyring_done = None, False
        self.finish_mode, self.calls = False, 0
        self.last_local = None
        self.receipt_writer = self.receipt_reader = None
        self.view = self.caps = self.recipient = self.recipient_pin = None
        self.view_pin = self.caps_pin = self.keyring_pin = self.keyring_return = None
        self.work = self.label = self.ordinary_close_observation = self.result_name = None
        self.artifact_sources = self.finish_return = self.command = None
        self.borrowed_pins = ()
        self.binding_kind = type(binding)
        self.view_kind = self.caps_kind = self.keyring_kind = None
        self.binding_pin = _frozen_fields(binding)
        self.function_names = _PRODUCTIVE_FUNCTION_NAMES
        self.source_methods = tuple((name, globals()[name]) for name in _PRODUCTIVE_FUNCTION_NAMES)
        self.own_methods = tuple((kind, name, function) for kind in
            (_ProductiveSession, _ObjectPin, _ProductiveWriter, _ProductiveReader, Recipient,
             _ProductiveValidationReturn, _ProductiveExportReturn, _ProductiveArtifact, _ProductiveKnownClose)
            for name, function in kind.__dict__.items() if callable(function))
        self.type_slots = tuple((module, name, getattr(module, name)) for module, names in (
            (files, ("NativeFile", "PrivateDirectory", "Snapshot", "_Pin", "FileInfo", "_WinApi")),
            (processes, ("WindowsScope", "WindowsProcess", "WinApi")), (gzip, ("GzipFile",)),
            (tarfile, ("TarFile", "TarInfo", "_Stream")), (io, ("BufferedReader", "FileIO")))
            for name in names)
        if hasattr(gzip, "_WriteBufferStream"):
            self.type_slots += ((gzip, "_WriteBufferStream", gzip._WriteBufferStream),
                                (io, "BufferedWriter", io.BufferedWriter))
        copy_module, slotnames, self.tarinfo_copy_pin = _tarinfo_copy_cache()
        suppliers = tuple(kind for _module, _name, kind in self.type_slots) + (Path, type(Path()),)
        self.supplier_classes = tuple(_class_pin(kind) for kind in suppliers)
        # Keep the exact PRE-initializer supplier, not a post-call rebaseline.
        self.supplier_slots = ((copy_module, "_slotnames", slotnames),) + tuple(
            (module, name, getattr(module, name)) for module, names in (
            (files, ("_release", "_acquire", "_end", "_check_time", "_close_native", "_cleanup", "_on_exit",
                     "_exit_close", "absolute_parts", "relative_parts", "component", "require",
                     "MAX_FILE_BYTES", "MAX_MEMBERS", "MAX_READ_BYTES", "MAX_SECONDS", "CHUNK")),
            (processes, ("ownership_environment", "resolve_executable", "_retire_actions", "_finish_retirement",
                         "_bounded_drain", "_check_drain_deadline", "JOB_ENV", "CHAIN_ENV", "DOMAINS_ENV", "STATE_ENV")),
            (portable, ("_deadline", "_fail", "_packet_length", "_public_armor", "_key_identity", "_ciphertext_stream",
                        "primitives", "EvidenceError", "_path", "_private_directory", "_identity",
                        "MAX_KEY_BYTES", "MAX_BYTES", "MAX_MEMBERS", "MAX_ARCHIVE_BYTES", "MAX_CIPHERTEXT_BYTES",
                        "MAX_DIAGNOSTIC_BYTES", "ARTIFACT", "MANIFEST")),
            # Keep original leaf globals AND their actual suppliers: a public
            # reexport left untouched cannot conceal a changed function global.
            (primitives, ("EvidenceError", "_fail", "_deadline", "_path", "_private_directory", "_identity",
                          "_exception_detail", "Path", "os", "stat", "time")),
            (primitives.os, ("getuid",) if hasattr(primitives.os, "getuid") else ()),
            (primitives.stat, ("S_ISDIR", "S_ISLNK")), (primitives.time, ("monotonic",)),
            (tarfile, ("open", "copyfileobj", "PAX_FORMAT", "DIRTYPE")),
            (gzip, ("write32u",)), (gzip.zlib, ("compressobj", "crc32")),
            (time, ("monotonic", "time", "sleep")), (os, ("getpid", "fstat")),
            (shutil, ("which",)), (hashlib, ("sha256",)), (json, ("loads", "dumps")),
            (uuid, ("uuid4",))) for name in names)
        self.supplier_methods = tuple((kind, name, getattr(kind, name)) for kind, names in (
            (Path, ("open", "lstat")), (type(Path()), ("open", "lstat")), (files.FileInfo, ("as_dict",)),
            (primitives.Path, ("__new__", "__init__", "is_absolute", "parts", "anchor", "__truediv__", "__eq__",
                              "__ne__", "lstat", "iterdir")),
            (type(primitives.Path()), ("__new__", "__init__", "is_absolute", "parts", "anchor", "__truediv__", "__eq__",
                                     "__ne__", "lstat", "iterdir")),
            (tarfile.TarInfo, ("tobuf", "create_pax_header", "create_ustar_header")))
            for name in names)
        # Registry before the first fallible E callback; no post-callback cache
        # initialization or replacement can become fresh original currency.
        _PRODUCTIVE_SESSIONS[id(binding)] = self
        _PRODUCTIVE_SESSION_PINS[id(self)] = {
            "session": self, "kind": type(self), "dictionary": self.__dict__, "fields": _frozen_fields(self),
            "first": None, "unknown": False, "guarding": False, "callback": False,
            "capture": _ProductiveSession.capture, "close": _ProductiveSession.close, "fail": _ProductiveSession.fail,
            "pins": _ProductiveSession.pins, "check": _ProductiveSession.check, "guard": _ProductiveSession.guard,
            "errors": self.errors, "seen": self._seen, "capturing": False,
            "pipeline": None, "observations": [], "commands": [], "adapters": [], "active_adapters": [],
            "rows": [], "factory_returns": [], "scope_returns": [],
            "tar_stream_return": None, "tar_stream_transfer": None}
        try:
            _session_set(self, "e", _productive_e())
            _session_set(self, "e_methods", tuple((name, getattr(self.e, name)) for name in (
                "_checked_productive_validation_binding", "_checked_productive_export_binding",
                "_productive_work_guard", "_productive_finish_guard", "_productive_whole_guard",
                "_productive_expected_node", "_productive_node_guard", "_productive_check_snapshot",
                "_productive_manifest", "_productive_keyring_begin", "_productive_keyring_guard",
                "_productive_keyring_complete")))
            name = "_checked_productive_validation_binding" if validation else "_checked_productive_export_binding"
            _session_set(self, "view", self.invoke_e(name))
            _session_set(self, "caps", self.view.caps)
            _session_set(self, "view_kind", type(self.view))
            _session_set(self, "caps_kind", type(self.caps))
            _session_set(self, "view_pin", _frozen_fields(self.view))
            _session_set(self, "caps_pin", _frozen_fields(self.caps))
            _require(self.view.role == "windows-x64" and self.caps.finishReserveNs == 30 * 10 ** 9 and
                     self.caps.operationLimitNs == (60 if validation else 240) * 10 ** 9,
                     "Productive Windows operation caps differ")
            _session_set(self, "last_local", self.caps.firstLocal)
            _session_set(self, "work", self.view.work if validation else self.view.recipient.work)
            _session_set(self, "label", "recipient-validation" if validation else "encrypted-export")
            roots = (self.work,) if validation else (self.work, self.view.payload, self.view.output)
            for root in roots:
                _require(type(root) is files.PrivateDirectory, "Productive Windows borrowed root differs")
                self._borrowed.append(_ObjectPin(root))
            _session_set(self, "borrowed_pins", tuple(self._borrowed))
            _session_guard(self)
        except BaseException as error:
            _session_capture(self, "productive-begin", error)
            raise

    def capture(self, phase, error, *, unknown=False):
        saved = _PRODUCTIVE_SESSION_PINS.get(id(self))
        _require(saved is not None and saved["session"] is self, "Productive original failure registry differs")
        if saved["first"] is None:
            saved["first"] = error
        saved["unknown"] |= unknown
        # Diagnostic accessors may reenter or mutate the visible session. The
        # original registry latch and dictionary, not those accessors/fields,
        # retain the first failure. Never rebase any other field after failure.
        if saved["capturing"]:
            saved["unknown"] = True
            detail = None
        else:
            saved["capturing"] = True
            try:
                detail = _exception_detail(error)
                saved["unknown"] |= detail["retirementUnknown"]
            except BaseException:
                detail = None
                saved["unknown"] = True
            finally:
                saved["capturing"] = False
        if id(error) not in saved["seen"]:
            saved["seen"].add(id(error))
            if detail is not None and len(saved["errors"]) < 64:
                saved["errors"].append({"phase": phase, "detail": detail})
            else:
                saved["unknown"] = True
        dictionary, fields = saved["fields"]
        dictionary["original"], dictionary["unknown"] = saved["first"], saved["unknown"]
        saved["fields"] = dictionary, tuple((name, saved["first"] if name == "original" else
            saved["unknown"] if name == "unknown" else value) for name, value in fields)

    def pins(self, *, whole=False, passive=False):
        saved = _session_fields(self)
        _require(_PRODUCTIVE_SESSIONS.get(id(self.binding)) is self and os.getpid() == self.pid,
                 "Productive Windows session registration differs")
        _require(self.original is saved["first"] and self.unknown is saved["unknown"] and
                 self.function_names is _PRODUCTIVE_FUNCTION_NAMES, "Productive original session state differs")
        _require(self.resources is self._resource_list and self.commands is self._command_list and
                 self.observations is self._observation_list and self.errors is self._error_list and
                 self._slots is self._slot_list and self._owners is self._owner_map and
                 len(self.resources) == len(self._slots), "Productive Windows ledger replaced")
        for name, function in self.e_methods:
            _require(getattr(self.e, name) is function, "Productive E method slot changed")
        for name, function in self.source_methods:
            _require(globals()[name] is function, "Productive Windows source method slot changed")
        for kind, name, function in self.own_methods:
            _require(getattr(kind, name) is function and (kind is not type(self) or name not in self.__dict__),
                     "Productive Windows owner method slot changed")
        for module, name, kind in self.type_slots:
            _require(getattr(module, name) is kind, "Productive Windows supplier type slot changed")
        for module, name, value in self.supplier_slots:
            _require(_same_scalar(getattr(module, name), value), "Productive Windows supplier slot changed")
        for kind, name, function in self.supplier_methods:
            _require(getattr(kind, name) is function, "Productive Windows supplier method changed")
        for pin in self.supplier_classes:
            _class_current(pin)
        _data_current(self.tarinfo_copy_pin)
        if saved["tar_stream_transfer"] is not None:
            returned = saved["tar_stream_return"]
            _require(returned is saved["tar_stream_transfer"] and type(returned) is tuple and len(returned) == 3,
                     "Productive original tar stream transfer changed")
            archive, stream, compressed = returned
            _require(type(archive) is tarfile.TarFile and type(stream) is tarfile._Stream and
                     type(compressed) is gzip.GzipFile and archive.fileobj is stream and
                     stream.fileobj is compressed and archive._extfileobj is True and stream._extfileobj is True,
                     "Productive original direct tar stream ownership changed")
            for owner in (archive, stream):
                row = self._owners.get(id(owner))
                pipeline = saved["pipeline"]
                if row is None:
                    _require(pipeline is not None and pipeline[0] is tarfile.open and pipeline[1] == "construct",
                             "Productive original tar stream owner was never registered")
                    continue  # No callback occurs between adoption and BOTH settled pins.
                _row_current(row)
                _require(row["owner"] is owner and row["pin"] is not None,
                         "Productive original tar stream row changed")
                # Constant two-owner check, including after E callbacks. Only
                # THIS owner's genuine original close may change its live flag;
                # the unattempted stream never inherits TarFile's close state.
                closing = pipeline is not None and pipeline[0] is owner and pipeline[1] == "close"
                _ObjectPin.check(row["pin"], passive=passive, closing=closing)
        _require(type(self.binding) is self.binding_kind, "Productive original binding type changed")
        _fields_current(self.binding, self.binding_pin)
        if self.view_pin is not None:
            _require(type(self.view) is self.view_kind and type(self.caps) is self.caps_kind,
                     "Productive original view/caps type changed")
            _fields_current(self.view, self.view_pin)
            _fields_current(self.caps, self.caps_pin)
        if self.recipient_pin is not None:
            _require(type(self.recipient) is Recipient, "Productive original Recipient type changed")
            _fields_current(self.recipient, self.recipient_pin)
        if self.keyring_cap is not None:
            _require(type(self.keyring_cap) is self.keyring_kind, "Productive original keyring type changed")
            _fields_current(self.keyring_cap, self.keyring_pin)
        elif self.keyring_done:
            _require(type(self.keyring_return) is self.keyring_kind, "Productive completed keyring type changed")
            _fields_current(self.keyring_return, self.keyring_pin)
        _require(len(self.resources) == len(saved["rows"]), "Productive original resource count changed")
        if whole:
            for index, original in enumerate(saved["rows"]):
                _require(self.resources[index] is original and self._slots[index] is original and
                         self._owners.get(id(original["owner"])) is original,
                         "Productive original resource slot changed")
                _require(original["pin"] is not None, "Productive original resource was never pinned")
                _row_current(original, full=True)
                pipeline = saved["pipeline"]
                closing = (original["pin"].category in ("tar", "tar-stream") and pipeline is not None and
                           pipeline[0] is original["owner"] and pipeline[1] == "close")
                _ObjectPin.check(original["pin"], passive=passive, closing=closing)
        _require(len(self.observations) == len(saved["observations"]), "Productive original observations changed")
        if whole:
            for actual, (record, pin) in zip(self.observations, saved["observations"]):
                _require(actual is record, "Productive original observation slot changed")
                if pin is not None:
                    _data_current(pin)
        _require(len(self.commands) == len(saved["commands"]) and
                 all(row is command["row"] for row, command in zip(self.commands, saved["commands"])),
                 "Productive original command list changed")
        for command in saved["commands"]:
            _command_current(command)
        if self.command is not None:
            _command_current(self.command)
        for adapter in saved["adapters"] if whole else saved["active_adapters"]:
            _adapter_current(adapter)
        _require(len(self._borrowed) == len(self.borrowed_pins) and
                 all(left is right for left, right in zip(self._borrowed, self.borrowed_pins)),
                 "Productive borrowed root pins replaced")
        for pin in self._borrowed:
            _ObjectPin.check(pin, passive=passive, borrowed=passive)

    def check(self):
        saved = _session_pin(self)
        try:
            saved["pins"](self)
        except BaseException as error:
            _session_capture(self, "productive-original-pins", error, unknown=True)
            raise
        if self.original is not None:
            raise self.original
        _require(not self.unknown, "Productive Windows retirement is UNKNOWN")

    def refuse(self, message, *, unknown=False):
        error = portable.EvidenceError(message)
        _session_capture(self, "productive-refusal", error, unknown=unknown)
        raise error

    def entry(self):
        saved = _session_pin(self)
        if saved["guarding"] or saved["callback"] or self.busy:
            self.refuse("Productive Windows operation reentered")
        _session_check(self)

    def invoke_e(self, name, *args):
        saved = _session_pin(self)
        if saved["callback"]:
            self.refuse("Productive Windows E callback reentered")
        _session_check(self)
        function = dict(self.e_methods)[name]
        saved["callback"] = True
        try:
            result = function(self.binding, *args)
            _session_check(self)
            return result
        except BaseException as error:
            _session_capture(self, "productive-E-" + name, error)
            raise
        finally:
            saved["callback"] = False

    def guard(self, *, whole=False):
        self.entry()
        saved = _session_pin(self)
        saved["guarding"] = True
        try:
            _require(not self.finished, "Productive completed operation cannot do new work")
            # The second work/finish sample charges the full whole check too.
            for step in range(2 if whole else 1):
                name = "_productive_finish_guard" if self.finish_mode else "_productive_work_guard"
                _require(self.invoke_e(name) is self.caps, "Productive guard returned replacement caps")
                if self.keyring_cap is not None:
                    _require(not self.finish_mode and self.invoke_e("_productive_keyring_guard", self.keyring_cap)
                             is self.keyring_cap, "Productive keyring guard differs")
                local = time.monotonic()
                _session_check(self)
                _require(type(local) is float and math.isfinite(local) and self.last_local <= local < self.end(),
                         "Productive original LOCAL bound exhausted or regressed")
                _session_set(self, "last_local", local)
                _session_set(self, "calls", self.calls + 1)
                if whole and step == 0:
                    _require(self.invoke_e("_productive_whole_guard") is self.caps,
                             "Productive whole guard returned replacement caps")
                    saved["pins"](self, whole=True)
            return local
        except BaseException as error:
            _session_capture(self, "productive-guard", error)
            raise
        finally:
            saved["guarding"] = False

    def end(self):
        if self.finish_mode:
            return self.caps.operationFinishEndLocal
        return self.keyring_cap.workEndLocal if self.keyring_cap is not None else self.caps.workEndLocal

    def hold(self, label, owner, *, deadline=None):
        state = _session_pin(self)
        original = dict(state["fields"][1])
        resources, slots, owners = original["resources"], original["_slots"], original["_owners"]
        _require(id(owner) not in owners and len(resources) < 4 * files.MAX_MEMBERS,
                 "Productive resource ownership duplicate/limit")
        row = {"label": label, "owner": owner, "pin": None, "closed": False, "quarantined": False,
               "attempted": False, "close_return": None, "observed_return": False,
               "completion": None, "coverage": "DIRECT", "operations": [],
               "final_info": None, "final_vector": None,
               "deadline": self.end() if deadline is None else deadline}
        resources.append(row)
        slots.append(row)
        owners[id(owner)] = row
        state["rows"].append(row)
        _PRODUCTIVE_ROWS[id(row)] = {"row": row, "fields": tuple(row.items()), "operations": [],
                                     "actual_close": None}
        try:
            _row_set(row, "pin", _ObjectPin(owner))
            self.pins()
            if type(owner) in (files.NativeFile, files.Snapshot):
                _require(type(owner._deadline) is float and owner._deadline == row["deadline"],
                         "Productive native resource deadline differs from its original cap")
            if row["pin"].children:
                _row_set(row, "coverage", "TRANSITIVE_ORIGINAL_AGGREGATE_RETURN")
        except BaseException as error:
            _session_capture(self, "resource-pin", error, unknown=True)
            _row_set(row, "quarantined", True)
            raise
        return owner

    def pin_for(self, owner):
        row = self._owners.get(id(owner))
        if row is not None:
            _row_current(row)
            _require(row["owner"] is owner and row["pin"] is not None and not row["attempted"] and
                     not row["quarantined"], "Productive original resource is not live")
            _ObjectPin.check(row["pin"])
            return row["pin"], row
        for pin in self._borrowed:
            if pin.owner is owner:
                _ObjectPin.check(pin)
                return pin, None
        for row in self.resources:
            if type(row["owner"]) is processes.WindowsScope:
                _row_current(row)
                for child in row["pin"].children:
                    if child.owner is owner:
                        # Prior retired scopes remain original evidence, but
                        # only THIS process's scope must authorize live work.
                        _require(not row["attempted"] and not row["quarantined"],
                                 "Productive process scope is not live")
                        _ObjectPin.check(child)
                        return child, row
        raise portable.EvidenceError("Productive operation on an unowned native resource")

    @_productive_frame
    def call(self, owner, name, *args, **kwargs):
        self.entry()
        _session_guard(self)
        pin, row = self.pin_for(owner)
        _require(row is None or row["deadline"] == self.end(), "Productive native resource subcap differs")
        if self.finish_mode:
            _require(owner is self.receipt_writer or owner is self.receipt_reader,
                     "Productive finish cannot perform ordinary work")
        methods = dict(pin.methods)
        _require(name in methods and not self.busy, "Productive resource method/reentry differs")
        adopt, failed_spawn = pin.adopt_process, pin.failed_spawn
        state = _session_pin(self)
        _session_set(self, "busy", True)
        try:
            value = methods[name](owner, *args, **kwargs)
            # FIRST action after actual spawn return retains the original process.
            if name == "spawn":
                state["factory_returns"].append(("actual-spawn-return", value))
                adopt(value)
                _row_set(row, "coverage", "TRANSITIVE_ORIGINAL_AGGREGATE_RETURN")
            observation, observation_pin = _returned_value(owner, name, value)
            pin.returned_call(name, value)
            _session_set(self, "busy", False)
            local = _session_guard(self)
            _ObjectPin.check(pin)  # Selected original AGAIN after the actual post-call callback.
            if row is not None:
                _row_observe(row, name, observation, observation_pin, local, self.caps)
            else:
                self.observe(owner, name, observation, observation_pin, local)
            return value
        except BaseException as error:
            if name == "spawn" and not pin.leaders:
                try:
                    failed_spawn()
                except BaseException as secondary:
                    _session_capture(self, "failed-launch-pins", secondary, unknown=True)
            _session_capture(self, "native-" + name, error)
            raise
        finally:
            self.unbusy()

    def unbusy(self):
        # A tampered busy slot is a failure, never a way to keep a forged flag.
        saved = _session_pin(self)
        dictionary, fields = saved["fields"]
        expected = dict(fields)["busy"]
        if self.busy is not expected:
            _session_capture(self, "native-busy-slot", portable.EvidenceError("Productive busy slot changed"), unknown=True)
            dictionary, fields = saved["fields"]
        self.busy = False
        saved["fields"] = dictionary, tuple((name, False if name == "busy" else value) for name, value in fields)

    def observe(self, owner, name, observation, pin, local):
        saved = _session_fields(self)
        _require(len(self.observations) < 4 * files.MAX_MEMBERS and
                 len(self.observations) == len(saved["observations"]), "Productive observation bound/shape differs")
        if pin is not None:
            _data_current(pin)
        record = (owner, name, observation, local, self.caps)
        self.observations.append(record)
        saved["observations"].append((record, pin))

    @_productive_frame
    def effect(self, label, function, *args):
        """Actual public metadata/non-owning effect, never a private path open."""
        self.entry()
        _session_guard(self)
        _session_set(self, "busy", True)
        try:
            value = function(*args)
            observation, pin = _returned_value(None, label, value)
            _session_set(self, "busy", False)
            local = _session_guard(self)
            self.observe(function, label, observation, pin, local)
            return value
        except BaseException as error:
            _session_capture(self, "public-" + label, error)
            raise
        finally:
            self.unbusy()

    @_productive_frame
    def construct(self, label, factory, *args, **kwargs):
        self.entry()
        state = _session_pin(self)
        _require(state["pipeline"] is None and
                 any(factory is original for original in (processes.WindowsScope, gzip.GzipFile, tarfile.open)),
                 "Productive original constructor differs")
        memory = factory is gzip.GzipFile or factory is tarfile.open
        command_row = None
        if not memory:
            _require(self.command is not None and self.command["row"] is not None,
                     "Productive scope requires its original active command")
            _command_current(self.command)
            command_row = self.command["row"]
        end = self.end()
        _session_guard(self)
        if factory is tarfile.open:
            _require(state["tar_stream_return"] is None and label == "plaintext-tar" and args == () and
                     set(kwargs) == {"fileobj", "mode", "format"} and kwargs["mode"] == "w|" and
                     kwargs["format"] == tarfile.PAX_FORMAT and type(kwargs["fileobj"]) is gzip.GzipFile,
                     "Productive original streaming tar construction differs")
            self.pin_for(kwargs["fileobj"])
        value = None
        try:
            if memory:
                state["pipeline"] = (factory, "construct")
            else:
                _session_set(self, "busy", True)
            value = factory(*args, **kwargs)
            state["factory_returns"].append((label, value))
            if factory is tarfile.open:
                # ONE actual factory return, with its actual nested stream;
                # this is not a second factory call or a reconstructed owner.
                returned = (value, value.fileobj, kwargs["fileobj"])
                state["tar_stream_return"] = returned  # Before fallible checks/transfer/pins.
                archive, stream, compressed = returned
                _require(type(archive) is tarfile.TarFile and type(stream) is tarfile._Stream and
                         archive.fileobj is stream and stream.fileobj is compressed and archive.mode == "w" and
                         stream.mode == "w" and stream.comptype == "tar" and
                         archive._extfileobj is False and stream._extfileobj is True and
                         archive.closed is False and stream.closed is False,
                         "Productive original tar/stream factory relationship differs")
                # Source-owned one-time transfer BEFORE settled pins/callbacks.
                # Keep stdlib's SAME buffer/defaults without a private ctor ABI.
                archive._extfileobj = True
                state["tar_stream_transfer"] = returned
                self.hold("plaintext-tar-stream", stream, deadline=end)
            if not memory:
                state["scope_returns"].append((command_row, value))
            self.hold(label, value, deadline=end)
            _session_set(self, "busy", False)
            state["pipeline"] = None
            _session_guard(self)
            self.pin_for(value)
            return value
        except BaseException as error:
            _session_capture(self, "productive-construction", error, unknown=value is not None)
            raise
        finally:
            state["pipeline"] = None
            self.unbusy()

    @_productive_frame
    def open_executable(self, path, end):
        self.entry()
        _require(type(path) is type(Path()) and path.suffix.lower() == ".exe" and end == self.end() and
                 not self.finish_mode, "Productive public executable input differs")
        function = type(path).open
        state = _session_pin(self)
        _session_guard(self)
        _session_set(self, "busy", True)
        try:
            stream = function(path, "rb")
            state["factory_returns"].append(("public-installed-executable", stream))
            self.hold("public-installed-executable", stream, deadline=end)
            _session_set(self, "busy", False)
            _session_guard(self)
            self.pin_for(stream)
            return stream
        except BaseException as error:
            _session_capture(self, "public-executable-open", error)
            raise
        finally:
            self.unbusy()

    @_productive_frame
    def begin_command(self, recipient, arguments, end, output, output_name, encryption, borrowed):
        # This original input pin precedes even the first executable/E guard.
        self.entry()
        _require(self.command is None and not self.finish_mode and recipient is self.recipient and
                 type(arguments) is list and 0 < len(arguments) <= 64 and
                 all(type(item) is str for item in arguments) and type(end) is float and end == self.end() and
                 type(output_name) is str and type(encryption) is bool and type(borrowed) is tuple,
                 "Productive original GPG command inputs differ")
        command = {"recipient": recipient, "recipient_pin": _frozen_fields(recipient),
                   "arguments": _data_pin(arguments), "inputs": (end, output, output_name, encryption, borrowed),
                   "row": None, "row_pin": None, "argv": None, "environment": None, "completed": None}
        _PRODUCTIVE_COMMAND_PINS[id(command)] = (command, tuple(command.items()))
        _session_set(self, "command", command)

    def start_command(self, row, argv, environment):
        _session_check(self)
        saved = self.command
        _require(saved is not None and saved["row"] is None and row["argv"] is argv and
                 type(argv) is list and all(type(item) is str for item in argv) and
                 type(environment) is dict and all(type(key) is type(value) is str for key, value in environment.items()),
                 "Productive generated argv/environment differs")
        _command_set(saved, "row_pin", _data_pin(row))
        _command_set(saved, "argv", argv)
        _command_set(saved, "environment", _data_pin(environment))
        _command_set(saved, "row", row)
        _PRODUCTIVE_COMMANDS[id(row)] = saved
        self.commands.append(row)
        _session_pin(self)["commands"].append(saved)

    def complete_command(self, row, stdout, stderr):
        _session_guard(self)
        saved = self.command
        _require(saved is _PRODUCTIVE_COMMANDS.get(id(row)) and saved["completed"] is None,
                 "Productive GPG completion was not original")
        _command_current(saved)
        _command_set(saved, "completed", (stdout, stderr, self.last_local, self.caps, self.keyring_cap))
        _session_set(self, "command", None)

    @_productive_frame
    def create(self, label, owner, name, *args, **kwargs):
        self.entry()
        _session_guard(self)
        pin, _row = self.pin_for(owner)
        end = self.end()
        if "deadline" in kwargs:
            _require(type(kwargs["deadline"]) is float and kwargs["deadline"] == self.end(),
                     "Productive native creation cannot retime its cap")
        if self.finish_mode:
            _require(owner is self.work and args == (self.result_name,) and
                     ((name == "create_file" and self.receipt_writer is None and self.receipt_reader is None) or
                      (name == "open_file" and self.receipt_writer is not None and self.receipt_reader is None and
                       self._owners[id(self.receipt_writer)]["closed"])),
                     "Productive finish permits only its one fixed result writer/readback")
        methods = dict(pin.methods)
        state = _session_pin(self)
        _require(name in methods and not self.busy, "Productive factory method/reentry differs")
        _session_set(self, "busy", True)
        try:
            value = methods[name](owner, *args, **kwargs)
            state["factory_returns"].append((label, value))
            self.hold(label, value, deadline=end)  # BEFORE next callback/guard/metadata effect.
            if self.finish_mode:
                if name == "create_file":
                    _session_set(self, "receipt_writer", value)
                else:
                    _session_set(self, "receipt_reader", value)
            _ObjectPin.check(pin)
            _session_set(self, "busy", False)
            _session_guard(self)
            _ObjectPin.check(pin)
            self.pin_for(value)
            return value
        except BaseException as error:
            _session_capture(self, "native-create", error)
            raise
        finally:
            self.unbusy()

    @_productive_frame
    def close(self, owner):
        state = _session_pin(self)
        if state["callback"] or state["guarding"] or self.busy or state["pipeline"] is not None:
            self.refuse("Productive resource close reentered owned work", unknown=True)
        row = self._owners[id(owner)]
        _row_current(row)
        _require(row["owner"] is owner, "Productive close owner replaced")
        if row["attempted"] or row["quarantined"]:
            return
        pin = row["pin"]
        try:
            state["pins"](self)
            _ObjectPin.check(pin)
        except BaseException as error:
            _session_capture(self, "close-pins", error, unknown=True)
            _row_set(row, "quarantined", True)
            return
        # Expiry/failure cannot suppress necessary real ownership cleanup, but
        # it cannot produce timely success. NativeFile uses its OWN old deadline.
        _row_set(row, "attempted", True)
        function, returned_close = dict(pin.methods)["close"], pin.returned_close
        try:
            _session_guard(self)
            _require(row["deadline"] == self.end(), "Productive close cannot retime an original resource")
        except BaseException as error:
            _session_capture(self, "close-entry", error)
        try:
            # Cleanup after expiry is allowed only for the SAME original owner.
            # A callback that replaced its pins/methods does not authorize an
            # unsafe close of the replacement, even though the attempt failed.
            _ObjectPin.check(pin)
        except BaseException as error:
            _session_capture(self, "close-post-guard-pins", error, unknown=True)
            _row_set(row, "quarantined", True)
            return
        try:
            if type(owner) in (gzip.GzipFile, tarfile.TarFile, tarfile._Stream):
                state["pipeline"] = (owner, "close")
            else:
                _session_set(self, "busy", True)
            returned = function(owner)
            _PRODUCTIVE_ROWS[id(row)]["actual_close"] = (owner, function, returned)
            _row_set(row, "close_return", returned)
            _row_set(row, "observed_return", True)
            _require(returned is None, "Productive close returned an unexpected value")
            returned_close()
            if type(owner) is files.NativeFile:
                _row_set(row, "final_info", owner.final_info)
                _row_set(row, "final_vector", _native_vector(owner.final_info))
            _row_set(row, "closed", True)
            _session_set(self, "busy", False)
            state["pipeline"] = None
            local = _session_guard(self)
            _ObjectPin.check(pin, passive=True)
            _require(local < row["deadline"], "Productive original native close returned late")
            _row_set(row, "completion", local)
        except BaseException as error:
            _session_capture(self, row["label"] + "-close", error, unknown=True)
        finally:
            state["pipeline"] = None
            self.unbusy()

    @_productive_frame
    def pipeline(self, owner, name, *args):
        """Owned tar/gzip callbacks may enter their ONE pinned stream adapter.

        Unlike a native operation this frame intentionally calls our adapters;
        the fixed adapters' guards/locks still reject native/reader reentry.
        """
        self.entry()
        state = _session_pin(self)
        if state["pipeline"] is not None:
            self.refuse("Productive archive pipeline reentered")
        _session_guard(self)
        pin, row = self.pin_for(owner)
        _require(type(owner) in (gzip.GzipFile, tarfile.TarFile) and name in ("write", "addfile"),
                 "Productive pipeline method differs")
        try:
            state["pipeline"] = (owner, name)
            result = dict(pin.methods)[name](owner, *args)
            observation, observed_pin = _returned_value(owner, name, result)
            _ObjectPin.check(pin)
            state["pipeline"] = None
            local = _session_guard(self)
            _ObjectPin.check(pin)
            _row_observe(row, name, observation, observed_pin, local, self.caps)
            return result
        except BaseException as error:
            _session_capture(self, "pipeline-" + name, error)
            raise
        finally:
            state["pipeline"] = None

    def quarantine(self, owners):
        _session_capture(self, "native-quarantine", portable.EvidenceError("Productive domain retirement is UNKNOWN"), unknown=True)
        for row in self.resources:
            if any(row["owner"] is owner for owner in owners) and not row["observed_return"]:
                _row_set(row, "quarantined", True)

    @_productive_frame
    def read_bytes(self, root, name, maximum, end):
        stream = self.create(name + "-reader", root, "open_file", name, max_bytes=maximum, deadline=end)
        pieces, count = [], 0
        while True:
            block = self.call(stream, "read", min(files.CHUNK, maximum + 1 - count))
            if not block:
                break
            count += len(block)
            _require(count <= maximum, "Productive private input exceeds bound")
            pieces.append(block)
        info = self.call(stream, "verify")
        _require(info.size == count and self.call(stream, "read", 1) == b"", "Productive private EOF differs")
        _session_close(self, stream)
        _session_check(self)
        return b"".join(pieces)

    @_productive_frame
    def write_bytes(self, root, name, raw, maximum, end):
        _require(type(raw) is bytes and len(raw) <= maximum, "Productive private bytes exceed bound")
        stream = self.create(name + "-writer", root, "create_file", name, max_bytes=maximum, deadline=end)
        for offset in range(0, len(raw), files.CHUNK):
            block = raw[offset:offset + files.CHUNK]
            _require(self.call(stream, "write", block) == len(block), "Productive native write differs")
        self.call(stream, "sync")
        info = self.call(stream, "verify")
        _require(info.size == len(raw), "Productive private write size differs")
        _session_close(self, stream)
        _session_check(self)
        return stream, self._owners[id(stream)]["final_info"]

    def set_recipient(self, recipient):
        _session_guard(self)
        _require(type(recipient) is Recipient and recipient.work is self.work,
                 "Productive actual Recipient differs")
        _session_set(self, "recipient", recipient)
        _session_set(self, "recipient_pin", _frozen_fields(recipient))

    def fail(self, phase, error):
        _session_capture(self, phase, error)
        state = _PRODUCTIVE_SESSION_PINS[id(self)]
        for row in reversed(state["rows"]):
            try:
                saved_row = _PRODUCTIVE_ROWS[id(row)]
                owner = dict(saved_row["fields"])["owner"]
                state["close"](self, owner)
            except BaseException as secondary:
                _session_capture(self, "failed-cleanup", secondary, unknown=True)
        accounted, pending = set(), []
        for row in state["rows"]:
            fields = dict(_PRODUCTIVE_ROWS[id(row)]["fields"])
            accounted.add(id(fields["owner"]))
            if fields["pin"] is not None:
                pending.append(fields["pin"])
        visited = set()
        while pending:
            pin = pending.pop()
            if id(pin) in visited:
                continue
            visited.add(id(pin))
            fields = dict(_PRODUCTIVE_PINS[id(pin)][3][1])
            accounted.add(id(fields["owner"]))
            pending.extend(fields["children"])
        if any(id(owner) not in accounted for _label, owner in state["factory_returns"]):
            _session_capture(self, "unregistered-actual-return", error, unknown=True)
        if state["unknown"] and not any(item is self for item in _QUARANTINE):
            _QUARANTINE.append(self)
        if not isinstance(state["first"], Exception):
            raise state["first"]
        raw = (b'{"result":"FAILED","retirement":"' + (b"UNKNOWN" if state["unknown"] else b"OWNED_CLEANUP_ONLY") +
               b'","scope":"PRODUCTIVE_WINDOWS"}\n')
        raise WindowsEvidenceError(state["first"], raw, state["unknown"]) from None


def _session_create(session, label, owner, name, *args, **kwargs):
    if type(session) is _ProductiveSession:
        return session.create(label, owner, name, *args, **kwargs)
    return session.hold(label, getattr(owner, name)(*args, **kwargs))


def _session_call(session, owner, name, *args, **kwargs):
    if type(session) is _ProductiveSession:
        return session.call(owner, name, *args, **kwargs)
    return getattr(owner, name)(*args, **kwargs)


def _session_executable(session, path, end):
    if type(session) is _ProductiveSession:
        _session_guard(session)
        result = _executable_owned(path, end, session)
        _session_guard(session)
        return result
    return _executable(path, end)


def _adapter_register(adapter):
    session = adapter.session
    state = _session_fields(session)
    _require(len(state["adapters"]) < 2 * files.MAX_MEMBERS, "Productive adapter bound exceeded")
    methods = tuple((name, function) for name, function in type(adapter).__dict__.items() if callable(function))
    digest = getattr(adapter, "digest", None)
    saved = {"adapter": adapter, "kind": type(adapter), "dictionary": adapter.__dict__,
             "fields": _frozen_fields(adapter), "methods": methods, "session": session,
             "digest": None if digest is None else _reference_pin(digest, ("update", "digest", "hexdigest")),
             "digest_value": None if digest is None else digest.digest(), "completion": None}
    _PRODUCTIVE_ADAPTERS[id(adapter)] = saved
    state["adapters"].append(adapter)
    state["active_adapters"].append(adapter)
    _adapter_current(adapter)


def _adapter_current(adapter):
    saved = _PRODUCTIVE_ADAPTERS.get(id(adapter))
    _require(saved is not None and saved["adapter"] is adapter and type(adapter) is saved["kind"] and
             adapter.__dict__ is saved["dictionary"], "Productive original stream adapter differs")
    _fields_current(adapter, saved["fields"])
    for name, function in saved["methods"]:
        _require(getattr(saved["kind"], name) is function and name not in adapter.__dict__,
                 "Productive original adapter method changed")
    if saved["digest"] is not None:
        _reference_current(saved["digest"])
        digest = saved["digest"][0]
        _require(digest.digest() == saved["digest_value"], "Productive original stream digest changed")
    if type(adapter) is _ProductiveReader and adapter.node is not None:
        _require(type(adapter.node) is adapter.node_kind, "Productive original expected-node type changed")
        _fields_current(adapter.node, adapter.node_pin)
    return saved


def _adapter_set(adapter, name, value):
    saved = _PRODUCTIVE_ADAPTERS[id(adapter)]
    _require(name in ("busy", "count", "done"), "Productive adapter transition differs")
    saved["fields"] = _changed_field(adapter, saved["fields"], name, value)


def _adapter_begin(adapter):
    try:
        saved = _adapter_current(adapter)
    except BaseException as error:
        saved = _PRODUCTIVE_ADAPTERS.get(id(adapter))
        if saved is not None and saved["adapter"] is adapter:
            _session_capture(saved["session"], "productive-original-adapter", error)
        raise
    if adapter.busy or adapter.done:
        saved["session"].refuse("Productive original stream adapter reentered or completed")
    _adapter_set(adapter, "busy", True)
    return saved


def _adapter_unbusy(adapter):
    saved = _PRODUCTIVE_ADAPTERS[id(adapter)]
    try:
        _adapter_set(adapter, "busy", False)
    except BaseException as error:
        _session_capture(saved["session"], "productive-adapter-state", error)
        # No rebasing or reuse after mutation: the original session is failed.


def _adapter_complete(adapter, completion):
    saved = _adapter_current(adapter)
    _require(saved["completion"] is None and not adapter.done, "Productive adapter completion repeated")
    saved["completion"] = completion
    _adapter_set(adapter, "done", True)
    active = _session_pin(saved["session"])["active_adapters"]
    index = next((i for i, item in enumerate(active) if item is adapter), None)
    _require(index is not None, "Productive active adapter slot disappeared")
    del active[index]


class _ProductiveWriter:
    """Only the original archive sink; trailer writes spend ordinary work too."""

    def __init__(self, session, raw):
        self.session, self.raw = session, raw
        self.count, self.busy, self.done = 0, False, False
        _adapter_register(self)

    def write(self, data):
        saved = _adapter_begin(self)
        session, raw, count = self.session, self.raw, self.count
        try:
            _require(type(data) is bytes, "Productive archive block type differs")
            result = session.call(raw, "write", data)
            _adapter_current(self)
            _require(type(result) is int and result == len(data), "Productive archive write was incomplete")
            _adapter_set(self, "count", count + result)
            return result
        except BaseException as error:
            _session_capture(saved["session"], "productive-archive-writer", error)
            raise
        finally:
            _adapter_unbusy(self)

    def flush(self):
        saved = _adapter_begin(self)
        session, raw = self.session, self.raw
        try:
            session.call(raw, "sync")
            _adapter_current(self)
        except BaseException as error:
            _session_capture(saved["session"], "productive-archive-flush", error)
            raise
        finally:
            _adapter_unbusy(self)

    def finish(self):
        saved = _adapter_begin(self)
        try:
            self.session.entry()
            row = self.session._owners[id(self.raw)]
            _row_current(row, full=True)
            _require(row["closed"] and row["completion"] is not None and
                     row["final_info"].size == self.count, "Productive actual archive sink close/count differs")
            _adapter_complete(self, (self.raw, row["completion"], self.count))
        except BaseException as error:
            _session_capture(saved["session"], "productive-writer-finish", error)
            raise
        finally:
            _adapter_unbusy(self)


class _ProductiveReader:
    def __init__(self, session, stream, node=None):
        self.session, self.stream, self.node = session, stream, node
        self.digest, self.count, self.busy, self.done = hashlib.sha256(), 0, False, False
        self.node_kind = type(node)
        self.node_pin = _frozen_fields(node) if node is not None else None
        _adapter_register(self)

    def check(self, count):
        _adapter_current(self)
        session, stream, node = self.session, self.stream, self.node
        _require(type(count) is int and self.count == count, "Productive archive reader original count changed")
        _session_guard(session)
        _adapter_current(self)
        if node is not None:
            _require(session.invoke_e("_productive_node_guard", node) is node,
                     "Productive expected node guard differs")
            _adapter_current(self)
        info = session.call(stream, "verify")
        _adapter_current(self)
        if node is not None:
            _require(_native_vector(info) == node.native, "Productive actual stream metadata differs")
        _require(self.count == count, "Productive stream callback changed ledger")

    def read(self, size=-1):
        saved = _adapter_begin(self)
        session, stream, node, digest, before = self.session, self.stream, self.node, self.digest, self.count
        try:
            _require(type(size) is int and 0 <= size <= files.MAX_READ_BYTES,
                     "Productive stream must use bounded explicit reads")
            self.check(before)
            value = session.call(stream, "read", size)
            _adapter_current(self)
            _require(type(value) is bytes and len(value) <= size and self.count == before,
                     "Productive actual stream read differs")
            _adapter_set(self, "count", before + len(value))
            if node is not None:
                _require(self.count <= node.bytes, "Productive tar stream exceeds expected length")
                digest.update(value)  # EXACT bytes handed to tar, never an earlier different stream.
                saved["digest_value"] = digest.digest()
            self.check(self.count)
            return value
        except BaseException as error:
            _session_capture(saved["session"], "productive-stream", error)
            raise
        finally:
            _adapter_unbusy(self)

    def seek(self, offset, whence=0):
        saved = _adapter_begin(self)
        session, stream = self.session, self.stream
        try:
            _require(self.node is None, "Productive tar stream is sequential only")
            self.check(self.count)
            value = session.call(stream, "seek", offset, whence)
            self.check(self.count)
            return value
        except BaseException as error:
            _session_capture(saved["session"], "productive-packet-seek", error)
            raise
        finally:
            _adapter_unbusy(self)

    def tell(self):
        saved = _adapter_begin(self)
        session, stream = self.session, self.stream
        try:
            _require(self.node is None, "Productive tar stream is sequential only")
            self.check(self.count)
            value = session.call(stream, "tell")
            self.check(self.count)
            return value
        except BaseException as error:
            _session_capture(saved["session"], "productive-packet-tell", error)
            raise
        finally:
            _adapter_unbusy(self)

    def finish(self):
        saved = _adapter_begin(self)
        session, stream, node = self.session, self.stream, self.node
        try:
            _require(node is not None and self.count == node.bytes and self.digest.hexdigest() == node.sha256,
                     "Productive tar bytes/hash differ")
            self.check(self.count)
            _require(session.call(stream, "read", 1) == b"", "Productive tar stream lacks EOF")
            self.check(self.count)
            _session_close(session, stream)
            _session_check(session)
            _adapter_current(self)
            _adapter_complete(self, (stream, node, self.count, self.digest.hexdigest(),
                                      session._owners[id(stream)]["completion"]))
        except BaseException as error:
            _session_capture(saved["session"], "productive-tar-finish", error)
            raise
        finally:
            _adapter_unbusy(self)

    def finish_packet(self):
        saved = _adapter_begin(self)
        try:
            _require(self.node is None, "Productive packet parser completion differs")
            _session_guard(self.session)
            _adapter_current(self)
            # The parser returned, but its stream is STILL owned for hash/copy/close.
            _adapter_complete(self, ("PACKET_PARSER_RETURN_NOT_STREAM_CLOSE", self.stream, self.session.last_local))
        except BaseException as error:
            _session_capture(saved["session"], "productive-packet-finish", error)
            raise
        finally:
            _adapter_unbusy(self)


def _productive_archive(session, snapshot, destination, end):
    _session_guard(session, whole=True)
    _require(session.invoke_e("_productive_check_snapshot", snapshot.entries) is snapshot.entries,
             "Productive snapshot comparison returned replacement entries")
    _session_check(session)
    raw = session.create("plaintext-archive", destination, "create_file", "evidence.tar.gz",
                         max_bytes=portable.MAX_ARCHIVE_BYTES, deadline=end)
    writer = _ProductiveWriter(session, raw)
    compressed = session.construct("plaintext-gzip", gzip.GzipFile, fileobj=writer, mode="wb", filename="", mtime=0)
    archive = session.construct("plaintext-tar", tarfile.open, fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT)
    try:
        for name, stamp in sorted(snapshot.entries.items()):
            _session_guard(session)
            node = session.invoke_e("_productive_expected_node", name)
            _session_check(session)
            _require(node.relative == name and node.native == _native_vector(stamp),
                     "Productive actual snapshot node differs")
            _require(len(name.encode("utf-8")) <= 1024, "Evidence member name exceeds archive bound")
            info = tarfile.TarInfo("evidence/" + name if name else "evidence")
            info.uid, info.gid, info.uname, info.gname, info.mtime = 0, 0, "", "", 0
            if stamp.is_directory:
                _require(node.kind == "directory" and node.bytes is None and node.sha256 is None,
                         "Productive directory sentinel differs")
                info.type, info.mode = tarfile.DIRTYPE, 0o700
                session.pipeline(archive, "addfile", info)
            else:
                _require(node.kind == "file" and type(node.bytes) is int and node.bytes == stamp.size,
                         "Productive actual file length differs")
                info.mode, info.size = 0o600, stamp.size
                stream = session.create("archive-member", snapshot, "open_file", name)
                reader = _ProductiveReader(session, stream, node)
                session.pipeline(archive, "addfile", info, reader)
                reader.finish()
        _session_close(session, archive)
        _session_check(session)
        _session_close(session, archive.fileobj)
        _session_check(session)
        _session_close(session, compressed)
        _session_check(session)
        session.call(raw, "sync")
        session.call(raw, "verify")
        _session_close(session, raw)
        _session_check(session)
        writer.finish()
        session.call(snapshot, "verify")
        _session_guard(session, whole=True)
        _require(session.invoke_e("_productive_check_snapshot", snapshot.entries) is snapshot.entries,
                 "Productive final snapshot comparison differs")
        _session_check(session)
    except BaseException as error:
        _session_capture(session, "productive-archive", error)
        raise


def _productive_hash(session, stream):
    digest, count = hashlib.sha256(), 0
    before = session.call(stream, "verify")
    while True:
        block = session.call(stream, "read", files.CHUNK)
        if not block:
            break
        count += len(block)
        _require(count <= portable.MAX_CIPHERTEXT_BYTES, "Productive ciphertext exceeds bound")
        digest.update(block)
    after = session.call(stream, "verify")
    _require(_native_vector(before) == _native_vector(after) and after.size == count and
             session.call(stream, "read", 1) == b"", "Productive ciphertext length/EOF/native binding differs")
    return digest.hexdigest(), count, after


def _productive_close_ordinary(session):
    _session_guard(session, whole=True)
    _require(session.command is None and session.keyring_cap is None and not session.finish_mode and
             not _session_pin(session)["active_adapters"], "Productive ordinary work is not complete")
    for row in reversed(session.resources):
        _session_close(session, row["owner"])
    _session_check(session)
    _session_pin(session)["pins"](session, whole=True)
    _require(all(row["closed"] and row["observed_return"] and row["close_return"] is None and
                 row["completion"] is not None and not row["quarantined"] for row in session.resources),
             "Productive ordinary resources lack actual timely normal closes")
    _session_set(session, "ordinary_close_observation", (tuple(session.resources), _session_guard(session)))
    return session.ordinary_close_observation


def _productive_accounting(resources, borrowed):
    direct, nested, pins, memory = {}, {}, {}, {}
    contributions = 0

    def retain(pin, destination):
        nonlocal contributions
        if id(pin.owner) in direct or id(pin.owner) in nested:
            return
        destination[id(pin.owner)] = pin.owner
        if pin.pin_slots is not None:
            contributions += len(pin.pin_slots)
            for cell in pin.pin_slots:
                pins[id(cell)] = cell
        for reference in pin.references:
            memory[id(reference[0])] = reference[0]
        for child in pin.children:
            retain(child, nested)

    for row in resources:
        retain(row["pin"], direct)
    _require(not any(id(pin.owner) in direct or id(pin.owner) in nested for pin in borrowed),
             "Productive backend attempted to own a borrowed root")
    return {"directOriginalCloseCalls": len(resources), "directOriginalOwners": len(direct),
            "transitivelyClosedOriginalOwners": len(nested), "uniqueOriginalPinReferences": len(pins),
            "originalPinReleaseContributions": contributions, "borrowedRootsNotClosedHere": len(borrowed),
            "memoryHelpersRetainedWithoutIndependentCloseClaim": len(memory),
            "pinReleaseMeaning": "OWNER_CONTRIBUTION_NOT_EARLY_BORROWED_RAW_HANDLE_CLOSE",
            "timingCapacityQualification": "NOT_PERFORMED"}


def _finish_initial_productive(session, binding):
    try:
        return _finish_initial_productive_owned(session, binding)
    except BaseException as error:
        saved = _PRODUCTIVE_SESSION_PINS.get(id(session))
        if saved is not None and saved["session"] is session:
            _session_capture(session, "productive-finish", error)
        raise


def _finish_initial_productive_owned(session, binding):
    _require(type(session) is _ProductiveSession and session.binding is binding and
             _PRODUCTIVE_SESSIONS.get(id(binding)) is session,
             "Productive Windows finish registration differs")
    session.entry()
    if session.known_close is not None or session.finish_mode or session.keyring_cap is not None:
        session.refuse("Productive Windows finish is once-only after ordinary work")
    if session.ordinary_close_observation is None:
        session.refuse("Productive Windows finish lacks actual ordinary-close return")
    prior, completion = session.ordinary_close_observation
    _require(type(prior) is tuple and len(prior) == len(session.resources) and
             all(left is right for left, right in zip(prior, session.resources)) and
             type(completion) is float and completion < session.caps.workEndLocal and
             all(row["closed"] and row["observed_return"] and row["completion"] is not None for row in prior),
             "Productive finish lacks original ordinary-close return")
    _session_set(session, "finish_mode", True)  # NOT a new interval: same original caps object.
    _session_guard(session, whole=True)
    name = session.label + "-result-" + uuid.uuid4().hex + ".json"
    _require(re.fullmatch(r"(?:recipient-validation|encrypted-export)-result-[0-9a-f]{32}\.json", name),
             "Productive original private result name differs")
    _session_set(session, "result_name", name)
    value = {"schema": 1, "operation": session.label,
             "scope": "INITIAL_RECIPIENT_PRODUCTIVE_WINDOWS_PRIOR_FACTS_V1",
             "result": "PENDING_RESULT_WRITER_READBACK_AND_FUNCTION_RETURN",
             "outerOwnerClose": "PENDING", "ownWriterClose": "PENDING", "ownReadback": "NOT_STARTED",
             "ordinaryResources": [{"label": row["label"], "coverage": row["coverage"],
                                    "normalCloseReturned": True} for row in prior],
             "priorResourceAccounting": _productive_accounting(prior, session.borrowed_pins),
             "commands": session.commands, "priorGuardReturns": session.calls,
             "retirement": "PRIOR_OWNED_RESOURCES_KNOWN_NOT_OUTER_CLOSE"}
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    _require(0 < len(raw) <= MAX_RECORD_BYTES, "Productive private result exceeds original bound")
    writer, written = session.write_bytes(session.work, name, raw, MAX_RECORD_BYTES,
                                          session.caps.operationFinishEndLocal)
    reader = session.create(name + "-reader", session.work, "open_file", name,
                             max_bytes=MAX_RECORD_BYTES, deadline=session.caps.operationFinishEndLocal)
    opened = session.call(reader, "verify")
    _require(_native_vector(opened) == _native_vector(written), "Productive result readback native binding differs")
    digest, count = hashlib.sha256(), 0
    pieces = []
    while True:
        block = session.call(reader, "read", files.CHUNK)
        if not block:
            break
        count += len(block)
        _require(count <= MAX_RECORD_BYTES, "Productive result readback exceeds bound")
        digest.update(block)
        pieces.append(block)
    readback = session.call(reader, "verify")
    _require(count == len(raw) and b"".join(pieces) == raw and digest.hexdigest() == hashlib.sha256(raw).hexdigest()
             and _native_vector(readback) == _native_vector(written) and
             session.call(reader, "read", 1) == b"", "Productive result readback/EOF differs")
    _session_close(session, reader)
    _session_check(session)
    _session_set(session, "receipt", (name, raw, writer, reader, written, readback, digest.hexdigest(), count))
    _session_guard(session, whole=True)
    resources = tuple(session.resources)
    _require(all(row["closed"] and row["observed_return"] and row["completion"] is not None and
                 not row["quarantined"] for row in resources), "Productive finish has an unclosed resource")
    observations = tuple((row["owner"], row["pin"], row["coverage"], row["close_return"],
                          row["completion"], tuple(row["operations"])) for row in resources)
    observations += tuple(session.observations)
    result = _ProductiveKnownClose(session, resources, session.receipt, observations)
    _session_set(session, "known_close", result)
    sealed_rows = tuple((row, _PRODUCTIVE_ROWS[id(row)]["fields"],
                         _PRODUCTIVE_ROWS[id(row)]["actual_close"], tuple(_PRODUCTIVE_ROWS[id(row)]["operations"]))
                        for row in resources)
    receipt_pin = (_data_pin(written), _data_pin(readback), hashlib.sha256(raw).hexdigest(), len(raw))
    _PRODUCTIVE_CLOSES[id(result)] = (result, session, _frozen_fields(result), sealed_rows, receipt_pin)
    return result


def _productive_register_return(session, result, known_close):
    # FIRST capture after actual finish return. No disk record attests this fact.
    _require(known_close is session.known_close and _PRODUCTIVE_CLOSES.get(id(known_close), (None,))[0]
             is known_close, "Productive actual finish return differs")
    _session_set(session, "finish_return", known_close)
    _session_guard(session, whole=True)
    _session_set(session, "finished", True)
    _session_set(session, "result", result)
    _PRODUCTIVE_RESULTS[id(result)] = (result, session, _frozen_fields(result))
    return result


def _validate_initial_productive(binding):
    session = _ProductiveSession(binding, True)
    try:
        _native()
        view, work, end = session.view, session.work, session.caps.workEndLocal
        session.call(work, "verify")
        _empty(work, session, end)
        public_key = view.public_key_raw
        _require(type(public_key) is bytes and 0 < len(public_key) <= portable.MAX_KEY_BYTES,
                 "Productive original public key exceeds bound")

        def unique(pairs):
            value = {}
            for name, item in pairs:
                _require(type(name) is str and name not in value, "Productive original policy has duplicate keys")
                value[name] = item
            return value

        # Only DATA extraction from E's original authenticated policy. E/PC alone
        # rederive authority, policy/source, current expiry and original key bytes.
        policy = json.loads(view.policy_raw, object_pairs_hook=unique)
        expected = policy["recipient"]["fingerprint"]
        _require(type(expected) is str and re.fullmatch(r"[0-9a-fA-F]{40}", expected),
                 "Productive original fingerprint differs")
        job = view.source.job_id
        _require(type(job) is str and re.fullmatch(r"[0-9a-f]{32}", job), "Productive original child job differs")
        packets = portable._public_armor(public_key)
        _session_guard(session)
        installed = session.effect("installed-gpg-lookup", shutil.which, "gpg.exe")
        _require(installed is not None, "Installed native GPG is required; no download fallback")
        executable = Path(installed)
        executable_sha256 = _session_executable(session, executable, end)
        session.create("gpg-home-created", work, "create_directory", "gnupg", deadline=end)
        session.create("gpg-temp-created", work, "create_directory", "tmp", deadline=end)
        session.write_bytes(work, "recipient.asc", public_key, portable.MAX_KEY_BYTES, end)
        session.write_bytes(work, "recipient.gpg", packets, portable.MAX_KEY_BYTES, end)
        seed = Recipient(work, executable, executable_sha256, work.identity, expected.upper(), "", 0,
                         hashlib.sha256(public_key).hexdigest(), job)
        session.set_recipient(seed)
        version, _ = _gpg(session, seed, ["--version"], end)
        _require(re.match(rb"gpg \(GnuPG\) 2\.[0-9]+\.[0-9]+(?:[ \r\n]|$)", version),
                 "Installed executable did not identify as GnuPG 2")
        common = ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint"]
        shown, _ = _gpg(session, seed, common + ["--import-options", "show-only", "--import",
                                               str(work.path / "recipient.asc")], end)
        fingerprint, expiry = portable._key_identity(shown, seed.fingerprint)
        selected, _ = _gpg(session, seed, common + ["--list-keys"], end)
        _require(portable._key_identity(selected, seed.fingerprint) == (fingerprint, expiry),
                 "Selected recipient differs from validated public key")
        recipient = dataclasses.replace(seed, encryption_fingerprint=fingerprint, expires_at=expiry)
        session.set_recipient(recipient)
        _productive_close_ordinary(session)
        known = _finish_initial_productive(session, binding)
        result = _ProductiveValidationReturn(binding, session, recipient, known.observations, known)
        return _productive_register_return(session, result, known)
    except BaseException as error:
        _session_fail(session, "productive-validation", error)


def _export_initial_productive(binding):
    session = _ProductiveSession(binding, False)
    try:
        _native()
        view, recipient, end = session.view, session.view.recipient, session.caps.workEndLocal
        session.set_recipient(recipient)
        evidence, output, work = view.payload, view.output, session.work
        for owner in (evidence, output, work):
            session.call(owner, "verify")
        _disjoint(evidence, work, output)
        _empty(output, session, end)
        _session_guard(session, whole=True)
        _require(not session.keyring_done and session.keyring_cap is None, "Productive keyring may begin only once")
        cap = session.invoke_e("_productive_keyring_begin")
        _session_set(session, "keyring_cap", cap)
        _session_set(session, "keyring_kind", type(cap))
        _session_set(session, "keyring_pin", _frozen_fields(cap))
        _require(cap.limitNs == 30 * 10 ** 9 and cap.workEndNs <= session.caps.workEndNs and
                 type(cap.workEndLocal) is float and cap.workEndLocal <= session.caps.workEndLocal,
                 "Productive original keyring cap differs")
        _session_guard(session)
        listing, _ = _gpg(session, recipient, ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint",
                                              "--list-keys"], cap.workEndLocal)
        _require(portable._key_identity(listing, recipient.fingerprint) ==
                 (recipient.encryption_fingerprint, recipient.expires_at), "Recipient keyring changed before export")
        _session_guard(session)
        _require(session.invoke_e("_productive_keyring_complete", cap) is cap,
                 "Productive actual keyring completion differs")
        _session_set(session, "keyring_return", cap)
        _session_set(session, "keyring_cap", None)
        _session_set(session, "keyring_done", True)
        _session_guard(session)
        snapshot = session.create("original-evidence-snapshot", evidence, "snapshot",
                                  max_bytes=portable.MAX_BYTES, max_members=portable.MAX_MEMBERS, deadline=end)
        _require(session.invoke_e("_productive_check_snapshot", snapshot.entries) is snapshot.entries,
                 "Productive original snapshot comparison differs")
        _session_guard(session, whole=True)
        private = session.create("export-work", work, "create_directory", "export-" + uuid.uuid4().hex, deadline=end)
        _productive_archive(session, snapshot, private, end)
        plaintext = session.create("plaintext-input-pin", private, "open_file", "evidence.tar.gz",
                                   max_bytes=portable.MAX_ARCHIVE_BYTES, deadline=end)
        _, status = _gpg(session, recipient, ["--cipher-algo", "AES256", "--compress-algo", "none",
                          "--no-encrypt-to", "--recipient", recipient.encryption_fingerprint + "!",
                          "--output", "-", "--encrypt", str(plaintext.path)], end,
                        output=private, output_name=portable.ARTIFACT, encryption=True,
                        borrowed_owners=(private, plaintext))
        session.call(plaintext, "verify")
        lines = status.splitlines()
        _require(sum(line.startswith(b"[GNUPG:] BEGIN_ENCRYPTION ") for line in lines) == 1 and
                 lines.count(b"[GNUPG:] END_ENCRYPTION") == 1 and
                 not any(line.startswith((b"[GNUPG:] FAILURE", b"[GNUPG:] ERROR")) for line in lines),
                 "GPG did not confirm complete evidence encryption")
        encrypted = session.create("private-ciphertext-reader", private, "open_file", portable.ARTIFACT,
                                   max_bytes=portable.MAX_CIPHERTEXT_BYTES, deadline=end)
        packets = _ProductiveReader(session, encrypted)
        portable._ciphertext_stream(packets, encrypted.initial_info.size, recipient.encryption_fingerprint)
        packets.finish_packet()
        session.call(encrypted, "verify")
        session.call(encrypted, "seek", 0)
        digest, size, private_info = _productive_hash(session, encrypted)
        _session_guard(session, whole=True)
        manifest_raw = session.invoke_e("_productive_manifest", digest, size)
        _session_check(session)
        _require(type(manifest_raw) is bytes and 0 < len(manifest_raw) <= MAX_MANIFEST_BYTES,
                 "Productive canonical manifest bytes differ")
        _session_guard(session, whole=True)
        published = session.create("public-ciphertext-writer", output, "create_file", portable.ARTIFACT,
                                   max_bytes=size, deadline=end)
        session.call(encrypted, "seek", 0)
        copied = 0
        for block in iter(lambda: session.call(encrypted, "read", files.CHUNK), b""):
            copied += len(block)
            _require(copied <= size and session.call(published, "write", block) == len(block),
                     "Productive public ciphertext write differs")
        _require(copied == size, "Productive ciphertext copy length differs")
        session.call(published, "sync")
        _require(session.call(published, "verify").size == size, "Productive public ciphertext size differs")
        _session_close(session, published)
        _session_check(session)
        session.write_bytes(output, portable.MANIFEST, manifest_raw, MAX_MANIFEST_BYTES, end)
        session.call(snapshot, "verify")
        _require(session.invoke_e("_productive_check_snapshot", snapshot.entries) is snapshot.entries,
                 "Productive final original snapshot comparison differs")
        sealed = session.create("sealed-output-snapshot", output, "snapshot",
                                max_bytes=files.MAX_FILE_BYTES, max_members=3, deadline=end)
        _require(set(sealed.entries) == {"", portable.ARTIFACT, portable.MANIFEST},
                 "Productive output roster differs")
        public_reader = session.create("sealed-ciphertext-reader", sealed, "open_file", portable.ARTIFACT)
        actual_digest, actual_size, public_info = _productive_hash(session, public_reader)
        _require((actual_digest, actual_size) == (digest, size), "Productive public/private ciphertext bytes differ")
        _session_close(session, public_reader)
        _session_check(session)
        actual_manifest = session.read_bytes(output, portable.MANIFEST, MAX_MANIFEST_BYTES, end)
        _require(actual_manifest == manifest_raw and
                 session.invoke_e("_productive_manifest", digest, size) == manifest_raw,
                 "Productive actual manifest readback differs")
        session.call(sealed, "verify")
        session.call(snapshot, "verify")
        _session_guard(session, whole=True)
        artifact = _ProductiveArtifact(portable.ARTIFACT, digest, size, _native_vector(public_info))
        _session_set(session, "artifact_sources", (encrypted, private_info, published, public_reader, public_info, sealed))
        _PRODUCTIVE_ARTIFACTS[id(artifact)] = (artifact, session, _frozen_fields(artifact), session.artifact_sources)
        _productive_close_ordinary(session)
        known = _finish_initial_productive(session, binding)
        result = _ProductiveExportReturn(binding, session, manifest_raw, artifact, known.observations, known)
        return _productive_register_return(session, result, known)
    except BaseException as error:
        _session_fail(session, "productive-export", error)


def _checked_productive_return_unlatched(result, binding, kind):
    # PASSIVE. In particular NO E call, RAW/LOCAL sample or borrowed-root verify.
    saved = _PRODUCTIVE_RESULTS.get(id(result))
    _require(saved is not None and saved[0] is result and type(result) is kind and result.binding is binding,
             "Productive Windows result is not original registered currency")
    session = saved[1]
    _fields_current(result, saved[2])
    _require(type(session) is _ProductiveSession and session.binding is binding and session.result is result and
             session.finished and session.original is None and not session.unknown and not session.busy,
             "Productive Windows result state differs")
    _session_pin(session)["pins"](session, whole=True, passive=True)
    state = _session_pin(session)
    _require(not state["guarding"] and not state["callback"] and state["pipeline"] is None and
             not state["active_adapters"] and session.command is None,
             "Productive Windows result was checked inside unfinished work")
    _require(all(adapter.done and not adapter.busy and _PRODUCTIVE_ADAPTERS[id(adapter)]["completion"] is not None
                 for adapter in state["adapters"]) and
             all(command["completed"] is not None for command in state["commands"]),
             "Productive Windows actual helper returns are missing")
    known = result.known_close
    closed = _PRODUCTIVE_CLOSES.get(id(known))
    _require(closed is not None and closed[0] is known and closed[1] is session and session.known_close is known and
             session.finish_return is known and result.observations is known.observations and
             known.session is session and known.receipt is session.receipt,
             "Productive Windows known-close return differs")
    _fields_current(known, closed[2])
    _require(len(known.resources) == len(session.resources) and
             all(original is current for original, current in zip(known.resources, session.resources)) and
             all(row["closed"] and row["observed_return"] and row["close_return"] is None and
                 row["completion"] is not None and not row["quarantined"] for row in known.resources),
             "Productive Windows original closes changed")
    _require(len(closed[3]) == len(known.resources), "Productive sealed resource count differs")
    for (row, fields, actual_close, operations), original in zip(closed[3], known.resources):
        saved_row = _row_current(row, full=True)
        _require(row is original and saved_row["fields"] is fields and
                 saved_row["actual_close"] is actual_close and
                 len(operations) == len(saved_row["operations"]) and
                 all(left is right for left, right in zip(operations, saved_row["operations"])) and
                 type(row["completion"]) is float and 0 <= row["completion"] < row["deadline"],
                 "Productive sealed original close/observations changed")
    name, raw, writer, reader, written, readback, digest, size = known.receipt
    _require(writer is session.receipt_writer and reader is session.receipt_reader and writer is not reader and
             name == session.result_name and len(raw) == size == closed[4][3] and
             digest == closed[4][2] == hashlib.sha256(raw).hexdigest() and
             _native_vector(written) == _native_vector(readback) and written.size == size,
             "Productive original result writer/readback receipt changed")
    _data_current(closed[4][0])
    _data_current(closed[4][1])
    if kind is _ProductiveValidationReturn:
        _require(result.recipient is session.recipient, "Productive original validation Recipient differs")
    else:
        artifact = result.artifact
        source = _PRODUCTIVE_ARTIFACTS.get(id(artifact))
        _require(source is not None and source[0] is artifact and source[1] is session and
                 source[3] is session.artifact_sources and type(artifact) is _ProductiveArtifact,
                 "Productive output Artifact lacks actual registered readback")
        _fields_current(artifact, source[2])
        _require(_native_vector(source[3][4]) == artifact.native and source[3][4].size == artifact.size,
                 "Productive original public readback changed")
    return result


def _checked_productive_return(result, binding, kind):
    saved = _PRODUCTIVE_RESULTS.get(id(result))
    try:
        return _checked_productive_return_unlatched(result, binding, kind)
    except BaseException as error:
        if saved is not None and saved[0] is result:
            _session_capture(saved[1], "productive-passive-result", error)
        raise


def _checked_productive_validation_return(result, binding):
    return _checked_productive_return(result, binding, _ProductiveValidationReturn)


def _checked_productive_export_return(result, binding):
    return _checked_productive_return(result, binding, _ProductiveExportReturn)


_PRODUCTIVE_FUNCTION_NAMES = (
    "files", "processes", "portable", "primitives", "ordinary", "gzip", "tarfile", "io", "time", "os", "hashlib",
    "json", "dataclasses", "uuid", "shutil", "stat", "struct", "re", "copyreg",
    "_require", "_exception_detail", "_native", "_empty", "_disjoint", "_environment", "_read", "_write",
    "Recipient", "Path", "_ProductiveSession", "_ObjectPin", "_ProductiveWriter", "_ProductiveReader",
    "_ProductiveValidationReturn", "_ProductiveExportReturn", "_ProductiveArtifact", "_ProductiveKnownClose",
    "MAX_RECORD_BYTES", "MAX_MANIFEST_BYTES", "MAX_EXECUTABLE_BYTES", "_QUARANTINE",
    "_PRODUCTIVE_SESSIONS", "_PRODUCTIVE_RESULTS", "_PRODUCTIVE_ARTIFACTS", "_PRODUCTIVE_CLOSES",
    "_PRODUCTIVE_PINS", "_PRODUCTIVE_APIS", "_PRODUCTIVE_SESSION_PINS", "_PRODUCTIVE_ROWS",
    "_PRODUCTIVE_ADAPTERS", "_PRODUCTIVE_COMMANDS", "_PRODUCTIVE_COMMAND_PINS",
    "_productive_e", "_native_vector", "_same_scalar", "_frozen_fields", "_fields_current", "_changed_field",
    "_data_pin", "_data_current", "_api_pin", "_api_current", "_reference_pin", "_reference_current",
    "_class_pin", "_class_current", "_tarinfo_copy_cache",
    "_session_pin", "_session_fields", "_session_set", "_row_current", "_row_set", "_row_observe", "_returned_value",
    "_session_capture", "_session_check", "_session_guard", "_session_close", "_session_fail", "_session_returned_scope",
    "_command_current", "_command_set", "_command_update", "_productive_frame",
    "_adapter_register", "_adapter_current", "_adapter_set",
    "_adapter_begin", "_adapter_unbusy", "_adapter_complete",
    "_session_create", "_session_call", "_session_executable", "_executable_owned", "_executable_reader", "_gpg",
    "_productive_archive", "_productive_hash", "_productive_close_ordinary", "_productive_accounting",
    "_finish_initial_productive", "_finish_initial_productive_owned",
    "_productive_register_return", "_validate_initial_productive", "_export_initial_productive",
    "_checked_productive_return_unlatched", "_checked_productive_return",
    "_checked_productive_validation_return", "_checked_productive_export_return")
