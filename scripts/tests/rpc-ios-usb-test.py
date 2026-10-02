#!/usr/bin/env python3
"""Offline iPhone USB contract controls. Fake transports are NEVER device evidence."""
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_ios_usb as m
import rpc_mobile_usb as usb
spec = importlib.util.spec_from_file_location('ios_usb_test_files', ROOT / 'scripts/run-rpc-capacity-lab.py')
files = importlib.util.module_from_spec(spec)
spec.loader.exec_module(files)


def bound():
    return dict(schema='1', scope=m.protocol.SCOPE, runLabel='offline-ios', runNonce='1' * 64,
                hostPlatform='Ios', hostSourceSha='2' * 40, hostArtifactSha256='3' * 64)


def inbox():
    alphabet = 'abcdefghijklmnopqrstuvwxyz234567'
    pins = ['p2f1-' + 'a' * 50 + alphabet[i // 32] + alphabet[i % 32] for i in range(128)]
    return bound() | dict(hostAddress='192.168.14.2', hostPort='48123', hostInterface='en0',
                          subnets='192.168.14.0/24', clientPins=','.join(pins))


def prepared():
    b = bound()
    return dict(schema='1', scope='ios-usb-slot', runLabel=b['runLabel'], sourceSha=b['hostSourceSha'],
                artifactSha256=b['hostArtifactSha256'])


def telemetry():
    return bound() | m.protocol.RESOURCE_KINDS['Ios'] | dict(clock='host-run-monotonic') | \
        dict.fromkeys(m.protocol.NUMBERS, '0') | dict(sequence='1', uptimeMillis='1000', residentBytes='1048576', nativeThreads='12')


class FakeBackend:
    def __init__(self):
        self.records = {'prepared.txt': m.protocol.encode(prepared())}
        self.published = []
        self.verified = 0

    def verify(self, deadline):
        self.verified += 1

    def read(self, name, deadline):
        return self.records.get(name)

    def publish(self, name, raw, deadline):
        self.published.append((name, raw))


def fixture():
    backend, clock = FakeBackend(), [0.0]
    value = m.IosUsb(backend, bound(), owner_authorized=True, now=lambda: clock[0])
    value.start()
    value.provision(m.protocol.encode(inbox()))
    return value, backend, clock


class FileProtocol(unittest.TestCase):
    def test_complete_seal_binds_exact_name_length_and_digest(self):
        raw = b'schema=1\n'
        seal = m.input_seal('inbox.txt', raw)
        self.assertEqual(seal, ('schema=1\nname=inbox.txt\nbytes=9\nsha256=' + hashlib.sha256(raw).hexdigest() + '\n').encode())
        self.assertEqual(m.verify_input('inbox.txt', raw, seal), raw)
        for name, data, marker in (('stop.txt', raw, seal), ('inbox.txt', raw[:-1], seal),
                                   ('inbox.txt', raw, seal[:-1]), ('inbox.txt', b'schema=2\n', seal)):
            with self.subTest(name=name, data=data), self.assertRaises(ValueError):
                m.verify_input(name, data, marker)

    def test_invalid_names_empty_binary_or_oversize_records_are_rejected(self):
        for name, raw in (('../inbox.txt', b'x=1\n'), ('telemetry.txt', b'x=1\n'), ('stop.txt', b''),
                          ('inbox.txt', b'x=\0\n'), ('inbox.txt', b'x=' + b'a' * 16384)):
            with self.subTest(name=name), self.assertRaises(ValueError):
                m.input_seal(name, raw)

    def test_selected_device_requires_exact_wired_paired_ios_details(self):
        row = dict(identifier='SELECTED', connectionProperties=dict(transportType='wired', pairingState='paired'),
                   hardwareProperties=dict(platform='iOS'))
        m.selected_details(dict(result=row), 'SELECTED')
        for change in (dict(identifier='OTHER'), dict(connectionProperties=dict(transportType='wireless', pairingState='paired')),
                       dict(connectionProperties=dict(transportType='wired', pairingState='unpaired')),
                       dict(hardwareProperties=dict(platform='visionOS'))):
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.selected_details(dict(result=row | change), 'SELECTED')
        with self.assertRaises(ValueError):
            m.selected_details(dict(result=dict(devices=[row])), 'SELECTED')

    def test_missing_unknown_or_ambiguous_file_metadata_is_not_absence_or_a_regular_file(self):
        row = dict(name='prepared.txt', isDirectory=False, isSymbolicLink=False, fileSize=200)
        self.assertEqual(m.file_inventory(dict(result=dict(files=[row]))), {'prepared.txt': 200})
        self.assertEqual(m.file_inventory(dict(result=dict(files=[]))), {})
        for change in (dict(isDirectory=True), dict(isSymbolicLink=True), dict(fileSize=True), dict(fileSize=16385),
                       dict(name='../secret'), dict(name='unrelated.txt')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.file_inventory(dict(result=dict(files=[row | change])))
        for rows in ([row, row], [{k: v for k, v in row.items() if k != 'isSymbolicLink'}], None):
            with self.assertRaises(ValueError):
                m.file_inventory(dict(result=dict(files=rows)))

    def test_inbox_retains_full_binding_and_exactly_128_distinct_pins(self):
        self.assertEqual(m.inbox_record(m.protocol.encode(inbox()), bound()), inbox())
        for key, value in (('hostSourceSha', '4' * 40), ('hostPlatform', 'Android'), ('runNonce', '4' * 64),
                           ('hostArtifactSha256', '4' * 64), ('clientPins', ','.join(['p2f1-' + 'a' * 52] * 128)),
                           ('hostAddress', '127.0.0.1'), ('hostPort', '22'), ('hostInterface', '../en0'),
                           ('subnets', '0.0.0.0/0'), ('extra', 'field')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.inbox_record(m.protocol.encode(inbox() | {key: value}), bound())

    def test_one_exact_bounded_app_atomic_scratch_is_never_an_input_or_download(self):
        row = dict(name='.capacity-11111111-2222-3333-4444-555555555555',
                   isDirectory=False, isSymbolicLink=False, fileSize=0)
        self.assertEqual(m.file_inventory(dict(result=dict(files=[row]))), {})
        self.assertNotIn(row['name'], m.FILES)
        for rows in ([row, row | dict(name='.capacity-22222222-2222-3333-4444-555555555555')],
                     [row | dict(name='.capacity-unknown')], [row | dict(isSymbolicLink=True)]):
            with self.assertRaises(ValueError):
                m.file_inventory(dict(result=dict(files=rows)))


class StateMachine(unittest.TestCase):
    def test_explicit_authorization_precedes_any_backend_call(self):
        backend = Mock()
        with self.assertRaises(ValueError):
            m.IosUsb(backend, bound())
        backend.assert_not_called()
        self.assertEqual(backend.mock_calls, [])

    def test_android_or_changed_run_cannot_enter_ios_controller(self):
        for change in (dict(hostPlatform='Android'), dict(runLabel='../escape')):
            with self.assertRaises(ValueError):
                m.IosUsb(FakeBackend(), bound() | change, owner_authorized=True)

    def test_owner_prepared_slot_and_signed_executable_must_match_before_provisioning(self):
        for change in (dict(sourceSha='4' * 40), dict(artifactSha256='4' * 64), dict(runLabel='other'), dict(extra='field')):
            backend = FakeBackend()
            backend.records['prepared.txt'] = m.protocol.encode(prepared() | change)
            value = m.IosUsb(backend, bound(), owner_authorized=True)
            with self.assertRaises(ValueError):
                value.start()
            self.assertEqual(backend.published, [])

    def test_each_config_and_stop_publication_is_attempted_only_once_even_after_failure(self):
        backend = FakeBackend()
        value = m.IosUsb(backend, bound(), owner_authorized=True)
        value.start()
        backend.publish = Mock(side_effect=RuntimeError('synthetic partial copy'))
        with self.assertRaises(RuntimeError):
            value.provision(m.protocol.encode(inbox()))
        with self.assertRaises(ValueError):
            value.provision(m.protocol.encode(inbox()))
        self.assertEqual(backend.publish.call_count, 1)
        value, backend, _ = fixture()
        backend.publish = Mock(side_effect=RuntimeError('synthetic partial copy'))
        with self.assertRaises(RuntimeError):
            value.stop(m.protocol.encode(value.protocol.stop()))
        with self.assertRaises(ValueError):
            value.stop(m.protocol.encode(value.protocol.stop()))
        self.assertEqual(backend.publish.call_count, 1)

    def test_record_read_deadline_includes_backend_setup_and_verification(self):
        value, backend, clock = fixture()
        def late(name, deadline):
            self.assertEqual(deadline, 4)
            clock[0] = 4
            return m.protocol.encode(telemetry())
        backend.read = late
        with self.assertRaises(ValueError):
            value.read('telemetry.txt')
        self.assertIsNone(value.protocol.previous)

    def test_no_identity_role_artifact_or_monotonic_sample_substitution(self):
        value, backend, clock = fixture()
        raw = telemetry()
        backend.records['telemetry.txt'] = m.protocol.encode(raw)
        self.assertEqual(value.read('telemetry.txt'), raw)
        first = value.last_sample
        clock[0] = 1
        self.assertEqual(value.read('telemetry.txt'), raw)
        self.assertEqual(value.last_sample, first, 'An unchanged slot cannot refresh freshness')
        for change in (dict(sequence='0'), dict(runNonce='4' * 64), dict(hostArtifactSha256='4' * 64),
                       dict(cpuSource='jvm'), dict(uptimeMillis='0')):
            backend.records['telemetry.txt'] = m.protocol.encode(raw | change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                value.read('telemetry.txt')
        backend.records['telemetry.txt'] = m.protocol.encode(raw)
        clock[0] = 4.5
        with self.assertRaises(ValueError):
            value.read('telemetry.txt')

    def test_cleanup_requires_actual_bound_closed_record_not_copy_or_host_exit(self):
        value, backend, _ = fixture()
        value.stop(m.protocol.encode(value.protocol.stop()))
        bad = bound() | dict(runtimeClosed='true', clientPinsRemoved='false', controlHealthy='true')
        backend.records['closed.txt'] = m.protocol.encode(bad)
        with self.assertRaises(ValueError):
            value.read('closed.txt')
        self.assertFalse(value.runtime_closed)
        backend.records['closed.txt'] = m.protocol.encode(bad | dict(clientPinsRemoved='true'))
        value.read('closed.txt')
        result = value.close()
        self.assertTrue(result['runtimeClosed'])
        self.assertTrue(result['deviceEvidenceRetained'])
        self.assertTrue(result['requiresOuterNativeFinalization'])
        self.assertFalse(result['devicePairingRevoked'])
        self.assertFalse(result['capacityQualified'])

    def test_no_stop_or_foreign_closed_record_cannot_claim_retirement(self):
        value, backend, _ = fixture()
        backend.records['closed.txt'] = m.protocol.encode(bound() | dict(runtimeClosed='true', clientPinsRemoved='true', controlHealthy='true'))
        with self.assertRaises(ValueError):
            value.read('closed.txt')
        self.assertFalse(value.close()['runtimeClosed'])

    def test_failed_record_is_not_a_success_or_retriable_absence(self):
        value, backend, _ = fixture()
        backend.records['failed.txt'] = b'failed=true\nphase=mobile-control\n'
        with self.assertRaises(ValueError):
            value.read('failed.txt')


class NativeBackendPolicy(unittest.TestCase):
    def test_privileged_writable_or_foreign_developer_tool_is_rejected_before_read_or_execution(self):
        tool, info = Mock(), Mock()
        tool.resolve.return_value, info.resolve.return_value = tool, info
        valid = dict(st_mode=stat.S_IFREG | 0o755, st_uid=0, st_nlink=1, st_size=100)
        for change in (dict(st_mode=stat.S_IFREG | stat.S_ISUID | 0o755),
                       dict(st_mode=stat.S_IFREG | stat.S_ISGID | 0o755), dict(st_mode=stat.S_IFREG | 0o777),
                       dict(st_mode=stat.S_IFIFO | 0o600), dict(st_uid=1234), dict(st_nlink=2)):
            tool.lstat.return_value = SimpleNamespace(**(valid | change))
            with self.subTest(change=change), patch.object(m, 'DEVICECTL', tool), patch.object(m, 'COREDEVICE_INFO', info):
                with self.assertRaises(ValueError):
                    m.DevicectlFiles.__new__(m.DevicectlFiles).tool_binding()
                tool.read_bytes.assert_not_called()
                info.read_bytes.assert_not_called()

    def fixture(self, directory):
        value = m.DevicectlFiles.__new__(m.DevicectlFiles)
        value.directory = directory
        value.attempted = set()
        value.verify = Mock()
        value.inventory = Mock(return_value={'prepared.txt': 100})
        value.copy = Mock()
        value.download = Mock(return_value=b'x=1\n')
        value.commands = Mock(files=files)
        return value

    def test_staging_readback_precedes_seal_and_never_copies_to_canonical_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = self.fixture(Path(tmp).resolve())
            value.publish('inbox.txt', b'x=1\n', 30)
            calls = value.copy.call_args_list
            self.assertEqual([c.args[2] for c in calls], ['.incoming-inbox.txt', '.sealed-inbox.txt'])
            value.download.assert_called_once_with('.incoming-inbox.txt', 30)
            self.assertEqual(value.verify.call_count, 2)
            self.assertEqual(files.read_private(value.directory / 'seal-inbox.txt'), m.input_seal('inbox.txt', b'x=1\n'))
            with self.assertRaises(ValueError):
                value.publish('inbox.txt', b'x=1\n', 60)
            self.assertEqual(len(value.copy.call_args_list), 2)

    def test_corrupt_or_partial_device_copy_never_publishes_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = self.fixture(Path(tmp).resolve())
            value.download.return_value = b'x='
            with self.assertRaises(ValueError):
                value.publish('stop.txt', b'x=1\n', 30)
            self.assertEqual([c.args[2] for c in value.copy.call_args_list], ['.incoming-stop.txt'])
            self.assertIn('stop.txt', value.attempted)

    def test_preexisting_input_or_staging_is_preserved_not_overwritten(self):
        for name in ('inbox.txt', '.incoming-inbox.txt', '.sealed-inbox.txt'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                value = self.fixture(Path(tmp).resolve())
                value.inventory.return_value = {'prepared.txt': 100, name: 1}
                with self.assertRaises(ValueError):
                    value.publish('inbox.txt', b'x=1\n', 30)
                value.copy.assert_not_called()

    def test_copy_uses_only_exact_app_container_and_never_shell_launch_install_or_pair(self):
        value = m.DevicectlFiles.__new__(m.DevicectlFiles)
        value.directory, value.remote, value.selected = Path('/PRIVATE'), 'Library/Application Support/rpc-capacity/test', 'SELECTED'
        value.command = Mock()
        value.copy('to', Path('/PRIVATE/input'), '.incoming-inbox.txt', 30)
        args = value.command.call_args.args
        self.assertEqual(args[0], 'copy-to')
        self.assertEqual(args[1], ['device', 'copy', 'to', '--device', 'SELECTED', '--domain-type', 'appDataContainer',
            '--domain-identifier', 'dev.p2pkit.rpc.phonelab', '--source', '/PRIVATE/input', '--destination',
            'Library/Application Support/rpc-capacity/test/.incoming-inbox.txt'])
        with self.assertRaises(ValueError):
            value.copy('to', Path('/OTHER/input'), '.incoming-inbox.txt', 30)

    def test_local_copy_reader_rejects_symlinks_hardlinks_and_foreign_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve()
            value = self.fixture(directory)
            path = directory / 'copied'
            path.write_bytes(b'x=1\n')
            path.chmod(0o644)
            self.assertEqual(value.read_owned(path), b'x=1\n')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            linked = directory / 'link'
            linked.symlink_to(path)
            with self.assertRaises(ValueError):
                value.read_owned(linked)
            linked.unlink()
            os.link(path, linked)
            with self.assertRaises(ValueError):
                value.read_owned(path)
            linked.unlink()
            path.chmod(0o666)
            with self.assertRaises(ValueError):
                value.read_owned(path)

    def test_usb_log_or_input_setup_cannot_launch_after_the_original_deadline(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, P2PKIT_AUDIT_OWNERSHIP_CHAIN='OFFLINE'):
            value = usb.Commands(Path(tmp).resolve(), {}, files)
            with patch.object(usb.time, 'monotonic', side_effect=[0, 4]), patch.object(usb.subprocess, 'Popen') as popen:
                with self.assertRaises(ValueError):
                    value.run('offline-deadline', ['/NOT_EXECUTED'], timeout=4)
            popen.assert_not_called()
            self.assertEqual(value.rows[0]['exitCode'], None)

    def test_json_duplicate_fields_cannot_change_a_success_into_an_unrelated_response(self):
        with self.assertRaises(ValueError):
            m.unique([('result', {}), ('result', {'different': True})])


if __name__ == '__main__':
    unittest.main(verbosity=2)
