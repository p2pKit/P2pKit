#!/usr/bin/env python3
"""Synthetic, offline packager controls; never build or execute an application.

All Git/host identity observations are mocked. Native headers, class files and APK
contents are deliberately synthetic, not qualified binaries or hosted evidence.
TemporaryDirectory honors the caller's owned TMPDIR and cleans on every exit.
"""

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile


SPEC = importlib.util.spec_from_file_location("sample_app_packager", Path(__file__).resolve().parents[1] / "package-sample-apps.py")
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)
SHA, TREE = "a" * 40, "b" * 40


class PackageFixtures(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sample-app-packager-synthetic-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "checkout"
        self.root.mkdir()
        self.output = self.base / "p2pkit-sample-apps"
        self.identity = {"repository": subject.REPOSITORY, "commit": SHA, "tree": TREE, "platform": "linux",
                         "architecture": "x64", "event_name": "push", "ref": "refs/heads/main",
                         "run_id": "1", "run_attempt": "1", "job": "verify", "workflow_sha": SHA,
                         "workflow_ref": subject.REPOSITORY + "/.github/workflows/desktop-cross-host.yml@refs/heads/main",
                         "osRelease": "synthetic", "python": "synthetic", "translation": "NOT_APPLICABLE"}
        self.environment = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                            "GITHUB_REPOSITORY": subject.REPOSITORY, "GITHUB_SERVER_URL": "https://github.com",
                            "GITHUB_API_URL": "https://api.github.com", "GITHUB_WORKSPACE": str(self.root),
                            "RUNNER_TEMP": str(self.base), "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64"}
        for key, value in self.identity.items():
            if key in ("event_name", "ref", "run_id", "run_attempt", "job", "workflow_ref", "workflow_sha"):
                self.environment["GITHUB_" + key.upper()] = value
        self.environment["GITHUB_SHA"] = SHA

    def write(self, path, data=b"synthetic", mode=0o644):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)
        return path

    def observed_context(self, environment=None, dirty=b"", sha=SHA):
        def git(_root, *arguments):
            if arguments[0] == "status":
                return dirty
            return (TREE if arguments[-1] == "HEAD^{tree}" else sha).encode("ascii")
        with mock.patch.object(subject, "git", side_effect=git), mock.patch.object(subject.platform, "system", return_value="Linux"), \
                mock.patch.object(subject.platform, "machine", return_value="x86_64"):
            return subject.context(self.root, self.environment if environment is None else environment)

    def archive_fixture(self):
        source = self.base / "Synthetic App"
        self.write(source / "bin" / "launcher", b"not an executable", 0o755)
        self.write(source / "lib" / "payload", b"synthetic payload")
        self.write(source / "legal" / "LICENSE", b"synthetic license")
        self.write(source / "empty", b"")
        (source / "empty-directory").mkdir()
        (source / "bin" / "alias").symlink_to("../lib/payload")
        return source

    def native(self, path, system, arch="x64"):
        data = bytearray(128)
        if system == "linux":
            data[:6] = b"\x7fELF\x02\x01"
            data[18:20] = (62 if arch == "x64" else 183).to_bytes(2, "little")
        elif system == "windows":
            data[:2] = b"MZ"
            data[60:64] = (64).to_bytes(4, "little")
            data[64:68] = b"PE\0\0"
            data[68:70] = (0x8664 if arch == "x64" else 0xAA64).to_bytes(2, "little")
            data[88:90] = b"\x0b\x02"
        else:
            data[:4] = b"\xcf\xfa\xed\xfe"
            data[4:8] = (0x1000007 if arch == "x64" else 0x100000C).to_bytes(4, "little")
        return self.write(path, bytes(data), 0o755)

    def jar(self, path, main):
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(main, b"\xca\xfe\xba\xbeNOT_A_REAL_CLASS")

    def application_fixture(self, system):
        image = self.root / subject.IMAGE / ("P2pKit Sample.app" if system == "macos" else "P2pKit Sample")
        app, runtime, launcher, vm = {
            "linux": ("lib/app", "lib/runtime", "bin/P2pKit Sample", "lib/server/libjvm.so"),
            "windows": ("app", "runtime", "P2pKit Sample.exe", "bin/server/jvm.dll"),
            "macos": ("Contents/app", "Contents/runtime/Contents/Home", "Contents/MacOS/P2pKit Sample", "lib/server/libjvm.dylib"),
        }[system]
        self.native(image / launcher, system)
        self.native(image / runtime / vm, system)
        self.write(image / runtime / "release", b'JAVA_VERSION="17.0.1"\nOS_ARCH="amd64"\n')
        self.write(image / app / "P2pKit Sample.cfg", b"[Application]\napp.mainclass=dev.p2pkit.sample.desktop.ui.MainKt\n")
        self.jar(image / app / "sample.jar", "dev/p2pkit/sample/desktop/ui/MainKt.class")
        self.write(image / runtime / "legal" / "LICENSE", b"synthetic vendor license")
        cli = self.root / subject.CLI
        self.write(cli / "bin" / ("p2p-sample-desktop.bat" if system == "windows" else "p2p-sample-desktop"),
                   b"synthetic launcher dev.p2pkit.sample.desktop.MainKt", 0o755)
        self.jar(cli / "lib" / "sample.jar", "dev/p2pkit/sample/desktop/MainKt.class")
        for relative in subject.LICENSES.values():
            self.write(self.root / relative, b"synthetic public license/notice")
        return image, cli

    def android_fixture(self):
        directory = self.root / subject.APK
        directory.mkdir(parents=True)
        apk = directory / "sample-debug.apk"
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"synthetic manifest, not Android binary XML")
            archive.writestr("classes.dex", b"synthetic DEX, not executable")
        metadata = {"version": 3, "artifactType": {"type": "APK", "kind": "Directory"},
                    "applicationId": "dev.p2pkit.sample.android", "variantName": "debug", "elements": [
                        {"type": "SINGLE", "filters": [], "versionCode": 1, "versionName": "0.1.0", "outputFile": apk.name}]}
        (directory / "output-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        return directory, metadata

    def test_context_requires_exact_clean_source_and_native_identity(self):
        self.assertEqual(SHA, self.observed_context()["commit"])
        for kwargs in ({"dirty": b" M tracked-source"}, {"sha": "c" * 40}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.observed_context(**kwargs)
        mutations = {"GITHUB_ACTIONS": "false", "RUNNER_ENVIRONMENT": "self-hosted", "GITHUB_REPOSITORY": "other/repo",
                     "GITHUB_SERVER_URL": "https://example.invalid", "GITHUB_API_URL": "https://example.invalid",
                     "GITHUB_SHA": "bad", "GITHUB_RUN_ID": "0", "GITHUB_RUN_ATTEMPT": "1\n2", "RUNNER_ARCH": "ARM64",
                     "RUNNER_OS": "Windows", "GITHUB_WORKSPACE": str(self.base), "GITHUB_REF": "refs/tags/v1",
                     "GITHUB_WORKFLOW_REF": "other/repo/.github/workflows/workflow.yml@refs/heads/main"}
        for key, value in mutations.items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.observed_context({**self.environment, key: value})

    def test_context_admits_only_supported_pr_and_dispatch_refs(self):
        for event, ref in (("pull_request", "refs/pull/123/merge"), ("workflow_dispatch", "refs/heads/work/candidate")):
            self.assertEqual(event, self.observed_context({**self.environment, "GITHUB_EVENT_NAME": event,
                                                          "GITHUB_REF": ref})["event_name"])
        with self.assertRaises(ValueError):
            self.observed_context({**self.environment, "GITHUB_EVENT_NAME": "pull_request_target"})

    def test_mac_translation_probe_is_observed_and_never_faked_as_admission(self):
        environment = {**self.environment, "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64"}
        def git(_root, *arguments):
            return b"" if arguments[0] == "status" else (TREE if arguments[-1] == "HEAD^{tree}" else SHA).encode("ascii")
        with mock.patch.object(subject, "git", side_effect=git), \
                mock.patch.object(subject.platform, "system", return_value="Darwin"), \
                mock.patch.object(subject.platform, "machine", return_value="arm64"):
            for code, out, err in ((0, b"0\n", b""), (1, b"", b"")):
                probe = mock.Mock(returncode=code, stdout=out, stderr=err)
                with mock.patch.object(subject.subprocess, "run", return_value=probe) as runner:
                    self.assertIn(subject.context(self.root, environment)["translation"],
                                  ("NATIVE_0", "OPTIONAL_KEY_ABSENT_EXIT_1"))
                    self.assertEqual(["/usr/sbin/sysctl", "-in", "sysctl.proc_translated"], runner.call_args.args[0])
            for code, out, err in ((0, b"1\n", b""), (1, b"", b"permission denied"), (0, b"", b"")):
                with mock.patch.object(subject.subprocess, "run", return_value=mock.Mock(returncode=code, stdout=out, stderr=err)), \
                        self.assertRaisesRegex(ValueError, "Translated or indeterminate"):
                    subject.context(self.root, environment)

    def test_output_must_be_exact_new_owned_location(self):
        self.assertEqual(self.output, subject.output_path(str(self.output), self.environment))
        with self.assertRaises(ValueError):
            subject.output_path(str(self.base / "other"), self.environment)
        with mock.patch.object(subject, "context", return_value=self.identity):
            subject.prepare(self.root, self.output)
            with self.assertRaises(FileExistsError):
                subject.prepare(self.root, self.output)

    def test_prepare_rejects_existing_generated_root_and_linked_ancestor(self):
        generated = self.root / subject.IMAGE
        generated.mkdir(parents=True)
        with mock.patch.object(subject, "context", return_value=self.identity), self.assertRaises(ValueError):
            subject.prepare(self.root, self.output)
        generated.rmdir()
        build = self.root / "samples/p2p-sample-desktop-ui/build"
        shutil.rmtree(build)
        build.symlink_to(self.base, target_is_directory=True)
        with mock.patch.object(subject, "context", return_value=self.identity), self.assertRaises(ValueError):
            subject.prepare(self.root, self.output)
        self.assertFalse(self.output.exists())

    def test_archive_round_trip_preserves_bytes_modes_links_and_licenses(self):
        source = self.archive_fixture()
        entries = subject.inventory(source)
        for extension in (".zip", ".tar.gz"):
            with self.subTest(extension=extension):
                result = subject.archive_image(source, self.base / ("app" + extension), entries)
                self.assertEqual(entries, result["entries"])
                self.assertTrue(any(entry["path"] == "legal/LICENSE" for entry in entries))
                self.assertTrue(any(entry["type"] == "symlink" for entry in entries))
                self.assertEqual(subject.file_hash(self.base / result["file"])["sha256"], result["sha256"])

    def test_inventory_rejects_unsafe_links_special_files_empty_images_and_bounds(self):
        source = self.archive_fixture()
        link = source / "escape"
        for target in (str(self.base), "../outside", "."):
            link.symlink_to(target)
            try:
                with self.subTest(target=target), self.assertRaises((ValueError, FileNotFoundError)):
                    subject.inventory(source)
            finally:
                link.unlink()
        with mock.patch.object(subject, "MAX_FILES", 1), self.assertRaises(ValueError):
            subject.inventory(source)
        with mock.patch.object(subject, "MAX_TOTAL", 1), self.assertRaises(ValueError):
            subject.inventory(source)
        empty = self.base / "empty-image"
        empty.mkdir()
        with self.assertRaises(ValueError):
            subject.inventory(empty)
        with self.assertRaises(ValueError):
            subject.file_hash(source / "lib/payload", limit=1)
        # No FIFO creation/blocking I/O: mock only this private entry's lstat.
        regular = source / "lib/payload"
        original = Path.lstat
        def special(path):
            info = original(path)
            if path == regular:
                return mock.Mock(st_mode=stat.S_IFIFO | 0o644, st_file_attributes=0)
            return info
        with mock.patch.object(Path, "lstat", special), self.assertRaisesRegex(ValueError, "Special"):
            subject.inventory(source)

    def test_portable_path_rejection(self):
        for name in ("../outside", "/absolute", "a//b", "a\\b", "a:b", "a/./b", "a\nfile", "CON", "file.", "file "):
            with self.subTest(name=name), self.assertRaises(ValueError):
                subject.safe_name(name)

    def test_archive_rejects_changed_source(self):
        source = self.archive_fixture()
        entries = subject.inventory(source)
        (source / "lib/payload").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            subject.archive_image(source, self.base / "changed.zip", entries)

    def test_archive_verifier_rejects_payload_mode_link_and_member_tampering(self):
        source = self.archive_fixture()
        entries = subject.inventory(source)
        for extension in (".zip", ".tar.gz"):
            original = self.base / ("original" + extension)
            subject.archive_image(source, original, entries)
            for mutation in ("payload", "mode", "link", "path", "missing"):
                altered = self.base / (mutation + extension)
                if extension == ".zip":
                    with zipfile.ZipFile(original) as before, zipfile.ZipFile(altered, "w") as after:
                        for entry in before.infolist():
                            data = before.read(entry)
                            if entry.filename.endswith("lib/payload"):
                                if mutation == "payload":
                                    data = b"changed payload"
                                elif mutation == "mode":
                                    entry.external_attr ^= 0o100 << 16
                                elif mutation == "path":
                                    entry.filename = "../escape"
                                elif mutation == "missing":
                                    continue
                            if mutation == "link" and stat.S_ISLNK(entry.external_attr >> 16):
                                data = b"../different"
                            after.writestr(entry, data)
                else:
                    with tarfile.open(original, "r:gz") as before, tarfile.open(altered, "w:gz") as after:
                        for entry in before:
                            data = before.extractfile(entry).read() if entry.isfile() else b""
                            if entry.name.endswith("lib/payload"):
                                if mutation == "payload":
                                    data = b"changed payload"
                                    entry.size = len(data)
                                elif mutation == "mode":
                                    entry.mode ^= 0o100
                                elif mutation == "path":
                                    entry.name = "../escape"
                                elif mutation == "missing":
                                    continue
                            if mutation == "link" and entry.issym():
                                entry.linkname = "../different"
                            after.addfile(entry, io.BytesIO(data) if entry.isfile() else None)
                with self.subTest(extension=extension, mutation=mutation), self.assertRaises(ValueError):
                    subject.verify_archive(altered, entries, source.name)

    def test_copy_is_bounded_for_growth_and_truncation(self):
        for data, size in ((b"longer", 1), (b"short", 10)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                subject.copy_stream(io.BytesIO(data), io.BytesIO(), size)

    def test_zip_preflight_rejects_zip64_override_before_zipfile(self):
        path = self.base / "zip64.jar"
        self.jar(path, "Main.class")
        raw = path.read_bytes()
        end = len(raw) - 22
        central_bytes, central_offset = struct.unpack_from("<LL", raw, end + 12)
        # Tiny fixture: classic EOCD values are ordinary, but Python otherwise
        # replaces them from this ZIP64 record, before allocating ZipInfo objects.
        extended = struct.pack("<4sQHHIIQQQQ", b"PK\x06\x06", 44, 45, 45, 0, 0,
                               subject.MAX_FILES + 1, subject.MAX_FILES + 1,
                               central_bytes, central_offset)
        locator = struct.pack("<4sIQI", b"PK\x06\x07", 0, end, 1)
        path.write_bytes(raw[:end] + extended + locator + raw[end:])
        with mock.patch.object(subject.zipfile, "ZipFile", side_effect=AssertionError("ZipFile reached before preflight")), \
                self.assertRaisesRegex(ValueError, "ZIP64"):
            subject.zip_input(path)

    def test_zip_preflight_counts_actual_records_before_zipfile(self):
        path = self.base / "false-count.jar"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("first", b"one")
            archive.writestr("second", b"two")
        raw = path.read_bytes()
        for count in (0, 1, 3):
            changed = bytearray(raw)
            struct.pack_into("<HH", changed, len(raw) - 22 + 8, count, count)
            path.write_bytes(changed)
            with self.subTest(count=count), \
                    mock.patch.object(subject.zipfile, "ZipFile", side_effect=AssertionError("ZipFile reached before preflight")), \
                    self.assertRaises(ValueError):
                subject.zip_input(path)

    def test_zip_preflight_validates_record_extents_and_no_zip64_entries(self):
        path = self.base / "central.jar"
        info = zipfile.ZipInfo("Main.class")
        info.extra = struct.pack("<HH4s", 0xCAFE, 4, b"test")
        with zipfile.ZipFile(path, "w") as archive:
            archive.comment = b"ordinary archive comment"
            archive.writestr(info, b"synthetic class")
        raw = path.read_bytes()
        end = raw.rfind(b"PK\x05\x06")
        central_bytes, central = struct.unpack_from("<LL", raw, end + 12)
        with subject.zip_input(path) as archive:
            self.assertEqual(["Main.class"], archive.namelist())
        mutations = (
            (end + 12, "<L", central_bytes - 1),
            (end + 16, "<L", central - 1),
            (central, "<4s", b"FAIL"),
            (central + 28, "<H", 65535),
            (central + 34, "<H", 1),
            (central + 20, "<L", 0xFFFFFFFF),
            (central + 24, "<L", 0xFFFFFFFF),
            (central + 42, "<L", 0xFFFFFFFF),
            (central + 46 + len(info.filename), "<H", 1),
            (central + 46 + len(info.filename) + 2, "<H", 65535),
        )
        for offset, pattern, value in mutations:
            changed = bytearray(raw)
            struct.pack_into(pattern, changed, offset, value)
            path.write_bytes(changed)
            with self.subTest(offset=offset, value=value), \
                    mock.patch.object(subject.zipfile, "ZipFile", side_effect=AssertionError("ZipFile reached before preflight")), \
                    self.assertRaises(ValueError):
                subject.zip_input(path)

    def test_native_headers_reject_other_architecture_and_truncation(self):
        for system in ("linux", "windows", "macos"):
            for arch in ("x64", "arm64"):
                path = self.native(self.base / (system + arch), system, arch)
                self.assertEqual([arch], subject.native_architectures(path, system))
            bad = self.write(self.base / (system + "-bad"), b"NOT A NATIVE BINARY")
            with self.subTest(system=system), self.assertRaises(ValueError):
                subject.native_architectures(bad, system)

    def test_fat_macho_requires_real_matching_slice_headers(self):
        path = self.base / "fat"
        thin_x64 = self.native(self.base / "thin-x64", "macos").read_bytes()
        thin_arm64 = self.native(self.base / "thin-arm64", "macos", "arm64").read_bytes()
        header = struct.pack(">2I", 0xCAFEBABE, 2) + struct.pack(">5I", 0x1000007, 3, 64, 128, 0) + \
            struct.pack(">5I", 0x100000C, 0, 192, 128, 0)
        path.write_bytes(header.ljust(64, b"\0") + thin_x64 + thin_arm64)
        self.assertEqual(["arm64", "x64"], subject.native_architectures(path, "macos"))
        path.write_bytes(header.ljust(64, b"\0") + thin_x64 + thin_x64)
        with self.assertRaises(ValueError):
            subject.native_architectures(path, "macos")

    def test_layout_accepts_stripped_java_but_rejects_missing_vm_or_main_class(self):
        image, cli = self.application_fixture("linux")
        self.assertIsNone(subject.desktop_layout(image, cli, self.identity)["runtimeJava"])
        vm = image / "lib/runtime/lib/server/libjvm.so"
        self.native(vm, "linux", "arm64")
        with self.assertRaisesRegex(ValueError, "architecture"):
            subject.desktop_layout(image, cli, self.identity)
        vm.unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            subject.desktop_layout(image, cli, self.identity)
        self.native(vm, "linux")
        self.jar(image / "lib/app/sample.jar", "Wrong.class")
        with self.assertRaisesRegex(ValueError, "main class"):
            subject.desktop_layout(image, cli, self.identity)

    def test_android_metadata_is_actual_single_debug_output_not_path_guesses(self):
        directory, metadata = self.android_fixture()
        destination = self.base / "android"
        destination.mkdir()
        result = subject.android_artifact(self.root, destination)
        self.assertEqual("sample-debug.apk", result["artifact"]["file"])
        self.assertEqual("debug", result["agpMetadata"]["variant"])
        self.assertIn("signer identity not verified", result["apkInspection"])
        (destination / "sample-debug.apk").unlink()
        mutations = [("outputFile", "../outside.apk"), ("outputFile", "subdir/sample.apk"), ("outputFile", "missing.apk"),
                     ("filters", [{"filterType": "ABI", "value": "arm64-v8a"}]), ("versionCode", True), ("type", "SPLIT")]
        for key, value in mutations:
            changed = copy.deepcopy(metadata)
            changed["elements"][0][key] = value
            (directory / "output-metadata.json").write_text(json.dumps(changed), encoding="utf-8")
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                subject.android_artifact(self.root, destination)

    def test_android_rejects_ambiguous_outputs_and_duplicate_metadata(self):
        directory, metadata = self.android_fixture()
        destination = self.base / "android"
        destination.mkdir()
        self.write(directory / "extra.apk")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            subject.android_artifact(self.root, destination)
        (directory / "extra.apk").unlink()
        (directory / "output-metadata.json").write_text('{"elements":[],"elements":[]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            subject.android_artifact(self.root, destination)

    def test_android_rejects_corrupt_crc(self):
        directory, _ = self.android_fixture()
        apk = directory / "sample-debug.apk"
        apk.write_bytes(apk.read_bytes().replace(b"synthetic DEX", b"corrupted DEX", 1))
        destination = self.base / "android"
        destination.mkdir()
        with self.assertRaises((ValueError, zipfile.BadZipFile)):
            subject.android_artifact(self.root, destination)

    def test_full_synthetic_package_has_separate_scoped_delivery_and_checksums(self):
        for system in ("linux", "windows", "macos"):
            with self.subTest(system=system):
                identity = {**self.identity, "platform": system}
                with mock.patch.object(subject, "context", return_value=identity):
                    subject.prepare(self.root, self.output)
                    self.application_fixture(system)
                    if system == "linux":
                        self.android_fixture()
                    subject.package(self.root, self.output)
                    self.assertTrue((self.output / ".complete.json").is_file())
                    self.assertEqual(system == "linux", (self.output / "android").is_dir())
                    self.assertFalse((self.output / ".packaging").exists())
                    manifest = subject.read_json(self.output / "desktop/manifest.json")
                    self.assertEqual("NOT_PERFORMED", manifest["scope"]["appLaunch"])
                    self.assertEqual(TREE, manifest["sourceAndRun"]["tree"])
                    self.assertEqual(2, len(manifest["artifacts"]))
                    for line in (self.output / "desktop/checksums.sha256").read_text("utf-8").splitlines():
                        digest, relative = line.split("  ", 1)
                        self.assertEqual(digest, hashlib.sha256((self.output / "desktop" / relative).read_bytes()).hexdigest())
                    with self.assertRaises(ValueError):
                        subject.package(self.root, self.output)
                shutil.rmtree(self.output)
                shutil.rmtree(self.root)
                self.root.mkdir()

    def test_package_rejects_changed_source_and_missing_output(self):
        with mock.patch.object(subject, "context", return_value=self.identity):
            subject.prepare(self.root, self.output)
            with self.assertRaises(FileNotFoundError):
                subject.package(self.root, self.output)
        with mock.patch.object(subject, "context", return_value={**self.identity, "tree": "c" * 40}), \
                self.assertRaisesRegex(ValueError, "Prepare identity"):
            subject.package(self.root, self.output)

    def test_failure_before_delivery_removes_only_own_packaging_stage(self):
        sentinel = self.write(self.base / "outside-sentinel", b"preserve")
        with mock.patch.object(subject, "context", return_value=self.identity):
            subject.prepare(self.root, self.output)
            self.application_fixture("linux")
            self.android_fixture()
            with mock.patch.object(subject, "finish_manifest", side_effect=ValueError("injected failure")), \
                    self.assertRaisesRegex(ValueError, "injected failure"):
                subject.package(self.root, self.output)
        self.assertEqual({".prepare.json"}, {path.name for path in self.output.iterdir()})
        self.assertEqual(b"preserve", sentinel.read_bytes())
        self.assertTrue((self.root / subject.IMAGE).is_dir())

    def test_final_source_drift_prevents_delivery_after_archives_were_created(self):
        with mock.patch.object(subject, "context", return_value=self.identity):
            subject.prepare(self.root, self.output)
        self.application_fixture("linux")
        self.android_fixture()
        with mock.patch.object(subject, "context", side_effect=[self.identity, {**self.identity, "tree": "c" * 40}]), \
                self.assertRaisesRegex(ValueError, "Source/run changed"):
            subject.package(self.root, self.output)
        self.assertEqual({".prepare.json"}, {path.name for path in self.output.iterdir()})


if __name__ == "__main__":
    unittest.main(verbosity=2)
