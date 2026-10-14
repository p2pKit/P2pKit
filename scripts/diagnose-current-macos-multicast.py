#!/usr/bin/env python3
"""Current ARM runner diagnosis only; never a replacement for complete-gate.

Reuse the maintained native executor, control inventory, direct-Java fixture and
closed OS observations after the unchanged fresh-audit-session bootstrap drops
privilege. No Terminal/permission/network configuration is changed.
Network.framework selects independently; its result is NOT a path proof
for the Java fixture's captured interface. Native Python/JDK probes are matched.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import os
from pathlib import Path
import platform
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
REF = "refs/heads/work/rpc-macos-multicast-diagnostic-20261014"
SCOPE = "CURRENT_ARM_MULTICAST_DIAGNOSIS_NOT_COMPLETE_GATE_OR_RELEASE"
COMPONENT_REF = "refs/heads/work/rpc-macos-ci-context-20261014"
COMPONENT_SCOPE = "CURRENT_ARM_TERMINAL_COMPONENT_CONTROLS_NOT_MULTICAST_OR_COMPLETE_GATE"

BOOL = r"(?:true|false)"
KNOWN = r"(?:true|false|UNKNOWN)"
JAVA_FAILURE = r"(?:NONE|java\.(?:net\.(?:NoRouteToHostException|SocketException|BindException)|" \
    r"io\.IOException|lang\.(?:IllegalArgumentException|UnsupportedOperationException|SecurityException)))"
PYTHON_FAILURE = r"(?:NONE|OSError|PermissionError|BlockingIOError|InterruptedError|TimeoutError|ValueError|RuntimeError)"
STAGE = r"(?:ADMISSION|IDENTITY|SOCKET|REUSE|BIND|INTERFACE|JOIN|TTL|SEND)"
SENT = r"(?:[0-9]|[1-3][0-9]|4[0-2])"
PRIMITIVE_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r"startup primitivePair observation=POST_FAILURE scope=CAPTURED_IPV4_MDNS interpretation=KERNEL_ACCEPTANCE_ONLY",
    r"startup primitivePair attempted=false reason=(?:CONTEXT_OR_CAPTURE_NOT_MATCHED|CANONICAL_INTERPRETER_REQUIRED|CURRENT_INTERFACE_NOT_MATCHED)",
    r"startup primitive=JDK_MULTICAST reuseAddress=" + BOOL + r" reusePort=" + BOOL,
    r"startup primitive=JDK_MULTICAST stage=" + STAGE + r" result=(?:FAIL|KERNEL_ACCEPTED) failureClass=" + JAVA_FAILURE
    + r" errno=UNKNOWN sentBytes=" + SENT + r" socketClosed=(?:true|false|NOT_CREATED) closeFailureClass=" + JAVA_FAILURE,
    r"startup primitive=PYTHON_IPV4 attempted=false reason=CURRENT_INTERFACE_NOT_MATCHED",
    r"startup primitive=PYTHON_IPV4 processCompleted=" + BOOL + r" exitZero=" + KNOWN,
    r"startup primitive=PYTHON_IPV4 reportValid=" + BOOL,
    r"startup primitive=PYTHON_IPV4 stage=" + STAGE + r" result=(?:FAIL|KERNEL_ACCEPTED) failureClass=" + PYTHON_FAILURE
    + r" errno=(?:UNKNOWN|-?[0-9]{1,3}) sentBytes=" + SENT
    + r" socketClosed=(?:true|false|NOT_CREATED) closeFailureClass=" + PYTHON_FAILURE,
    r"startup primitive=PYTHON_IPV4 processFailureClass=(?:java.lang.InterruptedException|java.io.IOException)",
    r"startup primitive=PYTHON_IPV4 processReaped=" + BOOL,
))


def primitive_projection(raw):
    require(type(raw) is bytes and len(raw) <= 16 * 1024 * 1024, "Bounded primitive transcript required")
    candidates = [line for line in raw.decode(errors="replace").splitlines() if line.startswith("startup primitive")]
    require(len(candidates) <= 32, "Excessive primitive observations")
    admitted = [line for line in candidates if any(pattern.fullmatch(line) for pattern in PRIMITIVE_PATTERNS)]
    return {"markers": admitted, "unclassifiedPrimitiveLineCount": len(candidates) - len(admitted),
            "logSha256": hashlib.sha256(raw).hexdigest(), "logBytes": len(raw)}


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_session(record):
    expected = {"schema": 1, "scope": "PROCESS_LOCAL_AUDIT_SESSION_NOT_OWNERSHIP_OR_PRODUCT_ADMISSION",
                "freshAssignedSession": True, "auditPolicyPreserved": True,
                "invokingCredentialsRestored": True, "rootCannotBeRegained": True,
                "privilegedObservationOrProductExecution": False}
    require(type(record) is dict and set(record) == {*expected, "previousSessionAssigned"},
            "Exact bootstrap record required")
    require(type(record["previousSessionAssigned"]) is bool and all(
        type(record[key]) is type(value) and record[key] == value for key, value in expected.items()),
        "Unproven bootstrap boundary")
    return record


def admit(env, system, machine, uid, euid, profile="multicast"):
    require(profile in ("multicast", "terminal-components"), "Unknown diagnostic profile")
    require(system == "Darwin" and machine == "arm64" and uid == euid and uid > 0,
            "Native ordinary-user ARM macOS required")
    expected = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                "GITHUB_REPOSITORY": "p2pKit/P2pKit",
                "GITHUB_REF": REF if profile == "multicast" else COMPONENT_REF,
                "GITHUB_EVENT_NAME": "push", "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64"}
    require(all(env.get(key) == value for key, value in expected.items()), "Wrong diagnostic event/context")
    require(re.fullmatch(r"[0-9a-f]{40}", env.get("GITHUB_SHA", "")), "Exact source required")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(re.fullmatch(r"[1-9][0-9]{0,19}", env.get(key, "")), "Exact run/attempt required")
    for key in ("P2PKIT_JMDNS_FIXTURE_IPV4", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS",
                "JAVA_OPTS", "GRADLE_OPTS"):
        require(not env.get(key), "Network/JVM overrides refused")


class Diagnostic:
    def __init__(self, profile="multicast"):
        admit(os.environ, platform.system(), platform.machine(), os.getuid(), os.geteuid(), profile)
        self.profile = profile
        require(os.getgid() == os.getegid() and os.getgid() > 0, "Original ordinary group required")
        require(Path(sys.executable).is_absolute() and Path(sys.executable) == Path(sys.executable).resolve(strict=True),
                "Execute the canonical interpreter; do not rewrite its identity")
        require(Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True) == ROOT, "Wrong checkout")
        self.runner = load("mdns_executor", "run-audit-command.py")
        self.checker = load("mdns_receipt", "check-audit-receipt.py")
        self.qualification = load("mdns_components", "run-rpc-qualification.py")
        self.policy = load("mdns_markers", "run-rpc-hosted-validation.py")
        self.network = load("mdns_network", "rpc_apple_network_diagnostics.py")
        temporary = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
        session = temporary / ("p2pkit-mdns-session-" + os.environ["GITHUB_RUN_ID"] + "-" +
                               os.environ["GITHUB_RUN_ATTEMPT"])
        session_record = validate_session(self.runner.read_json(session / "session-admission.json"))
        self.parent = temporary / ("p2pkit-mdns-" + os.environ["GITHUB_RUN_ID"] + "-" +
                                   os.environ["GITHUB_RUN_ATTEMPT"])
        require(not self.parent.is_relative_to(ROOT) and not ROOT.is_relative_to(self.parent),
                "Diagnostic state must be outside source")
        self.parent.mkdir(mode=0o700)
        self.private = self.parent / "private"
        self.private.mkdir(mode=0o700)
        self.export = self.parent / "export"
        self.export.mkdir(mode=0o700)
        self.state = self.parent / "state"
        self.wrapper = ROOT / "gradlew"
        self.lane = "apple-arm64"
        with (self.private / "init.log").open("x") as log, contextlib.redirect_stdout(log):
            self.runner.initialize(argparse.Namespace(root=str(ROOT), state=str(self.state),
                expected_commit=os.environ["GITHUB_SHA"], host="macos-arm64"))
        self.state, self.context = self.runner.context_at(str(self.state))
        (self.state / "work").mkdir(mode=0o700)
        os.environ[self.runner.STATE_ENV] = str(self.state)
        # No Maven/GitHub/signing credential is needed in any diagnostic child.
        for key in list(os.environ):
            if key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN") or key.upper().startswith(
                    ("SIGNING_", "ORG_GRADLE_PROJECT_SIGNING", "MAVEN_CENTRAL_", "SONATYPE_")):
                os.environ.pop(key)
        self.result = {"scope": SCOPE if profile == "multicast" else COMPONENT_SCOPE,
                       "releaseCredit": False, "completeGateCredit": False,
                       "source": self.context["source"], "run": os.environ["GITHUB_RUN_ID"],
                       "attempt": os.environ["GITHUB_RUN_ATTEMPT"], "result": "FAIL",
                       "counts": {}, "commands": [], "observations": {}, "fixture": "NOT_RUN"}
        self.result["bootstrap"] = session_record
        self.proofs = {}

    def output(self, proof, maximum=16 * 1024 * 1024, stream="stdout"):
        require(stream in ("stdout", "stderr"), "Invalid stream")
        return self.qualification.bounded(self.state / "evidence" / proof["id"] /
                                          ("product." + stream + ".log"), maximum)

    def invoke(self, purpose, argv, timeout, allow_failure=False):
        require(not any(row["purpose"] == purpose for row in self.result["commands"]), "No automatic retries")
        alias = self.private / (purpose + ".json")
        row = {"purpose": purpose, "timeoutSeconds": timeout, "finalizationVerified": False}
        self.result["commands"].append(row)
        print("START " + purpose, flush=True)
        with (self.private / (purpose + ".log")).open("x") as log, \
                contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            code = self.runner.main(["--cwd", str(ROOT), "--wrapper", str(self.wrapper), "--kind", "command",
                "--purpose", purpose, "--timeout", str(timeout), "--receipt", str(alias), "--", *argv])
        row["exit"] = code
        proof = self.runner.read_json(alias)
        stop = b"".join(self.qualification.bounded(self.state / "evidence" / proof["id"] /
                      ("stop." + stream + ".log"), 16 * 1024 * 1024)
                       for stream in ("stdout", "stderr")
                       if (self.state / "evidence" / proof["id"] / ("stop." + stream + ".log")).is_file())
        row["diagnostic"] = self.qualification.receipt_diagnostic(proof, stop.decode(errors="replace"))
        self.checker.validate(proof, code, purpose, ROOT, self.wrapper, argv)
        require(proof["jobId"] == self.context["id"] and proof["host"] == "macos-arm64" and
                proof["kind"] == "command" and proof["gradleHome"] == self.context["gradleHome"] and
                proof["sourceBefore"] == self.context["source"] and proof["ancestorInvocationIds"] == [] and
                proof["executedArgv"] == argv and proof["ownership"]["discoveryErrors"] == [] and
                not proof.get("cancelledSignals") and not proof.get("cancelRequested"), "Wrong/unresolved ownership")
        canonical = self.state / "evidence" / proof["id"] / "receipt.json"
        require(proof == self.runner.read_json(canonical) and
                self.runner.file_digest(alias) == self.runner.file_digest(canonical), "Receipt aliases differ")
        row.update(finalizationVerified=True, receiptSha256=self.runner.file_digest(alias))
        self.proofs[purpose] = proof
        print("END " + purpose + " exit=" + str(code), flush=True)
        require(code == 0 or allow_failure, "Diagnostic prerequisite failed")
        return proof

    def execute(self):
        # Exact existing control inventory and unchanged owned execution/stop policy.
        self.qualification.Qualification.native_controls(self)
        if self.profile == "terminal-components":
            # Separate explicit component run: this is not a multicast retry or
            # a replacement for any full CI command. The maintained native
            # inventory includes the real shell lifetime and new finalizer cases.
            for purpose, filename, count in (
                    ("ci-source-admission", "rpc-apple-ci-admission-test.py", 49),
                    ("ci-metadata", "rpc-apple-ci-metadata-test.py", 22),
                    ("terminal-refusal", "with-darwin-terminal-context-test.py", 28)):
                proof = self.invoke(purpose, [str(Path(sys.executable)), "-I", "-B", "-S",
                    str(ROOT / "scripts/tests" / filename)], 90)
                transcript = self.output(proof) + self.output(proof, stream="stderr")
                require(re.search(rb"(?m)^Ran " + str(count).encode() + rb" tests in [0-9.]+s$", transcript)
                        and re.search(rb"(?m)^OK$", transcript), "Incomplete component controls")
                self.result["counts"][purpose] = count
            self.result["result"] = "PASS_COMPONENT_CONTROLS_ONLY"
            return
        java = Path(os.environ["JAVA_HOME"]).resolve(strict=True) / "bin/java"
        proof = self.invoke("jdk17", [str(java), "-XshowSettings:properties", "-version"], 45)
        properties = self.output(proof, stream="stderr").decode()
        require(re.search(r"(?m)^\s*java.specification.version = 17\s*$", properties) and
                re.search(r"(?m)^\s*os.arch = aarch64\s*$", properties), "Native JDK17 required")
        try:
            # Retains all source/dependency checks and original 10s/45s bounds.
            self.qualification.Qualification.multicast_admission(self)
            self.result["fixture"] = "PASS_CONTROL_ONLY"
        except self.qualification.QualificationError as error:
            # Only the genuine product readiness failure permits independent OS
            # observations; missing/failed finalization never reaches this path.
            require(error.code == "PREREQUISITE_MISSING" and
                    str(error) == "Multicast prerequisite failed" and
                    self.result["commands"][-1]["purpose"] == "multicast-readiness-control" and
                    self.result["commands"][-1]["finalizationVerified"], "Unexpected prerequisite failure")
            self.result["fixture"] = "FAIL"

        self.result["matchedPrimitiveObservations"] = primitive_projection(
            self.output(self.proofs["multicast-readiness-control"]))

        source = ROOT / "scripts/diagnostics/apple-bonjour-probe.c"
        binary = self.state / "work/native-network-probe"
        self.invoke("network-compile", ["/usr/bin/xcrun", "--sdk", "macosx", "clang", "-std=c11",
            "-Wall", "-Wextra", "-Werror", "-fblocks", "-target", "arm64-apple-macos15.0",
            "-framework", "Network", "-framework", "CoreFoundation", str(source), "-o", str(binary)], 120)
        self.result["nativeBinarySha256"] = self.runner.file_digest(binary)
        self.result["networkFrameworkSelection"] = "INDEPENDENT_NOT_BOUND_TO_FIXTURE_INTERFACE"
        for mode in ("bsd", "multicast-path", "mdns-policy"):
            proof = self.invoke("network-" + mode, [str(binary), mode], 45, allow_failure=True)
            self.result["observations"][mode] = self.network.observe(
                self.output(proof), "host", mode, proof["productExitCode"])
        require(self.result["fixture"] == "PASS_CONTROL_ONLY" and all(
            row["exit"] == 0 for row in self.result["commands"]), "Observed multicast failure remains FAIL")
        self.result["result"] = "PASS_DIAGNOSTIC_ONLY"

    def run(self):
        try:
            self.execute()
        except Exception as error:
            # Closed class label only: raw paths, interfaces and exceptions stay private.
            self.result["failureClass"] = type(error).__name__
        finally:
            self.result["sourceUnchanged"] = self.runner.source_snapshot(ROOT) == self.context["source"]
            if not self.result["sourceUnchanged"]:
                self.result["result"] = "FAIL"
            self.runner.write_new_json(self.export / "summary.json", self.result)
        expected = "PASS_DIAGNOSTIC_ONLY" if self.profile == "multicast" else "PASS_COMPONENT_CONTROLS_ONLY"
        return 0 if self.result["result"] == expected else 1


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--profile", choices=("multicast", "terminal-components"), default="multicast")
        status = Diagnostic(parser.parse_args().profile).run()
    except Exception as failure:
        print("DIAGNOSTIC_REFUSED " + type(failure).__name__, file=sys.stderr)
        status = 125
    raise SystemExit(status)
