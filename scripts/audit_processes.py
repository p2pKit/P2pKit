#!/usr/bin/env python3
"""Identity-scoped children for the opt-in audit executor; never a process-name sweep.

Windows uses a kernel Job Object attached atomically before resume. Linux discovers
controlled marker-inheriting descendants and signals through pidfds. macOS binds
each launch before exec, adds an inherited anonymous-pipe capability, and follows
observed non-reaper parent lifetimes. SIP hides restricted executables' environment;
reparent-then-exec can also replace their parent unique ID with launchd's ID.
Signals use real Mach audit tokens, never a PID/group/name fallback. Unresolved
ancestry fails closed. Neither POSIX backend contains malicious children or work
delegated to unrelated services; native API/fixture admission remains required.
"""
from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import time
from typing import Any

JOB_ENV = "P2PKIT_AUDIT_JOB_ID"
CHAIN_ENV = "P2PKIT_AUDIT_OWNERSHIP_CHAIN"
DOMAINS_ENV = "P2PKIT_AUDIT_OWNERSHIP_DOMAINS"
STATE_ENV = "P2PKIT_AUDIT_STATE_DIR"
PIPE_ENV = "P2PKIT_AUDIT_DARWIN_PIPES"
MAX_PROCESS_BYTES = 8 * 1024 * 1024
MAX_PROCESSES = 65536
MAX_PROCESS_FDS = 65536
SIG_TERM = 15
SIG_KILL = 9
# Diagnostic labels only. A kernel name never grants ownership, exclusion or
# signal authority; unknown/shortened names are deliberately not guessed.
DARWIN_DIAGNOSTIC_ROLES = frozenset((
    "java", "python", "simctl", "xcodebuild", "xctest", "launchd_sim", "launchd",
    "Simulator", "SimulatorTrampoline", "SimulatorBridge", "SpringBoard", "backboardd",
    "DataMigrator", "testmanagerd", "testmanagerd_sim", "runningboardd", "installd",
    "ReportCrash", "ReportMemoryException", "diagnosticd", "logd", "lsd", "cfprefsd",
    "mDNSResponder", "OTHER", "UNRECORDED",
))
DARWIN_DIAGNOSTIC_PARENTAGE = frozenset(("OWNED", "BASELINE", "UNOBSERVED", "TRACED", "INVALID"))


def darwin_diagnostic_role(name: bytes) -> str:
    if name in (b"Python", b"Python3", b"python") or re.fullmatch(rb"python3(?:\.[0-9]{1,2})?", name):
        return "python"
    return next((label for label in DARWIN_DIAGNOSTIC_ROLES - {"OTHER", "UNRECORDED"}
                 if name == label.encode("ascii")), "OTHER")


class OwnershipError(RuntimeError):
    """Ownership cannot be established or finalized safely."""


class DiscoveryUncertain(OwnershipError):
    """A live, unclassified lifetime must not be treated as unrelated or retired."""


def host_role() -> str:
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(
        platform.machine().lower(), "unsupported")
    system = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(
        platform.system(), "unsupported")
    if system == "macos":
        library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        function = library.sysctlbyname
        function.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                             ctypes.c_void_p, ctypes.c_size_t]
        function.restype = ctypes.c_int
        translated, length = ctypes.c_int(), ctypes.c_size_t(ctypes.sizeof(ctypes.c_int))
        ctypes.set_errno(0)
        result = function(b"sysctl.proc_translated", ctypes.byref(translated), ctypes.byref(length), None, 0)
        if result == 0:
            if length.value != ctypes.sizeof(translated) or translated.value != 0:
                raise OwnershipError("Translated macOS interpreter cannot satisfy a native host role")
        elif ctypes.get_errno() != errno.ENOENT:
            raise OwnershipError("Cannot establish native macOS execution (translation query failed)")
    elif system == "windows":
        try:
            library = ctypes.WinDLL("kernel32", use_last_error=True)
            function = library.IsWow64Process2
            function.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_uint16)]
            function.restype = ctypes.c_int32
            process_machine, native_machine = ctypes.c_uint16(), ctypes.c_uint16()
            result = function(ctypes.c_void_p(-1), ctypes.byref(process_machine), ctypes.byref(native_machine))
        except (AttributeError, OSError) as error:
            raise OwnershipError("Cannot establish native Windows process architecture") from error
        if not result or process_machine.value != 0 or native_machine.value != 0x8664:
            raise OwnershipError("Windows host role requires native AMD64, not architecture emulation")
    return f"{system}-{arch}"


def ownership_domains(chain: str, encoded: str) -> list[dict[str, str]]:
    if not chain:
        if encoded:
            raise OwnershipError("Ownership domains lack their invocation chain")
        return []
    if not re.fullmatch(r"[0-9a-f]{32}(?::[0-9a-f]{32}){0,31}", chain) or len(encoded) > 512 * 1024:
        raise OwnershipError("Malformed or excessive ownership chain/domain encoding")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise OwnershipError("Duplicate ownership domain key")
            result[key] = value
        return result

    try:
        domains = json.loads(encoded, object_pairs_hook=unique)
    except (ValueError, TypeError) as error:
        raise OwnershipError("Malformed ownership domains") from error
    if not isinstance(domains, list) or len(domains) != len(chain.split(":")):
        raise OwnershipError("Ownership domain count differs from the invocation chain")
    for identifier, domain in zip(chain.split(":"), domains):
        if not isinstance(domain, dict) or set(domain) != {"id", "job", "state", "home"} or \
                domain["id"] != identifier or not isinstance(domain["job"], str) or \
                not re.fullmatch(r"[0-9a-f]{32}", domain["job"]) or \
                any(not isinstance(domain[key], str) or not domain[key] or "\0" in domain[key]
                    for key in ("state", "home")):
            raise OwnershipError("Invalid ownership domain binding")
    if len(set(chain.split(":"))) != len(domains):
        raise OwnershipError("Duplicate ownership domain")
    return domains


def ownership_environment(base: dict[str, str], job: str, invocation: str,
                          state: str, home: str, *, allow_new_context: bool = False) -> dict[str, str]:
    for value in (job, invocation):
        if not re.fullmatch(r"[0-9a-f]{32}", value):
            raise OwnershipError("Invalid ownership identity")
    inherited_job = base.get(JOB_ENV, "")
    chain = base.get(CHAIN_ENV, "")
    domains = ownership_domains(chain, base.get(DOMAINS_ENV, ""))
    if domains and (inherited_job != domains[-1]["job"] or base.get(STATE_ENV) != domains[-1]["state"] or
                    base.get("GRADLE_USER_HOME") != domains[-1]["home"]):
        raise OwnershipError("Inherited current context differs from its ownership domain")
    if inherited_job and inherited_job != job and not allow_new_context:
        raise OwnershipError("Inherited ownership belongs to a different audit job")
    if inherited_job and not domains:
        raise OwnershipError("Malformed or unbound inherited ownership chain")
    parts = chain.split(":") if chain else []
    if invocation in parts or len(parts) >= 32 or len(set(parts)) != len(parts):
        raise OwnershipError("Duplicate or excessive ownership nesting")
    if not allow_new_context and base.get("GRADLE_USER_HOME") and \
            os.path.normcase(os.path.abspath(base["GRADLE_USER_HOME"])) != os.path.normcase(os.path.abspath(home)):
        raise OwnershipError("Inherited GRADLE_USER_HOME differs from the job-owned home")
    domains.append({"id": invocation, "job": job, "state": state, "home": home})
    encoded = json.dumps(domains, separators=(",", ":"), ensure_ascii=True)
    if len(encoded) > 512 * 1024:
        raise OwnershipError("Ownership domains exceed the bounded environment encoding")
    result = dict(base)
    result.update({JOB_ENV: job, CHAIN_ENV: ":".join(parts + [invocation]),
                   DOMAINS_ENV: encoded,
                   STATE_ENV: state, "GRADLE_USER_HOME": home})
    return result


def parse_procargs2(raw: bytes) -> dict[bytes, bytes]:
    """Parse bounded Darwin KERN_PROCARGS2; never return or retain argv."""
    if not 5 <= len(raw) <= MAX_PROCESS_BYTES:
        raise OwnershipError("Invalid KERN_PROCARGS2 size")
    argc = struct.unpack_from("=i", raw)[0]
    if not 1 <= argc <= len(raw):
        raise OwnershipError("Invalid KERN_PROCARGS2 argc")
    end = raw.find(b"\0", 4)
    if end < 0:
        raise OwnershipError("Unterminated KERN_PROCARGS2 executable")
    cursor = end + 1
    while cursor < len(raw) and raw[cursor] == 0:
        cursor += 1
    for _ in range(argc):
        end = raw.find(b"\0", cursor)
        if end < 0:
            raise OwnershipError("Unterminated KERN_PROCARGS2 argv")
        cursor = end + 1
    return parse_environment(raw[cursor:])


def parse_environment(raw: bytes) -> dict[bytes, bytes]:
    if len(raw) > MAX_PROCESS_BYTES:
        raise OwnershipError("Process environment exceeds the bounded parser")
    selected = {key.encode() for key in (JOB_ENV, CHAIN_ENV, DOMAINS_ENV, STATE_ENV, "GRADLE_USER_HOME")}
    result: dict[bytes, bytes] = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        key, separator, value = entry.partition(b"=")
        if key in selected:
            if not separator or key in result:
                raise OwnershipError("Duplicate or malformed process ownership field")
            result[key] = value
    return result


def resolve_executable(argv: list[str], cwd: str, env: dict[str, str]) -> list[str]:
    if not argv or any(not isinstance(arg, str) or "\0" in arg for arg in argv):
        raise OwnershipError("Missing executable or NUL in argv")
    executable = argv[0]
    if os.path.isabs(executable):
        resolved = executable
    elif os.path.dirname(executable):
        resolved = os.path.abspath(os.path.join(cwd, executable))
    else:
        resolved = shutil.which(executable, path=env.get("PATH"))
    if not resolved or not Path(resolved).is_file():
        raise OwnershipError("Command executable does not resolve to an existing file")
    return [os.path.abspath(resolved), *argv[1:]]


class PosixProcess:
    def __init__(self, process: subprocess.Popen[bytes]):
        self.process = process
        self.pid = process.pid
        self.stdout = process.stdout
        self.stderr = process.stderr

    def poll(self) -> int | None:
        return self.process.poll()

    def wait(self, timeout: float | None = None) -> int:
        return self.process.wait(timeout=timeout)

    def close(self) -> None:
        # Stream ownership belongs to the tee threads, not this process handle.
        self.process.poll()


class PosixScope:
    name = "abstract"

    def __init__(self, job: str, invocation: str, state: str, home: str):
        self.job, self.invocation, self.state, self.home = job, invocation, state, home
        self.known: dict[tuple[int, ...], dict[str, Any]] = {}
        self.handles: dict[tuple[int, ...], Any] = {}
        self.leaders: list[PosixProcess] = []
        self.launches: list[dict[str, Any]] = []
        self.discovery_errors: set[str] = set()
        self.pending_discoveries: dict[int, dict[str, Any]] = {}
        self.discovery_reconciliations: list[dict[str, Any]] = []
        self.baseline: set[tuple[int, ...]] = set()
        self._admit()
        for pid in self._pids():
            identity = self._identity(pid)
            if identity is not None:
                self._remember_identity(identity)
                self.baseline.add(self._key(identity))

    def _admit(self) -> None:
        raise NotImplementedError

    def _pids(self) -> list[int]:
        raise NotImplementedError

    def _identity(self, pid: int) -> dict[str, Any] | None:
        raise NotImplementedError

    def _key(self, identity: dict[str, Any]) -> tuple[int, ...]:
        raise NotImplementedError

    def _environment(self, pid: int) -> dict[bytes, bytes]:
        raise NotImplementedError

    def _inspect_environment(self, identity: dict[str, Any]) -> dict[bytes, bytes]:
        try:
            return self._environment(identity["pid"])
        except (PermissionError, OwnershipError) as error:
            current = self._identity(identity["pid"])
            if current is None or not current["live"] or self._key(current) != self._key(identity):
                raise ProcessLookupError(identity["pid"]) from error
            raise

    def _acquire(self, identity: dict[str, Any]) -> Any:
        raise NotImplementedError

    def _send(self, identity: dict[str, Any], handle: Any, signum: int) -> None:
        raise NotImplementedError

    def _release(self, handle: Any) -> None:
        pass

    def _remember_identity(self, identity: dict[str, Any]) -> None:
        pass

    def _ownership_proof(self, identity: dict[str, Any], environment: dict[bytes, bytes]) -> dict[str, Any] | None:
        return {"kind": "inherited-domain"} if self._ours(environment) else None

    def _retain_proof(self, identity: dict[str, Any], proof: dict[str, Any]) -> None:
        pass

    def _ours(self, environment: dict[bytes, bytes]) -> bool:
        def value(key: str) -> bytes | None:
            return environment.get(key.encode())
        chain = value(CHAIN_ENV)
        if chain is None or self.invocation.encode() not in chain.split(b":"):
            return False
        encoded = value(DOMAINS_ENV)
        if encoded is None:
            raise OwnershipError("Owned invocation marker lacks its ancestor domain bindings")
        try:
            domains = ownership_domains(chain.decode("ascii"), encoded.decode("ascii"))
        except UnicodeError as error:
            raise OwnershipError("Invalid ownership domain encoding") from error
        if not domains or value(JOB_ENV) != domains[-1]["job"].encode() or \
                value(STATE_ENV) != os.fsencode(domains[-1]["state"]) or \
                value("GRADLE_USER_HOME") != os.fsencode(domains[-1]["home"]):
            raise OwnershipError("Owned process current context does not match its last domain")
        return {"id": self.invocation, "job": self.job, "state": self.state, "home": self.home} in domains

    def _discovery_failed(self, identity: dict[str, Any], error: Exception) -> str:
        message = f"Cannot inspect new same-uid process {identity['pid']}: {type(error).__name__}"
        self.discovery_errors.add(message)
        return message

    def _discovery_resolved(self, pid: int, outcome: str, current: dict[str, Any] | None = None) -> None:
        record = self.pending_discoveries.pop(pid, None)
        if record is not None:
            record.update(outcome=outcome, lastIdentity=current)
            self.discovery_errors.discard(record["message"])

    def discover(self) -> list[dict[str, Any]]:
        for leader in self.leaders:
            leader.poll()  # Reap our children; a zombie is not a running worker.
        # A missing census entry is not exit evidence for an unresolved lifetime.
        census = []
        for pid in dict.fromkeys([*self._pids(), *self.pending_discoveries]):
            if pid == os.getpid():
                continue
            identity = self._identity(pid)
            if identity is not None:
                self._remember_identity(identity)
            census.append((pid, identity))
        # Remember the entire observed census before interpreting parentage; OS
        # enumeration order is neither ancestry nor proof of ownership.
        for pid, identity in census:
            pending = self.pending_discoveries.get(pid)
            if pending is not None and (identity is None or not identity["live"] or
                                        self._key(identity) != self._key(pending["identity"])):
                outcome = "lifetime-ended" if identity is None else "nonrunning" if not identity["live"] else "replaced"
                self._discovery_resolved(pid, outcome, identity)
            if identity is None or not identity["live"] or identity["uid"] != os.getuid():
                continue
            key = self._key(identity)
            if key in self.baseline:
                continue
            if key in self.known:
                self.known[key] = identity
                continue
            try:
                environment = self._inspect_environment(identity)
            except (PermissionError, OwnershipError) as error:
                self._discovery_failed(identity, error)
                continue
            except ProcessLookupError:
                self._discovery_resolved(pid, "lifetime-ended")
                continue
            try:
                proof = self._ownership_proof(identity, environment)
            except DiscoveryUncertain as error:
                self._discovery_failed(identity, error)
                continue
            except ProcessLookupError:
                self._discovery_resolved(pid, "lifetime-ended")
                continue
            if proof is None:
                self._discovery_resolved(pid, "unmarked", identity)
                continue
            try:
                # Both native backends recheck the bound lifetime while acquiring
                # the handle. A separate eligibility read here could hide denial
                # as absence before this positively owned process is registered.
                handle = self._acquire(identity)
            except ProcessLookupError:
                self._discovery_resolved(pid, "lifetime-ended")
                continue
            self.known[key] = identity
            self.handles[key] = handle
            self._retain_proof(identity, proof)
            self._discovery_resolved(pid, "owned", identity)
        live = []
        for key, previous in list(self.known.items()):
            current = self._identity(previous["pid"])
            if current is not None and current["live"] and self._key(current) == key:
                self.known[key] = current
                live.append(dict(current))
        return sorted(live, key=lambda item: item["pid"])

    def spawn(self, argv: list[str], cwd: str, env: dict[str, str]) -> PosixProcess:
        launch = {"api": "subprocess.Popen", "requestedArgv": list(argv),
                  "cwd": cwd, "shell": False, "created": False}
        self.launches.append(launch)
        actual = resolve_executable(argv, cwd, env)
        launch.update({"resolvedArgv": actual, "executable": actual[0]})
        process = PosixProcess(subprocess.Popen(actual, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               start_new_session=True, close_fds=True, bufsize=0))
        launch.update({"created": True, "pid": process.pid})
        self.leaders.append(process)
        # A very short leader may already have exited; marker discovery still finds
        # its detached descendants. No fallback broad process-group signaling.
        self.discover()
        return process

    def signal_all(self, signum: int) -> None:
        for identity in self.discover():
            key = self._key(identity)
            try:
                self._send(identity, self.handles[key], signum)
            except ProcessLookupError:
                pass

    def drain(self, grace: float = 5.0, kill_wait: float = 5.0) -> list[dict[str, Any]]:
        if self.discover():
            self.signal_all(SIG_TERM)
        end = time.monotonic() + grace
        quiet = 0
        while time.monotonic() < end:
            live = self.discover()
            # No known workers is not quiescence while a discovered lifetime is
            # still unclassified. Keep observing within the ORIGINAL drain
            # bounds; only positive reconciliation can make a sample quiet.
            if not live and not self.pending_discoveries:
                quiet += 1
                if quiet >= 3:
                    return []
            else:
                quiet = 0
                if live:
                    self.signal_all(SIG_TERM)
            time.sleep(0.1)
        self.signal_all(SIG_KILL)
        end = time.monotonic() + kill_wait
        quiet = 0
        while time.monotonic() < end:
            live = self.discover()
            if not live and not self.pending_discoveries:
                quiet += 1
                if quiet >= 3:
                    return []
            else:
                quiet = 0
                if live:
                    self.signal_all(SIG_KILL)
            time.sleep(0.1)
        return self.discover()

    def description(self) -> dict[str, Any]:
        return {"backend": self.name, "scope": "controlled-marker-inheriting-descendants",
                "invocation": self.invocation, "job": self.job,
                "launches": self.launches,
                "startedIdentities": sorted(self.known.values(), key=lambda item: item["pid"]),
                "discoveryReconciliations": self.discovery_reconciliations,
                "discoveryErrors": sorted(self.discovery_errors)}

    def close(self) -> None:
        for handle in self.handles.values():
            self._release(handle)
        self.handles.clear()
        for process in self.leaders:
            process.close()


class LinuxScope(PosixScope):
    name = "linux-proc-pidfd"

    def _admit(self) -> None:
        if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
            raise OwnershipError("Linux ownership requires pidfd_open and pidfd_send_signal")
        identity = self._identity(os.getpid())
        if identity is None:
            raise OwnershipError("Cannot inspect the Linux controller identity")
        handle = self._acquire(identity)
        try:
            signal.pidfd_send_signal(handle, 0)
        finally:
            os.close(handle)

    def _pids(self) -> list[int]:
        pids = [int(entry.name) for entry in Path("/proc").iterdir() if entry.name.isdecimal()]
        if len(pids) > MAX_PROCESSES:
            raise OwnershipError("Process count exceeds ownership bound")
        return pids

    def _identity(self, pid: int, *, required: bool = False) -> dict[str, Any] | None:
        try:
            base = Path("/proc") / str(pid)
            raw = (base / "stat").read_bytes()
            end = raw.rfind(b")")
            fields = raw[end + 2:].split()
            if end < 0 or len(fields) < 20:
                raise OwnershipError("Malformed Linux process identity")
            return {"pid": pid, "uid": base.stat().st_uid, "parentPid": int(fields[1]),
                    "group": int(fields[2]), "session": int(fields[3]),
                    "startTicks": int(fields[19]), "live": fields[0] not in (b"Z", b"X")}
        except (FileNotFoundError, ProcessLookupError):
            return None
        except PermissionError:
            if required or pid in self.pending_discoveries or any(key[0] == pid for key in self.known):
                raise OwnershipError("Cannot reinspect a recorded Linux process identity")
            return None  # Not eligible for same-uid marker discovery.

    def _key(self, identity: dict[str, Any]) -> tuple[int, ...]:
        return identity["pid"], identity["startTicks"]

    def _environment(self, pid: int) -> dict[bytes, bytes]:
        try:
            with (Path("/proc") / str(pid) / "environ").open("rb") as stream:
                raw = stream.read(MAX_PROCESS_BYTES + 1)
            return parse_environment(raw)
        except FileNotFoundError as error:
            raise ProcessLookupError(pid) from error

    def _inspect_environment(self, identity: dict[str, Any]) -> dict[bytes, bytes]:
        try:
            return self._environment(identity["pid"])
        except (PermissionError, OwnershipError) as error:
            # This identity was already observed as a live same-UID candidate.
            # A later stat denial is not absence or permission to forget it.
            current = self._identity(identity["pid"], required=True)
            if current is None or not current["live"] or self._key(current) != self._key(identity):
                raise ProcessLookupError(identity["pid"]) from error
            raise

    def _discovery_failed(self, identity: dict[str, Any], error: Exception) -> str:
        message = super()._discovery_failed(identity, error)
        # A transient /proc access denial is recoverable only by later positive
        # observation of this lifetime, or its verified exit/replacement. Keep
        # structural/ownership errors sticky even when the process later exits.
        if isinstance(error, PermissionError):
            record = self.pending_discoveries.get(identity["pid"])
            if record is None:
                if len(self.discovery_reconciliations) >= 1024:
                    raise OwnershipError("Linux discovery evidence exceeds its bound")
                record = {"identity": dict(identity), "message": message, "firstFailure": str(error),
                          "failures": 0, "outcome": "unresolved"}
                self.pending_discoveries[identity["pid"]] = record
                self.discovery_reconciliations.append(record)
            record.update(lastIdentity=dict(identity), lastFailure=str(error), failures=record["failures"] + 1)
        return message

    def drain(self, grace: float = 5.0, kill_wait: float = 5.0) -> list[dict[str, Any]]:
        live = super().drain(grace, kill_wait)
        if self.pending_discoveries:
            raise OwnershipError("Unclassified Linux lifetimes remain; cleanup is not proven")
        return live

    def _acquire(self, identity: dict[str, Any]) -> int:
        handle = os.pidfd_open(identity["pid"], 0)
        try:
            current = self._identity(identity["pid"], required=True)
            if current is None or not current["live"] or self._key(current) != self._key(identity):
                raise ProcessLookupError(identity["pid"])
            return handle
        except BaseException:
            os.close(handle)
            raise

    def _send(self, identity: dict[str, Any], handle: int, signum: int) -> None:
        signal.pidfd_send_signal(handle, signum)

    def _release(self, handle: int) -> None:
        os.close(handle)


# Fixed-width fields are intentional: ctypes.wintypes.DWORD is not 32-bit on
# every non-Windows interpreter used to inspect these layouts.
U32 = ctypes.c_uint32
I32 = ctypes.c_int32
U64 = ctypes.c_uint64
PTR = ctypes.c_void_p
SIZE = ctypes.c_size_t


class DarwinBsdInfo(ctypes.Structure):
    _fields_ = [(name, U32) for name in ("flags", "status", "xstatus", "pid", "ppid", "uid", "gid",
                                         "ruid", "rgid", "svuid", "svgid", "reserved")] + [
        ("comm", ctypes.c_char * 16), ("name", ctypes.c_char * 32), ("nfiles", U32), ("pgid", U32),
        ("pjobc", U32), ("tdev", U32), ("tpgid", U32), ("nice", I32), ("startsec", U64), ("startusec", U64)]


class DarwinUniqueInfo(ctypes.Structure):
    _fields_ = [("uuid", ctypes.c_uint8 * 16), ("uniqueid", U64), ("parentuniqueid", U64),
                ("pidversion", I32), ("parentpidversion", I32), ("reserve2", U64), ("reserve3", U64)]


class DarwinIdentity(ctypes.Structure):
    _fields_ = [("bsd", DarwinBsdInfo), ("unique", DarwinUniqueInfo)]


class AuditToken(ctypes.Structure):
    # Opaque. Never populate or interpret val[] manually.
    _fields_ = [("val", U32 * 8)]


class DarwinFileInfo(ctypes.Structure):
    _fields_ = [("openflags", U32), ("status", U32), ("offset", ctypes.c_int64),
                ("type", I32), ("guardflags", U32)]


class DarwinVinfoStat(ctypes.Structure):
    _fields_ = [("dev", U32), ("mode", ctypes.c_uint16), ("nlink", ctypes.c_uint16),
                ("ino", U64), ("uid", U32), ("gid", U32)] + [
        (name, ctypes.c_int64) for name in ("atime", "atimensec", "mtime", "mtimensec", "ctime", "ctimensec",
                                           "birthtime", "birthtimensec", "size", "blocks")] + [
        ("blksize", I32), ("flags", U32), ("gen", U32), ("rdev", U32), ("spare", ctypes.c_int64 * 2)]


class DarwinPipeInfo(ctypes.Structure):
    _fields_ = [("file", DarwinFileInfo), ("stat", DarwinVinfoStat), ("handle", U64), ("peer", U64),
                ("status", I32), ("reserved", I32)]


class DarwinFdInfo(ctypes.Structure):
    _fields_ = [("fd", I32), ("type", U32)]


class DarwinObservationError(OwnershipError):
    """A failed observation, not proof of exit or an unreleased kernel right."""


class DarwinObservationExhausted(OwnershipError):
    """Still unresolved at this census; a later positive observation may reconcile it."""


class DarwinScope(PosixScope):
    name = "darwin-libproc-audit-token"

    def __init__(self, job: str, invocation: str, state: str, home: str):
        self.pipe_fds: tuple[int, ...] = ()
        self.pipe_marker: tuple[int, ...] | None = None
        try:
            super().__init__(job, invocation, state, home)
            # Keep BOTH endpoints alive until close: a kernel pipe handle cannot
            # be recycled into an unrelated pipe while this reference is held.
            self.pipe_fds = os.pipe()
            self.pipe_marker = self._pipe_identity(os.getpid(), self.pipe_fds[1])
            if self.pipe_marker is None or not self.pipe_marker[1]:
                raise OwnershipError("Cannot bind the Darwin inherited pipe capability")
        except BaseException:
            for descriptor in self.pipe_fds:
                os.close(descriptor)
            self.pipe_fds = ()
            raise

    def _admit(self) -> None:
        self.observation_reconciliations: list[dict[str, Any]] = []
        self.identity_history: dict[int, dict[str, Any]] = {}
        self.diagnostic_roles: dict[tuple[int, ...], str] = {}
        self.ownership_proofs: dict[tuple[int, ...], dict[str, Any]] = {}
        self.foreign_sessions: dict[tuple[int, ...], dict[str, Any]] = {}
        if (ctypes.sizeof(DarwinBsdInfo), ctypes.sizeof(DarwinUniqueInfo), ctypes.sizeof(DarwinIdentity),
                ctypes.sizeof(AuditToken), ctypes.sizeof(DarwinFileInfo), ctypes.sizeof(DarwinVinfoStat),
                ctypes.sizeof(DarwinPipeInfo), ctypes.sizeof(DarwinFdInfo)) != (136, 56, 192, 32, 24, 136, 184, 8):
            raise OwnershipError("Unsupported Darwin process ABI layout")
        try:
            self.proc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
            self.system = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            self.bsm = ctypes.CDLL("/usr/lib/libbsm.dylib", use_errno=True)
            self.proc.proc_pidinfo.argtypes = [I32, I32, U64, PTR, I32]
            self.proc.proc_pidinfo.restype = I32
            self.proc.proc_pidfdinfo.argtypes = [I32, I32, I32, PTR, I32]
            self.proc.proc_pidfdinfo.restype = I32
            self.proc.proc_listallpids.argtypes = [PTR, I32]
            self.proc.proc_listallpids.restype = I32
            self.proc.proc_signal_with_audittoken.argtypes = [ctypes.POINTER(AuditToken), I32]
            self.proc.proc_signal_with_audittoken.restype = I32
            self.system.sysctl.argtypes = [ctypes.POINTER(I32), U32, PTR, ctypes.POINTER(SIZE), PTR, SIZE]
            self.system.sysctl.restype = I32
            self.system.task_name_for_pid.argtypes = [U32, I32, ctypes.POINTER(U32)]
            self.system.task_name_for_pid.restype = I32
            self.system.task_info.argtypes = [U32, U32, PTR, ctypes.POINTER(U32)]
            self.system.task_info.restype = I32
            self.system.mach_port_deallocate.argtypes = [U32, U32]
            self.system.mach_port_deallocate.restype = I32
            self.bsm.audit_token_to_asid.argtypes = [AuditToken]
            self.bsm.audit_token_to_asid.restype = U32
            self.bsm.audit_token_to_pid.argtypes = [AuditToken]
            self.bsm.audit_token_to_pid.restype = I32
            self.bsm.audit_token_to_euid.argtypes = [AuditToken]
            self.bsm.audit_token_to_euid.restype = U32
            self.self_port = U32.in_dll(self.system, "mach_task_self_").value
        except (AttributeError, OSError, ValueError) as error:
            raise OwnershipError("Required Darwin libproc/Mach API is unavailable") from error
        limit = I32()
        length = SIZE(ctypes.sizeof(limit))
        mib = (I32 * 2)(1, 8)  # CTL_KERN, KERN_ARGMAX.
        if self.system.sysctl(mib, 2, ctypes.byref(limit), ctypes.byref(length), None, 0) != 0 or \
                length.value != ctypes.sizeof(limit) or not 4096 <= limit.value <= MAX_PROCESS_BYTES:
            raise OwnershipError("Cannot admit bounded Darwin KERN_ARGMAX")
        self.argmax = limit.value
        identity = self._identity(os.getpid())
        if identity is None:
            raise OwnershipError("Cannot inspect the Darwin controller identity")
        self._inspect_environment(identity)
        # Token acquisition admission is not proof that signaling controls pass;
        # the native fixture must exercise a real child and stale token.
        self.controller_session = self._audit_session(identity)

    def _audit_session(self, identity: dict[str, Any]) -> int:
        token = self._acquire(identity)
        # These are libbsm's decoders, not fabricated/interpreted token words.
        if self.bsm.audit_token_to_pid(token) != identity["pid"] or \
                self.bsm.audit_token_to_euid(token) != identity["uid"]:
            raise OwnershipError("Darwin audit token decoder/identity mismatch")
        return self.bsm.audit_token_to_asid(token)

    def _pipe_identity(self, pid: int, descriptor: int) -> tuple[int, ...] | None:
        value = DarwinPipeInfo()
        ctypes.set_errno(0)
        size = self.proc.proc_pidfdinfo(pid, descriptor, 6, ctypes.byref(value), ctypes.sizeof(value))
        if size == 0 and ctypes.get_errno() in (errno.EBADF, errno.ENOENT, errno.EINVAL):
            return None  # The descriptor closed/changed; never a positive match.
        if size == 0:
            raise DarwinObservationError(f"Darwin pipe observation failed: errno {ctypes.get_errno()}")
        if size != ctypes.sizeof(value) or not value.handle or \
                value.stat.mode & 0o170000 != 0o010000:
            raise OwnershipError("Unsupported Darwin pipe identity response")
        # Opaque pipe handles are never emitted in logs, receipts or environment.
        return value.handle, value.peer, value.stat.ino

    @staticmethod
    def _pipe_digest(marker: tuple[int, ...]) -> str:
        return hashlib.sha256(struct.pack("=QQQ", *marker)).hexdigest()

    def _inherited_pipes(self, env: dict[str, str]) -> list[dict[str, Any]]:
        encoded = env.get(PIPE_ENV, "[]")
        if len(encoded) > 8192:
            raise OwnershipError("Darwin inherited pipe bindings exceed their bound")
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise OwnershipError("Duplicate Darwin inherited pipe binding field")
                value[key] = item
            return value
        try:
            records = json.loads(encoded, object_pairs_hook=unique)
        except (ValueError, TypeError) as error:
            raise OwnershipError("Invalid Darwin inherited pipe bindings") from error
        if not isinstance(records, list) or len(records) > 32:
            raise OwnershipError("Invalid Darwin inherited pipe binding count")
        chain = env.get(CHAIN_ENV, "").split(":")
        verified, seen, descriptors = [], set(), set()
        for record in records:
            if not isinstance(record, dict) or set(record) != {"id", "fd", "digest"} or \
                    not isinstance(record["id"], str) or record["id"] not in chain or record["id"] in seen or \
                    type(record["fd"]) is not int or not 3 <= record["fd"] < MAX_PROCESS_FDS or \
                    record["fd"] in descriptors or \
                    not isinstance(record["digest"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["digest"]):
                raise OwnershipError("Invalid Darwin inherited pipe binding")
            seen.add(record["id"])
            descriptors.add(record["fd"])
        for record in records:
            marker = self._pipe_identity(os.getpid(), record["fd"])
            # Some controlled tools close nonstandard FDs when they spawn. A lost
            # optional marker is not authority, nor proof of nonownership. Retain
            # environment/ancestry checks; never pass an unrelated reused FD.
            if marker is not None and self._pipe_digest(marker) == record["digest"]:
                verified.append(record)
        return verified

    def _has_pipe(self, identity: dict[str, Any]) -> bool:
        if self.pipe_marker is None or len(self.pipe_fds) != 2 or \
                self._pipe_identity(os.getpid(), self.pipe_fds[1]) != self.pipe_marker:
            raise OwnershipError("Darwin observation lost its held pipe capability")
        def inspect(current):
            capacity = 128
            while capacity <= MAX_PROCESS_FDS:
                rows = (DarwinFdInfo * capacity)()
                ctypes.set_errno(0)
                size = self.proc.proc_pidinfo(current["pid"], 1, 0, rows, ctypes.sizeof(rows))
                if size < 0 or size > ctypes.sizeof(rows) or size % ctypes.sizeof(DarwinFdInfo):
                    raise OwnershipError("Unsupported Darwin descriptor census")
                if size == 0:
                    if ctypes.get_errno() == 0:
                        return False
                    raise DarwinObservationError(f"Darwin descriptor census failed: errno {ctypes.get_errno()}")
                if size == ctypes.sizeof(rows):
                    capacity *= 2
                    continue
                return any(row.type == 6 and self._pipe_identity(current["pid"], row.fd) == self.pipe_marker
                           for row in rows[:size // ctypes.sizeof(DarwinFdInfo)])
            raise OwnershipError("Darwin descriptor census exceeds its bound")
        return self._observe(identity, "inherited pipe", inspect)

    def _remember_identity(self, identity: dict[str, Any]) -> None:
        unique = identity["uniqueId"]
        if unique <= 0 or identity["parentUniqueId"] == unique:
            raise OwnershipError("Invalid Darwin original-parent identity")
        previous = self.identity_history.get(unique)
        if previous is not None and self._key(previous) != self._key(identity):
            raise OwnershipError("Darwin unique ID changed its bound lifetime")
        if previous is None and len(self.identity_history) >= MAX_PROCESSES:
            raise OwnershipError("Darwin lineage history exceeds its bound")
        self.identity_history[unique] = dict(identity)

    def _retain_proof(self, identity: dict[str, Any], proof: dict[str, Any]) -> None:
        # Link to startedIdentities without duplicating every full observation.
        self.ownership_proofs.setdefault(self._key(identity), {"identity": list(self._key(identity)), **proof})

    def _ownership_proof(self, identity: dict[str, Any], environment: dict[bytes, bytes]) -> dict[str, Any] | None:
        proof = super()._ownership_proof(identity, environment)
        if proof is not None:
            return proof
        try:
            if self._has_pipe(identity):
                return {"kind": "inherited-pipe-capability"}
            try:
                return self._parent_proof(identity)
            except DiscoveryUncertain:
                # Audit sessions are inherited across ordinary fork/exec. An OS
                # service in a different session is outside this controlled scope;
                # matching sessions confer NO ownership. Session-changing/delegated
                # work needs a separate explicit lifecycle owner, not a tree sweep.
                session = self._audit_session(identity)
                if self.controller_session not in (0, 0xffffffff) and session not in (0, 0xffffffff) and \
                        session != self.controller_session:
                    if self._key(identity) not in self.foreign_sessions and len(self.foreign_sessions) >= MAX_PROCESSES:
                        raise OwnershipError("Darwin foreign-session history exceeds its bound")
                    self.foreign_sessions[self._key(identity)] = {
                        "identity": list(self._key(identity)), "kind": "different-kernel-audit-session",
                        "signalAuthority": False}
                    return None
                raise
        except DarwinObservationExhausted as error:
            raise DiscoveryUncertain(str(error)) from error

    def _parent_proof(self, identity: dict[str, Any]) -> dict[str, Any] | None:
        # p_puniqueid survives ordinary reparenting, but exec can reset it to the
        # reaper's ID. A launchd edge is NEVER original-parent/nonownership proof.
        # The retained original-parent VERSION is diagnostic only: it is a lone
        # wrapping 32-bit number, not an identity we can safely reconstruct.
        current, ancestors, seen = identity, [], {identity["uniqueId"]}
        for _ in range(256):
            if current["flags"] & 2:  # PROC_FLAG_TRACED: debugger reparenting is not our authority.
                raise DiscoveryUncertain("Darwin traced parentage is not an ownership proof")
            parent = self.identity_history.get(current["parentUniqueId"])
            if parent is None or parent["pid"] == 1:
                raise DiscoveryUncertain("Darwin non-reaper original-parent lifetime was not observed")
            if parent["uniqueId"] in seen:
                raise OwnershipError("Cyclic Darwin original-parent evidence")
            seen.add(parent["uniqueId"])
            ancestors.append(list(self._key(parent)))
            if self._key(parent) in self.known:
                return {"kind": "kernel-original-parent", "ancestors": ancestors}
            if self._key(parent) in self.baseline:
                return None  # Positive foreign lineage, not missing markers alone.
            current = parent
        raise OwnershipError("Darwin original-parent depth exceeds its bound")

    def spawn(self, argv: list[str], cwd: str, env: dict[str, str]) -> PosixProcess:
        # Validate the inheritance contract before creating any process. Direct
        # ownership does not authorize fabricated/missing ancestor domains.
        if not self._ours({os.fsencode(key): os.fsencode(value) for key, value in env.items()}):
            raise OwnershipError("Darwin launch lacks its bound inherited ownership domain")
        inherited = self._inherited_pipes(env)
        if self.pipe_marker is None or len(self.pipe_fds) != 2 or \
                self._pipe_identity(os.getpid(), self.pipe_fds[1]) != self.pipe_marker:
            raise OwnershipError("Darwin launch lost its inherited pipe capability")
        inherited = [record for record in inherited if record["id"] != self.invocation]
        inherited.append({"id": self.invocation, "fd": self.pipe_fds[1], "digest": self._pipe_digest(self.pipe_marker)})
        if len(inherited) > 32:
            raise OwnershipError("Darwin pipe nesting exceeds its bound")
        child_env = {**env, PIPE_ENV: json.dumps(inherited, separators=(",", ":"))}
        pass_fds = tuple(sorted({record["fd"] for record in inherited}))
        actual = resolve_executable(argv, cwd, env)
        launch = {"api": "subprocess.Popen", "requestedArgv": list(argv), "resolvedArgv": actual,
                  "executable": actual[0], "cwd": cwd, "shell": False, "created": False,
                  "gateReleased": False}
        self.launches.append(launch)
        owner = self._identity(os.getpid(), required=True)
        if owner is None or not owner["live"]:
            raise OwnershipError("Cannot bind the Darwin spawning controller")
        self._remember_identity(owner)
        ready_read = ready_write = release_read = release_write = -1
        process = None
        try:
            ready_read, ready_write = os.pipe()
            release_read, release_write = os.pipe()
            bootstrap = [sys.executable, "-I", "-S", str(Path(__file__).with_name("audit_exec_gate.py")),
                         str(ready_write), str(release_read), *actual]
            launch["bootstrapArgv"] = bootstrap
            process = PosixProcess(subprocess.Popen(bootstrap, cwd=cwd, env=child_env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, close_fds=True, bufsize=0,
                pass_fds=(*pass_fds, ready_write, release_read)))
            launch.update({"created": True, "pid": process.pid})
            self.leaders.append(process)
            os.close(ready_write)
            ready_write = -1
            os.close(release_read)
            release_read = -1
            if not select.select([ready_read], [], [], 10)[0] or os.read(ready_read, 1) != b"R":
                raise OwnershipError("Darwin exec gate did not establish readiness")
            # The trusted gate cannot exec/fork the product until the bound
            # lifetime and a real token have been acquired. No fast-exit race.
            identity = self._identity(process.pid, required=True)
            if identity is None or not identity["live"] or identity["parentPid"] != os.getpid() or \
                    identity["parentUniqueId"] != owner["uniqueId"] or identity["uid"] != os.getuid() or \
                    identity["realUid"] != os.getuid() or self._key(identity) in self.baseline:
                raise OwnershipError("Darwin exec gate is not the directly spawned lifetime")
            if not self._has_pipe(identity):
                raise OwnershipError("Darwin exec gate did not inherit its bound pipe capability")
            self._remember_identity(identity)
            handle = self._acquire(identity)
            self.known[self._key(identity)] = identity
            self.handles[self._key(identity)] = handle
            self._retain_proof(identity, {"kind": "direct-spawn-gate", "controller": list(self._key(owner))})
            launch["boundIdentity"] = dict(identity)
            if os.write(release_write, b"G") != 1:
                raise OwnershipError("Darwin exec gate was not released")
            launch["gateReleased"] = True
            # Return the streams to their owner before further fallible census
            # work. The leader is already bound; normal waiting discovers children.
            return process
        except BaseException:
            if process is not None and not launch["gateReleased"]:
                # Closing the private gate produces EOF, not product execution.
                # No consumer owns these streams on a failed spawn.
                process.stdout.close()
                process.stderr.close()
            raise
        finally:
            for descriptor in (ready_read, ready_write, release_read, release_write):
                if descriptor >= 0:
                    os.close(descriptor)

    def drain(self, grace: float = 5.0, kill_wait: float = 5.0) -> list[dict[str, Any]]:
        live = super().drain(grace, kill_wait)
        if self.pending_discoveries:
            raise OwnershipError("Unclassified Darwin lifetimes remain; cleanup is not proven")
        return live

    def _pids(self) -> list[int]:
        count = self.proc.proc_listallpids(None, 0)
        if count <= 0:
            raise OwnershipError("Cannot enumerate Darwin processes")
        capacity = count + 128
        for _ in range(5):
            if capacity > MAX_PROCESSES:
                break
            data = (I32 * capacity)()
            got = self.proc.proc_listallpids(data, ctypes.sizeof(data))
            if got <= 0:
                raise OwnershipError("Darwin process enumeration failed")
            if got < capacity:
                return [int(data[index]) for index in range(got) if data[index] > 0]
            capacity *= 2
        raise OwnershipError("Darwin process list did not stabilize within its bound")

    def _identity(self, pid: int, *, required: bool = False) -> dict[str, Any] | None:
        value = DarwinIdentity()
        ctypes.set_errno(0)
        got = self.proc.proc_pidinfo(pid, 18, 1, ctypes.byref(value), ctypes.sizeof(value))
        if got == 0:
            error = ctypes.get_errno()
            if error in (errno.ESRCH, errno.ENOENT):
                return None
            failure = DarwinObservationError(f"Darwin process identity failed for pid {pid}: errno {error}")
            if not required:
                previous = self._recorded_identity(pid)
                if previous is not None:
                    return self._reconcile_identity(previous, failure)
                if error == 0 or (error in (errno.EPERM, errno.EACCES) and pid != os.getpid()):
                    return None
            raise failure
        if got != ctypes.sizeof(value) or value.bsd.pid != pid:
            raise OwnershipError("Unsupported Darwin combined identity response")
        if value.bsd.status not in (1, 2, 3, 4, 5):
            failure = DarwinObservationError(f"Unsupported Darwin bound process status for pid {pid}")
            if required:
                raise failure
            previous = self._recorded_identity(pid)
            if previous is not None:
                return self._reconcile_identity(previous, failure)
        identity = {"pid": pid, "uid": value.bsd.uid, "parentPid": value.bsd.ppid, "group": value.bsd.pgid,
                "uniqueId": value.unique.uniqueid, "parentUniqueId": value.unique.parentuniqueid,
                "originalParentPidVersion": value.unique.parentpidversion,
                "pidVersion": value.unique.pidversion, "startSeconds": value.bsd.startsec,
                "startMicroseconds": value.bsd.startusec, "realUid": value.bsd.ruid,
                "status": value.bsd.status, "flags": value.bsd.flags, "live": value.bsd.status not in (0, 5)}
        # Reuse this already-required kernel read. No extra census, environment,
        # path, task port or permission is acquired for diagnostic attribution.
        if hasattr(self, "diagnostic_roles"):
            key = self._key(identity)
            if key not in self.diagnostic_roles and len(self.diagnostic_roles) >= MAX_PROCESSES:
                raise OwnershipError("Darwin diagnostic role history exceeds its bound")
            self.diagnostic_roles[key] = darwin_diagnostic_role(bytes(value.bsd.name))
        return identity

    def _recorded_identity(self, pid: int) -> dict[str, Any] | None:
        # Only failed observations need this history lookup, not every ordinary
        # successful census read. A PID may have more than one recorded lifetime.
        pending = self.pending_discoveries.get(pid)
        if pending is not None:
            return pending["identity"]
        return next((item for item in reversed(self.known.values()) if item["pid"] == pid), None)

    def _discovery_failed(self, identity: dict[str, Any], error: Exception) -> str:
        message = super()._discovery_failed(identity, error)
        # Defer an exhausted observation or missing original-parent lifetime,
        # never structural errors or leaked Mach rights. No relaxed finalizer.
        if isinstance(error, (DarwinObservationExhausted, DiscoveryUncertain)):
            record = self.pending_discoveries.get(identity["pid"])
            if record is None:
                if len(self.discovery_reconciliations) >= 1024:
                    raise OwnershipError("Darwin discovery evidence exceeds its bound")
                record = {"identity": dict(identity), "message": message, "firstFailure": str(error),
                          "failures": 0, "outcome": "unresolved"}
                self.pending_discoveries[identity["pid"]] = record
                self.discovery_reconciliations.append(record)
            record.update(lastIdentity=dict(identity), lastFailure=str(error), failures=record["failures"] + 1)
        return message

    def _reconcile_identity(self, previous: dict[str, Any], failure: DarwinObservationError) -> dict[str, Any] | None:
        # A known child can temporarily become unreadable, including across a
        # privileged exec. Required rechecks are raw and cannot recurse here.
        try:
            return self._observe(previous, "identity", lambda current: current, initial_error=failure)
        except ProcessLookupError:
            return None  # Observed exit/replacement, never permission denial alone.

    def _key(self, identity: dict[str, Any]) -> tuple[int, ...]:
        # Exec can change pidVersion without changing process ownership. Signaling
        # obtains a fresh opaque token and checks the full current identity below.
        return (identity["pid"], identity["uniqueId"], identity["startSeconds"], identity["startMicroseconds"])

    def _observe(self, identity: dict[str, Any], operation: str, action: Any,
                 *, initial_error: DarwinObservationError | None = None) -> Any:
        # libproc's zombie-list lookup can still return a non-SZOMB INEXIT proc
        # after Mach/procargs lookup loses it. INEXIT is pending, not completion.
        # Reconcile only failed observations; do not slow every process census or
        # extend product deadlines. This bounds retries, not a blocking kernel API.
        deadline = time.monotonic() + 0.25
        first_error = last_error = None if initial_error is None else str(initial_error)
        current, outcome, attempts = identity, "unresolved", 0

        def recheck():
            nonlocal current, outcome
            current = self._identity(identity["pid"], required=True)
            if current is None or not current["live"] or self._key(current) != self._key(identity):
                outcome = "absent" if current is None else "nonrunning" if not current["live"] else "replaced"
                raise ProcessLookupError(identity["pid"])
            return current

        try:
            for attempts in range(1, 27):
                try:
                    before = recheck()
                    result = action(before)
                    after = recheck()
                    if after["pidVersion"] != before["pidVersion"]:
                        raise DarwinObservationError("Darwin exec version changed during observation")
                    outcome = "recovered"
                    return result
                except DarwinObservationError as error:
                    last_error = str(error)
                    if first_error is None:
                        first_error = last_error
                remaining = deadline - time.monotonic()
                if remaining <= 0 or attempts == 26:
                    break
                time.sleep(min(0.01, remaining))
            raise DarwinObservationExhausted(f"Darwin {operation} unresolved after bounded observation: {last_error}")
        finally:
            if first_error is not None:
                if len(self.observation_reconciliations) >= 1024:
                    raise OwnershipError("Darwin observation evidence exceeds its bound")
                self.observation_reconciliations.append({"operation": operation, "identity": identity,
                    "lastIdentity": current, "attempts": attempts, "firstFailure": first_error,
                    "lastFailure": last_error, "outcome": outcome})

    def _inspect_environment(self, identity: dict[str, Any]) -> dict[bytes, bytes]:
        return self._observe(identity, "environment", lambda before: self._environment(before["pid"]))

    def _environment(self, pid: int) -> dict[bytes, bytes]:
        mib = (I32 * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2.
        data = ctypes.create_string_buffer(self.argmax)
        length = SIZE(self.argmax)
        ctypes.set_errno(0)
        if self.system.sysctl(mib, 3, data, ctypes.byref(length), None, 0) != 0:
            error = ctypes.get_errno()
            raise DarwinObservationError(f"Darwin process environment failed: errno {error}")
        if length.value > self.argmax:
            raise OwnershipError("Darwin process environment exceeded admitted bound")
        try:
            return parse_procargs2(data.raw[:length.value])
        except OwnershipError as error:
            raise DarwinObservationError(str(error)) from error

    def _acquire(self, identity: dict[str, Any]) -> AuditToken:
        return self._observe(identity, "task token", self._acquire_once)

    def _acquire_once(self, identity: dict[str, Any]) -> AuditToken:
        port = U32()
        try:
            result = self.system.task_name_for_pid(self.self_port, identity["pid"], ctypes.byref(port))
            if result != 0 or not port.value:
                raise DarwinObservationError(f"Darwin task-name access unavailable: Mach result {result}")
            token = AuditToken()
            count = U32(8)
            result = self.system.task_info(port, 15, ctypes.byref(token), ctypes.byref(count))
            if result != 0 or count.value != 8:
                raise DarwinObservationError(f"Darwin TASK_AUDIT_TOKEN unavailable: Mach result {result}")
            return token
        finally:
            if port.value and self.system.mach_port_deallocate(self.self_port, port) != 0:
                # Never catch/retry a leaked right as an ordinary observation error.
                raise OwnershipError("Cannot release the owned Darwin task-name port")

    def _pending_context(self) -> dict[str, Any]:
        """Recorded context only: cannot resolve a denial or confer authority.

        This deliberately makes no native call and does not try another proof
        after failed environment admission. Even recorded positive ancestry
        leaves the existing discovery error and finalization failure intact.
        """
        roles: dict[str, int] = {}
        parentage: dict[str, int] = {}
        for record in self.pending_discoveries.values():
            identity = record.get("lastIdentity", record["identity"])
            role = getattr(self, "diagnostic_roles", {}).get(self._key(identity), "UNRECORDED")
            roles[role] = roles.get(role, 0) + 1
            try:
                proof = self._parent_proof(identity)
                label = "BASELINE" if proof is None else "OWNED"
            except DiscoveryUncertain:
                label = "TRACED" if identity["flags"] & 2 else "UNOBSERVED"
            except OwnershipError:
                # This is only descriptive: the original unknown lifetime still
                # prevents cleanup, and no malformed lineage is accepted.
                label = "INVALID"
            parentage[label] = parentage.get(label, 0) + 1
        return {"scope": "RECORDED_CONTEXT_NOT_OWNERSHIP_OR_EXIT", "roles": roles, "parentage": parentage}

    def description(self) -> dict[str, Any]:
        return {**super().description(), "scope": "controlled-domains-pipes-and-observed-nonreaper-parent-lifetimes",
                "ownershipProofs": list(self.ownership_proofs.values()),
                "foreignAuditSessions": list(self.foreign_sessions.values()),
                "inheritedPipeBound": self.pipe_marker is not None,
                "unclassifiedLifetimes": list(self.pending_discoveries.values()),
                "unclassifiedContext": self._pending_context(),
                "observationReconciliations": self.observation_reconciliations}

    def close(self) -> None:
        try:
            super().close()
        finally:
            descriptors, self.pipe_fds = self.pipe_fds, ()
            self.pipe_marker = None
            for descriptor in descriptors:
                os.close(descriptor)

    def _send(self, identity: dict[str, Any], handle: AuditToken, signum: int) -> None:
        # A real token is reacquired after exec-version changes; never os.kill(pid).
        token = self._acquire(identity)
        result = self.proc.proc_signal_with_audittoken(ctypes.byref(token), signum)
        if result == errno.ESRCH:
            raise ProcessLookupError(identity["pid"])
        if result != 0:
            raise OwnershipError(f"Darwin identity-scoped signal failed: errno {result}")


class SecurityAttributes(ctypes.Structure):
    _fields_ = [("length", U32), ("descriptor", PTR), ("inherit", I32)]


class ProcessInformation(ctypes.Structure):
    _fields_ = [("process", PTR), ("thread", PTR), ("pid", U32), ("tid", U32)]


class StartupInfo(ctypes.Structure):
    _fields_ = [("cb", U32), ("reserved", ctypes.c_wchar_p), ("desktop", ctypes.c_wchar_p),
                ("title", ctypes.c_wchar_p)] + [(name, U32) for name in
                ("x", "y", "xsize", "ysize", "xchars", "ychars", "fill", "flags")] + [
                ("show", ctypes.c_uint16), ("reserved2size", ctypes.c_uint16), ("reserved2", PTR),
                ("stdin", PTR), ("stdout", PTR), ("stderr", PTR)]


class StartupInfoEx(ctypes.Structure):
    _fields_ = [("startup", StartupInfo), ("attributes", PTR)]


class JobBasicLimits(ctypes.Structure):
    _fields_ = [("processTime", ctypes.c_int64), ("jobTime", ctypes.c_int64), ("flags", U32),
                ("minimumWorkingSet", SIZE), ("maximumWorkingSet", SIZE), ("activeProcessLimit", U32),
                ("affinity", SIZE), ("priority", U32), ("scheduling", U32)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, U64) for name in ("readOps", "writeOps", "otherOps", "readBytes", "writeBytes", "otherBytes")]


class JobExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", JobBasicLimits), ("io", IoCounters)] + [(name, SIZE) for name in
                ("processMemory", "jobMemory", "peakProcessMemory", "peakJobMemory")]


class FileTime(ctypes.Structure):
    _fields_ = [("low", U32), ("high", U32)]


def batch_command_line(cmd: str, argv: list[str]) -> str:
    """Restricted cmd.exe grammar, not arbitrary shell escaping or `call`.

    %* in the checked-in Gradle batch file ultimately reaches the Java CRT.
    Doubling trailing backslashes prevents the closing quote becoming an escaped
    quote there. Reject embedded quotes and every expansion/control metacharacter.
    """
    forbidden = re.compile(r'[\x00-\x1f"%!&|<>^()]')
    if not argv or any(forbidden.search(arg) for arg in [cmd, *argv]):
        raise OwnershipError("Unsupported batch argument expansion/control character")

    def quote(arg: str) -> str:
        trailing = len(arg) - len(arg.rstrip("\\"))
        return '"' + arg + ("\\" * trailing) + '"'

    inner = " ".join(quote(arg) for arg in argv)
    return f'{subprocess.list2cmdline([cmd])} /d /s /v:off /c "{inner}"'


class WinApi:
    def __init__(self):
        if os.name != "nt" or ctypes.sizeof(PTR) != 8:
            raise OwnershipError("Windows audit ownership requires native 64-bit Python")
        if tuple(ctypes.sizeof(kind) for kind in (SecurityAttributes, ProcessInformation, StartupInfo,
                                                StartupInfoEx, JobBasicLimits, IoCounters, JobExtendedLimits)) != \
                (24, 24, 104, 112, 64, 48, 144):
            raise OwnershipError("Unsupported Windows Job Object ABI layout")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._bind("CreateJobObjectW", [PTR, ctypes.c_wchar_p], PTR)
        self._bind("SetInformationJobObject", [PTR, I32, PTR, U32], I32)
        self._bind("QueryInformationJobObject", [PTR, I32, PTR, U32, ctypes.POINTER(U32)], I32)
        self._bind("TerminateJobObject", [PTR, U32], I32)
        self._bind("IsProcessInJob", [PTR, PTR, ctypes.POINTER(I32)], I32)
        self._bind("CreatePipe", [ctypes.POINTER(PTR), ctypes.POINTER(PTR), ctypes.POINTER(SecurityAttributes), U32], I32)
        self._bind("SetHandleInformation", [PTR, U32, U32], I32)
        self._bind("CreateFileW", [ctypes.c_wchar_p, U32, U32, ctypes.POINTER(SecurityAttributes), U32, U32, PTR], PTR)
        self._bind("InitializeProcThreadAttributeList", [PTR, U32, U32, ctypes.POINTER(SIZE)], I32)
        self._bind("UpdateProcThreadAttribute", [PTR, U32, SIZE, PTR, SIZE, PTR, PTR], I32)
        self._bind("DeleteProcThreadAttributeList", [PTR], None)
        self._bind("CreateProcessW", [ctypes.c_wchar_p, ctypes.c_wchar_p, PTR, PTR, I32, U32,
                                      PTR, ctypes.c_wchar_p, ctypes.POINTER(StartupInfoEx),
                                      ctypes.POINTER(ProcessInformation)], I32)
        self._bind("ResumeThread", [PTR], U32)
        self._bind("CloseHandle", [PTR], I32)
        self._bind("WaitForSingleObject", [PTR, U32], U32)
        self._bind("GetExitCodeProcess", [PTR, ctypes.POINTER(U32)], I32)
        self._bind("GetProcessTimes", [PTR, ctypes.POINTER(FileTime), ctypes.POINTER(FileTime),
                                       ctypes.POINTER(FileTime), ctypes.POINTER(FileTime)], I32)
        self._bind("OpenProcess", [U32, I32, U32], PTR)
        self._bind("GenerateConsoleCtrlEvent", [U32, U32], I32)
        self._bind("GetSystemDirectoryW", [ctypes.c_wchar_p, U32], U32)

    def _bind(self, name: str, args: list[Any], result: Any) -> None:
        function = getattr(self.kernel, name)
        function.argtypes, function.restype = args, result
        setattr(self, name, function)

    def check(self, result: Any, operation: str) -> Any:
        if not result:
            raise OwnershipError(f"Windows {operation} failed: error {ctypes.get_last_error()}")
        return result

    def close(self, handle: Any) -> None:
        if handle:
            self.check(self.CloseHandle(handle), "CloseHandle")

    def identity(self, handle: Any, pid: int) -> dict[str, Any]:
        creation, exit_time, kernel, user = FileTime(), FileTime(), FileTime(), FileTime()
        self.check(self.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                        ctypes.byref(kernel), ctypes.byref(user)), "GetProcessTimes")
        return {"pid": pid, "creationFileTime": (creation.high << 32) | creation.low}

    def cmd(self) -> str:
        output = ctypes.create_unicode_buffer(32768)
        length = self.GetSystemDirectoryW(output, len(output))
        if not 0 < length < len(output):
            raise OwnershipError("Cannot resolve trusted Windows System32 directory")
        path = str(Path(output.value) / "cmd.exe")
        if not Path(path).is_file():
            raise OwnershipError("Native System32 cmd.exe is unavailable")
        return path


class WindowsProcess:
    def __init__(self, api: WinApi, handle: Any, pid: int, stdout: Any, stderr: Any):
        self.api, self.handle, self.pid = api, handle, pid
        self.stdout, self.stderr = stdout, stderr
        self.returncode: int | None = None

    def poll(self) -> int | None:
        if self.returncode is not None:
            return self.returncode
        result = self.api.WaitForSingleObject(self.handle, 0)
        if result == 258:  # WAIT_TIMEOUT; exit code 259 alone is not liveness.
            return None
        if result != 0:
            raise OwnershipError("Cannot wait on owned Windows process handle")
        code = U32()
        self.api.check(self.api.GetExitCodeProcess(self.handle, ctypes.byref(code)), "GetExitCodeProcess")
        self.returncode = code.value
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        deadline = None if timeout is None else time.monotonic() + timeout
        while self.poll() is None:
            if deadline is not None and time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired("owned Windows process", timeout)
            time.sleep(0.05)
        return self.returncode  # type: ignore[return-value]

    def close(self) -> None:
        if self.handle:
            self.api.close(self.handle)
            self.handle = None


class WindowsScope:
    name = "windows-job-list-suspended"

    def __init__(self, job: str, invocation: str, state: str, home: str):
        self.api = WinApi()
        self.job_id, self.invocation = job, invocation
        self.leaders: list[WindowsProcess] = []
        self.launches: list[dict[str, Any]] = []
        self.known: dict[tuple[int, int], dict[str, Any]] = {}
        self.discovery_errors: set[str] = set()
        self.job = self.api.check(self.api.CreateJobObjectW(None, None), "CreateJobObjectW")
        try:
            limits = JobExtendedLimits()
            limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE; no breakaway bits.
            self.api.check(self.api.SetInformationJobObject(self.job, 9, ctypes.byref(limits),
                                                           ctypes.sizeof(limits)), "SetInformationJobObject")
        except BaseException:
            self.api.close(self.job)
            self.job = None
            raise

    def _member_pids(self) -> list[int]:
        capacity = 64
        for _ in range(12):
            if capacity > MAX_PROCESSES:
                break
            data = ctypes.create_string_buffer(8 + ctypes.sizeof(SIZE) * capacity)
            returned = U32()
            result = self.api.QueryInformationJobObject(self.job, 3, data, len(data), ctypes.byref(returned))
            assigned, count = struct.unpack_from("=II", data.raw)
            if result and count <= capacity and assigned <= capacity:
                array = (SIZE * count).from_buffer(data, 8)
                return [int(pid) for pid in array]
            if not result and ctypes.get_last_error() != 234:  # ERROR_MORE_DATA
                self.api.check(result, "QueryInformationJobObject")
            capacity = max(capacity * 2, assigned + 16)
        raise OwnershipError("Windows owned job membership exceeded its bound")

    def discover(self) -> list[dict[str, Any]]:
        result = []
        for pid in self._member_pids():
            handle = self.api.OpenProcess(0x1000 | 0x100000, 0, pid)
            if not handle:
                if pid not in self._member_pids():
                    continue
                self.api.check(handle, "OpenProcess owned-job member")
            try:
                member = I32()
                self.api.check(self.api.IsProcessInJob(handle, self.job, ctypes.byref(member)), "IsProcessInJob")
                if not member.value:
                    continue  # PID reused outside the job; never signal it.
                if self.api.WaitForSingleObject(handle, 0) == 0:
                    continue
                identity = self.api.identity(handle, pid)
                key = (pid, identity["creationFileTime"])
                identity = {**self.known.get(key, {}), **identity}
                self.known[key] = identity
                result.append(identity)
            finally:
                self.api.close(handle)
        return sorted(result, key=lambda item: item["pid"])

    def spawn(self, argv: list[str], cwd: str, env: dict[str, str]) -> WindowsProcess:
        import msvcrt
        launch = {"api": "CreateProcessW", "requestedArgv": list(argv), "cwd": cwd,
                  "created": False, "resumed": False}
        self.launches.append(launch)
        actual = resolve_executable(argv, cwd, env)
        launch["resolvedArgv"] = actual
        batch = Path(actual[0]).suffix.lower() in (".bat", ".cmd")
        if batch:
            executable = self.api.cmd()
            command = batch_command_line(executable, actual)
        else:
            if Path(actual[0]).suffix.lower() not in (".exe", ".com"):
                raise OwnershipError("Native Windows command requires .exe/.com or explicit interpreter")
            executable = actual[0]
            command = subprocess.list2cmdline(actual)
        if len(command) >= 32767:
            raise OwnershipError("Windows command line exceeds CreateProcessW bound")
        # Windows receives one command-line string, not an argv vector. Retain
        # exactly what CreateProcessW receives, including trusted cmd.exe framing
        # for batch files; never mislabel the logical wrapper argv as the native
        # executable or reverse-parse a supposedly equivalent argument list.
        launch.update({"applicationName": executable, "commandLine": command, "batch": batch})
        attributes = None
        initialized = False
        handles: list[Any] = []
        streams: list[Any] = []
        process = ProcessInformation()
        created = False
        try:
            security = SecurityAttributes(ctypes.sizeof(SecurityAttributes), None, 1)
            reads, writes = [], []
            for _ in range(2):
                read, write = PTR(), PTR()
                self.api.check(self.api.CreatePipe(ctypes.byref(read), ctypes.byref(write),
                                                    ctypes.byref(security), 0), "CreatePipe")
                handles.extend([read.value, write.value])
                self.api.check(self.api.SetHandleInformation(read, 1, 0), "SetHandleInformation")
                reads.append(read.value)
                writes.append(write.value)
            stdin = self.api.CreateFileW("NUL", 0x80000000, 3, ctypes.byref(security), 3, 0x80, None)
            if stdin in (None, ctypes.c_void_p(-1).value):
                raise OwnershipError("Cannot create owned Windows NUL stdin")
            handles.append(stdin)
            size = SIZE()
            self.api.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
            if not size.value or size.value > 1024 * 1024:
                raise OwnershipError("Invalid Windows startup attribute allocation")
            attributes = ctypes.create_string_buffer(size.value)
            self.api.check(self.api.InitializeProcThreadAttributeList(attributes, 2, 0,
                                                                       ctypes.byref(size)), "Initialize attributes")
            initialized = True
            inherited = (PTR * 3)(stdin, *writes)
            job_list = (PTR * 1)(self.job)
            self.api.check(self.api.UpdateProcThreadAttribute(attributes, 0, 0x00020002, inherited,
                                                               ctypes.sizeof(inherited), None, None), "HANDLE_LIST")
            self.api.check(self.api.UpdateProcThreadAttribute(attributes, 0, 0x0002000D, job_list,
                                                               ctypes.sizeof(job_list), None, None), "JOB_LIST")
            startup = StartupInfoEx()
            startup.startup.cb = ctypes.sizeof(startup)
            startup.startup.flags = 0x100  # STARTF_USESTDHANDLES
            startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = stdin, *writes
            startup.attributes = ctypes.cast(attributes, PTR)
            if any("\0" in key or "=" in key or "\0" in value for key, value in env.items()):
                raise OwnershipError("Invalid Windows environment field")
            environment = "\0".join(f"{key}={env[key]}" for key in sorted(env, key=str.upper)) + "\0\0"
            env_buffer = ctypes.create_unicode_buffer(environment)
            mutable = ctypes.create_unicode_buffer(command)
            flags = 0x4 | 0x200 | 0x400 | 0x80000  # SUSPENDED, group, Unicode, EXTENDED_STARTUPINFO
            self.api.check(self.api.CreateProcessW(executable, mutable, None, None, 1, flags, env_buffer,
                                                   cwd, ctypes.byref(startup), ctypes.byref(process)),
                           "CreateProcessW (atomic job assignment)")
            created = True
            launch.update({"created": True, "pid": process.pid})
            member = I32()
            self.api.check(self.api.IsProcessInJob(process.process, self.job, ctypes.byref(member)),
                           "pre-resume IsProcessInJob")
            if not member.value:
                raise OwnershipError("Suspended Windows child lacks required job membership")
            identity = self.api.identity(process.process, process.pid)
            identity["jobAssignedBeforeResume"] = True
            launch["jobAssignedBeforeResume"] = True
            self.known[(process.pid, identity["creationFileTime"])] = identity
            for handle in reads:
                fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
                handles.remove(handle)  # Descriptor now owns the OS handle.
                streams.append(os.fdopen(fd, "rb", buffering=0))
            child = WindowsProcess(self.api, process.process, process.pid, streams[0], streams[1])
            self.leaders.append(child)
            process.process = None  # Child object now owns the process handle.
            if self.api.ResumeThread(process.thread) == 0xFFFFFFFF:
                raise OwnershipError("ResumeThread failed for assigned Windows child")
            launch["resumed"] = True
            streams.clear()  # The caller's independent tee threads now own them.
            return child
        except BaseException:
            if created:
                self.api.TerminateJobObject(self.job, 125)
            raise
        finally:
            if initialized:
                self.api.DeleteProcThreadAttributeList(attributes)
            for handle in handles:
                self.api.close(handle)
            for stream in streams:
                stream.close()
            self.api.close(process.thread)
            self.api.close(process.process)

    def signal_all(self, signum: int) -> None:
        if signum == SIG_KILL:
            self.api.check(self.api.TerminateJobObject(self.job, 125), "TerminateJobObject")
            return
        # A best-effort scoped CTRL_BREAK may be unavailable for detached leaders.
        # Hard cleanup below always uses the proven job, never a process-group0 signal.
        for child in self.leaders:
            if child.pid > 0 and child.poll() is None:
                self.api.GenerateConsoleCtrlEvent(1, child.pid)

    def drain(self, grace: float = 5.0, kill_wait: float = 5.0) -> list[dict[str, Any]]:
        if self.discover():
            self.signal_all(SIG_TERM)
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            if not self.discover():
                return []
            time.sleep(0.1)
        self.signal_all(SIG_KILL)
        deadline = time.monotonic() + kill_wait
        while time.monotonic() < deadline:
            if not self.discover():
                return []
            time.sleep(0.1)
        return self.discover()

    def description(self) -> dict[str, Any]:
        return {"backend": self.name, "scope": "kernel-job-no-breakaway-kill-on-close",
                "invocation": self.invocation, "job": self.job_id,
                "launches": self.launches,
                "startedIdentities": sorted(self.known.values(), key=lambda item: item["pid"]),
                "discoveryErrors": sorted(self.discovery_errors)}

    def close(self) -> None:
        for child in self.leaders:
            child.close()
        if self.job:
            self.api.close(self.job)
            self.job = None


def make_scope(job: str, invocation: str, state: str, home: str) -> PosixScope | WindowsScope:
    kind = {"Linux": LinuxScope, "Darwin": DarwinScope, "Windows": WindowsScope}.get(platform.system())
    if kind is None:
        raise OwnershipError("Unsupported native process-ownership backend")
    return kind(job, invocation, state, home)
