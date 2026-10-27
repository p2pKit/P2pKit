#!/usr/bin/env python3
"""Portable synthetic Mac/phone control failures, never physical-device qualification."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import stat
import sys
import tempfile
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_mobile_capacity as protocol
import rpc_mobile_usb as usb
import rpc_ios_usb as ios


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


coordinator = load('mac_mobile_test_coordinator', 'run-rpc-mobile-capacity.py')
ios_coordinator = load('mac_mobile_test_ios_coordinator', 'run-rpc-ios-mobile-capacity.py')
lab = load('mac_mobile_test_lab', 'run-rpc-capacity-lab.py')


def binding(platform='Android', count=256):
    return dict(schema='2', scope=protocol.SCOPE, runLabel='offline-mac', runNonce='1' * 64,
                hostPlatform=platform, hostSourceSha='2' * 40, hostArtifactSha256='3' * 64,
                clientCount=str(count))


def environment(platform='Android'):
    return dict(batteryPercentMilli='70000', batteryCurrentMicroamps='-125000',
                batteryTemperatureMilliC='32000', batteryState='unplugged', batterySource='android-battery-manager',
                thermalState='nominal', thermalSource='android-power-manager') if platform == 'Android' else \
        dict(batteryPercentMilli='70000', batteryCurrentMicroamps='unavailable',
             batteryTemperatureMilliC='unavailable', batteryState='unplugged', batterySource='ios-uidevice',
             thermalState='nominal', thermalSource='ios-process-info')


def telemetry(platform='Android', count=256):
    return binding(platform, count) | protocol.RESOURCE_KINDS[platform] | dict(clock='host-run-monotonic') | \
        dict.fromkeys(protocol.NUMBERS, '0') | dict(sequence='1', uptimeMillis='1000', residentBytes='1048576',
            nativeThreads='12') | environment(platform)


def inbox(platform='Android', count=256):
    alphabet = 'abcdefghijklmnopqrstuvwxyz234567'
    pins = ['p2f1-' + 'a' * 50 + alphabet[number // 32] + alphabet[number % 32] for number in range(count)]
    return binding(platform, count) | dict(hostAddress='192.168.14.2', hostPort='48123',
        hostInterface='en0' if platform == 'Ios' else 'wlan0', subnets='192.168.14.0/24', clientPins=','.join(pins))


class SelectedSchema(unittest.TestCase):
    def test_legacy_binding_stays_exactly128_without_new_fields(self):
        old = {key: value for key, value in binding(count=128).items() if key != 'clientCount'} | dict(schema='1')
        self.assertEqual(protocol.client_count(old), 128)
        with self.assertRaises(ValueError):
            protocol.binding(old | dict(clientCount='256'))

    def test_explicit128_and256_binding_roundtrip_and_unknown_profiles_refused(self):
        for count in (128, 256):
            self.assertEqual(protocol.client_count(protocol.parse(protocol.encode(binding(count=count)))), count)
        for changed in (dict(clientCount='512'), dict(clientCount='0256'), dict(clientCount=True),
                        dict(schema='3'), dict(clients='256'), dict(clientCount=''), dict(clientCount='128.0')):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                protocol.binding(binding() | changed)
        with self.assertRaises(ValueError):
            protocol.binding({key: value for key, value in binding().items() if key != 'clientCount'})

    def test_every_control_record_retains_selected_count(self):
        value = protocol.Protocol(binding(), '192.168.14.2', 48123)
        ready = binding() | dict(address='192.168.14.2', port='48123', fingerprint='p2f1-' + 'a' * 52,
            compiledSourceMatched='true', artifactKind='android-installed-base-apk')
        closed = binding() | dict(runtimeClosed='true', clientPinsRemoved='true', controlHealthy='true')
        value.ready(ready)
        value.closed(closed)
        self.assertEqual(value.stop(), binding() | dict(action='stop'))
        for row, consumer in ((ready, value.ready), (closed, value.closed), (telemetry(), value.telemetry)):
            for changed in (row | dict(clientCount='128'), {key: val for key, val in row.items() if key != 'clientCount'}):
                with self.assertRaises(ValueError):
                    consumer(changed)

    def test_profile_caps_match_host_limits_and_not_claimed512_capacity(self):
        for count in (128, 256):
            value = protocol.Protocol(binding(count=count), '192.168.14.2', 48123)
            maximum = telemetry(count=count) | dict(connected=str(count), running=str(count), queued=str(count * 2),
                records=str(count * 1024), payloadBytes=str(count * 512 * 1024))
            self.assertEqual(value.telemetry(maximum)['connected'], count)
            for name in ('connected', 'running', 'queued', 'records', 'payloadBytes'):
                with self.subTest(count=count, name=name), self.assertRaises(ValueError):
                    value.telemetry(maximum | {name: str(int(maximum[name]) + 1)})

    def test_sensor_fields_are_mandatory_explicit_and_native_platform_bound(self):
        for platform in ('Android', 'Ios'):
            value = protocol.Protocol(binding(platform), '192.168.14.2', 48123)
            row = telemetry(platform)
            parsed = value.telemetry(row)
            self.assertEqual(parsed['batteryPercentMilli'], 70000)
            for name in protocol.ENVIRONMENT_FIELDS:
                with self.subTest(platform=platform, name=name), self.assertRaises(ValueError):
                    value.telemetry({key: val for key, val in row.items() if key != name})
            with self.assertRaises(ValueError):
                value.telemetry(row | dict(cpuSource='jvm'))
        for changed in (dict(batteryPercentMilli='100001'), dict(batteryCurrentMicroamps='-20000001'),
                        dict(batteryTemperatureMilliC='100001'), dict(batteryPercentMilli='070000'),
                        dict(batteryState='plugged'), dict(thermalState='hot'), dict(thermalSource='ios-process-info'),
                        dict(batterySource='unavailable'), dict(batteryCurrentMicroamps='-0'), dict(thermalState='unavailable')):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                protocol.environment(environment() | changed, 'Android')

    def test_unavailable_public_sensors_do_not_invent_measurements(self):
        raw = dict.fromkeys(protocol.ENVIRONMENT_FIELDS, 'unavailable')
        for platform in ('Android', 'Ios'):
            self.assertEqual(protocol.environment(raw, platform), raw)
        for name in ('batteryCurrentMicroamps', 'batteryTemperatureMilliC'):
            with self.assertRaises(ValueError):
                protocol.environment(environment('Ios') | {name: '1'}, 'Ios')

    def test_signed_sensor_changes_require_new_monotonic_sample(self):
        value = protocol.Protocol(binding(), '192.168.14.2', 48123)
        first = telemetry()
        self.assertEqual(value.telemetry(first)['batteryCurrentMicroamps'], -125000)
        self.assertIsNone(value.telemetry(first))
        with self.assertRaises(ValueError):
            value.telemetry(first | dict(batteryState='charging'))
        new = first | dict(sequence='2', uptimeMillis='2000', batteryState='charging', batteryCurrentMicroamps='100000')
        self.assertEqual(value.telemetry(new)['batteryCurrentMicroamps'], 100000)

    def test_sensor_retention_preserves_schema_and_runtime_retirement_requirements(self):
        value = protocol.Protocol(binding(), '192.168.14.2', 48123)
        before = value.telemetry(telemetry() | dict(records='100'))
        after = value.telemetry(telemetry() | dict(sequence='66', uptimeMillis='66000', batteryPercentMilli='69990'))
        self.assertEqual(protocol.retention(before, after)['status'], 'PASS')
        for changed in (dict(records=1), dict(batteryPercentMilli=True), dict(batteryCurrentMicroamps=-20000001)):
            with self.assertRaises(ValueError):
                protocol.retention(before, after | changed)
        with self.assertRaises(ValueError):
            protocol.retention(before, {key: val for key, val in after.items() if key not in protocol.ENVIRONMENT_FIELDS})

    def test_exact_selected_pin_cohort_and_record_bound(self):
        for platform in ('Android', 'Ios'):
            raw = protocol.encode(inbox(platform))
            self.assertLessEqual(len(raw), protocol.RECORD_LIMIT)
            self.assertEqual(protocol.inbox(raw, binding(platform)), inbox(platform))
            for changed in (dict(clientCount='128'), dict(clientPins=inbox(platform)['clientPins'] + ',p2f1-' + 'a' * 52),
                            dict(hostArtifactSha256='4' * 64), dict(subnets='0.0.0.0/0')):
                with self.subTest(platform=platform, changed=str(changed)[:80]), self.assertRaises(ValueError):
                    protocol.inbox(protocol.encode(inbox(platform) | changed), binding(platform))


class MacAdmission(unittest.TestCase):
    def settings(self):
        return dict(schema='2', clientCount='256', sourceSha='2' * 40, hostArtifactSha256='3' * 64,
            endpointAddress='192.168.14.2', port='48123', subnets='192.168.14.0/24', interface='en0',
            localAddress='192.168.14.3', hostInterface='wlan0', androidUsbSerial='OFFLINE_DEVICE',
            adb='/NOT_EXECUTED/platform-tools/adb')

    def test_mac_android_settings_preserve_source_network_artifact_and_count(self):
        values = self.settings()
        self.assertEqual(coordinator.settings(values, '2' * 40, 'offline-mac', lab)['clientCount'], '256')
        run = coordinator.Run.__new__(coordinator.Run)
        run.native_host, run.values, run.lab = 'macos-arm64', values, lab
        self.assertEqual(run.configuration('2' * 40, 'offline-mac')['interface'], 'en0')
        for changed in (dict(interface='utun0'), dict(clientCount='512'), dict(sourceSha='4' * 40),
                        dict(schema='1'), dict(clientCount='0256'), dict(endpointAddress='8.8.8.8')):
            run.values = values | changed
            with self.assertRaises((ValueError, RuntimeError)):
                run.configuration('2' * 40, 'offline-mac')

    def test_mac_ios_settings_use_same_count_and_refuse_android_fields(self):
        values = {key: val for key, val in self.settings().items() if key not in ('androidUsbSerial', 'adb')}
        values |= dict(iosDeviceIdentifier='11111111-2222-3333-4444-555555555555', hostInterface='en0')
        self.assertEqual(ios_coordinator.settings(values, '2' * 40, 'offline-mac', lab)['clientCount'], '256')
        for changed in (dict(interface='utun0'), dict(hostInterface='wlan0'), dict(clientCount='512'), dict(adb='/foreign')):
            with self.assertRaises((ValueError, RuntimeError)):
                ios_coordinator.settings(values | changed, '2' * 40, 'offline-mac', lab)

    def test_native_mac_admission_is_explicit_unprivileged_and_not_rosetta(self):
        run = coordinator.Run.__new__(coordinator.Run)
        with patch('audit_processes.host_role', return_value='macos-arm64'), \
                patch.object(coordinator.platform, 'system', return_value='Darwin'), \
                patch.object(coordinator.platform, 'machine', return_value='arm64'), \
                patch.object(coordinator.os, 'getuid', return_value=501), \
                patch.object(coordinator.os, 'geteuid', return_value=501):
            run.admit_environment(SimpleNamespace(owner_authorized_mobile=True))
            self.assertEqual(run.native_host, 'macos-arm64')
            with self.assertRaises(ValueError):
                run.admit_environment(SimpleNamespace(owner_authorized_mobile=False))
            with patch.object(coordinator.os, 'getuid', return_value=0), self.assertRaises(ValueError):
                run.admit_environment(SimpleNamespace(owner_authorized_mobile=True))
            with patch.object(coordinator.platform, 'machine', return_value='x86_64'), self.assertRaises(ValueError):
                run.admit_environment(SimpleNamespace(owner_authorized_mobile=True))

    def test_mac_generator_initialization_does_not_read_linux_counters_or_start_observers(self):
        run = coordinator.Run.__new__(coordinator.Run)
        run.native_host = 'macos-arm64'
        run.result, run.policy, run.commands = {}, Mock(), Mock()
        with patch.object(coordinator.evidence, 'clock_snapshot') as linux, \
                patch.object(coordinator.darwin, 'snapshot') as mac:
            self.assertIsNone(run.initial_generator_snapshot())
            with self.assertRaises(ValueError):
                run.generator_snapshot()
            linux.assert_not_called()
            mac.assert_not_called()
            run.policy.control_inventory.return_value = run.result['nativeControlTests'] = 100
            run.generator_snapshot()
            mac.assert_called_once_with(run.commands)

    def test_mac_context_preserves_actual_source_and_native_host(self):
        source = dict(commit='2' * 40, tree='3' * 40, status='')
        runner = Mock(source_snapshot=Mock(return_value=source))
        context = dict(host='macos-arm64', root=str(coordinator.ROOT), source=source)
        self.assertEqual(coordinator.bind_sources(runner, context, 'macos-arm64'), source)
        for changed in (dict(host='linux-x64'), dict(source=source | dict(status=' M changed')), dict(root='/FOREIGN')):
            with self.assertRaises(ValueError):
                coordinator.bind_sources(runner, context | changed, 'macos-arm64')


class RuntimeFailures(unittest.TestCase):
    def fixture(self):
        run = coordinator.Run.__new__(coordinator.Run)
        run.protocol = protocol.Protocol(binding(), '192.168.14.2', 48123)
        run.samples, run.last_sample = [], None
        run.phone, run.lab = Mock(), Mock()
        run.directory = Path('/NOT_EXECUTED')
        run.result = dict(errors=[])
        return run

    def test_thermal_stopping_threshold_is_retained_before_abort(self):
        for thermal in ('serious', 'critical'):
            run = self.fixture()
            run.phone.read.side_effect = lambda name, **kwargs: None if name == 'failed.txt' else telemetry() | dict(thermalState=thermal)
            with self.assertRaises(ValueError):
                run.sample()
            self.assertEqual(run.samples[0]['thermalState'], thermal)
            self.assertEqual(run.result['thermalAbort']['status'], 'ABORTED')
            run.lab.write_private.assert_called_once()

    def test_valid_fair_thermal_sample_is_recorded_without_bypassing_resource_caps(self):
        run = self.fixture()
        run.phone.read.side_effect = lambda name, **kwargs: None if name == 'failed.txt' else telemetry() | dict(thermalState='fair')
        self.assertEqual(run.sample()['thermalState'], 'fair')
        self.assertNotIn('thermalAbort', run.result)

    def test_missing_stale_or_mismatched_launcher_count_is_rejected_before_measurement(self):
        run = self.fixture()
        run.context, run.config, run.mode = dict(source=dict(commit='2' * 40)), dict(runLabel='offline-mac'), 'steady'
        good = dict(schema=2, clientCount=256, sourceSha='2' * 40, runLabel='offline-mac', role='client', mode='steady')
        run.require_result_binding(good)
        for changed in (dict(schema=1), dict(clientCount=128), dict(clientCount=True), dict(clientCount='256'), dict(sourceSha='4' * 40)):
            with self.assertRaises(ValueError):
                run.require_result_binding(good | changed)
        with self.assertRaises(ValueError):
            run.require_result_binding({key: val for key, val in good.items() if key != 'clientCount'})

    def test_connected_idle_crossbinds_phone_and_verified_driver_artifacts(self):
        run = self.fixture()
        run.context, run.config = dict(source=dict(commit='2' * 40)), dict(runLabel='offline-mac')
        entries = [dict(name='driver.jar', sha256='4' * 64), dict(name='library.jar', sha256='5' * 64)]
        transcript = lab.encode({f'entry{index}file0': item['name'] + ':' + item['sha256']
                                 for index, item in enumerate(entries)})
        run.lab.distribution.return_value = (None, {'entries': entries}, None)
        run.lab.read_private.return_value = transcript
        run.lab.encode.side_effect = lab.encode
        valid = dict(sourceSha='2' * 40, runLabel='offline-mac', hostArtifactSha256='3' * 64,
                     hostPlatform='Android', driverArtifactSha256=hashlib.sha256(transcript).hexdigest())
        with patch.object(coordinator.evidence, 'connected_idle', return_value=valid, create=True) as validator:
            self.assertEqual(run.connected_idle(valid), valid)
            validator.assert_called_once_with(valid, client_count=256)
            for changed in (dict(sourceSha='6' * 40), dict(runLabel='other'), dict(hostArtifactSha256='7' * 64),
                            dict(hostPlatform='Ios'), dict(driverArtifactSha256='8' * 64)):
                validator.return_value = valid | changed
                with self.assertRaises(ValueError):
                    run.connected_idle(valid | changed)
            validator.return_value = valid
            run.lab.read_private.return_value = transcript + b'extra=foreign\n'
            with self.assertRaises(ValueError):
                run.connected_idle(valid)

    def test_connected_idle_uses_actual_helper_for_complete_bound_samples(self):
        evidence = coordinator.evidence
        for count in (128, 256):
            for platform in ('Android', 'Ios'):
                with self.subTest(count=count, platform=platform):
                    run = self.fixture()
                    run.protocol = protocol.Protocol(binding(platform, count), '192.168.14.2', 48123)
                    run.context, run.config = dict(source=dict(commit='2' * 40)), dict(runLabel='offline-mac')
                    entries = [dict(name='driver.jar', sha256='4' * 64)]
                    transcript = lab.encode({'entry0file0': 'driver.jar:' + '4' * 64})
                    run.lab.distribution.return_value = (None, {'entries': entries}, None)
                    run.lab.read_private.return_value = transcript
                    run.lab.encode.side_effect = lab.encode
                    first = dict.fromkeys(evidence.IDLE_SAMPLE_FIELDS, 0)
                    first.update(uptimeMillis=1000, cpuNanos=1000000, residentBytes=1048576,
                                 nativeThreads=12, connected=count, accepted=600 * count,
                                 completed=600 * count, driverCpuNanos=1000000)
                    last = first | dict(uptimeMillis=31000, cpuNanos=2000000,
                                        driverElapsedNanos=30000000000, driverCpuNanos=3000000)
                    measured = dict.fromkeys(evidence.IDLE_FIELDS, 0)
                    measured.update(clients=count, sampleCount=2, actualDurationNanos=40000000000,
                        actualSettleNanos=10000000000, hostUptimeDeltaMillis=30000, hostCpuDeltaNanos=1000000,
                        driverElapsedNanos=30000000000, driverCpuDeltaNanos=2000000,
                        sampledMinHostRssBytes=1048576, sampledMaxHostRssBytes=1048576,
                        sampledMinHostThreads=12, sampledMaxHostThreads=12,
                        hostConnectionsBefore=count, hostConnectionsAfter=count)
                    value = dict(schema=2, clientCount=count, sourceSha='2' * 40, runLabel='offline-mac',
                        hostPlatform=platform, hostArtifactSha256='3' * 64,
                        driverArtifactSha256=hashlib.sha256(transcript).hexdigest(),
                        scope='CONNECTED_IDLE_RESOURCE_OBSERVATION_NOT_CAPACITY',
                        status='OBSERVED_CONNECTED_IDLE_NOT_CAPACITY', capacityQualified=False,
                        settleMillis=10000, requiredHostIdleMillis=30000, failureStage=None,
                        measurements=measured, samples=[first, last])
                    self.assertEqual(run.connected_idle(value), value)
                    with self.assertRaises(ValueError):
                        run.connected_idle(value | dict(clientCount=384 - count))
                    with self.assertRaises(ValueError):
                        run.connected_idle(value | dict(hostArtifactSha256='5' * 64))


class BoundActivation(unittest.TestCase):
    def test_coordinator_automates_only_explicit_schema2_and_keeps_legacy_manual_admission(self):
        for schema in ('1', '2'):
            with self.subTest(schema=schema), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                run = coordinator.Run.__new__(coordinator.Run)
                run.bound = binding(count=128) if schema == '2' else \
                    {key: value for key, value in binding(count=128).items() if key != 'clientCount'} | dict(schema='1')
                run.protocol = protocol.Protocol(run.bound, '192.168.14.2', 48123)
                run.directory, run.control = root / 'client', root / 'control'
                run.directory.mkdir()
                run.control.mkdir()
                (run.directory / 'mobile-inbox.txt').touch()
                run.state, run.client_id, run.client_count = root, 'OFFLINE', 128
                run.mode, run.config, run.values, run.env = 'steady', {}, {'hostInterface': 'wlan0'}, {}
                run.result, run.lab, run.phone = {}, Mock(), Mock()
                run.lab.read_private.return_value = b'OFFLINE_INPUT_NOT_PROVISIONING'
                ready = run.bound | dict(address='192.168.14.2', port='48123', fingerprint='p2f1-' + 'a' * 52,
                    compiledSourceMatched='true', artifactKind='android-installed-base-apk')
                run.phone.read.side_effect = lambda name: None if name == 'failed.txt' else ready
                try:
                    with patch.object(coordinator.subprocess, 'Popen', return_value=Mock(poll=Mock(return_value=None))):
                        run.launch()
                    self.assertEqual(run.phone.activate.call_count, 1 if schema == '2' else 0)
                    run.phone.provision.assert_called_once()
                finally:
                    run.client_log.close()

    def test_android_development_activation_binds_exact_published_inbox_and_is_once_only(self):
        value = usb.AndroidUsb(Mock(), Path('/NOT_EXECUTED'), Path('/NOT_EXECUTED/adb'),
            'OFFLINE_DEVICE', 'offline-mac', binding=binding())
        value.authorized = True
        value.adb_command = Mock(return_value=(0, b'Status: ok\n'))
        raw = protocol.encode(inbox())
        value.provision(raw)
        value.activate(raw)
        label, argv = value.adb_command.call_args.args
        self.assertEqual(label, 'android-start-bound-campaign')
        self.assertIn(hashlib.sha256(raw).hexdigest(), argv)
        self.assertIn('2' * 40, argv)
        self.assertIn('3' * 64, argv)
        self.assertNotIn('root', argv)
        with self.assertRaises(ValueError):
            value.activate(raw)
        value.stop(protocol.encode(binding() | dict(action='stop')))
        with self.assertRaises(ValueError):
            value.stop(protocol.encode(binding() | dict(action='stop')))

    def test_android_launch_error_and_mismatched_inbox_preserve_stop_obligation(self):
        value = usb.AndroidUsb(Mock(), Path('/NOT_EXECUTED'), Path('/NOT_EXECUTED/adb'),
            'OFFLINE_DEVICE', 'offline-mac', binding=binding())
        value.authorized = True
        value.adb_command = Mock(return_value=(0, b'Error: Activity not started\n'))
        raw = protocol.encode(inbox())
        value.provision(raw)
        with self.assertRaises(ValueError):
            value.activate(protocol.encode(inbox() | dict(hostInterface='wlan1')))
        self.assertFalse(value.activation_attempted)
        with self.assertRaises(ValueError):
            value.activate(raw)
        self.assertTrue(value.provisioned)
        value.adb_command = Mock(return_value=(0, b''))
        value.stop(protocol.encode(binding() | dict(action='stop')))

    def ios(self):
        prepared = dict(schema='2', clientCount='256', scope='ios-usb-slot', runLabel='offline-mac',
                        sourceSha='2' * 40, artifactSha256='3' * 64)
        backend = Mock(read=Mock(return_value=protocol.encode(prepared)))
        value = ios.IosUsb(backend, binding('Ios'), owner_authorized=True)
        value.start()
        raw = protocol.encode(inbox('Ios'))
        value.provision(raw)
        return value, backend, raw

    def test_ios_sealed_start_command_does_not_relaunch_or_terminate_active_app(self):
        value, backend, raw = self.ios()
        value.activate(raw)
        name, command, deadline = backend.publish.call_args.args
        self.assertEqual(name, 'campaign.txt')
        self.assertEqual(protocol.parse(command), dict(schema='1', scope='mobile-usb-start', runLabel='offline-mac',
            hostSourceSha='2' * 40, hostArtifactSha256='3' * 64, inboxSha256=hashlib.sha256(raw).hexdigest()))
        self.assertNotIn('launch', [call[0] for call in backend.mock_calls])
        self.assertEqual(ios.verify_input(name, command, ios.input_seal(name, command)), command)
        with self.assertRaises(ValueError):
            value.activate(raw)

    def test_ios_partial_campaign_copy_remains_failure_and_requires_exact_stop(self):
        value, backend, raw = self.ios()
        backend.publish.side_effect = RuntimeError('synthetic partial publication')
        with self.assertRaises(RuntimeError):
            value.activate(raw)
        self.assertTrue(value.provisioned)
        with self.assertRaises(ValueError):
            value.activate(raw)
        backend.publish.side_effect = None
        value.stop(protocol.encode(value.protocol.stop()))
        self.assertEqual(backend.publish.call_args.args[0], 'stop.txt')


class InstalledTool(unittest.TestCase):
    def test_recorded_coredevice_version_may_vary_but_identity_and_lifetime_must_not(self):
        tool, metadata = Mock(), Mock()
        tool.resolve.return_value, metadata.resolve.return_value = tool, metadata
        tool.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFREG | 0o755, st_uid=0, st_nlink=1, st_size=100)
        metadata.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0, st_nlink=1, st_size=200)
        tool.read_bytes.return_value = b'\xcf\xfa\xed\xfe' + b'OFFLINE_NOT_EXECUTABLE'
        original = plistlib.dumps(dict(CFBundleIdentifier='com.apple.CoreDevice', CFBundleVersion='900.7.1'))
        metadata.read_bytes.return_value = original
        value = ios.DevicectlFiles.__new__(ios.DevicectlFiles)
        with patch.object(ios, 'DEVICECTL', tool), patch.object(ios, 'COREDEVICE_INFO', metadata), \
                patch.object(ios.os, 'access', return_value=True):
            first = value.tool_binding()
            self.assertEqual(value.tool_version, '900.7.1')
            self.assertEqual(value.metadata_sha256, hashlib.sha256(original).hexdigest())
            self.assertEqual(value.tool_binding(), first)
            for changed in (dict(CFBundleIdentifier='foreign', CFBundleVersion='900.7.1'),
                            dict(CFBundleIdentifier='com.apple.CoreDevice', CFBundleVersion='not-a-version'),
                            dict(CFBundleIdentifier='com.apple.CoreDevice', CFBundleVersion='900.7.2')):
                metadata.read_bytes.return_value = plistlib.dumps(changed)
                with self.assertRaises(ValueError):
                    value.tool_binding()


class CampaignKeys(unittest.TestCase):
    def fixture(self, directory):
        keys = directory / 'campaign-keys'
        keys.mkdir(mode=0o700)
        apk_tool = directory / 'adb'
        apk_tool.write_bytes(b'OFFLINE_NOT_AN_ADB_TOOL')
        private, public = b'OFFLINE_NOT_A_PRIVATE_KEY', b'OFFLINE_NOT_A_PUBLIC_KEY'
        lab.write_private(keys / 'adbkey', private)
        lab.write_private(keys / 'adbkey.pub', public)
        manifest = dict(schema='1', scope='mobile-usb-campaign-adb-keys', sourceSha='2' * 40,
            adbSha256=hashlib.sha256(apk_tool.read_bytes()).hexdigest(), privateKeySha256=hashlib.sha256(private).hexdigest(),
            publicKeySha256=hashlib.sha256(public).hexdigest())
        lab.write_private(keys / 'manifest.txt', protocol.encode(manifest))
        control_dir = directory / 'control'
        control_dir.mkdir(mode=0o700)
        commands = Mock(files=lab, env={})
        control = usb.AndroidUsb(commands, control_dir, apk_tool, 'OFFLINE_DEVICE', 'offline-mac',
            binding=binding(), campaign_keys=keys)
        return control, keys, manifest

    def test_explicit_campaign_material_is_source_tool_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            control, keys, manifest = self.fixture(Path(temporary))
            material = control.campaign_material()
            self.assertEqual(set(material), {'adbkey', 'adbkey.pub'})
            self.assertEqual(control.campaign_material(), material)
            lab.write_private(keys / 'manifest.txt', protocol.encode(manifest | dict(sourceSha='4' * 40)), replace=True)
            with self.assertRaises(ValueError):
                control.campaign_material()

    def test_changed_linked_foreign_or_unscoped_keys_are_never_adopted(self):
        for alteration in ('bytes', 'hardlink', 'permissions', 'scope', 'unknown'):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                control, keys, manifest = self.fixture(directory)
                if alteration == 'bytes':
                    (keys / 'adbkey').write_bytes(b'CHANGED')
                elif alteration == 'hardlink':
                    os.link(keys / 'adbkey', directory / 'linked-key')
                elif alteration == 'permissions':
                    (keys / 'adbkey.pub').chmod(0o644)
                elif alteration == 'scope':
                    lab.write_private(keys / 'manifest.txt', protocol.encode(manifest | dict(scope='global-adb')), replace=True)
                else:
                    lab.write_private(keys / 'unexpected', b'PRESERVE')
                with self.assertRaises(ValueError):
                    control.campaign_material()
                control.commands.run.assert_not_called()

    def test_reuse_copies_only_into_new_server_and_retires_only_owned_copies(self):
        with tempfile.TemporaryDirectory(prefix='mobile-keys-') as temporary:
            control, keys, manifest = self.fixture(Path(temporary))
            expected = {name: (keys / name).read_bytes() for name in ('adbkey', 'adbkey.pub')}
            sock = socket.socket(socket.AF_UNIX)
            def child(argv, **options):
                for name, raw in expected.items():
                    self.assertEqual((control.home / name).read_bytes(), raw)
                self.assertEqual(options['env']['ADB_SERVER_SOCKET'], 'localfilesystem:' + str(control.socket))
                sock.bind(str(control.socket))
                return Mock(poll=Mock(return_value=None), wait=Mock(return_value=0))
            try:
                with patch.object(usb.subprocess, 'Popen', side_effect=child):
                    control.start()
                control.server.poll.return_value = 0
                result = control.close()
                self.assertTrue(result['privateServerExited'])
                self.assertTrue(result['copiedHostKeysRetired'])
                self.assertTrue(result['campaignKeysRetained'])
                self.assertFalse(result['testHostKeysRetired'])
                self.assertEqual({name: (keys / name).read_bytes() for name in expected}, expected)
                self.assertEqual(list(control.home.iterdir()), [])
            finally:
                sock.close()
                if control.log is not None and not control.log.closed:
                    control.log.close()

    def test_legacy_schema_cannot_reuse_campaign_credentials(self):
        old = {key: value for key, value in binding(count=128).items() if key != 'clientCount'} | dict(schema='1')
        with self.assertRaises(ValueError):
            usb.AndroidUsb(Mock(), Path('/NOT_EXECUTED'), Path('/NOT_EXECUTED/adb'), 'OFFLINE_DEVICE', 'offline-mac',
                binding=old, campaign_keys=Path('/NOT_EXECUTED/private'))


class SlotPreparation(unittest.TestCase):
    def fixture(self):
        value = ios.DevicectlFiles.__new__(ios.DevicectlFiles)
        value.remote = 'Library/Application Support/rpc-capacity/offline-mac'
        previous = binding('Ios', 128) | dict(runLabel='previous-ios')
        raw = protocol.encode(inbox('Ios', 128) | dict(runLabel='previous-ios'))
        closed = previous | dict(runtimeClosed='true', clientPinsRemoved='true', controlHealthy='true')
        acknowledgement = dict(schema='2', clientCount='256', scope='ios-usb-slot', runLabel='offline-mac',
                               sourceSha='2' * 40, artifactSha256='3' * 64)
        value.verify = Mock()
        value.inventory = Mock(return_value=dict.fromkeys(('inbox.txt', 'closed.txt'), 1))
        value.download = Mock(return_value=raw)
        value.read = Mock(side_effect=[protocol.encode(closed), protocol.encode(acknowledgement)])
        value.publish = Mock()
        value.remaining = Mock(return_value=10)
        return value, raw, closed, acknowledgement

    def test128_to256_uses_actual_prior_healthy_close_and_acknowledged_new_slot(self):
        value, raw, closed, acknowledgement = self.fixture()
        value.prepare_next(binding('Ios'), 'previous-ios', hashlib.sha256(raw).hexdigest(), 30)
        name, request, deadline = value.publish.call_args.args
        self.assertEqual(name, 'next.txt')
        self.assertEqual(protocol.parse(request), dict(schema='1', scope='mobile-usb-prepare-next', runLabel='previous-ios',
            nextRunLabel='offline-mac', hostSourceSha='2' * 40, hostArtifactSha256='3' * 64,
            inboxSha256=hashlib.sha256(raw).hexdigest(), clientCount='256'))
        self.assertEqual(value.remote, 'Library/Application Support/rpc-capacity/offline-mac')
        self.assertEqual([call.args[0] for call in value.read.call_args_list], ['closed.txt', 'next-ready.txt'])

    def test_failed_missing_foreign_or_uncertain_prior_run_never_prepares_a_new_slot(self):
        for alteration in ('cleanup', 'inbox-hash', 'missing', 'wrong-source'):
            with self.subTest(alteration=alteration):
                value, raw, closed, acknowledgement = self.fixture()
                digest = hashlib.sha256(raw).hexdigest()
                if alteration == 'cleanup':
                    value.read.side_effect = [protocol.encode(closed | dict(controlHealthy='false'))]
                elif alteration == 'inbox-hash':
                    digest = '4' * 64
                elif alteration == 'missing':
                    value.inventory.return_value = {'inbox.txt': 1}
                else:
                    bad = protocol.encode(protocol.parse(raw) | dict(hostSourceSha='4' * 40))
                    value.download.return_value, digest = bad, hashlib.sha256(bad).hexdigest()
                with self.assertRaises(ValueError):
                    value.prepare_next(binding('Ios'), 'previous-ios', digest, 30)
                value.publish.assert_not_called()
                self.assertEqual(value.remote, 'Library/Application Support/rpc-capacity/offline-mac')

    def test_stale_next_acknowledgement_is_not_admitted_as_current_preparation(self):
        value, raw, closed, acknowledgement = self.fixture()
        value.read.side_effect = [protocol.encode(closed), protocol.encode(acknowledgement | dict(clientCount='128'))]
        with self.assertRaises(ValueError):
            value.prepare_next(binding('Ios'), 'previous-ios', hashlib.sha256(raw).hexdigest(), 30)
        self.assertEqual(value.publish.call_count, 1)

    def test_directory_wait_observes_existing_parents_and_never_queries_a_missing_slot(self):
        value = ios.DevicectlFiles.__new__(ios.DevicectlFiles)
        value.remote, value.selected = 'Library/Application Support/rpc-capacity/offline-mac', 'OFFLINE'
        row = lambda name: dict(name=name, isDirectory=True, isSymbolicLink=False)
        value.command = Mock(side_effect=[dict(result=dict(files=[row('Application Support')])),
            dict(result=dict(files=[row('rpc-capacity')])), dict(result=dict(files=[]))])
        self.assertFalse(value.slot_present(30))
        self.assertEqual([call.args[1][-1] for call in value.command.call_args_list],
                         ['Library', 'Library/Application Support', 'Library/Application Support/rpc-capacity'])
        value.command = Mock(side_effect=[dict(result=dict(files=[row(name)])) for name in
                                         ('Application Support', 'rpc-capacity', 'offline-mac')])
        self.assertTrue(value.slot_present(30))
        value.command = Mock(return_value=dict(result=dict(files=[row('Application Support') | dict(isSymbolicLink=True)])))
        with self.assertRaises(ValueError):
            value.slot_present(30)


class InstallBeforeRun(unittest.TestCase):
    def test_android_install_is_checksum_bound_and_does_not_claim_readiness(self):
        with tempfile.TemporaryDirectory() as temporary:
            apk = Path(temporary) / 'sample.apk'
            apk.write_bytes(b'OFFLINE_NOT_AN_APK')
            bound = binding() | dict(hostArtifactSha256=hashlib.sha256(apk.read_bytes()).hexdigest())
            value = usb.AndroidUsb(Mock(), Path('/NOT_EXECUTED'), Path('/NOT_EXECUTED/adb'),
                'OFFLINE_DEVICE', 'offline-mac', binding=bound)
            value.authorized, value.adb_command = True, Mock(return_value=(0, b'Success\n'))
            self.assertTrue(value.install_app(apk)['requiresInstalledReadyHash'])
            self.assertIn('--no-streaming', value.adb_command.call_args.args[1])
            value.provisioned = True
            with self.assertRaises(ValueError):
                value.install_app(apk)
            value.provisioned = False
            apk.write_bytes(b'CHANGED')
            with self.assertRaises(ValueError):
                value.install_app(apk)

    def test_ios_install_requires_fixed_bundle_and_exact_selected_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / 'RpcPhone.app'
            app.mkdir()
            metadata, executable = app / 'Info.plist', app / 'RpcPhone'
            metadata.write_bytes(plistlib.dumps(dict(CFBundleIdentifier=ios.IOS_PACKAGE, CFBundleExecutable='RpcPhone')))
            executable.write_bytes(b'OFFLINE_NOT_AN_IOS_EXECUTABLE')
            bound = binding('Ios') | dict(hostArtifactSha256=hashlib.sha256(executable.read_bytes()).hexdigest())
            value = ios.DevicectlFiles.__new__(ios.DevicectlFiles)
            value.selected, value.verify, value.command = 'OFFLINE', Mock(), Mock()
            self.assertTrue(value.install_app(app, bound, 120)['requiresInstalledReadyHash'])
            self.assertEqual(value.command.call_args.args[1][:3], ['device', 'install', 'app'])
            value.command.reset_mock()
            metadata.write_bytes(plistlib.dumps(dict(CFBundleIdentifier='foreign.app', CFBundleExecutable='RpcPhone')))
            with self.assertRaises(ValueError):
                value.install_app(app, bound, 120)
            value.command.assert_not_called()

    def test_prepare_launch_is_source_bound_and_has_no_termination_flag(self):
        value = ios.DevicectlFiles.__new__(ios.DevicectlFiles)
        value.selected, value.verify, value.command = 'OFFLINE', Mock(), Mock()
        value.launch_prepare(binding('Ios'), 30)
        arguments = value.command.call_args.args[1]
        self.assertEqual(arguments[:3], ['device', 'process', 'launch'])
        self.assertIn('--rpc-usb-client-count', arguments)
        self.assertIn('256', arguments)
        self.assertIn('2' * 40, arguments)
        self.assertNotIn('--terminate-existing', arguments)

    def test_native_json_option_precedes_application_delimiter(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = ios.DevicectlFiles.__new__(ios.DevicectlFiles)
            value.directory, value.tool_sha256, value.count = Path(temporary), '4' * 64, 0
            value.tool_binding = Mock(return_value='4' * 64)
            value.now, value.remaining = lambda: 0, Mock(return_value=30)
            value.commands = Mock()
            value.read_owned = Mock(return_value=json.dumps(dict(info=dict(outcome='success'), result={})).encode())
            value.command('prepare', ['device', 'process', 'launch', ios.IOS_PACKAGE, '--', '--rpc-usb-prepare', 'offline-mac'], 30)
            arguments = value.commands.run.call_args.args[1]
            self.assertLess(arguments.index('--json-output'), arguments.index('--'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
