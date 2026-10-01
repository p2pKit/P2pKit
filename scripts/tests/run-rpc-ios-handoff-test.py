#!/usr/bin/env python3
"""Offline fake-file/receipt handoff controls; never Apple, Java or device execution."""
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ios_handoff_subject', ROOT / 'scripts/run-rpc-ios-handoff.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
runner = h.module('ios_handoff_pure_files', 'run-audit-command.py')
phone = h.module('ios_handoff_phone_parser', 'run-rpc-phone-ios-controls.py')
native_policy = h.module('ios_handoff_native_diagnostic_parser', 'run-rpc-qualification.py')


class HandoffControls(unittest.TestCase):
    runtime = 'com.apple.CoreSimulator.SimRuntime.iOS-26-4'

    def runtime_row(self):
        return dict(identifier=self.runtime, isAvailable=True, version='26.4', supportedArchitectures=['arm64'])

    def controls(self):
        return dict(simulatorArchitecture='arm64', runtimeVersion='26.4', unitMethods=10, uiMethods=2,
                    simulatorShutdown=True, simulatorDeleted=True, nestedFrameworkProducers=1,
                    nestedProvenanceChecks=2, deviceArchitecture='arm64', deviceMinimumOs='15.0')

    def public(self):
        return dict(schema=2, scope=h.SCOPE, source={'commit': 'a' * 40, 'tree': 'b' * 40}, result='PASS',
            sourceUnchanged=True, nativeControlTests=125, foundationStatus='NOT_READY', physicalInstallable=False,
            physicalQualification=False, mobileCapacityQualification=False, appleMatrixQualification=False,
            commands=[dict(purpose=p, exitCode=0, finalizationVerified=True) for p in h.PURPOSES],
            controls=self.controls(), artifacts={h.ARCHIVE: dict(bytes=100, sha256='a' * 64, files=2)},
            phoneDiagnostics=None, producerDiagnostic=None)

    def test_only_explicit_source_bound_supported_native_arm_context_is_admitted(self):
        env = dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted', GITHUB_REPOSITORY='p2pKit/P2pKit',
            GITHUB_REF=h.REF, GITHUB_EVENT_NAME='push', GITHUB_SHA='a' * 40, DEVELOPER_DIR=h.DEVELOPER,
            GITHUB_WORKSPACE=str(ROOT))
        with patch.object(h.platform, 'system', return_value='Darwin'), patch.object(h.platform, 'machine', return_value='arm64'), \
                patch.object(h.os, 'getuid', return_value=1001), patch.object(h.os, 'geteuid', return_value=1001):
            h.admit(env)
            for key, value in (('GITHUB_REF', 'refs/heads/main'), ('GITHUB_EVENT_NAME', 'pull_request'),
                               ('RUNNER_ENVIRONMENT', 'self-hosted'), ('GITHUB_WORKSPACE', '/'),
                               ('GITHUB_SHA', 'HEAD'), ('DEVELOPER_DIR', '/Applications/Xcode_26.3.app/Contents/Developer')):
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    h.admit({**env, key: value})
            with patch.object(h.platform, 'machine', return_value='x86_64'), self.assertRaises(RuntimeError): h.admit(env)
            with patch.object(h.os, 'getuid', return_value=0), self.assertRaises(RuntimeError): h.admit(env)

    def test_runtime_inventory_requires_actual_available_native_arm_support(self):
        row = self.runtime_row()
        self.assertEqual(h.runtime_selection({'runtimes': [row]}), self.runtime)
        for change in (dict(isAvailable=False), dict(isAvailable=1), dict(version='private'),
                       dict(supportedArchitectures=['x86_64']), dict(supportedArchitectures=['arm64', 'arm64']),
                       dict(supportedArchitectures=['arm64', 'PRIVATE']), dict(identifier='../other')):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                h.runtime_selection({'runtimes': [{**row, **change}]})
        for value in ({}, {'runtimes': []}, {'runtimes': [row, row]}):
            with self.assertRaises(RuntimeError): h.runtime_selection(value)

    def test_fixed_commands_keep_real_phone_controller_toolchains_and_native_executor(self):
        q = SimpleNamespace(NATIVE_ROLE_PROBE='fixed native probe')
        with patch.dict(os.environ, JAVA_HOME=str(ROOT), P2PKIT_AUDIT_JDK21=str(ROOT)):
            value = h.commands(Path('/owned/state'), q, self.runtime)
        self.assertEqual(tuple(value[p] for p in ('jdk17', 'jdk21')), tuple([str(ROOT / 'bin/java'), '-XshowSettings:properties', '-version'] for _ in range(2)))
        self.assertEqual(set(value), set(h.PURPOSES))
        self.assertEqual(value['phone-controls'][1], str(ROOT / 'scripts/run-rpc-phone-ios-controls.py'))
        self.assertIn('--owner-authorized-phone-controls', value['phone-controls'])
        self.assertEqual(value['phone-controls'][-1], self.runtime)
        self.assertEqual(value['native-controls'][2:4], ['--expected-host', 'macos-arm64'])
        source = (ROOT / 'scripts/run-rpc-ios-handoff.py').read_text()
        for forbidden in ('os.kill(', 'killall', 'setfacl', 'publishToMavenLocal', 'codesign --sign'):
            self.assertNotIn(forbidden, source)

    def test_actual_device_macho_target_is_required_not_plist_or_simulator_substitution(self):
        raw = b'fixture-app:\n  platform IOS\n  minos 15.0\n  sdk 26.4\n'
        h.verify_device_target(raw)
        for value in (b'', raw.replace(b'IOS', b'IOSSIMULATOR'), raw.replace(b'15.0', b'26.0'),
                      raw + raw, b'platform IOS\n', 'platform IOS\nminos 15.0\n'):
            with self.assertRaises(RuntimeError): h.verify_device_target(value)

    def test_unfinalized_native_invocation_cannot_start_subsequent_work(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, JAVA_HOME=str(ROOT), P2PKIT_AUDIT_JDK21=str(ROOT)):
            instance = object.__new__(h.Job)
            instance.state = Path(tmp).resolve()
            instance.private = instance.state / 'private'
            instance.private.mkdir()
            instance.result = dict(commands=[], runtime=None)
            instance.runner, instance.checker, instance.context = Mock(), Mock(), {}
            instance.q = SimpleNamespace(NATIVE_ROLE_PROBE='fixture-probe')
            instance.unsafe, instance.proofs = False, {}
            instance.runner.main.return_value = 125
            with patch.object(h, 'receipt', side_effect=RuntimeError('unfinalized')), self.assertRaises(RuntimeError):
                instance.invoke('native-controls')
            self.assertTrue(instance.unsafe)
            self.assertEqual(instance.result['commands'][0]['exitCode'], 125)
            self.assertFalse(instance.result['commands'][0]['verified'])
            with self.assertRaises(RuntimeError): instance.invoke('jdk17')
            self.assertEqual(instance.runner.main.call_count, 1)

    def test_outer_receipt_requires_exact_source_owner_kind_host_and_canonical_copy(self):
        state = Path('/owned/state')
        context = dict(id='job', source={'commit': 'a' * 40}, gradleHome='/owned/state/gradle-home')
        proof = dict(id='a' * 32, jobId='job', host='macos-arm64', kind='command', sourceBefore=context['source'],
            sourceAfter=context['source'], gradleHome=context['gradleHome'], ancestorInvocationIds=[], errors=[],
            ownedSurvivors=[], ownership={'discoveryErrors': []}, stopExitCode=0)
        fake, checker = Mock(), Mock()
        fake.read_json.return_value = proof
        self.assertEqual(h.receipt(fake, checker, state, context, 'native-controls', ['fixed-command'], 0), proof)
        for change in (dict(host='macos-x64'), dict(kind='gradle'), dict(jobId='foreign'), dict(gradleHome='/other'),
                       dict(ancestorInvocationIds=['foreign']), dict(sourceAfter={'commit': 'f' * 40}),
                       dict(errors=['FAILED']), dict(ownedSurvivors=[1]), dict(ownership={'discoveryErrors': ['unreadable']}),
                       dict(stopExitCode=1)):
            fake.read_json.return_value = {**proof, **change}
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                h.receipt(fake, checker, state, context, 'native-controls', ['fixed-command'], 0)
        fake.read_json.side_effect = [proof, {**proof, 'id': 'b' * 32}]
        with self.assertRaises(RuntimeError): h.receipt(fake, checker, state, context, 'native-controls', ['fixed-command'], 0)

    def make_app(self, root):
        app = root / 'p2pkit-rpc-phone.app'
        app.mkdir(parents=True, mode=0o700)
        (app / 'p2pkit-rpc-phone').write_bytes(b'OFFLINE-NOT-A-MACHO-OR-RUNNABLE-APP')
        (app / 'Info.plist').write_bytes(plistlib.dumps(dict(CFBundleIdentifier='dev.p2pkit.rpc.phonelab',
            CFBundleExecutable='p2pkit-rpc-phone', MinimumOSVersion='15.0')))
        for p in app.iterdir(): p.chmod(0o600)
        return app

    def test_archive_has_only_exact_unsigned_app_bytes_and_is_create_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            app, archive = self.make_app(root), root / h.ARCHIVE
            manifest = h.app_manifest(app, runner)
            row = h.export_app(app, archive, manifest, runner)
            self.assertEqual(row['files'], 2)
            self.assertEqual(row['sha256'], runner.file_digest(archive))
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(set(z.namelist()), {app.name + '/' + n for n in manifest})
                for name in manifest: self.assertEqual(z.read(app.name + '/' + name), (app / name).read_bytes())
            with self.assertRaises(RuntimeError): h.export_app(app, archive, manifest, runner)
            (app / 'p2pkit-rpc-phone').write_bytes(b'CHANGED')
            with self.assertRaises(RuntimeError): h.export_app(app, root / 'other.zip', manifest, runner)

    def test_signing_provisioning_symlink_hardlink_and_wrong_app_inputs_are_rejected(self):
        for kind in ('signature', 'provisioning', 'symlink', 'hardlink', 'writable', 'identity', 'minimum-os'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                app = self.make_app(root)
                if kind == 'signature':
                    (app / '_CodeSignature').mkdir()
                    (app / '_CodeSignature/CodeResources').write_bytes(b'PRIVATE-NOT-REAL')
                elif kind == 'provisioning': (app / 'embedded.mobileprovision').write_bytes(b'PRIVATE-NOT-REAL')
                elif kind == 'symlink': (app / 'alias').symlink_to(app / 'p2pkit-rpc-phone')
                elif kind == 'hardlink': os.link(app / 'p2pkit-rpc-phone', app / 'alias')
                elif kind == 'writable': (app / 'p2pkit-rpc-phone').chmod(0o666)
                else:
                    value = plistlib.loads((app / 'Info.plist').read_bytes())
                    value['CFBundleIdentifier' if kind == 'identity' else 'MinimumOSVersion'] = 'OTHER'
                    (app / 'Info.plist').write_bytes(plistlib.dumps(value))
                with self.assertRaises((RuntimeError, runner.AuditError)): h.app_manifest(app, runner)

    def test_closed_public_manifest_cannot_promote_partial_native_or_physical_results(self):
        value = self.public()
        h.validate_public(value, value['source'], 125)
        for change in (dict(schema=True), dict(nativeControlTests=True), dict(nativeControlTests=124), dict(sourceUnchanged=False),
                       dict(physicalInstallable=True), dict(physicalQualification=True), dict(mobileCapacityQualification=True),
                       dict(appleMatrixQualification=True), dict(foundationStatus='READY'), dict(private='SECRET'),
                       dict(commands=value['commands'][:-1]), dict(artifacts={}), dict(controls=None)):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                h.validate_public({**value, **change}, value['source'], 125)
        with self.assertRaises(RuntimeError): h.validate_public(value, value['source'], True)
        for change in (dict(simulatorDeleted=False), dict(simulatorShutdown=False), dict(simulatorArchitecture='x86_64'),
                       dict(unitMethods=True), dict(unitMethods=7), dict(uiMethods=1),
                       dict(nestedProvenanceChecks=1), dict(token='SECRET')):
            with self.assertRaises(RuntimeError): h.validate_public({**value, 'controls': {**value['controls'], **change}}, value['source'], 125)

    def test_failure_manifest_cannot_export_an_archive_or_partial_control_pass(self):
        value = {**self.public(), 'result': 'FAIL', 'artifacts': {}, 'controls': None}
        h.validate_public(value, value['source'], 125)
        for change in (dict(artifacts=self.public()['artifacts']), dict(controls=self.controls())):
            with self.assertRaises(RuntimeError): h.validate_public({**value, **change}, value['source'], 125)
        for change in (dict(exitCode=True), dict(exitCode='PRIVATE'), dict(exitCode=125), dict(purpose='foreign'), dict(raw='PRIVATE')):
            bad = self.public()
            bad['commands'][0].update(change)
            with self.assertRaises(RuntimeError): h.validate_public(bad, bad['source'], 125)

    def test_failed_phone_command_retains_only_closed_stage_and_boot_observations(self):
        private = dict(status='FAIL', simulatorTestsPassed=False, unsignedDeviceAppBuilt=False,
            simulatorShutdown=True, simulatorDeleted=True,
            commands=[dict(label='boot-readiness', timeoutSeconds=120,
                           startedUtc='2026-10-01T12:00:00+00:00')],
            errors=['RuntimeError: Command deadline; native owner must drain: boot-readiness',
                    'PRIVATE-INVITATION-AND-ENDPOINT'])
        logs = {'boot-readiness': {'stdout': b'Waiting on Data Migration\nStatus=2, isTerminal=NO, Elapsed=02:00\nPRIVATE',
                                  'stderr': b'PRIVATE'}}
        result = h.phone_diagnostics.observe(private, logs, ROOT)
        self.assertEqual(result['commands'][0]['exitCode'], None)
        self.assertEqual(result['commands'][0]['elapsedMillis'], None)
        self.assertEqual(result['errors'], [dict(category='COMMAND_DEADLINE', command='boot-readiness'),
                                          dict(category='UNCLASSIFIED', command=None)])
        self.assertEqual(result['logs']['logs']['boot-readiness']['stdout']['lastBootStatuses'],
                         [dict(status=2, terminal=False, elapsedSeconds=120)])
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertFalse(result['executionAdmitted'])

    def test_phone_diagnostics_never_admit_unknown_commands_types_or_raw_data(self):
        private = dict(status='FAIL', simulatorTestsPassed=False, unsignedDeviceAppBuilt=False,
                       simulatorShutdown=False, simulatorDeleted=False, commands=[], errors=[])
        result = h.phone_diagnostics.observe(private, {}, ROOT)
        for change in (dict(executionAdmitted=True), dict(private='SECRET'), dict(reportedStatus='SECRET'),
                       dict(resultAvailable=1), dict(errors=[dict(category='SECRET', command=None)]),
                       dict(commands=[dict(label='foreign', timeoutSeconds=120, exitCode=0, elapsedMillis=2)])):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                h.phone_diagnostics.validate({**result, **change}, ROOT)
        for row in (dict(label='foreign', timeoutSeconds=120), dict(label='boot-readiness', timeoutSeconds=121),
                    dict(label='boot-readiness', timeoutSeconds=120, exitCode=True),
                    dict(label='boot-readiness', timeoutSeconds=120, startedUtc='PRIVATE')):
            with self.subTest(row=row), self.assertRaises(RuntimeError):
                h.phone_diagnostics.observe({**private, 'commands': [row]}, {}, ROOT)
        with self.assertRaises(RuntimeError):
            h.phone_diagnostics.observe({**private, 'simulatorShutdown': 1}, {}, ROOT)

    def test_phone_diagnostic_missing_result_is_not_a_success_or_known_cleanup(self):
        result = h.phone_diagnostics.observe(None, {'phone-controls': {'stdout': b'', 'stderr': b''}}, ROOT)
        self.assertFalse(result['resultAvailable'])
        self.assertIsNone(result['reportedStatus'])
        self.assertTrue(all(value is None for value in result['reportedFlags'].values()))
        self.assertEqual(result['commands'], [])
        self.assertFalse(result['executionAdmitted'])

    def test_phone_diagnostic_wall_intervals_preserve_clock_reversal_and_closed_bounds(self):
        private = dict(status='FAIL', simulatorTestsPassed=False, unsignedDeviceAppBuilt=False,
            simulatorShutdown=True, simulatorDeleted=True, errors=[], commands=[dict(label='framework-producer',
                timeoutSeconds=3900, exitCode=125, startedUtc='2026-10-01T12:00:00+00:00',
                endedUtc='2026-10-01T11:59:59+00:00')])
        result = h.phone_diagnostics.observe(private, {}, ROOT)
        self.assertEqual(result['commands'][0]['elapsedMillis'], -1000)
        self.assertEqual(result['commands'][0]['exitCode'], 125)
        self.assertFalse(result['executionAdmitted'])
        with self.assertRaises(RuntimeError):
            h.phone_diagnostics.observe({**private, 'commands': private['commands'] * 2}, {}, ROOT)

    @contextmanager
    def fixture(self):
        """Real files/parsers, invented producer/native receipts; NOT actual Apple evidence."""
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp).resolve()
            parent, root = temp / 'job', temp / 'source'
            parent.mkdir(mode=0o700)
            (root / 'scripts').mkdir(parents=True)
            (root / 'scripts/run-rpc-phone-ios-controls.py').write_bytes(b'offline-script')
            (root / 'gradle').mkdir()
            shutil.copyfile(ROOT / 'gradle/platform-test-policy.json', root / 'gradle/platform-test-policy.json')
            for name, _, _ in phone.TARGETS.values():
                destination = root / 'samples/p2p-sample-rpc/phone-ios' / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / 'samples/p2p-sample-rpc/phone-ios' / name, destination)
            state = parent / 'state'
            work = state / 'work/phone-controls'
            for path in (state / 'private', work, state / 'tools/xcodegen/bin'): path.mkdir(parents=True, mode=0o700)
            xcodegen = state / 'tools/xcodegen/bin/xcodegen'
            xcodegen.write_bytes(b'offline-not-executable')
            context = dict(id='job', source={**self.public()['source'], 'status': '', 'diffSha256': 'c' * 64}, gradleHome=str(state / 'gradle-home'))
            q = SimpleNamespace(NATIVE_ROLE_PROBE='fixture-native-probe', control_inventory=lambda _: 125,
                unittest_count=lambda _: 125, admit_native_apple_role=Mock(),
                receipt_diagnostic=native_policy.receipt_diagnostic, validate_diagnostic=native_policy.validate_diagnostic)
            fake = SimpleNamespace(absolute_path=lambda _: parent, context_at=lambda _: (state, context),
                read_json=runner.read_json, write_new_json=runner.write_new_json, file_digest=runner.file_digest,
                source_snapshot=Mock(return_value=context['source']), reject_symlinks=runner.reject_symlinks,
                regular_report_files=runner.regular_report_files)
            proofs = {p: dict(id=h.hashlib.sha256(p.encode()).hexdigest()[:32]) for p in h.PURPOSES}
            outputs = {'native-controls': ('', 'Ran 125 tests\nOK\n'),
                'jdk17': ('', 'java.specification.version = 17\nos.arch = aarch64\n'),
                'jdk21': ('', 'java.specification.version = 21\nos.arch = aarch64\n'),
                'macos-version': ('26.0\n', ''), 'xcode-version': ('Xcode 26.5\nBuild version fixture\n', ''),
                'rosetta-admission': ('fixture-native-probe', ''),
                'phone-runtimes': (json.dumps({'runtimes': [self.runtime_row()]}), '')}
            for purpose, proof in proofs.items():
                folder = state / 'evidence' / proof['id']
                folder.mkdir(parents=True)
                for stream, text in zip(('stdout', 'stderr'), outputs.get(purpose, ('', ''))):
                    (folder / ('product.' + stream + '.log')).write_text(text)
                runner.write_new_json(state / 'private' / (purpose + '.json'), proof)
            nested = []
            for n, purpose in enumerate(('rpc-phone-framework-producer', 'rpc-phone-xcode-provenance', 'rpc-phone-xcode-provenance')):
                identifier = str(n + 1) * 32
                path = state / 'evidence' / identifier / 'receipt.json'
                path.parent.mkdir()
                proof = dict(id=identifier, jobId=context['id'], sourceBefore=context['source'], sourceAfter=context['source'],
                    gradleHome=context['gradleHome'], ancestorInvocationIds=[proofs['phone-controls']['id']], purpose=purpose,
                    host='macos-arm64', kind='gradle', errors=[], ownedSurvivors=[], ownership={'discoveryErrors': []}, stopExitCode=0,
                    requestedArgv=[phone.FRAMEWORK_TASK, '--console=plain'] if n == 0 else [phone.FRAMEWORK_TASK, '-q', '--console=plain'])
                runner.write_new_json(path, proof)
                nested.append(dict(id=identifier, sha256=runner.file_digest(path)))
            objects = [{'summaries': [{'_type': {'_name': 'ActionTestableSummary'}, 'targetName': {'_value': target},
                'tests': [{'_type': {'_name': 'ActionTestMetadata'}, 'identifier': {'_value': name}, 'testStatus': {'_value': 'Success'}}
                          for name in sorted(methods)]} for target, methods in phone.inventory(root).items()]}]
            runner.write_new_json(work / 'xcresult-tests-0.stdout', objects[0])
            (work / 'phone-unit-ui.stdout').write_bytes(b'** TEST SUCCEEDED **\n')
            (work / 'device-architectures.stdout').write_bytes(b'arm64\n')
            (work / 'device-minimum-os.stdout').write_bytes(b'fixture:\n platform IOS\n minos 15.0\n')
            app = self.make_app(work / 'device-derived/Build/Products/Debug-iphoneos')
            manifest = h.app_manifest(app, fake)
            runner.write_new_json(work / 'unsigned-device-app-manifest.json', manifest)
            result = dict(schema=1, scope=phone.SCOPE, status='PASS_REQUIRES_OUTER_FINALIZATION', source=context['source'],
                scriptSha256=runner.file_digest(root / 'scripts/run-rpc-phone-ios-controls.py'), architecture='arm64', runtime=self.runtime,
                runtimeVersion='26.4', xcodegenSha256=runner.file_digest(xcodegen), errors=[], simulatorTestsPassed=True,
                simulatorShutdown=True, simulatorDeleted=True, unsignedDeviceAppBuilt=True, physicalInstallable=False,
                capacityQualified=False, commands=[], methods=phone.assess_xctest(objects, phone.inventory(root)),
                nestedFrameworkProducer=nested[:1], nestedProvenance=nested[1:], frameworkProducerReceiptSha256=nested[0]['sha256'],
                unsignedDeviceApp=str(app))
            runner.write_new_json(work / 'result.json', result)
            with patch.object(h, 'ROOT', root), patch.dict(os.environ, JAVA_HOME=str(root), P2PKIT_AUDIT_JDK21=str(root),
                    RPC_QUALIFICATION_PARENT=str(parent), RUNNER_TEMP=str(temp), GITHUB_SHA=context['source']['commit']):
                original = dict(schema=1, scope=h.SCOPE, source=context['source'], result='PASS', sourceUnchanged=True,
                    nativeControlTests=125, runtime=self.runtime, commands=[dict(purpose=p, argv=h.commands(state, q, self.runtime)[p],
                        exitCode=0, verified=True, receiptSha256=runner.file_digest(state / 'private' / (p + '.json'))) for p in h.PURPOSES])
                runner.write_new_json(state / 'private/result.json', original)
                modules = {'run-audit-command.py': fake, 'check-audit-receipt.py': Mock(), 'run-rpc-qualification.py': q,
                    'run-rpc-phone-ios-controls.py': phone, 'run-rpc-capacity-lab.py': SimpleNamespace(private_directory=Mock())}
                with patch.object(h, 'admit'), patch.object(h, 'module', side_effect=lambda _, name: modules[name]), \
                        patch.object(h, 'receipt', side_effect=lambda _r, _c, _s, _ctx, p, _a, _code: proofs[p]) as receipts:
                    yield SimpleNamespace(parent=parent, root=root, state=state, work=work, context=context, original=original,
                        result=result, runner=fake, q=q, app=app, manifest=manifest, proofs=proofs, receipts=receipts)

    def test_real_phone_parsers_reject_missing_lifecycle_provenance_or_native_fields(self):
        for change in (dict(simulatorDeleted=False), dict(simulatorShutdown=False), dict(architecture='x86_64'),
                       dict(status='FAIL'), dict(nestedProvenance=[]), dict(nestedFrameworkProducer=[]),
                       dict(errors=['FAILED']), dict(physicalInstallable=True), dict(capacityQualified=True)):
            with self.subTest(change=change), self.fixture() as f:
                (f.work / 'result.json').write_text(json.dumps({**f.result, **change}))
                with self.assertRaises(RuntimeError):
                    h.assess_phone(f.state, f.context, f.proofs['phone-controls'], self.runtime, f.runner, Mock(), phone)

    def test_nested_producer_cannot_be_a_foreign_source_owner_or_gradle_home(self):
        for change in (dict(host='macos-x64'), dict(jobId='foreign'), dict(gradleHome='/foreign'),
                       dict(ancestorInvocationIds=[]), dict(kind='command'), dict(ownedSurvivors=[1]),
                       dict(sourceAfter={'commit': 'f' * 40}), dict(ownership={'discoveryErrors': ['unreadable']})):
            with self.subTest(change=change), self.fixture() as f:
                row = f.result['nestedFrameworkProducer'][0]
                path = f.state / 'evidence' / row['id'] / 'receipt.json'
                value = runner.read_json(path)
                path.write_text(json.dumps({**value, **change}))
                row['sha256'] = runner.file_digest(path)
                f.result['frameworkProducerReceiptSha256'] = row['sha256']
                (f.work / 'result.json').write_text(json.dumps(f.result))
                with self.assertRaises(RuntimeError):
                    h.assess_phone(f.state, f.context, f.proofs['phone-controls'], self.runtime, f.runner, Mock(), phone)

    def test_collector_rechecks_all_commands_actual_method_json_and_archive_before_atomic_export(self):
        with self.fixture() as f:
            self.assertEqual(h.collect(), 0)
            self.assertEqual(f.receipts.call_count, len(h.PURPOSES))
            self.assertEqual(set(p.name for p in (f.parent / 'public').iterdir()), {h.ARCHIVE, 'manifest.json'})
            manifest = runner.read_json(f.parent / 'public/manifest.json')
            self.assertEqual(manifest['controls'], self.controls())
            self.assertFalse(manifest['physicalInstallable'])
            self.assertFalse(manifest['appleMatrixQualification'])
            self.assertEqual(manifest['artifacts'][h.ARCHIVE]['sha256'], runner.file_digest(f.parent / 'public' / h.ARCHIVE))
            self.assertFalse((f.parent / 'export-staging').exists())
            f.q.admit_native_apple_role.assert_called_once()

    def test_unverified_outer_native_receipt_yields_only_failed_manifest(self):
        with self.fixture() as f:
            f.receipts.side_effect = RuntimeError('unproven')
            self.assertEqual(h.collect(), 1)
            self.assertEqual([p.name for p in (f.parent / 'public').iterdir()], ['manifest.json'])
            self.assertTrue(all(not r['finalizationVerified'] for r in runner.read_json(f.parent / 'public/manifest.json')['commands']))

    def test_failed_controller_keeps_actual_closed_observations_without_exporting_an_app(self):
        with self.fixture() as f:
            f.original['result'] = 'FAIL'
            f.original['commands'][-1]['exitCode'] = 1
            (f.state / 'private/result.json').write_text(json.dumps(f.original))
            f.result.update(status='FAIL', simulatorTestsPassed=False, unsignedDeviceAppBuilt=False,
                commands=[dict(label='boot-readiness', timeoutSeconds=120, startedUtc='2026-10-01T12:00:00+00:00')],
                errors=['RuntimeError: Command deadline; native owner must drain: boot-readiness'])
            (f.work / 'result.json').write_text(json.dumps(f.result))
            (f.work / 'boot-readiness.stdout').write_bytes(b'Waiting on Data Migration\nPRIVATE')
            (f.work / 'boot-readiness.stderr').write_bytes(b'PRIVATE')
            self.assertEqual(h.collect(), 1)
            value = runner.read_json(f.parent / 'public/manifest.json')
            self.assertEqual(value['phoneDiagnostics']['errors'][0]['category'], 'COMMAND_DEADLINE')
            self.assertFalse(value['phoneDiagnostics']['executionAdmitted'])
            self.assertEqual(value['artifacts'], {})
            self.assertIsNone(value['controls'])
            self.assertNotIn('PRIVATE', json.dumps(value))
            self.assertEqual([p.name for p in (f.parent / 'public').iterdir()], ['manifest.json'])

    def test_observation_rejects_wrong_source_scope_script_or_symlinked_result(self):
        for field, value in (('source', {'commit': 'f' * 40}), ('scope', 'FOREIGN'), ('schema', True),
                             ('architecture', 'x86_64'), ('runtime', 'FOREIGN'), ('scriptSha256', 'f' * 64), ('symlink', None)):
            with self.subTest(field=field), self.fixture() as f:
                path = f.work / 'result.json'
                if field == 'symlink':
                    path.rename(f.work / 'other.json')
                    path.symlink_to(f.work / 'other.json')
                else:
                    path.write_text(json.dumps({**f.result, field: value}))
                with self.assertRaises((RuntimeError, runner.AuditError, ValueError)):
                    h.phone_observations(f.state, f.context, f.proofs['phone-controls'], self.runtime, f.runner, f.q)

    def test_failed_nested_producer_is_diagnostic_not_admission_and_cannot_belong_to_another_owner(self):
        for change in (None, dict(jobId='foreign'), dict(ancestorInvocationIds=[]), dict(host='macos-x64'),
                       dict(gradleHome='/foreign'), dict(sourceBefore={'commit': 'f' * 40}), dict(requestedArgv=['true'])):
            with self.subTest(change=change), self.fixture() as f:
                p = f.state / 'evidence' / f.result['nestedFrameworkProducer'][0]['id'] / 'receipt.json'
                proof = runner.read_json(p)
                proof.update(sourceUnchanged=True, finalExitCode=125, productExitCode=1,
                             errors=['PRIVATE-UNRECOGNIZED-ERROR'])
                if change: proof.update(change)
                p.write_text(json.dumps(proof))
                (f.work / 'framework-producer.json').write_text(json.dumps(proof))
                if change:
                    with self.assertRaises(RuntimeError):
                        h.phone_observations(f.state, f.context, f.proofs['phone-controls'], self.runtime, f.runner, f.q)
                else:
                    _, observed = h.phone_observations(f.state, f.context, f.proofs['phone-controls'], self.runtime, f.runner, f.q)
                    self.assertEqual(observed['errorKinds'], ['OTHER'])
                    self.assertEqual(observed['finalExitCode'], 125)
                    self.assertNotIn('PRIVATE', json.dumps(observed))

    def test_manifest_refuses_unowned_phone_or_private_native_observations(self):
        value = self.public()
        value['phoneDiagnostics'] = h.phone_diagnostics.observe(None, {}, ROOT)
        h.validate_public(value, value['source'], 125)
        bad = {**value, 'commands': value['commands'][:-1], 'result': 'FAIL', 'artifacts': {}, 'controls': None}
        with self.assertRaises(RuntimeError): h.validate_public(bad, bad['source'], 125)
        with self.assertRaises(RuntimeError):
            h.validate_public({**value, 'producerDiagnostic': {'PRIVATE': 'DATA'}}, value['source'], 125)

    def test_phone_process_diagnostics_cannot_substitute_intel_for_native_arm(self):
        value = {**self.public(), 'result': 'FAIL', 'controls': None, 'artifacts': {}}
        boot = dict(schema=1, scope=h.phone_diagnostics.boot.SCOPE, nativeRole='macos-arm64',
            executionAdmitted=False, elapsedNanos=1, unobservedTailNanos=1, intervals=[])
        private = dict(status='FAIL', errors=[], commands=[dict(label='boot-readiness', timeoutSeconds=120,
            exitCode=None, processObservation=boot)], **dict.fromkeys(h.phone_diagnostics.FLAGS, False))
        value['phoneDiagnostics'] = h.phone_diagnostics.observe(private, {}, ROOT)
        h.validate_public(value, value['source'], 125)
        value['phoneDiagnostics']['bootProcesses']['nativeRole'] = 'macos-x64'
        with self.assertRaises(RuntimeError):
            h.validate_public(value, value['source'], 125)

    def test_failed_test_json_modified_app_or_wrong_runtime_prevents_binary_export(self):
        for failure in ('test', 'app', 'runtime', 'toolchain', 'command'):
            with self.subTest(failure=failure), self.fixture() as f:
                if failure == 'test':
                    p = f.work / 'xcresult-tests-0.stdout'
                    p.write_text(p.read_text().replace('Success', 'Failure', 1))
                elif failure == 'app': (f.app / 'p2pkit-rpc-phone').write_bytes(b'CHANGED')
                elif failure == 'toolchain':
                    (f.state / 'evidence' / f.proofs['jdk17']['id'] / 'product.stderr.log').write_text('java.specification.version = 17\nos.arch = amd64\n')
                else:
                    if failure == 'runtime': f.original['runtime'] = 'com.apple.CoreSimulator.SimRuntime.iOS-25-0'
                    else: f.original['commands'][0]['argv'] = ['true']
                    (f.state / 'private/result.json').write_text(json.dumps(f.original))
                with self.assertRaises(RuntimeError): h.collect()
                self.assertFalse((f.parent / 'public').exists())

    def test_copy_failure_and_source_drift_keep_archive_on_private_staging_path(self):
        for failure in ('copy', 'source'):
            with self.subTest(failure=failure), self.fixture() as f:
                export = h.export_app
                def copy_app(app, target, manifest, owner):
                    row = export(app, target, manifest, owner)
                    if failure == 'copy': raise OSError('copy fixture failure')
                    return row
                if failure == 'source': f.runner.source_snapshot.side_effect = [f.context['source'], {**f.context['source'], 'status': 'modified'}]
                with patch.object(h, 'export_app', side_effect=copy_app), self.assertRaises((RuntimeError, OSError)):
                    h.collect()
                self.assertFalse((f.parent / 'public').exists())
                self.assertTrue((f.parent / 'export-staging' / h.ARCHIVE).is_file())

    def test_workflow_is_explicit_native_unsigned_private_and_independent_of_full_matrix(self):
        source = (ROOT / '.github/workflows/rpc-ios-handoff.yml').read_text()
        for expected in ('[rpc-ios-handoff]', 'runs-on: macos-26', '/Applications/Xcode_26.5.app/Contents/Developer',
                         'cancel-in-progress: false', 'persist-credentials: false', 'fetch-tags: false', '--unshallow',
                         'with-darwin-audit-session.py', '--owner-authorized-phone-handoff', "steps.collect.outcome == 'success'",
                         '/public/p2pkit-rpc-iphone-unsigned.app.zip', 'retention-days: 7'):
            self.assertIn(expected, source)
        for forbidden in ('appleMatrixQualification: true', 'codesign', 'cache:', '/private/', '/state/', 'run-rpc-qualification.py run'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
