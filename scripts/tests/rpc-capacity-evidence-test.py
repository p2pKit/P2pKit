#!/usr/bin/env python3
"""Offline parser controls only; never starts a timer, Java or a load test."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('capacity_evidence', ROOT / 'scripts/rpc_capacity_evidence.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def measurement(mode='steady'):
    fields = evidence.STEADY_FIELDS if mode == 'steady' else evidence.LARGE_FIELDS
    values = dict.fromkeys(fields, 0)
    if mode == 'steady':
        values.update(clients=128, callsPerSecondPerClient=10, expected=2304000, dispatched=2304000,
                      completed=2304000, encodedRequestBytes=1024, encodedResponseBytes=1024,
                      requiredDurationNanos=1800000000000, actualSchedulingNanos=1800000000000,
                      hostAcceptedDelta=2304000, hostCompletedDelta=2304000, hostSamples=1800)
    else:
        values.update(expected=20, dispatched=20, completed=20, concurrency=2, encodedRequestBytes=1048576,
                      encodedResponseBytes=1048576, actualDurationNanos=1000000000)
    result = {'schema': 1, 'mode': mode, 'status': 'PENDING_RESOURCE_AND_NETWORK_REVIEW',
              'capacityQualified': False, 'measurements': values, 'cleanup': 'AWAIT_FINAL_RECORD',
              'throughputResponsesPerSecond': 1280.0 if mode == 'steady' else 20.0,
              'latencyBucketUpperMs': {'p50': 2, 'p95': 5, 'p99': 8, 'max': 10},
              'latencyOverflowBucketMs': 30001, 'rpcFailuresByKind': dict.fromkeys(evidence.FAILURE_KINDS, 0)}
    if mode == 'steady':
        result['schedulingDelayBucketUpperMs'] = {'p50': 1, 'p95': 2, 'p99': 2, 'max': 10}
    return result


class EvidenceTest(unittest.TestCase):
    def test_read_only_environment_shape_rejects_arbitrary_or_inconsistent_values(self):
        value = {'cpuAffinityCount': 4, 'memoryKiB': {'MemTotal': 16000000, 'MemAvailable': 8000000,
                 'SwapTotal': 0, 'SwapFree': 0}, 'vmstat': {'balloon_inflate': 0}}
        self.assertEqual(evidence.snapshot(value), value)
        for change in ({'cpuAffinityCount': True}, {'cpuAffinityCount': 0}, {'private': 'never-export'},
                       {'vmstat': {'arbitrary': 0}}, {'memoryKiB': {**value['memoryKiB'], 'MemAvailable': 16000001}}):
            with self.assertRaises(ValueError):
                evidence.snapshot({**value, **change})

    def test_independent_clock_control_cannot_hide_coalescing_pressure_or_award_capacity(self):
        sample = {'cpuAffinityCount': 4, 'memoryKiB': {'MemTotal': 16000000, 'MemAvailable': 8000000,
                  'SwapTotal': 0, 'SwapFree': 0}, 'vmstat': {'balloon_inflate': 0}}
        value = {'scope': 'INDEPENDENT_CLOCK_PREFLIGHT_NOT_CAPACITY', 'healthyForAttempt': True,
                 'periodNanos': 10000000, 'durationNanos': 125000000000, 'kernelExpirations': 12500,
                 'userspaceReads': 12500, 'coalescedExpirations': 0, 'maximumGapNanos': 11000000,
                 'minimumAvailableKiB': 8000000, 'balloonInflateDelta': 0, 'capacityQualified': False,
                 'samples': [{'elapsedNanos': 0, **sample}, {'elapsedNanos': 124000000000, **sample}]}
        self.assertEqual(evidence.clock_evidence(value), value)
        for change in ({'scope': 'CAPACITY_PASS'}, {'capacityQualified': True}, {'healthyForAttempt': False},
                       {'maximumGapNanos': 100000000}, {'minimumAvailableKiB': 7000000},
                       {'durationNanos': 124999999999}, {'coalescedExpirations': 1}, {'balloonInflateDelta': 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                evidence.clock_evidence({**value, **change})
        failed = {**value, 'maximumGapNanos': 150000000, 'healthyForAttempt': False}
        self.assertEqual(evidence.clock_evidence(failed), failed)

    def test_full_mechanical_shape_does_not_award_qualification(self):
        for mode in ('steady', 'large'):
            self.assertEqual(measurement(mode), evidence.measurement(measurement(mode), mode))
            self.assertFalse(evidence.measurement(measurement(mode), mode)['capacityQualified'])

    def test_partial_duration_cannot_pass(self):
        value = measurement()
        value['measurements']['actualSchedulingNanos'] -= 1
        with self.assertRaises(ValueError):
            evidence.measurement(value, 'steady')

    def test_missed_slots_cannot_disappear_or_pass(self):
        value = measurement()
        values = value['measurements']
        values['completed'] -= 1
        values['dispatched'] -= 1
        values['missedDispatches'] = values['timerLate'] = 1
        values['hostAcceptedDelta'] -= 1
        values['hostCompletedDelta'] -= 1
        value['throughputResponsesPerSecond'] = values['completed'] / 1800
        with self.assertRaises(ValueError):
            evidence.measurement(value, 'steady')
        value['status'] = 'FAIL'
        self.assertEqual(value, evidence.measurement(value, 'steady'))
        values['timerLate'] = 0
        with self.assertRaises(ValueError):
            evidence.measurement(value, 'steady')

    def test_no_fabricated_latency_threshold_or_zero_peak_queue_rule(self):
        value = measurement()
        value['latencyBucketUpperMs'] = {'p50': 25, 'p95': 100, 'p99': 500, 'max': 1000}
        value['measurements']['sampledMaxHostQueue'] = 1
        self.assertEqual(value, evidence.measurement(value, 'steady'))
        # Resource time-series/retention review is still mandatory and separate.
        self.assertFalse(value['capacityQualified'])

    def test_empty_latency_sentinels_cannot_hide_missing_measurements(self):
        for mode in ('steady', 'large'):
            fields = ('latencyBucketUpperMs', 'schedulingDelayBucketUpperMs') if mode == 'steady' else ('latencyBucketUpperMs',)
            for field in fields:
                value = measurement(mode)
                value[field] = dict.fromkeys(('p50', 'p95', 'p99', 'max'), -1)
                with self.subTest(mode=mode, field=field), self.assertRaises(ValueError):
                    evidence.measurement(value, mode)
        empty = dict.fromkeys(('p50', 'p95', 'p99', 'max'), -1)
        self.assertEqual(evidence.histogram(empty, 0), empty)
        with self.assertRaises(ValueError):
            evidence.histogram({**empty, 'max': 0}, 0)

    def test_unknown_fields_booleans_bad_counters_and_claims_rejected(self):
        for path, bad in ((('secret',), 'never-export'), (('schema',), True),
                          (('capacityQualified',), True), (('measurements', 'completed'), True),
                          (('measurements', 'failed'), -1), (('measurements', 'dispatched'), 2**63),
                          (('rpcFailuresByKind', 'DeadlineExceeded'), 1),
                          (('throughputResponsesPerSecond',), float('nan')),
                          (('throughputResponsesPerSecond',), 1281),
                          (('latencyBucketUpperMs', 'p95'), 0)):
            value = measurement()
            target = value
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = bad
            with self.subTest(path=path), self.assertRaises(ValueError):
                evidence.measurement(value, 'steady')

    def test_large_has_exact_payloads_and_concurrency(self):
        for key, bad in (('concurrency', 1), ('encodedResponseBytes', 1024), ('expected', 19)):
            value = measurement('large')
            value['measurements'][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                evidence.measurement(value, 'large')

    def test_closed_host_series_retains_all_samples(self):
        first = dict.fromkeys(evidence.HOST_FIELDS, 0)
        first.update(sequence=1, uptimeMillis=10, cpuNanos=20, residentBytes=1024, nativeThreads=2, jvmThreads=1)
        second = {**first, 'sequence': 2, 'uptimeMillis': 1010, 'cpuNanos': 30, 'queued': 1}
        result = evidence.host_series([first, second])
        self.assertEqual(result['observedMillis'], 1000)
        self.assertEqual(result['cpuNanosDelta'], 10)
        self.assertEqual(result['maxima']['queued'], 1)
        self.assertEqual(result['samples'], [first, second])
        for key, bad in (('sequence', 1), ('cpuNanos', 10), ('connected', 129), ('queued', 257),
                         ('records', 131073), ('payloadBytes', 67108865), ('residentBytes', 0), ('token', 'private')):
            changed = {**second, key: bad}
            with self.subTest(key=key), self.assertRaises(ValueError):
                evidence.host_series([first, changed])

    def test_bounded_file_and_unique_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.json'
            path.write_text('{"schema":1,"schema":2}')
            with self.assertRaises(ValueError):
                evidence.read(path)
            path.write_text('{}')
            alias = Path(directory) / 'alias'
            alias.symlink_to(path)
            with self.assertRaises(ValueError):
                evidence.read(alias)
            with self.assertRaises(ValueError):
                evidence.read(path, maximum=1)
            self.assertEqual({}, evidence.read(path))


if __name__ == '__main__':
    unittest.main()
