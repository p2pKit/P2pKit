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
import math
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
import hosted_initial_ordinary_adapter as initial
import hosted_jvm_library_custody as jvm
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
PRODUCT_SECONDS = {"full": 7200, "desktop": 600, "jvm-library": 600}
OUTER_SECONDS = {"full": 7530, "desktop": 825, "jvm-library": 825}
TOTAL_SECONDS = {"full": 8400, "desktop": 1500, "jvm-library": 1500}
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
JVM_ORDER = ("job-time", "recipient-validation", "audit-init", "product", "export")
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
    if profile == jvm.PROFILE:
        require(not package_samples, "JVM_CANNOT_PACKAGE_SAMPLES")
        return jvm.command(role)
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
    require(profile != jvm.PROFILE or role in jvm.BACKENDS, "JVM_SESSION_HOST")
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
    require(value.get("scope") == "ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY" and
            initial.identity.worker_cohort(record) is None, "ORDINARY_ADMISSION_ONLY")
    require(digest(event) == value["github"]["eventSha256"] and digest(policy) == value["policy"]["sha256"] and
            digest(key) == value["policy"]["keySha256"], "ORIGINAL_ADMISSION_BYTES_CHANGED")
    return identity.Admission(record, event, policy, key, value["policy"]["fingerprint"],
                              value["policy"]["keySha256"], value["policy"]["expiresAt"])


def context_identity(owner, directory, context, end):
    """Explicit origin dispatch; an initial DATA identity is never Admission."""
    if context.get("scope") == initial.INITIAL_CONTEXT_SCOPE:
        binding = initial.initial_context(context)
        bound = initial.load_identity(owner, directory, end)
        require(digest(bound.record) == binding["identitySha256"], "INITIAL_CONTEXT_IDENTITY_CHANGED")
        return bound
    require(context.get("scope") == "CLOSED_ORDINARY_TEST_CONTROLLER" and "initialOrdinary" not in context,
            "ORDINARY_CONTEXT_ONLY")
    return load_admission(owner, directory, end)


def sample_intent(admitted):
    if type(admitted) in (initial.identity.InitialOrdinaryIdentity, initial.identity.InitialJvmLibraryIdentity):
        require(initial.identity.worker_cohort(admitted.record) is not None, "INITIAL_SAMPLE_IDENTITY")
        return False  # C2 is the first PR, never a main application producer.
    require(type(admitted) is identity.Admission, "SAMPLE_ORDINARY_ADMISSION")
    return identity.sample_packaging_required(admitted)


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
            context["profile"], context["role"], seed.stage_path(private.path, context["profile"], context["role"],
                                                             admitted_raw=admitted.record),
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
    admitted = context_identity(owner, owner.child(evidence, "admission", end), context, end)
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
    admitted = context_identity(owner, owner.child(evidence, "admission", end), context, end)
    is_initial = type(admitted) in (initial.identity.InitialOrdinaryIdentity, initial.identity.InitialJvmLibraryIdentity)
    budget = load_job_budget(owner, private, admitted, context, end)
    bound = consume_binding(owner, private, admitted, budget, end)
    require(bound == context.get("dependencyCache"), "CACHE_FROZEN_CONTEXT_CHANGED")
    originals, streamed = {}, {}
    native = bound["scope"] in ("ORDINARY_NATIVE_CONSUME_ORIGINALS", "INITIAL_ORDINARY_NATIVE_CONSUME_ORIGINALS")
    require(not is_initial or native, "INITIAL_FROZEN_NATIVE_PROVIDER_REQUIRED")
    directory = owner.child(evidence, "dependency-cache", end)
    names = {"plan.json", "staging.json", "preparation.json", "provider.json", "restoration.json",
             "controller-context.json"}
    require(set(seed_names(owner, directory.path, end)) == names | ({"provider-originals"} if native else set()),
            "CACHE_ORIGINAL_RECEIPT_ROSTER")
    for name in sorted(names):
        originals["dependency-cache/" + name] = owner.read(directory, name, end)
    require(originals["dependency-cache/controller-context.json"] == context_raw, "CACHE_ORIGINAL_CONTEXT_CHANGED")
    if native:
        import hosted_cache_provider_readback as provider_readback
        provider = parse(originals["dependency-cache/provider.json"])
        original_directory = owner.child(directory, "provider-originals", end)
        raw_files = read_native_provider_originals(owner, original_directory, provider["originals"], end, check)
        for slot, name, maximum in provider_readback.ORIGINAL_FILES:
            target = "dependency-cache/provider-originals/" + name
            originals[target], streamed[target] = raw_files[slot], maximum
    timing = owner.child(evidence, "job-time", end)
    names = set(seed_names(owner, timing.path, end))
    fixed = ({"budget.json", "current-budget.json", "initial-current"} if is_initial else
             {"attempt.json", "jobs.json", "child-return.json", "budget.json"})
    require(fixed <= names <= fixed | {"product-cancellation.json"}, "CACHE_TIMING_RECEIPT_ROSTER")
    for name in sorted(names - ({"initial-current"} if is_initial else set())):
        originals["job-time/" + name] = owner.read(timing, name, end)
    anchors = {"dependency-cache/" + name + ".json": bound[key + "Sha256"] for name, key in
               (("preparation", "preparation"), ("restoration", "restoration"), ("plan", "plan"),
                ("provider", "provider"), ("staging", "staging"))}
    anchors["job-time/budget.json"] = budget.sha256
    if is_initial:
        history = owner.child(timing, "initial-current", end)
        data = initial.read_history(owner, history, end)
        originals.update({"job-time/initial-current/" + name: raw for name, raw in data.items()})
        disposition = initial.current_budget_disposition(budget, digest(data[initial.HISTORY_NAME]))
        require(originals["job-time/current-budget.json"] == encoded(disposition) and
                disposition["historySha256"] == initial.initial_context(context)["historySha256"],
                "INITIAL_FROZEN_BUDGET_ORIGIN_CHANGED")
        anchors.update({"job-time/initial-current/" + name: budget.value["provenance"][key] for name, key in (
            ("current.json", "sourceCurrentSha256"), ("context.json", "sourceContextSha256"),
            ("first-session.json", "currentFirstSessionSha256"), ("native-start.json", "sourceNativeStartSha256"),
            ("native-return.json", "sourceNativeReturnSha256"), ("owner-close.json", "sourceOwnerCloseSha256"))})
        anchors.update({"job-time/initial-current/" + key + ".bin": sha
                        for key, sha in budget.value["originalsSha256"].items()})
        require("job-time" not in seed_names(owner, owner.child(evidence, "commands", end).path, end),
                "INITIAL_FROZEN_FAKE_JOB_TIME_PHASE")
    else:
        phase = owner.child(owner.child(evidence, "commands", end), "job-time", end)
        names = {"start.json", "result.json", "baseline.json", "stdout.log", "stderr.log"}
        require(set(seed_names(owner, phase.path, end)) == names, "CACHE_TIME_PHASE_ROSTER")
        for name in sorted(names):
            originals["commands/job-time/" + name] = owner.read(phase, name, end)
        anchors.update({**{"job-time/" + key + ".json": sha for key, sha in budget.value["originalsSha256"].items()},
            "job-time/child-return.json": budget.value["provenance"]["childReturnSha256"],
            "commands/job-time/start.json": budget.value["provenance"]["phaseStartSha256"],
            "commands/job-time/result.json": budget.value["provenance"]["phaseResultSha256"]})
    require(all(digest(originals[name]) == sha for name, sha in anchors.items()),
            "CACHE_VALIDATED_ORIGINALS_CHANGED_BEFORE_FREEZE")
    before_raw = owner.read(evidence, "profile-result-before-export.json", end)
    require(parse(before_raw).get("dependencyCache") == bound and
            parse(before_raw).get("contextSha256") == digest(context_raw), "CACHE_FROZEN_PROFILE_CHANGED")
    if is_initial:
        require(parse(before_raw).get("scope") == initial.INITIAL_RESULT_SCOPE and
                parse(before_raw).get("currentBudget") == disposition, "INITIAL_FROZEN_CURRENT_BUDGET_CHANGED")
    originals["profile-result-before-export.json"] = before_raw
    frozen = owner.child(private, "frozen-evidence", end)
    map_raw = owner.read(frozen, "original-path-map.json", end)
    mapping = seed_copy_map(map_raw, evidence.path)
    rows = {row["original"]: row for row in mapping["files"]}
    require(set(seed_names(owner, frozen.path, end)) == {"original-path-map.json", *[row["member"] for row in rows.values()]} and
            all({name for name in rows if name.startswith(prefix)} == {name for name in originals if name.startswith(prefix)}
                for prefix in ("dependency-cache/", "job-time/", "commands/job-time/")), "CACHE_FROZEN_ROSTER_CHANGED")
    for prefix, expected in (("dependency-cache", ["dependency-cache"] +
            (["dependency-cache/provider-originals"] if native else [])),
            ("job-time", ["job-time"] + (["job-time/initial-current"] if is_initial else [])),
            ("commands/job-time", [] if is_initial else ["commands/job-time"])):
        require([name for name in mapping["directories"] if name == prefix or name.startswith(prefix + "/")] == expected,
                "CACHE_FROZEN_DIRECTORY_ROSTER")
    for name, raw in originals.items():
        check()
        row = rows.get(name)
        require(type(row) is dict and (row["size"], row["sha256"]) == (len(raw), digest(raw)),
                "CACHE_FROZEN_ORIGINAL_BINDING")
        frozen_raw = (provider_file_bytes(owner, frozen, row["member"], streamed[name], end, check)[0]
                      if name in streamed else owner.read(frozen, row["member"], end))
        require(frozen_raw == raw, "CACHE_FROZEN_ORIGINAL_DIFFERS")
    for name, raw in originals.items():
        current = evidence
        parts = name.split("/")  # Closed producer-selected names above, never external paths.
        for part in parts[:-1]:
            current = owner.child(current, part, end)
        current_raw = (provider_file_bytes(owner, current, parts[-1], streamed[name], end, check)[0]
                       if name in streamed else owner.read(current, parts[-1], end))
        require(current_raw == raw, "CACHE_ORIGINAL_CHANGED_DURING_FREEZE")
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
        require(profile != jvm.PROFILE or preflight or consume_dependencies, "JVM_REQUIRES_NATIVE_CONSUME")
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
        require(self.profile != jvm.PROFILE or label in JVM_ORDER, "JVM_CLOSED_NATIVE_PHASE")
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
            self.before_phase_launch(row, directory, env, end, raw_work_end, raw_final_end)
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

    def before_phase_launch(self, row, directory, env, end, raw_work_end, raw_final_end):
        """Ordinary phases have no initial-recipient request or current cast."""
        return None

    def prepare_identity(self):
        if self.consume_requested:
            adopt_preparation(self)
        else:
            self.allocate()
            self.admitted = admission(self, self.profile, self.evidence.path / "admission", self.check)

    def recheck_identity(self, destination, check, end, *, purpose, stage="productive"):
        require(type(self.admitted) is identity.Admission, "ORDINARY_RECHECK_ONLY")
        check()
        result = admission(self, self.profile, destination, check, expected=self.admitted)
        check()
        return result

    def bind_run_context(self, context):
        require(type(self.admitted) is identity.Admission and context["scope"] == "CLOSED_ORDINARY_TEST_CONTROLLER",
                "ORDINARY_CONTEXT_ONLY")

    def bind_result(self, result):
        return None

    def setup(self):
        self.prepare_identity()
        if self.profile == "full":
            resolved = shutil.which("python3", path=self.environment.get("PATH", ""))
            require(resolved is not None and Path(resolved).resolve(strict=True) == Path(sys.executable).resolve(strict=True),
                    "FULL_PYTHON_DIFFERS_FROM_NATIVE_CONTROLLER")
        original = parse(self.admitted.record)
        self.sample_required = sample_intent(self.admitted)
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
        self.bind_run_context(context)
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
        if self.profile == jvm.PROFILE:
            self.request_raw = jvm.reserve(self, globals())
            self.request = jvm.request_data(self.request_raw, self.run_context_raw, self.canonical_context_raw)
            return  # No CLI/diagnostics loader or custody subprocess exists for JVM.
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
        path = seed.stage_path(self.path, self.profile, self.role, admitted_raw=self.admitted.record)
        owners, original = seed._Owners(self), None
        try:
            container = owners.acquire("stage-container", lambda: seed.private_root(path))
            source = owners.acquire("stage-source", lambda: seed.public_root(path / "restore-home"))
            staging_raw = self.read(container, "staging.json", end)
            require(digest(staging_raw) == os.environ["P2PKIT_DEPENDENCY_SEED_STAGE_SHA256"],
                    "SEED_ORIGINAL_STAGE_OUTPUT_CHANGED")
            inputs, compiled = seed.source_inputs(self, ROOT, end, check)
            # Existing exact clean-source/native admission, not a new Git blob API.
            self.recheck_identity(self.runtime.path / "seed-input-admission", check, end, purpose="seed")
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
        if self.profile in ("desktop", jvm.PROFILE):
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
        if self.profile == jvm.PROFILE:
            if not self.collect_attempted:
                self.collect_attempted = True
                try:
                    self.custody = jvm.collect(self, globals())
                except BaseException as error:
                    # Missing launched originals/stop/close cannot become normal
                    # upload-ready evidence by omitting the failed collection.
                    self.error("jvm-library-original-custody", error, unknown=True)
                    raise
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
        if self.profile == jvm.PROFILE:
            require(self.export_return["result"].get("jvmLibraryFrozen") ==
                    jvm.frozen_binding(self, globals(), self.private, end,
                                       lambda: self.check_window("export-verify", end)),
                    "JVM_ORIGINAL_EXPORT_RETURN_DIFFERS")
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
        self.bind_result(value)
        value["profilePassed"] = profile_passed(value)
        return parse(encoded(value))


def initial_budget_originals(owner, private, admitted, end):
    """Recompute DATA from first-source originals, never a fake job-time phase."""
    require(type(admitted) in (initial.identity.InitialOrdinaryIdentity, initial.identity.InitialJvmLibraryIdentity),
            "INITIAL_BUDGET_IDENTITY")
    evidence = owner.child(private, "evidence", end)
    directory = owner.child(evidence, "job-time", end)
    history = owner.child(directory, "initial-current", end)
    data = initial.read_history(owner, history, end)
    raw = owner.read(directory, "budget.json", end)
    declared = job_time.Budget(raw)
    require(declared.value["schema"] == 3, "INITIAL_CURRENT_BUDGET_ONLY")
    budget = job_time.derive_initial_retained(admitted, initial.budget_originals(data),
                                             declared.value["provenance"]["controllerJob"])
    require(raw == budget.record and data["identity.json"] == admitted.record,
            "INITIAL_ORIGINAL_CURRENT_BUDGET_CHANGED")
    history_sha = digest(data[initial.HISTORY_NAME])
    disposition = initial.current_budget_disposition(budget, history_sha)
    require(owner.read(directory, "current-budget.json", end) == encoded(disposition),
            "INITIAL_ORIGINAL_CURRENT_DISPOSITION_CHANGED")
    return budget, history, history_sha, disposition


def reacquire_initial_source(owner, private, admitted, budget, history_sha, end, *, cancelled, preceding, stage):
    """Later-process actual acquisition. No prior registry, token or pid reuse."""
    evidence = owner.child(private, "evidence", end)
    history = owner.child(owner.child(evidence, "job-time", end), "initial-current", end)
    now = budget.check(stage)
    local = time.monotonic()  # Later LOCAL conservatively maps the immutable local cap to RAW.
    require(local < end, "INITIAL_REACQUISITION_EXPIRED")
    cap = initial.local_raw_cap(now, budget.fence(stage), local, end)
    session = initial.reacquire(owner, history, history_sha, end,
        cancelled=lambda: check_cancelled(cancelled), original_work_end_ns=cap,
        original_final_end_ns=cap, preceding_outcome=preceding)
    require(session.identity.record == admitted.record, "INITIAL_REACQUIRED_IDENTITY_CHANGED")
    posix._deadline(end)
    budget.check(stage)
    return session


def initial_controller_entry(profile, cancelled, preflight):
    """Consume legitimate API credential BEFORE the ordinary base constructor."""
    initial.forbid_service_environment()
    check_cancelled(cancelled)
    if preflight:
        first = job_time.current_reading(profile)
        return initial.acquire_first(cancelled=lambda: check_cancelled(cancelled),
            original_work_end_ns=first.nanoseconds + 75 * job_time.NS,
            original_final_end_ns=first.nanoseconds + 120 * job_time.NS), None
    require(os.environ.get("P2PKIT_HOSTED_PREPARE_OUTCOME") == "success" and
            os.environ.get("P2PKIT_CACHE_GUARD_OUTCOME") == "success", "INITIAL_ORIGINAL_PROVIDER_STEP_REQUIRED")
    owner, failure, answer = PrivateOwner(), None, None
    end = time.monotonic() + 120
    try:
        private = owner.open(session_path(profile, processes.host_role()))
        evidence = owner.child(private, "evidence", end)
        bound = initial.load_identity(owner, owner.child(evidence, "admission", end), end)
        budget, _history, history_sha, disposition = initial_budget_originals(owner, private, bound, end)
        require(history_sha == os.environ.get("P2PKIT_INITIAL_CURRENT_HISTORY_SHA256") and
                budget.profile == profile, "INITIAL_PROVIDER_HISTORY_OUTPUT_CHANGED")
        end = min(end, budget.deadline("productive", 120))
        session = reacquire_initial_source(owner, private, bound, budget, history_sha, end, cancelled=cancelled,
            preceding=os.environ["P2PKIT_CACHE_GUARD_OUTCOME"], stage="productive")
        answer = session, (budget, history_sha, disposition)
    except BaseException as error:
        failure = error
        owner.error("initial-controller-entry", error)
    finally:
        try:
            owner.close()
        except BaseException as error:
            failure = failure or error
    if failure is not None:
        if answer is not None:
            answer[0].fail(failure)
        raise failure
    require(answer is not None and not owner.errors and not owner.unknown, "INITIAL_ENTRY_NOT_RETURNED")
    posix._deadline(end)
    answer[0].check()
    return answer


class InitialController(Controller):
    """Separate actual Stage2 controller; shared products, never Admission casting."""
    def __init__(self, profile, *, preflight=False, cancelled=None):
        cancelled = [] if cancelled is None else cancelled
        session, adopted = initial_controller_entry(profile, cancelled, preflight)
        try:
            super().__init__(profile, consume_dependencies=not preflight, preflight=preflight)
            self.cancelled, self.current_session, self.initial_adopted = cancelled, session, adopted
            self.history_sha = self.current_budget = None
            self._initial_crypto_pending = None
            require(job_time.TOKEN_ENV not in os.environ and self.actions_token is None,
                    "INITIAL_TOKEN_MUST_BE_OWNED_BEFORE_CONTROLLER")
            bound = parse(session.identity.record)
            require(bound["profile"] == profile and initial.identity.worker_cohort(session.identity.record) ==
                    ("desktop" if profile == jvm.PROFILE else profile, self.role), "INITIAL_CONTROLLER_PROFILE")
        except BaseException as error:
            session.fail(error)
            raise

    def check(self, finalizing=False):
        self.current_session.check(current=False)
        super().check(finalizing)

    def prepare_identity(self):
        require(self.consume_requested and not self.preflight, "INITIAL_RUN_REQUIRES_NATIVE_RESTORE")
        adopt_initial_preparation(self)

    def prepare_first_identity(self):
        require(self.preflight and self.initial_adopted is None, "INITIAL_FIRST_PRETOOL_ONLY")
        self.allocate()
        self.admitted = self.current_session.identity
        self.budget = job_time.derive_initial(self.current_session.current, self.job)
        self.clock = self.budget.clock
        timing = original_clock(self.budget)
        self.deadline = min(self.deadline, timing.deadline("controller-return", TOTAL_SECONDS[self.profile]))
        self.last_raw = timing.last
        self.check()
        end = self.window("productive", 45)
        directory = self.child(self.evidence, "admission", end, create=True)
        initial.retain_identity(self.current_session, self, directory, end)
        timing_directory = self.child(self.evidence, "job-time", end, create=True)
        history = self.child(timing_directory, "initial-current", end, create=True)
        self.history_sha = initial.retain_first(self.current_session, self, history, end)
        self.current_budget = initial.current_budget_disposition(self.budget, self.history_sha)
        self.write(timing_directory, "budget.json", self.budget.record, end)
        self.write(timing_directory, "current-budget.json", self.current_budget, end)
        self.check_window("productive", end)

    def acquire_job_time(self):
        raise ControllerError("INITIAL_MUST_NOT_EXECUTE_ORDINARY_JOB_TIME")

    def recheck_identity(self, destination, check, end, *, purpose, stage="productive"):
        require(type(self.admitted) in (initial.identity.InitialOrdinaryIdentity, initial.identity.InitialJvmLibraryIdentity) and
                self.current_session.identity.record == self.admitted.record, "INITIAL_SOURCE_IDENTITY_CHANGED")
        check()
        initial.claim_within(self.current_session, purpose, self.budget, stage, end)
        check()
        return self.admitted

    def bind_run_context(self, context):
        require(self.history_sha is not None and self.current_budget is not None and not self.sample_required and
                self.budget.value["schema"] == 3, "INITIAL_CONTEXT_MISSING_ORIGINAL_BUDGET")
        context["scope"] = initial.INITIAL_CONTEXT_SCOPE
        context["initialOrdinary"] = {"historySha256": self.history_sha,
            "identitySha256": digest(self.admitted.record), "sourceBudgetSha256": self.budget.sha256,
            "samplePackagingRequired": False}
        initial.initial_context(context)

    def bind_result(self, result):
        result["scope"] = initial.INITIAL_RESULT_SCOPE
        result["currentBudget"] = self.current_budget
        result["initialOrdinary"] = {"identitySha256": None if self.admitted is None else digest(self.admitted.record),
            "historySha256": self.history_sha, "samplePackagingRequired": False}

    def product_run(self):
        end = self.window("productive", 120)
        self.recheck_identity(self.runtime.path / "product-current", self.check, end, purpose="worker")
        return super().product_run()

    def before_phase_launch(self, row, directory, env, end, raw_work_end, raw_final_end):
        if row["phase"] not in ("recipient-validation", "export"):
            require(row["phase"] != "job-time", "INITIAL_FAKE_JOB_TIME_PHASE")
            return
        pending = self._initial_crypto_pending
        require(pending is not None and row["phase"] == pending["phase"] and
                row["argv"] == self.python(__file__, "_initial-crypto", pending["operation"], "--profile", self.profile,
                                            "--context-sha256", self.context_hash), "INITIAL_CRYPTO_FIXED_LAUNCH")
        self.current_session.check()
        current = initial.current_module().initial_ordinary_record(self.current_session.current)
        require(current == pending["current"], "INITIAL_CRYPTO_PRELAUNCH_CURRENT_CHANGED")
        record = parse(self.admitted.record)
        raw = encoded({"schema": 1, "scope": initial.CRYPTO_SCOPE, "operation": pending["operation"],
            "source": record["source"], "github": record["github"], "identitySha256": digest(self.admitted.record),
            "policySha256": digest(self.admitted.original_policy), "contextSha256": self.context_hash,
            "historySha256": self.history_sha, "jobBudgetSha256": self.budget.sha256,
            "currentSha256": digest(current), "current": current.decode("ascii"),
            "native": {name: row[name] for name in ("job", "invocation", "state", "home", "cwd", "phase")},
            "window": {"clock": job_time.clock_value(self.clock), "startedNs": row["startedRawNs"],
                       "workEndNs": raw_work_end, "finalEndNs": raw_final_end}})
        request = initial.crypto_request(raw, self.admitted, self.run_context_raw, self.budget, row,
            {name: env[name] for name in query._CONTEXT}, pending["operation"])
        self.write(directory, "initial-request.json", request.raw, end)
        pending["request"] = request

    def crypto_operation(self, operation):
        require(operation in ("validate", "export") and self._initial_crypto_pending is None,
                "INITIAL_CRYPTO_OPERATION")
        label = "recipient-validation" if operation == "validate" else "export"
        stage = "productive" if operation == "validate" else "export"
        end = self.window(stage, 120)
        check = lambda: (self.check(finalizing=operation == "export"), self.check_window(stage, end))
        self.recheck_identity(self.runtime.path / (operation + "-current-before"), check, end,
                              purpose="custody" if operation == "validate" else "evidence", stage=stage)
        pending = {"phase": label, "operation": operation,
            "current": initial.current_module().initial_ordinary_record(self.current_session.current),
            "qualifications": initial.current_qualifications(self.current_session), "request": None}
        self._initial_crypto_pending = pending
        first_record = len(self.records)
        try:
            row = self.phase(label, self.python(__file__, "_initial-crypto", operation, "--profile", self.profile,
                "--context-sha256", self.context_hash), 240, finalizing=operation == "export")
            returned = super().crypto_return(operation, row)
            request = pending["request"]
            expected = {"requestSha256": digest(request.raw), "currentBeforeSha256": digest(pending["current"]),
                "identitySha256": digest(self.admitted.record), "historySha256": self.history_sha}
            require(returned["result"].get("initialOrdinary") == expected, "INITIAL_CRYPTO_ORIGINAL_RETURN_CHANGED")
            stage = "productive" if operation == "validate" else "export-read"
            end = self.window(stage, 120)
            check = lambda: (self.check(finalizing=operation == "export"), self.check_window(stage, end))
            self.recheck_identity(self.runtime.path / (operation + "-current-after"), check, end,
                purpose="custody" if operation == "validate" else "evidence", stage=stage)
            require(initial.current_qualifications(self.current_session) == pending["qualifications"],
                    "INITIAL_CRYPTO_CURRENT_QUALIFICATIONS_CHANGED")
            after = initial.current_module().initial_ordinary_record(self.current_session.current)
            acceptance = encoded({"schema": 1, "scope": "INITIAL_ORDINARY_ACTUAL_CRYPTO_RETURN_ACCEPTANCE_V1",
                "operation": operation, **expected, "currentAfterSha256": digest(after),
                "phaseResultSha256": self.phase_hashes[label], "childReturnSha256": returned["sha256"],
                "jobBudgetSha256": self.budget.sha256, "acceptedAtRawNs": self.now_raw(),
                "lateSourceOriginals": "OPERATIONAL_NOT_IN_FROZEN_PAYLOAD", "retirement": "KNOWN"})
            directory = self.child(self.commands, label, end)
            self.write(directory, "source-current-acceptance.json", acceptance, end)
            returned["initialCurrentAcceptance"] = {"sha256": digest(acceptance), "record": parse(acceptance)}
            if operation == "export":
                expected_manifest = initial.manifest_data(request)
                require(returned["result"]["manifest"] == {
                    **expected_manifest, "artifact": returned["result"]["manifest"]["artifact"]},
                    "INITIAL_CRYPTO_MANIFEST_CHANGED")
            check()
            return returned
        except BaseException as error:
            self.current_session.fail(error)
            if any(row["phase"] == label and row["launchAttempted"] for row in self.records[first_record:]):
                self.error("initial-crypto-" + operation + "-return", error, unknown=True)
            raise
        finally:
            self._initial_crypto_pending = None


def profile_passed(value):
    """A boolean label cannot overrule original phase/custody outcomes."""
    if not seed.profile_passed(value):
        return False
    is_initial = value.get("scope") == initial.INITIAL_RESULT_SCOPE
    if is_initial:
        scope = value.get("initialOrdinary")
        origin = value.get("currentBudget")
        if not (type(scope) is dict and set(scope) == {"identitySha256", "historySha256", "samplePackagingRequired"} and
                scope["samplePackagingRequired"] is False and "samplePackaging" not in value and
                type(origin) is dict and origin.get("scope") == "ORIGINAL_INITIAL_ORDINARY_CURRENT_JOB_BUDGET_DATA_V1" and
                origin.get("identitySha256") == scope["identitySha256"] and
                origin.get("historySha256") == scope["historySha256"] and
                origin.get("budgetSha256") == value.get("jobBudget", {}).get("sha256") and
                origin.get("ordinaryJobTimePhase") == "NOT_EXECUTED_NOT_CLAIMED" and
                type(value.get("dependencyCache")) is dict):
            return False
    elif value.get("scope") != "ORDINARY_PROFILE_CUSTODY_ONLY" or "initialOrdinary" in value or "currentBudget" in value:
        return False
    rows = value["phases"]
    labels = ["recipient-validation", "audit-init", "custody-prepare", "product", "custody-collect",
              "custody-uninstall"]
    if value.get("profile") == jvm.PROFILE:
        if not (value.get("role") in jvm.BACKENDS and "samplePackaging" not in value and
                "jobBudget" in value and type(value.get("dependencyCache")) is dict and
                value["dependencyCache"].get("scope") == ("INITIAL_ORDINARY_NATIVE_CONSUME_ORIGINALS" if is_initial else
                                                         "ORDINARY_NATIVE_CONSUME_ORIGINALS") and
                type(value.get("dependencySeed")) is dict and
                type(value["dependencySeed"].get("admittedCount")) is int and
                value["dependencySeed"]["admittedCount"] > 0 and
                type(value["dependencySeed"].get("admittedBytes")) is int and
                value["dependencySeed"]["admittedBytes"] > 0 and
                jvm.profile_passed(value)):
            return False
        labels = ["recipient-validation", "audit-init", "product"]
    if value.get("profile") in ("desktop", jvm.PROFILE) and "jobBudget" in value:
        if not is_initial:
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
            if row["phase"] in {"recipient-validation", "audit-init", "custody-prepare", "product"} and not (
                    type(row.get("completedRawNs")) is int and
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
        labels = [*(() if is_initial else ("job-time",)), "recipient-validation", "audit-init", *simulator.PREPARE,
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
NATIVE_PREPARATION_SCOPES = ("ORIGINAL_NATIVE_CONSUME_PREPARATION_V1", "INITIAL_ORDINARY_NATIVE_CONSUME_PREPARATION_V1")
NATIVE_PROVIDER_SCOPES = ("ORIGINAL_NATIVE_CONSUME_PROVIDER_V1", "INITIAL_ORDINARY_NATIVE_CONSUME_PROVIDER_V1")
NATIVE_RESTORE_SCOPES = ("ORIGINAL_NATIVE_CONSUME_ACCEPTANCE_V1", "INITIAL_ORDINARY_NATIVE_CONSUME_ACCEPTANCE_V1")
NATIVE_PREPARATION_KEYS = (PREPARATION_KEYS - {"phaseResultSha256", "retirement"}) | {
    "budgetOrigin", "nativeProvider", "enclosingOwnerClose", "providerAcceptance"}
_PROVIDER_KEY, _PROVIDER_EPISODES, _PROVIDER_FINAL_IO = object(), {}, set()


class ProviderEpisode(PrivateOwner):
    """Actual fixed controller resource episode; never decoded bootstrap Owner.

    Preparation and readback allocate different instances/readings/ledgers. The
    native Node uses the same original provider180, never a new allowance. This
    is only ownership around maintained native file/process suppliers.
    """
    def __init__(self, key, parent, issued, hard_end, mode):
        super().__init__()
        require(key is _PROVIDER_KEY and type(parent) in (Controller, InitialController) and
                type(parent.budget) is job_time.Budget and mode in ("prepare", "service", "readback"),
                "PROVIDER_EPISODE_FACTORY")
        self.parent, self.fence, self.mode = parent, parent.budget, mode
        self.local_first = time.monotonic()
        self.first = job_time.current_reading(parent.profile)
        require(self.first.clock.role == parent.role and (parent.budget.clock is None or
                self.first.clock == parent.budget.clock), "PROVIDER_EPISODE_HOST_CLOCK")
        self.issued, self.hard_end, self.last = issued, hard_end, self.first.nanoseconds
        require(type(issued) is int and type(hard_end) is int and issued <= self.last < hard_end <=
                min(issued + 180 * job_time.NS, parent.budget.fence("productive")), "PROVIDER_EPISODE_ORIGINAL_INTERVAL")
        cap = min(hard_end, self.last + 45 * job_time.NS) if mode != "service" else hard_end
        self.work_limit = min(cap, hard_end - 45 * job_time.NS) if mode != "readback" else cap
        self.final_limit = cap
        require(self.last < self.work_limit, "PROVIDER_EPISODE_NO_TIME")
        self.local_end = job_time._directed_deadline(self.local_first, (cap - self.last) / job_time.NS, cap, self.last)
        self.closed, self.pid = False, os.getpid()
        # Fixed real parent callback, not a caller-selected resource dispatcher.
        self.cancelled = lambda: parent.check()
        _PROVIDER_EPISODES[id(self)] = (self, parent, parent.budget, self.first, self.resources, self.cancelled,
            self.local_end, self.work_limit, self.final_limit, self.issued, self.hard_end, mode, self.pid)
        self.end()

    def _same(self):
        saved = _PROVIDER_EPISODES.get(id(self))
        require(type(self) is ProviderEpisode and saved is not None and saved[0] is self and
                self.parent is saved[1] and self.fence is saved[2] is self.parent.budget and
                self.first is saved[3] and self.resources is saved[4] and self.cancelled is saved[5] and
                (self.local_end, self.work_limit, self.final_limit, self.issued, self.hard_end, self.mode, self.pid) ==
                saved[6:] and self.pid == os.getpid(), "PROVIDER_EPISODE_REPLACED")
        if type(self.parent) is InitialController:
            self.parent.current_session.check(current=False)  # Source is HISTORY during long provider work.

    def end(self, *, final=False):
        self._same()
        require(not self.closed and not self.unknown and (final or self.original is None), "PROVIDER_EPISODE_NOT_LIVE")
        if not final:
            self.cancelled()
        local = time.monotonic()  # Earlier LOCAL, then RAW; never renew elapsed work.
        self.last = job_time.raw_now(self.last, clock=self.first.clock)
        cap = self.final_limit if final else self.work_limit
        require(self.last < cap, "PROVIDER_EPISODE_EXPIRED")
        end = min(self.local_end, job_time._directed_deadline(local, 180, cap, self.last))
        posix._deadline(end)
        return end

    def acquire(self, label, factory):
        final = id(self) in _PROVIDER_FINAL_IO
        self.end(final=final)
        value = super().acquire(label, factory)
        self.end(final=final)  # Preserve a returned allocation before a late failure.
        return value

    def final_io(self, scope):
        """Only the actual already-closed service native owner unlocks final IO."""
        self.end(final=True)
        require(self.mode == "service" and id(self) not in _PROVIDER_FINAL_IO and
                not self.errors and self.original is None and scope is not None and
                any(row["owner"] is scope and row["attempted"] and row["closed"] for row in self.resources),
                "PROVIDER_FINAL_IO_REQUIRES_NATIVE_CLOSE")
        _PROVIDER_FINAL_IO.add(id(self))

    def close_fence(self):
        try:
            self._same()
            self.last = job_time.raw_now(self.last, clock=self.first.clock)
            require(self.last < self.final_limit, "PROVIDER_EPISODE_CLOSE_EXPIRED")
            posix._deadline(self.local_end)
        except BaseException as error:
            self.error("provider-close-fence", error)

    def close_one(self, value):
        self.close_fence()
        super().close_one(value)
        self.close_fence()

    def close(self):
        if self.closed:
            return
        self.close_fence()
        try:
            super().close()
        finally:
            self.closed = True
        self.close_fence()
        if self.original is not None:
            raise self.original

    def original_close(self):
        self._same()
        require(self.closed and not self.unknown and not self.errors and self.original is None and
                all(row["attempted"] and row["closed"] for row in self.resources), "PROVIDER_EPISODE_CLOSE_REQUIRED")
        return {"scope": "ACTUAL_ORDINARY_PROVIDER_RESOURCE_EPISODE_CLOSE_V1", "mode": self.mode,
            "clock": job_time.clock_value(self.first.clock), "firstNs": self.first.nanoseconds,
            "issuedNs": self.issued, "hardEndNs": self.hard_end, "workEndNs": self.work_limit,
            "finalEndNs": self.final_limit, "closedNs": self.last, "resources": len(self.resources),
            "retirement": "KNOWN", "errors": []}


def provider_input(owner, directory, frame_raw):
    """Known writer close, then distinct read-only stdin owner at position0."""
    end = owner.end()
    require(type(frame_raw) is bytes and 0 < len(frame_raw) <= 16384, "PROVIDER_STDIN_BOUND")
    owner.write(directory, "service-input.json", frame_raw, end)
    original = owner.acquire("provider-stdin-directory", lambda: seed.private_root(directory.path))
    reader = owner.acquire("provider-stdin-reader", lambda: original.open_file(
        "service-input.json", max_bytes=16384, deadline=owner.local_end))
    info = reader.verify()
    require(info.size == len(frame_raw) and reader.read(len(frame_raw)) == frame_raw and reader.read(1) == b"" and
            reader.verify() == info and reader.seek(0) == 0, "PROVIDER_STDIN_ORIGINAL")
    # The POSIX maintained reader intentionally has no general fileno API.
    # Retain that exact typed owner's pin; Scope only borrows the captured fd.
    handle = reader if os.name == "nt" else reader._pins[-1].fd
    return reader, handle, seed._info_binding(info)


def provider_service(parent, prepared, frame_raw, node, tool_path, service_environment, *, issued, hard_end):
    """Fixed service-only Node in the real maintained outer native domain."""
    import hosted_cache_provider_readback as native_readback
    from hosted_cache_provider_environment import SERVICE_FIELDS, runtime_service_fragment
    is_initial = type(parent) is InitialController
    owner = ProviderEpisode(_PROVIDER_KEY, parent, issued, hard_end, "service")
    private = directory = out = err = reader = scope = child = None
    original, returned, native_known = None, None, False
    env = None
    invocation = uuid.uuid4().hex
    row = {"schema": 1, "scope": "ORDINARY_PROVIDER_SERVICE_NATIVE_RETURN_V1", "job": parent.job,
        "invocation": invocation, "pid": os.getpid(), "role": parent.role, "startedNs": None,
        "completedNs": None, "closedNs": None, "exitCode": None, "launchAttempted": False,
        "scopeAttempted": False, "retirement": "UNKNOWN", "errors": []}
    try:
        private = owner.open(parent.runtime.path / "cache-provider")
        directory = owner.child(private, "service", owner.end(), create=True)
        reader, stdin, input_identity = provider_input(owner, directory, frame_raw)
        row["input"] = {"bytes": len(frame_raw), "sha256": digest(frame_raw), "identity": input_identity}
        out = owner.acquire("provider-node-stdout", lambda: directory.create_file(
            "stdout.log", max_bytes=16384, deadline=owner.local_end))
        err = owner.acquire("provider-node-stderr", lambda: directory.create_file(
            "stderr.log", max_bytes=MIB, deadline=owner.local_end))
        argv = [node, str(SCRIPTS / "hosted-cache-provider-action.cjs"),
            "--initial-ordinary-restore-service" if is_initial else "--ordinary-restore-service"]
        context = parse(prepared.request)
        base = {"PATH": tool_path, "GITHUB_WORKSPACE": str(ROOT), "LANG": "C", "LC_ALL": "C"}
        if os.name == "nt":
            require(type(parent.environment.get("SYSTEMROOT")) is str, "PROVIDER_SERVICE_SYSTEMROOT")
            base.update(SYSTEMROOT=parent.environment["SYSTEMROOT"], USERPROFILE=context["home"],
                        TEMP=context["home"], TMP=context["home"], PATHEXT=".EXE")
        else:
            base.update(HOME=context["home"], TMPDIR=context["home"])
        base.update(query._inherited_context())
        env = processes.ownership_environment(base, parent.job, invocation, str(parent.path),
                                               str(parent.path / "control-home"), allow_new_context=True)
        env.update(runtime_service_fragment(service_environment))
        require(set(env) == set(base) | set(query._CONTEXT) | set(SERVICE_FIELDS) and
                not any(name in env for name in (job_time.TOKEN_ENV, "GITHUB_TOKEN", "GH_TOKEN", "GITHUB_OUTPUT")),
                "PROVIDER_SERVICE_CREDENTIAL_DOMAIN")
        row.update(argv=argv, cwd=str(ROOT), state=str(parent.path), home=str(parent.path / "control-home"))
        row["scopeAttempted"] = True
        scope = owner.acquire("provider-node-native", lambda: processes.make_scope(
            parent.job, invocation, str(parent.path), str(parent.path / "control-home")))
        owner.end()
        row["startedNs"] = owner.last
        row["launchAttempted"] = True
        child = scope.spawn(argv, str(ROOT), env, stdout=out, stderr=err, stdin=stdin)
        require(child.stdout is None and child.stderr is None, "PROVIDER_NATIVE_PRIVATE_SINKS")
        native_readback.launch._scope_binding(scope, parent.role, parent.job, invocation,
                                              str(parent.path), str(parent.path / "control-home"))
        native_readback.launch._leader(scope, child, parent.role)
        while True:
            owner.end()
            if os.name == "nt":
                out.observe_live_output()
                err.observe_live_output()
            else:
                out.verify()
                err.verify()
            code = child.poll()
            if code is not None:
                row["exitCode"] = code
                owner.end()
                row["completedNs"] = owner.last
                require(type(code) is int and code == 0, "PROVIDER_NODE_EXIT")
                break
            scope.discover()
            time.sleep(.05)
    except BaseException as error:
        original = error
        owner.error("provider-node", error)
    finally:
        if env is not None:
            for name in SERVICE_FIELDS:
                env.pop(name, None)
        if scope is not None:
            try:
                row["ownedSurvivors"] = scope.drain(grace=5, kill_wait=5)
                row["ownership"] = scope.description()
                require(row["ownedSurvivors"] == [] and row["ownership"].get("discoveryErrors") == [],
                        "PROVIDER_NODE_RETIREMENT")
                native_known = True
            except BaseException as error:
                owner.error("provider-node-drain", error, unknown=True)
            owner.close_one(scope)
        elif row["scopeAttempted"]:
            owner.error("provider-node-construction", original or ControllerError("PROVIDER_SCOPE_UNKNOWN"), unknown=True)
        else:
            native_known = True
        if native_known and not owner.unknown:
            for stream in (out, err):
                if stream is not None:
                    try:
                        stream.sync()
                        stream.verify()
                    except BaseException as error:
                        owner.error("provider-node-capture", error)
                    owner.close_one(stream)
            if reader is not None:
                try:
                    # The shared offset naturally advanced while Node read.
                    # Full rewind/read/EOF/native binding precedes reader close.
                    require(seed._info_binding(reader.verify()) == row["input"]["identity"] and reader.seek(0) == 0 and
                            reader.read(len(frame_raw)) == frame_raw and reader.read(1) == b"" and
                            seed._info_binding(reader.verify()) == row["input"]["identity"], "PROVIDER_STDIN_CHANGED")
                except BaseException as error:
                    owner.error("provider-stdin-return", error)
                owner.close_one(reader)
        else:
            owner.unknown = True
        try:
            if original is None and native_known and not owner.unknown and owner.original is None:
                owner.final_io(scope)
                end = owner.end(final=True)
                raw = owner.read(directory, "stdout.log", end, 16384)
                stderr = owner.read(directory, "stderr.log", end, MIB)
                require(stderr == b"", "PROVIDER_NODE_STDERR")
                returned, ack = initial.service_return(raw, frame_raw, prepared.request, initial_ordinary=is_initial)
                row.update(stdout={"bytes": len(raw), "sha256": digest(raw)},
                           stderr={"bytes": len(stderr), "sha256": digest(stderr)},
                           retirement="KNOWN", errors=[])
                row["closedNs"] = job_time.raw_now(owner.last, clock=owner.first.clock)
                owner.last = row["closedNs"]
                require(ack.observed_ns <= row["closedNs"] < hard_end, "PROVIDER_NODE_POST_CLOSE_TIME")
                validate_provider_node(row, prepared.request, frame_raw, raw, is_initial)
                owner.write(directory, "native-return.json", row, end)
        except BaseException as error:
            original = original or error
            owner.error("provider-node-final", error)
        finally:
            try:
                owner.close()  # Receipt failure never skips the original ledger.
            except BaseException as error:
                original = original or error
                owner.error("provider-node-owner-close", error)
    if original is not None:
        parent.error("provider-node", original, unknown=owner.unknown)
        raise original
    require(returned is not None and owner.closed and not owner.unknown and not owner.errors,
            "PROVIDER_NODE_NOT_RETURNED")
    return row, raw, owner.original_close()


def validate_provider_node(row, request_raw, frame_raw, service_raw, is_initial):
    request = parse(request_raw)
    value, ack = initial.service_return(service_raw, frame_raw, request_raw, initial_ordinary=is_initial)
    role = request["role"]
    argv = [request["node"], str(SCRIPTS / "hosted-cache-provider-action.cjs"),
            "--initial-ordinary-restore-service" if is_initial else "--ordinary-restore-service"]
    require(type(row) is dict and set(row) == set("schema scope job invocation pid role startedNs completedNs closedNs "
            "exitCode launchAttempted scopeAttempted retirement errors input argv cwd state home ownedSurvivors "
            "ownership stdout stderr".split()) and row.get("schema") == 1 and type(row["schema"]) is int and
            row.get("scope") == "ORDINARY_PROVIDER_SERVICE_NATIVE_RETURN_V1" and row.get("role") == role and
            row.get("argv") == argv and row.get("cwd") == str(ROOT) and type(row.get("exitCode")) is int and
            row["exitCode"] == 0 and row.get("retirement") == "KNOWN" and row.get("errors") == [] and
            row.get("ownedSurvivors") == [] and row.get("launchAttempted") is row.get("scopeAttempted") is True and
            row.get("input", {}).get("sha256") == digest(frame_raw) and row["input"].get("bytes") == len(frame_raw) and
            row.get("stdout") == {"bytes": len(service_raw), "sha256": digest(service_raw)} and
            row.get("stderr") == {"bytes": 0, "sha256": digest(b"")} and
            all(type(row[name]) is str and re.fullmatch(r"[0-9a-f]{32}", row[name]) for name in ("job", "invocation")) and
            type(row["pid"]) is int and row["pid"] > 0 and
            row["state"] == request["plan"]["session"] and
            row["home"] == str(Path(row["state"]) / "control-home"), "PROVIDER_NODE_ORIGINAL_RESULT")
    input_row = row["input"]
    require(type(input_row) is dict and set(input_row) == {"bytes", "sha256", "identity"} and
            seed._file_binding(input_row["identity"]),
            "PROVIDER_NODE_ORIGINAL_STDIN_IDENTITY")
    ownership = row["ownership"]
    backend = "windows-job-list-suspended" if role == "windows-x64" else (
        "linux-proc-pidfd" if role == "linux-x64" else "darwin-libproc-audit-token")
    require(ownership.get("backend") == backend and ownership.get("job") == row["job"] and
            ownership.get("invocation") == row["invocation"] and ownership.get("discoveryErrors") == [] and
            ownership.get("startedIdentities") and type(ownership.get("launches")) is list and
            len(ownership["launches"]) == 1, "PROVIDER_NODE_NATIVE_ORIGINAL")
    launch = ownership["launches"][0]
    require(launch.get("requestedArgv") == launch.get("resolvedArgv") == argv and launch.get("created") is True and
            launch.get("cwd") == str(ROOT) and type(launch.get("pid")) is int and launch["pid"] > 0 and
            launch.get("inputMode") == ("caller-owned-native-file" if role == "windows-x64" else "caller-owned-file") and
            launch.get("outputMode") == ("caller-owned-native-files" if role == "windows-x64" else "caller-owned-files"),
            "PROVIDER_NODE_FIXED_STDIN_LAUNCH")
    require(all(type(row.get(name)) is int for name in ("startedNs", "completedNs", "closedNs")) and
            int(request["issuedNs"]) <= row["startedNs"] <= ack.observed_ns <= row["completedNs"] <= row["closedNs"] <
            int(request["hardEndNs"]), "PROVIDER_NODE_ORIGINAL_CHRONOLOGY")
    if role == "windows-x64":
        import subprocess
        require(launch.get("api") == "CreateProcessW" and launch.get("resumed") is True and launch.get("batch") is False and
                launch.get("applicationName") == argv[0] and launch.get("commandLine") == subprocess.list2cmdline(argv),
                "PROVIDER_NODE_WINDOWS_FRAME")
    else:
        require(launch.get("api") == "subprocess.Popen" and launch.get("shell") is False and
                launch.get("executable") == argv[0], "PROVIDER_NODE_POSIX_FRAME")
    return value, ack


def provider_file_bytes(owner, directory, name, maximum, end, check):
    """Fixed bounded raw-file reader; the six-MiB packet is NOT JSON metadata."""
    require(type(maximum) is int and 0 < maximum <= 6 * MIB, "PROVIDER_RAW_LIMIT")
    root = reader = None
    failure, raw, binding = None, bytearray(), None
    try:
        check()
        root = owner.acquire("provider-raw-root", lambda: seed.private_root(directory.path))
        reader = owner.acquire("provider-raw-reader", lambda: root.open_file(name, max_bytes=maximum, deadline=end))
        info = reader.verify()
        while len(raw) < info.size:
            check()
            block = reader.read(min(MIB, info.size - len(raw)))
            require(type(block) is bytes and 0 < len(block) <= info.size - len(raw), "PROVIDER_RAW_SHORT_READ")
            raw.extend(block)
        require(reader.read(1) == b"" and reader.verify() == info, "PROVIDER_RAW_CHANGED_OR_NOT_EOF")
        binding = seed._info_binding(info)
        check()
    except BaseException as error:
        failure = error
        owner.error("provider-raw-reader", error)
    finally:
        for resource in (reader, root):
            if resource is not None:
                owner.close_one(resource)
    if failure is not None:
        raise failure
    require(binding is not None and not owner.unknown, "PROVIDER_RAW_CLOSE_UNKNOWN")
    check()
    return bytes(raw), binding


def copy_provider_originals(owner, source, destination, readback):
    """Stream all four actual originals before product, then reread/known-close.

    read_success has already bound the original ACK/bytes/native identities.
    The new reads below prove the actual copy, never synthesize provider data
    from ACK hashes or feed a six-MiB packet through the metadata writer.
    """
    import hosted_cache_provider_readback as native
    require(type(owner) is ProviderEpisode and owner.mode == "readback" and
            type(readback) is native.ProviderReadback, "PROVIDER_ORIGINAL_COPY_OWNER")
    references, originals = dict(readback.acknowledgement.files), dict(readback.originals)
    require(set(originals) == {row[0] for row in native.ORIGINAL_FILES}, "PROVIDER_ORIGINAL_COPY_ROSTER")
    source_root = target_root = None
    copied, identities = [], {tuple(reference.identity) for reference in references.values()}
    require(len(identities) == 4, "PROVIDER_ORIGINAL_FILE_ALIAS")
    try:
        source_root = owner.acquire("provider-copy-source", lambda: seed.private_root(source.path))
        target_root = owner.acquire("provider-copy-target", lambda: seed.private_root(destination.path))
        require(source_root.identity != target_root.identity, "PROVIDER_COPY_ROOT_ALIAS")
        for slot, name, maximum in native.ORIGINAL_FILES:
            reference, raw = references[slot], originals[slot]
            reader = writer = None
            end = owner.end()
            hashed, size, written_identity = hashlib.sha256(), 0, None
            try:
                reader = owner.acquire("provider-copy-reader", lambda: source_root.open_file(
                    name, max_bytes=maximum, deadline=end))
                before = reader.verify()
                require(tuple(before.identity) == reference.identity and before.size == reference.size == len(raw) and
                        digest(raw) == reference.sha256, "PROVIDER_COPY_ORIGINAL_REPLACED")
                writer = owner.acquire("provider-copy-writer", lambda: target_root.create_file(
                    name, max_bytes=max(1, reference.size), deadline=end))
                while size < reference.size:
                    owner.end()
                    block = reader.read(min(MIB, reference.size - size))
                    require(type(block) is bytes and block and size + len(block) <= reference.size and
                            block == raw[size:size + len(block)] and writer.write(block) == len(block),
                            "PROVIDER_COPY_CHANGED_OR_SHORT")
                    size += len(block)
                    hashed.update(block)
                require(reader.read(1) == b"" and reader.verify() == before and size == reference.size and
                        hashed.hexdigest() == reference.sha256, "PROVIDER_COPY_ORIGINAL_CHANGED")
                writer.sync()
                after = writer.verify()
                require(after.size == size and tuple(after.identity) not in identities, "PROVIDER_COPY_OUTPUT_ALIAS")
                written_identity = tuple(after.identity)
                identities.add(written_identity)
            finally:
                for stream in (writer, reader):
                    if stream is not None:
                        owner.close_one(stream)
            owner.end()
            copied_raw, binding = provider_file_bytes(owner, destination, name, maximum, owner.end(), owner.end)
            require(copied_raw == raw and tuple(binding["identity"]) == written_identity,
                    "PROVIDER_COPY_READBACK_CHANGED")
            copied.append({"slot": slot, "name": name, "bytes": size, "sha256": reference.sha256,
                "originalIdentity": list(reference.identity), "copyIdentity": binding})
        require(set(target_root.names(max_names=4, deadline=owner.end())) == {row[1] for row in native.ORIGINAL_FILES},
                "PROVIDER_COPY_EXACT_ROSTER")
        owner.end()
    finally:
        for resource in (target_root, source_root):
            if resource is not None:
                owner.close_one(resource)
    owner.end()
    return copied


def read_native_provider_originals(owner, directory, declarations, end, check):
    import hosted_cache_provider_readback as native
    require(type(declarations) is list and len(declarations) == 4 and
            [row.get("slot") for row in declarations] == [slot for slot, _, _ in native.ORIGINAL_FILES],
            "PROVIDER_COPIED_ORIGINAL_ROSTER")
    original_ids, copy_ids, raw = set(), set(), {}
    require(set(seed_names(owner, directory.path, end)) == {row[1] for row in native.ORIGINAL_FILES},
            "PROVIDER_COPIED_FILE_ROSTER")
    for row, (slot, name, maximum) in zip(declarations, native.ORIGINAL_FILES):
        require(type(row) is dict and set(row) == {"slot", "name", "bytes", "sha256", "originalIdentity", "copyIdentity"} and
                row["name"] == name and type(row["bytes"]) is int and 0 <= row["bytes"] <= maximum and
                type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) and
                seed._identity(row["originalIdentity"]) and seed._file_binding(row["copyIdentity"]),
                "PROVIDER_COPIED_ORIGINAL_FIELDS")
        source_id, copy_id = tuple(row["originalIdentity"]), tuple(row["copyIdentity"]["identity"])
        require(source_id not in original_ids | copy_ids and copy_id not in original_ids | copy_ids | {source_id},
                "PROVIDER_COPIED_ORIGINAL_ALIAS")
        original_ids.add(source_id)
        copy_ids.add(copy_id)
        raw[slot], binding = provider_file_bytes(owner, directory, name, maximum, end, check)
        require(binding == row["copyIdentity"] and (len(raw[slot]), digest(raw[slot])) == (row["bytes"], row["sha256"]),
                "PROVIDER_COPIED_ORIGINAL_CHANGED")
    return raw


def native_origin(admitted):
    if type(admitted) in (initial.identity.InitialOrdinaryIdentity, initial.identity.InitialJvmLibraryIdentity):
        require(initial.identity.worker_cohort(admitted.record) is not None, "INITIAL_NATIVE_IDENTITY")
        return 1
    require(type(admitted) is identity.Admission and initial.identity.worker_cohort(admitted.record) is None,
            "ORDINARY_NATIVE_IDENTITY")
    return 0


def native_budget_origin(owner, private, admitted, budget, end):
    if native_origin(admitted):
        rebuilt, _history, _sha, disposition = initial_budget_originals(owner, private, admitted, end)
        require(rebuilt.record == budget.record, "NATIVE_INITIAL_BUDGET_CHANGED")
        return disposition
    require(budget.value["schema"] in (1, 2), "NATIVE_ORDINARY_BUDGET_ONLY")
    return {"scope": "ORIGINAL_ORDINARY_JOB_TIME_PHASE", "phaseResultSha256":
            budget.value["provenance"]["phaseResultSha256"]}


def read_native_preparation(owner, private, admitted, budget, raw, end):
    """Exact native successor. Disconnected legacy scopes are never recast."""
    index = native_origin(admitted)
    value, record = parse(raw), parse(admitted.record)
    require(len(raw) <= 2 * MIB and raw == encoded(value) and set(value) == NATIVE_PREPARATION_KEYS and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == NATIVE_PREPARATION_SCOPES[index] and
            value["profile"] == budget.profile == record["profile"] and value["source"] == record["source"] and
            value["github"] == record["github"] and value["admissionSha256"] == digest(admitted.record) and
            value["session"] == str(private.path) == str(session_path(value["profile"], value["role"])) and
            value["sessionIdentity"] == list(private.identity) and value["role"] == processes.host_role() and
            type(value["pid"]) is int and value["pid"] > 0 and
            value["jobBudgetSha256"] == budget.sha256 and value["job"] == budget.value["provenance"]["controllerJob"] and
            value["budgetOrigin"] == native_budget_origin(owner, private, admitted, budget, end) and
            value["enclosingOwnerClose"] == "NOT_OBSERVED" and value["providerAcceptance"] == "NOT_ESTABLISHED",
            "NATIVE_PREPARATION_ORIGINAL_BINDING")
    require(type(value["directories"]) is dict and set(value["directories"]) == set(PREPARATION_DIRECTORIES),
            "NATIVE_PREPARATION_DIRECTORY_ROSTER")
    private.verify()
    for name, before in value["directories"].items():
        current = owner.child(private, name, end)
        current.verify()
        require(list(current.identity) == before, "NATIVE_PREPARATION_DIRECTORY_CHANGED")
    directory = cache_directory(owner, private, end)
    plan_raw, stage_raw = (owner.read(directory, name, end) for name in ("plan.json", "staging.json"))
    plan = parse(plan_raw)
    require(plan_raw == encoded(plan) and digest(plan_raw) == value["planSha256"] and
            digest(stage_raw) == value["stagingSha256"], "NATIVE_PREPARATION_PLAN_CHANGED")
    interval = value["restoreWindow"]
    require(type(interval) is dict and set(interval) == {"beganRawNs", "endRawNs", "timeoutMinutes"} and
            all(type(item) is int for item in interval.values()) and type(value["completedRawNs"]) is int and
            budget.value["responseFinishedRawNs"] <= value["completedRawNs"] == interval["beganRawNs"] < interval["endRawNs"] and
            interval["endRawNs"] == min(budget.fence("productive"), interval["beganRawNs"] + 180 * job_time.NS) and
            interval["timeoutMinutes"] == (interval["endRawNs"] - interval["beganRawNs"]) // (60 * job_time.NS) and
            1 <= interval["timeoutMinutes"] <= 3, "NATIVE_PREPARATION_ORIGINAL_WINDOW")
    require(type(value["nativeProvider"]) is str and value["nativeProvider"].isascii() and
            len(value["nativeProvider"]) <= 16384, "NATIVE_PREPARATION_DESCRIPTOR_BYTES")
    descriptor_raw = value["nativeProvider"].encode("ascii")
    descriptor = parse(descriptor_raw)
    prepared = owner.child(owner.child(private, "runtime", end), "cache-provider", end)
    clock = job_time.clock_identity(descriptor.get("clock"))
    require(descriptor_raw == encoded(descriptor) and set(descriptor) == set("schema scope phase source github planSha256 "
            "directory directoryIdentity clock providerWindow providerRequest providerExecution enclosingOwnerClose "
            "providerAcceptance".split()) and type(descriptor["schema"]) is int and descriptor["schema"] == 1 and
            descriptor["scope"] == ("P2PKIT_INITIAL_ORDINARY_RESTORE_NATIVE_DESCRIPTOR_V1" if index else
                                     "P2PKIT_ORDINARY_RESTORE_NATIVE_DESCRIPTOR_V1") and
            descriptor["phase"] == "restore" and descriptor["source"] == value["source"] and
            descriptor["github"] == value["github"] and descriptor["planSha256"] == value["planSha256"] and
            descriptor["directory"] == str(prepared.path) == str(private.path / "runtime/cache-provider") and
            descriptor["directoryIdentity"] == list(prepared.identity) and clock.role == value["role"] and
            (budget.clock is None or clock == budget.clock) and descriptor["providerWindow"] == {
                "issuedNs": interval["beganRawNs"], "hardEndNs": interval["endRawNs"], "actualProviderStart": "NOT_OBSERVED"} and
            descriptor["providerRequest"] == cache.restore_provider_contract(plan)["request"] and
            descriptor["providerExecution"] == "NOT_PERFORMED" and descriptor["enclosingOwnerClose"] == "NOT_OBSERVED" and
            descriptor["providerAcceptance"] == "NOT_ESTABLISHED", "NATIVE_PREPARATION_DESCRIPTOR_BINDING")
    return raw


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
    if value.get("scope") in NATIVE_PREPARATION_SCOPES:
        return read_native_preparation(owner, private, admitted, budget, raw, end)
    require(native_origin(admitted) == 0, "INITIAL_REQUIRES_NATIVE_PREPARATION")
    require(record["profile"] != jvm.PROFILE, "JVM_REQUIRES_NATIVE_PREPARATION")
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
    if parse(prepared_raw)["scope"] in NATIVE_PREPARATION_SCOPES:
        return native_consume_binding(owner, private, admitted, budget, prepared_raw, end,
                                      staging_raw=staging_raw, inputs=inputs, compiled=compiled)
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


def provider_episode_close(value, mode, interval, clock):
    require(type(value) is dict and set(value) == set("scope mode clock firstNs issuedNs hardEndNs workEndNs finalEndNs "
            "closedNs resources retirement errors".split()) and
            value["scope"] == "ACTUAL_ORDINARY_PROVIDER_RESOURCE_EPISODE_CLOSE_V1" and value["mode"] == mode and
            value["clock"] == job_time.clock_value(clock) and value["issuedNs"] == interval["beganRawNs"] and
            value["hardEndNs"] == interval["endRawNs"] and value["retirement"] == "KNOWN" and value["errors"] == [] and
            all(type(value[name]) is int for name in
                ("firstNs", "issuedNs", "hardEndNs", "workEndNs", "finalEndNs", "closedNs", "resources")) and
            value["resources"] > 0 and value["issuedNs"] <= value["firstNs"] <= value["closedNs"] < value["finalEndNs"] <=
            value["hardEndNs"] and value["firstNs"] < value["workEndNs"] <= value["finalEndNs"],
            "PROVIDER_ORIGINAL_RESOURCE_CLOSE")
    final = min(value["hardEndNs"], value["firstNs"] + 45 * job_time.NS) if mode != "service" else value["hardEndNs"]
    work = min(final, value["hardEndNs"] - 45 * job_time.NS) if mode != "readback" else final
    require(value["workEndNs"] == work and value["finalEndNs"] == final, "PROVIDER_ORIGINAL_RESOURCE_WINDOW")


def native_consume_binding(owner, private, admitted, budget, prepared_raw, end, *, staging_raw=None,
                           inputs=None, compiled=None):
    """Native-success originals -> actual retained raw4 -> exact source acceptance.

    This reader verifies DATA. Product adoption additionally requires the actual
    complete fixed launcher step and a new ordinary admission/initial current.
    """
    import hosted_cache_provider_readback as native
    index = native_origin(admitted)
    directory = cache_directory(owner, private, end)
    plan_raw, original_stage, provider_raw, restored_raw = (owner.read(directory, name, end) for name in
        ("plan.json", "staging.json", "provider.json", "restoration.json"))
    prepared, plan, provider, restored = map(parse, (prepared_raw, plan_raw, provider_raw, restored_raw))
    if compiled is None:
        inputs, compiled = seed.source_inputs(owner, ROOT, end, lambda: posix._deadline(end))
    require(staging_raw is None or staging_raw == original_stage, "NATIVE_RESTORE_STAGE_CHANGED")
    cache.validate_plan(plan, admitted.record, original_stage, compiled, inputs, session=private.path,
        profile=seed.byte_cohort(admitted.record, prepared["profile"], prepared["role"])[0],
        role=prepared["role"], mode="consume")
    require(set(provider) == set("schema scope preparationSha256 planSha256 jobBudgetSha256 source github request frame "
            "serviceReturn python bindings clockBindings nativeReturn preparationClose serviceClose readbackClose originals "
            "classification observedRawNs readbackRawNs toolsSha256 currentBefore".split()) and
            type(provider["schema"]) is int and provider["schema"] == 1 and provider["scope"] == NATIVE_PROVIDER_SCOPES[index] and
            provider["preparationSha256"] == digest(prepared_raw) and provider["planSha256"] == digest(plan_raw) and
            provider["jobBudgetSha256"] == budget.sha256 and provider["source"] == prepared["source"] and
            provider["github"] == prepared["github"] and provider_raw == encoded(provider) and
            all(type(provider[name]) is str and provider[name].isascii() for name in ("request", "frame", "serviceReturn")) and
            provider["python"] == str(Path(sys.executable).resolve(strict=True)), "NATIVE_PROVIDER_ENVELOPE")
    request_raw, frame_raw, service_raw = (provider[name].encode("ascii") for name in ("request", "frame", "serviceReturn"))
    request, _ = native.outer._context(request_raw)
    require(request["plan"] == plan and request["phase"] == "restore" and
            request["issuedNs"] == str(prepared["restoreWindow"]["beganRawNs"]) and
            request["hardEndNs"] == str(prepared["restoreWindow"]["endRawNs"]), "NATIVE_PROVIDER_ORIGINAL_REQUEST")
    frame = parse(frame_raw)
    require(frame.get("request") == provider["request"] and frame.get("python") == provider["python"] and
            frame.get("bindings") == provider["bindings"] and frame.get("clockBindings") == provider["clockBindings"],
            "NATIVE_PROVIDER_FRAME_BINDING")
    service, ack = validate_provider_node(provider["nativeReturn"], request_raw, frame_raw, service_raw, bool(index))
    raw_directory = owner.child(directory, "provider-originals", end)
    raw_files = read_native_provider_originals(owner, raw_directory, provider["originals"], end,
                                               lambda: posix._deadline(end))
    decoded = native.decode_originals(raw_files, request_raw, service["acknowledgement"].encode("ascii"), 0,
                                      python=provider["python"], bindings=provider["bindings"])
    actual = decoded.provider
    require(actual.scope == "TRANSPORTED_PROVIDER_CAPTURE_ONLY_V2" and actual.kind == "success" and
            provider["toolsSha256"] == digest(actual.tools) and provider["observedRawNs"] == actual.observed_ns and
            type(provider["readbackRawNs"]) is int, "NATIVE_PROVIDER_ORIGINAL_V2")
    for row in provider["originals"]:
        require(tuple(row["originalIdentity"]) == dict(ack.files)[row["slot"]].identity,
                "NATIVE_PROVIDER_ORIGINAL_IDENTITY_CHANGED")
    classification = cache.provider_observation(plan, "restore", original_outcome="success", outputs=dict(actual.outputs))
    require(provider["classification"] == classification and classification["status"] == "REPORTED_EXACT_HIT",
            "NATIVE_PROVIDER_NO_EXACT_HIT")
    clock = job_time.clock_identity(parse(prepared["nativeProvider"].encode("ascii"))["clock"])
    for field, mode in (("preparationClose", "prepare"), ("serviceClose", "service"), ("readbackClose", "readback")):
        provider_episode_close(provider[field], mode, prepared["restoreWindow"], clock)
    require(provider["preparationClose"]["closedNs"] <= provider["serviceClose"]["firstNs"] <=
            provider["nativeReturn"]["startedNs"] <= actual.observed_ns <= actual.tools_closed_ns <= ack.observed_ns <=
            provider["nativeReturn"]["closedNs"] <= provider["serviceClose"]["closedNs"] <=
            provider["readbackClose"]["firstNs"] <= provider["readbackRawNs"] <= provider["readbackClose"]["closedNs"],
            "NATIVE_PROVIDER_ORIGINAL_ORDER")
    expected = {"schema": 1, "scope": NATIVE_RESTORE_SCOPES[index], "preparationSha256": digest(prepared_raw),
        "planSha256": digest(plan_raw), "stagingSha256": digest(original_stage), "providerSha256": digest(provider_raw),
        "jobBudgetSha256": budget.sha256, "source": prepared["source"], "github": prepared["github"],
        "observedRawNs": provider["readbackClose"]["closedNs"], "retirement": "KNOWN",
        "enclosingControllerReturn": "NOT_OBSERVED"}
    require(set(restored) == set(expected) | {"acceptedAtRawNs", "currentAfter", "currentJoin"} and
            all(restored[name] == value for name, value in expected.items()) and restored_raw == encoded(restored) and
            type(restored["acceptedAtRawNs"]) is int and
            restored["observedRawNs"] <= restored["acceptedAtRawNs"] < budget.fence("productive"),
            "NATIVE_RESTORE_ACCEPTANCE_BINDING")
    if index:
        _original_budget, history, _hash, _disposition = initial_budget_originals(owner, private, admitted, end)
        qualifications = tuple(owner.read(history, "qualification-" + str(n) + ".json", end) for n in range(1, 5))
        join = initial.provider_join_data(qualifications, plan, actual)
        require(restored["currentJoin"] == join and provider["currentBefore"] != restored["currentAfter"],
                "NATIVE_RESTORE_CURRENT_JOIN_CHANGED")
        for text in (provider["currentBefore"], restored["currentAfter"]):
            require(type(text) is str and text.isascii(), "NATIVE_RESTORE_CURRENT_DATA")
            current = initial.identity.retained_worker_current(text.encode("ascii"), admitted, prepared["role"])
            require(current["qualifications"] == join["qualificationsSha256"],
                    "NATIVE_RESTORE_CURRENT_DATA_CHANGED")
    else:
        require(provider["currentBefore"] is restored["currentAfter"] is restored["currentJoin"] is None,
                "ORDINARY_RESTORE_CANNOT_USE_INITIAL_AUTHORITY")
    return {"scope": "INITIAL_ORDINARY_NATIVE_CONSUME_ORIGINALS" if index else "ORDINARY_NATIVE_CONSUME_ORIGINALS",
        "preparationSha256": digest(prepared_raw), "restorationSha256": digest(restored_raw), "planSha256": digest(plan_raw),
        "providerSha256": digest(provider_raw), "stagingSha256": digest(original_stage),
        "providerObservedRawNs": restored["observedRawNs"], "restoredAtRawNs": restored["acceptedAtRawNs"]}


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
    if prepared["scope"] in NATIVE_PREPARATION_SCOPES:
        require(os.environ.get("P2PKIT_NATIVE_PROVIDER_OUTCOME") == "success",
                "NATIVE_PROVIDER_COMPLETE_ACTION_REQUIRED")
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


def adopt_initial_preparation(controller):
    require(type(controller) is InitialController and controller.initial_adopted is not None and
            os.environ.get("P2PKIT_HOSTED_PREPARE_OUTCOME") == "success" and
            os.environ.get("P2PKIT_CACHE_GUARD_OUTCOME") == "success" and
            os.environ.get("P2PKIT_NATIVE_PROVIDER_OUTCOME") == "success", "INITIAL_NATIVE_ACTION_REQUIRED")
    controller.current_session.check()
    budget, history_sha, disposition = controller.initial_adopted
    controller.budget, controller.clock = budget, budget.clock
    controller.history_sha, controller.current_budget = history_sha, disposition
    timing = original_clock(budget)
    controller.deadline = min(controller.deadline, timing.deadline("controller-return", TOTAL_SECONDS[controller.profile]))
    controller.last_raw = timing.last
    end = controller.window("productive", 90)
    controller.private = controller.open(controller.path)
    for name in ("evidence", "runtime", "crypto"):
        setattr(controller, name, controller.child(controller.private, name, end))
    controller.commands = controller.child(controller.evidence, "commands", end)
    controller.admitted = controller.current_session.identity
    require(initial.load_identity(controller, controller.child(controller.evidence, "admission", end), end).record ==
            controller.admitted.record, "INITIAL_ADOPTION_IDENTITY_CHANGED")
    reproduced, _history, original_hash, original_disposition = initial_budget_originals(
        controller, controller.private, controller.admitted, end)
    require(reproduced.record == budget.record and original_hash == history_sha and original_disposition == disposition,
            "INITIAL_ADOPTION_BUDGET_CHANGED")
    prepared_raw = read_preparation(controller, controller.private, controller.admitted, budget, end)
    prepared = parse(prepared_raw)
    require(prepared["scope"] == NATIVE_PREPARATION_SCOPES[1] and
            digest(prepared_raw) == os.environ.get("P2PKIT_HOSTED_PREPARE_SHA256") and
            prepared["pid"] != os.getpid() and prepared["job"] != controller.job,
            "INITIAL_PREPARATION_REPLAYED_OR_CHANGED")
    binding = consume_binding(controller, controller.private, controller.admitted, budget, end)
    require(binding["restorationSha256"] == os.environ.get("P2PKIT_CACHE_RESTORATION_SHA256"),
            "INITIAL_ORIGINAL_RESTORE_OUTPUT_CHANGED")
    controller.preparation_raw, controller.cache_binding = prepared_raw, binding
    controller.last_raw = max(controller.last_raw, binding["restoredAtRawNs"])
    # No fake job-time row: the actual first-source originals remain mandatory.
    require(not controller.records and not controller.phase_hashes, "INITIAL_JOB_TIME_PHASE_NOT_EXECUTED")
    controller.current_session.check()
    controller.check_window("productive", end)


def ordinary_prepare_restore(profile, *, cancelled=None):
    return native_prepare_restore(profile, Controller, cancelled=cancelled)


def initial_prepare_restore(profile, *, cancelled=None):
    return native_prepare_restore(profile, InitialController, cancelled=cancelled)


def native_prepare_restore(profile, controller_type, *, cancelled):
    """One fixed real source/provider/resource owner, not adjacent stock steps.

    The two public entrypoints choose an exact controller class. No caller enum,
    request path, supplier, arbitrary command or restored-result substitution is
    accepted. Actual Action close/success remains a downstream prerequisite.
    """
    import hosted_cache_provider_prepare as native_prepare
    import hosted_cache_provider_readback as native_readback
    require(controller_type in (Controller, InitialController), "NATIVE_PROVIDER_FIXED_CONTROLLER")
    initial_kind = controller_type is InitialController
    index = 1 if initial_kind else 0
    service_environment, controller, failure, outputs = None, None, None, None
    preparation_owner = readback_owner = None
    end = None
    try:
        # Only this fixed service-owning entry receives these runner fields.
        # The current-source owner consumes its API token itself, before any
        # source/Git/tool/crypto child and before InitialController's base ctor.
        service_environment = initial.take_service_environment()
        controller = (InitialController(profile, preflight=True, cancelled=cancelled) if initial_kind else
                      Controller(profile, preflight=True))
        controller.cancelled = [] if cancelled is None else cancelled
        controller.check()
        if initial_kind:
            controller.prepare_first_identity()
        else:
            controller.allocate()
            controller.admitted = admission(controller, profile, controller.evidence.path / "admission", controller.check)
            controller.acquire_job_time()
        end = controller.window("productive", 120)
        check = lambda: (controller.check(), controller.check_window("productive", end))
        path = seed.stage_path(controller.path, profile, controller.role, admitted_raw=controller.admitted.record)
        stage = controller.acquire("native-cache-stage", lambda: seed.private_root(path, create=True))
        source = controller.acquire("native-cache-restore-home", lambda: stage.create_directory("restore-home", deadline=end))
        inputs, compiled = seed.source_inputs(controller, ROOT, end, check)
        controller.recheck_identity(controller.runtime.path / "native-cache-before", check, end, purpose="provider")
        before_current = (initial.current_module().initial_ordinary_record(controller.current_session.current)
                          if initial_kind else None)
        qualifications = initial.current_qualifications(controller.current_session) if initial_kind else None
        staging_raw = seed.encoded(seed.stage_record(controller.admitted.record, profile, controller.role, path,
                                                     stage.verify(), source.verify(), inputs))
        controller.write(stage, "staging.json", staging_raw, end)
        directory = controller.child(controller.evidence, "dependency-cache", end, create=True)
        plan = cache.make_plan(controller.admitted.record, staging_raw, compiled, inputs, session=controller.path,
                               profile=seed.byte_cohort(controller.admitted.record, profile, controller.role)[0],
                               role=controller.role, mode="consume")
        plan_raw = encoded(plan)
        controller.write(directory, "plan.json", plan_raw, end)
        controller.write(directory, "staging.json", staging_raw, end)
        # Installed paths only. B proves actual executable/version/native tool
        # semantics in its credential-free worker preflight inside original180.
        tool_path = controller.environment.get("PATH")
        require(type(tool_path) is str and tool_path, "NATIVE_PROVIDER_INSTALLED_PATH_REQUIRED")
        node_path = shutil.which("node.exe" if os.name == "nt" else "node", path=tool_path)
        require(node_path is not None, "NATIVE_PROVIDER_INSTALLED_NODE_REQUIRED")
        node = str(Path(node_path).resolve(strict=True))
        require(Path(node).name == ("node.exe" if os.name == "nt" else "node"), "NATIVE_PROVIDER_NODE_NAME")
        origin = native_budget_origin(controller, controller.private, controller.admitted, controller.budget, end)
        issued = controller.now_raw()
        hard_end = min(controller.budget.fence("productive"), issued + 180 * job_time.NS)
        minutes = (hard_end - issued) // (60 * job_time.NS)
        require(1 <= minutes <= 3 and hard_end > issued + 75 * job_time.NS, "NATIVE_PROVIDER_NO_ORIGINAL_WINDOW")
        record = parse(controller.admitted.record)
        preparation_error = None
        try:
            preparation_owner = ProviderEpisode(_PROVIDER_KEY, controller, issued, hard_end, "prepare")
            root = preparation_owner.child(controller.runtime, "cache-provider", preparation_owner.end(), create=True)
            descriptor_raw = encoded({"schema": 1, "scope": "P2PKIT_" + ("INITIAL_ORDINARY_" if initial_kind else "ORDINARY_") +
                "RESTORE_NATIVE_DESCRIPTOR_V1", "phase": "restore", "source": record["source"], "github": record["github"],
                "planSha256": digest(plan_raw), "directory": str(root.path), "directoryIdentity": list(root.identity),
                "clock": job_time.clock_value(preparation_owner.first.clock), "providerWindow": {
                    "issuedNs": issued, "hardEndNs": hard_end, "actualProviderStart": "NOT_OBSERVED"},
                "providerRequest": cache.restore_provider_contract(plan)["request"], "providerExecution": "NOT_PERFORMED",
                "enclosingOwnerClose": "NOT_OBSERVED", "providerAcceptance": "NOT_ESTABLISHED"})
            require(len(descriptor_raw) <= 16384, "NATIVE_PROVIDER_DESCRIPTOR_LIMIT")
            prepared_raw = encoded({"schema": 1, "scope": NATIVE_PREPARATION_SCOPES[index], "profile": profile,
                "role": controller.role, "session": str(controller.path), "sessionIdentity": list(controller.private.identity),
                "directories": {name: list(preparation_owner.child(controller.private, name, preparation_owner.end()).identity)
                                for name in PREPARATION_DIRECTORIES},
                "source": record["source"], "github": record["github"], "admissionSha256": digest(controller.admitted.record),
                "job": controller.job, "jobBudgetSha256": controller.budget.sha256, "budgetOrigin": origin,
                "planSha256": digest(plan_raw), "stagingSha256": digest(staging_raw),
                "restoreWindow": {"beganRawNs": issued, "endRawNs": hard_end, "timeoutMinutes": minutes},
                "completedRawNs": issued, "pid": os.getpid(), "nativeProvider": descriptor_raw.decode("ascii"),
                "enclosingOwnerClose": "NOT_OBSERVED", "providerAcceptance": "NOT_ESTABLISHED"})
            require(len(prepared_raw) <= 2 * MIB, "NATIVE_PREPARATION_LIMIT")
            preparation_owner.write(directory, "preparation.json", prepared_raw, preparation_owner.end())
            require(read_native_preparation(preparation_owner, controller.private, controller.admitted,
                controller.budget, prepared_raw, preparation_owner.end()) == prepared_raw, "NATIVE_PREPARATION_CHANGED")
            bundle_raw = initial.acquire_provider_bundle(preparation_owner, plan)
            materialize = (native_prepare.materialize_initial_ordinary_restore if initial_kind else
                           native_prepare.materialize_ordinary_restore)
            prepared = materialize(preparation_owner, root, prepared_raw, digest(prepared_raw), plan=plan,
                bundle_raw=bundle_raw, node=node, tool_path=tool_path, worker_cutoff_ns=hard_end - 30 * job_time.NS)
            preparation_owner.end()
        except BaseException as error:
            preparation_error = error
            if preparation_owner is not None:
                preparation_owner.error("native-prepare", error)
            raise
        finally:
            if preparation_owner is not None:
                try:
                    preparation_owner.close()
                except BaseException as error:
                    if preparation_error is None:
                        raise
                    seed._note(preparation_error, "native-preparation-close", error)
        preparation_close = preparation_owner.original_close()
        frame_raw = initial.service_frame(prepared, str(Path(sys.executable).resolve(strict=True)),
                                           initial_ordinary=initial_kind)
        native_return, service_raw, service_close = provider_service(controller, prepared, frame_raw, node,
            tool_path, service_environment, issued=issued, hard_end=hard_end)
        service, ack = initial.service_return(service_raw, frame_raw, prepared.request, initial_ordinary=initial_kind)
        readback_error = None
        try:
            readback_owner = ProviderEpisode(_PROVIDER_KEY, controller, issued, hard_end, "readback")
            require(service_close["closedNs"] <= readback_owner.first.nanoseconds and
                    ack.observed_ns <= readback_owner.first.nanoseconds, "NATIVE_NEW_READBACK_REQUIRED")
            provider_directory = readback_owner.open(controller.runtime.path / "cache-provider/provider")
            returned = native_readback.read_success(readback_owner, provider_directory, prepared.request,
                service["acknowledgement"].encode("ascii"), 0, python=str(Path(sys.executable).resolve(strict=True)),
                bindings=dict(prepared.bindings))
            copied = readback_owner.child(directory, "provider-originals", readback_owner.end(), create=True)
            copies = copy_provider_originals(readback_owner, provider_directory, copied, returned)
            readback_owner.end()
        except BaseException as error:
            readback_error = error
            if readback_owner is not None:
                readback_owner.error("native-readback", error)
            raise
        finally:
            if readback_owner is not None:
                try:
                    readback_owner.close()
                except BaseException as error:
                    if readback_error is None:
                        raise
                    seed._note(readback_error, "native-readback-close", error)
        readback_close = readback_owner.original_close()
        # Original provider180 is now historical and CLOSED. Fresh mutable
        # source qualification is charged to the original productive/job fence,
        # never relabelled as an earlier provider observation.
        end = controller.window("productive", 120)
        controller.recheck_identity(controller.runtime.path / "native-cache-after", check, end, purpose="provider")
        current_after = (initial.current_module().initial_ordinary_record(controller.current_session.current)
                         if initial_kind else None)
        joined = initial.provider_current_binding(controller.current_session, plan, returned.provider,
                                                   qualifications) if initial_kind else None
        classification = cache.provider_observation(plan, "restore", original_outcome="success",
                                                     outputs=dict(returned.provider.outputs))
        require(classification["status"] == "REPORTED_EXACT_HIT", "NATIVE_PROVIDER_NO_EXACT_HIT")
        seed.validate_stage(parse(staging_raw), controller.admitted.record, profile, controller.role, path,
                            stage.verify(), source.verify(), inputs)
        require(controller.read(stage, "staging.json", end) == staging_raw, "NATIVE_STAGE_CHANGED_AFTER_RESTORE")
        provider_raw = encoded({"schema": 1, "scope": NATIVE_PROVIDER_SCOPES[index],
            "preparationSha256": digest(prepared_raw), "planSha256": digest(plan_raw),
            "jobBudgetSha256": controller.budget.sha256, "source": record["source"], "github": record["github"],
            "request": prepared.request.decode("ascii"), "frame": frame_raw.decode("ascii"),
            "serviceReturn": service_raw.decode("ascii"), "python": str(Path(sys.executable).resolve(strict=True)),
            "bindings": dict(prepared.bindings), "clockBindings": dict(prepared.clock_bindings),
            "nativeReturn": native_return, "preparationClose": preparation_close, "serviceClose": service_close,
            "readbackClose": readback_close, "originals": copies, "classification": classification,
            "observedRawNs": returned.provider.observed_ns, "readbackRawNs": returned.checked_ns,
            "toolsSha256": digest(returned.provider.tools), "currentBefore":
                None if before_current is None else before_current.decode("ascii")})
        controller.write(directory, "provider.json", provider_raw, end)
        restored_raw = encoded({"schema": 1, "scope": NATIVE_RESTORE_SCOPES[index],
            "preparationSha256": digest(prepared_raw), "planSha256": digest(plan_raw), "stagingSha256": digest(staging_raw),
            "providerSha256": digest(provider_raw), "jobBudgetSha256": controller.budget.sha256,
            "source": record["source"], "github": record["github"], "observedRawNs": readback_close["closedNs"],
            "acceptedAtRawNs": controller.now_raw(), "currentAfter":
                None if current_after is None else current_after.decode("ascii"), "currentJoin": joined,
            "retirement": "KNOWN", "enclosingControllerReturn": "NOT_OBSERVED"})
        controller.write(directory, "restoration.json", restored_raw, end)
        native_consume_binding(controller, controller.private, controller.admitted, controller.budget, prepared_raw, end,
                               staging_raw=staging_raw, inputs=inputs, compiled=compiled)
        check()
        outputs = ("dependency_seed_ready=true\ndependency_cache_ready=true\nnative_provider_ready=true\n" +
            "dependency_seed_home=" + plan["restoreHome"] + "\ndependency_seed_staging_sha256=" + digest(staging_raw) +
            "\npreparation_sha256=" + digest(prepared_raw) + "\nrestoration_sha256=" + digest(restored_raw) +
            "\ncache_key=" + plan["key"] + "\ncache_path=" + plan["path"] + "\n" +
            ("initial_current_history_sha256=" + controller.history_sha + "\n" if initial_kind else ""))
    except BaseException as error:
        failure = error
        if controller is not None:
            controller.error("native-prepare-restore", error,
                unknown=any(item is not None and item.unknown for item in (preparation_owner, readback_owner)))
            if initial_kind:
                controller.current_session.fail(error)
    finally:
        if service_environment is not None:
            service_environment.clear()
        if controller is not None:
            controller.actions_token = None
            try:
                controller.close()
            except BaseException as error:
                failure = failure or error
    if failure is not None:
        raise failure
    require(controller is not None and outputs is not None and not controller.unknown and not controller.errors,
            "NATIVE_PROVIDER_CONTROLLER_NOT_RETURNED")
    def final_check():
        check_cancelled(cancelled)
        controller.check_window("productive", end)
        controller.check()
        if initial_kind:
            controller.current_session.check()
    # This fixed launcher child never receives GITHUB_OUTPUT. Emit only bounded
    # safe DATA to its private pipe; the Action must observe actual EOF/exit and
    # close BEFORE forwarding any allowlisted output. A late child failure can
    # therefore never leak provisional output authority into the next step.
    require("GITHUB_OUTPUT" not in os.environ, "NATIVE_PROVIDER_ACTION_OWNS_OUTPUTS")
    final_check()
    result = {"schema": 1, "scope": ("INITIAL_ORDINARY_" if initial_kind else "ORDINARY_") +
        "CACHE_PROVIDER_CONTROLLER_PENDING_ACTION_CLOSE_V1", "profile": profile, "role": controller.role,
        "controllerPid": os.getpid(), "source": record["source"],
        "github": {name: record["github"][name] for name in ("repository", "event", "ref", "workflow", "workflowSha",
                                                          "job", "runId", "runAttempt")},
        "outputs": dict(line.split("=", 1) for line in outputs.splitlines()), "retirement": "KNOWN", "errors": [],
        "enclosingActionReturn": "NOT_OBSERVED", "resolverAcceptance": "NOT_PERFORMED"}
    raw = encoded(result)
    require(len(raw) <= 16384, "NATIVE_PROVIDER_ACTION_RETURN_LIMIT")
    sys.stdout.write(raw.decode("ascii"))
    sys.stdout.flush()
    final_check()


def prepare_consume(profile, *, cancelled=None):
    """Native, source-bound pre-tool acquisition. No Gradle, restore or cache save."""
    require(profile != jvm.PROFILE, "JVM_REQUIRES_NATIVE_PROVIDER_ENTRY")
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
    require(profile != jvm.PROFILE, "JVM_REQUIRES_NATIVE_PROVIDER_ENTRY")
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
    if type(admitted) in (initial.identity.InitialOrdinaryIdentity, initial.identity.InitialJvmLibraryIdentity):
        return initial_budget_originals(owner, private, admitted, end)[0]
    require(type(admitted) is identity.Admission, "ORDINARY_BUDGET_ADMISSION_ONLY")
    evidence = owner.child(private, "evidence", end)
    originals = owner.child(evidence, "job-time", end)
    commands = owner.child(evidence, "commands", end)
    phase = owner.child(commands, "job-time", end)
    runtime = owner.child(private, "runtime", end)
    start_raw, phase_raw = owner.read(phase, "start.json", end), owner.read(phase, "result.json", end)
    returned_raw = owner.read(runtime, "job-time-result.json", end)
    start, row, returned = parse(start_raw), parse(phase_raw), parse(returned_raw)
    profile = parse(admitted.record)["profile"]
    clock = job_time.clock_identity(row.get("clock")) if profile in ("desktop", jvm.PROFILE) else None
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
    if type(admitted) in (initial.identity.InitialOrdinaryIdentity, initial.identity.InitialJvmLibraryIdentity):
        binding = initial.initial_context(context)
        budget, _history, history_sha, disposition = initial_budget_originals(owner, private, admitted, end)
        require(budget.sha256 == context["jobBudgetSha256"] == binding["sourceBudgetSha256"] and
                digest(admitted.record) == binding["identitySha256"] and
                history_sha == binding["historySha256"] and budget.profile == context["profile"],
                "INITIAL_IMMUTABLE_SOURCE_BUDGET_CHANGED")
        prepared_raw = read_preparation(owner, private, admitted, budget, end)
        require(digest(prepared_raw) == context.get("jobTimeAcquisitionSha256") and
                context.get("dependencyCache", {}).get("preparationSha256") == digest(prepared_raw) and
                parse(prepared_raw)["job"] == budget.value["provenance"]["controllerJob"] != context["job"] and
                disposition == initial.current_budget_disposition(budget, history_sha),
                "INITIAL_ORIGINAL_BUDGET_ADOPTION_CHANGED")
        return budget
    require(context.get("scope") == "CLOSED_ORDINARY_TEST_CONTROLLER" and "initialOrdinary" not in context,
            "ORDINARY_BUDGET_CONTEXT_ONLY")
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
        if profile in ("desktop", jvm.PROFILE):
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
    return _crypto_phase(operation, profile, context_hash, initial_kind=False)


def initial_crypto_phase(operation, profile, context_hash):
    return _crypto_phase(operation, profile, context_hash, initial_kind=True)


def _crypto_phase(operation, profile, context_hash, *, initial_kind):
    """Closed child; its real outer native owner must outlive ALL GPG descendants."""
    owner = PrivateOwner()
    error, terminal, runtime, exported, budget, budget_clock = None, False, None, None, None, None
    initial_request = None
    end = time.monotonic() + 210
    def check_crypto():
        posix._deadline(end)
        if budget_clock is not None:
            budget_clock.check("productive" if operation == "validate" else "export")
    try:
        require(operation in ("validate", "export"), "CRYPTO_OPERATION")
        require(job_time.TOKEN_ENV not in os.environ, "JOB_TIME_TOKEN_IN_CRYPTO")
        if initial_kind:
            initial.forbid_service_environment()
        inherited = query._inherited_context()
        require(set(inherited) == set(query._CONTEXT), "CRYPTO_REQUIRES_EXISTING_NATIVE_OWNER")
        role = processes.host_role()
        path = session_path(profile, role)
        private = owner.open(path)
        raw = owner.read(private, "run-context.json", end)
        context = parse(raw)
        require(context.get("scope") == (initial.INITIAL_CONTEXT_SCOPE if initial_kind else
                "CLOSED_ORDINARY_TEST_CONTROLLER") and ("initialOrdinary" in context) is initial_kind,
                "CRYPTO_FIXED_ORIGIN")
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
        admitted = context_identity(owner, original, context, end)
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
        if initial_kind:
            require(budget is not None and budget.value["schema"] == 3, "INITIAL_CRYPTO_ORIGINAL_BUDGET_REQUIRED")
            initial_request = initial.crypto_request(owner.read(phase, "initial-request.json", end), admitted,
                raw, budget, started, inherited, operation)
            window = parse(initial_request.raw)["window"]
            end = min(end, original_deadline(budget_clock, "productive" if operation == "validate" else "export",
                                            window["workEndNs"], 210))
        work = owner.child(private, "crypto", end)
        checked = (initial.check_local(owner, admitted, runtime.path / (operation + "-admission"), check_crypto, end=end)
                   if initial_kind else admission(owner, profile, runtime.path / (operation + "-admission"),
                                                  check_crypto, expected=admitted))
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
            jvm_frozen = jvm.frozen_binding(owner, globals(), private, end, check_crypto) if profile == jvm.PROFILE else None
            supplier, original_error = None, None
            try:
                supplier = query.NativeGitQueries(ROOT, runtime.path / "export-manifest-admission",
                    check_cancel=check_crypto, **({"owner_deadlines": (end, end)} if initial_kind else {}))
                supplier.native_host_matches_actions()
                if initial_kind:
                    timeout = min(180, math.floor(end - time.monotonic()))
                    require(timeout > 0, "INITIAL_CRYPTO_NO_ORIGINAL_EXPORT_TIME")
                    if os.name == "nt":
                        output = owner.new(path / "export")
                        manifest = windows.export_initial_ordinary_encrypted(frozen, output, recipient, root=ROOT,
                            request=initial_request, query_runner=supplier, check=check_crypto, timeout_seconds=timeout)
                    else:
                        manifest = ordinary.export_initial_ordinary_encrypted(frozen.path, path / "export", recipient,
                            root=ROOT, request=initial_request, query_runner=supplier, check=check_crypto,
                            timeout_seconds=timeout)
                        output = owner.child(private, "export", end)
                elif os.name == "nt":
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
                if jvm_frozen is not None:
                    require(jvm.frozen_binding(owner, globals(), private, end, check_crypto) == jvm_frozen,
                            "JVM_CHANGED_DURING_ORIGINAL_EXPORT")
                    exported["jvmLibraryFrozen"] = jvm_frozen
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
                    **({"initialOrdinary": {"requestSha256": digest(initial_request.raw),
                        "currentBeforeSha256": parse(initial_request.raw)["currentSha256"],
                        "identitySha256": digest(initial_request.bound.record),
                        "historySha256": parse(initial_request.raw)["historySha256"]}}
                       if initial_request is not None else {}),
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
    return _run(profile, seed_dependencies=seed_dependencies, consume_dependencies=consume_dependencies,
                initial_kind=False)


def initial_run(profile):
    return _run(profile, seed_dependencies=False, consume_dependencies=True, initial_kind=True)


def _run(profile, *, seed_dependencies, consume_dependencies, initial_kind):
    controller, result, terminal = None, None, False
    handlers, cancelled = {}, []
    original = None
    try:
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handlers[number] = signal.getsignal(number)
            signal.signal(number, lambda value, _frame: cancelled.append(value))
        controller = (InitialController(profile, cancelled=cancelled) if initial_kind else
                      Controller(profile, consume_dependencies=True) if consume_dependencies else
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
    print(("INITIAL_ORDINARY_TEST_CUSTODY=" if initial_kind else "ORDINARY_TEST_CUSTODY=") +
          ("RETURNED_FOR_SEAL" if ready else "HOLD"))
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
    is_jvm = result["profile"] == jvm.PROFILE
    is_initial = context.get("scope") == initial.INITIAL_CONTEXT_SCOPE
    if is_initial:
        binding = initial.initial_context(context)
        require(budget is not None and budget.value["schema"] == 3 and
                result.get("scope") == initial.INITIAL_RESULT_SCOPE and
                result.get("initialOrdinary") == {"identitySha256": binding["identitySha256"],
                    "historySha256": binding["historySha256"], "samplePackagingRequired": False} and
                result.get("currentBudget") == initial.current_budget_disposition(budget, binding["historySha256"]),
                "INITIAL_PHASE_ORIGINAL_CONTEXT")
    else:
        require(context.get("scope") == "CLOSED_ORDINARY_TEST_CONTROLLER" and "initialOrdinary" not in context and
                result.get("scope") == "ORDINARY_PROFILE_CUSTODY_ONLY" and "initialOrdinary" not in result and
                "currentBudget" not in result and (budget is None or budget.value["schema"] in (1, 2)),
                "ORDINARY_PHASE_ORIGINAL_CONTEXT")
    order = FULL_ORDER if full else JVM_ORDER if is_jvm else DESKTOP_ORDER
    preparatory = FULL_PREPARATION if full else JVM_ORDER[:4] if is_jvm else DESKTOP_ORDER[:5]
    if is_jvm:
        require(budget is not None and budget.profile == jvm.PROFILE and result["role"] in jvm.BACKENDS and
                "samplePackagingRequired" not in context and "samplePackaging" not in result and
                result.get("cancelled") is False and type(result.get("dependencyCache")) is dict,
                "JVM_REQUIRED_ORIGINAL_CONTEXT")
    if is_initial:
        order = tuple(label for label in order if label not in ("job-time", "sample-packaging"))
        preparatory = tuple(label for label in preparatory if label != "job-time")
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
            if budget.clock is not None:
                require(start.get("clock") == row.get("clock") == job_time.clock_value(budget.clock),
                        "PHASE_CLOCK_CHANGED")
            if not full:
                require(row.get("simulatorBindingSha256") is None and row.get("supplementPhase") is False and
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
            if label in {*[name for name in preparatory if name != "job-time"],
                         *(supplements.PRODUCTIVE if full else ())}:
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
        if is_initial and label in ("recipient-validation", "export"):
            initial_crypto_binding(owner, private, result, context, budget, end,
                                   "validate" if label == "recipient-validation" else "export")
    if is_jvm:
        original, _, request_raw, _ = jvm.verify(owner, globals(), private, encoded(context), result, end,
                                                lambda: posix._deadline(end))
        reservation = parse(request_raw)["operation"]
        require(budget.value["responseFinishedRawNs"] <= reservation["startedRawNs"] <=
                reservation["finishedRawNs"] < budget.fence("productive"), "JVM_RESERVATION_ORIGINAL_WINDOW")
        require(reservation["finishedRawNs"] <= original["operation"]["startedRawNs"] <=
                original["operation"]["finishedRawNs"] < budget.fence("collect"), "JVM_COLLECTION_ORIGINAL_WINDOW")
    elif result["custody"] is not None:
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


def initial_crypto_binding(owner, private, result, context, budget, end, operation):
    """Original child/phase/request and actual parent's later acceptance DATA.

    This verifier never hydrates a current or fabricates an inherited native
    context. Separate seal/upload callers still need their own genuine current.
    """
    binding = initial.initial_context(context)
    label = "recipient-validation" if operation == "validate" else "export"
    require(operation in ("validate", "export") and result.get("scope") == initial.INITIAL_RESULT_SCOPE,
            "INITIAL_CRYPTO_RETAINED_ORIGIN")
    rows = [row for row in result["phases"] if row["phase"] == label]
    require(len(rows) == 1, "INITIAL_CRYPTO_ORIGINAL_PHASE_REQUIRED")
    row = rows[0]
    context_raw = owner.read(private, "run-context.json", end)
    require(parse(context_raw) == context and digest(context_raw) == result["contextSha256"] and
            row["argv"] == [context["python"], "-I", "-B", "-S", str(Path(__file__)), "_initial-crypto", operation,
                "--profile", context["profile"], "--context-sha256", digest(context_raw)] and
            type(row["exitCode"]) is int and row["exitCode"] == 0 and row["retirement"] == "KNOWN" and
            row["errors"] == [] and row["launchAttempted"] is row["scopeAttempted"] is True,
            "INITIAL_CRYPTO_FIXED_RETURN")
    evidence = owner.child(private, "evidence", end)
    admitted = initial.load_identity(owner, owner.child(evidence, "admission", end), end)
    directory = owner.child(owner.child(evidence, "commands", end), label, end)
    start_raw, phase_raw = (owner.read(directory, name, end) for name in ("start.json", "result.json"))
    require(parse(phase_raw) == row and digest(phase_raw) == result["phaseSha256"][label],
            "INITIAL_CRYPTO_PHASE_BYTES_CHANGED")
    request = initial.crypto_request_data(owner.read(directory, "initial-request.json", end), admitted,
                                          context_raw, budget, parse(start_raw), operation)
    request_value = parse(request.raw)
    child_raw = owner.read(owner.child(private, "runtime", end), operation + "-result.json", end)
    child = parse(child_raw)
    expected = {"requestSha256": digest(request.raw), "currentBeforeSha256": request_value["currentSha256"],
                "identitySha256": binding["identitySha256"], "historySha256": binding["historySha256"]}
    require(child_raw == encoded(child) and child.get("schema") == 1 and child.get("operation") == operation and
            child.get("profile") == context["profile"] and child.get("contextSha256") == digest(context_raw) and
            child.get("jobBudgetSha256") == budget.sha256 and child.get("returned") is True and
            child.get("retirement") == "KNOWN" and child.get("errors") == [] and child.get("initialOrdinary") == expected,
            "INITIAL_CRYPTO_RETAINED_CHILD_CHANGED")
    accepted_raw = owner.read(directory, "source-current-acceptance.json", end)
    accepted = parse(accepted_raw)
    fixed = {"schema": 1, "scope": "INITIAL_ORDINARY_ACTUAL_CRYPTO_RETURN_ACCEPTANCE_V1", "operation": operation,
        **expected, "phaseResultSha256": digest(phase_raw), "childReturnSha256": digest(child_raw),
        "jobBudgetSha256": budget.sha256, "lateSourceOriginals": "OPERATIONAL_NOT_IN_FROZEN_PAYLOAD", "retirement": "KNOWN"}
    require(set(accepted) == set(fixed) | {"currentAfterSha256", "acceptedAtRawNs"} and accepted_raw == encoded(accepted) and
            all(accepted[name] == value for name, value in fixed.items()) and
            type(accepted["currentAfterSha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", accepted["currentAfterSha256"]) and
            accepted["currentAfterSha256"] != expected["currentBeforeSha256"] and
            type(accepted["acceptedAtRawNs"]) is int and row["finalizedRawNs"] <= accepted["acceptedAtRawNs"] <
            budget.fence("productive" if operation == "validate" else "export-read") and
            accepted["acceptedAtRawNs"] <= result["jobBudget"]["terminalRawNs"], "INITIAL_CRYPTO_PARENT_ACCEPTANCE_CHANGED")
    if operation == "export":
        require(result["exportReturn"] == {"result": child, "sha256": digest(child_raw),
                "initialCurrentAcceptance": {"sha256": digest(accepted_raw), "record": accepted}} and
                child["manifest"] == {**initial.manifest_data(request), "artifact": child["manifest"]["artifact"]},
                "INITIAL_CRYPTO_EXPORT_ACCEPTANCE_CHANGED")
    else:
        # Validation/request/current acceptance precedes product and its secret
        # screen. Verify their actual copies, unlike the later export receipt.
        frozen = owner.child(private, "frozen-evidence", end)
        mapping = seed_copy_map(owner.read(frozen, "original-path-map.json", end), evidence.path)
        copies = {item["original"]: item for item in mapping["files"]}
        for name, raw in (("initial-request.json", request.raw), ("source-current-acceptance.json", accepted_raw)):
            item = copies.get("commands/" + label + "/" + name)
            require(type(item) is dict and (item["size"], item["sha256"]) == (len(raw), digest(raw)) and
                    owner.read(frozen, item["member"], end) == raw, "INITIAL_CRYPTO_VALIDATION_NOT_FROZEN")
    return request


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
    require(budget.profile == result.get("profile") and budget.profile in ("desktop", jvm.PROFILE),
            "SHORT_JOB_DELIVERY_SCOPE")
    terminal = result.get("jobBudget", {}).get("terminalRawNs")
    require(type(terminal) is int and budget.value["responseFinishedRawNs"] <= terminal <
            budget.fence("controller-return"), "DESKTOP_ORIGINAL_TERMINAL_REQUIRED")
    return min(budget.fence("delivery"), terminal + job_time.DESKTOP_DELIVERY_SECONDS * job_time.NS)


def original_deadline(clock, stage, fence, seconds):
    local = time.monotonic()
    now = clock.check(stage)
    require(now < fence, "ORIGINAL_DELIVERY_WINDOW_EXPIRED")
    return job_time._directed_deadline(local, seconds, min(fence, clock.budget.fence(stage)), now)


def initial_operation_source(session, context):
    """Genuine current's operational reference, not delivered late originals."""
    require(type(session) is initial.CurrentSession, "INITIAL_OPERATION_CURRENT_REQUIRED")
    session.check()
    value = {"identitySha256": digest(session.identity.record),
        "historySha256": initial.initial_context(context)["historySha256"],
        "currentSha256": digest(initial.current_module().initial_ordinary_record(session.current)),
        "lateSourceOriginals": "OPERATIONAL_NOT_IN_FROZEN_PAYLOAD"}
    initial_operation_source_data(value, context)
    return value


def initial_operation_source_data(value, context):
    """Closed historical binding; does not perform or authorize source checks."""
    binding = initial.initial_context(context)
    require(type(value) is dict and set(value) == {"identitySha256", "historySha256", "currentSha256", "lateSourceOriginals"} and
            value["identitySha256"] == binding["identitySha256"] and value["historySha256"] == binding["historySha256"] and
            type(value["currentSha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["currentSha256"]) and
            value["lateSourceOriginals"] == "OPERATIONAL_NOT_IN_FROZEN_PAYLOAD", "INITIAL_OPERATION_SOURCE_DATA")
    return value


def initial_seal_data(value, context):
    keys = {"schema", "scope", "controllerResultSha256", "manifestSha256", "artifact", "profilePassed", "source",
        "retirement", "decryption", "jobBudgetSha256", "clockDomain", "sealedAtRawNs", "upload", "initialOrdinary"}
    if context["profile"] in ("desktop", jvm.PROFILE):
        keys.add("deliveryEndRawNs")
    require(type(value) is dict and set(value) == keys and type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == "INITIAL_ORDINARY_POST_RETURN_SEAL_V1" and value["decryption"] == "NOT_PERFORMED",
            "INITIAL_SEAL_DATA_ORIGIN")
    return initial_operation_source_data(value["initialOrdinary"], context)


def validate_public(profile, *, cancelled=None):
    return _validate_public(profile, initial_kind=False, cancelled=cancelled)


def initial_validate_public(profile, *, cancelled=None):
    return _validate_public(profile, initial_kind=True, cancelled=cancelled)


def _validate_public(profile, *, initial_kind, cancelled):
    """Separate interpreter only; provisional files cannot grant upload authority."""
    require(os.environ.get("P2PKIT_HOSTED_TEST_RUN_OUTCOME") == "success", "ORIGINAL_CONTROLLER_DID_NOT_SUCCEED")
    if initial_kind:
        initial.forbid_service_environment()
    else:
        require(job_time.TOKEN_ENV not in os.environ, "JOB_TIME_TOKEN_IN_SEAL")
    owner = PrivateOwner()
    end = time.monotonic() + 120
    error, budget, budget_clock, delivery_end = None, None, None, None
    current_session = None
    passed = False
    def check_seal():
        check_cancelled(cancelled)
        posix._deadline(end)
        if budget_clock is not None:
            observed = budget_clock.check("seal")
            require(delivery_end is None or observed < delivery_end, "DESKTOP_SEAL_DELIVERY_EXPIRED")
        if current_session is not None:
            current_session.check()
    try:
        role = processes.host_role()
        path = session_path(profile, role)
        private = owner.open(path)
        result_raw = owner.read(private, "controller-result.json", end)
        result = parse(result_raw)
        context_raw = owner.read(private, "run-context.json", end)
        context = parse(context_raw)
        require(result["schema"] == 1 and result["scope"] == (initial.INITIAL_RESULT_SCOPE if initial_kind else
                "ORDINARY_PROFILE_CUSTODY_ONLY") and
                result["profile"] == profile and result["role"] == role and result["controllerPid"] != os.getpid() and
                result["retirement"] == "KNOWN" and result["encrypted"] is True and
                result["readyForPostReturnSeal"] is True and result["contextSha256"] == digest(context_raw),
                "CONTROLLER_RESULT_NOT_SEALABLE")
        require(context["profile"] == profile and context["role"] == role and context["root"] == str(ROOT) and
                context["session"] == str(path) and context["canonicalSources"] == canonical_bindings() and
                context.get("scope") == (initial.INITIAL_CONTEXT_SCOPE if initial_kind else "CLOSED_ORDINARY_TEST_CONTROLLER"),
                "SEALED_CONTEXT_CHANGED")
        evidence = owner.child(private, "evidence", end)
        original = owner.child(evidence, "admission", end)
        expected = context_identity(owner, original, context, end)
        require(digest(expected.record) == context["admissionSha256"], "SEALED_ADMISSION_CHANGED")
        if "jobBudgetSha256" in context:
            budget = load_job_budget(owner, private, expected, context, end)
            budget_clock = original_clock(budget, result["jobBudget"]["terminalRawNs"])
            budget_clock.check("seal-start")
            end = min(end, budget_clock.deadline("seal", 120))
            if profile in ("desktop", jvm.PROFILE):
                delivery_end = desktop_delivery_end(budget, result)
                end = min(end, original_deadline(budget_clock, "seal", delivery_end, 120))
        # A replay cannot overwrite the previous post-return receipt.
        validation = owner.new(path / "post-return-validation")
        if initial_kind:
            require(budget is not None and budget.value["schema"] == 3, "INITIAL_SEAL_ORIGINAL_BUDGET_REQUIRED")
            current_session = reacquire_initial_source(owner, private, expected, budget,
                initial.initial_context(context)["historySha256"], end, cancelled=cancelled,
                preceding=os.environ["P2PKIT_HOSTED_TEST_RUN_OUTCOME"], stage="seal")
            current_session.claim("evidence")
            checked = current_session.identity
            check_seal()
        else:
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
        require((profile == jvm.PROFILE) == ("jvmLibraryFrozen" in returned), "JVM_FROZEN_BINDING_REQUIRED")
        sample_required = sample_intent(checked)
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
        if initial_kind:
            request = initial_crypto_binding(owner, private, result, context, budget, end, "export")
            expected_manifest = {**initial.manifest_data(request), "artifact": actual}
        else:
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
        jvm_frozen = None
        if profile == jvm.PROFILE:
            jvm_frozen = jvm.frozen_binding(owner, globals(), private, end, check_seal)
            require(jvm_frozen == returned["jvmLibraryFrozen"], "JVM_SEALED_EXPORT_RETURN_CHANGED")
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
            **({"deliveryEndRawNs": delivery_end} if delivery_end is not None else {}),
            **({"scope": "INITIAL_ORDINARY_POST_RETURN_SEAL_V1",
                "initialOrdinary": initial_operation_source(current_session, context)} if initial_kind else {})}, end)
        if initial_kind:
            initial_seal_data(parse(owner.read(validation, "seal.json", end)), context)
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
        if jvm_frozen is not None:
            require(jvm.frozen_binding(owner, globals(), private, end, check_seal) == jvm_frozen,
                    "JVM_POST_RETURN_INPUT_CHANGED")
    except BaseException as caught:
        error = caught
        owner.error("post-return-seal", caught)
        if current_session is not None:
            current_session.fail(caught)
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
    print(("INITIAL_ORDINARY_TEST_CIPHERTEXT_SEAL=" if initial_kind else "ORDINARY_TEST_CIPHERTEXT_SEAL=") +
          "PASS; PRIVATE_DECRYPTION=NOT_PERFORMED")


def full_upload_guard(phase, *, cancelled=None):
    return _full_upload_guard(phase, initial_kind=False, cancelled=cancelled)


def _full_upload_guard(phase, *, initial_kind, cancelled):
    """Closed before/after fence for FUTURE reviewed upload wiring, not upload.

    Wiring must require both guards' real successful outcomes, the exact before
    receipt hash, a <=3 minute pinned upload step and its successful outcome.
    This guard cannot schedule/guarantee GitHub step transitions or transfer.
    A late/failed upload never grants whole-gate acceptance from a prior seal.
    """
    require(phase in ("before", "after") and (initial_kind or job_time.TOKEN_ENV not in os.environ) and
            os.environ.get("P2PKIT_HOSTED_TEST_RUN_OUTCOME") == "success" and
            os.environ.get("P2PKIT_HOSTED_TEST_SEAL_OUTCOME") == "success", "UPLOAD_REQUIRES_REAL_SEAL_SUCCESS")
    if initial_kind:
        initial.forbid_service_environment()
    check_cancelled(cancelled)
    if phase == "after":
        require(os.environ.get("P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME") == "success", "UPLOAD_ORIGINAL_ACTION_FAILED")
    owner = PrivateOwner()
    error, clock, outputs, upload_end = None, None, None, None
    current_session = None
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
                result["readyForPostReturnSeal"] is True and context.get("scope") ==
                (initial.INITIAL_CONTEXT_SCOPE if initial_kind else "CLOSED_ORDINARY_TEST_CONTROLLER") and
                result.get("scope") == (initial.INITIAL_RESULT_SCOPE if initial_kind else "ORDINARY_PROFILE_CUSTODY_ONLY"),
                "UPLOAD_ORIGINAL_CONTEXT_CHANGED")
        evidence = owner.child(private, "evidence", end)
        original = owner.child(evidence, "admission", end)
        admitted = context_identity(owner, original, context, end)
        require(digest(admitted.record) == context["admissionSha256"], "UPLOAD_ORIGINAL_ADMISSION_CHANGED")
        budget = load_job_budget(owner, private, admitted, context, end)
        seal_directory = owner.child(private, "post-return-validation", end)
        seal_raw = owner.read(seal_directory, "seal.json", end)
        seal = parse(seal_raw)
        if initial_kind:
            initial_seal_data(seal, context)
        else:
            require("scope" not in seal and "initialOrdinary" not in seal, "ORDINARY_UPLOAD_SEAL_ONLY")
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
        if initial_kind:
            current_session = reacquire_initial_source(owner, private, admitted, budget,
                initial.initial_context(context)["historySha256"], end, cancelled=cancelled,
                preceding=os.environ["P2PKIT_HOSTED_TEST_SEAL_OUTCOME" if phase == "before" else
                                     "P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME"], stage=stage)
            current_session.claim("evidence")
            checked = current_session.identity
            source_binding = initial_operation_source(current_session, context)
            require(source_binding["currentSha256"] != seal["initialOrdinary"]["currentSha256"],
                    "INITIAL_UPLOAD_REQUIRES_FRESH_CURRENT")
        else:
            checked = admission(owner, "full", private.path / ("upload-" + phase + "-admission"),
                lambda: (check_cancelled(cancelled), posix._deadline(end), clock.check(stage)), expected=admitted)
        require(parse(checked.record)["source"] == seal["source"], "UPLOAD_SOURCE_CHANGED")
        output = owner.child(private, "export", end)
        manifest_raw = owner.read(output, posix.MANIFEST, end, 65536)
        require(digest(manifest_raw) == seal["manifestSha256"] and parse(manifest_raw)["artifact"] == seal["artifact"] and
                artifact_metadata(owner, output, end) == seal["artifact"],
                "UPLOAD_SEALED_MANIFEST_CHANGED")
        binding = {"schema": 1, "scope": ("CLOSED_INITIAL_ORDINARY_FULL_UPLOAD_SCHEDULING_CAP" if initial_kind else
                   "CLOSED_FULL_UPLOAD_SCHEDULING_CAP"), "contextSha256": digest(context_raw),
                   "controllerResultSha256": digest(result_raw), "sealSha256": digest(seal_raw),
                   "jobBudgetSha256": budget.sha256, "manifestSha256": digest(manifest_raw),
                   "source": seal["source"], "clockDomain": job_time.RAW_CLOCK_DOMAIN,
                   "maximumSeconds": job_time.UPLOAD_SECONDS, "timeoutMinutes": 3}
        if phase == "before":
            upload_end = min(budget.fence("upload"), began + job_time.UPLOAD_SECONDS * job_time.NS)
            raw = encoded({**binding, "beganRawNs": began, "endRawNs": upload_end,
                           **({"initialSource": source_binding} if initial_kind else {})})
            owner.write(private, "upload-before.json", raw, end)
            outputs = "upload_ready=true\nupload_timeout_minutes=3\nupload_guard_sha256=" + digest(raw) + "\n"
        else:
            raw = owner.read(private, "upload-before.json", end)
            before = parse(raw)
            require(os.environ.get("P2PKIT_HOSTED_TEST_UPLOAD_GUARD_SHA256") == digest(raw) and
                    set(before) == set(binding) | {"beganRawNs", "endRawNs"} |
                    ({"initialSource"} if initial_kind else set()) and
                    all(before.get(key) == value for key, value in binding.items()) and
                    type(before["beganRawNs"]) is int and type(before["endRawNs"]) is int and
                    seal["sealedAtRawNs"] <= before["beganRawNs"] < budget.fence("upload-start") and
                    before["endRawNs"] == min(budget.fence("upload"),
                                              before["beganRawNs"] + job_time.UPLOAD_SECONDS * job_time.NS) and
                    before["beganRawNs"] <= began < before["endRawNs"], "UPLOAD_ORIGINAL_FENCE_CHANGED_OR_EXPIRED")
            if initial_kind:
                previous_source = initial_operation_source_data(before["initialSource"], context)
                require(previous_source["currentSha256"] not in
                    (seal["initialOrdinary"]["currentSha256"], source_binding["currentSha256"]),
                    "INITIAL_UPLOAD_SOURCE_EPISODE_REUSED")
            upload_end = before["endRawNs"]
            observed = clock.check(stage) if initial_kind else began
            require(began <= observed < upload_end, "UPLOAD_ORIGINAL_FENCE_CHANGED_OR_EXPIRED")
            owner.write(private, "upload-after.json", {**binding, "beforeSha256": digest(raw), "observedRawNs": observed,
                "stepOutcome": "success", **({"initialSource": source_binding} if initial_kind else {})}, end)
            outputs = "upload_complete=true\n"
    except BaseException as caught:
        error = caught
        owner.error("upload-" + phase, caught)
        if current_session is not None:
            current_session.fail(caught)
    finally:
        try:
            owner.close()
        except BaseException as caught:
            error = error or caught
    if error is not None:
        raise error
    require(not owner.unknown and outputs is not None, "UPLOAD_GUARD_RETIREMENT_UNKNOWN")
    def check():
        check_cancelled(cancelled)
        posix._deadline(end)
        require(clock.check(stage) < upload_end, "UPLOAD_GUARD_EXPIRED")
        if current_session is not None:
            current_session.check()
    check()
    target = Path(os.environ["GITHUB_OUTPUT"])
    audit.reject_symlinks(target)
    with target.open("a", encoding="ascii") as stream:
        check()
        stream.write(outputs)
        stream.flush()
        os.fsync(stream.fileno())
    check()
    print(("INITIAL_ORDINARY_FULL_UPLOAD_GUARD=" if initial_kind else "ORDINARY_FULL_UPLOAD_GUARD=") +
          phase.upper() + "; NO_UPLOAD_PERFORMED")


def delivery_inputs(owner, end, *, initial_kind=False, profile="desktop"):
    """Read a separately sealed Desktop result; do not create new time authority."""
    require((initial_kind or job_time.TOKEN_ENV not in os.environ) and
            all(os.environ.get("P2PKIT_HOSTED_TEST_" + key + "_OUTCOME") == "success" for key in ("RUN", "SEAL")),
            "DELIVERY_REQUIRES_ORIGINAL_SUCCESS")
    if initial_kind:
        initial.forbid_service_environment()
    require(profile in ("desktop", jvm.PROFILE), "DELIVERY_CLOSED_PROFILE")
    role = processes.host_role()
    private = owner.open(session_path(profile, role))
    context_raw, result_raw = (owner.read(private, name, end) for name in ("run-context.json", "controller-result.json"))
    context, result = parse(context_raw), parse(result_raw)
    require(context.get("profile") == result.get("profile") == profile and context.get("role") == result.get("role") == role and
            context.get("root") == str(ROOT) and context.get("session") == str(private.path) and
            context.get("canonicalSources") == canonical_bindings() and
            type(context.get("dependencyCache")) is dict and result.get("contextSha256") == digest(context_raw) and
            result.get("retirement") == "KNOWN" and result.get("encrypted") is True and
            result.get("readyForPostReturnSeal") is True and context.get("scope") ==
            (initial.INITIAL_CONTEXT_SCOPE if initial_kind else "CLOSED_ORDINARY_TEST_CONTROLLER") and
            result.get("scope") == (initial.INITIAL_RESULT_SCOPE if initial_kind else "ORDINARY_PROFILE_CUSTODY_ONLY"),
            "DELIVERY_ORIGINAL_CONTEXT_CHANGED")
    evidence = owner.child(private, "evidence", end)
    admitted = context_identity(owner, owner.child(evidence, "admission", end), context, end)
    require(digest(admitted.record) == context["admissionSha256"] and
            parse(admitted.record)["source"] == context["source"] == result["source"], "DELIVERY_ORIGINAL_SOURCE_CHANGED")
    sample_required = sample_intent(admitted)
    require((context.get("samplePackagingRequired") is sample_required if profile == "desktop" else
             "samplePackagingRequired" not in context and sample_required is False) and
            sample_required == ("samplePackaging" in result) and
            (context.get("kind"), context.get("command")) ==
            profile_command(profile, role, package_samples=sample_required), "DELIVERY_SAMPLE_INTENT_CHANGED")
    budget = load_job_budget(owner, private, admitted, context, end)
    fence = desktop_delivery_end(budget, result)
    sealed = owner.child(private, "post-return-validation", end)
    seal_raw = owner.read(sealed, "seal.json", end)
    seal = parse(seal_raw)
    if initial_kind:
        initial_seal_data(seal, context)
    else:
        require("scope" not in seal and "initialOrdinary" not in seal, "ORDINARY_DELIVERY_SEAL_ONLY")
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
    if "currentSession" in data:
        data["currentSession"].check()
    return now


def desktop_upload_scope(data):
    profile = data["context"].get("profile")
    require(profile in ("desktop", jvm.PROFILE), "UPLOAD_CLOSED_WORKER")
    label = "JVM_LIBRARY" if profile == jvm.PROFILE else "DESKTOP"
    if data["context"].get("scope") == initial.INITIAL_CONTEXT_SCOPE:
        initial.initial_context(data["context"])
        return "CLOSED_INITIAL_ORDINARY_" + label + "_UPLOAD_SCHEDULING_CAP"
    require(data["context"].get("scope") == "CLOSED_ORDINARY_TEST_CONTROLLER", "UPLOAD_CONTEXT_ORIGIN")
    return "CLOSED_" + label + "_UPLOAD_SCHEDULING_CAP"


def desktop_upload_before(data, raw):
    value = parse(raw)
    binding = delivery_binding(data, desktop_upload_scope(data))
    expected_keys = set(binding) | {"beganRawNs", "endRawNs", "timeoutObservedRawNs", "timeoutMinutes"}
    if data["context"].get("scope") == initial.INITIAL_CONTEXT_SCOPE:
        expected_keys.add("initialSource")
        source = initial_operation_source_data(value.get("initialSource"), data["context"])
        require(source["currentSha256"] != data["seal"]["initialOrdinary"]["currentSha256"],
                "INITIAL_UPLOAD_ORIGINAL_SOURCE_REUSED")
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
    binding = delivery_binding(data, desktop_upload_scope(data))
    extra = {"initialSource"} if data["context"].get("scope") == initial.INITIAL_CONTEXT_SCOPE else set()
    require(set(after) == set(binding) | {"beforeSha256", "observedRawNs", "stepOutcome"} | extra and
            all(after.get(key) == value for key, value in binding.items()) and after.get("stepOutcome") == "success" and
            after.get("beforeSha256") == digest(before_raw) and type(after.get("observedRawNs")) is int and
            before["timeoutObservedRawNs"] <= after["observedRawNs"] < before["endRawNs"],
            "DELIVERY_ORIGINAL_UPLOAD_CHANGED")
    if extra:
        source = initial_operation_source_data(after["initialSource"], data["context"])
        require(source["currentSha256"] not in (before["initialSource"]["currentSha256"],
                data["seal"]["initialOrdinary"]["currentSha256"]), "INITIAL_UPLOAD_RETURN_SOURCE_REUSED")
    data["clock"].last = max(data["clock"].last, after["observedRawNs"])
    return before_raw, after_raw


def upload_guard(phase, profile="full", *, cancelled=None):
    if profile == "full":
        return full_upload_guard(phase, cancelled=cancelled)
    return _desktop_upload_guard(phase, profile, initial_kind=False, cancelled=cancelled)


def initial_upload_guard(phase, profile, *, cancelled=None):
    if profile == "full":
        return _full_upload_guard(phase, initial_kind=True, cancelled=cancelled)
    return _desktop_upload_guard(phase, profile, initial_kind=True, cancelled=cancelled)


def _desktop_upload_guard(phase, profile, *, initial_kind, cancelled):
    require(profile in ("desktop", jvm.PROFILE) and phase in ("before", "after"), "UPLOAD_CLOSED_PROFILE")
    if phase == "after":
        require(os.environ.get("P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME") == "success", "UPLOAD_ORIGINAL_ACTION_FAILED")
    owner, error, outputs, data, fence = PrivateOwner(), None, None, None, None
    end = time.monotonic() + job_time.TRANSITION_SECONDS
    def check():
        require(not owner.unknown, "UPLOAD_GUARD_RETIREMENT_UNKNOWN")
        return delivery_check(data, "upload", end, cancelled, fence=fence)
    try:
        check_cancelled(cancelled)
        data = delivery_inputs(owner, end, initial_kind=initial_kind, profile=profile)
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
        if initial_kind:
            session = reacquire_initial_source(owner, private, data["admitted"], data["budget"],
                initial.initial_context(data["context"])["historySha256"], end, cancelled=cancelled,
                preceding=os.environ["P2PKIT_HOSTED_TEST_SEAL_OUTCOME" if phase == "before" else
                                     "P2PKIT_HOSTED_TEST_UPLOAD_OUTCOME"], stage="upload")
            data["currentSession"] = session
            session.claim("evidence")
            source_binding = initial_operation_source(session, data["context"])
            require(source_binding["currentSha256"] != data["seal"]["initialOrdinary"]["currentSha256"],
                    "INITIAL_UPLOAD_FRESH_SOURCE_REQUIRED")
            check()
        else:
            admission(owner, profile, private.path / ("upload-" + phase + "-admission"), check, expected=data["admitted"])
        output = owner.child(private, "export", end)
        manifest_raw = owner.read(output, posix.MANIFEST, end, 65536)
        require(digest(manifest_raw) == data["seal"]["manifestSha256"] and
                parse(manifest_raw)["artifact"] == data["seal"]["artifact"] and
                artifact_metadata(owner, output, end) == data["seal"]["artifact"], "UPLOAD_SEALED_MANIFEST_CHANGED")
        binding = delivery_binding(data, desktop_upload_scope(data))
        observed = check()
        if phase == "before":
            minutes = (fence - observed) // (60 * job_time.NS)
            require(1 <= minutes <= 3, "UPLOAD_NO_COMPLETE_MINUTE_LEFT")
            raw = encoded({**binding, "beganRawNs": began, "endRawNs": fence,
                "timeoutObservedRawNs": observed, "timeoutMinutes": minutes,
                **({"initialSource": source_binding} if initial_kind else {})})
            desktop_upload_before(data, raw)
            owner.write(private, "upload-before.json", raw, end)
            outputs = "upload_ready=true\nupload_timeout_minutes=" + str(minutes) + "\nupload_guard_sha256=" + digest(raw) + "\n"
        else:
            owner.write(private, "upload-after.json", {**binding, "beforeSha256": digest(before_raw),
                "observedRawNs": observed, "stepOutcome": "success",
                **({"initialSource": source_binding} if initial_kind else {})}, end)
            desktop_upload_pair(owner, data, end)
            outputs = "upload_complete=true\n"
        check()
    except BaseException as caught:
        error = caught
        owner.error("desktop-upload-" + phase, caught)
        if data is not None and "currentSession" in data:
            data["currentSession"].fail(caught)
    finally:
        try:
            owner.close()
        except BaseException as caught:
            error = error or caught
    if error is not None:
        raise error
    require(outputs is not None and not owner.unknown, "UPLOAD_GUARD_NOT_RETURNED")
    append_outputs(outputs, check)
    print(("INITIAL_ORDINARY_" if initial_kind else "ORDINARY_") + profile.upper().replace("-", "_") + "_UPLOAD_GUARD=" +
          phase.upper() + "; NO_UPLOAD_PERFORMED")


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
    require(profile != jvm.PROFILE, "JVM_REQUIRES_NATIVE_PROVIDER_ENTRY")
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
                 "prepare-consume", "restore-guard", "package-samples", "sample-upload-guard", "sample-delivery-guard",
                 "ordinary-prepare-restore", "initial-prepare-restore", "initial-run", "initial-validate-public",
                 "_initial-crypto", "initial-upload-guard"):
        entry = sub.add_parser(name)
        entry.add_argument("--profile", choices=("desktop",) if name in
                           ("package-samples", "sample-upload-guard", "sample-delivery-guard") else PRODUCT_SECONDS,
                           required=True)
        if name in ("_crypto", "_initial-crypto"):
            entry.add_argument("phase", choices=("validate", "export"))
            entry.add_argument("--context-sha256", required=True)
        elif name == "_job-time":
            entry.add_argument("--admission-sha256", required=True)
        elif name in ("upload-guard", "initial-upload-guard", "sample-upload-guard"):
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
        if args.operation == "initial-run":
            return initial_run(args.profile)
        if args.operation == "validate-public":
            guarded_operation(validate_public, args.profile)
        elif args.operation == "initial-validate-public":
            guarded_operation(initial_validate_public, args.profile)
        elif args.operation == "ordinary-prepare-restore":
            guarded_operation(ordinary_prepare_restore, args.profile)
        elif args.operation == "initial-prepare-restore":
            guarded_operation(initial_prepare_restore, args.profile)
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
        elif args.operation == "initial-upload-guard":
            guarded_operation(initial_upload_guard, args.phase, args.profile)
        else:
            require(re.fullmatch(r"[0-9a-f]{64}", args.context_sha256), "CRYPTO_CONTEXT_HASH")
            (initial_crypto_phase if args.operation == "_initial-crypto" else crypto_phase)(
                args.phase, args.profile, args.context_sha256)
        return 0
    except BaseException:
        print("ORDINARY_TEST_CUSTODY=HOLD; PRIVATE_EVIDENCE_REQUIRED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
