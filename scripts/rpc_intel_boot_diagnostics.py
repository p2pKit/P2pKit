#!/usr/bin/env python3
"""Observe one original Intel cold boot; never grant readiness or ownership.

The native parent retains its 120-second deadline and all descendant cleanup.
Unlike a later CPU snapshot, these intervals describe the actual attempted
boot. No other command, warm-up, retry, policy change or signal is introduced.
Only closed numeric role aggregates leave the private tool output stream.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

import rpc_apple_boot_diagnostics as intervals
import rpc_intel_inventory_diagnostics as inventory
import rpc_intel_process_diagnostics as processes

PREFIX = 'RPC_INTEL_COLD_BOOT_CPU_JSON:'
SCOPE = 'INTEL_COLD_BOOT_CPU_NOT_READINESS_OR_OWNERSHIP'
MAX_LOG = 4 * 1024 * 1024


def need(condition):
    if not condition:
        raise ValueError('Invalid source-bound Intel cold-boot observation')


def admit(env, device):
    inventory.admit(env)  # Preserve the exact native/runtime/owned context.
    need(type(device) is str and re.fullmatch(r'[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}', device) and
         env.get('P2PKIT_SELECTED_SIMULATOR') == device)


def validate(value):
    need(type(value) is dict and set(value) == {'schema', 'scope', 'executionAdmitted', 'elapsedNanos',
        'unobservedTailNanos', 'intervals', 'childExitCode'} and value['scope'] == SCOPE and
        (value['childExitCode'] is None or type(value['childExitCode']) is int and -255 <= value['childExitCode'] <= 255))
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
            continue  # Raw tool messages, device IDs and paths are never exported.
        count += 1
        need(count <= 34 and len(line) <= 128 * 1024)
        row = validate(json.loads(line[len(PREFIX):], object_pairs_hook=unique))
        if previous is not None:
            need(previous['childExitCode'] is None and row['elapsedNanos'] >= previous['elapsedNanos'] and
                 row['intervals'][:len(previous['intervals'])] == previous['intervals'])
        previous = row
    return previous  # Missing/partial observation cannot establish successful boot.


def publish(value):
    print(PREFIX + json.dumps(validate(value), sort_keys=True, separators=(',', ':')), file=sys.stderr, flush=True)


def run_boot(device, *, native=None, now=time.monotonic_ns, sleep=time.sleep, launch=subprocess.Popen, emit=publish):
    # This independently checks the actual native role, credentials and ownership
    # before launching any child. Test injection is not the execution admission.
    native = native if native is not None else processes.NativeSnapshot(expected_role='macos-x64')
    observer = intervals.BootObserver('macos-x64', native=native, now=now)
    observer.start()
    child = launch(['/usr/bin/xcrun', 'simctl', 'bootstatus', device, '-b'], stdin=subprocess.DEVNULL)
    def record(code):
        row = observer.finish()  # No further native read, sleep or hidden boot time.
        row['intervals'] = list(row['intervals'])  # Later samples cannot rewrite a published frame.
        emit(validate({k: v for k, v in row.items() if k not in ('scope', 'nativeRole')} |
                      dict(scope=SCOPE, childExitCode=code)))
    record(None)
    count = 0
    while child.poll() is None:
        observer.sample()
        if len(observer.intervals) != count:
            count = len(observer.intervals)
            record(None)
        sleep(.1)
    code = child.wait()
    record(code)
    return code  # Never erase an unsuccessful tool result with successful diagnostics.


def main():
    need(len(sys.argv) == 2)
    admit(os.environ, sys.argv[1])
    return run_boot(sys.argv[1])


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # Any live descendant is still the original native parent's obligation.
        # No catch-and-pass, PID signal or arbitrary exception text in public logs.
        print('Intel cold-boot observation failed; no admission', file=sys.stderr)
        raise SystemExit(125)
