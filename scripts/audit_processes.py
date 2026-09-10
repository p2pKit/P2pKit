#!/usr/bin/env python3
"""Identity-scoped children for the opt-in audit executor; never a process-name sweep.

Windows uses a kernel Job Object attached atomically before resume. POSIX discovers
controlled marker-inheriting descendants and signals through pidfds (Linux) or real
Mach audit tokens (macOS). POSIX markers are not containment of malicious children
that erase their environment or delegate work to another service. Native API/fixture
admission is required; unsupported ownership fails closed rather than using PID kill.
"""
from __future__ import annotations

import ctypes
import errno
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import struct
import subprocess
import time
from typing import Any

JOB_ENV = "P2PKIT_AUDIT_JOB_ID"
CHAIN_ENV = "P2PKIT_AUDIT_OWNERSHIP_CHAIN"
DOMAINS_ENV = "P2PKIT_AUDIT_OWNERSHIP_DOMAINS"
STATE_ENV = "P2PKIT_AUDIT_STATE_DIR"
MAX_PROCESS_BYTES = 8 * 1024 * 1024
MAX_PROCESSES = 65536
SIG_TERM = 15
SIG_KILL = 9


class OwnershipError(RuntimeError):
    """Ownership cannot be established or finalized safely."""


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
        for pid in dict.fromkeys([*self._pids(), *self.pending_discoveries]):
            if pid == os.getpid():
                continue
            identity = self._identity(pid)
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
            if not self._ours(environment):
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
            if not live:
                quiet += 1
                if quiet >= 3:
                    return []
            else:
                quiet = 0
                self.signal_all(SIG_TERM)
            time.sleep(0.1)
        self.signal_all(SIG_KILL)
        end = time.monotonic() + kill_wait
        quiet = 0
        while time.monotonic() < end:
            live = self.discover()
            if not live:
                quiet += 1
                if quiet >= 3:
                    return []
            else:
                quiet = 0
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

    def _identity(self, pid: int) -> dict[str, Any] | None:
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
            if any(key[0] == pid for key in self.known):
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

    def _acquire(self, identity: dict[str, Any]) -> int:
        handle = os.pidfd_open(identity["pid"], 0)
        current = self._identity(identity["pid"])
        if current is None or not current["live"] or self._key(current) != self._key(identity):
            os.close(handle)
            raise ProcessLookupError(identity["pid"])
        return handle

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


class DarwinObservationError(OwnershipError):
    """A failed observation, not proof of exit or an unreleased kernel right."""


class DarwinObservationExhausted(OwnershipError):
    """Still unresolved at this census; a later positive observation may reconcile it."""


class DarwinScope(PosixScope):
    name = "darwin-libproc-audit-token"

    def _admit(self) -> None:
        self.observation_reconciliations: list[dict[str, Any]] = []
        if (ctypes.sizeof(DarwinBsdInfo), ctypes.sizeof(DarwinUniqueInfo), ctypes.sizeof(DarwinIdentity),
                ctypes.sizeof(AuditToken)) != (136, 56, 192, 32):
            raise OwnershipError("Unsupported Darwin process ABI layout")
        try:
            self.proc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
            self.system = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
            self.proc.proc_pidinfo.argtypes = [I32, I32, U64, PTR, I32]
            self.proc.proc_pidinfo.restype = I32
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
        self._acquire(identity)

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
        return {"pid": pid, "uid": value.bsd.uid, "parentPid": value.bsd.ppid, "group": value.bsd.pgid,
                "uniqueId": value.unique.uniqueid, "parentUniqueId": value.unique.parentuniqueid,
                "pidVersion": value.unique.pidversion, "startSeconds": value.bsd.startsec,
                "startMicroseconds": value.bsd.startusec, "realUid": value.bsd.ruid,
                "status": value.bsd.status, "flags": value.bsd.flags, "live": value.bsd.status not in (0, 5)}

    def _recorded_identity(self, pid: int) -> dict[str, Any] | None:
        # Only failed observations need this history lookup, not every ordinary
        # successful census read. A PID may have more than one recorded lifetime.
        pending = self.pending_discoveries.get(pid)
        if pending is not None:
            return pending["identity"]
        return next((item for item in reversed(self.known.values()) if item["pid"] == pid), None)

    def _discovery_failed(self, identity: dict[str, Any], error: Exception) -> str:
        message = super()._discovery_failed(identity, error)
        # Defer only a reconciler's exhausted observation, never structural errors
        # or leaked Mach rights. No extra wait or relaxed finalizer is introduced.
        if isinstance(error, DarwinObservationExhausted):
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

    def description(self) -> dict[str, Any]:
        return {**super().description(), "observationReconciliations": self.observation_reconciliations}

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
