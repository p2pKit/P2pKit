#!/usr/bin/env python3
"""One manual, nonproductive Darwin context experiment; never a release owner.

The only network workload is one fixed synthetic IPv4 multicast datagram.
Real status/EOF/retirement, not final DATA, gates the original foreground's
single public encrypted export. Source/offline controls are not native proof.
"""
from __future__ import annotations

import contextlib
import ctypes
import errno
import hashlib
import importlib.util
import ipaddress
import json
import math
import os
from pathlib import Path
import platform
import plistlib
import pwd
import grp
import re
import select
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = "scripts/run-hosted-darwin-context-experiment.py"
WORKFLOW = ".github/workflows/darwin-native-context-experiment.yml"
REPOSITORY = "p2pKit/P2pKit"
OWNER, OWNER_ID = "Apdelrahman1911", "104788132"
SCOPE = "MANUAL_DARWIN_CONTEXT_EXPERIMENT_V1"
REQUEST_KEYS = {"source_sha", "source_tree"}
CASES = ("N1", "N2", "N3", "N4")
SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
NUMBER = re.compile(r"[1-9][0-9]{0,19}\Z")
REF = re.compile(r"refs/heads/work/release-foundation-context-[A-Za-z0-9-]+\Z")
NS = 1_000_000_000
JOB_SECONDS, STEP_SECONDS = 1440, 720
PREPARE_SECONDS, NATIVE_SECONDS, CASE_SECONDS = 120, 180, 40
ABORT_SECONDS, FREEZE_SECONDS, EXPORT_SECONDS = 120, 60, 120
UPLOAD_SECONDS, ADMIN_SECONDS = 420, 10  # two60s guards and one300s upload
FRAME_BYTES, STREAM_BYTES, EVIDENCE_BYTES, EVIDENCE_MEMBERS = 16384, 65536, 2 * 1024 * 1024, 128
JSON_DEPTH, JSON_NODES = 32, 4096
POLICY_PATH = ".github/test-evidence-recipient.json"
# These are the existing independently owner-decided public policy/key pins.
# A candidate or this experiment cannot authorize/renew its own recipient.
POLICY_SHA256 = "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521"
KEY_SHA256 = "5dcb108725ffb2a9c99f4e61e35c3473d34776530effca7385282faf62b86aaf"
FINGERPRINT = "0A996D2BC19518FB50071A95D3FDADA57CFB7E1F"
ENCRYPTION_FINGERPRINT = "4D7CF63A16AFC0BDDC82F3E686D7D3D9A7B44350"
KEY_EXPIRES = 1821484800
POLICY_EXPIRES = 1791158400  # 2026-10-05T00:00:00Z; not extended here
LATEST_ENTRY = "2026-10-04T20:30:00Z"
QUERY = bytes.fromhex("000000000001000000000000127032706b69742d61756469742d70726f6265056c6f63616c0000010001")
OWNER_ENV = ("P2PKIT_AUDIT_JOB_ID", "P2PKIT_AUDIT_OWNERSHIP_CHAIN", "P2PKIT_AUDIT_OWNERSHIP_DOMAINS",
             "P2PKIT_AUDIT_STATE_DIR", "GRADLE_USER_HOME")
STAGES = frozenset(("PREPARE", "SOURCE", "POLICY", "ADMIN_CREATE", "BOOTSTRAP", "IDENTITY", "ATTACH", "START",
                    "NATIVE_SEND", "CHILD_WAIT", "SERVICE_WAIT", "RETIRE", "CLOSE", "FREEZE", "EXPORT", "UPLOAD"))
REASONS = frozenset(("UNSUPPORTED", "REFUSED", "IDENTITY_CHANGED", "PERMISSION_DENIED", "TIMEOUT", "RETURN_FAILED",
                     "STATUS_MISSING", "STATUS_UNEXPECTED", "RESOURCE_UNKNOWN", "BOUND", "EXPORT_FAILED", "UPLOAD_FAILED"))
ERRNOS = frozenset(("EPERM", "EACCES", "ENOENT", "ESRCH", "EINTR", "EPIPE", "EINVAL", "EADDRINUSE", "ENETUNREACH",
                    "EHOSTUNREACH", "ECONNRESET", "ETIMEDOUT", "NONE", "UNKNOWN"))
# Pinned XNU f6217f891ac0bb64f3d375211650a4c1ff8ca1ea, event.h and un.h.
# Python does not necessarily expose every Darwin constant. Actual native
# registration/returned flags and permissions are still required, never inferred.
EVFILT_PROC, EV_ADD, EV_ENABLE, EV_RECEIPT, EV_ERROR, EV_EOF = -5, 0x1, 0x4, 0x40, 0x4000, 0x8000
NOTE_EXIT, NOTE_EXITSTATUS = 0x80000000, 0x04000000
SOL_LOCAL, LOCAL_PEERPID, LOCAL_PEERTOKEN = 0, 0x002, 0x006
FRAME_ROSTER = (
    (1, "D>F", "HELLO"), (2, "F>D", "PREPARE"), (3, "P>D", "CHILD_READY"),
    (4, "D>F", "CHILD_READY"), (5, "F>D", "START"), (6, "D>P", "START"),
    (7, "P>D", "RESULT"), (8, "D>F", "CHILD_RESULT_AND_EXIT_READY"),
)
CLOSURE_KEYS = frozenset(("producerWait", "producerStreams", "producerNativeExit", "serviceNativeExit",
                         "controlEof", "nativeClosed", "registrationAbsent", "rootObjectsRemoved", "adminClosed"))
IDENTITY_KEYS = frozenset(("pid", "parentPid", "uniqueId", "parentUniqueId", "pidVersion", "startSeconds",
                           "startMicroseconds", "uid", "realUid", "gid", "realGid", "status"))
STAT_FORMAT = "%d:%i:%p:%u:%g:%l:%z:%m:%c"
ROOT_TEMPLATE = "/private/var/db/p2pkit-context.XXXXXXXXXX"
OS_TOOLS = ("/usr/bin/sudo", "/usr/bin/mktemp", "/usr/bin/stat", "/usr/bin/tee", "/bin/cat", "/bin/ls",
            "/bin/rm", "/bin/rmdir", "/bin/launchctl", "/usr/bin/git", "/usr/bin/sw_vers")
OS_PARENTS = ("/", "/private", "/private/var", "/private/var/db", "/usr", "/usr/bin", "/bin")
MAX_CIPHERTEXT_BYTES = 576 * 1024 * 1024
SOURCE_SITES = frozenset((
    "REQUEST_EVENT", "REQUEST_SOURCE", "SOURCE_STATUS", "SOURCE_OBJECTS",
    "PIN_TYPE", "PIN_OWNER", "PIN_NLINK", "PIN_MODE", "PIN_SIZE", "PIN_EXECUTABLE",
    "PIN_READ_SIZE", "PIN_FD_STABLE", "PIN_PATH_STABLE",
    "PYTHON_PARENT_TYPE", "PYTHON_PARENT_OWNER", "PYTHON_PARENT_MODE",
    "PREPARED_SOURCE", "PREPARED_RUN", "ORIGINAL_SOURCE_PATHS", "CHECKOUT_SOURCE",
    "OS_OWNER", "OS_MODE", "OS_TYPE", "OS_FIRST_IDENTITY", "OS_NEXT_IDENTITY",
    "FREEZE_SOURCE", "UPLOAD_SOURCE",
))
SOURCE_OS_SITES = frozenset(("OS_OWNER", "OS_MODE", "OS_TYPE", "OS_FIRST_IDENTITY", "OS_NEXT_IDENTITY"))
# Explanatory tokens only: these do not select paths or capture observations.
SOURCE_OS_ITEMS = {
    "/": "ROOT", "/private": "PRIVATE", "/private/var": "PRIVATE_VAR", "/private/var/db": "PRIVATE_VAR_DB",
    "/usr": "USR", "/usr/bin": "USR_BIN", "/bin": "BIN",
    "/usr/bin/sudo": "SUDO", "/usr/bin/mktemp": "MKTEMP", "/usr/bin/stat": "STAT", "/usr/bin/tee": "TEE",
    "/bin/cat": "CAT", "/bin/ls": "LS", "/bin/rm": "RM", "/bin/rmdir": "RMDIR",
    "/bin/launchctl": "LAUNCHCTL", "/usr/bin/git": "GIT", "/usr/bin/sw_vers": "SW_VERS",
}
ADMIN_SITES = frozenset((
    "META_KIND", "META_TYPE", "META_OWNER", "META_GROUP", "META_INODE", "META_WRITE_MODE", "META_LINKS",
    "META_EXACT_MODE", "META_LIST_TYPE", "META_SIZE", "META_PREVIOUS", "META_STABLE", "PLIST_TEE", "PLIST_CAT",
))
ADMIN_ITEMS = frozenset((*SOURCE_OS_ITEMS.values(), "PRIVATE_DIRECTORY", "PRIVATE_FILE"))


class ExperimentError(RuntimeError):
    """Only fixed source-owned fields, not raw private exceptions, reach stdout."""

    def __init__(self, stage, reason, errno_name="NONE", *, source_site=None, source_item=None,
                 admin_site=None, admin_item=None, admin_field=None):
        self.stage = stage if stage in STAGES else "PREPARE"
        self.reason = reason if reason in REASONS else "REFUSED"
        self.errno_name = errno_name if errno_name in ERRNOS else "UNKNOWN"
        self.source_site, self.source_item = source_site, source_item
        self.admin_site, self.admin_item = admin_site, admin_item
        self.admin_field = admin_field
        super().__init__(self.stage + "/" + self.reason + "/" + self.errno_name)


def require(value, stage, reason="REFUSED", errno_name="NONE", *, source_site=None, source_item=None,
            admin_site=None, admin_item=None, admin_field=None):
    if not value:
        raise ExperimentError(stage, reason, errno_name, source_site=source_site, source_item=source_item,
                              admin_site=admin_site, admin_item=admin_item, admin_field=admin_field)


def errno_name(value):
    name = errno.errorcode.get(value, "UNKNOWN") if type(value) is int else "UNKNOWN"
    return name if name in ERRNOS else "UNKNOWN"


def public_error(error):
    if not isinstance(error, ExperimentError):
        error = ExperimentError("PREPARE", "REFUSED", "UNKNOWN")
    return "P2PKIT_CONTEXT_FAILURE|" + "|".join((error.stage, error.reason, error.errno_name))


def source_os_item(name):
    return SOURCE_OS_ITEMS.get(name, "NONE") if type(name) is str else "NONE"


def public_source_site(error):
    """First guard refusal only, not a root cause, completed phase or acceptance."""
    if not isinstance(error, ExperimentError) or error.stage != "SOURCE" or error.reason != "IDENTITY_CHANGED":
        return None
    site, item = getattr(error, "source_site", None), getattr(error, "source_item", None)
    site = site if type(site) is str and site in SOURCE_SITES else "UNKNOWN"
    item = item if site in SOURCE_OS_SITES and type(item) is str and item in SOURCE_OS_ITEMS.values() else "NONE"
    return "P2PKIT_CONTEXT_SOURCE_SITE|" + site + "|" + item


def admin_object_item(path, kind):
    """Explanatory role only; this never admits a path or acquires metadata."""
    if type(path) is not str or type(kind) is not str or kind not in ("directory", "file"):
        return "NONE"
    return SOURCE_OS_ITEMS.get(path, "PRIVATE_DIRECTORY" if kind == "directory" else "PRIVATE_FILE")


def public_admin_site(error):
    """First administrative guard refusal only, not cause or retirement proof."""
    if (not isinstance(error, ExperimentError) or type(error.stage) is not str or type(error.reason) is not str or
            error.stage != "ADMIN_CREATE" or error.reason != "IDENTITY_CHANGED"):
        return None
    site, item = getattr(error, "admin_site", None), getattr(error, "admin_item", None)
    site = site if type(site) is str and site in ADMIN_SITES else "UNKNOWN"
    item = item if site in ADMIN_SITES and type(item) is str and item in ADMIN_ITEMS else "NONE"
    if site == "META_PREVIOUS":
        field = getattr(error, "admin_field", None)
        field = field.upper() if type(field) is str and field in ("dev", "ino", "mode", "uid", "gid", "nlink") else "UNKNOWN"
        return "P2PKIT_CONTEXT_ADMIN_SITE|" + site + "|" + item + "|" + field
    return "P2PKIT_CONTEXT_ADMIN_SITE|" + site + "|" + item


@contextlib.contextmanager
def at_stage(stage):
    """Keep the actual failing boundary/errno, but never print private text."""
    try:
        yield
    except ExperimentError:
        raise
    except OSError as error:
        reason = "PERMISSION_DENIED" if error.errno in (errno.EPERM, errno.EACCES) else "RETURN_FAILED"
        raise ExperimentError(stage, reason, errno_name(error.errno)) from None
    except subprocess.TimeoutExpired:
        raise ExperimentError(stage, "TIMEOUT", "ETIMEDOUT") from None
    except BaseException:
        raise ExperimentError(stage, "REFUSED", "UNKNOWN") from None


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    pending, nodes = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        require(nodes <= JSON_NODES and depth <= JSON_DEPTH, "PREPARE", "BOUND")
        if type(item) is dict:
            require(all(type(key) is str for key in item), "PREPARE", "REFUSED")
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        else:
            require(item is None or type(item) in (str, int, bool, float), "PREPARE", "REFUSED")
            require(type(item) is not float or math.isfinite(item), "PREPARE", "REFUSED")
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
    except (TypeError, ValueError, RecursionError):
        raise ExperimentError("PREPARE", "BOUND") from None


def parsed(raw, limit=FRAME_BYTES):
    require(type(raw) is bytes and type(limit) is int and 0 < len(raw) <= limit, "PREPARE", "BOUND")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "PREPARE", "REFUSED")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: require(False, "PREPARE", "REFUSED"))
    except (ValueError, UnicodeError, RecursionError):
        raise ExperimentError("PREPARE", "REFUSED") from None
    require(len(encoded(value)) <= limit, "PREPARE", "BOUND")
    return value


def validate_request(request, env, event_inputs):
    """Consistency against the original Step, not attestation from copied DATA."""
    require(type(request) is dict and set(request) == REQUEST_KEYS and
            all(type(value) is str and SHA.fullmatch(value) for value in request.values()), "SOURCE")
    require(type(event_inputs) is dict and event_inputs == request, "SOURCE", "IDENTITY_CHANGED",
            source_site="REQUEST_EVENT")
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPOSITORY and
            env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            env.get("GITHUB_JOB") == "context_experiment" and env.get("GITHUB_ACTOR") == OWNER and
            env.get("GITHUB_ACTOR_ID") == OWNER_ID and env.get("GITHUB_TRIGGERING_ACTOR") == OWNER,
            "SOURCE", "REFUSED")
    ref = env.get("GITHUB_REF", "")
    require(type(ref) is str and REF.fullmatch(ref), "SOURCE")
    require(env.get("GITHUB_SHA") == env.get("GITHUB_WORKFLOW_SHA") == request["source_sha"] and
            env.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + WORKFLOW + "@" + ref, "SOURCE", "IDENTITY_CHANGED",
            source_site="REQUEST_SOURCE")
    require(all(type(env.get(key)) is str and NUMBER.fullmatch(env[key])
                for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")), "SOURCE")
    require(not any(key in env for key in OWNER_ENV), "IDENTITY", "REFUSED")
    return {"repository": REPOSITORY, "workflow": WORKFLOW, "job": "context_experiment", "ref": ref,
            "source": request["source_sha"], "sourceTree": request["source_tree"],
            "runId": env["GITHUB_RUN_ID"], "runAttempt": env["GITHUB_RUN_ATTEMPT"],
            "actor": OWNER, "actorId": OWNER_ID, "triggeringActor": OWNER}


def validate_account(actual, expected=None):
    require(type(actual) is dict and set(actual) == {"uid", "euid", "gid", "egid", "groups"}, "IDENTITY")
    require(all(type(actual[key]) is int and 0 <= actual[key] < 2 ** 32 for key in ("uid", "euid", "gid", "egid")) and
            actual["uid"] == actual["euid"] != 0 and actual["gid"] == actual["egid"], "IDENTITY", "REFUSED")
    groups = actual["groups"]
    require(type(groups) is list and len(groups) <= 256 and
            all(type(value) is int and 0 <= value < 2 ** 32 for value in groups) and
            groups == sorted(set(groups)), "IDENTITY")
    require(expected is None or actual == expected, "IDENTITY", "IDENTITY_CHANGED")
    return actual


def account():
    return validate_account({"uid": os.getuid(), "euid": os.geteuid(), "gid": os.getgid(), "egid": os.getegid(),
                             "groups": sorted(set(os.getgroups()))})


def validate_allocation(allocation, request, github, now_ns, wall_ns):
    keys = {"schema", "source", "sourceTree", "runId", "runAttempt", "startedMonotonicNs", "startedEpochNs"}
    require(type(allocation) is dict and set(allocation) == keys and type(allocation["schema"]) is int and
            allocation["schema"] == 1 and allocation["source"] == request["source_sha"] and
            allocation["sourceTree"] == request["source_tree"] and allocation["runId"] == github["runId"] and
            allocation["runAttempt"] == github["runAttempt"], "PREPARE", "IDENTITY_CHANGED")
    require(all(type(value) is int and value > 0 for value in
                (now_ns, wall_ns, allocation["startedMonotonicNs"], allocation["startedEpochNs"])), "PREPARE")
    elapsed = now_ns - allocation["startedMonotonicNs"]
    require(0 <= elapsed < JOB_SECONDS * NS and
            abs((wall_ns - allocation["startedEpochNs"]) - elapsed) <= 10 * NS, "PREPARE", "TIMEOUT")
    return allocation["startedMonotonicNs"] + JOB_SECONDS * NS


def decode_exit_event(event, expected_pid):
    """Decode an actual returned event. Requested flags or Popen codes are not it."""
    require(type(event) is dict and set(event) == {"ident", "filter", "flags", "fflags", "data"} and
            all(type(value) is int for value in event.values()) and type(expected_pid) is int and expected_pid > 0,
            "SERVICE_WAIT", "STATUS_MISSING")
    require(event["ident"] == expected_pid and event["filter"] == EVFILT_PROC and not event["flags"] & EV_ERROR and
            event["fflags"] & (NOTE_EXIT | NOTE_EXITSTATUS) == NOTE_EXIT | NOTE_EXITSTATUS,
            "SERVICE_WAIT", "STATUS_MISSING")
    raw = event["data"]
    # No NOTE_EXIT_DETAIL is requested; high/reparenting/unknown bits are refusal.
    require(0 <= raw <= 0xffff, "SERVICE_WAIT", "STATUS_UNEXPECTED")
    if os.WIFEXITED(raw):
        value, kind = os.WEXITSTATUS(raw), "EXITED"
        code = value
    elif os.WIFSIGNALED(raw):
        value, kind = os.WTERMSIG(raw), "SIGNALED"
        require(0 < value < 128, "SERVICE_WAIT", "STATUS_UNEXPECTED")
        code = -value
    else:
        raise ExperimentError("SERVICE_WAIT", "STATUS_UNEXPECTED")
    return {"rawStatus": raw, "kind": kind, "value": value, "popenCode": code}


def validate_probe_result(value):
    require(type(value) is dict and set(value) == {"stage", "result", "errno", "sent", "socketCreated", "closed", "closeError"},
            "NATIVE_SEND")
    require(all(type(value[key]) is str for key in ("stage", "result", "errno", "closeError")), "NATIVE_SEND")
    require(value["stage"] in {"SOCKET", "REUSE", "BIND", "INTERFACE", "JOIN", "TTL", "SEND", "NO_NETWORK"} and
            value["result"] in {"KERNEL_ACCEPTED", "FAIL", "EXPECTED_FAILURE", "NO_NETWORK"} and
            value["errno"] in ERRNOS and value["closeError"] in ERRNOS and type(value["sent"]) is int and
            0 <= value["sent"] <= 42 and type(value["socketCreated"]) is bool and type(value["closed"]) is bool,
            "NATIVE_SEND", "BOUND")
    require((value["socketCreated"] and value["closed"] or not value["socketCreated"] and not value["closed"]) and
            value["closeError"] == "NONE", "CLOSE", "RESOURCE_UNKNOWN")
    return value


def validate_case_result(case, producer_code, service_status, probe_result):
    require(case in CASES and type(producer_code) is int and type(service_status) is dict and
            set(service_status) == {"rawStatus", "kind", "value", "popenCode"}, "SERVICE_WAIT")
    if case == "N3":
        require(probe_result is None and producer_code == -signal.SIGTERM and
                service_status["kind"] == "EXITED" and service_status["value"] == 24 and
                service_status["popenCode"] == 24, "SERVICE_WAIT", "STATUS_UNEXPECTED")
        return True
    value = validate_probe_result(probe_result)
    if case == "N4":
        require(producer_code == 0 and service_status["kind"] == "SIGNALED" and
                service_status["value"] == signal.SIGTERM and service_status["popenCode"] == -signal.SIGTERM and
                value["result"] == "NO_NETWORK" and not value["socketCreated"] and value["sent"] == 0,
                "SERVICE_WAIT", "STATUS_UNEXPECTED")
        return True
    require(service_status["kind"] == "EXITED" and service_status["value"] == producer_code == service_status["popenCode"],
            "SERVICE_WAIT", "STATUS_UNEXPECTED")
    if case == "N2":
        require(producer_code == 23 and value["result"] == "EXPECTED_FAILURE" and
                not value["socketCreated"] and value["sent"] == 0, "CHILD_WAIT", "STATUS_UNEXPECTED")
        return True
    if value["result"] == "KERNEL_ACCEPTED":
        require(producer_code == 0 and value["stage"] == "SEND" and value["errno"] == "NONE" and
                value["sent"] == 42 and value["socketCreated"] and value["closed"], "NATIVE_SEND", "STATUS_UNEXPECTED")
        return True
    require(value["result"] == "FAIL" and producer_code == 23, "NATIVE_SEND", "STATUS_UNEXPECTED")
    return False


def frame_value(serial, binding, payload):
    require(type(serial) is int and 1 <= serial <= 8 and type(binding) is str and HASH.fullmatch(binding) and
            type(payload) is dict, "START", "BOUND")
    value = {"schema": 1, "serial": serial, "kind": FRAME_ROSTER[serial - 1][2], "binding": binding, "payload": payload}
    require(len(encoded(value)) <= FRAME_BYTES, "START", "BOUND")
    return value


def validate_frame(value, serial, binding):
    require(type(value) is dict and set(value) == {"schema", "serial", "kind", "binding", "payload"} and
            type(value["schema"]) is int and value["schema"] == 1 and type(value["serial"]) is int and
            value["serial"] == serial and value["binding"] == binding, "START", "IDENTITY_CHANGED")
    require(value == frame_value(serial, binding, value["payload"]), "START", "REFUSED")
    return value["payload"]


def frame_record(value):
    serial = value["serial"]
    return {"serial": serial, "direction": FRAME_ROSTER[serial - 1][1], "kind": value["kind"], "sha256": digest(encoded(value))}


def validate_frame_trace(case, trace):
    require(case in CASES and type(trace) is list, "START")
    expected = [row for row in FRAME_ROSTER if not (case == "N3" and row[0] == 7)]
    require(len(trace) == len(expected), "START", "BOUND")
    for actual, (serial, direction, kind) in zip(trace, expected):
        require(type(actual) is dict and set(actual) == {"serial", "direction", "kind", "sha256"} and
                type(actual["serial"]) is int and actual["serial"] == serial and actual["direction"] == direction and
                actual["kind"] == kind and type(actual["sha256"]) is str and HASH.fullmatch(actual["sha256"]),
                "START", "REFUSED")
    return trace


def validate_closure(value):
    """Validate closed result DATA, never manufacture a live native return."""
    require(type(value) is dict and set(value) == CLOSURE_KEYS and all(item is True for item in value.values()),
            "CLOSE", "RESOURCE_UNKNOWN")
    return value


def validate_upload_binding(seal, env):
    require(type(seal) is dict and seal.get("scope") == SCOPE and seal.get("outcome") in {"SUCCESS", "CLOSED_FAILURE"}, "UPLOAD")
    wanted = "success" if seal["outcome"] == "SUCCESS" else "failure"
    success = env.get("P2PKIT_CONTEXT_SUCCESS_SHA256", "")
    failed = env.get("P2PKIT_CONTEXT_CLOSED_FAILURE_SHA256", "")
    actual = digest(encoded(seal))
    require(env.get("P2PKIT_CONTEXT_STEP_OUTCOME") == wanted and
            (success == actual and failed == "" if wanted == "success" else failed == actual and success == ""),
            "UPLOAD", "IDENTITY_CHANGED")
    return actual


def physical(value):
    path = Path(value)
    original = os.fspath(value)
    require(type(original) is str and str(path) == original and not original.startswith("//") and
            all(32 <= ord(char) < 127 for char in original) and path.is_absolute() and ".." not in path.parts,
            "PREPARE", "REFUSED")
    for item in (path, *path.parents):
        require(not item.is_symlink(), "PREPARE", "IDENTITY_CHANGED")
    return path


def private_directory(path, *, empty=False):
    path = physical(path)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
            "PREPARE", "IDENTITY_CHANGED")
    require(not empty or not any(path.iterdir()), "PREPARE", "REFUSED")
    return [info.st_dev, info.st_ino]


def read_file(path, limit=STREAM_BYTES):
    path = physical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid() and
                not before.st_mode & 0o022 and 0 <= before.st_size <= limit, "PREPARE", "BOUND")
        raw = stream.read(limit + 1)
        stamp = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_nlink,
                               value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        require(len(raw) == before.st_size and stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()),
                "PREPARE", "IDENTITY_CHANGED")
    return raw


def write_new(path, raw):
    require(type(raw) is bytes and len(raw) <= EVIDENCE_BYTES, "FREEZE", "BOUND")
    path = physical(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        require(stream.write(raw) == len(raw), "FREEZE", "RETURN_FAILED")
        stream.flush()
        os.fsync(stream.fileno())
    require(read_file(path, max(STREAM_BYTES, len(raw))) == raw, "FREEZE", "IDENTITY_CHANGED")


def left(end_ns, stage):
    require(type(end_ns) is int, stage, "TIMEOUT")
    remaining = (end_ns - time.monotonic_ns()) / NS
    require(remaining > 0, stage, "TIMEOUT")
    return remaining


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def child_environment(parent):
    # No copied credentials/GitHub command files, ambient Python/DYLD injection,
    # owner erasure, or synthetic hosted identity. Project code is always nonroot.
    require(not any(key in os.environ for key in OWNER_ENV), "IDENTITY")
    return {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(parent / "home"),
            "TMPDIR": str(parent / "tmp"), "LANG": "C", "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
            "__CF_USER_TEXT_ENCODING": f"0x{os.getuid():X}:0:0",
            "DEVELOPER_DIR": "/Applications/Xcode_26.5.app/Contents/Developer"}


# Held on an unproved OS-command timeout; never pretend communicate(timeout)
# terminated a privileged command. No export follows a nonempty collection.
_UNCLOSED_COMMANDS = []


def capture_fixed(argv, end_ns, env, *, input_raw=b"", stage="SOURCE"):
    """Small pipe mechanism used only by fixed source/OS argv below, not a CLI."""
    require(type(input_raw) is bytes and len(input_raw) <= FRAME_BYTES, stage, "BOUND")
    end_ns = min(end_ns, time.monotonic_ns() + ADMIN_SECONDS * NS)
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


def source_snapshot(end_ns, env):
    rows = []
    for arguments in (("rev-parse", "HEAD"), ("rev-parse", "HEAD^{tree}"),
                      ("status", "--porcelain=v1", "--untracked-files=all", "--ignored")):
        result = capture_fixed(["/usr/bin/git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                                "--no-pager", "-C", str(ROOT), *arguments], end_ns,
                               {**env, "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})
        require(result["code"] == 0 and not result["stderr"], "SOURCE", "RETURN_FAILED")
        rows.append(result["stdout"])
    require(not rows[2], "SOURCE", "IDENTITY_CHANGED", source_site="SOURCE_STATUS")
    commit, tree = (row.decode("ascii").strip() for row in rows[:2])
    require(SHA.fullmatch(commit) and SHA.fullmatch(tree), "SOURCE", "IDENTITY_CHANGED", source_site="SOURCE_OBJECTS")
    files = {name: digest(read_file(ROOT / name, EVIDENCE_BYTES)) for name in
             (SCRIPT, WORKFLOW, "scripts/audit_processes.py", "scripts/hosted_evidence.py",
              "scripts/hosted_evidence_primitives.py", "AGENTS.md", "CLAUDE.md", POLICY_PATH)}
    return {"commit": commit, "tree": tree, "files": files}


def validate_policy(raw, now):
    require(type(now) in (int, float) and math.isfinite(now) and digest(raw) == POLICY_SHA256, "POLICY", "REFUSED")
    value = parsed(raw, 96 * 1024)
    require(type(value) is dict and set(value) == {"schema", "repository", "purpose", "retrievalOwner", "retentionDays",
            "notBefore", "expiresAt", "recipient"} and type(value["schema"]) is int and value["schema"] == 1 and
            value["repository"] == REPOSITORY and value["purpose"] == "P2PKIT_TEST_TRANSCRIPTS" and
            value["retrievalOwner"] == OWNER and type(value["retentionDays"]) is int and value["retentionDays"] == 14,
            "POLICY", "REFUSED")
    require(type(value["notBefore"]) is int and type(value["expiresAt"]) is int and
            value["expiresAt"] == POLICY_EXPIRES and value["expiresAt"] - value["notBefore"] == 14 * 86400 and
            value["notBefore"] <= now and now + JOB_SECONDS < value["expiresAt"] and now < POLICY_EXPIRES - 12600,
            "POLICY", "TIMEOUT")
    key = value["recipient"]
    require(type(key) is dict and set(key) == {"publicKey", "fingerprint", "sha256"} and
            type(key["publicKey"]) is str and key["fingerprint"] == FINGERPRINT and key["sha256"] == KEY_SHA256 and
            digest(key["publicKey"].encode("ascii")) == KEY_SHA256, "POLICY", "IDENTITY_CHANGED")
    return value


def same_identity(actual, expected):
    for value in (actual, expected):
        require(type(value) is dict and set(value) == IDENTITY_KEYS and
                all(type(item) is int and item >= 0 for item in value.values()) and value["pid"] > 0 and
                value["uniqueId"] > 0 and value["status"] in (1, 2, 3, 4), "IDENTITY", "IDENTITY_CHANGED")
    require(all(actual[key] == expected[key] for key in IDENTITY_KEYS - {"status"}), "IDENTITY", "IDENTITY_CHANGED")
    return actual


def identity_account(identity, expected):
    validate_account(expected)
    require(identity["uid"] == identity["realUid"] == expected["uid"] and
            identity["gid"] == identity["realGid"] == expected["gid"], "IDENTITY", "IDENTITY_CHANGED")


class Darwin:
    """Direct original lifetimes only. This is deliberately not DarwinScope."""

    def __init__(self, *, observe_exit=True):
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
                "uid": value.bsd.uid, "realUid": value.bsd.ruid, "gid": value.bsd.gid, "realGid": value.bsd.rgid,
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
        self.token(identity)
        require(identity["pid"] not in self.watched, "ATTACH", "IDENTITY_CHANGED")
        change = select.kevent(identity["pid"], filter=EVFILT_PROC, flags=EV_ADD | EV_ENABLE | EV_RECEIPT,
                               fflags=NOTE_EXIT | NOTE_EXITSTATUS)
        # Only one receipt can be returned here; an earlier watched process's
        # terminal event must not be silently consumed as registration DATA.
        started = time.monotonic_ns()
        receipts = self.kqueue.control([change], 1, 0)
        returned = time.monotonic_ns()
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
        observation["recheckedMonotonicNs"] = time.monotonic_ns()
        self.registrations[identity["pid"]] = observation

    def signal(self, identity, signum, end_ns):
        require(signum in (signal.SIGTERM, signal.SIGKILL), "CLOSE", "REFUSED")
        left(end_ns, "CLOSE")
        token = self.token(identity)
        left(end_ns, "CLOSE")
        started = time.monotonic_ns()
        code = self.proc.proc_signal_with_audittoken(ctypes.byref(token), signum)
        self.signals.append({"identity": dict(identity), "signal": int(signum), "returnedCode": code,
                             "startedMonotonicNs": started, "returnedMonotonicNs": time.monotonic_ns()})
        require(code == 0, "CLOSE", "RETURN_FAILED", errno_name(code))
        left(end_ns, "CLOSE")

    def wait(self, identities, end_ns):
        wanted = {value["pid"] for value in identities}
        require(wanted <= self.watched.keys(), "SERVICE_WAIT", "REFUSED")
        while not wanted <= self.events.keys():
            events = self.kqueue.control(None, 16, min(0.05, left(end_ns, "SERVICE_WAIT")))
            for event in events:
                require(event.ident in self.watched and event.ident not in self.events, "SERVICE_WAIT", "IDENTITY_CHANGED")
                row = {key: int(getattr(event, key)) for key in ("ident", "filter", "flags", "fflags", "data")}
                self.events[event.ident] = {"event": row, "status": decode_exit_event(row, event.ident)}
        return {value["pid"]: self.events[value["pid"]] for value in identities}

    def poll(self):
        require(self.kqueue is not None and not self.closed, "SERVICE_WAIT", "RESOURCE_UNKNOWN")
        for event in self.kqueue.control(None, 16, 0):
            require(event.ident in self.watched and event.ident not in self.events, "SERVICE_WAIT", "IDENTITY_CHANGED")
            row = {key: int(getattr(event, key)) for key in ("ident", "filter", "flags", "fflags", "data")}
            self.events[event.ident] = {"event": row, "status": decode_exit_event(row, event.ident)}

    def close(self):
        require(not self.closed, "CLOSE", "RESOURCE_UNKNOWN")
        if self.kqueue is not None:
            self.kqueue.close()
            require(self.kqueue.closed, "CLOSE", "RESOURCE_UNKNOWN")
        self.closed = True


def interface_ipv4(expected=None):
    """Small getifaddrs observation; no resolver, route probe or interface hop."""
    class Address(ctypes.Structure):
        _fields_ = [("length", ctypes.c_uint8), ("family", ctypes.c_uint8), ("data", ctypes.c_char * 14)]

    class Interface(ctypes.Structure):
        pass

    Interface._fields_ = [("next", ctypes.POINTER(Interface)), ("name", ctypes.c_char_p), ("flags", ctypes.c_uint32),
                         ("address", ctypes.POINTER(Address)), ("netmask", ctypes.POINTER(Address)),
                         ("destination", ctypes.POINTER(Address)), ("data", ctypes.c_void_p)]
    require(platform.system() == "Darwin" and ctypes.sizeof(Interface) == 56, "NATIVE_SEND", "UNSUPPORTED")
    system = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    system.getifaddrs.argtypes, system.getifaddrs.restype = [ctypes.POINTER(ctypes.POINTER(Interface))], ctypes.c_int
    system.freeifaddrs.argtypes, system.freeifaddrs.restype = [ctypes.POINTER(Interface)], None
    first, rows = ctypes.POINTER(Interface)(), []
    require(system.getifaddrs(ctypes.byref(first)) == 0, "NATIVE_SEND", "RETURN_FAILED", errno_name(ctypes.get_errno()))
    try:
        current, count = first, 0
        while current:
            count += 1
            require(count <= 512, "NATIVE_SEND", "BOUND")
            item = current.contents
            if item.address and item.address.contents.family == socket.AF_INET and item.flags & 1 and item.flags & 0x8000:
                require(item.address.contents.length >= 16 and item.name, "NATIVE_SEND", "UNSUPPORTED")
                name = item.name.decode("ascii")
                require(re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", name), "NATIVE_SEND", "BOUND")
                raw = ctypes.string_at(item.address, 16)[4:8]
                address = ipaddress.IPv4Address(raw)
                if not item.flags & 8 and not (address.is_unspecified or address.is_loopback or address.is_multicast):
                    index = socket.if_nametoindex(name)
                    require(index > 0 and socket.if_indextoname(index) == name, "NATIVE_SEND", "IDENTITY_CHANGED")
                    rows.append({"index": index, "name": name, "address": str(address)})
            current = item.next
    finally:
        system.freeifaddrs(first)  # Native void return, not an invented success code.
    rows.sort(key=lambda row: (row["index"], row["name"], int(ipaddress.IPv4Address(row["address"]))))
    require(rows, "NATIVE_SEND", "REFUSED")
    if expected is not None:
        require(type(expected) is dict and set(expected) == {"index", "name", "address"} and
                type(expected["index"]) is int and expected["index"] > 0 and type(expected["name"]) is str and
                type(expected["address"]) is str and expected in rows,
                "NATIVE_SEND", "IDENTITY_CHANGED")
        return expected
    return rows[0]


def native_probe(case, selected, end_ns, *, observation=None):
    require(case in CASES and case != "N3", "NATIVE_SEND")
    if observation is None:
        observation = {}
    require(type(observation) is dict and not observation, "NATIVE_SEND", "REFUSED")
    observation.update(startedMonotonicNs=time.monotonic_ns(), socketFd=None, sendStartedMonotonicNs=None,
                       sendFinishedMonotonicNs=None, sendReturn=None, closeStartedMonotonicNs=None,
                       closeReturnedMonotonicNs=None, closedFd=None, finishedMonotonicNs=None)
    value = {"stage": "NO_NETWORK", "result": "EXPECTED_FAILURE" if case == "N2" else "NO_NETWORK", "errno": "NONE",
             "sent": 0, "socketCreated": False, "closed": False, "closeError": "NONE"}
    if case != "N1":
        observation["finishedMonotonicNs"] = time.monotonic_ns()
        return value
    interface_ipv4(selected)
    stream = None
    try:
        left(end_ns, "NATIVE_SEND")
        value.update(stage="SOCKET", result="FAIL")
        stream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        value["socketCreated"] = True
        observation["socketFd"] = stream.fileno()
        stream.setblocking(False)
        value["stage"] = "REUSE"
        for option in (socket.SO_REUSEADDR, socket.SO_REUSEPORT):
            stream.setsockopt(socket.SOL_SOCKET, option, 1)
            require(stream.getsockopt(socket.SOL_SOCKET, option) != 0, "NATIVE_SEND", "RETURN_FAILED")
        value["stage"] = "BIND"
        stream.bind(("0.0.0.0", 5353))
        value["stage"] = "INTERFACE"
        address = socket.inet_aton(selected["address"])
        stream.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, address)
        require(stream.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, 4) == address, "NATIVE_SEND", "IDENTITY_CHANGED")
        value["stage"] = "JOIN"
        stream.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton("224.0.0.251") + address)
        value["stage"] = "TTL"
        stream.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
        value["stage"] = "SEND"
        left(end_ns, "NATIVE_SEND")
        observation["sendStartedMonotonicNs"] = time.monotonic_ns()
        try:
            value["sent"] = stream.sendto(QUERY, ("224.0.0.251", 5353))
            observation["sendReturn"] = value["sent"]
        finally:
            observation["sendFinishedMonotonicNs"] = time.monotonic_ns()
        left(end_ns, "NATIVE_SEND")
        if value["sent"] == 42:
            value["result"] = "KERNEL_ACCEPTED"
    except OSError as error:
        value["errno"] = errno_name(error.errno)
    finally:
        if stream is not None:
            try:
                observation["closeStartedMonotonicNs"] = time.monotonic_ns()
                stream.close()
                observation["closeReturnedMonotonicNs"] = time.monotonic_ns()
                observation["closedFd"] = stream.fileno()
                value["closed"] = observation["closedFd"] == -1
            except OSError as error:
                value["closeError"] = errno_name(error.errno)
        observation["finishedMonotonicNs"] = time.monotonic_ns()
    return validate_probe_result(value)


def validate_probe_observation(value, probe, case, end_ns):
    keys = {"startedMonotonicNs", "socketFd", "sendStartedMonotonicNs", "sendFinishedMonotonicNs", "sendReturn",
            "closeStartedMonotonicNs", "closeReturnedMonotonicNs", "closedFd", "finishedMonotonicNs"}
    require(type(value) is dict and set(value) == keys and type(value["startedMonotonicNs"]) is int and
            type(value["finishedMonotonicNs"]) is int and
            0 < value["startedMonotonicNs"] <= value["finishedMonotonicNs"] < end_ns, "NATIVE_SEND", "TIMEOUT")
    if probe["socketCreated"]:
        require(case == "N1" and type(value["socketFd"]) is int and value["socketFd"] >= 0 and value["closedFd"] == -1 and
                type(value["closeStartedMonotonicNs"]) is int and type(value["closeReturnedMonotonicNs"]) is int and
                value["startedMonotonicNs"] <= value["closeStartedMonotonicNs"] <= value["closeReturnedMonotonicNs"] <=
                value["finishedMonotonicNs"], "CLOSE", "RESOURCE_UNKNOWN")
    else:
        require(all(value[key] is None for key in ("socketFd", "closedFd", "closeStartedMonotonicNs", "closeReturnedMonotonicNs")),
                "CLOSE", "RESOURCE_UNKNOWN")
    if probe["stage"] == "SEND":
        require(type(value["sendStartedMonotonicNs"]) is int and type(value["sendFinishedMonotonicNs"]) is int and
                value["startedMonotonicNs"] <= value["sendStartedMonotonicNs"] <= value["sendFinishedMonotonicNs"] <=
                value["closeStartedMonotonicNs"] and
                (value["sendReturn"] is None if probe["errno"] != "NONE" else
                 type(value["sendReturn"]) is int and value["sendReturn"] == probe["sent"]),
                "NATIVE_SEND", "STATUS_UNEXPECTED")
    else:
        require(all(value[key] is None for key in ("sendStartedMonotonicNs", "sendFinishedMonotonicNs", "sendReturn")),
                "NATIVE_SEND", "REFUSED")
    return value


def receive_bytes(channel, size, stage):
    """Accept plain DATA only; unexpected descriptor rights are closed/refused."""
    with at_stage(stage):
        raw, ancillary, flags, _address = channel.recvmsg(size, socket.CMSG_SPACE(16))
        if ancillary:
            for level, kind, data in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    for index in range(0, len(data) - len(data) % 4, 4):
                        os.close(struct.unpack("=i", data[index:index + 4])[0])
        require(not ancillary and flags == 0, stage, "REFUSED")
        return raw


def send_frame(channel, serial, binding, payload, trace, end_ns):
    require(type(trace) is list and len(trace) < 8 and all(row["serial"] < serial for row in trace), "START", "BOUND")
    value = frame_value(serial, binding, payload)
    raw = encoded(value)
    pending = memoryview(struct.pack("!I", len(raw)) + raw)
    while pending:
        left(end_ns, "START")
        _, ready, _ = select.select([], [channel], [], min(0.05, left(end_ns, "START")))
        if ready:
            with at_stage("START"):
                count = channel.send(pending)
            require(count > 0, "START", "RETURN_FAILED")
            pending = pending[count:]
    left(end_ns, "START")
    trace.append(frame_record(value))
    return value


def read_frame(channel, serial, binding, trace, end_ns, pump=None):
    require(type(trace) is list and len(trace) < 8 and all(row["serial"] < serial for row in trace), "START", "BOUND")
    def exact(size):
        data = bytearray()
        while len(data) < size:
            if pump is not None:
                pump()
            ready, _, _ = select.select([channel], [], [], min(0.05, left(end_ns, "START")))
            if ready:
                part = receive_bytes(channel, size - len(data), "START")
                require(part, "START", "STATUS_MISSING")
                data.extend(part)
        return bytes(data)

    size = struct.unpack("!I", exact(4))[0]
    require(0 < size <= FRAME_BYTES, "START", "BOUND")
    raw = exact(size)
    value = parsed(raw)
    require(raw == encoded(value), "START", "REFUSED")
    validate_frame(value, serial, binding)
    left(end_ns, "START")
    trace.append(frame_record(value))
    return value


def wait_eof(channel, end_ns, pump=None):
    while True:
        if pump is not None:
            pump()
        ready, _, _ = select.select([channel], [], [], min(0.05, left(end_ns, "CLOSE")))
        if ready:
            require(receive_bytes(channel, 1, "CLOSE") == b"", "CLOSE", "REFUSED")
            left(end_ns, "CLOSE")
            return


class ProbePipes:
    """The one direct child's two original pipes; no background drain thread."""

    def __init__(self, process):
        self.process, self.active = process, [process.stdout, process.stderr]
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

    def finish(self, end_ns, directory):
        while self.active or self.process.poll() is None:
            self.pump()
            select.select(self.active, [], [], min(0.02, left(end_ns, "CHILD_WAIT")))
        code = self.process.wait(timeout=left(end_ns, "CHILD_WAIT"))
        require(all(stream.closed for stream in (self.process.stdout, self.process.stderr)), "CLOSE", "RESOURCE_UNKNOWN")
        rows = []
        for name, raw in self.data.items():
            raw = bytes(raw)
            write_new(directory / ("producer." + name), raw)
            rows.append({"name": "producer." + name, "size": len(raw), "sha256": digest(raw), "eof": True, "closed": True})
        self.closed = True
        return code, rows


def producer(fd):
    """Only the original D-created inherited FD and fixed START can select work."""
    require(type(fd) is int and 2 < fd < 4096 and stat.S_ISSOCK(os.fstat(fd).st_mode), "IDENTITY")
    identity_account = account()
    require(signal.getsignal(signal.SIGTERM) == signal.SIG_DFL and
            signal.SIGTERM not in signal.pthread_sigmask(signal.SIG_BLOCK, []), "IDENTITY")
    native, channel = Darwin(observe_exit=False), socket.socket(fileno=fd)
    channel.setblocking(False)
    trace = []
    # These are fixed D-supplied local plumbing values, not hosted identity or a
    # user command/case input. Original D/P source and parentage are checked too.
    binding = os.environ.get("P2PKIT_CONTEXT_BINDING", "")
    end_text = os.environ.get("P2PKIT_CONTEXT_CASE_END_NS", "")
    require(HASH.fullmatch(binding) and re.fullmatch(r"[1-9][0-9]{0,19}", end_text), "START")
    end_ns = int(end_text)
    require(0 < left(end_ns, "START") <= CASE_SECONDS, "START", "TIMEOUT")
    identity, parent = native.identity(os.getpid()), native.identity(os.getppid())
    try:
        source_hash = digest(read_file(ROOT / SCRIPT, EVIDENCE_BYTES))
        send_frame(channel, 3, binding, {"producer": identity, "parent": parent, "account": identity_account,
                   "sigtermDefault": True, "sigtermBlocked": False, "sourceSha256": source_hash,
                   "boot": native.boot(), "interpreter": str(Path(sys.executable).resolve(strict=True))}, trace, end_ns)
        start = read_frame(channel, 6, binding, trace, end_ns)["payload"]
        require(set(start) == {"case", "account", "service", "sourceSha256", "interface", "deadlineNs"} and
                start["case"] in CASES and type(start["deadlineNs"]) is int and start["deadlineNs"] == end_ns,
                "START", "REFUSED")
        validate_account(identity_account, start["account"])
        same_identity(start["service"], parent)
        require(start["sourceSha256"] == source_hash, "IDENTITY", "IDENTITY_CHANGED")
        native.same(parent)
        if start["case"] == "N3":
            # D forwarded START before observing F's ordered EOF, but no ACK or
            # claimed consumption of START is created. Actual SIGTERM is required.
            wait_eof(channel, end_ns)
            raise ExperimentError("CLOSE", "REFUSED")
        observation = {}
        value = native_probe(start["case"], start["interface"], end_ns, observation=observation)
        validate_probe_observation(observation, value, start["case"], end_ns)
        native.close()
        send_frame(channel, 7, binding, {"case": start["case"], "probe": value, "observation": observation}, trace, end_ns)
        channel.close()
        return 23 if start["case"] == "N2" or value["result"] == "FAIL" else 0
    finally:
        if not native.closed:
            native.close()
        channel.close()


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
        raise ExperimentError("ADMIN_CREATE", "UNSUPPORTED") from None
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


def parse_service_print(raw, label, plist_path, arguments, expected_pid, *, running=True):
    require(type(raw) is bytes and 0 < len(raw) <= STREAM_BYTES and type(arguments) is list and
            all(type(value) is str and value and "\n" not in value for value in arguments), "BOOTSTRAP", "BOUND")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeError:
        raise ExperimentError("BOOTSTRAP", "UNSUPPORTED") from None
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


def service_arguments(interpreter, directory):
    return [safe_component_path(interpreter), "-I", "-B", "-S", safe_component_path(ROOT / SCRIPT),
            "_service", safe_component_path(directory)]


def service_plist(label, interpreter, directory, username, groupname):
    require(re.fullmatch(r"p2pkit\.context\.[a-z0-9.]{1,110}", label) and
            all(type(value) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", value)
                for value in (username, groupname)), "ADMIN_CREATE", "REFUSED")
    arguments = service_arguments(interpreter, directory)
    value = {"Label": label, "ProgramArguments": arguments, "UserName": username, "GroupName": groupname,
             "InitGroups": True, "RunAtLoad": True, "KeepAlive": False, "AbandonProcessGroup": False,
             "WorkingDirectory": str(ROOT), "EnvironmentVariables": child_environment(directory),
             "StandardInPath": "/dev/null", "StandardOutPath": "/dev/null", "StandardErrorPath": "/dev/null"}
    raw = plistlib.dumps(value, fmt=plistlib.FMT_XML, sort_keys=True)
    require(0 < len(raw) <= FRAME_BYTES, "ADMIN_CREATE", "BOUND")
    return raw


class Admin:
    """One original root-private plist/registration; no public command selector."""

    def __init__(self, context, directory, label, end_ns):
        self.context, self.directory, self.label, self.end_ns = context, directory, label, end_ns
        self.arguments = service_arguments(context.interpreter["path"], directory)
        self.plist = service_plist(label, context.interpreter["path"], directory, context.username, context.groupname)
        self.root, self.path, self.root_meta, self.file_meta, self.service = None, None, None, None, None
        self.bootstrapped, self.retired, self.removed, self.closed = False, False, False, False
        self.calls, self.written = 0, 0
        self.record = os.fdopen(os.open(directory / "admin.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                       0o600), "wb")

    def _allowed(self, argv, input_raw):
        metadata_paths = {*OS_PARENTS, *OS_TOOLS}
        metadata_paths.update(value for value in (self.root, self.path) if value is not None)
        exact = [["/usr/bin/mktemp", "-d", ROOT_TEMPLATE]] if self.root is None else []
        if self.root is not None and self.path is None:
            exact.append(["/usr/bin/mktemp", self.root + "/job.XXXXXXXXXX"])
        if self.path is not None:
            exact.extend((["/bin/cat", self.path], ["/usr/bin/tee", self.path],
                          ["/bin/launchctl", "bootstrap", "system", self.path], ["/bin/rm", self.path]))
        if self.root is not None:
            exact.append(["/bin/rmdir", self.root])
        exact.append(["/bin/launchctl", "print", "system/" + self.label])
        if self.service is not None:
            exact.append(["/bin/launchctl", "bootout", "system/" + self.label])
        metadata = (len(argv) == 4 and argv[:3] == ["/usr/bin/stat", "-f", STAT_FORMAT] and argv[3] in metadata_paths or
                    len(argv) == 3 and argv[:2] == ["/bin/ls", "-lde"] and argv[2] in metadata_paths)
        require(argv in exact or metadata, "ADMIN_CREATE", "REFUSED")
        require((input_raw == self.plist and self.file_meta is not None) if argv[:1] == ["/usr/bin/tee"]
                else input_raw == b"", "ADMIN_CREATE", "REFUSED")

    def _run(self, argv, stage, *, input_raw=b"", success=True):
        self._allowed(argv, input_raw)
        require(not self.closed and self.calls < 96 and not _UNCLOSED_COMMANDS, stage, "RESOURCE_UNKNOWN")
        self.calls += 1
        started = time.monotonic_ns()
        with at_stage(stage):
            result = capture_fixed(["/usr/bin/sudo", "-n", "--", *argv], self.end_ns,
                                   self.context.os_env, input_raw=input_raw, stage=stage)
        returned = time.monotonic_ns()
        row = {"schema": 1, "ordinal": self.calls, "argv": result["argv"], "code": result["code"],
               "stdoutHex": result["stdout"].hex(), "stderrHex": result["stderr"].hex(),
               "stdinSha256": digest(input_raw), "stdinSize": len(input_raw),
               "startedMonotonicNs": started, "returnedMonotonicNs": returned,
               "waited": result["waited"], "eof": result["eof"], "closed": result["closed"]}
        raw = encoded(row)
        self.written += len(raw)
        require(self.written <= EVIDENCE_BYTES // 4, stage, "BOUND")
        require(self.record.write(raw) == len(raw), stage, "RETURN_FAILED")
        self.record.flush()
        os.fsync(self.record.fileno())
        require(all(result[key] is True for key in ("waited", "eof", "closed")), stage, "RESOURCE_UNKNOWN")
        if success:
            require(result["code"] == 0 and result["stderr"] == b"", stage, "RETURN_FAILED")
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
        require(self.root is None and self.path is None, "ADMIN_CREATE", "REFUSED")
        raw = self._run(["/usr/bin/mktemp", "-d", ROOT_TEMPLATE], "ADMIN_CREATE")["stdout"]
        require(re.fullmatch(rb"/private/var/db/p2pkit-context\.[A-Za-z0-9]{10}\n", raw), "ADMIN_CREATE", "UNSUPPORTED")
        self.root = raw[:-1].decode("ascii")
        self.root_meta = self.metadata(self.root, "directory", mode=0o700)
        raw = self._run(["/usr/bin/mktemp", self.root + "/job.XXXXXXXXXX"], "ADMIN_CREATE")["stdout"]
        require(re.fullmatch(re.escape(self.root.encode("ascii")) + rb"/job\.[A-Za-z0-9]{10}\n", raw),
                "ADMIN_CREATE", "UNSUPPORTED")
        self.path = raw[:-1].decode("ascii")
        self.file_meta = self.metadata(self.path, "file", mode=0o600, size=0)
        self.metadata(self.root, "directory", mode=0o700, previous=self.root_meta)
        # mktemp was exclusive. tee is intentionally NOT described as exclusive:
        # only the checked root0700 original parent protects its truncating open.
        returned = self._run(["/usr/bin/tee", self.path], "ADMIN_CREATE", input_raw=self.plist)
        require(returned["stdout"] == self.plist, "ADMIN_CREATE", "IDENTITY_CHANGED",
                admin_site="PLIST_TEE", admin_item="PRIVATE_FILE")
        self.file_meta = self.metadata(self.path, "file", mode=0o600, previous=self.file_meta, size=len(self.plist))
        require(self._run(["/bin/cat", self.path], "ADMIN_CREATE")["stdout"] == self.plist,
                "ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="PLIST_CAT", admin_item="PRIVATE_FILE")
        self.metadata(self.path, "file", mode=0o600, previous=self.file_meta, size=len(self.plist))
        self.metadata(self.root, "directory", mode=0o700, previous=self.root_meta)
        write_new(self.directory / "launch.plist", self.plist)

    def bootstrap(self):
        require(self.path is not None and not self.bootstrapped and self.service is None, "BOOTSTRAP", "REFUSED")
        service_absent(self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP", success=False), self.label)
        self._run(["/bin/launchctl", "bootstrap", "system", self.path], "BOOTSTRAP")
        self.bootstrapped = True

    def inspect(self, identity, *, running=True):
        require(self.bootstrapped, "BOOTSTRAP", "REFUSED")
        if self.service is not None:
            same_identity(identity, self.service)
        raw = self._run(["/bin/launchctl", "print", "system/" + self.label], "BOOTSTRAP")["stdout"]
        result = parse_service_print(raw, self.label, self.path, self.arguments, identity["pid"], running=running)
        self.service = dict(identity)
        return result

    def retire(self, identity):
        require(self.service is not None and not self.retired and not self.removed, "RETIRE", "RESOURCE_UNKNOWN")
        self.inspect(identity, running=False)
        self._run(["/bin/launchctl", "bootout", "system/" + self.label], "RETIRE")
        service_absent(self._run(["/bin/launchctl", "print", "system/" + self.label], "RETIRE", success=False), self.label)
        self.retired = True
        self.metadata(self.root, "directory", mode=0o700, previous=self.root_meta)
        self.metadata(self.path, "file", mode=0o600, previous=self.file_meta, size=len(self.plist))
        require(self._run(["/bin/cat", self.path], "RETIRE")["stdout"] == self.plist, "RETIRE", "IDENTITY_CHANGED")
        self._run(["/bin/rm", self.path], "RETIRE")
        self.metadata(self.root, "directory", mode=0o700, previous=self.root_meta)
        self._run(["/bin/rmdir", self.root], "RETIRE")
        for name in (self.root, self.path):
            try:
                os.lstat(name)
            except FileNotFoundError as error:
                require(error.errno == errno.ENOENT, "RETIRE", "RESOURCE_UNKNOWN")
            else:
                raise ExperimentError("RETIRE", "RESOURCE_UNKNOWN")
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
    safe_component_path(path)
    for parent in path.parents:
        info = physical(parent).lstat()
        require(stat.S_ISDIR(info.st_mode), "SOURCE", "IDENTITY_CHANGED", source_site="PYTHON_PARENT_TYPE")
        require(info.st_uid in (0, os.getuid()), "SOURCE", "IDENTITY_CHANGED", source_site="PYTHON_PARENT_OWNER")
        require(not info.st_mode & 0o022, "SOURCE", "IDENTITY_CHANGED", source_site="PYTHON_PARENT_MODE")
    return file_pin(path, 64 * 1024 * 1024, end_ns, owners=(0, os.getuid()), executable=True)


class CommandFile:
    """The original Step's one held command-file FD; never passed to D/P."""

    def __init__(self, env):
        self.path = physical(env["GITHUB_OUTPUT"])
        temporary = physical(env["RUNNER_TEMP"])
        require(temporary in self.path.parents and ROOT not in self.path.parents, "PREPARE", "IDENTITY_CHANGED")
        self.fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        self.stamp = self._stamp(os.fstat(self.fd))
        self.emitted, self.closed = False, False
        require(self.stamp == self._stamp(self.path.lstat()) and self.stamp[6] == 0,
                "PREPARE", "IDENTITY_CHANGED")

    @staticmethod
    def _stamp(value):
        require(stat.S_ISREG(value.st_mode) and value.st_uid == os.getuid() and value.st_nlink == 1 and
                not value.st_mode & 0o022 and value.st_size <= STREAM_BYTES, "UPLOAD", "IDENTITY_CHANGED")
        return [value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid, value.st_nlink,
                value.st_size, value.st_mtime_ns, value.st_ctime_ns]

    def emit(self, values):
        require(type(values) is dict and values and not self.emitted and not self.closed and
                str(self.path) == os.environ.get("GITHUB_OUTPUT") and
                self.stamp == self._stamp(os.fstat(self.fd)) == self._stamp(self.path.lstat()), "UPLOAD", "IDENTITY_CHANGED")
        require(set(values) in ({"outcome", "successSha256"}, {"outcome", "closedFailureSha256"}, {"uploadAllowed"}) and
                all(type(value) is str and (value in ("SUCCESS", "CLOSED_FAILURE") if key == "outcome"
                                           else HASH.fullmatch(value)) for key, value in values.items()), "UPLOAD", "REFUSED")
        raw = "".join(key + "=" + value + "\n" for key, value in values.items()).encode("ascii")
        require(os.write(self.fd, raw) == len(raw), "UPLOAD", "RETURN_FAILED")
        os.fsync(self.fd)
        after = self._stamp(os.fstat(self.fd))
        require(after == self._stamp(self.path.lstat()) and after[:6] == self.stamp[:6] and after[6] == len(raw) and
                read_file(self.path) == raw, "UPLOAD", "IDENTITY_CHANGED")
        self.emitted = True
        self.close()
        return {"path": str(self.path), "stat": after, "sha256": digest(raw), "closed": self.closed}

    def close(self):
        if not self.closed:
            os.close(self.fd)
            self.closed = True


class ServiceCaptures:
    """Nonroot-owned standard streams, opened before reading prepared DATA."""

    def __init__(self, directory):
        self.directory, self.handles, self.closed = directory, [], False
        for fd, name in ((1, "service.stdout"), (2, "service.stderr")):
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
                os.dup2(null, fd)  # Retire the capture's standard-FD duplicate first.
                os.close(original)
                raw = read_file(self.directory / name)
                rows.append({"name": name, "size": len(raw), "sha256": digest(raw), "closed": True, "fsync": True})
        finally:
            os.close(null)
        self.closed = True
        return rows


PREPARED_KEYS = frozenset(("schema", "binding", "case", "github", "allocation", "source", "account", "foreground",
                            "boot", "interpreter", "directoryIdentity", "operationIdentity", "socketIdentity",
                            "caseEndNs", "stepEndNs", "jobEndNs"))


def validate_prepared(value, directory, native, interpreter):
    require(type(value) is dict and set(value) == PREPARED_KEYS and type(value["schema"]) is int and value["schema"] == 1 and
            type(value["binding"]) is str and HASH.fullmatch(value["binding"]) and value["case"] in CASES and
            directory.name == value["case"] and directory.parent.name == "evidence", "IDENTITY", "REFUSED")
    validate_account(account(), value["account"])
    require(private_directory(directory) == value["directoryIdentity"] and
            private_directory(directory.parent.parent) == value["operationIdentity"] and
            native.boot() == value["boot"] and interpreter == value["interpreter"], "IDENTITY", "IDENTITY_CHANGED")
    require(all(type(value[key]) is int and value[key] > 0 for key in ("caseEndNs", "stepEndNs", "jobEndNs")) and
            value["caseEndNs"] <= min(value["stepEndNs"], value["jobEndNs"]) and
            0 < left(value["caseEndNs"], "START") <= CASE_SECONDS, "START", "TIMEOUT")
    source = value["source"]
    require(type(source) is dict and set(source) == {"commit", "tree", "files"} and
            source["commit"] == value["github"]["source"] and source["tree"] == value["github"]["sourceTree"] and
            source["files"][SCRIPT] == digest(read_file(ROOT / SCRIPT, EVIDENCE_BYTES)), "SOURCE", "IDENTITY_CHANGED",
            source_site="PREPARED_SOURCE")
    require(value["github"]["workflow"] == WORKFLOW and value["github"]["job"] == "context_experiment" and
            value["github"]["repository"] == REPOSITORY and value["allocation"]["runId"] == value["github"]["runId"] and
            value["allocation"]["runAttempt"] == value["github"]["runAttempt"], "SOURCE", "IDENTITY_CHANGED",
            source_site="PREPARED_RUN")
    # These are forwarded original F observations, NOT a claim that this service
    # is another original hosted Step. No worker validates a Recipient or key.
    return value


def validate_ready(frame, prepared, service_identity, producer_identity):
    payload = validate_frame(frame, 3, prepared["binding"])
    require(set(payload) == {"producer", "parent", "account", "sigtermDefault", "sigtermBlocked", "sourceSha256",
                             "boot", "interpreter"} and payload["sigtermDefault"] is True and
            payload["sigtermBlocked"] is False, "IDENTITY", "REFUSED")
    validate_account(payload["account"], prepared["account"])
    same_identity(payload["parent"], service_identity)
    same_identity(payload["producer"], producer_identity)
    identity_account(producer_identity, prepared["account"])
    require(producer_identity["parentPid"] == service_identity["pid"] and
            producer_identity["parentUniqueId"] == service_identity["uniqueId"] and
            payload["sourceSha256"] == prepared["source"]["files"][SCRIPT] and payload["boot"] == prepared["boot"] and
            payload["interpreter"] == prepared["interpreter"]["path"], "IDENTITY", "IDENTITY_CHANGED")
    return payload


def socket_identity(path):
    path = physical(path)
    info = path.lstat()
    require(stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
            "IDENTITY", "IDENTITY_CHANGED")
    return [info.st_dev, info.st_ino]


def close_socket(channel):
    channel.close()
    require(channel.fileno() == -1, "CLOSE", "RESOURCE_UNKNOWN")


def service(directory):
    """Genuine launchd-selected nonroot account; no drop-privilege Python path."""
    directory = physical(directory)
    private_directory(directory)
    account()  # Root is refused before the first private capture/data operation.
    captures = ServiceCaptures(directory)
    native, channel, probe_channel, process, pipes, producer_identity = None, None, None, None, None, None
    prepared, trace, end_ns = None, [], None
    try:
        with at_stage("IDENTITY"):
            native = Darwin(observe_exit=False)
            prepared = parsed(read_file(directory / "prepared.json"))
            require(type(prepared) is dict and type(prepared.get("caseEndNs")) is int, "START", "TIMEOUT")
            end_ns = prepared["caseEndNs"]
            interpreter = checked_interpreter(end_ns)
            validate_prepared(prepared, directory, native, interpreter)
            service_identity = native.identity(os.getpid())
            identity_account(service_identity, prepared["account"])
            require(service_identity["parentPid"] == 1, "IDENTITY", "REFUSED")
            control = directory / "control.sock"
            require(socket_identity(control) == prepared["socketIdentity"], "IDENTITY", "IDENTITY_CHANGED")
            channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            channel.settimeout(left(end_ns, "IDENTITY"))
            channel.connect(str(control))
            channel.setblocking(False)
            foreground_peer = native.peer(channel)  # Fresh post-exec D -> F connection.
            same_identity(foreground_peer, prepared["foreground"])
            identity_account(foreground_peer, prepared["account"])
        binding = prepared["binding"]
        send_frame(channel, 1, binding, {"service": service_identity, "account": account(), "foregroundPeer": foreground_peer,
                   "boot": native.boot(), "sourceSha256": prepared["source"]["files"][SCRIPT], "interpreter": interpreter,
                   "directoryIdentity": private_directory(directory)}, trace, end_ns)
        received = read_frame(channel, 2, binding, trace, end_ns, captures.check)["payload"]
        require(received == prepared, "START", "IDENTITY_CHANGED")
        native.same(foreground_peer)
        # Only F's actual acknowledged D registration permits PREPARE. The one
        # child blocks on its inherited source-owned FD; no workload has START.
        with at_stage("IDENTITY"):
            probe_channel, child_channel = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                child_fd = child_channel.fileno()
                environment = child_environment(directory)
                environment.update(P2PKIT_CONTEXT_BINDING=binding, P2PKIT_CONTEXT_CASE_END_NS=str(end_ns))
                left(end_ns, "START")
                process = subprocess.Popen([interpreter["path"], "-I", "-B", "-S", str(ROOT / SCRIPT), "_probe", str(child_fd)],
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           close_fds=True, pass_fds=(child_fd,), cwd=ROOT, env=environment)
                producer_identity = native.identity(process.pid)
                require(producer_identity["parentPid"] == os.getpid() and
                        producer_identity["parentUniqueId"] == service_identity["uniqueId"], "IDENTITY", "IDENTITY_CHANGED")
                pipes = ProbePipes(process)
            finally:
                close_socket(child_channel)
            probe_channel.setblocking(False)
            ready = read_frame(probe_channel, 3, binding, trace, end_ns, pipes.pump)
            validate_ready(ready, prepared, service_identity, producer_identity)
            native.same(producer_identity)
        send_frame(channel, 4, binding, {"readyFrame": ready}, trace, end_ns)
        start = read_frame(channel, 5, binding, trace, end_ns, pipes.pump)["payload"]
        require(set(start) == {"case", "account", "service", "sourceSha256", "interface", "deadlineNs"} and
                start["case"] == prepared["case"] and start["account"] == prepared["account"] and
                start["sourceSha256"] == prepared["source"]["files"][SCRIPT] and start["deadlineNs"] == end_ns,
                "START", "IDENTITY_CHANGED")
        same_identity(start["service"], service_identity)
        require(start["interface"] is None if prepared["case"] != "N1" else type(start["interface"]) is dict,
                "START", "REFUSED")
        native.same(producer_identity)
        forward_started = time.monotonic_ns()
        send_frame(probe_channel, 6, binding, start, trace, end_ns)
        forward_returned = time.monotonic_ns()
        result_frame = None
        if prepared["case"] == "N3":
            # Crucial ordering: forward actual START first, THEN consume the
            # ordered half-close. Earlier EOF failed read_frame(5), no success.
            wait_eof(channel, end_ns, pipes.pump)
            with at_stage("CLOSE"):
                native.signal(producer_identity, signal.SIGTERM, end_ns)
        else:
            result_frame = read_frame(probe_channel, 7, binding, trace, end_ns, pipes.pump)
            payload = result_frame["payload"]
            require(set(payload) == {"case", "probe", "observation"} and payload["case"] == prepared["case"], "CHILD_WAIT", "REFUSED")
            validate_probe_result(payload["probe"])
            validate_probe_observation(payload["observation"], payload["probe"], prepared["case"], end_ns)
        wait_eof(probe_channel, end_ns, pipes.pump)
        close_socket(probe_channel)
        producer_code, producer_streams = pipes.finish(end_ns, directory)
        expected = -signal.SIGTERM if prepared["case"] == "N3" else (
            23 if prepared["case"] == "N2" or result_frame["payload"]["probe"]["result"] == "FAIL" else 0)
        require(producer_code == expected, "CHILD_WAIT", "STATUS_UNEXPECTED")
        native.close()
        service_streams = captures.close()
        payload = {"case": prepared["case"], "producerCode": producer_code, "producerStreams": producer_streams,
                   "serviceStreams": service_streams, "resultFrame": result_frame, "tracePrefix": list(trace),
                   "producerControlEof": True, "producerWait": True, "nativeClosed": True, "capturesClosed": True,
                   "signalReturns": native.signals,
                   "startForward": {"startedMonotonicNs": forward_started, "returnedMonotonicNs": forward_returned}}
        # DATA is provisional. No self exit receipt, ACK or ninth frame exists.
        send_frame(channel, 8, binding, payload, trace, end_ns)
        close_socket(channel)
        if prepared["case"] == "N4":
            require(signal.getsignal(signal.SIGTERM) == signal.SIG_DFL and
                    signal.SIGTERM not in signal.pthread_sigmask(signal.SIG_BLOCK, []), "SERVICE_WAIT", "REFUSED")
            signal.raise_signal(signal.SIGTERM)
            raise ExperimentError("SERVICE_WAIT", "STATUS_UNEXPECTED")
        return 24 if prepared["case"] == "N3" else producer_code
    except BaseException as error:
        # A failed service never sends a substituted final success frame. D's
        # own cleanup uses only its inherited case end, never a new120-second
        # budget. The original F owns the one suite-wide exceptional interval.
        if process is not None and process.poll() is None and native is not None and producer_identity is not None:
            with contextlib.suppress(BaseException):
                native.signal(producer_identity, signal.SIGTERM, end_ns)
        if pipes is not None and not pipes.closed:
            with contextlib.suppress(BaseException):
                pipes.finish(end_ns, directory)
        if not captures.closed:
            with contextlib.suppress(BaseException):
                os.write(2, (public_error(error) + "\n").encode("ascii"))
        raise
    finally:
        for stream in (probe_channel, channel):
            if stream is not None and stream.fileno() != -1:
                close_socket(stream)
        if native is not None and not native.closed:
            native.close()
        if not captures.closed:
            captures.close()


class Context:
    """Original F-only state for this one experiment, not a reusable owner API."""

    def __init__(self):
        self.env, self.started = dict(os.environ), time.monotonic_ns()
        self.native, self.output, self.recipient, self.exporter = None, None, None, None
        self.current, self.sentinel, self.sentinel_pipes = None, None, None
        self.sentinel_closed, self.finished, self.export_called = False, False, False
        self.abort_end, self.result, self.case_results = None, None, []

    def limit(self, seconds):
        return min(time.monotonic_ns() + seconds * NS, self.step_end, self.job_end, self.policy_end)


def original_request(env):
    require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and
            platform.system() == "Darwin" and platform.machine() == "arm64" and
            env.get("RUNNER_OS") == "macOS" and env.get("RUNNER_ARCH") == "ARM64", "SOURCE", "UNSUPPORTED")
    require(not any(key.startswith("DYLD_") or key in ("PYTHONPATH", "PYTHONHOME", "LD_PRELOAD") for key in env),
            "SOURCE", "REFUSED")
    require(physical(Path(__file__)) == ROOT / SCRIPT and physical(env["GITHUB_WORKSPACE"]) / "controller" == ROOT,
            "SOURCE", "IDENTITY_CHANGED", source_site="ORIGINAL_SOURCE_PATHS")
    request = parsed(env.get("P2PKIT_CONTEXT_REQUEST", "").encode("utf-8"))
    event = parsed(read_file(physical(env["GITHUB_EVENT_PATH"]), EVIDENCE_BYTES), EVIDENCE_BYTES)
    require(type(event) is dict and "inputs" in event, "SOURCE", "REFUSED")
    return request, validate_request(request, env, event["inputs"])


def operation_paths(env):
    parent, temporary, workspace = physical(env["P2PKIT_CONTEXT_OPERATION"]), physical(env["RUNNER_TEMP"]), physical(env["GITHUB_WORKSPACE"])
    require(parent.parent == temporary and re.fullmatch(r"p2pkit-context-experiment-[A-Za-z0-9_-]{6,64}", parent.name) and
            workspace not in parent.parents and parent not in workspace.parents and parent != workspace,
            "PREPARE", "IDENTITY_CHANGED")
    safe_component_path(parent)
    return parent, private_directory(parent)


def prepare():
    context = Context()
    try:
        with at_stage("PREPARE"):
            context.request, context.github = original_request(context.env)
            context.account = account()
            context.parent, context.parent_identity = operation_paths(context.env)
            require({path.name for path in context.parent.iterdir()} == {"allocation.json"}, "PREPARE", "REFUSED")
            context.allocation = parsed(read_file(context.parent / "allocation.json"))
            now, wall = time.monotonic_ns(), time.time_ns()
            context.job_end = validate_allocation(context.allocation, context.request, context.github, now, wall)
            context.policy_end = now + POLICY_EXPIRES * NS - wall
            context.step_end = min(context.started + STEP_SECONDS * NS, context.job_end, context.policy_end)
            require(left(context.job_end, "PREPARE") >= STEP_SECONDS + UPLOAD_SECONDS, "PREPARE", "TIMEOUT")
            end = min(context.started + PREPARE_SECONDS * NS, context.step_end, context.policy_end)
            context.output = CommandFile(context.env)
            for name in ("evidence", "crypto", "outputs", "home", "tmp"):
                (context.parent / name).mkdir(mode=0o700)
                private_directory(context.parent / name, empty=True)
            context.evidence = context.parent / "evidence"
            context.environment = child_environment(context.parent)
            context.os_env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"}
        with at_stage("SOURCE"):
            context.source = source_snapshot(end, context.environment)
            require(context.source["commit"] == context.request["source_sha"] and
                    context.source["tree"] == context.request["source_tree"], "SOURCE", "IDENTITY_CHANGED",
                    source_site="CHECKOUT_SOURCE")
            context.interpreter = checked_interpreter(end)
            context.os_files = {}
            for name in (*OS_PARENTS, *OS_TOOLS):
                path = physical(name)
                info = path.lstat()
                require(info.st_uid == 0, "SOURCE", "IDENTITY_CHANGED",
                        source_site="OS_OWNER", source_item=source_os_item(name))
                require(not info.st_mode & 0o022, "SOURCE", "IDENTITY_CHANGED",
                        source_site="OS_MODE", source_item=source_os_item(name))
                require(stat.S_ISDIR(info.st_mode) if name in OS_PARENTS else stat.S_ISREG(info.st_mode),
                        "SOURCE", "IDENTITY_CHANGED", source_site="OS_TYPE", source_item=source_os_item(name))
                # Installed OS tools retain their original link count; private
                # files still require one link. Directory child counts may change.
                context.os_files[name] = ([info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid] +
                                          ([info.st_nlink] if name in OS_TOOLS else []))
            version = capture_fixed(["/usr/bin/sw_vers", "-productVersion"], end, context.os_env)
            require(version["code"] == 0 and version["stderr"] == b"" and
                    re.fullmatch(rb"26\.[0-9]+(?:\.[0-9]+)?\n", version["stdout"]), "SOURCE", "UNSUPPORTED")
            context.os_version = version["stdout"].decode("ascii").strip()
        with at_stage("IDENTITY"):
            context.native = Darwin()
            context.foreground = context.native.identity(os.getpid())
            identity_account(context.foreground, context.account)
            context.boot = context.native.boot()
            context.username = pwd.getpwuid(context.account["uid"]).pw_name
            context.groupname = grp.getgrgid(context.account["gid"]).gr_name
            require(pwd.getpwnam(context.username).pw_uid == context.account["uid"] and
                    grp.getgrnam(context.groupname).gr_gid == context.account["gid"], "IDENTITY", "IDENTITY_CHANGED")
        with at_stage("POLICY"):
            policy_raw = read_file(ROOT / POLICY_PATH, 96 * 1024)
            policy = validate_policy(policy_raw, time.time())
            key_path = context.parent / "recipient-public.asc"
            write_new(key_path, policy["recipient"]["publicKey"].encode("ascii"))
            gpg = shutil.which("gpg")
            require(gpg is not None, "POLICY", "UNSUPPORTED")
            context.gpg = file_pin(Path(gpg).resolve(strict=True), 64 * 1024 * 1024, end,
                                   owners=(0, os.getuid()), executable=True)
            load_module("hosted_evidence_primitives", "scripts/hosted_evidence_primitives.py")
            context.exporter = load_module("context_public_evidence", "scripts/hosted_evidence.py")
            # Public validation has its maintained60s plus bounded cleanup tail.
            # Reserve it inside the ORIGINAL prepare/Step/job ends before entry.
            require(left(end, "POLICY") >= 70, "POLICY", "TIMEOUT")
            context.recipient = context.exporter.validate_recipient(key_path, FINGERPRINT, context.parent / "crypto")
            left(end, "POLICY")
            require(context.recipient.fingerprint == FINGERPRINT and context.recipient.key_sha256 == KEY_SHA256 and
                    context.recipient.encryption_fingerprint == ENCRYPTION_FINGERPRINT and
                    context.recipient.expires_at == KEY_EXPIRES and context.recipient.work_dir == context.parent / "crypto" and
                    str(context.recipient.executable) == context.gpg["path"], "POLICY", "IDENTITY_CHANGED")
            context.recipient_original = context.recipient
            context.recipient_home = private_directory(context.recipient.home)
            context.recipient_work = private_directory(context.recipient.work_dir)
            context.recipient_files = {name: file_pin(context.recipient.work_dir / name, 64 * 1024, end)
                                       for name in ("recipient.asc", "recipient.gpg")}
        write_new(context.evidence / "original-foreground.json", encoded({"schema": 1, "scope": SCOPE,
                  "github": context.github, "allocation": context.allocation, "account": context.account,
                  "foreground": context.foreground, "boot": context.boot, "source": context.source,
                  "interpreter": context.interpreter, "pythonVersion": sys.version, "osVersion": context.os_version,
                  "osFiles": context.os_files,
                  "policySha256": POLICY_SHA256, "policyExpires": POLICY_EXPIRES,
                  "recipientValidationReturned": True, "startedMonotonicNs": context.started,
                  "preparedMonotonicNs": time.monotonic_ns(), "stepEndNs": context.step_end, "jobEndNs": context.job_end}))
        left(end, "PREPARE")
        return context
    except BaseException:
        if context.native is not None and not context.native.closed:
            context.native.close()
        if context.output is not None:
            context.output.close()
        raise


def validate_hello(payload, prepared, peer):
    require(type(payload) is dict and set(payload) == {"service", "account", "foregroundPeer", "boot", "sourceSha256",
            "interpreter", "directoryIdentity"}, "IDENTITY", "REFUSED")
    same_identity(payload["service"], peer)
    same_identity(payload["foregroundPeer"], prepared["foreground"])
    identity_account(peer, prepared["account"])
    validate_account(payload["account"], prepared["account"])
    require(peer["parentPid"] == 1 and payload["boot"] == prepared["boot"] and
            payload["sourceSha256"] == prepared["source"]["files"][SCRIPT] and
            payload["interpreter"] == prepared["interpreter"] and payload["directoryIdentity"] == prepared["directoryIdentity"],
            "IDENTITY", "IDENTITY_CHANGED")


def validate_final_frame(payload, case, prepared, observed, ready, start):
    require(type(payload) is dict and set(payload) == {"case", "producerCode", "producerStreams", "serviceStreams",
            "resultFrame", "tracePrefix", "producerControlEof", "producerWait", "nativeClosed", "capturesClosed",
            "signalReturns", "startForward"} and
            payload["case"] == case and type(payload["producerCode"]) is int and
            all(payload[key] is True for key in ("producerControlEof", "producerWait", "nativeClosed", "capturesClosed")),
            "CHILD_WAIT", "RESOURCE_UNKNOWN")
    trace = payload["tracePrefix"]
    require(type(trace) is list, "START", "REFUSED")
    # The final frame cannot hash itself. F supplies its actually received row8;
    # every F-observed prefix hash and the original forwarded P frame is joined.
    validate_frame_trace(case, [*trace, observed[-1]])
    actual = {row["serial"]: row for row in trace}
    for row in observed[:-1]:
        require(actual.get(row["serial"]) == row, "START", "IDENTITY_CHANGED")
    require(actual.get(3) == frame_record(ready) and
            actual.get(6) == frame_record(frame_value(6, prepared["binding"], start)), "START", "IDENTITY_CHANGED")
    probe = None
    forward = payload["startForward"]
    require(type(forward) is dict and set(forward) == {"startedMonotonicNs", "returnedMonotonicNs"} and
            all(type(value) is int and value > 0 for value in forward.values()) and
            forward["startedMonotonicNs"] <= forward["returnedMonotonicNs"] < prepared["caseEndNs"], "START", "TIMEOUT")
    require(type(payload["signalReturns"]) is list, "CLOSE", "REFUSED")
    if case == "N3":
        require(payload["resultFrame"] is None and 7 not in actual, "CHILD_WAIT", "REFUSED")
        require(len(payload["signalReturns"]) == 1, "CLOSE", "REFUSED")
        sent = payload["signalReturns"][0]
        require(type(sent) is dict and set(sent) == {"identity", "signal", "returnedCode", "startedMonotonicNs", "returnedMonotonicNs"}
                and type(sent["signal"]) is int and sent["signal"] == signal.SIGTERM and type(sent["returnedCode"]) is int and
                sent["returnedCode"] == 0 and type(sent["startedMonotonicNs"]) is int and
                type(sent["returnedMonotonicNs"]) is int and forward["returnedMonotonicNs"] <= sent["startedMonotonicNs"] <=
                sent["returnedMonotonicNs"] < prepared["caseEndNs"], "CLOSE", "RETURN_FAILED")
        same_identity(sent["identity"], ready["payload"]["producer"])
    else:
        require(payload["signalReturns"] == [], "CLOSE", "REFUSED")
        result = payload["resultFrame"]
        data = validate_frame(result, 7, prepared["binding"])
        require(set(data) == {"case", "probe", "observation"} and data["case"] == case and actual.get(7) == frame_record(result),
                "CHILD_WAIT", "IDENTITY_CHANGED")
        probe = validate_probe_result(data["probe"])
        validate_probe_observation(data["observation"], probe, case, prepared["caseEndNs"])
    return probe, [*trace, observed[-1]]


def verify_streams(directory, rows, names, *, service=False):
    require(type(rows) is list and len(rows) == 2, "CLOSE", "RESOURCE_UNKNOWN")
    for row, name in zip(rows, names):
        expected = {"name", "size", "sha256", "closed", "fsync"} if service else {"name", "size", "sha256", "eof", "closed"}
        require(type(row) is dict and set(row) == expected and row["name"] == name and type(row["size"]) is int and
                0 <= row["size"] <= STREAM_BYTES and row["closed"] is True and
                row["fsync" if service else "eof"] is True, "CLOSE", "RESOURCE_UNKNOWN")
        raw = read_file(directory / name)
        require(len(raw) == row["size"] and digest(raw) == row["sha256"], "CLOSE", "IDENTITY_CHANGED")


def perform_case(context, case, native_end):
    require(case in CASES and len(context.case_results) == CASES.index(case) and context.abort_end is None,
            "START", "REFUSED")
    end_ns = min(context.limit(CASE_SECONDS), native_end)
    left(end_ns, "START")
    directory = context.evidence / case
    directory.mkdir(mode=0o700)
    for name in ("home", "tmp"):
        (directory / name).mkdir(mode=0o700)
    binding = digest(os.urandom(32))
    label = "p2pkit.context.r" + context.github["runId"] + ".a" + context.github["runAttempt"] + "." + case.lower() + "." + binding[:16]
    state = {"case": case, "directory": directory, "listener": None, "channel": None, "admin": None,
             "service": None, "producer": None, "prepareSent": False, "socket": None}
    context.current = state
    admin = state["admin"] = Admin(context, directory, label, end_ns)
    # Before the first service, inspect the actual fixed physical OS paths and
    # ACLs. Later cases recheck their held local identities; never adopt a tool.
    if case == "N1":
        for name in (*OS_PARENTS, *OS_TOOLS):
            observed = admin.metadata(name, "directory" if name in OS_PARENTS else "file")
            require([observed[key] for key in ("dev", "ino", "mode", "uid", "gid")] +
                    ([observed["nlink"]] if name in OS_TOOLS else []) == context.os_files[name],
                    "SOURCE", "IDENTITY_CHANGED", source_site="OS_FIRST_IDENTITY", source_item=source_os_item(name))
    else:
        for name, original in context.os_files.items():
            info = physical(name).lstat()
            require([info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid] +
                    ([info.st_nlink] if name in OS_TOOLS else []) == original,
                    "SOURCE", "IDENTITY_CHANGED", source_site="OS_NEXT_IDENTITY", source_item=source_os_item(name))
    control_path = directory / "control.sock"
    require(len(str(control_path).encode("utf-8")) + 1 <= 104, "IDENTITY", "BOUND")
    with at_stage("IDENTITY"):
        listener = state["listener"] = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(control_path))
        os.chmod(control_path, 0o600)
        state["socket"] = socket_identity(control_path)
        listener.listen(1)
        listener.setblocking(False)
        prepared = {"schema": 1, "binding": binding, "case": case, "github": context.github,
                    "allocation": context.allocation, "source": context.source, "account": context.account,
                    "foreground": context.foreground, "boot": context.boot, "interpreter": context.interpreter,
                    "directoryIdentity": private_directory(directory), "operationIdentity": context.parent_identity,
                    "socketIdentity": state["socket"], "caseEndNs": end_ns, "stepEndNs": context.step_end,
                    "jobEndNs": context.job_end}
        require(len(encoded(prepared)) <= FRAME_BYTES, "START", "BOUND")
        write_new(directory / "prepared.json", encoded(prepared))
    with at_stage("ADMIN_CREATE"):
        admin.create()
    with at_stage("BOOTSTRAP"):
        admin.bootstrap()
    while True:
        ready, _, _ = select.select([listener], [], [], min(0.05, left(end_ns, "IDENTITY")))
        if ready:
            channel, _address = listener.accept()
            state["channel"] = channel
            channel.setblocking(False)
            close_socket(listener)  # No second peer, reconnect or additional channel.
            break
    trace = []
    with at_stage("IDENTITY"):
        peer = context.native.peer(channel)
        hello = read_frame(channel, 1, binding, trace, end_ns)
        validate_hello(hello["payload"], prepared, peer)
        registration = admin.inspect(peer)
        state["service"] = peer
    with at_stage("ATTACH"):
        context.native.watch(peer)  # Original D observation precedes PREPARE/P creation.
    state["prepareSent"] = True
    send_frame(channel, 2, binding, prepared, trace, end_ns)
    ready = read_frame(channel, 4, binding, trace, end_ns)["payload"]
    require(set(ready) == {"readyFrame"}, "IDENTITY", "REFUSED")
    ready = ready["readyFrame"]
    with at_stage("IDENTITY"):
        data = validate_frame(ready, 3, binding)
        require(type(data.get("producer")) is dict and type(data["producer"].get("pid")) is int, "IDENTITY", "REFUSED")
        producer_identity = context.native.identity(data["producer"]["pid"])
        validate_ready(ready, prepared, peer, producer_identity)
        state["producer"] = producer_identity
    with at_stage("ATTACH"):
        context.native.watch(producer_identity)
        context.native.same(peer)
        context.native.same(producer_identity)
    with at_stage("NATIVE_SEND"):
        selected = interface_ipv4() if case == "N1" else None
    start = {"case": case, "account": context.account, "service": peer, "sourceSha256": context.source["files"][SCRIPT],
             "interface": selected, "deadlineNs": end_ns}
    # Both actual original registration receipts returned before this START.
    start_started = time.monotonic_ns()
    require(all(context.native.registrations[value["pid"]]["recheckedMonotonicNs"] <= start_started
                for value in (peer, producer_identity)), "START", "IDENTITY_CHANGED")
    send_frame(channel, 5, binding, start, trace, end_ns)
    start_returned = time.monotonic_ns()
    if case == "N3":
        with at_stage("CLOSE"):
            channel.shutdown(socket.SHUT_WR)  # Ordered after START, no extra ACK frame.
    final = read_frame(channel, 8, binding, trace, end_ns)["payload"]
    probe, full_trace = validate_final_frame(final, case, prepared, trace, ready, start)
    require(start_started <= final["startForward"]["startedMonotonicNs"], "START", "IDENTITY_CHANGED")
    wait_eof(channel, end_ns)
    close_socket(channel)
    with at_stage("SERVICE_WAIT"):
        events = context.native.wait([producer_identity, peer], end_ns)
    require(events[producer_identity["pid"]]["status"]["popenCode"] == final["producerCode"],
            "CHILD_WAIT", "STATUS_UNEXPECTED")
    passed = validate_case_result(case, final["producerCode"], events[peer["pid"]]["status"], probe)
    verify_streams(directory, final["producerStreams"], ("producer.stdout", "producer.stderr"))
    verify_streams(directory, final["serviceStreams"], ("service.stdout", "service.stderr"), service=True)
    sentinel_after_cancellation = None
    if case == "N3":
        require(context.sentinel.poll() is None, "CLOSE", "STATUS_UNEXPECTED")
        sentinel_after_cancellation = {"identity": context.native.same(context.sentinel_identity), "popenCode": None,
                                       "observedMonotonicNs": time.monotonic_ns()}
    with at_stage("RETIRE"):
        admin.retire(peer)
        require(socket_identity(control_path) == state["socket"], "RETIRE", "IDENTITY_CHANGED")
        control_path.unlink()
        require(not os.path.lexists(control_path), "RETIRE", "RESOURCE_UNKNOWN")
        admin.close()
    result = {"case": case, "passed": passed, "registration": registration, "service": peer, "producer": producer_identity,
              "producerNative": events[producer_identity["pid"]], "serviceNative": events[peer["pid"]],
              "registrations": [context.native.registrations[value["pid"]] for value in (peer, producer_identity)],
              "startSend": {"startedMonotonicNs": start_started, "returnedMonotonicNs": start_returned,
                            "frameSha256": frame_record(frame_value(5, binding, start))["sha256"]},
              "sentinelAfterCancellation": sentinel_after_cancellation,
              "originalServiceFinalData": final, "probe": probe, "trace": full_trace, "selectedInterface": selected,
              "closedMonotonicNs": time.monotonic_ns(), "caseEndNs": end_ns,
              "closure": {"producerWait": final["producerWait"], "producerStreams": True,
                          "producerNativeExit": producer_identity["pid"] in context.native.events,
                          "serviceNativeExit": peer["pid"] in context.native.events, "controlEof": True,
                          "nativeClosed": False, "registrationAbsent": admin.retired,
                          "rootObjectsRemoved": admin.removed, "adminClosed": admin.closed}}
    left(end_ns, "CLOSE")
    context.case_results.append(result)
    context.current = None
    return result


def close_sentinel(context, end_ns):
    require(context.sentinel is not None and not context.sentinel_closed, "CLOSE", "RESOURCE_UNKNOWN")
    context.sentinel.stdin.close()  # Its private input has never received bytes.
    require(context.sentinel.stdin.closed, "CLOSE", "RESOURCE_UNKNOWN")
    code, streams = context.sentinel_pipes.finish(end_ns, context.evidence / "sentinel")
    require(code == 0 and context.sentinel_pipes.closed, "CLOSE", "STATUS_UNEXPECTED")
    context.sentinel_closed = True
    return {"identity": context.sentinel_identity, "waitCode": code, "stdinClosed": True, "streams": streams,
            "closedMonotonicNs": time.monotonic_ns()}


def abort_suite(context):
    """One nonrenewable exceptional interval. Never turns failure into export."""
    if context.abort_end is None:
        context.abort_end = context.limit(ABORT_SECONDS)
    end_ns, state = context.abort_end, context.current
    failures = []

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
        identities = [state[key] for key in ("producer", "service") if state[key] is not None]
        watched = [value for value in identities if value["pid"] in context.native.watched]
        # Only original joined D/P identities, never sentinel/PID-name/group
        # fallback. A failed or missing watch/identity is not repairable DATA.
        if attempt(context.native.poll):
            for identity in watched:
                if identity["pid"] not in context.native.events:
                    attempt(lambda identity=identity: context.native.signal(identity, signal.SIGTERM, end_ns))
        joined = bool(watched) and attempt(lambda: context.native.wait(watched, end_ns))
        admin = state["admin"]
        all_known = len(watched) == len(identities) and (state["producer"] is not None or not state["prepareSent"])
        if joined and all_known and admin is not None and admin.service is not None and not admin.retired and not _UNCLOSED_COMMANDS:
            admin.end_ns = end_ns  # Same single original F abort interval, never a reset.
            attempt(lambda: admin.retire(state["service"]))
        for name in ("channel", "listener"):
            stream = state[name]
            if stream is not None and stream.fileno() != -1:
                attempt(lambda stream=stream: close_socket(stream))
        if state["socket"] is not None:
            def remove_socket():
                path = state["directory"] / "control.sock"
                require(socket_identity(path) == state["socket"], "CLOSE", "IDENTITY_CHANGED")
                path.unlink()
            attempt(remove_socket)
        if admin is not None and not admin.closed:
            attempt(admin.close)
    if context.sentinel is not None and not context.sentinel_closed:
        attempt(lambda: close_sentinel(context, end_ns))
    if context.native is not None and not context.native.closed:
        attempt(context.native.close)
    if context.output is not None:
        attempt(context.output.close)
    # This is deliberately outside any success path; no cleanup receipt permits
    # retrying a case, resetting a clock, freezing or exporting the failed suite.
    attempt(lambda: write_new(context.evidence / "aborted-no-export.json", encoded({"schema": 1, "scope": SCOPE,
                  "qualification": "REFUSED", "exportAllowed": False, "cleanupErrors": failures,
                  "adminLifetimeUnknown": bool(_UNCLOSED_COMMANDS), "abortEndNs": end_ns,
                  "registrationAttempts": context.native.attach_attempts, "signalReturns": context.native.signals})))


def run_cases(context):
    require(not context.finished and context.abort_end is None and not context.export_called and not context.case_results,
            "START", "REFUSED")
    native_end = context.limit(NATIVE_SECONDS)
    try:
        with at_stage("IDENTITY"):
            sentinel_directory = context.evidence / "sentinel"
            sentinel_directory.mkdir(mode=0o700)
            left(native_end, "START")
            context.sentinel = subprocess.Popen(["/bin/cat"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE, close_fds=True, env=context.environment)
            context.sentinel_pipes = ProbePipes(context.sentinel)
            context.sentinel_identity = context.native.identity(context.sentinel.pid)
            require(context.sentinel_identity["parentPid"] == os.getpid() and
                    context.sentinel_identity["parentUniqueId"] == context.foreground["uniqueId"],
                    "IDENTITY", "IDENTITY_CHANGED")
            identity_account(context.sentinel_identity, context.account)
        for case in CASES:
            perform_case(context, case, native_end)
        with at_stage("CLOSE"):
            context.native.same(context.sentinel_identity)
            sentinel = close_sentinel(context, native_end)
            context.native.same(context.foreground)
            context.native.close()
            require(not _UNCLOSED_COMMANDS and context.sentinel_closed and context.current is None,
                    "CLOSE", "RESOURCE_UNKNOWN")
            for row in context.case_results:
                row["closure"]["nativeClosed"] = context.native.closed and row["originalServiceFinalData"]["nativeClosed"]
                validate_closure(row["closure"])
                write_new(context.evidence / row["case"] / "foreground-result.json", encoded(row))
            context.result = {"schema": 1, "scope": SCOPE, "cases": context.case_results, "sentinel": sentinel,
                              "outcome": "SUCCESS" if all(row["passed"] for row in context.case_results) else "CLOSED_FAILURE",
                              "closedMonotonicNs": time.monotonic_ns(), "nativeEndNs": native_end,
                              "originalCause": "UNKNOWN", "productiveIntegrationAccepted": False,
                              "holdsChanged": False, "releaseReadiness": "NOT_READY"}
            left(native_end, "CLOSE")
            context.finished = True
            return context.result
    except BaseException:
        abort_suite(context)
        raise


def freeze_evidence(root, end_ns):
    private_directory(root)
    files, directories, total = [], [], 0
    for current, children, names in os.walk(root, topdown=True, followlinks=False):
        children.sort()
        names.sort()
        directory = physical(current)
        private_directory(directory)
        directories.append(directory)
        require(len(files) + len(directories) + len(names) <= EVIDENCE_MEMBERS, "FREEZE", "BOUND")
        for name in names:
            path = directory / name
            require(re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name), "FREEZE", "REFUSED")
            pin = file_pin(path, EVIDENCE_BYTES, end_ns)
            total += pin["size"]
            require(total <= EVIDENCE_BYTES, "FREEZE", "BOUND")
            files.append((path, pin))
    require(files and len(files) + len(directories) <= EVIDENCE_MEMBERS, "FREEZE", "BOUND")
    frozen = []
    for path, before in files:
        left(end_ns, "FREEZE")
        os.chmod(path, 0o400, follow_symlinks=False)
        after = file_pin(path, EVIDENCE_BYTES, end_ns)
        require(after["sha256"] == before["sha256"] and after["size"] == before["size"] and
                after["stat"][:2] == before["stat"][:2] and stat.S_IMODE(after["stat"][2]) == 0o400,
                "FREEZE", "IDENTITY_CHANGED")
        frozen.append({"name": str(path.relative_to(root)), "stat": after["stat"],
                       "size": after["size"], "sha256": after["sha256"]})
    for path in reversed(directories):
        os.chmod(path, 0o500, follow_symlinks=False)
        info = path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o500,
                "FREEZE", "IDENTITY_CHANGED")
    left(end_ns, "FREEZE")
    return {"files": frozen, "directories": [str(path.relative_to(root)) for path in directories], "bytes": total}


def output_snapshot(parent, github, end_ns, *, expected_manifest=None):
    outputs, directory = parent / "outputs", parent / "outputs" / "encrypted"
    private_directory(outputs)
    identity = private_directory(directory)
    require({path.name for path in directory.iterdir()} == {"evidence.tar.gz.gpg", "manifest.json"}, "UPLOAD", "REFUSED")
    raw = read_file(directory / "manifest.json")
    manifest = parsed(raw)
    require(raw == encoded(manifest) and type(manifest) is dict and
            set(manifest) == {"schema", "scope", "source", "github", "artifact"} and
            type(manifest["schema"]) is int and manifest["schema"] == 1 and
            manifest["scope"] == "ENCRYPTED_PRIVATE_TEST_EVIDENCE" and
            manifest["source"] == {"commit": github["source"], "tree": github["sourceTree"]} and
            manifest["github"] == {"repository": REPOSITORY, "runId": github["runId"], "runAttempt": github["runAttempt"]},
            "UPLOAD", "IDENTITY_CHANGED")
    require(expected_manifest is None or manifest == expected_manifest, "EXPORT", "IDENTITY_CHANGED")
    artifact = manifest["artifact"]
    require(type(artifact) is dict and set(artifact) == {"name", "size", "sha256"} and
            artifact["name"] == "evidence.tar.gz.gpg" and type(artifact["size"]) is int and
            0 < artifact["size"] <= MAX_CIPHERTEXT_BYTES and type(artifact["sha256"]) is str and HASH.fullmatch(artifact["sha256"]),
            "UPLOAD", "REFUSED")
    files = {name: file_pin(directory / name, maximum, end_ns) for name, maximum in
             (("evidence.tar.gz.gpg", MAX_CIPHERTEXT_BYTES), ("manifest.json", STREAM_BYTES))}
    require(files["evidence.tar.gz.gpg"]["sha256"] == artifact["sha256"] and
            files["evidence.tar.gz.gpg"]["size"] == artifact["size"] and files["manifest.json"]["sha256"] == digest(raw),
            "UPLOAD", "IDENTITY_CHANGED")
    return {"identity": identity, "files": files}


def finish_export(context, result):
    """One public export using the very same original F Recipient, after closure."""
    require(context.finished and result is context.result and context.current is None and context.abort_end is None and
            context.sentinel_closed and context.sentinel_pipes.closed and context.native.closed and not _UNCLOSED_COMMANDS and
            not context.export_called and context.recipient is context.recipient_original,
            "EXPORT", "RESOURCE_UNKNOWN")
    require(type(result) is dict and result["cases"] is context.case_results and
            [row["case"] for row in context.case_results] == list(CASES), "EXPORT", "REFUSED")
    for row in context.case_results:
        validate_closure(row["closure"])
        require(type(row["passed"]) is bool and row["passed"] == validate_case_result(
            row["case"], row["originalServiceFinalData"]["producerCode"], row["serviceNative"]["status"], row["probe"]),
                "EXPORT", "IDENTITY_CHANGED")
    outcome = "SUCCESS" if all(row["passed"] for row in context.case_results) else "CLOSED_FAILURE"
    require(result["outcome"] == outcome, "EXPORT", "IDENTITY_CHANGED")
    freeze_end = context.limit(FREEZE_SECONDS)
    with at_stage("FREEZE"):
        request, github = original_request(dict(os.environ))
        require(request == context.request and github == context.github and account() == context.account and
                private_directory(context.parent) == context.parent_identity and
                source_snapshot(freeze_end, context.environment) == context.source and
                checked_interpreter(freeze_end) == context.interpreter, "SOURCE", "IDENTITY_CHANGED",
                source_site="FREEZE_SOURCE")
        policy_raw = read_file(ROOT / POLICY_PATH, 96 * 1024)
        validate_policy(policy_raw, context.allocation["startedEpochNs"] / NS)
        require(time.time_ns() < POLICY_EXPIRES * NS and left(context.job_end, "EXPORT") > EXPORT_SECONDS + UPLOAD_SECONDS,
                "POLICY", "TIMEOUT")
        require(private_directory(context.recipient.work_dir) == context.recipient_work and
                private_directory(context.recipient.home) == context.recipient_home and
                {name: file_pin(context.recipient.work_dir / name, 64 * 1024, freeze_end)
                 for name in context.recipient_files} == context.recipient_files and
                file_pin(Path(context.gpg["path"]), 64 * 1024 * 1024, freeze_end,
                         owners=(0, os.getuid()), executable=True) == context.gpg, "POLICY", "IDENTITY_CHANGED")
        write_new(context.evidence / "suite-result.json", encoded(result))
        frozen = freeze_evidence(context.evidence, freeze_end)
    export_end = context.limit(EXPORT_SECONDS)
    with at_stage("EXPORT"):
        # The maintained direct GPG cleanup can take its bounded10s after a
        # timeout. Keep that tail inside this caller's ORIGINAL120s phase too.
        seconds = min(EXPORT_SECONDS, math.floor(left(export_end, "EXPORT") - 10))
        require(seconds > 0 and context.output is not None and not context.output.closed, "EXPORT", "TIMEOUT")
        context.export_called = True  # Sticky even if an export or cleanup raises.
        manifest = context.exporter.export_encrypted(context.evidence, context.parent / "outputs" / "encrypted",
                    context.recipient_original, source_commit=context.github["source"], source_tree=context.github["sourceTree"],
                    run_id=context.github["runId"], run_attempt=context.github["runAttempt"],
                    max_bytes=EVIDENCE_BYTES, max_members=EVIDENCE_MEMBERS, timeout_seconds=seconds)
        # This line is reached only after the ORIGINAL public call, including its
        # finally cleanup, returned. Output-file presence alone never reaches it.
        returned = time.monotonic_ns()
        left(export_end, "EXPORT")
        outputs = output_snapshot(context.parent, context.github, export_end, expected_manifest=manifest)
        seal = {"schema": 1, "scope": SCOPE, "outcome": outcome, "github": context.github, "source": context.source,
                "allocation": context.allocation, "operationIdentity": context.parent_identity,
                "account": context.account, "policySha256": POLICY_SHA256, "policyExpires": POLICY_EXPIRES,
                "exportReturnedMonotonicNs": returned, "stepStartedMonotonicNs": context.started,
                "stepEndMonotonicNs": context.step_end, "jobEndMonotonicNs": context.job_end,
                "uploadEndMonotonicNs": min(returned + UPLOAD_SECONDS * NS, context.job_end, context.policy_end),
                "encrypted": outputs, "evidenceSha256": digest(encoded(frozen))}
        write_new(context.parent / "export-return.json", encoded(seal))
        seal_hash = digest(encoded(seal))
        output = context.output.emit({"outcome": outcome,
                                      "successSha256" if outcome == "SUCCESS" else "closedFailureSha256": seal_hash})
        # Also require original command-file close BEFORE publishing this later
        # gate. A CLOSED_FAILURE followed by output-close error must not borrow
        # the same Step.failure label to authorize an artifact.
        step_return = {"schema": 1, "scope": SCOPE, "sealSha256": seal_hash, "commandFile": output,
                       "outputCloseReturned": True, "intendedExitCode": 0 if outcome == "SUCCESS" else 1,
                       "returnedMonotonicNs": time.monotonic_ns()}
        left(context.step_end, "EXPORT")
        write_new(context.parent / "step-return.json", encoded(step_return))
    return seal


SEAL_KEYS = frozenset(("schema", "scope", "outcome", "github", "source", "allocation", "operationIdentity", "account",
                       "policySha256", "policyExpires", "exportReturnedMonotonicNs", "stepStartedMonotonicNs",
                       "stepEndMonotonicNs", "jobEndMonotonicNs", "uploadEndMonotonicNs", "encrypted", "evidenceSha256"))


def validate_seal(seal, github, allocation, identity, now_ns):
    require(type(seal) is dict and set(seal) == SEAL_KEYS and type(seal["schema"]) is int and seal["schema"] == 1 and
            seal["scope"] == SCOPE and seal["outcome"] in ("SUCCESS", "CLOSED_FAILURE") and seal["github"] == github and
            seal["allocation"] == allocation and seal["operationIdentity"] == identity and
            seal["policySha256"] == POLICY_SHA256 and type(seal["policyExpires"]) is int and seal["policyExpires"] == POLICY_EXPIRES and
            type(seal["evidenceSha256"]) is str and HASH.fullmatch(seal["evidenceSha256"]), "UPLOAD", "IDENTITY_CHANGED")
    names = ("exportReturnedMonotonicNs", "stepStartedMonotonicNs", "stepEndMonotonicNs", "jobEndMonotonicNs", "uploadEndMonotonicNs")
    require(all(type(seal[name]) is int and seal[name] > 0 for name in names) and type(now_ns) is int and
            allocation["startedMonotonicNs"] <= seal["stepStartedMonotonicNs"] <= seal["exportReturnedMonotonicNs"] <
            seal["stepEndMonotonicNs"] <= seal["stepStartedMonotonicNs"] + STEP_SECONDS * NS and
            seal["jobEndMonotonicNs"] == allocation["startedMonotonicNs"] + JOB_SECONDS * NS and
            seal["exportReturnedMonotonicNs"] <= now_ns < seal["uploadEndMonotonicNs"] <=
            min(seal["exportReturnedMonotonicNs"] + UPLOAD_SECONDS * NS, seal["jobEndMonotonicNs"]),
            "UPLOAD", "TIMEOUT")
    return seal


def validate_artifact_return(env, expected_seal):
    require(env.get("P2PKIT_CONTEXT_UPLOAD_ALLOWED") == expected_seal and
            env.get("P2PKIT_CONTEXT_UPLOAD_OUTCOME") == "success" and
            type(env.get("P2PKIT_CONTEXT_ARTIFACT_ID")) is str and NUMBER.fullmatch(env["P2PKIT_CONTEXT_ARTIFACT_ID"]) and
            type(env.get("P2PKIT_CONTEXT_ARTIFACT_DIGEST")) is str and HASH.fullmatch(env["P2PKIT_CONTEXT_ARTIFACT_DIGEST"]),
            "UPLOAD", "UPLOAD_FAILED")
    return {"artifactId": env["P2PKIT_CONTEXT_ARTIFACT_ID"], "artifactDigest": env["P2PKIT_CONTEXT_ARTIFACT_DIGEST"]}


def upload_guard(*, after=False):
    """Read original post-return bindings; never validate a new Recipient/export."""
    with at_stage("UPLOAD"):
        env, started = dict(os.environ), time.monotonic_ns()
        request, github = original_request(env)
        parent, identity = operation_paths(env)
        allocation = parsed(read_file(parent / "allocation.json"))
        job_end = validate_allocation(allocation, request, github, started, time.time_ns())
        raw = read_file(parent / "export-return.json")
        seal = parsed(raw, STREAM_BYTES)
        require(raw == encoded(seal), "UPLOAD", "IDENTITY_CHANGED")
        validate_seal(seal, github, allocation, identity, started)
        seal_hash = validate_upload_binding(seal, env)
        end = min(started + 60 * NS, job_end, seal["uploadEndMonotonicNs"],
                  started + POLICY_EXPIRES * NS - time.time_ns())
        require(account() == seal["account"] and
                source_snapshot(end, child_environment(parent)) == seal["source"], "SOURCE", "IDENTITY_CHANGED",
                source_site="UPLOAD_SOURCE")
        # Byte/policy-window checks only. NO second public-key validation, new
        # Recipient, exporter call, worker key access, tail archive or upload.
        validate_policy(read_file(ROOT / POLICY_PATH, 96 * 1024), allocation["startedEpochNs"] / NS)
        step = parsed(read_file(parent / "step-return.json"), STREAM_BYTES)
        require(type(step) is dict and set(step) == {"schema", "scope", "sealSha256", "commandFile", "outputCloseReturned",
                "intendedExitCode", "returnedMonotonicNs"} and type(step["schema"]) is int and step["schema"] == 1 and
                step["scope"] == SCOPE and step["sealSha256"] == seal_hash and step["outputCloseReturned"] is True and
                type(step["intendedExitCode"]) is int and step["intendedExitCode"] == (0 if seal["outcome"] == "SUCCESS" else 1) and
                type(step["returnedMonotonicNs"]) is int and seal["exportReturnedMonotonicNs"] <=
                step["returnedMonotonicNs"] < seal["stepEndMonotonicNs"], "UPLOAD", "IDENTITY_CHANGED")
        command = step["commandFile"]
        require(type(command) is dict and set(command) == {"path", "stat", "sha256", "closed"} and command["closed"] is True and
                type(command["sha256"]) is str and HASH.fullmatch(command["sha256"]) and
                type(command["path"]) is str and type(command["stat"]) is list and len(command["stat"]) == 9,
                "UPLOAD", "IDENTITY_CHANGED")
        original_output = {"outcome": seal["outcome"],
                           "successSha256" if seal["outcome"] == "SUCCESS" else "closedFailureSha256": seal_hash}
        output_raw = "".join(key + "=" + value + "\n" for key, value in original_output.items()).encode("ascii")
        require(command["sha256"] == digest(output_raw) and command["stat"][6] == len(output_raw),
                "UPLOAD", "IDENTITY_CHANGED")
        require(output_snapshot(parent, github, end) == seal["encrypted"], "UPLOAD", "IDENTITY_CHANGED")
        if not after:
            output = CommandFile(env)
            try:
                returned = output.emit({"uploadAllowed": seal_hash})
            finally:
                output.close()
            write_new(parent / "before-upload.json", encoded({"schema": 1, "scope": SCOPE, "sealSha256": seal_hash,
                      "encryptedSha256": digest(encoded(seal["encrypted"])), "commandFile": returned,
                      "returnedMonotonicNs": time.monotonic_ns(), "outsideCiphertext": True}))
        else:
            before = parsed(read_file(parent / "before-upload.json"), STREAM_BYTES)
            require(type(before) is dict and set(before) == {"schema", "scope", "sealSha256", "encryptedSha256", "commandFile",
                    "returnedMonotonicNs", "outsideCiphertext"} and type(before["schema"]) is int and before["schema"] == 1 and
                    before["scope"] == SCOPE and before["sealSha256"] == seal_hash and before["outsideCiphertext"] is True and
                    before["encryptedSha256"] == digest(encoded(seal["encrypted"])) and
                    type(before["returnedMonotonicNs"]) is int and step["returnedMonotonicNs"] <=
                    before["returnedMonotonicNs"] <= started, "UPLOAD", "IDENTITY_CHANGED")
            artifact = validate_artifact_return(env, seal_hash)
            # These are the original upload action's returned labels. Root still
            # must read back actual GitHub run/artifact metadata and original
            # ciphertext; a syntactically numeric id is not remote attestation.
            write_new(parent / "after-upload.json", encoded({"schema": 1, "scope": SCOPE, "sealSha256": seal_hash,
                      "artifact": artifact, "github": github, "retentionDays": 14, "outsideCiphertext": True,
                      "remoteReadbackRequired": True, "returnedMonotonicNs": time.monotonic_ns()}))
        left(end, "UPLOAD")
    return 0


def experiment():
    context = prepare()
    try:
        result = run_cases(context)
        seal = finish_export(context, result)
        if seal["outcome"] == "CLOSED_FAILURE":
            value = context.case_results[0]["probe"]
            print(public_error(ExperimentError("NATIVE_SEND", "RETURN_FAILED", value["errno"])))
            return 1
        print("P2PKIT_CONTEXT_EXPERIMENT_SUCCESS")
        return 0
    finally:
        if context.output is not None:
            context.output.close()


def main():
    os.umask(0o077)
    try:
        require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, "PREPARE", "REFUSED")
        if len(sys.argv) == 2 and sys.argv[1] == "experiment":
            with at_stage("PREPARE"):
                return experiment()
        if len(sys.argv) == 2 and sys.argv[1] in ("before-upload", "after-upload"):
            return upload_guard(after=sys.argv[1] == "after-upload")
        if len(sys.argv) == 3 and sys.argv[1] == "_service":
            with at_stage("IDENTITY"):
                return service(sys.argv[2])
        if len(sys.argv) == 3 and sys.argv[1] == "_probe":
            require(re.fullmatch(r"[1-9][0-9]{0,3}", sys.argv[2]), "IDENTITY", "REFUSED")
            with at_stage("NATIVE_SEND"):
                return producer(int(sys.argv[2]))
        raise ExperimentError("PREPARE", "REFUSED")
    except BaseException as error:
        print(public_error(error))
        diagnostic = public_source_site(error)
        if diagnostic is not None:
            print(diagnostic)
        admin_diagnostic = public_admin_site(error)
        if admin_diagnostic is not None:
            print(admin_diagnostic)
        return 2  # No qualifying exclusive outcome/seal tuple on this route.


if __name__ == "__main__":
    raise SystemExit(main())
