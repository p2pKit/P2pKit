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
REF = "refs/heads/work/rpc-lan-20260927-054728-8b1b11da"
MARKER = "[rpc-qualify]"
HOSTS = {
    "apple-arm64": ("Darwin", "arm64", "macos-arm64", "26", "26.5"),
    "apple-x64": ("Darwin", "x86_64", "macos-x64", "15", "26.3"),
    "android-art": ("Linux", "x86_64", "linux-x64", None, None),
}
PHASES = ("native-controls", "toolchain", "tool-installation", "archive-controls", "multicast-admission",
          "simulator-admission", "full-platform", "scoped-native", "abi", "dokka", "rpc-frameworks",
          "swift-api", "sbom", "apple-producer", "apple-project", "swift-runtime", "kvm-admission", "art-runtime")
STATUSES = ("PASS", "FAIL", "NOT_RUN", "BLOCKED_PREREQUISITE")
CODES = ("CHECK_FAILED", "PRODUCT_FAILED", "OWNERSHIP_UNPROVEN", "PREREQUISITE_MISSING")
PURPOSES = frozenset((
    "native-controls", "jdk17", "jdk21", "macos-version", "xcode-version", "xcode-first-launch",
    "rosetta-admission", "intel-hardware", "android-compile-platforms", "pinned-xcodegen", "archive-controls",
    "multicast-reviewed-dependency", "multicast-vendor-compile", "multicast-fixture-compile", "multicast-readiness-control",
    "simulator-runtimes", "simulator-create", "simulator-initial", "full-platform", "scoped-native", "all-library-abi",
    "strict-dokka", "rpc-frameworks", "swift-sdk-iphoneos", "swift-sdk-iphonesimulator", "swift-api-iosarm64",
    "swift-api-iosx64", "swift-api-iossimulatorarm64", "sbom-producer", "sbom-validation", "xcframework-build",
    "xcframework-minimum-os", "xcode-project", "swift-simulator-readiness", "swift-simulator-ready", "swift-unit-ui",
    "xcresult-actions", *("xcresult-tests-" + str(index) for index in range(8)), "simulator-finalization-before",
    "owned-simulator-shutdown", "simulator-shutdown-verified", "owned-simulator-delete", "simulator-deletion-verified",
    "kvm-policy-before", "kvm-policy-after", "android-art",
))
BOUNDS = {"native-controls": 1800, "platform": 7200, "swift-readiness": 120, "swift-runtime": 7200,
          "art-runtime": 7200, "multicast-admission": 45, "archive-controls": 180}
MAX_FILE = 16 * 1024 * 1024
MAX_LOG = 256 * 1024 * 1024
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


def unittest_count(raw):
    match = re.search(r"\nRan ([1-9][0-9]*) tests? in [0-9.]+s\s+OK\s*$", raw)
    need(match is not None, "Native controls are missing, failed or skipped")
    return int(match[1])


def control_failures(raw):
    source = ast.parse(bounded(ROOT / "scripts/tests/run-audit-command-test.py").decode())
    admitted = {node.name for node in ast.walk(source) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
    return [{"outcome": match[1], "method": match[2]} for match in re.finditer(
        r"(?m)^(FAIL|ERROR): (test_[A-Za-z0-9_]+) \([A-Za-z0-9_.]+\)$", raw) if match[2] in admitted]


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
    return sum(len(methods(name)) for name in ("PurePolicyTests", "DarwinObservationTests", native))


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
                 "swiftUnitPassed", "swiftUiPassed"):
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
        commands.append({"purpose": label, "exitCode": code, "finalizationVerified": row.get("verified") is True})
    failures = private.get("controlFailures", [])
    need(type(failures) is list and len(failures) <= 256 and failures == control_failures("\n".join(
        str(row.get("outcome")) + ": " + str(row.get("method")) + " (__main__.Fixture)" for row in failures)),
        "Invalid public control failure")
    policy = module("rpc_public_marker_policy", "run-rpc-hosted-validation.py")
    markers = private.get("multicastMarkers", [])
    need(type(markers) is list and len(markers) <= 160 and all(type(line) is str and any(
         pattern.fullmatch(line) for pattern in policy.FIXTURE_MARKERS) for line in markers), "Invalid public multicast marker")
    return {"schema": 1, "scope": "FEATURE_ONLY_AUTOMATED_CHECKS_NOT_RELEASE_DEVICE_OR_CAPACITY",
            "source": {key: source[key] for key in ("commit", "tree")}, "lane": private["lane"], "result": outcome,
            "phases": phases, "counts": counts, "countsSemantics": "ADMITTED_COUNTS_ONLY_NOT_ATTEMPT_COUNTS", "commands": commands,
            "controlFailures": failures, "multicastMarkers": markers,
            "sourceUnchanged": private.get("sourceAfter") == source,
            "simulatorRetired": private.get("simulatorRetired") is True,
            "kvmPolicyUnchanged": private.get("kvmPolicyUnchanged") is True,
            "foundationStatus": "NOT_READY", "externalPublication": False, "physicalQualification": False,
            "rpcCapacityQualification": False}


class Qualification:
    def __init__(self, lane):
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
        need(MARKER in self.runner.git(ROOT, "show", "-s", "--format=%B", "HEAD").decode(), "Unmarked source commit")
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
        self.result = {"lane": lane, "source": self.context["source"], "result": "FAIL", "commands": [],
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
        translated = self.invoke("rosetta-admission", ["/usr/sbin/sysctl", "-in", "sysctl.proc_translated"], 45, allow_failure=True)
        need((translated["productExitCode"], self.output(translated).strip()) in ((0, b"0"), (1, b"")), "Rosetta/unclassified host")
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
        return matches[0]

    def platform_tests(self, full):
        arch = "arm64" if self.lane == "apple-arm64" else "x64"
        profile = "full" if full else "ios-" + arch
        token = uuid.uuid4().hex
        coverage = ROOT / "build/reports/platform-tests" / token / "execution.json"
        need(not coverage.parent.exists(), "Coverage must be fresh")
        argv = [*self.gate.PROFILES[profile], *self.gate.FLAGS, "--init-script", str(ROOT / "gradle/platform-test-coverage.init.gradle"),
            "-Pp2pkit.testCoverageRoot=" + str(ROOT), "-Pp2pkit.testCoverageToken=" + token,
            "--init-script", str(self.sim_init), "--no-configure-on-demand", "--warning-mode=fail"]
        proof = self.invoke("full-platform" if full else "scoped-native", argv, BOUNDS["platform"], "gradle", allow_failure=True)
        report = self.gate.read_json(coverage)
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
        need(bundle.is_dir(), "No actual XCTest bundle")
        entries = self.runner.regular_report_files(bundle, [0])
        need(entries and sum(p.stat().st_size for p in entries) <= 1024 * 1024 * 1024, "Invalid/bounded native result")
        original = {str(p.relative_to(bundle)): self.runner.file_digest(p) for p in entries}
        self.runner.write_new_json(self.private / "xcresult-manifest.json", {"files": original})
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
        self.result["nestedProvenance"] = nested
        actions = self.invoke("xcresult-actions", ["/usr/bin/xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json", "--path", str(bundle)], 120)
        data = json.loads(self.output(actions))
        refs = {row["actionResult"]["testsRef"]["id"]["_value"] for row in data.get("actions", {}).get("_values", [])
                if "testsRef" in row.get("actionResult", {})}
        need(0 < len(refs) <= 8, "Missing/excessive XCTest summaries")
        objects = []
        for index, identifier in enumerate(sorted(refs)):
            need(re.fullmatch(r"[A-Za-z0-9_+=/~\-]{1,512}", identifier), "Invalid XCTest reference")
            entry = self.invoke("xcresult-tests-" + str(index), ["/usr/bin/xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json",
                "--path", str(bundle), "--id", identifier], 120)
            objects.append(json.loads(self.output(entry)))
        swift = module("rpc_pure_swift_assessor", "run-audit-host.py")
        actual = swift.assess_swift(objects)
        need(set(actual) == set(expected) and all({case["identifier"] for case in actual[target]} == expected[target] for target in expected),
             "Actual XCTest methods differ from source")
        need(original == {str(p.relative_to(bundle)): self.runner.file_digest(p) for p in self.runner.regular_report_files(bundle, [0])},
             "Native result changed during inspection")
        need(proof["productExitCode"] == 0 and b"** TEST SUCCEEDED **" in self.output(proof, MAX_LOG), "Swift tests failed", "PRODUCT_FAILED")
        self.result["counts"].update(swiftUnitPassed=len(actual["p2pkit-sample-tests"]), swiftUiPassed=len(actual["p2pkit-sample-uitests"]))

    def kvm_admission(self):
        # Never setfacl/chmod/sudo or manufacture the legacy kvm-restored sentinel.
        path = Path("/dev/kvm")
        need(path.exists() and not path.is_symlink() and stat.S_ISCHR(path.stat().st_mode) and
             os.access(path, os.R_OK | os.W_OK), "Existing KVM access is required; no policy change is authorized", "PREREQUISITE_MISSING")
        with path.open("rb+", buffering=0):
            pass
        self.kvm = self.kvm_snapshot("kvm-policy-before")

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
            toolchain = self.phase("toolchain", self.toolchain, controls)
            if self.lane == "android-art":
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
                self.phase("abi", lambda: self.compile_phase("abi"), tools)
                self.phase("dokka", lambda: self.compile_phase("dokka"), tools)
                frameworks = self.phase("rpc-frameworks", lambda: self.compile_phase("rpc-frameworks"), tools)
                self.phase("swift-api", self.swift_api, frameworks)
                self.phase("sbom", self.sbom, tools)
                producer = self.phase("apple-producer", self.apple_producer, tools)
                project = self.phase("apple-project", self.apple_project, producer)
                self.phase("swift-runtime", self.swift_runtime, project and simulator)
        finally:
            self.finish()
        return 0 if self.result["result"] == "PASS" else 1


def collect(lane):
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
            required = {"native-controls", "toolchain", "kvm-admission", "art-runtime"} if lane == "android-art" else {
                "native-controls", "toolchain", "tool-installation", "archive-controls", "multicast-admission",
                "simulator-admission", "full-platform", "abi", "dokka", "rpc-frameworks", "swift-api", "sbom",
                "apple-producer", "apple-project", "swift-runtime"}
            need(set(result["phases"]) == required and all(row["status"] == "PASS" for row in result["phases"].values()) and
                 result["sourceAfter"] == context["source"] and not result["errors"] and
                 result.get("kvmPolicyUnchanged" if lane == "android-art" else "simulatorRetired") is True,
                 "Incomplete phase inventory/finalization cannot pass")
    else:
        source = runner.source_snapshot(ROOT)
        result = {"source": source, "lane": lane, "result": "INCOMPLETE"}
    need(result["source"]["commit"] == os.environ["GITHUB_SHA"] and result["lane"] == lane, "Unrelated result")
    public = parent / "public"
    public.mkdir(mode=0o700)
    runner.write_new_json(public / "summary.json", public_summary(result))
    print("QUALIFICATION " + lane + " " + result["result"] + "; sanitized evidence only", flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("run", "collect"))
    parser.add_argument("--lane", required=True, choices=tuple(HOSTS))
    args = parser.parse_args()
    try:
        return collect(args.lane) if args.operation == "collect" else Qualification(args.lane).run()
    except BaseException:
        # Deliberately do not print exception messages/tracebacks to hosted logs.
        # The private command receipts remain the original, detailed evidence.
        print("QUALIFICATION admission/finalization failed; no readiness claim", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
