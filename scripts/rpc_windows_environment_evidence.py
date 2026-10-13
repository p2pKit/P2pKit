#!/usr/bin/env python3
"""Pure RPC experiment readback checks; no network, execution, or release authorization.

The caller must first bind the receipt, artifacts and wrapper bytes to the exact Git
source/run. Contracts come from those verified wrapper bytes, NEVER from the receipt.
These checks do not qualify protected profiles, JNI, installed applications or a supervisor.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re


SNAPSHOT_SCOPE = "ONE_PARENT_ENUMERATION_NOT_STABILIZED_ABSENCE_OR_ACCEPTANCE"
HANDLE_SCOPE = "THREE_BROKER_VALUES_ONLY_NOT_EXHAUSTIVE"
CONTROL_SUFFIX = b" inert parent-namespace/notification ownership controls; NOT Windows runtime evidence"
HANDLE_KEYS = frozenset((
    "knownHandleAuditScope", "knownHandleAuditPassed", "knownHandleChecked", "knownHandleAbsent",
    "knownHandleReused", "knownHandleLeaked", "knownHandleError", "knownHandleHelperControlsPassed",
))


def require(condition, message):
    if not condition:
        raise ValueError(message)



def load_json(raw):
    """Reject ambiguous duplicate names and non-JSON numbers before comparing evidence."""
    def unique_pairs(pairs):
        result = {}
        for name, value in pairs:
            require(name not in result, "Duplicate JSON field")
            result[name] = value
        return result

    def non_json_number(_):
        raise ValueError("Non-JSON numeric value")

    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=non_json_number)


def require_same_json(actual, claimed):
    """Python equality alone wrongly accepts true==1 and false==0 in nested observations."""
    require(type(actual) is type(claimed), "Evidence JSON type mismatch")
    if type(actual) is dict:
        require(actual.keys() == claimed.keys(), "Evidence JSON fields differ")
        for key in actual:
            require_same_json(actual[key], claimed[key])
    elif type(actual) is list:
        require(len(actual) == len(claimed), "Evidence JSON list size differs")
        for value, other in zip(actual, claimed):
            require_same_json(value, other)
    else:
        require(actual == claimed, "Evidence JSON value differs")


def unsigned(value, maximum=0xffffffff):
    return type(value) is int and 0 <= value <= maximum


@dataclass(frozen=True)
class ProfileContract:
    observer_controls: int | None
    phases: bool
    snapshot: bool


def profile_contract(verified_wrapper: bytes) -> ProfileContract:
    """Inspect only the caller's already Git-bound producer, not candidate fields."""
    require(type(verified_wrapper) is bytes and len(verified_wrapper) <= 65536, "Invalid wrapper bytes")
    counts = re.findall(rb"PASS ([0-9]{1,3})" + re.escape(CONTROL_SUFFIX), verified_wrapper)
    require(len(counts) <= 1, "Ambiguous observer control count")
    count = int(counts[0]) if counts else None
    require(count in (None, 18, 32, 33), "Unreviewed observer control inventory")
    phases = verified_wrapper.count(b"$result.hiveObserverPhases =")
    snapshot = verified_wrapper.count(b"$result.hiveObserverSnapshot = $null")
    require(phases <= 1 and snapshot <= 1 and snapshot <= phases, "Ambiguous diagnostic contract")
    return ProfileContract(count, bool(phases), bool(snapshot))


def known_handles_required(verified_wrapper: bytes) -> bool:
    require(type(verified_wrapper) is bytes and len(verified_wrapper) <= 65536, "Invalid wrapper bytes")
    checks = verified_wrapper.count(b"$record.knownHandleAuditScope -cne '" + HANDLE_SCOPE.encode() + b"'")
    require(checks <= 1, "Ambiguous known-handle contract")
    require((b"knownHandleAuditScope" in verified_wrapper) == (checks == 1), "Partial known-handle contract")
    return checks == 1


def parse_hive_diagnostics(stderr: bytes):
    """Return bounded observations only. Snapshot state2 is NOT acceptance evidence."""
    require(type(stderr) is bytes and len(stderr) <= 256, "Unbounded diagnostic output")
    pattern = rb"(?:(?:P2PKIT_HIVE_PHASE [1-8]|P2PKIT_HIVE_SNAPSHOT [1-3] [0-9]{1,10})\r?\n){0,9}"
    require(re.fullmatch(pattern, stderr) is not None, "Unexpected diagnostic output")
    phases = [int(value) for value in re.findall(rb"P2PKIT_HIVE_PHASE ([1-8])", stderr)]
    require(len(set(phases)) == len(phases), "Repeated phase diagnostic")
    snapshots = re.findall(rb"P2PKIT_HIVE_SNAPSHOT ([1-3]) ([0-9]{1,10})", stderr)
    require(len(snapshots) <= 1, "Repeated snapshot diagnostic")
    snapshot = None
    if snapshots:
        state, status = map(int, snapshots[0])
        require(unsigned(status), "Snapshot status exceeds DWORD")
        require((state == 1 and status == 0) or (state == 2 and status == 259) or
                (state == 3 and status not in (0, 259)), "Inconsistent snapshot diagnostic")
        snapshot = {"state": state, "status": status, "scope": SNAPSHOT_SCOPE}
    return phases, snapshot


def validate_profile_diagnostics(receipt, stderr: bytes, contract: ProfileContract):
    phases, snapshot = parse_hive_diagnostics(stderr)
    if contract.phases:
        claimed = receipt.get("hiveObserverPhases")
        require(type(claimed) is list and all(type(value) is int for value in claimed), "Missing/invalid phases")
        require(claimed == phases, "Phase receipt differs from retained output")
    else:
        require(not stderr and "hiveObserverPhases" not in receipt, "Unexpected historical diagnostic")
    if contract.snapshot:
        require("hiveObserverSnapshot" in receipt, "Missing snapshot receipt field")
        claimed = receipt["hiveObserverSnapshot"]
        if claimed is not None:
            require(type(claimed) is dict and set(claimed) == {"state", "status", "scope"}, "Snapshot shape")
            require(unsigned(claimed["state"]) and unsigned(claimed["status"]), "Snapshot numeric types")
        require(claimed == snapshot, "Snapshot receipt differs from retained output")
    else:
        require(snapshot is None and "hiveObserverSnapshot" not in receipt, "Unexpected historical snapshot")
    if receipt.get("result") == "PASS":
        require(snapshot is None or snapshot["state"] != 3, "Failed snapshot cannot qualify a passing run")
    return {"phases": phases, "snapshot": snapshot}


def validate_observer_controls(stdout: bytes, stderr: bytes, contract: ProfileContract):
    require(contract.observer_controls is not None, "Unexpected observer control executable")
    expected = b"PASS " + str(contract.observer_controls).encode() + CONTROL_SUFFIX
    require(type(stdout) is bytes and stdout in (expected + b"\n", expected + b"\r\n"),
            "Control output does not match verified source inventory")
    require(stderr == b"", "Unexpected observer control stderr")



def validate_profile_completion(receipt, observation, contract: ProfileContract):
    """Enforce current-source mandatory controls/namespace evidence before accepting PASS.

    Failure packets can legitimately stop before compilation or observation. They remain failures,
    not missing-data substitutes for success. Pre-observer historical packets retain their old scope.
    """
    if receipt.get("result") != "PASS" or contract.observer_controls is None:
        return
    binary = receipt.get("controlExecutable")
    require(type(binary) is dict and set(binary) == {"sha256", "bytes"}, "Missing observer control image")
    require(type(binary["sha256"]) is str and re.fullmatch(r"[0-9a-fA-F]{64}", binary["sha256"]) is not None,
            "Invalid observer control digest")
    require(unsigned(binary["bytes"], 32 * 1024 * 1024) and binary["bytes"] > 0, "Invalid observer control size")
    execution = receipt.get("controlExecution")
    require(type(execution) is dict, "Missing observer control execution")
    for key, value in (("passed", True), ("processExitObserved", True), ("finalizationCompleted", True),
                       ("timedOut", False), ("outputExceeded", False)):
        require(execution.get(key) is value, "Observer control execution was not successful")
    require(type(execution.get("exitCode")) is int and execution["exitCode"] == 0, "Observer control exit")
    require(unsigned(execution.get("elapsedMs"), 9999), "Observer control deadline")
    require(type(observation) is dict, "Missing profile observation")
    for key in ("namespaceAbsenceObserved", "namespaceRetired"):
        require(observation.get(key) is True, "Missing/invalid namespace retirement")
    for key, value in (("namespaceOpenStatus", 0), ("namespaceEnumerationStatus", 259),
                       ("namespaceNotificationStatus", 0), ("namespaceCloseStatus", 0),
                       ("namespaceSystemError", 0), ("hiveQueryError", 0), ("hiveCloseError", 0)):
        require(type(observation.get(key)) is int and observation[key] == value, "Namespace status/type mismatch")
    require(unsigned(observation.get("namespaceScans"), 65536) and observation["namespaceScans"] > 0,
            "Missing/invalid namespace scan count")


def validate_known_handles(observation, required: bool, require_pass: bool):
    present = HANDLE_KEYS.intersection(observation)
    if not required:
        require(not present, "Unexpected historical known-handle observation")
        return None
    require(present == HANDLE_KEYS, "Incomplete known-handle observation")
    require(observation["knownHandleAuditScope"] == HANDLE_SCOPE, "Known-handle scope escalation")
    passed = observation["knownHandleAuditPassed"]
    require(type(passed) is bool, "Known-handle result type")
    for key in HANDLE_KEYS - {"knownHandleAuditScope", "knownHandleAuditPassed"}:
        require(unsigned(observation[key]), "Known-handle numeric type/range")
    checked = observation["knownHandleChecked"]
    absent = observation["knownHandleAbsent"]
    reused = observation["knownHandleReused"]
    leaked = observation["knownHandleLeaked"]
    error = observation["knownHandleError"]
    controls = observation["knownHandleHelperControlsPassed"]
    require(checked <= 3 and absent + reused + leaked == checked and controls <= 6,
            "Inconsistent known-handle accounting")
    if passed or require_pass:
        require(passed and checked == 3 and absent + reused == 3 and leaked == 0 and error == 0 and controls == 6,
                "Known-handle admission did not pass")
    return {key: observation[key] for key in sorted(HANDLE_KEYS)}
