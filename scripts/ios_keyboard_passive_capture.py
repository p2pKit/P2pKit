#!/usr/bin/env python3
"""Post-Xcode, read-only #520 telemetry from the ordinary selected simulator.

This temporary investigative branch does not create/retire a device, open
Simulator, change preferences, rerun tests, or decide keyboard readiness.
The caller retains its original result and launcher lock until this returns.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import tempfile
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_processes
import ci_evidence

SUBSYSTEM = "dev.p2pkit.sample.keyboard-cause-probe"
MAX_BYTES = 512 * 1024
CAPTURE_SECONDS = 30
CLOSE_SECONDS = 30
DEADLINE_ENV = "P2PKIT_CI_COMMAND_DEADLINE_NS"
UUID = re.compile(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}")


class CaptureError(RuntimeError):
    """Source-owned diagnostic code, never a native command/error transcript."""


def require(condition, code):
    if not condition:
        raise CaptureError(code)


def admit(environment, device):
    require(environment.get("COMPONENT") in ("compatibility", "apple-keyboard-query-diagnostic") and
            ci_evidence._hosted_darwin_context(environment), "HOSTED_KEYBOARD_OBSERVATION_REQUIRED")
    require(UUID.fullmatch(device) is not None, "EXACT_SELECTED_DEVICE_REQUIRED")
    domains = audit_processes.ownership_domains(environment.get(audit_processes.CHAIN_ENV, ""),
                                               environment.get(audit_processes.DOMAINS_ENV, ""))
    require(domains and all(environment.get(key) == domains[-1][field] for key, field in (
        (audit_processes.JOB_ENV, "job"), (audit_processes.STATE_ENV, "state"),
        ("GRADLE_USER_HOME", "home"))), "INHERITED_OWNERSHIP_REQUIRED")
    deadline = environment.get(DEADLINE_ENV, "")
    require(re.fullmatch(r"[0-9]{1,20}", deadline) is not None, "INHERITED_DEADLINE_REQUIRED")
    return int(deadline) / 1e9


def log_command(device):
    # The 3h retrospective window covers Compatibility's unchanged 180-minute
    # outer command. It is not a wait or a new execution allowance. Consumers
    # still match process/arming/uptime markers; old log rows are not readiness.
    return ["/usr/bin/xcrun", "simctl", "spawn", device, "log", "show", "--style", "ndjson",
            "--info", "--last", "3h", "--predicate", 'subsystem == "' + SUBSYSTEM + '"']


def collect(device, command_status, launcher_status, environment, *, root=ROOT, cancelled=lambda: False):
    require(command_status is None or type(command_status) is int and 0 <= command_status <= 255,
            "INVALID_ORIGINAL_COMMAND_STATUS")
    require(type(launcher_status) is int and 0 <= launcher_status <= 255, "INVALID_LAUNCHER_STATUS")
    outer_end = admit(environment, device)
    report = root / "build/reports/keyboard-passive-probe"
    report.mkdir(mode=0o700, parents=True, exist_ok=False)
    private = Path(tempfile.mkdtemp(prefix="keyboard-passive-execution-", dir=root / "build"))
    begin = time.monotonic()
    # Only this post-return read/close is bounded here. Never rewrite the
    # inherited deadline, shorten XCTest, or create a fresh cleanup allowance.
    close_end = min(outer_end, begin + CAPTURE_SECONDS + CLOSE_SECONDS)
    capture_end = min(begin + CAPTURE_SECONDS, close_end - CLOSE_SECONDS)
    scope, child, streams = None, None, []
    log_status, completed_in_time, retirement_known = None, False, False
    errors, native_errors = [], []

    def check():
        require(not cancelled() and launcher_status not in (130, 143), "CANCELLED")
        require(time.monotonic() < capture_end, "CAPTURE_DEADLINE")
        require(not any(stream.error for stream in streams), "CAPTURE_FAILED")

    def failed(code, error):
        errors.append(error.args[0] if type(error) is CaptureError else code)
        diagnostic = ci_evidence.native_error_diagnostic(error)
        if diagnostic is not None:
            native_errors.append({"stage": code, "diagnostic": diagnostic})

    try:
        check()
        require(command_status is not None, "ORIGINAL_COMMAND_EXIT_UNOBSERVED")
        token = uuid.uuid4().hex
        child_environment = audit_processes.local_ownership_environment(environment, token)
        scope = ci_evidence.local_command_scope(environment[audit_processes.JOB_ENV], token,
            str(private), environment["GRADLE_USER_HOME"], environment)
        check()
        child = scope.spawn(log_command(device), str(root), child_environment)
        for name, pipe in (("stdout.log", child.stdout), ("stderr.log", child.stderr)):
            stream = ci_evidence.Capture(pipe, private / name, MAX_BYTES)
            streams.append(stream)
            stream.thread.start()
        next_discovery = begin
        while True:
            check()  # Native admission/spawn time belongs to the same bound.
            log_status = child.poll()
            check()  # A late or fast exit cannot bypass the original clock.
            if log_status is not None:
                completed_in_time = True
                require(log_status == 0, "LOG_COMMAND_FAILED")
                break
            if time.monotonic() >= next_discovery:
                scope.discover()
                next_discovery = time.monotonic() + 1
                check()
            time.sleep(min(.05, max(0, capture_end - time.monotonic())))
    except BaseException as error:
        failed("NATIVE_CAPTURE_FAILED", error)
    finally:
        # A native spawn can register a real leader and then raise before
        # returning. Retain all original pipes before scope.close clears them.
        leaders = tuple(scope.leaders) if scope else ()
        pipes = [pipe for leader in leaders for pipe in (leader.stdout, leader.stderr) if pipe is not None]
        if scope:
            try:
                live = scope.drain(grace=10, kill_wait=10, deadline=close_end)
                retirement_known = not live and not scope.discovery_errors
                require(retirement_known, "NATIVE_RETIREMENT_UNKNOWN")
                for leader in leaders:
                    leader.wait(timeout=max(0, close_end - time.monotonic()))
            except BaseException as error:
                retirement_known = False
                failed("NATIVE_RETIREMENT_FAILED", error)
            finally:
                try:
                    scope.close()
                except BaseException as error:
                    retirement_known = False
                    failed("SCOPE_CLOSE_FAILED", error)
        for stream in streams:
            if stream.thread.ident is not None:
                stream.thread.join(timeout=max(0, close_end - time.monotonic()))
        adopted = {id(stream.pipe) for stream in streams if stream.thread.ident is not None}
        for pipe in pipes:
            if id(pipe) not in adopted:
                try:
                    pipe.close()
                except BaseException as error:
                    retirement_known = False
                    failed("ORIGINAL_PIPE_CLOSE_FAILED", error)

    captures_closed = len(streams) == 2 and all(not stream.thread.is_alive() and stream.eof and
        stream.closed and stream.error is None for stream in streams)
    if not captures_closed:
        errors.append("CAPTURE_NOT_CLOSED")
    retained = []
    for stream in streams:
        row = dict(name=stream.path.name, eof=stream.eof, closed=stream.closed,
                   error=stream.error, retained=False)
        retained.append(row)
        # A closed partial sink is useful failure evidence, not complete output.
        # Never read/copy a sink while its original writer remains active.
        if stream.thread.is_alive() or not stream.closed or not stream.path.is_file():
            continue
        raw = stream.path.read_bytes()
        require(len(raw) <= MAX_BYTES, "CAPTURE_BOUND_CHANGED")
        ci_evidence.write_private(report / stream.path.name, raw)
        row.update(retained=True, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        if stream.path.name == "stdout.log" and (b"KEYBOARD_CAUSE_EVENT" not in raw or b"event=armed" not in raw):
            errors.append("APP_TELEMETRY_NOT_OBSERVED")
    if time.monotonic() >= close_end:
        errors.append("CAPTURE_CLOSE_DEADLINE")
    if cancelled():
        errors.append("CANCELLED")
    summary = dict(schema=1, scope="KEYBOARD_OBSERVATION_NOT_QUALIFICATION",
        component=environment["COMPONENT"],
        sourceCommit=environment["GITHUB_SHA"], selectedDevice=device, deviceMutationAuthority=False,
        originalCommandExitCode=command_status, originalLauncherExitCode=launcher_status,
        logExitCode=log_status, logCompletedWithinDeadline=completed_in_time,
        nativeRetirementKnown=retirement_known, capturesClosed=captures_closed,
        inheritedDeadlineNs=environment[DEADLINE_ENV], captures=retained,
        errors=sorted(set(errors)), nativeErrors=native_errors, underlyingHistoricalCauseEstablished=False)
    ci_evidence.write_private(report / "summary.json", ci_evidence.encoded(summary))
    return (125 if errors else 0), summary


def main():
    os.umask(0o077)
    require(len(sys.argv) == 4, "EXACT_DEVICE_AND_ORIGINAL_STATUSES_REQUIRED")
    device, command, launcher = sys.argv[1:]
    require(command == "UNOBSERVED" or re.fullmatch(r"[0-9]{1,3}", command), "INVALID_ORIGINAL_COMMAND_STATUS")
    require(re.fullmatch(r"[0-9]{1,3}", launcher), "INVALID_LAUNCHER_STATUS")
    cancelled = [False]
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: cancelled.__setitem__(0, True))
    code, summary = collect(device, None if command == "UNOBSERVED" else int(command), int(launcher),
                            os.environ, cancelled=lambda: cancelled[0])
    # The enclosing evidence owner encrypts stdout. Forward only already-closed,
    # bounded copies so its closed-captures-only failure path can retain them too.
    print("KEYBOARD_PASSIVE_CAPTURE_SUMMARY_JSON:" + json.dumps(summary, sort_keys=True), flush=True)
    for row in summary["captures"]:
        if row["retained"]:
            print("KEYBOARD_PASSIVE_CLOSED_CAPTURE_BEGIN " + row["name"], flush=True)
            sys.stdout.buffer.write((ROOT / "build/reports/keyboard-passive-probe" / row["name"]).read_bytes())
            sys.stdout.buffer.flush()
            print("\nKEYBOARD_PASSIVE_CLOSED_CAPTURE_END " + row["name"], flush=True)
    return code


if __name__ == "__main__":
    try:
        result = main()
    except BaseException as error:
        # Never forward exception text, paths or native stderr unencrypted.
        code = str(error) if type(error) is CaptureError else "CAPTURE_FAILED"
        print("KEYBOARD_PASSIVE_CAPTURE_REFUSED " + code, file=sys.stderr)
        result = 125
    raise SystemExit(result)
