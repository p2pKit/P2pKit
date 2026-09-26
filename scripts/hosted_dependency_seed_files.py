"""Closed optional dependency-byte seed, not a cache, resolver or process backend.

The accepted data-only parser stays separate. Only admitted files-2.1 bytes may
enter a fresh canonical home; no extraction, wrapper copy, cache save, subprocess
or deletion exists here. KNOWN seed custody is never proof of Gradle reuse.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

import hosted_cache_bootstrap_identity as bootstrap
import hosted_dependency_seed as authority
import hosted_initial_recipient_bootstrap_identity as initial_bootstrap
import hosted_windows_files as windows

MIB = 1024 * 1024
FILE_LIMIT, TOTAL_LIMIT, BLOCK = 512 * MIB, 2048 * MIB, MIB
NAMES_LIMIT, VERSION_LIMIT, MEMBER_LIMIT = 1024, 64, 10000
RECEIPT_LIMIT, HARD_SECONDS, SOFT_SECONDS = 4 * MIB, 120, 90
PREFIX = tuple(authority.FILESTORE_PREFIX.split("/"))
WRAPPER = "MISS_NOT_SEEDED_V1"
POLICY = "EXACT_FILES_2_1_SEED_V1"
KNOWN = ("KNOWN_MISS", "KNOWN_PARTIAL", "KNOWN_SEEDED")
STATUS = (*KNOWN, "FAILED", "UNKNOWN")
INPUTS = ("gradle/verification-metadata.xml", "gradle/wrapper/gradle-wrapper.properties",
          "scripts/hosted_dependency_seed.py", "scripts/hosted_dependency_seed_files.py",
          "scripts/hosted_windows_files.py", "scripts/run-hosted-test-custody.py", "scripts/hosted_canonical_python.py",
          "scripts/hosted_cache_bootstrap_identity.py", "scripts/hosted_test_identity.py",
          "scripts/hosted_initial_recipient_bootstrap_identity.py", "scripts/hosted_initial_recipient_stages.py",
          "scripts/hosted_initial_recipient_exception.py")


class SeedError(RuntimeError):
    """Finite safe reason; original private ownership errors are not discarded."""


def require(value, reason):
    if not value:
        raise SeedError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    require(len(raw) <= RECEIPT_LIMIT, "SEED_RECEIPT_LIMIT")
    return raw


def record(raw):
    require(type(raw) is bytes and 0 < len(raw) <= RECEIPT_LIMIT, "SEED_RECORD_BYTES")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "SEED_RECORD_DUPLICATE")
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: require(False, "SEED_RECORD_NONFINITE"))
    except (ValueError, UnicodeError, RecursionError):
        raise SeedError("SEED_RECORD_MALFORMED") from None
    require(type(value) is dict, "SEED_RECORD_OBJECT")
    return value


def policy():
    return {"version": POLICY, "prefix": authority.FILESTORE_PREFIX, "wrapper": WRAPPER,
            "fileBytes": FILE_LIMIT, "prehashBytes": TOTAL_LIMIT, "outputBytes": TOTAL_LIMIT,
            "blockBytes": BLOCK, "directoryNames": NAMES_LIMIT, "versionNames": VERSION_LIMIT,
            "sourceNames": MEMBER_LIMIT, "destinationMembers": MEMBER_LIMIT,
            "receiptBytes": RECEIPT_LIMIT, "hardSeconds": HARD_SECONDS, "softSeconds": SOFT_SECONDS}


def _deadline(end):
    require(type(end) in (int, float) and time.monotonic() < end, "SEED_FILE_DEADLINE")


def _note(error, stage, secondary):
    error.__notes__ = [*getattr(error, "__notes__", ()),
                       "Seed " + stage + " retirement UNKNOWN: " + type(secondary).__name__]


def _release(pins, original=None):
    first = original
    for pin in reversed(pins):
        try:
            pin.release()
        except BaseException as error:
            if first is None:
                first = error
            else:
                _note(first, "descriptor", error)
    if first is not None and original is None:
        raise first


def _acquire(pins):
    acquired = []
    try:
        for pin in pins:
            acquired.append(pin.acquire())
        return acquired
    except BaseException as error:
        _release(acquired, error)
        raise


@dataclass(frozen=True)
class PosixInfo:
    identity: tuple[int, int]
    is_directory: bool
    size: int
    mode: int
    uid: int
    links: int
    mtime_ns: int
    ctime_ns: int

    def as_dict(self):
        return asdict(self)


def _info(value):
    return PosixInfo((value.st_dev, value.st_ino), stat.S_ISDIR(value.st_mode), value.st_size,
                     value.st_mode, value.st_uid, value.st_nlink, value.st_mtime_ns, value.st_ctime_ns)


class _PosixPin:
    """Retained descriptor and descriptor-relative original pathname identity."""

    def __init__(self, fd, path, parent, name, *, directory, private=None, immutable=False):
        self.fd, self.path, self.parent, self.name = fd, path, parent, name
        self.directory, self.private, self.immutable = directory, private, immutable
        self.original, self.references = _info(os.fstat(fd)), 1
        self.observe()

    def observe(self):
        require(self.references > 0, "SEED_DESCRIPTOR_CLOSED")
        current = _info(os.fstat(self.fd))
        linked = _info(os.stat(self.name, dir_fd=self.parent.fd, follow_symlinks=False)
                       if self.parent is not None else os.stat(self.path, follow_symlinks=False))
        require(current == linked and current.identity == self.original.identity and
                (stat.S_ISDIR(current.mode) if self.directory else stat.S_ISREG(current.mode)) and
                (self.directory or current.links == 1), "SEED_DESCRIPTOR_IDENTITY_OR_KIND")
        if self.private is not None:
            require(current.uid == os.getuid() and not current.mode & (0o077 if self.private else 0o022),
                    "SEED_PRIVATE_MODE" if self.private else "SEED_PUBLIC_SOURCE_MODE")
        if self.immutable:
            require(current == self.original, "SEED_IMMUTABLE_INPUT_CHANGED")
        return current

    def acquire(self):
        require(self.references > 0, "SEED_DESCRIPTOR_CLOSED")
        self.references += 1
        return self

    def release(self):
        require(self.references > 0, "SEED_DESCRIPTOR_DOUBLE_CLOSE")
        self.references -= 1
        if self.references == 0:
            try:
                os.close(self.fd)
            except BaseException as error:
                _note(error, "descriptor", error)
                raise


class _PosixDirectory:
    """Seed-only fd-relative view; query/private evidence naming is unchanged."""

    def __init__(self, pins, private):
        self._pins, self.private, self.closed = pins, private, False
        self.path, self.identity = pins[-1].path, pins[-1].original.identity

    def verify(self):
        require(not self.closed, "SEED_DIRECTORY_CLOSED")
        for pin in self._pins:
            current = pin.observe()
        return current

    def names(self, *, max_names, deadline):
        _deadline(deadline)
        require(type(max_names) is int and 0 < max_names <= MEMBER_LIMIT, "SEED_DIRECTORY_LIMIT")
        before = self.verify()
        names, seen = [], set()
        iterator = os.scandir(self._pins[-1].fd)
        first = None
        try:
            for row in iterator:
                _deadline(deadline)
                require(len(names) < max_names and row.name.casefold() not in seen,
                        "SEED_DIRECTORY_OVERFLOW_OR_ALIAS")
                # Unselected names are counted, never opened or made authority.
                require(row.name not in ("", ".", "..") and "/" not in row.name and "\x00" not in row.name,
                        "SEED_DIRECTORY_NAME")
                names.append(row.name)
                seen.add(row.name.casefold())
        except BaseException as error:
            first = error
        finally:
            try:
                iterator.close()
            except BaseException as error:
                if first is None:
                    first = error
                # A lone close failure is just as uncertain as one following
                # an enumeration error. Poison the owner before other closes.
                _note(first, "directory-cursor", error)
        if first is not None:
            raise first
        require(self.verify() == before, "SEED_DIRECTORY_CHANGED_DURING_LISTING")
        _deadline(deadline)
        return tuple(sorted(names))

    def _child(self, name, *, directory, deadline, create=False, max_bytes=FILE_LIMIT):
        authority._basename(name)
        _deadline(deadline)
        self.verify()
        require(not create or self.private, "SEED_SOURCE_IS_READ_ONLY")
        parent, fd, pins = self._pins[-1], None, []
        path = self.path / name
        try:
            if directory and create:
                os.mkdir(name, mode=0o700, dir_fd=parent.fd)
            flags = os.O_NOFOLLOW | (os.O_DIRECTORY if directory else 0)
            flags |= os.O_WRONLY | os.O_CREAT | os.O_EXCL if create and not directory else os.O_RDONLY
            if not directory and not create:
                # The selected name may be (or become) a FIFO. Acquire without
                # waiting for a writer, then let the retained descriptor's
                # no-follow identity/kind checks refuse every nonregular file.
                flags |= os.O_NONBLOCK
            fd = os.open(name, flags, 0o600, dir_fd=parent.fd)
            pin = _PosixPin(fd, path, parent, name, directory=directory, private=self.private,
                            immutable=not create and not self.private or not directory and not create)
            require(pin.original.identity[0] == self.identity[0], "SEED_SELECTED_VOLUME_CHANGED")
            require(directory or 0 <= pin.original.size <= max_bytes, "SEED_FILE_LIMIT")
            # Creation may change this private parent's timestamps; immutable
            # source parents still cannot change while acquiring a child.
            self.verify()
            pins = _acquire(self._pins)
            pins.append(pin)
            fd = None
            result = (PosixPrivateDirectory(pins) if directory and self.private else
                      PosixSourceDirectory(pins) if directory else
                      PosixFile(pins, max_bytes, create, deadline))
            pins = []
            return result
        except BaseException as error:
            if fd is not None:
                try:
                    os.close(fd)
                except BaseException as secondary:
                    _note(error, "new-descriptor", secondary)
            _release(pins, error)
            raise

    def open_directory(self, name, *, deadline):
        return self._child(name, directory=True, deadline=deadline)

    def open_file(self, name, *, max_bytes, deadline):
        require(type(max_bytes) is int and 0 <= max_bytes <= FILE_LIMIT, "SEED_FILE_LIMIT")
        return self._child(name, directory=False, deadline=deadline, max_bytes=max_bytes)

    def close(self):
        if self.closed:
            return
        first = None
        try:
            self.verify()
        except BaseException as error:
            first = error
        self.closed = True
        pins, self._pins = self._pins, []
        _release(pins, first)
        if first is not None:
            raise first


class PosixSourceDirectory(_PosixDirectory):
    def __init__(self, pins):
        super().__init__(pins, False)


class PosixPrivateDirectory(_PosixDirectory):
    def __init__(self, pins):
        super().__init__(pins, True)

    def create_directory(self, name, *, deadline):
        return self._child(name, directory=True, deadline=deadline, create=True)

    def create_file(self, name, *, max_bytes, deadline):
        require(type(max_bytes) is int and 0 <= max_bytes <= FILE_LIMIT, "SEED_FILE_LIMIT")
        return self._child(name, directory=False, deadline=deadline, create=True, max_bytes=max_bytes)

    def read_bytes(self, name, *, max_bytes, deadline):
        require(type(max_bytes) is int and 0 < max_bytes <= RECEIPT_LIMIT, "SEED_PRIVATE_RECORD_LIMIT")
        reader = self.open_file(name, max_bytes=max_bytes, deadline=deadline)
        first = None
        try:
            raw = bytearray()
            while len(raw) < reader.initial_info.size:
                part = reader.read(min(BLOCK, reader.initial_info.size - len(raw)))
                require(part, "SEED_PRIVATE_RECORD_SHORT_READ")
                raw.extend(part)
            require(reader.read(1) == b"" and reader.verify() == reader.initial_info,
                    "SEED_PRIVATE_RECORD_CHANGED")
            return bytes(raw)
        except BaseException as error:
            first = error
            raise
        finally:
            try:
                reader.close()
            except BaseException as error:
                if first is None:
                    raise
                _note(first, "private-reader", error)


class PosixFile:
    def __init__(self, pins, maximum, writable, deadline):
        self._pins, self.maximum, self.writable, self.deadline = pins, maximum, writable, deadline
        self.path, self.identity = pins[-1].path, pins[-1].original.identity
        self.initial_info, self.final_info, self.closed = pins[-1].original, None, False

    def verify(self):
        _deadline(self.deadline)
        require(not self.closed, "SEED_FILE_CLOSED")
        for pin in self._pins:
            current = pin.observe()
        require(0 <= current.size <= self.maximum and (self.writable or current == self.initial_info),
                "SEED_FILE_CHANGED_OR_OVERSIZED")
        self.final_info = current
        return current

    def read(self, size):
        _deadline(self.deadline)
        require(not self.closed and not self.writable and type(size) is int and 0 <= size <= BLOCK,
                "SEED_BOUNDED_READER_REQUIRED")
        return os.read(self._pins[-1].fd, size)

    def seek(self, offset, whence=0):
        _deadline(self.deadline)
        require(not self.closed and not self.writable and offset == 0 and whence == 0,
                "SEED_REWIND_SAME_READER_REQUIRED")
        return os.lseek(self._pins[-1].fd, 0, os.SEEK_SET)

    def write(self, raw):
        _deadline(self.deadline)
        require(not self.closed and self.writable and 0 < len(raw) <= BLOCK, "SEED_EXCLUSIVE_WRITER_REQUIRED")
        fd = self._pins[-1].fd
        require(os.lseek(fd, 0, os.SEEK_CUR) + len(raw) <= self.maximum, "SEED_OUTPUT_LIMIT")
        count = os.write(fd, raw)
        require(type(count) is int and 0 < count <= len(raw), "SEED_WRITE_NO_PROGRESS")
        return count

    def sync(self):
        self.verify()
        require(self.writable, "SEED_EXCLUSIVE_WRITER_REQUIRED")
        os.fsync(self._pins[-1].fd)
        self.verify()

    def close(self):
        if self.closed:
            return
        first = None
        try:
            self.verify()
        except BaseException as error:
            first = error
        self.closed = True
        pins, self._pins = self._pins, []
        _release(pins, first)
        if first is not None:
            raise first


def _posix_root(path, *, private, create=False):
    require(os.name == "posix" and os.geteuid() != 0, "SEED_ORDINARY_POSIX_USER_REQUIRED")
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts and str(path) != "/", "SEED_PHYSICAL_ABSOLUTE_ROOT")
    require(not create or private, "SEED_SOURCE_IS_READ_ONLY")
    pins, fd = [], None
    try:
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        pins.append(_PosixPin(fd, Path("/"), None, None, directory=True))
        fd = None
        for index, name in enumerate(path.parts[1:]):
            last = index == len(path.parts) - 2
            parent = pins[-1]
            parent.observe()
            if last and create:
                os.mkdir(name, mode=0o700, dir_fd=parent.fd)
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent.fd)
            pins.append(_PosixPin(fd, parent.path / name, parent, name, directory=True,
                                  private=private if last else None, immutable=last and not private))
            fd = None
        result = PosixPrivateDirectory(pins) if private else PosixSourceDirectory(pins)
        pins = []
        return result
    except BaseException as error:
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as secondary:
                _note(error, "root-descriptor", secondary)
        _release(pins, error)
        raise


def public_root(path):
    return windows.open_dependency_source(path) if os.name == "nt" else _posix_root(path, private=False)


def private_root(path, *, create=False):
    if os.name == "nt":
        return (windows.create_private_directory if create else windows.open_private_directory)(path)
    return _posix_root(path, private=True, create=create)


class _Owners:
    """Adopt every file/directory into the existing controller's one-shot ledger."""
    def __init__(self, parent):
        self.parent, self.resources = parent, []

    def acquire(self, label, factory):
        result = self.parent.acquire("dependency-seed-" + label, factory)
        self.resources.append(result)
        return result

    def close_one(self, resource):
        require(not self.parent.unknown, "SEED_RETIREMENT_UNKNOWN")
        self.parent.close_one(resource)
        require(not self.parent.unknown, "SEED_RETIREMENT_UNKNOWN")

    def close(self):
        for resource in reversed(self.resources):
            if self.parent.unknown:
                break
            self.parent.close_one(resource)
        require(not self.parent.unknown, "SEED_RETIREMENT_UNKNOWN")


def _info_binding(info):
    return {"identity": list(info.identity), "stampSha256": digest(encoded(info.as_dict()))}


def _small_read(owners, directory, name, end, maximum, check):
    reader = owners.acquire("input", lambda: directory.open_file(name, max_bytes=maximum, deadline=end))
    first = None
    try:
        before = reader.initial_info
        raw = bytearray()
        while len(raw) < before.size:
            check()
            part = reader.read(min(BLOCK, before.size - len(raw)))
            require(type(part) is bytes and 0 < len(part) <= before.size - len(raw), "SEED_INPUT_SHORT_READ")
            raw.extend(part)
        require(reader.read(1) == b"" and reader.verify() == before, "SEED_INPUT_CHANGED")
        return bytes(raw)
    except BaseException as error:
        first = error
        owners.parent.error("dependency-seed-input-read", error)
        raise
    finally:
        try:
            owners.close_one(reader)
        except BaseException as error:
            if first is None:
                raise
            _note(first, "input", error)


def source_inputs(parent, root, end, check):
    """Read only this closed admitted-source roster; no new Git/parser language."""
    owners, values = _Owners(parent), {}
    first = None
    try:
        opened = {(): owners.acquire("source-root", lambda: public_root(root))}
        for relative in INPUTS:
            check()
            parts = tuple(relative.split("/"))
            for index in range(1, len(parts)):
                prefix = parts[:index]
                if prefix not in opened:
                    directory = opened[prefix[:-1]]
                    opened[prefix] = owners.acquire("source-parent", lambda: directory.open_directory(
                        prefix[-1], deadline=end))
            values[relative] = _small_read(owners, opened[parts[:-1]], parts[-1], end,
                                          authority.MAX_XML_BYTES, check)
        compiled = authority.parse_allowlist(values[INPUTS[0]])
        bound = {"files": {name: digest(raw) for name, raw in values.items()},
                 "allowlistSha256": compiled.authority_sha256, "artifacts": len(compiled.artifacts),
                 "components": compiled.component_count, "policy": policy()}
        for directory in opened.values():
            directory.verify()
        check()
    except BaseException as error:
        first = error
        parent.error("dependency-seed-source-inputs", error)
        raise
    finally:
        try:
            owners.close()
        except BaseException as error:
            if first is None:
                raise
            _note(first, "source-inputs", error)
    check()
    return bound, compiled


def stage_path(session, profile, role, *, admitted_raw=None):
    """One literal provider target per runner-temp/cohort, not run provenance.

    Ordinary allocation precedes admission and keeps its original default.
    Only explicit bootstrap admission permits dropping its productive parent;
    the original session/run binding must still agree before that adjustment.
    This pure path calculation does not authenticate a runner-temp root.
    """
    require(profile in ("desktop", "full") and role in
            ("macos-arm64", "macos-x64", "linux-x64", "windows-x64") and
            (profile != "full" or role.startswith("macos-")), "SEED_PROFILE_ROLE")
    path = Path(session)
    parent = path.parent
    if admitted_raw is not None and validate_cohort(admitted_raw, profile, role) is not None:
        admitted = record(admitted_raw)
        github = admitted["github"]
        require(all(type(github.get(name)) is str and re.fullmatch(r"[1-9][0-9]{0,19}", github[name])
                    for name in ("runId", "runAttempt")), "SEED_BOOTSTRAP_RUN")
        expected = ("p2pkit-cache-originals-" + github["runId"] + "-" + github["runAttempt"] + "-" +
                    admitted["selection"] + "-productive")
        require(path.is_absolute() and ".." not in path.parts and len(path.parts) > 3 and
                str(path) == str(session) and path.name == "initializer" and parent.name == expected,
                "SEED_BOOTSTRAP_SESSION_PATH")
        parent = parent.parent
    return parent / ("p2pkit-dependency-seed-" + profile + "-" + role)


def _bootstrap_cohort(admitted_raw):
    try:
        initial = initial_bootstrap.cache_cohort(admitted_raw)
        if initial is not None:
            return initial
        return bootstrap.cache_cohort(admitted_raw)
    except bootstrap.ordinary.AdmissionError:
        raise SeedError("SEED_BOOTSTRAP_IDENTITY_CHANGED") from None


def validate_cohort(admitted_raw, profile, role):
    """Pre-budget byte routing only; no native/staging/producer authority."""
    selected = _bootstrap_cohort(admitted_raw)
    require(selected is None or selected == (profile, role), "SEED_BOOTSTRAP_COHORT_CHANGED")
    return selected


def require_connected_execution(admitted_raw):
    # Bootstrap needs a separate original-budget/producer/custody path. Never
    # route it through ordinary Desktop or fictional FULL primary ABI fields.
    require(_bootstrap_cohort(admitted_raw) is None, "SEED_BOOTSTRAP_EXECUTION_NOT_CONNECTED")


def stage_record(admitted_raw, profile, role, path, root_info, source_info, inputs):
    validate_cohort(admitted_raw, profile, role)
    admitted = record(admitted_raw)
    return {"schema": 1, "scope": "DEPENDENCY_SEED_STAGING_V1", "profile": profile, "role": role,
            "source": admitted["source"], "github": admitted["github"], "admissionSha256": digest(admitted_raw),
            "container": str(path), "restoreHome": str(path / "restore-home"),
            "containerIdentity": list(root_info.identity), "sourceIdentity": list(source_info.identity),
            "inputs": inputs, "retirement": "KNOWN", "completed": True}


def validate_stage(stage, admitted_raw, profile, role, path, root_info, source_info, inputs):
    require(type(stage) is dict and type(stage.get("schema")) is int and stage.get("completed") is True and
            stage == stage_record(admitted_raw, profile, role, path, root_info, source_info, inputs),
            "SEED_STAGING_ADMISSION_OR_IDENTITY_CHANGED")


def seed_intent(admitted_raw, profile, role, path, staging_raw, inputs):
    validate_cohort(admitted_raw, profile, role)
    return {"schema": 1, "policy": POLICY, "profile": profile, "role": role,
            "admissionSha256": digest(admitted_raw), "stagingSha256": digest(staging_raw),
            "container": str(path), "restoreHome": str(path / "restore-home"), "inputs": inputs}


def validate_retained_stage(stage, admitted_raw, context, inputs):
    """Validate original receipt grammar, NOT the post-product S/cache contents."""
    validate_cohort(admitted_raw, context["profile"], context["role"])
    require(type(stage) is dict and _identity(stage.get("containerIdentity")) and
            _identity(stage.get("sourceIdentity")) and stage["containerIdentity"] != stage["sourceIdentity"],
            "SEED_STAGING_IDENTITY_GRAMMAR")
    path = stage_path(context["session"], context["profile"], context["role"], admitted_raw=admitted_raw)
    admitted = record(admitted_raw)
    expected = {"schema": 1, "scope": "DEPENDENCY_SEED_STAGING_V1", "profile": context["profile"],
                "role": context["role"], "source": admitted["source"], "github": admitted["github"],
                "admissionSha256": digest(admitted_raw), "container": str(path),
                "restoreHome": str(path / "restore-home"), "containerIdentity": stage["containerIdentity"],
                "sourceIdentity": stage["sourceIdentity"], "inputs": inputs,
                "retirement": "KNOWN", "completed": True}
    require(type(stage.get("schema")) is int and stage == expected and stage.get("completed") is True,
            "SEED_STAGING_RECORD_CHANGED")
    return stage


class _SourceLookup:
    """Cache listings only while their exact parents stay pinned; bound live fds."""
    def __init__(self, owners, root, end, check):
        self.owners, self.end, self.check = owners, end, check
        self.directories, self.listings, self.observed = {(): root}, {}, set()

    def names(self, parts, maximum=NAMES_LIMIT):
        directory = self.directories[parts]
        directory.verify()
        if parts not in self.listings:
            self.check()
            names = directory.names(max_names=maximum, deadline=self.end)
            self.observed.update(parts + (name,) for name in names)
            require(len(self.observed) <= MEMBER_LIMIT, "SEED_SOURCE_NAME_LIMIT")
            self.listings[parts] = names
        require(len(self.listings[parts]) <= maximum, "SEED_VERSION_BUCKET_LIMIT")
        return self.listings[parts]

    def directory(self, parts):
        if parts in self.directories:
            return self.directories[parts]
        parent = self.directory(parts[:-1])
        if parent is None or parts[-1] not in self.names(parts[:-1]):
            return None  # Only a complete stable pinned listing proves absence.
        self.check()
        child = self.owners.acquire("source-directory", lambda: parent.open_directory(
            parts[-1], deadline=self.end))
        self.directories[parts] = child
        return child

    def coordinate(self, parts):
        # Keep shared prefix pins/listings, retire previous coordinates/buckets.
        for current in sorted(tuple(self.directories), key=len, reverse=True):
            if current and parts[:len(current)] != current:
                self.owners.close_one(self.directories.pop(current))
                self.listings.pop(current, None)
        return self.directory(parts)


class _Destination:
    """Only this invocation's recorded exclusive directories may be reopened."""
    def __init__(self, owners, root, end, check, *, empty=False):
        require(type(empty) is bool, "SEED_DESTINATION_MODE")
        self.owners, self.end, self.check = owners, end, check
        self.directories, self.identities = {(): root}, {(): root.identity}
        # The fresh-H seed keeps its original properties-only default. A
        # dependency-only export must explicitly select a truly empty target.
        self.members, self.created = {(): set() if empty else {"gradle.properties"}}, 0

    def directory(self, parts, create=True):
        self.check()
        # Bound actual descriptors, not just total inventory size.
        for current in sorted(tuple(self.directories), key=len, reverse=True):
            if current and parts[:len(current)] != current:
                self.owners.close_one(self.directories.pop(current))
        for index in range(1, len(parts) + 1):
            prefix = parts[:index]
            if prefix in self.directories:
                continue
            parent = self.directories[prefix[:-1]]
            require(set(parent.names(max_names=NAMES_LIMIT, deadline=self.end)) == self.members[prefix[:-1]],
                    "SEED_FOREIGN_DESTINATION_MEMBER")
            if prefix not in self.identities:
                require(create and self.created < MEMBER_LIMIT, "SEED_DESTINATION_MEMBER_LIMIT")
                child = self.owners.acquire("destination-directory", lambda: parent.create_directory(
                    prefix[-1], deadline=self.end))
                self.identities[prefix], self.members[prefix] = child.identity, set()
                self.members[prefix[:-1]].add(prefix[-1])
                self.created += 1
            else:
                child = self.owners.acquire("destination-reopen", lambda: parent.open_directory(
                    prefix[-1], deadline=self.end))
                require(child.identity == self.identities[prefix], "SEED_DESTINATION_DIRECTORY_REPLACED")
            self.directories[prefix] = child
        directory = self.directories[parts]
        require(set(directory.names(max_names=NAMES_LIMIT, deadline=self.end)) == self.members[parts],
                "SEED_FOREIGN_DESTINATION_MEMBER")
        return directory

    def create_file(self, parts, size):
        directory = self.directory(parts[:-1])
        require(parts[-1] not in self.members[parts[:-1]] and self.created < MEMBER_LIMIT,
                "SEED_PREEXISTING_DESTINATION_FILE")
        writer = self.owners.acquire("writer", lambda: directory.create_file(
            parts[-1], max_bytes=size, deadline=self.end))
        self.members[parts[:-1]].add(parts[-1])
        self.created += 1
        return directory, writer

    def verify(self, admitted):
        for parts in sorted(self.members):
            self.directory(parts, create=False)
        for row in admitted:
            self.check()
            parts = tuple(row["path"].split("/"))
            parent = self.directory(parts[:-1], create=False)
            reader = self.owners.acquire("final-identity", lambda: parent.open_file(
                parts[-1], max_bytes=row["size"], deadline=self.end))
            first = None
            try:
                require(_info_binding(reader.verify()) == row["destination"], "SEED_ADMITTED_FILE_CHANGED")
            except BaseException as error:
                first = error
                raise
            finally:
                try:
                    self.owners.close_one(reader)
                except BaseException as error:
                    if first is None:
                        raise
                    _note(first, "final-identity", error)


def _hash(reader, size, check, writer=None):
    sha256, sha1, remaining = hashlib.sha256(), hashlib.sha1(), size
    while remaining:
        check()
        raw = reader.read(min(BLOCK, remaining))
        require(type(raw) is bytes and 0 < len(raw) <= min(BLOCK, remaining), "SEED_COPY_SHORT_READ")
        if writer is not None:
            offset = 0
            while offset < len(raw):
                check()
                count = writer.write(raw[offset:])
                require(type(count) is int and 0 < count <= len(raw) - offset, "SEED_COPY_SHORT_WRITE")
                offset += count
        sha256.update(raw)
        sha1.update(raw)
        remaining -= len(raw)
    require(reader.read(1) == b"", "SEED_SOURCE_GREW")
    require(reader.verify().size == size, "SEED_SOURCE_SIZE_CHANGED")
    check()
    return sha256.hexdigest(), sha1.hexdigest()


def _copy_candidate(owners, parent, artifact, bucket, index, destination, counts, end, check, reserve):
    reader = writer = readback = None
    first = None
    answer = None
    try:
        reader = owners.acquire("candidate", lambda: parent.open_file(
            artifact.name, max_bytes=FILE_LIMIT, deadline=end))
        size = reader.initial_info.size
        if counts["prehashBytes"] + size > TOTAL_LIMIT:
            return "BYTE_BUDGET", None
        counts["prehashBytes"] += size  # Charge rejected candidates too, before reading.
        sha256, sha1 = _hash(reader, size, check)
        if sha256 != artifact.sha256:
            return "SHA256_REJECTED", None
        if sha1 != bucket:
            return "LAYOUT_REJECTED", None
        parts = (*PREFIX, artifact.group, artifact.module, artifact.version, sha1, artifact.name)
        relative = "/".join(parts)
        if counts["outputBytes"] + size > TOTAL_LIMIT or not reserve(index, relative, size):
            return "BYTE_OR_RECEIPT_BUDGET", None
        require(reader.seek(0) == 0 and reader.verify() == reader.initial_info, "SEED_SOURCE_REWIND_CHANGED")
        target, writer = destination.create_file(parts, size)
        written = _hash(reader, size, check, writer)
        require(written == (sha256, sha1), "SEED_SOURCE_CHANGED_BETWEEN_PASSES")
        writer.sync()
        written_info = writer.verify()
        require(written_info.size == size, "SEED_WRITER_SIZE_CHANGED")
        owners.close_one(writer)
        check()
        readback = owners.acquire("readback", lambda: target.open_file(
            artifact.name, max_bytes=size, deadline=end))
        require(readback.initial_info.identity == written_info.identity and readback.initial_info.size == size,
                "SEED_READBACK_IDENTITY_CHANGED")
        require(_hash(readback, size, check) == (sha256, sha1), "SEED_READBACK_BYTES_CHANGED")
        answer = {"index": index, "path": relative, "size": size, "sha256": sha256, "sha1": sha1,
                  "source": _info_binding(reader.verify()), "destination": _info_binding(readback.verify())}
    except BaseException as error:
        first = error
        owners.parent.error("dependency-seed-candidate", error)
        raise
    finally:
        for resource in (readback, writer, reader):
            if resource is not None:
                try:
                    owners.close_one(resource)
                except BaseException as error:
                    if first is None:
                        first = error
                    else:
                        _note(first, "copy-resource", error)
        if first is not None and answer is not None:
            raise first
        if first is not None and owners.parent.unknown:
            raise first
    check()
    counts["outputBytes"] += size
    return "ADMITTED", answer


def window(started, hard, soft, *, raw, job_budget):
    require(all(type(value) is int for value in (started, hard, soft)) and
            0 <= started < soft <= hard <= started + HARD_SECONDS * 10**9 and
            soft <= started + SOFT_SECONDS * 10**9, "SEED_ORIGINAL_WINDOW")
    return {"clock": "controller-raw-ns" if raw else "process-monotonic-ns", "startedNs": started,
            "hardEndNs": hard, "softEndNs": soft, "finishedNs": None, "jobBudgetSha256": job_budget}


def _copy_allowlisted(owners, source, output, compiled, result, end, check, now, interval, budget,
                      *, empty_destination=False):
    """Shared bounded traversal; callers separately admit original H/S custody.

    This never resolves dependencies, adopts existing target files or invents a
    reversed seed context. Only the destination's initial member set differs.
    """
    counts, accepted, misses = result["counts"], result["admitted"], result["misses"]
    used = 0
    def reserve(index, path, size):
        maximum = {"identity": [2**64 - 1, "f" * 32], "stampSha256": "f" * 64}
        row = {"index": index, "path": path, "size": size, "sha256": "f" * 64, "sha1": "f" * 40,
               "source": maximum, "destination": maximum}
        return used + len(encoded(row)) <= budget
    lookup = _SourceLookup(owners, source, end, check)
    destination = _Destination(owners, output, end, check, empty=empty_destination)
    stopped = False
    for index, artifact in enumerate(compiled.artifacts):
        check()
        if stopped or now() >= interval["softEndNs"]:
            stopped = True
            misses.append({"index": index, "reason": "BUDGET_NOT_STARTED", "rejected": 0})
            continue
        coordinate = (*PREFIX, artifact.group, artifact.module, artifact.version)
        version = lookup.coordinate(coordinate)
        outcome, rejected = "ABSENT", 0
        if version is not None:
            buckets = lookup.names(coordinate, VERSION_LIMIT)
            for bucket in buckets:
                if not re.fullmatch(r"[0-9a-f]{40}", bucket):
                    continue
                check()
                if now() >= interval["softEndNs"]:
                    outcome, stopped = "BUDGET_NOT_STARTED", True
                    break
                selected = (*coordinate, bucket)
                directory = lookup.directory(selected)
                if artifact.name not in lookup.names(selected):
                    continue
                outcome, row = _copy_candidate(owners, directory, artifact, bucket, index, destination,
                                               counts, end, check, reserve)
                if outcome == "ADMITTED":
                    accepted.append(row)
                    used += len(encoded(row))
                    break
                if "BUDGET" in outcome:
                    stopped = True
                    break
                counts["sha256Rejected" if outcome == "SHA256_REJECTED" else "layoutRejected"] += 1
                rejected += 1
        if outcome != "ADMITTED":
            misses.append({"index": index, "reason": outcome, "rejected": rejected})
    destination.verify(accepted)
    counts.update(sourceNames=len(lookup.observed), destinationMembers=destination.created)


def seed_home(parent, home, intent, staging, compiled, context_raw, canonical_raw, admitted_raw,
              *, end, check, now, interval):
    """Complete one owned seed, or fail without exposing a partial H to a loader."""
    require_connected_execution(admitted_raw)
    owners, first = _Owners(parent), None
    admitted_record, canonical = record(admitted_raw), record(canonical_raw)
    counts = {"prehashBytes": 0, "outputBytes": 0, "sourceNames": 0, "destinationMembers": 0,
              "sha256Rejected": 0, "layoutRejected": 0}
    accepted, misses = [], []
    result = {"schema": 1, "scope": "DEPENDENCY_SEED_FILE_CUSTODY_V1", "intentSha256": digest(encoded(intent)),
              "contextSha256": digest(context_raw), "canonicalContextSha256": digest(canonical_raw),
              "stagingSha256": intent["stagingSha256"], "source": admitted_record["source"],
              "github": admitted_record["github"], "role": intent["role"], "home": str(home),
              "restoreHome": intent["restoreHome"], "inputs": intent["inputs"], "policy": policy(),
              "wrapper": WRAPPER, "status": "FAILED", "completed": False, "retirement": "KNOWN",
              "errors": [], "window": dict(interval), "counts": counts, "admitted": accepted, "misses": misses}
    def checked():
        check()
        _deadline(end)
        require(now() < interval["hardEndNs"], "SEED_ORIGINAL_HARD_DEADLINE")
    budget = RECEIPT_LIMIT - len(encoded(result)) - 512 * 1024
    try:
        checked()
        container = owners.acquire("restore-container", lambda: private_root(intent["container"]))
        require(list(container.identity) == staging["containerIdentity"], "SEED_RESTORE_CONTAINER_REPLACED")
        source = owners.acquire("restore-root", lambda: public_root(intent["restoreHome"]))
        output = owners.acquire("canonical-home", lambda: private_root(home))
        require(list(source.identity) == staging["sourceIdentity"], "SEED_RESTORED_ROOT_REPLACED")
        require(source.identity != output.identity and
                set(output.names(max_names=NAMES_LIMIT, deadline=end)) == {"gradle.properties"},
                "SEED_HOME_NOT_FRESH")
        properties = _small_read(owners, output, "gradle.properties", end, RECEIPT_LIMIT, checked)
        require(digest(properties) == canonical["gradlePropertiesSha256"], "SEED_CANONICAL_PROPERTIES_CHANGED")
        result.update(sourceIdentity=list(source.identity), homeIdentity=list(output.identity),
                      propertiesSha256=digest(properties), propertiesAfterSha256=None)
        _copy_allowlisted(owners, source, output, compiled, result, end, checked, now, interval, budget)
        require(_small_read(owners, output, "gradle.properties", end, RECEIPT_LIMIT, checked) == properties,
                "SEED_CANONICAL_PROPERTIES_CHANGED")
        source.verify()
        result["propertiesAfterSha256"] = digest(properties)
        checked()
    except BaseException as error:
        first = error
        parent.error("dependency-seed-copy", error)
    finally:
        try:
            owners.close()
        except BaseException as error:
            if first is None:
                first = error
            else:
                _note(first, "final", error)
        result["retirement"] = "UNKNOWN" if parent.unknown else "KNOWN"
        if first is not None:
            result["status"] = "UNKNOWN" if parent.unknown else "FAILED"
            result["errors"] = [type(first).__name__]
    if first is not None:
        first.seed_result = result
        raise first
    checked()
    result["window"]["finishedNs"] = now()
    require(result["window"]["finishedNs"] < interval["hardEndNs"], "SEED_LATE_FINALIZATION")
    result.update(completed=True, status="KNOWN_MISS" if not accepted else
                  "KNOWN_PARTIAL" if misses else "KNOWN_SEEDED")
    encoded(result)
    return result


def disposition(raw):
    value = record(raw)
    return {"required": True, "status": value["status"], "manifestSha256": digest(raw),
            "intentSha256": value["intentSha256"], "contextSha256": value["contextSha256"],
            "completed": value["completed"], "retirement": value["retirement"],
            "admittedCount": len(value["admitted"]), "admittedBytes": value["counts"]["outputBytes"],
            "wrapper": value["wrapper"]}


def profile_passed(value):
    row = value.get("dependencySeed")
    if row is None:
        return True  # No optional seed was requested; seal separately binds intent.
    return (type(row) is dict and set(row) == {"required", "status", "manifestSha256", "intentSha256",
            "contextSha256", "completed", "retirement", "admittedCount", "admittedBytes", "wrapper"} and
            row["required"] is True and row["status"] in KNOWN and row["completed"] is True and
            row["retirement"] == "KNOWN" and row["wrapper"] == WRAPPER and
            row["contextSha256"] == value.get("contextSha256") and
            all(type(row[key]) is str and re.fullmatch(r"[0-9a-f]{64}", row[key]) for key in
                ("manifestSha256", "intentSha256", "contextSha256")) and
            type(row["admittedCount"]) is int and 0 <= row["admittedCount"] <= authority.MAX_ARTIFACTS and
            type(row["admittedBytes"]) is int and 0 <= row["admittedBytes"] <= TOTAL_LIMIT and
            ((row["status"] == "KNOWN_MISS") == (row["admittedCount"] == 0)) and
            (row["admittedCount"] != 0 or row["admittedBytes"] == 0))


def _identity(value):
    return (type(value) is list and len(value) == 2 and type(value[0]) is int and 0 < value[0] < 2**64 and
            (type(value[1]) is int and 0 < value[1] < 2**64 or
             type(value[1]) is str and re.fullmatch(r"[0-9a-f]{32}", value[1]) is not None and
             value[1] != "0" * 32))


def _file_binding(value):
    return (type(value) is dict and set(value) == {"identity", "stampSha256"} and _identity(value["identity"]) and
            type(value["stampSha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["stampSha256"]) is not None)


def validate_receipt(value, intent, staging_raw, context_raw, canonical_raw, admitted_raw, compiled):
    """Closed semantic verification, without reopening post-product cache bytes."""
    require_connected_execution(admitted_raw)
    required = {"schema", "scope", "intentSha256", "contextSha256", "canonicalContextSha256",
                "stagingSha256", "source", "github", "role", "home", "restoreHome", "inputs", "policy",
                "wrapper", "status", "completed", "retirement", "errors", "window", "counts", "admitted",
                "misses", "sourceIdentity", "homeIdentity", "propertiesSha256", "propertiesAfterSha256"}
    require(type(value) is dict and set(value) == required and type(value["schema"]) is int and value["schema"] == 1,
            "SEED_RECEIPT_GRAMMAR")
    canonical, admitted, context, staging = map(record, (canonical_raw, admitted_raw, context_raw, staging_raw))
    validate_retained_stage(staging, admitted_raw, context, intent["inputs"])
    expected_intent = seed_intent(admitted_raw, context["profile"], context["role"],
                                 Path(intent["container"]), staging_raw, intent["inputs"])
    require(intent == expected_intent and context.get("dependencySeed") == intent and
            intent["container"] == str(stage_path(Path(context["session"]), context["profile"], context["role"])),
            "SEED_INTENT_CHANGED")
    require(type(intent["inputs"]) is dict and set(intent["inputs"]) ==
            {"files", "allowlistSha256", "artifacts", "components", "policy"} and
            type(intent["inputs"]["files"]) is dict and set(intent["inputs"]["files"]) == set(INPUTS) and
            all(type(sha) is str and re.fullmatch(r"[0-9a-f]{64}", sha) for sha in intent["inputs"]["files"].values()) and
            type(intent["inputs"]["artifacts"]) is int and type(intent["inputs"]["components"]) is int and
            intent["inputs"]["allowlistSha256"] == compiled.authority_sha256 and
            intent["inputs"]["files"][INPUTS[0]] == compiled.source_sha256 and
            intent["inputs"]["artifacts"] == len(compiled.artifacts) and
            intent["inputs"]["components"] == compiled.component_count and intent["inputs"]["policy"] == policy(),
            "SEED_ALLOWLIST_CHANGED")
    require(value["scope"] == "DEPENDENCY_SEED_FILE_CUSTODY_V1" and
            value["intentSha256"] == digest(encoded(intent)) and value["contextSha256"] == digest(context_raw) and
            value["canonicalContextSha256"] == digest(canonical_raw) and
            value["stagingSha256"] == intent["stagingSha256"] == digest(staging_raw) and
            value["source"] == context["source"] == admitted["source"] == staging["source"] and
            value["github"] == admitted["github"] == staging["github"] and value["role"] == context["role"] and
            value["home"] == canonical["gradleHome"] == str(Path(context["session"]) / "state/gradle-home") and
            value["restoreHome"] == intent["restoreHome"] == staging["restoreHome"] and
            value["inputs"] == intent["inputs"] == staging["inputs"] and value["policy"] == policy() and
            value["propertiesSha256"] == value["propertiesAfterSha256"] == canonical["gradlePropertiesSha256"] and
            value["sourceIdentity"] == staging["sourceIdentity"] and _identity(value["sourceIdentity"]) and
            _identity(value["homeIdentity"]) and value["homeIdentity"] != value["sourceIdentity"],
            "SEED_RECEIPT_SOURCE_OR_HOME_CHANGED")
    require(value["wrapper"] == WRAPPER and value["completed"] is True and value["retirement"] == "KNOWN" and
            value["errors"] == [] and value["status"] in KNOWN, "SEED_RECEIPT_NOT_KNOWN")
    interval = value["window"]
    require(type(interval) is dict and set(interval) == {"clock", "startedNs", "hardEndNs", "softEndNs",
            "finishedNs", "jobBudgetSha256"} and all(type(interval[key]) is int for key in
            ("startedNs", "hardEndNs", "softEndNs", "finishedNs")) and
            0 <= interval["startedNs"] <= interval["finishedNs"] < interval["hardEndNs"] <=
            interval["startedNs"] + HARD_SECONDS * 10**9 and interval["startedNs"] < interval["softEndNs"] <=
            min(interval["hardEndNs"], interval["startedNs"] + SOFT_SECONDS * 10**9), "SEED_RECEIPT_TIME_CHANGED")
    if context["profile"] == "full":
        require(interval["clock"] == "controller-raw-ns" and interval["jobBudgetSha256"] ==
                context["jobBudgetSha256"] and interval["hardEndNs"] <=
                context["primaryAbiAccounting"]["productiveCutoffRawNs"], "SEED_RAW_CUTOFF_CHANGED")
    else:
        require(interval["clock"] == "process-monotonic-ns" and interval["jobBudgetSha256"] is None,
                "SEED_RECEIPT_CLOCK_CHANGED")
    _validate_inventory(value, compiled)
    return value


def _validate_inventory(value, compiled, *, statuses=KNOWN, destination_identity=None):
    """Closed shared copy inventory, not provenance or a provider observation."""
    if destination_identity is None:
        destination_identity = value["homeIdentity"]
    counts = value["counts"]
    require(type(counts) is dict and set(counts) == {"prehashBytes", "outputBytes", "sourceNames",
            "destinationMembers", "sha256Rejected", "layoutRejected"} and
            all(type(counts[key]) is int and 0 <= counts[key] <= maximum for key, maximum in
            (("prehashBytes", TOTAL_LIMIT), ("outputBytes", TOTAL_LIMIT), ("sourceNames", MEMBER_LIMIT),
             ("destinationMembers", MEMBER_LIMIT), ("sha256Rejected", MEMBER_LIMIT),
             ("layoutRejected", MEMBER_LIMIT))), "SEED_RECEIPT_COUNTS_CHANGED")
    require(type(value["admitted"]) is list and type(value["misses"]) is list and
            len(value["admitted"]) + len(value["misses"]) == len(compiled.artifacts), "SEED_RECEIPT_ROSTER")
    seen, paths, destinations, identities, output_bytes = set(), set(), set(), set(), 0
    for row in value["admitted"]:
        require(type(row) is dict and set(row) == {"index", "path", "size", "sha256", "sha1", "source", "destination"}
                and type(row["index"]) is int and 0 <= row["index"] < len(compiled.artifacts) and
                row["index"] not in seen and type(row["size"]) is int and 0 <= row["size"] <= FILE_LIMIT and
                type(row["sha1"]) is str and re.fullmatch(r"[0-9a-f]{40}", row["sha1"]) and
                _file_binding(row["source"]) and _file_binding(row["destination"]), "SEED_ADMITTED_ROW_CHANGED")
        artifact = compiled.artifacts[row["index"]]
        parts = (*PREFIX, artifact.group, artifact.module, artifact.version, row["sha1"], artifact.name)
        require(row["sha256"] == artifact.sha256 and row["path"] == "/".join(parts) and
                row["path"] not in paths and row["source"]["identity"] != row["destination"]["identity"] and
                tuple(row["destination"]["identity"]) not in identities and
                row["destination"]["identity"] != destination_identity and
                row["source"]["identity"] != value["sourceIdentity"],
                "SEED_ADMITTED_AUTHORITY_CHANGED")
        seen.add(row["index"])
        paths.add(row["path"])
        identities.add(tuple(row["destination"]["identity"]))
        destinations.update(parts[:index] for index in range(1, len(parts) + 1))
        output_bytes += row["size"]
    reasons = {"ABSENT", "SHA256_REJECTED", "LAYOUT_REJECTED", "BYTE_BUDGET", "BYTE_OR_RECEIPT_BUDGET",
               "BUDGET_NOT_STARTED"}
    for row in value["misses"]:
        require(type(row) is dict and set(row) == {"index", "reason", "rejected"} and
                type(row["index"]) is int and 0 <= row["index"] < len(compiled.artifacts) and row["index"] not in seen and
                row["reason"] in reasons and type(row["rejected"]) is int and 0 <= row["rejected"] <= VERSION_LIMIT,
                "SEED_MISS_ROW_CHANGED")
        seen.add(row["index"])
    require(counts["outputBytes"] == output_bytes <= counts["prehashBytes"] and
            counts["destinationMembers"] == len(destinations) and
            sum(row["rejected"] for row in value["misses"]) <= counts["sha256Rejected"] + counts["layoutRejected"] <=
            counts["sourceNames"] and
            value["status"] == (statuses[0] if not value["admitted"] else
                                statuses[1] if value["misses"] else statuses[2]),
            "SEED_TERMINAL_RELABELLED")
    return value
