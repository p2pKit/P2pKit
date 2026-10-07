#!/usr/bin/env python3
"""Same-live owned TXT scope queries with an SRV control; never native qualification."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
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
FILES = ("LanProbe.swift", "main.swift")
POLICIES = ("OWNED_TXT",)
SCOPE = "INTEL_LAN_OWNED_TXT_DIAGNOSTIC_V1"
MARKER = b"P2PKIT_LAN_OWNED_TXT_V1 "
EXECUTION_END = None


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
    """Use fixed label work ceilings and unchanged 15+5s owned-group retirement."""
    required_seconds = (GATE._intel_work_seconds(label) + GATE.TERMINATION_GRACE_SECONDS +
                        GATE.TERMINATION_KILL_SECONDS)
    require(EXECUTION_END is not None and time.monotonic() + required_seconds <= EXECUTION_END, "COMMAND_WINDOW")
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


COUNTERS = {"listenerReady", "listenerWaiting", "listenerFailed", "browserReady", "browserWaiting",
            "browserFailed", "registrationAdded", "registrationRemoved", "resultCallbacks", "maximumResultCount",
            "unexpectedConnections"}
PEER_BOOLS = {"listenerCancelled", "browserCancelled", "ownRegistrationObserved", "registrationNameChanged",
              "expectedPeerObserved"}
PACKAGE_KEYS = {"readOK", "usageDescriptionPresent", "requiredBonjourPresent", "bundleIdentifierPresent",
                "expectedBundleIdentifier", "applicationPackageType"}
STATES = {"none", "setup", "waiting", "ready", "failed", "cancelled", "unknown"}

CONFIG_BOOLS = {"listenerObserved", "listenerNoDelay", "listenerP2P", "listenerCellBan",
                "browserObserved", "browserP2P", "browserCellBan", "browserIncludesTXT",
                "advertisementAfterReady", "noAutoRename", "configuredServiceTxtPresent",
                "configuredServiceTxtReadbackMatches", "configuredServiceTxtShapeValid"}
CONFIG_TRANSPORTS = {"listenerTransport", "browserTransport"}
TRANSPORTS = {"unobserved", "none", "tcp", "other"}
TXT_COUNTERS = {"started", "callbacks", "matchingCallbacks", "removedCallbacks", "absenceCallbacks", "bytes"}
TXT_BOOLS = {"received", "matchesExpected", "malformed", "identityMatched", "interfaceMatched", "retired", "present"}
QUERY_FIELDS = ("txtQuery", "localTxtQuery", "localSrvQuery")
QUERY_RETIREMENT_REASONS = {"none", "cutoff", "interfaceRemoved", "serviceRemoved", "browserFailed",
                          "queueFailed", "callbackFailed", "invalidCallback"}
CALLBACK_INTERFACE_CLASSES = {"none", "selectedConcrete", "otherConcrete", "localOnly", "p2p", "unicast",
                             "ble", "any", "otherSpecial"}
SELECTED_INTERFACE_KINDS = {"none", "wifi", "wiredEthernet", "loopback", "other"}


def exact_keys(value, keys):
    require(type(value) is dict and set(value) == set(keys), "SUMMARY_KEYS")


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, "SUMMARY_INTEGER")


def booleans(value, keys):
    for key in keys:
        require(type(value[key]) is bool, "SUMMARY_BOOLEAN")


def validate_configuration(value, policy, listener_ready, setup_failed):
    exact_keys(value, CONFIG_BOOLS | CONFIG_TRANSPORTS)
    booleans(value, CONFIG_BOOLS)
    for key in CONFIG_TRANSPORTS:
        require(type(value[key]) is str and value[key] in TRANSPORTS, "CONFIG_TRANSPORT")
    for prefix, expected, flags in (
        ("listener", "tcp", ("listenerNoDelay", "listenerP2P", "listenerCellBan")),
        ("browser", "none", ("browserP2P", "browserCellBan")),
    ):
        if value[prefix + "Observed"]:
            require(value[prefix + "Transport"] == expected and all(value[key] for key in flags),
                    "CONFIG_READBACK")
        else:
            require(value[prefix + "Transport"] == "unobserved" and not any(value[key] for key in flags),
                    "UNOBSERVED_CONFIGURATION")
    if value["browserObserved"]:
        require(value["browserIncludesTXT"] is False, "CONFIG_DESCRIPTOR_READBACK")
    else:
        require(value["browserIncludesTXT"] is False, "UNOBSERVED_DESCRIPTOR")
    advertised = ("noAutoRename", "configuredServiceTxtPresent", "configuredServiceTxtReadbackMatches",
                  "configuredServiceTxtShapeValid")
    if value["advertisementAfterReady"]:
        require(listener_ready > 0 and all(value[key] for key in advertised), "ADVERTISE_CONFIG_READBACK")
    else:
        require(not any(value[key] for key in advertised), "UNASSIGNED_SERVICE_CONFIG")
    if not setup_failed:
        require(value["listenerObserved"] and value["browserObserved"] and value["advertisementAfterReady"],
                "INCOMPLETE_CONFIGURATION")


def validate_txt_query(value, expected_peer_observed, field, elapsed_milliseconds, cleanup_milliseconds):
    """Role-aware observations; LocalOnly availability is not LAN interface equivalence."""
    require(field in QUERY_FIELDS, "QUERY_ROLE")
    exact_keys(value, TXT_COUNTERS | TXT_BOOLS | {"errorCode", "startMilliseconds", "retirementMilliseconds",
                                               "retirementReason", "callbackInterfaceClass"})
    booleans(value, TXT_BOOLS)
    for key in TXT_COUNTERS:
        integer(value[key], 0, 1 if key == "started" else 65535)
    integer(value["errorCode"], -(2 ** 31), 2 ** 31 - 1)
    for key in ("startMilliseconds", "retirementMilliseconds"):
        integer(value[key], -1, 125000)
        require(value[key] <= elapsed_milliseconds + cleanup_milliseconds, "QUERY_TIME_OUTSIDE_PROBE")
    reason, interface = value["retirementReason"], value["callbackInterfaceClass"]
    require(type(reason) is str and reason in QUERY_RETIREMENT_REASONS, "QUERY_RETIREMENT_REASON")
    require(type(interface) is str and interface in CALLBACK_INTERFACE_CLASSES, "QUERY_INTERFACE_CLASS")
    require(value["retired"], "UNRETIRED_TXT_QUERY")
    require(value["matchingCallbacks"] + value["removedCallbacks"] + value["absenceCallbacks"] <= value["callbacks"],
            "TXT_CALLBACK_COUNTS")
    if value["started"] == 0:
        require(not any(value[key] for key in TXT_COUNTERS - {"started"}) and
                not any(value[key] for key in TXT_BOOLS - {"retired"}), "UNSTARTED_TXT_QUERY")
        require(value["startMilliseconds"] == value["retirementMilliseconds"] == -1 and
                reason == "none" and interface == "none", "UNSTARTED_QUERY_LIFETIME")
    else:
        require(expected_peer_observed, "TXT_QUERY_WITHOUT_OWNED_PEER")
        require(reason != "none" and value["retirementMilliseconds"] >= 0, "MISSING_QUERY_RETIREMENT")
        if reason == "queueFailed":
            require(value["startMilliseconds"] == -1 and value["errorCode"] != 0 and
                    value["callbacks"] == 0, "UNSCHEDULED_QUERY_LIFETIME")
        else:
            require(0 <= value["startMilliseconds"] <= value["retirementMilliseconds"], "QUERY_LIFETIME_ORDER")
    require(reason != "interfaceRemoved" or field == "txtQuery", "LOCAL_QUERY_CONCRETE_RETIREMENT")
    if reason in {"interfaceRemoved", "serviceRemoved", "browserFailed", "callbackFailed", "invalidCallback"}:
        require(not value["present"] and not value["matchesExpected"], "RETIRED_QUERY_STALE_PRESENCE")
    if value["started"] and value["errorCode"]:
        require(reason in {"queueFailed", "callbackFailed"}, "QUERY_ERROR_WITHOUT_RETIREMENT")
    if value["callbacks"] == 0:
        require(not any(value[key] for key in ("received", "matchesExpected", "malformed",
                "identityMatched", "interfaceMatched", "bytes", "present")) and interface == "none",
                "UNOBSERVED_TXT_CALLBACK")
    require(value["interfaceMatched"] == (interface == "selectedConcrete"), "QUERY_INTERFACE_OBSERVATION")
    require(not value["received"] or value["callbacks"] > 0, "TXT_RECEIPT_WITHOUT_CALLBACK")
    require(value["bytes"] == 0 or value["received"], "TXT_BYTES_WITHOUT_RECEIPT")
    require(value["matchingCallbacks"] == 0 or value["received"], "TXT_MATCH_WITHOUT_RECEIPT")
    if value["present"]:
        require(value["started"] == 1 and value["received"] and value["identityMatched"] and
                interface != "none" and value["errorCode"] == 0, "QUERY_PRESENCE_NOT_PROVED")
        if field == "txtQuery":
            require(value["interfaceMatched"], "CONCRETE_QUERY_INTERFACE")
    if field == "localSrvQuery":
        require(value["matchingCallbacks"] == 0 and not value["matchesExpected"], "SRV_IS_NOT_TXT")
        require(not value["received"] or value["bytes"] >= 7, "SRV_AVAILABILITY_LENGTH")
    if value["matchesExpected"]:
        require(value["started"] == 1 and value["received"] and value["matchingCallbacks"] > 0 and
                value["present"] and value["bytes"] > 0 and value["identityMatched"] and
                not value["malformed"] and value["errorCode"] == 0, "TXT_MATCH_NOT_PROVED")
        if field == "txtQuery":
            require(value["interfaceMatched"], "CONCRETE_TXT_MATCH_INTERFACE")
    return value["matchesExpected"]


def validate_probe(probe, policy):
    require(policy in POLICIES, "POLICY")
    exact_keys(probe, {"schema", "diagnosticOnly", "mode", "browserDescriptor", "outcome", "windowMilliseconds",
        "observationElapsedMilliseconds", "cleanupElapsedMilliseconds", "isSimulatorBuild", "isX86_64Build",
        "counterOverflow", "packaging", "peers", "cleanup"})
    integer(probe["schema"], 1, 1)
    booleans(probe, {"diagnosticOnly", "isSimulatorBuild", "isX86_64Build", "counterOverflow"})
    require(probe["diagnosticOnly"] and probe["isSimulatorBuild"] and probe["isX86_64Build"] and
            not probe["counterOverflow"] and probe["mode"] == "cli" and
            probe["browserDescriptor"] == policy, "SUMMARY_ROLE")
    require(probe["outcome"] in {"discovered", "notDiscovered", "setupFailed"}, "UNUSABLE_OBSERVATION")
    integer(probe["windowMilliseconds"], 30000, 30000)
    integer(probe["observationElapsedMilliseconds"], 30000, 120000)
    integer(probe["cleanupElapsedMilliseconds"], 0, 5000)
    exact_keys(probe["packaging"], PACKAGE_KEYS)
    booleans(probe["packaging"], PACKAGE_KEYS)
    require(not probe["packaging"]["expectedBundleIdentifier"], "CLI_APP_IDENTITY")
    peers = probe["peers"]
    require(type(peers) is list and len(peers) == 2, "PEER_COUNT")
    for peer in peers:
        exact_keys(peer, COUNTERS | PEER_BOOLS |
                   {"listenerLastState", "browserLastState", "listenerError", "browserError", "configuration",
                    "selectedInterfaceKind", "candidateInterfaceCount"} | set(QUERY_FIELDS))
        for key in COUNTERS:
            integer(peer[key], 0, 65535)
        booleans(peer, PEER_BOOLS)
        validate_configuration(peer["configuration"], policy, peer["listenerReady"],
                               probe["outcome"] == "setupFailed")
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
        kind = peer["selectedInterfaceKind"]
        require(type(kind) is str and kind in SELECTED_INTERFACE_KINDS, "SELECTED_INTERFACE_KIND")
        integer(peer["candidateInterfaceCount"], 0, 128)
        require((kind == "none") == (peer["candidateInterfaceCount"] == 0), "SELECTED_INTERFACE_COUNT")
        for field in QUERY_FIELDS:
            validate_txt_query(peer[field], peer["expectedPeerObserved"], field,
                               probe["observationElapsedMilliseconds"], probe["cleanupElapsedMilliseconds"])
            require(peer[field]["started"] == 0 or kind != "none", "QUERY_WITHOUT_SELECTED_INTERFACE")
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
        require((probe["outcome"] == "discovered") == all(
                peer["expectedPeerObserved"] and peer["txtQuery"]["matchesExpected"] for peer in peers),
                "DISCOVERY_RESULT")
    return probe


def probe_result(streams, policy, token):
    require(policy in POLICIES and type(token) is str and re.fullmatch(r"[0-9a-f]{32}", token), "ARM_IDENTITY")
    marker = MARKER
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
    exact_keys(value, {"schema", "token", "browserDescriptor", "probe"})
    integer(value["schema"], 1, 1)
    require(value["token"] == token and value["browserDescriptor"] == policy, "STALE_PROBE_TOKEN_OR_POLICY")
    probe = validate_probe(value["probe"], policy)
    result = {"probe": probe, "originals": {name + "Sha256": digest(raw) for name, raw in streams.items()}}
    return result


def emit(arm, value, source, context):
    summary = {"schema": 1, "scope": SCOPE, "qualification": False, "arm": arm,
               "sourceSha": source["commit"], "sourceTree": source["tree"],
               "runId": context["GITHUB_RUN_ID"], "attempt": context["GITHUB_RUN_ATTEMPT"],
               "job": context["GITHUB_JOB"], "observation": value}
    raw = encoded(summary)
    require(len(raw) <= 8192, "SUMMARY_LIMIT")
    print("P2PKIT_LAN_OWNED_TXT_SUMMARY_V1 " + raw.decode("ascii").strip(), flush=True)


def run_arms(evidence, binary, udid, arm_tokens, source, context, results):
    exact_keys(arm_tokens, POLICIES)
    require(type(results) is dict and not results, "ARM_RESULTS_NOT_EMPTY")
    require(all(type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value)
                for value in arm_tokens.values()) and len(set(arm_tokens.values())) == 1, "ARM_TOKENS")
    for policy in POLICIES:
        streams = command(evidence, "cli-" + policy.lower(), ["/usr/bin/xcrun", "simctl", "spawn", udid,
                          str(binary), "--token", arm_tokens[policy], "--browser-descriptor", policy])
        # One new observation only; preserve failures and never substitute a previous descriptor arm.
        results[policy] = probe_result(streams, policy, arm_tokens[policy])
        emit(policy, results[policy], source, context)


def run():
    global EXECUTION_END
    monotonic_start = time.monotonic()
    # Keep the reviewed productive deadline and owner-retirement envelope.
    # No APP is built/installed; prepare and all three retirement captures are unchanged.
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
            context["GITHUB_REF"] == "refs/heads/work/foundation-native-frontier-20261007-CC4DEkbv" and
            context["DEVELOPER_DIR"] == "/Applications/Xcode_26.3.app/Contents/Developer" and
            Path(context["GITHUB_WORKSPACE"]).resolve() == ROOT and
            all(re.fullmatch(r"[1-9][0-9]*", context[k]) for k in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")),
            "HOSTED_CONTEXT")
    source = GATE.source_state()
    GATE._intel_source(source)
    require(source["commit"] == context["GITHUB_SHA"], "SOURCE_SHA")
    require(GATE.ordinary_simulator_binding("ios-x64", "x64", source) is None, "ORDINARY_CONTEXT")
    token = uuid.uuid4().hex
    arm_tokens = {policy: uuid.uuid4().hex for policy in POLICIES}
    require(len({token, *arm_tokens.values()}) == 2, "TOKEN_COLLISION")
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
                                    "armTokens": arm_tokens, "sharedInputs": manifest, "qualification": False})
    owner, results, errors = None, {}, []
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
        command(evidence, "cli-architecture", ["/usr/bin/lipo", str(binary), "-verify_arch", "x86_64"])
        cli_binary = read_file(binary, 64 * 1024 * 1024)
        write(evidence / "cli-binary.json", {"bytes": len(cli_binary), "sha256": digest(cli_binary)})
        phase = "CLI_OWNED_TXT"
        run_arms(evidence, binary, udid, arm_tokens, source, context, results)
    except KeyboardInterrupt:
        errors.append(phase + "_INTERRUPTED")
    except Exception:
        errors.append(phase + "_FAILED")
    finally:
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            EXECUTION_END = monotonic_start + 2180
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
                      "source": source, "context": context, "token": token, "armTokens": arm_tokens, "results": results,
                      "startedUtc": started, "finishedUtc": datetime.now(timezone.utc).isoformat(),
                      "simulatorRetired": retired, "errors": errors}
            write(evidence / "comparison.json", result)
            print("P2PKIT_LAN_OWNED_TXT_COMPLETION_V1 " + encoded({"qualification": False,
                  "complete": set(results) == set(POLICIES) and retired and not errors,
                  "simulatorRetired": retired, "errors": errors}).decode("ascii").strip(), flush=True)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    return 0 if set(results) == set(POLICIES) and retired and not errors else 1


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception:
        print("P2PKIT_LAN_OWNED_TXT_DIAGNOSTIC_FAILED", flush=True)
        sys.exit(1)
