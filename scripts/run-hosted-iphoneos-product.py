#!/usr/bin/env python3
"""Closed unsigned iphoneos recipe proof, not a runtime, signing or release gate.

Only the exact manual Desktop operation may call this adapter. Product processes
use the existing immutable audit leaf; small tool/leaf-controller processes use
its existing native ownership backend with private, caller-owned output sinks.
No generic command, task, ref, runner, recipient or timeout input is accepted.
Public-build output classification and the finite caps require independent review
before dispatch. Imports do not launch tools or create execution state.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import signal
import stat
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY, WORKFLOW, JOB = "p2pKit/P2pKit", ".github/workflows/desktop-cross-host.yml", "iphoneos-product"
ROLE = "macos-arm64"
DEVELOPER = "/Applications/Xcode_26.5.app/Contents/Developer"
SCOPE = "UNSIGNED_IPHONEOS_RECIPE_PRODUCT_ONLY"
MIB, GIB = 1024 ** 2, 1024 ** 3
DRIVER_SECONDS, COMPLETION_SECONDS, FINAL_SECONDS = 9000, 600, 300
META_LIMIT, LOG_LIMIT, LOG_TOTAL, PUBLIC_TOTAL = 4 * MIB, 32 * MIB, 128 * MIB, 256 * MIB
FILE_LIMIT, PRODUCT_TOTAL, PRODUCT_FILES = 512 * MIB, 2 * GIB, 4096
TASK = ":p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance"
SIDECARS = ("BUILD_COMMIT.txt", "BUILD_SOURCE_STATE.txt", "BUILD_INPUTS_SHA256.txt", "BUILD_ARTIFACTS_SHA256.txt")
LEAF_FILES = ("start.json", "receipt.json", "report-manifest.json", "product.stdout.log", "product.stderr.log",
              "stop.stdout.log", "stop.stderr.log")
LEAVES = {"xcodegen-install": "command", "xcframework-build": "gradle", "xcode-project": "gradle",
          "iphoneos-build": "command", "xcode-provenance": "gradle"}
COMMAND_CAPS = {"java17": 60, "java21": 60, "xcode-version": 60, "xcode-first-launch": 60, "memory": 30,
                "iphoneos-sdk": 60, "iphonesimulator-sdk": 60, "init": 60, "xcodegen-install": 900,
                "xcframework-build": 7200, "xcode-project": 600, "iphoneos-build": 7200,
                "app-vtool": 120, "app-lipo": 120, "framework-vtool": 120, "framework-lipo": 120, "cleanup": 180}
COMMANDS = frozenset(COMMAND_CAPS)
TOOLCHAIN_COMMANDS = tuple(COMMAND_CAPS)[:7]
TOOLCHAIN_FILES = ("toolchains.json", "toolchains/SystemVersion.plist", "toolchains/iphoneos.json",
                   "toolchains/iphonesimulator.json", "toolchains/android-36.properties", "toolchains/android-37.0.properties")
PUBLIC_FIXED = frozenset({"admission.json", "result.json", "toolchains.json", "product.json", "cleanup.json",
                         "budget.json", "context.json", "gradle-policy.properties", "producer-product.json",
                         "xcframework-sidecars.json", "host-xcframework-build.json", *SIDECARS,
                         "cleanup/start.json", "cleanup/receipt.json",
                         "toolchains/SystemVersion.plist", "toolchains/iphoneos.json", "toolchains/iphonesimulator.json",
                         "toolchains/android-36.properties", "toolchains/android-37.0.properties",
                         "products/Info.plist", "products/framework-Info.plist", "products/p2pkit-sample-ui.xcscheme"})
DEVICE_BINARY = "library/p2p-transport-lan/build/XCFrameworks/release/P2pKitShared.xcframework/ios-arm64/P2pKitShared.framework/P2pKitShared"
APP_RELATIVE = "Build/Products/Debug-iphoneos/p2pkit-sample.app"
FRAMEWORK_RELATIVE = "Frameworks/P2pKitShared.framework/P2pKitShared"


class RouteError(ValueError):
    """Only fixed reason codes may be printed; original build diagnostics are retained separately."""


def require(value, code):
    if not value:
        raise RouteError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def reason(error):
    return error.args[0] if isinstance(error, RouteError) else type(error).__name__


def number(value, maximum):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum


def hash_record(value, *, nonempty=False, limit=FILE_LIMIT):
    require(type(value) is dict and set(value) == {"bytes", "sha256"} and
            type(value["bytes"]) is int and int(nonempty) <= value["bytes"] <= limit and
            type(value["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]), "HASH_RECORD")
    return value


def load_script(name):
    spec = importlib.util.spec_from_file_location("iphoneos_" + name.replace("-", "_"), ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    # The isolated top-level driver admits only this checked-in module directory.
    # The existing public leaf imports its existing audit_processes sibling.
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def physical(path, *, installed=False):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts and not any(c in str(path) for c in "\r\n\0"), "PATH")
    if installed:
        return path.resolve(strict=True)
    require(all(not part.is_symlink() for part in (path, *path.parents)), "PATH_LINK")
    return path


def fd_stream(fd, mode):
    try:
        return os.fdopen(fd, mode)
    except BaseException:
        os.close(fd)
        raise


def file_record(path, *, limit=FILE_LIMIT, retain=False, installed=False, check=lambda: None):
    path = physical(path, installed=installed)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= limit, "FILE_KIND_SIZE")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    chunks, checksum, size = [], hashlib.sha256(), 0
    with fd_stream(fd, "rb") as stream:
        require(os.path.samestat(before, os.fstat(stream.fileno())), "FILE_REPLACED")
        while True:
            check()
            block = stream.read(min(128 * 1024, limit + 1 - size))
            if not block:
                break
            size += len(block)
            require(size <= limit, "FILE_LIMIT")
            checksum.update(block)
            if retain:
                chunks.append(block)
        after = os.fstat(stream.fileno())
    require(os.path.samestat(before, after) and os.path.samestat(after, path.lstat()) and
            size == before.st_size == after.st_size and before.st_mtime_ns == after.st_mtime_ns, "FILE_CHANGED")
    return {"bytes": size, "sha256": checksum.hexdigest()}, b"".join(chunks) if retain else None


def read(path, limit=META_LIMIT, *, installed=False):
    return file_record(path, limit=limit, retain=True, installed=installed)[1]


def parse(raw):
    def pairs(items):
        result = {}
        for name, value in items:
            require(name not in result, "JSON_DUPLICATE")
            result[name] = value
        return result
    def finite_float(token):
        value = float(token)
        require(math.isfinite(value), "JSON_NONFINITE")
        return value
    require(type(raw) is bytes and 0 < len(raw) <= META_LIMIT, "JSON_SIZE")
    return json.loads(raw, object_pairs_hook=pairs, parse_float=finite_float,
                      parse_constant=lambda _: require(False, "JSON_NONFINITE"))


def encoded(value):
    raw = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
    require(len(raw) <= META_LIMIT, "METADATA_LIMIT")
    return raw


def write(path, raw):
    path = physical(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with fd_stream(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def dispatch_identity(env, event, source):
    expected, tree = env.get("P2PKIT_EXPECTED_SHA", ""), env.get("P2PKIT_EXPECTED_TREE", "")
    require(re.fullmatch(r"[0-9a-f]{40}", expected) and re.fullmatch(r"[0-9a-f]{40}", tree), "SOURCE_INPUT")
    fixed = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": REPOSITORY,
             "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
             "GITHUB_WORKFLOW": "Desktop cross-host", "GITHUB_JOB": JOB, "GITHUB_SHA": expected,
             "GITHUB_WORKFLOW_SHA": expected, "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS",
             "RUNNER_ARCH": "ARM64", "P2PKIT_OPERATION": JOB, "DEVELOPER_DIR": DEVELOPER}
    require(all(env.get(key) == value for key, value in fixed.items()), "DISPATCH_IDENTITY")
    ref = env.get("GITHUB_REF", "")
    require(ref.startswith("refs/heads/") and len(ref) <= 256 and not any(c in ref for c in "\r\n\0") and
            ref != "refs/heads/audit/complete-2026-09-04", "BRANCH")
    require(env.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + WORKFLOW + "@" + ref, "WORKFLOW_REF")
    require(all(re.fullmatch(r"[1-9][0-9]{0,19}", env.get(key, "")) for key in
                ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")), "RUN_ID")
    require(type(event) is dict and event.get("repository", {}).get("full_name") == REPOSITORY and
            event.get("ref") in (ref, ref[len("refs/heads/"):]), "EVENT")
    supplied = event.get("inputs")
    empty = {"reviewed_base", "evidence_public_key", "evidence_fingerprint"}
    require(type(supplied) is dict and {k: v for k, v in supplied.items() if k not in empty} ==
            {"operation": JOB, "expected_sha": expected, "expected_tree": tree} and
            all(type(supplied[k]) is str and supplied[k] == "" for k in empty & supplied.keys()), "EVENT_INPUTS")
    require(source == {"commit": expected, "tree": tree, "status": "", "diffSha256": digest(b"")}, "SOURCE")
    return {"repository": REPOSITORY, "workflow": WORKFLOW, "workflowRef": env["GITHUB_WORKFLOW_REF"],
            "workflowSha": expected, "ref": ref, "event": "workflow_dispatch", "job": JOB, "host": ROLE,
            "runId": env["GITHUB_RUN_ID"], "runAttempt": env["GITHUB_RUN_ATTEMPT"], "source": source, "scope": SCOPE}


def build_environment(env):
    # Never pass Actions tokens, recipients, publishing/signing values, injected
    # Gradle/JVM/shell/Git/Python hooks, proxies, agents or arbitrary P2PKIT opt-ins.
    hooks = ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS",
             "BASH_ENV", "ENV", "PYTHONPATH", "PYTHONHOME", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES")
    require(not any(env.get(name, "").strip() for name in hooks), "AMBIENT_HOOK")
    names = ("PATH", "HOME", "TMPDIR", "JAVA_HOME", "P2PKIT_AUDIT_JDK21", "DEVELOPER_DIR", "ANDROID_HOME")
    result = {name: env[name] for name in names if env.get(name)}
    require(all(name in result for name in ("PATH", "HOME", "DEVELOPER_DIR")), "ENVIRONMENT_REQUIRED")
    require(all(type(value) is str and not any(c in value for c in "\0\r\n") for value in result.values()), "ENVIRONMENT_VALUE")
    require(all(Path(part).is_absolute() for part in result["PATH"].split(os.pathsep)), "PATH_SEARCH")
    result.update(LANG="en_US.UTF-8", LC_ALL="en_US.UTF-8", PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
                  GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    return result


def admission(env, audit, *, failure_export=False):
    require(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, "ISOLATED_PYTHON")
    require(os.getuid() != 0 and audit.host_role() == ROLE, "NATIVE_USER")
    source = audit.source_snapshot(ROOT)
    require(audit.git(ROOT, "rev-parse", "--is-shallow-repository").strip() == b"false", "FULL_HISTORY")
    event_raw = read(Path(env["GITHUB_EVENT_PATH"]))
    if failure_export:
        # A failed generation may have dirtied a tracked plist. Preserve its
        # original failed logs; this never admits another product or a PASS.
        require(source["commit"] == env.get("P2PKIT_EXPECTED_SHA") and source["tree"] == env.get("P2PKIT_EXPECTED_TREE"), "SOURCE")
        source = {**source, "status": "", "diffSha256": digest(b"")}
    result = dispatch_identity(env, parse(event_raw), source)
    result["eventSha256"] = digest(event_raw)  # Never retain the raw shared dispatch event.
    result["pythonExecutable"] = str(physical(Path(sys.executable), installed=True))
    return result


def xcode_arguments(derived):
    return ["/usr/bin/xcodebuild", "-jobs", "2", "-project", "samples/iosApp/p2pkit-sample.xcodeproj",
            "-scheme", "p2pkit-sample-ui", "-configuration", "Debug", "-sdk", "iphoneos", "-destination",
            "generic/platform=iOS", "-derivedDataPath", str(derived), "CODE_SIGNING_ALLOWED=NO",
            "SWIFT_TREAT_WARNINGS_AS_ERRORS=YES", "build"]


def assess_native(vtool, lipo, minimum):
    text = vtool.decode("utf-8")
    fields = {key: re.findall(r"^\s*" + key + r"\s+([^\s]+)\s*$", text, re.M) for key in ("platform", "minos", "sdk")}
    require(lipo.decode("ascii").split() == ["arm64"] and fields["platform"] == ["IOS"] and
            fields["minos"] == [minimum] and len(fields["sdk"]) == 1 and
            re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", fields["sdk"][0]), "NATIVE_PRODUCT")
    require(len(re.findall(r"^\s*cmd LC_BUILD_VERSION\s*$", text, re.M)) == 1, "NATIVE_LOAD_COMMAND")
    return {"architectures": ["arm64"], "platform": "IOS", "minimum": minimum, "sdk": fields["sdk"][0]}


def assess_info(raw):
    info = plistlib.loads(raw)
    require(type(info) is dict and info.get("CFBundleIdentifier") == "dev.p2pkit.sample" and
            info.get("CFBundleExecutable") == "p2pkit-sample" and info.get("CFBundlePackageType") == "APPL" and
            info.get("DTPlatformName") == "iphoneos" and info.get("CFBundleSupportedPlatforms") == ["iPhoneOS"] and
            info.get("MinimumOSVersion") == "15.0" and info.get("CFBundleShortVersionString") == "1.0.0" and
            info.get("CFBundleVersion") == "1" and info.get("NSBonjourServices") == ["_p2pkit2._tcp"] and
            type(info.get("NSLocalNetworkUsageDescription")) is str and info["NSLocalNetworkUsageDescription"], "APP_INFO")
    return {name: info[name] for name in ("CFBundleIdentifier", "CFBundleExecutable", "DTPlatformName", "MinimumOSVersion",
                                         "CFBundleShortVersionString", "CFBundleVersion")}


def assess_framework_info(raw):
    info = plistlib.loads(raw)
    require(type(info) is dict and info.get("CFBundleExecutable") == "P2pKitShared" and
            info.get("CFBundlePackageType") == "FMWK" and info.get("CFBundleSupportedPlatforms") == ["iPhoneOS"] and
            info.get("MinimumOSVersion") == "14.0", "FRAMEWORK_INFO")
    return info


def leaf_arguments(purpose, work):
    return {"xcodegen-install": ["/bin/bash", "scripts/install-xcodegen.sh", str(work / "xcodegen")],
            "xcframework-build": [TASK], "xcode-project": [":iosApp:regenerateXcodeProject"],
            "iphoneos-build": xcode_arguments(work / "state/xcode-deriveddata"),
            "xcode-provenance": [TASK, "-q", "--console=plain"]}[purpose]


def public_path(name):
    if type(name) is not str or PurePosixPath(name).as_posix() != name or ".." in PurePosixPath(name).parts:
        return False
    if name in PUBLIC_FIXED:
        return True
    parts = PurePosixPath(name).parts
    if len(parts) == 3 and parts[0] == "commands" and parts[1] in COMMANDS:
        return parts[2] in ("record.json", "stdout.log", "stderr.log")
    return len(parts) == 3 and parts[0] == "leaves" and re.fullmatch(r"[0-9a-f]{32}", parts[1]) is not None and parts[2] in LEAF_FILES


def files_bounded(root, entries_limit, depth_limit, directory_allowed=lambda _: True):
    """Count *all* entries while scanning, including empty directories, without following links."""
    require(stat.S_ISDIR(physical(root).lstat().st_mode), "INVENTORY_ROOT")
    pending, count = [root], 0
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1
                require(count <= entries_limit, "INVENTORY_ENTRIES")
                path = physical(Path(entry.path))
                relative = path.relative_to(root).as_posix()
                mode = path.lstat().st_mode
                if stat.S_ISDIR(mode):
                    require(len(path.relative_to(root).parts) <= depth_limit and directory_allowed(relative), "INVENTORY_DIRECTORY")
                    pending.append(path)
                else:
                    require(stat.S_ISREG(mode), "INVENTORY_FILE")
                    yield path


def public_directory(name):
    parts = PurePosixPath(name).parts
    if len(parts) == 1:
        return name in ("commands", "leaves", "products", "cleanup", "toolchains")
    return len(parts) == 2 and ((parts[0] == "commands" and parts[1] in COMMANDS) or
                               (parts[0] == "leaves" and re.fullmatch(r"[0-9a-f]{32}", parts[1]) is not None))


def public_inventory(root):
    rows, metadata, logs, log_bytes, total = [], 0, 0, 0, 0
    for path in files_bounded(root, 224, 2, public_directory):
        relative = path.relative_to(root).as_posix()
        if relative == "manifest.json":
            # Its digest cannot include itself, but its count/bytes still consume
            # the same public quota as every other original metadata member.
            item, _ = file_record(path, limit=META_LIMIT)
            metadata += 1
            total += item["bytes"]
            require(metadata <= 64 and total <= PUBLIC_TOTAL, "PUBLIC_LIMIT")
            continue
        require(public_path(relative), "PUBLIC_MEMBER")
        log = relative.endswith(".log")
        row, _ = file_record(path, limit=LOG_LIMIT if log else META_LIMIT)
        logs += int(log)
        metadata += int(not log)
        log_bytes += row["bytes"] if log else 0
        total += row["bytes"]
        require(logs <= 96 and metadata <= 64 and log_bytes <= LOG_TOTAL and total <= PUBLIC_TOTAL, "PUBLIC_LIMIT")
        rows.append({"path": relative, **row})
    require(rows, "PUBLIC_EMPTY")
    return sorted(rows, key=lambda row: row["path"])


class Driver:
    def __init__(self, env, admitted, audit, entered):
        self.audit, self.admitted, self.env = audit, admitted, build_environment(env)
        self.entered, self.deadline, self.cancelled = entered, entered + DRIVER_SECONDS, []
        self.job, self.safe, self.context = uuid.uuid4().hex, True, None
        base = physical(Path(env["RUNNER_TEMP"]))
        suffix = admitted["runId"] + "-" + admitted["runAttempt"]
        self.work, self.public = base / ("p2pkit-iphoneos-work-" + suffix), base / ("p2pkit-iphoneos-evidence-" + suffix)
        require(not self.work.exists() and not self.public.exists(), "FRESH_RUN")
        self.work.mkdir(mode=0o700)
        self.work_identity = self.work.stat()
        self.state, self.retained = self.work / "state", self.work / "retained"
        self.retained.mkdir(mode=0o700)
        for name in ("commands", "products", "leaves"):
            (self.retained / name).mkdir(mode=0o700)
        for name in ("home", "tmp"):
            (self.work / name).mkdir(mode=0o700)
        self.env.update(HOME=str(self.work / "home"), TMPDIR=str(self.work / "tmp"),
                        P2PKIT_AUDIT_STATE_DIR=str(self.state), GRADLE_USER_HOME=str(self.state / "gradle-home"),
                        KONAN_DATA_DIR=str(self.state / "konan"), ANDROID_USER_HOME=str(self.state / "android-user"),
                        P2PKIT_GRADLE_EXECUTOR=str(ROOT / "scripts/run-audit-command.py"), P2PKIT_XCODE_JOBS="2")
        self.commands, self.receipts, self.handlers, self.attempted_leaves = {}, {}, {}, {}
        self.prerequisite_captures = {}
        self.fresh_caches = [path for path in (ROOT / ".gradle", ROOT / ".kotlin", ROOT / "buildSrc/.gradle")
                             if not path.exists() and not path.is_symlink()]
        self.initial_info = digest(read(ROOT / "samples/iosApp/Info.plist"))
        self.put("admission.json", admitted)
        self.put("budget.json", {"driverSeconds": DRIVER_SECONDS, "leafCompletionSeconds": COMPLETION_SECONDS,
                                "enteredMonotonic": entered, "deadlineMonotonic": self.deadline,
                                "finalSeconds": FINAL_SECONDS, "scope": "CAPS_NOT_DURATION_OR_DOWNLOAD_GUARANTEES"})

    def guard(self, *, final=False):
        require(os.path.samestat(self.work_identity, physical(self.work).stat()), "WORK_IDENTITY")
        require(self.safe and (final or not self.cancelled), "OWNERSHIP_OR_CANCEL_HOLD")
        require(time.monotonic() < self.deadline - (0 if final else FINAL_SECONDS), "DRIVER_DEADLINE")

    def put(self, name, value):
        require(public_path(name), "PUBLIC_MEMBER")
        write(self.retained / name, encoded(value))

    def copy(self, source, name):
        require(public_path(name), "PUBLIC_MEMBER")
        value = read(source, LOG_LIMIT if name.endswith(".log") else META_LIMIT)
        destination = self.retained / name
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write(destination, value)
        require(read(destination, max(META_LIMIT, len(value))) == value ==
                read(source, LOG_LIMIT if name.endswith(".log") else META_LIMIT), "RETENTION_CHANGED")

    def retain_prerequisite(self, name, raw):
        require(name in TOOLCHAIN_FILES and name not in self.prerequisite_captures and
                type(raw) is bytes and len(raw) <= META_LIMIT, "PREREQUISITE_CAPTURE")
        # Bind bytes at the original observation, BEFORE writing. A failed or
        # changed retained copy cannot later be recaptured as the new original.
        self.prerequisite_captures[name] = {"source": dict(self.admitted["source"]),
                                            "file": {"bytes": len(raw), "sha256": digest(raw)}}
        path = self.retained / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write(path, raw)
        require(read(path, META_LIMIT) == raw, "PREREQUISITE_RETENTION_CHANGED")

    def prerequisite_barrier(self, rows, budget):
        present = {row["path"] for row in rows} & set(TOOLCHAIN_FILES)
        commands = {PurePosixPath(row["path"]).parts[1] for row in rows if row["path"].startswith("commands/")}
        require(commands == set(self.commands), "RETAINED_COMMAND_PHASE")
        # The later export seal cannot undo deletion. Require the same reached
        # init/command/context agreement here, including the no-context branch.
        order = [name for name in COMMAND_CAPS if name in commands]
        productive = [name for name in order if name != "cleanup"]
        require(productive == list(COMMAND_CAPS)[:len(productive)] and
                all(self.commands[name]["exitCode"] == 0 for name in productive[:-1]) and
                len({record["id"] for record in self.commands.values()}) == len(self.commands) and
                all(self.commands[first]["endedMonotonic"] <= self.commands[second]["startedMonotonic"]
                    for first, second in zip(order, order[1:])), "RETAINED_COMMAND_ORDER")
        init, initialized = self.commands.get("init"), self.context is not None
        require(initialized == (init is not None and init["exitCode"] == 0), "RETAINED_INIT_PHASE")
        post_init = commands - set(TOOLCHAIN_COMMANDS) - {"init"}
        phase_files = {row["path"] for row in rows}
        require(initialized or (not self.attempted_leaves and not self.state.exists() and not self.state.is_symlink() and
                not post_init and not phase_files.intersection({"context.json", "gradle-policy.properties"}) and
                not any(name.startswith("leaves/") for name in phase_files)), "RETAINED_INIT_PHASE")
        if init is not None:
            expected_init = [self.admitted["pythonExecutable"], "-B", "-S", str(ROOT / "scripts/run-audit-command.py"),
                             "init", "--root", str(ROOT), "--state", str(self.state), "--expected-commit",
                             self.admitted["source"]["commit"], "--host", ROLE]
            require(init.get("argv") == expected_init and init.get("leafId") is None and
                    init.get("jobId") == self.job and init.get("state") == str(self.work) and
                    init.get("gradleHome") == str(self.state / "gradle-home") and
                    (not initialized or self.context.get("id") != self.job), "RETAINED_INIT_COMMAND")
            require(all(self.commands[name].get("jobId") == self.context["id"] and
                        self.commands[name].get("state") == str(self.state) and
                        self.commands[name].get("gradleHome") == str(self.state / "gradle-home")
                        for name in post_init), "RETAINED_INIT_DOMAIN")
        # Actual init/leaf/state evidence is authoritative; a missing summary or
        # a relabelled in-memory context cannot make a completed phase optional.
        complete = (self.context is not None or bool(self.attempted_leaves) or self.state.exists() or self.state.is_symlink() or
                    bool(commands - set(TOOLCHAIN_COMMANDS)) or "toolchains.json" in present or
                    "toolchains.json" in self.prerequisite_captures)
        require(present == set(self.prerequisite_captures) and
                (not complete or present == set(TOOLCHAIN_FILES)), "RETAINED_PREREQUISITE_PHASE")
        for name, original in self.prerequisite_captures.items():
            require(original == {"source": self.admitted["source"],
                    "file": file_record(self.retained / name, limit=META_LIMIT)[0]}, "RETAINED_TOOLCHAIN_CAPTURE")
        if not complete:
            # Genuine pre-init rejection may retain a partial original family;
            # it must not invent SDK/JDK metadata for stages never reached.
            require(commands <= set(TOOLCHAIN_COMMANDS), "RETAINED_PREREQUISITE_PHASE")
            return
        value = public_toolchains(self.retained)
        expected = {"xcode-version": ["/usr/bin/xcodebuild", "-version"],
                    "xcode-first-launch": ["/usr/bin/xcodebuild", "-checkFirstLaunchStatus"],
                    "memory": ["/usr/sbin/sysctl", "-n", "hw.memsize"]}
        for label, variable in (("java17", "JAVA_HOME"), ("java21", "P2PKIT_AUDIT_JDK21")):
            home = value["java"][label]["home"]
            require(home == self.env.get(variable), "RETAINED_PREREQUISITE_JAVA")
            expected[label] = [str(Path(home) / "bin/java"), "-XshowSettings:properties", "-version"]
        for sdk in ("iphoneos", "iphonesimulator"):
            expected[sdk + "-sdk"] = ["/usr/bin/xcrun", "--sdk", sdk, "--show-sdk-path"]
            require(read(self.retained / "commands" / (sdk + "-sdk") / "stdout.log", LOG_LIMIT).decode("utf-8").strip() ==
                    value["sdks"][sdk]["path"], "RETAINED_PREREQUISITE_SDK")
        records = []
        for name in TOOLCHAIN_COMMANDS:
            record = command_evidence(self.retained, name, self.admitted, budget, allow_failure=False)
            require(record == self.commands.get(name) and record.get("argv") == expected[name] and
                    record.get("leafId") is None and record.get("jobId") == self.job and
                    record.get("state") == str(self.work) and record.get("gradleHome") == str(self.state / "gradle-home"),
                    "RETAINED_PREREQUISITE_COMMAND")
            records.append(record)
        require(all(first["endedMonotonic"] <= second["startedMonotonic"] for first, second in zip(records, records[1:])) and
                len({record["id"] for record in records}) == len(records), "RETAINED_PREREQUISITE_ORDER")

    def command(self, name, argv, cap, *, leaf_id=None, final=False):
        self.guard(final=final)
        require(name in COMMANDS and name not in self.commands, "COMMAND_IDENTITY")
        require(number(cap, COMMAND_CAPS[name]) and cap >= 0.1, "COMMAND_CAP")
        started = time.monotonic()
        reserve = COMPLETION_SECONDS if leaf_id else 15
        seconds = min(cap, self.deadline - started - reserve - (0 if final else FINAL_SECONDS))
        require(seconds >= 0.1, "NOT_EXECUTED_BUDGET")
        directory = self.retained / "commands" / name
        directory.mkdir(mode=0o700)
        invocation = uuid.uuid4().hex
        # A canonical leaf must inherit its *same* admitted job/state/home.
        # Before init, native tools belong only to this driver's fresh domain.
        job = self.context["id"] if self.context is not None else self.job
        state = str(self.state if self.context is not None else self.work)
        record = {"id": invocation, "name": name, "argv": argv, "capSeconds": seconds, "exitCode": None,
                  "jobId": job, "state": state, "gradleHome": str(self.state / "gradle-home"), "leafId": leaf_id,
                  "cancelRequested": False, "retirement": "UNKNOWN", "errors": [], "source": self.admitted["source"]}
        self.commands[name] = record
        scope, child, outputs, captured = None, None, [], {}
        productive_end, completion_end = started + seconds, started + seconds + reserve
        record.update(startedMonotonic=started, productiveDeadlineMonotonic=productive_end,
                      completionDeadlineMonotonic=completion_end)

        def cancel_leaf():
            nonlocal completion_end
            if not record["cancelRequested"]:
                record["cancelRequested"] = True
                # Early cancellation shortens the already reserved window. A
                # repeated signal/error cannot grant another completion window.
                completion_end = min(completion_end, time.monotonic() + reserve)
                record["completionDeadlineMonotonic"] = completion_end
                if leaf_id:
                    self.audit.request_cancellation(self.state, self.context["id"], leaf_id)

        try:
            for filename in ("stdout.log", "stderr.log"):
                path = physical(directory / filename)
                outputs.append(fd_stream(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb"))
            scope = self.audit.make_scope(job, invocation, state, str(self.state / "gradle-home"))
            environment = self.audit.ownership_environment(self.env, job, invocation, state,
                                                          str(self.state / "gradle-home"))
            child = scope.spawn(argv, str(ROOT), environment, stdout=outputs[0], stderr=outputs[1])
            while True:
                record["exitCode"] = child.poll()
                scope.discover()
                require(all(os.fstat(stream.fileno()).st_size <= LOG_LIMIT for stream in outputs), "OUTPUT_LIMIT")
                now = time.monotonic()
                if self.cancelled or now >= productive_end:
                    cancel_leaf()
                    # Keep the last 10s of the *same* completion reserve for
                    # the unchanged native 5+5s drain; never add it afterward.
                    if not leaf_id or now >= completion_end - 10:
                        raise RouteError("COMMAND_DEADLINE")
                if record["exitCode"] is not None:
                    break
                time.sleep(0.1)
        except BaseException as error:
            record["errors"].append(reason(error))
            # Even capture/observation failure requests the canonical leaf's
            # finally/--stop before native drain. Preserve the first cause.
            if leaf_id and scope is not None:
                try:
                    cancel_leaf()
                    while time.monotonic() < completion_end - 10 and any(p.poll() is None for p in scope.leaders):
                        scope.discover()
                        time.sleep(0.1)
                except BaseException as caught:
                    record["errors"].append("CANCELLATION_" + reason(caught))
        finally:
            if scope is not None:
                try:
                    survivors = scope.drain()
                    record["ownership"] = scope.description()
                    require(survivors == [] and not record["ownership"].get("discoveryErrors"), "OWNED_SURVIVORS")
                    record["retirement"] = "KNOWN"
                except BaseException as error:
                    record["errors"].append("RETIREMENT_" + reason(error))
                    self.safe = False
                try:
                    scope.close()
                except BaseException as error:
                    record["retirement"] = "UNKNOWN"
                    record["errors"].append("SCOPE_CLOSE_" + type(error).__name__)
                    self.safe = False
            else:
                record["retirement"] = "KNOWN"  # No scope returned, hence no spawn was attempted.
            for output in outputs:
                try:
                    output.flush()
                    os.fsync(output.fileno())
                except BaseException as error:
                    record["errors"].append("OUTPUT_SYNC_" + reason(error))
                finally:
                    try:
                        output.close()
                    except BaseException as error:
                        record["retirement"] = "UNKNOWN"
                        record["errors"].append("OUTPUT_CLOSE_" + reason(error))
                        self.safe = False
            try:
                for filename in ("stdout.log", "stderr.log"):
                    captured[filename] = file_record(directory / filename, limit=LOG_LIMIT, retain=True,
                        check=lambda: require(time.monotonic() < completion_end, "COMPLETION_DEADLINE"))
                record["outputs"] = {name: value[0] for name, value in captured.items()}
            except BaseException as error:
                # Oversized originals stay in place. Never trim to the export cap.
                record["errors"].append("OUTPUT_RETENTION_" + reason(error))
            ended = time.monotonic()
            record.update(endedMonotonic=ended, durationSeconds=ended - started)
            if ended >= completion_end:
                record["errors"].append("COMPLETION_DEADLINE")
            self.put("commands/" + name + "/record.json", record)
        # The terminal record cannot include its own fsync duration. A late
        # record write still prevents success, rather than resetting any budget.
        require(time.monotonic() < completion_end, "COMPLETION_DEADLINE")
        self.guard(final=final)
        require(record["retirement"] == "KNOWN" and not record["errors"] and not record["cancelRequested"], "COMMAND_HOLD")
        require(record["exitCode"] == 0, "COMMAND_FAILED")
        return captured["stdout.log"][1], captured["stderr.log"][1]

    def prerequisites(self):
        self.guard()
        require(shutil.disk_usage(self.work).free >= 16 * GIB, "DISK_ADMISSION")
        system_raw = read(Path("/System/Library/CoreServices/SystemVersion.plist"), installed=True)
        system = plistlib.loads(system_raw)
        (self.retained / "toolchains").mkdir(mode=0o700)
        self.retain_prerequisite("toolchains/SystemVersion.plist", system_raw)
        require(system.get("ProductVersion", "").split(".")[0] == "26", "MACOS_VERSION")
        developer = physical(Path(DEVELOPER), installed=True)
        require(developer.is_dir(), "XCODE_INSTALLATION")
        result = {"macOS": system["ProductVersion"], "developerDirectory": str(developer), "java": {}, "sdks": {}}
        for label, variable, version in (("java17", "JAVA_HOME", "17"), ("java21", "P2PKIT_AUDIT_JDK21", "21")):
            home = physical(Path(self.env.get(variable, "")), installed=True)
            require((home / "bin/javac").is_file(), "JDK_INSTALLATION")
            stdout, stderr = self.command(label, [str(home / "bin/java"), "-XshowSettings:properties", "-version"], 60)
            text = (stdout + stderr).decode("utf-8")
            require(re.search(r'\bversion "' + version + r'\.', text) and
                    re.search(r"^\s*os.arch = (?:aarch64|arm64)\s*$", text, re.M), "JDK_VERSION_ARCH")
            self.env[variable] = str(home)
            result["java"][label] = {"home": str(home), "major": version, "native": True}
        xcode, _ = self.command("xcode-version", ["/usr/bin/xcodebuild", "-version"], 60)
        require(xcode.decode("utf-8").splitlines()[0] == "Xcode 26.5", "XCODE_VERSION")
        self.command("xcode-first-launch", ["/usr/bin/xcodebuild", "-checkFirstLaunchStatus"], 60)
        memory, _ = self.command("memory", ["/usr/sbin/sysctl", "-n", "hw.memsize"], 30)
        require(re.fullmatch(rb"[0-9]+\n?", memory) and int(memory) >= 6 * GIB, "MEMORY_ADMISSION")
        result["physicalMemoryBytes"] = int(memory)
        for sdk in ("iphoneos", "iphonesimulator"):
            output, _ = self.command(sdk + "-sdk", ["/usr/bin/xcrun", "--sdk", sdk, "--show-sdk-path"], 60)
            path = physical(Path(output.decode("utf-8").strip()), installed=True)
            require(developer in path.parents, "SELECTED_SDK_PATH")
            raw = read(path / "SDKSettings.json", installed=True)
            settings = parse(raw)
            self.retain_prerequisite("toolchains/" + sdk + ".json", raw)
            require(type(settings.get("Version")) is str and settings.get("CanonicalName") == sdk + settings["Version"], "APPLE_SDK")
            result["sdks"][sdk] = {"path": str(path), "version": settings["Version"], "canonicalName": settings["CanonicalName"]}
        require(not (ROOT / "local.properties").exists(), "LOCAL_SDK_OVERRIDE")
        android = physical(Path(self.env.get("ANDROID_HOME", "")), installed=True)
        for platform, api in (("android-36", "36"), ("android-37.0", "37.0")):
            raw = read(android / "platforms" / platform / "source.properties", installed=True)
            require(re.findall(rb"^AndroidVersion.ApiLevel=(.+)$", raw, re.M) == [api.encode()], "ANDROID_SDK_METADATA")
            self.retain_prerequisite("toolchains/" + platform + ".properties", raw)
            result["sdks"][platform] = {"api": api, "sourcePropertiesSha256": digest(raw)}
        self.retain_prerequisite("toolchains.json", encoded(result))

    def leaf(self, purpose, arguments, kind, cap):
        self.guard()
        require(LEAVES.get(purpose) == kind and purpose not in self.attempted_leaves and
                arguments == leaf_arguments(purpose, self.work), "LEAF_PURPOSE")
        invocation = uuid.uuid4().hex
        self.attempted_leaves[purpose] = invocation
        seconds = min(cap, self.deadline - time.monotonic() - COMPLETION_SECONDS - FINAL_SECONDS)
        require(seconds >= 0.1, "NOT_EXECUTED_BUDGET")
        receipt = self.state / ("host-" + purpose + ".json")
        # The unchanged leaf needs its sibling module search path. -B -S and
        # the closed, hook-free child environment keep its normal public CLI.
        argv = [self.admitted["pythonExecutable"], "-B", "-S", str(ROOT / "scripts/run-audit-command.py"), "--cwd", str(ROOT),
                "--wrapper", str(ROOT / "gradlew"), "--purpose", purpose, "--kind", kind, "--id", invocation,
                "--receipt", str(receipt), "--timeout", str(seconds), "--stop-timeout", "120", "--", *arguments]
        try:
            self.command(purpose, argv, seconds, leaf_id=invocation)
        finally:
            self.retain_leaves()
        record = parse(read(receipt))
        self.validate_leaf(record, invocation, purpose, kind, arguments, receipt)
        self.receipts[purpose] = record
        return record

    def validate_leaf(self, record, invocation, purpose, kind, arguments, receipt):
        load_script("check-audit-receipt").validate(record, 0, purpose, ROOT, ROOT / "gradlew", arguments)
        require(record.get("id") == invocation and record.get("jobId") == self.context["id"] and
                record.get("kind") == kind and record.get("host") == ROLE and
                record.get("gradleHome") == self.context["gradleHome"] and record.get("sourceBefore") == self.admitted["source"], "LEAF_BINDING")
        expected = [str(ROOT / "gradlew"), *self.audit.gradle_arguments(arguments, reuse_xcframework=purpose == "xcode-provenance")] if kind == "gradle" else arguments
        require(record.get("executedArgv") == expected and not record.get("cancelRequested", False) and
                not record.get("cancelledSignals", []), "LEAF_EXECUTION")
        directory = self.state / "evidence" / invocation
        require(record.get("evidenceDirectory") == str(directory) and read(directory / "receipt.json") == read(receipt), "LEAF_COPY")
        start = parse(read(directory / "start.json"))
        for name in ("schema", "id", "purpose", "kind", "jobId", "host", "gradleHome", "cwd", "wrapper", "requestedArgv"):
            require(start.get(name) == record.get(name) and type(start.get(name)) is type(record.get(name)), "LEAF_START")
        reports = parse(read(directory / "report-manifest.json"))
        require(reports.get("schema") == 1 and reports.get("records") == record.get("reports"), "LEAF_REPORTS")
        require(read(self.state / "context.json") == self.context_bytes, "CONTEXT_CHANGED")

    def retain_leaves(self):
        if self.context is None:
            return
        try:
            for directory in self.leaf_directories():
                start = parse(read(directory / "start.json"))
                require(start.get("purpose") in LEAVES and start.get("jobId") == self.context["id"] and
                        start.get("id") == directory.name, "UNEXPECTED_LEAF")
                for name in LEAF_FILES:
                    source, destination = directory / name, self.retained / "leaves" / directory.name / name
                    # These are terminal productive leaves. No required original
                    # capture becomes optional just because it is absent.
                    if destination.exists():
                        limit = LOG_LIMIT if name.endswith(".log") else META_LIMIT
                        require(read(source, limit) == read(destination, limit), "RETAINED_LEAF_CHANGED")
                    else:
                        self.copy(source, "leaves/" + directory.name + "/" + name)
        except BaseException:
            self.safe = False
            raise

    def leaf_directories(self):
        directories = []
        with os.scandir(physical(self.state / "evidence")) as entries:
            for count, entry in enumerate(entries, 1):
                require(count <= 64, "LEAF_DIRECTORY_LIMIT")
                if re.fullmatch(r"[0-9a-f]{32}", entry.name):
                    path = physical(Path(entry.path))
                    require(stat.S_ISDIR(path.lstat().st_mode), "LEAF_DIRECTORY")
                    directories.append(path)
        require(len(directories) <= len(LEAVES), "LEAF_COUNT")
        return directories

    def terminal_leaves(self, *, for_cleanup):
        """Audit every known attempt independently of capture success and prior failures.

        Empty survivor lists do not establish stream/handle retirement. Both export
        and deletion require complete canonical finalization, including errors=[],
        source/launch/stop bindings and all originals. A nonzero product exit with
        that complete proof is different from an infrastructure/unknown result.
        """
        failures, found = [], set()
        identities = set(self.attempted_leaves.values())
        try:
            require(self.context is not None and read(self.state / "context.json") == self.context_bytes, "CLEANUP_CONTEXT")
        except BaseException as error:
            failures.append(reason(error))
        try:
            # A malformed sibling must not prevent the other known attempts
            # (including the nested prebuild) from receiving their own audit.
            with os.scandir(physical(self.state / "evidence")) as entries:
                for count, entry in enumerate(entries, 1):
                    if count > 64:
                        failures.append("LEAF_DIRECTORY_LIMIT")
                        break
                    try:
                        path = physical(Path(entry.path))
                        if re.fullmatch(r"[0-9a-f]{32}", entry.name):
                            identities.add(entry.name)
                            require(stat.S_ISDIR(path.lstat().st_mode), "LEAF_DIRECTORY")
                        else:
                            require(stat.S_ISREG(path.lstat().st_mode), "UNEXPECTED_EVIDENCE_DIRECTORY")
                    except BaseException as error:
                        failures.append(reason(error))
        except BaseException as error:
            failures.append(reason(error))
        for identity in sorted(identities, key=str):
            try:
                require(type(identity) is str and re.fullmatch(r"[0-9a-f]{32}", identity), "LEAF_ID")
                directory = self.state / "evidence" / identity
                start = parse(read(directory / "start.json"))
                purpose = start.get("purpose")
                require(purpose in LEAVES and (purpose == "xcode-provenance" or
                        self.attempted_leaves.get(purpose) == identity), "UNEXPECTED_LEAF")
                leaf_evidence(directory, identity, purpose, self.work, self.context, self.audit, allow_failure=True)
                if purpose != "xcode-provenance":
                    require(read(self.state / ("host-" + purpose + ".json")) == read(directory / "receipt.json"), "LEAF_COPY")
                found.add(identity)
            except BaseException as error:
                failures.append("LEAF_" + reason(error))
        if failures:
            self.safe = False  # Sticky: a later clean list cannot undo unknown custody.
            raise RouteError("UNPROVED_LEAF_RETIREMENT")
        if len(found) > len(LEAVES) or not set(self.attempted_leaves.values()) <= found:
            self.safe = False
            raise RouteError("UNFINALIZED_LEAF")
        return sorted(found)

    def retention_barrier(self):
        """Required originals must be exact and complete before *any* deletion."""
        try:
            budget = public_budget(self.retained)
            require(parse(read(self.retained / "admission.json")) == self.admitted, "RETAINED_ADMISSION")
            for name, original in self.commands.items():
                record = command_evidence(self.retained, name, self.admitted, budget)
                require(record == original, "RETAINED_COMMAND_CHANGED")
            rows = public_inventory(self.retained)  # Aggregate as well as per-member retention caps.
            if self.context is None:
                self.prerequisite_barrier(rows, budget)
                require(not self.attempted_leaves and not self.state.exists() and
                        not self.state.is_symlink(), "UNPROVED_INIT_PHASE")
                return
            identities = self.terminal_leaves(for_cleanup=True)
            self.retain_leaves()  # All seven originals and exact copies, not exists()-only capture.
            require(read(self.retained / "context.json") == self.context_bytes == read(self.state / "context.json") and
                    read(self.retained / "gradle-policy.properties") == read(self.state / "gradle-home/gradle.properties"),
                    "RETAINED_CONTEXT")
            require(public_context(self.retained, self.admitted, self.audit, self.work) == self.context, "RETAINED_CONTEXT")
            self.prerequisite_barrier(public_inventory(self.retained), budget)
            records = {}
            for purpose, identity in self.attempted_leaves.items():
                record = public_leaf(self.retained, identity, purpose, self.work, self.context, self.audit, allow_failure=True)
                command = self.commands.get(purpose, {})
                leaf_controller(command, record, purpose, self.admitted, self.work)
                records[purpose] = record
            nested_ids = set(identities) - set(self.attempted_leaves.values())
            require(len(nested_ids) <= 1 and (not nested_ids or "iphoneos-build" in records), "RETAINED_NESTED_PHASE")
            if records.get("xcframework-build", {}).get("finalExitCode") == 0:
                producer = records["xcframework-build"]
                require(read(self.retained / "host-xcframework-build.json") == read(self.state / "host-xcframework-build.json"),
                        "RETAINED_PRODUCER")
                binding = public_sidecars(self.retained, producer)
                require(binding == self.audit.xcframework_reuse_binding(self.state, self.context, ROOT, ROOT / "gradlew"),
                        "RETAINED_SIDECARS")
                observed = parse(read(self.retained / "producer-product.json"))
                require(observed == {"source": self.admitted["source"], "binding": binding,
                        "binaryPath": str(ROOT / DEVICE_BINARY),
                        "binary": file_record(ROOT / DEVICE_BINARY, check=lambda: self.guard(final=True))[0],
                        "observation": "AFTER_FRESH_PRODUCER_BEFORE_XCODEBUILD"}, "RETAINED_PRODUCER_OBSERVATION")
            for identity in nested_ids:
                nested = public_leaf(self.retained, identity, "xcode-provenance", self.work, self.context, self.audit, allow_failure=True)
                build = records["iphoneos-build"]
                require(records.get("xcframework-build", {}).get("finalExitCode") == 0 and
                        nested.get("ancestorInvocationIds") == [*build["ancestorInvocationIds"], build["id"]] and
                        nested.get("xcframeworkReuse") == public_sidecars(self.retained, records["xcframework-build"]) and
                        nested.get("xcframeworkReuseUnchanged") is True, "RETAINED_NESTED_REUSE")
            if records.get("xcode-project", {}).get("finalExitCode") == 0:
                require(read(self.retained / "products/p2pkit-sample-ui.xcscheme") == read(ROOT /
                        "samples/iosApp/p2pkit-sample.xcodeproj/xcshareddata/xcschemes/p2pkit-sample-ui.xcscheme"),
                        "RETAINED_SCHEME")
            if records.get("iphoneos-build", {}).get("finalExitCode") == 0:
                product = parse(read(self.retained / "product.json"))
                app = self.state / "xcode-deriveddata" / APP_RELATIVE
                require(product.get("source") == self.admitted["source"] and product.get("app") == str(app) and
                        product.get("buildInvocationId") == records["iphoneos-build"]["id"], "RETAINED_PRODUCT")
                for path, name in ((app / "Info.plist", "products/Info.plist"),
                                   (app / "Frameworks/P2pKitShared.framework/Info.plist", "products/framework-Info.plist")):
                    require(read(path) == read(self.retained / name), "RETAINED_PRODUCT_METADATA")
                for label, path in (("app", app / "p2pkit-sample"), ("framework", app / FRAMEWORK_RELATIVE)):
                    actual = file_record(path, check=lambda: self.guard(final=True))[0]
                    require(all(product["binaries"][label].get(key) == value for key, value in actual.items()),
                            "RETAINED_PRODUCT_BINARY")
            public_inventory(self.retained)
        except BaseException:
            self.safe = False
            raise

    def producer(self):
        record = self.leaf("xcframework-build", [TASK], "gradle", 7200)
        release = ROOT / "library/p2p-transport-lan/build/XCFrameworks/release"
        rows = []
        for name in SIDECARS:
            raw = read(release / name)
            write(self.state / "evidence" / name, raw)
            self.copy(self.state / "evidence" / name, name)
            require(read(release / name) == raw, "SIDECAR_CHANGED")
            rows.append({"path": name, "sha256": digest(raw), "result": "RETAINED"})
        manifest = {"files": rows, "sourceInvocationId": record["id"]}
        write(self.state / "evidence/xcframework-sidecars.json", encoded(manifest))
        self.copy(self.state / "evidence/xcframework-sidecars.json", "xcframework-sidecars.json")
        self.copy(self.state / "host-xcframework-build.json", "host-xcframework-build.json")
        binding = self.audit.xcframework_reuse_binding(self.state, self.context, ROOT, ROOT / "gradlew")
        require(binding is not None and read(self.retained / "BUILD_COMMIT.txt") ==
                (self.admitted["source"]["commit"] + "\n").encode("ascii") and
                read(self.retained / "BUILD_SOURCE_STATE.txt") == b"clean\n", "PRODUCER_SIDECARS")
        self.device_framework = ROOT / DEVICE_BINARY
        self.producer_binary = hash_record(file_record(self.device_framework, check=self.guard)[0], nonempty=True)
        # The fourth sidecar is an aggregate over paths and raw bytes, NOT a
        # per-binary list. This original observation separately binds the actual
        # producer slice before Xcode runs; the app assessor compares real bytes.
        self.put("producer-product.json", {"source": self.admitted["source"], "binding": binding,
                 "binaryPath": str(self.device_framework), "binary": self.producer_binary,
                 "observation": "AFTER_FRESH_PRODUCER_BEFORE_XCODEBUILD"})

    def nested_reuse(self):
        outer = self.receipts["iphoneos-build"]
        candidates = []
        for directory in self.leaf_directories():
            if (directory / "receipt.json").exists():
                record = parse(read(directory / "receipt.json"))
                if record.get("purpose") == "xcode-provenance":
                    candidates.append((record, directory / "receipt.json"))
        require(len(candidates) == 1, "NESTED_COUNT")
        record, receipt = candidates[0]
        self.validate_leaf(record, record["id"], "xcode-provenance", "gradle", [TASK, "-q", "--console=plain"], receipt)
        binding = self.audit.xcframework_reuse_binding(self.state, self.context, ROOT, ROOT / "gradlew")
        require(record.get("ancestorInvocationIds") == [*outer["ancestorInvocationIds"], outer["id"]] and
                record.get("xcframeworkReuse") == binding and record.get("xcframeworkReuseUnchanged") is True and
                record.get("executedArgv") == [str(ROOT / "gradlew"), *self.audit.gradle_arguments(
                    [TASK, "-q", "--console=plain"], reuse_xcframework=True)], "NESTED_REUSE")
        return record["id"]

    def product(self, derived):
        self.guard()
        app = physical(derived / APP_RELATIVE)
        require(app.is_dir(), "APP_ABSENT")
        info = read(app / "Info.plist")
        metadata = assess_info(info)
        toolchains = parse(read(self.retained / "toolchains.json"))
        require(plistlib.loads(info).get("DTSDKName") == toolchains["sdks"]["iphoneos"]["canonicalName"], "APP_SDK_IDENTITY")
        self.copy(app / "Info.plist", "products/Info.plist")
        framework = app / FRAMEWORK_RELATIVE
        assess_framework_info(read(framework.parent / "Info.plist"))
        self.copy(framework.parent / "Info.plist", "products/framework-Info.plist")
        require(file_record(framework, check=self.guard)[0] == self.producer_binary ==
                file_record(self.device_framework, check=self.guard)[0], "EMBEDDED_PRODUCER_CHANGED")
        minimums = re.findall(r"^IOS_MIN_VERSION=([0-9]+\.[0-9]+)$", read(ROOT / "gradle.properties").decode("utf-8"), re.M)
        require(minimums == ["14.0"], "FRAMEWORK_MINIMUM")
        binaries = {}
        for label, binary, minimum in (("app", app / "p2pkit-sample", "15.0"), ("framework", framework, minimums[0])):
            before = file_record(binary, check=self.guard)[0]
            require(before["bytes"] > 0 and binary.stat().st_mode & 0o111, "EXECUTABLE")
            vtool, _ = self.command(label + "-vtool", ["/usr/bin/xcrun", "vtool", "-show-build", str(binary)], 120)
            lipo, _ = self.command(label + "-lipo", ["/usr/bin/xcrun", "lipo", "-archs", str(binary)], 120)
            assessment = assess_native(vtool, lipo, minimum)
            require(file_record(binary, check=self.guard)[0] == before, "BINARY_CHANGED")
            binaries[label] = {"path": binary.relative_to(app).as_posix(), **before, **assessment,
                               "vtoolSha256": digest(vtool), "lipoSha256": digest(lipo)}
        rows, total = [], 0
        for path in files_bounded(app, 8192, 32):
            row = file_record(path, check=self.guard)[0]
            total += row["bytes"]
            require(len(rows) < PRODUCT_FILES and total <= PRODUCT_TOTAL, "PRODUCT_INVENTORY_LIMIT")
            rows.append({"path": path.relative_to(app).as_posix(), **row})
        self.put("product.json", {"scope": SCOPE, "source": self.admitted["source"], "derivedData": str(derived),
                                 "initiallyAbsent": True, "app": str(app), "info": metadata, "binaries": binaries,
                                 "producerInvocationId": self.receipts["xcframework-build"]["id"],
                                 "buildInvocationId": self.receipts["iphoneos-build"]["id"], "nestedInvocationId": self.nested_reuse(),
                                 "files": sorted(rows, key=lambda row: row["path"]),
                                 "generatedProject": file_record(ROOT / "samples/iosApp/p2pkit-sample.xcodeproj/project.pbxproj")[0],
                                 "binaryRetention": "HASH_SIZE_AND_ORIGINAL_NATIVE_INSPECTION_NOT_REDISTRIBUTION"})

    def clean(self):
        self.guard(final=True)
        require(self.context is not None, "NO_CLEANUP_CONTEXT")
        self.retention_barrier()  # Never contingent on output discovery or a later upload/seal.
        preexisting = {Path(name) for name in self.context["preexistingOutputPaths"]}
        targets = [path for path in self.audit.disposable_roots(ROOT) if path not in preexisting and path.exists()]
        derived = self.state / "xcode-deriveddata"
        if derived.exists():
            targets.append(derived)
        if targets:
            self.command("cleanup", [self.admitted["pythonExecutable"], "-B", "-S", str(ROOT / "scripts/run-audit-command.py"),
                                     "cleanup", "--state", str(self.state),
                                     *[arg for path in targets for arg in ("--path", str(path))]], 180, final=True)
            records = sorted((self.state / "evidence").glob("cleanup-*.json"))
            require(len(records) == 2, "CLEANUP_RECORD_COUNT")
            starts = [path for path in records if path.name.endswith("-start.json")]
            require(len(starts) == 1, "CLEANUP_START")
            final_path = starts[0].with_name(starts[0].name.replace("-start.json", ".json"))
            actual = parse(read(final_path))
            require(actual.get("errors") == [] and actual.get("jobId") == self.context["id"] and
                    actual.get("paths") == actual.get("removed") == [str(path) for path in targets], "CLEANUP_RESULT")
            self.copy(starts[0], "cleanup/start.json")
            self.copy(final_path, "cleanup/receipt.json")
        removed = []
        # These are exact descendants allocated under this driver's new root,
        # not arbitrary caches or a recursively discovered directory named build.
        for path in (self.state / "gradle-home", self.state / "konan", self.state / "android-user", self.work / "xcodegen",
                     self.work / "home", self.work / "tmp", *self.fresh_caches):
            self.guard(final=True)
            if path.exists():
                physical(path)
                self.audit.inspect_disposable_tree(path)
                shutil.rmtree(path)
                require(not path.exists(), "CLEANUP_REMAINS")
                removed.append(str(path))
        self.put("cleanup.json", {"result": "COMPLETE", "generatedOutputs": [str(path) for path in targets],
                                  "ownedWorkRemoved": removed, "retirement": "KNOWN",
                                  "leafIds": self.terminal_leaves(for_cleanup=True)})

    def run(self):
        errors, passed, unchanged = [], False, False
        try:
            for number in (signal.SIGINT, signal.SIGTERM):
                previous = signal.getsignal(number)
                self.handlers[number] = previous
                signal.signal(number, lambda signum, _frame: self.cancelled.append(signum))
            self.prerequisites()  # Before any leaf's same-home wrapper stop can bootstrap Gradle.
            self.command("init", [self.admitted["pythonExecutable"], "-B", "-S", str(ROOT / "scripts/run-audit-command.py"), "init",
                                  "--root", str(ROOT), "--state", str(self.state), "--expected-commit",
                                  self.admitted["source"]["commit"], "--host", ROLE], 60)
            self.context_bytes = read(self.state / "context.json")
            self.context = parse(self.context_bytes)
            require(self.context.get("source") == self.admitted["source"] and self.context.get("host") == ROLE and
                    self.context.get("gradleHome") == self.env["GRADLE_USER_HOME"] and
                    self.context.get("preexistingOutputPaths") == [], "INITIAL_CONTEXT")
            self.copy(self.state / "context.json", "context.json")
            self.copy(self.state / "gradle-home/gradle.properties", "gradle-policy.properties")
            self.leaf("xcodegen-install", ["/bin/bash", "scripts/install-xcodegen.sh", str(self.work / "xcodegen")], "command", 900)
            xcodegen = physical(self.work / "xcodegen/bin/xcodegen")
            require(xcodegen.is_file() and os.access(xcodegen, os.X_OK), "XCODEGEN_EXECUTABLE")
            self.env["PATH"] = str(xcodegen.parent) + os.pathsep + self.env["PATH"]
            self.producer()
            self.leaf("xcode-project", [":iosApp:regenerateXcodeProject"], "gradle", 600)
            require(digest(read(ROOT / "samples/iosApp/Info.plist")) == self.initial_info, "REGENERATED_SOURCE")
            project = ROOT / "samples/iosApp/p2pkit-sample.xcodeproj"
            scheme = project / "xcshareddata/xcschemes/p2pkit-sample-ui.xcscheme"
            raw = read(scheme)
            require(b"<!DOCTYPE" not in raw and b"<!ENTITY" not in raw, "SCHEME_XML")
            ET.fromstring(raw)
            self.copy(scheme, "products/p2pkit-sample-ui.xcscheme")
            derived = self.state / "xcode-deriveddata"
            require(not derived.exists() and not derived.is_symlink(), "FRESH_DERIVED_DATA")
            self.leaf("iphoneos-build", xcode_arguments(derived), "command", 7200)
            self.product(derived)
            require(self.audit.source_snapshot(ROOT) == self.admitted["source"], "SOURCE_CHANGED")
            passed = True
        except BaseException as caught:
            errors.append(reason(caught))
        finally:
            # Capture and retirement are independent obligations. In particular,
            # a malformed start or missing log cannot skip all terminal audits.
            try:
                self.retain_leaves()
            except BaseException as caught:
                self.safe = False
                errors.append("RETENTION_" + reason(caught))
            try:
                if self.context is not None or self.attempted_leaves:
                    self.terminal_leaves(for_cleanup=False)
                else:
                    require(not self.state.exists() and not self.state.is_symlink(), "UNPROVED_INIT_PHASE")
            except BaseException as caught:
                self.safe = False
                errors.append("TERMINAL_" + reason(caught))
            try:
                require(self.safe, "UNPROVED_FINALIZATION")
                if self.context is not None:
                    self.clean()
                else:
                    self.guard(final=True)
                    self.retention_barrier()
                    removed = []
                    for path in (self.work / "home", self.work / "tmp"):
                        self.audit.inspect_disposable_tree(path)
                        shutil.rmtree(path)
                        require(not path.exists() and not path.is_symlink(), "CLEANUP_REMAINS")
                        removed.append(str(path))
                    self.put("cleanup.json", {"result": "NO_PRODUCT_STARTED", "retirement": "KNOWN",
                        "generatedOutputs": [], "leafIds": [], "ownedWorkRemoved": removed})
            except BaseException as caught:
                self.safe = False
                passed = False
                errors.append("FINALIZATION_" + reason(caught))
                if not (self.retained / "cleanup.json").exists():
                    self.put("cleanup.json", {"result": "HOLD", "errors": [reason(caught)],
                                              "retirement": "KNOWN" if self.safe else "UNKNOWN"})
            for number, previous in self.handlers.items():
                try:
                    signal.signal(number, previous)
                except BaseException as caught:
                    passed = False
                    errors.append("HANDLER_RESTORATION_" + reason(caught))
        final_source = None
        try:
            final_source = self.audit.source_snapshot(ROOT)
            unchanged = final_source == self.admitted["source"]
            require(unchanged, "FINAL_SOURCE_CHANGED")
        except BaseException as caught:
            passed = False
            errors.append("FINAL_SOURCE_" + reason(caught))
        passed = passed and self.safe and not self.cancelled and not errors and time.monotonic() < self.deadline
        self.put("result.json", {"scope": SCOPE, "admission": self.admitted, "result": "PASS" if passed else "HOLD",
                                 "errors": errors, "retirement": "KNOWN" if self.safe else "UNKNOWN", "sourceUnchanged": unchanged,
                                 "sourceAfter": final_source, "durationSeconds": time.monotonic() - self.entered,
                                 "cancelled": bool(self.cancelled), "commands": sorted(self.commands),
                                 "contextInitialized": self.context is not None, "attemptedLeaves": self.attempted_leaves,
                                 "limits": "No runtime, simulator, phone, signing, installation, publication or release acceptance"})
        require(self.safe, "UNSAFE_EXPORT")
        self.guard(final=True)
        rows = public_inventory(self.retained)
        try:
            validate_result(self.retained, self.admitted, self.audit, self.work, rows,
                            parse(read(self.retained / "result.json")), self.env)
        except BaseException:
            self.safe = False
            raise
        self.guard(final=True)
        write(self.retained / "manifest.json", encoded({"schema": 1, "admission": self.admitted, "files": rows}))
        require(public_inventory(self.retained) == rows, "PUBLIC_FINAL_INVENTORY")
        require(not self.public.exists(), "PUBLIC_EXISTS")
        self.retained.rename(self.public)
        self.guard(final=True)
        require(not passed or not self.cancelled, "LATE_CANCELLATION")
        return 0 if passed else 2


def public_ownership(value, invocation, job, arguments, *, sinks=False):
    require(type(value) is dict and value.get("backend") == "darwin-libproc-audit-token" and
            value.get("scope") == "controlled-marker-inheriting-descendants" and
            value.get("invocation") == invocation and value.get("job") == job and
            value.get("discoveryErrors") == [], "PUBLIC_OWNERSHIP")
    launches = value.get("launches")
    require(type(launches) is list and len(launches) == len(arguments), "PUBLIC_LAUNCH_COUNT")
    for launch, argv in zip(launches, arguments):
        require(type(argv) is list and argv and all(type(arg) is str for arg in argv) and
                Path(argv[0]).is_absolute(), "PUBLIC_LAUNCH_ARGV")
        require(type(launch) is dict and launch.get("requestedArgv") == argv and launch.get("created") is True and
                launch.get("shell") is False and launch.get("cwd") == str(ROOT) and
                type(launch.get("pid")) is int and launch["pid"] > 0 and
                launch.get("resolvedArgv") == argv and launch.get("executable") == argv[0] and
                (launch.get("outputMode") == "caller-owned-files" if sinks else "outputMode" not in launch), "PUBLIC_LAUNCH")


def command_evidence(root, name, admitted, budget, *, allow_failure=True):
    record = parse(read(root / "commands" / name / "record.json"))
    require(record.get("name") == name and name in COMMANDS and record.get("source") == admitted["source"] and
            type(record.get("id")) is str and re.fullmatch(r"[0-9a-f]{32}", record["id"]) and
            type(record.get("jobId")) is str and re.fullmatch(r"[0-9a-f]{32}", record["jobId"]) and
            type(record.get("exitCode")) is int and 0 <= record["exitCode"] <= 255 and record["exitCode"] != 125 and
            (allow_failure or record["exitCode"] == 0) and record.get("errors") == [] and
            record.get("cancelRequested") is False and record.get("retirement") == "KNOWN", "PUBLIC_COMMAND_RESULT")
    require(number(record.get("capSeconds"), COMMAND_CAPS[name]) and record["capSeconds"] >= 0.1 and
            number(record.get("startedMonotonic"), 1e12) and number(record.get("endedMonotonic"), 1e12) and
            budget["enteredMonotonic"] <= record["startedMonotonic"] <= record["endedMonotonic"] < budget["deadlineMonotonic"] and
            record.get("productiveDeadlineMonotonic") == record["startedMonotonic"] + record["capSeconds"] and
            record.get("completionDeadlineMonotonic") == record["productiveDeadlineMonotonic"] + (COMPLETION_SECONDS if record.get("leafId") else 15) and
            record["endedMonotonic"] < record["completionDeadlineMonotonic"] and
            record["completionDeadlineMonotonic"] <= budget["deadlineMonotonic"] - (0 if name == "cleanup" else FINAL_SECONDS) and
            record.get("durationSeconds") == record["endedMonotonic"] - record["startedMonotonic"], "PUBLIC_COMMAND_BUDGET")
    public_ownership(record.get("ownership"), record["id"], record["jobId"], [record.get("argv")], sinks=True)
    outputs = {filename: file_record(root / "commands" / name / filename, limit=LOG_LIMIT)[0]
               for filename in ("stdout.log", "stderr.log")}
    require(record.get("outputs") == outputs, "PUBLIC_COMMAND_OUTPUTS")
    return record


def leaf_evidence(directory, identity, purpose, work, context, audit, *, allow_failure=False):
    require(type(identity) is str and re.fullmatch(r"[0-9a-f]{32}", identity), "PUBLIC_LEAF_ID")
    record = parse(read(directory / "receipt.json"))
    arguments, kind = leaf_arguments(purpose, work), LEAVES[purpose]
    status = record.get("finalExitCode")
    require(type(status) is int and 0 <= status <= 255 and status != 125 and
            (allow_failure or status == 0), "PUBLIC_LEAF_RESULT")
    # The unchanged supplier's exact checker rejects ALL finalization errors,
    # not merely nonempty survivor lists or selected error-message substrings.
    load_script("check-audit-receipt").validate(record, status, purpose, ROOT, ROOT / "gradlew", arguments)
    executed = [str(ROOT / "gradlew"), *audit.gradle_arguments(arguments, reuse_xcframework=purpose == "xcode-provenance")] if kind == "gradle" else arguments
    stop = [str(ROOT / "gradlew"), "--stop", "--console=plain", "--no-parallel", "--max-workers=2",
            "-Dorg.gradle.jvmargs=" + audit.JVM_ARGUMENTS]
    require(record.get("id") == identity and record.get("kind") == kind and record.get("host") == ROLE and
            record.get("jobId") == context["id"] and record.get("gradleHome") == context["gradleHome"] and
            record.get("sourceBefore") == context["source"] and record.get("executedArgv") == executed and
            record.get("stopArgv") == stop and record.get("productLaunchIndex") == 0 and record.get("stopLaunchIndex") == 1 and
            record.get("evidenceDirectory") == str(work / "state/evidence" / identity) and
            not record.get("cancelRequested", False) and not record.get("cancelledSignals", []), "PUBLIC_LEAF_BINDING")
    public_ownership(record.get("ownership"), identity, context["id"], [executed, stop])
    start = parse(read(directory / "start.json"))
    for name in ("schema", "id", "purpose", "kind", "jobId", "host", "gradleHome", "cwd", "wrapper", "requestedArgv",
                 "evidenceDirectory", "startedUtc", "ancestorInvocationIds", "controllerPid"):
        require(start.get(name) == record.get(name) and type(start.get(name)) is type(record.get(name)), "PUBLIC_LEAF_START")
    require(parse(read(directory / "report-manifest.json")) == {
        "schema": 1, "records": record.get("reports"),
        "limitation": "Changed bytes are not proof of test execution; use the unchanged product assessor."}, "PUBLIC_LEAF_REPORTS")
    for name in LEAF_FILES:
        file_record(directory / name, limit=LOG_LIMIT if name.endswith(".log") else META_LIMIT)
    return record


def public_leaf(root, identity, purpose, work, context, audit, *, allow_failure=False):
    require(type(identity) is str and re.fullmatch(r"[0-9a-f]{32}", identity), "PUBLIC_LEAF_ID")
    return leaf_evidence(root / "leaves" / identity, identity, purpose, work, context, audit, allow_failure=allow_failure)


def leaf_controller(command, record, name, admitted, work):
    require(command.get("leafId") == record["id"] and command["exitCode"] == record["finalExitCode"] and
            record.get("ancestorInvocationIds") == [command["id"]], "PUBLIC_LEAF_ANCESTOR")
    argv = command.get("argv")
    require(type(argv) is list and len(argv) >= 22 and argv[:16] == [admitted["pythonExecutable"], "-B", "-S",
            str(ROOT / "scripts/run-audit-command.py"), "--cwd", str(ROOT), "--wrapper", str(ROOT / "gradlew"),
            "--purpose", name, "--kind", LEAVES[name], "--id", record["id"], "--receipt", str(work / "state" / ("host-" + name + ".json"))] and
            argv[16:17] == ["--timeout"] and argv[18:21] == ["--stop-timeout", "120", "--"] and
            argv[21:] == leaf_arguments(name, work) and number(float(argv[17]), COMMAND_CAPS[name]) and
            float(argv[17]) >= command["capSeconds"], "PUBLIC_LEAF_COMMAND")


def public_context(root, admitted, audit, work):
    context = parse(read(root / "context.json"))
    require(context.get("schema") == 1 and context.get("root") == str(ROOT) and context.get("host") == ROLE and
            context.get("source") == admitted["source"] and context.get("expectedCommit") == admitted["source"]["commit"] and
            context.get("tree") == admitted["source"]["tree"] and context.get("preexistingOutputPaths") == [] and
            context.get("gradleHome") == str(work / "state/gradle-home") and
            type(context.get("id")) is str and re.fullmatch(r"[0-9a-f]{32}", context["id"]), "PUBLIC_CONTEXT")
    policy = read(root / "gradle-policy.properties")
    actual_policy, homes = audit.java_policy()
    require(policy == actual_policy and digest(policy) == context.get("gradlePropertiesSha256") and
            context.get("javaHomes") == homes, "PUBLIC_GRADLE_POLICY")
    return context


def public_budget(root):
    budget = parse(read(root / "budget.json"))
    require(budget.get("driverSeconds") == DRIVER_SECONDS and budget.get("leafCompletionSeconds") == COMPLETION_SECONDS and
            budget.get("finalSeconds") == FINAL_SECONDS and number(budget.get("enteredMonotonic"), 1e12) and
            budget.get("deadlineMonotonic") == budget["enteredMonotonic"] + DRIVER_SECONDS, "PUBLIC_BUDGET")
    return budget


def public_sidecars(root, producer):
    raw = read(root / "xcframework-sidecars.json")
    values = {name: read(root / name) for name in SIDECARS}
    manifest = parse(raw)
    require(manifest == {"sourceInvocationId": producer["id"], "files": [
        {"path": name, "sha256": digest(values[name]), "result": "RETAINED"} for name in SIDECARS]}, "PUBLIC_SIDECARS")
    require(values["BUILD_COMMIT.txt"] == (producer["sourceBefore"]["commit"] + "\n").encode("ascii") and
            values["BUILD_SOURCE_STATE.txt"] == b"clean\n" and
            all(re.fullmatch(rb"[0-9a-f]{64}\n", values[name]) for name in SIDECARS[2:]), "PUBLIC_SIDECAR_CONTENT")
    return {"producerInvocationId": producer["id"], "producerReceiptSha256": digest(read(root / "host-xcframework-build.json")),
            "sidecarsManifestSha256": digest(raw), "sidecars": {name: digest(value) for name, value in values.items()}}


def public_toolchains(root):
    value = parse(read(root / "toolchains.json"))
    require(value.get("developerDirectory") == DEVELOPER and
            value.get("macOS") == plistlib.loads(read(root / "toolchains/SystemVersion.plist")).get("ProductVersion") and
            value["macOS"].split(".")[0] == "26" and type(value.get("physicalMemoryBytes")) is int and
            value["physicalMemoryBytes"] >= 6 * GIB, "PUBLIC_TOOLCHAINS")
    for sdk in ("iphoneos", "iphonesimulator"):
        actual = parse(read(root / "toolchains" / (sdk + ".json")))
        recorded = value.get("sdks", {}).get(sdk, {})
        require(type(actual.get("Version")) is str and actual.get("CanonicalName") == sdk + actual["Version"] and
                recorded.get("version") == actual["Version"] and recorded.get("canonicalName") == actual["CanonicalName"] and
                Path(DEVELOPER) in Path(recorded.get("path", "")).parents, "PUBLIC_APPLE_SDK")
    for platform, api in (("android-36", "36"), ("android-37.0", "37.0")):
        raw = read(root / "toolchains" / (platform + ".properties"))
        require(re.findall(rb"^AndroidVersion.ApiLevel=(.+)$", raw, re.M) == [api.encode()] and
                value.get("sdks", {}).get(platform) == {"api": api, "sourcePropertiesSha256": digest(raw)}, "PUBLIC_ANDROID_SDK")
    for label, version in (("java17", "17"), ("java21", "21")):
        jdk = value.get("java", {}).get(label, {})
        require(jdk.get("major") == version and jdk.get("native") is True and
                type(jdk.get("home")) is str and Path(jdk["home"]).is_absolute(), "PUBLIC_JAVA")
        output = read(root / "commands" / label / "stdout.log") + read(root / "commands" / label / "stderr.log")
        require(re.search(rb'\bversion "' + version.encode() + rb'\.', output) and
                re.search(rb"^\s*os.arch = (?:aarch64|arm64)\s*$", output, re.M), "PUBLIC_JAVA_OUTPUT")
    require(read(root / "commands/xcode-version/stdout.log").splitlines()[0] == b"Xcode 26.5" and
            int(read(root / "commands/memory/stdout.log")) == value["physicalMemoryBytes"], "PUBLIC_TOOL_OUTPUT")
    return value


def validate_complete_product(root, admitted, audit, work, rows, result):
    context, budget = public_context(root, admitted, audit, work), public_budget(root)
    toolchains = public_toolchains(root)
    records = {name: command_evidence(root, name, admitted, budget, allow_failure=False) for name in COMMANDS}
    require(result.get("commands") == sorted(COMMANDS), "PUBLIC_COMMAND_SET")
    require(result.get("contextInitialized") is True and result.get("attemptedLeaves") == {
        name: records[name]["leafId"] for name in LEAVES if name != "xcode-provenance"}, "PUBLIC_ATTEMPTED_LEAVES")
    expected_files = set(PUBLIC_FIXED)
    for name in records:
        expected_files.update("commands/" + name + "/" + filename for filename in ("record.json", "stdout.log", "stderr.log"))
    order = list(COMMAND_CAPS)
    require(len({record["id"] for record in records.values()}) == len(COMMANDS) and
            all(records[first]["endedMonotonic"] <= records[second]["startedMonotonic"] for first, second in zip(order, order[1:])) and
            records["cleanup"]["endedMonotonic"] <= budget["enteredMonotonic"] + result["durationSeconds"], "PUBLIC_COMMAND_ORDER")
    leaves = {}
    for name in LEAVES:
        if name == "xcode-provenance":
            continue
        command = records[name]
        record = public_leaf(root, command.get("leafId"), name, work, context, audit)
        leaf_controller(command, record, name, admitted, work)
        leaves[name] = record
    product, observed = parse(read(root / "product.json")), parse(read(root / "producer-product.json"))
    nested = public_leaf(root, product.get("nestedInvocationId"), "xcode-provenance", work, context, audit)
    leaves["xcode-provenance"] = nested
    producer, build = leaves["xcframework-build"], leaves["iphoneos-build"]
    require(read(root / "host-xcframework-build.json") == read(root / "leaves" / producer["id"] / "receipt.json"), "PUBLIC_PRODUCER_COPY")
    binding = public_sidecars(root, producer)
    require(nested.get("ancestorInvocationIds") == [*build["ancestorInvocationIds"], build["id"]] and
            nested.get("xcframeworkReuse") == binding and nested.get("xcframeworkReuseUnchanged") is True, "PUBLIC_NESTED_REUSE")
    require(observed == {"source": admitted["source"], "binding": binding, "binaryPath": str(ROOT / DEVICE_BINARY),
                        "binary": hash_record(observed.get("binary"), nonempty=True),
                        "observation": "AFTER_FRESH_PRODUCER_BEFORE_XCODEBUILD"}, "PUBLIC_PRODUCER_OBSERVATION")
    derived, app = work / "state/xcode-deriveddata", work / "state/xcode-deriveddata" / APP_RELATIVE
    require(product.get("source") == admitted["source"] and product.get("scope") == SCOPE and
            product.get("derivedData") == str(derived) and product.get("app") == str(app) and product.get("initiallyAbsent") is True and
            product.get("producerInvocationId") == producer["id"] and product.get("buildInvocationId") == build["id"] and
            product.get("info") == assess_info(read(root / "products/Info.plist")) and
            plistlib.loads(read(root / "products/Info.plist")).get("DTSDKName") == toolchains["sdks"]["iphoneos"]["canonicalName"], "PUBLIC_PRODUCT")
    assess_framework_info(read(root / "products/framework-Info.plist"))
    hash_record(product.get("generatedProject"), nonempty=True, limit=META_LIMIT)
    scheme = read(root / "products/p2pkit-sample-ui.xcscheme")
    require(b"<!DOCTYPE" not in scheme and b"<!ENTITY" not in scheme, "PUBLIC_SCHEME")
    refs = ET.fromstring(scheme).findall("./BuildAction/BuildActionEntries/BuildActionEntry/BuildableReference")
    require(any(ref.get("BlueprintName") == "p2pkit-sample" and ref.get("BuildableName") == "p2pkit-sample.app" and
                ref.get("ReferencedContainer") == "container:p2pkit-sample.xcodeproj" for ref in refs), "PUBLIC_APP_SCHEME")
    files = product.get("files")
    require(type(files) is list and 1 <= len(files) <= PRODUCT_FILES, "PUBLIC_APP_INVENTORY")
    inventory, total = {}, 0
    for row in files:
        name = row.get("path")
        require(type(name) is str and 0 < len(name) <= 1024 and PurePosixPath(name).as_posix() == name and
                not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and name not in inventory, "PUBLIC_APP_MEMBER")
        inventory[name] = hash_record({key: value for key, value in row.items() if key != "path"})
        total += inventory[name]["bytes"]
    require(list(inventory) == sorted(inventory) and total <= PRODUCT_TOTAL, "PUBLIC_APP_INVENTORY_LIMIT")
    require(inventory.get("Info.plist") == file_record(root / "products/Info.plist")[0] and
            inventory.get("Frameworks/P2pKitShared.framework/Info.plist") == file_record(root / "products/framework-Info.plist")[0], "PUBLIC_APP_PLISTS")
    require(type(product.get("binaries")) is dict and set(product["binaries"]) == {"app", "framework"}, "PUBLIC_BINARIES")
    for label, relative, minimum in (("app", "p2pkit-sample", "15.0"), ("framework", FRAMEWORK_RELATIVE, "14.0")):
        vtool, lipo = read(root / "commands" / (label + "-vtool") / "stdout.log"), read(root / "commands" / (label + "-lipo") / "stdout.log")
        size_hash = hash_record(inventory.get(relative), nonempty=True)
        require(product["binaries"][label] == {"path": relative, **size_hash, **assess_native(vtool, lipo, minimum),
                                             "vtoolSha256": digest(vtool), "lipoSha256": digest(lipo)}, "PUBLIC_NATIVE_PRODUCT")
        if label == "framework":
            require(size_hash == observed["binary"], "PUBLIC_EMBEDDED_PRODUCER")
        for tool, option in (("vtool", "-show-build"), ("lipo", "-archs")):
            require(records[label + "-" + tool].get("argv") == ["/usr/bin/xcrun", tool, option, str(app / relative)], "PUBLIC_NATIVE_COMMAND")
    for name, record in leaves.items():
        expected_files.update("leaves/" + record["id"] + "/" + filename for filename in LEAF_FILES)
    require({row["path"] for row in rows} == expected_files, "PUBLIC_REQUIRED_FILES")
    cleanup = parse(read(root / "cleanup.json"))
    original_cleanup, cleanup_start = parse(read(root / "cleanup/receipt.json")), parse(read(root / "cleanup/start.json"))
    targets = cleanup.get("generatedOutputs")
    allowed = {str(path) for path in audit.disposable_roots(ROOT)} | {str(derived)}
    require(type(targets) is list and len(targets) == len(set(targets)) and set(targets) <= allowed and
            {str(derived), str(ROOT / "samples/iosApp/p2pkit-sample.xcodeproj")} <= set(targets) and
            cleanup.get("result") == "COMPLETE" and cleanup.get("retirement") == "KNOWN" and
            cleanup.get("leafIds") == sorted(record["id"] for record in leaves.values()) and
            original_cleanup.get("jobId") == context["id"] == cleanup_start.get("jobId") and
            original_cleanup.get("id") == cleanup_start.get("id") and original_cleanup.get("errors") == [] and
            original_cleanup.get("paths") == original_cleanup.get("removed") == targets == cleanup_start.get("paths") and
            all(not Path(path).exists() and not Path(path).is_symlink() for path in targets), "PUBLIC_CLEANUP")
    removed = cleanup.get("ownedWorkRemoved")
    owned = {str(work / path) for path in ("state/gradle-home", "state/konan", "state/android-user", "xcodegen", "home", "tmp")}
    owned.update(str(ROOT / path) for path in (".gradle", ".kotlin", "buildSrc/.gradle"))
    require(type(removed) is list and len(removed) == len(set(removed)) and set(removed) <= owned and
            {str(work / path) for path in ("state/gradle-home", "xcodegen", "home", "tmp")} <= set(removed) and
            all(not Path(path).exists() and not Path(path).is_symlink() for path in removed), "PUBLIC_OWNED_CLEANUP")
    expected_native = {"init": [admitted["pythonExecutable"], "-B", "-S", str(ROOT / "scripts/run-audit-command.py"), "init",
                               "--root", str(ROOT), "--state", str(work / "state"), "--expected-commit", admitted["source"]["commit"], "--host", ROLE],
        "xcode-version": ["/usr/bin/xcodebuild", "-version"], "xcode-first-launch": ["/usr/bin/xcodebuild", "-checkFirstLaunchStatus"],
        "memory": ["/usr/sbin/sysctl", "-n", "hw.memsize"],
        "cleanup": [admitted["pythonExecutable"], "-B", "-S", str(ROOT / "scripts/run-audit-command.py"), "cleanup", "--state", str(work / "state"),
                    *[arg for path in targets for arg in ("--path", path)]]}
    expected_native.update({label: [str(Path(toolchains["java"][label]["home"]) / "bin/java"), "-XshowSettings:properties", "-version"]
                            for label in ("java17", "java21")})
    for sdk in ("iphoneos", "iphonesimulator"):
        expected_native[sdk + "-sdk"] = ["/usr/bin/xcrun", "--sdk", sdk, "--show-sdk-path"]
        require(read(root / "commands" / (sdk + "-sdk") / "stdout.log").decode("utf-8").strip() == toolchains["sdks"][sdk]["path"], "PUBLIC_SDK_PATH")
    for name, argv in expected_native.items():
        require(records[name].get("argv") == argv and records[name].get("leafId") is None, "PUBLIC_FIXED_COMMAND")
    pre_job = records["init"].get("jobId")
    require(type(pre_job) is str and re.fullmatch(r"[0-9a-f]{32}", pre_job) and pre_job != context["id"], "PUBLIC_PREINIT_JOB")
    for name in list(COMMAND_CAPS)[:8]:
        require(records[name].get("jobId") == pre_job and records[name].get("state") == str(work) and
                records[name].get("gradleHome") == context["gradleHome"], "PUBLIC_PREINIT_DOMAIN")
    for name in ("xcodegen-install", "xcframework-build", "xcode-project", "iphoneos-build", "app-vtool", "app-lipo", "framework-vtool", "framework-lipo", "cleanup"):
        require(records[name].get("jobId") == context["id"] and records[name].get("state") == str(work / "state") and
                records[name].get("gradleHome") == context["gradleHome"], "PUBLIC_COMMAND_DOMAIN")


def validate_hold(root, admitted, audit, work, rows, result, env):
    """Known-safe partial execution, not a waiver of original-evidence checks.

    Unstarted phases may be absent. Once a controller/leaf is attempted all of
    its original captures and terminal proof are mandatory. Infrastructure or
    cancelled/incomplete leaves are refused even when their survivor lists are
    empty. A fully finalized nonzero product may stop the productive prefix.
    """
    names = result.get("commands")
    require(type(names) is list and all(type(name) is str and name in COMMANDS for name in names) and
            names == sorted(set(names)), "PUBLIC_COMMAND_SET")
    actual_files = {row["path"] for row in rows}
    if names == sorted(COMMANDS) or "product.json" in actual_files:
        # A complete product still needs the identical deep proof when a later
        # driver/source failure causes HOLD instead of PASS.
        validate_complete_product(root, admitted, audit, work, rows, result)
        return
    budget = public_budget(root)
    records = {name: command_evidence(root, name, admitted, budget) for name in names}
    order = [name for name in COMMAND_CAPS if name in records]
    productive = [name for name in order if name != "cleanup"]
    require(productive == list(COMMAND_CAPS)[:len(productive)] and
            all(records[name]["exitCode"] == 0 for name in productive[:-1]) and
            len({record["id"] for record in records.values()}) == len(records) and
            all(records[first]["endedMonotonic"] <= records[second]["startedMonotonic"] for first, second in zip(order, order[1:])) and
            all(record["endedMonotonic"] <= budget["enteredMonotonic"] + result["durationSeconds"] for record in records.values()),
            "PUBLIC_COMMAND_ORDER")
    initialized = result.get("contextInitialized")
    require(type(initialized) is bool and initialized == (records.get("init", {}).get("exitCode") == 0), "PUBLIC_INIT_PHASE")
    context = public_context(root, admitted, audit, work) if initialized else None
    attempted = {name: records[name].get("leafId") for name in LEAVES if name in records}
    require(result.get("attemptedLeaves") == attempted and
            len(set(attempted.values())) == len(attempted) and (context is not None or not attempted), "PUBLIC_ATTEMPTED_LEAVES")
    expected = {"admission.json", "budget.json", "result.json", "cleanup.json"}
    for name in records:
        expected.update("commands/" + name + "/" + filename for filename in ("record.json", "stdout.log", "stderr.log"))
    toolchain_files = {"toolchains.json", "toolchains/SystemVersion.plist", "toolchains/iphoneos.json", "toolchains/iphonesimulator.json",
                       "toolchains/android-36.properties", "toolchains/android-37.0.properties"}
    if "toolchains.json" in actual_files or "init" in records:
        public_toolchains(root)
        expected.update(toolchain_files)
    else:
        # Prerequisite rejection is not supported-toolchain acceptance. Retain
        # only the originals actually reached before rejection; no leaf ran.
        require(context is None, "PUBLIC_TOOLCHAIN_PHASE")
        present = actual_files & toolchain_files
        require(not records or "toolchains/SystemVersion.plist" in present, "PUBLIC_SYSTEM_ORIGINAL")
        if "toolchains/SystemVersion.plist" in present:
            require(type(plistlib.loads(read(root / "toolchains/SystemVersion.plist")).get("ProductVersion")) is str,
                    "PUBLIC_SYSTEM_ORIGINAL")
        for sdk in ("iphoneos", "iphonesimulator"):
            if "toolchains/" + sdk + ".json" in present:
                require(records.get(sdk + "-sdk", {}).get("exitCode") == 0 and
                        type(parse(read(root / "toolchains" / (sdk + ".json")))) is dict, "PUBLIC_SDK_PHASE")
        for platform, api in (("android-36", "36"), ("android-37.0", "37.0")):
            if "toolchains/" + platform + ".properties" in present:
                require(records.get("iphonesimulator-sdk", {}).get("exitCode") == 0 and
                        re.findall(rb"^AndroidVersion.ApiLevel=(.+)$", read(root / "toolchains" / (platform + ".properties")), re.M) ==
                        [api.encode()], "PUBLIC_ANDROID_PHASE")
        expected.update(present)
    if context is not None:
        expected.update(("context.json", "gradle-policy.properties"))
    else:
        require(not (work / "state").exists() and not (work / "state").is_symlink(), "PUBLIC_UNPROVED_INIT")
    leaves = {}
    for name, identity in attempted.items():
        record = public_leaf(root, identity, name, work, context, audit, allow_failure=True)
        leaf_controller(records[name], record, name, admitted, work)
        leaves[name] = record
    binding = None
    producer = leaves.get("xcframework-build")
    if producer is not None and producer["finalExitCode"] == 0:
        require(read(root / "host-xcframework-build.json") == read(root / "leaves" / producer["id"] / "receipt.json"), "PUBLIC_PRODUCER_COPY")
        binding = public_sidecars(root, producer)
        observed = parse(read(root / "producer-product.json"))
        require(observed == {"source": admitted["source"], "binding": binding, "binaryPath": str(ROOT / DEVICE_BINARY),
                "binary": hash_record(observed.get("binary"), nonempty=True),
                "observation": "AFTER_FRESH_PRODUCER_BEFORE_XCODEBUILD"}, "PUBLIC_PRODUCER_OBSERVATION")
        expected.update((*SIDECARS, "host-xcframework-build.json", "xcframework-sidecars.json", "producer-product.json"))
    if leaves.get("xcode-project", {}).get("finalExitCode") == 0:
        scheme = read(root / "products/p2pkit-sample-ui.xcscheme")
        require(b"<!DOCTYPE" not in scheme and b"<!ENTITY" not in scheme, "PUBLIC_SCHEME")
        refs = ET.fromstring(scheme).findall("./BuildAction/BuildActionEntries/BuildActionEntry/BuildableReference")
        require(any(ref.get("BlueprintName") == "p2pkit-sample" and ref.get("BuildableName") == "p2pkit-sample.app" and
                    ref.get("ReferencedContainer") == "container:p2pkit-sample.xcodeproj" for ref in refs), "PUBLIC_APP_SCHEME")
        expected.add("products/p2pkit-sample-ui.xcscheme")
    require(leaves.get("iphoneos-build", {}).get("finalExitCode") != 0, "PUBLIC_INCOMPLETE_PRODUCT_INSPECTION")
    ids = {PurePosixPath(name).parts[1] for name in actual_files if name.startswith("leaves/")}
    nested_ids = ids - set(attempted.values())
    require(len(nested_ids) <= 1 and (not nested_ids or "iphoneos-build" in leaves), "PUBLIC_NESTED_PHASE")
    for identity in nested_ids:
        record = public_leaf(root, identity, "xcode-provenance", work, context, audit, allow_failure=True)
        build = leaves["iphoneos-build"]
        require(binding is not None and record.get("ancestorInvocationIds") == [*build["ancestorInvocationIds"], build["id"]] and
                record.get("xcframeworkReuse") == binding and record.get("xcframeworkReuseUnchanged") is True, "PUBLIC_NESTED_REUSE")
        leaves["xcode-provenance"] = record
    for record in leaves.values():
        expected.update("leaves/" + record["id"] + "/" + filename for filename in LEAF_FILES)
    cleanup = parse(read(root / "cleanup.json"))
    targets, removed = cleanup.get("generatedOutputs"), cleanup.get("ownedWorkRemoved")
    require(type(targets) is list and all(type(path) is str for path in targets) and len(targets) == len(set(targets)) and
            type(removed) is list and all(type(path) is str for path in removed) and len(removed) == len(set(removed)) and
            cleanup.get("retirement") == "KNOWN" and cleanup.get("leafIds") == sorted(record["id"] for record in leaves.values()),
            "PUBLIC_CLEANUP")
    if context is None:
        require(cleanup == {"result": "NO_PRODUCT_STARTED", "retirement": "KNOWN", "generatedOutputs": [], "leafIds": [],
                "ownedWorkRemoved": [str(work / "home"), str(work / "tmp")]} and "cleanup" not in records, "PUBLIC_NO_PRODUCT_CLEANUP")
    else:
        allowed = {str(path) for path in audit.disposable_roots(ROOT)} | {str(work / "state/xcode-deriveddata")}
        require(cleanup.get("result") == "COMPLETE" and set(targets) <= allowed and bool(targets) == ("cleanup" in records) and
                (leaves.get("xcode-project", {}).get("finalExitCode") != 0 or
                 str(ROOT / "samples/iosApp/p2pkit-sample.xcodeproj") in targets), "PUBLIC_CLEANUP")
        owned = {str(work / path) for path in ("state/gradle-home", "state/konan", "state/android-user", "xcodegen", "home", "tmp")}
        owned.update(str(ROOT / path) for path in (".gradle", ".kotlin", "buildSrc/.gradle"))
        required = {str(work / path) for path in ("state/gradle-home", "home", "tmp")}
        if leaves.get("xcodegen-install", {}).get("finalExitCode") == 0:
            required.add(str(work / "xcodegen"))
        require(required <= set(removed) <= owned, "PUBLIC_OWNED_CLEANUP")
        if targets:
            original, start = parse(read(root / "cleanup/receipt.json")), parse(read(root / "cleanup/start.json"))
            require(records["cleanup"]["exitCode"] == 0 and original.get("jobId") == context["id"] == start.get("jobId") and
                    type(original.get("id")) is str and re.fullmatch(r"[0-9a-f]{32}", original["id"]) and
                    original["id"] == start.get("id") and original.get("errors") == start.get("errors") == [] and
                    original.get("paths") == original.get("removed") == targets == start.get("paths") and
                    start.get("removed") == [], "PUBLIC_CLEANUP_ORIGINALS")
            expected.update(("cleanup/start.json", "cleanup/receipt.json"))
    require(all(not Path(path).exists() and not Path(path).is_symlink() for path in [*targets, *removed]), "PUBLIC_OWNED_CLEANUP")
    fixed = {"init": [admitted["pythonExecutable"], "-B", "-S", str(ROOT / "scripts/run-audit-command.py"), "init", "--root", str(ROOT),
                      "--state", str(work / "state"), "--expected-commit", admitted["source"]["commit"], "--host", ROLE],
             "xcode-version": ["/usr/bin/xcodebuild", "-version"], "xcode-first-launch": ["/usr/bin/xcodebuild", "-checkFirstLaunchStatus"],
             "memory": ["/usr/sbin/sysctl", "-n", "hw.memsize"],
             "cleanup": [admitted["pythonExecutable"], "-B", "-S", str(ROOT / "scripts/run-audit-command.py"), "cleanup",
                         "--state", str(work / "state"), *[arg for path in targets for arg in ("--path", path)]]}
    for label, variable in (("java17", "JAVA_HOME"), ("java21", "P2PKIT_AUDIT_JDK21")):
        if label in records:
            home = Path(env.get(variable, ""))
            require(home.is_absolute(), "PUBLIC_JAVA_HOME")
            fixed[label] = [str(home.resolve() / "bin/java"), "-XshowSettings:properties", "-version"]
    for sdk in ("iphoneos", "iphonesimulator"):
        fixed[sdk + "-sdk"] = ["/usr/bin/xcrun", "--sdk", sdk, "--show-sdk-path"]
    pre_job = records[productive[0]]["jobId"] if productive else None
    for name, record in records.items():
        if name not in attempted:
            require(name in fixed and record.get("argv") == fixed[name] and record.get("leafId") is None, "PUBLIC_FIXED_COMMAND")
        pre = name in list(COMMAND_CAPS)[:8]
        require(record.get("jobId") == (pre_job if pre else context["id"]) and
                record.get("state") == str(work if pre else work / "state") and
                record.get("gradleHome") == str(work / "state/gradle-home") and
                (context is None or pre_job != context["id"]), "PUBLIC_COMMAND_DOMAIN")
    require(actual_files == expected, "PUBLIC_REQUIRED_FILES")


def validate_result(root, admitted, audit, work, rows, result, env):
    source = audit.source_snapshot(ROOT)
    require(type(result.get("sourceAfter")) is dict and result["sourceAfter"] == source and
            source.get("commit") == admitted["source"]["commit"] and source.get("tree") == admitted["source"]["tree"] and
            type(result.get("sourceUnchanged")) is bool and result["sourceUnchanged"] == (source == admitted["source"]) and
            number(result.get("durationSeconds"), DRIVER_SECONDS) and type(result.get("errors")) is list and
            all(type(error) is str and 0 < len(error) <= 256 for error in result["errors"]), "PUBLIC_RESULT_SOURCE")
    if result["result"] == "PASS":
        require(result["errors"] == [] and result["sourceUnchanged"] is True and result.get("cancelled") is False, "PUBLIC_PASS_SOURCE")
        validate_complete_product(root, admitted, audit, work, rows, result)
    else:
        require(result["errors"] or result.get("cancelled") is True, "PUBLIC_HOLD_REASON")
        validate_hold(root, admitted, audit, work, rows, result, env)


def validate_public(env, admitted, audit):
    suffix = admitted["runId"] + "-" + admitted["runAttempt"]
    base = physical(Path(env["RUNNER_TEMP"]))
    root, work = base / ("p2pkit-iphoneos-evidence-" + suffix), base / ("p2pkit-iphoneos-work-" + suffix)
    manifest, result = parse(read(root / "manifest.json")), parse(read(root / "result.json"))
    rows = public_inventory(root)
    require(manifest == {"schema": 1, "admission": admitted, "files": rows} and
            parse(read(root / "admission.json")) == admitted == result.get("admission") and result.get("scope") == SCOPE and
            result.get("result") in ("PASS", "HOLD") and result.get("retirement") == "KNOWN" and
            type(result.get("cancelled")) is bool, "PUBLIC_BINDING")
    passed = result["result"] == "PASS"
    require(env.get("P2PKIT_IPHONEOS_RUN_OUTCOME") == "success" if passed else
            env.get("P2PKIT_IPHONEOS_RUN_OUTCOME") in ("failure", "cancelled"), "PUBLIC_RUN_OUTCOME")
    validate_result(root, admitted, audit, work, rows, result, env)
    output = physical(Path(env["GITHUB_OUTPUT"]))
    info = output.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "GITHUB_OUTPUT")
    fd = os.open(output, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
    with fd_stream(fd, "ab") as stream:
        require(os.path.samestat(info, os.fstat(stream.fileno())), "GITHUB_OUTPUT_CHANGED")
        stream.write(b"artifacts_ready=true\nproduct_passed=" + (b"true" if passed else b"false") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return 0


def main():
    entered = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("admit", "run", "validate-public"))
    args = parser.parse_args()
    original = dict(os.environ)
    try:
        environment = build_environment(original)
        os.environ.clear()
        os.environ.update(environment)
        audit = load_script("run-audit-command")
        admitted = admission(original, audit, failure_export=args.operation == "validate-public")
        if args.operation == "admit":
            print("IPHONEOS_RECIPE:DISPATCH_ADMITTED_NOT_TOOLCHAIN_OR_PRODUCT_ACCEPTANCE")
            return 0
        if args.operation == "validate-public":
            return validate_public(original, admitted, audit)
        return Driver(original, admitted, audit, entered).run()
    except BaseException as error:
        code = error.args[0] if isinstance(error, RouteError) else type(error).__name__
        print("IPHONEOS_RECIPE_HOLD:" + str(code), file=sys.stderr)
        return 2
    finally:
        os.environ.clear()
        os.environ.update(original)


if __name__ == "__main__":
    raise SystemExit(main())
