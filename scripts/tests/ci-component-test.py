#!/usr/bin/env python3
"""Component routing and real task coverage, independent of remote execution."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ci_component', ROOT / 'scripts/ci_component.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

class ComponentTests(unittest.TestCase):
    def test_all_is_complete_and_unique(self):
        rows = C.matrix('all')['include']
        self.assertEqual(len(rows), 12)
        self.assertEqual({x['component'] for x in rows}, set(C.COMPONENTS))
    def test_work_budget_has_explicit_job_upload_headroom(self):
        for row in C.matrix('all')['include']:
            self.assertEqual(row['job_minutes'], row['minutes'] + 10)
    def test_source_uses_actual_workflow_expression_linter(self):
        command = next(argv for name, argv in C.commands('source') if name == 'workflow-syntax')
        self.assertEqual(command[0], 'actionlint')
        self.assertIn('.github/workflows/ci-component.yml', command)
        self.assertIn('.github/workflows/publish-maven-central.yml', command)
    def test_single_is_independent(self):
        self.assertEqual([x['component'] for x in C.matrix('android')['include']], ['android'])
    def test_unknown_duplicate_empty_refused(self):
        for value in ['', 'android,android', 'bogus', 'source,']:
            with self.subTest(value=value), self.assertRaises(ValueError): C.matrix(value)
    def test_gradle_calls_are_strict_and_cache_free(self):
        for component in C.COMPONENTS:
            for name, argv in C.commands(component):
                if 'gradlew' in argv[0]:
                    self.assertIn('--dependency-verification', argv)
                    self.assertIn('strict', argv)
                    self.assertIn('--no-build-cache', argv)
                    self.assertIn('--no-configuration-cache', argv)
    def test_rpc_library_and_sample_preserve_native_host_and_android_coverage(self):
        with tempfile.TemporaryDirectory(prefix='ci-rpc-routing-') as temporary:
            root = Path(temporary)
            with patch.object(C, 'ROOT', root):
                for component in ('jvm-linux', 'jvm-windows', 'android'):
                    self.assertFalse(any(':p2p-sample-rpc:' in arg
                                         for _, argv in C.commands(component) for arg in argv))
                (root / 'library/p2p-rpc').mkdir(parents=True)
                (root / 'samples/p2p-sample-rpc').mkdir(parents=True)
                for component in ('jvm-linux', 'jvm-windows'):
                    tasks = C.commands(component)[0][1]
                    self.assertEqual(tasks.count(':p2p-rpc:jvmTest'), 1)
                    self.assertEqual(tasks.count(':p2p-sample-rpc:jvmTest'), 1)
                    self.assertNotIn('--tests', tasks)
                tasks = C.commands('android')[0][1]
                self.assertEqual(tasks.count(':p2p-rpc:testAndroidHostTest'), 1)
                self.assertEqual(tasks.count(':p2p-sample-rpc:testAndroidHostTest'), 1)
                self.assertNotIn('--tests', tasks)

    def test_native_platform_acceptance_preserved(self):
        self.assertIn('full', C.commands('apple-arm64')[0][1])
        self.assertIn('ios-x64', C.commands('apple-x64')[0][1])
        self.assertEqual(C.COMPONENTS['apple-x64'][0], 'macos-15-intel')
    def test_all_installers_have_real_producer(self):
        for component, task in [('android', ':p2p-sample-android:assembleDebug'),
                                ('desktop-linux', ':p2p-sample-desktop-ui:packageDeb'),
                                ('desktop-windows', ':p2p-sample-desktop-ui:packageMsi'),
                                ('desktop-macos', ':p2p-sample-desktop-ui:packageDmg')]:
            self.assertTrue(any(task in argv for _, argv in C.commands(component)))
    def test_compatibility_has_actual_checks(self):
        names = {x[0] for x in C.commands('compatibility')}
        self.assertTrue({'abi-graph', 'api-abi', 'documentation', 'sbom', 'publication-shape',
                         'isolated-consumers', 'xcframework', 'minimum-apple-os', 'swift-ui'} <= names)
    def test_no_publish_or_bootstrap_commands(self):
        for c in C.COMPONENTS:
            text = str(C.commands(c))
            self.assertNotIn('initial-recipient', text)
            self.assertNotIn('publish-central-portal-bundle', text)
            self.assertNotIn('publishAllPublications', text)

    def execute_model(self, results, *, component='jvm-linux', tool_error=None):
        with tempfile.TemporaryDirectory(prefix='ci-component-model-') as temp:
            root = Path(temp)
            with patch.object(C, 'ROOT', root), patch.object(C, 'record_tools', side_effect=tool_error), \
                    patch.object(C, 'commands', return_value=[('actual-tests', ['synthetic-test'])]), \
                    patch.object(C.subprocess, 'run', side_effect=results) as invoked, \
                    patch.dict(C.os.environ, {'RUNNER_TEMP': temp}):
                error = None
                try:
                    code = C.execute(component)
                except RuntimeError as caught:
                    error, code = caught, None
                report = json.loads((root / 'build/reports/ci-component' / (component + '.json')).read_text())
                return code, report, invoked.call_args_list, error

    def test_original_task_failure_survives_cleanup_failure_and_stop_is_bounded(self):
        code, report, calls, error = self.execute_model([Mock(returncode=7), Mock(returncode=9)])
        self.assertIsNone(error)
        self.assertEqual((code, report['exitCode']), (7, 7))
        self.assertEqual(report['tasks'], [{'task': 'actual-tests', 'exitCode': 7},
                                           {'task': 'gradle-stop', 'exitCode': 9}])
        self.assertEqual(calls[-1].args[0][-1], '--stop')
        self.assertEqual(calls[-1].kwargs['timeout'], 90)

    def test_cleanup_failure_or_timeout_denies_pass_and_preserves_report(self):
        for outcome, expected in ((Mock(returncode=9), 9),
                                  (subprocess.TimeoutExpired(['synthetic-stop'], 90), 124),
                                  (OSError('synthetic unavailable tool'), 125)):
            with self.subTest(expected=expected):
                code, report, calls, error = self.execute_model([Mock(returncode=0), outcome])
                self.assertIsNone(error)
                self.assertEqual((code, report['exitCode']), (expected, expected))
                self.assertEqual(report['tasks'][-1], {'task': 'gradle-stop', 'exitCode': expected})
                self.assertEqual(len(calls), 2)

    def test_setup_failure_still_stops_gradle_and_writes_failure_report(self):
        original = RuntimeError('synthetic setup failure')
        code, report, calls, error = self.execute_model([Mock(returncode=0)], tool_error=original)
        self.assertIs(error, original)
        self.assertIsNone(code)
        self.assertEqual(report['exitCode'], 125)
        self.assertEqual(report['tasks'], [{'task': 'component-setup', 'exitCode': 125},
                                           {'task': 'gradle-stop', 'exitCode': 0}])
        self.assertEqual(len(calls), 1)

    def test_isolated_package_inspection_requires_successful_build_and_stop(self):
        code, report, calls, error = self.execute_model([Mock(returncode=0) for _ in range(4)], component='android')
        self.assertIsNone(error)
        self.assertEqual(code, 0)
        self.assertEqual([row['task'] for row in report['tasks']],
                         ['prepare-android', 'actual-tests', 'gradle-stop', 'inspect-android'])
        self.assertIn('prepare', calls[0].args[0])
        self.assertIn('package', calls[-1].args[0])
        self.assertEqual(calls[-1].args[0][calls[-1].args[0].index('--kind') + 1], 'android')
        code, report, calls, error = self.execute_model([Mock(returncode=0), Mock(returncode=7),
                                                        Mock(returncode=0)], component='desktop-linux')
        self.assertEqual(code, 7)
        self.assertNotIn('inspect-desktop', [row['task'] for row in report['tasks']])
        self.assertEqual(len(calls), 3)

    def test_source_component_does_not_launch_gradle_for_cleanup(self):
        code, report, calls, error = self.execute_model([Mock(returncode=0)], component='source')
        self.assertEqual(code, 0)
        self.assertIsNone(error)
        self.assertEqual(report['tasks'], [{'task': 'actual-tests', 'exitCode': 0}])
        self.assertEqual(len(calls), 1)

class SecurityInputTests(unittest.TestCase):
    def arguments(self, root):
        # Execute the actual argument-selection loop only: no tool installation,
        # scanner, network, vulnerability exception or private evidence access.
        source = (ROOT / 'scripts/setup-ci-component.sh').read_text()
        begin = source.index("    git ls-files '*gradle.lockfile' | while IFS= read -r path; do")
        end = source.index('\n    done', begin) + len('\n    done')
        result = subprocess.run(['bash', '-euo', 'pipefail', '-c', source[begin:end]],
                                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=10, check=True)
        self.assertEqual(result.stderr, b'')
        return result.stdout.decode().splitlines()

    def test_actual_security_inputs_equal_maintained_nonempty_lock_roster(self):
        expected = [line.strip() for line in (ROOT / '.github/workflows/osv-scanner.yml').read_text().splitlines()
                    if line.strip().startswith('--lockfile=')]
        actual = self.arguments(ROOT)
        self.assertEqual(sorted(actual), sorted(expected))
        self.assertEqual(len(actual), len(set(actual)))
        self.assertNotIn('--lockfile=./gradle.lockfile', actual)
        self.assertNotIn('--lockfile=./settings-gradle.lockfile', actual)

    def test_empty_roots_excluded_and_nonstandard_gradle_names_typed(self):
        with tempfile.TemporaryDirectory(prefix='ci-security-lock-model-') as temporary:
            root = Path(temporary)
            files = {'gradle.lockfile': '# empty root\nempty=runtimeClasspath\n',
                     'settings-gradle.lockfile': 'org.example:plugin:1=classpath\n',
                     'buildscript-gradle.lockfile': 'org.example:build:1=classpath\n',
                     'library/gradle.lockfile': 'org.example:library:1=runtimeClasspath\n',
                     'empty/gradle.lockfile': '# only comments\n',
                     'not-a-lock.txt': 'org.example:ignored:1=classpath\n'}
            for name, body in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body)
            for argv in (['git', 'init', '--quiet'], ['git', 'add', '.']):
                subprocess.run(argv, cwd=root, check=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=10)
            self.assertEqual(self.arguments(root), [
                '--lockfile=gradle.lockfile:./buildscript-gradle.lockfile',
                '--lockfile=./library/gradle.lockfile',
                '--lockfile=gradle.lockfile:./settings-gradle.lockfile'])


if __name__ == '__main__': unittest.main()
