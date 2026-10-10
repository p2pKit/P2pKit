#!/usr/bin/env python3
"""Offline parser and bounded-input controls; actual signature checks belong to explicit Mac fixtures."""
import importlib.util
import os
from pathlib import Path
import plistlib
import tempfile
import time
import unittest
import zipfile

HELPER_PATH = Path(__file__).resolve().parents[1] / 'stage-rpc-macos-app.py'
SPEC = importlib.util.spec_from_file_location('stage_rpc_app', HELPER_PATH)
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


class AppImageControls(unittest.TestCase):
    def test_finalizer_declares_producers_before_lazy_packager_configuration(self):
        source = (HELPER_PATH.parent.parent / 'samples/p2p-sample-desktop-ui/build.gradle.kts').read_text()
        registration = source.split('tasks.register<Exec>("finalizeRpcMacosDevelopmentApp") {', 1)[1]
        registration = registration.split('tasks.withType<AbstractJPackageTask>()', 1)[0]
        self.assertIn('dependsOn("createDistributable", ":p2p-transport-lan:stageMacTcp")', registration)
        self.assertIn('inputs.dir(originalApp)', registration)
        self.assertIn('"--input-app", originalApp.get().asFile', registration)
        self.assertIn('argumentProviders.add(CommandLineArgumentProvider', registration)
        self.assertNotIn('commandLine(', registration)
        self.assertNotIn('doFirst', registration)
        self.assertNotIn('finalizeRpcMacosDevelopmentApp.configure', source)
        self.assertIn('appImage.set(finalizedDirectory)', source)
        self.assertNotIn('appImage.set(finalizedApp)', source)

    def test_native_stage_keeps_clean_check_in_independent_producer(self):
        root = HELPER_PATH.parent.parent
        source = (root / 'library/p2p-transport-lan/build.gradle.kts').read_text()
        registration = source.split('tasks.register<Exec>("stageMacTcp") {', 1)[1]
        registration = registration.split('// Opt-in tests', 1)[0]
        self.assertIn('inputs.property("sourceDirty", macTcpDirty)', registration)
        self.assertIn('argumentProviders.add(CommandLineArgumentProvider', registration)
        self.assertNotIn('doFirst', registration)
        producer = (root / 'scripts/build-macos-jvm-tcp.py').read_text()
        self.assertLess(producer.index("'Clean source required'"), producer.index('if output.exists():'))
        self.assertIn('output.rmdir()', producer)
        self.assertNotIn('shutil.rmtree', producer)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='p2pkit-app-image-controls-')
        self.root = Path(self.temporary.name).resolve()
        self.app = self.root / 'P2pKit Fixture.app'
        (self.app / 'Contents/MacOS').mkdir(parents=True)
        (self.app / 'Contents/app').mkdir()
        (self.app / 'Contents/MacOS/Fixture').write_bytes(b'not an executable; parser fixture only')
        (self.app / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable': 'Fixture'}))
        self.raw = b'synthetic-authority\n'
        self.jar('transport.jar', {'dev/p2pkit/transport/lan/MacLanNativeLoader.class': b'not real bytecode'})
        self.jar('mangled-manifest-name.jar', {HELPER.RESOURCE: self.raw})
        self.cfg()

    def tearDown(self):
        self.temporary.cleanup()

    def jar(self, name, entries):
        with zipfile.ZipFile(self.app / 'Contents/app' / name, 'x') as jar:
            for path, data in entries.items():
                jar.writestr(path, data)

    def cfg(self, classpath=None, options=None):
        classpath = classpath or ['$APPDIR/transport.jar:$APPDIR/mangled-manifest-name.jar']
        options = options if options is not None else ['-D' + HELPER.PROPERTY + '=' + HELPER.POLICY]
        (self.app / 'Contents/app/Fixture.cfg').write_text(
            '[Application]\n' + ''.join('app.classpath=' + value + '\n' for value in classpath) +
            '[JavaOptions]\n' + ''.join('java-options=' + value + '\n' for value in options))

    def test_mangled_manifest_name_and_explicit_multiple_classpath_lines(self):
        self.assertEqual(HELPER.classpath_authority(self.app, self.raw),
                         ('Fixture', 'mangled-manifest-name.jar', 'transport.jar'))
        self.cfg(classpath=['$APPDIR/transport.jar', '$APPDIR/mangled-manifest-name.jar'])
        self.assertEqual(HELPER.classpath_authority(self.app, self.raw)[1], 'mangled-manifest-name.jar')

    def test_external_wildcard_and_duplicate_classpaths_rejected(self):
        for entry in ['/tmp/transport.jar', '$APPDIR/../transport.jar', '$APPDIR/*',
                      '$APPDIR/transport.jar:$APPDIR/transport.jar']:
            with self.subTest(entry=entry):
                self.cfg(classpath=[entry])
                with self.assertRaises(ValueError):
                    HELPER.launcher_classpath(self.app)

    def test_exact_policy_and_no_private_or_alternate_code_authority(self):
        expected = '-D' + HELPER.PROPERTY + '=' + HELPER.POLICY
        for options in [[], [expected, expected], [expected + '-wrong'],
                        [expected, '-Ddev.p2pkit.lan.macos.nativeDir=/arbitrary'],
                        [expected, '-javaagent:agent.jar'], [expected, '-Djava.system.class.loader=Alternate']]:
            with self.subTest(options=options):
                self.cfg(options=options)
                with self.assertRaises(ValueError):
                    HELPER.launcher_classpath(self.app)

    def test_duplicate_authority_and_wrong_manifest_rejected(self):
        with self.assertRaises(ValueError):
            HELPER.classpath_authority(self.app, b'wrong')
        self.jar('other.jar', {HELPER.RESOURCE: self.raw})
        self.cfg(classpath=['$APPDIR/transport.jar:$APPDIR/mangled-manifest-name.jar:$APPDIR/other.jar'])
        with self.assertRaises(ValueError):
            HELPER.classpath_authority(self.app, self.raw)

    def test_bounded_reads_reject_oversize_symlink_and_hardlink(self):
        path = self.root / 'bounded'
        path.write_bytes(b'12345')
        self.assertEqual(HELPER.bounded_read(path, 5), b'12345')
        with self.assertRaises(ValueError):
            HELPER.bounded_read(path, 4)
        link = self.root / 'link'
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            HELPER.bounded_read(link, 5)
        os.link(path, self.root / 'hardlink')
        with self.assertRaises(ValueError):
            HELPER.bounded_read(path, 5)

    def test_large_plist_is_rejected_before_decoding(self):
        (self.app / 'Contents/Info.plist').write_bytes(b'x' * 65537)
        with self.assertRaisesRegex(ValueError, 'size bound'):
            HELPER.launcher_classpath(self.app)

    def test_exited_leader_with_held_writer_fails_without_blocking_or_signalling_writer(self):
        read_fd, write_fd = os.pipe()
        stream = os.fdopen(read_fd, 'rb', buffering=0)
        class ExitedLeader:
            stdout = stream
            def poll(self):
                return 0
            def wait(self, timeout):
                return 0
            def kill(self):
                raise AssertionError('Exited leader or unowned writer must not be signalled')
        try:
            start = time.monotonic()
            with self.assertRaisesRegex(ValueError, 'EOF remains unproven'):
                HELPER.collect_tool(ExitedLeader(), timeout=0.05)
            self.assertLess(time.monotonic() - start, 1)
            self.assertTrue(stream.closed)
            os.fstat(write_fd)  # The test-owned writer remains open; no claim that a descendant was retired.
        finally:
            stream.close()
            os.close(write_fd)

    def test_adhoc_flags_are_structured_not_exact_combined_display(self):
        good = 'CodeDirectory v=20500 size=100 flags=0x10002(adhoc,runtime) hashes=2+5\n'
        good += 'Signature=adhoc\nTeamIdentifier=not set\n'
        HELPER.ad_hoc(good)
        for value in [good.replace('0x10002', '0x10000'), good.replace('Signature=adhoc', 'Signature=invalid'),
                      good.replace('TeamIdentifier=not set', 'TeamIdentifier=WRONG'), good + 'Signature=adhoc\n']:
            with self.subTest(metadata=value):
                with self.assertRaises(ValueError):
                    HELPER.ad_hoc(value)


if __name__ == '__main__':
    unittest.main()
