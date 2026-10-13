#!/usr/bin/env python3
"""Synthetic-byte controls, not Windows package/runtime evidence."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("image_check", ROOT / "scripts/verify-rpc-windows-app-image.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


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
        with zipfile.ZipFile(self.image / "app/sample.jar", "w") as archive:
            archive.writestr("dev/p2pkit/sample/desktop/ui/MainKt.class", b"inert")
            archive.writestr("dev/p2pkit/sample/desktop/ui/DesktopSampleNavigation.class", b"inert")
        (self.image / "runtime").mkdir()
        (self.image / "runtime/release").write_text('MODULES="java.base jdk.unsupported"\n')
        self.msi = self.root / "P2pKit Sample-1.0.0.msi"
        self.msi.write_bytes(bytes.fromhex("d0cf11e0a1b11ae1") + b"synthetic-not-an-installer")

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
