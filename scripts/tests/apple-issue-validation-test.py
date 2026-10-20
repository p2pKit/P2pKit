#!/usr/bin/env python3
"""Offline wiring controls only; never native or physical acceptance."""
import json
import plistlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('apple_issue_validation', ROOT / 'scripts/run-apple-issue-validation.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE = {'commit': 'a' * 40, 'tree': 'b' * 40, 'status': '', 'diffSha256': 'c' * 64}


def result():
    return {'schema': 1, 'result': 'PASS', 'source': SOURCE, 'case': module.CASE,
            'nativeCase': {'identifier': module.CASE, 'status': 'Success'},
            'resultBundle': 'Logs/Test/swift-jvm-transfer-synthetic.xcresult',
            'transfers': [{'direction': direction, 'transferId': direction, 'bytes': 204800,
                           'sha256': 'a' * 64, 'sender': {'events': ['actual']}, 'receiver': {'events': ['actual']}}
                          for direction in ('swift-to-jvm', 'jvm-to-swift')],
            'cleanupErrors': [], 'unresolvedChildren': [], 'cliQuitWriteUtc': 'synthetic', 'cliQuitFlushedUtc': 'synthetic',
            'readiness': {'activity': {'producerRawNanoseconds': 10_000_000_000},
                          'firstOfferAccepted': {'hostRawNanoseconds': 20_000_000_000, 'monotonicSeconds': 340},
                          'absoluteDeadlineMonotonicSeconds': 360, 'finalUniqueActivityVerified': True}}


class Controls(unittest.TestCase):
    def test_device_recipe_uses_exact_fresh_absolute_derived_data_and_device_not_simulator(self):
        with tempfile.TemporaryDirectory() as temporary:
            derived = Path(temporary).resolve() / 'new/DerivedData'
            command = module.iphoneos_command(derived)
            self.assertEqual(str(derived), command[command.index('-derivedDataPath') + 1])
            self.assertEqual('iphoneos', command[command.index('-sdk') + 1])
            self.assertEqual('generic/platform=iOS', command[command.index('-destination') + 1])
            self.assertIn('CODE_SIGNING_ALLOWED=NO', command)
            self.assertEqual('build', command[-1])
            derived.mkdir(parents=True)
            with self.assertRaises(ValueError):
                module.iphoneos_command(derived)
            with self.assertRaises(ValueError):
                module.iphoneos_command(Path('relative/DerivedData'))

    def test_receipt_requires_actual_command_same_source_and_clean_finalization(self):
        valid = {'finalExitCode': 0, 'productExitCode': 0, 'stopExitCode': 0, 'sourceUnchanged': True,
                 'sourceBefore': SOURCE, 'sourceAfter': SOURCE, 'errors': [], 'ownedSurvivors': []}
        module.receipt_ok(valid, SOURCE)
        for key, value in [('productExitCode', None), ('stopExitCode', 1), ('sourceUnchanged', False),
                           ('sourceAfter', {}), ('errors', ['failure']), ('ownedSurvivors', ['live'])]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.receipt_ok({**valid, key: value}, SOURCE)

    def test_transfer_requires_native_method_two_full_transfers_and_natural_quit(self):
        bundle = [Path('swift-jvm-transfer-synthetic.xcresult')]
        module.transfer_ok(result(), SOURCE, bundle)
        for key, value in [('nativeCase', {}), ('transfers', []), ('cleanupErrors', ['timeout']),
                           ('unresolvedChildren', ['cli']), ('cliQuitTimeoutUtc', 'synthetic'),
                           ('cliQuitWriteUtc', None), ('result', 'FAIL'), ('source', {})]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.transfer_ok({**result(), key: value}, SOURCE, bundle)
        for bundles in ([], bundle * 2):
            with self.assertRaises(ValueError):
                module.transfer_ok(result(), SOURCE, bundles)
        for mutation in ('truncated', 'one-direction', 'missing-digest', 'missing-receiver'):
            value = result()
            row = value['transfers'][0]
            if mutation == 'truncated':
                row['bytes'] = 204799
            elif mutation == 'one-direction':
                row['direction'] = 'jvm-to-swift'
            elif mutation == 'missing-digest':
                row['sha256'] = ''
            else:
                row['receiver'] = {}
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                module.transfer_ok(value, SOURCE, bundle)

    def test_readiness_does_not_replace_transfer_or_extend_either_original_clock(self):
        for mutation in ('late-raw', 'late-absolute', 'nonunique', 'missing'):
            value = result()
            ready = value['readiness']
            if mutation == 'late-raw':
                ready['firstOfferAccepted']['hostRawNanoseconds'] = 130_000_000_000
            elif mutation == 'late-absolute':
                ready['firstOfferAccepted']['monotonicSeconds'] = 360
            elif mutation == 'nonunique':
                ready['finalUniqueActivityVerified'] = False
            else:
                ready.clear()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                module.transfer_ok(value, SOURCE, [Path('swift-jvm-transfer-synthetic.xcresult')])

    def test_device_product_inspection_rejects_simulator_and_missing_embedded_framework(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            app = directory / 'Build/Products/Debug-iphoneos/p2pkit-sample.app'
            framework = app / 'Frameworks/P2pKitShared.framework'
            framework.mkdir(parents=True)
            executable = app / 'p2pkit-sample'
            executable.write_bytes(b'synthetic app')
            binary = framework / 'P2pKitShared'
            binary.write_bytes(b'synthetic framework')
            info = {'CFBundleExecutable': 'p2pkit-sample', 'CFBundleSupportedPlatforms': ['iPhoneOS'],
                    'DTPlatformName': 'iphoneos'}
            (app / 'Info.plist').write_bytes(plistlib.dumps(info))
            def native(command, **_kwargs):
                if command[1] == 'lipo':
                    return b'arm64\n'
                if command[1] == 'vtool':
                    return b'platform IOS\nminos 14.0\n'
                return b'@rpath/P2pKitShared.framework/P2pKitShared\n'
            with mock.patch.object(module.subprocess, 'check_output', side_effect=native):
                module.inspect_iphoneos(directory, directory / 'product.json')
                document = json.loads((directory / 'product.json').read_text())
                self.assertEqual(str(app), document['product'])
                self.assertFalse(document['deviceInstalled'])
                self.assertFalse(document['signed'])
                binary.unlink()
                with self.assertRaises(ValueError):
                    module.inspect_iphoneos(directory, directory / 'missing.json')
                info['CFBundleSupportedPlatforms'] = ['iPhoneSimulator']
                (app / 'Info.plist').write_bytes(plistlib.dumps(info))
                with self.assertRaises(ValueError):
                    module.inspect_iphoneos(directory, directory / 'simulator.json')

    def test_failed_run_retains_original_log_even_without_a_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            state = parent / 'state'
            state.mkdir()
            log = parent / 'driver.log'
            log.write_bytes(b'original synthetic failure bytes')
            report = parent / 'reports'
            with mock.patch.object(module, 'REPORT', report), self.assertRaises(ValueError):
                module.retain(state, log)
            self.assertEqual(log.read_bytes(), (report / 'driver.log').read_bytes())

    def test_simulator_selects_exact_newest_available_shutdown_device_without_ambiguity(self):
        old = {'name': 'iPhone 17', 'isAvailable': True, 'state': 'Shutdown',
               'udid': '00000000-0000-0000-0000-000000000001'}
        new = {**old, 'udid': '00000000-0000-0000-0000-000000000002'}
        devices = {'com.apple.CoreSimulator.SimRuntime.iOS-26-2': [old],
                   'com.apple.CoreSimulator.SimRuntime.iOS-26-3': [new]}
        self.assertEqual(new['udid'], module.select_simulator(devices))
        devices['com.apple.CoreSimulator.SimRuntime.iOS-26-3'].append(old)
        with self.assertRaises(ValueError):
            module.select_simulator(devices)
        with self.assertRaises(ValueError):
            module.select_simulator({'com.apple.CoreSimulator.SimRuntime.iOS-26-3': [{**new, 'state': 'Booted'}]})

    def test_no_native_processes_from_non_macos_host(self):
        with mock.patch.object(module.platform, 'system', return_value='Linux'), \
                mock.patch.object(module.subprocess, 'call') as execute, self.assertRaises(ValueError):
            module.run(Path('/unused'), 'both')
        execute.assert_not_called()

    def test_workflow_encryption_step_describes_receipt_validation_not_native_execution(self):
        workflow = (ROOT / '.github/workflows/apple-issue-validation.yml').read_text()
        self.assertIn('scripts/run-apple-issue-validation.py run', workflow)
        self.assertIn('scripts/run-apple-issue-validation.py retain', workflow)
        self.assertIn("steps.native.outcome != 'skipped'", workflow)
        self.assertIn('--report-glob \'build/apple-issue-validation/**/*\'', workflow)
        self.assertNotIn('continue-on-error', workflow)
        self.assertNotIn('pull_request_target', workflow)
        self.assertNotIn('secrets.', workflow)


if __name__ == '__main__':
    unittest.main()
