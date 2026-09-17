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
import hosted_full_simulator as simulator
import hosted_evidence as posix
import hosted_primary_abi as abi
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
FULL_STAGE = {"recipient-validation": "productive", "audit-init": "productive",
              "custody-prepare": "productive", "product": "product-return", "custody-collect": "collect",
              "custody-uninstall": "uninstall", "export": "export",
              **{label: "productive" for label in (*simulator.PREPARE, simulator.PRELAUNCH)},
              **{label: label for label in simulator.RETIRE}}
FULL_FINISH = {"productive": "preparation-final", "product-return": "product-final", "collect": "collect-final",
               "uninstall": "uninstall-final", "export": "export-final",
               **{label: label + "-final" for label in simulator.RETIRE}}
FULL_PREPARATION = ("job-time", "recipient-validation", "audit-init", *simulator.PREPARE,
                    "custody-prepare", simulator.PRELAUNCH, "product")
FULL_ORDER = (*FULL_PREPARATION, "custody-collect", "custody-uninstall", *simulator.RETIRE, "export")
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


def abi_references(owner, commit, destination, end, check):
    """Own exactly24 closed Git reads including constructor/final-return failures."""
    supplier, original, references = None, None, {}
    try:
        supplier = query.NativeGitQueries(ROOT, destination, check_cancel=check)
        check()  # A returned allocation is owned even if this pre-entry check fails.
        supplier.native_host_matches_actions()
        view = identity.GitView(ROOT, dict(os.environ), supplier)
        for index, path in enumerate(abi.BASELINES):
            check()
            references[index] = view.abi_baseline(commit, path)
        check()
    except BaseException as error:
        original = error
    finally:
        if supplier is not None:
            try:
                supplier._finalize(original)
            except BaseException as error:
                original = original or error
        if (supplier is not None and supplier.unknown) or query.QUARANTINE or windows._QUARANTINE:
            owner.error("abi-reference-query", original or ControllerError("QUERY_UNKNOWN"), unknown=True)
        try:
            check()  # Native query close cannot extend the caller's original fence.
        except BaseException as error:
            original = original or error
    if original is not None:
        raise original
    require(not owner.unknown and set(references) == set(range(8)), "ABI_REFERENCE_QUERIES_INCOMPLETE")
    directory = owner.open(destination)
    raw = owner.read(directory, "session-result.json", end, query.MAX_RECEIPT_BYTES)
    value = parse(raw)
    require(value.get("schema") == 1 and value.get("scope") == "ORDINARY_GIT_QUERIES_ONLY" and
            value.get("result") == "READY_FOR_CALLER_SEAL" and value.get("retirement") == "KNOWN" and
            value.get("firstError") is None and value.get("errors") == [] and
            type(value.get("queries")) is list and len(value["queries"]) == 24, "ABI_REFERENCE_QUERY_RETURN")
    for index, path in enumerate(abi.BASELINES):
        blob, _raw = references[index]
        suffixes = (("ls-tree", "-z", commit, "--", path), ("cat-file", "-s", blob), ("cat-file", "blob", blob))
        for row, suffix in zip(value["queries"][index * 3:index * 3 + 3], suffixes):
            require(row.get("argv") == [view.executable, "--no-replace-objects", "--no-pager", "-c",
                        "core.fsmonitor=false", "-C", str(ROOT), *suffix] and
                    row.get("cwd") == str(ROOT) and row.get("result") == "READY_FOR_CALLER_SEAL" and
                    row.get("retirement") == "KNOWN" and row.get("errors") == [] and
                    type(row.get("waitExitCode")) is int and row["waitExitCode"] == 0,
                    "ABI_REFERENCE_ORIGINAL_QUERY_CHANGED")
    check()
    return references, {"bytes": len(raw), "sha256": digest(raw)}


def abi_ancestors(build, subtree):
    """Public0755 generated descendants are not private-directory suppliers."""
    build.verify()  # Original pre-writer root owner, never a newly adopted build.
    stamps = {}
    for relative in ("kotlin", "kotlin/" + subtree):
        path = build.path / relative
        try:
            info = path.lstat()
        except FileNotFoundError:
            return None  # A known absent output can be retained as missing, never green.
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o022,
                "ABI_GENERATED_ANCESTOR_UNSAFE")
        stamps[relative] = list(posix._stamp(info))
    return stamps


def retain_abi_generated(owner, target, build_owners, end):
    """Six exact snapshots; eight separately acquired original generated files."""
    require(os.name == "posix", "PRIMARY_FULL_ABI_NATIVE_MAC_ONLY")
    groups = {}
    for index, (module, generated, *_rest) in enumerate(abi.ROUTES):
        subtree, name = generated.split("/", 1)
        groups.setdefault((module, subtree), []).append((index, name))
    originals, acquired, roots = {}, {}, []
    for (module, subtree), members in groups.items():
        posix._deadline(end)
        build_path = ROOT / "library" / module / "build"
        require(build_path in build_owners, "ABI_PREWRITER_BUILD_OWNER_MISSING")
        build = build_owners[build_path]
        require(build.path == build_path, "ABI_PREWRITER_BUILD_OWNER_CHANGED")
        before = abi_ancestors(build, subtree)
        root = build.path / "kotlin" / subtree
        bound = {"root": str(root.relative_to(ROOT)), "buildRoot": str(build_path.relative_to(ROOT)),
                 "buildIdentity": list(build.identity), "ancestors": before}
        roots.append(bound)
        if before is None:
            for index, _name in members:
                originals[index] = acquired[index] = None
            require(abi_ancestors(build, subtree) is None, "ABI_MISSING_OUTPUT_CHANGED")
            continue
        names = {name for _index, name in members}
        directories = {""} | {name.rsplit("/", 1)[0] for name in names if "/" in name}
        entries = posix_snapshot(owner, root, len(members) * abi.FILE_LIMIT, len(names | directories), end)
        require(set(entries) == names | directories and
                all(stat.S_ISDIR(entries[name][2]) for name in directories) and
                all(stat.S_ISREG(entries[name][2]) and 0 < entries[name][5] <= abi.FILE_LIMIT for name in names),
                "ABI_EXACT_GENERATED_ROSTER_REQUIRED")
        for index, name in members:
            reader = owner.acquire("abi-generated-reader", lambda: posix._open_member(root, name, entries))
            original = None
            try:
                posix._deadline(end)
                raw = reader.read(entries[name][5] + 1)
                require(type(raw) is bytes and len(raw) == entries[name][5] and reader.read(1) == b"" and
                        posix._stamp(os.fstat(reader.fileno())) == entries[name], "ABI_ORIGINAL_CHANGED_DURING_READ")
            except BaseException as error:
                original = error
                owner.error("abi-generated-read", error)
            finally:
                owner.close_one(reader)
            if original is not None:
                raise original
            require(not owner.unknown, "ABI_GENERATED_READER_RETIREMENT_UNKNOWN")
            owner.write(target, abi.member(index, "generated"), raw, end)
            originals[index], acquired[index] = raw, list(entries[name])
        require(posix_snapshot(owner, root, len(members) * abi.FILE_LIMIT, len(names | directories), end) == entries and
                abi_ancestors(build, subtree) == before, "ABI_GENERATED_SNAPSHOT_CHANGED")
        build.verify()
    return originals, {"roots": roots, "files": [acquired[index] for index in range(8)]}


def primary_abi_log(owner, invocation, end, *, name="product.stdout.log"):
    """Bounded original-log stream; never the4MiB JSON record reader."""
    invocation.verify()
    query._component(name)  # Also admits only the closed opaque frozen-copy member.
    path = invocation.path / name
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1 and
            not info.st_mode & 0o077 and 0 <= info.st_size <= abi.LOG_LIMIT, "ABI_ORIGINAL_LOG_UNSAFE")
    rows = {"": posix._stamp(invocation.path.lstat()), name: posix._stamp(info)}
    reader = owner.acquire("abi-log-reader", lambda: posix._open_member(invocation.path, name, rows))
    original, result = None, None
    try:
        result = abi.observe_log(reader, info.st_size, lambda: posix._deadline(end))
        require(posix._stamp(os.fstat(reader.fileno())) == rows[name], "ABI_ORIGINAL_LOG_CHANGED")
    except BaseException as error:
        original = error
        owner.error("abi-log-read", error)
    finally:
        owner.close_one(reader)
    if original is not None:
        raise original
    require(not owner.unknown and posix._stamp(path.lstat()) == rows[name] and
            posix._stamp(invocation.path.lstat()) == rows[""], "ABI_ORIGINAL_LOG_CHANGED_OR_UNCLOSED")
    invocation.verify()
    return result


def primary_abi_inputs(owner, private, context, end):
    """The original command receipt + platform Gradle selector, not an invented leaf."""
    state = owner.child(private, "state", end)
    state_raw = owner.read(state, "context.json", end)
    admitted = parse(state_raw)
    evidence = owner.child(private, "evidence", end)
    custody = owner.child(evidence, "custody", end)
    request_raw, custody_raw = (owner.read(custody, name, end) for name in ("request.json", "result.json"))
    request, collected = parse(request_raw), parse(custody_raw)
    retained = owner.child(custody, "retained", end)
    canonical_evidence = owner.child(state, "evidence", end)
    invocation = owner.child(canonical_evidence, request["owner"]["productInvocation"], end)
    canonical_raw = owner.read(invocation, "receipt.json", end)
    canonical = parse(canonical_raw)
    require(canonical_raw == owner.read(retained, "owner-result.json", end), "ABI_ORIGINAL_CUSTODY_DIFFERS")
    source = {**context["source"], "status": "", "diffSha256": digest(b"")}
    require(context.get("primaryAbiRequired") is True and context["profile"] == "full" and
            context["root"] == str(ROOT) and context["session"] == str(private.path) and
            context["role"] in ("macos-arm64", "macos-x64") and
            context["kind"] == "command" and context["command"] == ["python3", "scripts/run-platform-tests.py", "full"] and
            admitted["source"] == request["source"] == source and admitted["preexistingOutputPaths"] == [] and
            admitted["id"] == request["owner"]["job"] == canonical["jobId"] and
            admitted["host"] == canonical["host"] == context["role"] and admitted["root"] == request["root"] == str(ROOT) and
            admitted["gradleHome"] == request["home"] == canonical["gradleHome"] == str(state.path / "gradle-home") and
            request["ownerKind"] == "audit" and request["ownerState"] == str(state.path) and
            request["command"] == canonical["requestedArgv"] == canonical.get("executedArgv") == context["command"] and
            canonical["id"] == request["owner"]["productInvocation"] and canonical["kind"] == "command" and
            canonical.get("purpose") == "ordinary-full" and canonical["cwd"] == str(ROOT) and
            canonical.get("wrapper") == str(ROOT / "gradlew") and
            canonical["sourceBefore"] == canonical["sourceAfter"] == source and canonical["sourceUnchanged"] is True and
            canonical["errors"] == [] and canonical["ownedSurvivors"] == [] and
            canonical["ownership"]["discoveryErrors"] == [] and
            (canonical.get("cancelledSignals") is None or canonical.get("cancelledSignals") == []) and
            (canonical.get("cancelRequested") is None or canonical.get("cancelRequested") is False) and
            all(type(canonical[key]) is int and canonical[key] == 0 for key in
                ("productExitCode", "stopExitCode", "finalExitCode")) and
            collected["requestSha256"] == digest(request_raw) and collected["result"] == "RETAINED" and
            collected["retirement"] == "KNOWN" and collected["errors"] == [] and
            all(type(collected[key]) is int and collected[key] == 0 for key in
                ("productExitCode", "stopExitCode", "ownerFinalExitCode")), "ABI_PRIMARY_CANONICAL_NOT_PASSING")
    uninstall_raw = owner.read(custody, "uninstalled.json", end)
    uninstall = parse(uninstall_raw)
    require(uninstall.get("absent") is True and uninstall.get("originalsDeleted") is False and
            uninstall.get("requestSha256") == digest(request_raw), "ABI_PRIMARY_LOADER_NOT_UNINSTALLED")
    commands = owner.child(evidence, "commands", end)
    product_directory = owner.child(commands, "product", end)
    product_raw = owner.read(product_directory, "result.json", end)
    product = parse(product_raw)
    require(type(product["exitCode"]) is int and product["exitCode"] == 0 and product["retirement"] == "KNOWN" and
            product["errors"] == [] and product["survivors"] == [], "ABI_PRIMARY_OUTER_NOT_PASSING")
    binding = owner.read(owner.child(evidence, "simulator", end), "binding.json", end)
    platform = platform_simulator_binding(owner, private, binding, end)
    start_raw = owner.read(invocation, "start.json", end)
    prelaunch = original_simulator_prelaunch(owner, private, binding, end)
    # Existing A authority verifies actual created outer/canonical native births.
    original_simulator_authority(owner, private, binding, prelaunch, product, end)
    report_directory = invocation
    for name in ("reports", "build", "reports", "platform-tests", platform["token"]):
        report_directory = owner.child(report_directory, name, end)
    reports = {}
    for name in ("invocation", "execution", "summary"):
        raw = owner.read(report_directory, name + ".json", end)
        require(digest(raw) == platform["reportsSha256"][name], "ABI_PLATFORM_REPORT_CHANGED")
        reports[name] = parse(raw)
    expected = [str(ROOT / "gradlew"), "check", *abi.FLAGS, "--init-script",
                str(ROOT / "gradle/platform-test-coverage.init.gradle"), "-Pp2pkit.testCoverageRoot=" + str(ROOT),
                "-Pp2pkit.testCoverageToken=" + platform["token"],
                "-Pp2pkit.ordinarySimulatorBinding=" + str(private.path / simulator.RELATIVE),
                "-Pp2pkit.ordinarySimulatorSha256=" + digest(binding),
                "-Pp2pkit.ordinarySimulatorStartSha256=" + digest(start_raw),
                "-Pp2pkit.ordinarySimulatorPrelaunchSha256=" + digest(prelaunch)]
    arch = reports["execution"].get("host", {})
    require(reports["invocation"].get("command") == reports["summary"].get("command") == expected and
            arch.get("os") in ("Mac OS X", "Darwin") and arch.get("arch", "").lower() in
            (("aarch64", "arm64") if context["role"] == "macos-arm64" else ("x86_64", "amd64")),
            "ABI_PLATFORM_FULL_SELECTOR_OR_HOST_CHANGED")
    return {"canonicalReceiptSha256": digest(canonical_raw), "canonicalStartSha256": digest(start_raw),
            "canonicalContextSha256": digest(state_raw), "custodyRequestSha256": digest(request_raw),
            "custodyResultSha256": digest(custody_raw), "uninstallSha256": digest(uninstall_raw),
            "productPhaseSha256": digest(product_raw), "productInvocation": canonical["id"],
            "reportManifestSha256": digest(owner.read(invocation, "report-manifest.json", end)),
            "platform": platform, "gradleCommand": expected}, primary_abi_log(owner, invocation, end)


def abi_disposition(raw):
    value = parse(raw)
    return {"status": value["assessment"]["status"], "manifestSha256": digest(raw),
            "contextSha256": value["contextSha256"], "productPhaseSha256": value["primary"]["productPhaseSha256"],
            "generatedCount": sum(row["generated"] is not None for row in value["assessment"]["routes"])}


def abi_copy_map(raw, root):
    """The exact two copy_tree schemas; their strings are lookups, never paths to open."""
    mapping = parse(raw)
    require(type(mapping) is dict and set(mapping) == {"schema", "scope", "originalRoot", "directories", "files"} and
            type(mapping["schema"]) is int and mapping["schema"] == 1 and
            mapping["scope"] == "REVERSIBLE_PRIVATE_BYTE_COPY" and mapping["originalRoot"] == str(root) and
            type(mapping["files"]) is list and type(mapping["directories"]) is list and
            len(mapping["files"]) + len(mapping["directories"]) <= posix.MAX_MEMBERS, "ABI_FROZEN_MAP_CHANGED")
    all_rows = mapping["files"]

    def relative(name):
        return (type(name) is str and len(name.encode("utf-8")) <= 1024 and "\\" not in name and
                all(ord(part) >= 32 and ord(part) != 127 for part in name) and
                (name == "" or len(name.split("/")) <= 65 and
                 all(part not in ("", ".", "..") for part in name.split("/"))))

    require(all(type(row) is dict and set(row) == {"original", "member", "size", "sha256"} and
                relative(row["original"]) and row["original"] != "" and type(row["member"]) is str and
                row["member"] == "member-" + str(index).zfill(5) + ".bin" and
                type(row["size"]) is int and 0 <= row["size"] <= posix.MAX_BYTES and
                type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
                for index, row in enumerate(all_rows)) and
            all(relative(name) for name in mapping["directories"]), "ABI_FROZEN_MAP_ROSTER")
    names, directories = [row["original"] for row in all_rows], mapping["directories"]
    require(names == sorted(set(names)) and directories == sorted(set(directories)) and "" in directories and
            not set(names) & set(directories) and sum(row["size"] for row in all_rows) <= posix.MAX_BYTES and
            all((name.rsplit("/", 1)[0] if "/" in name else "") in directories
                for name in [*names, *directories] if name),
            "ABI_FROZEN_MAP_ROSTER")
    return mapping


def frozen_abi_provenance(owner, private, frozen, outer, end):
    """Resolve only closed primary roles through BOTH maps to independent originals.

    A self-consistent copied map cannot certify its own content. Read the original
    custody ID and canonical token inventory, not a path supplied by either map.
    Known failed/partial products bind available originals without requiring PASS;
    absence is checked too. This adds no process, query, product or time window.
    """
    directories, absent, stamps, originals = {(): private}, set(), {}, []

    def directory(parts):
        if parts in directories:
            return directories[parts]
        parent = directory(parts[:-1])
        if parent is None:
            return None
        query._component(parts[-1])
        parent.verify()
        posix._deadline(end)
        path = parent.path / parts[-1]
        if not os.path.lexists(path):
            absent.add(path)
            directories[parts] = None
        else:
            directories[parts] = owner.child(parent, parts[-1], end)
        return directories[parts]

    def original(parts, maximum, log=False):
        parent = directory(parts[:-1])
        if parent is None:
            return None
        query._component(parts[-1])
        parent.verify()
        posix._deadline(end)
        path = parent.path / parts[-1]
        try:
            stamps[path] = posix._stamp(path.lstat())
        except FileNotFoundError:
            absent.add(path)
            return None
        return (primary_abi_log(owner, parent, end, name=parts[-1]) if log else
                owner.read(parent, parts[-1], end, maximum))

    def copied(row, maximum, log=False):
        require(type(row) is dict and 0 <= row["size"] <= maximum, "ABI_FROZEN_PROVENANCE_BOUND")
        value = (primary_abi_log(owner, frozen, end, name=row["member"]) if log else
                 owner.read(frozen, row["member"], end, maximum))
        size, sha256 = (value["bytes"], value["sha256"]) if log else (len(value), digest(value))
        require((size, sha256) == (row["size"], row["sha256"]), "ABI_FROZEN_PROVENANCE_BYTES_CHANGED")
        return value

    def match(parts, copied_name, maximum=RECORD_LIMIT, *, inner_row=None, log=False):
        value = original(parts, maximum, log)
        row = outer.get(copied_name)
        require((value is None) == (row is None), "ABI_FROZEN_PROVENANCE_MISSING")
        if value is None:
            originals.append({"original": "/".join(parts), "copy": copied_name, "present": False})
            return None
        if inner_row is not None:
            require((row["size"], row["sha256"]) == (inner_row["size"], inner_row["sha256"]),
                    "ABI_FROZEN_CANONICAL_MAP_DIFFERS")
        require(copied(row, maximum, log) == value, "ABI_FROZEN_ORIGINAL_PROVENANCE_DIFFERS")
        size, sha256 = (value["bytes"], value["sha256"]) if log else (len(value), digest(value))
        originals.append({"original": "/".join(parts), "copy": copied_name, "member": row["member"],
                          "present": True, "size": size, "sha256": sha256,
                          **({"log": value} if log else {})})
        return value

    run_raw = original(("run-context.json",), RECORD_LIMIT)
    require(run_raw is not None, "ABI_ORIGINAL_CONTEXT_MISSING")
    request_raw = None
    direct = ["profile-result-before-export.json", "primary-abi/manifest.json", "custody/request.json", "custody/result.json",
              "custody/uninstalled.json", "custody/retained/owner-result.json",
              "primary-abi-queries/session-result.json", "commands/product/start.json", "commands/product/result.json"]
    direct += ["simulator/" + name + ".json" for name in
               ("admission", "binding", "prelaunch", "canonical-start", "canonical-product", "launch", "retirement")]
    direct += ["commands/" + label + "/" + name for label in
               (*simulator.PREPARE, simulator.PRELAUNCH, *simulator.RETIRE)
               for name in ("start.json", "result.json", "stdout.log", "stderr.log")]
    for name in direct:
        value = match(("evidence", *name.split("/")), name,
                      query.MAX_RECEIPT_BYTES if name == "primary-abi-queries/session-result.json" else RECORD_LIMIT)
        if name == "custody/request.json":
            request_raw = value

    # Before canonical admission a failed init may leave an unused partial state.
    # Once its context was used by simulator/custody/B1, both exported roles are
    # mandatory, even for HOLD. Never read a cache or adopt a generated build here.
    canonical_used = (directory(("evidence", "simulator")) is not None or
                      directory(("evidence", "custody")) is not None or
                      directory(("evidence", "canonical-audit")) is not None or
                      any(name == "canonical-context.json" or name.startswith("canonical-audit/") for name in outer))
    canonical_raw, canonical_directory, canonical_rows = None, None, None
    if canonical_used:
        require(match(("state", "context.json"), "canonical-context.json") is not None,
                "ABI_FROZEN_CANONICAL_CONTEXT_MISSING")
        canonical_directory = directory(("state", "evidence"))
        require(canonical_directory is not None, "ABI_FROZEN_CANONICAL_ROOT_MISSING")
        canonical_rows = posix_snapshot(owner, canonical_directory.path, posix.MAX_BYTES, posix.MAX_MEMBERS, end)
        canonical_raw = copied(outer.get("canonical-audit/original-path-map.json"), RECORD_LIMIT)
        inner = abi_copy_map(canonical_raw, private.path / "state/evidence")
        inner_rows = {row["original"]: row for row in inner["files"]}
        require(inner["directories"] == sorted(name for name, row in canonical_rows.items() if stat.S_ISDIR(row[2])) and
                set(inner_rows) == {name for name, row in canonical_rows.items() if stat.S_ISREG(row[2])} and
                all(row["size"] == canonical_rows[name][5] for name, row in inner_rows.items()),
                "ABI_FROZEN_CANONICAL_ROSTER_DIFFERS")
        require({name for name in outer if name.startswith("canonical-audit/")} ==
                {"canonical-audit/original-path-map.json", *["canonical-audit/" + row["member"]
                                                           for row in inner["files"]]},
                "ABI_FROZEN_CANONICAL_COPY_ROSTER")
        if request_raw is not None:
            request = parse(request_raw)
            invocation = request.get("owner", {}).get("productInvocation")
            require(type(invocation) is str and re.fullmatch(r"[0-9a-f]{32}", invocation), "ABI_ORIGINAL_INVOCATION")
            paths = [invocation + "/" + name for name in
                     ("receipt.json", "start.json", "report-manifest.json", "product.stdout.log")]
            reports = [name for name in canonical_rows if re.fullmatch(re.escape(invocation) +
                       r"/reports/build/reports/platform-tests/[0-9a-f]{32}/(?:invocation|execution|summary)\.json", name)]
            require(len({name.split("/")[-2] for name in reports}) <= 1, "ABI_ORIGINAL_PLATFORM_TOKEN_ROSTER")
            for name in [*paths, *sorted(reports)]:
                row = inner_rows.get(name)
                # None cannot address any outer row; a missing original stays
                # missing rather than being supplied from another invocation.
                copied_name = None if row is None else "canonical-audit/" + row["member"]
                log = name == invocation + "/product.stdout.log"
                match(("state", "evidence", *name.split("/")), copied_name,
                      abi.LOG_LIMIT if log else RECORD_LIMIT, inner_row=row, log=log)
    for path, stamp in stamps.items():
        posix._deadline(end)
        require(os.path.lexists(path) and posix._stamp(path.lstat()) == stamp, "ABI_ORIGINAL_PROVENANCE_CHANGED")
    for path in absent:
        posix._deadline(end)
        require(not os.path.lexists(path), "ABI_ORIGINAL_PROVENANCE_APPEARED")
    for parent in directories.values():
        if parent is not None:
            parent.verify()
    if canonical_directory is not None:
        require(posix_snapshot(owner, canonical_directory.path, posix.MAX_BYTES, posix.MAX_MEMBERS, end) == canonical_rows,
                "ABI_ORIGINAL_CANONICAL_TREE_CHANGED")
    require(not owner.unknown, "ABI_PROVENANCE_RETIREMENT_UNKNOWN")
    posix._deadline(end)
    return {"contextSha256": digest(run_raw), "canonicalMapSha256": None if canonical_raw is None else digest(canonical_raw),
            "originals": originals}


def frozen_abi_packet(owner, private, end):
    """Exact flat copies consumed by the real export child, not live build paths."""
    require(os.name == "posix", "PRIMARY_FULL_ABI_NATIVE_MAC_ONLY")
    frozen = owner.child(private, "frozen-evidence", end)
    snapshot = posix_snapshot(owner, frozen.path, posix.MAX_BYTES, posix.MAX_MEMBERS, end)
    map_raw = owner.read(frozen, "original-path-map.json", end)
    mapping = abi_copy_map(map_raw, private.path / "evidence")
    all_rows = mapping["files"]
    require(set(snapshot) == {"", "original-path-map.json", *[row["member"] for row in all_rows]} and
            all(stat.S_ISREG(row[2]) for name, row in snapshot.items() if name), "ABI_FROZEN_MAP_MEMBERS_CHANGED")
    accepted = {"primary-abi/manifest.json", "profile-result-before-export.json"} | {
        "primary-abi/" + abi.member(index, role) for index in range(8) for role in ("generated", "baseline")}
    rows = [row for row in all_rows if row["original"].startswith("primary-abi/") or
            row["original"] == "profile-result-before-export.json"]
    require({row["original"] for row in rows} <= accepted and
            any(row["original"] == "profile-result-before-export.json" for row in rows), "ABI_FROZEN_PACKET_ROSTER")
    originals = {}
    for row in rows:
        maximum = RECORD_LIMIT if row["original"].endswith(".json") else abi.FILE_LIMIT
        require(type(row["size"]) is int and 0 < row["size"] <= maximum, "ABI_FROZEN_PACKET_BOUND")
        raw = owner.read(frozen, row["member"], end, maximum)
        require(len(raw) == row["size"] and digest(raw) == row["sha256"], "ABI_FROZEN_PACKET_CHANGED")
        originals[row["original"]] = raw
    provenance = frozen_abi_provenance(owner, private, frozen, {row["original"]: row for row in all_rows}, end)
    require(owner.read(frozen, "original-path-map.json", end) == map_raw and
            posix_snapshot(owner, frozen.path, posix.MAX_BYTES, posix.MAX_MEMBERS, end) == snapshot, "ABI_FROZEN_MAP_CHANGED")
    manifest = originals.get("primary-abi/manifest.json")
    return {"mapSha256": digest(map_raw), "files": rows, "provenance": provenance,
            "manifestSha256": None if manifest is None else digest(manifest)}, originals


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
        self.simulator = self.simulator_admission = self.simulator_binding = self.simulator_terminal = None
        self.simulator_prelaunch = self.simulator_start = self.simulator_canonical = self.simulator_authority = None
        self.simulator_directory = None
        self.export_return = None
        self.build_owners = {}
        self.primary_abi, self.primary_abi_attempted, self.export_freeze_end = None, False, None
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
                require(label in FULL_STAGE, "FULL_JOB_CLOSED_PHASE")
                end = min(end, self.window(FULL_STAGE[label], timeout))
                final_end = min(final_end, self.window(FULL_FINISH[FULL_STAGE[label]], timeout + FINAL_SECONDS))
                raw_work_end = min(raw_started + timeout * job_time.NS, self.budget.fence(FULL_STAGE[label]))
                raw_final_end = min(raw_started + (timeout + FINAL_SECONDS) * job_time.NS,
                                    self.budget.fence(FULL_FINISH[FULL_STAGE[label]]))
        else:
            require(not acquire_time, "JOB_TIME_FULL_ONLY")
        invocation = uuid.uuid4().hex
        directory = self.child(self.commands, label, final_end, create=True)
        job = self.context["id"] if product else self.job
        state = self.state_path if product else self.path
        home = state / ("gradle-home" if product else "control-home")
        env = processes.ownership_environment(self.environment, job, invocation, str(state), str(home),
                                              allow_new_context=True)
        if self.profile == "full" and product:
            require(label == "product" and self.simulator_binding is not None, "PRIMARY_SIMULATOR_BINDING_REQUIRED")
            env.update({simulator.PATH_ENV: str(self.path / simulator.RELATIVE),
                        simulator.HASH_ENV: digest(self.simulator_binding)})
        if acquire_time:
            require(type(self.actions_token) is str and self.actions_token, "JOB_TIME_READ_TOKEN_REQUIRED")
            env[job_time.TOKEN_ENV], self.actions_token = self.actions_token, None
        row = {"schema": 1, "phase": label, "argv": list(argv), "cwd": str(ROOT), "job": job,
               "invocation": invocation, "state": str(state), "home": str(home), "exitCode": None,
               "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN", "errors": []}
        if self.profile == "full":
            row.update(jobBudgetSha256=None if self.budget is None else self.budget.sha256,
                       startedRawNs=raw_started, completedRawNs=None, finalizedRawNs=None,
                       cooperativeCancellation=None, developerDir=self.environment.get("DEVELOPER_DIR"),
                       simulatorBindingSha256=None if self.simulator_binding is None else digest(self.simulator_binding),
                       childAncestorInvocationIds=env[processes.CHAIN_ENV].split(":"))
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
            context.update(primarySimulatorRequired=True, primaryAbiRequired=True,
                           developerDir=self.environment.get("DEVELOPER_DIR"),
                           ancestorInvocationIds=self.environment.get(processes.CHAIN_ENV, "").split(":")
                           if self.environment.get(processes.CHAIN_ENV) else [])
        self.run_context_raw = encoded(context)
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
        self.canonical_context_raw = self.read(state, "context.json", self.window("productive", 30))
        self.context = parse(self.canonical_context_raw)
        require(self.context["root"] == str(ROOT) and self.context["host"] == self.role and
                self.context["gradleHome"] == str(self.state_path / "gradle-home") and
                self.context["source"] == {**original["source"], "status": "", "diffSha256": digest(b"")} and
                not self.context["preexistingOutputPaths"], "CANONICAL_CONTEXT_DIFFERS_OR_STALE_OUTPUTS")
        if self.profile == "full":
            self.admit_simulator()  # Cheap inventory BEFORE installing a custody loader or launching any product.
        # Protect original outputs BEFORE the writers, not merely copied XML.
        outputs = audit.output_roots(ROOT)
        for path in [*outputs, ROOT / ".gradle", ROOT / ".kotlin",
                     ROOT / "buildSrc/.gradle", ROOT / "buildSrc/.kotlin"]:
            self.check()
            require(not os.path.lexists(path), "PREEXISTING_OUTPUT_OR_CACHE_ROOT")
            owned = self.new(path)  # Native protected DACL + original ancestry pins on Windows.
            if path in outputs:
                self.build_owners[path] = owned
        row = self.phase("custody-prepare", self.python(SCRIPTS / "test-transcript-custody.py", "prepare",
            "--root", ROOT, "--directory", self.evidence.path / "custody", "--home", self.state_path / "gradle-home",
            "--owner-state", self.state_path, "--owner-kind", "audit", "--scope",
            "both" if self.profile == "full" else "cli", "--", *self.command), 120)
        require(row["exitCode"] == 0, "CUSTODY_PREPARE_FAILED")
        directory = self.child(self.evidence, "custody", self.window("productive", 30))
        self.request_raw = self.read(directory, "request.json", self.window("productive", 30))
        self.request = parse(self.request_raw)
        require(self.request["ownerKind"] == "audit" and self.request["owner"]["job"] == self.context["id"] and
                self.request["command"] == self.command and self.request["ownerState"] == str(self.state_path),
                "CUSTODY_RESERVATION_DIFFERS")
        if self.profile == "full":
            self.simulator_binding = simulator.binding_record(self.run_context_raw, self.canonical_context_raw,
                                                             self.request_raw, self.simulator_admission)
            self.write(self.simulator_directory, "binding.json", self.simulator_binding, self.window("productive", 30))

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
        if self.profile == "full":
            self.verify_simulator_inputs(self.window("productive", 30), require_binding=True)
            observed = self.simulator_observation(simulator.PRELAUNCH)
            self.simulator_prelaunch = simulator.prelaunch_record(self.run_context_raw, self.simulator_binding, *observed)
            self.write(self.simulator_directory, "prelaunch.json", self.simulator_prelaunch, self.window("productive", 30))
        reserved = self.request["owner"]["productInvocation"]
        require(type(reserved) is str and re.fullmatch(r"[0-9a-f]{32}", reserved), "RESERVED_INVOCATION_REQUIRED")
        wrapper = ROOT / ("gradlew.bat" if self.role == "windows-x64" else "gradlew")
        argv = self.python(SCRIPTS / "run-audit-command.py", "--cwd", ROOT, "--wrapper", wrapper,
                           "--kind", self.kind, "--purpose", "ordinary-" + self.profile, "--id", reserved,
                           "--timeout", PRODUCT_SECONDS[self.profile], "--stop-timeout", 120, "--", *self.command)
        original = None
        try:
            self.product = self.phase("product", argv, OUTER_SECONDS[self.profile], product=True)
        except BaseException as error:
            original = error
            raise
        finally:
            if self.profile == "full" and not self.unknown:
                try:
                    self.capture_simulator_authority()
                except BaseException as error:
                    self.error("simulator-launch-authority", error)
                    if original is None:
                        raise

    def simulator_observation(self, label, *, finalizing=False):
        """Closed native commands only; no writer Runtime, override UUID or new backend."""
        require(self.profile == "full" and (label in simulator.RETIRE) == finalizing, "SIMULATOR_CLOSED_PHASE")
        row = self.phase(label, simulator.command(label, self.simulator), simulator.SECONDS, finalizing=finalizing)
        stage = label + "-read" if finalizing else "productive"
        end = self.window(stage, 30)
        directory = self.child(self.commands, label, end)
        stdout, stderr = self.read(directory, "stdout.log", end), self.read(directory, "stderr.log", end)
        self.check_window(stage, end)
        require(type(row["exitCode"]) is int and row["exitCode"] == 0, "SIMULATOR_NATIVE_COMMAND_FAILED")
        return row, stdout, stderr

    def admit_simulator(self):
        self.simulator_directory = self.child(self.evidence, "simulator", self.window("productive", 30), create=True)
        observations = {}
        for label in simulator.PREPARE:
            observations[label] = self.simulator_observation(label)
            simulator.original(label, self.role, observations[label][1])
        self.simulator_admission = simulator.admission_record(self.run_context_raw, self.canonical_context_raw,
            observations, self.environment.get("DEVELOPER_DIR"))
        self.simulator = parse(self.simulator_admission)["selected"]
        self.write(self.simulator_directory, "admission.json", self.simulator_admission, self.window("productive", 30))

    def verify_simulator_inputs(self, end, *, require_binding):
        require(self.simulator is not None and self.simulator_admission is not None, "SIMULATOR_ADMISSION_REQUIRED")
        original, binding = original_simulator_inputs(self, self.private, end, binding_required=require_binding)
        require(original == self.simulator_admission and binding == self.simulator_binding and
                parse(original)["selected"] == self.simulator and
                parse(original)["developerDir"] == self.environment.get("DEVELOPER_DIR"),
                "SIMULATOR_IMMUTABLE_INPUT_CHANGED")
        if self.simulator_prelaunch is not None:
            require(original_simulator_prelaunch(self, self.private, binding, end) == self.simulator_prelaunch,
                    "SIMULATOR_PRELAUNCH_CHANGED")
        if self.simulator_authority is not None:
            row = next(row for row in self.records if row["phase"] == "product")
            start, canonical, authority = original_simulator_authority(self, self.private, binding, self.simulator_prelaunch,
                                                                       row, end)
            require((start, canonical, authority) == (self.simulator_start, self.simulator_canonical, self.simulator_authority),
                    "SIMULATOR_LAUNCH_AUTHORITY_CHANGED")

    def capture_simulator_authority(self):
        """Freeze actual started-product authority before collection can fail/change evidence."""
        row = next((row for row in self.records if row["phase"] == "product"), None)
        if row is None or not any(launch.get("created") is True for launch in row.get("ownership", {}).get("launches", [])):
            require(self.product is None or self.product.get("exitCode") != 0, "SIMULATOR_PRODUCT_NEVER_CREATED")
            return
        end = self.window("product-final", 30)
        state = self.child(self.private, "state", end)
        evidence = self.child(state, "evidence", end)
        invocation = self.child(evidence, self.request["owner"]["productInvocation"], end)
        start, canonical = self.read(invocation, "start.json", end), self.read(invocation, "receipt.json", end)
        authority = simulator.launch_authority(self.simulator_binding, self.simulator_prelaunch, start, canonical, row)
        self.check_window("product-final", end)
        # These byte strings are independent of later on-disk receipt damage.
        # They authorize only safe cleanup after this known native drain, never acceptance.
        self.simulator_start, self.simulator_canonical, self.simulator_authority = start, canonical, authority
        for name, raw in (("canonical-start.json", start), ("canonical-product.json", canonical), ("launch.json", authority)):
            self.write(self.simulator_directory, name, raw, end)
        self.check_window("product-final", end)

    def retire_simulator(self):
        if self.profile != "full" or self.simulator is None:
            return
        # Publish the in-memory UNKNOWN before any I/O. A failed/late record or
        # close cannot leave a provisional KNOWN/green simulator disposition.
        value = {"schema": 1, "scope": "PRIMARY_ORDINARY_FULL_SIMULATOR_RETIREMENT",
                 "contextSha256": self.context_hash, "admissionSha256": digest(self.simulator_admission),
                 "bindingSha256": None if self.simulator_binding is None else digest(self.simulator_binding),
                 "prelaunchSha256": None if self.simulator_prelaunch is None else digest(self.simulator_prelaunch),
                 "launchAuthoritySha256": None if self.simulator_authority is None else digest(self.simulator_authority),
                 "productAttempted": self.product_attempted, "productPhaseSha256": self.phase_hashes.get("product"),
                 "before": None, "after": None, "shutdownAttempted": False, "phases": {},
                 "status": "HOLD", "retirement": "UNKNOWN", "cleanupStatus": "UNKNOWN", "coverage": None, "errors": []}
        self.simulator_terminal = value
        first = len(self.errors)
        failure = None
        observations = {}
        try:
            self.check(finalizing=True)
            self.verify_simulator_inputs(self.window(simulator.BEFORE, 30), require_binding=self.product_attempted)
        except BaseException as error:
            failure = error
            self.error("simulator-retirement-integrity", error)
        try:
            # Evidence integrity is distinct from already established in-memory
            # cleanup authority. Never let damaged files suppress safe owned
            # retirement, and never bypass an UNKNOWN native owner.
            self.check(finalizing=True)
            observations[simulator.BEFORE] = self.simulator_observation(simulator.BEFORE, finalizing=True)
            value["before"] = simulator.terminal_device(observations[simulator.BEFORE][1], self.simulator)
            if value["before"]["state"] != "Shutdown":
                # A selected but never launched device remains externally owned.
                # Do not acquire shutdown authority just because its state changed.
                authority = None if self.simulator_authority is None else parse(self.simulator_authority)
                require(type(authority) is dict and authority.get("bindingSha256") == value["bindingSha256"] and
                        authority.get("prelaunchSha256") == value["prelaunchSha256"] and
                        authority.get("device") == self.simulator["device"],
                        "SIMULATOR_UNLAUNCHED_EXTERNAL_STATE_CHANGE")
                observations[simulator.SHUTDOWN] = self.simulator_observation(simulator.SHUTDOWN, finalizing=True)
        except BaseException as error:
            failure = failure or error
            self.error("simulator-retirement-before", error)
        finally:
            # A known failed shutdown still needs the exact terminal inventory;
            # an UNKNOWN native owner cannot authorize another child launch.
            if not self.unknown:
                try:
                    observations[simulator.AFTER] = self.simulator_observation(simulator.AFTER, finalizing=True)
                    value["after"] = simulator.terminal_device(observations[simulator.AFTER][1], self.simulator)
                    require(value["after"]["state"] == "Shutdown", "SIMULATOR_NOT_RETIRED")
                except BaseException as error:
                    failure = failure or error
                    self.error("simulator-retirement-after", error)
        value["shutdownAttempted"] = any(row["phase"] == simulator.SHUTDOWN and row["launchAttempted"]
                                         for row in self.records)
        value["phases"] = {label: simulator.phase_reference(*observed) for label, observed in observations.items()}
        value["errors"] = self.errors[first:]
        if not self.unknown and value["after"] is not None and value["after"]["state"] == "Shutdown" and \
                simulator.AFTER in observations:
            value["cleanupStatus"] = "KNOWN_SHUTDOWN"
        if failure is None and not self.unknown:
            value.update(status="KNOWN_SHUTDOWN", retirement="KNOWN")
        try:
            if not self.unknown:
                end = self.window("simulator-retirement", 30)
                if value["retirement"] == "KNOWN" and self.product_attempted and self.custody is not None and \
                        type(self.custody.get("productExitCode")) is int and self.custody["productExitCode"] == 0:
                    value["coverage"] = platform_simulator_binding(self, self.private, self.simulator_binding, end)
                self.write(self.simulator_directory, "retirement.json", value, end)
                self.check_window("simulator-retirement", end)
        except BaseException as error:
            failure = failure or error
            self.error("simulator-retirement-record", error)
        if failure is not None or self.unknown:
            value.update(status="HOLD", retirement="UNKNOWN", errors=self.errors[first:])
            self.unknown = True
            raise failure or ControllerError("SIMULATOR_RETIREMENT_UNKNOWN")

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

    def freeze_end(self):
        # B1 retention and the existing export copies share ONE local and RAW
        # window. Re-entering export never renews a separate180s allowance.
        if self.export_freeze_end is None:
            self.export_freeze_end = self.window("export-freeze", 180)
        self.check_window("export-freeze", self.export_freeze_end)
        return self.export_freeze_end

    def retain_primary_abi(self):
        if self.profile != "full" or self.request is None or not self.product_attempted:
            return
        self.check(finalizing=True)
        require(not self.primary_abi_attempted, "ABI_PRIMARY_RETENTION_IS_ONE_SHOT")
        self.primary_abi_attempted = True
        self.primary_abi = {"status": "HOLD", "manifestSha256": None, "contextSha256": self.context_hash,
                            "productPhaseSha256": self.phase_hashes.get("product"), "generatedCount": None}
        end = self.freeze_end()
        target = self.child(self.evidence, "primary-abi", end, create=True)
        # Every generated byte is separately acquired BEFORE reference reads and
        # before any future supplemental writer. A baseline is never a fallback.
        generated, acquisition = retain_abi_generated(self, target, self.build_owners, end)

        def check():
            self.check(finalizing=True)
            self.check_window("export-freeze", end)

        references, queries = abi_references(self, parse(self.admitted.record)["source"]["commit"],
            self.evidence.path / "primary-abi-queries", end, check)
        for index, (_blob, raw) in references.items():
            self.write(target, abi.member(index, "baseline"), raw, end)
        context_raw = self.read(self.private, "run-context.json", end)
        require(context_raw == self.run_context_raw, "ABI_CONTEXT_CHANGED")
        primary, log = primary_abi_inputs(self, self.private, parse(context_raw), end)
        require(primary["productPhaseSha256"] == self.phase_hashes.get("product"), "ABI_PRIMARY_PHASE_CHANGED")
        raw = encoded({"schema": 1, "scope": "PRIMARY_FULL_ABI_ORIGINALS", "source": parse(context_raw)["source"],
                       "contextSha256": self.context_hash, "primary": primary, "referenceQueries": queries,
                       "acquisition": acquisition, "assessment": abi.assess(generated, references, log)})
        self.write(target, "manifest.json", raw, end)
        check()  # A late/failed write keeps the earlier HOLD, not a provisional pass.
        self.primary_abi = abi_disposition(raw)

    def export(self):
        self.check(finalizing=True)
        require(self.admitted is not None and hasattr(self, "recipient_raw"), "NO_VALIDATED_RECIPIENT")
        end = self.freeze_end()
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
            value["primaryAbi"] = self.primary_abi
            value["simulator"] = {"admissionSha256": None if self.simulator_admission is None else
                                  digest(self.simulator_admission),
                                  "bindingSha256": None if self.simulator_binding is None else digest(self.simulator_binding),
                                  "selected": self.simulator, "terminal": self.simulator_terminal}
        value["profilePassed"] = profile_passed(value)
        return parse(encoded(value))


def profile_passed(value):
    """A boolean label cannot overrule original phase/custody outcomes."""
    rows = value["phases"]
    labels = ["recipient-validation", "audit-init", "custody-prepare", "product", "custody-collect",
              "custody-uninstall"]
    if value.get("profile") == "full":
        retained = value.get("primaryAbi")
        if not (type(retained) is dict and set(retained) == {"status", "manifestSha256", "contextSha256",
                "productPhaseSha256", "generatedCount"} and retained["status"] == "PASS" and
                type(retained["generatedCount"]) is int and retained["generatedCount"] == 8 and
                retained["contextSha256"] == value.get("contextSha256") and
                retained["productPhaseSha256"] == value.get("phaseSha256", {}).get("product") and
                all(type(retained[key]) is str and re.fullmatch(r"[0-9a-f]{64}", retained[key]) for key in
                    ("manifestSha256", "contextSha256", "productPhaseSha256"))):
            return False
        owned = value.get("simulator")
        if not simulator_profile_passed(value, owned):
            return False
        labels = ["job-time", "recipient-validation", "audit-init", *simulator.PREPARE,
                  "custody-prepare", simulator.PRELAUNCH, "product", "custody-collect", "custody-uninstall", simulator.BEFORE]
        if owned["terminal"]["shutdownAttempted"]:
            labels.append(simulator.SHUTDOWN)
        labels.append(simulator.AFTER)
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
            if row["phase"] in {"recipient-validation", "audit-init", "custody-prepare", "product",
                                 *simulator.PREPARE, simulator.PRELAUNCH} and not (
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


def simulator_profile_passed(result, owned):
    """No Boolean simulator label substitutes for original phase/Property proof."""
    if type(owned) is not dict or set(owned) != {"admissionSha256", "bindingSha256", "selected", "terminal"}:
        return False
    terminal = owned["terminal"]
    if not (type(terminal) is dict and terminal.get("status") == "KNOWN_SHUTDOWN" and
            terminal.get("cleanupStatus") == "KNOWN_SHUTDOWN" and
            all(type(terminal.get(key)) is str and re.fullmatch(r"[0-9a-f]{64}", terminal[key]) for key in
                ("prelaunchSha256", "launchAuthoritySha256")) and
            terminal.get("retirement") == "KNOWN" and terminal.get("errors") == [] and
            terminal.get("productAttempted") is True and terminal.get("contextSha256") == result.get("contextSha256") and
            terminal.get("admissionSha256") == owned["admissionSha256"] and
            terminal.get("bindingSha256") == owned["bindingSha256"] and
            all(type(owned.get(key)) is str and re.fullmatch(r"[0-9a-f]{64}", owned[key])
                for key in ("admissionSha256", "bindingSha256")) and
            terminal.get("productPhaseSha256") == result.get("phaseSha256", {}).get("product") and
            terminal.get("productPhaseSha256") is not None and type(terminal.get("shutdownAttempted")) is bool and
            type(terminal.get("coverage")) is dict and terminal["coverage"].get("status") == "BOUND" and
            terminal["coverage"].get("bindingSha256") == owned["bindingSha256"]):
        return False
    try:
        selected = owned["selected"]
        if selected["device"]["state"] != "Shutdown" or simulator.descriptor(selected["device"]) != selected["device"]:
            return False
        before, after = terminal["before"], terminal["after"]
        for observed in (before, after):
            if simulator.descriptor(observed) != observed or any(observed[key] != value
                    for key, value in selected["device"].items() if key != "state"):
                return False
        if after["state"] != "Shutdown" or terminal["shutdownAttempted"] != (before["state"] != "Shutdown"):
            return False
        labels = {simulator.BEFORE, simulator.AFTER} | ({simulator.SHUTDOWN} if terminal["shutdownAttempted"] else set())
        return set(terminal["phases"]) == labels and all(terminal["phases"][label]["phaseSha256"] ==
            result["phaseSha256"][label] for label in labels)
    except (KeyError, TypeError, ValueError):
        return False


def original_simulator_inputs(owner, private, end, *, binding_required):
    """Reconstruct admission from ORIGINAL native stdout/phase bytes, not labels."""
    run_raw = owner.read(private, "run-context.json", end)
    state = owner.child(private, "state", end)
    canonical_raw = owner.read(state, "context.json", end)
    evidence = owner.child(private, "evidence", end)
    directory = owner.child(evidence, "simulator", end)
    raw = owner.read(directory, "admission.json", end)
    commands = owner.child(evidence, "commands", end)
    observations = {}
    for label in simulator.PREPARE:
        phase = owner.child(commands, label, end)
        phase_raw = owner.read(phase, "result.json", end)
        row = parse(phase_raw)
        require(phase_raw == encoded(row), "SIMULATOR_ORIGINAL_PHASE_ENCODING_CHANGED")
        observations[label] = row, owner.read(phase, "stdout.log", end), owner.read(phase, "stderr.log", end)
    expected = simulator.admission_record(run_raw, canonical_raw, observations, parse(run_raw).get("developerDir"))
    require(raw == expected, "SIMULATOR_ADMISSION_ORIGINALS_CHANGED")
    binding = None
    if binding_required or os.path.lexists(private.path / simulator.RELATIVE):
        custody = owner.child(evidence, "custody", end)
        request_raw = owner.read(custody, "request.json", end)
        binding = owner.read(directory, "binding.json", end)
        require(binding == simulator.binding_record(run_raw, canonical_raw, request_raw, raw),
                "SIMULATOR_PRIMARY_BINDING_CHANGED")
    return raw, binding


def platform_simulator_binding(owner, private, binding_raw, end):
    """Inspect the actual canonical-retained platform invocation/execution/summary.

    The canonical product still calls the unchanged full selector. This adds a
    receipt for its KGP Property proof, not a second product or fake ABI/test run.
    """
    require(binding_raw is not None, "SIMULATOR_PLATFORM_BINDING_REQUIRED")
    binding = parse(binding_raw)
    state = owner.child(private, "state", end)
    evidence = owner.child(state, "evidence", end)
    invocation = owner.child(evidence, binding["productInvocation"], end)
    canonical_raw = owner.read(invocation, "receipt.json", end)
    canonical = parse(canonical_raw)
    start_raw = owner.read(invocation, "start.json", end)
    simulator.canonical_start(binding_raw, start_raw, canonical.get("ancestorInvocationIds"), canonical.get("controllerPid"))
    prelaunch_raw = original_simulator_prelaunch(owner, private, binding_raw, end)
    require(canonical.get("id") == binding["productInvocation"] and canonical.get("jobId") == binding["job"] and
            canonical.get("kind") == "command" and canonical.get("requestedArgv") ==
            ["python3", "scripts/run-platform-tests.py", "full"] and canonical.get("sourceBefore") ==
            canonical.get("sourceAfter") == binding["source"] and canonical.get("sourceUnchanged") is True,
            "SIMULATOR_PLATFORM_CANONICAL_BINDING")
    reports = canonical.get("reports")
    require(type(reports) is list and len(reports) <= posix.MAX_MEMBERS and
            all(type(row) is dict for row in reports), "SIMULATOR_PLATFORM_REPORT_MAP")
    manifest = parse(owner.read(invocation, "report-manifest.json", end))
    require(manifest.get("schema") == 1 and manifest.get("records") == reports, "SIMULATOR_PLATFORM_REPORT_MAP_CHANGED")
    selected = {}
    tokens = set()
    for row in reports:
        match = re.fullmatch(r"build/reports/platform-tests/([0-9a-f]{32})/(invocation|execution|summary)\.json",
                             row.get("source", ""))
        if match is None:
            continue
        token, name = match.groups()
        require(name not in selected and row.get("classification") == "changed-since-admission" and
                row.get("retained") == "reports/" + row["source"], "SIMULATOR_PLATFORM_REPORT_REUSED_OR_DUPLICATE")
        selected[name] = row
        tokens.add(token)
    require(set(selected) == {"invocation", "execution", "summary"} and len(tokens) == 1,
            "SIMULATOR_CURRENT_PLATFORM_REPORTS_MISSING")
    token = next(iter(tokens))
    directory = invocation
    for name in ("reports", "build", "reports", "platform-tests", token):
        directory = owner.child(directory, name, end)
    raw, values = {}, {}
    for name, row in selected.items():
        raw[name] = owner.read(directory, name + ".json", end)
        require(row.get("sha256") == digest(raw[name]) and type(row.get("bytes")) is int and
                row["bytes"] == len(raw[name]), "SIMULATOR_PLATFORM_REPORT_BYTES_CHANGED")
        values[name] = parse(raw[name])
    source, execution, summary = (values[name] for name in ("invocation", "execution", "summary"))
    identity = simulator.assess_coverage(execution, binding_raw, start_raw, prelaunch_raw)
    for value in (source, summary):
        require(value.get("profile") == "full" and value.get("token") == token and
                all(value.get(key) == expected for key, expected in binding["source"].items()) and
                value.get("ordinarySimulator") == identity, "SIMULATOR_PLATFORM_INVOCATION_CHANGED")
    require(execution.get("token") == token and execution.get("buildFailed") is False and execution.get("dryRun") is False and
            summary.get("sourceAfter") == binding["source"] and summary.get("result") == "PASS" and
            summary.get("errors") == [] and type(summary.get("gradleExitCode")) is int and summary["gradleExitCode"] == 0 and
            type(summary.get("stopExitCode")) is int and summary["stopExitCode"] == 0 and
            source.get("command") == summary.get("command"), "SIMULATOR_PLATFORM_NOT_PASSED")
    command = source.get("command", [])
    require(type(command) is list and command[:2] == [str(ROOT / "gradlew"), "check"] and
            "-Pp2pkit.ordinarySimulatorBinding=" + str(private.path / simulator.RELATIVE) in command and
            "-Pp2pkit.ordinarySimulatorSha256=" + digest(binding_raw) in command and
            "-Pp2pkit.ordinarySimulatorStartSha256=" + digest(start_raw) in command and
            "-Pp2pkit.ordinarySimulatorPrelaunchSha256=" + digest(prelaunch_raw) in command,
            "SIMULATOR_PLATFORM_SELECTOR_CHANGED")
    return {"status": "BOUND", **identity, "token": token, "canonicalReceiptSha256": digest(canonical_raw),
            "reportsSha256": {name: digest(data) for name, data in raw.items()}}


def original_simulator_prelaunch(owner, private, binding_raw, end):
    evidence = owner.child(private, "evidence", end)
    directory = owner.child(evidence, "simulator", end)
    commands = owner.child(evidence, "commands", end)
    phase = owner.child(commands, simulator.PRELAUNCH, end)
    raw = owner.read(phase, "result.json", end)
    row = parse(raw)
    require(raw == encoded(row), "SIMULATOR_PRELAUNCH_PHASE_ENCODING_CHANGED")
    expected = simulator.prelaunch_record(owner.read(private, "run-context.json", end), binding_raw, row,
                                          owner.read(phase, "stdout.log", end), owner.read(phase, "stderr.log", end))
    require(owner.read(directory, "prelaunch.json", end) == expected, "SIMULATOR_PRELAUNCH_ORIGINALS_CHANGED")
    return expected


def original_simulator_authority(owner, private, binding_raw, prelaunch_raw, outer, end):
    state = owner.child(private, "state", end)
    canonical_evidence = owner.child(state, "evidence", end)
    invocation = owner.child(canonical_evidence, parse(binding_raw)["productInvocation"], end)
    start, canonical = owner.read(invocation, "start.json", end), owner.read(invocation, "receipt.json", end)
    authority = simulator.launch_authority(binding_raw, prelaunch_raw, start, canonical, outer)
    evidence = owner.child(private, "evidence", end)
    directory = owner.child(evidence, "simulator", end)
    for name, raw in (("canonical-start.json", start), ("canonical-product.json", canonical), ("launch.json", authority)):
        require(owner.read(directory, name, end) == raw, "SIMULATOR_LAUNCH_ORIGINALS_CHANGED")
    return start, canonical, authority


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
            abi_frozen = frozen_abi_packet(owner, private, end)[0] if profile == "full" else None
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
                if profile == "full":
                    require(frozen_abi_packet(owner, private, end)[0] == abi_frozen, "ABI_CHANGED_DURING_ORIGINAL_EXPORT")
                    exported["primaryAbiFrozen"] = abi_frozen
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
            for name in ("collect", "retire_simulator", "retain_primary_abi", "export"):
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
    require(type(result["phases"]) is list and len(result["phases"]) <= (len(FULL_STAGE) + 1 if budget is not None else 7) and
            len({row["phase"] for row in result["phases"]}) == len(result["phases"]), "PHASE_SET_CHANGED")
    require(set(result["phaseSha256"]) == {row["phase"] for row in result["phases"]}, "PHASE_BINDING_SET")
    if budget is not None:
        labels = [row["phase"] for row in result["phases"]]
        preparation = [label for label in labels if label in FULL_PREPARATION]
        require(all(label in FULL_ORDER for label in labels) and labels and labels[-1] == "export" and
                labels == sorted(labels, key=FULL_ORDER.index) and preparation and
                preparation == list(FULL_PREPARATION[:len(preparation)]) and
                ("custody-collect" not in labels or "custody-prepare" in preparation) and
                ("custody-uninstall" not in labels or "custody-collect" in labels), "PHASE_SEQUENCE_CHANGED")
    previous_raw = None
    for row in result["phases"]:
        label = row["phase"]
        allowed = set(FULL_STAGE) | {"job-time"} if budget is not None else {
            "recipient-validation", "audit-init", "custody-prepare", "product", "custody-collect", "custody-uninstall", "export"}
        require(label in allowed, "PHASE_LABEL")
        directory = owner.child(commands, label, end)
        raw = owner.read(directory, "result.json", end)
        require(digest(raw) == result["phaseSha256"][label] and parse(raw) == row and row["cwd"] == str(ROOT),
                "ORIGINAL_PHASE_CHANGED")
        if budget is not None:
            start = parse(owner.read(directory, "start.json", end))
            require(all(start[key] == row[key] for key in ("phase", "argv", "cwd", "job", "invocation", "state", "home",
                         "jobBudgetSha256", "startedRawNs", "developerDir", "simulatorBindingSha256",
                         "childAncestorInvocationIds")), "PHASE_RAW_START_CHANGED")
            require(row["developerDir"] == context.get("developerDir"), "PHASE_DEVELOPER_DIR_CHANGED")
            require(row["childAncestorInvocationIds"] == context["ancestorInvocationIds"] + [row["invocation"]],
                    "PHASE_NATIVE_ANCESTORS_CHANGED")
            require(type(row.get("startedRawNs")) is int and type(row.get("finalizedRawNs")) is int and
                    0 <= row["startedRawNs"] <= row["finalizedRawNs"] <= job_time.UINT64,
                    "PHASE_RAW_INTERVAL_CHANGED")
            require(previous_raw is None or previous_raw <= row["startedRawNs"], "PHASE_RAW_SEQUENCE_CHANGED")
            previous_raw = row["finalizedRawNs"]
            if row.get("completedRawNs") is not None:
                require(type(row["completedRawNs"]) is int and
                        row["startedRawNs"] <= row["completedRawNs"] <= row["finalizedRawNs"], "PHASE_RAW_INTERVAL_CHANGED")
            if label != "job-time":
                require(row["jobBudgetSha256"] == budget.sha256 and
                        row["startedRawNs"] < budget.fence(FULL_STAGE[label]) and
                        row["finalizedRawNs"] < budget.fence(FULL_FINISH[FULL_STAGE[label]]), "PHASE_JOB_TIME_CHANGED")
            if label != "product":
                require(row["job"] == context["job"] and row["state"] == context["session"] and
                        row["home"] == context["session"] + "/control-home", "PHASE_CONTROLLER_DOMAIN_CHANGED")
            if label in (*simulator.PREPARE, simulator.PRELAUNCH, *simulator.RETIRE):
                require(row["argv"] == simulator.command(label, result.get("simulator", {}).get("selected")),
                        "SIMULATOR_FIXED_COMMAND_CHANGED")
                require(row["finalizedRawNs"] < row["startedRawNs"] +
                        (simulator.SECONDS + FINAL_SECONDS) * job_time.NS and
                        (row["completedRawNs"] is None or row["completedRawNs"] < min(
                            row["startedRawNs"] + simulator.SECONDS * job_time.NS,
                            budget.fence(FULL_STAGE[label]))), "SIMULATOR_PHASE_BOUND_CHANGED")
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
                previous_raw is not None and previous_raw <= timing["terminalRawNs"] and
                type(timing.get("exhausted")) is bool, "SEALED_JOB_BUDGET_CHANGED")
        cutoff = timing.get("cutoffObservation")
        if timing["exhausted"]:
            require(type(cutoff) is dict and set(cutoff) == {"phase", "observedRawNs"} and
                    cutoff["phase"] in {"admission", "recipient-validation", "audit-init", "custody-prepare", "product",
                                        *simulator.PREPARE, simulator.PRELAUNCH} and
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
        verify_simulator_bindings(owner, private, result, context, end)


def verify_abi_acquisition(value, generated):
    """Frozen acquisition stamps, never newly adopted/supplemental build outputs."""
    require(type(value) is dict and set(value) == {"roots", "files"} and type(value["roots"]) is list and
            type(value["files"]) is list and len(value["files"]) == 8, "ABI_ACQUISITION_ROSTER")
    groups = list(dict.fromkeys((module, path.split("/", 1)[0]) for module, path, *_rest in abi.ROUTES))
    require(len(value["roots"]) == len(groups), "ABI_ACQUISITION_ROOTS")

    def stamp(row, directory, size=None):
        require(type(row) is list and len(row) == 8 and all(type(part) is int and part >= 0 for part in row) and
                row[3] == os.getuid() and not row[2] & 0o022 and
                (stat.S_ISDIR(row[2]) if directory else stat.S_ISREG(row[2]) and row[4] == 1 and row[5] == size),
                "ABI_ACQUISITION_STAMP")

    for row, (module, subtree) in zip(value["roots"], groups):
        build = "library/" + module + "/build"
        require(type(row) is dict and set(row) == {"root", "buildRoot", "buildIdentity", "ancestors"} and
                row["root"] == build + "/kotlin/" + subtree and row["buildRoot"] == build and
                type(row["buildIdentity"]) is list and len(row["buildIdentity"]) == 2 and
                all(type(part) is int and part >= 0 for part in row["buildIdentity"]), "ABI_ACQUISITION_ROOT_IDENTITY")
        indices = [index for index, route in enumerate(abi.ROUTES) if route[0] == module and route[1].split("/", 1)[0] == subtree]
        ancestors = row["ancestors"]
        if ancestors is None:
            require(all(generated[index] is None and value["files"][index] is None for index in indices),
                    "ABI_MISSING_ORIGINAL_RELABELLED")
        else:
            require(type(ancestors) is dict and set(ancestors) == {"kotlin", "kotlin/" + subtree}, "ABI_ANCESTOR_STAMPS")
            for entry in ancestors.values():
                stamp(entry, True)
            for index in indices:
                require(generated[index] is not None, "ABI_GENERATED_ROLE_MISSING")
                stamp(value["files"][index], False, len(generated[index]))


def verify_primary_abi_bindings(owner, private, result, context, end, check):
    """Reassess from original producer and frozen primary bytes, without rebuilding."""
    require(context.get("primaryAbiRequired") is True, "SEALED_PRIMARY_ABI_REQUIRED")
    bound, frozen = frozen_abi_packet(owner, private, end)
    require(bound == result["exportReturn"]["result"].get("primaryAbiFrozen"), "ABI_ORIGINAL_EXPORT_BINDING_CHANGED")
    before = parse(frozen["profile-result-before-export.json"])
    disposition = result.get("primaryAbi")
    require(before.get("primaryAbi") == disposition and before.get("source") == context["source"] and
            before.get("contextSha256") == result["contextSha256"], "ABI_FROZEN_PROFILE_CHANGED")
    names = {name.removeprefix("primary-abi/") for name in frozen if name.startswith("primary-abi/")}
    evidence = owner.child(private, "evidence", end)
    if disposition is None:
        require(result["productAttempted"] is False and not names and
                not os.path.lexists(evidence.path / "primary-abi"), "ABI_UNATTEMPTED_RELABELLED")
        require(frozen_abi_packet(owner, private, end)[0] == bound, "ABI_POST_RETURN_PACKET_CHANGED")
        check()
        return
    original = owner.child(evidence, "primary-abi", end)
    rows = posix_snapshot(owner, original.path, 2 * abi.TOTAL_LIMIT + RECORD_LIMIT, 18, end)
    require(set(rows) == {"", *names}, "ABI_RETAINED_PACKET_ROSTER_CHANGED")
    for name in names:
        raw = owner.read(original, name, end, RECORD_LIMIT if name == "manifest.json" else abi.FILE_LIMIT)
        require(raw == frozen["primary-abi/" + name], "ABI_FROZEN_ORIGINAL_DIFFERS")

    def final_integrity():
        # A retained failed/partial product has the same final integrity fence;
        # HOLD is not permission to encrypt/accept changed primary originals.
        require(posix_snapshot(owner, original.path, 2 * abi.TOTAL_LIMIT + RECORD_LIMIT, 18, end) == rows and
                frozen_abi_packet(owner, private, end)[0] == bound, "ABI_POST_RETURN_PACKET_CHANGED")
        check()

    raw = frozen.get("primary-abi/manifest.json")
    if raw is None:
        # Safe partial failure retention, never regenerated evidence or a pass.
        require(disposition == {"status": "HOLD", "manifestSha256": None, "contextSha256": result["contextSha256"],
                "productPhaseSha256": result["phaseSha256"].get("product"), "generatedCount": None} and
                result.get("errors"), "ABI_INCOMPLETE_RETENTION_RELABELLED")
        final_integrity()
        return
    manifest = parse(raw)
    require(raw == encoded(manifest) and set(manifest) == {"schema", "scope", "source", "contextSha256", "primary",
            "referenceQueries", "acquisition", "assessment"} and manifest["schema"] == 1 and
            manifest["scope"] == "PRIMARY_FULL_ABI_ORIGINALS" and manifest["source"] == context["source"] and
            manifest["contextSha256"] == result["contextSha256"] and disposition == abi_disposition(raw),
            "ABI_MANIFEST_BINDING_CHANGED")
    references, _queries = abi_references(owner, context["source"]["commit"], private.path / "seal-primary-abi-queries", end, check)
    query_directory = owner.child(evidence, "primary-abi-queries", end)
    query_raw = owner.read(query_directory, "session-result.json", end, query.MAX_RECEIPT_BYTES)
    require(manifest["referenceQueries"] == {"bytes": len(query_raw), "sha256": digest(query_raw)},
            "ABI_ORIGINAL_REFERENCE_QUERIES_CHANGED")
    generated = {}
    for index in range(8):
        generated[index] = frozen.get("primary-abi/" + abi.member(index, "generated"))
        require(frozen.get("primary-abi/" + abi.member(index, "baseline")) == references[index][1],
                "ABI_FROZEN_REFERENCE_DIFFERS_FROM_SOURCE")
    primary, log = primary_abi_inputs(owner, private, context, end)
    require(primary == manifest["primary"] and primary["productPhaseSha256"] == result["phaseSha256"].get("product") and
            manifest["assessment"] == abi.assess(generated, references, log), "ABI_ORIGINAL_ASSESSMENT_CHANGED")
    verify_abi_acquisition(manifest["acquisition"], generated)
    final_integrity()


def verify_simulator_bindings(owner, private, result, context, end):
    """Independent post-return ownership fence, also for known failed products."""
    owned = result.get("simulator")
    require(context.get("primarySimulatorRequired") is True and type(owned) is dict and set(owned) ==
            {"admissionSha256", "bindingSha256", "selected", "terminal"}, "SEALED_SIMULATOR_REQUIRED")
    if owned["selected"] is None:
        require(owned == {"admissionSha256": None, "bindingSha256": None, "selected": None, "terminal": None} and
                result["productAttempted"] is False and not any(row["phase"] in {"product", *simulator.RETIRE}
                    for row in result["phases"]) and not os.path.lexists(private.path / simulator.RELATIVE),
                "SEALED_UNADMITTED_SIMULATOR_PRODUCT")
        return  # Original known admission failure may be retained, but cannot pass the profile.
    original, binding = original_simulator_inputs(owner, private, end, binding_required=result["productAttempted"])
    require(digest(original) == owned["admissionSha256"] and parse(original)["selected"] == owned["selected"] and
            (None if binding is None else digest(binding)) == owned["bindingSha256"], "SEALED_SIMULATOR_INPUT_CHANGED")
    evidence = owner.child(private, "evidence", end)
    directory = owner.child(evidence, "simulator", end)
    terminal = parse(owner.read(directory, "retirement.json", end))
    require(terminal == owned["terminal"] and terminal.get("schema") == 1 and
            terminal.get("scope") == "PRIMARY_ORDINARY_FULL_SIMULATOR_RETIREMENT" and
            terminal.get("contextSha256") == result["contextSha256"] and
            terminal.get("admissionSha256") == owned["admissionSha256"] and
            terminal.get("bindingSha256") == owned["bindingSha256"] and terminal.get("status") == "KNOWN_SHUTDOWN" and
            terminal.get("cleanupStatus") == "KNOWN_SHUTDOWN" and
            terminal.get("retirement") == "KNOWN" and terminal.get("errors") == [] and
            terminal.get("productAttempted") is result["productAttempted"] and
            terminal.get("productPhaseSha256") == result["phaseSha256"].get("product"), "SEALED_SIMULATOR_TERMINAL_CHANGED")
    product = next((row for row in result["phases"] if row["phase"] == "product"), None)
    if result["productAttempted"]:
        bound = parse(binding)
        expected = canonical_python(context["python"], context["canonicalSources"], "--cwd", str(ROOT),
            "--wrapper", str(ROOT / "gradlew"), "--kind", "command", "--purpose", "ordinary-full", "--id",
            bound["productInvocation"], "--timeout", str(PRODUCT_SECONDS["full"]), "--stop-timeout", "120", "--",
            *context["command"])
        require(type(product) is dict and product["launchAttempted"] is True and product["argv"] == expected and
                product["job"] == bound["job"] and product["state"] == bound["state"] and product["home"] == bound["home"] and
                product["simulatorBindingSha256"] == digest(binding), "SEALED_SIMULATOR_LAUNCH_AUTHORITY_CHANGED")
    else:
        require(product is None or product["launchAttempted"] is False, "SEALED_SIMULATOR_LAUNCH_AUTHORITY_CHANGED")
    prelaunch = None
    if terminal.get("prelaunchSha256") is not None:
        prelaunch = original_simulator_prelaunch(owner, private, binding, end)
        require(digest(prelaunch) == terminal["prelaunchSha256"], "SEALED_SIMULATOR_PRELAUNCH_CHANGED")
    if terminal.get("launchAuthoritySha256") is not None:
        require(product is not None and prelaunch is not None, "SEALED_SIMULATOR_LAUNCH_AUTHORITY_MISSING")
        _start, _canonical, authority = original_simulator_authority(owner, private, binding, prelaunch, product, end)
        require(digest(authority) == terminal["launchAuthoritySha256"], "SEALED_SIMULATOR_LAUNCH_AUTHORITY_CHANGED")
    else:
        require(terminal.get("shutdownAttempted") is False, "SEALED_SIMULATOR_SHUTDOWN_WITHOUT_LAUNCH")
    commands = owner.child(evidence, "commands", end)
    references, observed = {}, {}
    for row in result["phases"]:
        label = row["phase"]
        if label not in simulator.RETIRE:
            continue
        require(row["exitCode"] == 0 and type(row["exitCode"]) is int and row["retirement"] == "KNOWN" and
                row["launchAttempted"] is True and row["errors"] == [] and row["simulatorBindingSha256"] ==
                owned["bindingSha256"], "SEALED_SIMULATOR_RETIREMENT_PHASE_FAILED")
        phase = owner.child(commands, label, end)
        stdout, stderr = owner.read(phase, "stdout.log", end), owner.read(phase, "stderr.log", end)
        references[label] = simulator.phase_reference(row, stdout, stderr)
        if label != simulator.SHUTDOWN:
            observed[label] = simulator.terminal_device(stdout, owned["selected"])
    require(terminal.get("phases") == references and set(observed) == {simulator.BEFORE, simulator.AFTER} and
            terminal["before"] == observed[simulator.BEFORE] and terminal["after"] == observed[simulator.AFTER] and
            terminal["after"]["state"] == "Shutdown" and type(terminal.get("shutdownAttempted")) is bool and
            terminal["shutdownAttempted"] == (simulator.SHUTDOWN in references) == (terminal["before"]["state"] != "Shutdown") and
            (result["productAttempted"] or terminal["shutdownAttempted"] is False), "SEALED_SIMULATOR_RETIREMENT_CHANGED")
    if result["productAttempted"] and type(result["custody"]) is dict and result["custody"].get("productExitCode") == 0:
        require(terminal.get("coverage") == platform_simulator_binding(owner, private, binding, end),
                "SEALED_SIMULATOR_PROPERTY_EVIDENCE_CHANGED")
    else:
        require(terminal.get("coverage") is None, "SEALED_UNEXECUTED_SIMULATOR_COVERAGE")


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
        if profile == "full":
            verify_primary_abi_bindings(owner, private, result, context, end,
                                       lambda: (posix._deadline(end), budget_clock.check("seal")))
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
