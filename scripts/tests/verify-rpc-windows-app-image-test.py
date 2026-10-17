#!/usr/bin/env python3
"""Synthetic-byte controls, not Windows package/runtime evidence."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import struct
import subprocess
import sys
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
    "dev/p2pkit/sample/rpc/profile/WindowsProfileInstalledProvider.class",
    "dev/p2pkit/sample/rpc/profile/WindowsProfileInstalledProvider$Entry.class",
    "dev/p2pkit/sample/rpc/profile/WindowsProfileInstalledProvider$CompleteAdapter.class",
    "dev/p2pkit/sample/rpc/profile/WindowsProfileInstalledProvider$Unavailable.class",
    "dev/p2pkit/sample/rpc/profile/WindowsProfileInstalledProvider$Unavailable$Companion.class",
    "dev/p2pkit/sample/rpc/profile/WindowsProfileCustodyJni.class",
    "dev/p2pkit/sample/rpc/profile/WindowsProfilePinnedImage.class",
)


ADAPTER_PREFIX = "dev/p2pkit/rpc/windows/loader/"
ADAPTER_ENTRIES = (
    "module-info.class", ADAPTER_PREFIX + "Probe.class", ADAPTER_PREFIX + "WindowsLoader.class",
    ADAPTER_PREFIX + "WindowsLoader$Unavailable.class",
    ADAPTER_PREFIX + "WindowsLoaderRuntime.class", ADAPTER_PREFIX + "WindowsX64Frame.class",
    ADAPTER_PREFIX + "WindowsX64Frame$AcquisitionFailure.class",
    ADAPTER_PREFIX + "WindowsX64Frame$CloseFailure.class", ADAPTER_PREFIX + "WindowsX64Frame$CleanupObservation.class",
    ADAPTER_PREFIX + "WindowsX64Frame$1.class",
    ADAPTER_PREFIX + "WindowsJniRegistrationOwner.class",
    ADAPTER_PREFIX + "WindowsJniRegistrationOwner$Failure.class",
    ADAPTER_PREFIX + "WindowsJniRegistrationOwner$FailureKind.class",
    ADAPTER_PREFIX + "WindowsJniRegistrationOwner$Invocation.class",
    ADAPTER_PREFIX + "WindowsJniRegistrationOwner$Report.class",
    ADAPTER_PREFIX + "WindowsJniRegistrationOwner$Retention.class",
    ADAPTER_PREFIX + "WindowsJniRegistrationOwner$State.class",
    ADAPTER_PREFIX + "WindowsJniRegistrationInvocation.class",
    ADAPTER_PREFIX + "WindowsJniRegistrationInvocation$AcquisitionFailure.class",
    ADAPTER_PREFIX + "WindowsJniRegistrationInvocation$RetirementFailure.class",
    ADAPTER_PREFIX + "WindowsJvmAcquisitionInvocation.class",
    ADAPTER_PREFIX + "WindowsJvmAcquisitionInvocation$Failure.class",
    ADAPTER_PREFIX + "WindowsJvmAcquisitionInvocation$Result.class",
    ADAPTER_PREFIX + "WindowsLibraryLoadInvocation.class",
    ADAPTER_PREFIX + "WindowsLibraryLoadInvocation$Failure.class",
    ADAPTER_PREFIX + "WindowsLibraryLoadInvocation$Result.class",
    ADAPTER_PREFIX + "WindowsExportLookupInvocation.class",
    ADAPTER_PREFIX + "WindowsExportLookupInvocation$Failure.class",
    ADAPTER_PREFIX + "WindowsExportLookupInvocation$Result.class",
    ADAPTER_PREFIX + "WindowsImageReadInvocation.class",
    ADAPTER_PREFIX + "WindowsImageReadInvocation$Failure.class",
    ADAPTER_PREFIX + "WindowsImageReadInvocation$Result.class",
    ADAPTER_PREFIX + "WindowsImageReadInvocation$Kind.class",
    ADAPTER_PREFIX + "WindowsSystemBootstrapCandidate.class",
    ADAPTER_PREFIX + "WindowsSystemBootstrapCandidate$Failure.class",
    ADAPTER_PREFIX + "WindowsOriginalJvmCandidate.class",
    ADAPTER_PREFIX + "WindowsOriginalJvmCandidate$Failure.class",
    ADAPTER_PREFIX + "WindowsOriginalJvmFileCandidate.class",
    ADAPTER_PREFIX + "WindowsOriginalFileLease.class",
    ADAPTER_PREFIX + "WindowsOriginalFileLease$Failure.class",
    ADAPTER_PREFIX + "WindowsOriginalProfileDllFileCandidate.class",
    ADAPTER_PREFIX + "WindowsOriginalProfileDllFileCandidate$Failure.class",
    ADAPTER_PREFIX + "WindowsProfileDllPath.class",
    ADAPTER_PREFIX + "WindowsInstallationSecurity.class",
    ADAPTER_PREFIX + "WindowsInstallationSecurity$Kind.class",
    ADAPTER_PREFIX + "WindowsOriginalJvmSecurityCandidate.class",
    ADAPTER_PREFIX + "WindowsOriginalFileSecurityQuery.class",
    ADAPTER_PREFIX + "WindowsOriginalFileSecurityQuery$Failure.class",
    ADAPTER_PREFIX + "WindowsOriginalProfileDllSecurityCandidate.class",
    ADAPTER_PREFIX + "WindowsOriginalProfileDllSecurityCandidate$Failure.class",
    ADAPTER_PREFIX + "WindowsOriginalJvmAncestorsCandidate.class",
    ADAPTER_PREFIX + "WindowsOriginalFileAncestorsLease.class",
    ADAPTER_PREFIX + "WindowsOriginalFileAncestorsLease$Failure.class",
    ADAPTER_PREFIX + "WindowsOriginalProfileDllAncestorsCandidate.class",
    ADAPTER_PREFIX + "WindowsOriginalProfileDllAncestorsCandidate$Failure.class",
    ADAPTER_PREFIX + "WindowsOriginalJvmBytesCandidate.class",
    ADAPTER_PREFIX + "WindowsOriginalJvmBytesCandidate$Failure.class",
    ADAPTER_PREFIX + "WindowsSystemImportResolution.class",
    ADAPTER_PREFIX + "WindowsSystemImportResolution$Failure.class",
    ADAPTER_PREFIX + "WindowsSystemExportPlan.class",
    ADAPTER_PREFIX + "WindowsSystemExportPlan$Input.class",
    ADAPTER_PREFIX + "WindowsSystemExportPlan$Target.class",
    ADAPTER_PREFIX + "WindowsSystemExportPlan$Forward.class",
    ADAPTER_PREFIX + "WindowsSystemExportPlan$Span.class",
    ADAPTER_PREFIX + "WindowsSystemExportPlan$Section.class",
    ADAPTER_PREFIX + "WindowsSystemExportPlan$Budget.class",
    ADAPTER_PREFIX + "WindowsSystemExportPlan$Module.class",
    ADAPTER_PREFIX + "WindowsPackagedVerifier.class",
)
ADAPTER_OPTIONS = (
    "--enable-preview", "--module-path=$APPDIR/resources/rpc-loader-jdk21",
    "--add-modules=dev.p2pkit.rpc.windows.loader", "--enable-native-access=dev.p2pkit.rpc.windows.loader",
)


def u2(*values):
    return struct.pack(">" + "H" * len(values), *values)


def utf(value):
    encoded = value.encode("ascii")
    return b"\x01" + u2(len(encoded)) + encoded


def inert_class(name, *, major=65, minor=0):
    # Complete structural class file with no executable methods, used only by the static byte reader.
    # This is not a substitute for JVM verification/real javac output or installed runtime tests.
    cp = utf(name[:-6]) + b"\x07" + u2(1) + utf("java/lang/Object") + b"\x07" + u2(3)
    return b"\xca\xfe\xba\xbe" + u2(minor, major, 5) + cp + u2(0x21, 2, 4, 0, 0, 0, 0)


def inert_module(*, module="dev.p2pkit.rpc.windows.loader", exports="dev/p2pkit/rpc/windows/loader",
                 dependency="java.base", flags=0):
    cp = (utf("module-info") + b"\x07" + u2(1) + utf("Module") + utf(module) + b"\x13" + u2(4) +
          utf(dependency) + b"\x13" + u2(6) + utf("21.0.11") + utf(exports) + b"\x14" + u2(9))
    descriptor = u2(5, flags, 0, 1, 7, 0x8000, 8, 1, 10, 0, 0, 0, 0, 0)
    return (b"\xca\xfe\xba\xbe" + u2(0, 65, 11) + cp + u2(0x8000, 2, 0, 0, 0, 0, 1, 3) +
            struct.pack(">I", len(descriptor)) + descriptor)


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

    def inspect(self, preview_adapter=False):
        return CHECK.inspect(self.image, self.compiler, self.msi, self.source, self.tree, preview_adapter)

    def add_adapter(self):
        self.adapter = self.image / "app/resources/rpc-loader-jdk21/p2pkit-windows-loader-jdk21.jar"
        self.adapter.parent.mkdir()
        self.adapter_content = {entry: inert_class(entry, minor=65535 if entry.endswith("/Probe.class") else 0)
                                for entry in ADAPTER_ENTRIES}
        self.adapter_content["module-info.class"] = inert_module()
        self.write_adapter()
        (self.image / "runtime/release").write_text('JAVA_VERSION="21.0.11"\nMODULES="java.base jdk.unsupported"\n')
        self.cfg = self.image / "app/P2pKit Sample.cfg"
        self.write_cfg(ADAPTER_OPTIONS)

    def write_adapter(self):
        with zipfile.ZipFile(self.adapter, "w") as archive:
            archive.writestr("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\r\n\r\n")
            archive.writestr("META-INF/LICENSE", (ROOT / "LICENSE").read_bytes())
            for name, data in self.adapter_content.items():
                archive.writestr(name, data)

    def write_cfg(self, options):
        self.cfg.write_bytes(("[Application]\r\napp.mainclass=dev.p2pkit.sample.desktop.ui.MainKt\r\n"
                              "[JavaOptions]\r\njava-options=-Djpackage.app-version=1.0.0\r\n" +
                              "".join("java-options=" + option + "\r\n" for option in options)).encode("utf-8"))

    def test_optional_adapter_binds_structural_metadata_hash_and_exact_launcher_flags(self):
        self.add_adapter()
        result = self.inspect(True)
        adapter = result["adapter"]
        self.assertEqual("STATIC_JDK21_PREVIEW_MODULE_NOT_LOAD_AUTHORITY", adapter["scope"])
        self.assertEqual("app/resources/rpc-loader-jdk21/p2pkit-windows-loader-jdk21.jar", adapter["file"])
        self.assertEqual("dev.p2pkit.rpc.windows.loader", adapter["module"])
        self.assertEqual(65, adapter["probeMajor"])
        self.assertEqual(65535, adapter["probeMinor"])
        self.assertEqual(self.adapter.stat().st_size, adapter["jarBytes"])
        self.assertEqual(CHECK.digest(self.adapter.read_bytes()), adapter["jarSha256"])
        self.assertEqual(sorted(ADAPTER_ENTRIES), [entry["entry"] for entry in adapter["classes"]])
        self.assertEqual(list(ADAPTER_OPTIONS), adapter["launcher"]["requiredOptions"])
        self.assertEqual(CHECK.digest(self.cfg.read_bytes()), adapter["launcher"]["sha256"])
        self.assertEqual("NOT_ESTABLISHED", adapter["installedAuthority"])
        self.assertEqual("NOT_PERFORMED", adapter["nativeExecution"])
        self.assertEqual("NOT_PERFORMED", result["runtimeQualification"])

    def test_adapter_inventory_bound_counts_only_exact_files_and_optional_directories(self):
        self.add_adapter()
        directories = ("META-INF/", "dev/", "dev/p2pkit/", "dev/p2pkit/rpc/", "dev/p2pkit/rpc/windows/",
                       ADAPTER_PREFIX)
        self.adapter_content.update({name: b"" for name in directories})
        self.write_adapter()
        self.assertEqual("PASS", self.inspect(True)["result"])
        with zipfile.ZipFile(self.adapter) as archive:
            self.assertEqual(len(ADAPTER_ENTRIES) + 2 + len(directories), len(archive.infolist()))
        self.adapter_content["unexpected/"] = b""
        self.write_adapter()
        with self.assertRaisesRegex(ValueError, "oversized adapter inventory"):
            self.inspect(True)
        del self.adapter_content[directories[0]]
        self.write_adapter()
        with self.assertRaisesRegex(ValueError, "unexpected or test adapter entry"):
            self.inspect(True)

    def test_default_inspection_keeps_original_three_component_contract(self):
        self.assertNotIn("adapter", self.inspect())

    def test_default_mode_cannot_ignore_unrequested_adapter_resources_or_classpath_entries(self):
        self.write_classes(self.image / "app/unrequested-adapter.jar", [ADAPTER_PREFIX + "Probe.class"])
        with self.assertRaisesRegex(ValueError, "application classpath"):
            self.inspect()
        (self.image / "app/unrequested-adapter.jar").unlink()
        self.add_adapter()
        with self.assertRaisesRegex(ValueError, "explicit optional inspection"):
            self.inspect()

    def test_optional_adapter_cannot_be_missing_or_have_unreviewed_siblings(self):
        with self.assertRaisesRegex(ValueError, "adapter resources"):
            self.inspect(True)
        self.add_adapter()
        (self.adapter.parent / "extra.jar").write_bytes(b"inert")
        with self.assertRaisesRegex(ValueError, "adapter resources"):
            self.inspect(True)

    def test_adapter_classes_and_jar_use_the_same_observation(self):
        self.add_adapter()
        original = CHECK.file_digest

        def mutate(path, stream, before, maximum):
            if path == self.adapter:
                data = path.read_bytes()
                path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
            return original(path, stream, before, maximum)

        with patch.object(CHECK, "file_digest", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "JAR changed before digest"):
                self.inspect(True)

    def test_adapter_jar_rejects_tests_versioned_shadows_and_other_entries(self):
        self.add_adapter()
        for extra in (ADAPTER_PREFIX + "WindowsLoaderTest.class", ADAPTER_PREFIX + "RegistrationOwnerTests.class",
                      ADAPTER_PREFIX + "RegistrationInvocationTests.class",
                      ADAPTER_PREFIX + "VmAcquisitionInvocationTests.class",
                      ADAPTER_PREFIX + "LibraryLoadInvocationTests.class",
                      ADAPTER_PREFIX + "ExportLookupInvocationTests.class",
                      ADAPTER_PREFIX + "ImageReadInvocationTests.class",
                      ADAPTER_PREFIX + "SystemBootstrapCandidateTests.class",
                      ADAPTER_PREFIX + "InstallationSecurityTests.class",
                      ADAPTER_PREFIX + "AncestorRetirementTests.class",
                      ADAPTER_PREFIX + "ByteReadInvocationTests.class",
                      ADAPTER_PREFIX + "PackagedVerifierTests.class",
                      ADAPTER_PREFIX + "LoadedRegistrationTests.class",
                      ADAPTER_PREFIX + "LoadedRegistrationTests$Fixture.class",
                      ADAPTER_PREFIX + "LoadedRegistrationTests$SystemImports.class",
                      ADAPTER_PREFIX + "WindowsJniRegistrationOwner$Unexpected.class",
                      "META-INF/versions/21/" + ADAPTER_ENTRIES[1],
                      "META-INF/services/unexpected", "unexpected.dll"):
            self.adapter_content[extra] = b"inert"
            self.write_adapter()
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "test adapter entry"):
                self.inspect(True)
            del self.adapter_content[extra]

    def test_each_adapter_class_is_mandatory(self):
        self.add_adapter()
        for entry in ADAPTER_ENTRIES:
            removed = self.adapter_content.pop(entry)
            self.write_adapter()
            with self.subTest(missing=entry), self.assertRaisesRegex(ValueError, "adapter entry"):
                self.inspect(True)
            self.adapter_content[entry] = removed

    def test_duplicate_adapter_entry_rejected(self):
        self.add_adapter()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.adapter, "a") as archive:
                archive.writestr(ADAPTER_ENTRIES[1], self.adapter_content[ADAPTER_ENTRIES[1]])
        with self.assertRaisesRegex(ValueError, "Duplicate.*adapter inventory"):
            self.inspect(True)

    def test_adapter_descriptor_is_parsed_not_substring_matched(self):
        self.add_adapter()
        for descriptor in (inert_module(module="unexpected.module"), inert_module(exports="another/package"),
                           inert_module(dependency="java.logging"), inert_module(flags=0x20),
                           b"dev.p2pkit.rpc.windows.loader", inert_module()[:-1], inert_module() + b"extra"):
            self.adapter_content["module-info.class"] = descriptor
            self.write_adapter()
            with self.subTest(descriptor=descriptor[-24:]), self.assertRaises(ValueError):
                self.inspect(True)

    def test_adapter_probe_requires_real_class_header_and_exact_preview_family(self):
        self.add_adapter()
        name = ADAPTER_PREFIX + "Probe.class"
        for data in (inert_class(name, minor=0), inert_class(name, major=66, minor=65535),
                     inert_class(name, minor=1), inert_class(ADAPTER_PREFIX + "Wrong.class", minor=65535),
                     inert_class(name, minor=65535)[:-1], b"not-a-class"):
            self.adapter_content[name] = data
            self.write_adapter()
            with self.subTest(data=data[:12]), self.assertRaises(ValueError):
                self.inspect(True)

    def test_adapter_manifest_cannot_add_classpath_or_automatic_module_identity(self):
        self.add_adapter()
        for extra in (b"Class-Path: outside.jar\r\n", b"Automatic-Module-Name: other.module\r\n"):
            with zipfile.ZipFile(self.adapter, "w") as archive:
                archive.writestr("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\r\n" + extra + b"\r\n")
                archive.writestr("META-INF/LICENSE", (ROOT / "LICENSE").read_bytes())
                for name, data in self.adapter_content.items():
                    archive.writestr(name, data)
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "adapter manifest"):
                self.inspect(True)

    def test_adapter_requires_the_maintained_license_notice_without_mutation(self):
        self.add_adapter()
        for license_bytes in (None, b"replaced notice"):
            with zipfile.ZipFile(self.adapter, "w") as archive:
                archive.writestr("META-INF/MANIFEST.MF", b"Manifest-Version: 1.0\r\n\r\n")
                if license_bytes is not None:
                    archive.writestr("META-INF/LICENSE", license_bytes)
                for name, data in self.adapter_content.items():
                    archive.writestr(name, data)
            with self.subTest(missing=license_bytes is None), self.assertRaisesRegex(ValueError, "entry|license"):
                self.inspect(True)

    def test_optional_adapter_requires_linked_runtime_21(self):
        self.add_adapter()
        for version in ('17.0.18', '22', '21garbage'):
            (self.image / "runtime/release").write_text(
                'JAVA_VERSION="' + version + '"\nMODULES="java.base jdk.unsupported"\n')
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "linked JDK21"):
                self.inspect(True)

    def test_each_explicit_adapter_option_is_required_once_and_cannot_be_overridden(self):
        self.add_adapter()
        for option in ADAPTER_OPTIONS:
            for options in ([entry for entry in ADAPTER_OPTIONS if entry != option], [*ADAPTER_OPTIONS, option]):
                self.write_cfg(options)
                with self.subTest(options=options), self.assertRaisesRegex(ValueError, "adapter runtime option"):
                    self.inspect(True)
        for extra in ('--enable-native-access=ALL-UNNAMED', '--module-path=other', '-p=other',
                      '--add-modules=ALL-MODULE-PATH', '--enable-preview=false',
                      '--patch-module=dev.p2pkit.rpc.windows.loader=outside.jar', '-javaagent:outside.jar'):
            self.write_cfg([*ADAPTER_OPTIONS, extra])
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "authority|runtime option"):
                self.inspect(True)

    def test_adapter_cannot_be_put_on_application_classpath_or_versioned_shadow(self):
        self.add_adapter()
        for name in (ADAPTER_ENTRIES[1], "META-INF/versions/21/" + ADAPTER_ENTRIES[1]):
            self.write_classes(self.image / "app/shadow.jar", [name])
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "application classpath"):
                self.inspect(True)
        (self.image / "app/shadow.jar").unlink()
        self.cfg.write_text(self.cfg.read_text().replace("[JavaOptions]", "app.classpath=" + self.adapter.name +
                                                       "\n[JavaOptions]"))
        with self.assertRaisesRegex(ValueError, "application classpath"):
            self.inspect(True)


    def test_adapter_options_in_other_launcher_section_are_rejected(self):
        self.add_adapter()
        self.cfg.write_text(self.cfg.read_text() + "[AppCDSJavaOptions]\njava-options=--enable-preview\n")
        with self.assertRaisesRegex(ValueError, "outside maintained launcher section"):
            self.inspect(True)

    def test_adapter_resource_ancestor_reported_as_link_is_rejected(self):
        self.add_adapter()
        original = Path.is_symlink

        def observed_link(path):
            # Deterministic structural seam; no symlink privileges or native reparse claims.
            return path == self.adapter.parent or original(path)

        with patch.object(Path, "is_symlink", observed_link):
            with self.assertRaisesRegex(ValueError, "ordinary adapter resources/ancestors"):
                self.inspect(True)

    def test_optional_adapter_cli_creates_source_bound_new_receipt_without_overwriting(self):
        self.add_adapter()
        output = self.root / "new-inspection.json"
        command = [sys.executable, "-I", "-B", str(ROOT / "scripts/verify-rpc-windows-app-image.py"),
                   "--preview-adapter", "--source", self.source, "--tree", self.tree]
        for name, path in (("image", self.image), ("compiler", self.compiler), ("msi", self.msi), ("output", output)):
            command.extend(("--" + name, str(path)))
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        before = output.read_bytes()
        self.assertEqual("dev.p2pkit.rpc.windows.loader", json.loads(before)["adapter"]["module"])
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(before, output.read_bytes())

    def test_failed_cli_keeps_bounded_diagnostics_but_never_a_success_receipt(self):
        self.add_adapter()
        self.cfg.write_text(self.cfg.read_text().replace("[JavaOptions]", "app.classpath=" + self.adapter.name +
                                                       "\n[JavaOptions]"))
        output, diagnostics = self.root / "inspection.json", self.root / "diagnostics"
        command = [sys.executable, "-I", "-B", str(ROOT / "scripts/verify-rpc-windows-app-image.py"),
                   "--preview-adapter", "--source", self.source, "--tree", self.tree]
        for name, path in (("image", self.image), ("compiler", self.compiler), ("msi", self.msi),
                           ("output", output), ("diagnostics", diagnostics)):
            command.extend(("--" + name, str(path)))
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Adapter must not use application classpath", result.stderr)
        self.assertFalse(output.exists())
        record = json.loads((diagnostics / "diagnostics.json").read_text())
        self.assertEqual("BUILD_IMAGE_DIAGNOSTICS_NOT_ACCEPTANCE_OR_LOAD_AUTHORITY", record["scope"])
        self.assertNotIn("result", record)
        self.assertEqual((self.source, self.tree), (record["source"], record["tree"]))
        self.assertEqual(["launcher.cfg", "runtime-release"], [entry["file"] for entry in record["files"]])
        for entry in record["files"]:
            data = (diagnostics / entry["file"]).read_bytes()
            self.assertEqual((self.image / entry["input"]).read_bytes(), data)
            self.assertEqual((len(data), CHECK.digest(data)), (entry["bytes"], entry["sha256"]))

    def test_diagnostics_refuse_overwrite_and_oversized_input(self):
        self.add_adapter()
        destination = self.root / "diagnostics"
        CHECK.retain_launcher_diagnostics(self.image, destination, self.source, self.tree)
        before = (destination / "diagnostics.json").read_bytes()
        with self.assertRaises(FileExistsError):
            CHECK.retain_launcher_diagnostics(self.image, destination, self.source, self.tree)
        self.assertEqual(before, (destination / "diagnostics.json").read_bytes())
        self.cfg.write_bytes(b"x" * 65537)
        failed = self.root / "oversized-diagnostics"
        with self.assertRaisesRegex(ValueError, "Input size outside bound"):
            CHECK.retain_launcher_diagnostics(self.image, failed, self.source, self.tree)
        self.assertEqual([], list(failed.iterdir()))

    def test_diagnostics_refuse_nonordinary_image_ancestors_before_copying(self):
        self.add_adapter()
        original = Path.is_symlink
        for directory in (self.image, self.image / "app", self.image / "runtime"):
            with patch.object(Path, "is_symlink", lambda path: path == directory or original(path)):
                with self.assertRaisesRegex(ValueError, "ordinary build image diagnostic directories"):
                    CHECK.retain_launcher_diagnostics(self.image, self.root / "diagnostics", self.source, self.tree)
            self.assertFalse((self.root / "diagnostics").exists())

    def test_diagnostics_only_cli_never_requests_or_creates_inspection_receipt(self):
        self.add_adapter()
        self.cfg.write_text(self.cfg.read_text().replace("[JavaOptions]", "app.classpath=" + self.adapter.name +
                                                       "\n[JavaOptions]"))
        destination = self.root / "diagnostics"
        command = [sys.executable, "-I", "-B", str(ROOT / "scripts/verify-rpc-windows-app-image.py"),
                   "--diagnostics-only", "--image", str(self.image), "--diagnostics", str(destination),
                   "--source", self.source, "--tree", self.tree]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("BUILD_IMAGE_DIAGNOSTICS_RETAINED_NOT_ACCEPTANCE\n", result.stdout)
        self.assertNotIn("result", json.loads((destination / "diagnostics.json").read_text()))
        self.assertEqual({"launcher.cfg", "runtime-release", "diagnostics.json"},
                         {path.name for path in destination.iterdir()})
        # The exact same bad configuration still fails ordinary inspection.
        with self.assertRaisesRegex(ValueError, "application classpath"):
            self.inspect(True)

    def test_cli_cannot_mix_diagnostics_with_a_success_receipt_or_omit_inspection_inputs(self):
        self.add_adapter()
        output, destination = self.root / "inspection.json", self.root / "diagnostics"
        base = [sys.executable, "-I", "-B", str(ROOT / "scripts/verify-rpc-windows-app-image.py"),
                "--image", str(self.image), "--source", self.source, "--tree", self.tree]
        for arguments in ([], ["--diagnostics-only"],
                          ["--diagnostics-only", "--diagnostics", str(destination), "--output", str(output)],
                          ["--diagnostics-only", "--diagnostics", str(destination), "--preview-adapter"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(base + arguments, capture_output=True, text=True, timeout=10)
                self.assertEqual(2, result.returncode)
                self.assertFalse(destination.exists())
                self.assertFalse(output.exists())

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
