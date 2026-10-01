#!/usr/bin/env python3
"""Opt-in Apple lab isolation, before (not instead of) native ownership admission.

Only the small bootstrap runs as root: allocate this process a fresh kernel audit
session, preserving its audit policy, then permanently return to the invoking
account. No census, signal, tool, test, or source import runs with privilege.
The normal, unchanged ownership executor must still admit and finalize the work.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import pwd
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
LIMIT = 128 * 1024
ENVIRONMENT = frozenset((
    "PATH", "LANG", "LC_ALL", "TMPDIR", "JAVA_HOME", "P2PKIT_AUDIT_JDK21", "ANDROID_HOME", "ANDROID_SDK_ROOT",
    "DEVELOPER_DIR", "GITHUB_ACTIONS", "RUNNER_ENVIRONMENT", "GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_EVENT_NAME",
    "GITHUB_SHA", "GITHUB_WORKSPACE", "RUNNER_TEMP", "RPC_QUALIFICATION_PARENT", "RPC_QUALIFY_REQUESTED",
    "RPC_ADMISSION_ONLY", "RPC_APPLE_SSH_CONTEXT", "RPC_APPLE_LAUNCHD_CONTEXT", "RPC_APPLE_TERMINAL_CONTEXT",
    "RPC_APPLE_BONJOUR_ADVERTISING", "RPC_INTEL_INVESTIGATION", "RPC_APPLE_LANE",
))


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


class AuditInfo(ctypes.Structure):
    # SDK bsm/audit.h auditinfo_addr_t, identical on the supported native x64/ARM64 ABIs.
    _fields_ = [("auid", ctypes.c_uint32), ("success", ctypes.c_uint32), ("failure", ctypes.c_uint32),
                ("port", ctypes.c_int32), ("type", ctypes.c_uint32), ("address", ctypes.c_uint32 * 4),
                ("asid", ctypes.c_int32), ("flags", ctypes.c_uint64)]


def validate(config, uid, gid):
    need(type(config) is dict and set(config) == {"uid", "gid", "cwd", "argv", "environment"}, "Invalid session config")
    need(type(uid) is int and type(gid) is int and uid > 0 and gid > 0 and
         type(config["uid"]) is int and type(config["gid"]) is int and
         config["uid"] == uid and config["gid"] == gid, "Only the invoking unprivileged account is admitted")
    need(type(config["cwd"]) is str and Path(config["cwd"]).is_absolute(), "Absolute working directory required")
    argv = config["argv"]
    need(type(argv) is list and 1 <= len(argv) <= 128 and all(type(value) is str and "\0" not in value for value in argv)
         and Path(argv[0]).is_absolute(), "Bounded explicit command required")
    env = config["environment"]
    need(type(env) is dict and set(env) <= ENVIRONMENT and "PATH" in env and
         all(type(value) is str and "\0" not in value for value in env.values()), "Unadmitted environment input")
    need("\0" not in config["cwd"], "Invalid working directory")


def physical(path):
    need(path.is_absolute() and path == Path(os.path.normpath(path)), "Absolute normalized path required")
    for item in (path, *path.parents):
        need(not item.is_symlink(), "Symlinked session path refused")


def read_config(path, uid):
    physical(path)
    info, parent = path.lstat(), path.parent.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == uid and stat.S_IMODE(info.st_mode) == 0o600 and
         stat.S_ISDIR(parent.st_mode) and parent.st_uid == uid and stat.S_IMODE(parent.st_mode) == 0o700,
         "Session config must be privately owned by the invoker")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        actual = os.fstat(stream.fileno())
        need((actual.st_dev, actual.st_ino) == (info.st_dev, info.st_ino), "Session config changed identity")
        raw = stream.read(LIMIT + 1)
    need(0 < len(raw) <= LIMIT, "Session config exceeds its bound")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "Duplicate session config key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def new_session(system):
    need(ctypes.sizeof(AuditInfo) == 48, "Unsupported auditinfo_addr_t ABI")
    for name in ("getaudit_addr", "setaudit_addr"):
        function = getattr(system, name)
        function.argtypes = [ctypes.POINTER(AuditInfo), ctypes.c_int]
        function.restype = ctypes.c_int
    before = AuditInfo()
    need(system.getaudit_addr(ctypes.byref(before), 48) == 0, "Cannot read the bootstrap's audit policy")
    requested = AuditInfo.from_buffer_copy(bytes(before))
    requested.asid = -1  # AU_ASSIGN_ASID: allocate, never join a caller-selected session.
    need(system.setaudit_addr(ctypes.byref(requested), 48) == 0, "Cannot allocate a private audit session")
    after = AuditInfo()
    need(system.getaudit_addr(ctypes.byref(after), 48) == 0, "Cannot verify the allocated audit session")
    need(after.asid not in (0, -1, before.asid), "A fresh assigned session is required")
    compared = AuditInfo.from_buffer_copy(bytes(after))
    compared.asid = before.asid
    # Check while still root. Darwin deliberately redacts masks to all-ones for
    # ordinary callers; comparing a post-drop masked read would be a false failure.
    need(bytes(compared) == bytes(before), "Audit policy changed during session allocation")
    return after.asid, before.asid not in (0, -1)


def drop_privileges(uid, gid, account):
    groups = set(os.getgrouplist(account, gid))
    os.initgroups(account, gid)
    os.setgid(gid)
    os.setuid(uid)  # As root this sets real, effective AND saved IDs on Darwin.
    need(os.getuid() == os.geteuid() == uid and os.getgid() == os.getegid() == gid and
         set(os.getgroups()) == groups, "Invoking credentials were not fully restored")
    try:
        os.setuid(0)
    except PermissionError:
        return
    raise RuntimeError("Bootstrap retained recoverable root authority")


def write_new(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def bootstrap(path):
    need(platform.system() == "Darwin" and os.getuid() == os.geteuid() == 0, "Darwin setup privilege required")
    uid, gid = int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])
    config = read_config(path, uid)
    validate(config, uid, gid)
    account = pwd.getpwuid(uid)
    need(account.pw_gid == gid, "Unexpected invoking primary group")
    system = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    asid, previous_assigned = new_session(system)
    drop_privileges(uid, gid, account.pw_name)
    # Everything below is unprivileged, including ALL evidence writes and exec.
    observed = AuditInfo()
    need(system.getaudit_addr(ctypes.byref(observed), 48) == 0 and observed.asid == asid,
         "Private audit session did not survive credential drop")
    env = {**config["environment"], "HOME": account.pw_dir, "USER": account.pw_name, "LOGNAME": account.pw_name,
           "SECURITYSESSIONID": format(asid, "x"), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
    os.chdir(config["cwd"])
    write_new(path.parent / "session-admission.json", {
        "schema": 1, "scope": "PROCESS_LOCAL_AUDIT_SESSION_NOT_OWNERSHIP_OR_PRODUCT_ADMISSION",
        "previousSessionAssigned": previous_assigned, "freshAssignedSession": True,
        "auditPolicyPreserved": True, "invokingCredentialsRestored": True, "rootCannotBeRegained": True,
        "privilegedObservationOrProductExecution": False,
    })
    os.execvpe(config["argv"][0], config["argv"], env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--parent", type=Path)
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.bootstrap:
        need(args.parent is None and not args.argv, "Invalid bootstrap arguments")
        bootstrap(args.bootstrap)
        return 125
    need(platform.system() == "Darwin" and os.getuid() == os.geteuid() != 0,
         "Invoke from the unprivileged Apple lab account")
    need(args.parent is not None and args.argv and args.argv[0] == "--", "Explicit private parent and command required")
    physical(args.parent)
    parent = args.parent.lstat()
    need(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and stat.S_IMODE(parent.st_mode) == 0o700,
         "Private parent is not owned")
    argv = args.argv[1:]
    need(argv and shutil.which(argv[0]) is not None, "Command executable is unavailable")
    argv[0] = str(Path(shutil.which(argv[0])).absolute())
    config = {"uid": os.getuid(), "gid": os.getgid(), "cwd": os.getcwd(), "argv": argv,
              "environment": {key: value for key, value in os.environ.items() if key in ENVIRONMENT}}
    validate(config, os.getuid(), os.getgid())
    need(len(json.dumps(config).encode()) <= LIMIT, "Session config exceeds its bound")
    path = args.parent / "session-config.json"
    write_new(path, config)
    # -I -S excludes caller Python paths/site hooks while the small bootstrap has privilege.
    return subprocess.call(["/usr/bin/sudo", "-n", str(Path(sys.executable).absolute()), "-I", "-S",
                            str(Path(__file__).resolve()), "--bootstrap", str(path)])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("Private Apple audit-session setup failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(125)
