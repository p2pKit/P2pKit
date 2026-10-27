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


def measurement(mode='steady', clients=128, schema=1):
    fields = evidence.STEADY_FIELDS if mode == 'steady' else evidence.LARGE_FIELDS
    values = dict.fromkeys(fields, 0)
    if mode == 'steady':
        expected = clients * 18000
        values.update(clients=clients, callsPerSecondPerClient=10, expected=expected, dispatched=expected,
                      completed=expected, encodedRequestBytes=1024, encodedResponseBytes=1024,
                      requiredDurationNanos=1800000000000, actualSchedulingNanos=1800000000000,
                      hostAcceptedDelta=expected, hostCompletedDelta=expected, hostSamples=1800)
    else:
        values.update(expected=20, dispatched=20, completed=20, concurrency=2, encodedRequestBytes=1048576,
                      encodedResponseBytes=1048576, actualDurationNanos=1000000000)
    result = {'schema': schema, 'mode': mode, 'status': 'PENDING_RESOURCE_AND_NETWORK_REVIEW',
              'capacityQualified': False, 'measurements': values, 'cleanup': 'AWAIT_FINAL_RECORD',
              'throughputResponsesPerSecond': clients * 10.0 if mode == 'steady' else 20.0,
              'latencyBucketUpperMs': {'p50': 2, 'p95': 5, 'p99': 8, 'max': 10},
              'latencyOverflowBucketMs': 30001, 'rpcFailuresByKind': dict.fromkeys(evidence.FAILURE_KINDS, 0)}
    if mode == 'steady':
        result['schedulingDelayBucketUpperMs'] = {'p50': 1, 'p95': 2, 'p99': 2, 'max': 10}
    if schema == 2:
        result['clientCount'] = clients
    return result


def initialization(clients=128, schema=1):
    m = dict.fromkeys(evidence.INITIALIZATION_FIELDS, 0)
    expected = clients * 600
    m.update(clients=clients, callsPerClient=600, minimumCallPeriodNanos=100000000, callPhaseTimeoutMillis=120000,
             encodedRequestBytes=1024, encodedResponseBytes=1024, expected=expected, dispatched=expected,
             completed=expected, actualDurationNanos=61000000000, driverCompilationMillisAfter=2000)
    h = dict.fromkeys(evidence.INITIALIZATION_HOST_FIELDS, 0)
    h.update(acceptedAfter=expected, completedAfter=expected, connectedAfter=clients, uptimeMillisDelta=61000)
    result = dict(schema=schema, scope='FIXED_RPC_PATH_INITIALIZATION_NOT_CAPACITY_OR_COLD_START_QUALIFICATION',
                status='INITIALIZED_NOT_CAPACITY', capacityQualified=False, measurements=m, hostObservation=h,
                latencyBucketUpperMs={'p50': 5, 'p95': 20, 'p99': 200, 'max': 2000},
                rpcFailuresByKind=dict.fromkeys(evidence.FAILURE_KINDS, 0))
    if schema == 2:
        result['clientCount'] = clients
    return result


def exercise(mode='correctness', clients=256):
    cases = evidence.CORRECTNESS_CASES if mode == 'correctness' else evidence.CHURN_CASES
    expected_echo = clients * 3 + 5 if mode == 'correctness' else clients * 5
    values = dict.fromkeys(evidence.CONTROL_FIELDS, 0)
    values.update(clients=clients, expectedEchoResponses=expected_echo, echoResponses=expected_echo,
                  actualDurationNanos=20000000000, hostConnectionsBefore=clients, hostConnectionsAfter=clients)
    if mode == 'correctness':
        values.update(concurrentEchoResponses=clients * 2, applicationErrors=1, authorizationRefusals=1,
            sentDeadlineFailures=1, sentCancellations=1, disconnectUnknownOutcomes=1, holdEntered=3, holdRetired=3,
            slowHandlerResponses=16, fairnessEchoResponses=1, disconnects=1, reconnects=1)
    else:
        values.update(churnRounds=5, disconnects=clients * 5, reconnects=clients * 5)
    return dict(schema=2, clientCount=clients, mode=mode, scope='REAL_AUTHENTICATED_RPC_CONTROLS_NOT_CAPACITY',
                status='PENDING_RESOURCE_AND_NETWORK_REVIEW', capacityQualified=False,
                expectedCases=list(cases), passedCases=list(cases), failureCase=None, measurements=values,
                trueSlowConsumerQualified=False, cleanup='AWAIT_FINAL_RECORD')


def connected_idle(clients=256):
    rows = []
    for index in range(7):
        row = dict.fromkeys(evidence.IDLE_SAMPLE_FIELDS, 0)
        row.update(uptimeMillis=10000 + index * 5000, cpuNanos=1000000 + index * 1000000,
                   residentBytes=32 * 1048576, nativeThreads=24, connected=clients,
                   accepted=clients * 600, completed=clients * 600, driverElapsedNanos=index * 5000000000,
                   driverCpuNanos=2000000 + index * 500000)
        rows.append(row)
    m = dict.fromkeys(evidence.IDLE_FIELDS, 0)
    m.update(clients=clients, sampleCount=7, actualDurationNanos=40000000000, actualSettleNanos=10000000000,
             hostUptimeDeltaMillis=30000, hostCpuDeltaNanos=6000000, driverElapsedNanos=30000000000,
             driverCpuDeltaNanos=3000000, sampledMinHostRssBytes=32 * 1048576,
             sampledMaxHostRssBytes=32 * 1048576, sampledMinHostThreads=24, sampledMaxHostThreads=24,
             hostConnectionsBefore=clients, hostConnectionsAfter=clients)
    return dict(schema=2, clientCount=clients, sourceSha='a' * 40, runLabel='idle-control', hostPlatform='Ios',
                hostArtifactSha256='b' * 64, driverArtifactSha256='c' * 64,
                scope='CONNECTED_IDLE_RESOURCE_OBSERVATION_NOT_CAPACITY', status='OBSERVED_CONNECTED_IDLE_NOT_CAPACITY',
                capacityQualified=False, settleMillis=10000, requiredHostIdleMillis=30000, failureStage=None,
                measurements=m, samples=rows)


def profile():
    return dict(schema=1, scope='BOUNDED_JFR_SAMPLES_AND_CPU_LOAD_NOT_CAPACITY', capacityQualified=False,
        role='client', sourceSha='a' * 40, recordingSha256='b' * 64, configuredDelaySeconds=120,
        configuredDurationSeconds=180, samplingPeriodMillis=20, waitThresholdMillis=20,
        firstEventEpochMillis=1800000000000, lastEventEpochMillis=1800000180000, totalEvents=3, ignoredEvents=1,
        truncatedStacks=0, cpuLoad={'samples': 1, 'sumPpm': {'jvmUser': 200000, 'jvmSystem': 50000, 'machineTotal': 950000},
                                  'maximumPpm': {'jvmUser': 200000, 'jvmSystem': 50000, 'machineTotal': 950000}},
        events={'ExecutionSample': {'LanInterfaceEnumeration': {'count': 1, 'durationNanos': 0,
        'maximumDurationNanos': 0}}, 'NativeMethodSample': {}, 'ThreadPark': {}, 'JavaMonitorEnter': {}})


class EvidenceTest(unittest.TestCase):
    def test_connected_idle_is_source_bound_and_separate_from_initialization_and_steady(self):
        for clients in (128, 256):
            value = connected_idle(clients)
            self.assertEqual(value, evidence.connected_idle(value, client_count=clients))
            self.assertFalse(value['capacityQualified'])
            with self.assertRaises(ValueError):
                evidence.initialization(value, client_count=clients)
            with self.assertRaises(ValueError):
                evidence.measurement(value, 'steady', client_count=clients)
            with self.assertRaises(ValueError):
                evidence.connected_idle(value, client_count=384 - clients)

    def test_connected_idle_rejects_missing_binding_noncanonical_counts_and_private_fields(self):
        for path, changed in ((('schema',), 1), (('clientCount',), True), (('clientCount',), '256'),
                              (('capacityQualified',), True), (('scope',), 'CAPACITY'), (('private',), 'do-not-export'),
                              (('hostPlatform',), 'iphone'), (('sourceSha',), 'current'), (('runLabel',), 'local user'),
                              (('hostArtifactSha256',), 'b' * 63), (('driverArtifactSha256',), 'c' * 65),
                              (('settleMillis',), 0), (('requiredHostIdleMillis',), 29000),
                              (('measurements', 'hostCpuDeltaNanos'), True),
                              (('measurements', 'private'), 0), (('measurements', 'sampleCount'), 6)):
            value = connected_idle()
            target = value
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = changed
            with self.subTest(path=path), self.assertRaises(ValueError):
                evidence.connected_idle(value, client_count=256)
        for field in ('sourceSha', 'hostArtifactSha256', 'driverArtifactSha256', 'samples'):
            value = connected_idle()
            del value[field]
            with self.assertRaises(ValueError):
                evidence.connected_idle(value, client_count=256)

    def test_connected_idle_requires_full_cohort_and_no_intervening_work_or_state_change(self):
        for field, changed in (('connected', 255), ('running', 1), ('queued', 1), ('accepted', 153601),
                               ('completed', 153601), ('refused', 1), ('duplicates', 1), ('droppedNotifications', 1),
                               ('protocolFailures', 1), ('connectionFailures', 1), ('nativeThreads', 0),
                               ('residentBytes', 0), ('private', 0)):
            value = connected_idle()
            value['samples'][3][field] = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence.connected_idle(value, client_count=256)
        for field in ('connectionChanges', 'invalidHostSamples'):
            value = connected_idle()
            value['measurements'][field] = 1
            with self.assertRaises(ValueError):
                evidence.connected_idle(value, client_count=256)

    def test_idle_duration_cannot_be_fabricated_from_driver_time_or_uncrossbound_summaries(self):
        for field, changed in (('hostUptimeDeltaMillis', 29999), ('hostCpuDeltaNanos', 6000001),
                               ('driverCpuDeltaNanos', 2999999), ('sampledMaxHostRssBytes', 32 * 1048576 + 1),
                               ('sampledMinHostThreads', 23), ('actualSettleNanos', 9999999999),
                               ('actualDurationNanos', 39999999999), ('hostAcceptedDelta', 1)):
            value = connected_idle()
            value['measurements'][field] = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence.connected_idle(value, client_count=256)
        value = connected_idle()
        for index, row in enumerate(value['samples']):
            row['uptimeMillis'] = 10000 + index * 4000
        value['measurements']['hostUptimeDeltaMillis'] = 24000
        with self.assertRaises(ValueError):
            evidence.connected_idle(value, client_count=256)
        value = connected_idle()
        value['samples'] = [value['samples'][0], value['samples'][-1]]
        value['samples'][1]['driverElapsedNanos'] = 5000000000
        value['measurements'].update(sampleCount=2, driverElapsedNanos=5000000000, actualDurationNanos=15000000000)
        with self.assertRaises(ValueError):
            evidence.connected_idle(value, client_count=256)

    def test_idle_counter_regression_remains_exportable_failed_evidence_not_zero_clamping(self):
        value = connected_idle()
        value.update(status='FAIL', failureStage='observe')
        value['samples'] = value['samples'][:2]
        value['samples'][1]['cpuNanos'] = 900000
        value['measurements'].update(sampleCount=2, hostUptimeDeltaMillis=5000, hostCpuDeltaNanos=-100000,
            driverElapsedNanos=5000000000, driverCpuDeltaNanos=500000, actualDurationNanos=15000000000,
            invalidHostSamples=1)
        self.assertEqual(value, evidence.connected_idle(value, client_count=256))
        value.update(status='OBSERVED_CONNECTED_IDLE_NOT_CAPACITY', failureStage=None)
        with self.assertRaises(ValueError):
            evidence.connected_idle(value, client_count=256)

    def test_host_thirty_seconds_with_only_twenty_five_seconds_of_registered_observation_cannot_pass(self):
        value = connected_idle()
        value['samples'] = value['samples'][:6]
        for index, row in enumerate(value['samples']):
            row['uptimeMillis'] = 10000 + index * 6000
        value['measurements'].update(sampleCount=6, hostUptimeDeltaMillis=30000, driverElapsedNanos=25000000000,
                                     actualDurationNanos=35000000000, hostCpuDeltaNanos=5000000,
                                     driverCpuDeltaNanos=2500000)
        with self.assertRaises(ValueError):
            evidence.connected_idle(value, client_count=256)
        # Retain the actual shorter record as failure; do not erase or pretend that observation took 30 seconds.
        value.update(status='FAIL', failureStage='validation')
        self.assertEqual(value, evidence.connected_idle(value, client_count=256))

    def test_missing_idle_telemetry_stays_a_failed_empty_sample_set(self):
        value = connected_idle()
        value.update(status='FAIL', failureStage='baseline', samples=[])
        value['measurements'] = dict.fromkeys(evidence.IDLE_FIELDS, 0)
        value['measurements'].update(clients=256, actualSettleNanos=10000000000, actualDurationNanos=15000000000)
        self.assertEqual(value, evidence.connected_idle(value, client_count=256))
        value['failureStage'] = None
        with self.assertRaises(ValueError):
            evidence.connected_idle(value, client_count=256)

    def test_real_control_rosters_and_exact_outcomes_remain_distinct_from_steady_capacity(self):
        for clients in (128, 256):
            for mode in ('correctness', 'churn'):
                value = exercise(mode, clients)
                self.assertEqual(value, evidence.exercise(value, mode, client_count=clients))
                self.assertFalse(value['capacityQualified'])
                self.assertFalse(value['trueSlowConsumerQualified'])
                with self.assertRaises(ValueError):
                    evidence.measurement(value, 'steady', client_count=clients)

    def test_control_success_requires_full_cohort_and_every_exact_typed_outcome(self):
        for mode in ('correctness', 'churn'):
            original = exercise(mode)
            checked = ('echoResponses', 'hostConnectionsBefore', 'hostConnectionsAfter')
            if mode == 'correctness':
                checked += ('concurrentEchoResponses', 'applicationErrors', 'authorizationRefusals',
                    'sentDeadlineFailures', 'sentCancellations', 'disconnectUnknownOutcomes', 'holdEntered',
                    'holdRetired', 'slowHandlerResponses', 'fairnessEchoResponses', 'disconnects', 'reconnects')
            else:
                checked += ('churnRounds', 'disconnects', 'reconnects')
            for field in checked:
                value = copy.deepcopy(original)
                value['measurements'][field] -= 1
                with self.subTest(mode=mode, field=field), self.assertRaises(ValueError):
                    evidence.exercise(value, mode, client_count=256)
            for changed in ({'passedCases': original['passedCases'][:-1]}, {'failureCase': original['expectedCases'][0]},
                            {'expectedCases': original['expectedCases'][:-1]}, {'trueSlowConsumerQualified': True},
                            {'capacityQualified': True}, {'clientCount': '256'}, {'private': 'do-not-export'}):
                with self.assertRaises(ValueError):
                    evidence.exercise(original | changed, mode, client_count=256)

    def test_failed_controls_preserve_partial_records_without_fake_passes_or_reordered_case_lists(self):
        value = exercise()
        value.update(status='FAIL', passedCases=value['passedCases'][:4], failureCase='sent-deadline')
        value['measurements'].update(sentDeadlineFailures=0, sentCancellations=0, disconnectUnknownOutcomes=0,
            holdEntered=1, holdRetired=1, slowHandlerResponses=0, fairnessEchoResponses=0,
            disconnects=0, reconnects=0, hostConnectionsAfter=0)
        self.assertEqual(value, evidence.exercise(value, 'correctness', client_count=256))
        for changed in ({'passedCases': ['sent-deadline']}, {'failureCase': 'raw-local-message'},
                        {'schema': 1}, {'clientCount': True}):
            with self.assertRaises(ValueError):
                evidence.exercise(value | changed, 'correctness', client_count=256)

    def test_schema2_requires_explicit_matching_integer_cohort_and_accounts_every_call(self):
        for clients in (128, 256):
            for mode in ('steady', 'large'):
                value = measurement(mode, clients, schema=2)
                self.assertEqual(value, evidence.measurement(value, mode, client_count=clients))
                with self.assertRaises(ValueError):
                    evidence.measurement(value, mode, client_count=384 - clients)
            initial = initialization(clients, schema=2)
            self.assertEqual(initial, evidence.initialization(initial, client_count=clients))
            self.assertEqual(initial['measurements']['expected'], clients * 600)
            self.assertEqual(measurement(clients=clients, schema=2)['measurements']['expected'], clients * 18000)

    def test_legacy_schema_cannot_be_used_to_admit256_or_infer_a_new_profile(self):
        for mode in ('steady', 'large'):
            with self.assertRaises(ValueError):
                evidence.measurement(measurement(mode, clients=256), mode, client_count=256)
            with self.assertRaises(ValueError):
                evidence.measurement(measurement(mode, clients=256, schema=2), mode)
        with self.assertRaises(ValueError):
            evidence.initialization(initialization(256), client_count=256)
        with self.assertRaises(ValueError):
            evidence.initialization(initialization(256, schema=2))

    def test_schema2_profile_cannot_use_strings_boolean_counts_extra_fields_or_incomplete_workload(self):
        for bad in ('256', True, 128, 512, 256.0):
            value = measurement(clients=256, schema=2)
            value['clientCount'] = bad
            with self.assertRaises(ValueError):
                evidence.measurement(value, 'steady', client_count=256)
        for path, changed in ((('measurements', 'expected'), 2304000),
                              (('measurements', 'clients'), 128), (('schema',), 1),
                              (('private',), 'no-export'), (('schema',), True)):
            value = measurement(clients=256, schema=2)
            target = value
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = changed
            with self.assertRaises(ValueError):
                evidence.measurement(value, 'steady', client_count=256)
        for clients in (True, '256', 512, 127):
            with self.assertRaises(ValueError):
                evidence.initialization(initialization(256, schema=2), client_count=clients)

    def test_profile_counts_are_source_bound_and_cannot_be_substituted_for_capacity(self):
        value = profile()
        self.assertEqual(evidence.runtime_profile(value, 'client', 'a' * 40, 'b' * 64), value)
        for role, source, digest in (('host', 'a' * 40, 'b' * 64), ('client', 'c' * 40, 'b' * 64),
                                     ('client', 'a' * 40, 'c' * 64)):
            with self.assertRaises(ValueError):
                evidence.runtime_profile(value, role, source, digest)
        for mode in ('steady', 'large'):
            with self.assertRaises(ValueError):
                evidence.measurement(value, mode)

    def test_profile_privacy_bounds_and_conservation_are_not_just_schema_checks(self):
        for path, bad in ((('private',), 'never-export'), (('schema',), True), (('capacityQualified',), True),
                         (('configuredDurationSeconds',), 1800), (('totalEvents',), 4), (('truncatedStacks',), 2),
                         (('events', 'SocketRead'), {}), (('events', 'ExecutionSample', 'private-symbol'), {}),
                         (('events', 'ExecutionSample', 'LanInterfaceEnumeration', 'count'), True),
                         (('events', 'ExecutionSample', 'LanInterfaceEnumeration', 'durationNanos'), 100),
                         (('events', 'ExecutionSample'), {}), (('firstEventEpochMillis',), 2 ** 63),
                         (('cpuLoad', 'samples'), 0), (('cpuLoad', 'maximumPpm', 'jvmUser'), 1000001),
                         (('cpuLoad', 'sumPpm', 'machineTotal'), float('nan')),
                         (('cpuLoad', 'sumPpm', 'secret'), 0),
                         (('lastEventEpochMillis',), 1)):
            value = profile()
            target = value
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = bad
            with self.subTest(path=path), self.assertRaises(ValueError):
                evidence.runtime_profile(value, 'client', 'a' * 40, 'b' * 64)

    def test_wait_durations_are_aggregate_waits_not_cpu_percentages(self):
        value = profile()
        value['totalEvents'] += 2
        row = dict(count=2, durationNanos=50000000, maximumDurationNanos=30000000)
        value['events']['ThreadPark']['CoroutineScheduler'] = row
        self.assertEqual(evidence.runtime_profile(value, 'client', 'a' * 40, 'b' * 64), value)
        for key, invalid in (('maximumDurationNanos', 100), ('maximumDurationNanos', 60000000), ('count', 0)):
            broken = copy.deepcopy(value)
            broken['events']['ThreadPark']['CoroutineScheduler'][key] = invalid
            with self.assertRaises(ValueError):
                evidence.runtime_profile(broken, 'client', 'a' * 40, 'b' * 64)

    def test_fixed_initialization_is_additional_and_never_counts_as_capacity(self):
        self.assertEqual(evidence.initialization(initialization()), initialization())
        for mode in ('steady', 'large'):
            with self.assertRaises(ValueError):
                evidence.measurement(initialization(), mode)
        # The full measured gate is unchanged, not reduced by the priming responses.
        value = measurement()
        for key in ('expected', 'completed', 'dispatched', 'hostAcceptedDelta', 'hostCompletedDelta'):
            value['measurements'][key] -= 76800
        value['throughputResponsesPerSecond'] = value['measurements']['completed'] / 1800
        with self.assertRaises(ValueError):
            evidence.measurement(value, 'steady')

    def test_initialization_must_complete_its_exact_calls_and_actual_host_quiescence(self):
        for path, changed in ((('measurements', 'callsPerClient'), 599), (('measurements', 'expected'), 76799),
                              (('measurements', 'actualDurationNanos'), 59000000000),
                              (('measurements', 'actualDurationNanos'), 130000000000),
                              (('measurements', 'minimumCallPeriodNanos'), 1),
                              (('measurements', 'callPhaseTimeoutMillis'), 240000),
                              (('hostObservation', 'acceptedAfter'), 76799), (('hostObservation', 'runningAfter'), 1),
                              (('hostObservation', 'queuedAfter'), 1), (('hostObservation', 'connectedAfter'), 127),
                              (('hostObservation', 'refusedDelta'), 1), (('hostObservation',), None)):
            value = initialization()
            target = value
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = changed
            with self.subTest(path=path), self.assertRaises(ValueError):
                evidence.initialization(value)

    def test_initialization_failure_stays_failed_not_an_ignored_warmup_error(self):
        value = initialization()
        value['measurements'].update(dispatched=12, completed=11, failed=1, actualDurationNanos=2000000000)
        value['hostObservation'] = None
        value['rpcFailuresByKind']['DeadlineExceeded'] = 1
        with self.assertRaises(ValueError):
            evidence.initialization(value)
        value['status'] = 'FAIL'
        self.assertEqual(value, evidence.initialization(value))
        self.assertFalse(value['capacityQualified'])

    def test_initialization_rejects_private_extra_fields_boolean_counts_and_false_qualification(self):
        for path, changed in ((('private',), 'never-export'), (('schema',), True), (('capacityQualified',), True),
                              (('scope',), 'CAPACITY'), (('measurements', 'completed'), True),
                              (('hostObservation', 'private'), 'never-export'),
                              (('rpcFailuresByKind', 'secret'), 0),
                              (('measurements', 'driverCompilationMillisAfter'), -1)):
            value = initialization()
            target = value
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = changed
            with self.subTest(path=path), self.assertRaises(ValueError):
                evidence.initialization(value)

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
