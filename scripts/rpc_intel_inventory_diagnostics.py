#!/usr/bin/env python3
"""Observe one real Intel runtime inventory command, never readiness or ownership.

Only the explicit runtime investigation uses this source-bound wrapper. Its
parent native executor retains the original 120-second deadline and owns every
descendant. No retry, warm-up, process signal, permission or timeout override.
The command's stdout is untouched. Closed numeric CPU observations go to the
private stderr log so a silent/timed-out inventory still leaves useful evidence.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import rpc_apple_boot_diagnostics as intervals
import rpc_intel_process_diagnostics as processes
import rpc_intel_service_diagnostics as service_logs
import rpc_apple_audit_context as audit_context

COMMAND = ('/usr/bin/xcrun', 'simctl', 'list', '--json', 'runtimes')
PREFIX = 'RPC_INTEL_INVENTORY_CPU_JSON:'
SCOPE = 'RUNTIME_INVENTORY_CPU_NOT_READINESS_OR_OWNERSHIP'
MAX_LOG = 4 * 1024 * 1024


def need(condition):
    if not condition:
        raise ValueError('Invalid source-bound Intel inventory observation')


def admit(env):
    audit = audit_context.requested(env)
    need(env.get('RPC_INTEL_INVESTIGATION') == 'runtime' and env.get('RPC_APPLE_LANE') == 'apple-x64' and
         env.get('RPC_QUALIFY_REQUESTED') == 'true' and
         (env.get('RPC_APPLE_TERMINAL_CONTEXT') == 'true' or audit) and
         env.get('DEVELOPER_DIR') == '/Applications/Xcode_26.3.app/Contents/Developer' and
         env.get('P2PKIT_AUDIT_OWNERSHIP_CHAIN'))


def validate(value):
    need(type(value) is dict and set(value) == {'schema', 'scope', 'executionAdmitted', 'elapsedNanos',
        'unobservedTailNanos', 'intervals', 'childExitCode'} and value['scope'] == SCOPE and
        (value['childExitCode'] is None or type(value['childExitCode']) is int and -255 <= value['childExitCode'] <= 255))
    # Reuse the closed interval/count/lifetime-consistency validator, not its
    # boot scope. The exported record always describes inventory, not a boot.
    intervals.validate({k: v for k, v in value.items() if k not in ('scope', 'childExitCode')} |
                       dict(scope=intervals.SCOPE, nativeRole='macos-x64'))
    return value


def observation(raw):
    need(type(raw) is bytes and len(raw) <= MAX_LOG)
    def unique(pairs):
        row = {}
        for key, value in pairs:
            need(key not in row)
            row[key] = value
        return row
    previous = None
    count = 0
    for line in raw.decode('utf-8').splitlines():
        if not line.startswith(PREFIX):
            continue  # Never export the tool's arbitrary error text.
        count += 1
        need(count <= 34 and len(line) <= 128 * 1024)
        row = validate(json.loads(line[len(PREFIX):], object_pairs_hook=unique))
        if previous is not None:
            need(previous['childExitCode'] is None and row['elapsedNanos'] >= previous['elapsedNanos'] and
                 row['intervals'][:len(previous['intervals'])] == previous['intervals'])
        previous = row
    return previous  # Missing evidence is not a zero CPU or successful command.


def publish(value):
    print(PREFIX + json.dumps(validate(value), sort_keys=True, separators=(',', ':')), file=sys.stderr, flush=True)


def run_inventory(*, native=None, now=time.monotonic_ns, sleep=time.sleep, launch=subprocess.Popen, emit=publish,
                  launch_log=subprocess.Popen, log_emit=lambda line: print(line, file=sys.stderr, flush=True)):
    # NativeSnapshot independently rejects root, translation, a foreign native
    # role and missing ownership context before any child is created.
    native = native if native is not None else processes.NativeSnapshot(expected_role='macos-x64')
    numerator, denominator = native.timebase()
    need(0 < numerator < 2 ** 32 and 0 < denominator < 2 ** 32)
    started = now()
    previous = processes.cpu_records(native, now)
    observed_at = now()
    rows = []
    child = launch(list(COMMAND), stdin=subprocess.DEVNULL)
    reader = None
    reader_reported = False
    reader_code = None
    def record(code):
        elapsed = now() - started
        emit(validate(dict(schema=1, scope=SCOPE, executionAdmitted=False, elapsedNanos=elapsed,
            unobservedTailNanos=elapsed - rows[-1]['endedElapsedNanos'] if rows else elapsed,
            intervals=list(rows), childExitCode=code)))
    record(None)
    while child.poll() is None:
        if reader is None and now() - started >= service_logs.QUERY_AFTER_NANOS:
            # One read-only query, while the ORIGINAL inventory is still live.
            # It has no separate extended bound, retry, service mutation or
            # privilege. The native parent owns and finalizes this descendant.
            log_emit(service_logs.BEGIN)
            reader = launch_log(list(service_logs.COMMAND), stdin=subprocess.DEVNULL,
                                stdout=sys.stderr, stderr=sys.stderr)
        if reader is not None and not reader_reported and reader.poll() is not None:
            reader_code = reader.wait()
            log_emit(service_logs.END + json.dumps(dict(exitCode=reader_code), sort_keys=True))
            reader_reported = True
        if now() - observed_at >= intervals.PERIOD:
            need(len(rows) < 32)
            after = processes.cpu_records(native, now)
            ended = now()
            cpu = processes.cpu_difference(previous, after, numerator, denominator,
                after['atNanos'] - observed_at, ended - previous['atNanos'])
            rows.append(dict(endedElapsedNanos=ended - started, cpu=cpu))
            previous, observed_at = after, ended
            record(None)
        sleep(.1)
    code = child.wait()
    if reader is not None and not reader_reported:
        # No detached reader or suppressed cleanup: this remains inside the
        # original native-owned 120-second command envelope, including drain.
        reader_code = reader.wait()
        log_emit(service_logs.END + json.dumps(dict(exitCode=reader_code), sort_keys=True))
    record(code)
    # Keep the actual inventory exit in its observation, but never turn a
    # failed requested diagnostic into a passing experiment.
    return code if code or reader_code is None else reader_code


def main():
    need(len(sys.argv) == 1)
    admit(os.environ)
    return run_inventory()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # The native executor still owns/finalizes any created child. Never
        # turn an observation failure into a passing inventory or leak text.
        print('Intel inventory observation failed; no admission', file=sys.stderr)
        raise SystemExit(125)
