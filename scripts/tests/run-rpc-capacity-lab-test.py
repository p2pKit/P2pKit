#!/usr/bin/env python3
"""Offline controls only. No Java, SDK, subprocess workload, network or capacity claims."""

import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("capacity_lab", ROOT / "scripts/run-rpc-capacity-lab.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)
SOURCE = "a" * 40


class LabControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rpc-capacity-controls-")
        self.root = Path(self.temporary.name).resolve()
        self.root.chmod(0o700)

    def tearDown(self):
        self.temporary.cleanup()

    def settings(self):
        return dict(schema="1", role="client", runLabel="unit-test", sourceSha=SOURCE,
                    endpointAddress="10.25.0.2", port="48123", subnets="10.25.0.0/24",
                    interface="eth0", localAddress="10.25.0.3")

    def test_exact_source_and_explicit_private_configuration(self):
        expected = self.settings()
        self.assertEqual(expected, lab.configuration(lab.parse(lab.encode(expected)), SOURCE))
        with self.assertRaises(RuntimeError):
            lab.configuration(expected, "b" * 40)

    def test_refuse_public_loopback_dns_and_unapproved_destinations(self):
        for address in ("127.0.0.1", "8.8.8.8", "169.254.1.2", "example.test", "198.18.0.1", "10.26.0.2", "::1"):
            with self.subTest(address=address), self.assertRaises((RuntimeError, ValueError)):
                lab.configuration({**self.settings(), "endpointAddress": address}, SOURCE)

    def test_invalid_subnets_roles_ports_and_extra_fields_fail_closed(self):
        for changes in ({"role": "mesh"}, {"port": "22"}, {"port": "65536"}, {"port": "04812"},
                        {"subnets": "0.0.0.0/0"}, {"subnets": "10.25.0.1/24"}, {"extra": "unsafe"},
                        {"runLabel": "private-user@example"}, {"interface": "en0;command"}):
            with self.subTest(changes=changes), self.assertRaises((RuntimeError, ValueError)):
                lab.configuration({**self.settings(), **changes}, SOURCE)

    def test_control_parser_rejects_duplicate_fields_and_unbounded_inputs(self):
        for data in (b"x=1\nx=2\n", b"x=\n", b"x=value\r\n", b"x=\0secret\n", b"a" * (lab.LIMIT + 1)):
            with self.subTest(length=len(data)), self.assertRaises(RuntimeError):
                lab.parse(data)

    def test_private_file_round_trip_does_not_replace_without_permission(self):
        path = self.root / "control.txt"
        lab.write_private(path, b"x=1\n")
        self.assertEqual(b"x=1\n", lab.read_private(path))
        self.assertEqual(0o600, path.stat().st_mode & 0o777)
        with self.assertRaises(FileExistsError):
            lab.write_private(path, b"x=2\n")
        lab.write_private(path, b"x=3\n", replace=True)
        self.assertEqual(b"x=3\n", lab.read_private(path))

    def test_concurrent_create_has_one_winner_and_no_stale_temporary_files(self):
        path = self.root / "winner.txt"

        def attempt(number):
            data = f"winner={number}\n".encode()
            try:
                lab.write_private(path, data)
                return data
            except FileExistsError:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            winners = [result for result in executor.map(attempt, range(32)) if result is not None]
        self.assertEqual(1, len(winners))
        self.assertEqual(winners[0], lab.read_private(path))
        self.assertEqual([path], list(self.root.iterdir()))

    def test_unprotected_or_symlinked_paths_are_never_adopted(self):
        path = self.root / "foreign"
        path.mkdir(mode=0o755)
        path.chmod(0o755)  # Do not let the invoking shell's restrictive umask repair this negative fixture.
        with self.assertRaises(RuntimeError):
            lab.private_directory(path)
        link = self.root / "link"
        link.symlink_to(path, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            lab.private_directory(link)
        file = self.root / "control.txt"
        file.symlink_to(path / "absent")
        with self.assertRaises(RuntimeError):
            lab.write_private(file, b"x=1\n", replace=True)
        self.assertFalse((path / "absent").exists())

    def distribution(self):
        directory = self.root / "samples/p2p-sample-rpc/build/capacity-lab"
        directory.mkdir(parents=True)
        (directory / "lab.jar").write_bytes(b"unit-test-only-not-a-runtime")
        manifest = {"schema": 1, "sourceSha": SOURCE, "scope": "SYNTHETIC_LAB_NOT_PUBLICATION_OR_QUALIFICATION",
                    "entries": [{"name": "lab.jar", "sha256": hashlib.sha256((directory / "lab.jar").read_bytes()).hexdigest()}]}
        (directory / "manifest.json").write_text(json.dumps(manifest))
        return directory

    def test_distribution_is_bound_to_real_bytes_order_and_source(self):
        directory = self.distribution()
        with patch.object(lab, "ROOT", self.root):
            self.assertEqual(str(directory / "lab.jar"), lab.classpath(SOURCE))
            with self.assertRaises(RuntimeError):
                lab.classpath("b" * 40)
            (directory / "lab.jar").write_bytes(b"changed")
            with self.assertRaises(RuntimeError):
                lab.classpath(SOURCE)

    def test_distribution_cannot_add_ambient_classes_or_symlinks(self):
        directory = self.distribution()
        (directory / "ambient.jar").symlink_to(directory / "lab.jar")
        with patch.object(lab, "ROOT", self.root), self.assertRaises(RuntimeError):
            lab.classpath(SOURCE)

    def test_missing_native_ownership_or_owner_acknowledgement_refuses_execution(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            lab.owned_context()
        with patch.dict(os.environ, {"P2PKIT_AUDIT_OWNERSHIP_CHAIN": "not-sufficient"}, clear=True):
            with self.assertRaises(RuntimeError):
                lab.owned_context()


if __name__ == "__main__":
    unittest.main(verbosity=2)
