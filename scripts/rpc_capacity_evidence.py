"""Closed numeric capacity evidence. This never awards physical, mobile or release readiness."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

LIMIT = 8 * 1024 * 1024
HOST_FIELDS = ('sequence', 'uptimeMillis', 'cpuNanos', 'residentBytes', 'nativeThreads', 'jvmThreads',
               'connected', 'accepted', 'completed', 'refused', 'duplicates', 'droppedNotifications',
               'protocolFailures', 'connectionFailures', 'running', 'queued', 'records', 'payloadBytes')
STEADY_FIELDS = ('clients', 'callsPerSecondPerClient', 'encodedRequestBytes', 'encodedResponseBytes',
                 'requiredDurationNanos', 'actualSchedulingNanos', 'drainNanos', 'expected', 'dispatched',
                 'completed', 'failed', 'missedDispatches', 'timerLate', 'permitUnavailable', 'workerLate',
                 'outstandingAfterDrain', 'connectionChanges', 'invalidHostSamples', 'hostSamples',
                 'sampledMaxOutstanding', 'sampledMaxHostRssBytes', 'sampledMaxHostThreads', 'sampledMaxHostQueue',
                 'hostUptimeDeltaMillis', 'hostCpuDeltaNanos', 'hostAcceptedDelta', 'hostCompletedDelta',
                 'driverCpuDeltaNanos', 'driverGcCollectionsDelta', 'driverReportedGcMillisDelta')
LARGE_FIELDS = ('expected', 'concurrency', 'encodedRequestBytes', 'encodedResponseBytes', 'actualDurationNanos',
                'dispatched', 'completed', 'failed')
FAILURE_KINDS = ('NotConnected', 'Closed', 'PermissionMissing', 'Overloaded', 'DeadlineExceeded', 'Unauthorized',
                 'Authentication', 'Protocol', 'IncompatibleVersion', 'UnknownProcedure', 'InvalidPayload',
                 'HandlerFailed', 'ResultUnavailable', 'UnknownOutcome', 'HostRestarted', 'RemoteCancelled', 'TrustStorage')


def need(condition):
    if not condition:
        raise ValueError('Incomplete or invalid closed capacity evidence')


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result)
        result[key] = value
    return result


def bounded(path, maximum=LIMIT):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum)
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    need(len(raw) <= maximum)
    return raw


def read(path, maximum=LIMIT):
    return json.loads(bounded(path, maximum), object_pairs_hook=unique)


def numbers(value, fields):
    need(type(value) is dict and set(value) == set(fields))
    need(all(type(v) is int and 0 <= v < 2**63 for v in value.values()))
    return dict(value)


def histogram(value, samples=None):
    need(type(value) is dict and set(value) == {'p50', 'p95', 'p99', 'max'})
    need(all(type(v) is int and -1 <= v <= 30001 for v in value.values()))
    need(value['p50'] <= value['p95'] <= value['p99'] <= value['max'])
    if samples is not None:
        need(type(samples) is int and samples >= 0)
        need(all(v >= 0 for v in value.values()) if samples else all(v == -1 for v in value.values()))
    return dict(value)


def measurement(value, mode):
    need(mode in ('steady', 'large'))
    keys = {'schema', 'mode', 'status', 'capacityQualified', 'measurements', 'throughputResponsesPerSecond',
            'latencyBucketUpperMs', 'latencyOverflowBucketMs', 'rpcFailuresByKind', 'cleanup'}
    if mode == 'steady':
        keys.add('schedulingDelayBucketUpperMs')
    need(type(value) is dict and set(value) == keys and type(value['schema']) is int and value['schema'] == 1)
    need(value['mode'] == mode and value['status'] in ('FAIL', 'PENDING_RESOURCE_AND_NETWORK_REVIEW') and
         value['capacityQualified'] is False and value['cleanup'] == 'AWAIT_FINAL_RECORD')
    m = numbers(value['measurements'], STEADY_FIELDS if mode == 'steady' else LARGE_FIELDS)
    failures = numbers(value['rpcFailuresByKind'], FAILURE_KINDS)
    histogram(value['latencyBucketUpperMs'], m['dispatched'])
    need(type(value['latencyOverflowBucketMs']) is int and value['latencyOverflowBucketMs'] == 30001)
    rate = value['throughputResponsesPerSecond']
    duration = m['actualSchedulingNanos' if mode == 'steady' else 'actualDurationNanos']
    need(type(rate) in (int, float) and math.isfinite(rate) and duration > 0 and
         math.isclose(rate, m['completed'] * 1_000_000_000 / duration, rel_tol=1e-12))
    need(m['dispatched'] == m['completed'] + m['failed'] and sum(failures.values()) <= m['failed'])
    if mode == 'steady':
        # Even a missed slot records its scheduling delay; no empty histogram
        # sentinel may stand in for a complete 30-minute scheduling observation.
        histogram(value['schedulingDelayBucketUpperMs'], m['expected'])
        need(m['clients'] == 128 and m['callsPerSecondPerClient'] == 10 and m['expected'] == 2304000 and
             m['encodedRequestBytes'] == m['encodedResponseBytes'] == 1024 and
             m['requiredDurationNanos'] == 1800000000000 and m['actualSchedulingNanos'] >= m['requiredDurationNanos'])
        need(m['dispatched'] + m['missedDispatches'] == m['expected'] and
             m['missedDispatches'] == m['timerLate'] + m['permitUnavailable'] + m['workerLate'])
    else:
        need(m['expected'] == 20 and m['concurrency'] == 2 and
             m['encodedRequestBytes'] == m['encodedResponseBytes'] == 1048576)
    if value['status'] == 'PENDING_RESOURCE_AND_NETWORK_REVIEW':
        need(m['expected'] == m['dispatched'] == m['completed'] and m['failed'] == 0 and
             all(v == 0 for v in failures.values()))
        if mode == 'steady':
            need(all(m[k] == 0 for k in ('missedDispatches', 'outstandingAfterDrain', 'connectionChanges',
                                       'invalidHostSamples')) and
                 m['hostSamples'] >= 180 and m['hostAcceptedDelta'] == m['hostCompletedDelta'] == m['expected'])
    # Freshly serialized closed shape only, not the caller's arbitrary object graph.
    return json.loads(json.dumps(value, allow_nan=False))


def host_series(rows):
    need(type(rows) is list and 2 <= len(rows) <= 3000)
    for row in rows:
        numbers(row, HOST_FIELDS)
        need(row['residentBytes'] > 0 and row['nativeThreads'] > 0 and row['jvmThreads'] > 0)
        # The existing LabTelemetry/RpcLimits bounds, not new capacity thresholds.
        need(row['connected'] <= 128 and row['running'] <= 128 and row['queued'] <= 256 and
             row['records'] <= 131072 and row['payloadBytes'] <= 64 * 1048576)
    for a, b in zip(rows, rows[1:]):
        need(a['sequence'] < b['sequence'] and a['uptimeMillis'] < b['uptimeMillis'] and a['cpuNanos'] <= b['cpuNanos'])
        need(all(a[k] <= b[k] for k in ('accepted', 'completed', 'refused', 'duplicates', 'droppedNotifications',
                                      'protocolFailures', 'connectionFailures')))
    return {'samples': rows, 'observedMillis': rows[-1]['uptimeMillis'] - rows[0]['uptimeMillis'],
            'cpuNanosDelta': rows[-1]['cpuNanos'] - rows[0]['cpuNanos'],
            'maxima': {k: max(r[k] for r in rows) for k in
                       ('residentBytes', 'nativeThreads', 'jvmThreads', 'connected', 'running', 'queued', 'records', 'payloadBytes')},
            'includesProvisioningAndIdleRetention': True}


def file_hash(path):
    return hashlib.sha256(bounded(path)).hexdigest()


def snapshot(value):
    need(type(value) is dict and set(value) == {'cpuAffinityCount', 'memoryKiB', 'vmstat'})
    need(type(value['cpuAffinityCount']) is int and 1 <= value['cpuAffinityCount'] <= 4096)
    numbers(value['memoryKiB'], ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'))
    need(value['memoryKiB']['MemTotal'] > 0 and value['memoryKiB']['MemAvailable'] <= value['memoryKiB']['MemTotal'] and
         value['memoryKiB']['SwapFree'] <= value['memoryKiB']['SwapTotal'])
    need(type(value['vmstat']) is dict and set(value['vmstat']) <= {
        'balloon_inflate', 'balloon_deflate', 'pgscan_direct', 'pswpin', 'pswpout'})
    numbers(value['vmstat'], value['vmstat'].keys())
    return json.loads(json.dumps(value))


def clock_evidence(value):
    fields = {'scope', 'healthyForAttempt', 'periodNanos', 'durationNanos', 'kernelExpirations', 'userspaceReads',
              'coalescedExpirations', 'maximumGapNanos', 'minimumAvailableKiB', 'balloonInflateDelta', 'samples',
              'capacityQualified'}
    need(type(value) is dict and set(value) == fields and value['scope'] == 'INDEPENDENT_CLOCK_PREFLIGHT_NOT_CAPACITY' and
         type(value['healthyForAttempt']) is bool and value['capacityQualified'] is False)
    counts = fields - {'scope', 'healthyForAttempt', 'samples', 'capacityQualified'}
    numbers({k: value[k] for k in counts}, counts)
    need(value['periodNanos'] == 10000000 and value['durationNanos'] >= 125000000000 and
         value['kernelExpirations'] >= 12500 and value['userspaceReads'] > 0 and
         value['kernelExpirations'] == value['userspaceReads'] + value['coalescedExpirations'])
    samples = value['samples']
    need(type(samples) is list and 2 <= len(samples) <= 127)
    for row in samples:
        need(type(row) is dict and set(row) == {'elapsedNanos', 'cpuAffinityCount', 'memoryKiB', 'vmstat'} and
             type(row['elapsedNanos']) is int and 0 <= row['elapsedNanos'] <= value['durationNanos'])
        snapshot({k: v for k, v in row.items() if k != 'elapsedNanos'})
    need(samples[0]['elapsedNanos'] == 0 and all(a['elapsedNanos'] < b['elapsedNanos'] for a, b in zip(samples, samples[1:])) and
         value['minimumAvailableKiB'] == min(s['memoryKiB']['MemAvailable'] for s in samples) and
         value['balloonInflateDelta'] == samples[-1]['vmstat'].get('balloon_inflate', 0) - samples[0]['vmstat'].get('balloon_inflate', 0))
    healthy = value['maximumGapNanos'] < 100000000 and value['minimumAvailableKiB'] >= 6 * 1024 * 1024 and value['balloonInflateDelta'] == 0
    need(value['healthyForAttempt'] is healthy)
    return json.loads(json.dumps(value))


def clock_snapshot():
    """Linux-only read-only numeric observations; no interfaces, identities or command lines."""
    import os
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, rest = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
            memory[key] = int(rest.split()[0])
    vm = {}
    for line in Path('/proc/vmstat').read_text().splitlines():
        key, value = line.split()
        if key in ('balloon_inflate', 'balloon_deflate', 'pgscan_direct', 'pswpin', 'pswpout'):
            vm[key] = int(value)
    return snapshot({'cpuAffinityCount': len(os.sched_getaffinity(0)), 'memoryKiB': memory, 'vmstat': vm})


def clock_control():
    """125-second independent timer, never an RPC or capacity pass. Native owner required."""
    import ctypes
    import os
    import struct
    import time
    need(os.environ.get('P2PKIT_AUDIT_OWNERSHIP_CHAIN'))
    class Timespec(ctypes.Structure):
        _fields_ = [('seconds', ctypes.c_long), ('nanos', ctypes.c_long)]
    class Timerspec(ctypes.Structure):
        _fields_ = [('interval', Timespec), ('value', Timespec)]
    libc = ctypes.CDLL(None, use_errno=True)
    libc.timerfd_create.argtypes = [ctypes.c_int, ctypes.c_int]
    libc.timerfd_create.restype = ctypes.c_int
    libc.timerfd_settime.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(Timerspec), ctypes.c_void_p]
    libc.timerfd_settime.restype = ctypes.c_int
    fd = libc.timerfd_create(1, os.O_CLOEXEC)
    need(fd >= 0)
    start = previous = time.monotonic_ns()
    snapshots = [{'elapsedNanos': 0, **clock_snapshot()}]
    count = reads = maximum = 0
    try:
        timer = Timerspec(Timespec(0, 10000000), Timespec(0, 10000000))
        need(libc.timerfd_settime(fd, 0, ctypes.byref(timer), None) == 0)
        while previous - start < 125000000000:
            expirations = struct.unpack('Q', os.read(fd, 8))[0]
            now = time.monotonic_ns()
            maximum = max(maximum, now - previous)
            previous = now
            count += expirations
            reads += 1
            if now - start - snapshots[-1]['elapsedNanos'] >= 1000000000:
                snapshots.append({'elapsedNanos': now - start, **clock_snapshot()})
    finally:
        os.close(fd)
    minimum = min(s['memoryKiB']['MemAvailable'] for s in snapshots)
    balloon = snapshots[-1]['vmstat'].get('balloon_inflate', 0) - snapshots[0]['vmstat'].get('balloon_inflate', 0)
    # A conservative experiment prerequisite, not a relaxation or new product promise.
    healthy = maximum < 100000000 and minimum >= 6 * 1024 * 1024 and balloon == 0
    return {'scope': 'INDEPENDENT_CLOCK_PREFLIGHT_NOT_CAPACITY', 'healthyForAttempt': healthy,
            'periodNanos': 10000000, 'durationNanos': previous - start, 'kernelExpirations': count,
            'userspaceReads': reads, 'coalescedExpirations': count - reads, 'maximumGapNanos': maximum,
            'minimumAvailableKiB': minimum, 'balloonInflateDelta': balloon, 'samples': snapshots,
            'capacityQualified': False}
