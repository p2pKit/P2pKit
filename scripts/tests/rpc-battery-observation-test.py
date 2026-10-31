#!/usr/bin/env python3
"""Offline battery-recording refusal controls; no device, discharge or energy evidence."""
import copy
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rpc_battery_observation as m


def fixture():
    bound = dict(schema='2', scope=m.protocol.SCOPE, hostPlatform='Ios', clientCount='128',
                 hostSourceSha='1' * 40, hostArtifactSha256='2' * 64, runLabel='offline-recorder', runNonce='3' * 64)
    rows = [dict(uptimeMillis=1000 * index, sequence=index, batteryPercentMilli=80000 - index,
                 batteryCurrentMicroamps='unavailable', batteryTemperatureMilliC='unavailable',
                 batteryState='unplugged', batterySource='ios-uidevice', thermalState='nominal',
                 thermalSource='ios-process-info') for index in range(1801)]
    result = dict(mobileBinding=bound, mode='steady', iosControlTransport='wireless', clientCount=128,
                  source=dict(commit='1' * 40), status='MECHANICAL_PASS_PENDING_NETWORK_AND_RESOURCE_REVIEW',
                  sourceUnchanged=True, harnessUnchanged=True, errors=[], phoneSamples=rows,
                  phoneCleanup=dict(runtimeClosed=True, clientPinsRemoved=True, controlHealthy=True),
                  measurement=dict(measurements=dict(hostUptimeDeltaMillis=1800000, hostSamples=181,
                      requiredDurationNanos=1800000000000, actualSchedulingNanos=1800000000000)))
    log = b'host,uptimeMs,cpuNs,rssBytes,threads,accepted,completed,running,queued,payloadBytes,records,connected\n'
    log += b''.join(('host,' + str(index * 10000) + ',0,1,1,0,0,0,0,0,0,128\n').encode() for index in range(181))
    return result, log, bound


class Recording(unittest.TestCase):
    def test_public_level_drop_never_awards_energy_temperature_or_capacity(self):
        result, log, bound = fixture()
        output = m.observe_wireless_iphone(result, log, bound)
        self.assertEqual(output['observedDropMilliPercent'], 1800)
        self.assertTrue(output['batteryLevelDecreased'])
        self.assertEqual(output['observedHostMillis'], 1800000)
        for key in ('calibratedEnergyQualified', 'preciseTemperatureQualified', 'physicalCapacityQualified'):
            self.assertFalse(output[key])

    def test_constant_or_increasing_public_level_is_retained_without_claiming_discharge_or_low_power(self):
        for end in (80000, 81000):
            result, log, bound = fixture()
            for row in result['phoneSamples']:
                row['batteryPercentMilli'] = end
            result['phoneSamples'][0]['batteryPercentMilli'] = 80000
            output = m.observe_wireless_iphone(result, log, bound)
            self.assertFalse(output['batteryLevelDecreased'])
            self.assertLessEqual(output['observedDropMilliPercent'], 0)

    def test_wired_failed_foreign_or_unretired_run_is_not_discharge_evidence(self):
        for change in (dict(iosControlTransport='wired'), dict(status='FAIL'), dict(mode='large'), dict(clientCount=256),
                       dict(errors=[dict(phase='execution')]), dict(source=dict(commit='4' * 40)),
                       dict(phoneCleanup={}), dict(sourceUnchanged=False), dict(harnessUnchanged=False),
                       dict(thermalAbort=dict(status='ABORTED'))):
            result, log, bound = fixture()
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.observe_wireless_iphone(result | change, log, bound)

    def test_charging_unavailable_or_unsafe_thermal_sample_anywhere_refuses_the_whole_interval(self):
        for key, value in (('batteryState', 'charging'), ('batteryState', 'unknown'), ('batteryState', 'full'),
                           ('batteryPercentMilli', 'unavailable'), ('batterySource', 'unavailable'),
                           ('batteryCurrentMicroamps', -1), ('batteryTemperatureMilliC', 32000),
                           ('thermalState', 'serious'), ('thermalState', 'critical'), ('thermalState', 'unavailable')):
            result, log, bound = fixture()
            result['phoneSamples'][900][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                m.observe_wireless_iphone(result, log, bound)

    def test_sparse_replayed_regressed_or_short_series_cannot_cover_the_workload(self):
        for kind in ('gap', 'replay', 'clock', 'end', 'start', 'short-workload', 'timeline-mismatch'):
            result, log, bound = fixture()
            if kind == 'gap':
                del result['phoneSamples'][900:905]
            elif kind == 'replay':
                result['phoneSamples'].insert(900, copy.deepcopy(result['phoneSamples'][899]))
            elif kind == 'clock':
                result['phoneSamples'][900]['uptimeMillis'] = 1
            elif kind == 'end':
                del result['phoneSamples'][-6:]
            elif kind == 'start':
                del result['phoneSamples'][:6]
            elif kind == 'short-workload':
                result['measurement']['measurements']['actualSchedulingNanos'] -= 1
            else:
                result['measurement']['measurements']['hostUptimeDeltaMillis'] -= 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                m.observe_wireless_iphone(result, log, bound)

    def test_initialization_idle_and_post_stop_battery_changes_are_excluded(self):
        result, log, bound = fixture()
        for row in result['phoneSamples']:
            row['uptimeMillis'] += 10000
            row['sequence'] += 10
        log = b''.join(('host,' + str(10000 + index * 10000) + ',0,1,1,0,0,0,0,0,0,128\n').encode()
                       for index in range(181))
        before = copy.deepcopy(result['phoneSamples'][0]) | dict(uptimeMillis=0, sequence=0, batteryState='charging')
        after = copy.deepcopy(result['phoneSamples'][-1]) | dict(uptimeMillis=1820000, sequence=1820, batteryState='full')
        result['phoneSamples'] = [before, *result['phoneSamples'], after]
        output = m.observe_wireless_iphone(result, log, bound)
        self.assertEqual(output['sampleCount'], 1801)
        self.assertEqual(output['observedDropMilliPercent'], 1800)


if __name__ == '__main__':
    unittest.main(verbosity=2)
