"""Bounded read-only CPU observations during the original cold-boot deadline.

No extra wait, thread, process, permission, warm-up or readiness attempt. These
observations cannot grant readiness/ownership or extend any timeout. Process
lifetime keys stay in memory; only the existing closed numeric role aggregates
can leave the controller. Native read/deallocation errors remain failures.
"""
from __future__ import annotations

import time

import rpc_intel_process_diagnostics as processes

SCOPE = 'COLD_BOOT_PROCESS_INTERVALS_NOT_READINESS_OR_OWNERSHIP'
ROLES = ('macos-x64', 'macos-arm64')
PERIOD = processes.CPU_WAIT_SECONDS * 10 ** 9


def need(condition):
    if not condition:
        raise ValueError('Invalid bounded Apple boot process observation')


def validate(value):
    need(type(value) is dict and set(value) == {
        'schema', 'scope', 'nativeRole', 'executionAdmitted', 'elapsedNanos',
        'unobservedTailNanos', 'intervals'} and type(value['schema']) is int and value['schema'] == 1 and
        value['scope'] == SCOPE and value['nativeRole'] in ROLES and value['executionAdmitted'] is False)
    need(all(type(value[k]) is int and 0 <= value[k] < 2 ** 63 for k in ('elapsedNanos', 'unobservedTailNanos')) and
         value['unobservedTailNanos'] <= value['elapsedNanos'])
    need(type(value['intervals']) is list and len(value['intervals']) <= 32)
    previous = 0
    for interval in value['intervals']:
        need(type(interval) is dict and set(interval) == {'endedElapsedNanos', 'cpu'} and
             type(interval['endedElapsedNanos']) is int and previous < interval['endedElapsedNanos'] <= value['elapsedNanos'])
        processes.validate_cpu_interval(interval['cpu'])
        previous = interval['endedElapsedNanos']
    need(value['elapsedNanos'] - previous == value['unobservedTailNanos'])
    return value


class BootObserver:
    def __init__(self, expected_role, *, native=None, now=time.monotonic_ns):
        need(expected_role in ROLES)
        self.role, self.now = expected_role, now
        # The phone caller uses its independently admitted context's native
        # role, never uname spoofing or x86 evidence as an ARM substitute.
        self.native = native if native is not None else processes.NativeSnapshot(expected_role=expected_role)
        self.numerator, self.denominator = self.native.timebase()
        need(0 < self.numerator < 2 ** 32 and 0 < self.denominator < 2 ** 32)
        self.started = None
        self.previous = None
        self.intervals = []

    def start(self):
        need(self.started is None)
        self.started = self.now()
        self.previous = processes.cpu_records(self.native, self.now)
        self.observed_at = self.now()

    def sample(self):
        need(self.started is not None and self.previous is not None)
        if self.now() - self.observed_at < PERIOD:
            return
        need(len(self.intervals) < 32)
        after = processes.cpu_records(self.native, self.now)
        end = self.now()
        cpu = processes.cpu_difference(self.previous, after, self.numerator, self.denominator,
            after['atNanos'] - self.observed_at, end - self.previous['atNanos'])
        self.intervals.append({'endedElapsedNanos': end - self.started, 'cpu': cpu})
        self.previous, self.observed_at = after, end

    def finish(self):
        # No final native read or sleep: product/cleanup deadlines still apply.
        need(self.started is not None)
        elapsed = self.now() - self.started
        return validate(dict(schema=1, scope=SCOPE, nativeRole=self.role, executionAdmitted=False,
            elapsedNanos=elapsed,
            unobservedTailNanos=elapsed - self.intervals[-1]['endedElapsedNanos'] if self.intervals else elapsed,
            intervals=self.intervals))
