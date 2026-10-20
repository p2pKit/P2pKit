#!/usr/bin/env python3
"""Offline wiring controls only; never native or physical acceptance."""
import json
import plistlib
import importlib.util
from pathlib import Path
import tempfile
import types
import os
import unittest
from unittest import mock
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('apple_issue_validation', ROOT / 'scripts/run-apple-issue-validation.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
spec = importlib.util.spec_from_file_location('apple_issue_command', ROOT / 'scripts/run-apple-issue-command.py')
command = importlib.util.module_from_spec(spec)
spec.loader.exec_module(command)
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
                 'sourceBefore': SOURCE, 'sourceAfter': SOURCE, 'errors': [], 'ownedSurvivors': [],
                 'ownership': {'ownershipBoundary': module.HOSTED_BOUNDARY}}
        module.receipt_ok(valid, SOURCE)
        for key, value in [('productExitCode', None), ('stopExitCode', 1), ('sourceUnchanged', False),
                           ('sourceAfter', {}), ('errors', ['failure']), ('ownedSurvivors', ['live']), ('ownership', {})]:
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
                debug = app / 'p2pkit-sample.debug.dylib'
                debug.write_bytes(b'synthetic Debug dylib')
                def native_debug(command, **kwargs):
                    if command[1] == 'otool' and command[-1] == str(executable):
                        return b'@rpath/p2pkit-sample.debug.dylib\n'
                    return native(command, **kwargs)
                with mock.patch.object(module.subprocess, 'check_output', side_effect=native_debug):
                    module.inspect_iphoneos(directory, directory / 'debug-product.json')
                    self.assertIn('appDebugDylib', json.loads((directory / 'debug-product.json').read_text())['binaries'])
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

    def test_only_transfer_operation_selects_exact_native_arm_host(self):
        for operation in module.OPERATIONS:
            arm = operation == 'swift-jvm-transfer'
            environment = {'RUNNER_OS': 'macOS', 'RUNNER_ARCH': 'ARM64' if arm else 'X64'}
            machine, version = ('arm64', '26.1') if arm else ('x86_64', '15.7')
            with self.subTest(operation=operation), mock.patch.dict(os.environ, environment, clear=True), \
                    mock.patch.object(module.platform, 'system', return_value='Darwin'), \
                    mock.patch.object(module.platform, 'machine', return_value=machine), \
                    mock.patch.object(module.platform, 'mac_ver', return_value=(version, (), '')):
                self.assertEqual('macos-arm64' if arm else 'macos-x64', module.native_host(operation))
                for key, value in [('RUNNER_OS', 'Linux'), ('RUNNER_ARCH', 'X64' if arm else 'ARM64')]:
                    with mock.patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                        module.native_host(operation)
                with mock.patch.object(module.platform, 'machine', return_value='x86_64' if arm else 'arm64'), \
                        self.assertRaises(ValueError):
                    module.native_host(operation)
                with mock.patch.object(module.platform, 'mac_ver', return_value=('15.7' if arm else '26.1', (), '')), \
                        self.assertRaises(ValueError):
                    module.native_host(operation)
        with self.assertRaises(ValueError):
            module.native_host('unknown')

    def test_run_initializes_selected_architecture_with_exact_source_and_refuses_nested_context(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary).resolve()
            runner = types.SimpleNamespace(execute=mock.Mock(), result={'result': 'PASS'})
            environment = {'RUNNER_ENVIRONMENT': 'github-hosted', 'GITHUB_SHA': 'a' * 40}
            with mock.patch.dict(os.environ, environment, clear=True), \
                    mock.patch.object(module, 'native_host', return_value='macos-arm64') as host, \
                    mock.patch.object(module.subprocess, 'call', return_value=0) as execute, \
                    mock.patch.object(module, 'Run', return_value=runner):
                self.assertEqual(0, module.run(state, 'swift-jvm-transfer'))
                host.assert_called_once_with('swift-jvm-transfer')
                argv = execute.call_args.args[0]
                self.assertEqual('macos-arm64', argv[argv.index('--host') + 1])
                self.assertEqual('a' * 40, argv[argv.index('--expected-commit') + 1])
                execute.reset_mock()
                for mutation in ({'RUNNER_ENVIRONMENT': 'self-hosted'}, {'P2PKIT_AUDIT_JOB_ID': 'nested'}):
                    with mock.patch.dict(os.environ, mutation), self.assertRaises(ValueError):
                        module.run(state, 'swift-jvm-transfer')
                execute.assert_not_called()

    def test_wrong_xcode_fails_before_canonical_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary).resolve()
            (state / 'context.json').write_text(json.dumps({'source': SOURCE}))
            runner = module.Run(state, 'swift-jvm-transfer')
            with mock.patch.dict(os.environ, {'JAVA_HOME': '/synthetic/java'}), \
                    mock.patch.object(module.subprocess, 'check_output', return_value=b'Xcode 26.3\nBuild synthetic\n'), \
                    mock.patch.object(runner, 'invoke') as invoke, self.assertRaises(ValueError):
                runner.execute()
            invoke.assert_not_called()
            self.assertTrue((state / 'tools.json').is_file())

    def test_workflow_selects_maintained_arm_setup_only_for_transfer(self):
        workflow = (ROOT / '.github/workflows/apple-issue-validation.yml').read_text()
        self.assertIn("runs-on: ${{ inputs.operation == 'swift-jvm-transfer' && 'macos-26' || 'macos-15-intel' }}", workflow)
        self.assertIn("SETUP_COMPONENT: ${{ inputs.operation == 'swift-jvm-transfer' && 'apple-arm64' || 'consumers' }}", workflow)
        self.assertIn('bash scripts/setup-ci-component.sh "$SETUP_COMPONENT"', workflow)
        setup = (ROOT / 'scripts/setup-ci-component.sh').read_text()
        self.assertIn('ARM64 ]]; then xcode=/Applications/Xcode_26.5.app/Contents/Developer', setup)

    def test_workflow_encryption_step_describes_receipt_validation_not_native_execution(self):
        workflow = (ROOT / '.github/workflows/apple-issue-validation.yml').read_text()
        self.assertIn('scripts/run-apple-issue-validation.py run', workflow)
        self.assertIn('scripts/run-apple-issue-validation.py retain', workflow)
        self.assertIn("steps.native.outcome != 'skipped'", workflow)
        self.assertIn('--report-glob \'build/apple-issue-validation/**/*\'', workflow)
        self.assertNotIn('continue-on-error', workflow)
        self.assertNotIn('pull_request_target', workflow)
        self.assertNotIn('workflow_dispatch:', workflow)
        self.assertIn('workflow_call:', workflow)
        self.assertNotIn('secrets.', workflow)


class HostedCommandControls(unittest.TestCase):
    def environment(self):
        return {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted', 'GITHUB_REPOSITORY': 'p2pKit/P2pKit',
                'GITHUB_SHA': 'a' * 40, 'GITHUB_WORKFLOW_SHA': 'a' * 40, 'GITHUB_JOB': 'native',
                'GITHUB_WORKFLOW_REF': 'p2pKit/P2pKit/.github/workflows/ci.yml@refs/heads/synthetic'}

    def test_adapter_requires_actual_hosted_source_bound_ci_native_context(self):
        environment = self.environment()
        with mock.patch.object(command.evidence.platform, 'system', return_value='Darwin'):
            command.require_hosted_context(environment)
            for mutation in ({'GITHUB_JOB': 'other'}, {'RUNNER_ENVIRONMENT': 'self-hosted'},
                             {'GITHUB_ACTIONS': 'false'}, {'GITHUB_WORKFLOW_SHA': 'b' * 40},
                             {'GITHUB_REPOSITORY': 'other/repository'},
                             {'GITHUB_WORKFLOW_REF': 'p2pKit/P2pKit/.github/workflows/apple-issue-validation.yml@refs/heads/synthetic'},
                             {'GITHUB_WORKFLOW_REF': 'p2pKit/P2pKit/.github/workflows/ci.yml@'}):
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    command.require_hosted_context({**environment, **mutation})
        with mock.patch.object(command.evidence.platform, 'system', return_value='Linux'), self.assertRaises(ValueError):
            command.require_hosted_context(environment)

    def test_adapter_changes_only_scope_factory_preserving_exact_argv_and_failure_exit(self):
        executor = types.SimpleNamespace(main=mock.Mock(return_value=125), make_scope=None)
        argv = ['--purpose', 'xcode-provenance', '--timeout', '900', '--', 'original']
        with mock.patch.dict(os.environ, self.environment(), clear=True), \
                mock.patch.object(command.evidence.platform, 'system', return_value='Darwin'), \
                mock.patch.object(command, 'load_executor', return_value=executor):
            self.assertEqual(125, command.main(argv))
        self.assertIs(command.make_scope, executor.make_scope)
        executor.main.assert_called_once_with(argv)
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(command, 'load_executor') as load, self.assertRaises(ValueError):
            command.main(argv)
        load.assert_not_called()

    def test_adapter_inherits_all_existing_native_proofs_and_owned_cleanup(self):
        for name in ('_ownership_proof', 'discover', 'spawn', 'drain', '_send', '_acquire', 'close'):
            self.assertIs(getattr(command.HostedAppleScope, name), getattr(command.evidence._HostedDarwinScope, name))
        scope = object.__new__(command.HostedAppleScope)
        scope.outside_domain_observations = 3
        original = {'backend': 'darwin-libproc-audit-token', 'discoveryErrors': [], 'ownershipProofs': ['original']}
        with mock.patch.object(command.evidence._HostedDarwinScope, 'description', return_value=original):
            description = scope.description()
        self.assertEqual('original', description['ownershipProofs'][0])
        self.assertEqual(module.HOSTED_BOUNDARY, description['ownershipBoundary'])
        self.assertEqual(3, description['outsideDomainObservations'])
        with mock.patch.dict(os.environ, self.environment(), clear=True), \
                mock.patch.object(command.evidence.platform, 'system', return_value='Darwin'), \
                mock.patch.object(command, 'HostedAppleScope', return_value=scope) as factory:
            self.assertIs(scope, command.make_scope('job', 'invocation', 'state', 'home'))
        factory.assert_called_once_with('job', 'invocation', 'state', 'home')

    def test_driver_uses_adapter_for_leaf_and_nested_xcode_and_blocks_after_unknown_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary).resolve()
            (state / 'context.json').write_text(json.dumps({'source': SOURCE}))
            runner = module.Run(state, 'both')
            self.assertEqual(str(module.HOSTED_EXECUTOR), runner.environment['P2PKIT_GRADLE_EXECUTOR'])
            captured = []
            def execute(argv, **kwargs):
                captured.append((argv, kwargs))
                receipt = Path(argv[argv.index('--receipt') + 1])
                receipt.write_text(json.dumps({'errors': ['original cleanup failure'], 'ownedSurvivors': ['original'],
                                               'stopExitCode': 0, 'sourceUnchanged': True,
                                               'sourceBefore': SOURCE, 'sourceAfter': SOURCE,
                                               'ownership': {'ownershipBoundary': module.HOSTED_BOUNDARY}}))
                return 125
            with mock.patch.object(module.subprocess, 'call', side_effect=execute):
                with self.assertRaises(module.UnsafeRun):
                    runner.invoke('swift-jvm-transfer', ['original', 'command'], timeout=900)
                with self.assertRaises(ValueError):
                    runner.invoke('must-not-run', ['next'])
            self.assertEqual(1, len(captured))
            argv, kwargs = captured[0]
            self.assertEqual(str(module.HOSTED_EXECUTOR), argv[1])
            self.assertEqual('900', argv[argv.index('--timeout') + 1])
            self.assertEqual(['original', 'command'], argv[-2:])
            self.assertEqual(str(module.HOSTED_EXECUTOR), kwargs['env']['P2PKIT_GRADLE_EXECUTOR'])


class AppleTerminalControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terminal = module.terminal_module()

    def environment(self, temporary):
        parent = temporary / 'apple-issue-validation.synthetic'
        parent.mkdir(mode=0o700)
        return {'PATH': '/usr/bin:/bin', 'RUNNER_TEMP': str(temporary), 'APPLE_ISSUE_PARENT': str(parent),
            'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted', 'RUNNER_OS': 'macOS',
            'RUNNER_ARCH': 'ARM64', 'GITHUB_REPOSITORY': 'p2pKit/P2pKit', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
            'GITHUB_SHA': 'a' * 40, 'GITHUB_WORKFLOW_SHA': 'a' * 40, 'GITHUB_JOB': 'native',
            'GITHUB_REF': 'refs/heads/synthetic', 'GITHUB_WORKSPACE': str(ROOT), 'RUNNER_TRACKING_ID': 'synthetic',
            'GITHUB_WORKFLOW_REF': 'p2pKit/P2pKit/.github/workflows/ci.yml@refs/heads/synthetic',
            'P2PKIT_AUDIT_JDK21': '/synthetic/java21'}

    def test_fixed_arm_context_rejects_cross_profile_ref_source_ownership_and_injection(self):
        terminal = self.terminal
        component = terminal.APPLE_COMPONENT
        with tempfile.TemporaryDirectory() as temporary:
            env = self.environment(Path(temporary).resolve())
            with mock.patch.object(terminal.platform, 'system', return_value='Darwin'), \
                    mock.patch.object(terminal.platform, 'machine', return_value='arm64'), \
                    mock.patch.object(terminal.platform, 'mac_ver', return_value=('26.1', (), '')):
                terminal.environment_admit(env, component)
                for mutation in ({'RUNNER_ARCH': 'X64'}, {'GITHUB_JOB': 'component'}, {'GITHUB_EVENT_NAME': 'push'},
                    {'GITHUB_WORKFLOW_SHA': 'b' * 40}, {'GITHUB_REF': 'refs/heads/other'},
                    {'GITHUB_WORKFLOW_REF': 'p2pKit/P2pKit/.github/workflows/apple-issue-validation.yml@refs/heads/synthetic'},
                    {'P2PKIT_AUDIT_JDK21': ''}, {'P2PKIT_AUDIT_JOB_ID': 'nested'},
                    {'P2PKIT_AUDIT_OWNERSHIP_CHAIN': 'nested'}, {'P2PKIT_AUDIT_DARWIN_PIPES': 'nested'}):
                    with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                        terminal.environment_admit({**env, **mutation}, component)
                for other in terminal.PROFILES.keys() - {component}:
                    with self.subTest(component=other), self.assertRaises(RuntimeError):
                        terminal.environment_admit(env, other)
            self.assertEqual(terminal.allowed_environment(component) - terminal.ENVIRONMENT,
                             {'APPLE_ISSUE_PARENT', 'P2PKIT_AUDIT_JDK21'})
            self.assertTrue({'GH_TOKEN', 'GITHUB_TOKEN', 'JAVA_TOOL_OPTIONS', 'OPERATION',
                'P2PKIT_AUDIT_JOB_ID', 'P2PKIT_AUDIT_OWNERSHIP_CHAIN'}.isdisjoint(terminal.allowed_environment(component)))
            argv = terminal.command({**env, 'OPERATION': 'both', 'EXTRA_ARGS': '--arbitrary'}, component)
            self.assertEqual(argv, [str(Path(sys.executable).resolve()), '-B',
                str(ROOT / 'scripts/run-apple-issue-validation.py'), 'run', '--state',
                str(Path(env['APPLE_ISSUE_PARENT']) / 'state'), '--operation', 'swift-jvm-transfer'])
            self.assertNotIn('ci_evidence.py', ' '.join(argv))
            (Path(env['APPLE_ISSUE_PARENT']) / 'state').mkdir()
            with self.assertRaisesRegex(RuntimeError, 'APPLE_STATE_EXISTS'):
                terminal.command(env, component)
            # Post-run source/config readback must still admit the now-existing state.
            self.assertEqual(Path(env['APPLE_ISSUE_PARENT']), terminal.apple_parent(env))

    def test_parent_must_be_physical_private_direct_runner_temp_child(self):
        terminal = self.terminal
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            env = self.environment(root)
            parent = Path(env['APPLE_ISSUE_PARENT'])
            for value in ('relative', str(root / 'missing'), str(root), str(parent / 'nested')):
                with self.subTest(value=value), self.assertRaises((RuntimeError, OSError)):
                    terminal.apple_parent({**env, 'APPLE_ISSUE_PARENT': value})
            link = root / 'apple-issue-validation.link'
            link.symlink_to(parent, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                terminal.apple_parent({**env, 'APPLE_ISSUE_PARENT': str(link)})
            parent.chmod(0o755)
            with self.assertRaises(RuntimeError):
                terminal.apple_parent(env)

    def test_native_driver_pass_cannot_replace_original_terminal_finalization(self):
        terminal = self.terminal
        identity = {key: SOURCE[key] for key in ('commit', 'tree')}
        component = terminal.APPLE_COMPONENT
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            env = self.environment(root)
            parent = Path(env['APPLE_ISSUE_PARENT'])
            directory = root / 'ci-terminal-synthetic'
            directory.mkdir(mode=0o700)
            reference = {'schema': 1, 'component': component, 'source': identity, 'directory': str(directory)}
            terminal.private.write_json(parent / 'terminal-context.json', reference)
            documents = {
                'wrapper-result.json': {'schema': 1, 'component': component, 'source': identity,
                    'finalExitCode': 0, 'finalized': True, 'commandRemoved': True},
                'compile-result.json': {'code': 'PASS', 'cleanupKnown': True, 'capturesClosed': True},
                'application-result.json': dict(schema=3, executionMode=terminal.bounds(component)['mode'],
                    stage='FINALIZED', exitCode=0, failureCheck='NONE', openErrorDomain='NONE', openErrorCode=0,
                    **dict.fromkeys(terminal.terminal.APPLICATION_FLAGS, True)),
                'child-admission.json': {'source': identity, 'ancestry': {'method': terminal.terminal.ANCESTRY_METHOD,
                    'depth': 3, 'systemLoginAncestors': 1, 'restrictedCombinedDenials': 1}},
                'child-result.json': {'source': identity, 'exitCode': 0}}
            for name, document in documents.items():
                terminal.private.write_json(directory / name, document)
            terminal.private.write_new(directory / 'shell-result.txt', b'0\n')
            with mock.patch.dict(os.environ, env, clear=True):
                module.terminal_ok(parent, SOURCE)
                for name, key, value in (
                    ('wrapper-result.json', 'finalExitCode', 125), ('wrapper-result.json', 'finalized', False),
                    ('wrapper-result.json', 'finalExitCode', False), ('wrapper-result.json', 'finalized', 1),
                    ('wrapper-result.json', 'commandRemoved', False), ('wrapper-result.json', 'source', {}),
                    ('compile-result.json', 'cleanupKnown', False), ('compile-result.json', 'code', 'COMMAND_FAILED'),
                    ('application-result.json', 'applicationTerminated', False),
                    ('application-result.json', 'executionMode', 'modular-consumers'),
                    ('child-admission.json', 'source', {}), ('child-result.json', 'exitCode', 1)):
                    path = directory / name
                    path.write_text(json.dumps({**documents[name], key: value}))
                    with self.subTest(name=name, key=key), self.assertRaises((ValueError, RuntimeError)):
                        module.terminal_ok(parent, SOURCE)
                    path.write_text(json.dumps(documents[name]))
                (directory / 'shell-result.txt').write_bytes(b'1\n')
                with self.assertRaises(ValueError):
                    module.terminal_ok(parent, SOURCE)
                (directory / 'shell-result.txt').write_bytes(b'0\n')
                (directory / 'child-admission.json').unlink()
                with self.assertRaises(OSError):
                    module.terminal_ok(parent, SOURCE)

    def test_early_driver_failure_still_retains_original_terminal_partial_logs_and_shell_status(self):
        terminal = self.terminal
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            env = self.environment(root)
            parent = Path(env['APPLE_ISSUE_PARENT'])
            directory = root / 'ci-terminal-synthetic'
            directory.mkdir(mode=0o700)
            terminal.private.write_json(parent / 'terminal-context.json', {'schema': 1,
                'component': terminal.APPLE_COMPONENT, 'source': SOURCE, 'directory': str(directory)})
            terminal.private.write_json(directory / 'application-result.json', {'stage': 'CHILD', 'exitCode': 125})
            terminal.private.write_new(directory / 'child.stdout.log', b'original private synthetic failure')
            terminal.private.write_new(directory / 'shell-result.txt', b'1\n')
            terminal.private.write_new(parent / 'driver.log', b'finite wrapper failure')
            report = root / 'report'
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(module, 'REPORT', report), \
                    self.assertRaises(ValueError):
                module.retain(parent / 'state', parent / 'driver.log')
            self.assertEqual((report / 'terminal/child.stdout.log').read_bytes(), b'original private synthetic failure')
            self.assertEqual((report / 'terminal/shell-result.txt').read_bytes(), b'1\n')
            self.assertTrue((report / 'terminal/application-result.json').is_file())

    def test_workflow_terminal_overhead_does_not_change_probe_deadlines_or_intel_profiles(self):
        terminal = self.terminal
        budget = terminal.bounds(terminal.APPLE_COMPONENT)
        self.assertEqual(budget, {'mode': 'modular-apple-swift-jvm-transfer', 'command': 16200,
            'child': 16380, 'native': 16440, 'controller': 16500, 'wrapper': 16650})
        workflow = (ROOT / '.github/workflows/apple-issue-validation.yml').read_text()
        self.assertIn('if [[ "$OPERATION" == swift-jvm-transfer ]]; then', workflow)
        self.assertIn('scripts/run-ci-terminal-component.py --component apple-swift-jvm-transfer', workflow)
        self.assertIn("timeout-minutes: ${{ inputs.operation == 'swift-jvm-transfer' && 285 || 270 }}", workflow)
        self.assertIn("timeout-minutes: ${{ inputs.operation == 'swift-jvm-transfer' && 320 || 300 }}", workflow)
        controller = (ROOT / 'scripts/run-swift-jvm-transfer.py').read_text()
        self.assertIn('self.deadline = time.monotonic() + 360', controller)
        self.assertIn('self.cli.wait(timeout=30)', controller)
        self.assertEqual(terminal.bounds('macos-shared')['command'], 7200)
        self.assertEqual(terminal.bounds('jmdns-diagnostic')['command'], 1800)


if __name__ == '__main__':
    unittest.main()
