#!/usr/bin/env python3
"""Component routing and real task coverage, independent of remote execution."""
import importlib.util
import json
import os
import signal
import threading
from contextlib import ExitStack
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
    def test_required_tool_version_parsing_accepts_windows_crlf_not_extra_content(self):
        with tempfile.TemporaryDirectory(prefix='ci-tools-crlf-') as temporary:
            root = Path(temporary)
            for name in ('java', 'gpg', 'gradlew'):
                (root / name).write_bytes(b'public synthetic executable')
            for newline in (b'\n', b'\r\n'):
                raw = newline.join((b'Gradle 9.7.0', b'--------------------', b''))
                # Retain the original demonstrated mismatch, not a Windows claim.
                self.assertEqual(C.re.search(r'(?m)^Gradle ([0-9A-Za-z.+-]+)$',
                                             raw.decode()) is None, newline == b'\r\n')
                versions = [Mock(stdout=b'openjdk version "17.0.20.1"' + newline),
                            Mock(stdout=b'gpg (GnuPG) 2.5.22' + newline), Mock(stdout=raw)]
                with patch.object(C, 'ROOT', root), \
                        patch.object(C.shutil, 'which', side_effect=lambda name: str(root / name)), \
                        patch.object(C.subprocess, 'run', side_effect=versions), \
                        patch.dict(C.os.environ, {'CI_EVIDENCE_TOOLS_FILE': str(root / 'tools.json')}):
                    C.record_tools('jvm-windows')
                self.assertEqual(json.loads((root / 'tools.json').read_text())['gradle']['version'], '9.7.0')
            with patch.object(C, 'ROOT', root), \
                    patch.object(C.shutil, 'which', side_effect=lambda name: str(root / name)), \
                    patch.object(C.subprocess, 'run', side_effect=[Mock(stdout=b'java version "17"'),
                        Mock(stdout=b'gpg (GnuPG) 2.5.22'), Mock(stdout=b'Gradle 9.7.0 PRIVATE_SUFFIX\r\n')]), \
                    patch.dict(C.os.environ, {'CI_EVIDENCE_TOOLS_FILE': str(root / 'tools.json')}):
                with self.assertRaisesRegex(RuntimeError, '^Cannot identify required tool: gradle$'):
                    C.record_tools('jvm-windows')

    def test_all_is_complete_and_unique(self):
        rows = C.matrix('all')['include']
        self.assertEqual(len(rows), 14)
        self.assertEqual({x['component'] for x in rows}, set(C.COMPONENTS))
    def test_work_budget_has_explicit_job_upload_headroom(self):
        for row in C.matrix('all')['include']:
            self.assertEqual(row['job_minutes'], row['minutes'] + 10)
    def test_source_uses_actual_workflow_expression_linter(self):
        command = next(argv for name, argv in C.commands('source') if name == 'workflow-syntax')
        self.assertEqual(command[0], 'actionlint')
        self.assertIn('.github/workflows/ci-component.yml', command)
        self.assertIn('.github/workflows/publish-maven-central.yml', command)
    def test_retained_publication_security_controls_are_in_source_component(self):
        expected = {
            'release-tag-controls': 'check-release-tag',
            'release-identity-controls': 'check-release-identity',
            'maven-environment-controls': 'check-maven-release-environment',
            'maven-namespace-controls': 'check-maven-namespace-access',
            'maven-coordinate-controls': 'check-maven-central-version',
            'maven-upload-controls': 'publish-central-portal-bundle'}
        actual = dict(C.commands('source'))
        for name, script in expected.items():
            self.assertEqual(actual[name], ['bash', 'scripts/tests/' + script + '-test.sh'])

    def test_signed_original_and_recovery_regressions_are_run_offline_in_source(self):
        actual = dict(C.commands('source'))
        for name in ('central-bundle-evidence-test.py', 'maven-recovery-test.py'):
            self.assertEqual(actual[name], [C.sys.executable, '-B', 'scripts/tests/' + name, '-v'])
        evidence_spec = importlib.util.spec_from_file_location('ci_evidence_routes', ROOT / 'scripts/ci_evidence.py')
        evidence = importlib.util.module_from_spec(evidence_spec)
        with patch.object(C.sys, 'path', [str(ROOT / 'scripts'), *C.sys.path]):
            evidence_spec.loader.exec_module(evidence)
        self.assertTrue(set(actual) <= evidence.TASK_NAMES)

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
                    tasks = dict(C.commands(component))['jvm-tests']
                    self.assertEqual(tasks.count(':p2p-rpc:jvmTest'), 1)
                    self.assertEqual(tasks.count(':p2p-sample-rpc:jvmTest'), 1)
                    self.assertNotIn('--tests', tasks)
                tasks = C.commands('android')[0][1]
                self.assertEqual(tasks.count(':p2p-rpc:testAndroidHostTest'), 1)
                self.assertEqual(tasks.count(':p2p-sample-rpc:testAndroidHostTest'), 1)
                self.assertNotIn('--tests', tasks)

    def test_additional_host_supervisor_route_has_exact_seven_genuine_cases(self):
        import ast
        evidence = ast.parse((ROOT / 'scripts/tests/ci-evidence-test.py').read_text())
        methods = {node.name for cls in evidence.body if isinstance(cls, ast.ClassDef) and cls.name == 'EvidenceTests'
                   for node in cls.body if isinstance(node, ast.FunctionDef)}
        expected = ('test_real_success_captures_both_private_streams_and_known_close',
                    'test_real_nonzero_is_preserved_and_not_relabelled_pass',
                    'test_real_timeout_retires_original_child',
                    'test_real_leader_exit_does_not_leave_child_writing',
                    'test_real_output_limit_is_enforced_during_capture',
                    'test_actual_scope_failed_postspawn_still_closes_original_pipes',
                    'test_real_cancellation_is_not_pass')
        self.assertTrue(set(expected) <= methods)
        self.assertEqual(C.SUPERVISOR_TESTS, tuple('EvidenceTests.' + name for name in expected))
        for component in C.COMPONENTS:
            selected = [(name, argv) for name, argv in C.commands(component) if name == 'supervisor-controls']
            self.assertEqual(len(selected), int(component in ('jvm-windows', 'desktop-macos')))
            if selected:
                self.assertEqual(C.commands(component)[0], selected[0])
                self.assertEqual(selected[0][1], [C.sys.executable, '-B', 'scripts/tests/ci-evidence-test.py',
                                                 '-v', *C.SUPERVISOR_TESTS])

    def test_windows_installer_retains_existing_rpc_preview_adapter_only_when_present(self):
        flag = '-Pp2pkit.rpc.windows.previewAdapter=true'
        with tempfile.TemporaryDirectory(prefix='ci-rpc-package-') as temporary:
            root = Path(temporary)
            with patch.object(C, 'ROOT', root):
                for present in (False, True):
                    if present:
                        (root / 'samples/p2p-sample-rpc').mkdir(parents=True)
                    for component in ('desktop-linux', 'desktop-windows', 'desktop-macos'):
                        argv = dict(C.commands(component))['desktop-tests-and-installer']
                        self.assertEqual(argv.count(flag), int(present and component == 'desktop-windows'))
                        self.assertIn(':p2p-sample-desktop-ui:createDistributable', argv)
                        self.assertNotIn('--tests', argv)

    def test_native_platform_acceptance_preserved(self):
        self.assertIn('ios-arm64', C.commands('apple-arm64')[0][1])
        self.assertEqual(C.COMPONENTS['macos-shared'], ('macos-15-intel', 120))
        self.assertEqual(C.commands('macos-shared'), [('shared-platform-tests',
                         [C.sys.executable, '-B', 'scripts/run-platform-tests.py', 'macos-shared'])])
        self.assertIn('ios-x64', C.commands('apple-x64')[0][1])
        self.assertEqual(C.COMPONENTS['apple-x64'][0], 'macos-15-intel')
    def test_all_installers_have_real_producer(self):
        for component, task in [('android', ':p2p-sample-android:assembleDebug'),
                                ('desktop-linux', ':p2p-sample-desktop-ui:packageDeb'),
                                ('desktop-windows', ':p2p-sample-desktop-ui:packageMsi'),
                                ('desktop-macos', ':p2p-sample-desktop-ui:packageDmg')]:
            self.assertTrue(any(task in argv for _, argv in C.commands(component)))
    def test_swift_ui_uses_exact_reviewed_runtime_and_retains_launcher_controls(self):
        command = dict(C.commands('compatibility'))['swift-ui']
        self.assertEqual(command, ['env', 'SIM_RUNTIME=com.apple.CoreSimulator.SimRuntime.iOS-26-5',
                                   'bash', 'scripts/run-ios-ui-tests.sh'])
        spec = importlib.util.spec_from_file_location('swift_simulator_policy', ROOT / 'scripts/hosted_full_simulator.py')
        policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)
        self.assertEqual(command[1], 'SIM_RUNTIME=' + policy.HOSTS['macos-arm64']['runtime'])
        self.assertEqual(dict(C.commands('source'))['ios-launcher-controls'],
                         ['bash', 'scripts/tests/run-ios-app-test.sh'])

    def test_compatibility_has_actual_checks(self):
        names = {x[0] for x in C.commands('compatibility')}
        self.assertTrue({'abi-graph', 'api-abi', 'documentation', 'sbom', 'publication-shape',
                         'signed-bundle-test', 'xcframework', 'minimum-apple-os', 'swift-ui'} <= names)
        self.assertNotIn('isolated-consumers', names)
    def test_complete_consumers_are_independent_mandatory_and_keep_cleanup(self):
        self.assertEqual(C.COMPONENTS['consumers'], ('macos-15-intel', 120))
        self.assertEqual(C.commands('consumers'),
                         [('isolated-consumers', ['bash', 'scripts/check-published-consumers.sh'])])
        spec = importlib.util.spec_from_file_location('component_qualification', ROOT / 'scripts/ci_qualification.py')
        qualification = importlib.util.module_from_spec(spec); spec.loader.exec_module(qualification)
        self.assertEqual(set(C.COMPONENTS), set(qualification.COMPONENTS))
        self.assertEqual({name: row[0] for name, row in C.COMPONENTS.items()}, qualification.RUNNERS)
        for component in ('apple-arm64', 'desktop-macos', 'compatibility'):
            self.assertEqual(C.COMPONENTS[component][0], 'macos-26')
        for status, stopped in ((0, 0), (7, 0), (0, 9), (7, 9)):
            code, report, calls, error = self.execute_model([Mock(returncode=status), Mock(returncode=stopped)],
                                                           component='consumers')
            self.assertIsNone(error)
            self.assertEqual(code, status or stopped)
            self.assertEqual(report['tasks'], [{'task': 'actual-tests', 'exitCode': status},
                                               {'task': 'gradle-stop', 'exitCode': stopped}])
            self.assertEqual(calls[-1].args[0][-1], '--stop')
            self.assertEqual(calls[-1].kwargs['timeout'], 90)

    def test_consumers_record_exact_xcode_and_refuse_other_versions(self):
        with tempfile.TemporaryDirectory(prefix='consumer-tool-model-') as temporary:
            root = Path(temporary)
            for name in ('java', 'gpg', 'gradlew', 'xcodebuild'):
                (root / name).write_bytes(b'synthetic public tool')
            for component in ("consumers", "published-consumers-diagnostic", "consumers-pom-diagnostic", "jmdns-diagnostic", "macos-shared"):
                for version in ('26.3', '26.5', '26.30'):
                    versions = [Mock(stdout=b'openjdk version "17"'), Mock(stdout=b'gpg (GnuPG) 2.5.22'),
                                Mock(stdout=b'Gradle 9.7.0\n'), Mock(stdout=('Xcode ' + version + '\nBuild version synthetic\n').encode())]
                    target = root / 'tools.json'
                    target.unlink(missing_ok=True)
                    with patch.object(C, 'ROOT', root), \
                            patch.object(C.shutil, 'which', side_effect=lambda name: str(root / name)), \
                            patch.object(C.subprocess, 'run', side_effect=versions), \
                            patch.dict(C.os.environ, {'CI_EVIDENCE_TOOLS_FILE': str(target)}):
                        if version == '26.3':
                            C.record_tools(component)
                            self.assertEqual(json.loads(target.read_text())['xcode']['version'], version)
                        else:
                            with self.assertRaisesRegex(RuntimeError, 'requires Xcode 26.3'):
                                C.record_tools(component)
                            self.assertFalse(target.exists())

    def assert_no_publish_or_bootstrap_commands(self, commands):
        text = str(commands)
        self.assertNotIn('initial-recipient', text)
        # Match the production script, not the separate offline -test.sh fixture.
        # Inspect all arguments, including shell strings and --script= wrappers.
        self.assertNotRegex(text, r'(?<![\w.-])publish-central-portal-bundle\.sh(?![\w.-])')
        self.assertNotIn('publishAllPublications', text)

    def test_no_publish_or_bootstrap_commands(self):
        for c in C.COMPONENTS:
            self.assert_no_publish_or_bootstrap_commands(C.commands(c))

    def test_publisher_guard_allows_only_fixture_not_wrapped_production(self):
        self.assert_no_publish_or_bootstrap_commands([
            ('fixture', ['bash', 'scripts/tests/publish-central-portal-bundle-test.sh'])])
        for argv in (
                ['scripts/publish-central-portal-bundle.sh'],
                ['bash', 'scripts/publish-central-portal-bundle.sh'],
                ['wrapper', '--script=scripts/publish-central-portal-bundle.sh'],
                ['wrapper', r'--script=C:\source\scripts\publish-central-portal-bundle.sh'],
                ['bash', '-c', 'exec scripts/publish-central-portal-bundle.sh "$@"'],
                ['./gradlew', ':p2p-core:publishAllPublicationsToMavenCentralRepository'],
                ['wrapper', '--script=scripts/initial-recipient-upload.py']):
            with self.subTest(argv=argv), self.assertRaises(AssertionError):
                self.assert_no_publish_or_bootstrap_commands([('forbidden', argv)])

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

    def test_bundle_diagnostic_explicit_only_and_never_in_required_all(self):
        self.assertEqual(C.DIAGNOSTICS, {'bundle-diagnostic': ('macos-26', 60), 'jmdns-diagnostic': ('macos-15-intel', 30),
                                       'published-consumers-diagnostic': ('macos-15-intel', 120),
                                       'consumers-pom-diagnostic': ('macos-15-intel', 60)})
        self.assertEqual(len(C.COMPONENTS), 14)
        self.assertNotIn('bundle-diagnostic', C.COMPONENTS)
        self.assertEqual({row['component'] for row in C.matrix('all')['include']}, set(C.COMPONENTS))
        self.assertEqual(C.matrix('bundle-diagnostic'), {'include': [{'component': 'bundle-diagnostic',
                         'os': 'macos-26', 'minutes': 60, 'job_minutes': 70}]})
        for invalid in ('bundle-diagnostic,source', 'compatibility,bundle-diagnostic',
                        'bundle-diagnostic,bundle-diagnostic', 'all,bundle-diagnostic'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                C.matrix(invalid)

    def test_pom_diagnostic_is_explicit_only_and_preserves_original_failure_and_cleanup(self):
        self.assertEqual(C.matrix('consumers-pom-diagnostic'), {'include': [{'component': 'consumers-pom-diagnostic',
                         'os': 'macos-15-intel', 'minutes': 60, 'job_minutes': 70}]})
        self.assertNotIn('consumers-pom-diagnostic', C.COMPONENTS)
        self.assertEqual(len(C.matrix('all')['include']), 14)
        self.assertEqual(C.commands('consumers-pom-diagnostic'), [('published-pom-diagnostic',
                         ['bash', 'scripts/check-published-consumers.sh', '--pom-diagnostic'])])
        self.assertEqual(C.commands('consumers'), [('isolated-consumers',
                         ['bash', 'scripts/check-published-consumers.sh'])])
        for invalid in ('consumers-pom-diagnostic,source', 'all,consumers-pom-diagnostic'):
            with self.assertRaises(ValueError):
                C.matrix(invalid)
        for status, stopped in ((0, 0), (7, 0), (0, 9), (7, 9)):
            code, report, calls, error = self.execute_model([Mock(returncode=status), Mock(returncode=stopped)],
                                                           component='consumers-pom-diagnostic')
            self.assertIsNone(error)
            self.assertEqual(code, status or stopped)
            self.assertEqual(report['tasks'], [{'task': 'actual-tests', 'exitCode': status},
                                               {'task': 'gradle-stop', 'exitCode': stopped}])
            self.assertEqual(calls[-1].args[0][-1], '--stop')
            self.assertEqual(calls[-1].kwargs['timeout'], 90)
            self.assertEqual(len(calls), 2)

    def test_published_consumer_diagnostic_has_fixed_remote_scope_and_preserves_failure_cleanup(self):
        name = 'published-consumers-diagnostic'
        self.assertEqual(C.matrix(name), {'include': [{'component': name,
                         'os': 'macos-15-intel', 'minutes': 120, 'job_minutes': 130}]})
        self.assertNotIn(name, C.COMPONENTS)
        self.assertEqual(len(C.matrix('all')['include']), 14)
        self.assertEqual(C.commands(name), [(name, ['env',
            'P2PKIT_CONSUMER_REPOSITORY_URL=https://repo.maven.apache.org/maven2',
            'bash', 'scripts/check-published-consumers.sh', '--latest-published'])])
        self.assertEqual(C.commands('consumers'), [('isolated-consumers',
                         ['bash', 'scripts/check-published-consumers.sh'])])
        evidence_spec = importlib.util.spec_from_file_location('ci_evidence_remote_routes', ROOT / 'scripts/ci_evidence.py')
        evidence = importlib.util.module_from_spec(evidence_spec)
        with patch.object(C.sys, 'path', [str(ROOT / 'scripts'), *C.sys.path]):
            evidence_spec.loader.exec_module(evidence)
        self.assertTrue({task for task, argv in C.commands(name)} <= evidence.TASK_NAMES)
        for invalid in (name + ',source', 'all,' + name, name + ',' + name):
            with self.assertRaises(ValueError):
                C.matrix(invalid)
        for status, stopped in ((0, 0), (7, 0), (0, 9), (7, 9)):
            code, report, calls, error = self.execute_model([Mock(returncode=status), Mock(returncode=stopped)],
                                                           component=name)
            self.assertIsNone(error)
            self.assertEqual(code, status or stopped)
            self.assertEqual(report['tasks'], [{'task': 'actual-tests', 'exitCode': status},
                                               {'task': 'gradle-stop', 'exitCode': stopped}])
            self.assertEqual(calls[-1].args[0][-1], '--stop')
            self.assertEqual(calls[-1].kwargs['timeout'], 90)
            self.assertEqual(len(calls), 2)

    def test_jmdns_diagnostic_is_focused_independent_and_preserves_failure_cleanup(self):
        self.assertEqual(C.matrix('jmdns-diagnostic'), {'include': [{'component': 'jmdns-diagnostic',
                         'os': 'macos-15-intel', 'minutes': 30, 'job_minutes': 40}]})
        self.assertNotIn('jmdns-diagnostic', C.COMPONENTS)
        self.assertEqual(len(C.matrix('all')['include']), 14)
        for invalid in ('jmdns-diagnostic,source', 'bundle-diagnostic,jmdns-diagnostic',
                        'jmdns-diagnostic,jmdns-diagnostic', 'all,jmdns-diagnostic'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                C.matrix(invalid)
        command = C.commands('jmdns-diagnostic')
        self.assertEqual(len(command), 1)
        self.assertEqual(command[0][0], 'jmdns-close-tests')
        self.assertEqual(command[0][1][1:], [*C.FLAGS, ':p2p-transport-lan:jvmTest', '--tests',
                         'dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest'])
        self.assert_no_publish_or_bootstrap_commands(command)
        for status, stopped in ((0, 0), (7, 0), (0, 9), (7, 9)):
            code, report, calls, error = self.execute_model([Mock(returncode=status), Mock(returncode=stopped)],
                                                           component='jmdns-diagnostic')
            self.assertIsNone(error)
            self.assertEqual(code, status or stopped)
            self.assertEqual(report['tasks'], [{'task': 'actual-tests', 'exitCode': status},
                                               {'task': 'gradle-stop', 'exitCode': stopped}])
            self.assertEqual(calls[-1].args[0][-1], '--stop')
            self.assertEqual(calls[-1].kwargs['timeout'], 90)
            self.assertEqual(len(calls), 2)

    def test_bundle_diagnostic_is_only_existing_disposable_test_and_cli_can_list_without_execution(self):
        command = [('signed-bundle-test', ['bash', 'scripts/tests/build-central-portal-bundle-test.sh'])]
        self.assertEqual(C.commands('bundle-diagnostic'), command)
        self.assertEqual(dict(C.commands('compatibility'))['signed-bundle-test'], command[0][1])
        self.assert_no_publish_or_bootstrap_commands(command)
        listed = subprocess.run([C.sys.executable, '-I', '-S', '-B', str(ROOT / 'scripts/ci_component.py'),
                                 'bundle-diagnostic', '--list-commands'], capture_output=True, check=True, timeout=10)
        self.assertEqual(json.loads(listed.stdout), [['signed-bundle-test', command[0][1]]])
        self.assertEqual(listed.stderr, b'')

    def test_bundle_diagnostic_retains_bounded_stop_and_original_failure(self):
        for status, stopped in ((0, 0), (7, 0), (0, 9), (7, 9)):
            code, report, calls, error = self.execute_model([Mock(returncode=status), Mock(returncode=stopped)],
                                                           component='bundle-diagnostic')
            self.assertIsNone(error)
            self.assertEqual(code, status or stopped)
            self.assertEqual(report['tasks'], [{'task': 'actual-tests', 'exitCode': status},
                                               {'task': 'gradle-stop', 'exitCode': stopped}])
            self.assertEqual(calls[-1].args[0][-1], '--stop')
            self.assertEqual(calls[-1].kwargs['timeout'], 90)
            self.assertEqual(len(calls), 2)

    def test_bundle_diagnostic_records_actual_selected_xcode_identity(self):
        with tempfile.TemporaryDirectory(prefix='bundle-tools-model-') as temporary:
            root = Path(temporary)
            for name in ('java', 'gpg', 'gradlew', 'xcodebuild'):
                (root / name).write_bytes(b'public synthetic executable')
            versions = [Mock(stdout=b'openjdk version "17.0.20.1"'), Mock(stdout=b'gpg (GnuPG) 2.5.22'),
                        Mock(stdout=b'Gradle 9.7.0\n'), Mock(stdout=b'Xcode 26.5\nBuild version 17F1\n')]
            with patch.object(C, 'ROOT', root), \
                    patch.object(C.shutil, 'which', side_effect=lambda name: str(root / name)), \
                    patch.object(C.subprocess, 'run', side_effect=versions) as invoked, \
                    patch.dict(C.os.environ, {'CI_EVIDENCE_TOOLS_FILE': str(root / 'tools.json')}):
                C.record_tools('bundle-diagnostic')
            recorded = json.loads((root / 'tools.json').read_text())
            self.assertEqual(set(recorded), {'java', 'gpg', 'gradle', 'xcode'})
            self.assertEqual(recorded['xcode'], {'version': '26.5',
                             'executableSha256': C.hashlib.sha256(b'public synthetic executable').hexdigest()})
            self.assertEqual(invoked.call_args_list[-1].args[0], [str(root / 'xcodebuild'), '-version'])

    def test_intel_transaction_wraps_original_native_then_stop_then_restore(self):
        code, report, calls, error = self.execute_model([Mock(returncode=0) for _ in range(4)], component='apple-x64')
        self.assertIsNone(error)
        self.assertEqual(code, 0)
        self.assertEqual([row['task'] for row in report['tasks']],
                         ['intel-advertising-prepare', 'actual-tests', 'gradle-stop', 'intel-advertising-restore'])
        for index, phase in ((0, 'prepare'), (3, 'restore')):
            self.assertEqual(calls[index].args[0], [C.sys.executable, '-I', '-S', '-B',
                                                  'scripts/with-intel-bonjour-advertising.py', phase])
            self.assertEqual(calls[index].kwargs['timeout'], 150)
        self.assertEqual(calls[2].kwargs['timeout'], 90)

    def test_intel_failed_preparation_does_not_launch_product_but_restores_after_stop(self):
        for prepare, expected in ((Mock(returncode=7), 7),
                                  (subprocess.TimeoutExpired(['prepare'], 150), 124),
                                  (OSError('synthetic prepare unavailable'), 125)):
            with self.subTest(expected=expected):
                code, report, calls, error = self.execute_model([prepare, Mock(returncode=0), Mock(returncode=9)],
                                                               component='apple-x64')
                self.assertIsNone(error)
                self.assertEqual((code, report['exitCode']), (expected, expected))
                self.assertEqual([row['task'] for row in report['tasks']],
                                 ['intel-advertising-prepare', 'gradle-stop', 'intel-advertising-restore'])
                self.assertEqual(report['tasks'][-1]['exitCode'], 9)

    def test_intel_product_stop_and_restore_failures_never_become_pass(self):
        for outcomes, expected in (((0, 7, 9, 11), 7), ((0, 0, 9, 11), 9), ((0, 0, 0, 11), 11)):
            code, report, calls, error = self.execute_model([Mock(returncode=value) for value in outcomes],
                                                           component='apple-x64')
            self.assertIsNone(error)
            self.assertEqual((code, report['exitCode']), (expected, expected))
            self.assertEqual([row['task'] for row in report['tasks']],
                             ['intel-advertising-prepare', 'actual-tests', 'gradle-stop', 'intel-advertising-restore'])
        code, report, calls, error = self.execute_model([Mock(returncode=0), Mock(returncode=0),
            subprocess.TimeoutExpired(['stop'], 90), Mock(returncode=0)], component='apple-x64')
        self.assertEqual(code, 124)
        self.assertEqual(report['tasks'][-1], {'task': 'intel-advertising-restore', 'exitCode': 0})
        code, report, calls, error = self.execute_model([Mock(returncode=0), Mock(returncode=0), Mock(returncode=0),
            subprocess.TimeoutExpired(['restore'], 150)], component='apple-x64')
        self.assertEqual(code, 124)
        self.assertEqual(report['tasks'][-1], {'task': 'intel-advertising-restore', 'exitCode': 124})

    def test_intel_setup_failure_before_preparation_never_creates_restore_transaction(self):
        original = RuntimeError('synthetic setup error')
        code, report, calls, error = self.execute_model([Mock(returncode=0)], component='apple-x64', tool_error=original)
        self.assertIs(error, original)
        self.assertEqual([row['task'] for row in report['tasks']], ['component-setup', 'gradle-stop'])

    def test_intel_transaction_offline_controls_are_source_routed_and_closed_evidence_labels(self):
        actual = dict(C.commands('source'))
        for name in ('rpc-apple-bonjour-environment-test.py', 'intel-bonjour-advertising-test.py'):
            self.assertEqual(actual[name], [C.sys.executable, '-B', 'scripts/tests/' + name, '-v'])
        evidence_spec = importlib.util.spec_from_file_location('ci_evidence_intel', ROOT / 'scripts/ci_evidence.py')
        evidence = importlib.util.module_from_spec(evidence_spec)
        with patch.object(C.sys, 'path', [str(ROOT / 'scripts'), *C.sys.path]):
            evidence_spec.loader.exec_module(evidence)
        self.assertTrue({'intel-advertising-prepare', 'intel-advertising-restore'} <= evidence.TASK_NAMES)

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

class SetupBaselineTests(unittest.TestCase):
    def selected(self, component, *, os_name='macOS', arch='X64', release='15.7', xcode='26.3', present=True):
        source = (ROOT / 'scripts/setup-ci-component.sh').read_text()
        begin = source.index('if [[ "$component" == macos-shared || "$component" == consumers || "$component" == published-consumers-diagnostic || "$component" == consumers-pom-diagnostic || "$component" == jmdns-diagnostic || "$component" == dependency-update ]]; then')
        end = source.index('  xcodegen_bin_dir=', begin)
        # Actual selection/admission shell block, with synthetic readbacks only.
        # No SDK installation, GPG, Gradle, network or native evidence.
        block = source[begin:end] + '\nfi\n'
        with tempfile.TemporaryDirectory(prefix='consumer-setup-model-') as temporary:
            output = Path(temporary) / 'github-env'
            environment = {'PATH': C.os.environ['PATH'], 'component': component, 'RUNNER_OS': os_name,
                           'RUNNER_ARCH': arch, 'MODEL_RELEASE': release, 'MODEL_XCODE': xcode,
                           'MODEL_PRESENT': '1' if present else '0', 'GITHUB_ENV': str(output)}
            fake = ('sw_vers() { printf "%s\\n" "$MODEL_RELEASE"; }\n'
                    'xcodebuild() { printf "Xcode %s\\nBuild version synthetic\\n" "$MODEL_XCODE"; }\n'
                    'test() { [[ "$1" == -d && "$MODEL_PRESENT" == 1 ]]; }\n')
            result = subprocess.run(['bash', '-euo', 'pipefail', '-c', fake + block], env=environment,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            return result.returncode, output.read_text() if output.exists() else ''

    def test_actual_selection_requires_exact_supported_host_and_tool(self):
        for component in ('consumers', 'published-consumers-diagnostic', 'consumers-pom-diagnostic', 'jmdns-diagnostic', 'dependency-update', 'macos-shared'):
            self.assertEqual(self.selected(component),
                             (0, 'DEVELOPER_DIR=/Applications/Xcode_26.3.app/Contents/Developer\n'))
            for changed in ({'os_name': 'Linux'}, {'arch': 'ARM64'}, {'release': '14.8.1'}, {'release': '26.0'},
                            {'xcode': '26.5'}, {'xcode': '26.30'}, {'present': False}):
                with self.subTest(component=component, changed=changed):
                    code, output = self.selected(component, **changed)
                    self.assertNotEqual(code, 0)
                    self.assertEqual(output, '')

    def test_native_and_installer_xcode_selection_remains_unchanged(self):
        for component in ('compatibility', 'apple-arm64', 'desktop-macos'):
            self.assertEqual(self.selected(component, arch='ARM64', release='26.0', xcode='26.5'),
                             (0, 'DEVELOPER_DIR=/Applications/Xcode_26.5.app/Contents/Developer\n'))
        self.assertEqual(self.selected('apple-x64', arch='X64', release='15.7', xcode='26.3'),
                         (0, 'DEVELOPER_DIR=/Applications/Xcode_26.3.app/Contents/Developer\n'))


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


class TerminalDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('modular_terminal_test', ROOT / 'scripts/run-ci-terminal-component.py')
        cls.T = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.T)

    def environment(self):
        return dict(PATH='/usr/bin:/bin', GITHUB_WORKSPACE=str(ROOT), GITHUB_SHA='a' * 40,
            GITHUB_WORKFLOW_SHA='a' * 40, GITHUB_WORKFLOW_REF='p2pKit/P2pKit/.github/workflows/ci.yml@refs/heads/test',
            GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_REPOSITORY='p2pKit/P2pKit', GITHUB_ACTIONS='true',
            RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='macOS', RUNNER_ARCH='X64',
            RUNNER_TRACKING_ID='github_123-test', RUNNER_TEMP='/tmp')

    def test_terminal_route_is_only_explicit_diagnostic_and_preserves_exact_command(self):
        T = self.T
        env = self.environment()
        argv = T.command(env)
        python = str(Path(T.sys.executable).resolve())
        self.assertEqual(argv, [python, '-B', str(ROOT / 'scripts/ci_evidence.py'), '--component', 'jmdns-diagnostic',
            '--timeout-seconds', '1800', '--source-root', str(ROOT), '--output-dir', '/tmp/ci-evidence-jmdns-diagnostic',
            '--report-glob', '**/build/test-results/**/*.xml', '--report-glob', 'build/reports/**/*', '--',
            python, '-B', str(ROOT / 'scripts/ci_component.py'), 'jmdns-diagnostic'])
        workflow = (ROOT / '.github/workflows/ci-component.yml').read_text()
        self.assertIn('if [[ "$COMPONENT" == jmdns-diagnostic || "$COMPONENT" == macos-shared || "$COMPONENT" == consumers || "$COMPONENT" == published-consumers-diagnostic ]]; then', workflow)
        self.assertIn('if [[ "$COMPONENT" == jmdns-diagnostic ]]; then [[ "$MINUTES" == 30 ]]', workflow)
        self.assertIn('else [[ "$MINUTES" == 120 ]]; fi', workflow)
        self.assertEqual(workflow.count('python3 -B scripts/run-ci-terminal-component.py'), 1)
        self.assertIn('else\n            python3 -B scripts/ci_evidence.py', workflow)
        self.assertNotIn('jmdns-diagnostic', C.COMPONENTS)
        self.assertEqual(C.matrix('jmdns-diagnostic')['include'][0]['job_minutes'], 40)
        self.assertEqual(len(C.matrix('all')['include']), 14)
        self.assertEqual(C.commands('jmdns-diagnostic')[0][1][-3:],
            [':p2p-transport-lan:jvmTest', '--tests', 'dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest'])
        self.assertEqual(C.commands('apple-arm64')[0][1][-1], 'ios-arm64')
        self.assertEqual(C.commands('apple-x64')[0][1][-1], 'ios-x64')

    def test_terminal_environment_admission_and_nonsecret_allowlist(self):
        T = self.T
        with patch.object(T.platform, 'system', return_value='Darwin'), patch.object(T.platform, 'machine', return_value='x86_64'):
            T.environment_admit(self.environment())
            for key, value in [('RUNNER_TRACKING_ID', ''), ('RUNNER_TRACKING_ID', 'bad tracking'),
                ('GITHUB_EVENT_NAME', 'pull_request'), ('GITHUB_SHA', 'b' * 40), ('RUNNER_ARCH', 'ARM64'),
                ('GITHUB_WORKFLOW_REF', 'p2pKit/P2pKit/.github/workflows/publish-maven-central.yml@refs/tags/v1'),
                ('P2PKIT_AUDIT_OWNERSHIP_CHAIN', 'existing-domain')]:
                with self.subTest(key=key, value=value), self.assertRaises(T.ContextFailure):
                    T.environment_admit({**self.environment(), key: value})
        self.assertTrue({'RUNNER_TRACKING_ID', 'JAVA_HOME', 'JAVA_HOME_21_X64', 'GRADLE_USER_HOME',
                         'CI_EVIDENCE_RECIPIENT_FINGERPRINT'} <= T.ENVIRONMENT)
        self.assertTrue({'GITHUB_TOKEN', 'GH_TOKEN', 'CENTRAL_TOKEN_PASSWORD', 'SIGNING_KEY',
                         'JAVA_TOOL_OPTIONS', 'P2PKIT_AUDIT_OWNERSHIP_CHAIN'}.isdisjoint(T.ENVIRONMENT))

    def test_terminal_config_rejects_credentials_source_and_environment_mutation(self):
        T = self.T
        with tempfile.TemporaryDirectory(prefix='terminal-config-') as tmp:
            temp = Path(tmp).resolve()
            directory = temp / 'ci-terminal-case'
            directory.mkdir(mode=0o700)
            env = {**self.environment(), 'RUNNER_TEMP': str(temp)}
            config = dict(uid=501, gid=20, groups=[20, 80], source={'commit': 'a' * 40, 'tree': 'b' * 40}, environment=env, component=T.COMPONENT)
            with patch.object(T, 'environment_admit'), patch.object(T.private, 'private_parent'), \
                 patch.object(T.os, 'getuid', return_value=501), patch.object(T.os, 'geteuid', return_value=501), \
                 patch.object(T.os, 'getgid', return_value=20), patch.object(T.os, 'getegid', return_value=20), \
                 patch.object(T.os, 'getgroups', return_value=[80, 20]), \
                 patch.dict(T.os.environ, {'RUNNER_TRACKING_ID': env['RUNNER_TRACKING_ID']}):
                T.validate_config(config, directory)
                for key, value in [('uid', 0), ('groups', [20]), ('source', {'commit': 'c' * 40, 'tree': 'b' * 40}),
                    ('environment', {**env, 'GITHUB_TOKEN': 'PRIVATE'}),
                    ('environment', {**env, 'RUNNER_TRACKING_ID': 'different'})]:
                    with self.subTest(key=key), self.assertRaises(T.ContextFailure):
                        T.validate_config({**config, key: value}, directory)
                with self.assertRaises(T.ContextFailure):
                    T.validate_config(config, temp / 'wrong-directory')

    def test_terminal_original_evidence_exit_and_cancel_are_not_conflated(self):
        T = self.T
        with tempfile.TemporaryDirectory(prefix='terminal-wait-') as tmp, patch.object(T.time, 'sleep'):
            directory = Path(tmp)
            for code in (0, 1):
                process = Mock()
                process.poll.return_value = code
                self.assertEqual(T.wait_evidence(process, directory, threading.Event(), T.time.monotonic() + 30), code)
                process.send_signal.assert_not_called()
            process = Mock()
            process.poll.side_effect = [None, 0]
            cancelled = threading.Event()
            cancelled.set()
            with self.assertRaisesRegex(T.ContextFailure, '^CANCELLED$'):
                T.wait_evidence(process, directory, cancelled, T.time.monotonic() + 30)
            process.send_signal.assert_called_once_with(signal.SIGTERM)
            process.kill.assert_not_called()
            process = Mock()
            process.poll.return_value = None
            with patch.object(T.time, 'monotonic', side_effect=[10, 71]), \
                 self.assertRaisesRegex(T.ContextFailure, '^CHILD_RETIREMENT_UNKNOWN$'):
                T.wait_evidence(process, directory, threading.Event(), 5)
            process.send_signal.assert_called_once_with(signal.SIGTERM)
            process.kill.assert_not_called()

    def test_terminal_controller_cancellation_keeps_native_finalizer_authority(self):
        T = self.T
        with tempfile.TemporaryDirectory(prefix='terminal-controller-') as tmp, patch.object(T.time, 'sleep'):
            directory = Path(tmp)
            process = Mock(returncode=125)
            process.poll.side_effect = [None, 125]
            cancelled = threading.Event()
            cancelled.set()
            self.assertEqual(T.wait_controller(process, directory, cancelled, T.time.monotonic() + 30), 125)
            self.assertEqual((directory / 'cancel').read_bytes(), b'cancel\n')
            process.send_signal.assert_not_called()
            process.kill.assert_not_called()
            process = Mock(returncode=0)
            process.poll.return_value = 0
            with patch.object(T.time, 'monotonic', return_value=20), \
                 self.assertRaisesRegex(T.ContextFailure, '^CONTROLLER_RETIREMENT_UNKNOWN$'):
                T.wait_controller(process, directory, threading.Event(), 10)

    def test_terminal_native_lease_and_complete_result_cannot_be_replaced_by_inner_pass(self):
        T = self.T
        source = {'commit': 'a' * 40, 'tree': 'b' * 40}
        app = dict(schema=3, executionMode=T.bounds(T.COMPONENT)['mode'], stage='FINALIZED', exitCode=0, failureCheck='NONE',
            openErrorDomain='NONE', openErrorCode=0, **dict.fromkeys(T.terminal.APPLICATION_FLAGS, True))
        admission = dict(source=source, ancestry=dict(method=T.terminal.ANCESTRY_METHOD, depth=3,
            systemLoginAncestors=1, restrictedCombinedDenials=1))
        T.validate_result(app, admission, dict(source=source, exitCode=0), source, 0)
        for key in T.terminal.APPLICATION_FLAGS:
            with self.subTest(flag=key), self.assertRaises(T.ContextFailure):
                T.validate_result({**app, key: False}, admission, dict(source=source, exitCode=0), source, 0)
        for key, value in [('exitCode', False), ('stage', 'QUIT'), ('failureCheck', 'SHELL_RETIREMENT'),
                           ('executionMode', 'qualification')]:
            with self.subTest(key=key), self.assertRaises(T.ContextFailure):
                T.validate_result({**app, key: value}, admission, dict(source=source, exitCode=0), source, 0)
        with self.assertRaises(T.ContextFailure):
            T.validate_result(app, admission, dict(source={'commit': 'c' * 40, 'tree': 'b' * 40}, exitCode=0), source, 0)
        native = (ROOT / 'scripts/diagnostics/apple-terminal-context.m').read_text()
        self.assertIn('@{@"modular-jmdns":@1800, @"modular-shared":@7200,\n            @"modular-consumers":@7200, @"modular-published-consumers":@7200,\n            @"modular-dependency-generate":@10800}[executionMode]', native)
        self.assertIn('if (!modularCommand) return 125;', native)
        self.assertIn('childBound = @(modularCommand.doubleValue + 240);', native)
        self.assertIn('![expectedMode isEqualToString:executionMode]', native)
        self.assertIn('config[@"environment"][@"RUNNER_TRACKING_ID"] isEqual:tracking', native)
        self.assertIn('@"RUNNER_TRACKING_ID":tracking', native)
        self.assertIn('outcome = finalizeApplication(', native)
        self.assertNotIn('forceTerminate', native)
        self.assertNotIn('kill(', native)
        raw = (ROOT / 'scripts/run-ci-terminal-component.py').read_text()
        self.assertNotIn('with-darwin-audit-session.py', raw)
        self.assertNotIn('run-rpc-qualification.py', raw)
        self.assertIn('private.source_snapshot() == source', raw)

    def test_terminal_child_source_change_and_early_cancel_remain_failure(self):
        T = self.T
        source = {'commit': 'a' * 40, 'tree': 'b' * 40}
        for cancelled, changed in ((True, False), (False, True), (False, False)):
            with self.subTest(cancelled=cancelled, changed=changed), \
                 tempfile.TemporaryDirectory(prefix='terminal-child-') as tmp, ExitStack() as stack:
                directory = Path(tmp)
                if cancelled:
                    (directory / 'cancel').write_bytes(b'cancel\n')
                config = dict(source=source, environment=self.environment(), component=T.COMPONENT)
                stack.enter_context(patch.object(T.private, 'read_json', return_value=config))
                stack.enter_context(patch.object(T, 'validate_config'))
                stack.enter_context(patch.object(T.private, 'source_snapshot', side_effect=[source,
                    {'commit': 'c' * 40, 'tree': 'b' * 40} if changed else source]))
                stack.enter_context(patch.object(T.terminal, 'terminal_ancestor', return_value={}))
                stack.enter_context(patch.object(T.pwd, 'getpwuid', return_value=Mock(pw_dir='/nonsecret', pw_name='synthetic')))
                writes = stack.enter_context(patch.object(T.private, 'write_json'))
                popen = stack.enter_context(patch.object(T.subprocess, 'Popen'))
                popen.return_value.poll.return_value = 0
                stack.enter_context(patch.object(T, 'wait_evidence', return_value=0))
                if cancelled or changed:
                    with self.assertRaisesRegex(T.ContextFailure, '^' + ('CANCELLED' if cancelled else 'SOURCE_CHANGED') + '$'):
                        T.child(directory / 'config.json')
                    writes.assert_called_with(directory / 'child-result.json', dict(source=source, exitCode=125))
                else:
                    self.assertEqual(T.child(directory / 'config.json'), 0)
                    writes.assert_called_with(directory / 'child-result.json', dict(source=source, exitCode=0))
                if cancelled:
                    popen.assert_not_called()

    def test_terminal_outer_source_or_cancel_failure_cannot_be_inner_success(self):
        T = self.T
        source = {'commit': 'a' * 40, 'tree': 'b' * 40}
        for failure in ('source', 'cancel-after-child', 'cancel-before-spawn'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(prefix='terminal-parent-') as tmp, ExitStack() as stack:
                env = {**self.environment(), 'RUNNER_TEMP': str(Path(tmp).resolve())}
                stack.enter_context(patch.dict(T.os.environ, env, clear=True))
                stack.enter_context(patch.object(T, 'environment_admit'))
                stack.enter_context(patch.object(T, 'validate_config'))
                stack.enter_context(patch.object(T.private, 'source_snapshot', side_effect=[source,
                    {'commit': 'c' * 40, 'tree': 'b' * 40} if failure == 'source' else source]))
                stack.enter_context(patch.object(T.private, 'read_json', return_value={}))
                stack.enter_context(patch.object(T, 'validate_result'))
                popen = stack.enter_context(patch.object(T.subprocess, 'Popen'))
                popen.return_value.poll.return_value = 0
                def compile_result(*args, **kwargs):
                    self.assertEqual(kwargs['timeout'], 90)
                    if failure == 'cancel-before-spawn':
                        kwargs['cancelled'].__self__.set()
                    return dict(code='PASS', cleanupKnown=True, capturesClosed=True)
                stack.enter_context(patch.object(T.evidence, 'run_command', side_effect=compile_result))
                def wait(process, directory, cancelled, deadline):
                    if failure == 'cancel-after-child':
                        cancelled.set()
                    return 0
                stack.enter_context(patch.object(T, 'wait_controller', side_effect=wait))
                with self.assertRaisesRegex(T.ContextFailure, '^' + ('SOURCE_CHANGED' if failure == 'source' else 'CANCELLED') + '$'):
                    T.run()
                if failure == 'cancel-before-spawn':
                    popen.assert_not_called()
                else:
                    popen.assert_called_once()

    def test_terminal_source_snapshot_ignores_generated_reports_not_tracked_edits(self):
        T = self.T
        with tempfile.TemporaryDirectory(prefix='terminal-source-') as tmp:
            root = Path(tmp).resolve()
            environment = {'PATH': os.environ['PATH'], 'HOME': str(root), 'GIT_CONFIG_NOSYSTEM': '1',
                           'GIT_AUTHOR_NAME': 'Synthetic', 'GIT_AUTHOR_EMAIL': 'synthetic@example.invalid',
                           'GIT_COMMITTER_NAME': 'Synthetic', 'GIT_COMMITTER_EMAIL': 'synthetic@example.invalid'}
            def git(*args):
                subprocess.run(['/usr/bin/git', *args], cwd=root, env=environment, check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            git('init', '-q')
            (root / '.gitignore').write_text('build/\n')
            (root / 'source.txt').write_text('original\n')
            git('add', '.gitignore', 'source.txt')
            git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'synthetic')
            with patch.object(T.private, 'ROOT', root), patch.object(T.private.os, 'getuid', return_value=501), \
                 patch.object(T.private.os, 'geteuid', return_value=501):
                source = T.private.source_snapshot()
                (root / 'build/reports').mkdir(parents=True)
                (root / 'build/reports/synthetic.xml').write_text('<synthetic/>')
                self.assertEqual(T.private.source_snapshot(), source)
                (root / 'source.txt').write_text('changed\n')
                with self.assertRaisesRegex(T.private.ContextFailure, 'Immutable clean source required'):
                    T.private.source_snapshot()

    def test_terminal_deadlines_and_native_tracking_failure_are_fail_closed(self):
        T = self.T
        for component in T.PROFILES.keys() - {'dependency-generate'}:
            budget = T.bounds(component)
            route = C.matrix(component)['include'][0]
            self.assertEqual(budget['command'], route['minutes'] * 60)
            self.assertLess(budget['command'], budget['child'])
            self.assertLess(budget['child'], budget['native'])
            self.assertLess(budget['native'] + 30, budget['controller'])
            self.assertLess(budget['controller'], budget['wrapper'])
            self.assertLess(budget['wrapper'], route['job_minutes'] * 60)
        self.assertEqual(T.bounds('jmdns-diagnostic'),
            dict(mode='modular-jmdns', command=1800, child=1980, native=2040, controller=2100, wrapper=2250))
        self.assertEqual(T.bounds('macos-shared'),
            dict(mode='modular-shared', command=7200, child=7380, native=7440, controller=7500, wrapper=7650))
        source = {'commit': 'a' * 40, 'tree': 'b' * 40}
        app = dict(schema=3, executionMode=T.bounds(T.COMPONENT)['mode'], stage='OPEN', exitCode=125, failureCheck='RUNNER_TRACKING',
            openErrorDomain='NONE', openErrorCode=0, **dict.fromkeys(T.terminal.APPLICATION_FLAGS, False))
        with self.assertRaisesRegex(T.ContextFailure, '^APPLICATION_FINALIZATION$'):
            T.validate_result(app, {}, dict(source=source, exitCode=0), source, 0)

    def test_terminal_shared_fixed_profile_has_original_full_shared_command_not_a_test_subset(self):
        T = self.T
        self.assertEqual(set(T.PROFILES), {'jmdns-diagnostic', 'macos-shared', 'consumers', 'published-consumers-diagnostic', 'dependency-generate'})
        argv = T.command(self.environment(), 'macos-shared')
        self.assertEqual(argv[argv.index('--component') + 1], 'macos-shared')
        self.assertEqual(argv[argv.index('--timeout-seconds') + 1], '7200')
        self.assertEqual(argv[argv.index('--output-dir') + 1], '/tmp/ci-evidence-macos-shared')
        self.assertEqual(argv[-2:], [str(ROOT / 'scripts/ci_component.py'), 'macos-shared'])
        self.assertEqual(C.commands('macos-shared'),
            [('shared-platform-tests', [C.sys.executable, '-B', 'scripts/run-platform-tests.py', 'macos-shared'])])
        for component in ('dependency-update', 'compatibility', 'apple-arm64', 'apple-x64', '', 'macos-shared --skip'):
            with self.subTest(component=component), self.assertRaisesRegex(T.ContextFailure, '^COMPONENT$'):
                T.command(self.environment(), component)

    def test_terminal_shared_accepts_existing_ci_events_but_not_foreign_workflow_or_diagnostic_pr(self):
        T = self.T
        with patch.object(T.platform, 'system', return_value='Darwin'), patch.object(T.platform, 'machine', return_value='x86_64'):
            for event in ('workflow_dispatch', 'push', 'pull_request', 'schedule'):
                env = {**self.environment(), 'GITHUB_EVENT_NAME': event}
                T.environment_admit(env, 'macos-shared')
                if event != 'workflow_dispatch':
                    with self.assertRaisesRegex(T.ContextFailure, '^HOST_CONTEXT$'):
                        T.environment_admit(env, 'jmdns-diagnostic')
            for changes in ({'GITHUB_EVENT_NAME': 'workflow_run'}, {'GITHUB_WORKFLOW_SHA': 'b' * 40},
                {'GITHUB_WORKFLOW_REF': 'p2pKit/P2pKit/.github/workflows/publish-maven-central.yml@refs/tags/v1'}):
                with self.subTest(changes=changes), self.assertRaisesRegex(T.ContextFailure, '^HOST_CONTEXT$'):
                    T.environment_admit({**self.environment(), **changes}, 'macos-shared')
        source = {'commit': 'a' * 40, 'tree': 'b' * 40}
        app = dict(schema=3, executionMode='modular-shared', stage='FINALIZED', exitCode=0, failureCheck='NONE',
            openErrorDomain='NONE', openErrorCode=0, **dict.fromkeys(T.terminal.APPLICATION_FLAGS, True))
        admission = dict(source=source, ancestry=dict(method=T.terminal.ANCESTRY_METHOD, depth=3,
            systemLoginAncestors=1, restrictedCombinedDenials=1))
        T.validate_result(app, admission, dict(source=source, exitCode=0), source, 0, 'macos-shared')
        with self.assertRaisesRegex(T.ContextFailure, '^APPLICATION_FINALIZATION$'):
            T.validate_result(app, admission, dict(source=source, exitCode=0), source, 0, 'jmdns-diagnostic')

    def test_terminal_consumers_preserve_full_driver_and_bind_native_modes(self):
        T = self.T
        native = (ROOT / 'scripts/diagnostics/apple-terminal-context.m').read_text()
        source = {'commit': 'a' * 40, 'tree': 'b' * 40}
        admission = dict(source=source, ancestry=dict(method=T.terminal.ANCESTRY_METHOD, depth=3,
            systemLoginAncestors=1, restrictedCombinedDenials=1))
        for component, mode in (('consumers', 'modular-consumers'),
                                ('published-consumers-diagnostic', 'modular-published-consumers')):
            argv = T.command(self.environment(), component)
            self.assertEqual(argv[argv.index('--component') + 1], component)
            self.assertEqual(argv[argv.index('--timeout-seconds') + 1], '7200')
            self.assertEqual(argv[argv.index('--output-dir') + 1], '/tmp/ci-evidence-' + component)
            self.assertEqual(argv[-2:], [str(ROOT / 'scripts/ci_component.py'), component])
            self.assertEqual(T.bounds(component),
                dict(mode=mode, command=7200, child=7380, native=7440, controller=7500, wrapper=7650))
            self.assertIn('@"' + component + '":@"' + mode + '"', native)
            self.assertIn('@"' + mode + '":@7200', native)
            app = dict(schema=3, executionMode=mode, stage='FINALIZED', exitCode=0, failureCheck='NONE',
                openErrorDomain='NONE', openErrorCode=0, **dict.fromkeys(T.terminal.APPLICATION_FLAGS, True))
            T.validate_result(app, admission, dict(source=source, exitCode=0), source, 0, component)
            for other in T.PROFILES.keys() - {component}:
                with self.subTest(component=component, other=other), self.assertRaisesRegex(T.ContextFailure, '^APPLICATION_FINALIZATION$'):
                    T.validate_result(app, admission, dict(source=source, exitCode=0), source, 0, other)

    def test_terminal_remote_diagnostic_is_dispatch_only_and_passes_no_endpoint_or_secret_override(self):
        T = self.T
        with patch.object(T.platform, 'system', return_value='Darwin'), patch.object(T.platform, 'machine', return_value='x86_64'):
            for event in ('workflow_dispatch', 'push', 'pull_request', 'schedule'):
                env = {**self.environment(), 'GITHUB_EVENT_NAME': event}
                T.environment_admit(env, 'consumers')
                if event == 'workflow_dispatch':
                    T.environment_admit(env, 'published-consumers-diagnostic')
                else:
                    with self.assertRaisesRegex(T.ContextFailure, '^HOST_CONTEXT$'):
                        T.environment_admit(env, 'published-consumers-diagnostic')
            for component in ('consumers', 'published-consumers-diagnostic'):
                for changes in ({'GITHUB_EVENT_NAME': 'workflow_run'}, {'GITHUB_WORKFLOW_SHA': 'b' * 40},
                    {'GITHUB_WORKFLOW_REF': 'p2pKit/P2pKit/.github/workflows/publish-maven-central.yml@refs/tags/v1'}):
                    with self.subTest(component=component, changes=changes), self.assertRaisesRegex(T.ContextFailure, '^HOST_CONTEXT$'):
                        T.environment_admit({**self.environment(), **changes}, component)
        for key in ('P2PKIT_CONSUMER_REPOSITORY_URL', 'GH_TOKEN', 'GITHUB_TOKEN', 'MAVEN_CENTRAL_USERNAME',
                    'MAVEN_CENTRAL_PASSWORD', 'ORG_GRADLE_PROJECT_signingInMemoryKey'):
            self.assertNotIn(key, T.ENVIRONMENT)

    def test_terminal_shell_waits_original_child_and_has_no_environment_or_command_override(self):
        T = self.T
        raw = T.command_bytes(Path('/private/synthetic folder')).decode()
        self.assertIn('run-ci-terminal-component.py', raw)
        self.assertIn('--child', raw)
        self.assertIn('status=$?', raw)
        self.assertIn('printf \'%s\\n\' "$status"', raw)
        self.assertIn('exit "$status"', raw)
        self.assertNotIn('exec ', raw)
        self.assertNotIn(' &', raw)


class TerminalDependencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TerminalDiagnosticTests.setUpClass()
        cls.T = TerminalDiagnosticTests.T

    def environment(self, workspace):
        T = self.T
        request = dict(controller_sha='a' * 40, controller_tree='b' * 40,
                       candidate_sha='c' * 40, candidate_tree='d' * 40, dependency_base_sha='e' * 40)
        env = dict(PATH='/usr/bin:/bin', GITHUB_WORKSPACE=str(workspace), GITHUB_SHA='a' * 40,
            GITHUB_WORKFLOW_SHA='a' * 40,
            GITHUB_WORKFLOW_REF='p2pKit/P2pKit/.github/workflows/dependency-update-candidate.yml@refs/heads/test',
            GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_JOB='generate', GITHUB_REPOSITORY='p2pKit/P2pKit',
            GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='macOS', RUNNER_ARCH='X64',
            RUNNER_TRACKING_ID='github_123-test', RUNNER_TEMP=str(workspace),
            DEPENDENCY_UPDATE_REQUEST=json.dumps(request), P2PKIT_CI_COMMAND_DEADLINE_NS='1000000000000')
        return {**T.evidence.audit_processes.ownership_environment(env, 'a' * 32, 'b' * 32,
            str(workspace / 'state'), str(workspace / 'gradle-home'), allow_new_context=True),
            T.evidence.audit_processes.PIPE_ENV: '[]'}

    def test_candidate_workflow_request_and_inherited_domain_must_all_match(self):
        T = self.T
        with tempfile.TemporaryDirectory(prefix='terminal-generator-') as tmp:
            root = Path(tmp).resolve(); candidate = root / 'candidate'; candidate.mkdir()
            env = self.environment(root)
            with patch.object(T, 'ROOT', candidate), patch.object(T.time, 'monotonic', return_value=100), \
                 patch.object(T.platform, 'system', return_value='Darwin'), patch.object(T.platform, 'machine', return_value='x86_64'):
                T.environment_admit(env, 'dependency-generate')
                for changed in ({'GITHUB_JOB': 'component'}, {'GITHUB_SHA': 'c' * 40},
                    {'GITHUB_EVENT_NAME': 'push'}, {'GITHUB_WORKFLOW_REF': 'p2pKit/P2pKit/.github/workflows/ci.yml@refs/heads/test'},
                    {'DEPENDENCY_UPDATE_REQUEST': '{}'}, {'GRADLE_USER_HOME': str(root / 'different')},
                    {'P2PKIT_AUDIT_STATE_DIR': str(root / 'different')}, {'P2PKIT_AUDIT_OWNERSHIP_CHAIN': ''},
                    {'P2PKIT_AUDIT_EXTRA': 'unexpected'}):
                    with self.subTest(changed=changed), self.assertRaises((T.ContextFailure, T.evidence.audit_processes.OwnershipError)):
                        T.environment_admit({**env, **changed}, 'dependency-generate')
        self.assertNotIn('dependency-generate', C.COMPONENTS)
        self.assertNotIn('dependency-generate', C.DIAGNOSTICS)
        self.assertEqual(T.command({}, 'dependency-generate'), [str(ROOT / 'gradlew'),
            'resolveAndLockAll', '--write-locks', '--write-verification-metadata', 'sha256', '--continue',
            '--no-configure-on-demand', '--no-daemon', '--console=plain'])

    def test_inherited_deadline_rejects_missing_expired_future_and_malformed_values(self):
        T = self.T
        with patch.object(T.time, 'monotonic', return_value=100):
            self.assertEqual(T.dependency_deadline({'P2PKIT_CI_COMMAND_DEADLINE_NS': '1000000000000'}), 1000)
            for value in ('', '100000000000', '11000000000000', 'NaN', '1000000000000 PRIVATE', '-1', '1e12', True):
                with self.subTest(value=value), self.assertRaisesRegex(T.ContextFailure, '^DEPENDENCY_DEADLINE$'):
                    T.dependency_deadline({'P2PKIT_CI_COMMAND_DEADLINE_NS': value})

    def test_candidate_delta_allows_only_existing_locks_xml_not_product_or_new_files(self):
        T = self.T
        with tempfile.TemporaryDirectory(prefix='terminal-mutable-') as tmp:
            root = Path(tmp).resolve()
            def git(*argv):
                return subprocess.check_output(['git', '-C', str(root), *argv], stderr=subprocess.PIPE)
            git('init', '--quiet'); (root / 'gradle').mkdir()
            for name in ('gradle.lockfile', 'gradle/verification-metadata.xml', 'product.txt'):
                (root / name).write_text('original')
            (root / '.gitignore').write_text('build/\n')
            git('add', '.'); git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                                '-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'synthetic')
            request = dict(controller_sha='a' * 40, controller_tree='b' * 40,
                           candidate_sha=git('rev-parse', 'HEAD').decode().strip(),
                           candidate_tree=git('rev-parse', 'HEAD^{tree}').decode().strip(), dependency_base_sha='e' * 40)
            with patch.object(T, 'ROOT', root):
                source, before = T.begin_source('dependency-generate', {'DEPENDENCY_UPDATE_REQUEST': json.dumps(request)})
                (root / 'gradle.lockfile').write_text('generated'); (root / 'gradle/verification-metadata.xml').write_text('generated')
                (root / 'build/reports').mkdir(parents=True); (root / 'build/reports/original.log').write_text('synthetic')
                T.finish_source('dependency-generate', source, before)
                (root / 'product.txt').write_text('changed')
                with self.assertRaisesRegex(T.dependency.UpdateError, 'NON_DEPENDENCY_SOURCE_CHANGED'):
                    T.finish_source('dependency-generate', source, before)
                (root / 'product.txt').write_text('original'); (root / 'unexpected').write_text('new')
                with self.assertRaisesRegex(T.dependency.UpdateError, 'CANDIDATE_ROSTER_CHANGED'):
                    T.finish_source('dependency-generate', source, before)
                (root / 'unexpected').unlink(); git('add', 'gradle.lockfile')
                with self.assertRaisesRegex(T.dependency.UpdateError, 'CANDIDATE_ROSTER_CHANGED'):
                    T.finish_source('dependency-generate', source, before)

    def test_generator_child_preserves_command_failure_cleanup_cancel_and_remaining_budget(self):
        T = self.T
        source = dict(commit='c' * 40, tree='d' * 40)
        for case in ('success', 'command-failure', 'cleanup', 'cancel-before', 'cancel-after', 'exhausted'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='terminal-generator-child-') as tmp, ExitStack() as stack:
                root = Path(tmp).resolve(); directory = root / 'private'; directory.mkdir()
                env = self.environment(root)
                if case == 'exhausted': env['P2PKIT_CI_COMMAND_DEADLINE_NS'] = '500000000000'
                if case == 'cancel-before': (directory / 'cancel').write_text('cancel')
                stack.enter_context(patch.object(T, 'ROOT', root))
                stack.enter_context(patch.object(T.private, 'read_json', return_value=dict(source=source, environment=env, component='dependency-generate')))
                stack.enter_context(patch.object(T, 'validate_config'))
                stack.enter_context(patch.object(T, 'begin_source', return_value=(source, {})))
                checked = stack.enter_context(patch.object(T, 'finish_source'))
                stack.enter_context(patch.object(T.terminal, 'terminal_ancestor', return_value={}))
                stack.enter_context(patch.object(T.pwd, 'getpwuid', return_value=Mock(pw_dir='/nonsecret', pw_name='synthetic')))
                stack.enter_context(patch.object(T.time, 'monotonic', return_value=100))
                writes = stack.enter_context(patch.object(T.private, 'write_json'))
                popen = stack.enter_context(patch.object(T.subprocess, 'Popen'))
                def execute(argv, **kwargs):
                    self.assertEqual(kwargs['timeout'], 450)
                    self.assertEqual(kwargs['private'], root / 'build/reports/dependency-generation')
                    self.assertEqual(argv, T.command(env, 'dependency-generate'))
                    self.assertFalse(kwargs['cancelled']())
                    for key in T.DEPENDENCY_ENVIRONMENT:
                        self.assertEqual(kwargs['environment'][key], env[key])
                    if case == 'cancel-after': (directory / 'cancel').write_text('cancel')
                    return dict(code='COMMAND_FAILED' if case == 'command-failure' else 'PASS',
                                cleanupKnown=case != 'cleanup', capturesClosed=case != 'cleanup', exitCode=7 if case == 'command-failure' else 0)
                executed = stack.enter_context(patch.object(T.evidence, 'run_command', side_effect=execute))
                if case in ('success', 'command-failure'):
                    self.assertEqual(T.child(directory / 'config.json'), 0 if case == 'success' else 1)
                else:
                    with self.assertRaises(T.ContextFailure): T.child(directory / 'config.json')
                popen.assert_not_called()
                self.assertGreaterEqual(checked.call_count, 1)
                self.assertEqual(executed.call_count, 0 if case in ('cancel-before', 'exhausted') else 1)
                expected = 0 if case == 'success' else 1 if case == 'command-failure' else 125
                writes.assert_called_with(directory / 'child-result.json', dict(source=source, exitCode=expected))

    def test_generator_compiler_native_and_child_environments_never_receive_provenance_token(self):
        T = self.T
        source = dict(commit='c' * 40, tree='d' * 40)
        with tempfile.TemporaryDirectory(prefix='terminal-generator-parent-') as tmp, ExitStack() as stack:
            root = Path(tmp).resolve(); env = {**self.environment(root), 'GH_TOKEN': 'PRIVATE_TOKEN',
                'GITHUB_TOKEN': 'PRIVATE_TOKEN', 'ORG_GRADLE_PROJECT_signingInMemoryKey': 'PRIVATE_KEY'}
            stack.enter_context(patch.dict(T.os.environ, env, clear=True))
            stack.enter_context(patch.object(T.time, 'monotonic', return_value=100))
            stack.enter_context(patch.object(T, 'environment_admit'))
            stack.enter_context(patch.object(T, 'validate_config'))
            stack.enter_context(patch.object(T, 'begin_source', return_value=(source, {})))
            stack.enter_context(patch.object(T, 'finish_source'))
            stack.enter_context(patch.object(T.private, 'read_json', return_value={}))
            stack.enter_context(patch.object(T, 'validate_result'))
            writes = stack.enter_context(patch.object(T.private, 'write_json'))
            compile_call = stack.enter_context(patch.object(T.evidence, 'run_command', return_value=dict(code='PASS', cleanupKnown=True, capturesClosed=True)))
            popen = stack.enter_context(patch.object(T.subprocess, 'Popen')); popen.return_value.poll.return_value = 0
            waited = stack.enter_context(patch.object(T, 'wait_controller', return_value=0))
            self.assertEqual(T.run('dependency-generate'), 0)
            self.assertEqual(waited.call_args.args[3], 940)
            observed = (compile_call.call_args.kwargs['environment'], popen.call_args.kwargs['env'], writes.call_args_list[0].args[1]['environment'])
            for environment in observed:
                for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'ORG_GRADLE_PROJECT_signingInMemoryKey'):
                    self.assertNotIn(key, environment)
                for key in T.DEPENDENCY_ENVIRONMENT:
                    self.assertEqual(environment[key], env[key])

    def test_native_generator_requires_same_deadline_and_owned_domain_not_new_context(self):
        native = (ROOT / 'scripts/diagnostics/apple-terminal-context.m').read_text()
        for text in ('mach_absolute_time()', '10800ULL * 1000000000ULL',
                     'modularRemaining(modularDeadline) <= 450', 'childBound = @(remaining - 120)',
                     'P2PKIT_CI_COMMAND_DEADLINE_NS', 'P2PKIT_AUDIT_OWNERSHIP_DOMAINS',
                     '![value isEqualToString:[NSString stringWithUTF8String:original]]',
                     'if (modularEnvironment.count != 9) break;'):
            self.assertIn(text, native)
        self.assertNotIn('GH_TOKEN', native)
        self.assertNotIn('GITHUB_TOKEN', native)
        self.assertEqual(self.T.PROFILES['dependency-generate'], ('modular-dependency-generate', 10800))


if __name__ == '__main__': unittest.main()
