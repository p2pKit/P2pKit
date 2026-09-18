#!/usr/bin/env python3
"""Dormant bootstrap originals, recipient and initializer; NOT a cache builder.

No workflow, productive budget, producer, seed/export/save,
policy installer or uploader exists here. Separate read-only original adoption
never becomes execution authority. A future trusted workflow must bind the
actual original prepare-step outcome, not a provisional receipt/digest.
The internal recipient/initializer parents own native launch/retirement/readback;
no public operation or workflow calls it. Offline controls are not native,
custodian, scheduling or encrypted-custody qualification.
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
import threading
import time
import uuid

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import audit_processes as processes
import hosted_cache_bootstrap_allocation as allocation
import hosted_cache_bootstrap_canonical as canonical
import hosted_cache_bootstrap_history as history
import hosted_cache_bootstrap_identity as bootstrap
import hosted_cache_bootstrap_initialization as initialization
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
NEW_ENTRY_SCOPE = "BOOTSTRAP_NEW_ENTRY_READMISSION_CLOSED_NO_EXECUTION_V1"
NEW_ENTRY_PENDING_SCOPE = "BOOTSTRAP_NEW_ENTRY_READMISSION_PENDING_CLOSE_V1"
NEW_ENTRY_WINDOW_SCOPE = "BOOTSTRAP_NEW_ENTRY_SOURCE_CAP_NOT_JOB_ADMISSION_V1"
_ENTRY_CLAIM_LOCK = threading.Lock()
_ENTRY_ATTEMPTS = {}
RECIPIENT_CONTEXT_SCOPE = "BOOTSTRAP_RECIPIENT_CHILD_CONTEXT_V1"
RECIPIENT_START_SCOPE = "BOOTSTRAP_RECIPIENT_PARENT_PRELAUNCH_V1"
RECIPIENT_SCOPE = "BOOTSTRAP_RECIPIENT_SUPPLIER_RETURN_PENDING_CHILD_CLOSE_V1"
RECIPIENT_ACK_SCOPE = "BOOTSTRAP_RECIPIENT_CHILD_POST_CLOSE_ACK_V1"
RECIPIENT_DIRECTORIES = ("recipient-validation", "crypto", "control-home", "temporary")
RECIPIENT_CONTEXT_FIELDS = {"schema", "scope", "profile", "selection", "cacheCohort", "source", "github",
    "root", "session", "originalSession", "originalContextSha256", "admissionSha256", "proposalSha256",
    "clock", "job", "inheritedContext", "runnerName", "previousTransitionSha256", "previousCheckedNs",
    "directories", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"}
RECIPIENT_PREFIX_SCOPE = "BOOTSTRAP_RECIPIENT_PREFIX_CLOSED_NO_EXECUTION_V1"
_RECIPIENT_CLAIM_LOCK = threading.Lock()
_RECIPIENT_ATTEMPTS = {}
_INITIALIZER_CLAIM_LOCK = threading.Lock()
_INITIALIZER_ATTEMPTS = {}
_PARENT_CONTROLS = {}


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


@dataclass(eq=False)
class _EntryAttempt:
    """Strong, once-claimed in-call references, including unsuccessful attempts."""
    transition: object = field(repr=False)
    originals: tuple = field(repr=False)
    state: str = "CLAIMED"
    first: object = field(default=None, repr=False)
    window: object = field(default=None, repr=False)
    owner: object = field(default=None, repr=False)
    callback: object = field(default=None, repr=False)
    bindings: object = field(default=None, repr=False)
    local_start: object = field(default=None, repr=False)
    local_end: object = field(default=None, repr=False)
    target: object = field(default=None, repr=False)
    private: object = field(default=None, repr=False)
    previous_target: object = field(default=None, repr=False)
    admitted: object = field(default=None, repr=False)
    returned: object = field(default=None, repr=False)
    admission_originals: object = field(default=None, repr=False)
    preparation: object = field(default=None, repr=False)
    target_identity: object = field(default=None, repr=False)
    retained_ns: object = field(default=None, repr=False)
    pending_raw: object = field(default=None, repr=False)
    failure_raw: object = field(default=None, repr=False)
    resources: tuple = field(default=(), repr=False)
    snapshot: object = field(default=None, repr=False)
    original: object = field(default=None, repr=False)
    errors: list = field(default_factory=list, repr=False)
    unknown: bool = False
    failure_custody: str = "UNAVAILABLE"
    result: object = field(default=None, repr=False)


@dataclass(frozen=True)
class NewEntryTransition:
    """Returned new-entry resource close only, NOT producer or job admission."""
    raw: bytes = field(repr=False)
    _attempt: object = field(repr=False, compare=False)
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


@dataclass(frozen=True)
class _LegacyOriginalReader:
    """View of the EXISTING original reader, not another owner or admission.

    Historical data and the original adopter's first reading are derived here,
    never caller-selected. Only the old Owner/origin.Fence pair is supported.
    A future productive reader needs its separate one-shot transaction; this
    constructor cannot accept a job clock or recreate an expired original.
    Outer phase/entry/hosted-outcome provenance checks are still indispensable.
    """
    owner: object = field(repr=False, compare=False)
    current: object = field(repr=False, compare=False)
    past: object = field(init=False, repr=False)
    first: object = field(init=False, repr=False)

    def __post_init__(self):
        require(type(self.owner) is Owner and type(self.current) is origin.Fence and
                self.owner.fence is self.current, "BOOTSTRAP_LEGACY_READER_OWNER")
        object.__setattr__(self, "past", history.snapshot(self.current))
        object.__setattr__(self, "first", self.owner.first)

    def checked(self):
        require(type(self) is _LegacyOriginalReader and type(self.owner) is Owner and
                type(self.current) is origin.Fence and self.owner.fence is self.current and
                self.owner.first is self.first, "BOOTSTRAP_LEGACY_READER_CHANGED")
        require(history.checked(self.past) == history.snapshot(self.current),
                "BOOTSTRAP_LEGACY_READER_HISTORY_CHANGED")
        return self

    def observe(self, *, final, minimum):
        self.checked()
        require(self.owner.closed is False and self.owner.unknown is False and
                (final or self.owner.original is None), "BOOTSTRAP_LEGACY_READER_NOT_LIVE")
        # Keep this actual observation at the old call site. Data validation
        # cannot replace it or transfer any local/current high-water to history.
        return self.current.now(final=final, minimum=minimum)


@dataclass(frozen=True)
class _NewEntryWindow:
    """Only this claimed entry's inclusive120/75+45 cap; no job authority.

    This is deliberately NOT origin.Fence and contains no reissued prelude.
    The fixed work/final fields also constrain the existing native admit()
    supplier itself, not merely the outer Owner's I/O or cancellation callback.
    """
    attempt: object = field(repr=False, compare=False)
    clock: object = field(init=False, repr=False)
    first: int = field(init=False, repr=False)
    work: int = field(init=False, repr=False)
    final: int = field(init=False, repr=False)
    phase_end: int = field(init=False, repr=False)
    last: int = field(init=False, repr=False, compare=False)
    cancelled: object = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        _entry_claim_identity(self.attempt)
        require(self.attempt.state == "CLAIMED" and self.attempt.window is None,
                "BOOTSTRAP_NEW_ENTRY_WINDOW_ALREADY_CREATED")
        clock, first, work, final, phase_end = _new_entry_limits(self.attempt)
        for name, value in (("clock", clock), ("first", first), ("work", work),
                             ("final", final), ("phase_end", phase_end), ("last", first)):
            object.__setattr__(self, name, value)
        require(callable(self.attempt.callback), "BOOTSTRAP_NEW_ENTRY_CALLBACK")
        object.__setattr__(self, "cancelled", self.attempt.callback)

    def checked(self):
        _entry_claim_identity(self.attempt)
        require(type(self) is _NewEntryWindow and self.attempt.window is self and
                self.attempt.state in ("CLAIMED", "READING", "CLOSING", "COMPLETE", "FAILED"),
                "BOOTSTRAP_NEW_ENTRY_WINDOW_NOT_CURRENT")
        expected = _new_entry_limits(self.attempt)
        actual = (self.clock, self.first, self.work, self.final, self.phase_end)
        require(all(type(a) is type(b) and a == b for a, b in zip(actual, expected)) and
                origin.integer(self.last, self.first) == self.last and self.cancelled is self.attempt.callback,
                "BOOTSTRAP_NEW_ENTRY_WINDOW_CHANGED")
        owner = self.attempt.owner
        if owner is not None:
            _new_entry_roster(self.attempt)
            require(type(owner) is Owner and owner is not self.attempt.transition._owner and
                    owner.fence is self and owner.first is self.attempt.first and
                    type(owner.local_end) is float and owner.local_end == self.attempt.local_end and
                    owner.work_limit is None and owner.final_limit is None and
                    owner.cancelled is self.cancelled and
                    owner.early_last == self.first and type(self.attempt.bindings) is tuple and
                    len(self.attempt.bindings) == 8 and
                    all(a is b for a, b in zip((owner, self, self.attempt.first, self.cancelled),
                                               self.attempt.bindings[:4])) and
                    owner.local_end == self.attempt.bindings[4] and
                    all(a is b for a, b in zip((owner.admissions, owner.resources, owner.errors),
                                               self.attempt.bindings[5:])), "BOOTSTRAP_NEW_ENTRY_OWNER_CHANGED")
        return self

    def now(self, *, final=False, minimum=0, limit=None):
        self.checked()
        require(type(final) is bool and self.attempt.state not in ("COMPLETE", "FAILED"),
                "BOOTSTRAP_NEW_ENTRY_NOT_LIVE")
        now = origin.clocks.checked_now(self.clock, minimum_ns=max(self.last, origin.integer(minimum)))
        # Keep the actual observation BEFORE expiry, cancellation or conversion.
        object.__setattr__(self, "last", now)
        ceiling = self.final if final else self.work
        if limit is not None:
            ceiling = min(ceiling, origin.integer(limit))
        require(now < ceiling, "BOOTSTRAP_NEW_ENTRY_FENCE_EXPIRED")
        if not final:
            self.cancelled()
        self.checked()
        require(self.last == now, "BOOTSTRAP_NEW_ENTRY_HIGHWATER_CHANGED")
        return now

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(maximum) in (int, float), "BOOTSTRAP_OPERATION_MAXIMUM")
        try:
            maximum = float(maximum)
        except (ValueError, OverflowError):
            raise origin.OriginError("BOOTSTRAP_OPERATION_MAXIMUM") from None
        require(math.isfinite(maximum) and maximum > 0, "BOOTSTRAP_OPERATION_MAXIMUM")
        # Owner.acquire registered any just-returned resource before end().
        # Capture it before even the LOCAL clock supplier can fail or mutate.
        self.checked()
        local = time.monotonic()
        now = self.now(final=final, limit=limit)
        ceiling = self.final if final else self.work
        if limit is not None:
            ceiling = min(ceiling, origin.integer(limit))
        result = origin.wire._directed_deadline(local, maximum, ceiling, now)
        self.checked()
        require(self.last == now, "BOOTSTRAP_NEW_ENTRY_HIGHWATER_CHANGED")
        return result

    def record(self):
        self.checked()
        return {"scope": NEW_ENTRY_WINDOW_SCOPE, "clock": origin.clock_value(self.clock),
                "firstNs": self.first, "workEndNs": self.work, "finalEndNs": self.final,
                "originalPhaseEndNs": self.phase_end, "maximumSeconds": 120,
                "newWorkSeconds": 75, "reservedCleanupSeconds": 45,
                "budgetAcceptance": "NOT_ADMITTED"}


@dataclass(frozen=True)
class _NewEntryOriginalReader:
    """Only the exact in-progress claim can view originals under its NEW owner."""
    attempt: object = field(repr=False, compare=False)
    owner: object = field(init=False, repr=False, compare=False)
    current: object = field(init=False, repr=False, compare=False)
    past: object = field(init=False, repr=False)
    first: object = field(init=False, repr=False)

    def __post_init__(self):
        _new_entry_live(self.attempt)
        transition = self.attempt.transition
        for name, value in (("owner", self.attempt.owner), ("current", self.attempt.window),
                             ("past", history.snapshot(transition._fence)),
                             ("first", transition._owner.first)):
            object.__setattr__(self, name, value)

    def checked(self):
        _new_entry_live(self.attempt)
        transition = self.attempt.transition
        require(type(self) is _NewEntryOriginalReader and self.owner is self.attempt.owner and
                self.current is self.attempt.window and self.first is transition._limits[8] and
                self.first is transition._owner.first and self.first is not self.owner.first and
                history.checked(self.past) == history.snapshot(transition._fence),
                "BOOTSTRAP_NEW_ENTRY_READER_CHANGED")
        self.current.checked()
        return self

    def observe(self, *, final, minimum):
        self.checked()
        return self.current.now(final=final, minimum=minimum)


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
    return _context_history_record(raw, admitted, path, history.snapshot(fence))


def _context_history_record(raw, admitted, path, past):
    """Source-owned historical record grammar; no current reader or admission."""
    past = history.checked(past)
    value = origin.parse(raw)
    record = origin.admitted_value(admitted)
    require(set(value) == CONTEXT_FIELDS and raw == origin.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == CONTEXT_SCOPE and
            value["prelude"] == origin.parse(past.raw) and value["selection"] == record["selection"] and
            value["cacheCohort"] == record["cacheCohort"] and value["source"] == record["source"] and
            value["github"] == record["github"] and record["cacheCohort"]["role"] == past.clock.role and
            value["root"] == str(ROOT) and value["session"] == str(path) and
            value["admissionSha256"] == origin.digest(admitted.record) and
            value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False,
            "BOOTSTRAP_ORIGINAL_CONTEXT")
    require(type(value["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["job"]) and
            type(value["runnerName"]) is str and 0 < len(value["runnerName"]) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in value["runnerName"]) and
            type(value["admissionReturnSha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["admissionReturnSha256"]),
            "BOOTSTRAP_ORIGINAL_CONTEXT_IDENTITIES")
    history.context_return(past, value["admissionReturnedNs"])
    inherited = value["inheritedContext"]
    require(type(inherited) is dict and set(inherited).issubset(query._CONTEXT) and
            all(type(item) is str for item in inherited.values()) and
            (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(query._CONTEXT)),
            "BOOTSTRAP_ORIGINAL_PARENT_CONTEXT")
    return value


def start_record(raw, context_raw, context, path, fence):
    return _start_history_record(raw, context_raw, context, path, history.snapshot(fence))


def _start_history_record(raw, context_raw, context, path, past):
    """Historical start plus actual SOURCE-owned command resolution, not argv injection."""
    past = history.checked(past)
    start = origin.parse(raw)
    require(set(start) == START_FIELDS and raw == origin.encoded(start) and
            type(start["schema"]) is int and start["schema"] == 1 and start["scope"] == PHASE_SCOPE and
            start["contextSha256"] == origin.digest(context_raw) and start["argv"] == command(origin.digest(context_raw)) and
            start["cwd"] == str(ROOT) and start["role"] == past.clock.role and start["job"] == context["job"] and
            start["state"] == str(path) and start["home"] == str(path / "control-home") and
            start["exitCode"] is None and start["launchAttempted"] is False and start["scopeAttempted"] is False and
            start["retirement"] == "UNKNOWN" and type(start["invocation"]) is str and
            re.fullmatch(r"[0-9a-f]{32}", start["invocation"]), "BOOTSTRAP_ORIGINAL_PRELAUNCH")
    history.phase_start(past, context["admissionReturnedNs"], start)
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
    return _admission_history_content(admitted, session, returned, history.snapshot(fence))


def _admission_history_content(admitted, session, returned, past):
    """Old query originals remain inside original75, not a fresh admission window."""
    past = history.checked(past)
    value = origin.parse(returned)
    require(returned == origin.encoded(value) and
            set(value) == {"admissionSha256", "sessionSha256", "clock", "returnedNs"} and
            value["admissionSha256"] == origin.digest(admitted.record) and
            value["sessionSha256"] == origin.digest(session) and value["clock"] == origin.clock_value(past.clock) and
            history.admission_return(past, value["returnedNs"]), "BOOTSTRAP_ORIGINAL_ADMISSION_RETURN")
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
    return _read_chain(_LegacyOriginalReader(owner, fence), private, context_raw, admitted,
                       records, returned, admission_hashes, final=final)


def _read_chain(reader, private, context_raw, admitted, records, returned, admission_hashes, *, final):
    require(type(reader) in (_LegacyOriginalReader, _NewEntryOriginalReader, _RecipientParentReader),
            "BOOTSTRAP_ORIGINAL_READER_KIND")
    reader.checked()
    owner, past = reader.owner, reader.past
    require(type(records) is dict and set(records) == PHASE_FILES and
            all(type(raw) is bytes for raw in records.values()), "BOOTSTRAP_ORIGINAL_PHASE_FILES")
    context = _context_history_record(context_raw, admitted, private.path, past)
    require(context["admissionReturnSha256"] == admission_hashes["returnSha256"] and
            context["admissionReturnedNs"] == returned["returnedNs"], "BOOTSTRAP_ORIGINAL_CONTEXT_RETURN_CHANGED")
    directory = owner.child(private, "service", final=final)
    start = _start_history_record(records["start.json"], context_raw, context, private.path, past)
    row, birth = (origin.parse(records[name]) for name in ("result.json", "native-start.json"))
    baseline_record(records["baseline.json"], past.clock.role)
    require(set(row) == TERMINAL_FIELDS and set(birth) == {"ownership", "leader", "preparerIdentity", "observedNs"},
            "BOOTSTRAP_ORIGINAL_TERMINAL_FIELDS")
    preparer = closed_lifetime(row["preparerIdentity"], past.clock.role)
    require(preparer == closed_lifetime(birth["preparerIdentity"], past.clock.role) and
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
            any(lifetime(item, past.clock.role) == lifetime(row["leader"], past.clock.role)
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
            ack["clock"] == origin.clock_value(past.clock), "BOOTSTRAP_ORIGINAL_CHILD_ACK")
    require(set(child) == {"schema", "scope", "contextSha256", "startSha256", "admissionSha256", "invocation", "clock",
            "launchMinimumNs", "beganNs", "metadataLastNs", "acquiredNs", "completedNs", "originalsSha256",
            "returned", "retirement", "errors"} and
            type(child["schema"]) is int and child["schema"] == 1 and child["scope"] == CHILD_SCOPE and
            child["contextSha256"] == origin.digest(context_raw) and child["startSha256"] == origin.digest(records["start.json"]) and
            child["admissionSha256"] == origin.digest(admitted.record) and child["invocation"] == start["invocation"] and
            child["clock"] == origin.clock_value(past.clock) and child["returned"] is True and
            child["retirement"] == "KNOWN" and child["errors"] == [] and
            child["launchMinimumNs"] == row["launchMinimumNs"], "BOOTSTRAP_ORIGINAL_CHILD_TERMINAL")
    responses = {name: owner.read(directory, name + ".json", final=final) for name in ("attempt", "jobs")}
    basis = service_time.derive(admitted, responses, start["invocation"], past.clock, context["runnerName"])
    service = basis["service"]
    require(child["originalsSha256"] == service["originalsSha256"], "BOOTSTRAP_ORIGINAL_RESPONSES_CHANGED")
    minimum = history.chain_minimum(past, context["admissionReturnedNs"],
                                    start, row, birth, child, service, ack)
    # This is still the actual owning reader's observation. A pure historical
    # minimum cannot attest current time, renew a fence or register provenance.
    last = reader.observe(final=final, minimum=minimum)
    return {"service": service, "serviceTimeBasis": basis, "childTerminalSha256": origin.digest(child_raw),
            "phaseSha256": {name: origin.digest(raw) for name, raw in records.items()},
            "admissionOriginals": admission_hashes, "preludeSha256": origin.digest(past.raw), "revalidatedNs": last,
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
    return _read_prepared(_LegacyOriginalReader(owner, fence), private, handoff_raw, context_raw)


def _read_prepared(reader, private, handoff_raw, context_raw):
    require(type(reader) in (_LegacyOriginalReader, _NewEntryOriginalReader, _RecipientParentReader) and reader.first is not None,
            "BOOTSTRAP_ADOPTION_READER")
    reader.checked()
    owner, past = reader.owner, reader.past
    owner.end()
    handoff = handoff_record(handoff_raw, past.clock)
    require(owner.read(private, "prepare-handoff.json") == handoff_raw and
            owner.read(private, "context.json") == context_raw and
            origin.digest(context_raw) == handoff["contextSha256"] and
            owner.read(private, "prelude.json") == past.raw, "BOOTSTRAP_ADOPTION_ORIGINALS_CHANGED")
    raw = owner.read(private, "origin-result.json")
    require(origin.digest(raw) == handoff["originSha256"], "BOOTSTRAP_ADOPTION_ORIGIN_CHANGED")
    result = origin.parse(raw)
    require(set(result) == RESULT_FIELDS and raw == origin.encoded(result) and
            type(result["schema"]) is int and result["schema"] == 1 and result["scope"] == RESULT_SCOPE and
            result["contextSha256"] == origin.digest(context_raw) and result["budgetAcceptance"] == "NOT_ADMITTED" and
            result["testAcceptance"] == "NOT_PERFORMED" and result["exportSaveAuthority"] is False and
            type(result["directories"]) is dict and set(result["directories"]) == set(DIRECTORIES),
            "BOOTSTRAP_ADOPTION_PARENT_RESULT")
    identities = {"sessionIdentity": directory_identity(result["sessionIdentity"], past.clock.role),
        "directories": {name: directory_identity(value, past.clock.role) for name, value in result["directories"].items()}}
    require(private_identities(owner, private, final=False) == identities, "BOOTSTRAP_ADOPTION_DIRECTORIES_CHANGED")
    admitted_values, returns, hashes = [], [], []
    for name in ("admission", "final-admission"):
        directory = owner.child(private, name)
        admitted = load_admission(owner, directory)
        returned, bound = _admission_history_content(admitted, owner.read(directory, "session-result.json"),
            owner.read(private, name + "-return.json"), past)
        admitted_values.append(admitted)
        returns.append(returned)
        hashes.append(bound)
    admitted = admitted_values[0]
    require(admitted_values[1] == admitted, "BOOTSTRAP_ADOPTION_FINAL_ADMISSION_CHANGED")
    context = _context_history_record(context_raw, admitted, private.path, past)
    directory = owner.child(private, "service")
    records = {name: owner.read(directory, name,
        ACK_LIMIT if name == "stdout.log" else STDERR_LIMIT if name == "stderr.log" else LIMIT) for name in sorted(PHASE_FILES)}
    checked = _read_chain(reader, private, context_raw, admitted, records, returns[0], hashes[0], final=False)
    terminal = origin.parse(records["result.json"])
    process_identity = closed_lifetime(result["processIdentity"], past.clock.role)
    require(process_identity == terminal["preparerIdentity"] == handoff["processIdentity"],
            "BOOTSTRAP_ADOPTION_PREPARER_CHANGED")
    original_chain = result["originalChain"]
    require(type(original_chain) is dict, "BOOTSTRAP_ADOPTION_ORIGINAL_CHAIN")
    revalidated = origin.integer(original_chain.get("revalidatedNs"))
    require(origin.encoded(original_chain) == origin.encoded({**checked, "revalidatedNs": revalidated}) and
            origin.encoded(result["finalAdmission"]) == origin.encoded(returns[1]) and
            origin.encoded(result["finalAdmissionOriginals"]) == origin.encoded(hashes[1]),
            "BOOTSTRAP_ADOPTION_ORIGINAL_CHAIN_CHANGED")
    history.adopter_first(past, terminal["finalizedNs"], returns[1]["returnedNs"],
        revalidated, result["retainedNs"], handoff["closedNs"], handoff["recordedNs"], reader.first.nanoseconds)
    require(private_identities(owner, private, final=False) == identities, "BOOTSTRAP_ADOPTION_DIRECTORIES_CHANGED")
    reader.checked()
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


def _new_entry_original_pins(transition):
    entry = transition._entry
    first = transition._owner.first
    return ((transition.raw, transition.pending_raw, transition.proposal_raw, transition.responses,
             transition._retained_ns, transition._preclose_ns, transition._closed_ns, transition._checked_ns,
             entry.raw, entry.session, entry.session_original, entry.return_original, entry.handoff_original,
             entry.context_original, entry.preparation_original, first.nanoseconds,
             (first.clock.role, first.clock.domain, first.clock.ticks_per_second)),
            (entry, transition._owner, transition._fence, transition._limits, transition._callbacks,
             transition._snapshot, entry.admitted, entry._private, entry._target, entry._owner, entry._fence,
             first, transition._owner.admissions, transition._owner.admissions.get(str(entry._target.path / "admission"))))


def _entry_attempt_record(attempt):
    """Find the actual retained claim without trusting mutable attempt fields.

    In particular, rejection/cleanup must not look up the owner through a
    changed transition. Value-equal/copied attempts cannot select this record.
    """
    require(type(attempt) is _EntryAttempt, "BOOTSTRAP_NEW_ENTRY_NOT_CLAIMED")
    # Never hold this lock across a clock, callback, parsing or owned operation.
    with _ENTRY_CLAIM_LOCK:
        matches = [record for record in _ENTRY_ATTEMPTS.values() if type(record) is tuple and
                   len(record) == 4 and record[1] is attempt]
    require(len(matches) == 1, "BOOTSTRAP_NEW_ENTRY_NOT_CLAIMED")
    return matches[0]


def _entry_claim_identity(attempt):
    registered = _entry_attempt_record(attempt)
    require(type(registered) is tuple and len(registered) == 4 and registered[0] is attempt.transition and
            registered[1] is attempt and registered[2] is attempt.originals and registered[3] is attempt.bindings,
            "BOOTSTRAP_NEW_ENTRY_NOT_CLAIMED")
    if registered[3] is not None:
        pins = registered[3]
        require(all(a is b for a, b in zip((attempt.owner, attempt.window, attempt.first, attempt.callback), pins[:4])) and
                type(attempt.local_end) is float and attempt.local_end == pins[4], "BOOTSTRAP_NEW_ENTRY_OWNER_CHANGED")
    transition = attempt.transition
    require(transition._owner.entry_close_original is transition, "BOOTSTRAP_ENTRY_CLOSE_NOT_CURRENT_RETURN")
    values, references = _new_entry_original_pins(transition)
    require(all(type(a) is type(b) and a == b for a, b in zip(values, attempt.originals[0])) and
            all(a is b for a, b in zip(references, attempt.originals[1])), "BOOTSTRAP_NEW_ENTRY_ORIGINAL_CHANGED")
    _entry_close_state(transition)
    history.snapshot(transition._fence)
    require(transition._fence.last == transition._checked_ns and
            transition._limits[8] is transition._owner.first, "BOOTSTRAP_NEW_ENTRY_ORIGINAL_CLOCK_CHANGED")
    return attempt


def _claim_closed_entry(transition):
    # Invalid/foreign inputs cannot consume the original or assume its cleanup.
    check_closed_entry_transition(transition)
    require(type(transition._entry) is OriginalEntry and type(transition._fence) is origin.Fence and
            type(transition._limits) is tuple and len(transition._limits) == 10 and
            type(transition._callbacks) is tuple and len(transition._callbacks) == 2 and
            all(callable(callback) for callback in transition._callbacks), "BOOTSTRAP_NEW_ENTRY_ORIGINAL_KIND")
    first = origin.clocks.validate_reading(transition._limits[8])
    require(first is transition._owner.first and first.clock == transition._fence.clock and
            first.nanoseconds == origin.parse(transition._entry.raw)["window"]["adopterFirstNs"],
            "BOOTSTRAP_NEW_ENTRY_ORIGINAL_FIRST")
    entry = transition._entry
    registered = transition._owner.admissions.get(str(entry._target.path / "admission"))
    require(type(registered) is tuple and len(registered) == 3 and registered[0] is entry.admitted and
            registered[1:] == (entry.session_original, entry.return_original) and
            all(any(resource is directory for _, _, resource in transition._snapshot[1])
                for directory in (entry._private, entry._target)), "BOOTSTRAP_NEW_ENTRY_ORIGINAL_REGISTRY")
    phase_end = origin.integer(origin.parse(transition.proposal_raw)["phaseFencesNs"]["productive-entry"])
    pins = (*_new_entry_original_pins(transition), phase_end)
    attempt = _EntryAttempt(transition, pins)
    with _ENTRY_CLAIM_LOCK:
        require(id(transition) not in _ENTRY_ATTEMPTS, "BOOTSTRAP_NEW_ENTRY_ALREADY_CLAIMED")
        _ENTRY_ATTEMPTS[id(transition)] = (transition, attempt, pins, None)
    return attempt


def _new_entry_owner(attempt):
    # Cleanup uses the independently retained actual constructor return, never
    # a changed attempt.owner or equal/copy owner supplied by a callback.
    registered = _entry_attempt_record(attempt)
    return None if registered[3] is None else registered[3][0]


def _new_entry_limits(attempt):
    _entry_claim_identity(attempt)
    first = origin.clocks.validate_reading(attempt.first)
    transition = attempt.transition
    require(first is not transition._owner.first and first.clock == transition._fence.clock and
            first.nanoseconds >= transition._checked_ns, "BOOTSTRAP_NEW_ENTRY_FIRST_CLOCK")
    # The proposal is already rederived by the original close check; its bytes
    # and this extracted end are pinned to this claim. Live originals are also
    # reread/rederived below. No allocationStartBasisNs wait or renewed job end.
    phase_end = attempt.originals[2]
    final = min(origin.integer(first.nanoseconds + 120 * origin.NS), phase_end)
    work = min(origin.integer(first.nanoseconds + 75 * origin.NS),
               origin.integer(final - 45 * origin.NS))
    require(first.nanoseconds < work, "BOOTSTRAP_NEW_ENTRY_NO_WORK_INTERVAL")
    return first.clock, first.nanoseconds, work, final, phase_end


def _new_entry_cancel(attempt):
    _entry_claim_identity(attempt)
    for callback in attempt.transition._callbacks:
        callback()
        _entry_claim_identity(attempt)
        if attempt.window is not None:
            attempt.window.checked()


def _new_entry_live(attempt):
    _entry_claim_identity(attempt)
    require(attempt.state == "READING" and type(attempt.owner) is Owner and
            attempt.owner.closed is False and attempt.owner.unknown is False and attempt.owner.original is None and
            attempt.owner.errors == [] and attempt.owner.phase_originals is None and
            attempt.owner.entry_original is None and attempt.owner.entry_close_attempted is False and
            attempt.owner.entry_close_original is None and attempt.owner.entry_close_snapshot is None and
            not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
            "BOOTSTRAP_NEW_ENTRY_NOT_LIVE")
    attempt.window.checked()
    return attempt.owner


def _new_entry_paths(attempt):
    entry = attempt.transition._entry
    context = origin.parse(entry.context_original)
    path = Path(context["session"])
    previous, target = (path.with_name(path.name + suffix) for suffix in ("-adoption", "-entry"))
    require(context["root"] == str(ROOT) and entry._private.path == path and entry._target.path == previous and
            entry.session == str(previous), "BOOTSTRAP_NEW_ENTRY_PATH_CHANGED")
    return path, previous, target


def _new_entry_host(attempt):
    owner = _new_entry_live(attempt)
    owner.end()
    require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE, "BOOTSTRAP_PRIOR_UNKNOWN")
    require(origin.wire.TOKEN_ENV not in os.environ, "BOOTSTRAP_ADOPTION_TOKEN_FORBIDDEN")
    require(os.environ.get(PREPARE_OUTCOME_ENV) == "success", "BOOTSTRAP_PREPARE_ORIGINAL_OUTCOME")
    entry = attempt.transition._entry
    require(os.environ.get(PREPARE_HASH_ENV) == origin.digest(entry.handoff_original),
            "BOOTSTRAP_PREPARE_ORIGINAL_HASH_CHANGED")
    selection, path, event = host_inputs(attempt.first.clock.role)
    context, admitted = origin.parse(entry.context_original), origin.admitted_value(entry.admitted)
    inherited = query._inherited_context()
    child_environment(path)
    require(path == _new_entry_paths(attempt)[0] and selection == context["selection"] == admitted["selection"] and
            event == entry.admitted.original_event and context["runnerName"] == os.environ.get("RUNNER_NAME") and
            context["inheritedContext"] == inherited, "BOOTSTRAP_NEW_ENTRY_HOST_CHANGED")
    require(os.getpid() != origin.parse(entry.preparation_original)["processIdentity"]["pid"],
            "BOOTSTRAP_ADOPTER_SAME_PROCESS")
    _entry_claim_identity(attempt)
    owner.end()


def _new_entry_owned(owner, directory, path, identity, *, final=False):
    require(directory is not None and directory.path == path and any(row["label"] == "directory" and
            row["owner"] is directory and row["attempted"] is False and row["closed"] is False
            for row in owner.resources), "BOOTSTRAP_NEW_ENTRY_DIRECTORY_NOT_OWNED")
    owner.end(final=final)
    directory.verify()
    require(directory_identity(list(directory.identity), owner.fence.clock.role) == list(identity),
            "BOOTSTRAP_NEW_ENTRY_DIRECTORY_CHANGED")
    owner.end(final=final)


def _new_entry_read_originals(attempt):
    owner = _new_entry_live(attempt)
    transition, entry = attempt.transition, attempt.transition._entry
    value, paths = origin.parse(entry.raw), _new_entry_paths(attempt)
    _new_entry_host(attempt)
    for directory, path, identity in ((attempt.private, paths[0], value["preparation"]["sessionIdentity"]),
            (attempt.previous_target, paths[1], value["sessionIdentity"]),
            (attempt.target, paths[2], attempt.target_identity)):
        _new_entry_owned(owner, directory, path, identity)
    previous = attempt.previous_target
    require(owner.read(previous, "entry-context.json") == entry.raw and
            owner.read(previous, "entry-close-pending.json") == transition.pending_raw,
            "BOOTSTRAP_NEW_ENTRY_ADOPTION_CHANGED")
    directory = owner.child(previous, "admission")
    admitted = load_admission(owner, directory)
    session, returned = owner.read(directory, "session-result.json"), owner.read(previous, "admission-return.json")
    require(admitted == entry.admitted and session == entry.session_original and returned == entry.return_original,
            "BOOTSTRAP_NEW_ENTRY_OLD_ADMISSION_CHANGED")
    _admission_history_content(admitted, session, returned, history.snapshot(transition._fence))
    reader = _NewEntryOriginalReader(attempt)
    again, context, prepared = _read_prepared(reader, attempt.private, entry.handoff_original, entry.context_original)
    require(again == entry.admitted and same_preparation(prepared, origin.parse(entry.preparation_original)),
            "BOOTSTRAP_NEW_ENTRY_PREPARATION_CHANGED")
    directory = owner.child(attempt.private, "service")
    responses = tuple((name, owner.read(directory, name + ".json")) for name in ("attempt", "jobs"))
    require(responses == transition.responses and
            origin.encoded(_entry_close_proposal(entry, responses)) == transition.proposal_raw,
            "BOOTSTRAP_NEW_ENTRY_SERVICE_ORIGINALS_CHANGED")
    _new_entry_host(attempt)
    _new_entry_live(attempt)
    return prepared


def _new_entry_return_content(attempt):
    """Current actual-return registry/window only; historical original75 stays closed."""
    owner, window = attempt.owner, attempt.window
    window.checked()
    registered = owner.admissions.get(str(_new_entry_paths(attempt)[2] / "admission"))
    require(type(registered) is tuple and len(registered) == 3 and registered is attempt.admission_originals and
            type(attempt.admitted) is I.Admission and registered[0] is attempt.admitted and
            attempt.admitted == attempt.transition._entry.admitted and type(attempt.returned) is dict and
            origin.encoded(attempt.returned) == registered[2], "BOOTSTRAP_NEW_ENTRY_NOT_CURRENT_ADMISSION")
    session, raw = registered[1:]
    value = origin.parse(raw)
    require(raw == origin.encoded(value) and set(value) == {"admissionSha256", "sessionSha256", "clock", "returnedNs"} and
            value["admissionSha256"] == origin.digest(attempt.admitted.record) and
            value["sessionSha256"] == origin.digest(session) and value["clock"] == origin.clock_value(window.clock) and
            window.first <= origin.integer(value["returnedNs"]) <= window.last and value["returnedNs"] < window.work,
            "BOOTSTRAP_NEW_ENTRY_ADMISSION_RETURN")
    status = origin.parse(session)
    require(set(status) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"} and
            type(status["schema"]) is int and status["schema"] == 1 and status["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
            status["result"] == "READY_FOR_CALLER_SEAL" and status["retirement"] == "KNOWN" and
            status["firstError"] is None and status["errors"] == [] and type(status["queries"]) is list and
            type(status["readbacks"]) is list and type(status["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", status["job"]),
            "BOOTSTRAP_NEW_ENTRY_QUERY_SESSION")
    return {"admissionSha256": origin.digest(attempt.admitted.record), "sessionSha256": origin.digest(session),
            "returnSha256": origin.digest(raw)}


def _new_entry_read_admission(attempt):
    owner = _new_entry_live(attempt)
    hashes = _new_entry_return_content(attempt)
    _new_entry_owned(owner, attempt.target, _new_entry_paths(attempt)[2], attempt.target_identity)
    directory = owner.child(attempt.target, "admission")
    require(load_admission(owner, directory) == attempt.admitted and
            owner.read(directory, "session-result.json") == attempt.admission_originals[1] and
            owner.read(attempt.target, "admission-return.json") == attempt.admission_originals[2],
            "BOOTSTRAP_NEW_ENTRY_READMISSION_CHANGED")
    require(_new_entry_return_content(attempt) == hashes, "BOOTSTRAP_NEW_ENTRY_READMISSION_CHANGED")
    return hashes


def _new_entry_pending(attempt):
    entry, window = attempt.transition._entry, attempt.window
    return {"schema": 1, "scope": NEW_ENTRY_PENDING_SCOPE,
            "previousTransitionSha256": origin.digest(attempt.transition.raw),
            "entryContextSha256": origin.digest(entry.raw), "proposalSha256": origin.digest(attempt.transition.proposal_raw),
            "session": str(_new_entry_paths(attempt)[2]), "sessionIdentity": list(attempt.target_identity),
            "preparation": origin.parse(attempt.preparation), "readmission": _new_entry_return_content(attempt),
            "originalAdopterFirstNs": attempt.transition._limits[8].nanoseconds,
            "previousCheckedNs": attempt.transition._checked_ns, "window": window.record(),
            "retainedNs": attempt.retained_ns, "newOwnerRetirement": "PENDING_CLOSE",
            "productiveOwner": "NOT_CREATED", "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}


def _new_entry_error(attempt, stage, error, *, unknown=False):
    if attempt.original is None:
        attempt.original = error
    owner = _new_entry_owner(attempt)
    if owner is not None:
        owner.error(stage, error, unknown=unknown)
        attempt.unknown |= owner.unknown
    else:
        detail = diagnostics._exception_detail(error)
        attempt.unknown |= unknown or detail["retirementUnknown"]
        if len(attempt.errors) < 64:
            attempt.errors.append({"stage": stage, "detail": detail})
        else:
            attempt.unknown = True


def _new_entry_roster(attempt):
    """Retain all observed row/resource identities before any fallible supplier.

    Append-only ownership, not append-only close flags: writers can already be
    closed. A replaced/removed/reordered row or list cannot erase a known pin.
    Even a newly observed malformed replacement remains referenced on failure.
    """
    owner = _new_entry_owner(attempt)
    require(type(owner) is Owner and type(owner.resources) is list and type(attempt.resources) is tuple,
            "BOOTSTRAP_NEW_ENTRY_ROSTER")
    seen = {id(row): resource for row, _, resource in attempt.resources}
    additions = []
    for row in owner.resources:
        label, resource = (row.get("label"), row.get("owner")) if type(row) is dict else (None, None)
        if id(row) not in seen or seen[id(row)] is not resource:
            additions.append((row, label, resource))
            seen[id(row)] = resource
    attempt.resources += tuple(additions)
    bindings = _entry_attempt_record(attempt)[3]
    require(owner.resources is bindings[6] and len(owner.resources) == len(attempt.resources),
            "BOOTSTRAP_NEW_ENTRY_ROSTER")
    for current, (row, label, resource) in zip(owner.resources, attempt.resources):
        require(current is row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                row["label"] == label and label in ("directory", "writer") and row["owner"] is resource and
                type(row["attempted"]) is bool and type(row["closed"]) is bool and
                (not row["closed"] or row["attempted"]), "BOOTSTRAP_NEW_ENTRY_ROSTER")


def _new_entry_snapshot(attempt):
    # Unlike the successful old close bridge, a failed new entry may not yet
    # have acquired anything. An actually empty new roster still must close.
    _new_entry_roster(attempt)
    return _new_entry_owner(attempt).resources, attempt.resources


def _new_entry_known(attempt):
    owner, snapshot = _new_entry_owner(attempt), attempt.snapshot
    require(type(snapshot) is tuple and len(snapshot) == 2 and type(snapshot[1]) is tuple and owner.closed is True and
            owner.resources is snapshot[0] and len(owner.resources) == len(snapshot[1]), "BOOTSTRAP_NEW_ENTRY_ROSTER")
    for current, (row, label, resource) in zip(owner.resources, snapshot[1]):
        require(current is row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                row["label"] == label and row["owner"] is resource and row["attempted"] is True and
                row["closed"] is True, "BOOTSTRAP_NEW_ENTRY_ROSTER")


def _new_entry_preserve(attempt):
    owner = _new_entry_owner(attempt)
    if owner is None:
        return
    try:
        _new_entry_known(attempt)
    except BaseException as error:
        _new_entry_error(attempt, "new-entry-roster-return", error, unknown=True)
    attempt.original = attempt.original or owner.original
    attempt.unknown |= owner.unknown
    if owner.unknown and not any(value is owner for value in QUARANTINE):
        QUARANTINE.append(owner)
    # attempt.snapshot retains the captured rows even if the owner list changed.


def _new_entry_failure_retention(attempt):
    owner = _new_entry_owner(attempt)
    if owner is None or owner.closed or owner.unknown or attempt.target is None or attempt.target_identity is None:
        return
    try:
        require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE, "BOOTSTRAP_PRIOR_UNKNOWN")
        attempt.window.checked()
        posix._deadline(attempt.local_end)
        attempt.window.now(final=True)
        _new_entry_owned(owner, attempt.target, _new_entry_paths(attempt)[2], attempt.target_identity, final=True)
        attempt.failure_custody = "INCOMPLETE"
        attempt.failure_raw = owner.write(attempt.target, "new-entry-failure.json", {"schema": 1, "result": "HOLD",
            "previousTransitionSha256": origin.digest(attempt.transition.raw), "window": attempt.window.record(),
            "errors": attempt.errors, "newOwnerRetirement": "PENDING_CLOSE", "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}, final=True)
        attempt.failure_custody = "PRIVATE_PROVISIONAL_ONLY"
    except BaseException as error:
        _new_entry_error(attempt, "new-entry-failure-retention", error)


def _new_entry_record(attempt, preclose_ns, closed_ns):
    return {"schema": 1, "scope": NEW_ENTRY_SCOPE,
            "previousTransitionSha256": origin.digest(attempt.transition.raw),
            "pendingSha256": origin.digest(attempt.pending_raw), "window": attempt.window.record(),
            "preCloseNs": preclose_ns, "closedNs": closed_ns, "resourceCount": len(attempt.snapshot[1]),
            "newOwnerRetirement": "KNOWN_RESOURCE_CLOSE_ONLY", "productiveOwner": "NOT_CREATED",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}


def _new_entry_result_content(result):
    attempt = _entry_claim_identity(result._attempt)
    owner, window = attempt.owner, attempt.window
    window.checked()
    _new_entry_known(attempt)
    require(attempt.state in ("CLOSING", "COMPLETE") and attempt.original is None and attempt.unknown is False and
            owner.original is None and owner.errors == [] and owner.unknown is False and
            owner.phase_originals is None and owner.entry_original is None and owner.entry_close_attempted is False and
            owner.entry_close_original is None and owner.entry_close_snapshot is None and
            set(owner.admissions) == {str(_new_entry_paths(attempt)[2] / "admission")} and
            attempt.pending_raw == origin.encoded(_new_entry_pending(attempt)), "BOOTSTRAP_NEW_ENTRY_NOT_SUCCESSFUL")
    prepared = origin.parse(attempt.preparation)
    times = (window.first, attempt.returned["returnedNs"], prepared["originalChain"]["revalidatedNs"],
             attempt.retained_ns, result._preclose_ns, result._closed_ns, result._checked_ns)
    require(all(type(value) is int and 0 <= value <= origin.clocks.UINT64 for value in times) and
            list(times) == sorted(times) and result._preclose_ns < window.work and result._checked_ns < window.final and
            window.last == result._checked_ns, "BOOTSTRAP_NEW_ENTRY_RETURN_CLOCK")
    value = _new_entry_record(attempt, result._preclose_ns, result._closed_ns)
    require(type(result.raw) is bytes and result.raw == origin.encoded(value), "BOOTSTRAP_NEW_ENTRY_RETURN_CHANGED")
    return value


def check_new_entry_transition(result):
    """Exact registered closed entry only; no current read or producer authority."""
    require(type(result) is NewEntryTransition and type(result._attempt) is _EntryAttempt and
            result._attempt.state == "COMPLETE" and result._attempt.result is result,
            "BOOTSTRAP_NEW_ENTRY_NOT_CURRENT_RETURN")
    return _new_entry_result_content(result)


def readmit_closed_entry(transition):
    """Dormant INTERNAL once-claimed entry/readmission transaction, not a producer.

    It NEVER advances/reopens the old Owner/Fence/handles. Only fresh entry
    resources are acquired and closed here; the result has no execution or
    export/save authority. No public operation/workflow calls this function.
    """
    attempt = _claim_closed_entry(transition)
    owner = preclose_ns = None
    try:
        attempt.local_start = local = time.monotonic()
        require(type(local) in (int, float) and math.isfinite(local) and local >= 0, "BOOTSTRAP_NEW_ENTRY_LOCAL_CLOCK")
        # Retain the actual return before validation or any later fallible work.
        attempt.first = origin.clocks.observe()
        attempt.callback = lambda: _new_entry_cancel(attempt)
        attempt.window = _NewEntryWindow(attempt)
        attempt.local_end = origin.wire._directed_deadline(local, 120, attempt.window.final, attempt.window.first)
        attempt.owner = owner = Owner(attempt.local_end, attempt.window, first=attempt.first, cancelled=attempt.callback)
        attempt.bindings = (attempt.owner, attempt.window, attempt.first, attempt.callback, attempt.local_end,
                            attempt.owner.admissions, attempt.owner.resources, attempt.owner.errors)
        with _ENTRY_CLAIM_LOCK:
            registered = _ENTRY_ATTEMPTS[id(transition)]
            _ENTRY_ATTEMPTS[id(transition)] = (*registered[:3], attempt.bindings)
        attempt.errors = attempt.owner.errors
        attempt.state = "READING"
        owner = _new_entry_live(attempt)
        owner.end()
        _new_entry_host(attempt)
        path, previous, target = _new_entry_paths(attempt)
        attempt.private = owner.open(path)
        attempt.previous_target = owner.open(previous)
        value = origin.parse(transition._entry.raw)
        _new_entry_owned(owner, attempt.private, path, value["preparation"]["sessionIdentity"])
        _new_entry_owned(owner, attempt.previous_target, previous, value["sessionIdentity"])
        attempt.target = owner.new(target)  # Exclusive source-derived sibling; no retry or overwrite.
        attempt.target_identity = tuple(directory_identity(list(attempt.target.identity), attempt.window.clock.role))
        before = _new_entry_read_originals(attempt)
        attempt.admitted, attempt.returned = admit(owner, attempt.window, target / "admission", expected=transition._entry.admitted)
        attempt.admission_originals = owner.admissions.get(str(target / "admission"))
        _new_entry_return_content(attempt)
        owner.write(attempt.target, "admission-return.json", attempt.admission_originals[2])
        _new_entry_read_admission(attempt)
        after = _new_entry_read_originals(attempt)
        require(same_preparation(after, before), "BOOTSTRAP_NEW_ENTRY_CHANGED_DURING_READMISSION")
        attempt.preparation = origin.encoded(after)
        attempt.retained_ns = attempt.window.now(minimum=after["originalChain"]["revalidatedNs"])
        attempt.pending_raw = owner.write(attempt.target, "new-entry-pending.json", _new_entry_pending(attempt))
        _new_entry_read_admission(attempt)
        last = _new_entry_read_originals(attempt)
        require(same_preparation(last, after) and owner.read(attempt.target, "new-entry-pending.json") == attempt.pending_raw,
                "BOOTSTRAP_NEW_ENTRY_PENDING_CHANGED")
        _new_entry_cancel(attempt)
        owner.end()
        _new_entry_live(attempt)
        preclose_ns = attempt.window.last
    except BaseException as error:
        _new_entry_error(attempt, "new-entry-readmission", error)
        _new_entry_failure_retention(attempt)
    finally:
        if owner is not None:
            attempt.state = "CLOSING"
            try:
                attempt.snapshot = _new_entry_snapshot(attempt)
            except BaseException as error:
                attempt.snapshot = (owner.resources, attempt.resources)
                _new_entry_error(attempt, "new-entry-snapshot", error, unknown=True)
            try:
                owner.close()
            except BaseException as error:
                _new_entry_error(attempt, "new-entry-close-return", owner.original or error)
    _new_entry_preserve(attempt)
    if attempt.original is not None:
        attempt.state = "FAILED"
        raise attempt.original
    try:
        require(attempt.pending_raw is not None and preclose_ns is not None, "BOOTSTRAP_NEW_ENTRY_INCOMPLETE")
        _new_entry_cancel(attempt)
        posix._deadline(attempt.local_end)
        closed_ns = attempt.window.now(final=True, minimum=preclose_ns)
        raw = origin.encoded(_new_entry_record(attempt, preclose_ns, closed_ns))
        _new_entry_result_content(NewEntryTransition(raw, attempt, preclose_ns, closed_ns, closed_ns))
        _new_entry_cancel(attempt)
        posix._deadline(attempt.local_end)
        checked_ns = attempt.window.now(final=True, minimum=closed_ns)
        _new_entry_cancel(attempt)
        posix._deadline(attempt.local_end)
        result = NewEntryTransition(raw, attempt, preclose_ns, closed_ns, checked_ns)
        _new_entry_result_content(result)  # Non-acquiring final state/roster check after every callback/clock.
        require(attempt.result is None, "BOOTSTRAP_NEW_ENTRY_RESULT_ALREADY_REGISTERED")
        attempt.result, attempt.state = result, "COMPLETE"
        return result
    except BaseException as error:
        # Already closed: retain references, never reopen or allocate failure custody.
        _new_entry_error(attempt, "new-entry-postreturn", error)
        _new_entry_preserve(attempt)
        attempt.state = "FAILED"
        raise attempt.original


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


def recipient_command(context_hash, minimum=None):
    """Closed argv for the dormant internal recipient-only parent."""
    require(type(context_hash) is str and re.fullmatch(r"[0-9a-f]{64}", context_hash), "BOOTSTRAP_RECIPIENT_CONTEXT_HASH")
    result = [str(Path(sys.executable).resolve(strict=True)), "-I", "-B", "-S", str(Path(__file__).resolve()),
              "_recipient", "--context-sha256", context_hash]
    return result if minimum is None else result + ["--minimum-ns", str(origin.integer(minimum))]


def recipient_environment(path):
    """Separate narrow installed-tool lookup, never broaden the service child.

    The internal native parent uses this environment and adds its real domain.
    This function creates no owner/credential authority and downloads nothing.
    """
    require(origin.wire.TOKEN_ENV not in os.environ, "BOOTSTRAP_RECIPIENT_TOKEN_FORBIDDEN")
    result = child_environment(path)  # Keep the existing override refusal unchanged.
    search = os.environ.get("PATH", os.defpath)
    require(type(search) is str and 0 < len(search) <= 32768 and
            not any(ord(char) < 32 or ord(char) == 127 for char in search) and
            all(part and Path(part).is_absolute() for part in search.split(os.pathsep)),
            "BOOTSTRAP_RECIPIENT_INSTALLED_TOOL_PATH")
    result["PATH"] = search
    return result


@dataclass(frozen=True)
class _RecipientWindow:
    """New child-only cap, not a productive owner or an authenticated parent.

    Metadata has its own immutable45 window/owner, closed before operative
    ownership. Both clocks still start at the actual child's FIRST observations;
    learning the frame never starts another210. The original parent work fence
    only shortens operative ownership, not the already-closed metadata owner.
    Synchronous validators cannot be preempted by these before/after checks.
    """
    reading: object = field(repr=False)
    metadata_last: int
    local_start: float = field(repr=False)
    parent_work: object
    cancelled: object = field(repr=False, compare=False)
    metadata: bool = False
    clock: object = field(init=False, repr=False)
    first: int = field(init=False)
    work: int = field(init=False)
    final: int = field(init=False)
    local_end: float = field(init=False, repr=False)
    last: int = field(init=False)

    def __post_init__(self):
        origin.clocks.validate_reading(self.reading)
        first = self.reading.nanoseconds
        require(type(self.metadata) is bool and (self.parent_work is None) == self.metadata,
                "BOOTSTRAP_RECIPIENT_WINDOW_KIND")
        seconds = 45 if self.metadata else 210
        end = origin.integer(first + seconds * origin.NS)
        if not self.metadata:
            end = min(end, origin.integer(self.parent_work))
        require(first <= origin.integer(self.metadata_last) < end and callable(self.cancelled),
                "BOOTSTRAP_RECIPIENT_CHILD_WINDOW")
        local_end = origin.wire._directed_deadline(self.local_start, seconds, end, first)
        for name, value in (("clock", self.reading.clock), ("first", first), ("work", end), ("final", end),
                            ("local_end", local_end), ("last", self.metadata_last)):
            object.__setattr__(self, name, value)

    def now(self, *, final=False, minimum=0, limit=None):
        observed = origin.clocks.checked_now(self.clock, minimum_ns=max(self.last, origin.integer(minimum)))
        object.__setattr__(self, "last", observed)  # Before expiry/cancellation/local conversion can fail.
        end = self.final if limit is None else min(self.final, origin.integer(limit))
        require(observed < end, "BOOTSTRAP_RECIPIENT_CHILD_EXPIRED")
        posix._deadline(self.local_end)
        if not final:
            self.cancelled()
        require(self.last == observed, "BOOTSTRAP_RECIPIENT_HIGHWATER_CHANGED")
        return observed

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 210,
                "BOOTSTRAP_RECIPIENT_OPERATION_MAXIMUM")
        local = time.monotonic()
        observed = self.now(final=final, limit=limit)
        end = self.final if limit is None else min(self.final, origin.integer(limit))
        return min(self.local_end, origin.wire._directed_deadline(local, maximum, end, observed))


def _recipient_content(raws, admitted, identities, original_path, path, first, minimum):
    """Supplied-original consistency, NOT parent-launch/once-claim admission."""
    past = history.HistoricalPrelude(origin.encoded(origin.parse(raws["original-context"])["prelude"]))
    require(past.clock == first.clock, "BOOTSTRAP_RECIPIENT_ORIGINAL_CLOCK")
    original = _context_history_record(raws["original-context"], admitted, original_path, past)
    service_start = _start_history_record(raws["service-start"], raws["original-context"], original, original_path, past)
    responses = {name: raws[name] for name in ("attempt", "jobs")}
    proposal = allocation.validate_proposal(raws["proposal"], admitted, responses,
        service_start["invocation"], first.clock, original["runnerName"])
    value, start = origin.parse(raws["context"]), origin.parse(raws["start"])
    record = origin.admitted_value(admitted)
    require(set(value) == RECIPIENT_CONTEXT_FIELDS and raws["context"] == origin.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == RECIPIENT_CONTEXT_SCOPE and
            value["profile"] == bootstrap.PROFILE and value["root"] == str(ROOT) and value["session"] == str(path) and
            value["originalSession"] == str(original_path) and value["clock"] == origin.clock_value(first.clock) and
            value["originalContextSha256"] == origin.digest(raws["original-context"]) and
            value["admissionSha256"] == origin.digest(admitted.record) and
            value["proposalSha256"] == origin.digest(raws["proposal"]) and
            value["directories"] == identities and value["inheritedContext"] == original["inheritedContext"] and
            value["runnerName"] == original["runnerName"] and
            all(value[name] == record[name] for name in ("selection", "cacheCohort", "source", "github")) and
            value["budgetAcceptance"] == "NOT_ADMITTED" and value["testAcceptance"] == "NOT_PERFORMED" and
            value["exportSaveAuthority"] is False, "BOOTSTRAP_RECIPIENT_CONTEXT")
    require(type(value["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["job"]) and
            type(value["previousTransitionSha256"]) is str and
            re.fullmatch(r"[0-9a-f]{64}", value["previousTransitionSha256"]), "BOOTSTRAP_RECIPIENT_CONTEXT_IDENTITIES")
    require(type(value["directories"]) is dict and set(value["directories"]) == set(identities) and
            all(directory_identity(item, first.clock.role) == identities[name]
                for name, item in value["directories"].items()) and
            origin.wire.clock_identity(value["clock"]) == first.clock, "BOOTSTRAP_RECIPIENT_NATIVE_IDENTITIES")
    previous = origin.integer(value["previousCheckedNs"], proposal["serviceTimeBasis"]["service"]["lastNs"])
    require(set(start) == START_FIELDS and raws["start"] == origin.encoded(start) and
            type(start["schema"]) is int and start["schema"] == 1 and start["scope"] == RECIPIENT_START_SCOPE and
            start["contextSha256"] == origin.digest(raws["context"]) and
            start["argv"] == recipient_command(origin.digest(raws["context"])) and start["cwd"] == str(ROOT) and
            start["role"] == first.clock.role and start["job"] == value["job"] and
            start["state"] == str(path) and start["home"] == str(path / "control-home") and
            start["exitCode"] is None and start["launchAttempted"] is False and start["scopeAttempted"] is False and
            start["retirement"] == "UNKNOWN" and type(start["invocation"]) is str and
            re.fullmatch(r"[0-9a-f]{32}", start["invocation"]), "BOOTSTRAP_RECIPIENT_PRELAUNCH")
    began = origin.integer(start["startedNs"], previous)
    work = min(origin.integer(began + 240 * origin.NS), proposal["phaseFencesNs"]["recipient-validation"],
               proposal["proposedJobEndNs"])
    final = min(origin.integer(began + 285 * origin.NS), proposal["phaseFencesNs"]["recipient-final"],
                proposal["proposedJobEndNs"])
    require(type(start["workEndNs"]) is int and type(start["finalEndNs"]) is int and
            start["workEndNs"] == work and start["finalEndNs"] == final and
            began <= origin.integer(minimum) <= first.nanoseconds < work <= final,
            "BOOTSTRAP_RECIPIENT_PARENT_FENCES")
    expected = processes.ownership_environment(value["inheritedContext"], value["job"], start["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    require(start["inheritedContext"] == {name: expected[name] for name in query._CONTEXT} and
            query._inherited_context() == start["inheritedContext"], "BOOTSTRAP_RECIPIENT_ORIGINAL_NATIVE_CONTEXT")
    return value, start, proposal


def _recipient_inputs(owner, context_hash, minimum):
    owner.end()
    require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE, "BOOTSTRAP_PRIOR_UNKNOWN")
    selection, original_path, event = host_inputs(owner.first.clock.role)
    path = original_path.with_name(original_path.name + "-productive")
    expected_environment = recipient_environment(path)
    require(set(query._inherited_context()) == set(query._CONTEXT), "BOOTSTRAP_RECIPIENT_NATIVE_PARENT_REQUIRED")
    # A genuine source-owned parent will pass only this environment. Never let
    # an ambient credential/tool hook reach the child merely because GPG later
    # uses a sanitized environment. CPython may add this locale-coercion value.
    actual = dict(os.environ)
    if "LC_CTYPE" not in expected_environment and actual.get("LC_CTYPE") in ("C.UTF-8", "UTF-8"):
        actual.pop("LC_CTYPE")
    require(actual == expected_environment, "BOOTSTRAP_RECIPIENT_CHILD_ENVIRONMENT")
    original, private = owner.open(original_path), owner.open(path)
    handles = {"original": original, "session": private}
    handles.update({name: owner.child(private, name) for name in RECIPIENT_DIRECTORIES})
    source_admission = owner.child(original, "admission")
    admitted = load_admission(owner, source_admission)
    service = owner.child(original, "service")
    raws = {"context": owner.read(private, "recipient-context.json"),
            "start": owner.read(handles["recipient-validation"], "start.json"),
            "proposal": owner.read(private, "allocation.json"),
            "original-context": owner.read(original, "context.json"),
            "service-start": owner.read(service, "start.json"),
            **{name: owner.read(service, name + ".json") for name in ("attempt", "jobs")}}
    require(origin.digest(raws["context"]) == context_hash, "BOOTSTRAP_RECIPIENT_CONTEXT_HASH_CHANGED")
    identities = {}
    for name, directory in handles.items():
        owner.end()
        directory.verify()
        identities[name] = directory_identity(list(directory.identity), owner.first.clock.role)
        owner.end()
    context, start, proposal = _recipient_content(raws, admitted, identities, original_path, path, owner.first, minimum)
    require(selection == context["selection"] and event == admitted.original_event and
            context["runnerName"] == os.environ.get("RUNNER_NAME"), "BOOTSTRAP_RECIPIENT_HOST_CHANGED")
    return {"admitted": admitted, "context": context, "start": start, "proposal": proposal, "handles": handles,
            "raws": raws, "binding": (admitted, tuple(sorted(raws.items())), origin.encoded(identities))}


def _recipient_admit(owner, directory, phase_directory, admitted):
    """Actual query/return inside original query75/120 AND child/parent caps."""
    window, supplier, original, result = owner.fence, None, None, None
    began = window.now()
    work, final = min(window.final, began + 75 * origin.NS), min(window.final, began + 120 * origin.NS)
    limits = owner.work_limit, owner.final_limit
    owner.work_limit, owner.final_limit = work, final
    try:
        try:
            pair = (window.deadline(75, limit=work), window.deadline(120, final=True, limit=final))
            supplier = query.NativeGitQueries(ROOT, directory, check_cancel=lambda: window.now(limit=work),
                                              owner_deadlines=pair)
            supplier.native_host_matches_actions()
            result = bootstrap.admit(ROOT, query_runner=supplier, expected=admitted)
            supplier.retain_admission(result)
            window.now(limit=work)
        except BaseException as error:
            original = error
        finally:
            if supplier is not None:
                try:
                    supplier._finalize(original)
                except BaseException as error:
                    if original is None:
                        original = error
            if (supplier is not None and supplier.unknown) or query.QUARANTINE or diagnostics._QUARANTINE:
                if original is None:
                    original = origin.OriginError("BOOTSTRAP_QUERY_UNKNOWN")
                owner.error("recipient-native-query", original, unknown=True)
        if original is not None:
            raise original
        require(type(result) is I.Admission and result == admitted, "BOOTSTRAP_RECIPIENT_READMISSION")
        # The actual supplier returned after its finalizer. Its provisional
        # session bytes alone could not attest that later close/return.
        owner.work_limit = final
        owner.end()
        retained = owner.open(directory)
        require(load_admission(owner, retained) == result, "BOOTSTRAP_RECIPIENT_READMISSION_CHANGED")
        session = owner.read(retained, "session-result.json")
        returned = origin.encoded({"admissionSha256": origin.digest(result.record), "sessionSha256": origin.digest(session),
            "clock": origin.clock_value(window.clock), "returnedNs": window.now(limit=final)})
        owner.write(phase_directory, "admission-return.json", returned)
        originals = (result, session, returned)
        owner.admissions[str(directory)] = originals
        return retained, originals
    finally:
        owner.work_limit, owner.final_limit = limits


def _recipient_admission_readback(owner, directory, phase_directory, originals):
    require(owner.admissions.get(str(directory.path)) is originals, "BOOTSTRAP_RECIPIENT_NOT_CURRENT_ADMISSION")
    admitted, session, returned = originals
    require(load_admission(owner, directory) == admitted and owner.read(directory, "session-result.json") == session and
            owner.read(phase_directory, "admission-return.json") == returned, "BOOTSTRAP_RECIPIENT_ADMISSION_ORIGINALS_CHANGED")


def _recipient_supplier_record(recipient, work, admitted, job):
    """Bind the actual returned supplier object; do not reconstruct success."""
    if os.name == "nt":
        require(type(recipient) is diagnostics.Recipient and recipient.work is work and recipient.job_id == job,
                "BOOTSTRAP_RECIPIENT_NATIVE_RETURN")
    else:
        require(type(recipient) is posix.Recipient and recipient.work_dir == work.path and
                recipient.home == work.path / "gnupg", "BOOTSTRAP_RECIPIENT_NATIVE_RETURN")
    work.verify()
    require(recipient.work_identity == work.identity and recipient.key_sha256 == admitted.key_sha256 and
            recipient.fingerprint == admitted.fingerprint.upper() and type(recipient.encryption_fingerprint) is str and
            re.fullmatch(r"[0-9A-F]{40}", recipient.encryption_fingerprint) and type(recipient.expires_at) is int and
            0 <= recipient.expires_at and (recipient.expires_at == 0 or admitted.expires_at <= recipient.expires_at),
            "BOOTSTRAP_RECIPIENT_KEY_OR_POLICY_CHANGED")
    names = ("fingerprint", "encryption_fingerprint", "expires_at", "key_sha256", "work_identity")
    value = {name: getattr(recipient, name) for name in names}
    value["executable"] = str(recipient.executable)
    if os.name == "nt":
        value.update(executable_sha256=recipient.executable_sha256, job_id=recipient.job_id)
    return value


def recipient_child(context_hash, minimum, cancelled):
    """Executable child of the dormant internal recipient-only transaction.

    Supplied context alone cannot attest its parent, native240/final45 or read30.
    Validation does not authorize the routine custodian or any producer/cache.
    """
    recipient_command(context_hash, minimum)
    local_start = time.monotonic()
    first = origin.clocks.validate_reading(origin.clocks.observe())
    require(first.nanoseconds >= origin.integer(minimum), "BOOTSTRAP_RECIPIENT_PRECEDES_LAUNCH")
    metadata_window = _RecipientWindow(first, first.nanoseconds, local_start, None,
                                       lambda: cancellation(cancelled), metadata=True)
    metadata = Owner(metadata_window.local_end, metadata_window, first=first, cancelled=metadata_window.cancelled)
    owner, target, window, result_raw, original, recipient = metadata, None, None, None, None, None
    try:
        initial = _recipient_inputs(metadata, context_hash, minimum)
        target = initial["handles"]["recipient-validation"]
        metadata.close()
        if metadata.original is not None:
            raise metadata.original
        require(not metadata.unknown and all(row["attempted"] is True and row["closed"] is True
                for row in metadata.resources), "BOOTSTRAP_RECIPIENT_METADATA_CLOSE")
        window = _RecipientWindow(first, metadata_window.last, local_start, initial["start"]["workEndNs"],
                                  lambda: cancellation(cancelled))
        window.now()
        # A separate owner, not Owner.bind/local45 renewal. The new owner's
        # inclusive end was fixed by the FIRST child observation above.
        owner = Owner(window.local_end, window, first=first, cancelled=window.cancelled)
        target = None
        current = _recipient_inputs(owner, context_hash, minimum)
        require(current["binding"] == initial["binding"], "BOOTSTRAP_RECIPIENT_METADATA_CHANGED")
        target = current["handles"]["recipient-validation"]
        private, work = current["handles"]["session"], current["handles"]["crypto"]
        admission_directory, admission_originals = _recipient_admit(owner, private.path / "recipient-admission", target,
                                                                   current["admitted"])
        _recipient_admission_readback(owner, admission_directory, target, admission_originals)
        require(_recipient_inputs(owner, context_hash, minimum)["binding"] == initial["binding"],
                "BOOTSTRAP_RECIPIENT_ORIGINALS_CHANGED")
        window.now()
        checked = admission_originals[0]
        # Both existing suppliers are synchronous60. The enclosing native
        # parent is essential to stop an overrun/descendant. No inline deadline
        # observation or child ACK claims to supply that enclosing enforcement.
        if os.name == "nt":
            recipient = diagnostics.validate_recipient(checked.public_key, checked.fingerprint, work,
                                                       job_id=current["context"]["job"])
        else:
            recipient = posix.validate_recipient(admission_directory.path / "recipient-public.asc", checked.fingerprint, work.path)
        if diagnostics._QUARANTINE:
            error = origin.OriginError("BOOTSTRAP_RECIPIENT_SUPPLIER_UNKNOWN")
            owner.error("recipient-supplier", error, unknown=True)
            raise error
        returned_ns = window.now()
        value = _recipient_supplier_record(recipient, work, checked, current["context"]["job"])
        _recipient_admission_readback(owner, admission_directory, target, admission_originals)
        require(_recipient_inputs(owner, context_hash, minimum)["binding"] == initial["binding"],
                "BOOTSTRAP_RECIPIENT_ORIGINALS_CHANGED")
        result_raw = owner.write(target, "child-result.json", {"schema": 1, "scope": RECIPIENT_SCOPE,
            "contextSha256": context_hash, "startSha256": origin.digest(current["raws"]["start"]),
            "proposalSha256": origin.digest(current["raws"]["proposal"]),
            "admissionReturnSha256": origin.digest(admission_originals[2]), "recipient": value,
            "clock": origin.clock_value(window.clock), "invocation": current["start"]["invocation"],
            "launchMinimumNs": minimum, "beganNs": first.nanoseconds, "metadataLastNs": metadata_window.last,
            "supplierReturnedNs": returned_ns, "completedNs": window.now(minimum=returned_ns),
            "supplierReturned": True, "childResourceClose": "PENDING_CLOSE", "parentRetirement": "NOT_OBSERVED_HERE",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        require(_recipient_inputs(owner, context_hash, minimum)["binding"] == initial["binding"] and
                owner.read(target, "child-result.json") == result_raw, "BOOTSTRAP_RECIPIENT_TERMINAL_CHANGED")
    except BaseException as error:
        # Owner.close records the first error before raising its later UNKNOWN
        # wrapper, including during metadata handover. Keep that original.
        original = error if owner.original is None else owner.original
        supplier_unknown = (isinstance(error, diagnostics.WindowsEvidenceError) and
                            error.retirement_unknown is not False)
        owner.error("recipient-child", error,
                    unknown=supplier_unknown or bool(diagnostics._QUARANTINE or query.QUARANTINE))
        if target is not None and not owner.closed and not owner.unknown:
            try:
                owner.write(target, "child-failure.json", {"schema": 1, "result": "HOLD", "errors": owner.errors,
                    "childResourceClose": "PENDING_CLOSE", "parentRetirement": "NOT_OBSERVED_HERE",
                    "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}, final=True)
            except BaseException as secondary:
                owner.error("recipient-failure-retention", secondary)
    finally:
        # Strong local owner references, not fields in caller-supplied records.
        # No new failure owner, overwrite, retry or postclose file acquisition.
        for actual in (owner,) if owner is metadata else (owner, metadata):
            try:
                actual.close()
            except BaseException as error:
                if original is None:
                    original = error if actual.original is None else actual.original
            if original is None:
                original = actual.original
    if original is not None:
        raise original
    require(window is not None and result_raw is not None and not owner.unknown and
            all(row["attempted"] is True and row["closed"] is True for row in owner.resources),
            "BOOTSTRAP_RECIPIENT_CHILD_INCOMPLETE")
    cancellation(cancelled)
    closed_ns = window.now()
    return {"schema": 1, "scope": RECIPIENT_ACK_SCOPE, "invocation": current["start"]["invocation"],
            "terminalSha256": origin.digest(result_raw), "clock": origin.clock_value(window.clock), "closedNs": closed_ns,
            "childResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "parentRetirement": "NOT_OBSERVED_HERE",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}, window, window.final


@dataclass(frozen=True)
class RecipientPrefix:
    """Private finalized evidence only; no live Recipient or next-phase authority."""
    raw: bytes = field(repr=False)
    pending_raw: bytes = field(repr=False)
    originals: tuple = field(repr=False)
    checked_ns: int = field(repr=False)


@dataclass(frozen=True)
class _RecipientParentBindings:
    owner: object
    window: object
    first: object
    callback: object
    local_start: float
    local_end: float
    admissions: object
    resources: object
    errors: object
    # Independent strong references: a callback-replaced row/list cannot erase
    # a returned resource, or redirect cleanup through call.owner/transition.
    seen: list = field(default_factory=list)
    window_state: list = field(default_factory=list)
    observations: list = field(default_factory=list)
    files: list = field(default_factory=list)
    close_roster: list = field(default_factory=list)
    handler_rows: list = field(default_factory=list)
    handler_restored: list = field(default_factory=list)
    initialization: list = field(default_factory=list)


@dataclass(eq=False)
class _RecipientResource:
    row: object
    label: object
    resource: object
    attempted: bool = False
    closed: bool = False


def _recipient_predecessor_pins(transition):
    previous = transition._attempt
    return ((transition.raw, transition._preclose_ns, transition._closed_ns, transition._checked_ns,
             previous.pending_raw, previous.preparation, tuple(previous.target_identity)),
            (previous, previous.transition, previous.owner, previous.window, previous.admitted,
             previous.admission_originals, previous.snapshot, previous.first, previous.bindings))


@dataclass(frozen=True)
class _RecipientPredecessorGraph:
    """Exact closed-graph pins between complete predecessor validations.

    Compile the already validated transitive graph once, then compare EVERY
    edge at EVERY boundary. This is not a successful-result cache: replacing a
    nested reference, changing a typed scalar or mutating a container refuses
    before another supplier. Cycles retain strong references. No clock, file,
    resource method or cancellation callback is called here.

    Only the known source-owned record/Owner/Fence types are traversed. Opaque
    callbacks/resources retain identity/type; the path properties actually used
    by the full validator are independently rechecked with its original path
    and registry-key semantics. Like the full checker, this is not a sandbox
    against arbitrary code replacement inside the Python process.
    """
    transition: object = field(repr=False)
    registry: object = field(repr=False)
    registered: object = field(repr=False)
    registry_key: int = field(repr=False)
    paths: tuple = field(repr=False)
    nodes: tuple = field(repr=False)

    @staticmethod
    def path_values(transition):
        attempt, old = transition._attempt, transition._attempt.transition
        paths = _new_entry_paths(attempt)  # Original equality checks, not string-only replacement.
        values = (ROOT, old._entry._private.path, old._entry._target.path, *paths)
        require(all(type(value) is type(ROOT) for value in values), "BOOTSTRAP_RECIPIENT_PREDECESSOR_PATH_KIND")
        return (tuple((type(value), str(value), tuple(value.parts), value.drive, value.root) for value in values),
                str(old._entry._target.path / "admission"), str(paths[2] / "admission"))

    @classmethod
    def capture(cls, transition):
        registered = _entry_attempt_record(transition._attempt)
        key = id(transition._attempt.transition)
        require(type(_ENTRY_ATTEMPTS) is dict and _ENTRY_ATTEMPTS.get(key) is registered,
                "BOOTSTRAP_RECIPIENT_PREDECESSOR_REGISTRY")
        traversed = (NewEntryTransition, _EntryAttempt, ClosedEntryTransition, OriginalEntry, OriginalPhase,
                     Owner, origin.Fence, _NewEntryWindow, I.Admission, origin.clocks.Reading, origin.clocks.ClockIdentity)
        scalars = (type(None), bool, int, float, str, bytes)
        pending, seen, nodes = [transition, registered], set(), []
        while pending:
            value = pending.pop()
            kind = type(value)
            if kind in scalars or id(value) in seen:
                continue
            seen.add(id(value))
            require(len(seen) <= 10000, "BOOTSTRAP_RECIPIENT_PREDECESSOR_GRAPH_LIMIT")
            if kind is dict:
                saved = tuple(value.items())
                require(all(type(key) in scalars for key, _ in saved), "BOOTSTRAP_RECIPIENT_PREDECESSOR_KEY_KIND")
                pending.extend(item for pair in saved for item in pair)
                mode = "mapping"
            elif kind in (list, tuple):
                saved, mode = tuple(value), "sequence"
                pending.extend(saved)
            elif kind in traversed:
                saved, mode = object.__getattribute__(value, "__dict__"), "record"
                pending.append(saved)
            else:
                saved, mode = None, "opaque"
            nodes.append((value, kind, mode, saved))
        result = cls(transition, _ENTRY_ATTEMPTS, registered, key, cls.path_values(transition), tuple(nodes))
        result.checked(transition)
        return result

    def checked(self, transition):
        require(type(self) is _RecipientPredecessorGraph and transition is self.transition and
                _ENTRY_ATTEMPTS is self.registry and self.registry.get(self.registry_key) is self.registered and
                _entry_attempt_record(transition._attempt) is self.registered,
                "BOOTSTRAP_RECIPIENT_PREDECESSOR_REGISTRY")
        scalars = (type(None), bool, int, float, str, bytes)
        def same(actual, original):
            return actual is original or (type(actual) is type(original) and type(original) in scalars and actual == original)
        for value, kind, mode, saved in self.nodes:
            require(type(value) is kind, "BOOTSTRAP_RECIPIENT_PREDECESSOR_CHANGED")
            if mode == "record":
                valid = object.__getattribute__(value, "__dict__") is saved
            elif mode == "mapping":
                valid = len(value) == len(saved) and all(same(key, old_key) and same(item, old_item)
                    for (key, item), (old_key, old_item) in zip(value.items(), saved))
            elif mode == "sequence":
                valid = len(value) == len(saved) and all(same(item, old) for item, old in zip(value, saved))
            else:
                valid = mode == "opaque"
            require(valid, "BOOTSTRAP_RECIPIENT_PREDECESSOR_CHANGED")
        require(self.path_values(transition) == self.paths, "BOOTSTRAP_RECIPIENT_PREDECESSOR_PATH_CHANGED")


@dataclass(frozen=True)
class _ParentControl:
    """Published in-call bindings, not the storage of cleanup responsibility.

    A frozen dataclass still exposes mutable fields through __dict__ and
    object.__setattr__. The separate private tuple below retains the originals;
    replacing this publication OR one of its fields cannot erase them. This is
    finite input binding, not a sandbox against Python/closure-code replacement.
    """
    call: object
    registry: object
    key: int
    record: tuple
    handoff_pin: tuple = ()
    handlers: tuple = ()


def _original_parent_controls():
    """Encapsulate originals; module/call aliases are never cleanup authority.

    No mutable container escapes. Each saved frame is an immutable tuple with
    separate original record/handoff/handler references, NOT the published
    dataclass as another mutable holder. Only the existing staged source binds
    and pre-install handler retention may replace a frame, before suppliers.
    """
    originals = {}
    def register(control):
        require(type(control) is _ParentControl and id(control.call) not in originals,
                "BOOTSTRAP_PARENT_CONTROL_ALREADY_REGISTERED")
        originals[id(control.call)] = (control, control.call, control.registry, control.key,
                                        control.record, control.handoff_pin, control.handlers)
    def frame(call):
        saved = originals.get(id(call))
        require(type(saved) is tuple and len(saved) == 7 and saved[1] is call,
                "BOOTSTRAP_RECIPIENT_NOT_CLAIMED")
        return saved
    def lookup(call):
        return frame(call)[0]
    def unchanged(call, control):
        saved = frame(call)
        require(_parent_control(call) is control and saved[0] is control and
                _PARENT_CONTROLS.get(id(call)) is control and
                saved[2] is (_RECIPIENT_ATTEMPTS if type(call) is _RecipientParent else _INITIALIZER_ATTEMPTS) and
                saved[2].get(saved[3]) is saved[4], "BOOTSTRAP_PARENT_CONTROL_CHANGED")
        return saved
    def bind(call, control, record):
        saved = unchanged(call, control)
        old = saved[4]
        require(type(record) is tuple and len(record) == len(old) and
                all(new is previous for new, previous in zip(record[:3], old[:3])),
                "BOOTSTRAP_PARENT_CONTROL_BINDING")
        if old[3] is None:
            require(type(record[3]) is _RecipientParentBindings and record[3] is call.bindings and
                    all(new is previous for new, previous in zip(record[4:], old[4:])),
                    "BOOTSTRAP_PARENT_CONTROL_BINDING")
        else:
            require(type(call) is _InitializerParent and old[5] is None and record[3] is old[3] and
                    record[4] is old[4] and type(record[5]) is tuple and len(record[5]) == 2 and
                    type(record[5][0]) is _InitializationInputs, "BOOTSTRAP_PARENT_CONTROL_BINDING")
        saved[2][saved[3]] = record
        object.__setattr__(control, "record", record)
        originals[id(call)] = (*saved[:4], record, *saved[5:])
    def handler(call, control, number, previous):
        saved = unchanged(call, control)
        numbers = (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else []))
        require(len(saved[6]) < len(numbers) and number is numbers[len(saved[6])],
                "BOOTSTRAP_PARENT_HANDLER_BINDING")
        handlers = (*saved[6], (number, previous))
        object.__setattr__(control, "handlers", handlers)
        originals[id(call)] = (*saved[:6], handlers)
    return register, lookup, frame, bind, handler


(_register_parent_control, _original_parent_control, _original_parent_frame,
 _bind_parent_control, _retain_parent_handler) = _original_parent_controls()
del _original_parent_controls


def _parent_originals(call):
    # Closed source-owned pairs only; never virtual/caller-selected registries.
    if type(call) is _RecipientParent:
        width = 5
    elif type(call) is _InitializerParent:
        width = 6
    else:
        raise origin.OriginError("BOOTSTRAP_RECIPIENT_NOT_CLAIMED")
    saved = _original_parent_frame(call)
    require(type(saved[2]) is dict and type(saved[4]) is tuple and len(saved[4]) == width and saved[4][1] is call,
            "BOOTSTRAP_RECIPIENT_NOT_CLAIMED")
    return saved


def _parent_control(call):
    # Strict published-field validation is for live work ONLY. Cleanup must
    # not repeat a rejected publication at every resource until error64/UNKNOWN.
    saved = _parent_originals(call)
    control = saved[0]
    require(type(control) is _ParentControl and control.call is saved[1] and control.registry is saved[2] and
            type(control.key) is type(saved[3]) and control.key == saved[3] and control.record is saved[4] and
            control.handoff_pin is saved[5] and control.handlers is saved[6],
            "BOOTSTRAP_PARENT_CONTROL_CHANGED")
    return control


def _recipient_parent_registration(call):
    # Never redirect cleanup through a rejected registry/parent alias. Live
    # checks separately require the public-in-module registry to match exactly.
    return _parent_originals(call)[4]


def _parent_parameters(call):
    """No phase/registry/command input and no subclass fallback."""
    if type(call) is _RecipientParent:
        return (_RecipientParentWindow, 240, 285, 315,
                ("recipient-validation", "recipient-final", "recipient-read"))
    require(type(call) is _InitializerParent, "BOOTSTRAP_RECIPIENT_NOT_CLAIMED")
    return (_InitializerWindow, 120, 165, 195,
            ("canonical-init", "canonical-init-final", "canonical-init-read"))


def _parent_location(call):
    call.check()
    if type(call) is _RecipientParent:
        result = ("recipient-validation", call.paths()[3])
    else:
        require(type(call) is _InitializerParent, "BOOTSTRAP_RECIPIENT_NOT_CLAIMED")
        result = ("canonical-init", call.paths()[3] / "initializer")
    call.check()
    return result


def _parent_environment(call):
    call.check()
    path = _parent_location(call)[1]
    result = recipient_environment(path)
    if type(call) is _InitializerParent:
        result.update(call.init_inputs().toolchains.environment())
    call.check()
    return result


def _parent_argv(call, minimum=None):
    call.check()
    if type(call) is _RecipientParent:
        result = recipient_command(origin.digest(call.records["context"]), minimum)
    else:
        require(type(call) is _InitializerParent, "BOOTSTRAP_RECIPIENT_NOT_CLAIMED")
        call.request_unchanged()
        # Canonical init has no --minimum-ns option. Its outer parent retains
        # the original launch observation; the command is NOT recipient argv.
        result = origin.parse(call.init_inputs().request_raw)["argv"]
    call.check()
    return result


@dataclass(frozen=True)
class _RecipientParentWindow:
    """Distinct work240/final45/read30 ownership, never an old entry renewal.

    Finalization is capped by BOTH first+285 and actual-final-start+45.
    Readback starts only after native/writer close, has its own start+30, and
    also stays inside first+315 and the original cumulative proposal/job fence.
    These are unadmitted source caps. Synchronous OS calls are not real-time
    cancellable; late returns fail and known-owner cleanup is still attempted.
    """
    call: object = field(repr=False, compare=False)
    clock: object = field(init=False)
    first: int = field(init=False)
    work: int = field(init=False)
    native_end: int = field(init=False)
    prefix_end: int = field(init=False)
    work_local: float = field(init=False)
    native_local: float = field(init=False)
    local_end: float = field(init=False)
    last: int = field(init=False)
    local_last: float = field(init=False)
    phase: str = field(default="WORK", init=False)
    final_started: object = field(default=None, init=False)
    final_local_start: object = field(default=None, init=False)
    final: int = field(init=False)
    final_local: float = field(init=False)
    read_started: object = field(default=None, init=False)
    read_local_start: object = field(default=None, init=False)
    read_attempted: bool = field(default=False, init=False)
    read_end: object = field(default=None, init=False)
    read_local: object = field(default=None, init=False)

    def __post_init__(self):
        self.call.check()
        clock, began, work, final, end, work_local, native_local, local_end = self.limits()
        for name, value in (("clock", clock), ("first", began), ("work", work), ("native_end", final),
                ("prefix_end", end), ("work_local", work_local), ("native_local", native_local),
                ("local_end", local_end), ("last", began), ("local_last", self.call.local_start),
                ("final", final), ("final_local", native_local)):
            object.__setattr__(self, name, value)

    def limits(self, *, cleanup=False):
        # Rederive static limits from the exact closed predecessor, not mutable
        # phase fields. Both RAW and independently projected LOCAL caps apply.
        registered = _recipient_parent_registration(self.call)
        bound = registered[3]
        require(type(cleanup) is bool and (not cleanup or bound is not None),
                "BOOTSTRAP_RECIPIENT_CLEANUP_NOT_BOUND")
        first = origin.clocks.validate_reading(bound.first if cleanup else self.call.first)
        previous = registered[0] if cleanup else self.call.transition
        predecessor_ns = previous._checked_ns if type(self.call) is _RecipientParent else registered[4].checked_ns
        require(first.clock == previous._attempt.window.clock and first.nanoseconds >= predecessor_ns,
                "BOOTSTRAP_RECIPIENT_PARENT_FIRST_CLOCK")
        local = bound.local_start if cleanup else self.call.local_start
        require(type(local) in (int, float) and math.isfinite(local) and local >= 0,
                "BOOTSTRAP_RECIPIENT_PARENT_LOCAL_CLOCK")
        if type(self.call) is _InitializerParent:
            require(local >= registered[4].local_last, "BOOTSTRAP_INIT_LOCAL_PREDECESSOR")
        proposal = origin.parse(previous._attempt.transition.proposal_raw)
        fences, job_end = proposal["phaseFencesNs"], proposal["proposedJobEndNs"]
        began = first.nanoseconds
        _kind, work_seconds, native_seconds, prefix_seconds, names = _parent_parameters(self.call)
        work = min(origin.integer(began + work_seconds * origin.NS), fences[names[0]], job_end)
        final = min(origin.integer(began + native_seconds * origin.NS), fences[names[1]], job_end)
        end = min(origin.integer(began + prefix_seconds * origin.NS), fences[names[2]], job_end)
        require(began < work <= final <= end, "BOOTSTRAP_RECIPIENT_PARENT_NO_INTERVAL")
        return (first.clock, began, work, final, end,
                origin.wire._directed_deadline(local, work_seconds, work, began),
                origin.wire._directed_deadline(local, native_seconds, final, began),
                origin.wire._directed_deadline(local, prefix_seconds, end, began))

    def phase_state(self):
        return (self.phase, self.final_started, self.final_local_start, self.final, self.final_local,
                self.read_attempted, self.read_started, self.read_local_start, self.read_end, self.read_local)

    def remember_phase(self):
        _recipient_parent_registration(self.call)[3].window_state[:] = [self.phase_state()]

    def checked(self, *, cleanup=False):
        self.call.check(cleanup=cleanup)  # Retain actual resources BEFORE any clock/callback.
        bound = _recipient_parent_registration(self.call)[3]
        actual = (self.clock, self.first, self.work, self.native_end, self.prefix_end,
                  self.work_local, self.native_local, self.local_end)
        expected = self.limits(cleanup=cleanup)
        require(type(self) is _parent_parameters(self.call)[0] and bound is not None and bound.window is self and
                (cleanup or self.call.window is self) and
                all(type(a) is type(b) and a == b for a, b in zip(actual, expected)) and
                type(self.last) is int and self.first <= self.last <= origin.clocks.UINT64 and
                type(self.local_last) in (int, float) and math.isfinite(self.local_last) and
                self.local_last >= bound.local_start and bound.observations == [self.last, self.local_last] and
                bound.window_state == [self.phase_state()] and self.phase in ("WORK", "FINAL", "READ"),
                "BOOTSTRAP_RECIPIENT_PARENT_WINDOW_CHANGED")
        if self.phase == "WORK":
            expected_final = (None, None, self.native_end, self.native_local)
            require(self.read_attempted is False, "BOOTSTRAP_RECIPIENT_PARENT_PHASE_CHANGED")
        elif self.final_started is None:
            # Failed final-start observation is a permanently expired sentinel,
            # not a fictional actual start or a renewable cleanup45.
            expected_final = (None, None, 0, 0.0)
        else:
            began = origin.integer(self.final_started, self.first)
            end = min(self.native_end, origin.integer(began + 45 * origin.NS))
            expected_final = (began, self.final_local_start, end, min(self.native_local,
                origin.wire._directed_deadline(self.final_local_start, 45, end, began)))
        require((self.final_started, self.final_local_start, self.final, self.final_local) == expected_final and
                type(self.read_attempted) is bool, "BOOTSTRAP_RECIPIENT_PARENT_PHASE_CHANGED")
        if self.phase == "READ":
            began = origin.integer(self.read_started, self.final_started)
            end = min(self.prefix_end, origin.integer(began + 30 * origin.NS))
            require(self.read_attempted and began < self.final and self.read_local_start < self.final_local and
                    self.read_end == end and self.read_local == min(self.local_end,
                        origin.wire._directed_deadline(self.read_local_start, 30, end, began)),
                    "BOOTSTRAP_RECIPIENT_PARENT_PHASE_CHANGED")
        else:
            require((self.read_started, self.read_local_start, self.read_end, self.read_local) == (None,) * 4,
                    "BOOTSTRAP_RECIPIENT_PARENT_PHASE_CHANGED")
        return self

    def local_now(self, *, cleanup=False):
        self.checked(cleanup=cleanup)
        local = time.monotonic()
        require(type(local) in (int, float) and math.isfinite(local) and local >= self.local_last,
                "BOOTSTRAP_RECIPIENT_PARENT_LOCAL_CLOCK")
        object.__setattr__(self, "local_last", local)
        _recipient_parent_registration(self.call)[3].observations[1] = local
        self.checked(cleanup=cleanup)
        return local

    def raw_now(self, minimum=0, *, cleanup=False):
        observed = origin.clocks.checked_now(self.clock, minimum_ns=max(self.last, origin.integer(minimum)))
        object.__setattr__(self, "last", observed)  # Before any later check can fail.
        _recipient_parent_registration(self.call)[3].observations[0] = observed
        self.checked(cleanup=cleanup)
        return observed

    def now(self, *, final=False, minimum=0, limit=None):
        # Final observations are cleanup-only, never permission to acquire.
        # Owner.close_fence must still inspect the original known frame after
        # an execution alias changes; repeating that alias refusal per resource
        # could otherwise saturate diagnostics and truncate known cleanup.
        # Owner.end -> deadline keeps STRICT entry/exit checks, even final=True.
        self.checked(cleanup=final)
        require(type(final) is bool and self.call.state not in ("COMPLETE", "FAILED") and
                (self.phase != "FINAL" or final), "BOOTSTRAP_RECIPIENT_PARENT_NOT_LIVE")
        observed = self.raw_now(minimum, cleanup=final)
        end = self.read_end if self.phase == "READ" else self.final if final else self.work
        if limit is not None:
            end = min(end, origin.integer(limit))
        require(observed < end, "BOOTSTRAP_RECIPIENT_PARENT_EXPIRED")
        local = self.local_now(cleanup=final)
        require(local < (self.read_local if self.phase == "READ" else self.final_local if final else self.work_local),
                "BOOTSTRAP_RECIPIENT_PARENT_LOCAL_EXPIRED")
        if not final:
            self.call.cancel()
            # Cancellation callbacks are suppliers too. Their successful return
            # cannot authorize a prefix using observations made before them.
            # No callback follows these final RAW/LOCAL observations.
            observed = self.raw_now(minimum=observed)
            require(observed < end, "BOOTSTRAP_RECIPIENT_PARENT_EXPIRED")
            local = self.local_now()
            require(local < (self.read_local if self.phase == "READ" else self.work_local),
                    "BOOTSTRAP_RECIPIENT_PARENT_LOCAL_EXPIRED")
        self.checked(cleanup=final)
        require(self.last == observed, "BOOTSTRAP_RECIPIENT_PARENT_HIGHWATER_CHANGED")
        return observed

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(maximum) in (int, float) and 0 < maximum <= _parent_parameters(self.call)[3] and math.isfinite(maximum),
                "BOOTSTRAP_RECIPIENT_PARENT_MAXIMUM")
        self.checked()
        local = self.local_now()
        observed = self.now(final=final, limit=limit)
        end = self.read_end if self.phase == "READ" else self.final if final else self.work
        if limit is not None:
            end = min(end, origin.integer(limit))
        cap = self.read_local if self.phase == "READ" else self.final_local if final else self.work_local
        result = min(cap, origin.wire._directed_deadline(local, maximum, end, observed))
        self.checked()
        return result

    def cleanup_deadline(self, maximum):
        """Only an already-owned native drain; NEVER Owner.end/file admission."""
        require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 45,
                "BOOTSTRAP_RECIPIENT_CLEANUP_MAXIMUM")
        self.checked(cleanup=True)
        local = self.local_now(cleanup=True)
        observed = self.now(final=True)
        end = self.read_end if self.phase == "READ" else self.final
        cap = self.read_local if self.phase == "READ" else self.final_local
        result = min(cap, origin.wire._directed_deadline(local, maximum, end, observed))
        self.checked(cleanup=True)
        return result

    def begin_final(self):
        # Mark once, before suppliers. Failed observation leaves an EXPIRED cap,
        # never a new45 on the next cleanup attempt or a invented actual start.
        self.checked(cleanup=True)
        require(self.phase == "WORK", "BOOTSTRAP_RECIPIENT_FINAL_REENTRY")
        object.__setattr__(self, "phase", "FINAL")
        object.__setattr__(self, "final", 0)
        object.__setattr__(self, "final_local", 0.0)
        self.remember_phase()
        local = self.local_now(cleanup=True)
        observed = self.raw_now(cleanup=True)
        object.__setattr__(self, "final_started", observed)
        object.__setattr__(self, "final_local_start", local)
        end = min(self.native_end, origin.integer(observed + 45 * origin.NS))
        object.__setattr__(self, "final", end)
        object.__setattr__(self, "final_local", min(self.native_local,
            origin.wire._directed_deadline(local, 45, end, observed)))
        self.remember_phase()
        self.now(final=True)

    def begin_read(self):
        self.checked()
        require(self.phase == "FINAL" and not self.read_attempted and self.call.native_retired and
                self.call.captures_retired and self.call.original is None and not self.call.unknown,
                "BOOTSTRAP_RECIPIENT_READ_BEFORE_RETIREMENT")
        self.call.phase_writers_closed()
        self.now(final=True)
        object.__setattr__(self, "read_attempted", True)
        self.remember_phase()
        local = self.local_now()
        observed = self.raw_now()
        require(observed < self.final and local < self.final_local, "BOOTSTRAP_RECIPIENT_READ_START_EXPIRED")
        object.__setattr__(self, "read_started", observed)
        object.__setattr__(self, "read_local_start", local)
        end = min(self.prefix_end, origin.integer(observed + 30 * origin.NS))
        object.__setattr__(self, "read_end", end)
        object.__setattr__(self, "read_local", min(self.local_end,
            origin.wire._directed_deadline(local, 30, end, observed)))
        object.__setattr__(self, "phase", "READ")
        self.remember_phase()
        self.now()

    def record(self):
        self.checked()
        return {"clock": origin.clock_value(self.clock), "firstNs": self.first, "workEndNs": self.work,
                "nativeEndNs": self.native_end, "prefixEndNs": self.prefix_end,
                "finalStartedNs": self.final_started, "finalEndNs": self.final,
                "readStartedNs": self.read_started, "readEndNs": self.read_end,
                "budgetAcceptance": "NOT_ADMITTED"}


@dataclass(frozen=True)
class _RecipientParentReader:
    """Historical chain under THIS new live owner, not a disguised old reader."""
    call: object = field(repr=False, compare=False)
    owner: object = field(init=False, repr=False, compare=False)
    current: object = field(init=False, repr=False, compare=False)
    past: object = field(init=False, repr=False)
    first: object = field(init=False, repr=False)

    def __post_init__(self):
        owner = self.call.live()
        old = self.call.transition._attempt.transition
        for name, value in (("owner", owner), ("current", self.call.window),
                            ("past", history.snapshot(old._fence)), ("first", old._limits[8])):
            object.__setattr__(self, name, value)

    def checked(self):
        require(self.call.live() is self.owner and self.current is self.call.window and
                self.first is self.call.transition._attempt.transition._limits[8] and
                history.checked(self.past) == history.snapshot(self.call.transition._attempt.transition._fence),
                "BOOTSTRAP_RECIPIENT_READER_CHANGED")
        return self

    def observe(self, *, final, minimum):
        self.checked()
        return self.current.now(final=final, minimum=minimum)


@dataclass(eq=False)
class _RecipientParent:
    transition: object = field(repr=False)
    originals: tuple = field(repr=False)
    state: str = "CLAIMED"
    local_start: object = None
    first: object = field(default=None, repr=False)
    window: object = field(default=None, repr=False)
    owner: object = field(default=None, repr=False)
    bindings: object = field(default=None, repr=False)
    callback: object = field(default=None, repr=False)
    cancelled: list = field(default_factory=list, repr=False)
    handlers: dict = field(default_factory=dict, repr=False)
    handles: dict = field(default_factory=dict, repr=False)
    identities: dict = field(default_factory=dict, repr=False)
    records: dict = field(default_factory=dict, repr=False)
    row: dict = field(default_factory=dict, repr=False)
    original: object = field(default=None, repr=False)
    errors: list = field(default_factory=list, repr=False)
    unknown: bool = False
    native_retired: bool = False
    captures_retired: bool = False
    child_accepted: bool = False
    pending_raw: object = field(default=None, repr=False)
    failure_custody: str = "UNAVAILABLE"
    result: object = field(default=None, repr=False)

    def actual_owner(self):
        bound = _recipient_parent_registration(self)[3]
        return None if bound is None else bound.owner

    def roster(self):
        bound = _recipient_parent_registration(self)[3]
        if bound is None:
            return
        owner = bound.owner
        try:
            # Capture returned resources from the original list even if a later
            # callback has rebound owner.resources. Retain suspicious new rows
            # too, but never use them to erase earlier close responsibility.
            seen = {(id(pin.row), id(pin.resource)) for pin in bound.seen}
            for rows in (bound.resources,) if owner.resources is bound.resources else (bound.resources, owner.resources):
                if type(rows) is list:
                    for row in rows:
                        label, resource = (row.get("label"), row.get("owner")) if type(row) is dict else (None, None)
                        if (id(row), id(resource)) not in seen:
                            bound.seen.append(_RecipientResource(row, label, resource))
                            seen.add((id(row), id(resource)))
            require(type(owner.resources) is list and owner.resources is bound.resources and
                    len(owner.resources) == len(bound.seen), "BOOTSTRAP_RECIPIENT_PARENT_ROSTER")
            # Retain late rows above, but NEVER learn a larger successful roster
            # during/after close. Flags on an unobserved late row prove nothing.
            require(len(bound.close_roster) <= 1 and (not owner.closed or len(bound.close_roster) == 1),
                    "BOOTSTRAP_RECIPIENT_PARENT_CLOSE_ROSTER")
            if bound.close_roster:
                frozen = bound.close_roster[0]
                require(len(owner.resources) == len(frozen) and all(current is row and
                        row.get("label") == label and row.get("owner") is resource
                        for current, (row, label, resource) in zip(owner.resources, frozen)),
                        "BOOTSTRAP_RECIPIENT_PARENT_CLOSE_ROSTER")
            for current, pin in zip(owner.resources, bound.seen):
                row = pin.row
                require(current is row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                        row["label"] == pin.label and pin.label in ("directory", "writer", "stdout", "stderr", "native-scope") and
                        row["owner"] is pin.resource and type(row["attempted"]) is bool and type(row["closed"]) is bool and
                        (not row["closed"] or row["attempted"]) and (not pin.attempted or row["attempted"]) and
                        (not pin.closed or row["closed"]), "BOOTSTRAP_RECIPIENT_PARENT_ROSTER")
                pin.attempted, pin.closed = row["attempted"], row["closed"]
        except BaseException as error:
            self.error("recipient-roster", error, unknown=True)
            raise

    def check(self, *, full=False, cleanup=False):
        require(type(cleanup) is bool, "BOOTSTRAP_RECIPIENT_CHECK_MODE")
        registered = _recipient_parent_registration(self)
        self.roster()
        if QUARANTINE or query.QUARANTINE or diagnostics._QUARANTINE:
            error = origin.OriginError("BOOTSTRAP_RECIPIENT_PARENT_PRIOR_UNKNOWN")
            self.error("recipient-global-uncertainty", error, unknown=True)
            raise self.original
        if not cleanup:
            control = _parent_control(self)
            registry = _RECIPIENT_ATTEMPTS if type(self) is _RecipientParent else _INITIALIZER_ATTEMPTS
            require(_PARENT_CONTROLS.get(id(self)) is control and control.registry is registry and
                    registry.get(control.key) is registered and registered[0] is self.transition and
                    registered[2] is self.originals and registered[3] is self.bindings,
                    "BOOTSTRAP_RECIPIENT_PARENT_CLAIM_CHANGED")
        transition, originals, bound = registered[0], registered[2], registered[3]
        require(not cleanup or bound is not None, "BOOTSTRAP_RECIPIENT_CLEANUP_NOT_BOUND")
        if type(self) is _InitializerParent:
            registered[4].checked(self, cleanup=cleanup)
        else:
            require(type(registered[4]) is bool, "BOOTSTRAP_RECIPIENT_INTENT_CHANGED")
        # Full parsing repeatedly recursed through the same closed records at
        # every nested clock/Owner check. Exact transitive typed pins preserve
        # immediate rejection, without repeatedly parsing unchanged originals.
        # Full validation still surrounds original reads and final return.
        originals[2].checked(transition)
        if full:
            check_new_entry_transition(transition)  # NEVER advances the closed clock.
            originals[2].checked(transition)
        values, references = _recipient_predecessor_pins(transition)
        require(values == originals[0] and all(a is b for a, b in zip(references, originals[1])),
                "BOOTSTRAP_RECIPIENT_PARENT_PREDECESSOR_CHANGED")
        if bound is not None:
            owner = bound.owner
            # Cleanup uses only independently registered originals. Rejected
            # call aliases stay rejected; they are NEVER restored or admitted
            # for live/deadline/read/record work. Actual owner/frame changes,
            # roster uncertainty and global quarantine still fail closed.
            require(owner.fence is bound.window and owner.first is bound.first and
                    owner.cancelled is bound.callback and owner.local_end == bound.local_end and
                    owner.work_limit is None and owner.final_limit is None and owner.early_last == bound.first.nanoseconds and
                    owner.admissions is bound.admissions and owner.errors is bound.errors,
                    "BOOTSTRAP_RECIPIENT_PARENT_OWNER_CHANGED")
            if not cleanup:
                require(self.owner is owner and self.window is bound.window and self.first is bound.first and
                        self.callback is bound.callback and self.errors is bound.errors and
                        type(self.local_start) is type(bound.local_start) and self.local_start == bound.local_start,
                        "BOOTSTRAP_RECIPIENT_PARENT_OWNER_CHANGED")
                require(tuple(self.handlers.items()) == tuple(bound.handler_rows) == _parent_control(self).handlers,
                        "BOOTSTRAP_PARENT_HANDLER_ROSTER_CHANGED")
        return self

    def freeze_roster(self):
        self.roster()
        bound = _recipient_parent_registration(self)[3]
        require(bound is not None and not bound.owner.closed and not bound.close_roster,
                "BOOTSTRAP_RECIPIENT_PARENT_CLOSE_REENTRY")
        bound.close_roster.append(tuple((pin.row, pin.label, pin.resource) for pin in bound.seen))

    def closed_roster(self):
        # Always inspect even if an earlier exception already exists. A late
        # removed/unfinished row is UNKNOWN, not a known failure with lost pins.
        owner = self.actual_owner()
        if owner is None:
            return
        try:
            self.roster()
            require(owner.closed is True and all(pin.attempted and pin.closed
                    for pin in _recipient_parent_registration(self)[3].seen), "BOOTSTRAP_RECIPIENT_PARENT_NOT_CLOSED")
        except BaseException as error:
            self.error("recipient-closed-roster", error, unknown=True)

    def cancel(self):
        self.check()
        cancellation(self.cancelled)
        for callback in self.transition._attempt.transition._callbacks:
            callback()
            self.check()

    def error(self, stage, error, *, unknown=False):
        owner = self.actual_owner()
        if self.original is None:
            self.original = error if owner is None or owner.original is None else owner.original
        unknown |= (isinstance(error, diagnostics.WindowsEvidenceError) and error.retirement_unknown is not False)
        unknown |= bool(query.QUARANTINE or diagnostics._QUARANTINE)
        if owner is not None:
            owner.error(stage, error, unknown=unknown)
            self.unknown |= owner.unknown
        else:
            self.unknown |= unknown or diagnostics._exception_detail(error)["retirementUnknown"]
            if len(self.errors) < 64:
                self.errors.append({"stage": stage, "detail": diagnostics._exception_detail(error)})
            else:
                self.unknown = True

    def live(self):
        self.check()
        owner = self.actual_owner()
        require(self.state == "RUNNING" and owner is not None and not owner.closed and
                self.original is None and owner.original is None and not self.unknown and not owner.unknown and
                not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                "BOOTSTRAP_RECIPIENT_PARENT_NOT_LIVE")
        return owner

    def paths(self):
        old = self.transition._attempt.transition._entry
        original = Path(origin.parse(old.context_original)["session"])
        return original, *(original.with_name(original.name + suffix) for suffix in ("-adoption", "-entry", "-productive"))

    def host(self):
        owner = self.live()
        owner.end()
        entry = self.transition._attempt.transition._entry
        context = origin.parse(entry.context_original)
        require(origin.wire.TOKEN_ENV not in os.environ and os.environ.get(PREPARE_OUTCOME_ENV) == "success" and
                os.environ.get(PREPARE_HASH_ENV) == origin.digest(entry.handoff_original),
                "BOOTSTRAP_RECIPIENT_PREPARE_OUTCOME_OR_TOKEN")
        selection, path, event = host_inputs(self.first.clock.role)
        recipient_environment(self.paths()[3])
        require(path == self.paths()[0] and selection == context["selection"] and event == entry.admitted.original_event and
                context["runnerName"] == os.environ.get("RUNNER_NAME") and
                context["inheritedContext"] == query._inherited_context() and
                os.getpid() != origin.parse(entry.preparation_original)["processIdentity"]["pid"],
                "BOOTSTRAP_RECIPIENT_PARENT_HOST_CHANGED")
        owner.end()

    def read_originals(self):
        self.check(full=True)
        owner = self.live()
        self.host()
        previous, old = self.transition._attempt, self.transition._attempt.transition
        entry, paths = old._entry, self.paths()
        value = origin.parse(entry.raw)
        for name, path, identity in (("original", paths[0], value["preparation"]["sessionIdentity"]),
                ("adoption", paths[1], value["sessionIdentity"]), ("entry", paths[2], previous.target_identity)):
            _new_entry_owned(owner, self.handles[name], path, identity)
        adoption, current = self.handles["adoption"], self.handles["entry"]
        require(owner.read(adoption, "entry-context.json") == entry.raw and
                owner.read(adoption, "entry-close-pending.json") == old.pending_raw and
                owner.read(current, "new-entry-pending.json") == previous.pending_raw,
                "BOOTSTRAP_RECIPIENT_ENTRY_ORIGINAL_CHANGED")
        for target, admitted, session, returned in ((adoption, entry.admitted, entry.session_original, entry.return_original),
                (current, previous.admitted, previous.admission_originals[1], previous.admission_originals[2])):
            directory = owner.child(target, "admission")
            require(load_admission(owner, directory) == admitted and owner.read(directory, "session-result.json") == session and
                    owner.read(target, "admission-return.json") == returned, "BOOTSTRAP_RECIPIENT_ENTRY_ADMISSION_CHANGED")
        _admission_history_content(entry.admitted, entry.session_original, entry.return_original, history.snapshot(old._fence))
        _new_entry_return_content(previous)  # Original closed new-entry registry, not fresh admission.
        admitted, _, prepared = _read_prepared(_RecipientParentReader(self), self.handles["original"],
                                              entry.handoff_original, entry.context_original)
        require(admitted == entry.admitted and same_preparation(prepared, origin.parse(entry.preparation_original)) and
                same_preparation(prepared, origin.parse(previous.preparation)), "BOOTSTRAP_RECIPIENT_PREPARATION_CHANGED")
        service = owner.child(self.handles["original"], "service")
        responses = tuple((name, owner.read(service, name + ".json")) for name in ("attempt", "jobs"))
        require(responses == old.responses and origin.encoded(_entry_close_proposal(entry, responses)) == old.proposal_raw,
                "BOOTSTRAP_RECIPIENT_SERVICE_ORIGINALS_CHANGED")
        self.host()
        self.check(full=True)
        return prepared

    def private_inputs(self):
        owner = self.live()
        for name in ("original", "session", *RECIPIENT_DIRECTORIES):
            directory = self.handles[name]
            _new_entry_owned(owner, directory, self.paths()[0] if name == "original" else self.paths()[3] if name == "session"
                             else self.paths()[3] / name, self.identities[name])
        for directory, name, key in ((self.handles["session"], "recipient-context.json", "context"),
                (self.handles["session"], "allocation.json", "proposal"),
                (self.handles["recipient-validation"], "start.json", "start.json")):
            require(owner.read(directory, name) == self.records[key], "BOOTSTRAP_RECIPIENT_PARENT_INPUT_CHANGED")
        self.host()

    def resource(self, label):
        bound = _recipient_parent_registration(self)[3]
        rows = [] if bound is None else [pin for pin in bound.seen if pin.label == label]
        require(len(rows) <= 1, "BOOTSTRAP_RECIPIENT_DUPLICATE_PHASE_RESOURCE")
        return rows[0].resource if rows else None

    def close_phase_resource(self, label):
        """Existing Owner close, with original pins retained on every failure."""
        bound = _recipient_parent_registration(self)[3]
        try:
            resource = self.resource(label)
            if resource is not None:
                bound.owner.close_one(resource)
            self.roster()
        except BaseException as error:
            self.error("recipient-" + label + "-close-return", error, unknown=True)
        pins = [pin for pin in bound.seen if pin.label == label]
        return (len(pins) == 1 and pins[0].attempted, len(pins) == 1 and pins[0].closed)

    def phase_writers_closed(self):
        self.roster()
        pins = _recipient_parent_registration(self)[3].seen
        for name in ("native-scope", "stdout", "stderr"):
            selected = [pin for pin in pins if pin.label == name]
            require(len(selected) == 1 and selected[0].attempted and selected[0].closed,
                    "BOOTSTRAP_RECIPIENT_READ_BEFORE_RETIREMENT")

    def remember_file(self, key, directory, name, raw, maximum=LIMIT):
        owner = self.live()
        bound = _recipient_parent_registration(self)[3]
        require(type(raw) is bytes and len(raw) <= maximum and not any(row[0] == key for row in bound.files),
                "BOOTSTRAP_RECIPIENT_DUPLICATE_ORIGINAL")
        identity = tuple(directory_identity(list(directory.identity), self.window.clock.role))
        _new_entry_owned(owner, directory, directory.path, identity)
        bound.files.append((key, directory, directory.path, identity, name, maximum, raw))
        self.records[key] = raw
        return raw

    def reread_files(self):
        owner = self.live()
        self.phase_writers_closed()
        for key, directory, path, identity, name, maximum, raw in _recipient_parent_registration(self)[3].files:
            _new_entry_owned(owner, directory, path, identity)
            require(self.records.get(key) == raw and owner.read(directory, name, maximum) == raw,
                    "BOOTSTRAP_RECIPIENT_RETAINED_ORIGINAL_CHANGED")
        self.private_inputs()

    def launch(self):
        owner, window = self.live(), self.window
        phase, path = _parent_location(self)
        directory = self.handles[phase]
        context = origin.parse(self.records["context"])
        start = origin.parse(self.records["start.json"])
        self.row = {**start, "captureOutcomes": {name: {"synced": False, "verified": False,
            "closeAttempted": False, "closed": False, "readback": False} for name in ("stdout", "stderr")}}
        env = processes.ownership_environment(_parent_environment(self), context["job"], start["invocation"],
                                               str(path), str(path / "control-home"), allow_new_context=True)
        require({name: env[name] for name in query._CONTEXT} == start["inheritedContext"],
                "BOOTSTRAP_RECIPIENT_PARENT_DOMAIN_CHANGED")
        try:
            end = window.deadline(_parent_parameters(self)[2], final=True)
            for name, maximum in (("stdout", ACK_LIMIT), ("stderr", STDERR_LIMIT)):
                owner.acquire(name, lambda name=name, maximum=maximum: directory.create_file(name + ".log",
                                                                                             max_bytes=maximum, deadline=end))
            def make_scope():
                self.row["scopeAttempted"] = True  # Actual factory attempt, not acquire's earlier precheck.
                return processes.make_scope(start["job"], start["invocation"], str(path), str(path / "control-home"))
            scope = owner.acquire("native-scope", make_scope)
            self.row["preparerIdentity"] = preparer_identity(scope, window.clock.role)
            raw = owner.write(directory, "baseline.json", {"role": window.clock.role,
                "baseline": sorted(scope.baseline) if hasattr(scope, "baseline") else None,
                "kernelJob": window.clock.role == "windows-x64"})
            self.remember_file("baseline.json", directory, "baseline.json", raw)
            baseline_record(self.records["baseline.json"], window.clock.role)
            self.row["baselineSha256"] = origin.digest(self.records["baseline.json"])
            self.read_originals()
            self.private_inputs()
            self.row["launchMinimumNs"] = window.now()
            argv = _parent_argv(self, self.row["launchMinimumNs"])
            self.private_inputs()
            require(processes.ownership_environment(_parent_environment(self), context["job"], start["invocation"],
                    str(path), str(path / "control-home"), allow_new_context=True) == env,
                    "BOOTSTRAP_PARENT_LAUNCH_ENVIRONMENT_CHANGED")
            window.now(minimum=self.row["launchMinimumNs"])
            self.row["launchArgv"] = argv
            self.row["launchAttempted"] = True
            child = scope.spawn(argv, str(ROOT), env, stdout=self.resource("stdout"), stderr=self.resource("stderr"))
            require(child.stdout is None and child.stderr is None, "BOOTSTRAP_RECIPIENT_PRIVATE_SINKS_REQUIRED")
            birth = origin.parse(origin.encoded(scope.description()))
            leaders = [item for item in birth.get("startedIdentities", []) if item.get("pid") == child.pid]
            require(len(leaders) == 1, "BOOTSTRAP_RECIPIENT_NATIVE_BIRTH")
            self.row["leader"] = leaders[0]
            native_record(birth, start, leaders[0], argv, terminal=False)
            raw = owner.write(directory, "native-start.json", {"ownership": birth,
                "leader": leaders[0], "preparerIdentity": self.row["preparerIdentity"], "observedNs": window.now()})
            self.remember_file("native-start.json", directory, "native-start.json", raw)
            self.row["nativeStartSha256"] = origin.digest(self.records["native-start.json"])
            while True:
                window.now()
                for name in ("stdout", "stderr"):
                    stream = self.resource(name)
                    stream.observe_live_output() if window.clock.role == "windows-x64" else stream.verify()
                code = child.poll()
                if code is not None:
                    self.row["exitCode"] = code  # Preserve actual return before any fallible observation.
                observed = window.now()
                if code is not None:
                    self.row["completedNs"] = observed
                    require(type(code) is int and code == 0, "BOOTSTRAP_RECIPIENT_CHILD_FAILED")
                    require(scope.discover() == [], "BOOTSTRAP_RECIPIENT_LEFT_DESCENDANTS")
                    break
                scope.discover()
                time.sleep(.025)
        except BaseException as error:
            self.error("recipient-native", error)
        finally:
            try:
                self.finish_native()
            except BaseException as error:
                # A cleanup callback must not erase the original failure or
                # drop the independently retained scope/capture references.
                self.error("recipient-native-final-return", error, unknown=True)
        if self.original is not None:
            raise self.original

    def finish_native(self):
        # Independently retained actual bindings survive callback rebinding.
        bound = _recipient_parent_registration(self)[3]
        owner, window = bound.owner, bound.window
        final_ready = False
        try:
            window.begin_final()
            final_ready = True
        except BaseException as error:
            self.error("recipient-final-fence", error)
        try:
            scope = self.resource("native-scope")
        except BaseException as error:
            self.error("recipient-scope-reference", error, unknown=True)
            return
        if scope is not None:
            try:
                try:
                    require(final_ready, "BOOTSTRAP_RECIPIENT_FINAL_START_FAILED")
                    end = window.cleanup_deadline(45)
                    remaining = max(0, end - window.local_now(cleanup=True))
                except BaseException as error:
                    self.error("recipient-drain-fence", error)
                    remaining = 0
                grace = min(5, remaining)
                self.row["survivors"] = scope.drain(grace=grace, kill_wait=min(5, max(0, remaining - grace)))
                self.row["ownership"] = origin.parse(origin.encoded(scope.description()))
                require(self.row["survivors"] == [] and self.row["ownership"].get("discoveryErrors") == [],
                        "BOOTSTRAP_RECIPIENT_NATIVE_DRAIN_UNKNOWN")
                # A returned scope is registered before acquire's post-return
                # clock. If that clock failed, these observations may never
                # have happened. Do not invent them or turn known drain into
                # UNKNOWN merely because a later assignment was not reached.
                if "preparerIdentity" in self.row:
                    require(preparer_identity(scope, window.clock.role) == self.row["preparerIdentity"],
                            "BOOTSTRAP_RECIPIENT_PARENT_LIFETIME_CHANGED")
                if "leader" in self.row:
                    native_record(self.row["ownership"], self.row, self.row["leader"], self.row["launchArgv"])
                self.native_retired = True
            except BaseException as error:
                self.error("recipient-drain", error, unknown=True)
            attempted, closed = self.close_phase_resource("native-scope")
            self.row.update(scopeCloseAttempted=attempted, scopeClosed=closed)
            self.native_retired &= closed
        elif self.row.get("scopeAttempted"):
            self.error("recipient-construction", origin.OriginError("BOOTSTRAP_RECIPIENT_SCOPE_UNKNOWN"), unknown=True)
        else:
            self.native_retired = True
        if self.native_retired and not owner.unknown:
            for name in ("stdout", "stderr"):
                try:
                    stream = self.resource(name)
                    if stream is None:
                        continue
                    outcome = self.row["captureOutcomes"][name]
                    window.now(final=True)
                    stream.sync()
                    outcome["synced"] = True
                    stream.verify()
                    outcome["verified"] = True
                    window.now(final=True)
                except BaseException as error:
                    self.error("recipient-capture", error)
                attempted, closed = self.close_phase_resource(name)
                self.row["captureOutcomes"][name].update(closeAttempted=attempted, closed=closed)
                if owner.unknown:
                    break
            self.captures_retired = all(outcome["closed"] for outcome in self.row["captureOutcomes"].values())
        try:
            self.row["finalizedNs"] = window.now(final=True)
        except BaseException as error:
            self.error("recipient-final-return", error)
        if self.original is None and owner.original is not None:
            self.error("recipient-native-close", owner.original)
        # An outer drain does not prove a failed/late child's supplier returned
        # KNOWN. Preserve it conservatively, with no further file acquisitions.
        if self.row.get("launchAttempted") and self.original is not None:
            self.error("recipient-child-return", self.original, unknown=True)

    def native_content(self):
        """Bind original baseline/birth/terminal/captures after actual close."""
        self.phase_writers_closed()
        row, window = self.row, self.window
        start = origin.parse(self.records["start.json"])
        birth = origin.parse(self.records["native-start.json"])
        baseline = baseline_record(self.records["baseline.json"], window.clock.role)
        require(set(row) == TERMINAL_FIELDS and set(birth) == {"ownership", "leader", "preparerIdentity", "observedNs"},
                "BOOTSTRAP_RECIPIENT_NATIVE_TERMINAL_FIELDS")
        preparer = closed_lifetime(row["preparerIdentity"], window.clock.role)
        require(preparer == closed_lifetime(birth["preparerIdentity"], window.clock.role) and
                preparer["pid"] != row["leader"]["pid"], "BOOTSTRAP_RECIPIENT_NATIVE_PREPARER_CHANGED")
        for name in set(start) - {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}:
            require(row[name] == start[name], "BOOTSTRAP_RECIPIENT_NATIVE_START_CHANGED")
        require(type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is True and
                row["scopeAttempted"] is True and row["scopeCloseAttempted"] is True and row["scopeClosed"] is True and
                row["retirement"] == "KNOWN" and row["survivors"] == [] and row["errors"] == [] and
                row["nativeStartSha256"] == origin.digest(self.records["native-start.json"]) and
                row["baselineSha256"] == origin.digest(self.records["baseline.json"]) and row["leader"] == birth["leader"],
                "BOOTSTRAP_RECIPIENT_NATIVE_RETURN")
        argv = _parent_argv(self, origin.integer(row["launchMinimumNs"], window.first))
        require(row["launchArgv"] == argv, "BOOTSTRAP_RECIPIENT_NATIVE_ARGV")
        native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
        native_record(row["ownership"], start, row["leader"], argv)
        require(birth["ownership"]["launches"] == row["ownership"]["launches"], "BOOTSTRAP_RECIPIENT_NATIVE_BIRTH_CHANGED")
        if baseline["baseline"] is not None:
            identity = lifetime(row["leader"], window.clock.role)
            require(list(identity[:4] if window.clock.role.startswith("macos-") else identity) not in baseline["baseline"],
                    "BOOTSTRAP_RECIPIENT_NATIVE_PREEXISTING_LEADER")
        times = (window.first, row["launchMinimumNs"], birth["observedNs"], row["completedNs"],
                 window.final_started, row["finalizedNs"], window.read_started)
        require(all(type(value) is int and 0 <= value <= origin.clocks.UINT64 for value in times) and
                list(times) == sorted(times) and row["completedNs"] < window.work and
                row["finalizedNs"] < window.final, "BOOTSTRAP_RECIPIENT_NATIVE_CHRONOLOGY")
        require(row["captureOutcomes"] == {name: {"synced": True, "verified": True, "closeAttempted": True,
                    "closed": True, "readback": True} for name in ("stdout", "stderr")} and
                all(type(flag) is bool for value in row["captureOutcomes"].values() for flag in value.values()) and
                row["captures"] == {name: {"sha256": origin.digest(self.records[name + ".log"]),
                    "bytes": len(self.records[name + ".log"])} for name in ("stdout", "stderr")},
                "BOOTSTRAP_RECIPIENT_NATIVE_CAPTURES")

    def read_child(self):
        owner, window = self.live(), self.window
        window.begin_read()
        directory = self.handles["recipient-validation"]
        try:
            for name, maximum in (("stdout", ACK_LIMIT), ("stderr", STDERR_LIMIT)):
                self.remember_file(name + ".log", directory, name + ".log", owner.read(directory, name + ".log", maximum), maximum)
                self.row["captureOutcomes"][name]["readback"] = True
            self.remember_file("child-result.json", directory, "child-result.json", owner.read(directory, "child-result.json"))
            child, ack = (origin.parse(self.records[name]) for name in ("child-result.json", "stdout.log"))
            start, context = origin.parse(self.records["start.json"]), origin.parse(self.records["context"])
            require(self.records["stderr.log"] == b"" and self.records["child-result.json"] == origin.encoded(child) and
                    self.records["stdout.log"] == origin.encoded(ack), "BOOTSTRAP_RECIPIENT_CHILD_ORIGINALS")
            require(set(child) == {"schema", "scope", "contextSha256", "startSha256", "proposalSha256",
                    "admissionReturnSha256", "recipient", "clock", "invocation", "launchMinimumNs", "beganNs",
                    "metadataLastNs", "supplierReturnedNs", "completedNs", "supplierReturned", "childResourceClose",
                    "parentRetirement", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"} and
                    type(child["schema"]) is int and child["schema"] == 1 and child["scope"] == RECIPIENT_SCOPE and
                    child["contextSha256"] == origin.digest(self.records["context"]) and
                    child["startSha256"] == origin.digest(self.records["start.json"]) and
                    child["proposalSha256"] == origin.digest(self.records["proposal"]) and child["supplierReturned"] is True and
                    child["childResourceClose"] == "PENDING_CLOSE" and
                    child["launchMinimumNs"] == self.row["launchMinimumNs"], "BOOTSTRAP_RECIPIENT_CHILD_TERMINAL")
            require(set(ack) == {"schema", "scope", "invocation", "terminalSha256", "clock", "closedNs",
                    "childResourceClose", "parentRetirement", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"} and
                    type(ack["schema"]) is int and ack["schema"] == 1 and ack["scope"] == RECIPIENT_ACK_SCOPE and
                    ack["terminalSha256"] == origin.digest(self.records["child-result.json"]) and
                    ack["childResourceClose"] == "KNOWN_RESOURCE_CLOSE_ONLY", "BOOTSTRAP_RECIPIENT_CHILD_ACK")
            for value in (child, ack):
                require(value["invocation"] == start["invocation"] and value["clock"] == origin.clock_value(window.clock) and
                        value["parentRetirement"] == "NOT_OBSERVED_HERE" and value["budgetAcceptance"] == "NOT_ADMITTED" and
                        value["testAcceptance"] == "NOT_PERFORMED" and value["exportSaveAuthority"] is False,
                        "BOOTSTRAP_RECIPIENT_CHILD_AUTHORITY")
            admission = owner.child(self.handles["session"], "recipient-admission")
            admitted = load_admission(owner, admission)
            require(admitted == self.transition._attempt.admitted, "BOOTSTRAP_RECIPIENT_CHILD_ADMISSION_CHANGED")
            for name, raw in (("admission.json", admitted.record), ("original-event.json", admitted.original_event),
                    ("original-policy.json", admitted.original_policy), ("recipient-public.asc", admitted.public_key)):
                self.remember_file("recipient-admission/" + name, admission, name, raw)
            session_raw = owner.read(admission, "session-result.json")
            returned_raw = owner.read(directory, "admission-return.json")
            self.remember_file("recipient-admission/session-result.json", admission, "session-result.json", session_raw)
            self.remember_file("admission-return.json", directory, "admission-return.json", returned_raw)
            session, returned = origin.parse(session_raw), origin.parse(returned_raw)
            require(set(session) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"} and
                    type(session["schema"]) is int and session["schema"] == 1 and session["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
                    session["result"] == "READY_FOR_CALLER_SEAL" and session["retirement"] == "KNOWN" and
                    session["firstError"] is None and session["errors"] == [] and type(session["queries"]) is list and
                    type(session["readbacks"]) is list and type(session["job"]) is str and
                    re.fullmatch(r"[0-9a-f]{32}", session["job"]), "BOOTSTRAP_RECIPIENT_CHILD_QUERY_SESSION")
            require(set(returned) == {"admissionSha256", "sessionSha256", "clock", "returnedNs"} and
                    returned_raw == origin.encoded(returned) and returned["admissionSha256"] == origin.digest(admitted.record) and
                    returned["sessionSha256"] == origin.digest(session_raw) and returned["clock"] == origin.clock_value(window.clock) and
                    child["admissionReturnSha256"] == origin.digest(returned_raw), "BOOTSTRAP_RECIPIENT_CHILD_QUERY_RETURN")
            times = (start["startedNs"], self.row["launchMinimumNs"], child["beganNs"], child["metadataLastNs"],
                     returned["returnedNs"], child["supplierReturnedNs"], child["completedNs"], ack["closedNs"], self.row["completedNs"])
            require(all(type(value) is int and 0 <= value <= origin.clocks.UINT64 for value in times) and
                    list(times) == sorted(times) and child["metadataLastNs"] < child["beganNs"] + 45 * origin.NS and
                    ack["closedNs"] < min(child["beganNs"] + 210 * origin.NS, window.work) and
                    self.row["completedNs"] < window.work, "BOOTSTRAP_RECIPIENT_CHILD_CHRONOLOGY")
            recipient = child["recipient"]
            fields = {"fingerprint", "encryption_fingerprint", "expires_at", "key_sha256", "work_identity", "executable"}
            if window.clock.role == "windows-x64":
                fields |= {"executable_sha256", "job_id"}
            require(type(recipient) is dict and set(recipient) == fields and
                    recipient["fingerprint"] == admitted.fingerprint.upper() and recipient["key_sha256"] == admitted.key_sha256 and
                    recipient["work_identity"] == self.identities["crypto"] and
                    type(recipient["encryption_fingerprint"]) is str and re.fullmatch(r"[0-9A-F]{40}", recipient["encryption_fingerprint"]) and
                    type(recipient["expires_at"]) is int and (recipient["expires_at"] == 0 or recipient["expires_at"] >= admitted.expires_at) and
                    type(recipient["executable"]) is str and 0 < len(recipient["executable"]) <= 32768 and
                    Path(recipient["executable"]).is_absolute(), "BOOTSTRAP_RECIPIENT_CHILD_KEY_RETURN")
            if window.clock.role == "windows-x64":
                require(recipient["job_id"] == context["job"] and type(recipient["executable_sha256"]) is str and
                        re.fullmatch(r"[0-9a-f]{64}", recipient["executable_sha256"]), "BOOTSTRAP_RECIPIENT_CHILD_WINDOWS_RETURN")
            for name, expected in (("recipient.asc", admitted.public_key), ("recipient.gpg", posix._public_armor(admitted.public_key))):
                raw = owner.read(self.handles["crypto"], name, posix.MAX_KEY_BYTES)
                require(raw == expected, "BOOTSTRAP_RECIPIENT_CHILD_KEY_ORIGINAL_CHANGED")
                self.remember_file("crypto/" + name, self.handles["crypto"], name, raw, posix.MAX_KEY_BYTES)
            self.row.update(retirement="KNOWN", captures={name: {"sha256": origin.digest(self.records[name + ".log"]),
                "bytes": len(self.records[name + ".log"])} for name in ("stdout", "stderr")}, errors=[])
            self.native_content()
            self.reread_files()
            self.read_originals()
            self.reread_files()
            window.now()
            self.child_accepted = True
        except BaseException as error:
            self.error("recipient-readback", error, unknown=True)
            raise self.original


def run_recipient_after_entry(transition):
    """Once-claimed INTERNAL recipient prefix; no public/workflow caller.

    All resources and handlers close in this one call under the ORIGINAL prefix
    caps. No live Recipient is reconstructed from child JSON; this wrapper never
    selects initialization. Producer/cache/custody remains separate unfinished work.
    """
    return _recipient_after_entry(transition, initialize=False)


def initialize_after_entry(transition):
    """INTERNAL same-call recipient + initialization, never Prefix authority.

    No public CLI or workflow calls this operation. The original shared claim
    fixes its intent before any clock/native/file supplier and consumes failure.
    Initialization yields evidence only, not producer/cache permission.
    """
    return _recipient_after_entry(transition, initialize=True)


def _install_parent_handlers(call, control):
    owner = call.live()
    require(_parent_control(call) is control, "BOOTSTRAP_PARENT_CONTROL_CHANGED")
    bound = control.record[3]
    for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
        handler = signal.getsignal(number)
        call.handlers[number] = handler
        bound.handler_rows.append((number, handler))
        # Retain the original pair in the actual locally held control BEFORE
        # installation: even a failed/partially effective signal() owes restore.
        _retain_parent_handler(call, control, number, handler)
        signal.signal(number, lambda signum, _frame: call.cancelled.append(signum))
        owner.end()


def _close_parent(call, owner, window, control):
    """Known close with the actual local holder, never its registry alias."""
    saved = _parent_originals(call)
    require(saved[0] is control, "BOOTSTRAP_PARENT_CONTROL_CHANGED")
    bound = saved[4][3]
    if owner is not None:
        call.state = "CLOSING"
        try:
            call.freeze_roster()
        except BaseException as error:
            call.error("recipient-prefix-close-roster", error, unknown=True)
        if window.phase == "WORK":
            try:
                window.begin_final()
            except BaseException as error:
                call.error("recipient-prefix-final-start", error)
        try:
            call.roster()
        except BaseException as error:
            call.error("recipient-prefix-roster", error, unknown=True)
        try:
            owner.close()  # Actual strong local reference, not an execution alias.
        except BaseException as error:
            call.error("recipient-prefix-close", error)
        if owner.original is not None:
            call.error("recipient-prefix-owner-return", owner.original)
    for number, handler in saved[6]:
        try:
            signal.signal(number, handler)
            require(signal.getsignal(number) == handler, "BOOTSTRAP_PARENT_HANDLER_NOT_RESTORED")
            bound.handler_restored.append((number, handler))
        except BaseException as error:
            call.error("recipient-prefix-handler-restore", error)
    call.closed_roster()


def _recipient_after_entry(transition, *, initialize):
    require(type(initialize) is bool, "BOOTSTRAP_RECIPIENT_INTENT")
    check_new_entry_transition(transition)
    pins = (*_recipient_predecessor_pins(transition), _RecipientPredecessorGraph.capture(transition))
    call = _RecipientParent(transition, pins)
    with _RECIPIENT_CLAIM_LOCK:
        require(id(transition) not in _RECIPIENT_ATTEMPTS, "BOOTSTRAP_RECIPIENT_ALREADY_CLAIMED")
        _RECIPIENT_ATTEMPTS[id(transition)] = (transition, call, pins, None, initialize)
        control = _ParentControl(call, _RECIPIENT_ATTEMPTS, id(transition), _RECIPIENT_ATTEMPTS[id(transition)])
        _register_parent_control(control)
        _PARENT_CONTROLS[id(call)] = control
    owner = window = None
    try:
        call.local_start = time.monotonic()
        require(type(call.local_start) in (int, float) and math.isfinite(call.local_start) and call.local_start >= 0,
                "BOOTSTRAP_RECIPIENT_PARENT_LOCAL_CLOCK")
        call.first = origin.clocks.observe()
        call.callback = call.cancel
        call.window = window = _RecipientParentWindow(call)
        call.owner = owner = Owner(window.local_end, window, first=call.first, cancelled=call.callback)
        # Retain the actual return BEFORE another supplier/clock/callback.
        call.bindings = _RecipientParentBindings(owner, window, call.first, call.callback, call.local_start, owner.local_end,
            owner.admissions, owner.resources, owner.errors, window_state=[window.phase_state()],
            observations=[window.last, window.local_last])
        with _RECIPIENT_CLAIM_LOCK:
            _bind_parent_control(call, control, (transition, call, pins, call.bindings, initialize))
        call.errors, call.state = owner.errors, "RUNNING"
        owner.end()
        _install_parent_handlers(call, control)
        call.host()
        for name, path in zip(("original", "adoption", "entry"), call.paths()[:3]):
            call.handles[name] = owner.open(path)
        call.read_originals()
        path = call.paths()[3]
        call.handles["session"] = owner.new(path)
        for name in RECIPIENT_DIRECTORIES:
            call.handles[name] = owner.child(call.handles["session"], name, create=True)
        for name in ("original", "session", *RECIPIENT_DIRECTORIES):
            call.handles[name].verify()
            call.identities[name] = directory_identity(list(call.handles[name].identity), window.clock.role)
            owner.end()
        old = transition._attempt.transition
        original, admitted = origin.parse(old._entry.context_original), origin.admitted_value(old._entry.admitted)
        context = {"schema": 1, "scope": RECIPIENT_CONTEXT_SCOPE, "profile": bootstrap.PROFILE,
            **{name: admitted[name] for name in ("selection", "cacheCohort", "source", "github")},
            "root": str(ROOT), "session": str(path), "originalSession": str(call.paths()[0]),
            "originalContextSha256": origin.digest(old._entry.context_original),
            "admissionSha256": origin.digest(old._entry.admitted.record), "proposalSha256": origin.digest(old.proposal_raw),
            "clock": origin.clock_value(window.clock), "job": uuid.uuid4().hex,
            "inheritedContext": original["inheritedContext"], "runnerName": original["runnerName"],
            "previousTransitionSha256": origin.digest(transition.raw), "previousCheckedNs": transition._checked_ns,
            "directories": call.identities, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False}
        call.remember_file("proposal", call.handles["session"], "allocation.json",
                           owner.write(call.handles["session"], "allocation.json", old.proposal_raw))
        call.remember_file("context", call.handles["session"], "recipient-context.json",
                           owner.write(call.handles["session"], "recipient-context.json", context))
        invocation = uuid.uuid4().hex
        env = processes.ownership_environment(recipient_environment(path), context["job"], invocation,
                                               str(path), str(path / "control-home"), allow_new_context=True)
        start_raw = owner.write(call.handles["recipient-validation"], "start.json", {
            "schema": 1, "scope": RECIPIENT_START_SCOPE, "contextSha256": origin.digest(call.records["context"]),
            "argv": recipient_command(origin.digest(call.records["context"])), "cwd": str(ROOT), "role": window.clock.role,
            "job": context["job"], "invocation": invocation, "state": str(path), "home": str(path / "control-home"),
            "inheritedContext": {name: env[name] for name in query._CONTEXT}, "startedNs": window.first,
            "workEndNs": window.work, "finalEndNs": window.native_end, "exitCode": None,
            "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"})
        call.remember_file("start.json", call.handles["recipient-validation"], "start.json", start_raw)
        call.launch()
        call.read_child()
        call.remember_file("result.json", call.handles["recipient-validation"], "result.json",
                           owner.write(call.handles["recipient-validation"], "result.json", call.row))
        call.reread_files()
        call.pending_raw = owner.write(call.handles["session"], "recipient-prefix-pending.json", {
            "schema": 1, "scope": "BOOTSTRAP_RECIPIENT_PREFIX_PENDING_RESOURCE_CLOSE_V1",
            "previousTransitionSha256": origin.digest(transition.raw), "window": window.record(),
            "originalsSha256": {name: origin.digest(raw) for name, raw in call.records.items()},
            "childReturn": "VALIDATED_ORIGINALS_AFTER_NATIVE_RETIREMENT", "parentResourceClose": "PENDING_CLOSE",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        call.reread_files()
        call.read_originals()
        call.reread_files()
        call.native_content()
        require(owner.read(call.handles["session"], "recipient-prefix-pending.json") == call.pending_raw and
                owner.read(call.handles["recipient-validation"], "result.json") == call.records["result.json"],
                "BOOTSTRAP_RECIPIENT_PREFIX_PENDING_CHANGED")
        call.cancel()
        owner.end()
    except BaseException as error:
        call.error("recipient-prefix", error, unknown=call.row.get("launchAttempted", False) and not call.child_accepted)
        # Retain only through the existing live, known owner and original cap.
        # No crypto, retry, postclose writer, or promise of encrypted delivery.
        if owner is not None and not owner.closed and not owner.unknown and "session" in call.handles:
            try:
                if window.phase == "WORK":
                    window.begin_final()
                call.check()
                call.failure_custody = "INCOMPLETE"
                owner.write(call.handles["session"], "recipient-prefix-failure.json", {"schema": 1, "result": "HOLD",
                    "errors": call.errors, "window": window.record(), "parentResourceClose": "PENDING_CLOSE",
                    "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}, final=True)
                call.failure_custody = "PRIVATE_PROVISIONAL_ONLY"
            except BaseException as secondary:
                call.error("recipient-prefix-failure-retention", secondary)
    finally:
        _close_parent(call, owner, window, control)
    try:
        if call.original is not None:
            raise call.original
        call.check(full=True)
        require(owner is not None and owner.closed and not owner.unknown and not call.unknown and call.child_accepted and
                all(row["attempted"] is True and row["closed"] is True for row in owner.resources),
                "BOOTSTRAP_RECIPIENT_PREFIX_NOT_CLOSED")
        call.cancel()
        closed_ns = window.now(minimum=call.row["finalizedNs"])
        raw = origin.encoded({"schema": 1, "scope": RECIPIENT_PREFIX_SCOPE,
            "previousTransitionSha256": origin.digest(transition.raw), "pendingSha256": origin.digest(call.pending_raw),
            "window": window.record(), "closedNs": closed_ns, "resourceCount": len(owner.resources),
            "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "childReturn": "VALIDATED_ORIGINALS_AFTER_NATIVE_RETIREMENT",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False})
        call.cancel()
        call.check(full=True)
        checked = window.now(minimum=closed_ns)
        call.check()
        call.closed_roster()
        require(window.last == checked and owner.original is None and not owner.unknown and
                all(row["attempted"] is True and row["closed"] is True for row in owner.resources),
                "BOOTSTRAP_RECIPIENT_PREFIX_FINAL_STATE_CHANGED")
        registered = _recipient_parent_registration(call)
        require(registered[4] is initialize and registered[3].handler_restored == registered[3].handler_rows,
                "BOOTSTRAP_RECIPIENT_INTENT_OR_HANDLERS_CHANGED")
        if not initialize:
            call.result = RecipientPrefix(raw, call.pending_raw, tuple(sorted(call.records.items())), checked)
            call.state = "COMPLETE"
            return call.result
        call.state = "HANDED_OFF"
        handoff = _InitializerPredecessor.capture(call, raw, checked)
        next_call = _InitializerParent(transition, pins)
        with _INITIALIZER_CLAIM_LOCK:
            require(id(call) not in _INITIALIZER_ATTEMPTS, "BOOTSTRAP_INIT_ALREADY_CLAIMED")
            _INITIALIZER_ATTEMPTS[id(call)] = (transition, next_call, pins, None, handoff, None)
            next_control = _ParentControl(next_call,
                _INITIALIZER_ATTEMPTS, id(call), _INITIALIZER_ATTEMPTS[id(call)], handoff_pin=handoff.pin())
            _register_parent_control(next_control)
            _PARENT_CONTROLS[id(next_call)] = next_control
    except BaseException as error:
        call.error("recipient-prefix-final-return", error)
        call.closed_roster()
        call.state = "FAILED"
        if owner is not None and (owner.unknown or call.unknown) and not any(actual is owner for actual in QUARANTINE):
            QUARANTINE.append(owner)
        raise call.original
    # Outside the recipient failure handler: neither initializer success nor
    # failure reopens/advances/errors its already-closed predecessor.
    return _initialize_claimed(next_call)


@dataclass(frozen=True)
class _InitializerPredecessor:
    """Original in-call intent and CLOSED recipient, never a returned Prefix.

    Checks inspect only retained graph/path values, not old resource methods,
    callbacks, clocks or files. All original bytes are separately reread using
    the initializer's new owner. No initializer can retrofit recipient intent.
    """
    recipient: object = field(repr=False)
    registry: object = field(repr=False)
    registered: object = field(repr=False)
    nodes: tuple = field(repr=False)
    paths: tuple = field(repr=False)
    files: tuple = field(repr=False)
    raw: bytes = field(repr=False)
    checked_ns: int
    local_last: float

    @staticmethod
    def path_values(call):
        return tuple((key, type(value), str(value.path), tuple(value.path.parts), value.path.drive, value.path.root,
                      tuple(value.identity)) for key, value in call.handles.items())

    def pin(self):
        return (self, self.recipient, self.registry, self.registered, self.nodes, self.paths, self.files,
                self.raw, self.checked_ns, self.local_last)

    @classmethod
    def capture(cls, call, raw, checked):
        registered = _recipient_parent_registration(call)
        bound = registered[3]
        require(type(call) is _RecipientParent and registered[4] is True and call.state == "HANDED_OFF" and
                call.result is None and call.original is None and not call.unknown and call.child_accepted and
                bound.owner.closed and not bound.owner.unknown and bound.owner.original is None and
                len(bound.close_roster) == 1 and all(pin.attempted and pin.closed for pin in bound.seen) and
                bound.handler_rows == bound.handler_restored and bound.window.last == checked and
                bound.window.phase == "READ", "BOOTSTRAP_INIT_NOT_ORIGINAL_HANDOFF")
        traversed = (_RecipientParent, _RecipientParentWindow, _RecipientParentBindings, _RecipientResource, _ParentControl,
                     Owner, origin.clocks.Reading, origin.clocks.ClockIdentity)
        scalars = (type(None), bool, int, float, str, bytes, signal.Signals)
        pending, seen, nodes = [call, registered, _parent_control(call)], set(), []
        while pending:
            value = pending.pop()
            kind = type(value)
            if kind in scalars or id(value) in seen:
                continue
            seen.add(id(value))
            require(len(seen) <= 10000, "BOOTSTRAP_INIT_PREDECESSOR_GRAPH_LIMIT")
            if kind is dict:
                saved, mode = tuple(value.items()), "mapping"
                require(all(type(key) in scalars for key, _ in saved), "BOOTSTRAP_INIT_PREDECESSOR_KEY")
                pending.extend(item for pair in saved for item in pair)
            elif kind in (list, tuple):
                saved, mode = tuple(value), "sequence"
                pending.extend(saved)
            elif kind in traversed:
                saved, mode = object.__getattribute__(value, "__dict__"), "record"
                pending.append(saved)
            else:
                saved, mode = None, "opaque"
            nodes.append((value, kind, mode, saved))
        files = tuple((key, str(path), identity, name, maximum, original)
            for key, _directory, path, identity, name, maximum, original in bound.files)
        files += (("pending", str(call.paths()[3]), tuple(call.identities["session"]),
                   "recipient-prefix-pending.json", LIMIT, call.pending_raw),)
        return cls(call, _RECIPIENT_ATTEMPTS, registered, tuple(nodes), cls.path_values(call),
                   files, raw, checked, bound.window.local_last)

    def checked(self, current, *, cleanup=False):
        registered = _recipient_parent_registration(current)
        original = _parent_originals(current)[5]
        actual = self.pin()
        require(len(original) == len(actual) and all(a is b for a, b in zip(actual[:7], original[:7])) and
                all(type(a) is type(b) and a == b for a, b in zip(actual[7:], original[7:])),
                "BOOTSTRAP_INIT_HANDOFF_CHANGED")
        require(type(self) is _InitializerPredecessor and type(current) is _InitializerParent and
                self.registry is _RECIPIENT_ATTEMPTS and
                self.registry.get(id(self.recipient.transition)) is self.registered and self.registered[4] is True and
                registered[0] is self.registered[0] and registered[2] is self.registered[2] and
                (cleanup or (current.transition is self.registered[0] and current.originals is self.registered[2])),
                "BOOTSTRAP_INIT_HANDOFF_REGISTRY_CHANGED")
        scalars = (type(None), bool, int, float, str, bytes, signal.Signals)
        def same(actual, original):
            return actual is original or (type(actual) is type(original) and type(original) in scalars and actual == original)
        for value, kind, mode, saved in self.nodes:
            require(type(value) is kind, "BOOTSTRAP_INIT_CLOSED_PREDECESSOR_CHANGED")
            if mode == "record":
                valid = object.__getattribute__(value, "__dict__") is saved
            elif mode == "mapping":
                valid = len(value) == len(saved) and all(same(key, old_key) and same(item, old_item)
                    for (key, item), (old_key, old_item) in zip(value.items(), saved))
            elif mode == "sequence":
                valid = len(value) == len(saved) and all(same(item, old) for item, old in zip(value, saved))
            else:
                valid = mode == "opaque"
            require(valid, "BOOTSTRAP_INIT_CLOSED_PREDECESSOR_CHANGED")
        require(self.path_values(self.recipient) == self.paths and
                self.registered[3].window.last == self.checked_ns and
                self.registered[3].window.local_last == self.local_last, "BOOTSTRAP_INIT_CLOSED_PREDECESSOR_CHANGED")


@dataclass(frozen=True)
class _InitializerWindow(_RecipientParentWindow):
    """Fixed work120/native165/prefix195 using the nonvirtual shared mechanics."""


@dataclass(frozen=True)
class _InitializationInputs:
    request_raw: bytes = field(repr=False)
    interpreter: tuple = field(repr=False)
    toolchains: object = field(repr=False)
    environment: tuple = field(repr=False)
    homes: tuple = field(repr=False)
    policy: bytes = field(repr=False)


def _initializer_names(owner, directory):
    """Bounded complete listing under the existing native/private owner."""
    end = owner.end()
    directory.verify()
    if owner.first.clock.role == "windows-x64":
        names = directory.names(max_names=32, deadline=end)
    else:
        names = []
        with os.scandir(directory.path) as entries:
            for entry in entries:
                require(len(names) < 32, "BOOTSTRAP_INIT_DIRECTORY_LIMIT")
                names.append(entry.name)
    require(len(names) == len(set(name.casefold() for name in names)), "BOOTSTRAP_INIT_DIRECTORY_ALIASES")
    directory.verify()
    owner.end()
    return tuple(sorted(names))


def _initializer_outputs_absent(owner):
    """Canonical output baseline, independently checked without executing Git."""
    owner.end()
    pinned = {}
    def stamp(info, contents):
        identity = (info.st_dev, info.st_ino, info.st_mode, getattr(info, "st_file_attributes", 0))
        return identity + ((info.st_mtime_ns, info.st_ctime_ns) if contents else ())
    def pin(path, info=None, *, contents=True):
        info = path.lstat() if info is None else info
        require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "BOOTSTRAP_INIT_SOURCE_DIRECTORY")
        pinned[path] = (contents, stamp(info, contents))
    # Shared ancestors (e.g. /tmp) are identity/type/mode pins, not source
    # content pins. Unrelated siblings may change their directory timestamps.
    # ROOT and every enumerated source directory retain the stronger check.
    for path in ROOT.parents:
        pin(path, contents=False)
    for path in (ROOT, ROOT / "buildSrc", ROOT / "library", ROOT / "samples", ROOT / "samples/iosApp"):
        pin(path)
    paths = [ROOT / "build", ROOT / "buildSrc/build", ROOT / "samples/iosApp/p2pkit-sample.xcodeproj"]
    for parent in (ROOT / "library", ROOT / "samples"):
        try:
            with os.scandir(parent) as entries:
                for count, entry in enumerate(entries, start=1):
                    owner.end()
                    require(count <= 20000, "BOOTSTRAP_INIT_SOURCE_DIRECTORY_LIMIT")
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400:
                        pin(Path(entry.path), info)
                        paths.append(Path(entry.path) / "build")
        except BaseException as error:
            owner.error("initializer-output-enumeration", error, unknown=True)
            raise
    for path in paths:
        owner.end()
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise origin.OriginError("BOOTSTRAP_INIT_PREEXISTING_OUTPUTS")
    for path, (contents, original) in pinned.items():
        owner.end()
        info = path.lstat()
        require(stamp(info, contents) == original and
                not getattr(info, "st_file_attributes", 0) & 0x400, "BOOTSTRAP_INIT_SOURCE_DIRECTORY_CHANGED")
    owner.end()


@dataclass(eq=False)
class _InitializerParent(_RecipientParent):
    """Second exact parent kind; no override of clocks/roster/close/native engine."""

    def init_inputs(self):
        self.check()
        registered = _recipient_parent_registration(self)
        bound, pin = registered[3], registered[5]
        require(bound is not None and len(bound.initialization) == 1 and
                type(pin) is tuple and len(pin) == 2 and bound.initialization[0] is pin[0] and
                type(pin[0]) is _InitializationInputs, "BOOTSTRAP_INIT_INPUTS_NOT_BOUND")
        inputs = pin[0]
        require((inputs.request_raw, inputs.interpreter, inputs.environment, inputs.homes, inputs.policy) == pin[1][:5] and
                inputs.toolchains is pin[1][5] and inputs.toolchains.originals == pin[1][6],
                "BOOTSTRAP_INIT_INPUTS_CHANGED")
        return bound.initialization[0]

    def request_unchanged(self):
        owner = self.live()
        owner.end()
        inputs = self.init_inputs()
        environment = recipient_environment(_parent_location(self)[1])
        environment.update(inputs.toolchains.environment())
        require(tuple(sorted(environment.items())) == inputs.environment and
                canonical._interpreter() == inputs.interpreter and inputs.homes == inputs.toolchains.homes() and
                inputs.policy == initialization.properties(inputs.homes), "BOOTSTRAP_INIT_INPUTS_CHANGED")
        require(canonical.init_request(state=str(_parent_location(self)[1] / "state"),
                expected_commit=origin.parse(self.transition._attempt.admitted.record)["source"]["commit"],
                role=self.first.clock.role) == inputs.request_raw, "BOOTSTRAP_INIT_REQUEST_CHANGED")
        owner.end()

    def host(self):
        _RecipientParent.host(self)
        bound = _recipient_parent_registration(self)[3]
        if bound is not None and bound.initialization:
            self.request_unchanged()

    def recipient_originals(self):
        owner = self.live()
        handoff = _recipient_parent_registration(self)[4]
        for _key, spelling, identity, name, maximum, raw in handoff.files:
            path = Path(spelling)
            key = "recipient:" + str(path)
            if key not in self.handles:
                self.handles[key] = owner.open(path)
            directory = self.handles[key]
            _new_entry_owned(owner, directory, path, identity)
            require(owner.read(directory, name, maximum) == raw, "BOOTSTRAP_INIT_RECIPIENT_ORIGINAL_CHANGED")
        self.check()

    def absent_state(self):
        owner = self.live()
        require("state" not in {name.casefold() for name in _initializer_names(owner, self.handles["session"])},
                "BOOTSTRAP_INIT_STATE_ALREADY_EXISTS")

    def private_inputs(self):
        owner = self.live()
        phase, path = _parent_location(self)
        for name in ("session", phase, "control-home", "temporary"):
            _new_entry_owned(owner, self.handles[name], path if name == "session" else path / name,
                             self.identities[name])
        self.recipient_originals()
        for key, directory, target, identity, name, maximum, raw in _recipient_parent_registration(self)[3].files:
            _new_entry_owned(owner, directory, target, identity)
            require(self.records.get(key) == raw and owner.read(directory, name, maximum) == raw,
                    "BOOTSTRAP_INIT_RETAINED_ORIGINAL_CHANGED")
        self.request_unchanged()
        if not self.row.get("launchAttempted"):
            self.absent_state()

    def admit(self):
        """Fresh real query supplier; all of its finalization stays in work120.

        Do not mutate Owner limits or borrow native/read reservations. The one
        immutable supplier pair intersects original75/120 with remaining work;
        setup and its actual close/return never restart this parent's allowance.
        """
        owner, window = self.live(), self.window
        directory = _parent_location(self)[1] / "admission"
        supplier = original = result = None
        began = window.now()
        work = min(window.work, origin.integer(began + 75 * origin.NS))
        final = min(window.work, origin.integer(began + 120 * origin.NS))
        pair = (window.deadline(75, limit=work), window.deadline(120, limit=final))
        try:
            supplier = query.NativeGitQueries(ROOT, directory, check_cancel=lambda: window.now(limit=work),
                                              owner_deadlines=pair)
            supplier.native_host_matches_actions()
            result = bootstrap.admit(ROOT, query_runner=supplier, expected=self.transition._attempt.admitted)
            supplier.retain_admission(result)
            window.now(limit=work)
        except BaseException as error:
            original = error
        finally:
            if supplier is not None:
                try:
                    supplier._finalize(original)
                except BaseException as error:
                    if original is None:
                        original = error
            if (supplier is not None and supplier.unknown) or query.QUARANTINE or diagnostics._QUARANTINE:
                if original is None:
                    original = origin.OriginError("BOOTSTRAP_INIT_QUERY_UNKNOWN")
                self.error("initializer-native-query", original, unknown=True)
        if original is not None:
            raise original
        window.now(limit=final)
        require(type(result) is I.Admission and result == self.transition._attempt.admitted,
                "BOOTSTRAP_INIT_READMISSION")
        retained = owner.open(directory)
        require(load_admission(owner, retained) == result, "BOOTSTRAP_INIT_READMISSION_CHANGED")
        for name, raw in (("admission.json", result.record), ("original-event.json", result.original_event),
                ("original-policy.json", result.original_policy), ("recipient-public.asc", result.public_key),
                ("session-result.json", owner.read(retained, "session-result.json"))):
            self.remember_file("admission/" + name, retained, name, raw)
        session = origin.parse(self.records["admission/session-result.json"])
        require(set(session) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"} and
                type(session["schema"]) is int and session["schema"] == 1 and session["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
                type(session["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", session["job"]) and
                type(session["queries"]) is list and type(session["readbacks"]) is list and
                session["result"] == "READY_FOR_CALLER_SEAL" and session["retirement"] == "KNOWN" and
                session["firstError"] is None and session["errors"] == [], "BOOTSTRAP_INIT_QUERY_RETURN")
        returned = {"admissionSha256": origin.digest(result.record),
            "sessionSha256": origin.digest(self.records["admission/session-result.json"]),
            "clock": origin.clock_value(window.clock), "returnedNs": window.now(limit=final)}
        target = self.handles["canonical-init"]
        self.remember_file("admission-return.json", target, "admission-return.json",
                           owner.write(target, "admission-return.json", returned))
        window.now(limit=final)

    def initialized_state(self, *, first=False):
        owner = self.live()
        self.phase_writers_closed()
        path = _parent_location(self)[1] / "state"
        for name in ("state", "gradle-home", "evidence", "cancellations"):
            key = "state:" + name
            if first:
                self.handles[key] = owner.child(self.handles["session"] if name == "state" else self.handles["state:state"], name)
                self.identities[key] = directory_identity(list(self.handles[key].identity), self.first.clock.role)
            _new_entry_owned(owner, self.handles[key], path if name == "state" else path / name, self.identities[key])
            expected = (("cancellations", "context.json", "evidence", "gradle-home") if name == "state" else
                        ("gradle.properties",) if name == "gradle-home" else ())
            require(_initializer_names(owner, self.handles[key]) == expected, "BOOTSTRAP_INIT_STATE_ROSTER_CHANGED")
        context = owner.read(self.handles["state:state"], "context.json")
        policy = owner.read(self.handles["state:gradle-home"], "gradle.properties", 16384)
        inputs = self.init_inputs()
        value = initialization.context_record(context, admitted_raw=self.transition._attempt.admitted.record,
            root=str(ROOT), state=str(path), role=self.first.clock.role,
            outer_job=origin.parse(self.records["context"])["job"], homes=inputs.homes, policy_raw=policy)
        require(value["id"] != origin.parse(_recipient_parent_registration(self)[4].recipient.records["context"])["job"],
                "BOOTSTRAP_INIT_CONTEXT_JOB")
        if first:
            self.remember_file("canonical-context.json", self.handles["state:state"], "context.json", context)
            self.remember_file("gradle.properties", self.handles["state:gradle-home"], "gradle.properties", policy, 16384)
        else:
            require(context == self.records["canonical-context.json"] and policy == self.records["gradle.properties"],
                    "BOOTSTRAP_INIT_CONTEXT_OR_POLICY_CHANGED")
        _initializer_outputs_absent(owner)

    def read_child(self):
        owner, window = self.live(), self.window
        window.begin_read()
        directory = self.handles["canonical-init"]
        try:
            for name, maximum in (("stdout", ACK_LIMIT), ("stderr", STDERR_LIMIT)):
                raw = owner.read(directory, name + ".log", maximum)
                self.remember_file(name + ".log", directory, name + ".log", raw, maximum)
                self.row["captureOutcomes"][name]["readback"] = True
            expected = initialization.stdout_path(str(_parent_location(self)[1] / "state"), window.clock.role)
            require(self.records["stdout.log"] == expected and self.records["stderr.log"] == b"",
                    "BOOTSTRAP_INIT_STDOUT_CONTEXT_PATH")
            self.initialized_state(first=True)
            self.row.update(retirement="KNOWN", captures={name: {"sha256": origin.digest(self.records[name + ".log"]),
                "bytes": len(self.records[name + ".log"])} for name in ("stdout", "stderr")}, errors=[])
            self.native_content()
            self.reread_files()
            self.read_originals()
            self.initialized_state()
            self.reread_files()
            window.now()
            self.child_accepted = True
        except BaseException as error:
            self.error("initializer-readback", error, unknown=True)
            raise self.original


@dataclass(frozen=True)
class InitializationPrefix:
    """Closed initialization evidence only. No producer/export/save authority."""
    raw: bytes = field(repr=False)
    pending_raw: bytes = field(repr=False)
    originals: tuple = field(repr=False)
    checked_ns: int = field(repr=False)


def _initialize_claimed(call):
    require(type(call) is _InitializerParent and call.state == "CLAIMED", "BOOTSTRAP_INIT_ALREADY_CLAIMED")
    saved = _parent_originals(call)
    control, registered = saved[0], saved[4]
    call.state = "STARTING"  # Consumed before the first fallible supplier.
    owner = window = None
    try:
        call.check()
        call.local_start = time.monotonic()
        call.first = origin.clocks.observe()
        call.callback = call.cancel
        call.window = window = _InitializerWindow(call)
        call.owner = owner = Owner(window.local_end, window, first=call.first, cancelled=call.callback)
        call.bindings = _RecipientParentBindings(owner, window, call.first, call.callback, call.local_start, owner.local_end,
            owner.admissions, owner.resources, owner.errors, window_state=[window.phase_state()],
            observations=[window.last, window.local_last])
        with _INITIALIZER_CLAIM_LOCK:
            _bind_parent_control(call, control, (*registered[:3], call.bindings, *registered[4:]))
        call.errors, call.state = owner.errors, "RUNNING"
        owner.end()
        _install_parent_handlers(call, control)
        call.host()
        for name, path in zip(("original", "adoption", "entry"), call.paths()[:3]):
            call.handles[name] = owner.open(path)
        call.read_originals()
        call.recipient_originals()
        phase, path = _parent_location(call)
        initialization.stdout_path(str(path / "state"), window.clock.role)
        call.handles["session"] = owner.new(path)
        for name in (phase, "control-home", "temporary"):
            call.handles[name] = owner.child(call.handles["session"], name, create=True)
        for name in ("session", phase, "control-home", "temporary"):
            call.handles[name].verify()
            call.identities[name] = directory_identity(list(call.handles[name].identity), window.clock.role)
            owner.end()
        call.absent_state()  # Canonical initialize(), not this parent, creates it.
        call.remember_file("recipient-closed.json", call.handles["session"], "recipient-closed.json",
                           owner.write(call.handles["session"], "recipient-closed.json", registered[4].raw))
        toolchains = initialization.installed_toolchains()
        owner.end()
        interpreter = canonical._interpreter()
        request_raw = canonical.init_request(state=str(path / "state"),
            expected_commit=origin.parse(call.transition._attempt.admitted.record)["source"]["commit"], role=window.clock.role)
        owner.end()
        environment = recipient_environment(path)
        environment.update(toolchains.environment())
        homes = toolchains.homes()
        inputs = _InitializationInputs(request_raw, interpreter, toolchains,
            tuple(sorted(environment.items())), homes, initialization.properties(homes))
        call.bindings.initialization.append(inputs)
        with _INITIALIZER_CLAIM_LOCK:
            current = _INITIALIZER_ATTEMPTS[id(registered[4].recipient)]
            require(current[5] is None, "BOOTSTRAP_INIT_INPUTS_ALREADY_BOUND")
            _bind_parent_control(call, control, (*current[:5], (inputs,
                (inputs.request_raw, inputs.interpreter, inputs.environment, inputs.homes, inputs.policy,
                 inputs.toolchains, inputs.toolchains.originals))))
        call.request_unchanged()
        call.remember_file("request.json", call.handles[phase], "request.json",
                           owner.write(call.handles[phase], "request.json", request_raw))
        call.admit()
        call.read_originals()
        call.recipient_originals()
        # Readmission is a supplier boundary too. Reject an unexpected state
        # before preparing any native initializer scope/captures, while keeping
        # the later immediate prelaunch absence checks as well.
        call.absent_state()
        _initializer_outputs_absent(owner)
        context = {"schema": 1, "scope": "BOOTSTRAP_INITIALIZER_PARENT_CONTEXT_V1", "job": uuid.uuid4().hex,
            "previousSha256": origin.digest(registered[4].raw), "requestSha256": origin.digest(request_raw),
            "admissionSha256": origin.digest(call.transition._attempt.admitted.record),
            "clock": origin.clock_value(window.clock), "directories": call.identities,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        call.remember_file("context", call.handles["session"], "initializer-context.json",
                           owner.write(call.handles["session"], "initializer-context.json", context))
        invocation = uuid.uuid4().hex
        environment = processes.ownership_environment(_parent_environment(call), context["job"], invocation,
            str(path), str(path / "control-home"), allow_new_context=True)
        start = {"schema": 1, "scope": "BOOTSTRAP_INITIALIZER_PARENT_PRELAUNCH_V1",
            "contextSha256": origin.digest(call.records["context"]), "argv": _parent_argv(call),
            "cwd": str(ROOT), "role": window.clock.role, "job": context["job"], "invocation": invocation,
            "state": str(path), "home": str(path / "control-home"),
            "inheritedContext": {name: environment[name] for name in query._CONTEXT}, "startedNs": window.first,
            "workEndNs": window.work, "finalEndNs": window.native_end, "exitCode": None,
            "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"}
        call.remember_file("start.json", call.handles[phase], "start.json", owner.write(call.handles[phase], "start.json", start))
        call.launch()
        call.read_child()
        call.remember_file("result.json", call.handles[phase], "result.json", owner.write(call.handles[phase], "result.json", call.row))
        call.pending_raw = owner.write(call.handles["session"], "initializer-prefix-pending.json", {
            "schema": 1, "scope": "BOOTSTRAP_INITIALIZER_PREFIX_PENDING_RESOURCE_CLOSE_V1",
            "recipientClosedSha256": origin.digest(registered[4].raw), "window": window.record(),
            "originalsSha256": {name: origin.digest(raw) for name, raw in call.records.items()},
            "childReturn": "INITIALIZED_CONTEXT_NOT_PRODUCT_RECEIPT", "parentResourceClose": "PENDING_CLOSE",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        call.reread_files()
        call.read_originals()
        call.initialized_state()
        call.reread_files()
        call.native_content()
        require(owner.read(call.handles["session"], "initializer-prefix-pending.json") == call.pending_raw,
                "BOOTSTRAP_INIT_PENDING_CHANGED")
        call.cancel()
        owner.end()
    except BaseException as error:
        call.error("initializer-prefix", error, unknown=call.row.get("launchAttempted", False) and not call.child_accepted)
        if owner is not None and not owner.closed and not owner.unknown and "session" in call.handles:
            try:
                if window.phase == "WORK":
                    window.begin_final()
                call.check()
                call.failure_custody = "INCOMPLETE"
                owner.write(call.handles["session"], "initializer-prefix-failure.json", {"schema": 1, "result": "HOLD",
                    "errors": call.errors, "window": window.record(), "parentResourceClose": "PENDING_CLOSE",
                    "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}, final=True)
                call.failure_custody = "PRIVATE_PROVISIONAL_ONLY"
            except BaseException as secondary:
                call.error("initializer-failure-retention", secondary)
    finally:
        _close_parent(call, owner, window, control)
    try:
        if call.original is not None:
            raise call.original
        call.check(full=True)
        require(owner is not None and owner.closed and not owner.unknown and not call.unknown and call.child_accepted and
                call.bindings.handler_restored == call.bindings.handler_rows and
                all(row["attempted"] is True and row["closed"] is True for row in owner.resources),
                "BOOTSTRAP_INIT_PREFIX_NOT_CLOSED")
        call.cancel()
        closed = window.now(minimum=call.row["finalizedNs"])
        raw = origin.encoded({"schema": 1, "scope": "BOOTSTRAP_INITIALIZER_PREFIX_CLOSED_NO_EXECUTION_V1",
            "recipientClosedSha256": origin.digest(registered[4].raw), "pendingSha256": origin.digest(call.pending_raw),
            "window": window.record(), "closedNs": closed, "resourceCount": len(owner.resources),
            "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "childReturn": "INITIALIZED_CONTEXT_NOT_PRODUCT_RECEIPT",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False})
        call.cancel()
        call.check(full=True)
        checked = window.now(minimum=closed)
        call.check()
        call.closed_roster()
        require(window.last == checked and owner.original is None and not owner.unknown and
                all(row["attempted"] is True and row["closed"] is True for row in owner.resources),
                "BOOTSTRAP_INIT_FINAL_STATE_CHANGED")
        call.result = InitializationPrefix(raw, call.pending_raw, tuple(sorted(call.records.items())), checked)
        call.state = "COMPLETE"
        return call.result
    except BaseException as error:
        call.error("initializer-final-return", error)
        call.closed_roster()
        call.state = "FAILED"
        if owner is not None and (owner.unknown or call.unknown) and not any(actual is owner for actual in QUARANTINE):
            QUARANTINE.append(owner)
        raise call.original


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
                if original is None:
                    original = error
    if original is not None:
        raise original
    value, fence, limit = result
    cancellation(cancelled)
    observed = fence.now(final=True, limit=limit)
    if value.get("scope") in (ACK_SCOPE, RECIPIENT_ACK_SCOPE):
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
    for name in ("_service", "_recipient"):
        child = commands.add_parser(name)
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
            if args.operation == "_service":
                command(args.context_sha256, minimum)
                guarded(lambda cancelled: service_child(args.context_sha256, minimum, cancelled))
            else:
                recipient_command(args.context_sha256, minimum)
                guarded(lambda cancelled: recipient_child(args.context_sha256, minimum, cancelled))
        return 0
    except BaseException:
        # No exception/argv/path/response/token is suitable for public logs.
        print("CACHE_BOOTSTRAP_ORIGINALS_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
