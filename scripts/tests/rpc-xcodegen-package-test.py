#!/usr/bin/env python3
"""Offline package-layout controls; fixtures are never executable tools."""
import copy
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('xcodegen_package_tests', ROOT / 'scripts/rpc_xcodegen_package.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Package(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.prefix = self.base / 'installed'
        self.binary = self.prefix / 'bin/xcodegen'
        self.binary.parent.mkdir(parents=True)
        self.binary.write_bytes(b'OFFLINE FIXTURE: NEVER EXECUTED')
        self.binary.chmod(0o755)
        for relative in m.REQUIRED_PRESETS:
            path = self.prefix / 'share/xcodegen/SettingPresets' / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'OFFLINE_SETTING: true\n')
            path.chmod(0o644)
        self.destination = self.base / 'private-tool'

    def preset(self, relative='base.yml'):
        return self.prefix / 'share/xcodegen/SettingPresets' / relative

    def test_inventory_and_stage_bind_binary_and_every_required_resource(self):
        manifest = m.inventory(self.binary)
        self.assertEqual(len(manifest['files']), 1 + len(m.REQUIRED_PRESETS))
        staged = m.stage(manifest, self.destination)
        self.assertEqual(staged['executable'], str(self.destination / 'bin/xcodegen'))
        self.assertFalse(staged['globalInstallation'])
        self.assertEqual(staged['resourceFiles'], len(m.REQUIRED_PRESETS))
        self.assertEqual(m.inventory(self.binary), manifest)
        self.assertEqual(m.inventory(self.destination / 'bin/xcodegen')['files'], manifest['files'])
        for row in manifest['files']:
            path = self.destination / row['path']
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if row['path'] == 'bin/xcodegen' else 0o600)
            self.assertEqual(path.read_bytes(), (self.prefix / row['path']).read_bytes())

    def test_binary_only_copy_is_not_an_installed_package(self):
        lone = self.base / 'binary-only/bin/xcodegen'
        lone.parent.mkdir(parents=True)
        lone.write_bytes(self.binary.read_bytes())
        lone.chmod(0o700)
        with self.assertRaises((RuntimeError, OSError)):
            m.inventory(lone)

    def test_missing_each_required_preset_is_rejected(self):
        for relative in m.REQUIRED_PRESETS:
            with self.subTest(relative=relative):
                path = self.preset(relative)
                raw = path.read_bytes()
                path.unlink()
                with self.assertRaises(RuntimeError):
                    m.inventory(self.binary)
                path.write_bytes(raw)
                path.chmod(0o644)

    def test_tampering_after_preparation_prevents_any_staging(self):
        manifest = m.inventory(self.binary)
        self.preset().write_bytes(b'OFFLINE_CHANGED: true\n')
        with self.assertRaises(RuntimeError):
            m.stage(manifest, self.destination)
        self.assertFalse(self.destination.exists())

    def test_tampering_after_admission_is_rejected_during_copy(self):
        manifest = m.inventory(self.binary)
        def changed(_manifest):
            self.preset().write_bytes(b'OFFLINE_CHANGED_DURING_STAGE: true\n')
            return self.prefix
        with patch.object(m, 'admit', side_effect=changed), self.assertRaises(RuntimeError):
            m.stage(manifest, self.destination)
        self.assertTrue(self.destination.exists())  # Failed evidence is retained, not automatically removed.

    def test_wrong_source_or_noncanonical_manifest_cannot_be_staged(self):
        manifest = m.inventory(self.binary)
        for change in (dict(schema=True), dict(scope='OTHER'), dict(extra=True), dict(files=[])):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                m.stage(manifest | change, self.destination)
        changed = copy.deepcopy(manifest)
        changed['files'][0]['path'] = '../escape'
        with self.assertRaises(RuntimeError):
            m.stage(changed, self.destination)
        self.assertFalse(self.destination.exists())

    def test_existing_destination_is_never_replaced(self):
        manifest = m.inventory(self.binary)
        self.destination.mkdir()
        sentinel = self.destination / 'retained'
        sentinel.write_bytes(b'KEEP')
        with self.assertRaises((RuntimeError, OSError)):
            m.stage(manifest, self.destination)
        self.assertEqual(sentinel.read_bytes(), b'KEEP')

    def test_manifest_file_fields_do_not_accept_coercions_or_unknown_fields(self):
        manifest = m.inventory(self.binary)
        for index, change in enumerate((dict(bytes=float(manifest['files'][0]['bytes'])), dict(extra=True),
                                        dict(sha256='z' * 64), dict(path='../escape'))):
            with self.subTest(change=change):
                changed = copy.deepcopy(manifest)
                changed['files'][0].update(change)
                destination = self.base / ('invalid-manifest-' + str(index))
                with self.assertRaises(RuntimeError):
                    m.stage(changed, destination)
                self.assertFalse(destination.exists())

    def test_symlinked_binary_or_preset_or_destination_is_refused(self):
        alias = self.base / 'binary-alias'
        alias.symlink_to(self.binary)
        with self.assertRaises(RuntimeError):
            m.inventory(alias)
        manifest = m.inventory(self.binary)
        self.destination.symlink_to(self.prefix, target_is_directory=True)
        with self.assertRaises((RuntimeError, OSError)):
            m.stage(manifest, self.destination)
        preset = self.preset()
        preset.unlink()
        preset.symlink_to(self.binary)
        with self.assertRaises(RuntimeError):
            m.inventory(self.binary)

    def test_hardlinked_resource_and_writable_or_executable_data_are_refused(self):
        alias = self.base / 'hardlink'
        os.link(self.preset(), alias)
        with self.assertRaises(RuntimeError):
            m.inventory(self.binary)

        alias.unlink()
        for mode in (0o666, 0o644 | stat.S_ISUID, 0o755):
            with self.subTest(mode=mode):
                self.preset().chmod(mode)
                with self.assertRaises(RuntimeError):
                    m.inventory(self.binary)
        self.preset().chmod(0o644)
        self.binary.chmod(0o644)
        with self.assertRaises(RuntimeError):
            m.inventory(self.binary)

    def test_symlinked_optional_preset_directory_cannot_disappear_from_inventory(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (outside / 'macOS.yml').write_bytes(b'OFFLINE_SETTING: true\n')
        self.preset('SupportedDestinations').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            m.inventory(self.binary)

    def test_unexpected_file_kind_and_oversized_resource_are_rejected(self):
        extra = self.preset('unexpected.py')
        extra.write_bytes(b'NOT EXECUTED')
        with self.assertRaises(RuntimeError):
            m.inventory(self.binary)
        extra.unlink()
        with patch.object(m, 'MAX_PRESET_BYTES', 8), self.assertRaises(RuntimeError):
            m.inventory(self.binary)

    def test_independent_readback_rejects_corrupted_staging(self):
        manifest = m.inventory(self.binary)
        original = m.copy_verified
        def corrupt(source, target, row):
            original(source, target, row)
            if row['path'].endswith('/base.yml'):
                target.write_bytes(b'OFFLINE CORRUPTED WRITE')
        with patch.object(m, 'copy_verified', side_effect=corrupt), self.assertRaises(RuntimeError):
            m.stage(manifest, self.destination)
        self.assertTrue(self.destination.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
