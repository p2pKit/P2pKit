#!/usr/bin/env python3
"""Closed ordinary full/Desktop custody; inert until separately reviewed CI wiring.

No policy bootstrap, installer, arbitrary command, publication or local-host
fallback exists. All children use the maintained native owner and private supplied
sinks. The canonical immutable executor remains the product/stop authority.
Encrypted failed-test retention is not a pass. A separate post-return process
must seal the exact ciphertext, then CI must require its profile_passed output.
"""
from __future__ import annotations

import argparse
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

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import audit_processes as processes
import hosted_full_job_budget as job_time
import hosted_evidence as posix
import hosted_test_evidence as ordinary
import hosted_test_identity as identity
import hosted_test_query as query
import hosted_windows_evidence as windows
import hosted_windows_files as files

SPEC = importlib.util.spec_from_file_location("ordinary_canonical_audit", SCRIPTS / "run-audit-command.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

MIB = 1024 * 1024
RECORD_LIMIT, OUTPUT_LIMIT = 4 * MIB, 64 * MIB
FINAL_SECONDS = 45
QUARANTINE = []
DESKTOP_TASKS = (
    ":p2p-sample-desktop:check", ":p2p-sample-desktop:installDist", ":p2p-sample-desktop-ui:test",
    ":p2p-sample-desktop-ui:checkRuntime", ":p2p-sample-desktop-ui:hotRunArgfile",
    ":p2p-sample-desktop-ui:createDistributable",
)
INSTALLERS = {"linux-x64": ":p2p-sample-desktop-ui:packageDeb",
              "windows-x64": ":p2p-sample-desktop-ui:packageMsi",
              "macos-arm64": ":p2p-sample-desktop-ui:packageDmg",
              "macos-x64": ":p2p-sample-desktop-ui:packageDmg"}
# This is deliberately NOT the old whole-job 30-minute allowance. A Windows
# NativeFile's original lifetime cannot exceed 900s. Keep the product + canonical
# stop + outer retirement/receipt envelope below it; a timeout remains a failure.
PRODUCT_SECONDS = {"full": 7200, "desktop": 600}
OUTER_SECONDS = {"full": 7530, "desktop": 825}
TOTAL_SECONDS = {"full": 8400, "desktop": 1500}
IDENTITY_ENV = (
    "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_REF", "GITHUB_RUN_ID",
    "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA",
    "GITHUB_WORKSPACE", "GITHUB_EVENT_PATH", "GITHUB_SERVER_URL", "GITHUB_API_URL", "GITHUB_JOB",
    "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME", "RUNNER_ENVIRONMENT", "RUNNER_TEMP", "ImageOS", "ImageVersion",
)

# Only these two exact, source-bound siblings enter the isolated canonical
# interpreter. Do not restore the script directory or ambient PYTHONPATH: the
# canonical supplier imports audit_processes without adding its own directory.
CANONICAL_NAMES = ("audit_processes.py", "run-audit-command.py")
CANONICAL_SOURCE_LIMIT = 512 * 1024
CANONICAL_BOOTSTRAP = '''import hashlib, json, os, stat, sys, types
from pathlib import Path
def require(value):
    if not value:
        raise RuntimeError("CANONICAL_BOOTSTRAP_REFUSED")
require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode)
require(len(sys.argv) >= 4 and "audit_processes" not in sys.modules)
directory = Path(sys.argv[1])
require(directory.is_absolute() and ".." not in directory.parts and directory.name == "scripts")
for path in (directory, *directory.parents):
    info = path.lstat()
    require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400)
bindings = json.loads(sys.argv[2])
names = ("audit_processes.py", "run-audit-command.py")
require(type(bindings) is dict and set(bindings) == set(names))
source = {}
for name in names:
    path = directory / name
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            not getattr(before, "st_file_attributes", 0) & 0x400 and 0 < before.st_size <= 512 * 1024)
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require(os.path.samestat(before, opened))
        raw = stream.read(512 * 1024 + 1)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    require(os.path.samestat(before, after) and os.path.samestat(before, current) and
            before.st_mtime_ns == after.st_mtime_ns == current.st_mtime_ns and
            before.st_size == after.st_size == current.st_size == len(raw) and
            type(bindings[name]) is str and hashlib.sha256(raw).hexdigest() == bindings[name])
    source[name] = compile(raw, str(path), "exec", dont_inherit=True)
# Execute precisely the admitted bytes, not a second path read after hashing.
# Preloading this closed sibling preserves -I without changing sys.path.
module = types.ModuleType("audit_processes")
module.__file__, module.__package__, module.__spec__ = str(directory / names[0]), None, None
sys.modules["audit_processes"] = module
exec(source[names[0]], module.__dict__)
sys.argv = [str(directory / names[1]), *sys.argv[3:]]
main = types.ModuleType("__main__")
main.__file__, main.__package__, main.__spec__, main.__cached__ = sys.argv[0], None, None, None
sys.modules["__main__"] = main
exec(source[names[1]], main.__dict__)
'''


class ControllerError(RuntimeError):
    """Finite public-safe reason; original errors/paths stay in private evidence."""


def require(value, code):
    if not value:
        raise ControllerError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    require(len(raw) <= RECORD_LIMIT, "CONTROLLER_RECORD_LIMIT")
    return raw


def parse(raw):
    return identity.parse(raw, RECORD_LIMIT)


def canonical_bindings():
    """Capture only canonical suppliers after exact ordinary source admission."""
    result = {}
    for name in CANONICAL_NAMES:
        path = SCRIPTS / name
        audit.reject_symlinks(path)
        result[name] = audit.file_digest(path, CANONICAL_SOURCE_LIMIT)
    return result


def canonical_python(executable, bindings, *args):
    require(type(bindings) is dict and set(bindings) == set(CANONICAL_NAMES) and
            all(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) for value in bindings.values()),
            "CANONICAL_SOURCE_BINDINGS")
    return [executable, "-I", "-B", "-S", "-c", CANONICAL_BOOTSTRAP, str(SCRIPTS),
            encoded(bindings).decode("ascii").strip(), *map(str, args)]


def profile_command(profile, role):
    require(profile in PRODUCT_SECONDS and role in INSTALLERS, "CONTROLLER_PROFILE")
    if profile == "full":
        require(role.startswith("macos-"), "FULL_REQUIRES_NATIVE_MAC")
        return "command", ["python3", "scripts/run-platform-tests.py", "full"]
    tasks = list(DESKTOP_TASKS)
    if role == "linux-x64":
        tasks.append(":p2p-sample-android:assembleDebug")
    return "gradle", [*tasks, INSTALLERS[role], "--console=plain"]


def session_path(profile, role):
    require(profile in PRODUCT_SECONDS and role in INSTALLERS, "CONTROLLER_PROFILE")
    run, attempt = os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_RUN_ATTEMPT")
    require(type(run) is str and identity.ID.fullmatch(run) and type(attempt) is str and
            identity.ID.fullmatch(attempt), "CONTROLLER_RUN_ID")
    parent = Path(os.environ.get("RUNNER_TEMP", ""))
    audit.reject_symlinks(parent)
    require(parent.is_absolute() and parent.is_dir() and ".." not in parent.parts and
            parent != ROOT and parent not in ROOT.parents and ROOT not in parent.parents,
            "CONTROLLER_PRIVATE_PARENT")
    return parent / ("p2pkit-test-" + profile + "-" + run + "-" + attempt + "-" + role)


def child_environment(base, session, state):
    """Drop credentials, not conflicting execution policy; never impersonate CI."""
    blocked = {"JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS",
               "BASH_ENV", "ENV", "ZDOTDIR", "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT",
               "KONAN_HOME", "KOTLIN_HOME", "KOTLIN_OPTS", "KONAN_OPTS", "KONAN_JVM_ARGS",
               "KOTLIN_NATIVE_HOME", "SDKROOT", "TOOLCHAINS", "XCODE_XCCONFIG_FILE"}
    for name, value in base.items():
        require(not (value and (name in blocked or name.startswith(("DYLD_", "LD_", "BASH_FUNC_",
                                                                  "ORG_GRADLE_PROJECT_")))),
                "AMBIENT_EXECUTION_OVERRIDE")
        require(not name.startswith("GIT_") or name == "GIT_TERMINAL_PROMPT", "AMBIENT_GIT_OVERRIDE")
    context = query._inherited_context()  # Validate, do not erase a genuine existing ancestor.
    allowed = {*IDENTITY_ENV, "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
               "APPDATA", "LOCALAPPDATA", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "DEVELOPER_DIR",
               "JAVA_HOME", "P2PKIT_AUDIT_JDK21", "ANDROID_HOME", "LANG", "LC_ALL"}
    result = {name: value for name, value in base.items() if name in allowed}
    result.update(context)
    require(result.get("JAVA_HOME") and result.get("P2PKIT_AUDIT_JDK21"), "TWO_EXPLICIT_JDK_HOMES_REQUIRED")
    result.update(CI="true", GIT_TERMINAL_PROMPT="0", PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
                  TMPDIR=str(session / "temporary"), TEMP=str(session / "temporary"), TMP=str(session / "temporary"),
                  KONAN_DATA_DIR=str(state / "konan"), ANDROID_USER_HOME=str(state / "android-user"),
                  P2PKIT_GRADLE_EXECUTOR=str(SCRIPTS / "run-audit-command.py"))
    # Leave the real ordinary HOME for CoreSimulator. This is credential
    # non-inheritance, not a sandbox against same-user source.
    return result


class PrivateOwner:
    """File/pin ownership around existing suppliers; never another process backend."""
    def __init__(self):
        self.resources, self.errors = [], []
        self.unknown = False
        self.original = None

    def error(self, stage, error, unknown=False):
        detail = windows._exception_detail(error)
        self.unknown |= unknown or detail["retirementUnknown"]
        if self.original is None:
            self.original = error
        if len(self.errors) < 64:
            self.errors.append({"stage": stage, "detail": detail})
        else:
            self.unknown = True

    def hold(self, label, owner):
        require(not any(row["owner"] is owner for row in self.resources), "DUPLICATE_RESOURCE_OWNER")
        self.resources.append({"label": label, "owner": owner, "attempted": False, "closed": False})
        return owner

    def acquire(self, label, factory):
        try:
            return self.hold(label, factory())
        except BaseException as error:
            self.error(label + "-allocation", error, unknown=True)
            raise

    def close_one(self, owner):
        row = next(row for row in self.resources if row["owner"] is owner)
        if row["attempted"]:
            return
        row["attempted"] = True
        try:
            owner.close()
            row["closed"] = True
        except BaseException as error:
            self.error(row["label"] + "-close", error, unknown=True)

    def close(self):
        if not self.unknown:
            for row in reversed(self.resources):
                if self.unknown:
                    break
                self.close_one(row["owner"])
        if self.unknown:
            if not any(value is self for value in QUARANTINE):
                QUARANTINE.append(self)
            raise ControllerError("CONTROLLER_RESOURCE_RETIREMENT_UNKNOWN")

    def new(self, path):
        return self.acquire("private-directory", lambda: query._new_private_directory(Path(path)))

    def open(self, path):
        return self.acquire("private-directory", lambda: files.open_private_directory(path) if os.name == "nt"
                            else query._PosixDirectory(Path(path)))

    def child(self, parent, name, end, create=False):
        if create:
            return self.acquire("private-child", lambda: parent.create_directory(name, deadline=end))
        if os.name == "nt":
            return self.acquire("private-child", lambda: parent.open_directory(name, deadline=end))
        parent.verify()
        query._component(name)
        return self.open(parent.path / name)

    def read(self, parent, name, end, maximum=RECORD_LIMIT):
        posix._deadline(end)
        try:
            raw = parent.read_bytes(name, max_bytes=maximum, deadline=end)
        except BaseException as error:
            # Opaque delegated reader may have failed its own descriptor close.
            self.error("private-reader", error, unknown=True)
            raise
        posix._deadline(end)
        return raw

    def write(self, parent, name, value, end):
        raw = value if type(value) is bytes else encoded(value)
        require(len(raw) <= RECORD_LIMIT, "CONTROLLER_RECORD_LIMIT")
        posix._deadline(end)
        stream = self.acquire(name, lambda: parent.create_file(name, max_bytes=max(1, len(raw)), deadline=end))
        original = None
        try:
            require(stream.write(raw) == len(raw), "CONTROLLER_SHORT_WRITE")
            stream.sync()
            require(stream.verify().size == len(raw), "CONTROLLER_RECORD_CHANGED")
        except BaseException as error:
            original = error
            self.error(name + "-write", error)
        finally:
            self.close_one(stream)
        if original is not None:
            raise original
        require(not self.unknown and self.read(parent, name, end, max(1, len(raw))) == raw,
                "CONTROLLER_RECORD_READBACK")


def admission(owner, profile, destination, check_cancel, expected=None):
    """Use ONLY the approved native query binding; own pre-enter cancellation."""
    supplier = None
    original = None
    result = None
    try:
        supplier = query.NativeGitQueries(ROOT, destination, check_cancel=check_cancel)
        check_cancel()
        supplier.native_host_matches_actions()
        result = identity.admit(profile, ROOT, query_runner=supplier, expected=expected)
        supplier.retain_admission(result)
        check_cancel()
    except BaseException as error:
        original = error
    finally:
        if supplier is not None:
            try:
                supplier._finalize(original)
            except BaseException as error:
                if original is None:
                    original = error
        if (supplier is not None and supplier.unknown) or query.QUARANTINE or windows._QUARANTINE:
            owner.error("native-query", original or ControllerError("QUERY_UNKNOWN"), unknown=True)
    if original is not None:
        raise original
    require(type(result) is identity.Admission, "MISSING_ORDINARY_ADMISSION")
    return result


def load_admission(owner, directory, end):
    record = owner.read(directory, "admission.json", end)
    event = owner.read(directory, "original-event.json", end)
    policy = owner.read(directory, "original-policy.json", end)
    key = owner.read(directory, "recipient-public.asc", end)
    value = parse(record)
    require(digest(event) == value["github"]["eventSha256"] and digest(policy) == value["policy"]["sha256"] and
            digest(key) == value["policy"]["keySha256"], "ORIGINAL_ADMISSION_BYTES_CHANGED")
    return identity.Admission(record, event, policy, key, value["policy"]["fingerprint"],
                              value["policy"]["keySha256"], value["policy"]["expiresAt"])


def copy_tree(owner, source, destination, end):
    """Flat, reversible private copy using original-path/size/SHA256 inventory.

    Query-private sinks intentionally accept only narrow lowercase components;
    do not widen that approved supplier to accommodate TEST-*.xml/buildSrc/etc.
    Fixed opaque member names preserve arbitrary admitted original names in a
    private path map. Original and destination snapshots and bytes are verified.
    No paths from that map are ever materialized by this controller.
    """
    target = owner.new(destination)
    snapshot = None
    copied = []
    try:
        source.verify()
        if os.name == "nt":
            snapshot = owner.acquire("copy-snapshot", lambda: source.snapshot(
                max_bytes=posix.MAX_BYTES, max_members=posix.MAX_MEMBERS, deadline=end))
            entries = snapshot.entries
            directories = sorted(name for name, value in entries.items() if value.is_directory)
            members = [(name, value.size) for name, value in entries.items() if not value.is_directory]
            opener = snapshot.open_file
        else:
            entries = posix_snapshot(owner, source.path, posix.MAX_BYTES, posix.MAX_MEMBERS, end)
            directories = sorted(name for name, value in entries.items() if stat.S_ISDIR(value[2]))
            members = [(name, value[5]) for name, value in entries.items() if stat.S_ISREG(value[2])]
            opener = lambda name: posix._open_member(source.path, name, entries)
        for index, (name, size) in enumerate(sorted(members)):
            posix._deadline(end)
            leaf = "member-" + str(index).zfill(5) + ".bin"
            reader = writer = None
            hashed = hashlib.sha256()
            try:
                reader = owner.acquire("copy-reader", lambda: opener(name))
                writer = owner.acquire("copy-writer", lambda: target.create_file(
                    leaf, max_bytes=max(size, 1), deadline=end))
                remaining = size
                while remaining:
                    posix._deadline(end)
                    raw = reader.read(min(MIB, remaining))
                    require(raw and len(raw) <= remaining and writer.write(raw) == len(raw), "COPY_SHORT_OR_CHANGED")
                    hashed.update(raw)
                    remaining -= len(raw)
                require(reader.read(1) == b"", "COPY_MEMBER_GREW")
                writer.sync()
                require(writer.verify().size == size, "COPY_SIZE_CHANGED")
            finally:
                for stream in (writer, reader):
                    if stream is not None:
                        owner.close_one(stream)
            require(not owner.unknown, "COPY_RETIREMENT_UNKNOWN")
            copied.append({"original": name, "member": leaf, "size": size, "sha256": hashed.hexdigest()})
        if snapshot is not None:
            snapshot.verify()
        else:
            require(posix_snapshot(owner, source.path, posix.MAX_BYTES, posix.MAX_MEMBERS, end) == entries,
                    "COPY_ORIGINAL_TREE_CHANGED")
        source.verify()
    finally:
        if snapshot is not None:
            owner.close_one(snapshot)
    require(not owner.unknown, "COPY_SNAPSHOT_CLOSE_UNKNOWN")
    # One destination snapshot; do not rescan an N-file tree twice per file.
    readback = None
    try:
        if os.name == "nt":
            readback = owner.acquire("copy-readback-snapshot", lambda: target.snapshot(
                max_bytes=posix.MAX_BYTES, max_members=posix.MAX_MEMBERS, deadline=end))
            opener = readback.open_file
        else:
            target_rows = posix_snapshot(owner, target.path, posix.MAX_BYTES, posix.MAX_MEMBERS, end)
            opener = lambda name: posix._open_member(target.path, name, target_rows)
        for row in copied:
            reader = owner.acquire("copy-readback", lambda: opener(row["member"]))
            try:
                require(hash_stream(reader, row["size"], end) == row["sha256"], "COPY_READBACK_DIFFERS")
            finally:
                owner.close_one(reader)
            require(not owner.unknown, "COPY_READBACK_RETIREMENT_UNKNOWN")
        if readback is not None:
            readback.verify()
        else:
            require(posix_snapshot(owner, target.path, posix.MAX_BYTES, posix.MAX_MEMBERS, end) == target_rows,
                    "COPY_READBACK_TREE_CHANGED")
    finally:
        if readback is not None:
            owner.close_one(readback)
    require(not owner.unknown, "COPY_READBACK_SNAPSHOT_UNKNOWN")
    owner.write(target, "original-path-map.json", {"schema": 1, "scope": "REVERSIBLE_PRIVATE_BYTE_COPY",
        "originalRoot": str(source.path), "directories": directories, "files": copied}, end)
    target.verify()
    return target


def posix_snapshot(owner, root, maximum, members, end):
    try:
        return posix._snapshot(root, maximum, members, end)
    except BaseException as error:
        # The delegated snapshot has native descriptors even when allocation
        # never returned. Do not infer clean close from a missing snapshot.
        owner.error("posix-snapshot", error, unknown=True)
        raise


def hash_stream(stream, size, end):
    hasher, total = hashlib.sha256(), 0
    while True:
        posix._deadline(end)
        block = stream.read(MIB)
        if not block:
            break
        total += len(block)
        require(total <= size, "HASH_MEMBER_GREW")
        hasher.update(block)
    require(total == size, "HASH_MEMBER_TRUNCATED")
    return hasher.hexdigest()


def hash_member(owner, root, name, end, *, maximum):
    """Existing native/path readers only; bounded streaming, including empty files."""
    stream = None
    try:
        if os.name == "nt":
            stream = owner.acquire("member-reader", lambda: root.open_file(name, max_bytes=maximum, deadline=end))
            size = stream.initial_info.size
        else:
            root.verify()
            rows = posix_snapshot(owner, root.path, posix.MAX_CIPHERTEXT_BYTES, posix.MAX_MEMBERS, end)
            require(name in rows and stat.S_ISREG(rows[name][2]), "HASH_MEMBER_MISSING")
            size = rows[name][5]
            stream = owner.acquire("member-reader", lambda: posix._open_member(root.path, name, rows))
        require(0 <= size <= maximum, "HASH_MEMBER_BOUND")
        hashed = hash_stream(stream, size, end)
        if os.name == "nt":
            stream.verify()
        else:
            require(posix_snapshot(owner, root.path, posix.MAX_CIPHERTEXT_BYTES, posix.MAX_MEMBERS, end) == rows,
                    "HASH_MEMBER_CHANGED")
        result = {"name": name, "size": size, "sha256": hashed}
    finally:
        if stream is not None:
            owner.close_one(stream)
    require(not owner.unknown, "HASH_MEMBER_RETIREMENT_UNKNOWN")
    return result


class Controller(PrivateOwner):
    def __init__(self, profile):
        super().__init__()
        require(profile in PRODUCT_SECONDS, "CONTROLLER_PROFILE")
        self.profile, self.role = profile, processes.host_role()
        self.kind, self.command = profile_command(profile, self.role)
        self.path = session_path(profile, self.role)
        self.state_path = self.path / "state"
        self.deadline = time.monotonic() + TOTAL_SECONDS[profile]
        # This remains an operation ceiling, NEVER the full job's start/time.
        # Full products cannot launch until the actual service budget is bound.
        self.budget, self.last_raw = None, 0
        self.budget_exhausted, self.cutoff_observation = False, None
        self.budget_cancellation, self.terminal_raw = None, None
        token = os.environ.pop(job_time.TOKEN_ENV, None)
        self.actions_token = token if profile == "full" else None
        self.cancelled, self.records, self.phase_hashes = [], [], {}
        self.job = uuid.uuid4().hex
        self.private = self.evidence = self.commands = self.runtime = self.crypto = None
        self.context = self.request = self.admitted = None
        self.product = self.custody = None
        self.product_attempted = self.encrypted = False
        self.export_return = None
        self.environment = child_environment(dict(os.environ), self.path, self.state_path)

    def now_raw(self):
        self.last_raw = job_time.raw_now(self.last_raw)
        return self.last_raw

    def window(self, stage, seconds):
        local = time.monotonic()
        if self.budget is None:
            return min(self.deadline, local + seconds)
        now = self.now_raw()
        fence = self.budget.fence(stage)
        require(now < fence, "FULL_JOB_STAGE_EXPIRED")
        return min(self.deadline, local + seconds, local + (fence - now) / job_time.NS)

    def check_window(self, stage, end):
        posix._deadline(end)
        if self.budget is not None:
            require(self.now_raw() < self.budget.fence(stage), "FULL_JOB_STAGE_EXPIRED")

    def mark_cutoff(self, phase, now):
        self.budget_exhausted = True
        if self.cutoff_observation is None:
            self.cutoff_observation = {"phase": phase, "observedRawNs": now}

    def budget_result(self):
        return {"sha256": None if self.budget is None else self.budget.sha256,
                "productiveCutoffRawNs": None if self.budget is None else self.budget.fence("productive"),
                "controllerReturnRawNs": None if self.budget is None else self.budget.fence("controller-return"),
                "exhausted": self.budget_exhausted, "cutoffObservation": self.cutoff_observation,
                "cooperativeCancellation": self.budget_cancellation, "terminalRawNs": self.terminal_raw}

    def check(self, finalizing=False):
        require(not self.unknown and not QUARANTINE and not windows._QUARANTINE and not query.QUARANTINE,
                "PRIOR_NATIVE_RETIREMENT_UNKNOWN")
        posix._deadline(self.deadline)
        if self.budget is not None:
            now = self.now_raw()
            require(now < self.budget.fence("controller-return"), "FULL_JOB_RETURN_EXPIRED")
            if not finalizing and now >= self.budget.fence("productive"):
                self.mark_cutoff("admission", now)
            require(finalizing or not self.budget_exhausted, "FULL_JOB_PRODUCTIVE_CUTOFF")
        if self.cancelled and not finalizing:
            raise KeyboardInterrupt("ORDINARY_TEST_CONTROLLER_CANCELLED")

    def allocate(self):
        self.private = self.new(self.path)
        end = min(self.deadline, time.monotonic() + FINAL_SECONDS)
        self.evidence = self.child(self.private, "evidence", end, create=True)
        self.commands = self.child(self.evidence, "commands", end, create=True)
        self.runtime = self.child(self.private, "runtime", end, create=True)
        self.crypto = self.child(self.private, "crypto", end, create=True)
        self.child(self.private, "temporary", end, create=True)
        self.child(self.private, "control-home", end, create=True)

    def phase(self, label, argv, timeout, *, finalizing=False, product=False, acquire_time=False):
        """Actual fixed-caller composition around make_scope, not a new backend."""
        self.check(finalizing)
        require(type(timeout) is int and 0 < timeout <= OUTER_SECONDS[self.profile], "PHASE_TIMEOUT")
        started = time.monotonic()
        end, final_end = min(self.deadline, started + timeout), min(self.deadline, started + timeout + FINAL_SECONDS)
        raw_started = raw_work_end = raw_final_end = None
        if self.profile == "full":
            raw_started = self.now_raw()
            if acquire_time:
                require(label == "job-time" and not finalizing and not product and self.budget is None and
                        self.admitted is not None and timeout == job_time.ACQUIRE_SECONDS and
                        argv == self.python(__file__, "_job-time", "--profile", "full", "--admission-sha256",
                                            digest(self.admitted.record)), "JOB_TIME_CLOSED_ACQUISITION")
                raw_work_end = raw_started + timeout * job_time.NS
                raw_final_end = raw_work_end + FINAL_SECONDS * job_time.NS
            else:
                require(self.budget is not None, "FULL_JOB_TIME_NOT_ADMITTED")
                stage = {"recipient-validation": "productive", "audit-init": "productive",
                         "custody-prepare": "productive", "product": "product-return",
                         "custody-collect": "collect", "custody-uninstall": "uninstall", "export": "export"}
                finish = {"productive": "preparation-final", "product-return": "product-final",
                          "collect": "collect-final", "uninstall": "uninstall-final", "export": "export-final"}
                require(label in stage, "FULL_JOB_CLOSED_PHASE")
                end = min(end, self.window(stage[label], timeout))
                final_end = min(final_end, self.window(finish[stage[label]], timeout + FINAL_SECONDS))
                raw_work_end = min(raw_started + timeout * job_time.NS, self.budget.fence(stage[label]))
                raw_final_end = min(raw_started + (timeout + FINAL_SECONDS) * job_time.NS,
                                    self.budget.fence(finish[stage[label]]))
        else:
            require(not acquire_time, "JOB_TIME_FULL_ONLY")
        invocation = uuid.uuid4().hex
        directory = self.child(self.commands, label, final_end, create=True)
        job = self.context["id"] if product else self.job
        state = self.state_path if product else self.path
        home = state / ("gradle-home" if product else "control-home")
        env = processes.ownership_environment(self.environment, job, invocation, str(state), str(home),
                                              allow_new_context=True)
        if acquire_time:
            require(type(self.actions_token) is str and self.actions_token, "JOB_TIME_READ_TOKEN_REQUIRED")
            env[job_time.TOKEN_ENV], self.actions_token = self.actions_token, None
        row = {"schema": 1, "phase": label, "argv": list(argv), "cwd": str(ROOT), "job": job,
               "invocation": invocation, "state": str(state), "home": str(home), "exitCode": None,
               "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN", "errors": []}
        if self.profile == "full":
            row.update(jobBudgetSha256=None if self.budget is None else self.budget.sha256,
                       startedRawNs=raw_started, completedRawNs=None, finalizedRawNs=None,
                       cooperativeCancellation=None)
        self.records.append(row)
        before_errors = len(self.errors)
        receipt_complete = False
        scope = child = out = err = None
        native_known = False
        original = None
        cancellation_requested = False

        def check_phase_budget():
            nonlocal cancellation_requested, end
            now = self.now_raw() if self.profile == "full" else None
            cutoff = self.budget is not None and not finalizing and now >= self.budget.fence("productive")
            if cutoff:
                self.mark_cutoff(label, now)
            if (cutoff or self.cancelled) and not finalizing:
                if product and not cancellation_requested:
                    # Record the single ATTEMPT before entering the canonical
                    # writer. A failed call is never retried or called a request.
                    cancellation_requested = True
                    cancellation = {"reason": "job-budget" if cutoff else "signal", "job": self.context["id"],
                                    "invocation": self.request["owner"]["productInvocation"],
                                    "attemptedRawNs": now, "returnedRawNs": None, "requested": False,
                                    "requestSha256": None}
                    if self.profile == "full":
                        row["cooperativeCancellation"] = cancellation
                        self.budget_cancellation = cancellation
                    audit.request_cancellation(self.state_path, self.context["id"],
                                               self.request["owner"]["productInvocation"])
                    cancellation["requested"] = True
                    cancellation["returnedRawNs"] = self.now_raw() if self.profile == "full" else None
                    end = min(end, time.monotonic() + 330)
                    if self.profile == "full":
                        # The exact request still precedes native drain when a
                        # delayed poll has consumed the cooperative slot. Its
                        # original bytes may use ONLY the reserved final slot.
                        copy_end = min(final_end, self.window("product-final", 30))
                        state_directory = self.child(self.private, "state", copy_end)
                        requests = self.child(state_directory, "cancellations", copy_end)
                        raw = self.read(requests, cancellation["invocation"] + ".json", copy_end)
                        actual = parse(raw)
                        require(actual.get("schema") == 1 and actual.get("id") == cancellation["invocation"] and
                                actual.get("jobId") == cancellation["job"], "JOB_TIME_CANCELLATION_CHANGED")
                        target = self.child(self.evidence, "job-time", copy_end)
                        self.write(target, "product-cancellation.json", raw, copy_end)
                        cancellation["requestSha256"] = digest(raw)
                        self.check_window("product-final", copy_end)
                    # Full end already uses the immutable productive+330 fence;
                    # observation delay MUST NOT grant another fresh 330s.
                elif not product:
                    if cutoff:
                        raise ControllerError("FULL_JOB_PRODUCTIVE_CUTOFF")
                    raise KeyboardInterrupt("ORDINARY_TEST_CONTROLLER_CANCELLED")
            if self.profile == "full":
                now = self.now_raw()
                require(now < raw_work_end, "FULL_JOB_PHASE_EXPIRED")
            return now

        try:
            self.write(directory, "start.json", row, final_end)
            out = self.acquire("phase-stdout", lambda: directory.create_file(
                "stdout.log", max_bytes=OUTPUT_LIMIT, deadline=final_end))
            err = self.acquire("phase-stderr", lambda: directory.create_file(
                "stderr.log", max_bytes=OUTPUT_LIMIT, deadline=final_end))
            self.check(finalizing)
            row["scopeAttempted"] = True
            scope = self.acquire("native-phase", lambda: processes.make_scope(job, invocation, str(state), str(home)))
            self.write(directory, "baseline.json", {"role": self.role,
                "baseline": sorted(scope.baseline) if hasattr(scope, "baseline") else None,
                "kernelJob": self.role == "windows-x64"}, final_end)
            self.check(finalizing)
            if self.profile == "full":
                require(self.now_raw() < raw_work_end, "FULL_JOB_PHASE_EXPIRED")
            row["launchAttempted"] = True
            if product:
                self.product_attempted = True
            child = scope.spawn(list(argv), str(ROOT), env, stdout=out, stderr=err)
            require(child.stdout is None and child.stderr is None, "PRIVATE_SUPPLIED_SINKS_REQUIRED")
            while True:
                # Cooperative cancellation comes BEFORE a deadline exception
                # can enter native drain, even if polling was badly delayed.
                check_phase_budget()
                posix._deadline(end)
                if self.role == "windows-x64":
                    out.observe_live_output()
                    err.observe_live_output()
                else:
                    out.verify()
                    err.verify()
                code = child.poll()
                observed = check_phase_budget()
                posix._deadline(end)
                if code is not None:
                    row["exitCode"] = code
                    if self.profile == "full":
                        row["completedRawNs"] = observed
                    break
                scope.discover()
                time.sleep(.05)
        except BaseException as error:
            original = error
            self.error(label, error)
            if self.profile == "full" and product and row["launchAttempted"]:
                # A poll/capture/discovery error may itself have crossed the
                # productive cutoff. Preserve that first error, but do not let
                # its exceptional return bypass the single exact cooperative
                # request before the existing native failure cleanup. A failed
                # monitor is not permission for a new unmonitored grace/retry.
                try:
                    check_phase_budget()
                except BaseException as secondary:
                    self.error(label + "-cutoff-finalizer", secondary)
        finally:
            env.pop(job_time.TOKEN_ENV, None)
            self.actions_token = None
            if scope is not None:
                try:
                    row["survivors"] = scope.drain(grace=5, kill_wait=5)
                    require(row["survivors"] == [], "PHASE_SURVIVORS")
                    row["ownership"] = scope.description()
                    require(row["ownership"].get("discoveryErrors") == [], "PHASE_DISCOVERY_UNKNOWN")
                    native_known = True
                except BaseException as error:
                    self.error(label + "-drain", error, unknown=True)
                self.close_one(scope)
            elif row["scopeAttempted"]:
                self.error(label + "-construction", ControllerError("PHASE_CONSTRUCTION_UNKNOWN"), unknown=True)
            else:
                native_known = True
            if native_known and not self.unknown:
                for stream in (out, err):
                    if stream is not None:
                        try:
                            stream.sync()
                            stream.verify()
                        except BaseException as error:
                            self.error(label + "-capture", error)
                        self.close_one(stream)
            else:
                self.unknown = True  # Keep original pins/sinks beneath an unknown writer.
            row["retirement"] = "UNKNOWN" if self.unknown else "KNOWN"
            try:
                if self.profile == "full":
                    row["finalizedRawNs"] = self.now_raw()
                    require(row["finalizedRawNs"] < raw_final_end, "FULL_JOB_PHASE_FINAL_EXPIRED")
                row["errors"] = self.errors[before_errors:]
                posix._deadline(final_end)
                self.write(directory, "result.json", row, final_end)
                if self.profile == "full":
                    require(self.now_raw() < raw_final_end, "FULL_JOB_PHASE_FINAL_EXPIRED")
                self.phase_hashes[label] = digest(encoded(row))
                receipt_complete = True
            except BaseException as error:
                self.error(label + "-receipt", error)
        if original is not None:
            raise original
        require(receipt_complete and not self.unknown and len(self.errors) == before_errors and
                not row["errors"], "PHASE_FINALIZATION_FAILED")
        if self.cancelled and not finalizing:
            raise KeyboardInterrupt("ORDINARY_TEST_CONTROLLER_CANCELLED")
        require(finalizing or not self.budget_exhausted, "FULL_JOB_PRODUCTIVE_CUTOFF")
        return row

    def python(self, *args):
        executable = str(Path(sys.executable).resolve(strict=True))
        if args and Path(args[0]) == SCRIPTS / "run-audit-command.py":
            return canonical_python(executable, self.canonical_sources, *args[1:])
        return [executable, "-I", "-B", "-S", *map(str, args)]

    def setup(self):
        self.allocate()
        self.admitted = admission(self, self.profile, self.evidence.path / "admission", self.check)
        if self.profile == "full":
            resolved = shutil.which("python3", path=self.environment.get("PATH", ""))
            require(resolved is not None and Path(resolved).resolve(strict=True) == Path(sys.executable).resolve(strict=True),
                    "FULL_PYTHON_DIFFERS_FROM_NATIVE_CONTROLLER")
        original = parse(self.admitted.record)
        self.canonical_sources = canonical_bindings()
        if self.profile == "full":
            self.acquire_job_time()
        context = {"schema": 1, "scope": "CLOSED_ORDINARY_TEST_CONTROLLER", "profile": self.profile,
                   "role": self.role, "root": str(ROOT), "session": str(self.path), "job": self.job,
                   "admissionSha256": digest(self.admitted.record), "source": original["source"],
                   "command": self.command, "kind": self.kind, "python": str(Path(sys.executable).resolve(strict=True)),
                   "canonicalSources": self.canonical_sources}
        if self.profile == "full":
            context["jobBudgetSha256"] = self.budget.sha256
        self.write(self.private, "run-context.json", context, self.window("productive", 45))
        self.context_hash = digest(encoded(context))
        self.crypto_operation("validate")
        self.recipient_raw = self.read(self.private, "recipient.json", self.window("productive", 30))
        recipient = parse(self.recipient_raw)
        require(recipient["fingerprint"] == self.admitted.fingerprint and
                recipient["key_sha256"] == self.admitted.key_sha256 and
                (recipient["expires_at"] == 0 or self.admitted.expires_at <= recipient["expires_at"]),
                "RECIPIENT_VALIDITY_DIFFERS")
        # init, not this controller, creates the previously absent state/home.
        row = self.phase("audit-init", self.python(SCRIPTS / "run-audit-command.py", "init", "--root", ROOT,
                         "--state", self.state_path, "--expected-commit", original["source"]["commit"],
                         "--host", self.role), 120)
        require(row["exitCode"] == 0, "CANONICAL_INIT_FAILED")
        state = self.child(self.private, "state", self.window("productive", 30))
        self.context = parse(self.read(state, "context.json", self.window("productive", 30)))
        require(self.context["root"] == str(ROOT) and self.context["host"] == self.role and
                self.context["gradleHome"] == str(self.state_path / "gradle-home") and
                self.context["source"] == {**original["source"], "status": "", "diffSha256": digest(b"")} and
                not self.context["preexistingOutputPaths"], "CANONICAL_CONTEXT_DIFFERS_OR_STALE_OUTPUTS")
        # Protect original outputs BEFORE the writers, not merely copied XML.
        for path in [*audit.output_roots(ROOT), ROOT / ".gradle", ROOT / ".kotlin",
                     ROOT / "buildSrc/.gradle", ROOT / "buildSrc/.kotlin"]:
            self.check()
            require(not os.path.lexists(path), "PREEXISTING_OUTPUT_OR_CACHE_ROOT")
            self.new(path)  # Native protected DACL + original ancestry pins on Windows.
        row = self.phase("custody-prepare", self.python(SCRIPTS / "test-transcript-custody.py", "prepare",
            "--root", ROOT, "--directory", self.evidence.path / "custody", "--home", self.state_path / "gradle-home",
            "--owner-state", self.state_path, "--owner-kind", "audit", "--scope",
            "both" if self.profile == "full" else "cli", "--", *self.command), 120)
        require(row["exitCode"] == 0, "CUSTODY_PREPARE_FAILED")
        directory = self.child(self.evidence, "custody", self.window("productive", 30))
        self.request = parse(self.read(directory, "request.json", self.window("productive", 30)))
        require(self.request["ownerKind"] == "audit" and self.request["owner"]["job"] == self.context["id"] and
                self.request["command"] == self.command and self.request["ownerState"] == str(self.state_path),
                "CUSTODY_RESERVATION_DIFFERS")

    def acquire_job_time(self):
        require(self.budget is None, "JOB_TIME_ALREADY_ADMITTED")
        row = self.phase("job-time", self.python(__file__, "_job-time", "--profile", "full", "--admission-sha256",
                         digest(self.admitted.record)), job_time.ACQUIRE_SECONDS, acquire_time=True)
        require(row["exitCode"] == 0, "JOB_TIME_ACQUISITION_FAILED")
        end = min(self.deadline, time.monotonic() + 30)
        budget = derive_job_budget(self, self.private, self.admitted, end)
        directory = self.child(self.evidence, "job-time", end)
        returned_raw = self.read(self.runtime, "job-time-result.json", end)
        require(digest(returned_raw) == budget.value["provenance"]["childReturnSha256"],
                "JOB_TIME_ORIGINAL_RETURN_CHANGED")
        self.write(directory, "child-return.json", returned_raw, end)
        self.write(directory, "budget.json", budget.record, end)
        self.budget = budget
        self.deadline = min(self.deadline, budget.deadline("controller-return", TOTAL_SECONDS["full"]))
        self.check()  # Already-spent setup never reaches crypto/init/products.

    def product_run(self):
        reserved = self.request["owner"]["productInvocation"]
        require(type(reserved) is str and re.fullmatch(r"[0-9a-f]{32}", reserved), "RESERVED_INVOCATION_REQUIRED")
        wrapper = ROOT / ("gradlew.bat" if self.role == "windows-x64" else "gradlew")
        argv = self.python(SCRIPTS / "run-audit-command.py", "--cwd", ROOT, "--wrapper", wrapper,
                           "--kind", self.kind, "--purpose", "ordinary-" + self.profile, "--id", reserved,
                           "--timeout", PRODUCT_SECONDS[self.profile], "--stop-timeout", 120, "--", *self.command)
        self.product = self.phase("product", argv, OUTER_SECONDS[self.profile], product=True)

    def collect(self):
        if self.request is None or self.unknown:
            return
        directory = self.evidence.path / "custody"
        receipt = self.state_path / "evidence" / self.request["owner"]["productInvocation"] / "receipt.json"
        # Also run after nonzero exit, timeout, cancellation, partial launch or
        # absent canonical receipt. The collector retains HOLD, not a fake pass.
        row = self.phase("custody-collect", self.python(SCRIPTS / "test-transcript-custody.py", "collect",
                         "--directory", directory, "--owner-result", receipt), 120, finalizing=True)
        end = self.window("collect-read", 30)
        private = self.child(self.evidence, "custody", end)
        self.custody = parse(self.read(private, "result.json", end))
        self.check_window("collect-read", end)
        require(row["exitCode"] in (0, 125), "CUSTODY_COLLECTOR_UNSUPPORTED_EXIT")
        if self.custody.get("retirement") != "KNOWN":
            self.unknown = True
            raise ControllerError("CANONICAL_CUSTODY_RETIREMENT_UNKNOWN")
        row = self.phase("custody-uninstall", self.python(SCRIPTS / "test-transcript-custody.py", "uninstall",
                         "--directory", directory), 90, finalizing=True)
        require(row["exitCode"] == 0, "CUSTODY_LOADER_UNINSTALL_FAILED")
        end = self.window("uninstall-read", 30)
        removed = parse(self.read(private, "uninstalled.json", end))
        self.check_window("uninstall-read", end)
        require(removed.get("absent") is True and removed.get("originalsDeleted") is False,
                "CUSTODY_UNINSTALL_RECEIPT_DIFFERS")

    def export(self):
        self.check(finalizing=True)
        require(self.admitted is not None and hasattr(self, "recipient_raw"), "NO_VALIDATED_RECIPIENT")
        end = self.window("export-freeze", 180)
        if self.context is not None:
            state = self.child(self.private, "state", end)
            original = self.child(state, "evidence", end)
            copy_tree(self, original, self.evidence.path / "canonical-audit", end)
            self.write(self.evidence, "canonical-context.json", self.read(state, "context.json", end), end)
        copy_tree(self, self.crypto, self.evidence.path / "recipient-validation", end)
        self.write(self.evidence, "recipient.json", self.recipient_raw, end)
        self.write(self.evidence, "profile-result-before-export.json", self.result(), end)
        # Frozen evidence must not contain subsequent query, crypto or outer
        # export-command writers. Only the already-frozen commands are copied.
        self.frozen = copy_tree(self, self.evidence, self.path / "frozen-evidence", end)
        self.check_window("export-freeze", end)
        self.export_return = self.crypto_operation("export")
        end = self.window("export-open", 90)
        output = self.child(self.private, "export", end)
        self.check_window("export-open", end)
        end = self.window("export-verify", 90)
        verify_export_binding(self, output, self.export_return, end)
        self.check_window("export-verify", end)
        self.check(finalizing=True)
        self.encrypted = True

    def crypto_operation(self, operation):
        """No launched crypto exception may bypass the exact child-return fence."""
        require(operation in ("validate", "export"), "CRYPTO_OPERATION")
        label = "recipient-validation" if operation == "validate" else "export"
        first_record = len(self.records)
        try:
            row = self.phase(label, self.python(__file__, "_crypto", operation, "--profile", self.profile,
                             "--context-sha256", self.context_hash), 240, finalizing=operation == "export")
            return self.crypto_return(operation, row)
        except BaseException as error:
            # A clean enclosing drain cannot establish the separate child's
            # terminal return/UNKNOWN state. This includes late outer receipt
            # failure after the child provisionally wrote its own result.
            if any(row["phase"] == label and row["launchAttempted"] for row in self.records[first_record:]):
                self.error("crypto-" + operation + "-return", error, unknown=True)
            raise

    def crypto_return(self, operation, row):
        # A generic nonzero child exit cannot erase that child's sticky supplier
        # UNKNOWN, including an exception after a provisional terminal receipt.
        if row["exitCode"] != 0:
            self.unknown = True
            raise ControllerError("CRYPTO_CHILD_DID_NOT_RETURN_KNOWN")
        try:
            stage = "export-read" if operation == "export" else "productive"
            end = self.window(stage, 30)
            raw = self.read(self.runtime, operation + "-result.json", end)
            self.check_window(stage, end)
            value = parse(raw)
            require(value["schema"] == 1 and value["operation"] == operation and value["profile"] == self.profile and
                    value["contextSha256"] == self.context_hash and value["retirement"] == "KNOWN" and
                    value["errors"] == [] and value["returned"] is True, "CRYPTO_RETURN_BINDING")
            if self.profile == "full":
                require(value.get("jobBudgetSha256") == self.budget.sha256, "CRYPTO_JOB_TIME_CHANGED")
            return {"result": value, "sha256": digest(raw)}
        except BaseException as error:
            self.error("crypto-return", error, unknown=True)
            raise

    def result(self):
        # JSON round-trip freezes lists/dicts so late finalization cannot mutate
        # a provisional return object and make an equality fence tautological.
        value = {"schema": 1, "scope": "ORDINARY_PROFILE_CUSTODY_ONLY", "profile": self.profile,
                "role": self.role, "controllerPid": os.getpid(), "source": None if self.admitted is None else
                parse(self.admitted.record)["source"], "contextSha256": getattr(self, "context_hash", None),
                "productAttempted": self.product_attempted, "retirement": "UNKNOWN" if self.unknown else "KNOWN",
                "cancelled": bool(self.cancelled), "encrypted": self.encrypted,
                "readyForPostReturnSeal": self.encrypted and not self.unknown,
                "phases": self.records, "phaseSha256": self.phase_hashes, "custody": self.custody,
                "exportReturn": self.export_return, "errors": self.errors}
        if self.profile == "full":
            value["jobBudget"] = self.budget_result()
        value["profilePassed"] = profile_passed(value)
        return parse(encoded(value))


def profile_passed(value):
    """A boolean label cannot overrule original phase/custody outcomes."""
    rows = value["phases"]
    labels = ["recipient-validation", "audit-init", "custody-prepare", "product", "custody-collect",
              "custody-uninstall"]
    if value.get("profile") == "full":
        labels.insert(0, "job-time")
        budget = value.get("jobBudget", {})
        if not (type(budget.get("sha256")) is str and re.fullmatch(r"[0-9a-f]{64}", budget["sha256"]) and
                budget.get("exhausted") is False and budget.get("cutoffObservation") is None and
                budget.get("cooperativeCancellation") is None):
            return False
        for row in rows:
            if row["phase"] == "job-time":
                continue
            if row.get("jobBudgetSha256") != budget["sha256"]:
                return False
            if row["phase"] in ("recipient-validation", "audit-init", "custody-prepare", "product") and not (
                    type(row.get("completedRawNs")) is int and type(budget.get("productiveCutoffRawNs")) is int and
                    row["completedRawNs"] < budget["productiveCutoffRawNs"]):
                return False
    if value["encrypted"]:
        labels.append("export")
    custody = value["custody"]
    return (value["productAttempted"] is True and value["cancelled"] is False and value["retirement"] == "KNOWN" and
            value["errors"] == [] and [row["phase"] for row in rows] == labels and
            all(type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is True and
                row["scopeAttempted"] is True and row["retirement"] == "KNOWN" and row["errors"] == [] and
                row.get("survivors") == [] and row.get("ownership", {}).get("discoveryErrors") == [] for row in rows) and
            type(custody) is dict and custody.get("result") == "RETAINED" and custody.get("retirement") == "KNOWN" and
            custody.get("errors") == [] and all(type(custody.get(key)) is int and custody[key] == 0 for key in
                ("productExitCode", "stopExitCode", "ownerFinalExitCode")))


def recipient_record(recipient):
    names = ("fingerprint", "encryption_fingerprint", "expires_at", "key_sha256", "work_identity")
    value = {name: getattr(recipient, name) for name in names}
    value["executable"] = str(recipient.executable)
    if os.name == "nt":
        value.update(executable_sha256=recipient.executable_sha256, job_id=recipient.job_id)
    return value


def restore_recipient(owner, work, raw, context):
    value = parse(raw)
    shared = {name: value[name] for name in ("fingerprint", "encryption_fingerprint", "expires_at", "key_sha256")}
    executable = Path(value["executable"])
    if os.name == "nt":
        require(value["job_id"] == context["job"], "RECIPIENT_JOB_CHANGED")
        return windows.Recipient(work, executable, value["executable_sha256"], tuple(value["work_identity"]),
                                 **shared, job_id=value["job_id"])
    return posix.Recipient(work.path, work.path / "gnupg", executable, **shared,
                           work_identity=tuple(value["work_identity"]))


def derive_job_budget(owner, private, admitted, end):
    """Recompute from ORIGINAL API bytes + original native phase/child return."""
    evidence = owner.child(private, "evidence", end)
    originals = owner.child(evidence, "job-time", end)
    commands = owner.child(evidence, "commands", end)
    phase = owner.child(commands, "job-time", end)
    runtime = owner.child(private, "runtime", end)
    start_raw, phase_raw = owner.read(phase, "start.json", end), owner.read(phase, "result.json", end)
    returned_raw = owner.read(runtime, "job-time-result.json", end)
    start, row, returned = parse(start_raw), parse(phase_raw), parse(returned_raw)
    expected = [str(Path(sys.executable).resolve(strict=True)), "-I", "-B", "-S", str(Path(__file__)), "_job-time",
                "--profile", "full", "--admission-sha256", digest(admitted.record)]
    require(start["phase"] == row["phase"] == "job-time" and start["argv"] == row["argv"] == expected and
            start["cwd"] == row["cwd"] == str(ROOT) and start["job"] == row["job"] and
            start["invocation"] == row["invocation"] and start["state"] == row["state"] == str(private.path) and
            start["home"] == row["home"] == str(private.path / "control-home") and
            type(row["exitCode"]) is int and row["exitCode"] == 0 and row["retirement"] == "KNOWN" and
            row["launchAttempted"] is True and row["scopeAttempted"] is True and row["errors"] == [] and
            row.get("survivors") == [] and row.get("jobBudgetSha256") is None and
            row.get("cooperativeCancellation") is None, "JOB_TIME_ORIGINAL_PHASE_CHANGED")
    ownership = row["ownership"]
    require(ownership["backend"] == "darwin-libproc-audit-token" and ownership["job"] == row["job"] and
            ownership["invocation"] == row["invocation"] and ownership["discoveryErrors"] == [] and
            ownership["launches"] and ownership["startedIdentities"], "JOB_TIME_NATIVE_PHASE_REQUIRED")
    require(type(returned.get("schema")) is int and returned["schema"] == 1 and
            returned.get("scope") == "ORDINARY_FULL_JOB_TIME_ACQUISITION" and returned.get("returned") is True and
            returned.get("retirement") == "KNOWN" and returned.get("errors") == [] and
            returned.get("admissionSha256") == digest(admitted.record) and returned.get("job") == row["job"] and
            returned.get("invocation") == row["invocation"] and returned.get("clockDomain") == job_time.RAW_CLOCK_DOMAIN,
            "JOB_TIME_ORIGINAL_RETURN_CHANGED")
    raw = {label: owner.read(originals, label + ".json", end, job_time.RECORD_LIMIT) for label in ("attempt", "jobs")}
    require(returned.get("originalsSha256") == {label: digest(value) for label, value in raw.items()},
            "JOB_TIME_ORIGINAL_RESPONSES_CHANGED")
    first, last = job_time.parse(raw["attempt"]), job_time.parse(raw["jobs"])
    times = [start.get("startedRawNs"), row.get("startedRawNs"), first.get("startedRawNs"), last.get("finishedRawNs"),
             returned.get("completedRawNs"), row.get("completedRawNs"), row.get("finalizedRawNs")]
    require(all(type(value) is int and 0 <= value <= job_time.UINT64 for value in times) and
            times == sorted(times) and times[0] == times[1] and
            times[-1] <= times[0] + (job_time.ACQUIRE_SECONDS + FINAL_SECONDS) * job_time.NS,
            "JOB_TIME_NATIVE_INTERVAL_CHANGED")
    return job_time.derive(admitted, raw, {"controllerJob": row["job"], "invocation": row["invocation"],
        "phaseStartSha256": digest(start_raw), "phaseResultSha256": digest(phase_raw),
        "childReturnSha256": digest(returned_raw), "runnerName": returned.get("runnerName")})


def load_job_budget(owner, private, admitted, context, end):
    budget = derive_job_budget(owner, private, admitted, end)
    evidence = owner.child(private, "evidence", end)
    original = owner.child(evidence, "job-time", end)
    runtime = owner.child(private, "runtime", end)
    returned_raw = owner.read(original, "child-return.json", end)
    require(returned_raw == owner.read(runtime, "job-time-result.json", end) and
            digest(returned_raw) == budget.value["provenance"]["childReturnSha256"],
            "JOB_TIME_RETAINED_RETURN_CHANGED")
    raw = owner.read(original, "budget.json", end)
    require(raw == budget.record and digest(raw) == context.get("jobBudgetSha256") and
            budget.value["provenance"]["controllerJob"] == context["job"], "IMMUTABLE_JOB_TIME_CHANGED")
    return budget


def job_time_phase(profile, admission_hash):
    """One closed read-only child; the token never enters ordinary/Git children."""
    token = os.environ.pop(job_time.TOKEN_ENV, None)
    owner = PrivateOwner()
    end, began = time.monotonic() + job_time.ACQUIRE_SECONDS, job_time.raw_now()
    runtime = None
    error, returned, terminal = None, None, False
    try:
        require(profile == "full", "JOB_TIME_FULL_ONLY")
        inherited = query._inherited_context()
        require(set(inherited) == set(query._CONTEXT), "JOB_TIME_REQUIRES_EXISTING_NATIVE_OWNER")
        role = processes.host_role()
        require(role in ("macos-arm64", "macos-x64"), "JOB_TIME_NATIVE_MAC_REQUIRED")
        path = session_path(profile, role)
        private = owner.open(path)
        runtime = owner.child(private, "runtime", end)
        evidence = owner.child(private, "evidence", end)
        original = owner.child(evidence, "admission", end)
        admitted = load_admission(owner, original, end)
        require(digest(admitted.record) == admission_hash, "JOB_TIME_ADMISSION_CHANGED")
        record, _, _, _ = job_time.admitted_identity(admitted)
        require(record["github"]["runnerArch"] == ("ARM64" if role == "macos-arm64" else "X64"),
                "JOB_TIME_NATIVE_ARCH_CHANGED")
        commands = owner.child(evidence, "commands", end)
        phase = owner.child(commands, "job-time", end)
        start = parse(owner.read(phase, "start.json", end))
        domain = processes.ownership_domains(inherited[processes.CHAIN_ENV], inherited[processes.DOMAINS_ENV])[-1]
        require(start["job"] == domain["job"] and start["invocation"] == domain["id"] and
                start["state"] == domain["state"] == str(path) and
                start["home"] == domain["home"] == str(path / "control-home") and start["cwd"] == str(ROOT) and
                start["phase"] == "job-time", "JOB_TIME_ORIGINAL_NATIVE_DOMAIN_CHANGED")
        directory = owner.child(evidence, "job-time", end, create=True)
        raw = job_time.acquire(admitted, domain["id"], token,
                               lambda label, value: owner.write(directory, label + ".json", value, end))
        returned = {"schema": 1, "scope": "ORDINARY_FULL_JOB_TIME_ACQUISITION", "admissionSha256": admission_hash,
                    "job": domain["job"], "invocation": domain["id"], "runnerName": os.environ.get("RUNNER_NAME"),
                    "clockDomain": job_time.RAW_CLOCK_DOMAIN, "completedRawNs": job_time.raw_now(began),
                    "originalsSha256": {label: digest(value) for label, value in raw.items()}}
    except BaseException as caught:
        error = caught
        owner.error("job-time-acquisition", caught)
    finally:
        token = None
        try:
            if runtime is not None:
                owner.write(runtime, "job-time-result.json", {**(returned or {}), "returned": error is None,
                    "retirement": "UNKNOWN" if owner.unknown else "KNOWN", "errors": owner.errors}, end)
                terminal = True
        except BaseException as caught:
            error = error or caught
            owner.error("job-time-terminal", caught)
        try:
            owner.close()
        except BaseException as caught:
            error = error or caught
    # A provisional receipt is insufficient: actual child exit and native
    # retirement must also succeed before the parent derives any budget.
    posix._deadline(end)
    require(job_time.raw_now(began) < began + job_time.ACQUIRE_SECONDS * job_time.NS, "JOB_TIME_ACQUISITION_EXPIRED")
    if error is not None:
        raise error
    require(terminal and not owner.unknown and not owner.errors, "JOB_TIME_TERMINAL_INCOMPLETE")


def crypto_phase(operation, profile, context_hash):
    """Closed child; its real outer native owner must outlive ALL GPG descendants."""
    owner = PrivateOwner()
    error, terminal, runtime, exported, budget, budget_clock = None, False, None, None, None, None
    end = time.monotonic() + 210
    def check_crypto():
        posix._deadline(end)
        if budget_clock is not None:
            budget_clock.check("productive" if operation == "validate" else "export")
    try:
        require(operation in ("validate", "export"), "CRYPTO_OPERATION")
        require(job_time.TOKEN_ENV not in os.environ, "JOB_TIME_TOKEN_IN_CRYPTO")
        inherited = query._inherited_context()
        require(set(inherited) == set(query._CONTEXT), "CRYPTO_REQUIRES_EXISTING_NATIVE_OWNER")
        role = processes.host_role()
        path = session_path(profile, role)
        private = owner.open(path)
        raw = owner.read(private, "run-context.json", end)
        context = parse(raw)
        require(digest(raw) == context_hash and context["profile"] == profile and context["role"] == role and
                context["root"] == str(ROOT) and context["session"] == str(path), "CRYPTO_CONTEXT_CHANGED")
        require(inherited[processes.JOB_ENV] == context["job"] and inherited[processes.STATE_ENV] == str(path) and
                inherited["GRADLE_USER_HOME"] == str(path / "control-home"), "CRYPTO_OUTER_CONTEXT_DIFFERS")
        runtime = owner.child(private, "runtime", end)
        evidence = owner.child(private, "evidence", end)
        commands = owner.child(evidence, "commands", end)
        phase = owner.child(commands, "recipient-validation" if operation == "validate" else "export", end)
        started = parse(owner.read(phase, "start.json", end))
        domain = processes.ownership_domains(inherited[processes.CHAIN_ENV], inherited[processes.DOMAINS_ENV])[-1]
        require(started["job"] == domain["job"] and started["invocation"] == domain["id"] and
                started["state"] == domain["state"] and started["home"] == domain["home"] and
                started["cwd"] == str(ROOT), "CRYPTO_ORIGINAL_OUTER_START_DIFFERS")
        original = owner.child(evidence, "admission", end)
        admitted = load_admission(owner, original, end)
        require(digest(admitted.record) == context["admissionSha256"], "CRYPTO_ADMISSION_CHANGED")
        if profile == "full":
            budget = load_job_budget(owner, private, admitted, context, end)
            budget_clock = job_time.BudgetClock(budget)
            end = min(end, budget_clock.deadline("productive" if operation == "validate" else "export", 210))
        work = owner.child(private, "crypto", end)
        checked = admission(owner, profile, runtime.path / (operation + "-admission"),
                            check_crypto, expected=admitted)
        if operation == "validate":
            if os.name == "nt":
                recipient = windows.validate_recipient(checked.public_key, checked.fingerprint, work, job_id=context["job"])
            else:
                recipient = posix.validate_recipient(original.path / "recipient-public.asc", checked.fingerprint, work.path)
            require(recipient.key_sha256 == checked.key_sha256 and
                    (not recipient.expires_at or checked.expires_at <= recipient.expires_at), "CRYPTO_POLICY_LIFETIME")
            owner.write(private, "recipient.json", recipient_record(recipient), end)
        else:
            recipient = restore_recipient(owner, work, owner.read(private, "recipient.json", end), context)
            frozen = owner.child(private, "frozen-evidence", end)
            supplier, original_error = None, None
            try:
                supplier = query.NativeGitQueries(ROOT, runtime.path / "export-manifest-admission",
                                                  check_cancel=check_crypto)
                supplier.native_host_matches_actions()
                if os.name == "nt":
                    output = owner.new(path / "export")
                    manifest = windows.export_test_encrypted(frozen, output, recipient, profile=profile, root=ROOT,
                                      admission=checked, query_runner=supplier, timeout_seconds=180)
                else:
                    manifest = ordinary.export_encrypted(frozen.path, path / "export", recipient, profile=profile,
                                      root=ROOT, admission=checked, query_runner=supplier, timeout_seconds=180)
                    output = owner.child(private, "export", end)
                # Bind the exporter's ORIGINAL return before the enclosing child
                # returns, not a manifest synthesized from post-return files.
                exported = {"manifest": manifest, "manifestSha256": digest(encoded(manifest))}
                require(owner.read(output, posix.MANIFEST, end, 65536) == encoded(manifest) and
                        artifact_metadata(owner, output, end) == manifest["artifact"], "ORIGINAL_EXPORT_DIFFERS")
            except BaseException as caught:
                original_error = caught
            finally:
                if supplier is not None:
                    try:
                        supplier._finalize(original_error)
                    except BaseException as secondary:
                        if original_error is None:
                            original_error = secondary
                if (supplier is not None and supplier.unknown) or query.QUARANTINE or windows._QUARANTINE:
                    owner.error("export-query", original_error or ControllerError("QUERY_UNKNOWN"), unknown=True)
            if original_error is not None:
                raise original_error
        require(not owner.unknown and not query.QUARANTINE and not windows._QUARANTINE, "CRYPTO_RETIREMENT_UNKNOWN")
        check_crypto()
    except BaseException as caught:
        error = caught
        owner.error("crypto-" + operation, caught)
    finally:
        try:
            if runtime is not None:
                owner.write(runtime, operation + "-result.json", {"schema": 1, "operation": operation,
                    "profile": profile, "contextSha256": context_hash, "returned": error is None,
                    "retirement": "UNKNOWN" if owner.unknown else "KNOWN", "errors": owner.errors,
                    **({"jobBudgetSha256": budget.sha256} if budget is not None else {}),
                    **(exported or {})}, end)
                terminal = True
        except BaseException as caught:
            owner.error("crypto-terminal", caught)
            error = error or caught
        try:
            owner.close()
        except BaseException as caught:
            error = error or caught
    try:
        check_crypto()
    except BaseException as caught:
        owner.error("crypto-final-deadline", caught)
        error = error or caught
    if error is not None:
        raise error
    require(terminal and not owner.unknown and not owner.errors, "CRYPTO_TERMINAL_INCOMPLETE")


def run(profile):
    controller, result, terminal = None, None, False
    handlers, cancelled = {}, []
    original = None
    try:
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handlers[number] = signal.getsignal(number)
            signal.signal(number, lambda value, _frame: cancelled.append(value))
        controller = Controller(profile)
        controller.cancelled = cancelled
        controller.check()
        controller.setup()
        controller.product_run()
    except BaseException as error:
        original = error
        if controller is not None:
            controller.actions_token = None
            controller.error("run", error)
    finally:
        if controller is not None:
            controller.actions_token = None
            for name in ("collect", "export"):
                try:
                    getattr(controller, name)()
                except BaseException as error:
                    controller.error(name, error)
                    original = original or error
            try:
                if profile == "full":
                    controller.check(finalizing=True)
                    controller.terminal_raw = controller.now_raw()
                result = controller.result()
                if controller.private is not None:
                    controller.write(controller.private, "controller-result.json", result,
                                     min(controller.deadline, time.monotonic() + FINAL_SECONDS))
                    terminal = True  # Complete write AND exact readback, not only an attempted write.
            except BaseException as error:
                controller.error("final-receipt", error)
                original = original or error
            try:
                controller.close()
            except BaseException as error:
                terminal = False
                original = original or error
        for number, handler in handlers.items():
            try:
                signal.signal(number, handler)
            except BaseException as error:
                terminal = False
                original = original or error
                if controller is not None:
                    controller.error("signal-restoration", error, unknown=True)
    # Known failed products may be encrypted/retained, never a passing gate.
    # Immutable final-state equality and actual process exit fence late errors.
    ready = (terminal and result is not None and result["readyForPostReturnSeal"] and controller is not None and
             not controller.unknown and time.monotonic() < controller.deadline and not QUARANTINE and
             not windows._QUARANTINE and not query.QUARANTINE and result == controller.result())
    if ready and profile == "full":
        try:
            controller.check(finalizing=True)
        except BaseException:
            ready = False
    print("ORDINARY_TEST_CUSTODY=" + ("RETURNED_FOR_SEAL" if ready else "HOLD"))
    return 0 if ready else 125


def artifact_metadata(owner, output, end):
    snapshot = None
    try:
        if os.name == "nt":
            snapshot = owner.acquire("sealed-output-snapshot", lambda: output.snapshot(
                max_bytes=files.MAX_FILE_BYTES, max_members=3, deadline=end))
            require(set(snapshot.entries) == {"", posix.ARTIFACT, posix.MANIFEST}, "SEALED_OUTPUT_MEMBERS")
        else:
            rows = posix_snapshot(owner, output.path, posix.MAX_CIPHERTEXT_BYTES, 3, end)
            require(set(rows) == {"", posix.ARTIFACT, posix.MANIFEST}, "SEALED_OUTPUT_MEMBERS")
        result = hash_member(owner, output, posix.ARTIFACT, end, maximum=posix.MAX_CIPHERTEXT_BYTES)
        if snapshot is not None:
            snapshot.verify()
        else:
            require(posix_snapshot(owner, output.path, posix.MAX_CIPHERTEXT_BYTES, 3, end) == rows, "SEALED_OUTPUT_CHANGED")
    finally:
        if snapshot is not None:
            owner.close_one(snapshot)
    require(not owner.unknown, "SEALED_OUTPUT_CLOSE_UNKNOWN")
    return result


def verify_export_binding(owner, output, original, end):
    value = original["result"]
    require(digest(encoded(value)) == original["sha256"] and value["returned"] is True and
            value["retirement"] == "KNOWN" and value["errors"] == [], "EXPORT_RETURN_CHANGED")
    raw = owner.read(output, posix.MANIFEST, end, 65536)
    require(digest(raw) == value["manifestSha256"] and parse(raw) == value["manifest"] and
            artifact_metadata(owner, output, end) == value["manifest"]["artifact"], "EXPORTED_ARTIFACT_CHANGED")
    return raw


def verify_phase_bindings(owner, private, result, context, end, budget=None):
    """Retain/recheck original phase bytes, exact selectors and native domains."""
    evidence = owner.child(private, "evidence", end)
    commands = owner.child(evidence, "commands", end)
    request = None
    require(type(result["phases"]) is list and len(result["phases"]) <= (8 if budget is not None else 7) and
            len({row["phase"] for row in result["phases"]}) == len(result["phases"]), "PHASE_SET_CHANGED")
    require(set(result["phaseSha256"]) == {row["phase"] for row in result["phases"]}, "PHASE_BINDING_SET")
    for row in result["phases"]:
        label = row["phase"]
        require(label in ({"recipient-validation", "audit-init", "custody-prepare", "product", "custody-collect",
                           "custody-uninstall", "export"} | ({"job-time"} if budget is not None else set())), "PHASE_LABEL")
        directory = owner.child(commands, label, end)
        raw = owner.read(directory, "result.json", end)
        require(digest(raw) == result["phaseSha256"][label] and parse(raw) == row and row["cwd"] == str(ROOT),
                "ORIGINAL_PHASE_CHANGED")
        if budget is not None:
            start = parse(owner.read(directory, "start.json", end))
            require(all(start[key] == row[key] for key in ("phase", "argv", "cwd", "job", "invocation", "state", "home",
                                                         "jobBudgetSha256", "startedRawNs")), "PHASE_RAW_START_CHANGED")
            require(type(row.get("startedRawNs")) is int and type(row.get("finalizedRawNs")) is int and
                    0 <= row["startedRawNs"] <= row["finalizedRawNs"] <= job_time.UINT64,
                    "PHASE_RAW_INTERVAL_CHANGED")
            if row.get("completedRawNs") is not None:
                require(type(row["completedRawNs"]) is int and
                        row["startedRawNs"] <= row["completedRawNs"] <= row["finalizedRawNs"], "PHASE_RAW_INTERVAL_CHANGED")
            if label != "job-time":
                finish = {"recipient-validation": "preparation-final", "audit-init": "preparation-final",
                          "custody-prepare": "preparation-final", "product": "product-final",
                          "custody-collect": "collect-final", "custody-uninstall": "uninstall-final", "export": "export-final"}
                require(row["jobBudgetSha256"] == budget.sha256 and
                        row["finalizedRawNs"] < budget.fence(finish[label]), "PHASE_JOB_TIME_CHANGED")
        if row["retirement"] == "KNOWN" and row["launchAttempted"]:
            ownership = row["ownership"]
            expected_backend = {"linux-x64": "linux-proc-pidfd", "windows-x64": "windows-job-list-suspended",
                                "macos-arm64": "darwin-libproc-audit-token", "macos-x64": "darwin-libproc-audit-token"}
            require(ownership["job"] == row["job"] and ownership["invocation"] == row["invocation"] and
                    ownership["backend"] == expected_backend[result["role"]] and ownership["launches"] and
                    ownership["startedIdentities"] and ownership["discoveryErrors"] == [], "PHASE_NATIVE_BINDING")
    if result["custody"] is not None:
        custody = owner.child(evidence, "custody", end)
        request_raw = owner.read(custody, "request.json", end)
        request = parse(request_raw)
        original = parse(owner.read(custody, "result.json", end))
        require(original == result["custody"] and original["requestSha256"] == digest(request_raw) and
                request["root"] == str(ROOT) and request["ownerKind"] == "audit" and
                request["command"] == context["command"] and request["ownerState"] == str(private.path / "state") and
                request["home"] == str(private.path / "state/gradle-home"), "ORIGINAL_CUSTODY_CHANGED")
        if profile_passed(result):
            state = owner.child(private, "state", end)
            canonical_context = parse(owner.read(state, "context.json", end))
            require(canonical_context["id"] == request["owner"]["job"] and
                    canonical_context["source"] == request["source"] and
                    all(request["source"][key] == context["source"][key] for key in ("commit", "tree")),
                    "CANONICAL_SOURCE_CONTEXT_CHANGED")
            retained = owner.child(custody, "retained", end)
            canonical_raw = owner.read(retained, "owner-result.json", end)
            canonical = parse(canonical_raw)
            evidence_state = owner.child(state, "evidence", end)
            invocation = owner.child(evidence_state, request["owner"]["productInvocation"], end)
            require(owner.read(invocation, "receipt.json", end) == canonical_raw and
                    canonical["requestedArgv"] == context["command"] and canonical["kind"] == context["kind"] and
                    canonical["id"] == request["owner"]["productInvocation"] and
                    canonical["jobId"] == request["owner"]["job"] and canonical["gradleHome"] == request["home"] and
                    canonical["cwd"] == str(ROOT) and canonical["host"] == result["role"] and
                    canonical["sourceBefore"] == canonical["sourceAfter"] == request["source"] and
                    canonical["sourceUnchanged"] is True and canonical["errors"] == [] and
                    canonical["ownedSurvivors"] == [] and canonical["ownership"]["discoveryErrors"] == [] and
                    all(type(canonical[key]) is int and canonical[key] == 0 for key in
                        ("productExitCode", "stopExitCode", "finalExitCode")), "CANONICAL_PRODUCT_NOT_PASSING")
            product = next(row for row in result["phases"] if row["phase"] == "product")
            expected = canonical_python(context["python"], context["canonicalSources"], "--cwd", str(ROOT),
                "--wrapper", str(ROOT / ("gradlew.bat" if result["role"] == "windows-x64" else "gradlew")),
                "--kind", context["kind"], "--purpose", "ordinary-" + result["profile"], "--id", canonical["id"],
                "--timeout", str(PRODUCT_SECONDS[result["profile"]]), "--stop-timeout", "120", "--", *context["command"])
            require(product["argv"] == expected and product["job"] == canonical["jobId"] and
                    product["state"] == str(state.path) and product["home"] == request["home"], "PRODUCT_SELECTOR_CHANGED")
            removed = parse(owner.read(custody, "uninstalled.json", end))
            require(removed["absent"] is True and removed["originalsDeleted"] is False and
                    removed["requestSha256"] == original["requestSha256"], "ORIGINAL_UNINSTALL_CHANGED")
    if budget is not None:
        timing = result.get("jobBudget", {})
        require(timing.get("sha256") == budget.sha256 and
                timing.get("productiveCutoffRawNs") == budget.fence("productive") and
                timing.get("controllerReturnRawNs") == budget.fence("controller-return") and
                type(timing.get("terminalRawNs")) is int and
                budget.value["responseFinishedRawNs"] <= timing["terminalRawNs"] < budget.fence("controller-return") and
                type(timing.get("exhausted")) is bool, "SEALED_JOB_BUDGET_CHANGED")
        cutoff = timing.get("cutoffObservation")
        if timing["exhausted"]:
            require(type(cutoff) is dict and set(cutoff) == {"phase", "observedRawNs"} and
                    cutoff["phase"] in {"admission", "recipient-validation", "audit-init", "custody-prepare", "product"} and
                    type(cutoff["observedRawNs"]) is int and
                    budget.fence("productive") <= cutoff["observedRawNs"] <= timing["terminalRawNs"],
                    "SEALED_JOB_CUTOFF_CHANGED")
        else:
            require(cutoff is None, "SEALED_JOB_CUTOFF_CHANGED")
        cancellation = timing.get("cooperativeCancellation")
        product = next((row for row in result["phases"] if row["phase"] == "product"), None)
        if cancellation is not None:
            require(product is not None and product.get("cooperativeCancellation") == cancellation and
                    cancellation.get("reason") in ("job-budget", "signal") and type(cancellation.get("requested")) is bool,
                    "SEALED_CANCELLATION_CHANGED")
            if cancellation["reason"] == "job-budget":
                require(timing["exhausted"] and type(cancellation.get("attemptedRawNs")) is int and
                        cancellation["attemptedRawNs"] >= budget.fence("productive"), "SEALED_CANCELLATION_CHANGED")
            if cancellation["requested"]:
                require(type(request) is dict, "SEALED_CANCELLATION_WITHOUT_CUSTODY")
                original = owner.child(evidence, "job-time", end)
                raw = owner.read(original, "product-cancellation.json", end)
                state = owner.child(private, "state", end)
                requests = owner.child(state, "cancellations", end)
                require(owner.read(requests, cancellation["invocation"] + ".json", end) == raw and
                        digest(raw) == cancellation.get("requestSha256"), "SEALED_CANCELLATION_ORIGINAL_CHANGED")
                value = parse(raw)
                require(value.get("schema") == 1 and value.get("jobId") == cancellation["job"] and
                        value.get("id") == cancellation["invocation"] and request["owner"]["job"] == cancellation["job"] and
                        request["owner"]["productInvocation"] == cancellation["invocation"], "SEALED_CANCELLATION_CHANGED")
        else:
            require(product is None or product.get("cooperativeCancellation") is None, "SEALED_CANCELLATION_CHANGED")


def validate_public(profile):
    """Separate interpreter only; provisional files cannot grant upload authority."""
    require(os.environ.get("P2PKIT_HOSTED_TEST_RUN_OUTCOME") == "success", "ORIGINAL_CONTROLLER_DID_NOT_SUCCEED")
    require(job_time.TOKEN_ENV not in os.environ, "JOB_TIME_TOKEN_IN_SEAL")
    owner = PrivateOwner()
    end = time.monotonic() + 120
    error, budget, budget_clock = None, None, None
    passed = False
    try:
        role = processes.host_role()
        path = session_path(profile, role)
        private = owner.open(path)
        result_raw = owner.read(private, "controller-result.json", end)
        result = parse(result_raw)
        context_raw = owner.read(private, "run-context.json", end)
        context = parse(context_raw)
        require(result["schema"] == 1 and result["scope"] == "ORDINARY_PROFILE_CUSTODY_ONLY" and
                result["profile"] == profile and result["role"] == role and result["controllerPid"] != os.getpid() and
                result["retirement"] == "KNOWN" and result["encrypted"] is True and
                result["readyForPostReturnSeal"] is True and result["contextSha256"] == digest(context_raw),
                "CONTROLLER_RESULT_NOT_SEALABLE")
        require(context["profile"] == profile and context["role"] == role and context["root"] == str(ROOT) and
                context["session"] == str(path) and context["canonicalSources"] == canonical_bindings(),
                "SEALED_CONTEXT_CHANGED")
        evidence = owner.child(private, "evidence", end)
        original = owner.child(evidence, "admission", end)
        expected = load_admission(owner, original, end)
        require(digest(expected.record) == context["admissionSha256"], "SEALED_ADMISSION_CHANGED")
        if profile == "full":
            budget = load_job_budget(owner, private, expected, context, end)
            budget_clock = job_time.BudgetClock(budget)
            budget_clock.check("seal-start")
            end = min(end, budget_clock.deadline("seal", 120))
        # A replay cannot overwrite the previous post-return receipt.
        validation = owner.new(path / "post-return-validation")
        checked = admission(owner, profile, path / "seal-admission", lambda: posix._deadline(end), expected=expected)
        output = owner.child(private, "export", end)
        runtime = owner.child(private, "runtime", end)
        returned_raw = owner.read(runtime, "export-result.json", end)
        require(digest(returned_raw) == result["exportReturn"]["sha256"] and
                parse(returned_raw) == result["exportReturn"]["result"], "ORIGINAL_EXPORT_RETURN_CHANGED")
        returned = result["exportReturn"]["result"]
        require(returned["operation"] == "export" and returned["profile"] == profile and
                returned["contextSha256"] == digest(context_raw), "SEALED_EXPORT_CONTEXT_CHANGED")
        if budget is not None:
            require(returned.get("jobBudgetSha256") == budget.sha256, "SEALED_EXPORT_JOB_TIME_CHANGED")
        manifest_raw = verify_export_binding(owner, output, result["exportReturn"], end)
        manifest = parse(manifest_raw)
        actual = manifest["artifact"]
        record = parse(checked.record)
        expected_manifest = {"schema": 2, "scope": "ENCRYPTED_PRIVATE_TEST_EVIDENCE", "source": record["source"],
            "github": record["github"], "policy": record["policy"],
            "custody": {"profile": record["profile"], "suites": record["suites"]}, "artifact": actual}
        require(manifest == expected_manifest and result["source"] == context["source"] == record["source"],
                "SEALED_MANIFEST_DIFFERS")
        require((context["kind"], context["command"]) == profile_command(profile, role), "SEALED_SELECTOR_CHANGED")
        verify_phase_bindings(owner, private, result, context, end, budget)
        passed = profile_passed(result)
        require(type(result["profilePassed"]) is bool and result["profilePassed"] == passed, "FAILED_PROFILE_RELABELLED")
        owner.write(validation, "seal.json", {"schema": 1, "controllerResultSha256": digest(result_raw),
            "manifestSha256": digest(manifest_raw), "artifact": actual, "profilePassed": passed,
            "source": record["source"], "retirement": "KNOWN", "decryption": "NOT_PERFORMED",
            **({"jobBudgetSha256": budget.sha256, "clockDomain": job_time.RAW_CLOCK_DOMAIN,
                "sealedAtRawNs": budget_clock.check("seal"),
                "upload": {"seconds": job_time.UPLOAD_SECONDS, "latestStartRawNs": budget.fence("upload-start"),
                           "endRawNs": budget.fence("upload")}} if budget is not None else {})}, end)
        require(owner.read(private, "controller-result.json", end) == result_raw and
                owner.read(output, posix.MANIFEST, end, 65536) == manifest_raw, "POST_RETURN_INPUT_CHANGED")
    except BaseException as caught:
        error = caught
        owner.error("post-return-seal", caught)
    finally:
        try:
            owner.close()
        except BaseException as caught:
            if error is None:
                error = caught
    if error is not None:
        raise error
    require(not owner.unknown, "POST_RETURN_CLOSE_UNKNOWN")
    posix._deadline(end)
    if budget_clock is not None:
        budget_clock.check("seal")
    # Mandatory workflow consumers also require THIS step's successful outcome;
    # a partial append/error does not grant upload from a failed seal step.
    target = Path(os.environ["GITHUB_OUTPUT"])
    audit.reject_symlinks(target)
    with target.open("a", encoding="ascii") as stream:
        posix._deadline(end)
        stream.write("artifacts_ready=true\nprofile_passed=" + str(passed).lower() + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    # Step success is required even if a provisional output append preceded an
    # overrun/failure during fsync or output close. Never renew the original end.
    posix._deadline(end)
    if budget_clock is not None:
        budget_clock.check("seal")
    print("ORDINARY_TEST_CIPHERTEXT_SEAL=PASS; PRIVATE_DECRYPTION=NOT_PERFORMED")


def upload_guard(phase):
    """Closed before/after fence for FUTURE reviewed upload wiring, not upload.

    Wiring must require both guards' real successful outcomes, the exact before
    receipt hash, a <=3 minute pinned upload step and its successful outcome.
    This guard cannot schedule/guarantee GitHub step transitions or transfer.
    A late/failed upload never grants whole-gate acceptance from a prior seal.
    """
    require(phase in ("before", "after") and job_time.TOKEN_ENV not in os.environ and
            os.environ.get("P2PKIT_HOSTED_TEST_RUN_OUTCOME") == "success" and
            os.environ.get("P2PKIT_HOSTED_TEST_SEAL_OUTCOME") == "success", "UPLOAD_REQUIRES_REAL_SEAL_SUCCESS")
    if phase == "after":
        require(os.environ.get("P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME") == "success", "UPLOAD_ORIGINAL_ACTION_FAILED")
    owner = PrivateOwner()
    error, clock, outputs, upload_end = None, None, None, None
    end = time.monotonic() + job_time.TRANSITION_SECONDS
    stage = "upload-start" if phase == "before" else "upload"
    try:
        private = owner.open(session_path("full", processes.host_role()))
        context_raw = owner.read(private, "run-context.json", end)
        result_raw = owner.read(private, "controller-result.json", end)
        context, result = parse(context_raw), parse(result_raw)
        require(context["profile"] == result["profile"] == "full" and context["root"] == str(ROOT) and
                context["session"] == str(private.path) and context["canonicalSources"] == canonical_bindings() and
                result["contextSha256"] == digest(context_raw) and result["retirement"] == "KNOWN" and
                result["readyForPostReturnSeal"] is True, "UPLOAD_ORIGINAL_CONTEXT_CHANGED")
        evidence = owner.child(private, "evidence", end)
        original = owner.child(evidence, "admission", end)
        admitted = load_admission(owner, original, end)
        require(digest(admitted.record) == context["admissionSha256"], "UPLOAD_ORIGINAL_ADMISSION_CHANGED")
        budget = load_job_budget(owner, private, admitted, context, end)
        clock = job_time.BudgetClock(budget)
        began = clock.check(stage)
        end = min(end, clock.deadline(stage, job_time.TRANSITION_SECONDS))
        seal_directory = owner.child(private, "post-return-validation", end)
        seal_raw = owner.read(seal_directory, "seal.json", end)
        seal = parse(seal_raw)
        require(seal.get("jobBudgetSha256") == budget.sha256 and seal.get("clockDomain") == job_time.RAW_CLOCK_DOMAIN and
                seal.get("controllerResultSha256") == digest(result_raw) and seal.get("source") == context["source"] and
                seal.get("profilePassed") == result["profilePassed"] == profile_passed(result) and
                seal.get("retirement") == "KNOWN" and type(seal.get("sealedAtRawNs")) is int and
                budget.value["responseFinishedRawNs"] <= seal["sealedAtRawNs"] < budget.fence("seal") and
                seal["sealedAtRawNs"] <= began and seal.get("upload") == {
                    "seconds": job_time.UPLOAD_SECONDS, "latestStartRawNs": budget.fence("upload-start"),
                    "endRawNs": budget.fence("upload")}, "UPLOAD_ORIGINAL_SEAL_CHANGED")
        checked = admission(owner, "full", private.path / ("upload-" + phase + "-admission"),
                            lambda: (posix._deadline(end), clock.check(stage)), expected=admitted)
        require(parse(checked.record)["source"] == seal["source"], "UPLOAD_SOURCE_CHANGED")
        output = owner.child(private, "export", end)
        manifest_raw = owner.read(output, posix.MANIFEST, end, 65536)
        require(digest(manifest_raw) == seal["manifestSha256"] and parse(manifest_raw)["artifact"] == seal["artifact"] and
                artifact_metadata(owner, output, end) == seal["artifact"],
                "UPLOAD_SEALED_MANIFEST_CHANGED")
        binding = {"schema": 1, "scope": "CLOSED_FULL_UPLOAD_SCHEDULING_CAP", "contextSha256": digest(context_raw),
                   "controllerResultSha256": digest(result_raw), "sealSha256": digest(seal_raw),
                   "jobBudgetSha256": budget.sha256, "manifestSha256": digest(manifest_raw),
                   "source": seal["source"], "clockDomain": job_time.RAW_CLOCK_DOMAIN,
                   "maximumSeconds": job_time.UPLOAD_SECONDS, "timeoutMinutes": 3}
        if phase == "before":
            upload_end = min(budget.fence("upload"), began + job_time.UPLOAD_SECONDS * job_time.NS)
            raw = encoded({**binding, "beganRawNs": began, "endRawNs": upload_end})
            owner.write(private, "upload-before.json", raw, end)
            outputs = "upload_ready=true\nupload_timeout_minutes=3\nupload_guard_sha256=" + digest(raw) + "\n"
        else:
            raw = owner.read(private, "upload-before.json", end)
            before = parse(raw)
            require(os.environ.get("P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256") == digest(raw) and
                    set(before) == set(binding) | {"beganRawNs", "endRawNs"} and
                    all(before.get(key) == value for key, value in binding.items()) and
                    type(before["beganRawNs"]) is int and type(before["endRawNs"]) is int and
                    seal["sealedAtRawNs"] <= before["beganRawNs"] < budget.fence("upload-start") and
                    before["endRawNs"] == min(budget.fence("upload"),
                                              before["beganRawNs"] + job_time.UPLOAD_SECONDS * job_time.NS) and
                    before["beganRawNs"] <= began < before["endRawNs"], "UPLOAD_ORIGINAL_FENCE_CHANGED_OR_EXPIRED")
            upload_end = before["endRawNs"]
            owner.write(private, "upload-after.json", {**binding, "beforeSha256": digest(raw), "observedRawNs": began,
                                                       "stepOutcome": "success"}, end)
            outputs = "upload_complete=true\n"
    except BaseException as caught:
        error = caught
        owner.error("upload-" + phase, caught)
    finally:
        try:
            owner.close()
        except BaseException as caught:
            error = error or caught
    if error is not None:
        raise error
    require(not owner.unknown and outputs is not None, "UPLOAD_GUARD_RETIREMENT_UNKNOWN")
    posix._deadline(end)
    require(clock.check(stage) < upload_end, "UPLOAD_GUARD_EXPIRED")
    target = Path(os.environ["GITHUB_OUTPUT"])
    audit.reject_symlinks(target)
    with target.open("a", encoding="ascii") as stream:
        posix._deadline(end)
        require(clock.check(stage) < upload_end, "UPLOAD_GUARD_EXPIRED")
        stream.write(outputs)
        stream.flush()
        os.fsync(stream.fileno())
    posix._deadline(end)
    require(clock.check(stage) < upload_end, "UPLOAD_GUARD_EXPIRED")
    print("ORDINARY_FULL_UPLOAD_GUARD=" + phase.upper() + "; NO_UPLOAD_PERFORMED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for name in ("run", "validate-public", "_crypto", "_job-time", "upload-guard"):
        entry = sub.add_parser(name)
        entry.add_argument("--profile", choices=("full",) if name in ("_job-time", "upload-guard") else PRODUCT_SECONDS,
                           required=True)
        if name == "_crypto":
            entry.add_argument("phase", choices=("validate", "export"))
            entry.add_argument("--context-sha256", required=True)
        elif name == "_job-time":
            entry.add_argument("--admission-sha256", required=True)
        elif name == "upload-guard":
            entry.add_argument("phase", choices=("before", "after"))
    args = parser.parse_args()
    try:
        if args.operation == "run":
            return run(args.profile)
        if args.operation == "validate-public":
            validate_public(args.profile)
        elif args.operation == "_job-time":
            require(re.fullmatch(r"[0-9a-f]{64}", args.admission_sha256), "JOB_TIME_ADMISSION_HASH")
            job_time_phase(args.profile, args.admission_sha256)
        elif args.operation == "upload-guard":
            upload_guard(args.phase)
        else:
            require(re.fullmatch(r"[0-9a-f]{64}", args.context_sha256), "CRYPTO_CONTEXT_HASH")
            crypto_phase(args.phase, args.profile, args.context_sha256)
        return 0
    except BaseException:
        print("ORDINARY_TEST_CUSTODY=HOLD; PRIVATE_EVIDENCE_REQUIRED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
