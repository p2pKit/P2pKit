#!/usr/bin/env python3
"""Single-CLI ordinary NW endpoint and initial DNS-SD identity joins; never native qualification."""
from __future__ import annotations

from contextlib import contextmanager
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
MAINTAINED_INTEL_WORK_SECONDS = GATE._intel_work_seconds
APP = "P2pKitLanHostProbe"
BUNDLE = "dev.p2pkit.diagnostics.lanhost"
RUNNER_BUNDLE = BUNDLE + ".uitests.xctrunner"
FILES = ("LanProbe.swift", "main.swift")
POLICIES = ("BONJOUR", "WITH_TXT")
ARMS = ("CLI",)
SCOPE = "INTEL_LAN_DNS_SD_ENDPOINT_JOIN_DIAGNOSTIC_V1"
MARKER = b"P2PKIT_LAN_DNS_SD_ENDPOINT_JOIN_V1 "
APP_MARKER = b"P2PKIT_LAN_APP_V1 "
EXECUTION_END = None
BOOTSTATUS_MEASUREMENT = {"workSeconds": 600, "maintainedWorkSeconds": 300,
                         "elapsedCeilingSeconds": 620, "productiveSeconds": 1200}
RUNTIME_MEASUREMENT = {"workSeconds": 300, "maintainedWorkSeconds": 120,
                       "elapsedCeilingSeconds": 320, "productiveSeconds": 1200}
APP_PROBE_MEASUREMENT = {"workSeconds": 300, "maintainedWorkSeconds": 120,
                         "elapsedCeilingSeconds": 320, "requiredStartRoomSeconds": 460,
                         "productiveSeconds": 1200, "cleanupAbsoluteSeconds": 2480}


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


@contextmanager
def diagnostic_bootstatus_budget(owner):
    """One preparation scope; private runtime selector binding has no concurrent commands."""
    previous_seconds = GATE.INTEL_BOOTSTATUS_SECONDS
    require(type(previous_seconds) is int and previous_seconds == 300, "DIAGNOSTIC_BOOTSTATUS_BASELINE")
    original_selector = MAINTAINED_INTEL_WORK_SECONDS
    require(GATE._intel_work_seconds is original_selector and
            type(GATE.simulator.SECONDS) is int and GATE.simulator.SECONDS == 120 and
            type(GATE.TERMINATION_GRACE_SECONDS) is int and GATE.TERMINATION_GRACE_SECONDS == 15 and
            type(GATE.TERMINATION_KILL_SECONDS) is int and GATE.TERMINATION_KILL_SECONDS == 5 and
            original_selector("simulator-runtimes") == 120 and original_selector("intel-bootstatus") == 300,
            "DIAGNOSTIC_RUNTIME_BASELINE")
    attributes = vars(owner)
    had_phase = "phase" in attributes
    previous_attribute = attributes.get("phase")
    original_phase = owner.phase

    def runtime_seconds(label):
        require(GATE._intel_work_seconds is runtime_seconds, "DIAGNOSTIC_RUNTIME_BINDING")
        return 300 if type(label) is str and label == "simulator-runtimes" else original_selector(label)

    def measured_phase(label):
        require(type(label) is str and label in GATE.INTEL_PREPARE, "DIAGNOSTIC_OWNER_PHASE")
        require(GATE.INTEL_BOOTSTATUS_SECONDS == previous_seconds, "DIAGNOSTIC_BOOTSTATUS_BASELINE")
        require(GATE._intel_work_seconds is original_selector, "DIAGNOSTIC_RUNTIME_BASELINE")
        work = 600 if label == "intel-bootstatus" else 300 if label == "simulator-runtimes" else original_selector(label)
        required = work + GATE.TERMINATION_GRACE_SECONDS + GATE.TERMINATION_KILL_SECONDS
        require(EXECUTION_END is not None and time.monotonic() + required <= EXECUTION_END,
                "DIAGNOSTIC_PREPARE_WINDOW")
        if label == "simulator-runtimes":
            try:
                # The same binding covers the original capture AND original phase validation.
                GATE._intel_work_seconds = runtime_seconds
                result = original_phase(label)
                require(GATE._intel_work_seconds is runtime_seconds, "DIAGNOSTIC_RUNTIME_BINDING")
                return result
            finally:
                GATE._intel_work_seconds = original_selector
        if label != "intel-bootstatus":
            return original_phase(label)
        try:
            # The original phase uses this same named constant for capture AND validation.
            GATE.INTEL_BOOTSTATUS_SECONDS = 600
            return original_phase(label)
        finally:
            GATE.INTEL_BOOTSTATUS_SECONDS = previous_seconds

    try:
        attributes["phase"] = measured_phase
        yield
        require(GATE._intel_work_seconds is original_selector, "DIAGNOSTIC_RUNTIME_BINDING")
    finally:
        GATE._intel_work_seconds = original_selector
        GATE.INTEL_BOOTSTATUS_SECONDS = previous_seconds
        if had_phase:
            attributes["phase"] = previous_attribute
        else:
            attributes.pop("phase", None)


@contextmanager
def diagnostic_app_probe_budget():
    """Temporarily bind this diagnostic process's private GATE selector; no concurrent commands."""
    original_selector = MAINTAINED_INTEL_WORK_SECONDS
    require(GATE._intel_work_seconds is original_selector and
            type(GATE.simulator.SECONDS) is int and GATE.simulator.SECONDS == 120 and
            type(GATE.INTEL_BOOTSTATUS_SECONDS) is int and GATE.INTEL_BOOTSTATUS_SECONDS == 300 and
            type(GATE.TERMINATION_GRACE_SECONDS) is int and GATE.TERMINATION_GRACE_SECONDS == 15 and
            type(GATE.TERMINATION_KILL_SECONDS) is int and GATE.TERMINATION_KILL_SECONDS == 5 and
            original_selector("app-probe") == 120 and original_selector("intel-bootstatus") == 300,
            "DIAGNOSTIC_APP_PROBE_BASELINE")

    def measured_seconds(label):
        require(GATE._intel_work_seconds is measured_seconds, "DIAGNOSTIC_APP_PROBE_BINDING")
        return 300 if type(label) is str and label == "app-probe" else original_selector(label)

    try:
        GATE._intel_work_seconds = measured_seconds
        yield
        require(GATE._intel_work_seconds is measured_seconds, "DIAGNOSTIC_APP_PROBE_BINDING")
    finally:
        GATE._intel_work_seconds = original_selector


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

CONFIG_BOOLS = {"listenerObserved", "listenerNoDelay", "listenerP2P", "listenerCellBan",
                "browserObserved", "browserP2P", "browserCellBan", "browserIncludesTXT",
                "advertisementAfterReady", "noAutoRename", "configuredServiceTxtPresent",
                "configuredServiceTxtReadbackMatches", "configuredServiceTxtShapeValid"}
CONFIG_TRANSPORTS = {"listenerTransport", "browserTransport"}
TRANSPORTS = {"unobserved", "none", "tcp", "other"}
TXT_HISTORY = {"observations", "matchingObservations", "malformedObservations"}
TXT_BOOLS = {"received", "present", "identityMatched", "matchesExpected", "rawMatchesExpected", "malformed"}
TXT_KINDS = {"none", "bonjour", "other", "mixed"}
INTERFACE_KINDS = {"cellular", "loopback", "other", "unknown", "wifi", "wiredEthernet"}


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
        require(value["browserIncludesTXT"] is (policy == "WITH_TXT"), "CONFIG_DESCRIPTOR_READBACK")
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


def validate_interfaces(value, owned_results):
    exact_keys(value, {"observed", "count", "kinds"})
    booleans(value, {"observed"})
    integer(value["count"], 0, 128)
    kinds = value["kinds"]
    require(type(kinds) is list and len(kinds) <= len(INTERFACE_KINDS) and
            all(type(kind) is str and kind in INTERFACE_KINDS for kind in kinds) and
            kinds == sorted(set(kinds)) and len(kinds) <= value["count"], "INTERFACE_KINDS")
    require(value["observed"] == (owned_results > 0), "INTERFACE_OBSERVATION")
    require((value["count"] == 0) == (not kinds), "INTERFACE_COUNT")
    if not value["observed"]:
        require(value["count"] == 0, "UNOBSERVED_INTERFACES")


def validate_txt_metadata(value, peer):
    """Current actual owned-result metadata; historical counters never confer discovery."""
    exact_keys(value, TXT_HISTORY | TXT_BOOLS | {"ownedResults", "maximumBytes", "kind"})
    booleans(value, TXT_BOOLS)
    for key in TXT_HISTORY:
        integer(value[key], 0, 65535)
    integer(value["ownedResults"], 0, 128)
    integer(value["maximumBytes"], 0, 65535)
    require(type(value["kind"]) is str and value["kind"] in TXT_KINDS, "TXT_METADATA_KIND")
    require(value["matchingObservations"] <= value["observations"] and
            value["malformedObservations"] <= value["observations"], "TXT_HISTORY_COUNTS")
    if value["ownedResults"] == 0:
        require(value["kind"] == "none" and value["maximumBytes"] == 0 and
                not any(value[key] for key in TXT_BOOLS), "MISSING_CURRENT_METADATA")
    else:
        require(peer["expectedPeerObserved"] and peer["resultCallbacks"] > 0 and
                value["observations"] >= value["ownedResults"], "TXT_OWNED_RESULT")
    require(value["present"] == (value["maximumBytes"] > 0) and
            (not value["present"] or value["received"]), "TXT_CURRENT_LENGTH")
    if value["received"]:
        require(value["ownedResults"] > 0 and value["kind"] in {"bonjour", "mixed"}, "TXT_ACTUAL_DATA")
    if value["kind"] == "bonjour":
        require(value["received"], "BONJOUR_DATA_NOT_OBSERVED")
    if value["identityMatched"]:
        require(value["received"] and value["present"] and value["kind"] == "bonjour" and
                not value["malformed"], "TXT_IDENTITY_NOT_PROVED")
    if value["malformed"]:
        require(value["ownedResults"] > 0 and value["malformedObservations"] > 0, "TXT_MALFORMED_HISTORY")
    if value["matchesExpected"]:
        require(value["identityMatched"] and value["matchingObservations"] > 0 and
                value["received"] and value["present"] and value["kind"] == "bonjour" and
                not value["malformed"], "TXT_MATCH_NOT_PROVED")
    require(not value["rawMatchesExpected"] or value["matchesExpected"], "RAW_TXT_REQUIRES_SEMANTIC_MATCH")
    validate_interfaces(peer["interfaces"], value["ownedResults"])


DNS_SCOPES = {"none", "concrete", "localOnly", "p2p", "any", "otherSpecial"}
DNS_BROWSE_BOOLS = {"attempted", "created", "started", "retired", "ambiguous", "unsupportedScope"}
DNS_BROWSE_COUNTS = {"callbacks", "ownedAdds", "ownedRemoves", "batches"}
DNS_RESOLVE_BOOLS = {"attempted", "created", "started", "retired", "invalidated", "scopeMatches", "scopeValid",
                     "identityMatched", "received", "matchesExpected", "portMatches"}
DNS_TIMES = {"startMilliseconds", "retirementMilliseconds"}
JOIN_BOOLS = {"tupleMatched", "ambiguous", "policyCompatible", "initialResolveJoined"}
JOIN_RELATIONS = {"unobserved", "unavailable", "equal", "different", "ambiguous", "invalid"}


def validate_dns_sd(probe):
    """Initial DNS-SD resolution history; never substitutes for current NWBrowser admission or TXT monitoring."""
    browse = probe["dnsBrowse"]
    exact_keys(browse, DNS_BROWSE_BOOLS | DNS_BROWSE_COUNTS | DNS_TIMES | {"errorCode"})
    booleans(browse, DNS_BROWSE_BOOLS)
    for name in DNS_BROWSE_COUNTS:
        integer(browse[name], 0, 256)
    integer(browse["errorCode"], -(2 ** 31), 2 ** 31 - 1)
    end = probe["observationElapsedMilliseconds"]
    retired_end = end + probe["cleanupElapsedMilliseconds"]
    for name in DNS_TIMES:
        integer(browse[name], -1, retired_end)
    require(browse["created"] == browse["retired"], "DNS_BROWSE_RETIREMENT")
    require(not browse["created"] or browse["attempted"], "DNS_BROWSE_CREATION")
    require(not browse["started"] or browse["created"], "DNS_BROWSE_START")
    require((browse["startMilliseconds"] >= 0) == browse["attempted"] and
            (browse["retirementMilliseconds"] >= 0) == browse["retired"], "DNS_BROWSE_TIMING")
    if browse["attempted"]:
        require(browse["startMilliseconds"] <= end, "DNS_BROWSE_AFTER_CUTOFF")
    if browse["retired"]:
        require(browse["retirementMilliseconds"] >= browse["startMilliseconds"], "DNS_BROWSE_ORDER")
    require(browse["ownedAdds"] + browse["ownedRemoves"] <= browse["callbacks"] and
            browse["batches"] <= browse["callbacks"], "DNS_BROWSE_COUNTS")
    if not browse["started"]:
        require(not any(browse[name] for name in DNS_BROWSE_COUNTS) and
                not browse["ambiguous"] and not browse["unsupportedScope"], "DNS_UNSTARTED_BROWSE")
    if not browse["attempted"]:
        require(browse["errorCode"] == 0, "DNS_UNATTEMPTED_BROWSE_ERROR")
    if probe["outcome"] != "setupFailed" and all(
            peer["ownRegistrationObserved"] and peer["listenerLastState"] == "ready" and
            peer["browserLastState"] == "ready" for peer in probe["peers"]):
        require(browse["attempted"], "DNS_BROWSE_PREREQUISITE_NOT_USED")
    for peer in probe["peers"]:
        first = peer["firstResultMilliseconds"]
        integer(first, -1, end)
        require((first == -1) == (peer["resultCallbacks"] == 0), "DNS_NW_CALLBACK_TIME")
        value = peer["dnsResolve"]
        exact_keys(value, DNS_RESOLVE_BOOLS | DNS_TIMES | {"callbacks", "matchingCallbacks", "errorCode",
                   "requestedScope", "returnedScope", "bytes", "resultMilliseconds"})
        booleans(value, DNS_RESOLVE_BOOLS)
        for name in ("callbacks", "matchingCallbacks"):
            integer(value[name], 0, 1)
        integer(value["errorCode"], -(2 ** 31), 2 ** 31 - 1)
        integer(value["bytes"], 0, 65535)
        for name in DNS_TIMES | {"resultMilliseconds"}:
            integer(value[name], -1, retired_end)
        for name in ("requestedScope", "returnedScope"):
            require(type(value[name]) is str and value[name] in DNS_SCOPES, "DNS_SCOPE")
        require(value["created"] == value["retired"] and
                (not value["created"] or value["attempted"]) and
                (not value["started"] or value["created"]), "DNS_RESOLVE_LIFETIME")
        require((value["startMilliseconds"] >= 0) == value["attempted"] and
                (value["retirementMilliseconds"] >= 0) == value["retired"] and
                (value["resultMilliseconds"] >= 0) == (value["callbacks"] > 0), "DNS_RESOLVE_TIMING")
        if value["attempted"]:
            require(browse["started"] and browse["ownedAdds"] > 0 and browse["batches"] > 0 and
                    value["requestedScope"] in {"concrete", "localOnly", "p2p"} and
                    browse["startMilliseconds"] <= value["startMilliseconds"] <= end,
                    "DNS_RESOLVE_BROWSE_JOIN")
        else:
            require(value["requestedScope"] == "none" and value["errorCode"] == 0,
                    "DNS_UNATTEMPTED_RESOLVE")
        if value["retired"]:
            require(value["retirementMilliseconds"] >= value["startMilliseconds"], "DNS_RESOLVE_ORDER")
        if value["callbacks"]:
            require(value["started"] and value["startMilliseconds"] <= value["resultMilliseconds"] <= end and
                    value["resultMilliseconds"] <= value["retirementMilliseconds"], "DNS_RESOLVE_RESULT_TIME")
        if not value["callbacks"] or value["errorCode"] != 0:
            require(value["returnedScope"] == "none" and not any(value[name] for name in
                    {"scopeMatches", "scopeValid", "identityMatched", "received", "matchesExpected", "portMatches"})
                    and value["bytes"] == value["matchingCallbacks"] == 0, "DNS_NO_SUCCESS_DATA")
        if value["scopeMatches"]:
            require(value["requestedScope"] == value["returnedScope"] and value["callbacks"] == 1 and
                    value["errorCode"] == 0, "DNS_SCOPE_EQUALITY")
        valid_scope = (value["scopeMatches"] and value["requestedScope"] in {"concrete", "localOnly"}) or (
                       value["requestedScope"] == "p2p" and value["returnedScope"] == "concrete")
        require(value["scopeValid"] == valid_scope, "DNS_SCOPE_RELATION")
        require(value["matchingCallbacks"] <= value["callbacks"], "DNS_MATCH_COUNT")
        if value["received"]:
            require(value["identityMatched"] and value["scopeValid"] and value["callbacks"] == 1 and
                    value["errorCode"] == 0, "DNS_RAW_DATA_JOIN")
        else:
            require(value["bytes"] == 0 and not value["matchesExpected"] and value["matchingCallbacks"] == 0,
                    "DNS_UNRECEIVED_DATA")
        if value["matchesExpected"]:
            require(value["matchingCallbacks"] == 1 and value["received"] and value["bytes"] > 0 and
                    value["identityMatched"] and value["scopeValid"] and value["portMatches"] and
                    not value["invalidated"] and browse["errorCode"] == 0 and
                    not browse["ambiguous"] and not browse["unsupportedScope"], "DNS_MATCH_NOT_PROVED")
        if browse["errorCode"] != 0 or browse["ambiguous"] or browse["unsupportedScope"]:
            require(not value["matchesExpected"], "DNS_INVALID_BROWSE_OWNERSHIP")


def validate_endpoint_join(probe):
    """Actual current NW tuple/interfaces joined to the OTHER publisher's initial resolution only."""
    peers = probe["peers"]
    live = all(peer["ownRegistrationObserved"] and not peer["registrationNameChanged"] and
               peer["registrationRemoved"] == 0 and peer["listenerReady"] > 0 and peer["browserReady"] > 0 and
               peer["listenerLastState"] == "ready" and peer["browserLastState"] == "ready" for peer in peers)
    for index, peer in enumerate(peers):
        value = peer["endpointJoin"]
        exact_keys(value, JOIN_BOOLS | {"endpointKind", "endpointRelation", "resultRelation"})
        booleans(value, JOIN_BOOLS)
        require(type(value["endpointKind"]) is str and value["endpointKind"] in INTERFACE_KINDS | {"none"},
                "ENDPOINT_INTERFACE_KIND")
        relations = (value["endpointRelation"], value["resultRelation"])
        require(all(type(item) is str and item in JOIN_RELATIONS for item in relations), "ENDPOINT_RELATION")
        owned = peer["txtMetadata"]["ownedResults"]
        interfaces = peer["interfaces"]
        if owned == 0:
            require(not any(value[key] for key in JOIN_BOOLS) and value["endpointKind"] == "none" and
                    relations == ("unobserved", "unobserved"), "UNOBSERVED_ENDPOINT_JOIN")
            continue
        require("unobserved" not in relations, "OWNED_ENDPOINT_NOT_OBSERVED")
        if value["ambiguous"]:
            require((owned > 1 or interfaces["count"] > 1) and relations == ("ambiguous", "ambiguous") and
                    not value["tupleMatched"] and not value["policyCompatible"] and
                    not value["initialResolveJoined"], "AMBIGUOUS_ENDPOINT_JOIN")
            if owned > 1:
                require(value["endpointKind"] == "none", "MULTIPLE_ENDPOINT_SELECTION")
            continue
        require(owned == 1 and "ambiguous" not in relations, "ENDPOINT_UNIQUE_OWNER")
        if value["endpointKind"] == "none":
            require(value["endpointRelation"] in {"unavailable", "invalid"} and
                    not value["policyCompatible"], "MISSING_ENDPOINT_INTERFACE")
        if interfaces["count"] == 0:
            require(value["resultRelation"] in {"unavailable", "invalid"} and
                    not value["policyCompatible"], "MISSING_RESULT_INTERFACE")
        if value["policyCompatible"]:
            configuration = peer["configuration"]
            require(value["endpointKind"] in INTERFACE_KINDS - {"cellular", "unknown"} and
                    interfaces["count"] > 0 and interfaces["kinds"] == [value["endpointKind"]] and
                    "invalid" not in relations and configuration["browserObserved"] and
                    configuration["browserTransport"] == "none" and configuration["browserP2P"] and
                    configuration["browserCellBan"] and not configuration["browserIncludesTXT"],
                    "ENDPOINT_POLICY_NOT_PROVED")
        # validate_dns_sd already requires raw/full-name/port/scope and noninvalidated ownership for this match.
        resolved = peers[1 - index]["dnsResolve"]
        usable = live and not probe["counterOverflow"] and resolved["matchesExpected"]
        if value["tupleMatched"] or any(item in {"equal", "different"} for item in relations):
            require(usable, "ENDPOINT_OTHER_PUBLISHER_RESOLUTION")
        for relation in relations:
            if relation == "equal":
                require(resolved["returnedScope"] == "concrete", "NO_SPECIAL_SCOPE_COERCION")
        require(value["initialResolveJoined"] == (usable and value["tupleMatched"] and
                value["policyCompatible"] and relations == ("equal", "equal")), "INITIAL_ENDPOINT_JOIN")


def sdk_contract(sdk_path, evidence):
    """One bounded selected-SDK declaration check in the same run, before Swift compilation."""
    sdk = Path(sdk_path).resolve(strict=True)
    header = sdk / "usr/include/dns_sd.h"
    mode = header.lstat()
    require(stat.S_ISREG(mode.st_mode) and header.resolve(strict=True) == header and
            0 < mode.st_size <= 262144, "DNS_SDK_HEADER_IDENTITY")
    with header.open("rb") as stream:
        raw = stream.read(262145)
    require(len(raw) == mode.st_size, "DNS_SDK_HEADER_CHANGED")
    text = raw.decode("utf-8")
    checks = {
        "browse": bool(re.search(r"DNSServiceBrowse\s*\(\s*DNSServiceRef\s*\*", text)),
        "resolve": bool(re.search(r"DNSServiceResolve\s*\(\s*DNSServiceRef\s*\*", text)),
        "browseReply": bool(re.search(r"DNSServiceBrowseReply\)\s*\(\s*DNSServiceRef", text)),
        "resolveReply": bool(re.search(r"DNSServiceResolveReply\)\s*\(\s*DNSServiceRef", text)),
        "dispatchQueue": bool(re.search(r"DNSServiceSetDispatchQueue\s*\(\s*DNSServiceRef", text)),
        "deallocate": bool(re.search(r"DNSServiceRefDeallocate\s*\(\s*DNSServiceRef", text)),
        "constructFullName": bool(re.search(r"DNSServiceConstructFullName\s*\(", text)),
        "interfaceConstants": all(name in text for name in (
            "kDNSServiceInterfaceIndexAny", "kDNSServiceInterfaceIndexLocalOnly",
            "kDNSServiceInterfaceIndexP2P", "kDNSServiceFlagsIncludeP2P",
            "kDNSServiceFlagsAdd", "kDNSServiceFlagsMoreComing")),
    }
    write(evidence / "dns-sd-sdk.json", {"schema": 1, "sdkPath": sdk_path,
          "headerRelativePath": "usr/include/dns_sd.h", "headerBytes": len(raw), "headerSha256": digest(raw),
          "publicContractSha256": "5d0ca50f207f6eb02e09d743f9b65d2ade65e8f81862dcd3703845b4fe87a9c1",
          "checks": checks, "compatibleDeclarations": all(checks.values())})
    require(all(checks.values()), "DNS_SDK_CONTRACT")
    # Swift compilation against this SDK checks imported callback types/constants/linking before any probe runs.


def validate_probe(probe, policy, mode="cli"):
    require(policy in POLICIES and (mode, policy) in {("cli", "BONJOUR"), ("app", "WITH_TXT")}, "POLICY_OR_MODE")
    exact_keys(probe, {"schema", "diagnosticOnly", "mode", "browserDescriptor", "outcome", "windowMilliseconds",
        "observationElapsedMilliseconds", "cleanupElapsedMilliseconds", "isSimulatorBuild", "isX86_64Build",
        "counterOverflow", "packaging", "peers", "cleanup"} | ({"dnsBrowse"} if mode == "cli" else set()))
    integer(probe["schema"], 1, 1)
    booleans(probe, {"diagnosticOnly", "isSimulatorBuild", "isX86_64Build", "counterOverflow"})
    require(probe["diagnosticOnly"] and probe["isSimulatorBuild"] and probe["isX86_64Build"] and
            not probe["counterOverflow"] and probe["mode"] == mode and
            probe["browserDescriptor"] == policy, "SUMMARY_ROLE")
    require(probe["outcome"] in {"discovered", "notDiscovered", "setupFailed"}, "UNUSABLE_OBSERVATION")
    integer(probe["windowMilliseconds"], 30000, 30000)
    integer(probe["observationElapsedMilliseconds"], 30000, 120000)
    integer(probe["cleanupElapsedMilliseconds"], 0, 5000)
    exact_keys(probe["packaging"], PACKAGE_KEYS)
    booleans(probe["packaging"], PACKAGE_KEYS)
    if mode == "app":
        require(all(probe["packaging"].values()), "RUNNING_APP_PACKAGE")
    else:
        require(not probe["packaging"]["expectedBundleIdentifier"], "CLI_APP_IDENTITY")
    peers = probe["peers"]
    require(type(peers) is list and len(peers) == 2, "PEER_COUNT")
    for peer in peers:
        exact_keys(peer, COUNTERS | PEER_BOOLS |
                   {"listenerLastState", "browserLastState", "listenerError", "browserError", "configuration",
                    "interfaces", "txtMetadata"} |
                   ({"dnsResolve", "firstResultMilliseconds", "endpointJoin"} if mode == "cli" else set()))
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
        validate_txt_metadata(peer["txtMetadata"], peer)
        if peer["txtMetadata"]["ownedResults"] > 0:
            require(peer["browserLastState"] == "ready" and
                    all(other["listenerLastState"] == "ready" for other in peers), "CURRENT_METADATA_READINESS")
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
                peer["expectedPeerObserved"] and peer["ownRegistrationObserved"] and
                not peer["registrationNameChanged"] and peer["listenerReady"] > 0 and peer["browserReady"] > 0 and
                peer["listenerLastState"] == "ready" and peer["browserLastState"] == "ready" and
                peer["txtMetadata"]["matchesExpected"] for peer in peers),
                "DISCOVERY_RESULT")
    if mode == "cli":
        validate_dns_sd(probe)
        validate_endpoint_join(probe)
    return probe


def probe_result(streams, policy, token, mode="cli"):
    require(policy in POLICIES and (mode, policy) in {("cli", "BONJOUR"), ("app", "WITH_TXT")} and type(token) is str and
            re.fullmatch(r"[0-9a-f]{32}", token), "ARM_IDENTITY")
    marker = MARKER if mode == "cli" else APP_MARKER
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
    exact_keys(value, {"schema", "token", "browserDescriptor", "probe"} if mode == "cli" else
               {"schema", "token", "probe", "permission", "appNotRunning"})
    integer(value["schema"], 1, 1)
    require(value["token"] == token and (mode == "app" or value["browserDescriptor"] == policy),
            "STALE_PROBE_TOKEN_OR_POLICY")
    require(len(encoded(value["probe"])) <= 6144, "SHARED_PROBE_LIMIT")
    probe = validate_probe(value["probe"], policy, mode)
    result = {"probe": probe, "originals": {name + "Sha256": digest(raw) for name, raw in streams.items()}}
    if mode == "app":
        require(type(value["permission"]) is str and value["permission"] in {"notObserved", "handled"} and
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
    print("P2PKIT_LAN_DNS_SD_ENDPOINT_JOIN_SUMMARY_V1 " + raw.decode("ascii").strip(), flush=True)


def run_arms(evidence, binary, udid, arm_tokens, source, context, results):
    """The CLI runs once before any app build/install; a retired negative remains data."""
    exact_keys(arm_tokens, ARMS)
    require(type(results) is dict and not results, "ARM_RESULTS_NOT_EMPTY")
    require(all(type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value)
                for value in arm_tokens.values()) and len(set(arm_tokens.values())) == 1, "ARM_TOKENS")
    streams = command(evidence, "cli-probe", ["/usr/bin/xcrun", "simctl", "spawn", udid,
                      str(binary), "--token", arm_tokens["CLI"], "--browser-descriptor", "BONJOUR"])
    observed = probe_result(streams, "BONJOUR", arm_tokens["CLI"])
    require(observed["probe"]["outcome"] != "setupFailed", "CLI_SETUP_FAILED")
    results["CLI"] = observed
    emit("CLI", results["CLI"], source, context)


def run_app(evidence, work, generated, udid, token, source, context, results, attempts):
    """Retained actual app build/install/UI identity checks, using the other fresh token."""
    require(set(results) == {"CLI"} and type(token) is str and re.fullmatch(r"[0-9a-f]{32}", token),
            "APP_AFTER_CLI")
    exact_keys(attempts, {"installed", "runnerAttempted"})
    require(attempts["installed"] is False and attempts["runnerAttempted"] is False, "APP_ATTEMPT_REUSE")
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
    command(evidence, "app-architecture", ["/usr/bin/lipo", str(app / APP), "-verify_arch", "x86_64"])
    runner_plist = read_file(derived / "Build/Products/Debug-iphonesimulator" /
                             "P2pKitLanHostProbeUITests-Runner.app/Info.plist", 65536)
    require(plistlib.loads(runner_plist).get("CFBundleIdentifier") == RUNNER_BUNDLE, "UI_RUNNER_IDENTITY")
    GATE._intel_write(evidence / "built-runner-Info.plist", runner_plist)
    require(not {BUNDLE, RUNNER_BUNDLE} & installed_bundles(evidence, "apps-before", udid),
            "PREEXISTING_DIAGNOSTIC_INSTALL")
    attempts["installed"] = True  # Reserve before capture: a partial install must also be retired.
    command(evidence, "install-app", ["/usr/bin/xcrun", "simctl", "install", udid, str(app)])
    container = command(evidence, "installed-app", ["/usr/bin/xcrun", "simctl", "get_app_container", udid,
                                                   BUNDLE, "app"])
    actual = application_identity(installed_path(container["stdout"], udid), evidence, "installed")
    require(actual == built, "INSTALLED_APP_MISMATCH")
    require("TEST_RUNNER_P2PKIT_LAN_HOST_TOKEN" not in os.environ, "PREEXISTING_APP_TOKEN")
    # Reserve app capture/drain (320s) and the mandatory post-install identity capture (140s).
    require(EXECUTION_END is not None and time.monotonic() + 460 <= EXECUTION_END,
            "DIAGNOSTIC_APP_PROBE_WINDOW")
    attempts["runnerAttempted"] = True
    try:
        os.environ["TEST_RUNNER_P2PKIT_LAN_HOST_TOKEN"] = token
        with diagnostic_app_probe_budget():
            app_streams = command(evidence, "app-probe", xcode + [
                "-only-testing:P2pKitLanHostProbeUITests/LanHostProbeUITests/testApplicationHostProbe",
                "test-without-building"])
    finally:
        os.environ.pop("TEST_RUNNER_P2PKIT_LAN_HOST_TOKEN", None)
    observed = probe_result(app_streams, "WITH_TXT", token, mode="app")
    require(observed["probe"]["outcome"] != "setupFailed", "APP_SETUP_FAILED")
    container_after = command(evidence, "installed-app-after", ["/usr/bin/xcrun", "simctl", "get_app_container",
                                                                 udid, BUNDLE, "app"])
    require(application_identity(installed_path(container_after["stdout"], udid), evidence,
                                 "installed-after") == built, "POST_APP_MISMATCH")
    results["APP"] = observed
    emit("APP", observed, source, context)


def retire_apps(evidence, udid, attempts):
    """Only bundles reserved by this attempt, with observed post-uninstall absence."""
    if not attempts["installed"]:
        return
    present = installed_bundles(evidence, "apps-retire-before", udid)
    targets = (BUNDLE, RUNNER_BUNDLE) if attempts["runnerAttempted"] else (BUNDLE,)
    for index, bundle in enumerate(targets):
        if bundle in present:
            command(evidence, "uninstall-" + str(index), ["/usr/bin/xcrun", "simctl", "uninstall", udid, bundle])
    require(not set(targets) & installed_bundles(evidence, "apps-retire-after", udid),
            "INSTALL_RETIREMENT_NOT_OBSERVED")


def run():
    global EXECUTION_END
    monotonic_start = time.monotonic()
    # Diagnostic startup measurement only; retain the same separate 1280s retirement reserve.
    EXECUTION_END = monotonic_start + 1200
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
            all(re.fullmatch(r"[1-9][0-9]{0,19}", context[k]) for k in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")),
            "HOSTED_CONTEXT")
    source = GATE.source_state()
    GATE._intel_source(source)
    require(source["commit"] == context["GITHUB_SHA"], "SOURCE_SHA")
    require(GATE.ordinary_simulator_binding("ios-x64", "x64", source) is None, "ORDINARY_CONTEXT")
    token = uuid.uuid4().hex
    arm_tokens = {arm: uuid.uuid4().hex for arm in ARMS}
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
                                    "armTokens": arm_tokens, "sharedInputs": manifest, "qualification": False,
                                    "bootstatusMeasurement": dict(BOOTSTATUS_MEASUREMENT),
                                    "runtimeMeasurement": dict(RUNTIME_MEASUREMENT)})
    owner, results, errors = None, {}, []
    attempts = {"installed": False, "runnerAttempted": False}
    retired = False
    phase = "BUILD"
    started = datetime.now(timezone.utc).isoformat()

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt()

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        # SDK lookup and target compilation do not depend on an owned booted device.
        # Preserve their failures without first occupying a simulator; this is not a timeout extension.
        sdk = command(evidence, "sdk-path", ["/usr/bin/xcrun", "--sdk", "iphonesimulator", "--show-sdk-path"])
        sdk_path = sdk["stdout"].decode("utf-8").strip()
        require(sdk_path.startswith(context["DEVELOPER_DIR"] + "/Platforms/") and
                "\n" not in sdk_path and Path(sdk_path).is_dir(), "SDK_PATH")
        sdk_contract(sdk_path, evidence)
        binary = work / "P2pKitLanHostCLI"
        command(evidence, "compile-cli", ["/usr/bin/xcrun", "swiftc", "-sdk", sdk_path,
                "-target", "x86_64-apple-ios15.0-simulator", "-swift-version", "5", "-warnings-as-errors",
                "-j", "2",
                str(generated / "LanProbe.swift"), str(generated / "main.swift"), "-o", str(binary)])
        command(evidence, "cli-architecture", ["/usr/bin/lipo", str(binary), "-verify_arch", "x86_64"])
        cli_binary = read_file(binary, 64 * 1024 * 1024)
        cli_identity = {"bytes": len(cli_binary), "sha256": digest(cli_binary)}
        write(evidence / "cli-binary.json", cli_identity)
        phase = "PREPARE"
        owner = GATE.IntelSimulatorOwner(evidence, {**source, "token": token})
        with diagnostic_bootstatus_budget(owner):
            owner.prepare()
        udid = owner.selected["device"]["udid"]
        phase = "CLI"
        # Join the same compiled binary across the new preparation gap, immediately before spawn.
        cli_binary = read_file(binary, 64 * 1024 * 1024)
        require({"bytes": len(cli_binary), "sha256": digest(cli_binary)} == cli_identity, "CLI_BINARY_CHANGED")
        run_arms(evidence, binary, udid, arm_tokens, source, context, results)
    except KeyboardInterrupt:
        errors.append(phase + "_INTERRUPTED")
    except Exception:
        errors.append(phase + "_FAILED")
    finally:
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            EXECUTION_END = monotonic_start + 2480
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
            print("P2PKIT_LAN_DNS_SD_ENDPOINT_JOIN_COMPLETION_V1 " + encoded({"qualification": False,
                  "complete": set(results) == set(ARMS) and retired and not errors,
                  "simulatorRetired": retired, "errors": errors}).decode("ascii").strip(), flush=True)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    return 0 if set(results) == set(ARMS) and retired and not errors else 1


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception:
        print("P2PKIT_LAN_DNS_SD_ENDPOINT_JOIN_DIAGNOSTIC_FAILED", flush=True)
        sys.exit(1)
