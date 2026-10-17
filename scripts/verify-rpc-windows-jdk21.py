#!/usr/bin/env python3
"""Compare a fixed supplier archive with an extracted JDK; never download, extract or execute it.

The new-only result describes observed bytes, not an immutable directory lease or installed authority.
Packaging must select this actual verified home and preserve it until its tools finish. This helper alone
does not wire a build task, qualify a launcher, verify signatures or suppress startup overrides.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "samples/p2p-sample-rpc/native/windows-loader-jdk21/runtime-supplier.properties"
MAX_ENTRIES = 100_000
MAX_FILE = 512 * 1024 * 1024
MAX_EXPANDED = 2 * 1024 * 1024 * 1024
REQUIRED = {"bin/java.exe", "bin/javac.exe", "bin/jpackage.exe", "bin/jlink.exe", "bin/jli.dll",
            "bin/server/jvm.dll", "lib/modules", "jmods/java.base.jmod", "release"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(info):
    return info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns


def ordinary(path, directory=False):
    info = path.lstat()
    require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
            "Linked or reparse input refused")
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), "Nonordinary input refused")
    return info


def checked_path(path, directory=False):
    require(".." not in path.parts, "Parent traversal refused")
    path = path.absolute()
    for parent in reversed(path.parents):
        ordinary(parent, True)
    ordinary(path, directory)
    return path


def file_digest(path, maximum):
    before = ordinary(path)
    require(before.st_size <= maximum, "File exceeds size bound")
    digest, count = hashlib.sha256(), 0
    with path.open("rb") as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), "Opened file identity changed")
        while chunk := stream.read(1024 * 1024):
            count += len(chunk)
            require(count <= maximum, "File grew beyond size bound")
            digest.update(chunk)
        require(identity(os.fstat(stream.fileno())) == identity(before), "Open file changed")
    require(count == before.st_size and identity(ordinary(path)) == identity(before), "File changed")
    return count, digest.hexdigest(), identity(before)


def load_pin():
    raw = PIN.read_bytes()
    require(len(raw) <= 4096 and raw.endswith(b"\n"), "Invalid supplier descriptor")
    rows = [line.split("=", 1) for line in raw.decode("ascii").splitlines()]
    require(all(len(row) == 2 for row in rows), "Malformed supplier descriptor")
    pin = dict(rows)
    require(len(pin) == len(rows) and set(pin) == {
        "schema", "vendor", "os", "architecture", "vm", "version", "archive", "bytes", "sha256", "url", "source"
    }, "Unexpected supplier descriptor fields")
    require((pin["schema"], pin["vendor"], pin["os"], pin["architecture"], pin["vm"]) ==
            ("1", "Temurin", "windows", "x64", "hotspot"), "Unsupported supplier")
    require(re.fullmatch(r"21\.[0-9.]+\+[0-9]+", pin["version"]) and
            re.fullmatch(r"OpenJDK21U-jdk_x64_windows_hotspot_[0-9._]+\.zip", pin["archive"]) and
            re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]) and pin["bytes"].isdigit(), "Invalid supplier pin")
    pin["bytes"] = int(pin["bytes"])
    require(0 < pin["bytes"] <= MAX_FILE, "Supplier archive exceeds bound")
    return pin, hashlib.sha256(raw).hexdigest()


def member_parts(name):
    require(name and "\\" not in name and not name.startswith("/"), "Unsafe ZIP path")
    parts = name.removesuffix("/").split("/")
    for part in parts:
        require(part not in ("", ".", "..") and part[-1:] not in (".", " ") and
                not any(ord(char) < 32 or ord(char) > 126 or char in ':<>"|?*' for char in part),
                "Unsafe ZIP component")
        require(not re.fullmatch(r"(?:CON|CONIN\$|CONOUT\$|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part, re.I),
                "Windows device alias refused")
    return parts


def inventory(archive):
    entries = archive.infolist()
    require(0 < len(entries) <= MAX_ENTRIES, "ZIP entry count exceeds bound")
    root, seen, files, directories, total = None, set(), {}, set(), 0
    for entry in entries:
        require(entry.orig_filename == entry.filename, "Truncated ZIP name refused")
        parts = member_parts(entry.filename)
        require(not entry.flag_bits & 1 and entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                "Encrypted or unsupported ZIP entry")
        mode = entry.external_attr >> 16
        require(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR) and not entry.external_attr & 0x400,
                "Linked or special ZIP entry refused")
        require((not stat.S_ISDIR(mode) or entry.is_dir()) and
                (not stat.S_ISREG(mode) or not entry.is_dir()), "ZIP directory type disagreement")
        root = parts[0] if root is None else root
        require(parts[0] == root, "Multiple ZIP roots refused")
        key = "/".join(parts).casefold()
        require(key not in seen, "Duplicate or case-colliding ZIP entry")
        seen.add(key)
        require(len(parts) > 1 or entry.is_dir(), "Expected one JDK directory root")
        relative = "/".join(parts[1:])
        for index in range(1, len(parts) - 1):
            directories.add("/".join(parts[1:index + 1]))
        if entry.is_dir():
            require(entry.file_size == 0, "Nonempty ZIP directory")
            if relative:
                directories.add(relative)
        else:
            require(0 <= entry.file_size <= MAX_FILE, "ZIP file exceeds bound")
            total += entry.file_size
            require(total <= MAX_EXPANDED, "Expanded ZIP exceeds bound")
            files[relative] = entry
    all_paths = list(files) + list(directories)
    require(len({name.casefold() for name in all_paths}) == len(all_paths), "ZIP file/directory alias refused")
    require(REQUIRED <= files.keys(), "Required JDK tools missing")
    return files, directories


def verify(archive_path, home, pin):
    archive_path, home = checked_path(archive_path), checked_path(home, True)
    size, digest, archive_identity = file_digest(archive_path, pin["bytes"])
    require(size == pin["bytes"] and digest == pin["sha256"], "Supplier archive digest mismatch")
    snapshots = {home: identity(ordinary(home, True))}
    rows = []
    with archive_path.open("rb") as stream:
        require(identity(os.fstat(stream.fileno())) == archive_identity, "Archive identity changed")
        with zipfile.ZipFile(stream) as archive:
            files, directories = inventory(archive)
            actual_files, actual_directories = set(), set()
            def walk_error(error):
                raise error
            for parent, dirs, names in os.walk(home, followlinks=False, onerror=walk_error):
                for name in dirs:
                    path = Path(parent) / name
                    snapshots[path] = identity(ordinary(path, True))
                    actual_directories.add(path.relative_to(home).as_posix())
                for name in names:
                    path = Path(parent) / name
                    snapshots[path] = identity(ordinary(path))
                    actual_files.add(path.relative_to(home).as_posix())
                require(len(actual_files) + len(actual_directories) <= MAX_ENTRIES, "JDK home count exceeds bound")
            require(actual_files == files.keys() and actual_directories == directories, "JDK home inventory mismatch")
            for name, entry in sorted(files.items()):
                hasher, count = hashlib.sha256(), 0
                with archive.open(entry) as member:
                    while chunk := member.read(1024 * 1024):
                        count += len(chunk)
                        require(count <= entry.file_size, "ZIP member exceeds declared size")
                        hasher.update(chunk)
                require(count == entry.file_size, "Truncated ZIP member")
                observed_size, observed_hash, observed_identity = file_digest(home / name, MAX_FILE)
                require(observed_identity == snapshots[home / name] and observed_size == count and
                        observed_hash == hasher.hexdigest(), "JDK home differs from supplier archive")
                rows.append({"path": name, "bytes": count, "sha256": observed_hash})
        require(identity(os.fstat(stream.fileno())) == archive_identity, "Archive changed")
    require(identity(ordinary(archive_path)) == archive_identity, "Archive path changed")
    for path, before in snapshots.items():
        require(identity(ordinary(path, path == home or path.relative_to(home).as_posix() in directories)) == before,
                "JDK home changed during verification")
    return {"fileCount": len(rows), "directoryCount": len(directories), "bytes": sum(row["bytes"] for row in rows),
            "inventorySha256": hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "jdk-home", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        checked_path(args.output.parent, True)
        require(not args.output.exists() and not args.output.is_symlink(), "Result already exists")
        require(not args.output.absolute().is_relative_to(args.jdk_home.absolute()), "Result cannot modify JDK home")
        verifier_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        pin, pin_hash = load_pin()
        result = verify(args.archive, args.jdk_home, pin)
        require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == verifier_hash and
                hashlib.sha256(PIN.read_bytes()).hexdigest() == pin_hash, "Verifier source changed")
        document = {"schema": 1, "scope": "SUPPLIER_ARCHIVE_AND_JDK_HOME_BYTES_NOT_INSTALLED_AUTHORITY",
                    "supplier": pin, "home": result,
                    "source": {"pinSha256": pin_hash, "verifierSha256": verifier_hash}}
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(document, stream, sort_keys=True, indent=2)
            stream.write("\n")
        print("JDK_SUPPLIER_BYTES_PASS")
        return 0
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile, RuntimeError, EOFError, zlib.error):
        print("JDK_SUPPLIER_BYTES_REFUSED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
