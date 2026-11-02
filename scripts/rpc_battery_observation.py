"""Review an unplugged iPhone interval recorded by the sealed wireless campaign.

Only public battery-level observations are reported. Milli-percent storage does
not establish sensor precision, calibrated energy, or power consumption. The
caller must verify the original native receipts and preparation before calling.
"""
from __future__ import annotations

import hashlib
import re

import rpc_mobile_capacity as protocol

need = protocol.need
MAX_GAP_MILLIS = 4500


def observe_wireless_iphone(result, steady_stdout, expected_binding):
    binding = protocol.binding(expected_binding)
    need(binding['schema'] == '2' and binding['hostPlatform'] == 'Ios', 'Explicit sealed iPhone recording required')
    need(type(result) is dict and result.get('mobileBinding') == binding and
         result.get('source', {}).get('commit') == binding['hostSourceSha'] and
         result.get('clientCount') == int(binding['clientCount']) and
         result.get('mode') == 'steady' and result.get('iosControlTransport') == 'wireless' and
         result.get('status') == 'MECHANICAL_PASS_PENDING_NETWORK_AND_RESOURCE_REVIEW' and
         result.get('sourceUnchanged') is True and result.get('harnessUnchanged') is True and
         result.get('errors') == [] and result.get('thermalAbort') is None and
         result.get('phoneCleanup') == dict(runtimeClosed=True, clientPinsRemoved=True, controlHealthy=True),
         'Completed original wireless recording and healthy exact Stop required')
    need(type(steady_stdout) is bytes and 0 < len(steady_stdout) <= 8 * 1024 * 1024, 'Bounded original driver log required')
    # These rows are emitted only by the measured steady phase. Initializing,
    # connected-idle and post-Stop observations never enter its battery interval.
    # Parse the uptime column explicitly; the other columns remain in the
    # original log, independently verified by the steady measurement assessor.
    timestamps = [int(line.split(b',')[1]) for line in steady_stdout.splitlines()
                  if re.fullmatch(rb'host,[0-9]+(?:,[0-9]+){10}', line)]
    need(2 <= len(timestamps) <= 300 and all(b > a for a, b in zip(timestamps, timestamps[1:])),
         'Original steady host timeline missing or regressed')
    start, end = timestamps[0], timestamps[-1]
    measurements = result.get('measurement', {}).get('measurements', {})
    need(end > start and measurements.get('requiredDurationNanos') == 1_800_000_000_000 and
         type(measurements.get('actualSchedulingNanos')) is int and
         measurements['actualSchedulingNanos'] >= 1_800_000_000_000 and
         measurements.get('hostSamples') == len(timestamps) and measurements.get('hostUptimeDeltaMillis') == end - start,
         'Battery interval must match the independently measured thirty-minute host timeline')
    rows = result.get('phoneSamples')
    need(type(rows) is list and 2 <= len(rows) <= 3000, 'Original bounded phone series required')
    need(all(type(row) is dict and type(row.get('uptimeMillis')) is int and
             type(row.get('sequence')) is int for row in rows), 'Missing native phone sample clock')
    need(all(b['uptimeMillis'] > a['uptimeMillis'] and b['sequence'] > a['sequence'] for a, b in zip(rows, rows[1:])),
         'Replayed or regressed phone sample')
    first = next((i for i, row in enumerate(rows) if row['uptimeMillis'] >= start), None)
    last = next((i for i in range(len(rows) - 1, -1, -1) if rows[i]['uptimeMillis'] <= end), None)
    need(first is not None and last is not None and first < last and
         rows[first]['uptimeMillis'] - start < MAX_GAP_MILLIS and
         end - rows[last]['uptimeMillis'] < MAX_GAP_MILLIS, 'Battery endpoints do not cover the measured phase')
    selected = rows[first:last + 1]
    gaps = [b['uptimeMillis'] - a['uptimeMillis'] for a, b in zip(selected, selected[1:])]
    need(max(gaps) < MAX_GAP_MILLIS, 'Unobserved charging or thermal interval cannot be certified')
    for row in selected:
        fields = {key: str(row.get(key)) for key in protocol.ENVIRONMENT_FIELDS}
        normalized = protocol.environment(fields, 'Ios')
        need(normalized['batteryState'] == 'unplugged' and normalized['batterySource'] == 'ios-uidevice' and
             type(normalized['batteryPercentMilli']) is int and
             normalized['thermalState'] in ('nominal', 'fair') and normalized['thermalSource'] == 'ios-process-info',
             'Charging, missing battery data, or serious/critical/unknown thermal state invalidates discharge recording')
    before, after = selected[0], selected[-1]
    drop = before['batteryPercentMilli'] - after['batteryPercentMilli']
    return dict(schema=1, scope='UNPLUGGED_IOS_WIRELESS_PUBLIC_BATTERY_LEVEL_OBSERVATION',
                sourceSha=binding['hostSourceSha'], hostArtifactSha256=binding['hostArtifactSha256'],
                clientCount=int(binding['clientCount']), originalDriverLogSha256=hashlib.sha256(steady_stdout).hexdigest(),
                observedHostMillis=after['uptimeMillis'] - before['uptimeMillis'], sampleCount=len(selected),
                maximumObservedGapMillis=max(gaps), startBatteryPercentMilli=before['batteryPercentMilli'],
                endBatteryPercentMilli=after['batteryPercentMilli'], observedDropMilliPercent=drop,
                batteryLevelDecreased=drop > 0, calibratedEnergyQualified=False, preciseTemperatureQualified=False,
                physicalCapacityQualified=False, batteryLevelPrecision='PUBLIC_API_UNCALIBRATED',
                controlOverhead='WIRELESS_COREDEVICE_CONTROL_AND_TELEMETRY_INCLUDED',
                chargingStateCoverage='SAMPLED_PUBLIC_API_NOT_CONTINUOUS_HARDWARE_MEASUREMENT',
                measuredPhaseEndpointOffsetsMillis=dict(start=before['uptimeMillis'] - start,
                                                       end=end - after['uptimeMillis']))
