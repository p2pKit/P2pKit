#!/usr/bin/env python3
"""Offline closed diagnostics; no product or Apple execution."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_product_diagnostics as d


class Diagnostics(unittest.TestCase):
    def test_discovery_wait_stages_remain_closed_not_payload_text_or_new_verdicts(self):
        for stage, marker in (('INITIAL_PEER', 'INITIAL_PEER_DISCOVERY_TIMEOUT'),
                              ('INITIAL_PEER_SET', 'INITIAL_PEER_SET_DISCOVERY_TIMEOUT'),
                              ('REDISCOVERY', 'PEER_REDISCOVERY_TIMEOUT')):
            case = ET.fromstring('<testcase><failure>TimeoutCancellationException private message\n'
                                 'Suppressed: AssertionError: APPLE_LAN_DISCOVERY_WAIT_TIMEOUT stage=' + stage +
                                 '\n</failure></testcase>')
            row = d.failure_locations(case, {})
            self.assertEqual(row, {'sourceLocations': [], 'markers': ['ASSERTION', marker, 'TIMEOUT']})
            self.assertNotIn('private', str(row))
        case = ET.fromstring('<testcase><failure>APPLE_LAN_DISCOVERY_WAIT_TIMEOUT stage=INITIAL_PEER_SECRET'
                             '</failure></testcase>')
        self.assertEqual(d.failure_locations(case, {})['markers'], [])

    def test_browser_diagnostic_allowlist_matches_test_source_enums_and_never_exports_unknown_text(self):
        import re
        source = (ROOT / 'library/p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/'
                  'AppleLanDiscoveryFailure.kt').read_text()
        enums = re.search(r'enum class AppleLanDiscoveryMarker \{([^}]+)}', source)[1]
        names = re.findall(r'\b[A-Z][A-Z_0-9]+\b', enums)
        self.assertEqual({'APPLE_LAN_' + name for name in names},
                         {key for key in d.FAILURE_MARKERS if key.startswith('APPLE_LAN_')})
        for name in names:
            case = ET.fromstring('<testcase><failure>Suppressed: APPLE_LAN_DISCOVERY_OBSERVED marker=' + name +
                                 '\nprivate-payload</failure></testcase>')
            self.assertEqual(d.failure_locations(case, {})['markers'], ['APPLE_LAN_' + name])
        for unknown in ('BROWSER_PRIVATE', 'private-key', 'BROWSER_READY_PRIVATE'):
            case = ET.fromstring('<testcase><failure>APPLE_LAN_DISCOVERY_OBSERVED marker=' + unknown +
                                 '</failure></testcase>')
            self.assertEqual(d.failure_locations(case, {})['markers'], [])

    def test_failure_sites_are_only_unambiguous_existing_source_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'library/x/src/commonTest/kotlin/Fixture.kt'
            path.parent.mkdir(parents=True)
            path.write_text('package sample\nclass Fixture {\n fun test() {}\n}\n')
            case = ET.fromstring('<testcase><failure>private payload\n'
                                 'Unexpected warn/error diagnostics recorded\n'
                                 'P2pKit stopped before the session could be committed\n'
                                 'at /private/path/Fixture.kt:3:9\n'
                                 'at Fixture.kt:999\n'
                                 'at Unchecked.kt:1\n'
                                 '</failure></testcase>')
            row = d.failure_locations(case, d.source_locations(root))
            self.assertEqual(row['sourceLocations'], [['library/x/src/commonTest/kotlin/Fixture.kt', 3]])
            self.assertEqual(row['markers'], ['SETUP_AFTER_STOP', 'UNEXPECTED_DIAGNOSTIC'])
            self.assertNotIn('private', str(row))
            duplicate = root / 'samples/x/src/jvmTest/kotlin/Fixture.kt'
            duplicate.parent.mkdir(parents=True)
            duplicate.write_text(path.read_text())
            self.assertEqual(d.failure_locations(case, d.source_locations(root))['sourceLocations'], [])

    def test_only_closed_markers_and_numeric_boot_states_leave_raw_logs(self):
        raw = b'private-token /private/path\nWaiting on Data Migration\nStatus=2, isTerminal=NO, Elapsed=01:59.\nNSPOSIXErrorDomain Code=60 private-message'
        row = d.log_observation(raw)
        self.assertEqual(row['markers'], ['WAIT_MIGRATION'])
        self.assertEqual(row['domains'], [{'domain': 'NSPOSIXErrorDomain', 'code': 60}])
        self.assertEqual(row['lastBootStatuses'], [{'status': 2, 'terminal': False, 'elapsedSeconds': 119}])
        value = {'logs': {'swift-simulator-readiness': {'stdout': row, 'stderr': d.log_observation(b'')}}}
        d.validate(value, ROOT, {'swift-simulator-readiness'})
        self.assertNotIn('private', str(value))
        for key, bad in [('markers', ['private-token']), ('sha256', 'private-value'), ('bytes', True)]:
            changed = copy.deepcopy(value)
            changed['logs']['swift-simulator-readiness']['stdout'][key] = bad
            with self.assertRaises(ValueError):
                d.validate(changed, ROOT, {'swift-simulator-readiness'})

    def test_arbitrary_finished_test_stack_is_not_simulator_boot_completion(self):
        self.assertNotIn('BOOT_FINISHED', d.log_observation(b'at private.testFinished(Fixture.kt:3)')['markers'])
        self.assertIn('BOOT_FINISHED', d.log_observation(b'\nFinished!\n')['markers'])

    def test_failed_test_names_are_bound_to_checked_in_source_not_messages(self):
        cls, method = next(iter(d.source_methods(ROOT)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'gradle').mkdir()
            (root / 'gradle/platform-test-policy.json').write_bytes((ROOT / 'gradle/platform-test-policy.json').read_bytes())
            p = root / 'library/x/src/commonTest/kotlin'
            p.mkdir(parents=True)
            package, name = cls.rsplit('.', 1)
            (p / 'Fixture.kt').write_text(f'package {package}\nclass {name} {{ fun {method}() {{}} }}')
            xml = root / 'library/x/build/test-results/iosX64Test'
            xml.mkdir(parents=True)
            (xml / 'TEST-fixture.xml').write_text(f'<testsuite><testcase classname="{cls}" name="{method}[iosX64]"><failure>secret payload</failure></testcase><testcase classname="private" name="secret"><error>secret</error></testcase></testsuite>')
            row = d.native_observation(root, {'buildFailed': True})
            self.assertEqual(row['failedMethods'], [[cls, method]])
            self.assertEqual(row['unmappedFailedMethods'], 1)
            self.assertEqual(row['attemptCounts'], dict(passed=0, failed=1, errors=1, skipped=0))
            self.assertFalse(row['executionAdmitted'])
            value = {'native': {'scoped-native': row}}
            d.validate(value, root, {'scoped-native'})
            self.assertNotIn('secret', str(value))
            row['failedMethods'].append(['private', 'secret'])
            with self.assertRaises(ValueError):
                d.validate(value, root, {'scoped-native'})

    def test_real_native_task_prefix_is_source_bound_on_both_architectures(self):
        for task, target in (('iosX64Test', 'iosX64'), ('iosSimulatorArm64Test', 'iosSimulatorArm64')):
            with self.subTest(task=task), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'gradle').mkdir()
                (root / 'gradle/platform-test-policy.json').write_bytes(
                    (ROOT / 'gradle/platform-test-policy.json').read_bytes())
                source = root / 'library/x/src/appleTest/kotlin/Fixture.kt'
                source.parent.mkdir(parents=True)
                source.write_text('package sample\nclass Fixture {\n fun test() {}\n}\n')
                xml = root / 'library/x/build/test-results' / task / 'TEST-fixture.xml'
                xml.parent.mkdir(parents=True)
                xml.write_text(f'<testsuite><testcase classname="{task}.sample.Fixture" '
                               f'name="test[{target}]"><failure>AssertionError at Fixture.kt:3 '
                               'private payload</failure></testcase></testsuite>')
                row = d.native_observation(root, {'buildFailed': True})
                self.assertEqual(row['failedMethods'], [['sample.Fixture', 'test']])
                self.assertEqual(row['unmappedFailedMethods'], 0)
                self.assertEqual(row['attemptCounts']['failed'], 1)
                self.assertEqual(row['failureDetails'], [{
                    'method': ['sample.Fixture', 'test'],
                    'sourceLocations': [['library/x/src/appleTest/kotlin/Fixture.kt', 3]],
                    'markers': ['ASSERTION'],
                }])
                self.assertFalse(row['executionAdmitted'])
                d.validate({'native': {'scoped-native': row}}, root, {'scoped-native'})
                self.assertNotIn('private', str(row))

    def test_wrong_task_or_recursive_prefix_does_not_become_a_source_identity(self):
        methods = {('sample.Fixture', 'test')}
        for cls in ('iosSimulatorArm64Test.sample.Fixture',
                    'iosX64Test.iosX64Test.sample.Fixture',
                    'untrusted.sample.Fixture', 'iosX64Test.private.Secret'):
            with self.subTest(cls=cls):
                case = ET.fromstring(f'<testcase classname="{cls}" name="test[iosX64]"/>')
                self.assertIsNone(d.source_method_identity(case, 'iosX64Test', methods))

    def test_no_entity_expansion_or_diagnostic_admission(self):
        value = {'native': {'scoped-native': d.native_observation(ROOT, None)}}
        value['native']['scoped-native']['executionAdmitted'] = True
        with self.assertRaises(ValueError):
            d.validate(value, ROOT, {'scoped-native'})
        with self.assertRaises(ValueError):
            d.validate({'simulator': {'states': {'known': 'private'}}}, ROOT, {'known'})
        with self.assertRaises(ValueError):
            d.validate({'simulator': {'version': 'secret', 'architectures': ['arm64']}}, ROOT, set())
        with self.assertRaises(ValueError):
            d.validate({'private': 'secret'}, ROOT, set())

    def test_failed_tasks_remain_observations_not_admitted_counts(self):
        task = ':p2p-core:iosX64Test'
        report = {'buildFailed': True, 'tests': {task: dict(outcome='FAILED', enabled=True, inGraph=True,
                                                         passed=30, failed=1, skipped=0)}}
        row = d.native_observation(ROOT, report)
        self.assertEqual(row['tasks'][task]['failed'], 1)
        self.assertFalse(row['executionAdmitted'])
        d.validate({'native': {'scoped-native': row}}, ROOT, {'scoped-native'})


class IntelEnvironment(unittest.TestCase):
    MEMORY = (b'Mach Virtual Memory Statistics: (page size of 4096 bytes)\n'
              b'Pages free:                              200.\n'
              b'Pages active:                            100.\n'
              b'Pages inactive:                          300.\n'
              b'Pages wired down:                        400.\n'
              b'Pages occupied by compressor:              5.\n'
              b'Swapins:                                  20.\n'
              b'Swapouts:                                 30.\n')

    def observations(self):
        return {kind: d.intel_environment_observation(kind, raw) for kind, raw in (
            ('hardware', b'17179869184\n4\n'), ('memory', self.MEMORY),
            ('processes', b'0.0 2048 S /private/path/DataMigrator\n'))}

    def test_hardware_and_vm_snapshots_keep_only_closed_numeric_observations(self):
        rows = self.observations()
        self.assertEqual(rows['hardware']['memoryBytes'], 17179869184)
        self.assertEqual(rows['hardware']['logicalCpus'], 4)
        self.assertEqual(rows['memory']['pageSizeBytes'], 4096)
        self.assertEqual(rows['memory']['fields'], {'freePages': 200, 'activePages': 100, 'inactivePages': 300,
            'wiredPages': 400, 'compressorPages': 5, 'swapins': 20, 'swapouts': 30})
        value = {'intelEnvironment': {'before': rows, 'after': copy.deepcopy(rows)}}
        self.assertEqual(d.validate(value, ROOT, set()), value)
        self.assertNotIn('private', str(value))

    def test_load_and_tool_flags_are_metadata_not_process_or_ownership_proof(self):
        raw = dict(loadMilli=[2500, 1250, 3750], psSetuid=True, psSetgid=False,
                   psOwnedByRoot=True, unprivileged=True)
        row = d.intel_environment_observation('host', json.dumps(raw).encode())
        self.assertEqual({k: row[k] for k in raw}, raw)
        partial = {'intelEnvironment': {'before': {'host': row}}}
        self.assertEqual(d.validate(partial, ROOT, set()), partial)
        self.assertNotIn('executionAdmitted', str(partial))
        self.assertNotIn('processes', str(partial))
        for change in (dict(path='/private'), dict(loadMilli=[True, 0, 0]), dict(loadMilli=[1, 2]),
                       dict(psSetuid=1), dict(unprivileged=False), dict(psOwnedByRoot='private')):
            with self.assertRaises(ValueError):
                d.intel_environment_observation('host', json.dumps({**raw, **change}).encode())
        with self.assertRaises(ValueError):
            d.intel_environment_observation('host', b'{"psSetuid":true,"psSetuid":false}')

    def test_known_process_aggregates_discard_all_paths_arguments_unknown_names_and_ids(self):
        row = d.intel_environment_observation('processes',
            b' 101.1 120 R /private/path/DataMigrator\n'
            b' 0.01 40 U /another/path/DataMigrator\n'
            b' 0 50 S+ /private/path/com.apple.CoreSimulator.CoreSimulatorService\n'
            b' 99.9 999 R /private/secret-process\n'
            b' 0.0 99 S /private/DataMigrator --secret argument\n')
        self.assertEqual(row['observedProcesses'], 5)
        self.assertEqual(row['roles']['DataMigrator'], dict(count=2, cpuMilliPercent=101110,
                                                          residentKiB=160, running=1, uninterruptible=1, other=0))
        self.assertEqual(set(row['roles']), {'DataMigrator', 'com.apple.CoreSimulator.CoreSimulatorService'})
        for forbidden in ('private', 'secret', 'argument', '999', 'pid', '/path/'):
            self.assertNotIn(forbidden, str(row['roles']))

    def test_malformed_missing_excessive_or_duplicate_snapshots_fail_closed(self):
        cases = [('hardware', b''), ('hardware', b'1\n4\nextra\n'), ('hardware', b'1\n0\n'),
                 ('hardware', b'-1\n4\n'), ('memory', b''),
                 ('memory', self.MEMORY.replace(b'Pages free:', b'Missing:')),
                 ('memory', self.MEMORY.replace(b'4096 bytes', b'1234 bytes')),
                 ('memory', self.MEMORY + b'Pages active: 100.\n'),
                 ('processes', b''), ('processes', b'PID private-text\n'),
                 ('processes', b'0.0 -1 S DataMigrator\n'), ('unknown', b'0\n')]
        for kind, raw in cases:
            with self.subTest(kind=kind, raw=raw[:40]), self.assertRaises(ValueError):
                d.intel_environment_observation(kind, raw)
        with self.assertRaises(ValueError):
            d.intel_environment_observation('processes', '0 1 S DataMigrator')
        with self.assertRaises(ValueError):
            d.intel_environment_observation('processes', b'x' * (d.MAX_XML + 1))

    def test_public_schema_rejects_unknown_keys_names_boolean_counts_and_inconsistent_totals(self):
        original = {'intelEnvironment': {'before': self.observations()}}
        for mutate in (
                lambda v: v['intelEnvironment'].update(secret={}),
                lambda v: v['intelEnvironment']['before'].update(secret={}),
                lambda v: v['intelEnvironment']['before']['hardware'].update(path='/private/path'),
                lambda v: v['intelEnvironment']['before']['hardware'].update(logicalCpus=True),
                lambda v: v['intelEnvironment']['before']['memory']['fields'].update(secret=1),
                lambda v: v['intelEnvironment']['before']['processes']['roles'].update(secret={}),
                lambda v: v['intelEnvironment']['before']['processes'].update(observedProcesses=0),
                lambda v: v['intelEnvironment']['before']['processes']['roles']['DataMigrator'].update(count=2),
                lambda v: v['intelEnvironment']['before']['processes']['roles']['DataMigrator'].update(other=True),
                lambda v: v['intelEnvironment']['before']['processes'].update(sha256='private')):
            value = copy.deepcopy(original)
            mutate(value)
            with self.assertRaises(ValueError):
                d.validate(value, ROOT, set())


if __name__ == '__main__':
    unittest.main(verbosity=2)
