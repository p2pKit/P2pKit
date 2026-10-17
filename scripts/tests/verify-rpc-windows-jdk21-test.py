#!/usr/bin/env python3
"""Offline synthetic archive controls; no JDK download, extraction command or execution."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "verify-rpc-windows-jdk21.py"
SPEC = importlib.util.spec_from_file_location("supplier", SCRIPT)
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)


class SupplierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rpc-jdk-supplier-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.archive = self.root / "supplier.zip"
        self.home = self.root / "jdk"
        self.home.mkdir()
        self.files = {name: ("synthetic:" + name).encode() for name in V.REQUIRED}
        self.files["legal/java.base/LICENSE"] = b"Synthetic license fixture"
        for name, data in self.files.items():
            path = self.home / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.make_archive()

    def make_archive(self, extras=()):
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("jdk-fixture/", b"")
            for name, data in sorted(self.files.items()):
                archive.writestr("jdk-fixture/" + name, data)
            for name, data in extras:
                archive.writestr(name, data)
        self.pin = {"bytes": self.archive.stat().st_size,
                    "sha256": hashlib.sha256(self.archive.read_bytes()).hexdigest()}

    def test_actual_fixed_supplier_descriptor(self):
        pin, digest = V.load_pin()
        self.assertEqual(pin["version"], "21.0.12.1+1")
        self.assertEqual(pin["bytes"], 205073461)
        self.assertEqual(pin["sha256"], "f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e")
        self.assertEqual(pin["source"], "https://github.com/adoptium/jdk21u/commit/1c417fbfc2f70ab03a565b0af0a5a3c6f5e15ad6")
        self.assertTrue(pin["url"].endswith("/" + pin["archive"]))
        self.assertEqual(digest, hashlib.sha256(V.PIN.read_bytes()).hexdigest())
        self.assertNotIn("--pin", SCRIPT.read_text())
        self.assertNotIn("--sha256", SCRIPT.read_text())

    def test_complete_bytes_match_and_deterministic_inventory(self):
        result = V.verify(self.archive, self.home, self.pin)
        rows = [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in sorted(self.files.items())]
        expected = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(result, {"fileCount": len(self.files), "directoryCount": 6,
                                 "bytes": sum(map(len, self.files.values())), "inventorySha256": expected})

    def test_archive_digest_precedes_zip_parsing(self):
        self.archive.write_bytes(b"not a ZIP")
        with patch.object(V.zipfile, "ZipFile", side_effect=AssertionError("must not parse")):
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                V.verify(self.archive, self.home, self.pin)

    def test_unsafe_paths_and_aliases_refused(self):
        for name in ("/absolute", "jdk-fixture/../escape", "jdk-fixture/a//b", "jdk-fixture/a/./b",
                     "jdk-fixture/C:drive", "jdk-fixture/back\\slash", "jdk-fixture/trailing.",
                     "jdk-fixture/trailing ", "jdk-fixture/CON.txt", "jdk-fixture/LPT1", "jdk-fixture/a\nline",
                     "another-root/file", "jdk-fixture/BIN/java.exe", "jdk-fixture/bin"):
            with self.subTest(name=name):
                self.make_archive([(name, b"bad")])
                with self.assertRaises(ValueError):
                    V.verify(self.archive, self.home, self.pin)

    def test_links_special_entries_and_type_disagreement_refused(self):
        for mode, name, low in ((stat.S_IFLNK | 0o777, "link", 0),
                                (stat.S_IFIFO | 0o600, "pipe", 0),
                                (stat.S_IFREG | 0o600, "directory/", 0),
                                (stat.S_IFDIR | 0o700, "not-directory", 0),
                                (stat.S_IFREG | 0o600, "reparse", 0x400)):
            with self.subTest(name=name):
                entry = zipfile.ZipInfo("jdk-fixture/" + name)
                entry.create_system = 3
                entry.external_attr = (mode << 16) | low
                self.make_archive([(entry, b"")])
                with self.assertRaises(ValueError):
                    V.verify(self.archive, self.home, self.pin)

    def test_duplicate_encrypted_and_hidden_names_refused(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # zipfile warns while constructing this negative input.
            self.make_archive([("jdk-fixture/bin/java.exe", b"duplicate")])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            V.verify(self.archive, self.home, self.pin)
        self.make_archive()
        with zipfile.ZipFile(self.archive) as archive:
            entries = archive.infolist()
            for change in ("encryption", "truncation"):
                with self.subTest(change=change):
                    entry = entries[-1]
                    flags, original = entry.flag_bits, entry.orig_filename
                    if change == "encryption":
                        entry.flag_bits |= 1
                    else:
                        entry.orig_filename += "\0hidden"
                    with self.assertRaises(ValueError):
                        V.inventory(archive)
                    entry.flag_bits, entry.orig_filename = flags, original

    def test_crc_mismatch_refused_even_with_matching_synthetic_archive_pin(self):
        data = bytearray(self.archive.read_bytes())
        index = data.index(b"PK\x01\x02", data.index(b"PK\x01\x02") + 4)
        data[index + 16] ^= 1  # Change one central-directory CRC, not the member bytes.
        self.archive.write_bytes(data)
        self.pin = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        with self.assertRaises(zipfile.BadZipFile):
            V.verify(self.archive, self.home, self.pin)

    def test_missing_extra_and_modified_home_files_refused(self):
        target = self.home / "bin/java.exe"
        original = target.read_bytes()
        for change in ("missing", "modified", "extra", "extra-directory"):
            with self.subTest(change=change):
                if change == "missing":
                    target.unlink()
                elif change == "modified":
                    target.write_bytes(b"X" * len(original))
                elif change == "extra":
                    (self.home / "untrusted.dll").write_bytes(b"extra")
                else:
                    (self.home / "unexpected").mkdir()
                with self.assertRaises(ValueError):
                    V.verify(self.archive, self.home, self.pin)
                target.write_bytes(original)
                (self.home / "untrusted.dll").unlink(missing_ok=True)
                if (self.home / "unexpected").exists():
                    (self.home / "unexpected").rmdir()

    def test_home_links_and_linked_ancestor_refused(self):
        target = self.home / "bin/java.exe"
        target.unlink()
        target.symlink_to(self.home / "bin/javac.exe")
        with self.assertRaisesRegex(ValueError, "Linked"):
            V.verify(self.archive, self.home, self.pin)
        target.unlink()
        target.write_bytes(self.files["bin/java.exe"])
        alias = self.root / "alias"
        alias.symlink_to(self.home, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Linked"):
            V.verify(self.archive, alias, self.pin)

    def test_required_tools_and_expansion_bounds_refused(self):
        self.files.pop("bin/jpackage.exe")
        self.make_archive()
        with self.assertRaisesRegex(ValueError, "Required JDK tools"):
            V.verify(self.archive, self.home, self.pin)
        self.files["bin/jpackage.exe"] = (self.home / "bin/jpackage.exe").read_bytes()
        self.make_archive()
        for constant in ("MAX_ENTRIES", "MAX_EXPANDED"):
            with self.subTest(constant=constant), patch.object(V, constant, 1):
                with self.assertRaises(ValueError):
                    V.verify(self.archive, self.home, self.pin)

    def test_directory_walk_failure_is_not_ignored(self):
        def refused(*args, **kwargs):
            kwargs["onerror"](PermissionError("synthetic private path"))
            return iter(())
        with patch.object(V.os, "walk", side_effect=refused):
            with self.assertRaises(PermissionError):
                V.verify(self.archive, self.home, self.pin)

    def test_archive_change_after_digest_refused(self):
        digest = V.file_digest
        def changed(path, maximum):
            result = digest(path, maximum)
            if path == self.archive:
                path.write_bytes(b"changed archive")
            return result
        with patch.object(V, "file_digest", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "Archive identity changed"):
                V.verify(self.archive, self.home, self.pin)

    def test_home_change_after_its_read_refused(self):
        digest = V.file_digest
        def changed(path, maximum):
            result = digest(path, maximum)
            if path == self.home / "bin/java.exe":
                path.write_bytes(b"changed after its read")
            return result
        with patch.object(V, "file_digest", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "JDK home changed"):
                V.verify(self.archive, self.home, self.pin)

    def test_new_only_result_has_source_binding_and_no_host_path(self):
        output = self.root / "result.json"
        pin_hash = hashlib.sha256(V.PIN.read_bytes()).hexdigest()
        argv = [str(SCRIPT), "--archive", str(self.archive), "--jdk-home", str(self.home), "--output", str(output)]
        with patch.object(V, "load_pin", return_value=(self.pin, pin_hash)), patch.object(V.sys, "argv", argv):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(V.main(), 0)
            self.assertEqual(stdout.getvalue(), "JDK_SUPPLIER_BYTES_PASS\n")
            before = output.read_bytes()
            document = json.loads(before)
            self.assertEqual(document["source"], {"pinSha256": pin_hash,
                             "verifierSha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest()})
            self.assertIn("NOT_INSTALLED_AUTHORITY", document["scope"])
            self.assertNotIn(str(self.root), before.decode())
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(V.main(), 1)
            self.assertEqual(stderr.getvalue(), "JDK_SUPPLIER_BYTES_REFUSED\n")
            self.assertEqual(output.read_bytes(), before)

    def test_result_inside_home_and_failed_archive_leave_no_result(self):
        for output in (self.home / "result.json", self.root / "result.json"):
            with self.subTest(output=output.name):
                argv = [str(SCRIPT), "--archive", str(self.archive), "--jdk-home", str(self.home),
                        "--output", str(output)]
                with patch.object(V.sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()) as stderr:
                    self.assertEqual(V.main(), 1)
                self.assertEqual(stderr.getvalue(), "JDK_SUPPLIER_BYTES_REFUSED\n")
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
