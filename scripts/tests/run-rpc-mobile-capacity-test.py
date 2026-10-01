#!/usr/bin/env python3
"""Offline coordinator failure controls. Fake phones/receipts NEVER constitute USB/RPC/device execution."""
import copy
import importlib.util
import json
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('mobile_coordinator_test', ROOT / 'scripts/run-rpc-mobile-capacity.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
lab = m.module('mobile_coordinator_lab_test', 'run-rpc-capacity-lab.py')


def bound():
    return dict(schema='1', scope=m.protocol.SCOPE, runLabel='test-run', runNonce='1' * 64,
                hostPlatform='Android', hostSourceSha='2' * 40, hostArtifactSha256='3' * 64)


def row():
    return bound() | m.protocol.RESOURCE_KINDS['Android'] | dict(clock='host-run-monotonic') | \
        dict.fromkeys(m.protocol.NUMBERS, '0') | dict(sequence='1', uptimeMillis='1000', residentBytes='1048576', nativeThreads='12')


def closed():
    return bound() | dict(runtimeClosed='true', clientPinsRemoved='true', controlHealthy='true')


def fixture():
    run = m.Run.__new__(m.Run)
    run.protocol = m.protocol.Protocol(bound(), '192.168.14.2', 48123)
    run.phone = Mock(provisioned=True)
    run.samples, run.last_sample = [], None
    run.directory = Path('/NOT_EXECUTED/mobile-client-test-run')
    run.lab = Mock()
    run.result = dict(status='FAIL', errors=[])
    run.phone_stopped = run.stop_attempted = False
    return run


class Configuration(unittest.TestCase):
    def values(self):
        return dict(schema='1', sourceSha='2' * 40, hostArtifactSha256='3' * 64,
            endpointAddress='192.168.14.2', port='48123', subnets='192.168.14.0/24', interface='eth0',
            localAddress='192.168.14.3', hostInterface='wlan0', androidUsbSerial='OFFLINE_FIXTURE',
            adb='/NOT_EXECUTED/platform-tools/adb')

    def test_exact_configuration_retains_actual_lan_policy_and_artifact_binding(self):
        values = self.values()
        result = m.settings(values, '2' * 40, 'test-run', lab)
        self.assertEqual(result, {k: values[k] for k in lab.FIELDS - {'runLabel', 'role'}} |
                         dict(runLabel='test-run', role='client'))
        for key, value in (('schema', '2'), ('sourceSha', '4' * 40), ('hostArtifactSha256', 'not-a-hash'),
                           ('hostInterface', '../wlan0'), ('androidUsbSerial', 'emulator-5554'),
                           ('androidUsbSerial', '192.168.14.2:5555'), ('adb', 'adb'), ('adb', '/x/../adb'),
                           ('localAddress', '127.0.0.1'), ('endpointAddress', '8.8.8.8'), ('subnets', '0.0.0.0/0'),
                           ('port', '22'), ('extra', 'private')):
            with self.subTest(key=key), self.assertRaises((ValueError, RuntimeError)):
                m.settings(values | {key: value}, '2' * 40, 'test-run', lab)

    def test_direct_route_cannot_admit_gateway_tunnel_wrong_source_interface_or_ambiguity(self):
        config = m.settings(self.values(), '2' * 40, 'test-run', lab)
        good = dict(dst='192.168.14.2', dev='eth0', **{'from': '192.168.14.3'})
        checked = m.direct_route(json.dumps([good]).encode(), config)
        self.assertTrue(checked['selectedDirectRouteObserved'])
        self.assertFalse(checked['physicalLanProven'])
        for change in (dict(gateway='192.168.14.1'), dict(via={}), dict(encap={}), dict(multipath=[]),
                       dict(dst='192.168.14.1'), dict(dev='utun0'), {'from': '192.168.14.9'}, dict(type='local')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.direct_route(json.dumps([good | change]).encode(), config)
        for bad in ([good, good], {}, [], [True]):
            with self.assertRaises(ValueError):
                m.direct_route(json.dumps(bad).encode(), config)

    def test_credentials_are_not_forwarded_and_original_environment_is_unchanged(self):
        original = dict(GH_TOKEN='DO_NOT_FORWARD', SIGNING_KEY='DO_NOT_FORWARD', JAVA_HOME='/JDK17',
                        P2PKIT_AUDIT_OWNERSHIP_CHAIN='owned')
        snapshot = dict(original)
        actual = m.safe_environment(original)
        self.assertEqual(original, snapshot)
        self.assertEqual(actual['JAVA_HOME'], '/JDK17')
        self.assertNotIn('GH_TOKEN', actual)
        self.assertNotIn('SIGNING_KEY', actual)
        self.assertEqual(actual['RPC_CAPACITY_MOBILE_AUTHORIZED'], m.protocol.AUTHORIZATION)

    def test_no_owner_authorization_or_unverified_iphone_copy_can_start_hardware_work(self):
        with patch.object(m, 'module') as load, self.assertRaises(ValueError):
            m.Run(SimpleNamespace(owner_authorized_mobile=False))
        load.assert_not_called()
        commands = Mock()
        with self.assertRaises(NotImplementedError):
            m.usb.IosUsb(commands, Path('/NOT_EXECUTED'), 'OFFLINE', 'test-run')
        self.assertEqual(commands.mock_calls, [])

    def test_product_and_harness_sources_are_bound_independently_without_relabeling(self):
        product, harness = Path('/PRODUCT'), Path('/HARNESS')
        original = dict(commit='2' * 40, tree='3' * 40, status='', diffSha256='4' * 64)
        coordinator = original | dict(commit='5' * 40, tree='6' * 40)
        snapshots = {product: original, harness: coordinator}
        runner = Mock(source_snapshot=Mock(side_effect=lambda path: snapshots[path]))
        context = dict(host='linux-x64', root=str(product), source=original)
        with patch.object(m, 'ROOT', product), patch.object(m, 'HARNESS_ROOT', harness):
            self.assertEqual(m.bind_sources(runner, context), coordinator)
            self.assertEqual(context['source'], original)
            for changed in (dict(host='apple-arm64'), dict(root='/OTHER'), dict(source={}),
                            dict(source=original | dict(commit='7' * 40))):
                with self.assertRaises(ValueError):
                    m.bind_sources(runner, context | changed)
            snapshots[harness] = coordinator | dict(status=' M scripts/run-rpc-mobile-capacity.py')
            with self.assertRaises(ValueError):
                m.bind_sources(runner, context)
            snapshots[harness], snapshots[product] = coordinator, original | dict(status=' M changed')
            with self.assertRaises(ValueError):
                m.bind_sources(runner, context)

    def test_cli_requires_canonical_product_checkout_before_constructing_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp).resolve()
            product = parent / 'source'
            product.mkdir()
            alias = parent / 'alias'
            alias.symlink_to(product, target_is_directory=True)
            for path, valid in ((product, True), (alias, False), (Path('relative'), False)):
                argv = ['run-rpc-mobile-capacity.py', '--owner-authorized-mobile', '--settings', '/PRIVATE',
                        '--mode', 'large', '--run-label', 'test-run', '--source', str(path)]
                with patch.object(sys, 'argv', argv), patch.object(m, 'ROOT', m.ROOT), patch.object(m, 'Run') as run:
                    if valid:
                        run.return_value.run.return_value = 0
                        self.assertEqual(m.main(), 0)
                        self.assertEqual(m.ROOT, product)
                        self.assertEqual(run.call_args.args[0].source, product)
                    else:
                        with self.assertRaises(ValueError):
                            m.main()
                        run.assert_not_called()


class Telemetry(unittest.TestCase):
    def test_failure_and_telemetry_commands_share_one_budget(self):
        run, clock = fixture(), [0.0]
        def read(name, timeout):
            if name == 'failed.txt':
                self.assertEqual(timeout, 4)
                clock[0] += 2
                return None
            self.assertEqual(timeout, 2)
            clock[0] += .25
            return row()
        run.phone.read.side_effect = read
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
            observed = run.sample()
        self.assertEqual(observed['sequence'], 1)
        self.assertEqual(run.last_sample, 2.25)
        self.assertEqual(len(run.samples), 1)
        run.lab.write_private.assert_called_once()

    def test_late_valid_new_row_does_not_refresh_the_budget_or_count_as_a_sample(self):
        run, clock = fixture(), [0.0]
        def read(name, timeout):
            clock[0] += 2.1
            return None if name == 'failed.txt' else row()
        run.phone.read.side_effect = read
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), self.assertRaises(ValueError):
            run.sample()
        self.assertEqual(run.samples, [])
        self.assertIsNone(run.last_sample)
        run.lab.write_private.assert_not_called()

    def test_duplicate_rows_never_refresh_freshness_and_stale_rows_are_refused(self):
        run, clock = fixture(), [0.0]
        run.phone.read.side_effect = lambda name, **_: None if name == 'failed.txt' else row()
        with patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]):
            run.sample()
            clock[0] = 1.0
            self.assertIsNone(run.sample())
            self.assertEqual(run.last_sample, 0)
            clock[0] = 4.5
            with self.assertRaises(ValueError):
                run.sample()
        self.assertEqual(len(run.samples), 1)
        run.lab.write_private.assert_called_once()

    def test_explicit_phone_failure_is_never_ignored_as_optional_missing_data(self):
        run = fixture()
        run.phone.read.return_value = dict(failed='true', phase='mobile-control')
        with self.assertRaises(ValueError):
            run.sample()
        self.assertEqual(run.phone.read.call_count, 1)
        run.lab.write_private.assert_not_called()


class Cleanup(unittest.TestCase):
    def test_controlled_stop_is_once_only_and_requires_exact_bound_healthy_cleanup(self):
        run = fixture()
        run.phone.read.return_value = closed()
        run.stop_phone()
        run.stop_phone()
        self.assertTrue(run.phone_stopped)
        self.assertEqual(run.phone.stop.call_count, 1)
        self.assertEqual(m.protocol.parse(run.phone.stop.call_args.args[0]), bound() | dict(action='stop'))
        for changed in (dict(runNonce='4' * 64), dict(runtimeClosed='false'), dict(clientPinsRemoved='false'),
                        dict(controlHealthy='false')):
            run = fixture()
            run.phone.read.return_value = closed() | changed
            with self.assertRaises(ValueError):
                run.stop_phone()
            run.stop_phone()
            self.assertFalse(run.phone_stopped)
            self.assertEqual(run.phone.stop.call_count, 1)  # No overwrite/retry of a possibly committed Stop.

    def test_partial_native_inventory_stops_before_jvm_clock_or_usb(self):
        run = fixture()
        run.state = Path('/NOT_EXECUTED/state')
        run.config = dict(runLabel='test-run')
        run.native = Mock(return_value={})
        run.output = Mock(return_value=b'OFFLINE-NOT-NATIVE-EVIDENCE')
        run.policy = Mock(unittest_count=Mock(return_value=126), control_inventory=Mock(return_value=127))
        with self.assertRaises(ValueError):
            run.prerequisites()
        self.assertEqual(run.native.call_count, 1)
        run.phone.start.assert_not_called()

    def test_receipt_must_match_source_context_ancestry_canonical_copy_and_retirement(self):
        run = fixture()
        run.context = dict(id='job', source=dict(commit='2' * 40), gradleHome='/PRIVATE/HOME')
        run.ancestry = ['owned-outer']
        run.control, run.state = Path('/NOT_EXECUTED/control'), Path('/NOT_EXECUTED/state')
        run.result['nativeCommands'] = {}
        good = dict(id='inner', jobId='job', host='linux-x64', kind='command', gradleHome='/PRIVATE/HOME',
                    sourceBefore=run.context['source'], sourceAfter=run.context['source'],
                    ancestorInvocationIds=run.ancestry, ownedSurvivors=[], errors=[],
                    ownership=dict(discoveryErrors=[]), stopExitCode=0)
        run.checker = Mock()
        run.runner = Mock(read_json=Mock(return_value=good), file_digest=Mock(return_value='3' * 64))
        self.assertEqual(run.check_receipt('mobile-client', ['OFFLINE-NOT-EXECUTED'], 0), good)
        for changed in (dict(jobId='other'), dict(host='apple-arm64'), dict(kind='gradle'),
                        dict(gradleHome='/OTHER'), dict(sourceAfter={}), dict(ancestorInvocationIds=[]),
                        dict(ownedSurvivors=['unknown']), dict(errors=['unknown']),
                        dict(ownership=dict(discoveryErrors=['unknown'])), dict(stopExitCode=1)):
            run.runner.read_json.return_value = good | changed
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                run.check_receipt('mobile-client', ['OFFLINE-NOT-EXECUTED'], 0)
        run.runner.read_json.side_effect = [good, good | dict(id='substituted')]
        with self.assertRaises(ValueError):
            run.check_receipt('mobile-client', ['OFFLINE-NOT-EXECUTED'], 0)

    def finish_fixture(self, directory):
        run = fixture()
        run.result.update(status='MECHANICAL_PASS_PENDING_NETWORK_AND_RESOURCE_REVIEW')
        run.phone_stopped, run.stop_attempted = True, True
        run.context = dict(id='job', source={'commit': '2' * 40})
        run.harness_source = run.context['source']
        run.client = run.client_log = run.client_proof = None
        run.client_id = 'OWNED-OFFLINE-ID'
        run.client_argv = ['OFFLINE-NOT-EXECUTED']
        run.state, run.control = directory / 'state', directory
        run.runner = Mock(source_snapshot=Mock(return_value=run.context['source']))
        run.commands = Mock(rows=[])
        run.phone.close.return_value = dict(privateServerExited=True, testHostKeysRetired=True,
                                           deviceUsbAuthorizationRevoked=False)
        return run

    def test_cleanup_requests_only_exact_owned_invocation_and_keeps_failure_visible(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m.evidence, 'clock_snapshot', return_value={}):
            run = self.finish_fixture(Path(tmp))
            run.result['errors'].append(dict(phase='execution', error='ValueError'))
            run.client = Mock(poll=Mock(return_value=None), wait=Mock(return_value=1))
            run.check_receipt = Mock(return_value={})
            run.finish()
            run.runner.request_cancellation.assert_called_once_with(run.state, 'job', 'OWNED-OFFLINE-ID')
            run.client.wait.assert_called_once_with(timeout=150)
            run.check_receipt.assert_called_once_with('mobile-client', ['OFFLINE-NOT-EXECUTED'], 1)
            self.assertEqual(run.result['status'], 'FAIL')
            run.phone.close.assert_called_once()

    def test_already_exited_client_still_requires_receipt_and_usb_cleanup_failure_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m.evidence, 'clock_snapshot', return_value={}):
            run = self.finish_fixture(Path(tmp))
            run.client = Mock(poll=Mock(return_value=0), wait=Mock(return_value=0))
            run.check_receipt = Mock(return_value={})
            run.phone.close.side_effect = ValueError('PRIVATE-NOT-EXPORTED')
            run.finish()
            run.runner.request_cancellation.assert_not_called()
            run.check_receipt.assert_called_once()
            self.assertEqual(run.result['status'], 'FAIL')
            self.assertNotIn('PRIVATE-NOT-EXPORTED', json.dumps(run.result))

    def test_full_duration_numeric_evidence_is_not_truncated_to_the_control_file_limit(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m.evidence, 'clock_snapshot', return_value={}):
            run = self.finish_fixture(Path(tmp))
            run.samples = [dict.fromkeys(m.protocol.NUMBERS, 10 ** 12) for _ in range(2400)]
            run.runner.write_new_json.side_effect = lambda path, value: path.write_text(json.dumps(value))
            run.finish()
            report = run.control / 'result.json'
            self.assertGreater(report.stat().st_size, lab.LIMIT)
            self.assertEqual(len(json.loads(report.read_text())['phoneSamples']), 2400)

    def test_failed_source_bound_measurement_survives_earlier_control_failure_without_passing(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m.evidence, 'clock_snapshot', return_value={}):
            run = self.finish_fixture(Path(tmp))
            run.directory = Path(tmp)
            run.mode = 'large'
            run.config = dict(runLabel='test-run')
            run.client_proof = {'id': 'OFFLINE'}
            run.result['errors'].append(dict(phase='execution', error='ValueError'))
            measured = dict(status='FAIL', OFFLINE_NOT_A_MEASUREMENT=True)
            (run.directory / 'launcher-result.json').write_text('FIXTURE-PATH-ONLY')
            value = dict(sourceSha=run.context['source']['commit'], runLabel='test-run', role='client',
                         mode='large', measurement=measured)
            run.lab.read_private.return_value = json.dumps(value).encode()
            with patch.object(m.evidence, 'measurement', return_value=measured) as validate:
                run.finish()
            validate.assert_called_once_with(measured, 'large')
            self.assertEqual(run.result['measurement'], measured)
            self.assertEqual(run.result['status'], 'FAIL')
            self.assertEqual(len(run.result['errors']), 1)

    def test_retained_measurements_still_require_exact_source_run_role_and_mode(self):
        for changed in (dict(sourceSha='4' * 40), dict(runLabel='other'), dict(mode='steady'), dict(role='host')):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as tmp, \
                    patch.object(m.evidence, 'clock_snapshot', return_value={}):
                run = self.finish_fixture(Path(tmp))
                run.directory, run.mode, run.config = Path(tmp), 'large', dict(runLabel='test-run')
                run.client_proof = {'id': 'OFFLINE'}
                (run.directory / 'launcher-result.json').write_text('FIXTURE-PATH-ONLY')
                value = dict(sourceSha=run.context['source']['commit'], runLabel='test-run', role='client',
                             mode='large', measurement={'OFFLINE': True}) | changed
                run.lab.read_private.return_value = json.dumps(value).encode()
                with patch.object(m.evidence, 'measurement') as validate:
                    run.finish()
                validate.assert_not_called()
                self.assertNotIn('measurement', run.result)
                self.assertEqual(run.result['status'], 'FAIL')

    def test_harness_or_product_drift_at_cleanup_cannot_leave_a_mechanical_pass(self):
        for drift in ('harness', 'product'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as tmp, \
                    patch.object(m.evidence, 'clock_snapshot', return_value={}):
                run = self.finish_fixture(Path(tmp))
                snapshots = [run.context['source'], run.harness_source]
                snapshots[0 if drift == 'product' else 1] = {}
                run.runner.source_snapshot.side_effect = snapshots
                run.finish()
                self.assertEqual(run.result['status'], 'FAIL')
                self.assertFalse(run.result['sourceUnchanged' if drift == 'product' else 'harnessUnchanged'])


class Workload(unittest.TestCase):
    def fixture(self):
        run = fixture()
        run.mode, run.config, run.context = 'large', dict(runLabel='test-run'), dict(source=dict(commit='2' * 40))
        run.started = m.time.monotonic()
        run.client_log = io.BytesIO()
        run.client = Mock(poll=Mock(side_effect=[None, 0]), wait=Mock(return_value=0))
        run.client_argv = ['OFFLINE-NOT-EXECUTED']
        run.check_receipt = Mock(return_value={'id': 'OFFLINE'})
        run.sample = Mock()
        run.live = Mock(side_effect=AssertionError('Do not re-poll the normal exit boundary'))
        measured = dict(status='PENDING_RESOURCE_AND_NETWORK_REVIEW', OFFLINE_NOT_A_MEASUREMENT=True)
        result = dict(sourceSha='2' * 40, runLabel='test-run', role='client', mode='large',
            status=measured['status'], measurement=measured, cleanup=dict(cleanupVerified=True, mechanicalChecksPassed=True))
        run.lab.read_private.side_effect = lambda path: json.dumps(result).encode() if path.name == 'launcher-result.json' \
            else b'closed=true\nfixturesRemoved=true\n'
        run.lab.parse.side_effect = m.protocol.parse
        before = {k: int(v) for k, v in row().items() if k in m.protocol.NUMBERS}
        run.wait_fresh = Mock(side_effect=[before, before | dict(sequence=66, uptimeMillis=66000)])
        return run, result, measured

    def test_client_normal_exit_between_polls_is_finalized_not_misreported_as_lost(self):
        run, _, measured = self.fixture()
        with patch.object(m.time, 'sleep'), patch.object(m.evidence, 'measurement', return_value=measured):
            run.workload()
        self.assertEqual(run.result['measurement'], measured)
        self.assertEqual(run.result['postRetention']['status'], 'PASS')
        self.assertEqual(run.client.poll.call_count, 2)
        run.live.assert_not_called()
        run.check_receipt.assert_called_once_with('mobile-client', run.client_argv, 0)

    def test_actual_failed_workload_is_retained_and_no_idle_gate_is_awarded(self):
        run, result, measured = self.fixture()
        measured['status'] = result['status'] = 'FAIL'
        run.client.wait.return_value = 1
        with patch.object(m.time, 'sleep'), patch.object(m.evidence, 'measurement', return_value=measured), \
                self.assertRaises(ValueError):
            run.workload()
        self.assertEqual(run.result['measurement'], measured)
        run.wait_fresh.assert_not_called()
        run.check_receipt.assert_called_once_with('mobile-client', run.client_argv, 1)

    def test_foreign_workload_is_not_attributed_to_the_bound_source(self):
        run, result, _ = self.fixture()
        result['sourceSha'] = '4' * 40
        with patch.object(m.time, 'sleep'), patch.object(m.evidence, 'measurement') as validate, \
                self.assertRaises(ValueError):
            run.workload()
        validate.assert_not_called()
        self.assertNotIn('measurement', run.result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
