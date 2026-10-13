#!/usr/bin/env python3
"""Synthetic XML/byte controls only. No WiX, Windows, installation or native execution."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("msi_payload", ROOT / "scripts/verify-rpc-windows-msi-payload.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class StaticMsiPayloadTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.image = self.root / "image"
        self.extracted = self.root / "extract"
        self.files = self.extracted / "File"
        self.files.mkdir(parents=True)
        self.native = self.image / "app/resources/rpc-profile/windows-x64"
        self.native.mkdir(parents=True)
        self.dll = self.native / CHECK.DLL
        self.dll.write_bytes(b"synthetic-not-a-PE")
        self.manifest = self.native / "component.manifest"
        self.manifest.write_bytes(b"synthetic-not-a-production-manifest\n")
        self.jar = self.image / "app/p2pkit-windows-profile-parent-pin.jar"
        self.pin = b"synthetic-not-a-production-parent-pin\n"
        with zipfile.ZipFile(self.jar, "w") as archive:
            archive.writestr(CHECK.PIN, self.pin)
        self.msi = self.root / "P2pKit Sample.msi"
        self.msi.write_bytes(b"synthetic-not-a-production-msi")
        self.wxs = self.root / "decompiled.wxs"
        self.inspection = self.root / "image-inspection.json"
        self.receipt = {
            "scope": CHECK.IMAGE_SCOPE, "result": "PASS", "source": "a" * 40, "tree": "b" * 40,
            "dllSha256": CHECK.digest(self.dll.read_bytes()), "dllBytes": self.dll.stat().st_size,
            "manifestSha256": CHECK.digest(self.manifest.read_bytes()),
            "parentPin": {"file": self.jar.name, "pinSha256": CHECK.digest(self.pin),
                          "jarSha256": CHECK.digest(self.jar.read_bytes()), "jarBytes": self.jar.stat().st_size},
            "msi": {"file": self.msi.name, **CHECK.file_hash(self.msi, CHECK.MAX_MSI)},
        }
        self.save_receipt()
        self.xml = ET.Element(CHECK.NS + "Wix")
        self.product = ET.SubElement(self.xml, CHECK.NS + "Product")
        base = ET.SubElement(self.product, CHECK.NS + "Directory", Id="TARGETDIR", Name="SourceDir")
        base = ET.SubElement(base, CHECK.NS + "Directory", Id="ProgramFiles64Folder")
        install = ET.SubElement(base, CHECK.NS + "Directory", Id="INSTALLDIR", Name="P2pKit Sample")
        self.app = ET.SubElement(install, CHECK.NS + "Directory", Id="appDir", Name="app")
        resources = ET.SubElement(self.app, CHECK.NS + "Directory", Id="resourceDir", Name="resources")
        profile = ET.SubElement(resources, CHECK.NS + "Directory", Id="profileDir", Name="rpc-profile")
        self.arch = ET.SubElement(profile, CHECK.NS + "Directory", Id="archDir", Name="windows-x64")
        self.dll_node = self.add_file(self.arch, "nativeDll", self.dll)
        self.manifest_node = self.add_file(self.arch, "manifest", self.manifest)
        self.jar_node = self.add_file(self.app, "pinJar", self.jar)
        self.save_xml()

    def add_file(self, parent, identifier, original):
        target = self.files / identifier
        shutil.copyfile(original, target)
        owner = ET.SubElement(parent, CHECK.NS + "Component", Id="component_" + identifier)
        return ET.SubElement(owner, CHECK.NS + "File", Id=identifier, Name=original.name, Source=str(target))

    def save_xml(self):
        self.wxs.write_bytes(ET.tostring(self.xml, encoding="utf-8", xml_declaration=True))

    def save_receipt(self):
        self.inspection.write_text(json.dumps(self.receipt), encoding="utf-8")

    def inspect(self):
        return CHECK.inspect(self.wxs, self.extracted, self.image, self.inspection, self.msi)

    def test_exact_three_payloads_and_source_are_bound_without_installation_claim(self):
        result = self.inspect()
        self.assertEqual(CHECK.SCOPE, result["scope"])
        self.assertEqual("PASS", result["result"])
        self.assertEqual(self.receipt["source"], result["source"])
        self.assertEqual(3, len(result["comparedFiles"]))
        self.assertEqual({"File/nativeDll", "File/manifest", "File/pinJar"},
                         {file["extractedMember"] for file in result["comparedFiles"]})
        self.assertEqual(CHECK.digest(self.wxs.read_bytes()), result["wxsSha256"])
        for key in ("installation", "nativeExecution", "signing", "runtimeQualification",
                    "fullApplicationPayloadEquality"):
            self.assertEqual("NOT_PERFORMED", result[key])
        self.assertIn("CALLER_OWNED", result["extractionInvocation"])
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_mutation_of_each_extracted_component_is_rejected(self):
        for identifier in ("nativeDll", "manifest", "pinJar"):
            with self.subTest(component=identifier):
                path = self.files / identifier
                original = path.read_bytes()
                path.write_bytes(original + b"tamper")
                with self.assertRaisesRegex(ValueError, "payload differs"):
                    self.inspect()
                path.write_bytes(original)

    def test_matching_mutated_image_and_extracted_dll_cannot_replace_prior_pin(self):
        self.dll.write_bytes(b"different")
        shutil.copyfile(self.dll, self.files / "nativeDll")
        with self.assertRaisesRegex(ValueError, "changed after inspection"):
            self.inspect()

    def test_same_embedded_pin_does_not_allow_parent_jar_replacement(self):
        with zipfile.ZipFile(self.jar, "a") as archive:
            archive.writestr("extra.class", b"different")
        shutil.copyfile(self.jar, self.files / "pinJar")
        with self.assertRaisesRegex(ValueError, "parent JAR changed"):
            self.inspect()

    def test_missing_native_file_rejected(self):
        self.files.joinpath("nativeDll").unlink()
        with self.assertRaises(FileNotFoundError):
            self.inspect()

    def test_component_in_wrong_logical_directory_rejected(self):
        self.arch.set("Name", "windows-arm64")
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "misplaced MSI component"):
            self.inspect()

    def test_duplicate_component_name_including_case_variant_rejected(self):
        node = self.add_file(self.app, "duplicate", self.dll)
        node.set("Name", CHECK.DLL.upper())
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "duplicate or misplaced"):
            self.inspect()

    def test_duplicate_file_identifier_rejected(self):
        self.jar_node.set("Id", "nativeDll")
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "File identifier"):
            self.inspect()

    def test_duplicate_directory_identifier_rejected(self):
        self.arch.set("Id", "appDir")
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "Directory identifier"):
            self.inspect()

    def test_path_escape_or_alternate_extraction_source_rejected(self):
        original = self.dll_node.get("Source")
        for path in (self.root / "unowned", self.files / ".." / "File" / "nativeDll", Path("File/nativeDll")):
            self.dll_node.set("Source", str(path))
            self.save_xml()
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "Decompiler Source"):
                self.inspect()
        self.dll_node.set("Source", original)

    def test_source_file_identifier_traversal_rejected(self):
        self.dll_node.set("Id", "../nativeDll")
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "File identifier"):
            self.inspect()

    def test_msi_changed_since_prior_image_inspection_rejected(self):
        self.msi.write_bytes(self.msi.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "MSI differs"):
            self.inspect()

    def test_inspection_scope_result_and_weak_parent_observations_rejected(self):
        for key, replacement in (("scope", "SIGNED_READY"), ("result", "FAIL"), ("source", "HEAD")):
            original = self.receipt[key]
            self.receipt[key] = replacement
            self.save_receipt()
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect()
            self.receipt[key] = original
        del self.receipt["parentPin"]["jarSha256"]
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, "parent pin observation"):
            self.inspect()

    def test_duplicate_json_field_is_rejected(self):
        self.inspection.write_text('{"scope":"fake",' + json.dumps(self.receipt)[1:])
        with self.assertRaisesRegex(ValueError, "Duplicate inspection JSON"):
            self.inspect()

    def test_xml_entities_dtd_foreign_namespace_and_oversize_are_rejected(self):
        original = self.wxs.read_bytes()
        for xml in (b'<!DOCTYPE Wix [<!ENTITY x "x">]>' + original,
                    b'<!ENTITY x "x">' + original,
                    original.replace(b"http://schemas.microsoft.com/wix/2006/wi", b"https://untrusted.example"),
                    b" " * (CHECK.XML_LIMIT + 1)):
            self.wxs.write_bytes(xml)
            with self.subTest(size=len(xml)), self.assertRaises(ValueError):
                self.inspect()

    def test_utf8_bom_and_concrete_dot_directory_are_supported(self):
        component = next(node for node in self.arch if node.tag == CHECK.NS + "Component")
        self.arch.remove(component)
        dot = ET.SubElement(self.arch, CHECK.NS + "Directory", Id="dotDir", Name=".")
        dot.append(component)
        self.save_xml()
        self.wxs.write_bytes(b"\xef\xbb\xbf" + self.wxs.read_bytes())
        self.assertEqual("PASS", self.inspect()["result"])
        del dot.attrib["Name"]  # WiX dark serializes the MSI dot directory without a Name attribute.
        self.save_xml()
        self.assertEqual("PASS", self.inspect()["result"])

    def test_traversed_directory_rejection_is_not_bypassed(self):
        # Inert traversal seam, not a claim that native reparse-point behavior ran on this host.
        original = CHECK.ordinary
        calls = []
        def refuse(path, directory=False):
            calls.append(path)
            if path == self.files:
                raise ValueError("Expected an ordinary directory")
            return original(path, directory)
        CHECK.ordinary = refuse
        try:
            with self.assertRaisesRegex(ValueError, "ordinary directory"):
                self.inspect()
            self.assertIn(self.files, calls)
        finally:
            CHECK.ordinary = original

    def test_cli_creates_only_a_new_receipt_and_never_overwrites_it(self):
        output = self.root / "receipt.json"
        command = [sys.executable, "-I", "-B", str(ROOT / "scripts/verify-rpc-windows-msi-payload.py")]
        for name, value in (("wxs", self.wxs), ("extracted", self.extracted), ("image", self.image),
                            ("inspection", self.inspection), ("msi", self.msi), ("output", output)):
            command.extend(["--" + name, str(value)])
        first = subprocess.run(command, capture_output=True, timeout=20, check=False)
        self.assertEqual(0, first.returncode, first.stderr.decode())
        retained = output.read_bytes()
        second = subprocess.run(command, capture_output=True, timeout=20, check=False)
        self.assertNotEqual(0, second.returncode)
        self.assertEqual(retained, output.read_bytes())


if __name__ == "__main__":
    unittest.main()
