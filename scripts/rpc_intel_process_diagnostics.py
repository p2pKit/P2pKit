#!/usr/bin/env python3
"""Read-only, nonprivileged Intel boot observations, never ownership authority.

The system ps executable is set-id on the affected runner. Use documented
libproc/Mach read APIs instead; do not copy ps, elevate, inspect arguments or
environments, acquire task ports, signal processes, or change system policy.
Only aggregate counters for fixed OS roles leave the process. Unreadable and
racing processes are counted, never represented as absent or safely retired.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import PurePath
import sys
import time

from audit_processes import DarwinBsdInfo, host_role

ROLES = frozenset((
    'DataMigrator', 'backboardd', 'SpringBoard', 'launchd_sim', 'Simulator',
    'com.apple.CoreSimulator.CoreSimulatorService', 'simulatord', 'mds',
    'mds_stores', 'mdworker_shared', 'PerfPowerServices', 'mDNSResponder',
    'installd', 'mobileassetd', 'runningboardd', 'logd', 'ReportCrash',
    'ReportMemoryException', 'CrashReporterSupportHelper', 'diagnosticd',
    'WallpaperAgent', 'WallpaperImageExtension', 'WallpaperVideoExtension',
))
ROLE_FIELDS = frozenset(('count', 'residentBytes', 'threads', 'runningThreads',
                        'running', 'sleeping', 'other', 'sameUid', 'rootUid', 'otherUid'))
COUNTS = frozenset(('censusCount', 'unreadableCount', 'changedCount', 'otherRoleCount', 'observedCount'))
SCOPE = 'READ_ONLY_NATIVE_PROCESS_SNAPSHOT_NOT_OWNERSHIP_OR_CPU_ATTRIBUTION'
MAX_PROCESSES = 65536
MAX_BYTES = 128 * 1024


def need(condition):
    if not condition:
        raise ValueError('Invalid nonprivileged Intel process observation')


class TaskInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in (
        'virtual', 'resident', 'totalUser', 'totalSystem', 'threadsUser', 'threadsSystem')]
    _fields_ += [(name, ctypes.c_int32) for name in (
        'policy', 'faults', 'pageins', 'cowFaults', 'messagesSent', 'messagesReceived',
        'machSyscalls', 'unixSyscalls', 'switches', 'threadCount', 'runningThreads', 'priority')]


def validate(value):
    need(type(value) is dict and set(value) == COUNTS | {
        'schema', 'scope', 'unprivileged', 'elapsedNanos', 'cpuTicks', 'roles'})
    need(type(value['schema']) is int and value['schema'] == 1 and
         value['scope'] == SCOPE and value['unprivileged'] is True)
    need(all(type(value[k]) is int and 0 <= value[k] <= MAX_PROCESSES for k in COUNTS))
    need(value['censusCount'] > 0 and value['censusCount'] == sum(value[k] for k in (
        'unreadableCount', 'changedCount', 'otherRoleCount', 'observedCount')))
    need(type(value['elapsedNanos']) is int and 0 <= value['elapsedNanos'] < 2 ** 63)
    need(type(value['cpuTicks']) is dict and set(value['cpuTicks']) == {'user', 'system', 'idle', 'nice'} and
         all(type(n) is int and 0 <= n < 2 ** 32 for n in value['cpuTicks'].values()))
    need(type(value['roles']) is dict and set(value['roles']) <= ROLES)
    for row in value['roles'].values():
        need(type(row) is dict and set(row) == ROLE_FIELDS and
             all(type(n) is int and 0 <= n < 2 ** 63 for n in row.values()) and
             0 < row['count'] <= value['observedCount'] and row['residentBytes'] > 0 and
             row['runningThreads'] <= row['threads'] and
             row['running'] + row['sleeping'] + row['other'] == row['count'] and
             row['sameUid'] + row['rootUid'] + row['otherUid'] == row['count'])
    need(sum(row['count'] for row in value['roles'].values()) == value['observedCount'])
    return value


class NativeSnapshot:
    def __init__(self):
        need(sys.platform == 'darwin' and host_role() == 'macos-x64' and
             os.getuid() == os.geteuid() != 0 and os.getgid() == os.getegid() and
             os.environ.get('P2PKIT_AUDIT_OWNERSHIP_CHAIN'))
        need(ctypes.sizeof(TaskInfo) == 96 and ctypes.sizeof(DarwinBsdInfo) == 136)
        self.proc = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        self.system = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
        self.self_port = ctypes.c_uint32.in_dll(self.system, 'mach_task_self_').value
        for name, args in (
            ('proc_listallpids', [ctypes.c_void_p, ctypes.c_int]),
            ('proc_pidinfo', [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]),
            ('proc_pidpath', [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]),
        ):
            function = getattr(self.proc, name)
            function.argtypes, function.restype = args, ctypes.c_int
        for name, args, result in (
            ('mach_host_self', [], ctypes.c_uint32),
            ('host_statistics', [ctypes.c_uint32, ctypes.c_int, ctypes.c_void_p,
                                 ctypes.POINTER(ctypes.c_uint32)], ctypes.c_int),
            ('mach_port_deallocate', [ctypes.c_uint32, ctypes.c_uint32], ctypes.c_int),
        ):
            function = getattr(self.system, name)
            function.argtypes, function.restype = args, result

    def pids(self):
        count = self.proc.proc_listallpids(None, 0)
        need(0 < count <= MAX_PROCESSES)
        capacity = count + 128
        for _ in range(5):
            need(capacity <= MAX_PROCESSES)
            data = (ctypes.c_int * capacity)()
            size = self.proc.proc_listallpids(data, ctypes.sizeof(data))
            need(size > 0)
            if size < capacity:
                return sorted({n for n in data[:size] if n > 0})
            capacity *= 2
        raise ValueError('Intel process census did not stabilize')

    def cpu(self):
        port = self.system.mach_host_self()
        need(port != 0)
        try:
            ticks = (ctypes.c_uint32 * 4)()
            size = ctypes.c_uint32(4)
            need(self.system.host_statistics(port, 3, ticks, ctypes.byref(size)) == 0 and size.value == 4)
            return dict(zip(('user', 'system', 'idle', 'nice'), ticks))
        finally:
            need(self.system.mach_port_deallocate(self.self_port, port) == 0)

    def bsd(self, pid):
        row = DarwinBsdInfo()
        size = self.proc.proc_pidinfo(pid, 3, 0, ctypes.byref(row), ctypes.sizeof(row))
        return row if size == ctypes.sizeof(row) and row.pid == pid else None

    def path(self, pid):
        buffer = ctypes.create_string_buffer(4096)
        size = self.proc.proc_pidpath(pid, buffer, ctypes.sizeof(buffer))
        return PurePath(os.fsdecode(buffer.value)).name if 0 < size < len(buffer) else None

    def task(self, pid):
        row = TaskInfo()
        size = self.proc.proc_pidinfo(pid, 4, 0, ctypes.byref(row), ctypes.sizeof(row))
        return row if size == ctypes.sizeof(row) else None


def snapshot(native, now=time.monotonic_ns, uid=None):
    start = now()
    uid = os.getuid() if uid is None else uid
    need(uid > 0)
    value = dict(schema=1, scope=SCOPE, unprivileged=True, roles={}, cpuTicks=native.cpu(),
                 **dict.fromkeys(COUNTS, 0))
    pids = native.pids()
    value['censusCount'] = len(pids)
    for pid in pids:
        before = native.bsd(pid)
        role = native.path(pid) if before is not None else None
        if before is None or role is None:
            value['unreadableCount'] += 1
            continue
        if role not in ROLES:
            value['otherRoleCount'] += 1
            continue
        task = native.task(pid)
        after = native.bsd(pid)
        if task is None or after is None:
            value['unreadableCount'] += 1
            continue
        # This is read consistency, not a signaling/ownership identity.
        if (before.pid, before.startsec, before.startusec, before.uid, before.status, bytes(before.name)) != (
                after.pid, after.startsec, after.startusec, after.uid, after.status, bytes(after.name)):
            value['changedCount'] += 1
            continue
        if task.resident <= 0 or task.threadCount < 0 or not 0 <= task.runningThreads <= task.threadCount:
            value['unreadableCount'] += 1
            continue
        row = value['roles'].setdefault(role, dict.fromkeys(ROLE_FIELDS, 0))
        value['observedCount'] += 1
        row['count'] += 1
        row['residentBytes'] += task.resident
        row['threads'] += task.threadCount
        row['runningThreads'] += task.runningThreads
        row['running' if after.status == 2 else 'sleeping' if after.status == 3 else 'other'] += 1
        row['sameUid' if after.uid == uid else 'rootUid' if after.uid == 0 else 'otherUid'] += 1
    value['elapsedNanos'] = now() - start
    return validate(value)


def observation(raw):
    need(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES)
    def unique(pairs):
        value = {}
        for key, field in pairs:
            need(key not in value)
            value[key] = field
        return value
    return validate(json.loads(raw, object_pairs_hook=unique))


if __name__ == '__main__':
    need(sys.argv[1:] == ['snapshot'])
    print(json.dumps(snapshot(NativeSnapshot()), sort_keys=True, separators=(',', ':')))
