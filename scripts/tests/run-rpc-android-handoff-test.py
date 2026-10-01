#!/usr/bin/env python3
"""Offline handoff/negative export controls; never SDK, APK, Java or AVD execution."""
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('android_handoff_test_subject', ROOT / 'scripts/run-rpc-android-handoff.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
phone = h.module('android_handoff_existing_controls', 'run-rpc-android-controls.py')


class HandoffControls(unittest.TestCase):
    def test_apk_hash_uses_its_own_128_mib_bound_not_the_8_mib_report_limit(self):
        # A normal APK is not a small JSON report. Exercise the real hashing
        # and export path above the report limit, without an SDK or real APK.
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / 'source.apk', Path(tmp) / 'staged.apk'
            data = b'\x07' * (h.evidence.LIMIT + 1)
            source.write_bytes(data)
            source.chmod(0o600)
            expected = dict(bytes=len(data), sha256=h.hashlib.sha256(data).hexdigest())
            self.assertEqual(h.apk_metadata(source, Mock()), expected)
            h.export_apk(source, target, expected, Mock())
            self.assertEqual(h.apk_metadata(target, Mock()), expected)
            # Do not fix binary delivery by expanding the evidence parser's
            # global limit or allowing large arbitrary public reports.
            with self.assertRaises(ValueError):
                h.evidence.file_hash(source)

    def test_oversize_apk_is_rejected_before_reading_its_sparse_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'too-large.apk'
            with source.open('xb') as stream:
                stream.truncate(128 * 1024 * 1024 + 1)
            source.chmod(0o600)
            with self.assertRaises(RuntimeError):
                h.apk_metadata(source, Mock())

    def test_apk_changed_during_hashing_is_not_admitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source.apk'
            source.write_bytes(b'offline-fixture')
            source.chmod(0o600)
            before = source.stat()
            changed = SimpleNamespace(**{name: getattr(before, name) for name in
                ('st_dev', 'st_ino', 'st_uid', 'st_mode', 'st_size', 'st_mtime_ns', 'st_nlink')})
            changed.st_mtime_ns += 1
            with patch.object(h.os, 'fstat', side_effect=[before, changed]), self.assertRaises(RuntimeError):
                h.apk_metadata(source, Mock())

    def test_successful_native_apk_producer_keeps_closed_diagnostics_and_reaches_emulator_prerequisite(self):
        # Reproduce the hosted failure AFTER a zero-exit, verified producer.
        # Do not mock the diagnostic parser/validator: that boundary was missing
        # from the original orchestration fixture. No real product is executed.
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, JAVA_HOME=str(ROOT), P2PKIT_AUDIT_JDK21=str(ROOT)):
            instance = object.__new__(h.Job)
            instance.state = Path(tmp).resolve()
            instance.private = instance.state / 'private'
            instance.private.mkdir()
            instance.result = {'commands': [], 'productDiagnostics': {}}
            instance.unsafe = False
            instance.runner, instance.checker, instance.context = Mock(), Mock(), {}
            instance.runner.main.return_value = 0
            instance.runner.file_digest.return_value = 'a' * 64
            logs = instance.state / 'evidence' / ('a' * 32)
            logs.mkdir(parents=True)
            (logs / 'product.stdout.log').write_bytes(b'BUILD SUCCESSFUL in 1s\n')
            (logs / 'product.stderr.log').write_bytes(b'')
            proof = {'id': 'a' * 32}
            with patch.object(h, 'receipt', return_value=proof):
                actual = instance.invoke('android-apk-producer', h.commands(instance.state)['android-apk-producer'],
                                         h.BOUNDS['android-apk-producer'], 'gradle')
            self.assertEqual(actual, proof)
            self.assertFalse(instance.unsafe)
            self.assertTrue(instance.result['commands'][0]['verified'])
            result = instance.result['productDiagnostics']
            self.assertEqual(set(result['build']), {'android-apk-producer'})
            self.assertFalse(result['build']['android-apk-producer']['stdout']['executionAdmitted'])
            for purpose, admitted in (('unregistered-producer', h.PURPOSES), ('android-apk-producer', ())):
                with self.assertRaises(ValueError):
                    h.diagnostics.validate({'build': {purpose: result['build']['android-apk-producer']}}, ROOT, admitted)

    def value(self):
        token = 'c' * 32
        fields = dict(rpcToken=token, rpcApi='24', rpcAbi='x86_64', rpcVm='Dalvik', rpcScope=phone.SCOPE,
                      rpcOutcome='PASS', rpcCleanup='PASS', rpcCompleted='10')
        fields.update({f'rpcControl{i}': name for i, name in enumerate(phone.CONTROL_NAMES, 1)})
        return dict(source={'commit': 'a' * 40}, status='PASS', scope=phone.SCOPE,
            producerReceiptSha256='b' * 64, scriptSha256=h.evidence.file_hash(ROOT / 'scripts/run-rpc-android-controls.py'),
            appSha256='d' * 64, testApkSha256='e' * 64, booted=True, controlsPassed=True, naturalCleanup=True,
            errors=[], capacityQualified=False, acceleration='off', api=24, cores=1, bootSeconds=123.45,
            instrumentation=fields, imageProperties='Pkg.Revision=8\n', emulatorProperties='Pkg.Revision=36.2.10\n')

    def assess(self, value):
        return h.assess_controls(value, {'source': {'commit': 'a' * 40}}, 'b' * 64, 'd' * 64, 'e' * 64, phone)

    def test_only_source_bound_complete_ten_control_result_is_accepted_without_runtime_identifiers(self):
        value = self.value()
        result = self.assess(value)
        self.assertEqual(result['controlsPassed'], 10)
        self.assertEqual(result['api'], 24)
        self.assertNotIn('rpcToken', result)
        self.assertNotIn('buildFingerprint', result)
        for change in (dict(source={'commit': 'f' * 40}), dict(status='FAIL'), dict(booted=False),
                       dict(controlsPassed=False), dict(naturalCleanup=False), dict(errors=['private']),
                       dict(api=37), dict(api=True), dict(acceleration='kvm'), dict(capacityQualified=True),
                       dict(appSha256='f' * 64), dict(testApkSha256='f' * 64), dict(bootSeconds=601)):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.assess({**value, **change})

    def test_incomplete_duplicate_or_foreign_instrumentation_is_not_a_phone_pass(self):
        for key, value in (('rpcCompleted', '7'), ('rpcCompleted', '8'), ('rpcControl8', phone.CONTROL_NAMES[0]),
                           ('rpcVm', 'OpenJDK'), ('rpcAbi', 'arm64-v8a'), ('rpcToken', ''), ('rpcScope', 'physical')):
            changed = self.value()
            changed['instrumentation'][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.assess(changed)

    def test_package_metadata_exports_only_one_revision(self):
        self.assertEqual(h.package_revision('Secret=PRIVATE\nPkg.Revision = 36.2.10\n'), '36.2.10')
        for text in ('Pkg.Revision=PRIVATE\n', 'Pkg.Revision=1\nPkg.Revision=2\n', 'x' * 65537):
            with self.assertRaises(RuntimeError):
                h.package_revision(text)

    def test_fixed_inventory_keeps_both_apks_existing_emulator_controller_and_no_kvm_setup(self):
        with patch.dict(os.environ, JAVA_HOME=str(ROOT), P2PKIT_AUDIT_JDK21=str(ROOT)):
            commands = h.commands(Path('/owned/state'))
        self.assertEqual(set(commands), set(h.PURPOSES))
        self.assertEqual(commands['android-apk-producer'], [*h.TASKS, '--console=plain', '--warning-mode=fail', '--stacktrace'])
        self.assertEqual(commands['supplemental-api24'][1], str(ROOT / 'scripts/run-rpc-android-controls.py'))
        self.assertIn('--owner-authorized-software-emulator', commands['supplemental-api24'])
        self.assertEqual(h.BOUNDS['supplemental-api24'], 1800)
        self.assertIn('system-images;android-24;default;x86_64', h.PACKAGES)
        text = (ROOT / 'scripts/run-rpc-android-handoff.py').read_text()
        for forbidden in ('setfacl', 'chmod /dev', 'kvm-restored', 'os.kill(', 'killall', 'publishToMavenLocal'):
            self.assertNotIn(forbidden, text)

    def test_foreign_platform_root_or_unmarked_context_cannot_initialize(self):
        env = dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted', GITHUB_REPOSITORY='p2pKit/P2pKit',
            GITHUB_REF=h.REF, GITHUB_EVENT_NAME='push', RPC_ANDROID_HANDOFF_REQUESTED='true',
            GITHUB_SHA='a' * 40, GITHUB_WORKSPACE=str(ROOT))
        with patch.object(h.platform, 'system', return_value='Linux'), patch.object(h.platform, 'machine', return_value='x86_64'), \
                patch.object(h.os, 'getuid', return_value=1001), patch.object(h.os, 'geteuid', return_value=1001):
            h.admit(env)
            for key, value in (('GITHUB_REF', 'refs/heads/main'), ('GITHUB_EVENT_NAME', 'pull_request'),
                               ('RPC_ANDROID_HANDOFF_REQUESTED', 'false'), ('RUNNER_ENVIRONMENT', 'self-hosted'),
                               ('GITHUB_SHA', 'HEAD'), ('GITHUB_WORKSPACE', '/')):
                with self.assertRaises(RuntimeError):
                    h.admit({**env, key: value})
            with patch.object(h.os, 'getuid', return_value=0), self.assertRaises(RuntimeError):
                h.admit(env)
            with patch.object(h.platform, 'machine', return_value='arm64'), self.assertRaises(RuntimeError):
                h.admit(env)

    def test_export_is_create_only_bounded_and_content_checked_in_private_staging(self):
        runner = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / 'source.apk', Path(tmp) / 'staged.apk'
            source.write_bytes(b'fixture-not-a-real-apk')
            source.chmod(0o600)
            expected = h.apk_metadata(source, runner)
            h.export_apk(source, target, expected, runner)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            with self.assertRaises(FileExistsError):
                h.export_apk(source, target, expected, runner)
            with self.assertRaises(RuntimeError):
                h.export_apk(source, Path(tmp) / 'mismatched.apk', {**expected, 'sha256': '0' * 64}, runner)
            self.assertFalse((Path(tmp) / 'public').exists())

    def test_final_component_symlink_or_nonregular_file_cannot_be_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source.apk'
            source.write_bytes(b'fixture')
            link = Path(tmp) / 'link.apk'
            link.symlink_to(source)
            with self.assertRaises(OSError):
                h.export_apk(link, Path(tmp) / 'out.apk', {'bytes': 7, 'sha256': '0' * 64}, Mock())
            with self.assertRaises(RuntimeError):
                h.apk_metadata(Path(tmp), Mock())
            alias = Path(tmp) / 'hardlink.apk'
            os.link(source, alias)
            with self.assertRaises(RuntimeError):
                h.apk_metadata(alias, Mock())

    def test_unproven_native_receipt_cannot_be_reused_or_exported(self):
        state = Path('/owned/state')
        context = {'id': 'job', 'source': {'commit': 'a' * 40}, 'gradleHome': '/owned/state/gradle-home'}
        with patch.dict(os.environ, JAVA_HOME=str(ROOT), P2PKIT_AUDIT_JDK21=str(ROOT)):
            argv = h.commands(state)['android-apk-producer']
            proof = dict(jobId='job', sourceBefore=context['source'], sourceAfter=context['source'],
                         ancestorInvocationIds=[], errors=[], ownedSurvivors=[], ownership={'discoveryErrors': []},
                         stopExitCode=0, id='receipt', kind='gradle', host='linux-x64', gradleHome=context['gradleHome'])
            runner, checker = Mock(), Mock()
            runner.read_json.return_value = proof
            self.assertEqual(h.receipt(runner, checker, state, context, 'android-apk-producer', argv, 0), proof)
            for change in (dict(jobId='foreign'), dict(errors=['unproven']), dict(ownedSurvivors=[1]),
                           dict(ownership={'discoveryErrors': ['unreadable']}), dict(stopExitCode=1),
                           dict(sourceAfter={'commit': 'f' * 40}), dict(ancestorInvocationIds=['foreign']),
                           dict(kind='command'), dict(host='macos-x64'), dict(gradleHome='/foreign')):
                runner.read_json.return_value = {**proof, **change}
                with self.assertRaises(RuntimeError):
                    h.receipt(runner, checker, state, context, 'android-apk-producer', argv, 0)
            with self.assertRaises(RuntimeError):
                h.receipt(runner, checker, state, context, 'android-apk-producer', ['true'], 0)

    def public(self):
        return dict(schema=1, scope=h.SCOPE, source={'commit': 'a' * 40, 'tree': 'b' * 40}, result='PASS',
            sourceUnchanged=True, foundationStatus='NOT_READY', physicalQualification=False,
            mobileCapacityQualification=False, maintainedArtQualification=False, nativeControlTests=124,
            commands=[dict(purpose=p, exitCode=0, finalizationVerified=True) for p in h.PURPOSES],
            controls=self.assess(self.value()),
            artifacts={name: dict(bytes=16, sha256='e' * 64) for name in h.APKS}, productDiagnostics={})

    def test_public_manifest_has_closed_types_counts_sources_and_scope(self):
        good = self.public()
        self.assertEqual(h.validate_public(good, good['source'], 124), good)
        for change in (dict(nativeControlTests=True), dict(nativeControlTests='PRIVATE'), dict(nativeControlTests=123),
                       dict(physicalQualification=True), dict(maintainedArtQualification=True),
                       dict(mobileCapacityQualification=True), dict(foundationStatus='READY'), dict(schema=True),
                       dict(sourceUnchanged=False), dict(private='SECRET'), dict(source={'commit': 'a' * 40}),
                       dict(commands=good['commands'][:-1]), dict(artifacts={}), dict(controls=None)):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                h.validate_public({**good, **change}, good['source'], 124)

    def test_public_manifest_rejects_private_or_inconsistent_commands_and_control_fields(self):
        for change in (dict(exitCode=True), dict(exitCode='PRIVATE'), dict(exitCode=125), dict(exitCode=None),
                       dict(exitCode=-999), dict(finalizationVerified=False), dict(purpose='PRIVATE'), dict(stderr='PRIVATE')):
            value = self.public()
            value['commands'][0].update(change)
            with self.assertRaises(RuntimeError):
                h.validate_public(value, value['source'], 124)
        for change in (dict(api=True), dict(controlsPassed=True), dict(bootSeconds=float('nan')),
                       dict(bootSeconds=float('inf')), dict(bootSeconds=600), dict(token='PRIVATE'),
                       dict(imageRevision='PRIVATE'), dict(naturalCleanup=False)):
            value = self.public()
            value['controls'].update(change)
            with self.assertRaises(RuntimeError):
                h.validate_public(value, value['source'], 124)

    def test_failure_manifest_never_promotes_controls_or_exports_artifacts(self):
        value = {**self.public(), 'result': 'FAIL', 'nativeControlTests': 0, 'controls': None,
                 'artifacts': {}, 'commands': [dict(purpose='native-controls', exitCode=125, finalizationVerified=False)]}
        h.validate_public(value, value['source'], 124)
        for change in (dict(controls=self.public()['controls']), dict(artifacts=self.public()['artifacts'])):
            with self.assertRaises(RuntimeError):
                h.validate_public({**value, **change}, value['source'], 124)

    @contextmanager
    def collector_fixture(self):
        """Real private files/copies with fake APK bytes/receipts; never runtime evidence."""
        with tempfile.TemporaryDirectory() as tmp:
            temporary = Path(tmp).resolve()
            parent, root = temporary / 'job', temporary / 'source'
            parent.mkdir(mode=0o700)
            (root / 'scripts').mkdir(parents=True)
            (root / 'gradle').mkdir()
            (root / 'gradle/platform-test-policy.json').write_bytes((ROOT / 'gradle/platform-test-policy.json').read_bytes())
            (root / 'scripts/run-rpc-android-controls.py').write_bytes(b'offline-script-fixture')
            state = parent / 'state'
            for part in ('private', 'work/api24-controls', 'evidence/native-controls'):
                (state / part).mkdir(parents=True, mode=0o700)
            context = dict(id='job', source={**self.public()['source'], 'status': '', 'diffSha256': 'c' * 64})
            fake = SimpleNamespace(absolute_path=lambda _: parent, context_at=lambda _: (state, context),
                read_json=lambda p: json.loads(p.read_text()), source_snapshot=Mock(return_value=context['source']),
                reject_symlinks=Mock(), file_digest=h.evidence.file_hash)
            def write(path, value):
                with path.open('x') as stream:
                    json.dump(value, stream)
            fake.write_new_json = write
            files = {}
            for index, (name, relative) in enumerate(h.APKS.items()):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'NOT-AN-APK-' + bytes([index]))
                path.chmod(0o600)
                files[name] = h.apk_metadata(path, fake)
            controls = self.value()
            controls.update(source=context['source'], scriptSha256=h.evidence.file_hash(root / 'scripts/run-rpc-android-controls.py'),
                producerReceiptSha256=h.hashlib.sha256(b'{}').hexdigest(),
                appSha256=list(files.values())[0]['sha256'], testApkSha256=list(files.values())[1]['sha256'])
            write(state / 'work/api24-controls/result.json', controls)
            (state / 'evidence/native-controls/product.stderr.log').write_bytes(b'offline-control-count-fixture')
            for purpose in h.PURPOSES:
                (state / 'private' / (purpose + '.json')).write_bytes(b'{}')
            original = dict(schema=1, scope=h.SCOPE, source=context['source'], sourceUnchanged=True,
                result='PASS', nativeControlTests=124, artifacts=files, controls=self.assess(self.value()),
                productDiagnostics={}, commands=[dict(purpose=p, argv=[p], exitCode=0, verified=True,
                    receiptSha256=h.hashlib.sha256(b'{}').hexdigest()) for p in h.PURPOSES])
            write(state / 'private/result.json', original)
            q = SimpleNamespace(control_inventory=lambda _: 124, unittest_count=lambda _: 124)
            modules = {'run-audit-command.py': fake, 'check-audit-receipt.py': Mock(), 'run-rpc-qualification.py': q,
                       'run-rpc-android-controls.py': phone, 'run-rpc-capacity-lab.py': SimpleNamespace(private_directory=Mock())}
            with patch.object(h, 'ROOT', root), patch.object(h, 'admit'), patch.object(h, 'module', side_effect=lambda _, f: modules[f]), \
                    patch.dict(os.environ, RPC_ANDROID_HANDOFF_PARENT=str(parent), RUNNER_TEMP=str(temporary)), \
                    patch.object(h, 'receipt', side_effect=lambda _r, _c, _s, _ctx, purpose, _a, _code: {'id': purpose}) as receipts:
                yield SimpleNamespace(parent=parent, state=state, root=root, runner=fake, original=original,
                                      context=context, receipts=receipts)

    def test_collector_rechecks_each_receipt_and_exports_exact_tested_bytes_atomically(self):
        with self.collector_fixture() as f:
            self.assertEqual(h.collect(), 0)
            self.assertEqual(f.receipts.call_count, len(h.PURPOSES))
            self.assertEqual(set(p.name for p in (f.parent / 'public').iterdir()), {*h.APKS, 'manifest.json'})
            value = json.loads((f.parent / 'public/manifest.json').read_text())
            self.assertEqual(value['result'], 'PASS')
            self.assertEqual(value['artifacts'], f.original['artifacts'])
            for name, relative in h.APKS.items():
                self.assertEqual((f.parent / 'public' / name).read_bytes(), (f.root / relative).read_bytes())
            self.assertNotIn('rpcToken', json.dumps(value))
            self.assertFalse((f.parent / 'export-staging').exists())

    def test_collector_unverified_native_receipt_yields_only_failed_manifest_not_apks(self):
        with self.collector_fixture() as f:
            f.receipts.side_effect = RuntimeError('unproven')
            self.assertEqual(h.collect(), 1)
            self.assertEqual([p.name for p in (f.parent / 'public').iterdir()], ['manifest.json'])
            value = json.loads((f.parent / 'public/manifest.json').read_text())
            self.assertEqual(value['nativeControlTests'], 0)
            self.assertEqual(value['result'], 'FAIL')
            self.assertTrue(all(not r['finalizationVerified'] for r in value['commands']))

    def test_collector_second_copy_failure_never_exposes_first_binary(self):
        with self.collector_fixture() as f:
            export = h.export_apk
            def copy(source, target, expected, runner):
                if target.name == list(h.APKS)[1]:
                    raise OSError('copy failure')
                return export(source, target, expected, runner)
            with patch.object(h, 'export_apk', side_effect=copy), self.assertRaises(OSError):
                h.collect()
            self.assertTrue((f.parent / 'export-staging' / next(iter(h.APKS))).is_file())
            self.assertFalse((f.parent / 'public').exists())

    def test_collector_source_drift_during_staging_keeps_all_binaries_private(self):
        with self.collector_fixture() as f:
            f.runner.source_snapshot.side_effect = [f.context['source'], {**f.context['source'], 'status': 'modified'}]
            with self.assertRaisesRegex(RuntimeError, 'Source changed'):
                h.collect()
            self.assertFalse((f.parent / 'public').exists())

    def test_collector_rejects_modified_apk_or_private_command_fields_before_exposure(self):
        for failure in ('apk', 'command', 'count'):
            with self.subTest(failure=failure), self.collector_fixture() as f:
                if failure == 'apk':
                    (f.root / next(iter(h.APKS.values()))).write_bytes(b'changed')
                else:
                    if failure == 'command':
                        f.original['commands'][0]['exitCode'] = 'PRIVATE'
                    else:
                        f.original['nativeControlTests'] = 'PRIVATE'
                    (f.state / 'private/result.json').write_text(json.dumps(f.original))
                with self.assertRaises(RuntimeError):
                    h.collect()
                self.assertFalse((f.parent / 'public').exists())

    def test_unverified_execution_refuses_subsequent_work_and_preserves_failed_record(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, JAVA_HOME=str(ROOT), P2PKIT_AUDIT_JDK21=str(ROOT)):
            instance = object.__new__(h.Job)
            instance.state = Path(tmp).resolve()
            instance.private = instance.state / 'private'
            instance.private.mkdir()
            instance.result = {'commands': []}
            instance.unsafe = False
            instance.runner, instance.checker, instance.context = Mock(), Mock(), {}
            instance.runner.main.return_value = 125
            with patch.object(h, 'receipt', side_effect=RuntimeError('unproven')):
                with self.assertRaises(RuntimeError):
                    instance.invoke('native-controls', h.commands(instance.state)['native-controls'], h.BOUNDS['native-controls'])
            self.assertTrue(instance.unsafe)
            with self.assertRaises(RuntimeError):
                instance.invoke('jdk17', h.commands(instance.state)['jdk17'], 45)
            self.assertEqual(instance.runner.main.call_count, 1)
            self.assertEqual(instance.result['commands'][0]['exitCode'], 125)
            self.assertFalse(instance.result['commands'][0]['verified'])

    def test_workflow_delivers_binaries_only_after_successful_independent_collection(self):
        text = (ROOT / '.github/workflows/rpc-android-handoff.yml').read_text()
        self.assertIn("contains(github.event.head_commit.message, '[rpc-android-handoff]')", text)
        self.assertIn('persist-credentials: false', text)
        self.assertIn('cancel-in-progress: false', text)
        self.assertIn('contents: read', text)
        self.assertIn('if: ${{ steps.collect.outcome == \'success\' }}', text)
        self.assertNotIn('secrets.', text)
        self.assertNotIn('continue-on-error', text)
        self.assertNotIn('upload-artifact@v', text)
        binary_step = text.split('- name: Deliver only', 1)[1]
        for name in h.APKS:
            self.assertIn('/public/' + name, binary_step)
        for forbidden in ('*.apk', '/state/', 'keystore', '**', 'release'):
            self.assertNotIn(forbidden, binary_step)


if __name__ == '__main__':
    unittest.main(verbosity=2)
