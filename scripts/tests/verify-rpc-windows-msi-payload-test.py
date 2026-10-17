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
            # Stable synthetic JAR: MD5 includes two interior one-digit bytes (07 and 05).
            archive.writestr(zipfile.ZipInfo(CHECK.PIN, (2026, 1, 1, 0, 0, 46)), self.pin)
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
        # Exact scope representation observed in the ccb18938 hosted dark output:
        # x64 Package and ALLUSERS=1; no authored InstallScope attribute survives.
        ET.SubElement(self.product, CHECK.NS + "Package", Platform="x64", Compressed="yes",
                      InstallerVersion="200", Languages="1033")
        ET.SubElement(self.product, CHECK.NS + "Property", Id="ALLUSERS", Value="1")
        base = ET.SubElement(self.product, CHECK.NS + "Directory", Id="TARGETDIR", Name="SourceDir")
        base = ET.SubElement(base, CHECK.NS + "Directory", Id="ProgramFiles64Folder")
        install = ET.SubElement(base, CHECK.NS + "Directory", Id="INSTALLDIR", Name="P2pKit Sample")
        self.app = ET.SubElement(install, CHECK.NS + "Directory", Id="appDir", Name="app")
        self.resources = ET.SubElement(self.app, CHECK.NS + "Directory", Id="resourceDir", Name="resources")
        profile = ET.SubElement(self.resources, CHECK.NS + "Directory", Id="profileDir", Name="rpc-profile")
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

    def rename_parent_jar(self, name):
        self.jar = self.jar.rename(self.jar.with_name(name))
        self.receipt["parentPin"]["file"] = name
        self.jar_node.set("Name", name)
        self.save_receipt()
        self.save_xml()

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

    def test_actual_dark_machine_default_is_observed_without_installed_authority(self):
        self.assertNotIn("InstallScope", self.product.find(CHECK.NS + "Package").attrib)
        result = self.inspect()
        self.assertEqual({"scope": "STATIC_MSI_DEFAULTS_NOT_INSTALLED_AUTHORITY", "platform": "x64", "allUsers": "1",
                          "directoryChain": [{"id": "TARGETDIR", "name": "SourceDir"},
                                             {"id": "ProgramFiles64Folder", "name": None},
                                             {"id": "INSTALLDIR", "name": "P2pKit Sample"}],
                          "directoryChooser": "NOT_DECLARED", "administrativeOverrides": "NOT_PREVENTED"},
                         result["installationDefaults"])
        self.assertEqual("NOT_PERFORMED", result["installation"])
        self.product.find(CHECK.NS + "Package").set("InstallScope", "perMachine")
        self.save_xml()
        self.assertEqual(result["installationDefaults"], self.inspect()["installationDefaults"])

    def test_missing_duplicate_or_conflicting_package_scope_is_refused(self):
        package = self.product.find(CHECK.NS + "Package")
        self.product.remove(package)
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "package"):
            self.inspect()
        self.product.append(package)
        duplicate = ET.SubElement(self.product, CHECK.NS + "Package", Platform="x64")
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "package"):
            self.inspect()
        self.product.remove(duplicate)
        for name, value in (("Platform", "x86"), ("Platform", "arm64"), ("InstallScope", "perUser")):
            original = dict(package.attrib)
            package.set(name, value)
            self.save_xml()
            with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, "package"):
                self.inspect()
            package.attrib.clear()
            package.attrib.update(original)

    def test_allusers_is_exact_and_per_user_or_duplicate_properties_refuse(self):
        prop = self.product.find(CHECK.NS + "Property")
        for value in ("", "0", "2", "[ALLUSERS]"):
            prop.set("Value", value)
            self.save_xml()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "properties"):
                self.inspect()
        self.product.remove(prop)
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "properties"):
            self.inspect()
        prop.set("Value", "1")
        self.product.append(prop)
        for identifier in ("ALLUSERS", "MSIINSTALLPERUSER"):
            other = ET.SubElement(self.product, CHECK.NS + "Property", Id=identifier, Value="1")
            self.save_xml()
            with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, "properties"):
                self.inspect()
            self.product.remove(other)

    def test_install_default_root_name_and_ancestry_are_exact(self):
        directory = {node.get("Id"): node for node in self.xml.iter(CHECK.NS + "Directory")}
        for identifier, attribute, value in (("ProgramFiles64Folder", "Id", "LocalAppDataFolder"),
                                            ("ProgramFiles64Folder", "Id", "ProgramFilesFolder"),
                                            ("ProgramFiles64Folder", "Name", "other-root"),
                                            ("TARGETDIR", "Name", "other-root"),
                                            ("INSTALLDIR", "Name", "Other Application")):
            node = directory[identifier]
            original = dict(node.attrib)
            node.set(attribute, value)
            self.save_xml()
            with self.subTest(identifier=identifier, attribute=attribute), self.assertRaisesRegex(ValueError, "directory"):
                self.inspect()
            node.attrib.clear()
            node.attrib.update(original)
        base, install = directory["ProgramFiles64Folder"], directory["INSTALLDIR"]
        base.remove(install)
        extra = ET.SubElement(base, CHECK.NS + "Directory", Id="extraParent", Name="extra")
        extra.append(install)
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "directory"):
            self.inspect()

    def test_direct_install_directory_property_cannot_override_default(self):
        for value in ("", "C:\\Other", "[LocalAppDataFolder]"):
            node = ET.SubElement(self.product, CHECK.NS + "Property", Id="INSTALLDIR", Value=value)
            self.save_xml()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "overrides"):
                self.inspect()
            self.product.remove(node)

    def test_directory_chooser_properties_dialogs_and_routing_are_refused(self):
        cases = [("Property", {"Id": "WIXUI_INSTALLDIR", "Value": "INSTALLDIR"}),
                 ("Dialog", {"Id": "InstallDirDlg"}), ("Dialog", {"Id": "BrowseDlg"}),
                 ("DialogRef", {"Id": "InstallDirDlg"}),
                 ("Publish", {"Dialog": "InstallDirDlg", "Event": "NewDialog", "Value": "VerifyReadyDlg"}),
                 ("Publish", {"Dialog": "WelcomeDlg", "Event": "NewDialog", "Value": "BrowseDlg"}),
                 ("Publish", {"Property": "INSTALLDIR", "Value": "[LocalAppDataFolder]"}),
                 ("Publish", {"Event": "SetTargetPath", "Value": "[WIXUI_INSTALLDIR]"})]
        for tag, attributes in cases:
            node = ET.SubElement(self.product, CHECK.NS + tag, **attributes)
            self.save_xml()
            with self.subTest(tag=tag, attributes=attributes), self.assertRaisesRegex(ValueError, "chooser"):
                self.inspect()
            self.product.remove(node)

    def test_generic_ui_and_arp_metadata_are_not_misclassified_as_directory_chooser(self):
        ET.SubElement(self.product, CHECK.NS + "UIRef", Id="WixUI_InstallDir")
        ET.SubElement(self.product, CHECK.NS + "CustomAction", Id="JpSetARPINSTALLLOCATION",
                      Property="ARPINSTALLLOCATION", Value="[INSTALLDIR]")
        self.save_xml()
        self.assertEqual("PASS", self.inspect()["result"])

    def add_adapter(self):
        self.adapter = self.image / "app/resources/rpc-loader-jdk21/p2pkit-windows-loader-jdk21.jar"
        self.adapter.parent.mkdir()
        self.adapter.write_bytes(b"synthetic-adapter-not-native-or-runtime-evidence")
        self.receipt["adapter"] = {
            "scope": "STATIC_JDK21_PREVIEW_MODULE_NOT_LOAD_AUTHORITY",
            "file": "app/resources/rpc-loader-jdk21/p2pkit-windows-loader-jdk21.jar",
            "module": "dev.p2pkit.rpc.windows.loader", "probeMajor": 65, "probeMinor": 65535,
            "jarBytes": self.adapter.stat().st_size, "jarSha256": CHECK.digest(self.adapter.read_bytes()),
            "nativeExecution": "NOT_PERFORMED", "installedAuthority": "NOT_ESTABLISHED",
        }
        self.adapter_dir = ET.SubElement(self.resources, CHECK.NS + "Directory",
                                        Id="loaderAdapterDir", Name="rpc-loader-jdk21")
        self.adapter_node = self.add_file(self.adapter_dir, "loaderAdapter", self.adapter)
        self.save_receipt()
        self.save_xml()

    def test_optional_fourth_adapter_payload_has_exact_receipt_pins_without_runtime_claim(self):
        self.add_adapter()
        result = self.inspect()
        self.assertEqual(4, len(result["comparedFiles"]))
        self.assertEqual({"target": "app/resources/rpc-loader-jdk21/p2pkit-windows-loader-jdk21.jar",
                          "extractedMember": "File/loaderAdapter", "bytes": self.adapter.stat().st_size,
                          "sha256": CHECK.digest(self.adapter.read_bytes())}, result["comparedFiles"][3])
        for field in ("installation", "nativeExecution", "runtimeQualification", "signing"):
            self.assertEqual("NOT_PERFORMED", result[field])

    def test_extracted_optional_adapter_cannot_differ_from_image(self):
        self.add_adapter()
        (self.files / "loaderAdapter").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "payload differs"):
            self.inspect()

    def test_matching_replaced_image_and_extracted_adapter_cannot_replace_prior_pin(self):
        self.add_adapter()
        self.adapter.write_bytes(b"changed")
        shutil.copyfile(self.adapter, self.files / "loaderAdapter")
        with self.assertRaisesRegex(ValueError, "changed after inspection"):
            self.inspect()

    def test_adapter_size_pin_independently_required(self):
        self.add_adapter()
        self.receipt["adapter"]["jarBytes"] += 1
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, "adapter JAR changed"):
            self.inspect()

    def test_missing_adapter_inventory_and_missing_extracted_member_fail_closed(self):
        self.add_adapter()
        self.adapter_dir.clear()
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "missing Directory identifier|misplaced MSI component"):
            self.inspect()
        # Restore valid inventory but omit the actual decompiled payload.
        self.adapter_dir.set("Id", "loaderAdapterDir")
        self.adapter_dir.set("Name", "rpc-loader-jdk21")
        self.add_file(self.adapter_dir, "loaderAdapter", self.adapter)
        self.save_xml()
        (self.files / "loaderAdapter").unlink()
        with self.assertRaises(FileNotFoundError):
            self.inspect()

    def test_optional_adapter_has_exact_fixed_resource_location(self):
        self.add_adapter()
        self.adapter_dir.set("Name", "other-loader")
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "misplaced MSI component"):
            self.inspect()

    def test_optional_adapter_cannot_be_duplicated_in_application_classpath(self):
        self.add_adapter()
        self.add_file(self.app, "duplicateAdapter", self.adapter)
        self.save_xml()
        with self.assertRaisesRegex(ValueError, "duplicate or misplaced MSI component"):
            self.inspect()

    def test_optional_adapter_cannot_be_smuggled_into_original_three_component_receipt(self):
        self.add_adapter()
        del self.receipt["adapter"]
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, "no optional image observation"):
            self.inspect()

    def test_optional_adapter_rejects_null_and_weak_or_privilege_claiming_metadata(self):
        self.add_adapter()
        original = self.receipt["adapter"].copy()
        for key, value in (("scope", "READY"), ("file", "app/elsewhere.jar"), ("module", "unnamed"),
                           ("jarBytes", True), ("jarBytes", 0), ("jarBytes", 16 * 1024 * 1024 + 1),
                           ("jarSha256", "0" * 63), ("jarSha256", "A" * 64),
                           ("probeMajor", 66), ("probeMinor", 0), ("nativeExecution", "PASS"),
                           ("installedAuthority", "ESTABLISHED")):
            self.receipt["adapter"] = {**original, key: value}
            self.save_receipt()
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, "adapter image observation"):
                self.inspect()
        self.receipt["adapter"] = None
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, "adapter image observation"):
            self.inspect()

    def test_compose_content_renamed_jar_with_30_character_suffix_is_supported(self):
        # Independently fixed producer vector, not an expected value computed by the tested helper.
        name = "p2pkit-windows-profile-parent-pin-6414ce33bfc074754b7e6ffd6390e3.jar"
        self.rename_parent_jar(name)
        result = self.inspect()
        self.assertEqual("PASS", result["result"])
        self.assertIn("app/" + name, {file["target"] for file in result["comparedFiles"]})
        self.assertNotIn("composeSuffix", json.dumps(result))

    def test_compose_content_renamed_jar_with_32_character_suffix_is_supported(self):
        with zipfile.ZipFile(self.jar, "w") as archive:
            archive.writestr(zipfile.ZipInfo(CHECK.PIN, (2026, 1, 1, 0, 0, 0)), self.pin)
        shutil.copyfile(self.jar, self.files / "pinJar")
        self.receipt["parentPin"].update(jarSha256=CHECK.digest(self.jar.read_bytes()),
                                        jarBytes=self.jar.stat().st_size)
        self.rename_parent_jar("p2pkit-windows-profile-parent-pin-853cfde7dd614378a39b3d9c73836973.jar")
        self.assertEqual("PASS", self.inspect()["result"])

    def test_wrong_or_zero_padded_compose_suffix_is_rejected_even_with_matching_receipt_and_xml(self):
        for suffix in ("0" * 32, "6414ce33bfc07407054b7e6ffd6390e3", "6414ce33bfc074754b7e6ffd6390e2"):
            self.rename_parent_jar("p2pkit-windows-profile-parent-pin-" + suffix + ".jar")
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, "Compose content mangling"):
                self.inspect()

    def test_only_exact_parent_jar_family_and_compose_suffix_shape_are_allowed(self):
        original = self.receipt["parentPin"]["file"]
        for name in ("arbitrary.jar", "p2pkit-windows-profile-parent-pin-other.jar",
                     "p2pkit-windows-profile-parent-pin-" + "a" * 15 + ".jar",
                     "p2pkit-windows-profile-parent-pin-" + "a" * 33 + ".jar",
                     "p2pkit-windows-profile-parent-pin-" + "A" * 30 + ".jar",
                     "p2pkit-windows-profile-parent-pin-.jar", "p2pkit-windows-profile-parent-pin.jar.jar",
                     "p2pkit-windows-profile-parent-pin.jar.exe", "p2pkit-windows-profile-parent-pin.JAR"):
            self.receipt["parentPin"]["file"] = name
            self.save_receipt()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Unexpected parent-pin JAR"):
                self.inspect()
        self.receipt["parentPin"]["file"] = original

    def test_compose_suffix_cannot_be_transferred_to_a_different_jar(self):
        self.rename_parent_jar("p2pkit-windows-profile-parent-pin-6414ce33bfc074754b7e6ffd6390e3.jar")
        with zipfile.ZipFile(self.jar, "a") as archive:
            archive.writestr("extra.class", b"different")
        shutil.copyfile(self.jar, self.files / "pinJar")
        self.receipt["parentPin"].update(jarSha256=CHECK.digest(self.jar.read_bytes()),
                                        jarBytes=self.jar.stat().st_size)
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, "Compose content mangling"):
            self.inspect()

    def test_compose_name_does_not_replace_prior_sha256_authority(self):
        self.rename_parent_jar("p2pkit-windows-profile-parent-pin-6414ce33bfc074754b7e6ffd6390e3.jar")
        self.receipt["parentPin"]["jarSha256"] = "0" * 64
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, "parent JAR changed after inspection"):
            self.inspect()

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

    def test_windows_crlf_xml_and_inspection_json_are_supported(self):
        self.wxs.write_bytes(self.wxs.read_bytes().replace(b"\n", b"\r\n"))
        self.inspection.write_bytes(json.dumps(self.receipt, indent=2).replace("\n", "\r\n").encode())
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
