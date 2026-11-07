#!/usr/bin/env python3
"""Warm/revision-change staging and refusal controls using only fixture-owned files."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('capacity_copy_test', ROOT / 'scripts/prepare-rpc-capacity-copy.py')
copy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copy)


class CopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rpc-copy-test-', dir=Path.home())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.directory = self.root / 'samples/p2p-sample-rpc/build/capacity-lab'
        self.directory.mkdir(parents=True)
        self.target = self.directory / copy.files.MAC_MANIFEST_JAR
        self.source = 'a' * 40
        self.relative = 'library/p2p-transport-lan/build/macos-tcp/' + self.source
        self.original = self.root / self.relative / self.target.name
        self.original.parent.mkdir(parents=True)
        self.original.write_bytes(b'original native metadata')
        self.original.chmod(0o400)
        self.target.write_bytes(self.original.read_bytes())
        self.target.chmod(0o400)
        binding = dict(name=self.target.name, sha256=hashlib.sha256(self.target.read_bytes()).hexdigest())
        self.manifest = dict(schema=1, sourceSha=self.source,
                             scope='SYNTHETIC_LAB_NOT_PUBLICATION_OR_QUALIFICATION', entries=[binding],
                             macosNative=dict(directory=self.relative, entries=[binding]))
        self.save()

    def save(self):
        path = self.directory / 'manifest.json'
        path.write_text(json.dumps(self.manifest))
        path.chmod(0o600)

    def test_revision_change_replaces_copy_without_changing_original(self):
        original = self.original.stat()
        copy.prepare(self.root)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.original.stat(), original)
        self.assertEqual(self.original.read_bytes(), b'original native metadata')
        # Simulate the next Sync's owner-writable copy and its next warm preparation.
        self.target.write_bytes(b'next source metadata')
        self.target.chmod(0o600)
        next_copy = self.target.stat()
        copy.prepare(self.root)
        self.assertEqual(self.target.stat(), next_copy)

    def test_missing_copy_does_not_create_or_remove_anything(self):
        self.target.unlink()
        copy.prepare(self.root)
        self.assertTrue(self.original.exists())

    def test_unknown_or_changed_provenance_refuses_retirement(self):
        for change in (lambda: self.manifest.update(sourceSha='not-a-source'),
                       lambda: self.manifest['macosNative'].update(directory='../outside'),
                       lambda: self.manifest.update(entries=[]),
                       lambda: self.manifest['macosNative'].update(entries=[])):
            old = json.dumps(self.manifest)
            change()
            self.save()
            with self.assertRaises(RuntimeError):
                copy.prepare(self.root)
            self.assertTrue(self.target.exists())
            self.manifest = json.loads(old)

    def test_changed_original_refuses_retirement(self):
        self.original.chmod(0o600)
        self.original.write_bytes(b'changed')
        with self.assertRaises(RuntimeError):
            copy.prepare(self.root)
        self.assertTrue(self.target.exists())

    def test_link_alias_fifo_or_foreign_owner_refuses_retirement(self):
        alias = self.root / 'alias'
        os.link(self.target, alias)
        with self.assertRaises(RuntimeError):
            copy.prepare(self.root)
        alias.unlink()
        self.target.unlink()
        self.target.symlink_to(self.original)
        with self.assertRaises(RuntimeError):
            copy.prepare(self.root)
        self.target.unlink()
        os.mkfifo(self.target)
        with self.assertRaises(RuntimeError):
            copy.prepare(self.root)
        self.target.unlink()
        self.target.write_bytes(self.original.read_bytes())
        self.target.chmod(0o400)
        with patch.object(copy.os, 'getuid', return_value=os.getuid() + 1), self.assertRaises(RuntimeError):
            copy.prepare(self.root)
        self.assertTrue(self.target.exists())

    def test_unprotected_ancestry_refuses_retirement(self):
        self.directory.chmod(0o777)
        with self.assertRaises(RuntimeError):
            copy.prepare(self.root)
        self.assertTrue(self.target.exists())

    def test_copy_changed_after_read_refuses_retirement(self):
        read = copy.files.read_distribution_file

        def replace_original_read(path, *args, **kwargs):
            result = read(path, *args, **kwargs)
            if path == self.original:
                self.target.unlink()
                self.target.write_bytes(result)
                self.target.chmod(0o400)
            return result

        with patch.object(copy.files, 'read_distribution_file', side_effect=replace_original_read), \
                self.assertRaises(RuntimeError):
            copy.prepare(self.root)
        self.assertTrue(self.target.exists())

    def test_sync_uses_owner_writable_copies_and_guard_before_copy(self):
        source = (ROOT / 'samples/p2p-sample-rpc/build.gradle.kts').read_text()
        block = source.split('tasks.register<Sync>("prepareRpcCapacityLab")', 1)[1].split('// Separate from capacity', 1)[0]
        self.assertIn('filePermissions { unix("0600") }', block)
        self.assertIn('doFirst {', block)
        self.assertIn('"scripts/prepare-rpc-capacity-copy.py", "--root", rootDir', block)


if __name__ == '__main__':
    unittest.main()
