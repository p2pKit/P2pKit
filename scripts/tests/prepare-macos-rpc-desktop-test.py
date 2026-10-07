#!/usr/bin/env python3
"""Offline launcher admission regressions; codesign/exec are mocked, never native load or Java launch."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest import mock

PRODUCER = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'prepare-macos-rpc-desktop.py'))
SCOPE = 'LOCAL_APPLICATION_BUILD_NOT_NETWORK_OR_RELEASE_QUALIFICATION'


class LauncherAdmissionTests(unittest.TestCase):
    def exercise(self, transform=lambda root, manifest: None, *, pin_after=False, admitted=False):
        with tempfile.TemporaryDirectory(prefix='p2pkit-launcher-test-') as temp:
            root = Path(temp).resolve(strict=True)
            java = root / 'java'
            java.write_bytes(b'synthetic non-executable JDK identity')
            java_digest = PRODUCER['sha'](java)
            (root / 'safe.jar').write_bytes(b'synthetic classpath')
            native = root / 'native'
            native.mkdir()
            (native / 'p2pkit-macos-tcp-manifest.jar').write_bytes(b'synthetic native metadata')
            (native / 'libp2pkit_lan_socket.dylib').write_bytes(b'synthetic native bytes; NEVER loaded')
            manifest = dict(schema=1, sourceSha='1' * 40, scope=SCOPE, java=str(java),
                entries=[dict(name=name, sha256=PRODUCER['sha'](root / name)) for name in
                    ['safe.jar', 'native/p2pkit-macos-tcp-manifest.jar']],
                native=dict(file='libp2pkit_lan_socket.dylib', source='1' * 40, abi='1', arch='arm64',
                    sha256=PRODUCER['sha'](native / 'libp2pkit_lan_socket.dylib')))
            expected = hashlib.sha256(json.dumps(manifest).encode()).hexdigest()
            transform(root, manifest)
            raw = json.dumps(manifest).encode()
            if pin_after:
                expected = hashlib.sha256(raw).hexdigest()
            (root / 'manifest.json').write_bytes(raw)
            script = root / 'run.py'
            script.write_text(PRODUCER['launcher_source'](expected, '1' * 40, str(java), java_digest))
            # This is a parser/path/hash test, not signature or process-execution evidence. A complete
            # passing fixture is necessary: a malformed baseline would make every negative test vacuous.
            with mock.patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as signing, \
                    mock.patch.object(os, 'execve') as launch:
                if admitted:
                    runpy.run_path(str(script), run_name='__main__')
                    signing.assert_called_once_with(
                        ['/usr/bin/codesign', '--verify', '--strict', str(native / 'libp2pkit_lan_socket.dylib')],
                        check=True)
                    launch.assert_called_once()
                    self.assertEqual(str(java), launch.call_args.args[0])
                    self.assertEqual('dev.p2pkit.sample.rpc.desktop.RpcDesktopMainKt',
                        launch.call_args.args[1][-1])
                else:
                    with self.assertRaises(AssertionError):
                        runpy.run_path(str(script), run_name='__main__')
                    launch.assert_not_called()

    def test_complete_fixture_reaches_only_the_mocked_execution_boundary(self):
        self.exercise(admitted=True)

    def test_jointly_changed_manifest_and_payload_cannot_redefine_hash_authority(self):
        def change(root, manifest):
            (root / 'safe.jar').write_bytes(b'changed bytes')
            manifest['entries'][0]['sha256'] = PRODUCER['sha'](root / 'safe.jar')
        self.exercise(change)

    def test_changed_java_path_cannot_redefine_execution_authority(self):
        self.exercise(lambda root, manifest: manifest.update(java='/unapproved/java'))

    def test_even_pinned_manifest_cannot_use_parent_traversal(self):
        self.exercise(lambda root, manifest: manifest['entries'][0].update(name='../outside.jar'), pin_after=True)

    def test_even_pinned_manifest_cannot_substitute_source(self):
        self.exercise(lambda root, manifest: manifest.update(sourceSha='2' * 40), pin_after=True)

    def test_old_manual_only_package_scope_is_not_current_application_authority(self):
        self.exercise(lambda root, manifest: manifest.update(
            scope='LOCAL_MANUAL_TCP_NOT_MULTICAST_OR_RELEASE_QUALIFICATION'), pin_after=True)

    def test_changed_jdk_or_native_bytes_cannot_reuse_a_pinned_manifest(self):
        for name in ['java', 'native/libp2pkit_lan_socket.dylib']:
            with self.subTest(name=name):
                self.exercise(lambda root, manifest: (root / name).write_bytes(b'changed'))

    def test_symlinked_classpath_cannot_reuse_even_identical_bytes(self):
        def change(root, manifest):
            (root / 'safe.jar').rename(root / 'original.jar')
            (root / 'safe.jar').symlink_to(root / 'original.jar')
        self.exercise(change)


if __name__ == '__main__':
    unittest.main()
