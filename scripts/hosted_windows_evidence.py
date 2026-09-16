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
import gzip
import hashlib
import json
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


def _exception_detail(error):
    """Finite, cycle/accessor-safe PRIVATE details; incomplete graphs mean UNKNOWN.

    Supplier notes and the process owner's explicit carrier are BOTH inspected.
    No assumption is made that ``str(error)`` includes notes or secondary errors.
    This is bounded diagnostic handling of cooperating code, not an execution
    sandbox for a malicious Python ``__str__``/property which never returns.
    """
    result = {"nodes": [], "incomplete": False, "retirementUnknown": False}
    remaining = 32 * 1024

    def incomplete():
        result["incomplete"] = result["retirementUnknown"] = True

    def text(value, limit=2048):
        nonlocal remaining
        if type(value) is not str:
            incomplete()
            return "<non-text diagnostic>"
        admitted = min(limit, remaining)
        if len(value) > admitted:
            incomplete()
        value = value[:admitted]
        remaining -= len(value)
        if "UNKNOWN" in value:
            result["retirementUnknown"] = True
        return value

    def attribute(value, name, default=None):
        try:
            return getattr(value, name, default)
        except BaseException:
            incomplete()
            return default

    pending, seen = [("original", error)], {}
    while pending:
        edge, current = pending.pop(0)
        if current is None:
            continue
        if not isinstance(current, BaseException):
            incomplete()
            continue
        if len(result["nodes"]) >= 64:
            incomplete()
            break
        if id(current) in seen:
            result["nodes"].append({"edge": edge, "reference": seen[id(current)]})
            continue
        index = len(result["nodes"])
        seen[id(current)] = index
        try:
            message = str(current)
        except BaseException:
            incomplete()
            message = "<exception message unavailable>"
        try:
            kind = type(current).__name__
        except BaseException:
            incomplete()
            kind = "<exception type unavailable>"
        row = {"edge": edge, "type": text(kind, 128), "message": text(message)}
        result["nodes"].append(row)
        notes = attribute(current, "__notes__", ())
        if type(notes) not in (list, tuple):
            incomplete()
        else:
            if len(notes) > 16:
                incomplete()
            row["notes"] = [text(note, 512) for note in notes[:16]]
        carrier = attribute(current, "_p2pkit_retirement")
        if carrier is not None:
            result["retirementUnknown"] = True
            if type(carrier) is not dict or len(carrier) != 3 or \
                    not all(type(key) is str for key in carrier) or \
                    set(carrier) != {"status", "resources", "omitted"} or \
                    carrier.get("status") != "UNKNOWN" or type(carrier.get("resources")) is not list or \
                    type(carrier.get("omitted")) is not int or carrier["omitted"] < 0:
                incomplete()
                row["retirement"] = "<uninspectable carrier>"
            else:
                resources = carrier["resources"]
                if len(resources) > 32 or carrier["omitted"]:
                    incomplete()
                row["retirement"] = []
                for resource in resources[:32]:
                    if type(resource) is not dict or len(resource) != 4 or \
                            not all(type(key) is str for key in resource) or \
                            set(resource) != {"phase", "resource", "status", "error"}:
                        incomplete()
                        row["retirement"].append({"error": "<uninspectable resource>"})
                    else:
                        row["retirement"].append({key: text(resource[key], 512)
                                                  for key in ("phase", "resource", "status", "error")})
        for name in ("__cause__", "__context__"):
            linked = attribute(current, name)
            if linked is not None:
                pending.append((f"{index}.{name}", linked))
        grouped = attribute(current, "exceptions", ())
        if type(grouped) not in (tuple, list):
            incomplete()
        else:
            if len(grouped) > 64:
                incomplete()
            pending.extend((f"{index}.group[{i}]", child) for i, child in enumerate(grouped[:64]))
        if len(pending) > 128:
            incomplete()
            pending = pending[:128]
    return result


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
    snapshot = session.hold("empty-root-snapshot", root.snapshot(max_bytes=0, max_members=1, deadline=end))
    _require(set(snapshot.entries) == {""}, "Encryption work/output must be new and empty")
    session.close(snapshot)
    session.check()


def _executable(path, end):
    """Public installed executable only; private evidence never uses Path.open."""
    path = Path(path)
    portable._deadline(end)
    files.absolute_parts(str(path))
    _require(path.suffix.lower() == ".exe", "Installed GPG must be a native executable")
    for parent in (path, *path.parents):
        info = parent.lstat()
        _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                 "Installed GPG path cannot contain a reparse point")
    before = path.lstat()
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             64 <= before.st_size <= MAX_EXECUTABLE_BYTES, "Installed GPG executable is not bounded regular input")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())  # Public PE file, NOT a NativeFile or private stream.
        _require(os.path.samestat(before, opened), "Installed GPG changed during admission")
        header = stream.read(64)
        _require(header[:2] == b"MZ", "Installed GPG lacks a native PE header")
        offset = struct.unpack_from("<I", header, 60)[0]
        _require(64 <= offset <= before.st_size - 26, "Installed GPG PE header offset is invalid")
        stream.seek(offset)
        pe = stream.read(26)
        _require(pe[:4] == b"PE\0\0" and struct.unpack_from("<H", pe, 4)[0] == 0x8664 and
                 struct.unpack_from("<H", pe, 24)[0] == 0x20B, "Installed GPG is not native AMD64 PE32+")
        stream.seek(0)
        for chunk in iter(lambda: stream.read(files.CHUNK), b""):
            portable._deadline(end)
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    _require(os.path.samestat(before, after) and os.path.samestat(before, current) and
             before.st_size == after.st_size == current.st_size and
             before.st_mtime_ns == after.st_mtime_ns == current.st_mtime_ns,
             "Installed GPG changed during admission")
    return digest.hexdigest()


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
    stream = session.hold(name + "-reader", root.open_file(name, max_bytes=maximum, deadline=end))
    raw = stream.read(maximum + 1)
    _require(len(raw) <= maximum and stream.read(1) == b"", "Private input exceeds its byte bound")
    stream.verify()
    session.close(stream)
    session.check()
    return raw


def _write(session, root, name, data, maximum, end):
    _require(type(data) is bytes and len(data) <= maximum, "Private bytes exceed their fixed bound")
    stream = session.hold(name + "-writer", root.create_file(name, max_bytes=maximum, deadline=end))
    stream.write(data)
    stream.sync()
    _require(stream.verify().size == len(data), "Private byte write differs")
    session.close(stream)
    session.check()


def _gpg(session, recipient, arguments, end, *, output=None, output_name="stdout", encryption=False,
         borrowed_owners=()):
    portable._deadline(end)
    _require(_executable(recipient.executable, end) == recipient.executable_sha256, "Installed GPG changed")
    work = recipient.work
    _require(work.verify().identity == recipient.work_identity, "Recipient work ownership changed")
    # Inputs created by the caller precede this command's resource slice. Keep
    # their native input/ancestor owners, not only the paths handed to GPG.
    # Success leaves them caller-owned; UNKNOWN must prevent finish() closing them.
    borrowed_owners = tuple(borrowed_owners)
    for owner in borrowed_owners:
        held = session._owners.get(id(owner))
        _require(held is not None and held["owner"] is owner and not held["closed"] and not held["quarantined"],
                 "GPG borrowed custody must already be a live session-owned resource")
        owner.verify()
    start = len(session.resources)
    operation = session.hold("gpg-operation", work.create_directory("gpg-" + uuid.uuid4().hex, deadline=end))
    home = session.hold("gpg-home", work.open_directory("gnupg", deadline=end))
    temporary = session.hold("gpg-temp", work.open_directory("tmp", deadline=end))
    armor = session.hold("recipient-armor-pin", work.open_file("recipient.asc", max_bytes=portable.MAX_KEY_BYTES,
                                                              deadline=end))
    ring = session.hold("recipient-ring-pin", work.open_file("recipient.gpg", max_bytes=portable.MAX_KEY_BYTES,
                                                            deadline=end))
    armor_raw, ring_raw = armor.read(portable.MAX_KEY_BYTES), ring.read(portable.MAX_KEY_BYTES)
    _require(hashlib.sha256(armor_raw).hexdigest() == recipient.key_sha256 and
             portable._public_armor(armor_raw) == ring_raw, "Validated recipient bytes changed")
    destination = operation if output is None else output
    maximum = portable.MAX_DIAGNOSTIC_BYTES if output is None else portable.MAX_CIPHERTEXT_BYTES
    out = session.hold("gpg-stdout", destination.create_file(output_name, max_bytes=maximum, deadline=end))
    err = session.hold("gpg-stderr-status", operation.create_file("stderr", max_bytes=portable.MAX_DIAGNOSTIC_BYTES,
                                                               deadline=end))
    command = [str(recipient.executable), "--no-options", "--homedir", str(home.path),
               "--batch", "--no-tty", "--no-autostart", "--no-auto-key-retrieve", "--no-auto-key-import",
               "--auto-key-locate", "clear", "--disable-dirmngr", "--pinentry-mode", "error",
               "--no-random-seed-file", "--no-default-keyring", "--keyring", str(ring.path),
               "--lock-never", "--no-auto-check-trustdb", "--trust-model", "always"]
    if encryption:
        command += ["--status-fd", "2"]
    command += arguments
    invocation = uuid.uuid4().hex
    environment = _environment(recipient, invocation, home, temporary)
    scope = process = None
    row = {"argv": command, "invocation": invocation, "waitExitCode": None,
           "retirement": "UNSTARTED", "outputs": {}}
    session.commands.append(row)
    domain_known = False
    try:
        scope = processes.WindowsScope(recipient.job_id, invocation, str(work.path), str(home.path))
        process = scope.spawn(command, str(work.path), environment, stdout=out, stderr=err)
        _require(process.stdout is None and process.stderr is None, "Native GPG did not borrow private sinks")
        while True:
            portable._deadline(end)
            out.verify()
            err.verify()  # Child duplicates bypass NativeFile.write(): live readback is mandatory.
            code = process.poll()
            if code is not None:
                row["waitExitCode"] = code
                break
            time.sleep(0.025)
        _require(code == 0, "GPG failed; original private diagnostics retained")
        _require(not scope.discover(), "GPG left a live descendant; forced cleanup is not successful encryption")
    except BaseException as error:
        session.capture("gpg-command", error)
    finally:
        if scope is not None:
            try:
                # Never grant a failed/over-limit child a further graceful write
                # interval. The fixed five seconds are retirement, not acceptance.
                remaining = scope.drain(grace=0, kill_wait=5)
                _require(not remaining, "Native GPG domain retirement is UNKNOWN")
                domain_known = True
            except BaseException as error:
                session.capture("gpg-drain", error, unknown=True)
            try:
                row["ownership"] = scope.description()
                _require(not row["ownership"].get("discoveryErrors"), "GPG ownership discovery is UNKNOWN")
            except BaseException as error:
                session.capture("gpg-description", error, unknown=True)
            try:
                scope.close()
            except BaseException as error:
                session.capture("gpg-scope-close", error, unknown=True)
        elif session.original is not None:
            # Constructor cleanup details, including notes, are already captured;
            # a missing Python scope variable is not itself a retirement proof.
            domain_known = not session.unknown
        if not domain_known or session.unknown:
            session.quarantine([*borrowed_owners, *(item["owner"] for item in session.resources[start:])])
            row["retirement"] = "UNKNOWN"
        else:
            row["retirement"] = "KNOWN"
            for label, sink in (("stdout", out), ("stderr", err)):
                try:
                    info = sink.verify()
                    sink.sync()
                    row["outputs"][label] = info.as_dict()
                except BaseException as error:
                    session.capture("gpg-" + label + "-final", error)
                session.close(sink)
    session.check()
    # Writable NativeFiles cannot be read. Reopen by the still-pinned directory,
    # only AFTER native scope/duplicate retirement and writer verify/sync/close.
    stderr = _read(session, operation, "stderr", portable.MAX_DIAGNOSTIC_BYTES, end)
    stdout = b"" if output is not None else _read(session, operation, "stdout", portable.MAX_DIAGNOSTIC_BYTES, end)
    for label, value in (("stdout", stdout), ("stderr", stderr)):
        if label != "stdout" or output is None:
            row["outputs"][label]["sha256"] = hashlib.sha256(value).hexdigest()
    armor.verify()
    ring.verify()
    _empty(home, session, end)
    _empty(temporary, session, end)
    _require(_executable(recipient.executable, end) == recipient.executable_sha256,
             "Installed GPG changed during execution")
    # A 30-second key refresh must not leave its deadline-bound readers alive
    # until a potentially 900-second archive/export finishes.
    for item in reversed(session.resources[start:]):
        session.close(item["owner"])
    session.check()
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
        session.capture("recipient-validation", error)
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
                    session.close(stream)
                    session.check()
    raw.sync()
    raw.verify()
    session.close(raw)
    snapshot.verify()
    session.check()


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
    session.close(reader)
    encoded = _read(session, output, portable.MANIFEST, MAX_MANIFEST_BYTES, end)
    _require(encoded == _manifest_bytes(manifest), "Sealed output manifest differs")
    snapshot.verify()
    session.close(snapshot)
    session.check()


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
        session.close(published)
        session.check()
        _write(session, output, portable.MANIFEST, manifest_raw, MAX_MANIFEST_BYTES, end)
        snapshot.verify()
        _seal(session, output, manifest, end)
        result = manifest
    except BaseException as error:
        session.capture("encrypted-export", error)
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
