#!/usr/bin/env python3
"""One isolated CLI/application discovery comparison; never native qualification."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import signal
import stat
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("platform_gate", ROOT / "scripts/run-platform-tests.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
APP = "P2pKitLanHostProbe"
BUNDLE = "dev.p2pkit.diagnostics.lanhost"
FILES = ("LanProbe.swift", "main.swift", "App.swift", "UITests.swift", "project.yml")
SCOPE = "INTEL_LAN_HOST_COMPARISON_DIAGNOSTIC_V1"
EXECUTION_END = None
RUNNER_BUNDLE = BUNDLE + ".uitests.xctrunner"


def require(value, reason):
    if not value:
        raise ValueError(reason)


def encoded(value):
    return GATE.simulator.encoded(value)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    GATE._intel_write(path, encoded(value))


def private_dir(path):
    path.mkdir(mode=0o700, exist_ok=False)
    require(path.resolve(strict=True) == path and path.stat().st_uid == os.geteuid(), "DIRECTORY_IDENTITY")
    return path


def read_file(path, limit):
    mode = path.lstat()
    require(stat.S_ISREG(mode.st_mode) and mode.st_uid == os.geteuid() and 0 < mode.st_size <= limit,
            "FILE_IDENTITY_OR_LIMIT")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) == mode.st_size, "FILE_CHANGED_OR_EXCESSIVE")
    return raw


def command(directory, label, argv):
    """Reuse unchanged 120s command capture and 15+5s owned-group retirement."""
    require(EXECUTION_END is not None and time.monotonic() + 140 <= EXECUTION_END, "COMMAND_WINDOW")
    row = GATE._intel_capture_phase(directory, label, argv)
    raw = GATE.simulator_original(directory / label / "result.json")
    require(raw == encoded(row), "COMMAND_RESULT_CHANGED")
    streams = {}
    for name in ("stdout", "stderr"):
        value = GATE.simulator_original(directory / label / (name + ".bin"), allow_empty=True)
        require(len(value) == row[name + "Bytes"] and digest(value) == row[name + "Sha256"],
                "COMMAND_STREAM_CHANGED")
        streams[name] = value
    require(row["exitCode"] == 0 and row["timedOut"] is False and
            row["outputLimitExceeded"] is False and row["ownedGroupDrained"] is True, "COMMAND_FAILED")
    return streams


def installed_path(raw, udid):
    text = raw.decode("utf-8").strip()
    require("\n" not in text and text.startswith("/"), "INSTALL_CONTAINER_FORMAT")
    path = Path(text)
    base = Path.home() / "Library/Developer/CoreSimulator/Devices" / udid / "data/Containers/Bundle/Application"
    require(path.name == APP + ".app" and path.parent.parent == base and
            re.fullmatch(r"[0-9A-Fa-f-]{36}", path.parent.name) and
            path.resolve(strict=True) == path, "INSTALL_CONTAINER_IDENTITY")
    return path


def installed_bundles(evidence, label, udid):
    command(evidence, label, ["/usr/bin/xcrun", "simctl", "listapps", udid])
    streams = command(evidence, label + "-json", ["/usr/bin/plutil", "-convert", "json", "-o", "-",
                                                 str(evidence / label / "stdout.bin")])
    value = GATE.simulator.parse(streams["stdout"])
    require(type(value) is dict and all(type(k) is str for k in value), "APP_INVENTORY")
    return set(value)


def application_identity(path, evidence, label):
    plist_raw = read_file(path / "Info.plist", 65536)
    data = plistlib.loads(plist_raw)
    require(data.get("CFBundleIdentifier") == BUNDLE and data.get("CFBundleExecutable") == APP and
            data.get("CFBundlePackageType") == "APPL" and
            type(data.get("NSLocalNetworkUsageDescription")) is str and
            bool(data["NSLocalNetworkUsageDescription"].strip()) and
            data.get("NSBonjourServices") == ["_p2pkit._tcp"], "APP_PACKAGE_IDENTITY")
    executable = read_file(path / APP, 64 * 1024 * 1024)
    GATE._intel_write(evidence / (label + "-Info.plist"), plist_raw)
    identity = {"bundle": BUNDLE, "executable": APP, "executableBytes": len(executable),
                "executableSha256": digest(executable), "plistSha256": digest(plist_raw)}
    write(evidence / (label + "-identity.json"), identity)
    return identity


COUNTERS = {"listenerReady", "listenerWaiting", "listenerFailed", "browserReady", "browserWaiting",
            "browserFailed", "registrationAdded", "registrationRemoved", "resultCallbacks", "maximumResultCount",
            "unexpectedConnections"}
PEER_BOOLS = {"listenerCancelled", "browserCancelled", "ownRegistrationObserved", "registrationNameChanged",
              "expectedPeerObserved"}
PACKAGE_KEYS = {"readOK", "usageDescriptionPresent", "requiredBonjourPresent", "bundleIdentifierPresent",
                "expectedBundleIdentifier", "applicationPackageType"}
STATES = {"none", "setup", "waiting", "ready", "failed", "cancelled", "unknown"}


def exact_keys(value, keys):
    require(type(value) is dict and set(value) == set(keys), "SUMMARY_KEYS")


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, "SUMMARY_INTEGER")


def booleans(value, keys):
    for key in keys:
        require(type(value[key]) is bool, "SUMMARY_BOOLEAN")


def validate_probe(probe, arm):
    exact_keys(probe, {"schema", "diagnosticOnly", "mode", "outcome", "windowMilliseconds",
        "observationElapsedMilliseconds", "cleanupElapsedMilliseconds", "isSimulatorBuild", "isX86_64Build",
        "counterOverflow", "packaging", "peers", "cleanup"})
    integer(probe["schema"], 1, 1)
    booleans(probe, {"diagnosticOnly", "isSimulatorBuild", "isX86_64Build", "counterOverflow"})
    require(probe["diagnosticOnly"] and probe["isSimulatorBuild"] and probe["isX86_64Build"] and
            not probe["counterOverflow"] and probe["mode"] == arm.lower(), "SUMMARY_ROLE")
    require(probe["outcome"] in {"discovered", "notDiscovered", "setupFailed"}, "UNUSABLE_OBSERVATION")
    integer(probe["windowMilliseconds"], 30000, 30000)
    integer(probe["observationElapsedMilliseconds"], 30000, 120000)
    integer(probe["cleanupElapsedMilliseconds"], 0, 5000)
    exact_keys(probe["packaging"], PACKAGE_KEYS)
    booleans(probe["packaging"], PACKAGE_KEYS)
    if arm == "APP":
        require(all(probe["packaging"].values()), "RUNNING_APP_PACKAGE")
    else:
        require(not probe["packaging"]["expectedBundleIdentifier"], "CLI_APP_IDENTITY")
    peers = probe["peers"]
    require(type(peers) is list and len(peers) == 2, "PEER_COUNT")
    for peer in peers:
        exact_keys(peer, COUNTERS | PEER_BOOLS | {"listenerLastState", "browserLastState", "listenerError", "browserError"})
        for key in COUNTERS:
            integer(peer[key], 0, 65535)
        booleans(peer, PEER_BOOLS)
        require(peer["unexpectedConnections"] == 0, "UNOWNED_CONNECTION_CLEANUP")
        for kind in ("listener", "browser"):
            require(peer[kind + "LastState"] in STATES, "PEER_STATE")
            error = peer[kind + "Error"]
            exact_keys(error, {"domain", "code"})
            require(error["domain"] in {"none", "dns", "posix", "tls", "other"}, "ERROR_DOMAIN")
            integer(error["code"], -(2 ** 31), 2 ** 31 - 1)
            require(error["domain"] != "none" or error["code"] == 0, "EMPTY_ERROR_CODE")
        require(not peer["ownRegistrationObserved"] or peer["registrationAdded"] > 0, "REGISTRATION_OBSERVATION")
        require(not peer["expectedPeerObserved"] or peer["resultCallbacks"] > 0, "PEER_OBSERVATION")
    cleanup = probe["cleanup"]
    exact_keys(cleanup, {"listenersCreated", "listenersCancelled", "browsersCreated", "browsersCancelled", "complete"})
    require(cleanup["complete"] is True, "INCOMPLETE_PROBE_CLEANUP")
    for key in set(cleanup) - {"complete"}:
        integer(cleanup[key], 0, 2)
    for plural, singular in (("listeners", "listener"), ("browsers", "browser")):
        require(cleanup[plural + "Created"] == cleanup[plural + "Cancelled"] ==
                sum(peer[singular + "Cancelled"] for peer in peers), "CANCELLATION_COUNT")
    if probe["outcome"] != "setupFailed":
        require(cleanup["listenersCreated"] == cleanup["browsersCreated"] == 2, "CREATED_PEER_COUNT")
        require((probe["outcome"] == "discovered") == all(peer["expectedPeerObserved"] for peer in peers),
                "DISCOVERY_RESULT")
    return probe


def probe_result(streams, arm, token):
    marker = b"P2PKIT_LAN_HOST_V1 " if arm == "CLI" else b"P2PKIT_LAN_APP_V1 "
    matches = []
    for stream in streams.values():
        for line in stream.splitlines():
            if marker in line:
                require(line.count(marker) == 1, "DUPLICATE_MARKER_ON_LINE")
                raw = line.split(marker, 1)[1]
                require(0 < len(raw) <= 8192, "MARKER_LIMIT")
                matches.append(GATE.simulator.parse(raw))
    require(len(matches) == 1, "MISSING_OR_DUPLICATE_PROBE_RESULT")
    value = matches[0]
    exact_keys(value, {"schema", "token", "probe"} if arm == "CLI" else
               {"schema", "token", "probe", "permission", "appNotRunning"})
    integer(value["schema"], 1, 1)
    require(value["token"] == token, "STALE_PROBE_TOKEN")
    probe = validate_probe(value["probe"], arm)
    result = {"probe": probe, "originals": {name + "Sha256": digest(raw) for name, raw in streams.items()}}
    if arm == "APP":
        require(value["permission"] in {"notObserved", "handled", "unhandled"} and
                value["appNotRunning"] is True, "APP_RETIREMENT_OR_PERMISSION")
        result["permission"], result["appNotRunning"] = value["permission"], True
    return result


def emit(arm, value, source, context):
    summary = {"schema": 1, "scope": SCOPE, "qualification": False, "arm": arm,
               "sourceSha": source["commit"], "sourceTree": source["tree"],
               "runId": context["GITHUB_RUN_ID"], "attempt": context["GITHUB_RUN_ATTEMPT"],
               "job": context["GITHUB_JOB"], "observation": value}
    raw = encoded(summary)
    require(len(raw) <= 8192, "SUMMARY_LIMIT")
    print("P2PKIT_LAN_HOST_SUMMARY_V1 " + raw.decode("ascii").strip(), flush=True)


def run():
    global EXECUTION_END
    monotonic_start = time.monotonic()
    # Productive commands leave 9*140s for install cleanup/owned retirement.
    # A late prepare cannot install: the first command rejects it, so only
    # 3*140s owner retirement follows prepare (8*140 + 320s maximum).
    EXECUTION_END = monotonic_start + 900
    os.umask(0o077)
    require(GATE.ROOT == ROOT and GATE.platform.system() == "Darwin" and
            GATE.architecture(GATE.platform.machine()) == "x64", "HOST")
    names = (*GATE.INTEL_GITHUB.values(), "GITHUB_WORKSPACE", "DEVELOPER_DIR", "GITHUB_EVENT_NAME",
             "RUNNER_ENVIRONMENT", "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion")
    context = {name: os.environ.get(name) for name in names}
    require(all(type(v) is str and 0 < len(v) <= 4096 for v in context.values()) and
            context["GITHUB_ACTIONS"] == "true" and context["RUNNER_ENVIRONMENT"] == "github-hosted" and
            context["RUNNER_OS"] == "macOS" and context["RUNNER_ARCH"] == "X64" and
            context["GITHUB_REPOSITORY"] == "p2pKit/P2pKit" and context["GITHUB_JOB"] == "ios-x64" and
            context["GITHUB_EVENT_NAME"] == "workflow_dispatch" and
            context["GITHUB_REF"] == "refs/heads/work/foundation-intel-lan-host-20261007-lv7cq3ny" and
            context["DEVELOPER_DIR"] == "/Applications/Xcode_26.3.app/Contents/Developer" and
            Path(context["GITHUB_WORKSPACE"]).resolve() == ROOT and
            all(re.fullmatch(r"[1-9][0-9]*", context[k]) for k in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")),
            "HOSTED_CONTEXT")
    source = GATE.source_state()
    GATE._intel_source(source)
    require(source["commit"] == context["GITHUB_SHA"], "SOURCE_SHA")
    require(GATE.ordinary_simulator_binding("ios-x64", "x64", source) is None, "ORDINARY_CONTEXT")
    token = uuid.uuid4().hex
    # Build products are ignored and separate from the retained bounded evidence.
    for rel in ("build", "build/reports", "build/reports/intel-lan-host", "build/intel-lan-host"):
        path = ROOT / rel
        path.mkdir(mode=0o700, exist_ok=True)
        require(path.resolve(strict=True) == path and path.stat().st_uid == os.geteuid(), "BUILD_PARENT")
    evidence = private_dir(ROOT / "build/reports/intel-lan-host" / token)
    work = private_dir(ROOT / "build/intel-lan-host" / token)
    generated = private_dir(work / "generated")
    manifest = {}
    for name in FILES:
        raw = read_file(Path(__file__).parent / name, 128 * 1024)
        target = generated / name
        GATE._intel_write(target, raw)
        manifest[name] = {"bytes": len(raw), "sha256": digest(raw)}
    write(evidence / "source.json", {"source": source, "context": context, "token": token,
                                    "sharedInputs": manifest, "qualification": False})
    owner, results, errors = None, {}, []
    installed = False
    runner_attempted = False
    retired = False
    phase = "PREPARE"
    started = datetime.now(timezone.utc).isoformat()

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt()

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        owner = GATE.IntelSimulatorOwner(evidence, {**source, "token": token})
        owner.prepare()
        udid = owner.selected["device"]["udid"]
        phase = "BUILD"
        sdk = command(evidence, "sdk-path", ["/usr/bin/xcrun", "--sdk", "iphonesimulator", "--show-sdk-path"])
        sdk_path = sdk["stdout"].decode("utf-8").strip()
        require(sdk_path.startswith(context["DEVELOPER_DIR"] + "/Platforms/") and
                "\n" not in sdk_path and Path(sdk_path).is_dir(), "SDK_PATH")
        binary = work / "P2pKitLanHostCLI"
        command(evidence, "compile-cli", ["/usr/bin/xcrun", "swiftc", "-sdk", sdk_path,
                "-target", "x86_64-apple-ios15.0-simulator", "-swift-version", "5", "-warnings-as-errors",
                "-j", "2",
                str(generated / "LanProbe.swift"), str(generated / "main.swift"), "-o", str(binary)])
        command(evidence, "cli-architecture", ["/usr/bin/lipo", "-verify_arch", "x86_64", str(binary)])
        cli_binary = read_file(binary, 64 * 1024 * 1024)
        write(evidence / "cli-binary.json", {"bytes": len(cli_binary), "sha256": digest(cli_binary)})
        phase = "CLI"
        cli = command(evidence, "cli-probe", ["/usr/bin/xcrun", "simctl", "spawn", udid,
                                              str(binary), "--token", token])
        results["CLI"] = probe_result(cli, "CLI", token)
        emit("CLI", results["CLI"], source, context)
        # No app installation/permission exists before the successfully retired CLI arm.
        phase = "APP_BUILD"
        command(evidence, "install-xcodegen", ["/bin/bash", str(ROOT / "scripts/install-xcodegen.sh"),
                                               str(work / "xcodegen")])
        xcodegen = work / "xcodegen/bin/xcodegen"
        command(evidence, "generate-app", [str(xcodegen), "generate", "--spec", str(generated / "project.yml"),
                                           "--project", str(generated)])
        derived = work / "derived"
        xcode = ["/usr/bin/xcodebuild", "-project", str(generated / (APP + ".xcodeproj")),
                 "-scheme", APP, "-configuration", "Debug", "-sdk", "iphonesimulator",
                 "-destination", "id=" + udid, "-derivedDataPath", str(derived), "-jobs", "2",
                 "-parallel-testing-enabled", "NO", "-maximum-concurrent-test-simulator-destinations", "1",
                 "CODE_SIGNING_ALLOWED=NO", "ARCHS=x86_64", "ONLY_ACTIVE_ARCH=YES"]
        command(evidence, "build-app", xcode + ["build-for-testing"])
        app = derived / "Build/Products/Debug-iphonesimulator" / (APP + ".app")
        built = application_identity(app, evidence, "built")
        command(evidence, "app-architecture", ["/usr/bin/lipo", "-verify_arch", "x86_64", str(app / APP)])
        runner_plist = read_file(derived / "Build/Products/Debug-iphonesimulator" /
                                 "P2pKitLanHostProbeUITests-Runner.app/Info.plist", 65536)
        require(plistlib.loads(runner_plist).get("CFBundleIdentifier") == RUNNER_BUNDLE, "UI_RUNNER_IDENTITY")
        GATE._intel_write(evidence / "built-runner-Info.plist", runner_plist)
        phase = "APP_INSTALL"
        require(not {BUNDLE, RUNNER_BUNDLE} & installed_bundles(evidence, "apps-before", udid),
                "PREEXISTING_DIAGNOSTIC_INSTALL")
        installed = True  # A partial install must still be retired if interrupted.
        command(evidence, "install-app", ["/usr/bin/xcrun", "simctl", "install", udid, str(app)])
        container = command(evidence, "installed-app", ["/usr/bin/xcrun", "simctl", "get_app_container", udid,
                                                       BUNDLE, "app"])
        actual = application_identity(installed_path(container["stdout"], udid), evidence, "installed")
        require(actual == built, "INSTALLED_APP_MISMATCH")
        phase = "APP"
        os.environ["TEST_RUNNER_P2PKIT_LAN_HOST_TOKEN"] = token
        runner_attempted = True
        try:
            app_streams = command(evidence, "app-probe", xcode + ["-test-iterations", "1",
                "-only-testing:P2pKitLanHostProbeUITests/LanHostProbeUITests/testApplicationHostProbe",
                "test-without-building"])
        finally:
            os.environ.pop("TEST_RUNNER_P2PKIT_LAN_HOST_TOKEN", None)
        results["APP"] = probe_result(app_streams, "APP", token)
        container_after = command(evidence, "installed-app-after", ["/usr/bin/xcrun", "simctl", "get_app_container",
                                                                     udid, BUNDLE, "app"])
        require(application_identity(installed_path(container_after["stdout"], udid), evidence,
                                     "installed-after") == built, "POST_APP_MISMATCH")
        emit("APP", results["APP"], source, context)
    except KeyboardInterrupt:
        errors.append(phase + "_INTERRUPTED")
    except Exception:
        errors.append(phase + "_FAILED")
    finally:
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            EXECUTION_END = monotonic_start + 2180
            if installed and owner is not None and owner.selected is not None:
                udid = owner.selected["device"]["udid"]
                try:
                    present = installed_bundles(evidence, "apps-retire-before", udid)
                    targets = (BUNDLE, RUNNER_BUNDLE) if runner_attempted else (BUNDLE,)
                    for index, bundle in enumerate(targets):
                        if bundle in present:
                            command(evidence, "uninstall-" + str(index),
                                    ["/usr/bin/xcrun", "simctl", "uninstall", udid, bundle])
                    require(not set(targets) & installed_bundles(evidence, "apps-retire-after", udid),
                            "INSTALL_RETIREMENT_NOT_OBSERVED")
                except Exception:
                    errors.append("UNINSTALL_FAILED")
            if owner is not None:
                try:
                    retired = not owner.retire()
                    require(retired, "RETIREMENT_REJECTED")
                    for name, raw in owner.originals.items():
                        require(GATE.simulator_original(owner.directory / name,
                            allow_empty=not name.endswith("result.json")) == raw, "ORIGINAL_CHANGED")
                    for name, raw in (("binding.json", owner.binding_raw), ("retirement.json", owner.retirement_raw)):
                        if raw is not None:
                            require(GATE.simulator_original(owner.directory / name) == raw, "BINDING_CHANGED")
                except Exception:
                    errors.append("RETIREMENT_OR_ORIGINAL_FAILED")
            try:
                require(GATE.source_state() == source and context == {name: os.environ.get(name) for name in names},
                        "SOURCE_OR_CONTEXT_CHANGED")
                for name, expected in manifest.items():
                    raw = read_file(generated / name, 128 * 1024)
                    require({"bytes": len(raw), "sha256": digest(raw)} == expected, "GENERATED_INPUT_CHANGED")
            except Exception:
                errors.append("SOURCE_OR_INPUT_CHANGED")
            result = {"schema": 1, "scope": SCOPE, "qualification": False, "gradleLaunched": False,
                      "source": source, "context": context, "token": token, "results": results,
                      "startedUtc": started, "finishedUtc": datetime.now(timezone.utc).isoformat(),
                      "simulatorRetired": retired, "errors": errors}
            write(evidence / "comparison.json", result)
            print("P2PKIT_LAN_HOST_COMPLETION_V1 " + encoded({"qualification": False,
                  "complete": set(results) == {"CLI", "APP"} and retired and not errors,
                  "simulatorRetired": retired, "errors": errors}).decode("ascii").strip(), flush=True)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    return 0 if set(results) == {"CLI", "APP"} and retired and not errors else 1


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception:
        print("P2PKIT_LAN_HOST_DIAGNOSTIC_FAILED", flush=True)
        sys.exit(1)
