#!/usr/bin/env python3
"""Synthetic parser/negative tests; no native tools, mounts, apps, or downloads."""

import importlib.util
import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


subject = load("sample_artifact_identity", ROOT / "scripts/sample_artifact_identity.py")
fixture = load("sample_binary_manifest", ROOT / "scripts/tests/fixtures/sample_binary_manifest.py")
SOURCE, VERSION = "a" * 40, "0.8.0-rc1"


class ArtifactIdentityTests(unittest.TestCase):
    def test_actual_binary_manifest_attributes_utf8_and_utf16(self):
        for utf8 in (True, False):
            self.assertEqual(subject.apk_manifest(fixture.manifest(utf8=utf8)), {
                "applicationId": "dev.p2pkit.sample.android", "versionCode": 320202, "versionName": VERSION})

    def test_reject_text_truncation_length_and_resource_substitution(self):
        original = fixture.manifest()
        for bad in (b"<manifest package='fake'/>", original[:-1], original + b"\0", original[:4] + b"\0" * 4 + original[8:],
                    original.replace(struct.pack("<I", 0x0101021b), struct.pack("<I", 0x0101021a))):
            with self.subTest(length=len(bad)), self.assertRaises(ValueError):
                subject.apk_manifest(bad)

    def test_embedded_source_and_all_fields_are_required(self):
        value = subject.VERSION.embedded_identity(VERSION, SOURCE)
        self.assertEqual(subject.embedded(json.dumps(value).encode(), VERSION, SOURCE), value)
        for key, replacement in (("sourceCommit", "b" * 40), ("canonicalVersion", "0.8.0"), ("androidVersionCode", 1),
                                 ("nativeVersion", "1.8.399"), ("debianVersion", "1.8.201-2"), ("schema", 2)):
            with self.subTest(field=key), self.assertRaises(ValueError):
                subject.embedded(json.dumps({**value, key: replacement}).encode(), VERSION, SOURCE)
        with self.assertRaises(ValueError):
            subject.embedded(b'{"schema":1,"schema":1}', VERSION, SOURCE)

    def apk(self, version=VERSION, code=320202, source=SOURCE):
        result = io.BytesIO()
        with zipfile.ZipFile(result, "w") as archive:
            archive.writestr("AndroidManifest.xml", fixture.manifest(version=version, code=code))
            archive.writestr("assets/p2pkit-release.json", json.dumps(subject.VERSION.embedded_identity(version, source)))
        result.seek(0)
        return zipfile.ZipFile(result)

    def test_apk_sidecar_cannot_override_real_version_or_source(self):
        with self.apk() as archive:
            self.assertEqual(subject.inspect_apk(archive, VERSION, SOURCE)["binaryManifest"]["versionCode"], 320202)
        for arguments in ({"version": "0.8.0"}, {"code": 1}, {"source": "b" * 40}):
            with self.subTest(arguments=arguments), self.apk(**arguments) as archive, self.assertRaises(ValueError):
                subject.inspect_apk(archive, VERSION, SOURCE)

    def test_platform_versions_include_debian_revision_and_both_mac_keys(self):
        fixtures = {"linux": {"Package": "p2pkit-sample", "Version": "1.8.201-1", "Architecture": "amd64"},
                    "windows": {"ProductName": "P2pKit Sample", "ProductVersion": "1.8.201", "Template": "x64;1033"},
                    "macos": {"CFBundleShortVersionString": "1.8.201", "CFBundleVersion": "1.8.201"}}
        for system, fields in fixtures.items():
            self.assertEqual(subject.native_fields(system, fields, VERSION), fields)
            for key in fields:
                for wrong in (None, "", "1.0.0", "arm64"):
                    with self.subTest(system=system, key=key, wrong=wrong), self.assertRaises(ValueError):
                        subject.native_fields(system, {**fields, key: wrong}, VERSION)
        for wrong in ("1.8.201", "1.8.201-2", "1.8.201-1+extra"):
            with self.assertRaises(ValueError):
                subject.native_fields("linux", {**fixtures["linux"], "Version": wrong}, VERSION)

    def test_native_read_failure_does_not_become_a_version_pass(self):
        with mock.patch.object(subject, "run", side_effect=ValueError("native reader failure")), self.assertRaises(ValueError):
            subject.inspect_native(Path("fixture.deb"), "linux", VERSION, SOURCE, None)

    def jar(self, directory, name="sample.jar", main=True, identity=True, source=SOURCE):
        with zipfile.ZipFile(directory / name, "w") as archive:
            if main:
                archive.writestr(subject.MAIN_CLASS, b"\xca\xfe\xba\xbeSYNTHETIC")
            if identity:
                archive.writestr("p2pkit-release.json", json.dumps(subject.VERSION.embedded_identity(VERSION, source)))

    def test_embedded_identity_must_belong_to_the_main_class_jar(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.jar(directory)
            self.assertEqual(subject.jar_identity(directory, VERSION, SOURCE, zipfile.ZipFile)["sourceCommit"], SOURCE)
            (directory / "sample.jar").unlink()
            self.jar(directory, "main.jar", identity=False)
            self.jar(directory, "dependency.jar", main=False)
            with self.assertRaises(ValueError):
                subject.jar_identity(directory, VERSION, SOURCE, zipfile.ZipFile)

    def test_installer_payload_cannot_substitute_an_old_source_with_same_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.jar(directory, source="b" * 40)
            with self.assertRaises(ValueError):
                subject.jar_identity(directory, VERSION, SOURCE, zipfile.ZipFile)

    def test_debian_data_only_tar_reader_finds_actual_application_jar(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.jar(directory)
            data = (directory / "sample.jar").read_bytes()
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode="w") as archive:
                member = tarfile.TarInfo("./opt/p2pkit-sample/lib/app/p2p-sample-desktop-ui-0.8.0-rc1.jar")
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            stream.seek(0)
            output = directory / "output"
            output.mkdir()
            subject.deb_payload(stream, output)
            self.assertEqual((output / "application.jar").read_bytes(), data)
            self.assertEqual(subject.jar_identity(output, VERSION, SOURCE, zipfile.ZipFile)["sourceCommit"], SOURCE)

    def test_debian_stream_limit_is_checked_before_accumulation(self):
        with mock.patch.object(subject, "STREAM_LIMIT", 8):
            reader = subject.LimitedReader(io.BytesIO(b"123456789"))
            self.assertEqual(reader.read(8), b"12345678")
            with self.assertRaises(ValueError):
                reader.read(1)

    def test_apk_raw_package_cannot_disagree_with_typed_value(self):
        raw = fixture.manifest()
        attribute = struct.pack("<IIIHBBI", 0xffffffff, 1, 2, 8, 0, 3, 2)
        changed = raw.replace(attribute, struct.pack("<IIIHBBI", 0xffffffff, 1, 6, 8, 0, 3, 2))
        self.assertNotEqual(raw, changed)
        with self.assertRaises(ValueError):
            subject.apk_manifest(changed)

    def test_dmg_failed_attach_always_attempts_detach_and_preserves_uncertain_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve() / "owned"
            directory.mkdir()
            with mock.patch.object(subject.tempfile, "mkdtemp", return_value=str(directory)), \
                    mock.patch.object(subject, "run", side_effect=ValueError("native failure")) as reader:
                with self.assertRaises(ValueError):
                    subject.inspect_native(Path("fixture.dmg"), "macos", VERSION, SOURCE, zipfile.ZipFile)
            self.assertEqual([x.args[0][1] for x in reader.call_args_list], ["attach", "detach"])
            self.assertTrue((directory / "mounted").is_dir())

    def test_msi_selected_file_must_really_use_compressed_cabinet(self):
        for flags, summary in (("16384", 0), ("", 2), ("0", 2), ("16384", 2)):
            subject.compressed_msi_file(flags, summary)
        for flags, summary in (("8192", 2), ("24576", 2), ("0", 0), ("", 0), ("-1", 2), ("garbage", 2)):
            with self.subTest(flags=flags, summary=summary), self.assertRaises(ValueError):
                subject.compressed_msi_file(flags, summary)

    def test_cabinet_payload_size_and_nonspanned_identity_before_extraction(self):
        name, content = b"AppFile\0", b"not-a-real-jar"
        file = struct.pack("<II4H", len(content), 0, 0, 0, 0, 0) + name
        data_offset = 44 + len(file)
        block = struct.pack("<IHH", 0, len(content), len(content)) + content
        header = struct.pack("<4s5I2B5H", b"MSCF", 0, data_offset + len(block), 0, 44, 0, 3, 1, 1, 1, 0, 0, 0)
        raw = header + struct.pack("<IHH", data_offset, 1, 0) + file + block
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic.cab"
            path.write_bytes(raw)
            subject.cabinet_member(path, "AppFile", len(content))
            for key, size in (("OtherFile", len(content)), ("appfile", len(content)), ("AppFile", 512 * 1024**2)):
                with self.assertRaises(ValueError):
                    subject.cabinet_member(path, key, size)
            path.write_bytes(raw[:30] + struct.pack("<H", 1) + raw[32:])
            with self.assertRaises(ValueError):
                subject.cabinet_member(path, "AppFile", len(content))

    def test_native_deb_timeout_retires_the_decompressor_group(self):
        process = mock.Mock(pid=123456, stdout=io.BytesIO(b""))
        process.wait.return_value = 0
        with mock.patch.object(subject.subprocess, "Popen", return_value=process) as popen, \
                mock.patch.object(subject.threading, "Timer") as timer, mock.patch.object(subject.os, "killpg") as kill:
            with self.assertRaises(ValueError), subject.native_stream(["synthetic-not-executed"]) as stream:
                timer.call_args.args[1]()
                self.assertEqual(stream.read(), b"")
            self.assertTrue(popen.call_args.kwargs["start_new_session"])
            self.assertEqual(kill.call_count, 2)
            self.assertTrue(all(x.args == (process.pid, subject.signal.SIGKILL) for x in kill.call_args_list))


if __name__ == "__main__":
    unittest.main(failfast=True)
