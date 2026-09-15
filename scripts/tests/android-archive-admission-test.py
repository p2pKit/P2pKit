#!/usr/bin/env python3
"""Tiny synthetic archive/SDK and modeled curl/receipt tests, never native evidence.

No real subprocess, download, SDK tool or emulator is permitted. Published pins
are replaced only inside explicitly modeled fixtures, never in the production
entrypoint. A modeled successful receipt is not a genuine producer qualification.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zlib

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("android_archive_admission_test_subject", SCRIPTS / "android_archive_admission.py")
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)
runner = subject.controller.load_tool("run-audit-command.py")
checker = subject.controller.load_tool("check-audit-receipt.py")
artifacts = subject.controller.load_tool("verify-android-acceptance-artifacts.py")
SOURCE = {"commit": "1" * 40, "tree": "2" * 40, "status": "", "diffSha256": hashlib.sha256(b"").hexdigest()}
PRODUCER, OWNER = "3" * 32, "4" * 32


def binding(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def entry(name, raw=b"", mode=0o100644, method=0, descriptor=0, extra=b"", local_extra=b""):
    return {"name": name, "raw": raw, "mode": mode, "method": method, "descriptor": descriptor,
            "extra": extra, "localExtra": local_extra}


def archive(entries):
    """Explicit tiny ZIP32 writer, including valid zero local flag8 sizes/CRC."""
    local, central = bytearray(), bytearray()
    for row in entries:
        name, raw = row["name"].encode("ascii"), row["raw"]
        crc = zlib.crc32(raw) & 0xFFFFFFFF
        coder = zlib.compressobj(wbits=-15)
        payload = coder.compress(raw) + coder.flush() if row["method"] == 8 else raw
        flags, extra, local_extra = (8 if row["descriptor"] else 0), row["extra"], row["localExtra"]
        offset = len(local)
        sizes = (0, 0, 0) if flags & 8 else (crc, len(payload), len(raw))
        local += struct.pack("<I5H3I2H", 0x04034B50, 20, flags, row["method"], 0, 0,
                             *sizes, len(name), len(local_extra)) + name + local_extra + payload
        if row["descriptor"]:
            local += (b"PK\x07\x08" if row["descriptor"] == 16 else b"") + struct.pack("<III", crc, len(payload), len(raw))
        central += struct.pack("<I6H3I5H2I", 0x02014B50, 0x0314, 20, flags, row["method"], 0, 0, crc,
                               len(payload), len(raw), len(name), len(extra), 0, 0, 0, row["mode"] << 16, offset) + name + extra
    end = struct.pack("<I4H2IH", 0x06054B50, 0, 0, len(entries), len(entries), len(central), len(local), 0)
    return bytes(local + central + end)


def properties(role):
    return "".join(key + "=" + value + "\n" for key, value in subject.PROPERTIES[role].items()).encode("ascii")


def installer(role):
    prefix = ('<?xml version="1.0" encoding="UTF-8"?>'
              '<r:repository xmlns:r="http://schemas.android.com/repository/android/common/02" '
              'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
              'xmlns:s="http://schemas.android.com/sdk/android/repo/sys-img2/05" '
              'xmlns:g="http://schemas.android.com/repository/android/generic/02">')
    if role == "image":
        license_id, path = "android-sdk-arm-dbt-license", subject.IMAGE_PACKAGE
        details = ('<type-details xsi:type="s:sysImgDetailsType"><api-level>37.0</api-level>'
                   '<extension-level>22</extension-level><base-extension>true</base-extension>'
                   '<tag><id>google_apis_playstore</id><display>Google APIs PlayStore</display></tag>'
                   '<tag><id>page_size_16kb</id><display>Page Size 16KB</display></tag>'
                   '<vendor><id>google</id><display>Google Inc.</display></vendor>'
                   '<abi>arm64-v8a</abi><abis>arm64-v8a</abis></type-details>')
        revision, display = "<major>5</major>", "16 KB Page Size Google Play ARM 64 v8a System Image"
        dependencies = ('<dependencies><dependency path="emulator"><min-revision><major>35</major>'
                        '<minor>4</minor><micro>9</micro></min-revision></dependency></dependencies>')
    else:
        license_id, path = "android-sdk-license", "emulator"
        details = '<type-details xsi:type="g:genericDetailsType"/>'
        revision, display, dependencies = "<major>36</major><minor>6</minor><micro>11</micro>", "Android Emulator", ""
    return (prefix + f'<license id="{license_id}" type="text">MODEL ONLY, NOT A LICENSE ACCEPTANCE</license>'
            f'<localPackage path="{path}" obsolete="false">' + details + f'<revision>{revision}</revision>'
            f'<display-name>{display}</display-name><uses-license ref="{license_id}"/>' + dependencies +
            '</localPackage></r:repository>').encode()


def write(path, raw, mode=0o644):
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    with runner.new_file(path) as stream:
        stream.write(raw)
    path.chmod(mode)


class Pipe:
    def __init__(self, fd, chunks):
        self.fd, self.chunks, self.closed = fd, list(chunks), False

    def fileno(self):
        return self.fd

    def close(self):
        self.closed = True


class Selector:
    def __init__(self):
        self.keys = {}

    def register(self, pipe, events, data):
        self.keys[pipe.fd] = SimpleNamespace(fileobj=pipe, data=data)

    def unregister(self, pipe):
        del self.keys[pipe.fd]

    def get_map(self):
        return self.keys

    def select(self, seconds):
        return [(row, None) for row in list(self.keys.values()) if row.fileobj.chunks]

    def close(self):
        self.keys.clear()


class ModelTest(unittest.TestCase):
    def setUp(self):
        for item, key in ((subject.subprocess, "Popen"), (subject.subprocess, "run"), (socket, "create_connection")):
            patcher = mock.patch.object(item, key, side_effect=AssertionError("No real command/network in model tests"))
            patcher.start()
            self.addCleanup(patcher.stop)
        temporary = tempfile.TemporaryDirectory(prefix="p2pkit-archive-model-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.check = lambda: None

    def patched(self, owner, key, value):
        patcher = mock.patch.object(owner, key, value)
        patcher.start()
        self.addCleanup(patcher.stop)


class ArchiveTests(ModelTest):
    def rows(self, raw):
        return subject.zip_structure(io.BytesIO(raw), len(raw), self.check)

    def expanded(self, raw):
        stream = io.BytesIO(raw)
        return {row["name"]: b"".join(subject.member_blocks(stream, row, self.check)) for row in self.rows(raw)}

    def test_exact_public_pins_are_not_derived_from_installed_metadata(self):
        self.assertEqual(subject.PINS["image"]["bytes"], 2216674212)
        self.assertIsNone(subject.PINS["image"]["publisherSha256"])
        self.assertEqual(subject.PINS["emulator"]["bytes"], 383903546)
        self.assertEqual(subject.PINS["emulator"]["publisherSha256"],
                         "aebcd4dde29a4921d47e5e79b8c1ffece69a70f5b280d8dc7033ebaffa737072")
        self.assertEqual(len(subject.IMAGE_MEMBERS), 32)
        self.assertEqual(sum(subject.IMAGE_MEMBERS.values()), 3105182926)

    def test_archive_only_floor_reserve_and_exact_initial_byte_requirement(self):
        self.assertEqual(subject.FLOOR, 8 * subject.GIB)
        self.assertEqual(subject.RESERVE, 3 * subject.GIB)
        self.assertEqual(subject.FLOOR + subject.RESERVE + sum(pin["bytes"] for pin in subject.PINS.values()),
                         14411737822)

    def test_continuous_floor_rejects_modeled_decline_below_equality(self):
        disk = self.base / "modeled-evidence-filesystem"
        with mock.patch.object(subject.time, "monotonic", side_effect=(0.0, 0.0, 0.5, 1.0, 2.0)), \
                mock.patch.object(subject.shutil, "disk_usage", side_effect=[
                    SimpleNamespace(free=subject.FLOOR + 1), SimpleNamespace(free=subject.FLOOR),
                    SimpleNamespace(free=subject.FLOOR - 1)]) as usage:
            budget = subject.Budget(10, disk)
            budget()
            budget()  # The sub-second call must not replace the once-per-second observation.
            budget()
            with self.assertRaisesRegex(subject.Rejected, "Separate free-space floor exhausted"):
                budget()
        self.assertEqual(usage.call_args_list, [mock.call(disk)] * 3)

    def test_stored_deflated_empty_and_both_descriptor_forms(self):
        entries = [entry("emulator/empty"), entry("emulator/stored", b"abc"),
                   entry("emulator/deflated", b"ab" * 100000, method=8),
                   entry("emulator/signed", b"descriptor", method=8, descriptor=16),
                   entry("emulator/unsigned", b"unsigned", method=8, descriptor=12),
                   entry("emulator/empty-deflated", method=8, descriptor=16)]
        self.assertEqual(self.expanded(archive(entries)), {row["name"]: row["raw"] for row in entries})

    def test_rejects_truncation_suffix_prefix_eocd_comment_and_multidisk(self):
        raw = archive([entry("emulator/a", b"abc")])
        disk = bytearray(raw)
        struct.pack_into("<H", disk, len(disk) - 18, 1)
        comment = bytearray(raw)
        struct.pack_into("<H", comment, len(comment) - 2, 1)
        for bad in (raw[:-1], raw + b"x", b"x" + raw, bytes(disk), bytes(comment)):
            with self.subTest(length=len(bad)), self.assertRaises(subject.Rejected):
                self.rows(bad)

    def test_rejects_central_local_mismatch_and_gap(self):
        raw = archive([entry("emulator/a", b"abc")])
        central = struct.unpack_from("<I4H2IH", raw, len(raw) - 22)[6]
        for offset, format_string, value in ((6, "<H", 8), (14, "<I", 42), (30, "<B", ord("x")),
                                              (central + 42, "<I", 1), (central + 20, "<I", 2)):
            bad = bytearray(raw)
            struct.pack_into(format_string, bad, offset, value)
            with self.subTest(offset=offset), self.assertRaises(subject.Rejected):
                self.rows(bad)

    def test_rejects_crc_length_and_decoder_trailing_or_incomplete_data(self):
        raw = archive([entry("emulator/a", b"abc")])
        row = self.rows(raw)[0]
        bad = bytearray(raw)
        bad[row["dataOffset"]] ^= 1
        with self.assertRaises(subject.Rejected):
            self.expanded(bytes(bad))
        coder = zlib.compressobj(wbits=-15)
        compressed = coder.compress(b"abcdef") + coder.flush()
        base = {"dataOffset": 0, "compressedBytes": len(compressed), "bytes": 6,
                "method": 8, "crc32": zlib.crc32(b"abcdef")}
        for payload, length in ((compressed + b"x", 6), (compressed[:-1], 6), (compressed, 5), (compressed, 7)):
            changed = {**base, "compressedBytes": len(payload), "bytes": length}
            with self.subTest(length=length, payload=len(payload)), self.assertRaises(subject.Rejected):
                list(subject.member_blocks(io.BytesIO(payload), changed, self.check))

    def test_descriptor_values_and_sizes_are_not_optional(self):
        raw = archive([entry("emulator/a", b"abc", method=8, descriptor=16)])
        row = self.rows(raw)[0]
        for delta in (0, 4, 8, 12):
            bad = bytearray(raw)
            bad[row["dataOffset"] + row["compressedBytes"] + delta] ^= 1
            with self.subTest(delta=delta), self.assertRaises(subject.Rejected):
                self.rows(bytes(bad))

    def test_zip64_encryption_unknown_extras_and_special_modes_reject(self):
        raw = archive([entry("emulator/a", b"x")])
        central = struct.unpack_from("<I4H2IH", raw, len(raw) - 22)[6]
        for offset, fmt, value in ((central + 8, "<H", 1), (central + 6, "<H", 45),
                                  (central + 20, "<I", 0xFFFFFFFF), (central + 38, "<I", 0o020644 << 16),
                                  (central + 38, "<I", 0o104644 << 16)):
            bad = bytearray(raw)
            struct.pack_into(fmt, bad, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(subject.Rejected):
                self.rows(bytes(bad))
        for extra in (b"x", struct.pack("<HH", 1, 0), struct.pack("<HH", 0x5455, 5) + b"\x01\x00"):
            with self.subTest(extra=extra), self.assertRaises(subject.Rejected):
                self.rows(archive([entry("emulator/a", extra=extra)]))

    def test_known_unix_extras_are_bounded_not_authority(self):
        timestamp = struct.pack("<HHBI", 0x5455, 5, 1, 123)
        uid = struct.pack("<HHBBBBB", 0x7875, 5, 1, 1, 0, 1, 0)
        self.rows(archive([entry("emulator/a", extra=timestamp + uid, local_extra=timestamp + uid)]))
        with self.assertRaises(subject.Rejected):
            self.rows(archive([entry("emulator/a", extra=timestamp + timestamp)]))

    def test_archive_path_aliases_duplicates_and_file_parents_reject(self):
        for name in ("../a", "/emulator/a", "emulator//a", "emulator/../a", "emulator/a.", "emulator/a ", "emulator/a:b"):
            with self.subTest(name=name), self.assertRaises(subject.Rejected):
                self.rows(archive([entry(name)]))
        with self.assertRaises(subject.Rejected):
            self.rows(archive([entry("emulator/a"), entry("emulator/A")]))
        for entries in ([entry("emulator/a"), entry("emulator/a/b")],
                        [entry("emulator/Dir/a"), entry("emulator/dir/b")]):
            rows = self.rows(archive([*entries, entry("emulator/source.properties")]))
            with self.assertRaises(subject.Rejected):
                subject.namespace(rows, "emulator")

    def test_namespace_requires_exact_package_prefix_and_installer_exception(self):
        for entries in ([entry("other/a"), entry("emulator/source.properties")],
                        [entry("emulator/a")], [entry("emulator/source.properties"), entry("emulator/package.xml")]):
            with self.assertRaises(subject.Rejected):
                subject.namespace(self.rows(archive(entries)), "emulator")

    def test_image_requires_every_one_of_32_members_and_exact_metadata(self):
        rows = [{"relative": name, "bytes": size, "kind": "file", "mode": 0o100644,
                 "method": 8, "flags": 8, "centralExtraBytes": 0} for name, size in subject.IMAGE_MEMBERS.items()]
        subject.image_rows(rows)
        for key, value in (("bytes", 0), ("mode", 0o100755), ("flags", 0), ("centralExtraBytes", 5)):
            changed = copy.deepcopy(rows)
            changed[0][key] = value
            with self.subTest(key=key), self.assertRaises(subject.Rejected):
                subject.image_rows(changed)
        with self.assertRaises(subject.Rejected):
            subject.image_rows(rows[:-1])

    def test_expansion_and_member_limits_reject_before_inflation(self):
        raw = archive([entry("emulator/a", b"a" * 100, method=8)])
        with mock.patch.object(subject, "EXPANSION_LIMIT", 99), self.assertRaises(subject.Rejected):
            self.rows(raw)
        with mock.patch.object(subject, "MEMBER_LIMIT", 0), self.assertRaises(subject.Rejected):
            self.rows(raw)

    def test_source_properties_and_installer_identity(self):
        for role in ("image", "emulator"):
            props = subject.source_properties(properties(role), role)
            parsed = subject.installer_metadata(installer(role), role, props)
            self.assertEqual(parsed["authority"], "HASH_RETAINED_INSTALLER_RECORD_ONLY")
            with self.assertRaises(subject.Rejected):
                subject.source_properties(properties(role) + b"Pkg.Revision=9\n", role)
            with self.assertRaises(subject.Rejected):
                subject.installer_metadata(installer(role).replace(b"<major>", b"<major>9", 1), role, props)

    def test_installer_rejects_entities_duplicate_packages_shadow_types_and_wrong_license(self):
        raw, props = installer("emulator"), subject.PROPERTIES["emulator"]
        mutations = [b"<!DOCTYPE x [<!ENTITY e 'x'>]>" + raw,
                     raw.replace(b"</r:repository>", b'<localPackage path="evil"/></r:repository>'),
                     raw.replace(b'g:genericDetailsType', b's:genericDetailsType'),
                     raw.replace(b'android-sdk-license', b'other-license'),
                     raw.replace(b'<localPackage ', b'<localPackage xmlns:g="https://evil.invalid" '),
                     raw.replace(b'</license>', b'</license>unknown')]
        for value in mutations:
            with self.subTest(value=value[-120:]), self.assertRaises((subject.Rejected, subject.ET.ParseError)):
                subject.installer_metadata(value, "emulator", props)

    def test_symlink_text_resolution_is_in_root_and_cycle_free(self):
        nodes = {"": "directory", "bin": "directory", "bin/tool": "file", "lib": "directory",
                 "lib/link": "link", "alias": "link", "package.xml": "file"}
        subject.resolve_links(nodes, {"lib/link": "../bin/tool", "alias": "lib/link"})
        for links in ({"alias": "../../outside"}, {"alias": "/bin/tool"}, {"alias": "missing"},
                      {"alias": "lib/link", "lib/link": "../alias"}, {"alias": "package.xml"},
                      {"alias": "bin/tool/child"}, {"alias": "bin\\tool"}):
            with self.subTest(links=links), self.assertRaises(subject.Rejected):
                subject.resolve_links(nodes, links)

    def test_file_binding_rejects_alias_and_drift(self):
        path = self.base / "file"
        write(path, b"abcdef")
        os.link(path, self.base / "alias")
        with self.assertRaises(subject.Rejected):
            subject.file_binding(path, 6, self.check)
        (self.base / "alias").unlink()
        calls = 0
        def change():
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_bytes(b"abcdefg")
        with self.assertRaises(subject.Rejected):
            subject.file_binding(path, 6, change)

    def test_installed_inventory_bounds_and_no_symlink_following(self):
        root = self.base / "package"
        root.mkdir()
        write(root / "a", b"x")
        (root / "link").symlink_to("/definitely-not-an-admitted-target")
        rows = {}
        subject.installed_graph(root, self.check, rows)
        self.assertEqual(rows["link"]["kind"], "link")
        self.assertNotIn("linkText", rows["link"])
        with mock.patch.object(subject, "GRAPH_LIMIT", 2), self.assertRaises(subject.Rejected):
            subject.installed_graph(root, self.check, {})

    def test_https_redirect_policy_and_download_argv_are_closed(self):
        cdn = "https://r1---sn-abcd.gvt1.com/edgedl/android/repository/" + subject.EMULATOR_NAME + "?model=1"
        subject.approved_url(cdn, "emulator")
        for url in (cdn.replace("https:", "http:"), cdn.replace("gvt1.com", "gvt1.com.evil.invalid"),
                    cdn.replace("https://", "https://user@"), cdn + "#fragment",
                    cdn.replace(subject.EMULATOR_NAME, "different.zip"), cdn.replace("gvt1.com/", "gvt1.com:4433/")):
            with self.subTest(url=url), self.assertRaises(subject.Rejected):
                subject.approved_url(url, "emulator")
        with self.assertRaises(subject.Rejected):
            subject.approved_url(cdn, "image")
        argv = subject.curl_arguments(subject.IMAGE_URL, "image", False)
        self.assertEqual(argv[:2], ["/usr/bin/curl", "-q"])
        self.assertEqual(argv[argv.index("--max-time") + 1], "900")
        for option in ("-L", "--location", "--insecure", "--range", "--retry", "--continue-at", "--netrc", "--user"):
            self.assertNotIn(option, argv)
        head = subject.curl_arguments(subject.EMULATOR_URL, "emulator", True)
        self.assertEqual(head[head.index("--max-filesize") + 1], "383903546")

    def test_brace_and_bracket_query_urls_stay_literal_for_head_and_get(self):
        for query in ("?x={1,2}", "?x=[1-2]"):
            url = "https://dl.google.com/android/repository/" + subject.EMULATOR_NAME + query
            for head in (True, False):
                with self.subTest(query=query, head=head):
                    argv = subject.curl_arguments(url, "emulator", head)
                    self.assertEqual(argv[:3], ["/usr/bin/curl", "-q", "--globoff"])
                    self.assertEqual(argv.count("--globoff"), 1)
                    self.assertEqual(argv.count("--url"), 1)
                    self.assertEqual(argv[-2:], ["--url", url])
                    self.assertEqual("--head" in argv, head)
                    self.assertEqual(argv[argv.index("--max-time") + 1], "30" if head else "300")

    def test_http_header_and_actual_tls_status_guards(self):
        raw = b"HTTP/1.1 200 OK\r\nContent-Length: 2216674212\r\n\r\n"
        header = subject.response_headers(raw, "image", False)
        for changed in (raw.replace(b"200", b"206", 1), raw[:-1], raw.replace(b"2216674212", b"1"),
                        raw.replace(b"\r\n\r\n", b"\r\nTransfer-Encoding: chunked\r\n\r\n"),
                        raw.replace(b"\r\n\r\n", b"\r\nContent-Encoding: gzip\r\n\r\n"),
                        raw.replace(b"\r\n\r\n", b"\r\nContent-Length: 2216674212\r\n\r\n")):
            with self.subTest(changed=changed), self.assertRaises(subject.Rejected):
                subject.response_headers(changed, "image", False)
        status = ("HTTP_CODE=200\nSIZE_DOWNLOAD=2216674212\nSSL_VERIFY_RESULT=0\nURL_EFFECTIVE=" +
                  subject.IMAGE_URL + "\nNUM_REDIRECTS=0\n").encode()
        subject.curl_status(status, subject.IMAGE_URL, header, 2216674212)
        for changed in (status.replace(b"SSL_VERIFY_RESULT=0", b"SSL_VERIFY_RESULT=1"),
                        status.replace(b"NUM_REDIRECTS=0", b"NUM_REDIRECTS=1"), b"curl error\n" + status):
            with self.assertRaises(subject.Rejected):
                subject.curl_status(changed, subject.IMAGE_URL, header, 2216674212)

    def test_environment_rejects_overrides_and_preserves_exact_ownership(self):
        env = {"P2PKIT_AUDIT_JOB_ID": "model", "GRADLE_USER_HOME": "/model/gradle-home", "GH_TOKEN": "never inherited"}
        selected = subject.curl_environment(env, self.base)
        self.assertNotIn("GH_TOKEN", selected)
        self.assertEqual(selected["GRADLE_USER_HOME"], env["GRADLE_USER_HOME"])
        self.assertEqual(selected["P2PKIT_AUDIT_JOB_ID"], "model")
        for key in ("HTTPS_PROXY", "https_proxy", "CURL_CA_BUNDLE", "SSL_CERT_FILE", "DYLD_INSERT_LIBRARIES", "SSLKEYLOGFILE"):
            with self.subTest(key=key), self.assertRaises(subject.Rejected):
                subject.curl_environment({**env, key: "override"}, self.base)

    def test_no_unisolated_or_caller_archive_capture_request(self):
        argv = ["python3", "-I", "-B", "-S", "scripts/android_archive_admission.py", "capture"]
        subject.capture_request(argv, self.base)
        for bad in (argv + ["--trusted"], argv + ["--archive", "/tmp/body"], argv[:1] + argv[4:],
                    argv[:-1] + ["admit"], ["arbitrary-python", *argv[1:]]):
            with self.assertRaises(subject.Rejected):
                subject.capture_request(bad, self.base)


class WholeRouteModelTests(ModelTest):
    """The real comparator/producer-record/intake path, with only transport modeled."""
    def setUp(self):
        super().setUp()
        self.root, self.state, self.sdk = (self.base / name for name in ("source", "state", "synthetic-sdk"))
        for directory in (self.root, self.state, self.sdk):
            directory.mkdir()
        write(self.root / "gradlew", b"MODELED WRAPPER; NEVER EXECUTED\n")
        (self.state / "gradle-home").mkdir()
        self.context = {"id": "5" * 32, "root": str(self.root), "source": SOURCE,
                        "host": "macos-arm64", "gradleHome": str(self.state / "gradle-home")}
        self.environment = {"ANDROID_HOME": str(self.sdk), "GRADLE_USER_HOME": self.context["gradleHome"]}
        self.argv = ["python3", "-I", "-B", "-S", "scripts/android_archive_admission.py", "capture"]
        self.producer_directory = self.state / "evidence" / PRODUCER
        self.producer_directory.mkdir(parents=True)
        runner.write_new_json(self.producer_directory / "start.json", {"requestedArgv": self.argv})
        self.capture_directory = self.producer_directory / "android-archives"
        self.admission_directory = self.state / "evidence" / OWNER / "android-archive-admission"
        self.admission_directory.mkdir(parents=True)
        image_entries = [entry("arm64-v8a/" + name, properties("image") if name == "source.properties"
                               else ("MODEL ONLY " + name).encode(), method=8, descriptor=16)
                         for name in subject.IMAGE_MEMBERS]
        emulator_entries = [entry("emulator/source.properties", properties("emulator"), method=8, descriptor=12),
                            entry("emulator/bin/tool", b"MODEL ONLY; NEVER EXECUTABLE", mode=0o100755, method=8),
                            entry("emulator/empty/", mode=0o40755), entry("emulator/lib/engine", b"MODEL LIBRARY"),
                            entry("emulator/lib/alias", b"engine", mode=0o120777)]
        self.package_roots, self.archives = {}, {}
        for role, entries in (("image", image_entries), ("emulator", emulator_entries)):
            package = self.sdk / (subject.IMAGE_PATH if role == "image" else "emulator")
            package.mkdir(parents=True)
            self.package_roots[role] = package
            for row in entries:
                relative = row["name"].split("/", 1)[1].rstrip("/")
                path = package / relative
                if stat.S_ISDIR(row["mode"]):
                    path.mkdir(parents=True, exist_ok=True)
                    path.chmod(row["mode"] & 0o777)
                elif stat.S_ISLNK(row["mode"]):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.symlink_to(row["raw"].decode())
                    # A fixture input, not a production permission expectation.
                    row["mode"] = path.lstat().st_mode
                else:
                    write(path, row["raw"], row["mode"] & 0o777)
            write(package / "package.xml", installer(role))
            self.archives[role] = archive(entries)
        pins = copy.deepcopy(subject.PINS)
        for role in pins:
            pins[role]["bytes"] = len(self.archives[role])
        pins["emulator"]["publisherSha256"] = binding(self.archives["emulator"])["sha256"]
        self.patched(subject, "PINS", pins)
        self.patched(subject, "IMAGE_MEMBERS", {row["name"].split("/", 1)[1]: len(row["raw"]) for row in image_entries})
        self.patched(subject, "ROOT", self.root)
        self.patched(runner, "source_snapshot", lambda root: dict(SOURCE))
        self.initial_required = subject.FLOOR + subject.RESERVE + sum(pin["bytes"] for pin in pins.values())
        self.patched(subject.shutil, "disk_usage",
                     lambda path: SimpleNamespace(free=self.initial_required + subject.RESERVE))
        original_binding = subject.file_binding
        def modeled_curl(path, limit, check, keep=False):
            if path == Path("/usr/bin/curl"):
                raw = b"MODELED CURL IDENTITY; NO NATIVE READ"
                return binding(raw), raw if keep else None
            return original_binding(path, limit, check, keep)
        self.patched(subject, "file_binding", modeled_curl)
        self.pipes, self.forks, self.payload_transform, self.no_eof = {}, [], None, False
        self.patched(subject.subprocess, "Popen", self.fork)
        self.patched(subject.selectors, "DefaultSelector", Selector)
        self.patched(subject.os, "set_blocking", lambda fd, blocking: None)
        self.patched(subject.os, "read", lambda fd, size: self.pipes[fd].chunks.pop(0))

    def fork(self, argv, **kwargs):
        self.assertEqual(argv[:2], ["/usr/bin/curl", "-q"])
        self.assertEqual(kwargs["stdin"], subject.subprocess.DEVNULL)
        self.assertFalse(kwargs.get("shell", False))
        role = "image" if argv[-1] == subject.IMAGE_URL else "emulator"
        head = "--head" in argv
        body = b"" if head else self.archives[role]
        header = (f'HTTP/1.1 200 OK\r\nContent-Length: {len(self.archives[role])}\r\n\r\n').encode()
        status = (f'HTTP_CODE=200\nSIZE_DOWNLOAD={len(body)}\nSSL_VERIFY_RESULT=0\n'
                  f'URL_EFFECTIVE={argv[-1]}\nNUM_REDIRECTS=0\n').encode()
        code = 0
        if self.payload_transform is not None:
            header, body, status, code = self.payload_transform(role, head, header, body, status)
        output = header + body
        number = len(self.forks) + 1
        out_chunks = [output] if self.no_eof else [output[i:i + 57] for i in range(0, len(output), 57)] + [b""]
        err_chunks = [status[i:i + 57] for i in range(0, len(status), 57)] + [b""]
        out, err = Pipe(number * 2, out_chunks), Pipe(number * 2 + 1, err_chunks)
        self.pipes[out.fd], self.pipes[err.fd] = out, err
        child = SimpleNamespace(pid=100000 + number, stdout=out, stderr=err, poll=lambda: code)
        self.forks.append({"argv": argv, "child": child})
        return child

    def receipt(self):
        return {"schema": 1, "id": PRODUCER, "kind": "command", "purpose": "archive-model-capture",
                "cwd": str(self.root), "wrapper": str(self.root / "gradlew"), "requestedArgv": list(self.argv),
                "executedArgv": list(self.argv), "jobId": self.context["id"], "host": "macos-arm64",
                "gradleHome": self.context["gradleHome"], "sourceBefore": SOURCE, "sourceAfter": SOURCE,
                "productExitCode": 0, "finalExitCode": 0, "stopExitCode": 0, "sourceUnchanged": True,
                "errors": [], "ownedSurvivors": [], "evidenceDirectory": str(self.producer_directory)}

    def captured(self, good=True):
        path, actual_good = subject.capture(runner, self.state, self.context, PRODUCER, self.environment, self.check)
        self.assertEqual(actual_good, good)
        result = subject.json_original(path, self.check)[1]
        if good:
            runner.write_new_json(self.producer_directory / "receipt.json", self.receipt())
            write(self.producer_directory / "product.stdout.log", subject.output_binding(runner, path, self.check))
        return result

    def admit(self):
        result = {}
        subject.admit_retained(runner, checker, artifacts, self.state, self.context, OWNER, self.environment,
                               self.producer_directory / "receipt.json", "archive-model-capture", self.check,
                               self.admission_directory, result)
        return result

    def captured_at_capacity(self, delta, good):
        # No observation of the real evidence filesystem's capacity is made.
        with mock.patch.object(subject.shutil, "disk_usage",
                               return_value=SimpleNamespace(free=self.initial_required + delta)) as usage:
            result = self.captured(good)
        self.assertEqual(usage.call_args_list[0], mock.call(self.capture_directory))
        return result

    def test_initial_capacity_below_threshold_rejects_before_sdk_or_curl(self):
        with mock.patch.object(subject, "selected_sdk", side_effect=AssertionError("No SDK read below threshold")) as sdk:
            result = self.captured_at_capacity(-1, False)
        sdk.assert_not_called()
        self.assertEqual(self.forks, [])
        self.assertTrue(any("spare reserve and exact archive bytes" in error for error in result["errors"]))

    def test_initial_capacity_equal_threshold_passes(self):
        self.captured_at_capacity(0, True)

    def test_initial_capacity_above_threshold_passes(self):
        self.captured_at_capacity(1, True)

    def test_complete_synthetic_32_member_and_emulator_capture_admission(self):
        result = self.captured()
        self.assertEqual(result["runtime"], "NOT_RUN")
        self.assertEqual(result["independentReview"], "REQUIRED_SEPARATELY")
        self.assertIsNone(result["publisherWholeArchiveChecksum"]["image"])
        self.assertEqual(len(self.forks), 3)  # Image GET, emulator HEAD, one emulator GET.
        admitted = self.admit()
        self.assertEqual(admitted["status"], "AUTHENTICATED_OFFICIAL_ORIGIN_CONTENT_MATCH_PENDING_ADMISSION_RECEIPT")
        for role in ("image", "emulator"):
            report = subject.json_original(self.capture_directory / (role + "-comparison.json"), self.check)[1]
            self.assertEqual(report["archive"], binding(self.archives[role]))
            self.assertEqual(report["installedAfter"], "EXACTLY_EQUAL_TO_BEFORE")
            for row in report["members"]:
                self.assertEqual(row["archiveSha256"], row["installedSha256"])
        self.assertEqual(len(self.forks), 3, "Admission must not download, build or launch")

    def test_unknown_installed_content_is_not_read_and_partial_graph_survives(self):
        unknown = self.package_roots["image"] / "unreviewed.ini"
        write(unknown, b"THIS MODEL CONTENT MUST NOT BE READ")
        with mock.patch.object(subject, "original", wraps=subject.original) as opens:
            result = self.captured(False)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertNotIn(unknown, [call.args[0] for call in opens.call_args_list])
        report = subject.json_original(self.capture_directory / "image-comparison.json", self.check)[1]
        self.assertIn("unreviewed.ini", report["installedBefore"])
        self.assertEqual(report["members"], [])

    def test_missing_member_is_not_ignored(self):
        (self.package_roots["image"] / "NOTICE.txt").unlink()
        result = self.captured(False)
        self.assertTrue(any("namespace" in error for error in result["errors"]))

    def test_changed_installed_mode_is_not_byte_only_accepted(self):
        (self.package_roots["image"] / "NOTICE.txt").chmod(0o755)
        result = self.captured(False)
        self.assertTrue(any("mode differs" in error for error in result["errors"]))

    def test_unknown_installed_hardlink_is_rejected(self):
        os.link(self.package_roots["image"] / "NOTICE.txt", self.package_roots["image"] / "aliased.txt")
        result = self.captured(False)
        self.assertTrue(any("Aliased" in error for error in result["errors"]))

    def test_archive_member_mismatch_keeps_both_partial_hashes(self):
        path = self.package_roots["image"] / "NOTICE.txt"
        raw = path.read_bytes()
        path.write_bytes(b"!" + raw[1:])
        self.captured(False)
        report = subject.json_original(self.capture_directory / "image-comparison.json", self.check)[1]
        self.assertEqual(report["members"][0]["status"], "INCOMPLETE")
        self.assertNotEqual(report["members"][0]["archiveSha256"], report["members"][0]["installedSha256"])

    def test_installed_namespace_drift_during_read_is_rejected(self):
        archive_path = self.base / "model-image.zip"
        write(archive_path, self.archives["image"])
        report, changed = {}, False
        def check():
            nonlocal changed
            if report.get("members") and not changed:
                changed = True
                write(self.package_roots["image"] / "late.ini", b"MODEL")
        with self.assertRaises(subject.Rejected):
            subject.compare_package("image", archive_path, self.package_roots["image"], check, report)
        self.assertIn("late.ini", report["installedAfter"])
        self.assertEqual(report["status"], "INCOMPLETE")

    def test_first_package_drift_during_second_download_rejects_final_capture(self):
        changed = False
        def transform(role, head, header, body, status):
            nonlocal changed
            if role == "emulator" and not changed:
                changed = True
                write(self.package_roots["image"] / "late-input.ini", b"MODEL AFTER IMAGE COMPARISON")
            return header, body, status, 0
        self.payload_transform = transform
        self.captured(False)
        report = subject.json_original(self.capture_directory / "image-final-rejected.json", self.check)[1]
        self.assertIn("late-input.ini", report["installed"])

    def test_links_are_compared_as_text_not_dereferenced(self):
        path = self.package_roots["emulator"] / "lib/alias"
        path.unlink()
        path.symlink_to("/not-a-real-sdk-file")
        self.captured(False)
        report = subject.json_original(self.capture_directory / "emulator-comparison.json", self.check)[1]
        self.assertEqual(report["members"][-1]["kind"], "link")
        self.assertEqual(report["members"][-1]["status"], "INCOMPLETE")

    def test_admission_rechecks_installed_bytes_not_a_profile_boolean(self):
        self.captured()
        path = self.package_roots["image"] / "NOTICE.txt"
        raw = path.read_bytes()
        path.write_bytes(b"!" + raw[1:])
        with self.assertRaises(subject.Rejected):
            self.admit()
        report = subject.json_original(self.admission_directory / "image-rechecked.json", self.check)[1]
        self.assertEqual(report["status"], "INCOMPLETE")

    def test_installer_only_content_drift_invalidates_reuse(self):
        self.captured()
        path = self.package_roots["emulator"] / "package.xml"
        path.write_bytes(path.read_bytes().replace(b"MODEL ONLY", b"ALTERED MODEL"))
        with self.assertRaises(subject.Rejected):
            self.admit()

    def test_terminal_receipt_stop_source_owner_and_command_guards(self):
        receipt = self.receipt()
        subject.admit_producer(checker, receipt, self.context, self.root, "archive-model-capture")
        for key, value in (("kind", "gradle"), ("jobId", "different"), ("host", "macos-x64"),
                           ("gradleHome", "/other"), ("stopExitCode", 1), ("sourceUnchanged", False),
                           ("ownedSurvivors", [123]), ("errors", ["not finalized"]), ("productExitCode", 1),
                           ("executedArgv", ["copied-body"]), ("finalExitCode", 125)):
            changed = copy.deepcopy(receipt)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises((ValueError, subject.Rejected)):
                subject.admit_producer(checker, changed, self.context, self.root, "archive-model-capture")

    def test_caller_trusted_flags_cannot_replace_stdout_binding(self):
        self.captured()
        path = self.capture_directory / "result.json"
        result = subject.json_original(path, self.check)[1]
        result.update(trusted=True, downloaded=True, passed=True)
        path.write_bytes(runner.json_bytes(result))
        with self.assertRaises(subject.Rejected):
            self.admit()

    def test_noncanonical_receipt_and_moved_stdout_are_rejected(self):
        self.captured()
        forged = self.state / "forged.json"
        value = self.receipt()
        value["purpose"] = "different"
        runner.write_new_json(forged, value)
        with self.assertRaises(ValueError):
            subject.controller.canonical_receipt(runner, artifacts, self.state, forged)
        path = self.producer_directory / "product.stdout.log"
        path.write_bytes(b'{"path":"/copied/body","trusted":true}\n')
        with self.assertRaises(subject.Rejected):
            self.admit()

    def test_changed_retained_http_record_invalidates_reuse(self):
        self.captured()
        path = self.capture_directory / "emulator-head-0.stderr.original"
        path.write_bytes(path.read_bytes().replace(b"SSL_VERIFY_RESULT=0", b"SSL_VERIFY_RESULT=1"))
        with self.assertRaises(subject.Rejected):
            self.admit()

    def test_retained_head_and_get_argv_require_globoff(self):
        self.captured()
        for head in (True, False):
            with self.subTest(head=head):
                label = "emulator-head-0" if head else "emulator"
                path = self.capture_directory / (label + ".json")
                record = subject.json_original(path, self.check)[1]
                self.assertEqual(record["argv"].count("--globoff"), 1)
                record["argv"].remove("--globoff")
                path.write_bytes(runner.json_bytes(record))
                with self.assertRaisesRegex(subject.Rejected, "Original curl did not complete"):
                    subject.retained_transfer(self.capture_directory, "emulator", head, 0, self.check)

    def test_partial_exit0_body_is_not_success_and_original_is_retained(self):
        self.payload_transform = lambda role, head, header, body, status: (header, body[:-1], status, 0)
        result = self.captured(False)
        record = subject.json_original(self.capture_directory / "image.json", self.check)[1]
        self.assertEqual(record["exitCode"], 0)
        self.assertTrue(record["stdoutEof"])
        self.assertEqual(record["retention"], "PARTIAL")
        self.assertEqual((self.capture_directory / "image.body.original").stat().st_size, len(self.archives["image"]) - 1)
        self.assertEqual(result["status"], "INCOMPLETE")

    def test_bad_http_response_keeps_received_header_and_body_prefix(self):
        self.payload_transform = lambda role, head, header, body, status: (
            header.replace(b"200 OK", b"503 Bad"), body, b"curl error\n" + status, 22)
        self.captured(False)
        self.assertGreater((self.capture_directory / "image.headers.original").stat().st_size, 0)
        self.assertGreater((self.capture_directory / "image.body.original").stat().st_size, 0)
        record = subject.json_original(self.capture_directory / "image.json", self.check)[1]
        self.assertEqual(record["exitCode"], 22)
        self.assertNotEqual(record["retention"], "COMPLETE_AUTHENTICATED_TRANSFER")

    def test_exit0_without_pipe_eof_is_incomplete(self):
        self.no_eof = True
        self.capture_directory.mkdir()
        calls = 0
        def bounded():
            nonlocal calls
            calls += 1
            subject.need(calls < 25, "Modeled deadline while stdout remains open")
        transport = subject.CurlCapture(runner, self.capture_directory, self.environment, bounded)
        with self.assertRaises(subject.Rejected):
            transport.run("image", subject.IMAGE_URL)
        record = subject.json_original(self.capture_directory / "image.json", self.check)[1]
        self.assertEqual(record["exitCode"], 0)
        self.assertFalse(record["stdoutEof"])
        self.assertEqual(record["retention"], "PARTIAL")
        self.assertTrue(all(pipe.closed for pipe in self.pipes.values()))

    def test_redirect_download_is_bounded_and_has_one_get(self):
        destination = "https://dl.google.com/android/repository/" + subject.EMULATOR_NAME
        transport = subject.CurlCapture(runner, self.capture_directory, self.environment, self.check)
        calls = []
        def modeled(role, url, head=False, hop=0):
            calls.append((url, head))
            return {"response": {"status": 302 if url == subject.EMULATOR_URL else 200,
                                 "fields": {"location": destination}}}
        transport.run = modeled
        transport.download("emulator")
        self.assertEqual(calls, [(subject.EMULATOR_URL, True), (destination, True), (destination, False)])
        transport.run = lambda *args, **kwargs: {"response": {"status": 302, "fields": {"location": subject.EMULATOR_URL}}}
        with self.assertRaises(subject.Rejected):
            transport.download("emulator")
        calls.clear()
        def endless(role, url, head=False, hop=0):
            calls.append((url, head))
            return {"response": {"status": 302, "fields": {"location": destination + "?hop=" + str(hop)}}}
        transport.run = endless
        with self.assertRaises(subject.Rejected):
            transport.download("emulator")
        self.assertEqual(len(calls), 4)
        self.assertTrue(all(head for url, head in calls))

    def test_failed_capture_and_main_finally_do_not_keep_same_state_lock(self):
        order = []
        lock = SimpleNamespace(acquire=lambda: order.append("acquire"), close=lambda: order.append("close"))
        real_load = subject.controller.load_tool
        with mock.patch.object(subject.controller, "load_tool", side_effect=lambda name: runner if name ==
                               "run-audit-command.py" else real_load(name)), \
                mock.patch.object(runner, "context_at", return_value=(self.state, self.context)), \
                mock.patch.object(runner, "LeafLock", return_value=lock), \
                mock.patch.object(subject.controller, "admit_outer", return_value=PRODUCER), \
                mock.patch.object(subject.os, "getuid", return_value=501), \
                mock.patch.object(subject, "capture", side_effect=subject.Rejected("Modeled failure")), \
                mock.patch.dict(subject.os.environ, {"P2PKIT_AUDIT_STATE_DIR": str(self.state)}):
            with self.assertRaises(subject.Rejected):
                subject.execute(SimpleNamespace(action="capture"))
        self.assertEqual(order, ["acquire", "close"])


if __name__ == "__main__":
    unittest.main()
