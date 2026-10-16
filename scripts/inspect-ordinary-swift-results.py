#!/usr/bin/env python3
"""Closed ordinary Swift xcresult inspector; no build, simulator mutation or publication.

Only an existing canonical-domain native phase may call this helper. The parent
retains raw xcresults FIRST. All xcresulttool requests consume one original120s
and productive RAW window; a missing/failed/skipped case is never a pass.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import audit_processes as processes
import hosted_full_job_budget as budget
import hosted_full_supplements as full
import hosted_test_query as query


# An unreturned writer/ambiguous close is owned by the original enclosing
# native phase, not rescued with a second process scope, PID kill or wait.
QUARANTINE = []


def first_error(first, error, stage):
    """Keep the original failure; late ambiguity must not erase its cause."""
    if first is None:
        return error
    first.__notes__ = [*getattr(first, "__notes__", ()), "Swift " + stage + ": " + type(error).__name__]
    return first


def load_host():
    spec = importlib.util.spec_from_file_location("ordinary_swift_cases", SCRIPTS / "run-audit-host.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    path = Path(path)
    full.require(path.is_absolute() and path.resolve(strict=True) == path and path.is_file() and not path.is_symlink(),
                 "SWIFT_INSPECTION_PHYSICAL_FILE")
    before = path.stat()
    full.require(before.st_nlink == 1 and 0 <= before.st_size <= full.LIMIT, "SWIFT_INSPECTION_DOCUMENT_BOUND")
    stable = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_nlink,
                            value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    with path.open("rb") as stream:
        raw = stream.read(full.LIMIT + 1)
        full.require(stable(os.fstat(stream.fileno())) == stable(before), "SWIFT_INSPECTION_INPUT_CHANGED")
    full.require(len(raw) == before.st_size and stable(path.stat()) == stable(before), "SWIFT_INSPECTION_INPUT_CHANGED")
    return raw


def observe_owned(directory, command, name, *, remaining, raw_now, local_end, observations):
    """One fixed xcresulttool call, borrowing the parent's native domain.

    Existing POSIX suppliers bound both live streams. No Popen context-manager
    wait or independent signal/drain budget exists here. Missing return/close
    proof keeps original handles/partials and makes the helper UNKNOWN; only
    the enclosing native owner may retire remaining descendants.
    """
    record = {"file": name, "argv": command, "pid": None, "exitCode": None,
              "childReturned": False, "sinkRetirement": "UNKNOWN", "stderr": None,
              "startedRawNs": raw_now(), "finishedRawNs": None}
    observations.append(record)
    owner = child = out = err = None
    first, closed = None, False
    try:
        remaining()
        owner = query._PosixDirectory(directory)
        out = owner.create_file(name, max_bytes=full.LIMIT, deadline=local_end)
        err = owner.create_file(name + ".stderr", max_bytes=full.LIMIT, deadline=local_end)
        remaining()
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                 close_fds=True, env=dict(os.environ))
        record["pid"] = child.pid
        while True:
            remaining()
            out.verify()
            err.verify()
            code = child.poll()
            if code is not None:
                record["exitCode"], record["childReturned"] = code, True
            # Consume a real return before a late RAW/size failure; neither
            # observation grants success nor an unbounded cleanup allowance.
            remaining()
            out.verify()
            err.verify()
            if record["childReturned"]:
                break
            time.sleep(min(.05, remaining()))
    except BaseException as error:
        first = error
    finally:
        if record["childReturned"]:
            closed = True
            for sink in (out, err):
                try:
                    remaining()
                    sink.sync()
                    sink.verify()
                except BaseException as error:
                    first = first_error(first, error, "capture verification")
                try:
                    sink.close()
                    remaining()
                except BaseException as error:
                    closed = False
                    first = first_error(first, error, "capture close/return UNKNOWN")
            if owner is not None:
                try:
                    owner.close()
                    remaining()
                except BaseException as error:
                    closed = False
                    first = first_error(first, error, "capture directory close/return UNKNOWN")
        if not closed:
            QUARANTINE.append((owner, child, out, err))
        else:
            record["sinkRetirement"] = "KNOWN"
        try:
            remaining()
            record["finishedRawNs"] = raw_now()
            if closed:
                for suffix in ("", ".stderr"):
                    raw = read(directory / (name + suffix))
                    remaining()
                    value = {"file": name + suffix, "sha256": full.digest(raw), "bytes": len(raw)}
                    if suffix:
                        record["stderr"] = value
                    else:
                        record.update(sha256=value["sha256"], bytes=value["bytes"])
        except BaseException as error:
            first = first_error(first, error, "capture read/return UNKNOWN")
    if first is not None:
        raise first
    full.require(record["sinkRetirement"] == "KNOWN" and record["exitCode"] == 0 and
                 type(record["exitCode"]) is int, "SWIFT_XCRESULTTOOL_FAILED")
    return json.loads(read(directory / name)), record


def assess_return(directory, value, phase, *, context_sha, input_sha, canonical_id, raw_limit,
                  reader=read, check=lambda: None):
    """Independent original parent/seal resource proof; a native drain is not it."""
    check()
    # Command sinks are not the helper's entire I/O surface: case readers,
    # case-result and terminal writers also have fallible closes. A parseable
    # HOLD (or a PASS written before a failed close) cannot prove those resources
    # returned. Keep failed helpers private/UNKNOWN instead of inventing a new
    # file backend or a second cleanup allowance. Preserve the native phase as
    # observed; missing helper-custody proof is a separate fact.
    full.require(type(phase.get("exitCode")) is int and phase["exitCode"] == 0 and
                 phase.get("retirement") == "KNOWN" and phase.get("errors") == [],
                 "SWIFT_HELPER_SUCCESSFUL_PHASE_REQUIRED")
    full.require(value.get("schema") == 1 and value.get("scope") == "ORDINARY_SWIFT_CLOSED_CAPTURE_RETURN" and
                 value.get("contextSha256") == context_sha and value.get("inputSha256") == input_sha and
                 value.get("canonicalId") == canonical_id and value.get("helperDomain") == {
                    "id": phase["invocation"], "job": phase["job"], "state": phase["state"], "home": phase["home"]} and
                 value.get("retirement") == "KNOWN" and value.get("status") == "PASS",
                 "SWIFT_HELPER_RESOURCE_RETURN_REQUIRED")
    started, finished = value.get("startedRawNs"), value.get("finishedRawNs")
    full.require(type(started) is int and type(finished) is int and
                 phase["startedRawNs"] <= started <= finished <= phase["finalizedRawNs"] and
                 finished < min(started + 120 * budget.NS, raw_limit) and
                 type(value.get("commands")) is list and 0 < len(value["commands"]) <= 12,
                 "SWIFT_HELPER_RESOURCE_INTERVAL_CHANGED")
    files = set()
    for row in value["commands"]:
        check()
        name, argv = row.get("file"), row.get("argv")
        full.require(type(name) is str and re.fullmatch(r"actions-[0-3]\.json|tests-[0-3]-[0-7]\.json", name) and
                     name not in files and row.get("childReturned") is True and row.get("sinkRetirement") == "KNOWN" and
                     type(row.get("exitCode")) is int and type(row.get("pid")) is int and row["pid"] > 0 and
                     type(row.get("startedRawNs")) is int and type(row.get("finishedRawNs")) is int and
                     started <= row["startedRawNs"] <= row["finishedRawNs"] <= finished,
                     "SWIFT_HELPER_CAPTURE_RETURN_CHANGED")
        files.add(name)
        full.require(type(argv) is list and len(argv) in (9, 11) and argv[:8] == ["/usr/bin/xcrun", "xcresulttool", "get",
                     "object", "--legacy", "--format", "json", "--path"] and
                     Path(argv[8]).parent == directory.parent.parent / "work/swift-ui/DerivedData/Logs/Test" and
                     Path(argv[8]).suffix == ".xcresult" and
                     (len(argv) == 9 if name.startswith("actions-") else
                      len(argv) == 11 and argv[9] == "--id" and type(argv[10]) is str),
                     "SWIFT_HELPER_CAPTURE_SELECTOR_CHANGED")
        for metadata in (row, row.get("stderr")):
            full.require(type(metadata) is dict and metadata.get("file") == (name if metadata is row else name + ".stderr"),
                         "SWIFT_HELPER_BOTH_STREAMS_REQUIRED")
            raw = reader(directory / metadata["file"])
            full.require(len(raw) <= full.LIMIT and len(raw) == metadata.get("bytes") and
                         full.digest(raw) == metadata.get("sha256"), "SWIFT_HELPER_CAPTURE_BYTES_CHANGED")
        check()
    raw = reader(directory.parent / "swift-case-results.json")
    result = json.loads(raw)
    full.require(value.get("firstError") is None and full.digest(raw) == value.get("caseResultSha256") and
                 result.get("contextSha256") == context_sha and result.get("inputSha256") == input_sha and
                 result.get("canonicalId") == canonical_id and type(result.get("actions")) is list and
                 type(result.get("objects")) is list and all(row["exitCode"] == 0 for row in value["commands"]) and
                 {row["file"]: row for row in [*result["actions"], *result["objects"]]} ==
                 {row["file"]: row for row in value["commands"]} and
                 len(result["actions"]) + len(result["objects"]) == len(value["commands"]),
                 "SWIFT_CASES_LACK_ORIGINAL_CLOSED_CAPTURE")
    check()
    return {"status": value["status"], "retirement": "KNOWN", "commands": len(value["commands"])}


def assess_retained(directory, value, *, reader=read, check=lambda: None):
    objects = []
    full.require(type(value.get("objects")) is list and 0 < len(value["objects"]) <= 8, "SWIFT_ACTUAL_CASE_OBJECTS_REQUIRED")
    full.require(type(value.get("actions")) is list and 0 < len(value["actions"]) <= 4, "SWIFT_ACTUAL_ACTIONS_REQUIRED")
    expected, bundles = {}, []
    for index, row in enumerate(value["actions"]):
        check()
        name = "actions-" + str(index) + ".json"
        command = row.get("argv")
        full.require(row.get("file") == name and type(command) is list and len(command) == 9 and
                     command[:8] == ["/usr/bin/xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json", "--path"] and
                     row.get("exitCode") == 0 and type(row["exitCode"]) is int, "SWIFT_ACTION_COMMAND_CHANGED")
        bundle = Path(command[8])
        full.require(bundle.parent == directory.parent.parent / "work/swift-ui/DerivedData/Logs/Test" and
                     bundle.suffix == ".xcresult" and str(bundle) not in bundles, "SWIFT_ACTION_BUNDLE_CHANGED")
        bundles.append(str(bundle))
        raw = reader(directory / name)
        full.require(len(raw) == row.get("bytes") and full.digest(raw) == row.get("sha256"), "SWIFT_ACTION_BYTES_CHANGED")
        action = json.loads(raw)
        identifiers = {item["actionResult"]["testsRef"]["id"]["_value"]
                       for item in action.get("actions", {}).get("_values", []) if "testsRef" in item.get("actionResult", {})}
        full.require(identifiers and len(identifiers) <= 8 and all(type(item) is str and item and len(item) <= 512
                     and not any(ord(char) < 32 for char in item) for item in identifiers), "SWIFT_TESTSREF_REQUIRED")
        for ordinal, identifier in enumerate(sorted(identifiers)):
            expected[f"tests-{index}-{ordinal}.json"] = [*command, "--id", identifier]
    names = set()
    for row in value["objects"]:
        check()
        name = row.get("file")
        full.require(type(name) is str and re.fullmatch(r"tests-[0-3]-[0-7]\.json", name) and name not in names,
                     "SWIFT_CASE_OBJECT_ROSTER")
        names.add(name)
        full.require(row.get("argv") == expected.get(name) and row.get("exitCode") == 0 and
                     type(row["exitCode"]) is int, "SWIFT_CASE_COMMAND_CHANGED")
        raw = reader(directory / name)
        full.require(len(raw) == row.get("bytes") and full.digest(raw) == row.get("sha256"), "SWIFT_CASE_BYTES_CHANGED")
        objects.append(json.loads(raw))
    full.require(names == set(expected), "SWIFT_TESTSREF_OBJECTS_MISSING")
    result = load_host().assess_swift(objects)
    check()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    args = parser.parse_args()
    session = args.session
    full.require(session.is_absolute() and session.resolve(strict=True) == session, "SWIFT_SESSION")
    run_raw = read(session / "run-context.json")
    run = json.loads(run_raw)
    state = session / "state"
    context = json.loads(read(state / "context.json"))
    full.require(run.get("profile") == "full" and run["session"] == str(session) and
                 run["source"] == {key: context["source"][key] for key in ("commit", "tree")}, "SWIFT_CONTEXT")
    domains = processes.ownership_domains(os.environ.get(processes.CHAIN_ENV, ""), os.environ.get(processes.DOMAINS_ENV, ""))
    full.require(domains and domains[-1] == {"id": domains[-1]["id"], "job": context["id"], "state": str(state),
                                          "home": context["gradleHome"]} and
                 os.environ.get(processes.JOB_ENV) == context["id"] and os.environ.get(processes.STATE_ENV) == str(state) and
                 os.environ.get("GRADLE_USER_HOME") == context["gradleHome"], "SWIFT_HELPER_ACTUAL_DOMAIN")
    input_raw = read(session / "evidence/full-supplements/swift-inspection-input.json")
    inputs = json.loads(input_raw)
    intent = full.validate_intent(run["fullSupplementIntent"], state)
    canonical_id = next(row["id"] for row in intent if row["name"] == "swift-ui")
    full.require(full.digest(input_raw) == args.input_sha256 and inputs.get("contextSha256") == full.digest(run_raw) and
                 inputs.get("canonicalId") == canonical_id, "SWIFT_INSPECTOR_INPUT_CHANGED")
    budget_raw = read(session / "evidence/job-time/budget.json")
    full.require(full.digest(budget_raw) == run["jobBudgetSha256"], "SWIFT_JOB_BUDGET_CHANGED")
    # Reconstruct using the original serialized fixed-fence budget, not now+K.
    job = budget.Budget(budget_raw)
    raw_end = job.fence("productive")
    local_end = time.monotonic() + 120
    last = [budget.raw_now(job.value["responseFinishedRawNs"])]
    started_raw = last[0]
    def remaining():
        last[0] = budget.raw_now(last[0])
        seconds = min(90, local_end - time.monotonic(), (raw_end - last[0]) / budget.NS)
        full.require(seconds > 0, "SWIFT_INSPECTION_ORIGINAL_BUDGET_EXPIRED")
        return seconds
    directory = state / "evidence/swift-inspection"
    directory.mkdir(mode=0o700)
    objects, actions, observations = [], [], []
    def observe(command, name):
        return observe_owned(directory, command, name, remaining=remaining,
            raw_now=lambda: (remaining(), last[0])[1], local_end=local_end, observations=observations)
    first, result_raw = None, None
    try:
        full.require(type(inputs.get("bundles")) is list and 0 < len(inputs["bundles"]) <= 4 and
                     len(set(inputs["bundles"])) == len(inputs["bundles"]), "SWIFT_XCRESULT_ROSTER")
        for index, name in enumerate(inputs["bundles"]):
            path = Path(name)
            full.require(path.parent == state / "work/swift-ui/DerivedData/Logs/Test" and path.suffix == ".xcresult" and
                         path.is_dir() and path.resolve(strict=True) == path and not path.is_symlink(), "SWIFT_XCRESULT_PATH")
            command = ["/usr/bin/xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json", "--path", str(path)]
            action, original = observe(command, "actions-" + str(index) + ".json")
            actions.append(original)
            identifiers = {item["actionResult"]["testsRef"]["id"]["_value"]
                           for item in action.get("actions", {}).get("_values", []) if "testsRef" in item.get("actionResult", {})}
            full.require(identifiers and len(identifiers) <= 8 and all(type(value) is str and value and len(value) <= 512
                         and not any(ord(char) < 32 for char in value) for value in identifiers), "SWIFT_TESTSREF_REQUIRED")
            for ordinal, identifier in enumerate(sorted(identifiers)):
                full.require(len(objects) < 8, "SWIFT_TEST_OBJECT_LIMIT")
                _object, original = observe([*command, "--id", identifier], f"tests-{index}-{ordinal}.json")
                objects.append(original)
        result = {"schema": 1, "contextSha256": full.digest(run_raw), "inputSha256": full.digest(input_raw),
                  "canonicalId": canonical_id, "actions": actions, "objects": objects}
        result["cases"] = assess_retained(directory, result, check=remaining)
        remaining()
        result_raw = full.encoded(result)
        with (state / "evidence/swift-case-results.json").open("xb") as stream:
            stream.write(result_raw)
        remaining()
    except BaseException as error:
        first = error
    finally:
        # A parent native drain is not this helper's closed-sink proof. Even a
        # successful-looking case JSON has no authority without this original
        # final return, actual phase success and both streams' retained hashes.
        try:
            remaining()
            known = first is None and bool(observations) and not QUARANTINE and all(
                row["sinkRetirement"] == "KNOWN" and row["childReturned"] for row in observations)
            terminal = {"schema": 1, "scope": "ORDINARY_SWIFT_CLOSED_CAPTURE_RETURN",
                "contextSha256": full.digest(run_raw), "inputSha256": full.digest(input_raw), "canonicalId": canonical_id,
                "helperDomain": domains[-1], "startedRawNs": started_raw, "finishedRawNs": last[0],
                "commands": observations, "retirement": "KNOWN" if known else "UNKNOWN",
                "status": "PASS" if first is None and known else "HOLD", "firstError": None if first is None else type(first).__name__,
                "caseResultSha256": None if result_raw is None else full.digest(result_raw)}
            with (state / "evidence/swift-inspection-return.json").open("xb") as stream:
                stream.write(full.encoded(terminal))
            remaining()
        except BaseException as error:
            first = first_error(first, error, "terminal write/close/return UNKNOWN")
    if first is not None:
        raise first
    full.require(terminal["status"] == "PASS" and terminal["retirement"] == "KNOWN", "SWIFT_HELPER_RETURN_NOT_KNOWN")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("HOLD: ordinary Swift inspection: " + type(error).__name__, file=sys.stderr)
        for note in getattr(error, "__notes__", ()):
            print(note, file=sys.stderr)
        raise SystemExit(125)
