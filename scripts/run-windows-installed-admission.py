#!/usr/bin/env python3
"""Explicit installed admission with original-handle exit evidence.

Caller independently admits account, installation, startup and source. This
entry has no fixture, launcher, timeout or provider override. Its preparation
ceiling never extends the inner original 30-second application deadline.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys
import time
import uuid

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("installed_supervisor", SCRIPTS / "run-windows-installed-diagnostic.py")
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)
LOG_LIMIT = RECORD_LIMIT = 65536
PREPARATION_SECONDS = 60
SOURCE_FILES = (*H.SOURCE_FILES, "windows_installed_observer.cs", "run-windows-installed-diagnostic.ps1",
                "windows_process_witness.py", "run-windows-installed-admission.py")


class PreparationDeadline(H.Deadline):
    def __init__(self, counter):
        self.counter, self.start, self.frequency = counter, counter.now(), counter.frequency
        H.require(type(self.start) is int and 0 <= self.start < 2**63)
        H.require(type(self.frequency) is int and 0 < self.frequency <= 10**12)
        self.end = self.start + PREPARATION_SECONDS * self.frequency
        H.require(self.end < 2**63)
        self.check()


def source_identity():
    return {name: hashlib.sha256(H.read_bounded(SCRIPTS / name, 2 * 1024 * 1024)).hexdigest()
            for name in SOURCE_FILES}


def same_path(left, right):
    # Evidence comparison only, never a substitute for original-handle admission.
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def integer(value):
    H.require(type(value) is int and value >= 0)
    return value


def failure_detail(stage, error):
    frames, current = [], error.__traceback__
    while current is not None and len(frames) < 12:
        frames.append({"file": Path(current.tb_frame.f_code.co_filename).name[:120], "line": current.tb_lineno})
        current = current.tb_next
    return {"stage": stage, "type": type(error).__name__[:100], "frames": frames}


def validate_observer(observed, args, hashes, deadline, witnesses, wrapper_id, exit_counter, powershell, launcher):
    H.require(type(observed) is dict and type(observed["schema"]) is int and observed["schema"] == 1)
    H.require(observed["scope"] == "EXTERNAL_PROCESS_EXIT_OBSERVER_NOT_PROFILE_QUALIFICATION")
    H.require(observed["status"] == "PASS" and observed["appSource"] == args.expected_source)
    H.require(observed["operation"] == args.operation)
    H.require(observed["control"] is None and observed["stage"] == "RECEIPT")
    H.require(observed["phase"] == "CANDIDATE_REQUIRES_OBSERVED_EXTERNAL_EXIT")
    H.require(observed["finalizationCompleted"] is False)
    H.require(observed["supervisorSource"] == {name: hashes[name] for name in H.SOURCE_FILES})
    H.require(observed["observerSource"] == {name: hashes[name] for name in
        ("windows_installed_observer.cs", "run-windows-installed-diagnostic.ps1")})
    start, frequency = integer(observed["startCounter"]), integer(observed["counterFrequency"])
    end = integer(observed["deadlineCounter"])
    H.require(frequency == deadline.frequency and deadline.start <= start < end == start + 30 * frequency)
    H.require(start <= integer(observed["completedCounter"]) <= exit_counter < end)
    H.require(integer(observed["budgetMilliseconds"]) == 30000 and integer(observed["exitCode"]) == 0)
    for field in ("processExitObserved", "originalProcessHandleClosed", "managedProcessClosed",
                  "capturesClosed", "captureTasksRetired"):
        H.require(observed[field] is True)
    for field in ("outputExceeded", "terminationAttempted", "terminationReturned"):
        H.require(observed[field] is False)
    rows = witnesses.evidence()
    wrapper = [row for row in rows if (row["pid"], row["creationFileTime"]) == wrapper_id]
    H.require(len(wrapper) == 1 and same_path(wrapper[0]["imagePath"], powershell))
    H.require(wrapper[0]["exitCode"] == 0 and wrapper[0]["exitObservedCounter"] <= exit_counter)
    H.require(witnesses.all_exited())
    descendants = [row for row in rows if (row["pid"], row["creationFileTime"]) != wrapper_id]
    H.require(all(start <= row["firstSeenCounter"] <= row["exitObservedCounter"] < end for row in descendants))
    H.require(sum(same_path(row["imagePath"], args.python) for row in descendants) >= 2)
    H.require(sum(same_path(row["imagePath"], launcher) for row in descendants) >= 1)
    return end


def arguments(argv):
    parser = H.Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--operation", choices=tuple(H.ALL_OPERATIONS), default="admission")
    parser.add_argument("--private-parent", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--native-directory")
    parser.add_argument("--native-sha256")
    args = parser.parse_args(argv)
    H.require(re.fullmatch(r"[0-9a-f]{40}", args.expected_source) is not None)
    H.require(Path(args.private_parent).is_absolute() and Path(args.python).is_absolute())
    H.require(same_path(os.path.realpath(args.python), os.path.realpath(sys.executable)))
    H.N.validate_arguments(args)
    return args


def run(argv=None):
    args = arguments(sys.argv[1:] if argv is None else argv)
    deadline = PreparationDeadline(H.Counter())
    H.arm_watchdog(deadline)
    A, E, F = H.modules()
    from windows_process_witness import Witnesses

    parent = run_directory = scope = witnesses = subject = receipt = None
    original_pipes, captures, failures = [], [], []
    observed = inner = None
    accepted = cleanup = captures_closed = False
    wrapper_exit = wrapper_exit_counter = before_cleanup = wrapper_id = subject_end = None
    stage = "PREPARATION"
    hashes = source_identity()
    installed = H.installed_launcher()
    launcher = H.N.executable(args) if args.operation in H.N.OPERATIONS else installed
    powershell = installed.parent.parent / "PowerShell" / "7" / "pwsh.exe"
    H.require(powershell.is_file())
    try:
        stage = "PRIVATE_CUSTODY"
        parent = F.open_private_directory(args.private_parent)
        run_directory = parent.create_directory("admission-" + uuid.uuid4().hex, deadline=deadline.monotonic_end(5))
        job, invocation = uuid.uuid4().hex, uuid.uuid4().hex
        home = str(run_directory.path / "gradle-home")
        environment = A.ownership_environment(dict(os.environ), job, invocation, str(run_directory.path),
                                            home, allow_new_context=True)
        scope = A.WindowsScope(job, invocation, str(run_directory.path), home)
        witnesses = Witnesses(scope, deadline)
        command = [str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-File",
                   str(SCRIPTS / "run-windows-installed-diagnostic.ps1"), "-ExpectedSource", args.expected_source,
                   "-Operation", args.operation,
                   "-PrivateParent", str(run_directory.path), "-Python", args.python]
        if args.operation in H.N.OPERATIONS:
            command += ["-NativeDirectory", args.native_directory, "-NativeSha256", args.native_sha256]
        stage = "WRAPPER_START"
        child = scope.spawn(command, str(SCRIPTS), environment)
        identity = scope.api.identity(child.handle, child.pid)
        wrapper_id = (identity["pid"], identity["creationFileTime"])
        original_pipes = [child.stdout, child.stderr]
        for pipe, label in zip(original_pipes, ("stdout", "stderr")):
            capture = E.Capture(pipe, run_directory.path / ("wrapper-" + label + ".log"), LOG_LIMIT)
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
        stage = "OBSERVER_RECORD"
        run_directory.verify()
        locators = [name for name in run_directory.names(max_names=16, deadline=deadline.monotonic_end(5))
                    if re.fullmatch(r"installed-[0-9a-f]{32}", name)]
        H.require(len(locators) == 1)
        # Enumeration supplies a locator only; read through the original parent.
        subject = run_directory.open_directory(locators[0], deadline=deadline.monotonic_end(5))
        observed = H.decode(subject.read_bytes("observer.json", max_bytes=H.RECORD_LIMIT,
                                             deadline=deadline.monotonic_end(5)), H.RECORD_LIMIT)
        # Preserve inner failure as evidence before applying success predicates.
        inner = H.decode(subject.read_bytes("run/supervisor.json", max_bytes=H.RECORD_LIMIT,
                                          deadline=deadline.monotonic_end(5)), H.RECORD_LIMIT)
        stage = "TIMELY_INSTALLED_ADMISSION"
        H.require(wrapper_exit == 0)
        H.require(not H.read_bounded(run_directory.path / "wrapper-stderr.log", LOG_LIMIT))
        H.require(H.read_bounded(run_directory.path / "wrapper-stdout.log", LOG_LIMIT) in
                  (b"WINDOWS_INSTALLED_DIAGNOSTIC_OBSERVER PASS\n", b"WINDOWS_INSTALLED_DIAGNOSTIC_OBSERVER PASS\r\n"))
        subject_end = validate_observer(observed, args, hashes, deadline, witnesses, wrapper_id,
                                        wrapper_exit_counter, powershell, launcher)
        H.require(inner["status"] == "PASS" and inner["appSource"] == args.expected_source)
        H.require(inner["operation"] == args.operation)
        expected_scope = H.N.SCOPE if args.operation in H.N.OPERATIONS else H.SCOPE
        H.require(inner["scope"] == expected_scope and inner["supervisorSource"] == {name: hashes[name] for name in H.SOURCE_FILES})
        H.require(inner["outerCleanupKnown"] is True and inner["capturesClosed"] is True)
        H.require(H.validate_worker(inner["workerOutcome"], args.expected_source, args.operation))
        stage = "FINAL_SOURCE_BINDING"
        H.require(source_identity() == hashes)
        accepted = True
    except BaseException as error:
        failures.append(failure_detail(stage, error))
    finally:
        if witnesses is not None:
            witnesses.freeze()
            before_cleanup = deadline.now()
        if subject is not None:
            try:
                subject.close()
            except BaseException as error:
                failures.append(failure_detail("SUBJECT_CLOSE", error))
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
                cleanup = False
                failures.append(failure_detail("ENCLOSING_DRAIN", error))
            try:
                scope.close()
            except BaseException as error:
                cleanup = False
                failures.append(failure_detail("ENCLOSING_SCOPE_CLOSE", error))
        for capture in captures:
            try:
                capture.thread.join(timeout=deadline.check(1))
            except BaseException as error:
                failures.append(failure_detail("CAPTURE_JOIN", error))
        adopted = {id(capture.pipe) for capture in captures if capture.thread.ident is not None}
        for pipe in original_pipes:
            if id(pipe) not in adopted:
                try:
                    pipe.close()
                except BaseException as error:
                    failures.append(failure_detail("UNADOPTED_PIPE_CLOSE", error))
        captures_closed = len(captures) == 2 and all(H.capture_closed(item) for item in captures)
        if witnesses is not None:
            try:
                witnesses.close()
            except BaseException as error:
                failures.append(failure_detail("WITNESS_CLOSE", error))
        passed = (accepted and not failures and cleanup and captures_closed and
                  subject_end is not None and deadline.now() < subject_end)
        record = {"schema": 1, "scope": ("NATIVE_SMOKE_FIXED_OPERATION_NOT_JNI_OR_HOST_CLIENT_QUALIFICATION"
                    if args.operation in H.N.OPERATIONS else "INSTALLED_FIXED_OPERATION_NOT_HOST_CLIENT_QUALIFICATION"),
                  "status": "PASS" if passed else "FAIL", "appSource": args.expected_source, "sourceFiles": hashes,
                  "operation": args.operation,
                  "nativePayloadSha256": getattr(args, "native_sha256", None),
                  "phase": "CANDIDATE_REQUIRES_OBSERVED_DRIVER_EXIT", "finalizationCompleted": False,
                  "preparationStartCounter": deadline.start, "counterFrequency": deadline.frequency,
                  "preparationDeadlineCounter": deadline.end, "subjectDeadlineCounter": subject_end,
                  "wrapperExitCode": wrapper_exit, "wrapperExitObservedCounter": wrapper_exit_counter,
                  "validatedBeforeEnclosingCleanup": accepted, "beforeEnclosingCleanupCounter": before_cleanup,
                  "enclosingCleanupKnown": cleanup, "capturesClosed": captures_closed,
                  "witnesses": witnesses.evidence() if witnesses else [], "failureDetails": failures[:16],
                  "observerCandidate": observed, "supervisorCandidate": inner}
        try:
            H.require(run_directory is not None)
            raw = E.encoded(record)
            H.require(len(raw) <= RECORD_LIMIT)
            receipt = run_directory.create_file("admission.json", max_bytes=RECORD_LIMIT, deadline=deadline.monotonic_end())
            H.require(receipt.write(raw) == len(raw))
            deadline.check()
        finally:
            for owner in (receipt, run_directory, parent):
                try:
                    if owner is not None:
                        owner.close()
                        deadline.check()
                except BaseException:
                    passed = False
    deadline.check()
    if subject_end is None or deadline.now() >= subject_end:
        passed = False
    return (0 if passed else 1), deadline, subject_end


if __name__ == "__main__":
    result, deadline, subject_end = 1, None, None
    try:
        result, deadline, subject_end = run()
    except BaseException:
        result = 1
    sys.stdout.write("WINDOWS_INSTALLED_ADMISSION_QUALIFICATION " + ("PASS" if result == 0 else "FAIL") + "\n")
    sys.stdout.flush()
    if result == 0:
        try:
            H.require(deadline is not None and subject_end is not None and deadline.now() < subject_end)
        except BaseException:
            result = 1
    os._exit(result)
