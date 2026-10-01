#!/usr/bin/env python3
"""Fixed Darwin dependency-maintenance bridge; no CLI or publication authority.

The OS/private-file/peer/direct-child mechanisms are selectively derived from
90205d048cb91bcd07544e9cad8509987616b272's tiny native experiment (runtime SHA256
e7ee6a443987146c4019648c9c75ab32bb3300be16b8035fcba4321b0501add5). Its UDP probe,
diagnostic workflow, failure-export path and recipient/output owner are NOT
imported. Changed productive sessions, cancellation and custody require their
own genuine hosted qualification; tiny success is not that qualification.

F owns the original public Recipient/exporter and command file in its caller.
D is the real nonroot launchd service, P its sole direct canonical controller,
and K the unchanged canonical executor's child. All records below are DATA,
never serialized process tokens, native owners, or permission to export.
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
import grp
import hashlib
import importlib.util
import json
import math
import os
import platform
import plistlib
import pwd
import re
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
MODULE = "scripts/hosted_dependency_update_context.py"
LAUNCHER_SOURCE = "scripts/hosted_dependency_context_launcher.c"
LAUNCHER_HEADER = "hosted_dependency_context_launcher_config.h"
XCODE_DEVELOPER = "/Applications/Xcode_26.5.app/Contents/Developer"
LAUNCHER_TOOLCHAIN = "/Library/Developer/CommandLineTools"
LAUNCHER_SDK = LAUNCHER_TOOLCHAIN + "/SDKs/MacOSX.sdk"
REPOSITORY = "p2pKit/P2pKit"
OWNER, OWNER_ID = "Apdelrahman1911", "104788132"
INTERPRETER = "/Library/Developer/CommandLineTools/usr/bin/python3"
NS, UINT64 = 1_000_000_000, (1 << 64) - 1
CLOCK_SCHEMA = 2
CLOCK_DOMAIN = "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"
FRAME_BYTES, STREAM_BYTES = 16384, 65536
EVIDENCE_BYTES, FILE_BYTES = 4 * 1024 * 1024, 32 * 1024 * 1024
JSON_DEPTH, JSON_NODES = 32, 4096
ADMIN_SECONDS, ABORT_SECONDS = 10, 120
POLICY_PATH = ".github/test-evidence-recipient.json"
POLICY_SHA256 = "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521"
POLICY_EXPIRES = 1791158400
SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
NUMBER = re.compile(r"[1-9][0-9]{0,19}\Z")
UUID = re.compile(r"[0-9a-f]{32}\Z")
OWNER_ENV = ("P2PKIT_AUDIT_JOB_ID", "P2PKIT_AUDIT_OWNERSHIP_CHAIN",
             "P2PKIT_AUDIT_OWNERSHIP_DOMAINS", "P2PKIT_AUDIT_STATE_DIR", "GRADLE_USER_HOME")
TOOL_ENV = ("PATH", "JAVA_HOME", "P2PKIT_AUDIT_JDK21", "DEVELOPER_DIR", "ANDROID_HOME")
STARTUP_TOOL_ENV = ("PATH", "JAVA_HOME", "P2PKIT_AUDIT_JDK21", "DEVELOPER_DIR")
IDENTITY_KEYS = frozenset(("pid", "parentPid", "uniqueId", "parentUniqueId", "pidVersion", "startSeconds",
                           "startMicroseconds", "uid", "realUid", "savedUid", "gid", "realGid", "savedGid", "status"))
EVFILT_PROC, EV_ADD, EV_ENABLE, EV_RECEIPT, EV_ERROR = -5, 0x1, 0x4, 0x40, 0x4000
NOTE_EXIT, NOTE_EXITSTATUS = 0x80000000, 0x04000000
SOL_LOCAL, LOCAL_PEERPID, LOCAL_PEERTOKEN = 0, 0x002, 0x006
STAT_FORMAT = "%d:%i:%p:%u:%g:%l:%z:%m:%c"
ROOT_TEMPLATE = "/private/var/db/p2pkit-context.XXXXXXXXXX"
OS_TOOLS = ("/usr/bin/sudo", "/usr/bin/mktemp", "/usr/bin/stat", "/usr/bin/tee", "/bin/cat", "/bin/ls",
            "/bin/rm", "/bin/rmdir", "/bin/launchctl", "/usr/bin/git", "/usr/bin/sw_vers", "/bin/chmod")
OS_PARENTS = ("/", "/private", "/private/var", "/private/var/db", "/usr", "/usr/bin", "/bin")
# Keep all original 96 operations. Add chmod's three original metadata calls,
# 19 fixed launcher-create checks + at most four FRAME_BYTES writes, and eight
# launcher-retirement operations. No elapsed-time/stream/input bound changes.
ADMIN_CALL_LIMIT = 96 + 3 + 19 + (STREAM_BYTES + FRAME_BYTES - 1) // FRAME_BYTES + 8
LAUNCHER_FILES = frozenset(("launcher.c", LAUNCHER_HEADER, "launcher-dependencies.before.d",
                            "launcher-dependencies.after.d", "launcher.bin", "launcher.json",
                            "launcher-command-1.json", "launcher-command-2.json", "launcher-command-3.json"))
LAUNCHER_ROLES = frozenset(("ROOT_FILE", "COMPILER", "LINKER", "SDK", "RESOURCE", "DEPENDENCY",
                            "LIBSYSTEM", "LIBPROC"))
LAUNCHER_CHAINS = frozenset(("LEXICAL", "RESOLVED"))
LAUNCHER_NODES = ("SELF", *("P%02d" % index for index in range(1, 33)), "DEEPER")
LAUNCHER_PREDICATES = frozenset(("OWNER", "MODE", "WRITE_ACCESS", "PATH_TYPE", "DIRECTORY_TYPE", "FILE_TYPE",
                                "PIN_TYPE", "PIN_OWNER", "LINK_COUNT", "SIZE_POSITIVE", "SIZE_MAXIMUM", "EXEC_ACCESS"))
LAUNCHER_DETAIL_KEYS = frozenset(("launcher_role", "launcher_chain", "launcher_node", "launcher_predicate"))
LAUNCHER_MACHO_PREDICATES = frozenset(("INPUT_BOUND", "HEADER", "COMMAND_HEADER", "COMMAND_SHAPE",
    "NAME_COMMAND_SIZE", "NAME_OFFSET_TERMINATOR", "NAME_PADDING", "DYLIB_NAME", "LOADER_NAME", "SEGMENT_SIZE",
    "SEGMENT_SHAPE", "TEXT_SEGMENT", "ENTRY_COMMAND", "ENTRY_STACK", "BUILD_COMMAND", "BUILD_TARGET",
    "DATA_COMMAND_SIZE", "DATA_RANGE", "SYMBOL_COMMAND_SIZE", "SYMBOL_RANGES", "FIXED_COMMAND_SIZE",
    "COMMANDS_END", "LOADER_PRESENT", "LIBRARY_SET", "TEXT_PRESENT", "ENTRY_PRESENT", "ENTRY_RANGE",
    "BUILD_PRESENT", "SIGNATURE_COUNT"))
FRAME_ROSTER = ((1, "D>F", "HELLO"), (2, "F>D", "PREPARE"), (3, "P>D", "CHILD_READY"),
                (4, "D>F", "CHILD_READY"), (5, "F>D", "START"), (6, "D>P", "START"),
                (7, "P>D", "RESULT"), (8, "D>F", "CHILD_RESULT_AND_EXIT_READY"))
CASE_INPUT_KEYS = frozenset(("schema", "scope", "case", "binding", "github", "allocationSha256", "repositorySource",
                             "caseDirectoryIdentity", "foreground", "account", "caseStartNs", "caseEndNs"))
CANONICAL_ENTRY_KEYS = frozenset(("schema", "scope", "case", "binding", "caseInputSha256", "contextSha256",
                                  "contextId", "gradlePolicySha256", "producerIdentity", "enteredMonotonicNs"))
PRODUCER_RESULT_KEYS = frozenset(("schema", "scope", "case", "binding", "caseInputSha256", "canonicalEntrySha256",
                                  "producerIdentity", "commands", "code", "disposition", "completedRawNs"))
PREPARED_KEYS = frozenset(("schema", "scope", "binding", "case", "github", "allocation", "source", "account",
                           "foreground", "boot", "interpreter", "directoryIdentity", "operationIdentity",
                           "socketIdentity", "caseInputSha256", "caseEndNs", "stepEndNs", "jobEndNs", "policyEndNs",
                           "tools"))
CASE_FILES = frozenset(("case-input.json", "prepared.json", "canonical-entry.json", "producer-result.json",
                       "producer-captures.json", "producer-delivery.json", "producer-controller.stdout",
                       "producer-controller.stderr", "admin.jsonl", "launch.plist", "native-observations.json",
                       "action-observation.json", "bridge-protocol.json", "bridge-result.json")) | LAUNCHER_FILES
SERVICE_FILES = frozenset(("service.stdout", "service.stderr", "producer-pipe.stdout", "producer-pipe.stderr"))
FAILURE_FILES = {"D": "service-failure.json", "P": "producer-failure.json"}
FAILURE_KIND = "QUALIFICATION_FAILURE_DIAGNOSTIC"
FAILURE_BYTES, FAILURE_HINT_BYTES = 4096, 12288
FAILURE_MODULES = frozenset(("BRIDGE", "CALLER", "CANONICAL", "OWNERSHIP"))
FAILURE_ACTIONS = frozenset(("NONE", "RELEASE", "F_WRITE_EOF", "D_SIGKILL", "INVALID"))
FAILURE_PREDICATES = frozenset(("CASE_SUPPORTED", "RETURN_CODE_TYPE", "RECEIPT_TYPE", "RETURN_CODE", "SCHEMA",
    "INVOCATION_ID", "JOB_ID", "COMMAND_KIND", "PURPOSE", "PRODUCT_ARGV", "CONTROLLER_PID", "CWD", "WRAPPER",
    "HOST", "GRADLE_HOME", "SOURCE_SNAPSHOTS", "SOURCE_UNCHANGED", "PRODUCT_PID", "PRODUCT_EXIT", "STOP_EXIT",
    "FINAL_EXIT", "OWNED_SURVIVORS", "OWNERSHIP_DISCOVERY", "STOP_ARGV", "ERRORS_EMPTY", "CANCEL_SIGNALS_ABSENT",
    "CANCEL_REQUEST_ABSENT", "CANCELLATION_ERRORS", "CANCEL_SIGNALS", "CANCEL_REQUEST"))
STARTUP_DIAGNOSTIC_SECONDS = 30  # Fail-only probe safety; not canonical-init120 or an ordinary deadline.
STARTUP_DIAGNOSTIC_PHASES = frozenset(("PREPARE_CASE", "INPUTS_AND_ADMIN", "SOCKET_PREPARE", "LAUNCHER_CREATE",
    "BOOTSTRAP", "WAIT_CONNECT", "PEER_CHECK", "WAIT_HELLO", "HELLO_CHECK", "INSPECT_AND_ATTACH",
    "WAIT_CHILD_READY", "CHILD_READY_CHECK", "START_HANDOFF", "WAIT_FINAL", "FINAL_VALIDATE", "RETIRE"))
STARTUP_DIAGNOSTIC_STATUSES = frozenset(("NOT_OBSERVED", "RUNNING", "NOT_RUNNING", "SPAWN_SCHEDULED", "WAITING",
    "REGISTRATION_ABSENT", "PRINT_FAILED", "INVALID", "UNSUPPORTED"))


class ContextError(RuntimeError):
    """Only finite nonsecret stage/reason tokens may reach a public caller."""

    def __init__(self, stage, reason="REFUSED", errno_name="NONE", **details):
        self.stage, self.reason, self.errno_name = stage, reason, errno_name
        self.details = details  # Private structured location DATA, never arbitrary exception text.
        super().__init__(stage + "/" + reason + "/" + errno_name)


class ProductionRefusal(ContextError):
    pass


def require(value, stage, reason="REFUSED", errno_name="NONE", **details):
    if not value:
        raise ContextError(stage, reason, errno_name, **details)


def public_error(error):
    if isinstance(error, ContextError):
        result = "DEPENDENCY_CONTEXT/" + error.stage + "/" + error.reason + "/" + error.errno_name
        # Project only these source-defined labels, never private location DATA.
        # Keep the existing failure classification and native errno unchanged.
        if (error.stage, error.reason, error.errno_name) == ("SOURCE", "LAUNCHER_ROOT_INPUT", "NONE"):
            details = error.details
            fields = (("launcher_role", LAUNCHER_ROLES), ("launcher_chain", LAUNCHER_CHAINS),
                      ("launcher_node", LAUNCHER_NODES), ("launcher_predicate", LAUNCHER_PREDICATES))
            if type(details) is dict and set(details) == LAUNCHER_DETAIL_KEYS and all(
                    type(details[name]) is str and details[name] in admitted for name, admitted in fields):
                labelled = result + "/" + "/".join(details[name] for name, _admitted in fields)
                if len(labelled) <= 160:
                    return labelled
        elif (error.stage, error.reason, error.errno_name) == ("SOURCE", "LAUNCHER_MACHO", "NONE"):
            details = error.details
            if (type(details) is dict and all(type(name) is str for name in details) and
                    set(details) == {"launcher_macho_predicate"}):
                predicate = details["launcher_macho_predicate"]
                if type(predicate) is str and predicate in LAUNCHER_MACHO_PREDICATES:
                    labelled = result + "/" + predicate
                    if len(labelled) <= 160:
                        return labelled
        elif (type(error) is ContextError and getattr(error, "_startup_profile", None) is STARTUP and
              (error.stage, error.reason, error.errno_name) in (("START", "TIMEOUT", "NONE"),
              ("START", "TIMEOUT", "ETIMEDOUT"), ("START", "STARTUP_OBSERVATION_ONLY", "NONE"))):
            details = getattr(error, "_startup_diagnostic", None)
            if _startup_diagnostic_valid(details):
                labelled = result + "/" + "/".join(details[name] for name in
                    ("startup_phase", "registration_status", "registration_exit"))
                if len(labelled) <= 160:
                    return labelled
        return result
    return "DEPENDENCY_CONTEXT/UNKNOWN/REFUSED/UNKNOWN"


def _startup_diagnostic_valid(value):
    if (type(value) is not dict or not all(type(key) is str for key in value) or
            set(value) != {"startup_phase", "registration_status", "registration_exit"} or
            not all(type(item) is str for item in value.values())):
        return False
    code = value["registration_exit"]
    return (value["startup_phase"] in STARTUP_DIAGNOSTIC_PHASES and
            value["registration_status"] in STARTUP_DIAGNOSTIC_STATUSES and
            (code in ("NONE", "UNSUPPORTED") or
             re.fullmatch(r"CODE_(?:0|[1-9][0-9]{0,2})", code) is not None and int(code[5:]) <= 255))


def errno_name(value):
    name = errno.errorcode.get(value, "UNKNOWN")
    return name if name in {"EPERM", "EACCES", "ENOENT", "ESRCH", "EINTR", "EPIPE", "EINVAL",
                            "ECONNRESET", "ETIMEDOUT"} else "UNKNOWN"


@contextlib.contextmanager
def at_stage(stage):
    try:
        yield
    except ContextError:
        raise
    except OSError as error:
        raise ContextError(stage, "PERMISSION_DENIED" if error.errno in (errno.EPERM, errno.EACCES)
                           else "RETURN_FAILED", errno_name(error.errno)) from None
    except subprocess.TimeoutExpired:
        raise ContextError(stage, "TIMEOUT", "ETIMEDOUT") from None
    except BaseException:
        raise ContextError(stage, "REFUSED", "UNKNOWN") from None


class _Profile:
    __slots__ = ("script", "workflow", "job", "scope", "cases", "operation_env", "request_env",
                 "operation_prefix", "job_seconds", "step_seconds", "upload_seconds", "ref")

    def __init__(self, script, workflow, job, scope, cases, operation_env, request_env,
                 operation_prefix, job_seconds, step_seconds, upload_seconds, ref):
        self.script, self.workflow, self.job, self.scope, self.cases = script, workflow, job, scope, cases
        self.operation_env, self.request_env, self.operation_prefix = operation_env, request_env, operation_prefix
        self.job_seconds, self.step_seconds, self.upload_seconds, self.ref = job_seconds, step_seconds, upload_seconds, ref


GENERATION = _Profile("scripts/run-hosted-dependency-update.py", ".github/workflows/dependency-update-candidate.yml",
    "generate", "MANUAL_DEPENDENCY_GENERATION_ONLY_V1", ("GENERATION",), "P2PKIT_DEPENDENCY_OPERATION",
    "P2PKIT_MAINTENANCE_REQUEST", "p2pkit-dependency-update-", 12600, 9900, 1320,
    re.compile(r"refs/heads/(?:main|work/release-foundation-[A-Za-z0-9-]+)\Z"))
QUALIFICATION = _Profile("scripts/run-hosted-dependency-context-qualification.py",
    ".github/workflows/dependency-update-context-qualification.yml", "dependency_context_qualification",
    "MANUAL_DEPENDENCY_CONTEXT_QUALIFICATION_V1", ("Q1", "Q2", "Q3", "Q4"),
    "P2PKIT_DEPENDENCY_CONTEXT_OPERATION", "P2PKIT_DEPENDENCY_CONTEXT_REQUEST", "p2pkit-dependency-context-",
    2460, 1740, 420, re.compile(r"refs/heads/work/release-foundation-dependency-context-[A-Za-z0-9-]+\Z"))
STARTUP = _Profile("scripts/run-hosted-jmdns-startup.py", ".github/workflows/audit-jmdns-startup-context.yml",
    "jmdns_startup", "DIRECT_JAVA_STARTUP_DIAGNOSTIC_V1", ("STARTUP",), "P2PKIT_JMDNS_STARTUP_OPERATION",
    "P2PKIT_JMDNS_STARTUP_REQUEST", "p2pkit-jmdns-startup-", 12600, 9900, 1320,
    re.compile(r"refs/heads/work/release-foundation-dependency-context-startup-[A-Za-z0-9-]+\Z"))
STARTUP_PURPOSES = (
    "startup-prerequisites", "startup-slf4j-download", "startup-vendor-javac", "startup-fixture-javac",
    "startup-control", "startup-failed_recovery", "startup-shared_close", "startup-close_wins",
    "startup-recovery_wins", "startup-responder_close", "startup-callback_executor", "startup-cleanup_retry",
)


def validate_profile(profile):
    require(profile is GENERATION or profile is QUALIFICATION or profile is STARTUP, "SOURCE", "PROFILE")
    return profile


def shared_raw_ns():
    require(sys.platform == "darwin" and callable(getattr(time, "clock_gettime_ns", None)) and
            type(getattr(time, "CLOCK_MONOTONIC_RAW", None)) is int, "PREPARE", "UNSUPPORTED")
    value = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
    require(type(value) is int and 0 <= value <= UINT64, "PREPARE", "BOUND")
    return value


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    pending, nodes = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        require(nodes <= JSON_NODES and depth <= JSON_DEPTH, "PREPARE", "BOUND")
        if type(item) is dict:
            require(all(type(key) is str for key in item), "PREPARE")
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        else:
            require(item is None or type(item) in (str, int, bool, float), "PREPARE")
            require(type(item) is not float or math.isfinite(item), "PREPARE")
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
    except (TypeError, ValueError, RecursionError):
        raise ContextError("PREPARE", "BOUND") from None


def parsed(raw, limit=FRAME_BYTES):
    require(type(raw) is bytes and type(limit) is int and 0 < len(raw) <= limit, "PREPARE", "BOUND")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "PREPARE")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: require(False, "PREPARE"))
    except (ValueError, UnicodeError, RecursionError):
        raise ContextError("PREPARE") from None
    require(len(encoded(value)) <= limit, "PREPARE", "BOUND")
    return value


def copy_data(value):
    return parsed(encoded(value), FILE_BYTES)


def physical(value):
    path, original = Path(value), os.fspath(value)
    require(type(original) is str and str(path) == original and not original.startswith("//") and
            all(32 <= ord(char) < 127 for char in original) and path.is_absolute() and ".." not in path.parts,
            "PREPARE")
    for item in (path, *path.parents):
        require(not item.is_symlink(), "PREPARE", "IDENTITY_CHANGED")
    return path


def private_directory(path, *, empty=False):
    path = physical(path)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
            "PREPARE", "IDENTITY_CHANGED")
    require(not empty or not any(path.iterdir()), "PREPARE")
    return [info.st_dev, info.st_ino]


def read_file(path, limit=STREAM_BYTES):
    path = physical(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid() and
                not before.st_mode & 0o022 and 0 <= before.st_size <= limit, "PREPARE", "BOUND")
        raw = stream.read(limit + 1)
        stamp = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid, value.st_nlink,
                               value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        require(len(raw) == before.st_size and stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()),
                "PREPARE", "IDENTITY_CHANGED")
    return raw


def write_new(path, raw):
    require(type(raw) is bytes and len(raw) <= FILE_BYTES, "FREEZE", "BOUND")
    path = physical(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        require(stream.write(raw) == len(raw), "FREEZE", "RETURN_FAILED")
        stream.flush()
        os.fsync(stream.fileno())
    require(read_file(path, max(STREAM_BYTES, len(raw))) == raw, "FREEZE", "IDENTITY_CHANGED")


def left(end_ns, stage="START"):
    require(type(end_ns) is int, stage, "TIMEOUT")
    remaining = (end_ns - shared_raw_ns()) / NS
    require(remaining > 0, stage, "TIMEOUT")
    return remaining


def failure_sites(error, profile):
    """Failure DATA only: bounded original traceback sites, never error text."""
    require(profile is QUALIFICATION, "CLOSE", "DIAGNOSTIC")
    paths = {str(ROOT / MODULE): "BRIDGE", str(ROOT / profile.script): "CALLER",
             str(ROOT / "scripts/run-audit-command.py"): "CANONICAL",
             str(ROOT / "scripts/audit_processes.py"): "OWNERSHIP"}
    sites, node, count, truncated = [], error.__traceback__, 0, False
    while node is not None and count < 32:
        token, line = paths.get(node.tb_frame.f_code.co_filename), node.tb_lineno
        if token is not None and type(line) is int and 1 <= line <= 1_000_000:
            if len(sites) == 12:
                del sites[0]
                truncated = True
            sites.append({"module": token, "line": line})
        node, count = node.tb_next, count + 1
    return {"sites": sites, "truncated": truncated or node is not None}


def _failure_binding(profile, prepared):
    require(profile is QUALIFICATION and type(prepared) is dict and set(prepared) == PREPARED_KEYS and
            type(prepared["schema"]) is int and prepared["schema"] == 1 and prepared["scope"] == profile.scope and
            type(prepared["case"]) is str and prepared["case"] in profile.cases and
            all(type(prepared[key]) is str and HASH.fullmatch(prepared[key]) for key in ("binding", "caseInputSha256")) and
            type(prepared["source"]) is dict, "CLOSE", "DIAGNOSTIC")
    return {"schema": 1, "kind": FAILURE_KIND, "scope": profile.scope, "case": prepared["case"],
            "binding": prepared["binding"], "caseInputSha256": prepared["caseInputSha256"],
            "sourceSha256": digest(encoded(prepared["source"]))}


def _failure_detail(value):
    require(type(value) is dict and set(value) == {"sites", "truncated", "predicates"} and
            type(value["truncated"]) is bool and type(value["sites"]) is list and len(value["sites"]) <= 12 and
            type(value["predicates"]) is list and len(value["predicates"]) <= 32, "CLOSE", "DIAGNOSTIC")
    for site in value["sites"]:
        require(type(site) is dict and set(site) == {"module", "line"} and type(site["module"]) is str and
                site["module"] in FAILURE_MODULES and type(site["line"]) is int and
                1 <= site["line"] <= 1_000_000, "CLOSE", "DIAGNOSTIC")
    require(all(type(label) is str and label in FAILURE_PREDICATES for label in value["predicates"]) and
            len(set(value["predicates"])) == len(value["predicates"]), "CLOSE", "DIAGNOSTIC")
    return value


def record_failure(profile, directory, prepared, role, error):
    """Best effort after failure, using only the retained validated context."""
    if profile is not QUALIFICATION:
        return
    try:
        binding = _failure_binding(profile, prepared)
        require(type(role) is str and role in FAILURE_FILES, "CLOSE", "DIAGNOSTIC")
        left(prepared["caseEndNs"], "CLOSE")
        require(private_directory(directory) == prepared["directoryIdentity"], "CLOSE", "DIAGNOSTIC")
        labels = getattr(error, "_qualification_failure_predicates", ())
        require(type(labels) is tuple and len(labels) <= 32, "CLOSE", "DIAGNOSTIC")
        detail = _failure_detail({**failure_sites(error, profile), "predicates": list(labels)})
        raw = encoded({**binding, "role": role, **detail})
        require(len(raw) <= FAILURE_BYTES, "CLOSE", "DIAGNOSTIC")
        left(prepared["caseEndNs"], "CLOSE")
        write_new(directory / FAILURE_FILES[role], raw)
        left(prepared["caseEndNs"], "CLOSE")
    except BaseException:
        # A diagnostic is never allowed to replace the original failure.
        return


def _read_failure_marker(profile, directory, prepared, role):
    try:
        left(prepared["caseEndNs"], "CLOSE")
        expected = {**_failure_binding(profile, prepared), "role": role}
        path = physical(directory / FAILURE_FILES[role])
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return {"status": "MISSING"}
        try:
            with os.fdopen(fd, "rb", closefd=False) as stream:
                before = os.fstat(fd)
                require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid() and
                        stat.S_IMODE(before.st_mode) == 0o600 and 0 <= before.st_size <= FAILURE_BYTES,
                        "CLOSE", "DIAGNOSTIC")
                left(prepared["caseEndNs"], "CLOSE")
                raw = stream.read(FAILURE_BYTES + 1)
                stamp = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid,
                                       value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
                require(len(raw) == before.st_size and
                        stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()), "CLOSE", "DIAGNOSTIC")
        finally:
            os.close(fd)
        value = parsed(raw, FAILURE_BYTES)
        require(type(value) is dict and set(value) == set(expected) | {"sites", "truncated", "predicates"} and
                all(value[key] == original for key, original in expected.items()) and
                type(value["schema"]) is int and raw == encoded(value), "CLOSE", "DIAGNOSTIC")
        detail = _failure_detail({key: value[key] for key in ("sites", "truncated", "predicates")})
        left(prepared["caseEndNs"], "CLOSE")
        return {"status": "AVAILABLE", **detail}
    except BaseException:
        return {"status": "INVALID"}


def _failure_native_code(events, identity):
    if identity is None:
        return "NOT_OBSERVED"
    if type(identity) is not dict or type(identity.get("pid")) is not int or type(events) is not dict:
        return "INVALID"
    if identity["pid"] not in events:
        return "NOT_OBSERVED"
    event = events[identity["pid"]]
    if type(event) is not dict or type(event.get("status")) is not dict:
        return "INVALID"
    code = event["status"].get("popenCode")
    return code if type(code) is int and -127 <= code <= 255 else "INVALID"


def attach_failure_hint(profile, state, events, error):
    """Freeze original F-held observations before abort; never poll or rebind."""
    if profile is not QUALIFICATION:
        return
    try:
        require(type(error) is ContextError and (error.stage, error.reason, error.errno_name) ==
                ("CLOSE", "FINAL_FRAME_MISSING", "NONE"), "CLOSE", "DIAGNOSTIC")
        prepared, directory = state["prepared"], state["directory"]
        hint = _failure_binding(profile, prepared)
        action = state["action"].get("kind") if type(state["action"]) is dict else None
        hint["action"] = action if type(action) is str and action in FAILURE_ACTIONS else "INVALID"
        hint["codes"] = {role: _failure_native_code(events, state[name]) for role, name in
                         (("D", "service"), ("P", "producer"), ("K", "product"))}
        left(prepared["caseEndNs"], "CLOSE")
        require(private_directory(directory) == prepared["directoryIdentity"], "CLOSE", "DIAGNOSTIC")
        hint["failures"] = {role: _read_failure_marker(profile, directory, prepared, role) for role in ("D", "P")}
        raw = encoded(hint)
        require(len(raw) <= FAILURE_HINT_BYTES, "CLOSE", "DIAGNOSTIC")
        left(prepared["caseEndNs"], "CLOSE")
        error._qualification_failure_hint_raw = raw
    except BaseException:
        return


def public_failure_hint(error):
    """Optional finite, source-bound failure DATA; no exception-detail dump."""
    try:
        if type(error) is not ContextError or (error.stage, error.reason, error.errno_name) != (
                "CLOSE", "FINAL_FRAME_MISSING", "NONE"):
            return None
        raw = getattr(error, "_qualification_failure_hint_raw", None)
        if raw is None:
            return None
        value = parsed(raw, FAILURE_HINT_BYTES)
        require(type(value) is dict and set(value) == {"schema", "kind", "scope", "case", "binding", "caseInputSha256",
                "sourceSha256", "action", "codes", "failures"} and type(value["schema"]) is int and
                value["schema"] == 1 and value["kind"] == FAILURE_KIND and value["scope"] == QUALIFICATION.scope and
                type(value["case"]) is str and value["case"] in QUALIFICATION.cases and
                all(type(value[key]) is str and HASH.fullmatch(value[key]) for key in
                    ("binding", "caseInputSha256", "sourceSha256")) and
                type(value["action"]) is str and value["action"] in FAILURE_ACTIONS and
                type(value["codes"]) is dict and set(value["codes"]) == {"D", "P", "K"} and
                type(value["failures"]) is dict and set(value["failures"]) == {"D", "P"}, "CLOSE", "DIAGNOSTIC")
        require(all((type(code) is int and -127 <= code <= 255) or
                    (type(code) is str and code in ("NOT_OBSERVED", "INVALID")) for code in value["codes"].values()),
                "CLOSE", "DIAGNOSTIC")
        for failure in value["failures"].values():
            require(type(failure) is dict and type(failure.get("status")) is str, "CLOSE", "DIAGNOSTIC")
            if failure["status"] == "AVAILABLE":
                require(set(failure) == {"status", "sites", "truncated", "predicates"}, "CLOSE", "DIAGNOSTIC")
                _failure_detail({key: failure[key] for key in ("sites", "truncated", "predicates")})
            else:
                require(set(failure) == {"status"} and failure["status"] in ("MISSING", "INVALID"), "CLOSE", "DIAGNOSTIC")
        require(raw == encoded(value), "CLOSE", "DIAGNOSTIC")
        return raw.decode("ascii")[:-1]
    except BaseException:
        return None


def validate_account(actual, expected=None):
    require(type(actual) is dict and set(actual) == {"uid", "euid", "gid", "egid", "groups"}, "IDENTITY")
    require(all(type(actual[key]) is int and 0 <= actual[key] < 2 ** 32 for key in ("uid", "euid", "gid", "egid")) and
            actual["uid"] == actual["euid"] != 0 and actual["gid"] == actual["egid"], "IDENTITY")
    groups = actual["groups"]
    require(type(groups) is list and len(groups) <= 256 and
            all(type(value) is int and 0 <= value < 2 ** 32 for value in groups) and
            groups == sorted(set(groups)), "IDENTITY")
    require(expected is None or actual == expected, "IDENTITY", "IDENTITY_CHANGED")
    return actual


def account():
    return validate_account({"uid": os.getuid(), "euid": os.geteuid(), "gid": os.getgid(), "egid": os.getegid(),
                             "groups": sorted(set(os.getgroups()))})


def same_identity(actual, expected):
    for value in (actual, expected):
        require(type(value) is dict and set(value) == IDENTITY_KEYS and
                all(type(item) is int and item >= 0 for item in value.values()) and value["pid"] > 0 and
                value["uniqueId"] > 0 and value["status"] in (1, 2, 3, 4), "IDENTITY", "IDENTITY_CHANGED")
    require(all(actual[key] == expected[key] for key in IDENTITY_KEYS - {"status"}), "IDENTITY", "IDENTITY_CHANGED")
    return actual


def identity_account(identity, expected):
    validate_account(expected)
    require(identity["uid"] == identity["realUid"] == identity["savedUid"] == expected["uid"] and
            identity["gid"] == identity["realGid"] == identity["savedGid"] == expected["gid"],
            "IDENTITY", "IDENTITY_CHANGED")


def session_record(identity):
    return {"pid": identity["pid"], "sessionId": os.getsid(identity["pid"]),
            "processGroupId": os.getpgid(identity["pid"])}


def validate_orphan_identity(actual, original, service, current_session, original_session,
                             event_observed_ns, checked_ns):
    """DATA shape only; F calls this only from its original preattached D event."""
    same_identity(actual, actual)
    same_identity(original, original)
    same_identity(service, service)
    require(all(actual[key] == original[key] for key in IDENTITY_KEYS - {"status", "parentPid", "parentUniqueId"}),
            "IDENTITY", "IDENTITY_CHANGED")
    # Same-bound-image XNU reparent changes BSD parentPid but retains D's uniqueId.
    require(original["parentPid"] == service["pid"] and original["parentUniqueId"] == service["uniqueId"] and
            service["parentPid"] == 1 and
            (actual["parentPid"], actual["parentUniqueId"]) in
            ((service["pid"], service["uniqueId"]), (1, service["uniqueId"])), "IDENTITY", "IDENTITY_CHANGED")
    require(current_session == original_session == {"pid": original["pid"], "sessionId": original["pid"],
                                                    "processGroupId": original["pid"]}, "IDENTITY", "IDENTITY_CHANGED")
    require(type(event_observed_ns) is int and type(checked_ns) is int and 0 < event_observed_ns <= checked_ns,
            "IDENTITY", "EVENT_ORDER")
    return {"originalParentPid": original["parentPid"], "originalParentUniqueId": original["parentUniqueId"],
            "currentParentPid": actual["parentPid"], "currentParentUniqueId": actual["parentUniqueId"],
            "serviceExitObservedRawNs": event_observed_ns, "checkedRawNs": checked_ns}


def validate_allocation(profile, allocation, github, now_ns, wall_ns):
    validate_profile(profile)
    keys = {"schema", "clockDomain", "source", "sourceTree", "runId", "runAttempt", "startedMonotonicNs", "startedEpochNs"}
    if profile is QUALIFICATION or profile is STARTUP:
        keys.add("scope")
    require(type(allocation) is dict and set(allocation) == keys and type(allocation["schema"]) is int and
            allocation["schema"] == CLOCK_SCHEMA and allocation["clockDomain"] == CLOCK_DOMAIN and
            (profile is GENERATION or allocation["scope"] == profile.scope), "PREPARE", "ALLOCATION")
    require(allocation["source"] == github["source"] and allocation["sourceTree"] == github["sourceTree"] and
            allocation["runId"] == github["runId"] and allocation["runAttempt"] == github["runAttempt"],
            "PREPARE", "IDENTITY_CHANGED")
    require(all(type(value) is int and 0 < value <= UINT64 for value in
                (now_ns, wall_ns, allocation["startedMonotonicNs"], allocation["startedEpochNs"])), "PREPARE")
    elapsed = now_ns - allocation["startedMonotonicNs"]
    require(0 <= elapsed < profile.job_seconds * NS and
            abs((wall_ns - allocation["startedEpochNs"]) - elapsed) <= 60 * NS, "PREPARE", "TIMEOUT")
    return allocation["startedMonotonicNs"] + profile.job_seconds * NS


def validate_original_environment(profile, env):
    validate_profile(profile)
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPOSITORY and
            env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            env.get("GITHUB_JOB") == profile.job and env.get("GITHUB_ACTOR") == OWNER and
            env.get("GITHUB_ACTOR_ID") == OWNER_ID and env.get("GITHUB_TRIGGERING_ACTOR") == OWNER, "SOURCE")
    require(profile.ref.fullmatch(env.get("GITHUB_REF", "")) and
            env.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + profile.workflow + "@" + env["GITHUB_REF"] and
            SHA.fullmatch(env.get("GITHUB_SHA", "")) and env.get("GITHUB_WORKFLOW_SHA") == env["GITHUB_SHA"],
            "SOURCE", "IDENTITY_CHANGED")
    require(all(NUMBER.fullmatch(env.get(key, "")) for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")) and
            not any(name in env for name in OWNER_ENV), "SOURCE")
    request = parsed(env.get(profile.request_env, "").encode("utf-8"), 8192)
    if profile is GENERATION:
        keys = {"controller_sha", "controller_tree", "candidate_sha", "candidate_tree", "dependency_base_sha"}
        source_key, tree_key = "controller_sha", "controller_tree"
    else:
        require(profile is QUALIFICATION or profile is STARTUP, "SOURCE", "PROFILE")
        keys = {"source_sha", "source_tree"}
        source_key, tree_key = "source_sha", "source_tree"
    require(type(request) is dict and set(request) == keys and
            all(type(value) is str and SHA.fullmatch(value) for value in request.values()), "SOURCE", "REQUEST")
    source, tree = request[source_key], request[tree_key]
    require(source == env["GITHUB_SHA"], "SOURCE", "IDENTITY_CHANGED")
    # Compare the actual event's fields, not just an environment copy of inputs.
    event = parsed(read_file(physical(env["GITHUB_EVENT_PATH"]), FILE_BYTES), FILE_BYTES)
    require(type(event) is dict and event.get("inputs") == request, "SOURCE", "REQUEST")
    return {"repository": REPOSITORY, "workflow": profile.workflow, "job": profile.job, "ref": env["GITHUB_REF"],
            "source": source, "sourceTree": tree, "runId": env["GITHUB_RUN_ID"], "runAttempt": env["GITHUB_RUN_ATTEMPT"],
            "actor": OWNER, "actorId": OWNER_ID, "triggeringActor": OWNER}


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def child_environment(profile, operation, tools):
    """Literal allowed tool selection only; no copied hosted identity or secrets."""
    validate_profile(profile)
    if profile is GENERATION:
        tool_keys = set(TOOL_ENV)
    elif profile is STARTUP:
        tool_keys = set(STARTUP_TOOL_ENV)
    else:
        require(profile is QUALIFICATION, "IDENTITY", "PROFILE")
        tool_keys = set()
    require(type(tools) is dict and set(tools) == tool_keys, "IDENTITY")
    require(all(type(value) is str and value and len(value) <= 8192 and "\n" not in value and "\0" not in value
                for value in tools.values()), "IDENTITY")
    result = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(operation / "home"),
              "TMPDIR": str(operation / "tmp"), "LANG": "C", "LC_ALL": "C", "TZ": "UTC",
              "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
              "__CF_USER_TEXT_ENCODING": "0x" + format(os.getuid(), "X") + ":0:0",
              "DEVELOPER_DIR": "/Applications/Xcode_26.5.app/Contents/Developer",
              "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0"}
    if profile is GENERATION or profile is STARTUP:
        require(tools["DEVELOPER_DIR"] == result["DEVELOPER_DIR"], "IDENTITY")
        result.update(tools)
        result.update(XDG_CONFIG_HOME=str(operation / "home/config"), XDG_CACHE_HOME=str(operation / "home/cache"),
                      GNUPGHOME=str(operation / "home/gnupg"), GH_CONFIG_DIR=str(operation / "home/gh"),
                      KONAN_DATA_DIR=str(operation / "konan"), ANDROID_USER_HOME=str(operation / "android-user"))
    return result


def validate_private_environment(expected):
    require(not any(name in os.environ for name in OWNER_ENV), "IDENTITY", "ENCLOSING_OWNER")
    require(not any(name.startswith(("GITHUB_", "ACTIONS_", "DYLD_")) or name in
                    ("GH_TOKEN", "GITHUB_TOKEN", "PYTHONPATH", "PYTHONHOME", "BASH_ENV", "ENV", "JAVA_OPTS",
                     "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS")
                    for name in os.environ), "IDENTITY", "CREDENTIAL_BOUNDARY")
    require(all(os.environ.get(key) == value for key, value in expected.items()), "IDENTITY", "ENVIRONMENT")


_UNCLOSED_COMMANDS = []


def capture_fixed(argv, end_ns, env, *, input_raw=b"", stage="SOURCE"):
    """Small pipe mechanism used only by fixed source/OS argv below, not a CLI."""
    require(type(input_raw) is bytes and len(input_raw) <= FRAME_BYTES, stage, "BOUND")
    end_ns = min(end_ns, shared_raw_ns() + ADMIN_SECONDS * NS)
    left(end_ns, stage)
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=env, close_fds=True)
    streams, output, offset = [process.stdout, process.stderr], [bytearray(), bytearray()], 0
    try:
        # The actual child already exists: every post-Popen setup failure must
        # enter original-object quarantine, including nonblocking-pipe setup.
        for stream in (process.stdin, *streams):
            os.set_blocking(stream.fileno(), False)
        while streams or process.stdin is not None:
            timeout = min(0.05, left(end_ns, stage))
            writes = [process.stdin] if process.stdin is not None else []
            ready, writable, _ = select.select(streams, writes, [], timeout)
            if writable:
                if offset < len(input_raw):
                    offset += os.write(process.stdin.fileno(), input_raw[offset:])
                if offset == len(input_raw):
                    process.stdin.close()
                    process.stdin = None
            for stream in ready:
                data = os.read(stream.fileno(), 4096)
                index = 0 if stream is process.stdout else 1
                output[index].extend(data)
                require(sum(map(len, output)) <= STREAM_BYTES, stage, "BOUND")
                if not data:
                    streams.remove(stream)
                    stream.close()
        code = process.wait(timeout=left(end_ns, stage))
        left(end_ns, stage)
        return {"argv": list(argv), "code": code, "stdout": bytes(output[0]), "stderr": bytes(output[1]),
                "waited": True, "eof": True, "closed": True}
    except BaseException:
        # Keep unresolved original objects; do not PID-kill an unowned privileged
        # descendant or publish an optimistic close receipt.
        _UNCLOSED_COMMANDS.append({"process": process, "output": output, "stdinOffset": offset,
                                   "streams": streams, "argv": list(argv)})
        raise


def decode_exit_event(event, expected_pid):
    require(type(event) is dict and set(event) == {"ident", "filter", "flags", "fflags", "data"} and
            all(type(value) is int for value in event.values()) and type(expected_pid) is int and expected_pid > 0,
            "SERVICE_WAIT", "STATUS_MISSING")
    require(event["ident"] == expected_pid and event["filter"] == EVFILT_PROC and not event["flags"] & EV_ERROR and
            event["fflags"] & (NOTE_EXIT | NOTE_EXITSTATUS) == NOTE_EXIT | NOTE_EXITSTATUS,
            "SERVICE_WAIT", "STATUS_MISSING")
    raw = event["data"]
    require(0 <= raw <= 0xffff, "SERVICE_WAIT", "STATUS_UNEXPECTED")
    if os.WIFEXITED(raw):
        value, kind, code = os.WEXITSTATUS(raw), "EXITED", os.WEXITSTATUS(raw)
    elif os.WIFSIGNALED(raw):
        value, kind = os.WTERMSIG(raw), "SIGNALED"
        require(0 < value < 128, "SERVICE_WAIT", "STATUS_UNEXPECTED")
        code = -value
    else:
        raise ContextError("SERVICE_WAIT", "STATUS_UNEXPECTED")
    return {"rawStatus": raw, "kind": kind, "value": value, "popenCode": code}


class Darwin:
    """Direct original lifetimes only. This is deliberately not DarwinScope."""

    def __init__(self, *, role, observe_exit=True):
        require(role in ("F", "D", "P"), "IDENTITY")
        self.role = role
        require(platform.system() == "Darwin" and platform.machine() == "arm64", "IDENTITY", "UNSUPPORTED")
        # Reuse maintained native ABI types, not its marker-descendant owner.
        self.abi = sys.modules.get("audit_processes") or load_module("audit_processes", "scripts/audit_processes.py")
        a = self.abi
        require((ctypes.sizeof(a.DarwinIdentity), ctypes.sizeof(a.AuditToken)) == (192, 32), "IDENTITY", "UNSUPPORTED")
        self.proc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        self.system = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        self.proc.proc_pidinfo.argtypes, self.proc.proc_pidinfo.restype = [a.I32, a.I32, a.U64, a.PTR, a.I32], a.I32
        self.proc.proc_signal_with_audittoken.argtypes = [ctypes.POINTER(a.AuditToken), a.I32]
        self.proc.proc_signal_with_audittoken.restype = a.I32
        self.system.task_name_for_pid.argtypes = [a.U32, a.I32, ctypes.POINTER(a.U32)]
        self.system.task_name_for_pid.restype = a.I32
        self.system.task_info.argtypes = [a.U32, a.U32, a.PTR, ctypes.POINTER(a.U32)]
        self.system.task_info.restype = a.I32
        self.system.mach_port_deallocate.argtypes, self.system.mach_port_deallocate.restype = [a.U32, a.U32], a.I32
        self.self_port = a.U32.in_dll(self.system, "mach_task_self_").value
        self.system.sysctlbyname.argtypes = [ctypes.c_char_p, a.PTR, ctypes.POINTER(ctypes.c_size_t), a.PTR, ctypes.c_size_t]
        self.system.sysctlbyname.restype = a.I32
        self.kqueue, self.watched, self.events, self.closed = select.kqueue() if observe_exit else None, {}, {}, False
        self.registrations, self.attach_attempts, self.signals = {}, [], []
        self._tokens = {}  # Genuine opaque original tokens; never copied into DATA.

    def boot(self):
        raw, size = ctypes.create_string_buffer(128), ctypes.c_size_t(128)
        ctypes.set_errno(0)
        code = self.system.sysctlbyname(b"kern.bootsessionuuid", raw, ctypes.byref(size), None, 0)
        require(code == 0 and 1 < size.value <= 128, "IDENTITY", "UNSUPPORTED", errno_name(ctypes.get_errno()))
        value = raw.value.decode("ascii")
        require(re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", value), "IDENTITY", "UNSUPPORTED")
        return value.upper()

    def identity(self, pid):
        require(type(pid) is int and pid > 0 and not self.closed, "IDENTITY")
        value = self.abi.DarwinIdentity()
        ctypes.set_errno(0)
        got = self.proc.proc_pidinfo(pid, 18, 1, ctypes.byref(value), ctypes.sizeof(value))
        require(got == ctypes.sizeof(value) and value.bsd.pid == pid, "IDENTITY", "REFUSED", errno_name(ctypes.get_errno()))
        return {"pid": pid, "parentPid": value.bsd.ppid, "uniqueId": value.unique.uniqueid,
                "parentUniqueId": value.unique.parentuniqueid, "pidVersion": value.unique.pidversion,
                "startSeconds": value.bsd.startsec, "startMicroseconds": value.bsd.startusec,
                "uid": value.bsd.uid, "realUid": value.bsd.ruid, "savedUid": value.bsd.svuid,
                "gid": value.bsd.gid, "realGid": value.bsd.rgid, "savedGid": value.bsd.svgid,
                "status": value.bsd.status}

    def same(self, expected):
        actual = self.identity(expected["pid"])
        return same_identity(actual, expected)

    def token(self, identity):
        self.same(identity)
        a, port = self.abi, self.abi.U32()
        try:
            code = self.system.task_name_for_pid(self.self_port, identity["pid"], ctypes.byref(port))
            require(code == 0 and port.value != 0, "IDENTITY", "PERMISSION_DENIED", "UNKNOWN")
            token, count = a.AuditToken(), a.U32(8)
            code = self.system.task_info(port, 15, ctypes.byref(token), ctypes.byref(count))
            require(code == 0 and count.value == 8, "IDENTITY", "PERMISSION_DENIED", "UNKNOWN")
            self.same(identity)
            return token  # Opaque, original, in-process only; never serialized.
        finally:
            if port.value:
                require(self.system.mach_port_deallocate(self.self_port, port) == 0, "CLOSE", "RESOURCE_UNKNOWN")

    def peer(self, channel):
        pid_raw = channel.getsockopt(SOL_LOCAL, LOCAL_PEERPID, 4)
        require(len(pid_raw) == 4, "IDENTITY", "UNSUPPORTED")
        identity = self.identity(struct.unpack("=i", pid_raw)[0])
        peer_token = channel.getsockopt(SOL_LOCAL, LOCAL_PEERTOKEN, 32)
        require(len(peer_token) == 32 and bytes(self.token(identity)) == peer_token, "IDENTITY", "IDENTITY_CHANGED")
        self.same(identity)
        return identity

    def watch(self, identity):
        require(self.kqueue is not None and not self.closed, "ATTACH", "RESOURCE_UNKNOWN")
        self.same(identity)
        token = self.token(identity)
        require(identity["pid"] not in self.watched, "ATTACH", "IDENTITY_CHANGED")
        change = select.kevent(identity["pid"], filter=EVFILT_PROC, flags=EV_ADD | EV_ENABLE | EV_RECEIPT,
                               fflags=NOTE_EXIT | NOTE_EXITSTATUS)
        # Only one receipt can be returned here; an earlier watched process's
        # terminal event must not be silently consumed as registration DATA.
        started = shared_raw_ns()
        receipts = self.kqueue.control([change], 1, 0)
        returned = shared_raw_ns()
        observation = {"identity": dict(identity), "startedMonotonicNs": started, "returnedMonotonicNs": returned,
                       "requested": {"ident": identity["pid"], "filter": EVFILT_PROC,
                                     "flags": EV_ADD | EV_ENABLE | EV_RECEIPT, "fflags": NOTE_EXIT | NOTE_EXITSTATUS},
                       "receipts": [{key: int(getattr(row, key)) for key in ("ident", "filter", "flags", "fflags", "data")}
                                    for row in receipts]}
        self.attach_attempts.append(observation)
        require(len(receipts) == 1 and receipts[0].ident == identity["pid"] and receipts[0].filter == EVFILT_PROC and
                receipts[0].flags & EV_ERROR, "ATTACH", "RETURN_FAILED")
        require(receipts[0].data == 0, "ATTACH", "RETURN_FAILED", errno_name(receipts[0].data))
        self.same(identity)
        self.watched[identity["pid"]] = dict(identity)
        observation["recheckedMonotonicNs"] = shared_raw_ns()
        self.registrations[identity["pid"]] = observation
        self._tokens[identity["pid"]] = token

    def signal(self, identity, signum, end_ns):
        require(signum in (signal.SIGTERM, signal.SIGKILL), "CLOSE", "REFUSED")
        require(identity["pid"] in self._tokens and identity["pid"] in self.watched and
                identity["pid"] not in self.events, "CLOSE", "RESOURCE_UNKNOWN")
        same_identity(identity, self.watched[identity["pid"]])
        left(end_ns, "CLOSE")
        self.same(identity)
        return self._signal_return(identity, self._tokens[identity["pid"]], signum, end_ns, None)

    def _signal_return(self, identity, token, signum, end_ns, orphan):
        left(end_ns, "CLOSE")
        started = shared_raw_ns()
        code = self.proc.proc_signal_with_audittoken(ctypes.byref(token), signum)
        self.signals.append({"signaler": self.role, "observation": {"identity": dict(identity), "signal": int(signum),
                             "returnedCode": code, "startedMonotonicNs": started,
                             "returnedMonotonicNs": shared_raw_ns()}, "orphan": orphan})
        require(code == 0, "CLOSE", "RETURN_FAILED", errno_name(code))
        left(end_ns, "CLOSE")
        return code

    def signal_birth(self, identity, end_ns):
        """Strict failed-start cleanup only; no image refresh or PID fallback."""
        require(self.role == "D" and identity["pid"] not in self.watched, "CLOSE")
        token = self.token(identity)  # Refuses if the validated birth image changed.
        return self._signal_return(identity, token, signal.SIGTERM, end_ns, None)

    def signal_orphan(self, identity, service, original_session, end_ns):
        require(self.role == "F" and service["pid"] in self.watched and service["pid"] in self.events and
                identity["pid"] in self.watched and identity["pid"] in self._tokens and
                identity["pid"] not in self.events, "CLOSE", "RESOURCE_UNKNOWN")
        same_identity(service, self.watched[service["pid"]])
        same_identity(identity, self.watched[identity["pid"]])
        event = self.events[service["pid"]]  # The actual preattached original event, not caller DATA.
        left(end_ns, "CLOSE")
        actual = self.identity(identity["pid"])
        observed_session = session_record(identity)
        checked = shared_raw_ns()
        orphan = validate_orphan_identity(actual, identity, service, observed_session, original_session,
                                          event["observedRawNs"], checked)
        return self._signal_return(identity, self._tokens[identity["pid"]], signal.SIGTERM, end_ns, orphan)

    def wait(self, identities, end_ns):
        wanted = {value["pid"] for value in identities}
        require(wanted <= self.watched.keys(), "SERVICE_WAIT", "REFUSED")
        while not wanted <= self.events.keys():
            events = self.kqueue.control(None, 16, min(0.05, left(end_ns, "SERVICE_WAIT")))
            for event in events:
                require(event.ident in self.watched and event.ident not in self.events, "SERVICE_WAIT", "IDENTITY_CHANGED")
                row = {key: int(getattr(event, key)) for key in ("ident", "filter", "flags", "fflags", "data")}
                self.events[event.ident] = {"event": row, "status": decode_exit_event(row, event.ident),
                                           "observedRawNs": shared_raw_ns()}
        return {value["pid"]: self.events[value["pid"]] for value in identities}

    def poll(self):
        require(self.kqueue is not None and not self.closed, "SERVICE_WAIT", "RESOURCE_UNKNOWN")
        for event in self.kqueue.control(None, 16, 0):
            require(event.ident in self.watched and event.ident not in self.events, "SERVICE_WAIT", "IDENTITY_CHANGED")
            row = {key: int(getattr(event, key)) for key in ("ident", "filter", "flags", "fflags", "data")}
            self.events[event.ident] = {"event": row, "status": decode_exit_event(row, event.ident),
                                       "observedRawNs": shared_raw_ns()}

    def close(self):
        require(not self.closed, "CLOSE", "RESOURCE_UNKNOWN")
        if self.kqueue is not None:
            self.kqueue.close()
            require(self.kqueue.closed, "CLOSE", "RESOURCE_UNKNOWN")
        self._tokens.clear()
        self.closed = True


def admin_object_item(path, kind):
    return "OS_OBJECT" if path in (*OS_PARENTS, *OS_TOOLS) else "PRIVATE_DIRECTORY" if kind == "directory" else "PRIVATE_FILE"


def annotate_admin_return(error, return_site, case, result, *, ledger=False):
    error.details.update(returnSite=return_site, case=case, ledger=ledger, returnedCode=result["code"])


def parse_admin_metadata(raw, acl_raw, path, kind, *, mode=None, previous=None, size=None, expected_os_links=None):
    """Prospective BSD stat/ls parser; only an actual supported return qualifies."""
    require(type(raw) is bytes and type(acl_raw) is bytes and type(path) is str and
            0 < len(raw) <= 1024 and 0 < len(acl_raw) <= 4096, "ADMIN_CREATE", "BOUND")
    try:
        fields = raw.decode("ascii").strip().split(":")
        require(len(fields) == 9 and all(re.fullmatch(r"[0-9]+", value) for value in fields) and
                re.fullmatch(r"[0-7]+", fields[2]), "ADMIN_CREATE", "UNSUPPORTED")
        values = [int(value, 8 if index == 2 else 10) for index, value in enumerate(fields)]
        line = acl_raw.decode("ascii").splitlines()
    except (UnicodeError, ValueError):
        raise ContextError("ADMIN_CREATE", "UNSUPPORTED") from None
    keys = ("dev", "ino", "mode", "uid", "gid", "nlink", "size", "mtime", "ctime")
    value = dict(zip(keys, values))
    is_type = stat.S_ISDIR(value["mode"]) if kind == "directory" else stat.S_ISREG(value["mode"])
    require(kind in ("directory", "file"), "ADMIN_CREATE", "IDENTITY_CHANGED",
            admin_site="META_KIND", admin_item=admin_object_item(path, kind))
    require(is_type, "ADMIN_CREATE", "IDENTITY_CHANGED",
            admin_site="META_TYPE", admin_item=admin_object_item(path, kind))
    require(value["uid"] == 0, "ADMIN_CREATE", "IDENTITY_CHANGED",
            admin_site="META_OWNER", admin_item=admin_object_item(path, kind))
    require(0 <= value["gid"] < 2 ** 32, "ADMIN_CREATE", "IDENTITY_CHANGED",
            admin_site="META_GROUP", admin_item=admin_object_item(path, kind))
    require(value["ino"] > 0, "ADMIN_CREATE", "IDENTITY_CHANGED",
            admin_site="META_INODE", admin_item=admin_object_item(path, kind))
    require(not value["mode"] & 0o022, "ADMIN_CREATE", "IDENTITY_CHANGED",
            admin_site="META_WRITE_MODE", admin_item=admin_object_item(path, kind))
    require((kind == "directory" and expected_os_links is None) or (
                kind == "file" and (
                    (expected_os_links is None and value["nlink"] == 1) or (
                        path in OS_TOOLS and type(expected_os_links) is int and
                        expected_os_links > 0 and value["nlink"] == expected_os_links
                    )
                )
            ), "ADMIN_CREATE", "IDENTITY_CHANGED",
            admin_site="META_LINKS", admin_item=admin_object_item(path, kind))
    require(mode is None or stat.S_IMODE(value["mode"]) == mode, "ADMIN_CREATE", "IDENTITY_CHANGED",
            admin_site="META_EXACT_MODE", admin_item=admin_object_item(path, kind))
    # -e must produce exactly the one listing line, with neither '+' nor any ACL
    # entry. '@' alone denotes extended attributes, not an ACL grant.
    require(len(line) == 1 and line[0].endswith(" " + path) and
            re.fullmatch(r"[d-][rwxstST-]{9}@?", line[0].split()[0]), "ADMIN_CREATE", "UNSUPPORTED")
    require((line[0][0] == "d") == (kind == "directory"), "ADMIN_CREATE", "IDENTITY_CHANGED",
            admin_site="META_LIST_TYPE", admin_item=admin_object_item(path, kind))
    require(size is None or value["size"] == size, "ADMIN_CREATE", "IDENTITY_CHANGED",
            admin_site="META_SIZE", admin_item=admin_object_item(path, kind))
    if previous is not None:
        previous_field = None

        def previous_keys():
            nonlocal previous_field
            for previous_field in ("dev", "ino", "mode", "uid", "gid", "nlink"):
                yield previous_field

        require(all(value[key] == previous[key] for key in previous_keys()),
                "ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="META_PREVIOUS", admin_item=admin_object_item(path, kind),
                admin_field=previous_field)
    return value


def service_absent(result, label):
    require(re.fullmatch(r"p2pkit\.context\.[a-z0-9.]{1,110}", label), "BOOTSTRAP")
    expected = ('Could not find service "' + label + '" in domain for system\n').encode("ascii")
    require(type(result) is dict and type(result.get("code")) is int and 0 < result["code"] <= 255 and
            result.get("stdout") == b"" and result.get("stderr") in (expected, b"Bad request.\n" + expected) and
            all(result.get(key) is True for key in ("waited", "eof", "closed")), "BOOTSTRAP", "UNSUPPORTED")
    # No invented 113 (or generic nonzero) is absence proof. Keep the original
    # actual code/diagnostic in the private admin ledger for native inspection.
    return True


def parse_startup_registration(result, label, plist_path, arguments):
    """One exact registration's finite DATA, never a process identity or closure."""
    try:
        require(type(label) is str and re.fullmatch(r"p2pkit\.context\.[a-z0-9.]{1,110}", label) and
                type(plist_path) is str and re.fullmatch(
                    r"/private/var/db/p2pkit-context\.[A-Za-z0-9]{10}/job\.plist", plist_path) and
                type(arguments) is list and len(arguments) == 1 and type(arguments[0]) is str and
                arguments[0] == plist_path.rsplit("/", 1)[0] + "/launcher", "START", "DIAGNOSTIC_REGISTRATION")
        require(type(result) is dict and all(type(key) is str for key in result) and
                set(result) == {"argv", "code", "stdout", "stderr", "waited", "eof", "closed"} and
                type(result["argv"]) is list and all(type(item) is str for item in result["argv"]) and
                result["argv"] == ["/usr/bin/sudo", "-n", "--", "/bin/launchctl", "print", "system/" + label] and
                type(result["code"]) is int and -127 <= result["code"] <= 255 and
                all(type(result[name]) is bytes for name in ("stdout", "stderr")) and
                len(result["stdout"]) + len(result["stderr"]) <= STREAM_BYTES and
                all(result[name] is True for name in ("waited", "eof", "closed")), "START", "DIAGNOSTIC_REGISTRATION")
        if result["code"] != 0 or result["stderr"]:
            try:
                service_absent(result, label)
            except ContextError:
                return "PRINT_FAILED", "NONE"
            return "REGISTRATION_ABSENT", "NONE"
        raw = result["stdout"]
        require(raw and all(byte in (9, 10) or 32 <= byte <= 126 for byte in raw),
                "START", "DIAGNOSTIC_REGISTRATION")
        lines = raw.decode("ascii").splitlines()
        require(lines and lines[0] == "system/" + label + " = {" and lines[-1] == "}",
                "START", "DIAGNOSTIC_REGISTRATION")
        depth, fields, argv, in_arguments = 1, {}, [], False
        for original in lines[1:]:
            line = original.strip()
            if not line:
                continue
            require(depth >= 1, "START", "DIAGNOSTIC_REGISTRATION")
            require(("{" not in line and "}" not in line) or line == "}" or
                    (line.endswith(" = {") and line.count("{") == 1 and "}" not in line),
                    "START", "DIAGNOSTIC_REGISTRATION")
            if in_arguments:
                if line == "}":
                    in_arguments = False
                else:
                    require(depth == 2 and "{" not in line and "}" not in line and len(argv) < 8,
                            "START", "DIAGNOSTIC_REGISTRATION")
                    argv.append(line)
            elif depth == 1 and line != "}":
                require(" = " in line, "START", "DIAGNOSTIC_REGISTRATION")
                key, value = line.split(" = ", 1)
                require(key and key not in fields, "START", "DIAGNOSTIC_REGISTRATION")
                fields[key] = value
                if key == "arguments":
                    require(value == "{", "START", "DIAGNOSTIC_REGISTRATION")
                    in_arguments = True
            depth += line.count("{") - line.count("}")
            require(0 <= depth <= 8, "START", "DIAGNOSTIC_REGISTRATION")
        require(depth == 0 and not in_arguments and fields.get("path") == plist_path and
                fields.get("type") == "LaunchDaemon" and fields.get("program") == arguments[0] and
                argv == arguments and type(fields.get("state")) is str and fields["state"] not in ("", "{") and
                fields.get("last exit code") != "{",
                "START", "DIAGNOSTIC_REGISTRATION")
        status = {"running": "RUNNING", "not running": "NOT_RUNNING", "spawn scheduled": "SPAWN_SCHEDULED",
                  "waiting": "WAITING"}.get(fields.get("state"), "UNSUPPORTED")
        code = fields.get("last exit code")
        if code in (None, "(never exited)"):
            code = "NONE"
        elif re.fullmatch(r"0|[1-9][0-9]{0,2}", code) is not None and int(code) <= 255:
            code = "CODE_" + code
        else:
            code = "UNSUPPORTED"
        return status, code
    except (ContextError, UnicodeError):
        return "INVALID", "NONE"


def parse_service_print(raw, label, plist_path, arguments, expected_pid, *, running=True):
    require(type(raw) is bytes and 0 < len(raw) <= STREAM_BYTES and type(arguments) is list and
            all(type(value) is str and value and "\n" not in value for value in arguments), "BOOTSTRAP", "BOUND")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeError:
        raise ContextError("BOOTSTRAP", "UNSUPPORTED") from None
    target = "system/" + label
    require(lines and lines[0] == target + " = {" and lines[-1] == "}", "BOOTSTRAP", "UNSUPPORTED")
    depth, fields, argv, in_arguments = 1, {}, [], False
    for original in lines[1:]:
        line = original.strip()
        if not line:
            continue
        require(depth >= 1, "BOOTSTRAP", "UNSUPPORTED")
        if in_arguments:
            if line == "}":
                in_arguments = False
            else:
                require(depth == 2 and "{" not in line and "}" not in line and len(argv) < 8,
                        "BOOTSTRAP", "UNSUPPORTED")
                argv.append(line)
        elif depth == 1 and line != "}":
            require(" = " in line, "BOOTSTRAP", "UNSUPPORTED")
            key, value = line.split(" = ", 1)
            require(key not in fields, "BOOTSTRAP", "IDENTITY_CHANGED")
            fields[key] = value
            if key == "arguments":
                require(value == "{", "BOOTSTRAP", "UNSUPPORTED")
                in_arguments = True
        depth += line.count("{") - line.count("}")
        require(0 <= depth <= 8, "BOOTSTRAP", "BOUND")
    require(depth == 0 and not in_arguments and fields.get("path") == plist_path and
            fields.get("type") == "LaunchDaemon" and fields.get("program") == arguments[0] and argv == arguments,
            "BOOTSTRAP", "IDENTITY_CHANGED")
    require(type(expected_pid) is int and expected_pid > 0, "BOOTSTRAP", "IDENTITY_CHANGED")
    if running:
        require(fields.get("state") == "running" and fields.get("pid") == str(expected_pid),
                "BOOTSTRAP", "IDENTITY_CHANGED")
    else:
        require(fields.get("state") == "not running" and fields.get("pid") in (None, str(expected_pid)),
                "RETIRE", "IDENTITY_CHANGED")
    return {"target": target, "path": fields["path"], "program": fields["program"], "arguments": argv,
            "state": fields["state"], "pid": expected_pid if "pid" in fields else None}


def safe_component_path(path):
    value = os.fspath(path)
    require(type(value) is str and re.fullmatch(r"/[A-Za-z0-9_@./-]+", value) and
            str(Path(value)) == value and ".." not in Path(value).parts and not value.startswith("//"),
            "IDENTITY", "REFUSED")
    return value


def service_arguments(profile, interpreter, directory):
    validate_profile(profile)
    return [safe_component_path(interpreter), "-I", "-B", "-S", safe_component_path(ROOT / profile.script),
            "_service", safe_component_path(directory)]


def launcher_header(context, directory):
    """Compile-time DATA only; no privileged runtime argv/configuration selector."""
    validate_account(context.account)
    require(context.account == account(), "IDENTITY", "IDENTITY_CHANGED")

    def literal(value):
        require(type(value) is str and len(value) <= 8192 and
                not any(ord(char) < 32 or ord(char) == 127 for char in value), "SOURCE", "BOUND")
        return '"' + "".join("\\%03o" % byte for byte in value.encode("utf-8")) + '"'

    arguments = service_arguments(context.profile, context.interpreter["path"], directory)
    environment = child_environment(context.profile, context.operation, context.tools)
    require(len(arguments) == 7 and all(re.fullmatch(r"[A-Z_][A-Z0-9_]*", key) for key in environment),
            "SOURCE", "REFUSED")
    rows = ["/* Generated closed configuration, never read by a privileged process. */",
            "#define P2PKIT_UID ((uid_t)" + str(context.account["uid"]) + "U)",
            "#define P2PKIT_GID ((gid_t)" + str(context.account["gid"]) + "U)",
            "#define P2PKIT_GROUP_COUNT " + str(len(context.account["groups"])),
            "static const gid_t P2PKIT_GROUPS[256] = {" +
            (", ".join("(gid_t)" + str(value) + "U" for value in context.account["groups"]) or "0") + "};",
            "static const char P2PKIT_SOURCE_DIRECTORY[] = " + literal(safe_component_path(ROOT)) + ";",
            "static char *const P2PKIT_D_ARGV[] = {" + ", ".join(map(literal, arguments)) + ", NULL};",
            "static char *const P2PKIT_D_ENV[] = {" +
            ", ".join(literal(key + "=" + environment[key]) for key in sorted(environment)) + ", NULL};"]
    raw = ("\n".join(rows) + "\n").encode("ascii")
    require(0 < len(raw) <= STREAM_BYTES, "SOURCE", "BOUND")
    return raw


def _launcher_require(value, role, chain, node, predicate):
    """Label an existing failed predicate without another filesystem observation."""
    if not value:
        raise ContextError("SOURCE", "LAUNCHER_ROOT_INPUT", "NONE", launcher_role=role, launcher_chain=chain,
                           launcher_node=node, launcher_predicate=predicate)


def _launcher_node(index):
    # The label is bounded; traversal and every original check remain unbounded
    # by this diagnostic-only index. No path text is used as a public label.
    return LAUNCHER_NODES[index] if type(index) is int and 0 <= index <= 32 else "DEEPER"


def launcher_root_path(value, *, directory=False, role="ROOT_FILE"):
    """Root inputs must actually be immutable to the original nonroot F.

    SDK aliases may be root-owned links. Check both lexical and resolved parent
    chains, including ACL-effective write access; never accept a writable alias
    or merely trust the protected /usr/bin/clang selection shim.
    """
    original = Path(safe_component_path(value))
    resolved = original.resolve(strict=True)
    nodes = {}
    for chain, paths in (("LEXICAL", (original, *original.parents)), ("RESOLVED", (resolved, *resolved.parents))):
        for index, path in enumerate(paths):
            nodes.setdefault(path, (chain, _launcher_node(index)))
    for path, (chain, node) in nodes.items():
        info = path.lstat()
        _launcher_require(info.st_uid == 0, role, chain, node, "OWNER")
        _launcher_require(stat.S_ISLNK(info.st_mode) or not info.st_mode & 0o022, role, chain, node, "MODE")
        _launcher_require(not os.access(path, os.W_OK), role, chain, node, "WRITE_ACCESS")
        _launcher_require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode),
                          role, chain, node, "PATH_TYPE")
    resolved = physical(resolved)
    info = resolved.lstat()
    _launcher_require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),
                      role, "RESOLVED", "SELF", "DIRECTORY_TYPE" if directory else "FILE_TYPE")
    return resolved


def launcher_root_pin(value, maximum, end_ns, *, executable=False, role="ROOT_FILE"):
    path = launcher_root_path(value, role=role)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        before = os.fstat(stream.fileno())
        stamp = lambda info: [info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
                              info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
        _launcher_require(stat.S_ISREG(before.st_mode), role, "RESOLVED", "SELF", "PIN_TYPE")
        _launcher_require(before.st_uid == 0, role, "RESOLVED", "SELF", "PIN_OWNER")
        _launcher_require(before.st_nlink > 0, role, "RESOLVED", "SELF", "LINK_COUNT")
        _launcher_require(0 < before.st_size, role, "RESOLVED", "SELF", "SIZE_POSITIVE")
        _launcher_require(before.st_size <= maximum, role, "RESOLVED", "SELF", "SIZE_MAXIMUM")
        _launcher_require(not executable or os.access(path, os.X_OK), role, "RESOLVED", "SELF", "EXEC_ACCESS")
        checksum, size = hashlib.sha256(), 0
        while True:
            left(end_ns, "SOURCE")
            block = stream.read(65536)
            if not block:
                break
            size += len(block)
            require(size <= maximum, "SOURCE", "BOUND")
            checksum.update(block)
        require(size == before.st_size and stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()) and
                launcher_root_path(value, role=role) == path, "SOURCE", "IDENTITY_CHANGED")
    return {"path": str(path), "stat": stamp(before), "size": size, "sha256": checksum.hexdigest()}


def launcher_dependencies(raw, directory, sdk, resource):
    """Only the two fixed private inputs and actual root SDK/resource headers."""
    require(type(raw) is bytes and 0 < len(raw) <= STREAM_BYTES, "SOURCE", "BOUND")
    text = raw.decode("ascii").replace("\\\n", "")
    require(text.startswith("p2pkit-launcher:") and "\\" not in text, "SOURCE", "LAUNCHER_DEPENDENCIES")
    paths = [Path(safe_component_path(name)) for name in text[len("p2pkit-launcher:"):].split()]
    require(2 <= len(paths) <= 256 and len(paths) == len(set(paths)), "SOURCE", "LAUNCHER_DEPENDENCIES")
    local = {directory / "launcher.c", directory / LAUNCHER_HEADER}
    require(local <= set(paths), "SOURCE", "LAUNCHER_DEPENDENCIES")
    for path in set(paths) - local:
        path = launcher_root_path(path, role="DEPENDENCY")
        require(sdk in path.parents or resource in path.parents, "SOURCE", "LAUNCHER_DEPENDENCIES")
    return sorted(map(str, paths))


def _launcher_macho_require(value, predicate):
    """Name only an existing failed grammar site, never any observed binary data."""
    if not value:
        raise ContextError("SOURCE", "LAUNCHER_MACHO", "NONE", launcher_macho_predicate=predicate)


def _launcher_library_names(system_pin, proc_pin):
    """Derive one exact library set from the two original complete SDK input pins."""
    try:
        for pin in (system_pin, proc_pin):
            require(type(pin) is dict and all(type(key) is str for key in pin) and
                    set(pin) == {"path", "stat", "size", "sha256"}, "SOURCE", "LAUNCHER_LIBRARY_INPUT")
            require(type(pin["path"]) is str, "SOURCE", "LAUNCHER_LIBRARY_INPUT")
            safe_component_path(pin["path"])
            stamp = pin["stat"]
            require(type(stamp) is list and len(stamp) == 9 and all(type(value) is int for value in stamp),
                    "SOURCE", "LAUNCHER_LIBRARY_INPUT")
            require(stat.S_ISREG(stamp[2]) and not stamp[2] & 0o022 and stamp[3] == 0 and stamp[5] > 0 and
                    type(pin["size"]) is int and 0 < pin["size"] <= FILE_BYTES and pin["size"] == stamp[6] and
                    type(pin["sha256"]) is str and HASH.fullmatch(pin["sha256"]), "SOURCE", "LAUNCHER_LIBRARY_INPUT")
        system_record, proc_record = encoded(system_pin), encoded(proc_pin)
    except (ContextError, OverflowError):
        raise ContextError("SOURCE", "LAUNCHER_LIBRARY_INPUT") from None
    if system_pin["path"] == proc_pin["path"]:
        require(system_record == proc_record, "SOURCE", "LAUNCHER_LIBRARY_INPUT")
        return {b"/usr/lib/libSystem.B.dylib"}
    return {b"/usr/lib/libSystem.B.dylib", b"/usr/lib/libproc.dylib"}


def inspect_launcher_macho(raw, *, system_pin, proc_pin):
    """Bounded ARM64 executable grammar: OS loader/libSystem/libproc only."""
    _launcher_macho_require(type(raw) is bytes and 32 <= len(raw) <= STREAM_BYTES, "INPUT_BOUND")
    magic, cpu, subtype, kind, count, size, flags, reserved = struct.unpack_from("<8I", raw)
    _launcher_macho_require((magic, cpu, subtype, kind, reserved) == (0xfeedfacf, 0x0100000c, 0, 2, 0) and
            1 <= count <= 64 and 0 < size <= len(raw) - 32 and flags & 0x200085 == 0x200085 and
            not flags & 0x20000, "HEADER")
    # Unknown, weak/reexport/upward dylibs, LC_RPATH and LC_DYLD_ENVIRONMENT fail.
    admitted = {0x19, 0x2, 0xb, 0xe, 0x1b, 0x32, 0x2a, 0x80000028, 0xc,
                0x26, 0x29, 0x1d, 0x80000034, 0x80000033, 0x80000022, 0x2e}
    offset, commands, libraries, loader, entry, text_segment, build = 32, [], [], None, None, None, None
    for _ in range(count):
        _launcher_macho_require(offset + 8 <= 32 + size, "COMMAND_HEADER")
        command, length = struct.unpack_from("<2I", raw, offset)
        _launcher_macho_require(command in admitted and length >= 8 and length % 8 == 0 and offset + length <= 32 + size,
                                "COMMAND_SHAPE")
        data = raw[offset:offset + length]
        commands.append(command)
        if command in (0xc, 0xe):
            _launcher_macho_require(length >= (32 if command == 0xc else 16), "NAME_COMMAND_SIZE")
            name_offset = struct.unpack_from("<I", data, 8)[0]
            _launcher_macho_require(name_offset == (24 if command == 0xc else 12) and name_offset < length and
                                    b"\0" in data[name_offset:], "NAME_OFFSET_TERMINATOR")
            name, tail = data[name_offset:].split(b"\0", 1)
            _launcher_macho_require(not any(tail), "NAME_PADDING")
            if command == 0xc:
                _launcher_macho_require(name in (b"/usr/lib/libSystem.B.dylib", b"/usr/lib/libproc.dylib") and
                                        name not in libraries, "DYLIB_NAME")
                libraries.append(name)
            else:
                _launcher_macho_require(loader is None and name == b"/usr/lib/dyld", "LOADER_NAME")
                loader = name
        elif command == 0x19:
            _launcher_macho_require(length >= 72, "SEGMENT_SIZE")
            segment, _vmaddr, _vmsize, file_offset, file_size, maxprot, initprot, sections, _segment_flags = \
                struct.unpack_from("<16s4Q4I", data, 8)
            _launcher_macho_require(length == 72 + 80 * sections and file_offset + file_size <= len(raw) and
                                    not (initprot | maxprot) & ~7 and initprot & 6 != 6, "SEGMENT_SHAPE")
            if segment.rstrip(b"\0") == b"__TEXT":
                _launcher_macho_require(text_segment is None and file_offset == 0 and initprot == 5, "TEXT_SEGMENT")
                text_segment = (file_offset, file_size)
        elif command == 0x80000028:
            _launcher_macho_require(entry is None and length == 24, "ENTRY_COMMAND")
            entry, stack_size = struct.unpack_from("<2Q", data, 8)
            _launcher_macho_require(stack_size == 0, "ENTRY_STACK")
        elif command == 0x32:
            _launcher_macho_require(build is None and length >= 24, "BUILD_COMMAND")
            platform_id, minimum, sdk_version, tools = struct.unpack_from("<4I", data, 8)
            _launcher_macho_require(platform_id == 1 and minimum == (26 << 16) and sdk_version >= minimum and
                                    length == 24 + 8 * tools, "BUILD_TARGET")
            build = {"platform": platform_id, "minimum": minimum, "sdk": sdk_version}
        elif command in (0x26, 0x29, 0x1d, 0x80000034, 0x80000033, 0x2e):
            _launcher_macho_require(length == 16, "DATA_COMMAND_SIZE")
            position, amount = struct.unpack_from("<2I", data, 8)
            _launcher_macho_require(position + amount <= len(raw), "DATA_RANGE")
        elif command == 0x2:
            _launcher_macho_require(length == 24, "SYMBOL_COMMAND_SIZE")
            symbols, symbol_count, strings, string_size = struct.unpack_from("<4I", data, 8)
            _launcher_macho_require(symbols + symbol_count * 16 <= len(raw) and strings + string_size <= len(raw),
                                    "SYMBOL_RANGES")
        else:
            _launcher_macho_require(length == {0xb: 80, 0x1b: 24, 0x2a: 16, 0x80000022: 48}[command],
                                    "FIXED_COMMAND_SIZE")
        offset += length
    _launcher_macho_require(offset == 32 + size, "COMMANDS_END")
    _launcher_macho_require(loader == b"/usr/lib/dyld", "LOADER_PRESENT")
    _launcher_macho_require(set(libraries) == _launcher_library_names(system_pin, proc_pin), "LIBRARY_SET")
    _launcher_macho_require(text_segment is not None, "TEXT_PRESENT")
    _launcher_macho_require(entry is not None, "ENTRY_PRESENT")
    _launcher_macho_require(32 + size <= entry < text_segment[1], "ENTRY_RANGE")
    _launcher_macho_require(build is not None, "BUILD_PRESENT")
    _launcher_macho_require(commands.count(0x1d) == 1, "SIGNATURE_COUNT")
    return {"format": "MACH_O_ARM64_EXECUTE", "bytes": len(raw), "sha256": digest(raw),
            "loader": loader.decode("ascii"), "libraries": sorted(value.decode("ascii") for value in libraries),
            "commands": commands, "build": build}


def prepare_launcher(context, directory, end_ns):
    """One nonroot dependency preflight and compile, inside the original case end.

    The compiler's actual root-only SDK/resource headers are pinned on both sides
    of compilation, not merely a shim or an expected hash regenerated for green.
    The product remains a fixed <=64KiB byte object; root never copies this path.
    """
    validate_account(context.account, account())
    context.native.same(context.foreground_identity)
    check_source_files(context.profile, context.source)
    require(not any(os.path.lexists(directory / name) for name in LAUNCHER_FILES), "SOURCE", "REFUSED")
    source = read_file(ROOT / LAUNCHER_SOURCE, STREAM_BYTES)
    require(digest(source) == context.source["files"][LAUNCHER_SOURCE], "SOURCE", "IDENTITY_CHANGED")
    header = launcher_header(context, directory)
    write_new(directory / "launcher.c", source)
    write_new(directory / LAUNCHER_HEADER, header)
    compiler = launcher_root_path(LAUNCHER_TOOLCHAIN + "/usr/bin/clang", role="COMPILER")
    linker = launcher_root_path(LAUNCHER_TOOLCHAIN + "/usr/bin/ld", role="LINKER")
    sdk = launcher_root_path(LAUNCHER_SDK, directory=True, role="SDK")
    # Installed compiler/linker input bounds, not a change to product/stream caps.
    tool_roles = {str(compiler): "COMPILER", str(linker): "LINKER"}
    tool_pins = {str(path): launcher_root_pin(path, 512 * 1024 * 1024, end_ns, executable=True, role=role)
                 for path, role in ((compiler, "COMPILER"), (linker, "LINKER"))}
    environment = {**context.os_env, "DEVELOPER_DIR": LAUNCHER_TOOLCHAIN,
                   "HOME": str(context.operation / "home"), "TMPDIR": str(context.operation / "tmp")}
    returns = []

    def command(argv):
        left(end_ns, "SOURCE")
        require(len(returns) < 3, "SOURCE", "BOUND")
        started = shared_raw_ns()
        returned = capture_fixed(argv, end_ns, environment)
        row = {**returned, "stdout": returned["stdout"].hex(), "stderr": returned["stderr"].hex(),
               "startedRawNs": started, "returnedRawNs": shared_raw_ns()}
        returns.append(row)
        write_new(directory / ("launcher-command-" + str(len(returns)) + ".json"), encoded(row))
        require(returned["code"] == 0 and not returned["stderr"] and
                all(returned[key] is True for key in ("waited", "eof", "closed")), "SOURCE", "LAUNCHER_COMPILER")
        return returned

    resource_raw = command([str(compiler), "--no-default-config", "-print-resource-dir"])["stdout"]
    require(resource_raw.endswith(b"\n") and resource_raw.count(b"\n") == 1, "SOURCE", "LAUNCHER_TOOLCHAIN")
    resource = launcher_root_path(resource_raw[:-1].decode("ascii"), directory=True, role="RESOURCE")
    require(Path(LAUNCHER_TOOLCHAIN).resolve(strict=True) in resource.parents, "SOURCE", "LAUNCHER_TOOLCHAIN")
    common = [str(compiler), "--no-default-config", "-arch", "arm64", "-std=c11", "-O2", "-Wall", "-Wextra",
              "-Werror", "-fstack-protector-strong", "-fno-modules", "-fno-implicit-modules",
              "-mmacosx-version-min=26.0", "-isysroot", str(sdk), "-resource-dir", str(resource)]
    before_dep = directory / "launcher-dependencies.before.d"
    after_dep = directory / "launcher-dependencies.after.d"
    product = directory / "launcher.bin"
    command([*common, "-M", "-MF", str(before_dep), "-MT", "p2pkit-launcher", str(directory / "launcher.c")])
    before_raw = read_file(before_dep)
    paths = launcher_dependencies(before_raw, directory, sdk, resource)
    local = {str(directory / "launcher.c"), str(directory / LAUNCHER_HEADER)}
    root_paths = sorted(set(paths) - local | {str(sdk / "usr/lib/libSystem.tbd"), str(sdk / "usr/lib/libproc.tbd")})
    library_roles = {str(sdk / "usr/lib/libSystem.tbd"): "LIBSYSTEM", str(sdk / "usr/lib/libproc.tbd"): "LIBPROC"}
    root_pins = {path: launcher_root_pin(path, FILE_BYTES, end_ns, role=library_roles.get(path, "DEPENDENCY"))
                 for path in root_paths}
    require(sum(value["size"] for value in root_pins.values()) <= FILE_BYTES, "SOURCE", "BOUND")
    command([*common, "--ld-path=" + str(linker), "-Wl,-fatal_warnings", "-MD", "-MF", str(after_dep),
             "-MT", "p2pkit-launcher", "-o", str(product), str(directory / "launcher.c"), "-lproc"])
    after_raw = read_file(after_dep)
    require(launcher_dependencies(after_raw, directory, sdk, resource) == paths and
            read_file(directory / "launcher.c") == source and read_file(directory / LAUNCHER_HEADER) == header and
            launcher_header(context, directory) == header, "SOURCE", "IDENTITY_CHANGED")
    for path, pin in root_pins.items():
        require(launcher_root_pin(path, FILE_BYTES, end_ns, role=library_roles.get(path, "DEPENDENCY")) == pin,
                "SOURCE", "IDENTITY_CHANGED")
    for path, pin in tool_pins.items():
        require(launcher_root_pin(path, 512 * 1024 * 1024, end_ns, executable=True, role=tool_roles[path]) == pin,
                "SOURCE", "IDENTITY_CHANGED")
    require(launcher_root_path(LAUNCHER_SDK, directory=True, role="SDK") == sdk and
            launcher_root_path(str(resource), directory=True, role="RESOURCE") == resource, "SOURCE", "IDENTITY_CHANGED")
    binary = read_file(product)
    inspection = inspect_launcher_macho(binary, system_pin=root_pins[str(sdk / "usr/lib/libSystem.tbd")],
                                        proc_pin=root_pins[str(sdk / "usr/lib/libproc.tbd")])
    # Compilation is nonroot; the retained copy is DATA, never locally executed.
    for path in (before_dep, after_dep, product):
        os.chmod(physical(path), 0o600)
    require(read_file(product) == binary and read_file(before_dep) == before_raw and read_file(after_dep) == after_raw,
            "SOURCE", "IDENTITY_CHANGED")
    check_source_files(context.profile, context.source)
    context.native.same(context.foreground_identity)
    write_new(directory / "launcher.json", encoded({"schema": 1, "scope": "FIXED_NATIVE_DAEMON_PRELUDE_INPUTS_V1",
              "source": context.source, "account": context.account, "sourceSha256": digest(source),
              "headerSha256": digest(header), "sdk": str(sdk), "resource": str(resource), "tools": tool_pins,
              "rootInputs": root_pins, "dependencyBeforeSha256": digest(before_raw),
              "dependencyAfterSha256": digest(after_raw), "commands": returns, "inspection": inspection,
              "qualification": "NOT_PERFORMED"}))
    left(end_ns, "SOURCE")
    return binary


def service_plist(context, label, directory, launcher):
    require(re.fullmatch(r"p2pkit\.context\.[a-z0-9.]{1,110}", label) and
            all(type(value) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", value)
                for value in (context.username, context.groupname)), "ADMIN_CREATE")
    require(re.fullmatch(r"/private/var/db/p2pkit-context\.[A-Za-z0-9]{10}/launcher", launcher), "ADMIN_CREATE")
    value = {"Label": label, "ProgramArguments": [launcher], "RunAtLoad": True,
             "KeepAlive": False, "AbandonProcessGroup": False, "WorkingDirectory": "/",
             "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"},
             "StandardInPath": "/dev/null", "StandardOutPath": "/dev/null", "StandardErrorPath": "/dev/null"}
    raw = plistlib.dumps(value, fmt=plistlib.FMT_XML, sort_keys=True)
    require(0 < len(raw) <= FRAME_BYTES, "ADMIN_CREATE", "BOUND")
    return raw


class Admin:
    """One original root-private plist/launcher/registration; no public selector."""

    def __init__(self, context, directory, label, end_ns):
        self.context, self.directory, self.label, self.end_ns = context, directory, label, end_ns
        self.arguments, self.plist = None, None
        self.root, self.path, self.root_meta, self.file_meta, self.service = None, None, None, None, None
        self.launcher, self.launcher_meta, self.launcher_bytes, self.launcher_offset = None, None, None, 0
        self.root_populated_meta = None
        self.bootstrapped, self.retired, self.removed, self.closed = False, False, False, False
        self.calls, self.written = 0, 0
        self.record = os.fdopen(os.open(directory / "admin.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                       0o600), "wb")

    def _allowed(self, argv, input_raw):
        metadata_paths = {*OS_PARENTS, *OS_TOOLS}
        metadata_paths.update(value for value in (self.root, self.path, self.launcher) if value is not None)
        exact = [["/usr/bin/mktemp", "-d", ROOT_TEMPLATE]] if self.root is None else []
        if self.root is not None and self.path is None:
            exact.append(["/usr/bin/mktemp", self.root + "/job.plist"])
        if self.path is not None and self.launcher is None:
            exact.append(["/usr/bin/mktemp", self.root + "/launcher"])
        if self.path is not None:
            exact.extend((["/bin/cat", self.path], ["/usr/bin/tee", self.path],
                          ["/bin/launchctl", "bootstrap", "system", self.path], ["/bin/rm", self.path]))
        if self.launcher is not None:
            exact.extend((["/bin/cat", self.launcher], ["/bin/rm", self.launcher]))
            if self.launcher_bytes is not None and self.launcher_offset < len(self.launcher_bytes):
                exact.append(["/usr/bin/tee", *(["-a"] if self.launcher_offset else []), self.launcher])
            if self.launcher_bytes is not None and self.launcher_offset == len(self.launcher_bytes):
                exact.append(["/bin/chmod", "700", self.launcher])
        if self.root is not None:
            exact.append(["/bin/rmdir", self.root])
            if self.path is not None:
                exact.append(["/bin/ls", "-1A", self.root])
        exact.append(["/bin/launchctl", "print", "system/" + self.label])
        if self.service is not None:
            exact.append(["/bin/launchctl", "bootout", "system/" + self.label])
        metadata = (len(argv) == 4 and argv[:3] == ["/usr/bin/stat", "-f", STAT_FORMAT] and argv[3] in metadata_paths or
                    len(argv) == 3 and argv[:2] == ["/bin/ls", "-lde"] and argv[2] in metadata_paths)
        require(argv in exact or metadata, "ADMIN_CREATE", "REFUSED")
        if argv[:1] == ["/usr/bin/tee"]:
            if argv == ["/usr/bin/tee", self.path]:
                require(type(self.plist) is bytes and input_raw == self.plist and self.file_meta is not None,
                        "ADMIN_CREATE", "REFUSED")
            else:
                require(self.launcher_meta is not None and type(self.launcher_bytes) is bytes and
                        input_raw == self.launcher_bytes[self.launcher_offset:self.launcher_offset + FRAME_BYTES] and
                        0 < len(input_raw) <= FRAME_BYTES, "ADMIN_CREATE", "REFUSED")
        else:
            require(input_raw == b"", "ADMIN_CREATE", "REFUSED")

    def _run(self, argv, stage, *, input_raw=b"", success=True, return_site=None):
        self._allowed(argv, input_raw)
        require(not self.closed and self.calls < ADMIN_CALL_LIMIT and not _UNCLOSED_COMMANDS, stage, "RESOURCE_UNKNOWN")
        self.calls += 1
        started = shared_raw_ns()
        with at_stage(stage):
            result = capture_fixed(["/usr/bin/sudo", "-n", "--", *argv], self.end_ns,
                                   self.context.os_env, input_raw=input_raw, stage=stage)
        returned = shared_raw_ns()
        row = {"schema": 1, "ordinal": self.calls, "argv": result["argv"], "code": result["code"],
               "stdoutHex": result["stdout"].hex(), "stderrHex": result["stderr"].hex(),
               "stdinSha256": digest(input_raw), "stdinSize": len(input_raw),
               "startedMonotonicNs": started, "returnedMonotonicNs": returned,
               "waited": result["waited"], "eof": result["eof"], "closed": result["closed"]}
        raw = encoded(row)
        self.written += len(raw)
        require(self.written <= EVIDENCE_BYTES // 4, stage, "BOUND")
        try:
            require(self.record.write(raw) == len(raw), stage, "RETURN_FAILED")
        except ContextError as error:
            annotate_admin_return(error, return_site, self.directory.name, result, ledger=True)
            raise
        self.record.flush()
        os.fsync(self.record.fileno())
        require(all(result[key] is True for key in ("waited", "eof", "closed")), stage, "RESOURCE_UNKNOWN")
        if success:
            try:
                require(result["code"] == 0 and result["stderr"] == b"", stage, "RETURN_FAILED")
            except ContextError as error:
                annotate_admin_return(error, return_site, self.directory.name, result)
                raise
        return result

    def metadata(self, path, kind, *, mode=None, previous=None, size=None):
        expected_os_links = None
        if type(path) is str and path in OS_TOOLS:
            original = getattr(self.context, "os_files", None)
            require(type(original) is dict and path in original, "ADMIN_CREATE", "REFUSED")
            original = original[path]
            require(type(original) is list and len(original) == 6 and
                    all(type(value) is int for value in original) and original[5] > 0, "ADMIN_CREATE", "REFUSED")
            expected_os_links = original[5]
        first = self._run(["/usr/bin/stat", "-f", STAT_FORMAT, path], "ADMIN_CREATE")["stdout"]
        acl = self._run(["/bin/ls", "-lde", path], "ADMIN_CREATE")["stdout"]
        second = self._run(["/usr/bin/stat", "-f", STAT_FORMAT, path], "ADMIN_CREATE")["stdout"]
        require(first == second, "ADMIN_CREATE", "IDENTITY_CHANGED",
                admin_site="META_STABLE", admin_item=admin_object_item(path, kind))
        return parse_admin_metadata(first, acl, path, kind, mode=mode, previous=previous, size=size,
                                    expected_os_links=expected_os_links)

    def create(self):
        require(self.root is None and self.path is None and self.launcher is None and
                self.root_populated_meta is None, "ADMIN_CREATE", "REFUSED")
        self.launcher_bytes = prepare_launcher(self.context, self.directory, self.end_ns)
        require(type(self.launcher_bytes) is bytes and 0 < len(self.launcher_bytes) <= STREAM_BYTES,
                "ADMIN_CREATE", "BOUND")
        raw = self._run(["/usr/bin/mktemp", "-d", ROOT_TEMPLATE], "ADMIN_CREATE")["stdout"]
        require(re.fullmatch(rb"/private/var/db/p2pkit-context\.[A-Za-z0-9]{10}\n", raw), "ADMIN_CREATE", "UNSUPPORTED")
        self.root = raw[:-1].decode("ascii")
        self.root_meta = self.metadata(self.root, "directory", mode=0o700)
        require(self.root_meta["nlink"] > 0, "ADMIN_CREATE", "IDENTITY_CHANGED")
        raw = self._run(["/usr/bin/mktemp", self.root + "/job.plist"], "ADMIN_CREATE")["stdout"]
        require(raw == self.root.encode("ascii") + b"/job.plist\n", "ADMIN_CREATE", "UNSUPPORTED")
        self.path = raw[:-1].decode("ascii")
        self.file_meta = self.metadata(self.path, "file", mode=0o600, size=0)
        # Keep the empty original. Only this owned insertion may establish a
        # populated observation; no directory-link arithmetic is presumed.
        populated = self.metadata(self.root, "directory", mode=0o700)
        require(populated["nlink"] > 0 and
                all(populated[key] == self.root_meta[key] for key in ("dev", "ino", "mode", "uid", "gid")),
                "ADMIN_CREATE", "IDENTITY_CHANGED")
        require(self._run(["/bin/ls", "-1A", self.root], "ADMIN_CREATE")["stdout"] ==
                self.path.rsplit("/", 1)[1].encode("ascii") + b"\n", "ADMIN_CREATE", "IDENTITY_CHANGED")
        self.root_populated_meta = populated
        raw = self._run(["/usr/bin/mktemp", self.root + "/launcher"], "ADMIN_CREATE")["stdout"]
        require(raw == self.root.encode("ascii") + b"/launcher\n", "ADMIN_CREATE", "UNSUPPORTED")
        self.launcher = raw[:-1].decode("ascii")
        self.launcher_meta = self.metadata(self.launcher, "file", mode=0o600, size=0)
        # A second owned insertion establishes another observed directory state;
        # do not assume that inserting a regular file preserves its link count.
        populated = self.metadata(self.root, "directory", mode=0o700)
        require(populated["nlink"] > 0 and
                all(populated[key] == self.root_populated_meta[key] for key in ("dev", "ino", "mode", "uid", "gid")),
                "ADMIN_CREATE", "IDENTITY_CHANGED")
        require(self._run(["/bin/ls", "-1A", self.root], "ADMIN_CREATE")["stdout"] == b"job.plist\nlauncher\n",
                "ADMIN_CREATE", "IDENTITY_CHANGED")
        self.root_populated_meta = populated
        self.arguments = [self.launcher]
        self.plist = service_plist(self.context, self.label, self.directory, self.launcher)
        # mktemp was exclusive. tee is intentionally NOT described as exclusive:
        # only the checked root0700 original parent protects its truncating open.
        returned = self._run(["/usr/bin/tee", self.path], "ADMIN_CREATE", input_raw=self.plist)
        require(returned["stdout"] == self.plist, "ADMIN_CREATE", "IDENTITY_CHANGED",
                admin_site="PLIST_TEE", admin_item="PRIVATE_FILE")
        self.file_meta = self.metadata(self.path, "file", mode=0o600, previous=self.file_meta, size=len(self.plist))
        require(self._run(["/bin/cat", self.path], "ADMIN_CREATE")["stdout"] == self.plist,
                "ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="PLIST_CAT", admin_item="PRIVATE_FILE")
        self.metadata(self.path, "file", mode=0o600, previous=self.file_meta, size=len(self.plist))
        # Transfer only bounded, original F bytes, never a runner-writable path.
        while self.launcher_offset < len(self.launcher_bytes):
            chunk = self.launcher_bytes[self.launcher_offset:self.launcher_offset + FRAME_BYTES]
            argv = ["/usr/bin/tee", *(["-a"] if self.launcher_offset else []), self.launcher]
            require(self._run(argv, "ADMIN_CREATE", input_raw=chunk)["stdout"] == chunk,
                    "ADMIN_CREATE", "IDENTITY_CHANGED")
            self.launcher_offset += len(chunk)
        written = self.metadata(self.launcher, "file", mode=0o600, previous=self.launcher_meta,
                                size=len(self.launcher_bytes))
        self._run(["/bin/chmod", "700", self.launcher], "ADMIN_CREATE")
        # This is the one admitted mode transition on the same original inode.
        executable = {**written, "mode": (written["mode"] & ~0o7777) | 0o700}
        self.launcher_meta = self.metadata(self.launcher, "file", mode=0o700, previous=executable,
                                          size=len(self.launcher_bytes))
        require(self._run(["/bin/cat", self.launcher], "ADMIN_CREATE")["stdout"] == self.launcher_bytes,
                "ADMIN_CREATE", "IDENTITY_CHANGED")
        self.metadata(self.launcher, "file", mode=0o700, previous=self.launcher_meta, size=len(self.launcher_bytes))
        self.metadata(self.root, "directory", mode=0o700, previous=self.root_populated_meta)
        write_new(self.directory / "launch.plist", self.plist)

    def bootstrap(self):
        require(self.path is not None and self.launcher_meta is not None and
                self.launcher_offset == len(self.launcher_bytes) and not self.bootstrapped and self.service is None,
                "BOOTSTRAP", "REFUSED")
        service_absent(self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP", success=False,
                                 return_site="BOOTSTRAP_PRECHECK_PRINT"), self.label)
        self._run(["/bin/launchctl", "bootstrap", "system", self.path], "BOOTSTRAP", return_site="BOOTSTRAP_COMMAND")
        self.bootstrapped = True

    def inspect(self, identity, *, running=True):
        require(self.bootstrapped, "BOOTSTRAP", "REFUSED")
        if self.service is not None:
            same_identity(identity, self.service)
        raw = self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP",
                        return_site="INSPECT_RUNNING_PRINT" if running else "INSPECT_STOPPED_PRINT")["stdout"]
        result = parse_service_print(raw, self.label, self.path, self.arguments, identity["pid"], running=running)
        self.service = dict(identity)
        return result

    def retire(self, identity):
        require(self.service is not None and not self.retired and not self.removed and
                self.root_meta is not None and self.root_populated_meta is not None, "RETIRE", "RESOURCE_UNKNOWN")
        self.inspect(identity, running=False)
        self._run(["/bin/launchctl", "bootout", "system/" + self.label], "RETIRE")
        service_absent(self._run(["/bin/launchctl", "print", "system/" + self.label], "RETIRE", success=False), self.label)
        self.retired = True
        self.metadata(self.root, "directory", mode=0o700, previous=self.root_populated_meta)
        require(self._run(["/bin/ls", "-1A", self.root], "RETIRE")["stdout"] ==
                b"job.plist\nlauncher\n", "RETIRE", "IDENTITY_CHANGED")
        self.metadata(self.path, "file", mode=0o600, previous=self.file_meta, size=len(self.plist))
        require(self._run(["/bin/cat", self.path], "RETIRE")["stdout"] == self.plist, "RETIRE", "IDENTITY_CHANGED")
        self.metadata(self.launcher, "file", mode=0o700, previous=self.launcher_meta, size=len(self.launcher_bytes))
        require(self._run(["/bin/cat", self.launcher], "RETIRE")["stdout"] == self.launcher_bytes,
                "RETIRE", "IDENTITY_CHANGED")
        self.metadata(self.launcher, "file", mode=0o700, previous=self.launcher_meta, size=len(self.launcher_bytes))
        self._run(["/bin/rm", self.launcher], "RETIRE")
        self._run(["/bin/rm", self.path], "RETIRE")
        self.metadata(self.root, "directory", mode=0o700, previous=self.root_meta)
        self._run(["/bin/rmdir", self.root], "RETIRE")
        for name in (self.root, self.path, self.launcher):
            try:
                os.lstat(name)
            except FileNotFoundError as error:
                require(error.errno == errno.ENOENT, "RETIRE", "RESOURCE_UNKNOWN")
            else:
                raise ContextError("RETIRE", "RESOURCE_UNKNOWN")
        self.removed = True

    def close(self):
        require(not self.closed, "CLOSE", "RESOURCE_UNKNOWN")
        self.record.flush()
        os.fsync(self.record.fileno())
        self.record.close()
        require(self.record.closed, "CLOSE", "RESOURCE_UNKNOWN")
        self.closed = True


def file_pin(path, maximum, end_ns, *, owners=None, executable=False):
    path = physical(path)
    allowed_owners = (os.getuid(),) if owners is None else owners
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode), "SOURCE", "IDENTITY_CHANGED", source_site="PIN_TYPE")
        require(before.st_uid in allowed_owners, "SOURCE", "IDENTITY_CHANGED", source_site="PIN_OWNER")
        require(before.st_nlink == 1, "SOURCE", "IDENTITY_CHANGED", source_site="PIN_NLINK")
        require(not before.st_mode & 0o022, "SOURCE", "IDENTITY_CHANGED", source_site="PIN_MODE")
        require(0 <= before.st_size <= maximum, "SOURCE", "IDENTITY_CHANGED", source_site="PIN_SIZE")
        require(not executable or os.access(path, os.X_OK), "SOURCE", "IDENTITY_CHANGED", source_site="PIN_EXECUTABLE")
        value, size = hashlib.sha256(), 0
        while True:
            left(end_ns, "SOURCE")
            raw = handle.read(64 * 1024)
            if not raw:
                break
            size += len(raw)
            require(size <= maximum, "SOURCE", "BOUND")
            value.update(raw)
        stamp = lambda item: [item.st_dev, item.st_ino, item.st_mode, item.st_uid, item.st_gid, item.st_nlink,
                              item.st_size, item.st_mtime_ns, item.st_ctime_ns]
        require(size == before.st_size, "SOURCE", "IDENTITY_CHANGED", source_site="PIN_READ_SIZE")
        before_stamp = stamp(before)
        handle_stamp = stamp(os.fstat(handle.fileno()))
        require(before_stamp == handle_stamp, "SOURCE", "IDENTITY_CHANGED", source_site="PIN_FD_STABLE")
        require(handle_stamp == stamp(path.lstat()), "SOURCE", "IDENTITY_CHANGED", source_site="PIN_PATH_STABLE")
    return {"path": str(path), "stat": stamp(before), "size": size, "sha256": value.hexdigest()}


def checked_interpreter(end_ns):
    path = Path(sys.executable).resolve(strict=True)
    require(path == Path(INTERPRETER).resolve(strict=True), "SOURCE", "INTERPRETER")
    safe_component_path(path)
    for parent in path.parents:
        info = physical(parent).lstat()
        require(stat.S_ISDIR(info.st_mode), "SOURCE", "IDENTITY_CHANGED", source_site="PYTHON_PARENT_TYPE")
        require(info.st_uid in (0, os.getuid()), "SOURCE", "IDENTITY_CHANGED", source_site="PYTHON_PARENT_OWNER")
        require(not info.st_mode & 0o022, "SOURCE", "IDENTITY_CHANGED", source_site="PYTHON_PARENT_MODE")
    return file_pin(path, 64 * 1024 * 1024, end_ns, owners=(0, os.getuid()), executable=True)


def observe_startup_child(native, process, birth, parent, expected_account):
    """One original direct child's startup image, never an identity from READY."""
    require(process.returncode is None and type(process.pid) is int and process.pid > 0,
            "IDENTITY", "IDENTITY_CHANGED")
    same_identity(birth, birth)
    require(birth["pid"] == process.pid and birth["parentPid"] == parent["pid"] == os.getpid() and
            birth["parentUniqueId"] == parent["uniqueId"], "IDENTITY", "IDENTITY_CHANGED")
    identity_account(birth, expected_account)
    observed = native.identity(process.pid)
    same_identity(observed, observed)
    # Initial exec completion is not final interpreter readiness. Birth continuity
    # alone admits no work: READY and later checks require the full observed image,
    # including its actual pidVersion. Neither native observation is rewritten.
    require(all(observed[key] == birth[key] for key in IDENTITY_KEYS - {"status", "pidVersion"}),
            "IDENTITY", "IDENTITY_CHANGED")
    identity_account(observed, expected_account)
    return observed


def _source_names(profile):
    validate_profile(profile)
    names = (MODULE, LAUNCHER_SOURCE, profile.script, profile.workflow, "scripts/audit_processes.py", "scripts/run-audit-command.py",
             "AGENTS.md", "CLAUDE.md", POLICY_PATH)
    if profile is STARTUP:
        # The diagnostic imports the maintained generator's scope-neutral
        # helpers, not its request, producer or qualification authority.
        names += ("scripts/run-hosted-dependency-update.py", "scripts/hosted_evidence.py")
    return names


def source_snapshot(profile, end_ns, env):
    names = _source_names(profile)
    rows, returns = [], []
    for arguments in (("rev-parse", "HEAD"), ("rev-parse", "HEAD^{tree}"),
                      ("status", "--porcelain=v1", "--untracked-files=all", "--ignored")):
        result = capture_fixed(["/usr/bin/git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                                "--no-pager", "-C", str(ROOT), *arguments], end_ns,
                               {**env, "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1",
                                "GIT_CONFIG_GLOBAL": "/dev/null"})
        require(result["code"] == 0 and not result["stderr"], "SOURCE", "RETURN_FAILED")
        rows.append(result["stdout"])
        returns.append({"argv": result["argv"], "code": result["code"], "stdoutSha256": digest(result["stdout"]),
                        "stderrSha256": digest(result["stderr"]), "waited": result["waited"],
                        "eof": result["eof"], "closed": result["closed"]})
    require(not rows[2], "SOURCE", "IDENTITY_CHANGED")
    commit, tree = (row.decode("ascii").strip() for row in rows[:2])
    require(SHA.fullmatch(commit) and SHA.fullmatch(tree), "SOURCE", "IDENTITY_CHANGED")
    files = {name: digest(read_file(ROOT / name, EVIDENCE_BYTES)) for name in names}
    return {"commit": commit, "tree": tree, "files": files}, returns


def check_source_files(profile, source):
    names = set(_source_names(profile))
    require(type(source) is dict and set(source) == {"commit", "tree", "files"} and SHA.fullmatch(source["commit"]) and
            SHA.fullmatch(source["tree"]) and type(source["files"]) is dict and set(source["files"]) == names,
            "SOURCE", "IDENTITY_CHANGED")
    require(all(type(value) is str and HASH.fullmatch(value) and digest(read_file(ROOT / name, EVIDENCE_BYTES)) == value
                for name, value in source["files"].items()), "SOURCE", "IDENTITY_CHANGED")
    require(source["files"][POLICY_PATH] == POLICY_SHA256, "POLICY", "IDENTITY_CHANGED")


def case_paths(profile, operation, case):
    validate_profile(profile)
    require(case in profile.cases, "START", "CASE")
    directory = operation / "bridge/cases" / case
    if profile is GENERATION or profile is STARTUP:
        state, canonical = operation / "state", ROOT
    else:
        require(profile is QUALIFICATION, "START", "PROFILE")
        state, canonical = operation / "states" / case, operation / "fixture"
    return directory, state, canonical


def case_input(profile, directory):
    operation = directory.parent.parent.parent
    require(directory == case_paths(profile, operation, directory.name)[0], "IDENTITY")
    raw = read_file(directory / "case-input.json", FRAME_BYTES)
    value = parsed(raw)
    if profile is GENERATION:
        extra, name = "generationInputsSha256", "generation-inputs.json"
    elif profile is STARTUP:
        extra, name = "startupInputsSha256", "startup-inputs.json"
    else:
        require(profile is QUALIFICATION, "SOURCE", "PROFILE")
        extra, name = "fixtureSourceSha256", "fixture-source.json"
    require(type(value) is dict and set(value) == CASE_INPUT_KEYS | {extra} and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == profile.scope and value["case"] == directory.name and
            type(value["binding"]) is str and HASH.fullmatch(value["binding"]) and
            value["caseDirectoryIdentity"] == private_directory(directory), "IDENTITY")
    path = operation / name
    require(type(value[extra]) is str and HASH.fullmatch(value[extra]) and
            digest(read_file(path, FILE_BYTES)) == value[extra], "SOURCE", "IDENTITY_CHANGED")
    return value, digest(raw)


def validate_prepared(profile, value, directory, native, interpreter):
    validate_profile(profile)
    require(type(value) is dict and set(value) == PREPARED_KEYS and type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == profile.scope and value["case"] in profile.cases and value["case"] == directory.name,
            "IDENTITY")
    operation = directory.parent.parent.parent
    require(private_directory(operation) == value["operationIdentity"] and
            private_directory(directory) == value["directoryIdentity"] and native.boot() == value["boot"] and
            interpreter == value["interpreter"], "IDENTITY", "IDENTITY_CHANGED")
    validate_account(account(), value["account"])
    check_source_files(profile, value["source"])
    require(value["github"]["source"] == value["source"]["commit"] and
            value["github"]["sourceTree"] == value["source"]["tree"] and
            value["github"]["workflow"] == profile.workflow and value["github"]["job"] == profile.job and
            value["github"]["repository"] == REPOSITORY and profile.ref.fullmatch(value["github"]["ref"]),
            "SOURCE", "IDENTITY_CHANGED")
    now, wall = shared_raw_ns(), time.time_ns()
    require(validate_allocation(profile, value["allocation"], value["github"], now, wall) == value["jobEndNs"] and
            all(type(value[name]) is int and value[name] > now for name in
                ("caseEndNs", "stepEndNs", "jobEndNs", "policyEndNs")) and
            value["caseEndNs"] <= min(value["stepEndNs"], value["jobEndNs"], value["policyEndNs"]), "START", "TIMEOUT")
    inputs, input_hash = case_input(profile, directory)
    require(input_hash == value["caseInputSha256"] and inputs["binding"] == value["binding"] and
            inputs["github"] == value["github"] and inputs["account"] == value["account"] and
            inputs["foreground"] == value["foreground"] and inputs["caseEndNs"] == value["caseEndNs"] and
            inputs["repositorySource"] == {"commit": value["source"]["commit"], "tree": value["source"]["tree"]} and
            inputs["allocationSha256"] == digest(read_file(operation / "allocation.json")),
            "IDENTITY", "IDENTITY_CHANGED")
    return inputs


def validate_canonical_entry(profile, value, inputs, input_hash):
    validate_profile(profile)
    root_source = profile is GENERATION or profile is STARTUP
    extra = {"sourceCommit", "sourceTree"} if root_source else {"fixtureSourceCommit", "fixtureSourceTree", "invocationId"}
    require(type(value) is dict and set(value) == CANONICAL_ENTRY_KEYS | extra and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == profile.scope and value["case"] == inputs["case"] and
            value["binding"] == inputs["binding"] and value["caseInputSha256"] == input_hash and
            all(type(value[key]) is str and HASH.fullmatch(value[key]) for key in ("contextSha256", "gradlePolicySha256")) and
            type(value["contextId"]) is str and UUID.fullmatch(value["contextId"]), "START", "CANONICAL_ENTRY")
    source_keys = ("sourceCommit", "sourceTree") if root_source else ("fixtureSourceCommit", "fixtureSourceTree")
    require(all(type(value[key]) is str and SHA.fullmatch(value[key]) for key in source_keys) and
            (root_source or type(value["invocationId"]) is str and UUID.fullmatch(value["invocationId"])),
            "START", "CANONICAL_ENTRY")
    same_identity(value["producerIdentity"], value["producerIdentity"])
    require(type(value["enteredMonotonicNs"]) is int and
            inputs["caseStartNs"] <= value["enteredMonotonicNs"] < inputs["caseEndNs"], "START", "TIMEOUT")
    return value


def read_canonical_entry(profile, directory, inputs, input_hash):
    validate_profile(profile)
    raw = read_file(directory / "canonical-entry.json")
    entry = validate_canonical_entry(profile, parsed(raw), inputs, input_hash)
    _, state, canonical = case_paths(profile, directory.parent.parent.parent, inputs["case"])
    context_raw = read_file(state / "context.json", EVIDENCE_BYTES)
    context = parsed(context_raw, EVIDENCE_BYTES)
    policy_raw = read_file(state / "gradle-home/gradle.properties")
    require(digest(context_raw) == entry["contextSha256"] and digest(policy_raw) == entry["gradlePolicySha256"] and
            context["id"] == entry["contextId"] and context["root"] == str(canonical) and
            context["gradleHome"] == str(state / "gradle-home"), "START", "CANONICAL_ENTRY")
    root_source = profile is GENERATION or profile is STARTUP
    keys = ("sourceCommit", "sourceTree") if root_source else ("fixtureSourceCommit", "fixtureSourceTree")
    require(context["source"]["commit"] == entry[keys[0]] and context["source"]["tree"] == entry[keys[1]] and
            context["source"]["status"] == "" and context["source"]["diffSha256"] == digest(b""), "SOURCE", "IDENTITY_CHANGED")
    if root_source:
        require(entry["sourceCommit"] == inputs["repositorySource"]["commit"] and
                entry["sourceTree"] == inputs["repositorySource"]["tree"], "SOURCE", "IDENTITY_CHANGED")
    return entry, digest(raw)


def validate_producer_result(profile, value, entry, input_hash):
    validate_profile(profile)
    require(type(value) is dict and set(value) == PRODUCER_RESULT_KEYS and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == profile.scope and value["case"] == entry["case"] and
            value["binding"] == entry["binding"] and value["caseInputSha256"] == input_hash and
            type(value["canonicalEntrySha256"]) is str and HASH.fullmatch(value["canonicalEntrySha256"]) and
            value["disposition"] in ("SUCCESS", "CLOSED_FAILED_PRODUCT", "INFRASTRUCTURE_REFUSAL"),
            "CLOSE", "PRODUCER_RESULT")
    same_identity(value["producerIdentity"], entry["producerIdentity"])
    if profile is GENERATION:
        purposes = ("dependency-maintenance-prerequisites", "dependency-maintenance-generator")
    elif profile is STARTUP:
        purposes = STARTUP_PURPOSES
    else:
        require(profile is QUALIFICATION, "CLOSE", "PROFILE")
        purposes = ("dependency-context-" + entry["case"].lower(),)
    rows = value["commands"]
    require(type(rows) is list and 1 <= len(rows) <= len(purposes),
            "CLOSE", "PRODUCER_RESULT")
    previous = entry["enteredMonotonicNs"]
    ids = set()
    for index, row in enumerate(rows):
        require(type(row) is dict and set(row) == {"invocationId", "purpose", "receiptSha256", "code", "returnedRawNs"} and
                type(row["invocationId"]) is str and UUID.fullmatch(row["invocationId"]) and row["invocationId"] not in ids and
                type(row["receiptSha256"]) is str and HASH.fullmatch(row["receiptSha256"]) and
                type(row["code"]) is int and 0 <= row["code"] <= 125 and type(row["returnedRawNs"]) is int and
                previous <= row["returnedRawNs"], "CLOSE", "PRODUCER_RESULT")
        require(row["purpose"] == purposes[index] and (index == len(rows) - 1 or row["code"] == 0),
                "CLOSE", "PRODUCER_RESULT")
        if profile is QUALIFICATION:
            require(row["invocationId"] == entry["invocationId"], "CLOSE", "PRODUCER_RESULT")
        ids.add(row["invocationId"])
        previous = row["returnedRawNs"]
    require(type(value["code"]) is int and value["code"] == rows[-1]["code"] and type(value["completedRawNs"]) is int and
            previous <= value["completedRawNs"], "CLOSE", "PRODUCER_RESULT")
    expected = "SUCCESS" if value["code"] == 0 else "CLOSED_FAILED_PRODUCT" if 1 <= value["code"] <= 123 else "INFRASTRUCTURE_REFUSAL"
    require(value["disposition"] == expected and (value["code"] != 0 or len(rows) == len(purposes)),
            "CLOSE", "PRODUCER_RESULT")
    return value


def frame_value(serial, binding, payload):
    require(type(serial) is int and 1 <= serial <= len(FRAME_ROSTER) and type(binding) is str and HASH.fullmatch(binding),
            "START")
    _, direction, kind = FRAME_ROSTER[serial - 1]
    value = {"schema": 1, "serial": serial, "direction": direction, "kind": kind, "binding": binding, "payload": payload}
    require(len(encoded(value)) <= FRAME_BYTES, "START", "BOUND")
    return value


def validate_frame(value, serial, binding):
    require(type(value) is dict and set(value) == {"schema", "serial", "direction", "kind", "binding", "payload"} and
            type(value["schema"]) is int and value["schema"] == 1 and type(value["serial"]) is int and
            value == frame_value(serial, binding, value["payload"]), "START", "FRAME")
    return value["payload"]


def frame_record(value):
    return {"serial": value["serial"], "direction": value["direction"], "kind": value["kind"], "sha256": digest(encoded(value))}


def receive_bytes(channel, size):
    with at_stage("START"):
        raw, ancillary, flags, _address = channel.recvmsg(size, socket.CMSG_SPACE(16))
        if ancillary:
            for level, kind, data in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    for index in range(0, len(data) - len(data) % 4, 4):
                        os.close(struct.unpack("=i", data[index:index + 4])[0])
        require(not ancillary and flags == 0, "START")
        return raw


class FrameReader:
    """One bounded frame on one retained channel, pumped by its actual owner."""

    def __init__(self, channel, serial, binding, trace):
        require(not trace or trace[-1]["serial"] < serial, "START", "FRAME_ORDER")
        self.channel, self.serial, self.binding, self.trace = channel, serial, binding, trace
        self.raw, self.size, self.value, self.eof = bytearray(), None, None, False

    def poll(self):
        require(self.value is None and not self.eof, "START", "FRAME_REPLAY")
        while True:
            needed = 4 if self.size is None else self.size + 4
            ready, _, _ = select.select([self.channel], [], [], 0)
            if not ready:
                return None
            raw = receive_bytes(self.channel, needed - len(self.raw))
            if not raw:
                require(not self.raw, "START", "PARTIAL_FRAME")
                self.eof = True
                return None
            self.raw.extend(raw)
            if self.size is None and len(self.raw) == 4:
                self.size = struct.unpack("!I", self.raw)[0]
                require(0 < self.size <= FRAME_BYTES, "START", "BOUND")
            if self.size is not None and len(self.raw) == self.size + 4:
                data = bytes(self.raw[4:])
                self.value = parsed(data)
                require(encoded(self.value) == data, "START", "FRAME")
                validate_frame(self.value, self.serial, self.binding)
                self.trace.append(frame_record(self.value))
                return self.value


def send_frame(channel, serial, binding, payload, trace, end_ns):
    require(len(trace) < 8 and (not trace or trace[-1]["serial"] < serial), "START", "FRAME_ORDER")
    value = frame_value(serial, binding, payload)
    raw = encoded(value)
    pending = memoryview(struct.pack("!I", len(raw)) + raw)
    while pending:
        _, writable, _ = select.select([], [channel], [], min(0.05, left(end_ns)))
        if writable:
            with at_stage("START"):
                count = channel.send(pending)
            require(count > 0, "START", "RETURN_FAILED")
            pending = pending[count:]
    left(end_ns)
    trace.append(frame_record(value))
    return value


def read_frame(channel, serial, binding, trace, end_ns, pump=None):
    reader = FrameReader(channel, serial, binding, trace)
    while reader.value is None:
        if pump is not None:
            pump()
        reader.poll()
        require(not reader.eof, "START", "STATUS_MISSING")
        if reader.value is None:
            select.select([channel], [], [], min(0.05, left(end_ns)))
    left(end_ns)
    return reader.value


def wait_eof(channel, end_ns, pump=None):
    while True:
        if pump is not None:
            pump()
        ready, _, _ = select.select([channel], [], [], min(0.05, left(end_ns, "CLOSE")))
        if ready:
            require(receive_bytes(channel, 1) == b"", "CLOSE")
            left(end_ns, "CLOSE")
            return


def close_socket(channel):
    channel.close()
    require(channel.fileno() == -1, "CLOSE", "RESOURCE_UNKNOWN")


def socket_identity(path):
    info = physical(path).lstat()
    require(stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
            "IDENTITY", "IDENTITY_CHANGED")
    return [info.st_dev, info.st_ino]


class Captures:
    """Original process-private standard descriptors; no inherited sibling writer."""

    def __init__(self, directory, role):
        require(role in ("D", "P"), "PREPARE")
        prefix = "service" if role == "D" else "producer-controller"
        self.directory, self.handles, self.closed = directory, [], False
        for fd, suffix in ((1, "stdout"), (2, "stderr")):
            name = prefix + "." + suffix
            original = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            self.handles.append((fd, name, original))
            os.dup2(original, fd)

    def check(self):
        require(not self.closed and all(os.fstat(original).st_size <= STREAM_BYTES for _, _, original in self.handles),
                "CLOSE", "BOUND")

    def close(self):
        require(not self.closed, "CLOSE", "RESOURCE_UNKNOWN")
        sys.stdout.flush()
        sys.stderr.flush()
        self.check()
        null = os.open("/dev/null", os.O_WRONLY | os.O_NOFOLLOW)
        rows = []
        try:
            require(stat.S_ISCHR(os.fstat(null).st_mode), "CLOSE", "RESOURCE_UNKNOWN")
            for fd, name, original in self.handles:
                os.fsync(original)
                os.dup2(null, fd)
                os.close(original)
                raw = read_file(self.directory / name)
                rows.append({"name": name, "size": len(raw), "sha256": digest(raw), "closed": True, "fsync": True})
        finally:
            os.close(null)
        self.closed = True
        return rows


class Pipes:
    """Only original Popen descriptors, continuously drained without a thread."""

    def __init__(self, process, prefix="producer-pipe"):
        require(prefix in ("producer-pipe", "sentinel"), "START")
        self.process, self.prefix, self.active = process, prefix, [process.stdout, process.stderr]
        self.data, self.closed = {"stdout": bytearray(), "stderr": bytearray()}, False
        for stream in self.active:
            os.set_blocking(stream.fileno(), False)

    def pump(self):
        for stream in list(self.active):
            try:
                raw = os.read(stream.fileno(), 4096)
            except BlockingIOError:
                continue
            name = "stdout" if stream is self.process.stdout else "stderr"
            self.data[name].extend(raw)
            require(len(self.data[name]) <= STREAM_BYTES, "CHILD_WAIT", "BOUND")
            if not raw:
                stream.close()
                self.active.remove(stream)

    def finish(self, end_ns, directory, pump=None):
        while self.active or self.process.poll() is None:
            if pump is not None:
                pump()
            self.pump()
            select.select(self.active, [], [], min(0.02, left(end_ns, "CHILD_WAIT")))
        code = self.process.wait(timeout=left(end_ns, "CHILD_WAIT"))
        require(all(stream.closed for stream in (self.process.stdout, self.process.stderr)), "CLOSE", "RESOURCE_UNKNOWN")
        rows = []
        for name, raw in self.data.items():
            raw = bytes(raw)
            filename = self.prefix + "." + name
            write_new(directory / filename, raw)
            rows.append({"name": filename, "size": len(raw), "sha256": digest(raw), "eof": True, "closed": True})
        self.closed = True
        return code, rows


class Producer:
    def __init__(self, profile, fd):
        self.profile = validate_profile(profile)
        require(type(fd) is int and 2 < fd < 4096 and stat.S_ISSOCK(os.fstat(fd).st_mode), "IDENTITY")
        directory = physical(os.environ.get("P2PKIT_DEPENDENCY_BRIDGE_DIRECTORY", ""))
        self.directory, self.operation = directory, directory.parent.parent.parent
        private_directory(directory)
        account()  # Refuse privileged project interpreter before reading inputs/captures.
        self.captures = Captures(directory, "P")
        self.native, self.channel, self.trace = Darwin(role="P", observe_exit=False), socket.socket(fileno=fd), []
        self.channel.setblocking(False)
        self.prepared = parsed(read_file(directory / "prepared.json"))
        self.deadline_ns = self.prepared["caseEndNs"]
        interpreter = checked_interpreter(self.deadline_ns)
        self.inputs = validate_prepared(profile, self.prepared, directory, self.native, interpreter)
        self.case, self.binding = self.inputs["case"], self.inputs["binding"]
        self.case_start_ns = self.inputs["caseStartNs"]
        self.input_path, self.input_sha256 = directory / "case-input.json", self.prepared["caseInputSha256"]
        self.canonical_entry_path, self.producer_result_path = directory / "canonical-entry.json", directory / "producer-result.json"
        _, self.state, self.canonical_root = case_paths(profile, self.operation, self.case)
        self.repository_source = copy_data(self.inputs["repositorySource"])
        self.identity, self.parent = self.native.identity(os.getpid()), self.native.identity(os.getppid())
        identity_account(self.identity, self.prepared["account"])
        identity_account(self.parent, self.prepared["account"])
        require(self.identity["parentPid"] == self.parent["pid"] and
                self.identity["parentUniqueId"] == self.parent["uniqueId"] and self.parent["parentPid"] == 1,
                "IDENTITY", "IDENTITY_CHANGED")
        require(session_record(self.identity) == {"pid": os.getpid(), "sessionId": os.getpid(), "processGroupId": os.getpid()},
                "IDENTITY", "SESSION")
        expected = child_environment(profile, self.operation, self.prepared["tools"])
        expected.update(P2PKIT_DEPENDENCY_BRIDGE_DIRECTORY=str(directory), P2PKIT_DEPENDENCY_BRIDGE_BINDING=self.binding,
                        P2PKIT_DEPENDENCY_BRIDGE_CLOCK_SCHEMA=str(CLOCK_SCHEMA), P2PKIT_DEPENDENCY_BRIDGE_CLOCK_DOMAIN=CLOCK_DOMAIN)
        validate_private_environment(expected)
        require(signal.getsignal(signal.SIGTERM) == signal.SIG_DFL and
                signal.SIGTERM not in signal.pthread_sigmask(signal.SIG_BLOCK, []), "IDENTITY", "SIGNAL_STATE")
        self.started, self.completed, self.entry, self.entry_hash = False, False, None, None

    def identity_record(self):
        require(not self.started, "IDENTITY", "NO_POST_START_REBIND")
        return dict(self.native.same(self.identity))

    def ready(self, canonical_entry_path):
        require(not self.started and not self.completed and canonical_entry_path == self.canonical_entry_path, "START")
        self.entry, self.entry_hash = read_canonical_entry(self.profile, self.directory, self.inputs, self.input_sha256)
        same_identity(self.entry["producerIdentity"], self.native.same(self.identity))
        self.native.same(self.parent)
        require(case_input(self.profile, self.directory) == (self.inputs, self.input_sha256), "SOURCE", "IDENTITY_CHANGED")
        send_frame(self.channel, 3, self.binding, {"producer": dict(self.identity), "parent": dict(self.parent),
                   "account": account(), "sigtermDefault": signal.getsignal(signal.SIGTERM) == signal.SIG_DFL,
                   "sigtermBlocked": signal.SIGTERM in signal.pthread_sigmask(signal.SIG_BLOCK, []),
                   "sourceSha256": self.prepared["source"]["files"][self.profile.script], "boot": self.native.boot(),
                   "interpreter": self.prepared["interpreter"]["path"], "canonicalEntrySha256": self.entry_hash,
                   "session": session_record(self.identity)}, self.trace, self.deadline_ns)
        start = read_frame(self.channel, 6, self.binding, self.trace, self.deadline_ns)["payload"]
        require(start == start_payload(self.prepared, self.parent, self.entry_hash), "START", "IDENTITY_CHANGED")
        self.native.same(self.parent)
        self.native.same(self.identity)
        self.started = True

    def complete(self, producer_result_path):
        require(self.started and not self.completed and producer_result_path == self.producer_result_path, "CLOSE")
        raw = read_file(producer_result_path)
        result = validate_producer_result(self.profile, parsed(raw), self.entry, self.input_sha256)
        require(result["canonicalEntrySha256"] == self.entry_hash and result["completedRawNs"] < self.deadline_ns,
                "CLOSE", "IDENTITY_CHANGED")
        end_ns = self.deadline_ns
        if (self.profile is GENERATION or self.profile is STARTUP) and 0 <= result["code"] <= 123:
            end_ns = min(end_ns, result["commands"][-1]["returnedRawNs"] + 300 * NS)
        left(end_ns, "CLOSE")
        for row in result["commands"]:
            require(digest(read_file(self.state / "evidence" / row["invocationId"] / "receipt.json", EVIDENCE_BYTES)) ==
                    row["receiptSha256"], "CLOSE", "RECEIPT_CHANGED")
        # Q4 intentionally does not revalidate dead D's old parent tuple. Saved
        # full P identity remains DATA; only F owns the actual orphan authority.
        self.native.close()
        captures = self.captures.close()
        write_new(self.directory / "producer-captures.json", encoded({"schema": 1, "case": self.case,
                  "binding": self.binding, "producerResultSha256": digest(raw), "captures": captures,
                  "nativeClosed": self.native.closed}))
        self.completed = True
        delivered, failure = False, None
        try:
            send_frame(self.channel, 7, self.binding, {"case": self.case, "producerResultSha256": digest(raw),
                       "producerCapturesSha256": digest(read_file(self.directory / "producer-captures.json")),
                       "code": result["code"]}, self.trace, end_ns)
            delivered = True
        except ContextError as error:
            failure = public_error(error)
            if not (self.profile is QUALIFICATION and self.case == "Q4" and result["code"] == 125 and
                    error.errno_name in ("EPIPE", "ECONNRESET")):
                raise
        finally:
            close_socket(self.channel)
            write_new(self.directory / "producer-delivery.json", encoded({"schema": 1, "case": self.case,
                      "binding": self.binding, "resultSha256": digest(raw), "delivered": delivered,
                      "failure": failure, "channelClosed": self.channel.fileno() == -1,
                      "closedRawNs": shared_raw_ns()}))
        left(end_ns, "CLOSE")
        return result["code"]


def producer(profile, fd):
    return Producer(validate_profile(profile), fd)


def start_payload(prepared, service_identity, entry_hash):
    return {"case": prepared["case"], "account": prepared["account"], "service": service_identity,
            "sourceSha256": prepared["source"]["files"][MODULE], "caseInputSha256": prepared["caseInputSha256"],
            "canonicalEntrySha256": entry_hash, "deadlineNs": prepared["caseEndNs"], "clockDomain": CLOCK_DOMAIN}


def validate_ready(profile, ready, prepared, service_identity, producer_identity, directory):
    payload = validate_frame(ready, 3, prepared["binding"])
    require(type(payload) is dict and set(payload) == {"producer", "parent", "account", "sigtermDefault", "sigtermBlocked",
            "sourceSha256", "boot", "interpreter", "canonicalEntrySha256", "session"} and
            payload["sigtermDefault"] is True and payload["sigtermBlocked"] is False, "IDENTITY")
    same_identity(payload["parent"], service_identity)
    same_identity(payload["producer"], producer_identity)
    identity_account(producer_identity, prepared["account"])
    validate_account(payload["account"], prepared["account"])
    require(producer_identity["parentPid"] == service_identity["pid"] and
            producer_identity["parentUniqueId"] == service_identity["uniqueId"] and
            payload["sourceSha256"] == prepared["source"]["files"][profile.script] and
            payload["boot"] == prepared["boot"] and payload["interpreter"] == prepared["interpreter"]["path"],
            "IDENTITY", "IDENTITY_CHANGED")
    observed_session = session_record(producer_identity)
    service_session = session_record(service_identity)
    require(payload["session"] == observed_session == {"pid": producer_identity["pid"],
            "sessionId": producer_identity["pid"], "processGroupId": producer_identity["pid"]} and
            observed_session["sessionId"] != service_session["sessionId"] and
            observed_session["processGroupId"] != service_session["processGroupId"], "IDENTITY", "SESSION")
    inputs, input_hash = case_input(profile, directory)
    entry, entry_hash = read_canonical_entry(profile, directory, inputs, input_hash)
    require(payload["canonicalEntrySha256"] == entry_hash, "START", "CANONICAL_ENTRY")
    same_identity(entry["producerIdentity"], producer_identity)
    return entry, entry_hash, observed_session, service_session


def service_pump(state):
    """Same actual D liveness reaction for every fixed profile and control."""
    state["pipes"].pump()
    state["captures"].check()
    native, producer_identity = state["native"], state["producer"]
    native.poll()
    if state["foregroundLoss"] is None:
        ready, _, _ = select.select([state["channel"]], [], [], 0)
        if ready:
            require(receive_bytes(state["channel"], 1) == b"", "START", "UNEXPECTED_CONTROL")
            state["foregroundLoss"] = {"kind": "WRITE_EOF", "observedRawNs": shared_raw_ns()}
        elif state["foreground"]["pid"] in native.events:
            state["foregroundLoss"] = {"kind": "TERMINAL", "observedRawNs":
                                        native.events[state["foreground"]["pid"]]["observedRawNs"]}
    if state["foregroundLoss"] is not None and not state["cancelAttempted"] and producer_identity["pid"] not in native.events:
        state["cancelAttempted"] = True  # A failed signal never silently retries.
        native.same(state["service"])
        native.same(producer_identity)
        require(session_record(producer_identity) == state["producerSession"], "IDENTITY", "SESSION")
        native.signal(producer_identity, signal.SIGTERM, state["end"])
    left(state["end"])


def service(profile, directory):
    validate_profile(profile)
    require(Path(sys.argv[0]).resolve(strict=True) == ROOT / profile.script, "SOURCE", "ENTRY")
    directory = physical(directory)
    private_directory(directory)
    account()
    captures = Captures(directory, "D")
    native = channel = child_channel = producer_channel = process = pipes = None
    producer_identity = producer_birth = prepared = state = None
    diagnostic_prepared = None
    end_ns, trace, bound = None, [], False
    try:
        native = Darwin(role="D")
        prepared = parsed(read_file(directory / "prepared.json"))
        require(type(prepared) is dict and type(prepared.get("caseEndNs")) is int, "START", "TIMEOUT")
        end_ns = prepared["caseEndNs"]
        interpreter = checked_interpreter(end_ns)
        validate_prepared(profile, prepared, directory, native, interpreter)
        if profile is QUALIFICATION:
            diagnostic_prepared = prepared
        operation = directory.parent.parent.parent
        validate_private_environment(child_environment(profile, operation, prepared["tools"]))
        service_identity = native.identity(os.getpid())
        identity_account(service_identity, prepared["account"])
        require(service_identity["parentPid"] == 1, "IDENTITY")
        control = directory / "control.sock"
        require(socket_identity(control) == prepared["socketIdentity"], "IDENTITY", "IDENTITY_CHANGED")
        channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        channel.settimeout(left(end_ns))
        channel.connect(str(control))
        channel.setblocking(False)
        foreground = native.peer(channel)
        same_identity(foreground, prepared["foreground"])
        identity_account(foreground, prepared["account"])
        native.watch(foreground)
        send_frame(channel, 1, prepared["binding"], {"service": service_identity, "account": account(),
                   "foregroundPeer": foreground, "boot": native.boot(), "sourceSha256": prepared["source"]["files"][profile.script],
                   "interpreter": interpreter, "directoryIdentity": private_directory(directory)}, trace, end_ns)
        received = read_frame(channel, 2, prepared["binding"], trace, end_ns, captures.check)["payload"]
        require(received == prepared, "START", "IDENTITY_CHANGED")
        native.same(foreground)
        producer_channel, child_channel = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        child_fd = child_channel.fileno()
        environment = child_environment(profile, operation, prepared["tools"])
        environment.update(P2PKIT_DEPENDENCY_BRIDGE_DIRECTORY=str(directory),
                           P2PKIT_DEPENDENCY_BRIDGE_BINDING=prepared["binding"],
                           P2PKIT_DEPENDENCY_BRIDGE_CLOCK_SCHEMA=str(CLOCK_SCHEMA),
                           P2PKIT_DEPENDENCY_BRIDGE_CLOCK_DOMAIN=CLOCK_DOMAIN)
        left(end_ns)
        process = subprocess.Popen([interpreter["path"], "-I", "-B", "-S", str(ROOT / profile.script), "_produce", str(child_fd)],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   close_fds=True, pass_fds=(child_fd,), cwd=ROOT, env=environment, start_new_session=True)
        birth = native.identity(process.pid)
        same_identity(birth, birth)
        require(birth["pid"] == process.pid and birth["parentPid"] == os.getpid() and
                birth["parentUniqueId"] == service_identity["uniqueId"], "IDENTITY", "IDENTITY_CHANGED")
        identity_account(birth, prepared["account"])
        producer_birth = birth
        pipes = Pipes(process)
        close_socket(child_channel)
        child_channel = None
        producer_channel.setblocking(False)
        ready = read_frame(producer_channel, 3, prepared["binding"], trace, end_ns, pipes.pump)
        producer_identity = observe_startup_child(native, process, producer_birth, service_identity, prepared["account"])
        entry, entry_hash, producer_session, service_session = validate_ready(
            profile, ready, prepared, service_identity, producer_identity, directory)
        native.watch(producer_identity)
        native.same(producer_identity)
        bound = True
        send_frame(channel, 4, prepared["binding"], {"readyFrame": ready, "producerBirth": producer_birth}, trace, end_ns)
        start = read_frame(channel, 5, prepared["binding"], trace, end_ns, pipes.pump)["payload"]
        require(start == start_payload(prepared, service_identity, entry_hash), "START", "IDENTITY_CHANGED")
        native.same(foreground)
        native.same(producer_identity)
        require(session_record(producer_identity) == producer_session, "IDENTITY", "SESSION")
        forward_started = shared_raw_ns()
        send_frame(producer_channel, 6, prepared["binding"], start, trace, end_ns)
        forward_returned = shared_raw_ns()
        state = {"native": native, "pipes": pipes, "captures": captures, "channel": channel, "foreground": foreground,
                 "service": service_identity, "producer": producer_identity, "producerSession": producer_session,
                 "end": end_ns, "foregroundLoss": None, "cancelAttempted": False}
        result_frame = read_frame(producer_channel, 7, prepared["binding"], trace, end_ns, lambda: service_pump(state))
        result_payload = result_frame["payload"]
        require(type(result_payload) is dict and set(result_payload) ==
                {"case", "producerResultSha256", "producerCapturesSha256", "code"} and
                result_payload["case"] == prepared["case"], "CLOSE", "PRODUCER_RESULT")
        # F7 refers to already closed P originals. The actual command return,
        # not receipt/frame arrival, anchors the unchanged finalization300.
        result_raw = read_file(directory / "producer-result.json")
        result = validate_producer_result(profile, parsed(result_raw), entry, prepared["caseInputSha256"])
        require(result["canonicalEntrySha256"] == entry_hash and result["completedRawNs"] < end_ns and
                result_payload["producerResultSha256"] == digest(result_raw) and
                result_payload["producerCapturesSha256"] == digest(read_file(directory / "producer-captures.json")) and
                type(result_payload["code"]) is int and result_payload["code"] == result["code"],
                "CLOSE", "PRODUCER_RESULT")
        if (profile is GENERATION or profile is STARTUP) and 0 <= result["code"] <= 123:
            end_ns = min(end_ns, result["commands"][-1]["returnedRawNs"] + 300 * NS)
            state["end"] = end_ns
        left(end_ns, "CLOSE")
        wait_eof(producer_channel, end_ns, lambda: service_pump(state))
        close_socket(producer_channel)
        producer_channel = None
        producer_code, producer_streams = pipes.finish(end_ns, directory, lambda: service_pump(state))
        native.wait([producer_identity], end_ns)
        require(read_file(directory / "producer-result.json") == result_raw and
                result_payload["producerCapturesSha256"] == digest(read_file(directory / "producer-captures.json")) and
                result_payload["code"] == producer_code == result["code"] ==
                native.events[producer_identity["pid"]]["status"]["popenCode"], "CHILD_WAIT", "STATUS_UNEXPECTED")
        native.close()
        service_streams = captures.close()
        payload = {"case": prepared["case"], "producerCode": producer_code, "producerStreams": producer_streams,
                   "serviceStreams": service_streams, "resultFrame": result_frame, "tracePrefix": list(trace),
                   "producerControlEof": True, "producerWait": True, "nativeClosed": native.closed,
                   "capturesClosed": captures.closed, "signalReturns": native.signals,
                   "registrations": [{"observer": "D", "observation": row} for row in native.registrations.values()],
                   "producerNative": native.events[producer_identity["pid"]], "foregroundLoss": state["foregroundLoss"],
                   "startForward": {"startedMonotonicNs": forward_started, "returnedMonotonicNs": forward_returned}}
        send_frame(channel, 8, prepared["binding"], payload, trace, end_ns)
        close_socket(channel)
        channel = None
        # Actual P nonzero is preserved. Loss is never an ordinary product success.
        return 125 if state["foregroundLoss"] is not None else producer_code
    except BaseException as error:
        if profile is QUALIFICATION:
            with contextlib.suppress(BaseException):
                record_failure(profile, directory, diagnostic_prepared, "D", error)
        cleanup_identity = producer_identity if producer_identity is not None else producer_birth
        if process is not None and process.poll() is None and native is not None and cleanup_identity is not None:
            with contextlib.suppress(BaseException):
                if bound:
                    if state is None or not state["cancelAttempted"]:
                        native.signal(cleanup_identity, signal.SIGTERM, end_ns)
                else:
                    native.signal_birth(cleanup_identity, end_ns)
        if pipes is not None and not pipes.closed:
            with contextlib.suppress(BaseException):
                pipes.finish(end_ns, directory)
        raise
    finally:
        for stream in (child_channel, producer_channel, channel):
            if stream is not None and stream.fileno() != -1:
                close_socket(stream)
        if native is not None and not native.closed:
            native.close()
        if not captures.closed:
            captures.close()


class CaseOutcome:
    def __init__(self, owner, record):
        self._owner, self._raw = owner, encoded(record)

    @property
    def record(self):
        return parsed(self._raw, EVIDENCE_BYTES)


def validate_production_data(record):
    """Closed DATA consistency only. Foreground adds original object authority."""
    require(type(record) is dict and type(record.get("closure")) is dict and type(record.get("native")) is dict,
            "CLOSE", "PRODUCTION_RESULT")
    closure, native = record["closure"], record["native"]
    flags = ("producerNativeExit", "serviceNativeExit", "controlEof", "controlClosed", "registrationAbsent",
             "rootObjectsRemoved", "adminClosed", "soleWritersRetired")
    complete = (all(closure.get(key) is True for key in flags) and closure.get("producerPipeEof") is True and
                closure.get("producerPipeCaptures") == closure.get("serviceCaptures") == closure.get("producerRecords") == "CLOSED" and
                closure.get("serviceFinalFrame") == "RECEIVED" and record.get("lossAnnotations") == {} and
                closure.get("nativeRetention") == "HELD_UNTIL_SUITE_FINISH")
    if not complete:
        raise ProductionRefusal("CLOSE", "INCOMPLETE_PRODUCTION_CLOSURE")
    code = closure.get("producerWait")
    if not (type(code) is int and 0 <= code <= 123):
        raise ProductionRefusal("CLOSE", "INELIGIBLE_COMMAND_RETURN")
    require(native["producerNative"]["status"]["popenCode"] == code and
            native["serviceNative"]["status"]["popenCode"] == code, "CLOSE", "STATUS_UNEXPECTED")
    require(record["action"]["kind"] in ("NONE", "RELEASE"), "CLOSE", "PRODUCTION_ACTION")
    return code, "SUCCESS" if code == 0 else "CLOSED_FAILED_PRODUCT"


def verify_capture_rows(directory, rows, names, *, pipes=False):
    require(type(rows) is list and len(rows) == len(names), "CLOSE", "CAPTURE_ROSTER")
    for row, name in zip(rows, names):
        keys = {"name", "size", "sha256", "closed", "eof" if pipes else "fsync"}
        require(type(row) is dict and set(row) == keys and row["name"] == name and row["closed"] is True and
                row["eof" if pipes else "fsync"] is True, "CLOSE", "RESOURCE_UNKNOWN")
        raw = read_file(directory / name)
        require(type(row["size"]) is int and row["size"] == len(raw) and row["sha256"] == digest(raw),
                "CLOSE", "IDENTITY_CHANGED")


class Foreground:
    """One original F; neither cases nor serialized DATA may replace its owners."""

    def __init__(self, profile, operation, allocation, *, step_started_ns):
        self.profile = validate_profile(profile)
        require(Path(sys.argv[0]).resolve(strict=True) == ROOT / profile.script, "SOURCE", "ENTRY")
        self.env = dict(os.environ)
        self.github = validate_original_environment(profile, self.env)
        self.repository_source = {"commit": self.github["source"], "tree": self.github["sourceTree"]}
        self.operation = physical(operation)
        self.operation_identity = private_directory(self.operation)
        require(self.operation == physical(self.env[profile.operation_env]) and
                self.operation.parent == Path(self.env["RUNNER_TEMP"]).resolve(strict=True) and
                self.operation.name.startswith(profile.operation_prefix) and ROOT not in self.operation.parents,
                "PREPARE", "OPERATION")
        allocation_raw = read_file(self.operation / "allocation.json")
        require(parsed(allocation_raw) == allocation, "PREPARE", "ALLOCATION")
        self.allocation, self.allocation_hash = copy_data(allocation), digest(allocation_raw)
        now, wall = shared_raw_ns(), time.time_ns()
        require(type(step_started_ns) is int and self.allocation["startedMonotonicNs"] <= step_started_ns <= now,
                "PREPARE", "STEP_CLOCK")
        self.step_started_ns = step_started_ns
        self.job_end_ns = validate_allocation(profile, allocation, self.github, now, wall)
        self.policy_end_ns = allocation["startedMonotonicNs"] + POLICY_EXPIRES * NS - allocation["startedEpochNs"]
        self.step_end_ns = min(step_started_ns + profile.step_seconds * NS, self.job_end_ns, self.policy_end_ns)
        require(wall < (POLICY_EXPIRES - 12600) * NS and
                digest(read_file(ROOT / POLICY_PATH, 96 * 1024)) == POLICY_SHA256, "POLICY", "TIMEOUT")
        self.account = account()
        self.foreground_identity = None
        if profile is GENERATION:
            self.tools = {key: self.env[key] for key in TOOL_ENV}
        elif profile is STARTUP:
            self.tools = {key: self.env[key] for key in STARTUP_TOOL_ENV}
        else:
            require(profile is QUALIFICATION, "PREPARE", "PROFILE")
            self.tools = {}
        self.environment = child_environment(profile, self.operation, self.tools)
        self.os_env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"}
        self.native, self.source, self.interpreter = None, None, None
        self.current, self.outcomes, self.finished, self.failed = None, [], False, False
        self._aborted, self._abort_result, self._suite_end, self._finish_end = False, None, None, None
        self.sentinel, self.sentinel_pipes, self.sentinel_identity = None, None, None
        self.sentinel_observations, self.sentinel_closed = [], False
        self._initial_data = encoded({"github": self.github, "source": self.repository_source, "allocation": self.allocation,
                                      "account": self.account, "tools": self.tools})
        if profile is STARTUP:
            self._startup_phase, self._startup_probe_end, self._startup_probe_consumed = None, None, False

    def _original_data(self):
        require(encoded({"github": self.github, "source": self.repository_source, "allocation": self.allocation,
                         "account": self.account, "tools": self.tools}) == self._initial_data and
                private_directory(self.operation) == self.operation_identity and
                digest(read_file(self.operation / "allocation.json")) == self.allocation_hash,
                "IDENTITY", "ORIGINAL_CHANGED")

    def _set_startup_phase(self, phase):
        if getattr(self, "profile", None) is STARTUP:
            require(type(phase) is str and phase in STARTUP_DIAGNOSTIC_PHASES, "START", "DIAGNOSTIC_STATE")
            self._startup_phase = phase

    def attach_startup_failure(self, error, *, status="NOT_OBSERVED", exit_code="NONE"):
        """Capture this original F's finite phase before abort; never replace it."""
        if (getattr(self, "profile", None) is not STARTUP or type(error) is not ContextError or
                (error.stage, error.reason, error.errno_name) not in (("START", "TIMEOUT", "NONE"),
                ("START", "TIMEOUT", "ETIMEDOUT"), ("START", "STARTUP_OBSERVATION_ONLY", "NONE")) or
                hasattr(error, "_startup_diagnostic")):
            return
        value = {"startup_phase": getattr(self, "_startup_phase", None),
                 "registration_status": status, "registration_exit": exit_code}
        if _startup_diagnostic_valid(value):
            error._startup_profile, error._startup_diagnostic = STARTUP, value

    def _start_startup_probe(self, end_ns):
        if self.profile is STARTUP:
            require(self._startup_probe_end is None and not self._startup_probe_consumed,
                    "START", "DIAGNOSTIC_STATE")
            self._startup_probe_end = min(end_ns, shared_raw_ns() + STARTUP_DIAGNOSTIC_SECONDS * NS)

    def _startup_wait_check(self):
        """One fail-only print; its DATA never enables ownership or continuation."""
        if self.profile is not STARTUP:
            return
        state = self.current
        left(state["end"])  # Original case/step/job/policy deadline always wins.
        require(type(self._startup_probe_end) is int and not self._startup_probe_consumed,
                "START", "DIAGNOSTIC_STATE")
        if shared_raw_ns() < self._startup_probe_end:
            return
        admin = state["admin"]
        require(self._startup_phase in ("WAIT_CONNECT", "WAIT_HELLO") and type(admin) is Admin and
                admin.context is self and admin.directory == state["directory"] and admin.end_ns == state["end"] and
                admin.bootstrapped and not admin.closed and admin.service is None and
                admin.path is not None and admin.arguments == [admin.launcher] and
                state["service"] is None and state["producer"] is None and
                not state["prepareSent"] and not state["started"], "START", "DIAGNOSTIC_STATE")
        self._startup_probe_consumed = True
        status, code = "PRINT_FAILED", "NONE"
        try:
            result = admin._run(["/bin/launchctl", "print", "system/" + admin.label], "START", success=False)
            status, code = parse_startup_registration(result, admin.label, admin.path, admin.arguments)
        except BaseException:
            pass  # Retain the original _run quarantine; never retry or expose its error text.
        error = ContextError("START", "STARTUP_OBSERVATION_ONLY")
        self.attach_startup_failure(error, status=status, exit_code=code)
        raise error  # Even RUNNING/absent/invalid/failed observations cannot resume the normal130-call path.

    def _read_startup_hello(self, channel, binding, trace, end_ns):
        require(self.profile is STARTUP, "START", "PROFILE")
        reader = FrameReader(channel, 1, binding, trace)
        while reader.value is None:
            reader.poll()  # Ready-first: complete original HELLO wins over the diagnostic trigger.
            require(not reader.eof, "START", "STATUS_MISSING")
            if reader.value is None:
                self._startup_wait_check()
                select.select([channel], [], [], min(0.05, left(end_ns)))
        left(end_ns)
        return reader.value

    def prepare_case(self, case):
        self._set_startup_phase("PREPARE_CASE")
        require(not self.finished and not self.failed and not self._aborted and self.current is None and
                len(self.outcomes) < len(self.profile.cases) and case == self.profile.cases[len(self.outcomes)],
                "START", "CASE_ORDER")
        self._original_data()
        started = shared_raw_ns()
        if self._suite_end is None:
            reserve = 120 if self.profile is GENERATION or self.profile is STARTUP else 300
            self._suite_end = min(self.step_end_ns - reserve * NS,
                                  self.job_end_ns - (self.profile.upload_seconds + reserve) * NS,
                                  self.policy_end_ns - (self.profile.upload_seconds + reserve) * NS)
            if self.profile is QUALIFICATION:
                self._suite_end = min(self._suite_end, started + 1200 * NS)
            bridge = self.operation / "bridge"
            bridge.mkdir(mode=0o700)
            (bridge / "cases").mkdir(mode=0o700)
        end_ns = (self._suite_end if self.profile is GENERATION or self.profile is STARTUP
                  else min(self._suite_end, started + 300 * NS))
        left(end_ns)
        # Caller source orders real Recipient validation + prefix close before
        # this method. Only this original owner passively binds F here; active
        # registration, D/P, and the fixed sentinel start exclusively in run_case.
        if self.native is None:
            self.source, returns = source_snapshot(self.profile, end_ns, self.environment)
            require({"commit": self.source["commit"], "tree": self.source["tree"]} == self.repository_source,
                    "SOURCE", "IDENTITY_CHANGED")
            self.interpreter = checked_interpreter(end_ns)
            self.os_files = {}
            for name in (*OS_PARENTS, *OS_TOOLS):
                info = physical(name).lstat()
                require(info.st_uid == 0 and not info.st_mode & 0o022 and
                        (stat.S_ISDIR(info.st_mode) if name in OS_PARENTS else stat.S_ISREG(info.st_mode)),
                        "SOURCE", "OS_OBJECT")
                self.os_files[name] = ([info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid] +
                                       ([info.st_nlink] if name in OS_TOOLS else []))
            version = capture_fixed(["/usr/bin/sw_vers", "-productVersion"], end_ns, self.os_env)
            require(version["code"] == 0 and not version["stderr"] and
                    re.fullmatch(rb"26\.[0-9]+(?:\.[0-9]+)?\n", version["stdout"]), "SOURCE", "UNSUPPORTED")
            self.native = Darwin(role="F")
            self.foreground_identity = self.native.identity(os.getpid())
            identity_account(self.foreground_identity, self.account)
            self.boot = self.native.boot()
            self.username, self.groupname = pwd.getpwuid(self.account["uid"]).pw_name, grp.getgrgid(self.account["gid"]).gr_name
            require(pwd.getpwnam(self.username).pw_uid == self.account["uid"] and
                    grp.getgrnam(self.groupname).gr_gid == self.account["gid"], "IDENTITY", "IDENTITY_CHANGED")
            write_new(self.operation / "bridge/foreground.json", encoded({"schema": 1, "scope": self.profile.scope,
                      "github": self.github, "allocation": self.allocation, "source": self.source, "sourceReturns": returns,
                      "foreground": self.foreground_identity, "account": self.account, "boot": self.boot,
                      "interpreter": self.interpreter, "osVersion": version["stdout"].decode("ascii").strip(),
                      "pythonVersion": sys.version, "osFiles": self.os_files, "stepStartedRawNs": self.step_started_ns,
                      "stepEndNs": self.step_end_ns, "jobEndNs": self.job_end_ns, "policyEndNs": self.policy_end_ns}))
        else:
            self.native.same(self.foreground_identity)
            check_source_files(self.profile, self.source)
        directory, _state, _canonical = case_paths(self.profile, self.operation, case)
        directory.mkdir(mode=0o700)
        common = {"schema": 1, "scope": self.profile.scope, "case": case, "binding": digest(os.urandom(32)),
                  "github": copy_data(self.github), "allocationSha256": self.allocation_hash,
                  "repositorySource": copy_data(self.repository_source), "caseDirectoryIdentity": private_directory(directory),
                  "foreground": dict(self.foreground_identity), "account": copy_data(self.account),
                  "caseStartNs": started, "caseEndNs": end_ns}
        self.current = {"common": common, "directory": directory, "end": end_ns, "admin": None, "listener": None,
                        "channel": None, "socket": None, "service": None, "producer": None, "producerBirth": None,
                        "product": None, "producerSession": None, "serviceSession": None, "prepared": None,
                        "prepareSent": False, "started": False, "startReturnedNs": None, "trace": [], "final": None,
                        "entry": None, "entryHash": None, "reader": None, "eof": False, "actionDone": False,
                        "cancelAttempted": False, "action": {"kind": "NONE", "canonicalEntrySha256": None,
                        "canonicalStartSha256": None, "productReadySha256": None, "startedRawNs": None,
                        "returnedRawNs": None, "returnedValue": None}, "registrationStart": len(self.native.attach_attempts),
                        "signalStart": len(self.native.signals)}
        return copy_data(common)

    def _start_sentinel(self, end_ns):
        require(self.profile is QUALIFICATION and self.sentinel is None, "START")
        directory = self.operation / "bridge/sentinel"
        directory.mkdir(mode=0o700)
        self.sentinel = subprocess.Popen(["/bin/cat"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         cwd=self.operation, env=self.environment, close_fds=True)
        self.sentinel_identity = self.native.identity(self.sentinel.pid)
        identity_account(self.sentinel_identity, self.account)
        require(self.sentinel_identity["parentPid"] == self.foreground_identity["pid"] and
                self.sentinel_identity["parentUniqueId"] == self.foreground_identity["uniqueId"], "IDENTITY")
        self.native.watch(self.sentinel_identity)
        self.sentinel_pipes = Pipes(self.sentinel, "sentinel")
        left(end_ns)

    def _pump_case(self):
        state = self.current
        self.native.poll()
        self.native.same(self.foreground_identity)
        if self.sentinel is not None:
            self.sentinel_pipes.pump()
            require(self.sentinel.poll() is None and self.sentinel.pid not in self.native.events,
                    "CLOSE", "SENTINEL_LOST")
        service_identity, producer_identity = state["service"], state["producer"]
        if (state["started"] and service_identity["pid"] in self.native.events and state["final"] is None and
                producer_identity["pid"] not in self.native.events and not state["cancelAttempted"]):
            state["cancelAttempted"] = True
            self.native.signal_orphan(producer_identity, service_identity, state["producerSession"], state["end"])
        if self.profile is QUALIFICATION and state["started"] and not state["actionDone"]:
            self._qualifier_action(state)
        if service_identity is not None and service_identity["pid"] in self.native.events and not state["started"]:
            raise ContextError("START", "SERVICE_DIED_BEFORE_START")
        left(state["end"])

    def _qualifier_action(self, state):
        require(self.profile is QUALIFICATION, "START", "PROFILE")
        ready_path = state["directory"] / "product-ready.json"
        if not os.path.lexists(ready_path):
            require(shared_raw_ns() < min(state["end"], state["startReturnedNs"] + 15 * NS), "START", "PRODUCT_READY_TIMEOUT")
            return
        ready_raw = read_file(ready_path)
        ready = parsed(ready_raw)
        keys = {"schema", "scope", "case", "binding", "contextId", "invocationId", "pid", "parentPid", "account", "ownership",
                "sourceSha256", "sigtermDefault", "sigtermBlocked", "readyMonotonicNs"}
        entry, entry_hash = read_canonical_entry(self.profile, state["directory"], state["inputs"], state["inputHash"])
        require(entry == state["entry"] and entry_hash == state["entryHash"], "START", "CANONICAL_ENTRY")
        require(type(ready) is dict and set(ready) == keys and type(ready["schema"]) is int and ready["schema"] == 1 and
                ready["scope"] == self.profile.scope and ready["case"] == entry["case"] and ready["binding"] == entry["binding"] and
                ready["contextId"] == entry["contextId"] and ready["invocationId"] == entry["invocationId"] and
                type(ready["pid"]) is int and ready["pid"] > 0 and ready["parentPid"] == state["producer"]["pid"] and
                ready["sigtermDefault"] is True and ready["sigtermBlocked"] is False and type(ready["readyMonotonicNs"]) is int and
                state["startSentNs"] <= ready["readyMonotonicNs"] <= shared_raw_ns() < state["end"], "START", "PRODUCT_READY")
        validate_account(ready["account"], self.account)
        canonical_state = self.operation / "states" / entry["case"]
        ownership = {"jobId": entry["contextId"], "chain": entry["invocationId"],
                     "domains": [{"id": entry["invocationId"], "job": entry["contextId"], "state": str(canonical_state),
                                  "home": str(canonical_state / "gradle-home")}],
                     "state": str(canonical_state), "home": str(canonical_state / "gradle-home")}
        require(ready["ownership"] == ownership and
                ready["sourceSha256"] == digest(read_file(self.operation / "fixture/fixture.py")), "START", "PRODUCT_READY")
        start_raw = read_file(canonical_state / "evidence" / entry["invocationId"] / "start.json", EVIDENCE_BYTES)
        start = parsed(start_raw, EVIDENCE_BYTES)
        argv = [self.interpreter["path"], "-I", "-B", "-S", str(self.operation / "fixture/fixture.py"), "--product", entry["case"]]
        require(start.get("schema") == 1 and start.get("id") == entry["invocationId"] and
                start.get("jobId") == entry["contextId"] and start.get("controllerPid") == state["producer"]["pid"] and
                start.get("kind") == "command" and start.get("purpose") == "dependency-context-" + entry["case"].lower() and
                start.get("requestedArgv") == argv and start.get("cwd") == str(self.operation / "fixture") and
                start.get("wrapper") == str(self.operation / "fixture/gradlew") and start.get("host") == "macos-arm64" and
                start.get("gradleHome") == str(canonical_state / "gradle-home") and
                all(start.get(key) is None for key in ("sourceBefore", "sourceAfter", "productExitCode", "stopExitCode")) and
                "productPid" not in start and "executedArgv" not in start, "START", "CANONICAL_START")
        self.native.same(state["service"])
        self.native.same(state["producer"])
        product = self.native.identity(ready["pid"])
        identity_account(product, self.account)
        require(product["parentPid"] == state["producer"]["pid"] and
                product["parentUniqueId"] == state["producer"]["uniqueId"], "IDENTITY", "PRODUCT_PARENT")
        self.native.watch(product)
        self.native.same(product)
        state["product"] = product
        state["actionDone"] = True  # One original action attempt; never an automatic retry.
        started = shared_raw_ns()
        if entry["case"] in ("Q1", "Q2"):
            kind = "RELEASE"
            returned = write_new(state["directory"] / "product-release.json", encoded({"schema": 1,
                "scope": self.profile.scope, "case": entry["case"], "binding": entry["binding"],
                "readySha256": digest(ready_raw), "releasedMonotonicNs": started}))
        elif entry["case"] == "Q3":
            kind = "F_WRITE_EOF"
            returned = state["channel"].shutdown(socket.SHUT_WR)
        else:
            require(entry["case"] == "Q4", "START", "CASE")
            kind = "D_SIGKILL"
            returned = self.native.signal(state["service"], signal.SIGKILL, state["end"])
        state["action"] = {"kind": kind, "canonicalEntrySha256": entry_hash, "canonicalStartSha256": digest(start_raw),
                           "productReadySha256": digest(ready_raw), "startedRawNs": started,
                           "returnedRawNs": shared_raw_ns(), "returnedValue": returned}

    def run_case(self, case, input_path):
        require(not self.finished and not self.failed and not self._aborted and self.current is not None and
                case == self.current["common"]["case"] and input_path == self.current["directory"] / "case-input.json",
                "START", "CASE_ORDER")
        try:
            return self._run_current_case()
        except BaseException as error:
            self.attach_startup_failure(error)
            self.failed = True
            self.abort()
            raise

    def _run_current_case(self):
        self._set_startup_phase("INPUTS_AND_ADMIN")
        self._original_data()
        state = self.current
        inputs, input_hash = case_input(self.profile, state["directory"])
        require({key: inputs[key] for key in CASE_INPUT_KEYS} == state["common"], "START", "CASE_INPUT_CHANGED")
        state["inputs"], state["inputHash"] = inputs, input_hash
        end_ns, directory = state["end"], state["directory"]
        if self.profile is QUALIFICATION and self.sentinel is None:
            self._start_sentinel(end_ns)
        state["registrationStart"] = len(self.native.attach_attempts)
        label = "p2pkit.context.r" + self.github["runId"] + ".a" + self.github["runAttempt"] + "." + inputs["case"].lower() + "." + inputs["binding"][:16]
        admin = state["admin"] = Admin(self, directory, label, end_ns)
        if not self.outcomes:
            for name in (*OS_PARENTS, *OS_TOOLS):
                observed = admin.metadata(name, "directory" if name in OS_PARENTS else "file")
                require([observed[key] for key in ("dev", "ino", "mode", "uid", "gid")] +
                        ([observed["nlink"]] if name in OS_TOOLS else []) == self.os_files[name], "SOURCE", "OS_OBJECT_CHANGED")
        else:
            for name, original in self.os_files.items():
                info = physical(name).lstat()
                require([info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid] +
                        ([info.st_nlink] if name in OS_TOOLS else []) == original, "SOURCE", "OS_OBJECT_CHANGED")
        self._set_startup_phase("SOCKET_PREPARE")
        path = directory / "control.sock"
        require(len(str(path).encode("utf-8")) + 1 <= 104, "START", "SOCKET_PATH")
        listener = state["listener"] = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(path))
        os.chmod(path, 0o600)
        state["socket"] = socket_identity(path)
        listener.listen(1)
        listener.setblocking(False)
        prepared = state["prepared"] = {"schema": 1, "scope": self.profile.scope, "binding": inputs["binding"],
                    "case": inputs["case"], "github": self.github, "allocation": self.allocation, "source": self.source,
                    "account": self.account, "foreground": self.foreground_identity, "boot": self.boot,
                    "interpreter": self.interpreter, "directoryIdentity": private_directory(directory),
                    "operationIdentity": self.operation_identity, "socketIdentity": state["socket"],
                    "caseInputSha256": input_hash, "caseEndNs": end_ns, "stepEndNs": self.step_end_ns,
                    "jobEndNs": self.job_end_ns, "policyEndNs": self.policy_end_ns, "tools": self.tools}
        require(len(encoded(prepared)) <= FRAME_BYTES, "START", "BOUND")
        write_new(directory / "prepared.json", encoded(prepared))
        self._set_startup_phase("LAUNCHER_CREATE")
        admin.create()
        self._set_startup_phase("BOOTSTRAP")
        admin.bootstrap()
        self._start_startup_probe(end_ns)
        self._set_startup_phase("WAIT_CONNECT")
        while state["channel"] is None:
            ready, _, _ = select.select([listener], [], [], min(0.05, left(end_ns)))
            if ready:
                channel, _address = listener.accept()
                state["channel"] = channel
                channel.setblocking(False)
                close_socket(listener)
                state["listener"] = None
            elif self.profile is STARTUP:
                self._startup_wait_check()
        channel, trace = state["channel"], state["trace"]
        self._set_startup_phase("PEER_CHECK")
        peer = self.native.peer(channel)
        self._set_startup_phase("WAIT_HELLO")
        hello = (self._read_startup_hello(channel, inputs["binding"], trace, end_ns) if self.profile is STARTUP
                 else read_frame(channel, 1, inputs["binding"], trace, end_ns))["payload"]
        self._set_startup_phase("HELLO_CHECK")
        require(type(hello) is dict and set(hello) == {"service", "account", "foregroundPeer", "boot", "sourceSha256",
                "interpreter", "directoryIdentity"}, "IDENTITY")
        same_identity(hello["service"], peer)
        same_identity(hello["foregroundPeer"], self.foreground_identity)
        identity_account(peer, self.account)
        validate_account(hello["account"], self.account)
        require(peer["parentPid"] == 1 and hello["boot"] == self.boot and hello["sourceSha256"] == self.source["files"][self.profile.script] and
                hello["interpreter"] == self.interpreter and hello["directoryIdentity"] == prepared["directoryIdentity"],
                "IDENTITY", "IDENTITY_CHANGED")
        state["service"] = peer
        self._set_startup_phase("INSPECT_AND_ATTACH")
        admin.inspect(peer)
        self.native.watch(peer)
        state["prepareSent"] = True
        send_frame(channel, 2, inputs["binding"], prepared, trace, end_ns)
        self._set_startup_phase("WAIT_CHILD_READY")
        forwarding = read_frame(channel, 4, inputs["binding"], trace, end_ns, self._pump_case)["payload"]
        self._set_startup_phase("CHILD_READY_CHECK")
        require(type(forwarding) is dict and set(forwarding) == {"readyFrame", "producerBirth"}, "START")
        ready = forwarding["readyFrame"]
        data = validate_frame(ready, 3, inputs["binding"])
        require(type(data.get("producer")) is dict and type(data["producer"].get("pid")) is int, "IDENTITY")
        observed = self.native.identity(data["producer"]["pid"])
        entry, entry_hash, producer_session, service_session = validate_ready(
            self.profile, ready, prepared, peer, observed, directory)
        birth = forwarding["producerBirth"]
        same_identity(birth, birth)
        require(all(birth[key] == observed[key] for key in IDENTITY_KEYS - {"status", "pidVersion"}), "IDENTITY", "STARTUP_BIRTH")
        state.update(producer=observed, producerBirth=birth, producerSession=producer_session,
                     serviceSession=service_session, entry=entry, entryHash=entry_hash)
        self.native.watch(observed)  # Holds opaque token against post-READY full image, not provisional birth.
        self.native.same(peer)
        self.native.same(observed)
        self._set_startup_phase("START_HANDOFF")
        start = start_payload(prepared, peer, entry_hash)
        started = shared_raw_ns()
        require(all(self.native.registrations[value["pid"]]["recheckedMonotonicNs"] <= started for value in (peer, observed)),
                "START", "ATTACH_ORDER")
        send_frame(channel, 5, inputs["binding"], start, trace, end_ns)
        state["startSentNs"] = started
        state["startReturnedNs"], state["started"] = shared_raw_ns(), True
        self._set_startup_phase("WAIT_FINAL")
        reader = state["reader"] = FrameReader(channel, 8, inputs["binding"], trace)
        while True:
            # Drain an already-returned final frame before reacting to D's exit;
            # a normal completed D must not be mistaken for active D loss.
            if reader.value is None and not reader.eof:
                reader.poll()
                if reader.value is not None:
                    state["final"] = reader.value["payload"]
            self._pump_case()
            required = [peer, observed] + ([state["product"]] if state["product"] is not None else [])
            if all(value["pid"] in self.native.events for value in required) and (reader.value is not None or reader.eof):
                break
            select.select([] if reader.eof or reader.value is not None else [channel], [], [], min(0.02, left(end_ns)))
        self._set_startup_phase("FINAL_VALIDATE")
        expected_loss = self.profile is QUALIFICATION and inputs["case"] == "Q4" and state["action"]["kind"] == "D_SIGKILL"
        try:
            require(state["final"] is not None or expected_loss, "CLOSE", "FINAL_FRAME_MISSING")
        except ContextError as error:
            if self.profile is QUALIFICATION:
                with contextlib.suppress(BaseException):
                    attach_failure_hint(self.profile, state, self.native.events, error)
            raise
        if not reader.eof:
            wait_eof(channel, end_ns, self._pump_case)
        close_socket(channel)
        state["channel"] = None
        result_raw = read_file(directory / "producer-result.json")
        result = validate_producer_result(self.profile, parsed(result_raw), entry, input_hash)
        require(result["canonicalEntrySha256"] == entry_hash and result["completedRawNs"] < end_ns and
                self.native.events[observed["pid"]]["status"]["popenCode"] == result["code"], "CLOSE", "PRODUCER_RESULT")
        if (self.profile is GENERATION or self.profile is STARTUP) and 0 <= result["code"] <= 123:
            end_ns = min(end_ns, result["commands"][-1]["returnedRawNs"] + 300 * NS)
            state["end"], admin.end_ns = end_ns, end_ns
        left(end_ns, "CLOSE")
        capture_manifest = parsed(read_file(directory / "producer-captures.json"))
        require(type(capture_manifest) is dict and set(capture_manifest) ==
                {"schema", "case", "binding", "producerResultSha256", "captures", "nativeClosed"} and
                capture_manifest["schema"] == 1 and capture_manifest["case"] == inputs["case"] and
                capture_manifest["binding"] == inputs["binding"] and capture_manifest["producerResultSha256"] == digest(result_raw) and
                capture_manifest["nativeClosed"] is True, "CLOSE", "PRODUCER_CAPTURES")
        verify_capture_rows(directory, capture_manifest["captures"], ("producer-controller.stdout", "producer-controller.stderr"))
        delivery = parsed(read_file(directory / "producer-delivery.json"))
        require(type(delivery) is dict and set(delivery) ==
                {"schema", "case", "binding", "resultSha256", "delivered", "failure", "channelClosed", "closedRawNs"} and
                delivery["schema"] == 1 and delivery["case"] == inputs["case"] and delivery["binding"] == inputs["binding"] and
                delivery["resultSha256"] == digest(result_raw) and delivery["channelClosed"] is True and
                type(delivery["closedRawNs"]) is int and result["completedRawNs"] <= delivery["closedRawNs"] < end_ns,
                "CLOSE", "PRODUCER_DELIVERY")
        final, d_registrations, d_signals = state["final"], [], []
        if final is not None:
            require(not expected_loss and delivery["delivered"] is True and delivery["failure"] is None,
                    "CLOSE", "PRODUCER_DELIVERY")
            self._validate_final(state, result_raw, ready, start)
            # Preserve the actual received, validated full F8 frame. Q4 has no
            # such writer/frame and must not acquire a substitute closure file.
            write_new(directory / "service-final.json", encoded(reader.value))
            d_registrations, d_signals = final["registrations"], final["signalReturns"]
            verify_capture_rows(directory, final["producerStreams"], ("producer-pipe.stdout", "producer-pipe.stderr"), pipes=True)
            verify_capture_rows(directory, final["serviceStreams"], ("service.stdout", "service.stderr"))
        else:
            require(expected_loss and self.native.events[peer["pid"]]["status"]["popenCode"] == -signal.SIGKILL and
                    delivery["delivered"] is False and type(delivery["failure"]) is str and
                    delivery["failure"].endswith(("/EPIPE", "/ECONNRESET")), "CLOSE", "D_LOSS")
            # Only kernel-observed sole-writer death permits these incomplete
            # bytes. No D wait, EOF, close/fsync or final frame is fabricated.
            for name in ("service.stdout", "service.stderr", "producer-pipe.stdout", "producer-pipe.stderr"):
                if os.path.lexists(directory / name):
                    read_file(directory / name)
        if self.profile is QUALIFICATION and inputs["case"] in ("Q3", "Q4"):
            require(self.sentinel.poll() is None, "CLOSE", "SENTINEL_LOST")
            self.sentinel_observations.append({"case": inputs["case"], "identity": self.native.same(self.sentinel_identity),
                                               "observedRawNs": shared_raw_ns()})
        self._set_startup_phase("RETIRE")
        admin.retire(peer)
        require(socket_identity(path) == state["socket"], "RETIRE", "IDENTITY_CHANGED")
        path.unlink()
        require(not os.path.lexists(path), "RETIRE", "RESOURCE_UNKNOWN")
        state["socket"] = None
        admin.close()
        writers_retired = (all(value["pid"] in self.native.events for value in (peer, observed)) and
                           capture_manifest["nativeClosed"] is True and delivery["channelClosed"] is True and
                           (expected_loss or final["capturesClosed"] is True and final["producerControlEof"] is True) and
                           not _UNCLOSED_COMMANDS)
        require(writers_retired, "CLOSE", "RESOURCE_UNKNOWN")
        native_record = {"foreground": self.foreground_identity, "service": peer, "producerBirth": birth, "producer": observed,
            "serviceSession": service_session, "producerSession": producer_session, "product": state["product"],
            "producerNative": self.native.events[observed["pid"]], "serviceNative": self.native.events[peer["pid"]],
            "productNative": self.native.events[state["product"]["pid"]] if state["product"] is not None else None,
            "registrations": [{"observer": "F", "observation": row} for row in
                              self.native.attach_attempts[state["registrationStart"]:]] + d_registrations,
            "signalReturns": self.native.signals[state["signalStart"]:] + d_signals}
        closure = {"producerWait": final["producerCode"] if final is not None else "ABSENT_D_DIED",
            "producerPipeEof": True if final is not None else "ABSENT_D_DIED",
            "producerPipeCaptures": "CLOSED" if final is not None else "INCOMPLETE_D_DIED", "producerRecords": "CLOSED",
            "serviceFinalFrame": "RECEIVED" if final is not None else "ABSENT_D_DIED",
            "serviceCaptures": "CLOSED" if final is not None else "INCOMPLETE_D_DIED",
            "producerNativeExit": observed["pid"] in self.native.events, "serviceNativeExit": peer["pid"] in self.native.events,
            "controlEof": True, "controlClosed": True, "registrationAbsent": admin.retired,
            "rootObjectsRemoved": admin.removed, "adminClosed": admin.closed, "soleWritersRetired": writers_retired,
            "nativeRetention": "HELD_UNTIL_SUITE_FINISH"}
        loss = {key: closure[key] for key in ("producerWait", "producerPipeEof", "serviceFinalFrame", "producerPipeCaptures", "serviceCaptures")} if expected_loss else {}
        record = {"schema": 1, "scope": self.profile.scope, "case": inputs["case"], "binding": inputs["binding"],
            "caseInputSha256": input_hash, "canonicalEntrySha256": entry_hash, "producerResultSha256": digest(result_raw),
            "native": native_record, "action": state["action"], "closure": closure, "lossAnnotations": loss,
            "caseStartNs": inputs["caseStartNs"], "caseEndNs": inputs["caseEndNs"], "closedMonotonicNs": shared_raw_ns()}
        write_new(directory / "native-observations.json", encoded(native_record))
        write_new(directory / "action-observation.json", encoded(state["action"]))
        write_new(directory / "bridge-protocol.json", encoded({"schema": 1, "case": inputs["case"], "binding": inputs["binding"],
                  "preparedSha256": digest(encoded(prepared)), "foregroundTrace": trace, "readyFrame": ready,
                  "startSend": {"startedRawNs": started, "returnedRawNs": state["startReturnedNs"]},
                  "serviceFinalData": final}))
        write_new(directory / "bridge-result.json", encoded(record))
        left(end_ns, "CLOSE")
        outcome = CaseOutcome(self, record)
        self.outcomes.append(outcome)
        self.current, self._finish_end = None, end_ns
        return outcome

    def _validate_final(self, state, result_raw, ready, start):
        final = state["final"]
        keys = {"case", "producerCode", "producerStreams", "serviceStreams", "resultFrame", "tracePrefix", "producerControlEof",
                "producerWait", "nativeClosed", "capturesClosed", "signalReturns", "registrations", "producerNative",
                "foregroundLoss", "startForward"}
        require(type(final) is dict and set(final) == keys and final["case"] == state["inputs"]["case"] and
                all(final[key] is True for key in ("producerControlEof", "producerWait", "nativeClosed", "capturesClosed")) and
                type(final["producerCode"]) is int and
                final["producerCode"] == self.native.events[state["producer"]["pid"]]["status"]["popenCode"],
                "CLOSE", "SERVICE_RESULT")
        prefix = final["tracePrefix"]
        require(type(prefix) is list and [row["serial"] for row in prefix] == list(range(1, 8)), "START", "FRAME_ORDER")
        joined = {row["serial"]: row for row in prefix}
        require(all(joined[row["serial"]] == row for row in state["trace"][:-1]) and joined[3] == frame_record(ready) and
                joined[6] == frame_record(frame_value(6, state["inputs"]["binding"], start)) and
                joined[7] == frame_record(final["resultFrame"]), "START", "FRAME_CHANGED")
        result = validate_frame(final["resultFrame"], 7, state["inputs"]["binding"])
        require(type(result) is dict and set(result) == {"case", "producerResultSha256", "producerCapturesSha256", "code"} and
                result["case"] == state["inputs"]["case"] and type(result["code"]) is int and
                result["producerResultSha256"] == digest(result_raw) and
                result["producerCapturesSha256"] == digest(read_file(state["directory"] / "producer-captures.json")) and
                result["code"] == final["producerCode"], "CLOSE", "SERVICE_RESULT")
        forward = final["startForward"]
        require(type(forward) is dict and set(forward) == {"startedMonotonicNs", "returnedMonotonicNs"} and
                all(type(value) is int for value in forward.values()) and
                state["startSentNs"] <= forward["startedMonotonicNs"] <= forward["returnedMonotonicNs"] < state["end"],
                "START", "TIMEOUT")
        registrations = final["registrations"]
        require(type(registrations) is list and len(registrations) == 2, "CLOSE", "SERVICE_REGISTRATIONS")
        for wrapped, identity in zip(registrations, (self.foreground_identity, state["producer"])):
            require(type(wrapped) is dict and set(wrapped) == {"observer", "observation"} and
                    wrapped["observer"] == "D", "CLOSE", "SERVICE_REGISTRATIONS")
            row = wrapped["observation"]
            require(type(row) is dict and set(row) == {"identity", "startedMonotonicNs", "returnedMonotonicNs",
                    "recheckedMonotonicNs", "requested", "receipts"}, "CLOSE", "SERVICE_REGISTRATIONS")
            same_identity(row["identity"], identity)
            require(all(type(row[key]) is int for key in ("startedMonotonicNs", "returnedMonotonicNs", "recheckedMonotonicNs")) and
                    state["inputs"]["caseStartNs"] <= row["startedMonotonicNs"] <= row["returnedMonotonicNs"] <=
                    row["recheckedMonotonicNs"] <= state["startSentNs"] and row["requested"] ==
                    {"ident": identity["pid"], "filter": EVFILT_PROC, "flags": EV_ADD | EV_ENABLE | EV_RECEIPT,
                     "fflags": NOTE_EXIT | NOTE_EXITSTATUS}, "CLOSE", "SERVICE_REGISTRATIONS")
            receipts = row["receipts"]
            require(type(receipts) is list and len(receipts) == 1 and type(receipts[0]) is dict and
                    set(receipts[0]) == {"ident", "filter", "flags", "fflags", "data"} and
                    all(type(value) is int for value in receipts[0].values()) and receipts[0]["ident"] == identity["pid"] and
                    receipts[0]["filter"] == EVFILT_PROC and receipts[0]["flags"] & EV_ERROR and receipts[0]["data"] == 0,
                    "CLOSE", "SERVICE_REGISTRATIONS")
        terminal = final["producerNative"]
        require(type(terminal) is dict and set(terminal) == {"event", "status", "observedRawNs"} and
                terminal["status"] == decode_exit_event(terminal["event"], state["producer"]["pid"]) and
                type(terminal["observedRawNs"]) is int and forward["returnedMonotonicNs"] <=
                terminal["observedRawNs"] < state["end"] and
                terminal["event"] == self.native.events[state["producer"]["pid"]]["event"] and
                terminal["status"] == self.native.events[state["producer"]["pid"]]["status"],
                "CLOSE", "STATUS_UNEXPECTED")
        loss = final["foregroundLoss"]
        signals = final["signalReturns"]
        require(type(signals) is list, "CLOSE", "SERVICE_SIGNALS")
        if self.profile is QUALIFICATION and state["inputs"]["case"] == "Q3":
            require(type(loss) is dict and set(loss) == {"kind", "observedRawNs"} and loss["kind"] == "WRITE_EOF" and
                    type(loss["observedRawNs"]) is int and state["action"]["startedRawNs"] <= loss["observedRawNs"] and
                    len(signals) == 1 and type(signals[0]) is dict and
                    set(signals[0]) == {"signaler", "observation", "orphan"} and
                    signals[0]["signaler"] == "D" and signals[0]["orphan"] is None,
                    "CLOSE", "FOREGROUND_EOF")
            sent = signals[0]["observation"]
            require(type(sent) is dict and set(sent) == {"identity", "signal", "returnedCode", "startedMonotonicNs",
                    "returnedMonotonicNs"} and all(type(sent[key]) is int for key in
                    ("signal", "returnedCode", "startedMonotonicNs", "returnedMonotonicNs")) and
                    sent["signal"] == signal.SIGTERM and sent["returnedCode"] == 0 and
                    loss["observedRawNs"] <= sent["startedMonotonicNs"] <= parsed(result_raw)["commands"][-1]["returnedRawNs"] and
                    sent["startedMonotonicNs"] <= sent["returnedMonotonicNs"] <=
                    self.native.events[state["service"]["pid"]]["observedRawNs"], "CLOSE", "FOREGROUND_EOF")
            same_identity(sent["identity"], state["producer"])
        else:
            require(loss is None and signals == [], "CLOSE", "FOREGROUND_LOSS")

    def production_result(self, outcome):
        require(type(outcome) is CaseOutcome and outcome._owner is self and any(outcome is item for item in self.outcomes) and
                not self.failed and not self._aborted, "CLOSE", "ORIGINAL_OUTCOME")
        return validate_production_data(parsed(outcome._raw, EVIDENCE_BYTES))

    def _close_sentinel(self, end_ns):
        require(self.sentinel is not None and not self.sentinel_closed, "CLOSE")
        self.native.same(self.sentinel_identity)
        self.sentinel.stdin.close()
        require(self.sentinel.stdin.closed, "CLOSE", "RESOURCE_UNKNOWN")
        code, streams = self.sentinel_pipes.finish(end_ns, self.operation / "bridge/sentinel")
        native = self.native.wait([self.sentinel_identity], end_ns)[self.sentinel.pid]
        require(code == 0 and native["status"]["popenCode"] == 0 and self.sentinel_pipes.closed, "CLOSE", "SENTINEL_LOST")
        write_new(self.operation / "bridge/sentinel/native-exit.json", encoded(native))
        self.sentinel_closed = True
        return {"identity": self.sentinel_identity, "survivalObservations": self.sentinel_observations,
                "waitCode": code, "streams": streams, "closed": True}

    def finish(self):
        require(not self.finished and not self.failed and not self._aborted and self.current is None and
                [item.record["case"] for item in self.outcomes] == list(self.profile.cases), "CLOSE", "SUITE_ORDER")
        self._original_data()
        end_ns = self._finish_end
        sentinel = self._close_sentinel(end_ns) if self.profile is QUALIFICATION else None
        if sentinel is not None:
            require([row["case"] for row in sentinel["survivalObservations"]] == ["Q3", "Q4"], "CLOSE", "SENTINEL_ROSTER")
        self.native.same(self.foreground_identity)
        source, returns = source_snapshot(self.profile, end_ns, self.environment)
        require(source == self.source and checked_interpreter(end_ns) == self.interpreter and not _UNCLOSED_COMMANDS,
                "SOURCE", "IDENTITY_CHANGED")
        self.native.close()
        record = {"schema": 1, "scope": self.profile.scope, "github": self.github, "repositorySource": self.repository_source,
                  "allocationSha256": self.allocation_hash,
                  "cases": [{"case": item.record["case"], "bridgeResultSha256": digest(item._raw)} for item in self.outcomes],
                  "sentinel": sentinel, "nativeClosed": self.native.closed, "closedMonotonicNs": shared_raw_ns()}
        write_new(self.operation / "bridge/source-after.json", encoded({"source": source, "returns": returns}))
        write_new(self.operation / "bridge/suite-closed.json", encoded(record))
        files = self._closed_files()
        left(end_ns, "CLOSE")
        self.finished = True
        return {**record, "evidenceFiles": files}

    def _closed_files(self):
        """Finite source-owned roster after all original writers have retired."""
        bridge = self.operation / "bridge"
        root_files = {"foreground.json", "source-after.json", "suite-closed.json"}
        directories = {"cases"} | ({"sentinel"} if self.profile is QUALIFICATION else set())
        rosters = [(bridge, root_files, set(), directories),
                   (bridge / "cases", set(), set(), set(self.profile.cases))]
        for case in self.profile.cases:
            required, optional = set(CASE_FILES), set()
            if self.profile is QUALIFICATION:
                required.update(("product-ready.json", "case-result.json"))
                if case in ("Q1", "Q2"):
                    required.add("product-release.json")
            if self.profile is QUALIFICATION and case == "Q4":
                # Kernel-observed original D death closes its writers, not its
                # userspace wait/fsync/EOF. Absent streams remain absent; any
                # retained bytes keep the case's INCOMPLETE_D_DIED annotation.
                optional.update(SERVICE_FILES)
            else:
                required.update(SERVICE_FILES)
                required.add("service-final.json")
            rosters.append((bridge / "cases" / case, required, optional, set()))
        if self.profile is QUALIFICATION:
            rosters.append((bridge / "sentinel", {"sentinel.stdout", "sentinel.stderr", "native-exit.json"}, set(), set()))
        files, total = [], 0
        for directory, required, optional, child_directories in rosters:
            private_directory(directory)
            allowed, seen = required | optional | child_directories, set()
            for path in directory.iterdir():
                require(path.name in allowed and path.name not in seen, "FREEZE", "UNKNOWN_BRIDGE_MEMBER")
                seen.add(path.name)
                if path.name in child_directories:
                    private_directory(path)
                    continue
                info = physical(path).lstat()
                require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600,
                        "FREEZE", "BRIDGE_FILE_TYPE")
                maximum = (STREAM_BYTES if path.suffix in (".stdout", ".stderr", ".plist") else
                           EVIDENCE_BYTES // 4 if path.name == "admin.jsonl" else EVIDENCE_BYTES)
                raw = read_file(path, maximum)
                total += len(raw)
                require(total <= 512 * 1024 * 1024, "FREEZE", "BOUND")
                files.append({"path": path.relative_to(self.operation).as_posix(), "bytes": len(raw), "sha256": digest(raw)})
            require(required | child_directories <= seen, "FREEZE", "MISSING_BRIDGE_MEMBER")
        return sorted(files, key=lambda row: row["path"])

    def abort(self):
        if self._aborted:
            return self._abort_result
        self._aborted, self.failed = True, True
        end_ns = min(shared_raw_ns() + ABORT_SECONDS * NS, self.step_end_ns, self.job_end_ns, self.policy_end_ns)
        failures, state = [], self.current

        def attempt(operation):
            try:
                operation()
                return True
            except BaseException as error:
                failures.append(public_error(error))
                return False

        if state is not None:
            channel = state["channel"]
            if channel is not None and channel.fileno() != -1:
                attempt(lambda: channel.shutdown(socket.SHUT_WR))
            if self.native is not None:
                attempt(self.native.poll)
                producer_identity, service_identity = state["producer"], state["service"]
                if (producer_identity is not None and producer_identity["pid"] in self.native.watched and
                        producer_identity["pid"] not in self.native.events and not state["cancelAttempted"]):
                    state["cancelAttempted"] = True
                    if service_identity is not None and service_identity["pid"] in self.native.events:
                        attempt(lambda: self.native.signal_orphan(producer_identity, service_identity, state["producerSession"], end_ns))
                    else:
                        attempt(lambda: self.native.signal(producer_identity, signal.SIGTERM, end_ns))
                identities = [value for value in (producer_identity, service_identity) if value is not None]
                watched = [value for value in identities if value["pid"] in self.native.watched]
                closed = bool(watched) and attempt(lambda: self.native.wait(watched, end_ns))
                admin = state["admin"]
                known = len(watched) == len(identities) and (producer_identity is not None or not state["prepareSent"])
                if closed and known and admin is not None and admin.service is not None and not admin.retired and not _UNCLOSED_COMMANDS:
                    admin.end_ns = end_ns
                    attempt(lambda: admin.retire(service_identity))
            for name in ("listener", "channel"):
                stream = state[name]
                if stream is not None and stream.fileno() != -1:
                    attempt(lambda stream=stream: close_socket(stream))
            if state["socket"] is not None:
                def remove_socket():
                    path = state["directory"] / "control.sock"
                    require(socket_identity(path) == state["socket"], "CLOSE", "IDENTITY_CHANGED")
                    path.unlink()
                attempt(remove_socket)
            if state["admin"] is not None and not state["admin"].closed:
                attempt(state["admin"].close)
        if self.sentinel is not None and not self.sentinel_closed:
            attempt(lambda: self._close_sentinel(end_ns))
        if self.native is not None and not self.native.closed:
            attempt(self.native.close)
        self._abort_result = {"schema": 1, "scope": self.profile.scope, "exportAllowed": False,
                              "cleanupErrors": failures, "adminLifetimeUnknown": bool(_UNCLOSED_COMMANDS), "abortEndNs": end_ns}
        if (self.operation / "bridge").is_dir():
            attempt(lambda: write_new(self.operation / "bridge/aborted-no-export.json", encoded(self._abort_result)))
        return copy_data(self._abort_result)
