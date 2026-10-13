#!/usr/bin/env python3
"""Inspect existing Windows app/MSI bytes; never load a DLL, install, sign or grant runtime authority."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import zipfile

PIN = "META-INF/p2pkit/windows-profile-parent.properties"
DLL = "p2pkit-windows-profile.dll"
SCOPE = "WINDOWS_APP_IMAGE_BYTES_NOT_INSTALLED_OR_RUNTIME_QUALIFIED"
# Static presence checks only. A class entry/hash does not establish launcher classpath, linkage,
# first native-load authority, actual navigation, or installed-app execution.
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
    "dev/p2pkit/sample/rpc/profile/WindowsProfileCustodyJni.class",
    "dev/p2pkit/sample/rpc/profile/WindowsProfilePinnedImage.class",
)
REQUIRED_CLASSES = frozenset((*APPLICATION_CLASSES, *RPC_CLASSES))
MAX_CLASS = 16 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ordinary(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not path.is_symlink() and
            not getattr(info, "st_file_attributes", 0) & 0x400, "Expected an ordinary input file")
    return info


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_mode)


def read(path, limit):
    info = ordinary(path)
    require(0 < info.st_size <= limit, "Input size outside bound")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    require(len(data) == info.st_size and identity(ordinary(path)) == identity(info),
            "Input changed during inspection")
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path, stream, before, maximum):
    # Hash the same open file whose central directory and pin were inspected. This is an
    # observation in our build directory, not installed-file custody or first-load authority.
    require(0 < before.st_size <= maximum, "Input file exceeds digest bound")
    require(identity(os.fstat(stream.fileno())) == identity(before), "JAR changed before digest")
    hasher = hashlib.sha256()
    total = 0
    stream.seek(0)
    while chunk := stream.read(1024 * 1024):
        total += len(chunk)
        require(total <= before.st_size, "Input grew during digest")
        hasher.update(chunk)
    require(total == before.st_size and identity(os.fstat(stream.fileno())) == identity(before) and
            identity(ordinary(path)) == identity(before), "JAR changed during inspection")
    return total, hasher.hexdigest()


def fields(data, keys):
    require(len(data) <= 4096 and data.endswith(b"\n"), "Noncanonical component record")
    require(all(byte == 10 or 32 <= byte <= 126 for byte in data), "Noncanonical record encoding")
    lines = data.decode("ascii").splitlines()
    require(len(lines) == len(keys), "Unexpected component record fields")
    result = {}
    for key, line in zip(keys, lines):
        require(line.startswith(key + "="), "Missing, duplicate or reordered component field")
        result[key] = line[len(key) + 1:]
    return result


def inspect_required_classes(archive):
    observations = []
    seen = set()
    for entry in archive.infolist():
        versioned = re.fullmatch(r"META-INF/versions/[^/]+/(.+)", entry.filename)
        require(not versioned or versioned.group(1) not in REQUIRED_CLASSES,
                "Versioned required application class could shadow its reviewed base entry")
        if entry.filename not in REQUIRED_CLASSES:
            continue
        require(entry.filename not in seen, "Duplicate required application class in JAR")
        seen.add(entry.filename)
        require(not entry.flag_bits & 1 and 0 < entry.file_size <= MAX_CLASS,
                "Encrypted, empty or oversized required application class")
        with archive.open(entry) as stream:
            data = stream.read(MAX_CLASS + 1)
        require(len(data) == entry.file_size, "Required application class exceeds its declared size")
        observations.append({"entry": entry.filename, "bytes": len(data), "sha256": digest(data)})
    return sorted(observations, key=lambda value: value["entry"])


def inspect(image, compiler, msi, source, tree):
    require(re.fullmatch(r"[0-9a-f]{40}", source) and re.fullmatch(r"[0-9a-f]{40}", tree),
            "Full source/tree pins required")
    require(image.is_dir() and not image.is_symlink(), "Expected existing app image directory")
    compiler_fields = fields(read(compiler, 512), ["schema", "scope", "source", "tree", "sha256"])
    require(compiler_fields["schema"] == "1" and compiler_fields["scope"] == "COMPILER_BYTES_ONLY" and
            compiler_fields["source"] == source and compiler_fields["tree"] == tree and
            re.fullmatch(r"[0-9a-f]{64}", compiler_fields["sha256"]), "Compiler source pin mismatch")

    native = image / "app/resources/rpc-profile/windows-x64"
    require(native.is_dir() and not native.is_symlink(), "Missing native app resources")
    require({path.name for path in native.iterdir()} == {DLL, "component.manifest"},
            "Missing or unexpected native app resource")
    library = read(native / DLL, 32 * 1024 * 1024)
    manifest = read(native / "component.manifest", 4096)
    require(digest(library) == compiler_fields["sha256"], "Packaged DLL differs from compiler bytes")
    component = fields(manifest, ["schema", "component", "abi", "platform", "arch", "source", "tree", "clean",
                                 "file", "bytes", "sha256", "capabilities"])
    require(component == dict(zip(component, ["1", "windows-profile-custody", "13", "windows", "x86_64",
            source, tree, "true", DLL, str(len(library)), digest(library), "0x43"])),
            "Packaged manifest differs from current component contract")

    # The parent pin belongs to the existing application's packaged classpath. Like the macOS manifest JAR,
    # this is packaging metadata only; it is not independent installed-launcher/ACL/signature authority.
    jars = list((image / "app").glob("*.jar"))
    require(0 < len(jars) <= 512, "Unsupported application classpath inventory")
    owners = []
    application_owners = []
    class_jars = []
    class_owners = {entry: [] for entry in REQUIRED_CLASSES}
    for jar in sorted(jars):
        before = ordinary(jar)
        require(before.st_size <= 512 * 1024 * 1024, "Oversized application JAR")
        with jar.open("rb") as stream, zipfile.ZipFile(stream) as archive:
            require(identity(os.fstat(stream.fileno())) == identity(before), "JAR changed before inspection")
            require(len(archive.infolist()) <= 100_000, "Oversized JAR inventory")
            classes = inspect_required_classes(archive)
            for entry in classes:
                class_owners[entry["entry"]].append(jar.name)
            if any(entry["entry"] == APPLICATION_CLASSES[0] for entry in classes):
                application_owners.append(jar.name)
            entries = [entry for entry in archive.infolist() if entry.filename == PIN]
            pin_bytes = None
            if entries:
                require(len(entries) == 1 and 0 < entries[0].file_size <= 4096 and not entries[0].flag_bits & 1,
                        "Duplicate, encrypted or oversized parent pin")
                with archive.open(entries[0]) as pin_stream:
                    pin_bytes = pin_stream.read(4097)
                require(len(pin_bytes) == entries[0].file_size, "Parent pin exceeds its declared size")
                pin = fields(pin_bytes, ["schema", "scope", "source", "tree", "manifestSha256", "dllSha256"])
                require(pin == {"schema": "1", "scope": "PACKAGED_COMPONENT_PIN_NOT_LOAD_AUTHORITY",
                                "source": source, "tree": tree, "manifestSha256": digest(manifest),
                                "dllSha256": digest(library)}, "Packaged parent pin mismatch")
            if pin_bytes is not None or classes:
                jar_bytes, jar_hash = file_digest(jar, stream, before, 512 * 1024 * 1024)
                observed = {"file": jar.name, "jarBytes": jar_bytes, "jarSha256": jar_hash}
                if pin_bytes is not None:
                    owners.append({**observed, "pinSha256": digest(pin_bytes)})
                if classes:
                    class_jars.append({**observed, "classes": classes})
            else:
                require(identity(os.fstat(stream.fileno())) == identity(before) and
                        identity(ordinary(jar)) == identity(before), "JAR changed during inspection")
    require(len(owners) == 1, "Expected exactly one maintained application parent pin")
    require(len(application_owners) == 1,
            "Expected exactly one maintained Desktop application and required class owner")
    require(all(len(owners) == 1 for owners in class_owners.values()),
            "Missing or duplicate required application class owner")
    require(all(class_owners[entry] == application_owners for entry in APPLICATION_CLASSES),
            "Maintained Desktop required navigation/section must belong to its application JAR")

    # Metadata check only, not runtime execution or a proof that classes can load.
    release = read(image / "runtime/release", 65536).decode("utf-8")
    modules = [match.group(1) for line in release.splitlines()
               if (match := re.fullmatch(r'MODULES="([^"\r\n]*)"', line))]
    require(len(modules) == 1 and "jdk.unsupported" in modules[0].split(), "Packaged module dependency missing")
    installer = ordinary(msi)
    require(msi.suffix.lower() == ".msi" and 8 <= installer.st_size <= 1024 * 1024 * 1024,
            "Unsupported existing MSI output")
    hasher = hashlib.sha256()
    total = 0
    with msi.open("rb") as stream:
        require(stream.read(8) == bytes.fromhex("d0cf11e0a1b11ae1"), "MSI compound-file header missing")
        stream.seek(0)
        while chunk := stream.read(1024 * 1024):
            total += len(chunk)
            require(total <= installer.st_size, "MSI grew during inspection")
            hasher.update(chunk)
    require(total == installer.st_size and identity(ordinary(msi)) == identity(installer),
            "MSI changed during inspection")
    return {"scope": SCOPE, "source": source, "tree": tree, "result": "PASS",
            "nativeAbi": 13, "capabilities": "0x43", "dllBytes": len(library), "dllSha256": digest(library),
            "manifestSha256": digest(manifest), "parentPin": owners[0], "applicationJar": application_owners[0],
            "requiredClassJars": class_jars, "classInventory": "STATIC_ENTRIES_ONLY_NOT_LINKAGE_OR_EXECUTION",
            "declaredUnsupportedModule": True,
            "msi": {"file": msi.name, "bytes": installer.st_size, "sha256": hasher.hexdigest()},
            "installedPayloadEquality": "NOT_PERFORMED", "nativeExecution": "NOT_PERFORMED",
            "runtimeQualification": "NOT_PERFORMED", "signing": "NOT_PERFORMED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("image", "compiler", "msi", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--tree", required=True)
    args = parser.parse_args()
    result = inspect(args.image, args.compiler, args.msi, args.source, args.tree)
    with args.output.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, indent=2)
        destination.write("\n")
    print(SCOPE + ": PASS")


if __name__ == "__main__":
    main()
