#!/usr/bin/env python3
"""Offline packaging-input controls; no jpackage, SDK, network or signing execution."""
import hashlib
import json
from pathlib import Path
import runpy
import tempfile
import unittest
import zipfile

API = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'package-rpc-preview.py'))
SHA = 'a' * 40


class PackagingInputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'app.jar').write_bytes(b'fixture jar')
        self.row = dict(name='app.jar', sha256=hashlib.sha256(b'fixture jar').hexdigest())
        self.write([self.row])

    def write(self, rows, source=SHA):
        (self.root / 'manifest.json').write_text(json.dumps(dict(sourceSha=source, entries=rows)))

    def test_complete_fixture_is_admitted(self):
        self.assertEqual(API['checked_entries'](self.root, SHA), ['app.jar'])

    def test_wrong_source_rejected(self):
        self.write([self.row], 'b' * 40)
        with self.assertRaises(ValueError): API['checked_entries'](self.root, SHA)

    def test_modified_jar_rejected(self):
        (self.root / 'app.jar').write_bytes(b'modified')
        with self.assertRaises(ValueError): API['checked_entries'](self.root, SHA)

    def test_duplicate_rejected(self):
        self.write([self.row, self.row])
        with self.assertRaises(ValueError): API['checked_entries'](self.root, SHA)

    def test_path_escape_rejected(self):
        self.write([dict(self.row, name='../app.jar')])
        with self.assertRaises(ValueError): API['checked_entries'](self.root, SHA)

    def test_url_and_manifest_injection_rejected(self):
        for name in ('https:app.jar', 'app\n.jar', 'app name.jar', 'native/app.jar', r'..\app.jar'):
            self.write([dict(self.row, name=name)])
            with self.assertRaises(ValueError): API['checked_entries'](self.root, SHA)

    def test_missing_jar_rejected(self):
        (self.root / 'app.jar').unlink()
        with self.assertRaises(ValueError): API['checked_entries'](self.root, SHA)

    def test_bounded_classpath(self):
        for rows in ([], [self.row] * 129):
            self.write(rows)
            with self.assertRaises(ValueError): API['checked_entries'](self.root, SHA)

    def native_copy(self):
        name = API['NATIVE_MANIFEST_JAR']
        native = self.root / 'native'
        native.mkdir()
        path = native / name
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('META-INF/p2pkit/macos-tcp.properties', b'SYNTHETIC NATIVE METADATA; NOT LOADED')
        copied = self.root / name
        copied.write_bytes(path.read_bytes())
        row = dict(name=name, sha256=API['digest'](path))
        self.write([self.row, row])
        return path, copied, row

    def test_mac_root_duplicate_is_verified_and_omitted_only_with_original_native_authority(self):
        native, copied, row = self.native_copy()
        self.assertEqual(API['checked_entries'](self.root, SHA, native), ['app.jar'])
        # Non-Mac callers and the original manifest schema retain their unchanged classpath behavior.
        self.assertEqual(API['checked_entries'](self.root, SHA), ['app.jar', copied.name])
        self.write([self.row])
        self.assertEqual(API['checked_entries'](self.root, SHA, native), ['app.jar'])

    def test_native_metadata_mutation_cannot_be_hidden_by_omitting_the_root_copy(self):
        native, copied, row = self.native_copy()
        copied.write_bytes(b'MODIFIED ROOT COPY')
        with self.assertRaises(ValueError): API['checked_entries'](self.root, SHA, native)
        self.write([self.row, dict(row, sha256=API['digest'](copied))])
        with self.assertRaises(ValueError): API['checked_entries'](self.root, SHA, native)

    def test_linked_authority_and_duplicate_metadata_rows_remain_failures(self):
        native, copied, row = self.native_copy()
        self.write([self.row, row, row])
        with self.assertRaises(ValueError): API['checked_entries'](self.root, SHA, native)
        self.write([self.row, row])
        native.unlink()
        native.symlink_to(copied)
        with self.assertRaises(ValueError): API['checked_entries'](self.root, SHA, native)

    def test_mac_metadata_preserves_identity_and_declares_only_used_privacy_services(self):
        original = dict(CFBundleIdentifier='dev.p2pkit.sample.rpc.desktop',
                        LSMinimumSystemVersion='10.11', NSMicrophoneUsageDescription='Generic unused template')
        changed = API['mac_bundle_info'](original, '26.6')
        self.assertEqual(changed['CFBundleIdentifier'], original['CFBundleIdentifier'])
        self.assertEqual(changed['LSMinimumSystemVersion'], '26.6')
        self.assertEqual(changed['NSBonjourServices'], ['_p2pkit2._tcp'])
        self.assertTrue(changed['NSLocalNetworkUsageDescription'])
        self.assertNotIn('NSMicrophoneUsageDescription', changed)
        self.assertIn('NSMicrophoneUsageDescription', original)
        self.assertEqual(API['mac_bundle_info'](changed, '26.0')['LSMinimumSystemVersion'], '26.6')
        with self.assertRaises(ValueError): API['mac_bundle_info'](original, 'invalid')

    def test_manifest_folding_preserves_classpath(self):
        names = ['artifact-' + str(i) + '.jar' for i in range(100)]
        raw = API['manifest_bytes'](names)
        self.assertTrue(all(len(line) <= 70 for line in raw.split(b'\r\n')))
        unfolded = raw.replace(b'\r\n ', b'').decode('ascii')
        self.assertIn('Class-Path: ' + ' '.join(names) + '\r\n', unfolded)
        self.assertIn('Main-Class: dev.p2pkit.sample.rpc.desktop.RpcDesktopMainKt\r\n', unfolded)


if __name__ == '__main__': unittest.main()
