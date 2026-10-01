#!/usr/bin/env python3
"""Offline private phone protocol controls; not USB, native or mobile capacity evidence."""
import copy
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_mobile_capacity as m
import rpc_mobile_usb as usb


def binding(platform='Android'):
    return dict(schema='1', scope=m.SCOPE, runLabel='mobile-test', runNonce='1' * 64,
                hostPlatform=platform, hostSourceSha='2' * 40, hostArtifactSha256='3' * 64)


def telemetry(platform='Android', sequence=1, uptime=1000):
    return (binding(platform) | m.RESOURCE_KINDS[platform] | dict(clock='host-run-monotonic') |
            dict.fromkeys(m.NUMBERS, '0') | dict(sequence=str(sequence), uptimeMillis=str(uptime),
                                              residentBytes='1048576', nativeThreads='12'))


class ProtocolControls(unittest.TestCase):
    def test_exact_bounded_ascii_roundtrip_and_no_duplicate_or_empty_fields(self):
        original = binding()
        self.assertEqual(m.parse(m.encode(original)), original)
        for raw in (b'', b'\n', b'a=\n', b'a=b\na=c\n', b'a=b\r\n', b'a=\x00\n', b'a=\xff',
                    b'1a=b', b'a=' + b'b' * m.RECORD_LIMIT, b' a=b', b'a-b=c'):
            with self.subTest(raw=raw[:32]), self.assertRaises(ValueError):
                m.parse(raw)
        for bad in ({'a': 'b\nc=d'}, {'a': True}, {1: 'b'}):
            with self.assertRaises(ValueError):
                m.encode(bad)

    def test_source_artifact_platform_and_nonce_are_all_binding_fields(self):
        for platform in ('Android', 'Ios'):
            self.assertEqual(m.binding(binding(platform)), binding(platform))
        for key, value in (('schema', '2'), ('scope', 'public'), ('runLabel', '../test'),
                           ('hostPlatform', 'Jvm'), ('hostSourceSha', 'main'), ('runNonce', 'guess'),
                           ('hostArtifactSha256', '4' * 63), ('private', 'do-not-export')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.binding(binding() | {key: value})

    def test_readiness_binds_real_installed_artifact_kind_and_selected_endpoint(self):
        for platform in ('Android', 'Ios'):
            p = m.Protocol(binding(platform), '192.168.14.2', 48123)
            ready = binding(platform) | dict(fingerprint='p2f1-' + 'a' * 52, address='192.168.14.2', port='48123',
                compiledSourceMatched='true', artifactKind=m.ARTIFACT_KINDS[platform])
            self.assertEqual(p.ready(ready), ready)
            for key, bad in (('hostSourceSha', '4' * 40), ('hostArtifactSha256', '4' * 64), ('runNonce', '4' * 64),
                             ('address', '127.0.0.1'), ('port', '48124'), ('compiledSourceMatched', 'false'),
                             ('artifactKind', 'caller-supplied'), ('fingerprint', 'p2f1-' + 'a' * 51),
                             ('fingerprint', True), ('assumedTrust', 'true')):
                with self.subTest(platform=platform, key=key), self.assertRaises(ValueError):
                    p.ready(ready | {key: bad})

    def test_telemetry_has_actual_phone_collector_metadata_not_fake_jvm_fields(self):
        for platform in ('Android', 'Ios'):
            p = m.Protocol(binding(platform), '192.168.14.2', 48123)
            row = telemetry(platform)
            self.assertEqual(p.telemetry(row), {k: int(row[k]) for k in m.NUMBERS})
            for key, bad in (('jvmThreads', '1'), ('cpuSource', 'jvm'), ('nativeThreads', '0'), ('residentBytes', '0'),
                             ('clock', 'generator'), ('cpuNanos', '1'), ('hostPlatform', 'Jvm'),
                             ('queued', '257'), ('connected', '129'), ('running', '129'), ('records', '131073'),
                             ('payloadBytes', str(64 * 1048576 + 1)), ('completed', '-1'), ('accepted', '01'),
                             ('cpuNanos', str(2 ** 63)), ('sequence', '3000'), ('sequence', True)):
                with self.subTest(platform=platform, key=key), self.assertRaises(ValueError):
                    p.telemetry(row | {key: bad})

    def test_repeated_slot_never_advances_freshness_or_regresses_counters(self):
        p = m.Protocol(binding(), '192.168.14.2', 48123)
        row = telemetry() | dict(accepted='1', completed='1', cpuNanos='1000000')
        p.telemetry(row)
        self.assertIsNone(p.telemetry(row))
        for update in (dict(sequence='0'), dict(sequence='1', accepted='2'), dict(sequence='2'),
                       dict(sequence='2', uptimeMillis='2000', accepted='0'),
                       dict(sequence='2', uptimeMillis='2000', cpuNanos='0')):
            with self.assertRaises(ValueError):
                p.telemetry(row | update)
        next_row = row | dict(sequence='2', uptimeMillis='2000', accepted='2', completed='2')
        self.assertEqual(p.telemetry(next_row)['completed'], 2)

    def test_controlled_stop_is_exact_and_interrupted_cleanup_is_never_a_pass(self):
        p = m.Protocol(binding(), '192.168.14.2', 48123)
        self.assertEqual(p.stop(), binding() | dict(action='stop'))
        row = binding() | dict(runtimeClosed='true', clientPinsRemoved='true', controlHealthy='true')
        p.closed(row)
        for key, bad in (('runtimeClosed', 'false'), ('clientPinsRemoved', 'false'), ('controlHealthy', 'false'),
                         ('controlHealthy', True), ('runNonce', '4' * 64), ('assumedCleanup', 'true')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.closed(row | {key: bad})

    def test_post_retention_is_actual_phone_idle_counters_not_process_exit_or_rss_reset(self):
        p = m.Protocol(binding(), '192.168.14.2', 48123)
        before = p.telemetry(telemetry() | dict(accepted='20', completed='20', records='20', payloadBytes='40960'))
        after = p.telemetry(telemetry(sequence=67, uptime=66000) | dict(accepted='20', completed='20'))
        self.assertEqual(m.retention(before, after)['observedHostMillis'], 65000)
        for key, bad in (('uptimeMillis', 65999), ('records', 1), ('payloadBytes', 1), ('running', 1),
                         ('connected', 1), ('queued', 1), ('completed', 21), ('sequence', 1), ('residentBytes', 0)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.retention(before, after | {key: bad})
        with self.assertRaises(ValueError):
            m.retention(before | dict(connected=1), after)
        with self.assertRaises(ValueError):
            m.retention(before, after | dict(jvmThreads=1))

    def test_android_usb_is_explicit_paired_wired_not_emulator_network_or_automatic(self):
        serial = 'TEST_ONLY_SERIAL'
        original = 'List of devices attached\n' + serial + ' device usb:1-2 product:test transport_id:1\n'
        m.android_usb_inventory(original, serial)
        for bad in (original.replace(' usb:1-2', ''), original.replace(' device ', ' unauthorized '),
                    original + original.splitlines()[1] + '\n', original.replace('usb:1-2', 'usb:1-2 usb:2-3'),
                    original.replace(serial, 'emulator-5554'), original.replace(serial, '192.168.1.2:5555')):
            with self.assertRaises(ValueError):
                m.android_usb_inventory(bad, serial)
        for selected in ('emulator-5554', '192.168.1.2:5555', '../device', ''):
            with self.assertRaises(ValueError):
                m.android_usb_inventory(original, selected)

    def test_authorization_wait_observations_never_admit_a_device(self):
        raw = 'List of devices attached\nTEST_DEVICE unauthorized usb:1-2\n'
        self.assertEqual(m.android_usb_state(raw, 'TEST_DEVICE'), 'unauthorized')
        self.assertEqual(m.android_usb_state(raw.replace('unauthorized', 'offline'), 'TEST_DEVICE'), 'offline')
        self.assertEqual(m.android_usb_state('List of devices attached\n', 'TEST_DEVICE'), 'missing')
        for observed in (raw, raw.replace('unauthorized', 'offline'), 'List of devices attached\n'):
            with self.assertRaises(ValueError):
                m.android_usb_inventory(observed, 'TEST_DEVICE')

    def test_ios_details_cannot_assume_unknown_pairing_transport_or_device_identity(self):
        value = dict(result=dict(devices=[dict(identifier='TEST_ONLY_DEVICE', connectionProperties=dict(
            transportType='wired', pairingState='paired'), hardwareProperties=dict(platform='iOS'))]))
        m.ios_usb_details(value, 'TEST_ONLY_DEVICE')
        for key, bad in (('transportType', 'network'), ('transportType', 'tunnel'), ('pairingState', 'unpaired')):
            changed = copy.deepcopy(value)
            changed['result']['devices'][0]['connectionProperties'][key] = bad
            with self.assertRaises(ValueError):
                m.ios_usb_details(changed, 'TEST_ONLY_DEVICE')
        for bad in ({}, dict(result={}), dict(result=[]), dict(result=dict(device=dict(identifier='OTHER')))):
            with self.assertRaises(ValueError):
                m.ios_usb_details(bad, 'TEST_ONLY_DEVICE')
        with self.assertRaises(ValueError):
            m.ios_usb_details(dict(result=dict(devices=value['result']['devices'] * 2)), 'TEST_ONLY_DEVICE')

    def test_mac_available_pages_are_not_fabricated_phone_rss_or_linux_balloon_counters(self):
        raw = ('Mach Virtual Memory Statistics: (page size of 16384 bytes)\n'
               'Pages free: 10.\nPages inactive: 20.\nPages speculative: 5.\nPages active: 50.\n')
        self.assertEqual(m.parse_vm_stat(raw, 100 * 16384), 35 * 16384)
        for bad in (raw.replace('16384', '1024'), raw + 'Pages free: 1.\n', raw.replace('Pages free', 'free')):
            with self.assertRaises(ValueError):
                m.parse_vm_stat(bad, 100 * 16384)
        with self.assertRaises(ValueError):
            m.parse_vm_stat(raw, 1)


class AndroidUsbControls(unittest.TestCase):
    """Real bounded POSIX fixture files/processes, never ADB, Android, RPC or capacity execution."""
    def test_adb_cli_feature_lines_are_not_the_internal_comma_delimited_wire_reply(self):
        for raw in (b'cmd\nshell_v2\nstat_v2\n', b'shell_v2\ncmd\n', b'shell_v2\n', b'shell_v2'):
            with self.subTest(raw=raw):
                self.assertTrue(usb.android_shell_v2_supported(raw))

    def test_shell_v2_feature_admission_rejects_malformed_oversized_or_ambiguous_lists(self):
        for raw in (b'', b'cmd\n', b'cmd,shell_v2\n', b'shell_v2,cmd\n', b'cmd\nshell_v20\n',
                    b'cmd\nnot_shell_v2\n', b'shell_v2\nshell_v2\n', b'\nshell_v2\n', b'shell_v2\n\n',
                    b' shell_v2\n', b'shell_v2 \n', b'shell_v2\x00\n', b'\xff\nshell_v2\n',
                    b'shell_v2\n' + b'x' * 129 + b'\n', b'shell_v2\n' + b'x' * m.RECORD_LIMIT,
                    b'shell_v2\n' + b''.join(f'feature_{n}\n'.encode() for n in range(256)),
                    'shell_v2\n', None, bytearray(b'shell_v2\n')):
            with self.subTest(raw=str(raw)[:48]):
                self.assertFalse(usb.android_shell_v2_supported(raw))

    def run_script(self, directory, operation, name=None, data=b''):
        return subprocess.run(['/bin/sh', '-c', usb.android_script('test-run', operation, name)], cwd=directory,
            input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)

    def fixture(self, path):
        (path / 'no_backup').mkdir(mode=0o700)
        prepared = self.run_script(path, 'prepare', data=b'schema=1\n')
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        return path / 'no_backup/rpc-capacity/test-run'

    def test_fixed_shell_v2_grammar_preserves_stdin_exit_code_and_exact_script(self):
        for operation, name in (('prepare', None), ('stop', None), ('read', 'telemetry.txt')):
            args = usb.android_shell('test-run', operation, name)
            self.assertEqual(args[:-1], ['shell', '-T', '-e', 'none'])
            self.assertEqual(shlex.split(args[-1]), ['run-as', usb.ANDROID_PACKAGE, 'sh', '-c',
                                                  usb.android_script('test-run', operation, name)])
        for label in ('../directory', 'label;false', 'label\nfalse', '', 'A' * 65):
            with self.assertRaises(ValueError):
                usb.android_shell(label, 'prepare')
        for name in ('../inbox.txt', 'not-allowed.txt'):
            with self.assertRaises(ValueError):
                usb.android_shell('test-run', 'read', name)

    def test_immutable_private_input_publication_read_missing_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            run = self.fixture(base)
            self.assertEqual((run / 'inbox.txt').read_bytes(), b'schema=1\n')
            self.assertEqual((run / 'inbox.txt').stat().st_mode & 0o777, 0o600)
            self.assertEqual((run / 'inbox.txt').stat().st_nlink, 1)
            marker = run / '.complete-inbox.txt'
            self.assertEqual(marker.read_bytes(), b'')
            self.assertEqual(marker.stat().st_mode & 0o777, 0o600)
            self.assertEqual(marker.stat().st_nlink, 1)
            self.assertEqual(self.run_script(base, 'read', 'inbox.txt').stdout, b'schema=1\n')
            missing = self.run_script(base, 'read', 'ready.txt')
            self.assertEqual((missing.returncode, missing.stdout), (44, b''))
            stopped = self.run_script(base, 'stop', data=b'action=stop\n')
            self.assertEqual(stopped.returncode, 0, stopped.stderr)
            self.assertNotEqual(self.run_script(base, 'stop', data=b'action=changed\n').returncode, 0)
            self.assertEqual((run / 'stop.txt').read_bytes(), b'action=stop\n')
            self.assertFalse(list(run.glob('.usb-*')))

    def test_stop_is_not_visible_until_the_complete_input_has_arrived(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            run = self.fixture(base)
            child = subprocess.Popen(['/bin/sh', '-c', usb.android_script('test-run', 'stop')], cwd=base,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                child.stdin.write(b'action=')
                child.stdin.flush()
                deadline = time.monotonic() + 3
                while not (run / 'stop.txt').exists() or (run / 'stop.txt').stat().st_size == 0:
                    self.assertIsNone(child.poll())
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.01)
                self.assertFalse((run / '.complete-stop.txt').exists())
                incomplete = self.run_script(base, 'read', 'stop.txt')
                self.assertEqual((incomplete.returncode, incomplete.stdout), (44, b''))
            finally:
                child.stdin.write(b'stop\n')
                child.stdin.close()
                child.wait(timeout=5)
                out, err = child.stdout.read(), child.stderr.read()
                child.stdout.close()
                child.stderr.close()
            self.assertEqual(child.returncode, 0, err)
            self.assertEqual(out, b'')
            self.assertEqual((run / 'stop.txt').read_bytes(), b'action=stop\n')
            self.assertEqual((run / '.complete-stop.txt').read_bytes(), b'')

    def test_bad_file_types_links_modes_and_oversized_inputs_are_not_imported(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            run = self.fixture(base)
            self.assertNotEqual(self.run_script(base, 'stop', data=b'x' * 16385).returncode, 0)
            self.assertEqual((run / 'stop.txt').read_bytes(), b'x' * 16385)  # Failed bytes retained, not reclaimed.
            self.assertFalse((run / '.complete-stop.txt').exists())
            self.assertEqual(self.run_script(base, 'read', 'stop.txt').returncode, 44)
            self.assertNotEqual(self.run_script(base, 'stop', data=b'action=stop\n').returncode, 0)
            original = run / 'inbox.txt'
            target = base / 'unrelated'
            target.write_bytes(b'PRESERVE_FIXTURE')
            link = run / 'ready.txt'
            (run / '.complete-ready.txt').touch(mode=0o600)
            link.symlink_to(target)
            self.assertNotEqual(self.run_script(base, 'read', 'ready.txt').returncode, 0)
            self.assertEqual(target.read_bytes(), b'PRESERVE_FIXTURE')
            link.unlink()
            os.link(original, link)
            self.assertNotEqual(self.run_script(base, 'read', 'inbox.txt').returncode, 0)
            link.unlink()
            original.chmod(0o640)
            self.assertNotEqual(self.run_script(base, 'read', 'inbox.txt').returncode, 0)

    def test_sealed_missing_data_bad_markers_and_orphans_remain_invalid(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            run = self.fixture(base)
            marker = run / '.complete-stop.txt'
            marker.touch(mode=0o600)
            self.assertNotEqual(self.run_script(base, 'read', 'stop.txt').returncode, 0)
            self.assertNotEqual(self.run_script(base, 'stop', data=b'action=stop\n').returncode, 0)
            self.assertFalse((run / 'stop.txt').exists())
            marker.unlink()
            self.assertEqual(self.run_script(base, 'stop', data=b'action=stop\n').returncode, 0)
            marker.write_bytes(b'NOT-EMPTY')
            self.assertNotEqual(self.run_script(base, 'read', 'stop.txt').returncode, 0)
            marker.write_bytes(b'')
            marker.chmod(0o640)
            self.assertNotEqual(self.run_script(base, 'read', 'stop.txt').returncode, 0)
            marker.unlink()
            marker.symlink_to(run / '.complete-inbox.txt')
            self.assertNotEqual(self.run_script(base, 'read', 'stop.txt').returncode, 0)
            marker.unlink()
            os.link(run / '.complete-inbox.txt', marker)
            self.assertNotEqual(self.run_script(base, 'read', 'stop.txt').returncode, 0)
            marker.unlink()
            os.mkfifo(marker, 0o600)
            self.assertNotEqual(self.run_script(base, 'read', 'stop.txt').returncode, 0)

    def test_empty_publication_stays_unsealed_and_cannot_be_retried(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            run = self.fixture(base)
            self.assertNotEqual(self.run_script(base, 'stop', data=b'').returncode, 0)
            self.assertFalse((run / '.complete-stop.txt').exists())
            self.assertEqual(self.run_script(base, 'read', 'stop.txt').returncode, 44)
            self.assertNotEqual(self.run_script(base, 'stop', data=b'action=stop\n').returncode, 0)
            self.assertEqual((run / 'stop.txt').read_bytes(), b'')

    def test_concurrent_publishers_have_one_winner_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            run = self.fixture(base)
            (base / 'input').write_bytes(b'action=stop\n')
            inputs = [(base / 'input').open('rb') for _ in range(2)]
            children = [subprocess.Popen(['/bin/sh', '-c', usb.android_script('test-run', 'stop')], cwd=base,
                stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for source in inputs]
            try:
                for child in children:
                    child.wait(timeout=5)
                self.assertEqual(sum(child.returncode == 0 for child in children), 1)
            finally:
                for child in children:
                    child.stdout.close()
                    child.stderr.close()
                for source in inputs:
                    source.close()
            self.assertEqual(self.run_script(base, 'read', 'stop.txt').stdout, b'action=stop\n')
            self.assertEqual((run / 'stop.txt').read_bytes(), b'action=stop\n')

    def test_new_adb_keys_are_expected_under_only_the_new_home_dot_android(self):
        with tempfile.TemporaryDirectory(prefix='rpc-usb-') as temporary:
            directory = Path(temporary)
            commands = Mock(env={'HOME': '/UNRELATED', 'ANDROID_USER_HOME': '/UNRELATED', 'ADB_VENDOR_KEYS': '/UNRELATED'})
            control = usb.AndroidUsb(commands, directory, Path('/NOT_EXECUTED/adb'), 'TEST_DEVICE', 'test-run')
            control.verify = Mock()
            sock = socket.socket(socket.AF_UNIX)
            def launch(argv, **options):
                self.assertEqual(options['env']['HOME'], str(directory / 'adb-home'))
                self.assertEqual(options['env']['ANDROID_USER_HOME'], str(directory / 'adb-home/.android'))
                self.assertNotIn('ADB_VENDOR_KEYS', options['env'])
                self.assertEqual(options['env']['ADB_MDNS_AUTO_CONNECT'], '0')
                for name in ('adbkey', 'adbkey.pub'):
                    path = directory / 'adb-home/.android' / name
                    path.write_bytes(b'OFFLINE-NOT-A-KEY')
                    path.chmod(0o600)
                sock.bind(str(directory / 'adb.sock'))
                return Mock(poll=Mock(return_value=None), wait=Mock(return_value=0))
            try:
                with patch.object(usb.subprocess, 'Popen', side_effect=launch):
                    control.start()
                self.assertEqual({p.parent for p in control.key_identities}, {directory / 'adb-home/.android'})
                self.assertFalse(control.authorized)
                control.verify.assert_not_called()
                control.server.poll.return_value = 0
                result = control.close()
                self.assertTrue(result['testHostKeysRetired'])
                self.assertFalse(result['deviceUsbAuthorizationRevoked'])
                self.assertEqual(list(control.home.iterdir()), [])
            finally:
                sock.close()
                if control.log is not None and not control.log.closed:
                    control.log.close()

    def test_unauthorized_wait_is_before_import_and_cannot_admit_network_or_legacy_shell(self):
        with tempfile.TemporaryDirectory() as temporary:
            control = usb.AndroidUsb(Mock(), Path(temporary), Path('/NOT_EXECUTED/adb'), 'TEST_DEVICE', 'test-run')
            with self.assertRaises(ValueError):
                control.provision(b'schema=1\n')
            control.started = True
            control.adb_command = Mock(side_effect=[(0, b'TEST_DEVICE unauthorized usb:1-2\n'),
                (0, b'TEST_DEVICE device usb:1-2\n'), (0, b'TEST_DEVICE device usb:1-2\n'),
                (0, b'cmd\nshell_v2\nstat_v2\n'), (0, b'0\n')])
            with patch.object(usb.time, 'sleep'):
                control.await_authorization()
            self.assertTrue(control.authorized)
            self.assertEqual(control.adb_command.call_count, 5)
            control.adb_command = Mock(side_effect=[(0, b'TEST_DEVICE device usb:1-2\n'), (0, b'cmd\n')])
            with self.assertRaises(ValueError):
                control.verify()

    def test_partial_start_cleanup_has_defined_state_and_never_deletes_unknown_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            control = usb.AndroidUsb(Mock(), Path(temporary), Path('/NOT_EXECUTED/adb'), 'TEST_DEVICE', 'test-run')
            self.assertTrue(control.close()['privateServerExited'])
        with tempfile.TemporaryDirectory() as temporary:
            control = usb.AndroidUsb(Mock(), Path(temporary), Path('/NOT_EXECUTED/adb'), 'TEST_DEVICE', 'test-run')
            control.home.mkdir(parents=True)
            (control.home / 'unknown').write_bytes(b'PRESERVE_FIXTURE')
            with self.assertRaises(ValueError):
                control.close()
            self.assertEqual((control.home / 'unknown').read_bytes(), b'PRESERVE_FIXTURE')

    def test_telemetry_reobservation_shares_one_budget_instead_of_tripling_freshness(self):
        with tempfile.TemporaryDirectory() as temporary:
            control = usb.AndroidUsb(Mock(), Path(temporary), Path('/NOT_EXECUTED/adb'), 'TEST_DEVICE', 'test-run')
            control.provisioned = True
            control.adb_command = Mock(side_effect=[(45, b''), (0, b'sequence=2\n')])
            with patch.object(usb.time, 'monotonic', side_effect=[0, 0, 2]):
                self.assertEqual(control.read('telemetry.txt'), {'sequence': '2'})
            self.assertEqual([c.kwargs['timeout'] for c in control.adb_command.call_args_list], [4, 2])


if __name__ == '__main__':
    unittest.main(verbosity=2)
