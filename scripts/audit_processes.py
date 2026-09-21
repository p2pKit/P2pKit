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
import io
import json
import math
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


class DrainDeadlineExceeded(OwnershipError):
    """An explicit retirement phase expired; never evidence of disappearance."""


def _finite_number(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _drain_phase_ends(grace: float, kill_wait: float, deadline: float) -> tuple[float, float, float]:
    if not all(_finite_number(value) for value in (grace, kill_wait, deadline)) or grace < 0 or kill_wait < 0:
        raise OwnershipError("Explicit native drain requires finite nonboolean end and nonnegative durations")
    started = time.monotonic()
    if not _finite_number(started):
        raise OwnershipError("Invalid native drain monotonic observation")
    if deadline <= started:
        raise DrainDeadlineExceeded("Native drain absolute end is already expired")
    # Fix both ends before any discovery or signaling. A slow TERM phase never
    # creates a fresh KILL grace or extends the caller's original monotonic end.
    return started, min(started + grace, deadline), min(started + grace + kill_wait, deadline)


def _check_drain_deadline(deadline: float | None) -> None:
    if deadline is None:
        return  # The existing no-keyword route does not acquire a new clock.
    if not _finite_number(deadline):
        raise OwnershipError("Invalid native drain absolute phase end")
    now = time.monotonic()
    if not _finite_number(now):
        raise OwnershipError("Invalid native drain monotonic observation")
    if now >= deadline:
        raise DrainDeadlineExceeded("Native drain absolute phase end exhausted")


def _bounded_drain(scope: Any, grace: float, kill_wait: float, deadline: float, *,
                   quiet_required: int, repeat_signals: bool = True) -> list[dict[str, Any]]:
    """Bound acceptance, not synchronous kernel latency; an outer watchdog is required.

    Existing discover() inner loops/native calls retain their original bounds.
    A call already entered can finish late; its result cannot authorize success
    or new signals. Callers must also postcheck their end and resource closure.
    Darwin uses its own pending-lifetime reconciliation loop below.
    """
    _, term_end, kill_end = _drain_phase_ends(grace, kill_wait, deadline)
    live = []
    for signum, end in ((SIG_TERM, term_end), (SIG_KILL, kill_end)):
        quiet, sent = 0, False
        try:
            while True:
                _check_drain_deadline(end)
                observed = scope.discover()
                _check_drain_deadline(end)
                live = observed  # Only completed timely observations may be returned.
                if not live and not scope.discovery_errors and not getattr(scope, "pending_discoveries", None):
                    quiet += 1
                    if quiet >= quiet_required:
                        _check_drain_deadline(end)
                        return []
                else:
                    quiet = 0
                    if repeat_signals or not sent:
                        scope.signal_all(signum, deadline=end)
                        _check_drain_deadline(end)
                        sent = True
                remaining = end - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(0.1, remaining))
        except DrainDeadlineExceeded as error:
            if retirement_details(error):
                raise  # An expired operation cannot erase UNKNOWN resource cleanup.
            # Escalation, if any, spends only the already fixed second phase.
            # No quiet count, late observation or late signal result is accepted.
            continue
    if live:
        return live  # Conservative last timely census, not a new late discovery.
    raise DrainDeadlineExceeded("Native drain did not establish timely quiet retirement within its absolute bounds")


MAX_RETIREMENT_ERRORS = 256


def _exception_text(error: BaseException) -> str:
    try:
        message = str(error)[:2048]
    except BaseException:
        message = "<exception message unavailable>"
    return f"{type(error).__name__}: {message}"


def retirement_details(error: BaseException) -> dict[str, Any]:
    """Bounded, JSON-safe secondary failures; never mutate the primary's args/type."""
    value = getattr(error, "_p2pkit_retirement", None)
    return {"status": "UNKNOWN", "resources": [dict(row) for row in value["resources"]],
            "omitted": value["omitted"]} if value is not None else {}


def _retirement_text(row: dict[str, Any]) -> str:
    backend = "POSIX" if row["phase"].startswith("posix-") else "Windows"
    return f"{backend} resource retirement UNKNOWN ({row['phase']}/{row['resource']}): {row['error']}"


def format_ownership_error(error: BaseException) -> str:
    """Use at real receipt boundaries: str(error) alone omits exception notes."""
    text = _exception_text(error)
    detail = retirement_details(error)
    if detail:
        text += "; " + "; ".join(_retirement_text(row) for row in detail["resources"])
        if detail["omitted"]:
            text += f"; retirement UNKNOWN: {detail['omitted']} further resource errors exceed the evidence bound"
    return text


def _retire_actions(actions: list[Any], phase: str) -> tuple[list[dict[str, Any]], list[Any]]:
    outcomes, failures = [], []
    for label, action in actions:
        row = {"phase": phase, "resource": label, "status": "RETIRED"}
        try:
            action()
        except BaseException as error:
            row.update(status="UNKNOWN", error=_exception_text(error)[:512])
            failures.append((row, error))
        outcomes.append(row)
    return outcomes, failures


def _finish_retirement(failures: list[Any], original: BaseException | None = None) -> None:
    if not failures:
        return
    # Preserve every attempt even if the bounded carrier cannot hold every
    # diagnostic. Overflow is explicit UNKNOWN, never disposal/next-run authority.
    rows, omitted = [], 0
    for row, error in failures:
        rows.append(row)
        nested = retirement_details(error)
        rows.extend(nested.get("resources", []))
        omitted += nested.get("omitted", 0)
    cancellation = next((error for _, error in failures if not isinstance(error, Exception)), None)
    failure = original if original is not None else cancellation
    if failure is None:
        backend = "POSIX" if rows[0]["phase"].startswith("posix-") else "Windows"
        failure = OwnershipError(f"{backend} resource retirement UNKNOWN; "
                                 "all remaining resources attempted; " +
                                 "; ".join(_retirement_text(row) for row in rows[:MAX_RETIREMENT_ERRORS]))
    prior = retirement_details(failure)
    combined = [*prior.get("resources", []), *rows]
    failure._p2pkit_retirement = {"status": "UNKNOWN", "resources": combined[:MAX_RETIREMENT_ERRORS],
        "omitted": prior.get("omitted", 0) + omitted + max(0, len(combined) - MAX_RETIREMENT_ERRORS)}
    # Notes aid tracebacks on newer Python; the explicit carrier/formatter above
    # also works on Python 3.9 and survives constructor failure with scope=None.
    notes = [_retirement_text(row) for row in rows[:MAX_RETIREMENT_ERRORS]]
    failure.__notes__ = [*getattr(failure, "__notes__", ()), *notes]
    if original is None:
        if cancellation is not None:
            raise cancellation
        raise failure from failures[0][1]


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
    """Serialized, non-reentrant controller; close is not concurrent cancellation.

    Callers must drain their writer domain before handle finalization. Closing
    descriptors or polling leaders alone does not prove process retirement.
    """
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
        self._closed = False
        self._retirement_error: BaseException | None = None
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

    def _send(self, identity: dict[str, Any], handle: Any, signum: int, *, deadline: float | None = None) -> None:
        raise NotImplementedError

    def _release(self, handle: Any) -> None:
        pass

    def _ensure_open(self) -> None:
        failure = getattr(self, "_retirement_error", None)
        if failure is not None:
            raise failure
        if getattr(self, "_closed", False):
            raise OwnershipError("POSIX process owner is closed")

    def _retire_resources(self, actions: list[Any], phase: str, *, original: BaseException | None = None) -> None:
        # Preserve the closed four-field carrier consumed by private custody.
        _, failures = _retire_actions(actions, "posix-" + phase)
        if not failures:
            return
        prior = getattr(self, "_retirement_error", None)
        primary = prior if prior is not None else original if original is not None else failures[0][1]
        self._retirement_error = primary  # UNKNOWN remains terminal, even after a later successful close.
        _finish_retirement(failures, primary)
        if original is None:
            raise primary

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
        self._ensure_open()
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
                if retirement_details(error):
                    raise
                self._discovery_failed(identity, error)
                continue
            except ProcessLookupError as error:
                if retirement_details(error):
                    raise
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
            except ProcessLookupError as error:
                if retirement_details(error):
                    raise  # A vanished lifetime does not resolve an uncertain pidfd close.
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

    def spawn(self, argv: list[str], cwd: str, env: dict[str, str], *,
              stdout: Any = None, stderr: Any = None) -> PosixProcess:
        self._ensure_open()
        # Optional privately owned sinks avoid an additional pipe/thread owner.
        # The caller retains both sinks until complete scope retirement, bounds
        # live output size, and verifies/syncs them before accepting a result.
        # The default pipe contract used by existing executor callers is unchanged.
        if (stdout is None) != (stderr is None):
            raise OwnershipError("Both owned output sinks are required")
        launch = {"api": "subprocess.Popen", "requestedArgv": list(argv),
                  "cwd": cwd, "shell": False, "created": False}
        if stdout is not None:
            launch["outputMode"] = "caller-owned-files"
        self.launches.append(launch)
        actual = resolve_executable(argv, cwd, env)
        launch.update({"resolvedArgv": actual, "executable": actual[0]})
        process = PosixProcess(subprocess.Popen(actual, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                               stdout=subprocess.PIPE if stdout is None else stdout,
                                               stderr=subprocess.PIPE if stderr is None else stderr,
                                               start_new_session=True, close_fds=True, bufsize=0))
        launch.update({"created": True, "pid": process.pid})
        self.leaders.append(process)
        # A very short leader may already have exited; marker discovery still finds
        # its detached descendants. No fallback broad process-group signaling.
        self.discover()
        return process

    def signal_all(self, signum: int, *, deadline: float | None = None) -> None:
        self._ensure_open()
        _check_drain_deadline(deadline)
        live = self.discover()
        _check_drain_deadline(deadline)
        for identity in live:
            _check_drain_deadline(deadline)
            key = self._key(identity)
            try:
                if deadline is None:
                    self._send(identity, self.handles[key], signum)
                else:
                    self._send(identity, self.handles[key], signum, deadline=deadline)
            except ProcessLookupError as error:
                if retirement_details(error):
                    raise
            _check_drain_deadline(deadline)

    def drain(self, grace: float = 5.0, kill_wait: float = 5.0, *,
              deadline: float | None = None) -> list[dict[str, Any]]:
        self._ensure_open()
        if deadline is not None:
            return _bounded_drain(self, grace, kill_wait, deadline, quiet_required=3)
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
        if getattr(self, "_closed", False):
            failure = getattr(self, "_retirement_error", None)
            if failure is not None:
                raise failure
            return
        # Prepare the complete once-only roster before any native close. A close
        # can raise after releasing its descriptor; retrying may hit a reused fd.
        actions = [(f"handle:{index}", lambda handle=handle: self._release(handle))
                   for index, handle in enumerate(self.handles.values())]
        actions += [(f"leader:{index}", lambda process=process: process.close())
                    for index, process in enumerate(self.leaders)]
        self._closed = True
        self.handles.clear()
        self.leaders.clear()
        self._retire_resources(actions, "scope-close")
        failure = getattr(self, "_retirement_error", None)
        if failure is not None:
            raise failure


class LinuxScope(PosixScope):
    name = "linux-proc-pidfd"

    def _admit(self) -> None:
        if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
            raise OwnershipError("Linux ownership requires pidfd_open and pidfd_send_signal")
        identity = self._identity(os.getpid())
        if identity is None:
            raise OwnershipError("Cannot inspect the Linux controller identity")
        handle = self._acquire(identity)
        original = None
        try:
            signal.pidfd_send_signal(handle, 0)
        except BaseException as error:
            original = error
            raise
        finally:
            self._retire_resources([("pidfd", lambda: os.close(handle))], "admission-probe", original=original)

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
        self._ensure_open()
        handle = os.pidfd_open(identity["pid"], 0)
        try:
            current = self._identity(identity["pid"])
            if current is None or not current["live"] or self._key(current) != self._key(identity):
                raise ProcessLookupError(identity["pid"])
            self._ensure_open()
        except BaseException as error:
            self._retire_resources([("pidfd", lambda: os.close(handle))], "acquire", original=error)
            raise
        return handle

    def _send(self, identity: dict[str, Any], handle: int, signum: int, *, deadline: float | None = None) -> None:
        self._ensure_open()
        _check_drain_deadline(deadline)
        signal.pidfd_send_signal(handle, signum)
        _check_drain_deadline(deadline)

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
        self.drain_reconciliations: list[dict[str, Any]] = []
        self.active_drain: dict[str, Any] | None = None
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
        except ProcessLookupError as error:
            if retirement_details(error):
                raise
            return None  # Observed exit/replacement, never permission denial alone.

    def _key(self, identity: dict[str, Any]) -> tuple[int, ...]:
        # Exec can change pidVersion without changing process ownership. Signaling
        # obtains a fresh opaque token and checks the full current identity below.
        return (identity["pid"], identity["uniqueId"], identity["startSeconds"], identity["startMicroseconds"])

    def _observe(self, identity: dict[str, Any], operation: str, action: Any,
                 *, initial_error: DarwinObservationError | None = None) -> Any:
        self._ensure_open()
        if initial_error is not None and retirement_details(initial_error):
            self._retirement_error = initial_error
            raise initial_error
        # libproc's zombie-list lookup can still return a non-SZOMB INEXIT proc
        # after Mach/procargs lookup loses it. INEXIT is pending, not completion.
        # Reconcile only failed observations; do not slow every process census or
        # extend product deadlines. This bounds retries, not a blocking kernel API.
        deadline = time.monotonic() + 0.25
        first_error = last_error = None if initial_error is None else str(initial_error)
        current, outcome, attempts = identity, "unresolved", 0
        primary = None

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
                    if retirement_details(error):
                        raise  # A failed Mach-right release is not a retryable observation.
                    last_error = str(error)
                    if first_error is None:
                        first_error = last_error
                remaining = deadline - time.monotonic()
                if remaining <= 0 or attempts == 26:
                    break
                time.sleep(min(0.01, remaining))
            raise DarwinObservationExhausted(f"Darwin {operation} unresolved after bounded observation: {last_error}")
        except BaseException as error:
            primary = error
            raise
        finally:
            if first_error is not None:
                def record_observation():
                    if len(self.observation_reconciliations) >= 1024:
                        raise OwnershipError("Darwin observation evidence exceeds its bound")
                    self.observation_reconciliations.append({"operation": operation, "identity": identity,
                        "lastIdentity": current, "attempts": attempts, "firstFailure": first_error,
                        "lastFailure": last_error, "outcome": outcome})
                # This action retains metadata, not a Mach-right close. Its
                # failure is terminal but cannot replace an in-flight primary.
                self._retire_resources([("observation-record", record_observation)],
                    "darwin-observation-record", original=primary)

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
        self._ensure_open()
        port = U32()
        original = None

        def release_port():
            if self.system.mach_port_deallocate(self.self_port, port) != 0:
                raise OwnershipError("Cannot release the owned Darwin task-name port")

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
        except BaseException as error:
            original = error
            raise
        finally:
            if port.value:
                self._retire_resources([("task-name-port", release_port)], "darwin-token", original=original)

    def description(self) -> dict[str, Any]:
        return {**super().description(), "observationReconciliations": self.observation_reconciliations,
                "drainReconciliations": self.drain_reconciliations}

    def _send(self, identity: dict[str, Any], handle: AuditToken, signum: int, *,
              deadline: float | None = None) -> None:
        # A real token is reacquired after exec-version changes; never os.kill(pid).
        _check_drain_deadline(deadline)
        token = self._acquire(identity)
        # Token acquisition retains its existing bounded observation/Mach-right
        # cleanup. A token returned late must never reach the actual signal API.
        _check_drain_deadline(deadline)
        result = self.proc.proc_signal_with_audittoken(ctypes.byref(token), signum)
        if result not in (0, errno.ESRCH):
            # A real native denial stays fatal even if the call consumed this
            # phase. Turning it into normal phase expiry could hide the failure
            # behind a later KILL/quiet census and incorrectly accept retirement.
            raise OwnershipError(f"Darwin identity-scoped signal failed: errno {result}")
        _check_drain_deadline(deadline)
        if result == errno.ESRCH:
            raise ProcessLookupError(identity["pid"])

    def _reconcile_drain_signals(self, *, deadline: float | None = None) -> None:
        for key, record in list(self.active_drain["pending"].items()):
            # A filtered/empty census, changed credentials, or a stale token's
            # ESRCH is not retirement of this already-owned lifetime.
            _check_drain_deadline(deadline)
            current = self._identity(record["identity"]["pid"], required=True)
            _check_drain_deadline(deadline)
            record["lastIdentity"] = current
            if current is None or not current["live"] or self._key(current) != key:
                record["outcome"] = "absent" if current is None else "nonrunning" if not current["live"] else "replaced"
                self.active_drain["pending"].pop(key)

    def signal_all(self, signum: int, *, deadline: float | None = None) -> None:
        self._ensure_open()
        if self.active_drain is None:
            if deadline is None:
                return super().signal_all(signum)
            return super().signal_all(signum, deadline=deadline)
        active = self.active_drain
        if deadline is not None:
            if deadline != active["deadline"]:
                raise OwnershipError("Native signal end differs from its active drain phase")
            _check_drain_deadline(deadline)
        elif time.monotonic() >= active["deadline"]:
            return
        live = self.discover()
        _check_drain_deadline(deadline)
        if deadline is None:
            self._reconcile_drain_signals()
        else:
            self._reconcile_drain_signals(deadline=deadline)
        _check_drain_deadline(deadline)
        for identity in live:
            # Do not start another signal observation after this phase. An
            # in-flight census/_observe/kernel call retains its existing bounds.
            if deadline is not None:
                _check_drain_deadline(deadline)
            elif time.monotonic() >= active["deadline"]:
                break
            key = self._key(identity)
            first_observation = len(self.observation_reconciliations)
            try:
                if deadline is None:
                    self._send(identity, self.handles[key], signum)
                else:
                    self._send(identity, self.handles[key], signum, deadline=deadline)
                _check_drain_deadline(deadline)
            except ProcessLookupError as error:
                if retirement_details(error):
                    raise
                _check_drain_deadline(deadline)
                if deadline is None:
                    self._reconcile_drain_signals()
                else:
                    self._reconcile_drain_signals(deadline=deadline)
            except DarwinObservationExhausted as error:
                if retirement_details(error):
                    raise
                record = active["pending"].get(key)
                if record is None:
                    if sum(len(row["signalReconciliations"]) for row in self.drain_reconciliations) >= 1024:
                        raise OwnershipError("Darwin drain signal evidence exceeds its bound") from error
                    record = {"identity": dict(identity), "firstFailure": str(error), "failures": 0,
                              "firstSignal": signum, "firstObservation": first_observation, "outcome": "unresolved"}
                    active["pending"][key] = record
                    active["record"]["signalReconciliations"].append(record)
                record.update(lastIdentity=dict(identity), lastFailure=str(error), lastSignal=signum,
                              lastObservation=len(self.observation_reconciliations) - 1,
                              failures=record["failures"] + 1)
                _check_drain_deadline(deadline)
            else:
                record = active["pending"].pop(key, None)
                if record is not None:
                    # A successful fresh-token signal resolves access, not exit.
                    # Ordinary known-lifetime/quiet checks still govern retirement.
                    record.update(outcome="signal-succeeded", lastSignal=signum, lastIdentity=dict(identity),
                                  lastObservation=len(self.observation_reconciliations) - 1)
            _check_drain_deadline(deadline)

    def drain(self, grace: float = 5.0, kill_wait: float = 5.0, *,
              deadline: float | None = None) -> list[dict[str, Any]]:
        self._ensure_open()
        if self.active_drain is not None:
            raise OwnershipError("Darwin drain is already active")
        if len(self.drain_reconciliations) >= 1024:
            raise OwnershipError("Darwin drain evidence exceeds its bound")
        if deadline is None:
            started = time.monotonic()
            term_end, kill_end = started + grace, started + grace + kill_wait
        else:
            started, term_end, kill_end = _drain_phase_ends(grace, kill_wait, deadline)
        record = {"startedMonotonic": started, "graceSeconds": grace, "killWaitSeconds": kill_wait,
                  "phases": [], "signalReconciliations": [], "outcome": "unresolved"}
        if deadline is not None:
            record["absoluteDeadlineMonotonic"] = deadline
        self.drain_reconciliations.append(record)
        self.active_drain = {"record": record, "pending": {}, "deadline": started}
        live, primary = [], None
        try:
            # Both deadlines are fixed before any failed signal/census. No new
            # retry window is added for an exhausted 0.25-second observation.
            for signum, phase_end in ((SIG_TERM, term_end), (SIG_KILL, kill_end)):
                self.active_drain["deadline"] = phase_end
                record["phases"].append({"signal": signum, "deadlineMonotonic": phase_end})
                quiet = 0
                try:
                    while time.monotonic() < phase_end:
                        _check_drain_deadline(phase_end if deadline is not None else None)
                        observed = self.discover()
                        _check_drain_deadline(phase_end if deadline is not None else None)
                        live = observed
                        if deadline is None:
                            self._reconcile_drain_signals()
                        else:
                            self._reconcile_drain_signals(deadline=phase_end)
                        _check_drain_deadline(phase_end if deadline is not None else None)
                        unknown = deadline is not None and (self.discovery_errors or self.pending_discoveries)
                        if not live and not self.active_drain["pending"] and not unknown:
                            quiet += 1
                            if quiet >= 3:
                                _check_drain_deadline(phase_end if deadline is not None else None)
                                record["outcome"] = "retired"
                                return []
                        else:
                            quiet = 0
                            if deadline is None:
                                self.signal_all(signum)
                            else:
                                self.signal_all(signum, deadline=phase_end)
                        remaining = phase_end - time.monotonic()
                        if remaining > 0:
                            time.sleep(min(0.1, remaining))
                except DrainDeadlineExceeded as error:
                    if retirement_details(error):
                        raise
                    if deadline is None:
                        raise
                    record["phases"][-1]["outcome"] = "deadline-exhausted"
            if self.active_drain["pending"]:
                raise DarwinObservationExhausted("Darwin known-token drain remains unresolved within its phase bounds")
            if live:
                # No late discovery/token acquisition. This is the conservative
                # last observation, not a claim that a later exit was inspected.
                record["outcome"] = "last-observed-live"
                return live
            raise OwnershipError("Darwin drain did not establish three quiet censuses within its phase bounds")
        except BaseException as error:
            primary = error
            unknown = bool(retirement_details(error))
            record["error"] = format_ownership_error(error) if unknown else str(error)
            record["outcome"] = "unresolved" if isinstance(error, DarwinObservationExhausted) and not unknown else "failed"
            raise
        finally:
            if deadline is None:
                record["finishedMonotonic"] = time.monotonic()
                self.active_drain = None
            else:
                try:
                    finished = time.monotonic()
                    record["finishedMonotonic"] = finished
                    if not _finite_number(finished):
                        raise OwnershipError("Invalid native drain final monotonic observation")
                    if record["outcome"] == "retired" and finished >= self.active_drain["deadline"]:
                        raise DrainDeadlineExceeded("Native drain retirement returned after its absolute phase end")
                except BaseException as error:
                    if primary is None:
                        record.update(error=str(error), outcome="failed")
                        raise
                    record["finalizationError"] = str(error)
                finally:
                    # Earlier terminal/failed records are never rewritten by a
                    # later drain; even a late-return failure retires active state.
                    self.active_drain = None


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
    quote there. Parentheses are literal only inside the quotes emitted for every
    argv element. Keep them forbidden in the separately framed cmd executable;
    reject embedded quotes and all other expansion/control metacharacters in both.
    """
    forbidden = re.compile(r'[\x00-\x1f"%!&|<>^]')
    if not argv or any(char in cmd for char in "()") or any(forbidden.search(arg) for arg in [cmd, *argv]):
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
        self._bind("GetHandleInformation", [PTR, ctypes.POINTER(U32)], I32)
        self._bind("DuplicateHandle", [PTR, PTR, PTR, ctypes.POINTER(PTR), U32, I32, U32], I32)
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


class _WindowsPipeReader:
    """One CRT descriptor owner with a strictly nonowning, unbuffered I/O view."""

    def __init__(self, handle: int, name: str):
        self.native_handle, self.name = handle, name
        self._fd: int | None = None
        self._view: Any = None
        self._adoption_started = self._closed = self._fd_close_attempted = False
        self._close_error: BaseException | None = None

    @property
    def descriptor_adopted(self) -> bool:
        # Remains true even after an ambiguous descriptor-close failure. The
        # original Win32 value must never then reach CloseHandle as a fallback.
        return self._fd is not None or self._fd_close_attempted

    def adopt(self) -> None:
        import msvcrt
        if self._adoption_started or self._closed:
            raise OwnershipError("Owned pipe descriptor adoption cannot be repeated")
        self._adoption_started = True
        self._fd = msvcrt.open_osfhandle(self.native_handle, os.O_RDONLY | os.O_BINARY)
        # The pending owner is already registered before either adoption or this
        # fallible constructor. FileIO can never close/recycle the owned fd.
        self._view = io.FileIO(self._fd, "rb", closefd=False)

    @property
    def closed(self) -> bool:
        return self._closed

    def fileno(self) -> int:
        if self._closed or self._fd is None:
            raise ValueError("I/O operation on a closed owned pipe")
        return self._fd

    def read(self, size: int = -1) -> bytes:
        if self._closed or self._view is None:
            raise ValueError("I/O operation on a closed owned pipe")
        return self._view.read(size)

    def close(self) -> None:
        if self._closed:
            if self._close_error is not None:
                raise self._close_error
            return
        self._closed = True
        view, self._view = self._view, None
        actions = []
        if view is not None:
            actions.append((self.name + "-nonowning-view", view.close))
        if self._fd is not None:
            self._fd_close_attempted = True
            fd, self._fd = self._fd, None  # No retry, including cancellation or uncertain os.close.
            actions.append((self.name + "-crt-descriptor", lambda: os.close(fd)))
        _, failures = _retire_actions(actions, "pipe-close")
        try:
            _finish_retirement(failures)
        except BaseException as error:
            self._close_error = error
            raise


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
            # A failed native close has UNKNOWN retirement. Never retry a raw
            # handle value which the OS might already have recycled.
            handle, self.handle = self.handle, None
            self.api.close(handle)


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
        except BaseException as error:
            job, self.job = self.job, None
            self._retire([("job", lambda: self.api.close(job))], original=error, phase="scope-construction")
            raise

    def _retire(self, actions: list[Any], *, original: BaseException | None = None,
                launch: dict[str, Any] | None = None, phase: str = "scope-close") -> None:
        """Attempt every acquired resource once; cleanup cannot hide a primary failure."""
        outcomes, failures = _retire_actions(actions, phase)
        for row, _ in failures:
            self.discovery_errors.add(_retirement_text(row))
        if launch is not None:
            launch.setdefault("resourceCleanup", []).extend(outcomes)
        _finish_retirement(failures, original)

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

    def spawn(self, argv: list[str], cwd: str, env: dict[str, str], *,
              stdout: Any = None, stderr: Any = None) -> WindowsProcess:
        """Spawn with the existing pipe contract or two pinned private NativeFiles.

        Supplied sinks remain caller-owned. Only fresh duplicates of their
        borrowed, noninheritable Win32 handles enter the explicit HANDLE_LIST;
        a Win32 handle is never treated as a CRT descriptor. The caller must keep
        each original alive without a concurrent close through duplication and
        full child/domain retirement, monitor live size, then verify and sync.
        Job assignment, suspended creation and no-breakaway remain unchanged.
        """
        if (stdout is None) != (stderr is None):
            raise OwnershipError("Both owned output sinks are required")
        launch = {"api": "CreateProcessW", "requestedArgv": list(argv), "cwd": cwd,
                  "created": False, "resumed": False}
        if stdout is not None:
            launch["outputMode"] = "caller-owned-native-files"
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
        streams: list[_WindowsPipeReader] = []
        process = ProcessInformation()
        created = False
        original = None
        try:
            security = SecurityAttributes(ctypes.sizeof(SecurityAttributes), None, 1)
            reads, writes = [], []
            if stdout is None:
                for _ in range(2):
                    read, write = PTR(), PTR()
                    self.api.check(self.api.CreatePipe(ctypes.byref(read), ctypes.byref(write),
                                                        ctypes.byref(security), 0), "CreatePipe")
                    handles.extend([read.value, write.value])
                    self.api.check(self.api.SetHandleInformation(read, 1, 0), "SetHandleInformation")
                    reads.append(read.value)
                    writes.append(write.value)
            else:
                borrowed = set()
                for sink in (stdout, stderr):
                    handle = sink.native_handle
                    if type(handle) is not int or handle in (0, ctypes.c_void_p(-1).value) or \
                            handle in borrowed or not sink.writable():
                        raise OwnershipError("Distinct open native output handles are required")
                    borrowed.add(handle)
                    flags, duplicate = U32(), PTR()
                    self.api.check(self.api.GetHandleInformation(handle, ctypes.byref(flags)), "GetHandleInformation")
                    if flags.value & 1:
                        raise OwnershipError("Original private output handle must not be inheritable")
                    # DUPLICATE_SAME_ACCESS into this process; inherit ONLY the
                    # explicitly listed duplicate, never the original or all
                    # ambient runner handles.
                    self.api.check(self.api.DuplicateHandle(PTR(-1), handle, PTR(-1), ctypes.byref(duplicate),
                                                            0, 1, 2), "DuplicateHandle owned output")
                    handles.append(duplicate.value)
                    writes.append(duplicate.value)
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
            for index, handle in enumerate(reads):
                reader = _WindowsPipeReader(handle, "stdout" if index == 0 else "stderr")
                streams.append(reader)  # Register before CRT adoption or fallible FileIO wrapping.
                reader.adopt()
            child = WindowsProcess(self.api, process.process, process.pid,
                                   streams[0] if streams else None, streams[1] if streams else None)
            self.leaders.append(child)
            process.process = None  # Child object now owns the process handle.
            if self.api.ResumeThread(process.thread) == 0xFFFFFFFF:
                raise OwnershipError("ResumeThread failed for assigned Windows child")
            launch["resumed"] = True
        except BaseException as error:
            original = error
            raise
        finally:
            actions = []
            if initialized:
                actions.append(("startup-attributes", lambda: self.api.DeleteProcThreadAttributeList(attributes)))
            # Keep raw acquisition records until this phase. Successful CRT
            # adoption, including a failed FileIO construction, excludes that
            # raw handle from CloseHandle without a second ownership handoff.
            adopted = {stream.native_handle for stream in streams if stream.descriptor_adopted}
            actions.extend((f"launch-handle-{index}", lambda value=handle: self.api.close(value))
                           for index, handle in enumerate(handles) if handle not in adopted)
            if process.thread:
                actions.append(("primary-thread", lambda: self.api.close(process.thread)))
            if process.process:
                actions.append(("untransferred-process", lambda: self.api.close(process.process)))
            try:
                self._retire(actions, original=original, launch=launch, phase="launch-temporary")
            except BaseException as error:
                original = error
                raise
            finally:
                if original is not None:
                    pending = []
                    if created:
                        pending.append(("failed-launch-job-termination", lambda: self.api.check(
                            self.api.TerminateJobObject(self.job, 125), "TerminateJobObject failed launch")))
                    pending.extend((f"launch-stream-{index}", stream.close) for index, stream in enumerate(streams))
                    # Includes a late temporary-finalizer failure after resume.
                    # No caller/tee received these readers; the process handle
                    # remains registered for the outer owner's bounded drain.
                    self._retire(pending, original=original, launch=launch, phase="failed-return")
        streams.clear()  # Transfer only after every fallible launch finalizer succeeded.
        return child

    def signal_all(self, signum: int, *, deadline: float | None = None) -> None:
        _check_drain_deadline(deadline)
        if signum == SIG_KILL:
            self.api.check(self.api.TerminateJobObject(self.job, 125), "TerminateJobObject")
            _check_drain_deadline(deadline)
            return
        # A best-effort scoped CTRL_BREAK may be unavailable for detached leaders.
        # Hard cleanup below always uses the proven job, never a process-group0 signal.
        for child in self.leaders:
            _check_drain_deadline(deadline)
            if child.pid > 0 and child.poll() is None:
                _check_drain_deadline(deadline)
                self.api.GenerateConsoleCtrlEvent(1, child.pid)
            _check_drain_deadline(deadline)

    def drain(self, grace: float = 5.0, kill_wait: float = 5.0, *,
              deadline: float | None = None) -> list[dict[str, Any]]:
        if deadline is not None:
            return _bounded_drain(self, grace, kill_wait, deadline, quiet_required=1, repeat_signals=False)
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
        job, self.job = self.job, None
        actions = [(f"leader-{index}", child.close) for index, child in enumerate(self.leaders)]
        if job:
            actions.append(("job", lambda: self.api.close(job)))
        self._retire(actions)


def make_scope(job: str, invocation: str, state: str, home: str) -> PosixScope | WindowsScope:
    kind = {"Linux": LinuxScope, "Darwin": DarwinScope, "Windows": WindowsScope}.get(platform.system())
    if kind is None:
        raise OwnershipError("Unsupported native process-ownership backend")
    return kind(job, invocation, state, home)
