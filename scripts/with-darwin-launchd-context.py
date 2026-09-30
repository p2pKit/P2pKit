#!/usr/bin/env python3
"""Disposable NONROOT system launchd context, before unchanged native admission.

TN3179 explicitly distinguishes automatically allowed launchd daemons from GUI
agents. Bootstrap ONE nonpersistent, fixed-command job as the invoking account;
never execute an observer, build or product as root. No TCC/SIP, permissions,
routes, firewall, authentication, global plist or installed service is changed.
This experiment is not an application-permission or physical-LAN qualification.
"""
from __future__ import annotations

import argparse
import grp
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import pwd
import re
import stat
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
REF = "refs/heads/work/rpc-lan-20260927-054728-8b1b11da"
SCOPE = "DISPOSABLE_NONROOT_LAUNCHD_CONTEXT_NOT_APP_PERMISSION_OR_PHYSICAL_LAN"
LIMIT = 128 * 1024
ENVIRONMENT = frozenset((
    "PATH", "LANG", "LC_ALL", "TMPDIR", "JAVA_HOME", "P2PKIT_AUDIT_JDK21", "ANDROID_HOME", "ANDROID_SDK_ROOT",
    "DEVELOPER_DIR", "GITHUB_ACTIONS", "RUNNER_ENVIRONMENT", "GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_EVENT_NAME",
    "GITHUB_SHA", "GITHUB_WORKSPACE", "RUNNER_TEMP", "RPC_QUALIFICATION_PARENT", "RPC_QUALIFY_REQUESTED",
    "RPC_ADMISSION_ONLY", "RPC_APPLE_LAUNCHD_CONTEXT",
))
FLAGS = frozenset(("nonrootChild", "unrecoverableRootInChild", "launchdParent", "exactCommandFinished",
                   "jobStopped", "jobRemoved", "plistRemoved", "sourceUnchanged"))
STAGES = ("SETUP", "BOOTSTRAP", "CHILD", "STOPPED", "REMOVED", "FINALIZED")
CHECK_CATEGORIES = ("GROUP_POLICY", "SOURCE", "NONROOT", "JOB_STATE", "PRIVATE_FILE", "CONFIGURATION")


class ContextFailure(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise ContextFailure(message)


def check_category(message):
    # Only our fixed check messages enter this function. Export labels, not text.
    text = message.lower()
    return ("GROUP_POLICY" if "group" in text or "account policy" in text else
            "SOURCE" if "source" in text else "NONROOT" if "nonroot" in text or "root" in text else
            "JOB_STATE" if "job" in text or "child" in text or "bootstrap" in text else
            "PRIVATE_FILE" if any(v in text for v in ("private", "file", "directory", "symlink")) else "CONFIGURATION")


def physical(path):
    need(path.is_absolute() and path == Path(os.path.normpath(path)) and
         not any(ord(c) < 32 for c in str(path)), "Canonical physical path required")
    for item in (path, *path.parents):
        need(not item.is_symlink(), "Symlinked context path refused")


def private_parent(path, uid):
    physical(path)
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == uid and stat.S_IMODE(info.st_mode) == 0o700,
         "Private invoking-user directory required")


def write_new(path, data):
    need(type(data) is bytes and len(data) <= LIMIT, "Bounded bytes required")
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(data)


def write_json(path, value):
    write_new(path, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode())


def read_private(path, uid):
    physical(path)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == uid and stat.S_IMODE(info.st_mode) == 0o600,
         "Private file ownership required")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        actual = os.fstat(stream.fileno())
        need((actual.st_dev, actual.st_ino) == (info.st_dev, info.st_ino), "File identity changed")
        value = stream.read(LIMIT + 1)
    need(len(value) <= LIMIT, "File exceeds bound")
    return value


def read_json(path, uid=None):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "Duplicate configuration key")
            result[key] = value
        return result
    return json.loads(read_private(path, os.getuid() if uid is None else uid), object_pairs_hook=unique)


def source_snapshot():
    def git(*args):
        return subprocess.check_output(["/usr/bin/git", *args], cwd=ROOT, stderr=subprocess.PIPE, timeout=15).decode().strip()
    need(os.getuid() == os.geteuid() != 0, "No privileged source/product inspection")
    need(git("status", "--porcelain=v1") == "", "Immutable clean source required")
    return {"commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}")}


def environment_admit(env):
    need(platform.system() == "Darwin" and env.get("GITHUB_ACTIONS") == "true" and
         env.get("RUNNER_ENVIRONMENT") == "github-hosted" and env.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit" and
         env.get("GITHUB_REF") == REF and env.get("GITHUB_EVENT_NAME") == "push" and
         env.get("RPC_QUALIFY_REQUESTED") == env.get("RPC_APPLE_LAUNCHD_CONTEXT") == "true" and
         re.fullmatch("[0-9a-f]{40}", env.get("GITHUB_SHA", "")), "Explicit feature-only Apple context required")
    need(Path(env["GITHUB_WORKSPACE"]).resolve(strict=True) == ROOT, "Wrong source checkout")


def config_validate(config, uid, gid, directory):
    need(type(config) is dict and set(config) == {"uid", "gid", "groups", "source", "argv", "environment", "label"},
         "Unexpected launchd configuration")
    need(type(uid) is int and type(gid) is int and uid > 0 and gid > 0 and
         type(config["uid"]) is int and type(config["gid"]) is int and config["uid"] == uid and config["gid"] == gid,
         "Only invoking nonroot credentials admitted")
    account = pwd.getpwuid(uid)
    need(account.pw_gid == gid and config["groups"] == sorted(set(os.getgrouplist(account.pw_name, gid))) and
         all(type(g) is int and g >= 0 for g in config["groups"]), "Invoking account policy changed")
    need(type(config["label"]) is str and re.fullmatch(r"dev\.p2pkit\.rpc\.qualification\.[0-9a-f]{32}", config["label"]),
         "Only a unique ephemeral feature label admitted")
    env = config["environment"]
    need(type(env) is dict and set(env) <= ENVIRONMENT and "PATH" in env and
         all(type(v) is str and "\0" not in v for v in env.values()), "Unadmitted environment")
    environment_admit(env)
    parent = Path(env["RPC_QUALIFICATION_PARENT"])
    need(directory == parent / "launchd-context" and parent.is_relative_to(Path(env["RUNNER_TEMP"]).resolve(strict=True)),
         "Task-local context required")
    private_parent(parent, uid)
    private_parent(directory, uid)
    python = str(Path(sys.executable).resolve())
    prefix = [python, str(ROOT / "scripts/with-darwin-audit-session.py"), "--parent", str(parent), "--", python,
              str(ROOT / "scripts/run-rpc-qualification.py"), "run", "--lane"]
    argv = config["argv"]
    need(type(argv) is list and argv[:9] == prefix and len(argv) in (10, 11, 12) and
         argv[9] in ("apple-x64", "apple-arm64") and
         (argv[10:] in ([], ["--admission-only"]) or argv[9] == "apple-x64" and argv[10:] in
          (["--intel-investigation", "network"], ["--intel-investigation", "native"],
           ["--intel-investigation", "cold-boot"])), "Only unchanged native qualification command admitted")
    source = config["source"]
    need(type(source) is dict and set(source) == {"commit", "tree"} and all(type(v) is str and
         re.fullmatch("[0-9a-f]{40}", v) for v in source.values()) and source["commit"] == env["GITHUB_SHA"],
         "Exact source binding required")


def job_plist(config, directory):
    account = pwd.getpwuid(config["uid"])
    return {"Label": config["label"], "UserName": account.pw_name, "GroupName": grp.getgrgid(config["gid"]).gr_name,
            "InitGroups": True, "ProgramArguments": [str(Path(sys.executable).resolve()), "-I", "-S",
                str(Path(__file__).resolve()), "--child", str(directory / "config.json")],
            "WorkingDirectory": str(ROOT), "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            "ProcessType": "Background", "RunAtLoad": True, "KeepAlive": False,
            "StandardOutPath": str(directory / "child.stdout.log"),
            "StandardErrorPath": str(directory / "child.stderr.log")}


def job_status(raw):
    """Parse only state/exit, never export launchd's environment, paths or PIDs."""
    need(type(raw) is bytes and len(raw) <= LIMIT, "Bounded launchd state required")
    text = raw.decode()
    states = re.findall(r"(?m)^\s*state = ([a-z ]+)\s*$", text)
    pids = re.findall(r"(?m)^\s*pid = ([0-9]+)\s*$", text)
    exits = re.findall(r"(?m)^\s*last exit code = (-?[0-9]+)\s*$", text)
    need(len(states) == 1 and len(pids) <= 1 and len(exits) <= 1, "Ambiguous launchd state")
    code = int(exits[0]) if exits else None
    need(code is None or -255 <= code <= 255, "Invalid launchd exit")
    return states[0] == "not running" and not pids and code is not None, code


def launchctl(*args):
    return subprocess.run(["/bin/launchctl", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)


def setup(path, remove=False):
    """The only privileged function; never imports or launches product/observer code as root."""
    need(platform.system() == "Darwin" and os.getuid() == os.geteuid() == 0, "Darwin setup privilege required")
    uid, gid = int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"])
    config = read_json(path, uid)
    directory = path.parent
    need(path.name == "config.json", "Exact private config required")
    config_validate(config, uid, gid, directory)
    plist = directory / "job.plist"
    expected = plistlib.dumps(job_plist(config, directory))
    target = "system/" + config["label"]
    if remove:
        need(read_private(plist, 0) == expected, "Do not remove a changed/unowned system job")
        state = launchctl("print", target)
        finished = read_json(directory / "child-result.json", uid)
        need(state.returncode == 0 and finished == {"source": config["source"], "exitCode": finished.get("exitCode")} and
             type(finished["exitCode"]) is int and job_status(state.stdout) == (True, finished["exitCode"]),
             "Never bootout a running or unfinalized child")
        need(launchctl("bootout", target).returncode == 0, "Exact stopped job removal failed")
        need(launchctl("print", target).returncode == 113, "Exact job absence not verified")
        plist.unlink()
    else:
        need(launchctl("print", target).returncode == 113, "Fresh absent service label required")
        for name in ("child.stdout.log", "child.stderr.log"):
            need(read_private(directory / name, uid) == b"", "Fresh invoking-user log required")
        write_new(plist, expected)  # Fresh root-owned plist in task state, not /Library/LaunchDaemons.
        code = launchctl("bootstrap", "system", str(plist)).returncode
        print("LAUNCHD_BOOTSTRAP_EXIT=" + str(code), flush=True)
        need(code == 0, "Nonroot job bootstrap failed")
    return 0


def child(path):
    need(platform.system() == "Darwin" and os.getuid() == os.geteuid() != 0 and
         os.getgid() == os.getegid() != 0 and os.getppid() == 1, "Only native nonroot launchd child admitted")
    config = read_json(path)
    config_validate(config, os.getuid(), os.getgid(), path.parent)
    need(sorted(set(os.getgroups())) == config["groups"], "Nonroot supplementary group policy changed")
    need(source_snapshot() == config["source"], "Source changed before launchd child")
    try:
        os.setuid(0)
    except PermissionError:
        pass
    else:
        raise RuntimeError("Child retained recoverable root")
    write_json(path.parent / "child-admission.json", {"source": config["source"], "nonrootChild": True,
               "unrecoverableRootInChild": True, "launchdParent": True})
    account = pwd.getpwuid(os.getuid())
    env = {**config["environment"], "HOME": account.pw_dir, "USER": account.pw_name, "LOGNAME": account.pw_name,
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
    code = subprocess.call(config["argv"], cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
    need(source_snapshot() == config["source"], "Source changed during launchd child")
    write_json(path.parent / "child-result.json", {"source": config["source"], "exitCode": code})
    return code


def validate_proof(value, source, complete=True):
    need(type(value) is dict and set(value) == {"schema", "scope", "source", "exitCode", "stage", "logs", *FLAGS},
         "Incomplete launchd proof")
    need(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE and
         value["source"] == source and type(value["exitCode"]) is int and -255 <= value["exitCode"] <= 255 and
         value["stage"] in STAGES and all(type(value[k]) is bool for k in FLAGS), "Invalid launchd observation")
    need(type(value["logs"]) is dict and set(value["logs"]) <= {"child.stdout", "child.stderr"}, "Invalid log labels")
    for row in value["logs"].values():
        need(type(row) is dict and set(row) == {"bytes", "sha256", "failedChecks"} and type(row["bytes"]) is int and
             0 <= row["bytes"] <= LIMIT and type(row["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", row["sha256"]),
             "Invalid closed log hash/count")
        need(type(row["failedChecks"]) is list and row["failedChecks"] == sorted(set(row["failedChecks"])) and
             all(k in CHECK_CATEGORIES for k in row["failedChecks"]), "Unknown failed check label")
    if complete:
        need(all(value[k] for k in FLAGS) and value["stage"] == "FINALIZED" and 0 <= value["exitCode"] < 255,
             "launchd context not finalized")
    return value


def run(parent, lane, admission_only, investigation):
    need(os.getuid() == os.geteuid() != 0 and os.getgid() == os.getegid() != 0, "Nonroot controller required")
    environment_admit(os.environ)
    private_parent(parent, os.getuid())
    directory = parent / "launchd-context"
    directory.mkdir(mode=0o700)
    source = source_snapshot()
    python = str(Path(sys.executable).resolve())
    argv = [python, str(ROOT / "scripts/with-darwin-audit-session.py"), "--parent", str(parent), "--", python,
            str(ROOT / "scripts/run-rpc-qualification.py"), "run", "--lane", lane]
    if admission_only:
        argv.append("--admission-only")
    if investigation:
        argv += ["--intel-investigation", investigation]
    account = pwd.getpwuid(os.getuid())
    config = {"uid": os.getuid(), "gid": os.getgid(), "groups": sorted(set(os.getgrouplist(account.pw_name, os.getgid()))),
              "source": source, "argv": argv, "environment": {k: v for k, v in os.environ.items() if k in ENVIRONMENT},
              "label": "dev.p2pkit.rpc.qualification." + uuid.uuid4().hex}
    config_validate(config, os.getuid(), os.getgid(), directory)
    write_json(directory / "config.json", config)
    for name in ("child.stdout.log", "child.stderr.log"):
        write_new(directory / name, b"")
    proof = {"schema": 1, "scope": SCOPE, "source": source, "exitCode": 255, "stage": "SETUP", "logs": {},
             **dict.fromkeys(FLAGS, False)}
    helper = ["/usr/bin/sudo", "-n", python, "-I", "-S", str(Path(__file__).resolve())]
    try:
        subprocess.run([*helper, "--setup", str(directory / "config.json")], check=True, timeout=60)
        proof["stage"] = "BOOTSTRAP"
        deadline = time.monotonic() + (1800 if investigation == "network" else 325 * 60)
        while not (directory / "child-result.json").exists():
            need(time.monotonic() < deadline, "Unfinalized child; do not remove a running job")
            state = launchctl("print", "system/" + config["label"])
            need(state.returncode == 0, "Owned job disappeared before child result")
            stopped, code = job_status(state.stdout)
            need(not stopped, "Child stopped before exact result; no admission claim")
            time.sleep(2)
        proof["stage"] = "CHILD"
        admitted = read_json(directory / "child-admission.json")
        finished = read_json(directory / "child-result.json")
        need(admitted == {"source": source, "nonrootChild": True, "unrecoverableRootInChild": True, "launchdParent": True} and
             set(finished) == {"source", "exitCode"} and finished["source"] == source and
             type(finished["exitCode"]) is int and 0 <= finished["exitCode"] < 255, "Missing exact native child result")
        proof.update(nonrootChild=True, unrecoverableRootInChild=True, launchdParent=True,
                     exactCommandFinished=True, exitCode=finished["exitCode"])
        deadline = time.monotonic() + 30
        while True:
            state = launchctl("print", "system/" + config["label"])
            need(state.returncode == 0, "Owned job disappeared before finalization")
            if job_status(state.stdout) == (True, proof["exitCode"]):
                break
            need(time.monotonic() < deadline, "Exact launchd child did not exit")
            time.sleep(0.25)
        proof.update(jobStopped=True, stage="STOPPED")
        subprocess.run([*helper, "--remove", str(directory / "config.json")], check=True, timeout=90)
        proof.update(jobRemoved=True, plistRemoved=not (directory / "job.plist").exists(), stage="REMOVED")
    finally:
        proof["sourceUnchanged"] = source_snapshot() == source
        for label in ("child.stdout", "child.stderr"):
            raw = read_private(directory / (label + ".log"), os.getuid())
            proof["logs"][label] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "failedChecks":
                sorted({k for k in CHECK_CATEGORIES if ("CONTEXT_FAILURE " + k + "\n").encode() in raw})}
        if all(proof[k] for k in FLAGS):
            proof["stage"] = "FINALIZED"
        write_json(directory / "result.json", proof)
    validate_proof(proof, source)
    return proof["exitCode"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    for name in ("setup", "remove", "child"):
        operation.add_argument("--" + name, type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--parent", type=Path)
    parser.add_argument("--lane", choices=("apple-x64", "apple-arm64"))
    parser.add_argument("--admission-only", action="store_true")
    parser.add_argument("--intel-investigation", choices=("network", "native", "cold-boot"))
    args = parser.parse_args()
    path = args.setup or args.remove or args.child
    if path:
        need(args.parent is None and args.lane is None and not args.admission_only and args.intel_investigation is None,
             "Only fixed child/setup arguments admitted")
        return child(path) if args.child else setup(path, bool(args.remove))
    need(args.parent is not None and args.lane is not None, "Explicit task context required")
    return run(args.parent, args.lane, args.admission_only, args.intel_investigation)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if isinstance(error, ContextFailure):
            print("CONTEXT_FAILURE " + check_category(str(error)), file=sys.stderr)
        print("Disposable nonroot launchd context failed: " + type(error).__name__ + "; no admission claim", file=sys.stderr)
        raise SystemExit(125)
