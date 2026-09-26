#!/usr/bin/env python3
"""Bounded synthetic originals and fake-GPG controls; no keys, builds or network.

The certificate fixture has OpenPGP framing but deliberately is NOT a usable
cryptographic key. Fake GPG results cannot qualify a real signature or release.
"""

import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("public_central_evidence", ROOT / "scripts/central_bundle_evidence.py")
E = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E)
SOURCE, TREE, VERSION = "a" * 40, "b" * 40, "0.8.0"
# Independent roster, not constructed from the candidate's COORDINATES/roster.
PORTABLE = {
    "p2p-core": ".jar", "p2p-core-jvm": ".jar", "p2p-core-android": ".aar",
    "p2p-transport-lan": ".jar", "p2p-transport-lan-jvm": ".jar", "p2p-transport-lan-android": ".aar",
    "p2p-network-provisioning-android": ".jar", "p2p-network-provisioning-android-android": ".aar",
    "p2p-network-provisioning-desktop": ".jar",
}
BASES = set()
for coordinate, extension in [*PORTABLE.items(), *[(module + "-" + target, ".klib")
                          for module in ("p2p-core", "p2p-transport-lan") for target in ("iosarm64", "iossimulatorarm64", "iosx64")]]:
    suffixes = [extension, "-sources.jar", "-javadoc.jar", ".pom", ".module"]
    if extension == ".klib":
        suffixes += ["-metadata.jar"]
        if coordinate.startswith("p2p-transport-lan-"):
            suffixes += ["-cinterop-p2pkit_nw.klib"]
    BASES.update(f"io/github/apdelrahman1911/{coordinate}/{VERSION}/{coordinate}-{VERSION}{suffix}" for suffix in suffixes)


def packet(tag, body, old=False):
    return (bytes([0x80 | tag << 2 | 2]) if old else bytes([0xC0 | tag, 255])) + struct.pack(">I", len(body)) + body


def armor(binary):
    return b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n" + base64.encodebytes(binary) + b"-----END PGP PUBLIC KEY BLOCK-----\n"


PRIMARY_BODY = b"\x04\x00\x00\x00\x01\x01SYNTHETIC-NONKEY-FIXTURE"
PRIMARY_PACKET = packet(6, PRIMARY_BODY)
PUBLIC = armor(PRIMARY_PACKET + packet(13, b"Synthetic test fixture; not a usable key"))
FINGERPRINT = hashlib.sha1(b"\x99" + len(PRIMARY_BODY).to_bytes(2, "big") + PRIMARY_BODY).hexdigest().upper()
SUBKEY = "C" * 40


def status(signer=FINGERPRINT, primary=FINGERPRINT):
    suffix = " " + primary if primary is not None else ""
    return f"[GNUPG:] VALIDSIG {signer} 2026-09-26 1790410000 0 4 0 1 10 00{suffix}\n".encode()


def listing(primary=FINGERPRINT, subkey=None, validity="-"):
    def record(kind, identity):
        return f"{kind}:{validity}:4096:1:0000000000000000:1:0:::::sc:\nfpr:::::::::{identity}:\n"
    return (record("pub", primary) + (record("sub", subkey) if subkey else "")).encode()


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="p2pkit-public-central-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundle = self.root / "p2pkit-0.8.0-central-bundle.zip"
        self.manifest = self.bundle.with_suffix(".manifest.sha256")
        self.summary = self.bundle.with_suffix(".summary.json")
        self.public = self.bundle.with_suffix(".public.asc")
        self.files = {}
        for name in BASES:
            data = b"SYNTHETIC ORIGINAL, NOT A BUILT ARTIFACT: " + name.encode()
            self.files[name] = data
            self.files[name + ".asc"] = b"SYNTHETIC DETACHED SIGNATURE, NOT CRYPTOGRAPHIC"
            for algorithm in ("md5", "sha1", "sha256", "sha512"):
                self.files[name + "." + algorithm] = hashlib.new(algorithm, data).hexdigest().encode() + b"\n"
        self.write()

    def write(self, files=None, *, entries=None, mutate_zip=None, public=PUBLIC):
        files = self.files if files is None else files
        self.public.write_bytes(public)
        output = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # Deliberately authored duplicate ZIP control.
            with zipfile.ZipFile(output, "w") as archive:
                for name, data in (sorted(files.items()) if entries is None else entries):
                    if isinstance(name, zipfile.ZipInfo):
                        info = name
                    else:
                        info = zipfile.ZipInfo(name)
                        info.external_attr = (stat.S_IFREG | 0o600) << 16
                        info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, data)
        binary = output.getvalue()
        if mutate_zip is not None:
            binary = mutate_zip(binary)
        self.bundle.write_bytes(binary)
        self.manifest.write_text("".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n" for name, data in sorted(files.items())))
        document = {"schemaVersion": 2, "group": "io.github.apdelrahman1911", "version": VERSION,
                    "signingKeyFingerprint": FINGERPRINT, "bundleFile": self.bundle.name,
                    "bundleSha256": hashlib.sha256(binary).hexdigest(), "bundleSizeBytes": len(binary), "signedFiles": 84,
                    "sourceSha": SOURCE, "sourceTree": TREE, "manifestSha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
                    "publicKeyFile": self.public.name, "publicKeySha256": hashlib.sha256(public).hexdigest()}
        self.summary.write_text(json.dumps(document))
        return document

    def inspect(self, **options):
        return E.inspect(self.bundle, self.manifest, self.summary, self.public, SOURCE, TREE, VERSION, **options)

    def replace_summary(self, **changes):
        document = json.loads(self.summary.read_text())
        document.update(changes)
        self.summary.write_text(json.dumps(document))

    def fake_gpg(self, arguments, **options):
        self.gpg_calls.append((arguments, options))
        for option in ("--no-options", "--batch", "--no-autostart", "--no-auto-key-retrieve", "--no-auto-key-import"):
            self.assertIn(option, arguments)
        self.assertEqual({"PATH", "HOME", "GNUPGHOME", "LC_ALL"}, set(options["env"]))
        self.assertEqual(subprocess.DEVNULL, options["stdin"])
        self.assertEqual(subprocess.DEVNULL, options["stderr"])
        self.assertEqual(20, options["timeout"])
        home = Path(arguments[arguments.index("--homedir") + 1])
        self.assertEqual(0o700, stat.S_IMODE(home.stat().st_mode))
        self.assertEqual(PUBLIC, (home / "public.asc").read_bytes())
        if "--import" in arguments:
            return subprocess.CompletedProcess(arguments, 0, b"")
        if "--list-keys" in arguments:
            return subprocess.CompletedProcess(arguments, 0, listing(subkey=SUBKEY))
        self.assertIn("--verify", arguments)
        self.assertIn(Path(arguments[-1]).read_bytes(), self.files.values())
        self.assertEqual(b"SYNTHETIC DETACHED SIGNATURE, NOT CRYPTOGRAPHIC", Path(arguments[-2]).read_bytes())
        return subprocess.CompletedProcess(arguments, 0, status(SUBKEY))

    def test_complete_roster_matches_independent_inherited_mac_gate(self):
        self.assertEqual(84, len(BASES))
        self.assertEqual(BASES, E.roster(VERSION))
        script = (ROOT / "scripts/check-publish-artifacts.sh").read_text()
        self.assertEqual(PORTABLE, dict(re.findall(r"^check +(p2p-\S+) +(\.jar|\.aar)$", script, re.MULTILINE)))
        self.assertIn('for target in iosarm64 iossimulatorarm64 iosx64;', script)
        self.assertIn('required_artifacts+=("$artifact-$VERSION-metadata.jar")', script)
        self.assertIn('required_artifacts+=("$artifact-$VERSION-cinterop-p2pkit_nw.klib")', script)

    def test_structure_only_receipt_cannot_claim_signatures_or_publication(self):
        with mock.patch.object(E.subprocess, "run", side_effect=AssertionError("Unexpected GPG")):
            receipt = self.inspect(verify_signatures=False)
        self.assertEqual("UNVERIFIED_SYNTHETIC_STRUCTURE", receipt["scope"])
        self.assertIs(False, receipt["signaturesVerified"])
        self.assertEqual([], receipt["signerFingerprints"])
        self.assertEqual((15, 84, 504), (receipt["coordinates"], receipt["signedFiles"], receipt["memberCount"]))
        self.assertEqual(set(self.files), {x["path"] for x in receipt["members"]})
        self.assertEqual(SOURCE, receipt["sourceSha"])
        self.assertEqual(TREE, receipt["sourceTree"])
        self.assertNotIn("PUBLISHED", json.dumps(receipt))

    def test_full_fake_backend_requires_all_84_exact_detached_signatures(self):
        self.gpg_calls = []
        with mock.patch.object(E.shutil, "which", return_value="/synthetic-only/gpg"), \
                mock.patch.object(E.subprocess, "run", side_effect=self.fake_gpg):
            receipt = self.inspect()
        self.assertEqual(86, len(self.gpg_calls))
        self.assertEqual("VERIFIED_PUBLIC_SIGNATURES", receipt["scope"])
        self.assertIs(True, receipt["signaturesVerified"])
        self.assertEqual([SUBKEY], receipt["signerFingerprints"])
        self.assertTrue(all(not Path(call[1]["env"]["GNUPGHOME"]).exists() for call in self.gpg_calls))

    def test_gpg_validsig_with_nonzero_exit_is_not_success(self):
        self.gpg_calls = []
        def failed(arguments, **options):
            result = self.fake_gpg(arguments, **options)
            if "--verify" in arguments:
                result.returncode = 2
            return result
        with mock.patch.object(E.shutil, "which", return_value="/synthetic-only/gpg"), \
                mock.patch.object(E.subprocess, "run", side_effect=failed), \
                self.assertRaisesRegex(ValueError, "nonzero"):
            self.inspect()
        self.assertEqual(3, len(self.gpg_calls))

    def test_original_source_version_hash_names_and_summary_schema_fail_closed(self):
        changes = [{"schemaVersion": 1}, {"schemaVersion": True}, {"sourceSha": TREE}, {"sourceTree": SOURCE},
                   {"version": "0.8.1"}, {"group": "io.github.p2pkit"}, {"bundleFile": "another.zip"},
                   {"bundleSha256": "0" * 64}, {"bundleSizeBytes": True}, {"bundleSizeBytes": 1},
                   {"signedFiles": 45}, {"signedFiles": True}, {"manifestSha256": "0" * 64},
                   {"publicKeyFile": "different.asc"}, {"publicKeySha256": "0" * 64},
                   {"signingKeyFingerprint": "D" * 40}, {"unexpected": "field"}]
        original = self.summary.read_bytes()
        for change in changes:
            self.summary.write_bytes(original)
            self.replace_summary(**change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.inspect(verify_signatures=False)

    def test_duplicate_json_missing_fields_and_wrong_argument_bindings(self):
        original = json.loads(self.summary.read_text())
        for field in original:
            document = copy.deepcopy(original)
            del document[field]
            self.summary.write_text(json.dumps(document))
            with self.subTest(missing=field), self.assertRaises(ValueError):
                self.inspect(verify_signatures=False)
        self.summary.write_text(json.dumps(original)[:-1] + ',"schemaVersion":2}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.inspect(verify_signatures=False)
        self.write()
        for source, tree, version in ((SOURCE.upper(), TREE, VERSION), (SOURCE, "b" * 39, VERSION),
                                      (SOURCE, TREE, "0.8.0-SNAPSHOT"), (SOURCE, TREE, "0.8.00")):
            with self.subTest(version=version), self.assertRaises(ValueError):
                E.inspect(self.bundle, self.manifest, self.summary, self.public, source, tree, version, verify_signatures=False)
        with self.assertRaises(ValueError):
            self.inspect(verify_signatures="false")

    def test_every_signature_checksum_and_native_roster_member_is_required(self):
        base = "io/github/apdelrahman1911/p2p-transport-lan-iosx64/0.8.0/p2p-transport-lan-iosx64-0.8.0-cinterop-p2pkit_nw.klib"
        for suffix in ("", ".asc", ".md5", ".sha1", ".sha256", ".sha512"):
            files = dict(self.files)
            del files[base + suffix]
            self.write(files)
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                self.inspect(verify_signatures=False)
        files = {name: data for name, data in self.files.items() if "-ios" not in name}
        self.write(files)
        with self.assertRaises(ValueError):
            self.inspect(verify_signatures=False)

    def test_checksum_sidecar_content_is_verified_not_just_manifest_hash(self):
        base = min(BASES)
        for algorithm, length in (("md5", 32), ("sha1", 40), ("sha256", 64), ("sha512", 128)):
            files = dict(self.files)
            files[base + "." + algorithm] = b"0" * length + b"\n"
            self.write(files)
            with self.subTest(algorithm=algorithm), self.assertRaisesRegex(ValueError, "checksum sidecar"):
                self.inspect(verify_signatures=False)

    def test_manifest_order_duplicates_paths_and_content_hashes_are_exact(self):
        original = self.manifest.read_text().splitlines(keepends=True)
        changes = [list(reversed(original)), original + [original[0]], original[:-1],
                   ["0" * 64 + original[0][64:]] + original[1:],
                   [original[0].replace("  io/", "  ../io/")] + original[1:],
                   [original[0].rstrip("\n")] + original[1:]]
        for rows in changes:
            raw = "".join(rows).encode()
            self.manifest.write_bytes(raw)
            self.replace_summary(manifestSha256=hashlib.sha256(raw).hexdigest())
            with self.subTest(first=rows[0][:68]), self.assertRaises(ValueError):
                self.inspect(verify_signatures=False)

    def test_zip_duplicates_traversal_unknown_and_linked_members_reject(self):
        original = sorted(self.files.items())
        for name in (original[0][0], "../outside", "/absolute", "io/github/apdelrahman1911/unreviewed/extra"):
            self.write(entries=original + [(name, b"unexpected")])
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.inspect(verify_signatures=False)
        for kind in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR):
            entry = zipfile.ZipInfo(original[0][0])
            entry.external_attr = (kind | 0o600) << 16
            self.write(entries=[(entry, original[0][1])] + original[1:])
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.inspect(verify_signatures=False)

    def test_zip_encryption_zip64_comments_prefix_and_trailing_bytes_reject(self):
        def encrypted(binary):
            data = bytearray(binary)
            for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
                index = data.index(signature) + offset
                data[index] |= 1
            return bytes(data)
        for mutation in (encrypted, lambda data: b"prefix" + data, lambda data: data + b"suffix"):
            self.write(mutate_zip=mutation)
            with self.assertRaises(ValueError):
                self.inspect(verify_signatures=False)
        original = sorted(self.files.items())
        for option in ("zip64", "comment", "unsupported"):
            entry = zipfile.ZipInfo(original[0][0])
            if option == "zip64":
                entry.extra = struct.pack("<HHQ", 1, 8, 1)
            elif option == "comment":
                entry.comment = b"unreviewed metadata"
            else:
                entry.compress_type = zipfile.ZIP_BZIP2
            self.write(entries=[(entry, original[0][1])] + original[1:])
            with self.subTest(option=option), self.assertRaises(ValueError):
                self.inspect(verify_signatures=False)

    def test_safe_directory_entries_are_optional_but_cannot_contain_payloads(self):
        directory = zipfile.ZipInfo("io/github/apdelrahman1911/")
        directory.external_attr = (stat.S_IFDIR | 0o700) << 16
        self.write(entries=[(directory, b"")] + sorted(self.files.items()))
        self.assertEqual(504, self.inspect(verify_signatures=False)["memberCount"])
        self.write(entries=[(directory, b"hidden bytes")] + sorted(self.files.items()))
        with self.assertRaises(ValueError):
            self.inspect(verify_signatures=False)

    def test_limits_and_linked_originals_are_checked_before_unbounded_reads(self):
        for name, bound in (("MAX_MEMBER", 1), ("MAX_EXPANDED", 1), ("MAX_METADATA", 1), ("MAX_BUNDLE", 100)):
            with self.subTest(limit=name), mock.patch.object(E, name, bound), self.assertRaises(ValueError):
                self.inspect(verify_signatures=False)
        saved = self.root / "saved-public.asc"
        self.public.rename(saved)
        self.public.symlink_to(saved)
        with self.assertRaises(ValueError):
            self.inspect(verify_signatures=False)
        self.public.unlink()
        os.link(saved, self.public)
        with self.assertRaises(ValueError):
            self.inspect(verify_signatures=False)

    def test_public_certificate_rejects_secret_packets_under_public_armor(self):
        for old in (False, True):
            for tag in (5, 7):
                raw = armor(PRIMARY_PACKET + packet(tag, b"synthetic forbidden packet, no secret", old=old))
                self.write(public=raw)
                with self.subTest(old=old, tag=tag), mock.patch.object(E.subprocess, "run") as backend, \
                        self.assertRaisesRegex(ValueError, "Secret-key packets"):
                    self.inspect()
                backend.assert_not_called()

    def test_public_packet_framing_primary_and_exact_armor_hash(self):
        self.assertEqual(FINGERPRINT, E.public_key_fingerprint(PUBLIC))
        self.assertEqual(FINGERPRINT, E.public_key_fingerprint(armor(packet(6, PRIMARY_BODY, old=True))))
        for binary in (PRIMARY_PACKET + PRIMARY_PACKET, PRIMARY_PACKET[:-1], b"\xc6\xe0payload", b"\x9bpayload",
                       packet(13, b"wrong first packet"), PRIMARY_PACKET + packet(8, b"compressed contents")):
            with self.subTest(binary=binary[:2]), self.assertRaises(ValueError):
                E.public_key_fingerprint(armor(binary))
        self.public.write_bytes(PUBLIC.replace(b"\n", b"\r\n"))
        with self.assertRaisesRegex(ValueError, "hash differs"):
            self.inspect(verify_signatures=False)

    def test_signature_identity_requires_one_valid_primary_bound_signature(self):
        self.assertEqual(SUBKEY, E.signature_identity(status(SUBKEY), FINGERPRINT, {FINGERPRINT, SUBKEY}))
        self.assertEqual(FINGERPRINT, E.signature_identity(status(primary=None), FINGERPRINT, {FINGERPRINT}))
        failures = [status(SUBKEY, primary=None), status(SUBKEY, primary="D" * 40), status("D" * 40),
                    status() + status(), b"[GNUPG:] GOODSIG short-id\n", status().replace(b" 00 ", b" 01 ")]
        failures += [status() + f"[GNUPG:] {tag} failure\n".encode() for tag in
                     ("BADSIG", "ERRSIG", "NO_PUBKEY", "EXPKEYSIG", "REVKEYSIG", "KEYEXPIRED", "FAILURE", "NODATA")]
        for value in failures:
            with self.subTest(status=value[:24]), self.assertRaises(ValueError):
                E.signature_identity(value, FINGERPRINT, {FINGERPRINT, SUBKEY})
        trailing = status() + b"[GNUPG:] NOTATION_DATA trailing-status\n" * 20000
        self.assertEqual(FINGERPRINT, E.signature_identity(trailing, FINGERPRINT, {FINGERPRINT}))

    def test_missing_failing_oversized_or_timed_out_gpg_is_fatal(self):
        with mock.patch.object(E.shutil, "which", return_value=None), self.assertRaises(ValueError):
            self.inspect()
        for output in (subprocess.CompletedProcess([], 2, b""),
                       subprocess.CompletedProcess([], 0, b"x" * (E.MAX_GPG_OUTPUT + 1))):
            with mock.patch.object(E.shutil, "which", return_value="/synthetic-only/gpg"), \
                    mock.patch.object(E.subprocess, "run", return_value=output), self.assertRaises(ValueError):
                self.inspect()
        with mock.patch.object(E.shutil, "which", return_value="/synthetic-only/gpg"), \
                mock.patch.object(E.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic-only/gpg", 20)), \
                self.assertRaises(ValueError):
            self.inspect()

    def test_wrong_missing_ambiguous_or_revoked_imported_primary_cannot_verify(self):
        self.gpg_calls = []
        for output in (listing(primary="D" * 40), listing() + listing(), listing(validity="r"), b"", b"pub:-:4096:1:\n"):
            def changed(arguments, **options):
                result = self.fake_gpg(arguments, **options)
                if "--list-keys" in arguments:
                    result.stdout = output
                return result
            with self.subTest(listing=output[:12]), mock.patch.object(E.shutil, "which", return_value="/synthetic-only/gpg"), \
                    mock.patch.object(E.subprocess, "run", side_effect=changed), self.assertRaises(ValueError):
                self.inspect()


class BuilderSourceTests(unittest.TestCase):
    def test_signature_parser_consumes_trailing_status_and_rejects_ambiguous_or_error_status(self):
        source = (ROOT / "scripts/build-central-portal-bundle.sh").read_text()
        parser = re.search(r"^valid_signature_fingerprint\(\) \{\n.*?^\}", source, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(parser)
        script = parser[0] + '\nstatus=$(cat)\nvalid_signature_fingerprint "$status"\n'
        cases = [(status(), FINGERPRINT), (status(SUBKEY), FINGERPRINT),
                 (status() + b"[GNUPG:] NOTATION_DATA trailing-status\n" * 20000, FINGERPRINT),
                 (status() + status(), ""), (status() + b"[GNUPG:] FAILURE failure\n", ""),
                 (b"[GNUPG:] VALIDSIG not-a-full-fingerprint\n", "")]
        for raw, expected in cases:
            result = subprocess.run(["bash", "-c", script], input=raw, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=5, check=False)
            self.assertEqual(0, result.returncode, result.stderr.decode())
            self.assertEqual(expected, result.stdout.decode().strip())

    def test_builder_retains_only_public_export_and_actual_gpg_exit_with_clean_source(self):
        source = (ROOT / "scripts/build-central-portal-bundle.sh").read_text()
        self.assertIn('--armor --export "$expected_fingerprint"', source)
        self.assertNotIn("--export-secret", source)
        self.assertIn('|| signature_status=$?', source)
        self.assertIn('"$signature_status" -ne 0 || "$signature_fingerprint" != "$expected_fingerprint"', source)
        self.assertNotIn('} || true)', source)
        self.assertIn('[[ $checked -eq 84 ]]', source)
        self.assertIn('"$ROOT/scripts/check-publish-artifacts.sh" "$REPOSITORY"', source)
        self.assertIn('git -C "$ROOT" status --porcelain --untracked-files=all', source)
        self.assertIn('source changed while producing signed original evidence', source)
        for field in ("sourceSha", "sourceTree", "manifestSha256", "publicKeyFile", "publicKeySha256"):
            self.assertIn(field + ": $" + field, source)


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
