#!/usr/bin/env python3
"""Fixed installed diagnostic, not installation/account/provider authorization.

The external observer starts QPC before Python creation and must observe exit
within 30s. A separate outer process owns the E worker; its watchdog THREAD
remains armed through exit. Ordinary CPython/GIL and OS scheduling are trusted.
A hard kill requests job retirement, but never proves successful cleanup.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SCOPE = "INSTALLED_ADMISSION_SUPERVISION_NOT_PROFILE_QUALIFICATION"
LIMIT_SECONDS = 30
LOG_LIMIT = 4096
RECORD_LIMIT = 16384
SOURCE_FILES = ("run-windows-installed-diagnostic.py", "ci_evidence.py", "audit_processes.py",
                "hosted_evidence.py", "hosted_evidence_primitives.py", "hosted_windows_files.py")
COMMAND_FIELDS = {"exitCode", "timedOut", "cleanupKnown", "capturesClosed", "stage", "code",
                  "nativeError", "cleanupReasons", "pendingContext", "elapsedSeconds"}


def require(condition):
    if not condition:
        raise ValueError("WINDOWS_INSTALLED_SUPERVISOR_REFUSED")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("WINDOWS_INSTALLED_SUPERVISOR_ARGUMENTS")


def arguments(argv):
    parser = Parser(add_help=False, allow_abbrev=False)
    parser.add_argument("--start-counter", type=int, required=True)
    parser.add_argument("--counter-frequency", type=int, required=True)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--private-parent", required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require(re.fullmatch(r"[0-9a-f]{40}", args.expected_source) is not None)
    require(Path(args.private_parent).is_absolute())
    return args


class Counter:
    """Original shared Windows QPC units, not Python's monotonic epoch."""
    def __init__(self):
        require(os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8)
        self.kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
        signatures = {
            "QueryPerformanceCounter": ([ctypes.POINTER(ctypes.c_int64)], ctypes.c_int),
            "QueryPerformanceFrequency": ([ctypes.POINTER(ctypes.c_int64)], ctypes.c_int),
            "GetCurrentProcess": ([], ctypes.c_void_p),
            "TerminateProcess": ([ctypes.c_void_p, ctypes.c_uint32], ctypes.c_int),
            "RaiseFailFastException": ([ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32], None),
        }
        for name, (parameters, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = parameters, result
        value = ctypes.c_int64()
        require(self.kernel.QueryPerformanceFrequency(ctypes.byref(value)) and value.value > 0)
        self.frequency = value.value
        self.process = self.kernel.GetCurrentProcess()  # Original self pseudo-handle; never transferred/closed.
        require(self.process)

    def now(self):
        value = ctypes.c_int64()
        require(self.kernel.QueryPerformanceCounter(ctypes.byref(value)) and value.value >= 0)
        return value.value

    def terminate(self):
        # No stdout, lock, filesystem, Job-handle borrowing or interpreter finalizers.
        self.kernel.TerminateProcess(self.process, 125)
        self.kernel.RaiseFailFastException(None, None, 0)
        os._exit(125)


class Deadline:
    def __init__(self, counter, start, frequency):
        require(type(start) is int and 0 <= start < 2**63)
        require(type(frequency) is int and 0 < frequency <= 10**12 and frequency == counter.frequency)
        self.counter, self.start, self.frequency = counter, start, frequency
        self.end = start + LIMIT_SECONDS * frequency
        require(self.end < 2**63)
        self.check()

    def now(self):
        value = self.counter.now()
        require(type(value) is int and self.start <= value)
        return value

    def check(self, reserve=0):
        remaining = (self.end - self.now()) / self.frequency - reserve
        require(remaining > 0)
        return remaining

    def monotonic_end(self, reserve=0):
        # Conversion is only for existing relative APIs. QPC postchecks remain authoritative.
        return time.monotonic() + self.check(reserve)

    def worker_budgets(self):
        available = self.check(5)
        cleanup = min(5.0, available / 3)
        work = min(15.0, available - cleanup)
        require(work >= 0.1 and cleanup >= 0.1)
        return work, cleanup


def arm_watchdog(deadline):
    started = threading.Event()

    def watch():
        started.set()
        try:
            while True:
                # One second remains for kernel termination and external exit observation.
                time.sleep(min(0.02, deadline.check(1)))
        except BaseException:
            deadline.counter.terminate()

    thread = threading.Thread(target=watch, name="installed-deadline", daemon=True)
    thread.start()
    require(started.wait(timeout=deadline.check()))
    deadline.check()
    return thread  # Intentionally never disarmed or joined; external observer verifies process exit.


def modules():
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import audit_processes as A
    import ci_evidence as E
    import hosted_windows_files as F
    return A, E, F


def source_identity():
    # Packet binds these actual bytes to its supervisor commit/tree externally.
    # No unowned git subprocess or circular self-reported commit assertion.
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def installed_launcher():
    kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    kernel.IsWow64Process2.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint16),
                                     ctypes.POINTER(ctypes.c_uint16)]
    kernel.IsWow64Process2.restype = ctypes.c_int
    process_machine, native_machine = ctypes.c_uint16(), ctypes.c_uint16()
    require(kernel.IsWow64Process2(ctypes.c_void_p(-1), ctypes.byref(process_machine),
                                  ctypes.byref(native_machine)))
    require(process_machine.value == 0 and native_machine.value == 0x8664)
    shell = ctypes.WinDLL("shell32.dll", use_last_error=True, winmode=0x800)
    shell.SHGetFolderPathW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                     ctypes.c_uint32, ctypes.c_wchar_p]
    shell.SHGetFolderPathW.restype = ctypes.c_int32
    buffer = ctypes.create_unicode_buffer(260)
    require(shell.SHGetFolderPathW(None, 0x26, None, 0, buffer) == 0)
    root = Path(buffer.value)
    require(root.is_absolute())
    return root / "P2pKit Sample" / "P2pKit Sample.exe"


def expected_admission(source):
    return {"source": source, "admission": {"schema": 1,
        "scope": "INSTALLED_ADMISSION_ONLY_NOT_PROFILE_PROVIDER_QUALIFICATION",
        "admission": "REGISTERED", "repeat": "REUSED", "profileStorage": "NOT_ENTERED",
        "network": "NOT_ENTERED", "publicProvider": "NOT_ENTERED"}}


def admission_matches(raw, source):
    line = json.dumps(expected_admission(source), separators=(",", ":")).encode("ascii")
    return raw in (line + b"\n", line + b"\r\n")


def decode(raw, maximum):
    require(type(raw) is bytes and 0 < len(raw) <= maximum)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result
    def nonfinite(value):
        require(False)
    def finite_float(value):
        number = float(value)
        require(math.isfinite(number))
        return number
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=nonfinite, parse_float=finite_float)


def read_bounded(path, maximum):
    with path.open("rb") as stream:
        value = stream.read(maximum + 1)
    require(len(value) <= maximum)
    return value


def command_pass(outcome):
    return (type(outcome) is dict and set(outcome) == COMMAND_FIELDS and
        outcome.get("stage") == "COMMAND" and outcome.get("code") == "PASS" and
        type(outcome.get("exitCode")) is int and outcome["exitCode"] == 0 and
        outcome.get("timedOut") is False and outcome.get("cleanupKnown") is True and
        outcome.get("capturesClosed") is True and outcome.get("cleanupReasons") == [] and
        outcome.get("nativeError") is None and outcome.get("pendingContext") is None and
        type(outcome.get("elapsedSeconds")) in (int, float) and
        math.isfinite(outcome["elapsedSeconds"]) and outcome["elapsedSeconds"] >= 0)


def write_new(E, path, value):
    raw = E.encoded(value)
    require(len(raw) <= RECORD_LIMIT)
    E.write_private(path, raw)


def worker_argv(args, directory):
    return [sys.executable, "-I", "-B", "-S", str(HERE / "run-windows-installed-diagnostic.py"),
        "--worker", "--start-counter", str(args.start_counter),
        "--counter-frequency", str(args.counter_frequency), "--expected-source", args.expected_source,
        "--private-parent", str(directory.parent)]


def worker(args, deadline, E):
    directory = Path(args.private_parent) / "run"
    launcher = installed_launcher()
    work, cleanup = deadline.worker_budgets()
    outcome = E.run_command([str(launcher), "--rpc-windows-installed-admission"], cwd=launcher.parent,
        environment=dict(os.environ), private=directory / "command", timeout=work,
        cleanup_seconds=cleanup, log_limit=LOG_LIMIT)
    deadline.check(2)
    accepted = False
    if command_pass(outcome):
        raw = read_bounded(directory / "command" / "stdout.log", LOG_LIMIT)
        stderr = read_bounded(directory / "command" / "stderr.log", LOG_LIMIT)
        accepted = not stderr and admission_matches(raw, args.expected_source)
    value = {"schema": 1, "appSource": args.expected_source, "outcome": outcome,
             "admissionMatched": accepted}
    write_new(E, directory / "worker.json", value)
    deadline.check(2)
    return 0 if accepted else 1


def validate_worker(value, source):
    require(type(value) is dict and set(value) == {"schema", "appSource", "outcome", "admissionMatched"})
    require(type(value["schema"]) is int and value["schema"] == 1 and value["appSource"] == source)
    require(type(value["admissionMatched"]) is bool and type(value["outcome"]) is dict)
    return value["admissionMatched"] and command_pass(value["outcome"])


def capture_closed(capture):
    return (capture.thread.ident is not None and not capture.thread.is_alive() and
            capture.eof and capture.closed and capture.error is None)


def supervise(args, deadline, A, E, F):
    parent = run = receipt = scope = child = None
    captures, original_pipes = [], []
    cleanup, closed, accepted = False, False, False
    worker_value = None
    failure = False
    before = source_identity()
    directory = Path(args.private_parent) / "run"
    try:
        deadline.check(5)
        parent = F.open_private_directory(args.private_parent)
        run = parent.create_directory("run", deadline=deadline.monotonic_end(4))
        deadline.check(5)
        job, invocation = uuid.uuid4().hex, uuid.uuid4().hex
        home = str(directory / "gradle-home")
        environment = A.ownership_environment(dict(os.environ), job, invocation,
            str(directory), home, allow_new_context=True)
        scope = A.WindowsScope(job, invocation, str(directory), home)
        deadline.check(5)
        child = scope.spawn(worker_argv(args, directory), str(HERE.parent), environment)
        original_pipes = [child.stdout, child.stderr]
        deadline.check(4)
        captures = [E.Capture(pipe, directory / ("worker-" + label + ".log"), LOG_LIMIT)
                    for pipe, label in zip(original_pipes, ("stdout", "stderr"))]
        for capture in captures:
            capture.thread.start()
        while True:
            deadline.check(4)
            require(not any(capture.error for capture in captures))
            scope.discover()
            deadline.check(4)
            code = child.poll()
            deadline.check(4)
            if code is not None:
                require(code == 0)
                break
            time.sleep(min(0.05, deadline.check(4)))
    except BaseException:
        failure = True
    finally:
        if scope is not None:
            for leader in scope.leaders:
                for pipe in (leader.stdout, leader.stderr):
                    if pipe is not None and all(pipe is not original for original in original_pipes):
                        original_pipes.append(pipe)
        try:
            if scope is not None:
                live = scope.drain(grace=0.2, kill_wait=min(2.0, deadline.check(2)),
                                   deadline=deadline.monotonic_end(2))
                deadline.check(2)
                cleanup = not live and not scope.discovery_errors
                for leader in scope.leaders:
                    leader.wait(timeout=deadline.check(2))
                    deadline.check(2)
        except BaseException:
            cleanup, failure = False, True
        try:
            if scope is not None:
                scope.close()
                deadline.check(2)
        except BaseException:
            cleanup, failure = False, True
        for capture in captures:
            try:
                capture.thread.join(timeout=deadline.check(1))
                deadline.check(1)
            except BaseException:
                failure = True
        adopted = {id(capture.pipe) for capture in captures if capture.thread.ident is not None}
        for pipe in original_pipes:
            if id(pipe) not in adopted:
                try:
                    pipe.close()
                    deadline.check(1)
                except BaseException:
                    failure = True
        closed = len(captures) == 2 and all(capture_closed(capture) for capture in captures)
        try:
            if cleanup and closed:
                require(not any(read_bounded(directory / ("worker-" + label + ".log"), LOG_LIMIT)
                                for label in ("stdout", "stderr")))
                worker_value = decode(read_bounded(directory / "worker.json", RECORD_LIMIT), RECORD_LIMIT)
                accepted = validate_worker(worker_value, args.expected_source)
            require(source_identity() == before)
            if run is not None:
                run.verify()
            if parent is not None:
                parent.verify()
            deadline.check(1)
        except BaseException:
            failure, accepted = True, False
        try:
            accepted = accepted and not failure and cleanup and closed
            record = {"schema": 1, "scope": SCOPE, "status": "PASS" if accepted else "FAIL",
                "appSource": args.expected_source, "supervisorSource": before,
                "startCounter": deadline.start, "counterFrequency": deadline.frequency,
                "deadlineCounter": deadline.end, "watchdogCounter": deadline.end - deadline.frequency,
                "completedCounter": deadline.now(),
                "workerOutcome": worker_value, "outerCleanupKnown": cleanup, "capturesClosed": closed}
            deadline.check()
            require(run is not None)
            raw = E.encoded(record)
            require(len(raw) <= RECORD_LIMIT)
            # Create/write through the ORIGINAL directory while its parent pins
            # remain owned. A pathname reopen after releasing them is not custody.
            receipt = run.create_file("supervisor.json", max_bytes=RECORD_LIMIT,
                                      deadline=deadline.monotonic_end())
            deadline.check()
            require(receipt.write(raw) == len(raw))
            deadline.check()
        finally:
            for owner in (receipt, run, parent):
                try:
                    if owner is not None:
                        owner.close()
                        deadline.check()
                except BaseException:
                    failure, accepted = True, False
            # A previously written PASS candidate cannot certify its own close.
            # The external observer also requires timely actual outer exit0.
    deadline.check()
    return 0 if accepted else 1


def main(argv=None):
    code, args, deadline = 1, None, None
    try:
        args = arguments(sys.argv[1:] if argv is None else argv)
        deadline = Deadline(Counter(), args.start_counter, args.counter_frequency)
        arm_watchdog(deadline)
        A, E, F = modules()
        code = worker(args, deadline, E) if args.worker else supervise(args, deadline, A, E, F)
        deadline.check()
    except BaseException:
        code = 1
    if args is None or not args.worker:
        sys.stdout.write("WINDOWS_INSTALLED_SUPERVISOR " + ("PASS" if code == 0 else "FAIL") + "\n")
        sys.stdout.flush()
    if deadline is not None:
        try:
            deadline.check()
        except BaseException:
            code = 1
    os._exit(code)  # Watchdog remains armed even during this final process exit.


if __name__ == "__main__":
    main()
