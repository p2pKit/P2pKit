#!/usr/bin/env python3
"""Offline launcher admission regressions; no native load, signing, network or Java launch."""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

PRODUCER = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'prepare-macos-rpc-desktop.py'))


class LauncherAdmissionTests(unittest.TestCase):
    def rejected(self, transform, *, pin_after=False):
        with tempfile.TemporaryDirectory(prefix='p2pkit-launcher-test-') as temp:
            root = Path(temp)
            marker = root / 'executed'
            java = root / 'java'
            java.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
            java.chmod(0o700)
            manifest = dict(schema=1, sourceSha='1' * 40,
                scope='LOCAL_MANUAL_TCP_NOT_MULTICAST_OR_RELEASE_QUALIFICATION', java=str(java),
                entries=[dict(name='safe.jar', sha256='0' * 64)], native={})
            raw = json.dumps(manifest).encode()
            expected = hashlib.sha256(raw).hexdigest()
            transform(root, manifest)
            raw = json.dumps(manifest).encode()
            if pin_after:
                expected = hashlib.sha256(raw).hexdigest()
            (root / 'manifest.json').write_bytes(raw)
            (root / 'run.py').write_text(PRODUCER['launcher_source'](expected, '1' * 40, str(java),
                hashlib.sha256(java.read_bytes()).hexdigest()))
            result = subprocess.run([sys.executable, '-I', '-S', '-B', str(root / 'run.py')],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists(), 'Untrusted manifest must not launch Java')
            self.assertIn(b'AssertionError', result.stderr)

    def test_jointly_changed_manifest_and_payload_cannot_redefine_hash_authority(self):
        def change(root, manifest):
            (root / 'safe.jar').write_bytes(b'changed bytes')
            manifest['entries'][0]['sha256'] = hashlib.sha256(b'changed bytes').hexdigest()
        self.rejected(change)

    def test_changed_java_path_cannot_redefine_execution_authority(self):
        self.rejected(lambda root, manifest: manifest.update(java='/unapproved/java'))

    def test_even_pinned_manifest_cannot_use_parent_traversal(self):
        self.rejected(lambda root, manifest: manifest['entries'][0].update(name='../outside.jar'), pin_after=True)

    def test_even_pinned_manifest_cannot_substitute_source(self):
        self.rejected(lambda root, manifest: manifest.update(sourceSha='2' * 40), pin_after=True)


if __name__ == '__main__':
    unittest.main()
