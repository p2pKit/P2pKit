#!/usr/bin/env python3
"""Owned #317/#324 controller primitives, NOT a runtime entrypoint.

There is no CLI, reviewed Mac emulator/image profile or guest lifetime observer.
Do not replace that gap with a caller-provided 'trusted' flag, the Linux Smoke
constructor, an existing AVD, or the historical installed-SDK observations.

The functions below implement the source/receipt, command, installed-byte,
collection and finally boundaries for that future adapter. Their focused tests
substitute commands; the adapter and its exact native prerequisites still need
independent review. Neither this core nor a content-consistent packet
accepts runtime, pixels, mutants, a whole issue, or a physical device.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PACKAGE = "dev.p2pkit.sample.android"
PACKAGES = (PACKAGE, PACKAGE + ".test")
CASES = {"317": ("UiAcceptanceInstrumentation", 180), "324": ("CredentialUiInstrumentation", 240)}
MIB = 1024 * 1024
STREAM_LIMIT, METADATA_LIMIT, APK_LIMIT = 8 * MIB, MIB, 512 * MIB
COPY_CHUNK = 64 * 1024
COLLECTION_SECONDS = 120
COMMAND_LIMIT = 4096


class Rejected(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise Rejected(message)


def load_tool(filename):
    """Only adjacent, source-bound tools; never import a path from an input."""
    need(filename in ("run-audit-command.py", "check-audit-receipt.py", "audit_processes.py",
                      "verify-android-acceptance-artifacts.py", "run-android-art-smoke.py",
                      "verify-android-ui-evidence.py"), "Not a maintained controller dependency")
    # The maintained executor imports its adjacent ownership module. Do not
    # resolve that import from an ambient helper directory.
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("android_ui_" + filename.replace("-", "_").replace(".", "_"),
                                                  SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checked_case_token(case, token):
    need(case in CASES and type(token) is str and re.fullmatch(r"[0-9a-f]{32}", token), "Wrong UI case/token")


def checked_identity(case, token, source):
    checked_case_token(case, token)
    need(type(source) is dict and all(type(source.get(key)) is str and
         re.fullmatch(r"[0-9a-f]{40}", source[key]) for key in ("commit", "tree")), "Wrong UI source identity")


def instrument_arguments(case, token, source):
    checked_identity(case, token, source)
    return ["shell", "am", "instrument", "--user", "0", "-w", "-r", "-e", "case", case,
            "-e", "token", token, "-e", "sourceCommit", source["commit"], "-e", "sourceTree", source["tree"],
            PACKAGE + ".test/" + PACKAGE + ".runtime." + CASES[case][0]]


def instrument(guest, case, token, source):
    return guest.adb("ui-instrumentation", instrument_arguments(case, token, source),
                     seconds=CASES[case][1], limit=STREAM_LIMIT)


def purpose(value):
    need(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", value), "Wrong receipt purpose")
    return value


def canonical_receipt(runner, artifacts, state, path):
    path = runner.absolute_path(str(path))
    need(runner.within(path, state), "Receipt is outside the owned state")
    binding, raw = artifacts.fingerprint(path, runner.MAX_JSON_BYTES, True)
    receipt = runner.read_json(path)
    need(type(receipt.get("id")) is str and re.fullmatch(r"[0-9a-f]{32}", receipt["id"]), "Wrong receipt identity")
    canonical = state / "evidence" / receipt["id"] / "receipt.json"
    other, canonical_raw = artifacts.fingerprint(canonical, runner.MAX_JSON_BYTES, True)
    need(binding == other and raw == canonical_raw and receipt == runner.read_json(canonical),
         "Receipt differs from its finalized canonical original")
    need(receipt.get("evidenceDirectory") == str(canonical.parent), "Wrong canonical evidence directory")
    return receipt, binding


def admit_inspection_receipt(checker, receipt, context, root, build_path, build_purpose, inspection_purpose):
    """The inspector's provisional label alone has no execution authority."""
    argv = receipt.get("requestedArgv")
    need(type(argv) is list and len(argv) in (6, 9) and
         argv[0] in ("python3", "/usr/bin/python3", sys.executable), "Wrong actual APK inspection interpreter")
    script_index = 4 if len(argv) == 9 else 1
    need((script_index == 1 or argv[1:4] == ["-I", "-B", "-S"]) and
         argv[script_index] in ("scripts/verify-android-acceptance-artifacts.py",
                                str(root / "scripts/verify-android-acceptance-artifacts.py")) and
         argv[script_index + 1:] == ["--build-receipt", str(build_path), "--build-purpose", build_purpose],
         "Wrong actual APK inspection request")
    checker.validate(receipt, 0, inspection_purpose, root, root / "gradlew", argv)
    need(receipt.get("executedArgv") == argv and receipt.get("kind") == "command" and
         receipt.get("jobId") == context["id"] and receipt.get("host") == context["host"] and
         receipt.get("gradleHome") == context["gradleHome"] and receipt.get("sourceBefore") == context["source"],
         "Inspection belongs to another source/state/host or command")


def admit_outer(runner, processes, state, context, root, environment):
    """Validate the maintained active command domain, not a self-issued receipt."""
    actual_state, actual_context = runner.context_at(str(state))
    need(actual_state == state and actual_context == context, "Context differs from maintained native admission")
    need(context["root"] == str(root) and context["host"] == "macos-arm64" and
         runner.source_snapshot(root) == context["source"], "Wrong/changed native Mac source")
    chain = environment.get(processes.CHAIN_ENV, "")
    domains = processes.ownership_domains(chain, environment.get(processes.DOMAINS_ENV, ""))
    need(domains and domains[-1] == {"id": chain.split(":")[-1], "job": context["id"],
                                   "state": str(state), "home": context["gradleHome"]},
         "Missing/mismatched active ownership domain")
    need(environment.get(processes.JOB_ENV) == context["id"] and
         environment.get(processes.STATE_ENV) == str(state) and
         environment.get("GRADLE_USER_HOME") == context["gradleHome"], "Ambient ownership differs")
    identifier = domains[-1]["id"]
    owner = runner.read_json(state / "evidence" / identifier / "start.json")
    need(owner.get("id") == identifier and owner.get("jobId") == context["id"] and
         owner.get("kind") == "command" and owner.get("cwd") == str(root) and
         owner.get("wrapper") == str(root / "gradlew") and
         owner.get("gradleHome") == context["gradleHome"] and owner.get("host") == context["host"] and
         owner.get("ancestorInvocationIds") == chain.split(":")[:-1] and
         not (state / "evidence" / identifier / "receipt.json").exists(), "No active immutable command owner")
    return identifier


def new_fixture(runner, state):
    """Exclusive allocation only, not resource/lease/native admission or cleanup."""
    path = state / "fixtures"
    runner.reject_symlinks(path)
    path.mkdir(mode=0o700)  # No exist_ok, fallback, reuse or adoption.
    info = path.lstat()
    runner.write_new_json(path / "directory-identity.json",
                          {"path": str(path), "device": info.st_dev, "inode": info.st_ino})
    return path


def require_empty_server(raw):
    need(type(raw) is bytes and raw in (b"List of devices attached\n", b"List of devices attached\n\n"),
         "Private adb server is not initially empty or its observation is unsupported")


def intake(runner, checker, artifacts, manifests, state, context, root, args):
    """Recheck the existing producer/inspector bytes; no build, SDK or guest call.

    This composes the maintained map/file/manifest validators, not a second map
    parser. The inspector directory is exclusively created by its source-qualified
    command. Its original stdout must name that directory's result; its now-final
    canonical receipt, maps, generated/packaged bytes and source must all agree.
    """
    build_path = runner.absolute_path(str(args.build_receipt))
    build, build_binding = canonical_receipt(runner, artifacts, state, build_path)
    artifacts.admit_build_receipt(checker, build, build, context, root, purpose(args.build_purpose))
    need(build.get("executedArgv") == [str(root / "gradlew"), *runner.gradle_arguments(build["requestedArgv"])],
         "Producer did not execute the maintained fresh strict request")
    inspection, inspection_binding = canonical_receipt(runner, artifacts, state, args.inspection_receipt)
    need(inspection["id"] != build["id"], "Producer and inspector cannot be one leaf")
    admit_inspection_receipt(checker, inspection, context, root, build_path, args.build_purpose,
                             purpose(args.inspection_purpose))
    evidence = state / "evidence/android-acceptance-artifacts"
    result_path = evidence / "result.json"
    result_binding, _ = artifacts.fingerprint(result_path, runner.MAX_JSON_BYTES, True)
    result = runner.read_json(result_path)
    need(result.get("status") == "ARTIFACTS_VERIFIED_PENDING_OUTER_RECEIPT" and
         result.get("source") == result.get("sourceAfter") == context["source"] and result.get("errors") == [] and
         result.get("runtime") == "NOT_RUN" and result.get("producerId") == build["id"] and
         result.get("producerPurpose") == args.build_purpose, "Inspection result differs from its completed source")
    printed = artifacts.fingerprint(Path(inspection["evidenceDirectory"]) / "product.stdout.log", STREAM_LIMIT, True)[1]
    need(printed == (str(result_path) + "\n").encode(), "Final inspector stdout did not identify this result")
    raw_map = artifacts.retained_report(state, build, artifacts.MAP_PATH, artifacts.MAP_LIMIT)
    data = json.loads(raw_map, object_pairs_hook=runner.unique_object,
                      parse_constant=lambda _: need(False, "Nonfinite producer map"))
    artifacts.validate_map(data)
    for path in (root / artifacts.MAP_PATH, evidence / "producer-map.json"):
        need(artifacts.fingerprint(path, artifacts.MAP_LIMIT, True)[1] == raw_map, "Producer map changed")
    need(result.get("producerMapSha256") == hashlib.sha256(raw_map).hexdigest() and
         result.get("apks") == {role: data["components"][role]["apk"] for role in ("app", "test")},
         "Inspector map/APK binding differs")
    generated, packaged, retained_bindings = {}, {}, {"result.json": result_binding}
    for role in ("app", "test"):
        component = data["components"][role]
        manifest, apk = component["manifest"], component["apk"]
        raw = artifacts.retained_report(state, build, manifest["retainedPath"], artifacts.MANIFEST_LIMIT)
        need(raw == artifacts.verified_file(root, manifest["sourcePath"], manifest, artifacts.MANIFEST_LIMIT, True) ==
             artifacts.verified_file(root, manifest["retainedPath"], manifest, artifacts.MANIFEST_LIMIT, True),
             "Generated/retained manifest changed")
        copied_binding, copied = artifacts.fingerprint(evidence / (role + "-generated.xml"), artifacts.MANIFEST_LIMIT, True)
        need(copied == raw, "Inspector generated XML differs")
        generated[role] = raw
        retained_bindings[role + "-generated.xml"] = copied_binding
        retained_bindings[role + "-packaged.xml"], packaged[role] = artifacts.fingerprint(
            evidence / (role + "-packaged.xml"), artifacts.MANIFEST_LIMIT, True)
        artifacts.verified_file(root, apk["path"], apk, artifacts.APK_LIMIT)
    need(result.get("manifestIdentities") == manifests.matching_manifest_identities(
        generated["app"], generated["test"], packaged["app"], packaged["test"]), "Inspector manifest identities differ")
    commands = result.get("commands")
    analyzer = result.get("apkanalyzer", {})
    need(type(analyzer) is dict and set(analyzer) == {"path", "bytes", "sha256"} and
         type(analyzer.get("path")) is str and Path(analyzer["path"]).is_absolute() and
         type(analyzer.get("bytes")) is int and 0 < analyzer["bytes"] <= artifacts.MANIFEST_LIMIT and
         type(analyzer.get("sha256")) is str and re.fullmatch(r"[0-9a-f]{64}", analyzer["sha256"]),
         "Missing actual manifest inspector binding")
    need(type(commands) is list and len(commands) == 2, "Missing actual APK inspection commands")
    for role, command in zip(("app", "test"), commands):
        need(type(command) is dict and command.get("argv") ==
             [analyzer["path"], "manifest", "print", str(root / data["components"][role]["apk"]["path"])] and
             type(command.get("exitCode")) is int and command["exitCode"] == 0 and command.get("timeoutSeconds") == 60 and
             type(command.get("startedUtc")) is str and type(command.get("endedUtc")) is str,
             "Inspector did not complete both exact APK commands")
    # Recheck originals after admission. No caller-written installed/complete flag is read.
    need(canonical_receipt(runner, artifacts, state, build_path)[1] == build_binding and
         canonical_receipt(runner, artifacts, state, args.inspection_receipt)[1] == inspection_binding and
         artifacts.fingerprint(result_path, runner.MAX_JSON_BYTES)[0] == result_binding,
         "Receipt/inspection result changed during intake")
    return {"producer": build, "inspection": inspection, "map": data,
            "bindings": {"producerReceipt": build_binding, "inspectionReceipt": inspection_binding,
                         "inspectionFiles": retained_bindings},
            "apks": {role: root / data["components"][role]["apk"]["path"] for role in ("app", "test")}}


class Commands:
    """Original command streams, actual exit AND EOF; no process-name cleanup.

    The future adapter must construct this inside admit_outer's domain and retain
    the shared execution lease. Descendants inherit that domain. On timeout the
    prefix and unresolved handle survive in evidence; only the maintained outer
    executor may identity-drain them. No local timeout is turned into exit zero.
    """
    def __init__(self, runner, evidence, root, environment):
        self.runner, self.evidence, self.root = runner, evidence, root
        self.environment = dict(environment)
        self.children = []
        self.records = []

    def run(self, label, argv, seconds=40, limit=STREAM_LIMIT, destination=None):
        need(type(label) is str and re.fullmatch(r"[a-z0-9-]{1,80}", label), "Unsafe command label")
        need(type(argv) is list and argv and all(type(value) is str and "\0" not in value for value in argv),
             "Invalid command vector")
        need(0 < seconds <= 240 and 0 <= limit <= APK_LIMIT and len(self.records) < COMMAND_LIMIT,
             "Command bound exceeded")
        stem = f"{len(self.records) + 1:04d}-{label}"
        out = self.evidence / (stem + ".stdout") if destination is None else destination
        err = self.evidence / (stem + ".stderr")
        need(all(path.is_absolute() and ".." not in path.parts and self.runner.within(path, self.evidence)
                 for path in (out, err)),
             "Command originals must remain in this private evidence directory")
        record = {"argv": list(argv), "startedUtc": self.runner.utc(), "timeoutSeconds": seconds,
                  "stdout": str(out), "stderr": str(err), "exitCode": None,
                  "stdoutEof": False, "stderrEof": False, "errors": [], "retention": "PARTIAL"}
        self.records.append(record)
        child, selector = None, None
        streams = []
        counts = {"stdout": 0, "stderr": 0}
        try:
            selector = selectors.DefaultSelector()
            deadline = time.monotonic() + seconds
            with self.runner.new_file(out) as stdout, self.runner.new_file(err) as stderr:
                child = subprocess.Popen(argv, cwd=self.root, env=self.environment, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, bufsize=0)
                self.children.append(child)
                record["pid"] = child.pid
                streams = [child.stdout, child.stderr]
                for name, pipe, target, bound in (("stdout", child.stdout, stdout, limit),
                                                   ("stderr", child.stderr, stderr, STREAM_LIMIT)):
                    os.set_blocking(pipe.fileno(), False)
                    selector.register(pipe, selectors.EVENT_READ, (name, target, bound))
                while selector.get_map() or child.poll() is None:
                    need(time.monotonic() < deadline, "Command deadline: " + label)
                    for key, _ in selector.select(min(0.1, max(0, deadline - time.monotonic()))):
                        name, target, bound = key.data
                        block = os.read(key.fileobj.fileno(), COPY_CHUNK)
                        if not block:
                            record[name + "Eof"] = True
                            selector.unregister(key.fileobj)
                            continue
                        # Retain the actual last block too; an over-bound prefix
                        # stays explicitly partial, never truncated to a valid file.
                        target.write(block)
                        target.flush()
                        counts[name] += len(block)
                        need(counts[name] <= bound, "Command output bound: " + name)
                record["exitCode"] = child.poll()
                for target in (stdout, stderr):
                    target.flush()
                    os.fsync(target.fileno())
                record["retention"] = "COMPLETE_STREAMS"
        except BaseException as error:
            record["errors"].append(type(error).__name__ + ": " + str(error))
            raise
        finally:
            record["endedUtc"] = self.runner.utc()
            record["bytes"] = counts
            if child is not None:
                try:
                    record["exitCode"] = child.poll()
                except BaseException as error:
                    record["errors"].append("Exit observation: " + type(error).__name__ + ": " + str(error))
            for pipe in streams:
                try:
                    pipe.close()
                except BaseException as error:
                    record["errors"].append("Pipe close: " + type(error).__name__ + ": " + str(error))
            if selector is not None:
                try:
                    selector.close()
                except BaseException as error:
                    record["errors"].append("Selector close: " + type(error).__name__ + ": " + str(error))
            self.runner.write_new_json(self.evidence / (stem + ".json"), record)
        return record

    def settlement(self):
        """A later observation; do not rewrite the original command/timeout."""
        return [{"pid": child.pid, "exitCode": child.poll()} for child in self.children]


def completed(record):
    need(type(record.get("exitCode")) is int and record["exitCode"] == 0 and record.get("stdoutEof") is True and
         record.get("stderrEof") is True and record.get("errors") == [] and
         record.get("retention") == "COMPLETE_STREAMS", "Command did not complete successfully with both EOFs")
    return record


def command_output(record, limit, *, keep=False, bound=None):
    """Identity-stable bounded originals; zero-byte files are legitimate inputs."""
    completed(record)
    need(type(limit) is int and 0 <= limit <= APK_LIMIT, "Invalid original command read bound")
    path = Path(record["stdout"])
    need(path.is_absolute() and ".." not in path.parts, "Unsafe original command stdout path")
    for part in (path, *path.parents):
        need(not stat.S_ISLNK(part.lstat().st_mode), "Linked original command stdout path")
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
         "Missing/aliased/oversized original command stdout")
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    hasher, total, chunks = hashlib.sha256(), 0, []
    with os.fdopen(os.open(path, flags), "rb") as stream:
        need(identity(os.fstat(stream.fileno())) == identity(before), "Original stdout changed before read")
        while True:
            if bound is not None:
                bound()
            block = stream.read(min(COPY_CHUNK, limit - total + 1))
            if not block:
                break
            total += len(block)
            need(total <= limit, "Original stdout grew beyond its bound")
            hasher.update(block)
            if keep:
                chunks.append(block)
        need(identity(os.fstat(stream.fileno())) == identity(before), "Original stdout changed during read")
    need(total == before.st_size <= limit and identity(path.lstat()) == identity(before),
         "Original command output changed or exceeded its read bound")
    return {"bytes": total, "sha256": hasher.hexdigest()}, b"".join(chunks) if keep else None


def command_bytes(record, limit):
    return command_output(record, limit, keep=True)[1]


class PrivateAdb:
    """Narrow commands for a future adapter's fresh owned foreground server.

    This does NOT admit the supplied SDK, process handles, AVD or runtime. There
    is intentionally no production constructor call until that missing adapter
    is reviewed. No port, serial, executable or existing guest is a CLI input.
    """
    def __init__(self, commands, sdk, port, serial, server, emulator, case, token):
        checked_case_token(case, token)
        need(Path(sdk).is_absolute() and type(port) is int and 1024 <= port <= 65535 and
             type(serial) is str and re.fullmatch(r"emulator-[0-9]{4,5}", serial), "Invalid private adb selection")
        self.commands, self.sdk, self.port, self.serial = commands, Path(sdk), port, serial
        self.server, self.emulator = server, emulator
        self.remote = "no_backup/ui-" + case + "-" + token

    def adb(self, label, arguments, seconds=40, limit=STREAM_LIMIT, destination=None):
        need(self.server is not None and self.server.poll() is None, "Owned foreground adb server is not live")
        record = self.commands.run(label, [str(self.sdk / "platform-tools/adb"), "-P", str(self.port),
                                           "-s", self.serial, *arguments], seconds, limit, destination)
        need(self.server.poll() is None, "Owned foreground adb server exited; do not adopt its replacement")
        return record

    def run_as(self, label, arguments, seconds=40, limit=STREAM_LIMIT, destination=None):
        need(type(arguments) is list and arguments and all(type(value) is str for value in arguments),
             "Malformed guest collector command")
        prefix, path = arguments[:-1], arguments[-1]
        need(prefix in (["stat", "-c", STAT_FORMAT], ["ls", "-1a"], ["cat"]),
             "Not an exact read-only guest collector command")
        need(path == "no_backup" and prefix == ["stat", "-c", STAT_FORMAT] or
             (path == self.remote or path.startswith(self.remote + "/")) and
             all(re.fullmatch(r"[A-Za-z0-9._-]{1,200}", part) and part not in (".", "..")
                 for part in path.split("/")), "Collector path is not the exact owned UI tree")
        # adb's exec service accepts a shell command. Quote every generated token;
        # never interpolate a listing or accept an arbitrary private app root.
        remote = shlex.join(["run-as", PACKAGE, "/system/bin/toybox", *arguments])
        return self.adb(label, ["exec-out", remote], seconds, limit, destination)


def package_paths(raw):
    lines = raw.decode("ascii").splitlines()
    need(len(lines) == 1 and re.fullmatch(r"package:/data/app/[A-Za-z0-9_./+=~-]+/base\.apk", lines[0]),
         "Missing/ambiguous installed base APK")
    path = lines[0][len("package:"):]
    need(all(part not in ("", ".", "..") for part in path.split("/")[1:]), "Unsafe installed APK path")
    return path


def package_uids(raw):
    rows = {}
    for line in raw.decode("ascii").splitlines():
        match = re.fullmatch(r"package:([A-Za-z0-9_.]+) uid:([0-9]{1,10})", line)
        need(match and match[1] not in rows, "Malformed/duplicate package UID observation")
        rows[match[1]] = int(match[2])
    need(rows and len(rows) <= 4096, "Missing/excessive package UID inventory")
    return rows


def installed_pair(guest, artifacts, root, bundle, evidence):
    """Observe actual User0 packages and read back both complete installed APKs.

    The adapter must have installed each admitted APK without -g, after proving
    the packages absent in its fresh guest. This function never treats an install
    command's exit0, a supplied hash string or the manifest alone as installed bytes.
    """
    need(command_bytes(guest.adb("installed-user", ["shell", "am", "get-current-user"]), 32).strip() == b"0",
         "UI acceptance requires the actual User0 install")
    listing = command_bytes(guest.adb("installed-packages", ["shell", "pm", "list", "packages", "--user", "0", "-U"]),
                            METADATA_LIMIT)
    uids = package_uids(listing)
    result = {}
    for role, package in zip(("app", "test"), PACKAGES):
        need(package in uids and 10000 <= uids[package] < 100000 and list(uids.values()).count(uids[package]) == 1,
             "Missing/User0-invalid/shared installed UID")
        dump = command_bytes(guest.adb(role + "-installed-package", ["shell", "dumpsys", "package", package]),
                             STREAM_LIMIT).decode("utf-8")
        target = re.findall(r"(?m)^\s*versionCode=[0-9]+\s+minSdk=[0-9]+\s+targetSdk=([0-9]+)\s*$", dump)
        installed = re.findall(r"(?m)^\s*User 0: .*\binstalled=(true|false)\b.*$", dump)
        need(target == ["37"] and installed == ["true"], "Actual package target/User0 install not established")
        arguments = ["shell", "pm", "path", "--user", "0", package]
        path = package_paths(command_bytes(guest.adb(role + "-installed-path", arguments), METADATA_LIMIT))
        destination = evidence / (role + "-installed.apk")
        record = guest.adb(role + "-installed-bytes", ["exec-out", shlex.join(["cat", path])],
                           seconds=120, limit=APK_LIMIT, destination=destination)
        completed(record)
        description = bundle["map"]["components"][role]["apk"]
        actual = artifacts.fingerprint(destination, APK_LIMIT)[0]
        need(actual == {key: description[key] for key in ("bytes", "sha256")}, "Installed APK differs from its producer")
        need(package_paths(command_bytes(guest.adb(role + "-installed-path-after", arguments), METADATA_LIMIT)) == path,
             "Installed APK path changed during readback")
        artifacts.verified_file(root, description["path"], description, APK_LIMIT)
        result[package] = {"uid": uids[package], "path": path, "targetSdk": 37, "user": 0,
                           "retained": str(destination), **actual}
    need(package_uids(command_bytes(guest.adb("installed-packages-after",
        ["shell", "pm", "list", "packages", "--user", "0", "-U"]), METADATA_LIMIT)) == uids,
         "Package UID inventory changed during readback")
    return result


def directory_names(raw):
    need(len(raw) <= METADATA_LIMIT and raw.endswith(b"\n"), "Incomplete/oversized guest directory listing")
    names = raw.decode("ascii").splitlines()
    need(len(names) <= 322 and len(names) == len(set(names)) and names.count(".") == names.count("..") == 1,
         "Ambiguous guest directory membership")
    need(all(re.fullmatch(r"[A-Za-z0-9._-]{1,200}", name) for name in names), "Unsafe guest directory name")
    return sorted(name for name in names if name not in (".", ".."))


STAT_FORMAT = "%d|%i|%f|%h|%u|%s|%Y|%Z"


def guest_stat(raw, uid):
    need(type(uid) is int and 10000 <= uid < 100000 and len(raw) <= 1024, "Invalid guest stat bound/UID")
    values = raw.decode("ascii").strip().split("|")
    need(len(values) == 8 and all(re.fullmatch(r"[0-9]{1,20}", value) for i, value in enumerate(values) if i != 2) and
         re.fullmatch(r"[0-9a-fA-F]{1,8}", values[2]), "Unsupported guest stat observation")
    device, inode, mode, links, owner, size, mtime, ctime = (
        int(value, 16 if i == 2 else 10) for i, value in enumerate(values))
    need(inode > 0 and owner == uid and (stat.S_ISREG(mode) or stat.S_ISDIR(mode)),
         "Foreign/unidentified/link/special guest entry")
    need(links == 1 if stat.S_ISREG(mode) else links >= 1, "Aliased guest regular file")
    return {"device": device, "inode": inode, "mode": mode, "links": links,
            "uid": owner, "bytes": size, "mtimeSeconds": mtime, "ctimeSeconds": ctime}


class Collector:
    """Bounded whole-tree originals, including unknown safe names and empty dirs.

    No 'complete' input or guest-declared file list is trusted. Retention completion
    comes from successful EOF/count/stat/listing checks. It is not ART quiescence:
    the adapter must independently prove that before calling the final collection.
    Pre-retirement snapshots remain separately labeled even if internally stable.
    These are exclusive-owned/quiescent-tree checks, not hostile atomic reads.
    """
    def __init__(self, runner, guest, verifier, evidence, case, token, uid, phase):
        checked_case_token(case, token)
        need(phase in ("before-retirement-partial", "after-retirement"), "Unknown collection phase")
        self.runner, self.guest, self.verifier = runner, guest, verifier
        self.evidence, self.case, self.uid, self.phase = evidence, case, uid, phase
        self.remote = "no_backup/ui-" + case + "-" + token
        self.parent = evidence / phase
        self.local = self.parent / self.remote.split("/")[1]
        self.deadline = time.monotonic() + COLLECTION_SECONDS
        self.total, self.last_inventory = 0, {}

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        need(remaining > 0, "Guest collection deadline")
        return min(40, remaining)

    def observe(self, relative):
        path = self.remote if relative == "." else self.remote + "/" + relative
        record = self.guest.run_as("ui-stat", ["stat", "-c", STAT_FORMAT, path],
                                   seconds=self.remaining(), limit=1024)
        return guest_stat(command_bytes(record, 1024), self.uid)

    def names(self, relative):
        path = self.remote if relative == "." else self.remote + "/" + relative
        return directory_names(command_bytes(self.guest.run_as("ui-membership", ["ls", "-1a", path],
                               seconds=self.remaining(), limit=METADATA_LIMIT), METADATA_LIMIT))

    def inventory(self):
        rows, inodes, pending, files, directories = {}, set(), [(".", 0)], 0, 0
        self.last_inventory = rows
        parent = guest_stat(command_bytes(self.guest.run_as("ui-parent-stat",
            ["stat", "-c", STAT_FORMAT, "no_backup"], seconds=self.remaining(), limit=1024), 1024), self.uid)
        need(stat.S_ISDIR(parent["mode"]), "Evidence parent is not a physical directory")
        while pending:
            relative, depth = pending.pop()
            info = self.observe(relative)
            need(info["device"] == parent["device"] and (info["device"], info["inode"]) not in inodes,
                 "Cross-device/aliased guest graph")
            inodes.add((info["device"], info["inode"]))
            row = {"stat": info}
            rows[relative] = row
            if stat.S_ISDIR(info["mode"]):
                directories += 1
                need(depth <= self.verifier.DEPTH_LIMIT and directories <= self.verifier.DIRECTORY_LIMIT,
                     "Guest directory depth/count limit")
                row["names"] = self.names(relative)
                need(len(rows) + len(pending) + len(row["names"]) <=
                     self.verifier.FILE_LIMIT + self.verifier.DIRECTORY_LIMIT, "Guest graph entry limit")
                for name in reversed(row["names"]):
                    pending.append((name if relative == "." else relative + "/" + name, depth + 1))
                need(self.observe(relative) == info, "Guest directory changed during listing")
            else:
                need(relative != ".", "Guest evidence root is not a directory")
                files += 1
                need(files <= self.verifier.FILE_LIMIT, "Guest file count limit")
        return parent, rows

    def collect(self):
        result = {"phase": self.phase, "status": "INCOMPLETE", "remote": self.remote,
                  "retainedRoot": str(self.local), "files": [], "directories": [], "errors": [],
                  "artRetirement": "NOT_ESTABLISHED_BY_COLLECTOR"}
        self.runner.reject_symlinks(self.parent)
        self.parent.mkdir(mode=0o700)  # Never adopt a prior partial snapshot.
        try:
            before_parent, before = self.inventory()
            result["before"] = before
            need(stat.S_ISDIR(before["."]["stat"]["mode"]), "Guest evidence root is not a directory")
            self.local.mkdir(mode=0o700)
            for relative, row in sorted(before.items(), key=lambda item: (item[0].count("/"), item[0])):
                info = row["stat"]
                if stat.S_ISDIR(info["mode"]):
                    if relative != ".":
                        (self.local / relative).mkdir(mode=0o700)
                    result["directories"].append(relative)
                    continue
                # Unknown safe names are preserved, not filtered to the verifier's
                # allowlist. That verifier must reject them independently.
                limit = self.verifier.PNG_LIMIT if relative.endswith(".png") else (
                    self.verifier.PARCEL_LIMIT if relative.endswith(".parcel") else self.verifier.TEXT_LIMIT)
                need(info["bytes"] <= limit and self.total + info["bytes"] <= self.verifier.TOTAL_LIMITS[self.case],
                     "Guest retained byte budget exceeded; original remains in the owned guest")
                need(self.observe(relative) == info, "Guest file changed before read")
                destination = self.local / relative
                retained_row = {"path": relative, "expectedBytes": info["bytes"],
                                "commandStdout": str(destination), "readOutcome": "INCOMPLETE"}
                result["files"].append(retained_row)
                record = self.guest.run_as("ui-file", ["cat", self.remote + "/" + relative],
                                           seconds=self.remaining(), limit=limit, destination=destination)
                need(record.get("stdout") == str(destination), "Collector command retained another path")
                retained_row.update(command_output(record, limit, bound=self.remaining)[0])
                self.total += retained_row["bytes"]
                need(retained_row["bytes"] == info["bytes"] and self.observe(relative) == info,
                     "Short/changed guest file read")
                retained_row["readOutcome"] = "COMPLETE"
            after_parent, after = self.inventory()
            result["after"] = after
            need(before_parent == after_parent and before == after, "Guest membership/identity changed during capture")
            result["status"] = "RETAINED_STABLE_GRAPH"  # Not an ART or UI acceptance label.
        except BaseException as error:
            result["errors"].append(type(error).__name__ + ": " + str(error))
            raise
        finally:
            result["totalFileBytes"] = self.total
            result["lastInventory"] = self.last_inventory
            self.runner.write_new_json(self.parent / "collection.json", result)
        return result


def attempt_all(runner, evidence, actions):
    """Finally primitive: every action is attempted even after BaseException.

    Actions are source-owned operations, never input-supplied commands/statuses.
    This does not infer retirement from an action's return value. The native
    adapter still needs actual exact-ART/Activity/guest/worker observations.
    """
    rows = []
    for label, action in actions:
        need(re.fullmatch(r"[a-z0-9-]{1,80}", label), "Unsafe finalization label")
        row = {"step": label, "startedUtc": runner.utc(), "status": "FAILED"}
        rows.append(row)
        try:
            row["observation"] = action()
            row["status"] = "RETURNED"  # A return is deliberately not RETIRED/PASS.
        except BaseException as error:
            row["error"] = type(error).__name__ + ": " + str(error)
        finally:
            row["endedUtc"] = runner.utc()
            # Persistence failure must not prevent subsequent retirement attempts.
            try:
                runner.write_new_json(evidence / ("finally-" + label + ".json"), row)
            except BaseException as error:
                row["status"] = "FAILED"
                row["retentionError"] = type(error).__name__ + ": " + str(error)
    return rows


def stop_handles(guest):
    """Always attempt BOTH exact handle waits, with fixed20s/10s bounds.

    The future adapter must first request shutdown of its admitted emulator and
    its foreground adb server independently, even when ART retirement failed.
    A forced/unknown earlier retirement remains a failure in the episode record.
    No kill/terminate/PID sweep or default server is used here.
    """
    result = {}
    for label, handle, seconds in (("emulator", guest.emulator, 20), ("adb", guest.server, 10)):
        status = None
        try:
            need(handle is not None, "No owned " + label + " handle")
            status = handle.wait(timeout=seconds)
            need(type(status) is int and status == 0, "Owned " + label + " exit was not zero")
            result[label] = {"exitCode": status, "waitSeconds": seconds}
        except BaseException as error:
            result[label] = {"exitCode": status, "waitSeconds": seconds,
                             "error": type(error).__name__ + ": " + str(error)}
    return result


def retain_content_result(runner, verifier, evidence, retained, stdout, case, token, source):
    checked_identity(case, token, source)
    result = verifier.verify(retained, stdout, case, token, source["commit"], source["tree"])
    # Preserve the existing verifier's result verbatim. A source/installed/EOF
    # observer must never overwrite its UNPROVEN/NOT_ACCEPTED/review fields.
    runner.write_new_json(evidence / "content-result.json", result)
    return result


if __name__ == "__main__":
    raise SystemExit("android_ui_controller is a library of primitives, not an admitted runtime entrypoint")
