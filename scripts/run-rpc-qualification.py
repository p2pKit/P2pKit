#!/usr/bin/env python3
"""Explicit feature-only hosted qualification through the maintained identity-owned executor.

No legacy process-group launcher, release writer, external publication, cache restore,
privileged observer or policy override. Product failures remain failures. Independent
phases can continue only after verified finalization. Public evidence is an allowlist
of counts/status/source hashes, never raw command output, XCTest bundles or identities.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import sys
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import rpc_product_diagnostics as product_diagnostics
import rpc_apple_network_diagnostics as network_diagnostics
REF = "refs/heads/work/rpc-lan-20260927-054728-8b1b11da"
MARKER = "[rpc-qualify]"
ADMISSION_MARKER = "[rpc-admit]"
APPLE_ADMISSION_MARKER = "[rpc-apple-admit]"
INTEL_ADMISSION_MARKER = "[rpc-intel-admit]"
INTEL_MARKER = "[rpc-intel-qualify]"
INTEL_INVESTIGATION_MARKER = "[rpc-intel-investigate]"
INTEL_NATIVE_INVESTIGATION_MARKER = "[rpc-intel-native-investigate]"
INTEL_NETWORK_INVESTIGATION_MARKER = "[rpc-intel-network-investigate]"
ARM_MARKER = "[rpc-arm-qualify]"
APPLE_MARKER = "[rpc-apple-qualify]"
ART_MARKER = "[rpc-art]"
HOSTS = {
    "apple-arm64": ("Darwin", "arm64", "macos-arm64", "26", "26.5"),
    "apple-x64": ("Darwin", "x86_64", "macos-x64", "15", "26.3"),
    "android-art": ("Linux", "x86_64", "linux-x64", None, None),
}
PHASES = ("native-controls", "toolchain", "tool-installation", "archive-controls", "multicast-admission",
          "simulator-admission", "full-platform", "scoped-native", "abi", "dokka", "rpc-frameworks",
          "swift-api", "sbom", "apple-producer", "apple-project", "swift-runtime", "kvm-admission", "art-runtime",
          "owned-project-controls", "owned-native-helper-abi", "owned-swift-lifecycle", "owned-swift-cancellation",
          "intel-cold-boot", "apple-network-diagnostic")
ARM_PHASES = frozenset(("owned-project-controls", "owned-native-helper-abi", "owned-swift-lifecycle",
                        "owned-swift-cancellation"))
STATUSES = ("PASS", "FAIL", "NOT_RUN", "BLOCKED_PREREQUISITE")
CODES = ("CHECK_FAILED", "PRODUCT_FAILED", "OWNERSHIP_UNPROVEN", "PREREQUISITE_MISSING")
PURPOSES = frozenset((
    "native-controls", "jdk17", "jdk21", "macos-version", "xcode-version", "xcode-first-launch",
    "rosetta-admission", "intel-hardware", "android-compile-platforms", "pinned-xcodegen", "archive-controls",
    "multicast-reviewed-dependency", "multicast-vendor-compile", "multicast-fixture-compile", "multicast-readiness-control",
    "simulator-runtimes", "simulator-create", "simulator-initial", "full-platform", "scoped-native", "all-library-abi",
    "strict-dokka", "rpc-frameworks", "swift-sdk-iphoneos", "swift-sdk-iphonesimulator", "swift-api-iosarm64",
    "swift-api-iosx64", "swift-api-iossimulatorarm64", "sbom-producer", "sbom-validation", "xcframework-build",
    "xcframework-minimum-os", "xcode-project", "swift-simulator-initial", "swift-simulator-readiness", "swift-simulator-ready", "swift-unit-ui",
    "xcresult-actions", *("xcresult-tests-" + str(index) for index in range(8)), "simulator-finalization-before",
    "owned-simulator-shutdown", "simulator-shutdown-verified", "owned-simulator-delete", "simulator-deletion-verified",
    "kvm-policy-before", "kvm-policy-after", "android-art",
    "owned-project-controls", "owned-native-helper-abi", "owned-swift-lifecycle", "owned-swift-cancellation",
    "intel-cold-boot-initial", "intel-cold-boot-readiness", "intel-cold-boot-ready",
    *("network-probe-" + context + "-" + mode for context in network_diagnostics.CONTEXTS
      for mode in (*network_diagnostics.MODES, "sdk", "compile")),
    *("network-probe-" + stage for stage in ("isolate-before", "isolate-shutdown", "isolate-after",
                                           "retire-before", "retire-shutdown", "retire-after")),
    *("intel-boot-" + phase + "-" + kind for phase in ("before", "after")
      for kind in ("hardware", "memory", "processes", "host")),
    *(prefix + "-" + stage for prefix in ("platform-native", "owned-native", "owned-swift-lifecycle", "owned-swift-cancellation")
      for stage in ("isolate-before", "isolate-shutdown", "isolate-after", "retire-before", "retire-shutdown", "retire-after")),
    *(prefix + "-" + stage for prefix in ("owned-swift-lifecycle", "owned-swift-cancellation")
      for stage in ("actions", *("tests-" + str(index) for index in range(8)))),
))
BOUNDS = {"native-controls": 1800, "platform": 7200, "swift-readiness": 120, "swift-runtime": 7200,
          "art-runtime": 7200, "multicast-admission": 45, "archive-controls": 180}
MAX_FILE = 16 * 1024 * 1024
MAX_LOG = 256 * 1024 * 1024
NATIVE_ROLE_PROBE = "import sys; sys.path.insert(0, 'scripts'); from audit_processes import host_role; print(host_role())"
INTEL_HOST_PROBE = """import json, os, stat
info = os.stat('/bin/ps')
print(json.dumps({'loadMilli': [round(value * 1000) for value in os.getloadavg()],
    'psSetuid': bool(info.st_mode & stat.S_ISUID), 'psSetgid': bool(info.st_mode & stat.S_ISGID),
    'psOwnedByRoot': info.st_uid == 0, 'unprivileged': os.getuid() == os.geteuid() and os.getuid() > 0}))
"""
SIMULATOR_INIT = '''gradle.projectsEvaluated {
    def root = gradle.rootProject
    if (root.rootDir.absolutePath != System.getenv('P2PKIT_STRICT_SOURCE_ROOT')) return
    [':p2p-core', ':p2p-transport-lan', ':p2p-rpc', ':p2p-sample-rpc'].each { name ->
        ['iosX64Test', 'iosSimulatorArm64Test'].each { taskName ->
            def task = root.project(name).tasks.getByName(taskName)
            if (!(task.device instanceof org.gradle.api.provider.Property))
                throw new GradleException('Native simulator device property changed')
            task.device.set(System.getenv('P2PKIT_SELECTED_SIMULATOR'))
            task.device.finalizeValue()
            task.doFirst {
                if (task.device.get() != System.getenv('P2PKIT_SELECTED_SIMULATOR'))
                    throw new GradleException('Native test escaped the owned simulator')
                logger.lifecycle('OWNED_SIMULATOR_BINDING ' + task.path)
            }
        }
    }
}
'''


class QualificationError(RuntimeError):
    def __init__(self, message, code="CHECK_FAILED"):
        super().__init__(message)
        self.code = code


def need(condition, message, code="CHECK_FAILED"):
    if not condition:
        raise QualificationError(message, code)


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def bounded(path, maximum=MAX_FILE):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum, "Invalid bounded file")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    need(len(raw) <= maximum, "File grew beyond its bound")
    return raw


def admit_event(env, system, machine, lane):
    need(lane in HOSTS, "Unknown lane")
    need(env.get("GITHUB_ACTIONS") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted",
         "Only explicitly authorized disposable hosted runners", "PREREQUISITE_MISSING")
    need(env.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit" and env.get("GITHUB_REF") == REF,
         "Only this feature ref is admitted")
    need(env.get("GITHUB_EVENT_NAME") == "push" and env.get("RPC_QUALIFY_REQUESTED") == "true",
         "An intentional feature qualification push is required")
    need(re.fullmatch(r"[0-9a-f]{40}", env.get("GITHUB_SHA", "")), "Exact source SHA required")
    need((system, machine) == HOSTS[lane][:2], "Wrong native host", "PREREQUISITE_MISSING")


def admit_commit_marker(message, lane, admission_only, investigation=None):
    need(lane in HOSTS and type(admission_only) is bool, "Invalid marked qualification mode")
    need(investigation in (None, "native", "cold-boot", "network"), "Invalid Intel diagnostic experiment")
    ordinary_markers = (MARKER, ADMISSION_MARKER, APPLE_ADMISSION_MARKER, INTEL_ADMISSION_MARKER,
                        INTEL_MARKER, ARM_MARKER, APPLE_MARKER, ART_MARKER)
    diagnostic_modes = {INTEL_INVESTIGATION_MARKER: ("native", "cold-boot"),
                        INTEL_NATIVE_INVESTIGATION_MARKER: ("native",),
                        INTEL_NETWORK_INVESTIGATION_MARKER: ("network",)}
    selected = [marker for marker in diagnostic_modes if marker in message]
    if investigation is not None:
        need(lane == "apple-x64" and not admission_only and len(selected) == 1 and
             investigation in diagnostic_modes[selected[0]] and
             not any(marker in message for marker in ordinary_markers),
             "Intel diagnostics require their own explicit marker, mode and native host")
        return
    need(not selected, "Diagnostic marker cannot select ordinary qualification")
    if admission_only:
        markers = (ADMISSION_MARKER, APPLE_ADMISSION_MARKER) if lane.startswith("apple-") else (ADMISSION_MARKER,)
        if lane == "apple-x64":
            markers += (INTEL_ADMISSION_MARKER,)
    else:
        markers = (MARKER, ART_MARKER) if lane == "android-art" else (MARKER, APPLE_MARKER)
        if lane == "apple-x64":
            markers += (INTEL_MARKER,)
        elif lane == "apple-arm64":
            markers += (ARM_MARKER,)
    need(any(marker in message for marker in markers), "Unmarked source commit")


def admit_native_apple_role(lane, output):
    need(lane in ("apple-x64", "apple-arm64") and output == (HOSTS[lane][2] + "\n").encode(),
         "Native API host-role observation differs from the required Apple lane")


def unittest_count(raw):
    match = re.search(r"\nRan ([1-9][0-9]*) tests? in [0-9.]+s\s+OK\s*$", raw)
    need(match is not None, "Native controls are missing, failed or skipped")
    return int(match[1])


def control_failures(raw):
    source = ast.parse(bounded(ROOT / "scripts/tests/run-audit-command-test.py").decode())
    admitted = {node.name for node in ast.walk(source) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
    return [{"outcome": match[1], "method": match[2]} for match in re.finditer(
        r"(?m)^(FAIL|ERROR): (test_[A-Za-z0-9_]+) \([A-Za-z0-9_.]+\)$", raw) if match[2] in admitted]


def control_diagnostics(raw, evidence, runner):
    """Failure sites and closed receipt aggregates, never raw fixture output or identities."""
    result = []
    allowed_purposes = {"executor-fixture", "consumer-build", "consumer-publish"}
    blocks = re.split(r"(?m)^(?:FAIL|ERROR): (test_[A-Za-z0-9_]+) \([A-Za-z0-9_.]+\)\n", raw)
    for failure in control_failures(raw):
        name = failure["method"]
        if any(row["method"] == name for row in result):
            continue
        text = "\n".join(blocks[index + 1] for index in range(1, len(blocks), 2) if blocks[index] == name)
        lines = sorted({int(value) for value in re.findall(
            r'File "[^"\n]*/scripts/tests/run-audit-command-test.py", line ([1-9][0-9]*), in ', text)})
        case = evidence / name
        receipts, seen = [], set()
        if case.exists():
            paths = runner.regular_report_files(case, [0])
            need(len(paths) <= 8192, "Excessive retained fixture evidence")
            for path in paths:
                if path.name != "receipt.json":
                    continue
                data = bounded(path)
                digest = hashlib.sha256(data).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                need(len(seen) <= 128, "Excessive retained fixture receipts")
                proof = json.loads(data)
                purpose = proof.get("purpose")
                receipts.append({"purpose": purpose if purpose in allowed_purposes else "OTHER_FIXTURE",
                                 "sha256": digest, "diagnostic": receipt_diagnostic(proof, "")})
        result.append({"method": name, "assertionLines": lines, "receipts": receipts})
    return validate_control_diagnostics(result)


def validate_control_diagnostics(value):
    source = bounded(ROOT / "scripts/tests/run-audit-command-test.py").decode()
    methods = {node.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef)
               and node.name.startswith("test_")}
    need(type(value) is list and len(value) <= 256, "Invalid fixture diagnostics")
    for row in value:
        need(type(row) is dict and set(row) == {"method", "assertionLines", "receipts"} and
             row["method"] in methods, "Unadmitted fixture diagnostic method/fields")
        lines = row["assertionLines"]
        need(type(lines) is list and len(lines) <= 64 and all(type(n) is int and 1 <= n <= len(source.splitlines())
             for n in lines) and lines == sorted(set(lines)), "Invalid source assertion lines")
        need(type(row["receipts"]) is list and len(row["receipts"]) <= 128, "Invalid fixture receipt list")
        for receipt in row["receipts"]:
            need(type(receipt) is dict and set(receipt) == {"purpose", "sha256", "diagnostic"} and
                 receipt["purpose"] in ("executor-fixture", "consumer-build", "consumer-publish", "OTHER_FIXTURE") and
                 type(receipt["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"]),
                 "Unadmitted fixture receipt fields")
            validate_diagnostic(receipt["diagnostic"])
    return value


def control_inventory(host):
    tree = ast.parse(bounded(ROOT / "scripts/tests/run-audit-command-test.py").decode())
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    def methods(name):
        if name not in classes:
            return set()
        own = {node.name for node in classes[name].body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
        for base in classes[name].bases:
            if isinstance(base, ast.Name):
                own |= methods(base.id)
        return own
    native = {"macos-arm64": "DarwinNativeTests", "macos-x64": "DarwinNativeTests", "linux-x64": "LinuxNativeTests"}[host]
    return sum(len(methods(name)) for name in ("PurePolicyTests", "DarwinObservationTests", native,
               *(("LinuxObservationTests",) if host == "linux-x64" else ())))


def junit_counts(raw):
    need(len(raw) <= MAX_FILE and b"<!DOCTYPE" not in raw.upper() and b"<!ENTITY" not in raw.upper(),
         "Unbounded/entity-bearing JUnit XML")
    suite = ET.fromstring(raw)
    need(suite.tag == "testsuite", "Expected one JUnit suite")
    cases = suite.findall("testcase")
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for case in cases:
        labels = [key for key, tag in (("failed", "failure"), ("errors", "error"), ("skipped", "skipped"))
                  if case.find(tag) is not None]
        need(len(labels) <= 1, "Ambiguous JUnit case outcome")
        counts[labels[0] if labels else "passed"] += 1
    for name, actual in (("tests", len(cases)), ("failures", counts["failed"]),
                         ("errors", counts["errors"]), ("skipped", counts["skipped"])):
        value = suite.get(name, "0")
        need(re.fullmatch(r"[0-9]+", value) and int(value) == actual, "JUnit declared/observed counts differ")
    return counts


def swift_inventory(root):
    result = {}
    for directory, target in (("DiagnosticsTests", "p2pkit-sample-tests"), ("UITests", "p2pkit-sample-uitests")):
        cases = set()
        paths = sorted((root / "samples/iosApp" / directory).glob("*.swift"))
        need(0 < len(paths) <= 256, "Swift source inventory missing")
        for path in paths:
            text = bounded(path).decode()
            classes = re.findall(r"(?m)^\s*(?:final\s+)?class\s+(\w+)\s*:\s*XCTestCase\b", text)
            methods = re.findall(r"(?m)^\s*func\s+(test\w+)\s*\(", text)
            if methods:
                need(len(classes) == 1 and len(methods) == len(set(methods)), "Ambiguous XCTest source")
                for method in methods:
                    name = classes[0] + "/" + method + "()"
                    need(name not in cases, "Duplicate XCTest identity")
                    cases.add(name)
        need(cases, "No source XCTest methods")
        result[target] = cases
    need(len(result["p2pkit-sample-tests"]) == 88 and len(result["p2pkit-sample-uitests"]) == 6,
         "Maintained Swift inventory requires review")
    return result


ERROR_KINDS = {
    "PRE_STOP_DRAIN_FAILED": "Pre-stop ownership drain failed:",
    "FINAL_DRAIN_FAILED": "Final ownership drain failed:",
    "WRAPPER_FINALIZER_FAILED": "Wrapper stop/finalizer failed:",
    "WRAPPER_STOP_FAILED": "Applicable same-home Gradle wrapper --stop failed",
    "OWNERSHIP_TRACE_FAILED": "Ownership trace retention failed:",
    "SOURCE_EVIDENCE_FAILED": "Source/evidence finalization failed:",
    "SOURCE_CHANGED": "Exact admitted source changed or could not be admitted",
    "HANDLE_CLOSE_FAILED": "Owned handle close failed:",
    "PRODUCT_OBSERVATION_FAILED": "Product exit observation failed:",
    "STOP_OBSERVATION_FAILED": "Stop exit observation failed:",
    "CANCELLED": "Invocation cancellation cannot be a successful product result",
    "PRE_STOP_SURVIVORS": "Owned product workers survived pre-stop drain",
    "FINAL_SURVIVORS": "Owned workers survived final drain",
    "PROCESS_OBSERVATION_FAILED": "Cannot inspect new same-uid process ",
}
STOP_MARKERS = {
    "DISTRIBUTION_DOWNLOAD": "Downloading https://services.gradle.org/distributions/",
    "NO_DAEMONS": "No Gradle daemons are running.",
    "BUILD_FAILED": "BUILD FAILED",
    "BUILD_SUCCEEDED": "BUILD SUCCESSFUL",
    "DISTRIBUTION_INSTALL_FAILED": "Could not install Gradle distribution",
    "CHECKSUM_FAILED": "Verification of Gradle distribution failed",
    "JAVA_MISSING": "JAVA_HOME is not set",
    "EXCEPTION": "Exception in thread",
    "TIMEOUT": "timed out",
}
DARWIN_OPERATIONS = {"identity": "IDENTITY", "environment": "ENVIRONMENT", "task token": "TASK_TOKEN",
                     "inherited pipe": "INHERITED_PIPE"}
DARWIN_OUTCOMES = {name: name.upper() for name in ("unresolved", "recovered", "absent", "nonrunning", "replaced")}
DARWIN_STATES = {1: "IDLE", 2: "RUNNING", 3: "SLEEPING", 4: "STOPPED", 5: "ZOMBIE"}
DARWIN_CAUSES = {
    **{f"{label}_{name}": re.compile(r"(?:^|: )" + pattern + str(number) + r"$")
       for label, pattern in (("ENVIRONMENT", r"Darwin process environment failed: errno "),
                              ("IDENTITY", r"Darwin process identity failed for pid [0-9]+: errno "),
                              ("PIPE", r"Darwin pipe observation failed: errno "),
                              ("DESCRIPTORS", r"Darwin descriptor census failed: errno "))
       for number, name in ((0, "ZERO"), (1, "EPERM"), (2, "ENOENT"), (3, "ESRCH"), (5, "EIO"),
                             (9, "EBADF"), (13, "EACCES"), (22, "EINVAL"))},
    **{f"{label}_{name}": re.compile(r"(?:^|: )" + pattern + str(number) + r"$")
       for label, pattern in (("TASK_NAME", r"Darwin task-name access unavailable: Mach result "),
                              ("TASK_TOKEN", r"Darwin TASK_AUDIT_TOKEN unavailable: Mach result "))
       for number, name in ((0, "SUCCESS"), (1, "INVALID_ADDRESS"), (2, "PROTECTION_FAILURE"),
                             (4, "INVALID_ARGUMENT"), (5, "FAILURE"), (15, "INVALID_NAME"), (46, "NOT_SUPPORTED"))},
    "PARENT_UNOBSERVED": re.compile(r"(?:^|: )Darwin non-reaper original-parent lifetime was not observed$"),
    "TRACED_PARENT": re.compile(r"(?:^|: )Darwin traced parentage is not an ownership proof$"),
    "EXEC_CHANGED": re.compile(r"(?:^|: )Darwin exec version changed during observation$"),
}


def darwin_observation_diagnostic(observation):
    """Only closed aggregate labels; no PID, audit-session ID, token, path, environment or process name."""
    need(type(observation) is dict, "Invalid observation record")
    records = {}
    for name in ("observationReconciliations", "unclassifiedLifetimes"):
        rows = observation.get(name, [])
        need(type(rows) is list and len(rows) <= 1024 and all(type(row) is dict for row in rows),
             "Invalid bounded Darwin diagnostic inventory")
        records[name] = rows
    result = {"recorded": any(name in observation for name in records), "operations": {}, "outcomes": {},
              "pendingStates": {}, "failureKinds": [], "pendingCount": len(records["unclassifiedLifetimes"])}

    def increment(collection, label):
        result[collection][label] = result[collection].get(label, 0) + 1

    causes = set()
    for name, rows in records.items():
        for row in rows:
            if name == "observationReconciliations":
                increment("operations", DARWIN_OPERATIONS.get(row.get("operation"), "OTHER"))
                increment("outcomes", DARWIN_OUTCOMES.get(row.get("outcome"), "OTHER"))
            else:
                identity = row.get("lastIdentity", row.get("identity", {}))
                status = identity.get("status") if type(identity) is dict else None
                increment("pendingStates", DARWIN_STATES.get(status, "OTHER") if type(status) is int else "OTHER")
            for key in ("firstFailure", "lastFailure"):
                message = row.get(key)
                if message is not None:
                    need(type(message) is str and len(message) <= 4096, "Unbounded diagnostic failure")
                    causes.add(next((label for label, pattern in DARWIN_CAUSES.items() if pattern.search(message)), "OTHER"))
    result["failureKinds"] = sorted(causes)
    return validate_darwin_diagnostic(result)


def validate_darwin_diagnostic(value):
    need(type(value) is dict and set(value) == {"recorded", "operations", "outcomes", "pendingStates",
                                               "failureKinds", "pendingCount"}, "Invalid Darwin diagnostic schema")
    need(type(value["recorded"]) is bool and type(value["pendingCount"]) is int and
         0 <= value["pendingCount"] <= 1024, "Invalid pending Darwin count")
    for field, labels in (("operations", set(DARWIN_OPERATIONS.values())), ("outcomes", set(DARWIN_OUTCOMES.values())),
                           ("pendingStates", set(DARWIN_STATES.values()))):
        counts = value[field]
        need(type(counts) is dict and set(counts) <= labels | {"OTHER"} and
             all(type(count) is int and 0 <= count <= 1024 for count in counts.values()) and
             sum(counts.values()) <= 1024, "Invalid Darwin aggregate count")
    causes = value["failureKinds"]
    need(type(causes) is list and len(causes) <= len(DARWIN_CAUSES) + 1 and
         all(type(label) is str and label in {*DARWIN_CAUSES, "OTHER"} for label in causes) and
         causes == sorted(set(causes)), "Private Darwin diagnostic label rejected")
    need(sum(value["pendingStates"].values()) == value["pendingCount"] and
         sum(value["operations"].values()) == sum(value["outcomes"].values()), "Inconsistent Darwin diagnostic counts")
    return value


def fixed_error_inventory():
    # Only literal messages already present in the two reviewed executor sources.
    # Dynamic exception values, paths, process identities and traceback text are never returned.
    messages = set()
    for name in ("run-audit-command.py", "audit_processes.py"):
        tree = ast.parse(bounded(ROOT / "scripts" / name).decode())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            arguments = node.args[1:2] if node.func.id == "require" else node.args[:1] if node.func.id.endswith("Error") else []
            for value in arguments:
                # Both literal arms of a source-written conditional are fixed
                # messages too (e.g. product versus wrapper-stop timeout).
                literals = (value.body, value.orelse) if isinstance(value, ast.IfExp) else (value,)
                for literal in literals:
                    if isinstance(literal, ast.Constant) and type(literal.value) is str and 0 < len(literal.value) <= 256 and "\n" not in literal.value:
                        messages.add(literal.value)
    return messages


def receipt_diagnostic(proof, stop_output):
    """Closed enum/count diagnostics, even for a failed receipt; never execution admission."""
    errors = proof.get("errors", [])
    need(type(errors) is list and len(errors) <= 4096 and all(type(e) is str for e in errors), "Invalid error inventory")
    kinds = sorted({next((key for key, prefix in ERROR_KINDS.items() if error.startswith(prefix)), "OTHER") for error in errors})
    observation = proof.get("ownership", {})
    retained_errors = errors + [row[key] for name in ("discoveryReconciliations", "observationReconciliations")
        for row in observation.get(name, []) for key in ("firstFailure", "lastFailure") if type(row.get(key)) is str]
    survivors = proof.get("ownedSurvivors")
    need(survivors is None or type(survivors) is list and len(survivors) <= 100000 and
         all(type(row) is dict for row in survivors), "Invalid survivor inventory")
    survivor_state = "MISSING" if survivors is None else "KNOWN" if all(
        type(row.get("pid")) is int and row["pid"] > 0 and row.get("status") != "UNKNOWN" for row in survivors) else "UNKNOWN"
    result = {"errorKinds": kinds, "errorCount": len(errors), "sourceUnchanged": proof.get("sourceUnchanged") is True,
              "fixedErrorMessages": sorted(message for message in fixed_error_inventory()
                  if any(error == message or error.endswith(": " + message) for error in retained_errors)),
              # The executor's [{status: UNKNOWN, reason: ...}] is not one known
              # worker. Missing/unknown inventories must not imply a zero count either.
              "ownedSurvivorCount": len(survivors) if survivor_state == "KNOWN" else None,
              "survivorInventoryState": survivor_state,
              "discoveryErrorCount": len(observation.get("discoveryErrors", [])),
              "darwinObservations": darwin_observation_diagnostic(observation),
              "stopMarkers": sorted(key for key, marker in STOP_MARKERS.items() if marker in stop_output)}
    for key in ("productExitCode", "stopExitCode", "finalExitCode"):
        result[key] = proof.get(key)
    return validate_diagnostic(result)


def validate_diagnostic(value):
    required = {"errorKinds", "errorCount", "sourceUnchanged", "ownedSurvivorCount", "discoveryErrorCount",
                "stopMarkers", "productExitCode", "stopExitCode", "finalExitCode", "fixedErrorMessages"}
    need(type(value) is dict and required <= set(value) <= required | {"darwinObservations", "survivorInventoryState"},
         "Invalid diagnostic schema")
    if "darwinObservations" in value:
        validate_darwin_diagnostic(value["darwinObservations"])
    for name, allowed in (("errorKinds", {*ERROR_KINDS, "OTHER"}), ("stopMarkers", set(STOP_MARKERS)),
                          ("fixedErrorMessages", fixed_error_inventory())):
        need(type(value[name]) is list and len(value[name]) <= len(allowed) and all(type(v) is str and v in allowed for v in value[name]),
             "Private diagnostic label rejected")
    for name in ("errorCount", "discoveryErrorCount"):
        need(type(value[name]) is int and 0 <= value[name] <= 100000, "Invalid diagnostic count")
    count = value["ownedSurvivorCount"]
    if "survivorInventoryState" in value:
        state = value["survivorInventoryState"]
        need(state in ("MISSING", "KNOWN", "UNKNOWN") and
             (state == "KNOWN" and type(count) is int and 0 <= count <= 100000 or
              state != "KNOWN" and count is None), "Unknown survivor inventory cannot become a count")
    else:
        # Original schema used the number of receipt records, including the
        # UNKNOWN sentinel. Preserve readability; do not reinterpret old artifacts.
        need(type(count) is int and 0 <= count <= 100000, "Invalid legacy survivor-record count")
    for name in ("productExitCode", "stopExitCode", "finalExitCode"):
        need(value[name] is None or type(value[name]) is int and -255 <= value[name] <= 255, "Invalid diagnostic exit")
    need(type(value["sourceUnchanged"]) is bool, "Invalid diagnostic source flag")
    return value


def native_attempt(raw):
    matches = re.findall(r"(?m)^Ran ([1-9][0-9]*) tests? in [0-9.]+s$", raw)
    need(len(matches) <= 1, "Ambiguous native control output")
    status = "MISSING_OUTPUT" if not matches else "PASS_OUTPUT_ONLY" if re.search(r"\nOK\s*$", raw) else "FAIL_OUTPUT_ONLY"
    return {"reportedTests": int(matches[0]) if matches else 0, "status": status, "executionAdmitted": False}


def public_summary(private):
    """Explicit scalars only. Do not serialize an error string, command, test name or host identity."""
    source = private.get("source", {})
    for name in ("commit", "tree"):
        need(re.fullmatch(r"[0-9a-f]{40}", source.get(name, "")), "Invalid public source binding")
    need(private.get("lane") in HOSTS, "Invalid public lane")
    outcome = private.get("result", "INCOMPLETE")
    need(outcome in ("PASS", "FAIL", "INCOMPLETE"), "Invalid public outcome")
    phases = {}
    for label in PHASES:
        row = private.get("phases", {}).get(label, {})
        status = row.get("status", "NOT_RUN")
        need(status in STATUSES, "Invalid phase status")
        code = row.get("code")
        need(code is None or code in CODES, "Invalid public reason code")
        phases[label] = {"status": status, **({"code": code} if code else {})}
    counts = {}
    for name in ("nativeControlTests", "junitPassed", "junitFailed", "junitErrors", "junitSkipped", "junitSuites",
                 "swiftUnitPassed", "swiftUiPassed", "ownedNativePassed", "ownedSwiftLifecyclePassed",
                 "ownedSwiftCancellationPassed"):
        value = private.get("counts", {}).get(name, 0)
        need(type(value) is int and 0 <= value <= 10000000, "Invalid public count")
        counts[name] = value
    commands = []
    for row in private.get("commands", []):
        # Labels are source-written identifiers, not product output; reject arbitrary values anyway.
        label = row.get("purpose", "")
        need(label in PURPOSES, "Invalid command label")
        code = row.get("rawExitCode")
        need(code is None or type(code) is int and -255 <= code <= 255, "Invalid public exit code")
        commands.append({"purpose": label, "exitCode": code, "finalizationVerified": row.get("verified") is True,
                         **({"diagnostic": validate_diagnostic(row["diagnostic"])} if "diagnostic" in row else {})})
    failures = private.get("controlFailures", [])
    need(type(failures) is list and len(failures) <= 256 and failures == control_failures("\n".join(
        str(row.get("outcome")) + ": " + str(row.get("method")) + " (__main__.Fixture)" for row in failures)),
        "Invalid public control failure")
    policy = module("rpc_public_marker_policy", "run-rpc-hosted-validation.py")
    markers = private.get("multicastMarkers", [])
    need(type(markers) is list and len(markers) <= 160 and all(type(line) is str and any(
         pattern.fullmatch(line) for pattern in policy.FIXTURE_MARKERS) for line in markers), "Invalid public multicast marker")
    admission_only = private.get("admissionOnly", False)
    need(type(admission_only) is bool, "Invalid qualification mode")
    attempt = private.get("nativeAttempt", {"reportedTests": 0, "status": "MISSING_OUTPUT", "executionAdmitted": False})
    need(type(attempt) is dict and set(attempt) == {"reportedTests", "status", "executionAdmitted"} and
         type(attempt["reportedTests"]) is int and 0 <= attempt["reportedTests"] <= 100000 and
         attempt["status"] in ("MISSING_OUTPUT", "PASS_OUTPUT_ONLY", "FAIL_OUTPUT_ONLY") and attempt["executionAdmitted"] is False,
         "Invalid unadmitted control-output summary")
    investigation = private.get("intelInvestigation")
    need(investigation in (None, "native", "cold-boot", "network") and
         (investigation is None or private["lane"] == "apple-x64" and not admission_only),
         "Invalid Intel diagnostic scope")
    need(not private.get("productDiagnostics", {}).get("intelEnvironment") or investigation == "cold-boot",
         "Intel environment observations require the cold-boot diagnostic scope")
    need(not (private.get("productDiagnostics", {}).get("appleNetwork") or
              private.get("productDiagnostics", {}).get("appleNetworkCompiler")) or investigation == "network",
         "Primitive network observations cannot be substituted for product qualification")
    return {"schema": 1, "scope": "FEATURE_ONLY_INTEL_DIAGNOSTIC_NOT_PRODUCT_QUALIFICATION" if investigation else
            "FEATURE_ONLY_EXECUTOR_DIAGNOSTIC_NOT_PRODUCT_QUALIFICATION" if admission_only else
            "FEATURE_ONLY_AUTOMATED_CHECKS_NOT_RELEASE_DEVICE_OR_CAPACITY", "admissionOnly": admission_only, "nativeAttempt": attempt,
            "intelInvestigation": investigation,
            "source": {key: source[key] for key in ("commit", "tree")}, "lane": private["lane"], "result": outcome,
            "phases": phases, "counts": counts, "countsSemantics": "ADMITTED_COUNTS_ONLY_NOT_ATTEMPT_COUNTS", "commands": commands,
            "controlFailures": failures, "controlDiagnostics": validate_control_diagnostics(private.get("controlDiagnostics", [])),
            "multicastMarkers": markers,
            "productDiagnostics": product_diagnostics.validate(private.get("productDiagnostics", {}), ROOT, PURPOSES),
            "sourceUnchanged": private.get("sourceAfter") == source,
            "simulatorRetired": private.get("simulatorRetired") is True,
            "kvmPolicyUnchanged": private.get("kvmPolicyUnchanged") is True,
            "foundationStatus": "NOT_READY", "externalPublication": False, "physicalQualification": False,
            "rpcCapacityQualification": False}


class Qualification:
    def __init__(self, lane, admission_only=False, investigation=None):
        self.admission_only = admission_only
        self.intel_investigation = investigation
        admit_event(os.environ, platform.system(), platform.machine(), lane)
        self.lane = lane
        self.runner = module("rpc_owned_leaf", "run-audit-command.py")
        self.checker = module("rpc_receipt_checker", "check-audit-receipt.py")
        self.gate = module("rpc_pure_coverage", "run-platform-tests.py")
        self.policy = module("rpc_pure_compile_policy", "run-rpc-hosted-validation.py")
        self.parent = self.runner.absolute_path(os.environ["RPC_QUALIFICATION_PARENT"])
        temporary = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
        need(self.parent.is_relative_to(temporary) and self.parent != temporary, "Unowned qualification parent")
        need(ROOT == Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True), "Wrong checkout root")
        need(self.runner.git(ROOT, "rev-parse", "--is-shallow-repository").strip() == b"false" and
             not self.runner.git(ROOT, "for-each-ref", "--format=%(refname)", "refs/tags").strip(), "Full no-tags history required")
        need(self.runner.git(ROOT, "config", "--get", "remote.origin.url").decode().strip() in
             ("https://github.com/p2pKit/P2pKit", "https://github.com/p2pKit/P2pKit.git"), "Canonical origin required")
        message = self.runner.git(ROOT, "show", "-s", "--format=%B", "HEAD").decode()
        admit_commit_marker(message, lane, admission_only, investigation)
        self.state = self.parent / "state"
        with (self.parent / "initialization.log").open("x") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            self.runner.initialize(argparse.Namespace(root=str(ROOT), state=str(self.state),
                expected_commit=os.environ["GITHUB_SHA"], host=HOSTS[lane][2]))
        self.state, self.context = self.runner.context_at(str(self.state))
        need(self.context["preexistingOutputPaths"] == [], "Preexisting build outputs are not admitted")
        for name in ("private", "work", "tmp", "konan", "android-user", "tools"):
            (self.state / name).mkdir(mode=0o700)
        self.private = self.state / "private"
        self.wrapper = ROOT / ("gradlew.bat" if os.name == "nt" else "gradlew")
        os.environ.update(P2PKIT_AUDIT_STATE_DIR=str(self.state), GRADLE_USER_HOME=self.context["gradleHome"],
            KONAN_DATA_DIR=str(self.state / "konan"), ANDROID_USER_HOME=str(self.state / "android-user"),
            TMPDIR=str(self.state / "tmp"), P2PKIT_GRADLE_EXECUTOR=str(ROOT / "scripts/run-audit-command.py"),
            P2PKIT_XCODE_JOBS="2", PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
        for name in list(os.environ):
            if name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN") or name.upper().startswith(
                    ("SIGNING_", "ORG_GRADLE_PROJECT_SIGNING", "MAVEN_CENTRAL_", "SONATYPE_")):
                os.environ.pop(name)
        self.unsafe = False
        self.simulator = None
        self.simulator_deleted = False
        self.kvm = None
        self.result = {"productDiagnostics": {"logs": {}, "native": {}, "simulator": {"states": {}}}, "lane": lane, "admissionOnly": admission_only, "intelInvestigation": investigation, "source": self.context["source"], "result": "FAIL", "commands": [],
                       "phases": {}, "counts": {}, "errors": [], "startedUtc": self.runner.utc()}
        self.runner.write_new_json(self.private / "admission.json", self.result)

    def invoke(self, purpose, argv, timeout, kind="command", allow_failure=False, finalizer=False):
        need(not self.unsafe or finalizer, "Prior ownership failure blocks further product work", "OWNERSHIP_UNPROVEN")
        need(purpose in PURPOSES and not any(row["purpose"] == purpose for row in self.result["commands"]), "Do not repeat an attempted command")
        print("START " + purpose, flush=True)
        alias = self.private / (purpose + ".json")
        row = {"purpose": purpose, "argv": argv, "kind": kind, "timeoutSeconds": timeout, "verified": False}
        self.result["commands"].append(row)
        # Tee writes bytes through .buffer; real file streams prevent raw tool output reaching hosted logs.
        with (self.private / (purpose + ".driver.log")).open("x") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            code = self.runner.main(["--cwd", str(ROOT), "--wrapper", str(self.wrapper), "--kind", kind,
                "--purpose", purpose, "--timeout", str(timeout), "--receipt", str(alias), "--", *argv])
        row["rawExitCode"] = code
        try:
            proof = self.runner.read_json(alias)
            row.update(invocationId=proof["id"], receiptSha256=self.runner.file_digest(alias))
            stop_output = ""
            for stream in ("stdout", "stderr"):
                path = self.state / "evidence" / proof["id"] / ("stop." + stream + ".log")
                if path.exists():
                    stop_output += bounded(path, MAX_LOG).decode(errors="replace")
            row["diagnostic"] = receipt_diagnostic(proof, stop_output)
            if purpose in ("full-platform", "scoped-native", "swift-simulator-readiness", "intel-cold-boot-readiness",
                           "simulator-runtimes", "simulator-create") or purpose.startswith("network-probe-"):
                self.result["productDiagnostics"]["logs"][purpose] = {
                    stream: product_diagnostics.log_observation(self.output(proof, MAX_LOG, stream))
                    for stream in ("stdout", "stderr")}
            if purpose == "native-controls":
                path = self.state / "evidence" / proof["id"] / "product.stderr.log"
                raw = bounded(path, MAX_LOG).decode(errors="replace") if path.exists() else ""
                self.result["controlFailures"] = control_failures(raw)
                self.result["nativeAttempt"] = native_attempt(raw)
                self.result["controlDiagnostics"] = control_diagnostics(raw, self.state / "evidence/native-controls", self.runner)
            self.checker.validate(proof, code, purpose, ROOT, self.wrapper, argv)
            need(proof["jobId"] == self.context["id"] and proof["gradleHome"] == self.context["gradleHome"] and
                 proof["sourceBefore"] == self.context["source"] and proof["ancestorInvocationIds"] == [] and
                 proof["ownership"]["discoveryErrors"] == [], "Owned context/source mismatch")
            need(proof == self.runner.read_json(self.state / "evidence" / proof["id"] / "receipt.json") and
                 row["receiptSha256"] == self.runner.file_digest(self.state / "evidence" / proof["id"] / "receipt.json"),
                 "Receipt aliases differ")
            row["verified"] = True
        except BaseException as error:
            self.unsafe = True
            raise QualificationError("Invocation finalization unproven", "OWNERSHIP_UNPROVEN") from error
        print("END " + purpose + " exit=" + str(code), flush=True)
        need(code == 0 or allow_failure, purpose + " failed; no automatic retry", "PRODUCT_FAILED")
        return proof

    def output(self, proof, maximum=MAX_FILE, stream="stdout"):
        return bounded(self.state / "evidence" / proof["id"] / ("product." + stream + ".log"), maximum)

    def phase(self, label, operation, prerequisite=True):
        need(label in PHASES and label not in self.result["phases"], "Invalid/repeated phase")
        if not prerequisite or self.unsafe:
            self.result["phases"][label] = {"status": "BLOCKED_PREREQUISITE"}
            return False
        try:
            operation()
            self.result["phases"][label] = {"status": "PASS"}
            return True
        except Exception as error:
            code = error.code if isinstance(error, QualificationError) else "CHECK_FAILED"
            self.result["phases"][label] = {"status": "FAIL", "code": code}
            self.result["errors"].append({"phase": label, "error": type(error).__name__ + ": " + str(error)})
            print("PHASE " + label + " FAIL " + code, flush=True)
            return False

    def native_controls(self):
        proof = self.invoke("native-controls", [sys.executable, "scripts/tests/run-audit-command-test.py",
            "--expected-host", HOSTS[self.lane][2], "--evidence-dir", str(self.state / "evidence/native-controls")],
            BOUNDS["native-controls"], allow_failure=True)
        raw = self.output(proof, MAX_LOG, "stderr").decode()
        self.result["controlFailures"] = control_failures(raw)
        need(proof["productExitCode"] == 0, "Native executor controls failed", "PRODUCT_FAILED")
        self.result["counts"]["nativeControlTests"] = unittest_count(raw)
        need(self.result["counts"]["nativeControlTests"] == control_inventory(HOSTS[self.lane][2]), "Incomplete native control inventory")

    def toolchain(self):
        for label, home, major in (("jdk17", "JAVA_HOME", "17"), ("jdk21", "P2PKIT_AUDIT_JDK21", "21")):
            java = Path(os.environ[home]).resolve(strict=True) / "bin/java"
            proof = self.invoke(label, [str(java), "-XshowSettings:properties", "-version"], 45)
            text = self.output(proof, stream="stderr").decode()
            need(re.search(r"(?m)^\s*java\.specification\.version = " + major + r"\s*$", text), "Wrong JDK")
            arch = "aarch64" if self.lane == "apple-arm64" else "x86_64" if self.lane == "apple-x64" else "amd64"
            need(re.search(r"(?m)^\s*os\.arch = " + arch + r"\s*$", text), "JDK is not native")
        if not self.lane.startswith("apple"):
            return
        expected = HOSTS[self.lane]
        developer = Path("/Applications/Xcode_" + expected[4] + ".app/Contents/Developer")
        need(os.environ.get("DEVELOPER_DIR") == str(developer) and developer.is_dir(), "Required Xcode unavailable", "PREREQUISITE_MISSING")
        sw = self.invoke("macos-version", ["/usr/bin/sw_vers", "-productVersion"], 45)
        need(self.output(sw).decode().strip().split(".")[0] == expected[3], "Required macOS unavailable", "PREREQUISITE_MISSING")
        xcode = self.invoke("xcode-version", ["/usr/bin/xcodebuild", "-version"], 45)
        need(self.output(xcode).decode().splitlines()[0] == "Xcode " + expected[4], "Wrong selected Xcode")
        self.invoke("xcode-first-launch", ["/usr/bin/xcodebuild", "-checkFirstLaunchStatus"], 120)
        # sysctl -i deliberately returns success/empty for an absent OID on Intel.
        # Reuse the maintained native API observer instead of treating CLI exit
        # status/empty output as a translation result. It accepts only a native
        # zero or ENOENT and rejects query errors, wrong sizes and Rosetta.
        translated = self.invoke("rosetta-admission", [sys.executable, "-c", NATIVE_ROLE_PROBE], 45)
        admit_native_apple_role(self.lane, self.output(translated))
        if self.lane == "apple-x64":
            cpu = self.invoke("intel-hardware", ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"], 45)
            need(b"Intel" in self.output(cpu), "True Intel hardware required")

    def install_apple_tools(self):
        sdk = self.state / "work/sdk"
        sdk.mkdir()
        base = Path(os.environ["ANDROID_HOME"]).resolve(strict=True)
        for name in ("cmdline-tools/latest", "licenses"):
            need((base / name).is_dir(), "Missing preinstalled SDK tools/licenses", "PREREQUISITE_MISSING")
            shutil.copytree(base / name, sdk / name)
        os.environ.pop("ANDROID_SDK_ROOT", None)
        os.environ["ANDROID_HOME"] = str(sdk)
        self.invoke("android-compile-platforms", [str(sdk / "cmdline-tools/latest/bin/sdkmanager"),
            "--sdk_root=" + str(sdk), "platforms;android-36", "platforms;android-37.0", "platform-tools"], 900)
        install = self.state / "tools/xcodegen"
        self.invoke("pinned-xcodegen", ["/bin/bash", "scripts/install-xcodegen.sh", str(install)], 900)
        os.environ["PATH"] = str(install / "bin") + os.pathsep + os.environ["PATH"]

    def multicast_admission(self):
        # The previous hosted failure is not blindly retried as a full build.
        # First require this NEW host's unchanged real-resource control to finish
        # naturally, with the original 10s readiness and 45s child bound.
        need("P2PKIT_JMDNS_FIXTURE_IPV4" not in os.environ, "No multicast/interface override")
        work = self.state / "work/multicast"
        work.mkdir()
        dependency = work / "slf4j-api-2.0.7.jar"
        pins = ET.parse(ROOT / "gradle/verification-metadata.xml").getroot().findall(
            "./v:components/v:component[@group='org.slf4j'][@name='slf4j-api'][@version='2.0.7']/"
            "v:artifact[@name='slf4j-api-2.0.7.jar']/v:sha256", {"v": "https://schema.gradle.org/dependency-verification"})
        checksum = "5d6298b93a1905c32cda6478808ac14c2d4a47e91535e53c41f7feeb85d946f4"
        need([p.get("value") for p in pins] == [checksum], "Reviewed source dependency pin differs")
        self.invoke("multicast-reviewed-dependency", ["/usr/bin/curl", "--disable", "--fail", "--silent", "--show-error",
            "--proto", "=https", "--tlsv1.2", "--connect-timeout", "15", "--max-time", "60", "--max-filesize", "1048576",
            "--output", str(dependency), "https://repo.maven.apache.org/maven2/org/slf4j/slf4j-api/2.0.7/slf4j-api-2.0.7.jar"], 90)
        need(hashlib.sha256(bounded(dependency, 1048576)).hexdigest() == checksum, "Dependency pin failed")
        vendor = ROOT / "library/p2p-transport-lan/vendor/jmdns/src/main"
        sources = sorted(vendor.glob("java/**/*.java"))
        need(len(sources) == 60, "Vendor source inventory changed")
        fixture = ROOT / "library/p2p-transport-lan/src/jvmTest/java/dev/p2pkit/transport/lan/internal/jmdns/impl/JmdnsCloseLifecycleFixture.java"
        classes = work / "classes"
        classes.mkdir()
        java = Path(os.environ["JAVA_HOME"]).resolve(strict=True) / "bin"
        self.invoke("multicast-vendor-compile", [str(java / "javac"), "-J-Xmx256m", "-J-XX:ActiveProcessorCount=2",
            "--release", "8", "-encoding", "UTF-8", "-classpath", str(dependency), "-d", str(classes), *map(str, sources)], 90)
        self.invoke("multicast-fixture-compile", [str(java / "javac"), "-J-Xmx256m", "-J-XX:ActiveProcessorCount=2",
            "--release", "17", "-encoding", "UTF-8", "-classpath", os.pathsep.join(map(str, (classes, dependency))),
            "-d", str(classes), str(fixture)], 90)
        proof = self.invoke("multicast-readiness-control", [str(java / "java"), "-Xms16m", "-Xmx128m", "-XX:MaxMetaspaceSize=128m",
            "-XX:ActiveProcessorCount=2", "-XX:+UseSerialGC", "-Dorg.slf4j.simpleLogger.defaultLogLevel=off",
            "-Dp2pkit.audit.jmdnsStartupPrimitives=true", "-Dp2pkit.audit.pythonExecutable=" + sys.executable,
            "-cp", os.pathsep.join(map(str, (classes, vendor / "resources", dependency))),
            "dev.p2pkit.transport.lan.internal.jmdns.impl.JmdnsCloseLifecycleFixture", "control"], BOUNDS["multicast-admission"], allow_failure=True)
        raw = self.output(proof).decode() + self.output(proof, stream="stderr").decode()
        # Closed, reviewed enum/boolean/number markers only, never throwable messages/addresses.
        self.result["multicastMarkers"] = [line for line in raw.splitlines()
            if any(pattern.fullmatch(line) for pattern in self.policy.FIXTURE_MARKERS)]
        need(proof["productExitCode"] == 0 and raw.splitlines().count("PASS mode=control") == 1 and
             "FAIL mode=" not in raw and "phase=fixture_rescue_begin" not in raw, "Multicast prerequisite failed", "PREREQUISITE_MISSING")

    def select_simulator(self):
        proof = self.invoke("simulator-runtimes", ["/usr/bin/xcrun", "simctl", "list", "--json", "runtimes"], 120)
        rows = json.loads(self.output(proof))["runtimes"]
        available = [r for r in rows if r.get("isAvailable") and r.get("identifier", "").startswith("com.apple.CoreSimulator.SimRuntime.iOS-")]
        need(available, "No installed iOS simulator runtime", "PREREQUISITE_MISSING")
        runtime = max(available, key=lambda r: tuple(int(n) for n in r["version"].split(".")))
        self.result["productDiagnostics"]["simulator"].update(
            version=runtime["version"], architectures=runtime.get("supportedArchitectures", []))
        need(re.fullmatch(r"com\.apple\.CoreSimulator\.SimRuntime\.iOS-[0-9-]+", runtime["identifier"]), "Invalid runtime identity")
        proof = self.invoke("simulator-create", ["/usr/bin/xcrun", "simctl", "create", "RPC-qualification-" + uuid.uuid4().hex,
            "com.apple.CoreSimulator.SimDeviceType.iPhone-17", runtime["identifier"]], 120)
        identifier = self.output(proof).decode().strip()
        need(re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", identifier), "Invalid created device identity")
        self.simulator = identifier  # Only this newly created device can be finalized by this job.
        need(self.simulator_state("simulator-initial")["state"] == "Shutdown", "New simulator must start Shutdown")
        self.sim_init = self.private / "owned-simulator.init.gradle"
        with self.sim_init.open("x") as stream:
            stream.write(SIMULATOR_INIT)
        os.environ.update(P2PKIT_STRICT_SOURCE_ROOT=str(ROOT), P2PKIT_SELECTED_SIMULATOR=identifier)
        self.runner.write_new_json(self.private / "simulator-ownership.json", {"createdByThisJob": True,
            "creationReceiptId": proof["id"], "device": identifier, "runtime": runtime["identifier"], "initialState": "Shutdown"})

    def simulator_state(self, purpose, finalizer=False):
        proof = self.invoke(purpose, ["/usr/bin/xcrun", "simctl", "list", "--json", "devices", "available"], 120, finalizer=finalizer)
        matches = [d for rows in json.loads(self.output(proof))["devices"].values() for d in rows if d["udid"] == self.simulator]
        if self.simulator_deleted:
            need(not matches, "Deleted owned simulator remains")
            return None
        need(len(matches) == 1 and matches[0]["isAvailable"], "Owned simulator unavailable")
        self.result["productDiagnostics"]["simulator"]["states"][purpose] = matches[0]["state"]
        return matches[0]

    def platform_tests(self, full):
        arch = "arm64" if self.lane == "apple-arm64" else "x64"
        profile = "full" if full else "ios-" + arch
        if getattr(self, "intel_investigation", None) == "native":
            need(self.lane == "apple-x64" and not full, "Diagnostic subset cannot replace a required platform profile")
            profile = "ios-lan-x64"
        token = uuid.uuid4().hex
        coverage = ROOT / "build/reports/platform-tests" / token / "execution.json"
        need(not coverage.parent.exists(), "Coverage must be fresh")
        argv = [*self.gate.PROFILES[profile], *self.gate.FLAGS, "--init-script", str(ROOT / "gradle/platform-test-coverage.init.gradle"),
            "-Pp2pkit.testCoverageRoot=" + str(ROOT), "-Pp2pkit.testCoverageToken=" + token,
            "--init-script", str(self.sim_init), "--no-configure-on-demand", "--warning-mode=fail", "--stacktrace"]
        self.retire_created_simulator("platform-native-isolate")
        try:
            proof = self.invoke("full-platform" if full else "scoped-native", argv, BOUNDS["platform"], "gradle", allow_failure=True)
        finally:
            # KGP's standalone Native spawn is not a GUI-ready simulator lease.
            # Match the maintained host/ARM helper lifecycle on BOTH real hosts:
            # retire the exact owned device even after a failed Native invocation,
            # before independent producers or ordinary Swift readiness can start.
            self.retire_created_simulator("platform-native-retire")
        report = self.gate.read_json(coverage) if coverage.exists() else None
        self.result["productDiagnostics"]["native"]["full-platform" if full else "scoped-native"] = (
            product_diagnostics.native_observation(ROOT, report))
        need(report is not None, "Fresh native coverage report missing")
        self.runner.write_new_json(self.private / "execution.json", report)
        needed = self.gate.assess(report, self.gate.read_json(ROOT / "gradle/platform-test-policy.json"), profile, arch, token)
        counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        inventory, suites = [], 0
        for task in sorted(needed):
            project, name = task[1:].split(":")
            paths = [ROOT / container / project / "build/test-results" / name for container in ("library", "samples")]
            paths = [p for p in paths if p.is_dir()]
            need(len(paths) == 1, "JUnit task directory missing/ambiguous")
            files = sorted(paths[0].rglob("TEST-*.xml"))
            need(0 < len(files) <= 4096, "JUnit suites missing or excessive")
            actual = {key: 0 for key in counts}
            for path in files:
                self.runner.reject_symlinks(path)
                raw = bounded(path)
                for key, value in junit_counts(raw).items():
                    actual[key] += value
                inventory.append({"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
            expected = report["tests"][task]
            need(actual["errors"] == 0 and all(actual[k] == expected[k] for k in ("passed", "failed", "skipped")), "JUnit/coverage mismatch")
            for key in counts:
                counts[key] += actual[key]
            suites += len(files)
        self.runner.write_new_json(self.private / "junit-inventory.json", {"files": inventory, "counts": counts})
        self.result["counts"].update({"junit" + key.capitalize(): value for key, value in counts.items()}, junitSuites=suites)
        need(proof["productExitCode"] == 0, "Platform command failed", "PRODUCT_FAILED")

    def compile_phase(self, label):
        if label == "abi":
            self.invoke("all-library-abi", [*(":" + n + ":checkKotlinAbi" for n in self.policy.LIBRARIES), *self.policy.FLAGS], 1800, "gradle")
        else:
            command = self.policy.compilation_commands()[0 if label == "dokka" else 1]
            self.invoke(command[0], [*command[1], *self.policy.FLAGS], command[2], "gradle")
            self.result[label + "Outputs"] = self.policy.compilation_receipt(ROOT, command[0])

    def retire_created_simulator(self, prefix):
        """Retire only our newly created device; shutdown is cleanup, never a test verdict."""
        ordinary = prefix in ("platform-native-isolate", "platform-native-retire")
        network = (self.lane == "apple-x64" and getattr(self, "intel_investigation", None) == "network" and
                   prefix in ("network-probe-isolate", "network-probe-retire"))
        arm = prefix in {kind + "-" + step for kind in
                        ("owned-native", "owned-swift-lifecycle", "owned-swift-cancellation")
                        for step in ("isolate", "retire")}
        need(self.lane in ("apple-x64", "apple-arm64") and self.simulator and not self.simulator_deleted and
             (ordinary or network or (self.lane == "apple-arm64" and arm)), "Exact created Apple simulator scope required")
        try:
            if self.simulator_state(prefix + "-before", True)["state"] != "Shutdown":
                self.invoke(prefix + "-shutdown", ["/usr/bin/xcrun", "simctl", "shutdown", self.simulator],
                            120, finalizer=True)
            need(self.simulator_state(prefix + "-after", True)["state"] == "Shutdown",
                 "Exact owned simulator retirement is unproven", "OWNERSHIP_UNPROVEN")
        except BaseException:
            self.unsafe = True
            raise

    def retire_owned_simulator(self, prefix):
        need(self.lane == "apple-arm64", "Dedicated ownership follow-through requires the actual ARM device")
        self.retire_created_simulator(prefix)

    def owned_project_controls(self):
        need(self.lane == "apple-arm64", "ARM follow-through cannot be supplied by an Intel runner")
        self.invoke("owned-project-controls", [sys.executable, "scripts/tests/ios-project-generation-test.py",
            "IosProjectGenerationTest.test_owned_flow_sources_use_existing_test_containers",
            "IosProjectGenerationTest.test_ui_and_release_callers_preserve_both_test_targets",
            "IosProjectGenerationTest.test_cancellation_probe_is_excluded_from_both_acceptance_schemes",
            "IosProjectGenerationTest.test_generation_preserves_provenance_and_local_network_declarations"], 180)

    def retained_report(self, proof, source):
        rows = [row for row in proof["reports"] if row["source"] == source]
        need(len(rows) == 1 and rows[0]["classification"] == "changed-since-admission",
             "Missing fresh retained test report")
        row = rows[0]
        directory = self.state / "evidence" / proof["id"]
        path = directory / row["retained"]
        self.runner.reject_symlinks(path)
        need(path.resolve(strict=True).is_relative_to(directory) and path.stat().st_size == row["bytes"] and
             self.runner.file_digest(path) == row["sha256"], "Retained test report changed")
        return bounded(path)

    def owned_native_helper(self):
        """Run the maintained four-case ARM helper plus aggregate LAN ABI, not a substitute assessor."""
        need(self.lane == "apple-arm64", "Native ARM execution required")
        maintained = module("rpc_owned_native_assessor", "run-audit-host.py")
        token = uuid.uuid4().hex
        target = "iosSimulatorArm64"
        task = ":p2p-transport-lan:" + target + "Test"
        self.retire_owned_simulator("owned-native-isolate")
        try:
            # SIMULATOR_INIT assigns and finalizes the exact owned device before
            # Gradle applies task CLI options. A redundant --device (even the
            # identical UUID) mutates that finalized Property and fails before
            # any native test. Keep the immutable binding, not a second writer.
            proof = self.invoke("owned-native-helper-abi", [task, "--tests",
                maintained.OWNED_NATIVE_CLASS, ":p2p-transport-lan:checkKotlinAbi", "--continue",
                "--init-script", str(ROOT / "gradle/platform-test-coverage.init.gradle"),
                "-Pp2pkit.testCoverageRoot=" + str(ROOT), "-Pp2pkit.testCoverageToken=" + token,
                "--init-script", str(self.sim_init), "--no-configure-on-demand", "--warning-mode=fail", "--stacktrace"],
                BOUNDS["platform"], "gradle", allow_failure=True)
        finally:
            self.retire_owned_simulator("owned-native-retire")
        need(proof["productExitCode"] == 0, "Native helper/aggregate ABI invocation failed", "PRODUCT_FAILED")
        prefix = "library/p2p-transport-lan/build/test-results/" + target + "Test/TEST-"
        xml = prefix + target + "Test." + maintained.OWNED_NATIVE_CLASS + ".xml"
        need([row["source"] for row in proof["reports"] if row["source"].startswith(prefix) and
              row["source"].endswith(".xml")] == [xml], "Unexpected helper suite inventory")
        report = json.loads(self.retained_report(proof, "build/reports/platform-tests/" + token + "/execution.json"))
        assessment = maintained.assess_owned_native(report, self.gate.read_json(ROOT / "gradle/platform-test-policy.json"),
            token, self.retained_report(proof, xml), role="macos-arm64")
        abi = ["> Task :p2p-transport-lan:" + name for name in ("iosArm64MainKlibrary",
               "iosSimulatorArm64MainKlibrary", "iosX64MainKlibrary", "internalDumpKotlinAbi", "checkKotlinAbi")]
        lines = self.output(proof, MAX_LOG).decode().splitlines()
        need(all(lines.count(name) == 1 for name in abi), "Fresh aggregate native ABI tasks missing")
        self.runner.write_new_json(self.private / "owned-native-assessment.json", {
            **assessment, "token": token, "source": self.context["source"], "invocationId": proof["id"], "abiTasks": abi})
        self.result["counts"]["ownedNativePassed"] = len(assessment["methods"])

    def owned_swift(self, cancellation):
        """The original scoped XCTest actions, exact maintained inventories, and explicit retirement."""
        need(self.lane == "apple-arm64" and type(cancellation) is bool, "Native ARM ownership gate required")
        prefix = "owned-swift-cancellation" if cancellation else "owned-swift-lifecycle"
        action = "run-owned-cancellation" if cancellation else "run-owned-flow-lifecycle"
        filename = "swift-owned-cancellation" if cancellation else "swift-owned-flow-lifecycle"
        selection = "owned-cancellation" if cancellation else "owned-flow-lifecycle"
        work = self.state / "work" / prefix
        need(not work.exists(), "Focused Swift outputs must be fresh")
        bundle = work / "DerivedData/Logs/Test" / (filename + ".xcresult")
        self.retire_owned_simulator(prefix + "-isolate")
        extra = {"IOS_RUN_DIR": str(work), "KEEP_IOS_RUN_ARTIFACTS": "1", "SIM_UDID": self.simulator}
        previous = {key: os.environ.get(key) for key in extra}
        try:
            os.environ.update(extra)
            proof = self.invoke(prefix, ["/bin/bash", "scripts/run-ios-ui-tests.sh", action],
                                900 if cancellation else BOUNDS["swift-runtime"], allow_failure=True)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            self.retire_owned_simulator(prefix + "-retire")
        actual = self.inspect_swift_result(proof, bundle, prefix,
            lambda objects: module("rpc_owned_swift_assessor", "run-audit-host.py").assess_swift(objects, selection=selection))
        self.result["counts"]["ownedSwiftCancellationPassed" if cancellation else "ownedSwiftLifecyclePassed"] = sum(
            len(cases) for cases in actual.values())

    def swift_api(self):
        cache = self.state / "work/swift-module-cache"
        cache.mkdir()
        paths = {}
        for target, (sdk, triple) in self.policy.APPLE_TARGETS.items():
            if sdk not in paths:
                proof = self.invoke("swift-sdk-" + sdk, ["/usr/bin/xcrun", "--sdk", sdk, "--show-sdk-path"], 45)
                path = Path(self.output(proof, 4096).decode().strip()).resolve(strict=True)
                need(path.is_dir() and path.is_relative_to(Path(os.environ["DEVELOPER_DIR"])), "Wrong SDK")
                paths[sdk] = str(path)
            self.invoke("swift-api-" + target.lower(), ["/usr/bin/xcrun", "--sdk", sdk, "swiftc", "-typecheck", "-warnings-as-errors",
                "-swift-version", "5", "-sdk", paths[sdk], "-target", triple, "-module-cache-path", str(cache),
                "-F", str(self.policy.framework_path(ROOT, target).parent),
                str(ROOT / "samples/p2p-sample-rpc/verification/RpcSwiftApiCheck.swift")], 180)

    def sbom(self):
        folder = ROOT / "build/reports/cyclonedx"
        self.invoke("sbom-producer", ["cyclonedxBom", *self.policy.FLAGS], 1800, "gradle")
        self.invoke("sbom-validation", ["/bin/bash", "scripts/check-sbom.sh", str(folder / "bom.json"), str(folder / "bom.xml")], 120)

    def apple_producer(self):
        release = ROOT / "library/p2p-transport-lan/build/XCFrameworks/release"
        need(not release.exists(), "Fresh XCFramework producer required")
        proof = self.invoke("xcframework-build", [self.runner.XCFRAMEWORK_TASK], 7200, "gradle")
        shutil.copyfile(self.private / "xcframework-build.json", self.state / "host-xcframework-build.json")
        rows = []
        for name in self.runner.XCFRAMEWORK_SIDECARS:
            data = bounded(release / name, 1024 * 1024)
            destination = self.state / "evidence" / name
            with destination.open("xb") as stream:
                stream.write(data)
            need(self.runner.file_digest(destination) == self.runner.file_digest(release / name), "Sidecar changed")
            rows.append({"path": name, "sha256": self.runner.file_digest(destination), "result": "RETAINED"})
        self.runner.write_new_json(self.state / "evidence/xcframework-sidecars.json", {"files": rows, "sourceInvocationId": proof["id"]})
        self.producer = self.runner.xcframework_reuse_binding(self.state, self.context, ROOT, self.wrapper)
        need(bounded(release / "BUILD_COMMIT.txt").decode().strip() == self.context["expectedCommit"] and
             bounded(release / "BUILD_SOURCE_STATE.txt").decode().strip() == "clean", "Wrong producer source")
        self.invoke("xcframework-minimum-os", ["/bin/bash", "scripts/check-xcframework-minimum-os.sh"], 180)

    def apple_project(self):
        self.invoke("xcode-project", [":iosApp:regenerateXcodeProject", *self.policy.FLAGS], 1800, "gradle")
        project = ROOT / "samples/iosApp/p2pkit-sample.xcodeproj"
        text = bounded(project / "project.pbxproj")
        need(b"Check P2pKitShared XCFramework provenance" in text, "Mandatory provenance phase missing")
        ui = ET.fromstring(bounded(project / "xcshareddata/xcschemes/p2pkit-sample-ui.xcscheme"))
        enabled = {node.find("BuildableReference").get("BlueprintName") for node in ui.findall("TestAction/Testables/TestableReference")
                   if node.get("skipped") == "NO"}
        need(enabled == {"p2pkit-sample-tests", "p2pkit-sample-uitests"}, "Ordinary Swift targets changed")

    def swift_runtime(self):
        expected = swift_inventory(ROOT)
        need(self.simulator_state("swift-simulator-initial")["state"] == "Shutdown",
             "Ordinary Swift requires the Native simulator to have been retired", "OWNERSHIP_UNPROVEN")
        self.invoke("swift-simulator-readiness", ["/usr/bin/xcrun", "simctl", "bootstatus", self.simulator, "-b"], BOUNDS["swift-readiness"])
        need(self.simulator_state("swift-simulator-ready")["state"] == "Booted", "System app readiness unproven")
        build = self.state / "work/SwiftDerivedData"
        need(not build.exists(), "Fresh Swift runtime outputs required")
        bundle = build / "Logs/Test/feature-swift.xcresult"
        self.bundle = bundle
        proof = self.invoke("swift-unit-ui", ["/usr/bin/xcodebuild", "-jobs", "2", "-project", "samples/iosApp/p2pkit-sample.xcodeproj",
            "-scheme", "p2pkit-sample-ui", "-configuration", "Debug", "-sdk", "iphonesimulator", "-destination",
            "platform=iOS Simulator,id=" + self.simulator, "-derivedDataPath", str(build), "-resultBundlePath", str(bundle),
            "-parallel-testing-enabled", "NO", "-maximum-concurrent-test-simulator-destinations", "1",
            "SWIFT_TREAT_WARNINGS_AS_ERRORS=YES", "test"], BOUNDS["swift-runtime"], allow_failure=True)
        def assess(objects):
            swift = module("rpc_pure_swift_assessor", "run-audit-host.py")
            actual = swift.assess_swift(objects)
            need(set(actual) == set(expected) and all({case["identifier"] for case in actual[target]} == expected[target]
                 for target in expected), "Actual XCTest methods differ from source")
            return actual
        actual = self.inspect_swift_result(proof, bundle, "xcresult", assess)
        self.result["counts"].update(swiftUnitPassed=len(actual["p2pkit-sample-tests"]), swiftUiPassed=len(actual["p2pkit-sample-uitests"]))

    def inspect_swift_result(self, proof, bundle, prefix, assess):
        need(bundle.is_dir(), "No actual XCTest bundle")
        entries = self.runner.regular_report_files(bundle, [0])
        need(entries and sum(p.stat().st_size for p in entries) <= 1024 * 1024 * 1024, "Invalid/bounded native result")
        original = {str(p.relative_to(bundle)): self.runner.file_digest(p) for p in entries}
        self.runner.write_new_json(self.private / (prefix + "-manifest.json"), {"files": original})
        nested = []
        for path in (self.state / "evidence").glob("*/receipt.json"):
            leaf = self.runner.read_json(path)
            if proof["id"] not in leaf.get("ancestorInvocationIds", []):
                continue
            self.checker.validate(leaf, 0, "xcode-provenance", ROOT, self.wrapper, leaf["requestedArgv"])
            need(leaf["kind"] == "gradle" and leaf["jobId"] == self.context["id"] and leaf["sourceBefore"] == self.context["source"] and
                 leaf["ownership"]["discoveryErrors"] == [] and leaf["requestedArgv"] in self.runner.XCFRAMEWORK_ARGV and
                 leaf.get("xcframeworkReuseUnchanged") is True and leaf.get("xcframeworkReuse") == self.producer,
                 "Mandatory nested provenance is not intact")
            nested.append({"id": leaf["id"], "sha256": self.runner.file_digest(path)})
        need(len(nested) == 1, "Exactly one mandatory nested provenance receipt required")
        self.result.setdefault("nestedProvenance", {})[prefix] = nested
        actions = self.invoke(prefix + "-actions", ["/usr/bin/xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json", "--path", str(bundle)], 120)
        data = json.loads(self.output(actions))
        refs = {row["actionResult"]["testsRef"]["id"]["_value"] for row in data.get("actions", {}).get("_values", [])
                if "testsRef" in row.get("actionResult", {})}
        need(0 < len(refs) <= 8, "Missing/excessive XCTest summaries")
        objects = []
        for index, identifier in enumerate(sorted(refs)):
            need(re.fullmatch(r"[A-Za-z0-9_+=/~\-]{1,512}", identifier), "Invalid XCTest reference")
            entry = self.invoke(prefix + "-tests-" + str(index), ["/usr/bin/xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json",
                "--path", str(bundle), "--id", identifier], 120)
            objects.append(json.loads(self.output(entry)))
        actual = assess(objects)
        need(original == {str(p.relative_to(bundle)): self.runner.file_digest(p) for p in self.runner.regular_report_files(bundle, [0])},
             "Native result changed during inspection")
        need(proof["productExitCode"] == 0 and b"** TEST SUCCEEDED **" in self.output(proof, MAX_LOG), "Swift tests failed", "PRODUCT_FAILED")
        return actual

    def kvm_admission(self):
        # Never setfacl/chmod/sudo or manufacture the legacy kvm-restored sentinel.
        path = Path("/dev/kvm")
        need(path.exists() and not path.is_symlink() and stat.S_ISCHR(path.stat().st_mode) and
             os.access(path, os.R_OK | os.W_OK), "Existing KVM access is required; no policy change is authorized", "PREREQUISITE_MISSING")
        with path.open("rb+", buffering=0):
            pass
        self.kvm = self.kvm_snapshot("kvm-policy-before")

    def intel_environment_observation(self, phase, finalizer=False):
        need(self.lane == "apple-x64" and self.intel_investigation == "cold-boot" and phase in ("before", "after"),
             "Read-only Intel boot observations require the explicit diagnostic scope")
        need(type(finalizer) is bool and finalizer == (phase == "after"),
             "Only the post-boot read-only snapshot may follow a failed invocation")
        commands = {
            "hardware": ["/usr/sbin/sysctl", "-n", "hw.memsize", "hw.logicalcpu"],
            "memory": ["/usr/bin/vm_stat"],
            # Do not execute a system process-listing tool that may be set-id.
            # Its privilege transition is not an exception to native ownership.
            "host": [sys.executable, "-c", INTEL_HOST_PROBE],
        }
        observations = self.result["productDiagnostics"].setdefault("intelEnvironment", {}).setdefault(phase, {})
        for kind, argv in commands.items():
            proof = self.invoke("intel-boot-" + phase + "-" + kind, argv, 30, finalizer=finalizer)
            observations[kind] = product_diagnostics.intel_environment_observation(kind, self.output(proof))

    def intel_cold_boot(self):
        need(self.lane == "apple-x64" and self.intel_investigation == "cold-boot", "Explicit cold-boot diagnostic required")
        need(self.simulator_state("intel-cold-boot-initial")["state"] == "Shutdown", "Fresh simulator must be Shutdown")
        self.intel_environment_observation("before")
        primary = None
        try:
            # This device has NEVER hosted Native/Swift work. Test the supported
            # full-boot alternative without a hidden warm-up, retry or extra time.
            self.invoke("intel-cold-boot-readiness", ["/usr/bin/xcrun", "simctl", "bootstatus", self.simulator, "-b"],
                        BOUNDS["swift-readiness"])
            need(self.simulator_state("intel-cold-boot-ready")["state"] == "Booted", "Cold GUI readiness unproven")
        except BaseException as error:
            primary = error
            raise
        finally:
            # Read-only failure evidence, not permission to resume product work.
            # Existing unsafe state/errors remain; finish() must still retire the
            # exact created device and may not turn a timeout into a pass.
            try:
                self.intel_environment_observation("after", finalizer=True)
            except BaseException as error:
                if primary is None:
                    raise
                # Do not let an auxiliary snapshot hide the original boot failure.
                self.result["errors"].append({"diagnostic": "intel-boot-after", "error": str(error)})

    def investigate_intel(self, toolchain):
        need(self.lane == "apple-x64" and self.intel_investigation in ("native", "cold-boot", "network"),
             "Only the separately labeled native Intel experiments are admitted")
        if self.intel_investigation == "cold-boot":
            simulator = self.phase("simulator-admission", self.select_simulator, toolchain)
            self.phase("intel-cold-boot", self.intel_cold_boot, simulator)
        elif self.intel_investigation == "network":
            simulator = self.phase("simulator-admission", self.select_simulator, toolchain)
            self.phase("apple-network-diagnostic", self.apple_network_diagnostic, simulator)
        else:
            tools = self.phase("tool-installation", self.install_apple_tools, toolchain)
            self.phase("multicast-admission", self.multicast_admission, tools)
            simulator = self.phase("simulator-admission", self.select_simulator, tools)
            self.phase("scoped-native", lambda: self.platform_tests(False), simulator)

    def apple_network_diagnostic(self):
        """Compare actual OS APIs under the SAME unchanged unprivileged ownership executor.

        No warm-up, permission changes, service/route overrides or product-test
        substitution. The local-only DNS-SD control is labelled separately.
        """
        need(self.lane == "apple-x64" and self.intel_investigation == "network",
             "The primitive experiment requires its own explicit native Intel scope")
        work = self.state / "work/apple-network-probe"
        work.mkdir()
        source = ROOT / "scripts/diagnostics/apple-bonjour-probe.c"
        observed = self.result["productDiagnostics"]["appleNetwork"] = {}
        self.retire_created_simulator("network-probe-isolate")
        try:
            for context in network_diagnostics.CONTEXTS:
                sdk = "macosx" if context == "host" else "iphonesimulator"
                prefix = "network-probe-" + context + "-"
                proof = self.invoke(prefix + "sdk", ["/usr/bin/xcrun", "--sdk", sdk, "--show-sdk-path"], 30)
                sdk_path = Path(self.output(proof).decode().strip())
                need(sdk_path.is_absolute() and sdk_path.is_dir() and
                     sdk_path.resolve().is_relative_to(Path(os.environ["DEVELOPER_DIR"]).resolve()),
                     "Probe SDK must belong to the admitted Xcode")
                target = "x86_64-apple-macos15.0" if context == "host" else "x86_64-apple-ios15.0-simulator"
                binary = work / ("probe-" + context)
                # Darwin exports DNS-SD through implicitly linked libSystem.
                # -ldns_sd is the POSIX client-library flag, not an Apple SDK input.
                proof = self.invoke(prefix + "compile", ["/usr/bin/xcrun", "--sdk", sdk, "clang", "-std=c11",
                    "-Wall", "-Wextra", "-Werror", "-fblocks", "-target", target, "-isysroot", str(sdk_path),
                    "-framework", "Network", str(source), "-o", str(binary)], 120, allow_failure=True)
                self.result["productDiagnostics"].setdefault("appleNetworkCompiler", {})[context] = (
                    network_diagnostics.compiler_observation(self.output(proof, stream="stderr"), source))
                need(proof["productExitCode"] == 0, "Native diagnostic compilation failed", "PRODUCT_FAILED")
                for mode in network_diagnostics.MODES:
                    argv = [str(binary), mode]
                    if context == "simulator":
                        # Exact public launch mode used by the pinned Kotlin plugin.
                        argv = ["/usr/bin/xcrun", "simctl", "spawn", "--standalone", self.simulator, *argv]
                    proof = self.invoke(prefix + mode, argv, 45, allow_failure=True)
                    observed[context + "-" + mode] = network_diagnostics.observe(
                        self.output(proof), context, mode, proof["productExitCode"])
        finally:
            self.retire_created_simulator("network-probe-retire")
        need(len(observed) == len(network_diagnostics.CONTEXTS) * len(network_diagnostics.MODES) and
             all(row["observation"]["probeExit"] == 0 for row in observed.values()),
             "One or more OS primitive diagnostics failed; not product qualification", "PRODUCT_FAILED")

    def kvm_snapshot(self, purpose):
        info = Path("/dev/kvm").stat()
        proof = self.invoke(purpose, ["getfacl", "-cp", "/dev/kvm"], 30, finalizer=purpose.endswith("after"))
        return {"device": info.st_dev, "inode": info.st_ino, "rdev": info.st_rdev, "mode": info.st_mode,
                "uid": info.st_uid, "gid": info.st_gid, "aclSha256": hashlib.sha256(self.output(proof)).hexdigest()}

    def art_runtime(self):
        proof = self.invoke("android-art", [sys.executable, "scripts/run-android-art-smoke.py", "run"], BOUNDS["art-runtime"], allow_failure=True)
        result = self.runner.read_json(self.state / "evidence/android-art/result.json")
        self.result["artResultSha256"] = self.runner.file_digest(self.state / "evidence/android-art/result.json")
        need(result["source"] == self.context["source"] and result["status"] == "PASS" and proof["productExitCode"] == 0,
             "ART scenarios failed", "PRODUCT_FAILED")
        need([s["api"] for s in result["scenarios"]] == [37, 24, 25] and all(s["status"] == "PASS" for s in result["scenarios"]),
             "Incomplete ART scenario inventory")
        for path in (self.state / "evidence").glob("*/receipt.json"):
            leaf = self.runner.read_json(path)
            if proof["id"] in leaf.get("ancestorInvocationIds", []):
                self.checker.validate(leaf, 0, leaf["purpose"], ROOT, self.wrapper, leaf["requestedArgv"])
                need(leaf["sourceBefore"] == self.context["source"] and leaf["jobId"] == self.context["id"] and
                     leaf["ownership"]["discoveryErrors"] == [], "Nested ART ownership failed")

    def finish(self):
        if self.simulator:
            try:
                if self.simulator_state("simulator-finalization-before", True)["state"] != "Shutdown":
                    self.invoke("owned-simulator-shutdown", ["/usr/bin/xcrun", "simctl", "shutdown", self.simulator], 120, finalizer=True)
                need(self.simulator_state("simulator-shutdown-verified", True)["state"] == "Shutdown", "Simulator shutdown unverified")
                self.invoke("owned-simulator-delete", ["/usr/bin/xcrun", "simctl", "delete", self.simulator], 120, finalizer=True)
                self.simulator_deleted = True
                self.simulator_state("simulator-deletion-verified", True)
                self.result["simulatorRetired"] = True
            except BaseException as error:
                self.result["errors"].append({"finalizer": "simulator", "error": str(error)})
        if self.kvm:
            try:
                need(self.kvm == self.kvm_snapshot("kvm-policy-after"), "KVM policy changed")
                self.result["kvmPolicyUnchanged"] = True
            except BaseException as error:
                self.result["errors"].append({"finalizer": "kvm", "error": str(error)})
        try:
            self.result["sourceAfter"] = self.runner.source_snapshot(ROOT)
            need(self.result["sourceAfter"] == self.context["source"], "Source changed")
            self.runner.context_at(str(self.state))
        except BaseException as error:
            self.result["errors"].append({"finalizer": "source", "error": str(error)})
        if not self.result["errors"] and not self.unsafe and all(row["status"] == "PASS" for row in self.result["phases"].values()):
            self.result["result"] = "PASS"
        self.result["finishedUtc"] = self.runner.utc()
        self.runner.write_new_json(self.private / "result.json", self.result)

    def run(self):
        try:
            controls = self.phase("native-controls", self.native_controls)
            if not self.admission_only:
                toolchain = self.phase("toolchain", self.toolchain, controls)
                if self.intel_investigation:
                    self.investigate_intel(toolchain)
                elif self.lane == "android-art":
                    kvm = self.phase("kvm-admission", self.kvm_admission, controls and toolchain)
                    self.phase("art-runtime", self.art_runtime, controls and toolchain and kvm)
                else:
                    tools = self.phase("tool-installation", self.install_apple_tools, controls and toolchain)
                    self.phase("archive-controls", lambda: self.invoke("archive-controls", ["/bin/bash", "scripts/tests/check-embedded-jmdns-aar.sh"], BOUNDS["archive-controls"]), tools)
                    multicast = self.phase("multicast-admission", self.multicast_admission, tools)
                    simulator = self.phase("simulator-admission", self.select_simulator, tools)
                    if multicast:
                        self.phase("full-platform", lambda: self.platform_tests(True), simulator)
                    else:
                        self.phase("full-platform", lambda: None, False)
                        self.phase("scoped-native", lambda: self.platform_tests(False), simulator)
                    if self.lane == "apple-arm64":
                        self.phase("owned-project-controls", self.owned_project_controls, tools)
                        self.phase("owned-native-helper-abi", self.owned_native_helper, simulator and tools)
                    self.phase("abi", lambda: self.compile_phase("abi"), tools)
                    self.phase("dokka", lambda: self.compile_phase("dokka"), tools)
                    frameworks = self.phase("rpc-frameworks", lambda: self.compile_phase("rpc-frameworks"), tools)
                    self.phase("swift-api", self.swift_api, frameworks)
                    self.phase("sbom", self.sbom, tools)
                    producer = self.phase("apple-producer", self.apple_producer, tools)
                    project = self.phase("apple-project", self.apple_project, producer)
                    self.phase("swift-runtime", self.swift_runtime, project and simulator)
                    if self.lane == "apple-arm64":
                        self.phase("owned-swift-lifecycle", lambda: self.owned_swift(False), project and simulator)
                        # An ordinary assertion failure does not erase the independent
                        # case; unproven ownership/retirement still blocks it in phase().
                        self.phase("owned-swift-cancellation", lambda: self.owned_swift(True), project and simulator)
        finally:
            self.finish()
        return 0 if self.result["result"] == "PASS" else 1


def collect(lane, admission_only=False, investigation=None):
    admit_event(os.environ, platform.system(), platform.machine(), lane)
    runner = module("rpc_collect_leaf_policy", "run-audit-command.py")
    parent = runner.absolute_path(os.environ["RPC_QUALIFICATION_PARENT"])
    need(parent.is_relative_to(Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)), "Unowned collector path")
    state = parent / "state"
    path = state / "private/result.json"
    if path.exists():
        result = runner.read_json(path)
        state, context = runner.context_at(str(state))
        need(result["source"] == context["source"], "Collector source context differs")
        checker = module("rpc_collector_receipt_checker", "check-audit-receipt.py")
        wrapper = ROOT / ("gradlew.bat" if os.name == "nt" else "gradlew")
        invalid = False
        for row in result["commands"]:
            try:
                alias = state / "private" / (row["purpose"] + ".json")
                proof = runner.read_json(alias)
                checker.validate(proof, row["rawExitCode"], row["purpose"], ROOT, wrapper, row["argv"])
                need(proof["sourceBefore"] == context["source"] and proof["jobId"] == context["id"] and
                     proof["ancestorInvocationIds"] == [] and proof["ownership"]["discoveryErrors"] == [] and
                     runner.file_digest(alias) == row["receiptSha256"] == runner.file_digest(
                         state / "evidence" / proof["id"] / "receipt.json"), "Collector receipt binding differs")
                row["verified"] = True
            except Exception:
                row["verified"] = False
                invalid = True
        if invalid or runner.source_snapshot(ROOT) != context["source"]:
            result["result"] = "FAIL"
        if result["result"] == "PASS":
            required = required_phases(lane, admission_only, investigation)
            need(set(result["phases"]) == required and all(row["status"] == "PASS" for row in result["phases"].values()) and
                 result["sourceAfter"] == context["source"] and not result["errors"] and
                 (admission_only or result.get("kvmPolicyUnchanged" if lane == "android-art" else "simulatorRetired") is True),
                 "Incomplete phase inventory/finalization cannot pass")
    else:
        source = runner.source_snapshot(ROOT)
        result = {"source": source, "lane": lane, "admissionOnly": admission_only,
                  "intelInvestigation": investigation, "result": "INCOMPLETE"}
    need(result.get("admissionOnly") is admission_only and result.get("intelInvestigation") == investigation,
         "Collector mode differs")
    need(result["source"]["commit"] == os.environ["GITHUB_SHA"] and result["lane"] == lane, "Unrelated result")
    public = parent / "public"
    public.mkdir(mode=0o700)
    runner.write_new_json(public / "summary.json", public_summary(result))
    print("QUALIFICATION " + lane + " " + result["result"] + "; sanitized evidence only", flush=True)
    return 0


def required_phases(lane, admission_only, investigation=None):
    need(lane in HOSTS and type(admission_only) is bool, "Invalid phase inventory mode")
    need(investigation in (None, "native", "cold-boot", "network"), "Unknown diagnostic inventory")
    if investigation:
        need(lane == "apple-x64" and not admission_only, "Diagnostic inventory requires actual Intel")
        return {"native-controls", "toolchain", "simulator-admission"} | (
            {"intel-cold-boot"} if investigation == "cold-boot" else
            {"apple-network-diagnostic"} if investigation == "network" else
            {"tool-installation", "multicast-admission", "scoped-native"})
    required = {"native-controls"} if admission_only else {"native-controls", "toolchain", "kvm-admission", "art-runtime"} if lane == "android-art" else {
                "native-controls", "toolchain", "tool-installation", "archive-controls", "multicast-admission",
                "simulator-admission", "full-platform", "abi", "dokka", "rpc-frameworks", "swift-api", "sbom",
                "apple-producer", "apple-project", "swift-runtime"}
    if lane == "apple-arm64" and not admission_only:
        required |= ARM_PHASES
    return required


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("run", "collect"))
    parser.add_argument("--lane", required=True, choices=tuple(HOSTS))
    parser.add_argument("--admission-only", action="store_true", help="Diagnose native executor admission only; never run product gates")
    parser.add_argument("--intel-investigation", choices=("native", "cold-boot", "network"),
                        help="Explicit Intel-only diagnostic subset, never full matrix qualification")
    args = parser.parse_args()
    try:
        return collect(args.lane, args.admission_only, args.intel_investigation) if args.operation == "collect" else \
            Qualification(args.lane, args.admission_only, args.intel_investigation).run()
    except BaseException:
        # Deliberately do not print exception messages/tracebacks to hosted logs.
        # The private command receipts remain the original, detailed evidence.
        print("QUALIFICATION admission/finalization failed; no readiness claim", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
