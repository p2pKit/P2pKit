#!/usr/bin/env python3
"""One diagnostic-only Intel Simulator loopback TXT route; never native qualification."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import signal
import stat
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCOPE = "SIMULATOR_LOOPBACK_DNS_SD_ROUTE_PROBE_V1"
NATIVE_SCOPE = "SIMULATOR_LOOPBACK_DNS_SD_NATIVE_V1"
DEVELOPER = "/Applications/Xcode_26.3.app/Contents/Developer"
C_SOURCE = "scripts/native/ios_dns_sd_loopback_probe.c"
SUPPLIERS = {
    "scripts/run-platform-tests.py": "10e8f784289d98a1d06abbb8d71ad801811dc5c4fda6b22c01ca145d35043a0e",
    "scripts/hosted_full_simulator.py": "1995b258350d5d50b08db3698aac74eece4ea17d6f6aac3a2a1104ff892d42c1",
    "scripts/audit_processes.py": "7ef1beb8a79ce3c8e062100849babee6ffa0ce3421d0f0fc56706c3e0ef7ed13",
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def public_source(path, limit=2 * 1024 * 1024):
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            not before.st_mode & 0o022 and 0 < before.st_size <= limit, "PROBE_SOURCE_FILE")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    require(os.path.samestat(before, opened) and os.path.samestat(before, after) and
            os.path.samestat(before, current) and
            before.st_size == after.st_size == current.st_size == len(raw) and
            before.st_mtime_ns == after.st_mtime_ns == current.st_mtime_ns and
            before.st_ctime_ns == after.st_ctime_ns == current.st_ctime_ns, "PROBE_SOURCE_CHANGED")
    return raw


for _path, _sha in SUPPLIERS.items():
    require(hashlib.sha256(public_source(ROOT / _path)).hexdigest() == _sha, "PROBE_SUPPLIER_CHANGED")
_spec = importlib.util.spec_from_file_location("loopback_platform_supplier", ROOT / "scripts/run-platform-tests.py")
GATE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(GATE)
SIM = GATE.simulator
CUSTOM = ("probe-sdk-path", "probe-sdk-version", "probe-clang-path", "probe-spawn-help",
          "probe-compile", "probe-execute")
LABELS = (*GATE.INTEL_PREPARE, *CUSTOM, *GATE.INTEL_RETIRE)
BOOLS = ("interfaceValidated", "listenerStarted", "listenerPreserved", "registrationReady", "initialA",
         "updatedB", "publisherRefPreserved", "queryRefPreserved", "contextReleased")
CALLS = ("registerCalls", "queryCalls", "updateCalls")
CODES = ("registerCode", "queryCode", "updateCode", "registerQueueCode", "queryQueueCode",
         "registerCallbackCode", "queryCallbackCode")
COUNTS = ("registerCallbacks", "queryCallbacks", "removeCallbacks", "aCallbacks", "bCallbacks")
SCOPES = ("NONE", "ANY", "LOCAL_ONLY", "P2P", "UNICAST", "BLE", "INFRA", "CONCRETE")
# These are the only native outcomes; synchronize with the reviewed C producer.
REASONS = ("NONE", "ARGUMENT", "ALLOCATION", "CLOCK", "INTERFACE", "LISTENER", "LISTENER_CHANGED", "LISTENER_CLOSE",
           "REGISTER_API", "REGISTER_QUEUE", "REGISTER_CALLBACK", "REGISTER_IDENTITY", "REGISTER_TIMEOUT",
           "QUERY_API", "QUERY_QUEUE", "QUERY_CALLBACK", "QUERY_IDENTITY", "INITIAL_A_TIMEOUT",
           "UPDATE_API", "UPDATE_ORDER", "UPDATE_TIMEOUT", "CALLBACK_LIMIT_REACHED", "CLEANUP_TIMEOUT")


def identity(source, github):
    GATE._intel_source(source)
    require(type(github) is dict and set(github) == set(GATE.INTEL_GITHUB) and
            github["actions"] == "true" and github["repository"] == "p2pKit/P2pKit" and
            github["sha"] == source["commit"] and github["runAttempt"] == "1" and
            type(github["runId"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}", github["runId"]) and
            type(github["ref"]) is str and re.fullmatch(r"refs/heads/work/[A-Za-z0-9._/-]{1,160}", github["ref"]) and
            github["job"] == "loopback-route-probe", "PROBE_SOURCE_OR_GITHUB_IDENTITY")


def native_record(raw, source, github):
    require(type(raw) is bytes and 0 < len(raw) <= 8192 and raw.endswith(b"\n") and
            raw.count(b"\n") == 1 and all(value < 128 for value in raw), "PROBE_NATIVE_OUTPUT_BOUND")
    row = SIM.parse(raw)
    expected = {"schema", "scope", "source", "runId", "runAttempt", "target", "status", "reason",
                *BOOLS, *CALLS, *CODES, *COUNTS, "firstScope", "updateScope", "updateElapsedMs",
                "publisherCleanup", "queryCleanup"}
    require(type(row) is dict and set(row) == expected and type(row["schema"]) is int and row["schema"] == 1 and
            row["scope"] == NATIVE_SCOPE and row["source"] == source["commit"] and
            row["runId"] == github["runId"] and type(row["runAttempt"]) is int and row["runAttempt"] == 1 and
            row["target"] == "IOS_SIMULATOR_X86_64", "PROBE_NATIVE_IDENTITY")
    require(row["status"] in ("PASS", "FAIL") and row["reason"] in REASONS and
            (row["status"] == "PASS") == (row["reason"] == "NONE") and
            all(type(row[key]) is bool for key in BOOLS) and
            all(type(row[key]) is int and 0 <= row[key] <= 1 for key in CALLS) and
            all(row[key] is None or type(row[key]) is int and -(2**31) <= row[key] < 2**31 for key in CODES) and
            all(type(row[key]) is int and 0 <= row[key] <= 1024 for key in COUNTS) and
            all(row[key] in SCOPES for key in ("firstScope", "updateScope")) and
            (row["updateElapsedMs"] is None or type(row["updateElapsedMs"]) is int and
             0 <= row["updateElapsedMs"] <= 90000) and
            all(row[key] in ("NOT_STARTED", "COMPLETE", "TIMED_OUT")
                for key in ("publisherCleanup", "queryCleanup")), "PROBE_NATIVE_DOMAIN")
    if row["status"] == "PASS":
        require(all(row[key] for key in BOOLS) and all(row[key] == 1 for key in CALLS) and
                all(type(row[key]) is int and row[key] == 0 for key in CODES) and
                row["registerCallbacks"] >= 1 and row["queryCallbacks"] >= 2 and
                row["aCallbacks"] >= 1 and row["bCallbacks"] >= 1 and
                row["aCallbacks"] + row["bCallbacks"] + row["removeCallbacks"] <= row["queryCallbacks"] and
                row["firstScope"] != "NONE" and row["updateScope"] != "NONE" and
                type(row["updateElapsedMs"]) is int and row["updateElapsedMs"] < 30000 and
                row["publisherCleanup"] == row["queryCleanup"] == "COMPLETE", "PROBE_NATIVE_PASS_CONTRADICTION")
    return row


def text_observation(raw, pattern, reason):
    require(type(raw) is bytes and len(raw) <= 4096, reason)
    value = raw.decode("ascii").strip()
    require(re.fullmatch(pattern, value), reason)
    return value


def custom_commands(source, github, token, selected, originals, root):
    sdk = text_observation(originals["probe-sdk-path/stdout.bin"],
                           re.escape(DEVELOPER) + r"/Platforms/iPhoneSimulator\.platform/Developer/SDKs/"
                           r"iPhoneSimulator(?:[0-9]+(?:\.[0-9]+)*)?\.sdk", "PROBE_SELECTED_SDK")
    clang = text_observation(originals["probe-clang-path/stdout.bin"],
                            re.escape(DEVELOPER) + r"/Toolchains/XcodeDefault\.xctoolchain/usr/bin/clang",
                            "PROBE_SELECTED_CLANG")
    text_observation(originals["probe-sdk-version/stdout.bin"], r"26\.[0-9]+(?:\.[0-9]+)?", "PROBE_SDK_VERSION")
    help_text = originals["probe-spawn-help/stdout.bin"] + originals["probe-spawn-help/stderr.bin"]
    require(b"Usage: simctl spawn" in help_text, "PROBE_SPAWN_CAPABILITY")
    binary = root + "/build/reports/ios-dns-sd-loopback-probe/" + token + "/loopback-probe"
    return {
        "probe-sdk-path": ["/usr/bin/xcrun", "--sdk", "iphonesimulator", "--show-sdk-path"],
        "probe-sdk-version": ["/usr/bin/xcrun", "--sdk", "iphonesimulator", "--show-sdk-version"],
        "probe-clang-path": ["/usr/bin/xcrun", "--sdk", "iphonesimulator", "--find", "clang"],
        "probe-spawn-help": ["/usr/bin/xcrun", "simctl", "help", "spawn"],
        "probe-compile": [clang, "-std=c11", "-fblocks", "-target", "x86_64-apple-ios26.2-simulator",
                          "-isysroot", sdk, '-DP2PKIT_PROBE_SOURCE="' + source["commit"] + '"',
                          '-DP2PKIT_PROBE_RUN="' + github["runId"] + '"', "-DP2PKIT_PROBE_ATTEMPT=1",
                          root + "/" + C_SOURCE, "-o", binary],
        "probe-execute": ["/usr/bin/xcrun", "simctl", "spawn", selected["device"]["udid"], binary, token],
    }


def custom_phase(originals, label, argv, root, *, success=True):
    row = GATE._intel_json(originals[label + "/result.json"])
    require(set(row) == {"schema", "label", "argv", "cwd", "startedUtc", "finishedUtc", "exitCode",
                         "timedOut", "outputLimitExceeded", "ownedGroupDrained", "stdoutBytes", "stdoutSha256",
                         "stderrBytes", "stderrSha256"} and type(row["schema"]) is int and row["schema"] == 1 and
            row["label"] == label and row["argv"] == argv and row["cwd"] == root, "PROBE_PHASE_COMMAND")
    require(type(row["exitCode"]) is int and (not success or row["exitCode"] == 0) and
            row["timedOut"] is False and row["outputLimitExceeded"] is False and row["ownedGroupDrained"] is True,
            "PROBE_PHASE_FAILED")
    start, end = GATE._intel_time(row["startedUtc"]), GATE._intel_time(row["finishedUtc"])
    require(0 <= (end - start).total_seconds() <= 140, "PROBE_PHASE_DEADLINE")
    for stream in ("stdout", "stderr"):
        raw = originals[label + "/" + stream + ".bin"]
        require(type(row[stream + "Bytes"]) is int and row[stream + "Bytes"] == len(raw) and
                row[stream + "Sha256"] == SIM.digest(raw), "PROBE_PHASE_STREAM")
    return row


def admit_evidence(receipt, originals):
    """Pure admission of the new diagnostic, not an ordinary/native gate adapter."""
    require(type(receipt) is dict and set(receipt) == {"schema", "scope", "role", "root", "token", "source",
            "sourceAfter", "github", "developerDir", "selected", "binary", "cSourceSha256", "originals",
            "retirement"} and type(receipt["schema"]) is int and receipt["schema"] == 1 and
            receipt["scope"] == SCOPE and receipt["role"] == "macos-x64" and
            receipt["developerDir"] == DEVELOPER, "PROBE_RECEIPT_SCOPE")
    source, github, selected = receipt["source"], receipt["github"], receipt["selected"]
    identity(source, github)
    require(receipt["sourceAfter"] == source and type(receipt["token"]) is str and
            re.fullmatch(r"[0-9a-f]{32}", receipt["token"]), "PROBE_SOURCE_CHANGED")
    root = receipt["root"]
    require(type(root) is str and root.startswith("/") and "\0" not in root and ".." not in root.split("/"),
            "PROBE_ROOT")
    GATE._intel_originals(receipt["originals"], originals, LABELS)
    require(type(selected) is dict and set(selected) == {"runtime", "device"}, "PROBE_SELECTION")
    for label in GATE.INTEL_PREPARE[:4]:
        SIM.original(label, "macos-x64", originals[label + "/stdout.bin"])
    require(selected == {"runtime": SIM.original("simulator-runtimes", "macos-x64",
                            originals["simulator-runtimes/stdout.bin"]),
                         "device": SIM.original("simulator-devices", "macos-x64",
                            originals["simulator-devices/stdout.bin"])}, "PROBE_ORIGINAL_SELECTION")
    require(b"Usage: simctl bootstatus <device>" in originals["intel-bootstatus-help/stdout.bin"] +
            originals["intel-bootstatus-help/stderr.bin"], "PROBE_BOOTSTATUS_CAPABILITY")
    require(SIM.terminal_device(originals["intel-prelaunch/stdout.bin"], selected)["state"] == "Booted",
            "PROBE_PRELAUNCH")
    commands = custom_commands(source, github, receipt["token"], selected, originals, root)
    previous = None
    for label in LABELS:
        row = (custom_phase(originals, label, commands[label], root) if label in CUSTOM else
               GATE._intel_phase(originals, label, root, selected))
        start, end = GATE._intel_time(row["startedUtc"]), GATE._intel_time(row["finishedUtc"])
        require(previous is None or previous <= start, "PROBE_PHASE_ORDER")
        previous = end
    binary = receipt["binary"]
    require(type(binary) is dict and set(binary) == {"path", "bytes", "sha256"} and
            binary["path"] == commands["probe-execute"][-2] and type(binary["bytes"]) is int and
            0 < binary["bytes"] <= 4 * 1024 * 1024 and re.fullmatch(r"[0-9a-f]{64}", binary["sha256"]) and
            type(receipt["cSourceSha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", receipt["cSourceSha256"]),
            "PROBE_COMPILED_BINARY")
    verify_retirement(receipt, originals)
    native = native_record(originals["probe-execute/stdout.bin"], source, github)
    require(native["status"] == "PASS", "PROBE_NATIVE_ROUTE_NOT_DEMONSTRATED")
    return {"schema": 1, "scope": SCOPE, "source": source["commit"], "runId": github["runId"],
            "runAttempt": 1, "routeDemonstrated": True, "selectedSimulatorRetired": True,
            "nativeQualification": False, "physicalNetworkCoverage": False, "native": native}


def verify_retirement(receipt, originals):
    """The selected before/shutdown/after subset can be verified even if the probe fails."""
    source, selected, root = receipt["source"], receipt["selected"], receipt["root"]
    GATE._intel_source(source)
    require(receipt["sourceAfter"] == source, "PROBE_RETIREMENT_SOURCE")
    retired = GATE._intel_json(receipt["retirement"])
    require(set(retired) == {"schema", "scope", "root", "token", "source", "selected", "bindingSha256",
                            "shutdownIssued", "originals", "deviceAfter", "errors"} and
            type(retired["schema"]) is int and retired["schema"] == 1 and
            retired["scope"] == GATE.INTEL_RETIREMENT_SCOPE and retired["root"] == root and
            retired["token"] == receipt["token"] and retired["source"] == source and
            retired["selected"] == selected and retired["bindingSha256"] is None and
            retired["shutdownIssued"] is True and retired["errors"] == [], "PROBE_RETIREMENT")
    retired_originals = {key: value for key, value in originals.items() if key in GATE._intel_paths(GATE.INTEL_RETIRE)}
    GATE._intel_originals(retired["originals"], retired_originals, GATE.INTEL_RETIRE)
    previous = None
    for label in GATE.INTEL_RETIRE:
        row = GATE._intel_phase(originals, label, root, selected)
        start, end = GATE._intel_time(row["startedUtc"]), GATE._intel_time(row["finishedUtc"])
        require(previous is None or previous <= start, "PROBE_RETIREMENT_ORDER")
        previous = end
    before = SIM.terminal_device(originals["intel-retire-before/stdout.bin"], selected)
    after = SIM.terminal_device(originals["intel-retire-after/stdout.bin"], selected)
    require(before["state"] == "Booted" and after["state"] == "Shutdown" and retired["deviceAfter"] == after,
            "PROBE_SELECTED_RETIREMENT")
    return True


def load_phase(owner, label):
    for leaf in GATE.INTEL_LEAVES:
        path = owner.directory / label / leaf
        if path.exists():
            owner.originals[label + "/" + leaf] = GATE.simulator_original(path, allow_empty=leaf != "result.json")


def capture(owner, label, argv, *, success=True):
    try:
        GATE._intel_capture_phase(owner.directory, label, argv)
    finally:
        load_phase(owner, label)
    return custom_phase(owner.originals, label, argv, str(ROOT), success=success)


def prepare(owner):
    values = {}
    for label in GATE.INTEL_PREPARE[:4]:
        values[label] = SIM.original(label, "macos-x64", owner.phase(label))
    owner.phase("intel-bootstatus-help")
    require(b"Usage: simctl bootstatus <device>" in owner.originals["intel-bootstatus-help/stdout.bin"] +
            owner.originals["intel-bootstatus-help/stderr.bin"], "PROBE_BOOTSTATUS_CAPABILITY")
    device = SIM.original("simulator-devices", "macos-x64", owner.phase("simulator-devices"))
    owner.selected = {"runtime": values["simulator-runtimes"], "device": device}
    owner.phase("intel-boot")
    owner.phase("intel-bootstatus")
    require(SIM.terminal_device(owner.phase("intel-prelaunch"), owner.selected)["state"] == "Booted",
            "PROBE_PRELAUNCH")


def run():
    require(len(sys.argv) == 1 and platform.system() == "Darwin" and platform.machine() == "x86_64",
            "PROBE_INTEL_MAC_REQUIRED")
    require(os.environ.get("DEVELOPER_DIR") == DEVELOPER, "PROBE_DEVELOPER_DIR")
    os.umask(0o077)
    source = GATE.source_state()
    github = {key: os.environ.get(name) for key, name in GATE.INTEL_GITHUB.items()}
    identity(source, github)
    token = uuid.uuid4().hex
    directory = ROOT / "build/reports/ios-dns-sd-loopback-probe" / token
    directory.mkdir(parents=True, mode=0o700)
    owner = GATE.IntelSimulatorOwner(directory, {**source, "token": token})
    GATE._intel_write(directory / "source.json", SIM.encoded({"scope": SCOPE, "source": source, "github": github}))
    c_hash = SIM.digest(public_source(ROOT / C_SOURCE))
    binary, native, errors, retired_errors = None, None, [], []
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt()
    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        prepare(owner)
        tools = {
            "probe-sdk-path": ["/usr/bin/xcrun", "--sdk", "iphonesimulator", "--show-sdk-path"],
            "probe-sdk-version": ["/usr/bin/xcrun", "--sdk", "iphonesimulator", "--show-sdk-version"],
            "probe-clang-path": ["/usr/bin/xcrun", "--sdk", "iphonesimulator", "--find", "clang"],
            "probe-spawn-help": ["/usr/bin/xcrun", "simctl", "help", "spawn"],
        }
        for label, argv in tools.items():
            capture(owner, label, argv)
        commands = custom_commands(source, github, token, owner.selected, owner.originals, str(ROOT))
        capture(owner, "probe-compile", commands["probe-compile"])
        binary_path = Path(commands["probe-execute"][-2])
        binary_raw = public_source(binary_path, 4 * 1024 * 1024)
        binary = {"path": str(binary_path), "bytes": len(binary_raw), "sha256": SIM.digest(binary_raw)}
        require(SIM.digest(public_source(ROOT / C_SOURCE)) == c_hash, "PROBE_C_SOURCE_CHANGED")
        row = capture(owner, "probe-execute", commands["probe-execute"], success=False)
        native = native_record(owner.originals["probe-execute/stdout.bin"], source, github)
        require(row["exitCode"] == 0 and native["status"] == "PASS", "PROBE_NATIVE_ROUTE_NOT_DEMONSTRATED")
        require(SIM.digest(public_source(binary_path, 4 * 1024 * 1024)) == binary["sha256"], "PROBE_BINARY_CHANGED")
    except KeyboardInterrupt:
        errors.append("PROBE_INTERRUPTED")
    except (OSError, ValueError, TypeError, KeyError, RecursionError, UnicodeError) as error:
        reason = str(error)
        errors.append(reason if re.fullmatch(r"(?:PROBE|INTEL|SIMULATOR)_[A-Z_]{1,90}", reason) else "PROBE_CONTROLLER_ERROR")
    finally:
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            retired_errors = owner.retire()
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            retired_errors = ["PROBE_RETIREMENT_ERROR"]
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    try:
        source_after = GATE.source_state()
    except (OSError, ValueError):
        source_after = None
        errors.append("PROBE_SOURCE_AFTER_UNAVAILABLE")
    receipt = {"schema": 1, "scope": SCOPE, "role": "macos-x64", "root": str(ROOT), "token": token,
               "source": source, "sourceAfter": source_after, "github": github, "developerDir": DEVELOPER,
               "selected": owner.selected, "binary": binary, "cSourceSha256": c_hash,
               "originals": GATE._intel_references(owner.originals), "retirement": owner.retirement_raw}
    projection = {"schema": 1, "scope": SCOPE, "source": source["commit"], "runId": github["runId"],
                  "runAttempt": 1, "routeDemonstrated": False, "selectedSimulatorRetired": False,
                  "nativeQualification": False, "physicalNetworkCoverage": False, "native": native}
    try:
        projection["selectedSimulatorRetired"] = verify_retirement(receipt, owner.originals)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        errors.append("PROBE_SELECTED_RETIREMENT_UNVERIFIED")
    try:
        require(not errors and not retired_errors, "PROBE_EXECUTION_INCOMPLETE")
        require(os.environ.get("DEVELOPER_DIR") == DEVELOPER and
                {key: os.environ.get(name) for key, name in GATE.INTEL_GITHUB.items()} == github, "PROBE_CONTEXT_CHANGED")
        for name, raw in owner.originals.items():
            require(GATE.simulator_original(owner.directory / name, allow_empty=not name.endswith("result.json")) == raw,
                    "PROBE_ORIGINAL_CHANGED")
        projection = admit_evidence(receipt, owner.originals)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        reason = str(error)
        errors.append(reason if re.fullmatch(r"(?:PROBE|INTEL|SIMULATOR)_[A-Z_]{1,90}", reason) else "PROBE_ADMISSION_ERROR")
    # The maintained raw retirement receipt is only a supporting observation;
    # no ordinary binding, invocation, task count, XML or owner38 claim is created.
    serializable = {**receipt, "retirement": None if owner.retirement_raw is None else SIM.parse(owner.retirement_raw),
                    "errors": errors, "retirementErrors": retired_errors}
    GATE._intel_write(directory / "ownership.json", SIM.encoded(serializable))
    projection["errors"] = errors
    projection["retirementErrors"] = retired_errors
    GATE._intel_write(directory / "projection.json", SIM.encoded(projection))
    print(json.dumps(projection, sort_keys=True, separators=(",", ":")))
    return 0 if projection["routeDemonstrated"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({"scope": SCOPE, "routeDemonstrated": False, "nativeQualification": False,
                          "error": "PROBE_CONTROLLER_REJECTED"}, sort_keys=True))
        raise SystemExit(1)
