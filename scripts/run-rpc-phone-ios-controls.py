#!/usr/bin/env python3
"""Explicit source-bound iPhone test-app preparation and supplemental simulator controls.

Uses installed Xcode/XcodeGen and a newly owned simulator. Runs inside the admitted
native executor; never signs for a physical device, reads an Apple account, claims
supported-host/capacity qualification, changes a maintained gate, or kills by PID.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

SCOPE = "SUPPLEMENTAL_RPC_PHONE_APP_NOT_PHYSICAL_OR_CAPACITY_QUALIFICATION"
TARGETS = {
    "p2pkit-rpc-phone-tests": ("Tests/RpcPhoneRunOwnerTests.swift", "RpcPhoneRunOwnerTests", 35),
    "p2pkit-rpc-phone-uitests": ("UITests/RpcPhonePresentationTests.swift", "RpcPhonePresentationTests", 4),
}
LIMIT = 256 * 1024 * 1024
FRAMEWORK_TASK = ":p2p-sample-rpc:verifyP2pKitRpcExampleDebugXCFrameworkProvenance"
FRAMEWORK_REFERENCE = "../XCFrameworks/debug/P2pKitRpcExample.xcframework"


def framework_producer_argv(root, receipt):
    return [sys.executable, str(root / "scripts/run-audit-command.py"), "--cwd", str(root),
            "--wrapper", str(root / "gradlew"), "--purpose", "rpc-phone-framework-producer",
            "--kind", "gradle", "--timeout", "3600", "--receipt", str(receipt), "--",
            FRAMEWORK_TASK, "--console=plain"]


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify_framework_reference(project):
    """Check XcodeGen's actual group-relative path before booting the owned simulator."""
    objects = project.get("objects", {})
    need(type(objects) is dict and 0 < len(objects) <= 4096 and
         all(type(row) is dict for row in objects.values()), "Malformed generated Xcode project")
    main = objects.get(objects.get(project.get("rootObject"), {}).get("mainGroup"), {})
    references = [(key, row) for key, row in objects.items() if row.get("isa") == "PBXFileReference" and
                  row.get("lastKnownFileType") == "wrapper.xcframework"]
    need(len(references) == 1, "Exactly one current-source XCFramework reference is required")
    key, reference = references[0]
    parents = [(identifier, row) for identifier, row in objects.items() if row.get("isa") == "PBXGroup" and
               key in row.get("children", [])]
    need(reference.get("path") == FRAMEWORK_REFERENCE and reference.get("sourceTree") == "<group>" and
         len(parents) == 1 and parents[0][1].get("sourceTree") == "<group>" and not parents[0][1].get("path") and
         main.get("isa") == "PBXGroup" and main.get("sourceTree") == "<group>" and not main.get("path") and
         parents[0][0] in main.get("children", []), "XCFramework path is not relative to the generated project")


def verify_info_reference(project):
    """Reject doubled repository paths and configuration-specific plist overrides."""
    objects = project.get("objects", {})
    need(type(objects) is dict and 0 < len(objects) <= 4096 and
         all(type(row) is dict for row in objects.values()), "Malformed generated Xcode project")
    applications = [row for row in objects.values() if row.get("isa") == "PBXNativeTarget" and
                    row.get("productType") == "com.apple.product-type.application"]
    need(len(applications) == 1 and applications[0].get("name") == "p2pkit-rpc-phone",
         "Exactly one phone application target is required")
    configurations = objects.get(applications[0].get("buildConfigurationList"), {})
    ids = configurations.get("buildConfigurations", [])
    need(configurations.get("isa") == "XCConfigurationList" and type(ids) is list and len(ids) == 2 and
         all(type(key) is str for key in ids) and len(set(ids)) == 2,
         "Both explicit phone application configurations are required")
    rows = [objects.get(key, {}) for key in ids]
    need({row.get("name") for row in rows} == {"Debug", "Release"}, "Phone configurations changed")
    for row in rows:
        settings = row.get("buildSettings", {})
        need(row.get("isa") == "XCBuildConfiguration" and type(settings) is dict and
             {key: value for key, value in settings.items() if key.startswith("INFOPLIST_FILE")} ==
             {"INFOPLIST_FILE": "Info.plist"}, "Phone Info.plist must be relative to the generated project")


def project_generation_argv(root, xcodegen, project_parent):
    return [str(xcodegen), "generate", "--no-env", "--spec",
            str(root / "samples/p2p-sample-rpc/phone-ios/project.yml"), "--project-root", str(project_parent),
            "--project", str(project_parent)]


def inventory(root):
    result = {}
    for target, (name, owner, count) in TARGETS.items():
        source = (root / "samples/p2p-sample-rpc/phone-ios" / name).read_text()
        need(re.findall(r"final class (\w+): XCTestCase", source) == [owner], "Unexpected Swift test class")
        methods = re.findall(r"\bfunc (test\w+)\(", source)
        need(len(methods) == len(set(methods)) == count, "Changed or incomplete phone test inventory")
        result[target] = {owner + "/" + name + "()" for name in methods}
    return result


def verify_simulator_deleted(document, identifier):
    """Absence of the one freshly created device, never authority over another device."""
    need(type(identifier) is str and re.fullmatch(r"[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}", identifier),
         "Exact owned simulator identity required")
    need(type(document) is dict and type(document.get("devices")) is dict and len(document["devices"]) <= 64,
         "Complete bounded simulator inventory required after deletion")
    rows = []
    for group in document["devices"].values():
        need(type(group) is list and len(group) <= 256 and all(type(row) is dict and type(row.get("udid")) is str and
             re.fullmatch(r"[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}", row["udid"]) for row in group),
             "Malformed simulator deletion observation")
        rows.extend(group)
    ids = [row["udid"].lower() for row in rows]
    need(len(ids) <= 4096 and len(set(ids)) == len(ids), "Ambiguous/excessive simulator inventory")
    need(identifier.lower() not in ids, "Owned simulator remains after deletion")


def assess_xctest(objects, expected):
    need(type(objects) is list and objects and all(type(item) is dict for item in objects),
         "Missing actual XCTest summaries")
    actual = {target: [] for target in expected}

    def walk(value):
        if isinstance(value, dict):
            yield value
            for nested in value.values():
                yield from walk(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from walk(nested)

    def field(value, name):
        row = value.get(name)
        need(type(row) is dict and type(row.get("_value")) is str, "Malformed XCTest " + name)
        return row["_value"]

    for document in objects:
        for entry in walk(document):
            kind = entry.get("_type", {})
            need(type(kind) is dict, "Malformed XCTest type")
            if kind.get("_name") != "ActionTestableSummary":
                continue
            target = field(entry, "targetName")
            need(target in actual, "Unexpected XCTest target")
            for case in walk(entry.get("tests", {})):
                case_type = case.get("_type", {})
                need(type(case_type) is dict, "Malformed XCTest case type")
                if case_type.get("_name") == "ActionTestMetadata":
                    actual[target].append((field(case, "identifier"), field(case, "testStatus")))
    for target, methods in expected.items():
        cases = actual[target]
        need(len(cases) == len(methods) and {name for name, _ in cases} == methods and
             all(status == "Success" for _, status in cases),
             "Missing/duplicate/failed/skipped phone XCTest methods in " + target)
    return {target: [name for name, _ in sorted(cases)] for target, cases in actual.items()}


def module(root, name, file):
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / file)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def execute_tool(row, work, root, env, utc, *, required=True, popen=subprocess.Popen,
                 now=time.monotonic, sleep=time.sleep, observer=None):
    """One bounded attempt; only the surrounding native owner may drain children.

    Do not launch after observation/log setup has exhausted the original
    deadline. A late zero exit is not readiness. Record the end of the
    observation even when the child remains alive at the deadline, without
    inventing an exit or claiming that a closed log descriptor retired it.
    """
    label = row["label"]
    row["startedUtc"] = utc()
    deadline = now() + row["timeoutSeconds"]
    try:
        if observer is not None:
            need(label == "boot-readiness", "Process observations belong only to the original cold readiness attempt")
            observer.start()
        with (work / (label + ".stdout")).open("xb") as out, (work / (label + ".stderr")).open("xb") as err:
            need(now() < deadline, "Command deadline; native owner must drain: " + label)
            process = popen(row["argv"], cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
            while True:
                row["exitCode"] = process.poll()
                need(now() < deadline, "Command deadline; native owner must drain: " + label)
                need(out.tell() <= LIMIT and err.tell() <= LIMIT, "Bounded phone tool logs")
                if observer is not None:
                    observer.sample()
                    need(now() < deadline, "Command deadline; native owner must drain: " + label)
                if row["exitCode"] is not None:
                    break
                sleep(.5)
    finally:
        row["endedUtc"] = utc()
        if observer is not None:
            row["processObservation"] = observer.finish()
    need(not required or row["exitCode"] == 0, "Command failed: " + label)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-authorized-phone-controls", action="store_true")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--xcodegen", required=True, type=Path)
    parser.add_argument("--runtime", required=True)
    args = parser.parse_args()
    need(args.owner_authorized_phone_controls and platform.system() == "Darwin" and
         os.environ.get("P2PKIT_AUDIT_OWNERSHIP_CHAIN"), "Authorized admitted native macOS execution required")
    os.umask(0o077)
    sys.dont_write_bytecode = True
    root = args.root.resolve(strict=True)
    sys.path.insert(0, str(root / "scripts"))
    audit = module(root, "phone_ios_audit", "run-audit-command.py")
    checker = module(root, "phone_ios_checker", "check-audit-receipt.py")
    state, context = audit.context_at(os.environ["P2PKIT_AUDIT_STATE_DIR"])
    from rpc_apple_boot_diagnostics import BootObserver
    need(root == Path(context["root"]) and audit.source_snapshot(root) == context["source"] and
         context["source"]["status"] == "", "Exact clean admitted source required")
    work = args.directory
    need(work.is_absolute() and work.parent == state / "work" and re.fullmatch(r"[a-z0-9-]{1,64}", work.name),
         "New directly owned work directory required")
    audit.reject_symlinks(work.parent)
    work.mkdir(mode=0o700)
    xcodegen = args.xcodegen.resolve(strict=True)
    need(xcodegen.is_file() and os.access(xcodegen, os.X_OK), "Installed XcodeGen executable required")
    need(re.fullmatch(r"com\.apple\.CoreSimulator\.SimRuntime\.iOS-[0-9-]{1,16}", args.runtime),
         "An exact installed iOS simulator runtime is required")
    expected = inventory(root)
    result = dict(schema=1, scope=SCOPE, status="FAIL", source=context["source"],
                  scriptSha256=audit.file_digest(Path(__file__)), xcodegenSha256=audit.file_digest(xcodegen),
                  runtime=args.runtime, architecture=platform.machine(), commands=[], errors=[],
                  simulatorShutdown=False, simulatorDeleted=False, simulatorTestsPassed=False, unsignedDeviceAppBuilt=False,
                  physicalInstallable=False, capacityQualified=False, startedUtc=audit.utc())
    env = dict(os.environ)
    env["P2PKIT_PYTHON3"] = sys.executable
    simulator = None

    def run(label, argv, timeout=120, required=True):
        row = dict(label=label, argv=list(map(str, argv)), timeoutSeconds=timeout)
        result["commands"].append(row)
        print("START " + label, flush=True)
        observer = BootObserver(context["host"]) if label == "boot-readiness" else None
        execute_tool(row, work, root, env, audit.utc, required=required, observer=observer)
        print("END " + label + " exit=" + str(row["exitCode"]), flush=True)
        return row

    def output(label, maximum=16 * 1024 * 1024):
        path = work / (label + ".stdout")
        need(path.stat().st_size <= maximum, "Oversized tool output")
        return path.read_bytes()

    def sim_state(label):
        run(label, ["/usr/bin/xcrun", "simctl", "list", "--json", "devices", "available"])
        devices = json.loads(output(label))["devices"]
        selected = [value for group in devices.values() for value in group if value["udid"] == simulator]
        need(len(selected) == 1 and selected[0]["isAvailable"], "Exact owned simulator unavailable")
        return selected[0]["state"]

    def manifest(directory):
        paths = audit.regular_report_files(directory, [0])
        need(paths and sum(path.stat().st_size for path in paths) <= 1024 ** 3, "Missing/oversized artifact tree")
        return {path.relative_to(directory).as_posix(): audit.file_digest(path) for path in paths}

    try:
        for label, argv in (("macos-version", ["/usr/bin/sw_vers"]), ("xcode-version", ["/usr/bin/xcodebuild", "-version"]),
                            ("xcodegen-version", [str(xcodegen), "--version"]),
                            ("runtimes", ["/usr/bin/xcrun", "simctl", "list", "runtimes", "--json"])):
            run(label, argv)
        runtimes = json.loads(output("runtimes"))["runtimes"]
        selected = [value for value in runtimes if value["identifier"] == args.runtime and value["isAvailable"]]
        need(len(selected) == 1, "Required runtime is not installed and available")
        result["runtimeVersion"] = selected[0]["version"]
        result["runtimeBuild"] = selected[0]["buildversion"]
        project_parent = root / "samples/p2p-sample-rpc/build/phone-ios"
        project_parent.mkdir(mode=0o700, parents=True)
        run("project-generation", project_generation_argv(root, xcodegen, project_parent))
        project = project_parent / "p2pkit-rpc-phone.xcodeproj"
        run("project-reference-inspection", ["/usr/bin/plutil", "-convert", "json", "-o", "-",
            str(project / "project.pbxproj")])
        generated = json.loads(output("project-reference-inspection"))
        verify_framework_reference(generated)
        verify_info_reference(generated)
        spec = ET.parse(project / "xcshareddata/xcschemes/p2pkit-rpc-phone-controls.xcscheme").getroot()
        tests = spec.findall("TestAction/Testables/TestableReference")
        need(len(tests) == len(expected) and {entry.find("BuildableReference").get("BlueprintName") for entry in tests
             if entry.get("skipped") == "NO"} == set(expected), "Generated scheme changed the required targets")
        info = plistlib.loads((project_parent / "Info.plist").read_bytes())
        need(info.get("NSLocalNetworkUsageDescription") and info.get("NSBonjourServices") == ["_p2pkit2._tcp"],
             "Required local-network declarations missing")
        build_scripts = [json.loads(match[1]) for match in re.finditer(
            r'shellScript = ("(?:\\.|[^"\\])*?");', (project / "project.pbxproj").read_text())]
        need(build_scripts.count('sh "$SRCROOT/../../phone-ios/check-xcframework.sh"') == 1,
             "Exactly one mandatory current-source framework verifier is required")
        # Establish the actual cold-simulator prerequisite before compiling. This
        # is still one first boot, with the same 120-second readiness deadline:
        # no framework build, warm-up, retry or adopted preexisting device may
        # hide migration time. Failure prevents the expensive producer entirely.
        run("create-simulator", ["/usr/bin/xcrun", "simctl", "create", "p2pkit-rpc-phone-" + uuid.uuid4().hex[:12],
            "com.apple.CoreSimulator.SimDeviceType.iPhone-17", args.runtime])
        simulator = output("create-simulator").decode().strip()
        need(re.fullmatch(r"[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}", simulator), "New simulator ID invalid")
        need(sim_state("simulator-initial") == "Shutdown", "New simulator must start Shutdown")
        run("boot-simulator", ["/usr/bin/xcrun", "simctl", "boot", simulator])
        run("boot-readiness", ["/usr/bin/xcrun", "simctl", "bootstatus", simulator, "-b"])
        need(sim_state("simulator-ready") == "Booted", "Simulator readiness not established")

        # Xcode resolves slices before its application build phases. Produce and
        # verify the same-source framework before either build; both still run
        # their own mandatory nested verifier with the owner's Python pinned.
        producer_path = work / "framework-producer.json"
        run("framework-producer", framework_producer_argv(root, producer_path), timeout=3900)
        producer = audit.read_json(producer_path)
        checker.validate(producer, 0, "rpc-phone-framework-producer", root, root / "gradlew",
                         [FRAMEWORK_TASK, "--console=plain"])
        need(producer["sourceBefore"] == producer["sourceAfter"] == context["source"] and
             not producer["errors"] and not producer["ownedSurvivors"] and
             not producer["ownership"]["discoveryErrors"] and producer["stopExitCode"] == 0,
             "Framework producer must finalize successfully at the exact source")
        result["frameworkProducerReceiptSha256"] = audit.file_digest(producer_path)
        need((project_parent / FRAMEWORK_REFERENCE).resolve(strict=True) ==
             root / "samples/p2p-sample-rpc/build/XCFrameworks/debug/P2pKitRpcExample.xcframework",
             "Generated project does not select the freshly produced framework")
        bundle = work / "phone-tests.xcresult"
        test = run("phone-unit-ui", ["/usr/bin/xcodebuild", "-jobs", "2", "-project", str(project),
            "-scheme", "p2pkit-rpc-phone-controls", "-configuration", "Debug", "-sdk", "iphonesimulator",
            "-destination", "platform=iOS Simulator,id=" + simulator, "-derivedDataPath", str(work / "simulator-derived"),
            "-resultBundlePath", str(bundle), "-parallel-testing-enabled", "NO",
            "-maximum-concurrent-test-simulator-destinations", "1", "SWIFT_TREAT_WARNINGS_AS_ERRORS=YES", "test"],
            timeout=7200, required=False)
        if bundle.is_dir():
            original = manifest(bundle)
            audit.write_new_json(work / "xcresult-manifest.json", original)
            run("xcresult-actions", ["/usr/bin/xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json",
                "--path", str(bundle)])
            actions = json.loads(output("xcresult-actions"))
            refs = {row["actionResult"]["testsRef"]["id"]["_value"] for row in actions.get("actions", {}).get("_values", [])
                    if "testsRef" in row.get("actionResult", {})}
            need(0 < len(refs) <= 8, "Actual XCTest summaries missing")
            objects = []
            for index, identifier in enumerate(sorted(refs)):
                need(re.fullmatch(r"[A-Za-z0-9_+=/~\-]{1,512}", identifier), "Invalid XCTest reference")
                label = "xcresult-tests-" + str(index)
                run(label, ["/usr/bin/xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json",
                    "--path", str(bundle), "--id", identifier])
                objects.append(json.loads(output(label)))
            result["methods"] = assess_xctest(objects, expected)
            need(original == manifest(bundle), "XCTest result changed during assessment")
        need(test["exitCode"] == 0 and "methods" in result and b"** TEST SUCCEEDED **" in output("phone-unit-ui", LIMIT),
             "Actual phone simulator tests failed")
        result["simulatorTestsPassed"] = True
        device = run("unsigned-device-app", ["/usr/bin/xcodebuild", "-jobs", "2", "-project", str(project),
            "-scheme", "p2pkit-rpc-phone", "-configuration", "Debug", "-sdk", "iphoneos", "-destination", "generic/platform=iOS",
            "-derivedDataPath", str(work / "device-derived"), "-resultBundlePath", str(work / "device-build.xcresult"),
            "CODE_SIGNING_ALLOWED=NO", "CODE_SIGNING_REQUIRED=NO", "SWIFT_TREAT_WARNINGS_AS_ERRORS=YES", "build"], timeout=7200)
        app = work / "device-derived/Build/Products/Debug-iphoneos/p2pkit-rpc-phone.app"
        app_info = plistlib.loads((app / "Info.plist").read_bytes())
        need(device["exitCode"] == 0 and app_info["CFBundleIdentifier"] == "dev.p2pkit.rpc.phonelab" and
             app_info["CFBundleExecutable"] == "p2pkit-rpc-phone", "Wrong device app identity")
        result["unsignedDeviceApp"] = str(app)
        audit.write_new_json(work / "unsigned-device-app-manifest.json", manifest(app))
        run("device-architectures", ["/usr/bin/xcrun", "lipo", "-archs", str(app / app_info["CFBundleExecutable"])])
        need(output("device-architectures").decode().strip() == "arm64", "Wrong device binary architecture")
        run("device-minimum-os", ["/usr/bin/xcrun", "vtool", "-show-build", str(app / app_info["CFBundleExecutable"])])
        result["unsignedDeviceAppBuilt"] = True
        result["status"] = "PASS_REQUIRES_OUTER_FINALIZATION"
    except Exception as error:
        result["errors"].append(type(error).__name__ + ": " + str(error))
    finally:
        if simulator is not None:
            try:
                if sim_state("simulator-before-shutdown") != "Shutdown":
                    run("shutdown-simulator", ["/usr/bin/xcrun", "simctl", "shutdown", simulator])
                need(sim_state("simulator-final") == "Shutdown", "Exact simulator Shutdown unverified")
                result["simulatorShutdown"] = True
                run("delete-simulator", ["/usr/bin/xcrun", "simctl", "delete", simulator])
                run("simulator-deleted", ["/usr/bin/xcrun", "simctl", "list", "--json", "devices"])
                verify_simulator_deleted(json.loads(output("simulator-deleted")), simulator)
                result["simulatorDeleted"] = True
            except Exception as error:
                result["errors"].append("Simulator cleanup: " + type(error).__name__ + ": " + str(error))
        try:
            # Inspect only our nested verifier receipts, not another invocation's artifacts.
            ancestors = os.environ["P2PKIT_AUDIT_OWNERSHIP_CHAIN"].split(":")
            proofs = []
            producers = []
            for path in (state / "evidence").glob("*/receipt.json"):
                receipt = audit.read_json(path)
                if ancestors[-1] not in receipt.get("ancestorInvocationIds", []):
                    continue
                if receipt.get("purpose") not in ("rpc-phone-xcode-provenance", "rpc-phone-framework-producer"):
                    continue
                checker.validate(receipt, 0, receipt["purpose"], root, root / "gradlew", receipt["requestedArgv"])
                need(receipt["sourceBefore"] == receipt["sourceAfter"] == context["source"] and
                     not receipt["errors"] and not receipt["ownedSurvivors"] and
                     not receipt["ownership"]["discoveryErrors"] and receipt["stopExitCode"] == 0,
                     "Nested RPC framework verifier failed finalization")
                destination = proofs if receipt["purpose"] == "rpc-phone-xcode-provenance" else producers
                destination.append(dict(id=receipt["id"], sha256=audit.file_digest(path)))
            result["nestedProvenance"] = proofs
            result["nestedFrameworkProducer"] = producers
            if result["status"].startswith("PASS"):
                need(len(producers) == 1 and producers[0]["sha256"] == result["frameworkProducerReceiptSha256"],
                     "One unchanged owned current-source framework producer is required")
                need(len(proofs) == 2, "Both Xcode builds must run their mandatory nested verifier")
            need(audit.source_snapshot(root) == context["source"], "Phone work modified admitted source")
            need(audit.file_digest(xcodegen) == result["xcodegenSha256"], "XcodeGen changed")
        except Exception as error:
            result["errors"].append("Final verification: " + type(error).__name__ + ": " + str(error))
        if result["errors"] or not result["simulatorShutdown"] or not result["simulatorDeleted"]:
            result["status"] = "FAIL"
        result["finishedUtc"] = audit.utc()
        audit.write_new_json(work / "result.json", result)
        print(json.dumps({key: result[key] for key in ("status", "simulatorTestsPassed", "unsignedDeviceAppBuilt",
                                                       "simulatorShutdown", "simulatorDeleted", "errors")}), flush=True)
    return 0 if result["status"].startswith("PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
