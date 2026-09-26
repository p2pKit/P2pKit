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
import application_release_version as sample_version
import audit_processes as processes
import hosted_dependency_cache as cache
import hosted_dependency_seed_files as seed
import hosted_full_job_budget as job_time
import hosted_full_simulator as simulator
import hosted_full_supplements as supplements
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
SAMPLE_SCOPE = {"kind": "DEVELOPMENT_SAMPLE_BUILD_ARTIFACTS", "productionSigning": "NOT_REQUESTED_OR_VERIFIED",
                "desktopInstaller": True, "installationTest": "NOT_PERFORMED", "signatureVerification": "NOT_PERFORMED",
                "appLaunch": "NOT_PERFORMED", "networkRuntime": "NOT_PERFORMED",
                "physicalDeviceQualification": "NOT_PERFORMED"}
SAMPLE_INSTALLER_INSPECTION = "Native version metadata and byte hashes; not installed or signature-verified"
# This is deliberately NOT the old whole-job 30-minute allowance. A Windows
# NativeFile's original lifetime cannot exceed 900s. Keep the product + canonical
# stop + outer retirement/receipt envelope below it; a timeout remains a failure.
PRODUCT_SECONDS = {"full": 7200, "desktop": 600}
OUTER_SECONDS = {"full": 7530, "desktop": 825}
TOTAL_SECONDS = {"full": 8400, "desktop": 1500}
FULL_STAGE = {"recipient-validation": "productive", "audit-init": "productive",
              "custody-prepare": "productive", "product": "product-return", "custody-collect": "collect",
              "custody-uninstall": "uninstall", "export": "export",
              "sample-packaging": "controller-return",
              **{label: "productive" for label in (*simulator.PREPARE, simulator.PRELAUNCH)},
              **{label: label for label in simulator.RETIRE}, **supplements.STAGES}
FULL_FINISH = {"productive": "preparation-final", "product-return": "product-final", "collect": "collect-final",
               "uninstall": "uninstall-final", "export": "export-final",
               "controller-return": "controller-return",
               **{label: label + "-final" for label in simulator.RETIRE}}
FULL_PREPARATION = ("job-time", "recipient-validation", "audit-init", *simulator.PREPARE,
                    "custody-prepare", simulator.PRELAUNCH, "product")
FULL_ORDER = (*FULL_PREPARATION, "custody-collect", "custody-uninstall", *simulator.RETIRE, *supplements.ORDER, "export")
DESKTOP_ORDER = ("job-time", "recipient-validation", "audit-init", "custody-prepare", "product",
                 "custody-collect", "custody-uninstall", "sample-packaging", "export")
IDENTITY_ENV = (
    "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_REF", "GITHUB_RUN_ID",
    "GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA",
    "GITHUB_WORKSPACE", "GITHUB_EVENT_PATH", "GITHUB_SERVER_URL", "GITHUB_API_URL", "GITHUB_JOB",
    "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME", "RUNNER_ENVIRONMENT", "RUNNER_TEMP", "ImageOS", "ImageVersion",
)

# Only these two exact, source-bound siblings enter the isolated canonical
# interpreter. Do not restore the script directory or ambient PYTHONPATH: the
# canonical supplier imports audit_processes without adding its own directory.
# Separately reviewed source binding: never load this helper via a module cache,
# SourceFileLoader or ambient import path. It contains no non-stdlib imports.
_CANONICAL_HELPER_SHA256 = "432c06f0be8f98db286979b7adc58365d9eafde739c023ac13af1f227acaeba4"
_CANONICAL_HELPER_LIMIT = 32 * 1024


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


def check_cancelled(cancelled):
    if cancelled:
        raise KeyboardInterrupt("ORDINARY_TEST_CONTROLLER_CANCELLED")


def guarded_operation(function, *args, **kwargs):
    """Own CLI signal handlers before allocation; finalizers retain first failure.

    Provisional outputs are not authority if handler restoration or the last
    cancellation check fails. Every workflow consumer requires step success.
    """
    handlers, cancelled, original = {}, [], None
    try:
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handlers[number] = signal.getsignal(number)
            signal.signal(number, lambda signum, _frame: cancelled.append(signum))
        function(*args, cancelled=cancelled, **kwargs)
        check_cancelled(cancelled)
    except BaseException as error:
        original = error
    finally:
        for number, handler in handlers.items():
            try:
                signal.signal(number, handler)
            except BaseException as error:
                if original is None:
                    original = error
                else:
                    seed._note(original, "signal-restoration", error)
    if original is not None:
        raise original
    check_cancelled(cancelled)


def original_clock(budget, *observations):
    """Carry every validated predecessor's high-water mark across processes."""
    first = budget.value["responseFinishedRawNs"]
    require(all(type(value) is int and first <= value <= job_time.UINT64 for value in observations),
            "ORIGINAL_CLOCK_OBSERVATION")
    clock = job_time.BudgetClock(budget)
    clock.last = max((first, *observations))
    return clock


def _canonical_source(name, maximum):
    """Read a closed source sibling, never cached bytecode or an ambient alias.

    This is bounded source-byte inspection, not native/source/host admission or
    an atomic filesystem snapshot. A failed close cannot publish helper code.
    """
    require(type(name) is str and name in ("hosted_canonical_python.py", "audit_processes.py", "run-audit-command.py") and
            type(maximum) is int and 0 < maximum <= 512 * 1024, "CANONICAL_HELPER_SOURCE")
    path = SCRIPTS / name
    require(path.is_absolute() and ".." not in path.parts, "CANONICAL_HELPER_SOURCE")
    ancestors = [(parent, parent.lstat()) for parent in path.parents]
    require(all(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400
                for _, info in ancestors), "CANONICAL_HELPER_SOURCE")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            not getattr(before, "st_file_attributes", 0) & 0x400 and 0 < before.st_size <= maximum,
            "CANONICAL_HELPER_SOURCE")
    attributes = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns", "st_file_attributes")
    stamp = tuple(getattr(before, name, None) for name in attributes)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) |
                         getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    original, raw = None, b""
    try:
        opened = os.fstat(descriptor)
        require(tuple(getattr(opened, name, None) for name in attributes) == stamp, "CANONICAL_HELPER_SOURCE")
        while len(raw) <= maximum:
            block = os.read(descriptor, maximum + 1 - len(raw))
            if not block:
                break
            raw += block
        after = os.fstat(descriptor)
        require(tuple(getattr(after, name, None) for name in attributes) == stamp and
                len(raw) == before.st_size, "CANONICAL_HELPER_SOURCE")
    except BaseException as error:
        original = error
    try:
        os.close(descriptor)
    except BaseException as error:
        if original is not None:
            raise original from error
        raise
    if original is not None:
        raise original
    current = path.lstat()
    require(tuple(getattr(current, name, None) for name in attributes) == stamp, "CANONICAL_HELPER_SOURCE")
    for parent, previous in ancestors:
        current = parent.lstat()
        require(os.path.samestat(previous, current) and stat.S_ISDIR(current.st_mode) and
                not getattr(current, "st_file_attributes", 0) & 0x400, "CANONICAL_HELPER_SOURCE")
    return raw


def _load_canonical_helper():
    raw = _canonical_source("hosted_canonical_python.py", _CANONICAL_HELPER_LIMIT)
    require(hashlib.sha256(raw).hexdigest() == _CANONICAL_HELPER_SHA256, "CANONICAL_HELPER_SOURCE_BINDING")
    path = SCRIPTS / "hosted_canonical_python.py"
    namespace = {"__name__": "p2pkit_canonical_helpers", "__file__": str(path), "__package__": None}
    # Execute precisely the bounded bytes just compared to the caller's original
    # expected hash. No import cache, path mutation, loader hook or second read.
    exec(compile(raw, str(path), "exec", dont_inherit=True), namespace)
    return namespace


_CANONICAL_HELPER = _load_canonical_helper()
CANONICAL_NAMES = _CANONICAL_HELPER["CANONICAL_NAMES"]
CANONICAL_SOURCE_LIMIT = _CANONICAL_HELPER["CANONICAL_SOURCE_LIMIT"]
CANONICAL_BOOTSTRAP = _CANONICAL_HELPER["CANONICAL_BOOTSTRAP"]


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
    return _CANONICAL_HELPER["assemble"](executable, str(SCRIPTS),
                                       encoded(bindings).decode("ascii").strip(), *args)


def profile_command(profile, role, *, package_samples=False):
    require(profile in PRODUCT_SECONDS and role in INSTALLERS and type(package_samples) is bool,
            "CONTROLLER_PROFILE")
    if profile == "full":
        require(role.startswith("macos-") and not package_samples, "FULL_REQUIRES_NATIVE_MAC")
        return "command", ["python3", "scripts/run-platform-tests.py", "full"]
    tasks = list(DESKTOP_TASKS)
    if package_samples:
        if role == "linux-x64":
            tasks.append(":p2p-sample-android:assembleDebug")
        tasks.append(INSTALLERS[role])
    return "gradle", [*tasks, "--console=plain"]


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


def child_environment(base, session, state, *, require_jdks=True):
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
    require(not require_jdks or result.get("JAVA_HOME") and result.get("P2PKIT_AUDIT_JDK21"),
            "TWO_EXPLICIT_JDK_HOMES_REQUIRED")
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


def retain_abi_generated(owner, target, build_owners, end, check=lambda: None):
    """Six exact snapshots; eight separately acquired original generated files."""
    require(os.name == "posix", "PRIMARY_FULL_ABI_NATIVE_MAC_ONLY")
    groups = {}
    for index, (module, generated, *_rest) in enumerate(abi.ROUTES):
        subtree, name = generated.split("/", 1)
        groups.setdefault((module, subtree), []).append((index, name))
    originals, acquired, roots = {}, {}, []
    for (module, subtree), members in groups.items():
        check()
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
        check()
        require(set(entries) == names | directories and
                all(stat.S_ISDIR(entries[name][2]) for name in directories) and
                all(stat.S_ISREG(entries[name][2]) and 0 < entries[name][5] <= abi.FILE_LIMIT for name in names),
                "ABI_EXACT_GENERATED_ROSTER_REQUIRED")
        for index, name in members:
            check()
            reader = owner.acquire("abi-generated-reader", lambda: posix._open_member(root, name, entries))
            original = None
            try:
                posix._deadline(end)
                raw = reader.read(entries[name][5] + 1)
                require(type(raw) is bytes and len(raw) == entries[name][5] and reader.read(1) == b"" and
                        posix._stamp(os.fstat(reader.fileno())) == entries[name], "ABI_ORIGINAL_CHANGED_DURING_READ")
                check()
            except BaseException as error:
                original = error
                owner.error("abi-generated-read", error)
            finally:
                owner.close_one(reader)
            if original is not None:
                raise original
            require(not owner.unknown, "ABI_GENERATED_READER_RETIREMENT_UNKNOWN")
            check()
            owner.write(target, abi.member(index, "generated"), raw, end)
            check()
            originals[index], acquired[index] = raw, list(entries[name])
        require(posix_snapshot(owner, root, len(members) * abi.FILE_LIMIT, len(names | directories), end) == entries and
                abi_ancestors(build, subtree) == before, "ABI_GENERATED_SNAPSHOT_CHANGED")
        build.verify()
        check()
    return originals, {"roots": roots, "files": [acquired[index] for index in range(8)]}


def primary_abi_log(owner, invocation, end, *, name="product.stdout.log", check=lambda: None):
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
        result = abi.observe_log(reader, info.st_size, lambda: (posix._deadline(end), check()))
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
    check()
    return result


def primary_abi_inputs(owner, private, context, end, check=lambda: None):
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
            "platform": platform, "gradleCommand": expected}, primary_abi_log(owner, invocation, end, check=check)


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
    supplement_binding = supplements.frozen_packet(owner, globals(), private, frozen,
                                                    {row["original"]: row for row in all_rows}, end)
    require(owner.read(frozen, "original-path-map.json", end) == map_raw and
            posix_snapshot(owner, frozen.path, posix.MAX_BYTES, posix.MAX_MEMBERS, end) == snapshot, "ABI_FROZEN_MAP_CHANGED")
    manifest = originals.get("primary-abi/manifest.json")
    return {"mapSha256": digest(map_raw), "files": rows, "provenance": provenance, "supplements": supplement_binding,
            "manifestSha256": None if manifest is None else digest(manifest)}, originals


def seed_names(owner, path, end):
    """Bounded flat receipt inventory; never snapshot restored dependency bytes."""
    directory = owner.acquire("dependency-seed-record-directory", lambda: seed.private_root(path))
    original = None
    try:
        return directory.names(max_names=seed.MEMBER_LIMIT, deadline=end)
    except BaseException as error:
        original = error
        raise
    finally:
        owner.close_one(directory)
        if owner.unknown and original is None:
            raise ControllerError("SEED_RECORD_DIRECTORY_CLOSE_UNKNOWN")


def dependency_seed_intent(owner, private, admitted, context_raw, end, check):
    """Current admitted inputs plus original staging; no live cache revalidation."""
    context = parse(context_raw)
    intent = context.get("dependencySeed")
    require(type(intent) is dict, "SEED_ORIGINAL_INTENT_MISSING")
    check()
    inputs, compiled = seed.source_inputs(owner, ROOT, end, check)
    directory = owner.child(private, "dependency-seed", end)
    staging_raw = owner.read(directory, "staging.json", end)
    staging = parse(staging_raw)
    seed.validate_retained_stage(staging, admitted.record, context, inputs)
    require(staging_raw == seed.encoded(staging) and intent == seed.seed_intent(admitted.record,
            context["profile"], context["role"], seed.stage_path(private.path, context["profile"], context["role"]),
            staging_raw, inputs), "SEED_ORIGINAL_INTENT_CHANGED")
    check()
    return directory, staging_raw, compiled


def seed_copy_map(raw, root):
    """Seed-specific verification of copy_tree's closed map; strings are not paths."""
    value = parse(raw)
    require(set(value) == {"schema", "scope", "originalRoot", "directories", "files"} and
            type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == "REVERSIBLE_PRIVATE_BYTE_COPY" and value["originalRoot"] == str(root) and
            type(value["files"]) is list and type(value["directories"]) is list and
            len(value["files"]) + len(value["directories"]) <= posix.MAX_MEMBERS, "SEED_COPY_MAP_GRAMMAR")
    def relative(name):
        return (type(name) is str and len(name.encode("utf-8")) <= 1024 and "\\" not in name and
                all(ord(char) >= 32 and ord(char) != 127 for char in name) and
                (name == "" or len(name.split("/")) <= 65 and
                 all(part not in ("", ".", "..") for part in name.split("/"))))
    rows, directories = value["files"], value["directories"]
    require(all(type(row) is dict and set(row) == {"original", "member", "size", "sha256"} and
            relative(row["original"]) and row["original"] != "" and
            row["member"] == "member-" + str(index).zfill(5) + ".bin" and type(row["size"]) is int and
            0 <= row["size"] <= posix.MAX_BYTES and type(row["sha256"]) is str and
            re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) for index, row in enumerate(rows)) and
            all(relative(name) for name in directories), "SEED_COPY_MAP_ROWS")
    names = [row["original"] for row in rows]
    require(names == sorted(set(names)) and directories == sorted(set(directories)) and "" in directories and
            not set(names) & set(directories) and sum(row["size"] for row in rows) <= posix.MAX_BYTES and
            all((name.rsplit("/", 1)[0] if "/" in name else "") in directories
                for name in [*names, *directories] if name), "SEED_COPY_MAP_ROSTER")
    return value


def frozen_seed_packet(owner, private, end, check=lambda: None):
    """Original seed receipts -> inner map/copies -> outer map/copies -> export return.

    The stage container, S and H/cache payloads are never opened here. Legitimate
    later Gradle mutations are not a reason to invalidate original file custody.
    """
    context_raw = owner.read(private, "run-context.json", end)
    context = parse(context_raw)
    evidence = owner.child(private, "evidence", end)
    admitted = load_admission(owner, owner.child(evidence, "admission", end), end)
    require(digest(admitted.record) == context["admissionSha256"], "SEED_ORIGINAL_ADMISSION_CHANGED")
    original, staging_raw, compiled = dependency_seed_intent(owner, private, admitted, context_raw, end, check)
    originals = {"staging.json": staging_raw, "manifest.json": owner.read(original, "manifest.json", end)}
    require(set(seed_names(owner, original.path, end)) == set(originals), "SEED_ORIGINAL_RECEIPT_ROSTER")
    state = owner.child(private, "state", end)
    canonical_raw = owner.read(state, "context.json", end)
    seed.validate_receipt(parse(originals["manifest.json"]), context["dependencySeed"], staging_raw, context_raw,
                          canonical_raw, admitted.record, compiled)
    disposition = seed.disposition(originals["manifest.json"])
    before_raw = owner.read(evidence, "profile-result-before-export.json", end)
    require(parse(before_raw).get("dependencySeed") == disposition, "SEED_FROZEN_PROFILE_CHANGED")
    copied = owner.child(evidence, "dependency-seed", end)
    inner_raw = owner.read(copied, "original-path-map.json", end)
    inner = seed_copy_map(inner_raw, original.path)
    require(inner["directories"] == [""] and [row["original"] for row in inner["files"]] == sorted(originals) and
            set(seed_names(owner, copied.path, end)) == {"original-path-map.json", *[row["member"]
                for row in inner["files"]]}, "SEED_INNER_MAP_ROSTER")
    frozen = owner.child(private, "frozen-evidence", end)
    outer_raw = owner.read(frozen, "original-path-map.json", end)
    outer = seed_copy_map(outer_raw, evidence.path)
    outer_rows = {row["original"]: row for row in outer["files"]}
    expected_copies = {"dependency-seed/original-path-map.json": inner_raw,
                       "profile-result-before-export.json": before_raw}
    for row in inner["files"]:
        raw = originals[row["original"]]
        require((len(raw), digest(raw)) == (row["size"], row["sha256"]) and
                owner.read(copied, row["member"], end) == raw, "SEED_INNER_COPY_CHANGED")
        expected_copies["dependency-seed/" + row["member"]] = raw
    require({name for name in outer_rows if name.startswith("dependency-seed/")} ==
            {name for name in expected_copies if name.startswith("dependency-seed/")} and
            [name for name in outer["directories"] if name == "dependency-seed" or
             name.startswith("dependency-seed/")] == ["dependency-seed"] and
            set(seed_names(owner, frozen.path, end)) == {"original-path-map.json", *[row["member"]
                for row in outer["files"]]}, "SEED_OUTER_MAP_ROSTER")
    for name, raw in expected_copies.items():
        row = outer_rows.get(name)
        require(type(row) is dict and (row["size"], row["sha256"]) == (len(raw), digest(raw)) and
                owner.read(frozen, row["member"], end) == raw, "SEED_OUTER_COPY_CHANGED")
    require(owner.read(private, "run-context.json", end) == context_raw and
            owner.read(state, "context.json", end) == canonical_raw and
            owner.read(evidence, "profile-result-before-export.json", end) == before_raw and
            all(owner.read(original, name, end) == raw for name, raw in originals.items()) and
            owner.read(copied, "original-path-map.json", end) == inner_raw and
            owner.read(frozen, "original-path-map.json", end) == outer_raw and not owner.unknown,
            "SEED_PACKET_CHANGED_DURING_VERIFICATION")
    check()
    return {"disposition": disposition, "stagingSha256": digest(staging_raw), "contextSha256": digest(context_raw),
            "canonicalContextSha256": digest(canonical_raw), "innerMapSha256": digest(inner_raw),
            "outerMapSha256": digest(outer_raw), "copies": [outer_rows[name] for name in sorted(expected_copies)]}


def frozen_consume_packet(owner, private, end, check):
    """Original pre-tool/restore records must be the bytes actually encrypted.

    No live S/H cache is opened after the product. All these original records
    precede product/Central execution; no post-screen exception is introduced.
    """
    context_raw = owner.read(private, "run-context.json", end)
    context = parse(context_raw)
    evidence = owner.child(private, "evidence", end)
    admitted = load_admission(owner, owner.child(evidence, "admission", end), end)
    budget = load_job_budget(owner, private, admitted, context, end)
    bound = consume_binding(owner, private, admitted, budget, end)
    require(bound == context.get("dependencyCache"), "CACHE_FROZEN_CONTEXT_CHANGED")
    originals = {}
    directory = owner.child(evidence, "dependency-cache", end)
    names = {"plan.json", "staging.json", "preparation.json", "provider.json", "restoration.json",
             "controller-context.json"}
    require(set(seed_names(owner, directory.path, end)) == names, "CACHE_ORIGINAL_RECEIPT_ROSTER")
    for name in sorted(names):
        originals["dependency-cache/" + name] = owner.read(directory, name, end)
    require(originals["dependency-cache/controller-context.json"] == context_raw, "CACHE_ORIGINAL_CONTEXT_CHANGED")
    timing = owner.child(evidence, "job-time", end)
    names = set(seed_names(owner, timing.path, end))
    fixed = {"attempt.json", "jobs.json", "child-return.json", "budget.json"}
    require(fixed <= names <= fixed | {"product-cancellation.json"}, "CACHE_TIMING_RECEIPT_ROSTER")
    for name in sorted(names):
        originals["job-time/" + name] = owner.read(timing, name, end)
    phase = owner.child(owner.child(evidence, "commands", end), "job-time", end)
    names = {"start.json", "result.json", "baseline.json", "stdout.log", "stderr.log"}
    require(set(seed_names(owner, phase.path, end)) == names, "CACHE_TIME_PHASE_ROSTER")
    for name in sorted(names):
        originals["commands/job-time/" + name] = owner.read(phase, name, end)
    anchors = {"dependency-cache/" + name + ".json": bound[key + "Sha256"] for name, key in
               (("preparation", "preparation"), ("restoration", "restoration"), ("plan", "plan"),
                ("provider", "provider"), ("staging", "staging"))}
    anchors.update({"job-time/budget.json": budget.sha256,
        **{"job-time/" + key + ".json": sha for key, sha in budget.value["originalsSha256"].items()},
        "job-time/child-return.json": budget.value["provenance"]["childReturnSha256"],
        "commands/job-time/start.json": budget.value["provenance"]["phaseStartSha256"],
        "commands/job-time/result.json": budget.value["provenance"]["phaseResultSha256"]})
    require(all(digest(originals[name]) == sha for name, sha in anchors.items()),
            "CACHE_VALIDATED_ORIGINALS_CHANGED_BEFORE_FREEZE")
    before_raw = owner.read(evidence, "profile-result-before-export.json", end)
    require(parse(before_raw).get("dependencyCache") == bound and
            parse(before_raw).get("contextSha256") == digest(context_raw), "CACHE_FROZEN_PROFILE_CHANGED")
    originals["profile-result-before-export.json"] = before_raw
    frozen = owner.child(private, "frozen-evidence", end)
    map_raw = owner.read(frozen, "original-path-map.json", end)
    mapping = seed_copy_map(map_raw, evidence.path)
    rows = {row["original"]: row for row in mapping["files"]}
    require(set(seed_names(owner, frozen.path, end)) == {"original-path-map.json", *[row["member"] for row in rows.values()]} and
            all({name for name in rows if name.startswith(prefix)} == {name for name in originals if name.startswith(prefix)}
                for prefix in ("dependency-cache/", "job-time/", "commands/job-time/")), "CACHE_FROZEN_ROSTER_CHANGED")
    for name, raw in originals.items():
        check()
        row = rows.get(name)
        require(type(row) is dict and (row["size"], row["sha256"]) == (len(raw), digest(raw)) and
                owner.read(frozen, row["member"], end) == raw, "CACHE_FROZEN_ORIGINAL_DIFFERS")
    for name, raw in originals.items():
        current = evidence
        parts = name.split("/")  # Closed producer-selected names above, never external paths.
        for part in parts[:-1]:
            current = owner.child(current, part, end)
        require(owner.read(current, parts[-1], end) == raw, "CACHE_ORIGINAL_CHANGED_DURING_FREEZE")
    require(owner.read(frozen, "original-path-map.json", end) == map_raw and
            owner.read(private, "run-context.json", end) == context_raw and not owner.unknown,
            "CACHE_PACKET_CHANGED_DURING_VERIFICATION")
    check()
    return {"contextSha256": digest(context_raw), "binding": bound, "mapSha256": digest(map_raw),
            "files": [rows[name] for name in sorted(originals)]}


def sample_posix_reader(directory, name, snapshot, end):
    """Read a closed sample member without expanding dependency-name authority.

    The two dotfile receipts are not dependency filenames. The already-owned
    public source directory pins its descriptor/ancestry; O_NONBLOCK prevents a
    swapped FIFO waiting for a writer before fstat can reject it. Neither this
    adapter nor its caller starts a process or owns another directory descriptor.
    """
    require(isinstance(directory, seed.PosixSourceDirectory), "SAMPLE_PINNED_POSIX_DIRECTORY_REQUIRED")
    if name not in (".prepare.json", ".complete.json"):
        seed.authority._basename(name)
    posix._deadline(end)
    directory.verify()
    parent = directory._pins[-1].fd
    require(posix._stamp(os.fstat(parent)) == snapshot[""], "SAMPLE_DIRECTORY_CHANGED_BEFORE_OPEN")
    fd, stream = None, None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        require(posix._stamp(os.fstat(fd)) == snapshot[name] and stat.S_ISREG(snapshot[name][2]),
                "SAMPLE_FILE_CHANGED_BEFORE_OPEN")
        stream = os.fdopen(fd, "rb")
        fd = None  # Ownership transfers only after fdopen succeeds.
        directory.verify()
        posix._deadline(end)
        return stream
    except BaseException as original:
        try:
            if stream is not None:
                stream.close()
            elif fd is not None:
                os.close(fd)
        except BaseException as error:
            seed._note(original, "sample-reader-allocation-close", error)
        raise


def sample_output_identity(directory, end, check):
    """Observe the producer's Python stat identity under the original root pin.

    Windows FileInfo uses a volume/128-bit-ID hex pair, not Python st_dev/st_ino.
    Keep both representations separately; never guess a conversion between them.
    Original pinned ancestry is verified on both sides of the no-follow stat.
    """
    check()
    posix._deadline(end)
    before = directory.verify()
    info = os.stat(directory.path, follow_symlinks=False)
    require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400 and
            all(type(value) is int and value >= 0 for value in (info.st_dev, info.st_ino)) and
            directory.verify() == before, "SAMPLE_OUTPUT_IDENTITY_CHANGED")
    check()
    posix._deadline(end)
    return [info.st_dev, info.st_ino]


def sample_file(owner, directory, name, end, check, *, metadata=False):
    """Hash one original regular file using existing pinned/snapshot readers.

    Ordinary delivery retains the existing512MiB file/2GiB aggregate bound.
    This does not widen the Windows file supplier for oversized packages.
    """
    maximum = RECORD_LIMIT if metadata else seed.FILE_LIMIT
    stream, rows, parts = None, None, []
    try:
        directory.verify()
        if os.name == "nt":
            stream = owner.acquire("sample-reader", lambda: directory.open_file(name, max_bytes=maximum, deadline=end))
            info = stream.initial_info
            size, file_id = info.size, list(info.identity)
        else:
            rows = posix_snapshot(owner, directory.path, seed.TOTAL_LIMIT, 64, end)
            require(name in rows and stat.S_ISREG(rows[name][2]) and 0 < rows[name][5] <= maximum,
                    "SAMPLE_FILE_BOUND_OR_KIND")
            size, file_id = rows[name][5], list(rows[name][:2])
            stream = owner.acquire("sample-reader", lambda: sample_posix_reader(directory, name, rows, end))
        require(0 < size <= maximum, "SAMPLE_FILE_BOUND_OR_KIND")
        hasher, total = hashlib.sha256(), 0
        while total < size:
            check()
            block = stream.read(min(MIB, size - total))
            require(type(block) is bytes and block, "SAMPLE_FILE_TRUNCATED")
            total += len(block)
            hasher.update(block)
            if metadata:
                parts.append(block)
        require(stream.read(1) == b"", "SAMPLE_FILE_GREW")
        if os.name == "nt":
            require(stream.verify() == info, "SAMPLE_FILE_CHANGED")
        else:
            require(posix._stamp(os.fstat(stream.fileno())) == rows[name] and
                    posix_snapshot(owner, directory.path, seed.TOTAL_LIMIT, 64, end) == rows, "SAMPLE_FILE_CHANGED")
        directory.verify()
        check()
        result = {"size": total, "sha256": hasher.hexdigest(), "identity": file_id}
    except BaseException as error:
        owner.error("sample-reader", error)
        raise
    finally:
        if stream is not None:
            owner.close_one(stream)
    require(not owner.unknown, "SAMPLE_READER_RETIREMENT_UNKNOWN")
    check()
    return result, b"".join(parts) if metadata else None


def sample_fields(value, names, code):
    require(type(value) is dict and set(value) == set(names.split()), code)
    return value


def sample_embedded_identity(value, versions, commit):
    expected = sample_version.embedded_identity(versions["canonicalVersion"], commit)
    require(type(value) is dict and type(value.get("schema")) is int and
            type(value.get("androidVersionCode")) is int and value == expected, "SAMPLE_EMBEDDED_IDENTITY_CHANGED")


def sample_native_metadata(value, platform, versions, commit):
    """Bind the ORIGINAL packager's inspection; never run a native reader again."""
    value = sample_fields(value, "reader fields embeddedIdentity", "SAMPLE_NATIVE_INSPECTION_FIELDS")
    readers = {"linux": "dpkg-deb control + data-only tar",
               "windows": "MsiOpenDatabaseW/READONLY + embedded cabinet",
               "macos": "hdiutil read-only / Info.plist"}
    require(value["reader"] == readers[platform], "SAMPLE_NATIVE_READER_CHANGED")
    fields = value["fields"]
    if platform == "linux":
        require(fields == {"Package": "p2pkit-sample", "Version": versions["debianVersion"], "Architecture": "amd64"},
                "SAMPLE_NATIVE_VERSION_CHANGED")
    elif platform == "windows":
        sample_fields(fields, "ProductName ProductVersion Template WordCount", "SAMPLE_NATIVE_INSPECTION_FIELDS")
        require(fields["ProductName"] == "P2pKit Sample" and fields["ProductVersion"] == versions["nativeVersion"] and
                type(fields["Template"]) is str and re.fullmatch(r"x64;[0-9]+(?:,[0-9]+)*", fields["Template"]) and
                type(fields["WordCount"]) is int and 0 <= fields["WordCount"] <= 0x7fffffff,
                "SAMPLE_NATIVE_VERSION_CHANGED")
    else:
        require(fields == {"CFBundleShortVersionString": versions["nativeVersion"],
                           "CFBundleVersion": versions["nativeVersion"]}, "SAMPLE_NATIVE_VERSION_CHANGED")
    sample_embedded_identity(value["embeddedIdentity"], versions, commit)


def sample_manifest_identity(manifest, kind, current, versions):
    """Closed schema3 identity joins, not package/native/runtime qualification.

    The successful original packager owns inspection of actual application bytes.
    This reader binds that retained inspection and the immutable delivery files to
    the admitted checkout's independently decoded version, without invoking it.
    """
    common = "schema sourceAndRun scope versionBinding "
    sample_fields(manifest, common + ("artifacts layoutInspection installerInspection" if kind == "desktop" else
                  "artifact agpMetadata apkInspection metadataFile"), "SAMPLE_MANIFEST_FIELDS")
    require(type(manifest["schema"]) is int and manifest["schema"] == 3 and manifest["sourceAndRun"] == current and
            manifest["scope"] == SAMPLE_SCOPE and type(manifest["scope"].get("desktopInstaller")) is bool,
            "SAMPLE_MANIFEST_SOURCE_CHANGED")
    version = manifest["versionBinding"]
    require(type(version) is dict and type(version.get("androidVersionCode")) is int and version == versions,
            "SAMPLE_VERSION_BINDING_CHANGED")
    platform, architecture, commit = current["platform"], current["architecture"], current["commit"]
    if kind == "desktop":
        require(manifest["installerInspection"] == SAMPLE_INSTALLER_INSPECTION, "SAMPLE_INSTALLER_SCOPE_CHANGED")
        layout = sample_fields(manifest["layoutInspection"], "launcher runtimeVm runtimeJava javaVersion releaseArchitecture "
                               "embeddedIdentity jarCount cliRequiresExternalJava layoutOnlyNotRuntimeExecution",
                               "SAMPLE_LAYOUT_INSPECTION_FIELDS")
        for name in ("launcher", "runtimeVm", "runtimeJava"):
            architectures = layout[name]
            if name == "runtimeJava" and architectures is None:
                continue
            require(type(architectures) is list and all(type(item) is str and item in ("arm64", "x64")
                    for item in architectures) and architectures == sorted(set(architectures)) and
                    architecture in architectures and (platform == "macos" or architectures == [architecture]),
                    "SAMPLE_LAYOUT_ARCHITECTURE_CHANGED")
        release_arch = layout["releaseArchitecture"]
        require(type(layout["javaVersion"]) is str and bool(layout["javaVersion"]) and
                (release_arch is None or type(release_arch) is str and (not release_arch or
                 {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(release_arch) == architecture)) and
                type(layout["jarCount"]) is int and 0 < layout["jarCount"] <= 1024 and
                layout["cliRequiresExternalJava"] == "17+" and layout["layoutOnlyNotRuntimeExecution"] is True,
                "SAMPLE_LAYOUT_INSPECTION_CHANGED")
        sample_embedded_identity(layout["embeddedIdentity"], versions, commit)
    else:
        agp = sample_fields(manifest["agpMetadata"], "applicationId variant versionCode versionName", "SAMPLE_AGP_FIELDS")
        expected = {"applicationId": "dev.p2pkit.sample.android", "versionCode": versions["androidVersionCode"],
                    "versionName": versions["canonicalVersion"]}
        require(type(agp["versionCode"]) is int and agp == {**expected, "variant": "debug"}, "SAMPLE_AGP_IDENTITY_CHANGED")
        apk = sample_fields(manifest["apkInspection"], "binaryManifest embeddedIdentity signerIdentity", "SAMPLE_APK_FIELDS")
        binary = apk["binaryManifest"]
        require(type(binary) is dict and type(binary.get("versionCode")) is int and binary == expected and
                apk["signerIdentity"] == "NOT_VERIFIED", "SAMPLE_APK_IDENTITY_CHANGED")
        sample_embedded_identity(apk["embeddedIdentity"], versions, commit)
        metadata = sample_fields(manifest["metadataFile"], "bytes sha256", "SAMPLE_AGP_SOURCE_FIELDS")
        require(type(metadata["bytes"]) is int and 0 < metadata["bytes"] <= MIB and type(metadata["sha256"]) is str and
                re.fullmatch(r"[0-9a-f]{64}", metadata["sha256"]), "SAMPLE_AGP_SOURCE_BINDING")


def sample_snapshot(owner, session, admitted, role, end, check):
    """Exact successful packager output, never arbitrary upload paths or globbing."""
    check()
    # The existing one-shot parent ledger owns these acquisitions on failure;
    # success additionally requires the source reader/directory to close here.
    version_owners = seed._Owners(owner)
    version_source = version_owners.acquire("sample-version-source", lambda: seed.public_root(ROOT))
    properties = seed._small_read(version_owners, version_source, "gradle.properties", end, 65536, check)
    try:
        versions = sample_version.from_properties(properties.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise ControllerError("SAMPLE_SOURCE_VERSION_INVALID") from None
    check()
    root_path = session.parent / "p2pkit-sample-apps"
    root = owner.acquire("sample-output", lambda: seed.public_root(root_path))
    platforms = ["desktop", "android"] if role == "linux-x64" else ["desktop"]
    top = {".prepare.json", ".complete.json", *platforms}
    require(set(root.names(max_names=64, deadline=end)) == top, "SAMPLE_OUTPUT_ROSTER")
    output_identity = sample_output_identity(root, end, check)
    roster, originals, directories = {}, {}, {"": list(root.identity)}
    def capture(directory, prefix, name, metadata=False):
        row, raw = sample_file(owner, directory, name, end, check, metadata=metadata)
        roster[prefix + name] = row
        require(sum(item["size"] for item in roster.values()) <= seed.TOTAL_LIMIT, "SAMPLE_AGGREGATE_BOUND")
        if raw is not None:
            originals[prefix + name] = raw
        return raw
    prepared = parse(capture(root, "", ".prepare.json", True))
    completed = parse(capture(root, "", ".complete.json", True))
    record = parse(admitted.record)
    source, github = record["source"], record["github"]
    platform = "linux" if role.startswith("linux-") else "windows" if role.startswith("windows-") else "macos"
    architecture = "arm64" if role == "macos-arm64" else "x64"
    expected = {"repository": identity.REPOSITORY, **source, "run_id": github["runId"],
        "run_attempt": github["runAttempt"], "event_name": github["event"], "ref": github["ref"],
        "workflow_ref": identity.REPOSITORY + "/" + github["workflow"] + "@" + github["ref"],
        "workflow_sha": github["workflowSha"], "job": github["job"], "platform": platform,
        "architecture": architecture, "canonicalVersion": versions["canonicalVersion"]}
    current = completed.get("context")
    generated = ["samples/p2p-sample-desktop-ui/build/compose/binaries/main/app",
                 "samples/p2p-sample-desktop/build/install/p2p-sample-desktop",
                 "samples/p2p-sample-desktop-ui/build/compose/binaries/main/" +
                    {"linux": "deb", "windows": "msi", "macos": "dmg"}[platform]]
    if platform == "linux":
        generated.append("samples/p2p-sample-android/build/outputs/apk/debug")
    require(type(current) is dict and set(current) == set(expected) | {"osRelease", "python", "translation"} and
            all(current.get(key) == value for key, value in expected.items()) and
            all(type(current[name]) is str and current[name] for name in ("osRelease", "python")) and
            current["translation"] in (("NATIVE_0", "OPTIONAL_KEY_ABSENT_EXIT_1") if platform == "macos" else
                                       ("NOT_APPLICABLE",)) and
            set(completed) == {"schema", "context", "scope"} and
            type(completed.get("schema")) is int and completed["schema"] == 1 and
            completed.get("scope") == SAMPLE_SCOPE and type(completed["scope"].get("desktopInstaller")) is bool and
            set(prepared) == {"schema", "context", "root", "outputIdentity", "generatedRoots"} and
            type(prepared.get("schema")) is int and prepared["schema"] == 1 and prepared.get("context") == current and
            prepared.get("root") == str(ROOT) and prepared.get("outputIdentity") == output_identity and
            prepared.get("generatedRoots") == generated,
            "SAMPLE_ORIGINAL_SOURCE_OR_OUTPUT_CHANGED")
    label = platform + "-" + architecture + "-" + source["commit"][:12]
    licenses = {"P2pKit-LICENSE", "JmDNS-LICENSE", "JmDNS-NOTICE.txt"}
    for kind in platforms:
        check()
        directory = owner.acquire("sample-platform", lambda: root.open_directory(kind, deadline=end))
        directories[kind] = list(directory.identity)
        prefix = kind + "/"
        manifest = parse(capture(directory, prefix, "manifest.json", True))
        checksums = capture(directory, prefix, "checksums.sha256", True)
        sample_manifest_identity(manifest, kind, current, versions)
        if kind == "desktop":
            suffix = ".zip" if platform == "windows" else ".tar.gz"
            extension = {"linux": "deb", "windows": "msi", "macos": "dmg"}[platform]
            names = {"desktop-ui-" + label + suffix, "desktop-cli-" + label + suffix,
                     "desktop-installer-" + label + "." + extension}
            artifacts = manifest.get("artifacts")
            require(type(artifacts) is list and len(artifacts) == 3, "SAMPLE_ARTIFACT_ROSTER")
        else:
            artifacts = [manifest.get("artifact")]
            require(type(artifacts[0]) is dict and type(artifacts[0].get("file")) is str and
                    re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\.apk", artifacts[0]["file"]),
                    "SAMPLE_ANDROID_ARTIFACT_NAME")
            names = {artifacts[0]["file"]}
        require(all(type(row) is dict for row in artifacts) and {row.get("file") for row in artifacts} == names and
                set(directory.names(max_names=64, deadline=end)) == {"manifest.json", "checksums.sha256", "licenses", *names},
                "SAMPLE_ARTIFACT_ROSTER")
        for row in artifacts:
            if kind == "desktop" and row["file"].startswith("desktop-installer-"):
                sample_fields(row, "file bytes sha256 nativeMetadata", "SAMPLE_INSTALLER_FIELDS")
                sample_native_metadata(row["nativeMetadata"], platform, versions, source["commit"])
            elif kind == "desktop":
                sample_fields(row, "file bytes sha256 entries", "SAMPLE_ARCHIVE_FIELDS")
                require(type(row["entries"]) is list and 0 < len(row["entries"]) <= 20000 and
                        all(type(entry) is dict for entry in row["entries"]), "SAMPLE_ARCHIVE_INVENTORY")
            else:
                sample_fields(row, "file bytes sha256", "SAMPLE_APK_ARTIFACT_FIELDS")
            capture(directory, prefix, row["file"])
            actual = roster[prefix + row["file"]]
            require(type(row.get("bytes")) is int and row["bytes"] == actual["size"] and
                    row.get("sha256") == actual["sha256"], "SAMPLE_ARTIFACT_CHANGED")
        notices = owner.acquire("sample-licenses", lambda: directory.open_directory("licenses", deadline=end))
        directories[kind + "/licenses"] = list(notices.identity)
        require(set(notices.names(max_names=64, deadline=end)) == licenses, "SAMPLE_LICENSE_ROSTER")
        for name in sorted(licenses):
            capture(notices, prefix + "licenses/", name)
        expected_checksums = "".join(roster[name]["sha256"] + "  " + name[len(prefix):] + "\n"
            for name in sorted(roster) if name.startswith(prefix) and name != prefix + "checksums.sha256").encode("ascii")
        require(checksums == expected_checksums, "SAMPLE_CHECKSUM_ROSTER_CHANGED")
        notices.verify()
        directory.verify()
    root.verify()
    require(set(root.names(max_names=64, deadline=end)) == top and
            sample_output_identity(root, end, check) == output_identity, "SAMPLE_OUTPUT_CHANGED")
    require(seed._small_read(version_owners, version_source, "gradle.properties", end, 65536, check) == properties,
            "SAMPLE_SOURCE_VERSION_CHANGED")
    version_source.verify()
    version_owners.close()
    require(not owner.unknown, "SAMPLE_VERSION_SOURCE_CLOSE_UNKNOWN")
    check()
    return {"path": str(root_path), "packagerOutputIdentity": output_identity, "directories": directories, "files": roster,
            "versionSourceSha256": digest(properties), "versionBinding": versions}


def frozen_package_packet(owner, private, end, check):
    """Packaging command/summary originals must be inside the one encrypted copy."""
    evidence = owner.child(private, "evidence", end)
    context_raw = owner.read(private, "run-context.json", end)
    context = parse(context_raw)
    before_raw = owner.read(evidence, "profile-result-before-export.json", end)
    before = parse(before_raw)
    raw = owner.read(evidence, "sample-packaging.json", end)
    report = parse(raw)
    require(context.get("samplePackagingRequired") is True and context["profile"] == before["profile"] == "desktop" and
            before["samplePackaging"] == {"required": True, "status": "PASS", "manifestSha256": digest(raw)} and
            report.get("scope") == "ORIGINAL_PACKAGED_SAMPLES" and report.get("schema") == 1 and
            report.get("contextSha256") == before["contextSha256"] == digest(context_raw) and
            report.get("source") == context["source"] and report.get("role") == context["role"] and
            report.get("phaseSha256") == before["phaseSha256"]["sample-packaging"], "SAMPLE_ORIGINAL_PACKAGE_CHANGED")
    originals = {"sample-packaging.json": raw, "profile-result-before-export.json": before_raw}
    phase = owner.child(owner.child(evidence, "commands", end), "sample-packaging", end)
    for name in ("start.json", "result.json", "baseline.json", "stdout.log", "stderr.log"):
        originals["commands/sample-packaging/" + name] = owner.read(phase, name, end, OUTPUT_LIMIT)
    phase_raw = originals["commands/sample-packaging/result.json"]
    require(digest(phase_raw) == report["phaseSha256"] and parse(phase_raw) in before["phases"],
            "SAMPLE_PACKAGING_PHASE_CHANGED")
    frozen = owner.child(private, "frozen-evidence", end)
    map_raw = owner.read(frozen, "original-path-map.json", end)
    rows = {row["original"]: row for row in seed_copy_map(map_raw, evidence.path)["files"]}
    require({name for name in rows if name.startswith("commands/sample-packaging/")} ==
            {name for name in originals if name.startswith("commands/sample-packaging/")}, "SAMPLE_FROZEN_ROSTER_CHANGED")
    for name, content in originals.items():
        check()
        row = rows.get(name)
        require(type(row) is dict and (row["size"], row["sha256"]) == (len(content), digest(content)) and
                owner.read(frozen, row["member"], end, OUTPUT_LIMIT) == content, "SAMPLE_FROZEN_ORIGINAL_DIFFERS")
        directory = phase if name.startswith("commands/") else evidence
        require(owner.read(directory, name.split("/")[-1], end, OUTPUT_LIMIT) == content,
                "SAMPLE_ORIGINAL_CHANGED_DURING_FREEZE")
    require(owner.read(frozen, "original-path-map.json", end) == map_raw and
            owner.read(private, "run-context.json", end) == context_raw and not owner.unknown,
            "SAMPLE_PACKET_CHANGED_DURING_FREEZE")
    check()
    return {"manifestSha256": digest(raw), "mapSha256": digest(map_raw),
            "files": [rows[name] for name in sorted(originals)]}


class Controller(PrivateOwner):
    def __init__(self, profile, *, seed_dependencies=False, consume_dependencies=False, preflight=False):
        super().__init__()
        require(profile in PRODUCT_SECONDS, "CONTROLLER_PROFILE")
        self.profile, self.role = profile, processes.host_role()
        require(all(type(value) is bool for value in (seed_dependencies, consume_dependencies, preflight)),
                "SEED_OPTION_MUST_BE_BOOLEAN")
        require(not preflight or not (seed_dependencies or consume_dependencies), "PREFLIGHT_EXECUTION_SCOPE")
        self.consume_requested, self.preflight = consume_dependencies, preflight
        self.sample_required = False  # Derive only after original source admission.
        self.sample_result = {"required": True, "status": "NOT_ATTEMPTED", "manifestSha256": None}
        self.sample_attempted = False
        seed_dependencies |= consume_dependencies
        self.cache_binding = self.preparation_raw = None
        self.seed_requested, self.seed_directory, self.seed_intent = seed_dependencies, None, None
        self.seed_result = ({"required": True, "status": "FAILED", "completed": False, "retirement": "KNOWN"}
                            if seed_dependencies else None)
        self.kind, self.command = profile_command(profile, self.role)
        self.path = session_path(profile, self.role)
        self.state_path = self.path / "state"
        self.deadline = time.monotonic() + TOTAL_SECONDS[profile]
        # This remains an operation ceiling, NEVER the full job's start/time.
        # Full products cannot launch until the actual service budget is bound.
        self.budget, self.last_raw, self.clock = None, 0, None
        self.budget_exhausted, self.cutoff_observation = False, None
        self.budget_cancellation, self.terminal_raw = None, None
        token = os.environ.pop(job_time.TOKEN_ENV, None)
        self.actions_token = token if profile == "full" or preflight else None
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
        self.primary_abi_accounting = None
        self.collect_attempted = self.uninstall_attempted = self.simulator_retirement_attempted = False
        self.active_canonical = None
        self.full = supplements.Full(self, globals()) if profile == "full" else None
        self.environment = child_environment(dict(os.environ), self.path, self.state_path, require_jdks=not preflight)

    def now_raw(self):
        self.last_raw = (job_time.raw_now(self.last_raw) if self.clock is None else
                         job_time.raw_now(self.last_raw, clock=self.clock))
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

    def phase(self, label, argv, timeout, *, finalizing=False, product=False, acquire_time=False,
              supplement=None, helper=False):
        """Actual fixed-caller composition around make_scope, not a new backend."""
        self.check(finalizing)
        packaging = label == "sample-packaging"
        if packaging:
            require(self.sample_required and finalizing and not product and not acquire_time and
                    supplement is None and not helper and timeout == job_time.PACKAGE_SECONDS - FINAL_SECONDS and
                    argv == self.python(SCRIPTS / "package-sample-apps.py", "package", "--output",
                                        self.path.parent / "p2pkit-sample-apps"), "SAMPLE_PACKAGING_CLOSED_COMMAND")
            check_cancelled(self.cancelled)
        timed = self.profile == "full" or self.budget is not None or acquire_time
        if supplement is not None or helper:
            require(self.full is not None and not product and not acquire_time, "SUPPLEMENT_FULL_ONLY")
            self.full.admit_phase(label, argv, supplement, helper)
        canonical_id = (self.request["owner"]["productInvocation"] if product else
                        supplement["id"] if supplement is not None else None)
        canonical_domain = canonical_id is not None or helper
        require(self.active_canonical is None, "CANONICAL_SCOPE_ALREADY_EXECUTING")
        require(type(timeout) is int and 0 < timeout <= OUTER_SECONDS[self.profile], "PHASE_TIMEOUT")
        started = time.monotonic()
        end, final_end = min(self.deadline, started + timeout), min(self.deadline, started + timeout + FINAL_SECONDS)
        raw_started = raw_work_end = raw_final_end = None
        if timed:
            raw_started = self.now_raw()
            if acquire_time:
                require(label == "job-time" and not finalizing and not product and self.budget is None and
                        self.admitted is not None and timeout == job_time.ACQUIRE_SECONDS and
                        argv == self.python(__file__, "_job-time", "--profile", self.profile, "--admission-sha256",
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
                if label == supplements.CENTRAL_RETIRE:
                    # Original transaction fence, not a new285s on helper entry.
                    cap = self.full.central["helperEndRawNs"]
                    require(raw_started < cap, "CENTRAL_RETIREMENT_TRANSACTION_EXPIRED")
                    raw_work_end = min(raw_work_end, cap)
                    raw_final_end = min(raw_final_end, cap + FINAL_SECONDS * job_time.NS)
                    end = min(end, started + (raw_work_end - raw_started) / job_time.NS)
                    final_end = min(final_end, started + (raw_final_end - raw_started) / job_time.NS)
        invocation = uuid.uuid4().hex
        directory = self.child(self.commands, label, final_end, create=True)
        job = self.context["id"] if canonical_domain else self.job
        state = self.state_path if canonical_domain else self.path
        home = state / ("gradle-home" if canonical_domain else "control-home")
        env = processes.ownership_environment(self.environment, job, invocation, str(state), str(home),
                                              allow_new_context=True)
        if self.profile == "full" and product:
            require(label == "product" and self.simulator_binding is not None, "PRIMARY_SIMULATOR_BINDING_REQUIRED")
            env.update({simulator.PATH_ENV: str(self.path / simulator.RELATIVE),
                        simulator.HASH_ENV: digest(self.simulator_binding)})
        supplement_environment = self.full.environment(label) if supplement is not None or helper else None
        if supplement_environment is not None:
            env.update(supplement_environment)
        if acquire_time:
            require(type(self.actions_token) is str and self.actions_token, "JOB_TIME_READ_TOKEN_REQUIRED")
            env[job_time.TOKEN_ENV], self.actions_token = self.actions_token, None
        row = {"schema": 1, "phase": label, "argv": list(argv), "cwd": str(ROOT), "job": job,
               "invocation": invocation, "state": str(state), "home": str(home), "exitCode": None,
               "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN", "errors": []}
        if timed:
            row.update(jobBudgetSha256=None if self.budget is None else self.budget.sha256,
                       startedRawNs=raw_started, completedRawNs=None, finalizedRawNs=None,
                       cooperativeCancellation=None, developerDir=self.environment.get("DEVELOPER_DIR"),
                       simulatorBindingSha256=None if self.simulator_binding is None else digest(self.simulator_binding),
                       childAncestorInvocationIds=env[processes.CHAIN_ENV].split(":"),
                       canonicalInvocation=canonical_id, supplementPhase=supplement is not None,
                       postReturnHelper=bool(helper), supplementEnvironment=supplement_environment)
            if self.clock is not None:
                row["clock"] = job_time.clock_value(self.clock)
        self.records.append(row)
        before_errors = len(self.errors)
        receipt_complete = False
        scope = child = out = err = None
        native_known = False
        original = None
        cancellation_requested = False

        def check_phase_budget():
            nonlocal cancellation_requested, end
            now = self.now_raw() if timed else None
            cutoff = self.budget is not None and not finalizing and now >= self.budget.fence("productive")
            if cutoff:
                self.mark_cutoff(label, now)
            if (cutoff or self.cancelled) and (not finalizing or packaging):
                if canonical_id is not None and self.active_canonical == canonical_id and not cancellation_requested:
                    # Record the single ATTEMPT before entering the canonical
                    # writer. A failed call is never retried or called a request.
                    cancellation_requested = True
                    cancellation = {"reason": "job-budget" if cutoff else "signal", "job": self.context["id"],
                                    "invocation": canonical_id,
                                    "attemptedRawNs": now, "returnedRawNs": None, "requested": False,
                                    "requestSha256": None}
                    if timed:
                        row["cooperativeCancellation"] = cancellation
                        self.budget_cancellation = cancellation
                    audit.request_cancellation(self.state_path, self.context["id"], canonical_id)
                    cancellation["requested"] = True
                    cancellation["returnedRawNs"] = self.now_raw() if timed else None
                    end = min(end, time.monotonic() + (330 if self.profile == "full" else 225))
                    if timed:
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
                elif canonical_id is None:
                    if cutoff:
                        raise ControllerError("FULL_JOB_PRODUCTIVE_CUTOFF")
                    raise KeyboardInterrupt("ORDINARY_TEST_CONTROLLER_CANCELLED")
            if timed:
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
            if packaging:
                check_cancelled(self.cancelled)
            if timed:
                require(self.now_raw() < raw_work_end, "FULL_JOB_PHASE_EXPIRED")
            row["launchAttempted"] = True
            if product:
                self.product_attempted = True
            child = scope.spawn(list(argv), str(ROOT), env, stdout=out, stderr=err)
            require(child.stdout is None and child.stderr is None, "PRIVATE_SUPPLIED_SINKS_REQUIRED")
            if canonical_id is not None:
                if self.profile == "full":
                    birth = simulator.created_native_launch(scope.description(), 0, list(argv), str(ROOT), job, invocation)
                    require(birth["launch"]["pid"] == child.pid, "CANONICAL_CREATED_PROCESS_REQUIRED")
                # A reservation/spawn attempt is not an executing process. Do
                # not cancel a never-born ID after an exceptional spawn return.
                self.active_canonical = canonical_id
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
                if code is not None:
                    # Consume the actual return BEFORE the next fallible RAW
                    # read/signal check. A still-owned native scope may require
                    # draining, but its returned canonical child is no longer
                    # the cancellation target. The late cutoff still fails it.
                    row["exitCode"] = code
                    self.active_canonical = None
                observed = check_phase_budget()
                posix._deadline(end)
                if code is not None:
                    if timed:
                        row["completedRawNs"] = observed
                    break
                scope.discover()
                time.sleep(.05)
        except BaseException as error:
            original = error
            self.error(label, error)
            if timed and canonical_id is not None and self.active_canonical == canonical_id:
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
            if native_known and not self.unknown:
                self.active_canonical = None
            try:
                if timed:
                    row["finalizedRawNs"] = self.now_raw()
                    require(row["finalizedRawNs"] < raw_final_end, "FULL_JOB_PHASE_FINAL_EXPIRED")
                row["errors"] = self.errors[before_errors:]
                posix._deadline(final_end)
                self.write(directory, "result.json", row, final_end)
                if timed:
                    require(self.now_raw() < raw_final_end, "FULL_JOB_PHASE_FINAL_EXPIRED")
                self.phase_hashes[label] = digest(encoded(row))
                receipt_complete = True
            except BaseException as error:
                self.error(label + "-receipt", error)
        if original is not None:
            raise original
        require(receipt_complete and not self.unknown and len(self.errors) == before_errors and
                not row["errors"], "PHASE_FINALIZATION_FAILED")
        if self.cancelled and (not finalizing or packaging):
            raise KeyboardInterrupt("ORDINARY_TEST_CONTROLLER_CANCELLED")
        require(finalizing or not self.budget_exhausted, "FULL_JOB_PRODUCTIVE_CUTOFF")
        return row

    def python(self, *args):
        executable = str(Path(sys.executable).resolve(strict=True))
        if args and Path(args[0]) == SCRIPTS / "run-audit-command.py":
            return canonical_python(executable, self.canonical_sources, *args[1:])
        return [executable, "-I", "-B", "-S", *map(str, args)]

    def setup(self):
        if self.consume_requested:
            adopt_preparation(self)
        else:
            self.allocate()
            self.admitted = admission(self, self.profile, self.evidence.path / "admission", self.check)
        if self.profile == "full":
            resolved = shutil.which("python3", path=self.environment.get("PATH", ""))
            require(resolved is not None and Path(resolved).resolve(strict=True) == Path(sys.executable).resolve(strict=True),
                    "FULL_PYTHON_DIFFERS_FROM_NATIVE_CONTROLLER")
        original = parse(self.admitted.record)
        self.sample_required = identity.sample_packaging_required(self.admitted)
        require(not self.sample_required or self.consume_requested, "SAMPLE_REQUIRES_QUALIFIED_CONSUME")
        self.kind, self.command = profile_command(self.profile, self.role, package_samples=self.sample_required)
        self.canonical_sources = canonical_bindings()
        if self.profile == "full" and self.budget is None:
            self.acquire_job_time()
        context = {"schema": 1, "scope": "CLOSED_ORDINARY_TEST_CONTROLLER", "profile": self.profile,
                   "role": self.role, "root": str(ROOT), "session": str(self.path), "job": self.job,
                   "admissionSha256": digest(self.admitted.record), "source": original["source"],
                   "command": self.command, "kind": self.kind, "python": str(Path(sys.executable).resolve(strict=True)),
                   "canonicalSources": self.canonical_sources}
        if self.budget is not None:
            context["jobBudgetSha256"] = self.budget.sha256
        if self.consume_requested:
            context.update(dependencyCache=self.cache_binding,
                           jobTimeAcquisitionSha256=digest(self.preparation_raw),
                           developerDir=self.environment.get("DEVELOPER_DIR"),
                           ancestorInvocationIds=self.environment.get(processes.CHAIN_ENV, "").split(":")
                           if self.environment.get(processes.CHAIN_ENV) else [])
        if self.profile == "desktop":
            context["samplePackagingRequired"] = self.sample_required
        if self.profile == "full":
            context.update(primarySimulatorRequired=True, primaryAbiRequired=True,
                           fullSupplementIntent=self.full.intent(),
                           primaryAbiAccounting={"modes": ["productive", "terminal"], "oneShot": True,
                             "productiveCutoffRawNs": self.budget.fence("productive"), "localSeconds": 180},
                           developerDir=self.environment.get("DEVELOPER_DIR"),
                           ancestorInvocationIds=self.environment.get(processes.CHAIN_ENV, "").split(":")
                           if self.environment.get(processes.CHAIN_ENV) else [])
        if self.seed_requested:
            context["dependencySeed"] = self.prepare_seed_intent()
        self.run_context_raw = encoded(context)
        self.write(self.private, "run-context.json", context, self.window("productive", 45))
        if self.consume_requested:
            self.write(cache_directory(self, self.private, self.window("productive", 30)), "controller-context.json",
                       self.run_context_raw, self.window("productive", 30))
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
            self.full.allocate(state)
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
        if self.full is not None:
            self.full.bind_owners()
        if self.seed_requested:
            self.seed_dependencies()  # File-only; does not add a process phase or a new time allowance.
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

    def prepare_seed_intent(self):
        require(os.environ.get("P2PKIT_DEPENDENCY_SEED_STAGE_OUTCOME") == "success" and
                re.fullmatch(r"[0-9a-f]{64}", os.environ.get("P2PKIT_DEPENDENCY_SEED_STAGE_SHA256", "")),
                "SEED_ORIGINAL_STAGE_DID_NOT_SUCCEED")
        end = self.window("productive", 90)
        check = lambda: (self.check(), self.check_window("productive", end))
        path = seed.stage_path(self.path, self.profile, self.role)
        owners, original = seed._Owners(self), None
        try:
            container = owners.acquire("stage-container", lambda: seed.private_root(path))
            source = owners.acquire("stage-source", lambda: seed.public_root(path / "restore-home"))
            staging_raw = self.read(container, "staging.json", end)
            require(digest(staging_raw) == os.environ["P2PKIT_DEPENDENCY_SEED_STAGE_SHA256"],
                    "SEED_ORIGINAL_STAGE_OUTPUT_CHANGED")
            inputs, compiled = seed.source_inputs(self, ROOT, end, check)
            # Existing exact clean-source/native admission, not a new Git blob API.
            admission(self, self.profile, self.runtime.path / "seed-input-admission", check, expected=self.admitted)
            staging = parse(staging_raw)
            seed.validate_stage(staging, self.admitted.record, self.profile, self.role, path,
                                container.verify(), source.verify(), inputs)
            require(staging_raw == seed.encoded(staging), "SEED_STAGE_NOT_CANONICAL")
            self.seed_directory = self.child(self.private, "dependency-seed", end, create=True)
            self.write(self.seed_directory, "staging.json", staging_raw, end)
            self.seed_staging_raw, self.seed_compiled = staging_raw, compiled
            self.seed_intent = seed.seed_intent(self.admitted.record, self.profile, self.role, path, staging_raw, inputs)
            if self.consume_requested:
                binding = consume_binding(self, self.private, self.admitted, self.budget, end,
                                          staging_raw=staging_raw, inputs=inputs, compiled=compiled)
                require(binding == self.cache_binding, "CACHE_ORIGINAL_RESTORE_CHANGED")
        except BaseException as error:
            original = error
            raise
        finally:
            try:
                owners.close()
            except BaseException as error:
                if original is None:
                    raise
                seed._note(original, "stage-inputs", error)
        check()
        return self.seed_intent

    def seed_dependencies(self):
        now = self.now_raw if self.profile == "full" else lambda: int(time.monotonic() * job_time.NS)
        started = now()
        end = self.window("productive", seed.HARD_SECONDS)
        hard = min(started + seed.HARD_SECONDS * job_time.NS,
                   started + int(max(0, self.deadline - time.monotonic()) * job_time.NS))
        if self.profile == "full":
            hard = min(hard, self.budget.fence("productive"))
        # Desktop's copier deliberately retains its process-local representation.
        # The independently bound service-job clock clamps/checks this interval;
        # a Desktop budget hash is NOT a RAW copier-window identity.
        hard = min(hard, started + int(max(0, end - time.monotonic()) * job_time.NS))
        interval = seed.window(started, hard, min(hard, started + seed.SOFT_SECONDS * job_time.NS),
                               raw=self.profile == "full",
                               job_budget=self.budget.sha256 if self.profile == "full" else None)
        def check():
            self.check()
            self.check_window("productive", end)
            require(now() < hard, "SEED_ORIGINAL_WINDOW_EXPIRED")
        try:
            result = seed.seed_home(self, self.state_path / "gradle-home", self.seed_intent,
                parse(self.seed_staging_raw), self.seed_compiled, self.run_context_raw, self.canonical_context_raw,
                self.admitted.record, end=end, check=check, now=now, interval=interval)
            seed.validate_receipt(result, self.seed_intent, self.seed_staging_raw, self.run_context_raw,
                                  self.canonical_context_raw, self.admitted.record, self.seed_compiled)
            require(self.read(self.private, "run-context.json", end) == self.run_context_raw,
                    "SEED_ORIGINAL_CONTEXT_CHANGED")
            raw = seed.encoded(result)
            self.write(self.seed_directory, "manifest.json", raw, end)
            # The closed receipt-only copy precedes ALL product/key-capable
            # writers. Full's later Central secret screen must see this exact
            # inventory; do not add a new post-screen namespace exemption.
            copy_tree(self, self.seed_directory, self.evidence.path / "dependency-seed", end)
            check()  # A late close/write cannot authorize a provisional known manifest.
            self.seed_result = seed.disposition(raw)
            if self.consume_requested:
                require(sum(item["size"] for item in result["admitted"]) > 0,
                        "CACHE_EXACT_HIT_WITHOUT_ADMITTED_BYTES")
        except BaseException as error:
            result = getattr(error, "seed_result", None)
            if result is not None:
                self.seed_result = seed.disposition(seed.encoded(result))
                try:
                    self.write(self.seed_directory, "failure.json", seed.encoded(result), end)
                except BaseException as secondary:
                    self.error("seed-failure-receipt", secondary)
                    seed._note(error, "failure-receipt", secondary)
            raise

    def acquire_job_time(self):
        require(self.budget is None, "JOB_TIME_ALREADY_ADMITTED")
        if self.profile == "desktop":
            reading = job_time.current_reading(self.profile)
            require(reading.clock.role == self.role and reading.nanoseconds >= self.last_raw,
                    "JOB_TIME_NATIVE_CLOCK_CHANGED")
            self.clock, self.last_raw = reading.clock, reading.nanoseconds
        row = self.phase("job-time", self.python(__file__, "_job-time", "--profile", self.profile, "--admission-sha256",
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
        timing = original_clock(budget, self.last_raw)
        self.deadline = min(self.deadline, timing.deadline("controller-return", TOTAL_SECONDS[self.profile]))
        self.last_raw = timing.last
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
        if self.simulator_retirement_attempted:
            return
        self.simulator_retirement_attempted = True
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
        if not self.collect_attempted:
            # Latch BEFORE any I/O. Reentry after failure must not replace the
            # original fixed-path attempt or renew its budget.
            self.collect_attempted = True
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
        if self.custody is None or self.custody.get("retirement") != "KNOWN" or self.uninstall_attempted:
            return
        # Collector125 with original KNOWN may uninstall ONLY its exact loader.
        self.uninstall_attempted = True
        row = self.phase("custody-uninstall", self.python(SCRIPTS / "test-transcript-custody.py", "uninstall",
                         "--directory", directory), 90, finalizing=True)
        require(row["exitCode"] == 0, "CUSTODY_LOADER_UNINSTALL_FAILED")
        end = self.window("uninstall-read", 30)
        private = self.child(self.evidence, "custody", end)
        removed = parse(self.read(private, "uninstalled.json", end))
        self.check_window("uninstall-read", end)
        require(removed.get("absent") is True and removed.get("originalsDeleted") is False,
                "CUSTODY_UNINSTALL_RECEIPT_DIFFERS")

    def package_samples(self):
        """Archive successful Desktop products BEFORE the single evidence freeze.

        No second product/build or post-seal writer. The75s native work and45s
        finalization share one120s ceiling inside the original controller end.
        Packaging originals go into the same encrypted test-evidence packet;
        application bytes remain outside it for separate successful delivery.
        """
        require(self.sample_required and not self.sample_attempted, "SAMPLE_PACKAGING_ONE_SHOT")
        self.sample_attempted = True
        preceding = self.result()
        preceding.pop("samplePackaging")
        require(self.collect_attempted and self.uninstall_attempted and profile_passed(preceding),
                "SAMPLE_PACKAGING_REQUIRES_SUCCESSFUL_RETIRED_PRODUCT")
        self.sample_result["status"] = "FAILED"
        end = self.window("controller-return", job_time.PACKAGE_SECONDS)
        def check():
            self.check(finalizing=True)
            check_cancelled(self.cancelled)
            self.check_window("controller-return", end)
        check()
        row = self.phase("sample-packaging", self.python(SCRIPTS / "package-sample-apps.py", "package", "--output",
            self.path.parent / "p2pkit-sample-apps"), job_time.PACKAGE_SECONDS - FINAL_SECONDS, finalizing=True)
        require(type(row["exitCode"]) is int and row["exitCode"] == 0, "SAMPLE_PACKAGER_FAILED")
        snapshot = sample_snapshot(self, self.path, self.admitted, self.role, end, check)
        raw = encoded({"schema": 1, "scope": "ORIGINAL_PACKAGED_SAMPLES", "contextSha256": self.context_hash,
                       "source": parse(self.admitted.record)["source"], "role": self.role,
                       "phaseSha256": self.phase_hashes["sample-packaging"], "snapshot": snapshot})
        self.write(self.evidence, "sample-packaging.json", raw, end)
        check()
        self.sample_result.update(status="PASS", manifestSha256=digest(raw))

    def primary_barrier_passed(self):
        if (self.profile != "full" or self.errors or self.cancelled or self.unknown or self.budget_exhausted or
                self.active_canonical is not None or not self.collect_attempted or not self.uninstall_attempted or
                not self.simulator_retirement_attempted):
            return False
        labels = ("product", "custody-collect", "custody-uninstall")
        rows = {row["phase"]: row for row in self.records}
        return (all(label in rows and rows[label]["exitCode"] == 0 and rows[label]["retirement"] == "KNOWN" and
                    rows[label]["errors"] == [] for label in labels) and self.custody is not None and
                self.custody.get("result") == "RETAINED" and self.custody.get("errors") == [] and
                self.simulator_terminal is not None and self.simulator_terminal.get("retirement") == "KNOWN" and
                self.simulator_terminal.get("status") == "KNOWN_SHUTDOWN")

    def freeze_end(self):
        # B1 retention and the existing export copies share ONE local and RAW
        # window. Re-entering export never renews a separate180s allowance.
        if self.export_freeze_end is None:
            self.export_freeze_end = self.window("export-freeze", 180)
        self.check_window("export-freeze", self.export_freeze_end)
        return self.export_freeze_end

    def retain_primary_abi(self, *, mode="terminal"):
        if self.profile != "full" or self.request is None or not self.product_attempted:
            return
        require(mode in ("productive", "terminal"), "ABI_ACCOUNTING_MODE")
        require(not self.primary_abi_attempted, "ABI_PRIMARY_RETENTION_IS_ONE_SHOT")
        require(mode != "productive" or self.primary_barrier_passed(), "ABI_PRODUCTIVE_BARRIER_REQUIRED")
        # Latch the one original attempt and truthful unacquired HOLD BEFORE
        # any RAW/clock/window call can fail. Failure must not enable a terminal
        # retry or turn a begun acquisition into an unattempted product.
        self.primary_abi_attempted = True
        self.primary_abi = {"status": "HOLD", "manifestSha256": None, "contextSha256": self.context_hash,
                            "productPhaseSha256": self.phase_hashes.get("product"), "generatedCount": None}
        self.primary_abi_accounting = {"mode": mode, "startedRawNs": None, "finishedRawNs": None,
            "productiveCutoffRawNs": self.budget.fence("productive"), "endRawNs": None, "acquisitionStarted": False,
            "rosterSha256": digest(encoded(parse(self.run_context_raw)["fullSupplementIntent"]))}
        self.check(finalizing=mode == "terminal")
        raw_start = self.now_raw()
        self.primary_abi_accounting["startedRawNs"] = raw_start
        stage = "productive" if mode == "productive" else "export-freeze"
        end = self.window("productive", 180) if mode == "productive" else self.freeze_end()
        self.primary_abi_accounting["endRawNs"] = min(raw_start + 180 * job_time.NS, self.budget.fence(stage))
        def check():
            self.check(finalizing=mode == "terminal")
            self.check_window(stage, end)

        check()
        self.primary_abi_accounting["acquisitionStarted"] = True
        target = self.child(self.evidence, "primary-abi", end, create=True)
        # Every generated byte is separately acquired BEFORE reference reads and
        # before any future supplemental writer. A baseline is never a fallback.
        generated, acquisition = retain_abi_generated(self, target, self.build_owners, end, check)
        check()
        references, queries = abi_references(self, parse(self.admitted.record)["source"]["commit"],
            self.evidence.path / "primary-abi-queries", end, check)
        for index, (_blob, raw) in references.items():
            check()
            self.write(target, abi.member(index, "baseline"), raw, end)
        context_raw = self.read(self.private, "run-context.json", end)
        require(context_raw == self.run_context_raw, "ABI_CONTEXT_CHANGED")
        primary, log = primary_abi_inputs(self, self.private, parse(context_raw), end, check)
        require(primary["productPhaseSha256"] == self.phase_hashes.get("product"), "ABI_PRIMARY_PHASE_CHANGED")
        check()
        self.primary_abi_accounting["finishedRawNs"] = self.now_raw()
        raw = encoded({"schema": 1, "scope": "PRIMARY_FULL_ABI_ORIGINALS", "source": parse(context_raw)["source"],
                       "contextSha256": self.context_hash, "primary": primary, "referenceQueries": queries,
                       "acquisition": acquisition, "assessment": abi.assess(generated, references, log),
                       "accounting": self.primary_abi_accounting})
        self.write(target, "manifest.json", raw, end)
        check()  # A late/failed write keeps the earlier HOLD, not a provisional pass.
        self.primary_abi = abi_disposition(raw)

    def export(self):
        self.check(finalizing=True)
        require(self.admitted is not None and hasattr(self, "recipient_raw"), "NO_VALIDATED_RECIPIENT")
        end = self.freeze_end()
        if self.seed_requested:
            require(seed.profile_passed({"contextSha256": self.context_hash, "dependencySeed": self.seed_result}),
                    "SEED_NOT_COMPLETE_FOR_EXPORT")
        if self.full is not None:
            self.full.freeze(end)
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
        if self.seed_requested:
            require(self.export_return["result"].get("dependencySeedFrozen") ==
                    frozen_seed_packet(self, self.private, end, lambda: self.check_window("export-verify", end)),
                    "SEED_ORIGINAL_EXPORT_RETURN_DIFFERS")
        if self.consume_requested:
            require(self.export_return["result"].get("dependencyCacheFrozen") ==
                    frozen_consume_packet(self, self.private, end, lambda: self.check_window("export-verify", end)),
                    "CACHE_ORIGINAL_EXPORT_RETURN_DIFFERS")
        if self.sample_required and self.sample_result["status"] == "PASS":
            require(self.export_return["result"].get("samplePackagingFrozen") ==
                    frozen_package_packet(self, self.private, end, lambda: self.check_window("export-verify", end)),
                    "SAMPLE_ORIGINAL_EXPORT_RETURN_DIFFERS")
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
            if self.budget is not None:
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
        if self.budget is not None or self.profile == "full":
            value["jobBudget"] = self.budget_result()
        if self.consume_requested:
            value["dependencyCache"] = self.cache_binding
        if self.sample_required:
            value["samplePackaging"] = self.sample_result
        if self.profile == "full":
            value["primaryAbi"] = self.primary_abi
            value["primaryAbiAccounting"] = self.primary_abi_accounting
            value["fullSupplements"] = self.full.result()
            value["simulator"] = {"admissionSha256": None if self.simulator_admission is None else
                                  digest(self.simulator_admission),
                                  "bindingSha256": None if self.simulator_binding is None else digest(self.simulator_binding),
                                  "selected": self.simulator, "terminal": self.simulator_terminal}
        if self.seed_requested:
            value["dependencySeed"] = self.seed_result
        value["profilePassed"] = profile_passed(value)
        return parse(encoded(value))


def profile_passed(value):
    """A boolean label cannot overrule original phase/custody outcomes."""
    if not seed.profile_passed(value):
        return False
    rows = value["phases"]
    labels = ["recipient-validation", "audit-init", "custody-prepare", "product", "custody-collect",
              "custody-uninstall"]
    if value.get("profile") == "desktop" and "jobBudget" in value:
        labels.insert(0, "job-time")
        budget = value["jobBudget"]
        if not (type(budget.get("sha256")) is str and re.fullmatch(r"[0-9a-f]{64}", budget["sha256"]) and
                budget.get("exhausted") is False and budget.get("cutoffObservation") is None and
                budget.get("cooperativeCancellation") is None):
            return False
        for row in rows:
            if row["phase"] == "job-time":
                continue
            if row.get("jobBudgetSha256") != budget["sha256"]:
                return False
            if row["phase"] in labels[1:5] and not (type(row.get("completedRawNs")) is int and
                    type(budget.get("productiveCutoffRawNs")) is int and
                    row["completedRawNs"] < budget["productiveCutoffRawNs"]):
                return False
    if value.get("profile") == "full":
        if not supplements.profile_passed(value):
            return False
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
        labels.extend(supplements.passing_labels(value))
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
                                 *simulator.PREPARE, simulator.PRELAUNCH, *supplements.PRODUCTIVE} and not (
                    type(row.get("completedRawNs")) is int and type(budget.get("productiveCutoffRawNs")) is int and
                    row["completedRawNs"] < budget["productiveCutoffRawNs"]):
                return False
    if value["encrypted"]:
        labels.append("export")
    if "samplePackaging" in value:
        packaged = value["samplePackaging"]
        if not (value.get("profile") == "desktop" and type(packaged) is dict and
                set(packaged) == {"required", "status", "manifestSha256"} and packaged["required"] is True and
                packaged["status"] == "PASS" and type(packaged["manifestSha256"]) is str and
                re.fullmatch(r"[0-9a-f]{64}", packaged["manifestSha256"])):
            return False
        labels.insert(labels.index("export") if "export" in labels else len(labels), "sample-packaging")
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


PREPARATION_SCOPE = "ORIGINAL_CONSUME_ONLY_ACQUISITION"
PREPARATION_DIRECTORIES = ("evidence", "runtime", "crypto", "temporary", "control-home")
PREPARATION_KEYS = {"schema", "scope", "profile", "role", "session", "sessionIdentity", "directories",
                    "source", "github", "admissionSha256", "job", "jobBudgetSha256", "phaseResultSha256",
                    "planSha256", "stagingSha256", "restoreWindow", "completedRawNs", "pid", "retirement"}


def append_outputs(value, check):
    """Step success, including final close/deadline, is required by every caller."""
    require(type(value) is str and value.endswith("\n"), "OUTPUT_RECORD")
    target = Path(os.environ["GITHUB_OUTPUT"])
    audit.reject_symlinks(target)
    check()
    with target.open("a", encoding="utf-8") as output:
        output.write(value)
        output.flush()
        os.fsync(output.fileno())
    check()


def cache_directory(owner, private, end):
    return owner.child(owner.child(private, "evidence", end), "dependency-cache", end)


def read_preparation(owner, private, admitted, budget, end):
    """Rebind the original pre-tool process, not its UUID as a new owner."""
    directory = cache_directory(owner, private, end)
    raw = owner.read(directory, "preparation.json", end)
    value, record = parse(raw), parse(admitted.record)
    require(set(value) == PREPARATION_KEYS and type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == PREPARATION_SCOPE and value["profile"] == budget.profile == record["profile"] and
            value["source"] == record["source"] and value["github"] == record["github"] and
            value["admissionSha256"] == digest(admitted.record) and value["session"] == str(private.path) and
            value["sessionIdentity"] == list(private.identity) and value["retirement"] == "KNOWN" and
            type(value["pid"]) is int and value["pid"] > 0 and value["jobBudgetSha256"] == budget.sha256 and
            value["job"] == budget.value["provenance"]["controllerJob"] and
            value["phaseResultSha256"] == budget.value["provenance"]["phaseResultSha256"] and
            value["role"] in INSTALLERS and value["session"] == str(session_path(value["profile"], value["role"])) and
            (budget.clock is None or value["role"] == budget.clock.role) and
            record["github"]["runnerOS"] == ("Linux" if value["role"].startswith("linux-") else
                "Windows" if value["role"].startswith("windows-") else "macOS") and
            record["github"]["runnerArch"] == ("ARM64" if value["role"] == "macos-arm64" else "X64"),
            "CACHE_ORIGINAL_PREPARATION_CHANGED")
    require(type(value["directories"]) is dict and set(value["directories"]) == set(PREPARATION_DIRECTORIES),
            "CACHE_PREPARATION_DIRECTORY_ROSTER")
    private.verify()
    for name, original in value["directories"].items():
        current = owner.child(private, name, end)
        current.verify()
        require(list(current.identity) == original, "CACHE_PREPARATION_DIRECTORY_REPLACED")
    plan_raw, stage_raw = (owner.read(directory, name, end) for name in ("plan.json", "staging.json"))
    require(digest(plan_raw) == value["planSha256"] and digest(stage_raw) == value["stagingSha256"] and
            raw == encoded(value), "CACHE_PREPARATION_INPUT_CHANGED")
    phase = owner.child(owner.child(owner.child(private, "evidence", end), "commands", end), "job-time", end)
    phase_raw = owner.read(phase, "result.json", end)
    require(digest(phase_raw) == value["phaseResultSha256"], "CACHE_PREPARATION_PHASE_CHANGED")
    finalized = parse(phase_raw).get("finalizedRawNs")
    interval = value["restoreWindow"]
    require(type(interval) is dict and set(interval) == {"beganRawNs", "endRawNs", "timeoutMinutes"} and
            all(type(interval[key]) is int for key in interval) and type(value["completedRawNs"]) is int and
            type(finalized) is int and budget.value["responseFinishedRawNs"] <= finalized <=
                value["completedRawNs"] == interval["beganRawNs"] <
                interval["endRawNs"] <= budget.fence("productive") and
            interval["endRawNs"] == min(budget.fence("productive"), interval["beganRawNs"] + 180 * job_time.NS) and
            interval["timeoutMinutes"] == (interval["endRawNs"] - interval["beganRawNs"]) // (60 * job_time.NS) and
            1 <= interval["timeoutMinutes"] <= 3, "CACHE_ORIGINAL_RESTORE_WINDOW_CHANGED")
    return raw


def consume_binding(owner, private, admitted, budget, end, *, staging_raw=None, inputs=None, compiled=None):
    prepared_raw = read_preparation(owner, private, admitted, budget, end)
    directory = cache_directory(owner, private, end)
    plan_raw, original_stage, provider_raw, restored_raw = (owner.read(directory, name, end) for name in
        ("plan.json", "staging.json", "provider.json", "restoration.json"))
    prepared, plan, provider, restored = map(parse, (prepared_raw, plan_raw, provider_raw, restored_raw))
    require(digest(plan_raw) == prepared["planSha256"] and digest(original_stage) == prepared["stagingSha256"],
            "CACHE_PREPARATION_INPUT_CHANGED")
    if compiled is None:
        inputs, compiled = seed.source_inputs(owner, ROOT, end, lambda: posix._deadline(end))
    require(staging_raw is None or original_stage == staging_raw, "CACHE_RESTORED_STAGE_CHANGED")
    cache.validate_plan(plan, admitted.record, original_stage, compiled, inputs, session=private.path,
                        profile=prepared["profile"], role=prepared["role"], mode="consume")
    cache.validate_provider_observation(provider, plan, "restore")
    require(provider["status"] == "REPORTED_EXACT_HIT", "CACHE_NO_QUALIFIED_EXACT_HIT")
    expected = {"schema": 1, "scope": "ORIGINAL_EXACT_CACHE_RESTORE", "preparationSha256": digest(prepared_raw),
                "planSha256": digest(plan_raw), "stagingSha256": digest(original_stage),
                "providerSha256": digest(provider_raw), "jobBudgetSha256": budget.sha256,
                "source": prepared["source"], "github": prepared["github"], "retirement": "KNOWN"}
    require(set(restored) == set(expected) | {"observedRawNs"} and
            all(restored[key] == value for key, value in expected.items()) and
            type(restored["observedRawNs"]) is int and
            prepared["completedRawNs"] <= restored["observedRawNs"] < prepared["restoreWindow"]["endRawNs"] and
            all(raw == encoded(value) for raw, value in ((plan_raw, plan), (provider_raw, provider),
                                                         (restored_raw, restored))),
            "CACHE_ORIGINAL_RESTORE_RECEIPT_CHANGED")
    return {"scope": "CONSUME_ONLY_ORIGINALS", "preparationSha256": digest(prepared_raw),
            "restorationSha256": digest(restored_raw), "planSha256": digest(plan_raw),
            "providerSha256": digest(provider_raw), "stagingSha256": digest(original_stage),
            "restoredAtRawNs": restored["observedRawNs"]}


def adopt_preparation(controller):
    """Adopt successful original observations, never a prior controller identity."""
    require(os.environ.get("P2PKIT_HOSTED_PREPARE_OUTCOME") == "success" and
            os.environ.get("P2PKIT_CACHE_GUARD_OUTCOME") == "success", "CACHE_ORIGINAL_STEPS_REQUIRED")
    end = min(controller.deadline, time.monotonic() + 90)
    controller.private = controller.open(controller.path)
    for name in ("evidence", "runtime", "crypto"):
        setattr(controller, name, controller.child(controller.private, name, end))
    controller.commands = controller.child(controller.evidence, "commands", end)
    controller.admitted = load_admission(controller, controller.child(controller.evidence, "admission", end), end)
    budget = derive_job_budget(controller, controller.private, controller.admitted, end)
    prepared_raw = read_preparation(controller, controller.private, controller.admitted, budget, end)
    prepared = parse(prepared_raw)
    require(digest(prepared_raw) == os.environ.get("P2PKIT_HOSTED_PREPARE_SHA256") and
            prepared["role"] == controller.role and prepared["pid"] != os.getpid() and
            prepared["job"] != controller.job, "CACHE_PREPARATION_REPLAYED_OR_CHANGED")
    controller.cache_binding = consume_binding(controller, controller.private, controller.admitted, budget, end)
    require(controller.cache_binding["restorationSha256"] == os.environ.get("P2PKIT_CACHE_RESTORATION_SHA256"),
            "CACHE_ORIGINAL_RESTORE_OUTPUT_CHANGED")
    controller.budget, controller.clock, controller.preparation_raw = budget, budget.clock, prepared_raw
    timing = original_clock(budget, prepared["completedRawNs"], controller.cache_binding["restoredAtRawNs"])
    controller.last_raw = timing.last
    controller.deadline = min(controller.deadline, timing.deadline("controller-return", TOTAL_SECONDS[controller.profile]))
    controller.last_raw = timing.last
    controller.check()
    end = min(end, controller.window("productive", 90))
    original = controller.child(controller.evidence, "job-time", end)
    require(controller.read(original, "budget.json", end) == budget.record and
            controller.read(original, "child-return.json", end) ==
                controller.read(controller.runtime, "job-time-result.json", end), "CACHE_ORIGINAL_BUDGET_CHANGED")
    admission(controller, controller.profile, controller.runtime.path / "adoption-admission", controller.check,
              expected=controller.admitted)
    original_phase = controller.child(controller.commands, "job-time", end)
    phase_raw = controller.read(original_phase, "result.json", end)
    controller.records.append(parse(phase_raw))
    controller.phase_hashes["job-time"] = digest(phase_raw)
    controller.check()


def prepare_consume(profile, *, cancelled=None):
    """Native, source-bound pre-tool acquisition. No Gradle, restore or cache save."""
    controller, error, outputs = None, None, None
    try:
        controller = Controller(profile, preflight=True)
        controller.cancelled = [] if cancelled is None else cancelled
        controller.check()
        controller.allocate()
        controller.admitted = admission(controller, profile, controller.evidence.path / "admission", controller.check)
        controller.acquire_job_time()
        end = controller.window("productive", 120)
        check = lambda: (controller.check(), controller.check_window("productive", end))
        path = seed.stage_path(controller.path, profile, controller.role)
        stage = controller.acquire("cache-stage", lambda: seed.private_root(path, create=True))
        source = controller.acquire("cache-restore-home", lambda: stage.create_directory("restore-home", deadline=end))
        inputs, compiled = seed.source_inputs(controller, ROOT, end, check)
        admission(controller, profile, controller.runtime.path / "cache-source-admission", check,
                  expected=controller.admitted)
        staging_raw = seed.encoded(seed.stage_record(controller.admitted.record, profile, controller.role, path,
                                                     stage.verify(), source.verify(), inputs))
        controller.write(stage, "staging.json", staging_raw, end)
        directory = controller.child(controller.evidence, "dependency-cache", end, create=True)
        plan = cache.make_plan(controller.admitted.record, staging_raw, compiled, inputs, session=controller.path,
                               profile=profile, role=controller.role, mode="consume")
        plan_raw = encoded(plan)
        controller.write(directory, "plan.json", plan_raw, end)
        controller.write(directory, "staging.json", staging_raw, end)
        now = controller.now_raw()
        fence = min(controller.budget.fence("productive"), now + 180 * job_time.NS)
        minutes = (fence - now) // (60 * job_time.NS)
        require(1 <= minutes <= 3, "CACHE_RESTORE_WINDOW_EXHAUSTED")
        record = parse(controller.admitted.record)
        prepared_raw = encoded({"schema": 1, "scope": PREPARATION_SCOPE, "profile": profile, "role": controller.role,
            "session": str(controller.path), "sessionIdentity": list(controller.private.identity),
            "directories": {name: list(controller.child(controller.private, name, end).identity)
                            for name in PREPARATION_DIRECTORIES},
            "source": record["source"], "github": record["github"], "admissionSha256": digest(controller.admitted.record),
            "job": controller.job, "jobBudgetSha256": controller.budget.sha256,
            "phaseResultSha256": controller.phase_hashes["job-time"], "planSha256": digest(plan_raw),
            "stagingSha256": digest(staging_raw), "restoreWindow": {"beganRawNs": now, "endRawNs": fence,
                                                                   "timeoutMinutes": minutes},
            "completedRawNs": now, "pid": os.getpid(), "retirement": "KNOWN"})
        controller.write(directory, "preparation.json", prepared_raw, end)
        require(read_preparation(controller, controller.private, controller.admitted, controller.budget, end) ==
                prepared_raw, "CACHE_PREPARATION_FINAL_READBACK_CHANGED")
        outputs = ("dependency_seed_ready=true\ndependency_seed_home=" + plan["restoreHome"] +
                   "\ndependency_seed_staging_sha256=" + digest(staging_raw) + "\ncache_key=" + plan["key"] +
                   "\ncache_path=" + plan["path"] + "\npreparation_sha256=" + digest(prepared_raw) +
                   "\ncache_restore_timeout_minutes=" + str(minutes) + "\n")
    except BaseException as caught:
        error = caught
        if controller is not None:
            controller.error("prepare-consume", caught)
    finally:
        if controller is not None:
            controller.actions_token = None
            try:
                controller.close()
            except BaseException as caught:
                error = error or caught
    if error is not None:
        raise error
    require(controller is not None and not controller.unknown and not controller.errors and outputs is not None,
            "CACHE_PREPARATION_NOT_RETURNED")
    def final_check():
        controller.check()
        controller.check_window("productive", end)
        require(controller.now_raw() < fence, "CACHE_RESTORE_WINDOW_EXHAUSTED")
    append_outputs(outputs, final_check)
    print("DEPENDENCY_CACHE=CONSUME_PREPARED; RESTORE_AND_PRODUCT=NOT_RUN")


def restore_guard(profile, *, cancelled=None):
    """Original action outcome + exact key; a miss never becomes a cold product."""
    require(os.environ.get("P2PKIT_HOSTED_PREPARE_OUTCOME") == "success" and job_time.TOKEN_ENV not in os.environ,
            "CACHE_PREPARATION_NOT_SUCCESSFUL")
    owner, error, outputs, clock, fence = PrivateOwner(), None, None, None, None
    end = time.monotonic() + job_time.TRANSITION_SECONDS
    def check():
        check_cancelled(cancelled)
        posix._deadline(end)
        require(not owner.unknown and clock.check("productive") < fence, "CACHE_RESTORE_EXPIRED")
    try:
        role = processes.host_role()
        private = owner.open(session_path(profile, role))
        evidence = owner.child(private, "evidence", end)
        admitted = load_admission(owner, owner.child(evidence, "admission", end), end)
        budget = derive_job_budget(owner, private, admitted, end)
        prepared_raw = read_preparation(owner, private, admitted, budget, end)
        prepared = parse(prepared_raw)
        require(prepared["role"] == role and digest(prepared_raw) == os.environ.get("P2PKIT_HOSTED_PREPARE_SHA256"),
                "CACHE_PREPARATION_OUTPUT_CHANGED")
        clock = original_clock(budget, prepared["completedRawNs"])
        fence = prepared["restoreWindow"]["endRawNs"]
        end = min(end, original_deadline(clock, "productive", fence, job_time.TRANSITION_SECONDS))
        check()
        directory = cache_directory(owner, private, end)
        plan_raw, stage_raw = (owner.read(directory, name, end) for name in ("plan.json", "staging.json"))
        plan = parse(plan_raw)
        inputs, compiled = seed.source_inputs(owner, ROOT, end, check)
        cache.validate_plan(plan, admitted.record, stage_raw, compiled, inputs, session=private.path,
                            profile=profile, role=role, mode="consume")
        observed = cache.provider_observation(plan, "restore", original_outcome=os.environ.get(
            "P2PKIT_CACHE_RESTORE_OUTCOME", ""), outputs={
                "cache-primary-key": os.environ.get("P2PKIT_CACHE_RESTORE_PRIMARY_KEY", ""),
                "cache-matched-key": os.environ.get("P2PKIT_CACHE_RESTORE_MATCHED_KEY", ""),
                "cache-hit": os.environ.get("P2PKIT_CACHE_RESTORE_HIT", "")})
        provider_raw = encoded(observed)
        owner.write(directory, "provider.json", provider_raw, end)  # Failed originals remain failed.
        check()
        require(observed["status"] == "REPORTED_EXACT_HIT", "CACHE_NO_QUALIFIED_EXACT_HIT")
        path = seed.stage_path(private.path, profile, role)
        stage = owner.acquire("cache-stage-original", lambda: seed.private_root(path))
        source = owner.acquire("cache-restored-original", lambda: seed.public_root(path / "restore-home"))
        seed.validate_stage(parse(stage_raw), admitted.record, profile, role, path, stage.verify(), source.verify(), inputs)
        require(owner.read(stage, "staging.json", end) == stage_raw, "CACHE_STAGE_REPLACED")
        admission(owner, profile, private.path / "restore-admission", check, expected=admitted)
        raw = encoded({"schema": 1, "scope": "ORIGINAL_EXACT_CACHE_RESTORE", "preparationSha256": digest(prepared_raw),
            "planSha256": digest(plan_raw), "stagingSha256": digest(stage_raw), "providerSha256": digest(provider_raw),
            "jobBudgetSha256": budget.sha256, "source": prepared["source"], "github": prepared["github"],
            "observedRawNs": clock.check("productive"), "retirement": "KNOWN"})
        owner.write(directory, "restoration.json", raw, end)
        consume_binding(owner, private, admitted, budget, end, staging_raw=stage_raw, inputs=inputs, compiled=compiled)
        check()
        outputs = "dependency_cache_ready=true\nrestoration_sha256=" + digest(raw) + "\n"
    except BaseException as caught:
        error = caught
        owner.error("cache-restore-guard", caught)
    finally:
        try:
            owner.close()
        except BaseException as caught:
            error = error or caught
    if error is not None:
        raise error
    require(not owner.unknown and outputs is not None, "CACHE_RESTORE_NOT_RETURNED")
    append_outputs(outputs, check)
    print("DEPENDENCY_CACHE=REPORTED_EXACT_HIT; FILE_AND_RESOLVER_ADMISSION=STILL_REQUIRED")


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
    profile = parse(admitted.record)["profile"]
    clock = job_time.clock_identity(row.get("clock")) if profile == "desktop" else None
    require((clock is None and "clock" not in start and "clock" not in row) or
            start.get("clock") == row.get("clock"), "JOB_TIME_PHASE_CLOCK_CHANGED")
    expected = [str(Path(sys.executable).resolve(strict=True)), "-I", "-B", "-S", str(Path(__file__)), "_job-time",
                "--profile", profile, "--admission-sha256", digest(admitted.record)]
    require(start["phase"] == row["phase"] == "job-time" and start["argv"] == row["argv"] == expected and
            start["cwd"] == row["cwd"] == str(ROOT) and start["job"] == row["job"] and
            start["invocation"] == row["invocation"] and start["state"] == row["state"] == str(private.path) and
            start["home"] == row["home"] == str(private.path / "control-home") and
            type(row["exitCode"]) is int and row["exitCode"] == 0 and row["retirement"] == "KNOWN" and
            row["launchAttempted"] is True and row["scopeAttempted"] is True and row["errors"] == [] and
            row.get("survivors") == [] and row.get("jobBudgetSha256") is None and
            row.get("cooperativeCancellation") is None, "JOB_TIME_ORIGINAL_PHASE_CHANGED")
    ownership = row["ownership"]
    backend = ("darwin-libproc-audit-token" if clock is None or clock.role.startswith("macos-") else
               "linux-proc-pidfd" if clock.role == "linux-x64" else "windows-job-list-suspended")
    require(ownership["backend"] == backend and ownership["job"] == row["job"] and
            ownership["invocation"] == row["invocation"] and ownership["discoveryErrors"] == [] and
            ownership["launches"] and ownership["startedIdentities"], "JOB_TIME_NATIVE_PHASE_REQUIRED")
    require(type(returned.get("schema")) is int and returned["schema"] == (1 if clock is None else 2) and
            returned.get("scope") == "ORDINARY_" + profile.upper() + "_JOB_TIME_ACQUISITION" and
            returned.get("returned") is True and
            returned.get("retirement") == "KNOWN" and returned.get("errors") == [] and
            returned.get("admissionSha256") == digest(admitted.record) and returned.get("job") == row["job"] and
            returned.get("invocation") == row["invocation"] and
            returned.get("clockDomain") == (job_time.RAW_CLOCK_DOMAIN if clock is None else clock.domain) and
            (clock is None and "clock" not in returned or returned.get("clock") == job_time.clock_value(clock)),
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
    provenance = {"controllerJob": row["job"], "invocation": row["invocation"],
        "phaseStartSha256": digest(start_raw), "phaseResultSha256": digest(phase_raw),
        "childReturnSha256": digest(returned_raw), "runnerName": returned.get("runnerName")}
    return job_time.derive(admitted, raw, provenance, clock=clock) if clock is not None else job_time.derive(
        admitted, raw, provenance)


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
    require(raw == budget.record and digest(raw) == context.get("jobBudgetSha256"), "IMMUTABLE_JOB_TIME_CHANGED")
    if "jobTimeAcquisitionSha256" in context:
        prepared_raw = read_preparation(owner, private, admitted, budget, end)
        require(digest(prepared_raw) == context["jobTimeAcquisitionSha256"] and
                context.get("dependencyCache", {}).get("preparationSha256") == digest(prepared_raw) and
                parse(prepared_raw)["job"] != context["job"], "JOB_TIME_ADOPTION_CHANGED")
    else:
        require(budget.value["provenance"]["controllerJob"] == context["job"], "IMMUTABLE_JOB_TIME_CHANGED")
    return budget


def job_time_phase(profile, admission_hash):
    """One closed read-only child; the token never enters ordinary/Git children."""
    token = os.environ.pop(job_time.TOKEN_ENV, None)
    owner = PrivateOwner()
    clock, last, began = None, 0, None
    def now(minimum=0):
        nonlocal last
        floor = max(last, job_time.integer(minimum))
        last = job_time.raw_now(floor) if clock is None else job_time.raw_now(floor, clock=clock)
        return last
    end = time.monotonic() + job_time.ACQUIRE_SECONDS
    runtime = None
    error, returned, terminal = None, None, False
    try:
        require(profile in PRODUCT_SECONDS, "JOB_TIME_PROFILE")
        if profile == "desktop":
            reading = job_time.current_reading(profile)
            clock, last = reading.clock, reading.nanoseconds
            began = last
        else:
            began = now()
        inherited = query._inherited_context()
        require(set(inherited) == set(query._CONTEXT), "JOB_TIME_REQUIRES_EXISTING_NATIVE_OWNER")
        role = processes.host_role()
        require(role in INSTALLERS and (profile != "full" or role.startswith("macos-")), "JOB_TIME_NATIVE_ROLE")
        path = session_path(profile, role)
        private = owner.open(path)
        runtime = owner.child(private, "runtime", end)
        evidence = owner.child(private, "evidence", end)
        original = owner.child(evidence, "admission", end)
        admitted = load_admission(owner, original, end)
        require(digest(admitted.record) == admission_hash, "JOB_TIME_ADMISSION_CHANGED")
        record, _, _, _ = job_time.admitted_identity(admitted)
        require(record["github"]["runnerArch"] == ("ARM64" if role == "macos-arm64" else "X64") and
                (clock is None or clock.role == role),
                "JOB_TIME_NATIVE_ARCH_CHANGED")
        commands = owner.child(evidence, "commands", end)
        phase = owner.child(commands, "job-time", end)
        start = parse(owner.read(phase, "start.json", end))
        domain = processes.ownership_domains(inherited[processes.CHAIN_ENV], inherited[processes.DOMAINS_ENV])[-1]
        require(start["job"] == domain["job"] and start["invocation"] == domain["id"] and
                start["state"] == domain["state"] == str(path) and
                start["home"] == domain["home"] == str(path / "control-home") and start["cwd"] == str(ROOT) and
                start["phase"] == "job-time" and
                ("clock" not in start if clock is None else start.get("clock") == job_time.clock_value(clock)),
                "JOB_TIME_ORIGINAL_NATIVE_DOMAIN_CHANGED")
        require(start.get("jobBudgetSha256") is None and
                job_time.integer(start.get("startedRawNs")) <= began,
                "JOB_TIME_PRECEDES_ORIGINAL_NATIVE_START")
        require(now() < began + job_time.ACQUIRE_SECONDS * job_time.NS, "JOB_TIME_ACQUISITION_EXPIRED")
        directory = owner.child(evidence, "job-time", end, create=True)
        retain = lambda label, value: owner.write(directory, label + ".json", value, end)
        raw, acquired_at = job_time.acquire(admitted, domain["id"], token, retain, clock=clock, minimum=last)
        returned = {"schema": 1, "scope": "ORDINARY_" + profile.upper() + "_JOB_TIME_ACQUISITION",
                    "admissionSha256": admission_hash,
                    "job": domain["job"], "invocation": domain["id"], "runnerName": os.environ.get("RUNNER_NAME"),
                    "clockDomain": job_time.RAW_CLOCK_DOMAIN if clock is None else clock.domain,
                    "completedRawNs": now(job_time.integer(acquired_at, last)),
                    "originalsSha256": {label: digest(value) for label, value in raw.items()}}
        if clock is not None:
            returned.update(schema=2, clock=job_time.clock_value(clock))
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
    try:
        posix._deadline(end)
        if began is not None:
            require(now() < began + job_time.ACQUIRE_SECONDS * job_time.NS, "JOB_TIME_ACQUISITION_EXPIRED")
    except BaseException as caught:
        owner.error("job-time-final-deadline", caught)
        error = error or caught
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
        if "jobBudgetSha256" in context:
            budget = load_job_budget(owner, private, admitted, context, end)
            require(started.get("phase") == ("recipient-validation" if operation == "validate" else "export") and
                    started.get("jobBudgetSha256") == budget.sha256 and
                    ("clock" not in started if budget.clock is None else
                     started.get("clock") == job_time.clock_value(budget.clock)),
                    "CRYPTO_ORIGINAL_BUDGET_CLOCK_CHANGED")
            observations = [started.get("startedRawNs")]
            if "dependencyCache" in context:
                bound = consume_binding(owner, private, admitted, budget, end)
                require(bound == context["dependencyCache"] and
                        type(started.get("startedRawNs")) is int and
                        started["startedRawNs"] >= bound["restoredAtRawNs"],
                        "CRYPTO_PRECEDES_ORIGINAL_RESTORE")
                observations.append(bound["restoredAtRawNs"])
            budget_clock = original_clock(budget, *observations)
            end = min(end, budget_clock.deadline("productive" if operation == "validate" else "export", 210))
        work = owner.child(private, "crypto", end)
        checked = admission(owner, profile, runtime.path / (operation + "-admission"),
                            check_crypto, expected=admitted)
        if operation == "validate":
            if "dependencySeed" in context:
                dependency_seed_intent(owner, private, checked, raw, end, check_crypto)
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
            seed_frozen = (frozen_seed_packet(owner, private, end, check_crypto)
                           if "dependencySeed" in context else None)
            cache_frozen = (frozen_consume_packet(owner, private, end, check_crypto)
                            if "dependencyCache" in context else None)
            before = parse(owner.read(evidence, "profile-result-before-export.json", end))
            package_frozen = (frozen_package_packet(owner, private, end, check_crypto)
                              if before.get("samplePackaging", {}).get("status") == "PASS" else None)
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
                if seed_frozen is not None:
                    require(frozen_seed_packet(owner, private, end, check_crypto) == seed_frozen,
                            "SEED_CHANGED_DURING_ORIGINAL_EXPORT")
                    exported["dependencySeedFrozen"] = seed_frozen
                if cache_frozen is not None:
                    require(frozen_consume_packet(owner, private, end, check_crypto) == cache_frozen,
                            "CACHE_CHANGED_DURING_ORIGINAL_EXPORT")
                    exported["dependencyCacheFrozen"] = cache_frozen
                if package_frozen is not None:
                    require(frozen_package_packet(owner, private, end, check_crypto) == package_frozen,
                            "SAMPLE_CHANGED_DURING_ORIGINAL_EXPORT")
                    exported["samplePackagingFrozen"] = package_frozen
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


def run(profile, *, seed_dependencies=False, consume_dependencies=False):
    controller, result, terminal = None, None, False
    handlers, cancelled = {}, []
    original = None
    try:
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handlers[number] = signal.getsignal(number)
            signal.signal(number, lambda value, _frame: cancelled.append(value))
        controller = (Controller(profile, consume_dependencies=True) if consume_dependencies else
                      Controller(profile, seed_dependencies=True) if seed_dependencies else Controller(profile))
        controller.cancelled = cancelled
        controller.check()
        controller.setup()
        controller.product_run()
        if profile == "full":
            controller.collect()
            controller.retire_simulator()
            controller.check()
            require(controller.primary_barrier_passed(), "FULL_PRIMARY_BARRIER_NOT_PASSING")
            controller.retain_primary_abi(mode="productive")
            require(controller.primary_abi["status"] == "PASS", "FULL_PRIMARY_ABI_NOT_PASSING")
            controller.full.run()
        elif controller.sample_required:
            controller.collect()
            controller.package_samples()
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
                    if name != "retain_primary_abi" or not controller.primary_abi_attempted:
                        getattr(controller, name)()
                except BaseException as error:
                    controller.error(name, error)
                    original = original or error
            try:
                if controller.budget is not None:
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
    if ready and controller.budget is not None:
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
    full = result["profile"] == "full"
    order = FULL_ORDER if full else DESKTOP_ORDER
    preparatory = FULL_PREPARATION if full else DESKTOP_ORDER[:5]
    require(type(result["phases"]) is list and len(result["phases"]) <= (len(order) if budget is not None else 7) and
            len({row["phase"] for row in result["phases"]}) == len(result["phases"]), "PHASE_SET_CHANGED")
    require(set(result["phaseSha256"]) == {row["phase"] for row in result["phases"]}, "PHASE_BINDING_SET")
    if budget is not None:
        labels = [row["phase"] for row in result["phases"]]
        preparation = [label for label in labels if label in preparatory]
        require(all(label in order for label in labels) and labels and labels[-1] == "export" and
                labels == sorted(labels, key=order.index) and preparation and
                preparation == list(preparatory[:len(preparation)]) and
                ("custody-collect" not in labels or "custody-prepare" in preparation) and
                ("custody-uninstall" not in labels or "custody-collect" in labels), "PHASE_SEQUENCE_CHANGED")
    previous_raw = None
    for row in result["phases"]:
        label = row["phase"]
        allowed = set(order) if budget is not None else {
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
                         "childAncestorInvocationIds", "canonicalInvocation", "supplementPhase", "postReturnHelper",
                         "supplementEnvironment")), "PHASE_RAW_START_CHANGED")
            require(row["developerDir"] == context.get("developerDir"), "PHASE_DEVELOPER_DIR_CHANGED")
            require(row["childAncestorInvocationIds"] == context["ancestorInvocationIds"] + [row["invocation"]],
                    "PHASE_NATIVE_ANCESTORS_CHANGED")
            if not full:
                require(start.get("clock") == row.get("clock") == job_time.clock_value(budget.clock) and
                        row.get("simulatorBindingSha256") is None and row.get("supplementPhase") is False and
                        row.get("postReturnHelper") is False and row.get("supplementEnvironment") is None,
                        "DESKTOP_PHASE_CLOCK_OR_SCOPE_CHANGED")
                if label == "sample-packaging":
                    require(context.get("samplePackagingRequired") is True and
                            row["argv"] == [context["python"], "-I", "-B", "-S",
                                str(SCRIPTS / "package-sample-apps.py"), "package", "--output",
                                str(private.path.parent / "p2pkit-sample-apps")] and
                            row["job"] == context["job"] and row["state"] == str(private.path) and
                            row["home"] == str(private.path / "control-home") and row["canonicalInvocation"] is None and
                            row["finalizedRawNs"] < row["startedRawNs"] + job_time.PACKAGE_SECONDS * job_time.NS,
                            "SAMPLE_PACKAGING_COMMAND_OR_BOUND_CHANGED")
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
                if "dependencyCache" in context:
                    require(row["startedRawNs"] >= context["dependencyCache"]["restoredAtRawNs"],
                            "PHASE_PRECEDES_ORIGINAL_RESTORE")
            if full:
                supplements.verify_phase_role(owner, globals(), private, row, result, context, end)
            if label in {*preparatory[1:], *(supplements.PRODUCTIVE if full else ())}:
                require(row["startedRawNs"] < budget.fence("productive"), "PRODUCTIVE_PHASE_STARTED_AFTER_CUTOFF")
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
                                        *simulator.PREPARE, simulator.PRELAUNCH, *supplements.PRODUCTIVE} and
                    type(cutoff["observedRawNs"]) is int and
                    budget.fence("productive") <= cutoff["observedRawNs"] <= timing["terminalRawNs"],
                    "SEALED_JOB_CUTOFF_CHANGED")
        else:
            require(cutoff is None, "SEALED_JOB_CUTOFF_CHANGED")
        if full:
            supplements.verify_cancellation(owner, globals(), private, result, context, end, budget)
            verify_simulator_bindings(owner, private, result, context, end)
        else:
            verify_desktop_cancellation(owner, private, result, end, budget)


def verify_desktop_cancellation(owner, private, result, end, budget):
    """Existing canonical request and native birth, without a Darwin-only oracle."""
    cancellation = result["jobBudget"].get("cooperativeCancellation")
    rows = [row for row in result["phases"] if row.get("cooperativeCancellation") is not None]
    if cancellation is None:
        require(not rows, "DESKTOP_CANCELLATION_CHANGED")
        return
    require(len(rows) == 1 and rows[0]["phase"] == "product" and rows[0]["cooperativeCancellation"] == cancellation and
            type(cancellation) is dict and set(cancellation) == {"reason", "job", "invocation", "attemptedRawNs",
                "returnedRawNs", "requested", "requestSha256"}, "DESKTOP_CANCELLATION_CHANGED")
    row = rows[0]
    require(cancellation["job"] == row["job"] and cancellation["invocation"] == row["canonicalInvocation"] and
            row["launchAttempted"] is True and cancellation["reason"] in ("job-budget", "signal") and
            type(cancellation["requested"]) is bool and type(cancellation["attemptedRawNs"]) is int and
            row["startedRawNs"] <= cancellation["attemptedRawNs"] <= row["finalizedRawNs"],
            "DESKTOP_CANCELLATION_CHANGED")
    launches = row["ownership"]["launches"]
    require(len(launches) == 1 and launches[0].get("created") is True and launches[0].get("requestedArgv") == row["argv"] and
            launches[0].get("cwd") == str(ROOT) and
            (launches[0].get("api") == "CreateProcessW" and launches[0].get("resumed") is True and
             "shell" not in launches[0] if result["role"] == "windows-x64" else
             launches[0].get("api") == "subprocess.Popen" and launches[0].get("shell") is False) and
            len([entry for entry in row["ownership"]["startedIdentities"]
                 if entry.get("pid") == launches[0].get("pid")]) == 1, "DESKTOP_CANCELLATION_REQUIRES_NATIVE_BIRTH")
    if cancellation["reason"] == "job-budget":
        require(result["jobBudget"]["exhausted"] and cancellation["attemptedRawNs"] >= budget.fence("productive"),
                "DESKTOP_CANCELLATION_CHANGED")
    else:
        require(result["cancelled"] is True, "DESKTOP_CANCELLATION_CHANGED")
    if cancellation["requested"]:
        require(type(cancellation["returnedRawNs"]) is int and
                cancellation["attemptedRawNs"] <= cancellation["returnedRawNs"] <= row["finalizedRawNs"],
                "DESKTOP_CANCELLATION_CHANGED")
        state = owner.child(private, "state", end)
        original = owner.child(state, "cancellations", end)
        raw = owner.read(original, cancellation["invocation"] + ".json", end)
        retained = owner.child(owner.child(private, "evidence", end), "job-time", end)
        value = parse(raw)
        require(raw == owner.read(retained, "product-cancellation.json", end) and
                digest(raw) == cancellation["requestSha256"] and value.get("schema") == 1 and
                value.get("jobId") == cancellation["job"] and value.get("id") == cancellation["invocation"],
                "DESKTOP_CANCELLATION_ORIGINAL_CHANGED")
    else:
        require(cancellation["returnedRawNs"] is None and cancellation["requestSha256"] is None,
                "DESKTOP_FAILED_CANCELLATION_RELABELLED")


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
            before.get("contextSha256") == result["contextSha256"] and
            before.get("primaryAbiAccounting") == result.get("primaryAbiAccounting"), "ABI_FROZEN_PROFILE_CHANGED")
    names = {name.removeprefix("primary-abi/") for name in frozen if name.startswith("primary-abi/")}
    evidence = owner.child(private, "evidence", end)
    if disposition is None:
        require(result["productAttempted"] is False and result.get("primaryAbiAccounting") is None and not names and
                not os.path.lexists(evidence.path / "primary-abi"), "ABI_UNATTEMPTED_RELABELLED")
        require(frozen_abi_packet(owner, private, end)[0] == bound, "ABI_POST_RETURN_PACKET_CHANGED")
        check()
        return
    if not os.path.lexists(evidence.path / "primary-abi"):
        require(not names and disposition == {"status": "HOLD", "manifestSha256": None,
                "contextSha256": result["contextSha256"], "productPhaseSha256": result["phaseSha256"].get("product"),
                "generatedCount": None} and result.get("errors") and
                result.get("primaryAbiAccounting", {}).get("acquisitionStarted") is False,
                "ABI_UNACQUIRED_HOLD_CHANGED")
        supplements.verify_abi_accounting(result["primaryAbiAccounting"], result, context, partial=True)
        require(frozen_abi_packet(owner, private, end)[0] == bound and
                not os.path.lexists(evidence.path / "primary-abi"), "ABI_UNACQUIRED_ORIGINAL_CHANGED")
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
        supplements.verify_abi_accounting(result.get("primaryAbiAccounting"), result, context, partial=True)
        final_integrity()
        return
    manifest = parse(raw)
    require(raw == encoded(manifest) and set(manifest) == {"schema", "scope", "source", "contextSha256", "primary",
            "referenceQueries", "acquisition", "assessment", "accounting"} and manifest["schema"] == 1 and
            manifest["scope"] == "PRIMARY_FULL_ABI_ORIGINALS" and manifest["source"] == context["source"] and
            manifest["contextSha256"] == result["contextSha256"] and disposition == abi_disposition(raw),
            "ABI_MANIFEST_BINDING_CHANGED")
    supplements.verify_abi_accounting(manifest["accounting"], result, context)
    require(manifest["accounting"] == result.get("primaryAbiAccounting"), "ABI_ACCOUNTING_CHANGED")
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
    primary, log = primary_abi_inputs(owner, private, context, end, check)
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


def desktop_delivery_end(budget, result):
    """One original controller-terminal +600 cap, not a fresh tail per process."""
    require(budget.profile == result.get("profile") == "desktop", "DESKTOP_DELIVERY_SCOPE")
    terminal = result.get("jobBudget", {}).get("terminalRawNs")
    require(type(terminal) is int and budget.value["responseFinishedRawNs"] <= terminal <
            budget.fence("controller-return"), "DESKTOP_ORIGINAL_TERMINAL_REQUIRED")
    return min(budget.fence("delivery"), terminal + job_time.DESKTOP_DELIVERY_SECONDS * job_time.NS)


def original_deadline(clock, stage, fence, seconds):
    local = time.monotonic()
    now = clock.check(stage)
    require(now < fence, "ORIGINAL_DELIVERY_WINDOW_EXPIRED")
    return job_time._directed_deadline(local, seconds, min(fence, clock.budget.fence(stage)), now)


def validate_public(profile, *, cancelled=None):
    """Separate interpreter only; provisional files cannot grant upload authority."""
    require(os.environ.get("P2PKIT_HOSTED_TEST_RUN_OUTCOME") == "success", "ORIGINAL_CONTROLLER_DID_NOT_SUCCEED")
    require(job_time.TOKEN_ENV not in os.environ, "JOB_TIME_TOKEN_IN_SEAL")
    owner = PrivateOwner()
    end = time.monotonic() + 120
    error, budget, budget_clock, delivery_end = None, None, None, None
    passed = False
    def check_seal():
        check_cancelled(cancelled)
        posix._deadline(end)
        if budget_clock is not None:
            observed = budget_clock.check("seal")
            require(delivery_end is None or observed < delivery_end, "DESKTOP_SEAL_DELIVERY_EXPIRED")
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
        if "jobBudgetSha256" in context:
            budget = load_job_budget(owner, private, expected, context, end)
            budget_clock = original_clock(budget, result["jobBudget"]["terminalRawNs"])
            budget_clock.check("seal-start")
            end = min(end, budget_clock.deadline("seal", 120))
            if profile == "desktop":
                delivery_end = desktop_delivery_end(budget, result)
                end = min(end, original_deadline(budget_clock, "seal", delivery_end, 120))
        # A replay cannot overwrite the previous post-return receipt.
        validation = owner.new(path / "post-return-validation")
        checked = admission(owner, profile, path / "seal-admission", check_seal, expected=expected)
        output = owner.child(private, "export", end)
        runtime = owner.child(private, "runtime", end)
        returned_raw = owner.read(runtime, "export-result.json", end)
        require(digest(returned_raw) == result["exportReturn"]["sha256"] and
                parse(returned_raw) == result["exportReturn"]["result"], "ORIGINAL_EXPORT_RETURN_CHANGED")
        returned = result["exportReturn"]["result"]
        require(returned["operation"] == "export" and returned["profile"] == profile and
                returned["contextSha256"] == digest(context_raw), "SEALED_EXPORT_CONTEXT_CHANGED")
        require(("dependencySeed" in context) == ("dependencySeed" in result) ==
                ("dependencySeedFrozen" in returned), "SEED_SEALED_REQUIRED_DISPOSITION_MISSING")
        require(("dependencyCache" in context) == ("dependencyCache" in result) ==
                ("dependencyCacheFrozen" in returned), "CACHE_SEALED_REQUIRED_DISPOSITION_MISSING")
        sample_required = identity.sample_packaging_required(checked)
        require(context.get("samplePackagingRequired", False) is sample_required and
                (not sample_required or type(context.get("dependencyCache")) is dict) and
                sample_required == ("samplePackaging" in result) and
                (result.get("samplePackaging", {}).get("status") == "PASS") == ("samplePackagingFrozen" in returned),
                "SAMPLE_SEALED_REQUIRED_DISPOSITION_MISSING")
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
        require((context["kind"], context["command"]) ==
                profile_command(profile, role, package_samples=sample_required), "SEALED_SELECTOR_CHANGED")
        verify_phase_bindings(owner, private, result, context, end, budget)
        seed_frozen = None
        if "dependencySeed" in context:
            seed_frozen = frozen_seed_packet(owner, private, end,
                lambda: (posix._deadline(end), budget_clock.check("seal") if budget_clock is not None else None))
            require(seed_frozen == returned["dependencySeedFrozen"] and
                    seed_frozen["disposition"] == result["dependencySeed"], "SEED_SEALED_EXPORT_RETURN_CHANGED")
        cache_frozen = None
        if "dependencyCache" in context:
            cache_frozen = frozen_consume_packet(owner, private, end, check_seal)
            require(cache_frozen == returned["dependencyCacheFrozen"] and
                    cache_frozen["binding"] == result["dependencyCache"], "CACHE_SEALED_EXPORT_RETURN_CHANGED")
        package_frozen = None
        if "samplePackagingFrozen" in returned:
            package_frozen = frozen_package_packet(owner, private, end, check_seal)
            require(package_frozen == returned["samplePackagingFrozen"] and
                    package_frozen["manifestSha256"] == result["samplePackaging"]["manifestSha256"],
                    "SAMPLE_SEALED_EXPORT_RETURN_CHANGED")
        if profile == "full":
            supplements.verify(owner, globals(), private, result, context, end)
            before = parse(supplements.read_path(owner, globals(),
                           private.path / "evidence/profile-result-before-export.json", end))
            require(before.get("fullSupplements") == result.get("fullSupplements"), "SUPPLEMENT_FROZEN_PROFILE_CHANGED")
            verify_primary_abi_bindings(owner, private, result, context, end,
                                       lambda: (posix._deadline(end), budget_clock.check("seal")))
        passed = profile_passed(result)
        require(type(result["profilePassed"]) is bool and result["profilePassed"] == passed, "FAILED_PROFILE_RELABELLED")
        owner.write(validation, "seal.json", {"schema": 1, "controllerResultSha256": digest(result_raw),
            "manifestSha256": digest(manifest_raw), "artifact": actual, "profilePassed": passed,
            "source": record["source"], "retirement": "KNOWN", "decryption": "NOT_PERFORMED",
            **({"jobBudgetSha256": budget.sha256, "clockDomain": budget.value["clockDomain"],
                "sealedAtRawNs": budget_clock.check("seal"),
                "upload": {"seconds": job_time.UPLOAD_SECONDS, "latestStartRawNs": budget.fence("upload-start"),
                           "endRawNs": budget.fence("upload") if delivery_end is None else delivery_end}}
               if budget is not None else {}),
            **({"deliveryEndRawNs": delivery_end} if delivery_end is not None else {})}, end)
        require(owner.read(private, "controller-result.json", end) == result_raw and
                owner.read(output, posix.MANIFEST, end, 65536) == manifest_raw, "POST_RETURN_INPUT_CHANGED")
        if seed_frozen is not None:
            require(frozen_seed_packet(owner, private, end,
                    lambda: (posix._deadline(end), budget_clock.check("seal") if budget_clock is not None else None)) ==
                    seed_frozen, "SEED_POST_RETURN_INPUT_CHANGED")
        if cache_frozen is not None:
            require(frozen_consume_packet(owner, private, end, check_seal) == cache_frozen,
                    "CACHE_POST_RETURN_INPUT_CHANGED")
        if package_frozen is not None:
            require(frozen_package_packet(owner, private, end, check_seal) == package_frozen,
                    "SAMPLE_POST_RETURN_INPUT_CHANGED")
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
    check_seal()
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
    check_seal()
    print("ORDINARY_TEST_CIPHERTEXT_SEAL=PASS; PRIVATE_DECRYPTION=NOT_PERFORMED")


def full_upload_guard(phase, *, cancelled=None):
    """Closed before/after fence for FUTURE reviewed upload wiring, not upload.

    Wiring must require both guards' real successful outcomes, the exact before
    receipt hash, a <=3 minute pinned upload step and its successful outcome.
    This guard cannot schedule/guarantee GitHub step transitions or transfer.
    A late/failed upload never grants whole-gate acceptance from a prior seal.
    """
    require(phase in ("before", "after") and job_time.TOKEN_ENV not in os.environ and
            os.environ.get("P2PKIT_HOSTED_TEST_RUN_OUTCOME") == "success" and
            os.environ.get("P2PKIT_HOSTED_TEST_SEAL_OUTCOME") == "success", "UPLOAD_REQUIRES_REAL_SEAL_SUCCESS")
    check_cancelled(cancelled)
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
        seal_directory = owner.child(private, "post-return-validation", end)
        seal_raw = owner.read(seal_directory, "seal.json", end)
        seal = parse(seal_raw)
        previous = (parse(owner.read(private, "upload-before.json", end))["beganRawNs"]
                    if phase == "after" else seal["sealedAtRawNs"])
        clock = original_clock(budget, result["jobBudget"]["terminalRawNs"], seal["sealedAtRawNs"], previous)
        began = clock.check(stage)
        end = min(end, clock.deadline(stage, job_time.TRANSITION_SECONDS))
        require(seal.get("jobBudgetSha256") == budget.sha256 and seal.get("clockDomain") == job_time.RAW_CLOCK_DOMAIN and
                seal.get("controllerResultSha256") == digest(result_raw) and seal.get("source") == context["source"] and
                seal.get("profilePassed") == result["profilePassed"] == profile_passed(result) and
                seal.get("retirement") == "KNOWN" and type(seal.get("sealedAtRawNs")) is int and
                budget.value["responseFinishedRawNs"] <= seal["sealedAtRawNs"] < budget.fence("seal") and
                seal["sealedAtRawNs"] <= began and seal.get("upload") == {
                    "seconds": job_time.UPLOAD_SECONDS, "latestStartRawNs": budget.fence("upload-start"),
                    "endRawNs": budget.fence("upload")}, "UPLOAD_ORIGINAL_SEAL_CHANGED")
        checked = admission(owner, "full", private.path / ("upload-" + phase + "-admission"),
                            lambda: (check_cancelled(cancelled), posix._deadline(end), clock.check(stage)), expected=admitted)
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
    check_cancelled(cancelled)
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
    check_cancelled(cancelled)
    print("ORDINARY_FULL_UPLOAD_GUARD=" + phase.upper() + "; NO_UPLOAD_PERFORMED")


def delivery_inputs(owner, end):
    """Read a separately sealed Desktop result; do not create new time authority."""
    require(job_time.TOKEN_ENV not in os.environ and
            all(os.environ.get("P2PKIT_HOSTED_TEST_" + key + "_OUTCOME") == "success" for key in ("RUN", "SEAL")),
            "DELIVERY_REQUIRES_ORIGINAL_SUCCESS")
    role = processes.host_role()
    private = owner.open(session_path("desktop", role))
    context_raw, result_raw = (owner.read(private, name, end) for name in ("run-context.json", "controller-result.json"))
    context, result = parse(context_raw), parse(result_raw)
    require(context.get("profile") == result.get("profile") == "desktop" and context.get("role") == result.get("role") == role and
            context.get("root") == str(ROOT) and context.get("session") == str(private.path) and
            context.get("canonicalSources") == canonical_bindings() and
            type(context.get("dependencyCache")) is dict and result.get("contextSha256") == digest(context_raw) and
            result.get("retirement") == "KNOWN" and result.get("encrypted") is True and
            result.get("readyForPostReturnSeal") is True, "DELIVERY_ORIGINAL_CONTEXT_CHANGED")
    evidence = owner.child(private, "evidence", end)
    admitted = load_admission(owner, owner.child(evidence, "admission", end), end)
    require(digest(admitted.record) == context["admissionSha256"] and
            parse(admitted.record)["source"] == context["source"] == result["source"], "DELIVERY_ORIGINAL_SOURCE_CHANGED")
    sample_required = identity.sample_packaging_required(admitted)
    require(context.get("samplePackagingRequired") is sample_required and
            sample_required == ("samplePackaging" in result) and
            (context.get("kind"), context.get("command")) ==
            profile_command("desktop", role, package_samples=sample_required), "DELIVERY_SAMPLE_INTENT_CHANGED")
    budget = load_job_budget(owner, private, admitted, context, end)
    fence = desktop_delivery_end(budget, result)
    sealed = owner.child(private, "post-return-validation", end)
    seal_raw = owner.read(sealed, "seal.json", end)
    seal = parse(seal_raw)
    require(seal.get("jobBudgetSha256") == budget.sha256 and seal.get("clockDomain") == budget.value["clockDomain"] and
            seal.get("controllerResultSha256") == digest(result_raw) and seal.get("source") == context["source"] and
            type(seal.get("profilePassed")) is bool and seal["profilePassed"] == result["profilePassed"] == profile_passed(result) and
            seal.get("retirement") == "KNOWN" and type(seal.get("sealedAtRawNs")) is int and
            result["jobBudget"]["terminalRawNs"] <= seal["sealedAtRawNs"] < fence and
            seal.get("deliveryEndRawNs") == fence and seal.get("upload") == {"seconds": job_time.UPLOAD_SECONDS,
                "latestStartRawNs": budget.fence("upload-start"), "endRawNs": fence}, "DELIVERY_ORIGINAL_SEAL_CHANGED")
    clock = original_clock(budget, result["jobBudget"]["terminalRawNs"], seal["sealedAtRawNs"])
    return {"private": private, "role": role, "context": context, "contextRaw": context_raw,
            "result": result, "resultRaw": result_raw, "seal": seal, "sealRaw": seal_raw,
            "admitted": admitted, "budget": budget, "clock": clock, "endRawNs": fence}


def delivery_binding(data, scope):
    return {"schema": 1, "scope": scope, "contextSha256": digest(data["contextRaw"]),
            "controllerResultSha256": digest(data["resultRaw"]), "sealSha256": digest(data["sealRaw"]),
            "jobBudgetSha256": data["budget"].sha256, "source": data["context"]["source"],
            "clockDomain": data["budget"].value["clockDomain"], "deliveryEndRawNs": data["endRawNs"]}


def delivery_check(data, stage, end, cancelled, *, fence=None):
    check_cancelled(cancelled)
    posix._deadline(end)
    now = data["clock"].check(stage)
    require(now < min(data["endRawNs"], fence if fence is not None else data["endRawNs"]),
            "ORIGINAL_DELIVERY_WINDOW_EXPIRED")
    return now


def desktop_upload_before(data, raw):
    value = parse(raw)
    binding = delivery_binding(data, "CLOSED_DESKTOP_UPLOAD_SCHEDULING_CAP")
    expected_keys = set(binding) | {"beganRawNs", "endRawNs", "timeoutObservedRawNs", "timeoutMinutes"}
    require(set(value) == expected_keys and all(value.get(key) == item for key, item in binding.items()) and
            all(type(value[key]) is int for key in ("beganRawNs", "endRawNs", "timeoutObservedRawNs", "timeoutMinutes")) and
            data["seal"]["sealedAtRawNs"] <= value["beganRawNs"] <= value["timeoutObservedRawNs"] < value["endRawNs"] and
            value["endRawNs"] == min(data["endRawNs"], value["beganRawNs"] + job_time.UPLOAD_SECONDS * job_time.NS) and
            1 <= value["timeoutMinutes"] <= 3 and value["timeoutMinutes"] ==
                (value["endRawNs"] - value["timeoutObservedRawNs"]) // (60 * job_time.NS),
            "UPLOAD_ORIGINAL_FENCE_CHANGED_OR_EXPIRED")
    return value


def desktop_upload_pair(owner, data, end):
    private = data["private"]
    before_raw = owner.read(private, "upload-before.json", end)
    before = desktop_upload_before(data, before_raw)
    after_raw = owner.read(private, "upload-after.json", end)
    after = parse(after_raw)
    binding = delivery_binding(data, "CLOSED_DESKTOP_UPLOAD_SCHEDULING_CAP")
    require(set(after) == set(binding) | {"beforeSha256", "observedRawNs", "stepOutcome"} and
            all(after.get(key) == value for key, value in binding.items()) and after.get("stepOutcome") == "success" and
            after.get("beforeSha256") == digest(before_raw) and type(after.get("observedRawNs")) is int and
            before["timeoutObservedRawNs"] <= after["observedRawNs"] < before["endRawNs"],
            "DELIVERY_ORIGINAL_UPLOAD_CHANGED")
    data["clock"].last = max(data["clock"].last, after["observedRawNs"])
    return before_raw, after_raw


def upload_guard(phase, profile="full", *, cancelled=None):
    if profile == "full":
        return full_upload_guard(phase, cancelled=cancelled)
    require(profile == "desktop" and phase in ("before", "after"), "UPLOAD_CLOSED_PROFILE")
    if phase == "after":
        require(os.environ.get("P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME") == "success", "UPLOAD_ORIGINAL_ACTION_FAILED")
    owner, error, outputs, data, fence = PrivateOwner(), None, None, None, None
    end = time.monotonic() + job_time.TRANSITION_SECONDS
    def check():
        require(not owner.unknown, "UPLOAD_GUARD_RETIREMENT_UNKNOWN")
        return delivery_check(data, "upload", end, cancelled, fence=fence)
    try:
        check_cancelled(cancelled)
        data = delivery_inputs(owner, end)
        private = data["private"]
        before_raw = owner.read(private, "upload-before.json", end) if phase == "after" else None
        if before_raw is not None:
            before = desktop_upload_before(data, before_raw)
            require(digest(before_raw) == os.environ.get("P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256"),
                    "UPLOAD_ORIGINAL_GUARD_CHANGED")
            data["clock"].last = max(data["clock"].last, before["timeoutObservedRawNs"])
            fence = before["endRawNs"]
        began = check()
        if fence is None:
            fence = min(data["endRawNs"], began + job_time.UPLOAD_SECONDS * job_time.NS)
        end = min(end, original_deadline(data["clock"], "upload", fence, job_time.TRANSITION_SECONDS))
        admission(owner, "desktop", private.path / ("upload-" + phase + "-admission"), check, expected=data["admitted"])
        output = owner.child(private, "export", end)
        manifest_raw = owner.read(output, posix.MANIFEST, end, 65536)
        require(digest(manifest_raw) == data["seal"]["manifestSha256"] and
                parse(manifest_raw)["artifact"] == data["seal"]["artifact"] and
                artifact_metadata(owner, output, end) == data["seal"]["artifact"], "UPLOAD_SEALED_MANIFEST_CHANGED")
        binding = delivery_binding(data, "CLOSED_DESKTOP_UPLOAD_SCHEDULING_CAP")
        observed = check()
        if phase == "before":
            minutes = (fence - observed) // (60 * job_time.NS)
            require(1 <= minutes <= 3, "UPLOAD_NO_COMPLETE_MINUTE_LEFT")
            raw = encoded({**binding, "beganRawNs": began, "endRawNs": fence,
                           "timeoutObservedRawNs": observed, "timeoutMinutes": minutes})
            desktop_upload_before(data, raw)
            owner.write(private, "upload-before.json", raw, end)
            outputs = "upload_ready=true\nupload_timeout_minutes=" + str(minutes) + "\nupload_guard_sha256=" + digest(raw) + "\n"
        else:
            owner.write(private, "upload-after.json", {**binding, "beforeSha256": digest(before_raw),
                        "observedRawNs": observed, "stepOutcome": "success"}, end)
            desktop_upload_pair(owner, data, end)
            outputs = "upload_complete=true\n"
        check()
    except BaseException as caught:
        error = caught
        owner.error("desktop-upload-" + phase, caught)
    finally:
        try:
            owner.close()
        except BaseException as caught:
            error = error or caught
    if error is not None:
        raise error
    require(outputs is not None and not owner.unknown, "UPLOAD_GUARD_NOT_RETURNED")
    append_outputs(outputs, check)
    print("ORDINARY_DESKTOP_UPLOAD_GUARD=" + phase.upper() + "; NO_UPLOAD_PERFORMED")


def successful_sample_inputs(owner, end):
    require(all(os.environ.get("P2PKIT_HOSTED_TEST_" + name + "_OUTCOME") == "success"
                for name in ("UPLOAD", "UPLOAD_AFTER")), "SAMPLES_REQUIRE_ORIGINAL_EVIDENCE_UPLOAD")
    data = delivery_inputs(owner, end)
    require(data["context"].get("samplePackagingRequired") is True and
            data["result"]["profilePassed"] is True and
            data["result"].get("samplePackaging", {}).get("status") == "PASS", "SAMPLES_REQUIRE_PASSING_PROFILE")
    _, after_raw = desktop_upload_pair(owner, data, end)
    data["uploadAfterRaw"] = after_raw
    return data


def original_package(owner, data, end, check):
    private = data["private"]
    evidence = owner.child(private, "evidence", end)
    raw = owner.read(evidence, "sample-packaging.json", end)
    report = parse(raw)
    frozen = frozen_package_packet(owner, private, end, check)
    require(digest(raw) == data["result"]["samplePackaging"]["manifestSha256"] == frozen["manifestSha256"] and
            frozen == data["result"]["exportReturn"]["result"].get("samplePackagingFrozen"),
            "SAMPLE_ORIGINAL_FROZEN_PACKAGE_CHANGED")
    return raw, report, frozen


def packaging_binding(data, raw, report, frozen):
    return {**delivery_binding(data, "SEALED_ORIGINAL_SAMPLE_PACKAGE_READY"),
            "packageManifestSha256": digest(raw), "snapshotSha256": digest(encoded(report["snapshot"])),
            "frozenPacketSha256": digest(encoded(frozen)), "evidenceUploadAfterSha256": digest(data["uploadAfterRaw"])}


def package_succeeded(owner, data, end, check):
    require(os.environ.get("P2PKIT_SAMPLE_PACKAGE_OUTCOME") == "success", "SAMPLE_PACKAGE_GUARD_NOT_SUCCESSFUL")
    raw, report, frozen = original_package(owner, data, end, check)
    ready_raw = owner.read(data["private"], "packaging-ready.json", end)
    ready, binding = parse(ready_raw), packaging_binding(data, raw, report, frozen)
    require(digest(ready_raw) == os.environ.get("P2PKIT_SAMPLE_PACKAGE_SHA256") and
            set(ready) == set(binding) | {"observedRawNs"} and
            all(ready.get(key) == value for key, value in binding.items()) and type(ready.get("observedRawNs")) is int and
            parse(data["uploadAfterRaw"])["observedRawNs"] <= ready["observedRawNs"] < data["endRawNs"],
            "SAMPLE_ORIGINAL_PACKAGE_GUARD_CHANGED")
    data["clock"].last = max(data["clock"].last, ready["observedRawNs"])
    return ready_raw, report


def package_samples_guard(profile, *, cancelled=None):
    """NO WRITER: verify the original pre-export package and its delivery bytes."""
    require(profile == "desktop", "SAMPLE_DELIVERY_DESKTOP_ONLY")
    owner, error, outputs, data = PrivateOwner(), None, None, None
    end = time.monotonic() + job_time.TRANSITION_SECONDS
    def check():
        require(not owner.unknown, "SAMPLE_GUARD_RETIREMENT_UNKNOWN")
        return delivery_check(data, "delivery", end, cancelled)
    try:
        check_cancelled(cancelled)
        data = successful_sample_inputs(owner, end)
        end = min(end, original_deadline(data["clock"], "delivery", data["endRawNs"], job_time.TRANSITION_SECONDS))
        admission(owner, "desktop", data["private"].path / "package-guard-admission", check, expected=data["admitted"])
        raw, report, frozen = original_package(owner, data, end, check)
        require(sample_snapshot(owner, data["private"].path, data["admitted"], data["role"], end, check) == report["snapshot"],
                "SAMPLE_ORIGINAL_DELIVERY_BYTES_CHANGED")
        ready = encoded({**packaging_binding(data, raw, report, frozen), "observedRawNs": check()})
        owner.write(data["private"], "packaging-ready.json", ready, end)
        outputs = "packaging_ready=true\npackaging_sha256=" + digest(ready) + "\n"
        check()
    except BaseException as caught:
        error = caught
        owner.error("sample-package-guard", caught)
    finally:
        try:
            owner.close()
        except BaseException as caught:
            error = error or caught
    if error is not None:
        raise error
    require(outputs is not None and not owner.unknown, "SAMPLE_PACKAGE_GUARD_NOT_RETURNED")
    append_outputs(outputs, check)
    print("SAMPLE_PACKAGE_GUARD=PASS; NEW_PACKAGING_OR_BUILD=NOT_PERFORMED")


def sample_window(data, package_raw, raw):
    value = parse(raw)
    binding = {**delivery_binding(data, "ONE_ORIGINAL_SAMPLE_UPLOAD_WINDOW"), "packagingSha256": digest(package_raw)}
    require(set(value) == set(binding) | {"beganRawNs", "endRawNs"} and
            all(value.get(key) == item for key, item in binding.items()) and
            type(value.get("beganRawNs")) is int and type(value.get("endRawNs")) is int and
            parse(package_raw)["observedRawNs"] <= value["beganRawNs"] < value["endRawNs"] and
            value["endRawNs"] == min(data["endRawNs"], value["beganRawNs"] + job_time.UPLOAD_SECONDS * job_time.NS),
            "SAMPLE_ORIGINAL_SHARED_WINDOW_CHANGED")
    return value


def sample_upload_binding(data, platform, package_raw, window_raw):
    return {**delivery_binding(data, "ORIGINAL_SAMPLE_UPLOAD"), "platform": platform,
            "packagingSha256": digest(package_raw), "windowSha256": digest(window_raw)}


def sample_before(data, platform, package_raw, window_raw, raw):
    window, value = sample_window(data, package_raw, window_raw), parse(raw)
    binding = sample_upload_binding(data, platform, package_raw, window_raw)
    require(set(value) == set(binding) | {"beganRawNs", "timeoutObservedRawNs", "timeoutMinutes"} and
            all(value.get(key) == item for key, item in binding.items()) and
            all(type(value.get(key)) is int for key in ("beganRawNs", "timeoutObservedRawNs", "timeoutMinutes")) and
            window["beganRawNs"] <= value["beganRawNs"] <= value["timeoutObservedRawNs"] < window["endRawNs"] and
            1 <= value["timeoutMinutes"] <= 3 and value["timeoutMinutes"] ==
                (window["endRawNs"] - value["timeoutObservedRawNs"]) // (60 * job_time.NS),
            "SAMPLE_ORIGINAL_UPLOAD_FENCE_CHANGED")
    return value


def sample_upload_pair(owner, data, platform, package_raw, window_raw, end):
    before_raw = owner.read(data["private"], "sample-" + platform + "-before.json", end)
    before = sample_before(data, platform, package_raw, window_raw, before_raw)
    after_raw = owner.read(data["private"], "sample-" + platform + "-after.json", end)
    after = parse(after_raw)
    binding = sample_upload_binding(data, platform, package_raw, window_raw)
    require(set(after) == set(binding) | {"beforeSha256", "observedRawNs", "stepOutcome"} and
            all(after.get(key) == item for key, item in binding.items()) and after.get("beforeSha256") == digest(before_raw) and
            after.get("stepOutcome") == "success" and type(after.get("observedRawNs")) is int and
            before["timeoutObservedRawNs"] <= after["observedRawNs"] < parse(window_raw)["endRawNs"],
            "SAMPLE_ORIGINAL_UPLOAD_AFTER_CHANGED")
    data["clock"].last = max(data["clock"].last, after["observedRawNs"])
    return after_raw


def sample_upload_guard(phase, platform, profile, *, cancelled=None):
    require(profile == "desktop" and phase in ("before", "after") and platform in ("desktop", "android"),
            "SAMPLE_UPLOAD_CLOSED_CALL")
    if phase == "after":
        require(os.environ.get("P2PKIT_SAMPLE_UPLOAD_OUTCOME") == "success", "SAMPLE_ORIGINAL_UPLOAD_FAILED")
    owner, error, outputs, data, fence = PrivateOwner(), None, None, None, None
    end = time.monotonic() + job_time.TRANSITION_SECONDS
    def check():
        require(not owner.unknown, "SAMPLE_GUARD_RETIREMENT_UNKNOWN")
        return delivery_check(data, "samples", end, cancelled, fence=fence)
    try:
        check_cancelled(cancelled)
        data = successful_sample_inputs(owner, end)
        require(platform != "android" or data["role"] == "linux-x64", "ANDROID_SAMPLE_LINUX_ONLY")
        # Validate predecessor bytes before the first new clock sample. This
        # floor prevents a later process accepting a temporarily backward clock.
        package_raw, report = package_succeeded(owner, data, end, lambda: posix._deadline(end))
        private = data["private"]
        if phase == "before" and platform == "desktop":
            began = check()
            window_raw = encoded({**delivery_binding(data, "ONE_ORIGINAL_SAMPLE_UPLOAD_WINDOW"),
                "packagingSha256": digest(package_raw), "beganRawNs": began,
                "endRawNs": min(data["endRawNs"], began + job_time.UPLOAD_SECONDS * job_time.NS)})
            owner.write(private, "sample-window.json", window_raw, end)
        else:
            window_raw = owner.read(private, "sample-window.json", end)
        window = sample_window(data, package_raw, window_raw)
        fence = window["endRawNs"]
        data["clock"].last = max(data["clock"].last, window["beganRawNs"])
        if platform == "android":
            require(os.environ.get("P2PKIT_SAMPLE_DESKTOP_AFTER_OUTCOME") == "success",
                    "ANDROID_SAMPLE_REQUIRES_DESKTOP_RETURN")
            sample_upload_pair(owner, data, "desktop", package_raw, window_raw, end)
        before_raw = None
        if phase == "after":
            before_raw = owner.read(private, "sample-" + platform + "-before.json", end)
            before = sample_before(data, platform, package_raw, window_raw, before_raw)
            require(digest(before_raw) == os.environ.get("P2PKIT_SAMPLE_UPLOAD_GUARD_SHA256"),
                    "SAMPLE_ORIGINAL_BEFORE_OUTPUT_CHANGED")
            data["clock"].last = max(data["clock"].last, before["timeoutObservedRawNs"])
        began = check()
        end = min(end, original_deadline(data["clock"], "samples", fence, job_time.TRANSITION_SECONDS))
        admission(owner, "desktop", private.path / ("sample-" + platform + "-" + phase + "-admission"), check,
                  expected=data["admitted"])
        require(sample_snapshot(owner, private.path, data["admitted"], data["role"], end, check) == report["snapshot"],
                "SAMPLE_ORIGINAL_DELIVERY_BYTES_CHANGED")
        binding, observed = sample_upload_binding(data, platform, package_raw, window_raw), check()
        if phase == "before":
            minutes = (fence - observed) // (60 * job_time.NS)
            require(1 <= minutes <= 3, "SAMPLE_UPLOAD_NO_COMPLETE_MINUTE_LEFT")
            raw = encoded({**binding, "beganRawNs": began, "timeoutObservedRawNs": observed, "timeoutMinutes": minutes})
            sample_before(data, platform, package_raw, window_raw, raw)
            owner.write(private, "sample-" + platform + "-before.json", raw, end)
            outputs = "upload_ready=true\nupload_timeout_minutes=" + str(minutes) + "\nupload_guard_sha256=" + digest(raw) + "\n"
        else:
            owner.write(private, "sample-" + platform + "-after.json", {**binding, "beforeSha256": digest(before_raw),
                        "observedRawNs": observed, "stepOutcome": "success"}, end)
            sample_upload_pair(owner, data, platform, package_raw, window_raw, end)
            outputs = "upload_complete=true\n"
        check()
    except BaseException as caught:
        error = caught
        owner.error("sample-" + platform + "-" + phase, caught)
    finally:
        try:
            owner.close()
        except BaseException as caught:
            error = error or caught
    if error is not None:
        raise error
    require(outputs is not None and not owner.unknown, "SAMPLE_UPLOAD_GUARD_NOT_RETURNED")
    append_outputs(outputs, check)
    print("SAMPLE_UPLOAD_GUARD=" + platform.upper() + "_" + phase.upper() + "; NO_UPLOAD_PERFORMED")


def sample_delivery_guard(profile, *, cancelled=None):
    require(profile == "desktop", "SAMPLE_DELIVERY_DESKTOP_ONLY")
    owner, error, data = PrivateOwner(), None, None
    end = time.monotonic() + job_time.TRANSITION_SECONDS
    def check():
        require(not owner.unknown, "SAMPLE_GUARD_RETIREMENT_UNKNOWN")
        return delivery_check(data, "delivery", end, cancelled)
    try:
        check_cancelled(cancelled)
        data = successful_sample_inputs(owner, end)
        package_raw, _report = package_succeeded(owner, data, end, lambda: posix._deadline(end))
        private = data["private"]
        window_raw = owner.read(private, "sample-window.json", end)
        sample_window(data, package_raw, window_raw)
        after = {}
        for platform in ("desktop", "android"):
            expected = "success" if platform == "desktop" or data["role"] == "linux-x64" else "skipped"
            require(all(os.environ.get("P2PKIT_SAMPLE_" + platform.upper() + "_" + phase + "_OUTCOME") == expected
                        for phase in ("BEFORE", "UPLOAD", "AFTER")), "SAMPLE_DELIVERY_ORIGINAL_OUTCOME_FAILED")
            if expected == "success":
                after[platform] = digest(sample_upload_pair(owner, data, platform, package_raw, window_raw, end))
        end = min(end, original_deadline(data["clock"], "delivery", data["endRawNs"], job_time.TRANSITION_SECONDS))
        admission(owner, "desktop", private.path / "sample-delivery-admission", check, expected=data["admitted"])
        owner.write(private, "sample-delivery.json", {**delivery_binding(data, "ONE_HOST_SAMPLE_DELIVERY_COMPLETE"),
                    "packagingSha256": digest(package_raw), "windowSha256": digest(window_raw), "uploads": after,
                    "observedRawNs": check(), "retirement": "KNOWN"}, end)
        check()
    except BaseException as caught:
        error = caught
        owner.error("sample-delivery", caught)
    finally:
        try:
            owner.close()
        except BaseException as caught:
            error = error or caught
    if error is not None:
        raise error
    check()
    print("ONE_HOST_SAMPLE_DELIVERY=PASS; RELEASE_PUBLICATION=NOT_PERFORMED")


def stage_dependencies(profile):
    """Closed optional staging allocation. No restore, Gradle, save or H creation.

    Future workflow wiring must require this step's actual successful outcome,
    bind dependency_seed_staging_sha256 as P2PKIT_DEPENDENCY_SEED_STAGE_SHA256,
    and pass that outcome as P2PKIT_DEPENDENCY_SEED_STAGE_OUTCOME. A provisional
    receipt/output cannot authorize run --seed-dependencies after late failure.
    """
    owner, error, raw = PrivateOwner(), None, None
    end = time.monotonic() + 120
    def check():
        posix._deadline(end)
        require(not owner.unknown and not QUARANTINE and not query.QUARANTINE and not windows._QUARANTINE,
                "SEED_STAGE_RETIREMENT_UNKNOWN")
    try:
        role = processes.host_role()
        session = session_path(profile, role)
        path = seed.stage_path(session, profile, role)
        require(path != ROOT and path not in ROOT.parents and ROOT not in path.parents and
                path != session and path not in session.parents and session not in path.parents,
                "SEED_STAGE_ALIAS")
        container = owner.acquire("dependency-seed-stage-container", lambda: seed.private_root(path, create=True))
        admitted = admission(owner, profile, path / "admission", check)
        inputs, _compiled = seed.source_inputs(owner, ROOT, end, check)
        admission(owner, profile, path / "source-recheck", check, expected=admitted)
        source = owner.acquire("dependency-seed-stage-source", lambda: container.create_directory(
            "restore-home", deadline=end))
        raw = seed.encoded(seed.stage_record(admitted.record, profile, role, path, container.verify(),
                                            source.verify(), inputs))
        owner.write(container, "staging.json", raw, end)
        check()
    except BaseException as caught:
        error = caught
        owner.error("dependency-seed-stage", caught)
    finally:
        try:
            owner.close()
        except BaseException as caught:
            error = error or caught
    if error is not None:
        raise error
    require(raw is not None and not owner.unknown, "SEED_STAGE_NOT_FINALIZED")
    check()
    target = Path(os.environ["GITHUB_OUTPUT"])
    audit.reject_symlinks(target)
    with target.open("a", encoding="ascii") as output:
        check()
        output.write("dependency_seed_ready=true\ndependency_seed_home=" + str(path / "restore-home") +
                     "\ndependency_seed_staging_sha256=" + digest(raw) + "\n")
        output.flush()
        os.fsync(output.fileno())
    check()  # The actual successful step outcome, not earlier output, is mandatory.
    print("DEPENDENCY_SEED_STAGE=ALLOCATED; RESTORE_AND_REUSE=NOT_PERFORMED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for name in ("run", "validate-public", "_crypto", "_job-time", "upload-guard", "stage-dependencies",
                 "prepare-consume", "restore-guard", "package-samples", "sample-upload-guard", "sample-delivery-guard"):
        entry = sub.add_parser(name)
        entry.add_argument("--profile", choices=("desktop",) if name in
                           ("package-samples", "sample-upload-guard", "sample-delivery-guard") else PRODUCT_SECONDS,
                           required=True)
        if name == "_crypto":
            entry.add_argument("phase", choices=("validate", "export"))
            entry.add_argument("--context-sha256", required=True)
        elif name == "_job-time":
            entry.add_argument("--admission-sha256", required=True)
        elif name in ("upload-guard", "sample-upload-guard"):
            entry.add_argument("phase", choices=("before", "after"))
            if name == "sample-upload-guard":
                entry.add_argument("--platform", choices=("desktop", "android"), required=True)
        elif name == "run":
            seeds = entry.add_mutually_exclusive_group()
            seeds.add_argument("--seed-dependencies", action="store_true")
            seeds.add_argument("--consume-dependencies", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "run":
            return run(args.profile, seed_dependencies=args.seed_dependencies, consume_dependencies=args.consume_dependencies)
        if args.operation == "validate-public":
            guarded_operation(validate_public, args.profile)
        elif args.operation == "prepare-consume":
            guarded_operation(prepare_consume, args.profile)
        elif args.operation == "restore-guard":
            guarded_operation(restore_guard, args.profile)
        elif args.operation == "package-samples":
            guarded_operation(package_samples_guard, args.profile)
        elif args.operation == "sample-upload-guard":
            guarded_operation(sample_upload_guard, args.phase, args.platform, args.profile)
        elif args.operation == "sample-delivery-guard":
            guarded_operation(sample_delivery_guard, args.profile)
        elif args.operation == "stage-dependencies":
            stage_dependencies(args.profile)
        elif args.operation == "_job-time":
            require(re.fullmatch(r"[0-9a-f]{64}", args.admission_sha256), "JOB_TIME_ADMISSION_HASH")
            job_time_phase(args.profile, args.admission_sha256)
        elif args.operation == "upload-guard":
            guarded_operation(upload_guard, args.phase, args.profile)
        else:
            require(re.fullmatch(r"[0-9a-f]{64}", args.context_sha256), "CRYPTO_CONTEXT_HASH")
            crypto_phase(args.phase, args.profile, args.context_sha256)
        return 0
    except BaseException:
        print("ORDINARY_TEST_CUSTODY=HOLD; PRIVATE_EVIDENCE_REQUIRED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
