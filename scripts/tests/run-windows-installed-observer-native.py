#!/usr/bin/env python3
"""Fixed harmless Windows controls with original-handle death witnesses.

This is a test-only owner around the canonical PowerShell control wrapper. Its
60-second ceiling includes observer compilation/preparation; it NEVER extends
the observed subject's original QPC 30-second acceptance deadline. No installed
application, provider or caller-selected command is available here.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("installed_supervisor", SCRIPTS / "run-windows-installed-diagnostic.py")
H = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(H)
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import windows_process_witness as W

Witnesses = W.Witnesses
CASES = {
    "Normal": ("normal", 4),
    "Nonzero": ("nonzero", 3),
    "OutputOverflow": ("output-overflow", 3),
    "BlockedWorker": ("blocked-worker", 2),
    "BlockedOuter": ("blocked-outer", 3),
    "ObserverOutputOverflow": ("observer-output-overflow", 1),
}
LOG_LIMIT = 65536
RECORD_LIMIT = 65536
HARNESS_SECONDS = 60
SOURCE_FILES = (*H.SOURCE_FILES, "windows_process_witness.py", "windows_installed_observer.cs", "run-windows-installed-diagnostic.ps1",
                "tests/run-windows-installed-diagnostic-test.py", "tests/run-windows-installed-observer-control.ps1",
                "tests/run-windows-installed-observer-native.py")


class HarnessDeadline(H.Deadline):
    def __init__(self, counter):
        start, frequency = counter.now(), counter.frequency
        H.require(type(start) is int and 0 <= start < 2**63)
        H.require(type(frequency) is int and 0 < frequency <= 10**12)
        self.counter, self.start, self.frequency = counter, start, frequency
        self.end = start + HARNESS_SECONDS * frequency
        H.require(self.end < 2**63)
        self.check()


def sources():
    result = {}
    for name in SOURCE_FILES:
        raw = H.read_bounded(SCRIPTS / name, 2 * 1024 * 1024)
        result[name] = hashlib.sha256(raw).hexdigest()
    return result


def fixed_powershell():
    # Reuse the maintained native-x64/OS ProgramFiles resolver. This computes a
    # path only: it never reads or invokes the installed application.
    program_files = H.installed_launcher().parent.parent
    result = program_files / "PowerShell" / "7" / "pwsh.exe"
    H.require(result.is_file())
    return result


def integer(value):
    H.require(type(value) is int and value >= 0)
    return value


def validate_images(rows, case, python, wrapper_pid, wrapper_image):
    roots = [row for row in rows if row["pid"] == wrapper_pid]
    H.require(len(roots) == 1 and W.normalized_image(roots[0]["imagePath"]) == W.normalized_image(wrapper_image))
    expected_python = W.normalized_image(python)
    python_rows = [row for row in rows if row["pid"] != wrapper_pid and
                   W.normalized_image(row["imagePath"]) == expected_python]
    H.require(len(python_rows) >= CASES[case][1])
    return python_rows


def verify_e_overflow_evidence(subject, deadline):
    # Canonical E's command directory has its ordinary Windows mkdir ACL. This
    # fixed synthetic byte assertion does not claim F private-file custody for
    # that subtree. The caller has already observed every process's retirement.
    with subject.open_directory("run", deadline=deadline.monotonic_end(5)) as original_run:
        deadline.check(5)
        raw = H.read_bounded(original_run.path / "command" / "stdout.log", H.LOG_LIMIT)
        original_run.verify()
        deadline.check(5)
        H.require(raw == b"x" * H.LOG_LIMIT)
    deadline.check(5)  # Charge original reader and directory closure too.


def validate_control(args, wrapper, wrapper_exit, wrapper_exit_counter, witnesses, deadline, run, hashes):
    H.require(type(wrapper) is dict and set(wrapper) == {"schema", "scope", "case", "status", "capsule", "observation"})
    H.require(type(wrapper["schema"]) is int and wrapper["schema"] == 1)
    H.require(wrapper["scope"] == "HARMLESS_OBSERVER_CONTROL_NOT_INSTALLED" and wrapper["case"] == args.case)
    normal = args.case == "Normal"
    H.require(wrapper["status"] == ("PASS" if normal else "FAIL") and wrapper_exit == (0 if normal else 125))
    observed = wrapper["observation"]
    H.require(type(observed) is dict and observed["status"] == wrapper["status"])
    H.require(observed["schema"] == 1 and type(observed["schema"]) is int)
    H.require(observed["scope"] == "EXTERNAL_NATIVE_CONTROL_NOT_INSTALLED")
    H.require(observed["appSource"] == "0" * 40 and observed["control"] == CASES[args.case][0])
    H.require(observed["supervisorSource"] == {name: hashes[name] for name in
        (*H.SOURCE_FILES, "tests/run-windows-installed-diagnostic-test.py")})
    H.require(observed["observerSource"] == {name: hashes[name] for name in
        ("windows_installed_observer.cs", "run-windows-installed-diagnostic.ps1",
         "tests/run-windows-installed-observer-control.ps1")})
    start, frequency = integer(observed["startCounter"]), integer(observed["counterFrequency"])
    end = integer(observed["deadlineCounter"])
    H.require(frequency == deadline.frequency and deadline.start <= start < end == start + 30 * frequency)
    H.require(start <= integer(observed["completedCounter"]) < end)
    H.require(start <= wrapper_exit_counter < end)
    for field in ("processExitObserved", "originalProcessHandleClosed", "managedProcessClosed", "captureTasksRetired"):
        H.require(observed[field] is True)
    H.require(observed["finalizationCompleted"] is True)
    H.require(observed["phase"] == "RETURN_REQUIRES_OBSERVED_EXTERNAL_EXIT")
    rows = witnesses.evidence()
    H.require(witnesses.all_exited())
    python_rows = validate_images(rows, args.case, args.python, args.wrapper_pid, args.wrapper_image)
    roots = [row for row in rows if row["pid"] == args.wrapper_pid]
    H.require(len(roots) == 1 and roots[0]["exitCode"] == wrapper_exit)
    H.require(roots[0]["exitObservedCounter"] <= wrapper_exit_counter < end)
    # The first original is the suspended wrapper. Every subsequently witnessed
    # object must retire under the subject's original QPC end, before OUR cleanup.
    descendants = [row for row in rows if row["pid"] != args.wrapper_pid]
    H.require(all(deadline.start <= row["firstSeenCounter"] <= row["exitObservedCounter"] < end for row in descendants))
    H.require(all(start <= row["firstSeenCounter"] for row in python_rows))
    capsule = Path(wrapper["capsule"])
    H.require(capsule.is_absolute() and os.path.normcase(str(capsule.parent)) == os.path.normcase(str(run.path)))
    H.require(re.fullmatch(r"installed-[0-9a-f]{32}", capsule.name) is not None)
    raw_observer = None
    subject = run.open_directory(capsule.name, deadline=deadline.monotonic_end(5))
    try:
        raw_observer = H.decode(subject.read_bytes("observer.json", max_bytes=H.RECORD_LIMIT,
                                                deadline=deadline.monotonic_end(5)), H.RECORD_LIMIT)
        H.require(raw_observer["phase"] == "CANDIDATE_REQUIRES_OBSERVED_EXTERNAL_EXIT")
        H.require(raw_observer["finalizationCompleted"] is False)
        for field in ("schema", "scope", "status", "appSource", "control", "supervisorSource", "observerSource",
                      "startCounter", "counterFrequency", "deadlineCounter", "exitCode", "outputExceeded"):
            H.require(raw_observer[field] == observed[field])
        if args.case == "ObserverOutputOverflow":
            H.require(observed["outputExceeded"] is True and observed["capturesClosed"] is False)
            H.require(observed["terminationAttempted"] is True and observed["terminationReturned"] is True)
            H.require(observed["exitCode"] == 125)
            H.require(subject.read_bytes("observer-stdout.log", max_bytes=LOG_LIMIT,
                                         deadline=deadline.monotonic_end(5)) == b"x" * LOG_LIMIT)
        else:
            H.require(observed["outputExceeded"] is False and observed["capturesClosed"] is True)
            H.require(observed["terminationAttempted"] is False and observed["terminationReturned"] is False)
            if args.case == "BlockedOuter":
                H.require(observed["exitCode"] == 125)
                H.require(all(start + 29 * frequency <= row["exitObservedCounter"] < end for row in python_rows))
            else:
                H.require(observed["exitCode"] == (0 if normal else 1))
                inner = H.decode(subject.read_bytes("run/supervisor.json", max_bytes=H.RECORD_LIMIT,
                                                   deadline=deadline.monotonic_end(5)), H.RECORD_LIMIT)
                H.require(inner["status"] == ("PASS" if normal else "FAIL"))
                H.require(inner["outerCleanupKnown"] is True and inner["capturesClosed"] is True)
                if args.case in ("Nonzero", "OutputOverflow"):
                    worker = inner["workerOutcome"]
                    H.require(type(worker) is dict and worker["admissionMatched"] is False)
                    actual = worker["outcome"]
                    H.require(actual["cleanupKnown"] is True and actual["timedOut"] is False)
                    H.require(actual["cleanupReasons"] == [] and actual["nativeError"] is None and actual["pendingContext"] is None)
                    H.require(actual["code"] == ("COMMAND_FAILED" if args.case == "Nonzero" else "OUTPUT_LIMIT"))
                    if args.case == "Nonzero":
                        H.require(actual["exitCode"] == 7)
                    else:
                        H.require(actual["capturesClosed"] is False)
                        verify_e_overflow_evidence(subject, deadline)
    finally:
        subject.close()
    return observed, raw_observer


def failure_detail(stage, error):
    # Bounded private source locations diagnose a failed predicate without
    # publishing exception messages, paths or changing E's original outcome.
    frames, trace = [], error.__traceback__
    while trace is not None and len(frames) < 12:
        code = trace.tb_frame.f_code
        frames.append({"file": Path(code.co_filename).name[:96], "function": code.co_name[:96],
                       "line": trace.tb_lineno})
        trace = trace.tb_next
    return {"stage": stage, "type": type(error).__name__[:96], "frames": frames}


def main(argv=None):
    parser = H.Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("--case", choices=tuple(CASES), required=True)
    parser.add_argument("--private-parent", required=True)
    parser.add_argument("--python", required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    H.require(Path(args.private_parent).is_absolute() and Path(args.python).is_absolute())
    H.require(os.path.normcase(os.path.realpath(args.python)) == os.path.normcase(os.path.realpath(sys.executable)))
    deadline = HarnessDeadline(H.Counter())
    H.arm_watchdog(deadline)  # Fixed test ceiling, armed through final os._exit.
    A, E, F = H.modules()
    parent = run = scope = witnesses = receipt = None
    captures, original_pipes = [], []
    wrapper = observed = persisted = None
    failure, validated, cleanup, captures_closed = False, False, False, False
    wrapper_exit = wrapper_exit_counter = before_cleanup = None
    stage, failures = "PREPARATION", []
    def remember(where, error):
        if len(failures) < 8:
            failures.append(failure_detail(where, error))
    hashes = sources()
    try:
        stage = "PRIVATE_CUSTODY"
        parent = F.open_private_directory(args.private_parent)
        run = parent.create_directory("witness-" + uuid.uuid4().hex, deadline=deadline.monotonic_end(5))
        job, invocation = uuid.uuid4().hex, uuid.uuid4().hex
        home = str(run.path / "gradle-home")
        environment = A.ownership_environment(dict(os.environ), job, invocation, str(run.path), home, allow_new_context=True)
        scope = A.WindowsScope(job, invocation, str(run.path), home)
        witnesses = Witnesses(scope, deadline)
        command = [str(fixed_powershell()), "-NoLogo", "-NoProfile", "-NonInteractive", "-File",
                   str(SCRIPTS / "tests/run-windows-installed-observer-control.ps1"),
                   "-Case", args.case, "-PrivateParent", str(run.path), "-Python", args.python]
        args.wrapper_image = command[0]
        stage = "WRAPPER_START"
        child = scope.spawn(command, str(SCRIPTS), environment)
        args.wrapper_pid = child.pid
        original_pipes = [child.stdout, child.stderr]
        for pipe, label in zip(original_pipes, ("stdout", "stderr")):
            capture = E.Capture(pipe, run.path / ("wrapper-" + label + ".log"), LOG_LIMIT)
            captures.append(capture)
            capture.thread.start()
        stage = "ORIGINAL_PROCESS_OBSERVATION"
        while True:
            deadline.check(5)
            H.require(not any(capture.error for capture in captures))
            scope.discover()
            witnesses.poll()
            code = child.poll()
            if code is not None and wrapper_exit is None:
                wrapper_exit, wrapper_exit_counter = code, deadline.now()
            if wrapper_exit is not None and witnesses.all_exited() and all(H.capture_closed(item) for item in captures):
                break
            time.sleep(min(0.01, deadline.check(5)))
        H.require(not scope.discovery_errors)
        stage = "WRAPPER_RESULT"
        H.require(not H.read_bounded(run.path / "wrapper-stderr.log", LOG_LIMIT))
        wrapper = H.decode(H.read_bounded(run.path / "wrapper-stdout.log", LOG_LIMIT), LOG_LIMIT)
        stage = "EXPECTED_CONTROL_RESULT"
        observed, persisted = validate_control(args, wrapper, wrapper_exit, wrapper_exit_counter, witnesses, deadline, run, hashes)
        stage = "FINAL_SOURCE_BINDING"
        H.require(sources() == hashes)
        validated = True
    except BaseException as error:
        remember(stage, error)
        failure = True
    finally:
        # Freeze all qualifying death observations before the enclosing owner can
        # help terminate anything. A later cleanup cannot turn this result into PASS.
        if witnesses is not None:
            witnesses.freeze()
            before_cleanup = deadline.now()
        if scope is not None:
            for leader in scope.leaders:
                for pipe in (leader.stdout, leader.stderr):
                    if pipe is not None and all(pipe is not item for item in original_pipes):
                        original_pipes.append(pipe)
            try:
                live = scope.drain(grace=0.2, kill_wait=2, deadline=deadline.monotonic_end(2))
                cleanup = not live and not scope.discovery_errors
                for leader in scope.leaders:
                    leader.wait(timeout=deadline.check(2))
            except BaseException as error:
                remember("ENCLOSING_DRAIN", error)
                cleanup, failure = False, True
            try:
                scope.close()
            except BaseException as error:
                remember("ENCLOSING_SCOPE_CLOSE", error)
                cleanup, failure = False, True
        for capture in captures:
            try:
                capture.thread.join(timeout=deadline.check(1))
            except BaseException as error:
                remember("CAPTURE_JOIN", error)
                failure = True
        adopted = {id(capture.pipe) for capture in captures if capture.thread.ident is not None}
        for pipe in original_pipes:
            if id(pipe) not in adopted:
                try:
                    pipe.close()
                except BaseException as error:
                    remember("UNADOPTED_PIPE_CLOSE", error)
                    failure = True
        captures_closed = len(captures) == 2 and all(H.capture_closed(item) for item in captures)
        if witnesses is not None:
            try:
                witnesses.close()
            except BaseException as error:
                remember("WITNESS_CLOSE", error)
                failure = True
        passed = validated and not failure and cleanup and captures_closed
        version = sys.getwindowsversion()
        record = {"schema": 1, "scope": "ORIGINAL_HANDLE_SUPERVISOR_CONTROL_NOT_INSTALLED",
                  "status": "PASS" if passed else "FAIL", "case": args.case, "sourceFiles": hashes,
                  "harnessStartCounter": deadline.start, "counterFrequency": deadline.frequency,
                  "harnessDeadlineCounter": deadline.end, "harnessBudgetSeconds": HARNESS_SECONDS,
                  "beforeEnclosingCleanupCounter": before_cleanup, "completedCounter": deadline.now(),
                  "wrapperExitCode": wrapper_exit, "wrapperExitObservedCounter": wrapper_exit_counter,
                  "validatedBeforeEnclosingCleanup": validated, "enclosingCleanupKnown": cleanup,
                  "failureDetails": failures,
                  "capturesClosed": captures_closed, "witnesses": witnesses.evidence() if witnesses else [],
                  "wrapperResult": wrapper, "observerResult": observed, "persistedObserverCandidate": persisted,
                  "windows": {"major": version.major, "minor": version.minor, "build": version.build},
                  "pythonVersion": sys.version.split()[0]}
        try:
            H.require(run is not None)
            raw = E.encoded(record)
            H.require(len(raw) <= RECORD_LIMIT)
            receipt = run.create_file("witness.json", max_bytes=RECORD_LIMIT, deadline=deadline.monotonic_end())
            H.require(receipt.write(raw) == len(raw))
            deadline.check()
        finally:
            for owner in (receipt, run, parent):
                try:
                    if owner is not None:
                        owner.close()
                        deadline.check()
                except BaseException:
                    passed = False
    deadline.check()
    return 0 if passed else 1


if __name__ == "__main__":
    result = 1
    try:
        result = main()
    except BaseException:
        result = 1
    sys.stdout.write("WINDOWS_SUPERVISOR_NATIVE_CONTROL " + ("PASS" if result == 0 else "FAIL") + "\n")
    sys.stdout.flush()
    os._exit(result)
