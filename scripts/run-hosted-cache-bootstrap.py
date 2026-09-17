#!/usr/bin/env python3
"""Dormant, evidence-only bootstrap original acquisition; NOT a cache builder.

No workflow, productive budget, canonical init/producer, seed/export/save,
policy installer, uploader or standalone execution-adoption entry exists here.
The only public operation is prepare-originals. A future workflow must bind its
actual original step outcome, not this process's provisional receipt/digest.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
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
import hosted_cache_bootstrap_identity as bootstrap
import hosted_cache_bootstrap_origin as origin
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
RESULT_SCOPE = "BOOTSTRAP_ORIGINALS_PENDING_CALLER_RETURN_V1"
CONTEXT_FIELDS = {"schema", "scope", "prelude", "selection", "cacheCohort", "source", "github", "root", "session",
                  "job", "inheritedContext", "runnerName", "admissionSha256", "admissionReturnSha256",
                  "admissionReturnedNs", "budgetAcceptance", "exportSaveAuthority"}
START_FIELDS = {"schema", "scope", "contextSha256", "argv", "cwd", "role", "job", "invocation", "state", "home",
                "inheritedContext", "startedNs", "workEndNs", "finalEndNs", "exitCode", "launchAttempted",
                "scopeAttempted", "retirement"}
PHASE_FILES = {"start.json", "baseline.json", "result.json", "native-start.json", "stdout.log", "stderr.log"}
TERMINAL_FIELDS = START_FIELDS | {"captureOutcomes", "baselineSha256", "launchMinimumNs", "launchArgv", "leader",
    "nativeStartSha256", "completedNs", "survivors", "ownership", "scopeCloseAttempted", "scopeClosed",
    "finalizedNs", "captures", "errors"}
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
        self.phase_originals, self.admissions = None, {}

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
    origin.integer(value["admissionReturnedNs"], fence.first)
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
    began = origin.integer(start["startedNs"], context["admissionReturnedNs"])
    require(began < fence.work and type(start["workEndNs"]) is int and type(start["finalEndNs"]) is int and
            start["workEndNs"] == min(fence.work, began + 45 * origin.NS) and
            start["finalEndNs"] == min(fence.final, start["workEndNs"] + 45 * origin.NS),
            "BOOTSTRAP_ORIGINAL_PHASE_FENCES")
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


def admission_originals(owner, private, admitted, fence, *, final=False):
    name = "final-admission" if final else "admission"
    registered = owner.admissions.get(str(private.path / name))
    require(registered is not None and registered[0] is admitted, "BOOTSTRAP_ADMISSION_NOT_CURRENT_RETURN")
    directory = owner.child(private, name, final=True)
    require(load_admission(owner, directory, final=True) == admitted, "BOOTSTRAP_ORIGINAL_ADMISSION_CHANGED")
    session = owner.read(directory, "session-result.json", final=True)
    returned = owner.read(private, name + "-return.json", final=True)
    require(session == registered[1] and returned == registered[2], "BOOTSTRAP_ORIGINAL_ADMISSION_RETURN_CHANGED")
    value = origin.parse(returned)
    require(set(value) == {"admissionSha256", "sessionSha256", "clock", "returnedNs"} and
            value["admissionSha256"] == origin.digest(admitted.record) and
            value["sessionSha256"] == origin.digest(session) and value["clock"] == origin.clock_value(fence.clock) and
            fence.first <= origin.integer(value["returnedNs"]) < fence.work, "BOOTSTRAP_ORIGINAL_ADMISSION_RETURN")
    status = origin.parse(session)
    require(set(status) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"} and
            type(status["schema"]) is int and status["schema"] == 1 and status["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
            status["result"] == "READY_FOR_CALLER_SEAL" and status["retirement"] == "KNOWN" and
            status["firstError"] is None and status["errors"] == [] and type(status["queries"]) is list and
            type(status["readbacks"]) is list and type(status["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", status["job"]),
            "BOOTSTRAP_ORIGINAL_QUERY_SESSION")
    # This label is deliberately insufficient on its own. The registry is only
    # populated after the original supplier's actual _finalize returned.
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
            "leader": row["leader"], "observedNs": fence.now(limit=work_end)})
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
    flag or digest. No separate adoption CLI, refreshed query/API or new fence.
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
    start = start_record(records["start.json"], context_raw, context, private.path, fence)
    row, birth = (origin.parse(records[name]) for name in ("result.json", "native-start.json"))
    baseline_record(records["baseline.json"], fence.clock.role)
    require(set(row) == TERMINAL_FIELDS and set(birth) == {"ownership", "leader", "observedNs"},
            "BOOTSTRAP_ORIGINAL_TERMINAL_FIELDS")
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
    child_raw = owner.read(directory, "child-result.json", final=True)
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
    responses = {name: owner.read(directory, name + ".json", final=True) for name in ("attempt", "jobs")}
    service = origin.service_identity(admitted, responses, start["invocation"], fence.clock, context["runnerName"])
    require(child["originalsSha256"] == service["originalsSha256"], "BOOTSTRAP_ORIGINAL_RESPONSES_CHANGED")
    times = [fence.first, context["admissionReturnedNs"], start["startedNs"], row["launchMinimumNs"],
             child["beganNs"], child["metadataLastNs"], service["firstNs"],
             service["lastNs"], child["acquiredNs"], child["completedNs"], ack["closedNs"], row["completedNs"], row["finalizedNs"]]
    require(all(type(value) is int and 0 <= value <= origin.clocks.UINT64 for value in times) and times == sorted(times) and
            start["workEndNs"] == min(fence.work, start["startedNs"] + 45 * origin.NS) and
            start["finalEndNs"] == min(fence.final, start["workEndNs"] + 45 * origin.NS) and
            row["completedNs"] < start["workEndNs"] and row["finalizedNs"] < start["finalEndNs"] and
            row["launchMinimumNs"] <= origin.integer(birth["observedNs"]) <= row["completedNs"],
            "BOOTSTRAP_ORIGINAL_CLOCK_CHAIN")
    last = fence.now(final=True, minimum=max(*times, birth["observedNs"]))
    return {"service": service, "childTerminalSha256": origin.digest(child_raw),
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
        result_raw = owner.write(private, "origin-result.json", {"schema": 1, "scope": RESULT_SCOPE,
            "contextSha256": origin.digest(context_raw), "originalChain": checked,
            "finalAdmission": final_admission, "finalAdmissionOriginals": final_hashes, "retainedNs": fence.now(final=True),
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
    fence.now(final=True)
    cancellation(cancelled)
    return {"scope": RESULT_SCOPE, "provisionalSha256": origin.digest(result_raw), "budgetAcceptance": "NOT_ADMITTED",
            "exportSaveAuthority": False}, fence, fence.final


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
    child = commands.add_parser("_service")
    child.add_argument("--context-sha256", required=True)
    child.add_argument("--minimum-ns", required=True)
    args = parser.parse_args()
    try:
        require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
                "BOOTSTRAP_ISOLATED_INTERPRETER_REQUIRED")
        if args.operation == "prepare-originals":
            guarded(prepare_originals)
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
