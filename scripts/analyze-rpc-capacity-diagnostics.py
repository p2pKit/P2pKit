#!/usr/bin/env python3
"""Offline, bounded diagnostic correlation. NEVER capacity, source or ownership admission.

Inputs remain private. Output contains fixed numeric fields and input hashes only.
Sample-window overlap is correlation at one-second resolution, not per-call causality.
Validate the original workload/source/cleanup receipts separately before citing it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

SECONDS = 1800
PER_SECOND = 1280
NS = 1_000_000_000
# JVM rotates after writing a record, so an 8-MiB rotation may exceed 8 MiB.
# Keep the original bounded 9-MiB allowance identical in both evidence readers.
JVM_TIMING_MAX_BYTES = 9 * 1024 * 1024
STAGES = ('Considered', 'TimerLate', 'PermitUnavailable', 'Enqueued', 'WorkerStarted',
          'WorkerLate', 'Dispatched', 'Completed', 'Failed')
BIN_FIELDS = ('scheduledSecond', *STAGES, 'maxTimerDelayNs', 'maxWorkerQueueNs', 'lastObservedElapsedNs')
RUNTIME_FIELDS = ('elapsedNs', 'uptimeMs', 'sampleGapNs', 'cpuNs', 'heapBytes', 'clockLagNs',
                  'clockCpuNs', 'clockState', 'workerThreads', 'runnableWorkers', 'workerCpuNs',
                  'defaultTimerCpuNs', 'defaultTimerState', 'selfMinorFaults', 'selfMajorFaults',
                  'availableKiB', 'scanDirect', 'scanKswapd', 'allocstall', 'stealJiffies',
                  'balloonInflate', 'balloonDeflate', 'balloonMigrate')
STATES = {'NEW', 'RUNNABLE', 'BLOCKED', 'WAITING', 'TIMED_WAITING', 'TERMINATED', 'ABSENT'}
SAFEPOINT = re.compile(
    r'\[([0-9]+)ns\].*\[safepoint\s*\] Safepoint "[A-Za-z0-9_]+", Time since last: [0-9]+ ns, '
    r'Reaching safepoint: ([0-9]+) ns, Cleanup: ([0-9]+) ns, At safepoint: ([0-9]+) ns, Total: ([0-9]+) ns$')


def need(condition):
    if not condition:
        raise ValueError('Incomplete or inconsistent capacity diagnostics; no qualification inferred')


def bounded(path, maximum):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum)
    with path.open('rb') as stream:
        data = stream.read(maximum + 1)
    need(len(data) <= maximum)
    return data


def read_timings(paths):
    need(1 <= len(paths) <= 5 and len(set(paths)) == len(paths))
    return [bounded(path, JVM_TIMING_MAX_BYTES) for path in paths]


def table(lines, prefix, fields):
    selected = [line[len(prefix):].split(',') for line in lines if line.startswith(prefix)]
    need(selected and selected[0] == list(fields) and len(selected) <= 2401)
    result = []
    for values in selected[1:]:
        need(len(values) == len(fields))
        row = {}
        for key, value in zip(fields, values):
            if key.endswith('State'):
                need(value in STATES)
                row[key] = value
            else:
                need(re.fullmatch(r'-?[0-9]{1,19}', value) is not None)
                row[key] = int(value)
                need(row[key] >= (-1 if prefix == 'runtime,' else 0))
        result.append(row)
    return result


def verify_bins(bins, measurements):
    need(len(bins) == SECONDS and [b['scheduledSecond'] for b in bins] == list(range(SECONDS)))
    for b in bins:
        need(b['Considered'] == PER_SECOND)
        need(b['Considered'] == b['TimerLate'] + b['PermitUnavailable'] + b['Enqueued'])
        need(b['Enqueued'] == b['WorkerStarted'] == b['WorkerLate'] + b['Dispatched'])
        need(b['Dispatched'] == b['Completed'] + b['Failed'])
    totals = {name: sum(b[name] for b in bins) for name in STAGES}
    for field, stage in (('expected', 'Considered'), ('dispatched', 'Dispatched'), ('completed', 'Completed'),
                         ('failed', 'Failed'), ('timerLate', 'TimerLate'),
                         ('permitUnavailable', 'PermitUnavailable'), ('workerLate', 'WorkerLate')):
        need(type(measurements.get(field)) is int and measurements[field] == totals[stage])
    need(measurements['missedDispatches'] == sum(totals[k] for k in ('TimerLate', 'PermitUnavailable', 'WorkerLate')))
    need(measurements['actualSchedulingNanos'] >= SECONDS * NS and measurements['outstandingAfterDrain'] == 0)
    return totals


def overlap(bins, intervals):
    inside = [b for b in bins if any(b['scheduledSecond'] * NS < end and
                                    (b['scheduledSecond'] + 1) * NS > start for start, end in intervals)]
    return {'overlappingScheduledSeconds': len(inside),
            'missesInOverlappingBins': sum(b[k] for b in inside for k in ('TimerLate', 'PermitUnavailable', 'WorkerLate'))}


def analyze(client_raw, timing_raws):
    lines = client_raw.decode().splitlines()
    bins = table(lines, 'scheduleBins,', BIN_FIELDS)
    runtime = table(lines, 'runtime,', RUNTIME_FIELDS)
    need(2 <= len(runtime) <= 2400)
    need(0 <= runtime[0]['elapsedNs'] < 5 * NS and runtime[-1]['elapsedNs'] >= (SECONDS - 5) * NS)
    need(all(a['elapsedNs'] < b['elapsedNs'] and a['uptimeMs'] <= b['uptimeMs'] for a, b in zip(runtime, runtime[1:])))
    for field in ('cpuNs', 'clockCpuNs', 'selfMinorFaults', 'selfMajorFaults', 'scanDirect', 'scanKswapd',
                  'allocstall', 'stealJiffies', 'balloonInflate', 'balloonDeflate', 'balloonMigrate'):
        need(all(a[field] <= b[field] for a, b in zip(runtime, runtime[1:])))
    records = [json.loads(line.removeprefix('RPC_CAPACITY_RESULT_JSON:')) for line in lines
               if line.startswith('RPC_CAPACITY_RESULT_JSON:')]
    need(len(records) == 1 and records[0].get('mode') == 'steady' and records[0].get('capacityQualified') is False)
    measurements = records[0]['measurements']
    totals = verify_bins(bins, measurements)
    epochs = [re.fullmatch(r'scheduleEpoch,monotonicNanos=([0-9]+),uptimeMs=([0-9]+)', line)
              for line in lines if line.startswith('scheduleEpoch,')]
    need(len(epochs) == 1 and epochs[0] is not None)
    origin_uptime = int(epochs[0][2]) * 1_000_000
    # Counters are sampled after elapsedNs, before uptimeMs is printed. Use that
    # enclosing sample interval, not a file-copy timestamp or exact event time.
    pressure = []
    process_faults = []
    for previous, row in zip(runtime, runtime[1:]):
        end = max(row['elapsedNs'], row['uptimeMs'] * 1_000_000 - origin_uptime)
        interval = (previous['elapsedNs'], end)
        if previous['scanDirect'] >= 0 and row['scanDirect'] > previous['scanDirect']:
            pressure.append(interval)
        if previous['selfMajorFaults'] >= 0 and row['selfMajorFaults'] > previous['selfMajorFaults']:
            process_faults.append(interval)
    safepoints = []
    first_uptime, last_uptime = [], []
    for raw in timing_raws:
        stamps = [int(v) for v in re.findall(rb'\[([0-9]+)ns\]', raw)]
        need(stamps)
        first_uptime.append(min(stamps))
        last_uptime.append(max(stamps))
        for line in raw.decode().splitlines():
            match = SAFEPOINT.search(line)
            if match:
                end, reaching, cleanup, stopped, total = map(int, match.groups())
                need(reaching + cleanup + stopped == total)
                if origin_uptime < end <= origin_uptime + measurements['actualSchedulingNanos']:
                    safepoints.append((end - origin_uptime - total, end - origin_uptime, reaching, stopped, total))
    need(safepoints and len(safepoints) == len(set(safepoints)) and min(first_uptime) <= origin_uptime and
         max(last_uptime) >= origin_uptime + measurements['actualSchedulingNanos'])
    long_safepoints = [(s[0], s[1]) for s in safepoints if s[4] >= NS // 10]
    union = pressure + long_safepoints
    associated = overlap(bins, union)
    missed = measurements['missedDispatches']
    runtime_max = ('sampleGapNs', 'clockLagNs', 'heapBytes', 'workerThreads', 'runnableWorkers')
    deltas = ('cpuNs', 'clockCpuNs', 'selfMinorFaults', 'selfMajorFaults', 'scanDirect', 'scanKswapd',
              'allocstall', 'stealJiffies', 'balloonInflate', 'balloonDeflate', 'balloonMigrate')
    return {'schema': 1, 'scope': 'DIAGNOSTIC_CORRELATION_NOT_QUALIFICATION', 'capacityQualified': False,
            'slotTotals': totals, 'scheduledSeconds': len(bins), 'missedSlots': missed,
            'maximumTimerDelayNs': max(b['maxTimerDelayNs'] for b in bins),
            'maximumWorkerQueueNs': max(b['maxWorkerQueueNs'] for b in bins),
            'runtimeSamples': len(runtime), 'runtimeMaxima': {k: max(r[k] for r in runtime) for k in runtime_max},
            'runtimeCounterDeltas': {k: runtime[-1][k] - runtime[0][k] if runtime[0][k] >= 0 else None for k in deltas},
            'availableKiBRange': [min(r['availableKiB'] for r in runtime), max(r['availableKiB'] for r in runtime)],
            'safepoints': {'count': len(safepoints), 'atLeast100ms': len(long_safepoints),
                           'maximumTotalNs': max(s[4] for s in safepoints),
                           'maximumReachingNs': max(s[2] for s in safepoints),
                           'maximumStoppedNs': max(s[3] for s in safepoints)},
            'sampleWindowCorrelation': {'guestDirectReclaim': overlap(bins, pressure),
                                        'clientMajorFaults': overlap(bins, process_faults),
                                        'safepointsAtLeast100ms': overlap(bins, long_safepoints),
                                        'reclaimOrLongSafepoint': associated,
                                        'missesOutsideReclaimOrLongSafepointBins': missed - associated['missesInOverlappingBins']},
            'inputSha256': {'client': hashlib.sha256(client_raw).hexdigest(),
                            'jvmTiming': sorted(hashlib.sha256(raw).hexdigest() for raw in timing_raws)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-log', type=Path, required=True)
    parser.add_argument('--jvm-timing', type=Path, nargs='+', required=True,
                        help='All retained JVM unified-log rotations, including the current file')
    parser.add_argument('--output', type=Path, required=True, help='New private aggregate; never overwrites evidence')
    args = parser.parse_args()
    result = analyze(bounded(args.client_log, 8 * 1024 * 1024),
                     read_timings(args.jvm_timing))
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
