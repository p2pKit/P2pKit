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


ADAPTER_MODULE = "dev.p2pkit.rpc.windows.loader"
ADAPTER_PREFIX = "dev/p2pkit/rpc/windows/loader/"
ADAPTER_JAR = "p2pkit-windows-loader-jdk21.jar"
ADAPTER_PATH = "app/resources/rpc-loader-jdk21/" + ADAPTER_JAR
ADAPTER_SCOPE = "STATIC_JDK21_PREVIEW_MODULE_NOT_LOAD_AUTHORITY"
ADAPTER_CLASSES = frozenset(("module-info.class", *(ADAPTER_PREFIX + name + ".class" for name in (
    "Probe", "WindowsLoader", "WindowsLoaderRuntime", "WindowsX64Frame", "WindowsX64Frame$AcquisitionFailure",
    "WindowsX64Frame$CloseFailure", "WindowsX64Frame$CleanupObservation", "WindowsX64Frame$1",
    "WindowsJniRegistrationOwner", "WindowsJniRegistrationOwner$Failure", "WindowsJniRegistrationOwner$FailureKind",
    "WindowsJniRegistrationOwner$Invocation", "WindowsJniRegistrationOwner$Report",
    "WindowsJniRegistrationOwner$Retention", "WindowsJniRegistrationOwner$State",
    "WindowsJniRegistrationInvocation", "WindowsJniRegistrationInvocation$AcquisitionFailure",
    "WindowsJniRegistrationInvocation$RetirementFailure",
))))
ADAPTER_OPTIONS = (
    "--enable-preview", "--module-path=$APPDIR/resources/rpc-loader-jdk21",
    "--add-modules=" + ADAPTER_MODULE, "--enable-native-access=" + ADAPTER_MODULE,
)


class ClassBytes:
    """Bounded structural class/Module reader, not a JVM bytecode verifier or execution authority."""
    def __init__(self, data):
        self.data, self.offset = data, 0

    def take(self, count):
        require(0 <= count <= len(self.data) - self.offset, "Truncated adapter class structure")
        result = self.data[self.offset:self.offset + count]
        self.offset += count
        return result

    def number(self, width):
        return int.from_bytes(self.take(width), "big")

    def finished(self):
        require(self.offset == len(self.data), "Trailing adapter class structure")


def adapter_class(data, name):
    reader = ClassBytes(data)
    require(reader.take(4) == b"\xca\xfe\xba\xbe", "Invalid adapter class header")
    minor, major = reader.number(2), reader.number(2)
    require(major == 65 and minor in (0, 65535), "Adapter requires JDK21 class family")
    if name == ADAPTER_PREFIX + "Probe.class":
        require(minor == 65535, "Adapter Probe must require preview class semantics")
    pool = [None]
    count = reader.number(2)
    require(count > 1, "Empty adapter constant pool")
    while len(pool) < count:
        tag = reader.number(1)
        if tag == 1:
            # Constant pool strings use modified UTF-8. Compared structural names are ASCII;
            # retain raw bytes rather than decoding unrelated literal constants incorrectly.
            item = reader.take(reader.number(2))
        elif tag in (7, 8, 16, 19, 20):
            item = reader.number(2)
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
            item = reader.take(4)
        elif tag in (5, 6):
            item = reader.take(8)
        elif tag == 15:
            item = reader.take(3)
        else:
            raise ValueError("Unknown adapter constant pool tag")
        pool.append((tag, item))
        if tag in (5, 6):
            pool.append(None)
    require(len(pool) == count, "Invalid adapter constant pool slots")

    def cp(index, tag):
        require(0 < index < count and pool[index] is not None and pool[index][0] == tag,
                "Invalid adapter constant pool reference")
        return pool[index][1]

    def text(index):
        return cp(index, 1)

    def attributes(owner):
        result = []
        for _ in range(owner.number(2)):
            result.append((text(owner.number(2)), owner.take(owner.number(4))))
        return result

    access, this, parent = reader.number(2), reader.number(2), reader.number(2)
    require(text(cp(this, 7)) == name[:-6].encode("ascii"), "Adapter class entry/name mismatch")
    interfaces = reader.number(2)
    reader.take(interfaces * 2)
    members = []
    for _ in range(2):
        member_count = reader.number(2)
        members.append(member_count)
        for _ in range(member_count):
            reader.number(2)
            text(reader.number(2))
            text(reader.number(2))
            attributes(reader)
    attrs = attributes(reader)
    reader.finished()
    if name == "module-info.class":
        require(minor == 0 and access == 0x8000 and parent == 0 and interfaces == 0 and members == [0, 0],
                "Invalid adapter module descriptor class")
        require(len({key for key, _ in attrs}) == len(attrs) and
                all(key in (b"Module", b"SourceFile") for key, _ in attrs),
                "Unexpected adapter module attributes")
        modules = [value for key, value in attrs if key == b"Module"]
        require(len(modules) == 1, "Missing or duplicate adapter Module attribute")
        module = ClassBytes(modules[0])
        require(text(cp(module.number(2), 19)) == ADAPTER_MODULE.encode("ascii") and
                module.number(2) == 0 and module.number(2) == 0, "Unexpected adapter module identity/flags")
        require(module.number(2) == 1 and text(cp(module.number(2), 19)) == b"java.base" and
                module.number(2) == 0x8000, "Unexpected adapter module dependency")
        version = module.number(2)
        if version:
            require(re.fullmatch(rb"21(?:\.[0-9]+)*(?:[-+][A-Za-z0-9.+_-]+)?", text(version)),
                    "Unexpected adapter module java.base version")
        require(module.number(2) == 1 and text(cp(module.number(2), 20)) == ADAPTER_PREFIX[:-1].encode("ascii") and
                module.number(2) == 0 and module.number(2) == 0, "Unexpected adapter module exports")
        require(module.number(2) == 0 and module.number(2) == 0 and module.number(2) == 0,
                "Unexpected adapter module opens/services")
        module.finished()
    return {"entry": name, "bytes": len(data), "sha256": digest(data), "major": major, "minor": minor}


def inspect_adapter(image, release):
    directory = image
    for part in ("app", "resources", "rpc-loader-jdk21"):
        directory = directory / part
        require(directory.is_dir() and not directory.is_symlink() and
                not getattr(directory.lstat(), "st_file_attributes", 0) & 0x400,
                "Expected ordinary adapter resources/ancestors")
    require(directory.is_dir() and not directory.is_symlink() and
            not getattr(directory.lstat(), "st_file_attributes", 0) & 0x400 and
            {entry.name for entry in directory.iterdir()} == {ADAPTER_JAR},
            "Missing or unexpected adapter resources")
    jar = directory / ADAPTER_JAR
    before = ordinary(jar)
    require(0 < before.st_size <= 16 * 1024 * 1024, "Adapter JAR exceeds bound")
    classes = []
    with jar.open("rb") as stream, zipfile.ZipFile(stream) as archive:
        require(identity(os.fstat(stream.fileno())) == identity(before), "JAR changed before inspection")
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        require(len(entries) <= 64 and len(set(names)) == len(names), "Duplicate or oversized adapter inventory")
        allowed_dirs = {"META-INF/", "dev/", "dev/p2pkit/", "dev/p2pkit/rpc/", "dev/p2pkit/rpc/windows/",
                        ADAPTER_PREFIX}
        require(set(names) - allowed_dirs == ADAPTER_CLASSES | {"META-INF/MANIFEST.MF", "META-INF/LICENSE"},
                "Missing, unexpected or test adapter entry")
        for entry in entries:
            require(not entry.flag_bits & 1 and 0 <= entry.file_size <= 1024 * 1024,
                    "Encrypted or oversized adapter entry")
            with archive.open(entry) as member:
                data = member.read(1024 * 1024 + 1)
            require(len(data) == entry.file_size, "Adapter entry size mismatch")
            if entry.filename in ADAPTER_CLASSES:
                classes.append(adapter_class(data, entry.filename))
            elif entry.filename == "META-INF/LICENSE":
                # The maintained root Gradle configuration injects the exact repository license into every JAR.
                require(data == read(Path(__file__).resolve().parents[1] / "LICENSE", 65536),
                        "Adapter license differs from maintained repository license")
            elif entry.filename == "META-INF/MANIFEST.MF":
                require(data.replace(b"\r\n", b"\n") == b"Manifest-Version: 1.0\n\n",
                        "Unexpected adapter manifest authority or classpath")
            else:
                require(not data, "Nonempty adapter directory entry")
        jar_bytes, jar_hash = file_digest(jar, stream, before, 16 * 1024 * 1024)
    versions = [match.group(1) for line in release.splitlines()
                if (match := re.fullmatch(r'JAVA_VERSION="([^"\r\n]*)"', line))]
    require(len(versions) == 1 and re.fullmatch(r"21(?:\.[0-9]+)*(?:[-+][A-Za-z0-9.+_-]+)?", versions[0]),
            "Preview adapter requires linked JDK21 metadata")
    cfg = read(image / "app/P2pKit Sample.cfg", 65536)
    section, options = None, []
    sections = set()
    for line in cfg.decode("utf-8").splitlines():
        require("ALL-UNNAMED" not in line, "Adapter must not use unnamed authority")
        require(ADAPTER_JAR not in line, "Adapter must not use application classpath")
        if line.startswith("["):
            require(re.fullmatch(r"\[[A-Za-z]+\]", line) and line not in sections,
                    "Unexpected or duplicate launcher configuration section")
            sections.add(line)
            section = line
        elif line.startswith("java-options=") and section != "[JavaOptions]":
            require(not any(flag in line for flag in (*ADAPTER_OPTIONS, "--module-path", "--enable-native-access")),
                    "Adapter runtime option outside maintained launcher section")
        elif section == "[JavaOptions]" and line:
            require(line.startswith("java-options="), "Unexpected launcher Java option record")
            options.append(line[len("java-options="):])
    sensitive = ("--enable-preview", "--module-path", "-p", "--add-modules", "--enable-native-access",
                 "--patch-module", "-javaagent", "-agentlib", "-agentpath", "-Xbootclasspath")
    for option in options:
        if option.startswith(sensitive):
            require(option in ADAPTER_OPTIONS, "Unexpected adapter launcher runtime option")
    require(all(options.count(option) == 1 for option in ADAPTER_OPTIONS),
            "Missing or duplicate explicit adapter runtime option")
    return {"scope": ADAPTER_SCOPE, "file": ADAPTER_PATH, "jarBytes": jar_bytes, "jarSha256": jar_hash,
            "module": ADAPTER_MODULE, "probeMajor": 65, "probeMinor": 65535,
            "classes": sorted(classes, key=lambda value: value["entry"]),
            "launcher": {"file": "app/P2pKit Sample.cfg", "sha256": digest(cfg),
                         "requiredOptions": list(ADAPTER_OPTIONS)},
            "nativeExecution": "NOT_PERFORMED", "installedAuthority": "NOT_ESTABLISHED"}


def inspect(image, compiler, msi, source, tree, preview_adapter=False):
    require(re.fullmatch(r"[0-9a-f]{40}", source) and re.fullmatch(r"[0-9a-f]{40}", tree),
            "Full source/tree pins required")
    require(image.is_dir() and not image.is_symlink(), "Expected existing app image directory")
    adapter_directory = image / "app/resources/rpc-loader-jdk21"
    require(preview_adapter or not (adapter_directory.exists() or adapter_directory.is_symlink()),
            "Preview adapter resources require explicit optional inspection")
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
            require(not any(
                entry.filename.startswith(ADAPTER_PREFIX) or
                re.fullmatch(r"META-INF/versions/[^/]+/" + ADAPTER_PREFIX + r".*", entry.filename)
                for entry in archive.infolist()), "Adapter must not be duplicated on application classpath")
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
    adapter = inspect_adapter(image, release) if preview_adapter else None
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
    return {**({"adapter": adapter} if adapter is not None else {}),
            "scope": SCOPE, "source": source, "tree": tree, "result": "PASS",
            "nativeAbi": 13, "capabilities": "0x43", "dllBytes": len(library), "dllSha256": digest(library),
            "manifestSha256": digest(manifest), "parentPin": owners[0], "applicationJar": application_owners[0],
            "requiredClassJars": class_jars, "classInventory": "STATIC_ENTRIES_ONLY_NOT_LINKAGE_OR_EXECUTION",
            "declaredUnsupportedModule": True,
            "msi": {"file": msi.name, "bytes": installer.st_size, "sha256": hasher.hexdigest()},
            "installedPayloadEquality": "NOT_PERFORMED", "nativeExecution": "NOT_PERFORMED",
            "runtimeQualification": "NOT_PERFORMED", "signing": "NOT_PERFORMED"}


def retain_launcher_diagnostics(image, destination, source, tree):
    """Retain two bounded build outputs even when inspection refuses them. Never an acceptance receipt."""
    require(re.fullmatch(r"[0-9a-f]{40}", source) and re.fullmatch(r"[0-9a-f]{40}", tree),
            "Full source/tree pins required")
    for directory in (image, image / "app", image / "runtime"):
        info = directory.lstat()
        require(stat.S_ISDIR(info.st_mode) and not directory.is_symlink() and
                not getattr(info, "st_file_attributes", 0) & 0x400,
                "Expected ordinary build image diagnostic directories")
    destination.mkdir(mode=0o700)
    entries = []
    for relative, output in (("app/P2pKit Sample.cfg", "launcher.cfg"), ("runtime/release", "runtime-release")):
        data = read(image / relative, 65536)
        with (destination / output).open("xb") as target:
            target.write(data)
        entries.append({"input": relative, "file": output, "bytes": len(data), "sha256": digest(data)})
    with (destination / "diagnostics.json").open("x", encoding="utf-8") as target:
        json.dump({"scope": "BUILD_IMAGE_DIAGNOSTICS_NOT_ACCEPTANCE_OR_LOAD_AUTHORITY",
                   "source": source, "tree": tree, "files": entries}, target, indent=2)
        target.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    for name in ("compiler", "msi", "output"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--tree", required=True)
    parser.add_argument("--preview-adapter", action="store_true")
    parser.add_argument("--diagnostics", type=Path)
    parser.add_argument("--diagnostics-only", action="store_true")
    args = parser.parse_args()
    if args.diagnostics_only:
        if args.diagnostics is None or args.preview_adapter or any((args.compiler, args.msi, args.output)):
            parser.error("Diagnostics-only requires --diagnostics and forbids inspection/output arguments")
        retain_launcher_diagnostics(args.image, args.diagnostics, args.source, args.tree)
        print("BUILD_IMAGE_DIAGNOSTICS_RETAINED_NOT_ACCEPTANCE")
        return
    if any(value is None for value in (args.compiler, args.msi, args.output)):
        parser.error("Inspection requires --compiler, --msi and --output")
    if args.diagnostics is not None:
        retain_launcher_diagnostics(args.image, args.diagnostics, args.source, args.tree)
    result = inspect(args.image, args.compiler, args.msi, args.source, args.tree, args.preview_adapter)
    with args.output.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, indent=2)
        destination.write("\n")
    print(SCOPE + ": PASS")


if __name__ == "__main__":
    main()
