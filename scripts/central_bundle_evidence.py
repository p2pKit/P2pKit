#!/usr/bin/env python3
"""Inspect retained Central bytes using only their original public certificate.

This is not a build, a Central publication-status check, or a reconstruction of
the original embedded-JmDNS producer. The caller must bind these originals and
their hashes to the original source/run/attempt and inherited build gates.
"""

import argparse
import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile


GROUP = "io.github.apdelrahman1911"
GROUP_PATH = GROUP.replace(".", "/")
MAX_BUNDLE = 1024 ** 3  # Existing Portal bound: strictly less than 1 GiB.
MAX_EXPANDED = 2 * MAX_BUNDLE
MAX_MEMBER = 256 * 1024 ** 2
MAX_METADATA = 1024 ** 2
MAX_PUBLIC_KEY = 256 * 1024
MAX_SIGNATURE = 64 * 1024
MAX_GPG_OUTPUT = 1024 ** 2
GPG_TIMEOUT = 20
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
FINGERPRINT = re.compile(r"(?:[A-F0-9]{40}|[A-F0-9]{64})")
VERSION = re.compile(r"(?:0|[1-9][0-9]?)\.(?:0|[1-9][0-9]?)\.(?:0|[1-9][0-9]?)(?:-(?:alpha|beta|rc)[1-9][0-9]?)?")
CHECKSUMS = {"md5": 32, "sha1": 40, "sha256": 64, "sha512": 128}
# Independent transcription of check-publish-artifacts.sh's complete macOS
# roster. The 9 portable and 6 native coordinates contain 84 signed members.
COORDINATES = {
    "p2p-core": ".jar", "p2p-core-jvm": ".jar", "p2p-core-android": ".aar",
    "p2p-transport-lan": ".jar", "p2p-transport-lan-jvm": ".jar", "p2p-transport-lan-android": ".aar",
    "p2p-network-provisioning-android": ".jar", "p2p-network-provisioning-android-android": ".aar",
    "p2p-network-provisioning-desktop": ".jar",
    "p2p-core-iosarm64": ".klib", "p2p-core-iossimulatorarm64": ".klib", "p2p-core-iosx64": ".klib",
    "p2p-transport-lan-iosarm64": ".klib", "p2p-transport-lan-iossimulatorarm64": ".klib",
    "p2p-transport-lan-iosx64": ".klib",
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def roster(version):
    need(type(version) is str and VERSION.fullmatch(version), "Noncanonical or snapshot release version")
    result = set()
    for coordinate, extension in COORDINATES.items():
        suffixes = [extension, "-sources.jar", "-javadoc.jar", ".pom", ".module"]
        if extension == ".klib":
            suffixes.append("-metadata.jar")
            if coordinate.startswith("p2p-transport-lan-"):
                suffixes.append("-cinterop-p2pkit_nw.klib")
        result.update(f"{GROUP_PATH}/{coordinate}/{version}/{coordinate}-{version}{suffix}" for suffix in suffixes)
    need(len(COORDINATES) == 15 and len(result) == 84, "Maintained complete publication roster changed")
    return result


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "Duplicate JSON field")
        result[key] = value
    return result


@contextlib.contextmanager
def regular_input(path, limit):
    path = Path(path)
    need(not path.is_symlink(), "Original input must not be a symbolic link")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= limit,
             "Original input is empty, linked, nonregular or oversized")
        yield stream, before.st_size
        after = os.fstat(stream.fileno())
        attributes = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        need(all(getattr(before, key) == getattr(after, key) for key in attributes), "Original input changed during inspection")


def bounded_bytes(path, limit):
    with regular_input(path, limit) as (stream, size):
        raw = stream.read(limit + 1)
        need(len(raw) == size, "Original input size changed")
        return raw


def public_key_fingerprint(raw):
    """Reject secret/unsupported packets before a public-only GPG import.

    Packet framing and the primary fingerprint are checked here; GPG must still
    validate the certificate and every detached signature. No secret data is
    returned or included in errors.
    """
    need(type(raw) is bytes and 0 < len(raw) <= MAX_PUBLIC_KEY, "Public certificate exceeds bound")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeError as error:
        raise ValueError("Public certificate must be ASCII armor") from error
    need(len(lines) >= 4 and lines[0] == "-----BEGIN PGP PUBLIC KEY BLOCK-----" and
         lines[-1] == "-----END PGP PUBLIC KEY BLOCK-----", "Expected exactly one public-key armor block")
    position = 1
    while position < len(lines) - 1 and lines[position]:
        need(re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*: [\x20-\x7e]{0,200}", lines[position]), "Malformed armor header")
        position += 1
    need(position < len(lines) - 2, "Missing public armor body")
    body = lines[position + 1:-1]
    checksum = body.pop() if body and body[-1].startswith("=") else None
    need(body and all(re.fullmatch(r"[A-Za-z0-9+/]{1,76}={0,2}", line) for line in body), "Malformed public armor body")
    try:
        binary = base64.b64decode("".join(body), validate=True)
    except ValueError as error:
        raise ValueError("Invalid public armor encoding") from error
    if checksum is not None:
        need(re.fullmatch(r"=[A-Za-z0-9+/]{4}", checksum), "Malformed public armor checksum")
        crc = 0xB704CE
        for byte in binary:
            crc ^= byte << 16
            for _ in range(8):
                crc <<= 1
                if crc & 0x1000000:
                    crc ^= 0x1864CFB
        need(base64.b64decode(checksum[1:]) == (crc & 0xFFFFFF).to_bytes(3, "big"), "Public armor checksum differs")
    position, packets, primary = 0, 0, None
    while position < len(binary):
        first = binary[position]
        position += 1
        need(first & 0x80, "Invalid public packet header")
        if first & 0x40:
            tag = first & 63
            need(position < len(binary), "Truncated public packet length")
            length = binary[position]
            position += 1
            if 192 <= length < 224:
                need(position < len(binary), "Truncated public packet length")
                length = ((length - 192) << 8) + binary[position] + 192
                position += 1
            elif length == 255:
                need(position + 4 <= len(binary), "Truncated public packet length")
                length = int.from_bytes(binary[position:position + 4], "big")
                position += 4
            else:
                need(length < 192, "Partial public packet lengths are not admitted")
        else:
            tag, width = (first >> 2) & 15, first & 3
            need(width != 3, "Indeterminate public packet lengths are not admitted")
            width = 1 << width
            need(position + width <= len(binary), "Truncated public packet length")
            length = int.from_bytes(binary[position:position + width], "big")
            position += width
        need(tag not in (5, 7), "Secret-key packets are forbidden in retained public evidence")
        need(tag in (2, 6, 13, 14, 17) and (packets != 0 or tag == 6), "Unsupported public certificate packet")
        need(0 < length <= MAX_PUBLIC_KEY and position + length <= len(binary), "Truncated/oversized public packet")
        packet = binary[position:position + length]
        position += length
        packets += 1
        need(packets <= 128, "Too many public certificate packets")
        if tag == 6:
            need(primary is None and len(packet) >= 6, "Missing/ambiguous primary public certificate")
            if packet[0] == 4:
                need(length < 65536, "Oversized v4 primary public packet")
                primary = hashlib.sha1(b"\x99" + length.to_bytes(2, "big") + packet).hexdigest().upper()
            else:
                need(packet[0] in (5, 6), "Unsupported primary public-key version")
                prefix = b"\x9a" if packet[0] == 5 else b"\x9b"
                primary = sha256(prefix + length.to_bytes(4, "big") + packet).upper()
    need(primary is not None, "Missing primary public certificate")
    return primary


def signature_identity(status, expected_fingerprint, allowed_fingerprints):
    """Parse the complete status stream; a VALIDSIG line alone is not success."""
    rows = []
    bad = {"BADSIG", "ERRSIG", "NO_PUBKEY", "EXPSIG", "EXPKEYSIG", "REVKEYSIG", "KEYEXPIRED", "SIGEXPIRED", "FAILURE", "ERROR", "NODATA"}
    for line in status.decode("utf-8", errors="replace").splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[0] != "[GNUPG:]":
            continue
        need(fields[1] not in bad, "GPG reported an invalid, expired or revoked signature")
        if fields[1] == "VALIDSIG":
            rows.append(fields)
    need(len(rows) == 1 and len(rows[0]) in (11, 12), "Missing/ambiguous complete VALIDSIG status")
    row = rows[0]
    signer = row[2].upper()
    primary = row[11].upper() if len(row) == 12 else signer
    need(FINGERPRINT.fullmatch(signer) and FINGERPRINT.fullmatch(primary) and
         primary == expected_fingerprint and signer in allowed_fingerprints and
         row[10] == "00", "Detached signature fingerprint/primary binding differs")
    return signer


def verify_public_signatures(public_key, pairs, expected_fingerprint):
    """Verify detached signatures in an isolated, public-only GPG home.

    No user configuration, private key, agent startup or automatic key retrieval
    is used. This function never interprets successful verification as publish
    status, owner approval, or native/build qualification.
    """
    need(public_key_fingerprint(public_key) == expected_fingerprint, "Original public primary fingerprint differs")
    need(type(pairs) is list and 0 < len(pairs) <= 84, "Invalid detached-signature roster")
    executable = shutil.which("gpg")
    need(executable is not None, "Public GPG verifier is unavailable")
    with tempfile.TemporaryDirectory(prefix="p2pkit-central-public-") as temporary:
        home = Path(temporary)
        os.chmod(home, 0o700)
        key = home / "public.asc"
        key.write_bytes(public_key)
        environment = {"PATH": os.defpath, "HOME": str(home), "GNUPGHOME": str(home), "LC_ALL": "C"}
        common = [executable, "--no-options", "--batch", "--no-tty", "--homedir", str(home), "--no-autostart",
                  "--no-auto-key-retrieve", "--no-auto-key-import", "--auto-key-locate", "clear", "--no-auto-check-trustdb"]

        def run(arguments):
            try:
                result = subprocess.run(common + arguments, env=environment, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=GPG_TIMEOUT, check=False)
            except (OSError, subprocess.TimeoutExpired) as error:
                raise ValueError("Public GPG verification could not complete within its bound") from error
            need(result.returncode == 0, "Public GPG verifier returned nonzero status")
            need(len(result.stdout) <= MAX_GPG_OUTPUT, "Public GPG status exceeds bound")
            return result.stdout

        run(["--import", str(key)])
        listing = run(["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint", "--list-keys"])
        primary, allowed, pending = [], set(), None
        for line in listing.decode("utf-8", errors="replace").splitlines():
            fields = line.split(":")
            if fields[0] in ("pub", "sub"):
                need(len(fields) > 11, "Malformed public-key record")
                if fields[0] == "pub":
                    need(fields[1] not in ("r", "e", "d", "i"), "Public primary certificate is unusable")
                need(pending is None, "Missing public-key fingerprint record")
                pending = (fields[0], fields[1] not in ("r", "e", "d", "i"))
            elif fields[0] == "fpr":
                need(pending is not None and len(fields) > 9 and FINGERPRINT.fullmatch(fields[9]), "Malformed public fingerprint record")
                if pending[1]:
                    allowed.add(fields[9])
                if pending[0] == "pub":
                    primary.append(fields[9])
                pending = None
        need(pending is None and primary == [expected_fingerprint], "Imported public primary identity differs")
        signers = set()
        for artifact, signature in pairs:
            status = run(["--status-fd", "1", "--verify", str(signature), str(artifact)])
            signers.add(signature_identity(status, expected_fingerprint, allowed))
        return sorted(signers)


def _archive_members(archive, expected):
    items = archive.infolist()
    directories = {name[:index + 1] for name in expected for index, char in enumerate(name) if char == "/"}
    need(len(expected) <= len(items) <= len(expected) + len(directories), "Unexpected ZIP entry count")
    seen, total, files = set(), 0, {}
    for entry in items:
        name = entry.filename
        need(name == entry.orig_filename and name not in seen, "Duplicate/truncated ZIP member")
        seen.add(name)
        need(name in (directories if entry.is_dir() else expected), "Unsafe or undeclared ZIP member")
        mode = stat.S_IFMT(entry.external_attr >> 16)
        need(mode in (0, stat.S_IFDIR if entry.is_dir() else stat.S_IFREG) and not entry.flag_bits & 1 and
             entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and entry.extract_version <= 20,
             "Linked, encrypted or unsupported ZIP member")
        cursor = 0
        while cursor < len(entry.extra):
            need(cursor + 4 <= len(entry.extra), "Truncated ZIP extra field")
            kind, length = struct.unpack_from("<HH", entry.extra, cursor)
            cursor += 4
            need(kind != 1 and cursor + length <= len(entry.extra), "ZIP64 or truncated ZIP extra field")
            cursor += length
        need(not entry.comment and 0 <= entry.header_offset < archive.start_dir, "Unexpected ZIP comment/offset")
        if entry.is_dir():
            need(entry.file_size == entry.compress_size == entry.CRC == 0 and entry.compress_type == zipfile.ZIP_STORED,
                 "Directory member contains bytes")
        else:
            bound = MAX_SIGNATURE if name.endswith(".asc") else MAX_MEMBER
            if name.rsplit(".", 1)[-1] in CHECKSUMS:
                bound = 129
            need(0 < entry.file_size <= bound, "Empty or oversized ZIP member")
            total += entry.file_size
            need(total <= MAX_EXPANDED, "Expanded ZIP exceeds bound")
            files[name] = entry
    need(set(files) == expected and min(x.header_offset for x in items) == 0, "Incomplete or prefixed ZIP bundle")
    return files


def inspect(bundle, manifest, summary, public_key, source_sha, source_tree, version, *, verify_signatures=True):
    """Return a public receipt for exact original bytes; never infer publication.

    ``verify_signatures=False`` supports synthetic structure controls and
    unverified recovery-request preparation only. That preparatory metadata
    is not a verification result: its explicitly unverified receipt must never
    satisfy recovery admission. The CLI and accepting recovery execution both
    require full public-signature verification.
    """
    need(type(source_sha) is str and HEX40.fullmatch(source_sha) and type(source_tree) is str and HEX40.fullmatch(source_tree),
         "Exact lowercase source commit/tree are required")
    need(type(verify_signatures) is bool, "Signature-verification mode must be explicit")
    base = roster(version)
    expected = {name + suffix for name in base for suffix in ("", ".asc", ".md5", ".sha1", ".sha256", ".sha512")}
    manifest_raw = bounded_bytes(manifest, MAX_METADATA)
    summary_raw = bounded_bytes(summary, MAX_METADATA)
    public_raw = bounded_bytes(public_key, MAX_PUBLIC_KEY)
    document = json.loads(summary_raw, object_pairs_hook=unique_keys, parse_constant=lambda _: need(False, "Nonfinite JSON value"))
    keys = {"schemaVersion", "group", "version", "signingKeyFingerprint", "bundleFile", "bundleSha256", "bundleSizeBytes",
            "signedFiles", "sourceSha", "sourceTree", "manifestSha256", "publicKeyFile", "publicKeySha256"}
    need(type(document) is dict and set(document) == keys and type(document["schemaVersion"]) is int and document["schemaVersion"] == 2,
         "Original summary schema differs; missing originals cannot be regenerated")
    need(document["group"] == GROUP and document["version"] == version and document["sourceSha"] == source_sha and
         document["sourceTree"] == source_tree, "Original summary source/version differs")
    bundle, manifest, summary, public_key = map(Path, (bundle, manifest, summary, public_key))
    need(bundle.name.endswith(".zip") and document["bundleFile"] == bundle.name and
         manifest.name == bundle.stem + ".manifest.sha256" and summary.name == bundle.stem + ".summary.json" and
         public_key.name == bundle.stem + ".public.asc" and document["publicKeyFile"] == public_key.name,
         "Original output names differ")
    need(document["manifestSha256"] == sha256(manifest_raw) and document["publicKeySha256"] == sha256(public_raw),
         "Original manifest/public-certificate hash differs")
    fingerprint = public_key_fingerprint(public_raw)
    need(document["signingKeyFingerprint"] == fingerprint, "Original signing primary fingerprint differs")
    need(type(document["signedFiles"]) is int and document["signedFiles"] == 84 and
         type(document["bundleSizeBytes"]) is int and 0 < document["bundleSizeBytes"] < MAX_BUNDLE and
         type(document["bundleSha256"]) is str and HEX64.fullmatch(document["bundleSha256"]), "Incomplete original bundle identity")
    try:
        lines = manifest_raw.decode("ascii").splitlines(keepends=True)
    except UnicodeError as error:
        raise ValueError("Manifest must be exact ASCII SHA-256 rows") from error
    hashes = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)\n", line)
        need(match is not None and match[2] in expected and match[2] not in hashes, "Malformed, duplicate or undeclared manifest row")
        hashes[match[2]] = match[1]
    need(set(hashes) == expected and list(hashes) == sorted(expected), "Manifest must name the complete sorted 504-member set")
    records, signers = [], []
    with regular_input(bundle, MAX_BUNDLE - 1) as (stream, size), tempfile.TemporaryDirectory(prefix="p2pkit-central-inspect-") as temporary:
        need(size == document["bundleSizeBytes"] and size >= 22, "Bundle size differs")
        digest = hashlib.sha256()
        while block := stream.read(1024 ** 2):
            digest.update(block)
        need(digest.hexdigest() == document["bundleSha256"], "Original bundle hash differs")
        # A <1GiB, 504-file bundle needs neither ZIP64 nor concatenated/multidisk
        # archives. Bound its directory before allowing zipfile to parse it.
        stream.seek(-22, os.SEEK_END)
        end = struct.unpack("<4s4H2IH", stream.read(22))
        need(end[0] == b"PK\x05\x06" and end[1:3] == (0, 0) and end[3] == end[4] and end[4] < 65535 and
             end[5] <= MAX_METADATA and end[5] + end[6] == size - 22 and end[7] == 0,
             "Unexpected multidisk, ZIP64, prefixed or trailing ZIP directory")
        with zipfile.ZipFile(stream) as archive:
            need(archive.start_dir == end[6] and len(archive.infolist()) == end[4], "ZIP directory identity differs")
            files = _archive_members(archive, expected)
            paths, calculated, small = {}, {}, {}
            directory = Path(temporary)
            for index, name in enumerate(sorted(files)):
                entry = files[name]
                digests = {algorithm: hashlib.new(algorithm) for algorithm in CHECKSUMS} if name in base else {"sha256": hashlib.sha256()}
                output = directory / str(index)
                actual = 0
                with archive.open(entry) as member, output.open("xb") as destination:
                    while block := member.read(1024 ** 2):
                        actual += len(block)
                        need(actual <= entry.file_size, "ZIP member grew beyond declared size")
                        destination.write(block)
                        for value in digests.values():
                            value.update(block)
                need(actual == entry.file_size and digests["sha256"].hexdigest() == hashes[name], "Original member hash/size differs")
                records.append({"path": name, "bytes": actual, "sha256": hashes[name]})
                if name in base:
                    calculated[name] = {key: value.hexdigest() for key, value in digests.items()}
                    paths[name] = output
                elif name.endswith(".asc"):
                    paths[name] = output
                else:
                    small[name] = output.read_bytes()
            for name in base:
                for algorithm in CHECKSUMS:
                    need(small[name + "." + algorithm] == (calculated[name][algorithm] + "\n").encode("ascii"),
                         "Publication checksum sidecar differs")
            if verify_signatures:
                pairs = [(paths[name], paths[name + ".asc"]) for name in sorted(base)]
                signers = verify_public_signatures(public_raw, pairs, fingerprint)
    return {"schemaVersion": 1, "scope": "VERIFIED_PUBLIC_SIGNATURES" if verify_signatures else "UNVERIFIED_SYNTHETIC_STRUCTURE",
            "signaturesVerified": verify_signatures, "sourceSha": source_sha, "sourceTree": source_tree,
            "group": GROUP, "version": version, "bundleFile": bundle.name, "bundleSha256": document["bundleSha256"],
            "bundleSizeBytes": document["bundleSizeBytes"], "manifestSha256": sha256(manifest_raw), "summarySha256": sha256(summary_raw),
            "publicKeyFile": public_key.name, "publicKeySha256": sha256(public_raw), "signingKeyFingerprint": fingerprint,
            "signerFingerprints": signers, "coordinates": 15, "signedFiles": 84, "memberCount": len(records), "members": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "manifest", "summary", "public-key"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("source-sha", "source-tree", "version"):
        parser.add_argument("--" + name, required=True)
    options = parser.parse_args()
    receipt = inspect(options.bundle, options.manifest, options.summary, options.public_key,
                      options.source_sha, options.source_tree, options.version)
    # CLI has no unverified mode. Emit only compact public identity metadata;
    # API callers also receive the complete 504-member receipt.
    print(json.dumps({key: value for key, value in receipt.items() if key != "members"}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, RuntimeError, zipfile.BadZipFile) as error:
        print("FATAL: retained public Central bundle inspection failed: " + str(error), file=sys.stderr)
        raise SystemExit(1)
