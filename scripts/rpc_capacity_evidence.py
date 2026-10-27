"""Closed numeric capacity evidence. This never awards physical, mobile or release readiness."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

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
CORRECTNESS_CASES = ('full-authenticated-cohort', 'concurrent-correlation', 'application-error',
    'procedure-authorization', 'sent-deadline', 'sent-cancellation', 'slow-handler-fairness',
    'disconnect-during-call', 'full-authenticated-cohort-after')
CHURN_CASES = ('full-authenticated-cohort', 'five-round-original-identity-reconnect', 'full-authenticated-cohort-after')
CONTROL_FIELDS = ('clients', 'expectedEchoResponses', 'echoResponses', 'concurrentEchoResponses', 'applicationErrors',
    'authorizationRefusals', 'sentDeadlineFailures', 'sentCancellations', 'disconnectUnknownOutcomes',
    'holdEntered', 'holdRetired', 'slowHandlerResponses', 'fairnessEchoResponses', 'churnRounds',
    'disconnects', 'reconnects', 'actualDurationNanos', 'hostConnectionsBefore', 'hostConnectionsAfter',
    'hostRunningAfter', 'hostQueuedAfter')
INITIALIZATION_FIELDS = ('clients', 'callsPerClient', 'minimumCallPeriodNanos', 'callPhaseTimeoutMillis',
                         'encodedRequestBytes', 'encodedResponseBytes', 'expected', 'dispatched', 'completed', 'failed',
                         'actualDurationNanos', 'driverCpuDeltaNanos', 'driverCompilationMillisBefore',
                         'driverCompilationMillisAfter')
INITIALIZATION_HOST_FIELDS = ('acceptedBefore', 'completedBefore', 'acceptedAfter', 'completedAfter',
                             'runningAfter', 'queuedAfter', 'connectedAfter', 'refusedDelta', 'protocolFailuresDelta',
                             'connectionFailuresDelta', 'cpuNanosDelta', 'uptimeMillisDelta')
IDLE_SAMPLE_FIELDS = ('uptimeMillis', 'cpuNanos', 'residentBytes', 'nativeThreads', 'connected', 'accepted', 'completed',
    'refused', 'duplicates', 'droppedNotifications', 'protocolFailures', 'connectionFailures', 'running', 'queued',
    'records', 'payloadBytes', 'driverElapsedNanos', 'driverCpuNanos')
IDLE_FIELDS = ('clients', 'sampleCount', 'actualDurationNanos', 'actualSettleNanos', 'hostUptimeDeltaMillis',
    'hostCpuDeltaNanos', 'driverElapsedNanos', 'driverCpuDeltaNanos', 'connectionChanges', 'invalidHostSamples',
    'sampledMinHostRssBytes', 'sampledMaxHostRssBytes', 'sampledMinHostThreads', 'sampledMaxHostThreads',
    'hostConnectionsBefore', 'hostConnectionsAfter', 'hostAcceptedDelta', 'hostCompletedDelta',
    'hostRunningAfter', 'hostQueuedAfter')
IDLE_SIGNED_DELTAS = frozenset(('hostUptimeDeltaMillis', 'hostCpuDeltaNanos', 'driverCpuDeltaNanos',
                              'hostAcceptedDelta', 'hostCompletedDelta'))
IDLE_UNCHANGED_COUNTERS = ('accepted', 'completed', 'refused', 'duplicates', 'droppedNotifications',
                           'protocolFailures', 'connectionFailures')
PROFILE_CATEGORIES = frozenset(('LanInterfaceEnumeration', 'LanPathValidation', 'SocketRead', 'SocketWrite',
    'SocketPoll', 'Crypto', 'PayloadHash', 'JsonCodec', 'RpcHost', 'RpcClient', 'RpcLink', 'CoreSession',
    'CoroutineScheduler', 'CoroutineFlow', 'Other'))
PROFILE_NUMBERS = ('schema', 'configuredDelaySeconds', 'configuredDurationSeconds', 'samplingPeriodMillis',
                   'waitThresholdMillis', 'firstEventEpochMillis', 'lastEventEpochMillis', 'totalEvents',
                   'ignoredEvents', 'truncatedStacks')


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


def runtime_profile(value, role, source, recording_sha256):
    """Diagnostic counts, not CPU percentages: native samples may be blocked in I/O."""
    need(role in ('host', 'client') and type(source) is str and re.fullmatch('[a-f0-9]{40}', source) and
         type(recording_sha256) is str and re.fullmatch('[a-f0-9]{64}', recording_sha256))
    need(type(value) is dict and set(value) == set(PROFILE_NUMBERS) |
         {'scope', 'capacityQualified', 'role', 'sourceSha', 'recordingSha256', 'events', 'cpuLoad'})
    numbers({k: value[k] for k in PROFILE_NUMBERS}, PROFILE_NUMBERS)
    need(value['schema'] == 1 and value['scope'] == 'BOUNDED_JFR_SAMPLES_AND_CPU_LOAD_NOT_CAPACITY' and
         value['capacityQualified'] is False and value['role'] == role and value['sourceSha'] == source and
         value['recordingSha256'] == recording_sha256 and value['configuredDelaySeconds'] == 120 and
         value['configuredDurationSeconds'] == 180 and value['samplingPeriodMillis'] == value['waitThresholdMillis'] == 20)
    need(0 < value['firstEventEpochMillis'] <= value['lastEventEpochMillis'] and
         0 < value['totalEvents'] <= 2000000 and value['ignoredEvents'] < value['totalEvents'])
    events = value['events']
    need(type(events) is dict and set(events) == {'ExecutionSample', 'NativeMethodSample', 'ThreadPark', 'JavaMonitorEnter'})
    observed = 0
    for kind, categories in events.items():
        need(type(categories) is dict and set(categories) <= PROFILE_CATEGORIES)
        for row in categories.values():
            numbers(row, ('count', 'durationNanos', 'maximumDurationNanos'))
            need(0 < row['count'] <= 2000000 and row['maximumDurationNanos'] <= row['durationNanos'] <=
                 row['maximumDurationNanos'] * row['count'] and row['maximumDurationNanos'] <= 2400000000000)
            if kind in ('ExecutionSample', 'NativeMethodSample'):
                need(row['durationNanos'] == 0)
            observed += row['count']
    cpu = value['cpuLoad']
    need(type(cpu) is dict and set(cpu) == {'samples', 'sumPpm', 'maximumPpm'} and
         type(cpu['samples']) is int and 0 < cpu['samples'] <= 2000000)
    for field in ('sumPpm', 'maximumPpm'):
        numbers(cpu[field], ('jvmUser', 'jvmSystem', 'machineTotal'))
    for field in cpu['sumPpm']:
        maximum, total = cpu['maximumPpm'][field], cpu['sumPpm'][field]
        need(maximum <= 1000000 and maximum <= total <= maximum * cpu['samples'])
    need(events['ExecutionSample'] and observed + value['ignoredEvents'] + cpu['samples'] == value['totalEvents'] and
         value['truncatedStacks'] <= observed)
    return json.loads(json.dumps(value, allow_nan=False))


def record_profile(value, fields, client_count):
    """An explicit caller-selected cohort, never inferred from a possibly stale report."""
    need(type(client_count) is int and client_count in (128, 256))
    need(type(value) is dict and type(value.get('schema')) is int and value['schema'] in (1, 2))
    expected = set(fields) | ({'clientCount'} if value['schema'] == 2 else set())
    need(set(value) == expected)
    if value['schema'] == 1:
        need(client_count == 128)
    else:
        need(type(value['clientCount']) is int and value['clientCount'] == client_count)


def measurement(value, mode, client_count=128):
    need(mode in ('steady', 'large'))
    keys = {'schema', 'mode', 'status', 'capacityQualified', 'measurements', 'throughputResponsesPerSecond',
            'latencyBucketUpperMs', 'latencyOverflowBucketMs', 'rpcFailuresByKind', 'cleanup'}
    if mode == 'steady':
        keys.add('schedulingDelayBucketUpperMs')
    record_profile(value, keys, client_count)
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
        need(m['clients'] == client_count and m['callsPerSecondPerClient'] == 10 and
             m['expected'] == client_count * 18000 and
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


def initialization(value, client_count=128):
    """Additional fully accounted preparation, never part of the selected steady-state responses."""
    record_profile(value, {'schema', 'scope', 'status', 'capacityQualified', 'measurements',
         'hostObservation', 'latencyBucketUpperMs', 'rpcFailuresByKind'}, client_count)
    need(value['scope'] ==
         'FIXED_RPC_PATH_INITIALIZATION_NOT_CAPACITY_OR_COLD_START_QUALIFICATION' and
         value['capacityQualified'] is False and value['status'] in ('FAIL', 'INITIALIZED_NOT_CAPACITY'))
    m = numbers(value['measurements'], INITIALIZATION_FIELDS)
    errors = numbers(value['rpcFailuresByKind'], FAILURE_KINDS)
    histogram(value['latencyBucketUpperMs'], m['dispatched'])
    need(m['clients'] == client_count and m['callsPerClient'] == 600 and m['expected'] == client_count * 600 and
         m['minimumCallPeriodNanos'] == 100000000 and m['callPhaseTimeoutMillis'] == 120000 and
         m['encodedRequestBytes'] == m['encodedResponseBytes'] == 1024 and m['actualDurationNanos'] > 0 and
         m['dispatched'] == m['completed'] + m['failed'] and m['dispatched'] <= m['expected'] and
         sum(errors.values()) <= m['failed'] and m['driverCompilationMillisAfter'] >= m['driverCompilationMillisBefore'])
    h = value['hostObservation']
    if h is not None:
        numbers(h, INITIALIZATION_HOST_FIELDS)
        need(h['acceptedAfter'] >= h['acceptedBefore'] and h['completedAfter'] >= h['completedBefore'])
    if value['status'] == 'INITIALIZED_NOT_CAPACITY':
        need(m['dispatched'] == m['completed'] == m['expected'] and m['failed'] == 0 and
             60000000000 <= m['actualDurationNanos'] < 130000000000 and all(v == 0 for v in errors.values()) and
             h is not None and h['connectedAfter'] == client_count and
             h['acceptedAfter'] - h['acceptedBefore'] == h['completedAfter'] - h['completedBefore'] == m['expected'] and
             h['acceptedBefore'] == h['completedBefore'] and h['acceptedAfter'] == h['completedAfter'] and
             all(h[k] == 0 for k in ('runningAfter', 'queuedAfter', 'refusedDelta', 'protocolFailuresDelta',
                                   'connectionFailuresDelta')))
    return json.loads(json.dumps(value, allow_nan=False))


def exercise(value, mode, client_count=128):
    """Finite real RPC controls. Handler delay never proves socket backpressure or physical capacity."""
    need(mode in ('correctness', 'churn'))
    fields = {'schema', 'mode', 'scope', 'status', 'capacityQualified', 'expectedCases', 'passedCases',
              'failureCase', 'measurements', 'trueSlowConsumerQualified', 'cleanup'}
    record_profile(value, fields, client_count)
    need(value['schema'] == 2 and value['mode'] == mode and value['scope'] ==
         'REAL_AUTHENTICATED_RPC_CONTROLS_NOT_CAPACITY' and value['capacityQualified'] is False and
         value['trueSlowConsumerQualified'] is False and value['cleanup'] == 'AWAIT_FINAL_RECORD' and
         value['status'] in ('FAIL', 'PENDING_RESOURCE_AND_NETWORK_REVIEW'))
    expected_cases = list(CORRECTNESS_CASES if mode == 'correctness' else CHURN_CASES)
    need(type(value['expectedCases']) is list and value['expectedCases'] == expected_cases and
         type(value['passedCases']) is list and value['passedCases'] == expected_cases[:len(value['passedCases'])])
    m = numbers(value['measurements'], CONTROL_FIELDS)
    expected_echo = client_count * 3 + 5 if mode == 'correctness' else client_count * 5
    need(m['clients'] == client_count and m['expectedEchoResponses'] == expected_echo and
         m['actualDurationNanos'] > 0 and m['echoResponses'] <= expected_echo and
         m['hostConnectionsBefore'] in (0, client_count) and m['hostConnectionsAfter'] in (0, client_count) and
         m['holdRetired'] <= m['holdEntered'] <= 3 and m['slowHandlerResponses'] <= 16 and
         m['concurrentEchoResponses'] <= client_count * 2 and m['churnRounds'] <= 5 and
         m['disconnects'] <= client_count * 5 and m['reconnects'] <= m['disconnects'])
    singleton = ('applicationErrors', 'authorizationRefusals', 'sentDeadlineFailures', 'sentCancellations',
                 'disconnectUnknownOutcomes', 'fairnessEchoResponses')
    need(all(m[name] <= 1 for name in singleton))
    if value['status'] == 'PENDING_RESOURCE_AND_NETWORK_REVIEW':
        need(value['passedCases'] == expected_cases and value['failureCase'] is None and
             m['echoResponses'] == expected_echo and m['hostConnectionsBefore'] == m['hostConnectionsAfter'] ==
             client_count and m['hostRunningAfter'] == m['hostQueuedAfter'] == 0)
        if mode == 'correctness':
            need(m['concurrentEchoResponses'] == client_count * 2 and all(m[name] == 1 for name in singleton) and
                 m['holdEntered'] == m['holdRetired'] == 3 and m['slowHandlerResponses'] == 16 and
                 m['churnRounds'] == 0 and m['disconnects'] == m['reconnects'] == 1)
        else:
            need(all(m[name] == 0 for name in singleton) and m['concurrentEchoResponses'] ==
                 m['holdEntered'] == m['holdRetired'] == m['slowHandlerResponses'] == 0 and m['churnRounds'] == 5 and
                 m['disconnects'] == m['reconnects'] == client_count * 5)
    else:
        need(value['failureCase'] in expected_cases)
    return json.loads(json.dumps(value, allow_nan=False))


def connected_idle(value, client_count=128):
    """Separate real-host monotonic idle samples; neither initialization nor steady capacity evidence."""
    record_profile(value, {'schema', 'sourceSha', 'runLabel', 'hostPlatform', 'hostArtifactSha256',
        'driverArtifactSha256', 'scope', 'status', 'capacityQualified', 'settleMillis', 'requiredHostIdleMillis',
        'failureStage', 'measurements', 'samples'}, client_count)
    need(value['schema'] == 2 and value['scope'] == 'CONNECTED_IDLE_RESOURCE_OBSERVATION_NOT_CAPACITY' and
         value['capacityQualified'] is False and value['status'] in ('FAIL', 'OBSERVED_CONNECTED_IDLE_NOT_CAPACITY') and
         value['hostPlatform'] in ('Jvm', 'Android', 'Ios'))
    need(type(value['sourceSha']) is str and re.fullmatch('[a-f0-9]{40}', value['sourceSha']) and
         type(value['runLabel']) is str and re.fullmatch('[a-z0-9-]{1,64}', value['runLabel']) and
         all(type(value[field]) is str and re.fullmatch('[a-f0-9]{64}', value[field])
             for field in ('hostArtifactSha256', 'driverArtifactSha256')))
    need(type(value['settleMillis']) is int and value['settleMillis'] == 10000 and
         type(value['requiredHostIdleMillis']) is int and value['requiredHostIdleMillis'] == 30000)
    m = value['measurements']
    need(type(m) is dict and set(m) == set(IDLE_FIELDS))
    for field, count in m.items():
        need(type(count) is int and (-(2**63) if field in IDLE_SIGNED_DELTAS else 0) <= count < 2**63)
    rows = value['samples']
    need(type(rows) is list and 0 <= len(rows) <= 10 and m['clients'] == client_count and
         m['sampleCount'] == len(rows) and m['invalidHostSamples'] <= len(rows))
    for row in rows:
        numbers(row, IDLE_SAMPLE_FIELDS)
        need(row['residentBytes'] > 0 and row['nativeThreads'] > 0 and row['connected'] <= client_count and
             row['running'] <= client_count and row['queued'] <= client_count * 2 and
             row['records'] <= client_count * 1024 and
             row['payloadBytes'] <= (64 if client_count == 128 else 128) * 1048576)

    def first(field):
        return rows[0][field] if rows else 0

    def last(field):
        return rows[-1][field] if rows else 0

    need(m['hostUptimeDeltaMillis'] == last('uptimeMillis') - first('uptimeMillis') and
         m['hostCpuDeltaNanos'] == last('cpuNanos') - first('cpuNanos') and
         m['driverElapsedNanos'] == last('driverElapsedNanos') and
         m['driverCpuDeltaNanos'] == last('driverCpuNanos') - first('driverCpuNanos') and
         m['hostConnectionsBefore'] == first('connected') and m['hostConnectionsAfter'] == last('connected') and
         m['hostAcceptedDelta'] == last('accepted') - first('accepted') and
         m['hostCompletedDelta'] == last('completed') - first('completed') and
         m['hostRunningAfter'] == last('running') and m['hostQueuedAfter'] == last('queued'))
    for field, suffix in (('residentBytes', 'HostRssBytes'), ('nativeThreads', 'HostThreads')):
        need(m['sampledMin' + suffix] == min((r[field] for r in rows), default=0) and
             m['sampledMax' + suffix] == max((r[field] for r in rows), default=0))
    need(m['actualDurationNanos'] >= m['actualSettleNanos'] + m['driverElapsedNanos'] and
         (not rows or rows[0]['driverElapsedNanos'] == 0))
    if value['status'] == 'OBSERVED_CONNECTED_IDLE_NOT_CAPACITY':
        need(value['failureStage'] is None and len(rows) >= 2 and m['actualSettleNanos'] >= 10000000000 and
             m['hostUptimeDeltaMillis'] >= 30000 and m['driverElapsedNanos'] >= 30000000000 and
             m['connectionChanges'] == m['invalidHostSamples'] == 0 and
             abs(m['hostUptimeDeltaMillis'] - m['driverElapsedNanos'] // 1000000) <= 5000)
        need(all(r['connected'] == client_count and r['running'] == r['queued'] == 0 and
                 r['accepted'] == r['completed'] for r in rows))
        for a, b in zip(rows, rows[1:]):
            need(a['uptimeMillis'] < b['uptimeMillis'] and a['cpuNanos'] <= b['cpuNanos'] and
                 a['driverCpuNanos'] <= b['driverCpuNanos'] and
                 b['driverElapsedNanos'] >= a['driverElapsedNanos'] + 5000000000 and
                 all(a[field] == b[field] for field in IDLE_UNCHANGED_COUNTERS))
    else:
        need(value['failureStage'] in ('settle', 'baseline', 'observe', 'validation'))
    return json.loads(json.dumps(value, allow_nan=False))


def host_series(rows, client_count=128):
    need(type(client_count) is int and client_count in (128, 256))
    need(type(rows) is list and 2 <= len(rows) <= 3000)
    for row in rows:
        numbers(row, HOST_FIELDS)
        need(row['residentBytes'] > 0 and row['nativeThreads'] > 0 and row['jvmThreads'] > 0)
        # The existing LabTelemetry/RpcLimits bounds, not new capacity thresholds.
        need(row['connected'] <= client_count and row['running'] <= client_count and
             row['queued'] <= client_count * 2 and row['records'] <= client_count * 1024 and
             row['payloadBytes'] <= (64 if client_count == 128 else 128) * 1048576)
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
