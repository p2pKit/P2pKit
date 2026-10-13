#!/usr/bin/env python3
"""Synthetic-byte controls, not Windows package/runtime evidence."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
import warnings
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("image_check", ROOT / "scripts/verify-rpc-windows-app-image.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


# Independent expected inventory: do not derive fixtures from the implementation's requirement list.
APPLICATION_CLASSES = (
    "dev/p2pkit/sample/desktop/ui/MainKt.class",
    "dev/p2pkit/sample/desktop/ui/DesktopSampleNavigation.class",
    "dev/p2pkit/sample/desktop/ui/DesktopRpcSectionKt.class",
)
RPC_CLASSES = (
    "dev/p2pkit/sample/rpc/desktop/RpcDesktopPanel.class",
    "dev/p2pkit/sample/rpc/desktop/RpcDesktopWindowsRuntimeReadback.class",
    "dev/p2pkit/sample/rpc/desktop/DesktopRpcProfile.class",
    "dev/p2pkit/sample/rpc/profile/WindowsProfileFiles.class",
    "dev/p2pkit/sample/rpc/profile/WindowsProfileCustodyJni.class",
    "dev/p2pkit/sample/rpc/profile/WindowsProfilePinnedImage.class",
)


class ImageInspectionTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.image = self.root / "image"
        self.native = self.image / "app/resources/rpc-profile/windows-x64"
        self.native.mkdir(parents=True)
        self.source, self.tree = "a" * 40, "b" * 40
        library = b"synthetic-inert-library-not-a-PE"
        self.hash = CHECK.digest(library)
        (self.native / CHECK.DLL).write_bytes(library)
        self.manifest = ("schema=1\ncomponent=windows-profile-custody\nabi=13\nplatform=windows\narch=x86_64\n"
                         f"source={self.source}\ntree={self.tree}\nclean=true\nfile={CHECK.DLL}\n"
                         f"bytes={len(library)}\nsha256={self.hash}\ncapabilities=0x43\n").encode()
        (self.native / "component.manifest").write_bytes(self.manifest)
        self.compiler = self.root / "compiler.properties"
        self.compiler.write_bytes((f"schema=1\nscope=COMPILER_BYTES_ONLY\nsource={self.source}\n"
                                   f"tree={self.tree}\nsha256={self.hash}\n").encode("ascii"))
        self.pin = (f"schema=1\nscope=PACKAGED_COMPONENT_PIN_NOT_LOAD_AUTHORITY\nsource={self.source}\n"
                    f"tree={self.tree}\nmanifestSha256={CHECK.digest(self.manifest)}\ndllSha256={self.hash}\n")
        self.jar = self.image / "app/parent-pin.jar"
        self.write_pin(self.jar)
        self.application_jar = self.image / "app/sample.jar"
        self.rpc_jar = self.image / "app/rpc.jar"
        self.write_classes(self.application_jar, APPLICATION_CLASSES)
        self.write_classes(self.rpc_jar, RPC_CLASSES)
        (self.image / "runtime").mkdir()
        (self.image / "runtime/release").write_text('MODULES="java.base jdk.unsupported"\n')
        self.msi = self.root / "P2pKit Sample-1.0.0.msi"
        self.msi.write_bytes(bytes.fromhex("d0cf11e0a1b11ae1") + b"synthetic-not-an-installer")

    def write_classes(self, path, names):
        with zipfile.ZipFile(path, "w") as archive:
            for name in names:
                archive.writestr(name, b"synthetic-inert-class-not-runtime-evidence")

    def test_each_required_rpc_class_is_mandatory_not_just_main_and_native_pins(self):
        for missing in (*APPLICATION_CLASSES, *RPC_CLASSES):
            jar, names = ((self.application_jar, APPLICATION_CLASSES) if missing in APPLICATION_CLASSES
                          else (self.rpc_jar, RPC_CLASSES))
            self.write_classes(jar, [name for name in names if name != missing])
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, "required"):
                self.inspect()
            self.write_classes(jar, names)

    def test_required_class_shadow_in_another_jar_is_rejected(self):
        extra = self.image / "app/shadow.jar"
        for entry in (*APPLICATION_CLASSES, *RPC_CLASSES):
            self.write_classes(extra, [entry])
            with self.subTest(shadow=entry), self.assertRaisesRegex(ValueError, "required"):
                self.inspect()
        extra.unlink()

    def test_versioned_required_class_cannot_replace_the_reviewed_base_class(self):
        for entry in (*APPLICATION_CLASSES, *RPC_CLASSES):
            self.write_classes(self.image / "app/versioned.jar", ["META-INF/versions/17/" + entry])
            with self.subTest(shadow=entry), self.assertRaisesRegex(ValueError, "[Vv]ersioned"):
                self.inspect()

    def test_duplicate_required_entry_within_one_jar_is_rejected(self):
        for entry in RPC_CLASSES:
            self.write_classes(self.rpc_jar, RPC_CLASSES)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(self.rpc_jar, "a") as archive:
                    archive.writestr(entry, b"duplicate")
            with self.subTest(duplicate=entry), self.assertRaisesRegex(ValueError, "Duplicate required"):
                self.inspect()

    def test_empty_required_class_is_rejected(self):
        self.write_classes(self.rpc_jar, RPC_CLASSES[1:])
        with zipfile.ZipFile(self.rpc_jar, "a") as archive:
            archive.writestr(RPC_CLASSES[0], b"")
        with self.assertRaisesRegex(ValueError, "empty or oversized required"):
            self.inspect()

    def test_required_class_decompression_is_bounded(self):
        self.write_classes(self.rpc_jar, RPC_CLASSES[1:])
        with zipfile.ZipFile(self.rpc_jar, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(RPC_CLASSES[0], b"x" * (16 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, "oversized required"):
            self.inspect()

    def test_missing_base_class_is_not_satisfied_by_a_versioned_class(self):
        self.write_classes(self.rpc_jar, RPC_CLASSES[1:])
        with zipfile.ZipFile(self.rpc_jar, "a") as archive:
            archive.writestr("META-INF/versions/17/" + RPC_CLASSES[0], b"inert")
        with self.assertRaisesRegex(ValueError, "Versioned required"):
            self.inspect()

    def test_dependency_multirelease_entries_are_not_globally_rejected(self):
        self.write_classes(self.image / "app/dependency.jar", (
            "some/dependency/Entry.class", "META-INF/versions/17/some/dependency/Entry.class",
        ))
        self.assertEqual("PASS", self.inspect()["result"])

    def test_navigation_section_cannot_be_detached_from_the_maintained_application_jar(self):
        self.write_classes(self.application_jar, APPLICATION_CLASSES[:2])
        self.write_classes(self.image / "app/detached.jar", APPLICATION_CLASSES[2:])
        with self.assertRaisesRegex(ValueError, "must belong to its application JAR"):
            self.inspect()

    def test_class_inventory_has_exact_byte_pins_without_execution_or_classpath_claims(self):
        result = self.inspect()
        self.assertEqual("STATIC_ENTRIES_ONLY_NOT_LINKAGE_OR_EXECUTION", result["classInventory"])
        expected = {self.application_jar.name: APPLICATION_CLASSES, self.rpc_jar.name: RPC_CLASSES}
        self.assertEqual(sorted(expected), [jar["file"] for jar in result["requiredClassJars"]])
        for jar in result["requiredClassJars"]:
            path = self.image / "app" / jar["file"]
            self.assertEqual(len(path.read_bytes()), jar["jarBytes"])
            self.assertEqual(CHECK.digest(path.read_bytes()), jar["jarSha256"])
            self.assertEqual(sorted(expected[jar["file"]]), [entry["entry"] for entry in jar["classes"]])
            with zipfile.ZipFile(path) as archive:
                for entry in jar["classes"]:
                    data = archive.read(entry["entry"])
                    self.assertEqual(len(data), entry["bytes"])
                    self.assertEqual(CHECK.digest(data), entry["sha256"])
        self.assertEqual("NOT_PERFORMED", result["runtimeQualification"])
        self.assertNotIn(str(self.root), str(result))

    def test_class_entries_and_owning_jar_cannot_come_from_different_observations(self):
        original = CHECK.file_digest
        touched = []

        def mutate(path, stream, before, maximum):
            if path == self.rpc_jar:
                touched.append(path)
                data = path.read_bytes()
                path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
            return original(path, stream, before, maximum)

        with patch.object(CHECK, "file_digest", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "JAR changed before digest"):
                self.inspect()
        self.assertEqual([self.rpc_jar], touched)

    def write_pin(self, path, contents=None):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(CHECK.PIN, self.pin if contents is None else contents)

    def inspect(self):
        return CHECK.inspect(self.image, self.compiler, self.msi, self.source, self.tree)

    def test_matching_bytes_explicitly_do_not_qualify_installation_or_runtime(self):
        result = self.inspect()
        self.assertEqual(CHECK.SCOPE, result["scope"])
        for key in ("installedPayloadEquality", "nativeExecution", "runtimeQualification", "signing"):
            self.assertEqual("NOT_PERFORMED", result[key])
        self.assertEqual(self.hash, result["dllSha256"])
        self.assertEqual(len(self.jar.read_bytes()), result["parentPin"]["jarBytes"])
        self.assertEqual(CHECK.digest(self.jar.read_bytes()), result["parentPin"]["jarSha256"])

    def test_pin_and_whole_jar_digest_cannot_come_from_different_observations(self):
        original = CHECK.file_digest

        def mutate(path, stream, before, maximum):
            # Deterministic same-file/same-size mutation between pin validation and hashing.
            # Explicit timestamp makes this independent of host timestamp granularity.
            data = path.read_bytes()
            path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
            return original(path, stream, before, maximum)

        with patch.object(CHECK, "file_digest", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "JAR changed before digest"):
                self.inspect()

    def test_changed_dll_is_rejected(self):
        (self.native / CHECK.DLL).write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "compiler bytes"):
            self.inspect()

    def test_changed_manifest_is_rejected(self):
        (self.native / "component.manifest").write_bytes(self.manifest.replace(b"0x43", b"0x7f"))
        with self.assertRaisesRegex(ValueError, "component contract"):
            self.inspect()

    def test_parent_pin_source_and_digest_are_independently_checked(self):
        for original in (self.source, self.tree, self.hash, CHECK.digest(self.manifest)):
            self.write_pin(self.jar, self.pin.replace(original, "0" * len(original)))
            with self.subTest(field=original), self.assertRaisesRegex(ValueError, "parent pin mismatch"):
                self.inspect()

    def test_duplicate_pin_jar_is_rejected(self):
        self.write_pin(self.image / "app/extra.jar")
        with self.assertRaisesRegex(ValueError, "exactly one maintained application parent pin"):
            self.inspect()

    def test_missing_parent_pin_is_rejected(self):
        self.jar.unlink()
        with self.assertRaisesRegex(ValueError, "parent pin"):
            self.inspect()

    def test_other_app_cannot_replace_existing_application(self):
        (self.image / "app/sample.jar").unlink()
        with self.assertRaisesRegex(ValueError, "exactly one maintained Desktop"):
            self.inspect()

    def test_compiler_wrong_source_rejected(self):
        self.compiler.write_bytes(self.compiler.read_bytes().replace(self.source.encode("ascii"), b"0" * 40))
        with self.assertRaisesRegex(ValueError, "Compiler source"):
            self.inspect()

    def test_missing_module_is_rejected(self):
        (self.image / "runtime/release").write_text('MODULES="java.base"\n')
        with self.assertRaisesRegex(ValueError, "module dependency"):
            self.inspect()

    def test_windows_runtime_release_crlf_is_supported(self):
        (self.image / "runtime/release").write_bytes(b'JAVA_VERSION="17"\r\nMODULES="java.base jdk.unsupported"\r\n')
        self.assertTrue(self.inspect()["declaredUnsupportedModule"])

    def test_duplicate_runtime_module_declarations_are_rejected(self):
        (self.image / "runtime/release").write_bytes(b'MODULES="java.base jdk.unsupported"\r\n' * 2)
        with self.assertRaisesRegex(ValueError, "module dependency"):
            self.inspect()

    def test_missing_native_member_or_unexpected_file_is_rejected(self):
        (self.native / "unexpected").write_bytes(b"inert")
        with self.assertRaisesRegex(ValueError, "unexpected native"):
            self.inspect()
        (self.native / "unexpected").unlink()
        (self.native / CHECK.DLL).unlink()
        with self.assertRaisesRegex(ValueError, "unexpected native"):
            self.inspect()

    def test_truncated_or_other_installer_is_rejected(self):
        self.msi.write_bytes(b"not MSI bytes")
        with self.assertRaisesRegex(ValueError, "header"):
            self.inspect()

    def test_noncanonical_records_are_rejected(self):
        for value in (self.manifest.replace(b"\n", b"\r\n"), self.manifest + b"extra=true\n",
                      self.manifest[:-1]):
            (self.native / "component.manifest").write_bytes(value)
            with self.subTest(value=value[-20:]), self.assertRaises(ValueError):
                self.inspect()


if __name__ == "__main__":
    unittest.main()
