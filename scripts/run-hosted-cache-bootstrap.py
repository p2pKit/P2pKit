#!/usr/bin/env python3
"""Dormant, evidence-only bootstrap original acquisition; NOT a cache builder.

No workflow, productive budget, canonical init/producer, seed/export/save,
policy installer or uploader exists here. Separate read-only original adoption
never becomes execution authority. A future trusted workflow must bind the
actual original prepare-step outcome, not a provisional receipt/digest.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import audit_processes as processes
import hosted_cache_bootstrap_allocation as allocation
import hosted_cache_bootstrap_history as history
import hosted_cache_bootstrap_identity as bootstrap
import hosted_cache_bootstrap_origin as origin
import hosted_cache_bootstrap_service_time as service_time
import hosted_evidence as posix
import hosted_test_query as query
import hosted_windows_evidence as diagnostics
import hosted_windows_files as windows

I = bootstrap.ordinary
LIMIT = 2 * 1024 * 1024
ACK_LIMIT, STDERR_LIMIT = 16384, 65536
QUARANTINE = []
CONTEXT_SCOPE = "BOOTSTRAP_ORIGINAL_ACQUISITION_CONTEXT_V1"
PHASE_SCOPE = "BOOTSTRAP_ORIGINAL_NATIVE_PHASE_V1"
CHILD_SCOPE = "BOOTSTRAP_SERVICE_CHILD_PROVISIONAL_V1"
ACK_SCOPE = "BOOTSTRAP_SERVICE_POST_CLOSE_ACK_V1"
RESULT_SCOPE = "BOOTSTRAP_ORIGINALS_PENDING_CALLER_RETURN_V2"
HANDOFF_SCOPE = "BOOTSTRAP_PREPARE_POST_CLOSE_HANDOFF_V1"
HANDOFF_OUTPUT_SCOPE = "BOOTSTRAP_PREPARE_HANDOFF_PENDING_STEP_RETURN_V1"
ADOPTION_SCOPE = "BOOTSTRAP_READ_ONLY_ADOPTION_PENDING_RETURN_V2"
ENTRY_SCOPE = "BOOTSTRAP_READ_ONLY_EXECUTION_ENTRY_V1"
ENTRY_WINDOW_SCOPE = "BOOTSTRAP_ORIGINAL_PRELUDE_ENTRY_WINDOW_V1"
ENTRY_CLOSE_PENDING_SCOPE = "BOOTSTRAP_READ_ONLY_ENTRY_PENDING_CLOSE_V1"
ENTRY_CLOSE_SCOPE = "BOOTSTRAP_READ_ONLY_OWNER_CLOSED_NO_PRODUCTIVE_AUTHORITY_V1"
ENTRY_FIELDS = {"schema", "scope", "profile", "selection", "cacheCohort", "source", "github", "root", "session",
    "sessionIdentity", "preparation", "readmission", "prelude", "window", "retirement", "budgetAcceptance",
    "testAcceptance", "exportSaveAuthority"}
ENTRY_WINDOW_FIELDS = {"scope", "clock", "adopterFirstNs", "metadataLastNs", "readmissionReturnedNs",
    "startedNs", "workEndNs", "finalEndNs", "localCeiling"}
PREPARE_OUTCOME_ENV = "P2PKIT_BOOTSTRAP_PREPARE_OUTCOME"
PREPARE_HASH_ENV = "P2PKIT_BOOTSTRAP_PREPARE_SHA256"
DIRECTORIES = ("admission", "control-home", "final-admission", "service", "temporary")
CONTEXT_FIELDS = {"schema", "scope", "prelude", "selection", "cacheCohort", "source", "github", "root", "session",
                  "job", "inheritedContext", "runnerName", "admissionSha256", "admissionReturnSha256",
                  "admissionReturnedNs", "budgetAcceptance", "exportSaveAuthority"}
START_FIELDS = {"schema", "scope", "contextSha256", "argv", "cwd", "role", "job", "invocation", "state", "home",
                "inheritedContext", "startedNs", "workEndNs", "finalEndNs", "exitCode", "launchAttempted",
                "scopeAttempted", "retirement"}
PHASE_FILES = {"start.json", "baseline.json", "result.json", "native-start.json", "stdout.log", "stderr.log"}
TERMINAL_FIELDS = START_FIELDS | {"captureOutcomes", "baselineSha256", "launchMinimumNs", "launchArgv", "leader",
    "nativeStartSha256", "completedNs", "survivors", "ownership", "scopeCloseAttempted", "scopeClosed",
    "finalizedNs", "captures", "errors", "preparerIdentity"}
RESULT_FIELDS = {"schema", "scope", "contextSha256", "originalChain", "finalAdmission",
    "finalAdmissionOriginals", "retainedNs", "budgetAcceptance", "testAcceptance", "exportSaveAuthority",
    "sessionIdentity", "directories", "processIdentity"}
HANDOFF_FIELDS = {"schema", "scope", "originSha256", "contextSha256", "clock", "closedNs", "recordedNs",
    "processIdentity", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"}
LIFETIME_FIELDS = {
    "linux-x64": ("pid", "startTicks"), "windows-x64": ("pid", "creationFileTime"),
    **{role: ("pid", "uniqueId", "startSeconds", "startMicroseconds", "pidVersion")
       for role in ("macos-arm64", "macos-x64")},
}
IDENTITY_ENV = (
    "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_REF", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
    "GITHUB_EVENT_NAME", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKSPACE", "GITHUB_EVENT_PATH",
    "GITHUB_SERVER_URL", "GITHUB_API_URL", "GITHUB_JOB", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME",
    "RUNNER_ENVIRONMENT", "RUNNER_TEMP", "ImageOS", "ImageVersion",
)
BACKENDS = {"linux-x64": "linux-proc-pidfd", "windows-x64": "windows-job-list-suspended",
            "macos-arm64": "darwin-libproc-audit-token", "macos-x64": "darwin-libproc-audit-token"}


@dataclass(frozen=True)
class OriginalPhase:
    """Immutable returned bytes, also registered by identity on the current owner."""
    context: bytes
    records: tuple


@dataclass(frozen=True)
class OriginalEntry:
    """Same-call read-only entry; neither a productive owner nor a job budget."""
    raw: bytes
    admitted: I.Admission
    session: str
    session_original: bytes
    return_original: bytes
    handoff_original: bytes = field(repr=False)
    context_original: bytes = field(repr=False)
    preparation_original: bytes = field(repr=False)
    _owner: object = field(repr=False, compare=False)
    _fence: object = field(repr=False, compare=False)
    _private: object = field(repr=False, compare=False)
    _target: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class ClosedEntryTransition:
    """Same-call old-owner close only. Private bytes, no transferable live pins.

    No constructor/disk copy can recreate the owner's exact returned registry
    entry. This is not productive admission, atomic freeze or command success.
    """
    raw: bytes = field(repr=False)
    pending_raw: bytes = field(repr=False)
    proposal_raw: bytes = field(repr=False)
    responses: tuple = field(repr=False)
    _entry: object = field(repr=False, compare=False)
    _owner: object = field(repr=False, compare=False)
    _fence: object = field(repr=False, compare=False)
    _limits: tuple = field(repr=False)
    _callbacks: tuple = field(repr=False, compare=False)
    _snapshot: tuple = field(repr=False, compare=False)
    _retained_ns: int = field(repr=False)
    _preclose_ns: int = field(repr=False)
    _closed_ns: int = field(repr=False)
    _checked_ns: int = field(repr=False)


def require(value, reason):
    origin.require(value, reason)


def cancellation(cancelled):
    if cancelled:
        raise KeyboardInterrupt("BOOTSTRAP_ORIGIN_CANCELLED")


def host_inputs(role):
    """Actual process inputs only, never an injected hosted environment."""
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
            os.environ.get("GITHUB_REPOSITORY") == I.REPOSITORY and
            os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and
            os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            os.environ.get("GITHUB_WORKSPACE") == str(ROOT) and
            os.environ.get("GITHUB_JOB") == bootstrap.JOB and
            (os.environ.get("RUNNER_OS"), os.environ.get("RUNNER_ARCH")) == query._ROLES[role],
            "BOOTSTRAP_ACTUAL_HOSTED_CALLER")
    raw = I.read_regular(Path(os.environ.get("GITHUB_EVENT_PATH", "")), I.EVENT_LIMIT)
    inputs = I.parse(raw, I.EVENT_LIMIT).get("inputs")
    require(type(inputs) is dict and set(inputs) == bootstrap.INPUTS, "BOOTSTRAP_DISPATCH_INPUTS")
    selection = inputs["selection"]
    require(bootstrap.selection(selection)[1] == role, "BOOTSTRAP_SELECTION_NATIVE_ROLE")
    run, attempt = os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_RUN_ATTEMPT")
    require(type(run) is str and I.ID.fullmatch(run) and type(attempt) is str and I.ID.fullmatch(attempt),
            "BOOTSTRAP_RUN_ID")
    parent = Path(os.environ.get("RUNNER_TEMP", ""))
    require(parent.is_absolute() and ".." not in parent.parts and parent == parent.resolve(strict=True) and
            parent.is_dir() and parent != ROOT and ROOT not in parent.parents and parent not in ROOT.parents,
            "BOOTSTRAP_PRIVATE_PARENT")
    for path in (parent, *parent.parents):
        info = path.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "BOOTSTRAP_PRIVATE_PARENT_ALIAS")
    return selection, parent / ("p2pkit-cache-originals-" + run + "-" + attempt + "-" + selection), raw


def child_environment(path):
    base = dict(os.environ)
    blocked = {"JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS",
               "BASH_ENV", "ENV", "ZDOTDIR", "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT",
               "KONAN_HOME", "KOTLIN_HOME", "KOTLIN_OPTS", "KONAN_OPTS", "KONAN_JVM_ARGS",
               "KOTLIN_NATIVE_HOME", "SDKROOT", "TOOLCHAINS", "XCODE_XCCONFIG_FILE"}
    for name, value in base.items():
        require(not (value and (name in blocked or name.startswith(("DYLD_", "LD_", "BASH_FUNC_",
                "ORG_GRADLE_PROJECT_")))), "BOOTSTRAP_AMBIENT_EXECUTION_OVERRIDE")
        require(not name.startswith("GIT_") or name == "GIT_TERMINAL_PROMPT", "BOOTSTRAP_AMBIENT_GIT_OVERRIDE")
    inherited = query._inherited_context()
    allowed = {*IDENTITY_ENV, "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "LC_ALL"}
    result = {name: value for name, value in base.items() if name in allowed}
    result.update(inherited)
    result.update(PATH=os.defpath, HOME=str(path / "control-home"), USERPROFILE=str(path / "control-home"),
        TMPDIR=str(path / "temporary"), TMP=str(path / "temporary"), TEMP=str(path / "temporary"),
        PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", GIT_TERMINAL_PROMPT="0")
    return result


class Owner:
    """Original native-private file owners, not another process backend.

    The initial child metadata read has a fixed local45 ceiling until it loads
    the earlier parent frame. Binding can only shorten that ceiling. It grants
    no execution authority; the already-running native parent owns the child.
    """
    def __init__(self, local_end, fence=None, *, first=None, cancelled=lambda: None):
        require(type(local_end) in (int, float), "BOOTSTRAP_OWNER_LOCAL_FENCE")
        try:
            local_end = float(local_end)
        except (ValueError, OverflowError):
            raise origin.OriginError("BOOTSTRAP_OWNER_LOCAL_FENCE") from None
        local = time.monotonic()
        require(math.isfinite(local_end) and type(local) in (int, float) and math.isfinite(local) and
                0 <= local < local_end and callable(cancelled), "BOOTSTRAP_OWNER_LOCAL_FENCE")
        if first is not None:
            origin.clocks.validate_reading(first)
        self.local_end, self.fence = local_end, fence
        self.work_limit = self.final_limit = None
        self.first, self.early_last, self.cancelled = first, None if first is None else first.nanoseconds, cancelled
        self.resources, self.errors = [], []
        self.original, self.unknown, self.closed = None, False, False
        self.phase_originals, self.admissions, self.entry_original = None, {}, None
        self.entry_close_attempted, self.entry_close_original, self.entry_close_snapshot = False, None, None

    def error(self, stage, error, *, unknown=False):
        detail = diagnostics._exception_detail(error)
        self.unknown |= unknown or detail["retirementUnknown"]
        if self.original is None:
            self.original = error
        if len(self.errors) < 64:
            self.errors.append({"stage": stage, "detail": detail})
        else:
            self.unknown = True

    def bind(self, fence, *, work_limit, final_limit):
        require(self.fence is None and self.first is not None and self.first.clock == fence.clock,
                "BOOTSTRAP_OWNER_FRAME_BINDING")
        fence.now(minimum=self.early_last, limit=work_limit)
        self.fence, self.work_limit, self.final_limit = fence, work_limit, final_limit
        self.local_end = min(self.local_end, fence.deadline(45, final=True, limit=final_limit))
        self.end()

    def end(self, *, final=False):
        require(not self.closed and not self.unknown, "BOOTSTRAP_OWNER_NOT_LIVE")
        require(final or self.original is None, "BOOTSTRAP_OWNER_FAILED")
        end = self.local_end
        if self.fence is not None:
            end = min(end, self.fence.deadline(45, final=final,
                limit=self.final_limit if final else self.work_limit))
        elif self.first is not None:
            self.early_last = origin.clocks.checked_now(self.first.clock, minimum_ns=self.early_last)
            if not final:
                self.cancelled()
        posix._deadline(end)
        return end

    def acquire(self, label, factory, *, final=False):
        self.end(final=final)
        try:
            value = factory()
        except BaseException as error:
            self.error(label + "-allocation", error, unknown=True)
            raise
        require(not any(row["owner"] is value for row in self.resources), "BOOTSTRAP_DUPLICATE_OWNER")
        self.resources.append({"label": label, "owner": value, "attempted": False, "closed": False})
        # A returned, registered resource remains known when only this later
        # clock check fails. Cleanup must not be misclassified as UNKNOWN.
        self.end(final=final)
        return value

    def new(self, path):
        return self.acquire("directory", lambda: query._new_private_directory(path))

    def open(self, path, *, final=False):
        return self.acquire("directory", lambda: windows.open_private_directory(path) if os.name == "nt"
                            else query._PosixDirectory(path), final=final)

    def child(self, parent, name, *, create=False, final=False):
        end = self.end(final=final)
        if create:
            return self.acquire("directory", lambda: parent.create_directory(name, deadline=end), final=final)
        if os.name == "nt":
            return self.acquire("directory", lambda: parent.open_directory(name, deadline=end), final=final)
        parent.verify()
        query._component(name)
        return self.open(parent.path / name, final=final)

    def read(self, parent, name, maximum=LIMIT, *, final=False):
        end = self.end(final=final)
        try:
            raw = parent.read_bytes(name, max_bytes=maximum, deadline=end)
        except BaseException as error:
            self.error("reader", error, unknown=True)
            raise
        posix._deadline(end)
        self.end(final=final)
        return raw

    def close_fence(self):
        # Clock failure never skips already-owned cleanup or grants fresh time.
        try:
            if self.fence is not None:
                self.fence.now(final=True, limit=self.final_limit)
            elif self.first is not None:
                self.early_last = origin.clocks.checked_now(self.first.clock, minimum_ns=self.early_last)
            posix._deadline(self.local_end)
        except BaseException as error:
            self.error("close-fence", error)

    def close_one(self, value):
        row = next(row for row in self.resources if row["owner"] is value)
        if row["attempted"]:
            return
        self.close_fence()
        row["attempted"] = True
        try:
            value.close()
            row["closed"] = True
        except BaseException as error:
            self.error(row["label"] + "-close", error, unknown=True)
        self.close_fence()

    def write(self, parent, name, value, *, final=False):
        raw = value if type(value) is bytes else origin.encoded(value)
        require(0 < len(raw) <= LIMIT, "BOOTSTRAP_PRIVATE_RECORD_LIMIT")
        end = self.end(final=final)
        stream = self.acquire("writer", lambda: parent.create_file(name, max_bytes=len(raw), deadline=end), final=final)
        original = None
        try:
            require(stream.write(raw) == len(raw), "BOOTSTRAP_SHORT_WRITE")
            stream.sync()
            require(stream.verify().size == len(raw), "BOOTSTRAP_PRIVATE_WRITE_CHANGED")
        except BaseException as error:
            original = error
            self.error("write", error)
        finally:
            self.close_one(stream)
        if original is not None:
            raise original
        require(not self.unknown and self.read(parent, name, final=final) == raw, "BOOTSTRAP_PRIVATE_READBACK")
        posix._deadline(end)
        return raw

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.close_fence()
        if not self.unknown:
            for row in reversed(self.resources):
                if self.unknown:
                    break
                self.close_one(row["owner"])
        self.close_fence()
        if self.unknown:
            if not any(value is self for value in QUARANTINE):
                QUARANTINE.append(self)
            raise origin.OriginError("BOOTSTRAP_RETIREMENT_UNKNOWN")


def load_admission(owner, directory, *, final=False):
    raw = owner.read(directory, "admission.json", final=final)
    value = origin.parse(raw)
    admitted = I.Admission(raw, owner.read(directory, "original-event.json", final=final),
        owner.read(directory, "original-policy.json", final=final),
        owner.read(directory, "recipient-public.asc", final=final), value["policy"]["fingerprint"], value["policy"]["keySha256"],
        value["policy"]["expiresAt"])
    origin.admitted_value(admitted)
    return admitted


def admit(owner, fence, directory, *, expected=None):
    supplier = None
    original, result = None, None
    try:
        owner.end()
        require(owner.fence is fence and str(directory) not in owner.admissions, "BOOTSTRAP_ADMISSION_OWNER")
        pair = (min(owner.local_end, fence.deadline(origin.WORK_SECONDS)),
                min(owner.local_end, fence.deadline(origin.PRELUDE_SECONDS, final=True)))
        supplier = query.NativeGitQueries(ROOT, directory, check_cancel=fence.now, owner_deadlines=pair)
        supplier.native_host_matches_actions()
        result = bootstrap.admit(ROOT, query_runner=supplier, expected=expected)
        supplier.retain_admission(result)
        fence.now()
    except BaseException as error:
        original = error
    finally:
        if supplier is not None:
            try:
                supplier._finalize(original)
            except BaseException as error:
                original = original or error
        if (supplier is not None and supplier.unknown) or query.QUARANTINE or diagnostics._QUARANTINE:
            owner.error("native-query", original or origin.OriginError("BOOTSTRAP_QUERY_UNKNOWN"), unknown=True)
    if original is not None:
        raise original
    require(type(result) is I.Admission, "BOOTSTRAP_MISSING_ADMISSION")
    owner.end()
    retained = owner.open(directory)
    require(load_admission(owner, retained) == result, "BOOTSTRAP_RETURNED_ADMISSION_CHANGED")
    session = owner.read(retained, "session-result.json")
    returned = {"admissionSha256": origin.digest(result.record), "sessionSha256": origin.digest(session),
                "clock": origin.clock_value(fence.clock), "returnedNs": fence.now()}
    owner.admissions[str(directory)] = (result, session, origin.encoded(returned))
    return result, returned


def command(context_hash, minimum=None):
    require(type(context_hash) is str and re.fullmatch(r"[0-9a-f]{64}", context_hash), "BOOTSTRAP_CONTEXT_HASH")
    result = [str(Path(sys.executable).resolve(strict=True)), "-I", "-B", "-S", str(Path(__file__).resolve()),
              "_service", "--context-sha256", context_hash]
    return result if minimum is None else result + ["--minimum-ns", str(origin.integer(minimum))]


def lifetime(value, role):
    require(type(value) is dict, "BOOTSTRAP_NATIVE_LIFETIME")
    keys = (("pid", "creationFileTime") if role == "windows-x64" else
            ("pid", "uniqueId", "startSeconds", "startMicroseconds", "pidVersion") if role.startswith("macos-") else
            ("pid", "startTicks"))
    values = tuple(origin.integer(value.get(key), 0 if key in ("startMicroseconds", "pidVersion") else 1) for key in keys)
    if role.startswith("macos-"):
        require(value["startMicroseconds"] < 1_000_000, "BOOTSTRAP_NATIVE_LIFETIME")
    return values


def closed_lifetime(value, role):
    require(type(value) is dict and role in LIFETIME_FIELDS and set(value) == set(LIFETIME_FIELDS[role]),
            "BOOTSTRAP_PREPARER_LIFETIME")
    lifetime(value, role)
    return value


def preparer_identity(scope, role):
    """Read this process through the already-admitted native service scope.

    Windows uses the current-process pseudo-handle, never an acquired handle
    or a PID-based OpenProcess lookup. There is nothing extra to close. POSIX
    uses the scope's existing admitted native identity reader, not a new census.
    """
    require(scope.name == BACKENDS[role], "BOOTSTRAP_PREPARER_BACKEND")
    pid = os.getpid()
    if role == "windows-x64":
        value = scope.api.identity(processes.PTR(-1), pid)
    else:
        value = scope._identity(pid, required=True) if role.startswith("macos-") else scope._identity(pid)
        require(type(value) is dict and value.get("live") is True, "BOOTSTRAP_PREPARER_NOT_OBSERVED")
    require(type(value) is dict and type(value.get("pid")) is int and value["pid"] == pid,
            "BOOTSTRAP_PREPARER_NOT_OBSERVED")
    return closed_lifetime({name: value.get(name) for name in LIFETIME_FIELDS[role]}, role)


def directory_identity(value, role):
    require(type(value) is list and len(value) == 2 and type(value[0]) is int and
            0 <= value[0] <= origin.clocks.UINT64, "BOOTSTRAP_ORIGINAL_DIRECTORY_IDENTITY")
    if role == "windows-x64":
        require(type(value[1]) is str and re.fullmatch(r"[0-9a-f]{32}", value[1]),
                "BOOTSTRAP_ORIGINAL_DIRECTORY_IDENTITY")
    else:
        origin.integer(value[1], 1)
    return value


def private_identities(owner, private, *, final=True):
    """Observe original native directory IDs, never infer them from path names."""
    role = owner.fence.clock.role
    owner.end(final=final)
    private.verify()
    identity = directory_identity(list(private.identity), role)
    directories = {}
    for name in DIRECTORIES:
        child = owner.child(private, name, final=final)
        child.verify()
        directories[name] = directory_identity(list(child.identity), role)
        owner.end(final=final)
    private.verify()
    owner.end(final=final)
    return {"sessionIdentity": identity, "directories": directories}


def native_record(value, start, leader, argv, *, terminal=True):
    role = start["role"]
    require(type(value) is dict and value.get("backend") == BACKENDS[role] and
            value.get("job") == start["job"] and value.get("invocation") == start["invocation"] and
            type(value.get("discoveryErrors")) is list and (not terminal or value["discoveryErrors"] == []),
            "BOOTSTRAP_NATIVE_BINDING")
    wins = role == "windows-x64"
    require(value.get("scope") == ("kernel-job-no-breakaway-kill-on-close" if wins else
            "controlled-marker-inheriting-descendants"), "BOOTSTRAP_NATIVE_SCOPE")
    launches, identities = value.get("launches"), value.get("startedIdentities")
    require(type(launches) is list and len(launches) == 1 and type(launches[0]) is dict and
            type(identities) is list and identities and all(type(item) is dict for item in identities),
            "BOOTSTRAP_NATIVE_ORIGINAL_LAUNCH")
    launch = launches[0]
    require(launch.get("created") is True and launch.get("requestedArgv") == launch.get("resolvedArgv") == argv and
            launch.get("cwd") == start["cwd"] and type(launch.get("pid")) is int and launch["pid"] == leader["pid"] and
            len([item for item in identities if lifetime(item, role) == lifetime(leader, role)]) == 1,
            "BOOTSTRAP_NATIVE_ORIGINAL_LIFETIME")
    if wins:
        require(launch.get("api") == "CreateProcessW" and launch.get("batch") is False and
                launch.get("applicationName") == argv[0] and launch.get("commandLine") == subprocess.list2cmdline(argv) and
                launch.get("resumed") is True and launch.get("jobAssignedBeforeResume") is True and
                leader.get("jobAssignedBeforeResume") is True and
                launch.get("outputMode") == "caller-owned-native-files", "BOOTSTRAP_NATIVE_WINDOWS_LAUNCH")
        cleanup = launch.get("resourceCleanup")
        names = {"startup-attributes", "launch-handle-0", "launch-handle-1", "launch-handle-2", "primary-thread"}
        require(type(cleanup) is list and len(cleanup) == len(names) and all(type(row) is dict and
                set(row) == {"phase", "resource", "status"} and row["phase"] == "launch-temporary" and
                row["status"] == "RETIRED" and type(row["resource"]) is str for row in cleanup) and
                {row["resource"] for row in cleanup} == names, "BOOTSTRAP_NATIVE_WINDOWS_TEMPORARIES")
    else:
        require(launch.get("api") == "subprocess.Popen" and launch.get("shell") is False and
                launch.get("executable") == argv[0] and launch.get("outputMode") == "caller-owned-files" and
                type(value.get("discoveryReconciliations")) is list, "BOOTSTRAP_NATIVE_POSIX_LAUNCH")
    if role.startswith("macos-") and terminal:
        require(all(type(row) is dict and row.get("outcome") in
                ("lifetime-ended", "nonrunning", "replaced", "unmarked", "owned") for row in value["discoveryReconciliations"]),
                "BOOTSTRAP_NATIVE_DARWIN_DISCOVERY")
        drains = value.get("drainReconciliations")
        require(type(value.get("observationReconciliations")) is list and type(drains) is list and drains and
                all(type(row) is dict and row.get("outcome") == "retired" and "error" not in row and
                    type(row.get("signalReconciliations")) is list and
                    all(type(signal) is dict and signal.get("outcome") in ("absent", "nonrunning", "replaced", "signal-succeeded")
                        for signal in row["signalReconciliations"]) for row in drains), "BOOTSTRAP_NATIVE_DARWIN_DRAIN")


def context_record(raw, admitted, path, fence):
    value = origin.parse(raw)
    record = origin.admitted_value(admitted)
    require(set(value) == CONTEXT_FIELDS and raw == origin.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == CONTEXT_SCOPE and
            value["prelude"] == origin.parse(fence.raw) and value["selection"] == record["selection"] and
            value["cacheCohort"] == record["cacheCohort"] and value["source"] == record["source"] and
            value["github"] == record["github"] and record["cacheCohort"]["role"] == fence.clock.role and
            value["root"] == str(ROOT) and value["session"] == str(path) and
            value["admissionSha256"] == origin.digest(admitted.record) and
            value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False,
            "BOOTSTRAP_ORIGINAL_CONTEXT")
    require(type(value["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["job"]) and
            type(value["runnerName"]) is str and 0 < len(value["runnerName"]) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in value["runnerName"]) and
            type(value["admissionReturnSha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["admissionReturnSha256"]),
            "BOOTSTRAP_ORIGINAL_CONTEXT_IDENTITIES")
    history.context_return(history.snapshot(fence), value["admissionReturnedNs"])
    inherited = value["inheritedContext"]
    require(type(inherited) is dict and set(inherited).issubset(query._CONTEXT) and
            all(type(item) is str for item in inherited.values()) and
            (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(query._CONTEXT)),
            "BOOTSTRAP_ORIGINAL_PARENT_CONTEXT")
    return value


def start_record(raw, context_raw, context, path, fence):
    start = origin.parse(raw)
    require(set(start) == START_FIELDS and raw == origin.encoded(start) and
            type(start["schema"]) is int and start["schema"] == 1 and start["scope"] == PHASE_SCOPE and
            start["contextSha256"] == origin.digest(context_raw) and start["argv"] == command(origin.digest(context_raw)) and
            start["cwd"] == str(ROOT) and start["role"] == fence.clock.role and start["job"] == context["job"] and
            start["state"] == str(path) and start["home"] == str(path / "control-home") and
            start["exitCode"] is None and start["launchAttempted"] is False and start["scopeAttempted"] is False and
            start["retirement"] == "UNKNOWN" and type(start["invocation"]) is str and
            re.fullmatch(r"[0-9a-f]{32}", start["invocation"]), "BOOTSTRAP_ORIGINAL_PRELAUNCH")
    history.phase_start(history.snapshot(fence), context["admissionReturnedNs"], start)
    expected = processes.ownership_environment(context["inheritedContext"], context["job"], start["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    require(start["inheritedContext"] == {name: expected[name] for name in query._CONTEXT},
            "BOOTSTRAP_ORIGINAL_ANCESTORS")
    return start


def baseline_record(raw, role):
    value = origin.parse(raw)
    require(set(value) == {"role", "baseline", "kernelJob"} and value["role"] == role and
            value["kernelJob"] is (role == "windows-x64"), "BOOTSTRAP_ORIGINAL_BASELINE")
    if role == "windows-x64":
        require(value["baseline"] is None, "BOOTSTRAP_ORIGINAL_BASELINE")
    else:
        rows = value["baseline"]
        width = 4 if role.startswith("macos-") else 2
        require(type(rows) is list and all(type(row) is list and len(row) == width and
                all(type(part) is int and 0 <= part <= origin.clocks.UINT64 for part in row) and row[0] > 0
                for row in rows), "BOOTSTRAP_ORIGINAL_BASELINE")
        require(rows == sorted(rows) and len(set(tuple(row) for row in rows)) == len(rows) and
                (width != 4 or all(row[3] < 1_000_000 for row in rows)), "BOOTSTRAP_ORIGINAL_BASELINE")
    return value


def admission_originals(owner, private, admitted, fence, *, final=False, read_final=True):
    name = "final-admission" if final else "admission"
    registered = owner.admissions.get(str(private.path / name))
    require(registered is not None and registered[0] is admitted, "BOOTSTRAP_ADMISSION_NOT_CURRENT_RETURN")
    directory = owner.child(private, name, final=read_final)
    require(load_admission(owner, directory, final=read_final) == admitted, "BOOTSTRAP_ORIGINAL_ADMISSION_CHANGED")
    session = owner.read(directory, "session-result.json", final=read_final)
    returned = owner.read(private, name + "-return.json", final=read_final)
    require(session == registered[1] and returned == registered[2], "BOOTSTRAP_ORIGINAL_ADMISSION_RETURN_CHANGED")
    return admission_content(admitted, session, returned, fence)


def admission_content(admitted, session, returned, fence):
    """Record consistency only; never registers a supplied native-query return."""
    value = origin.parse(returned)
    require(returned == origin.encoded(value) and
            set(value) == {"admissionSha256", "sessionSha256", "clock", "returnedNs"} and
            value["admissionSha256"] == origin.digest(admitted.record) and
            value["sessionSha256"] == origin.digest(session) and value["clock"] == origin.clock_value(fence.clock) and
            history.admission_return(history.snapshot(fence), value["returnedNs"]), "BOOTSTRAP_ORIGINAL_ADMISSION_RETURN")
    status = origin.parse(session)
    require(set(status) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"} and
            type(status["schema"]) is int and status["schema"] == 1 and status["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
            status["result"] == "READY_FOR_CALLER_SEAL" and status["retirement"] == "KNOWN" and
            status["firstError"] is None and status["errors"] == [] and type(status["queries"]) is list and
            type(status["readbacks"]) is list and type(status["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", status["job"]),
            "BOOTSTRAP_ORIGINAL_QUERY_SESSION")
    # This label is deliberately insufficient on its own. Current-call use has
    # the registry above; later use needs the original trusted workflow outcome.
    return value, {"admissionSha256": origin.digest(admitted.record), "sessionSha256": origin.digest(session),
                   "returnSha256": origin.digest(returned)}


def phase(owner, private, context_raw, token, fence):
    context = origin.parse(context_raw)
    started = fence.now()
    work_end = min(fence.work, started + origin.wire.ACQUIRE_SECONDS * origin.NS)
    final_end = min(fence.final, work_end + 45 * origin.NS)
    old_limits = owner.work_limit, owner.final_limit
    owner.work_limit, owner.final_limit = work_end, final_end
    invocation = uuid.uuid4().hex
    argv = command(origin.digest(context_raw))
    env = processes.ownership_environment(child_environment(private.path), context["job"], invocation,
        str(private.path), str(private.path / "control-home"), allow_new_context=True)
    inherited = {name: env[name] for name in query._CONTEXT}
    start = {"schema": 1, "scope": PHASE_SCOPE, "contextSha256": origin.digest(context_raw), "argv": argv,
             "cwd": str(ROOT), "role": fence.clock.role, "job": context["job"], "invocation": invocation,
             "state": str(private.path), "home": str(private.path / "control-home"), "inheritedContext": inherited,
             "startedNs": started, "workEndNs": work_end, "finalEndNs": final_end,
             "exitCode": None, "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"}
    directory = owner.child(private, "service", create=True)
    start_raw = owner.write(directory, "start.json", start)
    row = dict(start)
    scope = out = err = child = None
    before_errors = len(owner.errors)
    captured, native_known, baseline_raw = {}, False, None
    row["captureOutcomes"] = {name: {"synced": False, "verified": False, "closeAttempted": False,
                                    "closed": False, "readback": False} for name in ("stdout", "stderr")}
    resource_start = len(owner.resources)
    try:
        # The capture files remain alive through finalization, but acquisition
        # itself still checks the original work cutoff before AND after return.
        # The lifetime of the inherited sinks is the ORIGINAL phase final
        # fence, not a new per-file IO45 interval beginning at allocation.
        end = min(owner.local_end, fence.deadline(origin.wire.ACQUIRE_SECONDS + 45,
            final=True, limit=final_end))
        out = owner.acquire("stdout", lambda: directory.create_file("stdout.log", max_bytes=ACK_LIMIT, deadline=end))
        err = owner.acquire("stderr", lambda: directory.create_file("stderr.log", max_bytes=STDERR_LIMIT, deadline=end))
        fence.now(limit=work_end)
        row["scopeAttempted"] = True
        scope = owner.acquire("native-scope", lambda: processes.make_scope(context["job"], invocation,
            str(private.path), str(private.path / "control-home")))
        row["preparerIdentity"] = preparer_identity(scope, fence.clock.role)
        baseline_raw = owner.write(directory, "baseline.json", {"role": fence.clock.role,
            "baseline": sorted(scope.baseline) if hasattr(scope, "baseline") else None,
            "kernelJob": fence.clock.role == "windows-x64"})
        row["baselineSha256"] = origin.digest(baseline_raw)
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "BOOTSTRAP_ACTIONS_READ_TOKEN")
        env[origin.wire.TOKEN_ENV], token = token, None
        row["launchMinimumNs"] = fence.now(limit=work_end)
        argv = command(origin.digest(context_raw), row["launchMinimumNs"])
        row["launchArgv"] = argv
        row["launchAttempted"] = True
        child = scope.spawn(argv, str(ROOT), env, stdout=out, stderr=err)
        env.pop(origin.wire.TOKEN_ENV, None)
        require(child.stdout is None and child.stderr is None, "BOOTSTRAP_PRIVATE_SINKS_REQUIRED")
        birth = scope.description()
        leaders = [item for item in birth.get("startedIdentities", []) if item.get("pid") == child.pid]
        require(len(leaders) == 1, "BOOTSTRAP_NATIVE_BIRTH_MISSING")
        row["leader"] = dict(leaders[0])
        lifetime(row["leader"], fence.clock.role)
        birth_raw = owner.write(directory, "native-start.json", {"ownership": birth,
            "leader": row["leader"], "preparerIdentity": row["preparerIdentity"],
            "observedNs": fence.now(limit=work_end)})
        row["nativeStartSha256"] = origin.digest(birth_raw)
        while True:
            fence.now(limit=work_end)
            if fence.clock.role == "windows-x64":
                out.observe_live_output()
                err.observe_live_output()
            else:
                out.verify()
                err.verify()
            code = child.poll()
            if code is not None:
                row["exitCode"] = code  # Preserve actual exit before fallible clock reads.
            observed = fence.now(limit=work_end)
            if code is not None:
                row["completedNs"] = observed
                require(type(code) is int and code == 0, "BOOTSTRAP_SERVICE_CHILD_FAILED")
                require(not scope.discover(), "BOOTSTRAP_SERVICE_LEFT_DESCENDANTS")
                break
            scope.discover()
            time.sleep(.025)
    except BaseException as error:
        owner.error("service", error)
    finally:
        env.pop(origin.wire.TOKEN_ENV, None)
        token = None
        # A known returned allocation can fail its post-allocation clock check
        # before Python assigns the local variable. Its original registry entry
        # still owns cleanup; do not invent a new scope or call it unreturned.
        if scope is None:
            scope = next((item["owner"] for item in owner.resources[resource_start:]
                          if item["label"] == "native-scope"), None)
        if scope is not None:
            try:
                try:
                    remaining = (final_end - fence.now(final=True, limit=final_end)) / origin.NS
                except BaseException as error:
                    owner.error("drain-fence", error)
                    remaining = 0
                grace = min(5, remaining)
                kill_wait = min(5, max(0, remaining - grace))
                row["survivors"] = scope.drain(grace=grace, kill_wait=kill_wait)
                require(row["survivors"] == [], "BOOTSTRAP_SERVICE_SURVIVORS")
                row["ownership"] = scope.description()
                require(row["ownership"].get("discoveryErrors") == [], "BOOTSTRAP_SERVICE_DISCOVERY_UNKNOWN")
                require(preparer_identity(scope, fence.clock.role) == row["preparerIdentity"],
                        "BOOTSTRAP_PREPARER_LIFETIME_CHANGED")
                native_known = True
            except BaseException as error:
                owner.error("service-drain", error, unknown=True)
            owner.close_one(scope)
            row["scopeCloseAttempted"] = next(item["attempted"] for item in owner.resources if item["owner"] is scope)
            row["scopeClosed"] = next(item["closed"] for item in owner.resources if item["owner"] is scope)
        elif row["scopeAttempted"]:
            owner.error("service-construction", origin.OriginError("BOOTSTRAP_NATIVE_CONSTRUCTION_UNKNOWN"), unknown=True)
        else:
            native_known = True
        if native_known and not owner.unknown:
            for name, stream in (("stdout", out), ("stderr", err)):
                if stream is not None:
                    outcome = row["captureOutcomes"][name]
                    try:
                        stream.sync()
                        outcome["synced"] = True
                        stream.verify()
                        outcome["verified"] = True
                    except BaseException as error:
                        owner.error("capture", error)
                    owner.close_one(stream)
                    resource = next(item for item in owner.resources if item["owner"] is stream)
                    outcome.update(closeAttempted=resource["attempted"], closed=resource["closed"])
            if not owner.unknown and out is not None and err is not None:
                try:
                    for name, maximum in (("stdout", ACK_LIMIT), ("stderr", STDERR_LIMIT)):
                        captured[name] = owner.read(directory, name + ".log", maximum, final=True)
                        row["captureOutcomes"][name]["readback"] = True
                except BaseException as error:
                    owner.error("capture-readback", error)
        else:
            owner.unknown = True
        row["retirement"] = "UNKNOWN" if owner.unknown else "KNOWN"
        try:
            row["finalizedNs"] = fence.now(final=True, limit=final_end)
            row["captures"] = {name: {"sha256": origin.digest(raw), "bytes": len(raw)} for name, raw in captured.items()}
            row["errors"] = owner.errors[before_errors:]
            row_raw = owner.write(directory, "result.json", row, final=True)
            fence.now(final=True, limit=final_end)
        except BaseException as error:
            owner.error("service-receipt", error)
        owner.work_limit, owner.final_limit = old_limits
    if owner.original is not None:
        raise owner.original
    require(not owner.unknown and not owner.errors and row["exitCode"] == 0 and captured.get("stderr") == b"",
            "BOOTSTRAP_SERVICE_NOT_ACCEPTED")
    require(owner.phase_originals is None, "BOOTSTRAP_DUPLICATE_ORIGINAL_PHASE")
    original = OriginalPhase(context_raw, tuple(sorted({"start.json": start_raw, "result.json": row_raw,
        "baseline.json": baseline_raw, "native-start.json": birth_raw,
        "stdout.log": captured["stdout"], "stderr.log": captured["stderr"]}.items())))
    owner.phase_originals = original
    return directory, original


def revalidate(owner, private, context_raw, admitted, originals, fence):
    """Repeatable READ-ONLY revalidation inside the current original owning call.

    `originals` comes from this call's returned native phase, not a public success
    flag or digest. Disk content validation below never populates this registry.
    """
    require(type(originals) is OriginalPhase and owner.phase_originals is originals and owner.fence is fence and
            originals.context == context_raw and any(item["owner"] is private and not item["attempted"]
                for item in owner.resources), "BOOTSTRAP_PHASE_NOT_CURRENT_RETURN")
    require(owner.read(private, "context.json", final=True) == context_raw and
            owner.read(private, "prelude.json", final=True) == fence.raw, "BOOTSTRAP_ORIGINAL_CONTEXT_CHANGED")
    context = context_record(context_raw, admitted, private.path, fence)
    returned, admission_hashes = admission_originals(owner, private, admitted, fence)
    require(context["admissionReturnSha256"] == admission_hashes["returnSha256"] and
            context["admissionReturnedNs"] == returned["returnedNs"], "BOOTSTRAP_ORIGINAL_CONTEXT_RETURN_CHANGED")
    require(type(originals.records) is tuple and len(originals.records) == len(PHASE_FILES) and
            all(type(item) is tuple and len(item) == 2 and type(item[0]) is str and type(item[1]) is bytes
                for item in originals.records), "BOOTSTRAP_ORIGINAL_PHASE_FILES")
    records = dict(originals.records)
    require(set(records) == PHASE_FILES, "BOOTSTRAP_ORIGINAL_PHASE_FILES")
    directory = owner.child(private, "service", final=True)
    for name, raw in records.items():
        maximum = ACK_LIMIT if name == "stdout.log" else STDERR_LIMIT if name == "stderr.log" else LIMIT
        require(owner.read(directory, name, maximum, final=True) == raw, "BOOTSTRAP_ORIGINAL_PHASE_CHANGED")
    return chain_content(owner, private, context_raw, admitted, records, returned, admission_hashes, fence, final=True)


def chain_content(owner, private, context_raw, admitted, records, returned, admission_hashes, fence, *, final):
    """Read-only record consistency, NOT a returned phase or admission owner.

    Current-call provenance is enforced by revalidate above. A cross-process
    reader instead needs the original handoff hash AND trusted step outcome;
    rehydrating these bytes never registers an OriginalPhase/native return.
    """
    require(type(records) is dict and set(records) == PHASE_FILES and
            all(type(raw) is bytes for raw in records.values()), "BOOTSTRAP_ORIGINAL_PHASE_FILES")
    context = context_record(context_raw, admitted, private.path, fence)
    require(context["admissionReturnSha256"] == admission_hashes["returnSha256"] and
            context["admissionReturnedNs"] == returned["returnedNs"], "BOOTSTRAP_ORIGINAL_CONTEXT_RETURN_CHANGED")
    directory = owner.child(private, "service", final=final)
    start = start_record(records["start.json"], context_raw, context, private.path, fence)
    row, birth = (origin.parse(records[name]) for name in ("result.json", "native-start.json"))
    baseline_record(records["baseline.json"], fence.clock.role)
    require(set(row) == TERMINAL_FIELDS and set(birth) == {"ownership", "leader", "preparerIdentity", "observedNs"},
            "BOOTSTRAP_ORIGINAL_TERMINAL_FIELDS")
    preparer = closed_lifetime(row["preparerIdentity"], fence.clock.role)
    require(preparer == closed_lifetime(birth["preparerIdentity"], fence.clock.role) and
            preparer["pid"] != row["leader"]["pid"], "BOOTSTRAP_ORIGINAL_PREPARER_CHANGED")
    for name in set(start) - {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}:
        require(row.get(name) == start[name], "BOOTSTRAP_ORIGINAL_START_CHANGED")
    require(type(row.get("exitCode")) is int and row["exitCode"] == 0 and row.get("launchAttempted") is True and
            row.get("scopeAttempted") is True and row.get("scopeCloseAttempted") is True and
            row.get("scopeClosed") is True and row.get("retirement") == "KNOWN" and
            row.get("survivors") == [] and row.get("errors") == [] and records["stderr.log"] == b"" and
            row.get("nativeStartSha256") == origin.digest(records["native-start.json"]) and
            row.get("baselineSha256") == origin.digest(records["baseline.json"]) and
            row.get("leader") == birth.get("leader"), "BOOTSTRAP_ORIGINAL_NATIVE_RETURN")
    argv = command(origin.digest(context_raw), origin.integer(row["launchMinimumNs"], start["startedNs"]))
    require(row["launchArgv"] == argv, "BOOTSTRAP_ORIGINAL_EXECUTED_ARGV")
    native_record(row["ownership"], start, row["leader"], argv)
    native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    # Birth may retain unresolved earlier observations. It cannot substitute
    # for the terminal native disposition, nor claim a later child clock.
    require(birth["ownership"]["launches"] == row["ownership"]["launches"] and
            any(lifetime(item, fence.clock.role) == lifetime(row["leader"], fence.clock.role)
                for item in birth["ownership"]["startedIdentities"]), "BOOTSTRAP_ORIGINAL_NATIVE_BIRTH_CHANGED")
    require(type(row["captures"]) is dict and set(row["captures"]) == {"stdout", "stderr"} and
            row["captureOutcomes"] == {name: {"synced": True, "verified": True, "closeAttempted": True,
                "closed": True, "readback": True} for name in ("stdout", "stderr")} and
            all(type(item) is bool for result in row["captureOutcomes"].values() for item in result.values()),
            "BOOTSTRAP_ORIGINAL_CAPTURE_RETIREMENT")
    for name in ("stdout", "stderr"):
        raw = records[name + ".log"]
        require(row["captures"].get(name) == {"sha256": origin.digest(raw), "bytes": len(raw)},
                "BOOTSTRAP_ORIGINAL_CAPTURE_CHANGED")
    child_raw = owner.read(directory, "child-result.json", final=final)
    child, ack = origin.parse(child_raw), origin.parse(records["stdout.log"])
    require(records["stdout.log"] == origin.encoded(ack) and set(ack) ==
            {"schema", "scope", "invocation", "terminalSha256", "clock", "closedNs"} and
            type(ack["schema"]) is int and ack["schema"] == 1 and ack["scope"] == ACK_SCOPE and
            ack["invocation"] == start["invocation"] and ack["terminalSha256"] == origin.digest(child_raw) and
            ack["clock"] == origin.clock_value(fence.clock), "BOOTSTRAP_ORIGINAL_CHILD_ACK")
    require(set(child) == {"schema", "scope", "contextSha256", "startSha256", "admissionSha256", "invocation", "clock",
            "launchMinimumNs", "beganNs", "metadataLastNs", "acquiredNs", "completedNs", "originalsSha256",
            "returned", "retirement", "errors"} and
            type(child["schema"]) is int and child["schema"] == 1 and child["scope"] == CHILD_SCOPE and
            child["contextSha256"] == origin.digest(context_raw) and child["startSha256"] == origin.digest(records["start.json"]) and
            child["admissionSha256"] == origin.digest(admitted.record) and child["invocation"] == start["invocation"] and
            child["clock"] == origin.clock_value(fence.clock) and child["returned"] is True and
            child["retirement"] == "KNOWN" and child["errors"] == [] and
            child["launchMinimumNs"] == row["launchMinimumNs"], "BOOTSTRAP_ORIGINAL_CHILD_TERMINAL")
    responses = {name: owner.read(directory, name + ".json", final=final) for name in ("attempt", "jobs")}
    basis = service_time.derive(admitted, responses, start["invocation"], fence.clock, context["runnerName"])
    service = basis["service"]
    require(child["originalsSha256"] == service["originalsSha256"], "BOOTSTRAP_ORIGINAL_RESPONSES_CHANGED")
    minimum = history.chain_minimum(history.snapshot(fence), context["admissionReturnedNs"],
                                    start, row, birth, child, service, ack)
    # This is still the actual owning reader's observation. A pure historical
    # minimum cannot attest current time, renew a fence or register provenance.
    last = fence.now(final=final, minimum=minimum)
    return {"service": service, "serviceTimeBasis": basis, "childTerminalSha256": origin.digest(child_raw),
            "phaseSha256": {name: origin.digest(raw) for name, raw in records.items()},
            "admissionOriginals": admission_hashes, "preludeSha256": origin.digest(fence.raw), "revalidatedNs": last,
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}


def service_child(context_hash, minimum, cancelled):
    token = os.environ.pop(origin.wire.TOKEN_ENV, None)
    local_end = time.monotonic() + 45
    first = origin.clocks.validate_reading(origin.clocks.observe())
    require(first.nanoseconds >= origin.integer(minimum), "BOOTSTRAP_CHILD_PRECEDES_LAUNCH")
    owner = Owner(local_end, first=first, cancelled=lambda: cancellation(cancelled))
    fence = result_raw = directory = None
    try:
        owner.end()
        selection, path, event = host_inputs(first.clock.role)
        owner.end()
        private = owner.open(path)
        context_raw = owner.read(private, "context.json")
        require(origin.digest(context_raw) == context_hash, "BOOTSTRAP_CHILD_CONTEXT_CHANGED")
        context = origin.parse(context_raw)
        fence = origin.Fence(context["prelude"], minimum=first.nanoseconds, cancelled=lambda: cancellation(cancelled))
        require(first.clock == fence.clock, "BOOTSTRAP_CHILD_CLOCK_CHANGED")
        directory = owner.child(private, "service")
        start_raw = owner.read(directory, "start.json")
        admitted = load_admission(owner, owner.child(private, "admission"))
        context = context_record(context_raw, admitted, path, fence)
        start = start_record(start_raw, context_raw, context, path, fence)
        require(context["selection"] == selection and admitted.original_event == event,
                "BOOTSTRAP_CHILD_ADMISSION_CHANGED")
        inherited = query._inherited_context()
        require(set(inherited) == set(query._CONTEXT) and inherited == start["inheritedContext"],
                "BOOTSTRAP_CHILD_ORIGINAL_NATIVE_CONTEXT")
        domain = processes.ownership_domains(inherited[processes.CHAIN_ENV], inherited[processes.DOMAINS_ENV])[-1]
        require(domain == {"id": start["invocation"], "job": start["job"], "state": start["state"], "home": start["home"]} and
                start["startedNs"] <= minimum <= first.nanoseconds < start["workEndNs"],
                "BOOTSTRAP_CHILD_PRECEDES_PARENT_OR_EXPIRED")
        # Keep every early metadata-read observation, not merely the later HTTP
        # time. Loading the original frame never renews the initial local cap.
        owner.bind(fence, work_limit=start["workEndNs"], final_limit=start["finalEndNs"])
        def retain(name, raw, *, failed):
            owner.write(directory, name + ".json", raw, final=failed)
        responses, acquired = origin.acquire(admitted, domain["id"], token, retain, fence,
            original_work_end=start["workEndNs"])
        token = None
        origin.service_identity(admitted, responses, domain["id"], fence.clock, context["runnerName"])
        result_raw = owner.write(directory, "child-result.json", {"schema": 1, "scope": CHILD_SCOPE,
            "contextSha256": context_hash, "startSha256": origin.digest(start_raw),
            "admissionSha256": context["admissionSha256"], "invocation": domain["id"], "clock": origin.clock_value(fence.clock),
            "launchMinimumNs": minimum, "beganNs": first.nanoseconds,
            "metadataLastNs": owner.early_last, "acquiredNs": acquired,
            "completedNs": fence.now(minimum=acquired, limit=start["workEndNs"]),
            "originalsSha256": {name: origin.digest(raw) for name, raw in responses.items()},
            "returned": True, "retirement": "KNOWN", "errors": []})
    except BaseException as error:
        owner.error("service-child", error)
        if directory is not None and not owner.unknown:
            try:
                owner.write(directory, "child-failure.json", {"schema": 1, "result": "HOLD", "errors": owner.errors,
                    "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED"}, final=True)
            except BaseException as secondary:
                owner.error("child-failure-retention", secondary)
    finally:
        token = None
        try:
            owner.close()
        except BaseException as error:
            owner.error("service-child-close", error)
    if owner.original is not None:
        raise owner.original
    require(fence is not None and result_raw is not None and not owner.unknown, "BOOTSTRAP_CHILD_NO_ORIGINALS")
    posix._deadline(owner.local_end)
    closed = fence.now(limit=start["workEndNs"])
    return {"schema": 1, "scope": ACK_SCOPE, "invocation": domain["id"], "terminalSha256": origin.digest(result_raw),
            "clock": origin.clock_value(fence.clock), "closedNs": closed}, fence, start["workEndNs"]


def prepare_originals(cancelled):
    token = os.environ.pop(origin.wire.TOKEN_ENV, None)
    first = origin.clocks.validate_reading(origin.clocks.observe())
    fence = origin.Fence(origin.prelude(first), minimum=first.nanoseconds, cancelled=lambda: cancellation(cancelled))
    owner = Owner(fence.deadline(origin.PRELUDE_SECONDS, final=True), fence)
    private = result_raw = None
    try:
        require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                "BOOTSTRAP_PRIOR_UNKNOWN")
        selection, path, event = host_inputs(first.clock.role)
        inherited = query._inherited_context()
        child_environment(path)  # Refuse conflicting inputs before allocating.
        fence.now()
        private = owner.new(path)  # Exclusive episode; never retry/overwrite a prior acquisition.
        owner.write(private, "prelude.json", fence.raw)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        admitted, returned = admit(owner, fence, path / "admission")
        value = origin.admitted_value(admitted)
        require(admitted.original_event == event and value["selection"] == selection and
                value["cacheCohort"]["role"] == fence.clock.role, "BOOTSTRAP_ENTRY_CHANGED")
        returned_raw = owner.write(private, "admission-return.json", returned)
        context_raw = owner.write(private, "context.json", {"schema": 1, "scope": CONTEXT_SCOPE,
            "prelude": origin.parse(fence.raw), "selection": selection, "cacheCohort": value["cacheCohort"],
            "source": value["source"], "github": value["github"], "root": str(ROOT), "session": str(path),
            "job": uuid.uuid4().hex, "inheritedContext": inherited, "runnerName": os.environ.get("RUNNER_NAME"),
            "admissionSha256": origin.digest(admitted.record), "admissionReturnSha256": origin.digest(returned_raw),
            "admissionReturnedNs": returned["returnedNs"], "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        directory, originals = phase(owner, private, context_raw, token, fence)
        token = None
        checked = revalidate(owner, private, context_raw, admitted, originals, fence)
        # Actual source/main/policy re-admission, not trusting candidate source or
        # substituting an unchanged digest for live source/query return.
        final_admitted, final_admission = admit(owner, fence, path / "final-admission", expected=admitted)
        owner.write(private, "final-admission-return.json", final_admission)
        _, final_hashes = admission_originals(owner, private, final_admitted, fence, final=True)
        # Recheck the original chain after the final actual admission as well;
        # this is read-only repetition, not a second API acquisition/adoption.
        checked = revalidate(owner, private, context_raw, admitted, originals, fence)
        identities = private_identities(owner, private)
        process_identity = origin.parse(dict(originals.records)["result.json"])["preparerIdentity"]
        result_raw = owner.write(private, "origin-result.json", {"schema": 1, "scope": RESULT_SCOPE,
            "contextSha256": origin.digest(context_raw), "originalChain": checked,
            "finalAdmission": final_admission, "finalAdmissionOriginals": final_hashes, "retainedNs": fence.now(final=True),
            **identities, "processIdentity": process_identity,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}, final=True)
    except BaseException as error:
        owner.error("prepare-originals", error)
        if private is not None and not owner.unknown:
            try:
                owner.write(private, "origin-failure.json", {"schema": 1, "result": "HOLD", "errors": owner.errors,
                    "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED"}, final=True)
            except BaseException as secondary:
                owner.error("failure-retention", secondary)
    finally:
        token = None
        try:
            owner.close()
        except BaseException as error:
            owner.error("prepare-close", error)
    if owner.original is not None:
        raise owner.original
    require(result_raw is not None and not owner.unknown, "BOOTSTRAP_ORIGINALS_INCOMPLETE")
    closed = fence.now(final=True)
    cancellation(cancelled)
    handoff = prepare_handoff(path, result_raw, context_raw, identities, process_identity, closed, fence, cancelled)
    return public_result(HANDOFF_OUTPUT_SCOPE, "handoffSha256", handoff), fence, fence.final


def public_result(scope, hash_name, raw):
    # Native lifetimes, paths, runner records and clock observations stay in
    # private files. This digest is provisional until the command/step returns.
    return {"scope": scope, hash_name: origin.digest(raw), "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}


def prepare_handoff(path, result_raw, context_raw, identities, process_identity, closed, fence, cancelled):
    """Retain the real post-original-owner-close floor using a fresh small owner.

    This does NOT observe its own subsequent writer/owner close or step return.
    It only uses the remaining ORIGINAL prelude final fence, never fresh work.
    """
    owner = Owner(fence.deadline(45, final=True), fence)
    raw = None
    try:
        cancellation(cancelled)
        private = owner.open(path, final=True)
        require(private_identities(owner, private) == identities and
                owner.read(private, "origin-result.json", final=True) == result_raw and
                owner.read(private, "context.json", final=True) == context_raw and
                owner.read(private, "prelude.json", final=True) == fence.raw, "BOOTSTRAP_HANDOFF_ORIGINALS_CHANGED")
        raw = owner.write(private, "prepare-handoff.json", {"schema": 1, "scope": HANDOFF_SCOPE,
            "originSha256": origin.digest(result_raw), "contextSha256": origin.digest(context_raw),
            "clock": origin.clock_value(fence.clock), "closedNs": closed, "recordedNs": fence.now(final=True, minimum=closed),
            "processIdentity": process_identity, "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}, final=True)
        require(private_identities(owner, private) == identities, "BOOTSTRAP_HANDOFF_DIRECTORIES_CHANGED")
    except BaseException as error:
        owner.error("prepare-handoff", error)
    finally:
        try:
            owner.close()
        except BaseException as error:
            owner.error("handoff-close", error)
    if owner.original is not None:
        raise owner.original
    require(raw is not None and not owner.unknown, "BOOTSTRAP_HANDOFF_INCOMPLETE")
    posix._deadline(owner.local_end)
    fence.now(final=True)
    cancellation(cancelled)
    return raw


def handoff_record(raw, clock):
    value = origin.parse(raw)
    require(set(value) == HANDOFF_FIELDS and raw == origin.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == HANDOFF_SCOPE and
            value["clock"] == origin.clock_value(clock) and value["budgetAcceptance"] == "NOT_ADMITTED" and
            value["testAcceptance"] == "NOT_PERFORMED" and value["exportSaveAuthority"] is False,
            "BOOTSTRAP_ORIGINAL_HANDOFF")
    for name in ("originSha256", "contextSha256"):
        require(type(value[name]) is str and re.fullmatch(r"[0-9a-f]{64}", value[name]), "BOOTSTRAP_HANDOFF_HASH")
    require(origin.integer(value["closedNs"]) <= origin.integer(value["recordedNs"]), "BOOTSTRAP_HANDOFF_CLOCK")
    closed_lifetime(value["processIdentity"], clock.role)
    return value


def prepared_content(owner, private, handoff_raw, context_raw, fence):
    """Read the original private chain without manufacturing in-call provenance.

    The caller must separately bind a trusted original prepare-step outcome,
    first clock observation, actual hosted inputs and fresh native re-admission.
    This function does not turn disk data into returned owner objects.
    """
    require(owner.fence is fence and owner.first is not None, "BOOTSTRAP_ADOPTION_READER")
    owner.end()
    handoff = handoff_record(handoff_raw, fence.clock)
    require(owner.read(private, "prepare-handoff.json") == handoff_raw and
            owner.read(private, "context.json") == context_raw and
            origin.digest(context_raw) == handoff["contextSha256"] and
            owner.read(private, "prelude.json") == fence.raw, "BOOTSTRAP_ADOPTION_ORIGINALS_CHANGED")
    raw = owner.read(private, "origin-result.json")
    require(origin.digest(raw) == handoff["originSha256"], "BOOTSTRAP_ADOPTION_ORIGIN_CHANGED")
    result = origin.parse(raw)
    require(set(result) == RESULT_FIELDS and raw == origin.encoded(result) and
            type(result["schema"]) is int and result["schema"] == 1 and result["scope"] == RESULT_SCOPE and
            result["contextSha256"] == origin.digest(context_raw) and result["budgetAcceptance"] == "NOT_ADMITTED" and
            result["testAcceptance"] == "NOT_PERFORMED" and result["exportSaveAuthority"] is False and
            type(result["directories"]) is dict and set(result["directories"]) == set(DIRECTORIES),
            "BOOTSTRAP_ADOPTION_PARENT_RESULT")
    identities = {"sessionIdentity": directory_identity(result["sessionIdentity"], fence.clock.role),
        "directories": {name: directory_identity(value, fence.clock.role) for name, value in result["directories"].items()}}
    require(private_identities(owner, private, final=False) == identities, "BOOTSTRAP_ADOPTION_DIRECTORIES_CHANGED")
    admitted_values, returns, hashes = [], [], []
    for name in ("admission", "final-admission"):
        directory = owner.child(private, name)
        admitted = load_admission(owner, directory)
        returned, bound = admission_content(admitted, owner.read(directory, "session-result.json"),
            owner.read(private, name + "-return.json"), fence)
        admitted_values.append(admitted)
        returns.append(returned)
        hashes.append(bound)
    admitted = admitted_values[0]
    require(admitted_values[1] == admitted, "BOOTSTRAP_ADOPTION_FINAL_ADMISSION_CHANGED")
    context = context_record(context_raw, admitted, private.path, fence)
    directory = owner.child(private, "service")
    records = {name: owner.read(directory, name,
        ACK_LIMIT if name == "stdout.log" else STDERR_LIMIT if name == "stderr.log" else LIMIT) for name in sorted(PHASE_FILES)}
    checked = chain_content(owner, private, context_raw, admitted, records, returns[0], hashes[0], fence, final=False)
    terminal = origin.parse(records["result.json"])
    process_identity = closed_lifetime(result["processIdentity"], fence.clock.role)
    require(process_identity == terminal["preparerIdentity"] == handoff["processIdentity"],
            "BOOTSTRAP_ADOPTION_PREPARER_CHANGED")
    original_chain = result["originalChain"]
    require(type(original_chain) is dict, "BOOTSTRAP_ADOPTION_ORIGINAL_CHAIN")
    revalidated = origin.integer(original_chain.get("revalidatedNs"))
    require(origin.encoded(original_chain) == origin.encoded({**checked, "revalidatedNs": revalidated}) and
            origin.encoded(result["finalAdmission"]) == origin.encoded(returns[1]) and
            origin.encoded(result["finalAdmissionOriginals"]) == origin.encoded(hashes[1]),
            "BOOTSTRAP_ADOPTION_ORIGINAL_CHAIN_CHANGED")
    history.adopter_first(history.snapshot(fence), terminal["finalizedNs"], returns[1]["returnedNs"],
        revalidated, result["retainedNs"], handoff["closedNs"], handoff["recordedNs"], owner.first.nanoseconds)
    require(private_identities(owner, private, final=False) == identities, "BOOTSTRAP_ADOPTION_DIRECTORIES_CHANGED")
    return admitted, context, {"handoffSha256": origin.digest(handoff_raw), "originSha256": origin.digest(raw),
        "contextSha256": origin.digest(context_raw), "originalChain": checked,
        "finalAdmissionOriginals": hashes[1], **identities, "processIdentity": process_identity}


def entry_directories(owner, target, private):
    # Equal paths/native identities do not put an unregistered handle inside
    # this owner's close obligation. Already-attempted resources cannot return.
    require(all(any(row["label"] == "directory" and row["owner"] is directory and
                    not row["attempted"] and not row["closed"] for row in owner.resources)
                for directory in (target, private)), "BOOTSTRAP_ENTRY_DIRECTORY_NOT_OWNED")


def same_preparation(current, previous):
    # Read-only revalidation advances only this observation, not any original
    # child/native/service clock, source binding, directory identity or hash.
    require(type(previous) is dict and type(previous.get("originalChain")) is dict,
            "BOOTSTRAP_ENTRY_PREPARATION_FIELDS")
    observed = origin.integer(previous["originalChain"].get("revalidatedNs"))
    return origin.encoded({**current, "originalChain": {**current["originalChain"],
        "revalidatedNs": observed}}) == origin.encoded(previous)


def execution_entry(owner, target, private, handoff_raw, context_raw, admitted, before, fence):
    """Connect original read-only custody to an internal entry context/window.

    The actual returned re-admission must still belong to this owner. The
    original preparation chain is reread here, not supplied by a budget digest.
    This entry is consumed by adoption retention below; it cannot start a
    canonical initializer, producer, seed, provider, or a longer-lived owner.
    """
    require(owner.fence is fence and owner.first is not None and owner.entry_original is None and
            target.path == private.path.with_name(private.path.name + "-adoption"), "BOOTSTRAP_ENTRY_OWNER")
    owner.end()
    entry_directories(owner, target, private)
    returned, hashes = admission_originals(owner, target, admitted, fence, read_final=False)
    again, context, after = prepared_content(owner, private, handoff_raw, context_raw, fence)
    require(again == admitted and same_preparation(after, before),
            "BOOTSTRAP_ADOPTION_CHANGED_DURING_READMISSION")
    value = origin.admitted_value(admitted)
    target.verify()
    target_identity = directory_identity(list(target.identity), fence.clock.role)
    started = fence.now(minimum=after["originalChain"]["revalidatedNs"])
    require(owner.first.nanoseconds <= origin.integer(owner.early_last) <= returned["returnedNs"] <= started,
            "BOOTSTRAP_ENTRY_PREDECESSOR_CLOCK")
    raw = origin.encoded({"schema": 1, "scope": ENTRY_SCOPE, "profile": bootstrap.PROFILE,
        "selection": value["selection"], "cacheCohort": value["cacheCohort"], "source": value["source"],
        "github": value["github"], "root": context["root"], "session": str(target.path),
        "sessionIdentity": target_identity, "preparation": after, "readmission": hashes,
        "prelude": origin.parse(fence.raw), "window": {"scope": ENTRY_WINDOW_SCOPE,
            "clock": origin.clock_value(fence.clock), "adopterFirstNs": owner.first.nanoseconds,
            "metadataLastNs": owner.early_last, "readmissionReturnedNs": returned["returnedNs"],
            "startedNs": started, "workEndNs": fence.work, "finalEndNs": fence.final,
            "localCeiling": "ORIGINAL_ADOPTER_IO45_ONLY_CAN_SHORTEN"},
        "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED",
        "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
    registered = owner.admissions[str(target.path / "admission")]
    entry = OriginalEntry(raw, admitted, str(target.path), registered[1], registered[2],
        handoff_raw, context_raw, origin.encoded(after), owner, fence, private, target)
    owner.entry_original = entry
    check_execution_entry(owner, target, entry, fence, retained=False)
    owner.write(target, "entry-context.json", entry.raw)
    check_execution_entry(owner, target, entry, fence, retained=True)
    return entry


def check_execution_entry(owner, target, entry, fence, *, retained):
    """Use the actual entry's original window; never rehydrate its provenance.

    An equal dataclass or consistent disk record is not this owner's entry.
    Work still uses original75 and the existing local45; original120 is only
    the enclosing finalization ceiling. None is a productive/job allowance.
    """
    require(type(entry) is OriginalEntry and entry._owner is owner and entry._fence is fence and
            owner.entry_original is entry and owner.fence is fence and
            owner.first is not None and str(target.path) == entry.session, "BOOTSTRAP_ENTRY_NOT_CURRENT_RETURN")
    owner.end()
    require(target is entry._target, "BOOTSTRAP_ENTRY_DIRECTORY_NOT_OWNED")
    entry_directories(owner, target, entry._private)
    registered = owner.admissions.get(str(target.path / "admission"))
    require(registered is not None and registered[0] is entry.admitted and
            registered[1:] == (entry.session_original, entry.return_original),
            "BOOTSTRAP_ENTRY_READMISSION_NOT_CURRENT_RETURN")
    returned, hashes = admission_originals(owner, target, entry.admitted, fence, read_final=False)
    value, admitted = origin.parse(entry.raw), origin.admitted_value(entry.admitted)
    require(set(value) == ENTRY_FIELDS and entry.raw == origin.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and type(value["window"]) is dict and
            set(value["window"]) == ENTRY_WINDOW_FIELDS, "BOOTSTRAP_ENTRY_CONTEXT_FIELDS")
    window = value["window"]
    require(value["profile"] == bootstrap.PROFILE and value["scope"] == ENTRY_SCOPE and value["root"] == str(ROOT) and
            value["selection"] == admitted["selection"] and value["cacheCohort"] == admitted["cacheCohort"] and
            value["source"] == admitted["source"] and value["github"] == admitted["github"] and
            value["session"] == entry.session and value["readmission"] == hashes and
            value["prelude"] == origin.parse(fence.raw) and window["scope"] == ENTRY_WINDOW_SCOPE and
            window["clock"] == origin.clock_value(fence.clock) and
            window["adopterFirstNs"] == owner.first.nanoseconds and window["metadataLastNs"] == owner.early_last and
            window["readmissionReturnedNs"] == returned["returnedNs"] and
            window["workEndNs"] == fence.work and window["finalEndNs"] == fence.final and
            window["localCeiling"] == "ORIGINAL_ADOPTER_IO45_ONLY_CAN_SHORTEN" and
            value["retirement"] == "PENDING_OWNER_CLOSE" and
            value["budgetAcceptance"] == "NOT_ADMITTED" and value["testAcceptance"] == "NOT_PERFORMED" and
            value["exportSaveAuthority"] is False, "BOOTSTRAP_ENTRY_CONTEXT_CHANGED")
    again, _, after = prepared_content(owner, entry._private, entry.handoff_original, entry.context_original, fence)
    require(again == entry.admitted and origin.encoded(value["preparation"]) == entry.preparation_original and
            same_preparation(after, value["preparation"]), "BOOTSTRAP_ENTRY_PREPARATION_CHANGED")
    times = [window[name] for name in ("adopterFirstNs", "metadataLastNs", "readmissionReturnedNs", "startedNs")]
    require(all(type(number) is int for number in times) and times == sorted(times) and
            fence.first <= times[0] <= times[-1] < fence.work and times[2] <=
            origin.integer(value["preparation"]["originalChain"]["revalidatedNs"]) <= times[-1],
            "BOOTSTRAP_ENTRY_PREDECESSOR_CLOCK")
    target.verify()
    require(directory_identity(list(target.identity), fence.clock.role) == value["sessionIdentity"],
            "BOOTSTRAP_ENTRY_DIRECTORY_CHANGED")
    fence.now(minimum=origin.integer(window["startedNs"]), limit=window["workEndNs"])
    if retained:
        require(owner.read(target, "entry-context.json") == entry.raw, "BOOTSTRAP_ENTRY_ORIGINAL_CHANGED")
    entry_directories(owner, target, entry._private)
    owner.end()
    return value


def _entry_close_limits(owner, fence):
    # Local float seconds and shared integer nanoseconds are different domains.
    # Neither is reconstructed or renewed by the close transition.
    return (owner.local_end, fence.raw, fence.clock, fence.first, fence.work, fence.final,
            owner.work_limit, owner.final_limit, owner.first, owner.early_last)


def _entry_close_bindings(owner, fence, limits, callbacks):
    current = _entry_close_limits(owner, fence)
    require(owner.fence is fence and len(current) == len(limits) and
            all(type(left) is type(right) and left == right for left, right in zip(current, limits)) and
            owner.cancelled is callbacks[0] and fence.cancelled is callbacks[1], "BOOTSTRAP_ENTRY_CLOSE_LIMITS_CHANGED")


def _entry_close_snapshot(owner):
    require(type(owner.resources) is list and bool(owner.resources), "BOOTSTRAP_ENTRY_CLOSE_ROSTER")
    require(all(type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                row["label"] in ("directory", "writer") and type(row["attempted"]) is bool and
                type(row["closed"]) is bool and (not row["closed"] or row["attempted"])
                for row in owner.resources), "BOOTSTRAP_ENTRY_CLOSE_ROSTER")
    return (owner.resources, tuple((row, row["label"], row["owner"]) for row in owner.resources))


def _entry_close_known(owner, snapshot):
    require(type(snapshot) is tuple and len(snapshot) == 2 and owner.closed is True and
            owner.resources is snapshot[0] and type(snapshot[1]) is tuple and bool(snapshot[1]) and
            len(owner.resources) == len(snapshot[1]), "BOOTSTRAP_ENTRY_CLOSE_ROSTER")
    for current, (row, label, resource) in zip(owner.resources, snapshot[1]):
        require(current is row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                row["label"] == label and row["owner"] is resource and
                row["attempted"] is True and row["closed"] is True, "BOOTSTRAP_ENTRY_CLOSE_ROSTER")


def _entry_close_preserve_uncertainty(owner, snapshot):
    # A completed close is idempotent; it cannot quarantine later discoveries.
    # Keep the actual captured rows/owners, even if their mutable registry changed.
    try:
        require(owner.entry_close_snapshot is snapshot, "BOOTSTRAP_ENTRY_CLOSE_ROSTER")
        _entry_close_known(owner, snapshot)
    except BaseException as error:
        owner.error("entry-close-roster-return", error, unknown=True)
    if owner.unknown:
        owner.entry_close_snapshot = snapshot
        if not any(value is owner for value in QUARANTINE):
            QUARANTINE.append(owner)


def _entry_close_proposal(entry, responses):
    require(type(responses) is tuple and len(responses) == 2 and
            all(type(row) is tuple and len(row) == 2 and type(row[1]) is bytes for row in responses) and
            tuple(row[0] for row in responses) == ("attempt", "jobs"), "BOOTSTRAP_ENTRY_CLOSE_RESPONSES")
    value, context = origin.parse(entry.raw), origin.parse(entry.context_original)
    basis = value["preparation"]["originalChain"]["serviceTimeBasis"]
    proposal = allocation.derive(entry.admitted, dict(responses), basis["invocation"], entry._fence.clock,
                                 context["runnerName"])
    require(origin.encoded(proposal["serviceTimeBasis"]) == origin.encoded(basis),
            "BOOTSTRAP_ENTRY_CLOSE_BASIS_CHANGED")
    return proposal


def _entry_close_pending(entry, proposal, retained_ns):
    return {"schema": 1, "scope": ENTRY_CLOSE_PENDING_SCOPE, "entryContextSha256": origin.digest(entry.raw),
            "proposal": proposal, "retainedNs": retained_ns, "oldOwnerRetirement": "PENDING_CLOSE",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}


def _entry_close_record(entry, pending, proposal, preclose_ns, closed_ns, count):
    return {"schema": 1, "scope": ENTRY_CLOSE_SCOPE, "entryContextSha256": origin.digest(entry.raw),
            "pendingSha256": origin.digest(pending), "proposalSha256": origin.digest(proposal),
            "clock": origin.clock_value(entry._fence.clock), "preCloseNs": preclose_ns, "closedNs": closed_ns,
            "resourceCount": count, "oldOwnerRetirement": "KNOWN_RESOURCE_CLOSE_ONLY",
            "productiveOwner": "NOT_CREATED", "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}


def _entry_close_state(transition):
    owner, fence, entry = transition._owner, transition._fence, transition._entry
    _entry_close_known(owner, transition._snapshot)
    require(owner.entry_close_attempted is True and owner.entry_original is entry and
            entry._owner is owner and entry._fence is fence and owner.entry_close_snapshot is transition._snapshot and
            owner.original is None and owner.errors == [] and owner.unknown is False,
            "BOOTSTRAP_ENTRY_CLOSE_NOT_SUCCESSFUL")
    _entry_close_bindings(owner, fence, transition._limits, transition._callbacks)


def _entry_close_content(transition):
    _entry_close_state(transition)
    owner, fence, entry = transition._owner, transition._fence, transition._entry
    proposal = _entry_close_proposal(entry, transition.responses)
    require(transition.proposal_raw == origin.encoded(proposal) and transition.pending_raw ==
            origin.encoded(_entry_close_pending(entry, proposal, transition._retained_ns)),
            "BOOTSTRAP_ENTRY_CLOSE_ORIGINAL_CHANGED")
    window = origin.parse(entry.raw)["window"]
    times = (window["startedNs"], transition._retained_ns, transition._preclose_ns,
             transition._closed_ns, transition._checked_ns)
    require(all(type(value) is int and 0 <= value <= origin.clocks.UINT64 for value in times) and
            list(times) == sorted(times) and transition._preclose_ns < window["workEndNs"] and
            transition._checked_ns < window["finalEndNs"] and fence.last == transition._checked_ns,
            "BOOTSTRAP_ENTRY_CLOSE_CLOCK")
    value = _entry_close_record(entry, transition.pending_raw, transition.proposal_raw,
                               transition._preclose_ns, transition._closed_ns, len(transition._snapshot[1]))
    require(type(transition.raw) is bytes and transition.raw == origin.encoded(value),
            "BOOTSTRAP_ENTRY_CLOSE_RETURN_CHANGED")
    return value


def check_closed_entry_transition(transition):
    """Non-acquiring consistency of this exact returned object, not a live gate.

    Repeated validation gives no productive/single-use authority. It observes
    no current source, filesystem, native clock or workflow outcome. A future
    distinct owner must re-admit/re-read those, and carry the original job fence
    plus this object's final observed _checked_ns, not only its earlier raw file.
    """
    require(type(transition) is ClosedEntryTransition and type(transition._owner) is Owner and
            transition._owner.entry_close_original is transition, "BOOTSTRAP_ENTRY_CLOSE_NOT_CURRENT_RETURN")
    return _entry_close_content(transition)


def close_entry_transition(owner, target, entry, fence):
    """Dormant INTERNAL old-owner close bridge; no public operation calls it.

    Rejected foreign arguments leave cleanup with their original caller. Once
    this exact live owner claims the one-shot transition, all failures preserve
    the first error and attempt known cleanup once. No old owner is prolonged,
    no live handle is transferred, and no productive owner/budget is created.
    """
    # Non-I/O provenance gate BEFORE claiming cleanup or invoking any supplier.
    require(type(owner) is Owner and type(entry) is OriginalEntry and type(fence) is origin.Fence and
            entry._owner is owner and entry._fence is fence and owner.fence is fence and
            owner.entry_original is entry and target is entry._target and owner.first is not None and
            owner.closed is False and owner.phase_originals is None and owner.entry_close_attempted is False and
            owner.entry_close_original is None and owner.entry_close_snapshot is None,
            "BOOTSTRAP_ENTRY_CLOSE_NOT_CURRENT_ENTRY")
    registered = owner.admissions.get(str(target.path / "admission"))
    require(type(registered) is tuple and len(registered) == 3 and registered[0] is entry.admitted and
            registered[1:] == (entry.session_original, entry.return_original),
            "BOOTSTRAP_ENTRY_CLOSE_NOT_CURRENT_ADMISSION")
    entry_directories(owner, target, entry._private)
    limits, callbacks = _entry_close_limits(owner, fence), (owner.cancelled, fence.cancelled)
    owner.entry_close_attempted = True
    pending_raw = proposal_raw = responses = retained_ns = preclose_ns = None
    try:
        check_execution_entry(owner, target, entry, fence, retained=True)
        directory = owner.child(entry._private, "service")
        responses = tuple((name, owner.read(directory, name + ".json")) for name in ("attempt", "jobs"))
        proposal = _entry_close_proposal(entry, responses)
        proposal_raw = origin.encoded(proposal)
        retained_ns = fence.now()
        pending_raw = owner.write(target, "entry-close-pending.json", _entry_close_pending(entry, proposal, retained_ns))
        check_execution_entry(owner, target, entry, fence, retained=True)
        require(owner.read(target, "entry-close-pending.json") == pending_raw,
                "BOOTSTRAP_ENTRY_CLOSE_PENDING_CHANGED")
        _entry_close_bindings(owner, fence, limits, callbacks)
        for callback in callbacks:
            callback()
        owner.end()
        _entry_close_bindings(owner, fence, limits, callbacks)
        preclose_ns = fence.last
    except BaseException as error:
        owner.error("entry-close-prepare", error)
        if not owner.unknown:
            try:
                # Failure retention is still new I/O. A rejected/expired frame
                # cannot grant it time; cancellation itself need not erase the
                # first failure's original, still-bounded custody opportunity.
                _entry_close_bindings(owner, fence, limits, callbacks)
                posix._deadline(limits[0])
                fence.now(final=True, limit=limits[5])
                _entry_close_bindings(owner, fence, limits, callbacks)
                owner.write(target, "entry-close-failure.json", {"schema": 1, "result": "HOLD", "errors": owner.errors,
                    "oldOwnerRetirement": "PENDING_CLOSE", "budgetAcceptance": "NOT_ADMITTED"}, final=True)
            except BaseException as secondary:
                owner.error("entry-close-failure-retention", secondary)
    finally:
        # Final revalidation and failure retention may add directory/writer rows.
        # The earlier private file cannot claim this later roster or its close.
        try:
            snapshot = _entry_close_snapshot(owner)
        except BaseException as error:
            # Even an invalid list retains immutable references to its rows.
            snapshot = (owner.resources, tuple(owner.resources) if type(owner.resources) is list else ())
            owner.error("entry-close-snapshot", error, unknown=True)
        owner.entry_close_snapshot = snapshot
        try:
            owner.close()
        except BaseException as error:
            owner.error("entry-close-return", error)
    _entry_close_preserve_uncertainty(owner, snapshot)
    if owner.original is not None:
        raise owner.original
    try:
        require(pending_raw is not None and preclose_ns is not None and owner.errors == [] and not owner.unknown,
                "BOOTSTRAP_ENTRY_CLOSE_INCOMPLETE")
        _entry_close_bindings(owner, fence, limits, callbacks)
        for callback in callbacks:
            callback()
        posix._deadline(limits[0])
        closed_ns = fence.now(final=True, minimum=preclose_ns, limit=limits[5])
        raw = origin.encoded(_entry_close_record(entry, pending_raw, proposal_raw,
                                                preclose_ns, closed_ns, len(snapshot[1])))
        arguments = dict(raw=raw, pending_raw=pending_raw, proposal_raw=proposal_raw, responses=responses,
            _entry=entry, _owner=owner, _fence=fence, _limits=limits, _callbacks=callbacks,
            _snapshot=snapshot, _retained_ns=retained_ns, _preclose_ns=preclose_ns,
            _closed_ns=closed_ns, _checked_ns=closed_ns)
        _entry_close_content(ClosedEntryTransition(**arguments))
        # Preserve the latest post-validation clock in the actual returned object.
        # No registered object or post-close file can escape before these checks.
        for callback in callbacks:
            callback()
        posix._deadline(limits[0])
        checked_ns = fence.now(final=True, minimum=closed_ns, limit=limits[5])
        _entry_close_bindings(owner, fence, limits, callbacks)
        for callback in callbacks:
            callback()
        posix._deadline(limits[0])
        result = ClosedEntryTransition(**{**arguments, "_checked_ns": checked_ns})
        # All final callbacks/clock suppliers have now returned. Recheck only
        # in-memory state here; no file acquisition or new clock allowance.
        _entry_close_state(result)
        require(owner.entry_close_original is None and fence.last == checked_ns,
                "BOOTSTRAP_ENTRY_CLOSE_FINAL_STATE_CHANGED")
        owner.entry_close_original = result
        return result
    except BaseException as error:
        owner.error("entry-close-postreturn", error)
        _entry_close_preserve_uncertainty(owner, snapshot)
        raise owner.original


def adopt_originals(cancelled):
    """Dormant read-only ORIGINAL adoption, not producer or job-budget admission.

    The two environment inputs must eventually come from the fixed trusted
    prepare step's ORIGINAL outcome/hash. No workflow wires that authority yet.
    Fresh readmission records go in a separate exclusive sibling; preparation
    originals are never modified. Every operation shares the original prelude.
    """
    local_end = time.monotonic() + 45
    first = origin.clocks.validate_reading(origin.clocks.observe())
    owner = Owner(local_end, first=first, cancelled=lambda: cancellation(cancelled))
    fence = target = result_raw = None
    try:
        require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE, "BOOTSTRAP_PRIOR_UNKNOWN")
        require(origin.wire.TOKEN_ENV not in os.environ, "BOOTSTRAP_ADOPTION_TOKEN_FORBIDDEN")
        require(os.environ.get(PREPARE_OUTCOME_ENV) == "success", "BOOTSTRAP_PREPARE_ORIGINAL_OUTCOME")
        expected_hash = os.environ.get(PREPARE_HASH_ENV)
        require(type(expected_hash) is str and re.fullmatch(r"[0-9a-f]{64}", expected_hash), "BOOTSTRAP_PREPARE_ORIGINAL_HASH")
        owner.end()
        selection, path, event = host_inputs(first.clock.role)
        inherited = query._inherited_context()
        child_environment(path)  # Same execution-override refusal; never forwards the prepare inputs.
        owner.end()
        private = owner.open(path)
        handoff_raw = owner.read(private, "prepare-handoff.json")
        require(origin.digest(handoff_raw) == expected_hash, "BOOTSTRAP_PREPARE_ORIGINAL_HASH_CHANGED")
        handoff = handoff_record(handoff_raw, first.clock)
        # Never replace the earliest observation with a later recovered clock.
        require(first.nanoseconds >= handoff["recordedNs"], "BOOTSTRAP_ADOPTER_PRECEDES_HANDOFF")
        # Conservative same-PID refusal is not a native liveness/retirement proof.
        require(os.getpid() != handoff["processIdentity"]["pid"], "BOOTSTRAP_ADOPTER_SAME_PROCESS")
        context_raw = owner.read(private, "context.json")
        prelude_raw = owner.read(private, "prelude.json")
        fence = origin.Fence(origin.parse(prelude_raw), minimum=first.nanoseconds, cancelled=lambda: cancellation(cancelled))
        require(first.clock == fence.clock and prelude_raw == fence.raw, "BOOTSTRAP_ADOPTION_CLOCK_CHANGED")
        owner.bind(fence, work_limit=fence.work, final_limit=fence.final)
        admitted, context, before = prepared_content(owner, private, handoff_raw, context_raw, fence)
        require(context["selection"] == selection and admitted.original_event == event and
                context["runnerName"] == os.environ.get("RUNNER_NAME") and context["inheritedContext"] == inherited,
                "BOOTSTRAP_ADOPTION_HOST_INPUTS_CHANGED")
        target = owner.new(path.with_name(path.name + "-adoption"))
        # Actual native/source/main/policy re-admission is WORK, not a finalizer.
        current, returned = admit(owner, fence, target.path / "admission", expected=admitted)
        owner.write(target, "admission-return.json", returned)
        entry = execution_entry(owner, target, private, handoff_raw, context_raw, current, before, fence)
        entry_value = check_execution_entry(owner, target, entry, fence, retained=True)
        window = entry_value["window"]
        result_raw = owner.write(target, "adoption-result.json", {"schema": 2, "scope": ADOPTION_SCOPE,
            "prepareOutcome": "success", "entryContextSha256": origin.digest(entry.raw),
            "originals": entry_value["preparation"], "prelude": entry_value["prelude"],
            "clock": window["clock"], "beganNs": window["adopterFirstNs"], "metadataLastNs": window["metadataLastNs"],
            "readmission": entry_value["readmission"], "readmissionReturnedNs": window["readmissionReturnedNs"],
            "retainedNs": fence.now(minimum=window["startedNs"], limit=window["workEndNs"]),
            "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False})
        check_execution_entry(owner, target, entry, fence, retained=True)
    except BaseException as error:
        owner.error("adopt-originals", error)
        if target is not None and not owner.unknown:
            try:
                owner.write(target, "adoption-failure.json", {"schema": 1, "result": "HOLD", "errors": owner.errors,
                    "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED"}, final=True)
            except BaseException as secondary:
                owner.error("adoption-failure-retention", secondary)
    finally:
        try:
            owner.close()
        except BaseException as error:
            owner.error("adoption-close", error)
    if owner.original is not None:
        raise owner.original
    require(result_raw is not None and not owner.unknown and fence is not None, "BOOTSTRAP_ADOPTION_INCOMPLETE")
    posix._deadline(owner.local_end)
    fence.now(final=True)
    cancellation(cancelled)
    return public_result(ADOPTION_SCOPE, "adoptionSha256", result_raw), fence, fence.final


def guarded(operation):
    handlers, cancelled, original, result = {}, [], None, None
    try:
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handlers[number] = signal.getsignal(number)
            signal.signal(number, lambda signum, _frame: cancelled.append(signum))
        result = operation(cancelled)
        cancellation(cancelled)
    except BaseException as error:
        original = error
    finally:
        for number, handler in handlers.items():
            try:
                signal.signal(number, handler)
            except BaseException as error:
                original = original or error
    if original is not None:
        raise original
    value, fence, limit = result
    cancellation(cancelled)
    observed = fence.now(final=True, limit=limit)
    if value.get("scope") == ACK_SCOPE:
        value["closedNs"] = observed
    raw = origin.encoded(value)
    require(len(raw) <= ACK_LIMIT and sys.stdout.buffer.write(raw) == len(raw), "BOOTSTRAP_ACK_WRITE")
    sys.stdout.buffer.flush()
    # Output is provisional until this actual process returns success. A late
    # flush/clock/cancellation still fails even when all digest bytes escaped.
    fence.now(final=True, limit=limit)
    cancellation(cancelled)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("prepare-originals")
    commands.add_parser("adopt-originals")
    child = commands.add_parser("_service")
    child.add_argument("--context-sha256", required=True)
    child.add_argument("--minimum-ns", required=True)
    args = parser.parse_args()
    try:
        require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
                "BOOTSTRAP_ISOLATED_INTERPRETER_REQUIRED")
        if args.operation == "prepare-originals":
            guarded(prepare_originals)
        elif args.operation == "adopt-originals":
            guarded(adopt_originals)
        else:
            require(re.fullmatch(r"0|[1-9][0-9]{0,19}", args.minimum_ns), "BOOTSTRAP_LAUNCH_MINIMUM")
            minimum = origin.integer(int(args.minimum_ns))
            command(args.context_sha256, minimum)
            guarded(lambda cancelled: service_child(args.context_sha256, minimum, cancelled))
        return 0
    except BaseException:
        # No exception/argv/path/response/token is suitable for public logs.
        print("CACHE_BOOTSTRAP_ORIGINALS_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
