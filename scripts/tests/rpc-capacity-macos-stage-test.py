#!/usr/bin/env python3
"""Offline original-stage admission controls; synthetic bytes are never loaded or executed."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mac_capacity_stage", ROOT / "scripts/run-rpc-capacity-lab.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)
SOURCE, TREE = "a" * 40, "b" * 40


class NativeStageTests(unittest.TestCase):
    def setUp(self):
        # The real admission deliberately refuses a world-writable /tmp ancestor.
        # Allocate these private synthetic files under the current user's home.
        self.temporary = tempfile.TemporaryDirectory(prefix="rpc-native-admission-", dir=Path.home())
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.stage = self.root / ("library/p2p-transport-lan/build/macos-tcp/" + SOURCE)
        self.stage.mkdir(parents=True)
        self.directory = self.root / "samples/p2p-sample-rpc/build/capacity-lab"
        self.directory.mkdir(parents=True)
        self.library = struct.pack("<IIII", 0xFEEDFACF, 0x0100000C, 0, 6) + bytes(16)
        self.properties = lab.encode(dict(abi="1", platform="macos", arch="arm64", source=SOURCE, tree=TREE,
            file="libp2pkit_lan_socket.dylib", bytes=str(len(self.library)),
            sha256=hashlib.sha256(self.library).hexdigest()))
        (self.stage / "libp2pkit_lan_socket.dylib").write_bytes(self.library)
        (self.stage / "macos-tcp.properties").write_bytes(self.properties)
        (self.stage / "producer.json").write_bytes(b'{"synthetic":"not a producer or native execution receipt"}')
        with zipfile.ZipFile(self.stage / lab.MAC_MANIFEST_JAR, "x", compression=zipfile.ZIP_STORED) as jar:
            jar.writestr("META-INF/p2pkit/macos-tcp.properties", self.properties)
        (self.directory / "lab.jar").write_bytes(b"synthetic JAR content; no JVM execution")
        self.refresh()

    def refresh(self):
        original = self.stage / lab.MAC_MANIFEST_JAR
        (self.directory / lab.MAC_MANIFEST_JAR).write_bytes(original.read_bytes())
        for file in self.stage.iterdir():
            file.chmod(0o500 if file.name == "libp2pkit_lan_socket.dylib" else 0o400)
        self.manifest = dict(schema=1, sourceSha=SOURCE, scope="SYNTHETIC_LAB_NOT_PUBLICATION_OR_QUALIFICATION",
            entries=[dict(name=file.name, sha256=hashlib.sha256(file.read_bytes()).hexdigest())
                     for file in sorted(self.directory.glob("*.jar"))],
            macosNative=dict(directory="library/p2p-transport-lan/build/macos-tcp/" + SOURCE,
                entries=[dict(name=name, sha256=hashlib.sha256((self.stage / name).read_bytes()).hexdigest())
                         for name in lab.MAC_NATIVE_FILES]))
        self.save_manifest()

    def save_manifest(self):
        (self.directory / "manifest.json").write_text(json.dumps(self.manifest))

    def admit(self, system="Darwin", machine="arm64"):
        with patch.object(lab, "ROOT", self.root), patch.object(lab.platform, "system", return_value=system), \
                patch.object(lab.platform, "machine", return_value=machine), \
                patch.object(lab.subprocess, "check_output", return_value=(TREE + "\n").encode()) as git:
            options, binding = lab.native_options(SOURCE)
            git.assert_called_once_with(["git", "rev-parse", "HEAD^{tree}"], cwd=self.root, timeout=10)
            return options, binding

    def test_complete_stage_reaches_only_scoped_property_boundary(self):
        options, binding = self.admit()
        self.assertEqual(options, ["-Ddev.p2pkit.lan.macos.nativeDir=" + str(self.stage)])
        self.assertEqual(binding["sourceSha"], SOURCE)
        self.assertEqual(binding["treeSha"], TREE)
        self.assertEqual(binding["entries"], self.manifest["macosNative"]["entries"])
        with patch.object(lab.subprocess, "Popen") as child:
            self.admit()
            child.assert_not_called()

    def test_original_linux_distribution_retains_flat_manifest_and_no_native_option(self):
        del self.manifest["macosNative"]
        (self.directory / lab.MAC_MANIFEST_JAR).unlink()
        self.manifest["entries"] = [entry for entry in self.manifest["entries"] if entry["name"] == "lab.jar"]
        self.save_manifest()
        with patch.object(lab, "ROOT", self.root), patch.object(lab.platform, "system", return_value="Linux"):
            self.assertEqual(lab.classpath(SOURCE), str(self.directory / "lab.jar"))
            self.assertEqual(lab.native_options(SOURCE), ([], None))
        with self.assertRaises(RuntimeError):
            self.admit()

    def test_missing_stage_or_unsupported_host_never_uses_portable_fallback(self):
        for system, machine in (("Darwin", "x86_64"), ("Linux", "x86_64")):
            with self.subTest(system=system), self.assertRaises(RuntimeError):
                self.admit(system, machine)
        self.manifest.pop("macosNative")
        self.save_manifest()
        with self.assertRaises(RuntimeError):
            self.admit()

    def test_changed_source_or_arbitrary_directory_cannot_redirect_native_loading(self):
        for directory in ("/unapproved/native", "../outside", "library/p2p-transport-lan/build/macos-tcp/" + "c" * 40):
            self.manifest["macosNative"]["directory"] = directory
            self.save_manifest()
            with self.subTest(directory=directory), self.assertRaises(RuntimeError):
                self.admit()

    def test_changed_stage_bytes_cannot_reuse_an_existing_distribution(self):
        for name in lab.MAC_NATIVE_FILES:
            path = self.stage / name
            original = path.read_bytes()
            path.chmod(0o600)
            path.write_bytes(original + b"changed")
            path.chmod(0o400)
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                self.admit()
            path.chmod(0o600)
            path.write_bytes(original)
            path.chmod(0o400)

    def test_stage_owner_mode_links_and_inventory_are_required(self):
        properties = self.stage / "macos-tcp.properties"
        properties.chmod(0o444)
        with self.assertRaises(RuntimeError):
            self.admit()
        properties.chmod(0o400)
        alias = self.root / "outside-property-copy"
        os.link(properties, alias)
        with self.assertRaises(RuntimeError):
            self.admit()
        alias.unlink()
        properties.rename(alias)
        properties.symlink_to(alias)
        with self.assertRaises(RuntimeError):
            self.admit()
        properties.unlink()
        alias.rename(properties)
        self.stage.chmod(0o777)
        with self.assertRaises(RuntimeError):
            self.admit()
        self.stage.chmod(0o700)
        (self.stage / "foreign.so").write_bytes(b"never loaded")
        with self.assertRaises(RuntimeError):
            self.admit()

    def test_matching_hashes_do_not_admit_a_foreign_native_source_tree_or_machine(self):
        for key, value in (("source", "c" * 40), ("tree", "d" * 40), ("arch", "x86_64"), ("abi", "2")):
            altered = lab.parse(self.properties) | {key: value}
            path = self.stage / "macos-tcp.properties"
            path.chmod(0o600)
            path.write_bytes(lab.encode(altered))
            self.refresh()
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.admit()
        path.chmod(0o600)
        path.write_bytes(self.properties)
        path = self.stage / "libp2pkit_lan_socket.dylib"
        for header in (struct.pack("<IIII", 0xFEEDFACF, 0x01000007, 0, 6),
                       struct.pack("<IIII", 0xFEEDFACF, 0x0100000C, 0, 2)):
            path.chmod(0o600)
            path.write_bytes(header + bytes(16))
            altered = lab.parse(self.properties) | {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            properties = self.stage / "macos-tcp.properties"
            properties.chmod(0o600)
            properties.write_bytes(lab.encode(altered))
            self.refresh()
            with self.subTest(header=header), self.assertRaises(RuntimeError):
                self.admit()

    def test_classpath_manifest_requires_exact_original_resource_and_copied_bytes(self):
        path = self.stage / lab.MAC_MANIFEST_JAR
        path.chmod(0o600)
        with zipfile.ZipFile(path, "w") as jar:
            jar.writestr("META-INF/p2pkit/macos-tcp.properties", self.properties)
            jar.writestr("extra", b"untrusted")
        self.refresh()
        with self.assertRaises(RuntimeError):
            self.admit()
        path.chmod(0o600)
        with zipfile.ZipFile(path, "w") as jar:
            jar.writestr("META-INF/p2pkit/macos-tcp.properties", self.properties)
        self.refresh()
        copied = self.directory / lab.MAC_MANIFEST_JAR
        copied.write_bytes(copied.read_bytes() + b"copied bytes changed")
        self.manifest["entries"] = [dict(name=file.name, sha256=hashlib.sha256(file.read_bytes()).hexdigest())
                                   for file in sorted(self.directory.glob("*.jar"))]
        self.save_manifest()
        with self.assertRaises(RuntimeError):
            self.admit()

    def test_duplicate_distribution_fields_cannot_shadow_original_authority(self):
        raw = json.dumps(self.manifest)
        (self.directory / "manifest.json").write_text(raw[:-1] + ',"sourceSha":"' + SOURCE + '"}')
        with self.assertRaises(RuntimeError):
            self.admit()

    def test_regular_file_replaced_by_fifo_or_symlink_is_refused_without_blocking(self):
        target = self.directory / "lab.jar"
        original_open = os.open
        replaced = [False]

        def replace_then_open(path, flags, *args, **kwargs):
            if Path(path) == target and not replaced[0]:
                self.assertTrue(flags & os.O_NONBLOCK)
                self.assertTrue(flags & os.O_NOFOLLOW)
                target.unlink()
                os.mkfifo(target)
                replaced[0] = True
            return original_open(path, flags, *args, **kwargs)

        with patch.object(lab.os, "open", side_effect=replace_then_open), self.assertRaises(RuntimeError):
            lab.read_distribution_file(target, 65536)
        self.assertTrue(replaced[0])
        target.unlink()
        target.symlink_to(self.stage / lab.MAC_MANIFEST_JAR)
        with self.assertRaises(RuntimeError):
            lab.read_distribution_file(target, 65536)


if __name__ == "__main__":
    unittest.main()
