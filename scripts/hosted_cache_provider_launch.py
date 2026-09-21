"""Dormant fixed native launch sites, NOT an admitted provider bridge.

There is no admitted CLI/workflow caller, pre-Node/environment/tool authority,
return protocol or custody/seal/upload in this module. Standalone start() leaves
original owners live on both return and failure. The separate original outer
supervisor must finish them under the SAME180/final45; never infer retirement
from child exit, an in-process quarantine, or a success-shaped supplied record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess
import sys
import threading
import time

import audit_processes as processes
import hosted_cache_provider_environment as environment
import hosted_cache_provider_lifecycle as lifecycle
import hosted_cache_provider_worker as worker_source
import hosted_dependency_cache as cache
import hosted_job_clock as clocks
import hosted_test_query as files


SCRIPTS = Path(__file__).absolute().parent
MARKERS = (processes.JOB_ENV, processes.CHAIN_ENV, processes.DOMAINS_ENV, processes.STATE_ENV, "GRADLE_USER_HOME")
QUARANTINE = []
_WORKERS = []
_FRAME_KEYS = {"schema", "role", "frequency", "issuedNs", "hardEndNs", "workerCutoffNs", "phase", "job",
               "outerId", "innerId", "directory", "directoryIdentity", "home", "homeIdentity", "captureIdentity",
               "node", "toolPath", "systemRoot", "plan", "prefix"}


class ProviderLaunchError(RuntimeError):
    """Fixed public-safe reason. Environments, original errors and files are private."""


@dataclass(frozen=True, repr=False)
class WorkerLaunch:
    """Original child and immutable actual request, not a provider result."""
    child: object = field(repr=False)
    request: bytes = field(repr=False)


def require(value, reason):
    if not value:
        raise ProviderLaunchError(reason)


def _json(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    require(len(raw) <= 16 * 1024, "PROVIDER_LAUNCH_WIRE_BOUND")
    return raw


def _domain_values(domains):
    return tuple(tuple(domain[key] for key in ("id", "job", "state", "home")) for domain in domains)


def _markers(values):
    require(type(values) is dict and set(values) <= set(MARKERS) and
            all(type(value) is str and "\0" not in value for value in values.values()), "PROVIDER_MARKER_FIELDS")
    if set(values) - {"GRADLE_USER_HOME"}:
        require(set(values) == set(MARKERS), "PROVIDER_PARTIAL_MARKERS")
        domains = processes.ownership_domains(values[processes.CHAIN_ENV], values[processes.DOMAINS_ENV])
        require(domains and values[processes.JOB_ENV] == domains[-1]["job"] and
                values[processes.STATE_ENV] == domains[-1]["state"] and
                values["GRADLE_USER_HOME"] == domains[-1]["home"], "PROVIDER_MARKER_CONTEXT")
        return _domain_values(domains), values["GRADLE_USER_HOME"]
    return (), values.get("GRADLE_USER_HOME")


def _ambient_markers():
    # Read the real original fields BEFORE sanitizing. Never copy the ambient
    # credential/loader environment and try to subtract a blacklist afterward.
    value = {name: os.environ[name] for name in MARKERS if name in os.environ}
    return value, _markers(value)


def _environment_values(value):
    require(type(value) is dict and all(type(name) is str and type(data) is str for name, data in value.items()),
            "PROVIDER_CHILD_ENVIRONMENT")
    # Only the JSON spelling may legitimately change; full ordered domain values
    # and every other field (including the closed credential roster) stay exact.
    return (tuple(sorted((name, data) for name, data in value.items() if name != processes.DOMAINS_ENV)),
            _markers({name: value[name] for name in MARKERS}))


def _service():
    return environment.runtime_service_fragment({name: os.environ[name]
        for name in environment.SERVICE_FIELDS if name in os.environ})


def _path(value, role):
    kind = PureWindowsPath if role == "windows-x64" else Path
    require(type(value) is str and 0 < len(value) <= 4096 and
            all(ord(char) >= 32 and ord(char) != 127 for char in value), "PROVIDER_LAUNCH_PATH")
    path = kind(value)
    require(path.is_absolute() and str(path) == value and ".." not in path.parts and
            (role != "windows-x64" or re.fullmatch(r"[A-Za-z]:", path.drive) is not None), "PROVIDER_LAUNCH_PATH")
    return path


def _identity(value, role):
    require(type(value) is list and len(value) == 2 and type(value[0]) is int and value[0] >= 0 and
            ((type(value[1]) is str and re.fullmatch(r"[0-9a-f]{32}", value[1])) if role == "windows-x64" else
             (type(value[1]) is int and value[1] > 0)), "PROVIDER_DIRECTORY_IDENTITY")
    return tuple(value)


def _ns(value):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value), "PROVIDER_RAW_DECIMAL")
    return clocks.integer(int(value))


def _frame(value):
    require(type(value) is dict and set(value) == _FRAME_KEYS and type(value["schema"]) is int and
            value["schema"] == 1, "PROVIDER_LAUNCH_FRAME")
    role = value["role"]
    require(type(role) is str and role in clocks.DOMAINS, "PROVIDER_LAUNCH_ROLE")
    clock = clocks.validate_identity(clocks.ClockIdentity(role, clocks.DOMAINS[role], value["frequency"]))
    issued, end, cut = map(_ns, (value["issuedNs"], value["hardEndNs"], value["workerCutoffNs"]))
    require(issued + 45 * clocks.NS < cut < end <= issued + 180 * clocks.NS, "PROVIDER_LAUNCH_WINDOW")
    require(value["phase"] in ("save", "lookup") and all(type(value[name]) is str and
            re.fullmatch(r"[0-9a-f]{32}", value[name]) for name in ("job", "outerId", "innerId")) and
            value["innerId"] != value["outerId"], "PROVIDER_LAUNCH_IDS")
    directory, home, node = (_path(value[name], role) for name in ("directory", "home", "node"))
    require(node.name == ("node.exe" if role == "windows-x64" else "node") and home != directory,
            "PROVIDER_FIXED_NODE_AND_HOME")
    for name in ("directoryIdentity", "homeIdentity", "captureIdentity"):
        _identity(value[name], role)
    require(len({tuple(value[name]) for name in ("directoryIdentity", "homeIdentity", "captureIdentity")}) == 3,
            "PROVIDER_DISTINCT_DIRECTORIES")
    require(type(value["toolPath"]) is str and bool(value["toolPath"]), "PROVIDER_TOOL_PATH")
    for part in value["toolPath"].split(";" if role == "windows-x64" else ":"):
        _path(part, role)  # No empty/current-directory or relative PATH member.
    require(value["systemRoot"] is None or role == "windows-x64", "PROVIDER_SYSTEM_ROOT")
    if role == "windows-x64":
        _path(value["systemRoot"], role)
    contract = cache.bootstrap_provider_contract(value["plan"], value["phase"])
    require(value["plan"]["role"] == role and str(home) != value["plan"]["restoreHome"], "PROVIDER_CONTROL_HOME")
    prefix = value["prefix"]
    require(type(prefix) is list and prefix and all(type(row) is list and len(row) == 4 for row in prefix),
            "PROVIDER_LAUNCH_PREFIX")
    domains = [dict(zip(("id", "job", "state", "home"), row)) for row in prefix]
    require(_domain_values(processes.ownership_domains(":".join(row[0] for row in prefix), _json(domains))) ==
            tuple(map(tuple, prefix)) and prefix[-1] == [value["outerId"], value["job"], str(directory), str(home)] and
            value["innerId"] not in [row[0] for row in prefix], "PROVIDER_LAUNCH_PREFIX")
    _json(value)
    return clock, issued, end, cut, contract


def _base(value):
    role, home = value["role"], value["home"]
    result = {"PATH": value["toolPath"], "GITHUB_WORKSPACE": str(SCRIPTS.parent), "LANG": "C", "LC_ALL": "C"}
    if role == "windows-x64":
        result.update(SYSTEMROOT=value["systemRoot"], USERPROFILE=home, TEMP=home, TMP=home, PATHEXT=".EXE")
    else:
        result.update(HOME=home, TMPDIR=home)
    return result


def _append(base, inherited, original, job, invocation, state, home):
    require(_markers(inherited) == original, "PROVIDER_ORIGINAL_PREFIX_CHANGED")
    result = processes.ownership_environment({**base, **inherited}, job, invocation, state, home)
    expected = (original[0] + ((invocation, job, state, home),), home)
    require(set(result) == set(base) | set(MARKERS) and
            _markers({name: result[name] for name in MARKERS}) == expected, "PROVIDER_APPEND_ONLY_HANDOFF")
    return result, expected


def _scope_binding(scope, role, job, invocation, state, home):
    expected = processes.WindowsScope if role == "windows-x64" else (
        processes.LinuxScope if role == "linux-x64" else processes.DarwinScope)
    require(type(scope) is expected and scope.invocation == invocation and
            (scope.job_id if role == "windows-x64" else scope.job) == job, "PROVIDER_ORIGINAL_SCOPE")
    if role != "windows-x64":
        require(scope.state == state and scope.home == home, "PROVIDER_ORIGINAL_SCOPE")


def _leader(scope, child, role):
    expected = processes.WindowsProcess if role == "windows-x64" else processes.PosixProcess
    require(type(child) is expected and child.stdout is None and child.stderr is None and
            type(scope.leaders) is list and len(scope.leaders) == 1 and scope.leaders[0] is child and
            type(scope.launches) is list and len(scope.launches) == 1, "PROVIDER_ORIGINAL_SPAWN_RETURN")


def _open_directory(path, role):
    return files.windows_files.open_private_directory(path) if role == "windows-x64" else files._PosixDirectory(path)


def _open_bundle(directory, role, end, maximum):
    return (directory.open_file("provider.cjs", max_bytes=maximum, deadline=end) if role == "windows-x64" else
            files._posix_stream(directory.path / "provider.cjs", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, "rb"))


def _bundle_bytes(reader, directory, role, contract):
    limit = contract["bundle"]["bytes"]
    before = reader.verify() if role == "windows-x64" else files._file_info(directory.path / "provider.cjs", reader, limit)
    raw = reader.read(limit + 1)
    after = reader.verify() if role == "windows-x64" else files._file_info(directory.path / "provider.cjs", reader, limit)
    require(before == after and type(raw) is bytes and len(raw) == before.size == limit and
            hashlib.sha256(raw).hexdigest() == contract["bundle"]["sha256"], "PROVIDER_BUNDLE_BYTES")
    directory.verify()
    return before


class _Window:
    """Only local fences against supplied original RAW bounds; NOT admission."""
    def __init__(self, first, issued, end, cutoff):
        clocks.validate_reading(first)
        require(issued <= first.nanoseconds < cutoff <= end, "PROVIDER_ORIGINAL_RAW_EXPIRED")
        self.clock, self.highest, self.end, self.cutoff = first.clock, first.nanoseconds, end, cutoff
        self.local_highest = self.local()
        now = self.raw()
        require(now < cutoff, "PROVIDER_ORIGINAL_RAW_EXPIRED")
        self.local_end = math.nextafter(self.local_highest + math.nextafter((cutoff - now) / clocks.NS, 0.0), -math.inf)
        self._binding = (self.clock, end, cutoff, self.local_end)

    def local(self):
        value = time.monotonic()
        require(type(value) in (int, float) and math.isfinite(value) and value >= getattr(self, "local_highest", 0),
                "PROVIDER_LAUNCH_LOCAL_CLOCK")
        self.local_highest = value
        return value

    def raw(self):
        self.highest = clocks.checked_now(self.clock, minimum_ns=self.highest)
        return self.highest

    def check(self, *, work=False):
        binding = self._binding
        require((self.clock, self.end, self.cutoff, self.local_end) == binding, "PROVIDER_LAUNCH_WINDOW_CHANGED")
        now = self.raw()
        local = self.local()
        require(self._binding is binding and (self.clock, self.end, self.cutoff, self.local_end) == binding,
                "PROVIDER_LAUNCH_WINDOW_CHANGED")
        require(now < min(self.cutoff, self.end - (45 * clocks.NS if work else 0)) and local < self.local_end,
                "PROVIDER_LAUNCH_EXPIRED")
        return now


class SupervisorLaunch:
    """Fixed provisional original outer owner. NO automatic cleanup or result.

    Transfer both actual native directory objects before start(). On any failure
    this object and all returned owners are retained in QUARANTINE. That is not
    retirement; only the separate bounded original outer supervisor may finalize it.
    """
    def __init__(self):
        self.directory = self.home = self.capture_directory = self.bundle = None
        self.stdout = self.stderr = self.scope = self.child = None
        self.window = self.worker_environment = self.worker_argv = None
        self.frame = self.source_originals = None
        self.attempted, self.original_error = set(), None
        self._thread, self._started = threading.get_ident(), False
        self.spawn_returned = False
        self._launch_return = None
        self._unreturned_acquisition = None
        self._owners = {name: None for name in ("directory", "home", "capture_directory", "bundle", "stdout", "stderr", "scope", "child")}

    def take_directories(self, directory, home):
        require(not self._started and self.directory is None and self.home is None and directory is not home,
                "PROVIDER_ROOT_TRANSFER")
        require(type(directory) is type(home) and type(directory) in (files._PosixDirectory, files.windows_files.PrivateDirectory),
                "PROVIDER_ROOT_TYPE")
        self._owners["directory"], self._owners["home"] = directory, home
        self.directory, self.home = directory, home  # Transfer before any verification.

    def _failed(self, error):
        if self.original_error is None:
            self.original_error = error
        if not any(item is self for item in QUARANTINE):
            QUARANTINE.append(self)

    def _healthy(self):
        if self.original_error is not None:
            raise self.original_error
        require(all(getattr(self, name) is owner for name, owner in self._owners.items()), "PROVIDER_ORIGINAL_OWNER_CHANGED")

    def _acquire(self, name, factory):
        self._healthy()
        self.window.check(work=True)
        require(name not in self.attempted, "PROVIDER_LAUNCH_DUPLICATE_OWNER")
        attempts = self.attempted
        attempts.add(name)
        expected = frozenset(attempts)
        try:
            owner = factory()
        except BaseException:
            # Retain the actual local episode on its exceptional return. The
            # callback-mutable diagnostic set cannot erase this obligation.
            self._unreturned_acquisition = name
            raise
        self._owners[name] = owner  # First action on return: fixed-roster custody.
        setattr(self, name, owner)
        if owner is None:
            self._unreturned_acquisition = name
            require(False, "PROVIDER_LAUNCH_OWNER_NOT_RETURNED")
        require(self.attempted is attempts and attempts == expected, "PROVIDER_LAUNCH_ACQUISITIONS_CHANGED")
        self.window.check(work=True)
        require(self.attempted is attempts and attempts == expected, "PROVIDER_LAUNCH_ACQUISITIONS_CHANGED")
        self._healthy()
        return getattr(self, name)

    def start(self, first, *, issued_ns, hard_end_ns, worker_cutoff_ns, phase, job, invocation, inner_invocation,
              plan, node, tool_path, cancelled):
        try:
            require(not self._started and threading.get_ident() == self._thread, "PROVIDER_LAUNCH_ONE_USE")
            self._started = True
            require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
                    "PROVIDER_SUPERVISOR_PYTHON_ISOLATION")
            inherited, original = _ambient_markers()
            require(self.directory is not None and self.home is not None and callable(cancelled), "PROVIDER_LAUNCH_ROOTS")
            role = first.clock.role
            for value in (issued_ns, hard_end_ns, worker_cutoff_ns):
                clocks.integer(value)
            require(issued_ns + 45 * clocks.NS < worker_cutoff_ns < hard_end_ns <= issued_ns + 180 * clocks.NS,
                    "PROVIDER_LAUNCH_WINDOW")
            self.window = _Window(first, issued_ns, hard_end_ns, hard_end_ns)
            self.window.check(work=True)
            self.directory.verify()
            self.home.verify()
            capture = self._acquire("capture_directory", lambda: self.directory.create_directory("capture", deadline=self.window.local_end))
            self._acquire("scope", lambda: processes.make_scope(job, invocation, str(self.directory.path), str(self.home.path)))
            scope = self.scope
            _scope_binding(scope, role, job, invocation, str(self.directory.path), str(self.home.path))
            env, prefix = _append({}, inherited, original, job, invocation, str(self.directory.path), str(self.home.path))
            frame = {"schema": 1, "role": role, "frequency": first.clock.ticks_per_second,
                "issuedNs": str(issued_ns), "hardEndNs": str(hard_end_ns), "workerCutoffNs": str(worker_cutoff_ns),
                "phase": phase, "job": job, "outerId": invocation, "innerId": inner_invocation,
                "directory": str(self.directory.path), "directoryIdentity": list(self.directory.identity),
                "home": str(self.home.path), "homeIdentity": list(self.home.identity), "captureIdentity": list(capture.identity),
                "node": node, "toolPath": tool_path, "systemRoot": os.environ.get("SYSTEMROOT") if role == "windows-x64" else None,
                "plan": plan, "prefix": list(map(list, prefix[0]))}
            frame = worker_source.record(_json(frame))  # Detach caller-owned dictionaries before callbacks.
            _, _, _, _, contract = _frame(frame)
            self.frame = frame
            self._acquire("bundle", lambda: _open_bundle(self.directory, role, self.window.local_end, contract["bundle"]["bytes"]))
            _bundle_bytes(self.bundle, self.directory, role, contract)
            for name in ("stdout", "stderr"):
                # The same narrow native log capability is used in TWO distinct
                # directories: worker logs here, provider logs under capture/.
                self._acquire(name, lambda name=name: self.directory.create_file("provider-" + name + ".log",
                    max_bytes=lifecycle.LOG_BYTES, deadline=self.window.local_end))
            sources = {name: worker_source.read_source(SCRIPTS, name) for name in worker_source.names(role)}
            self.source_originals = sources
            bindings = {name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()}
            executable = str(_path(sys.executable, role))
            argv = [executable, "-I", "-B", "-S", str(SCRIPTS / "hosted_cache_provider_worker.py"), _json(bindings), _json(frame)]
            require(role != "windows-x64" or len(subprocess.list2cmdline(argv).encode("utf-16-le")) < 60000,
                    "PROVIDER_WORKER_ARGV_BOUND")
            child_env = {**_base(frame), **env}
            services = _service()
            child_env.update(services)
            self.worker_environment, self.worker_argv = child_env, argv
            original_environment, original_argv = _environment_values(child_env), tuple(argv)
            request = original_argv[-1].encode("ascii")
            cancelled()
            self._healthy()
            self.window.check(work=True)
            for name, raw in sources.items():
                require(worker_source.read_source(SCRIPTS, name) == raw, "PROVIDER_WORKER_SOURCE_CHANGED")
            self.window.check(work=True)
            require(_ambient_markers()[1] == original and _service() == services and
                    _markers({name: child_env[name] for name in MARKERS}) == prefix and
                    _environment_values(child_env) == original_environment and tuple(argv) == original_argv and
                    self.worker_environment is child_env and self.worker_argv is argv and
                    self.source_originals is sources, "PROVIDER_WORKER_HANDOFF_CHANGED")
            _scope_binding(scope, role, job, invocation, str(self.directory.path), str(self.home.path))
            self._healthy()
            self.attempted.add("child")
            # Pass the immutable vector itself. The later diagnostic argv list
            # cannot replace the bytes handed to the actual native spawn.
            child = scope.spawn(original_argv, str(SCRIPTS.parent), child_env, stdout=self.stdout, stderr=self.stderr)
            self._owners["child"] = child
            self.child = child
            self.spawn_returned = True
            returned = WorkerLaunch(child, request)
            self._launch_return = returned
            self.window.check(work=True)
            self._healthy()
            _leader(scope, child, role)
            require(self._launch_return is returned and returned.child is child and returned.request is request,
                    "PROVIDER_ORIGINAL_LAUNCH_RETURN_CHANGED")
            return returned  # Never provider/step/retirement success.
        except BaseException as error:
            self._failed(error)
            raise self.original_error


class _CaptureWorker:
    def __init__(self, frame):
        self.frame = frame
        self.directory = self.home = self.bundle = self.capture_directory = self.capture = self.child = None
        self.window = self.provider_environment = self.provider_argv = None
        self.capture_return = self.original_error = None
        self.closed = []
        self.attempted, self.started = set(), False
        self._owners = {name: None for name in ("directory", "home", "bundle", "capture_directory", "capture", "child")}

    def _check(self, *, work=True):
        if self.original_error is not None:
            raise self.original_error
        require(all(getattr(self, name) is owner for name, owner in self._owners.items()), "PROVIDER_WORKER_OWNER_CHANGED")
        self.window.check(work=work)
        if self.original_error is not None:
            raise self.original_error
        require(all(getattr(self, name) is owner for name, owner in self._owners.items()), "PROVIDER_WORKER_OWNER_CHANGED")

    def _acquire(self, name, factory):
        self._check()
        require(name not in self.attempted, "PROVIDER_WORKER_DUPLICATE_OWNER")
        self.attempted.add(name)
        owner = factory()
        self._owners[name] = owner
        setattr(self, name, owner)
        self._check()
        return owner

    def run(self):
        try:
            require(not self.started, "PROVIDER_WORKER_ONE_USE")
            self.started = True
            inherited, original = _ambient_markers()
            value = self.frame
            clock, issued, end, cut, contract = _frame(value)
            original_frame = _json(value)
            role = clock.role
            require(original == (tuple(map(tuple, value["prefix"])), value["home"]), "PROVIDER_WORKER_PREFIX_LOST")
            first = clocks.observe()
            require(first.clock == clock, "PROVIDER_WORKER_CLOCK_CHANGED")
            self.window = _Window(first, issued, end, cut)
            self._check()
            for name in ("directory", "home"):
                owner = self._acquire(name, lambda name=name: _open_directory(value[name], role))
                owner.verify()
                require(tuple(owner.identity) == _identity(value[name + "Identity"], role), "PROVIDER_WORKER_ROOT_CHANGED")
            self._acquire("bundle", lambda: _open_bundle(self.directory, role, self.window.local_end, contract["bundle"]["bytes"]))
            _bundle_bytes(self.bundle, self.directory, role, contract)
            self._acquire("capture", lambda: lifecycle.ProviderCapture(first, issued_ns=issued, hard_end_ns=end,
                local_end=self.window.local_end, phase=value["phase"], job=value["job"], invocation=value["innerId"],
                home=value["home"], cancelled=lambda: self._check(work=False)))
            with self.capture as capture:
                self._acquire("capture_directory", lambda: _open_directory(str(_path(value["directory"], role) / "capture"), role))
                capture.take_directory(self.capture_directory)
                self.capture_directory.verify()
                require(tuple(self.capture_directory.identity) == _identity(value["captureIdentity"], role),
                        "PROVIDER_WORKER_CAPTURE_CHANGED")
                capture.prepare()
                scope, stdout, stderr, command = capture.scope, capture.stdout, capture.stderr, str(capture.command_path)
                state = str(self.capture_directory.path)
                _scope_binding(scope, role, value["job"], value["innerId"], state, value["home"])
                child_env, prefix = _append(_base(value), inherited, original, value["job"], value["innerId"], state, value["home"])
                child_env.update(contract["inputs"], GITHUB_OUTPUT=command)
                services = _service()
                child_env.update(services)
                argv = [value["node"], str(_path(value["directory"], role) / "provider.cjs")]
                self.provider_environment, self.provider_argv = child_env, argv
                original_environment, original_argv = _environment_values(child_env), tuple(argv)
                self._check()
                require(_ambient_markers()[1] == original and _service() == services and
                        _markers({name: child_env[name] for name in MARKERS}) == prefix and
                        _environment_values(child_env) == original_environment and tuple(argv) == original_argv and
                        self.provider_environment is child_env and self.provider_argv is argv and
                        _json(value) == original_frame, "PROVIDER_INNER_HANDOFF_CHANGED")
                _scope_binding(scope, role, value["job"], value["innerId"], state, value["home"])
                self.attempted.add("child")
                child = scope.spawn(argv, str(SCRIPTS.parent), child_env, stdout=stdout, stderr=stderr)
                self._owners["child"] = child
                self.child = child  # Retained before wait/admission/clock callbacks.
                capture.wait(child)
            self.capture_return = capture.result
            self._check(work=False)
            # These are this worker's separate readers/roots, not outer owners.
            for name in ("bundle", "home", "directory"):
                self._check(work=False)
                getattr(self, name).close()
                self.closed.append(name)
                self._check(work=False)
            return self.capture_return
        except BaseException as error:
            if self.original_error is None:
                self.original_error = error
            # No retry or guessed cleanup after incomplete acquisition/UNKNOWN.
            # The original OUTER supervisor must observe retirement independently.
            if not any(item is self for item in QUARANTINE):
                QUARANTINE.append(self)
            raise self.original_error
