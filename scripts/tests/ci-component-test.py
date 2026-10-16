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
        self.assertEqual(len(rows), 13)
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
        self.assertIn('full', C.commands('apple-arm64')[0][1])
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
        self.assertEqual(C.COMPONENTS['consumers'], ('macos-14', 120))
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
            for version in ('16.2', '26.5', '16.20'):
                versions = [Mock(stdout=b'openjdk version "17"'), Mock(stdout=b'gpg (GnuPG) 2.5.22'),
                            Mock(stdout=b'Gradle 9.7.0\n'), Mock(stdout=('Xcode ' + version + '\nBuild version synthetic\n').encode())]
                target = root / 'tools.json'
                target.unlink(missing_ok=True)
                with patch.object(C, 'ROOT', root), \
                        patch.object(C.shutil, 'which', side_effect=lambda name: str(root / name)), \
                        patch.object(C.subprocess, 'run', side_effect=versions), \
                        patch.dict(C.os.environ, {'CI_EVIDENCE_TOOLS_FILE': str(target)}):
                    if version == '16.2':
                        C.record_tools('consumers')
                        self.assertEqual(json.loads(target.read_text())['xcode']['version'], version)
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'requires Xcode 16.2'):
                            C.record_tools('consumers')
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
        self.assertEqual(C.DIAGNOSTICS, {'bundle-diagnostic': ('macos-26', 60), 'jmdns-diagnostic': ('macos-26', 30),
                                       'consumers-pom-diagnostic': ('macos-14', 60)})
        self.assertEqual(len(C.COMPONENTS), 13)
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
                         'os': 'macos-14', 'minutes': 60, 'job_minutes': 70}]})
        self.assertNotIn('consumers-pom-diagnostic', C.COMPONENTS)
        self.assertEqual(len(C.matrix('all')['include']), 13)
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

    def test_jmdns_diagnostic_is_focused_independent_and_preserves_failure_cleanup(self):
        self.assertEqual(C.matrix('jmdns-diagnostic'), {'include': [{'component': 'jmdns-diagnostic',
                         'os': 'macos-26', 'minutes': 30, 'job_minutes': 40}]})
        self.assertNotIn('jmdns-diagnostic', C.COMPONENTS)
        self.assertEqual(len(C.matrix('all')['include']), 13)
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
    def selected(self, component, *, os_name='macOS', arch='ARM64', release='14.8.1', xcode='16.2', present=True):
        source = (ROOT / 'scripts/setup-ci-component.sh').read_text()
        begin = source.index('if [[ "$component" == consumers || "$component" == consumers-pom-diagnostic || "$component" == dependency-update ]]; then')
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

    def test_actual_selection_requires_exact_temporary_host_and_tool(self):
        for component in ('consumers', 'consumers-pom-diagnostic', 'dependency-update'):
            self.assertEqual(self.selected(component),
                             (0, 'DEVELOPER_DIR=/Applications/Xcode_16.2.app/Contents/Developer\n'))
            for changed in ({'os_name': 'Linux'}, {'arch': 'X64'}, {'release': '26.0'},
                            {'xcode': '26.5'}, {'xcode': '16.20'}, {'present': False}):
                with self.subTest(component=component, changed=changed):
                    code, output = self.selected(component, **changed)
                    self.assertNotEqual(code, 0)
                    self.assertEqual(output, '')

    def test_native_and_installer_xcode_selection_remains_unchanged(self):
        for component in ('compatibility', 'apple-arm64', 'desktop-macos'):
            self.assertEqual(self.selected(component, release='26.0', xcode='26.5'),
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


if __name__ == '__main__': unittest.main()
