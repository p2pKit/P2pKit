#!/usr/bin/env python3
"""Current-source app-hosted Keychain/phone regressions; not physical iOS or RPC capacity qualification.

Uses the maintained CI supervisor and a fresh simulator. Reuses existing product
provenance checks, XCTest inventory and result parser, not the retired handoff
workflow's registration/authorization/producer-receipt protocol.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rpc_io_phone", ROOT / "scripts/run-rpc-phone-ios-controls.py")
phone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phone)
need = phone.need
SCOPE = "APP_HOSTED_IOS_REGRESSIONS_NOT_PHYSICAL_OR_AUTHENTICATED_CAPACITY_QUALIFICATION"
RUNTIME = "com.apple.CoreSimulator.SimRuntime.iOS-26-5"


def xctest_command(project, simulator, derived, bundle):
    need(re.fullmatch(r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}", simulator),
         "Exact newly owned simulator required")
    return ["xcodebuild", "-jobs", "2", "-project", str(project), "-scheme", "p2pkit-rpc-phone-controls",
            "-configuration", "Debug", "-sdk", "iphonesimulator", "-destination", "platform=iOS Simulator,id=" + simulator,
            "-derivedDataPath", str(derived), "-resultBundlePath", str(bundle), "-parallel-testing-enabled", "NO",
            "-maximum-concurrent-test-simulator-destinations", "1", "SWIFT_TREAT_WARNINGS_AS_ERRORS=YES", "test"]


def main():
    need(platform.system() == "Darwin" and platform.machine() == "arm64" and os.getuid() != 0,
         "Native ordinary-user macOS ARM execution required")
    need(re.fullmatch(r"[0-9a-f]{32}", os.environ.get("P2PKIT_AUDIT_JOB_ID", "")) and
         os.environ.get("P2PKIT_CI_COMMAND_DEADLINE_NS"), "Use the maintained ci_evidence.py supervisor")
    os.umask(0o077)
    report = ROOT / "build/reports/rpc-io-phone"
    report.mkdir(parents=True, exist_ok=False)
    work = Path(tempfile.mkdtemp(prefix="rpc-io-phone-", dir=os.environ["RUNNER_TEMP"]))
    env = dict(os.environ)
    env["GRADLE_OPTS"] = env.get("GRADLE_OPTS", "") + " -Dorg.gradle.daemon=false"
    end = int(env["P2PKIT_CI_COMMAND_DEADLINE_NS"]) / 1_000_000_000
    commands = []

    def run(label, argv, timeout=60, check=True, cleanup=False):
        # Leave the freshly created simulator time to shut down/delete before the outer deadline.
        available_end = end if cleanup else end - 240
        need(time.monotonic() < available_end, "Enclosing command deadline exhausted")
        row = dict(label=label, argv=list(map(str, argv)), exitCode=None)
        commands.append(row)
        started = time.monotonic()
        deadline = min(available_end, started + timeout)
        out, err = report / (label + ".stdout"), report / (label + ".stderr")
        with out.open("xb") as stdout, err.open("xb") as stderr:
            child = subprocess.Popen(row["argv"], cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                     stdout=stdout, stderr=stderr)
            try:
                while child.poll() is None:
                    need(time.monotonic() < deadline and
                         max(out.stat().st_size, err.stat().st_size) <= 64 * 1024 * 1024,
                         "Command deadline/output bound: " + label)
                    time.sleep(0.2)
                row["exitCode"] = child.wait()
                need(time.monotonic() < deadline, "Command completed after deadline: " + label)
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=10)
                row["observedExitCode"] = child.returncode
                row["elapsedSeconds"] = round(time.monotonic() - started, 3)
                (report / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        need(not check or row["exitCode"] == 0, "Command failed: " + label)
        return out.read_bytes()

    source = run("source-before", ["git", "rev-parse", "HEAD"]).decode().strip()
    tree = run("tree-before", ["git", "rev-parse", "HEAD^{tree}"]).decode().strip()
    need(not run("status-before", ["git", "status", "--porcelain=v1"]).strip(), "Clean source required")
    expected = phone.inventory(ROOT)
    xcodegen = shutil.which("xcodegen")
    need(xcodegen is not None, "Maintained XcodeGen installation missing")
    run("xcode-version", ["xcodebuild", "-version"])
    runtimes = json.loads(run("runtimes", ["xcrun", "simctl", "list", "runtimes", "--json"]))
    need(len([row for row in runtimes["runtimes"] if row.get("identifier") == RUNTIME and
              row.get("isAvailable") is True and "arm64" in row.get("supportedArchitectures", [])]) == 1,
         "Maintained iOS 26.5 ARM simulator runtime unavailable")
    run("framework", [ROOT / "gradlew", phone.FRAMEWORK_TASK, "--dependency-verification=strict",
                      "--no-daemon", "--console=plain", "--max-workers=2"], timeout=3600)
    project_parent = ROOT / "samples/p2p-sample-rpc/build/phone-ios"
    project_parent.mkdir(parents=True, exist_ok=True)
    run("project", phone.project_generation_argv(ROOT, Path(xcodegen), project_parent))
    project = project_parent / "p2pkit-rpc-phone.xcodeproj"
    generated = json.loads(run("project-inspection", ["plutil", "-convert", "json", "-o", "-",
                                                      project / "project.pbxproj"]))
    phone.verify_framework_reference(generated)
    phone.verify_info_reference(generated)
    simulator = None
    actual = None
    bundle = report / "phone-tests.xcresult"
    try:
        simulator = run("create-simulator", ["xcrun", "simctl", "create", "rpc-io-phone-" + uuid.uuid4().hex,
            "com.apple.CoreSimulator.SimDeviceType.iPhone-17", RUNTIME]).decode().strip()
        command = xctest_command(project, simulator, work / "derived", bundle)
        run("boot", ["xcrun", "simctl", "boot", simulator])
        # Operational cold boot headroom; no mobile latency/qualification claim is derived from boot time.
        run("boot-ready", ["xcrun", "simctl", "bootstatus", simulator, "-b"], timeout=600)
        run("xctest", command, timeout=2400, check=False)
        actions = json.loads(run("test-actions", ["xcrun", "xcresulttool", "get", "object", "--legacy",
                                                  "--format", "json", "--path", bundle]))
        refs = {row["actionResult"]["testsRef"]["id"]["_value"]
                for row in actions.get("actions", {}).get("_values", []) if "testsRef" in row.get("actionResult", {})}
        need(0 < len(refs) <= 8, "Missing actual XCTest summaries")
        summaries = [json.loads(run("test-summary-" + str(index),
            ["xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json", "--path", bundle, "--id", ref]))
            for index, ref in enumerate(sorted(refs))]
        actual = phone.assess_xctest(summaries, expected)
        need(next(row for row in commands if row["label"] == "xctest")["exitCode"] == 0,
             "XCTest command failed despite its partial summaries")
    finally:
        if simulator is not None:
            failures = []
            # Attempt deletion/readback even if shutdown failed. Any failed cleanup stays a failure.
            for label, argv in (("shutdown", ["xcrun", "simctl", "shutdown", simulator]),
                                ("delete", ["xcrun", "simctl", "delete", simulator])):
                try:
                    run(label, argv, timeout=90, cleanup=True)
                except Exception as error:
                    failures.append(error)
            try:
                phone.verify_simulator_deleted(json.loads(run("retired",
                    ["xcrun", "simctl", "list", "devices", "--json"], cleanup=True)), simulator)
            except Exception as error:
                failures.append(error)
            if failures:
                raise RuntimeError("Owned simulator cleanup failed; inspect original command outcomes") from failures[0]
    need(run("source-after", ["git", "rev-parse", "HEAD"]).decode().strip() == source and
         not run("status-after", ["git", "status", "--porcelain=v1"]).strip(), "Source changed")
    hashes = {path.relative_to(bundle).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in bundle.rglob("*") if path.is_file()}
    need(hashes, "Actual result bundle missing")
    (report / "result.json").write_text(json.dumps(dict(source=source, tree=tree, scope=SCOPE, tests=actual,
        runtime=RUNTIME, simulatorDeleted=True, bundleSha256=hashes), indent=2) + "\n")
    print("IOS_PHONE_CONTROLS_COMPLETE; app-hosted regressions only, not authenticated/mobile capacity")


if __name__ == "__main__":
    main()
