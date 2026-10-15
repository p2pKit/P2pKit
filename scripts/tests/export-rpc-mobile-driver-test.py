#!/usr/bin/env python3
"""Offline export controls. Fixture JAR/APK bytes and mocked receipts are NOT execution evidence."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('mobile_driver_export_test', ROOT / 'scripts/export-rpc-mobile-driver.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


SOURCE = dict(commit='2' * 40, tree='3' * 40)


def fixture(directory):
    directory.mkdir(mode=0o700)
    files = {'a-fixture.jar': b'OFFLINE-FIXTURE-NOT-JAVA', 'b-fixture.jar': b'OTHER-NOT-JAVA'}
    for name, raw in files.items():
        (directory / name).write_bytes(raw)
        (directory / name).chmod(0o600)
    manifest = dict(schema=1, scope='SYNTHETIC_LAB_NOT_PUBLICATION_OR_QUALIFICATION',
                    sourceSha=SOURCE['commit'], entries=[dict(name=k, sha256=digest(v)) for k, v in files.items()])
    (directory / 'manifest.json').write_text(json.dumps(manifest))
    (directory / 'manifest.json').chmod(0o600)
    return manifest, files


class Files(unittest.TestCase):
    def test_exact_producer_schema_and_bounded_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'distribution'
            manifest, files = fixture(directory)
            self.assertEqual(m.inventory(directory, SOURCE['commit']),
                             {'manifest.json': json.dumps(manifest).encode(), **files})
            with self.assertRaises(ValueError):
                m.inventory(directory, '4' * 40)
            with self.assertRaises(ValueError):
                m.regular_bytes(directory / 'a-fixture.jar', 1)

    def test_missing_duplicate_unsorted_unsafe_and_unexpected_entries_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'distribution'
            manifest, _ = fixture(directory)
            first = manifest['entries'][0]
            for entries in ([], [first, first], list(reversed(manifest['entries'])),
                            [first | dict(name='../a-fixture.jar')], [first | dict(name='/a-fixture.jar')],
                            [first | dict(name='a-fixture.zip')], [first | dict(sha256='0' * 64)],
                            [first | dict(extra='private')], [first | dict(sha256=True)]):
                with self.subTest(entries=entries):
                    (directory / 'manifest.json').write_text(json.dumps(manifest | dict(entries=entries)))
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        m.inventory(directory, SOURCE['commit'])
            for update in (dict(schema=True), dict(schema=2), dict(scope='RELEASE'), dict(extra='private')):
                (directory / 'manifest.json').write_text(json.dumps(manifest | update))
                with self.assertRaises(ValueError):
                    m.inventory(directory, SOURCE['commit'])
            (directory / 'manifest.json').write_text(json.dumps(manifest))
            (directory / 'UNEXPECTED').touch()
            with self.assertRaises(ValueError):
                m.inventory(directory, SOURCE['commit'])

    def test_duplicate_json_keys_and_wrong_manifest_type_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'distribution'
            fixture(directory)
            for raw in ('{"schema":1,"schema":1}', '[]', 'true', '{}'):
                (directory / 'manifest.json').write_text(raw)
                with self.assertRaises(ValueError):
                    m.inventory(directory, SOURCE['commit'])

    def test_links_foreign_write_access_empty_files_and_fifos_cannot_be_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'distribution'
            _, files = fixture(directory)
            file = directory / 'a-fixture.jar'
            for mode in (0o622, 0o660, 0o666):
                file.chmod(mode)
                with self.assertRaises(ValueError):
                    m.inventory(directory, SOURCE['commit'])
            file.chmod(0o600)
            alias = Path(tmp) / 'hardlink'
            os.link(file, alias)
            with self.assertRaises(ValueError):
                m.inventory(directory, SOURCE['commit'])
            alias.unlink()
            file.unlink()
            file.symlink_to(directory / 'b-fixture.jar')
            with self.assertRaises(ValueError):
                m.inventory(directory, SOURCE['commit'])
            file.unlink()
            os.mkfifo(file, 0o600)
            with self.assertRaises(ValueError):
                m.inventory(directory, SOURCE['commit'])
            file.unlink()
            file.touch(mode=0o600)
            with self.assertRaises(ValueError):
                m.inventory(directory, SOURCE['commit'])
            file.write_bytes(files[file.name])
            link = Path(tmp) / 'symlink-parent'
            link.symlink_to(directory, target_is_directory=True)
            with self.assertRaises(ValueError):
                m.regular_bytes(link / file.name, m.LIMIT)

    def test_same_size_file_replacement_during_read_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'distribution'
            fixture(directory)
            file = directory / 'a-fixture.jar'
            original = os.fstat
            calls = []
            def changed(fd):
                result = original(fd)
                calls.append(fd)
                if len(calls) == 2:
                    replacement = directory / 'replacement'
                    replacement.write_bytes(file.read_bytes())
                    replacement.chmod(0o600)
                    replacement.replace(file)
                return result
            with patch.object(m.os, 'fstat', side_effect=changed), self.assertRaises(ValueError):
                m.regular_bytes(file, m.LIMIT)


class Export(unittest.TestCase):
    def test_complete_bytes_are_rechecked_atomically_and_never_claim_mobile_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            directory = parent / 'distribution'
            fixture(directory)
            app = b'OFFLINE-APP-MANIFEST-NOT-PROVENANCE'
            check = Mock(return_value=True)
            result = m.export(directory, parent, SOURCE, app, '4' * 64, check)
            self.assertEqual(check.call_count, 2)
            self.assertFalse((parent / 'runtime-export-staging').exists())
            public = parent / 'runtime-public'
            self.assertEqual(json.loads((public / 'manifest.json').read_bytes()), result)
            self.assertEqual(result['scope'], m.SCOPE)
            self.assertFalse(result['mobileCapacityQualified'])
            self.assertFalse(result['physicalLanQualified'])
            self.assertEqual(result['foundationStatus'], 'NOT_READY')
            self.assertEqual(result['originalAndroidHandoffSha256'], digest(app))
            archive = public / result['artifact']['file']
            self.assertEqual(result['artifact']['sha256'], digest(archive.read_bytes()))
            self.assertEqual(result['artifact']['bytes'], archive.stat().st_size)
            with zipfile.ZipFile(archive) as zipped:
                self.assertEqual({name: zipped.read(name) for name in zipped.namelist()},
                                 m.inventory(directory, SOURCE['commit']))
                self.assertIsNone(zipped.testzip())
            for file in public.iterdir():
                self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                m.export(directory, parent, SOURCE, app, '4' * 64, check)

    def test_source_drift_or_copy_failure_cannot_publish_a_partial_driver(self):
        for failure in ('initial-source', 'final-source', 'write'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                parent = Path(tmp)
                directory = parent / 'distribution'
                fixture(directory)
                check = Mock(side_effect=[False] if failure == 'initial-source' else [True, False])
                with patch.object(m.zipfile.ZipFile, 'writestr', side_effect=OSError('OFFLINE')) if failure == 'write' \
                        else patch.object(m, 'LIMIT', m.LIMIT):
                    with self.assertRaises((ValueError, OSError)):
                        m.export(directory, parent, SOURCE, b'FIXTURE', '4' * 64, check)
                self.assertFalse((parent / 'runtime-public').exists())

    def test_changed_distribution_between_inventory_and_export_cannot_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            directory = parent / 'distribution'
            fixture(directory)
            inventory = m.inventory(directory, SOURCE['commit'])
            with patch.object(m, 'inventory', side_effect=[inventory, inventory | {'injected.jar': b'bad'}]), \
                    self.assertRaises(ValueError):
                m.export(directory, parent, SOURCE, b'FIXTURE', '4' * 64, lambda: True)
            self.assertFalse((parent / 'runtime-public').exists())


class CompleteHandoff(unittest.TestCase):
    """Fake receipt readers test refusal/control flow; real validation is delegated unchanged to the existing gate."""
    def fixture(self, parent):
        handoff = m.load('mobile_export_existing_handoff_fixture', 'run-rpc-android-handoff.py')
        purposes, names = handoff.PURPOSES, handoff.APKS
        context = dict(source=SOURCE | dict(status=''), id='offline')
        state = parent / 'state'
        controls = {'OFFLINE_ONLY': True}
        metadata = {k: dict(bytes=12, sha256='5' * 64) for k in names}
        original = dict(source=context['source'], result='PASS', sourceUnchanged=True, nativeControlTests=127,
            commands=[dict(purpose=p, argv=['OFFLINE-NOT-EXECUTED', p], exitCode=0, verified=True,
                           receiptSha256='4' * 64) for p in purposes], controls=controls, artifacts=metadata)
        public = dict(result='PASS', controls=controls, artifacts=metadata)
        h = Mock(PURPOSES=purposes, APKS=names, assess_controls=Mock(return_value=controls),
                 receipt=Mock(return_value={'id': 'OFFLINE'}), apk_metadata=Mock(return_value=next(iter(metadata.values()))))
        runner = Mock(absolute_path=Mock(return_value=parent), context_at=Mock(return_value=(state, context)),
            source_snapshot=Mock(return_value=context['source']), file_digest=Mock(return_value='4' * 64))
        runner.read_json.side_effect = lambda path: original if path.name == 'result.json' and path.parent.name == 'private' else {}
        policy = Mock(control_inventory=Mock(return_value=127), unittest_count=Mock(return_value=127))
        modules = dict(zip(('mobile_driver_handoff', 'mobile_driver_native', 'mobile_driver_receipts',
            'mobile_driver_inventory', 'mobile_driver_app_controls', 'mobile_driver_files'),
            (h, runner, Mock(), policy, Mock(), Mock())))
        return SimpleNamespace(h=h, runner=runner, policy=policy, modules=modules, original=original, public=public)

    def run_fixture(self, parent, fixture):
        env = dict(RPC_ANDROID_HANDOFF_PARENT=str(parent), RUNNER_TEMP=str(parent.parent))
        with patch.dict(os.environ, env), patch.object(m, 'load', side_effect=lambda name, _: fixture.modules[name]), \
                patch.object(m, 'regular_bytes', return_value=json.dumps(fixture.public).encode()), \
                patch.object(m.evidence, 'bounded', return_value=b'OFFLINE-NOT-NATIVE-RESULT'), \
                patch.object(m, 'export') as export:
            try:
                result = m.main()
                self.assertEqual(result, 0)
                return export.call_args
            except Exception:
                export.assert_not_called()
                raise

    def test_all_original_receipts_apks_and_controls_are_reverified_before_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            f = self.fixture(parent)
            args = self.run_fixture(parent, f)
            self.assertEqual(f.h.receipt.call_count, 6)
            self.assertEqual(f.h.apk_metadata.call_count, 4)
            self.assertEqual(f.h.assess_controls.call_count, 1)
            f.h.admit.assert_called_once()
            f.h.validate_public.assert_called_once()
            f.modules['mobile_driver_files'].classpath.assert_called_once_with(SOURCE['commit'])
            self.assertEqual(args.args[2], SOURCE)

    def test_failed_missing_changed_or_unfinalized_evidence_never_reaches_export(self):
        changes = ('public-fail', 'original-fail', 'drift', 'native-count', 'native-log', 'partial', 'order',
                   'exit', 'verified', 'receipt-hash', 'receipt-invalid', 'original-apk', 'exported-apk', 'controls')
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                parent = Path(tmp)
                f = self.fixture(parent)
                if change == 'public-fail':
                    f.public['result'] = 'FAIL'
                elif change == 'original-fail':
                    f.original['result'] = 'FAIL'
                elif change == 'drift':
                    f.runner.source_snapshot.return_value = {}
                elif change == 'native-count':
                    f.original['nativeControlTests'] = 126
                elif change == 'native-log':
                    f.policy.unittest_count.return_value = 126
                elif change == 'partial':
                    f.original['commands'].pop()
                elif change == 'order':
                    f.original['commands'].reverse()
                elif change in ('exit', 'verified', 'receipt-hash'):
                    field, value = {'exit': ('exitCode', 1), 'verified': ('verified', False),
                                    'receipt-hash': ('receiptSha256', '0' * 64)}[change]
                    f.original['commands'][2][field] = value
                elif change == 'receipt-invalid':
                    f.h.receipt.side_effect = ValueError('OFFLINE-INVALID-NATIVE-RECEIPT')
                elif change == 'original-apk':
                    f.original['artifacts'] = {}
                elif change == 'exported-apk':
                    same = next(iter(f.original['artifacts'].values()))
                    f.h.apk_metadata.side_effect = [same, same, same | dict(sha256='0' * 64)]
                elif change == 'controls':
                    f.h.assess_controls.return_value = {}
                with self.assertRaises(ValueError):
                    self.run_fixture(parent, f)


if __name__ == '__main__':
    unittest.main(verbosity=2)
