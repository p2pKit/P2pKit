#!/usr/bin/env python3
"""Inspect the shared Android acceptance producer; never build or boot a guest.

Run in a maintained immutable command leaf, after the same state's successful
three-task BUILD_ARGUMENTS leaf. Both generated manifests must have been newly
retained by that producer receipt. Inspect the exact APKs with the selected SDK's
apkanalyzer, then reuse the maintained generated/packaged identity comparator.
Success remains provisional until this command's outer receipt has finalized.
It proves no UI, permission, runtime, emulator, phone or interoperability result.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MODULE_BUILD = "samples/p2p-sample-android/build"
REPORT_DIRECTORY = MODULE_BUILD + "/reports/android-acceptance/debug"
MAP_PATH = REPORT_DIRECTORY + "/artifacts.json"
TASK = ":p2p-sample-android:retainDebugAcceptanceArtifacts"
BUILD_ARGUMENTS = [":p2p-sample-android:assembleDebug", ":p2p-sample-android:assembleDebugAndroidTest", TASK]
MANIFEST_LIMIT = 1024 * 1024
APK_LIMIT = 512 * 1024 * 1024
MAP_LIMIT = 1024 * 1024
PACKAGE = "dev.p2pkit.sample.android"


def need(condition, message):
    if not condition:
        raise ValueError(message)


def load_tool(filename):
    name = "android_acceptance_" + filename.replace("-", "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def keys(value, expected, label):
    need(type(value) is dict and set(value) == set(expected), "Wrong " + label + " fields")


def relative_build_path(value):
    need(type(value) is str and 0 < len(value) <= 2048 and "\\" not in value and
         all(32 <= ord(character) <= 126 for character in value),
         "Invalid artifact path")
    path = PurePosixPath(value)
    need(not path.is_absolute() and all(part not in ("", ".", "..") for part in value.split("/")) and
         path.as_posix() == value and value.startswith(MODULE_BUILD + "/"),
         "Artifact path is outside the module build root")
    return path


def producer_tasks(value):
    need(type(value) is list and 0 < len(value) <= 128 and all(
        type(item) is str and len(item) <= 512 and
        re.fullmatch(r":(?:[A-Za-z0-9_.-]+:)*[A-Za-z0-9_.-]+", item) for item in value),
        "Invalid provider task paths")
    need(value == sorted(set(value)) and TASK not in value, "Ambiguous/self-referential provider task paths")


def file_fields(value, limit):
    need(type(value["bytes"]) is int and 0 < value["bytes"] <= limit, "Invalid artifact byte count")
    need(type(value["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]),
         "Invalid artifact SHA256")
    producer_tasks(value["producerTasks"])


def validate_map(value):
    """Validate a supplied map's structure only, not its source or execution."""
    keys(value, ("schemaVersion", "taskPath", "variantName", "components"), "producer map")
    need(type(value["schemaVersion"]) is int and value["schemaVersion"] == 1 and
         value["taskPath"] == TASK and value["variantName"] == "debug", "Wrong acceptance producer")
    keys(value["components"], ("app", "test"), "component map")
    all_paths = set()
    for role, kind, package in (("app", "APPLICATION", PACKAGE), ("test", "ANDROID_TEST", PACKAGE + ".test")):
        component = value["components"][role]
        keys(component, ("componentKind", "applicationId", "variantName", "manifest", "apk", "metadataProjection"),
             "component")
        need(component["componentKind"] == kind and component["applicationId"] == package,
             "Wrong component identity")
        variant = component["variantName"]
        need(type(variant) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,127}", variant) and
             (role != "app" or variant == "debug"), "Invalid component variant")
        manifest, apk, metadata = component["manifest"], component["apk"], component["metadataProjection"]
        keys(manifest, ("sourcePath", "retainedPath", "bytes", "sha256", "producerTasks"), "manifest")
        keys(apk, ("providerPath", "path", "bytes", "sha256", "producerTasks", "outputType", "filters"), "APK")
        file_fields(manifest, MANIFEST_LIMIT)
        file_fields(apk, APK_LIMIT)
        need(manifest["retainedPath"] == REPORT_DIRECTORY + "/" + role + "-merged-AndroidManifest.xml",
             "Wrong retained manifest path")
        for path in (manifest["sourcePath"], manifest["retainedPath"], apk["path"]):
            relative_build_path(path)
            need(path not in all_paths, "Aliased artifact paths")
            all_paths.add(path)
        provider = relative_build_path(apk["providerPath"])
        need(PurePosixPath(apk["path"]).parent == provider and apk["path"].endswith(".apk"),
             "APK is not a direct output of its provider directory")
        need(apk["outputType"] == "SINGLE" and type(apk["filters"]) is list and not apk["filters"],
             "Ambiguous/split APK")
        keys(metadata, ("kind", "artifactType", "applicationId", "variantName", "elementCount", "versionCode",
                        "versionName"), "AGP metadata projection")
        need(metadata["kind"] == "AGP_BUILT_ARTIFACTS_API_PROJECTION" and metadata["artifactType"] == "APK" and
             metadata["applicationId"] == package and metadata["variantName"] == variant and
             type(metadata["elementCount"]) is int and metadata["elementCount"] == 1,
             "AGP metadata identity differs")
        version_code, version_name = metadata["versionCode"], metadata["versionName"]
        need(version_code is None or type(version_code) is int and 0 <= version_code <= 2147483647,
             "Malformed AGP version code")
        need(version_name is None or type(version_name) is str and len(version_name.encode("utf-16-le")) <= 8192 and
             all(ord(character) >= 32 for character in version_name), "Malformed AGP version name")
    return value


def fingerprint(path, limit, keep=False):
    """Bound regular-file reads; reject links and changes during the actual read.

    This is an exclusive-owned-output check, not atomic hostile-path protection.
    """
    for part in (path, *path.parents):
        info = part.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
             "Symlink/reparse-point artifact path")
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= limit, "Missing/nonregular/oversized artifact")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    hasher, total, chunks = hashlib.sha256(), 0, []
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        need(stat.S_ISREG(opened.st_mode) and identity(opened) == identity(before), "Artifact changed before read")
        while True:
            block = stream.read(min(1024 * 1024, limit - total + 1))
            if not block:
                break
            total += len(block)
            need(total <= limit, "Artifact grew beyond its bound")
            hasher.update(block)
            if keep:
                chunks.append(block)
        need(identity(os.fstat(stream.fileno())) == identity(opened), "Artifact changed during read")
    need(identity(path.lstat()) == identity(before) and total == before.st_size, "Artifact changed after read")
    return {"bytes": total, "sha256": hasher.hexdigest()}, b"".join(chunks) if keep else None


def verified_file(root, relative, description, limit, keep=False):
    relative_build_path(relative)
    actual, raw = fingerprint(root / relative, limit, keep)
    need(actual == {key: description[key] for key in ("bytes", "sha256")}, "Artifact content differs: " + relative)
    return raw


def retained_report(state, receipt, relative, limit):
    """Require this producer's new retained bytes, never a live map alone."""
    need(type(receipt.get("reports")) is list, "Producer report retention is absent")
    rows = [row for row in receipt["reports"] if type(row) is dict and row.get("source") == relative]
    need(len(rows) == 1 and rows[0].get("classification") == "changed-since-admission" and
         rows[0].get("retained") == "reports/" + relative, "Missing/old/ambiguous producer report")
    row = rows[0]
    need(type(row.get("bytes")) is int and 0 < row["bytes"] <= limit, "Invalid retained report byte count")
    path = state / "evidence" / receipt["id"] / row["retained"]
    actual, raw = fingerprint(path, limit, True)
    need(actual == {key: row.get(key) for key in ("bytes", "sha256")}, "Retained producer report hash differs")
    return raw


def admit_build_receipt(checker, receipt, canonical, context, root, purpose):
    arguments = receipt.get("requestedArgv")
    need(arguments in (BUILD_ARGUMENTS, BUILD_ARGUMENTS + ["--console=plain"]), "Wrong shared APK build request")
    wrapper = root / ("gradlew.bat" if os.name == "nt" else "gradlew")
    checker.validate(receipt, 0, purpose, root, wrapper, arguments)
    need(receipt == canonical and type(receipt.get("id")) is str and
         re.fullmatch(r"[0-9a-f]{32}", receipt["id"]), "Canonical producer receipt differs")
    need(receipt.get("kind") == "gradle" and receipt.get("jobId") == context["id"] and
         receipt.get("host") == context["host"] and receipt.get("gradleHome") == context["gradleHome"] and
         receipt.get("sourceBefore") == context["source"], "Producer belongs to a different source/state/host")
    need(str(root / MODULE_BUILD) not in context["preexistingOutputPaths"], "APK output root predated this state")


def inspect(args):
    # The maintained adapter imports its adjacent ownership module. This adds
    # only this clean checkout's scripts, never an ambient helper directory.
    sys.path.insert(0, str(SCRIPTS))
    runner = load_tool("run-audit-command.py")
    state, context = runner.context_at(os.environ["P2PKIT_AUDIT_STATE_DIR"])
    need(context["root"] == str(ROOT) and runner.source_snapshot(ROOT) == context["source"], "Wrong/changed source")
    chain = os.environ.get("P2PKIT_AUDIT_OWNERSHIP_CHAIN", "").split(":")
    need(chain and all(re.fullmatch(r"[0-9a-f]{32}", value) for value in chain), "Use an outer immutable command leaf")
    owner = runner.read_json(state / "evidence" / chain[-1] / "start.json")
    need(owner.get("id") == chain[-1] and owner.get("kind") == "command" and
         owner.get("jobId") == context["id"] and owner.get("cwd") == str(ROOT) and
         not (state / "evidence" / chain[-1] / "receipt.json").exists(), "Missing active outer command owner")
    evidence = state / "evidence" / "android-acceptance-artifacts"
    runner.reject_symlinks(evidence)
    evidence.mkdir(mode=0o700)
    result = {"status": "FAIL", "source": context["source"], "runtime": "NOT_RUN", "errors": [],
              "limitation": "Generated/packaged artifact identity only; requires successful outer receipt."}
    try:
        purpose = args.build_purpose
        need(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", purpose), "Malformed build purpose")
        path = runner.absolute_path(str(args.build_receipt))
        need(runner.within(path, state), "Build receipt is outside the owned state")
        receipt = runner.read_json(path)
        need(type(receipt.get("id")) is str and re.fullmatch(r"[0-9a-f]{32}", receipt["id"]), "Bad producer ID")
        canonical = runner.read_json(state / "evidence" / receipt["id"] / "receipt.json")
        admit_build_receipt(load_tool("check-audit-receipt.py"), receipt, canonical, context, ROOT, purpose)
        raw_map = retained_report(state, receipt, MAP_PATH, MAP_LIMIT)
        data = json.loads(raw_map, object_pairs_hook=runner.unique_object,
                          parse_constant=lambda _: need(False, "Nonfinite producer map"))
        validate_map(data)
        live_map = fingerprint(ROOT / MAP_PATH, MAP_LIMIT, True)[1]
        need(live_map == raw_map, "Live producer map differs from retained build evidence")
        generated, paths, file_bindings = {}, {}, {}
        for role in ("app", "test"):
            component = data["components"][role]
            manifest, apk = component["manifest"], component["apk"]
            original = verified_file(ROOT, manifest["sourcePath"], manifest, MANIFEST_LIMIT, True)
            copied = verified_file(ROOT, manifest["retainedPath"], manifest, MANIFEST_LIMIT, True)
            retained = retained_report(state, receipt, manifest["retainedPath"], MANIFEST_LIMIT)
            need(original == copied == retained, "Generated manifest source/copies differ")
            generated[role] = retained
            paths[role] = ROOT / apk["path"]
            verified_file(ROOT, apk["path"], apk, APK_LIMIT)
            for relative in (manifest["sourcePath"], manifest["retainedPath"], apk["path"]):
                file_bindings[relative] = manifest if relative != apk["path"] else apk
            with runner.new_file(evidence / (role + "-generated.xml")) as stream:
                stream.write(retained)
        with runner.new_file(evidence / "producer-map.json") as stream:
            stream.write(raw_map)
        sdk_value = os.environ.get("ANDROID_HOME", "")
        need(Path(sdk_value).is_absolute() and not os.environ.get("ANDROID_SDK_ROOT"), "Select one actual ANDROID_HOME")
        sdk = Path(sdk_value).resolve(strict=True)
        # This inspector does not install/admit SDK tools. Use the selected SDK
        # already admitted for the build; record the actual inspector bytes.
        analyzer_name = "apkanalyzer.bat" if os.name == "nt" else "apkanalyzer"
        analyzer = (sdk / "cmdline-tools/latest/bin" / analyzer_name).resolve(strict=True)
        need(runner.within(analyzer, sdk), "Manifest inspector resolves outside the selected SDK")
        need(os.name != "nt", "Windows analyzer launch is not admitted by this local inspector")
        analyzer_binding = fingerprint(analyzer, MANIFEST_LIMIT)[0]
        packaged, commands = {}, []
        result["commands"] = commands
        for role in ("app", "test"):
            argv = [str(analyzer), "manifest", "print", str(paths[role])]
            out, err = evidence / (role + "-packaged.xml"), evidence / (role + "-apkanalyzer.stderr")
            record = {"argv": argv, "startedUtc": runner.utc(), "timeoutSeconds": 60, "exitCode": None}
            commands.append(record)
            with runner.new_file(out) as stdout, runner.new_file(err) as stderr:
                child = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
                deadline = time.monotonic() + 60
                while child.poll() is None:
                    need(time.monotonic() < deadline, "APK manifest inspector timed out")
                    need(out.stat().st_size <= MANIFEST_LIMIT and err.stat().st_size <= MANIFEST_LIMIT,
                         "APK manifest inspector output exceeded its bound")
                    time.sleep(0.05)
                record["exitCode"] = child.returncode
                record["endedUtc"] = runner.utc()
                need(child.returncode == 0, "APK manifest inspector failed")
            need(err.stat().st_size <= MANIFEST_LIMIT, "APK inspector stderr exceeded its bound")
            packaged[role] = fingerprint(out, MANIFEST_LIMIT, True)[1]
        need(fingerprint(analyzer, MANIFEST_LIMIT)[0] == analyzer_binding, "APK manifest inspector changed")
        for relative, description in file_bindings.items():
            verified_file(ROOT, relative, description, APK_LIMIT if relative.endswith(".apk") else MANIFEST_LIMIT)
        need(fingerprint(ROOT / MAP_PATH, MAP_LIMIT, True)[1] == raw_map, "Producer map changed during inspection")
        identities = load_tool("run-android-art-smoke.py").matching_manifest_identities(
            generated["app"], generated["test"], packaged["app"], packaged["test"])
        result.update(status="ARTIFACTS_VERIFIED_PENDING_OUTER_RECEIPT", producerId=receipt["id"],
                      producerPurpose=purpose, producerMapSha256=hashlib.sha256(raw_map).hexdigest(),
                      manifestIdentities=identities, apkanalyzer={"path": str(analyzer), **analyzer_binding},
                      apks={role: data["components"][role]["apk"] for role in ("app", "test")})
    except BaseException as error:
        result["errors"].append(type(error).__name__ + ": " + str(error))
        raise
    finally:
        try:
            result["sourceAfter"] = runner.source_snapshot(ROOT)
        except BaseException as error:
            result["sourceAfter"] = None
            result["errors"].append("Source recheck: " + type(error).__name__ + ": " + str(error))
        if result["sourceAfter"] != context["source"]:
            result["status"] = "FAIL"
            result["errors"].append("Source changed during artifact inspection")
        runner.write_new_json(evidence / "result.json", result)
        # On timeout/cancellation, the maintained outer leaf drains any still
        # live inspector descendants before its unconditional same-home stop.
        # Do not remove APKs/reports: dependent UI cases still need these bytes.
    need(not result["errors"], "Artifact inspection/source recheck failed")
    print(str(evidence / "result.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-receipt", required=True, type=Path)
    parser.add_argument("--build-purpose", required=True)
    args = parser.parse_args()
    try:
        inspect(args)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        print("FATAL: Android acceptance artifacts not admitted: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
