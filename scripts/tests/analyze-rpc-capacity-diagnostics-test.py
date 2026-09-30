#!/usr/bin/env python3
"""Offline synthetic parser controls, never real-network or capacity evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('capacity_analysis', ROOT / 'scripts/analyze-rpc-capacity-diagnostics.py')
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


def fixtures():
    bins = []
    for second in range(a.SECONDS):
        row = dict.fromkeys(a.BIN_FIELDS, 0)
        row.update(scheduledSecond=second, Considered=1280, Enqueued=1280, WorkerStarted=1280,
                   Dispatched=1280, Completed=1280)
        bins.append(row)
    runtime = []
    for second in (0, 2, 1800):
        row = {key: 'WAITING' if key.endswith('State') else 0 for key in a.RUNTIME_FIELDS}
        row.update(elapsedNs=second * a.NS, uptimeMs=100_000 + second * 1000,
                   scanDirect=int(second > 0), selfMajorFaults=int(second > 0), availableKiB=1024)
        runtime.append(row)
    timing = (b'[0ns][info][gc] fixture\n'
              b'[101500000000ns][info][safepoint ] Safepoint "G1CollectForAllocation", Time since last: 0 ns, '
              b'Reaching safepoint: 10000000 ns, Cleanup: 0 ns, At safepoint: 190000000 ns, Total: 200000000 ns\n'
              b'[1901000000000ns][info][gc] fixture\n')
    return bins, runtime, timing


def client_log(bins, runtime):
    totals = {key: sum(row[key] for row in bins) for key in a.STAGES}
    measurements = {field: totals[stage] for field, stage in (
        ('expected', 'Considered'), ('dispatched', 'Dispatched'), ('completed', 'Completed'), ('failed', 'Failed'),
        ('timerLate', 'TimerLate'), ('permitUnavailable', 'PermitUnavailable'), ('workerLate', 'WorkerLate'))}
    measurements.update(missedDispatches=sum(totals[k] for k in ('TimerLate', 'PermitUnavailable', 'WorkerLate')),
                        actualSchedulingNanos=1800 * a.NS, outstandingAfterDrain=0)
    lines = ['scheduleEpoch,monotonicNanos=987654321,uptimeMs=100000']
    for prefix, fields, rows in (('runtime,', a.RUNTIME_FIELDS, runtime), ('scheduleBins,', a.BIN_FIELDS, bins)):
        lines.append(prefix + ','.join(fields))
        lines.extend(prefix + ','.join(str(row[key]) for key in fields) for row in rows)
    lines.append('RPC_CAPACITY_RESULT_JSON:' + json.dumps(
        dict(mode='steady', capacityQualified=False, measurements=measurements)))
    return ('\n'.join(lines) + '\n').encode()


def misses(row, timer, permit, worker):
    row.update(TimerLate=timer, PermitUnavailable=permit, WorkerLate=worker,
               Enqueued=1280 - timer - permit, WorkerStarted=1280 - timer - permit,
               Dispatched=1280 - timer - permit - worker, Completed=1280 - timer - permit - worker)


class AnalysisControls(unittest.TestCase):
    def test_rotation_record_allowance_is_bounded_and_shared_with_hosted_reader(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'jvm-timing.log'
            # Real unified-log rotation occurs after a record is written.
            # Sparse fixture checks the boundary without any Java execution.
            with path.open('wb') as stream:
                stream.truncate(8 * 1024 * 1024 + 512)
            self.assertEqual(len(a.read_timings([path])[0]), 8 * 1024 * 1024 + 512)
            with path.open('wb') as stream:
                stream.truncate(a.JVM_TIMING_MAX_BYTES + 1)
            with self.assertRaises(ValueError):
                a.read_timings([path])
            path.write_bytes(b'fixture')
            alias = Path(name) / 'alias'
            alias.symlink_to(path)
            for invalid in ([], [path, path], [alias], [Path(name) / str(i) for i in range(6)]):
                with self.subTest(paths=invalid), self.assertRaises(ValueError):
                    a.read_timings(invalid)
        hosted = (ROOT / 'scripts/run-rpc-capacity-qualification.py').read_text()
        self.assertIn("analyzer.read_timings(sorted(client_dir.glob('jvm-timing.log*')))", hosted)

    def test_all_unsent_stages_reconcile_and_never_become_rpc_failures(self):
        bins, runtime, timing = fixtures()
        misses(bins[1], 100, 20, 30)
        result = a.analyze(client_log(bins, runtime), [timing])
        self.assertEqual(result['missedSlots'], 150)
        self.assertEqual(result['slotTotals']['Failed'], 0)
        self.assertEqual(result['slotTotals']['Dispatched'], 2_304_000 - 150)
        self.assertEqual(result['sampleWindowCorrelation']['reclaimOrLongSafepoint']['missesInOverlappingBins'], 150)
        self.assertFalse(result['capacityQualified'])

    def test_unassociated_misses_are_not_concealed_or_attributed_to_reclaim(self):
        bins, runtime, timing = fixtures()
        misses(bins[1], 30, 0, 0)
        misses(bins[10], 20, 0, 10)
        result = a.analyze(client_log(bins, runtime), [timing])
        self.assertEqual(result['sampleWindowCorrelation']['missesOutsideReclaimOrLongSafepointBins'], 30)
        self.assertEqual(result['safepoints']['maximumTotalNs'], 200_000_000)
        self.assertEqual(result['safepoints']['maximumReachingNs'], 10_000_000)

    def test_complete_diagnostics_still_never_admit_capacity_or_export_payloads(self):
        bins, runtime, timing = fixtures()
        raw = client_log(bins, runtime) + b'private payload and identity=must-not-leave\n'
        result = a.analyze(raw, [timing])
        self.assertFalse(result['capacityQualified'])
        self.assertEqual(result['missedSlots'], 0)
        self.assertNotIn('must-not-leave', json.dumps(result))

    def test_missing_duplicate_and_unbalanced_slots_are_refused(self):
        bins, runtime, timing = fixtures()
        for broken in (bins[:-1], bins + [bins[0]], copy.deepcopy(bins)):
            if len(broken) == 1800:
                broken[0]['Enqueued'] -= 1
            with self.assertRaises(ValueError):
                a.analyze(client_log(broken, runtime), [timing])

    def test_partial_duplicate_or_unrecognized_jvm_timing_is_refused(self):
        bins, runtime, timing = fixtures()
        raw = client_log(bins, runtime)
        for files in ([timing, timing], [b'private missing timing'],
                      [timing.replace(b'1901000000000ns', b'103000000000ns')]):
            with self.assertRaises(ValueError):
                a.analyze(raw, files)

    def test_counter_reset_and_incomplete_observer_are_refused(self):
        bins, runtime, timing = fixtures()
        for broken in (runtime[:-1], copy.deepcopy(runtime)):
            if len(broken) == 3:
                broken[-1]['scanDirect'] = 0
            with self.assertRaises(ValueError):
                a.analyze(client_log(bins, broken), [timing])

    def test_unknown_state_other_modes_and_qualification_claim_are_refused(self):
        bins, runtime, timing = fixtures()
        raw = client_log(bins, runtime)
        for bad in (raw.replace(b'WAITING', b'private-secret'), raw.replace(b'"steady"', b'"large"'),
                    raw.replace(b'"capacityQualified": false', b'"capacityQualified": true')):
            with self.assertRaises(ValueError):
                a.analyze(bad, [timing])


if __name__ == '__main__':
    unittest.main(verbosity=2)
