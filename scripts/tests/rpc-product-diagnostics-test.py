#!/usr/bin/env python3
"""Offline closed diagnostics; no product or Apple execution."""
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_product_diagnostics as d


class Diagnostics(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
