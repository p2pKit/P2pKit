#!/usr/bin/env python3
"""Dormant configuration-bootstrap commands; no provider or Release execution.

No workflow, admitted productive budget, provider save,
policy installer or uploader exists here. Separate read-only original adoption
never becomes execution authority. A future trusted workflow must bind the
actual original prepare-step outcome, not a provisional receipt/digest.
The fixed producer command composes the original-call parents; no workflow
invokes it and CLI availability does not lift any execution HOLD.
Offline controls are not native,
custodian, scheduling or encrypted-custody qualification.
"""
from __future__ import annotations

import argparse
from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
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
import hosted_cache_bootstrap_collect_files as collect_files
import hosted_cache_bootstrap_custody as custody
import hosted_cache_bootstrap_export as dependency_export
import hosted_cache_bootstrap_save_set as dependency_save_set
import hosted_cache_bootstrap_history as history
import hosted_cache_bootstrap_identity as bootstrap
import hosted_cache_bootstrap_initialization as initialization
import hosted_cache_bootstrap_no_loader as no_loader
import hosted_cache_bootstrap_origin as origin
import hosted_cache_bootstrap_producer as producer
import hosted_cache_bootstrap_producer_command as producer_command
import hosted_cache_bootstrap_service_time as service_time
import hosted_cache_bootstrap_staging as staging
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
_STAGING_CLAIM_LOCK = threading.Lock()
_STAGING_ATTEMPTS = {}


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
        # A later RAW/LOCAL sample can shorten the final ceiling. Never pass
        # the native supplier a work deadline beyond that already-shorter end.
        pair = (min(pair), pair[1])
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
            drain_end = None
            try:
                try:
                    drain_end = min(owner.local_end, fence.deadline(45, final=True, limit=final_end))
                    remaining = max(0, drain_end - time.monotonic())
                except BaseException as error:
                    owner.error("drain-fence", error)
                    raise
                grace = min(5, remaining)
                kill_wait = min(5, max(0, remaining - grace))
                row["survivors"] = scope.drain(grace=grace, kill_wait=kill_wait, deadline=drain_end)
                require(row["survivors"] == [], "BOOTSTRAP_SERVICE_SURVIVORS")
                row["ownership"] = scope.description()
                require(row["ownership"].get("discoveryErrors") == [], "BOOTSTRAP_SERVICE_DISCOVERY_UNKNOWN")
                require(preparer_identity(scope, fence.clock.role) == row["preparerIdentity"],
                        "BOOTSTRAP_PREPARER_LIFETIME_CHANGED")
                fence.now(final=True, limit=final_end)
                posix._deadline(drain_end)  # Include time spent observing the original RAW fence.
                native_known = True
            except BaseException as error:
                owner.error("service-drain", error, unknown=True)
            owner.close_one(scope)
            if drain_end is not None:
                try:
                    fence.now(final=True, limit=final_end)
                    posix._deadline(drain_end)
                except BaseException as error:
                    native_known = False
                    owner.error("service-drain-close-fence", error, unknown=True)
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
    require(type(reader) in (_LegacyOriginalReader, _NewEntryOriginalReader, _RecipientParentReader,
                            _StagingOriginalReader, _ProducerOriginalReader, _CollectionPhaseReader),
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
    require(type(reader) in (_LegacyOriginalReader, _NewEntryOriginalReader, _RecipientParentReader,
                            _StagingOriginalReader, _ProducerOriginalReader, _CollectionPhaseReader) and
            reader.first is not None,
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
    """Old-owner close bridge used by the dormant fixed producer command.

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
    export/save authority. The fixed producer command calls it; no workflow does.
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


def _prepare_adoption(cancelled):
    """Shared fixed live-entry preparation; the successful caller owns its close.

    The two environment inputs must eventually come from the fixed trusted
    prepare step's ORIGINAL outcome/hash. No workflow wires that authority yet.
    Fresh readmission records go in a separate exclusive sibling; preparation
    originals are never modified. Every operation shares the original prelude.
    Failure before returning the live entry keeps this helper's cleanup duty.
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
        try:
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
            except BaseException as secondary:
                owner.error("adoption-close", secondary)
        raise owner.original if owner.original is not None else error
    return owner, target, entry, fence, result_raw


def adopt_originals(cancelled):
    """Read-only command: never selects the productive successor."""
    owner, _target, _entry, fence, result_raw = _prepare_adoption(cancelled)
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


def produce_originals(cancelled):
    """Fixed dormant composition, not an admitted budget or provider operation.

    No returned transition is reconstructed from disk. Once the old close
    returns, its graph/fence is immutable: later failures belong to their NEW
    owners, never to adoption's old failure-retention or completion tail.
    """
    owner, target, entry, fence, _raw = _prepare_adoption(cancelled)
    try:
        closed = close_entry_transition(owner, target, entry, fence)
    except BaseException as error:
        # A rejected pre-claim close leaves responsibility with this caller.
        # The bridge already handles claimed/closed failures; do not mutate it.
        if not owner.closed:
            try:
                owner.error("producer-entry-close", error)
            finally:
                try:
                    owner.close()
                except BaseException as secondary:
                    owner.error("producer-entry-close-return", secondary)
        raise owner.original if owner.original is not None else error
    current = readmit_closed_entry(closed)
    returned = save_handoff_after_entry(current)
    # This private original-call continuation retains the handoff function's
    # actual return under its SAME remaining fence, then hands it to guarded.
    return returned._complete(returned)


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
        width = 7
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
            require(all(type(value) is bool for value in registered[4:]) and
                    (not registered[6] or registered[5]) and (not registered[5] or registered[4]),
                    "BOOTSTRAP_RECIPIENT_INTENT_CHANGED")
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
            drain_end = None
            try:
                try:
                    require(final_ready, "BOOTSTRAP_RECIPIENT_FINAL_START_FAILED")
                    drain_end = window.cleanup_deadline(45)
                    remaining = max(0, drain_end - window.local_now(cleanup=True))
                except BaseException as error:
                    self.error("recipient-drain-fence", error)
                    raise
                grace = min(5, remaining)
                self.row["survivors"] = scope.drain(grace=grace, kill_wait=min(5, max(0, remaining - grace)),
                                                   deadline=drain_end)
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
                window.now(final=True)
                posix._deadline(drain_end)
                self.native_retired = True
            except BaseException as error:
                self.error("recipient-drain", error, unknown=True)
            attempted, closed = self.close_phase_resource("native-scope")
            self.row.update(scopeCloseAttempted=attempted, scopeClosed=closed)
            self.native_retired &= closed
            if drain_end is not None:
                try:
                    window.now(final=True)
                    posix._deadline(drain_end)
                except BaseException as error:
                    self.native_retired = False
                    self.error("recipient-drain-close-fence", error, unknown=True)
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
    """Once-claimed standalone recipient prefix; no workflow activation.

    All resources and handlers close in this one call under the ORIGINAL prefix
    caps. No live Recipient is reconstructed from child JSON; this wrapper never
    selects initialization. Producer/cache/custody remains separate unfinished work.
    """
    return _recipient_after_entry(transition, initialize=False, stage=False, reserve=False)


def initialize_after_entry(transition):
    """INTERNAL same-call recipient + initialization, never Prefix authority.

    No public CLI or workflow calls this operation. The original shared claim
    fixes its intent before any clock/native/file supplier and consumes failure.
    Initialization yields evidence only, not producer/cache permission.
    """
    return _recipient_after_entry(transition, initialize=True, stage=False, reserve=False)


def stage_after_entry(transition):
    """INTERNAL same-call recipient, initializer and empty staging/seed prefix.

    Intent is fixed before the shared claim, never selected by returned JSON.
    No CLI, workflow, producer or provider calls this dormant operation.
    """
    return _recipient_after_entry(transition, initialize=True, stage=True, reserve=False)


def reserve_configuration_after_entry(transition):
    """INTERNAL one-claim prefix through file-only configuration reservation.

    The original claim fixes reserve => stage => initialize before suppliers.
    The dormant producer uses this prefix; this function launches no producer.
    """
    return _recipient_after_entry(transition, initialize=True, stage=True, reserve=True)


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


def _recipient_after_entry(transition, *, initialize, stage, reserve):
    require(all(type(value) is bool for value in (initialize, stage, reserve)) and
            (not reserve or stage) and (not stage or initialize), "BOOTSTRAP_RECIPIENT_INTENT")
    check_new_entry_transition(transition)
    pins = (*_recipient_predecessor_pins(transition), _RecipientPredecessorGraph.capture(transition))
    call = _RecipientParent(transition, pins)
    with _RECIPIENT_CLAIM_LOCK:
        require(id(transition) not in _RECIPIENT_ATTEMPTS, "BOOTSTRAP_RECIPIENT_ALREADY_CLAIMED")
        _RECIPIENT_ATTEMPTS[id(transition)] = (transition, call, pins, None, initialize, stage, reserve)
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
            _bind_parent_control(call, control, (transition, call, pins, call.bindings, initialize, stage, reserve))
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
        require(registered[4] is initialize and registered[5] is stage and registered[6] is reserve and
                registered[3].handler_restored == registered[3].handler_rows,
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
    initialized = _initialize_claimed(next_call)
    # Actual initializer return precedes this separate one-use claim. Its
    # COMPLETE state/result and closed graph remain untouched on downstream
    # success OR failure; neither old failure handler encloses the next call.
    return _stage_after_initialization(next_call, initialized) if stage else initialized


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


@dataclass(frozen=True)
class StagingPrefix:
    """Private final stage/empty-seed evidence; NEVER producer/cache authority."""
    raw: bytes = field(repr=False)
    stage_raw: bytes = field(repr=False)
    stage_leaf: object = field(repr=False)
    seed_leaf: object = field(repr=False)
    checked_ns: int = field(repr=False)
    checked_local: float = field(repr=False)


@dataclass(frozen=True)
class ConfigurationCustodyPrefix:
    """Closed reservation evidence only; NEVER a producer/next-phase permit."""
    raw: bytes = field(repr=False)
    staged: object = field(repr=False)
    custody_leaf: object = field(repr=False)
    checked_ns: int = field(repr=False)
    checked_local: float = field(repr=False)


@dataclass(frozen=True)
class _StagingPhaseReturn:
    raw: bytes = field(repr=False)
    leaf: object = field(repr=False)
    checked_ns: int = field(repr=False)
    checked_local: float = field(repr=False)


@dataclass(eq=False)
class _StagingSequence:
    initializer: object = field(repr=False)
    returned: object = field(repr=False)
    originals: object = field(default=None, repr=False)
    phases: tuple = field(default=(), repr=False)
    state: str = "CLAIMED"
    original: object = field(default=None, repr=False)
    result: object = field(default=None, repr=False)
    failure_custody: str = "UNAVAILABLE"


@dataclass(frozen=True)
class _StagingClosedGraph:
    """Typed transitive pins; no method on any closed owner/fence/resource.

    Initializer inputs, InstalledToolchains.originals and its actual returned
    result are traversed, not treated as opaque authority. This is finite
    in-process input binding, not a sandbox against replacing Python code.
    """
    nodes: tuple = field(repr=False)
    paths: tuple = field(repr=False)

    @classmethod
    def capture(cls, *roots):
        traversed = (NewEntryTransition, _EntryAttempt, ClosedEntryTransition, OriginalEntry, OriginalPhase,
            Owner, _StagingFileOwner, origin.Fence, _NewEntryWindow, I.Admission, origin.clocks.Reading, origin.clocks.ClockIdentity,
            _RecipientParent, _InitializerParent, _RecipientParentWindow, _InitializerWindow,
            _RecipientParentBindings, _RecipientResource, _ParentControl, _RecipientPredecessorGraph,
            _InitializerPredecessor, _InitializationInputs, initialization.InstalledToolchains,
            InitializationPrefix, _StagingPhaseParent, _StagingWindow, _StagingPhaseReturn, StagingPrefix,
            custody.StagedEvidence, custody.ReservationEvidence, ConfigurationCustodyPrefix,
            staging.Originals, staging.PhaseStart, staging.LeafEvidence)
        scalars = (type(None), bool, int, float, str, bytes, signal.Signals)
        sequences = (list, tuple, _StagingFrame, _StagingLimits, _CustodyRequestPin)
        pending, seen, nodes, paths = list(roots), set(), [], []
        while pending:
            value = pending.pop()
            kind = type(value)
            if kind in scalars or id(value) in seen:
                continue
            seen.add(id(value))
            require(len(seen) <= 10000, "BOOTSTRAP_STAGING_CLOSED_GRAPH_LIMIT")
            if kind is dict:
                saved, mode = tuple(value.items()), "mapping"
                require(all(type(key) in scalars for key, _item in saved), "BOOTSTRAP_STAGING_CLOSED_GRAPH_KEY")
                pending.extend(item for pair in saved for item in pair)
            elif kind in sequences:
                saved, mode = tuple(value), "sequence"
                pending.extend(saved)
            elif kind in traversed:
                saved, mode = object.__getattribute__(value, "__dict__"), "record"
                pending.append(saved)
                if kind in (_RecipientParent, _InitializerParent, _StagingPhaseParent):
                    paths.extend((directory, type(directory), directory.path, tuple(directory.identity))
                                 for directory in value.handles.values())
            else:
                saved, mode = None, "opaque"
            nodes.append((value, kind, mode, saved))
        result = cls(tuple(nodes), tuple(paths))
        result.checked()
        return result

    def checked(self):
        scalars = (type(None), bool, int, float, str, bytes, signal.Signals)
        def same(actual, original):
            return actual is original or (type(actual) is type(original) and type(original) in scalars and actual == original)
        for value, kind, mode, saved in self.nodes:
            require(type(value) is kind, "BOOTSTRAP_STAGING_CLOSED_GRAPH_CHANGED")
            if mode == "record":
                valid = object.__getattribute__(value, "__dict__") is saved
            elif mode == "mapping":
                valid = len(value) == len(saved) and all(same(key, old_key) and same(item, old_item)
                    for (key, item), (old_key, old_item) in zip(value.items(), saved))
            elif mode == "sequence":
                valid = len(value) == len(saved) and all(same(item, old) for item, old in zip(value, saved))
            else:
                valid = mode == "opaque"
            require(valid, "BOOTSTRAP_STAGING_CLOSED_GRAPH_CHANGED")
        for directory, kind, path, identity in self.paths:
            require(type(directory) is kind and type(directory.path) is type(path) and directory.path == path and
                    tuple(directory.identity) == identity, "BOOTSTRAP_STAGING_CLOSED_PATH_CHANGED")


# The private frames below are actual immutable tuples, not frozen dataclasses
# whose public __dict__ can redirect cleanup. Mutable resources are retained by
# original reference AND an independent row/label/flag snapshot. No frame is
# published on a caller object. Replacing a module registry or public alias
# rejects live work but does not redirect the original known close obligations.
_StagingSequenceFrame = namedtuple("_StagingSequenceFrame", "call registry record graph originals original_pin "
    "files paths callbacks phases state original registries plan result")
_StagingLimits = namedtuple("_StagingLimits", "clock first soft hard local_start local_soft local_hard")
_StagingFrame = namedtuple("_StagingFrame", "call sequence name previous previous_pin previous_graph published state "
    "first phase_start phase_pin limits owner window callback owner_bindings resources handles files handlers restored "
    "close_roster leaf leaf_pin pending_raw result last local_last original unknown query_attempted queries foreign_resources "
    "closed_frames staged staged_pin request_pin")
_CustodyRequestPin = namedtuple("_CustodyRequestPin", "path directory retained binding_raw")

_STAGING_RESOURCE_LABELS = frozenset({"directory", "writer", "bootstrap-leaf-initializer-session",
    "bootstrap-leaf-initializer-directory", "bootstrap-leaf-reader", "bootstrap-leaf-bootstrap-source",
    "bootstrap-leaf-bootstrap-source-parent", "bootstrap-leaf-container", "bootstrap-leaf-restore-home",
    "bootstrap-leaf-staging-writer", "bootstrap-leaf-dependency-seed-source-root",
    "bootstrap-leaf-dependency-seed-source-parent", "bootstrap-leaf-dependency-seed-input"})
_CUSTODY_RESOURCE_LABELS = _STAGING_RESOURCE_LABELS | frozenset({
    "bootstrap-leaf-custody-source-root", "bootstrap-leaf-custody-source-scripts",
    "bootstrap-leaf-custody-stage-container", "bootstrap-leaf-custody-stage-home",
    "bootstrap-leaf-custody-directory", "bootstrap-leaf-custody-retained", "bootstrap-leaf-custody-request-writer"})


def _staging_plan(registries):
    # The original recipient control, not a returned prefix or mutable boolean,
    # fixes the only two source-selected plans. Initializer indices stay intact.
    recipient = registries[7][4]
    require(type(recipient) is tuple and len(recipient) == 7 and
            recipient[4] is True and recipient[5] is True and type(recipient[6]) is bool,
            "BOOTSTRAP_STAGING_INTENT_NOT_ORIGINAL")
    return ("dependency-stage", "empty-seed", "custody-prepare") if recipient[6] else ("dependency-stage", "empty-seed")


def _staging_labels(frame):
    require(frame.name in ("dependency-stage", "empty-seed", "custody-prepare"), "BOOTSTRAP_STAGING_PHASE")
    return _CUSTODY_RESOURCE_LABELS if frame.name == "custody-prepare" else _STAGING_RESOURCE_LABELS


def _staging_leaf_capture(name, value):
    if name == "custody-prepare":
        require(type(value) is custody.ReservationEvidence, "BOOTSTRAP_CUSTODY_LEAF_KIND")
        return (staging._bytes(value.raw), staging._bytes(value.request_raw), origin.integer(value.checked_ns),
                staging._local(value.local_started), staging._local(value.checked_local))
    require(name in ("dependency-stage", "empty-seed"), "BOOTSTRAP_STAGING_PHASE")
    return staging._capture_evidence(value)


def _capture_custody_request(frame):
    """Bind the returned original request BEFORE any later clock/I/O supplier.

    Retained parent copies cannot replace the actual reservation file. Only
    detached immutable path/identity/binding values escape this data validator.
    """
    saved = _staging_sequence_frame(frame.sequence)
    inputs = custody._Inputs(saved.originals, saved.original_pin, frame.staged, frame.staged_pin)
    leaf = frame.leaf
    value, request = staging.files.record(leaf.raw), staging.files.record(leaf.request_raw)
    require(staging.files.encoded(value) == leaf.raw and staging.files.encoded(request) == leaf.request_raw,
            "BOOTSTRAP_CUSTODY_RETURN_ENCODING")
    file_binding, window = value.get("requestBinding"), value.get("window")
    require(staging.files._file_binding(file_binding) and type(window) is dict and
            set(window) == {"phase", "clock", "firstNs", "hardEndNs", "softEndNs", "lastNewWorkNs", "finishedNs",
                            "predecessorSha256", "predecessorCheckedNs", "proposalSha256"},
            "BOOTSTRAP_CUSTODY_RETURN_BINDING")
    limits = frame.limits
    last_new, finished = origin.integer(window["lastNewWorkNs"]), origin.integer(window["finishedNs"])
    require(limits.first <= last_new <= finished <= leaf.checked_ns < limits.hard,
            "BOOTSTRAP_CUSTODY_RETURN_CHRONOLOGY")
    custody._equal(window, {"phase": "custody-prepare", "clock": origin.clock_value(inputs.clock),
        "firstNs": limits.first, "hardEndNs": limits.hard, "softEndNs": limits.soft,
        "lastNewWorkNs": last_new, "finishedNs": finished, "predecessorSha256": origin.digest(frame.previous_pin[0]),
        "predecessorCheckedNs": frame.previous_pin[1], "proposalSha256": origin.digest(inputs.proposal_raw)},
        "BOOTSTRAP_CUSTODY_RETURN_WINDOW")
    custody._equal(value, {"schema": 1, "scope": custody.SCOPE, "binding": inputs.binding(),
        "predecessors": inputs.predecessors(), "status": "RESERVED_CONFIGURATION_ONLY", "completed": True,
        "leafHandleClose": "KNOWN", "enclosingOwnerRetirement": "NOT_OBSERVED_HERE", "nextPhaseAuthority": False,
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False,
        "requestSha256": origin.digest(leaf.request_raw), "requestBinding": file_binding, "window": window},
        "BOOTSTRAP_CUSTODY_RETURN_SCOPE")
    identities = request.get("directories")
    require(type(identities) is dict and set(identities) == {"custody", "retained"}, "BOOTSTRAP_CUSTODY_REQUEST_DIRECTORIES")
    directory, retained = (staging._identity(identities[name], inputs.role) for name in ("custody", "retained"))
    require(directory != retained and directory not in inputs.directories.values() and
            retained not in inputs.directories.values(), "BOOTSTRAP_CUSTODY_REQUEST_DIRECTORY_ALIAS")
    staging._identity(file_binding["identity"], inputs.role)
    require(set(request) == {"schema", "scope", "binding", "predecessors", "inputs", "bootstrapInputs", "custodyInputs",
            "fileBindings", "directory", "directories", "owner", "evidenceDirectory", "evidenceDirectoryOwnership",
            "purpose", "kind", "requestedArgv", "producerScope", "ancestorDomainChain", "loader", "sourceAdmission",
            "nextPhaseAuthority", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"},
            "BOOTSTRAP_CUSTODY_REQUEST_FIELDS")
    for name, expected in {"schema": 1, "scope": custody.REQUEST_SCOPE, "binding": inputs.binding(),
            "predecessors": inputs.predecessors(), "directory": str(inputs.directory),
            "purpose": custody.producer.PURPOSE, "kind": "gradle", "requestedArgv": list(bootstrap.COMMAND),
            "producerScope": bootstrap.PRODUCER_SCOPE, "evidenceDirectoryOwnership": "NOT_CREATED_HERE",
            "ancestorDomainChain": "NOT_SYNTHESIZED_OR_ADMITTED", "loader": "NOT_INSTALLED_BY_CONFIGURATION_RESERVATION",
            "sourceAdmission": "NOT_ATTESTED_HERE", "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}.items():
        custody._equal(request[name], expected, "BOOTSTRAP_CUSTODY_REQUEST_SCOPE")
    return _CustodyRequestPin(str(inputs.directory), directory, retained, staging.files.encoded(file_binding))


def _custody_request_reader(parent):
    """Shared _read facade over this exact owner, not another owner/window.

    Immutable lexical pins survive public alias failure. Every actual resource
    still belongs to _StagingFileOwner's private ledger and original close path.
    """
    frame = parent.check()
    owner, window, request_pin = parent.live(), frame.window, frame.request_pin
    require(frame.name == "custody-prepare" and type(request_pin) is _CustodyRequestPin,
            "BOOTSTRAP_CUSTODY_REQUEST_NOT_BOUND")
    def bound():
        actual = _staging_owner_frame(owner)
        require(actual.call is parent and actual.window is window and actual.request_pin is request_pin and
                actual.name == "custody-prepare", "BOOTSTRAP_CUSTODY_REQUEST_READER_CHANGED")
        return actual
    class Reader:
        def check(self, *, new=False):
            require(type(new) is bool, "BOOTSTRAP_CUSTODY_REQUEST_READER_MODE")
            bound()
            window.now()  # Reads always use this phase's SOFT==HARD window.
            bound()

        def end(self, *, new=False):
            self.check(new=new)
            return owner.end()

        def acquire(self, label, factory):
            require(label == "reader", "BOOTSTRAP_CUSTODY_REQUEST_READER_LABEL")
            self.check(new=True)
            return owner.acquire("bootstrap-leaf-reader", factory)

        def error(self, stage, error, *, unknown=False):
            parent.error(stage, error, unknown=unknown)

        def close_one(self, resource):
            try:
                bound()
                owner.close_one(resource)
            except BaseException as error:
                parent.error("custody-request-close", error)
            actual = _staging_frame(parent)
            first = actual.original if actual.original is not None else owner.original
            if first is not None:
                raise first  # close_one can record rather than raise; preserve falsey first errors.
            require(not actual.unknown and not owner.unknown and
                    any(pin[2] is resource and pin[3] and pin[4] for pin in actual.resources),
                    "BOOTSTRAP_CUSTODY_REQUEST_CLOSE_UNKNOWN")
    return Reader()


def _staging_private_controls():
    sequences, frames, windows_by_id, owners_by_id = {}, {}, {}, {}
    def claim(sequence, registry, record):
        require(id(sequence) not in sequences, "BOOTSTRAP_STAGING_SEQUENCE_REENTRY")
        sequences[id(sequence)] = _StagingSequenceFrame(sequence, registry, record,
            None, None, None, (), (), (), (), "CLAIMED", None, (), (), None)
    def sequence_frame(sequence):
        saved = sequences.get(id(sequence))
        require(type(saved) is _StagingSequenceFrame and saved.call is sequence, "BOOTSTRAP_STAGING_NOT_CLAIMED")
        return saved
    def sequence_update(sequence, **values):
        saved = sequence_frame(sequence)
        sequences[id(sequence)] = saved._replace(**values)
        return sequences[id(sequence)]
    def register(parent, previous_pin, previous_graph, *, closed_frames=(), staged=None):
        saved = _staging_sequence_checked(parent.sequence)
        require(saved.state == "RUNNING" and len(saved.phases) < len(saved.plan) and
                parent.name == saved.plan[len(saved.phases)] and
                id(parent) not in frames, "BOOTSTRAP_STAGING_PHASE_REENTRY")
        staged_pin = None if staged is None else custody._capture_staged(staged)
        saved = sequence_update(parent.sequence, phases=(*saved.phases, parent))
        parent.sequence.phases = saved.phases
        frames[id(parent)] = _StagingFrame(parent, parent.sequence, parent.name, parent.previous,
            previous_pin, previous_graph, (parent.handles, parent.records, parent.handlers, parent.cancelled),
            "CLAIMED", None, None, None, None, None, None, None, None, (), (), (), (), (), None,
            None, None, None, None, None, None, None, False, False, (), (), closed_frames, staged,
            staged_pin, None)
    def frame(parent):
        saved = frames.get(id(parent))
        require(type(saved) is _StagingFrame and saved.call is parent, "BOOTSTRAP_STAGING_PHASE_NOT_CLAIMED")
        return saved
    def update(parent, **values):
        saved = frame(parent)
        frames[id(parent)] = saved._replace(**values)
        if "window" in values:
            require(saved.window is None and values["window"] is not None, "BOOTSTRAP_STAGING_WINDOW_REENTRY")
            windows_by_id[id(values["window"])] = parent
        if "owner" in values:
            require(saved.owner is None and type(values["owner"]) is _StagingFileOwner,
                    "BOOTSTRAP_STAGING_OWNER_REENTRY")
            owners_by_id[id(values["owner"])] = parent
        return frames[id(parent)]
    def window_frame(window):
        parent = windows_by_id.get(id(window))
        saved = frame(parent)
        require(saved.window is window, "BOOTSTRAP_STAGING_WINDOW_NOT_BOUND")
        return saved
    def owner_frame(owner):
        saved = frame(owners_by_id.get(id(owner)))
        require(saved.owner is owner, "BOOTSTRAP_STAGING_OWNER_NOT_BOUND")
        return saved
    return claim, sequence_frame, sequence_update, register, frame, update, window_frame, owner_frame


(_claim_staging_sequence, _staging_sequence_frame, _update_staging_sequence, _register_staging_phase,
 _staging_frame, _update_staging_frame, _staging_window_frame, _staging_owner_frame) = _staging_private_controls()
del _staging_private_controls


def _staging_sequence_checked(sequence):
    saved = _staging_sequence_frame(sequence)
    require(type(sequence) is _StagingSequence and _STAGING_ATTEMPTS is saved.registry and
            saved.registry.get(id(sequence.initializer)) is saved.record and
            saved.record[0] is sequence.initializer and saved.record[1] is sequence.returned and saved.record[2] is sequence and
            sequence.originals is saved.originals and sequence.phases is saved.phases and sequence.state == saved.state and
            sequence.original is saved.original and sequence.result is saved.result and saved.graph is not None,
            "BOOTSTRAP_STAGING_SEQUENCE_CHANGED")
    entries, recipients, initializers, controls, attempt, entry_record, init_frame, recipient_frame = saved.registries
    require(_ENTRY_ATTEMPTS is entries and _RECIPIENT_ATTEMPTS is recipients and
            _INITIALIZER_ATTEMPTS is initializers and _PARENT_CONTROLS is controls and
            entries.get(id(attempt.transition)) is entry_record and _entry_attempt_record(attempt) is entry_record and
            all(_parent_originals(frame[1]) is frame and _parent_control(frame[1]) is frame[0] and
                controls.get(id(frame[1])) is frame[0] and frame[2].get(frame[3]) is frame[4]
                for frame in (init_frame, recipient_frame)), "BOOTSTRAP_STAGING_REGISTRY_CHANGED")
    saved.graph.checked()
    require(type(saved.plan) is tuple and saved.plan == _staging_plan(saved.registries) and
            len(saved.phases) <= len(saved.plan) and
            all(type(parent) is _StagingPhaseParent and parent.name == saved.plan[index]
                for index, parent in enumerate(saved.phases)), "BOOTSTRAP_STAGING_PLAN_CHANGED")
    require(staging._capture(saved.originals) == saved.original_pin, "BOOTSTRAP_STAGING_ORIGINALS_CHANGED")
    return saved


def _capture_staging_initializer(initializer, returned):
    """Only called after actual _initialize_claimed return; entirely passive."""
    require(type(initializer) is _InitializerParent and type(returned) is InitializationPrefix and
            initializer.state == "COMPLETE" and initializer.result is returned,
            "BOOTSTRAP_STAGING_NOT_ORIGINAL_INITIALIZER_RETURN")
    frame = _parent_originals(initializer)
    registered, bound, predecessor = frame[4], frame[4][3], frame[4][4]
    require(_parent_control(initializer) is frame[0] and _PARENT_CONTROLS.get(id(initializer)) is frame[0] and
            frame[2] is _INITIALIZER_ATTEMPTS and _INITIALIZER_ATTEMPTS.get(frame[3]) is registered and
            type(predecessor) is _InitializerPredecessor and type(bound) is _RecipientParentBindings and
            registered[0] is initializer.transition and registered[2] is initializer.originals and bound is initializer.bindings,
            "BOOTSTRAP_STAGING_INITIALIZER_REGISTRY_CHANGED")
    predecessor.checked(initializer)  # Pure closed graph; no old Owner/Fence/resource calls.
    recipient_frame = _parent_originals(predecessor.recipient)
    require(_parent_control(predecessor.recipient) is recipient_frame[0] and
            _PARENT_CONTROLS.get(id(predecessor.recipient)) is recipient_frame[0] and
            recipient_frame[2] is _RECIPIENT_ATTEMPTS and recipient_frame[4] is predecessor.registered and
            recipient_frame[4][4] is True and recipient_frame[4][5] is True,
            "BOOTSTRAP_STAGING_INTENT_NOT_ORIGINAL")
    owner, window = bound.owner, bound.window
    require(type(owner) is Owner and type(window) is _InitializerWindow and initializer.owner is owner and
            initializer.window is window and owner.fence is window and owner.first is bound.first and
            owner.cancelled is bound.callback and owner.resources is bound.resources and owner.errors is bound.errors and
            owner.admissions is bound.admissions and owner.local_end == bound.local_end and
            owner.work_limit is None and owner.final_limit is None and owner.closed is True and
            owner.original is None and owner.unknown is False and initializer.original is None and
            initializer.unknown is False and initializer.child_accepted is True and
            bound.handler_rows == bound.handler_restored and len(bound.close_roster) == 1 and
            len(owner.resources) == len(bound.seen) == len(bound.close_roster[0]) and window.last == returned.checked_ns and
            window.phase == "READ", "BOOTSTRAP_STAGING_INITIALIZER_NOT_CLOSED")
    for row, pin, closed in zip(owner.resources, bound.seen, bound.close_roster[0]):
        require(row is pin.row and closed[0] is row and row["label"] == closed[1] == pin.label and
                row["owner"] is closed[2] is pin.resource and row["attempted"] is True and row["closed"] is True and
                pin.attempted is True and pin.closed is True, "BOOTSTRAP_STAGING_INITIALIZER_ROSTER")
    inputs_pin = registered[5]
    require(type(inputs_pin) is tuple and len(inputs_pin) == 2 and type(inputs_pin[0]) is _InitializationInputs and
            bound.initialization == [inputs_pin[0]] and type(inputs_pin[0].toolchains) is initialization.InstalledToolchains,
            "BOOTSTRAP_STAGING_INITIALIZER_INPUTS")
    inputs, expected = inputs_pin
    require((inputs.request_raw, inputs.interpreter, inputs.environment, inputs.homes, inputs.policy) == expected[:5] and
            inputs.toolchains is expected[5] and inputs.toolchains.originals == expected[6] and
            returned.pending_raw == initializer.pending_raw and returned.originals == tuple(sorted(initializer.records.items())),
            "BOOTSTRAP_STAGING_INITIALIZER_INPUTS_CHANGED")
    old = initializer.transition._attempt.transition
    context = origin.parse(old._entry.context_original)
    proposal = _entry_close_proposal(old._entry, old.responses)
    require(origin.encoded(proposal) == old.proposal_raw, "BOOTSTRAP_STAGING_PROPOSAL_CHANGED")
    original_path = Path(context["session"])
    paths = (original_path, original_path.with_name(original_path.name + "-adoption"),
             original_path.with_name(original_path.name + "-entry"),
             original_path.with_name(original_path.name + "-productive") / "initializer")
    originals = staging.Originals(initializer.transition._attempt.admitted, dict(old.responses),
        proposal["serviceTimeBasis"]["invocation"], bound.first.clock, context["runnerName"], old.proposal_raw,
        str(paths[0]), initializer.records["context"], initializer.records["canonical-context.json"],
        initializer.records["gradle.properties"], {name: tuple(initializer.identities[
            "session" if name == "session" else "state:" + name]) for name in staging.DIRECTORIES},
        returned.raw, returned.checked_ns, window.local_last)
    original_pin = staging._capture(originals)
    staging._Inputs(originals, original_pin)  # Strict data consistency, not the original-return claim above.
    files = predecessor.files + tuple((key, str(path), identity, name, maximum, raw)
        for key, _directory, path, identity, name, maximum, raw in bound.files)
    files += (("initializer-pending", str(paths[3]), tuple(initializer.identities["session"]),
               "initializer-prefix-pending.json", LIMIT, initializer.pending_raw),)
    attempt = initializer.transition._attempt
    entry_record = _entry_attempt_record(attempt)
    require(_ENTRY_ATTEMPTS.get(id(attempt.transition)) is entry_record,
            "BOOTSTRAP_STAGING_REGISTRY_CHANGED")
    registries = (_ENTRY_ATTEMPTS, _RECIPIENT_ATTEMPTS, _INITIALIZER_ATTEMPTS, _PARENT_CONTROLS,
                  attempt, entry_record, frame, recipient_frame)
    graph = _StagingClosedGraph.capture(initializer, returned, frame, recipient_frame, registries)
    return graph, originals, original_pin, files, paths, old._callbacks, registries


def _staging_actual_owner(frame):
    """Cleanup-only actual bindings; never a rejected public-parent alias."""
    owner, pin, limits = frame.owner, frame.owner_bindings, frame.limits
    require(type(owner) is _StagingFileOwner and owner.resources is pin[0] and owner.errors is pin[1] and
            owner.admissions is pin[2] and type(owner.local_end) is type(pin[3]) and owner.local_end == pin[3] and
            owner.first is frame.first and owner.cancelled is frame.callback and owner.fence is frame.window and
            type(frame.window) is _StagingWindow and frame.window.call is frame.call and
            owner.early_last == limits.first and owner.work_limit is None and owner.final_limit is None and
            type(owner.closed) is bool and type(owner.unknown) is bool and
            staging._capture_phase(frame.phase_start) == frame.phase_pin and
            frame.first.nanoseconds == limits.first and staging._clock(frame.first.clock) == limits.clock,
            "BOOTSTRAP_STAGING_OWNER_CHANGED")
    return frame


class _StagingFileOwner(Owner):
    """Exact new file-only owner. Ordinary Owner/Owner.bind stay unchanged.

    Leaf/write close_one calls and whole-parent close use the private original
    window and resource pins, never dispatch through a changed fence/row. A
    rejected public parent/registry alias cannot erase known cleanup. Actual
    owner/cap/roster corruption is UNKNOWN and forbids another resource close.
    """
    def _checked(self):
        frame = _staging_owner_frame(self)
        try:
            frame.call.roster()
            frame = _staging_owner_frame(self)
            require(frame.unknown is False, "BOOTSTRAP_STAGING_RETIREMENT_UNKNOWN")
            return _staging_actual_owner(frame)
        except BaseException as error:
            frame.call.error("staging-file-owner-binding", error, unknown=True)
            raise

    def end(self, *, final=False):
        # Check BEFORE inherited end can dispatch owner.fence.deadline.
        self._checked()
        result = super().end(final=final)
        self._checked().call.check()
        return result

    def acquire(self, label, factory, *, final=False):
        frame = self._checked()
        require(type(label) is str and label in _staging_labels(frame) and type(final) is bool,
                "BOOTSTRAP_STAGING_RESOURCE_LABEL")
        require(frame.state == "RUNNING" and frame.close_roster is None,
                "BOOTSTRAP_STAGING_ACQUIRE_NOT_LIVE")
        self.end(final=final)
        try:
            value = factory()
        except BaseException as error:
            frame.call.error(label + "-allocation", error, unknown=True)
            raise
        frame = _staging_owner_frame(self)
        # A duplicate return is still the original obligation, not a new row
        # or a second close. No supplier/check runs before retaining a NEW
        # actual return in the private acquisition ledger.
        require(not any(pin[2] is value for pin in frame.resources), "BOOTSTRAP_DUPLICATE_OWNER")
        row = {"label": label, "owner": value, "attempted": False, "closed": False}
        _update_staging_frame(frame.call, resources=(*frame.resources, (row, label, value, False, False)))
        try:
            # Use the original bound list even if the factory changed its
            # published alias. The post-return check rejects that change;
            # neither it nor a failed append can lose the actual allocation.
            frame.owner_bindings[0].append(row)
        except BaseException as error:
            frame.call.error(label + "-registration", error, unknown=True)
            raise
        self.end(final=final)
        return value

    def _cleanup_fence(self):
        try:
            frame = self._checked()
        except BaseException:
            return False  # The first binding error and original pins are retained.
        if self.unknown:
            return False
        try:
            # Captured private window, not self.fence or a caller alias.
            frame.window.now(final=True)
            posix._deadline(frame.owner_bindings[3])
        except BaseException as error:
            self.error("close-fence", error)
        try:
            self._checked()
        except BaseException:
            return False
        return not self.unknown

    def close_fence(self):
        self._cleanup_fence()

    def close_one(self, value):
        try:
            frame = self._checked()
            pin = next((pin for pin in frame.resources if pin[2] is value), None)
            require(pin is not None, "BOOTSTRAP_STAGING_CLOSE_FOREIGN_RESOURCE")
        except BaseException as error:
            _staging_owner_frame(self).call.error("staging-file-close-binding", error, unknown=True)
            return
        if self.unknown or pin[3] or not self._cleanup_fence():
            return
        frame = self._checked()
        row = pin[0]
        row["attempted"] = True
        _update_staging_frame(frame.call, resources=tuple(
            (*old[:3], True, old[4]) if old[0] is row else old for old in frame.resources))
        try:
            value.close()
            row["closed"] = True
            current = _staging_owner_frame(self)
            _update_staging_frame(frame.call, resources=tuple(
                (*old[:3], old[3], True) if old[0] is row else old for old in current.resources))
        except BaseException as error:
            self.error(pin[1] + "-close", error, unknown=True)
        self._cleanup_fence()  # Recheck before any later clock or close dispatch.

    def close(self):
        frame = self._checked()
        if self.closed:
            return
        self.closed = True
        self._cleanup_fence()
        for pin in reversed(frame.resources):
            if self.unknown:
                break
            self.close_one(pin[2])
        self._cleanup_fence()
        if self.unknown:
            if not any(value is self for value in QUARANTINE):
                QUARANTINE.append(self)
            raise origin.OriginError("BOOTSTRAP_RETIREMENT_UNKNOWN")


@dataclass(frozen=True)
class _StagingWindow:
    """Fixed file-only SOFT/HARD caps. No native45/read30 phase fallback."""
    call: object = field(repr=False, compare=False)

    @property
    def clock(self):
        return origin.clocks.ClockIdentity(*_staging_window_frame(self).limits.clock)

    @property
    def last(self):
        return _staging_window_frame(self).last

    @property
    def local_last(self):
        return _staging_window_frame(self).local_last

    def _sample(self, *, new, strict, minimum=0, limit=None):
        frame = _staging_window_frame(self)
        if strict:
            frame.call.check()
        elif frame.owner is not None:
            _StagingFileOwner._checked(frame.owner)
        limits = frame.limits
        local = staging._local(time.monotonic())
        require(local >= frame.local_last, "BOOTSTRAP_STAGING_LOCAL_BACKWARDS")
        _update_staging_frame(frame.call, local_last=local)
        observed = origin.clocks.checked_now(origin.clocks.ClockIdentity(*limits.clock),
            minimum_ns=max(frame.last, origin.integer(minimum)))
        _update_staging_frame(frame.call, last=observed)  # Retain valid RAW even if the next LOCAL fails.
        local_after = staging._local(time.monotonic())
        require(local_after >= local, "BOOTSTRAP_STAGING_LOCAL_BACKWARDS")
        _update_staging_frame(frame.call, local_last=local_after)
        end = limits.soft if new else limits.hard
        if limit is not None:
            end = min(end, origin.integer(limit))
        require(observed < end and local_after < (limits.local_soft if new else limits.local_hard),
                "BOOTSTRAP_STAGING_ORIGINAL_PHASE_EXPIRED")
        if strict:
            frame.call.check()
        elif frame.owner is not None:
            _StagingFileOwner._checked(frame.owner)
        return observed

    def now(self, *, final=False, minimum=0, limit=None):
        require(type(final) is bool, "BOOTSTRAP_STAGING_CLOCK_MODE")
        frame = _staging_window_frame(self)
        # Cleanup checks actual owner/window/roster bindings and immutable caps;
        # rejected public aliases do not erase known close work.
        observed = self._sample(new=not final, strict=not final, minimum=minimum, limit=limit)
        if not final:
            frame.call.cancel()
            observed = self._sample(new=True, strict=True, minimum=observed, limit=limit)
        return observed

    def deadline(self, maximum, *, final=False, limit=None):
        # Owner.end(final=True) is STILL an acquisition boundary. The seed's
        # 90-to120 tail permits only already-owned completion/close, never a
        # fresh file/query/record. Owner.close_fence uses now(final=True) instead.
        require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 120 and
                type(final) is bool, "BOOTSTRAP_STAGING_MAXIMUM")
        frame = _staging_window_frame(self)
        frame.call.check()
        local = staging._local(time.monotonic())
        observed = self.now(limit=limit)
        end = frame.limits.soft if limit is None else min(frame.limits.soft, origin.integer(limit))
        result = min(frame.limits.local_soft, origin.wire._directed_deadline(local, maximum, end, observed))
        frame.call.check()
        return result

    def record(self):
        frame = _staging_window_frame(self)
        frame.call.check()
        limits = frame.limits
        return {"phase": frame.name, "clock": origin.clock_value(self.clock), "firstNs": limits.first,
                "softEndNs": limits.soft, "hardEndNs": limits.hard, "budgetAcceptance": "NOT_ADMITTED"}


@dataclass(frozen=True)
class _StagingOriginalReader:
    """Exact new file-only reader kind, never an old owner's live-clock alias."""
    call: object = field(repr=False, compare=False)
    owner: object = field(init=False, repr=False, compare=False)
    current: object = field(init=False, repr=False, compare=False)
    past: object = field(init=False, repr=False)
    first: object = field(init=False, repr=False)

    def __post_init__(self):
        owner = self.call.live()
        old = self.call.original_transition()._attempt.transition
        for name, value in (("owner", owner), ("current", _staging_frame(self.call).window),
                ("past", history.snapshot(old._fence)), ("first", old._limits[8])):
            object.__setattr__(self, name, value)

    def checked(self):
        old = self.call.original_transition()._attempt.transition
        require(type(self.call) is _StagingPhaseParent and self.call.live() is self.owner and
                self.current is _staging_frame(self.call).window and self.first is old._limits[8] and
                history.checked(self.past) == history.snapshot(old._fence), "BOOTSTRAP_STAGING_READER_CHANGED")
        return self

    def observe(self, *, final, minimum):
        self.checked()
        # Historical final reads still acquire under THIS phase's SOFT cap.
        return self.current.now(minimum=minimum)


@dataclass(eq=False)
class _StagingPhaseParent:
    """File-only parent, deliberately NOT a _RecipientParent subclass."""
    sequence: object = field(repr=False)
    name: str
    previous: object = field(repr=False)
    state: str = "CLAIMED"
    first: object = field(default=None, repr=False)
    phase_start: object = field(default=None, repr=False)
    owner: object = field(default=None, repr=False)
    window: object = field(default=None, repr=False)
    callback: object = field(default=None, repr=False)
    handles: dict = field(default_factory=dict, repr=False)
    records: dict = field(default_factory=dict, repr=False)
    handlers: dict = field(default_factory=dict, repr=False)
    cancelled: list = field(default_factory=list, repr=False)
    leaf: object = field(default=None, repr=False)
    pending_raw: object = field(default=None, repr=False)
    result: object = field(default=None, repr=False)
    original: object = field(default=None, repr=False)
    unknown: bool = False

    def error(self, stage, error, *, unknown=False):
        frame = _staging_frame(self)
        owner = frame.owner
        first = frame.original
        if first is None:
            first = owner.original if owner is not None and owner.original is not None else error
        uncertain = frame.unknown or unknown or bool(QUARANTINE or query.QUARANTINE or diagnostics._QUARANTINE)
        uncertain |= diagnostics._exception_detail(error)["retirementUnknown"]
        _update_staging_frame(self, original=first, unknown=uncertain)
        self.original, self.unknown = first, uncertain
        if owner is not None:
            try:
                owner.error(stage, error, unknown=uncertain)
                uncertain |= owner.unknown
            except BaseException:
                # A corrupted published error container cannot replace the
                # first private error or authorize any more cleanup.
                owner.unknown, uncertain = True, True
        _update_staging_frame(self, original=first, unknown=uncertain)
        self.original, self.unknown = first, uncertain

    def roster(self):
        frame = _staging_frame(self)
        owner = frame.owner
        if owner is None:
            return
        original_rows = frame.owner_bindings[0]
        pins, foreign = frame.resources, list(frame.foreign_resources)
        seen = {(id(pin[0]), id(pin[2])) for pin in (*pins, *foreign)}
        # Retain original references even on removed/replaced rows. Suspicious
        # discoveries are NEVER acquisition authority, even on later checks
        # after a caller removes the extra row or restores public flags.
        for rows in (original_rows,) if owner.resources is original_rows else (original_rows, owner.resources):
            if type(rows) is list:
                for row in rows:
                    label, resource = (row.get("label"), row.get("owner")) if type(row) is dict else (None, None)
                    if (id(row), id(resource)) not in seen:
                        foreign.append((row, label, resource, False, False))
                        seen.add((id(row), id(resource)))
        _update_staging_frame(self, foreign_resources=tuple(foreign))  # Before any rejection.
        try:
            require(not foreign and owner.resources is original_rows and type(original_rows) is list and
                    len(original_rows) == len(pins),
                    "BOOTSTRAP_STAGING_ROSTER_CHANGED")
            if frame.close_roster is not None:
                require(len(original_rows) == len(frame.close_roster) and all(row is old[0] and row.get("label") == old[1]
                        and row.get("owner") is old[2] for row, old in zip(original_rows, frame.close_roster)),
                        "BOOTSTRAP_STAGING_CLOSE_ROSTER_CHANGED")
            for row, pin in zip(original_rows, pins):
                require(row is pin[0] and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                        row["label"] == pin[1] and pin[1] in _staging_labels(frame) and row["owner"] is pin[2] and
                        type(row["attempted"]) is bool and type(row["closed"]) is bool and
                        row["attempted"] is pin[3] and row["closed"] is pin[4],
                        "BOOTSTRAP_STAGING_ROSTER_CHANGED")
                # Only _StagingFileOwner's actual close path advances private
                # flags. Caller dictionaries cannot attest resource retirement.
        except BaseException as error:
            self.error("staging-roster", error, unknown=True)
            raise

    def check(self):
        self.roster()  # Retain real returned allocations before every callback/clock.
        frame = _staging_frame(self)
        sequence = _staging_sequence_checked(frame.sequence)
        require(type(self) is _StagingPhaseParent and self.sequence is frame.sequence and self.name == frame.name and
                self.previous is frame.previous and self.state == frame.state and self.first is frame.first and
                self.phase_start is frame.phase_start and self.owner is frame.owner and self.window is frame.window and
                self.callback is frame.callback and self.handles is frame.published[0] and self.records is frame.published[1] and
                self.handlers is frame.published[2] and self.cancelled is frame.published[3] and
                self.leaf is frame.leaf and self.pending_raw is frame.pending_raw and self.result is frame.result and
                self.original is frame.original and self.unknown is frame.unknown, "BOOTSTRAP_STAGING_PARENT_CHANGED")
        require(tuple(self.handles.items()) == tuple((row[0], row[1]) for row in frame.handles) and
                tuple(self.records.items()) == tuple((row[0], row[6]) for row in frame.files) and
                tuple(self.handlers.items()) == frame.handlers, "BOOTSTRAP_STAGING_PUBLIC_ROSTER_CHANGED")
        if frame.previous_graph is not None:
            frame.previous_graph.checked()
        if frame.name == "dependency-stage":
            require(frame.previous is sequence.record[1] and frame.previous_pin ==
                    (frame.previous.raw, frame.previous.checked_ns, sequence.originals.initializer_checked_local),
                    "BOOTSTRAP_STAGING_INITIALIZER_RETURN_CHANGED")
        elif frame.name == "empty-seed":
            require(type(frame.previous) is _StagingPhaseReturn and frame.previous_pin ==
                    (frame.previous.raw, frame.previous.checked_ns, frame.previous.checked_local) and
                    sequence.phases[0].result is frame.previous, "BOOTSTRAP_STAGING_STAGE_RETURN_CHANGED")
        else:
            require(frame.name == "custody-prepare" and len(sequence.phases) == 3 and sequence.phases[2] is self and
                    type(frame.previous) is StagingPrefix and frame.previous_pin ==
                    (frame.previous.raw, frame.previous.checked_ns, frame.previous.checked_local) and
                    sequence.phases[1].result is frame.previous and len(frame.closed_frames) == 2 and
                    all(parent is sequence.phases[index] and _staging_frame(parent) is old and
                        old.state == "COMPLETE" and parent.state == "COMPLETE" and parent.result is old.result
                        for index, (parent, old) in enumerate(frame.closed_frames)),
                    "BOOTSTRAP_CUSTODY_SEED_PARENT_RETURN_CHANGED")
            require(type(frame.staged) is custody.StagedEvidence and custody._capture_staged(frame.staged) == frame.staged_pin and
                    frame.staged.stage_leaf is frame.previous.stage_leaf and frame.staged.seed_leaf is frame.previous.seed_leaf,
                    "BOOTSTRAP_CUSTODY_STAGED_RETURN_CHANGED")
        if frame.name != "custody-prepare":
            require(not frame.closed_frames and frame.staged is None and frame.staged_pin is None and frame.request_pin is None,
                    "BOOTSTRAP_STAGING_UNEXPECTED_CUSTODY_INPUT")
        if frame.phase_start is not None:
            require(staging._capture_phase(frame.phase_start) == frame.phase_pin and
                    type(frame.window) is _StagingWindow and frame.window.call is self, "BOOTSTRAP_STAGING_PHASE_CHANGED")
        if frame.leaf is not None:
            require(_staging_leaf_capture(frame.name, frame.leaf) == frame.leaf_pin, "BOOTSTRAP_STAGING_LEAF_RETURN_CHANGED")
        if frame.owner is not None:
            _staging_actual_owner(frame)
        require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                "BOOTSTRAP_STAGING_PRIOR_UNKNOWN")
        return frame

    def live(self):
        frame = self.check()
        require(frame.state == "RUNNING" and frame.owner is not None and frame.owner.closed is False and
                frame.original is None and frame.owner.original is None and not frame.unknown and not frame.owner.unknown,
                "BOOTSTRAP_STAGING_NOT_LIVE")
        return frame.owner

    def cancel(self):
        frame = self.check()
        cancellation(frame.published[3])
        for callback in _staging_sequence_frame(frame.sequence).callbacks:
            callback()
            self.check()
        cancellation(frame.published[3])

    def original_transition(self):
        frame = self.check()
        return _staging_sequence_frame(frame.sequence).record[0].transition

    def directory(self, key, path, identity=None, *, parent=None, create=False):
        owner = self.live()
        frame = _staging_frame(self)
        existing = next((row for row in frame.handles if row[0] == key), None)
        if existing is None:
            directory = owner.open(path) if parent is None else owner.child(parent, path.name, create=create)
            actual = tuple(directory_identity(list(directory.identity), frame.limits.clock[0]))
            _update_staging_frame(self, handles=(*_staging_frame(self).handles, (key, directory, path, actual)))
            self.handles[key] = directory
            existing = (key, directory, path, actual)
        require(existing[2] == path and (identity is None or existing[3] == tuple(identity)),
                "BOOTSTRAP_STAGING_DIRECTORY_BINDING_CHANGED")
        _new_entry_owned(owner, existing[1], path, existing[3])
        self.check()
        return existing[1]

    def host(self):
        owner = self.live()
        owner.end()
        sequence = _staging_sequence_frame(self.sequence)
        initializer = sequence.record[0]
        entry = initializer.transition._attempt.transition._entry
        context = origin.parse(entry.context_original)
        require(origin.wire.TOKEN_ENV not in os.environ and os.environ.get(PREPARE_OUTCOME_ENV) == "success" and
                os.environ.get(PREPARE_HASH_ENV) == origin.digest(entry.handoff_original),
                "BOOTSTRAP_STAGING_PREPARE_OUTCOME_OR_TOKEN")
        selection, path, event = host_inputs(sequence.originals.clock.role)
        require(path == sequence.paths[0] and selection == context["selection"] and event == entry.admitted.original_event and
                context["runnerName"] == os.environ.get("RUNNER_NAME") and
                context["inheritedContext"] == query._inherited_context() and
                os.getpid() != origin.parse(entry.preparation_original)["processIdentity"]["pid"],
                "BOOTSTRAP_STAGING_ACTUAL_HOST_CHANGED")
        inputs = _parent_originals(initializer)[4][5][0]
        # New metadata observations under this phase, not calls on old owners.
        require(initialization._installed() == inputs.toolchains.originals and
                canonical._interpreter() == inputs.interpreter and inputs.policy == initialization.properties(inputs.homes),
                "BOOTSTRAP_STAGING_INSTALLED_INPUTS_CHANGED")
        environment = recipient_environment(sequence.paths[3])
        environment.update({name: home for name, _supplied, home, _identities in inputs.toolchains.originals})
        require(tuple(sorted(environment.items())) == inputs.environment and canonical.init_request(
            state=str(sequence.paths[3] / "state"), expected_commit=origin.parse(entry.admitted.record)["source"]["commit"],
            role=sequence.originals.clock.role) == inputs.request_raw, "BOOTSTRAP_STAGING_REQUEST_CHANGED")
        owner.end()

    def read_originals(self):
        owner = self.live()
        self.host()
        sequence = _staging_sequence_frame(self.sequence)
        previous, old = self.original_transition()._attempt, self.original_transition()._attempt.transition
        entry, paths = old._entry, sequence.paths
        value = origin.parse(entry.raw)
        for name, path, identity in (("original", paths[0], value["preparation"]["sessionIdentity"]),
                ("adoption", paths[1], value["sessionIdentity"]), ("entry", paths[2], previous.target_identity)):
            self.directory(name, path, identity)
        adoption, current = self.handles["adoption"], self.handles["entry"]
        require(owner.read(adoption, "entry-context.json") == entry.raw and
                owner.read(adoption, "entry-close-pending.json") == old.pending_raw and
                owner.read(current, "new-entry-pending.json") == previous.pending_raw,
                "BOOTSTRAP_STAGING_ENTRY_ORIGINAL_CHANGED")
        for target, admitted, session_raw, returned_raw in (
                (adoption, entry.admitted, entry.session_original, entry.return_original),
                (current, previous.admitted, previous.admission_originals[1], previous.admission_originals[2])):
            directory = self.directory("admission:" + str(target.path), target.path / "admission", parent=target)
            require(load_admission(owner, directory) == admitted and owner.read(directory, "session-result.json") == session_raw and
                    owner.read(target, "admission-return.json") == returned_raw, "BOOTSTRAP_STAGING_ENTRY_ADMISSION_CHANGED")
        _admission_history_content(entry.admitted, entry.session_original, entry.return_original, history.snapshot(old._fence))
        _new_entry_return_content(previous)
        admitted, _context, prepared = _read_prepared(_StagingOriginalReader(self), self.handles["original"],
            entry.handoff_original, entry.context_original)
        require(admitted == entry.admitted and same_preparation(prepared, origin.parse(entry.preparation_original)) and
                same_preparation(prepared, origin.parse(previous.preparation)), "BOOTSTRAP_STAGING_PREPARATION_CHANGED")
        service = self.directory("service", paths[0] / "service", parent=self.handles["original"])
        responses = tuple((name, owner.read(service, name + ".json")) for name in ("attempt", "jobs"))
        require(responses == old.responses and origin.encoded(_entry_close_proposal(entry, responses)) == old.proposal_raw and
                old.proposal_raw == sequence.originals.proposal_raw, "BOOTSTRAP_STAGING_SERVICE_ORIGINALS_CHANGED")
        for _key, spelling, identity, name, maximum, raw in sequence.files:
            path = Path(spelling)
            directory = self.directory("predecessor:" + spelling, path, identity)
            require(owner.read(directory, name, maximum) == raw, "BOOTSTRAP_STAGING_PREDECESSOR_FILE_CHANGED")
        self.host()
        self.check()

    def remember(self, key, directory, name, raw, maximum=LIMIT):
        owner = self.live()
        frame = _staging_frame(self)
        require(type(raw) is bytes and 0 < len(raw) <= maximum and not any(row[0] == key for row in frame.files),
                "BOOTSTRAP_STAGING_RETAINED_ROSTER")
        identity = tuple(directory_identity(list(directory.identity), frame.limits.clock[0]))
        _new_entry_owned(owner, directory, directory.path, identity)
        _update_staging_frame(self, files=(*frame.files, (key, directory, directory.path, identity, name, maximum, raw)))
        self.records[key] = raw
        self.check()

    def reread(self):
        owner = self.live()
        for _key, directory, path, identity, name, maximum, raw in _staging_frame(self).files:
            _new_entry_owned(owner, directory, path, identity)
            require(owner.read(directory, name, maximum) == raw, "BOOTSTRAP_STAGING_RETAINED_BYTES_CHANGED")
        self.check()
        if _staging_frame(self).name == "custody-prepare":
            self.read_custody_request()

    def read_custody_request(self):
        """Reopen the ACTUAL reservation, not only request-original.json."""
        frame = self.check()
        owner, pin = self.live(), frame.request_pin
        reader = _custody_request_reader(self)
        opened = []
        try:
            directory = owner.acquire("bootstrap-leaf-custody-directory", lambda: staging.files.private_root(pin.path))
            opened.append(directory)
            end = owner.end()
            retained = owner.acquire("bootstrap-leaf-custody-retained",
                lambda: directory.open_directory("retained", deadline=end))
            opened.append(retained)
            require(str(directory.path) == pin.path and tuple(directory.verify().identity) == pin.directory and
                    tuple(retained.verify().identity) == pin.retained, "BOOTSTRAP_CUSTODY_REQUEST_DIRECTORY_CHANGED")
            staging._read(reader, directory, "request.json", expected=frame.leaf_pin[1],
                          binding=staging.files.record(pin.binding_raw))
            staging._names(reader, directory, ("request.json", "retained"))
            staging._names(reader, retained, ())
            require(tuple(directory.verify().identity) == pin.directory and
                    tuple(retained.verify().identity) == pin.retained, "BOOTSTRAP_CUSTODY_REQUEST_DIRECTORY_CHANGED")
            reader.check()
        except BaseException as error:
            self.error("custody-request-readback", error)
            raise _staging_frame(self).original
        finally:
            for resource in reversed(opened):
                if owner.unknown:
                    break
                try:
                    reader.close_one(resource)
                except BaseException as error:
                    self.error("custody-request-readback-close", error)
        if _staging_frame(self).original is not None:
            raise _staging_frame(self).original
        self.check()

    def admit(self):
        """Both immutable query deadlines AND actual finalizer return fit SOFT."""
        owner = self.live()
        frame = _staging_frame(self)
        window, limits = frame.window, frame.limits
        require(frame.query_attempted is False, "BOOTSTRAP_STAGING_QUERY_ALREADY_CLAIMED")
        _update_staging_frame(self, query_attempted=True)
        path = self.handles["phase"].path / "admission"
        began = window.now()
        work = min(limits.soft, origin.integer(began + 75 * origin.NS))
        final = min(limits.soft, origin.integer(began + 120 * origin.NS))
        pair = (window.deadline(75, limit=work), window.deadline(120, limit=final))
        supplier = original = result = None
        try:
            supplier = query.NativeGitQueries(ROOT, path, check_cancel=lambda: window.now(limit=work), owner_deadlines=pair)
            _update_staging_frame(self, queries=(*_staging_frame(self).queries, (supplier, pair, work, final)))
            supplier.native_host_matches_actions()
            result = bootstrap.admit(ROOT, query_runner=supplier, expected=self.original_transition()._attempt.admitted)
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
                    original = origin.OriginError("BOOTSTRAP_STAGING_QUERY_UNKNOWN")
                self.error("staging-query", original, unknown=True)
        if original is not None:
            raise original
        window.now(limit=final)  # A provisional session record does not prove actual supplier return.
        require(type(result) is I.Admission and result == self.original_transition()._attempt.admitted,
                "BOOTSTRAP_STAGING_READMISSION")
        retained = self.directory("admission", path)
        require(load_admission(owner, retained) == result, "BOOTSTRAP_STAGING_READMISSION_CHANGED")
        for name, raw in (("admission.json", result.record), ("original-event.json", result.original_event),
                ("original-policy.json", result.original_policy), ("recipient-public.asc", result.public_key),
                ("session-result.json", owner.read(retained, "session-result.json"))):
            self.remember("admission/" + name, retained, name, raw)
        session_raw = self.records["admission/session-result.json"]
        session = origin.parse(session_raw)
        require(set(session) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"} and
                type(session["schema"]) is int and session["schema"] == 1 and session["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
                type(session["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", session["job"]) and
                type(session["queries"]) is list and type(session["readbacks"]) is list and
                session["result"] == "READY_FOR_CALLER_SEAL" and session["retirement"] == "KNOWN" and
                session["firstError"] is None and session["errors"] == [], "BOOTSTRAP_STAGING_QUERY_RETURN")
        target = self.handles["phase"]
        raw = owner.write(target, "admission-return.json", {"admissionSha256": origin.digest(result.record),
            "sessionSha256": origin.digest(session_raw), "clock": origin.clock_value(window.clock),
            "returnedNs": window.now(limit=final), "ownerDeadlineScope": "ORIGINAL_PHASE_SOFT_ONLY"})
        self.remember("admission-return", target, "admission-return.json", raw)
        window.now(limit=final)


def _close_staging_phase(parent):
    """Original file-only close/handlers; no new failure writer or owner."""
    frame = _staging_frame(parent)
    owner, window = frame.owner, frame.window
    if owner is not None:
        bound = False
        _update_staging_frame(parent, state="CLOSING")
        parent.state = "CLOSING"
        try:
            parent.roster()
            actual = _staging_frame(parent)
            require(actual.close_roster is None and owner.closed is False, "BOOTSTRAP_STAGING_CLOSE_REENTRY")
            _update_staging_frame(parent, close_roster=tuple(pin[:3] for pin in actual.resources))
            _staging_actual_owner(actual)
            bound = True
        except BaseException as error:
            parent.error("staging-close-binding", error, unknown=True)
        if bound:
            try:
                owner.close()
            except BaseException as error:
                parent.error("staging-close", error)
        if owner.original is not None:
            parent.error("staging-owner-return", owner.original)
    for number, handler in _staging_frame(parent).handlers:
        try:
            signal.signal(number, handler)
            require(signal.getsignal(number) == handler, "BOOTSTRAP_STAGING_HANDLER_NOT_RESTORED")
            actual = _staging_frame(parent)
            _update_staging_frame(parent, restored=(*actual.restored, (number, handler)))
        except BaseException as error:
            parent.error("staging-handler-restore", error)
    try:
        parent.roster()
        actual = _staging_frame(parent)
        require(owner is None or (owner.closed is True and actual.close_roster is not None and
                all(pin[3] and pin[4] for pin in actual.resources)), "BOOTSTRAP_STAGING_CLOSE_INCOMPLETE")
    except BaseException as error:
        parent.error("staging-close-roster", error, unknown=True)


def _run_staging_phase(sequence, previous, name):
    saved = _staging_sequence_checked(sequence)
    require(type(name) is str and name in saved.plan and saved.state == "RUNNING", "BOOTSTRAP_STAGING_PHASE")
    staged, closed_frames = None, ()
    if name == "dependency-stage":
        require(not saved.phases and previous is saved.record[1], "BOOTSTRAP_STAGING_PHASE_ORDER")
        pin = (previous.raw, previous.checked_ns, saved.originals.initializer_checked_local)
        previous_graph = None
    elif name == "empty-seed":
        require(len(saved.phases) == 1 and type(previous) is _StagingPhaseReturn and
                saved.phases[0].state == "COMPLETE" and saved.phases[0].result is previous,
                "BOOTSTRAP_STAGING_PHASE_ORDER")
        pin = (previous.raw, previous.checked_ns, previous.checked_local)
        previous_graph = _StagingClosedGraph.capture(saved.phases[0], _staging_frame(saved.phases[0]), previous)
    else:
        require(name == "custody-prepare" and len(saved.phases) == 2 and type(previous) is StagingPrefix,
                "BOOTSTRAP_CUSTODY_PHASE_ORDER")
        closed_frames = tuple((parent, _staging_frame(parent)) for parent in saved.phases)
        stage_parent, seed_parent = (pair[1] for pair in closed_frames)
        require(all(parent.state == "COMPLETE" and old.state == "COMPLETE" and parent.result is old.result
                    for parent, old in closed_frames) and seed_parent.result is previous and
                type(stage_parent.result) is _StagingPhaseReturn and previous.stage_leaf is stage_parent.leaf and
                previous.seed_leaf is seed_parent.leaf and previous.stage_raw == stage_parent.result.raw and
                previous.checked_ns == seed_parent.last and previous.checked_local == seed_parent.local_last,
                "BOOTSTRAP_CUSTODY_NOT_ORIGINAL_SEED_RETURN")
        pin = (previous.raw, previous.checked_ns, previous.checked_local)
        staged = custody.StagedEvidence(previous.raw, previous.stage_raw, previous.stage_leaf,
                                       previous.seed_leaf, previous.checked_ns, previous.checked_local)
        # The coordinator legitimately advances; NEVER freeze its whole dict.
        # Pin BOTH closed private frames and the fully traversed typed prefix.
        previous_graph = _StagingClosedGraph.capture(*saved.phases, stage_parent, seed_parent, previous, staged)
    parent = _StagingPhaseParent(sequence, name, previous)
    _register_staging_phase(parent, pin, previous_graph, closed_frames=closed_frames, staged=staged)
    # Registration consumes the phase before all clocks/suppliers.
    owner = window = None
    try:
        parent.check()
        local = staging._local(time.monotonic())
        first = origin.clocks.validate_reading(origin.clocks.observe())
        require(staging._clock(first.clock) == staging._clock(saved.originals.clock) and
                first.nanoseconds >= pin[1] and local >= pin[2], "BOOTSTRAP_STAGING_PREDECESSOR_CLOCK")
        proposal = allocation.validate_proposal(saved.originals.proposal_raw, saved.originals.admitted,
            saved.originals.responses, saved.originals.invocation, saved.originals.clock, saved.originals.runner_name)
        hard = min(origin.integer(first.nanoseconds + 120 * origin.NS), proposal["phaseFencesNs"][name],
                   proposal["proposedJobEndNs"])
        seconds = 90 if name == "empty-seed" else 120
        soft = min(hard, origin.integer(first.nanoseconds + seconds * origin.NS))
        require(first.nanoseconds < soft, "BOOTSTRAP_STAGING_NO_PHASE_INTERVAL")
        limits = _StagingLimits(staging._clock(first.clock), first.nanoseconds, soft, hard, local,
            origin.wire._directed_deadline(local, seconds, soft, first.nanoseconds),
            origin.wire._directed_deadline(local, 120, hard, first.nanoseconds))
        phase = staging.PhaseStart(first, local)
        window, callback = _StagingWindow(parent), parent.cancel
        _update_staging_frame(parent, first=first, phase_start=phase, phase_pin=staging._capture_phase(phase),
            limits=limits, window=window, callback=callback, last=first.nanoseconds, local_last=local)
        parent.first, parent.phase_start, parent.window, parent.callback = first, phase, window, callback
        parent.check()
        owner = _StagingFileOwner(limits.local_hard, window, first=first, cancelled=callback)
        _update_staging_frame(parent, owner=owner, owner_bindings=(owner.resources, owner.errors, owner.admissions, owner.local_end),
                              state="RUNNING")
        parent.owner, parent.state = owner, "RUNNING"
        owner.end()
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handler = signal.getsignal(number)
            actual = _staging_frame(parent)
            _update_staging_frame(parent, handlers=(*actual.handlers, (number, handler)))
            parent.handlers[number] = handler  # Original pair retained BEFORE a fallible install.
            signal.signal(number, lambda signum, _frame: _staging_frame(parent).published[3].append(signum))
            owner.end()
        parent.read_originals()
        initial = parent.directory("initializer", saved.paths[3], saved.originals.directories["session"])
        target = parent.directory("phase", saved.paths[3] / (name + "-parent"), parent=initial, create=True)
        parent.admit()
        parent.read_originals()
        if name == "dependency-stage":
            leaf = staging.stage_empty(owner, saved.originals, phase)
        elif name == "empty-seed":
            leaf = staging.observe_empty_seed(owner, saved.originals, phase, previous.leaf)
        else:
            leaf = custody.reserve_configuration(owner, saved.originals, phase, _staging_frame(parent).staged)
        _update_staging_frame(parent, leaf=leaf, leaf_pin=_staging_leaf_capture(name, leaf))
        parent.leaf = leaf
        if name == "custody-prepare":
            _update_staging_frame(parent, request_pin=_capture_custody_request(_staging_frame(parent)))
        parent.check()
        # The actual leaf return is not the later parent return/closed graph.
        require(leaf.local_started == local and leaf.checked_ns >= first.nanoseconds and leaf.checked_local >= local,
                "BOOTSTRAP_STAGING_LEAF_RETURN_CLOCK")
        window.now(minimum=leaf.checked_ns)
        require(window.local_last >= leaf.checked_local, "BOOTSTRAP_STAGING_LEAF_LOCAL_RETURN")
        if name == "custody-prepare":
            parent.read_custody_request()
        parent.remember("leaf-evidence", target, "leaf-evidence.json", owner.write(target, "leaf-evidence.json", leaf.raw))
        key, original = ("request-original", leaf.request_raw) if name == "custody-prepare" else ("staging-original", leaf.staging_raw)
        parent.remember(key, target, key + ".json", owner.write(target, key + ".json", original))
        parent.read_originals()
        parent.reread()
        pending_scope = ("BOOTSTRAP_CONFIGURATION_CUSTODY_PARENT_PENDING_CLOSE_V1" if name == "custody-prepare" else
                         "BOOTSTRAP_STAGING_PARENT_PENDING_CLOSE_V1")
        pending = owner.write(target, "pending.json", {"schema": 1, "scope": pending_scope,
            "phase": name, "window": window.record(), "predecessorSha256": origin.digest(pin[0]),
            "predecessorCheckedNs": pin[1], "leafSha256": origin.digest(leaf.raw), "leafCheckedNs": leaf.checked_ns,
            "originalsSha256": {key: origin.digest(raw) for key, raw in parent.records.items()},
            "parentResourceClose": "PENDING_CLOSE", "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        _update_staging_frame(parent, pending_raw=pending)
        parent.pending_raw = pending
        parent.remember("pending", target, "pending.json", pending)
        parent.read_originals()
        parent.reread()
        window.now(minimum=leaf.checked_ns)
    except BaseException as error:
        parent.error("staging-phase", error)
    finally:
        _close_staging_phase(parent)
    try:
        frame = _staging_frame(parent)
        if frame.original is not None:
            raise frame.original
        parent.check()
        require(owner is not None and owner.closed is True and owner.original is None and owner.unknown is False and
                frame.unknown is False and not frame.foreign_resources and
                frame.handlers == frame.restored and frame.leaf is not None and all(pin[3] and pin[4] for pin in frame.resources),
                "BOOTSTRAP_STAGING_PARENT_NOT_CLOSED")
        parent.cancel()
        closed = window.now(final=True, minimum=frame.leaf.checked_ns)
        scope = ("BOOTSTRAP_CONFIGURATION_CUSTODY_PARENT_CLOSED_NO_EXECUTION_V1" if name == "custody-prepare" else
                 "BOOTSTRAP_STAGING_PARENT_CLOSED_NO_EXECUTION_V1")
        raw = origin.encoded({"schema": 1, "scope": scope, "phase": name,
            "window": window.record(), "pendingSha256": origin.digest(frame.pending_raw),
            "predecessorSha256": origin.digest(pin[0]), "predecessorCheckedNs": pin[1],
            "leafSha256": origin.digest(frame.leaf.raw), "leafCheckedNs": frame.leaf.checked_ns, "closedNs": closed,
            "resourceCount": len(frame.resources), "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False})
        parent.cancel()
        checked = window.now(final=True, minimum=closed)
        parent.check()
        frame = _staging_frame(parent)
        require(frame.last == checked and frame.local_last >= frame.leaf.checked_local and owner.original is None and
                owner.unknown is False and frame.unknown is False and not frame.foreign_resources and
                frame.handlers == frame.restored and all(pin[3] and pin[4] for pin in frame.resources),
                "BOOTSTRAP_STAGING_FINAL_RETURN_CHANGED")
        if name == "dependency-stage":
            result = _StagingPhaseReturn(raw, frame.leaf, checked, frame.local_last)
        elif name == "empty-seed":
            result = StagingPrefix(raw, previous.raw, previous.leaf, frame.leaf, checked, frame.local_last)
        else:
            result = ConfigurationCustodyPrefix(raw, previous, frame.leaf, checked, frame.local_last)
        _update_staging_frame(parent, result=result, state="COMPLETE")
        parent.result, parent.state = result, "COMPLETE"
        return result
    except BaseException as error:
        parent.error("staging-parent-return", error)
        _update_staging_frame(parent, state="FAILED")
        parent.state = "FAILED"
        frame = _staging_frame(parent)
        if owner is not None and (frame.unknown or owner.unknown) and not any(item is owner for item in QUARANTINE):
            QUARANTINE.append(owner)
        # No new writer/owner, and no claim of encrypted failure delivery.
        try:
            frame.original.bootstrap_staging_parent = parent
            frame.original.bootstrap_staging_resources = tuple(pin[:3] for pin in frame.resources)
            frame.original.bootstrap_staging_unregistered_resources = tuple(pin[:3] for pin in frame.foreign_resources)
        except BaseException:
            pass  # The immutable private registry still retains originals; never replace the first failure.
        raise frame.original


def _stage_after_initialization(initializer, returned):
    sequence = _StagingSequence(initializer, returned)
    with _STAGING_CLAIM_LOCK:
        require(id(initializer) not in _STAGING_ATTEMPTS, "BOOTSTRAP_STAGING_ALREADY_CLAIMED")
        record = (initializer, returned, sequence)
        _STAGING_ATTEMPTS[id(initializer)] = record
        _claim_staging_sequence(sequence, _STAGING_ATTEMPTS, record)
    try:
        graph, originals, original_pin, files, paths, callbacks, registries = _capture_staging_initializer(initializer, returned)
        _update_staging_sequence(sequence, graph=graph, originals=originals, original_pin=original_pin,
                                 files=files, paths=paths, callbacks=callbacks, registries=registries,
                                 plan=_staging_plan(registries), state="RUNNING")
        sequence.originals, sequence.state = originals, "RUNNING"
        stage = _run_staging_phase(sequence, returned, "dependency-stage")
        # This starts only AFTER actual stage parent return, not its leaf or
        # pending JSON. No call/clock/resource on the closed stage parent.
        result = _run_staging_phase(sequence, stage, "empty-seed")
        if _staging_sequence_frame(sequence).plan == ("dependency-stage", "empty-seed", "custody-prepare"):
            # Still RUNNING, with a DISTINCT third owner. Outside both closed
            # parents' handlers: success/failure never reopens or errors them.
            result = _run_staging_phase(sequence, result, "custody-prepare")
        # The selected final parent has already observed its final RAW/LOCAL
        # boundary. Only private bookkeeping follows; stage-only is unchanged.
        _update_staging_sequence(sequence, state="COMPLETE", result=result)
        sequence.result, sequence.state = result, "COMPLETE"
        return result
    except BaseException as error:
        saved = _staging_sequence_frame(sequence)
        first = error if saved.original is None else saved.original
        _update_staging_sequence(sequence, original=first, state="FAILED")
        sequence.original, sequence.state = first, "FAILED"
        sequence.failure_custody = "INCOMPLETE" if any(_staging_frame(parent).files for parent in saved.phases) else "UNAVAILABLE"
        try:
            first.bootstrap_staging_sequence = sequence
        except BaseException:
            pass
        raise first


@dataclass(frozen=True)
class ConfigurationPrefix:
    """Closed original configuration observations, NOT transferable authority."""
    raw: bytes = field(repr=False)
    request_raw: bytes = field(repr=False)
    start_raw: bytes = field(repr=False)
    receipt_raw: bytes = field(repr=False)
    observation_raw: bytes = field(repr=False)
    checked_ns: int
    checked_local: float


# These prospective limits concern exactly TWO outer files, not the four
# canonical logs/reports, dependency bytes, a Snapshot, or a kernel disk quota.
PRODUCER_STREAM_BYTES = 64 * 1024 * 1024 + 65536
PRODUCER_OUTER_BYTES = 2 * PRODUCER_STREAM_BYTES
PRODUCER_READ_BLOCK = 65536
_ProducerPredecessor = namedtuple("_ProducerPredecessor", "sequence frame published phases graph")
_ProducerLimits = namedtuple("_ProducerLimits", "clock first local_start ends local_ends")
_ProducerPhase = namedtuple("_ProducerPhase", "name started local_started end local_end")
_ProducerResource = namedtuple("_ProducerResource", "row label value kind attempted closed")
_ProducerFile = namedtuple("_ProducerFile", "key directory path identity name maximum raw binding_raw")
_ProducerCapture = namedtuple("_ProducerCapture", "name stream identity highwater final_stamp synced verified readback")
_ProducerNative = namedtuple("_ProducerNative", "scope_attempted launch_attempted child child_kind child_pid "
    "baseline_raw preparer_raw birth_raw leader_raw launch_minimum argv exit_code completed_ns work_accepted "
    "drain_attempted survivors_raw terminal_raw retired finalized_ns", defaults=(None,) * 19)
_ProducerFrame = namedtuple("_ProducerFrame", "call transition roots operation state published reservation predecessor "
    "first limits window owner owner_bindings last local_last phases resources foreign handles files handlers restored "
    "close_roster original unknown errors descriptor environment outer_invocation native captures "
    "query_attempted query query_returned cancellation_attempted cancellation_raw cancellation_stamps "
    "result", defaults=(None,) * 38)
_ProducerResultPin = namedtuple("_ProducerResultPin", "frame result dictionary fields records graph graph_pin")


def _producer_private_controls():
    """Keep the original call and cleanup frames outside mutable publications.

    No constructor, returned prefix, copied registry or caller callback selects
    the reservation operation. Like the existing registries this is finite
    same-process binding, not protection against arbitrary Python-code changes.
    """
    roots = (_ENTRY_ATTEMPTS, _RECIPIENT_ATTEMPTS, _INITIALIZER_ATTEMPTS, _PARENT_CONTROLS, _STAGING_ATTEMPTS)
    operation, lock = _recipient_after_entry, threading.Lock()
    attempts, frames, owners, windows_by_id, results = {}, {}, {}, {}, {}
    result_attempted = set()

    def original_roots():
        require(all(actual is old for actual, old in zip(
            (_ENTRY_ATTEMPTS, _RECIPIENT_ATTEMPTS, _INITIALIZER_ATTEMPTS, _PARENT_CONTROLS, _STAGING_ATTEMPTS), roots)) and
            _recipient_after_entry is operation, "BOOTSTRAP_PRODUCER_ORIGINAL_CALL_CHANGED")

    def claim(transition):
        require(type(transition) is NewEntryTransition, "BOOTSTRAP_PRODUCER_TRANSITION_KIND")
        original_roots()
        with lock:
            require(id(transition) not in attempts, "BOOTSTRAP_PRODUCER_ALREADY_CLAIMED")
            call = _ProducerParent(transition)
            attempts[id(transition)] = (transition, call)
            frames[id(call)] = _ProducerFrame(call=call, transition=transition, roots=roots, operation=operation,
                state="CLAIMED", published=(call.handles, call.records, call.handlers, call.cancelled), phases=(),
                resources=(), foreign=(), handles=(), files=(), handlers=(), restored=(), unknown=False, errors=(),
                captures=(), native=_ProducerNative(scope_attempted=False, launch_attempted=False, work_accepted=False,
                    drain_attempted=False, retired=False), query_attempted=False, cancellation_attempted=False,
                cancellation_stamps=())
        return call

    def frame(call):
        saved = frames.get(id(call))
        require(type(saved) is _ProducerFrame and saved.call is call and
                attempts.get(id(saved.transition)) == (saved.transition, call), "BOOTSTRAP_PRODUCER_NOT_CLAIMED")
        return saved

    def update(call, **values):
        saved = frame(call)
        result_fields = result_dictionary = None
        if "result" in values:
            result = values["result"]
            require(saved.result is None and id(call) not in result_attempted, "BOOTSTRAP_PRODUCER_RESULT_REENTRY")
            result_attempted.add(id(call))  # Failed capture/publication is also consumed.
            require(type(result) is ConfigurationPrefix and values.get("state") == "COMPLETE",
                    "BOOTSTRAP_PRODUCER_RESULT_ORIGINALS")
            # Retain immutable originals at the ORIGINAL producer publication,
            # not from mutable dataclass fields first seen by a later consumer.
            result_dictionary = object.__getattribute__(result, "__dict__")
            result_fields = tuple(result_dictionary[name] for name in
                ("raw", "request_raw", "start_raw", "receipt_raw", "observation_raw", "checked_ns", "checked_local"))
            require(set(result_dictionary) == {"raw", "request_raw", "start_raw", "receipt_raw", "observation_raw",
                    "checked_ns", "checked_local"} and
                    all(type(raw) is bytes and 0 < len(raw) <= 4194304 for raw in result_fields[:5]) and
                    type(result_fields[5]) is int and type(result_fields[6]) in (int, float) and
                    math.isfinite(result_fields[6]), "BOOTSTRAP_PRODUCER_RESULT_ORIGINALS")
        if "owner" in values:
            require(saved.owner is None and type(values["owner"]) is _ProducerOwner, "BOOTSTRAP_PRODUCER_OWNER_REENTRY")
            owners[id(values["owner"])] = call
        if "window" in values:
            require(saved.window is None and type(values["window"]) is _ProducerWindow, "BOOTSTRAP_PRODUCER_WINDOW_REENTRY")
            windows_by_id[id(values["window"])] = call
        updated = saved._replace(**values)
        if result_fields is not None:
            # These original containers must be pinned BEFORE returning to the
            # enclosing call. A later first snapshot cannot recover erased query
            # rows or graph witnesses. The parent's public result/state are the
            # only remaining bookkeeping and are deliberately not captured here.
            selected = (updated.owner, updated.window, updated.result, updated.query[0],
                        *(row.stream for row in updated.captures))
            records, graph = _capture_producer_graph(updated, selected)
            graph_pin = (object.__getattribute__(graph, "__dict__"), graph.nodes, graph.paths)
            results[id(call)] = _ProducerResultPin(updated, values["result"], result_dictionary, result_fields,
                                                   records, graph, graph_pin)
        frames[id(call)] = updated
        return frames[id(call)]

    def invoke(call):
        saved = frame(call)
        original_roots()
        require(saved.state == "CLAIMED" and saved.reservation is None, "BOOTSTRAP_PRODUCER_RESERVATION_REENTRY")
        update(call, state="RESERVING")
        call.state = "RESERVING"
        # Outside the claim lock. Failure consumes both this intent and any
        # original recipient claim; a prior direct reservation cannot be adopted.
        returned = operation(saved.transition, initialize=True, stage=True, reserve=True)
        update(call, reservation=returned, state="RESERVATION_RETURNED")
        call.state = "RESERVATION_RETURNED"  # Actual return retained before validation.
        original_roots()
        return returned

    def owner_frame(owner):
        saved = frame(owners.get(id(owner)))
        require(saved.owner is owner, "BOOTSTRAP_PRODUCER_OWNER_NOT_BOUND")
        return saved

    def window_frame(window):
        saved = frame(windows_by_id.get(id(window)))
        require(type(window) is _ProducerWindow and saved.window is window and window.call is saved.call,
                "BOOTSTRAP_PRODUCER_WINDOW_NOT_BOUND")
        return saved

    def original_call(transition):
        """Passive same-process lookup, NOT a prefix/adoption or execution API."""
        require(type(transition) is NewEntryTransition, "BOOTSTRAP_PRODUCER_TRANSITION_KIND")
        original_roots()
        row = attempts.get(id(transition))
        require(type(row) is tuple and len(row) == 2 and row[0] is transition and
                type(row[1]) is _ProducerParent, "BOOTSTRAP_PRODUCER_NOT_ORIGINAL_CALL")
        saved = frame(row[1])
        require(saved.transition is transition and saved.call is row[1] and saved.roots is roots and
                saved.operation is operation, "BOOTSTRAP_PRODUCER_NOT_ORIGINAL_CALL")
        return row[1]

    def original_result(call):
        original_roots()
        saved, pin = frame(call), results.get(id(call))
        require(type(pin) is _ProducerResultPin and pin.frame is saved and pin.result is saved.result and
                type(pin.result) is ConfigurationPrefix and
                object.__getattribute__(pin.result, "__dict__") is pin.dictionary,
                "BOOTSTRAP_PRODUCER_RESULT_NOT_ORIGINAL")
        names = ("raw", "request_raw", "start_raw", "receipt_raw", "observation_raw", "checked_ns", "checked_local")
        require(set(pin.dictionary) == set(names) and all(type(pin.dictionary[name]) is type(old) and
                pin.dictionary[name] == old for name, old in zip(names, pin.fields)),
                "BOOTSTRAP_PRODUCER_RESULT_ORIGINALS_CHANGED")
        _check_producer_result_graph(pin)
        return pin

    return claim, frame, update, invoke, original_roots, owner_frame, window_frame, original_call, original_result


(_claim_producer, _producer_frame, _update_producer, _invoke_producer_reservation, _producer_original_roots,
 _producer_owner_frame, _producer_window_frame, _producer_original_call, _producer_original_result) = _producer_private_controls()
del _producer_private_controls


def _producer_closed_phase(parent, frame):
    """Passive exact closed-frame validation; NEVER call its owner/window."""
    require(type(parent) is _StagingPhaseParent and _staging_frame(parent) is frame and frame.call is parent and
            frame.state == parent.state == "COMPLETE" and parent.result is frame.result and
            frame.original is None and parent.original is None and frame.unknown is False and parent.unknown is False and
            not frame.foreign_resources and frame.handlers == frame.restored and frame.close_roster is not None and
            parent.owner is frame.owner and parent.window is frame.window and
            type(frame.owner) is _StagingFileOwner and frame.owner.closed is True and frame.owner.original is None and
            frame.owner.unknown is False and frame.owner.errors == [] and frame.owner.resources is frame.owner_bindings[0] and
            frame.owner.errors is frame.owner_bindings[1] and frame.owner.admissions is frame.owner_bindings[2] and
            frame.owner.local_end == frame.owner_bindings[3] and frame.owner.fence is frame.window and
            frame.owner.first is frame.first and frame.owner.cancelled is frame.callback and
            frame.last == frame.result.checked_ns and frame.local_last == frame.result.checked_local and
            type(frame.last) is int and type(frame.local_last) in (int, float) and math.isfinite(frame.local_last),
            "BOOTSTRAP_PRODUCER_PREDECESSOR_NOT_CLOSED")
    require(len(frame.resources) == len(frame.owner.resources) == len(frame.close_roster),
            "BOOTSTRAP_PRODUCER_PREDECESSOR_ROSTER")
    for row, pin, closed in zip(frame.owner.resources, frame.resources, frame.close_roster):
        require(type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                row is pin[0] is closed[0] and row["label"] == pin[1] == closed[1] and
                row["owner"] is pin[2] is closed[2] and row["attempted"] is row["closed"] is True and
                pin[3] is pin[4] is True, "BOOTSTRAP_PRODUCER_PREDECESSOR_ROSTER")


def _capture_producer_predecessor(call):
    saved = _producer_frame(call)
    _producer_original_roots()
    require(saved.state == "RESERVATION_RETURNED" and type(saved.reservation) is ConfigurationCustodyPrefix,
            "BOOTSTRAP_PRODUCER_NOT_ORIGINAL_RESERVATION")
    recipient = saved.roots[1].get(id(saved.transition))
    require(type(recipient) is tuple and len(recipient) == 7 and recipient[0] is saved.transition and
            type(recipient[1]) is _RecipientParent and all(flag is True for flag in recipient[4:]),
            "BOOTSTRAP_PRODUCER_RECIPIENT_INTENT")
    recipient_frame = _parent_originals(recipient[1])
    require(recipient_frame[2] is saved.roots[1] and recipient_frame[4] is recipient,
            "BOOTSTRAP_PRODUCER_RECIPIENT_ORIGINAL")
    registered = saved.roots[2].get(id(recipient[1]))
    require(type(registered) is tuple and len(registered) == 6 and registered[0] is saved.transition and
            type(registered[1]) is _InitializerParent and _parent_originals(registered[1])[4] is registered and
            registered[1].state == "COMPLETE", "BOOTSTRAP_PRODUCER_INITIALIZER_ORIGINAL")
    row = saved.roots[4].get(id(registered[1]))
    require(type(row) is tuple and len(row) == 3 and row[0] is registered[1] and row[1] is registered[1].result and
            type(row[1]) is InitializationPrefix and type(row[2]) is _StagingSequence,
            "BOOTSTRAP_PRODUCER_SEQUENCE_ORIGINAL")
    sequence = row[2]
    frame = _staging_sequence_checked(sequence)
    require(frame.record is row and frame.state == "COMPLETE" and frame.original is None and
            frame.result is saved.reservation and frame.plan == ("dependency-stage", "empty-seed", "custody-prepare") and
            len(frame.phases) == 3, "BOOTSTRAP_PRODUCER_SEQUENCE_NOT_COMPLETE")
    phases = tuple((parent, _staging_frame(parent)) for parent in frame.phases)
    for parent, old in phases:
        _producer_closed_phase(parent, old)
    last = phases[-1][1]
    require(last.result is saved.reservation and last.leaf is saved.reservation.custody_leaf and
            saved.reservation.staged is phases[1][1].result and
            saved.reservation.checked_ns == last.last and saved.reservation.checked_local == last.local_last and
            type(last.request_pin) is _CustodyRequestPin, "BOOTSTRAP_PRODUCER_FINAL_RESERVATION_RETURN")
    graph = _StagingClosedGraph.capture(*frame.phases, *(old for _parent, old in phases), saved.reservation)
    result = _ProducerPredecessor(sequence, frame, (sequence.__dict__, tuple(sequence.__dict__.items())), phases, graph)
    _update_producer(call, predecessor=result, state="RESERVED")
    call.state = "RESERVED"
    _producer_predecessor_checked(call)


def _producer_predecessor_checked(call):
    saved = _producer_frame(call)
    _producer_original_roots()
    pin = saved.predecessor
    require(type(pin) is _ProducerPredecessor and _staging_sequence_checked(pin.sequence) is pin.frame and
            pin.sequence.__dict__ is pin.published[0] and tuple(pin.sequence.__dict__.items()) == pin.published[1] and
            pin.frame.result is saved.reservation,
            "BOOTSTRAP_PRODUCER_SEQUENCE_CHANGED")
    for parent, old in pin.phases:
        _producer_closed_phase(parent, old)
    pin.graph.checked()
    return pin.frame


def _producer_set_state(call, state):
    _update_producer(call, state=state)
    call.state = state


def _producer_native(call, **values):
    frame = _producer_frame(call)
    _update_producer(call, native=frame.native._replace(**values))


@dataclass(frozen=True)
class _ProducerWindow:
    """First600/825/870/900 caps, shortened by each actual phase and LOCAL.

    RETURN is cleanup only; it can never make late WORK successful. A failed
    start is consumed before clocks, with zero discretionary time on failure.
    No synchronous supplier is claimed preemptible or a measured job budget.
    """
    call: object = field(repr=False, compare=False)

    @property
    def clock(self):
        return origin.clocks.ClockIdentity(*_producer_window_frame(self).limits.clock)

    def _raw_local(self, *, strict, minimum=0):
        frame = _producer_window_frame(self)
        call = frame.call
        call.check() if strict else call.cleanup_bindings()
        local = staging._local(time.monotonic())
        require(local >= _producer_frame(call).local_last, "BOOTSTRAP_PRODUCER_LOCAL_BACKWARDS")
        # Keep each actual returned sample with the ORIGINAL call before a
        # publication recheck. A supplier may replace window.call; it cannot
        # erase this high-water, update another claim, or select its methods.
        _update_producer(call, local_last=local)
        _producer_window_frame(self)
        observed = origin.clocks.checked_now(origin.clocks.ClockIdentity(*frame.limits.clock),
            minimum_ns=max(_producer_frame(call).last, origin.integer(minimum)))
        require(observed >= _producer_frame(call).last, "BOOTSTRAP_PRODUCER_RAW_BACKWARDS")
        _update_producer(call, last=observed)
        _producer_window_frame(self)
        after = staging._local(time.monotonic())
        require(after >= _producer_frame(call).local_last, "BOOTSTRAP_PRODUCER_LOCAL_BACKWARDS")
        _update_producer(call, local_last=after)
        _producer_window_frame(self)
        call.check() if strict else call.cleanup_bindings()
        return observed, after

    def sample(self, *, cleanup=False, minimum=0, limit=None):
        require(type(cleanup) is bool, "BOOTSTRAP_PRODUCER_CLOCK_MODE")
        frame = _producer_window_frame(self)
        require(frame.state not in ("COMPLETE", "FAILED") and frame.phases and
                (cleanup or frame.phases[-1].name in ("WORK", "READ")), "BOOTSTRAP_PRODUCER_PHASE_NOT_LIVE")
        observed, local = self._raw_local(strict=not cleanup, minimum=minimum)
        phase = _producer_window_frame(self).phases[-1]
        end = phase.end if limit is None else min(phase.end, origin.integer(limit))
        require(observed < end and local < phase.local_end, "BOOTSTRAP_PRODUCER_PHASE_EXPIRED")
        return observed

    def now(self, *, final=False, minimum=0, limit=None):
        observed = self.sample(cleanup=final, minimum=minimum, limit=limit)
        if not final:
            _producer_window_frame(self).call.cancel()
            observed = self.sample(minimum=observed, limit=limit)
        return observed

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(final) is bool and final is False and type(maximum) in (int, float) and
                0 < maximum <= 900 and math.isfinite(maximum), "BOOTSTRAP_PRODUCER_ACQUISITION_MODE")
        frame = _producer_window_frame(self)
        call = frame.call
        call.live()
        local = staging._local(time.monotonic())
        require(local >= _producer_frame(call).local_last, "BOOTSTRAP_PRODUCER_LOCAL_BACKWARDS")
        _update_producer(call, local_last=local)
        _producer_window_frame(self)
        observed = self.now(limit=limit)
        phase = _producer_window_frame(self).phases[-1]
        end = phase.end if limit is None else min(phase.end, origin.integer(limit))
        return min(phase.local_end, origin.wire._directed_deadline(local, maximum, end, observed))

    def cleanup_deadline(self, maximum):
        require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 225,
                "BOOTSTRAP_PRODUCER_CLEANUP_MAXIMUM")
        frame = _producer_window_frame(self)
        require(frame.phases[-1].name in ("RETURN", "FINAL"), "BOOTSTRAP_PRODUCER_CLEANUP_PHASE")
        call = frame.call
        local = staging._local(time.monotonic())
        require(local >= _producer_frame(call).local_last, "BOOTSTRAP_PRODUCER_LOCAL_BACKWARDS")
        _update_producer(call, local_last=local)
        _producer_window_frame(self)
        observed = self.sample(cleanup=True)
        phase = _producer_window_frame(self).phases[-1]
        return min(phase.local_end, origin.wire._directed_deadline(local, maximum, phase.end, observed))

    def advance(self, name):
        frame = _producer_window_frame(self)
        call = frame.call
        require(type(name) is str and 0 < len(frame.phases) < 4 and
                name == ("WORK", "RETURN", "FINAL", "READ")[len(frame.phases)], "BOOTSTRAP_PRODUCER_PHASE_REENTRY")
        previous = frame.phases[-1]
        # Immutable sentinel is installed BEFORE any phase-start supplier.
        _update_producer(call, phases=(*frame.phases, _ProducerPhase(name, None, None, 0, 0.0)))
        local = observed = None
        try:
            # An unavailable/failed start cannot acquire discretionary time by
            # advancing again with a repaired clock. Known cleanup still runs
            # with zero grace; ordinary WORK failure after a VALID phase start
            # does not lose the separately established native cleanup cap.
            require(previous.started is not None and previous.local_started is not None and
                    previous.end > 0 and previous.local_end > 0, "BOOTSTRAP_PRODUCER_PRIOR_START_FAILED")
            if name == "READ":
                call.live()
                call.writers_closed()
            observed, local = self._raw_local(strict=name == "READ")
            current = _producer_window_frame(self)
            index, seconds = len(current.phases) - 1, {"RETURN": 225, "FINAL": 45, "READ": 30}[name]
            end = min(current.limits.ends[index], origin.integer(observed + seconds * origin.NS))
            local_end = min(current.limits.local_ends[index],
                origin.wire._directed_deadline(local, seconds, end, observed))
            if name == "READ":
                # The previous FINAL cap is pinned separately from the new
                # consumed READ slot. Its first observation must precede it.
                require(observed < previous.end and local < previous.local_end, "BOOTSTRAP_PRODUCER_READ_START_EXPIRED")
            _update_producer(call, phases=(*current.phases[:-1], _ProducerPhase(name, observed, local, end, local_end)))
            self.sample(cleanup=name != "READ")
        except BaseException as error:
            # Preserve valid returned samples, but never leave a reusable or
            # apparently live failed phase. Its next stage is cleanup only.
            current = _producer_frame(call)
            _update_producer(call, phases=(*current.phases[:-1], _ProducerPhase(name, observed, local, 0, 0.0)))
            call.error("producer-" + name.lower() + "-start", error)
            raise

    def record(self):
        frame = _producer_window_frame(self)
        return {"clock": origin.clock_value(self.clock), "firstNs": frame.limits.first,
            "globalEndsNs": dict(zip(("WORK", "RETURN", "FINAL", "READ"), frame.limits.ends)),
            "phases": [{"phase": phase.name, "startedNs": phase.started, "endNs": phase.end} for phase in frame.phases],
            "budgetAcceptance": "NOT_ADMITTED"}


class _ProducerOwner(Owner):
    """New producer ledger. No general RETURN/FINAL acquisition escape hatch."""
    def error(self, stage, error, *, unknown=False):
        _producer_owner_frame(self).call.error(stage, error, unknown=unknown)

    def end(self, *, final=False):
        require(final is False, "BOOTSTRAP_PRODUCER_NO_FINAL_ACQUISITION")
        frame = _producer_owner_frame(self)
        frame.call.live()
        return frame.window.deadline(45)

    def _retain(self, label, value):
        frame = _producer_owner_frame(self)
        require(not any(pin.value is value for pin in frame.resources), "BOOTSTRAP_PRODUCER_DUPLICATE_RESOURCE")
        row = {"label": label, "owner": value, "attempted": False, "closed": False}
        pin = _ProducerResource(row, label, value, type(value), False, False)
        _update_producer(frame.call, resources=(*frame.resources, pin))
        # The private original survives a changed public list or failed append.
        frame.owner_bindings[0].append(row)
        return value

    def acquire(self, label, factory, *, final=False):
        require(final is False and type(label) is str and label in (
            "directory", "reader", "writer", "stdout", "stderr", "native-scope", "source-directory"),
            "BOOTSTRAP_PRODUCER_RESOURCE_LABEL")
        frame = _producer_owner_frame(self)
        self.end()
        require(frame.close_roster is None and (frame.phases[-1].name == "WORK" or label in
            ("directory", "reader", "source-directory")), "BOOTSTRAP_PRODUCER_RESOURCE_PHASE")
        try:
            value = factory()
        except BaseException as error:
            frame.call.error(label + "-allocation", error, unknown=True)
            raise
        self._retain(label, value)
        self.end()
        return value

    def new(self, path):
        return self.acquire("directory", lambda: staging.files.private_root(path, create=True))

    def open(self, path, *, final=False):
        require(final is False, "BOOTSTRAP_PRODUCER_NO_FINAL_ACQUISITION")
        return self.acquire("directory", lambda: staging.files.private_root(path))

    def child(self, parent, name, *, create=False, final=False):
        require(type(create) is bool and final is False, "BOOTSTRAP_PRODUCER_DIRECTORY_MODE")
        frame = _producer_owner_frame(self)
        require(not create or frame.phases[-1].name == "WORK", "BOOTSTRAP_PRODUCER_READ_ONLY_PHASE")
        end = self.end()
        return self.acquire("directory", lambda: parent.create_directory(name, deadline=end) if create else
                            parent.open_directory(name, deadline=end))

    def read(self, parent, name, maximum=LIMIT, *, final=False):
        require(final is False, "BOOTSTRAP_PRODUCER_NO_FINAL_ACQUISITION")
        raw, _binding = _producer_owner_frame(self).call.read_file(parent, name, maximum)
        return raw

    def write(self, parent, name, value, *, final=False):
        require(final is False, "BOOTSTRAP_PRODUCER_NO_FINAL_ACQUISITION")
        raw = value if type(value) is bytes else origin.encoded(value)
        require(0 < len(raw) <= LIMIT, "BOOTSTRAP_PRODUCER_PRIVATE_RECORD_LIMIT")
        end = self.end()
        writer = self.acquire("writer", lambda: parent.create_file(name, max_bytes=len(raw), deadline=end))
        frame = _producer_owner_frame(self)
        try:
            offset = 0
            while offset < len(raw):
                self.end()
                part = raw[offset:offset + PRODUCER_READ_BLOCK]
                count = writer.write(part)
                require(type(count) is int and 0 < count <= len(part), "BOOTSTRAP_PRODUCER_SHORT_WRITE")
                offset += count
                self.end()
            writer.sync()
            require(writer.verify().size == len(raw), "BOOTSTRAP_PRODUCER_PRIVATE_WRITE_CHANGED")
            self.end()
        except BaseException as error:
            frame.call.error("producer-write", error)
        finally:
            self.close_one(writer)
        frame.call.raise_first()
        require(self.read(parent, name) == raw, "BOOTSTRAP_PRODUCER_PRIVATE_READBACK")
        return raw

    def close_one(self, value):
        frame = _producer_owner_frame(self)
        pin = next((pin for pin in frame.resources if pin.value is value), None)
        if pin is None:
            frame.call.error("producer-close-foreign", origin.OriginError("BOOTSTRAP_PRODUCER_FOREIGN_RESOURCE"), unknown=True)
            return
        if pin.attempted:
            return
        try:
            frame.call.cleanup_bindings()
            require(type(value) is pin.kind and not frame.unknown, "BOOTSTRAP_PRODUCER_CLOSE_UNKNOWN")
        except BaseException as error:
            frame.call.error("producer-close-binding", error, unknown=True)
            return
        self.close_fence()
        frame.call.close_resource(pin)
        self.close_fence()

    def close_fence(self):
        frame = _producer_owner_frame(self)
        try:
            frame.window.sample(cleanup=True)
        except BaseException as error:
            frame.call.error("producer-close-fence", error)

    def close(self):
        frame = _producer_owner_frame(self)
        if self.closed:
            return
        self.closed = True
        self.close_fence()
        for pin in reversed(frame.resources):
            if _producer_frame(frame.call).unknown:
                break
            self.close_one(pin.value)
        self.close_fence()
        if _producer_frame(frame.call).unknown:
            if not any(value is self for value in QUARANTINE):
                QUARANTINE.append(self)
            raise origin.OriginError("BOOTSTRAP_PRODUCER_RETIREMENT_UNKNOWN")


@dataclass(frozen=True)
class _ProducerOriginalReader:
    call: object = field(repr=False, compare=False)
    owner: object = field(init=False, repr=False, compare=False)
    current: object = field(init=False, repr=False, compare=False)
    past: object = field(init=False, repr=False)
    first: object = field(init=False, repr=False)

    def __post_init__(self):
        call = self.call
        require(type(call) is _ProducerParent, "BOOTSTRAP_PRODUCER_READER_CHANGED")
        frame = call.check()
        old = frame.transition._attempt.transition
        for name, value in (("owner", call.live()), ("current", frame.window),
                ("past", history.snapshot(old._fence)), ("first", old._limits[8])):
            object.__setattr__(self, name, value)

    def checked(self):
        call, owner, current = self.call, self.owner, self.current
        require(type(call) is _ProducerParent and type(owner) is _ProducerOwner and type(current) is _ProducerWindow,
                "BOOTSTRAP_PRODUCER_READER_CHANGED")
        # Check passive ORIGINAL window/owner identity before invoking any
        # published parent. Even a different exact registered parent is not
        # this view's target and must not have its roster/error state touched.
        frame = _producer_window_frame(current)
        require(frame.call is call and frame.owner is owner, "BOOTSTRAP_PRODUCER_READER_CHANGED")
        frame = call.check()
        old = frame.transition._attempt.transition
        require(self.call is call and self.owner is owner and self.current is current and call.live() is owner and
                current is frame.window and
                self.first is old._limits[8] and history.checked(self.past) == history.snapshot(old._fence),
                "BOOTSTRAP_PRODUCER_READER_CHANGED")
        return self

    def observe(self, *, final, minimum):
        self.checked()
        return self.current.now(minimum=minimum)


def _producer_stamp(info, role):
    """Common original direct-sink/readback fields; each supplier checks mode."""
    if role == "windows-x64":
        require(type(info) is windows.FileInfo, "BOOTSTRAP_PRODUCER_FILE_INFO")
        return (tuple(info.identity), info.size, origin.encoded(info.as_dict()))
    if type(info) is query._PosixInfo:
        identity = (info.device, info.inode)
    else:
        require(type(info) is staging.files.PosixInfo, "BOOTSTRAP_PRODUCER_FILE_INFO")
        identity = tuple(info.identity)
    return (identity, info.size, info.mtime_ns, info.ctime_ns)


@dataclass(eq=False)
class _ProducerParent:
    """One source-owned configuration parent, separate from ordinary FULL.

    The constructor alone has no claim; the dormant producer owns its call.
    Closed predecessors remain closed; only the separately retained ancestor
    cancellation callbacks belong to this new call's current obligations.
    """
    transition: object = field(repr=False)
    state: str = "CLAIMED"
    owner: object = field(default=None, repr=False)
    window: object = field(default=None, repr=False)
    handles: dict = field(default_factory=dict, repr=False)
    records: dict = field(default_factory=dict, repr=False)
    handlers: dict = field(default_factory=dict, repr=False)
    cancelled: list = field(default_factory=list, repr=False)
    original: object = field(default=None, repr=False)
    unknown: bool = False
    result: object = field(default=None, repr=False)

    def error(self, stage, error, *, unknown=False):
        frame = _producer_frame(self)
        first = frame.original
        if first is None:
            first = frame.owner.original if frame.owner is not None and frame.owner.original is not None else error
        detail = diagnostics._exception_detail(error)
        uncertain = frame.unknown or unknown or detail["retirementUnknown"] or bool(
            QUARANTINE or query.QUARANTINE or diagnostics._QUARANTINE)
        errors = frame.errors
        if len(errors) < 64:
            errors = (*errors, origin.encoded({"stage": stage, "detail": detail}))
        else:
            uncertain = True
        _update_producer(self, original=first, unknown=uncertain, errors=errors)
        self.original, self.unknown = first, uncertain
        if frame.owner is not None:
            try:
                require(frame.owner.errors is frame.owner_bindings[1], "BOOTSTRAP_PRODUCER_ERRORS_CHANGED")
                Owner.error(frame.owner, stage, error, unknown=uncertain)
                uncertain |= frame.owner.unknown
            except BaseException:
                uncertain = True
            frame.owner.original, frame.owner.unknown = first, uncertain
            _update_producer(self, unknown=uncertain)
            self.unknown = uncertain

    def raise_first(self):
        frame = _producer_frame(self)
        if frame.original is not None:
            raise frame.original
        if frame.owner is not None and frame.owner.original is not None:
            self.error("producer-owner-return", frame.owner.original)
            raise _producer_frame(self).original

    def roster(self):
        frame = _producer_frame(self)
        if frame.owner is None:
            return
        original_rows = frame.owner_bindings[0]
        foreign = list(frame.foreign)
        seen = {(id(pin.row), id(pin.value)) for pin in frame.resources}
        seen.update((id(row), id(value)) for row, _label, value in foreign)
        for rows in (original_rows,) if frame.owner.resources is original_rows else (original_rows, frame.owner.resources):
            if type(rows) is list:
                for row in rows:
                    label, value = (row.get("label"), row.get("owner")) if type(row) is dict else (None, None)
                    if (id(row), id(value)) not in seen:
                        foreign.append((row, label, value))
                        seen.add((id(row), id(value)))
        _update_producer(self, foreign=tuple(foreign))
        try:
            require(not foreign and frame.owner.resources is original_rows and type(original_rows) is list and
                    len(original_rows) == len(frame.resources) <= 4096, "BOOTSTRAP_PRODUCER_ROSTER_CHANGED")
            for row, pin in zip(original_rows, frame.resources):
                require(row is pin.row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                        row["label"] == pin.label and row["owner"] is pin.value and type(pin.value) is pin.kind and
                        row["attempted"] is pin.attempted and row["closed"] is pin.closed,
                        "BOOTSTRAP_PRODUCER_ROSTER_CHANGED")
            if frame.close_roster is not None:
                require(tuple((id(pin.row), pin.label, id(pin.value)) for pin in frame.resources) == frame.close_roster,
                        "BOOTSTRAP_PRODUCER_CLOSE_ROSTER_CHANGED")
        except BaseException as error:
            self.error("producer-roster", error, unknown=True)
            raise

    def cleanup_bindings(self):
        """Actual owner/window pins only; a rejected call alias is not authority."""
        frame = _producer_frame(self)
        if frame.owner is not None:
            owner, bound = frame.owner, frame.owner_bindings
            self.roster()
            frame = _producer_frame(self)
            require(type(owner) is _ProducerOwner and owner.resources is bound[0] and owner.errors is bound[1] and
                    owner.admissions is bound[2] and type(owner.local_end) is type(bound[3]) and owner.local_end == bound[3] and
                    owner.first is frame.first and owner.fence is frame.window and owner.cancelled is bound[4] and
                    owner.work_limit is None and owner.final_limit is None and owner.early_last == frame.limits.first and
                    type(owner.closed) is bool and type(owner.unknown) is bool,
                    "BOOTSTRAP_PRODUCER_OWNER_CHANGED")
        if frame.window is not None:
            require(type(frame.window) is _ProducerWindow and frame.window.call is self and
                    _producer_window_frame(frame.window) is frame and type(frame.limits) is _ProducerLimits and
                    staging._clock(frame.first.clock) == frame.limits.clock and frame.first.nanoseconds == frame.limits.first,
                    "BOOTSTRAP_PRODUCER_WINDOW_CHANGED")
        return frame

    def check(self):
        frame = self.cleanup_bindings()
        _producer_original_roots()
        require((PRODUCER_STREAM_BYTES, PRODUCER_OUTER_BYTES, PRODUCER_READ_BLOCK) == (67174400, 134348800, 65536) and
                all(type(value) is int for value in (PRODUCER_STREAM_BYTES, PRODUCER_OUTER_BYTES, PRODUCER_READ_BLOCK)),
                "BOOTSTRAP_PRODUCER_CAPTURE_POLICY_CHANGED")
        require(type(self) is _ProducerParent and self.transition is frame.transition and self.state == frame.state and
                self.owner is frame.owner and self.window is frame.window and self.original is frame.original and
                self.unknown is frame.unknown and self.result is frame.result and self.handles is frame.published[0] and
                self.records is frame.published[1] and self.handlers is frame.published[2] and self.cancelled is frame.published[3],
                "BOOTSTRAP_PRODUCER_PARENT_CHANGED")
        require(tuple(self.handles.items()) == tuple((row[0], row[1]) for row in frame.handles) and
                tuple(self.records.items()) == tuple((row[0], row[6]) for row in frame.files) and
                tuple(self.handlers.items()) == frame.handlers, "BOOTSTRAP_PRODUCER_PUBLIC_ROSTER_CHANGED")
        if frame.predecessor is not None:
            _producer_predecessor_checked(self)
        require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE, "BOOTSTRAP_PRODUCER_PRIOR_UNKNOWN")
        return _producer_frame(self)

    def live(self):
        frame = self.check()
        self.raise_first()
        require(frame.state == "RUNNING" and frame.owner is not None and frame.owner.closed is False and
                frame.unknown is False and frame.owner.unknown is False, "BOOTSTRAP_PRODUCER_NOT_LIVE")
        return frame.owner

    def cancel(self):
        frame = self.check()
        cancellation(frame.published[3])
        for callback in frame.predecessor.frame.callbacks:
            callback()
            self.check()
        cancellation(frame.published[3])

    def inputs(self):
        frame = self.check()
        saved, last = frame.predecessor.frame, frame.predecessor.phases[-1][1]
        return custody._Inputs(saved.originals, saved.original_pin, last.staged, last.staged_pin)

    def directory(self, key, path, identity=None, *, parent=None, create=False):
        owner = self.live()
        frame = _producer_frame(self)
        found = next((row for row in frame.handles if row[0] == key), None)
        if found is None:
            directory = owner.open(path) if parent is None else owner.child(parent, path.name, create=create)
            actual = tuple(directory_identity(list(directory.identity), frame.limits.clock[0]))
            # The requested grammar may use PurePath; the native opener returns
            # Path. Pin the ORIGINAL backend path, not the request's type. The
            # value/ownership checks below still bind it to the requested route.
            row = (key, directory, directory.path, actual)
            _update_producer(self, handles=(*_producer_frame(self).handles, row))
            self.handles[key] = directory
            found = row
        require(found[2] == path and (identity is None or found[3] == tuple(identity)),
                "BOOTSTRAP_PRODUCER_DIRECTORY_CHANGED")
        _new_entry_owned(owner, found[1], path, found[3])
        self.check()
        return found[1]

    def read_file(self, directory, name, maximum=LIMIT, *, expected=None, binding=None):
        """Bounded metadata only; outer streams use their separate hash reader."""
        owner = self.live()
        require(type(maximum) is int and 0 < maximum <= producer.LIMIT, "BOOTSTRAP_PRODUCER_METADATA_LIMIT")
        end = owner.end()
        reader = owner.acquire("reader", lambda: directory.open_file(name, max_bytes=maximum, deadline=end))
        raw = retained = None
        try:
            before = reader.initial_info
            require(type(before.size) is int and 0 <= before.size <= maximum, "BOOTSTRAP_PRODUCER_METADATA_SIZE")
            retained = staging.files._info_binding(before)
            require(binding is None or retained == binding, "BOOTSTRAP_PRODUCER_ORIGINAL_FILE_REPLACED")
            data = bytearray()
            while len(data) < before.size:
                owner.end()
                count = min(PRODUCER_READ_BLOCK, before.size - len(data))
                part = reader.read(count)
                require(type(part) is bytes and 0 < len(part) <= count, "BOOTSTRAP_PRODUCER_METADATA_SHORT_READ")
                data.extend(part)
                owner.end()
            require(reader.read(1) == b"" and reader.verify() == before, "BOOTSTRAP_PRODUCER_METADATA_CHANGED")
            raw = bytes(data)
            require(expected is None or raw == expected, "BOOTSTRAP_PRODUCER_ORIGINAL_BYTES_CHANGED")
            owner.end()
        except BaseException as error:
            self.error("producer-metadata-read", error)
        finally:
            owner.close_one(reader)
        self.raise_first()
        owner.end()
        return raw, retained

    def remember(self, key, directory, name, raw, maximum=LIMIT, *, binding=None):
        frame = self.check()
        require(type(raw) is bytes and len(raw) <= maximum and not any(row[0] == key for row in frame.files),
                "BOOTSTRAP_PRODUCER_ORIGINAL_ROSTER")
        identity = tuple(directory_identity(list(directory.identity), frame.limits.clock[0]))
        _new_entry_owned(self.live(), directory, directory.path, identity)
        # A reader's ORIGINAL binding must cross this boundary, especially for
        # canonical start/receipt. For newly written metadata establish it now;
        # never regenerate a supplied original binding from a later same-byte
        # file. The detached encoding cannot be mutated through the caller.
        if binding is None:
            _actual, binding = self.read_file(directory, name, maximum, expected=raw)
        require(staging.files._file_binding(binding), "BOOTSTRAP_PRODUCER_ORIGINAL_FILE_BINDING")
        retained = origin.encoded(binding)
        frame = self.check()
        _update_producer(self, files=(*frame.files,
            _ProducerFile(key, directory, directory.path, identity, name, maximum, raw, retained)))
        self.records[key] = raw
        self.check()

    def reread(self):
        owner = self.live()
        for _key, directory, path, identity, name, maximum, raw, binding_raw in _producer_frame(self).files:
            _new_entry_owned(owner, directory, path, identity)
            self.read_file(directory, name, maximum, expected=raw, binding=origin.parse(binding_raw))
        self.check()

    def file_facade(self):
        """Source-only adapter for unchanged original-file parsers, no owner."""
        call, owner = self, self.live()
        directories = {"bootstrap-source", "bootstrap-source-parent", "custody-source-root", "custody-source-scripts",
                       "dependency-seed-source-root", "dependency-seed-source-parent"}
        class Reader:
            @property
            def unknown(self):
                return _producer_frame(call).unknown

            def check(self, *, new=False):
                require(type(new) is bool, "BOOTSTRAP_PRODUCER_FILE_MODE")
                require(call.live() is owner, "BOOTSTRAP_PRODUCER_FILE_OWNER_CHANGED")
                owner.end()

            def end(self, *, new=False):
                self.check(new=new)
                return owner.end()

            def acquire(self, label, factory):
                require(label in directories or label in ("reader", "dependency-seed-input"),
                        "BOOTSTRAP_PRODUCER_SOURCE_LABEL")
                return owner.acquire("source-directory" if label in directories else "reader", factory)

            def close_one(self, resource):
                owner.close_one(resource)
                call.raise_first()
                require(any(pin.value is resource and pin.attempted and pin.closed for pin in
                    _producer_frame(call).resources), "BOOTSTRAP_PRODUCER_SOURCE_CLOSE_UNKNOWN")

            def error(self, stage, error, *, unknown=False):
                call.error(stage, error, unknown=unknown)
        return Reader()

    def host(self):
        owner = self.live()
        owner.end()
        frame = _producer_frame(self)
        saved = frame.predecessor.frame
        entry = frame.transition._attempt.transition._entry
        context = origin.parse(entry.context_original)
        require(origin.wire.TOKEN_ENV not in os.environ and os.environ.get(PREPARE_OUTCOME_ENV) == "success" and
                os.environ.get(PREPARE_HASH_ENV) == origin.digest(entry.handoff_original),
                "BOOTSTRAP_PRODUCER_PREPARE_OUTCOME_OR_TOKEN")
        selection, path, event = host_inputs(saved.originals.clock.role)
        require(path == saved.paths[0] and selection == context["selection"] and event == entry.admitted.original_event and
                context["runnerName"] == os.environ.get("RUNNER_NAME") and context["inheritedContext"] == query._inherited_context() and
                os.getpid() != origin.parse(entry.preparation_original)["processIdentity"]["pid"],
                "BOOTSTRAP_PRODUCER_ACTUAL_HOST_CHANGED")
        inputs = _parent_originals(saved.record[0])[4][5][0]
        require(initialization._installed() == inputs.toolchains.originals and canonical._interpreter() == inputs.interpreter and
                inputs.policy == initialization.properties(inputs.homes), "BOOTSTRAP_PRODUCER_INSTALLED_INPUTS_CHANGED")
        env = recipient_environment(saved.paths[3])
        env.update({name: home for name, _supplied, home, _identities in inputs.toolchains.originals})
        require(tuple(sorted(env.items())) == inputs.environment, "BOOTSTRAP_PRODUCER_INITIAL_ENVIRONMENT_CHANGED")
        owner.end()
        return env

    def read_originals(self):
        owner = self.live()
        self.host()
        frame = _producer_frame(self)
        saved, previous = frame.predecessor.frame, frame.transition._attempt
        old = previous.transition
        entry, paths = old._entry, saved.paths
        value = origin.parse(entry.raw)
        for key, path, identity in (("original", paths[0], value["preparation"]["sessionIdentity"]),
                ("adoption", paths[1], value["sessionIdentity"]), ("entry", paths[2], previous.target_identity)):
            self.directory(key, path, identity)
        adoption, current = self.handles["adoption"], self.handles["entry"]
        require(owner.read(adoption, "entry-context.json") == entry.raw and
                owner.read(adoption, "entry-close-pending.json") == old.pending_raw and
                owner.read(current, "new-entry-pending.json") == previous.pending_raw,
                "BOOTSTRAP_PRODUCER_ENTRY_ORIGINAL_CHANGED")
        for target, admitted, session_raw, returned_raw in (
                (adoption, entry.admitted, entry.session_original, entry.return_original),
                (current, previous.admitted, previous.admission_originals[1], previous.admission_originals[2])):
            directory = self.directory("admission:" + str(target.path), target.path / "admission", parent=target)
            require(load_admission(owner, directory) == admitted and owner.read(directory, "session-result.json") == session_raw and
                    owner.read(target, "admission-return.json") == returned_raw, "BOOTSTRAP_PRODUCER_ENTRY_ADMISSION_CHANGED")
        _admission_history_content(entry.admitted, entry.session_original, entry.return_original, history.snapshot(old._fence))
        _new_entry_return_content(previous)
        admitted, _context, prepared = _read_prepared(_ProducerOriginalReader(self), self.handles["original"],
            entry.handoff_original, entry.context_original)
        require(admitted == entry.admitted and same_preparation(prepared, origin.parse(entry.preparation_original)) and
                same_preparation(prepared, origin.parse(previous.preparation)), "BOOTSTRAP_PRODUCER_PREPARATION_CHANGED")
        service = self.directory("service", paths[0] / "service", parent=self.handles["original"])
        responses = tuple((name, owner.read(service, name + ".json")) for name in ("attempt", "jobs"))
        require(responses == old.responses and origin.encoded(_entry_close_proposal(entry, responses)) == old.proposal_raw and
                old.proposal_raw == saved.originals.proposal_raw, "BOOTSTRAP_PRODUCER_SERVICE_ORIGINALS_CHANGED")
        files = saved.files + tuple((key, str(path), identity, name, maximum, raw)
            for _parent, closed in frame.predecessor.phases
            for key, _directory, path, identity, name, maximum, raw in closed.files)
        for _key, spelling, identity, name, maximum, raw in files:
            path = Path(spelling)
            directory = self.directory("predecessor:" + spelling, path, identity)
            self.read_file(directory, name, maximum, expected=raw)
        self.host()

    def state_readback(self, *, before):
        """Fresh prelaunch baseline and a DIFFERENT narrow postlaunch oracle."""
        require(type(before) is bool, "BOOTSTRAP_PRODUCER_STATE_MODE")
        owner, inputs = self.live(), self.inputs()
        frame = _producer_frame(self)
        request = origin.parse(frame.predecessor.phases[-1][1].leaf.request_raw)
        initial = self.directory("initializer", inputs.session, inputs.directories["session"])
        handles = {"session": initial}
        for name in staging.DIRECTORIES[1:]:
            parent = initial if name == "state" else handles["state"]
            handles[name] = self.directory("canonical:" + name, parent.path / name, inputs.directories[name], parent=parent)
        for key, directory, name, raw in (("initializer-context", initial, "initializer-context.json", inputs.context_raw),
                ("canonical-context", handles["state"], "context.json", inputs.canonical_raw),
                ("properties", handles["gradle-home"], "gradle.properties", inputs.properties_raw)):
            self.read_file(directory, name, expected=raw, binding=request["fileBindings"][key])
        leaf = self.file_facade()
        if before:
            require(frame.native.launch_attempted is False, "BOOTSTRAP_PRODUCER_PRELAUNCH_AFTER_SPAWN")
            staging._names(leaf, handles["state"], ("context.json", "gradle-home", "evidence", "cancellations"))
            staging._names(leaf, handles["gradle-home"], ("gradle.properties",))
            staging._names(leaf, handles["evidence"], ())
            staging._names(leaf, handles["cancellations"], ())
        else:
            require(frame.native.work_accepted is True and frame.native.retired is True and not frame.cancellation_attempted,
                    "BOOTSTRAP_PRODUCER_POSTLAUNCH_NOT_SUCCESS")
            staging._names(leaf, handles["state"], ("context.json", "gradle-home", "evidence", "cancellations", "gradle.lock"))
            invocation = request["owner"]["productInvocation"]
            staging._names(leaf, handles["evidence"], (invocation,))
            staging._names(leaf, handles["cancellations"], ())
            # Warmed H is not enumerated/copied or called a populated cohort.
        for name, directory in handles.items():
            require(tuple(directory.verify().identity) == inputs.directories[name], "BOOTSTRAP_PRODUCER_INITIALIZER_REPLACED")
        pin = frame.predecessor.phases[-1][1].request_pin
        directory = self.directory("reservation", Path(pin.path), pin.directory)
        retained = self.directory("retained", Path(pin.path) / "retained", pin.retained, parent=directory)
        self.read_file(directory, "request.json", expected=frame.predecessor.phases[-1][1].leaf.request_raw,
                       binding=staging.files.record(pin.binding_raw))
        staging._names(leaf, directory, ("request.json", "retained"))
        staging._names(leaf, retained, ())
        container = self.directory("stage-container", inputs.container)
        restore = self.directory("restore-home", inputs.restore, parent=container)
        custody._stage_readback(leaf, inputs, container, restore)
        require(custody._sources(leaf, inputs) == {name: request[name] for name in ("inputs", "bootstrapInputs", "custodyInputs")},
                "BOOTSTRAP_PRODUCER_SOURCE_INPUTS_CHANGED")
        expected_owner = {"job": inputs.canonical["id"], "productInvocation": request["owner"]["productInvocation"],
                          "sameHomeStopInvocation": request["owner"]["productInvocation"]}
        require(request["owner"] == expected_owner and producer._uuid(expected_owner["productInvocation"]) and
                request["evidenceDirectory"] == str(inputs.state / "evidence" / expected_owner["productInvocation"]),
                "BOOTSTRAP_PRODUCER_RESERVATION_TARGET")
        owner.end()

    def admit(self):
        owner = self.live()
        frame = _producer_frame(self)
        require(not frame.query_attempted and frame.phases[-1].name == "WORK", "BOOTSTRAP_PRODUCER_QUERY_REENTRY")
        _update_producer(self, query_attempted=True)
        window = frame.window
        began = window.now()
        work = min(frame.limits.ends[0], origin.integer(began + 75 * origin.NS))
        final = min(frame.limits.ends[0], origin.integer(began + 120 * origin.NS))
        pair = (window.deadline(75, limit=work), window.deadline(120, limit=final))
        path = self.handles["phase"].path / "admission"
        supplier = original = result = None
        try:
            supplier = query.NativeGitQueries(ROOT, path, check_cancel=lambda: window.now(limit=work), owner_deadlines=pair)
            _update_producer(self, query=(supplier, type(supplier), pair, work, final))
            window.now(limit=work)
            supplier.native_host_matches_actions()
            result = bootstrap.admit(ROOT, query_runner=supplier, expected=frame.transition._attempt.admitted)
            supplier.retain_admission(result)
            window.now(limit=work)
        except BaseException as error:
            original = error
        finally:
            if supplier is not None:
                try:
                    supplier._finalize(original)
                    _update_producer(self, query_returned=(True, None, None))
                except BaseException as error:
                    _update_producer(self, query_returned=(False, None, None))
                    if original is None:
                        original = error
            # Observe exceptional finalizer return as well; it does not erase
            # an original exception or authorize the provisional session bytes.
            try:
                observed = window.now(limit=final)
                if supplier is not None:
                    returned = _producer_frame(self).query_returned
                    _update_producer(self, query_returned=(returned[0], observed, _producer_frame(self).local_last))
            except BaseException as error:
                if original is None:
                    original = error
            if (supplier is not None and supplier.unknown) or query.QUARANTINE or diagnostics._QUARANTINE:
                if original is None:
                    original = origin.OriginError("BOOTSTRAP_PRODUCER_QUERY_UNKNOWN")
                self.error("producer-query", original, unknown=True)
        if original is not None:
            self.error("producer-query-return", original)
            raise _producer_frame(self).original
        require(type(result) is I.Admission and result == frame.transition._attempt.admitted and supplier.closed and
                _producer_frame(self).query_returned[0] is True, "BOOTSTRAP_PRODUCER_READMISSION")
        directory = self.directory("producer-admission", path)
        require(load_admission(owner, directory) == result, "BOOTSTRAP_PRODUCER_READMISSION_CHANGED")
        for name, raw in (("admission.json", result.record), ("original-event.json", result.original_event),
                ("original-policy.json", result.original_policy), ("recipient-public.asc", result.public_key),
                ("session-result.json", owner.read(directory, "session-result.json"))):
            self.remember("admission/" + name, directory, name, raw)
        session = origin.parse(self.records["admission/session-result.json"])
        require(set(session) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"} and
                type(session["schema"]) is int and session["schema"] == 1 and session["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
                type(session["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", session["job"]) and
                type(session["queries"]) is list and type(session["readbacks"]) is list and
                session["result"] == "READY_FOR_CALLER_SEAL" and session["retirement"] == "KNOWN" and
                session["firstError"] is None and session["errors"] == [],
                "BOOTSTRAP_PRODUCER_QUERY_RECORD")
        raw = owner.write(self.handles["phase"], "admission-return.json", {"admissionSha256": origin.digest(result.record),
            "sessionSha256": origin.digest(self.records["admission/session-result.json"]), "clock": origin.clock_value(window.clock),
            "returnedNs": _producer_frame(self).query_returned[1], "ownerDeadlineScope": "ORIGINAL_PRODUCER_WORK_ONLY"})
        self.remember("admission-return", self.handles["phase"], "admission-return.json", raw)
        window.now(limit=final)

    def command(self, *, first=False):
        frame = self.check()
        owner, inputs = self.live(), self.inputs()
        require(type(first) is bool and frame.phases[-1].name in ("WORK", "READ"), "BOOTSTRAP_PRODUCER_COMMAND_MODE")
        base = self.host()
        request = origin.parse(frame.predecessor.phases[-1][1].leaf.request_raw)
        invocation = request["owner"]["productInvocation"]
        inherited = processes.ownership_domains(base.get(processes.CHAIN_ENV, ""), base.get(processes.DOMAINS_ENV, ""))
        require(len(inherited) <= 30 and invocation not in {row["id"] for row in inherited},
                "BOOTSTRAP_PRODUCER_RESERVED_ANCESTRY_COLLISION")
        outer = frame.outer_invocation
        if first:
            require(frame.descriptor is None and outer is None, "BOOTSTRAP_PRODUCER_COMMAND_REENTRY")
            selected = uuid.uuid4()
            require(type(selected) is uuid.UUID and selected.version == 4, "BOOTSTRAP_PRODUCER_UUID_SUPPLIER")
            outer = selected.hex
            _update_producer(self, outer_invocation=outer)  # One original allocation; no collision retry.
        else:
            require(type(outer) is str and frame.descriptor is not None, "BOOTSTRAP_PRODUCER_COMMAND_NOT_BOUND")
        saved = frame.predecessor.frame
        old_invocations = {origin.parse(old[4][1].records["start.json"])["invocation"] for old in saved.registries[6:8]}
        require(outer not in {invocation, inputs.invocation, inputs.canonical["id"], origin.parse(inputs.context_raw)["job"],
                             *old_invocations, *(row["id"] for row in inherited)} and invocation not in old_invocations,
                "BOOTSTRAP_PRODUCER_OUTER_INVOCATION_COLLISION")
        environment = processes.ownership_environment(base, inputs.canonical["id"], outer, str(inputs.state), str(inputs.home),
                                                       allow_new_context=True)
        domains = processes.ownership_domains(environment[processes.CHAIN_ENV], environment[processes.DOMAINS_ENV])
        require(domains[:-1] == inherited and domains[-1] == {"id": outer, "job": inputs.canonical["id"],
            "state": str(inputs.state), "home": str(inputs.home)}, "BOOTSTRAP_PRODUCER_DOMAIN_CHANGED")
        raw = producer_command.command_request(inputs.admitted.record, inputs.canonical_raw,
            invocation=invocation, ancestor_invocations=tuple(row["id"] for row in domains))
        if first:
            _update_producer(self, descriptor=raw, environment=tuple(sorted(environment.items())))
        else:
            require(raw == frame.descriptor and tuple(sorted(environment.items())) == frame.environment,
                    "BOOTSTRAP_PRODUCER_COMMAND_CHANGED")
        owner.end()
        return origin.parse(raw), environment

    def resource(self, label):
        pins = [pin for pin in _producer_frame(self).resources if pin.label == label]
        require(len(pins) <= 1, "BOOTSTRAP_PRODUCER_RESOURCE_DUPLICATE")
        return pins[0] if pins else None

    def close_resource(self, pin):
        """Once-close an actual private return, never a caller's close flag."""
        frame = _producer_frame(self)
        actual = next((row for row in frame.resources if row.value is pin.value), None)
        require(actual is not None and actual.row is pin.row and actual.kind is type(pin.value),
                "BOOTSTRAP_PRODUCER_CLOSE_BINDING")
        if actual.attempted:
            return
        _update_producer(self, resources=tuple(row._replace(attempted=True) if row.value is pin.value else row
                                              for row in frame.resources))
        pin.row["attempted"] = True
        try:
            pin.value.close()
            current = _producer_frame(self)
            _update_producer(self, resources=tuple(row._replace(closed=True) if row.value is pin.value else row
                                                  for row in current.resources))
            pin.row["closed"] = True
        except BaseException as error:
            self.error(pin.label + "-close", error, unknown=True)

    def original_file(self, key):
        rows = [row for row in _producer_frame(self).files if row[0] == key]
        require(len(rows) == 1, "BOOTSTRAP_PRODUCER_ORIGINAL_MISSING")
        return rows[0][6]

    def native_scope(self):
        """Narrow independently known scope, even after unrelated file UNKNOWN."""
        frame, pin = _producer_frame(self), self.resource("native-scope")
        require(pin is not None and type(pin.value) is pin.kind and not pin.attempted,
                "BOOTSTRAP_PRODUCER_SCOPE_NOT_OWNED")
        start = origin.parse(self.original_file("outer-start"))
        scope = pin.value
        if frame.limits.clock[0] == "windows-x64":
            require(scope.job_id == start["job"] and scope.invocation == start["invocation"],
                    "BOOTSTRAP_PRODUCER_NATIVE_DOMAIN_CHANGED")
        else:
            require((scope.job, scope.invocation, scope.state, scope.home) ==
                    (start["job"], start["invocation"], start["state"], start["home"]),
                    "BOOTSTRAP_PRODUCER_NATIVE_DOMAIN_CHANGED")
        return scope

    def capture_binding(self, capture):
        frame = _producer_frame(self)
        pin = self.resource(capture.name)
        require(pin is not None and pin.value is capture.stream and type(pin.value) is pin.kind and not pin.attempted,
                "BOOTSTRAP_PRODUCER_CAPTURE_NOT_OWNED")
        target = next(row for row in frame.handles if row[0] == "capture-output")
        stream = capture.stream
        require(stream.path == target[2] / (capture.name + ".log"), "BOOTSTRAP_PRODUCER_CAPTURE_PATH_CHANGED")
        maximum, end = ((stream.max_bytes, stream._deadline) if frame.limits.clock[0] == "windows-x64" else
                        (stream.maximum, stream.deadline))
        require(type(maximum) is int and maximum == 67174400 and type(end) is type(frame.limits.local_ends[2]) and
                end == frame.limits.local_ends[2], "BOOTSTRAP_PRODUCER_CAPTURE_BOUND_CHANGED")
        target[1].verify()
        require(tuple(target[1].identity) == target[3], "BOOTSTRAP_PRODUCER_CAPTURE_DIRECTORY_CHANGED")
        return stream

    def observe_captures(self, *, cleanup=False):
        frame = _producer_frame(self)
        require(type(cleanup) is bool and len(frame.captures) == 2 and
                tuple(row.name for row in frame.captures) == ("stdout", "stderr") and
                len({row.identity for row in frame.captures}) == 2, "BOOTSTRAP_PRODUCER_CAPTURE_ROSTER")
        for capture in frame.captures:
            frame.window.now(final=cleanup)
            stream = self.capture_binding(capture)
            info = stream.observe_live_output() if frame.limits.clock[0] == "windows-x64" else stream.verify()
            stamp = _producer_stamp(info, frame.limits.clock[0])
            require(stamp[0] == capture.identity and type(stamp[1]) is int and
                    capture.highwater <= stamp[1] <= 67174400, "BOOTSTRAP_PRODUCER_CAPTURE_SHRANK_OR_OVERFLOWED")
            current = _producer_frame(self)
            _update_producer(self, captures=tuple(row._replace(highwater=stamp[1]) if row.name == capture.name else row
                                                  for row in current.captures))
            frame.window.now(final=cleanup)
        require(sum(row.highwater for row in _producer_frame(self).captures) <= 134348800,
                "BOOTSTRAP_PRODUCER_OUTER_CAPTURE_AGGREGATE")

    def launch(self):
        owner, frame = self.live(), _producer_frame(self)
        window, directory = frame.window, self.handles["phase"]
        descriptor, environment = self.command()
        request = origin.parse(descriptor["requestBytes"].encode("ascii"))
        start = {"schema": 1, "scope": "BOOTSTRAP_CONFIGURATION_PARENT_PRELAUNCH_V1",
            "contextSha256": descriptor["canonicalContextSha256"], "argv": descriptor["argv"], "cwd": str(ROOT),
            "role": frame.limits.clock[0], "job": request["jobId"], "invocation": frame.outer_invocation,
            "state": descriptor["state"], "home": request["gradleHome"],
            "inheritedContext": {name: environment[name] for name in query._CONTEXT}, "startedNs": frame.limits.first,
            "workEndNs": frame.limits.ends[0], "finalEndNs": frame.limits.ends[2], "exitCode": None,
            "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"}
        raw = owner.write(directory, "outer-start.json", start)
        self.remember("outer-start", directory, "outer-start.json", raw)
        try:
            # Only this independently reopened direct-output view owns native
            # sinks. Seed PosixFile is NOT a fileno-compatible launch sink.
            output = owner.acquire("directory", lambda: windows.open_private_directory(directory.path)
                if frame.limits.clock[0] == "windows-x64" else query._PosixDirectory(directory.path))
            require(tuple(output.identity) == tuple(directory.identity), "BOOTSTRAP_PRODUCER_OUTPUT_DIRECTORY_CHANGED")
            current = _producer_frame(self)
            _update_producer(self, handles=(*current.handles, ("capture-output", output, directory.path, tuple(output.identity))))
            self.handles["capture-output"] = output
            for name in ("stdout", "stderr"):
                stream = owner.acquire(name, lambda name=name: output.create_file(name + ".log",
                    max_bytes=67174400, deadline=frame.limits.local_ends[2]))
                info = stream.observe_live_output() if frame.limits.clock[0] == "windows-x64" else stream.verify()
                stamp = _producer_stamp(info, frame.limits.clock[0])
                require(type(stamp[1]) is int and stamp[1] == 0, "BOOTSTRAP_PRODUCER_NONEMPTY_CAPTURE")
                capture = _ProducerCapture(name, stream, stamp[0], 0, None, False, False, None)
                current = _producer_frame(self)
                _update_producer(self, captures=(*current.captures, capture))
                window.now()
            def factory():
                _producer_native(self, scope_attempted=True)
                return processes.make_scope(start["job"], start["invocation"], start["state"], start["home"])
            scope = owner.acquire("native-scope", factory)
            self.native_scope()
            identity = preparer_identity(scope, frame.limits.clock[0])
            _producer_native(self, preparer_raw=origin.encoded(identity))
            baseline = origin.encoded({"role": frame.limits.clock[0],
                "baseline": sorted(scope.baseline) if hasattr(scope, "baseline") else None,
                "kernelJob": frame.limits.clock[0] == "windows-x64"})
            _producer_native(self, baseline_raw=baseline)
            baseline_record(baseline, frame.limits.clock[0])
            self.remember("baseline", directory, "baseline.json", owner.write(directory, "baseline.json", baseline))
            self.read_originals()
            self.state_readback(before=True)
            checked_descriptor, checked_environment = self.command()
            require(checked_descriptor == descriptor and checked_environment == environment,
                    "BOOTSTRAP_PRODUCER_LAUNCH_COMMAND_CHANGED")
            minimum = window.now()
            _producer_native(self, launch_minimum=minimum, argv=tuple(descriptor["argv"]), launch_attempted=True)
            child = scope.spawn(descriptor["argv"], str(ROOT), environment,
                                stdout=self.resource("stdout").value, stderr=self.resource("stderr").value)
            _producer_native(self, child=child, child_kind=type(child))  # Before pipe, PID, birth, callback or clock checks.
            require(child.stdout is None and child.stderr is None, "BOOTSTRAP_PRODUCER_PRIVATE_SINKS_REQUIRED")
            pid = child.pid
            require(type(pid) is int and 0 < pid <= 2**32 - 1, "BOOTSTRAP_PRODUCER_CHILD_PID")
            _producer_native(self, child_pid=pid)
            birth_raw = origin.encoded(scope.description())
            _producer_native(self, birth_raw=birth_raw)
            birth = origin.parse(birth_raw)
            leaders = [item for item in birth.get("startedIdentities", []) if item.get("pid") == pid]
            require(len(leaders) == 1, "BOOTSTRAP_PRODUCER_NATIVE_BIRTH")
            native_record(birth, start, leaders[0], descriptor["argv"], terminal=False)
            require(identity["pid"] != pid, "BOOTSTRAP_PRODUCER_CONTROLLER_IS_PARENT")
            baseline_value = baseline_record(baseline, frame.limits.clock[0])
            if baseline_value["baseline"] is not None:
                leader = lifetime(leaders[0], frame.limits.clock[0])
                require(list(leader[:4] if frame.limits.clock[0].startswith("macos-") else leader)
                        not in baseline_value["baseline"], "BOOTSTRAP_PRODUCER_PREEXISTING_LEADER")
            _producer_native(self, leader_raw=origin.encoded(leaders[0]))  # Credible ORIGINAL birth, not launchAttempted.
            observed = window.now(minimum=minimum)
            raw = owner.write(directory, "native-start.json", {"ownership": birth, "leader": leaders[0],
                "preparerIdentity": identity, "observedNs": observed})
            self.remember("native-start", directory, "native-start.json", raw)
            while True:
                window.now()
                self.observe_captures()
                code = child.poll()
                if code is not None:
                    _producer_native(self, exit_code=code)  # Actual exit precedes every subsequent check.
                window.now()
                require(type(child) is _producer_frame(self).native.child_kind and child.pid == pid,
                        "BOOTSTRAP_PRODUCER_CHILD_CHANGED")
                survivors = scope.discover()
                window.now()
                self.observe_captures()
                if code is not None:
                    require(type(code) is int and code == 0, "BOOTSTRAP_PRODUCER_CANONICAL_EXIT")
                    require(survivors == [], "BOOTSTRAP_PRODUCER_WORK_DESCENDANTS")
                    completed = window.now()
                    _producer_native(self, completed_ns=completed, work_accepted=True)
                    break
                time.sleep(.025)
        except BaseException as error:
            self.error("producer-native-work", error)
        finally:
            self.finish_native()
        self.raise_first()

    def cancellation_request(self):
        """Exclusive one-shot RETURN transaction over the original pinned home.

        The unchanged canonical reader accepts these four fields. Unlike the
        old idempotent writer, this does not adopt an existing/racing file.
        A visible or read-back request is NOT proof the child cooperated.
        """
        frame = _producer_frame(self)
        require(frame.phases[-1].name == "RETURN" and frame.original is not None and not frame.cancellation_attempted,
                "BOOTSTRAP_PRODUCER_CANCEL_REENTRY_OR_PHASE")
        _update_producer(self, cancellation_attempted=True)
        writer = reader = None
        try:
            self.cleanup_bindings()
            frame = _producer_frame(self)
            require(not frame.unknown and not frame.owner.unknown and frame.native.leader_raw is not None and
                    frame.native.child is not None and type(frame.native.child) is frame.native.child_kind and
                    frame.native.child.pid == frame.native.child_pid, "BOOTSTRAP_PRODUCER_CANCEL_NO_ORIGINAL_CHILD")
            scope = self.native_scope()
            start = origin.parse(self.original_file("outer-start"))
            native_record(origin.parse(frame.native.birth_raw), start, origin.parse(frame.native.leader_raw),
                          list(frame.native.argv), terminal=False)
            require(scope is self.resource("native-scope").value, "BOOTSTRAP_PRODUCER_CANCEL_SCOPE_CHANGED")
            descriptor = origin.parse(frame.descriptor)
            request = origin.parse(descriptor["requestBytes"].encode("ascii"))
            directories = {row[0]: row for row in frame.handles}
            for key in ("canonical:state", "canonical:gradle-home", "canonical:cancellations"):
                _key, directory, path, identity = directories[key]
                require(directory.path == path and tuple(directory.verify().identity) == identity,
                        "BOOTSTRAP_PRODUCER_CANCEL_DIRECTORY_CHANGED")
            directory = directories["canonical:cancellations"][1]
            require(directory.path == Path(descriptor["state"]) / "cancellations" and
                    start["state"] == descriptor["state"] and start["home"] == request["gradleHome"] and
                    start["job"] == request["jobId"] and request["id"] != start["invocation"],
                    "BOOTSTRAP_PRODUCER_CANCEL_TARGET_CHANGED")
            attempted = frame.window.sample(cleanup=True)
            _update_producer(self, cancellation_stamps=(("attempted", attempted, _producer_frame(self).local_last),))
            label = datetime.now(timezone.utc).isoformat()
            producer._utc(label)
            producer._uuid(request["id"])
            producer._uuid(request["jobId"])
            raw = origin.encoded({"schema": 1, "id": request["id"], "jobId": request["jobId"], "requestedUtc": label})
            require(0 < len(raw) <= 512, "BOOTSTRAP_PRODUCER_CANCEL_BYTES")
            _update_producer(self, cancellation_raw=raw)
            end = frame.window.cleanup_deadline(225)
            # The two source-selected file acquisitions below are NOT exposed
            # as generic RETURN owner.acquire/read/write or arbitrary callbacks.
            writer = directory.create_file(request["id"] + ".json", max_bytes=len(raw), deadline=end)
            frame.owner._retain("cancellation-writer", writer)
            frame.window.sample(cleanup=True)
            count = writer.write(raw)
            require(type(count) is int and count == len(raw), "BOOTSTRAP_PRODUCER_CANCEL_SHORT_WRITE")
            frame.window.sample(cleanup=True)
            writer.sync()
            info = writer.verify()
            require(info.size == len(raw), "BOOTSTRAP_PRODUCER_CANCEL_WRITE_CHANGED")
            binding = staging.files._info_binding(info)
            frame.window.sample(cleanup=True)
            frame.owner.close_one(writer)
            pin = self.resource("cancellation-writer")
            require(pin.attempted and pin.closed and not _producer_frame(self).unknown,
                    "BOOTSTRAP_PRODUCER_CANCEL_WRITER_NOT_CLOSED")
            end = frame.window.cleanup_deadline(225)
            reader = directory.open_file(request["id"] + ".json", max_bytes=len(raw), deadline=end)
            frame.owner._retain("cancellation-reader", reader)
            frame.window.sample(cleanup=True)
            before = reader.initial_info
            require(staging.files._info_binding(before) == binding and before.size == len(raw),
                    "BOOTSTRAP_PRODUCER_CANCEL_READBACK_REPLACED")
            actual = reader.read(len(raw))
            frame.window.sample(cleanup=True)
            require(type(actual) is bytes and actual == raw and reader.read(1) == b"" and reader.verify() == before,
                    "BOOTSTRAP_PRODUCER_CANCEL_READBACK_CHANGED")
            frame.owner.close_one(reader)
            pin = self.resource("cancellation-reader")
            require(pin.attempted and pin.closed and not _producer_frame(self).unknown,
                    "BOOTSTRAP_PRODUCER_CANCEL_READER_NOT_CLOSED")
            returned = frame.window.sample(cleanup=True)
            current = _producer_frame(self)
            _update_producer(self, cancellation_stamps=(*current.cancellation_stamps,
                ("readback-returned", returned, current.local_last)))
        except BaseException as error:
            self.error("producer-cancellation-request", error)
        finally:
            # Actually returned handles already belong to the private ledger;
            # factory failures create no substitute target or adopted record.
            for resource in (reader, writer):
                if resource is not None:
                    frame.owner.close_one(resource)

    def return_child(self):
        frame = _producer_frame(self)
        require(frame.phases[-1].name == "RETURN", "BOOTSTRAP_PRODUCER_RETURN_PHASE")
        if frame.native.child is None or frame.native.leader_raw is None:
            return
        if frame.original is not None and not frame.unknown:
            self.cancellation_request()
        # No new product, stop, query, source or directory acquisition here.
        while not _producer_frame(self).unknown:
            frame.window.sample(cleanup=True)
            current = _producer_frame(self)
            if current.native.exit_code is not None:
                return
            child = current.native.child
            require(type(child) is current.native.child_kind and child.pid == current.native.child_pid,
                    "BOOTSTRAP_PRODUCER_RETURN_CHILD_CHANGED")
            self.observe_captures(cleanup=True)
            code = child.poll()
            if code is not None:
                _producer_native(self, exit_code=code)
            frame.window.sample(cleanup=True)
            self.native_scope().discover()
            frame.window.sample(cleanup=True)
            if code is not None:
                return  # A late0 is retained, NEVER promoted to work_accepted.
            time.sleep(.025)

    def finish_native(self):
        frame = _producer_frame(self)
        if frame.window is None:
            return
        try:
            frame.window.advance("RETURN")
            self.return_child()
        except BaseException as error:
            self.error("producer-return", error)
        final_ready = False
        try:
            frame.window.advance("FINAL")
            final_ready = True
        except BaseException as error:
            self.error("producer-final", error)
        pin = self.resource("native-scope")
        if pin is not None:
            drain_end = None
            try:
                scope = self.native_scope()
                try:
                    require(final_ready, "BOOTSTRAP_PRODUCER_FINAL_START_FAILED")
                    drain_end = frame.window.cleanup_deadline(45)
                    local = staging._local(time.monotonic())
                    require(local >= _producer_frame(self).local_last, "BOOTSTRAP_PRODUCER_LOCAL_BACKWARDS")
                    _update_producer(self, local_last=local)
                    remaining = max(0, drain_end - local)
                except BaseException as error:
                    self.error("producer-drain-fence", error)
                    raise
                _producer_native(self, drain_attempted=True)
                grace = min(5, remaining)
                survivors = scope.drain(grace=grace, kill_wait=min(5, max(0, remaining - grace)), deadline=drain_end)
                _producer_native(self, survivors_raw=origin.encoded({"survivors": survivors}))
                terminal = origin.encoded(scope.description())
                _producer_native(self, terminal_raw=terminal)
                require(survivors == [] and origin.parse(terminal).get("discoveryErrors") == [],
                        "BOOTSTRAP_PRODUCER_NATIVE_DRAIN_UNKNOWN")
                current = _producer_frame(self)
                if current.native.preparer_raw is not None:
                    require(origin.encoded(preparer_identity(scope, frame.limits.clock[0])) == current.native.preparer_raw,
                            "BOOTSTRAP_PRODUCER_PARENT_LIFETIME_CHANGED")
                if current.native.leader_raw is not None:
                    native_record(origin.parse(terminal), origin.parse(self.original_file("outer-start")),
                        origin.parse(current.native.leader_raw), list(current.native.argv))
                    require(origin.parse(current.native.birth_raw)["launches"] == origin.parse(terminal)["launches"],
                            "BOOTSTRAP_PRODUCER_NATIVE_LAUNCH_CHANGED")
                frame.window.sample(cleanup=True)
                posix._deadline(drain_end)
                _producer_native(self, retired=True)
            except BaseException as error:
                self.error("producer-native-drain", error, unknown=True)
            try:
                # A separately known scope is not abandoned because an
                # unrelated file/query failed. No rejected public alias is used.
                self.native_scope()
                self.close_resource(pin)
            except BaseException as error:
                self.error("producer-native-close", error, unknown=True)
            if not self.resource("native-scope").closed:
                _producer_native(self, retired=False)
            if drain_end is not None:
                try:
                    frame.window.sample(cleanup=True)
                    posix._deadline(drain_end)
                except BaseException as error:
                    _producer_native(self, retired=False)
                    self.error("producer-drain-close-fence", error, unknown=True)
        elif frame.native.scope_attempted:
            self.error("producer-native-allocation", origin.OriginError("BOOTSTRAP_PRODUCER_SCOPE_UNKNOWN"), unknown=True)
        else:
            _producer_native(self, retired=True)
        current = _producer_frame(self)
        if current.native.retired and not current.unknown:
            for capture in current.captures:
                try:
                    frame.window.sample(cleanup=True)
                    stream = self.capture_binding(capture)
                    stream.sync()
                    info = stream.verify()
                    stamp = _producer_stamp(info, frame.limits.clock[0])
                    require(stamp[0] == capture.identity and capture.highwater <= stamp[1] <= 67174400,
                            "BOOTSTRAP_PRODUCER_FINAL_CAPTURE_CHANGED")
                    now = _producer_frame(self)
                    _update_producer(self, captures=tuple(row._replace(highwater=stamp[1], final_stamp=stamp,
                        synced=True, verified=True) if row.name == capture.name else row for row in now.captures))
                    frame.window.sample(cleanup=True)
                except BaseException as error:
                    self.error("producer-capture-final", error)
                frame.owner.close_one(capture.stream)
            # A returned capture whose first metadata observation failed is
            # still in resources even if no _ProducerCapture was constructed.
            for name in ("stdout", "stderr"):
                capture_pin = self.resource(name)
                if capture_pin is not None:
                    frame.owner.close_one(capture_pin.value)
        try:
            finalized = frame.window.sample(cleanup=True)
            _producer_native(self, finalized_ns=finalized)
        except BaseException as error:
            self.error("producer-native-final-return", error)

    def writers_closed(self):
        frame = self.check()
        require(frame.native.work_accepted is True and frame.native.retired is True and len(frame.captures) == 2 and
                all(row.final_stamp is not None and row.synced and row.verified for row in frame.captures),
                "BOOTSTRAP_PRODUCER_READ_BEFORE_RETIREMENT")
        for name in ("native-scope", "stdout", "stderr"):
            pin = self.resource(name)
            require(pin is not None and pin.attempted and pin.closed, "BOOTSTRAP_PRODUCER_READ_BEFORE_CLOSE")

    def read_capture(self, capture):
        owner, frame = self.live(), _producer_frame(self)
        self.writers_closed()
        require(frame.phases[-1].name == "READ" and capture in frame.captures and capture.readback is None,
                "BOOTSTRAP_PRODUCER_CAPTURE_READ_REENTRY")
        directory, end = self.handles["phase"], owner.end()
        reader = owner.acquire("reader", lambda: directory.open_file(capture.name + ".log", max_bytes=67174400, deadline=end))
        count, digest = 0, hashlib.sha256()
        try:
            before = reader.initial_info
            require(_producer_stamp(before, frame.limits.clock[0]) == capture.final_stamp,
                    "BOOTSTRAP_PRODUCER_CLOSED_CAPTURE_REPLACED")
            while count < before.size:
                owner.end()
                maximum = min(65536, before.size - count)
                part = reader.read(maximum)
                require(type(part) is bytes and 0 < len(part) <= maximum, "BOOTSTRAP_PRODUCER_CAPTURE_SHORT_READ")
                count += len(part)
                require(count <= 67174400, "BOOTSTRAP_PRODUCER_CAPTURE_OVERFLOW")
                digest.update(part)
                owner.end()
            # Positive read even for a zero-byte original: read(0) is not EOF.
            require(reader.read(1) == b"" and reader.verify() == before and count == before.size,
                    "BOOTSTRAP_PRODUCER_CAPTURE_READ_CHANGED")
            owner.end()
        except BaseException as error:
            self.error("producer-capture-read", error)
        finally:
            owner.close_one(reader)
        self.raise_first()
        observed = frame.window.now()
        current = _producer_frame(self)
        record = (count, digest.hexdigest(), observed, current.local_last)
        _update_producer(self, captures=tuple(row._replace(readback=record) if row.name == capture.name else row
                                              for row in current.captures))
        return record

    def read_canonical(self):
        frame = self.check()
        frame.window.advance("READ")
        self.writers_closed()
        self.state_readback(before=False)
        for capture in _producer_frame(self).captures:
            self.read_capture(capture)
        require(sum(row.readback[0] for row in _producer_frame(self).captures) <= 134348800,
                "BOOTSTRAP_PRODUCER_READBACK_AGGREGATE")
        inputs = self.inputs()
        descriptor, _environment = self.command()
        request_raw = descriptor["requestBytes"].encode("ascii")
        request = producer.parse(request_raw)
        evidence = self.handles["canonical:evidence"]
        directory = self.directory("canonical-invocation", evidence.path / request["id"], parent=evidence)
        for name in ("start", "receipt"):
            raw, binding = self.read_file(directory, name + ".json", producer.LIMIT)
            self.remember("canonical-" + name, directory, name + ".json", raw, producer.LIMIT, binding=binding)
        start_raw, receipt_raw = self.original_file("canonical-start"), self.original_file("canonical-receipt")
        for raw in (start_raw, receipt_raw):
            require(type(producer.parse(raw).get("controllerPid")) is int and
                    producer.parse(raw)["controllerPid"] == frame.native.child_pid,
                    "BOOTSTRAP_PRODUCER_CANONICAL_CONTROLLER_CHANGED")
        observed = producer.observe_canonical(request_raw, inputs.admitted.record, inputs.canonical_raw,
            start_raw, receipt_raw, original_exit_code=frame.native.exit_code)
        observation_raw = producer.encoded(observed)
        self.reread()
        self.state_readback(before=False)
        self.read_originals()
        self.command()
        frame.window.now()
        return request_raw, start_raw, receipt_raw, observation_raw


def _close_producer(parent):
    """No postclose writer/owner: known original cleanup and handler obligations."""
    frame = _producer_frame(parent)
    owner = frame.owner
    if owner is not None:
        _producer_set_state(parent, "CLOSING")
        if frame.phases[-1].name == "WORK":
            try:
                parent.finish_native()
            except BaseException as error:
                parent.error("producer-unlaunched-final", error)
        try:
            parent.roster()
            frame = _producer_frame(parent)
            require(frame.close_roster is None, "BOOTSTRAP_PRODUCER_CLOSE_REENTRY")
            _update_producer(parent, close_roster=tuple((id(pin.row), pin.label, id(pin.value)) for pin in frame.resources))
            owner.close()
        except BaseException as error:
            parent.error("producer-resource-close", error)
    for number, handler in _producer_frame(parent).handlers:
        try:
            signal.signal(number, handler)
            require(signal.getsignal(number) == handler, "BOOTSTRAP_PRODUCER_HANDLER_NOT_RESTORED")
            current = _producer_frame(parent)
            _update_producer(parent, restored=(*current.restored, (number, handler)))
        except BaseException as error:
            parent.error("producer-handler-restore", error)
    try:
        parent.roster()
        frame = _producer_frame(parent)
        require(owner is None or (owner.closed is True and frame.close_roster is not None and
                all(pin.attempted and pin.closed for pin in frame.resources)), "BOOTSTRAP_PRODUCER_CLOSE_INCOMPLETE")
    except BaseException as error:
        parent.error("producer-close-roster", error, unknown=True)


def _run_configuration_producer(parent):
    frame = parent.check()
    require(frame.state == "RESERVED" and frame.owner is None and frame.window is None and frame.result is None,
            "BOOTSTRAP_PRODUCER_RUN_REENTRY")
    _producer_set_state(parent, "STARTING")  # Consumed even if the first clock fails.
    returned = None
    try:
        previous = frame.predecessor.phases[-1][1]
        saved = frame.predecessor.frame
        local = staging._local(time.monotonic())
        _update_producer(parent, local_last=local)
        first = origin.clocks.validate_reading(origin.clocks.observe())
        _update_producer(parent, first=first, last=first.nanoseconds)
        require(staging._clock(first.clock) == staging._clock(saved.originals.clock) and
                first.nanoseconds >= previous.last and local >= previous.local_last,
                "BOOTSTRAP_PRODUCER_PREDECESSOR_CLOCK")
        proposal = allocation.validate_proposal(saved.originals.proposal_raw, saved.originals.admitted,
            saved.originals.responses, saved.originals.invocation, saved.originals.clock, saved.originals.runner_name)
        names, seconds = ("producer-work", "producer-return", "producer-final", "producer-read"), (600, 825, 870, 900)
        ends = tuple(min(origin.integer(first.nanoseconds + maximum * origin.NS), proposal["phaseFencesNs"][name],
                         proposal["proposedJobEndNs"]) for name, maximum in zip(names, seconds))
        require(first.nanoseconds < ends[0] <= ends[1] <= ends[2] <= ends[3], "BOOTSTRAP_PRODUCER_NO_PHASE_INTERVAL")
        local_ends = tuple(origin.wire._directed_deadline(local, maximum, end, first.nanoseconds)
                           for maximum, end in zip(seconds, ends))
        limits = _ProducerLimits(staging._clock(first.clock), first.nanoseconds, local, ends, local_ends)
        window, callback = _ProducerWindow(parent), parent.cancel
        _update_producer(parent, limits=limits, window=window,
            phases=(_ProducerPhase("WORK", first.nanoseconds, local, ends[0], local_ends[0]),))
        parent.window = window
        owner = _ProducerOwner(local_ends[3], window, first=first, cancelled=callback)
        _update_producer(parent, owner=owner,
            owner_bindings=(owner.resources, owner.errors, owner.admissions, owner.local_end, callback), state="RUNNING")
        parent.owner, parent.state = owner, "RUNNING"
        owner.end()
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handler = signal.getsignal(number)
            current = _producer_frame(parent)
            _update_producer(parent, handlers=(*current.handlers, (number, handler)))
            parent.handlers[number] = handler  # Original restore duty BEFORE a potentially partial install.
            signal.signal(number, lambda signum, _frame: _producer_frame(parent).published[3].append(signum))
            owner.end()
        parent.read_originals()
        parent.state_readback(before=True)
        initial = parent.handles["initializer"]
        parent.directory("phase", initial.path / "configuration-parent", parent=initial, create=True)
        parent.admit()
        parent.read_originals()
        parent.state_readback(before=True)
        parent.command(first=True)
        parent.launch()
        returned = parent.read_canonical()
    except BaseException as error:
        parent.error("producer-parent", error)
    finally:
        _close_producer(parent)
    try:
        parent.raise_first()
        frame = parent.check()
        require(frame.owner is not None and frame.owner.closed and frame.owner.original is None and
                not frame.unknown and not frame.owner.unknown and not frame.errors and not frame.foreign and
                frame.handlers == frame.restored and all(pin.attempted and pin.closed for pin in frame.resources) and
                frame.native.work_accepted is True and frame.native.retired is True and
                type(frame.native.exit_code) is int and frame.native.exit_code == 0 and returned is not None,
                "BOOTSTRAP_PRODUCER_FINAL_RETURN_NOT_CLOSED")
        request_raw, start_raw, receipt_raw, observation_raw = returned
        require(start_raw == parent.original_file("canonical-start") and receipt_raw == parent.original_file("canonical-receipt") and
                request_raw == origin.parse(frame.descriptor)["requestBytes"].encode("ascii"),
                "BOOTSTRAP_PRODUCER_RETURN_ORIGINALS_CHANGED")
        # No report paths are followed. The unchanged helper's own disclaimers
        # stay intact alongside separate original enclosing observations.
        producer.validate_observation(producer.parse(observation_raw), request_raw,
            frame.predecessor.frame.originals.admitted.record, frame.predecessor.frame.originals.canonical_raw,
            start_raw, receipt_raw, original_exit_code=frame.native.exit_code)
        parent.cancel()
        closed = frame.window.now(minimum=frame.native.finalized_ns)
        raw = origin.encoded({"schema": 1, "scope": "BOOTSTRAP_CONFIGURATION_PARENT_CLOSED_OBSERVATIONS_V1",
            "reservationSha256": origin.digest(frame.reservation.raw), "descriptorSha256": origin.digest(frame.descriptor),
            "requestSha256": origin.digest(request_raw), "canonicalObservationSha256": origin.digest(observation_raw),
            "window": frame.window.record(), "closedNs": closed, "originalExitCode": frame.native.exit_code,
            "workCompletedNs": frame.native.completed_ns, "outerNativeRetirement": "KNOWN_ORIGINAL_SCOPE_CLOSE",
            "outerStartSha256": origin.digest(parent.original_file("outer-start")),
            "outerBaselineSha256": origin.digest(frame.native.baseline_raw),
            "outerBirthSha256": origin.digest(frame.native.birth_raw), "outerTerminalSha256": origin.digest(frame.native.terminal_raw),
            "outerCaptures": {row.name: {"bytes": row.readback[0], "sha256": row.readback[1], "readNs": row.readback[2]}
                              for row in frame.captures},
            "outerCaptureScope": "TWO_ORIGINAL_STREAMS_OBSERVED_SIZE_NOT_KERNEL_QUOTA_OR_COMPLETE_CUSTODY",
            "canonicalFourLogReportCollection": "NOT_PERFORMED", "dependencyPopulation": "NOT_ATTESTED",
            "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "resourceCount": len(frame.resources),
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False})
        # This final now includes all original callbacks and fresh RAW/LOCAL
        # observations after them. Only passive graph/bookkeeping follows.
        checked = frame.window.now(minimum=closed)
        frame = parent.check()
        require(frame.last == checked and frame.original is None and frame.owner.original is None and
                not frame.unknown and frame.handlers == frame.restored and all(pin.attempted and pin.closed for pin in frame.resources),
                "BOOTSTRAP_PRODUCER_FINAL_BOUNDARY_CHANGED")
        result = ConfigurationPrefix(raw, request_raw, start_raw, receipt_raw, observation_raw, checked, frame.local_last)
        _update_producer(parent, result=result, state="COMPLETE")
        parent.result, parent.state = result, "COMPLETE"
        return result
    except BaseException as error:
        parent.error("producer-final-return", error)
        _producer_set_state(parent, "FAILED")
        frame = _producer_frame(parent)
        if frame.owner is not None and frame.unknown and not any(value is frame.owner for value in QUARANTINE):
            QUARANTINE.append(frame.owner)
        try:
            frame.original.bootstrap_configuration_parent = parent
            frame.original.bootstrap_configuration_resources = tuple((pin.label, pin.value, pin.attempted, pin.closed)
                                                                       for pin in frame.resources)
            frame.original.bootstrap_configuration_custody = "INCOMPLETE" if frame.files else "UNAVAILABLE"
        except BaseException:
            pass
        raise frame.original


def configure_after_entry(transition):
    """Original-call configuration under the dormant producer; no prefix upgrade.

    The private intent exists before the fixed tuple7 reservation call. All
    claims consume failure. COMPLETE predecessor states are never reopened.
    Configuration-only help supplies no ABI/simulator/transcript acceptance,
    populated-cache proof, admitted5400 budget, export/save or custody delivery.
    """
    parent = _claim_producer(transition)
    try:
        _invoke_producer_reservation(parent)
        _capture_producer_predecessor(parent)
        return _run_configuration_producer(parent)
    except BaseException as error:
        if _producer_frame(parent).original is None:
            parent.error("producer-configure-intent", error)
        _producer_set_state(parent, "FAILED")
        raise _producer_frame(parent).original


@dataclass(eq=False)
class _CollectionOrigin:
    """Private in-call binding component; no collection owner or public return.

    Constructing this record cannot claim a transition. The future enclosing
    collector must start its NEW owner under the original cumulative allocation
    before returning collection evidence. This component neither opens files nor
    supplies a transferable ConfigurationPrefix-to-execution upgrade.
    """
    transition: object = field(repr=False)
    state: str = "CLAIMED"
    producer: object = field(default=None, repr=False)
    returned: object = field(default=None, repr=False)
    original: object = field(default=None, repr=False)


_CollectionOriginFrame = namedtuple("_CollectionOriginFrame", "call transition state producer returned "
    "producer_frame records graph graph_pin original", defaults=(None,) * 10)


def _collection_origin_controls():
    """Once-claim BEFORE the original producer call, including failed attempts.

    Registry/function-object identity is finite in-process binding, not a Python
    sandbox or hosted identity. No selector, callback, prefix or file path can
    substitute a producer operation. No lock is held across its invocation.
    """
    operation, lookup, result_lookup = configure_after_entry, _producer_original_call, _producer_original_result
    attempts, frames, lock = {}, {}, threading.Lock()

    def roots():
        require(configure_after_entry is operation and _producer_original_call is lookup and
                _producer_original_result is result_lookup,
                "BOOTSTRAP_COLLECTION_ORIGINAL_OPERATION_CHANGED")
        _producer_original_roots()

    def claim(transition):
        require(type(transition) is NewEntryTransition, "BOOTSTRAP_COLLECTION_TRANSITION_KIND")
        roots()
        with lock:
            require(id(transition) not in attempts, "BOOTSTRAP_COLLECTION_ALREADY_CLAIMED")
            call = _CollectionOrigin(transition)
            attempts[id(transition)] = (transition, call)
            frames[id(call)] = _CollectionOriginFrame(call=call, transition=transition, state="CLAIMED")
        return call

    def frame(call):
        saved = frames.get(id(call))
        require(type(call) is _CollectionOrigin and type(saved) is _CollectionOriginFrame and saved.call is call,
                "BOOTSTRAP_COLLECTION_NOT_CLAIMED")
        row = attempts.get(id(saved.transition))
        require(type(row) is tuple and len(row) == 2 and row[0] is saved.transition and row[1] is call,
                "BOOTSTRAP_COLLECTION_NOT_CLAIMED")
        return saved

    def update(call, **values):
        saved = frame(call)
        frames[id(call)] = saved._replace(**values)
        return frames[id(call)]

    def invoke(call):
        saved = frame(call)
        roots()
        require(saved.state == call.state == "CLAIMED" and call.transition is saved.transition and
                saved.producer is call.producer is None and saved.returned is call.returned is None and
                saved.original is call.original is None, "BOOTSTRAP_COLLECTION_PRODUCER_REENTRY")
        update(call, state="INVOKING")
        call.state = "INVOKING"
        returned = operation(saved.transition)
        # Retain the actual return BEFORE a fallible root/lookup/closed check.
        update(call, returned=returned, state="RETURNED")
        call.returned, call.state = returned, "RETURNED"
        roots()
        producer_call = lookup(saved.transition)
        update(call, producer=producer_call)
        call.producer = producer_call
        return producer_call, returned

    return claim, frame, update, invoke, roots


(_claim_collection_origin, _collection_origin_frame, _update_collection_origin,
 _invoke_collection_producer, _collection_origin_roots) = _collection_origin_controls()
del _collection_origin_controls


def _collection_producer_original_bytes(frame, returned):
    """Pure comparisons of retained records, not native/source rederivation.

    In particular command_request/init_request/host/read_originals are NOT pure
    record checks. The separate original result pin preserves all five exact
    encodings before this comparison; parsing does not mint original bytes.
    """
    files = {row.key: row for row in frame.files}
    require(len(files) == len(frame.files) and {"outer-start", "baseline", "native-start",
            "canonical-start", "canonical-receipt"}.issubset(files), "BOOTSTRAP_COLLECTION_PRODUCER_ORIGINAL_FILES")
    native, descriptor = frame.native, origin.parse(frame.descriptor)
    request = producer.parse(returned.request_raw)
    original = frame.predecessor.frame.originals
    producer.validate_observation(producer.parse(returned.observation_raw), returned.request_raw,
        original.admitted.record, original.canonical_raw, returned.start_raw, returned.receipt_raw,
        original_exit_code=native.exit_code)
    require(type(descriptor["argv"]) is list and type(native.argv) is tuple and tuple(descriptor["argv"]) == native.argv and
            descriptor["role"] == request["host"] == frame.limits.clock[0] and
            descriptor["root"] == request["cwd"] and descriptor["gradleHome"] == request["gradleHome"] and
            descriptor["requestSha256"] == origin.digest(returned.request_raw) and
            descriptor["admissionSha256"] == origin.digest(original.admitted.record) and
            descriptor["canonicalContextSha256"] == origin.digest(original.canonical_raw) and
            descriptor["requestBytes"].encode("ascii") == returned.request_raw and
            all(type(producer.parse(raw).get("controllerPid")) is int and
                producer.parse(raw)["controllerPid"] == native.child_pid for raw in (returned.start_raw, returned.receipt_raw)),
            "BOOTSTRAP_COLLECTION_PRODUCER_DESCRIPTOR_BINDING")
    environment = dict(frame.environment)
    outer = {"schema": 1, "scope": "BOOTSTRAP_CONFIGURATION_PARENT_PRELAUNCH_V1",
        "contextSha256": descriptor["canonicalContextSha256"], "argv": descriptor["argv"], "cwd": descriptor["root"],
        "role": frame.limits.clock[0], "job": request["jobId"], "invocation": frame.outer_invocation,
        "state": descriptor["state"], "home": request["gradleHome"],
        "inheritedContext": {name: environment[name] for name in query._CONTEXT}, "startedNs": frame.limits.first,
        "workEndNs": frame.limits.ends[0], "finalEndNs": frame.limits.ends[2], "exitCode": None,
        "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"}
    require(files["outer-start"].raw == origin.encoded(outer) and files["baseline"].raw == native.baseline_raw,
            "BOOTSTRAP_COLLECTION_PRODUCER_OUTER_START_CHANGED")
    scope = next(row.value for row in frame.resources if row.label == "native-scope")
    if frame.limits.clock[0] == "windows-x64":
        actual_scope, expected_scope = (scope.job_id, scope.invocation), (outer["job"], outer["invocation"])
    else:
        actual_scope = (scope.job, scope.invocation, scope.state, scope.home)
        expected_scope = (outer["job"], outer["invocation"], outer["state"], outer["home"])
    require(all(type(value) is str for value in actual_scope) and actual_scope == expected_scope,
            "BOOTSTRAP_COLLECTION_PRODUCER_SCOPE_CHANGED")
    supplier = frame.query[0]
    phase = next(row for row in frame.handles if row[0] == "phase")
    require(type(supplier.root) is type(Path(descriptor["root"])) and supplier.root == Path(descriptor["root"]) and
            type(supplier.path) is type(phase[2]) and supplier.path == phase[2] / "admission",
            "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_LOCATION_CHANGED")
    leader, birth, terminal = (origin.parse(raw) for raw in (native.leader_raw, native.birth_raw, native.terminal_raw))
    baseline = baseline_record(native.baseline_raw, frame.limits.clock[0])
    preparer = closed_lifetime(origin.parse(native.preparer_raw), frame.limits.clock[0])
    native_record(birth, outer, leader, list(native.argv), terminal=False)
    native_record(terminal, outer, leader, list(native.argv))
    require(leader["pid"] == native.child_pid and preparer["pid"] != native.child_pid and
            birth["launches"] == terminal["launches"], "BOOTSTRAP_COLLECTION_PRODUCER_NATIVE_RECORD_CHANGED")
    if baseline["baseline"] is not None:
        identity = lifetime(leader, frame.limits.clock[0])
        require(list(identity[:4] if frame.limits.clock[0].startswith("macos-") else identity) not in baseline["baseline"],
                "BOOTSTRAP_COLLECTION_PRODUCER_PREEXISTING_LEADER")
    born = origin.parse(files["native-start"].raw)
    require(set(born) == {"ownership", "leader", "preparerIdentity", "observedNs"} and
            origin.encoded(born["ownership"]) == native.birth_raw and origin.encoded(born["leader"]) == native.leader_raw and
            origin.encoded(born["preparerIdentity"]) == native.preparer_raw and
            native.launch_minimum <= origin.integer(born["observedNs"]) <= native.completed_ns,
            "BOOTSTRAP_COLLECTION_PRODUCER_NATIVE_START_CHANGED")
    value = origin.parse(returned.raw)
    closed = origin.integer(value.get("closedNs"))
    require(max(native.finalized_ns, *(row.readback[2] for row in frame.captures)) <= closed <= frame.last,
            "BOOTSTRAP_COLLECTION_PRODUCER_CLOSED_CHRONOLOGY")
    expected = {"schema": 1, "scope": "BOOTSTRAP_CONFIGURATION_PARENT_CLOSED_OBSERVATIONS_V1",
        "reservationSha256": origin.digest(frame.reservation.raw), "descriptorSha256": origin.digest(frame.descriptor),
        "requestSha256": origin.digest(returned.request_raw), "canonicalObservationSha256": origin.digest(returned.observation_raw),
        "window": {"clock": origin.clock_value(frame.first.clock), "firstNs": frame.limits.first,
            "globalEndsNs": dict(zip(("WORK", "RETURN", "FINAL", "READ"), frame.limits.ends)),
            "phases": [{"phase": phase.name, "startedNs": phase.started, "endNs": phase.end} for phase in frame.phases],
            "budgetAcceptance": "NOT_ADMITTED"}, "closedNs": closed, "originalExitCode": native.exit_code,
        "workCompletedNs": native.completed_ns, "outerNativeRetirement": "KNOWN_ORIGINAL_SCOPE_CLOSE",
        "outerStartSha256": origin.digest(files["outer-start"].raw), "outerBaselineSha256": origin.digest(native.baseline_raw),
        "outerBirthSha256": origin.digest(native.birth_raw), "outerTerminalSha256": origin.digest(native.terminal_raw),
        "outerCaptures": {row.name: {"bytes": row.readback[0], "sha256": row.readback[1], "readNs": row.readback[2]}
                          for row in frame.captures},
        "outerCaptureScope": "TWO_ORIGINAL_STREAMS_OBSERVED_SIZE_NOT_KERNEL_QUOTA_OR_COMPLETE_CUSTODY",
        "canonicalFourLogReportCollection": "NOT_PERFORMED", "dependencyPopulation": "NOT_ATTESTED",
        "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "resourceCount": len(frame.resources),
        "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
        "exportSaveAuthority": False}
    require(returned.raw == origin.encoded(expected), "BOOTSTRAP_COLLECTION_PRODUCER_CLOSED_RECORD_CHANGED")


def _collection_closed_producer(parent, returned):
    """Passive closed-return binding: NEVER call producer.check/roster/owners.

    Those live methods can update a frame or record errors. Refusal here cannot
    reopen, advance, cancel or assume cleanup of the already returned producer.
    No current clock, file, provider or native observation occurs here.
    """
    require(type(parent) is _ProducerParent and type(returned) is ConfigurationPrefix,
            "BOOTSTRAP_COLLECTION_PRODUCER_RETURN_KIND")
    frame = _producer_frame(parent)
    require(_producer_original_result(parent).frame is frame, "BOOTSTRAP_COLLECTION_PRODUCER_NOT_ORIGINAL_RESULT")
    _producer_predecessor_checked(parent)
    require(frame.state == parent.state == "COMPLETE" and frame.result is parent.result is returned and
            frame.transition is parent.transition and frame.original is parent.original is None and
            frame.unknown is parent.unknown is False and frame.errors == () and frame.foreign == () and
            type(frame.published) is tuple and len(frame.published) == 4 and
            parent.handles is frame.published[0] and parent.records is frame.published[1] and
            parent.handlers is frame.published[2] and parent.cancelled is frame.published[3] and
            type(parent.cancelled) is list and not parent.cancelled,
            "BOOTSTRAP_COLLECTION_PRODUCER_NOT_COMPLETE")
    owner, window, bindings = frame.owner, frame.window, frame.owner_bindings
    require(type(owner) is _ProducerOwner and type(window) is _ProducerWindow and
            type(bindings) is tuple and len(bindings) == 5 and type(frame.limits) is _ProducerLimits and
            parent.owner is owner and parent.window is window and window.call is parent and
            _producer_owner_frame(owner) is frame and _producer_window_frame(window) is frame and
            owner.closed is True and owner.original is None and owner.unknown is False and
            owner.resources is bindings[0] and owner.errors is bindings[1] and owner.admissions is bindings[2] and
            owner.errors == [] and type(owner.local_end) is type(bindings[3]) and owner.local_end == bindings[3] and
            owner.cancelled is bindings[4] and owner.first is frame.first and owner.fence is window and
            owner.work_limit is owner.final_limit is None and owner.early_last == frame.limits.first and
            frame.first.nanoseconds == frame.limits.first and staging._clock(frame.first.clock) == frame.limits.clock and
            owner.local_end == frame.limits.local_ends[-1],
            "BOOTSTRAP_COLLECTION_PRODUCER_OWNER_NOT_CLOSED")
    require(type(frame.resources) is tuple and type(owner.resources) is list and
            len(frame.resources) == len(owner.resources) <= 4096 and type(frame.close_roster) is tuple and
            len(frame.close_roster) == len(frame.resources) and frame.handlers == frame.restored and
            tuple(parent.handlers.items()) == frame.handlers and
            len({id(row.row) for row in frame.resources}) == len(frame.resources) and
            len({id(row.value) for row in frame.resources}) == len(frame.resources),
            "BOOTSTRAP_COLLECTION_PRODUCER_CLOSE_ROSTER")
    for row, pin, closed in zip(owner.resources, frame.resources, frame.close_roster):
        require(type(pin) is _ProducerResource and type(row) is dict and
                set(row) == {"label", "owner", "attempted", "closed"} and row is pin.row and
                type(pin.label) is str and pin.label in
                ("directory", "reader", "writer", "stdout", "stderr", "native-scope", "source-directory") and
                type(row["label"]) is str and row["label"] == pin.label and row["owner"] is pin.value and
                type(pin.value) is pin.kind and row["attempted"] is row["closed"] is pin.attempted is pin.closed is True and
                closed == (id(row), pin.label, id(pin.value)), "BOOTSTRAP_COLLECTION_PRODUCER_CLOSE_ROSTER")
    required = {name: tuple(row for row in frame.resources if row.label == name)
                for name in ("native-scope", "stdout", "stderr")}
    require(all(len(rows) == 1 for rows in required.values()), "BOOTSTRAP_COLLECTION_PRODUCER_REQUIRED_CLOSE")
    require(type(frame.handles) is tuple and type(frame.files) is tuple and
            all(type(row) is tuple and len(row) == 4 for row in frame.handles) and
            all(type(row) is _ProducerFile and type(row.raw) is bytes and type(row.binding_raw) is bytes for row in frame.files) and
            tuple(parent.handles.items()) == tuple((row[0], row[1]) for row in frame.handles) and
            tuple(parent.records.items()) == tuple((row.key, row.raw) for row in frame.files),
            "BOOTSTRAP_COLLECTION_PRODUCER_RECORD_ROSTER")
    for _key, directory, path, identity in frame.handles:
        require(type(directory.path) is type(path) and directory.path == path and tuple(directory.identity) == identity,
                "BOOTSTRAP_COLLECTION_PRODUCER_DIRECTORY_CHANGED")
    for row in frame.files:
        require(type(row.directory.path) is type(row.path) and row.directory.path == row.path and
                tuple(row.directory.identity) == row.identity,
                "BOOTSTRAP_COLLECTION_PRODUCER_FILE_DIRECTORY_CHANGED")
    require(type(frame.phases) is tuple and len(frame.phases) == 4 and
            all(type(phase) is _ProducerPhase for phase in frame.phases) and
            tuple(phase.name for phase in frame.phases) == ("WORK", "RETURN", "FINAL", "READ") and
            type(frame.last) is int and frame.last == returned.checked_ns and
            type(returned.checked_ns) is int and origin.integer(frame.last) < frame.phases[-1].end and
            type(frame.local_last) in (int, float) and math.isfinite(frame.local_last) and
            type(returned.checked_local) is type(frame.local_last) and
            staging._local(frame.local_last) == returned.checked_local < frame.phases[-1].local_end,
            "BOOTSTRAP_COLLECTION_PRODUCER_FINAL_HIGHWATER")
    require(type(frame.limits.ends) is tuple and type(frame.limits.local_ends) is tuple and
            len(frame.limits.ends) == len(frame.limits.local_ends) == 4 and
            all(type(value) is int for value in frame.limits.ends) and
            all(type(value) in (int, float) and math.isfinite(value) for value in frame.limits.local_ends) and
            frame.limits.first < frame.limits.ends[0] <= frame.limits.ends[1] <= frame.limits.ends[2] <= frame.limits.ends[3] and
            staging._local(frame.limits.local_start) < frame.limits.local_ends[0] <= frame.limits.local_ends[1] <=
                frame.limits.local_ends[2] <= frame.limits.local_ends[3], "BOOTSTRAP_COLLECTION_PRODUCER_PHASE_LIMITS")
    previous_raw, previous_local = frame.limits.first, frame.limits.local_start
    for index, (phase, maximum) in enumerate(zip(frame.phases, (600, 225, 45, 30))):
        require(previous_raw <= origin.integer(phase.started) <= frame.last and
                previous_local <= staging._local(phase.local_started) <= frame.local_last and
                phase.started < origin.integer(phase.end) <= min(frame.limits.ends[index], phase.started + maximum * origin.NS) and
                phase.local_started < staging._local(phase.local_end) <=
                    min(frame.limits.local_ends[index], phase.local_started + maximum),
                "BOOTSTRAP_COLLECTION_PRODUCER_PHASE_CHRONOLOGY")
        previous_raw, previous_local = phase.started, phase.local_started
    require(frame.phases[0] == _ProducerPhase("WORK", frame.limits.first, frame.limits.local_start,
                frame.limits.ends[0], frame.limits.local_ends[0]) and
            frame.phases[-1].started < frame.phases[-2].end and
            frame.phases[-1].local_started < frame.phases[-2].local_end,
            "BOOTSTRAP_COLLECTION_PRODUCER_PHASE_CHRONOLOGY")
    native = frame.native
    require(type(native) is _ProducerNative and native.scope_attempted is native.launch_attempted is True and
            native.work_accepted is native.drain_attempted is native.retired is True and
            native.child is not None and type(native.child) is native.child_kind and
            type(native.child_pid) is int and 0 < native.child_pid <= (1 << 32) - 1 and
            type(native.child.pid) is int and native.child.pid == native.child_pid and
            native.child.stdout is native.child.stderr is None and
            type(native.exit_code) is int and native.exit_code == 0 and
            frame.limits.first <= origin.integer(native.launch_minimum) <= origin.integer(native.completed_ns) <=
                frame.phases[1].started and native.completed_ns < frame.phases[0].end and
            frame.phases[2].started <= origin.integer(native.finalized_ns) <= frame.phases[3].started and
            native.finalized_ns < frame.phases[2].end and
            all(type(raw) is bytes and 0 < len(raw) <= 4194304 for raw in
                (native.baseline_raw, native.preparer_raw, native.birth_raw, native.leader_raw,
                 native.survivors_raw, native.terminal_raw)) and
            origin.parse(native.survivors_raw) == {"survivors": []} and
            origin.parse(native.terminal_raw).get("discoveryErrors") == [] and
            frame.cancellation_attempted is False and frame.cancellation_raw is None and frame.cancellation_stamps == () and
            frame.query_attempted is True and type(frame.query_returned) is tuple and len(frame.query_returned) == 3 and
            frame.query_returned[0] is True and frame.limits.first <= origin.integer(frame.query_returned[1]) <= native.launch_minimum and
            frame.limits.local_start <= staging._local(frame.query_returned[2]) <= frame.local_last,
            "BOOTSTRAP_COLLECTION_PRODUCER_ORIGINAL_RETIREMENT")
    require(type(frame.query) is tuple and len(frame.query) == 5, "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_NOT_CLOSED")
    supplier, kind, pair, work, final = frame.query
    require(type(supplier) is kind and supplier.closed is True and supplier.unknown is supplier.failed is supplier.active is False and
            supplier.first_error is supplier.cancellation is None and type(supplier.errors) is list and not supplier.errors and
            type(supplier.resources) is list and type(supplier.records) is list and type(supplier.readbacks) is list and
            all(type(row) is dict and set(row) == {"label", "owner", "closeAttempted", "closed"} and
                type(row["label"]) is str and row["owner"] is not None and
                row["closeAttempted"] is row["closed"] is True for row in supplier.resources) and
            type(pair) is tuple and len(pair) == 2 and supplier._owner_deadlines is pair and
            staging._local(pair[0]) <= staging._local(pair[1]) <= frame.phases[0].local_end and
            frame.query_returned[2] < frame.phases[0].local_end and
            origin.integer(work) <= origin.integer(final) <= frame.phases[0].end and frame.query_returned[1] < final,
            "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_NOT_CLOSED")
    # The supplier's fixed pair governed its own finalizer operations. The later
    # outer query_returned sample is NOT that supplier's final LOCAL sample: the
    # original producer bounds it by RAW final and the enclosing WORK LOCAL cap.
    # Pinning terminal facts cannot invent a missing earlier observation.
    query_required = {name: tuple(row for row in supplier.resources if row["label"] == name)
                      for name in ("private-root", "query-home", "session-result.json")}
    require(all(len(rows) == 1 for rows in query_required.values()) and
            query_required["private-root"][0]["owner"] is supplier.private and
            query_required["query-home"][0]["owner"] is supplier.home and
            len({id(row) for row in supplier.resources}) == len(supplier.resources) and
            len({id(row["owner"]) for row in supplier.resources}) == len(supplier.resources),
            "BOOTSTRAP_COLLECTION_PRODUCER_QUERY_ROSTER")
    require(type(frame.captures) is tuple and len(frame.captures) == 2 and
            all(type(row) is _ProducerCapture for row in frame.captures) and
            tuple(row.name for row in frame.captures) == ("stdout", "stderr") and
            all(row.final_stamp is not None and row.synced is row.verified is True and
                type(row.readback) is tuple and len(row.readback) == 4 and
                type(row.readback[0]) is int and 0 <= row.readback[0] <= 67174400 and
                type(row.readback[1]) is str and re.fullmatch(r"[0-9a-f]{64}", row.readback[1]) and
                frame.phases[3].started <= origin.integer(row.readback[2]) <= frame.last and
                frame.phases[3].local_started <= staging._local(row.readback[3]) <= frame.local_last
                for row in frame.captures), "BOOTSTRAP_COLLECTION_PRODUCER_CAPTURE_NOT_READ")
    outputs = tuple(row for row in frame.handles if row[0] == "capture-output")
    require(len(outputs) == 1, "BOOTSTRAP_COLLECTION_PRODUCER_CAPTURE_DIRECTORY")
    for capture in frame.captures:
        stream = capture.stream
        require(stream is required[capture.name][0].value and type(capture.identity) is tuple and
                type(capture.final_stamp) is tuple and len(capture.final_stamp) ==
                    (3 if frame.limits.clock[0] == "windows-x64" else 4) and
                capture.final_stamp[0] == capture.identity and type(capture.final_stamp[1]) is int and
                type(capture.highwater) is int and capture.highwater == capture.final_stamp[1] == capture.readback[0] and
                type(stream.path) is type(outputs[0][2]) and stream.path == outputs[0][2] / (capture.name + ".log"),
                "BOOTSTRAP_COLLECTION_PRODUCER_CAPTURE_BINDING")
        maximum, end = ((stream.max_bytes, stream._deadline) if frame.limits.clock[0] == "windows-x64" else
                        (stream.maximum, stream.deadline))
        require(type(maximum) is int and maximum == 67174400 and type(end) is type(frame.limits.local_ends[2]) and
                end == frame.limits.local_ends[2], "BOOTSTRAP_COLLECTION_PRODUCER_CAPTURE_BOUNDS")
    require(frame.captures[0].identity != frame.captures[1].identity and
            frame.captures[0].readback[2] <= frame.captures[1].readback[2] and
            frame.captures[0].readback[3] <= frame.captures[1].readback[3],
            "BOOTSTRAP_COLLECTION_PRODUCER_CAPTURE_CHRONOLOGY")
    for key, raw in (("canonical-start", returned.start_raw), ("canonical-receipt", returned.receipt_raw)):
        matches = tuple(row for row in frame.files if row.key == key)
        require(len(matches) == 1 and type(raw) is bytes and matches[0].raw == raw,
                "BOOTSTRAP_COLLECTION_PRODUCER_ORIGINAL_BYTES")
    require(type(returned.raw) is bytes and type(returned.observation_raw) is bytes and
            type(returned.request_raw) is bytes and type(frame.descriptor) is bytes and
            origin.parse(frame.descriptor)["requestBytes"].encode("ascii") == returned.request_raw,
            "BOOTSTRAP_COLLECTION_PRODUCER_REQUEST_CHANGED")
    require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
            "BOOTSTRAP_COLLECTION_PRIOR_UNKNOWN")
    _collection_producer_original_bytes(frame, returned)
    return frame


def _capture_producer_graph(frame, selected):
    """Finite passive snapshot, including witnesses rather than trusting them.

    The original publication excludes the producer parent's dictionary because
    its result/state bookkeeping has not returned yet. All selected query,
    stream, owner and older witness containers are already final. The later
    collection snapshot additionally selects the returned parent. Neither
    snapshot reopens or invokes a closed resource, callback or clock.
    """
    # The staging graph intentionally treats producer records as opaque. Pin
    # each producer dictionary pointer explicitly and flatten the exact immutable
    # producer tuple families; do not silently rely on unknown-type traversal.
    tuples = (_ProducerFrame, _ProducerPredecessor, _ProducerLimits, _ProducerNative,
              _ProducerPhase, _ProducerResource, _ProducerFile, _ProducerCapture, _StagingSequenceFrame)
    special = (_ProducerOwner, _ProducerWindow, ConfigurationPrefix, _StagingSequence, _StagingClosedGraph)
    records, roots, seen = [], [], set()
    pending = [frame, *selected]
    while pending:
        value = pending.pop()
        kind = type(value)
        if kind in (type(None), bool, int, float, str, bytes, signal.Signals):
            continue
        if id(value) in seen:
            continue
        seen.add(id(value))
        require(len(seen) <= 10000, "BOOTSTRAP_COLLECTION_GRAPH_LIMIT")
        if kind in special or any(value is item for item in selected):
            original = object.__getattribute__(value, "__dict__")
            records.append((value, kind, original))
            roots.append(original)
            pending.append(original)
        elif kind in tuples:
            flattened = tuple(value)  # Only the explicitly named exact tuple families.
            roots.append(flattened)
            pending.extend(flattened)
        elif kind is dict:
            pending.extend(value.values())
        elif kind in (list, tuple, _StagingFrame, _StagingLimits, _CustodyRequestPin):
            pending.extend(value)
        # No generic __dict__/iterable/native backend introspection. Old graph
        # dictionaries/nodes/paths are found through these finite typed roots.
    records = tuple(records)
    graph = _StagingClosedGraph.capture(*roots)
    paths = tuple((directory, type(directory), path, identity) for _key, directory, path, identity in frame.handles)
    paths += tuple((row.directory, type(row.directory), row.path, row.identity) for row in frame.files)
    graph = _StagingClosedGraph(graph.nodes, (*graph.paths, *paths))
    graph.checked()
    return records, graph


def _check_producer_result_graph(pin):
    require(type(pin.graph) is _StagingClosedGraph and type(pin.graph_pin) is tuple and len(pin.graph_pin) == 3 and
            object.__getattribute__(pin.graph, "__dict__") is pin.graph_pin[0] and
            set(pin.graph_pin[0]) == {"nodes", "paths"} and pin.graph.nodes is pin.graph_pin[1] and
            pin.graph.paths is pin.graph_pin[2], "BOOTSTRAP_PRODUCER_RESULT_GRAPH_CHANGED")
    for value, kind, original in pin.records:
        require(type(value) is kind and object.__getattribute__(value, "__dict__") is original,
                "BOOTSTRAP_PRODUCER_RESULT_DICTIONARY_CHANGED")
    pin.graph.checked()


def _capture_collection_producer(parent, returned):
    frame = _collection_closed_producer(parent, returned)
    selected = (parent, frame.owner, frame.window, returned, frame.query[0], *(row.stream for row in frame.captures))
    records, graph = _capture_producer_graph(frame, selected)
    require(_collection_closed_producer(parent, returned) is frame, "BOOTSTRAP_COLLECTION_PRODUCER_FRAME_CHANGED")
    return frame, records, graph


def _checked_collection_origin(call):
    """Passive read of this exact claim, not a live collection/next-phase permit."""
    saved = _collection_origin_frame(call)
    _collection_origin_roots()
    require(call.transition is saved.transition and call.state == saved.state and
            call.producer is saved.producer and call.returned is saved.returned and call.original is saved.original,
            "BOOTSTRAP_COLLECTION_ORIGIN_CHANGED")
    require(saved.state == "BOUND" and saved.original is None and saved.graph is not None,
            "BOOTSTRAP_COLLECTION_ORIGIN_NOT_BOUND")
    require(type(saved.graph) is _StagingClosedGraph and type(saved.graph_pin) is tuple and len(saved.graph_pin) == 3 and
            object.__getattribute__(saved.graph, "__dict__") is saved.graph_pin[0] and
            set(saved.graph_pin[0]) == {"nodes", "paths"} and saved.graph.nodes is saved.graph_pin[1] and
            saved.graph.paths is saved.graph_pin[2], "BOOTSTRAP_COLLECTION_GRAPH_CHANGED")
    require(_producer_original_call(saved.transition) is saved.producer and
            _collection_closed_producer(saved.producer, saved.returned) is saved.producer_frame,
            "BOOTSTRAP_COLLECTION_PRODUCER_FRAME_CHANGED")
    for value, kind, original in saved.records:
        require(type(value) is kind and object.__getattribute__(value, "__dict__") is original,
                "BOOTSTRAP_COLLECTION_PRODUCER_DICTIONARY_CHANGED")
    saved.graph.checked()
    return saved


def _begin_collection_after_entry(transition):
    """Internal binding component, not itself a file owner or collection leaf.

    Its original-call claim encloses the collection parent; it cannot be
    reconstructed from returned data. The parent supplies fresh readmission.
    BOUND is NOT collection or execution acceptance.
    """
    call = _claim_collection_origin(transition)
    try:
        parent, returned = _invoke_collection_producer(call)
        frame, records, graph = _capture_collection_producer(parent, returned)
        graph_pin = (object.__getattribute__(graph, "__dict__"), graph.nodes, graph.paths)
        _update_collection_origin(call, state="BOUND", producer_frame=frame, records=records, graph=graph, graph_pin=graph_pin)
        call.state = "BOUND"
        _checked_collection_origin(call)
        return call
    except BaseException as error:
        saved = _collection_origin_frame(call)
        first = error if saved.original is None else saved.original
        _update_collection_origin(call, state="FAILED", original=first)
        call.state, call.original = "FAILED", first
        try:
            first.bootstrap_collection_origin = call
        except BaseException:
            pass  # Private claim retains the first error/actual returned objects.
        raise first


@dataclass(frozen=True)
class CollectionPrefix:
    """Closed file-collection observations, never transferable execution rights."""
    raw: bytes = field(repr=False)
    leaf: object = field(repr=False)
    manifest_raw: bytes = field(repr=False)
    checked_ns: int
    checked_local: float


_CollectionPhaseLimits = namedtuple("_CollectionPhaseLimits", "clock first local_start ends local_ends")
_CollectionPhaseStep = namedtuple("_CollectionPhaseStep", "name started local_started end local_end")
_CollectionPhaseResource = namedtuple("_CollectionPhaseResource", "row label value kind attempted closed")
_CollectionPhaseFile = namedtuple("_CollectionPhaseFile", "key directory path identity name maximum raw binding_raw")
_CollectionPhaseQueryOrigin = namedtuple("_CollectionPhaseQueryOrigin", "dictionary root path roots resources records readbacks")
_CollectionPhaseQueryBefore = namedtuple("_CollectionPhaseQueryBefore", "rows readbacks graph graph_pin")
_CollectionPhaseResultPin = namedtuple("_CollectionPhaseResultPin", "frame result dictionary fields graph graph_pin")
_CollectionPhaseFrame = namedtuple("_CollectionPhaseFrame", "call transition state binding bound predecessor published "
    "first limits window owner owner_bindings last local_last phases resources foreign handles files handlers restored "
    "close_roster original unknown errors query_attempted query query_returned query_pin borrowed source_pin "
    "manifest_attempted manifest_pin leaf_attempted leaf_originals leaf_originals_pin leaf leaf_pin leaf_began "
    "pending_raw result owner_closed expired_closes query_result query_errors result_pin source_attempted "
    "query_origin query_preclose query_final_attempted", defaults=(None,) * 50)


def _collection_phase_controls():
    """The outer intent exists BEFORE the original binding/producer call.

    A returned BOUND object, constructor or copied prefix is not an entry point.
    These finite same-process pins are not a sandbox against code replacement.
    """
    begin, checked = _begin_collection_after_entry, _checked_collection_origin
    module, operation = collect_files, collect_files.collect_inventory
    input_kind, result_kind = collect_files.FileOriginals, collect_files.FileCollectionEvidence
    capture, inputs, grammar = collect_files._capture, collect_files._Inputs, collect_files.inventory
    describe = grammar.describe_inventory
    attempts, frames, owners, windows_by_id, lock = {}, {}, {}, {}, threading.Lock()
    results, result_attempted = {}, set()

    def roots():
        require(_begin_collection_after_entry is begin and _checked_collection_origin is checked and
                collect_files is module and collect_files.collect_inventory is operation and
                collect_files.FileOriginals is input_kind and collect_files.FileCollectionEvidence is result_kind and
                collect_files._capture is capture and collect_files._Inputs is inputs and
                collect_files.inventory is grammar and grammar.describe_inventory is describe,
                "BOOTSTRAP_COLLECTION_PHASE_OPERATION_CHANGED")
        _collection_origin_roots()

    def claim(transition):
        require(type(transition) is NewEntryTransition, "BOOTSTRAP_COLLECTION_PHASE_TRANSITION_KIND")
        roots()
        with lock:
            require(id(transition) not in attempts, "BOOTSTRAP_COLLECTION_PHASE_ALREADY_CLAIMED")
            call = _CollectionPhaseParent(transition)
            attempts[id(transition)] = (transition, call)
            frames[id(call)] = _CollectionPhaseFrame(call=call, transition=transition, state="CLAIMED",
                published=(call.handles, call.records, call.handlers, call.cancelled), phases=(), resources=(),
                foreign=(), handles=(), files=(), handlers=(), restored=(), unknown=False, errors=(),
                query_attempted=False, manifest_attempted=False, leaf_attempted=False, owner_closed=False,
                expired_closes=(), query_errors=(), source_attempted=False, query_final_attempted=False)
        return call

    def frame(call):
        saved = frames.get(id(call))
        require(type(call) is _CollectionPhaseParent and type(saved) is _CollectionPhaseFrame and saved.call is call,
                "BOOTSTRAP_COLLECTION_PHASE_NOT_CLAIMED")
        row = attempts.get(id(saved.transition))
        require(type(row) is tuple and len(row) == 2 and row[0] is saved.transition and row[1] is call,
                "BOOTSTRAP_COLLECTION_PHASE_NOT_CLAIMED")
        return saved

    def update(call, **values):
        saved = frame(call)
        if "owner" in values:
            require(saved.owner is None and type(values["owner"]) is _CollectionPhaseOwner,
                    "BOOTSTRAP_COLLECTION_PHASE_OWNER_REENTRY")
            owners[id(values["owner"])] = call
        if "window" in values:
            require(saved.window is None and type(values["window"]) is _CollectionPhaseWindow,
                    "BOOTSTRAP_COLLECTION_PHASE_WINDOW_REENTRY")
            windows_by_id[id(values["window"])] = call
        frames[id(call)] = saved._replace(**values)
        return frames[id(call)]

    def invoke(call):
        saved = frame(call)
        roots()
        require(saved.state == call.state == "CLAIMED" and call.transition is saved.transition and
                saved.binding is None and saved.original is call.original is None,
                "BOOTSTRAP_COLLECTION_PHASE_BEGIN_REENTRY")
        update(call, state="BINDING")
        call.state = "BINDING"
        returned = begin(saved.transition)  # No claim lock is held across execution.
        update(call, binding=returned, state="BINDING_RETURNED")
        call.state = "BINDING_RETURNED"  # Actual return retained before lookup/checks.
        roots()
        bound = checked(returned)
        require(bound.transition is saved.transition, "BOOTSTRAP_COLLECTION_PHASE_FOREIGN_BINDING")
        borrowed = frozenset(id(row[0]) for row in bound.graph.nodes) | frozenset(
            id(row[0]) for row in bound.records) | frozenset((id(returned), id(bound.producer), id(bound.returned)))
        update(call, bound=bound, predecessor=bound.producer_frame.predecessor, borrowed=borrowed, state="BOUND")
        call.state = "BOUND"

    def owner_frame(owner):
        saved = frame(owners.get(id(owner)))
        require(type(owner) is _CollectionPhaseOwner and saved.owner is owner,
                "BOOTSTRAP_COLLECTION_PHASE_OWNER_NOT_BOUND")
        return saved

    def window_frame(window):
        saved = frame(windows_by_id.get(id(window)))
        require(type(window) is _CollectionPhaseWindow and saved.window is window and window.call is saved.call,
                "BOOTSTRAP_COLLECTION_PHASE_WINDOW_NOT_BOUND")
        return saved

    def leaf(call, originals):
        saved = call.check()
        roots()
        require(saved.state == "RUNNING" and saved.phases[-1].name == "WORK" and not saved.leaf_attempted and
                saved.manifest_pin is not None, "BOOTSTRAP_COLLECTION_PHASE_LEAF_REENTRY")
        update(call, leaf_attempted=True)  # Failure never earns a second copy.
        captured = capture(originals)
        update(call, leaf_originals=originals, leaf_originals_pin=captured)
        began = saved.window.now()
        update(call, leaf_began=(began, frame(call).local_last))
        returned = operation(saved.owner, originals)
        update(call, leaf=returned)  # Even malformed returns precede any fallible validation.
        require(type(returned) is result_kind, "BOOTSTRAP_COLLECTION_PHASE_LEAF_KIND")
        dictionary = object.__getattribute__(returned, "__dict__")
        require(set(dictionary) == {"raw", "inventory_raw", "local_started", "checked_local"},
                "BOOTSTRAP_COLLECTION_PHASE_LEAF_FIELDS")
        pin = (dictionary, returned.raw, returned.inventory_raw, returned.local_started, returned.checked_local)
        require(all(type(raw) is bytes and 0 < len(raw) <= 4194304 for raw in pin[1:3]),
                "BOOTSTRAP_COLLECTION_PHASE_LEAF_BYTES")
        staging._local(pin[3])
        staging._local(pin[4])
        update(call, leaf_pin=pin)
        call.check()
        call.validate_leaf()
        saved.window.now()
        current = call.check()
        require(current.leaf_began[1] <= pin[3] <= pin[4] <= current.local_last,
                "BOOTSTRAP_COLLECTION_PHASE_LEAF_RETURN_LOCAL")
        return returned

    def publish(call, returned):
        # Called only AFTER the last parent.check() and public COMPLETE/result
        # bookkeeping. check() can replace the private frame even when closed.
        saved = frame(call)
        require(id(call) not in result_attempted, "BOOTSTRAP_COLLECTION_PHASE_PUBLICATION_REENTRY")
        result_attempted.add(id(call))  # A failed capture never earns a new baseline.
        roots()
        require(_collection_phase_closed_return(call, returned) is saved,
                "BOOTSTRAP_COLLECTION_PHASE_PUBLICATION_CHANGED")
        dictionary = object.__getattribute__(returned, "__dict__")
        fields = tuple(dictionary[name] for name in ("raw", "leaf", "manifest_raw", "checked_ns", "checked_local"))
        graph = _CollectionReturnGraph.capture(saved)
        pin = _CollectionPhaseResultPin(saved, returned, dictionary, fields, graph,
            (object.__getattribute__(graph, "__dict__"), graph.nodes, graph.paths))
        # The registry is deliberately outside its own captured graph. No
        # post-publication parent/frame mutation, file I/O or clock observation.
        results[id(call)] = pin
        return original_result(call)

    def original_call(transition):
        roots()
        require(type(transition) is NewEntryTransition, "BOOTSTRAP_COLLECTION_PHASE_TRANSITION_KIND")
        row = attempts.get(id(transition))
        require(type(row) is tuple and len(row) == 2 and row[0] is transition and
                type(row[1]) is _CollectionPhaseParent and frame(row[1]).transition is transition,
                "BOOTSTRAP_COLLECTION_PHASE_NOT_ORIGINAL_CALL")
        return row[1]

    def original_result(call):
        roots()
        saved, pin = frame(call), results.get(id(call))
        require(type(pin) is _CollectionPhaseResultPin and pin.frame is saved and
                pin.result is saved.result and type(pin.result) is CollectionPrefix and
                object.__getattribute__(pin.result, "__dict__") is pin.dictionary,
                "BOOTSTRAP_COLLECTION_PHASE_RESULT_NOT_PUBLISHED")
        names = ("raw", "leaf", "manifest_raw", "checked_ns", "checked_local")
        require(len(pin.dictionary) == len(names) and set(pin.dictionary) == set(names) and pin.dictionary["leaf"] is pin.fields[1] and
                all(type(pin.dictionary[name]) is type(old) and pin.dictionary[name] == old
                    for name, old in zip(names, pin.fields) if name != "leaf"),
                "BOOTSTRAP_COLLECTION_PHASE_PUBLISHED_FIELDS_CHANGED")
        _check_collection_return_graph(pin)
        return pin

    return claim, frame, update, invoke, roots, owner_frame, window_frame, leaf, publish, original_call, original_result


(_claim_collection_phase, _collection_phase_frame, _update_collection_phase, _invoke_collection_phase_begin,
 _collection_phase_roots, _collection_phase_owner_frame, _collection_phase_window_frame,
 _invoke_collection_phase_leaf, _publish_collection_phase, _collection_phase_original_call,
 _collection_phase_original_result) = _collection_phase_controls()
del _collection_phase_controls


def _collection_phase_state(call, state):
    _update_collection_phase(call, state=state)
    call.state = state


def _collection_phase_query_identity(frame):
    """Original NEW query location/roots/pair, not a post-close baseline."""
    supplier, kind, pair, work, final = frame.query
    pin = frame.query_origin
    require(type(supplier) is kind is query.NativeGitQueries and type(pin) is _CollectionPhaseQueryOrigin and
            object.__getattribute__(supplier, "__dict__") is pin.dictionary and
            type(pair) is tuple and len(pair) == 2 and supplier._owner_deadlines is pair and
            staging._local(pair[0]) <= staging._local(pair[1]) <= frame.phases[0].local_end and
            origin.integer(work) <= origin.integer(final) <= frame.phases[0].end and
            type(supplier.root) is type(pin.root) and supplier.root == pin.root and
            type(supplier.path) is type(pin.path) and supplier.path == pin.path and
            supplier.resources is pin.resources and type(pin.resources) is list and
            supplier.records is pin.records and type(pin.records) is list and
            supplier.readbacks is pin.readbacks and type(pin.readbacks) is list,
            "BOOTSTRAP_COLLECTION_PHASE_QUERY_ORIGIN_CHANGED")
    for actual, (directory, expected_kind, path, identity) in zip((supplier.private, supplier.home), pin.roots):
        require(actual is directory and type(actual) is expected_kind and type(actual.path) is type(path) and
                actual.path == path and tuple(actual.identity) == identity,
                "BOOTSTRAP_COLLECTION_PHASE_QUERY_ROOT_CHANGED")
    return supplier, pin


def _collection_phase_query_rows(rows, *, closed):
    require(type(rows) is list and 2 <= len(rows) <= 4096 and
            all(type(row) is dict and set(row) == {"label", "owner", "closeAttempted", "closed"} and
                type(row["label"]) is str and row["owner"] is not None and
                type(row["closeAttempted"]) is type(row["closed"]) is bool and
                row["closeAttempted"] is row["closed"] and (not closed or row["closed"] is True) for row in rows) and
            len({id(row) for row in rows}) == len(rows) and len({id(row["owner"]) for row in rows}) == len(rows),
            "BOOTSTRAP_COLLECTION_PHASE_QUERY_ROSTER")


def _collection_phase_query_before(parent):
    """Pin the actual pre-final roster, including non-required original rows.

    This bounded pre-final-to-terminal custody does not prove no row was lost
    earlier. Failure retains these references and forbids finalizer dispatch.
    """
    frame = _collection_phase_frame(parent)
    supplier, original = _collection_phase_query_identity(frame)
    require(frame.query_preclose is None and frame.query_final_attempted is False and
            supplier.closed is supplier.unknown is supplier.active is False,
            "BOOTSTRAP_COLLECTION_PHASE_QUERY_FINAL_STATE")
    require(len(original.resources) <= 4096 and len(original.records) <= 64 and len(original.readbacks) <= 4096,
            "BOOTSTRAP_COLLECTION_PHASE_QUERY_BEFORE_LIMIT")
    # Retain actual row/value references BEFORE validating their current flags.
    rows = tuple(_CollectionPhaseResource(row, row.get("label"), row.get("owner"), type(row.get("owner")),
                row.get("closeAttempted"), row.get("closed")) if type(row) is dict else
                _CollectionPhaseResource(row, None, None, type(None), None, None) for row in original.resources)
    before = _CollectionPhaseQueryBefore(rows, tuple(original.readbacks), None, None)
    _update_collection_phase(parent, query_preclose=before)
    _collection_phase_query_rows(original.resources, closed=False)
    required = {name: tuple(row for row in rows if row.label == name) for name in ("private-root", "query-home")}
    require(all(len(value) == 1 for value in required.values()) and
            required["private-root"][0].value is original.roots[0][0] and
            required["query-home"][0].value is original.roots[1][0] and
            not any(row.label == "session-result.json" for row in rows),
            "BOOTSTRAP_COLLECTION_PHASE_QUERY_INITIAL_ROSTER")
    graph = _StagingClosedGraph.capture(original.records, before.readbacks)
    pin = (object.__getattribute__(graph, "__dict__"), graph.nodes, graph.paths)
    _update_collection_phase(parent, query_preclose=before._replace(graph=graph, graph_pin=pin))


def _collection_phase_query_pin(frame, result):
    supplier, original = _collection_phase_query_identity(frame)
    before = frame.query_preclose
    require(type(before) is _CollectionPhaseQueryBefore and frame.query_final_attempted is True and
            frame.query_returned[0] is True, "BOOTSTRAP_COLLECTION_PHASE_QUERY_NOT_RETURNED")
    require(type(supplier) is query.NativeGitQueries and supplier.closed is True and supplier.unknown is False and
            supplier.failed is False and supplier.active is False and supplier.first_error is None and
            supplier.cancellation is None and type(supplier.errors) is list and supplier.errors == [],
            "BOOTSTRAP_COLLECTION_PHASE_QUERY_NOT_CLOSED")
    _collection_phase_query_rows(original.resources, closed=True)
    require(len(original.resources) == len(before.rows) + 1 and
            all(row is pin.row and row["label"] == pin.label and row["owner"] is pin.value and
                type(row["owner"]) is pin.kind for row, pin in zip(original.resources, before.rows)) and
            original.resources[-1]["label"] == "session-result.json",
            "BOOTSTRAP_COLLECTION_PHASE_QUERY_FINAL_ROSTER")
    graph, pin = before.graph, before.graph_pin
    require(type(graph) is _StagingClosedGraph and object.__getattribute__(graph, "__dict__") is pin[0] and
            set(pin[0]) == {"nodes", "paths"} and graph.nodes is pin[1] and graph.paths is pin[2],
            "BOOTSTRAP_COLLECTION_PHASE_QUERY_BEFORE_GRAPH_CHANGED")
    graph.checked()
    # Successful close appends exactly its session receipt's readback. The
    # earlier query/receipt records remain the actual pre-final originals.
    require(len(original.readbacks) == len(before.readbacks) + 1 and
            all(row is old for row, old in zip(original.readbacks, before.readbacks)),
            "BOOTSTRAP_COLLECTION_PHASE_QUERY_READBACK_ROSTER")
    tail = original.readbacks[-1]
    require(type(tail) is dict and set(tail) == {"parent", "name", "maximum", "retirement", "result", "bytes"} and
            tail["parent"] == str(original.path) and tail["name"] == "session-result.json" and
            tail["retirement"] == "KNOWN" and tail["result"] == "RETAINED" and
            type(tail["maximum"]) is type(tail["bytes"]) is int and 0 < tail["bytes"] == tail["maximum"] <= LIMIT,
            "BOOTSTRAP_COLLECTION_PHASE_QUERY_FINAL_READBACK")
    dictionary = object.__getattribute__(supplier, "__dict__")
    graph = _StagingClosedGraph.capture(dictionary, result)
    graph = _StagingClosedGraph(graph.nodes, (*graph.paths, *original.roots))
    graph.checked()
    return dictionary, graph, object.__getattribute__(graph, "__dict__"), graph.nodes, graph.paths


def _collection_phase_query_checked(frame):
    if frame.query_pin is None:
        return
    supplier = frame.query[0]
    dictionary, graph, graph_dictionary, nodes, paths = frame.query_pin
    require(type(supplier) is query.NativeGitQueries and object.__getattribute__(supplier, "__dict__") is dictionary and
            type(graph) is _StagingClosedGraph and object.__getattribute__(graph, "__dict__") is graph_dictionary and
            set(graph_dictionary) == {"nodes", "paths"} and graph.nodes is nodes and graph.paths is paths,
            "BOOTSTRAP_COLLECTION_PHASE_QUERY_PIN_CHANGED")
    graph.checked()


@dataclass(frozen=True)
class _CollectionPhaseWindow:
    """NEW file work120/close45/return30; every cap intersects original allocation.

    READ is only post-close return accounting here, not a file-read execution.
    It cannot reopen this owner or any predecessor; all I/O stays in WORK.
    """
    call: object = field(repr=False, compare=False)

    @property
    def clock(self):
        return origin.clocks.ClockIdentity(*_collection_phase_window_frame(self).limits.clock)

    def _raw_local(self, *, strict, minimum=0):
        frame = _collection_phase_window_frame(self)
        call = frame.call
        call.check() if strict else call.cleanup_bindings()
        local = staging._local(time.monotonic())
        require(local >= _collection_phase_frame(call).local_last, "BOOTSTRAP_COLLECTION_PHASE_LOCAL_BACKWARDS")
        _update_collection_phase(call, local_last=local)
        _collection_phase_window_frame(self)
        observed = origin.clocks.checked_now(origin.clocks.ClockIdentity(*frame.limits.clock),
            minimum_ns=max(_collection_phase_frame(call).last, origin.integer(minimum)))
        require(observed >= _collection_phase_frame(call).last, "BOOTSTRAP_COLLECTION_PHASE_RAW_BACKWARDS")
        _update_collection_phase(call, last=observed)
        _collection_phase_window_frame(self)
        after = staging._local(time.monotonic())
        require(after >= _collection_phase_frame(call).local_last, "BOOTSTRAP_COLLECTION_PHASE_LOCAL_BACKWARDS")
        _update_collection_phase(call, local_last=after)
        _collection_phase_window_frame(self)
        call.check() if strict else call.cleanup_bindings()
        return observed, after

    def sample(self, *, cleanup=False, minimum=0, limit=None):
        require(type(cleanup) is bool, "BOOTSTRAP_COLLECTION_PHASE_CLOCK_MODE")
        frame = _collection_phase_window_frame(self)
        require(frame.state not in ("COMPLETE", "FAILED") and frame.phases and
                (cleanup or frame.phases[-1].name in ("WORK", "READ")),
                "BOOTSTRAP_COLLECTION_PHASE_NOT_LIVE")
        observed, local = self._raw_local(strict=not cleanup, minimum=minimum)
        phase = _collection_phase_window_frame(self).phases[-1]
        end = phase.end if limit is None else min(phase.end, origin.integer(limit))
        require(observed < end and local < phase.local_end, "BOOTSTRAP_COLLECTION_PHASE_EXPIRED")
        return observed

    def now(self, *, final=False, minimum=0, limit=None):
        observed = self.sample(cleanup=final, minimum=minimum, limit=limit)
        if not final:
            _collection_phase_window_frame(self).call.cancel()
            observed = self.sample(minimum=observed, limit=limit)
        return observed

    def deadline(self, maximum, *, final=False, limit=None):
        require(final is False and type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 120,
                "BOOTSTRAP_COLLECTION_PHASE_ACQUISITION_MODE")
        frame = _collection_phase_window_frame(self)
        call = frame.call
        call.live()
        local = staging._local(time.monotonic())
        require(local >= _collection_phase_frame(call).local_last, "BOOTSTRAP_COLLECTION_PHASE_LOCAL_BACKWARDS")
        _update_collection_phase(call, local_last=local)
        _collection_phase_window_frame(self)
        observed = self.now(limit=limit)
        phase = _collection_phase_window_frame(self).phases[-1]
        end = phase.end if limit is None else min(phase.end, origin.integer(limit))
        return min(phase.local_end, origin.wire._directed_deadline(local, maximum, end, observed))

    def advance(self, name):
        frame = _collection_phase_window_frame(self)
        call = frame.call
        require(type(name) is str and 0 < len(frame.phases) < 3 and
                name == ("WORK", "FINAL", "READ")[len(frame.phases)],
                "BOOTSTRAP_COLLECTION_PHASE_STEP_REENTRY")
        previous = frame.phases[-1]
        _update_collection_phase(call, phases=(*frame.phases, _CollectionPhaseStep(name, None, None, 0, 0.0)))
        observed = local = None
        try:
            require(previous.started is not None and previous.local_started is not None and
                    previous.end > 0 and previous.local_end > 0, "BOOTSTRAP_COLLECTION_PHASE_PRIOR_START_FAILED")
            if name == "READ":
                call.closed()
            observed, local = self._raw_local(strict=name == "READ")
            current = _collection_phase_window_frame(self)
            index, seconds = len(current.phases) - 1, 45 if name == "FINAL" else 30
            end = min(current.limits.ends[index], origin.integer(observed + seconds * origin.NS))
            local_end = min(current.limits.local_ends[index],
                origin.wire._directed_deadline(local, seconds, end, observed))
            if name == "READ":
                require(observed < previous.end and local < previous.local_end,
                        "BOOTSTRAP_COLLECTION_PHASE_RETURN_START_EXPIRED")
            _update_collection_phase(call, phases=(*current.phases[:-1],
                _CollectionPhaseStep(name, observed, local, end, local_end)))
            self.sample(cleanup=name == "FINAL")
        except BaseException as error:
            current = _collection_phase_frame(call)
            _update_collection_phase(call, phases=(*current.phases[:-1],
                _CollectionPhaseStep(name, observed, local, 0, 0.0)))
            call.error("collection-phase-" + name.lower() + "-start", error)
            raise

    def record(self):
        frame = _collection_phase_window_frame(self)
        return {"clock": origin.clock_value(self.clock), "firstNs": frame.limits.first,
            "globalEndsNs": dict(zip(("WORK", "FINAL", "READ"), frame.limits.ends)),
            "phases": [{"phase": row.name, "startedNs": row.started, "endNs": row.end} for row in frame.phases],
            "readSlotScope": "POST_CLOSE_RETURN_OBSERVATIONS_ONLY_NO_FILE_READ_EXECUTION",
            "budgetAcceptance": "NOT_ADMITTED"}


class _CollectionPhaseOwner(Owner):
    """Distinct file-only ledger; no WORK acquisition after close/final/return."""
    def error(self, stage, error, *, unknown=False):
        _collection_phase_owner_frame(self).call.error(stage, error, unknown=unknown)

    def end(self, *, final=False):
        require(final is False, "BOOTSTRAP_COLLECTION_PHASE_NO_FINAL_ACQUISITION")
        frame = _collection_phase_owner_frame(self)
        frame.call.live()
        return frame.window.deadline(45)

    def _retain(self, label, value):
        frame = _collection_phase_owner_frame(self)
        require(id(value) not in frame.borrowed and not any(pin.value is value for pin in frame.resources), "BOOTSTRAP_COLLECTION_PHASE_DUPLICATE_RESOURCE")
        row = {"label": label, "owner": value, "attempted": False, "closed": False}
        pin = _CollectionPhaseResource(row, label, value, type(value), False, False)
        _update_collection_phase(frame.call, resources=(*frame.resources, pin))
        # The private original survives a changed public list or failed append.
        frame.owner_bindings[0].append(row)
        return value

    def acquire(self, label, factory, *, final=False):
        require(final is False and type(label) is str and label in (
            "directory", "reader", "writer", "source-directory", "bootstrap-collection-root",
            "bootstrap-collection-reader", "bootstrap-collection-writer", "bootstrap-collection-directory"),
            "BOOTSTRAP_COLLECTION_PHASE_RESOURCE_LABEL")
        frame = _collection_phase_owner_frame(self)
        self.end()
        require(frame.close_roster is None and frame.phases[-1].name == "WORK" and len(frame.resources) < 4096, "BOOTSTRAP_COLLECTION_PHASE_RESOURCE_PHASE")
        try:
            value = factory()
        except BaseException as error:
            frame.call.error(label + "-allocation", error, unknown=True)
            raise
        self._retain(label, value)
        self.end()
        return value

    def new(self, path):
        return self.acquire("directory", lambda: staging.files.private_root(path, create=True))

    def open(self, path, *, final=False):
        require(final is False, "BOOTSTRAP_COLLECTION_PHASE_NO_FINAL_ACQUISITION")
        return self.acquire("directory", lambda: staging.files.private_root(path))

    def child(self, parent, name, *, create=False, final=False):
        require(type(create) is bool and final is False, "BOOTSTRAP_COLLECTION_PHASE_DIRECTORY_MODE")
        frame = _collection_phase_owner_frame(self)
        require(not create or frame.phases[-1].name == "WORK", "BOOTSTRAP_COLLECTION_PHASE_READ_ONLY_PHASE")
        end = self.end()
        return self.acquire("directory", lambda: parent.create_directory(name, deadline=end) if create else
                            parent.open_directory(name, deadline=end))

    def read(self, parent, name, maximum=LIMIT, *, final=False):
        require(final is False, "BOOTSTRAP_COLLECTION_PHASE_NO_FINAL_ACQUISITION")
        raw, _binding = _collection_phase_owner_frame(self).call.read_file(parent, name, maximum)
        return raw

    def write(self, parent, name, value, *, final=False):
        require(final is False, "BOOTSTRAP_COLLECTION_PHASE_NO_FINAL_ACQUISITION")
        raw = value if type(value) is bytes else origin.encoded(value)
        require(0 < len(raw) <= LIMIT, "BOOTSTRAP_COLLECTION_PHASE_PRIVATE_RECORD_LIMIT")
        end = self.end()
        writer = self.acquire("writer", lambda: parent.create_file(name, max_bytes=len(raw), deadline=end))
        frame = _collection_phase_owner_frame(self)
        try:
            offset = 0
            while offset < len(raw):
                self.end()
                part = raw[offset:offset + 65536]
                count = writer.write(part)
                require(type(count) is int and 0 < count <= len(part), "BOOTSTRAP_COLLECTION_PHASE_SHORT_WRITE")
                offset += count
                self.end()
            writer.sync()
            require(writer.verify().size == len(raw), "BOOTSTRAP_COLLECTION_PHASE_PRIVATE_WRITE_CHANGED")
            self.end()
        except BaseException as error:
            frame.call.error("collection-phase-write", error)
        finally:
            self.close_one(writer)
        frame.call.raise_first()
        require(self.read(parent, name) == raw, "BOOTSTRAP_COLLECTION_PHASE_PRIVATE_READBACK")
        return raw

    def close_one(self, value):
        frame = _collection_phase_owner_frame(self)
        pin = next((pin for pin in frame.resources if pin.value is value), None)
        if pin is None:
            frame.call.error("collection-phase-close-foreign", origin.OriginError("BOOTSTRAP_COLLECTION_PHASE_FOREIGN_RESOURCE"), unknown=True)
            return
        if pin.attempted:
            return
        try:
            frame.call.cleanup_bindings()
            require(type(value) is pin.kind and not frame.unknown, "BOOTSTRAP_COLLECTION_PHASE_CLOSE_UNKNOWN")
        except BaseException as error:
            frame.call.error("collection-phase-close-binding", error, unknown=True)
            return
        self.close_fence()
        frame.call.close_resource(pin)
        self.close_fence()

    def close_fence(self):
        frame = _collection_phase_owner_frame(self)
        try:
            observed, local = frame.window._raw_local(strict=False)
            current = _collection_phase_owner_frame(self)
            phase = current.phases[-1]
            if observed >= phase.end or local >= phase.local_end:
                # Every close is sampled. Re-observing one fixed expired cap
                # is not a new event that may exhaust the finite error ledger.
                index = len(current.phases) - 1
                if index not in current.expired_closes:
                    _update_collection_phase(frame.call, expired_closes=(*current.expired_closes, index))
                    frame.call.error("collection-phase-close-expired",
                        origin.OriginError("BOOTSTRAP_COLLECTION_PHASE_EXPIRED"))
        except BaseException as error:
            frame.call.error("collection-phase-close-fence", error)

    def close(self):
        frame = _collection_phase_owner_frame(self)
        if self.closed:
            return
        _update_collection_phase(frame.call, owner_closed=True)
        self.closed = True
        self.close_fence()
        for pin in reversed(frame.resources):
            if _collection_phase_frame(frame.call).unknown:
                break
            self.close_one(pin.value)
        self.close_fence()
        if _collection_phase_frame(frame.call).unknown:
            if not any(value is self for value in QUARANTINE):
                QUARANTINE.append(self)
            raise origin.OriginError("BOOTSTRAP_COLLECTION_PHASE_RETIREMENT_UNKNOWN")


@dataclass(frozen=True)
class _CollectionPhaseReader:
    call: object = field(repr=False, compare=False)
    owner: object = field(init=False, repr=False, compare=False)
    current: object = field(init=False, repr=False, compare=False)
    past: object = field(init=False, repr=False)
    first: object = field(init=False, repr=False)

    def __post_init__(self):
        call = self.call
        require(type(call) is _CollectionPhaseParent, "BOOTSTRAP_COLLECTION_PHASE_READER_CHANGED")
        frame = call.check()
        old = frame.transition._attempt.transition
        for name, value in (("owner", call.live()), ("current", frame.window),
                ("past", history.snapshot(old._fence)), ("first", old._limits[8])):
            object.__setattr__(self, name, value)

    def checked(self):
        call, owner, current = self.call, self.owner, self.current
        require(type(call) is _CollectionPhaseParent and type(owner) is _CollectionPhaseOwner and type(current) is _CollectionPhaseWindow,
                "BOOTSTRAP_COLLECTION_PHASE_READER_CHANGED")
        # Check passive ORIGINAL window/owner identity before invoking any
        # published parent. Even a different exact registered parent is not
        # this view's target and must not have its roster/error state touched.
        frame = _collection_phase_window_frame(current)
        require(frame.call is call and frame.owner is owner, "BOOTSTRAP_COLLECTION_PHASE_READER_CHANGED")
        frame = call.check()
        old = frame.transition._attempt.transition
        require(self.call is call and self.owner is owner and self.current is current and call.live() is owner and
                current is frame.window and
                self.first is old._limits[8] and history.checked(self.past) == history.snapshot(old._fence),
                "BOOTSTRAP_COLLECTION_PHASE_READER_CHANGED")
        return self

    def observe(self, *, final, minimum):
        self.checked()
        return self.current.now(minimum=minimum)



@dataclass(eq=False)
class _CollectionPhaseParent:
    """Once-claimed NEW parent. Its constructor and returned data grant no rights."""
    transition: object = field(repr=False)
    state: str = "CLAIMED"
    owner: object = field(default=None, repr=False)
    window: object = field(default=None, repr=False)
    handles: dict = field(default_factory=dict, repr=False)
    records: dict = field(default_factory=dict, repr=False)
    handlers: dict = field(default_factory=dict, repr=False)
    cancelled: list = field(default_factory=list, repr=False)
    original: object = field(default=None, repr=False)
    unknown: bool = False
    result: object = field(default=None, repr=False)

    def cleanup_bindings(self):
        frame = _collection_phase_frame(self)
        if frame.owner is not None:
            owner, pin = frame.owner, frame.owner_bindings
            self.roster()
            frame = _collection_phase_frame(self)
            require(type(owner) is _CollectionPhaseOwner and owner.resources is pin[0] and owner.errors is pin[1] and
                    owner.admissions is pin[2] and type(owner.local_end) is type(pin[3]) and owner.local_end == pin[3] and
                    owner.first is frame.first and owner.fence is frame.window and owner.cancelled is pin[4] and
                    owner.work_limit is None and owner.final_limit is None and owner.early_last == frame.limits.first and
                    type(owner.closed) is bool and owner.closed is frame.owner_closed and type(owner.unknown) is bool,
                    "BOOTSTRAP_COLLECTION_PHASE_OWNER_CHANGED")
        if frame.window is not None:
            require(type(frame.window) is _CollectionPhaseWindow and frame.window.call is self and
                    _collection_phase_window_frame(frame.window) is frame and type(frame.limits) is _CollectionPhaseLimits and
                    staging._clock(frame.first.clock) == frame.limits.clock and frame.first.nanoseconds == frame.limits.first,
                    "BOOTSTRAP_COLLECTION_PHASE_WINDOW_CHANGED")
        return frame

    def check(self):
        frame = self.cleanup_bindings()
        _collection_phase_roots()
        require(self.transition is frame.transition and self.state == frame.state and self.owner is frame.owner and
                self.window is frame.window and self.original is frame.original and self.unknown is frame.unknown and
                self.result is frame.result and self.handles is frame.published[0] and self.records is frame.published[1] and
                self.handlers is frame.published[2] and self.cancelled is frame.published[3],
                "BOOTSTRAP_COLLECTION_PHASE_PARENT_CHANGED")
        require(tuple(self.handles.items()) == tuple((row[0], row[1]) for row in frame.handles) and
                tuple(self.records.items()) == tuple((row[0], row[6]) for row in frame.files) and
                tuple(self.handlers.items()) == frame.handlers, "BOOTSTRAP_COLLECTION_PHASE_PUBLIC_ROSTER_CHANGED")
        require(frame.bound is not None and _checked_collection_origin(frame.binding) is frame.bound and
                frame.bound.transition is frame.transition and frame.predecessor is frame.bound.producer_frame.predecessor,
                "BOOTSTRAP_COLLECTION_PHASE_PREDECESSOR_CHANGED")
        _collection_phase_query_checked(frame)
        if frame.leaf_originals is not None:
            require(collect_files._capture(frame.leaf_originals) == frame.leaf_originals_pin,
                    "BOOTSTRAP_COLLECTION_PHASE_LEAF_INPUT_CHANGED")
        if frame.leaf_pin is not None:
            leaf, pin = frame.leaf, frame.leaf_pin
            require(type(leaf) is collect_files.FileCollectionEvidence and object.__getattribute__(leaf, "__dict__") is pin[0] and
                    set(pin[0]) == {"raw", "inventory_raw", "local_started", "checked_local"} and
                    all(type(value) is type(old) and value == old for value, old in zip(
                        (leaf.raw, leaf.inventory_raw, leaf.local_started, leaf.checked_local), pin[1:])),
                    "BOOTSTRAP_COLLECTION_PHASE_LEAF_RETURN_CHANGED")
        if frame.result_pin is not None:
            result, pin = frame.result, frame.result_pin
            require(type(result) is CollectionPrefix and object.__getattribute__(result, "__dict__") is pin[0] and
                    set(pin[0]) == {"raw", "leaf", "manifest_raw", "checked_ns", "checked_local"} and
                    result.leaf is frame.leaf and all(type(value) is type(old) and value == old for value, old in zip(
                        (result.raw, result.manifest_raw, result.checked_ns, result.checked_local), pin[1:])),
                    "BOOTSTRAP_COLLECTION_PHASE_RESULT_CHANGED")
        require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                "BOOTSTRAP_COLLECTION_PHASE_PRIOR_UNKNOWN")
        return _collection_phase_frame(self)

    def live(self):
        frame = self.check()
        self.raise_first()
        require(frame.state == "RUNNING" and frame.phases[-1].name == "WORK" and frame.owner is not None and
                frame.owner.closed is False and not frame.unknown and not frame.owner.unknown,
                "BOOTSTRAP_COLLECTION_PHASE_NOT_LIVE")
        return frame.owner

    def cancel(self):
        frame = self.check()
        cancellation(frame.published[3])
        for callback in frame.predecessor.frame.callbacks:
            callback()
            self.check()
        cancellation(frame.published[3])

    def closed(self):
        self.raise_first()
        frame = self.check()
        require(frame.owner is not None and frame.owner.closed is True and frame.owner_closed is True and
                frame.owner.original is None and not frame.owner.unknown and not frame.unknown and not frame.errors and
                not frame.foreign and frame.close_roster is not None and frame.handlers == frame.restored and
                all(pin.attempted and pin.closed for pin in frame.resources) and frame.leaf_pin is not None and
                frame.query_pin is not None and frame.query_returned[0] is True,
                "BOOTSTRAP_COLLECTION_PHASE_NOT_CLOSED")
        return frame

    def error(self, stage, error, *, unknown=False):
        frame = _collection_phase_frame(self)
        first = frame.original
        if first is None:
            first = frame.owner.original if frame.owner is not None and frame.owner.original is not None else error
        detail = diagnostics._exception_detail(error)
        uncertain = frame.unknown or unknown or detail["retirementUnknown"] or bool(
            QUARANTINE or query.QUARANTINE or diagnostics._QUARANTINE)
        errors = frame.errors
        if len(errors) < 64:
            errors = (*errors, origin.encoded({"stage": stage, "detail": detail}))
        else:
            uncertain = True
        _update_collection_phase(self, original=first, unknown=uncertain, errors=errors)
        self.original, self.unknown = first, uncertain
        if frame.owner is not None:
            try:
                require(frame.owner.errors is frame.owner_bindings[1], "BOOTSTRAP_COLLECTION_PHASE_ERRORS_CHANGED")
                Owner.error(frame.owner, stage, error, unknown=uncertain)
                uncertain |= frame.owner.unknown
            except BaseException:
                uncertain = True
            frame.owner.original, frame.owner.unknown = first, uncertain
            _update_collection_phase(self, unknown=uncertain)
            self.unknown = uncertain

    def raise_first(self):
        frame = _collection_phase_frame(self)
        if frame.original is not None:
            raise frame.original
        if frame.owner is not None and frame.owner.original is not None:
            self.error("collection-phase-owner-return", frame.owner.original)
            raise _collection_phase_frame(self).original

    def roster(self):
        frame = _collection_phase_frame(self)
        if frame.owner is None:
            return
        original_rows = frame.owner_bindings[0]
        foreign = list(frame.foreign)
        seen = {(id(pin.row), id(pin.value)) for pin in frame.resources}
        seen.update((id(row), id(value)) for row, _label, value in foreign)
        for rows in (original_rows,) if frame.owner.resources is original_rows else (original_rows, frame.owner.resources):
            if type(rows) is list:
                for row in rows:
                    label, value = (row.get("label"), row.get("owner")) if type(row) is dict else (None, None)
                    if (id(row), id(value)) not in seen:
                        foreign.append((row, label, value))
                        seen.add((id(row), id(value)))
        _update_collection_phase(self, foreign=tuple(foreign))
        try:
            require(not foreign and frame.owner.resources is original_rows and type(original_rows) is list and
                    len(original_rows) == len(frame.resources) <= 4096, "BOOTSTRAP_COLLECTION_PHASE_ROSTER_CHANGED")
            for row, pin in zip(original_rows, frame.resources):
                require(row is pin.row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                        row["label"] == pin.label and row["owner"] is pin.value and type(pin.value) is pin.kind and
                        row["attempted"] is pin.attempted and row["closed"] is pin.closed,
                        "BOOTSTRAP_COLLECTION_PHASE_ROSTER_CHANGED")
            if frame.close_roster is not None:
                require(tuple((id(pin.row), pin.label, id(pin.value)) for pin in frame.resources) == frame.close_roster,
                        "BOOTSTRAP_COLLECTION_PHASE_CLOSE_ROSTER_CHANGED")
        except BaseException as error:
            self.error("collection-phase-roster", error, unknown=True)
            raise

    def inputs(self):
        frame = self.check()
        saved, last = frame.predecessor.frame, frame.predecessor.phases[-1][1]
        return custody._Inputs(saved.originals, saved.original_pin, last.staged, last.staged_pin)

    def directory(self, key, path, identity=None, *, parent=None, create=False):
        owner = self.live()
        frame = _collection_phase_frame(self)
        found = next((row for row in frame.handles if row[0] == key), None)
        if found is None:
            directory = owner.open(path) if parent is None else owner.child(parent, path.name, create=create)
            actual = tuple(directory_identity(list(directory.identity), frame.limits.clock[0]))
            row = (key, directory, path, actual)
            _update_collection_phase(self, handles=(*_collection_phase_frame(self).handles, row))
            self.handles[key] = directory
            found = row
        require(found[2] == path and (identity is None or found[3] == tuple(identity)),
                "BOOTSTRAP_COLLECTION_PHASE_DIRECTORY_CHANGED")
        _new_entry_owned(owner, found[1], path, found[3])
        self.check()
        return found[1]

    def read_file(self, directory, name, maximum=LIMIT, *, expected=None, binding=None):
        """Bounded metadata only; outer streams use their separate hash reader."""
        owner = self.live()
        require(type(maximum) is int and 0 < maximum <= producer.LIMIT, "BOOTSTRAP_COLLECTION_PHASE_METADATA_LIMIT")
        end = owner.end()
        reader = owner.acquire("reader", lambda: directory.open_file(name, max_bytes=maximum, deadline=end))
        raw = retained = None
        try:
            before = reader.initial_info
            require(type(before.size) is int and 0 <= before.size <= maximum, "BOOTSTRAP_COLLECTION_PHASE_METADATA_SIZE")
            retained = staging.files._info_binding(before)
            require(binding is None or retained == binding, "BOOTSTRAP_COLLECTION_PHASE_ORIGINAL_FILE_REPLACED")
            data = bytearray()
            while len(data) < before.size:
                owner.end()
                count = min(65536, before.size - len(data))
                part = reader.read(count)
                require(type(part) is bytes and 0 < len(part) <= count, "BOOTSTRAP_COLLECTION_PHASE_METADATA_SHORT_READ")
                data.extend(part)
                owner.end()
            require(reader.read(1) == b"" and reader.verify() == before, "BOOTSTRAP_COLLECTION_PHASE_METADATA_CHANGED")
            raw = bytes(data)
            require(expected is None or raw == expected, "BOOTSTRAP_COLLECTION_PHASE_ORIGINAL_BYTES_CHANGED")
            owner.end()
        except BaseException as error:
            self.error("collection-phase-metadata-read", error)
        finally:
            owner.close_one(reader)
        self.raise_first()
        owner.end()
        return raw, retained

    def remember(self, key, directory, name, raw, maximum=LIMIT, *, binding=None):
        frame = self.check()
        require(type(raw) is bytes and len(raw) <= maximum and not any(row[0] == key for row in frame.files),
                "BOOTSTRAP_COLLECTION_PHASE_ORIGINAL_ROSTER")
        identity = tuple(directory_identity(list(directory.identity), frame.limits.clock[0]))
        _new_entry_owned(self.live(), directory, directory.path, identity)
        # A reader's ORIGINAL binding must cross this boundary, especially for
        # canonical start/receipt. For newly written metadata establish it now;
        # never regenerate a supplied original binding from a later same-byte
        # file. The detached encoding cannot be mutated through the caller.
        if binding is None:
            _actual, binding = self.read_file(directory, name, maximum, expected=raw)
        require(staging.files._file_binding(binding), "BOOTSTRAP_COLLECTION_PHASE_ORIGINAL_FILE_BINDING")
        retained = origin.encoded(binding)
        frame = self.check()
        _update_collection_phase(self, files=(*frame.files,
            _CollectionPhaseFile(key, directory, directory.path, identity, name, maximum, raw, retained)))
        self.records[key] = raw
        self.check()

    def reread(self):
        owner = self.live()
        for _key, directory, path, identity, name, maximum, raw, binding_raw in _collection_phase_frame(self).files:
            _new_entry_owned(owner, directory, path, identity)
            self.read_file(directory, name, maximum, expected=raw, binding=origin.parse(binding_raw))
        self.check()

    def file_facade(self):
        """Source-only adapter for unchanged original-file parsers, no owner."""
        call, owner = self, self.live()
        directories = {"bootstrap-source", "bootstrap-source-parent", "custody-source-root", "custody-source-scripts",
                       "dependency-seed-source-root", "dependency-seed-source-parent"}
        class Reader:
            @property
            def unknown(self):
                return _collection_phase_frame(call).unknown

            def check(self, *, new=False):
                require(type(new) is bool, "BOOTSTRAP_COLLECTION_PHASE_FILE_MODE")
                require(call.live() is owner, "BOOTSTRAP_COLLECTION_PHASE_FILE_OWNER_CHANGED")
                owner.end()

            def end(self, *, new=False):
                self.check(new=new)
                return owner.end()

            def acquire(self, label, factory):
                require(label in directories or label in ("reader", "dependency-seed-input"),
                        "BOOTSTRAP_COLLECTION_PHASE_SOURCE_LABEL")
                return owner.acquire("source-directory" if label in directories else "reader", factory)

            def close_one(self, resource):
                owner.close_one(resource)
                call.raise_first()
                require(any(pin.value is resource and pin.attempted and pin.closed for pin in
                    _collection_phase_frame(call).resources), "BOOTSTRAP_COLLECTION_PHASE_SOURCE_CLOSE_UNKNOWN")

            def error(self, stage, error, *, unknown=False):
                call.error(stage, error, unknown=unknown)
        return Reader()

    def host(self):
        owner = self.live()
        owner.end()
        frame = _collection_phase_frame(self)
        saved = frame.predecessor.frame
        entry = frame.transition._attempt.transition._entry
        context = origin.parse(entry.context_original)
        require(origin.wire.TOKEN_ENV not in os.environ and os.environ.get(PREPARE_OUTCOME_ENV) == "success" and
                os.environ.get(PREPARE_HASH_ENV) == origin.digest(entry.handoff_original),
                "BOOTSTRAP_COLLECTION_PHASE_PREPARE_OUTCOME_OR_TOKEN")
        selection, path, event = host_inputs(saved.originals.clock.role)
        require(path == saved.paths[0] and selection == context["selection"] and event == entry.admitted.original_event and
                context["runnerName"] == os.environ.get("RUNNER_NAME") and context["inheritedContext"] == query._inherited_context() and
                os.getpid() != origin.parse(entry.preparation_original)["processIdentity"]["pid"],
                "BOOTSTRAP_COLLECTION_PHASE_ACTUAL_HOST_CHANGED")
        inputs = _parent_originals(saved.record[0])[4][5][0]
        require(initialization._installed() == inputs.toolchains.originals and canonical._interpreter() == inputs.interpreter and
                inputs.policy == initialization.properties(inputs.homes), "BOOTSTRAP_COLLECTION_PHASE_INSTALLED_INPUTS_CHANGED")
        env = recipient_environment(saved.paths[3])
        env.update({name: home for name, _supplied, home, _identities in inputs.toolchains.originals})
        require(tuple(sorted(env.items())) == inputs.environment, "BOOTSTRAP_COLLECTION_PHASE_INITIAL_ENVIRONMENT_CHANGED")
        owner.end()
        return env

    def read_originals(self):
        owner = self.live()
        self.host()
        frame = _collection_phase_frame(self)
        saved, previous = frame.predecessor.frame, frame.transition._attempt
        old = previous.transition
        entry, paths = old._entry, saved.paths
        value = origin.parse(entry.raw)
        for key, path, identity in (("original", paths[0], value["preparation"]["sessionIdentity"]),
                ("adoption", paths[1], value["sessionIdentity"]), ("entry", paths[2], previous.target_identity)):
            self.directory(key, path, identity)
        adoption, current = self.handles["adoption"], self.handles["entry"]
        require(owner.read(adoption, "entry-context.json") == entry.raw and
                owner.read(adoption, "entry-close-pending.json") == old.pending_raw and
                owner.read(current, "new-entry-pending.json") == previous.pending_raw,
                "BOOTSTRAP_COLLECTION_PHASE_ENTRY_ORIGINAL_CHANGED")
        for target, admitted, session_raw, returned_raw in (
                (adoption, entry.admitted, entry.session_original, entry.return_original),
                (current, previous.admitted, previous.admission_originals[1], previous.admission_originals[2])):
            directory = self.directory("admission:" + str(target.path), target.path / "admission", parent=target)
            require(load_admission(owner, directory) == admitted and owner.read(directory, "session-result.json") == session_raw and
                    owner.read(target, "admission-return.json") == returned_raw, "BOOTSTRAP_COLLECTION_PHASE_ENTRY_ADMISSION_CHANGED")
        _admission_history_content(entry.admitted, entry.session_original, entry.return_original, history.snapshot(old._fence))
        _new_entry_return_content(previous)
        admitted, _context, prepared = _read_prepared(_CollectionPhaseReader(self), self.handles["original"],
            entry.handoff_original, entry.context_original)
        require(admitted == entry.admitted and same_preparation(prepared, origin.parse(entry.preparation_original)) and
                same_preparation(prepared, origin.parse(previous.preparation)), "BOOTSTRAP_COLLECTION_PHASE_PREPARATION_CHANGED")
        service = self.directory("service", paths[0] / "service", parent=self.handles["original"])
        responses = tuple((name, owner.read(service, name + ".json")) for name in ("attempt", "jobs"))
        require(responses == old.responses and origin.encoded(_entry_close_proposal(entry, responses)) == old.proposal_raw and
                old.proposal_raw == saved.originals.proposal_raw, "BOOTSTRAP_COLLECTION_PHASE_SERVICE_ORIGINALS_CHANGED")
        files = saved.files + tuple((key, str(path), identity, name, maximum, raw)
            for _parent, closed in frame.predecessor.phases
            for key, _directory, path, identity, name, maximum, raw in closed.files)
        for _key, spelling, identity, name, maximum, raw in files:
            path = Path(spelling)
            directory = self.directory("predecessor:" + spelling, path, identity)
            self.read_file(directory, name, maximum, expected=raw)
        self.host()
        # New handles compare the closed producer's ORIGINAL bindings. Even a
        # same-byte replacement is not an original metadata file.
        for row in self.check().bound.producer_frame.files:
            directory = self.directory("producer-record:" + str(row.path), row.path, row.identity)
            self.read_file(directory, row.name, row.maximum, expected=row.raw,
                           binding=origin.parse(row.binding_raw))
        self.host()

    def close_resource(self, pin):
        """Recheck AFTER the pre-close clock, then once-close the private return.

        Mere expiry preserves known cleanup. Newly UNKNOWN ownership or changed
        bindings must neither dispatch close nor mark the original attempted.
        """
        try:
            frame = self.cleanup_bindings()
            require(not frame.unknown and frame.owner.unknown is False,
                    "BOOTSTRAP_COLLECTION_PHASE_CLOSE_UNKNOWN")
            actual = next((row for row in frame.resources if row.value is pin.value), None)
            require(actual is not None and actual.row is pin.row and actual.kind is type(pin.value),
                    "BOOTSTRAP_COLLECTION_PHASE_CLOSE_BINDING")
            if actual.attempted:
                return
        except BaseException as error:
            self.error("collection-phase-close-dispatch", error, unknown=True)
            return
        _update_collection_phase(self, resources=tuple(row._replace(attempted=True) if row.value is pin.value else row
                                              for row in frame.resources))
        pin.row["attempted"] = True
        try:
            pin.value.close()
            current = _collection_phase_frame(self)
            _update_collection_phase(self, resources=tuple(row._replace(closed=True) if row.value is pin.value else row
                                                  for row in current.resources))
            pin.row["closed"] = True
        except BaseException as error:
            self.error(pin.label + "-close", error, unknown=True)

    def source_inputs(self, *, first=False):
        """Separate current file bindings, not an expanded stage/cache roster.

        The first read precedes NEW native clean-source admission; later reads
        must match its actual file bindings and bytes. This is not loaded-code
        or uninterrupted source-directory/atomic-snapshot qualification.
        """
        require(type(first) is bool, "BOOTSTRAP_COLLECTION_PHASE_SOURCE_MODE")
        owner, frame = self.live(), self.check()
        require((first and not frame.source_attempted and frame.source_pin is None) or
                (not first and frame.source_pin is not None), "BOOTSTRAP_COLLECTION_PHASE_SOURCE_REENTRY")
        if first:
            _update_collection_phase(self, source_attempted=True)
        opened, rows, result = [], [], None
        try:
            root = owner.acquire("source-directory", lambda: staging.files.public_root(ROOT))
            opened.append(root)
            end = owner.end()
            scripts = owner.acquire("source-directory", lambda: root.open_directory("scripts", deadline=end))
            opened.append(scripts)
            before = tuple(directory.verify() for directory in opened)
            for name in ("hosted_cache_bootstrap_collection.py", "hosted_cache_bootstrap_collect_files.py"):
                raw, binding = self.read_file(scripts, name, 4194304)
                rows.append(("scripts/" + name, raw, origin.encoded(binding)))
            result = (tuple(tuple(info.identity) for info in before), tuple(rows))
            if first:
                _update_collection_phase(self, source_pin=result)  # Actual reads precede callbacks/close.
            require(result == self.check().source_pin and
                    all(directory.verify() == info for directory, info in zip(opened, before)),
                    "BOOTSTRAP_COLLECTION_PHASE_SOURCE_CHANGED")
            owner.end()
        except BaseException as error:
            self.error("collection-phase-source", error)
        finally:
            for directory in reversed(opened):
                owner.close_one(directory)
        self.raise_first()
        return result

    def admit(self):
        """A NEW supplier's actual return, not its provisional session JSON.

        Both query75/final120 are shortened by WORK120. The actual supplier
        LOCAL pair and the later outer RAW-final/WORK-LOCAL sample are distinct.
        No second HTTP service acquisition or recipient-policy installation.
        """
        owner, frame = self.live(), self.check()
        require(not frame.query_attempted and frame.phases[-1].name == "WORK" and frame.source_pin is not None,
                "BOOTSTRAP_COLLECTION_PHASE_QUERY_REENTRY")
        _update_collection_phase(self, query_attempted=True)
        window = frame.window
        began = window.now()
        work = min(frame.limits.ends[0], origin.integer(began + 75 * origin.NS))
        final = min(frame.limits.ends[0], origin.integer(began + 120 * origin.NS))
        pair = (window.deadline(75, limit=work), window.deadline(120, limit=final))
        path = self.handles["phase"].path / "admission"
        supplier = result = None
        owned = False
        try:
            supplier = query.NativeGitQueries(ROOT, path, check_cancel=lambda: window.now(limit=work), owner_deadlines=pair)
            _update_collection_phase(self, query=(supplier, type(supplier), pair, work, final))
            require(type(supplier) is query.NativeGitQueries and id(supplier) not in frame.borrowed,
                    "BOOTSTRAP_COLLECTION_PHASE_QUERY_BORROWED")
            owned = True
            roots = tuple((directory, type(directory), expected,
                tuple(directory_identity(list(directory.identity), frame.limits.clock[0]))) for directory, expected in
                ((supplier.private, path), (supplier.home, path / "query-home")))
            _update_collection_phase(self, query_origin=_CollectionPhaseQueryOrigin(
                object.__getattribute__(supplier, "__dict__"), ROOT, path, roots,
                supplier.resources, supplier.records, supplier.readbacks))
            _collection_phase_query_identity(_collection_phase_frame(self))
            window.now(limit=work)
            supplier.native_host_matches_actions()
            result = bootstrap.admit(ROOT, query_runner=supplier, expected=frame.transition._attempt.admitted)
            _update_collection_phase(self, query_result=result)  # Before retention or post-return checks.
            require(type(result) is I.Admission and result == frame.transition._attempt.admitted,
                    "BOOTSTRAP_COLLECTION_PHASE_READMISSION")
            supplier.retain_admission(result)
            window.now(limit=work)
        except BaseException as error:
            current = _collection_phase_frame(self)
            _update_collection_phase(self, query_errors=(*current.query_errors, ("body", error)))
            self.error("collection-phase-query-body", error)
        finally:
            if owned:
                try:
                    _collection_phase_query_before(self)
                except BaseException as error:
                    current = _collection_phase_frame(self)
                    _update_collection_phase(self, query_errors=(*current.query_errors, ("pre-final", error)))
                    if not any(value is supplier for value in query.QUARANTINE):
                        query.QUARANTINE.append(supplier)
                    self.error("collection-phase-query-before-final", error, unknown=True)
                else:
                    _update_collection_phase(self, query_final_attempted=True)
                    try:
                        supplier._finalize(_collection_phase_frame(self).original)
                        _update_collection_phase(self, query_returned=(True, None, None))
                        _update_collection_phase(self, query_pin=_collection_phase_query_pin(_collection_phase_frame(self), result))
                    except BaseException as error:
                        current = _collection_phase_frame(self)
                        # A returned finalizer with failed post-return validation
                        # is not a thrown finalizer. Keep the actual fact distinct.
                        if current.query_returned is None:
                            _update_collection_phase(self, query_returned=(False, None, None))
                        _update_collection_phase(self, query_errors=(*current.query_errors, ("final", error)))
                        uncertain = current.query_returned is not None and current.query_returned[0] is True
                        if uncertain and not any(value is supplier for value in query.QUARANTINE):
                            query.QUARANTINE.append(supplier)
                        self.error("collection-phase-query-final", error, unknown=uncertain or supplier.unknown)
            try:
                observed = window.now(limit=final)
                current = _collection_phase_frame(self)
                if current.query_returned is not None:
                    _update_collection_phase(self, query_returned=(current.query_returned[0], observed, current.local_last))
            except BaseException as error:
                current = _collection_phase_frame(self)
                _update_collection_phase(self, query_errors=(*current.query_errors, ("outer-return", error)))
                self.error("collection-phase-query-return", error)
            if (owned and supplier.unknown) or query.QUARANTINE or diagnostics._QUARANTINE:
                self.error("collection-phase-query-unknown",
                    origin.OriginError("BOOTSTRAP_COLLECTION_PHASE_QUERY_UNKNOWN"), unknown=True)
        self.raise_first()
        frame = self.check()
        require(owned and frame.query_pin is not None and frame.query_returned[0] is True and
                frame.query_returned[1] is not None and frame.query_returned[2] is not None and
                frame.query_result is result, "BOOTSTRAP_COLLECTION_PHASE_READMISSION")
        directory = self.directory("collection-admission", path)
        require(load_admission(owner, directory) == result, "BOOTSTRAP_COLLECTION_PHASE_READMISSION_CHANGED")
        for name, raw in (("admission.json", result.record), ("original-event.json", result.original_event),
                ("original-policy.json", result.original_policy), ("recipient-public.asc", result.public_key),
                ("session-result.json", owner.read(directory, "session-result.json"))):
            self.remember("admission/" + name, directory, name, raw)
        session = origin.parse(self.records["admission/session-result.json"])
        require(set(session) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"} and
                type(session["schema"]) is int and session["schema"] == 1 and session["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
                type(session["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", session["job"]) and
                type(session["queries"]) is list and type(session["readbacks"]) is list and
                session["result"] == "READY_FOR_CALLER_SEAL" and session["retirement"] == "KNOWN" and
                session["firstError"] is None and session["errors"] == [] and
                origin.encoded(session["queries"]) == origin.encoded(frame.query_origin.records) and
                origin.encoded(session["readbacks"]) == origin.encoded(frame.query_preclose.readbacks),
                "BOOTSTRAP_COLLECTION_PHASE_QUERY_RECORD")
        raw = owner.write(self.handles["phase"], "admission-return.json", {"admissionSha256": origin.digest(result.record),
            "sessionSha256": origin.digest(self.records["admission/session-result.json"]), "clock": origin.clock_value(window.clock),
            "returnedNs": frame.query_returned[1], "ownerDeadlineScope": "ORIGINAL_COLLECTION_WORK_ONLY"})
        self.remember("admission-return", self.handles["phase"], "admission-return.json", raw)
        window.now(limit=final)

    def state_readback(self, *, after):
        """Warmed H throughout; retained/ is empty BEFORE copy, exact AFTER.

        Never call the old producer's empty-retained postlaunch oracle after
        copying. Current descendant lifetimes are not leaf-time baselines.
        """
        require(type(after) is bool, "BOOTSTRAP_COLLECTION_PHASE_STATE_MODE")
        owner, inputs, frame = self.live(), self.inputs(), self.check()
        require((after and frame.leaf_pin is not None) or (not after and not frame.leaf_attempted),
                "BOOTSTRAP_COLLECTION_PHASE_STATE_ORDER")
        closed = frame.predecessor.phases[-1][1]
        request = origin.parse(closed.leaf.request_raw)
        initial = self.directory("initializer", inputs.session, inputs.directories["session"])
        handles = {"session": initial}
        for name in staging.DIRECTORIES[1:]:
            parent = initial if name == "state" else handles["state"]
            handles[name] = self.directory("canonical:" + name, parent.path / name, inputs.directories[name], parent=parent)
        for key, directory, name, raw in (("initializer-context", initial, "initializer-context.json", inputs.context_raw),
                ("canonical-context", handles["state"], "context.json", inputs.canonical_raw),
                ("properties", handles["gradle-home"], "gradle.properties", inputs.properties_raw)):
            self.read_file(directory, name, expected=raw, binding=request["fileBindings"][key])
        facade = self.file_facade()
        staging._names(facade, handles["state"], ("context.json", "gradle-home", "evidence", "cancellations", "gradle.lock"))
        invocation = request["owner"]["productInvocation"]
        staging._names(facade, handles["evidence"], (invocation,))
        staging._names(facade, handles["cancellations"], ())
        # No H enumeration/population claim: the original producer warmed it.
        for name, directory in handles.items():
            require(tuple(directory.verify().identity) == inputs.directories[name],
                    "BOOTSTRAP_COLLECTION_PHASE_INITIALIZER_REPLACED")
        pin = closed.request_pin
        directory = self.directory("reservation", Path(pin.path), pin.directory)
        retained = self.directory("retained", Path(pin.path) / "retained", pin.retained, parent=directory)
        self.read_file(directory, "request.json", expected=closed.leaf.request_raw,
                       binding=staging.files.record(pin.binding_raw))
        staging._names(facade, directory, ("request.json", "retained"))
        if not after:
            staging._names(facade, retained, ())
        container = self.directory("stage-container", inputs.container)
        restore = self.directory("restore-home", inputs.restore, parent=container)
        custody._stage_readback(facade, inputs, container, restore)
        require(custody._sources(facade, inputs) == {name: request[name] for name in ("inputs", "bootstrapInputs", "custodyInputs")},
                "BOOTSTRAP_COLLECTION_PHASE_SOURCE_INPUTS_CHANGED")
        require(request["owner"] == {"job": inputs.canonical["id"], "productInvocation": invocation,
                "sameHomeStopInvocation": invocation} and producer._uuid(invocation) and
                request["evidenceDirectory"] == str(inputs.state / "evidence" / invocation),
                "BOOTSTRAP_COLLECTION_PHASE_RESERVATION_TARGET")
        if after:
            self.current_membership()
        owner.end()

    def manifest(self):
        owner, frame = self.live(), self.check()
        require(not frame.manifest_attempted and frame.query_pin is not None, "BOOTSTRAP_COLLECTION_PHASE_MANIFEST_REENTRY")
        _update_collection_phase(self, manifest_attempted=True)
        files = frame.bound.producer_frame.files
        rows = tuple(tuple(row for row in files if row.key == "canonical-" + name) for name in ("start", "receipt"))
        require(all(len(row) == 1 for row in rows), "BOOTSTRAP_COLLECTION_PHASE_PRODUCER_METADATA_MISSING")
        start, receipt = (row[0] for row in rows)
        require(start.path == receipt.path and start.identity == receipt.identity and start.directory is receipt.directory,
                "BOOTSTRAP_COLLECTION_PHASE_PRODUCER_INVOCATION_CHANGED")
        directory = self.directory("canonical-invocation", start.path, start.identity, parent=self.handles["canonical:evidence"])
        for row in (start, receipt):
            self.read_file(directory, row.name, row.maximum, expected=row.raw, binding=origin.parse(row.binding_raw))
            self.remember(row.key, directory, row.name, row.raw, row.maximum, binding=origin.parse(row.binding_raw))
        raw, binding = self.read_file(directory, "report-manifest.json", 4194304)
        _update_collection_phase(self, manifest_pin=(directory, start.path, start.identity, raw, origin.encoded(binding)))
        self.remember("manifest", directory, "report-manifest.json", raw, 4194304, binding=binding)
        current, inputs = self.check(), self.inputs()
        original = current.bound.returned
        require(original.start_raw == start.raw and original.receipt_raw == receipt.raw,
                "BOOTSTRAP_COLLECTION_PHASE_PRODUCER_METADATA_CHANGED")
        bindings = {row.name: origin.parse(row.binding_raw) for row in (start, receipt)}
        bindings["report-manifest.json"] = origin.parse(current.manifest_pin[4])
        value = collect_files.FileOriginals(original.request_raw, inputs.admitted.record, inputs.canonical_raw,
            start.raw, receipt.raw, raw, current.bound.producer_frame.native.exit_code, start.identity,
            current.predecessor.phases[-1][1].request_pin.retained, origin.encoded(bindings))
        owner.end()
        return value

    def validate_leaf(self):
        """Check the original return's data scope, never reconstruct a leaf run."""
        frame = self.check()
        require(frame.leaf_pin is not None, "BOOTSTRAP_COLLECTION_PHASE_LEAF_MISSING")
        inputs = collect_files._Inputs(frame.leaf_originals)
        raw, inventory_raw, began, checked = frame.leaf_pin[1:]
        require(inventory_raw == inputs.inventory_raw, "BOOTSTRAP_COLLECTION_PHASE_INVENTORY_CHANGED")
        value = staging.files.record(raw)
        fixed = {"schema": 1, "scope": "BOOTSTRAP_CONFIGURATION_FILE_COPY_LEAF_V1",
            "inventorySha256": origin.digest(inventory_raw), "inputProvenance": "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL",
            "collectionState": "COPIED_AND_READ_BACK", "completed": True, "leafHandleClose": "KNOWN",
            "enclosingOwnerRetirement": "NOT_OBSERVED_HERE", "noLoaderObservation": "NOT_OBSERVED",
            "dependencyPopulation": "NOT_ATTESTED", "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "nextPhaseAuthority": False, "exportSaveAuthority": False,
            "readBoundary": "WINDOWS_DECLARED_SIZE_AND_SAME_DESCRIPTOR_VERIFY" if inputs.role == "windows-x64" else
                            "POSIX_POSITIVE_READ_EMPTY_AND_SAME_DESCRIPTOR_VERIFY",
            "sourceDirectory": str(inputs.source), "retainedDirectory": str(inputs.target),
            "directoryBindings": {name: list(identity) for name, identity in inputs.identities.items()}}
        require(set(value) == {*fixed, "counts", "files", "localWindow"} and staging.files.encoded(value) == raw and
                origin.encoded({key: value[key] for key in fixed}) == origin.encoded(fixed),
                "BOOTSTRAP_COLLECTION_PHASE_LEAF_RECORD")
        expected = {}
        def members(tree, prefix=""):
            for name, member in sorted(tree.items()):
                path = prefix + ("/" if prefix else "") + name
                if type(member) is dict:
                    members(member, path)
                else:
                    require(type(member) is collect_files._Member, "BOOTSTRAP_COLLECTION_PHASE_MEMBER_KIND")
                    expected[path] = member
        members(inputs.tree)
        rows = value["files"]
        require(type(rows) is list and len(rows) == len(expected) and
                all(type(row) is dict and set(row) == {"path", "bytes", "sha256", "sourceBinding", "destinationBinding"}
                    for row in rows) and [row["path"] for row in rows] == list(expected),
                "BOOTSTRAP_COLLECTION_PHASE_LEAF_ROSTER")
        aliases, total = set(inputs.identities.values()), 0
        for row in rows:
            member = expected[row["path"]]
            require(type(row["bytes"]) is int and 0 <= row["bytes"] <= member.maximum and
                    (member.size is None or row["bytes"] == member.size) and type(row["sha256"]) is str and
                    re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) and
                    (row["bytes"] != 0 or row["sha256"] == origin.digest(b"")) and
                    (member.sha256 is None or row["sha256"] == member.sha256),
                    "BOOTSTRAP_COLLECTION_PHASE_LEAF_FILE")
            for side in ("source", "destination"):
                binding = row[side + "Binding"]
                require(staging.files._file_binding(binding) and
                        type(binding["identity"][1]) is (str if inputs.role == "windows-x64" else int),
                        "BOOTSTRAP_COLLECTION_PHASE_LEAF_FILE_BINDING")
                identity = tuple(binding["identity"])
                require(identity not in aliases, "BOOTSTRAP_COLLECTION_PHASE_LEAF_FILE_ALIAS")
                aliases.add(identity)
            require(member.binding_raw is None or staging.files.encoded(row["sourceBinding"]) == member.binding_raw,
                    "BOOTSTRAP_COLLECTION_PHASE_ORIGINAL_METADATA_BINDING")
            total += row["bytes"]
        require(total <= collect_files.MAX_BYTES, "BOOTSTRAP_COLLECTION_PHASE_LEAF_PAYLOAD_LIMIT")
        metadata_bytes = sum(expected[name].size for name in collect_files.METADATA)
        counts = {"sourceReadBytes": 2 * total + metadata_bytes, "destinationReadBytes": total,
            "outputBytesRequested": total, "outputBytesAcknowledged": total,
            **{name: inputs.members for name in ("sourceMembers", "destinationMembers", "sourceFinalMembers", "destinationFinalMembers")}}
        require(origin.encoded(value["counts"]) == origin.encoded(counts), "BOOTSTRAP_COLLECTION_PHASE_LEAF_COUNTS")
        window = value["localWindow"]
        require(type(window) is dict and set(window) == {"started", "end", "observed", "scope"} and
                type(window["started"]) is type(began) and window["started"] == began and
                type(window["end"]) in (int, float) and window["end"] == staging._local(began + 120) and
                window["scope"] == "LOCAL120_SHORTENS_CALLER_NOT_SHARED_CLOCK_OR_JOB_ADMISSION" and
                frame.leaf_began[1] <= began <= staging._local(window["observed"]) <= checked < window["end"],
                "BOOTSTRAP_COLLECTION_PHASE_LEAF_LOCAL_WINDOW")
        return value, inputs, expected

    def current_membership(self):
        """Current complete membership/root/file bindings, not an atomic freeze.

        Descendant directories verify their OWN newly opened lifetime. The leaf
        does not export earlier descendant bindings: do not invent continuity.
        No payload rehash/copy, loader operation, or FINAL/READ file work.
        """
        owner = self.live()
        value, inputs, expected = self.validate_leaf()
        rows = {row["path"]: row for row in value["files"]}
        aliases, counts = {}, {(side, final): 0 for side in ("source", "destination") for final in (False, True)}
        def info(binding_info, side, path, directory):
            kind = windows.FileInfo if inputs.role == "windows-x64" else staging.files.PosixInfo
            require(type(binding_info) is kind and binding_info.is_directory is directory,
                    "BOOTSTRAP_COLLECTION_PHASE_CURRENT_FILE_KIND")
            binding = staging.files._info_binding(binding_info)
            require(staging.files._file_binding(binding), "BOOTSTRAP_COLLECTION_PHASE_CURRENT_FILE_BINDING")
            identity, key = tuple(binding["identity"]), (side, path)
            require(identity not in aliases or aliases[identity] == key, "BOOTSTRAP_COLLECTION_PHASE_CURRENT_ALIAS")
            aliases[identity] = key
            return binding
        def names(directory, tree, side, final):
            end = owner.end()
            actual = directory.names(max_names=10000, deadline=end)
            require(type(actual) is tuple and all(type(name) is str for name in actual),
                    "BOOTSTRAP_COLLECTION_PHASE_CURRENT_NAMES")
            counts[(side, final)] += len(actual)
            require(counts[(side, final)] <= 10000 and actual == tuple(sorted(tree)),
                    "BOOTSTRAP_COLLECTION_PHASE_CURRENT_MEMBERS")
            owner.end()
        def walk(directory, tree, side, prefix=""):
            before = directory.verify()
            original = info(before, side, prefix, True)
            if not prefix:
                require(tuple(original["identity"]) == inputs.identities[side],
                        "BOOTSTRAP_COLLECTION_PHASE_CURRENT_ROOT_CHANGED")
            names(directory, tree, side, False)
            for name, member in sorted(tree.items()):
                path = prefix + ("/" if prefix else "") + name
                end = owner.end()
                resource = owner.acquire("directory" if type(member) is dict else "reader", lambda:
                    directory.open_directory(name, deadline=end) if type(member) is dict else
                    directory.open_file(name, max_bytes=expected[path].maximum, deadline=end))
                try:
                    if type(member) is dict:
                        walk(resource, member, side, path)
                    else:
                        first = resource.initial_info
                        require(info(first, side, path, False) == rows[path][side + "Binding"] and
                                first.size == rows[path]["bytes"] and resource.verify() == first,
                                "BOOTSTRAP_COLLECTION_PHASE_CURRENT_FILE_CHANGED")
                    owner.end()
                except BaseException as error:
                    self.error("collection-phase-current-member", error)
                finally:
                    owner.close_one(resource)
                self.raise_first()
            names(directory, tree, side, True)
            require(directory.verify() == before, "BOOTSTRAP_COLLECTION_PHASE_CURRENT_DIRECTORY_CHANGED")
            owner.end()
        for side, key in (("source", "canonical-invocation"), ("destination", "retained")):
            walk(self.handles[key], inputs.tree, side)
        require(all(count == inputs.members for count in counts.values()), "BOOTSTRAP_COLLECTION_PHASE_CURRENT_MEMBER_COUNT")
        return {"scope": "CURRENT_MEMBERSHIP_ROOT_AND_FILE_BINDINGS_NOT_DESCENDANT_CONTINUITY_OR_FREEZE",
                "membersPerSide": inputs.members, "files": len(rows)}

    def pending(self):
        owner, frame = self.live(), self.check()
        require(frame.pending_raw is None and frame.leaf_pin is not None and frame.source_pin is not None,
                "BOOTSTRAP_COLLECTION_PHASE_PENDING_REENTRY")
        raw = owner.write(self.handles["phase"], "collection-pending.json", {"schema": 1,
            "scope": "BOOTSTRAP_COLLECTION_PENDING_PARENT_CLOSE_NOT_RETURN_V1",
            "producerSha256": origin.digest(frame.bound.returned.raw),
            "manifestSha256": origin.digest(frame.manifest_pin[3]), "leafSha256": origin.digest(frame.leaf_pin[1]),
            "inventorySha256": origin.digest(frame.leaf_pin[2]),
            "collectionInputs": {name: origin.digest(raw) for name, raw, _binding in frame.source_pin[1]},
            "sourceBindingScope": "NEW_FILE_BYTES_AND_BINDINGS_AROUND_NATIVE_CLEAN_ADMISSION_NOT_LOADED_CODE_PROOF",
            "noLoaderObservation": "NOT_OBSERVED", "parentClose": "PENDING", "window": frame.window.record(),
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False})
        _update_collection_phase(self, pending_raw=raw)
        self.remember("collection-pending", self.handles["phase"], "collection-pending.json", raw)

def _close_collection_phase(parent):
    """Known NEW obligations only. Expiry forbids acquisition, not known close."""
    frame = _collection_phase_frame(parent)
    owner, window = frame.owner, frame.window
    if owner is not None:
        _collection_phase_state(parent, "CLOSING")
        if frame.phases[-1].name == "WORK":
            try:
                window.advance("FINAL")
            except BaseException as error:
                parent.error("collection-phase-final-start", error)
        try:
            parent.roster()
            frame = _collection_phase_frame(parent)
            require(frame.close_roster is None, "BOOTSTRAP_COLLECTION_PHASE_CLOSE_REENTRY")
            _update_collection_phase(parent,
                close_roster=tuple((id(pin.row), pin.label, id(pin.value)) for pin in frame.resources))
            owner.close()
        except BaseException as error:
            parent.error("collection-phase-resource-close", error)
    for number, handler in _collection_phase_frame(parent).handlers:
        try:
            window.sample(cleanup=True)
        except BaseException as error:
            parent.error("collection-phase-pre-restore-clock", error)
        try:
            signal.signal(number, handler)
            require(signal.getsignal(number) is handler, "BOOTSTRAP_COLLECTION_PHASE_HANDLER_NOT_RESTORED")
            current = _collection_phase_frame(parent)
            _update_collection_phase(parent, restored=(*current.restored, (number, handler)))
        except BaseException as error:
            parent.error("collection-phase-handler-restore", error)
        try:
            window.sample(cleanup=True)
        except BaseException as error:
            parent.error("collection-phase-post-restore-clock", error)
    try:
        parent.roster()
        frame = _collection_phase_frame(parent)
        require(owner is None or (owner.closed is True and frame.owner_closed is True and frame.close_roster is not None and
                all(pin.attempted and pin.closed for pin in frame.resources)), "BOOTSTRAP_COLLECTION_PHASE_CLOSE_INCOMPLETE")
    except BaseException as error:
        parent.error("collection-phase-close-roster", error, unknown=True)


def _run_collection_phase(parent):
    frame = parent.check()
    require(frame.state == "BOUND" and frame.owner is None and frame.window is None and frame.result is None,
            "BOOTSTRAP_COLLECTION_PHASE_RUN_REENTRY")
    _collection_phase_state(parent, "STARTING")  # Consumed BEFORE the first clock.
    try:
        previous, saved = frame.bound.returned, frame.predecessor.frame
        local = staging._local(time.monotonic())
        _update_collection_phase(parent, local_last=local)
        first = origin.clocks.validate_reading(origin.clocks.observe())
        _update_collection_phase(parent, first=first, last=first.nanoseconds)
        require(staging._clock(first.clock) == staging._clock(saved.originals.clock) and
                first.nanoseconds >= previous.checked_ns and local >= previous.checked_local,
                "BOOTSTRAP_COLLECTION_PHASE_PREDECESSOR_CLOCK")
        parent.check()
        proposal = allocation.validate_proposal(saved.originals.proposal_raw, saved.originals.admitted,
            saved.originals.responses, saved.originals.invocation, saved.originals.clock, saved.originals.runner_name)
        names, seconds = ("custody-collect", "custody-collect-final", "custody-collect-read"), (120, 165, 195)
        ends = tuple(min(origin.integer(first.nanoseconds + maximum * origin.NS), proposal["phaseFencesNs"][name],
                         proposal["proposedJobEndNs"]) for name, maximum in zip(names, seconds))
        require(first.nanoseconds < ends[0] <= ends[1] <= ends[2], "BOOTSTRAP_COLLECTION_PHASE_NO_INTERVAL")
        local_ends = tuple(origin.wire._directed_deadline(local, maximum, end, first.nanoseconds)
                           for maximum, end in zip(seconds, ends))
        limits = _CollectionPhaseLimits(staging._clock(first.clock), first.nanoseconds, local, ends, local_ends)
        window, callback = _CollectionPhaseWindow(parent), parent.cancel
        _update_collection_phase(parent, limits=limits, window=window,
            phases=(_CollectionPhaseStep("WORK", first.nanoseconds, local, ends[0], local_ends[0]),))
        parent.window = window
        owner = _CollectionPhaseOwner(local_ends[2], window, first=first, cancelled=callback)
        _update_collection_phase(parent, owner=owner,
            owner_bindings=(owner.resources, owner.errors, owner.admissions, owner.local_end, callback), state="RUNNING")
        parent.owner, parent.state = owner, "RUNNING"
        owner.end()
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handler = signal.getsignal(number)
            current = _collection_phase_frame(parent)
            _update_collection_phase(parent, handlers=(*current.handlers, (number, handler)))
            parent.handlers[number] = handler  # Restore duty precedes the possibly partial install.
            signal.signal(number, lambda signum, _frame: _collection_phase_frame(parent).published[3].append(signum))
            owner.end()
        parent.read_originals()
        parent.state_readback(after=False)
        initial = parent.handles["initializer"]
        parent.directory("phase", initial.path / "configuration-collection-parent", parent=initial, create=True)
        parent.source_inputs(first=True)
        parent.admit()
        parent.source_inputs()
        parent.read_originals()
        parent.state_readback(after=False)
        originals = parent.manifest()
        _invoke_collection_phase_leaf(parent, originals)
        parent.state_readback(after=True)
        parent.source_inputs()
        parent.read_originals()
        parent.pending()
        parent.reread()
        parent.host()
        window.now()  # All file/admission/copy/pending work must actually return in WORK.
    except BaseException as error:
        parent.error("collection-phase-body", error)
    finally:
        _close_collection_phase(parent)
    try:
        frame = parent.closed()
        # The reserved READ slot is used only for post-close clock/return
        # accounting. It is explicitly NOT a native/file read phase.
        frame.window.advance("READ")
        closed = frame.window.now()
        frame = parent.closed()
        require(frame.pending_raw is not None, "BOOTSTRAP_COLLECTION_PHASE_PENDING_MISSING")
        raw = origin.encoded({"schema": 1, "scope": "BOOTSTRAP_COLLECTION_PARENT_CLOSED_OBSERVATIONS_V1",
            "producerSha256": origin.digest(frame.bound.returned.raw), "producerCheckedNs": frame.bound.returned.checked_ns,
            "manifestSha256": origin.digest(frame.manifest_pin[3]), "leafSha256": origin.digest(frame.leaf_pin[1]),
            "inventorySha256": origin.digest(frame.leaf_pin[2]), "pendingSha256": origin.digest(frame.pending_raw),
            "window": frame.window.record(), "closedNs": closed, "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY",
            "resourceCount": len(frame.resources),
            "currentFileObservation": "MEMBERSHIP_ROOT_AND_FILE_BINDINGS_NOT_DESCENDANT_CONTINUITY_OR_FREEZE",
            "noLoaderObservation": "NOT_OBSERVED", "dependencyPopulation": "NOT_ATTESTED",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False})
        checked = frame.window.now(minimum=closed)
        frame = parent.closed()
        require(frame.last == checked, "BOOTSTRAP_COLLECTION_PHASE_FINAL_BOUNDARY_CHANGED")
        result = CollectionPrefix(raw, frame.leaf, frame.manifest_pin[3], checked, frame.local_last)
        result_pin = (object.__getattribute__(result, "__dict__"), raw, frame.manifest_pin[3], checked, frame.local_last)
        _update_collection_phase(parent, result=result, result_pin=result_pin, state="COMPLETE")
        parent.result, parent.state = result, "COMPLETE"
        parent.check()  # Passive; no post-close resource or predecessor call.
        _publish_collection_phase(parent, result)
        return result
    except BaseException as error:
        parent.error("collection-phase-final-return", error)
        _collection_phase_state(parent, "FAILED")
        frame = _collection_phase_frame(parent)
        if frame.owner is not None and frame.unknown and not any(value is frame.owner for value in QUARANTINE):
            QUARANTINE.append(frame.owner)
        raise frame.original


def collect_after_entry(transition):
    """INTERNAL original-call producer/collection; never a prefix adoption API.

    The dormant producer calls this path; no workflow does. Claims consume failure.
    Neither a successful copy nor a configuration-only producer establishes
    no-loader, cache population, tests, admitted5400 or export/save authority.
    """
    parent = _claim_collection_phase(transition)
    try:
        _invoke_collection_phase_begin(parent)
        return _run_collection_phase(parent)
    except BaseException as error:
        if _collection_phase_frame(parent).original is None:
            parent.error("collection-phase-intent", error)
        _collection_phase_state(parent, "FAILED")
        frame = _collection_phase_frame(parent)
        try:
            frame.original.bootstrap_collection_parent = parent
            frame.original.bootstrap_collection_resources = tuple((pin.label, pin.value, pin.attempted, pin.closed)
                                                                    for pin in frame.resources)
            frame.original.bootstrap_collection_custody = "INCOMPLETE" if frame.files else "UNAVAILABLE"
        except BaseException:
            pass
        raise frame.original


@dataclass(frozen=True)
class _CollectionReturnGraph:
    """Finite passive original-return snapshot, not native-resource inspection.

    Pin the selected exact record/tuple families and the older witnesses
    themselves. Bound edges BEFORE materializing containers: a node counter
    alone does not bound a huge scalar-only list. Composed capacity remains
    unqualified; exhaustion refuses, never widens an earlier graph's limits.
    These limits do not cap the preceding retained-predecessor validators.
    """
    nodes: tuple = field(repr=False)
    paths: tuple = field(repr=False)

    @classmethod
    def capture(cls, frame):
        records = (NewEntryTransition, _EntryAttempt, ClosedEntryTransition, OriginalEntry, OriginalPhase,
            Owner, _StagingFileOwner, origin.Fence, _NewEntryWindow, I.Admission,
            origin.clocks.Reading, origin.clocks.ClockIdentity, _RecipientParent, _InitializerParent,
            _RecipientParentWindow, _InitializerWindow, _RecipientParentBindings, _RecipientResource,
            _ParentControl, _RecipientPredecessorGraph, _InitializerPredecessor, _InitializationInputs,
            initialization.InstalledToolchains, InitializationPrefix, _StagingPhaseParent, _StagingWindow,
            _StagingPhaseReturn, StagingPrefix, custody.StagedEvidence, custody.ReservationEvidence,
            ConfigurationCustodyPrefix, staging.Originals, staging.PhaseStart, staging.LeafEvidence,
            _StagingSequence, _StagingClosedGraph, _ProducerParent, _ProducerWindow, _ProducerOwner,
            ConfigurationPrefix, _CollectionOrigin, _CollectionPhaseParent, _CollectionPhaseOwner,
            _CollectionPhaseWindow, CollectionPrefix, collect_files.FileOriginals,
            collect_files.FileCollectionEvidence, query.NativeGitQueries)
        sequences = (list, tuple, _StagingFrame, _StagingLimits, _CustodyRequestPin, _StagingSequenceFrame,
            _ProducerFrame, _ProducerPredecessor, _ProducerLimits, _ProducerNative, _ProducerPhase,
            _ProducerResource, _ProducerFile, _ProducerCapture, _CollectionOriginFrame,
            _CollectionPhaseFrame, _CollectionPhaseLimits, _CollectionPhaseStep, _CollectionPhaseResource,
            _CollectionPhaseFile, _CollectionPhaseQueryOrigin, _CollectionPhaseQueryBefore)
        scalars = (type(None), bool, int, float, str, bytes, signal.Signals)
        require(type(frame) is _CollectionPhaseFrame, "BOOTSTRAP_COLLECTION_RETURN_GRAPH_KIND")
        pending, seen, nodes, paths, path_ids = [frame], set(), [], [], {}
        edges = 0

        def path_pin(directory, kind, path, identity):
            require(type(identity) is tuple and len(identity) == 2, "BOOTSTRAP_COLLECTION_RETURN_PATH_IDENTITY")
            # Preserve this runner's original role grammar (including Windows
            # string file IDs), not a different backend's tighter byte grammar.
            directory_identity(list(identity), frame.limits.clock[0])
            old = path_ids.get(id(directory))
            pin = (directory, kind, path, identity)
            if old is not None:
                require(old[0] is directory and old[1] is kind and type(old[2]) is type(path) and
                        old[2] == path and all(type(item) is type(prior) and item == prior
                            for item, prior in zip(identity, old[3])), "BOOTSTRAP_COLLECTION_RETURN_PATH_ALIAS")
                return
            require(len(paths) < 10000, "BOOTSTRAP_COLLECTION_RETURN_PATH_LIMIT")
            path_ids[id(directory)] = pin
            paths.append(pin)

        require(type(frame.handles) is type(frame.files) is tuple and
                len(frame.handles) + len(frame.files) <= 10000, "BOOTSTRAP_COLLECTION_RETURN_PATH_LIMIT")
        for _key, directory, path, identity in frame.handles:
            path_pin(directory, type(directory), path, identity)
        for row in frame.files:
            require(type(row) is _CollectionPhaseFile, "BOOTSTRAP_COLLECTION_RETURN_FILE_KIND")
            path_pin(row.directory, type(row.directory), row.path, row.identity)
        while pending:
            value = pending.pop()
            kind = type(value)
            if kind in scalars or id(value) in seen:
                continue
            seen.add(id(value))
            require(len(seen) <= 10000, "BOOTSTRAP_COLLECTION_RETURN_NODE_LIMIT")
            if kind is dict:
                edges += 2 * len(value)
                require(edges <= 10000, "BOOTSTRAP_COLLECTION_RETURN_EDGE_LIMIT")
                saved, mode = tuple(value.items()), "mapping"
                require(all(type(key) in scalars for key, _item in saved), "BOOTSTRAP_COLLECTION_RETURN_GRAPH_KEY")
                pending.extend(item for pair in saved for item in pair)
            elif kind in sequences:
                edges += len(value)
                require(edges <= 10000, "BOOTSTRAP_COLLECTION_RETURN_EDGE_LIMIT")
                saved, mode = tuple(value), "sequence"
                pending.extend(saved)
            elif kind in records:
                edges += 1
                require(edges <= 10000, "BOOTSTRAP_COLLECTION_RETURN_EDGE_LIMIT")
                saved, mode = object.__getattribute__(value, "__dict__"), "record"
                pending.append(saved)
                if kind is _StagingClosedGraph:
                    # Use its ORIGINAL path witnesses, not a late baseline of
                    # whatever attributes its old resource now exposes.
                    require(type(value.paths) is tuple and len(value.paths) <= 10000,
                            "BOOTSTRAP_COLLECTION_RETURN_PATH_LIMIT")
                    for row in value.paths:
                        require(type(row) is tuple and len(row) == 4, "BOOTSTRAP_COLLECTION_RETURN_PATH_KIND")
                        path_pin(*row)
            else:
                saved, mode = None, "opaque"
            nodes.append((value, kind, mode, saved))
        graph = cls(tuple(nodes), tuple(paths))
        graph.checked()
        return graph

    def checked(self):
        scalars = (type(None), bool, int, float, str, bytes, signal.Signals)
        def same(actual, old):
            return actual is old or (type(actual) is type(old) and type(old) in scalars and actual == old)
        require(type(self.nodes) is type(self.paths) is tuple and len(self.nodes) <= 10000 and len(self.paths) <= 10000,
                "BOOTSTRAP_COLLECTION_RETURN_GRAPH_LIMIT")
        for value, kind, mode, saved in self.nodes:
            require(type(value) is kind, "BOOTSTRAP_COLLECTION_RETURN_GRAPH_CHANGED")
            if mode == "record":
                valid = object.__getattribute__(value, "__dict__") is saved
            elif mode == "mapping":
                valid = len(value) == len(saved) and all(same(key, old_key) and same(item, old_item)
                    for (key, item), (old_key, old_item) in zip(value.items(), saved))
            elif mode == "sequence":
                valid = len(value) == len(saved) and all(same(item, old) for item, old in zip(value, saved))
            else:
                valid = mode == "opaque"
            require(valid, "BOOTSTRAP_COLLECTION_RETURN_GRAPH_CHANGED")
        for directory, kind, path, identity in self.paths:
            require(type(directory) is kind, "BOOTSTRAP_COLLECTION_RETURN_PATH_CHANGED")
            actual = directory.identity
            require(type(directory.path) is type(path) and directory.path == path and
                    type(actual) in (tuple, list) and len(actual) == 2 and
                    all(type(item) is type(prior) and item == prior for item, prior in zip(actual, identity)),
                    "BOOTSTRAP_COLLECTION_RETURN_PATH_CHANGED")


def _check_collection_return_graph(pin):
    graph, original = pin.graph, pin.graph_pin
    require(type(graph) is _CollectionReturnGraph and type(original) is tuple and len(original) == 3 and
            object.__getattribute__(graph, "__dict__") is original[0] and len(original[0]) == 2 and
            set(original[0]) == {"nodes", "paths"} and
            graph.nodes is original[1] and graph.paths is original[2], "BOOTSTRAP_COLLECTION_RETURN_WITNESS_CHANGED")
    graph.checked()


def _collection_phase_closed_return(parent, returned):
    """Compare retained data only; no closed check/roster/owner/query/clock call.

    The original publication supplies authority for WHICH return this is, not a
    new native observation. In particular query pre-final coverage, descendant
    continuity and current H contents cannot be retroactively strengthened.
    """
    frame = _collection_phase_frame(parent)
    # Bound these projections before allocating tuples/sets. Native/leaf work
    # already has narrower bounds; this is not authority to grow its rosters.
    require(type(frame.published) is tuple and len(frame.published) == 4 and
            type(frame.handles) is type(frame.files) is type(frame.close_roster) is tuple and
            len(frame.handles) <= 4096 and len(frame.files) <= 4096 and len(frame.close_roster) <= 4096 and
            type(frame.handlers) is type(frame.restored) is tuple and len(frame.handlers) <= 3 and
            all(type(value) is dict and len(value) <= 4096 for value in (parent.handles, parent.records, parent.handlers)) and
            type(frame.result_pin) is tuple and len(frame.result_pin) == 5 and
            type(frame.manifest_pin) is tuple and len(frame.manifest_pin) == 5 and
            type(frame.leaf_pin) is tuple and len(frame.leaf_pin) == 5,
            "BOOTSTRAP_COLLECTION_RETURN_CONTAINER_LIMIT")
    require(type(parent) is _CollectionPhaseParent and type(returned) is CollectionPrefix and
            parent.transition is frame.transition and parent.state == frame.state == "COMPLETE" and
            parent.result is frame.result is returned and parent.original is frame.original is None and
            parent.unknown is frame.unknown is False and frame.errors == frame.foreign == frame.expired_closes == () and
            parent.owner is frame.owner and parent.window is frame.window and
            parent.handles is frame.published[0] and parent.records is frame.published[1] and
            parent.handlers is frame.published[2] and parent.cancelled is frame.published[3] and
            type(parent.cancelled) is list and parent.cancelled == [], "BOOTSTRAP_COLLECTION_RETURN_NOT_COMPLETE")
    require(_checked_collection_origin(frame.binding) is frame.bound and frame.bound.transition is frame.transition and
            frame.predecessor is frame.bound.producer_frame.predecessor,
            "BOOTSTRAP_COLLECTION_RETURN_PREDECESSOR_CHANGED")
    owner, window, bindings = frame.owner, frame.window, frame.owner_bindings
    require(type(owner) is _CollectionPhaseOwner and type(window) is _CollectionPhaseWindow and
            window.call is parent and _collection_phase_owner_frame(owner) is frame and
            _collection_phase_window_frame(window) is frame and type(bindings) is tuple and len(bindings) == 5 and
            owner.closed is frame.owner_closed is True and owner.original is None and owner.unknown is False and
            owner.resources is bindings[0] and owner.errors is bindings[1] and owner.admissions is bindings[2] and
            owner.errors == [] and type(owner.local_end) is type(bindings[3]) and owner.local_end == bindings[3] and
            owner.cancelled is bindings[4] and owner.first is frame.first and owner.fence is window and
            owner.work_limit is owner.final_limit is None and owner.early_last == frame.limits.first and
            owner.local_end == frame.limits.local_ends[-1], "BOOTSTRAP_COLLECTION_RETURN_OWNER_NOT_CLOSED")
    require(type(frame.resources) is tuple and type(owner.resources) is list and
            len(frame.resources) == len(owner.resources) == len(frame.close_roster) <= 4096 and
            len({id(pin.row) for pin in frame.resources}) == len(frame.resources) and
            len({id(pin.value) for pin in frame.resources}) == len(frame.resources) and
            frame.handlers == frame.restored and tuple(parent.handlers.items()) == frame.handlers and
            tuple(parent.handles.items()) == tuple((row[0], row[1]) for row in frame.handles) and
            tuple(parent.records.items()) == tuple((row.key, row.raw) for row in frame.files),
            "BOOTSTRAP_COLLECTION_RETURN_ROSTER")
    for row, pin, closed in zip(owner.resources, frame.resources, frame.close_roster):
        require(type(pin) is _CollectionPhaseResource and type(row) is dict and len(row) == 4 and
                set(row) == {"label", "owner", "attempted", "closed"} and row is pin.row and
                type(pin.label) is str and row["label"] == pin.label and row["owner"] is pin.value and
                type(pin.value) is pin.kind and row["attempted"] is row["closed"] is pin.attempted is pin.closed is True and
                closed == (id(row), pin.label, id(pin.value)), "BOOTSTRAP_COLLECTION_RETURN_ROSTER")
    require(type(frame.limits) is _CollectionPhaseLimits and type(frame.phases) is tuple and len(frame.phases) == 3 and
            all(type(row) is _CollectionPhaseStep for row in frame.phases) and
            tuple(row.name for row in frame.phases) == ("WORK", "FINAL", "READ") and
            staging._clock(frame.first.clock) == frame.limits.clock and frame.first.nanoseconds == frame.limits.first and
            frame.limits.first >= origin.integer(frame.bound.returned.checked_ns) and
            frame.limits.local_start >= staging._local(frame.bound.returned.checked_local) and
            type(frame.last) is type(returned.checked_ns) is int and frame.last == returned.checked_ns and
            type(frame.local_last) is type(returned.checked_local) and
            staging._local(frame.local_last) == staging._local(returned.checked_local),
            "BOOTSTRAP_COLLECTION_RETURN_HIGHWATER")
    require(type(frame.limits.ends) is type(frame.limits.local_ends) is tuple and
            len(frame.limits.ends) == len(frame.limits.local_ends) == 3 and
            frame.limits.first < frame.limits.ends[0] <= frame.limits.ends[1] <= frame.limits.ends[2] and
            frame.limits.local_start < frame.limits.local_ends[0] <= frame.limits.local_ends[1] <= frame.limits.local_ends[2],
            "BOOTSTRAP_COLLECTION_RETURN_LIMITS")
    raw_previous, local_previous = frame.limits.first, frame.limits.local_start
    for index, (phase, maximum) in enumerate(zip(frame.phases, (120, 45, 30))):
        require(raw_previous <= origin.integer(phase.started) <= frame.last < frame.phases[-1].end and
                local_previous <= staging._local(phase.local_started) <= frame.local_last < frame.phases[-1].local_end and
                phase.started < origin.integer(phase.end) <= min(origin.integer(frame.limits.ends[index]),
                    phase.started + maximum * origin.NS) and
                phase.local_started < staging._local(phase.local_end) <= min(staging._local(frame.limits.local_ends[index]),
                    phase.local_started + maximum), "BOOTSTRAP_COLLECTION_RETURN_CHRONOLOGY")
        raw_previous, local_previous = phase.started, phase.local_started
    require(frame.phases[0] == _CollectionPhaseStep("WORK", frame.limits.first, frame.limits.local_start,
                frame.limits.ends[0], frame.limits.local_ends[0]) and frame.phases[-1].started < frame.phases[-2].end and
            frame.phases[-1].local_started < frame.phases[-2].local_end,
            "BOOTSTRAP_COLLECTION_RETURN_CHRONOLOGY")
    require(frame.query_attempted is frame.query_final_attempted is True and frame.query_errors == () and
            type(frame.query_returned) is tuple and len(frame.query_returned) == 3 and frame.query_returned[0] is True and
            frame.query_pin is not None and frame.query_result is not None and
            frame.phases[0].started <= origin.integer(frame.query_returned[1]) < frame.query[4] <= frame.phases[0].end and
            frame.phases[0].local_started <= staging._local(frame.query_returned[2]) < frame.phases[0].local_end,
            "BOOTSTRAP_COLLECTION_RETURN_QUERY_NOT_CLOSED")
    _collection_phase_query_identity(frame)
    _collection_phase_query_checked(frame)
    require(frame.manifest_attempted is frame.leaf_attempted is frame.source_attempted is True and
            frame.source_pin is not None and frame.leaf_pin is not None and
            type(frame.leaf_originals) is collect_files.FileOriginals and
            collect_files._capture(frame.leaf_originals) == frame.leaf_originals_pin and
            type(frame.leaf) is collect_files.FileCollectionEvidence and returned.leaf is frame.leaf and
            object.__getattribute__(frame.leaf, "__dict__") is frame.leaf_pin[0] and
            len(frame.leaf_pin[0]) == 4 and set(frame.leaf_pin[0]) == {"raw", "inventory_raw", "local_started", "checked_local"} and
            all(type(value) is type(old) and value == old for value, old in zip(
                (frame.leaf.raw, frame.leaf.inventory_raw, frame.leaf.local_started, frame.leaf.checked_local), frame.leaf_pin[1:])) and
            returned.manifest_raw == frame.manifest_pin[3] == frame.leaf_originals.manifest_raw,
            "BOOTSTRAP_COLLECTION_RETURN_LEAF_CHANGED")
    require(type(returned.raw) is type(returned.manifest_raw) is type(frame.pending_raw) is bytes and
            all(0 < len(raw) <= 4194304 for raw in (returned.raw, returned.manifest_raw, frame.pending_raw)) and
            object.__getattribute__(returned, "__dict__") is frame.result_pin[0] and
            len(frame.result_pin[0]) == 5 and set(frame.result_pin[0]) == {"raw", "leaf", "manifest_raw", "checked_ns", "checked_local"} and
            all(type(value) is type(old) and value == old for value, old in zip(
                (returned.raw, returned.manifest_raw, returned.checked_ns, returned.checked_local), frame.result_pin[1:])),
            "BOOTSTRAP_COLLECTION_RETURN_RESULT_CHANGED")
    value = origin.parse(returned.raw)
    closed = origin.integer(value.get("closedNs"))
    require(frame.phases[-1].started <= closed <= frame.last, "BOOTSTRAP_COLLECTION_RETURN_CLOSED_TIME")
    expected = {"schema": 1, "scope": "BOOTSTRAP_COLLECTION_PARENT_CLOSED_OBSERVATIONS_V1",
        "producerSha256": origin.digest(frame.bound.returned.raw), "producerCheckedNs": frame.bound.returned.checked_ns,
        "manifestSha256": origin.digest(frame.manifest_pin[3]), "leafSha256": origin.digest(frame.leaf_pin[1]),
        "inventorySha256": origin.digest(frame.leaf_pin[2]), "pendingSha256": origin.digest(frame.pending_raw),
        "window": {"clock": origin.clock_value(frame.first.clock), "firstNs": frame.limits.first,
            "globalEndsNs": dict(zip(("WORK", "FINAL", "READ"), frame.limits.ends)),
            "phases": [{"phase": row.name, "startedNs": row.started, "endNs": row.end} for row in frame.phases],
            "readSlotScope": "POST_CLOSE_RETURN_OBSERVATIONS_ONLY_NO_FILE_READ_EXECUTION", "budgetAcceptance": "NOT_ADMITTED"},
        "closedNs": closed, "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "resourceCount": len(frame.resources),
        "currentFileObservation": "MEMBERSHIP_ROOT_AND_FILE_BINDINGS_NOT_DESCENDANT_CONTINUITY_OR_FREEZE",
        "noLoaderObservation": "NOT_OBSERVED", "dependencyPopulation": "NOT_ATTESTED", "nextPhaseAuthority": False,
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    require(returned.raw == origin.encoded(expected), "BOOTSTRAP_COLLECTION_RETURN_RECORD_CHANGED")
    require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
            "BOOTSTRAP_COLLECTION_RETURN_PRIOR_UNKNOWN")
    return frame


@dataclass(eq=False)
class _NoLoaderOrigin:
    """Private in-call binding only; no new owner, absence call or public token."""
    transition: object = field(repr=False)
    state: str = "CLAIMED"
    collection: object = field(default=None, repr=False)
    returned: object = field(default=None, repr=False)
    original: object = field(default=None, repr=False)


_NoLoaderOriginFrame = namedtuple("_NoLoaderOriginFrame", "call transition state collection returned pin original",
                                defaults=(None,) * 7)


def _no_loader_origin_controls():
    operation, lookup, result_lookup = collect_after_entry, _collection_phase_original_call, _collection_phase_original_result
    attempts, frames, lock = {}, {}, threading.Lock()

    def roots():
        require(collect_after_entry is operation and _collection_phase_original_call is lookup and
                _collection_phase_original_result is result_lookup, "BOOTSTRAP_NO_LOADER_ORIGINAL_OPERATION_CHANGED")
        _collection_phase_roots()

    def claim(transition):
        roots()
        require(type(transition) is NewEntryTransition, "BOOTSTRAP_NO_LOADER_TRANSITION_KIND")
        with lock:
            require(id(transition) not in attempts, "BOOTSTRAP_NO_LOADER_ALREADY_CLAIMED")
            call = _NoLoaderOrigin(transition)
            attempts[id(transition)] = (transition, call)
            frames[id(call)] = _NoLoaderOriginFrame(call=call, transition=transition, state="CLAIMED")
        return call

    def frame(call):
        saved = frames.get(id(call))
        require(type(call) is _NoLoaderOrigin and type(saved) is _NoLoaderOriginFrame and saved.call is call,
                "BOOTSTRAP_NO_LOADER_NOT_CLAIMED")
        row = attempts.get(id(saved.transition))
        require(type(row) is tuple and len(row) == 2 and row[0] is saved.transition and row[1] is call,
                "BOOTSTRAP_NO_LOADER_NOT_CLAIMED")
        return saved

    def update(call, **values):
        frames[id(call)] = frame(call)._replace(**values)
        return frames[id(call)]

    def invoke(call):
        saved = frame(call)
        roots()
        require(saved.state == call.state == "CLAIMED" and call.transition is saved.transition and
                call.collection is saved.collection is None and call.returned is saved.returned is None and
                call.original is saved.original is None, "BOOTSTRAP_NO_LOADER_COLLECTION_REENTRY")
        update(call, state="INVOKING")
        call.state = "INVOKING"
        returned = operation(saved.transition)  # No claim lock held during the fixed original call.
        update(call, returned=returned, state="RETURNED")
        call.returned, call.state = returned, "RETURNED"  # Preserve actual return BEFORE fallible lookup.
        roots()
        parent = lookup(saved.transition)
        update(call, collection=parent)
        call.collection = parent
        pin = result_lookup(parent)
        update(call, pin=pin)
        require(pin.result is returned and _collection_phase_closed_return(parent, returned) is pin.frame,
                "BOOTSTRAP_NO_LOADER_NOT_ORIGINAL_COLLECTION_RETURN")

    return claim, frame, update, invoke, roots


(_claim_no_loader_origin, _no_loader_origin_frame, _update_no_loader_origin,
 _invoke_no_loader_collection, _no_loader_origin_roots) = _no_loader_origin_controls()
del _no_loader_origin_controls


def _checked_no_loader_origin(call):
    saved = _no_loader_origin_frame(call)
    _no_loader_origin_roots()
    require(call.transition is saved.transition and call.state == saved.state == "BOUND" and
            call.collection is saved.collection and call.returned is saved.returned and
            call.original is saved.original is None and type(saved.pin) is _CollectionPhaseResultPin,
            "BOOTSTRAP_NO_LOADER_ORIGIN_NOT_BOUND")
    require(_collection_phase_original_call(saved.transition) is saved.collection and
            _collection_phase_original_result(saved.collection) is saved.pin and saved.pin.result is saved.returned and
            _collection_phase_closed_return(saved.collection, saved.returned) is saved.pin.frame,
            "BOOTSTRAP_NO_LOADER_COLLECTION_CHANGED")
    return saved


def _begin_no_loader_after_entry(transition):
    """INTERNAL once-claimed binding, NOT a no-loader owner or execution step.

    Never adopts supplied CollectionPrefix data or a prior direct collector.
    Original return pins stay closed; no method/clock on a predecessor is called.
    The directory-only parent stays inside this original enclosing call and
    supplies NEW ownership/admission/fences. No workflow invokes this chain.
    """
    call = _claim_no_loader_origin(transition)
    try:
        _invoke_no_loader_collection(call)
        _update_no_loader_origin(call, state="BOUND")
        call.state = "BOUND"
        _checked_no_loader_origin(call)
        return call
    except BaseException as error:
        saved = _no_loader_origin_frame(call)
        first = error if saved.original is None else saved.original
        _update_no_loader_origin(call, state="FAILED", original=first)
        call.state, call.original = "FAILED", first
        try:
            first.bootstrap_no_loader_origin = call
        except BaseException:
            pass  # Private claim keeps actual return/references and the first error.
        raise first



@dataclass(frozen=True)
class NoLoaderPrefix:
    """Original same-call observation, not uninstall, freeze or export authority."""
    raw: bytes = field(repr=False)
    leaf: object = field(repr=False)
    checked_ns: int
    checked_local: float


def _no_loader_parent_controls():
    """One small, directory-only owner around the accepted absence leaf.

    Mutable ownership state stays in the original call's closure. The leaf gets
    only its existing owner protocol, not a constructor, deadline setter, file
    writer or predecessor owner. Retained calls are private failure custody,
    not a code-replacement sandbox or encrypted evidence delivery.
    """
    begin, checked = _begin_no_loader_after_entry, _checked_no_loader_origin
    module, operation = no_loader, no_loader.observe_absence
    input_kind, result_kind, inputs_kind = no_loader.HomeOriginals, no_loader.AbsenceEvidence, no_loader._Inputs
    prefix_kind, capture = NoLoaderPrefix, no_loader._capture
    calls, lock = {}, threading.Lock()

    def roots():
        require(_begin_no_loader_after_entry is begin and _checked_no_loader_origin is checked and
                no_loader is module and module.observe_absence is operation and
                module.HomeOriginals is input_kind and module.AbsenceEvidence is result_kind and
                module._Inputs is inputs_kind and module._capture is capture and NoLoaderPrefix is prefix_kind,
                "BOOTSTRAP_NO_LOADER_PARENT_OPERATION_CHANGED")
        _no_loader_origin_roots()

    def execute(transition):
        roots()
        require(type(transition) is NewEntryTransition, "BOOTSTRAP_NO_LOADER_PARENT_TRANSITION")
        with lock:
            require(id(transition) not in calls, "BOOTSTRAP_NO_LOADER_PARENT_ALREADY_CLAIMED")
            state = {"transition": transition, "binding": None, "bound": None, "owner": None,
                "leaf": None, "leaf_pin": None, "result": None, "result_pin": None,
                "original": None, "unknown": False, "closed": False, "complete": False,
                "resources": [], "pins": [], "returns": [], "errors": [], "handlers": [],
                "restored": [], "cancelled": [], "phases": [], "expired": set()}
            calls[id(transition)] = state  # Claim BEFORE the fixed original collection call.
        ledger, pins = state["resources"], state["pins"]
        owner = bound = originals = inputs = None
        first = last = local_last = None
        ends = local_ends = ()
        phase = -1
        issued_end = None
        expiry = None

        def error(stage, failure, *, unknown=False):
            state["complete"] = False
            if state["original"] is None:
                state["original"] = failure
            state["unknown"] |= unknown
            try:
                detail = diagnostics._exception_detail(failure)
                state["unknown"] |= detail["retirementUnknown"]
                require(len(state["errors"]) < 64, "BOOTSTRAP_NO_LOADER_PARENT_ERROR_LIMIT")
                state["errors"].append(origin.encoded({"stage": stage, "detail": detail}))
            except BaseException:
                state["unknown"] = True  # Never replace an unannotatable/falsey first failure.

        def raise_first():
            if state["original"] is not None:
                raise state["original"]

        def roster():
            try:
                require(len(ledger) == len(pins) <= 2, "BOOTSTRAP_NO_LOADER_PARENT_ROSTER")
                for row, pin in zip(ledger, pins):
                    saved, label, value, kind, attempted, closed = pin
                    require(row is saved and type(row) is dict and len(row) == 4 and
                            set(row) == {"label", "owner", "attempted", "closed"} and
                            type(row["label"]) is str and row["label"] == label and
                            row["owner"] is value and type(value) is kind and
                            row["attempted"] is attempted and row["closed"] is closed,
                            "BOOTSTRAP_NO_LOADER_PARENT_ROSTER")
            except BaseException as failure:
                error("roster", failure, unknown=True)
                raise

        def check():
            roots()
            require(bound is not None and checked(state["binding"]) is bound and
                    bound.transition is transition, "BOOTSTRAP_NO_LOADER_PARENT_PREDECESSOR_CHANGED")
            roster()
            require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                    "BOOTSTRAP_NO_LOADER_PARENT_PRIOR_UNKNOWN")
            if inputs is not None:
                inputs.unchanged()

        def cancel():
            check()
            cancellation(state["cancelled"])
            for callback in bound.pin.frame.predecessor.frame.callbacks:
                callback()
                check()
            cancellation(state["cancelled"])

        def sample(*, cleanup=False):
            nonlocal last, local_last, expiry
            expiry = None
            if not cleanup:
                check()
            before = staging._local(time.monotonic())
            require(before >= local_last, "BOOTSTRAP_NO_LOADER_PARENT_LOCAL_BACKWARDS")
            local_last = before
            observed = origin.clocks.checked_now(first.clock, minimum_ns=last)
            require(observed >= last, "BOOTSTRAP_NO_LOADER_PARENT_RAW_BACKWARDS")
            last = observed
            after = staging._local(time.monotonic())
            require(after >= local_last, "BOOTSTRAP_NO_LOADER_PARENT_LOCAL_BACKWARDS")
            local_last = after
            current = state["phases"][-1]
            if observed >= current[2] or after >= current[3]:
                expiry = origin.OriginError("BOOTSTRAP_NO_LOADER_PARENT_EXPIRED")
                raise expiry
            return before, observed

        def close_clock():
            try:
                sample(cleanup=True)
            except BaseException as failure:
                if failure is not expiry or phase not in state["expired"]:
                    if failure is expiry:
                        state["expired"].add(phase)
                    error("close-clock", failure)

        def advance():
            nonlocal phase, last, local_last
            phase += 1  # Consumed even when the first observation fails.
            require(phase in (1, 2), "BOOTSTRAP_NO_LOADER_PARENT_PHASE_REENTRY")
            previous = state["phases"][-1]
            state["phases"].append((None, None, 0, 0.0))
            # Known cleanup still proceeds if an observation/fence fails.
            local = staging._local(time.monotonic())
            require(local >= local_last, "BOOTSTRAP_NO_LOADER_PARENT_LOCAL_BACKWARDS")
            local_last = local  # Retain this actual reading even if RAW then fails.
            observed = origin.clocks.checked_now(first.clock, minimum_ns=last)
            require(observed >= last, "BOOTSTRAP_NO_LOADER_PARENT_RAW_BACKWARDS")
            last = observed
            if phase == 2:
                require(observed < previous[2] and local < previous[3], "BOOTSTRAP_NO_LOADER_PARENT_RETURN_EXPIRED")
            seconds = 45 if phase == 1 else 30
            end = min(ends[phase], origin.integer(observed + seconds * origin.NS))
            local_end = min(local_ends[phase], origin.wire._directed_deadline(local, seconds, end, observed))
            state["phases"][-1] = (observed, local, end, local_end)
            sample(cleanup=phase == 1)

        class DirectoryOwner:
            __slots__ = ()  # No mutable public flags or alternate operations.
            resources = property(lambda self: ledger)
            original = property(lambda self: state["original"])
            unknown = property(lambda self: state["unknown"])
            closed = property(lambda self: state["closed"])
            cancelled = property(lambda self: cancel)

            def error(self, stage, failure, *, unknown=False):
                error(stage, failure, unknown=unknown)

            def end(self):
                nonlocal issued_end
                raise_first()
                require(phase == 0 and not self.closed and not self.unknown,
                        "BOOTSTRAP_NO_LOADER_PARENT_NOT_LIVE")
                cancel()
                local, observed = sample()
                issued_end = min(issued_end, origin.wire._directed_deadline(local, 90, ends[0], observed))
                require(local_last < issued_end, "BOOTSTRAP_NO_LOADER_PARENT_EXPIRED")
                return issued_end

            def acquire(self, label, factory):
                self.end()
                require(type(label) is str and label in (
                    "bootstrap-collection-no-loader-home", "bootstrap-collection-no-loader-init") and
                    len(pins) < 2 and len(state["returns"]) < 2, "BOOTSTRAP_NO_LOADER_PARENT_RESOURCE")
                try:
                    value = factory()
                except BaseException as failure:
                    error("allocation", failure, unknown=True)
                    raise
                state["returns"].append(value)  # Retain BEFORE fallible kind/borrow/roster checks.
                try:
                    require(type(value) is inputs.kind and not any(value is pin[2] for pin in pins) and
                            not any(value is row[0] for row in bound.pin.graph.nodes),
                            "BOOTSTRAP_NO_LOADER_PARENT_BORROWED_RESOURCE")
                except BaseException as failure:
                    error("resource-return", failure, unknown=True)
                    raise
                row = {"label": label, "owner": value, "attempted": False, "closed": False}
                pins.append((row, label, value, type(value), False, False))
                ledger.append(row)
                self.end()
                return value

            def close_one(self, value):
                index = next((i for i, pin in enumerate(pins) if pin[2] is value), None)
                if index is None:
                    error("foreign-close", origin.OriginError("BOOTSTRAP_NO_LOADER_PARENT_FOREIGN_RESOURCE"), unknown=True)
                    return
                pin = pins[index]
                if pin[4]:
                    return
                try:
                    roster()
                    require(not self.unknown, "BOOTSTRAP_NO_LOADER_PARENT_UNKNOWN")
                except BaseException as failure:
                    error("close-binding", failure, unknown=True)
                    return
                close_clock()
                try:
                    # The clock/diagnostic boundary can change knownness or
                    # reenter a close. Never dispatch using the earlier pin.
                    roster()
                    require(not self.unknown and not QUARANTINE and not query.QUARANTINE and
                            not diagnostics._QUARANTINE, "BOOTSTRAP_NO_LOADER_PARENT_UNKNOWN")
                    if pins[index][4]:
                        return  # A known inner close already consumed this duty.
                    require(pins[index] is pin, "BOOTSTRAP_NO_LOADER_PARENT_CLOSE_CHANGED")
                except BaseException as failure:
                    error("post-clock-close-binding", failure, unknown=True)
                    return
                pins[index] = (*pin[:4], True, False)
                pin[0]["attempted"] = True
                try:
                    value.close()
                    pins[index] = (*pin[:4], True, True)
                    pin[0]["closed"] = True
                    roster()
                except BaseException as failure:
                    error("directory-close", failure, unknown=True)
                close_clock()

        def leaf_pin():
            value = state["leaf"]
            require(type(value) is result_kind, "BOOTSTRAP_NO_LOADER_PARENT_LEAF_KIND")
            dictionary = object.__getattribute__(value, "__dict__")
            require(len(dictionary) == 3 and set(dictionary) == {"raw", "local_started", "checked_local"},
                    "BOOTSTRAP_NO_LOADER_PARENT_LEAF_FIELDS")
            require(type(value.raw) is bytes and 0 < len(value.raw) <= LIMIT,
                    "BOOTSTRAP_NO_LOADER_PARENT_LEAF_BYTES")
            staging._local(value.local_started)
            staging._local(value.checked_local)
            return dictionary, value.raw, value.local_started, value.checked_local

        def leaf_unchanged():
            current, original = leaf_pin(), state["leaf_pin"]
            require(current[0] is original[0] and all(type(a) is type(b) and a == b
                    for a, b in zip(current[1:], original[1:])), "BOOTSTRAP_NO_LOADER_PARENT_LEAF_CHANGED")

        try:
            state["binding"] = begin(transition)  # No lock across the original operation.
            bound = state["bound"] = checked(state["binding"])
            check()
            saved = bound.pin.frame.predecessor.frame.originals
            local_last = staging._local(time.monotonic())
            first = origin.clocks.validate_reading(origin.clocks.observe())
            last = first.nanoseconds
            require(staging._clock(first.clock) == staging._clock(saved.clock) and
                    last >= bound.returned.checked_ns and local_last >= bound.returned.checked_local,
                    "BOOTSTRAP_NO_LOADER_PARENT_PREDECESSOR_CLOCK")
            proposal = allocation.validate_proposal(saved.proposal_raw, saved.admitted, saved.responses,
                                                    saved.invocation, saved.clock, saved.runner_name)
            names = ("custody-uninstall", "custody-uninstall-final", "custody-uninstall-read")
            spans = (90, 135, 165)
            ends = tuple(min(origin.integer(last + seconds * origin.NS), proposal["phaseFencesNs"][name],
                             proposal["proposedJobEndNs"]) for name, seconds in zip(names, spans))
            require(last < ends[0] <= ends[1] <= ends[2], "BOOTSTRAP_NO_LOADER_PARENT_NO_INTERVAL")
            local_ends = tuple(origin.wire._directed_deadline(local_last, seconds, end, last)
                               for seconds, end in zip(spans, ends))
            phase, issued_end = 0, local_ends[0]
            state["phases"].append((last, local_last, ends[0], local_ends[0]))
            original_producer = bound.pin.frame.bound.returned
            originals = input_kind(original_producer.request_raw, saved.admitted.record, saved.canonical_raw,
                                   tuple(saved.directories["gradle-home"]))
            inputs = inputs_kind(originals)
            owner = state["owner"] = DirectoryOwner()
            owner.end()
            for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
                handler = signal.getsignal(number)
                state["handlers"].append((number, handler))  # Duty precedes a possibly partial install.
                signal.signal(number, lambda signum, _frame: state["cancelled"].append(signum))
                owner.end()
            began = local_last
            state["leaf"] = operation(owner, originals)  # Actual return BEFORE fallible validation.
            state["leaf_pin"] = leaf_pin()
            owner.end()
            raw = origin.parse(state["leaf"].raw)
            expected = {"schema": 1, "scope": module.SCOPE, "binding": inputs.binding(), "completed": True,
                "observationState": "EXACT_TARGET_ABSENT_AT_LISTINGS", "inputProvenance": "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL",
                "leafHandleClose": "KNOWN", "enclosingOwnerRetirement": "NOT_OBSERVED_HERE",
                "producerAndCollectionReturn": "NOT_OBSERVED_HERE", "historicalLoaderExecution": "NOT_OBSERVED",
                "otherInitializerContents": "NOT_INSPECTED", "deletionPerformed": False, "fileContentsRead": False,
                "observationBoundary": "PINNED_LISTINGS_AND_SAME_HANDLE_VERIFY_NOT_ATOMIC_OR_HISTORICAL_ABSENCE",
                "dependencyPopulation": "NOT_ATTESTED", "budgetAcceptance": "NOT_ADMITTED",
                "testAcceptance": "NOT_PERFORMED", "nextPhaseAuthority": False, "exportSaveAuthority": False}
            require(type(raw) is dict and len(raw) == len(expected) + 3 and
                    raw.get("initDirectory") in ("OBSERVED_DIRECTORY", "ABSENT_IN_HOME_LISTINGS") and
                    len(pins) == (2 if raw["initDirectory"] == "OBSERVED_DIRECTORY" else 1) and
                    type(raw.get("listings")) is list and len(raw["listings"]) == 2 * len(pins) and
                    origin.encoded(raw) == origin.encoded({**expected, **{key: raw[key]
                        for key in ("initDirectory", "listings", "localWindow")}}),
                    "BOOTSTRAP_NO_LOADER_PARENT_LEAF_DISPOSITION")
            leaf = state["leaf"]
            window = raw["localWindow"]
            require(type(window) is dict and len(window) == 4 and
                    origin.encoded(window) == origin.encoded({"started": leaf.local_started,
                        "end": staging._local(leaf.local_started + 90), "observed": window.get("observed"),
                        "scope": "LOCAL90_SHORTENS_CALLER_NOT_SHARED_CLOCK_OR_JOB_ADMISSION"}) and
                    began <= leaf.local_started <= staging._local(window["observed"]) <= leaf.checked_local <= local_last and
                    leaf.checked_local < window["end"], "BOOTSTRAP_NO_LOADER_PARENT_LEAF_CHRONOLOGY")
            leaf_unchanged()
            owner.end()
        except BaseException as failure:
            error("body", failure)
        finally:
            if owner is not None:
                try:
                    advance()
                except BaseException as failure:
                    error("final-start", failure)
                state["closed"] = True
                for pin in reversed(pins):
                    if state["unknown"]:
                        break
                    owner.close_one(pin[2])
            for number, handler in state["handlers"]:
                close_clock()
                try:
                    signal.signal(number, handler)
                    require(signal.getsignal(number) is handler, "BOOTSTRAP_NO_LOADER_PARENT_HANDLER_NOT_RESTORED")
                    state["restored"].append((number, handler))
                except BaseException as failure:
                    error("handler-restore", failure)
                close_clock()
        try:
            raise_first()
            check()
            require(state["closed"] and not state["unknown"] and state["handlers"] == state["restored"] and
                    all(pin[4] and pin[5] for pin in pins), "BOOTSTRAP_NO_LOADER_PARENT_CLOSE_INCOMPLETE")
            leaf_unchanged()
            advance()  # READ is post-close accounting only; never reopens a handle.
            cancel()
            sample()
            raw = origin.encoded({"schema": 1, "scope": "BOOTSTRAP_NO_LOADER_PARENT_CLOSED_OBSERVATIONS_V1",
                "collectionSha256": origin.digest(bound.returned.raw), "leafSha256": origin.digest(state["leaf"].raw),
                "clock": origin.clock_value(first.clock), "firstNs": first.nanoseconds,
                "globalEndsNs": dict(zip(names, ends)), "phases": state["phases"], "closedNs": last,
                "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "resourceCount": len(pins),
                "operation": "OBSERVE_EXACT_LOADER_NOT_UNINSTALL", "nextPhaseAuthority": False,
                "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
            cancel()
            sample()
            check()
            leaf_unchanged()
            cancellation(state["cancelled"])  # Final flag check adds no callback or renewed clock.
            result = prefix_kind(raw, state["leaf"], last, local_last)
            state["closed_check"] = (check, leaf_unchanged)
            state["result"], state["complete"] = result, True
            state["result_pin"] = (object.__getattribute__(result, "__dict__"), raw, result.leaf, last, local_last)
            return result
        except BaseException as failure:
            error("return", failure)
            if state["unknown"] and not any(value is state for value in QUARANTINE):
                QUARANTINE.append(state)
            try:
                state["original"].bootstrap_no_loader_parent = owner
                state["original"].bootstrap_no_loader_resources = tuple(pins)
            except BaseException:
                pass
            raise state["original"]

    def closed_return(transition, returned):
        """Read original private publication pins; never capture a replacement baseline."""
        roots()
        state = calls.get(id(transition))
        require(state is not None and state["transition"] is transition and state["complete"] is True and
                state["original"] is None and state["unknown"] is False and state["closed"] is True and
                state["result"] is returned and type(returned) is prefix_kind and
                state["handlers"] == state["restored"] and state["errors"] == [],
                "BOOTSTRAP_NO_LOADER_RETURN_NOT_ORIGINAL")
        for check in state["closed_check"]:
            check()  # Closed data only: no predecessor owner/clock operation.
        cancellation(state["cancelled"])
        pin = state["result_pin"]
        require(object.__getattribute__(returned, "__dict__") is pin[0] and len(pin[0]) == 4 and
                set(pin[0]) == {"raw", "leaf", "checked_ns", "checked_local"} and returned.leaf is pin[2] and
                all(type(value) is type(old) and value == old for value, old in zip(
                    (returned.raw, returned.checked_ns, returned.checked_local), (pin[1], pin[3], pin[4]))) and
                all(row[4] is row[5] is True for row in state["pins"]),
                "BOOTSTRAP_NO_LOADER_RETURN_CHANGED")
        return state["bound"]

    return execute, closed_return


observe_no_loader_after_entry, _checked_no_loader_parent_return = _no_loader_parent_controls()
del _no_loader_parent_controls


@dataclass(frozen=True)
class BootstrapExportPrefix:
    """Original bounded copy return; no frozen set or provider/save authority."""
    raw: bytes = field(repr=False)
    leaf: object = field(repr=False)
    checked_ns: int
    checked_local: float


@dataclass(frozen=True)
class BootstrapSaveSetPrefix:
    """Original before-save return; no provider or archived-byte authority."""
    raw: bytes = field(repr=False)
    leaf: object = field(repr=False)
    checked_ns: int
    checked_local: float


@dataclass(frozen=True)
class BootstrapSaveHandoffPrefix:
    """Private pending handoff, NOT an original workflow outcome or save permit."""
    raw: bytes = field(repr=False)
    checked_ns: int
    checked_local: float
    _complete: object = field(repr=False, compare=False)


def _bootstrap_export_controls():
    """Two fixed siblings share owner code, never an already-closed owner."""
    operation, predecessor = observe_no_loader_after_entry, _checked_no_loader_parent_return
    module, copy = dependency_export, dependency_export.export_snapshot
    input_kind, window_kind = custody._Inputs, dependency_export._Window
    result_kind, prefix_kind = dependency_export.ExportEvidence, BootstrapExportPrefix
    scope, statuses = dependency_export.SCOPE, dependency_export.STATUSES
    save_module, save_copy = dependency_save_set, dependency_save_set.before_save
    save_window, save_result, save_prefix = dependency_save_set._Window, dependency_save_set.SaveSetEvidence, BootstrapSaveSetPrefix
    save_scope, save_statuses = dependency_save_set.SCOPE, dependency_save_set.STATUSES
    handoff_owner, handoff_names, handoff_prefix = Owner, _initializer_names, BootstrapSaveHandoffPrefix
    calls, before_calls, lock = {}, {}, threading.Lock()

    def roots():
        require(observe_no_loader_after_entry is operation and _checked_no_loader_parent_return is predecessor and
                dependency_export is module and module.export_snapshot is copy and module._Window is window_kind and
                module.ExportEvidence is result_kind and module.SCOPE is scope and module.STATUSES is statuses and
                custody._Inputs is input_kind and BootstrapExportPrefix is prefix_kind,
                "BOOTSTRAP_EXPORT_OPERATION_CHANGED")

    def closed_return(transition, returned, before_save):
        roots()
        claims, kind = (before_calls, save_prefix) if before_save else (calls, prefix_kind)
        state = claims.get(id(transition))
        require(state is not None and state["transition"] is transition and state["result"] is returned and
                type(returned) is kind and state["original"] is None and state["unknown"] is False and
                state["closed"] is True and state["errors"] == [] and state["handlers"] == state["restored"],
                "BOOTSTRAP_EXPORT_RETURN_NOT_ORIGINAL")
        for check in state["closed_check"]:
            check()  # No old-owner operation, new baseline or clock sample.
        cancellation(state["cancelled"])
        pin = state["result_pin"]
        require(object.__getattribute__(returned, "__dict__") is pin[0] and len(pin[0]) == 4 and
                set(pin[0]) == {"raw", "leaf", "checked_ns", "checked_local"} and returned.leaf is pin[2] and
                all(type(a) is type(b) and a == b for a, b in zip(
                    (returned.raw, returned.checked_ns, returned.checked_local), (pin[1], pin[3], pin[4]))) and
                all(row[4] is row[5] is True for row in state["pins"]), "BOOTSTRAP_EXPORT_RETURN_CHANGED")
        return state["bound"]

    def closed_export_return(transition, returned):
        return closed_return(transition, returned, False)

    def closed_before_return(transition, returned):
        """Read original same-process pins, not a persisted handoff or save permit."""
        return closed_return(transition, returned, True)

    def drive(transition, before_save):
        # Only the two lexical wrappers below select a phase. No public mode,
        # supplied predecessor, owner factory or caller-selected operation.
        def phase_roots():
            roots()
            if before_save:
                require(dependency_save_set is save_module and save_module.before_save is save_copy and
                        save_module._Window is save_window and save_module.SaveSetEvidence is save_result and
                        save_module.SCOPE is save_scope and save_module.STATUSES is save_statuses and
                        BootstrapSaveSetPrefix is save_prefix and export_after_entry is execute and
                        before_save_after_entry is before and _checked_before_save_parent_return is closed_before_return,
                        "BOOTSTRAP_SAVE_OPERATION_CHANGED")

        phase_roots()
        run_previous, check_previous = (execute, closed_export_return) if before_save else (operation, predecessor)
        phase_window, phase_result, phase_prefix = ((save_window, save_result, save_prefix) if before_save else
                                                   (window_kind, result_kind, prefix_kind))
        phase_module, phase_copy = (save_module, save_copy) if before_save else (module, copy)
        claims = before_calls if before_save else calls
        require(type(transition) is NewEntryTransition, "BOOTSTRAP_EXPORT_TRANSITION")
        with lock:
            require(id(transition) not in claims, "BOOTSTRAP_EXPORT_ALREADY_CLAIMED")
            state = {"transition": transition, "previous": None, "bound": None, "inputs": None, "window": None,
                "leaf": None, "result": None, "original": None, "errors": [], "error_refs": [], "unknown": False,
                "closed": False, "resources": [], "pins": [], "returns": [], "cancelled": [],
                "handlers": [], "restored": [], "expired": False}
            claims[id(transition)] = state  # Includes failed/reentrant original calls.
        ledger, pins, owned = state["resources"], state["pins"], set()
        bound = inputs = window = owner = None
        fixed, issued_end, borrowed, kinds = (), None, frozenset(), ()

        def error(stage, failure, *, unknown=False):
            if state["original"] is None:
                state["original"] = failure
            state["unknown"] |= unknown
            try:
                detail = diagnostics._exception_detail(failure)
                state["unknown"] |= detail["retirementUnknown"]
                if any(stage == old_stage and failure is old for old_stage, old in state["error_refs"]):
                    return  # Repeated propagation is not another distinct failure.
                require(len(state["errors"]) < 64, "BOOTSTRAP_EXPORT_ERROR_LIMIT")
                state["error_refs"].append((stage, failure))
                state["errors"].append(origin.encoded({"stage": stage, "detail": detail}))
            except BaseException:
                state["unknown"] = True

        def raise_first():
            if state["original"] is not None:
                raise state["original"]

        def roster():
            try:
                require(len(ledger) == len(pins) == len(owned) <= 65536, "BOOTSTRAP_EXPORT_RESOURCE_LIMIT")
                for row, pin in zip(ledger, pins):
                    saved, label, value, kind, attempted, closed = pin
                    require(row is saved and type(row) is dict and len(row) == 4 and
                            set(row) == {"label", "owner", "attempted", "closed"} and row["label"] == label and
                            type(row["label"]) is str and row["owner"] is value and type(value) is kind and
                            row["attempted"] is attempted and row["closed"] is closed,
                            "BOOTSTRAP_EXPORT_ROSTER_CHANGED")
            except BaseException as failure:
                error("roster", failure, unknown=True)
                raise

        def fences():
            actual = (window.first, window.soft, window.hard, window.local_start, window.local_soft, window.local_hard)
            require(window.inputs is inputs and all(type(a) is type(b) and a == b for a, b in zip(actual, fixed)),
                    "BOOTSTRAP_EXPORT_FENCE_CHANGED")

        def leaf_unchanged():
            leaf, pin = state["leaf"], state["leaf_pin"]
            require(type(leaf) is phase_result and object.__getattribute__(leaf, "__dict__") is pin[0] and
                    len(pin[0]) == 4 and set(pin[0]) == {"raw", "checked_ns", "local_started", "checked_local"} and
                    all(type(a) is type(b) and a == b for a, b in zip(
                        (leaf.raw, leaf.checked_ns, leaf.local_started, leaf.checked_local), pin[1:])),
                    "BOOTSTRAP_EXPORT_LEAF_CHANGED")

        def check():
            phase_roots()
            require(bound is not None and check_previous(transition, state["previous"]) is bound,
                    "BOOTSTRAP_EXPORT_PREDECESSOR_CHANGED")
            inputs.unchanged()
            roster()
            fences()
            if "leaf_pin" in state:
                leaf_unchanged()
            require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                    "BOOTSTRAP_EXPORT_PRIOR_UNKNOWN")

        def cancel():
            check()
            cancellation(state["cancelled"])
            for callback in bound.pin.frame.predecessor.frame.callbacks:
                callback()
                check()
            cancellation(state["cancelled"])

        def sample(*, cleanup=False):
            if not cleanup:
                check()
            fences()
            before = staging._local(time.monotonic())
            require(before >= window.local_last, "BOOTSTRAP_EXPORT_LOCAL_BACKWARDS")
            window.local_last = before
            window.sample()
            fences()
            if not cleanup:
                check()
            return before

        def close_clock():
            try:
                sample(cleanup=True)
            except BaseException as failure:
                expired = (type(failure) is staging.files.SeedError and
                           failure.args == ("BOOTSTRAP_SEED_ORIGINAL_PHASE_EXPIRED",))
                if not expired or not state["expired"]:
                    state["expired"] |= expired
                    error("close-clock", failure)

        class FileOwner:
            __slots__ = ()
            resources = property(lambda self: ledger)
            original = property(lambda self: state["original"])
            unknown = property(lambda self: state["unknown"])
            closed = property(lambda self: state["closed"])
            cancelled = property(lambda self: cancel)

            def error(self, stage, failure, *, unknown=False):
                error(stage, failure, unknown=unknown)

            def end(self):
                nonlocal issued_end
                raise_first()
                require(not self.closed and not self.unknown, "BOOTSTRAP_EXPORT_NOT_LIVE")
                cancel()
                local = sample()
                issued_end = min(issued_end, origin.wire._directed_deadline(local, 120, fixed[2], window.last))
                require(window.local_last < issued_end, "BOOTSTRAP_EXPORT_EXPIRED")
                return issued_end

            def acquire(self, label, factory):
                self.end()
                require(type(label) is str and 0 < len(label) <= 256 and len(pins) < 65536,
                        "BOOTSTRAP_EXPORT_RESOURCE_LIMIT")
                try:
                    value = factory()
                except BaseException as failure:
                    error("allocation", failure, unknown=True)
                    raise
                state["returns"].append(value)  # Before kind/borrow/registration checks.
                if type(value) not in kinds or id(value) in owned or id(value) in borrowed:
                    failure = origin.OriginError("BOOTSTRAP_EXPORT_BORROWED_RESOURCE")
                    error("allocation-return", failure, unknown=True)
                    raise failure
                row = {"label": label, "owner": value, "attempted": False, "closed": False}
                pins.append((row, label, value, type(value), False, False))
                owned.add(id(value))
                ledger.append(row)
                self.end()
                return value

            def close_one(self, value):
                index = next((i for i, pin in enumerate(pins) if pin[2] is value), None)
                if index is None:
                    error("foreign-close", origin.OriginError("BOOTSTRAP_EXPORT_FOREIGN_RESOURCE"), unknown=True)
                    return
                pin = pins[index]
                if pin[4]:
                    return
                try:
                    roster()
                    require(not self.unknown, "BOOTSTRAP_EXPORT_UNKNOWN")
                    close_clock()
                    roster()
                    require(not self.unknown and not QUARANTINE and not query.QUARANTINE and
                            not diagnostics._QUARANTINE, "BOOTSTRAP_EXPORT_UNKNOWN")
                    if pins[index][4]:
                        return
                    require(pins[index] is pin, "BOOTSTRAP_EXPORT_CLOSE_CHANGED")
                except BaseException as failure:
                    error("close-binding", failure, unknown=True)
                    return
                pins[index] = (*pin[:4], True, False)
                pin[0]["attempted"] = True
                try:
                    value.close()
                    pins[index] = (*pin[:4], True, True)
                    pin[0]["closed"] = True
                    roster()
                except BaseException as failure:
                    error("close", failure, unknown=True)
                close_clock()

        try:
            state["previous"] = run_previous(transition)
            bound = state["bound"] = check_previous(transition, state["previous"])
            previous = state["previous"]
            saved, last = bound.pin.frame.predecessor.frame, bound.pin.frame.predecessor.phases[-1][1]
            inputs = state["inputs"] = input_kind(saved.originals, saved.original_pin, last.staged, last.staged_pin)
            local = staging._local(time.monotonic())
            first = origin.clocks.validate_reading(origin.clocks.observe())
            phase = staging.PhaseStart(first, local)
            window = state["window"] = phase_window(inputs, phase, (previous.raw, previous.checked_ns, previous.checked_local))
            fixed = (window.first, window.soft, window.hard, window.local_start, window.local_soft, window.local_hard)
            issued_end = window.local_hard
            borrowed = frozenset(id(row[0]) for row in bound.pin.graph.nodes)
            if before_save:
                prior = calls[id(transition)]
                borrowed |= frozenset(id(value) for value in prior["returns"])
                borrowed |= frozenset(id(pin[2]) for pin in prior["pins"])
            kinds = ((windows.PrivateDirectory, windows.DependencySourceDirectory, windows.NativeFile)
                     if inputs.role == "windows-x64" else
                     (staging.files.PosixPrivateDirectory, staging.files.PosixSourceDirectory, staging.files.PosixFile))
            owner = FileOwner()
            owner.end()
            for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
                handler = signal.getsignal(number)
                state["handlers"].append((number, handler))
                signal.signal(number, lambda signum, _frame: state["cancelled"].append(signum))
                owner.end()
            state["leaf"] = (phase_copy(owner, inputs, window, previous.leaf.raw) if before_save else
                             phase_copy(owner, inputs, window))
            leaf = state["leaf"]
            require(type(leaf) is phase_result and type(leaf.raw) is bytes and 0 < len(leaf.raw) <= staging.files.RECEIPT_LIMIT and
                    window.first <= origin.integer(leaf.checked_ns) <= window.last and
                    type(leaf.local_started) is type(leaf.checked_local) is float and
                    leaf.local_started == window.local_start and
                    leaf.local_started <= staging._local(leaf.checked_local) <= window.local_last,
                    "BOOTSTRAP_EXPORT_LEAF_RETURN")
            state["leaf_pin"] = (object.__getattribute__(leaf, "__dict__"), leaf.raw, leaf.checked_ns,
                                 leaf.local_started, leaf.checked_local)
            leaf_unchanged()
            owner.end()
            value = origin.parse(leaf.raw)
            require(value.get("scope") == phase_module.SCOPE and value.get("completed") is True and
                    value.get("retirement") == "KNOWN" and value.get("status") in phase_module.STATUSES and
                    value.get("nextPhaseAuthority") is value.get("exportSaveAuthority") is False and
                    value.get("budgetAcceptance") == "NOT_ADMITTED" and value.get("testAcceptance") == "NOT_PERFORMED",
                    "BOOTSTRAP_EXPORT_LEAF_DISPOSITION")
            require(all(pin[4] and pin[5] for pin in pins), "BOOTSTRAP_EXPORT_LEAF_NOT_CLOSED")
        except BaseException as failure:
            error("body", failure)
        finally:
            if owner is not None:
                state["closed"] = True
                for pin in reversed(pins):
                    if state["unknown"]:
                        break
                    owner.close_one(pin[2])
            for number, handler in state["handlers"]:
                close_clock()
                try:
                    signal.signal(number, handler)
                    require(signal.getsignal(number) is handler, "BOOTSTRAP_EXPORT_HANDLER_NOT_RESTORED")
                    state["restored"].append((number, handler))
                except BaseException as failure:
                    error("handler-restore", failure)
                close_clock()
        try:
            raise_first()
            check()
            require(state["closed"] and not state["unknown"] and state["handlers"] == state["restored"] and
                    all(pin[4] and pin[5] for pin in pins), "BOOTSTRAP_EXPORT_CLOSE_INCOMPLETE")
            leaf_unchanged()
            cancel()
            sample()
            raw = origin.encoded({"schema": 1, "scope": ("BOOTSTRAP_SAVE_SET_PARENT_CLOSED_OBSERVATIONS_V1" if before_save
                                                       else "BOOTSTRAP_EXPORT_PARENT_CLOSED_OBSERVATIONS_V1"),
                ("exportParentSha256" if before_save else "noLoaderSha256"): origin.digest(previous.raw),
                "leafSha256": origin.digest(leaf.raw),
                "clock": origin.clock_value(first.clock), "firstNs": fixed[0], "softEndNs": fixed[1],
                "hardEndNs": fixed[2], "closedNs": window.last, "resourceCount": len(pins),
                "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "nextPhaseAuthority": False,
                "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
            cancel()
            sample()
            cancellation(state["cancelled"])
            result = phase_prefix(raw, leaf, window.last, window.local_last)
            state["closed_check"] = (check, leaf_unchanged)
            state["result"] = result
            state["result_pin"] = (object.__getattribute__(result, "__dict__"), raw, leaf, window.last, window.local_last)
            return result
        except BaseException as failure:
            error("return", failure)
            if state["unknown"] and not any(value is state for value in QUARANTINE):
                QUARANTINE.append(state)
            raise state["original"]

    def execute(transition):
        return drive(transition, False)

    def before(transition):
        return drive(transition, True)

    def handoff_records(transition, returned, bound, inputs):
        """Fixed original-byte inventory, not serialization of an owner graph.

        Older file rows did not retain file stamps. Their references explicitly
        keep that absence; a new observation cannot invent an original binding.
        Large existing logs/reports are linked, never copied into this metadata.
        """
        exported = before_calls[id(transition)]["previous"]
        absence = calls[id(transition)]["previous"]
        collection_frame, collected = bound.pin.frame, bound.returned
        producer_frame, produced = collection_frame.bound.producer_frame, collection_frame.bound.returned
        predecessor = producer_frame.predecessor
        saved, reserved, native = predecessor.frame, producer_frame.reservation, producer_frame.native
        recipient = saved.registries[6][4][4]
        previous, old = transition._attempt, transition._attempt.transition
        entry = old._entry
        stage = inputs.staged_capture
        blobs = (
            ("before-parent.json", returned.raw), ("before-leaf.json", returned.leaf.raw),
            ("export-parent.json", exported.raw), ("export-leaf.json", exported.leaf.raw),
            ("no-loader-parent.json", absence.raw), ("no-loader-leaf.json", absence.leaf.raw),
            ("collection-parent.json", collected.raw), ("collection-leaf.json", collected.leaf.raw),
            ("collection-inventory.json", collected.leaf.inventory_raw),
            ("producer-parent.json", produced.raw), ("producer-request.json", produced.request_raw),
            ("producer-observation.json", produced.observation_raw), ("producer-command.json", producer_frame.descriptor),
            ("producer-birth.json", native.birth_raw), ("producer-leader.json", native.leader_raw),
            ("producer-preparer.json", native.preparer_raw), ("producer-terminal.json", native.terminal_raw),
            ("producer-survivors.json", native.survivors_raw),
            ("custody-parent.json", reserved.raw), ("custody-leaf.json", reserved.custody_leaf.raw),
            ("seed-parent.json", stage[0]), ("stage-parent.json", stage[1]),
            ("stage-leaf.json", stage[2][0]), ("seed-leaf.json", stage[3][0]),
            ("initializer-parent.json", inputs.closed_raw), ("recipient-parent.json", recipient.raw),
            ("allocation-proposal.json", inputs.proposal_raw), ("entry-parent.json", transition.raw),
            ("adoption-parent.json", old.raw), ("adoption-preparation.json", entry.preparation_original),
            ("entry-preparation.json", previous.preparation),
        )
        references = {}

        def reference(group, key, path, identity, name, maximum, blob=None, *, sha256=None, binding=None):
            label = group + "/" + key
            require(label not in references and (blob is None or type(blob) is bytes and len(blob) <= maximum),
                    "BOOTSTRAP_SAVE_HANDOFF_REFERENCE_CHANGED")
            require(blob is not None or type(sha256) is str and re.fullmatch(r"[0-9a-f]{64}", sha256),
                    "BOOTSTRAP_SAVE_HANDOFF_REFERENCE_HASH")
            references[label] = {"directory": str(path), "directoryIdentity": list(identity), "name": name,
                "maximumBytes": maximum, "bytes": None if blob is None else len(blob),
                "sha256": sha256 if blob is None else origin.digest(blob), "fileBinding": binding,
                "bindingScope": "ORIGINAL_FILE_BINDING" if binding is not None else
                                "ORIGINAL_DIRECTORY_AND_BYTES_OR_HASH_ONLY_NOT_FILE_IDENTITY"}

        for group, frame in (("producer", producer_frame), ("collector", collection_frame)):
            for row in frame.files:
                reference(group, row.key, row.path, row.identity, row.name, row.maximum, row.raw,
                          binding=origin.parse(row.binding_raw))
        # Staging retains the recipient roster followed by the initializer's.
        # They legitimately share keys; preserve their original group boundary.
        require(saved.files[:len(recipient.files)] == recipient.files,
                "BOOTSTRAP_SAVE_HANDOFF_RECIPIENT_ROSTER_CHANGED")
        for group, rows in (("recipient", recipient.files), ("initializer", saved.files[len(recipient.files):])):
            for key, path, identity, name, maximum, blob in rows:
                reference(group, key, path, identity, name, maximum, blob)
        for _parent, frame in predecessor.phases:
            for key, _directory, path, identity, name, maximum, blob in frame.files:
                reference(frame.name, key, path, identity, name, maximum, blob)

        prepared, original, adopted, current = origin.parse(entry.preparation_original), *saved.paths[:3]
        original_id = prepared["sessionIdentity"]
        adopted_id = origin.parse(entry.raw)["sessionIdentity"]
        current_id = previous.target_identity
        for key, blob in (("prepare-handoff.json", entry.handoff_original), ("context.json", entry.context_original),
                          ("prelude.json", old._fence.raw)):
            reference("preparation", key, original, original_id, key, LIMIT, blob)
        reference("preparation", "origin-result.json", original, original_id, "origin-result.json", LIMIT,
                  sha256=prepared["originSha256"])
        service = original / "service"
        service_id, original_chain = prepared["directories"]["service"], prepared["originalChain"]
        for name, digest in original_chain["phaseSha256"].items():
            maximum = ACK_LIMIT if name == "stdout.log" else STDERR_LIMIT if name == "stderr.log" else LIMIT
            reference("service", name, service, service_id, name, maximum, sha256=digest)
        reference("service", "child-result.json", service, service_id, "child-result.json", LIMIT,
                  sha256=original_chain["childTerminalSha256"])
        for name, blob in inputs.responses.items():
            reference("service", name, service, service_id, name + ".json", LIMIT, blob)
        for name, hashes in (("admission", original_chain["admissionOriginals"]),
                             ("final-admission", prepared["finalAdmissionOriginals"])):
            path, identity = original / name, prepared["directories"][name]
            reference("preparation", name + "-return", original, original_id, name + "-return.json", LIMIT,
                      sha256=hashes["returnSha256"])
            reference("preparation/" + name, "session-result", path, identity, "session-result.json", LIMIT,
                      sha256=hashes["sessionSha256"])
            for filename, blob in (("admission.json", entry.admitted.record), ("original-event.json", entry.admitted.original_event),
                    ("original-policy.json", entry.admitted.original_policy), ("recipient-public.asc", entry.admitted.public_key)):
                reference("preparation/" + name, filename, path, identity, filename, LIMIT, blob)
        for group, path, identity, records in (
                ("adoption", adopted, adopted_id, (("entry-context.json", entry.raw),
                    ("entry-close-pending.json", old.pending_raw), ("admission-return.json", entry.return_original))),
                ("entry", current, current_id, (("new-entry-pending.json", previous.pending_raw),
                    ("admission-return.json", previous.admission_originals[2])))):
            for name, blob in records:
                reference(group, name, path, identity, name, LIMIT, blob)
        # These admission-directory identities were captured by the original
        # producer's readback, not looked up through closed directory methods.
        for group, path, admitted, session in (("adoption", adopted, entry.admitted, entry.session_original),
                ("entry", current, previous.admitted, previous.admission_originals[1])):
            path = path / "admission"
            matches = [identity for _key, _directory, spelling, identity in producer_frame.handles if spelling == path]
            require(len(matches) == 1, "BOOTSTRAP_SAVE_HANDOFF_ADMISSION_DIRECTORY")
            for name, blob in (("admission.json", admitted.record), ("original-event.json", admitted.original_event),
                    ("original-policy.json", admitted.original_policy), ("recipient-public.asc", admitted.public_key),
                    ("session-result.json", session)):
                reference(group + "/admission", name, path, matches[0], name, LIMIT, blob)
        last = predecessor.phases[-1][1]
        reference("reservation", "request", last.request_pin.path, last.request_pin.directory, "request.json", LIMIT,
                  reserved.custody_leaf.request_raw, binding=origin.parse(last.request_pin.binding_raw))
        reference("staging", "staging", inputs.container, inputs.stage["containerIdentity"], "staging.json", LIMIT,
                  inputs.staging_raw, binding=inputs.stage_value["fileBindings"]["staging"])
        original_request = origin.parse(reserved.custody_leaf.request_raw)
        for key, path, identity, name, blob in (
                ("initializer-context", inputs.session, inputs.directories["session"], "initializer-context.json", inputs.context_raw),
                ("canonical-context", inputs.state, inputs.directories["state"], "context.json", inputs.canonical_raw),
                ("properties", inputs.home, inputs.directories["gradle-home"], "gradle.properties", inputs.properties_raw)):
            reference("initializer-actual", key, path, identity, name, LIMIT, blob,
                      binding=original_request["fileBindings"][key])
        phase = next(row for row in producer_frame.handles if row[0] == "phase")
        captures = {}
        for capture in producer_frame.captures:
            reference("producer-capture", capture.name, phase[2], phase[3], capture.name + ".log",
                      PRODUCER_STREAM_BYTES, sha256=capture.readback[1])
            stamp = capture.final_stamp
            captures[capture.name] = {"identity": list(capture.identity), "bytes": capture.readback[0],
                "sha256": capture.readback[1], "readNs": capture.readback[2],
                "nativeStamp": {"identity": list(stamp[0]), "size": stamp[1],
                    **({"nativeInfoBytes": stamp[2].decode("utf-8")} if inputs.role == "windows-x64" else
                       {"mtimeNs": stamp[2], "ctimeNs": stamp[3]})}}
        request = origin.parse(produced.request_raw)
        def returned_fields(value):
            return {"checkedNs": value.checked_ns, "checkedLocal": value.checked_local}
        def leaf_fields(value):
            return {**returned_fields(value), "localStarted": value.local_started}
        chain = {"producerJob": request["jobId"], "producerInvocation": request["id"],
            "producerOuterInvocation": producer_frame.outer_invocation, "producerCaptures": captures,
            "producerNative": {"launchMinimumNs": native.launch_minimum, "completedNs": native.completed_ns,
                "finalizedNs": native.finalized_ns, "executedArgv": list(native.argv), "originalExitCode": native.exit_code,
                "originalRetired": native.retired},
            "collectionManifestSha256": origin.digest(collected.manifest_raw),
            "returns": {"adoption": {"checkedNs": old._checked_ns}, "entry": {"checkedNs": transition._checked_ns},
                "recipient": {"checkedNs": recipient.checked_ns, "checkedLocal": recipient.local_last},
                "initializer": {"checkedNs": inputs.previous_ns, "checkedLocal": inputs.previous_local},
                **{frame.name: {"parent": returned_fields(frame.result), "leaf": leaf_fields(frame.leaf)}
                   for _parent, frame in predecessor.phases},
                "producer": returned_fields(produced), "collection": returned_fields(collected),
                "collectionLeaf": {"localStarted": collected.leaf.local_started, "checkedLocal": collected.leaf.checked_local},
                "noLoader": returned_fields(absence),
                "noLoaderLeaf": {"localStarted": absence.leaf.local_started, "checkedLocal": absence.leaf.checked_local},
                "export": returned_fields(exported), "exportLeaf": leaf_fields(exported.leaf),
                "before": returned_fields(returned), "beforeLeaf": leaf_fields(returned.leaf)},
            "referenceScope": "RETAINED_ORIGINAL_BINDINGS_NOT_A_FRESH_FILE_OBSERVATION_OR_PROVIDER_RESULT"}
        return blobs, references, chain

    def handoff(transition):
        """Retain the original same-call chain under one NEW return45 owner.

        Nothing supplied by a caller becomes an export, plan or return. The
        original before() claim also refuses a prior separately-run producer.
        Files remain provisional through close, handler restoration and return;
        no file can attest its own later successful workflow step.
        """
        owner = fence = returned = bound = inputs = None
        handlers, restored, cancelled = [], [], []
        failure = raw = None
        last = local_last = issued_end = None

        def roots_and_originals():
            roots()
            require(save_handoff_after_entry is handoff and before_save_after_entry is before and
                    _checked_before_save_parent_return is closed_before_return and Owner is handoff_owner and
                    _initializer_names is handoff_names and BootstrapSaveHandoffPrefix is handoff_prefix and
                    LIMIT == 2 * 1024 * 1024, "BOOTSTRAP_SAVE_HANDOFF_OPERATION_CHANGED")
            if returned is not None:
                require(closed_before_return(transition, returned) is bound,
                        "BOOTSTRAP_SAVE_HANDOFF_PREDECESSOR_CHANGED")
            if inputs is not None:
                inputs.unchanged()
            require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                    "BOOTSTRAP_SAVE_HANDOFF_PRIOR_UNKNOWN")

        def cancel():
            roots_and_originals()
            cancellation(cancelled)
            if bound is not None:
                for callback in bound.pin.frame.predecessor.frame.callbacks:
                    callback()
                    roots_and_originals()
                    cancellation(cancelled)

        def remember_failure(error):
            nonlocal failure
            if failure is None:
                failure = owner.original if owner is not None and owner.original is not None else error
            if owner is not None:
                try:
                    owner.error("save-handoff", error)
                except BaseException:
                    # Failure to describe an error cannot replace its cause or
                    # grant further ownership operations.
                    owner.unknown = True

        try:
            roots_and_originals()
            for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
                handler = signal.getsignal(number)
                handlers.append((number, handler))  # Duty precedes fallible installation.
                signal.signal(number, lambda signum, _frame: cancelled.append(signum))
            returned = before(transition)
            bound = closed_before_return(transition, returned)
            local_start = staging._local(time.monotonic())
            first = origin.clocks.validate_reading(origin.clocks.observe())
            saved, staged = bound.pin.frame.predecessor.frame, bound.pin.frame.predecessor.phases[-1][1]
            inputs = input_kind(saved.originals, saved.original_pin, staged.staged, staged.staged_pin)
            require(first.clock == inputs.clock and first.nanoseconds >= returned.checked_ns and
                    local_start >= returned.checked_local, "BOOTSTRAP_SAVE_HANDOFF_PREDECESSOR_CLOCK")
            hard = min(origin.integer(first.nanoseconds + 45 * staging.NS),
                       inputs.proposal["phaseFencesNs"]["producer-owner-return"], inputs.proposal["proposedJobEndNs"])
            require(first.nanoseconds < hard, "BOOTSTRAP_SAVE_HANDOFF_EXPIRED")
            local_end = origin.wire._directed_deadline(local_start, 45, hard, first.nanoseconds)
            last, local_last, issued_end = first.nanoseconds, local_start, local_end

            class ReturnFence:
                __slots__ = ()

                def now(self, *, final=False, minimum=None, limit=None):
                    nonlocal last, local_last, issued_end
                    # Cleanup samples only the original clocks: rejection of a
                    # predecessor cannot redirect or repeatedly block known closes.
                    if not final:
                        cancel()
                    before_raw = staging._local(time.monotonic())
                    require(before_raw >= local_last, "BOOTSTRAP_SAVE_HANDOFF_LOCAL_BACKWARDS")
                    local_last = before_raw  # Retain even if the RAW supplier fails.
                    observed = origin.clocks.validate_reading(origin.clocks.observe())
                    require(observed.clock == first.clock and observed.nanoseconds >= last and
                            (minimum is None or observed.nanoseconds >= minimum),
                            "BOOTSTRAP_SAVE_HANDOFF_RAW_BACKWARDS")
                    last = observed.nanoseconds
                    after_raw = staging._local(time.monotonic())
                    require(after_raw >= local_last, "BOOTSTRAP_SAVE_HANDOFF_LOCAL_BACKWARDS")
                    local_last = after_raw
                    cap = hard if limit is None else min(hard, origin.integer(limit))
                    issued_end = min(issued_end, origin.wire._directed_deadline(before_raw, 45, cap, last))
                    require(last < cap and local_last < issued_end, "BOOTSTRAP_SAVE_HANDOFF_EXPIRED")
                    if not final:
                        cancel()
                        # A callback itself may return late. Sample after it,
                        # without running another callback or granting new time.
                        return self.now(final=True, minimum=last, limit=cap)
                    return last

                def deadline(self, seconds, *, final=False, limit=None):
                    self.now(final=final, limit=limit)
                    return min(issued_end, local_last + min(45, seconds))

            fence = ReturnFence()
            fence.now()
            blobs, references, chain = handoff_records(transition, returned, bound, inputs)
            require(0 < len(blobs) < 32 and len({name.casefold() for name, _blob in blobs}) == len(blobs) and
                    all(type(blob) is bytes and 0 < len(blob) <= LIMIT for _name, blob in blobs),
                    "BOOTSTRAP_SAVE_HANDOFF_RECORD_LIMIT")
            fence.now()
            owner = handoff_owner(local_end, fence, first=first, cancelled=cancel)
            ledger, errors = owner.resources, owner.errors
            parent = owner.open(inputs.session)
            parent_identity = tuple(directory_identity(list(parent.identity), inputs.role))
            require(parent_identity == inputs.directories["session"], "BOOTSTRAP_SAVE_HANDOFF_INITIALIZER_CHANGED")
            directory = owner.child(parent, "dependency-save-handoff", create=True)
            directory_identity_ = tuple(directory_identity(list(directory.identity), inputs.role))
            require(directory_identity_ not in inputs.directories.values() and
                    directory_identity_ not in (tuple(inputs.stage["containerIdentity"]),
                                                tuple(inputs.stage["sourceIdentity"])) and
                    not handoff_names(owner, directory), "BOOTSTRAP_SAVE_HANDOFF_DIRECTORY_ALIAS_OR_NONEMPTY")
            path = inputs.session / "dependency-save-handoff"

            def pins():
                roots_and_originals()
                require(type(owner) is handoff_owner and owner.fence is fence and owner.first is first and
                        owner.cancelled is cancel and owner.resources is ledger and owner.errors is errors and
                        type(owner.local_end) is float and owner.local_end == local_end and
                        owner.work_limit is owner.final_limit is None and not owner.unknown and owner.original is None,
                        "BOOTSTRAP_SAVE_HANDOFF_OWNER_CHANGED")
                require(parent.path == inputs.session and directory.path == path and
                        tuple(parent.identity) == parent_identity and tuple(directory.identity) == directory_identity_,
                        "BOOTSTRAP_SAVE_HANDOFF_DIRECTORY_CHANGED")

            value = {"schema": 1, "scope": "BOOTSTRAP_SAVE_HANDOFF_PENDING_ORIGINAL_STEP_RETURN_V1",
                "binding": inputs.binding(), "source": inputs.admission["source"], "github": inputs.admission["github"],
                "selection": inputs.admission["selection"], "cacheCohort": {"profile": inputs.profile, "role": inputs.role},
                "plan": inputs.stage_value["plan"],
                "planSha256": origin.digest(staging.files.encoded(inputs.stage_value["plan"])),
                "directory": str(path), "directoryIdentity": list(directory_identity_),
                "blobs": {name: {"bytes": len(blob), "sha256": origin.digest(blob)} for name, blob in blobs},
                "references": references, "chain": chain,
                "window": {"phase": "producer-owner-return", "clock": origin.clock_value(first.clock),
                    "firstNs": first.nanoseconds, "hardEndNs": hard, "predecessorCheckedNs": returned.checked_ns,
                    "predecessorSha256": origin.digest(returned.raw)},
                "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "providerExecution": "NOT_PERFORMED",
                "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
                "exportSaveAuthority": False}
            raw = origin.encoded(value)
            require(type(raw) is bytes and 0 < len(raw) <= LIMIT, "BOOTSTRAP_SAVE_HANDOFF_INDEX_LIMIT")
            records = (*blobs, ("save-handoff.json", raw))
            for name, blob in records:
                pins()
                require(owner.write(directory, name, blob) == blob, "BOOTSTRAP_SAVE_HANDOFF_WRITE_RETURN")
                pins()
                fence.now()
            require(handoff_names(owner, directory) == tuple(sorted(name for name, _blob in records)),
                    "BOOTSTRAP_SAVE_HANDOFF_ROSTER_CHANGED")
            for name, blob in records:
                require(owner.read(directory, name) == blob, "BOOTSTRAP_SAVE_HANDOFF_READBACK_CHANGED")
                pins()
            require(handoff_names(owner, directory) == tuple(sorted(name for name, _blob in records)),
                    "BOOTSTRAP_SAVE_HANDOFF_ROSTER_CHANGED")
            parent.verify()
            directory.verify()
            pins()
            fence.now()
            close_roster = tuple((row, row["label"], row["owner"]) for row in ledger)
        except BaseException as error:
            remember_failure(error)
        finally:
            if owner is not None:
                try:
                    owner.close()
                    if owner.original is not None:
                        remember_failure(owner.original)
                except BaseException as error:
                    remember_failure(error)
                if owner.unknown and not any(value is owner for value in QUARANTINE):
                    QUARANTINE.append(owner)
            for number, handler in handlers:
                try:
                    signal.signal(number, handler)
                    require(signal.getsignal(number) is handler, "BOOTSTRAP_SAVE_HANDOFF_HANDLER_NOT_RESTORED")
                    restored.append((number, handler))
                except BaseException as error:
                    remember_failure(error)
        if failure is not None:
            raise failure
        def closed_pins():
            pins()
            require(owner.closed is True and owner.unknown is False and handlers == restored and
                    len(ledger) == len(close_roster) and all(row is old and row["label"] == label and
                        row["owner"] is resource and row["attempted"] is row["closed"] is True
                        for row, (old, label, resource) in zip(ledger, close_roster)),
                    "BOOTSTRAP_SAVE_HANDOFF_CLOSE_INCOMPLETE")

        closed_pins()
        cancel()
        fence.now(final=True)
        pins()
        cancellation(cancelled)
        checked_ns, checked_local = last, local_last
        completion_started, result = False, None

        def complete(original):
            """Caller-only retention after handoff return, within SAME return45.

            This closure retains the original fence/issued LOCAL end. No disk
            record, copied prefix or caller-selected path can recreate it.
            The new file cannot attest its own writer/command/step return.
            """
            nonlocal completion_started
            require(original is result, "BOOTSTRAP_PRODUCER_NOT_ORIGINAL_HANDOFF")
            with lock:
                require(not completion_started, "BOOTSTRAP_PRODUCER_COMPLETION_ALREADY_CLAIMED")
                completion_started = True

            def returned_pins():
                closed_pins()  # Passive checks only; never reopen the closed owner.
                require(type(result) is handoff_prefix and result.raw is raw and result._complete is complete and
                        type(result.checked_ns) is int and result.checked_ns == checked_ns and
                        type(result.checked_local) is float and result.checked_local == checked_local,
                        "BOOTSTRAP_PRODUCER_HANDOFF_RETURN_CHANGED")

            def boundary():
                returned_pins()
                fence.now(minimum=checked_ns, limit=hard)
                returned_pins()

            current_owner, record_raw, first_error = None, None, None

            def failed(error):
                nonlocal first_error
                if first_error is None:
                    first_error = (current_owner.original if current_owner is not None and
                                   current_owner.original is not None else error)
                if current_owner is not None:
                    try:
                        current_owner.error("producer-function-return", error)
                    except BaseException:
                        current_owner.unknown = True

            try:
                boundary()
                observed_ns, observed_local = last, local_last
                # deadline() can only shorten the handoff's original issued_end.
                end = fence.deadline(45, limit=hard)
                current_owner = handoff_owner(end, fence, first=first, cancelled=cancel)
                current_ledger, current_errors = current_owner.resources, current_owner.errors
                initializer = current_owner.open(inputs.session)
                index_directory = current_owner.child(initializer, "dependency-save-handoff")

                def current_pins():
                    returned_pins()
                    require(type(current_owner) is handoff_owner and current_owner.fence is fence and
                            current_owner.first is first and current_owner.cancelled is cancel and
                            current_owner.resources is current_ledger and current_owner.errors is current_errors and
                            type(current_owner.local_end) is float and current_owner.local_end == end and
                            current_owner.work_limit is current_owner.final_limit is None and
                            current_owner.original is None and current_owner.unknown is False,
                            "BOOTSTRAP_PRODUCER_RETURN_OWNER_CHANGED")
                    require(initializer.path == inputs.session and tuple(initializer.identity) == parent_identity and
                            index_directory.path == path and tuple(index_directory.identity) == directory_identity_,
                            "BOOTSTRAP_PRODUCER_RETURN_DIRECTORY_CHANGED")

                current_pins()
                initializer.verify()
                index_directory.verify()
                require(current_owner.read(index_directory, "save-handoff.json") == raw,
                        "BOOTSTRAP_PRODUCER_HANDOFF_INDEX_CHANGED")
                boundary()
                record_raw = current_owner.write(initializer, "producer-function-return.json", {
                    "schema": 1, "scope": "BOOTSTRAP_HANDOFF_FUNCTION_RETURN_PENDING_COMMAND_V1",
                    "handoffSha256": origin.digest(raw), "handoffDirectory": str(path),
                    "handoffDirectoryIdentity": list(directory_identity_), "initializerIdentity": list(parent_identity),
                    "clock": origin.clock_value(first.clock), "firstNs": first.nanoseconds, "hardEndNs": hard,
                    "handoffReturnedNs": checked_ns, "handoffReturnedLocal": checked_local,
                    "observedAfterReturnNs": observed_ns, "observedAfterReturnLocal": observed_local,
                    "observationScope": "HANDOFF_FUNCTION_RETURN_ONLY",
                    "recordWriterReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE",
                    "producerStepOutcome": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE",
                    "providerExecution": "NOT_PERFORMED", "budgetAcceptance": "NOT_ADMITTED",
                    "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
                current_pins()
                require(current_owner.read(index_directory, "save-handoff.json") == raw and
                        current_owner.read(initializer, "producer-function-return.json") == record_raw,
                        "BOOTSTRAP_PRODUCER_RETURN_READBACK_CHANGED")
                initializer.verify()
                index_directory.verify()
                boundary()
                current_pins()
                current_roster = tuple((row, row["label"], row["owner"]) for row in current_ledger)
            except BaseException as error:
                failed(error)
            finally:
                if current_owner is not None:
                    try:
                        current_owner.close()
                        if current_owner.original is not None:
                            failed(current_owner.original)
                    except BaseException as error:
                        failed(error)
                    if current_owner.unknown and not any(value is current_owner for value in QUARANTINE):
                        QUARANTINE.append(current_owner)
            if first_error is not None:
                raise first_error
            current_pins()
            require(current_owner.closed is True and len(current_ledger) == len(current_roster) and
                    all(row is old and row["label"] == label and row["owner"] is resource and
                        row["attempted"] is row["closed"] is True
                        for row, (old, label, resource) in zip(current_ledger, current_roster)),
                    "BOOTSTRAP_PRODUCER_RETURN_CLOSE_INCOMPLETE")
            boundary()
            current_pins()
            value = public_result("BOOTSTRAP_PRODUCER_PENDING_ORIGINAL_STEP_RETURN_V1",
                                  "producerReturnSha256", record_raw)
            value["handoffSha256"] = origin.digest(raw)
            return value, fence, hard

        result = handoff_prefix(raw, checked_ns, checked_local, complete)
        return result

    return execute, before, closed_before_return, handoff


(export_after_entry, before_save_after_entry, _checked_before_save_parent_return,
 save_handoff_after_entry) = _bootstrap_export_controls()
del _bootstrap_export_controls


def _read_save_handoff(owner, initializer, directory, admitted, *, producer_outcome, expected_sha256):
    """Read supplied package consistency, NOT trusted step/provider admission.

    The caller supplies its live bounded Owner and registered directories. This
    function neither creates/extends that owner nor closes borrowed resources.
    Its byte tuple returns with enclosing-owner close PENDING. No original-call
    registry is reconstructed. A future fixed workflow must bind the actual
    producer outcome/hash, never conclusion or a digest read from the package.
    The index lacks the final writer-return high-water; this reader does not
    consume the separate producer-return sidecar.
    """
    require(type(producer_outcome) is str and producer_outcome == "success",
            "BOOTSTRAP_SAVE_READ_PRODUCER_OUTCOME")
    require(type(expected_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", expected_sha256),
            "BOOTSTRAP_SAVE_READ_ORIGINAL_HASH")
    require(type(owner) is Owner and owner.first is not None and owner.fence is not None,
            "BOOTSTRAP_SAVE_READ_OWNER")
    first, fence, ledger, local_end = owner.first, owner.fence, owner.resources, owner.local_end
    cancelled = owner.cancelled
    limits = (owner.work_limit, owner.final_limit)
    origin.clocks.validate_reading(first)
    clock_raw, first_ns = origin.encoded(origin.clock_value(first.clock)), origin.integer(first.nanoseconds)

    def checked():
        require(type(owner) is Owner and owner.first is first and owner.fence is fence and owner.resources is ledger and
                owner.cancelled is cancelled and
                type(owner.local_end) is float and owner.local_end == local_end and
                (owner.work_limit, owner.final_limit) == limits and
                first.nanoseconds == first_ns and origin.encoded(origin.clock_value(first.clock)) == clock_raw and
                origin.encoded(origin.clock_value(fence.clock)) == clock_raw,
                "BOOTSTRAP_SAVE_READ_OWNER_CHANGED")
        require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                "BOOTSTRAP_SAVE_READ_PRIOR_UNKNOWN")
        owner.end()
        # A bound fence need not forward the borrowed owner's cancellation.
        cancelled()

    def same(actual, expected, reason="BOOTSTRAP_SAVE_READ_BINDING"):
        require(origin.encoded(actual) == origin.encoded(expected), reason)

    names = (
        "before-parent.json", "before-leaf.json", "export-parent.json", "export-leaf.json",
        "no-loader-parent.json", "no-loader-leaf.json", "collection-parent.json", "collection-leaf.json",
        "collection-inventory.json", "producer-parent.json", "producer-request.json", "producer-observation.json",
        "producer-command.json", "producer-birth.json", "producer-leader.json", "producer-preparer.json",
        "producer-terminal.json", "producer-survivors.json", "custody-parent.json", "custody-leaf.json",
        "seed-parent.json", "stage-parent.json", "stage-leaf.json", "seed-leaf.json", "initializer-parent.json",
        "recipient-parent.json", "allocation-proposal.json", "entry-parent.json", "adoption-parent.json",
        "adoption-preparation.json", "entry-preparation.json",
    )
    try:
        checked()
        admission = origin.admitted_value(admitted)  # Supplied-data check, NOT fresh native admission.
        profile, role = bootstrap.cache_cohort(admitted.record)
        require(role == first.clock.role and initializer.path.is_absolute() and ".." not in initializer.path.parts and
                initializer.path.name == "initializer" and initializer.path.parent.name ==
                "p2pkit-cache-originals-" + admission["github"]["runId"] + "-" + admission["github"]["runAttempt"] +
                "-" + admission["selection"] + "-productive" and
                directory.path == initializer.path / "dependency-save-handoff", "BOOTSTRAP_SAVE_READ_LAYOUT")
        session, path = initializer.path, directory.path
        parent_id = directory_identity(list(initializer.identity), role)
        directory_id = directory_identity(list(directory.identity), role)
        require(parent_id != directory_id, "BOOTSTRAP_SAVE_READ_DIRECTORY_ALIAS")

        def locations():
            checked()
            _new_entry_owned(owner, initializer, session, parent_id)
            _new_entry_owned(owner, directory, path, directory_id)
            checked()

        locations()
        raw = owner.read(directory, "save-handoff.json")
        require(type(raw) is bytes and 0 < len(raw) <= LIMIT and origin.digest(raw) == expected_sha256,
                "BOOTSTRAP_SAVE_READ_HASH_CHANGED")
        value = origin.parse(raw)
        require(type(value) is dict and set(value) == {"schema", "scope", "binding", "source", "github", "selection",
                "cacheCohort", "plan", "planSha256", "directory", "directoryIdentity", "blobs", "references", "chain",
                "window", "writerReturn", "providerExecution", "nextPhaseAuthority", "budgetAcceptance", "testAcceptance",
                "exportSaveAuthority"} and raw == origin.encoded(value) and type(value["schema"]) is int and
                value["schema"] == 1 and value["scope"] == "BOOTSTRAP_SAVE_HANDOFF_PENDING_ORIGINAL_STEP_RETURN_V1" and
                value["writerReturn"] == "PENDING_NOT_OBSERVABLE_BY_THIS_FILE" and value["providerExecution"] == "NOT_PERFORMED" and
                value["budgetAcceptance"] == "NOT_ADMITTED" and value["testAcceptance"] == "NOT_PERFORMED" and
                value["nextPhaseAuthority"] is value["exportSaveAuthority"] is False and
                type(value["references"]) is dict and type(value["chain"]) is dict,
                "BOOTSTRAP_SAVE_READ_INDEX")
        for name in ("source", "github", "selection", "cacheCohort"):
            same(value[name], admission[name])
        same(value["directory"], str(path))
        same(value["directoryIdentity"], directory_id)
        plan, binding = value["plan"], value["binding"]
        staging.cache._plan_shape(plan)  # Structural only; validate_plan/source rederivation remains outstanding.
        container = staging.files.stage_path(session, profile, role, admitted_raw=admitted.record)
        for name, expected in (("mode", "bootstrap"), ("profile", profile), ("role", role),
                ("source", admission["source"]), ("github", admission["github"]),
                ("admissionSha256", origin.digest(admitted.record)), ("session", str(session)),
                ("restoreHome", str(container / "restore-home")),
                ("path", str((container / "restore-home").joinpath(*staging.files.PREFIX)))):
            same(plan[name], expected)
        same(value["planSha256"], origin.digest(origin.encoded(plan)))
        require(type(binding) is dict, "BOOTSTRAP_SAVE_READ_BINDING")
        for name, expected in (("admissionSha256", plan["admissionSha256"]), ("session", str(session)),
                ("state", str(session / "state")), ("home", str(session / "state/gradle-home")),
                ("container", str(container)), ("restoreHome", plan["restoreHome"]),
                ("clock", origin.clock_value(first.clock))):
            same(binding[name], expected)
        same(binding["initializerDirectories"]["session"], parent_id)
        require(type(value["blobs"]) is dict and set(value["blobs"]) == set(names), "BOOTSTRAP_SAVE_READ_BLOB_ROSTER")
        roster = tuple(sorted((*names, "save-handoff.json")))
        require(_initializer_names(owner, directory) == roster, "BOOTSTRAP_SAVE_READ_DIRECTORY_ROSTER")
        blobs = {}
        for name in names:  # Never traverse reference paths or JSON-selected filenames.
            locations()
            row = value["blobs"][name]
            require(type(row) is dict and set(row) == {"bytes", "sha256"} and type(row["bytes"]) is int and
                    0 < row["bytes"] <= LIMIT and staging.cache._sha(row["sha256"]), "BOOTSTRAP_SAVE_READ_BLOB_BINDING")
            blob = owner.read(directory, name, row["bytes"])
            require(type(blob) is bytes and len(blob) == row["bytes"] and origin.digest(blob) == row["sha256"],
                    "BOOTSTRAP_SAVE_READ_BLOB_CHANGED")
            blobs[name] = blob

        proposal, before, exported = (origin.parse(blobs[name]) for name in
            ("allocation-proposal.json", "before-parent.json", "export-parent.json"))
        same(binding["proposalSha256"], origin.digest(blobs["allocation-proposal.json"]))
        for name in ("source", "github", "selection", "cacheCohort"):
            same(proposal[name], admission[name])
        same(proposal["clock"], origin.clock_value(first.clock))
        require(proposal["scope"] == allocation.SCOPE and proposal["budgetAcceptance"] == "NOT_ADMITTED" and
                proposal["testAcceptance"] == "NOT_PERFORMED" and proposal["exportSaveAuthority"] is False,
                "BOOTSTRAP_SAVE_READ_PROPOSAL")
        for name, scope in (("before-leaf.json", dependency_save_set.SCOPE), ("export-leaf.json", dependency_export.SCOPE),
                            ("stage-leaf.json", staging.STAGE_SCOPE), ("seed-leaf.json", staging.SEED_SCOPE)):
            leaf = origin.parse(blobs[name])
            require(leaf["scope"] == scope, "BOOTSTRAP_SAVE_READ_LEAF_SCOPE")
            same(leaf["binding"], binding)
            same(leaf["plan"], plan)
        for parent, scope, leaf_name in ((before, "BOOTSTRAP_SAVE_SET_PARENT_CLOSED_OBSERVATIONS_V1", "before-leaf.json"),
                (exported, "BOOTSTRAP_EXPORT_PARENT_CLOSED_OBSERVATIONS_V1", "export-leaf.json")):
            require(parent["scope"] == scope and parent["parentResourceClose"] == "KNOWN_RESOURCE_CLOSE_ONLY" and
                    parent["nextPhaseAuthority"] is parent["exportSaveAuthority"] is False and
                    parent["budgetAcceptance"] == "NOT_ADMITTED" and parent["testAcceptance"] == "NOT_PERFORMED",
                    "BOOTSTRAP_SAVE_READ_PARENT")
            same(parent["clock"], origin.clock_value(first.clock))
            same(parent["leafSha256"], origin.digest(blobs[leaf_name]))
        same(before["exportParentSha256"], origin.digest(blobs["export-parent.json"]))
        frozen = origin.parse(blobs["before-leaf.json"])
        same(frozen["exportSha256"], origin.digest(blobs["export-leaf.json"]))
        window, returned = value["window"], value["chain"]["returns"]["before"]
        require(type(window) is dict and set(window) == {"phase", "clock", "firstNs", "hardEndNs",
                "predecessorCheckedNs", "predecessorSha256"} and window["phase"] == "producer-owner-return",
                "BOOTSTRAP_SAVE_READ_WINDOW")
        same(window["clock"], origin.clock_value(first.clock))
        same(window["predecessorSha256"], origin.digest(blobs["before-parent.json"]))
        same(window["predecessorCheckedNs"], origin.integer(returned["checkedNs"]))
        staging._local(returned["checkedLocal"])  # Historical only; not a new process's LOCAL floor.
        began, hard = origin.integer(window["firstNs"]), origin.integer(window["hardEndNs"])
        require(origin.integer(before["firstNs"]) <= origin.integer(before["closedNs"]) <=
                window["predecessorCheckedNs"] < origin.integer(before["hardEndNs"]) and
                window["predecessorCheckedNs"] <= began < hard == min(origin.integer(began + 45 * staging.NS),
                    origin.integer(proposal["phaseFencesNs"]["producer-owner-return"]),
                    origin.integer(proposal["proposedJobEndNs"])) and first_ns >= began,
                "BOOTSTRAP_SAVE_READ_RECORDED_CHRONOLOGY")
        # Only the retained before floor and writer's first observation exist
        # here, NOT the writer's final checked_ns/checked_local or step return.
        require(_initializer_names(owner, directory) == roster, "BOOTSTRAP_SAVE_READ_DIRECTORY_ROSTER")
        for name in names:
            locations()
            require(owner.read(directory, name, len(blobs[name])) == blobs[name], "BOOTSTRAP_SAVE_READ_REREAD_CHANGED")
        require(owner.read(directory, "save-handoff.json") == raw, "BOOTSTRAP_SAVE_READ_INDEX_CHANGED")
        require(_initializer_names(owner, directory) == roster, "BOOTSTRAP_SAVE_READ_DIRECTORY_ROSTER")
        locations()
        return raw, tuple((name, blobs[name]) for name in names)
    except BaseException as error:
        # The caller still owns cleanup. Preserve a prior/falsey cause and let
        # the existing owner quarantine an uncertain reader/close normally.
        original = owner.original if owner.original is not None else error
        try:
            owner.error("save-handoff-read", error)
        except BaseException:
            owner.unknown = True
        raise original


def _producer_return_record(raw, handoff_raw, expected_sha256, first, initializer, directory):
    """Check supplied return bytes, not authenticate a workflow step or LOCAL epoch."""
    require(type(expected_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) and
            type(raw) is bytes and 0 < len(raw) <= LIMIT and origin.digest(raw) == expected_sha256,
            "BOOTSTRAP_SAVE_PRODUCER_RETURN_HASH")
    value, handoff = origin.parse(raw), origin.parse(handoff_raw)
    require(type(value) is dict and set(value) == {"schema", "scope", "handoffSha256", "handoffDirectory",
            "handoffDirectoryIdentity", "initializerIdentity", "clock", "firstNs", "hardEndNs",
            "handoffReturnedNs", "handoffReturnedLocal", "observedAfterReturnNs", "observedAfterReturnLocal",
            "observationScope", "recordWriterReturn", "producerStepOutcome", "providerExecution",
            "budgetAcceptance", "testAcceptance", "exportSaveAuthority"} and raw == origin.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == "BOOTSTRAP_HANDOFF_FUNCTION_RETURN_PENDING_COMMAND_V1" and
            value["observationScope"] == "HANDOFF_FUNCTION_RETURN_ONLY" and
            value["recordWriterReturn"] == value["producerStepOutcome"] == "PENDING_NOT_OBSERVABLE_BY_THIS_FILE" and
            value["providerExecution"] == "NOT_PERFORMED" and value["budgetAcceptance"] == "NOT_ADMITTED" and
            value["testAcceptance"] == "NOT_PERFORMED" and value["exportSaveAuthority"] is False,
            "BOOTSTRAP_SAVE_PRODUCER_RETURN_RECORD")
    origin.clocks.validate_reading(first)
    require(value["handoffSha256"] == origin.digest(handoff_raw) and
            value["handoffDirectory"] == str(directory.path) and
            directory_identity(value["handoffDirectoryIdentity"], first.clock.role) == list(directory.identity) and
            directory_identity(value["initializerIdentity"], first.clock.role) == list(initializer.identity) and
            origin.encoded(value["clock"]) == origin.encoded(origin.clock_value(first.clock)) ==
            origin.encoded(handoff["window"]["clock"]), "BOOTSTRAP_SAVE_PRODUCER_RETURN_BINDING")
    began, hard, returned, observed = (origin.integer(value[name]) for name in
        ("firstNs", "hardEndNs", "handoffReturnedNs", "observedAfterReturnNs"))
    require(began == origin.integer(handoff["window"]["firstNs"]) and
            hard == origin.integer(handoff["window"]["hardEndNs"]) and
            began <= returned <= observed < hard and first.nanoseconds >= observed,
            "BOOTSTRAP_SAVE_PRODUCER_RETURN_CHRONOLOGY")
    require(type(value["handoffReturnedLocal"]) is type(value["observedAfterReturnLocal"]) is float and
            staging._local(value["handoffReturnedLocal"]) <= staging._local(value["observedAfterReturnLocal"]),
            "BOOTSTRAP_SAVE_PRODUCER_RETURN_LOCAL_HISTORY")
    # The producer's LOCAL numbers are historical within that process only.
    # Only the admitted shared RAW clock supplies this new command's floor.
    return value


def _save_original_inventory(index, blobs, compiled, stage, staging_binding, proposal):
    """Check supplied complete export/freeze data; do not walk or freeze S again."""
    files = staging.files
    exported, frozen = (origin.parse(blobs[name]) for name in ("export-leaf.json", "before-leaf.json"))
    for value, name in ((exported, "export-leaf.json"), (frozen, "before-leaf.json")):
        require(type(value) is dict and type(value["schema"]) is int and value["schema"] == 1 and
                blobs[name] == origin.encoded(value) and value["completed"] is True and
                value["retirement"] == "KNOWN" and value["errors"] == [] and
                value["nextPhaseAuthority"] is value["exportSaveAuthority"] is False and
                value["budgetAcceptance"] == "NOT_ADMITTED" and value["testAcceptance"] == "NOT_PERFORMED" and
                value["inputProvenance"] == "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL",
                "BOOTSTRAP_SAVE_ORIGINAL_NOT_KNOWN")
    require(exported["status"] in dependency_export.STATUSES[1:] and
            exported["destinationIdentity"] == stage["sourceIdentity"] and
            exported["sourceIdentity"] == index["binding"]["initializerDirectories"]["gradle-home"] and
            exported["home"] == index["binding"]["home"] and exported["restoreHome"] == index["plan"]["restoreHome"] and
            exported["propertiesSha256"] == index["binding"]["propertiesSha256"] and
            origin.encoded(exported["policy"]) == origin.encoded(files.policy()),
            "BOOTSTRAP_SAVE_EXPORT_BINDING")
    files._validate_inventory(exported, compiled, statuses=dependency_export.STATUSES,
                              destination_identity=stage["sourceIdentity"])
    require(0 < exported["counts"]["outputBytes"] <= files.TOTAL_LIMIT,
            "BOOTSTRAP_SAVE_POSITIVE_EXPORT_REQUIRED")
    require(set(frozen) == {"schema", "scope", "binding", "predecessors", "exportSha256", "plan", "phase",
            "beforeSaveSha256", "status", "completed", "retirement", "errors", "container", "stagingFile",
            "directories", "files", "counts", "inputProvenance", "atomicSnapshot", "nextPhaseAuthority",
            "budgetAcceptance", "testAcceptance", "exportSaveAuthority", "saveSetInputs", "window"} and
            frozen["scope"] == dependency_save_set.SCOPE and frozen["phase"] == "before-save" and
            frozen["beforeSaveSha256"] is None and frozen["status"] == "KNOWN_FROZEN" and
            frozen["atomicSnapshot"] is False and
            origin.encoded(frozen["predecessors"]) == origin.encoded(exported["predecessors"]),
            "BOOTSTRAP_SAVE_BEFORE_BINDING")
    directories, selected = staging.cache._save_roster(exported)
    expected_counts = {"hashedBytes": exported["counts"]["outputBytes"], "verifiedFiles": len(selected),
                       "members": exported["counts"]["destinationMembers"]}
    require(type(frozen["counts"]) is dict and origin.encoded(frozen["counts"]) == origin.encoded(expected_counts) and
            frozen["files"] == sorted(row["path"] for row in selected.values()), "BOOTSTRAP_SAVE_INCOMPLETE_ROSTER")
    container = frozen["container"]
    require(type(container) is dict and set(container) == {"binding", "names"} and
            files._file_binding(container["binding"]) and
            container["binding"]["identity"] == stage["containerIdentity"] and
            container["names"] == ["restore-home", "staging.json"] and files._file_binding(frozen["stagingFile"]) and
            origin.encoded(frozen["stagingFile"]) == origin.encoded(staging_binding),
            "BOOTSTRAP_SAVE_CONTAINER_BINDING")
    rows = frozen["directories"]
    require(type(rows) is list and len(rows) == len(directories), "BOOTSTRAP_SAVE_DIRECTORY_ROSTER")
    identities = {tuple(stage["containerIdentity"]), tuple(staging_binding["identity"])}
    require(len(identities) == 2, "BOOTSTRAP_SAVE_CONTAINER_ALIAS")
    for row, parts in zip(rows, sorted(directories)):
        require(type(row) is dict and set(row) == {"path", "binding", "names"} and
                row["path"] == "/".join(parts) and row["names"] == list(directories[parts]) and
                files._file_binding(row["binding"]) and
                row["binding"]["identity"][0] == stage["sourceIdentity"][0] and
                tuple(row["binding"]["identity"]) not in identities and
                (bool(parts) or row["binding"]["identity"] == stage["sourceIdentity"]),
                "BOOTSTRAP_SAVE_DIRECTORY_BINDING")
        identities.add(tuple(row["binding"]["identity"]))
    require(all(tuple(row["destination"]["identity"]) not in identities for row in selected.values()),
            "BOOTSTRAP_SAVE_FILE_DIRECTORY_ALIAS")
    before_parent, export_parent = (origin.parse(blobs[name]) for name in ("before-parent.json", "export-parent.json"))
    window = frozen["window"]
    require(type(window) is dict and set(window) == {"phase", "clock", "firstNs", "hardEndNs", "softEndNs",
            "lastNewWorkNs", "finishedNs", "predecessorSha256", "predecessorCheckedNs", "proposalSha256"} and
            window["phase"] == "save-set-before" and
            window["proposalSha256"] == origin.digest(blobs["allocation-proposal.json"]) and
            window["predecessorSha256"] == origin.digest(blobs["export-parent.json"]) and
            origin.encoded(window["clock"]) == origin.encoded(index["binding"]["clock"]),
            "BOOTSTRAP_SAVE_BEFORE_WINDOW")
    first, hard, soft, last_new, finished, prior = (origin.integer(window[name]) for name in
        ("firstNs", "hardEndNs", "softEndNs", "lastNewWorkNs", "finishedNs", "predecessorCheckedNs"))
    require(hard == min(origin.integer(first + 120 * staging.NS), proposal["phaseFencesNs"]["save-set-before"],
                       proposal["proposedJobEndNs"]) and soft == min(hard, origin.integer(first + 90 * staging.NS)) and
            origin.integer(exported["window"]["finishedNs"]) <= origin.integer(export_parent["closedNs"]) <=
            prior <= first <= last_new <= finished <= origin.integer(before_parent["closedNs"]) <=
            origin.integer(index["chain"]["returns"]["before"]["checkedNs"]) < hard and last_new < soft and
            all(origin.encoded(before_parent[name]) == origin.encoded(window[name])
                for name in ("clock", "firstNs", "hardEndNs", "softEndNs")), "BOOTSTRAP_SAVE_BEFORE_WINDOW")


def prepare_save(cancelled):
    """Fixed dormant save transition; private descriptor only, never a provider.

    A successful original producer step and its two exported hashes are required.
    New native admission and source/plan/proposal rederivation share first30;
    no old owner/capability/LOCAL fence is reconstructed or prolonged.
    """
    local_start = staging._local(time.monotonic())
    first = origin.clocks.validate_reading(origin.clocks.observe())
    hard = origin.integer(first.nanoseconds + 30 * staging.NS)
    issued_end = origin.wire._directed_deadline(local_start, 30, hard, first.nanoseconds)
    last, local_last = first.nanoseconds, local_start
    owner = target = result_raw = None
    failure = None

    class SaveFence:
        __slots__ = ()
        clock = first.clock

        def now(self, *, final=False, minimum=0, limit=None):
            nonlocal last, local_last, issued_end
            require(type(final) is bool, "BOOTSTRAP_SAVE_TRANSITION_FINAL_FLAG")
            if not final:
                cancellation(cancelled)
            before = staging._local(time.monotonic())
            require(before >= local_last, "BOOTSTRAP_SAVE_TRANSITION_LOCAL_BACKWARDS")
            local_last = before
            observed = origin.clocks.validate_reading(origin.clocks.observe())
            require(observed.clock == first.clock and observed.nanoseconds >= max(last, origin.integer(minimum)),
                    "BOOTSTRAP_SAVE_TRANSITION_RAW_BACKWARDS")
            last = observed.nanoseconds
            after = staging._local(time.monotonic())
            require(after >= local_last, "BOOTSTRAP_SAVE_TRANSITION_LOCAL_BACKWARDS")
            local_last = after
            cap = hard if limit is None else min(hard, origin.integer(limit))
            issued_end = min(issued_end, origin.wire._directed_deadline(before, 30, cap, last))
            require(last < cap and local_last < issued_end, "BOOTSTRAP_SAVE_TRANSITION_EXPIRED")
            if not final:
                cancellation(cancelled)
                return self.now(final=True, minimum=last, limit=cap)
            return last

        def deadline(self, maximum, *, final=False, limit=None):
            require(type(maximum) in (int, float) and math.isfinite(maximum) and maximum > 0,
                    "BOOTSTRAP_SAVE_TRANSITION_MAXIMUM")
            self.now(final=final, limit=limit)
            return min(issued_end, local_last + min(30, maximum))

    fence = SaveFence()

    def shorten(proposal):
        nonlocal hard, issued_end
        hard = min(hard, origin.integer(proposal["phaseFencesNs"]["save-transition"]),
                   origin.integer(proposal["proposedJobEndNs"]))
        require(first.nanoseconds < hard, "BOOTSTRAP_SAVE_TRANSITION_EXPIRED")
        issued_end = min(issued_end, origin.wire._directed_deadline(local_start, 30, hard, first.nanoseconds))
        fence.now()

    def failed(error):
        nonlocal failure
        if failure is None:
            failure = owner.original if owner is not None and owner.original is not None else error
        if owner is not None:
            try:
                owner.error("prepare-save", error)
            except BaseException:
                owner.unknown = True

    try:
        fence.now()
        require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                "BOOTSTRAP_SAVE_PRIOR_UNKNOWN")
        require(origin.wire.TOKEN_ENV not in os.environ and
                os.environ.get("P2PKIT_BOOTSTRAP_PRODUCER_OUTCOME") == "success",
                "BOOTSTRAP_SAVE_ORIGINAL_PRODUCER_OUTCOME")
        handoff_hash = os.environ.get("P2PKIT_BOOTSTRAP_HANDOFF_SHA256")
        return_hash = os.environ.get("P2PKIT_BOOTSTRAP_PRODUCER_RETURN_SHA256")
        require(all(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value)
                    for value in (handoff_hash, return_hash)), "BOOTSTRAP_SAVE_ORIGINAL_PRODUCER_HASHES")
        selection, original_path, event = host_inputs(first.clock.role)
        child_environment(original_path)  # Reject ambient execution/Git overrides; launch nothing.
        runner_name = os.environ.get("RUNNER_NAME")
        session = original_path.with_name(original_path.name + "-productive") / "initializer"
        path = original_path.with_name(original_path.name + "-save")
        owner = Owner(issued_end, fence, first=first, cancelled=lambda: cancellation(cancelled))
        ledger, errors, owner_end, callback = owner.resources, owner.errors, owner.local_end, owner.cancelled

        def checked():
            require(type(owner) is Owner and owner.fence is fence and owner.first is first and
                    owner.resources is ledger and owner.errors is errors and owner.cancelled is callback and
                    type(owner.local_end) is float and owner.local_end == owner_end and
                    owner.work_limit is owner.final_limit is None and owner.original is None and not owner.unknown,
                    "BOOTSTRAP_SAVE_TRANSITION_OWNER_CHANGED")
            cancellation(cancelled)
            return owner.end()

        initializer = owner.open(session)
        directory = owner.child(initializer, "dependency-save-handoff")
        handoff_raw = owner.read(directory, "save-handoff.json")
        require(origin.digest(handoff_raw) == handoff_hash, "BOOTSTRAP_SAVE_ORIGINAL_HANDOFF_HASH")
        index = origin.parse(handoff_raw)
        require(handoff_raw == origin.encoded(index), "BOOTSTRAP_SAVE_ORIGINAL_HANDOFF_ENCODING")
        proposal_raw = owner.read(directory, "allocation-proposal.json")
        row = index["blobs"]["allocation-proposal.json"]
        require(type(row["bytes"]) is int and row["bytes"] == len(proposal_raw) and
                row["sha256"] == origin.digest(proposal_raw), "BOOTSTRAP_SAVE_ORIGINAL_PROPOSAL_HASH")
        # Recorded ends only DENY early. They grant nothing and cannot extend30;
        # full native/source/service rederivation below must still agree.
        shorten(origin.parse(proposal_raw))
        return_raw = owner.read(initializer, "producer-function-return.json")
        producer_return = _producer_return_record(return_raw, handoff_raw, return_hash, first, initializer, directory)
        target = owner.new(path)  # Exclusive one-use claim, outside the old graph/S/H/package.
        admitted, returned = admit(owner, fence, path / "admission")
        require(admitted.original_event == event, "BOOTSTRAP_SAVE_EVENT_CHANGED")
        owner.write(target, "admission-return.json", owner.admissions[str(path / "admission")][2])
        actual_raw, blobs = _read_save_handoff(owner, initializer, directory, admitted,
            producer_outcome="success", expected_sha256=handoff_hash)
        blobs = dict(blobs)
        require(actual_raw == handoff_raw and blobs["allocation-proposal.json"] == proposal_raw,
                "BOOTSTRAP_SAVE_PACKAGE_CHANGED")
        references = index["references"]

        def original(directory_, label, name):
            # All three names/paths below are fixed by source, never traversed
            # from the JSON reference. Retain its exact original byte binding.
            checked()
            reference = references[label]
            require(type(reference) is dict and set(reference) == {"directory", "directoryIdentity", "name",
                    "maximumBytes", "bytes", "sha256", "fileBinding", "bindingScope"} and
                    reference["directory"] == str(directory_.path) and reference["name"] == name and
                    type(reference["maximumBytes"]) is int and reference["maximumBytes"] == LIMIT and
                    type(reference["bytes"]) is int and 0 < reference["bytes"] <= LIMIT and
                    staging.cache._sha(reference["sha256"]), "BOOTSTRAP_SAVE_REFERENCE")
            _new_entry_owned(owner, directory_, directory_.path, reference["directoryIdentity"])
            return reference

        service = owner.open(original_path / "service")
        responses = {}
        for name in ("attempt", "jobs"):
            reference = original(service, "service/" + name, name + ".json")
            require(reference["fileBinding"] is None and reference["bindingScope"] ==
                    "ORIGINAL_DIRECTORY_AND_BYTES_OR_HASH_ONLY_NOT_FILE_IDENTITY", "BOOTSTRAP_SAVE_SERVICE_BINDING")
            raw = owner.read(service, name + ".json", reference["bytes"])
            require(len(raw) == reference["bytes"] and origin.digest(raw) == reference["sha256"],
                    "BOOTSTRAP_SAVE_SERVICE_CHANGED")
            responses[name] = raw
        require(index["binding"]["runnerName"] == runner_name, "BOOTSTRAP_SAVE_RUNNER_CHANGED")
        proposal = allocation.validate_proposal(proposal_raw, admitted, responses,
            index["binding"]["invocation"], first.clock, runner_name)
        shorten(proposal)
        inputs, compiled = staging.files.source_inputs(owner, ROOT, checked(), checked)
        profile, role = bootstrap.cache_cohort(admitted.record)
        container_path = staging.files.stage_path(session, profile, role, admitted_raw=admitted.record)
        container = owner.acquire("directory", lambda: staging.files.private_root(container_path))
        reference = original(container, "staging/staging", "staging.json")
        require(reference["fileBinding"] is not None and reference["bindingScope"] == "ORIGINAL_FILE_BINDING",
                "BOOTSTRAP_SAVE_STAGING_FILE_BINDING")

        class StageReader:
            """Only adapt the existing small bound-file reader to this Owner."""
            __slots__ = ()

            def end(self, *, new=False):
                return checked()

            def check(self):
                checked()

            def acquire(self, label, factory):
                return owner.acquire(label, factory)

            def error(self, stage, error):
                owner.error(stage, error)

            def close_one(self, value):
                if owner.unknown:
                    if owner.original is not None:
                        raise owner.original
                    raise origin.OriginError("BOOTSTRAP_SAVE_STAGING_READER_UNKNOWN")
                owner.close_one(value)
                if owner.original is not None:
                    raise owner.original
                require(not owner.unknown, "BOOTSTRAP_SAVE_STAGING_READER_UNKNOWN")

        staging_raw, _binding = staging._read(StageReader(), container, "staging.json",
            binding=reference["fileBinding"], maximum=reference["bytes"])
        require(len(staging_raw) == reference["bytes"] and origin.digest(staging_raw) == reference["sha256"],
                "BOOTSTRAP_SAVE_STAGING_CHANGED")
        end = checked()
        source = owner.acquire("save-stage-source", lambda: container.open_directory("restore-home", deadline=end))
        stage = origin.parse(staging_raw)
        staging.files.validate_stage(stage, admitted.record, profile, role, container_path,
                                     container.verify(), source.verify(), inputs)
        plan = staging.cache.validate_plan(index["plan"], admitted.record, staging_raw, compiled, inputs,
                                          session=session, profile=profile, role=role, mode="bootstrap")
        _save_original_inventory(index, blobs, compiled, stage, _binding, proposal)
        final_admitted, final_return = admit(owner, fence, path / "final-admission", expected=admitted)
        require(final_admitted == admitted and host_inputs(role) == (selection, original_path, event) and
                os.environ.get("RUNNER_NAME") == runner_name and origin.wire.TOKEN_ENV not in os.environ and
                os.environ.get("P2PKIT_BOOTSTRAP_PRODUCER_OUTCOME") == "success" and
                os.environ.get("P2PKIT_BOOTSTRAP_HANDOFF_SHA256") == handoff_hash and
                os.environ.get("P2PKIT_BOOTSTRAP_PRODUCER_RETURN_SHA256") == return_hash,
                "BOOTSTRAP_SAVE_FINAL_ADMISSION_CHANGED")
        child_environment(original_path)
        owner.write(target, "final-admission-return.json", owner.admissions[str(path / "final-admission")][2])
        require(owner.read(directory, "save-handoff.json") == handoff_raw and
                owner.read(initializer, "producer-function-return.json") == return_raw,
                "BOOTSTRAP_SAVE_FINAL_ORIGINALS_CHANGED")
        staging._read(StageReader(), container, "staging.json", expected=staging_raw,
                      binding=_binding, maximum=len(staging_raw))
        for name in ("attempt", "jobs"):
            require(owner.read(service, name + ".json") == responses[name], "BOOTSTRAP_SAVE_SERVICE_CHANGED")
        for resource in (initializer, directory, service, container, source):
            resource.verify()
        checked()
        issued = fence.now(minimum=producer_return["observedAfterReturnNs"])
        provider_end = min(origin.integer(issued + 180 * staging.NS),
                           proposal["phaseFencesNs"]["provider-save"], proposal["proposedJobEndNs"])
        require(issued < provider_end, "BOOTSTRAP_SAVE_PROVIDER_WINDOW_EXHAUSTED")
        result_raw = owner.write(target, "save-preparation.json", {
            "schema": 1, "scope": "BOOTSTRAP_SAVE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1",
            "source": index["source"], "github": index["github"], "selection": selection,
            "cacheCohort": index["cacheCohort"], "directory": str(path), "directoryIdentity": list(target.identity),
            "handoffSha256": handoff_hash, "producerReturnSha256": return_hash, "producerOriginalOutcome": "success",
            "admissionSha256": origin.digest(admitted.record), "admissionReturn": returned,
            "finalAdmissionReturn": final_return, "proposalSha256": origin.digest(proposal_raw),
            "plan": plan, "planSha256": origin.digest(origin.encoded(plan)),
            "clock": origin.clock_value(first.clock), "firstNs": first.nanoseconds, "hardEndNs": hard,
            "producerObservedAfterReturnNs": producer_return["observedAfterReturnNs"],
            "providerWindow": {"issuedNs": issued, "hardEndNs": provider_end,
                               "actualProviderStart": "NOT_OBSERVED"},
            "providerRequest": {"action": plan["provider"]["save"], "path": plan["path"], "key": plan["key"],
                                "enableCrossOsArchive": False, "scope": "PRIVATE_DESCRIPTOR_NOT_EXECUTION"},
            "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "providerExecution": "NOT_PERFORMED",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        checked()
        roster = tuple((row, row["label"], row["owner"]) for row in ledger)
    except BaseException as error:
        failed(error)
        if owner is not None and target is not None and not owner.unknown:
            try:
                owner.write(target, "save-preparation-failure.json", {"schema": 1, "result": "HOLD",
                    "errors": owner.errors, "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED"},
                    final=True)
            except BaseException as secondary:
                failed(secondary)
    finally:
        if owner is not None:
            try:
                owner.close()
                if owner.original is not None:
                    failed(owner.original)
            except BaseException as error:
                failed(error)
            if owner.unknown and not any(value is owner for value in QUARANTINE):
                QUARANTINE.append(owner)
    if failure is not None:
        raise failure
    require(result_raw is not None and owner.closed is True and owner.resources is ledger and owner.errors is errors and
            len(ledger) == len(roster) and all(row is old and row["label"] == label and row["owner"] is resource and
                row["attempted"] is row["closed"] is True
                for row, (old, label, resource) in zip(ledger, roster)), "BOOTSTRAP_SAVE_PREPARATION_CLOSE_INCOMPLETE")
    fence.now(final=True)
    cancellation(cancelled)
    return public_result("BOOTSTRAP_SAVE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1",
                         "savePreparationSha256", result_raw), fence, hard


def _save_preparation_record(raw, expected_sha256, admitted, handoff_raw, producer_raw, proposal, first, directory):
    """Validate supplied original descriptor bytes, never a provider start/stop."""
    require(type(expected_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) and
            type(raw) is bytes and 0 < len(raw) <= LIMIT and origin.digest(raw) == expected_sha256,
            "BOOTSTRAP_AFTER_SAVE_PREPARATION_HASH")
    value, index, produced = origin.parse(raw), origin.parse(handoff_raw), origin.parse(producer_raw)
    require(type(value) is dict and set(value) == {"schema", "scope", "source", "github", "selection", "cacheCohort",
            "directory", "directoryIdentity", "handoffSha256", "producerReturnSha256", "producerOriginalOutcome",
            "admissionSha256", "admissionReturn", "finalAdmissionReturn", "proposalSha256", "plan", "planSha256",
            "clock", "firstNs", "hardEndNs", "producerObservedAfterReturnNs", "providerWindow", "providerRequest",
            "writerReturn", "providerExecution", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"} and
            raw == origin.encoded(value) and type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == "BOOTSTRAP_SAVE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1" and
            value["producerOriginalOutcome"] == "success" and
            value["writerReturn"] == "PENDING_NOT_OBSERVABLE_BY_THIS_FILE" and
            value["providerExecution"] == value["testAcceptance"] == "NOT_PERFORMED" and
            value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False,
            "BOOTSTRAP_AFTER_SAVE_PREPARATION_RECORD")
    admission = origin.admitted_value(admitted)
    for name in ("source", "github", "selection", "cacheCohort"):
        require(origin.encoded(value[name]) == origin.encoded(index[name]) == origin.encoded(admission[name]),
                "BOOTSTRAP_AFTER_SAVE_PREPARATION_IDENTITY")
    require(value["directory"] == str(directory.path) and
            directory_identity(value["directoryIdentity"], first.clock.role) == list(directory.identity) and
            value["handoffSha256"] == origin.digest(handoff_raw) and
            value["producerReturnSha256"] == origin.digest(producer_raw) and
            value["admissionSha256"] == origin.digest(admitted.record) and
            value["proposalSha256"] == origin.digest(origin.encoded(proposal)) and
            origin.encoded(value["clock"]) == origin.encoded(origin.clock_value(first.clock)) and
            origin.encoded(value["plan"]) == origin.encoded(index["plan"]) and
            value["planSha256"] == origin.digest(origin.encoded(index["plan"])),
            "BOOTSTRAP_AFTER_SAVE_PREPARATION_BINDING")
    began, hard, prior = (origin.integer(value[name]) for name in
        ("firstNs", "hardEndNs", "producerObservedAfterReturnNs"))
    require(prior == origin.integer(produced["observedAfterReturnNs"]) and prior <= began < hard == min(
            origin.integer(began + 30 * staging.NS), proposal["phaseFencesNs"]["save-transition"],
            proposal["proposedJobEndNs"]), "BOOTSTRAP_AFTER_SAVE_PREPARATION_CHRONOLOGY")
    previous = began
    for name in ("admissionReturn", "finalAdmissionReturn"):
        returned = value[name]
        require(type(returned) is dict and set(returned) == {"admissionSha256", "sessionSha256", "clock", "returnedNs"}
                and returned["admissionSha256"] == value["admissionSha256"] and
                staging.cache._sha(returned["sessionSha256"]) and
                origin.encoded(returned["clock"]) == origin.encoded(value["clock"]) and
                previous <= origin.integer(returned["returnedNs"]) < hard,
                "BOOTSTRAP_AFTER_SAVE_PREPARATION_ADMISSION_RETURN")
        previous = returned["returnedNs"]
    window = value["providerWindow"]
    require(type(window) is dict and set(window) == {"issuedNs", "hardEndNs", "actualProviderStart"} and
            window["actualProviderStart"] == "NOT_OBSERVED", "BOOTSTRAP_AFTER_SAVE_PROVIDER_WINDOW")
    issued, provider_end = origin.integer(window["issuedNs"]), origin.integer(window["hardEndNs"])
    require(previous <= issued < hard and issued < provider_end == min(origin.integer(issued + 180 * staging.NS),
            proposal["phaseFencesNs"]["provider-save"], proposal["proposedJobEndNs"]) and
            issued <= first.nanoseconds < provider_end, "BOOTSTRAP_AFTER_SAVE_PROVIDER_RETURN_BOUND")
    require(origin.encoded(value["providerRequest"]) == origin.encoded({"action": index["plan"]["provider"]["save"],
            "path": index["plan"]["path"], "key": index["plan"]["key"], "enableCrossOsArchive": False,
            "scope": "PRIVATE_DESCRIPTOR_NOT_EXECUTION"}), "BOOTSTRAP_AFTER_SAVE_PROVIDER_REQUEST")
    return value


def _after_save_inputs(admitted, index, blobs, responses, original_path, clock, actuals):
    """Map retained data through existing validators; no old live graph is revived."""
    require(type(actuals) is dict and set(actuals) == {"initializer-context", "canonical-context", "properties", "staging"},
            "BOOTSTRAP_AFTER_SAVE_ACTUAL_ROSTER")
    binding, returns = index["binding"], index["chain"]["returns"]
    initial = returns["initializer"]
    originals = staging.Originals(admitted, responses, binding["invocation"], clock, binding["runnerName"],
        blobs["allocation-proposal.json"], str(original_path), actuals["initializer-context"], actuals["canonical-context"],
        actuals["properties"], binding["initializerDirectories"], blobs["initializer-parent.json"],
        initial["checkedNs"], initial["checkedLocal"])

    def leaf(name, filename):
        record = returns[name]["leaf"]
        return staging.LeafEvidence(blobs[filename], actuals["staging"], record["checkedNs"],
                                    record["localStarted"], record["checkedLocal"])

    seed_parent = returns["empty-seed"]["parent"]
    staged = custody.StagedEvidence(blobs["seed-parent.json"], blobs["stage-parent.json"],
        leaf("dependency-stage", "stage-leaf.json"), leaf("empty-seed", "seed-leaf.json"),
        seed_parent["checkedNs"], seed_parent["checkedLocal"])
    inputs = custody._Inputs(originals, staging._capture(originals), staged, custody._capture_staged(staged))
    require(origin.encoded(inputs.binding()) == origin.encoded(binding) and
            origin.encoded(inputs.stage_value["plan"]) == origin.encoded(index["plan"]),
            "BOOTSTRAP_AFTER_SAVE_SUPPLIED_INPUT_BINDING")
    return inputs


def after_save_originals(cancelled):
    """Fixed post-save acceptance guard, NOT provider execution/deadline enforcement.

    Actual trusted sequential step outcomes must come from a future workflow.
    The earliest new pair is only a post-action upper bound, never a start/return
    measurement. A late provider cannot be stopped retroactively by this guard.
    """
    local_start = staging._local(time.monotonic())
    first = origin.clocks.validate_reading(origin.clocks.observe())
    command_last, command_local = first.nanoseconds, local_start
    proposal = owner = fence = result_raw = None
    failure = None
    claims = {name: os.environ.get("P2PKIT_BOOTSTRAP_" + name) for name in
        ("PRODUCER_OUTCOME", "HANDOFF_SHA256", "PRODUCER_RETURN_SHA256", "SAVE_PREPARE_OUTCOME",
         "SAVE_PREPARATION_SHA256", "SAVE_OUTCOME")}

    def environment():
        require(origin.wire.TOKEN_ENV not in os.environ and
                all(os.environ.get("P2PKIT_BOOTSTRAP_" + name) == value for name, value in claims.items()),
                "BOOTSTRAP_AFTER_SAVE_ENVIRONMENT_CHANGED")
        require(all(claims[name] == "success" for name in
                ("PRODUCER_OUTCOME", "SAVE_PREPARE_OUTCOME", "SAVE_OUTCOME")),
                "BOOTSTRAP_AFTER_SAVE_ORIGINAL_OUTCOMES")
        require(all(type(claims[name]) is str and re.fullmatch(r"[0-9a-f]{64}", claims[name]) for name in
                ("HANDOFF_SHA256", "PRODUCER_RETURN_SHA256", "SAVE_PREPARATION_SHA256")),
                "BOOTSTRAP_AFTER_SAVE_ORIGINAL_HASHES")
        cancellation(cancelled)

    def phase_fence(name, began, local):
        # Only these three fixed command phases use this small local fence.
        seconds = {"save-readmission": 120, "save-observation": 30, "save-owner-return": 45}[name]
        require(began.clock == first.clock and began.nanoseconds >= command_last and local >= command_local,
                "BOOTSTRAP_AFTER_SAVE_PHASE_BACKWARDS")
        hard = origin.integer(began.nanoseconds + seconds * staging.NS)
        issued_end = origin.wire._directed_deadline(local, seconds, hard, began.nanoseconds)

        class Fence:
            __slots__ = ()
            clock = first.clock
            hard_end = property(lambda self: hard)
            local_end = property(lambda self: issued_end)
            last_local = property(lambda self: command_local)

            def shorten(self, value):
                nonlocal hard, issued_end
                hard = min(hard, origin.integer(value["phaseFencesNs"][name]),
                           origin.integer(value["proposedJobEndNs"]))
                issued_end = min(issued_end, origin.wire._directed_deadline(local, seconds, hard, began.nanoseconds))
                self.now()

            def now(self, *, final=False, minimum=0, limit=None):
                nonlocal command_last, command_local, issued_end
                if not final:
                    environment()
                before = staging._local(time.monotonic())
                require(before >= command_local, "BOOTSTRAP_AFTER_SAVE_LOCAL_BACKWARDS")
                command_local = before
                observed = origin.clocks.validate_reading(origin.clocks.observe())
                require(observed.clock == first.clock and observed.nanoseconds >= max(command_last, origin.integer(minimum)),
                        "BOOTSTRAP_AFTER_SAVE_RAW_BACKWARDS")
                command_last = observed.nanoseconds
                after = staging._local(time.monotonic())
                require(after >= command_local, "BOOTSTRAP_AFTER_SAVE_LOCAL_BACKWARDS")
                command_local = after
                cap = hard if limit is None else min(hard, origin.integer(limit))
                issued_end = min(issued_end, origin.wire._directed_deadline(before, seconds, cap, command_last))
                require(command_last < cap and command_local < issued_end, "BOOTSTRAP_AFTER_SAVE_PHASE_EXPIRED")
                if not final:
                    environment()
                    return self.now(final=True, minimum=command_last, limit=cap)
                return command_last

            def deadline(self, maximum, *, final=False, limit=None):
                require(type(maximum) in (int, float) and math.isfinite(maximum) and maximum > 0,
                        "BOOTSTRAP_AFTER_SAVE_MAXIMUM")
                self.now(final=final, limit=limit)
                return min(issued_end, command_local + min(seconds, maximum))

            def record(self):
                return {"phase": name, "clock": origin.clock_value(first.clock), "firstNs": began.nanoseconds,
                        "hardEndNs": hard, "localStarted": local, "localScope": "THIS_COMMAND_ONLY"}

        result = Fence()
        if proposal is not None:
            result.shorten(proposal)
        return result

    def next_pair():
        local = staging._local(time.monotonic())
        actual = origin.clocks.validate_reading(origin.clocks.observe())
        require(actual.clock == first.clock and actual.nanoseconds >= command_last and local >= command_local,
                "BOOTSTRAP_AFTER_SAVE_PHASE_BACKWARDS")
        return actual, local

    def close_known():
        nonlocal owner
        active, ledger, errors = owner, owner.resources, owner.errors
        roster = tuple((row, row["label"], row["owner"]) for row in ledger)
        active.close()
        if active.original is not None:
            raise active.original
        require(type(active) is Owner and active.closed is True and not active.unknown and not errors and
                active.resources is ledger and active.errors is errors and len(ledger) == len(roster) and
                all(row is old and set(row) == {"label", "owner", "attempted", "closed"} and row["label"] == label and
                    row["owner"] is resource and row["attempted"] is row["closed"] is True
                    for row, (old, label, resource) in zip(ledger, roster)) and
                not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                "BOOTSTRAP_AFTER_SAVE_OWNER_CLOSE_INCOMPLETE")
        closed = fence.now(final=True)
        result = {**fence.record(), "closedNs": closed, "closedLocal": fence.last_local,
                  "resourceCount": len(roster), "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY"}
        owner = None  # No later writer may use this closed object's handles.
        environment()
        fence.now(final=True)
        return result

    class BoundReader:
        """Adapt only the existing fixed-size bound reader to the active Owner."""
        __slots__ = ()

        def end(self, *, new=False):
            return owner.end()

        def check(self):
            owner.end()

        def acquire(self, label, factory):
            return owner.acquire(label, factory)

        def error(self, stage, error):
            owner.error(stage, error)

        def close_one(self, value):
            if owner.unknown:
                if owner.original is not None:
                    raise owner.original
                raise origin.OriginError("BOOTSTRAP_AFTER_SAVE_READER_UNKNOWN")
            owner.close_one(value)
            if owner.original is not None:
                raise owner.original
            require(not owner.unknown, "BOOTSTRAP_AFTER_SAVE_READER_UNKNOWN")

    try:
        environment()
        require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                "BOOTSTRAP_AFTER_SAVE_PRIOR_UNKNOWN")
        fence = phase_fence("save-readmission", first, local_start)
        selection, original_path, event = host_inputs(first.clock.role)
        child_environment(original_path)
        runner_name = os.environ.get("RUNNER_NAME")
        session = original_path.with_name(original_path.name + "-productive") / "initializer"
        path = original_path.with_name(original_path.name + "-after-save")
        owner = Owner(fence.local_end, fence, first=first, cancelled=environment)
        initializer = owner.open(session)
        directory = owner.child(initializer, "dependency-save-handoff")
        prepared_directory = owner.open(original_path.with_name(original_path.name + "-save"))
        prepared_raw = owner.read(prepared_directory, "save-preparation.json")
        require(origin.digest(prepared_raw) == claims["SAVE_PREPARATION_SHA256"],
                "BOOTSTRAP_AFTER_SAVE_PREPARATION_HASH")
        # Original saved scalars can deny before new native admission, never grant it.
        prepared = origin.parse(prepared_raw)
        require(first.nanoseconds < origin.integer(prepared["providerWindow"]["hardEndNs"]),
                "BOOTSTRAP_AFTER_SAVE_PROVIDER_RETURN_BOUND")
        handoff_raw = owner.read(directory, "save-handoff.json")
        require(origin.digest(handoff_raw) == claims["HANDOFF_SHA256"], "BOOTSTRAP_AFTER_SAVE_HANDOFF_HASH")
        index = origin.parse(handoff_raw)
        proposal_raw = owner.read(directory, "allocation-proposal.json")
        row = index["blobs"]["allocation-proposal.json"]
        require(type(row["bytes"]) is int and row["bytes"] == len(proposal_raw) and
                row["sha256"] == origin.digest(proposal_raw), "BOOTSTRAP_AFTER_SAVE_PROPOSAL_HASH")
        fence.shorten(origin.parse(proposal_raw))
        producer_raw = owner.read(initializer, "producer-function-return.json")
        _producer_return_record(producer_raw, handoff_raw, claims["PRODUCER_RETURN_SHA256"], first, initializer, directory)
        target = owner.new(path)
        target_identity = directory_identity(list(target.identity), first.clock.role)
        admitted, admission_return = admit(owner, fence, path / "admission")
        require(admitted.original_event == event, "BOOTSTRAP_AFTER_SAVE_EVENT_CHANGED")
        owner.write(target, "admission-return.json", owner.admissions[str(path / "admission")][2])
        actual_raw, blobs = _read_save_handoff(owner, initializer, directory, admitted,
            producer_outcome=claims["PRODUCER_OUTCOME"], expected_sha256=claims["HANDOFF_SHA256"])
        blobs = dict(blobs)
        require(actual_raw == handoff_raw and blobs["allocation-proposal.json"] == proposal_raw,
                "BOOTSTRAP_AFTER_SAVE_PACKAGE_CHANGED")
        originals = []

        def read_reference(directory_, label, name, *, bound):
            reference = index["references"][label]
            require(type(reference) is dict and set(reference) == {"directory", "directoryIdentity", "name", "maximumBytes",
                    "bytes", "sha256", "fileBinding", "bindingScope"} and reference["directory"] == str(directory_.path) and
                    reference["name"] == name and type(reference["maximumBytes"]) is int and reference["maximumBytes"] == LIMIT
                    and type(reference["bytes"]) is int and 0 < reference["bytes"] <= LIMIT and
                    staging.cache._sha(reference["sha256"]), "BOOTSTRAP_AFTER_SAVE_REFERENCE")
            _new_entry_owned(owner, directory_, directory_.path, reference["directoryIdentity"])
            if bound:
                require(reference["bindingScope"] == "ORIGINAL_FILE_BINDING" and reference["fileBinding"] is not None,
                        "BOOTSTRAP_AFTER_SAVE_REFERENCE_BINDING")
                raw, _ = staging._read(BoundReader(), directory_, name, binding=reference["fileBinding"],
                                      maximum=reference["bytes"])
            else:
                require(reference["fileBinding"] is None and reference["bindingScope"] ==
                        "ORIGINAL_DIRECTORY_AND_BYTES_OR_HASH_ONLY_NOT_FILE_IDENTITY",
                        "BOOTSTRAP_AFTER_SAVE_REFERENCE_BINDING")
                raw = owner.read(directory_, name, reference["bytes"])
            require(len(raw) == reference["bytes"] and origin.digest(raw) == reference["sha256"],
                    "BOOTSTRAP_AFTER_SAVE_REFERENCE_CHANGED")
            originals.append((directory_, name, reference, raw, bound))
            return raw

        service = owner.open(original_path / "service")
        responses = {name: read_reference(service, "service/" + name, name + ".json", bound=False)
                     for name in ("attempt", "jobs")}
        require(index["binding"]["runnerName"] == runner_name, "BOOTSTRAP_AFTER_SAVE_RUNNER_CHANGED")
        proposal = allocation.validate_proposal(proposal_raw, admitted, responses,
            index["binding"]["invocation"], first.clock, runner_name)
        fence.shorten(proposal)
        prepared = _save_preparation_record(prepared_raw, claims["SAVE_PREPARATION_SHA256"], admitted,
            handoff_raw, producer_raw, proposal, first, prepared_directory)
        source_inputs, compiled = staging.files.source_inputs(owner, ROOT, owner.end(), owner.end)
        profile, role = bootstrap.cache_cohort(admitted.record)
        container_path = staging.files.stage_path(session, profile, role, admitted_raw=admitted.record)
        container = owner.acquire("directory", lambda: staging.files.private_root(container_path))
        staging_raw = read_reference(container, "staging/staging", "staging.json", bound=True)
        end = owner.end()
        source = owner.acquire("after-save-stage", lambda: container.open_directory("restore-home", deadline=end))
        stage = origin.parse(staging_raw)
        staging.files.validate_stage(stage, admitted.record, profile, role, container_path,
                                     container.verify(), source.verify(), source_inputs)
        plan = staging.cache.validate_plan(index["plan"], admitted.record, staging_raw, compiled, source_inputs,
                                          session=session, profile=profile, role=role, mode="bootstrap")
        _save_original_inventory(index, blobs, compiled, stage, index["references"]["staging/staging"]["fileBinding"], proposal)
        actuals = {"staging": staging_raw}
        for key, location, name in (("initializer-context", session, "initializer-context.json"),
                ("canonical-context", session / "state", "context.json"),
                ("properties", session / "state/gradle-home", "gradle.properties")):
            location_owner = owner.acquire("directory", lambda location=location: staging.files.private_root(location))
            actuals[key] = read_reference(location_owner, "initializer-actual/" + key, name, bound=True)
        inputs = _after_save_inputs(admitted, index, blobs, responses, original_path, first.clock, actuals)
        final_admitted, final_return = admit(owner, fence, path / "final-admission", expected=admitted)
        require(final_admitted == admitted and host_inputs(role) == (selection, original_path, event) and
                os.environ.get("RUNNER_NAME") == runner_name, "BOOTSTRAP_AFTER_SAVE_FINAL_ADMISSION_CHANGED")
        environment()
        child_environment(original_path)
        owner.write(target, "final-admission-return.json", owner.admissions[str(path / "final-admission")][2])
        require(owner.read(directory, "save-handoff.json") == handoff_raw and
                owner.read(initializer, "producer-function-return.json") == producer_raw and
                owner.read(prepared_directory, "save-preparation.json") == prepared_raw,
                "BOOTSTRAP_AFTER_SAVE_FINAL_ORIGINALS_CHANGED")
        for directory_, name, reference, raw, bound in originals:
            _new_entry_owned(owner, directory_, directory_.path, reference["directoryIdentity"])
            if bound:
                staging._read(BoundReader(), directory_, name, expected=raw, binding=reference["fileBinding"],
                              maximum=len(raw))
            else:
                require(owner.read(directory_, name) == raw, "BOOTSTRAP_AFTER_SAVE_FINAL_ORIGINALS_CHANGED")
        readmission_close = close_known()

        # A distinct new owner runs exactly one existing full after-save walk.
        phase_first, phase_local = next_pair()
        previous = index["chain"]["returns"]["before"]
        window = dependency_save_set._AfterWindow(inputs, staging.PhaseStart(phase_first, phase_local),
            (blobs["before-parent.json"], previous["checkedNs"], previous["checkedLocal"]),
            current_process_floor=staging.PhaseStart(origin.clocks.Reading(first.clock, readmission_close["closedNs"]),
                                                     readmission_close["closedLocal"]))
        fixed = (window.first, window.soft, window.hard, window.local_start, window.local_soft, window.local_hard)
        local_end = window.local_hard

        class LeafFence:
            __slots__ = ()
            clock = first.clock
            last_local = property(lambda self: command_local)

            def now(self, *, final=False, minimum=0, limit=None):
                nonlocal command_last, command_local, local_end
                require(window.inputs is inputs and fixed == (window.first, window.soft, window.hard,
                        window.local_start, window.local_soft, window.local_hard), "BOOTSTRAP_AFTER_SAVE_LEAF_WINDOW_CHANGED")
                if not final:
                    environment()
                window.sample()
                require(window.last >= max(command_last, origin.integer(minimum)) and window.local_last >= command_local,
                        "BOOTSTRAP_AFTER_SAVE_LEAF_BACKWARDS")
                command_last, command_local = window.last, window.local_last
                cap = window.hard if limit is None else min(window.hard, origin.integer(limit))
                local_end = min(local_end, origin.wire._directed_deadline(command_local, 120, cap, command_last))
                require(command_last < cap and command_local < local_end, "BOOTSTRAP_AFTER_SAVE_PHASE_EXPIRED")
                if not final:
                    environment()
                    return self.now(final=True, minimum=command_last, limit=cap)
                return command_last

            def deadline(self, maximum, *, final=False, limit=None):
                self.now(final=final, limit=limit)
                return min(local_end, command_local + min(120, maximum))

            def record(self):
                return {"phase": "save-set-after", "clock": origin.clock_value(first.clock),
                        "firstNs": window.first, "softEndNs": window.soft, "hardEndNs": window.hard,
                        "localStarted": window.local_start, "localScope": "THIS_COMMAND_ONLY"}

        fence = LeafFence()
        owner = Owner(local_end, fence, first=phase_first, cancelled=environment)
        leaf = dependency_save_set.after_save(owner, inputs, window, blobs["export-leaf.json"], blobs["before-leaf.json"])
        require(type(leaf) is dependency_save_set.SaveSetEvidence and type(leaf.raw) is bytes and
                0 < len(leaf.raw) <= LIMIT and window.first <= origin.integer(leaf.checked_ns) <= window.last and
                leaf.local_started == window.local_start <= staging._local(leaf.checked_local) <= window.local_last,
                "BOOTSTRAP_AFTER_SAVE_LEAF_RETURN")
        leaf_raw, leaf_ns, leaf_local = leaf.raw, leaf.checked_ns, leaf.checked_local
        value = origin.parse(leaf_raw)
        require(value["scope"] == dependency_save_set.AFTER_SCOPE and value["status"] == "KNOWN_UNCHANGED" and
                value["completed"] is True and value["retirement"] == "KNOWN" and value["errors"] == [] and
                value["beforeSaveSha256"] == origin.digest(blobs["before-leaf.json"]) and
                value["exportSha256"] == origin.digest(blobs["export-leaf.json"]) and
                value["nextPhaseAuthority"] is value["exportSaveAuthority"] is False and
                value["testAcceptance"] == "NOT_PERFORMED" and value["budgetAcceptance"] == "NOT_ADMITTED",
                "BOOTSTRAP_AFTER_SAVE_LEAF_NOT_KNOWN")
        after_close = close_known()
        observation_first, observation_local = next_pair()
        fence = phase_fence("save-observation", observation_first, observation_local)
        owner = Owner(fence.local_end, fence, first=observation_first, cancelled=environment)
        provider = staging.cache.provider_observation(plan, "save", original_outcome=claims["SAVE_OUTCOME"], outputs={})
        require(provider["status"] == "SAVE_SUCCEEDED_STORAGE_UNPROVEN", "BOOTSTRAP_AFTER_SAVE_PROVIDER_NOT_SUCCESSFUL")
        owner.end()
        target = owner.open(path)
        _new_entry_owned(owner, target, path, target_identity)
        retained = {"after-leaf.json": leaf_raw, "save-preparation.json": prepared_raw,
            "provider-save.json": origin.encoded(provider), "readmission-close.json": origin.encoded({
                **readmission_close, "admissionReturn": admission_return, "finalAdmissionReturn": final_return}),
            "after-parent-close.json": origin.encoded({**after_close, "leafSha256": origin.digest(leaf_raw),
                "leafCheckedNs": leaf_ns, "leafCheckedLocal": leaf_local,
                "beforeParentSha256": origin.digest(blobs["before-parent.json"]),
                "historicalBeforeCheckedNs": previous["checkedNs"], "historicalBeforeCheckedLocal": previous["checkedLocal"],
                "historicalLocalScope": "ORIGINAL_PRODUCER_PROCESS_ONLY_NOT_COMPARED_WITH_THIS_COMMAND"})}
        for name, raw in retained.items():
            owner.write(target, name, raw)
        observations_raw = owner.write(target, "save-observations.json", {
            "schema": 1, "scope": "BOOTSTRAP_AFTER_SAVE_OBSERVATIONS_PENDING_WRITER_RETURN_V1",
            "source": index["source"], "github": index["github"], "selection": selection, "cacheCohort": index["cacheCohort"],
            "originalClaims": claims, "planSha256": origin.digest(origin.encoded(plan)),
            "clock": origin.clock_value(first.clock), "firstPostProviderNs": first.nanoseconds,
            "firstPostProviderLocal": local_start, "providerEndNs": prepared["providerWindow"]["hardEndNs"],
            "providerTimeScope": "POST_ACTION_UPPER_BOUND_ONLY_REQUIRES_TRUSTED_SEQUENTIAL_ORIGINAL_OUTCOME",
            "providerDeadlineEnforcement": "NOT_ESTABLISHED", "providerRetirement": "NOT_OBSERVED",
            "files": {name: origin.digest(raw) for name, raw in retained.items()},
            "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        observation_close = close_known()

        returned_first, returned_local = next_pair()
        fence = phase_fence("save-owner-return", returned_first, returned_local)
        owner = Owner(fence.local_end, fence, first=returned_first, cancelled=environment)
        target = owner.open(path)
        _new_entry_owned(owner, target, path, target_identity)
        for name, raw in {**retained, "save-observations.json": observations_raw}.items():
            require(owner.read(target, name) == raw, "BOOTSTRAP_AFTER_SAVE_RETAINED_OBSERVATIONS_CHANGED")
        result_raw = owner.write(target, "after-save-return.json", {
            "schema": 1, "scope": "BOOTSTRAP_AFTER_SAVE_PENDING_ORIGINAL_STEP_RETURN_V1",
            "directory": str(path), "directoryIdentity": target_identity, "clock": origin.clock_value(first.clock),
            "originalClaims": claims, "observationsSha256": origin.digest(observations_raw),
            "observationOwnerReturn": observation_close, "returnWindow": fence.record(),
            "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "providerStorage": "UNPROVEN",
            "providerDeadlineEnforcement": "NOT_ESTABLISHED", "providerRetirement": "NOT_OBSERVED",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        close_known()
    except BaseException as error:
        failure = owner.original if owner is not None and owner.original is not None else error
        if owner is not None:
            try:
                owner.error("after-save", error)
            except BaseException:
                owner.unknown = True
    finally:
        if owner is not None:
            try:
                owner.close()
                if failure is None and owner.original is not None:
                    failure = owner.original
            except BaseException as error:
                if failure is None:
                    failure = owner.original if owner.original is not None else error
            if owner.unknown and not any(value is owner for value in QUARANTINE):
                QUARANTINE.append(owner)
    if failure is not None:
        raise failure
    require(result_raw is not None and owner is None, "BOOTSTRAP_AFTER_SAVE_NOT_RETURNED")
    fence.now(final=True)
    environment()
    return public_result("BOOTSTRAP_AFTER_SAVE_PENDING_ORIGINAL_STEP_RETURN_V1", "afterSaveSha256", result_raw), fence, fence.hard_end


def _probe_after_save_records(owner, directory, expected_hash, claims, admitted, index, blobs, producer_raw,
                              proposal, first, prepared_directory):
    """Read the fixed hash-bound historical result, not a live old owner/clock."""
    raw = owner.read(directory, "after-save-return.json")
    require(origin.digest(raw) == expected_hash, "BOOTSTRAP_PROBE_AFTER_SAVE_HASH")
    returned = origin.parse(raw)
    require(type(returned) is dict and set(returned) == {"schema", "scope", "directory", "directoryIdentity", "clock",
            "originalClaims", "observationsSha256", "observationOwnerReturn", "returnWindow", "writerReturn",
            "providerStorage", "providerDeadlineEnforcement", "providerRetirement", "budgetAcceptance", "testAcceptance",
            "exportSaveAuthority"} and type(returned["schema"]) is int and returned["schema"] == 1 and
            raw == origin.encoded(returned) and returned["scope"] == "BOOTSTRAP_AFTER_SAVE_PENDING_ORIGINAL_STEP_RETURN_V1",
            "BOOTSTRAP_PROBE_AFTER_SAVE_RECORD")
    _new_entry_owned(owner, directory, directory.path, returned["directoryIdentity"])
    require(returned["directory"] == str(directory.path) and returned["providerStorage"] == "UNPROVEN",
            "BOOTSTRAP_PROBE_AFTER_SAVE_DIRECTORY")
    old_claims = {name: claims[name] for name in ("PRODUCER_OUTCOME", "HANDOFF_SHA256", "PRODUCER_RETURN_SHA256",
                                               "SAVE_PREPARE_OUTCOME", "SAVE_PREPARATION_SHA256", "SAVE_OUTCOME")}
    clock = origin.clock_value(first.clock)

    def nonacceptance(value):
        require(value["writerReturn"] == "PENDING_NOT_OBSERVABLE_BY_THIS_FILE" and
                value["providerDeadlineEnforcement"] == "NOT_ESTABLISHED" and value["providerRetirement"] == "NOT_OBSERVED"
                and value["budgetAcceptance"] == "NOT_ADMITTED" and value["testAcceptance"] == "NOT_PERFORMED" and
                value["exportSaveAuthority"] is False and origin.encoded(value["clock"]) == origin.encoded(clock) and
                origin.encoded(value["originalClaims"]) == origin.encoded(old_claims),
                "BOOTSTRAP_PROBE_AFTER_SAVE_CLAIMS")

    nonacceptance(returned)
    observations_raw = owner.read(directory, "save-observations.json")
    require(origin.digest(observations_raw) == returned["observationsSha256"], "BOOTSTRAP_PROBE_OBSERVATIONS_HASH")
    observations = origin.parse(observations_raw)
    require(type(observations) is dict and set(observations) == {"schema", "scope", "source", "github", "selection",
            "cacheCohort", "originalClaims", "planSha256", "clock", "firstPostProviderNs", "firstPostProviderLocal",
            "providerEndNs", "providerTimeScope", "providerDeadlineEnforcement", "providerRetirement", "files",
            "writerReturn", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"} and
            type(observations["schema"]) is int and observations["schema"] == 1 and
            observations_raw == origin.encoded(observations) and observations["scope"] ==
            "BOOTSTRAP_AFTER_SAVE_OBSERVATIONS_PENDING_WRITER_RETURN_V1" and observations["providerTimeScope"] ==
            "POST_ACTION_UPPER_BOUND_ONLY_REQUIRES_TRUSTED_SEQUENTIAL_ORIGINAL_OUTCOME" and
            observations["planSha256"] == origin.digest(origin.encoded(index["plan"])),
            "BOOTSTRAP_PROBE_OBSERVATIONS_RECORD")
    nonacceptance(observations)
    for name in ("source", "github", "selection", "cacheCohort"):
        require(origin.encoded(observations[name]) == origin.encoded(index[name]) ==
                origin.encoded(origin.admitted_value(admitted)[name]), "BOOTSTRAP_PROBE_OBSERVATIONS_IDENTITY")
    names = ("after-leaf.json", "save-preparation.json", "provider-save.json", "readmission-close.json",
             "after-parent-close.json")
    require(type(observations["files"]) is dict and set(observations["files"]) == set(names),
            "BOOTSTRAP_PROBE_OBSERVATIONS_ROSTER")
    retained = {name: owner.read(directory, name) for name in names}
    for name, value in retained.items():
        require(origin.digest(value) == observations["files"][name], "BOOTSTRAP_PROBE_OBSERVATION_CHANGED")
    post_ns = origin.integer(observations["firstPostProviderNs"])
    post_local = staging._local(observations["firstPostProviderLocal"])
    require(post_ns <= first.nanoseconds, "BOOTSTRAP_PROBE_AFTER_SAVE_BACKWARDS")
    # This is historical data, not today's observation or a renewed save window.
    prepared = _save_preparation_record(retained["save-preparation.json"], claims["SAVE_PREPARATION_SHA256"], admitted,
        origin.encoded(index), producer_raw, proposal, origin.clocks.Reading(first.clock, post_ns), prepared_directory)
    require(observations["providerEndNs"] == prepared["providerWindow"]["hardEndNs"] and
            owner.read(prepared_directory, "save-preparation.json") == retained["save-preparation.json"],
            "BOOTSTRAP_PROBE_ORIGINAL_SAVE_PREPARATION_CHANGED")
    provider = origin.parse(retained["provider-save.json"])
    require(retained["provider-save.json"] == origin.encoded(staging.cache.provider_observation(
            index["plan"], "save", original_outcome=claims["SAVE_OUTCOME"], outputs={})) and
            provider["status"] == "SAVE_SUCCEEDED_STORAGE_UNPROVEN", "BOOTSTRAP_PROBE_ORIGINAL_SAVE_OUTCOME")
    before, after = origin.parse(blobs["before-leaf.json"]), origin.parse(retained["after-leaf.json"])
    require(type(after) is dict and set(after) == set(before) and retained["after-leaf.json"] == origin.encoded(after) and
            after["scope"] == dependency_save_set.AFTER_SCOPE and after["phase"] == "after-save" and
            after["status"] == "KNOWN_UNCHANGED" and after["beforeSaveSha256"] == origin.digest(blobs["before-leaf.json"])
            and origin.encoded(before) == origin.encoded({**after, "scope": dependency_save_set.SCOPE,
                "phase": "before-save", "status": "KNOWN_FROZEN", "beforeSaveSha256": None, "window": before["window"]}),
            "BOOTSTRAP_PROBE_AFTER_SAVE_SET_CHANGED")
    readmission, parent = (origin.parse(retained[name]) for name in ("readmission-close.json", "after-parent-close.json"))
    previous_ns, previous_local = post_ns, post_local
    common = {"phase", "clock", "firstNs", "hardEndNs", "localStarted", "localScope"}
    closed = {"closedNs", "closedLocal", "resourceCount", "parentResourceClose"}
    for value, phase, seconds, extra in (
            (readmission, "save-readmission", 120, {"admissionReturn", "finalAdmissionReturn"}),
            (parent, "save-set-after", 120, {"softEndNs", "leafSha256", "leafCheckedNs", "leafCheckedLocal",
                "beforeParentSha256", "historicalBeforeCheckedNs", "historicalBeforeCheckedLocal", "historicalLocalScope"}),
            (returned["observationOwnerReturn"], "save-observation", 30, set()),
            (returned["returnWindow"], "save-owner-return", 45, set())):
        has_close = phase != "save-owner-return"
        require(type(value) is dict and set(value) == common | extra | (closed if has_close else set()) and
                value["phase"] == phase and value["localScope"] == "THIS_COMMAND_ONLY" and
                origin.encoded(value["clock"]) == origin.encoded(clock), "BOOTSTRAP_PROBE_AFTER_SAVE_WINDOW")
        began, hard = origin.integer(value["firstNs"]), origin.integer(value["hardEndNs"])
        local = staging._local(value["localStarted"])
        require(previous_ns <= began < hard == min(origin.integer(began + seconds * staging.NS),
                proposal["phaseFencesNs"][phase], proposal["proposedJobEndNs"]) and previous_local <= local,
                "BOOTSTRAP_PROBE_AFTER_SAVE_CHRONOLOGY")
        if has_close:
            require(began <= origin.integer(value["closedNs"]) < hard and local <= staging._local(value["closedLocal"]) and
                    type(value["resourceCount"]) is int and origin.integer(value["resourceCount"]) > 0 and
                    value["parentResourceClose"] == "KNOWN_RESOURCE_CLOSE_ONLY", "BOOTSTRAP_PROBE_AFTER_SAVE_CLOSE")
            previous_ns, previous_local = value["closedNs"], value["closedLocal"]
        else:
            # Real original after-save step success, not this file, attests its final writer return.
            require(began <= first.nanoseconds, "BOOTSTRAP_PROBE_AFTER_SAVE_BACKWARDS")
    require(readmission["firstNs"] == post_ns and readmission["localStarted"] == post_local,
            "BOOTSTRAP_PROBE_AFTER_SAVE_FIRST")
    prior = post_ns
    for name in ("admissionReturn", "finalAdmissionReturn"):
        value = readmission[name]
        require(type(value) is dict and set(value) == {"admissionSha256", "sessionSha256", "clock", "returnedNs"} and
                value["admissionSha256"] == origin.digest(admitted.record) and staging.cache._sha(value["sessionSha256"])
                and origin.encoded(value["clock"]) == origin.encoded(clock) and
                prior <= origin.integer(value["returnedNs"]) <= readmission["closedNs"],
                "BOOTSTRAP_PROBE_AFTER_SAVE_ADMISSION_RETURN")
        prior = value["returnedNs"]
    window, previous = after["window"], index["chain"]["returns"]["before"]
    require(type(window) is dict and set(window) == {"phase", "clock", "firstNs", "hardEndNs", "softEndNs",
            "lastNewWorkNs", "finishedNs", "predecessorSha256", "predecessorCheckedNs", "proposalSha256"} and
            window["phase"] == "save-set-after" and window["predecessorSha256"] == origin.digest(blobs["before-parent.json"])
            and window["predecessorCheckedNs"] == previous["checkedNs"] and
            window["proposalSha256"] == origin.digest(blobs["allocation-proposal.json"]),
            "BOOTSTRAP_PROBE_AFTER_LEAF_WINDOW")
    for name in ("clock", "firstNs", "hardEndNs", "softEndNs"):
        require(origin.encoded(window[name]) == origin.encoded(parent[name]), "BOOTSTRAP_PROBE_AFTER_LEAF_WINDOW")
    require(parent["softEndNs"] == min(parent["hardEndNs"], parent["firstNs"] + 90 * staging.NS) and
            previous["checkedNs"] <= window["firstNs"] <= origin.integer(window["lastNewWorkNs"]) <=
            origin.integer(window["finishedNs"]) <= origin.integer(parent["leafCheckedNs"]) <= parent["closedNs"] and
            window["lastNewWorkNs"] < parent["softEndNs"] and
            parent["leafSha256"] == origin.digest(retained["after-leaf.json"]) and
            parent["beforeParentSha256"] == origin.digest(blobs["before-parent.json"]) and
            parent["historicalBeforeCheckedNs"] == previous["checkedNs"] and
            staging._local(parent["historicalBeforeCheckedLocal"]) == staging._local(previous["checkedLocal"]) and
            parent["historicalLocalScope"] == "ORIGINAL_PRODUCER_PROCESS_ONLY_NOT_COMPARED_WITH_THIS_COMMAND" and
            parent["localStarted"] <= staging._local(parent["leafCheckedLocal"]) <= parent["closedLocal"],
            "BOOTSTRAP_PROBE_AFTER_LEAF_RETURN")
    return raw, {**retained, "save-observations.json": observations_raw, "after-save-return.json": raw}


def _probe_preparation_record(raw, expected_hash, claims, admitted, plan, proposal, first, directory):
    """Validate supplied original lookup issuance; never compute a fresh provider end."""
    require(type(raw) is bytes and 0 < len(raw) <= LIMIT and origin.digest(raw) == expected_hash,
            "BOOTSTRAP_PROBE_PREPARATION_HASH")
    value = origin.parse(raw)
    require(type(value) is dict and set(value) == {"schema", "scope", "source", "github", "selection", "cacheCohort",
            "directory", "directoryIdentity", "originalClaims", "admissionSha256", "admissionReturn",
            "finalAdmissionReturn", "proposalSha256", "plan", "planSha256", "clock", "firstNs", "hardEndNs",
            "providerWindow", "providerRequest", "writerReturn", "providerExecution", "budgetAcceptance",
            "testAcceptance", "exportSaveAuthority"} and type(value["schema"]) is int and value["schema"] == 1 and
            raw == origin.encoded(value) and value["scope"] == "BOOTSTRAP_PROBE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1"
            and value["writerReturn"] == "PENDING_NOT_OBSERVABLE_BY_THIS_FILE" and
            value["providerExecution"] == value["testAcceptance"] == "NOT_PERFORMED" and
            value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False,
            "BOOTSTRAP_PROBE_PREPARATION_RECORD")
    base_claims = {name: claims[name] for name in ("PRODUCER_OUTCOME", "HANDOFF_SHA256", "PRODUCER_RETURN_SHA256",
        "SAVE_PREPARE_OUTCOME", "SAVE_PREPARATION_SHA256", "SAVE_OUTCOME", "AFTER_SAVE_OUTCOME", "AFTER_SAVE_SHA256")}
    for name in ("source", "github", "selection", "cacheCohort"):
        require(origin.encoded(value[name]) == origin.encoded(origin.admitted_value(admitted)[name]),
                "BOOTSTRAP_PROBE_PREPARATION_IDENTITY")
    require(value["directory"] == str(directory.path) and
            directory_identity(value["directoryIdentity"], first.clock.role) == list(directory.identity) and
            origin.encoded(value["originalClaims"]) == origin.encoded(base_claims) and
            value["admissionSha256"] == origin.digest(admitted.record) and
            value["proposalSha256"] == origin.digest(origin.encoded(proposal)) and
            origin.encoded(value["plan"]) == origin.encoded(plan) and value["planSha256"] == origin.digest(origin.encoded(plan))
            and origin.encoded(value["clock"]) == origin.encoded(origin.clock_value(first.clock)),
            "BOOTSTRAP_PROBE_PREPARATION_BINDING")
    began, hard = origin.integer(value["firstNs"]), origin.integer(value["hardEndNs"])
    require(began < hard == min(origin.integer(began + 30 * staging.NS), proposal["phaseFencesNs"]["probe-transition"],
            proposal["proposedJobEndNs"]), "BOOTSTRAP_PROBE_PREPARATION_WINDOW")
    previous = began
    for name in ("admissionReturn", "finalAdmissionReturn"):
        returned = value[name]
        require(type(returned) is dict and set(returned) == {"admissionSha256", "sessionSha256", "clock", "returnedNs"} and
                returned["admissionSha256"] == value["admissionSha256"] and staging.cache._sha(returned["sessionSha256"])
                and origin.encoded(returned["clock"]) == origin.encoded(value["clock"]) and
                previous <= origin.integer(returned["returnedNs"]) < hard, "BOOTSTRAP_PROBE_PREPARATION_ADMISSION_RETURN")
        previous = returned["returnedNs"]
    window = value["providerWindow"]
    require(type(window) is dict and set(window) == {"issuedNs", "hardEndNs", "actualProviderStart"} and
            window["actualProviderStart"] == "NOT_OBSERVED", "BOOTSTRAP_PROBE_PROVIDER_WINDOW")
    issued, provider_end = origin.integer(window["issuedNs"]), origin.integer(window["hardEndNs"])
    require(previous <= issued < hard and issued < provider_end == min(origin.integer(issued + 180 * staging.NS),
            proposal["phaseFencesNs"]["provider-probe"], proposal["proposedJobEndNs"]) and
            issued <= first.nanoseconds < provider_end, "BOOTSTRAP_PROBE_PROVIDER_RETURN_BOUND")
    require(origin.encoded(value["providerRequest"]) == origin.encoded({"action": plan["provider"]["restore"],
            "path": plan["path"], "key": plan["key"], "lookupOnly": True, "restoreKeys": [], "failOnCacheMiss": True,
            "enableCrossOsArchive": False, "scope": "PRIVATE_DESCRIPTOR_NOT_EXECUTION"}), "BOOTSTRAP_PROBE_PROVIDER_REQUEST")
    return value


def _probe_command(cancelled, *, after):
    """Two fixed dormant commands. Neither executes nor enforces a provider lifecycle."""
    require(type(after) is bool, "BOOTSTRAP_PROBE_COMMAND")
    local_start = staging._local(time.monotonic())
    first = origin.clocks.validate_reading(origin.clocks.observe())
    last, local_last = first.nanoseconds, local_start
    proposal = owner = fence = result_raw = None
    failure = None
    base_names = ("PRODUCER_OUTCOME", "HANDOFF_SHA256", "PRODUCER_RETURN_SHA256", "SAVE_PREPARE_OUTCOME",
                  "SAVE_PREPARATION_SHA256", "SAVE_OUTCOME", "AFTER_SAVE_OUTCOME", "AFTER_SAVE_SHA256")
    names = base_names + (("PROBE_PREPARE_OUTCOME", "PROBE_PREPARATION_SHA256", "PROBE_OUTCOME") if after else ())
    claims = {name: os.environ.get("P2PKIT_BOOTSTRAP_" + name) for name in names}
    outputs = ({name: os.environ.get("P2PKIT_BOOTSTRAP_PROBE_" + suffix) for name, suffix in
               (("cache-primary-key", "PRIMARY_KEY"), ("cache-matched-key", "MATCHED_KEY"), ("cache-hit", "HIT"))}
               if after else {})

    def environment():
        require(origin.wire.TOKEN_ENV not in os.environ and
                all(os.environ.get("P2PKIT_BOOTSTRAP_" + name) == value for name, value in claims.items()),
                "BOOTSTRAP_PROBE_ENVIRONMENT_CHANGED")
        require(all(value == "success" for name, value in claims.items() if name.endswith("OUTCOME")),
                "BOOTSTRAP_PROBE_ORIGINAL_OUTCOMES")
        require(all(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value)
                    for name, value in claims.items() if name.endswith("SHA256")), "BOOTSTRAP_PROBE_ORIGINAL_HASHES")
        if after:
            require(all(type(outputs[name]) is str and len(outputs[name]) <= 512 and
                    all(32 <= ord(c) < 127 for c in outputs[name]) and
                    os.environ.get("P2PKIT_BOOTSTRAP_PROBE_" + suffix) == outputs[name]
                    for name, suffix in (("cache-primary-key", "PRIMARY_KEY"), ("cache-matched-key", "MATCHED_KEY"),
                                         ("cache-hit", "HIT"))), "BOOTSTRAP_PROBE_ORIGINAL_OUTPUTS")
        cancellation(cancelled)

    def phase_fence(name, began, local):
        seconds = {"probe-transition": 30, "custody-readmission": 120, "provider-observation": 30}[name]
        require(began.clock == first.clock and began.nanoseconds >= last and local >= local_last,
                "BOOTSTRAP_PROBE_PHASE_BACKWARDS")
        hard = origin.integer(began.nanoseconds + seconds * staging.NS)
        local_end = origin.wire._directed_deadline(local, seconds, hard, began.nanoseconds)

        class Fence:
            __slots__ = ()
            clock = first.clock
            hard_end = property(lambda self: hard)
            local_end = property(lambda self: local_end)

            def shorten(self, value):
                nonlocal hard, local_end
                hard = min(hard, origin.integer(value["phaseFencesNs"][name]), origin.integer(value["proposedJobEndNs"]))
                local_end = min(local_end, origin.wire._directed_deadline(local, seconds, hard, began.nanoseconds))
                self.now()

            def now(self, *, final=False, minimum=0, limit=None):
                nonlocal last, local_last, local_end
                if not final:
                    environment()
                before = staging._local(time.monotonic())
                require(before >= local_last, "BOOTSTRAP_PROBE_LOCAL_BACKWARDS")
                local_last = before
                observed = origin.clocks.validate_reading(origin.clocks.observe())
                require(observed.clock == first.clock and observed.nanoseconds >= max(last, origin.integer(minimum)),
                        "BOOTSTRAP_PROBE_RAW_BACKWARDS")
                last = observed.nanoseconds
                local = staging._local(time.monotonic())
                require(local >= local_last, "BOOTSTRAP_PROBE_LOCAL_BACKWARDS")
                local_last = local
                cap = hard if limit is None else min(hard, origin.integer(limit))
                local_end = min(local_end, origin.wire._directed_deadline(before, seconds, cap, last))
                require(last < cap and local_last < local_end, "BOOTSTRAP_PROBE_PHASE_EXPIRED")
                if not final:
                    environment()
                    return self.now(final=True, minimum=last, limit=cap)
                return last

            def deadline(self, maximum, *, final=False, limit=None):
                require(type(maximum) in (int, float) and math.isfinite(maximum) and maximum > 0,
                        "BOOTSTRAP_PROBE_MAXIMUM")
                self.now(final=final, limit=limit)
                return min(local_end, local_last + min(seconds, maximum))

            def record(self):
                return {"phase": name, "clock": origin.clock_value(first.clock), "firstNs": began.nanoseconds,
                        "hardEndNs": hard, "localStarted": local, "localScope": "THIS_COMMAND_ONLY"}

        result = Fence()
        if proposal is not None:
            result.shorten(proposal)
        return result

    def close_known():
        nonlocal owner
        active, ledger, errors = owner, owner.resources, owner.errors
        roster = tuple((row, row["label"], row["owner"]) for row in ledger)
        active.close()
        if active.original is not None:
            raise active.original
        require(type(active) is Owner and active.fence is fence and active.closed is True and not active.unknown and
                not errors and active.resources is ledger and active.errors is errors and len(ledger) == len(roster) and
                all(row is old and set(row) == {"label", "owner", "attempted", "closed"} and row["label"] == label and
                    row["owner"] is resource and row["attempted"] is row["closed"] is True
                    for row, (old, label, resource) in zip(ledger, roster)) and
                not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE,
                "BOOTSTRAP_PROBE_OWNER_CLOSE_INCOMPLETE")
        closed = fence.now(final=True)
        result = {**fence.record(), "closedNs": closed, "closedLocal": local_last, "resourceCount": len(roster),
                  "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY"}
        owner = None
        environment()
        fence.now(final=True)
        return result

    class BoundReader:
        __slots__ = ()

        def end(self, *, new=False):
            return owner.end()

        def check(self):
            owner.end()

        def acquire(self, label, factory):
            return owner.acquire(label, factory)

        def error(self, stage, error):
            owner.error(stage, error)

        def close_one(self, value):
            if owner.unknown:
                if owner.original is not None:
                    raise owner.original
                raise origin.OriginError("BOOTSTRAP_PROBE_READER_UNKNOWN")
            owner.close_one(value)
            if owner.original is not None:
                raise owner.original
            require(not owner.unknown, "BOOTSTRAP_PROBE_READER_UNKNOWN")

    try:
        environment()
        require(not QUARANTINE and not query.QUARANTINE and not diagnostics._QUARANTINE, "BOOTSTRAP_PROBE_PRIOR_UNKNOWN")
        fence = phase_fence("custody-readmission" if after else "probe-transition", first, local_start)
        selection, original_path, event = host_inputs(first.clock.role)
        child_environment(original_path)
        runner_name = os.environ.get("RUNNER_NAME")
        session = original_path.with_name(original_path.name + "-productive") / "initializer"
        path = original_path.with_name(original_path.name + ("-after-probe" if after else "-probe"))
        owner = Owner(fence.local_end, fence, first=first, cancelled=environment)
        initializer = owner.open(session)
        directory = owner.child(initializer, "dependency-save-handoff")
        after_directory = owner.open(original_path.with_name(original_path.name + "-after-save"))
        original_after = owner.read(after_directory, "after-save-return.json")
        require(origin.digest(original_after) == claims["AFTER_SAVE_SHA256"], "BOOTSTRAP_PROBE_AFTER_SAVE_HASH")
        probe_directory = probe_raw = None
        if after:
            probe_directory = owner.open(original_path.with_name(original_path.name + "-probe"))
            probe_raw = owner.read(probe_directory, "probe-preparation.json")
            require(origin.digest(probe_raw) == claims["PROBE_PREPARATION_SHA256"], "BOOTSTRAP_PROBE_PREPARATION_HASH")
            require(first.nanoseconds < origin.integer(origin.parse(probe_raw)["providerWindow"]["hardEndNs"]),
                    "BOOTSTRAP_PROBE_PROVIDER_RETURN_BOUND")
        handoff_raw = owner.read(directory, "save-handoff.json")
        require(origin.digest(handoff_raw) == claims["HANDOFF_SHA256"], "BOOTSTRAP_PROBE_HANDOFF_HASH")
        index = origin.parse(handoff_raw)
        proposal_raw = owner.read(directory, "allocation-proposal.json")
        row = index["blobs"]["allocation-proposal.json"]
        require(type(row["bytes"]) is int and row["bytes"] == len(proposal_raw) and
                row["sha256"] == origin.digest(proposal_raw), "BOOTSTRAP_PROBE_PROPOSAL_HASH")
        fence.shorten(origin.parse(proposal_raw))  # Original caps only deny early; no authority from serialized claims.
        producer_raw = owner.read(initializer, "producer-function-return.json")
        _producer_return_record(producer_raw, handoff_raw, claims["PRODUCER_RETURN_SHA256"], first, initializer, directory)
        target = owner.new(path)
        target_identity = directory_identity(list(target.identity), first.clock.role)
        admitted, admission_return = admit(owner, fence, path / "admission")
        require(admitted.original_event == event, "BOOTSTRAP_PROBE_EVENT_CHANGED")
        owner.write(target, "admission-return.json", owner.admissions[str(path / "admission")][2])
        actual_raw, blobs = _read_save_handoff(owner, initializer, directory, admitted,
            producer_outcome=claims["PRODUCER_OUTCOME"], expected_sha256=claims["HANDOFF_SHA256"])
        blobs = dict(blobs)
        require(actual_raw == handoff_raw and blobs["allocation-proposal.json"] == proposal_raw,
                "BOOTSTRAP_PROBE_PACKAGE_CHANGED")
        originals = []

        def reference(directory_, label, name, *, bound):
            value = index["references"][label]
            require(type(value) is dict and set(value) == {"directory", "directoryIdentity", "name", "maximumBytes",
                    "bytes", "sha256", "fileBinding", "bindingScope"} and value["directory"] == str(directory_.path) and
                    value["name"] == name and type(value["maximumBytes"]) is int and value["maximumBytes"] == LIMIT and
                    type(value["bytes"]) is int and 0 < value["bytes"] <= LIMIT and staging.cache._sha(value["sha256"]),
                    "BOOTSTRAP_PROBE_REFERENCE")
            _new_entry_owned(owner, directory_, directory_.path, value["directoryIdentity"])
            if bound:
                require(value["fileBinding"] is not None and value["bindingScope"] == "ORIGINAL_FILE_BINDING",
                        "BOOTSTRAP_PROBE_REFERENCE_BINDING")
                raw, _ = staging._read(BoundReader(), directory_, name, binding=value["fileBinding"], maximum=value["bytes"])
            else:
                require(value["fileBinding"] is None and value["bindingScope"] ==
                        "ORIGINAL_DIRECTORY_AND_BYTES_OR_HASH_ONLY_NOT_FILE_IDENTITY", "BOOTSTRAP_PROBE_REFERENCE_BINDING")
                raw = owner.read(directory_, name, value["bytes"])
            require(len(raw) == value["bytes"] and origin.digest(raw) == value["sha256"], "BOOTSTRAP_PROBE_REFERENCE_CHANGED")
            originals.append((directory_, name, value, raw, bound))
            return raw

        service = owner.open(original_path / "service")
        responses = {name: reference(service, "service/" + name, name + ".json", bound=False) for name in ("attempt", "jobs")}
        require(index["binding"]["runnerName"] == runner_name, "BOOTSTRAP_PROBE_RUNNER_CHANGED")
        proposal = allocation.validate_proposal(proposal_raw, admitted, responses,
            index["binding"]["invocation"], first.clock, runner_name)
        fence.shorten(proposal)
        source_inputs, compiled = staging.files.source_inputs(owner, ROOT, owner.end(), owner.end)
        profile, role = bootstrap.cache_cohort(admitted.record)
        container_path = staging.files.stage_path(session, profile, role, admitted_raw=admitted.record)
        container = owner.acquire("directory", lambda: staging.files.private_root(container_path))
        staging_raw = reference(container, "staging/staging", "staging.json", bound=True)
        end = owner.end()
        source = owner.acquire("probe-stage", lambda: container.open_directory("restore-home", deadline=end))
        stage = origin.parse(staging_raw)
        staging.files.validate_stage(stage, admitted.record, profile, role, container_path,
                                     container.verify(), source.verify(), source_inputs)
        plan = staging.cache.validate_plan(index["plan"], admitted.record, staging_raw, compiled, source_inputs,
                                          session=session, profile=profile, role=role, mode="bootstrap")
        _save_original_inventory(index, blobs, compiled, stage, index["references"]["staging/staging"]["fileBinding"], proposal)
        prepared_directory = owner.open(original_path.with_name(original_path.name + "-save"))
        after_raw, after_originals = _probe_after_save_records(owner, after_directory, claims["AFTER_SAVE_SHA256"],
            claims, admitted, index, blobs, producer_raw, proposal, first, prepared_directory)
        require(after_raw == original_after, "BOOTSTRAP_PROBE_AFTER_SAVE_CHANGED")
        prepared = (_probe_preparation_record(probe_raw, claims["PROBE_PREPARATION_SHA256"], claims, admitted,
                    plan, proposal, first, probe_directory) if after else None)
        if prepared is not None:
            require(origin.parse(after_raw)["returnWindow"]["firstNs"] <= prepared["firstNs"],
                    "BOOTSTRAP_PROBE_PREPARATION_PRECEDES_AFTER_SAVE")
        final_admitted, final_return = admit(owner, fence, path / "final-admission", expected=admitted)
        require(final_admitted == admitted and host_inputs(role) == (selection, original_path, event) and
                os.environ.get("RUNNER_NAME") == runner_name, "BOOTSTRAP_PROBE_FINAL_ADMISSION_CHANGED")
        environment()
        child_environment(original_path)
        owner.write(target, "final-admission-return.json", owner.admissions[str(path / "final-admission")][2])
        for directory_, name, raw in ((directory, "save-handoff.json", handoff_raw),
                (initializer, "producer-function-return.json", producer_raw),
                (prepared_directory, "save-preparation.json", after_originals["save-preparation.json"])):
            require(owner.read(directory_, name) == raw, "BOOTSTRAP_PROBE_FINAL_ORIGINALS_CHANGED")
        _new_entry_owned(owner, after_directory, after_directory.path, origin.parse(after_raw)["directoryIdentity"])
        for name, raw in after_originals.items():
            require(owner.read(after_directory, name) == raw, "BOOTSTRAP_PROBE_FINAL_AFTER_SAVE_CHANGED")
        for directory_, name, value, raw, bound in originals:
            _new_entry_owned(owner, directory_, directory_.path, value["directoryIdentity"])
            if bound:
                staging._read(BoundReader(), directory_, name, expected=raw, binding=value["fileBinding"], maximum=len(raw))
            else:
                require(owner.read(directory_, name) == raw, "BOOTSTRAP_PROBE_FINAL_REFERENCE_CHANGED")
        if not after:
            issued = fence.now()
            provider_end = min(origin.integer(issued + 180 * staging.NS), proposal["phaseFencesNs"]["provider-probe"],
                               proposal["proposedJobEndNs"])
            require(issued < provider_end, "BOOTSTRAP_PROBE_PROVIDER_WINDOW_EXHAUSTED")
            result_raw = owner.write(target, "probe-preparation.json", {
                "schema": 1, "scope": "BOOTSTRAP_PROBE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1",
                **{name: index[name] for name in ("source", "github", "selection", "cacheCohort")},
                "directory": str(path), "directoryIdentity": target_identity, "originalClaims": claims,
                "admissionSha256": origin.digest(admitted.record), "admissionReturn": admission_return,
                "finalAdmissionReturn": final_return, "proposalSha256": origin.digest(proposal_raw), "plan": plan,
                "planSha256": origin.digest(origin.encoded(plan)), "clock": origin.clock_value(first.clock),
                "firstNs": first.nanoseconds, "hardEndNs": fence.hard_end,
                "providerWindow": {"issuedNs": issued, "hardEndNs": provider_end, "actualProviderStart": "NOT_OBSERVED"},
                "providerRequest": {"action": plan["provider"]["restore"], "path": plan["path"], "key": plan["key"],
                    "lookupOnly": True, "restoreKeys": [], "failOnCacheMiss": True, "enableCrossOsArchive": False,
                    "scope": "PRIVATE_DESCRIPTOR_NOT_EXECUTION"},
                "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "providerExecution": "NOT_PERFORMED",
                "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
            close_known()
        else:
            _new_entry_owned(owner, probe_directory, probe_directory.path, prepared["directoryIdentity"])
            require(owner.read(probe_directory, "probe-preparation.json") == probe_raw, "BOOTSTRAP_PROBE_FINAL_PREPARATION_CHANGED")
            readmission_close = close_known()
            local = staging._local(time.monotonic())
            began = origin.clocks.validate_reading(origin.clocks.observe())
            fence = phase_fence("provider-observation", began, local)
            owner = Owner(fence.local_end, fence, first=began, cancelled=environment)
            # Classification, retention, this writer's close and guarded output all spend observation30.
            provider = staging.cache.provider_observation(plan, "lookup", original_outcome=claims["PROBE_OUTCOME"], outputs=outputs)
            owner.end()
            target = owner.open(path)
            _new_entry_owned(owner, target, path, target_identity)
            provider_raw = owner.write(target, "provider-probe.json", provider)
            require(provider["status"] == "REPORTED_EXACT_HIT", "BOOTSTRAP_PROBE_NO_QUALIFIED_EXACT_HIT")
            originals_raw = owner.write(target, "probe-preparation.json", probe_raw)
            close_raw = owner.write(target, "readmission-close.json", {**readmission_close,
                "admissionReturn": admission_return, "finalAdmissionReturn": final_return})
            result_raw = owner.write(target, "probe-result.json", {
                "schema": 1, "scope": "BOOTSTRAP_PROBE_PENDING_ORIGINAL_STEP_RETURN_V1",
                **{name: index[name] for name in ("source", "github", "selection", "cacheCohort")},
                "directory": str(path), "directoryIdentity": target_identity, "originalClaims": claims,
                "planSha256": origin.digest(origin.encoded(plan)), "proposalSha256": origin.digest(proposal_raw),
                "clock": origin.clock_value(first.clock), "firstPostProviderNs": first.nanoseconds,
                "firstPostProviderLocal": local_start, "providerEndNs": prepared["providerWindow"]["hardEndNs"],
                "providerTimeScope": "POST_ACTION_UPPER_BOUND_ONLY_REQUIRES_TRUSTED_SEQUENTIAL_ORIGINAL_OUTCOME",
                "observationWindow": fence.record(), "files": {"provider-probe.json": origin.digest(provider_raw),
                    "probe-preparation.json": origin.digest(originals_raw), "readmission-close.json": origin.digest(close_raw)},
                "status": "REPORTED_EXACT_HIT_PRESENCE_ONLY", "cacheContents": "NOT_PROVEN", "resolverReuse": "NOT_PROVEN",
                "providerDeadlineEnforcement": "NOT_ESTABLISHED", "providerRetirement": "NOT_OBSERVED",
                "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "budgetAcceptance": "NOT_ADMITTED",
                "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
            close_known()  # There is deliberately no new probe-owner-return45 allocation.
    except BaseException as error:
        failure = owner.original if owner is not None and owner.original is not None else error
        if owner is not None:
            try:
                owner.error("after-probe" if after else "prepare-probe", error)
            except BaseException:
                owner.unknown = True
    finally:
        if owner is not None:
            try:
                owner.close()
                if failure is None and owner.original is not None:
                    failure = owner.original
            except BaseException as error:
                if failure is None:
                    failure = owner.original if owner.original is not None else error
            if owner.unknown and not any(value is owner for value in QUARANTINE):
                QUARANTINE.append(owner)
    if failure is not None:
        raise failure
    require(result_raw is not None and owner is None, "BOOTSTRAP_PROBE_NOT_RETURNED")
    fence.now(final=True)
    environment()
    scope = "BOOTSTRAP_PROBE_PENDING_ORIGINAL_STEP_RETURN_V1" if after else "BOOTSTRAP_PROBE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1"
    return public_result(scope, "probeSha256" if after else "probePreparationSha256", result_raw), fence, fence.hard_end


def prepare_probe(cancelled):
    return _probe_command(cancelled, after=False)


def after_probe_originals(cancelled):
    return _probe_command(cancelled, after=True)


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
    commands.add_parser("produce-originals")
    commands.add_parser("prepare-save")
    commands.add_parser("after-save")
    commands.add_parser("prepare-probe")
    commands.add_parser("after-probe")
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
        elif args.operation == "produce-originals":
            guarded(produce_originals)
        elif args.operation == "prepare-save":
            guarded(prepare_save)
        elif args.operation == "after-save":
            guarded(after_save_originals)
        elif args.operation == "prepare-probe":
            guarded(prepare_probe)
        elif args.operation == "after-probe":
            guarded(after_probe_originals)
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
