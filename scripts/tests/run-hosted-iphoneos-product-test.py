#!/usr/bin/env python3
"""Bounded pure controls, NOT iphoneos/native/hosted execution or acceptance.

Synthetic temporary metadata and in-memory scope/clock models only. Subprocess,
native loaders and network calls are denied by default; no JVM, Gradle, Xcode,
SDK, GPG, simulator, account, key or download is used. The positive packet below
is deliberately synthetic parser input, never an artifact or execution receipt.
"""
from __future__ import annotations

import copy
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("iphoneos_product_pure_controls", Path(__file__).resolve().parents[1] / "run-hosted-iphoneos-product.py")
app = importlib.util.module_from_spec(SPEC)
with mock.patch.object(subprocess, "Popen", side_effect=AssertionError("No subprocess in pure controls")), \
        mock.patch.object(ctypes, "CDLL", side_effect=AssertionError("No native loader in pure controls")), \
        mock.patch.object(socket, "socket", side_effect=AssertionError("No network in pure controls")):
    SPEC.loader.exec_module(app)
    AUDIT = app.load_script("run-audit-command")
    CHECKER = app.load_script("check-audit-receipt")

SHA, TREE, JOB, PRE_JOB = "a" * 40, "b" * 40, "1" * 32, "2" * 32
POLICY = b"SYNTHETIC java_policy() fixture, not a real Gradle policy\n"
ORDER = ("java17", "java21", "xcode-version", "xcode-first-launch", "memory", "iphoneos-sdk", "iphonesimulator-sdk",
         "init", "xcodegen-install", "xcframework-build", "xcode-project", "iphoneos-build", "app-vtool", "app-lipo",
         "framework-vtool", "framework-lipo", "cleanup")
CAPS = dict(zip(ORDER, (60, 60, 60, 60, 30, 60, 60, 60, 900, 7200, 600, 7200, 120, 120, 120, 120, 180)))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(value if type(value) is bytes else app.encoded(value))
    path.chmod(0o600)


def ownership(identity, job, argv, *, sinks=False):
    return {"backend": "darwin-libproc-audit-token", "scope": "controlled-marker-inheriting-descendants",
            "invocation": identity, "job": job, "discoveryErrors": [], "syntheticOnly": True,
            "launches": [{"requestedArgv": args, "resolvedArgv": args, "executable": args[0], "created": True,
                          "shell": False, "cwd": str(app.ROOT), "pid": 123 + index,
                          **({"outputMode": "caller-owned-files"} if sinks else {})} for index, args in enumerate(argv)]}


class Clock:
    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(seconds, 1.0)


class ModelScope:
    """A fake child/scope whose metadata is explicitly not native qualification."""
    def __init__(self, test, job, invocation, state, home):
        self.test, self.job, self.invocation, self.state, self.home = test, job, invocation, state, home
        self.leaders, self.launches = [], []
        self.closed = self.drained = False

    def spawn(self, argv, cwd, env, *, stdout, stderr):
        self.argv, self.env, self.outputs = argv, env, (stdout, stderr)
        self.test.events.append("spawn")
        stdout.write(self.test.output)
        stdout.flush()
        stderr.write(b"synthetic stderr\n")
        stderr.flush()
        child = SimpleNamespace(poll=self.test.poll)
        self.leaders.append(child)
        if self.test.partial_spawn:
            raise OSError("synthetic partial launch")
        return child

    def discover(self):
        self.test.events.append("discover")
        return []

    def drain(self):
        self.drained = True
        self.test.events.append("drain")
        self.test.clock.now += self.test.drain_seconds
        if self.test.drain_error:
            raise OSError("synthetic unknown retirement")
        return []

    def description(self):
        return ownership(self.invocation, self.job, [self.argv], sinks=True)

    def close(self):
        self.closed = True
        self.test.events.append("close")
        if self.test.close_error:
            raise OSError("synthetic scope close failure")


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="iphoneos-pure-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.source = self.base / "source"
        self.source.mkdir()
        save(self.source / "samples/iosApp/Info.plist", b"synthetic tracked source\n")
        self.source_state = {"commit": SHA, "tree": TREE, "status": "", "diffSha256": app.digest(b"")}
        self.env = {
            "PATH": "/usr/bin:/bin", "HOME": str(self.base), "TMPDIR": str(self.base),
            "JAVA_HOME": str(self.base / "jdk17"), "P2PKIT_AUDIT_JDK21": str(self.base / "jdk21"),
            "ANDROID_HOME": str(self.base / "android"), "DEVELOPER_DIR": app.DEVELOPER,
            "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": app.REPOSITORY,
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
            "GITHUB_WORKFLOW": "Desktop cross-host", "GITHUB_JOB": app.JOB, "GITHUB_SHA": SHA, "GITHUB_WORKFLOW_SHA": SHA,
            "GITHUB_REF": "refs/heads/work/synthetic-parser-fixture", "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64", "RUNNER_TEMP": str(self.base),
            "P2PKIT_OPERATION": app.JOB, "P2PKIT_EXPECTED_SHA": SHA, "P2PKIT_EXPECTED_TREE": TREE,
            "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_EVENT_PATH": str(self.base / "event.json"),
            "GITHUB_OUTPUT": str(self.base / "output"), "P2PKIT_IPHONEOS_RUN_OUTCOME": "success",
        }
        self.env["GITHUB_WORKFLOW_REF"] = app.REPOSITORY + "/" + app.WORKFLOW + "@" + self.env["GITHUB_REF"]
        self.event = {"repository": {"full_name": app.REPOSITORY}, "ref": self.env["GITHUB_REF"],
                      "inputs": {"operation": app.JOB, "expected_sha": SHA, "expected_tree": TREE,
                                 "reviewed_base": "", "evidence_public_key": "", "evidence_fingerprint": ""}}
        save(Path(self.env["GITHUB_EVENT_PATH"]), self.event)
        save(Path(self.env["GITHUB_OUTPUT"]), b"")
        self.admitted = app.dispatch_identity(self.env, self.event, self.source_state)
        self.admitted.update(eventSha256=app.digest(Path(self.env["GITHUB_EVENT_PATH"]).read_bytes()),
                             pythonExecutable=str(Path(sys.executable).resolve()))
        self.work = self.base / "p2pkit-iphoneos-work-123-2"
        self.public = self.base / "p2pkit-iphoneos-evidence-123-2"
        self.output, self.poll = b"synthetic stdout\n", lambda: 0
        self.events, self.scopes = [], []
        self.partial_spawn = self.drain_error = self.close_error = False
        self.drain_seconds, self.clock = 0, Clock()
        for patcher in (
            mock.patch.object(app, "ROOT", self.source),
            mock.patch.object(app, "load_script", side_effect=lambda name: {"run-audit-command": AUDIT, "check-audit-receipt": CHECKER}[name]),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("No subprocess in pure controls")),
            mock.patch.object(ctypes, "CDLL", side_effect=AssertionError("No native loader in pure controls")),
            mock.patch.object(socket, "socket", side_effect=AssertionError("No network in pure controls")),
            mock.patch.object(socket, "create_connection", side_effect=AssertionError("No network in pure controls")),
            mock.patch.object(AUDIT, "host_role", return_value=app.ROLE),
            mock.patch.object(AUDIT, "source_snapshot", side_effect=lambda _: copy.deepcopy(self.source_state)),
            mock.patch.object(AUDIT, "git", side_effect=AssertionError("No git subprocess in pure controls")),
            mock.patch.object(AUDIT, "make_scope", side_effect=AssertionError("No real scope in pure controls")),
            mock.patch.object(AUDIT, "inspect_disposable_tree", return_value={"syntheticOnly": True}),
            mock.patch.object(AUDIT, "java_policy", return_value=(POLICY, [self.env["JAVA_HOME"], self.env["P2PKIT_AUDIT_JDK21"]])),
            mock.patch.object(signal, "signal", return_value=None),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def driver(self):
        return app.Driver(self.env, self.admitted, AUDIT, self.clock.monotonic())

    def model_scope(self, *args):
        scope = ModelScope(self, *args)
        self.scopes.append(scope)
        return scope

    def command(self, driver, *args, **kwargs):
        with mock.patch.object(app.time, "monotonic", side_effect=self.clock.monotonic), \
                mock.patch.object(app.time, "sleep", side_effect=self.clock.sleep), \
                mock.patch.object(AUDIT, "make_scope", side_effect=self.model_scope), \
                mock.patch.object(AUDIT, "request_cancellation", side_effect=lambda *unused: self.events.append("cancel")):
            return driver.command(*args, **kwargs)

    def context(self):
        return {"schema": 1, "id": JOB, "root": str(self.source), "host": app.ROLE, "source": self.source_state,
                "expectedCommit": SHA, "tree": TREE, "gradleHome": str(self.work / "state/gradle-home"),
                "preexistingOutputPaths": [], "gradlePropertiesSha256": app.digest(POLICY),
                "javaHomes": [self.env["JAVA_HOME"], self.env["P2PKIT_AUDIT_JDK21"]]}

    def leaf_fixture(self, identity, purpose, ancestor):
        arguments, kind = app.leaf_arguments(purpose, self.work), app.LEAVES[purpose]
        executed = [str(self.source / "gradlew"), *AUDIT.gradle_arguments(arguments, reuse_xcframework=purpose == "xcode-provenance")] if kind == "gradle" else arguments
        stop = [str(self.source / "gradlew"), "--stop", "--console=plain", "--no-parallel", "--max-workers=2",
                "-Dorg.gradle.jvmargs=" + AUDIT.JVM_ARGUMENTS]
        start = {"schema": 1, "id": identity, "purpose": purpose, "kind": kind, "jobId": JOB, "host": app.ROLE,
                 "gradleHome": str(self.work / "state/gradle-home"), "cwd": str(self.source), "wrapper": str(self.source / "gradlew"),
                 "requestedArgv": arguments, "evidenceDirectory": str(self.work / "state/evidence" / identity),
                 "startedUtc": "2026-09-17T00:00:00+00:00", "controllerPid": 123, "ancestorInvocationIds": ancestor}
        record = {**start, "sourceBefore": self.source_state, "sourceAfter": self.source_state, "sourceUnchanged": True,
                  "productExitCode": 0, "finalExitCode": 0, "stopExitCode": 0, "errors": [], "ownedSurvivors": [],
                  "reports": [], "executedArgv": executed, "stopArgv": stop, "productLaunchIndex": 0, "stopLaunchIndex": 1,
                  "ownership": ownership(identity, JOB, [executed, stop])}
        directory = self.public / "leaves" / identity
        save(directory / "start.json", start)
        save(directory / "receipt.json", record)
        save(directory / "report-manifest.json", {"schema": 1, "records": [],
             "limitation": "Changed bytes are not proof of test execution; use the unchanged product assessor."})
        for name in app.LEAF_FILES:
            if name.endswith(".log"):
                save(directory / name, b"synthetic canonical output; not executed\n")
        return record

    def packet(self):
        """Create the complete small synthetic packet accepted by the real parser."""
        save(self.public / "admission.json", self.admitted)
        save(self.public / "context.json", self.context())
        save(self.public / "gradle-policy.properties", POLICY)
        save(self.public / "budget.json", {"enteredMonotonic": 0, "deadlineMonotonic": 9000, "driverSeconds": 9000,
             "leafCompletionSeconds": 600, "finalSeconds": 300, "scope": "CAPS_NOT_DURATION_OR_DOWNLOAD_GUARANTEES"})
        info = {"CFBundleIdentifier": "dev.p2pkit.sample", "CFBundleExecutable": "p2pkit-sample", "CFBundlePackageType": "APPL",
                "DTPlatformName": "iphoneos", "CFBundleSupportedPlatforms": ["iPhoneOS"], "MinimumOSVersion": "15.0",
                "CFBundleShortVersionString": "1.0.0", "CFBundleVersion": "1", "NSBonjourServices": ["_p2pkit2._tcp"],
                "NSLocalNetworkUsageDescription": "Synthetic public description", "DTSDKName": "iphoneos26.5"}
        save(self.public / "products/Info.plist", plistlib.dumps(info))
        save(self.public / "products/framework-Info.plist", plistlib.dumps({"CFBundleExecutable": "P2pKitShared", "CFBundlePackageType": "FMWK",
             "CFBundleSupportedPlatforms": ["iPhoneOS"], "MinimumOSVersion": "14.0"}))
        save(self.public / "products/p2pkit-sample-ui.xcscheme", b'<Scheme><BuildAction><BuildActionEntries><BuildActionEntry><BuildableReference BlueprintName="p2pkit-sample" BuildableName="p2pkit-sample.app" ReferencedContainer="container:p2pkit-sample.xcodeproj"/></BuildActionEntry></BuildActionEntries></BuildAction></Scheme>')
        toolchains = {"macOS": "26.6.2", "developerDirectory": app.DEVELOPER, "physicalMemoryBytes": 8 * app.GIB,
                      "java": {}, "sdks": {}}
        save(self.public / "toolchains/SystemVersion.plist", plistlib.dumps({"ProductVersion": toolchains["macOS"]}))
        for sdk in ("iphoneos", "iphonesimulator"):
            toolchains["sdks"][sdk] = {"path": app.DEVELOPER + "/SDKs/" + sdk, "version": "26.5", "canonicalName": sdk + "26.5"}
            save(self.public / "toolchains" / (sdk + ".json"), {"Version": "26.5", "CanonicalName": sdk + "26.5"})
        for platform, api in (("android-36", "36"), ("android-37.0", "37.0")):
            raw = ("AndroidVersion.ApiLevel=" + api + "\n").encode()
            save(self.public / "toolchains" / (platform + ".properties"), raw)
            toolchains["sdks"][platform] = {"api": api, "sourcePropertiesSha256": app.digest(raw)}
        for label, version, variable in (("java17", "17", "JAVA_HOME"), ("java21", "21", "P2PKIT_AUDIT_JDK21")):
            toolchains["java"][label] = {"home": self.env[variable], "major": version, "native": True}
        save(self.public / "toolchains.json", toolchains)
        ids = {name: format(index + 100, "032x") for index, name in enumerate(app.LEAVES)}
        command_ids = {name: format(index + 1000, "032x") for index, name in enumerate(ORDER)}
        leaves = {name: self.leaf_fixture(identity, name, [command_ids[name]] if name != "xcode-provenance" else
                  [command_ids["iphoneos-build"], ids["iphoneos-build"]]) for name, identity in ids.items()}
        save(self.public / "host-xcframework-build.json", leaves["xcframework-build"])
        sidecars = {"BUILD_COMMIT.txt": (SHA + "\n").encode(), "BUILD_SOURCE_STATE.txt": b"clean\n",
                    "BUILD_INPUTS_SHA256.txt": b"c" * 64 + b"\n", "BUILD_ARTIFACTS_SHA256.txt": b"d" * 64 + b"\n"}
        for name, raw in sidecars.items():
            save(self.public / name, raw)
        save(self.public / "xcframework-sidecars.json", {"sourceInvocationId": ids["xcframework-build"], "files": [
            {"path": name, "result": "RETAINED", "sha256": app.digest(sidecars[name])} for name in app.SIDECARS]})
        binding = app.public_sidecars(self.public, leaves["xcframework-build"])
        leaves["xcode-provenance"].update(xcframeworkReuse=binding, xcframeworkReuseUnchanged=True)
        save(self.public / "leaves" / ids["xcode-provenance"] / "receipt.json", leaves["xcode-provenance"])
        app_binary = {"bytes": 10, "sha256": app.digest(b"synthetic app")}
        framework = {"bytes": 20, "sha256": app.digest(b"synthetic framework")}
        save(self.public / "producer-product.json", {"source": self.source_state, "binding": binding,
             "binaryPath": str(self.source / app.DEVICE_BINARY), "binary": framework, "observation": "AFTER_FRESH_PRODUCER_BEFORE_XCODEBUILD"})
        derived = self.work / "state/xcode-deriveddata"
        app_path = derived / app.APP_RELATIVE
        targets = [str(self.source / "samples/iosApp/p2pkit-sample.xcodeproj"), str(derived)]
        cleanup = {"schema": 1, "id": "9" * 32, "jobId": JOB, "paths": targets, "removed": targets, "errors": []}
        save(self.public / "cleanup/receipt.json", cleanup)
        save(self.public / "cleanup/start.json", {**cleanup, "removed": []})
        save(self.public / "cleanup.json", {"result": "COMPLETE", "retirement": "KNOWN", "generatedOutputs": targets,
             "ownedWorkRemoved": [str(self.work / path) for path in ("state/gradle-home", "xcodegen", "home", "tmp")], "leafIds": sorted(ids.values())})
        binaries = {}
        for index, name in enumerate(ORDER):
            stdout, stderr = b"synthetic command\n", b""
            identity = command_ids[name]
            leaf_id = ids.get(name)
            post_init = index >= ORDER.index("xcodegen-install")
            if leaf_id:
                argv = [self.admitted["pythonExecutable"], "-B", "-S", str(self.source / "scripts/run-audit-command.py"),
                        "--cwd", str(self.source), "--wrapper", str(self.source / "gradlew"), "--purpose", name,
                        "--kind", app.LEAVES[name], "--id", leaf_id, "--receipt", str(self.work / "state" / ("host-" + name + ".json")),
                        "--timeout", "100", "--stop-timeout", "120", "--", *app.leaf_arguments(name, self.work)]
            elif name in ("java17", "java21"):
                argv = [str(Path(toolchains["java"][name]["home"]) / "bin/java"), "-XshowSettings:properties", "-version"]
                stdout = b""
                stderr = ('openjdk version "' + toolchains["java"][name]["major"] + '.0.1"\n    os.arch = aarch64\n').encode()
            elif name in ("xcode-version", "xcode-first-launch"):
                argv = ["/usr/bin/xcodebuild", "-version" if name == "xcode-version" else "-checkFirstLaunchStatus"]
                stdout = b"Xcode 26.5\nBuild version synthetic\n" if name == "xcode-version" else b""
            elif name == "memory":
                argv, stdout = ["/usr/sbin/sysctl", "-n", "hw.memsize"], (str(8 * app.GIB) + "\n").encode()
            elif name.endswith("-sdk"):
                sdk = name[:-4]
                argv, stdout = ["/usr/bin/xcrun", "--sdk", sdk, "--show-sdk-path"], (toolchains["sdks"][sdk]["path"] + "\n").encode()
            elif name == "init":
                argv = [self.admitted["pythonExecutable"], "-B", "-S", str(self.source / "scripts/run-audit-command.py"), "init",
                        "--root", str(self.source), "--state", str(self.work / "state"), "--expected-commit", SHA, "--host", app.ROLE]
            elif name == "cleanup":
                argv = [self.admitted["pythonExecutable"], "-B", "-S", str(self.source / "scripts/run-audit-command.py"), "cleanup", "--state", str(self.work / "state"),
                        *[arg for path in targets for arg in ("--path", path)]]
            else:
                label, tool = name.split("-")
                relative, minimum = ("p2pkit-sample", "15.0") if label == "app" else (app.FRAMEWORK_RELATIVE, "14.0")
                argv = ["/usr/bin/xcrun", tool, "-show-build" if tool == "vtool" else "-archs", str(app_path / relative)]
                stdout = ("cmd LC_BUILD_VERSION\nplatform IOS\nminos " + minimum + "\nsdk 26.5\n").encode() if tool == "vtool" else b"arm64\n"
                binaries.setdefault(label, {"path": relative, **(app_binary if label == "app" else framework),
                    "architectures": ["arm64"], "platform": "IOS", "minimum": minimum, "sdk": "26.5"})[tool + "Sha256"] = app.digest(stdout)
            directory = self.public / "commands" / name
            save(directory / "stdout.log", stdout)
            save(directory / "stderr.log", stderr)
            started, ended = index * 2 + 1, index * 2 + 2
            cap = min(CAPS[name], 100)
            save(directory / "record.json", {"id": identity, "name": name, "source": self.source_state, "argv": argv,
                 "jobId": JOB if post_init else PRE_JOB, "state": str(self.work / "state" if post_init else self.work),
                 "gradleHome": str(self.work / "state/gradle-home"), "leafId": leaf_id, "capSeconds": cap,
                 "startedMonotonic": started, "endedMonotonic": ended, "durationSeconds": 1,
                 "productiveDeadlineMonotonic": started + cap, "completionDeadlineMonotonic": started + cap + (600 if leaf_id else 15),
                 "exitCode": 0, "cancelRequested": False, "retirement": "KNOWN", "errors": [],
                 "ownership": ownership(identity, JOB if post_init else PRE_JOB, [argv], sinks=True),
                 "outputs": {"stdout.log": {"bytes": len(stdout), "sha256": app.digest(stdout)}, "stderr.log": {"bytes": len(stderr), "sha256": app.digest(stderr)}}})
        product_files = {"p2pkit-sample": app_binary, app.FRAMEWORK_RELATIVE: framework,
                         "Info.plist": app.file_record(self.public / "products/Info.plist")[0],
                         "Frameworks/P2pKitShared.framework/Info.plist": app.file_record(self.public / "products/framework-Info.plist")[0]}
        save(self.public / "product.json", {"scope": app.SCOPE, "source": self.source_state, "derivedData": str(derived), "app": str(app_path),
             "initiallyAbsent": True, "producerInvocationId": ids["xcframework-build"], "buildInvocationId": ids["iphoneos-build"], "nestedInvocationId": ids["xcode-provenance"],
             "info": app.assess_info(plistlib.dumps(info)), "generatedProject": {"bytes": 10, "sha256": "e" * 64}, "binaries": binaries,
             "files": [{"path": name, **row} for name, row in sorted(product_files.items())]})
        save(self.public / "result.json", {"admission": self.admitted, "scope": app.SCOPE, "result": "PASS", "errors": [],
             "contextInitialized": True, "attemptedLeaves": {name: identity for name, identity in ids.items() if name != "xcode-provenance"},
             "sourceUnchanged": True, "sourceAfter": self.source_state, "retirement": "KNOWN", "cancelled": False, "commands": sorted(app.COMMANDS), "durationSeconds": 35})
        self.reseal()
        return ids

    def reseal(self):
        save(self.public / "manifest.json", {"schema": 1, "admission": self.admitted, "files": app.public_inventory(self.public)})

    def validate(self):
        return app.validate_public(self.env, self.admitted, AUDIT)

    def mutate(self, name, mutate):
        path = self.public / name
        value = app.parse(path.read_bytes())
        mutate(value)
        save(path, value)
        self.reseal()

    def partial_packet(self, last="iphoneos-build", code=65, *, cleanup=True):
        """A completed nonzero product and an otherwise exact synthetic prefix."""
        ids = self.packet()
        keep = set(ORDER[:ORDER.index(last) + 1]) | ({"cleanup"} if cleanup else set())
        for name in app.COMMANDS - keep:
            shutil.rmtree(self.public / "commands" / name)
        retained_ids = {name: identity for name, identity in ids.items()
                        if name in keep or (name == "xcode-provenance" and last == "iphoneos-build")}
        for name in ids.keys() - retained_ids.keys():
            shutil.rmtree(self.public / "leaves" / ids[name])
        for name in ("product.json", "products/Info.plist", "products/framework-Info.plist"):
            (self.public / name).unlink()
        if "xcode-project" not in keep or last == "xcode-project":
            (self.public / "products/p2pkit-sample-ui.xcscheme").unlink()
        if "xcframework-build" not in keep or last == "xcframework-build":
            for name in (*app.SIDECARS, "host-xcframework-build.json", "xcframework-sidecars.json", "producer-product.json"):
                (self.public / name).unlink()
        self.mutate("commands/" + last + "/record.json", lambda value: value.update(exitCode=code))
        self.mutate("leaves/" + ids[last] + "/receipt.json", lambda value: value.update(productExitCode=code, finalExitCode=code))
        self.mutate("cleanup.json", lambda value: value.update(leafIds=sorted(retained_ids.values())))
        if not cleanup:
            shutil.rmtree(self.public / "cleanup")
            self.mutate("cleanup.json", lambda value: value.update(generatedOutputs=[], ownedWorkRemoved=[
                str(self.work / path) for path in ("state/gradle-home", "home", "tmp")]))
        self.mutate("result.json", lambda value: value.update(result="HOLD", errors=["SYNTHETIC_NONZERO_PRODUCT"],
            commands=sorted(keep), attemptedLeaves={name: identity for name, identity in retained_ids.items() if name != "xcode-provenance"}))
        self.env["P2PKIT_IPHONEOS_RUN_OUTCOME"] = "failure"
        return retained_ids

    def finalized_nonzero_driver(self):
        self.clock.now = 0
        driver = self.driver()
        ids = self.partial_packet("xcodegen-install", 42, cleanup=False)
        for path in app.files_bounded(self.public, 224, 2, app.public_directory):
            relative = path.relative_to(self.public)
            if relative.as_posix() in app.TOOLCHAIN_FILES:
                driver.retain_prerequisite(relative.as_posix(), path.read_bytes())
            elif relative.as_posix() not in ("result.json", "manifest.json", "cleanup.json"):
                save(driver.retained / relative, path.read_bytes())
        shutil.rmtree(self.public)  # Only this synthetic packet; the driver exports anew.
        driver.context = self.context()
        driver.context_bytes = app.encoded(driver.context)
        save(driver.state / "context.json", driver.context_bytes)
        save(driver.state / "gradle-home/gradle.properties", POLICY)
        save(driver.state / "gradle-home/sentinel", b"SYNTHETIC must remain until original-evidence barrier")
        driver.commands = {name: app.parse((driver.retained / "commands" / name / "record.json").read_bytes())
                           for name in ORDER[:ORDER.index("xcodegen-install") + 1]}
        driver.job = PRE_JOB  # Synthetic original native-controller identity before init.
        driver.attempted_leaves = ids
        for purpose, identity in ids.items():
            shutil.copytree(driver.retained / "leaves" / identity, driver.state / "evidence" / identity)
            save(driver.state / ("host-" + purpose + ".json"), (driver.retained / "leaves" / identity / "receipt.json").read_bytes())
        self.clock.now = 100
        return driver, ids

    def failed_tail(self, driver):
        with mock.patch.object(app.time, "monotonic", side_effect=self.clock.monotonic), \
                mock.patch.object(driver, "prerequisites", side_effect=app.RouteError("SYNTHETIC_NONZERO_PRODUCT")):
            return driver.run()

    def original_init_prefix(self, code):
        """Finalized synthetic init command, with no state produced or inferred."""
        self.clock.now = 0
        driver = self.driver()
        self.packet()
        for name in app.TOOLCHAIN_FILES:
            driver.retain_prerequisite(name, (self.public / name).read_bytes())
        for name in ORDER[:ORDER.index("init") + 1]:
            target = driver.retained / "commands" / name
            shutil.copytree(self.public / "commands" / name, target)
            record = app.parse((target / "record.json").read_bytes())
            if name == "init":
                record["exitCode"] = code
                save(target / "record.json", record)
            driver.commands[name] = record
        driver.job = PRE_JOB
        shutil.rmtree(self.public)
        self.clock.now = 100
        return driver

    def case_driver(self, label):
        base = self.base / ("case-" + label)
        base.mkdir()
        self.env["RUNNER_TEMP"] = str(base)
        self.work = base / "p2pkit-iphoneos-work-123-2"
        self.public = base / "p2pkit-iphoneos-evidence-123-2"
        return self.finalized_nonzero_driver()[0]

    def assert_deletion_blocked(self, driver, *, barrier_only=False):
        with mock.patch.object(app.time, "monotonic", side_effect=self.clock.monotonic), \
                mock.patch.object(app.shutil, "rmtree", side_effect=AssertionError("Deletion reached before original proof")), \
                self.assertRaises((app.RouteError, ValueError, OSError)):
            driver.retention_barrier() if barrier_only else driver.clean()
        self.assertFalse(driver.safe)
        self.assertTrue((driver.state / "gradle-home/sentinel").exists())

    def test_complete_synthetic_packet_is_only_parser_acceptance(self):
        self.assertEqual(app.COMMAND_CAPS, CAPS)
        self.packet()
        self.assertEqual(self.validate(), 0)
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_bytes(), b"artifacts_ready=true\nproduct_passed=true\n")

    def test_dispatch_requires_exact_real_identity_fields_in_the_model(self):
        for key, value in (("GITHUB_ACTIONS", "false"), ("GITHUB_EVENT_NAME", "push"), ("GITHUB_SHA", "f" * 40),
                           ("GITHUB_WORKFLOW_SHA", "f" * 40), ("RUNNER_ARCH", "X64"), ("RUNNER_ENVIRONMENT", "self-hosted"),
                           ("GITHUB_REF", "refs/tags/v1"), ("GITHUB_RUN_ATTEMPT", "0"), ("DEVELOPER_DIR", "/other/Xcode")):
            with self.subTest(key=key), self.assertRaises(app.RouteError):
                app.dispatch_identity({**self.env, key: value}, self.event, self.source_state)
        for key in ("command", "reviewed_base", "evidence_public_key", "evidence_fingerprint"):
            event = copy.deepcopy(self.event)
            event["inputs"][key] = "must-not-be-admitted"
            with self.subTest(key=key), self.assertRaises(app.RouteError):
                app.dispatch_identity(self.env, event, self.source_state)

    def test_clean_exact_source_cannot_be_inferred_from_expected_sha_only(self):
        for key, value in (("status", " M changed"), ("tree", "f" * 40), ("diffSha256", "f" * 64)):
            with self.subTest(key=key), self.assertRaises(app.RouteError):
                app.dispatch_identity(self.env, self.event, {**self.source_state, key: value})

    def test_environment_is_closed_and_rejects_jvm_loader_hooks(self):
        result = app.build_environment({**self.env, "GH_TOKEN": "PRIVATE", "GITHUB_TOKEN": "PRIVATE", "P2PKIT_OTHER": "PRIVATE",
                                        "ORG_GRADLE_PROJECT_signingKey": "PRIVATE", "HTTPS_PROXY": "PRIVATE"})
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertFalse(any(name.startswith("GITHUB_") for name in result))
        for key in ("JAVA_TOOL_OPTIONS", "GRADLE_OPTS", "BASH_ENV", "DYLD_INSERT_LIBRARIES", "PYTHONPATH"):
            with self.subTest(key=key), self.assertRaises(app.RouteError):
                app.build_environment({**self.env, key: "unsafe"})

    def test_json_nonfinite_and_duplicate_keys_fail_closed(self):
        for raw in (b'{"x": 1, "x": 2}', b'{"x": NaN}', b'{"x": Infinity}', b'{"x": 1e999}', b'{"x": -1e999}'):
            with self.subTest(raw=raw), self.assertRaises(app.RouteError):
                app.parse(raw)

    def test_link_hardlink_and_oversized_members_rejected(self):
        file = self.base / "file"
        save(file, b"1234")
        linked = self.base / "linked"
        linked.symlink_to(file)
        with self.assertRaises(app.RouteError):
            app.read(linked)
        with self.assertRaises(app.RouteError):
            app.read(file, 3)
        linked.unlink()
        os.link(file, linked)
        with self.assertRaises(app.RouteError):
            app.read(file)

    def test_fdopen_failure_closes_its_already_open_descriptor(self):
        file = self.base / "file"
        save(file, b"data")
        closed = []
        original = os.close
        with mock.patch.object(os, "fdopen", side_effect=OSError("synthetic fdopen failure")), \
                mock.patch.object(os, "close", side_effect=lambda fd: (closed.append(fd), original(fd))[-1]):
            with self.assertRaises(OSError):
                app.read(file)
        self.assertEqual(len(closed), 1)
        with self.assertRaises(OSError):
            os.fstat(closed[0])

    def test_empty_directories_are_not_an_unbounded_or_unknown_public_channel(self):
        self.public.mkdir()
        (self.public / "unexpected").mkdir()
        with self.assertRaises(app.RouteError):
            app.public_inventory(self.public)
        (self.public / "unexpected").rmdir()
        for index in range(5):
            (self.public / str(index)).mkdir()
        with self.assertRaises(app.RouteError):
            list(app.files_bounded(self.public, 4, 2))

    def test_manifest_itself_still_consumes_the_same_public_quota(self):
        save(self.public / "admission.json", b"a")
        save(self.public / "manifest.json", b"m")
        with mock.patch.object(app, "PUBLIC_TOTAL", 1), self.assertRaisesRegex(app.RouteError, "PUBLIC_LIMIT"):
            app.public_inventory(self.public)

    def test_simulator_wrong_minimum_and_fat_architecture_fail(self):
        original = b"cmd LC_BUILD_VERSION\nplatform IOS\nminos 15.0\nsdk 26.5\n"
        self.assertEqual(app.assess_native(original, b"arm64\n", "15.0")["platform"], "IOS")
        for text, arch in ((original.replace(b"IOS", b"IOSSIMULATOR"), b"arm64\n"),
                           (original.replace(b"15.0", b"14.0"), b"arm64\n"), (original, b"arm64 x86_64\n"),
                           (original + b"platform IOS\n", b"arm64\n")):
            with self.subTest(text=text, arch=arch), self.assertRaises(app.RouteError):
                app.assess_native(text, arch, "15.0")

    def test_rehashed_product_tampering_cannot_omit_binary_freshness_or_paths(self):
        self.packet()
        path = self.public / "product.json"
        original = path.read_bytes()
        mutations = (lambda value: value["binaries"]["framework"].pop("sha256"),
                     lambda value: value["binaries"]["framework"].update(bytes=99),
                     lambda value: value.update(initiallyAbsent=False), lambda value: value.update(app="/stale.app"),
                     lambda value: value.update(derivedData="/stale"), lambda value: value.pop("generatedProject"),
                     lambda value: value.update(producerInvocationId="0" * 32), lambda value: value.update(files=[]))
        for index, mutate in enumerate(mutations):
            save(path, original)
            self.mutate("product.json", mutate)
            with self.subTest(index=index), self.assertRaises((app.RouteError, ValueError)):
                self.validate()
        save(path, original)

    def test_rehashed_consistent_embedded_inventory_still_binds_original_producer(self):
        self.packet()
        def corrupt(value):
            value["binaries"]["framework"]["sha256"] = "f" * 64
            next(row for row in value["files"] if row["path"] == app.FRAMEWORK_RELATIVE)["sha256"] = "f" * 64
        self.mutate("product.json", corrupt)
        with self.assertRaisesRegex(app.RouteError, "PUBLIC_EMBEDDED_PRODUCER"):
            self.validate()

    def test_every_original_sidecar_is_required_even_after_manifest_rehash(self):
        self.packet()
        for name in app.SIDECARS:
            path, original = self.public / name, (self.public / name).read_bytes()
            save(path, b"changed\n")
            self.reseal()
            with self.subTest(name=name), self.assertRaises(app.RouteError):
                self.validate()
            save(path, original)

    def test_nested_reuse_ancestor_execution_and_stop_are_all_required(self):
        ids = self.packet()
        name = "leaves/" + ids["xcode-provenance"] + "/receipt.json"
        original = (self.public / name).read_bytes()
        mutations = (lambda value: value.pop("xcframeworkReuse"), lambda value: value.update(xcframeworkReuseUnchanged=False),
                     lambda value: value.update(ancestorInvocationIds=[]), lambda value: value.update(stopExitCode=1),
                     lambda value: value.update(errors=["synthetic"]), lambda value: value.update(ownedSurvivors=[{"status": "UNKNOWN"}]),
                     lambda value: value.update(executedArgv=["true"]))
        for index, mutate in enumerate(mutations):
            save(self.public / name, original)
            self.mutate(name, mutate)
            with self.subTest(index=index), self.assertRaises((app.RouteError, ValueError)):
                self.validate()

    def test_missing_original_capture_cannot_be_hidden_by_manifest_rehash(self):
        ids = self.packet()
        (self.public / "leaves" / ids["iphoneos-build"] / "stop.stderr.log").unlink()
        self.reseal()
        with self.assertRaises(FileNotFoundError):
            self.validate()

    def test_command_exit_cancellation_ownership_and_output_hashes_are_rechecked(self):
        self.packet()
        name = "commands/app-vtool/record.json"
        original = (self.public / name).read_bytes()
        mutations = (lambda value: value.update(exitCode=1), lambda value: value.update(exitCode=False),
                     lambda value: value.update(cancelRequested=True), lambda value: value.update(retirement="UNKNOWN"),
                     lambda value: value.update(outputs={}), lambda value: value.update(completionDeadlineMonotonic=99999),
                     lambda value: value["ownership"].update(discoveryErrors=["unknown"]))
        for index, mutate in enumerate(mutations):
            save(self.public / name, original)
            self.mutate(name, mutate)
            with self.subTest(index=index), self.assertRaises(app.RouteError):
                self.validate()

    def test_original_command_caps_order_and_duration_cannot_be_rehashed_away(self):
        self.packet()
        name = "commands/memory/record.json"
        original = (self.public / name).read_bytes()
        def change_cap(value):
            value.update(capSeconds=31, productiveDeadlineMonotonic=value["startedMonotonic"] + 31,
                         completionDeadlineMonotonic=value["startedMonotonic"] + 46)
        def change_order(value):
            value.update(startedMonotonic=0, endedMonotonic=1, productiveDeadlineMonotonic=value["capSeconds"],
                         completionDeadlineMonotonic=value["capSeconds"] + 15)
        for mutate in (change_cap, change_order):
            save(self.public / name, original)
            self.mutate(name, mutate)
            with self.subTest(mutate=mutate.__name__), self.assertRaises(app.RouteError):
                self.validate()
        save(self.public / name, original)
        self.mutate("result.json", lambda value: value.update(durationSeconds=0))
        with self.assertRaises(app.RouteError):
            self.validate()

    def test_launch_executable_and_caller_owned_sinks_are_rechecked(self):
        self.packet()
        name = "commands/memory/record.json"
        original = (self.public / name).read_bytes()
        def change_executable(value):
            launch = value["ownership"]["launches"][0]
            launch["resolvedArgv"][0] = "/other/sysctl"
            launch["executable"] = "/other/sysctl"
        for mutate in (change_executable, lambda value: value["ownership"]["launches"][0].pop("outputMode")):
            save(self.public / name, original)
            self.mutate(name, mutate)
            with self.subTest(mutate=mutate.__name__), self.assertRaises(app.RouteError):
                self.validate()

    def test_literal_sdk37_metadata_cannot_be_renamed_to_pass(self):
        self.packet()
        save(self.public / "toolchains/android-37.0.properties", b"AndroidVersion.ApiLevel=37\n")
        self.reseal()
        with self.assertRaises(app.RouteError):
            self.validate()

    def test_failed_driver_outcome_cannot_publish_pass_metadata(self):
        self.packet()
        self.env["P2PKIT_IPHONEOS_RUN_OUTCOME"] = "failure"
        with self.assertRaisesRegex(app.RouteError, "PUBLIC_RUN_OUTCOME"):
            self.validate()

    def test_cleanup_is_bound_to_original_removals_and_actual_absence(self):
        self.packet()
        (self.work / "xcodegen").mkdir(parents=True)
        with self.assertRaisesRegex(app.RouteError, "PUBLIC_OWNED_CLEANUP"):
            self.validate()

    def test_missing_budget_refuses_spawn(self):
        driver = self.driver()
        self.clock.now = driver.deadline
        with self.assertRaises(app.RouteError):
            self.command(driver, "memory", ["/never-executed"], 30)
        self.assertEqual(self.events, [])

    def test_outer_scope_inherits_canonical_job_and_state_after_init(self):
        driver = self.driver()
        driver.context = self.context()
        self.command(driver, "memory", ["/never-executed"], 30)
        scope = self.scopes[0]
        self.assertEqual((scope.job, scope.state, scope.home), (JOB, str(driver.state), str(driver.state / "gradle-home")))
        # The real pure ownership validator, not a permissive lambda, must admit
        # a canonical leaf beneath the controller's returned environment.
        nested = AUDIT.ownership_environment(scope.env, JOB, "3" * 32, str(driver.state), scope.home)
        self.assertEqual(nested["P2PKIT_AUDIT_STATE_DIR"], str(driver.state))
        self.assertTrue(scope.drained and scope.closed and all(stream.closed for stream in scope.outputs))

    def test_output_overflow_retains_originals_and_drains_without_truncation(self):
        driver = self.driver()
        self.output = b"x" * 65
        with mock.patch.object(app, "LOG_LIMIT", 64), self.assertRaises(app.RouteError):
            self.command(driver, "memory", ["/never-executed"], 30)
        self.assertEqual((driver.retained / "commands/memory/stdout.log").read_bytes(), self.output)
        self.assertTrue(self.scopes[0].drained and self.scopes[0].closed)
        self.assertIn("OUTPUT_LIMIT", driver.commands["memory"]["errors"])

    def test_partial_spawn_and_close_failure_never_become_success(self):
        driver = self.driver()
        self.partial_spawn, self.close_error = True, True
        with self.assertRaises(app.RouteError):
            self.command(driver, "memory", ["/never-executed"], 30)
        self.assertTrue(self.scopes[0].drained and all(stream.closed for stream in self.scopes[0].outputs))
        self.assertFalse(driver.safe)
        self.assertEqual(driver.commands["memory"]["retirement"], "UNKNOWN")

    def test_unknown_drain_blocks_the_next_scope(self):
        driver = self.driver()
        self.drain_error = True
        with self.assertRaises(app.RouteError):
            self.command(driver, "memory", ["/never-executed"], 30)
        with self.assertRaises(app.RouteError):
            self.command(driver, "java17", ["/never-executed"], 30)
        self.assertEqual(len(self.scopes), 1)

    def test_completion_drain_does_not_gain_an_extra_budget(self):
        driver = self.driver()
        self.drain_seconds = 46
        with self.assertRaises(app.RouteError):
            self.command(driver, "memory", ["/never-executed"], 30)
        self.assertIn("COMPLETION_DEADLINE", driver.commands["memory"]["errors"])

    def test_original_output_retention_is_inside_the_same_command_budget(self):
        driver = self.driver()
        original, advanced = app.file_record, []
        def slow_record(path, **kwargs):
            result = original(path, **kwargs)
            if Path(path).name == "stdout.log" and not advanced:
                self.clock.now += 46
                advanced.append(True)
            return result
        with mock.patch.object(app, "file_record", side_effect=slow_record), self.assertRaises(app.RouteError):
            self.command(driver, "memory", ["/never-executed"], 30)
        self.assertTrue(self.scopes[0].drained and self.scopes[0].closed)
        self.assertIn("COMPLETION_DEADLINE", driver.commands["memory"]["errors"])

    def test_cooperative_cancellation_shortens_once_and_never_passes(self):
        driver = self.driver()
        driver.context = self.context()
        polls = []
        def poll():
            polls.append(1)
            driver.cancelled.append(signal.SIGTERM)
            return None if len(polls) < 3 else 0
        self.poll = poll
        with self.assertRaises(app.RouteError):
            self.command(driver, "xcframework-build", ["/never-executed"], 7200, leaf_id="3" * 32)
        record = driver.commands["xcframework-build"]
        self.assertEqual(self.events.count("cancel"), 1)
        self.assertLessEqual(record["completionDeadlineMonotonic"], record["startedMonotonic"] + 600)
        self.assertTrue(record["cancelRequested"] and self.scopes[0].closed)

    def test_unfinalized_leaf_blocks_cache_cleanup_even_with_no_build_targets(self):
        driver = self.driver()
        driver.context = self.context()
        driver.context_bytes = app.encoded(driver.context)
        save(driver.state / "context.json", driver.context_bytes)
        save(driver.state / "gradle-home/sentinel", b"required until finalized")
        save(driver.state / "evidence" / ("3" * 32) / "start.json", {"id": "3" * 32, "jobId": JOB, "purpose": "iphoneos-build"})
        with mock.patch.object(app.time, "monotonic", side_effect=self.clock.monotonic), \
                mock.patch.object(AUDIT, "disposable_roots", return_value=[]), \
                mock.patch.object(app.shutil, "rmtree", side_effect=AssertionError("No deletion before finalization")), \
                self.assertRaisesRegex(app.RouteError, "UNPROVED_LEAF_RETIREMENT"):
            driver.clean()
        self.assertTrue((driver.state / "gradle-home/sentinel").is_file())
        self.assertFalse(driver.safe)

    def test_known_safe_nonzero_product_retains_all_originals_then_cleans_and_exports_hold(self):
        driver, ids = self.finalized_nonzero_driver()
        self.assertEqual(self.failed_tail(driver), 2)
        self.assertTrue(driver.safe)
        self.assertFalse((driver.state / "gradle-home").exists())
        self.assertEqual(self.validate(), 0)
        for name in app.LEAF_FILES:
            self.assertEqual((driver.state / "evidence" / ids["xcodegen-install"] / name).read_bytes(),
                             (driver.public / "leaves" / ids["xcodegen-install"] / name).read_bytes())
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_bytes(), b"artifacts_ready=true\nproduct_passed=false\n")

    def test_known_safe_nonzero_xcode_product_seal_checks_nested_and_prior_producer(self):
        self.partial_packet()
        self.assertEqual(self.validate(), 0)
        self.assertIn(b"product_passed=false", Path(self.env["GITHUB_OUTPUT"]).read_bytes())

    def test_retention_error_cannot_skip_independent_terminal_audit(self):
        driver, ids = self.finalized_nonzero_driver()
        save(driver.state / "evidence" / ids["xcodegen-install"] / "start.json", b'{"id":')
        with mock.patch.object(driver, "terminal_leaves", wraps=driver.terminal_leaves) as terminal, \
                self.assertRaisesRegex(app.RouteError, "UNSAFE_EXPORT"):
            self.failed_tail(driver)
        terminal.assert_called_once_with(for_cleanup=False)
        self.assertFalse(driver.safe)
        self.assertFalse(driver.public.exists())
        self.assertTrue((driver.state / "gradle-home/sentinel").exists())

    def test_unknown_canonical_finalization_is_sticky_even_with_empty_survivor_lists(self):
        driver, ids = self.finalized_nonzero_driver()
        directory = driver.state / "evidence" / ids["xcodegen-install"]
        record = app.parse((directory / "receipt.json").read_bytes())
        record.update(finalExitCode=125, errors=["Owned stream retirement UNKNOWN: synthetic tail"])
        save(directory / "receipt.json", record)
        with self.assertRaisesRegex(app.RouteError, "UNSAFE_EXPORT"):
            self.failed_tail(driver)
        self.assertEqual(record["ownedSurvivors"], [])
        self.assertEqual(record["ownership"]["discoveryErrors"], [])
        self.assertFalse(driver.safe)
        self.assertFalse(driver.public.exists())
        self.assertTrue((driver.state / "gradle-home/sentinel").exists())

    def test_terminal_audit_continues_after_one_bad_leaf(self):
        driver, ids = self.finalized_nonzero_driver()
        identity = "f" * 32
        self.leaf_fixture(identity, "xcode-provenance", ["e" * 32, "d" * 32])
        shutil.copytree(self.public / "leaves" / identity, driver.state / "evidence" / identity)
        original = app.leaf_evidence
        seen = []
        def observe(*args, **kwargs):
            seen.append(args[1])
            if args[1] == ids["xcodegen-install"]:
                raise app.RouteError("SYNTHETIC_FIRST_LEAF_FAILURE")
            return original(*args, **kwargs)
        with mock.patch.object(app, "leaf_evidence", side_effect=observe), \
                self.assertRaisesRegex(app.RouteError, "UNPROVED_LEAF_RETIREMENT"):
            driver.terminal_leaves(for_cleanup=False)
        self.assertEqual(seen, [ids["xcodegen-install"], identity])
        self.assertFalse(driver.safe)

    def test_missing_changed_or_oversized_original_blocks_every_deletion(self):
        driver, ids = self.finalized_nonzero_driver()
        directory = driver.state / "evidence" / ids["xcodegen-install"]
        path, original = directory / "stop.stderr.log", (directory / "stop.stderr.log").read_bytes()
        for mode in ("missing", "changed", "oversized"):
            with self.subTest(mode=mode):
                driver.safe = True  # Independent synthetic starting state, never production recovery.
                save(path, original)
                if mode == "missing":
                    path.unlink()
                else:
                    save(path, b"different original" if mode == "changed" else b"x" * 1025)
                with mock.patch.object(app, "LOG_LIMIT", 1024), \
                        mock.patch.object(app.time, "monotonic", side_effect=self.clock.monotonic), \
                        mock.patch.object(app.shutil, "rmtree", side_effect=AssertionError("No deletion before original barrier")), \
                        self.assertRaises((app.RouteError, FileNotFoundError)):
                    driver.clean()
                self.assertFalse(driver.safe)
                self.assertTrue((driver.state / "gradle-home/sentinel").exists())

    def test_aggregate_original_limit_blocks_deletion_before_the_later_seal(self):
        driver, _ = self.finalized_nonzero_driver()
        with mock.patch.object(app, "LOG_TOTAL", 1), \
                mock.patch.object(app.time, "monotonic", side_effect=self.clock.monotonic), \
                mock.patch.object(app.shutil, "rmtree", side_effect=AssertionError("No deletion before aggregate barrier")), \
                self.assertRaisesRegex(app.RouteError, "PUBLIC_LIMIT"):
            driver.clean()
        self.assertFalse(driver.safe)
        self.assertTrue((driver.state / "gradle-home/sentinel").exists())

    def test_nested_leaf_without_its_outer_phase_blocks_deletion(self):
        driver, _ = self.finalized_nonzero_driver()
        identity = "f" * 32
        self.leaf_fixture(identity, "xcode-provenance", ["e" * 32, "d" * 32])
        shutil.copytree(self.public / "leaves" / identity, driver.state / "evidence" / identity)
        with mock.patch.object(app.time, "monotonic", side_effect=self.clock.monotonic), \
                mock.patch.object(app.shutil, "rmtree", side_effect=AssertionError("No deletion before nested binding")), \
                self.assertRaisesRegex(app.RouteError, "RETAINED_NESTED_PHASE"):
            driver.clean()
        self.assertFalse(driver.safe)
        self.assertTrue((driver.state / "gradle-home/sentinel").exists())

    def test_entire_completed_prerequisite_family_is_required_before_deletion(self):
        self.assertEqual(app.TOOLCHAIN_FILES, ("toolchains.json", "toolchains/SystemVersion.plist", "toolchains/iphoneos.json",
            "toolchains/iphonesimulator.json", "toolchains/android-36.properties", "toolchains/android-37.0.properties"))
        for index, name in enumerate(app.TOOLCHAIN_FILES):
            for mode in ("missing", "changed", "oversized"):
                with self.subTest(member=name, mode=mode):
                    driver = self.case_driver(str(index) + "-" + mode)
                    path = driver.retained / name
                    original = path.read_bytes()
                    self.assertEqual(driver.prerequisite_captures[name], {"source": self.source_state,
                                     "file": {"bytes": len(original), "sha256": app.digest(original)}})
                    if mode == "missing":
                        path.unlink()
                    else:
                        # A trailing LF preserves the parsed value: rejection
                        # must bind actual original bytes, not just SDK fields.
                        save(path, original + b"\n" if mode == "changed" else b"x" * 65537)
                    with mock.patch.object(app, "META_LIMIT", 65536):
                        self.assert_deletion_blocked(driver)

    def test_completed_prerequisite_commands_bind_actual_outputs_source_and_domains(self):
        for mode in ("sdk-output", "argv", "job", "source", "nonzero", "state", "missing-command"):
            with self.subTest(mode=mode):
                driver = self.case_driver(mode)
                name = "iphoneos-sdk"
                directory = driver.retained / "commands" / name
                record = copy.deepcopy(driver.commands[name])
                if mode == "sdk-output":
                    raw = b"/different/SDK\n"
                    save(directory / "stdout.log", raw)
                    record["outputs"]["stdout.log"] = {"bytes": len(raw), "sha256": app.digest(raw)}
                elif mode == "argv":
                    record["argv"] = ["/usr/bin/xcrun", "--sdk", "wrong-sdk", "--show-sdk-path"]
                    record["ownership"]["launches"][0].update(requestedArgv=record["argv"], resolvedArgv=record["argv"])
                elif mode == "job":
                    record["jobId"] = "f" * 32
                    record["ownership"]["job"] = record["jobId"]
                elif mode == "source":
                    record["source"]["tree"] = "f" * 40
                elif mode == "nonzero":
                    record["exitCode"] = 1
                elif mode == "state":
                    record["state"] = str(driver.state)
                if mode == "missing-command":
                    driver.commands.pop(name)
                    shutil.rmtree(directory)  # Synthetic omission before installing deletion spy.
                else:
                    # Keep in-memory/copy agreement: prerequisite binding, not
                    # merely a mismatched controller copy, must still reject.
                    driver.commands[name] = record
                    save(directory / "record.json", record)
                self.assert_deletion_blocked(driver)

    def test_actual_initialized_phase_cannot_waive_originals_by_relabel_or_omission(self):
        for mode in ("omitted-family", "context-relabel", "context-and-attempts-relabel"):
            with self.subTest(mode=mode):
                driver = self.case_driver(mode)
                for name in app.TOOLCHAIN_FILES:
                    (driver.retained / name).unlink()
                driver.prerequisite_captures.clear()  # Adverse waiver attempt, not production recovery.
                if mode != "omitted-family":
                    driver.context = None
                if mode == "context-and-attempts-relabel":
                    driver.attempted_leaves.clear()
                self.assert_deletion_blocked(driver, barrier_only=True)

    def test_genuine_preinit_partial_originals_do_not_require_future_toolchains(self):
        driver = self.driver()
        raw = plistlib.dumps({"ProductVersion": "15.0"})  # Synthetic unsupported-OS prerequisite rejection.
        driver.retain_prerequisite("toolchains/SystemVersion.plist", raw)
        self.assertEqual(self.failed_tail(driver), 2)
        self.assertTrue(driver.safe)
        self.assertEqual(driver.commands, {})
        self.assertFalse(driver.state.exists())
        self.assertFalse((driver.work / "home").exists())
        self.assertEqual((driver.public / "toolchains/SystemVersion.plist").read_bytes(), raw)
        self.assertFalse((driver.public / "toolchains.json").exists())
        self.env["P2PKIT_IPHONEOS_RUN_OUTCOME"] = "failure"
        self.assertEqual(self.validate(), 0)

    def test_finalized_nonzero_init_without_state_retains_and_exports_safe_hold(self):
        driver = self.original_init_prefix(42)
        self.assertEqual(self.failed_tail(driver), 2)
        self.assertTrue(driver.safe)
        self.assertFalse(driver.state.exists())
        self.assertFalse((driver.work / "home").exists())
        self.assertFalse((driver.work / "tmp").exists())
        self.env["P2PKIT_IPHONEOS_RUN_OUTCOME"] = "failure"
        self.assertEqual(self.validate(), 0)
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_bytes(), b"artifacts_ready=true\nproduct_passed=false\n")

    def test_successful_init_missing_original_state_blocks_full_tail_deletion(self):
        driver = self.original_init_prefix(0)
        with mock.patch.object(app.shutil, "rmtree") as deletion, self.assertRaisesRegex(app.RouteError, "UNSAFE_EXPORT"):
            self.failed_tail(driver)
        deletion.assert_not_called()
        self.assertFalse(driver.safe)
        self.assertFalse(driver.public.exists())
        self.assertTrue((driver.work / "home").exists())
        self.assertTrue((driver.work / "tmp").exists())

    def test_initialized_context_requires_original_init_command_before_full_tail_deletion(self):
        for mode in ("missing", "nonzero", "argv", "job", "state", "home", "order"):
            with self.subTest(mode=mode):
                driver = self.case_driver("init-" + mode)
                directory = driver.retained / "commands/init"
                record = copy.deepcopy(driver.commands["init"])
                if mode == "missing":
                    driver.commands.pop("init")
                    shutil.rmtree(directory)  # Synthetic omission before installing deletion spy.
                else:
                    if mode == "nonzero":
                        record["exitCode"] = 42
                    elif mode == "argv":
                        record["argv"][record["argv"].index("--host") + 1] = "macos-x64"
                        record["ownership"]["launches"][0].update(requestedArgv=record["argv"], resolvedArgv=record["argv"])
                    elif mode == "job":
                        record["jobId"] = "f" * 32
                        record["ownership"]["job"] = record["jobId"]
                    elif mode == "state":
                        record["state"] = str(driver.state)
                    elif mode == "home":
                        record["gradleHome"] = str(driver.work / "home")
                    elif mode == "order":
                        for key in ("startedMonotonic", "endedMonotonic", "productiveDeadlineMonotonic", "completionDeadlineMonotonic"):
                            record[key] -= 2
                    driver.commands["init"] = record
                    save(directory / "record.json", record)
                with mock.patch.object(app.shutil, "rmtree") as deletion, self.assertRaisesRegex(app.RouteError, "UNSAFE_EXPORT"):
                    self.failed_tail(driver)
                deletion.assert_not_called()
                self.assertFalse(driver.safe)
                self.assertFalse(driver.public.exists())
                self.assertTrue((driver.state / "gradle-home/sentinel").exists())
                self.assertTrue((driver.work / "home").exists())
                self.assertTrue((driver.work / "tmp").exists())

    def test_preinit_observed_original_is_not_optional_after_capture_loss(self):
        driver = self.driver()
        driver.retain_prerequisite("toolchains/SystemVersion.plist", plistlib.dumps({"ProductVersion": "15.0"}))
        (driver.retained / "toolchains/SystemVersion.plist").unlink()
        with mock.patch.object(app.shutil, "rmtree", side_effect=AssertionError("No deletion after lost original")), \
                self.assertRaisesRegex(app.RouteError, "UNSAFE_EXPORT"):
            self.failed_tail(driver)
        self.assertFalse(driver.safe)
        self.assertTrue((driver.work / "home").exists())
        self.assertTrue((driver.work / "tmp").exists())

    def test_prerequisite_write_failure_cannot_be_recaptured_as_not_started(self):
        driver = self.driver()
        raw = plistlib.dumps({"ProductVersion": "15.0"})
        with mock.patch.object(app, "write", side_effect=OSError("synthetic capture write failure")), self.assertRaises(OSError):
            driver.retain_prerequisite("toolchains/SystemVersion.plist", raw)
        self.assertIn("toolchains/SystemVersion.plist", driver.prerequisite_captures)
        with self.assertRaisesRegex(app.RouteError, "PREREQUISITE_CAPTURE"):
            driver.retain_prerequisite("toolchains/SystemVersion.plist", raw)
        with self.assertRaisesRegex(app.RouteError, "UNSAFE_EXPORT"):
            self.failed_tail(driver)
        self.assertFalse(driver.safe)
        self.assertTrue((driver.work / "home").exists())

    def test_hold_seal_rejects_incomplete_originals_and_unsafe_commands(self):
        ids = self.partial_packet()
        name = "commands/iphoneos-build/record.json"
        original = (self.public / name).read_bytes()
        for mutation in (lambda value: value.update(retirement="UNKNOWN"), lambda value: value.update(errors=["synthetic"]),
                         lambda value: value.update(exitCode=125), lambda value: value.update(outputs={})):
            save(self.public / name, original)
            self.mutate(name, mutation)
            with self.subTest(mutation=mutation), self.assertRaises(app.RouteError):
                self.validate()
        save(self.public / name, original)
        (self.public / "leaves" / ids["iphoneos-build"] / "stop.stderr.log").unlink()
        self.reseal()
        with self.assertRaises(FileNotFoundError):
            self.validate()

    def test_hold_seal_rejects_hidden_phase_omissions_and_later_productive_work(self):
        self.partial_packet()
        name = "result.json"
        original = (self.public / name).read_bytes()
        for mutation in (lambda value: value["attemptedLeaves"].pop("iphoneos-build"),
                         lambda value: value.update(contextInitialized=False), lambda value: value["commands"].remove("memory")):
            save(self.public / name, original)
            self.mutate(name, mutation)
            with self.subTest(mutation=mutation), self.assertRaises(app.RouteError):
                self.validate()
        save(self.public / name, original)
        self.mutate("commands/memory/record.json", lambda value: value.update(exitCode=1))
        with self.assertRaisesRegex(app.RouteError, "PUBLIC_COMMAND_ORDER"):
            self.validate()

    def test_hold_seal_checks_actual_source_and_original_cleanup(self):
        self.partial_packet()
        self.mutate("result.json", lambda value: value["sourceAfter"].update(diffSha256="f" * 64))
        with self.assertRaisesRegex(app.RouteError, "PUBLIC_RESULT_SOURCE"):
            self.validate()
        self.mutate("result.json", lambda value: value.update(sourceAfter=self.source_state))
        self.mutate("cleanup/receipt.json", lambda value: value.update(removed=[]))
        with self.assertRaisesRegex(app.RouteError, "PUBLIC_CLEANUP_ORIGINALS"):
            self.validate()

    def test_toolchain_hold_has_no_leaf_or_download_and_retains_actual_source_drift(self):
        driver = self.driver()
        dirty = {**self.source_state, "status": " M samples/iosApp/Info.plist\n", "diffSha256": "e" * 64}
        with mock.patch.object(app.time, "monotonic", side_effect=self.clock.monotonic), \
                mock.patch.object(driver, "prerequisites", side_effect=app.RouteError("SYNTHETIC_TOOLCHAIN_HOLD")), \
                mock.patch.object(AUDIT, "source_snapshot", return_value=dirty):
            self.assertEqual(driver.run(), 2)
        result = app.parse((driver.public / "result.json").read_bytes())
        self.assertEqual(result["result"], "HOLD")
        self.assertEqual(result["sourceAfter"], dirty)
        self.assertFalse(result["sourceUnchanged"])
        self.assertEqual(result["commands"], [])
        self.env["P2PKIT_IPHONEOS_RUN_OUTCOME"] = "failure"
        with mock.patch.object(AUDIT, "source_snapshot", return_value=dirty):
            self.assertEqual(self.validate(), 0)
        with self.assertRaisesRegex(app.RouteError, "PUBLIC_RESULT_SOURCE"):
            self.validate()  # A later different source state cannot reuse that HOLD.
        self.assertIn(b"product_passed=false", Path(self.env["GITHUB_OUTPUT"]).read_bytes())

    def test_failure_export_normalizes_identity_only_not_pass_admission(self):
        dirty = {**self.source_state, "status": " M changed\n", "diffSha256": "f" * 64}
        with mock.patch.object(AUDIT, "git", return_value=b"false\n"), \
                mock.patch.object(AUDIT, "source_snapshot", return_value=dirty):
            self.assertEqual(app.admission(self.env, AUDIT, failure_export=True)["source"], self.source_state)
            with self.assertRaises(app.RouteError):
                app.admission(self.env, AUDIT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
