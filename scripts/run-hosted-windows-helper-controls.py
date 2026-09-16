#!/usr/bin/env python3
"""Closed manual Windows helper qualification; no product build or publisher.

Only actual Windows/NTFS, installed Python/Git/GPG and an explicit PUBLIC key
are admitted. Commands are a fixed source inventory and tiny helper fixtures.
Every child uses the maintained WindowsScope and private NativeFile sinks.
The separate validate-public step runs AFTER this interpreter has returned;
only its exact ciphertext+manifest seal grants upload authority. A safe export
of failed tests may return zero here, but the workflow's final controls_passed
guard MUST fail the job. Neither ciphertext retention nor exit zero is test
acceptance; authenticated private fixture decryption is additionally pending.

There is no ordinary-recipient bootstrap, arbitrary command input, installer,
Gradle invocation, source clone, cache, raw-log upload, or cleanup/reset of an
UNKNOWN domain. In-process quarantine never grants cross-invocation recovery.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
from enum import Enum
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import sys
import time
import uuid

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import audit_processes as processes
import hosted_windows_evidence as encrypted
import hosted_windows_files as files


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / relative)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


# Read-only source/receipt parsers, not the historical witness run/SDK/Gradle path.
witness = module("windows_helper_witness_parsers", "run-windows-directory-control.py")
OPERATION = "windows-helper-controls"
REPOSITORY = "p2pKit/P2pKit"
WORKFLOW = ".github/workflows/desktop-cross-host.yml"
MAX_RECORD = 8 * 1024 * 1024
MAX_OUTPUT = 16 * 1024 * 1024
MAX_COMMAND_SECONDS = 300
NATIVE_CASES = ("native-sinks", "native-output-bound", "native-launch-close", "native-tee",
                "native-controller-command", "native-controller-retirement", "native-export",
                "native-export-wrong-recipient", "native-export-input-quarantine")
_HELD = []  # Deliberate strong references after UNKNOWN; never a recovery API.


class Stage(str, Enum):
    UNOBSERVED = "UNOBSERVED"
    IDENTITY = "IDENTITY"
    PATHS = "PATHS"
    BASE_ROOT = "BASE_ROOT"
    STATE_ROOT = "STATE_ROOT"
    EVIDENCE_ROOT = "EVIDENCE_ROOT"
    WORK_ROOT = "WORK_ROOT"
    OUTPUT_ROOT = "OUTPUT_ROOT"
    START_RECORD = "START_RECORD"
    COMMAND_SETUP = "COMMAND_SETUP"
    SIGNAL_SETUP = "SIGNAL_SETUP"
    PYTHON_TOOL = "PYTHON_TOOL"
    GIT_TOOL = "GIT_TOOL"
    GPG_TOOL = "GPG_TOOL"
    SOURCE_TOPLEVEL = "SOURCE_TOPLEVEL"
    SOURCE_HEAD = "SOURCE_HEAD"
    SOURCE_TREE = "SOURCE_TREE"
    SOURCE_SHALLOW = "SOURCE_SHALLOW"
    SOURCE_STATUS = "SOURCE_STATUS"
    SOURCE_ORIGIN = "SOURCE_ORIGIN"
    SOURCE_ENTRIES = "SOURCE_ENTRIES"
    SOURCE_BYTES = "SOURCE_BYTES"
    SOURCE_BINDING = "SOURCE_BINDING"
    RECIPIENT = "RECIPIENT"
    CONTROLS = "CONTROLS"
    COMMAND_FINALIZATION = "COMMAND_FINALIZATION"
    SIGNAL_RESTORE = "SIGNAL_RESTORE"
    EXPORT = "EXPORT"
    ROOT_FINALIZATION = "ROOT_FINALIZATION"
    POST_RETURN_SEAL = "POST_RETURN_SEAL"


class FailureReason(str, Enum):
    HELPER_GUARD = "HELPER_GUARD_REFUSED"
    FILESYSTEM = "NATIVE_FILESYSTEM_REFUSED"
    PROCESS = "NATIVE_PROCESS_REFUSED"
    EVIDENCE = "EVIDENCE_REFUSED"
    OTHER = "UNCLASSIFIED_FAILURE"


class NativeOperation(str, Enum):
    UNOBSERVED = "UNOBSERVED"
    FILE_CREATE = "FILE_CREATE"
    FILE_INFORMATION = "FILE_INFORMATION"
    FILE_SECURITY = "FILE_SECURITY"
    FILE_READ = "FILE_READ"
    FILE_WRITE = "FILE_WRITE"
    FILE_FLUSH = "FILE_FLUSH"
    HANDLE_INFORMATION = "HANDLE_INFORMATION"
    HANDLE_DUPLICATE = "HANDLE_DUPLICATE"
    HANDLE_CLOSE = "HANDLE_CLOSE"
    JOB_CREATE = "JOB_CREATE"
    JOB_CONFIGURE = "JOB_CONFIGURE"
    JOB_QUERY = "JOB_QUERY"
    JOB_ASSIGN = "JOB_ASSIGN"
    JOB_TERMINATE = "JOB_TERMINATE"
    PROCESS_CREATE = "PROCESS_CREATE"
    PROCESS_IDENTITY = "PROCESS_IDENTITY"
    PROCESS_EXIT = "PROCESS_EXIT"
    STARTUP_ATTRIBUTES = "STARTUP_ATTRIBUTES"


class NativeStatus(str, Enum):
    UNOBSERVED = "UNOBSERVED"
    ACCESS_DENIED = "ACCESS_DENIED"
    SHARING_VIOLATION = "SHARING_VIOLATION"
    PATH_ABSENT = "PATH_ABSENT"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    UNSUPPORTED = "UNSUPPORTED"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    OTHER = "OTHER_NATIVE_ERROR"


class GpgCommand(str, Enum):
    UNOBSERVED = "UNOBSERVED"
    VERSION = "VERSION"
    SHOW_ONLY = "SHOW_ONLY"
    LIST_KEYS = "LIST_KEYS"
    OTHER = "UNRECOGNIZED_COMMAND"


class GpgExit(str, Enum):
    UNOBSERVED = "UNOBSERVED"
    NO_EXIT_CODE = "NO_EXIT_CODE"
    ZERO = "ZERO"
    NONZERO = "NONZERO"


class RetirementObservation(str, Enum):
    NO_UNKNOWN_REPORTED = "NO_UNKNOWN_REPORTED"
    UNKNOWN = "UNKNOWN"


_NATIVE_OPERATIONS = {
    "NtCreateFile": NativeOperation.FILE_CREATE,
    "GetFileInformationByHandleEx": NativeOperation.FILE_INFORMATION,
    "GetSecurityInfo": NativeOperation.FILE_SECURITY,
    "ReadFile": NativeOperation.FILE_READ, "WriteFile": NativeOperation.FILE_WRITE,
    "FlushFileBuffers": NativeOperation.FILE_FLUSH,
    "GetHandleInformation": NativeOperation.HANDLE_INFORMATION,
    "DuplicateHandle owned output": NativeOperation.HANDLE_DUPLICATE,
    "CloseHandle": NativeOperation.HANDLE_CLOSE,
    "CreateJobObjectW": NativeOperation.JOB_CREATE,
    "SetInformationJobObject": NativeOperation.JOB_CONFIGURE,
    "QueryInformationJobObject": NativeOperation.JOB_QUERY,
    "IsProcessInJob": NativeOperation.JOB_ASSIGN, "pre-resume IsProcessInJob": NativeOperation.JOB_ASSIGN,
    "TerminateJobObject": NativeOperation.JOB_TERMINATE,
    "TerminateJobObject failed launch": NativeOperation.JOB_TERMINATE,
    "CreateProcessW (atomic job assignment)": NativeOperation.PROCESS_CREATE,
    "GetProcessTimes": NativeOperation.PROCESS_IDENTITY,
    "GetExitCodeProcess": NativeOperation.PROCESS_EXIT,
    "Initialize attributes": NativeOperation.STARTUP_ATTRIBUTES,
    "HANDLE_LIST": NativeOperation.STARTUP_ATTRIBUTES, "JOB_LIST": NativeOperation.STARTUP_ATTRIBUTES,
}
_NATIVE_STATUSES = {2: NativeStatus.PATH_ABSENT, 3: NativeStatus.PATH_ABSENT,
                    5: NativeStatus.ACCESS_DENIED, 32: NativeStatus.SHARING_VIOLATION,
                    33: NativeStatus.SHARING_VIOLATION, 80: NativeStatus.ALREADY_EXISTS,
                    183: NativeStatus.ALREADY_EXISTS, 1: NativeStatus.UNSUPPORTED,
                    50: NativeStatus.UNSUPPORTED, 87: NativeStatus.INVALID_PARAMETER}
_PUBLIC_FIELDS = {"stage": Stage, "reason": FailureReason, "nativeOperation": NativeOperation,
                  "nativeStatus": NativeStatus, "lastGpgCommand": GpgCommand, "lastGpgExit": GpgExit,
                  "retirementObservation": RetirementObservation}


class Progress:
    """Source-owned call-site observations, never host/retirement acceptance."""
    def __init__(self):
        self.stage = Stage.UNOBSERVED

    def mark(self, stage):
        if not isinstance(stage, Stage):
            raise ValueError("Expected a fixed helper observation stage")
        self.stage = stage


def public_observation(stage, detail):
    """Finite projection of already-bounded PRIVATE details; never echo their text.

    Native API/status matches are diagnostic classifications, not an OS cause or
    retirement proof. A last GPG command record does not prove a child started,
    or that the following command was reached. No exception accessor runs here.
    """
    def rows(value, maximum):
        return value[:maximum] if type(value) is list else ()
    detail = detail if type(detail) is dict else {}
    records = [row for row in rows(detail.get("windowsEvidence"), 8) if type(row) is dict]
    details = [detail]
    for record in records:
        details.extend(row["detail"] for row in rows(record.get("failures"), 64)
                       if type(row) is dict and type(row.get("detail")) is dict)
    nodes = []
    for item in details[:65]:
        nodes.extend(row for row in rows(item.get("nodes"), 64 - len(nodes)) if type(row) is dict)
        if len(nodes) >= 64:
            break
    kinds = {row["type"] for row in nodes if type(row.get("type")) is str}
    reason = next((value for name, value in (("FilesystemError", FailureReason.FILESYSTEM),
                  ("OwnershipError", FailureReason.PROCESS), ("HelperError", FailureReason.HELPER_GUARD),
                  ("WindowsEvidenceError", FailureReason.EVIDENCE), ("EvidenceError", FailureReason.EVIDENCE))
                   if name in kinds), FailureReason.OTHER)
    operation, status = NativeOperation.UNOBSERVED, NativeStatus.UNOBSERVED
    for node in nodes:
        message = node.get("message")
        if node.get("type") not in ("FilesystemError", "OwnershipError") or \
                type(message) is not str or len(message) > 2048:
            continue
        matched = re.fullmatch(
            r"Windows (.{1,80}) failed(?: \(error ([0-9]{1,10})\)|: error ([0-9]{1,10}))", message)
        if matched and matched[1] in _NATIVE_OPERATIONS:
            operation = _NATIVE_OPERATIONS[matched[1]]
            status = _NATIVE_STATUSES.get(int(matched[2] or matched[3]), NativeStatus.OTHER)
            break
    gpg, exited = GpgCommand.UNOBSERVED, GpgExit.UNOBSERVED
    if stage is Stage.RECIPIENT:
        for record in records:
            commands = record.get("commands")
            if record.get("operation") != "recipient-validation" or \
                    type(commands) is not list or not 0 < len(commands) <= 8:
                continue
            last = commands[-1]
            if type(last) is not dict or type(last.get("argv")) is not list:
                continue
            argv = last["argv"]
            if len(argv) > 128 or not all(type(value) is str and len(value) <= 65536 for value in argv):
                continue
            common = ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint"]
            gpg = (GpgCommand.VERSION if argv[-1:] == ["--version"] else
                   GpgCommand.LIST_KEYS if argv[-4:] == common + ["--list-keys"] else
                   GpgCommand.SHOW_ONLY if argv[-7:-1] == common + ["--import-options", "show-only", "--import"] else
                   GpgCommand.OTHER)
            code = last.get("waitExitCode")
            exited = (GpgExit.ZERO if type(code) is int and code == 0 else
                      GpgExit.NONZERO if type(code) is int and 0 < code <= 0xffffffff else GpgExit.NO_EXIT_CODE)
            break
    values = {"stage": stage if isinstance(stage, Stage) else Stage.UNOBSERVED, "reason": reason,
              "nativeOperation": operation, "nativeStatus": status, "lastGpgCommand": gpg, "lastGpgExit": exited,
              "retirementObservation": (RetirementObservation.NO_UNKNOWN_REPORTED
                  if detail.get("retirementUnknown") is False else RetirementObservation.UNKNOWN)}
    return {name: value.value for name, value in values.items()}


def print_public_failure(value):
    # Defense in depth: even a future bad caller cannot turn code-shaped private
    # text into a public code. Only exact enum members cross this boundary.
    checked = {}
    for name, domain in _PUBLIC_FIELDS.items():
        try:
            checked[name] = (domain(value[name]).value
                             if type(value) is dict and type(value.get(name)) is str else None)
        except (ValueError, TypeError):
            checked[name] = None
    if any(item is None for item in checked.values()):
        checked = public_observation(Stage.UNOBSERVED, {})
    print("WINDOWS_HELPER_NOT_ACCEPTED=" + checked.pop("reason") + "; " +
          "; ".join(name + "=" + text for name, text in checked.items()), file=sys.stderr)


class HelperError(RuntimeError):
    def __init__(self, code):
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code):
            code = "INTERNAL_INVALID_REASON"
        super().__init__(code)
        self.code = code


def require(value, code):
    if not value:
        raise HelperError(code)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_PRIVATE_JSON_KEY")
            result[key] = value
        return result
    require(type(raw) is bytes and len(raw) <= MAX_RECORD, "PRIVATE_JSON_BOUND")
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(HelperError("NONFINITE_PRIVATE_JSON")))
    require(type(value) is dict, "PRIVATE_JSON_OBJECT_REQUIRED")
    return value


def encoded(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    require(len(raw) <= MAX_RECORD, "PRIVATE_RECORD_BOUND")
    return raw


def private_write(root, name, raw):
    """Exclusive native write; an ambiguous close propagates, never retried."""
    require(type(raw) is bytes and len(raw) <= MAX_RECORD, "PRIVATE_WRITE_BOUND")
    with root.create_file(name, max_bytes=len(raw), deadline=time.monotonic() + 30) as stream:
        stream.write(raw)
        stream.sync()
        require(stream.verify().size == len(raw), "PRIVATE_WRITE_SIZE")


def private_json(root, name, value):
    private_write(root, name, encoded(value))


def private_read(root, name, maximum=MAX_RECORD):
    return root.read_bytes(name, max_bytes=maximum, deadline=time.monotonic() + 30)


def error_detail(error):
    """Bounded/accessor-safe supplier attachments, including nested failures."""
    detail = encrypted._exception_detail(error)
    pending, seen, attachments, total = [error], set(), set(), 0
    def unknown():
        detail["retirementUnknown"] = detail["incomplete"] = True
    def attribute(value, name, default=None):
        try:
            return getattr(value, name, default)
        except BaseException:
            unknown()
            return default
    while pending:
        current = pending.pop(0)
        if current is None or id(current) in seen:
            continue
        if not isinstance(current, BaseException) or len(seen) >= 64:
            unknown()
            break
        seen.add(id(current))
        for name in ("private_record", "_p2pkit_windows_evidence"):
            raw = attribute(current, name)
            if raw is None:
                continue
            try:
                require(type(raw) is bytes and len(raw) <= encrypted.MAX_RECORD_BYTES,
                        "ATTACHED_PRIVATE_RECORD_BOUND")
                sha = digest(raw)
                if sha in attachments:
                    continue
                total += len(raw)
                require(len(attachments) < 8 and total <= 2 * encrypted.MAX_RECORD_BYTES,
                        "ATTACHED_PRIVATE_GRAPH_BOUND")
                value = decode(raw)
                attachments.add(sha)
                detail.setdefault("windowsEvidence", []).append(value)
                detail["retirementUnknown"] |= value.get("retirement") != "KNOWN"
            except BaseException:
                unknown()
        flag = attribute(current, "retirement_unknown", False)
        if type(flag) is not bool:
            unknown()
        detail["retirementUnknown"] |= flag is not False
        pending.extend((attribute(current, "__cause__"), attribute(current, "__context__")))
        grouped = attribute(current, "exceptions", ())
        if type(grouped) not in (tuple, list):
            unknown()
        else:
            if len(grouped) > 64:
                unknown()
            pending.extend(grouped[:64])
        if len(pending) > 128:
            unknown()
            pending = pending[:128]
    return detail


def public_file(path, maximum):
    # Only checked-in source, installed executables and the actual runner event/
    # output file use Path I/O. Private evidence ALWAYS uses native private pins.
    path = Path(path)
    files.absolute_parts(str(path))
    for item in (path, *path.parents):
        row = item.lstat()
        require(not stat.S_ISLNK(row.st_mode) and not getattr(row, "st_file_attributes", 0) & files.REPARSE_POINT,
                "PUBLIC_INPUT_REPARSE")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= maximum,
            "PUBLIC_INPUT_KIND_OR_BOUND")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require(os.path.samestat(before, opened), "PUBLIC_INPUT_REPLACED")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    now = path.lstat()
    require(os.path.samestat(before, after) and os.path.samestat(before, now) and
            len(raw) == before.st_size == after.st_size == now.st_size and
            before.st_mtime_ns == after.st_mtime_ns == now.st_mtime_ns, "PUBLIC_INPUT_CHANGED")
    return raw


def identity(environment, event, root):
    """Pure closed manual identity. The caller supplies the REAL environment/event."""
    e = environment
    sha, tree = e.get("P2PKIT_EXPECTED_SHA", ""), e.get("P2PKIT_EXPECTED_TREE", "")
    require(re.fullmatch(r"[0-9a-f]{40}", sha) and re.fullmatch(r"[0-9a-f]{40}", tree), "FULL_SOURCE_REQUIRED")
    require(e.get("GITHUB_ACTIONS") == "true" and e.get("GITHUB_REPOSITORY") == REPOSITORY and
            e.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and e.get("GITHUB_JOB") == OPERATION and
            e.get("GITHUB_WORKFLOW") == "Desktop cross-host" and e.get("GITHUB_SHA") == sha and
            e.get("GITHUB_SERVER_URL") == "https://github.com" and e.get("GITHUB_API_URL") == "https://api.github.com" and
            e.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            e.get("GITHUB_WORKFLOW_SHA") == sha and e.get("P2PKIT_OPERATION") == OPERATION and
            e.get("RUNNER_OS") == "Windows" and e.get("RUNNER_ARCH") == "X64", "GENUINE_MANUAL_IDENTITY_REQUIRED")
    ref = e.get("GITHUB_REF", "")
    require(re.fullmatch(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]{0,200}", ref) and
            not any(value in ref for value in ("..", "//", "@{")) and not ref.endswith(("/", ".", ".lock")) and
            ref != "refs/heads/audit/complete-2026-09-04" and
            e.get("GITHUB_REF_TYPE") == "branch" and e.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + WORKFLOW + "@" + ref,
            "EXACT_WORKFLOW_REF_REQUIRED")
    run, attempt = e.get("GITHUB_RUN_ID", ""), e.get("GITHUB_RUN_ATTEMPT", "")
    require(all(re.fullmatch(r"[1-9][0-9]{0,19}", value) for value in (run, attempt)), "BOUND_RUN_REQUIRED")
    require(e.get("P2PKIT_REVIEWED_BASE", "") == "", "HELPER_HAS_NO_WRITER_BASE")
    public = e.get("P2PKIT_EVIDENCE_PUBLIC_KEY", "").encode("ascii")
    fingerprint = e.get("P2PKIT_EVIDENCE_FINGERPRINT", "")
    require(0 < len(public) <= encrypted.portable.MAX_KEY_BYTES and
            re.fullmatch(r"[0-9a-fA-F]{40}", fingerprint), "EXPLICIT_PUBLIC_RECIPIENT_REQUIRED")
    encrypted.portable._public_armor(public)  # Refuses secret packets, not merely an armor label.
    expected_inputs = {"operation": OPERATION, "expected_sha": sha, "expected_tree": tree,
                       "evidence_public_key": public.decode("ascii"), "evidence_fingerprint": fingerprint}
    require(type(event) is dict and type(event.get("repository")) is dict and
            event["repository"].get("full_name") == REPOSITORY, "EVENT_REPOSITORY_DIFFERS")
    require(event.get("ref") in (ref, ref[len("refs/heads/"):]), "EVENT_REF_DIFFERS")
    provided = event.get("inputs")
    # This helper has no writer authority. As in the existing witness/capacity
    # operations, the optional writer-only default can be omitted or exactly
    # empty. Never normalize other inputs, nulls, whitespace or recipient bytes.
    require(type(provided) is dict and set(provided) in
            (set(expected_inputs), set(expected_inputs) | {"reviewed_base"}), "EVENT_INPUT_KEYS_DIFFER")
    require("reviewed_base" not in provided or
            (type(provided["reviewed_base"]) is str and provided["reviewed_base"] == ""),
            "EVENT_WRITER_BASE_NOT_EMPTY")
    require(all(type(provided[key]) is str and provided[key] == value for key, value in expected_inputs.items()),
            "EVENT_REQUIRED_INPUT_VALUES_DIFFER")
    require(e.get("GITHUB_WORKSPACE") == str(root), "WORKSPACE_DIFFERS")
    return {"schema": 1, "operation": OPERATION, "repository": REPOSITORY, "sourceSha": sha, "sourceTree": tree,
            "runId": run, "runAttempt": attempt, "ref": ref, "workflowRef": e["GITHUB_WORKFLOW_REF"],
            "workflowSha": sha, "job": OPERATION, "root": str(root), "recipientSha256": digest(public),
            "recipientFingerprint": fingerprint.upper()}


def actual_identity():
    require(os.name == "nt" and processes.host_role() == "windows-x64", "NATIVE_WINDOWS_X64_REQUIRED")
    require(str(ROOT) == os.environ.get("GITHUB_WORKSPACE"), "ACTUAL_CHECKOUT_ROOT_DIFFERS")
    event = decode(public_file(os.environ["GITHUB_EVENT_PATH"], 256 * 1024))
    return identity(dict(os.environ), event, ROOT)


def paths(admitted):
    parent = Path(os.environ["RUNNER_TEMP"])
    files.absolute_parts(str(parent))
    require(parent != ROOT and parent not in ROOT.parents and ROOT not in parent.parents, "TEMP_SOURCE_OVERLAP")
    suffix = admitted["runId"] + "-" + admitted["runAttempt"]
    return parent / ("p2pkit-windows-helper-" + suffix), parent / ("p2pkit-windows-helper-export-" + suffix)


def command_environment(base):
    """No credentials/hooks/ambient Java options; preserve every actual owner domain."""
    allowed = {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "TEMP", "TMP", "RUNNER_TEMP", "USERPROFILE", "HOME",
               "APPDATA", "LOCALAPPDATA", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
               processes.JOB_ENV, processes.CHAIN_ENV, processes.DOMAINS_ENV, processes.STATE_ENV, "GRADLE_USER_HOME"}
    result = {key: value for key, value in base.items() if key in allowed}
    result.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", GIT_TERMINAL_PROMPT="0",
                  GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS="0")
    return result


class Commands:
    """Private glue around the existing native owner; not another process owner."""
    def __init__(self, evidence, state, job, *, deadline, environment=None, cancellation=None):
        self.evidence, self.state, self.job = evidence, state, job
        self.deadline = deadline
        self.environment = command_environment(dict(os.environ) if environment is None else environment)
        self.records, self.directories = [], []
        self.cancelled = [] if cancellation is None else cancellation
        self.unknown = False

    def run(self, argv, name, *, cwd=ROOT, timeout=60, output_limit=MAX_OUTPUT, environment=None, finalizing=False):
        require(not self.unknown and not encrypted._QUARANTINE and not _HELD, "PRIOR_COMMAND_RETIREMENT_UNKNOWN")
        require(type(timeout) is int and 0 < timeout <= MAX_COMMAND_SECONDS and
                type(output_limit) is int and 0 < output_limit <= MAX_OUTPUT, "COMMAND_BOUND_INVALID")
        require(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name), "COMMAND_NAME_INVALID")
        directory = self.evidence.create_directory("command-" + str(len(self.records) + 1) + "-" + name)
        self.directories.append(directory)
        session = encrypted._Session(directory, "helper-command")
        session.borrowed += [self.evidence, self.state]
        invocation = uuid.uuid4().hex
        env = processes.ownership_environment(self.environment if environment is None else environment,
                self.job, invocation, str(self.state.path), str(self.state.path / "unused-home"), allow_new_context=True)
        row = {"schema": 1, "name": name, "argv": list(argv), "cwd": str(cwd), "invocation": invocation,
               "startedUtc": utc(), "waitExitCode": None, "retirement": "UNSTARTED", "outputs": {}}
        self.records.append(row)
        session.commands.append(row)
        out = err = scope = child = None
        domain_known = False
        end = min(self.deadline + (150 if finalizing else 0), time.monotonic() + timeout)
        try:
            require((finalizing or not self.cancelled) and time.monotonic() < end, "COMMAND_CANCELLED_OR_DEADLINE")
            private_json(directory, "start.json", row)
            out = session.hold("stdout", directory.create_file("stdout.bin", max_bytes=output_limit, deadline=end))
            err = session.hold("stderr", directory.create_file("stderr.bin", max_bytes=output_limit, deadline=end))
            scope = processes.make_scope(self.job, invocation, str(self.state.path), env["GRADLE_USER_HOME"])
            child = scope.spawn(list(argv), str(cwd), env, stdout=out, stderr=err)
            require(child.stdout is None and child.stderr is None, "BORROWED_SINK_MODE_REQUIRED")
            while True:
                require((finalizing or not self.cancelled) and time.monotonic() < end, "COMMAND_CANCELLED_OR_DEADLINE")
                out.verify()
                err.verify()
                code = child.poll()
                if code is not None:
                    row["waitExitCode"] = code
                    break
                time.sleep(.025)
            require(not scope.discover(), "CHILD_LEFT_LIVE_DESCENDANTS")
        except BaseException as error:
            session.capture("command", error)
        finally:
            if scope is not None:
                try:
                    require(scope.drain(grace=0, kill_wait=5) == [], "COMMAND_DOMAIN_RETIREMENT_UNKNOWN")
                    domain_known = True
                except BaseException as error:
                    session.capture("command-drain", error, unknown=True)
                try:
                    row["ownership"] = scope.description()
                    require(row["ownership"].get("discoveryErrors") == [], "COMMAND_DISCOVERY_UNKNOWN")
                except BaseException as error:
                    session.capture("command-description", error, unknown=True)
                try:
                    scope.close()
                except BaseException as error:
                    session.capture("command-close", error, unknown=True)
            else:
                domain_known = not session.unknown  # Failed construction carrier is already captured.
            if not domain_known or session.unknown:
                session.quarantine([item["owner"] for item in session.resources])
                self.unknown = True
                row["retirement"] = "UNKNOWN"
            else:
                row["retirement"] = "KNOWN"
                for label, stream in (("stdout", out), ("stderr", err)):
                    if stream is not None:
                        try:
                            row["outputs"][label] = stream.verify().as_dict()
                            stream.sync()
                        except BaseException as error:
                            session.capture(label + "-final", error)
                        session.close(stream)
            row["endedUtc"] = utc()
            try:
                session.finish()
            except BaseException as error:
                self.unknown |= error_detail(error)["retirementUnknown"]
                raise
        # Only after every exact child and inherited duplicate has retired.
        for label in ("stdout", "stderr"):
            raw = private_read(directory, label + ".bin", output_limit)
            row["outputs"][label]["sha256"] = digest(raw)
        private_json(directory, "command.json", row)
        return row, directory

    def close(self):
        errors = []
        if self.unknown or encrypted._QUARANTINE:
            _HELD.append(self)
            raise HelperError("COMMAND_CUSTODY_RETIREMENT_UNKNOWN")
        for directory in reversed(self.directories):
            try:
                directory.close()
            except BaseException as error:
                errors.append(error)
        if errors:
            self.unknown = True
            _HELD.append(self)
            failure = HelperError("COMMAND_DIRECTORY_RETIREMENT_UNKNOWN")
            for error in errors:
                files._note(failure, encoded(error_detail(error)).decode("ascii"))
            raise failure from errors[0]


def source_snapshot(commands, git, *, finalizing=False, observe=None):
    def query(stage, *args):
        if observe is not None:
            observe(stage)
        argv = [str(git), "--no-replace-objects", "-c", "core.autocrlf=false", "-c", "core.fsmonitor=false",
                "-c", "core.hooksPath=" + str(commands.state.path), "-c", "credential.helper=", "-C", str(ROOT), *args]
        row, directory = commands.run(argv, "source", timeout=60, finalizing=finalizing)
        require(row["waitExitCode"] == 0, "SOURCE_QUERY_FAILED")
        return private_read(directory, "stdout.bin", MAX_OUTPUT)
    require(query(Stage.SOURCE_TOPLEVEL, "rev-parse", "--show-toplevel").decode().strip().replace("/", "\\").casefold() ==
            str(ROOT).casefold(), "SOURCE_TOPLEVEL_DIFFERS")
    sha = query(Stage.SOURCE_HEAD, "rev-parse", "HEAD").decode().strip()
    tree = query(Stage.SOURCE_TREE, "rev-parse", "HEAD^{tree}").decode().strip()
    require(query(Stage.SOURCE_SHALLOW, "rev-parse", "--is-shallow-repository").strip() == b"false", "FULL_HISTORY_REQUIRED")
    require(query(Stage.SOURCE_STATUS, "status", "--porcelain=v1", "--untracked-files=all", "--ignored").strip() == b"",
            "CLEAN_FRESH_SOURCE_REQUIRED")
    require(query(Stage.SOURCE_ORIGIN, "config", "--get", "remote.origin.url").strip() in
            (b"https://github.com/p2pKit/P2pKit.git", b"https://github.com/p2pKit/P2pKit",
             b"git@github.com:p2pKit/P2pKit.git"), "ORIGIN_REPOSITORY_DIFFERS")
    entries = witness.tree_entries(query(Stage.SOURCE_ENTRIES, "ls-tree", "-rlz", "HEAD"))
    if observe is not None:
        observe(Stage.SOURCE_BYTES)
    observed = {}
    for name, entry in entries.items():
        raw = public_file(ROOT / name, witness.MAX_FILE)
        require(witness.blob_matches(raw, entry), "TRACKED_SOURCE_BYTES_DIFFER")
        observed[name] = {**entry, "sha256": digest(raw)}
    return {"commit": sha, "tree": tree, "files": observed}


def method_inventory(raw, selected):
    """Derive exact reviewed method IDs; do not copy a historical numeric total."""
    nodes = {node.name: node for node in ast.parse(raw).body if isinstance(node, ast.ClassDef)}
    def methods(name):
        node = nodes[name]
        result = {child.name for child in node.body if isinstance(child, ast.FunctionDef) and child.name.startswith("test_")}
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in nodes:
                result |= methods(base.id)
        return result
    return {name: sorted(methods(name)) for name in selected}


def assert_unittest(raw, inventory):
    """Exact verbose original outcomes, counts and no skips/xfails; not an OK grep."""
    expected = {(case, name) for case, names in inventory.items() for name in names}
    rows = re.findall(rb"(?m)^(test_[a-zA-Z0-9_]+) \(([^\r\n()]+)\) \.\.\. ([^\r\n]+)\r?$", raw)
    actual = []
    for name, qualified, outcome in rows:
        parts = qualified.split(b".")
        # Python 3.11+ repeats the method inside parentheses; 3.9 does not.
        case = parts[-2] if len(parts) >= 2 and parts[-1] == name else parts[-1]
        actual.append((case.decode(), name.decode(), outcome.decode()))
    require(len(actual) == len(expected) and {(case, name) for case, name, _ in actual} == expected and
            all(outcome == "ok" for _, _, outcome in actual), "UNITTEST_METHOD_OUTCOMES_DIFFER")
    counts = re.findall(rb"(?m)^Ran ([0-9]+) tests? in [0-9.]+s\r?$", raw)
    require(counts == [str(len(expected)).encode()] and re.search(rb"(?m)^OK\r?$", raw) and
            not re.search(rb"(?im)^(FAILED|OK \(|.*\.\.\. (skipped|expected failure|unexpected success))", raw),
            "UNITTEST_COUNT_OR_TERMINAL_DIFFERS")


NATIVE_OBSERVATIONS = {
    "native-sinks": ("native-sinks-observed",),
    "native-output-bound": ("expected-native-bound-failure",),
    "native-launch-close": ("injected-native-close",),
    "native-tee": ("actual-tee-paths",),
    "native-controller-command": ("controller-command-observed",),
    "native-controller-retirement": ("controller-native-retirement",),
    "native-export": ("fixture-byte-contract", "native-crypto-observed"),
    "native-export-wrong-recipient": ("actual-gpg-wrong-recipient",),
    "native-export-input-quarantine": ("fixture-byte-contract", "actual-encryption-input-pin-hold"),
}


def assert_native_result(name, value, admitted, read_member):
    """Bind completed tiny native cases to their exact original observations.

    Invoked ONLY after the real child returned zero and its real Job drained and
    closed. In-process pin-hold results alone never grant retirement authority.
    """
    require(set(value) == {"schema", "case", "native", "passed", "source", "run", "observations",
            "privateDecryption", "expectedPinHoldToInterpreterExit", "retirement", "acceptanceAuthority"} and
            value["schema"] == 1 and type(value["schema"]) is int and value["case"] == name and
            value["native"] is True and value["passed"] is True and value["privateDecryption"] == "NOT_RUN" and
            value["source"] == {"commit": admitted["sourceSha"], "tree": admitted["sourceTree"]} and
            value["run"] == {"id": admitted["runId"], "attempt": admitted["runAttempt"]} and
            value["acceptanceAuthority"] == "PARENT_ZERO_EXIT_AND_NATIVE_JOB_RETIREMENT",
            "NATIVE_SUPPLEMENT_RESULT_DIFFERS")
    hold = value["expectedPinHoldToInterpreterExit"]
    require(type(hold) is bool and (not hold or name in ("native-output-bound", "native-export-input-quarantine")) and
            (name != "native-export-input-quarantine" or hold) and
            value["retirement"] == ("EXPECTED_PIN_HOLD_TO_EXIT" if hold else "KNOWN"), "NATIVE_HOLD_AUTHORITY_DIFFERS")
    expected = NATIVE_OBSERVATIONS[name]
    rows = value["observations"]
    require(type(rows) is list and len(rows) == len(expected), "NATIVE_OBSERVATION_INVENTORY_DIFFERS")
    observed = {}
    for label, row in zip(expected, rows):
        require(type(row) is dict and set(row) == {"path", "sha256"} and row["path"] == label + ".json" and
                re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "NATIVE_OBSERVATION_BINDING_DIFFERS")
        raw = read_member(row["path"])
        require(digest(raw) == row["sha256"], "NATIVE_OBSERVATION_BYTES_CHANGED")
        observed[label] = decode(raw)
    row = observed[expected[-1]]
    if name == "native-sinks":
        phases = row.get("actualNativeObservations", [])
        require([item.get("phase") for item in phases] == ["after-native-spawn", "after-real-scope-close"] and
                all(len(item.get("pins", [])) == 2 for item in phases) and
                row.get("stdout", {}).get("bytes") == 1028 and row.get("stderr", {}).get("bytes") == 258,
                "NATIVE_SINK_OBSERVATIONS_INCOMPLETE")
    elif name == "native-output-bound":
        require(row.get("admittedBytes") == 128 and row.get("bytesEmitted") == 1024 and
                row.get("productionRecordNeverPromoted") is True and type(row.get("expectedFailure")) is dict,
                "NATIVE_BOUND_OBSERVATIONS_INCOMPLETE")
    elif name == "native-launch-close":
        require(row.get("injection") == "AFTER_REAL_CLOSE_RETURN_NOT_AN_OS_FAULT" and
                row.get("productionRetirement") == "UNKNOWN" and row.get("actualFixtureDomainDrained") is True and
                row.get("realCloseAttempts") and all(item.get("realCloseReturned") is True for item in row["realCloseAttempts"]),
                "NATIVE_INJECTED_CLOSE_OBSERVATIONS_INCOMPLETE")
    elif name == "native-tee":
        cases = row.get("cases", [])
        require(row.get("finishPolicySeconds") == 3 and [item.get("mode") for item in cases] ==
                ["constructor", "not-started", "started-cancel"] and cases[0].get("outputRenamedAfterFailure") is True and
                cases[0].get("sourceStillCallerOwned") is True and all(item.get("completionAcknowledged") is True and
                item.get("workerRetired") is True for item in cases[1:]) and cases[2].get("originalCancellation") is True,
                "NATIVE_TEE_OBSERVATIONS_INCOMPLETE")
    elif name == "native-controller-command":
        cases = row.get("cases", [])
        require(row.get("productGradleExecuted") is False and len(cases) == 2 and
                cases[0].get("originalFailureRetained") is True and cases[0].get("firstTeeRetired") is True and
                cases[1].get("actualOuterOwnership", {}).get("discoveryErrors") == [],
                "NATIVE_CALLER_OBSERVATIONS_INCOMPLETE")
    elif name == "native-controller-retirement":
        require(row.get("injection") == "AFTER_REAL_CLOSE_RETURN_NOT_AN_OS_FAULT" and
                row.get("productGradleExecuted") is False and all(row.get(key) is True for key in
                ("allFiveRootsPreservedPerCase", "bothCasesAndOuterAttempted", "originalNegativeReceiptsRemainFailed")),
                "NATIVE_CALLER_RETIREMENT_OBSERVATIONS_INCOMPLETE")
    elif name == "native-export":
        require(row.get("privateDecryption") == "NOT_RUN" and all(row.get(key) is True for key in
                ("actualNativeArchiveBytesMatched", "actualInstalledGpgEncryptionReturned", "actualTruncationParserRejected")) and
                set(row.get("expectedPrivateChecks", {})) == {"crypto-output/evidence.tar.gz.gpg",
                    "decrypt-controls/corrupt-last-byte.gpg", "decrypt-controls/truncated.gpg"},
                "NATIVE_CRYPTO_OBSERVATIONS_INCOMPLETE")
    elif name == "native-export-wrong-recipient":
        require(row.get("actualGpgListingExecuted") is True and row.get("providedFingerprint") != row.get("actualFingerprint") and
                row.get("expectedFailure", {}).get("retirementUnknown") is False,
                "NATIVE_RECIPIENT_OBSERVATIONS_INCOMPLETE")
    elif name == "native-export-input-quarantine":
        require(row.get("injection") == "AFTER_REAL_SCOPE_CLOSE_NOT_AN_OS_FAULT" and
                row.get("productionRetirement") == "UNKNOWN" and row.get("original", {}).get("retirementUnknown") is True and
                all(row.get(key) is True for key in ("newInvocationBlocked", "heldThroughInterpreterExit", "noPinResetOrRetry")) and
                type(row.get("plaintextPinAfterExportRaises")) is dict and type(row.get("ancestorPinAfterExportRaises")) is dict,
                "NATIVE_INPUT_QUARANTINE_OBSERVATIONS_INCOMPLETE")
    if "fixture-byte-contract" in observed:
        contract = observed["fixture-byte-contract"]
        require(contract.get("privateKeyOnRunner") is False and contract.get("privateDecryption") == "NOT_RUN" and
                contract.get("directories") == ["evidence", "evidence/nested"] and
                set(contract.get("members", {})) == {"evidence/payload.bin", "evidence/empty", "evidence/nested/line-é.txt"},
                "NATIVE_FIXTURE_BYTE_CONTRACT_DIFFERS")
    return observed


def admitted_tools(*, observe=None):
    if observe is not None:
        observe(Stage.PYTHON_TOOL)
    python = Path(sys.executable)
    require(python.suffix.lower() == ".exe", "NATIVE_PYTHON_EXE_REQUIRED")
    python_sha = encrypted._executable(python, time.monotonic() + 30)
    if observe is not None:
        observe(Stage.GIT_TOOL)
    git = shutil.which("git.exe")
    require(git is not None, "INSTALLED_GIT_REQUIRED")
    git = Path(git)
    git_sha = encrypted._executable(git, time.monotonic() + 30)
    if observe is not None:
        observe(Stage.GPG_TOOL)
    gpg = shutil.which("gpg.exe")
    require(gpg is not None, "GPG_NOT_INSTALLED_ON_PATH")
    try:
        gpg_sha = encrypted._executable(Path(gpg), time.monotonic() + 30)
    except BaseException as error:
        raise HelperError("GPG_NOT_NATIVE_AMD64_OR_SAFE_FILE") from error
    return python, git, {"python": {"path": str(python), "sha256": python_sha, "version": sys.version},
                         "git": {"path": str(git), "sha256": git_sha},
                         "gpg": {"path": gpg, "sha256": gpg_sha}}


def close_all(owners):
    failures = []
    if encrypted._QUARANTINE or _HELD:
        _HELD.extend(owners)
        raise HelperError("PRIVATE_CUSTODY_RETIREMENT_UNKNOWN")
    for owner in reversed(owners):
        try:
            owner.close()
        except BaseException as error:
            failures.append(error)
    if failures:
        _HELD.extend(owners)
        error = HelperError("PRIVATE_ROOT_CLOSE_UNKNOWN")
        for failure in failures:
            files._note(error, encoded(error_detail(failure)).decode("ascii"))
        raise error from failures[0]


def run(progress=None):
    progress = Progress() if progress is None else progress
    progress.mark(Stage.IDENTITY)
    admitted = actual_identity()
    progress.mark(Stage.PATHS)
    base_path, output_path = paths(admitted)
    owners, failures, handlers = [], [], {}
    runner = base = evidence = state = work = output = None
    controls_passed = False
    source_verified = False
    final_record_written = False
    result = {"schema": 1, "identity": admitted, "startedUtc": utc(), "controls": [], "failures": failures,
              "controlsPassed": False, "retirement": "UNKNOWN", "privateDecryption": "NOT_RUN"}
    def hold(owner):
        owners.append(owner)
        return owner
    def fail(phase, error):
        detail = error_detail(error)
        failures.append({"phase": phase, "detail": detail,
                         "observation": public_observation(progress.stage, detail)})
        if detail["retirementUnknown"]:
            result["retirement"] = "UNKNOWN"
        return detail["retirementUnknown"]
    try:
        progress.mark(Stage.BASE_ROOT)
        base = hold(files.create_private_directory(base_path))
        progress.mark(Stage.STATE_ROOT)
        state = hold(base.create_directory("state"))
        progress.mark(Stage.EVIDENCE_ROOT)
        evidence = hold(base.create_directory("evidence"))
        progress.mark(Stage.WORK_ROOT)
        work = hold(base.create_directory("export-work"))
        progress.mark(Stage.OUTPUT_ROOT)
        output = hold(files.create_private_directory(output_path))
        progress.mark(Stage.START_RECORD)
        private_json(base, "started.json", result)
        progress.mark(Stage.COMMAND_SETUP)
        job = uuid.uuid4().hex
        runner = Commands(evidence, state, job, deadline=time.monotonic() + 900)
        progress.mark(Stage.SIGNAL_SETUP)
        for number in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGBREAK", signal.SIGINT)):
            if number not in handlers:
                handlers[number] = signal.getsignal(number)
                signal.signal(number, lambda signum, _: runner.cancelled.append(signum))
        python, git, tools = admitted_tools(observe=progress.mark)
        result["tools"] = tools
        before = source_snapshot(runner, git, observe=progress.mark)
        progress.mark(Stage.SOURCE_BINDING)
        require((before["commit"], before["tree"]) == (admitted["sourceSha"], admitted["sourceTree"]),
                "REVIEWED_SOURCE_IDENTITY_DIFFERS")
        private_json(evidence, "source-before.json", before)
        # Actual GPG admission precedes every fixture. Never download or fall back.
        progress.mark(Stage.RECIPIENT)
        recipient = encrypted.validate_recipient(os.environ["P2PKIT_EVIDENCE_PUBLIC_KEY"].encode("ascii"),
                       admitted["recipientFingerprint"], work, job_id=job)
        result["recipient"] = {"fingerprint": recipient.fingerprint, "encryptionFingerprint": recipient.encryption_fingerprint,
                               "expiresAt": recipient.expires_at, "keySha256": recipient.key_sha256}
        progress.mark(Stage.CONTROLS)
        suites = [("executor", "run-audit-command-test.py", 300), ("files", "hosted-windows-files-test.py", 180)]
        for label, script, timeout in suites:
            suite_state = hold(state.create_directory(label))
            fixtures = hold(suite_state.create_directory("fixtures"))
            temporary = hold(fixtures.create_directory("native-tmp"))
            suite_environment = dict(runner.environment)
            # The child gets a distinct real state while preserving any genuine
            # inherited domain. Commands.run appends that domain, never TEMP.
            suite_job = uuid.uuid4().hex
            suite_runner = Commands(evidence, suite_state, suite_job, deadline=runner.deadline,
                                    environment=suite_environment, cancellation=runner.cancelled)
            suite_evidence = evidence.path / (label + "-fixtures")
            args = [str(python), "-I", "-B", "-S", str(SCRIPTS / "tests" / script)]
            args += (["--expected-host", "windows-x64"] if label == "executor" else ["--native"])
            args += ["--evidence-dir", str(suite_evidence), "--fixture-parent", str(temporary.path)]
            try:
                row, directory = suite_runner.run(args, label, timeout=timeout)
                require(row["waitExitCode"] == 0, "NATIVE_SUITE_FAILED")
                raw = public_file(SCRIPTS / "tests" / script, witness.MAX_FILE)
                selection = (["PurePolicyTests", "DarwinObservationTests", "WindowsNativeTests"] if label == "executor" else
                             ["PurePolicyTests", "NativeCallShapeTests", "ModelCustodyTests", "NativeFixtureOrchestrationTests",
                              "NativeWindowsTests"])
                inventory = method_inventory(raw, selection)
                assert_unittest(private_read(directory, "stderr.bin", MAX_OUTPUT), inventory)
                if label == "executor":
                    cleanup = witness.assess_native_cleanup(suite_evidence, raw)
                    require(len(cleanup) == len(inventory["WindowsNativeTests"]), "EXECUTOR_CLEANUP_INVENTORY_DIFFERS")
                else:
                    with files.open_private_directory(suite_evidence) as retained:
                        summary = decode(private_read(retained, "summary.json"))
                    require(summary.get("passed") is True and summary.get("nativeRetirementKnown") is True and
                            summary.get("nativeMethods") == inventory["NativeWindowsTests"], "FILE_FIXTURE_RETENTION_INCOMPLETE")
                result["controls"].append({"suite": label, "passed": True, "inventory": inventory})
            finally:
                suite_runner.close()
        # Every narrow supplement is a separate native interpreter. An expected
        # injected UNKNOWN case ends there; no latch is cleared or owner reused.
        for name in NATIVE_CASES:
            native_state = hold(state.create_directory(name))
            native_runner = Commands(evidence, native_state, uuid.uuid4().hex, deadline=runner.deadline,
                                     cancellation=runner.cancelled)
            environment = dict(native_runner.environment)
            for key in ("GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_EVENT_NAME", "GITHUB_SHA", "GITHUB_RUN_ID",
                        "GITHUB_RUN_ATTEMPT", "P2PKIT_EVIDENCE_PUBLIC_KEY", "P2PKIT_EVIDENCE_FINGERPRINT"):
                environment[key] = os.environ[key]
            environment["P2PKIT_HELPER_SOURCE_TREE"] = admitted["sourceTree"]
            destination = evidence.path / name
            args = [str(python), "-I", "-B", "-S", str(SCRIPTS / "tests/windows-helper-native-test.py"),
                    "--case", name, "--evidence-dir", str(destination)]
            try:
                row, directory = native_runner.run(args, name, timeout=120, environment=environment)
                require(row["waitExitCode"] == 0, "NATIVE_SUPPLEMENT_FAILED")
                with files.open_private_directory(destination) as retained:
                    native = decode(private_read(retained, "result.json"))
                    assert_native_result(name, native, admitted, lambda member: private_read(retained, member))
                result["controls"].append({"suite": name, "passed": True, "result": native})
            finally:
                native_runner.close()
        require(not runner.cancelled, "HELPER_CANCELLED")
        controls_passed = True
    except BaseException as error:
        fail("controls", error)
    finally:
        if runner is not None and "before" in locals() and not runner.unknown and not encrypted._QUARANTINE and not _HELD:
            try:
                after = source_snapshot(runner, git, finalizing=True, observe=progress.mark)
                progress.mark(Stage.SOURCE_BINDING)
                require(after == before and actual_identity() == admitted, "POST_CONTROLS_SOURCE_OR_EVENT_CHANGED")
                private_json(evidence, "source-after.json", after)
                source_verified = True
            except BaseException as error:
                fail("final-source", error)
        if runner is not None:
            try:
                progress.mark(Stage.COMMAND_FINALIZATION)
                runner.close()
            except BaseException as error:
                fail("command-finalization", error)
        for number, handler in handlers.items():
            try:
                progress.mark(Stage.SIGNAL_RESTORE)
                signal.signal(number, handler)
            except BaseException as error:
                fail("restore-signal", error)
    try:
        progress.mark(Stage.EXPORT)
        require(base is not None and evidence is not None and work is not None and output is not None,
                "PRIVATE_ROOT_ADMISSION_INCOMPLETE")
        require(not encrypted._QUARANTINE and not (runner and runner.unknown) and
                not any(row["detail"]["retirementUnknown"] for row in failures), "HELPER_RETIREMENT_UNKNOWN")
        # If admission failed before obtaining a recipient, no encryption or test
        # retry is attempted. The original private failure remains on the runner.
        require("recipient" in locals(), "RECIPIENT_ADMISSION_INCOMPLETE")
        require(source_verified, "FINAL_SOURCE_BINDING_INCOMPLETE")
        result.update(controlsPassed=controls_passed and not failures, retirement="KNOWN", endedUtc=utc())
        private_json(evidence, "controls-result.json", result)
        private_json(base, "source-binding.json", before)
        manifest = encrypted.export_encrypted(evidence, output, recipient, source_commit=admitted["sourceSha"],
                       source_tree=admitted["sourceTree"], run_id=admitted["runId"], run_attempt=admitted["runAttempt"],
                       timeout_seconds=180)
        private_json(base, "return.json", {"schema": 1, "identity": admitted, "retirement": "KNOWN",
                     "controlsPassed": result["controlsPassed"], "manifest": manifest,
                     "manifestSha256": digest(private_read(output, encrypted.portable.MANIFEST)),
                     "resultSha256": digest(encoded(result)), "privateDecryption": "NOT_RUN"})
        final_record_written = True
    except BaseException as error:
        fail("export-or-return", error)
        if base is not None:
            try:
                private_json(base, "not-accepted.json", {"schema": 1, "identity": admitted, "failures": failures})
            except BaseException:
                pass  # Never substitute fabricated evidence or leak the raw error.
    try:
        progress.mark(Stage.ROOT_FINALIZATION)
        close_all(owners)
    except BaseException as error:
        fail("last-native-close", error)
        final_record_written = False
    if not final_record_written:
        # Preserve the FIRST failing boundary; later eligibility/finalizer errors
        # cannot relabel an earlier source/tool failure as recipient failure.
        observation = dict(failures[0]["observation"]) if failures else public_observation(Stage.UNOBSERVED, {})
        if encrypted._QUARANTINE or _HELD or any(row["detail"]["retirementUnknown"] for row in failures):
            observation["retirementObservation"] = RetirementObservation.UNKNOWN.value
        print_public_failure(observation)
        return 1
    print("WINDOWS_HELPER_CUSTODY=RETURNED_FOR_SEAL; PRIVATE_DECRYPTION=NOT_RUN")
    return 0  # The workflow's independently sealed controls_passed guard is mandatory.


def validate_public():
    admitted = actual_identity()
    require(os.environ.get("P2PKIT_HELPER_RUN_OUTCOME") == "success", "CONTROLLER_DID_NOT_RETURN_SAFELY")
    base_path, output_path = paths(admitted)
    owners, runner = [], None
    def hold(owner):
        owners.append(owner)
        return owner
    original = None
    result = None
    try:
        base = hold(files.open_private_directory(base_path))
        output = hold(files.open_private_directory(output_path))
        returned = decode(private_read(base, "return.json"))
        require(returned.get("schema") == 1 and returned.get("identity") == admitted and
                returned.get("retirement") == "KNOWN" and type(returned.get("controlsPassed")) is bool and
                returned.get("privateDecryption") == "NOT_RUN", "RETURN_BINDING_DIFFERS")
        # A new exact validation root refuses replay/overwrite in this run attempt.
        validation = hold(base.create_directory("post-return-validation"))
        state = hold(validation.create_directory("state"))
        captures = hold(validation.create_directory("commands"))
        runner = Commands(captures, state, uuid.uuid4().hex, deadline=time.monotonic() + 100)
        _, git, _ = admitted_tools()
        require(source_snapshot(runner, git) == decode(private_read(base, "source-binding.json")),
                "POST_RETURN_SOURCE_CHANGED")
        runner.close()
        runner = None
        with output.snapshot(max_bytes=files.MAX_FILE_BYTES, max_members=3) as snapshot:
            require(set(snapshot.entries) == {"", encrypted.portable.ARTIFACT, encrypted.portable.MANIFEST},
                    "PUBLIC_INVENTORY_DIFFERS")
            manifest_raw = private_read(output, encrypted.portable.MANIFEST, 65536)
            manifest = decode(manifest_raw)
            require(digest(manifest_raw) == returned["manifestSha256"] and manifest == returned["manifest"],
                    "PUBLIC_MANIFEST_DIFFERS")
            expected = encrypted.portable._manifest_identity(admitted["sourceSha"], admitted["sourceTree"],
                                                             admitted["runId"], admitted["runAttempt"])
            require(set(manifest) == {*expected, "artifact"} and all(manifest[key] == value for key, value in expected.items()),
                    "PUBLIC_MANIFEST_IDENTITY_DIFFERS")
            with snapshot.open_file(encrypted.portable.ARTIFACT) as stream:
                hashed = hashlib.sha256()
                size = 0
                for block in iter(lambda: stream.read(files.CHUNK), b""):
                    hashed.update(block)
                    size += len(block)
                require(manifest["artifact"] == {"name": encrypted.portable.ARTIFACT, "sha256": hashed.hexdigest(),
                                                 "size": size}, "PUBLIC_CIPHERTEXT_DIFFERS")
                stream.verify()
            snapshot.verify()
        with base.open_directory("evidence") as evidence:
            raw_result = private_read(evidence, "controls-result.json")
        controls = decode(raw_result)
        require(digest(raw_result) == returned["resultSha256"] and controls.get("identity") == admitted and
                controls.get("retirement") == "KNOWN" and controls.get("controlsPassed") is returned["controlsPassed"],
                "PRIVATE_RESULT_BINDING_DIFFERS")
        require(actual_identity() == admitted, "POST_RETURN_EVENT_CHANGED")
        result = {"controlsPassed": returned["controlsPassed"], "manifestSha256": returned["manifestSha256"]}
        private_json(validation, "seal.json", {"schema": 1, "identity": admitted, "ciphertextSeal": "PASS", **result})
    except BaseException as error:
        original = error
    finally:
        if runner is not None:
            try:
                runner.close()
            except BaseException as error:
                if original is None:
                    original = error
                else:
                    files._note(original, encoded(error_detail(error)).decode("ascii"))
        try:
            close_all(owners)
        except BaseException as error:
            if original is None:
                original = error
            else:
                files._note(original, encoded(error_detail(error)).decode("ascii"))
    if original is not None:
        raise original
    require(result is not None, "POST_RETURN_SEAL_INCOMPLETE")
    destination = Path(os.environ["GITHUB_OUTPUT"])
    public_file(destination, 1024 * 1024)
    with destination.open("a", encoding="ascii", newline="\n") as stream:
        stream.write("artifacts_ready=true\ncontrols_passed=" + str(result["controlsPassed"]).lower() + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    print("WINDOWS_HELPER_CIPHERTEXT_SEAL=PASS; PRIVATE_DECRYPTION=NOT_RUN")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "validate-public"))
    args = parser.parse_args()
    progress = Progress()
    try:
        if args.action == "run":
            return run(progress)
        progress.mark(Stage.POST_RETURN_SEAL)
        return validate_public()
    except BaseException as error:
        print_public_failure(public_observation(progress.stage, error_detail(error)))
        return 1


if __name__ == "__main__":
    sys.exit(main())
