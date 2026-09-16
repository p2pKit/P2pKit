#!/usr/bin/env python3
"""Offline adversarial controls, NOT native/compiler/network evidence.

Every command is an in-memory callback. Tiny synthetic ZIP/ar/Mach-O files test
parsers, command construction and fail-closed orchestration, never native code.
No dependency, retained binary, Xcode invocation, simulator or socket is used.
"""
from __future__ import annotations

import ast
import ctypes
from dataclasses import replace
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import urllib.request
import warnings
import zipfile

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1] / "hosted_apple_link.py"
SPEC = importlib.util.spec_from_file_location("hosted_apple_link_controls", SOURCE)
app = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = app
with mock.patch.object(subprocess, "Popen", side_effect=AssertionError("No subprocess in offline controls")), \
        mock.patch.object(ctypes, "CDLL", side_effect=AssertionError("No native loader in offline controls")):
    SPEC.loader.exec_module(app)
REAL_TARGETS = app.TARGETS


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def native_object(target, *, filetype=1, sdk=(26 << 16) | (2 << 8), platform=None, cpu=None,
                  subtype=None, minimum=14 << 16, extra=b"", extra_count=0):
    build = struct.pack("<6I", 0x32, 24, target.platform if platform is None else platform, minimum, sdk, 0)
    return struct.pack("<8I", 0xFEEDFACF, target.cpu if cpu is None else cpu,
                       target.subtype if subtype is None else subtype, filetype, 1 + extra_count,
                       len(build) + len(extra), 0, 0) + build + extra


def member(name, raw, *, extended=True):
    if extended:
        raw = name.encode("ascii") + raw
        label = "#1/" + str(len(name))
    else:
        label = name + "/"
    header = (label.ljust(16) + "0".ljust(12) + "0".ljust(6) + "0".ljust(6) + "100644".ljust(8) +
              str(len(raw)).ljust(10) + "`\n").encode("ascii")
    assert len(header) == 60
    return header + raw + (b"\n" if len(raw) % 2 else b"")


def archive_bytes(target):
    return b"!<arch>\n" + member("__.SYMDEF", b"SYNTHETIC TABLE") + member("DwcFixture.swift.o", native_object(target))


def zip_bytes(target, archive=None, *, extras=(), manifest=None, archive_name=None, archive_mode=stat.S_IFREG | 0o644):
    if archive is None:
        archive = archive_bytes(target)
    if manifest is None:
        manifest = ("builtins_platform=NATIVE\ninterop=true\nnative_targets=" + target.native +
                    "\nstaticLibraries=libDwcCryptoKitInterop.a\n").encode()
    output = io.BytesIO()
    with warnings.catch_warnings(), zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        warnings.simplefilter("ignore", UserWarning)  # Deliberately duplicated hostile ZIP fixtures.
        for name, raw, mode in [("default/manifest", manifest, stat.S_IFREG | 0o644),
                                (archive_name or target.entry, archive, archive_mode), *extras]:
            info = zipfile.ZipInfo(name)
            info.create_system, info.external_attr, info.compress_type = 3, mode << 16, zipfile.ZIP_DEFLATED
            zipped.writestr(info, raw)
    return output.getvalue()


def repin(target, raw, native=None):
    value = replace(target, size=len(raw), sha256=digest(raw))
    return replace(value, archive_size=len(native), archive_sha256=digest(native)) if native is not None else value


def metadata_bytes(targets):
    return ('<verification-metadata xmlns="' + app.NAMESPACE + '"><components>' + ''.join(
        '<component group="dev.whyoleg.cryptography" name="' + target.component + '" version="0.6.0">'
        '<artifact name="' + target.filename + '"><sha256 value="' + target.sha256 + '"/></artifact></component>'
        for target in targets) + '</components></verification-metadata>').encode()


def file_bytes(path, raw):
    path.write_bytes(raw)
    path.chmod(0o600)


class Fixture(unittest.TestCase):
    def setUp(self):
        for module, name in ((subprocess, "Popen"), (subprocess, "run"), (socket, "socket"),
                             (socket, "create_connection"), (socket, "getaddrinfo"), (ctypes, "CDLL"),
                             (urllib.request, "urlopen"), (os, "system")):
            guard = mock.patch.object(module, name, side_effect=AssertionError("No native/process/network in offline controls"))
            guard.start()
            self.addCleanup(guard.stop)
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-apple-link-offline-", dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root, self.state, self.xcode = self.base / "source", self.base / "state", self.base / "Xcode_16.2.app/Contents/Developer"
        for path in (self.root, self.state, self.xcode):
            path.mkdir(parents=True, mode=0o700)
        (self.state / "commands").mkdir(mode=0o700)
        self.directory = self.state / "apple-link"
        header = self.root / app.HEADER
        header.parent.mkdir(parents=True, mode=0o700)
        # Source-shaped C text only; no compiler is ever allowed to read it.
        file_bytes(header, b"\n".join(("static inline int " + name + "(void) { return 0; }").encode()
                                    for name in app.BRIDGE_FUNCTIONS) + b"\n")
        self.payloads, self.targets = {}, []
        for original in REAL_TARGETS:
            native = archive_bytes(original)
            raw = zip_bytes(original, native)
            target = repin(original, raw, native)
            self.targets.append(target)
            self.payloads[target.name] = raw
        self.targets = tuple(self.targets)
        target_patch, xcode_patch = mock.patch.object(app, "TARGETS", self.targets), mock.patch.object(app, "XCODE", self.xcode)
        target_patch.start()
        xcode_patch.start()
        self.addCleanup(target_patch.stop)
        self.addCleanup(xcode_patch.stop)
        metadata = self.root / app.METADATA
        metadata.parent.mkdir(parents=True, mode=0o700)
        file_bytes(metadata, metadata_bytes(self.targets))
        self.toolchain = self.xcode / "Toolchains/XcodeDefault.xctoolchain/usr"
        self.tools = {}
        for name in ("clang", "ld", "swift"):
            path = self.toolchain / "bin" / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            file_bytes(path, b"OFFLINE PLACEHOLDER, NOT EXECUTABLE CONTENT\n")
            path.chmod(0o700)
            self.tools[name] = path
        self.sdks = {}
        for sdk, platform in (("iphoneos", "iPhoneOS"), ("iphonesimulator", "iPhoneSimulator")):
            path = self.xcode / "Platforms" / (platform + ".platform") / "Developer/SDKs" / (platform + "18.2.sdk")
            path.mkdir(parents=True, mode=0o700)
            self.sdks[sdk] = path
            for lib in (path / "usr/lib/swift/libswiftCore.tbd", self.toolchain / "lib/swift" / sdk / "libswiftCompatibility56.a"):
                lib.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                file_bytes(lib, b"OFFLINE INVENTORY PLACEHOLDER\n")
        self.calls = []
        self.hook = lambda label, argv, result: None
        self.output = lambda label, value: value

    def command(self, label, argv, seconds=120):
        self.calls.append((label, list(argv), seconds))
        stdout, stderr = b"", b""
        if label == "apple-link-xcode-version":
            stdout = app.XCODE_VERSION.encode()
        elif label.startswith("apple-link-find-"):
            stdout = (str(self.tools[argv[-1]]) + "\n").encode()
        elif label == "apple-link-clang-version":
            stdout = b"Apple clang version 16.0.0 (OFFLINE MODEL)\n"
        elif label == "apple-link-linker-version":
            stderr = b"@(#)PROGRAM:ld PROJECT:ld-OFFLINE_MODEL\n"
        elif label.startswith("apple-link-sdk-version-"):
            stdout = b"18.2\n"
        elif label.startswith("apple-link-sdk-"):
            stdout = (str(self.sdks[argv[2]]) + "\n").encode()
        elif label == "apple-link-curl-version":
            stdout = b"curl 8.7.1 (OFFLINE MODEL)\n"
        elif label.startswith("apple-link-fetch-"):
            target = next(target for target in self.targets if target.url == argv[-1])
            file_bytes(Path(argv[argv.index("--output") + 1]), self.payloads[target.name])
            stdout = ("200\n" + str(target.size) + "\n" + target.url + "\n").encode()
        elif label.startswith(("apple-link-compile-", "apple-link-link-")):
            target = next(target for target in self.targets if target.triple == argv[argv.index("-target") + 1])
            kind = 1 if "-c" in argv else 2
            file_bytes(Path(argv[argv.index("-o") + 1]), native_object(target, filetype=kind, sdk=(18 << 16) | (2 << 8)))
        else:
            self.fail("Unmodeled command: " + repr(argv))
        stdout = self.output(label, stdout)
        directory = self.state / "commands" / str(len(self.calls))
        directory.mkdir(mode=0o700)
        for name, raw in (("stdout", stdout), ("stderr", stderr)):
            file_bytes(directory / (name + ".log"), raw)
        row = {"argv": list(argv), "timeoutSeconds": seconds, "launchAttempted": True,
               "waitExitCode": 0, "exitAfterDrain": 0, "errors": [],
               "drains": [{"stage": "command-final", "survivors": [], "error": None}],
               "ownership": {"backend": "darwin-libproc-audit-token", "discoveryErrors": []},
               "streams": {name: {"observedBytes": len(raw), "retainedBytes": len(raw), "truncated": False}
                           for name, raw in (("stdout", stdout), ("stderr", stderr))}}
        result = SimpleNamespace(row=row, directory=directory, text=lambda: stdout.decode())
        self.hook(label, argv, result)
        return result

    def run_admission(self):
        return app.admit(self.root, self.directory, self.command)

    def hold(self, message=None):
        with self.assertRaises(Exception) as caught:
            self.run_admission()
        if message:
            self.assertIn(message, str(caught.exception))
        if (self.directory / "result.json").exists():
            self.assertEqual(json.loads((self.directory / "result.json").read_text())["status"], "HOLD")
        return caught.exception

    def no_fetches(self):
        self.assertFalse(any("-fetch-" in label for label, _, _ in self.calls))

    def zip_reject(self, **kwargs):
        target = self.targets[0]
        raw = zip_bytes(target, **kwargs)
        with self.assertRaises((ValueError, zipfile.BadZipFile)):
            app.unpack(raw, repin(target, raw))

    def archive_reject(self, raw, message=None):
        target = replace(self.targets[0], archive_size=len(raw), archive_sha256=digest(raw))
        with self.assertRaises(ValueError) as caught:
            app.inspect_archive(raw, target)
        if message:
            self.assertIn(message, str(caught.exception))


class OrchestrationTests(Fixture):
    def test_three_actual_model_products_are_retained_and_marked_not_executed(self):
        result = self.run_admission()
        self.assertEqual(result["status"], "ADMITTED_LINK_ONLY")
        self.assertEqual(result["scope"], app.SCOPE)
        self.assertEqual(result["fetchedBytes"], sum(target.size for target in self.targets))
        self.assertEqual(len(result["targets"]), 3)
        self.assertEqual(result, json.loads((self.directory / "result.json").read_text()))
        for name in ("runtimeExecuted", "writerExecuted", "physicalDeviceEvidence"):
            self.assertIs(result[name], False)
        for target, row in zip(self.targets, result["targets"]):
            self.assertEqual(row["status"], "LINKED_NOT_EXECUTED")
            self.assertEqual(row["executable"]["filetype"], 2)
            self.assertEqual(row["executable"]["platform"], target.platform)
            self.assertEqual((self.directory / target.name / target.filename).read_bytes(), self.payloads[target.name])
            self.assertEqual((self.directory / target.name / "libDwcCryptoKitInterop.a").read_bytes(), archive_bytes(target))

    def test_commands_force_load_whole_archives_with_strict_real_final_links(self):
        self.run_admission()
        links = [(argv, seconds) for label, argv, seconds in self.calls if label.startswith("apple-link-link-")]
        self.assertEqual(len(links), 3)
        for (argv, seconds), target in zip(links, self.targets):
            self.assertEqual(seconds, 120)
            self.assertIn("-force_load", argv)
            self.assertIn(str(self.directory / target.name / "libDwcCryptoKitInterop.a"), argv)
            self.assertIn("-fatal_warnings", argv)
            self.assertIn("-fuse-ld=" + str(self.tools["ld"]), argv)
            self.assertIn("-L" + str(self.sdks[target.sdk] / "usr/lib/swift"), argv)
            for forbidden in ("-r", "-c", "-undefined", "dynamic_lookup", "-w", "-weak_library"):
                self.assertNotIn(forbidden, argv)

    def test_compilation_binds_current_header_all_helpers_and_all_three_targets(self):
        self.run_admission()
        source = (self.directory / "bridge.m").read_text()
        self.assertIn('#include "p2pkit_nw.h"', source)
        for name in app.BRIDGE_FUNCTIONS:
            self.assertIn(" = &" + name + ";", source)
        compiles = [argv for label, argv, _ in self.calls if "-compile-" in label]
        self.assertEqual({argv[argv.index("-target") + 1] for argv in compiles}, {target.triple for target in self.targets})
        self.assertTrue(all("-Werror" in argv and "-fobjc-arc" in argv and "-fblocks" in argv for argv in compiles))
        self.assertTrue(all(str((self.root / app.HEADER).parent) in argv for argv in compiles))

    def test_downloads_are_only_three_fixed_urls_with_no_retry_redirect_or_config(self):
        self.run_admission()
        fetches = [(argv, seconds) for label, argv, seconds in self.calls if "-fetch-" in label]
        self.assertEqual([argv[-1] for argv, _ in fetches], [target.url for target in self.targets])
        for argv, seconds in fetches:
            self.assertEqual(argv[:2], ["/usr/bin/curl", "--disable"])
            self.assertEqual(seconds, 90)
            for flag, value in (("--proto", "=https"), ("--max-filesize", "131072"), ("--retry", "0"),
                                ("--max-redirs", "0"), ("--max-time", "60"), ("--proxy", "")):
                self.assertEqual(argv[argv.index(flag) + 1], value)
            self.assertNotIn("--location", argv)
            self.assertNotIn("--insecure", argv)

    def test_admission_has_no_subprocess_network_thread_or_standalone_cli_path(self):
        document = ast.parse(SOURCE.read_text())
        imports = {row.module.split(".")[0] for row in ast.walk(document) if isinstance(row, ast.ImportFrom) and row.module}
        imports.update(alias.name.split(".")[0] for row in ast.walk(document) if isinstance(row, ast.Import) for alias in row.names)
        self.assertFalse(imports & {"subprocess", "socket", "urllib", "requests", "ctypes", "threading", "argparse"})
        self.assertNotIn('__name__ == "__main__"', SOURCE.read_text())
        self.run_admission()
        self.assertTrue(all(not any(word in " ".join(argv).lower() for word in ("gradlew", "konanc", "simctl", "codesign"))
                            for _, argv, _ in self.calls))

    def test_callback_exception_is_hold_and_does_not_launch_next_stage(self):
        def hook(label, argv, result):
            if label.startswith("apple-link-link-"):
                raise RuntimeError("synthetic native retirement unavailable")
        self.hook = hook
        self.hold("retirement unavailable")
        self.assertEqual(sum("-fetch-" in label for label, _, _ in self.calls), 1)
        self.assertTrue((self.directory / self.targets[0].name / "link-admission").exists())

    def test_interrupt_retains_hold_and_original_files(self):
        def hook(label, argv, result):
            if label.startswith("apple-link-compile-"):
                raise KeyboardInterrupt("synthetic cancellation")
        self.hook = hook
        with self.assertRaises(KeyboardInterrupt):
            self.run_admission()
        self.assertEqual(json.loads((self.directory / "result.json").read_text())["status"], "HOLD")
        self.assertTrue((self.directory / self.targets[0].name / "libDwcCryptoKitInterop.a").exists())

    def test_changed_source_after_successful_links_cannot_admit(self):
        def hook(label, argv, result):
            if label == "apple-link-link-iosX64":
                with (self.root / app.HEADER).open("ab") as stream:
                    stream.write(b"\n// changed\n")
        self.hook = hook
        self.hold("source input changed")

    def test_unknown_bridge_helper_is_rejected_before_commands(self):
        with (self.root / app.HEADER).open("ab") as stream:
            stream.write(b"static inline int p2pkit_new_helper(void) { return 0; }\n")
        self.hold("helper inventory changed")
        self.assertFalse(self.calls)

    def test_toolchain_and_sdk_inventory_precede_any_dependency_fetch(self):
        self.run_admission()
        labels = [label for label, _, _ in self.calls]
        first = next(index for index, label in enumerate(labels) if "-fetch-" in label)
        for label in ("apple-link-sdk-iphoneos", "apple-link-sdk-iphonesimulator", "apple-link-curl-version"):
            self.assertLess(labels.index(label), first)


class InputAndHostTests(Fixture):
    def test_urls_use_published_module_urls_not_gradle_logical_cache_names(self):
        expected = (
            "https://repo.maven.apache.org/maven2/dev/whyoleg/cryptography/cryptography-provider-cryptokit-iosarm64/0.6.0/"
            "cryptography-provider-cryptokit-iosarm64-0.6.0-cinterop-swiftInteropDwcCryptoKitInterop.klib",
            "https://repo.maven.apache.org/maven2/dev/whyoleg/cryptography/cryptography-provider-cryptokit-iossimulatorarm64/0.6.0/"
            "cryptography-provider-cryptokit-iossimulatorarm64-0.6.0-cinterop-swiftInteropDwcCryptoKitInterop.klib",
            "https://repo.maven.apache.org/maven2/dev/whyoleg/cryptography/cryptography-provider-cryptokit-iosx64/0.6.0/"
            "cryptography-provider-cryptokit-iosx64-0.6.0-cinterop-swiftInteropDwcCryptoKitInterop.klib",
        )
        self.assertEqual(tuple(target.url for target in REAL_TARGETS), expected)
        self.assertTrue(all(not target.url.endswith(target.filename) for target in REAL_TARGETS))

    def test_real_three_pins_match_current_repository_metadata_without_download(self):
        with mock.patch.object(app, "TARGETS", REAL_TARGETS):
            app.check_pins((SOURCE.parents[1] / app.METADATA).read_bytes())
        self.assertEqual(sum(target.size for target in REAL_TARGETS), 292198)
        self.assertTrue(all(target.size < app.FETCH_LIMIT for target in REAL_TARGETS))

    def test_pin_change_blocks_every_command(self):
        path = self.root / app.METADATA
        file_bytes(path, path.read_bytes().replace(self.targets[0].sha256.encode(), b"a" * 64))
        self.hold("pin changed")
        self.assertFalse(self.calls)

    def test_duplicate_component_or_artifact_or_pin_is_rejected(self):
        raw = metadata_bytes(self.targets)
        for suffix in (b"</components>", b"</component>", b"</artifact>"):
            if suffix == b"</components>":
                insertion = raw[raw.index(b"<component "):raw.index(b"</component>") + len(b"</component>")]
            elif suffix == b"</component>":
                insertion = raw[raw.index(b"<artifact "):raw.index(b"</artifact>") + len(b"</artifact>")]
            else:
                insertion = ('<sha256 value="' + self.targets[0].sha256 + '"/>').encode()
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                app.check_pins(raw.replace(suffix, insertion + suffix, 1))

    def test_xml_entities_or_namespace_change_are_rejected(self):
        raw = metadata_bytes(self.targets)
        for value in (b'<!DOCTYPE x [<!ENTITY e "x">]>' + raw, raw.replace(app.NAMESPACE.encode(), b"urn:other")):
            with self.subTest(value=value[:30]), self.assertRaises(ValueError):
                app.check_pins(value)

    def test_xcode_build_mismatch_stops_before_fetch(self):
        self.output = lambda label, value: b"Xcode 16.2\nBuild version WRONG\n" if label == "apple-link-xcode-version" else value
        self.hold("build differs")
        self.no_fetches()

    def test_installed_sdk_version_mismatch_stops_before_fetch(self):
        self.output = lambda label, value: b"26.2\n" if label.startswith("apple-link-sdk-version-") else value
        self.hold("SDK version differs")
        self.no_fetches()

    def test_missing_installed_sdk_stops_before_fetch(self):
        shutil.rmtree(self.sdks["iphoneos"])
        self.hold()
        self.no_fetches()

    def test_sdk_escape_is_not_accepted_as_the_selected_installation(self):
        self.output = lambda label, value: (str(self.state) + "\n").encode() if label == "apple-link-sdk-iphoneos" else value
        self.hold("escapes selected")
        self.no_fetches()

    def test_wrong_sdk_platform_path_is_rejected(self):
        self.output = lambda label, value: (str(self.sdks["iphonesimulator"]) + "\n").encode() if label == "apple-link-sdk-iphoneos" else value
        self.hold("platform path differs")
        self.no_fetches()

    def test_canonical_sdk_symlink_inside_selected_xcode_is_allowed(self):
        alias = self.sdks["iphoneos"].parent / "iPhoneOS.sdk"
        alias.symlink_to(self.sdks["iphoneos"].name, target_is_directory=True)
        self.output = lambda label, value: (str(alias) + "\n").encode() if label == "apple-link-sdk-iphoneos" else value
        result = self.run_admission()
        self.assertEqual(result["installed"]["sdks"]["iphoneos"]["path"], str(self.sdks["iphoneos"]))

    def test_noncanonical_xcode_installation_is_rejected(self):
        alias = self.base / "XcodeAlias"
        alias.symlink_to(self.xcode, target_is_directory=True)
        with mock.patch.object(app, "XCODE", alias):
            self.hold("symlink")
        self.no_fetches()

    def test_wrong_or_nonexecutable_tool_is_rejected(self):
        self.tools["clang"].chmod(0o600)
        self.hold("not executable")
        self.no_fetches()

    def test_tool_outside_selected_xcode_is_rejected(self):
        self.output = lambda label, value: b"/usr/bin/true\n" if label == "apple-link-find-clang" else value
        self.hold("escapes selected")
        self.no_fetches()

    def test_empty_swift_support_directory_stops_before_fetch(self):
        (self.sdks["iphoneos"] / "usr/lib/swift/libswiftCore.tbd").unlink()
        self.hold("inventory is empty")
        self.no_fetches()

    def test_swift_support_symlink_escape_stops_before_fetch(self):
        outside = self.state / "foreign.tbd"
        file_bytes(outside, b"MODEL")
        path = self.sdks["iphoneos"] / "usr/lib/swift/libswiftCore.tbd"
        path.unlink()
        path.symlink_to(outside)
        self.hold("escapes selected")
        self.no_fetches()

    def test_old_curl_cannot_claim_streaming_transfer_bound(self):
        self.output = lambda label, value: b"curl 8.3.0 (OFFLINE)\n" if label == "apple-link-curl-version" else value
        self.hold("streaming max-filesize")
        self.no_fetches()

    def test_curl_8_4_streaming_boundary_is_admitted(self):
        self.output = lambda label, value: b"curl 8.4.0 (OFFLINE)\n" if label == "apple-link-curl-version" else value
        self.assertEqual(self.run_admission()["status"], "ADMITTED_LINK_ONLY")

    def test_existing_or_relative_evidence_directory_cannot_be_reused(self):
        self.directory.mkdir(mode=0o700)
        with self.assertRaises(FileExistsError):
            self.run_admission()
        with self.assertRaises(ValueError):
            app.admit(self.root, Path("relative"), self.command)
        self.assertFalse(self.calls)

    def test_evidence_inside_source_is_not_admitted(self):
        with self.assertRaises(ValueError):
            app.admit(self.root, self.root / "generated", self.command)
        self.assertFalse(self.calls)

    def test_nonprivate_or_symlink_evidence_parent_is_rejected(self):
        self.state.chmod(0o755)
        with self.assertRaises(ValueError):
            self.run_admission()
        self.state.chmod(0o700)
        alias = self.base / "alias"
        alias.symlink_to(self.state, target_is_directory=True)
        with self.assertRaises(ValueError):
            app.admit(self.root, alias / "new", self.command)
        self.assertFalse(self.calls)

    def test_source_hardlink_or_symlink_is_rejected(self):
        path = self.root / app.HEADER
        alias = self.state / "header-link"
        os.link(path, alias)
        self.hold("single-link")
        self.assertFalse(self.calls)

    def test_evidence_directory_replacement_does_not_write_into_replacement(self):
        original = self.state / "original"
        def hook(label, argv, result):
            if len(self.calls) == 1:
                self.directory.rename(original)
                self.directory.mkdir(mode=0o700)
        self.hook = hook
        self.hold("directory changed")
        self.assertFalse(list(self.directory.iterdir()))
        self.assertTrue((original / "bridge.m").exists())


class ReceiptAndResultTests(Fixture):
    def test_nonzero_or_missing_command_result_is_hold(self):
        self.hook = lambda label, argv, result: result.row.update(waitExitCode=1)
        self.hold("receipt differs")
        self.no_fetches()

    def test_unknown_or_surviving_command_retirement_is_hold(self):
        self.hook = lambda label, argv, result: result.row["drains"][0].update(survivors=None)
        self.hold("retirement unknown")
        self.no_fetches()

    def test_wrong_ownership_backend_is_hold(self):
        self.hook = lambda label, argv, result: result.row["ownership"].update(backend="synthetic-other-backend")
        self.hold("retirement unknown")
        self.no_fetches()

    def test_discovery_errors_remain_hold_even_with_exit_zero(self):
        self.hook = lambda label, argv, result: result.row["ownership"].update(discoveryErrors=["unavailable"])
        self.hold("retirement unknown")

    def test_truncated_or_inconsistent_original_stream_is_hold(self):
        self.hook = lambda label, argv, result: result.row["streams"]["stderr"].update(truncated=True)
        self.hold("stream incomplete")

    def test_receipt_argv_mismatch_is_hold(self):
        self.hook = lambda label, argv, result: result.row.update(argv=["different-command"])
        self.hold("receipt differs")

    def test_missing_swift_library_warning_is_hold_despite_exit_zero(self):
        def hook(label, argv, result):
            if label.startswith("apple-link-link-"):
                raw = b"ld: warning: Could not find or use auto-linked library 'swiftCompatibilityPacks'\n"
                file_bytes(result.directory / "stderr.log", raw)
                result.row["streams"]["stderr"].update(observedBytes=len(raw), retainedBytes=len(raw))
        self.hook = hook
        self.hold("diagnostics prevent")
        self.assertEqual(sum("-link-ios" in label for label, _, _ in self.calls), 1)
        self.assertIn("swiftCompatibilityPacks", next(path for path in (self.state / "commands").glob("*/stderr.log")
                                                    if b"swiftCompatibilityPacks" in path.read_bytes()).read_text())

    def test_compiler_warning_on_stdout_is_not_ignored(self):
        self.output = lambda label, value: b"bridge.m: warning: modeled unsafe construct\n" if "-compile-" in label else value
        self.hold("diagnostics prevent")
        self.assertFalse(any("-link-ios" in label for label, _, _ in self.calls))

    def test_missing_link_product_is_hold(self):
        self.hook = lambda label, argv, result: Path(argv[argv.index("-o") + 1]).unlink() if label.startswith("apple-link-link-") else None
        self.hold()

    def test_compile_only_product_cannot_be_a_successful_final_link(self):
        def hook(label, argv, result):
            if label.startswith("apple-link-link-"):
                target = next(target for target in self.targets if target.triple in argv)
                file_bytes(Path(argv[argv.index("-o") + 1]), native_object(target, sdk=(18 << 16) | (2 << 8)))
        self.hook = hook
        self.hold("filetype differs")

    def test_link_product_for_other_platform_is_hold(self):
        def hook(label, argv, result):
            if label == "apple-link-link-iosArm64":
                file_bytes(Path(argv[argv.index("-o") + 1]), native_object(self.targets[0], filetype=2,
                           sdk=(18 << 16) | (2 << 8), platform=7))
        self.hook = hook
        self.hold("platform/deployment/SDK")

    def test_redirect_or_effective_url_change_cannot_admit_download(self):
        self.output = lambda label, value: value.replace(b"200\n", b"302\n", 1) if "-fetch-" in label else value
        self.hold("HTTP source/size")
        self.assertFalse(any("-compile-" in label for label, _, _ in self.calls))

    def test_tampered_or_truncated_download_cannot_launch_compiler(self):
        name = self.targets[0].name
        self.payloads[name] = self.payloads[name][:-1]
        self.hold("download size/hash")
        self.assertFalse(any("-compile-" in label for label, _, _ in self.calls))

    def test_oversized_download_is_hold_before_zip_parsing(self):
        self.payloads[self.targets[0].name] = b"x" * (app.FETCH_LIMIT + 1)
        self.hold("bounded owned")
        self.assertFalse(any("-compile-" in label for label, _, _ in self.calls))


class ArchiveTests(Fixture):
    def test_all_three_synthetic_archives_preserve_whole_bytes_and_target_metadata(self):
        for target in self.targets:
            with self.subTest(target=target.name):
                raw, report = app.unpack(self.payloads[target.name], target)
                self.assertEqual(raw, archive_bytes(target))
                self.assertEqual(len(report["members"]), 2)
                self.assertEqual(report["members"][1]["macho"]["platform"], target.platform)

    def test_duplicate_zip_entry_is_rejected(self):
        self.zip_reject(extras=[("default/manifest", b"duplicate", stat.S_IFREG | 0o644)])

    def test_traversal_absolute_and_backslash_zip_paths_are_rejected(self):
        for name in ("../escape", "/escape", "a/../escape", "a//escape", "a\\escape"):
            with self.subTest(name=name):
                self.zip_reject(extras=[(name, b"x", stat.S_IFREG | 0o644)])

    def test_archive_symlink_or_special_file_is_rejected(self):
        for mode in (stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600, stat.S_IFCHR | 0o600):
            with self.subTest(mode=mode):
                self.zip_reject(archive_mode=mode)

    def test_additional_or_wrong_target_archive_is_rejected(self):
        self.zip_reject(extras=[("default/targets/ios_x64/included/foreign.a", b"x", stat.S_IFREG | 0o644)])
        self.zip_reject(archive_name="default/targets/foreign/included/libDwcCryptoKitInterop.a")

    def test_zip_decompression_or_entry_count_bound_is_enforced(self):
        self.zip_reject(extras=[("huge", b"z" * (app.ZIP_LIMIT + 1), stat.S_IFREG | 0o644)])
        self.zip_reject(extras=[("extra" + str(i), b"", stat.S_IFREG | 0o644) for i in range(128)])

    def test_wrong_or_duplicate_manifest_target_is_rejected(self):
        for raw in (b"builtins_platform=NATIVE\ninterop=true\nnative_targets=wrong\nstaticLibraries=libDwcCryptoKitInterop.a\n",
                    b"native_targets=ios_arm64\nnative_targets=ios_arm64\n"):
            with self.subTest(raw=raw):
                self.zip_reject(manifest=raw)

    def test_archive_checksum_mismatch_is_not_excused_by_klib_hash(self):
        changed = archive_bytes(self.targets[0]) + b"tampered"
        raw = zip_bytes(self.targets[0], changed)
        with self.assertRaises(ValueError):
            app.unpack(raw, repin(self.targets[0], raw))

    def test_nonarchive_truncation_and_invalid_member_extent_are_rejected(self):
        raw = archive_bytes(self.targets[0])
        for value in (b"not archive", raw[:-10], raw[:10]):
            with self.subTest(length=len(value)):
                self.archive_reject(value)

    def test_duplicate_or_path_ar_members_are_rejected(self):
        obj = native_object(self.targets[0])
        table = b"!<arch>\n" + member("__.SYMDEF", b"table")
        self.archive_reject(table + member("x.o", obj) + member("x.o", obj), "duplicate")
        self.archive_reject(table + member("../x.o", obj), "unsafe")

    def test_unknown_ar_payload_and_missing_symbol_table_are_rejected(self):
        self.archive_reject(b"!<arch>\n" + member("__.SYMDEF", b"table") + member("object.bc", b"bitcode"))
        self.archive_reject(b"!<arch>\n" + member("x.o", native_object(self.targets[0])), "complete native archive")

    def test_nonmatching_macho_architecture_platform_sdk_and_deployment_fail(self):
        target = self.targets[0]
        for changes in ({"cpu": self.targets[2].cpu}, {"subtype": 2}, {"platform": 7},
                        {"sdk": (18 << 16) | (2 << 8)}, {"minimum": 15 << 16}, {"filetype": 2}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                app.macho(native_object(target, **changes), target, 1, (26 << 16) | (2 << 8))

    def test_macho_truncation_and_command_bounds_fail(self):
        raw = native_object(self.targets[0])
        values = [raw[:20], raw[:-1], raw[:16] + struct.pack("<I", 513) + raw[20:],
                  raw[:36] + struct.pack("<I", 0) + raw[40:]]
        for value in values:
            with self.subTest(length=len(value)), self.assertRaises(ValueError):
                app.macho(value, self.targets[0], 1, (26 << 16) | (2 << 8))

    def test_linker_autolinks_are_preserved_not_executed_as_commands(self):
        options = b"-lswiftCompatibilityPacks\0"
        size = (12 + len(options) + 7) // 8 * 8
        extra = struct.pack("<III", 0x2D, size, 1) + options + b"\0" * (size - 12 - len(options))
        raw = native_object(self.targets[0], extra=extra, extra_count=1)
        report = app.macho(raw, self.targets[0], 1, (26 << 16) | (2 << 8))
        self.assertEqual(report["linkerOptions"], [["-lswiftCompatibilityPacks"]])
        self.assertFalse(self.calls)

    def test_malformed_autolink_count_or_strings_fail(self):
        extra = struct.pack("<III", 0x2D, 16, 33) + b"x\0\0\0"
        with self.assertRaises(ValueError):
            app.macho(native_object(self.targets[0], extra=extra, extra_count=1), self.targets[0], 1, (26 << 16) | (2 << 8))


if __name__ == "__main__":
    unittest.main(verbosity=2)
